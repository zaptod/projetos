# -*- coding: utf-8 -*-
"""Nos horarios dos duelos, os builds rodam ANTES das historias (21/10/2026).

O caso medido: na rodada das 09:37 de 21/10 o postar rodou historias e so
depois builds, no mesmo processo; o duelo so foi entregue ao Studio as
09:41:17 (`postar.txt`). Desde a decisao `esperar-envio-terminar` as
historias esperam o arquivo inteiro e o processamento antes do clique ("tempo
restante" de 2 s a 3 min lido no clique, mais o teto da qualidade), entao o
duelo sairia 3 a 8 min depois do horario. O plano e o canal de duelos.

O que muda: SO a ordem de rodar (`_ordem_dos_canais`), e por consequencia a
volta final (`_volta_final` exige um canal que rodou DEPOIS) passa das
historias para os builds nos horarios deles — 0 voltas finais no `postar.txt`
inteiro. O que NAO muda e provado aqui: fichas, Telegram, codigo de saida,
recuperacao (historias, builds), recuperacao do YouTube e reserva do TikTok.

Rode de dentro de historias/:
    python -m unittest tests.test_duelos_antes_das_historias_regressions -v
"""
from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_duelos_antes",
                                                  POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


class OrdemPelaGradeTests(unittest.TestCase):
    """A grade de verdade (`grade.HORAS_POR_CANAL`), com o instante dado."""

    def setUp(self):
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None

    def test_horarios_dos_duelos_ate_31_10(self):
        for hora, minuto in ((9, 40), (17, 59), (21, 40)):
            with self.subTest(hora=hora):
                self.assertEqual(
                    ("builds", "historias"),
                    self.m._ordem_dos_canais(
                        datetime(2026, 10, 21, hora, minuto)))

    def test_fora_dos_horarios_dos_duelos_a_ordem_de_sempre(self):
        # 06:37, 12:07, 15:37, 20:37, 22:37, 00:37 (depois da meia-noite).
        for quando in (datetime(2026, 10, 21, 6, 40),
                       datetime(2026, 10, 21, 12, 10),
                       datetime(2026, 10, 21, 15, 40),
                       datetime(2026, 10, 21, 20, 40),
                       datetime(2026, 10, 21, 22, 40),
                       datetime(2026, 10, 22, 0, 40)):
            with self.subTest(quando=quando):
                self.assertEqual(("historias", "builds"),
                                 self.m._ordem_dos_canais(quando))

    def test_a_tabela_de_01_11_tambem_vale(self):
        """Desde 01/11 os duelos saem 12:07, 20:37 e 22:37."""
        self.assertEqual(("builds", "historias"),
                         self.m._ordem_dos_canais(datetime(2026, 11, 2, 12, 10)))
        self.assertEqual(("historias", "builds"),
                         self.m._ordem_dos_canais(datetime(2026, 11, 2, 9, 40)))


