# -*- coding: utf-8 -*-
"""O "Fazer upgrade" fixo do rodape nao e motivo de falha (30/09/2026).

Medido: dois pedidos ao ChatGPT pela Vila (`82e154e4` 16:44:05 -> 16:44:49 e
`5030f732` 16:47:23 -> 16:48:03) falharam em segundos com
`erro: "o site diz: «Fazer upgrade»"`, `categoria: "upgrade"`. O Adrian mandou
o MESMO pedido direto no app e gerou normalmente. A conta e Free e o rodape da
pagina tem SEMPRE o botao "Fazer upgrade" (ficha do ChatGPT, fonte adrian,
29/09 02:10); a do Gemini tem "Faca upgrade para o Google AI Pro" na barra
lateral. O carteiro passava `document.body.innerText` INTEIRO para
`motivo_da_tela`, e `catalogo.varrer` casava a linha do botao: qualquer falha
do ChatGPT virava "upgrade" e a excecao de verdade sumia.

Conserto: o classificador so le o que a pagina GANHOU desde o envio
(`catalogo.linhas_novas`, por contagem) — a resposta do nosso turno e o aviso
que surgiu depois. Nenhum teste abre navegador nem toca o `%LOCALAPPDATA%`.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from ias import carteiro as carteiro_mod, catalogo, correio, imagem

# a pagina do ChatGPT Free como o innerText a le (rodape e topo fixos)
PAGINA_CHATGPT = (
    "Novo chat\nBuscar em chats\nBiblioteca\nSora\nGPTs\nChats\n"
    "Sprite sheet de projétil\nGato laranja\n"
    "Adrian Oliveira\nFree\nFazer upgrade\n"
    "ChatGPT\nVer planos\n"
    "O ChatGPT pode cometer erros. Confira informações importantes.")
PAGINA_GEMINI = (
    "Gemini\nNova conversa\nGems\nRecentes\nFaça upgrade para o Google AI Pro\n"
    "Configurações e ajuda\nPergunte ao Gemini")
PROMPT = "Create a professional 2D game projectile sprite sheet for:\n\nStone Boulder"


class LLMFalhou(RuntimeError):
    """Mesmo nome da excecao do cliente das historias."""


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._antes = os.environ.get("NF_IAS_PASTA")
        os.environ["NF_IAS_PASTA"] = str(Path(self._tmp.name) / "ias")

    def tearDown(self):
        if self._antes is None:
            os.environ.pop("NF_IAS_PASTA", None)
        else:
            os.environ["NF_IAS_PASTA"] = self._antes
        self._tmp.cleanup()


@contextmanager
def _trava_livre(nome, esperar=0.0):
    yield True


def _carteiro(fabrica):
    return carteiro_mod.Carteiro(
        fabrica_de_sessao=fabrica, fabrica_imagem=imagem.fabrica_imagem_duble(),
        trava=_trava_livre, nome_da_trava=lambda ia: f"perfil__{ia}__teste",
        avisar=lambda *a, **k: None, avisar_arquivo=lambda *a, **k: None,
        log=lambda m: None, dormir=lambda s: None,
        ajustes={"janela_conversa_s": 0, "resumo_a_cada": 50, "espera_conta_max_s": 100,
                 "rodizio_imagem": ["picasso", "gemini", "grok", "chatgpt"],
                 "cota_pausa_h": 6})


# ======================================================= o defeito, isolado
class ODefeitoReproduzido(unittest.TestCase):
    def test_a_pagina_inteira_diz_upgrade_mesmo_com_resposta_normal(self):
        """E o que o carteiro fazia: a pagina inteira no classificador."""
        depois = PAGINA_CHATGPT + "\n" + PROMPT + "\nImagem criada\nEditar imagem"
        categoria, motivo = carteiro_mod.classificar_erro(
            "chatgpt", LLMFalhou("o prompt nao entrou no editor"), depois)
        self.assertEqual(categoria, "upgrade")
        self.assertIn("Fazer upgrade", motivo)

    def test_so_o_que_surgiu_depois_do_envio_nao_diz_upgrade(self):
        depois = PAGINA_CHATGPT + "\n" + PROMPT + "\nImagem criada\nEditar imagem"
        novo = catalogo.linhas_novas([PAGINA_CHATGPT, PROMPT], depois)
        self.assertNotIn("Fazer upgrade", novo)
        categoria, motivo = carteiro_mod.classificar_erro(
            "chatgpt", LLMFalhou("o prompt nao entrou no editor"), novo)
        self.assertEqual(categoria, "erro")
        self.assertIn("LLMFalhou: o prompt nao entrou no editor", motivo)


# ================================================================ linhas novas
class LinhasNovas(unittest.TestCase):
    def test_caso_zero(self):
        self.assertEqual(catalogo.linhas_novas("", ""), "")
        self.assertEqual(catalogo.linhas_novas(None, None), "")
        self.assertEqual(catalogo.linhas_novas(PAGINA_CHATGPT, PAGINA_CHATGPT), "")

    def test_sem_antes_tudo_e_novo(self):
        self.assertEqual(catalogo.linhas_novas("", "a\nb"), "a\nb")

    def test_conta_repeticao_o_aviso_repetido_na_resposta_fica(self):
        depois = PAGINA_CHATGPT + "\nFazer upgrade"
        self.assertEqual(catalogo.linhas_novas(PAGINA_CHATGPT, depois), "Fazer upgrade")

    def test_espaco_e_caixa_nao_contam_e_lista_de_antes(self):
        novo = catalogo.linhas_novas(["  FAZER   upgrade ", "x"], "Fazer upgrade\nx\ny")
        self.assertEqual(novo, "y")


# ============================================ limite de verdade e borda de palavra
class LimiteDeVerdade(unittest.TestCase):
    def test_limites_reconhecidos(self):
        for frase in ("Você atingiu o limite do plano Free para geração de imagens",
                      "Você atingiu o limite de imagens. Faça upgrade para o ChatGPT Plus",
                      "Limite do plano Free atingido",
                      "You've hit the Free plan limit for image generation requests",
                      "You've reached your image creation limit"):
            self.assertEqual(catalogo.classificar(frase), "limite", frase)

    def test_upgrade_com_borda_de_palavra(self):
        self.assertEqual(catalogo.classificar("Fazer upgrade"), "upgrade")
        self.assertEqual(catalogo.classificar("Faça upgrade para o Google AI Pro"), "upgrade")
        for frase in ("refazer upgrade", "fazer upgrades em lote", "casino credits"):
            self.assertIsNone(catalogo.classificar(frase), frase)


# ============================================================ o carteiro
class CarteiroLeSoONossoTurno(_Base):
    def test_conversa_que_falha_com_rodape_upgrade_mostra_a_excecao_real(self):
        """O caso de 30/09 (5030f732): conversa, rodape fixo, falha no envio."""
        fabrica = carteiro_mod.fabrica_duble(
            tela_antes=PAGINA_CHATGPT, tela=PAGINA_CHATGPT + "\n" + PROMPT,
            falhar=LLMFalhou("o prompt nao entrou no editor (o campo continua vazio)"))
        c = _carteiro(fabrica)
        correio.enviar("chatgpt", PROMPT)
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertNotEqual(fim["categoria"], "upgrade")
        self.assertNotIn("Fazer upgrade", fim["erro"])
        self.assertIn("o prompt nao entrou no editor", fim["erro"])

    def test_gemini_barra_lateral_nao_vira_upgrade(self):
        fabrica = carteiro_mod.fabrica_duble(
            tela_antes=PAGINA_GEMINI, tela=PAGINA_GEMINI + "\n" + PROMPT,
            falhar=LLMFalhou("nao respondeu"))
        c = _carteiro(fabrica)
        correio.enviar("gemini", PROMPT)
        fim = c.uma_volta()
        self.assertNotEqual(fim["categoria"], "upgrade")
        self.assertIn("LLMFalhou: nao respondeu", fim["erro"])

    def test_pagina_com_rodape_e_imagem_gerada_e_sucesso(self):
        fabrica = carteiro_mod.fabrica_duble(
            tela_antes=PAGINA_CHATGPT,
            tela=PAGINA_CHATGPT + "\n" + PROMPT + "\nImagem criada")
        c = _carteiro(fabrica)
        m = correio.pedir_imagem("chatgpt", PROMPT, proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "respondida")
        self.assertTrue(correio.arquivo_da_imagem("chatgpt", m["id"]).is_file())

    def test_imagem_que_falha_com_rodape_nao_e_upgrade(self):
        fabrica = carteiro_mod.fabrica_duble(
            tela_antes=PAGINA_CHATGPT, tela=PAGINA_CHATGPT + "\nCriando imagem",
            imagem_falhar=LLMFalhou("cliquei em enviar e o turno nao apareceu"))
        c = _carteiro(fabrica)
        correio.pedir_imagem("chatgpt", PROMPT, proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertNotEqual(fim["categoria"], "upgrade")
        self.assertIn("o turno nao apareceu", fim["erro"])

    def test_limite_dentro_da_resposta_continua_limite(self):
        aviso = ("Você atingiu o limite do plano Free para geração de imagens. "
                 "Faça upgrade para o ChatGPT Plus ou tente depois das 18:40.")
        fabrica = carteiro_mod.fabrica_duble(
            tela_antes=PAGINA_CHATGPT, tela=PAGINA_CHATGPT + "\n" + PROMPT + "\n" + aviso,
            imagem_falhar=LLMFalhou("a resposta veio sem imagem"))
        c = _carteiro(fabrica)
        correio.pedir_imagem("chatgpt", PROMPT, proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["categoria"], "limite")
        self.assertIn("atingiu o limite do plano Free", fim["erro"])

    def test_dialogo_de_upgrade_que_surgiu_depois_continua_upgrade(self):
        fabrica = carteiro_mod.fabrica_duble(
            tela_antes=PAGINA_CHATGPT,
            tela=PAGINA_CHATGPT + "\n" + PROMPT + "\nFaça upgrade para o ChatGPT Plus\nFazer upgrade",
            falhar=LLMFalhou("nada mudou"))
        c = _carteiro(fabrica)
        correio.enviar("chatgpt", PROMPT)
        fim = c.uma_volta()
        self.assertEqual(fim["categoria"], "upgrade")


# ========================================================= a sessao real
class _Pagina:
    def __init__(self, telas):
        self.telas = list(telas)
        self.url = "https://chatgpt.com/c/x"

    def evaluate(self, js):
        return self.telas.pop(0) if len(self.telas) > 1 else self.telas[0]


class _Cliente:
    provedor = "chatgpt"

    def __init__(self, page, falhar):
        self.page = page
        self.sel = {"anexo_prova": []}
        self.falhar = falhar
        self.log = print

    def perguntar(self, texto, anexos=None):
        raise self.falhar


class SessaoRealFotografaAntes(unittest.TestCase):
    def test_sem_envio_nao_le_a_pagina(self):
        sessao = carteiro_mod.SessaoReal(_Cliente(_Pagina([PAGINA_CHATGPT]), None),
                                         log=lambda m: None)
        self.assertEqual(sessao.texto_do_turno(), "")
        self.assertEqual(carteiro_mod.tela_do_turno(sessao), "")

    def test_perguntar_fotografa_a_pagina_antes_do_envio(self):
        depois = PAGINA_CHATGPT + "\n" + PROMPT + "\nAlgo deu errado (1155)"
        cliente = _Cliente(_Pagina([PAGINA_CHATGPT, depois]), LLMFalhou("x"))
        sessao = carteiro_mod.SessaoReal(cliente, log=lambda m: None)
        with self.assertRaises(LLMFalhou):
            sessao.perguntar(PROMPT)
        self.assertEqual(sessao.texto_do_turno(), "Algo deu errado (1155)")
        cat, motivo = carteiro_mod.classificar_erro("chatgpt", LLMFalhou("x"),
                                                    carteiro_mod.tela_do_turno(sessao))
        self.assertEqual(cat, "erro_site")

    def test_dubles_antigos_sem_texto_do_turno_leem_o_visivel(self):
        sessao = imagem.SessaoImagemDuble("picasso", tela="Algo deu errado")
        self.assertEqual(carteiro_mod.tela_do_turno(sessao), "Algo deu errado")

    def test_picasso_sem_pedido_nao_le_a_pagina(self):
        s = imagem.SessaoPicasso(cliente=None, ajustes={}, config={}, log=lambda m: None)
        self.assertEqual(s.texto_do_turno(), "")


if __name__ == "__main__":
    unittest.main()
