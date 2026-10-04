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
    vigia.json                   `esperar`     o pulso de quem ouve os comandos (30 s) e a saida
    acessos.json                 gerado        agentes, conectores, contas (sem segredo), o que o app dispara

A CONFIG SO MUDA NO `aplicado`. O app grava o comando; o `config.json` muda
no `aplicado`. Assim a tela diz a verdade: "pendente" enquanto ninguem leu,
"aplicado" quando vale, "recusado" com o motivo.

DESDE 04/10/2026 QUEM APLICA E O SERVIDOR. A hierarquia e servidor (o
coordenador, 24 h) -> app -> trabalhadores. O pulso do coordenador chama
`aplicar_pelo_servidor` para cada comando pendente (a mensagem vira pedido,
a capacidade vale tambem no despachante, o parar vai ao despachante); a
sessao do VS Code deixou de ser necessaria e e so mais um trabalhador
(`situacao_do_vscode`, sem alarme). O topo de Agora mostra
`situacao_do_servidor`: pulso, pedidos, trabalhadores, comandos e alarmes.

CLI (a do orquestrador):

    python -m remoto.orquestrador agente-inicio --parte P --titulo T [--da-fila ID] [--relato R] [--forcar]
    python -m remoto.orquestrador relato <id> "o que aconteceu"
    python -m remoto.orquestrador agente-fim <id> [--situacao concluido|falhou|parado] [--commit H]... [--relato R]
    python -m remoto.orquestrador fila adicionar --parte P --item T [--posicao N]
    python -m remoto.orquestrador fila mover <id> subir|descer|topo
    python -m remoto.orquestrador fila ordenar <id> <id> ...   # a ordem final inteira
    python -m remoto.orquestrador fila remover <id>
    python -m remoto.orquestrador fila listar
    python -m remoto.orquestrador decisao --titulo T --escolha E [--porque P] [--alternativa A] [--parte P]
    python -m remoto.orquestrador modo um_por_vez|paralelo|forca_total   # operacional: NAO vira regra
    python -m remoto.orquestrador capacidade [--max-paralelo N] [--modo M] [--teto P]
        [--forca-total on|off] [--fonte chat|app] [--porque "palavras dele"]  # vira regra (Grimorio)
    python -m remoto.orquestrador eu "no que a sessao principal esta agora"
    python -m remoto.orquestrador pendentes [--json]
    python -m remoto.orquestrador aplicado <id> [--recusado MOTIVO] [--nota TEXTO]
    python -m remoto.orquestrador esperar [--intervalo S]     # sai quando chega comando
                                                  # ou resposta nova do Adrian (decisao_nova);
                                                  # pulsa o vigia.json a cada 30 s
    python -m remoto.orquestrador vigia                       # o `esperar` do VS Code (codigo 1 = fechado)
    python -m remoto.orquestrador servidor                    # o servidor: pulso, pedidos, alarmes
    python -m remoto.orquestrador config | estado | uso | pulso | onde | modelos
    python -m remoto.orquestrador sonda                        # mede o uso uma vez
    python -m remoto.orquestrador acessos [--conector NOME]... [--modo-permissao M]
    python -m remoto.orquestrador claude [status|liberar|proibir] [--motivo M]
                                  # o interruptor do Claude (claude_estado.py): proibido,
                                  # agente-inicio recusa (nem --forcar), a sonda para e o
                                  # `esperar` segura os comandos ate liberar
