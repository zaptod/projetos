"""Duas insercoes em PROCESSOS diferentes entram as duas no banco.

BLD-2 da auditoria profunda (14/10/2026). ``salvar_database(substituir=False)``
lia o banco numa trava e gravava em outra. A rodada da roleta e um
``generate-video`` manual (painel, bot ou terminal) podem inserir juntos: os
dois liam N, cada um gravava N+1 com o seu, e o personagem de um deles sumia
com os dois dizendo "inserido".

E a trava morava no TEMP de cada processo (BLD-7): dois processos com TEMP
diferente nem se excluiam. Aqui os dois filhos tem TEMP DIFERENTE de proposito.

Como a corrida e forcada: cada filho troca ``database.carregar_database`` por
um embrulho que, na PRIMEIRA leitura, cria ``barreira/<rotulo>`` e espera o
arquivo do outro por no maximo 3 s. Sem o conserto os dois leem o mesmo N,
se encontram na barreira e gravam por cima um do outro. Com o conserto o
segundo esta parado na trava, a espera do primeiro vence, e o segundo le o
banco ja com o primeiro.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from neural_fights.data import database

RAIZ = Path(__file__).resolve().parents[1]
PACOTE = Path(database.DATA_DIR)

FILHO = r'''
import json, os, sys, time
from pathlib import Path
rotulo, barreira = sys.argv[1], Path(sys.argv[2])
outro = "B" if rotulo == "A" else "A"
from neural_fights.data import database
from neural_fights.tools import gerador_database

real = database.carregar_database
estado = {"primeira": True}

def embrulho(*args, **kwargs):
    resultado = real(*args, **kwargs)
    if estado["primeira"]:
        estado["primeira"] = False
        (barreira / rotulo).write_text("li", encoding="utf-8")
        limite = time.monotonic() + 3.0
        while not (barreira / outro).exists() and time.monotonic() < limite:
            time.sleep(0.02)
    return resultado

database.carregar_database = embrulho
armas, chars = real()
arma = dict(armas[0]); pers = dict(chars[0])
arma["nome"] = "Arma Corrida " + rotulo
pers["nome"] = "Lutador Corrida " + rotulo
pers["nome_arma"] = arma["nome"]
gerador_database.salvar_database([arma], [pers], substituir=False)
print("inserido", rotulo, flush=True)
'''


def _ambiente(runtime: Path, temp: Path) -> dict:
    env = os.environ.copy()
    env[database.RUNTIME_DATA_DIR_ENV] = str(runtime)
    env["TEMP"] = env["TMP"] = str(temp)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(RAIZ), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    return env


def test_dois_processos_inserem_os_dois(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    shutil.copyfile(PACOTE / "armas.json", runtime / "armas.json")
    shutil.copyfile(PACOTE / "personagens.json", runtime / "personagens.json")
    barreira = tmp_path / "barreira"
    barreira.mkdir()
    antes = len(json.loads((runtime / "personagens.json").read_text("utf-8")))

    inicio = time.monotonic()
    filhos = {}
    for rotulo in ("A", "B"):
        temp = tmp_path / f"temp_{rotulo}"  # TEMP diferente em cada processo
        temp.mkdir()
        filhos[rotulo] = subprocess.Popen(
            [sys.executable, "-c", FILHO, rotulo, str(barreira)],
            cwd=RAIZ,
            env=_ambiente(runtime, temp),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    saidas = {r: p.communicate(timeout=60) for r, p in filhos.items()}
    duracao = time.monotonic() - inicio

    for rotulo, processo in filhos.items():
        assert processo.returncode == 0, saidas[rotulo][1]
        assert saidas[rotulo][0].strip() == f"inserido {rotulo}"
    gravados = json.loads((runtime / "personagens.json").read_text("utf-8"))
    nomes = {p["nome"] for p in gravados}
    assert {"Lutador Corrida A", "Lutador Corrida B"} <= nomes, nomes
    assert len(gravados) == antes + 2
    armas = {a["nome"] for a in json.loads((runtime / "armas.json").read_text("utf-8"))}
    assert {"Arma Corrida A", "Arma Corrida B"} <= armas
    assert duracao < 30, f"{duracao:.1f}s: passou do teto da trava"
    assert (runtime / ".persistence.lock").exists(), "a trava mora no runtime, nao no TEMP"
