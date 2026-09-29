# -*- coding: utf-8 -*-
"""Parte que passa de 3 min vira DOIS Shorts, e continua sendo UMA parte.

17/09/2026: as seis linhas da historia_00003 de 09-10/09 pareciam fantasmas
(o ledger dizia publicado e o canal nao tinha o titulo). Eram cortes: cada
parte subiu como "(1 de 2)" e "(2 de 2)", e por isso a linha guarda DUAS
confirmacoes separadas por " | ".

Decisao do orquestrador no mesmo dia: a parte cortada conta como UMA parte
para o teto do dia (os pedacos saem juntos, no mesmo horario), e os pedacos
entre si nao sao titulo repetido — mas outra PARTE com o mesmo titulo
continua barrada. Este arquivo trava o lado do LEDGER dessas duas regras;
o casamento com o canal (o sufixo "(1 de 2)" em `titulos.chave`) e do
random_builds.

Rode de dentro de historias/:
    python -m unittest tests.test_parte_cortada_regressions -v
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

from contos.pipeline import agenda

# Dia fixo: o teto conta pelo DIA DE GRADE (29/09/2026), e "hoje" do relogio
# as 03:00 poria a linha das 09:37 num dia de grade que ainda nao abriu.
HOJE = "2026-09-29"
AGORA = __import__("datetime").datetime(2026, 9, 29, 15, 40)
CORTADA = "publicado no YouTube | publicado no YouTube"


def _postar():
    caminho = Path(agenda.RAIZ).parent / "ferramentas" / "postar.py"
    spec = importlib.util.spec_from_file_location("postar_cortes", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _linha(parte: int, url: str = CORTADA, plataforma: str = "youtube"):
    return {"quando": f"{HOJE}T09:37:00", "plataforma": plataforma,
            "video_id": f"historia_00003:celular:p{parte:02d}",
            "titulo": f"A historia oficial nao fecha (Parte {parte})",
            "url": url}


class TetoDoDia(unittest.TestCase):

    def setUp(self):
        self.postar = _postar()

    def test_parte_cortada_em_dois_shorts_consome_uma_vaga_so(self):
        cheias = self.postar._fontes_cheias_hoje([_linha(4)], "youtube",
                                                 agora=AGORA)
        self.assertEqual(set(), cheias,
                         "uma parte cortada e UMA parte: com teto 2, a "
                         "historia ainda pode sair de novo hoje")

    def test_duas_partes_no_dia_fecham_a_historia(self):
        cheias = self.postar._fontes_cheias_hoje([_linha(4), _linha(5)],
                                                 "youtube", agora=AGORA)
        self.assertEqual({"historia_00003"}, cheias)

    def test_o_teto_continua_sendo_dois(self):
        self.assertEqual(2, self.postar.TETO_POR_FONTE_NO_DIA)


class TituloRepetido(unittest.TestCase):
    """Os pedacos nao competem na fila: o corte acontece na hora de
    publicar, e a fila tem PARTES. O que a guarda tem de barrar e outra
    parte com o titulo que ja esta no ar."""

    def setUp(self):
        self.postar = _postar()

    def _fila(self, titulos_no_ar, titulo_novo):
        self.postar._titulos_no_ar = lambda *_a, **_k: set(titulos_no_ar)
        video = SimpleNamespace(id="historia_00009:celular:p01",
                                titulo=titulo_novo)
        novos, repetidos = self.postar._sem_titulo_repetido([video],
                                                            "historias")
        return [v.id for v in novos], [v.id for v in repetidos]

    def test_outra_parte_com_o_mesmo_titulo_continua_barrada(self):
        from builds.publicar import titulos
        titulo = "A historia oficial nao fecha (Parte 4)"
        novos, repetidos = self._fila({titulos.chave(titulo)}, titulo)
        self.assertEqual([], novos)
        self.assertEqual(["historia_00009:celular:p01"], repetidos)

    def test_titulo_novo_passa(self):
        from builds.publicar import titulos
        novos, _ = self._fila({titulos.chave("Outra coisa (Parte 1)")},
                              "A historia oficial nao fecha (Parte 4)")
        self.assertEqual(["historia_00009:celular:p01"], novos)

    def test_a_fila_nao_tem_pedacos(self):
        """A prova de que (b) nao se decide aqui: quem corta e a publicacao.

        Se um dia a fila passar a trazer pedacos, este teste cai e a guarda
        de titulo precisa saber que "(1 de 2)" e "(2 de 2)" sao o mesmo
        video.
        """
        fonte = (Path(agenda.RAIZ).parent / "ferramentas"
                 / "postar.py").read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def fila_de_historias("):]
        corpo = corpo[:corpo.index("\ndef ")]
        self.assertNotIn("cortes", corpo)


if __name__ == "__main__":
    unittest.main()