"""
from __future__ import annotations

import argparse
import contextlib
import glob
import hashlib
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

from . import claude_estado
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
# O padrao de fabrica; sem `config.json`, vale o que o Grimorio diz
# (`padrao_do_grimorio`: modo-de-trabalho, teto-de-uso, forca-total-ainda-vale).
PADRAO_CONFIG = {"max_paralelo": 1, "modo": "um_por_vez", "teto_sessao_pct": 50,
                 "forca_total_antes_min": 20, "fila_pausada": False,
                 "sonda_min": 10,
                 # os modelos (01/10/2026): None = o padrao de cada um
                 "modelo_agentes": None, "modelo_claude": None, "modelo_codex": None}
# As chaves que o Grimorio diz (capacidade). So a falta DELAS faz o
# `ler_config` reler as decisoes: uma chave nova qualquer (os modelos) nao
# pode transformar cada leitura numa leitura do Grimorio inteiro.
CHAVES_DO_GRIMORIO = ("max_paralelo", "modo", "teto_sessao_pct", "forca_total_antes_min")
MAX_PARALELO = 8
FORA_DO_AR_S = 15 * 60
TEXTO_MAX = 1000
COMANDOS_JANELA_S = 10 * 60
COMANDOS_NA_JANELA_MAX = 40
FILA_MAX = 200                 # uma ordem maior que isso nao e uma fila
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


_PELO_SERVIDOR = threading.local()


@contextlib.contextmanager
def _pelo_servidor():
    """Enquanto o servidor aplica um comando, o que ele grava no estado NAO
    renova `atualizado_em`: esse campo e o sinal da sessao do VS Code (a CLI
    dela), e o servidor aplicando faria um VS Code fechado parecer aberto."""
    antes = getattr(_PELO_SERVIDOR, "ativo", False)
    _PELO_SERVIDOR.ativo = True
    try:
        yield
    finally:
        _PELO_SERVIDOR.ativo = antes


def _gravar_estado(estado: dict) -> None:
    if not getattr(_PELO_SERVIDOR, "ativo", False):
        estado["atualizado_em"] = _agora_iso()
    _arquivar_concluidos(estado)
    _gravar_json(arquivo("estado.json"), estado)


def _arquivar_concluidos(estado: dict) -> None:
    """Todo concluido vai para `tarefas_historico.jsonl`, uma vez.

    O `concluidos_hoje` se esvazia a cada dia. Sem o arquivo, a tarefa que uma
    decisao gerou (Grimorio, "o que isto gerou") viraria "desconhecida" no dia
    seguinte ao fim dela.
    """
    concluidos = [c for c in estado.get("concluidos_hoje") or [] if c.get("id")]
    if not concluidos:
        return
    caminho = arquivo("tarefas_historico.jsonl")
    ja, _ = _ler_jsonl(caminho)
    vistos = {(t.get("id"), t.get("fim")) for t in ja}
    for c in concluidos:
        if (c["id"], c.get("fim")) not in vistos:
            _anexar(caminho, c)
            vistos.add((c["id"], c.get("fim")))


SITUACAO_DA_TAREFA = {"trabalhando": "andamento", "parando": "parando",
                      "concluido": "concluida", "falhou": "falhou", "parado": "parada"}


def situacao_das_tarefas() -> dict:
    """{id: {situacao, titulo, parte, commits, desde, fim}} de toda tarefa que a
    Mesa conhece: o historico, os concluidos, a fila e o agora (o mais novo
    vale). Um item da fila que virou agente responde pelos dois ids.
    Arquivo ilegivel = Recusa (nunca "nenhuma tarefa")."""
    historico, _ = _ler_jsonl(arquivo("tarefas_historico.jsonl"))
    estado = _ler_json(arquivo("estado.json"), None) or {}
    if not isinstance(estado, dict):
        raise Recusa("estado.json está ilegível")
    saida: dict = {}

    def por(registro: dict, situacao: str) -> None:
        ficha = {"situacao": situacao, "titulo": registro.get("titulo")
                 or registro.get("item") or "", "parte": registro.get("parte", ""),
                 "commits": list(registro.get("commits") or []),
                 "desde": registro.get("desde"), "fim": registro.get("fim")}
        for chave in (registro.get("id"), registro.get("da_fila")):
            if chave:
                saida[chave] = ficha

    for registro in historico + list(estado.get("concluidos_hoje") or []):
        por(registro, SITUACAO_DA_TAREFA.get(registro.get("situacao"), "concluida"))
    for registro in estado.get("fila") or []:
        por(registro, "fila")
    for registro in estado.get("agora") or []:
        por(registro, SITUACAO_DA_TAREFA.get(registro.get("situacao"), "andamento"))
    return saida


def padrao_do_grimorio() -> dict:
    """O padrao da config lido das decisoes VIGENTES do Grimorio.

    Sem isto, uma Mesa sem `config.json` (maquina nova, pasta apagada) nascia
    "um por vez" com o Grimorio dizendo "paralelo" desde 28/09 20:29. O que
    nao der para ler fica no PADRAO_CONFIG.
    """
    padrao = dict(PADRAO_CONFIG)
    try:
        from . import decisoes
        itens = decisoes.carregar()
    except Exception:                                        # noqa: BLE001
        return padrao

    def vigente(no):
        item = itens.get(no) or {}
        if item.get("situacao") != "decidida":
            return None, ""
        v = item.get("vigente") or {}
        return v.get("opcao"), str(v.get("comentario") or "")

    opcao, comentario = vigente("modo-de-trabalho")
    if opcao == "paralelo":
        numero = re.search(r"até (\d+) agentes|max_paralelo (\d+)", comentario)
        n = int(next(g for g in numero.groups() if g)) if numero else 2
        padrao["modo"], padrao["max_paralelo"] = "paralelo", max(2, min(MAX_PARALELO, n))
    opcao, comentario = vigente("teto-de-uso")
    numero = re.search(r"(\d+)\s*%", comentario)
    if opcao == "outro" and numero and 10 <= int(numero.group(1)) <= 100:
        padrao["teto_sessao_pct"] = int(numero.group(1))
    opcao, _ = vigente("forca-total-ainda-vale")
    if opcao == "so-quando-eu-pedir":
        padrao["forca_total_antes_min"] = None
    return padrao


def ler_config() -> dict:
    dados = _ler_json(arquivo("config.json"), {})
    if not isinstance(dados, dict):
        raise Recusa("config.json está ilegível")
    faltam = [k for k in CHAVES_DO_GRIMORIO if k not in dados]
    padrao = padrao_do_grimorio() if faltam else PADRAO_CONFIG
    return {**padrao, **{k: v for k, v in dados.items() if k in PADRAO_CONFIG}}


def paralelo_efetivo(config: dict) -> int:
    """Quantos agentes de uma vez, de fato. Um por vez e um, qualquer que seja o max."""
    if config["modo"] == "um_por_vez":
        return 1
    return int(config["max_paralelo"])


def _mudar_config(chave: str, valor, origem: str, comando_id: str = "") -> bool:
    """Grava a config e o historico. Devolve se mudou de fato."""
    config = ler_config()
    antes = config.get(chave)
    if antes == valor:
        return False
    config[chave] = valor
    _gravar_json(arquivo("config.json"), config)
    _anexar(arquivo("config_historico.jsonl"),
            {"em": _agora_iso(), "chave": chave, "de": antes, "para": valor,
             "origem": origem, "comando": comando_id})
    return True


def _curto(texto, limite: int = 300) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


# -------------------------------------------------------- a sessao principal
# "No que voce esta trabalhando agora" nao e so os agentes: e a sessao
# principal (o orquestrador). `eu "..."` e o relato dela, em uma linha; cada
# movimento da CLI (disparar, fechar, aplicar, mudar a capacidade) entra
# sozinho na linha do tempo, para a tela nunca ficar muda.
LINHA_DO_TEMPO_MAX = 15


def _principal(estado: dict) -> dict:
    atual = estado.get("principal")
    if not isinstance(atual, dict):
        atual = {}
    if not isinstance(atual.get("linha"), list):
        atual["linha"] = []
    estado["principal"] = atual
    return atual


def _movimento(estado: dict, texto: str, tipo: str = "acao") -> None:
    """Uma linha na linha do tempo da sessao principal (so em memoria; quem
    chama grava o estado)."""
    principal = _principal(estado)
    em = _agora_iso()
    linha = {"em": em, "texto": _curto(texto, 200), "tipo": tipo}
    principal["linha"] = (principal["linha"] + [linha])[-LINHA_DO_TEMPO_MAX:]
    if tipo == "relato":
        principal["relato"], principal["relato_em"] = linha["texto"], em
    else:
        principal["movimento"], principal["movimento_em"] = linha["texto"], em


def eu(texto: str) -> dict:
    """A sessao principal diz no que esta, em uma linha."""
    texto = _curto(texto, 200)
    if not texto:
        raise Recusa("diga no que a sessão principal está")
    with _trava():
        estado = ler_estado()
        _movimento(estado, texto, "relato")
        _gravar_estado(estado)
    return estado["principal"]


# ----------------------------------------------------------------- agentes
def agente_inicio(parte: str, titulo: str, *, da_fila: str = "", relato: str = "",
                  forcar: bool = False, agente_id: str = "") -> dict:
    """Um agente comecou. Recusa se passa da capacidade (sem `forcar`).

    Com o Claude PROIBIDO pelo Adrian (claude_estado), recusa sempre, mesmo
    com `forcar`: o `--forcar` passa por cima da capacidade, nao da ordem dele.
    """
    proibido = claude_estado.motivo_proibido()
    if proibido:
        raise Recusa(f"{proibido}; nem o --forcar passa (só ele libera, pelo app)")
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
        if item_da_fila is not None:
            # a decisao que gerou o item da fila acha o agente pelo id antigo
            agente["da_fila"] = da_fila
        estado["agora"].append(agente)
        if item_da_fila is not None:
            estado["fila"] = [f for f in estado["fila"] if f.get("id") != da_fila]
            _numerar(estado["fila"])
        _movimento(estado, f"disparou [{agente['parte']}] {agente['titulo']}"
                   + (" (forçado)" if forcar else ""))
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
        _movimento(estado, f"fechou [{fim['parte']}] {fim['titulo']}: {situacao}")
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
        _movimento(estado, f"pôs na fila [{novo['parte']}] {novo['item']}")
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


def fila_versao(fila: list) -> str:
    """A ORDEM da fila num resumo curto. A tela manda de volta como `esperava`
    ao reordenar: diferente da atual = a fila mudou no PC enquanto ele
    arrastava (409), e a tela reabre com a que vale. Vazia tem versao tambem."""
    ids = ",".join(str(f.get("id") or "") for f in fila)
    return hashlib.sha1(ids.encode("utf-8")).hexdigest()[:8]


class FilaMudou(Recusa):
    """A ordem que a tela viu (`esperava`) nao e mais a da fila."""


def _ordenar(fila: list, ordem: list[str]) -> str:
    """Reordena a fila pela lista de ids (a ordem final inteira). Devolve uma
    nota (ou "").

    No `aplicado` ela e TOLERANTE, porque a fila pode ter mudado entre o toque
    e a aplicacao (o orquestrador pos ou tirou um item): id da ordem que ja
    saiu e pulado, e item que entrou depois fica no fim, na ordem em que
    estava. Os dois casos vao para a nota. Quem e estrito e o `gravar_comando`.
    """
    por_id = {f.get("id"): f for f in fila}
    vistos: set[str] = set()
    nova = []
    for item_id in ordem:
        if item_id in por_id and item_id not in vistos:
            nova.append(por_id[item_id])
            vistos.add(item_id)
    sobras = [f for f in fila if f.get("id") not in vistos]
    notas = []
    fora = [i for i in ordem if i not in por_id]
    if fora:
        notas.append(f"{len(fora)} item(ns) da ordem já tinha(m) saído da fila")
    if sobras:
        notas.append(f"{len(sobras)} item(ns) entrou(aram) depois e ficou(aram) no fim")
    if [f.get("id") for f in nova + sobras] == [f.get("id") for f in fila]:
        notas.append("já estava assim")
    fila[:] = nova + sobras
    _numerar(fila)
    return " · ".join(notas)


def fila_ordenar(ordem: list[str]) -> list:
    """A CLI: `fila ordenar <id> <id> ...`, estrita como o app."""
    ordem = validar_comando("priorizar", {"ordem": list(ordem)})["ordem"]
    with _trava():
        estado = ler_estado()
        _conferir_ordem(estado["fila"], ordem, None)
        nota = _ordenar(estado["fila"], ordem)
        if nota != "já estava assim":
            _movimento(estado, "reordenou a fila")
            _gravar_estado(estado)
    return estado["fila"]


def _conferir_ordem(fila: list, ordem: list[str], esperava: str | None) -> None:
    """A regra estrita da entrada: cada id da ordem existe, nenhum da fila
    falta, e a versao que a tela viu e a atual. Chame sob a trava."""
    if esperava is not None and esperava != fila_versao(fila):
        raise FilaMudou("a fila mudou no PC enquanto a tela estava aberta")
    atuais = [f.get("id") for f in fila]
    desconhecidos = [i for i in ordem if i not in atuais]
    if desconhecidos:
        raise Recusa(f"a fila não tem o item {desconhecidos[0]}")
    faltam = [i for i in atuais if i not in ordem]
    if faltam:
        raise Recusa(f"a ordem não diz onde fica o item {faltam[0]}")


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
        _movimento(estado, f"decidiu: {linha['titulo']} → {linha['escolha']}")
        _gravar_estado(estado)                   # vale como pulso
    return linha


def ler_decisoes() -> tuple[list[dict], int]:
    return _ler_jsonl(arquivo("decisoes_orquestrador.jsonl"))


def mudar_modo(modo: str, origem: str = "orquestrador", comando_id: str = "") -> None:
    """O modo que o PROPRIO orquestrador liga (ex.: a janela da forca total).

    E operacional: nao responde o Grimorio. Instrucao do Adrian e
    `capacidade --modo M --fonte chat`, que vira regra.
    """
    if modo not in MODOS:
        raise Recusa(f"modo desconhecido: {modo} ({', '.join(MODOS)})")
    with _trava():
        _mudar_config("modo", modo, origem, comando_id)
        estado = ler_estado()
        estado["modo"] = modo
        _movimento(estado, f"modo operacional: {ROTULO_MODO[modo]}")
        _gravar_estado(estado)


# ======================================================= respostas do Adrian
def _vistas() -> Path:
    return arquivo("decisoes_vistas.json")


def decisoes_novas() -> tuple[list[dict], int]:
    """(respostas novas e ainda nao lidas, ultima linha vista).

    O cursor (`decisoes_vistas.json`, a ultima linha do `_eventos.jsonl` que o
    `esperar` ja mostrou) guarda o lugar entre um `esperar` e outro: resposta
    que chega enquanto ninguem espera acorda o proximo. Sem cursor, ele nasce
    no fim (o passado e do `leitor`, nao do `esperar`). Quem chama avanca o
    cursor com `avancar_vistas` DEPOIS de mostrar.
    """
    from . import decisoes
    try:
        eventos = decisoes.ler_eventos()
    except decisoes.Recusa as exc:
        raise Recusa(f"Grimório: {exc}") from exc
    ultima = max((e["n"] for e in eventos), default=0)
    cursor = _ler_json(_vistas(), None)
    if not isinstance(cursor, dict) or not isinstance(cursor.get("linhas"), int):
        avancar_vistas(ultima)
        return [], ultima
    if cursor["linhas"] > ultima:            # o arquivo encolheu: recomeca do fim
        avancar_vistas(ultima)
        return [], ultima
    if cursor["linhas"] == ultima:
        return [], ultima
    try:
        todas = decisoes.leitor(todos=True)
    except decisoes.Recusa as exc:
        raise Recusa(f"Grimório: {exc}") from exc
    novas = [dict(e, tipo="decisao_nova") for e in todas
             if e["n"] > cursor["linhas"] and not e.get("lida")]
    return novas, ultima


def avancar_vistas(linha: int) -> None:
    _gravar_json(_vistas(), {"linhas": int(linha), "em": _agora_iso()})


def pulso() -> str:
    """So diz "estou aqui": atualiza `atualizado_em`."""
    with _trava():
        estado = ler_estado()
        _gravar_estado(estado)
    return estado["atualizado_em"]


# ================================================================ o vigia
# O `esperar` e o OUVIDO do orquestrador: sem ele, comando do app fica
# pendente. Em 29/09/2026 o "retomar a fila" ficou pendente 2 min 36 s
# (00:58:45 -> 01:01:21) com o vigia desligado desde um checkpoint, e a Mesa
# dizia "no ar", porque QUALQUER comando da CLI renova `estado.atualizado_em`.
# "A sessao deu sinal" e "alguem esta ouvindo" sao coisas diferentes: o
# `esperar` tem pulso proprio, `vigia.json`, reescrito a cada 30 s enquanto ele
# espera, e a SAIDA dele fica registrada (com o motivo). Morto sem aviso
# (processo encerrado a forca), o pulso envelhece e o PID nao existe mais.
VIGIA_PULSO_S = 30
VIGIA_VIVO_S = 90             # tres pulsos perdidos: nao esta ouvindo
VIGIA_ACORDOU_S = 180         # saiu com um comando: esta aplicando, ate 3 min
SITUACOES_DO_VIGIA = ("ouvindo", "acordou", "preso", "fora", "fechada")


def _vigia() -> Path:
    return arquivo("vigia.json")


def _gravar_vigia(dados: dict) -> bool:
    """Grava o pulso. Nunca derruba o `esperar`: um pulso perdido (o servidor
    lendo o arquivo no instante do `os.replace`, no Windows) e so um pulso."""
    alvo = _vigia()
    temporario = alvo.with_name(f".vigia.{os.getpid()}.{threading.get_ident()}.tmp")
    for _ in range(3):
        try:
            alvo.parent.mkdir(parents=True, exist_ok=True)
            temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
            os.replace(temporario, alvo)
            return True
        except OSError:
            time.sleep(0.2)
    try:
        temporario.unlink()
    except OSError:
        pass
    return False


def vigia_pulsar(desde: str, pid: int | None = None, segurando: str = "") -> bool:
    """`segurando`: ouvindo, mas sem acordar ninguem (Claude proibido)."""
    dados = {"situacao": "ouvindo", "pid": int(pid or os.getpid()),
             "desde": desde, "pulso_em": _agora_iso(), "pulso_s": VIGIA_PULSO_S}
    if segurando:
        dados["segurando"] = _curto(segurando, 200)
    return _gravar_vigia(dados)


def vigia_saiu(motivo: str, desde: str, pid: int | None = None) -> bool:
    """O `esperar` saiu: com um comando, com resposta nova, interrompido ou
    com erro. Outro `esperar` vivo (dois de uma vez) nao perde o pulso dele."""
    pid = int(pid or os.getpid())
    try:
        atual = _ler_json(_vigia(), None)
    except Recusa:
        atual = None
    if isinstance(atual, dict) and atual.get("pid") not in (None, pid) \
            and atual.get("situacao") == "ouvindo":
        idade = _idade_s(atual.get("pulso_em"), time.time())
        if idade is not None and idade <= VIGIA_VIVO_S:
            return False
    ultimo = atual.get("pulso_em") if isinstance(atual, dict) and \
        atual.get("pid") == pid else None
    return _gravar_vigia({"situacao": "saiu", "pid": pid, "desde": desde,
                          "pulso_em": ultimo or _agora_iso(), "saiu_em": _agora_iso(),
                          "motivo": _curto(motivo, 200)})


_KERNEL32 = None


def _pid_vivo(pid) -> bool | None:
    """O processo ainda existe? None quando nao da para saber (o pulso decide)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if os.name != "nt":                                     # pragma: no cover
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except OSError:
            return None
        return True
    global _KERNEL32
    try:
        import ctypes
        from ctypes import wintypes
        if _KERNEL32 is None:
            k = ctypes.WinDLL("kernel32", use_last_error=True)
            k.OpenProcess.restype = wintypes.HANDLE
            k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            k.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            k.GetExitCodeProcess.restype = wintypes.BOOL
            k.CloseHandle.argtypes = (wintypes.HANDLE,)
            _KERNEL32 = k
        k = _KERNEL32
        alca = k.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not alca:
            # 87 = ERROR_INVALID_PARAMETER: nenhum processo com esse PID
            return False if ctypes.get_last_error() == 87 else None
        try:
            codigo = wintypes.DWORD()
            if not k.GetExitCodeProcess(alca, ctypes.byref(codigo)):
                return None
            return codigo.value == 259                 # STILL_ACTIVE
        finally:
            k.CloseHandle(alca)
    except Exception:                                        # noqa: BLE001
        return None


def _hhmm(iso) -> str:
    return str(iso or "")[11:16] or "?"


