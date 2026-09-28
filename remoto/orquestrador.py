# -*- coding: utf-8 -*-
"""O orquestrador dentro do app: no que ele trabalha, e o que o Adrian manda.

Pedido dele em 28/09/2026: "um orquestrador dentro do app para que eu possa
entender no que você está trabalhando agora e controlar tudo: fluxo, o que
você tem acesso, quais decisões toma e, principalmente, controlar a
capacidade e os trabalhos e agentes paralelos; também preciso ter visão clara
dos limites de sessão e semanal". Desenho: `~/.claude/plans/orquestrador-no-app.md`.

O PRINCIPIO. O orquestrador (a sessao principal do Claude Code) PUBLICA o
seu estado em arquivos, por esta CLI. O app MOSTRA esses arquivos e ESCREVE
comandos. O orquestrador LE os comandos (`pendentes`), aplica, e registra que
aplicou (`aplicado`). Tudo mora em `%LOCALAPPDATA%\\neural-fights\\orquestrador\\`
(estado vivo, fora do git), com escrita atomica e uma trava entre processos.

    estado.json                  orquestrador  agora[], fila[], concluidos_hoje[], modo
    decisoes_orquestrador.jsonl  orquestrador  decisoes tecnicas que ele tomou sozinho
    config.json                  `aplicado`    max_paralelo, modo, teto, forca total, fila pausada
    config_historico.jsonl       `aplicado`    toda mudanca de config: de, para, por qual comando
    comandos.jsonl               app           {id, em, comando, valor, aparelho}
    comandos_aplicados.jsonl     orquestrador  {id, em, resultado, motivo}
    uso.json, uso_historico.jsonl  servidor    a sonda do `rate_limit_event`
    acessos.json                 gerado        agentes, conectores, contas (sem segredo), o que o app dispara

A CONFIG SO MUDA QUANDO O ORQUESTRADOR ACEITA. O app grava o comando; o
`config.json` muda no `aplicado`. Assim a tela diz a verdade: "pendente"
enquanto ninguem leu, "aplicado" quando vale, "recusado" com o motivo.

CLI (a do orquestrador):

    python -m remoto.orquestrador agente-inicio --parte P --titulo T [--da-fila ID] [--relato R] [--forcar]
    python -m remoto.orquestrador relato <id> "o que aconteceu"
    python -m remoto.orquestrador agente-fim <id> [--situacao concluido|falhou|parado] [--commit H]... [--relato R]
    python -m remoto.orquestrador fila adicionar --parte P --item T [--posicao N]
    python -m remoto.orquestrador fila mover <id> subir|descer|topo
    python -m remoto.orquestrador fila remover <id>
    python -m remoto.orquestrador fila listar
    python -m remoto.orquestrador decisao --titulo T --escolha E [--porque P] [--alternativa A] [--parte P]
    python -m remoto.orquestrador modo um_por_vez|paralelo|forca_total
    python -m remoto.orquestrador pendentes [--json]
    python -m remoto.orquestrador aplicado <id> [--recusado MOTIVO] [--nota TEXTO]
    python -m remoto.orquestrador esperar [--intervalo S]     # sai quando chega comando
    python -m remoto.orquestrador config | estado | uso | pulso | onde
    python -m remoto.orquestrador sonda                        # mede o uso uma vez
    python -m remoto.orquestrador acessos [--conector NOME]... [--modo-permissao M]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from .config import runtime_dir

RAIZ = Path(__file__).resolve().parents[1]
# Os testes (e a instancia de teste na 8934) apontam para outra pasta.
PASTA = None
USO_EXTRA = None              # ~/.claude/uso_sessao.json, gravado pelo vigia_uso.py
AGENTES = None                # .claude/agents
CLAUDE_SETTINGS = None        # ~/.claude/settings.json
LANCADOR = None               # app_celular.cmd

MODOS = ("um_por_vez", "paralelo", "forca_total")
ROTULO_MODO = {"um_por_vez": "Um por vez", "paralelo": "Paralelo",
               "forca_total": "Força total"}
# O padrao segue as decisoes do Adrian no Grimorio: `geral/modo-de-trabalho`
# (um projeto por vez) e `geral/teto-de-uso` (50%; forca total 20 min antes
# de a janela renovar).
PADRAO_CONFIG = {"max_paralelo": 1, "modo": "um_por_vez", "teto_sessao_pct": 50,
                 "forca_total_antes_min": 20, "fila_pausada": False,
                 "sonda_min": 10}
MAX_PARALELO = 8
FORA_DO_AR_S = 15 * 60
TEXTO_MAX = 1000
COMANDOS_JANELA_S = 10 * 60
COMANDOS_NA_JANELA_MAX = 40
SONDA_TIMEOUT_S = 180
PASTA_SONDA = Path(r"E:\tmp_testes\sonda_uso")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")

# Nomes dos conectores que so o orquestrador enxerga (nao ha arquivo que os
# liste). Ele os declara com `acessos --conector`; estes sao os de 28/09.
CONECTORES_28_09 = ["Gmail (claude.ai)", "Google Drive (claude.ai)",
                    "Claude Docs (claude.ai)", "Wix (claude.ai)"]


class Recusa(Exception):
    """A operacao nao vai acontecer; a mensagem e para quem pediu."""


# ================================================================ lugares
def pasta() -> Path:
    if PASTA:
        return Path(PASTA)
    if os.environ.get("NF_ORQUESTRADOR_PASTA"):
        return Path(os.environ["NF_ORQUESTRADOR_PASTA"])
    return runtime_dir() / "orquestrador"


def arquivo(nome: str) -> Path:
    return pasta() / nome


def _uso_extra() -> Path:
    return Path(USO_EXTRA) if USO_EXTRA else Path.home() / ".claude" / "uso_sessao.json"


def _trava():
    """Uma escrita por vez, entre threads e entre processos (app e CLI)."""
    from .api_http import trava_arquivo
    return trava_arquivo(arquivo("orquestrador.lock"))


def _agora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _novo_id() -> str:
    return secrets.token_hex(4)


# ================================================================== disco
def _ler_json(caminho: Path, padrao):
    """O JSON do arquivo; `padrao` se ele nao existe. Ilegivel = Recusa.

    Tratar ilegivel como vazio apagaria a fila inteira na proxima escrita.
    """
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:
        return padrao
    except OSError as exc:
        raise Recusa(f"{caminho.name} não pôde ser lido: {exc}") from exc
    try:
        return json.loads(texto)
    except ValueError as exc:
        raise Recusa(f"{caminho.name} está ilegível") from exc


def _gravar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(f".{caminho.name}.{os.getpid()}."
                                   f"{threading.get_ident()}.tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    os.replace(temporario, caminho)


def _anexar(caminho: Path, linha: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _ler_jsonl(caminho: Path) -> tuple[list[dict], int]:
    """(linhas, quantas ilegiveis). A ilegivel e CONTADA, nunca some calada."""
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [], 0
    except OSError as exc:
        raise Recusa(f"{caminho.name} não pôde ser lido: {exc}") from exc
    linhas, ruins = [], 0
    for bruta in texto.splitlines():
        if not bruta.strip():
            continue
        try:
            linha = json.loads(bruta)
        except ValueError:
            ruins += 1
            continue
        if isinstance(linha, dict):
            linhas.append(linha)
        else:
            ruins += 1
    return linhas, ruins


# ================================================================= estado
def _estado_vazio() -> dict:
    return {"atualizado_em": None, "modo": ler_config()["modo"], "agora": [],
            "fila": [], "concluidos_hoje": []}


def ler_estado() -> dict:
    estado = _ler_json(arquivo("estado.json"), None)
    if estado is None:
        return _estado_vazio()
    if not isinstance(estado, dict):
        raise Recusa("estado.json está ilegível")
    for chave in ("agora", "fila", "concluidos_hoje"):
        if not isinstance(estado.get(chave), list):
            estado[chave] = []
    hoje = datetime.now().date().isoformat()
    estado["concluidos_hoje"] = [c for c in estado["concluidos_hoje"]
                                 if str(c.get("fim", ""))[:10] == hoje]
    return estado


def _gravar_estado(estado: dict) -> None:
    estado["atualizado_em"] = _agora_iso()
    _gravar_json(arquivo("estado.json"), estado)


def ler_config() -> dict:
    dados = _ler_json(arquivo("config.json"), {})
    if not isinstance(dados, dict):
        raise Recusa("config.json está ilegível")
    return {**PADRAO_CONFIG, **{k: v for k, v in dados.items() if k in PADRAO_CONFIG}}


def paralelo_efetivo(config: dict) -> int:
    """Quantos agentes de uma vez, de fato. Um por vez e um, qualquer que seja o max."""
    if config["modo"] == "um_por_vez":
        return 1
    return int(config["max_paralelo"])


def _mudar_config(chave: str, valor, origem: str, comando_id: str = "") -> None:
    config = ler_config()
    antes = config.get(chave)
    if antes == valor:
        return
    config[chave] = valor
    _gravar_json(arquivo("config.json"), config)
    _anexar(arquivo("config_historico.jsonl"),
            {"em": _agora_iso(), "chave": chave, "de": antes, "para": valor,
             "origem": origem, "comando": comando_id})


def _curto(texto, limite: int = 300) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


# ----------------------------------------------------------------- agentes
def agente_inicio(parte: str, titulo: str, *, da_fila: str = "", relato: str = "",
                  forcar: bool = False, agente_id: str = "") -> dict:
    """Um agente comecou. Recusa se passa da capacidade (sem `forcar`)."""
    with _trava():
        estado = ler_estado()
        config = ler_config()
        item_da_fila = None
        if da_fila:
            item_da_fila = next((f for f in estado["fila"] if f.get("id") == da_fila), None)
            if item_da_fila is None:
                raise Recusa(f"a fila não tem o item {da_fila}")
        parte = parte or (item_da_fila or {}).get("parte", "")
        titulo = titulo or (item_da_fila or {}).get("item", "")
        if not parte or not titulo:
            raise Recusa("diga a parte e o título (ou --da-fila)")
        if not forcar:
            limite = paralelo_efetivo(config)
            if len(estado["agora"]) >= limite:
                raise Recusa(f"já há {len(estado['agora'])} agente(s) e a capacidade é "
                             f"{limite} ({ROTULO_MODO.get(config['modo'])}); "
                             "use --forcar se o Adrian mandou")
            if config["fila_pausada"]:
                raise Recusa("a fila está pausada pelo Adrian; use --forcar se ele mandou")
            uso = ler_uso()
            if (uso["situacao"] == "ok" and uso["passou_teto"]
                    and config["modo"] != "forca_total"):
                raise Recusa(f"o uso da sessão está em {uso['medicao']['sessao_pct']:.0f}%, "
                             f"acima do teto de {config['teto_sessao_pct']}%")
        novo_id = agente_id or _novo_id()
        if not _ID.fullmatch(novo_id) or any(a.get("id") == novo_id for a in estado["agora"]):
            raise Recusa(f"id inválido ou já em uso: {novo_id}")
        agente = {"id": novo_id, "parte": _curto(parte, 40), "titulo": _curto(titulo, 200),
                  "desde": _agora_iso(), "situacao": "trabalhando",
                  "relato": _curto(relato), "relato_em": _agora_iso() if relato else None}
        estado["agora"].append(agente)
        if item_da_fila is not None:
            estado["fila"] = [f for f in estado["fila"] if f.get("id") != da_fila]
            _numerar(estado["fila"])
        _gravar_estado(estado)
    return agente


def relato(agente_id: str, texto: str) -> dict:
    with _trava():
        estado = ler_estado()
        agente = next((a for a in estado["agora"] if a.get("id") == agente_id), None)
        if agente is None:
            raise Recusa(f"nenhum agente ativo com o id {agente_id}")
        agente["relato"] = _curto(texto)
        agente["relato_em"] = _agora_iso()
        _gravar_estado(estado)
    return agente


SITUACOES_FIM = ("concluido", "falhou", "parado")


def agente_fim(agente_id: str, *, situacao: str = "concluido", commits=(),
               relato_final: str = "") -> dict:
    if situacao not in SITUACOES_FIM:
        raise Recusa(f"situação desconhecida: {situacao} ({', '.join(SITUACOES_FIM)})")
    with _trava():
        estado = ler_estado()
        agente = next((a for a in estado["agora"] if a.get("id") == agente_id), None)
        if agente is None:
            raise Recusa(f"nenhum agente ativo com o id {agente_id}")
        estado["agora"] = [a for a in estado["agora"] if a.get("id") != agente_id]
        fim = dict(agente, fim=_agora_iso(), situacao=situacao,
                   commits=[str(c).strip()[:12] for c in commits if str(c).strip()],
                   relato=_curto(relato_final) if relato_final else agente.get("relato", ""))
        estado["concluidos_hoje"].append(fim)
        _gravar_estado(estado)
    return fim


# -------------------------------------------------------------------- fila
def fila_adicionar(parte: str, item: str, posicao: int | None = None) -> dict:
    if not str(parte or "").strip() or not str(item or "").strip():
        raise Recusa("diga a parte e o item")
    with _trava():
        estado = ler_estado()
        novo = {"id": _novo_id(), "parte": _curto(parte, 40), "item": _curto(item, 200),
                "desde": _agora_iso()}
        fila = estado["fila"]
        if posicao is None or posicao > len(fila):
            fila.append(novo)
        else:
            fila.insert(max(0, int(posicao) - 1), novo)
        _numerar(fila)
        _gravar_estado(estado)
    return novo


def _numerar(fila: list) -> None:
    for n, item in enumerate(fila, 1):
        item["prioridade"] = n


def _mover(fila: list, item_id: str, direcao: str) -> None:
    indice = next((n for n, f in enumerate(fila) if f.get("id") == item_id), None)
    if indice is None:
        raise Recusa(f"a fila não tem o item {item_id}")
    if direcao not in ("subir", "descer", "topo"):
        raise Recusa(f"direção desconhecida: {direcao}")
    item = fila.pop(indice)
    destino = {"subir": max(0, indice - 1), "descer": min(len(fila), indice + 1),
               "topo": 0}[direcao]
    fila.insert(destino, item)
    _numerar(fila)


def fila_mover(item_id: str, direcao: str) -> list:
    with _trava():
        estado = ler_estado()
        _mover(estado["fila"], item_id, direcao)
        _gravar_estado(estado)
    return estado["fila"]


def fila_remover(item_id: str) -> None:
    with _trava():
        estado = ler_estado()
        antes = len(estado["fila"])
        estado["fila"] = [f for f in estado["fila"] if f.get("id") != item_id]
        if len(estado["fila"]) == antes:
            raise Recusa(f"a fila não tem o item {item_id}")
        _numerar(estado["fila"])
        _gravar_estado(estado)


# ------------------------------------------------------------ decisoes e modo
def decisao(titulo: str, escolha: str, porque: str = "", alternativa: str = "",
            parte: str = "geral", em: str = "") -> dict:
    if not str(titulo or "").strip() or not str(escolha or "").strip():
        raise Recusa("a decisão precisa de título e escolha")
    linha = {"id": _novo_id(), "em": em or _agora_iso(), "titulo": _curto(titulo, 200),
             "escolha": _curto(escolha, 500), "porque": _curto(porque, 800),
             "alternativa": _curto(alternativa, 500), "parte": _curto(parte, 40) or "geral"}
    with _trava():
        _anexar(arquivo("decisoes_orquestrador.jsonl"), linha)
        estado = ler_estado()
        _gravar_estado(estado)                   # vale como pulso
    return linha


def ler_decisoes() -> tuple[list[dict], int]:
    return _ler_jsonl(arquivo("decisoes_orquestrador.jsonl"))


def mudar_modo(modo: str, origem: str = "orquestrador", comando_id: str = "") -> None:
    if modo not in MODOS:
        raise Recusa(f"modo desconhecido: {modo} ({', '.join(MODOS)})")
    with _trava():
        _mudar_config("modo", modo, origem, comando_id)
        estado = ler_estado()
        estado["modo"] = modo
        _gravar_estado(estado)


def pulso() -> str:
    """So diz "estou aqui": atualiza `atualizado_em`."""
    with _trava():
        estado = ler_estado()
        _gravar_estado(estado)
    return estado["atualizado_em"]


# ================================================================ comandos
# comando -> (precisa de valor?, rotulo para a tela)
COMANDOS = {
    "max_paralelo": "agentes em paralelo",
    "modo": "modo",
    "teto_uso": "teto de uso da sessão",
    "forca_total": "força total antes de renovar",
    "pausar_fila": "pausar a fila",
    "retomar_fila": "retomar a fila",
    "parar_agente": "parar agente",
    "priorizar": "mudar a ordem da fila",
    "mensagem": "mensagem",
    "contestar": "contestou uma decisão",
}
# o que o app pode mandar pela rota de comando (o contestar tem rota propria)
DO_APP = tuple(c for c in COMANDOS if c != "contestar")


def validar_comando(comando: str, valor):
    """O valor normalizado, ou Recusa. A regra mora aqui, nao na tela."""
    if comando not in COMANDOS:
        raise Recusa(f"comando desconhecido: {comando}")
    if comando == "max_paralelo":
        if isinstance(valor, bool):
            raise Recusa("max_paralelo é um número de 1 a 8")
        try:
            numero = int(valor)
        except (TypeError, ValueError):
            raise Recusa("max_paralelo é um número de 1 a 8") from None
        if not 1 <= numero <= MAX_PARALELO or str(numero) != str(valor).strip():
            raise Recusa("max_paralelo é um número de 1 a 8")
        return numero
    if comando == "modo":
        if valor not in MODOS:
            raise Recusa(f"modo desconhecido ({', '.join(MODOS)})")
        return valor
    if comando == "teto_uso":
        if isinstance(valor, bool):
            raise Recusa("o teto é um número de 10 a 100")
        try:
            numero = int(valor)
        except (TypeError, ValueError):
            raise Recusa("o teto é um número de 10 a 100") from None
        if not 10 <= numero <= 100:
            raise Recusa("o teto é um número de 10 a 100")
        return numero
    if comando == "forca_total":
        # ligada = 20 min antes de renovar (a regra dele); desligada = None
        if valor is True:
            return PADRAO_CONFIG["forca_total_antes_min"] or 20
        if valor in (False, None):
            return None
        raise Recusa("força total é ligada ou desligada")
    if comando in ("pausar_fila", "retomar_fila"):
        return None
    if comando == "parar_agente":
        if not isinstance(valor, str) or not _ID.fullmatch(valor):
            raise Recusa("diga qual agente parar")
        return valor
    if comando == "priorizar":
        if not isinstance(valor, dict):
            raise Recusa("diga o item e a direção")
        item, direcao = valor.get("item"), valor.get("direcao")
        if not isinstance(item, str) or not _ID.fullmatch(item):
            raise Recusa("item da fila inválido")
        if direcao not in ("subir", "descer", "topo"):
            raise Recusa("a direção é subir, descer ou topo")
        return {"item": item, "direcao": direcao}
    if comando == "mensagem":
        texto = str(valor or "").strip()
        if not texto:
            raise Recusa("a mensagem está vazia")
        if len(texto) > TEXTO_MAX:
            raise Recusa(f"a mensagem passa de {TEXTO_MAX} caracteres")
        return texto
    if comando == "contestar":
        if not isinstance(valor, dict):
            raise Recusa("contestar leva a decisão e o nó")
        return {k: _curto(valor.get(k), 300) for k in ("decisao", "titulo", "no", "comentario")}
    raise Recusa(f"comando desconhecido: {comando}")        # pragma: no cover


def gravar_comando(comando: str, valor=None, aparelho: str = "") -> dict:
    """O app manda. Fica PENDENTE ate o orquestrador dizer `aplicado`."""
    valor = validar_comando(comando, valor)
    agora = time.time()
    with _trava():
        comandos, _ = _ler_jsonl(arquivo("comandos.jsonl"))
        recentes = 0
        for c in comandos[-COMANDOS_NA_JANELA_MAX - 5:]:
            try:
                if agora - datetime.fromisoformat(c["em"]).timestamp() < COMANDOS_JANELA_S:
                    recentes += 1
            except (KeyError, TypeError, ValueError):
                continue
        if recentes >= COMANDOS_NA_JANELA_MAX:
            raise Recusa("comandos demais em 10 minutos; espere o orquestrador")
        linha = {"id": _novo_id(), "em": _agora_iso(), "comando": comando,
                 "valor": valor, "aparelho": str(aparelho or "")[:8]}
        _anexar(arquivo("comandos.jsonl"), linha)
    return linha


def comandos_com_situacao(n: int | None = None) -> tuple[list[dict], int]:
    """Cada comando com `situacao` (pendente/aplicado/recusado) e o motivo."""
    comandos, ruins_c = _ler_jsonl(arquivo("comandos.jsonl"))
    aplicados, ruins_a = _ler_jsonl(arquivo("comandos_aplicados.jsonl"))
    por_id = {}
    for a in aplicados:
        por_id[a.get("id")] = a
    saida = []
    for c in comandos:
        feito = por_id.get(c.get("id"))
        linha = dict(c, rotulo=COMANDOS.get(c.get("comando"), c.get("comando")))
        if feito is None:
            linha["situacao"] = "pendente"
        else:
            linha["situacao"] = ("recusado" if feito.get("resultado") == "recusado"
                                 else "aplicado")
            linha["motivo"] = feito.get("motivo", "")
            linha["nota"] = feito.get("nota", "")
            linha["aplicado_em"] = feito.get("em")
        saida.append(linha)
    if n is not None:
        saida = saida[-n:]
    return saida, ruins_c + ruins_a


def pendentes() -> list[dict]:
    lista, _ = comandos_com_situacao()
    return [c for c in lista if c["situacao"] == "pendente"]


def _efeito(comando: dict) -> str:
    """O que o `aplicado` muda sozinho. Devolve uma nota (ou "")."""
    nome, valor, cid = comando["comando"], comando.get("valor"), comando["id"]
    if nome == "max_paralelo":
        _mudar_config("max_paralelo", int(valor), "app", cid)
    elif nome == "modo":
        _mudar_config("modo", valor, "app", cid)
        estado = ler_estado()
        estado["modo"] = valor
        _gravar_estado(estado)
    elif nome == "teto_uso":
        _mudar_config("teto_sessao_pct", int(valor), "app", cid)
    elif nome == "forca_total":
        _mudar_config("forca_total_antes_min", valor, "app", cid)
    elif nome == "pausar_fila":
        _mudar_config("fila_pausada", True, "app", cid)
    elif nome == "retomar_fila":
        _mudar_config("fila_pausada", False, "app", cid)
    elif nome == "priorizar":
        estado = ler_estado()
        _mover(estado["fila"], valor["item"], valor["direcao"])
        _gravar_estado(estado)
    elif nome == "parar_agente":
        estado = ler_estado()
        agente = next((a for a in estado["agora"] if a.get("id") == valor), None)
        if agente is None:
            raise Recusa(f"nenhum agente ativo com o id {valor}; recuse com o motivo")
        agente["situacao"] = "parando"
        _gravar_estado(estado)
        return "marcado como parando; feche com agente-fim --situacao parado"
    return ""


def aplicado(comando_id: str, *, recusado: str = "", nota: str = "") -> dict:
    """O orquestrador leu e aplicou (ou recusou, com o motivo)."""
    with _trava():
        lista, _ = comandos_com_situacao()
        comando = next((c for c in lista if c.get("id") == comando_id), None)
        if comando is None:
            raise Recusa(f"comando desconhecido: {comando_id}")
        if comando["situacao"] != "pendente":
            raise Recusa(f"o comando {comando_id} já foi {comando['situacao']}")
        if recusado:
            linha = {"id": comando_id, "em": _agora_iso(), "resultado": "recusado",
                     "motivo": _curto(recusado, 500), "nota": _curto(nota, 500)}
        else:
            extra = _efeito(comando)
            linha = {"id": comando_id, "em": _agora_iso(), "resultado": "aplicado",
                     "motivo": "", "nota": _curto(" · ".join(x for x in (nota, extra) if x),
                                                   500)}
        _anexar(arquivo("comandos_aplicados.jsonl"), linha)
        estado = ler_estado()
        _gravar_estado(estado)                   # quem aplica esta vivo
    return linha


# =================================================================== uso
def binario_claude() -> str | None:
    """O claude.exe que vem na extensao do VS Code (a mesma do vigia_uso.py)."""
    if os.environ.get("CLAUDE_BIN"):
        return os.environ["CLAUDE_BIN"]
    achados = sorted(glob.glob(os.path.join(
        os.path.expanduser("~"), ".vscode", "extensions",
        "anthropic.claude-code-*", "resources", "native-binary", "claude.exe")))
    return achados[-1] if achados else None


def ler_rate_limit(saida: str) -> dict | None:
    """O `rate_limit_event` da saida stream-json, ou None."""
    for bruta in (saida or "").splitlines():
        try:
            evento = json.loads(bruta)
        except ValueError:
            continue
        if not isinstance(evento, dict) or evento.get("type") != "rate_limit_event":
            continue
        info = evento.get("rate_limit_info") or {}
        janelas = info.get("unifiedWindows") or {}
        cinco = janelas.get("five_hour") or {}
        sete = janelas.get("seven_day") or {}
        if cinco.get("utilization") is None:
            continue
        try:
            return {"sessao_pct": round(float(cinco["utilization"]) * 100, 1),
                    "sessao_renova_em": cinco.get("resetsAt"),
                    "semana_pct": (round(float(sete["utilization"]) * 100, 1)
                                   if sete.get("utilization") is not None else None),
                    "semana_renova_em": sete.get("resetsAt"),
                    "status": info.get("status"),
                    "gravado_em": time.time()}
        except (TypeError, ValueError):
            continue
    return None


def medir(rodar=subprocess.run) -> tuple[dict | None, str]:
    """(medicao, motivo da falha). A chamada minima do vigia_uso.py."""
    binario = binario_claude()
    if not binario:
        return None, "não achei o claude.exe da extensão"
    try:
        PASTA_SONDA.mkdir(parents=True, exist_ok=True)
        cwd = str(PASTA_SONDA)
    except OSError:
        cwd = None
    try:
        saida = rodar([binario, "-p", "ok", "--model", "haiku", "--output-format",
                       "stream-json", "--verbose", "--max-turns", "1"],
                      cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                      errors="replace", timeout=SONDA_TIMEOUT_S,
                      creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        return None, f"a sonda passou de {SONDA_TIMEOUT_S} s"
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"a sonda falhou: {type(exc).__name__}"
    medicao = ler_rate_limit(getattr(saida, "stdout", "") or "")
    if medicao is None:
        return None, "a resposta não trouxe o rate_limit_event"
    return medicao, ""


def sondar(rodar=subprocess.run) -> dict:
    """Mede e grava. Falha tambem e gravada: a tela nao pode mostrar o velho."""
    medicao, motivo = medir(rodar)
    with _trava():
        anterior = _ler_json(arquivo("uso.json"), {}) or {}
        if not isinstance(anterior, dict):
            anterior = {}
        agora = time.time()
        if medicao is not None:
            novo = {"medicao": medicao, "fonte": "sonda do app",
                    "ultima_tentativa": agora, "ultima_falha": anterior.get("ultima_falha"),
                    "motivo": "", "falhas_seguidas": 0}
            _anexar(arquivo("uso_historico.jsonl"),
                    {"em": _agora_iso(), "sessao_pct": medicao["sessao_pct"],
                     "semana_pct": medicao["semana_pct"]})
        else:
            novo = {"medicao": anterior.get("medicao"), "fonte": anterior.get("fonte"),
                    "ultima_tentativa": agora, "ultima_falha": agora, "motivo": motivo,
                    "falhas_seguidas": int(anterior.get("falhas_seguidas") or 0) + 1}
        _gravar_json(arquivo("uso.json"), novo)
    return novo


def _limite_de_idade_s(config: dict) -> float:
    minutos = int(config.get("sonda_min") or PADRAO_CONFIG["sonda_min"])
    return max(25 * 60, 2 * minutos * 60 + 5 * 60)


def ler_uso(agora: float | None = None) -> dict:
    """O uso como a tela deve mostrar: NUNCA um numero velho como se fosse atual.

    situacao: "ok" (medicao valida), "velha" (a sonda falhou depois dela,
    passou do prazo, ou a janela ja renovou) ou "nunca". So "ok" leva numero.
    """
    agora = time.time() if agora is None else agora
    config = ler_config()
    try:
        registro = _ler_json(arquivo("uso.json"), {}) or {}
    except Recusa:
        registro = {}
    candidatos = []
    if isinstance(registro.get("medicao"), dict):
        candidatos.append((registro["medicao"], registro.get("fonte") or "sonda do app"))
    try:
        extra = json.loads(_uso_extra().read_text(encoding="utf-8"))
        if isinstance(extra, dict) and extra.get("sessao_pct") is not None:
            candidatos.append((extra, "vigia_uso.py"))
    except (OSError, ValueError):
        pass
    saida = {"situacao": "nunca", "medicao": None, "desde": None, "fonte": None,
             "motivo": registro.get("motivo") or "", "teto": config["teto_sessao_pct"],
             "passou_teto": False, "forca_total_antes_min": config["forca_total_antes_min"],
             "janela_forca_total": False, "falhas_seguidas":
                 int(registro.get("falhas_seguidas") or 0)}
    if not candidatos:
        return saida
    try:
        medicao, fonte = max(candidatos, key=lambda c: float(c[0].get("gravado_em") or 0))
        gravado = float(medicao.get("gravado_em") or 0)
    except (TypeError, ValueError):
        return saida
    saida["desde"] = gravado
    saida["fonte"] = fonte
    falha = registro.get("ultima_falha")
    renova = medicao.get("sessao_renova_em")
    velha = False
    if falha and float(falha) > gravado:
        velha = True
    elif agora - gravado > _limite_de_idade_s(config):
        velha = True
        saida["motivo"] = saida["motivo"] or "a medição passou do prazo"
    else:
        try:
            if renova and float(renova) <= agora:
                velha = True
                saida["motivo"] = "a janela renovou depois da medição"
        except (TypeError, ValueError):
            pass
    if velha:
        saida["situacao"] = "velha"
        return saida
    saida["situacao"] = "ok"
    saida["medicao"] = {k: medicao.get(k) for k in ("sessao_pct", "sessao_renova_em",
                                                    "semana_pct", "semana_renova_em",
                                                    "status", "gravado_em")}
    saida["passou_teto"] = float(medicao.get("sessao_pct") or 0) >= config["teto_sessao_pct"]
    antes = config["forca_total_antes_min"]
    try:
        saida["janela_forca_total"] = bool(
            antes and renova and 0 < float(renova) - agora <= antes * 60)
    except (TypeError, ValueError):
        pass
    return saida


def historico_do_dia(agora: float | None = None) -> list[dict]:
    hoje = datetime.fromtimestamp(time.time() if agora is None else agora).date().isoformat()
    linhas, _ = _ler_jsonl(arquivo("uso_historico.jsonl"))
    return [{"em": l.get("em"), "sessao_pct": l.get("sessao_pct"),
             "semana_pct": l.get("semana_pct")}
            for l in linhas if str(l.get("em", ""))[:10] == hoje]


class _Sonda:
    """A sonda de uso no servidor do app, a cada `sonda_min` (0 = desligada)."""

    def __init__(self):
        self._fio: threading.Thread | None = None
        self._parar = threading.Event()

    def iniciar(self) -> None:
        if self._fio and self._fio.is_alive():
            return
        self._parar.clear()
        self._fio = threading.Thread(target=self._laco, name="sonda-de-uso", daemon=True)
        self._fio.start()

    def parar(self) -> None:
        self._parar.set()

    def _laco(self) -> None:
        while not self._parar.is_set():
            try:
                minutos = int(ler_config().get("sonda_min") or 0)
            except (Recusa, TypeError, ValueError):
                minutos = PADRAO_CONFIG["sonda_min"]
            if minutos > 0:
                try:
                    sondar()
                except Exception as exc:                     # noqa: BLE001
                    sys.stderr.write(f"sonda de uso: {type(exc).__name__}: {exc}\n")
            self._parar.wait(max(1, minutos) * 60)


SONDA = _Sonda()


# ================================================================ acessos
def _frente(texto: str) -> dict:
    """O cabecalho `---` de um .md de agente: name, description."""
    if not texto.startswith("---"):
        return {}
    corpo = texto[3:].split("\n---", 1)[0]
    saida = {}
    for linha in corpo.splitlines():
        chave, sep, valor = linha.partition(":")
        if sep and chave.strip() in ("name", "description", "tools", "model"):
            saida[chave.strip()] = valor.strip()
    return saida


def _agentes() -> list[dict]:
    base = Path(AGENTES) if AGENTES else RAIZ / ".claude" / "agents"
    saida = []
    for md in sorted(base.glob("*.md")):
        try:
            frente = _frente(md.read_text(encoding="utf-8"))
        except OSError:
            continue
        saida.append({"nome": frente.get("name") or md.stem,
                      "descricao": _curto(frente.get("description"), 400),
                      "ferramentas": frente.get("tools", "")})
    return saida


def _contas() -> list[dict]:
    """Por servico: a conta de cada canal e PARA ONDE ela publica. Sem caminho,
    sem token, sem credencial."""
    try:
        from builds import contas
    except Exception as exc:                                 # noqa: BLE001
        return [{"erro": f"não consegui ler as contas: {type(exc).__name__}"}]
    saida = []
    for servico, dados in contas.SERVICOS.items():
        canais = []
        for canal in ("builds", "historias", "zombie"):
            try:
                nome = contas.ativa(servico, canal)
                quem = contas.identidade(servico, nome)
                canais.append({"canal": canal, "conta": nome,
                               "destino": quem.get("rotulo") or "",
                               "propria": contas.explicita(servico, canal)})
            except Exception:                                # noqa: BLE001
                canais.append({"canal": canal, "conta": "?", "destino": "",
                               "propria": False})
        saida.append({"servico": servico, "rotulo": dados.get("rotulo", servico),
                      "publica": bool(dados.get("publica")), "canais": canais})
    return saida


def _flags_do_lancador() -> dict:
    alvo = Path(LANCADOR) if LANCADOR else RAIZ / "app_celular.cmd"
    try:
        texto = alvo.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"acoes": False, "publicar": False, "perigosas": False}
    linhas = [l for l in texto.splitlines() if "remoto.api_http" in l
              and not l.strip().lower().startswith("rem")]
    linha = linhas[-1] if linhas else ""
    return {f: f"--{f}" in linha for f in ("acoes", "publicar", "perigosas")}


def _o_que_o_app_dispara(flags: dict) -> dict:
    if not flags.get("acoes"):
        return {"ligadas": False, "acoes": [], "publicar": False, "perigosas": False}
    from . import acoes, comandos_app
    antigas = [{"nome": n, "rotulo": n, "grupo": "controle"}
               for n in ("pausar", "retomar", "parar", "gerar")]
    if flags.get("publicar"):
        antigas.append({"nome": "publicar", "rotulo": "publicar (builds, público)",
                        "grupo": "publicacao"})
    catalogo = comandos_app.catalogo(bool(flags.get("perigosas")))
    grupos = {g["nome"]: g["rotulo"] for g in catalogo["grupos"]}
    fichas = [{"nome": f["nome"], "rotulo": f["rotulo"],
               "grupo": grupos.get(f["grupo"], f["grupo"])} for f in catalogo["acoes"]]
    destino = {"youtube": "YouTube", "tiktok": "TikTok",
               "ambos": "YouTube e TikTok"}.get(acoes.DESTINO_PADRAO, acoes.DESTINO_PADRAO)
    return {"ligadas": True, "publicar": bool(flags.get("publicar")),
            "perigosas": bool(flags.get("perigosas")),
            "destino_padrao": destino,
            "quem_publica": "só o app (o /publicar do bot não publica)",
            "limite_por_hora": acoes.LIMITE_POR_HORA,
            "acoes": antigas + fichas}


def _claude_settings() -> dict:
    alvo = Path(CLAUDE_SETTINGS) if CLAUDE_SETTINGS else Path.home() / ".claude" / "settings.json"
    try:
        dados = json.loads(alvo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def gerar_acessos(flags: dict | None = None, *, conectores=None,
                  modo_permissao: str | None = None) -> dict:
    """Monta e grava o acessos.json. Nenhum segredo: so nomes e destinos.

    Conectores e modo de permissao so o orquestrador conhece; quando ele nao
    os diz, ficam os que ja estavam gravados.
    """
    try:
        anterior = _ler_json(arquivo("acessos.json"), {}) or {}
    except Recusa:
        anterior = {}
    flags = flags if flags is not None else _flags_do_lancador()
    settings = _claude_settings()
    permissoes = settings.get("permissions") if isinstance(settings.get("permissions"),
                                                          dict) else {}
    if modo_permissao is None:
        modo_permissao = (anterior.get("modo_permissao")
                          or permissoes.get("defaultMode") or "não declarado")
    if conectores is None:
        conectores = anterior.get("conectores") or CONECTORES_28_09
    remoto = settings.get("remoteControlAtStartup")
    try:
        disparos = _o_que_o_app_dispara(flags)
    except Exception as exc:                                 # noqa: BLE001
        disparos = {"erro": f"{type(exc).__name__}"}
    dados = {"gerado_em": _agora_iso(),
             "agentes": _agentes(),
             "conectores": [_curto(c, 80) for c in conectores],
             "recursos": [{"nome": "Remote Control (/rc)",
                           "situacao": ("ligado na inicialização" if remoto
                                        else "desligado na inicialização")}],
             "modo_permissao": _curto(modo_permissao, 80),
             "contas": _contas(),
             "app": disparos,
             "servidor": {"flags": flags, "rede": "só o tailnet (tailscale serve; "
                                                   "funnel nunca)"}}
    with _trava():
        _gravar_json(arquivo("acessos.json"), dados)
    return dados


# ============================================================== para o app
def _idade_s(iso, agora: float) -> float | None:
    try:
        return agora - datetime.fromisoformat(str(iso)).timestamp()
    except (TypeError, ValueError):
        return None


def _ids_do_grimorio() -> set:
    try:
        from . import decisoes
        return set(decisoes.carregar())
    except Exception:                                        # noqa: BLE001
        return set()


def id_do_no(decisao_id: str) -> str:
    return f"contestada-{decisao_id}"


def para_o_app(agora: float | None = None) -> dict:
    """Tudo o que a Mesa de comando mostra, numa chamada. So leitura."""
    agora = time.time() if agora is None else agora
    erros = []

    def tentar(nome, funcao, padrao):
        try:
            return funcao()
        except Recusa as exc:
            erros.append(str(exc))
            return padrao

    config = tentar("config", ler_config, dict(PADRAO_CONFIG))
    estado = tentar("estado", ler_estado, None)
    existe = arquivo("estado.json").is_file()
    idade = _idade_s(estado.get("atualizado_em"), agora) if estado else None
    decisoes_lista, ruins_d = tentar("decisoes", ler_decisoes, ([], 0))
    comandos, ruins_c = tentar("comandos", lambda: comandos_com_situacao(40), ([], 0))
    grimorio = _ids_do_grimorio()
    for d in decisoes_lista:
        d["contestada"] = id_do_no(d.get("id", "")) in grimorio
    uso = tentar("uso", lambda: ler_uso(agora), {"situacao": "nunca", "medicao": None})
    try:
        historico = historico_do_dia(agora)
    except Recusa as exc:
        erros.append(str(exc))
        historico = []
    try:
        acessos = _ler_json(arquivo("acessos.json"), None)
    except Recusa as exc:
        erros.append(str(exc))
        acessos = None
    if ruins_d or ruins_c:
        erros.append(f"{ruins_d + ruins_c} linha(s) ilegível(is) nos registros")
    return {
        "agora": datetime.fromtimestamp(agora).isoformat(timespec="seconds"),
        "estado": estado or _estado_vazio_sem_disco(),
        "estado_existe": existe,
        "fora_do_ar": (not existe) or idade is None or idade > FORA_DO_AR_S,
        "idade_s": idade,
        "config": config,
        "paralelo_efetivo": paralelo_efetivo(config),
        "modos": [{"id": m, "rotulo": ROTULO_MODO[m]} for m in MODOS],
        "uso": uso,
        "historico_uso": historico,
        "decisoes": list(reversed(decisoes_lista))[:40],
        "comandos": list(reversed(comandos)),
        "pendentes": sum(1 for c in comandos if c.get("situacao") == "pendente"),
        "acessos": acessos,
        "erros": erros,
    }


def _estado_vazio_sem_disco() -> dict:
    return {"atualizado_em": None, "modo": PADRAO_CONFIG["modo"], "agora": [],
            "fila": [], "concluidos_hoje": []}


# ============================================================== contestar
def contestar(decisao_id: str, comentario: str = "", aparelho: str = "") -> dict:
    """Vira um no no Grimorio (a mesma funcao do `remoto.decisoes adicionar
    --commit`) e um comando `contestar` para o orquestrador ver. A resposta
    do Adrian ao no vale sobre a decisao do orquestrador."""
    from . import decisoes
    lista, _ = ler_decisoes()
    alvo = next((d for d in lista if d.get("id") == decisao_id), None)
    if alvo is None:
        raise Recusa("decisão do orquestrador desconhecida")
    comentario = _curto(comentario, 1500)
    projeto = alvo.get("parte") if alvo.get("parte") in decisoes.PROJETOS else "geral"
    opcoes = ["manter=Manter o que o orquestrador escolheu"]
    if alvo.get("alternativa"):
        opcoes.append(f"alternativa=Trocar pela alternativa|{alvo['alternativa']}")
    opcoes.append("outro=Outro caminho (comente)")
    pergunta = (f"O orquestrador decidiu sozinho em {str(alvo.get('em', ''))[:10]}: "
                f"{alvo.get('escolha')}.")
    if alvo.get("porque"):
        pergunta += f" Porque: {alvo['porque']}."
    contexto = f"Você contestou pelo app: “{comentario}”" if comentario else \
        "Você contestou pelo app."
    try:
        item, desfecho = decisoes.adicionar_e_commitar(
            projeto, f"Contestada: {alvo.get('titulo')}"[:120], pergunta, opcoes,
            id=id_do_no(decisao_id), contexto=contexto)
    except decisoes.Recusa as exc:
        raise Recusa(str(exc)) from exc
    gravar_comando("contestar", {"decisao": decisao_id, "titulo": alvo.get("titulo"),
                                 "no": item["id"], "comentario": comentario}, aparelho)
    return {"no": item["id"], "projeto": item["projeto"], "commit": desfecho}


# ==================================================================== cli
def _imprimir_estado(estado: dict) -> None:
    print(f"atualizado em {estado.get('atualizado_em') or 'nunca'} · modo {estado.get('modo')}")
    print("AGORA")
    for a in estado["agora"]:
        print(f"  {a['id']}  [{a['parte']}] {a['titulo']}  desde {a['desde'][11:16]}"
              f"  {a.get('situacao')}  — {a.get('relato') or ''}")
    if not estado["agora"]:
        print("  ninguém trabalhando")
    print("FILA")
    for f in estado["fila"]:
        print(f"  {f.get('prioridade')}. {f['id']}  [{f['parte']}] {f['item']}")
    if not estado["fila"]:
        print("  vazia")
    print("CONCLUÍDOS HOJE")
    for c in estado["concluidos_hoje"]:
        print(f"  {c['id']}  [{c['parte']}] {c['titulo']}  {c.get('situacao')}"
              f"  {' '.join(c.get('commits') or [])}")


def _imprimir_pendentes(lista: list, como_json: bool) -> None:
    if como_json:
        print(json.dumps(lista, ensure_ascii=False, indent=2))
        return
    for c in lista:
        print(f"{c['id']}  {c['em']}  {c['comando']}  "
              f"{json.dumps(c.get('valor'), ensure_ascii=False)}")
    if not lista:
        print("nenhum comando pendente")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m remoto.orquestrador",
                                description="o estado do orquestrador e os comandos do app")
    sub = p.add_subparsers(dest="cmd", required=True)
    ini = sub.add_parser("agente-inicio")
    ini.add_argument("--parte", default="")
    ini.add_argument("--titulo", default="")
    ini.add_argument("--da-fila", default="")
    ini.add_argument("--relato", default="")
    ini.add_argument("--id", default="")
    ini.add_argument("--forcar", action="store_true",
                     help="passa por cima da capacidade (só se o Adrian mandou)")
    rel = sub.add_parser("relato")
    rel.add_argument("id")
    rel.add_argument("texto")
    fim = sub.add_parser("agente-fim")
    fim.add_argument("id")
    fim.add_argument("--situacao", default="concluido", choices=SITUACOES_FIM)
    fim.add_argument("--commit", action="append", default=[])
    fim.add_argument("--relato", default="")
    fila = sub.add_parser("fila")
    fsub = fila.add_subparsers(dest="acao", required=True)
    fad = fsub.add_parser("adicionar")
    fad.add_argument("--parte", required=True)
    fad.add_argument("--item", required=True)
    fad.add_argument("--posicao", type=int, default=None)
    fmo = fsub.add_parser("mover")
    fmo.add_argument("id")
    fmo.add_argument("direcao", choices=("subir", "descer", "topo"))
    frm = fsub.add_parser("remover")
    frm.add_argument("id")
    fsub.add_parser("listar")
    dec = sub.add_parser("decisao")
    dec.add_argument("--titulo", required=True)
    dec.add_argument("--escolha", required=True)
    dec.add_argument("--porque", default="")
    dec.add_argument("--alternativa", default="")
    dec.add_argument("--parte", default="geral")
    dec.add_argument("--em", default="")
    mod = sub.add_parser("modo")
    mod.add_argument("modo", choices=MODOS)
    pen = sub.add_parser("pendentes")
    pen.add_argument("--json", action="store_true")
    apl = sub.add_parser("aplicado")
    apl.add_argument("id")
    apl.add_argument("--recusado", default="", metavar="MOTIVO")
    apl.add_argument("--nota", default="")
    esp = sub.add_parser("esperar", help="bloqueia até chegar comando do app")
    esp.add_argument("--intervalo", type=float, default=5.0)
    esp.add_argument("--json", action="store_true")
    acs = sub.add_parser("acessos", help="gera o acessos.json")
    acs.add_argument("--conector", action="append", default=None)
    acs.add_argument("--modo-permissao", default=None)
    for nome in ("config", "estado", "uso", "pulso", "onde", "sonda"):
        sub.add_parser(nome)
    args = p.parse_args(argv)

    try:
        if args.cmd == "agente-inicio":
            agente = agente_inicio(args.parte, args.titulo, da_fila=args.da_fila,
                                   relato=args.relato, forcar=args.forcar,
                                   agente_id=args.id)
            print(agente["id"])
        elif args.cmd == "relato":
            relato(args.id, args.texto)
            print("ok")
        elif args.cmd == "agente-fim":
            feito = agente_fim(args.id, situacao=args.situacao, commits=args.commit,
                               relato_final=args.relato)
            print(f"{feito['id']} {feito['situacao']}")
        elif args.cmd == "fila":
            if args.acao == "adicionar":
                print(fila_adicionar(args.parte, args.item, args.posicao)["id"])
            elif args.acao == "mover":
                fila_mover(args.id, args.direcao)
                print("ok")
            elif args.acao == "remover":
                fila_remover(args.id)
                print("ok")
            else:
                for f in ler_estado()["fila"]:
                    print(f"{f.get('prioridade')}. {f['id']}  [{f['parte']}] {f['item']}")
        elif args.cmd == "decisao":
            print(decisao(args.titulo, args.escolha, args.porque, args.alternativa,
                          args.parte, args.em)["id"])
        elif args.cmd == "modo":
            mudar_modo(args.modo)
            print(f"modo {args.modo}")
        elif args.cmd == "pendentes":
            _imprimir_pendentes(pendentes(), args.json)
        elif args.cmd == "aplicado":
            linha = aplicado(args.id, recusado=args.recusado, nota=args.nota)
            print(f"{linha['id']} {linha['resultado']}"
                  + (f" — {linha['nota']}" if linha.get("nota") else ""))
        elif args.cmd == "esperar":
            ultimo_pulso = 0.0
            while True:
                lista = pendentes()
                if lista:
                    _imprimir_pendentes(lista, args.json)
                    break
                # quem espera esta ouvindo: vale como pulso (a cada 5 min)
                if time.time() - ultimo_pulso > 300:
                    pulso()
                    ultimo_pulso = time.time()
                time.sleep(max(1.0, args.intervalo))
        elif args.cmd == "acessos":
            dados = gerar_acessos(conectores=args.conector,
                                  modo_permissao=args.modo_permissao)
            print(f"acessos.json: {len(dados['agentes'])} agentes, "
                  f"{len(dados['conectores'])} conectores, {len(dados['contas'])} serviços")
        elif args.cmd == "config":
            config = ler_config()
            print(json.dumps(dict(config, paralelo_efetivo=paralelo_efetivo(config)),
                             ensure_ascii=False, indent=2))
        elif args.cmd == "estado":
            _imprimir_estado(ler_estado())
        elif args.cmd == "uso":
            print(json.dumps(ler_uso(), ensure_ascii=False, indent=2))
        elif args.cmd == "sonda":
            registro = sondar()
            print(json.dumps(registro, ensure_ascii=False, indent=2))
            return 0 if not registro.get("motivo") else 2
        elif args.cmd == "pulso":
            print(pulso())
        else:
            print(f"pasta: {pasta()}")
            for nome in ("estado.json", "config.json", "comandos.jsonl",
                         "comandos_aplicados.jsonl", "decisoes_orquestrador.jsonl",
                         "uso.json", "uso_historico.jsonl", "acessos.json",
                         "config_historico.jsonl"):
                print(f"  {nome:<30} {'existe' if arquivo(nome).is_file() else '—'}")
        return 0
    except Recusa as exc:
        print(str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
