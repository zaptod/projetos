# -*- coding: utf-8 -*-
"""SCR-P1 (14/10/2026): `panorama.auditoria.metas` contava LINHAS do ledger.

Duas linhas no mesmo horario (parte em 2 Shorts, recuperacao) pagavam dois
horarios: "13 de 10" escondia horario perdido, e e esse numero que vai ao
veredito, a pagina Auditoria e ao relatorio. Conta de mao: tres linhas do
YouTube das historias no horario das 06:37 e relogio as 13:00 (vencidos
00:37, 06:37, 09:37 e 12:07 = 4): saiu 1, faltando 3. No codigo antigo,
saiu 3, faltando 1.
"""
from __future__ import annotations

import unittest
from datetime import datetime
from unittest import mock

from builds.publicar import metricas
from panorama import auditoria

AGORA = datetime(2026, 10, 14, 13, 0)


def _metas(linhas_por_canal):
    with mock.patch.object(metricas, "publicados",
                           side_effect=lambda canal: list(
                               linhas_por_canal.get(canal, []))):
        return auditoria.metas(AGORA)


class UmPorHorarioTests(unittest.TestCase):
    def test_tres_linhas_no_mesmo_horario_pagam_um(self):
        linhas = [{"plataforma": "youtube", "quando": f"2026-10-14T06:{m}:00",
                   "url": "https://youtu.be/x", "video_id": f"h:p{i}"}
                  for i, m in enumerate(("38", "40", "52"))]
        ficha = _metas({"historias": linhas})
        self.assertEqual({"saiu": 1, "devido": 4, "faltando": 3},
                         ficha["canais"]["historias"]["youtube"])

    def test_caso_zero_sem_linha_falta_tudo(self):
        ficha = _metas({})
        for canal in ficha["canais"].values():
            for plat in canal.values():
                self.assertEqual(plat["devido"], plat["faltando"])
                self.assertEqual(0, plat["saiu"])
        self.assertFalse(ficha["em_dia"])


if __name__ == "__main__":
    unittest.main()
