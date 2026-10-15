# -*- coding: utf-8 -*-
"""SCR-P6 (14/10/2026): o panorama media o disco E:, quem para a producao e o C:.

Medido em 14/10: E: com 57 GB livres ("disco ok") e C: com 13 GB — o
`disco_a_vigiar` de `historias/config/agenda.json` e de
`random_builds/config/geracao.json`, com freio de 5 GB. Agora cada volume
vigiado tem o limite do proprio config (critico = o freio; baixo = freio + 3).
"""
import unittest
from collections import namedtuple
from pathlib import Path
from unittest import mock

from panorama import auditoria, recursos

Uso = namedtuple("Uso", "total used free")
GB = 1024 ** 3


def _uso(livres):
    def uso_de(volume):
        return Uso(500 * GB, 0, livres[recursos._volume(volume)] * GB)
    return uso_de


class DiscoQueParaTests(unittest.TestCase):
    def setUp(self):
        # O repositorio "no E:", como no PC dele. O volume do repositorio entra
        # sempre na lista vigiada, e no runner do GitHub o checkout fica no
        # D: -- o disco falso nao tinha D: e dava KeyError (CI 38625290567).
        patcher = mock.patch.object(recursos, "RAIZ", Path(r"E:\projetos"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_disco_vigia_o_volume_do_config(self):
        disco = recursos._disco(_uso({"C:/": 4, "E:/": 50}))
        self.assertEqual("critico", disco["volumes"]["C:/"]["situacao"])
        self.assertEqual("ok", disco["volumes"]["E:/"]["situacao"])
        self.assertEqual("C:/", disco["volume"])
        self.assertEqual("critico", disco["situacao"])

    def test_c_com_7_gb_e_baixo(self):
        """Freio 5 GB + 3 de folga: 7 GB e "baixo"; 13 GB (o de hoje), "ok"."""
        self.assertEqual("baixo", recursos._disco(
            _uso({"C:/": 7, "E:/": 50}))["volumes"]["C:/"]["situacao"])
        self.assertEqual("ok", recursos._disco(
            _uso({"C:/": 13, "E:/": 57}))["situacao"])

    def test_alerta_cita_o_volume_e_o_veredito_e_erro(self):
        with mock.patch.object(recursos, "_disco",
                               return_value=recursos._disco(
                                   _uso({"C:/": 4, "E:/": 50}))):
            dados = recursos.situacao()
        alerta = [a for a in dados["alertas"] if a.startswith("disco")]
        self.assertEqual(1, len(alerta))
        self.assertIn("C:/", alerta[0])
        veredito = auditoria.veredito(
            {"qualidade": {"liberados": 5}, "metas": {"faltando": 0},
             "producao": {}, "recursos": {"alertas": alerta}})
        self.assertEqual("erro", veredito["cor"])

    def test_volume_que_nao_responde_nao_some(self):
        def uso_de(volume):
            if recursos._volume(volume) == "C:/":
                raise OSError("sem acesso")
            return Uso(500 * GB, 0, 50 * GB)
        disco = recursos._disco(uso_de)
        self.assertEqual(["C:/"], disco["sem_leitura"])


if __name__ == "__main__":
    unittest.main()
