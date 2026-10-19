# -*- coding: utf-8 -*-
"""19/10/2026: o canal `zombie` virou `bluelock`, com as MESMAS contas.

Pedido do Adrian: "vou usar o TikTok e o YouTube do zombie, ja que parei de
desenvolver ele por um tempo". O registro real (`contas.json`, fora do git)
diz, em cada servico, `"ativa": {"zombie": "zombie_survivores", ...}`. A
troca tem de valer SEM escrever nesse registro e sem mover login: o canal
novo le a escolha do antigo ate alguem escolher para ele, e quem escolhe
para o novo apaga o antigo.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from builds import contas

REGISTRO_DE_19_10 = {
    "servicos": {
        "youtube": {"contas": ["principal", "historinhas", "neural_fights", "zombie_survivores"],
                    "ativa": {"historias": "historinhas", "builds": "neural_fights",
                              "zombie": "zombie_survivores"}},
        "tiktok": {"contas": ["principal", "historinhas", "zombie_surviv0rs"],
                   "ativa": {"historias": "historinhas", "builds": "principal",
                             "zombie": "zombie_surviv0rs"}},
        "youtube_web": {"contas": ["principal", "neural_fights", "historinhas", "zombie_survivores"],
                        "ativa": {"builds": "neural_fights", "historias": "historinhas",
                                  "zombie": "zombie_survivores"}},
    },
    "identidades": {
        "youtube": {"zombie_survivores": {"rotulo": "Zombie survivores", "id": "UCzQ"},
                    "neural_fights": {"rotulo": "Neural fights", "id": "UCA3"},
                    "historinhas": {"rotulo": "historinhas", "id": "UC2S"}},
        "tiktok": {"zombie_surviv0rs": {"rotulo": "Zombie survivores (TikTok)", "id": "@zombie_surviv0rs"},
                   "principal": {"rotulo": "Neural fights (TikTok)", "id": "@neuralfights"},
                   "historinhas": {"rotulo": "historinhas (TikTok)", "id": "@historinhas2911"}},
    },
}


class CanalBlueLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        antes = (contas.ARQUIVO, contas.runtime_dir)
        self.arquivo = Path(self.tmp.name) / "contas.json"
        self.arquivo.write_text(json.dumps(REGISTRO_DE_19_10), encoding="utf-8")
        contas.ARQUIVO = self.arquivo
        contas.runtime_dir = lambda: Path(self.tmp.name)

        def restaurar():
            contas.ARQUIVO, contas.runtime_dir = antes
        self.addCleanup(restaurar)

    def test_bluelock_usa_as_contas_do_zombie_sem_mexer_no_registro(self):
        antes = self.arquivo.read_bytes()
        self.assertEqual("zombie_survivores", contas.ativa("youtube", "bluelock"))
        self.assertEqual("zombie_surviv0rs", contas.ativa("tiktok", "bluelock"))
        self.assertEqual("zombie_survivores", contas.ativa("youtube_web", "bluelock"))
        self.assertTrue(contas.explicita("tiktok", "bluelock"))
        self.assertEqual("Zombie survivores (TikTok)", contas.destino("tiktok", "bluelock")["identidade"])
        self.assertEqual(antes, self.arquivo.read_bytes())       # leitura pura

    def test_pasta_de_login_e_credencial_sao_as_mesmas_do_zombie(self):
        self.assertEqual("tiktok__zombie_surviv0rs", contas.perfil("tiktok", "bluelock").name)
        self.assertEqual("youtube_credentials_zombie_survivores.json",
                         contas.credencial_youtube("bluelock").name)

    def test_nome_antigo_e_apelido_do_novo(self):
        self.assertNotIn("zombie", contas.CANAIS)
        self.assertEqual("zombie_surviv0rs", contas.ativa("tiktok", "zombie"))
        self.assertEqual("bluelock", contas.canal_atual("zombie"))

    def test_escolher_para_o_bluelock_apaga_o_zombie_do_registro(self):
        contas.escolher("tiktok", "bluelock", "zombie_surviv0rs")
        ativa = json.loads(self.arquivo.read_text(encoding="utf-8"))["servicos"]["tiktok"]["ativa"]
        self.assertEqual("zombie_surviv0rs", ativa["bluelock"])
        self.assertNotIn("zombie", ativa)
        # os outros servicos continuam herdando do nome antigo
        self.assertEqual("zombie_survivores", contas.ativa("youtube", "bluelock"))

    def test_escolher_pelo_nome_antigo_grava_no_novo(self):
        contas.escolher("youtube", "zombie", "zombie_survivores")
        ativa = json.loads(self.arquivo.read_text(encoding="utf-8"))["servicos"]["youtube"]["ativa"]
        self.assertEqual({"historias", "builds", "bluelock"}, set(ativa))

    def test_builds_e_historias_nao_mudam(self):
        self.assertEqual("neural_fights", contas.ativa("youtube", "builds"))
        self.assertEqual("principal", contas.ativa("tiktok", "builds"))
        self.assertEqual("historinhas", contas.ativa("tiktok", "historias"))

    def test_bluelock_nao_colide_com_builds_nem_historias(self):
        """Caso ZERO da colisao: o destino do zombie e so do bluelock."""
        for servico in ("youtube", "tiktok"):
            # `geral` nao e canal de produto: a conformidade tambem o ignora
            repetidos = {k: [c for c in v if c != "geral"]
                         for k, v in contas.destinos_repetidos(servico).items()}
            self.assertEqual({}, {k: v for k, v in repetidos.items() if len(v) > 1}, servico)
            destino = contas.identidade(servico, contas.ativa(servico, "bluelock")).get("id")
            outros = {contas.identidade(servico, contas.ativa(servico, c)).get("id")
                      for c in ("builds", "historias")}
            self.assertTrue(destino and destino not in outros, servico)

    def test_bluelock_ainda_nao_publica(self):
        self.assertNotIn("bluelock", contas.CANAIS_PUBLICANDO)

    def test_canal_que_nunca_existiu_continua_recusado(self):
        with self.assertRaises(KeyError):
            contas.escolher("tiktok", "inventado", "x")
        self.assertFalse(contas.oauth_vivo("inventado")["ok"])


if __name__ == "__main__":
    unittest.main()
