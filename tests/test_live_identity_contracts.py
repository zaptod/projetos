"""Contratos do nome de espectador que vai para a tela.

O nome de exibicao e conteudo de terceiro renderizado numa transmissao
monetizada. Estes testes fixam o que a sanitizacao remove, quando ela desiste e
cai no fallback, e a separacao entre o nome que o motor usa como chave e o texto
que o publico ve.

Todo caractere invisivel aparece aqui como escape (``\\u200b`` e afins) de
proposito: um teste sobre caracteres que nao se ve nao pode depender de eles
sobreviverem a um copiar-e-colar.
"""

from __future__ import annotations

import unittest

from neural_fights.live.identity import (
    LIMITE_DISPLAY,
    PREFIXO_CATALOGO,
    catalog_name_de,
    eh_lutador_de_espectador,
    handle_de,
    resolver_display_name,
    sanitizar_display_name,
)

ZERO_WIDTH_SPACE = "​"
ZERO_WIDTH_JOINER = "‍"
RTL_OVERRIDE = "‮"
LTR_OVERRIDE = "‭"
ISOLATE_FIRST = "⁦"
ISOLATE_POP = "⁩"
ACENTO_COMBINANTE = "́"


def sanitizar(bruto, **kwargs):
    kwargs.setdefault("fallback", "FALLBACK")
    return sanitizar_display_name(bruto, **kwargs)


class NomeAceitoTests(unittest.TestCase):
    def test_nome_comum_passa_intacto(self) -> None:
        resultado = sanitizar("Ana Clara")
        self.assertEqual(resultado.valor, "Ana Clara")
        self.assertFalse(resultado.alterado)
        self.assertFalse(resultado.usou_fallback)

    def test_acentuacao_e_preservada(self) -> None:
        """Publico brasileiro: recusar acento tornaria o recurso inutil."""
        self.assertEqual(sanitizar("José Antônio").valor, "José Antônio")
        self.assertEqual(sanitizar("Conceição").valor, "Conceição")

    def test_digitos_sao_aceitos(self) -> None:
        self.assertEqual(sanitizar("Player 42").valor, "Player 42")

    def test_espacos_sao_colapsados(self) -> None:
        self.assertEqual(sanitizar("  Ana   Clara  ").valor, "Ana Clara")


class AbusoDeUnicodeTests(unittest.TestCase):
    def test_zero_width_e_removido(self) -> None:
        """Invisivel no chat, mas quebraria comparacao e moderacao."""
        self.assertEqual(sanitizar(f"Ana{ZERO_WIDTH_SPACE}Clara").valor, "AnaClara")
        self.assertEqual(sanitizar(f"Ana{ZERO_WIDTH_JOINER}Clara").valor, "AnaClara")

    def test_sobrescrita_bidirecional_e_removida(self) -> None:
        """RTL override inverte a ordem do texto renderizado na tela."""
        for controle in (RTL_OVERRIDE, LTR_OVERRIDE, ISOLATE_FIRST, ISOLATE_POP):
            with self.subTest(controle=repr(controle)):
                self.assertNotIn(controle, sanitizar(f"{controle}anA").valor)

    def test_zalgo_nao_vaza_para_fora_da_linha(self) -> None:
        resultado = sanitizar("a" + ACENTO_COMBINANTE * 30)
        self.assertLessEqual(len(resultado.valor), LIMITE_DISPLAY)
        self.assertTrue(resultado.alterado)

    def test_controles_c0_sao_removidos(self) -> None:
        self.assertEqual(sanitizar("Ana\x00\x07\x1b").valor, "Ana")

    def test_emoji_e_removido(self) -> None:
        self.assertEqual(sanitizar("Ana \U0001f600\U0001f525").valor, "Ana")

    def test_pontuacao_e_markup_nao_passam(self) -> None:
        """Pontuacao serve para imitar outro espectador e para poluir o HUD."""
        self.assertEqual(sanitizar("<script>x</script>").valor, "scriptxscript")
        self.assertNotIn("<", sanitizar("<b>Ana</b>").valor)

    def test_nome_e_truncado_no_limite(self) -> None:
        resultado = sanitizar("A" * 100)
        self.assertEqual(len(resultado.valor), LIMITE_DISPLAY)
        self.assertTrue(resultado.alterado)


