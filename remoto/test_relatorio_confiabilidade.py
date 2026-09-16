# -*- coding: utf-8 -*-
"""/confiabilidade: o Telegram FORMATA, nao calcula.

O numero mora em `panorama.confiabilidade`, o mesmo que a pagina do painel
le. Aqui a ficha e injetada pronta; nenhum caso toca ledger, rede ou
Telegram de verdade.
"""
import unittest

from remoto import comandos, config, relatorios


def _ficha(**mudancas):
    base = {"dia": "2026-09-16", "prometido": 14, "provado": 14,
            "sem_prova": 0, "sem_campo": 0, "alertas": [], "valvula": [],
            "num_destino_so": {"builds": [], "historias": []},
            "falhas_tiktok": 0, "veredito": "ok"}
    base.update(mudancas)
    return base


class OTexto(unittest.TestCase):

    def test_dia_limpo_e_uma_linha_so(self):
        # Relatorio que sempre e longo e relatorio que ninguem le.
        texto = relatorios.confiabilidade(ficha=_ficha())
        self.assertIn("✓ 14/14", texto)
        self.assertNotIn("•", texto)
        self.assertEqual(len(texto.splitlines()), 2)

    def test_alerta_aparece_com_o_motivo(self):
        texto = relatorios.confiabilidade(ficha=_ficha(
            veredito="atencao", provado=12,
            alertas=["2 publicação(ões) sem prova hoje"]))
        self.assertIn("⚠ 12/14", texto)
        self.assertIn("• 2 publicação(ões) sem prova hoje", texto)

    def test_sem_laudo_e_dito_como_nao_sei(self):
        texto = relatorios.confiabilidade(ficha=_ficha(sem_campo=3))
        self.assertIn("não sei, não é falha", texto)

    def test_mostra_quem_passou_pela_valvula(self):
        texto = relatorios.confiabilidade(ficha=_ficha(
            veredito="atencao", alertas=["a válvula abriu 1 vez(es)"],
            valvula=[{"hora": "12:10", "alvo": "g1:build:celular:B",
                      "motivo": "titulo ja publicado"}]))
        self.assertIn("g1:build:celular:B", texto)

    def test_mostra_amostra_do_destino_so(self):
        ids = [f"historia_00012:celular:p0{n}" for n in range(1, 6)]
        texto = relatorios.confiabilidade(ficha=_ficha(
            veredito="atencao", alertas=["5 vídeo(s) de historias"],
            num_destino_so={"historias": ids, "builds": []}))
        self.assertIn("p01", texto)
        self.assertIn("…", texto)
        self.assertNotIn("p05", texto)


class AsFalhasDosDoisDestinos(unittest.TestCase):

    def _texto(self, **falhas):
        return relatorios.confiabilidade(ficha=_ficha(
            veredito="atencao", alertas=["algo"], **falhas))

    def test_mostra_as_duas_plataformas(self):
        texto = self._texto(falhas_tiktok=2, falhas_youtube=1)
        self.assertIn("TikTok 2x", texto)
        self.assertIn("YouTube 1x", texto)

    def test_so_a_que_falhou_aparece(self):
        texto = self._texto(falhas_youtube=3)
        self.assertIn("YouTube 3x", texto)
        self.assertNotIn("TikTok", texto)

    def test_ficha_antiga_sem_o_campo_novo_nao_quebra(self):
        # Ficha anterior a 3b07c4e so tinha `falhas_tiktok`.
        texto = self._texto(falhas_tiktok=1)
        self.assertIn("TikTok 1x", texto)

    def test_sem_falha_nenhuma_nao_ha_linha(self):
        self.assertNotIn("falhas ao publicar", self._texto())


class AFonteQuebrada(unittest.TestCase):

    def test_montar_nunca_levanta(self):
        real = relatorios.RELATORIOS["confiabilidade"]

        def explode(_agora=None):
            raise OSError("ledger ilegivel")

        relatorios.RELATORIOS["confiabilidade"] = explode
        self.addCleanup(lambda: relatorios.RELATORIOS.__setitem__(
            "confiabilidade", real))
        texto = relatorios.montar("confiabilidade")
        self.assertIn("falhou", texto)


class OComando(unittest.TestCase):

    def test_esta_na_tabela_fechada(self):
        self.assertIs(comandos.TABELA["confiabilidade"],
                      comandos.confiabilidade)
        self.assertIs(comandos.TABELA["prova"], comandos.confiabilidade)

    def test_a_ajuda_lista_o_comando(self):
        self.assertIn("/confiabilidade", comandos.ajuda())


class NaoSaiSozinho(unittest.TestCase):

    def test_nao_esta_no_horario_padrao(self):
        # Decisao pendente do Adrian (16/09/2026): o comando responde quando
        # perguntado, mas o envio automatico diario so liga quando ele
        # escolher. Ligar aqui faria o bot mandar mensagem real sem ninguem
        # ter decidido isso.
        self.assertNotIn("confiabilidade",
                         config.PADRAO.get("relatorios") or {})


if __name__ == "__main__":
    unittest.main()
