# -*- coding: utf-8 -*-
"""O interruptor do Claude: liberado ou proibido, num arquivo so.

Pedido do Adrian (29/09/2026, 13:4x): "agora depois dessa interacao usar o
Claude esta proibido ate segunda ordem, crie algo no app para ligar e
desligar isso."

"Usar o Claude" e tudo que chama o Claude Code sozinho:
  - a sonda de uso do servidor do app (`claude.exe -p ok --model haiku`);
  - o apurador do bot (`claude -p` para diagnosticar e propor conserto);
  - o orquestrador: `agente-inicio` (dispara agente) e o `esperar` (cada
    vez que ele sai, a sessao principal acorda, e acordar e uso).
O carteiro das IAs (`ias/`) abre navegador, nao o Claude: fica de fora.

O ESTADO e um arquivo so, `%LOCALAPPDATA%\\neural-fights\\claude.json`:

    {"liberado": false, "em": "2026-09-29T14:02:11", "por": "app 614c026b",
     "motivo": "até segunda ordem"}

com escrita atomica e toda mudanca anexada em `claude_historico.jsonl`.

  - Arquivo AUSENTE = liberado (e como tudo funcionava antes dele), mas a
    leitura diz `origem: "sem_arquivo"`, e a primeira vez fica registrada
    no historico: a tela nao afirma "liberado pelo Adrian" sem ele ter dito.
  - Arquivo ILEGIVEL = PROIBIDO. A regra do app e falhar fechado: tratar
    ilegivel como liberado soltaria agente num estado que ninguem sabe ler.

Quem obedece le a cada vez (nada guardado em memoria): o app grava e, no
proximo passo, a sonda, o apurador e o orquestrador ja veem.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

ARQUIVO = None                 # os testes apontam para outro lugar
MOTIVO_MAX = 300


def _pasta() -> Path:
    # NF_CLAUDE_ESTADO: a instancia de teste (8934) usa um arquivo proprio.
    # NEURAL_FIGHTS_RUNTIME_DIR: o pytest (conftest.py da raiz) e o testar.py
    # isolam o runtime; um teste avulso nunca le o interruptor de verdade.
    if os.environ.get("NEURAL_FIGHTS_RUNTIME_DIR"):
        return Path(os.environ["NEURAL_FIGHTS_RUNTIME_DIR"])
    from .config import runtime_dir
    return runtime_dir()


def caminho() -> Path:
    if ARQUIVO:
        return Path(ARQUIVO)
    if os.environ.get("NF_CLAUDE_ESTADO"):
        return Path(os.environ["NF_CLAUDE_ESTADO"])
    return _pasta() / "claude.json"


def caminho_historico() -> Path:
    alvo = caminho()
    return alvo.with_name(alvo.stem + "_historico.jsonl")


def _agora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hhmm(iso) -> str:
    try:
        return datetime.fromisoformat(str(iso)).strftime("%H:%M")
    except ValueError:
        return "?"


def _quando(iso) -> str:
    """"14:02" hoje; "28/09 14:02" em outro dia."""
    try:
        momento = datetime.fromisoformat(str(iso))
    except ValueError:
        return "?"
    if momento.date() == datetime.now().date():
        return momento.strftime("%H:%M")
    return momento.strftime("%d/%m %H:%M")


def _anexar(linha: dict) -> None:
    alvo = caminho_historico()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    with open(alvo, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def ler() -> dict:
    """O estado como vale agora. Nunca levanta.

    Chaves: `liberado`, `em`, `por`, `motivo`, `origem` ("arquivo",
    "sem_arquivo" ou "ilegivel") e `texto` (a frase para a tela).
    """
    alvo = caminho()
    try:
        bruto = alvo.read_text(encoding="utf-8")
    except FileNotFoundError:
        _registrar_ausencia()
        return _com_texto({"liberado": True, "em": None, "por": "", "motivo": "",
                           "origem": "sem_arquivo"})
    except OSError as exc:
        return _com_texto({"liberado": False, "em": None, "por": "",
                           "motivo": f"claude.json não pôde ser lido: {exc}",
                           "origem": "ilegivel"})
    try:
        dados = json.loads(bruto)
        if not isinstance(dados, dict) or not isinstance(dados.get("liberado"), bool):
            raise ValueError("sem 'liberado' booleano")
    except ValueError:
        return _com_texto({"liberado": False, "em": None, "por": "",
                           "motivo": "claude.json está ilegível (tratado como proibido)",
                           "origem": "ilegivel"})
    return _com_texto({"liberado": dados["liberado"], "em": dados.get("em"),
                       "por": str(dados.get("por") or ""),
                       "motivo": str(dados.get("motivo") or ""),
                       "origem": "arquivo"})


_AUSENCIA_VISTA = set()
_AUSENCIA_TRAVA = threading.Lock()


def _registrar_ausencia() -> None:
    """A primeira leitura sem arquivo fica no historico (uma vez por arquivo
    e por processo, e so se o historico ainda nao existe)."""
    chave = str(caminho())
    with _AUSENCIA_TRAVA:
        if chave in _AUSENCIA_VISTA:
            return
        _AUSENCIA_VISTA.add(chave)
    try:
        if caminho_historico().exists():
            return
        _anexar({"em": _agora_iso(), "liberado": True, "por": "padrão",
                 "motivo": "claude.json ausente: tratado como liberado",
                 "pid": os.getpid()})
    except OSError:
        pass


def _por(por: str) -> str:
    """" por X", ou " pelo app (...)" como veio (sem "por pelo")."""
    if not por:
        return ""
    return f" {por}" if por.split(" ", 1)[0] in ("pelo", "pela", "por") else f" por {por}"


def _com_texto(estado: dict) -> dict:
    if estado["origem"] == "ilegivel":
        estado["texto"] = f"Claude PROIBIDO: {estado['motivo']}"
    elif estado["liberado"]:
        estado["texto"] = ("Claude liberado (nunca foi mudado)"
                           if estado["origem"] == "sem_arquivo" else
                           f"Claude liberado desde {_quando(estado['em'])}"
                           + _por(estado["por"]))
    else:
        estado["texto"] = (f"Claude proibido desde {_quando(estado['em'])}"
                           + _por(estado["por"])
                           + (f" — {estado['motivo']}" if estado["motivo"] else ""))
    return estado


def liberado() -> bool:
    return ler()["liberado"]


def motivo_proibido() -> str:
    """"" se liberado; senao, a frase de recusa para quem ia usar o Claude."""
    estado = ler()
    if estado["liberado"]:
        return ""
    if estado["origem"] == "ilegivel":
        return f"Claude proibido: {estado['motivo']}"
    return f"Claude proibido pelo Adrian desde {_quando(estado['em'])}"


def mudar(liberar: bool, *, por: str, motivo: str = "") -> dict:
    """Grava o novo estado (atomico, sob trava) e anexa ao historico.

    Devolve `{"estado": <ler()>, "mudou": bool, "antes": bool}`. Pedir o que
    ja vale nao reescreve o arquivo (o toque duplo nao vira duas linhas).
    """
    from .api_http import trava_arquivo

    alvo = caminho()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    with trava_arquivo(alvo.with_name(alvo.name + ".lock")):
        antes = ler()
        if antes["origem"] == "arquivo" and antes["liberado"] == bool(liberar):
            return {"estado": antes, "mudou": False, "antes": antes["liberado"]}
        novo = {"liberado": bool(liberar), "em": _agora_iso(),
                "por": str(por or "?")[:80],
                "motivo": str(motivo or "")[:MOTIVO_MAX]}
        temporario = alvo.with_name(f".{alvo.name}.{os.getpid()}."
                                    f"{threading.get_ident()}.tmp")
        temporario.write_text(json.dumps(novo, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
        os.replace(temporario, alvo)
        _anexar(dict(novo, antes=antes["liberado"], origem_antes=antes["origem"]))
    return {"estado": ler(), "mudou": True, "antes": antes["liberado"]}


def historico(n: int = 20) -> list[dict]:
    """As ultimas `n` mudancas, da mais nova para a mais velha."""
    try:
        texto = caminho_historico().read_text(encoding="utf-8")
    except OSError:
        return []
    linhas = []
    for bruta in texto.splitlines():
        try:
            linha = json.loads(bruta)
        except ValueError:
            continue
        if isinstance(linha, dict):
            linhas.append(linha)
    return list(reversed(linhas[-n:]))


def para_o_app() -> dict:
    estado = ler()
    return {"liberado": estado["liberado"], "em": estado["em"], "por": estado["por"],
            "motivo": estado["motivo"], "origem": estado["origem"],
            "texto": estado["texto"],
            "desde_hhmm": hhmm(estado["em"]) if estado["em"] else "",
            "historico": historico(6)}
