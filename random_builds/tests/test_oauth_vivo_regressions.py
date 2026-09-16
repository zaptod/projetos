# -*- coding: utf-8 -*-
"""`oauth_vivo`: a pergunta e sobre UM canal, e o engano tem de aparecer.

16/09/2026: `oauth_vivo("neural_fights")` passou o nome de uma CONTA onde vai
o canal. `ativa()` nao conhece esse canal e cai, de proposito, em
`principal` — entao tres "contas" testaram o MESMO arquivo, e "os tres
tokens estao revogados" chegou ao Adrian quando so um estava.

Nenhum caso toca a rede: o corpo que pergunta ao Google e dublado, e o
registro de contas mora numa pasta descartavel.
"""
import tempfile
import unittest
from pathlib import Path

from builds import contas


class _Base(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        reais = (contas.ARQUIVO, contas.runtime_dir, contas._oauth_vivo)
        contas.ARQUIVO = Path(self._tmp.name) / "contas.json"
        contas.runtime_dir = lambda: Path(self._tmp.name)
        self.perguntas = []

        def corpo_falso(canal, conta):
            self.perguntas.append((canal, conta,
                                   contas.credencial_youtube(canal, conta).name))
            return {"ok": True, "motivo": ""}

        contas._oauth_vivo = corpo_falso

        def restaurar():
            (contas.ARQUIVO, contas.runtime_dir, contas._oauth_vivo) = reais

        self.addCleanup(restaurar)
        for nome in ("neural_fights", "historinhas"):
            contas.adicionar("youtube", nome)
        contas.escolher("youtube", "builds", "neural_fights")
        contas.escolher("youtube", "historias", "historinhas")


class NomeDeContaNoLugarDoCanal(_Base):

    def test_o_caso_de_16_09_e_recusado_e_explicado(self):
        ficha = contas.oauth_vivo("neural_fights")
        self.assertFalse(ficha["ok"])
        self.assertIn("canal desconhecido", ficha["motivo"])
        self.assertIn("conta='neural_fights'", ficha["motivo"])
        # E, o principal: NAO testou arquivo nenhum no lugar.
        self.assertEqual([], self.perguntas)

    def test_nome_que_nao_e_nada_nao_ganha_a_dica_de_conta(self):
        ficha = contas.oauth_vivo("xpto")
        self.assertIn("canal desconhecido", ficha["motivo"])
        self.assertNotIn("use conta=", ficha["motivo"])

    def test_conta_nao_pode_mais_ir_por_posicao(self):
        with self.assertRaises(TypeError):
            contas.oauth_vivo("builds", "neural_fights")

    def test_duas_contas_nomeadas_testam_dois_arquivos(self):
        # O inverso exato do defeito: antes, tres nomes davam um arquivo so.
        contas.oauth_vivo("builds", conta="neural_fights")
        contas.oauth_vivo("builds", conta="historinhas")
        arquivos = {p[2] for p in self.perguntas}
        self.assertEqual({"youtube_credentials_neural_fights.json",
                          "youtube_credentials_historinhas.json"}, arquivos)


class CanalValido(_Base):

    def test_canal_valido_pergunta_pela_conta_dele(self):
        ficha = contas.oauth_vivo("builds")
        self.assertTrue(ficha["ok"])
        self.assertEqual("youtube_credentials_neural_fights.json",
                         self.perguntas[0][2])
        self.assertNotIn("aviso", ficha)

    def test_geral_continua_valendo(self):
        contas.oauth_vivo("geral")
        self.assertEqual(1, len(self.perguntas))


class CanalComNomeDeConta(_Base):
    """O outro lado da mesma armadilha: um nome que e canal E conta.

    Hoje nenhum nome coincide. O estado aqui e montado para os dois casos.
    """

    def test_canal_que_aponta_para_outra_conta_avisa(self):
        contas.adicionar("youtube", "historias")
        # O canal `historias` continua apontando para `historinhas`.
        ficha = contas.oauth_vivo("historias")
        self.assertIn("aviso", ficha)
        self.assertIn("'historinhas'", ficha["aviso"])
        self.assertIn("conta='historias'", ficha["aviso"])
        self.assertEqual("youtube_credentials_historinhas.json",
                         self.perguntas[0][2])

    def test_canal_que_aponta_para_a_conta_de_mesmo_nome_nao_avisa(self):
        contas.adicionar("youtube", "historias")
        contas.escolher("youtube", "historias", "historias")
        ficha = contas.oauth_vivo("historias")
        self.assertNotIn("aviso", ficha)

    def test_conta_explicita_nao_avisa(self):
        contas.adicionar("youtube", "historias")
        ficha = contas.oauth_vivo("historias", conta="historias")
        self.assertNotIn("aviso", ficha)


if __name__ == "__main__":
    unittest.main()