def _ha(segundos) -> str:
    if segundos is None:
        return "?"
    minutos = int(max(0, segundos) // 60)
    if minutos < 1:
        return "menos de 1 min"
    if minutos < 60:
        return f"{minutos} min"
    return f"{minutos // 60} h {minutos % 60:02d} min"


def situacao_do_vigia(agora: float | None = None, estado: dict | None = None) -> dict:
    """A sessao do VS Code: o `esperar` dela esta ouvindo?

    Desde 04/10/2026 quem aplica os comandos e o SERVIDOR (o pulso do
    coordenador, `aplicar_pelo_servidor`): isto so descreve a sessao do VS Code
    como mais um trabalhador, e a tela nao alarma por ela.

    ouvindo  o `esperar` pulsou ha menos de 90 s e o processo existe;
    acordou  ele saiu ha menos de 3 min com um comando ou resposta nova (esta
             aplicando; volta a ouvir em seguida);
    fora     a sessao deu sinal nos ultimos 15 min, mas o vigia esta desligado;
    fechada  nem vigia, nem sinal da sessao ha mais de 15 min.
    O texto vai pronto para a tela e para o Telegram, com a hora do PC.
    """
    agora = time.time() if agora is None else agora
    if estado is None:
        try:
            estado = ler_estado() if arquivo("estado.json").is_file() else None
        except Recusa:
            estado = None
    try:
        vigia = _ler_json(_vigia(), None)
    except Recusa:
        vigia = None
    if not isinstance(vigia, dict):
        vigia = None
    sessao_em = (estado or {}).get("atualizado_em")
    sessao_idade = _idade_s(sessao_em, agora) if sessao_em else None
    saida = {"situacao": "fechada", "texto": "", "pid": None, "desde": None,
             "pulso_em": None, "pulso_idade_s": None, "saiu_em": None, "motivo": "",
             "sem_ouvir_desde": None, "sem_ouvir_s": None, "sessao_em": sessao_em,
             "sessao_idade_s": sessao_idade, "nunca_ligou": vigia is None}
    if vigia:
        saida.update({k: vigia.get(k) for k in ("pid", "desde", "pulso_em", "saiu_em")})
        saida["motivo"] = str(vigia.get("motivo") or "")
        saida["pulso_idade_s"] = _idade_s(vigia.get("pulso_em"), agora)
        idade = saida["pulso_idade_s"]
        if (vigia.get("situacao") == "ouvindo" and idade is not None
                and idade <= VIGIA_VIVO_S and _pid_vivo(vigia.get("pid")) is not False):
            saida["situacao"] = "ouvindo"
            saida["texto"] = (f"A sessão do VS Code está ouvindo (último pulso às "
                              f"{str(vigia.get('pulso_em'))[11:19]}).")
            if vigia.get("segurando"):
                # Claude proibido: o `esperar` esta vivo, mas nao acorda
                saida["segurando"] = str(vigia["segurando"])
                saida["texto"] = (f"A sessão do VS Code está ouvindo, mas segurando: "
                                  f"{vigia['segurando']}. O servidor aplica os comandos.")
            return saida
        saiu_idade = _idade_s(vigia.get("saiu_em"), agora)
        if (vigia.get("situacao") == "saiu" and vigia.get("motivo") in
                ("comando", "decisao_nova") and saiu_idade is not None
                and saiu_idade <= VIGIA_ACORDOU_S):
            saida["situacao"] = "acordou"
            saida["texto"] = (f"A sessão do VS Code acordou às {_hhmm(vigia.get('saiu_em'))} "
                              "com um pedido; volta a ouvir em seguida.")
            return saida
        # desde quando ninguem ouve: a saida registrada, ou o ultimo pulso
        desde = vigia.get("saiu_em") if vigia.get("situacao") == "saiu" \
            else vigia.get("pulso_em")
        saida["sem_ouvir_desde"] = desde
        saida["sem_ouvir_s"] = _idade_s(desde, agora)
    if sessao_idade is not None and sessao_idade <= FORA_DO_AR_S:
        saida["situacao"] = "fora"
        if vigia is None:
            quanto = "o vigia nunca foi ligado"
        else:
            quanto = (f"o vigia está desligado há {_ha(saida['sem_ouvir_s'])} "
                      f"(desde {_hhmm(saida['sem_ouvir_desde'])})")
        saida["texto"] = (f"VS Code aberto (sinal às {_hhmm(sessao_em)}), sem ouvir os "
                          f"comandos: {quanto}. Não faz falta: o servidor aplica.")
        return saida
    agentes = len((estado or {}).get("agora") or [])
    if sessao_em:
        texto = (f"VS Code fechado: sem sinal da sessão desde {_hhmm(sessao_em)} "
                 f"(há {_ha(sessao_idade)}). Não faz falta: o servidor aplica os comandos.")
    else:
        texto = ("VS Code: a sessão nunca deu sinal aqui. Não faz falta: o servidor "
                 "aplica os comandos.")
    if agentes:
        texto += (f" {'O agente que ela registrou pode' if agentes == 1 else f'Os {agentes} agentes que ela registrou podem'}"
                  " não estar rodando.")
    saida["texto"] = texto
    return saida


def esperar(intervalo: float = 5.0, *, como_json: bool = False,
            pulso_s: float = VIGIA_PULSO_S, relogio=time.time, dormir=time.sleep) -> int:
    """Bloqueia ate chegar comando do app ou resposta nova do Adrian.

    Pulsa o `vigia.json` a cada `pulso_s` (e o estado a cada 5 min, que diz
    "a sessao esta aberta"). A saida fica registrada com o motivo, inclusive
    quando e interrompida; morto a forca, o pulso envelhece sozinho.

    CLAUDE PROIBIDO (claude_estado, 29/09/2026): cada saida do `esperar`
    acorda a sessao principal, e acordar e usar o Claude. Enquanto proibido,
    ele NAO sai com comando nem com resposta nova: os comandos ficam
    pendentes na fila e o cursor das decisoes nao anda. So sai quando o
    estado volta a `liberado`, com `{"tipo": "claude_liberado"}` na frente e
    tudo o que ficou guardado junto.

    A PROIBICAO QUE CHEGA NO MEIO (30/09/2026, pedido dele: "quando eu
    proibir e uma ordem para tudo que esta rodando parar em um checkpoint
    seguro"): se o `esperar` comecou liberado e o estado vira proibido, ele
    sai UMA vez com `{"tipo": "claude_proibido"}` para o orquestrador parar os
    agentes. Sem isso a sessao nao sabia da ordem e os agentes seguiam. O
    `esperar` seguinte, ja comecando proibido, segura como sempre.
    """
    desde = _agora_iso()
    pid = os.getpid()
    ultimo_vigia = ultimo_estado = float("-inf")
    motivo = "interrompido"
    segurou = False                 # esteve proibido enquanto esperava
    comecou_liberado = claude_estado.ler()["liberado"]
    try:
        while True:
            agora = relogio()
            estado_claude = claude_estado.ler()
            if agora - ultimo_vigia >= pulso_s:
                if estado_claude["liberado"]:
                    vigia_pulsar(desde, pid)
                else:
                    vigia_pulsar(desde, pid, segurando=estado_claude["texto"])
                ultimo_vigia = agora
            if not estado_claude["liberado"] and comecou_liberado:
                _imprimir_pendentes([{"tipo": "claude_proibido", "em": estado_claude["em"],
                                      "por": estado_claude["por"],
                                      "motivo": estado_claude["motivo"],
                                      "texto": estado_claude["texto"]}], como_json)
                motivo = "claude_proibido"
                return 0
            if not estado_claude["liberado"]:
                segurou = True
            else:
                lista = pendentes()
                novas, ultima = decisoes_novas()
                if segurou:
                    liberado_ = {"tipo": "claude_liberado", "em": estado_claude["em"],
                                 "por": estado_claude["por"],
                                 "motivo": estado_claude["motivo"],
                                 "texto": estado_claude["texto"]}
                    _imprimir_pendentes([liberado_]
                                        + [dict(c, tipo="comando") for c in lista]
                                        + novas, como_json)
                    avancar_vistas(ultima)
                    motivo = "claude_liberado"
                    return 0
                if lista or novas:
                    _imprimir_pendentes([dict(c, tipo="comando") for c in lista] + novas,
                                        como_json)
                    avancar_vistas(ultima)
                    motivo = "comando" if lista else "decisao_nova"
                    return 0
            if agora - ultimo_estado > 300:
                try:
                    pulso()
                except OSError:
                    pass                    # trava ocupada: o proximo pulso vem
                ultimo_estado = agora
            dormir(max(1.0, intervalo))
    except Recusa as exc:
        motivo = f"erro: {exc}"
        raise
    finally:
        vigia_saiu(motivo, desde, pid)


class _AvisoSemOuvinte:
    """No servidor do app: comando pendente ha mais de 2 min (o servidor sem
    pulso, ou preso nele) vira UM aviso no Telegram por ocorrencia, e um
    "aplicou" quando ela fecha (decisao app-e-bot/aviso-no-telegram-...). A
    ocorrencia mora em `aviso_sem_ouvinte.json`: o servidor do app que
    reinicia no meio dela nao avisa de novo."""

    INTERVALO_S = 30

    def __init__(self):
        self._fio: threading.Thread | None = None
        self._parar = threading.Event()

    def iniciar(self) -> None:
        if self._fio and self._fio.is_alive():
            return
        self._parar.clear()
        self._fio = threading.Thread(target=self._laco, name="aviso-sem-ouvinte",
                                     daemon=True)
        self._fio.start()

    def parar(self) -> None:
        self._parar.set()

    def _laco(self) -> None:
        while not self._parar.wait(self.INTERVALO_S):
            try:
                self.verificar()
            except Exception as exc:                         # noqa: BLE001
                sys.stderr.write(f"aviso sem ouvinte: {type(exc).__name__}: {exc}\n")

    @staticmethod
    def verificar(agora: float | None = None, avisar=None, coordenador: dict | None = None) -> str | None:
        """Uma olhada. Devolve o texto avisado (ou None).

        Desde 04/10 quem aplica e o pulso do servidor, com ou sem o Claude
        proibido: comando parado ha 2 min e o servidor sem pulso, ou preso
        nele. A sessao do VS Code nao entra na conta."""
        agora = time.time() if agora is None else agora
        if avisar is None:
            from .acoes import avisar_texto as avisar
        comandos, _ = comandos_com_situacao()
        servidor = situacao_do_servidor(agora, coordenador=coordenador, comandos=comandos,
                                        uso={}, estado={}, vigia={},
                                        pedidos_vivos=[], trabalhadores=([], []))
        aviso = servidor["comando_parado"]
        caminho = arquivo("aviso_sem_ouvinte.json")
        try:
            registro = _ler_json(caminho, {}) or {}
        except Recusa:
            registro = {}
        if not isinstance(registro, dict):
            registro = {}
        aberta = bool(registro.get("aberta"))
        texto = None
        if aviso and not aberta:
            texto = f"⏳ Mesa de comando: {aviso['texto']}"
            registro = {"aberta": True, "comando": aviso["comando"],
                        "desde": aviso["desde"], "avisado_em": _agora_iso()}
        elif not aviso and aberta:
            pendentes_ = [c for c in comandos if c.get("situacao") == "pendente"]
            antigo = next((c for c in comandos if c.get("id") == registro.get("comando")),
                          None)
            if antigo and antigo.get("situacao") != "pendente":
                demora = None
                inicio = _idade_s(registro.get("desde"), agora)
                fim = _idade_s(antigo.get("aplicado_em"), agora)
                if inicio is not None and fim is not None:
                    demora = inicio - fim
                texto = (f"✓ Mesa de comando: o servidor "
                         f"{'recusou' if antigo['situacao'] == 'recusado' else 'aplicou'} "
                         f"«{antigo.get('rotulo')}» às {_hhmm(antigo.get('aplicado_em'))}"
                         + (f" (ficou pendente {_ha(demora)})" if demora is not None else "")
                         + ".")
            elif pendentes_:
                texto = (f"✓ Mesa de comando: o servidor voltou a pulsar às "
                         f"{datetime.fromtimestamp(agora).strftime('%H:%M')}; "
                         "o comando sai em instantes.")
            else:
                texto = "✓ Mesa de comando: não há mais comando esperando."
            registro = {"aberta": False, "comando": registro.get("comando"),
                        "fechada_em": _agora_iso()}
        else:
            return None
        with _trava():
            _gravar_json(caminho, registro)
        avisar(texto)
        return texto


AVISO_SEM_OUVINTE = _AvisoSemOuvinte()


# ================================================================= modelos
# Pedido do Adrian (01/10/2026, tarefa 52dc403c): "suporte para mudar o modelo
# tanto do Claude quanto do Codex e do Gemini". Cada seletor da Mesa vira um
# COMANDO (pendente ate o orquestrador aplicar); vale no `aplicado`:
#   modelo_agentes  config.json  o `model` dos AGENTES que o orquestrador
#                   dispara. O da sessao principal so o Adrian troca (/model).
#   modelo_codex    config.json  o `-m` do `codex exec` (remoto/delegar.py);
#                   None = o do ~/.codex/config.toml
#   modelo_gemini   historias/config/llm.json, bloco "gemini" ->
#                   `modelo_preferido`: a ordem que o ClienteLLM procura no menu
#                   do site (o Gemini e o do NAVEGADOR: decisao gemini-sem-cli)
MODELOS_CLAUDE = (
    ("opus", "Opus", "o mais forte; gasta mais da janela"),
    ("sonnet", "Sonnet", "o equilíbrio entre força e custo"),
    ("haiku", "Haiku", "rápido e barato, para tarefa simples"),
    ("fable", "Fable", ""),
)
# O menu do site medido em 29/09 (ias/fichas/gemini.json) e o que os logs
# mostram o cliente escolhendo ("3.1 Pro Raciocínio avançado", "3.5 Flash Lite
# Respostas mais rápidas"). A lista e uma ORDEM DE QUEDA por texto: o primeiro
# que aparecer no menu ganha (`ClienteLLM._tentar_modelo`).
MODELOS_GEMINI = (
    ("pro", "3.1 Pro — raciocínio avançado", ["pro", "flash"]),
    ("raciocinio", "Raciocínio complexo — solução de problemas",
     ["raciocínio complexo", "raciocinio complexo", "pro"]),
    ("flash", "3.6 Flash — ajuda para tudo", ["3.6 flash", "flash"]),
    ("flash-lite", "3.5 Flash Lite — respostas mais rápidas",
     ["flash lite", "flash-lite", "flash"]),
)
LLM_JSON = None                 # os testes apontam para uma copia


def llm_json() -> Path:
    return Path(LLM_JSON) if LLM_JSON else RAIZ / "historias" / "config" / "llm.json"


def _json_do_llm(dados: dict) -> str:
    """O `llm.json` na forma em que ele e escrito a mao: um nivel aberto, e o
    resto numa linha so (listas e blocos curtos). Mudar o modelo vira um diff
    de UMA linha, nao do arquivo inteiro (ha teste de ida e volta)."""
    def linha(v):
        return json.dumps(v, ensure_ascii=False)
    saida = []
    itens = list(dados.items())
    for i, (k, v) in enumerate(itens):
        fim = "," if i < len(itens) - 1 else ""
        inteiro = linha(v)
        if isinstance(v, dict) and len(inteiro) > 100:
            corpo = ",\n".join(f"        {linha(kk)}: {linha(vv)}" for kk, vv in v.items())
            saida.append(f"    {linha(k)}: {{\n{corpo}\n    }}{fim}")
        else:
            saida.append(f"    {linha(k)}: {inteiro}{fim}")
    return "{\n" + "\n".join(saida) + "\n}\n"


def gemini_vigente() -> dict:
    """{"id": ..., "ordem": [...]} do `llm.json`; id None = o padrao do codigo,
    "outro" = uma ordem escrita a mao que nao e nenhuma das opcoes."""
    try:
        dados = json.loads(llm_json().read_text(encoding="utf-8-sig"))
        ordem = (dados.get("gemini") or {}).get("modelo_preferido")
    except (OSError, ValueError, AttributeError):
        return {"id": None, "ordem": None, "erro": "llm.json ilegível"}
    if not ordem:
        return {"id": None, "ordem": None}
    achado = next((m[0] for m in MODELOS_GEMINI if list(m[2]) == list(ordem)), "outro")
    return {"id": achado, "ordem": list(ordem)}


def gravar_gemini(modelo_id: str | None) -> bool:
    """Grava (ou tira) o `modelo_preferido` do Gemini. Devolve se mudou."""
    caminho = llm_json()
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise Recusa(f"não consegui ler o {caminho.name}: {exc}") from exc
    if not isinstance(dados, dict):
        raise Recusa(f"{caminho.name} está ilegível")
    bloco = dict(dados.get("gemini") or {})
    antes = bloco.get("modelo_preferido")
    if modelo_id is None:
        bloco.pop("modelo_preferido", None)
    else:
        bloco["modelo_preferido"] = list(next(m[2] for m in MODELOS_GEMINI
                                              if m[0] == modelo_id))
    if bloco.get("modelo_preferido") == antes:
        return False
    if bloco:
        dados["gemini"] = bloco
    else:
        dados.pop("gemini", None)
    temporario = caminho.with_name(f".{caminho.name}.{os.getpid()}.tmp")
    temporario.write_text(_json_do_llm(dados), encoding="utf-8", newline="\n")
    os.replace(temporario, caminho)
    return True


def modelos_para_o_app(config: dict) -> dict:
    """Os tres seletores: as opcoes, o que vale e de onde vem. Nunca levanta."""
    try:
        from . import delegar
        codex = delegar.modelos_codex()
    except Exception:                                        # noqa: BLE001
        codex = {"modelos": [], "fonte": "", "padrao": {"modelo": "", "esforco": ""}}
    padrao = codex.get("padrao") or {}
    gemini = gemini_vigente()
    return {
        "claude": {
            "vigente": config.get("modelo_claude") or config.get("modelo_agentes"),
            "opcoes": [{"id": i, "rotulo": r, "nota": n} for i, r, n in MODELOS_CLAUDE],
            "padrao": "o padrão do Claude Code",
            "nota": ("Vale para os trabalhadores Claude do servidor (o despachante usa no "
                     "próximo). O da sessão do VS Code só você troca, com /model."),
        },
        "codex": {
            "vigente": config.get("modelo_codex"),
            "opcoes": [{"id": m["id"], "rotulo": m["nome"], "nota": m.get("descricao", "")}
                       for m in codex.get("modelos") or []],
            "padrao": (f"{padrao.get('modelo') or 'o do Codex'}"
                       + (f", esforço {padrao['esforco']}" if padrao.get("esforco") else "")),
            "fonte": codex.get("fonte", ""),
            "livre": True,
            "nota": ("Vale para as próximas tarefas delegadas (a que já roda segue no "
                     "dela). Padrão = o do ~/.codex/config.toml."),
        },
        "gemini": {
            "vigente": gemini.get("id"),
            "ordem": gemini.get("ordem"),
            "erro": gemini.get("erro"),
            "opcoes": [{"id": i, "rotulo": r, "nota": " → ".join(o)}
                       for i, r, o in MODELOS_GEMINI],
            "padrao": "Pro, senão Flash (o dos seletores)",
            "nota": ("É o Gemini do NAVEGADOR: muda também o da pipeline (qualidade e "
                     "vídeo das histórias) a partir do próximo chat aberto."),
        },
    }


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
    "tirar_da_fila": "tirar da fila",
    "adicionar_a_fila": "pôr na fila",
    "mensagem": "mensagem",
    "contestar": "contestou uma decisão",
    "modelo_agentes": "modelo dos agentes (Claude)",
    "modelo_claude": "modelo dos trabalhadores Claude",
    "modelo_codex": "modelo do Codex",
    "modelo_gemini": "modelo do Gemini (navegador)",
    # Estes quatro sao consumidos pelo coordenador residente, sem IA. Os
    # demais continuam pertencendo a sessao principal.
    "servico_reiniciar": "reiniciar servico",
    "servico_parar": "parar servico",
    "servico_ligar": "ligar servico",
    "pc_acao": "acao do PC",
}
# o que o app pode mandar pela rota de comando (o contestar tem rota propria)
DO_APP = tuple(c for c in COMANDOS if c != "contestar")


