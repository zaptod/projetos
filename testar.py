# -*- coding: utf-8 -*-
"""Roda TUDO e diz, numa linha, se dá para confiar no estado do projeto.

    python testar.py             tudo (o que importa antes de mexer em algo)
    python testar.py --rapido    só os testes, sem abrir janela nem rede
    python testar.py --lista     o que existe, sem executar

Por que existe: o projeto virou três bases de código (random_builds,
historias, remoto) mais o painel, cada uma com o seu jeito de rodar teste.
"Testar tudo" virava quatro comandos em quatro pastas — e, na prática, ou se
esquecia um ou não se testava. Um comando que falha em vermelho é a
diferença entre confiar e torcer.

O que ele cobre, e por que cada parte está aqui:

  SUÍTES        os contratos de cada projeto. É o grosso.
  SMOKE         o painel MONTA as 12 páginas. Nenhuma suíte pega um erro de
                layout, e o painel é por onde tudo é operado.
  INTEGRIDADE   byte de controle no fonte. Já quebrou uma regex em silêncio
                (o heredoc do shell converte `\\b` em 0x08) e nada acusou.
  FERRAMENTAS   ffmpeg/ffprobe existem? Metade do projeto depende deles, e a
                falta só aparece no meio de um render de 20 minutos.

Sai com 0 quando tudo passa, 1 quando algo falha — serve em agendador.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PY = sys.executable
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# (nome, pasta, comando). A ordem é do mais barato para o mais caro: quem
# roda isto quer o primeiro erro rápido.
SUITES = (
    ("random_builds", RAIZ / "random_builds",
     [PY, "-X", "utf8", "-m", "unittest", "discover", "-s", "tests",
      "-p", "test_*.py"]),
    ("historias", RAIZ / "historias",
     [PY, "-X", "utf8", "-m", "unittest", "discover", "-s", "tests",
      "-p", "test_*.py"]),
    ("remoto (bot)", RAIZ,
     [PY, "-X", "utf8", "-m", "unittest", "remoto.test_remoto"]),
)
SMOKE = ("painel (12 páginas)", RAIZ, [PY, "-X", "utf8", "painel_ui.py",
                                       "--smoke"])

VERDE, VERMELHO, AMARELO, FIM = "\033[92m", "\033[91m", "\033[93m", "\033[0m"


def _cor(texto: str, cor: str) -> str:
    return f"{cor}{texto}{FIM}" if sys.stdout.isatty() else texto


def _rodar(nome: str, cwd: Path, comando: list, tempo: int = 900) -> dict:
    inicio = time.monotonic()
    try:
        proc = subprocess.run(comando, cwd=str(cwd), capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=tempo, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"nome": nome, "ok": False, "resumo": f"não rodou: {exc}",
                "segundos": time.monotonic() - inicio, "saida": ""}
    saida = (proc.stdout or "") + (proc.stderr or "")
    # `unittest` escreve o placar no stderr; o número de testes está nele.
    achado = re.search(r"^Ran (\d+) test", saida, re.M)
    quantos = int(achado.group(1)) if achado else 0
    falhas = re.findall(r"^(?:FAIL|ERROR): (\S+)", saida, re.M)
    ok = proc.returncode == 0
    resumo = (f"{quantos} testes" if quantos else "ok") if ok else (
        f"{len(falhas)} falha(s)" if falhas else
        f"código {proc.returncode}")
    return {"nome": nome, "ok": ok, "resumo": resumo, "falhas": falhas[:8],
            "segundos": time.monotonic() - inicio, "saida": saida}


def ferramentas() -> dict:
    faltando = [f for f in ("ffmpeg", "ffprobe") if not shutil.which(f)]
    return {"nome": "ferramentas externas", "ok": not faltando,
            "resumo": "ffmpeg e ffprobe no PATH" if not faltando
                      else f"FALTA: {', '.join(faltando)}",
            "falhas": faltando, "segundos": 0.0, "saida": ""}


def integridade() -> dict:
    """Byte de controle no fonte — o defeito que não aparece em teste nenhum."""
    permitidos = {9, 10, 13}
    sujos = []
    for projeto in (RAIZ / "random_builds", RAIZ / "historias",
                    RAIZ / "remoto"):
        if not projeto.is_dir():
            continue
        for arquivo in projeto.rglob("*.py"):
            if "__pycache__" in str(arquivo):
                continue
            bruto = arquivo.read_bytes()
            if any(b < 32 and b not in permitidos for b in bruto):
                posicao = next(i for i, b in enumerate(bruto)
                               if b < 32 and b not in permitidos)
                sujos.append(f"{arquivo.name}:{bruto[:posicao].count(10) + 1}")
    return {"nome": "integridade do fonte", "ok": not sujos,
            "resumo": "nenhum byte de controle" if not sujos
                      else f"{len(sujos)} arquivo(s) corrompido(s)",
            "falhas": sujos[:8], "segundos": 0.0, "saida": ""}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="testar", description="roda todos os testes do projeto")
    parser.add_argument("--rapido", action="store_true",
                        help="só as suítes (sem o smoke do painel)")
    parser.add_argument("--lista", action="store_true",
                        help="mostra o que seria rodado e sai")
    parser.add_argument("--verboso", action="store_true",
                        help="despeja a saída de quem falhou")
    args = parser.parse_args(argv)

    etapas = [("suite", nome, pasta, cmd) for nome, pasta, cmd in SUITES]
    if not args.rapido:
        etapas.append(("smoke", *SMOKE))

    if args.lista:
        print("verificações rápidas: ferramentas externas, integridade do fonte")
        for _tipo, nome, pasta, cmd in etapas:
            print(f"  {nome:22} em {pasta.name or '.'}: {' '.join(cmd[-3:])}")
        return 0

    print("=" * 68)
    resultados = [ferramentas(), integridade()]
    for resultado in resultados:
        marca = _cor("  ok  ", VERDE) if resultado["ok"] else _cor(" FALHA", VERMELHO)
        print(f"[{marca}] {resultado['nome']:24} {resultado['resumo']}")

    for _tipo, nome, pasta, comando in etapas:
        print(f"[ .... ] {nome:24} rodando...", end="\r", flush=True)
        resultado = _rodar(nome, pasta, comando)
        resultados.append(resultado)
        marca = _cor("  ok  ", VERDE) if resultado["ok"] else _cor(" FALHA", VERMELHO)
        print(f"[{marca}] {nome:24} {resultado['resumo']:22} "
              f"{resultado['segundos']:5.1f}s")
        for falha in resultado.get("falhas") or []:
            print(f"           {_cor('x ' + str(falha), VERMELHO)}")
        if args.verboso and not resultado["ok"]:
            print(resultado["saida"][-2500:])

    print("=" * 68)
    ruins = [r for r in resultados if not r["ok"]]
    total = sum(int(re.sub(r"\D", "", r["resumo"]) or 0)
                for r in resultados if r["ok"] and "teste" in r["resumo"])
    segundos = sum(r["segundos"] for r in resultados)
    if ruins:
        print(_cor(f"FALHOU: {', '.join(r['nome'] for r in ruins)}", VERMELHO))
        print("        rode de novo com --verboso para ver a saída.")
        return 1
    print(_cor(f"TUDO VERDE — {total} testes + smoke do painel "
               f"em {segundos:.0f}s", VERDE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
