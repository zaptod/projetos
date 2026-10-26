# -*- coding: utf-8 -*-
"""PUB-6: `conformidade()` nao acusa o canal `zombie`, que ainda nao publicava.

(26/10/2026: o `bluelock`, herdeiro do zombie, PASSOU a publicar - a serie de
videos, 1 por dia. Ele agora e cobrado como builds e historias: conta propria
em cada servico; a conta herdada do `zombie` do registro real vale como propria.)

Auditoria de 11/10/2026 (`publicar-historias.md` #9): a regra 3 cobrava
conta propria de todo canal que nao e `geral`, e o `zombie` (que nao publica)
gerava 3 alertas que nunca apagavam — o "TUDO DENTRO DO PADRAO" de
`ferramentas/auditoria_contas.py` nunca aparecia. Medido no HEAD com o
registro abaixo: `conformidade()` devolvia os 3 itens do zombie (youtube,
tiktok, youtube_web). Agora `[]`.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from builds import contas


class ConformidadeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        antes = (contas.ARQUIVO, contas.runtime_dir)
        contas.ARQUIVO = Path(self.tmp.name) / "contas.json"
        contas.runtime_dir = lambda: Path(self.tmp.name)

        def restaurar():
            contas.ARQUIVO, contas.runtime_dir = antes
        self.addCleanup(restaurar)

    def _padrao(self, com_bluelock: bool = True):
        canais = [("builds", "neural_fights", "UCA"),
                  ("historias", "historinhas", "UCB")]
        if com_bluelock:
            canais.append(("bluelock", "zombie_survivores", "UCC"))
        for servico, ficha in contas.SERVICOS.items():
            if not ficha.get("publica"):
                continue
            for canal, nome, ident in canais:
                contas.escolher(servico, canal, nome)
                contas.identificar(servico, nome, rotulo=nome,
                                   identificador=f"{ident}-{servico}")

    def test_tudo_no_padrao_e_lista_vazia(self):
        self._padrao()
        self.assertEqual([], contas.conformidade())

    def test_bluelock_continua_escolhivel(self):
        """O canal que nao publica ainda escolhe conta (19/10: o `zombie`
        virou `bluelock`, com as mesmas contas)."""
        self.assertIn("bluelock", contas.CANAIS)
        contas.escolher("tiktok", "bluelock", "zumbis")
        self.assertEqual("zumbis", contas.ativa("tiktok", "bluelock"))

    def test_bluelock_herdado_do_zombie_nao_gera_alerta(self):
        """O registro real ainda diz `zombie`; a conformidade continua `[]`."""
        self._padrao(com_bluelock=False)
        dados = contas.estado()
        for servico in ("youtube", "youtube_web", "tiktok"):
            dados["servicos"][servico]["ativa"]["zombie"] = "zombie_survivores"
            dados["servicos"][servico]["contas"].append("zombie_survivores")
        contas._gravar(dados)
        self.assertEqual([], contas.conformidade())

    def test_canal_que_publica_sem_conta_continua_acusado(self):
        """Caso ZERO (registro vazio): os tres que publicam SAO acusados."""
        canais = {a["detalhe"].split()[0] for a in contas.conformidade()
                  if a["tipo"] == "canal sem conta propria"}
        self.assertEqual({"builds", "historias", "bluelock"}, canais)


if __name__ == "__main__":
    unittest.main()
