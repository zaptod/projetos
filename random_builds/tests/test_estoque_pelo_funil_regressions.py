# -*- coding: utf-8 -*-
"""O contador de estoque conta o que a ESCOLHA pode levar, e nao o catalogo.

MEDIDO EM 27/09/2026, 23:55. O aviso do Telegram dizia "por formato — build
7d", e `proximo_build` nao tinha build nenhum para levar:

    catalogo - publicados (celular)   33  build 28, duelo 4, estreia 1
    sem pendencia                     30  (generation_00085, 00077 e 00077:B)
    sem titulo ja no ar                5  (25 variantes B barradas)
    com som                            4  (generation_00066 calada em 95%)

`estoque_por_formato` contava a primeira linha: 28 builds / 3,75 por dia = 7.
O real era 0. `pendentes_por_canal` contava a terceira (5): sem o audio.
Agora os dois contam a ultima, pela MESMA funcao da escolha
(`_builds_prontos`) — o mesmo defeito que `pendentes_por_canal` ja tinha tido
em 16/09 voltou porque o segundo contador tinha filtro proprio.

E o caso ZERO e testado por nome: contador que da nota boa para fila vazia
ja mentiu tres vezes num dia so neste projeto.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_estoque", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _V:
    def __init__(self, vid, titulo, origem, *, pendencias=None, quando=0.0):
        self.id, self.titulo, self.origem = vid, titulo, origem
        self.perfil, self.pendencias, self.quando = "celular", pendencias, quando
        self.caminho = ""


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


def _catalogo_de_27_09():
    """A forma do estoque de 27/09, com os numeros de la."""
    variantes = [_V(f"generation_{i:05d}:build:celular:B", f"Build {i}", "build")
                 for i in range(25)]
    pendentes = [_V(f"generation_{i:05d}:build:celular", f"Pendente {i}",
                    "build", pendencias=["sem payoff"]) for i in (77, 78, 85)]
    muda = _V("generation_00066:estreia:celular", "Estreia muda", "estreia")
    return variantes + pendentes + [muda]


# Os titulos das 25 variantes ja estao no ar (a variante A saiu com eles).
LEDGER_DE_27_09 = [{"video_id": f"generation_{i:05d}:build:celular",
                    "titulo": f"Build {i}", "plataforma": "youtube",
                    "url": "https://youtu.be/x", "publicado": True}
                   for i in range(25)]


class EstoquePeloFunilTests(unittest.TestCase):
    def setUp(self):
        from builds.publicar import catalogo, metricas
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.m.repetir_titulo = lambda *_a, **_k: False
        self.m.cota_da_grade = lambda config=None: {"build": 3, "duelo": 4,
                                                    "estreia": 1}
        self.m._servidos_recentes = lambda n=16: {}
        self.m._audio_mudo = lambda v: ("calado em 95%" if "00066" in v.id
                                        else "")
        self.catalogo, self.metricas = catalogo, metricas
        self._ledger(LEDGER_DE_27_09)

    def _ledger(self, linhas):
        _trocar(self, self.metricas, "publicados",
                lambda *a, **k: list(linhas))

    def _catalogo(self, videos):
        _trocar(self, self.catalogo, "listar", lambda *a, **k: list(videos))

    def test_o_caso_de_27_09_da_zero_em_todo_formato(self):
        """Era {build: 7, duelo: 0, estreia: 0}. Nenhum dos 29 podia sair."""
        self._catalogo(_catalogo_de_27_09())
        self.assertEqual({"build": 0, "duelo": 0, "estreia": 0},
                         self.m.estoque_por_formato(por_dia=10))
        self.assertIsNone(self.m.proximo_build(),
                          "o contador e a escolha tem de concordar")

    def test_a_gordura_do_canal_tambem_ve_o_audio_mudo(self):
        """`pendentes_por_canal` dizia 1 aqui (a estreia muda); a escolha, 0."""
        self._catalogo(_catalogo_de_27_09())
        self.m.fila_de_historias = lambda: []
        self.assertEqual(0, self.m.pendentes_por_canal()["builds"])

    def test_catalogo_vazio_e_zero_e_nao_silencio(self):
        """ZERO EVENTOS: formato sem nada aparece com 0 — e o aviso 'sem
        estoque' e quem dispara com ele. Sumir da lista seria calar."""
        self._catalogo([])
        self.assertEqual({"build": 0, "duelo": 0, "estreia": 0},
                         self.m.estoque_por_formato(por_dia=10))

    def test_o_que_a_escolha_leva_e_o_que_o_contador_conta(self):
        """Quatro duelos novos no meio do lixo de 27/09: o contador ve os
        quatro, e a escolha sai com um deles."""
        duelos = [_V(f"duelo_{i:05d}:duelo:celular", f"Duelo {i}", "duelo",
                     quando=float(i)) for i in range(12, 16)]
        self._catalogo(duelos + _catalogo_de_27_09())
        prontos = self.m._builds_prontos()
        self.assertEqual(sorted(v.id for v in duelos),
                         sorted(v.id for v in prontos))
        # 4 duelos / (10 disparos * 4/8) = 0 dias; com 2 disparos, 4 dias.
        self.assertEqual(4, self.m.estoque_por_formato(por_dia=2)["duelo"])
        self.assertIn(self.m.proximo_build().id, {v.id for v in duelos})

    def test_falha_de_leitura_nao_vira_estoque(self):
        def quebra(*_a, **_k):
            raise OSError("catalogo ilegivel")
        _trocar(self, self.catalogo, "listar", quebra)
        self.assertEqual({}, self.m.estoque_por_formato(por_dia=10))
        self.m.fila_de_historias = lambda: []
        self.assertEqual(-1, self.m.pendentes_por_canal()["builds"])


# A lembranca da medida de audio mudou-se para `builds.publicar.audio` em
# 28/09/2026 (a do `postar.py` morria a cada carga do modulo, e o bot o
# carrega do zero a cada relatorio). Os testes dela estao em
# test_luta_muda_regressions.MedidaLembradaTests.


if __name__ == "__main__":
    unittest.main()