class FallbackTests(unittest.TestCase):
    def test_nome_que_esvazia_cai_no_fallback_com_motivo(self) -> None:
        vazios = ("", "   ", f" {ZERO_WIDTH_SPACE}", "\U0001f525\U0001f525", None, 42)
        for bruto in vazios:
            with self.subTest(bruto=repr(bruto)):
                resultado = sanitizar(bruto)
                self.assertEqual(resultado.valor, "FALLBACK")
                self.assertEqual(resultado.motivo, "vazio_apos_sanitizacao")

    def test_blocklist_recusa_e_diz_o_motivo(self) -> None:
        resultado = sanitizar("Ana Golpista", blocklist=["golpista"])
        self.assertEqual(resultado.valor, "FALLBACK")
        self.assertEqual(resultado.motivo, "blocklist")

    def test_blocklist_ignora_caixa(self) -> None:
        self.assertEqual(sanitizar("ANA GOLPISTA", blocklist=["Golpista"]).motivo, "blocklist")

    def test_blocklist_nao_e_burlada_por_caractere_invisivel(self) -> None:
        """A comparacao acontece depois da limpeza, nao antes."""
        disfarcado = f"gol{ZERO_WIDTH_SPACE}pista"
        self.assertEqual(sanitizar(disfarcado, blocklist=["golpista"]).motivo, "blocklist")

    def test_termo_vazio_na_blocklist_e_ignorado(self) -> None:
        self.assertEqual(sanitizar("Ana", blocklist=["", "  "]).valor, "Ana")

    def test_original_e_sempre_preservado_para_auditoria(self) -> None:
        bruto = f"{RTL_OVERRIDE}anA"
        self.assertEqual(sanitizar(bruto).original, bruto)


class HandleTests(unittest.TestCase):
    def test_handle_e_deterministico_e_seguro(self) -> None:
        gerado = handle_de("UC-abc", "youtube")
        self.assertEqual(gerado, handle_de("UC-abc", "youtube"))
        self.assertTrue(gerado.isascii())
        self.assertEqual(sanitizar(gerado).valor, gerado[:LIMITE_DISPLAY])

    def test_handle_separa_plataformas(self) -> None:
        self.assertNotEqual(handle_de("id", "youtube"), handle_de("id", "tiktok"))

    def test_resolver_usa_o_handle_como_fallback(self) -> None:
        resultado = resolver_display_name(
            "\U0001f525", viewer_id="UC-abc", platform="youtube"
        )
        self.assertEqual(resultado.valor, handle_de("UC-abc", "youtube"))


class CatalogNameTests(unittest.TestCase):
    def test_catalog_name_usa_prefixo_reservado(self) -> None:
        nome = catalog_name_de("a3f2c1")
        self.assertTrue(nome.startswith(PREFIXO_CATALOGO))
        self.assertTrue(eh_lutador_de_espectador(nome))

    def test_gerador_de_roster_nunca_produz_o_prefixo(self) -> None:
        """Garante que colisao com o catalogo curado e impossivel."""
        from neural_fights.tools.gerador_database import gerar_nome_personagem

        for _ in range(200):
            self.assertFalse(gerar_nome_personagem().startswith(PREFIXO_CATALOGO))

    def test_roster_curado_nao_colide_com_o_espaco_de_espectador(self) -> None:
        from neural_fights.data import database

        for personagem in database.carregar_personagens():
            self.assertFalse(eh_lutador_de_espectador(personagem.nome))

    def test_catalog_name_exige_id(self) -> None:
        with self.assertRaises(ValueError):
            catalog_name_de("  ")


if __name__ == "__main__":
    unittest.main()
