# -*- coding: utf-8 -*-
"""A parede do PicassoIA: um dialogo por cima engole o clique.

Em 09/09/2026 o site passou a abrir uma parede de PROMOCAO no meio da fila de
imagens. O Playwright registrou o efeito com todas as letras:

    <div data-slot="dialog-overlay" class="fixed inset-0 z-50 bg-black/60">
         intercepts pointer events
    Locator.click: Timeout 10000ms exceeded
      - waiting for locator("#submit-button")

Nao era lentidao do site nem recusa de conteudo: era uma camada preta por
cima de tudo. E o codigo ja sabia fechar dialogo — `_fechar_modal_de_login`
existe desde 29/08 —, so que:

1. so era chamado ao ABRIR a pagina, e a parede aparece DEPOIS, entre uma
   cena e outra;
2. exigia um `svg.lucide-x` dentro do dialogo, e esta parede se apresentava
   com uma seta vermelha (`lucide-arrow-right`).

Isso tambem explica, em retrospecto, o padrao que eu havia medido como "a
imagem que falha NUNCA volta, fica os 600 s inteiros": ela nao estava
demorando, estava atras de um aviso que ninguem fechava. E explica por que
REENVIAR resolvia em 9 s — o reenvio passava pela abertura, que fechava.

O que este arquivo trava:

1. A DETECCAO E LARGA. Qualquer `role="dialog"` visivel e parede, com ou sem
   `lucide-x`.
2. A PAREDE SAI ANTES DO CLIQUE, em `submit_prompt` — nao adianta fechar so
   ao abrir a pagina.
3. E SAI TAMBEM DURANTE A ESPERA, mas DEPOIS da checagem de recusa: o escudo
   do filtro de conteudo tambem mora num dialogo, e fechar antes de olhar
   apagaria o motivo real.
4. ESC E A SEGUNDA SAIDA. Os dialogos do site sao Radix (fecham no ESC), e o
   proprio overlay pode estar cobrindo o X.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from builds.identity import picasso_client

RAIZ = Path(__file__).resolve().parents[2]
FONTE = (RAIZ / "random_builds" / "builds" / "identity"
         / "picasso_client.py").read_text(encoding="utf-8")


class LocalizadorFalso:
    def __init__(self, quantos=1, visivel=True, texto="Assine o plano PRO"):
        self._quantos = quantos
        self._visivel = visivel
        self._texto = texto
        self.cliques = 0

    def count(self):
        return self._quantos

    @property
    def first(self):
        return self

    def is_visible(self):
        return self._visivel

    def inner_text(self, timeout=None):
        return self._texto

    def click(self, timeout=None):
        self.cliques += 1


class TecladoFalso:
    def __init__(self):
        self.teclas = []

    def press(self, tecla):
        self.teclas.append(tecla)


class PaginaFalsa:
    """Uma pagina com parede que some depois de N tentativas de fechar."""

    def __init__(self, fecha_com=None, texto="Assine o plano PRO"):
        self.fecha_com = fecha_com          # "x" | "esc" | None
        self.texto = texto
        self.aberta = True
        self.keyboard = TecladoFalso()
        self.botao = LocalizadorFalso(texto=texto)

    def locator(self, seletor):
        if "dialog" in seletor and "button" not in seletor:
            return LocalizadorFalso(quantos=1 if self.aberta else 0,
                                    visivel=self.aberta, texto=self.texto)
        if self.fecha_com == "x" and self.aberta:
            class _Botao(LocalizadorFalso):
                def click(_s, timeout=None):
                    self.aberta = False
            return _Botao(texto=self.texto)
        return LocalizadorFalso(quantos=0, visivel=False)


def _cliente(page):
    cliente = picasso_client.PicassoClient.__new__(
        picasso_client.PicassoClient)
    cliente.page = page
    import random
    cliente.rng = random.Random(0)
    return cliente


class DeteccaoTests(unittest.TestCase):
    def test_dialogo_sem_lucide_x_TAMBEM_e_parede(self):
        """A parede de promocao se apresentava com uma seta, nao com um X."""
        cliente = _cliente(PaginaFalsa(fecha_com=None))
        self.assertIsNotNone(cliente._parede_visivel())

    def test_pagina_limpa_nao_tem_parede(self):
        pagina = PaginaFalsa()
        pagina.aberta = False
        self.assertIsNone(_cliente(pagina)._parede_visivel())

    def test_pagina_limpa_devolve_texto_vazio(self):
        pagina = PaginaFalsa()
        pagina.aberta = False
        self.assertEqual("", _cliente(pagina)._tirar_parede_da_frente())


class FechamentoTests(unittest.TestCase):
    def test_o_X_fecha_e_o_texto_volta(self):
        """O texto volta para o log distinguir promocao de limite de plano."""
        cliente = _cliente(PaginaFalsa(fecha_com="x", texto="Assine o PRO"))
        self.assertEqual("Assine o PRO", cliente._tirar_parede_da_frente())

    def test_ESC_e_a_segunda_saida(self):
        """O overlay pode estar cobrindo o proprio X."""
        pagina = PaginaFalsa(fecha_com="esc")

        teclado = pagina.keyboard
        original = teclado.press

        def press(tecla):
            original(tecla)
            if tecla == "Escape":
                pagina.aberta = False
        teclado.press = press

        cliente = _cliente(pagina)
        self.assertTrue(cliente._tirar_parede_da_frente())
        self.assertIn("Escape", teclado.teclas)

    def test_parede_que_nao_fecha_devolve_vazio_e_nao_levanta(self):
        """Ela nao pode derrubar a fila: a proxima cena ainda pode passar."""
        cliente = _cliente(PaginaFalsa(fecha_com=None))
        self.assertEqual("", cliente._tirar_parede_da_frente())


class OndeEChamadoTests(unittest.TestCase):
    def _corpo(self, nome: str) -> str:
        inicio = FONTE.index(f"def {nome}(")
        fim = FONTE.find("\n    def ", inicio + 10)
        return FONTE[inicio:fim if fim > 0 else len(FONTE)]

    def test_sai_antes_do_clique_de_enviar(self):
        """O overlay engolia o clique no #submit-button por 10 s."""
        corpo = self._corpo("submit_prompt")
        self.assertIn("_tirar_parede_da_frente()", corpo)
        self.assertLess(corpo.index("_tirar_parede_da_frente()"),
                        corpo.index("BOTAO_GERAR"))

    def test_sai_tambem_logo_antes_do_clique(self):
        """A parede pode aparecer DEPOIS de tirar no inicio, antes do clique."""
        corpo = self._corpo("submit_prompt")
        # Duas chamadas a _tirar_parede_da_frente: uma no inicio, outra logo
        # antes do botao.click(). A segunda tem que vir depois de
        # _esperar_estabilizar e antes de botao.click.
        self.assertEqual(corpo.count("_tirar_parede_da_frente()"), 2,
                         "submit_prompt deveria chamar _tirar_parede_da_frente "
                         "duas vezes: no inicio e logo antes do clique")
        # Verificar a ordem: _esperar_estabilizar, depois _tirar_parede,
        # depois click.
        idx_estabilizar = corpo.index("_esperar_estabilizar()")
        idx_tirar = corpo.index("_tirar_parede_da_frente()",
                                corpo.index("_tirar_parede_da_frente()") + 1)
        idx_click = corpo.index("botao.click(")
        self.assertLess(idx_estabilizar, idx_tirar,
                        "esperar estabilizar deve vir antes da segunda chamada "
                        "a _tirar_parede")
        self.assertLess(idx_tirar, idx_click,
                        "tirar parede deve vir logo antes do click")

    def test_sai_tambem_durante_a_espera(self):
        """A parede aparece no meio da fila, nao so ao abrir a pagina."""
        self.assertIn("_tirar_parede_da_frente()",
                      self._corpo("wait_for_render"))

    def test_a_recusa_e_olhada_ANTES_de_fechar_a_parede(self):
        """O escudo do filtro tambem e um dialogo: fechar antes apaga o motivo."""
        corpo = self._corpo("wait_for_render")
        self.assertLess(corpo.index("self._recusou()"),
                        corpo.index("_tirar_parede_da_frente()"))

    def test_botao_verif_pos_aprimorador(self):
        """O botao pode ficar desabilitado se aprimorador falhar; aguarda novamente.

        p06_cena_02 (2026-09-11): o botao nunca ficou habilitado na primeira
        tentativa porque o aprimorador de prompt pode desabilitar o form enquanto
        tenta usar. Agora apos _aprimorar() aguarda novamente o botao ficar
        habilitado antes de prosseguir.
        """
        corpo = self._corpo("submit_prompt")
        # Verifica que ha check de botao APOS _aprimorar
        aprimorador_idx = corpo.index("self._aprimorar(")
        botao_check_idx = corpo.index("botao.is_disabled()",
                                       aprimorador_idx)
        ajustar_select_idx = corpo.index('_ajustar_select("proporcao"',
                                          aprimorador_idx)
        # Garantir que o check do botao vem entre aprimorador e ajustar_select
        self.assertLess(aprimorador_idx, botao_check_idx,
                        "botao.is_disabled() deveria estar apos _aprimorar()")
        self.assertLess(botao_check_idx, ajustar_select_idx,
                        "botao.is_disabled() deveria estar antes de _ajustar_select()")

    def test_botao_verif_logo_antes_do_clique(self):
        """O botao pode desabilitar entre estabilizar e clicar; aguarda novamente.

        p06_cena_02 (2026-09-11): o Playwright registrou aria-disabled="true"
        no instante do click. Entre a ultima verificacao (apos aprimorador) e
        o clique, passam operacoes longas (_esperar_estabilizar ate 25s,
        _tirar_parede_da_frente). Se o botao desabilitar ali, tentar clicar
        numa aria-disabled falha em timeout do Playwright (10s), escondendo o
        motivo real. Verificar logo antes do clique evita isso.
        """
        corpo = self._corpo("submit_prompt")
        # Deve haver um check de botao APOS a segunda _tirar_parede_da_frente
        # e ANTES de botao.click()
        segunda_parede_idx = corpo.index("_tirar_parede_da_frente()",
                                         corpo.index("_tirar_parede_da_frente()") + 1)
        click_idx = corpo.index("botao.click(")
        # Procurar por um check do botao entre a segunda parede e o click
        slice_apos_parede = corpo[segunda_parede_idx:click_idx]
        self.assertIn("botao.is_disabled()", slice_apos_parede,
                      "deveria haver check de botao entre tirar parede "
                      "e botao.click()")


if __name__ == "__main__":
    unittest.main()
