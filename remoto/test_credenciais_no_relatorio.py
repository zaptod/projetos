# -*- coding: utf-8 -*-
"""O relatorio de funcionamento vigia as credenciais (11/09/2026).

Um refresh_token morto nao faz barulho nenhum: a publicacao continua, porque
ela vai pelo navegador, e so a MEDICAO para. Medido em 11/09/2026, o canal de
historias estava assim desde 31/08 — onze dias sem um numero e sem uma linha
de erro em lugar nenhum. O commit 1ad734d consertou a MENSAGEM de recusa e o
comando que ela sugere; nao havia nada que percebesse o problema sozinho.

    cd e:\\projetos
    python -m pytest remoto/test_credenciais_no_relatorio.py -q
"""
from __future__ import annotations

import unittest

from remoto import relatorios


class CredenciaisNoRelatorioTests(unittest.TestCase):

    def setUp(self):
        from builds import contas
        self.contas = contas
        self._antes = (contas.oauth_vivo, contas.ativa)
        # `testar.py` roda as suites com NEURAL_FIGHTS_RUNTIME_DIR apontando
        # para uma pasta vazia, entao o registro de contas da maquina NAO
        # existe aqui e `ativa` cai em "principal". Dublar e o que faz o
        # teste provar a LIGACAO (o comando nomeia a conta do canal) em vez
        # de provar o que esta gravado neste computador.
        contas.ativa = lambda servico, canal="geral": (
            "historinhas" if canal == "historias" else "neural_fights")
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        self.contas.oauth_vivo, self.contas.ativa = self._antes

    def _dublar(self, respostas: dict):
        """Dublado sempre: `oauth_vivo` usa REDE, e suite que toca rede e
        suite que falha no avião."""
        self.contas.oauth_vivo = lambda canal="geral", conta=None: respostas[canal]

    def test_tudo_vivo_sai_em_uma_linha(self):
        self._dublar({"builds": {"ok": True, "motivo": ""},
                      "historias": {"ok": True, "motivo": ""}})
        linhas = relatorios._linhas_das_credenciais()
        self.assertEqual(1, len(linhas))
        self.assertIn("✓", linhas[0])

    def test_token_morto_aparece_com_o_comando_do_conserto(self):
        self._dublar({
            "builds": {"ok": True, "motivo": ""},
            "historias": {"ok": False,
                          "motivo": "o Google revogou ou expirou o "
                                    "refresh_token: precisa autorizar de novo"}})
        texto = "\n".join(relatorios._linhas_das_credenciais())
        self.assertIn("historias", texto)
        self.assertIn("refresh_token", texto)
        self.assertIn("youtube_oauth", texto,
                      "avisar sem dizer o comando obriga a procurar")
        self.assertIn("--conta historinhas", texto,
                      "sem a conta certa a reautorizacao grava por cima do "
                      "canal errado")

    def test_escopo_faltando_avisa_sem_gritar(self):
        """Funciona, mas a retencao nao vem: e aviso, nao falha."""
        self._dublar({
            "builds": {"ok": True, "motivo": "funciona, mas sem o escopo "
                                             "yt-analytics.readonly"},
            "historias": {"ok": True, "motivo": ""}})
        linhas = relatorios._linhas_das_credenciais()
        self.assertTrue(any("⚠" in L for L in linhas))
        self.assertFalse(any("❗" in L for L in linhas))

    def test_a_secao_entra_no_relatorio(self):
        self._dublar({"builds": {"ok": True, "motivo": ""},
                      "historias": {"ok": True, "motivo": ""}})
        self.assertIn("*Credenciais*", relatorios.funcionamento())

    def test_conta_que_explode_nao_derruba_o_relatorio(self):
        """O relatorio das 09:00 nao pode sumir porque a rede caiu."""
        def explodir(canal="geral", conta=None):
            raise RuntimeError("sem rede")

        self.contas.oauth_vivo = explodir
        linhas = relatorios._linhas_das_credenciais()
        self.assertEqual(2, len(linhas))
        self.assertTrue(all("não deu para conferir" in L for L in linhas))


if __name__ == "__main__":
    unittest.main()
