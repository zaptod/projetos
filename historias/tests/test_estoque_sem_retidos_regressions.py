# -*- coding: utf-8 -*-
"""Parte retida nao e gordura: ela conta a parte.

28/09/2026, pedido do Adrian (via relatorio de historias, edf80bf): o estoque
e a gordura nao podem contar `nao_assistido` como pronto. Com a valvula de
qualidade (8cb59b2), a parte reprovada ou vista so pela folha so sai no lugar
do horario vazio — contada como dias de gordura, ela dizia que o canal tinha
video que a escolha nao usa. Medido na fila das 03:05: 19 partes, 18 delas
retidas ou vetadas.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_retidos", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _P:
    def __init__(self, vid):
        self.id = vid


class EstoqueSemRetidosTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.fila = [_P("historia_00032:celular:p05"),
                     _P("historia_00034:celular:p04"),
                     _P("historia_00037:celular:p01")]
        self.retidas = {"historia_00032:celular:p05": "a IA reprovou",
                        "historia_00034:celular:p04": "so pela folha"}
        self.m.fila_de_historias = lambda: list(self.fila)
        self.m._retencao = lambda v: self.retidas.get(v.id, "")
        # So o canal de historias interessa aqui.
        self.m._builds_prontos = lambda *a, **k: []

    def test_retida_sai_da_gordura_e_conta_a_parte(self):
        self.assertEqual(1, self.m.pendentes_por_canal()["historias"])
        self.assertEqual({"historias": 2}, self.m.retidos_por_canal())

    def test_caso_zero_fila_vazia(self):
        self.fila = []
        self.assertEqual(0, self.m.pendentes_por_canal()["historias"])
        self.assertEqual({"historias": 0}, self.m.retidos_por_canal())

    def test_tudo_retido_e_gordura_zero(self):
        self.retidas = {v.id: "x" for v in self.fila}
        self.assertEqual(0, self.m.pendentes_por_canal()["historias"])
        self.assertEqual(0, self.m.estoque(por_dia=10)["historias"])

    def test_falha_ao_contar_nao_vira_zero(self):
        def quebra():
            raise OSError("catalogo ilegivel")
        self.m.fila_de_historias = quebra
        self.assertEqual(-1, self.m.pendentes_por_canal()["historias"])
        self.assertEqual({"historias": -1}, self.m.retidos_por_canal())


if __name__ == "__main__":
    unittest.main()