def validar_comando(comando: str, valor):
    """O valor normalizado, ou Recusa. A regra mora aqui, nao na tela."""
    if comando not in COMANDOS:
        raise Recusa(f"comando desconhecido: {comando}")
    if comando in ("servico_reiniciar", "servico_parar", "servico_ligar"):
        if valor not in ("app", "bot", "carteiro", "vila"):
            raise Recusa("servico desconhecido")
        return valor
    if comando == "pc_acao":
        if not isinstance(valor, str) or not valor.strip() or len(valor) > 100:
            raise Recusa("acao do PC invalida")
        return valor.strip()
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
            raise Recusa("diga o item e a direção, ou a ordem inteira")
        if "ordem" in valor:
            # a forma nova (29/09): a ordem final inteira, num comando so.
            # Antes, por um item no topo eram 6 "subir" seguidos.
            ordem = valor.get("ordem")
            if not isinstance(ordem, list) or len(ordem) > FILA_MAX:
                raise Recusa("a ordem é a lista dos ids da fila")
            if any(not isinstance(i, str) or not _ID.fullmatch(i) for i in ordem):
                raise Recusa("item da fila inválido")
            if len(set(ordem)) != len(ordem):
                raise Recusa("a ordem repete um item")
            esperava = valor.get("esperava")
            if esperava is not None and (not isinstance(esperava, str)
                                         or not re.fullmatch(r"[0-9a-f]{8}", esperava)):
                raise Recusa("esperava é a versão da fila que a tela mostrou")
            saida = {"ordem": list(ordem)}
            if esperava is not None:
                saida["esperava"] = esperava
            return saida
        item, direcao = valor.get("item"), valor.get("direcao")
        if not isinstance(item, str) or not _ID.fullmatch(item):
            raise Recusa("item da fila inválido")
        if direcao not in ("subir", "descer", "topo"):
            raise Recusa("a direção é subir, descer ou topo")
        return {"item": item, "direcao": direcao}
    if comando == "tirar_da_fila":
        if not isinstance(valor, str) or not _ID.fullmatch(valor):
            raise Recusa("item da fila inválido")
        return valor
    if comando == "adicionar_a_fila":
        if not isinstance(valor, dict):
            raise Recusa("diga a parte e o item")
        parte = _curto(valor.get("parte"), 40)
        item = _curto(valor.get("item"), 200)
        if not parte or not item:
            raise Recusa("diga a parte e o item")
        return {"parte": parte, "item": item}
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
    if comando in ("modelo_agentes", "modelo_claude"):
        if valor in (None, ""):
            return None
        if not isinstance(valor, str) or valor not in {m[0] for m in MODELOS_CLAUDE}:
            raise Recusa("modelo dos agentes: " + ", ".join(m[0] for m in MODELOS_CLAUDE))
        return valor
    if comando == "modelo_codex":
        from . import delegar
        try:
            return delegar.validar_modelo(valor if isinstance(valor, str) or valor is None
                                          else "?")
        except delegar.Recusa as exc:
            raise Recusa(str(exc)) from None
    if comando == "modelo_gemini":
        if valor in (None, ""):
            return None
        if not isinstance(valor, str) or valor not in {m[0] for m in MODELOS_GEMINI}:
            raise Recusa("modelo do Gemini: " + ", ".join(m[0] for m in MODELOS_GEMINI))
        return valor
    raise Recusa(f"comando desconhecido: {comando}")        # pragma: no cover