class RodadaTests(unittest.TestCase):
    """`main` de verdade, `_publicar_canal` e `_volta_final` de verdade; os
    canais, a recuperacao e a reserva dublados e anotando a ordem."""

    H_SAIU = {"canal": "historias", "feito": True,
              "alvo": "historia_00085:celular:p03",
              "url": "publicado no YouTube", "tiktok": "publicado no TikTok"}
    B_SAIU = {"canal": "builds", "feito": True,
              "alvo": "duelo_00132:duelo:celular",
              "url": "publicado no YouTube",
              "tiktok": "publicado no TikTok"}
    B_CAIU = {"canal": "builds", "feito": False,
              "alvo": "duelo_00132:duelo:celular", "youtube_falhou": True,
              "motivo": "YouTube falhou: infraestrutura: nao abriu",
              "tiktok": "", "tiktok_falha": "infraestrutura: nao abriu"}
    H_CAIU = {"canal": "historias", "feito": False,
              "alvo": "historia_00085:celular:p03", "youtube_falhou": True,
              "motivo": "YouTube falhou: infraestrutura: em branco",
              "tiktok": "", "tiktok_falha": "infraestrutura: nao abriu"}
    B_FORA = {"canal": "builds", "feito": False, "fora_da_grade": True,
              "motivo": "o horario das 15:37 nao e da grade de builds"}

    def setUp(self):
        self.m = m = _postar()
        m._linha = lambda *_a, **_k: None
        m._dormir = lambda s: None
        m.esperar_a_rede = lambda **k: True
        m._ainda_no_horario = lambda comeco, slot, **k: True
        m._cabe_antes_do_proximo = lambda *a, **k: True
        m.avisar_lote_nao_fechou = lambda *a, **k: None
        m.estoque_do_lote = lambda *a, **k: {}
        m.linhas_do_estoque = lambda lote: []
        m.retidos_por_canal = lambda: {}
        m.reserva_do_tiktok = lambda *a, **k: []
        self.passos = []
        self.avisos = []
        m.avisar = lambda r: self.avisos.append([dict(f) for f in r])
        m.recuperar_no_tiktok = lambda so_ver=False, canal="historias": (
            self.passos.append(("recuperar_tiktok", canal)) or {"fila": 0})
        m.recuperar_no_youtube = lambda **k: (
            self.passos.append(("recuperar_youtube", k.get("canal")))
            or {"fila": 0})
        m.publicar_da_reserva = lambda so_ver=False: (
            self.passos.append(("reserva_tiktok",)) or {})
        from builds.publicar import tiktok
        _trocar(self, tiktok, "confirmado",
                lambda estado: str(estado).startswith("publicado no TikTok"))
        self.ordem = []

    def _horario(self, dos_duelos: bool):
        self.m._fora_da_grade_do_canal = (
            lambda canal, plataforma, agora=None:
            "" if dos_duelos or canal != "builds"
            else "o horario das 15:37 nao e da grade de builds")

    def _canal(self, nome, respostas):
        def funcao(so_ver=False):
            self.ordem.append(nome)
            vezes = self.ordem.count(nome)
            return dict(respostas[min(vezes, len(respostas)) - 1])
        return funcao

    def _rodada(self, historias, builds):
        self.m.postar_historia = self._canal("historias", historias)
        self.m.postar_build = self._canal("builds", builds)
        return self.m.main([])

    def test_no_horario_dos_duelos_builds_roda_primeiro(self):
        self._horario(True)
        saida = self._rodada([self.H_SAIU], [self.B_SAIU])
        self.assertEqual(["builds", "historias"], self.ordem)
        self.assertEqual(0, saida)

    def test_fora_do_horario_dos_duelos_a_ordem_de_sempre(self):
        self._horario(False)
        saida = self._rodada([self.H_SAIU], [self.B_FORA])
        self.assertEqual(["historias", "builds"], self.ordem)
        self.assertEqual(0, saida)

    def test_nada_mais_muda_fichas_telegram_recuperacao_e_reserva(self):
        """A mesma rodada com a ordem nova e com a antiga forcada: o que vai
        ao Telegram, o codigo de saida e os passos depois dos canais sao
        identicos."""
        self._horario(True)
        saida_nova = self._rodada([self.H_SAIU], [self.B_SAIU])
        nova = (self.avisos[-1], list(self.passos))
        self.ordem, self.passos = [], []
        self.m._ordem_dos_canais = lambda agora=None: ("historias", "builds")
        saida_antiga = self._rodada([self.H_SAIU], [self.B_SAIU])
        antiga = (self.avisos[-1], list(self.passos))
        self.assertEqual(["historias", "builds"], self.ordem)
        self.assertEqual(saida_antiga, saida_nova)
        self.assertEqual(antiga, nova)
        self.assertEqual(["historias", "builds"],
                         [f["canal"] for f in nova[0]])
        self.assertEqual([("recuperar_tiktok", "historias"),
                          ("recuperar_tiktok", "builds"),
                          ("recuperar_youtube", "builds"),
                          ("reserva_tiktok",)], nova[1])

    def test_caso_zero_os_dois_caem_sai_1_sem_volta(self):
        self._horario(True)
        saida = self._rodada([self.H_CAIU], [self.B_CAIU])
        self.assertEqual(["builds"] * 3 + ["historias"] * 3, self.ordem)
        self.assertEqual(1, saida)

    def test_a_volta_final_passa_para_os_duelos(self):
        """A unica consequencia alem da ordem: builds derrubado pela rede e
        historias publicando depois prova a rede — os duelos voltam uma vez.
        (0 voltas finais no postar.txt inteiro ate 21/10.)"""
        self._horario(True)
        self._rodada([self.H_SAIU], [self.B_CAIU, self.B_CAIU, self.B_CAIU,
                                     self.B_SAIU])
        self.assertEqual(["builds"] * 3 + ["historias", "builds"], self.ordem)

    def test_historias_que_cai_no_horario_dos_duelos_nao_tem_volta(self):
        """O outro lado, documentado: historias e o ultimo canal ali."""
        self._horario(True)
        self._rodada([self.H_CAIU], [self.B_SAIU])
        self.assertEqual(["builds"] + ["historias"] * 3, self.ordem)

    def test_so_historias_nao_roda_builds(self):
        self._horario(True)
        self.m.postar_historia = self._canal("historias", [self.H_SAIU])
        self.m.postar_build = self._canal("builds", [self.B_SAIU])
        self.m.main(["--so", "historias"])
        self.assertEqual(["historias"], self.ordem)


if __name__ == "__main__":
    unittest.main()
