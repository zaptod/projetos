# -*- coding: utf-8 -*-
"""Passagem de bastão entre chats do orquestrador.

O Adrian (02/10/2026): "sinto que essa sessão está performando mal pelo tempo
que passei nela, quero configurar uma estratégia de handout, multiagentes e
renovação de chat". Um chat longo esquece, repete erro e deixa entrega parada.
Este arquivo é a memória de trabalho que passa de um chat para o próximo.

    python ferramentas/handoff.py gerar [--motivo X]   # grava docs/handoff/ATUAL.md
    python ferramentas/handoff.py mostrar               # gera e imprime (SessionStart)

O ATUAL.md tem duas partes:
  - a NOTA, escrita pelo chat que sai (`docs/handoff/NOTA.md`): o que estava
    fazendo, o próximo passo, as armadilhas. Ela só muda quando um chat a
    reescreve (comando /renovar);
  - o RETRATO, medido aqui toda vez: git, entregas do Codex, Mesa, fila,
    Grimório, serviços, postagens. Nada nele é de memória: tudo é lido do disco.
Cada geração arquiva a anterior em `docs/handoff/historico/`.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "docs" / "handoff"
NOTA = PASTA / "NOTA.md"
ATUAL = PASTA / "ATUAL.md"
HISTORICO = PASTA / "historico"
LOCAL = Path(os.environ.get("LOCALAPPDATA", "")) / "neural-fights"
PY = [sys.executable, "-X", "utf8"]


def _rodar(args: list, timeout: float = 60) -> str:
    try:
        feito = subprocess.run(args, cwd=str(RAIZ), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
        return (feito.stdout or "").strip()
    except Exception as exc:                                   # noqa: BLE001
        return f"(não consegui: {type(exc).__name__}: {exc})"


def _json(caminho: Path) -> dict:
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _git() -> list[str]:
    linhas = ["## Git"]
    ramo = _rodar(["git", "branch", "--show-current"])
    linhas.append(f"- ramo: `{ramo}`")
    sujos = [l for l in _rodar(["git", "status", "--short"]).splitlines() if not l.startswith("??")]
    if sujos:
        linhas.append(f"- **mudanças NÃO commitadas ({len(sujos)})** — confira antes de qualquer coisa:")
        linhas += [f"  - `{l.strip()}`" for l in sujos[:25]]
    else:
        linhas.append("- nada por commitar")
    linhas.append("- últimos commits:")
    linhas += [f"  - {l}" for l in _rodar(["git", "log", "--oneline", "-12"]).splitlines()]
    return linhas


def _delegados() -> list[str]:
    linhas = ["## Entregas do Codex (delegados)"]
    pasta = LOCAL / "delegados"
    aplicados = {x.get("id") for x in (_json(LOCAL / "coordenador" / "estado.json")
                                       .get("trabalho") or {}).get("aplicados", [])}
    olho = {x.get("id"): x.get("motivo") for x in (_json(LOCAL / "coordenador" / "estado.json")
                                                    .get("trabalho") or {}).get("olho", [])}
    achou = False
    for estado in sorted(pasta.glob("*/estado.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:15]:
        e = _json(estado)
        ident = estado.parent.name
        if e.get("limpo"):
            continue
        situ = e.get("situacao")
        if situ == "terminou" and ident in aplicados:
            continue
        achou = True
        extra = ""
        if ident in olho:
            extra = f" — **PRECISA DE OLHO**: {str(olho[ident])[:160]}"
        elif situ == "terminou":
            extra = " — terminou e NÃO foi aplicado"
        linhas.append(f"- `{ident}`: {situ} ({str(e.get('titulo') or '')[:80]}){extra}")
    if not achou:
        linhas.append("- nenhuma entrega pendurada")
    return linhas


def _mesa_fila_grimorio() -> list[str]:
    linhas = ["## Mesa, fila e Grimório"]
    estado = _rodar(PY + ["-m", "remoto.orquestrador", "estado"])
    ativos = [l.strip() for l in estado.splitlines() if "trabalhando" in l or "rodando" in l]
    linhas.append("- agentes ativos na Mesa: " + ("; ".join(a[:120] for a in ativos[:6]) or "nenhum"))
    fila = _rodar(PY + ["-m", "remoto.orquestrador", "fila", "listar"]).splitlines()
    linhas.append(f"- fila ({len(fila)}):")
    linhas += [f"  - {l[:160]}" for l in fila[:10]]
    leitor = _rodar(PY + ["-m", "remoto.decisoes", "leitor"])
    nao_lidas = [l for l in leitor.splitlines() if "NÃO LIDA" in l]
    linhas.append("- Grimório: " + (f"**{len(nao_lidas)} resposta(s) NÃO LIDA(s)** — leia e aplique primeiro"
                                     if nao_lidas else "todas as respostas lidas"))
    linhas += [f"  - {l.strip()}" for l in nao_lidas[:8]]
    return linhas


def _servicos() -> list[str]:
    linhas = ["## Serviços e máquina"]
    c = _json(LOCAL / "coordenador" / "estado.json")
    serv = c.get("servicos") or {}
    linhas.append("- coordenador: " + (f"pid {c.get('pid')}, código {c.get('versao')}" if c else "sem estado"))
    for nome, s in serv.items():
        velho = " (código velho)" if s.get("codigo_velho") else ""
        linhas.append(f"  - {nome}: {s.get('situacao')}{velho}")
    claude = _rodar(PY + ["-m", "remoto.orquestrador", "claude", "status"])
    linhas.append(f"- Claude: {claude.splitlines()[0][:140] if claude else '?'}")
    try:
        from random_builds.builds.grade import GRADE
        agora = datetime.now()
        prox = sorted((h, m) for h, m in GRADE if (h, m) > (agora.hour, agora.minute))
        if prox:
            h, m = prox[0]
            linhas.append(f"- próxima postagem: {h:02d}:{m:02d} — nada de reiniciar app/carteiro de "
                          f"{h:02d}:{max(0, m - 12):02d} a {h:02d}:{min(59, m + 18):02d}")
    except Exception:                                          # noqa: BLE001
        pass
    return linhas


def gerar(motivo: str = "") -> Path:
    PASTA.mkdir(parents=True, exist_ok=True)
    HISTORICO.mkdir(parents=True, exist_ok=True)
    if ATUAL.is_file():
        carimbo = datetime.fromtimestamp(ATUAL.stat().st_mtime).strftime("%Y-%m-%d_%H%M")
        (HISTORICO / f"{carimbo}.md").write_text(ATUAL.read_text(encoding="utf-8"), encoding="utf-8")
    nota = NOTA.read_text(encoding="utf-8").strip() if NOTA.is_file() else "_(nenhuma nota: o chat anterior não rodou /renovar)_"
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    partes = [f"# Passagem de bastão — {agora}" + (f" ({motivo})" if motivo else ""),
              "",
              "Leia ANTES de agir. A NOTA é do chat anterior; o RETRATO é medido agora do disco.",
              "Regras de operação: `CLAUDE.md`. Equipe: `docs/agentes/EQUIPE.md`.",
              "",
              "# NOTA do chat anterior",
              "",
              nota,
              "",
              "# RETRATO (medido agora)",
              ""]
    for bloco in (_git, _delegados, _mesa_fila_grimorio, _servicos):
        try:
            partes += bloco() + [""]
        except Exception as exc:                               # noqa: BLE001
            partes += [f"## {bloco.__name__}: falhou ({type(exc).__name__}: {exc})", ""]
    ATUAL.write_text("\n".join(partes), encoding="utf-8")
    return ATUAL


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Passagem de bastão entre chats")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gerar")
    g.add_argument("--motivo", default="")
    sub.add_parser("mostrar")
    args = p.parse_args(argv)
    if args.cmd == "gerar":
        print(gerar(args.motivo))
    else:
        caminho = gerar("início de chat")
        sys.stdout.reconfigure(encoding="utf-8")
        print(caminho.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