def gravar_comando(comando: str, valor=None, aparelho: str = "") -> dict:
    """O app manda. Fica PENDENTE ate o orquestrador dizer `aplicado`."""
    valor = validar_comando(comando, valor)
    agora = time.time()
    ordem_inteira = comando == "priorizar" and "ordem" in valor
    with _trava():
        if ordem_inteira:
            # Estrito na entrada: id que a fila nao tem, item que a ordem nao
            # diz onde fica, ou a fila mudou no PC (`esperava`) = Recusa. A
            # ordem igual a atual nao vira comando ("ja estava assim").
            fila = ler_estado()["fila"]
            _conferir_ordem(fila, valor["ordem"], valor.get("esperava"))
            if valor["ordem"] == [f.get("id") for f in fila]:
                return {"comando": comando, "valor": valor, "ja_estava": True,
                        "aparelho": str(aparelho or "")[:8]}
        # O MESMO pedido ainda pendente nao entra de novo. Em 29/09 01:15:19,
        # tres toques rapidos no "+" gravaram max_paralelo 4, 4 e 5 no mesmo
        # segundo: o 4 repetido virou uma segunda resposta no Grimorio. So o
        # "priorizar" de um item soma (subir duas vezes e subir duas
        # posicoes); o da ordem inteira e idempotente como os outros.
        if comando != "priorizar" or ordem_inteira:
            lista, _ = comandos_com_situacao()
            chave = json.dumps(valor, sort_keys=True, ensure_ascii=False)
            igual = next((c for c in reversed(lista)
                          if c["situacao"] == "pendente" and c.get("comando") == comando
                          and json.dumps(c.get("valor"), sort_keys=True,
                                         ensure_ascii=False) == chave
                          and str(c.get("aparelho") or "") == str(aparelho or "")[:8]),
                         None)
            if igual is not None:
                return {k: igual.get(k) for k in ("id", "em", "comando", "valor",
                                                  "aparelho")} | {"repetido": True}
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


# ------------------------------------------------ capacidade vira regra
# Decisao do Adrian `geral/capacidade-pelo-app` (28/09, "Substitui: o que eu
# mudo no app vira a regra"). Ao valer, cada mudanca de capacidade responde o
# no correspondente do Grimorio, com commit: pela Mesa (`aplicado`) ou por uma
# instrucao dele no chat (`capacidade --fonte chat`). O modo que o proprio
# orquestrador liga (`modo`, ex.: a janela da forca total) e operacional e NAO
# vira regra.
COMANDO_PARA_CHAVE = {"max_paralelo": "max_paralelo", "modo": "modo",
                      "teto_uso": "teto_sessao_pct",
                      "forca_total": "forca_total_antes_min"}
NO_DA_CHAVE = {"max_paralelo": "modo-de-trabalho", "modo": "modo-de-trabalho",
               "teto_sessao_pct": "teto-de-uso",
               "forca_total_antes_min": "forca-total-ainda-vale"}
FONTES = {"app": "pela Mesa de comando", "chat": "no chat"}


def regra_da_config(chave: str, config: dict) -> tuple[str, str, str]:
    """(no do Grimorio, opcao, texto) que a config diz para aquela chave."""
    no = NO_DA_CHAVE[chave]
    if no == "modo-de-trabalho":
        n = paralelo_efetivo(config)
        if n == 1:
            texto = ("um por vez" if config["modo"] == "um_por_vez"
                     else f"{ROTULO_MODO[config['modo']].lower()}, até 1 agente")
            return no, "um", texto
        return no, "paralelo", f"{ROTULO_MODO[config['modo']].lower()}, até {n} agentes"
    if no == "teto-de-uso":
        pct = int(config["teto_sessao_pct"])
        return no, ("cinquenta" if pct == 50 else "outro"), \
            f"passou de {pct}% da sessão, para tudo"
    antes = config["forca_total_antes_min"]
    if antes:
        return no, "ligada", f"força total {antes} min antes de renovar"
    return no, "so-quando-eu-pedir", "força total só quando eu pedir"


def registrar_no_grimorio(chave: str, config: dict, fonte: str, *,
                          aparelho: str = "", porque: str = "") -> str:
    """Responde o no da chave. Devolve a nota. Nunca levanta: a config ja
    vale, e o que falhar aparece na nota, que a tela mostra."""
    from . import decisoes
    try:
        no, opcao, texto = regra_da_config(chave, config)
    except (KeyError, TypeError, ValueError) as exc:
        return f"Grimório: não soube traduzir {chave} ({type(exc).__name__})"
    try:
        vigente = (decisoes.carregar().get(no) or {}).get("vigente") or {}
    except Exception:                                         # noqa: BLE001
        vigente = {}
    if vigente.get("opcao") == opcao and texto in str(vigente.get("comentario", "")):
        # ex.: o maximo mudou no modo "um por vez": a regra continua a mesma
        return f"Grimório: {no} já dizia isso ({texto})"
    comentario = (f"{datetime.now().strftime('%d/%m %H:%M')}, "
                  f"{FONTES.get(fonte, fonte)}: {texto}")
    if porque:
        comentario += f" — nas palavras dele: {_curto(porque, 300)}"
    try:
        evento = decisoes.responder(no, opcao, comentario, aparelho=aparelho,
                                    origem="mesa" if fonte == "app" else fonte,
                                    commitar=False)
        # A capacidade ja vale quando o no e respondido: a resposta nasce LIDA
        # (gerou nada alem da config), e o leitor nao a cobra do orquestrador.
        try:
            decisoes.marcar(f"{no}@{evento['em']}", ["nada"],
                            "aplicada pela Mesa de comando: a config já vale",
                            origem="mesa", commitar=False)
        except Exception:                                     # noqa: BLE001
            pass                                  # fica "não lida": o leitor mostra
        with decisoes._trava():
            evento["commit"] = decisoes.commitar_por_caminho(
                *decisoes._tudo_para_commit(),
                f"decisão({evento['projeto']}): {evento['titulo']} → {evento['opcao_rotulo']}")
    except KeyError:
        return f"Grimório: não existe o nó {no}"
    except decisoes.Recusa as exc:
        return f"Grimório: não registrei em {no} ({exc})"
    except Exception as exc:                                  # noqa: BLE001
        return f"Grimório: falhou em {no} ({type(exc).__name__}: {exc})"
    nota = f"Grimório: {no} → {evento['opcao_rotulo']} ({texto})"
    if evento.get("a_rever"):
        nota += f"; foram para \"a rever\": {', '.join(evento['a_rever'])}"
    if str(evento.get("commit", "")).startswith("falhou"):
        nota += f"; o commit ficou para depois ({evento['commit'][:120]})"
    return nota


def _mudar_capacidade(nome: str, valor, fonte: str, cid: str) -> tuple[str, bool]:
    """(chave da config, mudou?). So a config; o Grimorio vem depois."""
    chave = COMANDO_PARA_CHAVE[nome]
    novo = int(valor) if nome in ("max_paralelo", "teto_uso") else valor
    mudou = _mudar_config(chave, novo, fonte, cid)
    if mudou and nome == "modo":
        estado = ler_estado()
        estado["modo"] = valor
        _gravar_estado(estado)
    return chave, mudou


def _aplicar(nome: str, valor, fonte: str, cid: str, *, aparelho: str = "",
             porque: str = "") -> str:
    """O efeito de um comando. Devolve uma nota (ou ""). Chame sob a trava."""
    if nome in COMANDO_PARA_CHAVE:
        chave, mudou = _mudar_capacidade(nome, valor, fonte, cid)
        if not mudou:
            return "já estava assim"
        return registrar_no_grimorio(chave, ler_config(), fonte, aparelho=aparelho,
                                     porque=porque)
    if nome in ("modelo_agentes", "modelo_claude", "modelo_codex"):
        return "" if _mudar_config(nome, valor, fonte, cid) else "já estava assim"
    if nome == "modelo_gemini":
        antes = gemini_vigente().get("id")
        if not gravar_gemini(valor):
            return "já estava assim"
        _anexar(arquivo("config_historico.jsonl"),
                {"em": _agora_iso(), "chave": "modelo_gemini", "de": antes, "para": valor,
                 "origem": fonte, "comando": cid})
        return ("historias/config/llm.json mudou (vale no próximo chat do Gemini): "
                "commite por caminho")
    if nome == "pausar_fila":
        _mudar_config("fila_pausada", True, fonte, cid)
    elif nome == "retomar_fila":
        _mudar_config("fila_pausada", False, fonte, cid)
    elif nome == "priorizar":
        estado = ler_estado()
        if "ordem" in valor:
            nota = _ordenar(estado["fila"], valor["ordem"])
            _gravar_estado(estado)
            return nota
        _mover(estado["fila"], valor["item"], valor["direcao"])
        _gravar_estado(estado)
    elif nome == "tirar_da_fila":
        estado = ler_estado()
        antes = len(estado["fila"])
        estado["fila"] = [f for f in estado["fila"] if f.get("id") != valor]
        if len(estado["fila"]) == antes:
            raise Recusa(f"a fila não tem o item {valor}; recuse com o motivo")
        _numerar(estado["fila"])
        _gravar_estado(estado)
    elif nome == "adicionar_a_fila":
        estado = ler_estado()
        estado["fila"].append({"id": _novo_id(), "parte": valor["parte"],
                               "item": valor["item"], "desde": _agora_iso(),
                               "pedido": "Adrian"})
        _numerar(estado["fila"])
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


def _efeito(comando: dict) -> str:
    """O que o `aplicado` muda sozinho. Devolve uma nota (ou "")."""
    return _aplicar(comando["comando"], comando.get("valor"), "app", comando["id"],
                    aparelho=str(comando.get("aparelho") or ""))


def _descrever(nome: str, valor) -> str:
    rotulo = COMANDOS.get(nome, nome)
    if nome.startswith("modelo_") and valor is None:
        return f"{rotulo}: o padrão"
    if valor is None:
        return rotulo
    if nome == "forca_total":
        return f"{rotulo}: {'ligada' if valor else 'desligada'}"
    if nome == "teto_uso":
        return f"{rotulo}: {valor}%"
    if nome == "priorizar" and isinstance(valor, dict) and "ordem" in valor:
        return f"{rotulo}: {len(valor['ordem'])} item(ns), a ordem inteira"
    if isinstance(valor, dict):
        valor = " ".join(str(v) for v in valor.values())
    return f"{rotulo}: {_curto(valor, 80)}"


class JaResolvido(Recusa):
    """O comando ja nao esta pendente: outro (o servidor ou a CLI) resolveu antes."""


def aplicado(comando_id: str, *, recusado: str = "", nota: str = "", efeito: bool = True,
             depois=None, por: str = "") -> dict:
    """Quem aplica (o servidor, desde 04/10; ou a CLI) registra que aplicou, ou
    recusou com o motivo.

    `efeito=False`: quem chamou ja fez o efeito (a mensagem que virou pedido, o
    parar do servidor). `depois`: uma funcao chamada depois do efeito, cuja
    nota entra no registro (o espelho no despachante); a falha dela vira nota,
    nunca desfaz o que ja valeu. `por` vai na linha do tempo ("o servidor").
    """
    with _trava():
        lista, _ = comandos_com_situacao()
        comando = next((c for c in lista if c.get("id") == comando_id), None)
        if comando is None:
            raise Recusa(f"comando desconhecido: {comando_id}")
        if comando["situacao"] != "pendente":
            raise JaResolvido(f"o comando {comando_id} já foi {comando['situacao']}")
        # o nome do item, antes de ele sair da fila (a linha do tempo diz o que saiu)
        descricao = _descrever(comando["comando"], comando.get("valor"))
        if comando["comando"] == "tirar_da_fila":
            item = next((f for f in ler_estado()["fila"]
                         if f.get("id") == comando.get("valor")), None)
            if item:
                descricao = f"tirar da fila: [{item['parte']}] {item['item']}"
        if recusado:
            linha = {"id": comando_id, "em": _agora_iso(), "resultado": "recusado",
                     "motivo": _curto(recusado, 500), "nota": _curto(nota, 500)}
        else:
            extra = _efeito(comando) if efeito else ""
            if depois is not None:
                try:
                    mais = depois() or ""
                except Exception as exc:                     # noqa: BLE001
                    mais = f"o espelho falhou ({type(exc).__name__}: {_curto(exc, 160)})"
                extra = " · ".join(x for x in (extra, mais) if x)
            linha = {"id": comando_id, "em": _agora_iso(), "resultado": "aplicado",
                     "motivo": "", "nota": _curto(" · ".join(x for x in (nota, extra) if x),
                                                   500)}
        _anexar(arquivo("comandos_aplicados.jsonl"), linha)
        estado = ler_estado()                    # quem aplica esta vivo
        _movimento(estado, (f"{por} " if por else "")
                   + ("recusou " if recusado else "aplicou ") + descricao)
        _gravar_estado(estado)
    return linha


