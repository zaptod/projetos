# -*- coding: utf-8 -*-
"""As decisoes do Adrian: uma arvore de habilidades por projeto, no git.

Pedido dele em 28/09/2026: "quero que seja separado por projetos e as decisoes
sejam tipo uma arvore de habilidades, assim posso voltar em alguma se quiser,
podendo ser compativel com o git, e essas decisoes devem de fato ir pras
sessoes para serem usadas como input".

ONDE MORA. `decisoes/<projeto>/<id>.json`, um arquivo por decisao, no
repositorio: indentacao 2, chaves ordenadas, LF e `\\n` no fim, para o diff
ser limpo. `decisoes/_eventos.jsonl` ganha uma linha por resposta, e o
orquestrador o vigia. `decisoes/<projeto>/README.md` e a arvore em texto,
gerada. A midia NAO vai para o git: o arquivo so aponta para ela (caminho do
repositorio, `%LOCALAPPDATA%\\...` ou absoluto).

A ARVORE. Uma decisao `depende_de` outras (decisao + opcao). Ela fica
`bloqueada` ate todos os pre-requisitos estarem `decidida` com a opcao
certa, e `pendente` dai em diante. Respondida, fica `decidida`. Quando ele
VOLTA e troca a opcao de uma decisao, tudo o que dependia dela (em qualquer
nivel) e tinha resposta vira `a_rever` — o "respec". Nada se apaga: cada
resposta entra no `historico`, e a `vigente` e so a ultima.

VIRA ENTRADA DAS SESSOES. Cada `docs/sessoes/<parte>.md` tem um bloco gerado
entre `<!-- decisoes:inicio -->` e `<!-- decisoes:fim -->` com as vigentes e
as pendentes daquela parte (e as gerais), regenerado a cada resposta.

COMMIT POR RESPOSTA, so por caminho: `git commit -- <arquivos>`. Nunca `-a`
nem `add .` (outro agente pode ter arquivo no stage). O bloco de uma sessao
so entra no commit se o arquivo nao tiver OUTRA mudanca por commitar. Commit
que falha nao desfaz a decisao: ela vale, e o aviso diz que o commit ficou.

    python -m remoto.decisoes listar [--projeto P] [--situacao S]
    python -m remoto.decisoes arvore [--projeto P]
    python -m remoto.decisoes adicionar --projeto P --titulo T --pergunta Q \\
        --opcao "Rotulo" --opcao "id=Rotulo|descricao" \\
        [--midia "caminho|ROTULO"] [--copiar] [--depende "decisao=opcao"] \\
        [--contexto C] [--sem-comentario] [--id ID] [--commit]
    python -m remoto.decisoes responder <id> <opcao> [--comentario C] [--sem-commit]
    python -m remoto.decisoes gerar      # regenera READMEs e blocos das sessoes
    python -m remoto.decisoes tirar-dependencia <id> <decisao> --nota N [--sem-commit]
    python -m remoto.decisoes onde
    python -m remoto.decisoes leitor [--todos] [--projeto P] [--json]   # respostas nao lidas
    python -m remoto.decisoes leitor marcar <N|id@em|projeto/id> \\
        --gerou tarefa:<id>|no:<projeto/id>|nada [--gerou ...] [--nota N] [--sem-commit]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from .config import runtime_dir

RAIZ = Path(__file__).resolve().parents[1]
# Os testes apontam tudo para um repositorio temporario.
PASTA = None                  # decisoes/
SESSOES = None                # docs/sessoes/
REPO = None                   # a raiz do git
TRAVA = None                  # o .lock (fora do repositorio)
MIDIA_LOCAL = None            # %LOCALAPPDATA%/neural-fights/decisoes_midia

PROJETOS = ("geral", "builds", "historias", "publicacao", "metricas",
            "app-e-bot", "painel-e-vila", "jogo-zombie")
ROTULOS = {"geral": "Geral", "builds": "Builds", "historias": "Histórias",
           "publicacao": "Publicação", "metricas": "Métricas",
           "app-e-bot": "App e bot", "painel-e-vila": "Painel e Vila",
           "jogo-zombie": "Jogo zombie"}
SITUACOES = ("bloqueada", "pendente", "decidida", "a_rever")
ICONES = {"decidida": "✅", "pendente": "⏳", "bloqueada": "🔒", "a_rever": "↺"}
COMENTARIO_MAX = 2000
TIPOS = {".mp4": "video/mp4", ".webm": "video/webm", ".png": "image/png",
         ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
_PEDE_COMENTARIO = re.compile(r"\((?:comente|diga)", re.IGNORECASE)
_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,59}")
INICIO, FIM = "<!-- decisoes:inicio -->", "<!-- decisoes:fim -->"
TENTATIVAS_DE_COMMIT = 6


class Recusa(Exception):
    """A operacao nao vai acontecer; a mensagem e para a tela."""


# ================================================================== lugares
def repo() -> Path:
    """A raiz do git. `NF_DECISOES_REPO` troca (a instancia de teste e a CLI
    que ela chama apontam para um clone, nunca para o repositorio real)."""
    if REPO:
        return Path(REPO)
    if os.environ.get("NF_DECISOES_REPO"):
        return Path(os.environ["NF_DECISOES_REPO"])
    return RAIZ


def pasta() -> Path:
    return Path(PASTA) if PASTA else repo() / "decisoes"


def pasta_sessoes() -> Path:
    return Path(SESSOES) if SESSOES else repo() / "docs" / "sessoes"


def pasta_midia_local() -> Path:
    return Path(MIDIA_LOCAL) if MIDIA_LOCAL else runtime_dir() / "decisoes_midia"


def caminho_eventos() -> Path:
    return pasta() / "_eventos.jsonl"


def caminho_item(projeto: str, item_id: str) -> Path:
    return pasta() / projeto / f"{item_id}.json"


def _trava():
    """Entre threads e entre processos (o servidor e a CLI)."""
    from .api_http import trava_arquivo
    if TRAVA:
        alvo = Path(TRAVA)
    elif os.environ.get("NF_DECISOES_REPO"):
        alvo = Path(os.environ["NF_DECISOES_REPO"]).parent / "decisoes.lock"
    else:
        alvo = runtime_dir() / "decisoes.lock"
    return trava_arquivo(alvo)


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ============================================================ caminhos da midia
def _guardar_caminho(caminho: Path) -> str:
    """Como o caminho vai para o git: relativo ao repo, %LOCALAPPDATA% ou cru."""
    caminho = Path(caminho).resolve()
    try:
        return caminho.relative_to(repo().resolve()).as_posix()
    except ValueError:
        pass
    local = os.environ.get("LOCALAPPDATA")
    if local:
        try:
            return "%LOCALAPPDATA%\\" + str(caminho.relative_to(Path(local).resolve()))
        except ValueError:
            pass
    return str(caminho)


def resolver_caminho(guardado: str) -> Path:
    caminho = Path(os.path.expandvars(str(guardado or "")))
    return caminho if caminho.is_absolute() else repo() / caminho


def tipo_da_midia(caminho) -> str | None:
    return TIPOS.get(Path(str(caminho)).suffix.lower())


# ================================================================== disco
def _canonico(item: dict) -> bytes:
    return (json.dumps(item, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def _gravar_bytes(alvo: Path, dados: bytes) -> None:
    alvo.parent.mkdir(parents=True, exist_ok=True)
    temporario = alvo.with_name(f".{alvo.name}.{os.getpid()}.tmp")
    temporario.write_bytes(dados)
    os.replace(temporario, alvo)


def carregar() -> dict:
    """{id: item} de todos os projetos. Arquivo ilegivel = Recusa.

    Tratar ilegivel como ausente faria a arvore recalcular sem ele e
    desbloquear (ou mandar para "a rever") o que nao devia.
    """
    itens = {}
    for projeto in PROJETOS:
        for arquivo in sorted((pasta() / projeto).glob("*.json")):
            try:
                item = json.loads(arquivo.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise Recusa(f"decisoes/{projeto}/{arquivo.name} está ilegível") from exc
            if not isinstance(item, dict) or item.get("id") != arquivo.stem:
                raise Recusa(f"decisoes/{projeto}/{arquivo.name} está ilegível")
            itens[item["id"]] = item
    _topologica(itens)            # ciclo escrito a mao = Recusa, em toda leitura
    return itens


def _gravar_itens(itens: dict, ids) -> list[Path]:
    """Grava os itens `ids` se mudaram. Devolve os caminhos gravados."""
    gravados = []
    for item_id in ids:
        item = itens[item_id]
        alvo = caminho_item(item["projeto"], item_id)
        novo = _canonico(item)
        try:
            if alvo.read_bytes() == novo:
                continue
        except OSError:
            pass
        _gravar_bytes(alvo, novo)
        gravados.append(alvo)
    return gravados


# ================================================================== arvore
QUALQUER = "*"                # depende de a decisao estar tomada, qualquer opcao


def _satisfeita(dep: dict, itens: dict) -> bool:
    alvo = itens.get(dep.get("decisao"))
    if not (alvo and alvo.get("situacao") == "decidida" and alvo.get("vigente")):
        return False
    return dep.get("opcao") in (QUALQUER, alvo["vigente"].get("opcao"))


def _topologica(itens: dict) -> list[str]:
    ordem, estado = [], {}

    def visitar(item_id, caminho=()):
        if estado.get(item_id) == 2:
            return
        if estado.get(item_id) == 1:
            raise Recusa("ciclo na árvore: " + " → ".join(caminho + (item_id,)))
        estado[item_id] = 1
        for dep in itens[item_id].get("depende_de") or []:
            if dep.get("decisao") in itens:
                visitar(dep["decisao"], caminho + (item_id,))
        estado[item_id] = 2
        ordem.append(item_id)

    for item_id in sorted(itens):
        visitar(item_id)
    return ordem


def recalcular(itens: dict) -> None:
    """A situacao de cada um, dos pre-requisitos para os dependentes.

    `a_rever` e pegajoso: so sai quando ele responde de novo aquela decisao.
    """
    for item_id in _topologica(itens):
        item = itens[item_id]
        ok = all(_satisfeita(d, itens) for d in item.get("depende_de") or [])
        if item.get("vigente"):
            item["situacao"] = ("a_rever" if item.get("situacao") == "a_rever"
                                or not ok else "decidida")
        else:
            item["situacao"] = "pendente" if ok else "bloqueada"


def _sincronizar_arestas(itens: dict) -> None:
    """`opcoes[].desbloqueia` sai dos `depende_de` dos outros, sempre igual."""
    abre: dict = {}
    for outro in itens.values():
        for dep in outro.get("depende_de") or []:
            abre.setdefault((dep.get("decisao"), dep.get("opcao")), set()).add(outro["id"])
    for item in itens.values():
        qualquer = abre.get((item["id"], QUALQUER), set())
        for opcao in item.get("opcoes") or []:
            opcao["desbloqueia"] = sorted(abre.get((item["id"], opcao["id"]), set())
                                          | qualquer)


def dependentes(itens: dict, item_id: str) -> list[str]:
    """Todos os que dependem de `item_id`, em qualquer nivel."""
    filhos: dict = {}
    for outro in itens.values():
        for dep in outro.get("depende_de") or []:
            filhos.setdefault(dep.get("decisao"), set()).add(outro["id"])
    vistos, fila = [], sorted(filhos.get(item_id, ()))
    while fila:
        atual = fila.pop(0)
        if atual in vistos:
            continue
        vistos.append(atual)
        fila.extend(sorted(filhos.get(atual, ())))
    return vistos


def a_rever_se_mudar(itens: dict, item_id: str) -> list[str]:
    """O que vai para "a rever" se ele trocar a opcao desta decisao."""
    return [d for d in dependentes(itens, item_id) if itens[d].get("vigente")]


# ================================================================== itens
def _slug(texto: str, limite: int = 40) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore")
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.decode().lower()).strip("-")
    return slug[:limite].strip("-") or "x"


def _opcoes(brutas) -> list[dict]:
    saida, vistos = [], set()
    for bruta in brutas or []:
        if isinstance(bruta, dict):
            rotulo = str(bruta.get("rotulo") or "").strip()
            descricao = str(bruta.get("descricao") or "").strip()
            opcao_id = str(bruta.get("id") or "").strip()
        else:
            texto = str(bruta)
            opcao_id = ""
            if "=" in texto.split("|")[0]:
                opcao_id, _, texto = texto.partition("=")
            rotulo, _, descricao = texto.partition("|")
            rotulo, descricao = rotulo.strip(), descricao.strip()
        if not rotulo:
            raise Recusa("opção sem rótulo")
        opcao_id = opcao_id.strip() or _slug(rotulo, 30)
        if not _ID.fullmatch(opcao_id) or opcao_id in vistos:
            raise Recusa(f"id de opção inválido ou repetido: {opcao_id}")
        vistos.add(opcao_id)
        saida.append({"id": opcao_id, "rotulo": rotulo, "descricao": descricao,
                      "desbloqueia": [],
                      "pede_comentario": bool(_PEDE_COMENTARIO.search(rotulo))})
    if not saida:
        raise Recusa("a decisão precisa de pelo menos uma opção")
    return saida


def _midias(brutas, item_id: str, copiar: bool) -> list[dict]:
    saida = []
    for bruta in brutas or []:
        if isinstance(bruta, (tuple, list)):
            caminho, rotulo = bruta[0], (bruta[1] if len(bruta) > 1 else "")
        elif isinstance(bruta, dict):
            caminho, rotulo = bruta.get("caminho"), bruta.get("rotulo", "")
        else:
            caminho, _, rotulo = str(bruta).partition("|")
        caminho = Path(str(caminho).strip().strip('"'))
        if not caminho.is_file():
            raise Recusa(f"a mídia não existe: {caminho}")
        if tipo_da_midia(caminho) is None:
            raise Recusa(f"tipo de mídia que o celular não toca: {caminho.suffix} "
                         f"(aceito: {', '.join(sorted(TIPOS))})")
        if copiar:
            destino = pasta_midia_local() / item_id / caminho.name
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(caminho, destino)
            caminho = destino
        saida.append({"caminho": _guardar_caminho(caminho),
                      "rotulo": str(rotulo).strip()})
    return saida


def _dependencias(brutas, itens: dict) -> list[dict]:
    saida = []
    for bruta in brutas or []:
        if isinstance(bruta, dict):
            decisao, opcao = bruta.get("decisao"), bruta.get("opcao")
        else:
            decisao, _, opcao = str(bruta).partition("=")
        decisao, opcao = str(decisao or "").strip(), str(opcao or "").strip()
        alvo = itens.get(decisao)
        if alvo is None:
            raise Recusa(f"depende de uma decisão que não existe: {decisao}")
        if opcao != QUALQUER and opcao not in {o["id"] for o in alvo.get("opcoes") or []}:
            raise Recusa(f"a decisão {decisao} não tem a opção {opcao}")
        saida.append({"decisao": decisao, "opcao": opcao})
    return saida


def adicionar(projeto: str, titulo: str, pergunta: str, opcoes, midias=(), *,
              id: str | None = None, contexto: str = "", comentario: bool = True,
              depende_de=(), copiar: bool = False) -> dict:
    """Registra uma decisao nova e regenera a arvore. Nao commita."""
    if projeto not in PROJETOS:
        raise Recusa(f"projeto desconhecido: {projeto} ({', '.join(PROJETOS)})")
    titulo = str(titulo or "").strip()
    if not titulo:
        raise Recusa("a decisão precisa de um título")
    with _trava():
        itens = carregar()
        item_id = id or _slug(titulo)
        if not _ID.fullmatch(item_id):
            raise Recusa(f"id inválido: {item_id}")
        if item_id in itens:
            raise Recusa(f"já existe uma decisão com o id {item_id}")
        item = {"id": item_id, "projeto": projeto, "titulo": titulo,
                "pergunta": str(pergunta or "").strip(),
                "contexto": str(contexto or "").strip(),
                "midias": _midias(midias, item_id, copiar),
                "opcoes": _opcoes(opcoes),
                "comentario": bool(comentario),
                "depende_de": _dependencias(depende_de, itens),
                "situacao": "pendente", "vigente": None, "historico": [],
                # Com microssegundos: a arvore e o README seguem a ordem em que
                # as decisoes nasceram, e as de um mesmo segundo empatariam.
                "criado": datetime.now().isoformat(timespec="microseconds")}
        itens[item_id] = item
        _topologica(itens)                       # ciclo = Recusa, nada gravado
        _sincronizar_arestas(itens)
        recalcular(itens)
        _gravar_itens(itens, sorted(itens))
        gerar_textos(itens)
    return item


def adicionar_e_commitar(projeto: str, titulo: str, pergunta: str, opcoes,
                         midias=(), **kwargs) -> tuple[dict, str]:
    """`adicionar` + commit por caminho: o `adicionar --commit` da CLI.

    Quem mais registra no por aqui (o "Contestar" da Mesa de comando) usa a
    MESMA funcao, para o no nascer igual e com o mesmo commit.
    """
    item = adicionar(projeto, titulo, pergunta, opcoes, midias, **kwargs)
    with _trava():
        desfecho = commitar_por_caminho(
            *_tudo_para_commit(), f"decisão({item['projeto']}): nova — {item['titulo']}")
    return item, desfecho


def acrescentar_midias(item_id: str, midias, *, copiar: bool = False) -> dict:
    """Mais midia num no que ja existe (ex.: um lote novo de clipes).

    So acrescenta: a midia que ja estava continua no mesmo indice, entao o
    celular que tinha um bilhete aberto nao passa a ver outro arquivo.
    """
    with _trava():
        itens = carregar()
        item = itens.get(item_id)
        if item is None:
            raise KeyError(item_id)
        novas = _midias(midias, item_id, copiar)
        if not novas:
            raise Recusa("nenhuma mídia para acrescentar")
        item["midias"] = list(item.get("midias") or []) + novas
        _gravar_itens(itens, [item_id])
        gerar_textos(itens)
    return item


def semear(item_id: str, opcao: str, em: str, comentario: str = "",
           nota: str = "") -> dict:
    """Uma decisao que ele JA tomou antes da arvore existir (com a data)."""
    with _trava():
        itens = carregar()
        item = itens.get(item_id)
        if item is None:
            raise Recusa(f"decisão desconhecida: {item_id}")
        if opcao not in {o["id"] for o in item["opcoes"]}:
            raise Recusa(f"a decisão {item_id} não tem a opção {opcao}")
        registro = {"opcao": opcao, "comentario": comentario, "em": em,
                    "origem": "semente"}
        if nota:
            registro["nota"] = nota
        item["historico"].append(registro)
        item["vigente"] = {"opcao": opcao, "comentario": comentario, "em": em}
        item["situacao"] = "decidida"
        recalcular(itens)
        _gravar_itens(itens, sorted(itens))
        gerar_textos(itens)
    return item


def _rotulo_da_opcao(item: dict, opcao_id) -> str:
    if opcao_id == QUALQUER:
        return "decidida"
    return next((o["rotulo"] for o in item.get("opcoes") or []
                 if o["id"] == opcao_id), str(opcao_id))


def responder(item_id: str, opcao: str, comentario: str = "", *,
              aparelho: str = "", origem: str = "app",
              commitar: bool = True, esperava: str | None = None) -> dict:
    """Grava a resposta, recalcula a arvore, regenera os textos e commita.

    Devolve o evento, com `a_rever` (quem foi para "a rever") e `commit`
    ("ok", "nada" ou "falhou: ..."). O commit que falha NAO desfaz nada.

    `esperava` e a hora da resposta vigente que a TELA tinha ("" = nenhuma).
    Se a vigente mudou nesse meio-tempo (outra aba, outro aparelho, a Mesa),
    recusa: a tela estava velha, e ele nao viu o que vale agora.
    """
    comentario = str(comentario or "").strip()[:COMENTARIO_MAX]
    with _trava():
        itens = carregar()
        item = itens.get(item_id)
        if item is None:
            raise KeyError(item_id)
        if esperava is not None:
            atual = str((item.get("vigente") or {}).get("em") or "")
            if atual != str(esperava or ""):
                if atual:
                    rotulo = _rotulo_da_opcao(item, (item.get("vigente") or {}).get("opcao"))
                    agora_vale = (f"agora vale “{rotulo}” "
                                  f"(de {atual[:16].replace('T', ' ')})")
                else:
                    agora_vale = "agora ela está sem resposta"
                raise Recusa(f"essa decisão mudou enquanto a tela estava aberta: {agora_vale}. "
                             "Abri de novo com o que vale; responda outra vez se quiser.")
        faltam = [d for d in item.get("depende_de") or [] if not _satisfeita(d, itens)]
        if faltam:
            nomes = ", ".join(f"{itens[d['decisao']]['titulo']} = "
                              f"{_rotulo_da_opcao(itens[d['decisao']], d['opcao'])}"
                              for d in faltam if d["decisao"] in itens)
            raise Recusa(f"essa decisão está bloqueada: antes, {nomes}")
        escolhida = next((o for o in item["opcoes"] if o["id"] == opcao), None)
        if escolhida is None:
            raise Recusa("escolha uma das opções")
        if escolhida.get("pede_comentario") and not comentario:
            raise Recusa("essa opção pede um comentário")
        em = _agora()
        anterior = (item.get("vigente") or {}).get("opcao")
        registro = {"opcao": opcao, "comentario": comentario, "em": em,
                    "origem": origem}
        if aparelho:
            registro["aparelho"] = aparelho
        if anterior:
            registro["anterior"] = anterior
        item["historico"].append(registro)
        item["vigente"] = {"opcao": opcao, "comentario": comentario, "em": em}
        item["situacao"] = "decidida"
        a_rever = []
        if anterior and anterior != opcao:
            for outro in a_rever_se_mudar(itens, item_id):
                itens[outro]["situacao"] = "a_rever"
                a_rever.append(outro)
        recalcular(itens)
        _gravar_itens(itens, sorted(itens))
        evento = {"projeto": item["projeto"], "id": item_id,
                  "titulo": item["titulo"], "opcao": opcao,
                  "opcao_rotulo": escolhida["rotulo"], "comentario": comentario,
                  "em": em, "anterior": anterior, "a_rever": a_rever}
        caminho_eventos().parent.mkdir(parents=True, exist_ok=True)
        with open(caminho_eventos(), "ab") as fh:
            fh.write((json.dumps(evento, ensure_ascii=False) + "\n").encode("utf-8"))
            fh.flush()
            os.fsync(fh.fileno())
        gerar_textos(itens)
        evento["commit"] = "desligado"
        if commitar:
            mensagem = f"decisão({item['projeto']}): {item['titulo']} → {escolhida['rotulo']}"
            evento["commit"] = commitar_por_caminho(*_tudo_para_commit(), mensagem)
    return evento


def tirar_dependencia(item_id: str, decisao_id: str, nota: str, *,
                      commitar: bool = True) -> dict:
    """Uma aresta que nao devia existir sai da arvore.

    Caso de 28/09: `capacidade-pelo-app` dependia de `modo-de-trabalho` (=*),
    e trocar o modo mandou a regra da Mesa para "a rever", embora ela valha em
    qualquer modo. Sem a aresta, o no que foi para "a rever" SO por causa
    dela volta para "decidida" com a MESMA resposta (a `vigente` nao muda), e
    o historico ganha uma linha `origem: correcao` com a nota. Nada se apaga.
    Nao entra no `_eventos.jsonl`: nao e uma resposta do Adrian.
    """
    nota = str(nota or "").strip()
    if not nota:
        raise Recusa("diga por que a dependência sai (--nota)")
    with _trava():
        itens = carregar()
        item = itens.get(item_id)
        if item is None:
            raise KeyError(item_id)
        antes = list(item.get("depende_de") or [])
        item["depende_de"] = [d for d in antes if d.get("decisao") != decisao_id]
        if len(item["depende_de"]) == len(antes):
            raise Recusa(f"{item_id} não depende de {decisao_id}")
        _sincronizar_arestas(itens)
        situacao_antes = item.get("situacao")
        voltou = False
        if (situacao_antes == "a_rever" and item.get("vigente")
                and all(_satisfeita(d, itens) for d in item["depende_de"])):
            item["situacao"] = "decidida"
            vigente = item["vigente"]
            item["historico"].append({"opcao": vigente.get("opcao"),
                                      "comentario": vigente.get("comentario", ""),
                                      "em": _agora(), "origem": "correcao",
                                      "nota": nota[:COMENTARIO_MAX]})
            voltou = True
        recalcular(itens)
        _gravar_itens(itens, sorted(itens))
        gerar_textos(itens)
        saida = {"id": item_id, "tirou": decisao_id, "situacao": item["situacao"],
                 "voltou": voltou, "commit": "desligado"}
        if commitar:
            saida["commit"] = commitar_por_caminho(
                *_tudo_para_commit(),
                f"decisão({item['projeto']}): {item['titulo']} — deixa de depender "
                f"de {itens[decisao_id]['titulo'] if decisao_id in itens else decisao_id}")
    return saida


# ================================================================= o leitor
# Pedido do Adrian pela Mesa, 28/09/2026 21:50: "Quero que voce crie um
# leitor de decisoes tomadas, para saber se isso gera mais ramificacoes
# ainda". Cada resposta dele (uma linha do `_eventos.jsonl`) e LIDA pelo
# orquestrador, que registra o que ela gerou: uma tarefa da Mesa, um no novo
# (ramo) ou nada. O registro mora no proprio no, em `consequencias[]`, e vai
# para o git. "Lida" nao tem arquivo proprio: uma resposta esta lida quando o
# no dela tem uma consequencia de um evento igual ou mais novo (ler a ultima
# resposta cobre as anteriores, que ela substituiu).
TIPOS_DE_CONSEQUENCIA = ("tarefa", "no", "nada")
_ID_TAREFA = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")
NOTA_MAX = 500


def ler_eventos() -> list[dict]:
    """Toda linha do `_eventos.jsonl`, com `n` (a linha, de 1) e `chave`.

    Linha ilegivel volta como `{"n", "ilegivel": True}`: some calada, ela
    seria uma resposta dele que ninguem leu e ninguem ve.
    """
    try:
        bruto = caminho_eventos().read_bytes().decode("utf-8", errors="replace")
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise Recusa(f"_eventos.jsonl não pôde ser lido: {exc}") from exc
    eventos = []
    for n, linha in enumerate(bruto.splitlines(), start=1):
        if not linha.strip():
            continue
        try:
            evento = json.loads(linha)
        except ValueError:
            evento = None
        if not (isinstance(evento, dict) and evento.get("id") and evento.get("em")):
            eventos.append({"n": n, "ilegivel": True})
            continue
        evento["n"] = n
        evento["chave"] = f"{evento['id']}@{evento['em']}"
        eventos.append(evento)
    return eventos


def _cobre(consequencia: dict, evento: dict) -> bool:
    """A consequencia foi registrada lendo este evento ou um mais novo?

    Pela hora e, no mesmo segundo (o toque duplo de 28/09 19:57:42/43), pela
    linha do arquivo, que so cresce."""
    marca, em = str(consequencia.get("evento") or ""), str(evento.get("em"))
    if marca != em:
        return marca > em
    if not consequencia.get("linha"):     # as primeiras marcas (28/09 22:26) nao tinham
        return True
    return int(consequencia["linha"]) >= int(evento.get("n") or 0)


def _lida(evento: dict, itens: dict) -> bool:
    item = itens.get(evento.get("id")) or {}
    return any(_cobre(c, evento) for c in item.get("consequencias") or [])


def _sinais(evento: dict, itens: dict) -> dict:
    """(a) o que a opcao desbloqueia, (b) o que foi para "a rever", (c) se ha
    comentario livre, que so uma leitura (LLM) diz se vira tarefa ou ramo."""
    item = itens.get(evento.get("id")) or {}
    opcao = next((o for o in item.get("opcoes") or []
                  if o.get("id") == evento.get("opcao")), {})

    def nos(ids):
        return [{"id": i, "projeto": itens[i]["projeto"], "titulo": itens[i]["titulo"],
                 "situacao": itens[i].get("situacao")} if i in itens
                else {"id": i, "projeto": "", "titulo": i, "situacao": "sumiu"}
                for i in ids]

    comentario = str(evento.get("comentario") or "").strip()
    vigente = (item.get("vigente") or {}).get("opcao")
    return {"desbloqueia": nos(opcao.get("desbloqueia") or []),
            "a_rever": nos(evento.get("a_rever") or []),
            "comentario": comentario,
            "precisa_de_leitura": bool(comentario),
            "existe": bool(item),
            "ainda_vale": bool(item) and vigente == evento.get("opcao")}


def leitor(*, todos: bool = False, projeto: str | None = None,
           itens: dict | None = None) -> list[dict]:
    """As respostas ainda nao lidas (ou todas), da mais velha para a mais nova."""
    itens = carregar() if itens is None else itens
    saida = []
    for evento in ler_eventos():
        if evento.get("ilegivel"):
            saida.append(dict(evento, lida=False))
            continue
        if projeto and evento.get("projeto") != projeto:
            continue
        lida = _lida(evento, itens)
        if lida and not todos:
            continue
        registro = dict(evento, lida=lida, **_sinais(evento, itens))
        if todos:
            registro["consequencias"] = [
                c for c in (itens.get(evento["id"]) or {}).get("consequencias") or []
                if c.get("evento") == evento["em"]
                and int(c.get("linha") or evento["n"]) == evento["n"]]
        saida.append(registro)
    return saida


def nao_lidas_por_no(itens: dict | None = None) -> dict:
    """{id do no: quantas respostas dele ainda nao foram lidas}."""
    itens = carregar() if itens is None else itens
    contagem: dict = {}
    for evento in ler_eventos():
        if evento.get("ilegivel") or _lida(evento, itens):
            continue
        contagem[evento["id"]] = contagem.get(evento["id"], 0) + 1
    return contagem


def achar_evento(ref: str, eventos: list[dict] | None = None) -> dict:
    """`N` ou `#N` (a linha), `id@em` ou `[projeto/]id` (a ULTIMA resposta dele)."""
    eventos = ler_eventos() if eventos is None else eventos
    ref = str(ref or "").strip()
    validos = [e for e in eventos if not e.get("ilegivel")]
    if re.fullmatch(r"#?\d+", ref):
        n = int(ref.lstrip("#"))
        achado = next((e for e in eventos if e["n"] == n), None)
        if achado is None:
            raise Recusa(f"o _eventos.jsonl não tem a linha {n}")
        if achado.get("ilegivel"):
            raise Recusa(f"a linha {n} do _eventos.jsonl está ilegível")
        return achado
    if "@" in ref:
        achado = next((e for e in validos if e["chave"] == ref), None)
        if achado is None:
            raise Recusa(f"nenhuma resposta {ref}")
        return achado
    projeto, _, item_id = ref.rpartition("/")
    dele = [e for e in validos if e["id"] == item_id
            and (not projeto or e.get("projeto") == projeto)]
    if not dele:
        raise Recusa(f"nenhuma resposta de {ref} no _eventos.jsonl")
    return dele[-1]


def _consequencia(bruta: str) -> tuple[str, str]:
    """"tarefa:<id>", "no:<projeto/id>" ou "nada" -> (tipo, alvo)."""
    tipo, _, alvo = str(bruta or "").strip().partition(":")
    tipo, alvo = tipo.strip().lower(), alvo.strip()
    if tipo == "nada" and not alvo:
        return "nada", ""
    if tipo == "tarefa" and _ID_TAREFA.fullmatch(alvo):
        return "tarefa", alvo
    if tipo == "no" and alvo:
        return "no", alvo
    raise Recusa(f"--gerou inválido: {bruta!r} (tarefa:<id>, no:<projeto/id> ou nada)")


def marcar(ref: str, gerou, nota: str = "", *, origem: str = "leitor",
           commitar: bool = True) -> dict:
    """Registra o que uma resposta gerou e a marca como lida.

    `no:X` liga o ramo X a esta resposta por `depende_de` (decisao + a opcao
    que ele escolheu), se ainda nao estiver ligado: o ramo nasce da resposta,
    e trocar a resposta manda o ramo para "a rever". So liga a uma resposta
    que ainda vale. Repetir a mesma marca nao duplica nada.
    """
    pedidos = [_consequencia(g) for g in (gerou or [])]
    if not pedidos:
        raise Recusa("diga o que a resposta gerou: --gerou tarefa:<id>|no:<projeto/id>|nada")
    if any(t == "nada" for t, _ in pedidos) and len(pedidos) > 1:
        raise Recusa("“nada” não combina com tarefa ou nó")
    nota = " ".join(str(nota or "").split())[:NOTA_MAX]
    with _trava():
        itens = carregar()
        evento = achar_evento(ref)
        item = itens.get(evento["id"])
        if item is None:
            raise Recusa(f"a decisão {evento['id']} não existe mais")
        consequencias = list(item.get("consequencias") or [])
        ja = {(c.get("evento"), int(c.get("linha") or 0), c.get("tipo"), c.get("alvo"))
              for c in consequencias}
        ligados, novas = [], []
        for tipo, alvo in pedidos:
            if tipo == "no":
                projeto, _, filho_id = alvo.rpartition("/")
                filho = itens.get(filho_id)
                if filho is None or (projeto and filho["projeto"] != projeto):
                    raise Recusa(f"o nó {alvo} não existe (crie antes com `adicionar`)")
                if filho_id == item["id"]:
                    raise Recusa("uma resposta não gera ela mesma")
                alvo = f"{filho['projeto']}/{filho_id}"
                if not any(d.get("decisao") == item["id"]
                           for d in filho.get("depende_de") or []):
                    if (item.get("vigente") or {}).get("opcao") != evento["opcao"]:
                        raise Recusa(
                            f"essa resposta de {item['id']} não vale mais (a vigente é "
                            f"{_rotulo_da_opcao(item, (item.get('vigente') or {}).get('opcao'))});"
                            " ligue o ramo à resposta atual")
                    filho["depende_de"] = list(filho.get("depende_de") or []) + [
                        {"decisao": item["id"], "opcao": evento["opcao"]}]
                    ligados.append(filho_id)
            chave = (evento["em"], evento["n"], tipo, alvo)
            if chave in ja:
                continue
            ja.add(chave)
            novas.append({"alvo": alvo, "em": _agora(), "evento": evento["em"],
                          "linha": evento["n"], "nota": nota, "opcao": evento["opcao"],
                          "origem": origem, "tipo": tipo})
        if ligados:
            _topologica(itens)                  # ciclo = Recusa, nada gravado
            _sincronizar_arestas(itens)
            recalcular(itens)
        item["consequencias"] = consequencias + novas
        _gravar_itens(itens, sorted(itens))
        gerar_textos(itens)
        saida = {"evento": evento, "novas": novas, "ligados": ligados,
                 "commit": "desligado"}
        if commitar and (novas or ligados):
            resumo = ", ".join(("nada" if c["tipo"] == "nada" else
                                f"{'tarefa' if c['tipo'] == 'tarefa' else 'nó'} {c['alvo']}")
                               for c in novas) or "ramos ligados"
            saida["commit"] = commitar_por_caminho(
                *_tudo_para_commit(),
                f"decisão({item['projeto']}): lida — {item['titulo']} gerou {resumo}"[:200])
        elif commitar:
            saida["commit"] = "nada"
    return saida


def _tarefas_da_mesa() -> tuple[dict, str]:
    """({id: situacao da tarefa}, erro). A Mesa ilegivel NAO vira "nenhuma"."""
    try:
        from . import orquestrador
        return orquestrador.situacao_das_tarefas(), ""
    except Exception as exc:                                  # noqa: BLE001
        return {}, f"a Mesa não pôde ser lida: {exc}"[:200]


def consequencias_para_o_app(item: dict, itens: dict, tarefas: dict,
                             erro_da_mesa: str = "") -> list[dict]:
    saida = []
    for c in item.get("consequencias") or []:
        publico = {k: c.get(k) for k in ("tipo", "alvo", "nota", "em", "evento", "linha",
                                          "opcao", "origem")}
        publico["opcao_rotulo"] = _rotulo_da_opcao(item, c.get("opcao"))
        if c.get("tipo") == "tarefa":
            achada = tarefas.get(c.get("alvo"))
            publico["tarefa"] = achada or {
                "situacao": "sem_leitura" if erro_da_mesa else "desconhecida",
                "titulo": "", "parte": ""}
        elif c.get("tipo") == "no":
            filho_id = str(c.get("alvo") or "").rpartition("/")[2]
            filho = itens.get(filho_id)
            publico["no"] = ({"id": filho_id, "titulo": filho["titulo"],
                              "projeto": filho["projeto"],
                              "situacao": filho.get("situacao"), "existe": True}
                             if filho else {"id": filho_id, "titulo": filho_id,
                                            "projeto": "", "situacao": None,
                                            "existe": False})
        saida.append(publico)
    return saida


# ================================================================ textos
def _data(em) -> str:
    texto = str(em or "")
    try:
        return datetime.fromisoformat(texto).strftime("%d/%m/%Y")
    except ValueError:
        return texto[:10]


def _linha(item: dict, itens: dict) -> str:
    icone = ICONES.get(item.get("situacao"), "•")
    texto = f"{icone} **{item['titulo']}**"
    vigente = item.get("vigente")
    if vigente:
        texto += f" — {_rotulo_da_opcao(item, vigente['opcao'])} ({_data(vigente.get('em'))})"
        if vigente.get("comentario"):
            texto += f" · “{vigente['comentario']}”"
    elif item.get("pergunta"):
        texto += f" — {item['pergunta']}"
    faltam = [d for d in item.get("depende_de") or [] if not _satisfeita(d, itens)]
    if faltam and item.get("situacao") in ("bloqueada", "a_rever"):
        texto += " · espera " + ", ".join(
            f"{itens[d['decisao']]['titulo']} = "
            f"{_rotulo_da_opcao(itens[d['decisao']], d['opcao'])}"
            for d in faltam if d["decisao"] in itens)
    return texto + f" `{item['id']}`"


def arvore_em_texto(itens: dict, projeto: str) -> list[str]:
    """A arvore do projeto, com indentacao. Cada no aparece uma vez."""
    do_projeto = {k: v for k, v in itens.items() if v["projeto"] == projeto}
    filhos: dict = {}
    raizes = []
    for item_id, item in sorted(do_projeto.items(), key=lambda kv: kv[1]["criado"]):
        pais = [d["decisao"] for d in item.get("depende_de") or []
                if d.get("decisao") in do_projeto]
        if pais:
            filhos.setdefault(pais[0], []).append(item_id)
        else:
            raizes.append(item_id)
    linhas, vistos = [], set()

    def descer(item_id, nivel):
        if item_id in vistos:
            return
        vistos.add(item_id)
        linhas.append("  " * nivel + "- " + _linha(itens[item_id], itens))
        for filho in filhos.get(item_id, []):
            descer(filho, nivel + 1)

    for raiz in raizes:
        descer(raiz, 0)
    for resto in sorted(set(do_projeto) - vistos):
        descer(resto, 0)
    return linhas


def _readme(itens: dict, projeto: str) -> str:
    linhas = [f"# Decisões — {ROTULOS[projeto]}", "",
              "Gerado por `remoto/decisoes.py` a cada resposta. Não edite à mão:",
              "a fonte são os `<id>.json` desta pasta.", "",
              "Legenda: ✅ decidida · ⏳ pendente · 🔒 bloqueada · ↺ a rever", ""]
    arvore = arvore_em_texto(itens, projeto)
    linhas += arvore or ["_Nenhuma decisão ainda._"]
    return "\n".join(linhas) + "\n"


def bloco_da_sessao(itens: dict, parte: str) -> str:
    """O bloco que entra no doc da sessao: as gerais e as da parte."""
    def da(projeto, situacoes):
        return [i for i in sorted(itens.values(), key=lambda i: i["criado"])
                if i["projeto"] == projeto and i.get("situacao") in situacoes]

    linhas = [INICIO,
              "## Decisões do Adrian (gerado — não edite à mão)", "",
              f"Fonte: `decisoes/{parte}/` e `decisoes/geral/`. **Decisão vigente "
              "do Adrian manda.** Para mudar uma, ele usa a tela Decisões do app.", ""]
    for projeto in ("geral", parte):
        vigentes = da(projeto, ("decidida",))
        esperando = da(projeto, ("pendente", "a_rever"))
        bloqueadas = da(projeto, ("bloqueada",))
        if not (vigentes or esperando or bloqueadas):
            continue
        linhas.append(f"**{ROTULOS[projeto]}**")
        linhas += ["- " + _linha(i, itens) for i in vigentes]
        linhas += ["- " + _linha(i, itens) for i in esperando]
        if bloqueadas:
            linhas.append(f"- 🔒 {len(bloqueadas)} bloqueada(s), esperando outra "
                          f"decisão: ver `decisoes/{projeto}/README.md`")
        linhas.append("")
    linhas.append(FIM)
    return "\n".join(linhas)


def _trocar_bloco(texto: str, bloco: str, nl: str) -> str:
    bloco = bloco.replace("\n", nl)
    if INICIO in texto and FIM in texto:
        antes, _, resto = texto.partition(INICIO)
        _, _, depois = resto.partition(FIM)
        return antes + bloco + depois
    # Sem marcas: o bloco entra logo depois do titulo (a primeira linha).
    primeira, sep, resto = texto.partition(nl)
    return primeira + sep + nl + bloco + nl + resto


def gerar_textos(itens: dict | None = None) -> dict:
    """Regenera os READMEs dos projetos e os blocos das sessoes.

    Devolve {"readmes": [...], "sessoes": [...]} so com o que MUDOU.
    """
    itens = carregar() if itens is None else itens
    mudou = {"readmes": [], "sessoes": []}
    for projeto in PROJETOS:
        if not any(i["projeto"] == projeto for i in itens.values()):
            continue
        alvo = pasta() / projeto / "README.md"
        novo = _readme(itens, projeto).encode("utf-8")
        try:
            if alvo.read_bytes() == novo:
                continue
        except OSError:
            pass
        _gravar_bytes(alvo, novo)
        mudou["readmes"].append(alvo)
    for parte in PROJETOS:
        alvo = pasta_sessoes() / f"{parte}.md"
        if parte == "geral" or not alvo.is_file():
            continue
        bruto = alvo.read_bytes().decode("utf-8")
        nl = "\r\n" if "\r\n" in bruto else "\n"
        novo = _trocar_bloco(bruto, bloco_da_sessao(itens, parte), nl)
        if novo != bruto:
            _gravar_bytes(alvo, novo.encode("utf-8"))
            mudou["sessoes"].append(alvo)
    return mudou


# ================================================================== git
def _git(*args, entrada: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo()), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          input=entrada, timeout=60,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _relativo(caminho: Path) -> str:
    return Path(caminho).resolve().relative_to(repo().resolve()).as_posix()


def _so_o_bloco_mudou(caminho: Path) -> bool:
    """O doc da sessao difere do HEAD SO dentro do bloco de decisoes?

    Se tiver outra mudanca por commitar (de outro agente), commitar o arquivo
    levaria a mudanca dele junto, com a mensagem de uma decisao.
    """
    rel = _relativo(caminho)
    feito = _git("show", f"HEAD:{rel}")
    atual = caminho.read_bytes().decode("utf-8").replace("\r\n", "\n")
    if feito.returncode != 0:
        return False
    no_head = feito.stdout.replace("\r\n", "\n")

    def sem_bloco(texto):
        if INICIO in texto and FIM in texto:
            antes, _, resto = texto.partition(INICIO)
            texto = antes + resto.partition(FIM)[2]
        return re.sub(r"\n{3,}", "\n\n", texto).strip()
    return sem_bloco(no_head) == sem_bloco(atual)


def _tudo_para_commit() -> tuple:
    """(arquivos, docs das sessoes): TUDO o que a arvore escreve.

    O commit filtra pelo que mudou. Passar tudo faz o commit que falhou
    antes (index.lock, disco) ir junto com a proxima resposta.
    """
    arquivos = sorted(pasta().glob("*/*.json")) + sorted(pasta().glob("*/README.md"))
    if caminho_eventos().is_file():
        arquivos.append(caminho_eventos())
    sessoes = [pasta_sessoes() / f"{p}.md" for p in PROJETOS
               if (pasta_sessoes() / f"{p}.md").is_file()]
    return arquivos, sessoes


def commitar_por_caminho(caminhos, sessoes, mensagem: str) -> str:
    """`git commit -- <caminhos>`, nunca -a nem add ".". Devolve o desfecho."""
    try:
        if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
            return "falhou: não é um repositório git"
        alvos = [_relativo(c) for c in caminhos]
        pulados = []
        for doc in sessoes:
            if _so_o_bloco_mudou(doc):
                alvos.append(_relativo(doc))
            else:
                pulados.append(_relativo(doc))
        alvos = sorted(set(alvos))
        if not alvos:
            return "nada"
        mudados = _git("status", "--porcelain", "--untracked-files=all", "--", *alvos)
        alvos = sorted({linha[3:].strip().strip('"') for linha in
                        mudados.stdout.splitlines() if linha.strip()} & set(alvos))
        if not alvos:
            return "nada"
        ultimo = ""
        for vez in range(TENTATIVAS_DE_COMMIT):
            # Arquivo novo precisa de `add` (so ele, por caminho) antes do
            # commit; o `add` tambem esbarra no index.lock, e entra na mesma
            # nova tentativa.
            ultimo = ""
            novos = _git("ls-files", "--others", "--exclude-standard", "--", *alvos)
            for novo in novos.stdout.splitlines():
                adicionado = _git("add", "--", novo.strip())
                if adicionado.returncode != 0:
                    ultimo = (adicionado.stderr or adicionado.stdout).strip()
                    break
            if not ultimo:
                feito = _git("commit", "-q", "-m", mensagem, "--", *alvos)
                if feito.returncode == 0:
                    return "ok" + (f" (sem o bloco de: {', '.join(pulados)}, que tem "
                                   "outras mudanças por commitar)" if pulados else "")
                ultimo = (feito.stderr or feito.stdout).strip()
            if "index.lock" not in ultimo:
                break
            time.sleep(1.0 + vez)
        return f"falhou: {ultimo[:200]}"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return f"falhou: {type(exc).__name__}: {exc}"


# ============================================================ para o app
def _publico(item: dict, itens: dict, leitura: dict | None = None) -> dict:
    """O item como o celular o ve: SEM caminho de arquivo.

    `leitura` = {"nao_lidas": {...}, "tarefas": {...}, "erro_da_mesa": ""}:
    o que o leitor sabe (lida ou nao, e o que a resposta gerou)."""
    leitura = leitura or {"nao_lidas": {}, "tarefas": {}, "erro_da_mesa": ""}
    midias = []
    for n, m in enumerate(item.get("midias") or []):
        caminho = resolver_caminho(m.get("caminho", ""))
        midias.append({"indice": n, "rotulo": m.get("rotulo", ""),
                       "nome": caminho.name, "tipo": tipo_da_midia(caminho),
                       "existe": caminho.is_file()})
    vigente = dict(item["vigente"]) if item.get("vigente") else None
    if vigente:
        vigente["opcao_rotulo"] = _rotulo_da_opcao(item, vigente["opcao"])
    historico = [dict(h, opcao_rotulo=_rotulo_da_opcao(item, h.get("opcao")))
                 for h in item.get("historico") or []]
    for h in historico:
        h.pop("aparelho", None)
    return {"id": item["id"], "projeto": item["projeto"], "titulo": item["titulo"],
            "pergunta": item.get("pergunta", ""), "contexto": item.get("contexto", ""),
            "midias": midias,
            "opcoes": [{k: o.get(k) for k in ("id", "rotulo", "descricao",
                                                "desbloqueia", "pede_comentario")}
                       for o in item.get("opcoes") or []],
            "comentario": bool(item.get("comentario", True)),
            "depende_de": [{"decisao": d["decisao"], "opcao": d["opcao"],
                            "titulo": itens.get(d["decisao"], {}).get("titulo", d["decisao"]),
                            "opcao_rotulo": _rotulo_da_opcao(itens.get(d["decisao"], {}),
                                                             d["opcao"]),
                            "ok": _satisfeita(d, itens)}
                           for d in item.get("depende_de") or []],
            "situacao": item.get("situacao"), "vigente": vigente,
            "historico": historico,
            "a_rever_se_mudar": [{"id": d, "titulo": itens[d]["titulo"]}
                                 for d in a_rever_se_mudar(itens, item["id"])],
            "nao_lidas": leitura["nao_lidas"].get(item["id"], 0),
            "consequencias": consequencias_para_o_app(item, itens, leitura["tarefas"],
                                                      leitura["erro_da_mesa"]),
            "criado": item.get("criado")}


def para_o_app() -> dict:
    itens = carregar()
    nao_lidas = nao_lidas_por_no(itens)
    tarefas, erro_da_mesa = ({}, "")
    if any(c.get("tipo") == "tarefa" for i in itens.values()
           for c in i.get("consequencias") or []):
        tarefas, erro_da_mesa = _tarefas_da_mesa()
    leitura = {"nao_lidas": nao_lidas, "tarefas": tarefas, "erro_da_mesa": erro_da_mesa}
    ilegiveis = sum(1 for e in ler_eventos() if e.get("ilegivel"))
    projetos = []
    for projeto in PROJETOS:
        dele = [i for i in itens.values() if i["projeto"] == projeto]
        contagem = {s: sum(1 for i in dele if i.get("situacao") == s) for s in SITUACOES}
        contagem["nao_lidas"] = sum(nao_lidas.get(i["id"], 0) for i in dele)
        projetos.append({"id": projeto, "rotulo": ROTULOS[projeto], "contagem": contagem})
    return {"projetos": projetos,
            "arvores": {p: _arvore_para_o_app(itens, p) for p in PROJETOS},
            "itens": {k: _publico(v, itens, leitura) for k, v in itens.items()},
            "leitor": {"nao_lidas": sum(nao_lidas.values()),
                       "eventos_ilegiveis": ilegiveis, "erro_da_mesa": erro_da_mesa}}


def _arvore_para_o_app(itens: dict, projeto: str) -> list[dict]:
    """[{id, nivel}] na ordem da arvore (a mesma do README)."""
    do_projeto = {k: v for k, v in itens.items() if v["projeto"] == projeto}
    filhos: dict = {}
    raizes = []
    for item_id, item in sorted(do_projeto.items(), key=lambda kv: kv[1]["criado"]):
        pais = [d["decisao"] for d in item.get("depende_de") or []
                if d.get("decisao") in do_projeto]
        (filhos.setdefault(pais[0], []) if pais else raizes).append(item_id)
    saida, vistos = [], set()

    def descer(item_id, nivel):
        if item_id in vistos:
            return
        vistos.add(item_id)
        saida.append({"id": item_id, "nivel": nivel})
        for filho in filhos.get(item_id, []):
            descer(filho, nivel + 1)

    for raiz in raizes:
        descer(raiz, 0)
    for resto in sorted(set(do_projeto) - vistos):
        descer(resto, 0)
    return saida


def midia(item_id: str, indice: int) -> tuple | None:
    """(caminho, tipo) da midia `indice` do item, conferida agora, ou None."""
    try:
        item = carregar().get(item_id)
    except Recusa:
        return None
    if item is None:
        return None
    midias = item.get("midias") or []
    if not isinstance(indice, int) or not 0 <= indice < len(midias):
        return None
    caminho = resolver_caminho(midias[indice].get("caminho", ""))
    tipo = tipo_da_midia(caminho)
    if tipo is None or not caminho.is_file():
        return None
    return caminho, tipo


def texto_do_aviso(evento: dict) -> str:
    """O que vai ao Telegram quando ele responde."""
    texto = f"🗳 Adrian decidiu: {evento['titulo']} → {evento['opcao_rotulo']}"
    if evento.get("comentario"):
        texto += f"\n“{evento['comentario'][:500]}”"
    if evento.get("a_rever"):
        texto += f"\n↺ foram para \"a rever\": {', '.join(evento['a_rever'])}"
    if str(evento.get("commit", "")).startswith("falhou"):
        texto += f"\n⚠ o commit ficou para depois ({evento['commit'][:150]})"
    return texto


# ==================================================================== cli
def _imprimir_leitor(lista: list[dict], todos: bool) -> None:
    def nomes(nos):
        return ", ".join(f"{n['projeto']}/{n['id']} [{n['situacao']}]" for n in nos) or "nada"

    for ev in lista:
        if ev.get("ilegivel"):
            print(f"#{ev['n']}  LINHA ILEGÍVEL no _eventos.jsonl (leia à mão)")
            print()
            continue
        quando = str(ev.get("em", ""))[5:16].replace("T", " ")
        marca = "lida" if ev.get("lida") else "NÃO LIDA"
        print(f"#{ev['n']}  {ev['projeto']}/{ev['id']}  {quando}  [{marca}]")
        troca = (f" (antes: {ev['anterior']})"
                 if ev.get("anterior") and ev["anterior"] != ev.get("opcao") else "")
        print(f"    {ev.get('titulo')} → {ev.get('opcao_rotulo')}{troca}")
        if not ev.get("existe"):
            print("    ⚠ o nó não existe mais")
        elif not ev.get("ainda_vale"):
            print("    ⚠ esta resposta já foi trocada por outra")
        print(f"    (a) desbloqueia: {nomes(ev.get('desbloqueia') or [])}")
        print(f"    (b) a rever: {nomes(ev.get('a_rever') or [])}")
        if ev.get("precisa_de_leitura"):
            print(f"    (c) COMENTÁRIO — precisa de leitura: “{ev['comentario']}”")
        else:
            print("    (c) sem comentário")
        for c in ev.get("consequencias") or []:
            print(f"    gerou: {c['tipo']} {c.get('alvo') or ''}"
                  + (f" — {c['nota']}" if c.get("nota") else ""))
        print()
    if not lista:
        print("todas as respostas foram lidas" if not todos else "nenhuma resposta ainda")
    else:
        faltam = sum(1 for e in lista if not e.get("lida"))
        print(f"{faltam} não lida(s). Marque com: python -m remoto.decisoes leitor marcar "
              "<N> --gerou tarefa:<id>|no:<projeto/id>|nada [--nota N]")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m remoto.decisoes",
                                     description="a árvore de decisões do Adrian")
    sub = parser.add_subparsers(dest="comando", required=True)
    add = sub.add_parser("adicionar", help="registra uma decisão")
    add.add_argument("--projeto", required=True, choices=PROJETOS)
    add.add_argument("--titulo", required=True)
    add.add_argument("--pergunta", default="")
    add.add_argument("--contexto", default="")
    add.add_argument("--opcao", action="append", default=[],
                     help='"rótulo", "rótulo|descrição" ou "id=rótulo|descrição"')
    add.add_argument("--midia", action="append", default=[],
                     help='"caminho" ou "caminho|RÓTULO" (repita)')
    add.add_argument("--copiar", action="store_true",
                     help="copia a mídia para %%LOCALAPPDATA%%/neural-fights/decisoes_midia")
    add.add_argument("--depende", action="append", default=[],
                     help='"decisao=opcao" (repita)')
    add.add_argument("--sem-comentario", action="store_true")
    add.add_argument("--id", default=None)
    add.add_argument("--commit", action="store_true", help="commita por caminho")
    lista = sub.add_parser("listar")
    lista.add_argument("--projeto", choices=PROJETOS)
    lista.add_argument("--situacao", choices=SITUACOES)
    resp = sub.add_parser("responder")
    resp.add_argument("id")
    resp.add_argument("opcao")
    resp.add_argument("--comentario", default="")
    resp.add_argument("--sem-commit", action="store_true")
    mid = sub.add_parser("midia", help="acrescenta mídia a uma decisão que já existe")
    mid.add_argument("id")
    mid.add_argument("--midia", action="append", default=[], required=True,
                     help='"caminho" ou "caminho|RÓTULO" (repita)')
    mid.add_argument("--copiar", action="store_true")
    mid.add_argument("--commit", action="store_true", help="commita por caminho")
    dep = sub.add_parser("tirar-dependencia",
                         help="tira uma aresta errada (a resposta vigente fica)")
    dep.add_argument("id")
    dep.add_argument("decisao", help="a decisão da qual ela deixa de depender")
    dep.add_argument("--nota", required=True, help="por que a aresta sai")
    dep.add_argument("--sem-commit", action="store_true")
    arv = sub.add_parser("arvore")
    arv.add_argument("--projeto", choices=PROJETOS)
    sub.add_parser("gerar", help="regenera os READMEs e os blocos das sessões")
    sub.add_parser("onde")
    lei = sub.add_parser("leitor", help="as respostas ainda não lidas, e o que geraram")
    lei.add_argument("--todos", action="store_true", help="também as já lidas")
    lei.add_argument("--projeto", choices=PROJETOS)
    lei.add_argument("--json", action="store_true")
    lsub = lei.add_subparsers(dest="acao")
    mar = lsub.add_parser("marcar", help="registra o que uma resposta gerou e a marca lida")
    mar.add_argument("evento", help="N (a linha), id@em ou [projeto/]id (a última dele)")
    mar.add_argument("--gerou", action="append", default=[], required=True,
                     help="tarefa:<id da Mesa> | no:<projeto/id> | nada (repita)")
    mar.add_argument("--nota", default="")
    mar.add_argument("--origem", default="leitor", choices=("leitor", "semente"))
    mar.add_argument("--sem-commit", action="store_true")
    args = parser.parse_args(argv)
    # Quem le esta saida (o orquestrador) le por pipe: no Windows seria cp1252,
    # e um emoji da arvore derrubava o `arvore` com UnicodeEncodeError.
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    try:
        if args.comando == "adicionar":
            opcoes = dict(id=args.id, contexto=args.contexto,
                          comentario=not args.sem_comentario,
                          depende_de=args.depende, copiar=args.copiar)
            if args.commit:
                item, desfecho = adicionar_e_commitar(
                    args.projeto, args.titulo, args.pergunta, args.opcao, args.midia,
                    **opcoes)
            else:
                item = adicionar(args.projeto, args.titulo, args.pergunta, args.opcao,
                                 args.midia, **opcoes)
            print(f"registrada: {item['projeto']}/{item['id']} [{item['situacao']}]")
            if args.commit:
                print("commit:", desfecho)
            return 0
        if args.comando == "midia":
            item = acrescentar_midias(args.id, args.midia, copiar=args.copiar)
            print(f"{item['projeto']}/{item['id']}: {len(item['midias'])} mídia(s)")
            if args.commit:
                with _trava():
                    print("commit:", commitar_por_caminho(
                        *_tudo_para_commit(),
                        f"decisão({item['projeto']}): mais mídia — {item['titulo']}"))
            return 0
        if args.comando == "listar":
            itens = carregar()
            achados = [i for i in sorted(itens.values(),
                                         key=lambda i: (i["projeto"], i["criado"]))
                       if (not args.projeto or i["projeto"] == args.projeto)
                       and (not args.situacao or i["situacao"] == args.situacao)]
            for i in achados:
                print(f"{i['projeto']:<14} {i['situacao']:<10} {i['id']}  {i['titulo']}")
            if not achados:
                print("nada aqui")
            return 0
        if args.comando == "responder":
            evento = responder(args.id, args.opcao, args.comentario, origem="cli",
                               commitar=not args.sem_commit)
            print(f"{evento['titulo']} → {evento['opcao_rotulo']} "
                  f"(a rever: {evento['a_rever'] or 'nada'}; commit: {evento['commit']})")
            return 0
        if args.comando == "tirar-dependencia":
            feito = tirar_dependencia(args.id, args.decisao, args.nota,
                                      commitar=not args.sem_commit)
            print(f"{feito['id']}: não depende mais de {feito['tirou']} · "
                  f"{feito['situacao']}{' (voltou a valer)' if feito['voltou'] else ''}"
                  f" · commit: {feito['commit']}")
            return 0
        if args.comando == "arvore":
            itens = carregar()
            for projeto in ([args.projeto] if args.projeto else PROJETOS):
                linhas = arvore_em_texto(itens, projeto)
                if linhas:
                    print(f"# {ROTULOS[projeto]}")
                    print("\n".join(linhas))
                    print()
            return 0
        if args.comando == "leitor":
            if args.acao == "marcar":
                feito = marcar(args.evento, args.gerou, args.nota, origem=args.origem,
                               commitar=not args.sem_commit)
                ev = feito["evento"]
                print(f"#{ev['n']} {ev['projeto']}/{ev['id']} lida · "
                      f"{len(feito['novas'])} consequência(s) nova(s)"
                      + (f" · ramos ligados: {', '.join(feito['ligados'])}"
                         if feito["ligados"] else "")
                      + f" · commit: {feito['commit']}")
                return 0
            lista = leitor(todos=args.todos, projeto=args.projeto)
            if args.json:
                print(json.dumps(lista, ensure_ascii=False, indent=2))
                return 0
            _imprimir_leitor(lista, args.todos)
            return 0
        if args.comando == "gerar":
            textos = gerar_textos()
            print(f"READMEs: {len(textos['readmes'])} · sessões: {len(textos['sessoes'])}")
            return 0
        print(f"decisões:  {pasta()}")
        print(f"eventos:   {caminho_eventos()}")
        print(f"mídia local: {pasta_midia_local()}")
        return 0
    except KeyError as exc:
        print(f"decisão desconhecida: {exc}", file=sys.stderr)
        return 1
    except Recusa as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
