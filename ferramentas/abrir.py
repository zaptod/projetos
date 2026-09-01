# -*- coding: utf-8 -*-
"""Abre as coisas do projeto, e CONSERTA o que falta antes de abrir.

    python ferramentas/abrir.py            o painel
    python ferramentas/abrir.py novo       o painel novo (previa)
    python ferramentas/abrir.py vila       a Oficina de sprites
    python ferramentas/abrir.py testar     roda todos os testes
    python ferramentas/abrir.py conferir   so diz o que esta faltando

Por que existe, e por que a logica NAO esta no .bat: desde 01/09/2026 o
projeto virou um conjunto de pacotes instalados (`pip install -e`). Se a
instalacao nao estiver de pe -- Python novo, pasta movida, maquina outra --
a janela simplesmente NAO ABRE, porque `pythonw` engole a mensagem de erro
junto com o console. Um atalho que falha em silencio e pior do que nao ter
atalho.

Entao aqui se confere primeiro, se conserta quando da, e so entao se abre.
Quando nao da, a mensagem diz o que fazer em portugues.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# (pacote, pasta que o instala). A ordem importa: `contos` depende de
# `builds`, e `panorama` depende dos dois.
PACOTES = [
    ("neural_fights", RAIZ),
    ("builds", RAIZ / "random_builds"),
    ("contos", RAIZ / "historias"),
    ("panorama", RAIZ / "visao"),
]

# O que nao e do projeto e nao da para instalar com `-e`.
DE_FORA = [("PIL", "Pillow"), ("numpy", "numpy")]


def _falta() -> list:
    """Quais pacotes do projeto nao importam agora."""
    import importlib
    ausentes = []
    for nome, pasta in PACOTES:
        try:
            importlib.import_module(nome)
        except Exception:                                   # noqa: BLE001
            ausentes.append((nome, pasta))
    return ausentes


def _falta_de_fora() -> list:
    import importlib
    ausentes = []
    for modulo, pacote in DE_FORA:
        try:
            importlib.import_module(modulo)
        except Exception:                                   # noqa: BLE001
            ausentes.append(pacote)
    return ausentes


def instalar(ausentes: list) -> bool:
    """`pip install -e` no que falta. True se resolveu tudo."""
    for nome, pasta in ausentes:
        print(f"  instalando {nome} ({pasta.name})...", flush=True)
        resultado = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(pasta),
             "--no-deps", "-q"], cwd=str(RAIZ))
        if resultado.returncode != 0:
            print(f"  nao consegui instalar {nome}.")
            return False
    # Um processo Python nao "desinstala" o que ja tentou importar; conferir
    # de novo aqui daria falso negativo. Quem confere e o processo seguinte.
    return True


def conferir(consertar: bool = True) -> int:
    """Diz o que falta. Com `consertar`, tenta resolver antes de reclamar."""
    de_fora = _falta_de_fora()
    if de_fora:
        print("Falta biblioteca de fora do projeto: " + ", ".join(de_fora))
        print(f"  {Path(sys.executable).name} -m pip install "
              + " ".join(de_fora))
        return 1

    ausentes = _falta()
    if not ausentes:
        print("Tudo no lugar.")
        return 0

    nomes = ", ".join(n for n, _p in ausentes)
    print(f"Faltando: {nomes}")
    if not consertar:
        return 1
    print("Instalando (uma vez so; das proximas ja estara pronto)...")
    if not instalar(ausentes):
        print()
        print("Nao deu. Rode isto na pasta do projeto e me diga o que apareceu:")
        print(f"  {Path(sys.executable).name} -m pip install -e . "
              "-e ./random_builds -e ./historias -e ./visao")
        return 1
    print("Pronto.")
    return 0


def _abrir_solto(argumentos: list) -> int:
    """Abre sem console e sem prender este processo."""
    executavel = Path(sys.executable)
    sem_console = executavel.with_name(
        executavel.name.replace("python.exe", "pythonw.exe"))
    interpretador = sem_console if sem_console.is_file() else executavel
    bandeiras = getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen([str(interpretador)] + argumentos, cwd=str(RAIZ),
                     creationflags=bandeiras)
    return 0


ALVOS = {
    "painel": (["painel_ui.py"], "o painel de controle"),
    "novo": (["-m", "painel"], "o painel novo (previa)"),
    "vila": (["-m", "vila.editor"], "a Oficina de sprites da Vila"),
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="abrir", description="abre as coisas do projeto")
    parser.add_argument("alvo", nargs="?", default="painel",
                        choices=list(ALVOS) + ["testar", "conferir"])
    args = parser.parse_args(argv)

    if args.alvo == "conferir":
        return conferir(consertar=False)

    codigo = conferir(consertar=True)
    if codigo != 0:
        return codigo

    if args.alvo == "testar":
        # Este fica preso de proposito: quem pediu quer LER o resultado.
        return subprocess.run([sys.executable, "-X", "utf8", "testar.py"],
                              cwd=str(RAIZ)).returncode

    argumentos, descricao = ALVOS[args.alvo]
    print(f"Abrindo {descricao}...")
    return _abrir_solto(argumentos)


if __name__ == "__main__":
    raise SystemExit(main())