def capacidade(pedidos, *, fonte: str = "chat", porque: str = "") -> list[dict]:
    """Uma instrucao do Adrian fora do app (no chat) vira regra IGUAL a uma da
    Mesa: muda a config pelo mesmo caminho do `aplicado`, com historico, e
    responde o no do Grimorio. Entra na lista de comandos ja aplicada, com a
    fonte, para a Mesa mostrar de onde veio.

    `pedidos` e [(comando, valor)]. Tudo e validado antes de mudar qualquer
    coisa, e o Grimorio e respondido UMA vez por no, com a config final: "modo
    paralelo, ate 2" numa instrucao so nao passa por um "um por vez" no meio.
    """
    if fonte not in FONTES:
        raise Recusa(f"fonte desconhecida: {fonte} ({', '.join(FONTES)})")
    validados = []
    for nome, valor in pedidos:
        if nome not in COMANDO_PARA_CHAVE:
            raise Recusa(f"capacidade é {', '.join(COMANDO_PARA_CHAVE)}")
        validados.append((nome, validar_comando(nome, valor)))
    if not validados:
        raise Recusa("diga o que muda: --max-paralelo, --modo, --teto ou --forca-total")
    with _trava():
        feitos, nos = [], {}
        for nome, valor in validados:
            cid = _novo_id()
            chave, mudou = _mudar_capacidade(nome, valor, fonte, cid)
            feitos.append({"id": cid, "comando": nome, "valor": valor, "chave": chave,
                           "mudou": mudou})
            if mudou:
                nos.setdefault(NO_DA_CHAVE[chave], chave)
        config = ler_config()
        notas = {no: registrar_no_grimorio(chave, config, fonte, porque=porque)
                 for no, chave in nos.items()}
        for feito in feitos:
            feito["nota"] = (notas[NO_DA_CHAVE[feito["chave"]]] if feito["mudou"]
                             else "já estava assim")
            em = _agora_iso()
            # O `aplicado` ANTES do comando: quem le (o `esperar`) le os
            # comandos primeiro, entao nunca ve este como pendente.
            _anexar(arquivo("comandos_aplicados.jsonl"),
                    {"id": feito["id"], "em": em, "resultado": "aplicado", "motivo": "",
                     "nota": _curto(" · ".join(x for x in (_curto(porque, 200),
                                                           feito["nota"]) if x), 500)})
            _anexar(arquivo("comandos.jsonl"),
                    {"id": feito["id"], "em": em, "comando": feito["comando"],
                     "valor": feito["valor"], "aparelho": "", "fonte": fonte})
        estado = ler_estado()
        _movimento(estado, f"capacidade {FONTES[fonte]}: "
                   + "; ".join(_descrever(f["comando"], f["valor"]) for f in feitos))
        _gravar_estado(estado)
    return feitos


# ===================================================== o servidor aplica
# 04/10/2026, o Adrian: "tá com um aviso de sessão fechada em relação ao
# orquestrador, resolva tudo". Desde 03/10 a hierarquia e SERVIDOR (o
# coordenador, 24 h) -> APP -> trabalhadores (Claude, Codex, VS Code). Medido
# as 13:16: o app dizia "Sessao fechada: sem sinal do orquestrador desde 07:12
# (ha 5 h 59 min)" com o selo vermelho, enquanto o coordenador pulsava a cada
# 5 s, com 2 trabalhadores rodando e 3 pedidos. E os comandos do app (max
# paralelo, fila, parar, modelos, mensagem) ficavam pendentes ate a sessao do
# VS Code rodar `esperar`/`aplicado`.
#
# Agora o pulso do coordenador chama `aplicar_pelo_servidor` para cada
# pendente: a config muda aqui (e no despachante, `delegados/config.json`), a
# mensagem vira PEDIDO (`coordenador.pedidos`), o parar vai ao despachante. Com
# o Claude proibido os comandos tambem valem: aplicar nao usa o Claude (a
# mensagem vira pedido, e o pedido espera o Claude ou vai ao Codex). A sessao
# do VS Code e so mais um trabalhador: se o `esperar` dela aplicar antes, o
# servidor ve `JaResolvido` e segue.
COORDENADOR_SEM_PULSO_S = 120     # sem pulso ha mais que isto: alarme
COMANDO_PARADO_S = 120            # pendente ha mais que isto com o servidor no ar: alarme
TRABALHADOR_TRAVADO_S = 15 * 60   # rodando sem evento (os pedidos param aos 10 min)
DO_SUPERVISOR = ("servico_reiniciar", "servico_parar", "servico_ligar", "pc_acao")


def _registrar_pedido(texto: str) -> dict:
    from coordenador import pedidos
    return pedidos.registrar(texto, "app")


def _espelhar_no_despachante(nome: str, despachante=None) -> str:
    """A capacidade e o modelo Claude da Mesa valem tambem para os
    trabalhadores do servidor (`delegados/config.json`). O `modelo_codex` o
    despachante ja le da Mesa a cada `criar`."""
    if despachante is None:
        from . import delegar as despachante
    config = ler_config()
    if nome in ("max_paralelo", "modo"):
        n = paralelo_efetivo(config)
        if int(despachante.ler_config().get("delegados_paralelo") or 1) == n:
            return f"o despachante já estava em {n} trabalhador(es) ao mesmo tempo"
        despachante.gravar_config({"delegados_paralelo": n})
        return f"despachante: até {n} trabalhador(es) ao mesmo tempo"
    if nome in ("modelo_agentes", "modelo_claude"):
        modelo = config.get("modelo_claude") or config.get("modelo_agentes")
        despachante.gravar_config({"modelo_claude": modelo})
        return "despachante: trabalhadores Claude com " + (modelo or "o modelo padrão")
    return ""


def _parar_pelo_servidor(alvo: str, despachante=None, vscode_aberto: bool = False) -> str:
    """Parar um trabalhador do servidor (o despachante para em ~2 s) e/ou um
    agente da Mesa. Agente da Mesa com o VS Code fechado ja nao roda (morreu
    com a sessao): fecha como "parado". Aberto, fica "parando" para ela."""
    if despachante is None:
        from . import delegar as despachante
    notas, achou = [], False
    try:
        ficha = despachante.ler_estado(alvo)
    except Exception:                                        # noqa: BLE001
        ficha = None
    if ficha is not None:
        achou = True
        try:
            notas.append(str(despachante.parar(alvo)))
        except Exception as exc:                             # noqa: BLE001
            notas.append(f"trabalhador {alvo}: {_curto(exc, 160)}")
    estado = ler_estado()
    agente = next((a for a in estado["agora"] if a.get("id") == alvo), None)
    if agente is not None:
        achou = True
        if vscode_aberto:
            agente["situacao"] = "parando"
            _gravar_estado(estado)
            notas.append("na Mesa: parando (a sessão do VS Code fecha com agente-fim)")
        else:
            agente_fim(alvo, situacao="parado",
                       relato_final="parado pelo servidor a pedido do app; o VS Code estava fechado")
            notas.append("na Mesa: fechado como parado (o VS Code está fechado)")
    if not achou:
        raise Recusa(f"nenhum trabalhador nem agente com o id {alvo}")
    return " · ".join(notas)


def aplicar_pelo_servidor(comando: dict, *, registrar_pedido=None, despachante=None,
                          vscode_aberto=None) -> dict | None:
    """Um comando do app, aplicado no pulso do coordenador. Devolve a linha de
    `comandos_aplicados.jsonl`, ou None quando nao era dele (servico e acao do
    PC sao do supervisor) ou outro ja resolveu. Recusa vira "recusado" com o
    motivo; erro de disco sobe (fica pendente e o pulso tenta de novo)."""
    cid = str(comando.get("id") or "")
    nome = comando.get("comando")
    valor = comando.get("valor")
    if not cid or nome in DO_SUPERVISOR:
        return None
    por = "o servidor"
    with _trava(), _pelo_servidor():
        atual = next((c for c in pendentes() if c.get("id") == cid), None)
        if atual is None:
            return None                          # ja resolvido (a CLI, o VS Code)
        try:
            if nome == "mensagem":
                texto = str(valor or "").strip()
                pedido = (registrar_pedido or _registrar_pedido)(texto)
                nota = (f"virou o pedido {pedido.get('id')}"
                        + (" (continuação do pedido em andamento)" if pedido.get("continuacao")
                           else "")
                        + "; um orquestrador do servidor atende (Agora > Pedir mostra)")
                return aplicado(cid, efeito=False, nota=nota, por=por)
            if nome == "parar_agente":
                if vscode_aberto is None:
                    vscode_aberto = situacao_do_vscode()["aberto"]
                nota = _parar_pelo_servidor(str(valor or ""), despachante, vscode_aberto)
                return aplicado(cid, efeito=False, nota=nota, por=por)
            if nome == "contestar":
                return aplicado(cid, efeito=False, por=por,
                                nota="o nó já está no Grimório; a sua resposta lá vira pedido "
                                     "no servidor")
            depois = None
            if nome in ("max_paralelo", "modo", "modelo_agentes", "modelo_claude"):
                def depois():
                    return _espelhar_no_despachante(nome, despachante)
            nota = ("vale no próximo trabalhador Codex" if nome == "modelo_codex"
                    else "aplicado pelo servidor")
            return aplicado(cid, nota=nota, depois=depois, por=por)
        except JaResolvido:
            return None
        except Recusa as exc:
            return aplicado(cid, recusado=str(exc), por=por)
        except ValueError as exc:                # o pedido vazio, a origem errada
            return aplicado(cid, recusado=str(exc), por=por)


def _estado_do_coordenador() -> dict:
    """O retrato que o coordenador publica a cada pulso. Nunca levanta."""
    try:
        from coordenador.estado import ler_estado as ler
        dados = ler()
    except Exception:                                        # noqa: BLE001
        return {}
    return dados if isinstance(dados, dict) else {}


def _pedidos_vivos() -> list[dict] | None:
    """Os pedidos em andamento; None quando nao deu para ler."""
    try:
        from coordenador import pedidos
        return [p for p in pedidos.para_o_app()["pedidos"]
                if p.get("situacao") in pedidos.VIVOS]
    except Exception:                                        # noqa: BLE001
        return None


def _trabalhadores_do_servidor(agora: float) -> tuple[list[dict], list[dict]] | None:
    """(rodando, travados) entre os trabalhadores do despachante. Travado: o
    processo sumiu sem desfecho, ou rodando sem evento ha mais de 15 min."""
    try:
        from . import delegar
        lista = [delegar._vivo_para_tela(e) for e in delegar.listar()]
    except Exception:                                        # noqa: BLE001
        return None
    rodando, travados = [], []
    for t in lista:
        if t.get("situacao") == "sumiu":
            travados.append(dict(t, motivo_travado="o processo sumiu sem desfecho"))
            continue
        if t.get("situacao") != "rodando":
            continue
        rodando.append(t)
        sinal = t.get("ultimo_evento_em") or t.get("inicio")
        idade = _idade_s(sinal, agora) if sinal else None
        if idade is not None and idade > TRABALHADOR_TRAVADO_S:
            travados.append(dict(t, motivo_travado=f"sem evento há {_ha(idade)}"))
    return rodando, travados


