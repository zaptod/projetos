"""Duas builds em paralelo com o MESMO nome: as duas entram, uma como "#2".

BLD-2 da auditoria profunda (14/10/2026), pelo caminho da roleta
(``exporter.insert_into_database``). O exporter lia o banco, escolhia o nome
livre e so depois gravava: na corrida, um personagem sumia, ou o segundo
processo levantava "nomes ja existentes" e a build morria. Agora o desempate
e a gravacao saem juntos de ``database.inserir_no_banco``, dentro da trava.

Dois processos de verdade, num banco descartavel (nunca o de
``%LOCALAPPDATA%``), com TEMP diferente em cada um. A corrida e forcada com
uma barreira na primeira leitura do banco (ver o teste irmao em
``tests/test_banco_insercao_concorrente_regressions.py``).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RB = Path(__file__).resolve().parents[1]
RAIZ = RB.parent

FILHO = r'''
import json, sys, time
from pathlib import Path
rotulo, barreira = sys.argv[1], Path(sys.argv[2])
outro = "B" if rotulo == "A" else "A"
from builds.nf_bridge import exporter
from builds.nf_bridge import loader as nf
database = nf.database

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
marca = {"A": 11, "B": 13}[rotulo]
arma = dict(armas[0]); pers = dict(chars[0])
arma["nome"] = "Lamina da Corrida"
arma["dano"] = float(marca)          # marca de quem e a arma
pers["nome"] = "Kael da Corrida"
pers["cor_r"] = marca                # a mesma marca no personagem
resultado = exporter.insert_into_database(arma, pers)
print(json.dumps(resultado), flush=True)
'''


class InsercaoDaRoletaConcorrenteTests(unittest.TestCase):
    def test_mesmo_nome_em_paralelo_vira_nome_e_nome_2(self):
        from neural_fights.data import database

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            runtime = tmp / "runtime"
            runtime.mkdir()
            pacote = Path(database.DATA_DIR)
            shutil.copyfile(pacote / "armas.json", runtime / "armas.json")
            shutil.copyfile(pacote / "personagens.json", runtime / "personagens.json")
            barreira = tmp / "barreira"
            barreira.mkdir()

            filhos = {}
            for rotulo in ("A", "B"):
                temp = tmp / f"temp_{rotulo}"
                temp.mkdir()
                env = os.environ.copy()
                env["NEURAL_FIGHTS_RUNTIME_DIR"] = str(runtime)
                env["TEMP"] = env["TMP"] = str(temp)
                env["PYTHONPATH"] = os.pathsep.join(
                    [str(RAIZ), str(RB), env.get("PYTHONPATH", "")]
                ).rstrip(os.pathsep)
                filhos[rotulo] = subprocess.Popen(
                    [sys.executable, "-c", FILHO, rotulo, str(barreira)],
                    cwd=RB, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
            saidas = {r: p.communicate(timeout=60) for r, p in filhos.items()}

            for rotulo, processo in filhos.items():
                self.assertEqual(0, processo.returncode, saidas[rotulo][1])
            resultados = {r: json.loads(saidas[r][0].strip().splitlines()[-1])
                          for r in filhos}
            self.assertEqual(
                {"Kael da Corrida", "Kael da Corrida #2"},
                {r["personagem"] for r in resultados.values()},
            )

            chars = json.loads((runtime / "personagens.json").read_text("utf-8"))
            armas = {a["nome"]: a for a in
                     json.loads((runtime / "armas.json").read_text("utf-8"))}
            corrida = [p for p in chars if p["nome"].startswith("Kael da Corrida")]
            self.assertEqual(2, len(corrida), [p["nome"] for p in corrida])
            for personagem in corrida:
                arma = armas[personagem["nome_arma"]]
                self.assertEqual(
                    float(personagem["cor_r"]), arma["dano"],
                    f"{personagem['nome']} aponta para a arma do outro processo",
                )
            for rotulo, r in resultados.items():
                gravado = next(p for p in chars if p["nome"] == r["personagem"])
                self.assertEqual(r["arma"], gravado["nome_arma"])


if __name__ == "__main__":
    unittest.main()
