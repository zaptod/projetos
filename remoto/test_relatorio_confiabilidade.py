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

    def test_falha_de_teste_descartada_e_dita(self):
        texto = self._texto(falhas_ignoradas=[
            {"ref": "trava:build:celular"}, {"ref": "trava:build:celular"}])
        self.assertIn("2 falha(s) de teste fora da conta", texto)
        self.assertIn("trava:build:celular", texto)
        self.assertEqual(1, texto.count("trava:build:celular"))


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


class SaiSozinhoSoAs2230(unittest.TestCase):
    """Decisao do Adrian (16/09/2026, 18:58): liga o envio diario as 22:30.

    Ate essa decisao este teste travava o contrario — que o relatorio NAO
    saisse sozinho —, porque ligar sem ninguem decidir faria o bot mandar
    mensagem real. Agora trava o estado decidido, e nada alem dele.
    """

    def test_confiabilidade_sai_as_2230(self):
        self.assertEqual("22:30", config.PADRAO["relatorios"]["confiabilidade"])

    def test_os_automaticos_sao_exatamente_estes(self):
        # Um quarto relatorio automatico e mais uma mensagem por dia no
        # celular dele: tem de ser decisao, nao efeito colateral.
        self.assertEqual({"metas": "21:00", "funcionamento": "09:00",
                          "confiabilidade": "22:30"},
                         config.PADRAO["relatorios"])

    def test_o_horario_vence_uma_vez_por_dia(self):
        from datetime import datetime
        horarios = config.PADRAO["relatorios"]
        antes = relatorios.devidos(horarios, datetime(2026, 9, 16, 22, 29),
                                   ja_enviados={"metas": "2026-09-16",
                                                "funcionamento": "2026-09-16"})
        depois = relatorios.devidos(horarios, datetime(2026, 9, 16, 22, 31),
                                    ja_enviados={"metas": "2026-09-16",
                                                 "funcionamento": "2026-09-16"})
        ja_foi = relatorios.devidos(horarios, datetime(2026, 9, 16, 23, 0),
                                    ja_enviados={"metas": "2026-09-16",
                                                 "funcionamento": "2026-09-16",
                                                 "confiabilidade": "2026-09-16"})
        self.assertNotIn("confiabilidade", antes)
        self.assertEqual(["confiabilidade"], depois)
        self.assertEqual([], ja_foi)


if __name__ == "__main__":
    unittest.main()