def situacao_do_vscode(agora: float | None = None, estado: dict | None = None,
                       vigia: dict | None = None) -> dict:
    """A sessao do VS Code como mais um trabalhador: aberta ou fechada, sem
    alarme. Sinal dela: o `esperar` pulsando (vigia.json) ou o relato `eu`.
    (O `estado.atualizado_em` nao serve: o servidor tambem grava o estado.)"""
    agora = time.time() if agora is None else agora
    if vigia is None:
        vigia = situacao_do_vigia(agora, estado)
    if estado is None:
        try:
            estado = ler_estado() if arquivo("estado.json").is_file() else {}
        except Recusa:
            estado = {}
    principal = (estado or {}).get("principal") or {}
    relato_em = principal.get("relato_em")
    idade_relato = _idade_s(relato_em, agora) if relato_em else None
    ouvindo = vigia.get("situacao") in ("ouvindo", "acordou")
    aberto = ouvindo or (idade_relato is not None and idade_relato <= FORA_DO_AR_S)
    sinais = [str(x) for x in (vigia.get("pulso_em"), vigia.get("saiu_em"), relato_em) if x]
    ultimo = max(sinais) if sinais else None
    if aberto:
        texto = "VS Code: aberto" + (" (ouvindo os comandos também)" if ouvindo else "")
    else:
        quando = None
        if ultimo:
            hoje = datetime.fromtimestamp(agora).date().isoformat()
            quando = (_hhmm(ultimo) if ultimo[:10] == hoje
                      else f"{ultimo[8:10]}/{ultimo[5:7]} {_hhmm(ultimo)}")
        texto = "VS Code: fechado" + (f" (último sinal {quando})" if quando else "")
    return {"aberto": bool(aberto), "texto": texto, "ultimo_sinal": ultimo,
            "relato": principal.get("relato") if aberto else None,
            "relato_em": relato_em if aberto else None}


def comando_parado(comandos: list[dict], servidor: dict, agora: float | None = None) -> dict | None:
    """O comando pendente MAIS VELHO, passado de 2 min. Quem aplica e o pulso
    do servidor (segundos): pendente ha 2 min com ele no ar e defeito
    ("preso"); sem pulso, sai quando ele voltar ("sem_servidor")."""
    agora = time.time() if agora is None else agora
    pendentes_ = [c for c in comandos if c.get("situacao") == "pendente"]
    idades = [(_idade_s(c.get("em"), agora), c) for c in pendentes_]
    idades = [(i, c) for i, c in idades if i is not None]
    if not idades:
        return None
    idade, comando = max(idades, key=lambda x: x[0])
    if idade < COMANDO_PARADO_S:
        return None
    qual = (f"«{comando.get('rotulo') or comando.get('comando')}», pendente desde "
            f"{_hhmm(comando.get('em'))} (há {_ha(idade)})")
    if len(pendentes_) > 1:
        qual += f", e mais {len(pendentes_) - 1}"
    if (servidor or {}).get("situacao") == "ok":
        tipo = "preso"
        texto = (f"O servidor está no ar, mas um comando não saiu da fila: {qual}. "
                 "O pulso não conseguiu aplicar (veja os eventos do Coordenador).")
    else:
        tipo = "sem_servidor"
        texto = (f"O servidor está sem pulso: {qual}. O comando sai quando ele voltar.")
    return {"tipo": tipo, "comando": comando.get("id"), "desde": comando.get("em"),
            "idade_s": idade, "quantos": len(pendentes_), "texto": texto}


def situacao_do_servidor(agora: float | None = None, *, coordenador: dict | None = None,
                         comandos: list[dict] | None = None, uso: dict | None = None,
                         estado: dict | None = None, vigia: dict | None = None,
                         pedidos_vivos=..., trabalhadores=...) -> dict:
    """O que o app mostra no topo de Agora: o SERVIDOR.

    ok        o coordenador pulsou ha menos de 2 min;
    sem_pulso pulsou, mas ha mais que isso;
    nunca     nao ha retrato do coordenador.
    `alarmes` so tem problema real: servidor sem pulso, comando parado ha mais
    de 2 min, trabalhador travado e o Claude acima do teto. A sessao do VS
    Code vai em `vscode`, sem alarme.
    """
    agora = time.time() if agora is None else agora
    coordenador = _estado_do_coordenador() if coordenador is None else coordenador
    pulso_em = coordenador.get("pulso_em")
    idade = _idade_s(pulso_em, agora) if pulso_em else None
    if not pulso_em or idade is None:
        situacao, texto = "nunca", "O servidor (coordenador) nunca publicou um pulso aqui."
    elif idade <= COORDENADOR_SEM_PULSO_S:
        situacao = "ok"
        texto = f"Servidor no ar · pulso às {str(pulso_em)[11:19]}"
    else:
        situacao = "sem_pulso"
        texto = (f"Servidor sem pulso desde {_hhmm(pulso_em)} (há {_ha(idade)}): "
                 "comandos, pedidos e trabalhadores param até ele voltar.")
    if comandos is None:
        try:
            comandos, _ = comandos_com_situacao()
        except Recusa:
            comandos = []
    if pedidos_vivos is ...:
        pedidos_vivos = _pedidos_vivos()
    if trabalhadores is ...:
        trabalhadores = _trabalhadores_do_servidor(agora)
    rodando, travados = trabalhadores if trabalhadores is not None else ([], [])
    pendentes_ = [c for c in comandos if c.get("situacao") == "pendente"]
    parado = comando_parado(comandos, {"situacao": situacao}, agora)
    alarmes = []
    if situacao != "ok":
        alarmes.append(texto)
    if parado and situacao == "ok":
        alarmes.append(parado["texto"])
    for t in travados:
        alarmes.append(f"Trabalhador travado: {t.get('id')} ({t.get('titulo') or t.get('cargo') or '?'})"
                       f" — {t['motivo_travado']}.")
    if uso is None:
        try:
            uso = ler_uso(agora)
        except Recusa:
            uso = {}
    if (uso or {}).get("passou_teto"):
        medicao = (uso or {}).get("medicao") or {}
        pct = medicao.get("sessao_pct")
        alarmes.append("O Claude passou do teto de uso"
                       + (f" ({round(pct)}% da sessão, teto {uso.get('teto')}%)"
                          if pct is not None else "")
                       + ": os pedidos esperam ou vão ao Codex.")
    resumo = []
    if pedidos_vivos is None:
        resumo.append("pedidos: não deu para ler")
    else:
        resumo.append(f"{len(pedidos_vivos)} pedido(s) em andamento")
    if trabalhadores is None:
        resumo.append("trabalhadores: não deu para ler")
    else:
        resumo.append(f"{len(rodando)} trabalhador(es) rodando")
    resumo.append("comandos: todos aplicados" if not pendentes_
                  else f"comandos: {len(pendentes_)} esperando o pulso")
    return {"situacao": situacao, "texto": texto, "resumo": " · ".join(resumo),
            "pulso_em": pulso_em, "pulso_idade_s": idade, "pid": coordenador.get("pid"),
            "desde": coordenador.get("desde"), "versao": coordenador.get("versao"),
            "pedidos": None if pedidos_vivos is None else len(pedidos_vivos),
            "trabalhadores": None if trabalhadores is None else len(rodando),
            "travados": [{"id": t.get("id"), "titulo": t.get("titulo"),
                          "motivo": t["motivo_travado"]} for t in travados],
            "comandos_pendentes": len(pendentes_), "comando_parado": parado,
            "vscode": situacao_do_vscode(agora, estado, vigia), "alarmes": alarmes}


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
    """Mede e grava. Falha tambem e gravada: a tela nao pode mostrar o velho.

    Com o Claude proibido, NAO chama o claude.exe e nao grava nada: devolve
    o registro de antes com `parada` (a tela le a mesma coisa em `ler_uso`).
    """
    proibido = claude_estado.motivo_proibido()
    if proibido:
        try:
            anterior = _ler_json(arquivo("uso.json"), {}) or {}
        except Recusa:
            anterior = {}
        return dict(anterior if isinstance(anterior, dict) else {},
                    parada=f"sonda parada: {proibido}")
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
    passou do prazo, ou a janela ja renovou), "parada" (Claude proibido: a
    sonda nao roda) ou "nunca". So "ok" leva numero.
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
    estado_claude = claude_estado.ler()
    if not estado_claude["liberado"]:
        # A sonda nao roda: numero nenhum e atual. Diz desde quando esta
        # parada, e guarda so a hora da ultima medicao (o "desde").
        saida["situacao"] = "parada"
        saida["motivo"] = ("sonda parada: " + (
            f"Claude proibido desde {claude_estado.hhmm(estado_claude['em'])}"
            if estado_claude["em"] else estado_claude["texto"]))
        try:
            saida["desde"] = max(float(c[0].get("gravado_em") or 0)
                                 for c in candidatos) if candidatos else None
        except (TypeError, ValueError):
            saida["desde"] = None
        return saida
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
            if minutos > 0 and claude_estado.liberado():
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


def historico_da_config(n: int = 12) -> list[dict]:
    linhas, _ = _ler_jsonl(arquivo("config_historico.jsonl"))
    return list(reversed(linhas[-n:]))


def grimorio_da_capacidade(config: dict) -> list[dict]:
    """Os nos do Grimorio que a capacidade responde, e se batem com a config.

    `bate` False quer dizer: a Mesa vale uma coisa e o Grimorio diz outra
    (ex.: a regra mudou antes da automacao, ou o commit falhou). A tela avisa.
    """
    try:
        from . import decisoes
        itens = decisoes.carregar()
    except Exception as exc:                                 # noqa: BLE001
        return [{"erro": f"não consegui ler o Grimório: {type(exc).__name__}"}]
    saida, vistos = [], set()
    for chave in ("modo", "teto_sessao_pct", "forca_total_antes_min"):
        no, opcao, texto = regra_da_config(chave, config)
        if no in vistos:
            continue
        vistos.add(no)
        item = itens.get(no)
        if item is None:
            saida.append({"no": no, "existe": False, "bate": False, "esperado": texto})
            continue
        vigente = item.get("vigente") or {}
        rotulo = next((o["rotulo"] for o in item.get("opcoes") or []
                       if o["id"] == vigente.get("opcao")), vigente.get("opcao"))
        bate = (item.get("situacao") == "decidida" and vigente.get("opcao") == opcao
                and (opcao != "outro" or texto in str(vigente.get("comentario", ""))))
        saida.append({"no": no, "existe": True, "titulo": item.get("titulo"),
                      "situacao": item.get("situacao"), "opcao": vigente.get("opcao"),
                      "rotulo": rotulo, "comentario": vigente.get("comentario", ""),
                      "em": vigente.get("em"), "bate": bool(bate), "esperado": texto})
    return saida


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
    try:
        historico_config = historico_da_config()
    except Recusa as exc:
        erros.append(str(exc))
        historico_config = []
    principal = (estado or {}).get("principal") or {}
    vigia = situacao_do_vigia(agora, estado if existe else None)
    # 04/10: quem aplica os comandos e o SERVIDOR (o pulso do coordenador); a
    # sessao do VS Code e so mais um trabalhador (`servidor.vscode`, sem alarme)
    servidor = situacao_do_servidor(agora, comandos=comandos, uso=uso,
                                    estado=estado if existe else {}, vigia=vigia)
    return {
        "agora": datetime.fromtimestamp(agora).isoformat(timespec="seconds"),
        "agora_epoch": agora,
        "servidor": servidor,
        # o detalhe do `esperar` do VS Code (a CLI `vigia`); a tela nao alarma por ele
        "vigia": vigia,
        "comando_parado": servidor["comando_parado"],
        # o interruptor do Claude (liberado / proibido), com quem e desde quando
        "claude": claude_estado.para_o_app(),
        "estado": estado or _estado_vazio_sem_disco(),
        # a ORDEM da fila, num resumo: a tela devolve como `esperava` ao
        # reordenar (409 se a fila mudou no PC no meio do arrasto)
        "fila_versao": fila_versao((estado or {}).get("fila") or []),
        "estado_existe": existe,
        # fora do ar = o SERVIDOR sem pulso (antes: a sessao do VS Code sem sinal)
        "fora_do_ar": servidor["situacao"] != "ok",
        "idade_s": idade,
        "config": config,
        "paralelo_efetivo": paralelo_efetivo(config),
        "principal": {"relato": principal.get("relato"),
                      "relato_em": principal.get("relato_em"),
                      "movimento": principal.get("movimento"),
                      "movimento_em": principal.get("movimento_em"),
                      "linha": list(reversed(principal.get("linha") or []))},
        "historico_config": historico_config,
        "grimorio": grimorio_da_capacidade(config),
        "modos": [{"id": m, "rotulo": ROTULO_MODO[m]} for m in MODOS],
        "uso": uso,
        "historico_uso": historico,
        "decisoes": list(reversed(decisoes_lista))[:40],
        "comandos": list(reversed(comandos)),
        "pendentes": sum(1 for c in comandos if c.get("situacao") == "pendente"),
        "acessos": acessos,
        # o carteiro da Vila das IAs (fase 2): aparece em "Agora" quando esta
        # entregando, e a caixa de cada IA com os pendentes
        "carteiro": carteiro_para_a_mesa(),
        # o Codex (01/10): o cartao da Oficina e os tres seletores de modelo
        "delegados": delegados_para_a_mesa(),
        "modelos": modelos_para_o_app(config),
        "erros": erros,
    }


