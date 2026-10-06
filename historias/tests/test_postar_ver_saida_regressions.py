# -*- coding: utf-8 -*-
"""`postar.py --ver` saia com 1 em TODO retrato.

Medido em 05/10/2026, 22:53: `python -X utf8 ferramentas/postar.py --ver`
mostrou o retrato inteiro (historias veria historia_00054:celular:p01, builds
veria generation_00094:estreia:celular, gordura, frescor, retidos) e saiu
com EXIT=1. A regra do fim de `main` ("tentou e nada saiu -> 1", de 12/09) e
para a rodada de verdade; com `--ver` nenhuma ficha tem `feito`, entao ela
dava 1 sempre. O app mostra a tarefa "ver o proximo horario" como "erro /
saiu 1" (`remoto/app/comandos.js:152`) e quem le o codigo nao separa o
retrato de um canal que levantou.

Caso ZERO: fila vazia nos dois canais com `--ver` e retrato, nao falha: 0.
O 1 do `--ver` passa a dizer uma coisa so: um canal levantou excecao
(`_rodar_canal` poe `excecao` na ficha). A rodada de verdade nao muda.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_ver_saida", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class VerSaiZeroTests(unittest.TestCase):
    def setUp(self):
        # Modulo novo a cada teste: as trocas abaixo morrem com ele, e nada
        # aqui abre navegador, rede, ledger ou diario.
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.m.esperar_a_rede = lambda **k: True
        self.m.avisar = lambda r: None
        self.m.avisar_lote_nao_fechou = lambda *a, **k: None
        self.m.estoque_do_lote = lambda *a, **k: {}
        self.m.linhas_do_estoque = lambda lote: []
        self.m.frescor_do_estoque = lambda *a, **k: {}
        self.m.retidos_por_canal = lambda: {}
        self.m.consertadas_por_canal = lambda: {}
        self.m.reserva_do_tiktok = lambda *a, **k: []
        self.m.recuperar_no_tiktok = lambda **k: {"fila": 0}
        self.m.recuperar_no_youtube = lambda **k: {"fila": 0}
        self.m.publicar_da_reserva = lambda **k: {}

    def _canais(self, historias, builds):
        self.m.postar_historia = historias
        self.m.postar_build = builds

    def test_ver_com_candidato_nos_dois_canais_sai_0(self):
        """O retrato de 05/10, 22:53: os dois canais 'veriam' um video."""
        self._canais(
            lambda **k: {"canal": "historias", "feito": False,
                         "veria": "historia_00054:celular:p01",
                         "motivo": "so vendo"},
            lambda **k: {"canal": "builds", "feito": False,
                         "veria": "generation_00094:estreia:celular",
                         "motivo": "so vendo"})
        self.assertEqual(0, self.m.main(["--ver"]))

    def test_ver_com_fila_vazia_sai_0(self):
        """Caso ZERO: nada a postar e informacao do retrato, nao falha."""
        self._canais(
            lambda **k: {"canal": "historias", "feito": False,
                         "motivo": "nao ha parte publicavel"},
            lambda **k: {"canal": "builds", "feito": False,
                         "motivo": "nao ha video pendente"})
        self.assertEqual(0, self.m.main(["--ver"]))

    def test_ver_com_canal_que_levantou_sai_1(self):
        """O 1 que sobra no `--ver` e o erro de verdade, engolido em ficha."""
        def quebra(**k):
            raise RuntimeError("catalogo ilegivel")
        self._canais(quebra,
                     lambda **k: {"canal": "builds", "feito": False,
                                  "veria": "g:build", "motivo": "so vendo"})
        self.assertEqual(1, self.m.main(["--ver"]))

    def test_rodada_de_verdade_que_nao_publicou_continua_1(self):
        """A regra de 12/09 nao muda: tentou e nada saiu -> 1."""
        self._canais(
            lambda **k: {"canal": "historias", "feito": False,
                         "motivo": "nao ha parte publicavel"},
            lambda **k: {"canal": "builds", "feito": False,
                         "motivo": "nao ha video pendente"})
        self.assertEqual(1, self.m.main([]))


if __name__ == "__main__":
    unittest.main()