def delegados_para_a_mesa() -> dict | None:
    """O resumo das tarefas do Codex para o cartao da Mesa. Nunca derruba a Mesa."""
    try:
        from . import delegar
        d = delegar.para_o_app(n=5)
        return {"total": len(delegar.listar()), "rodando": d["rodando"], "uso": d["uso"],
                "teto": d["config"].get("teto_codex_pct"),
                "ultimas": [{k: t.get(k) for k in ("id", "titulo", "situacao", "inicio",
                                                   "fim", "modelo")}
                            for t in d["delegados"]]}
    except Exception:                                        # noqa: BLE001
        return None


def carteiro_para_a_mesa() -> dict | None:
    """O carteiro (`ias.carteiro`) e as caixas do correio, para o Agora.

    Nunca derruba a Mesa: sem o pacote `ias`, ou com o correio ilegivel,
    devolve None e a tela nao mostra a linha.
    """
    try:
        from ias import correio
        estado = correio.estado_do_carteiro()
        caixas = [{"ia": ia, "rotulo": info["rotulo"], "emoji": info["emoji"],
                   "pendentes": info["pendentes"], "em_andamento": info["em_andamento"],
                   "nao_vistas": info["nao_vistas"]}
                  for ia, info in correio.resumo().items()]
        return {**estado, "caixas": caixas,
                "pendentes": sum(c["pendentes"] + c["em_andamento"] for c in caixas)}
    except Exception:                                        # noqa: BLE001
        return None


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
    principal = estado.get("principal") or {}
    print("SESSÃO PRINCIPAL")
    if principal.get("relato"):
        print(f"  {str(principal.get('relato_em'))[11:16]}  {principal['relato']}")
    if principal.get("movimento"):
        print(f"  último movimento {str(principal.get('movimento_em'))[11:16]}: "
              f"{principal['movimento']}")
    if not principal.get("relato") and not principal.get("movimento"):
        print("  nada relatado (use: eu \"...\")")
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
        if c.get("tipo") == "claude_liberado":
            print(f"claude_liberado  {c.get('texto')}")
            continue
        if c.get("tipo") == "decisao_nova":
            if c.get("ilegivel"):
                print(f"decisao_nova  #{c['n']}  linha ilegível no _eventos.jsonl")
                continue
            print(f"decisao_nova  #{c['n']}  {c['projeto']}/{c['id']} → {c['opcao_rotulo']}"
                  + ("  [COMENTÁRIO: precisa de leitura]" if c.get("precisa_de_leitura")
                     else "")
                  + (f"  desbloqueia {len(c['desbloqueia'])}" if c.get("desbloqueia") else "")
                  + (f"  a rever {len(c['a_rever'])}" if c.get("a_rever") else ""))
            continue
        print(f"{c['id']}  {c['em']}  {c['comando']}  "
              f"{json.dumps(c.get('valor'), ensure_ascii=False)}")
    if lista and any(c.get("tipo") == "decisao_nova" for c in lista):
        print("leia com: python -m remoto.decisoes leitor")
    if not lista:
        print("nenhum comando pendente")


def texto_do_aviso_claude(liberado: bool, por: str, em: str | None) -> str:
    """O aviso do Telegram quando o interruptor muda (app ou CLI)."""
    return (f"🤖 Claude {'liberado' if liberado else 'proibido'} {por} às "
            f"{claude_estado.hhmm(em) if em else '?'}"
            + ("" if liberado else
               " — nenhum trabalhador Claude, sonda ou apuração roda; os pedidos "
               "esperam (os de construir vão ao Codex) e os comandos da Mesa "
               "continuam valendo."))


def _cli_claude(acao: str, *, motivo: str = "", por: str = "", avisar: bool = True,
                entregar=None) -> int:
    """`claude status|liberar|proibir`. Status: 0 liberado, 1 proibido."""
    if acao == "status":
        estado = claude_estado.ler()
        print(estado["texto"])
        for linha in claude_estado.historico(5):
            print(f"  {linha.get('em')}  {'liberado' if linha.get('liberado') else 'proibido'}"
                  f"  por {linha.get('por')}"
                  + (f" — {linha.get('motivo')}" if linha.get("motivo") else ""))
        return 0 if estado["liberado"] else 1
    feito = claude_estado.mudar(acao == "liberar", por=por, motivo=motivo)
    estado = feito["estado"]
    print(estado["texto"] if feito["mudou"] else f"já estava assim: {estado['texto']}")
    # Nada na linha do tempo do `estado.json`: gravar la renova o
    # `atualizado_em`, que e o "sinal de vida" da sessao, e um toque no
    # interruptor pelo app faria a Mesa dizer que a sessao esta no ar. O
    # registro e o `claude_historico.jsonl`, que a Mesa mostra.
    if feito["mudou"] and avisar:
        texto = texto_do_aviso_claude(estado["liberado"], f"por {por}", estado["em"])
        if entregar is None:
            from . import acoes
            acoes.avisar_texto(texto)
            acoes._FILA_AVISOS.join()         # a CLI sai logo: espera a entrega
        else:
            entregar(texto)
    return 0


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
    ford = fsub.add_parser("ordenar", help="a ordem final inteira, um comando so")
    ford.add_argument("ids", nargs="+")
    fsub.add_parser("listar")
    dec = sub.add_parser("decisao")
    dec.add_argument("--titulo", required=True)
    dec.add_argument("--escolha", required=True)
    dec.add_argument("--porque", default="")
    dec.add_argument("--alternativa", default="")
    dec.add_argument("--parte", default="geral")
    dec.add_argument("--em", default="")
    mod = sub.add_parser("modo", help="modo operacional (não vira regra)")
    mod.add_argument("modo", choices=MODOS)
    cap = sub.add_parser("capacidade",
                         help="instrução do Adrian: muda a config e responde o Grimório")
    cap.add_argument("--max-paralelo", default=None)
    cap.add_argument("--modo", default=None, choices=MODOS)
    cap.add_argument("--teto", default=None, help="teto de uso da sessão, 10 a 100")
    cap.add_argument("--forca-total", default=None, choices=("on", "off"))
    cap.add_argument("--fonte", default="chat", choices=tuple(FONTES))
    cap.add_argument("--porque", default="", help="as palavras dele, curtas")
    eu_ = sub.add_parser("eu", help="no que a sessão principal está, em uma linha")
    eu_.add_argument("texto")
    pen = sub.add_parser("pendentes")
    pen.add_argument("--json", action="store_true")
    apl = sub.add_parser("aplicado")
    apl.add_argument("id")
    apl.add_argument("--recusado", default="", metavar="MOTIVO")
    apl.add_argument("--nota", default="")
    esp = sub.add_parser("esperar",
                         help="bloqueia até chegar comando do app ou resposta nova no Grimório")
    esp.add_argument("--intervalo", type=float, default=5.0)
    esp.add_argument("--json", action="store_true")
    acs = sub.add_parser("acessos", help="gera o acessos.json")
    acs.add_argument("--conector", action="append", default=None)
    acs.add_argument("--modo-permissao", default=None)
    for nome in ("config", "estado", "uso", "pulso", "onde", "sonda", "vigia", "servidor",
                 "modelos"):
        sub.add_parser(nome)
    cla = sub.add_parser("claude", help="o interruptor do Claude: status, liberar, proibir")
    cla.add_argument("acao", nargs="?", default="status",
                     choices=("status", "liberar", "proibir"))
    cla.add_argument("--motivo", default="")
    cla.add_argument("--por", default="orquestrador (CLI)")
    cla.add_argument("--sem-aviso", action="store_true",
                     help="não manda o aviso no Telegram")
    args = p.parse_args(argv)
    # Quem le esta saida (o orquestrador) le por pipe: no Windows seria cp1252,
    # e um emoji da arvore derrubava o `arvore` com UnicodeEncodeError.
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

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
            elif args.acao == "ordenar":
                fila_ordenar(args.ids)
                print("ok")
            else:
                for f in ler_estado()["fila"]:
                    print(f"{f.get('prioridade')}. {f['id']}  [{f['parte']}] {f['item']}")
        elif args.cmd == "decisao":
            print(decisao(args.titulo, args.escolha, args.porque, args.alternativa,
                          args.parte, args.em)["id"])
        elif args.cmd == "modo":
            mudar_modo(args.modo)
            print(f"modo {args.modo} (operacional; instrução do Adrian: capacidade --modo)")
        elif args.cmd == "capacidade":
            pedidos = [(n, v) for n, v in (
                ("max_paralelo", args.max_paralelo), ("modo", args.modo),
                ("teto_uso", args.teto),
                ("forca_total", None if args.forca_total is None
                 else args.forca_total == "on")) if v is not None]
            for feito in capacidade(pedidos, fonte=args.fonte, porque=args.porque):
                print(f"{feito['id']} {feito['comando']}={feito['valor']} · "
                      f"{feito['nota'] or 'ok'}")
        elif args.cmd == "eu":
            principal = eu(args.texto)
            print(f"{principal['relato_em'][11:16]} {principal['relato']}")
        elif args.cmd == "pendentes":
            _imprimir_pendentes(pendentes(), args.json)
        elif args.cmd == "aplicado":
            linha = aplicado(args.id, recusado=args.recusado, nota=args.nota)
            print(f"{linha['id']} {linha['resultado']}"
                  + (f" — {linha['nota']}" if linha.get("nota") else ""))
        elif args.cmd == "esperar":
            return esperar(args.intervalo, como_json=args.json)
        elif args.cmd == "vigia":
            # a sessao do VS Code (o `esperar` dela); quem aplica e o servidor
            situacao = situacao_do_vigia()
            print(f"{situacao['situacao']}: {situacao['texto']}")
            return 0 if situacao["situacao"] in ("ouvindo", "acordou") else 1
        elif args.cmd == "servidor":
            servidor = situacao_do_servidor()
            print(f"{servidor['situacao']}: {servidor['texto']}")
            print(servidor["resumo"])
            print(servidor["vscode"]["texto"])
            for alarme in servidor["alarmes"]:
                print("ALARME: " + alarme)
            return 0 if servidor["situacao"] == "ok" and not servidor["alarmes"] else 1
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
        elif args.cmd == "modelos":
            m = modelos_para_o_app(ler_config())
            print(f"agentes (Claude): {m['claude']['vigente'] or 'padrão'} "
                  f"(o orquestrador passa no `model` de cada subagente)")
            print(f"Codex: {m['codex']['vigente'] or 'padrão = ' + m['codex']['padrao']}")
            print(f"Gemini (navegador): {m['gemini']['vigente'] or 'padrão'}"
                  + (f" -> {m['gemini']['ordem']}" if m['gemini'].get('ordem') else ""))
        elif args.cmd == "uso":
            print(json.dumps(ler_uso(), ensure_ascii=False, indent=2))
        elif args.cmd == "sonda":
            registro = sondar()
            if registro.get("parada"):
                print(registro["parada"], file=sys.stderr)
                return 2
            print(json.dumps(registro, ensure_ascii=False, indent=2))
            return 0 if not registro.get("motivo") else 2
        elif args.cmd == "pulso":
            print(pulso())
        elif args.cmd == "claude":
            return _cli_claude(args.acao, motivo=args.motivo, por=args.por,
                               avisar=not args.sem_aviso)
        else:
            print(f"pasta: {pasta()}")
            for nome in ("estado.json", "config.json", "comandos.jsonl",
                         "comandos_aplicados.jsonl", "decisoes_orquestrador.jsonl",
                         "uso.json", "uso_historico.jsonl", "acessos.json",
                         "config_historico.jsonl", "vigia.json",
                         "aviso_sem_ouvinte.json"):
                print(f"  {nome:<30} {'existe' if arquivo(nome).is_file() else '—'}")
        return 0
    except Recusa as exc:
        print(str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
