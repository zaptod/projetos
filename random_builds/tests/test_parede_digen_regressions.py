# -*- coding: utf-8 -*-
"""A parede do Digen: o modal de propaganda que engole o clique.

Por que existe (28/09/2026). As 04:03 o payoff da generation_00085 falhou
tres vezes com o mesmo log:

    Locator.click: Timeout 30000ms exceeded
    - waiting for locator("[aria-placeholder^="Describe your video"]")
    - <img alt="Upgrade" src=".../pc-pop-916.webp"/> from
      <div role="dialog" ... data-slot="dialog-content"> intercepts

Olhando a TELA as 07:55: a propaganda "20% OFF Real Motion 3.5 Fast" aparece
SOZINHA 10-15 s depois de a pagina carregar, com overlay `fixed inset-0`, e
fecha pelo X (`button[data-slot="dialog-close"]`). A licao e a da parede do
PicassoIA (09/09): fechar so ao abrir nao basta — ela aparece depois.

O que este arquivo trava:
1. `tirar_parede_da_frente` fecha pelo X (forcado), cai no ESC e, se nada
   fechar, AVISA e devolve "" — nunca levanta.
2. O seletor da parede e o modal do shadcn, e NAO os popovers de modelo,
   duracao e anexo (que tambem sao `role=dialog` e fecha-los desfaria o
   preset).
3. O cliente instala o guarda do Playwright (`add_locator_handler`) ao
   nascer, e o guarda chama o mesmo fechamento.
4. Antes de cada clique do fluxo (New Space, composer, anexo, escrever,
   enviar, download) e dentro da espera, ha uma chamada explicita.
"""
from __future__ import annotations

import inspect
import unittest
from unittest import mock

from builds.identity import client, selectors


class _Botao:
    def __init__(self, dono, fecha=True, visivel=True):
        self.dono, self.fecha, self.visivel = dono, fecha, visivel
        self.cliques = []

    def count(self):
        return 1

    @property
    def first(self):
        return self

    def is_visible(self):
        return self.visivel

    def click(self, **kw):
        self.cliques.append(kw)
        if self.fecha:
            self.dono.aberta = False


class _Nada:
    def count(self):
        return 0


class _Parede:
    def __init__(self, pagina, botoes):
        self.pagina, self.botoes = pagina, botoes

    def count(self):
        return 1 if self.pagina.aberta else 0

    @property
    def first(self):
        return self

    def is_visible(self):
        return self.pagina.aberta

    def inner_text(self, timeout=None):
        return "Upgrade Now  Close"

    def locator(self, seletor):
        return self.botoes.get(seletor, _Nada())


class _Teclado:
    def __init__(self, pagina, fecha):
        self.pagina, self.fecha, self.teclas = pagina, fecha, []

    def press(self, tecla):
        self.teclas.append(tecla)
        if self.fecha and tecla == "Escape":
            self.pagina.aberta = False


class _Pagina:
    """Pagina duble: uma parede aberta, com X que fecha (ou nao)."""

    def __init__(self, x_fecha=True, esc_fecha=True, com_x=True):
        self.aberta = True
        self.x = _Botao(self, fecha=x_fecha)
        botoes = {"button[data-slot='dialog-close']": self.x} if com_x else {}
        self.parede = _Parede(self, botoes)
        self.keyboard = _Teclado(self, esc_fecha)
        self.guardas = []

    def locator(self, seletor):
        if seletor == selectors.PAREDE:
            return self.parede
        return _Nada()

    def add_locator_handler(self, locator, handler, **kw):
        self.guardas.append((locator, handler))


class FecharAParede(unittest.TestCase):

    def setUp(self):
        dorme = mock.patch.object(client.time, "sleep")
        dorme.start()
        self.addCleanup(dorme.stop)

    def test_fecha_pelo_x_forcado_e_devolve_o_texto(self):
        pagina = _Pagina()
        texto = client.tirar_parede_da_frente(pagina, espera=0.1)
        self.assertEqual("Upgrade Now Close", texto)
        self.assertFalse(pagina.aberta)
        # `force`: o X mora DENTRO da parede; sem forcar, o proprio guarda do
        # Playwright seria chamado para a acao de fechar.
        self.assertTrue(pagina.x.cliques[0].get("force"))
        self.assertEqual([], pagina.keyboard.teclas)

    def test_x_que_nao_fecha_cai_no_esc(self):
        pagina = _Pagina(x_fecha=False)
        self.assertEqual("Upgrade Now Close",
                         client.tirar_parede_da_frente(pagina, espera=0.1))
        self.assertEqual(["Escape"], pagina.keyboard.teclas)

    def test_sem_x_vai_direto_ao_esc(self):
        pagina = _Pagina(com_x=False)
        self.assertEqual("Upgrade Now Close",
                         client.tirar_parede_da_frente(pagina, espera=0.1))
        self.assertFalse(pagina.aberta)

    def test_parede_que_nao_fecha_avisa_e_nao_levanta(self):
        pagina = _Pagina(x_fecha=False, esc_fecha=False)
        with mock.patch("builtins.print") as fala:
            self.assertEqual("", client.tirar_parede_da_frente(pagina,
                                                               espera=0.1))
        self.assertIn("NAO fecha", " ".join(str(c) for c in fala.call_args_list))

    def test_sem_parede_nao_clica_em_nada(self):
        pagina = _Pagina()
        pagina.aberta = False
        self.assertEqual("", client.tirar_parede_da_frente(pagina))
        self.assertEqual([], pagina.x.cliques)
        self.assertEqual([], pagina.keyboard.teclas)

    def test_pagina_sem_locator_nao_quebra(self):
        # Os dubles antigos da suite nao tem `locator`: "nao sei" e "sem
        # parede", nunca excecao no meio do fluxo.
        class Velha:
            url = "https://digen.ai/en/space"
        self.assertEqual("", client.tirar_parede_da_frente(Velha()))
        self.assertFalse(client.instalar_guarda(Velha()))


class OSeletorEOModalNaoOPopover(unittest.TestCase):

    def test_so_o_modal_do_shadcn(self):
        self.assertIn("data-slot='dialog-content'", selectors.PAREDE)
        self.assertIn("role='dialog'", selectors.PAREDE)
        # Popover de modelo/duracao/anexo e `popover-content`: nao pode casar.
        self.assertNotIn("popover", selectors.PAREDE)
        self.assertNotEqual("[role='dialog']", selectors.PAREDE.strip())

    def test_o_x_do_shadcn_vem_primeiro(self):
        self.assertEqual("button[data-slot='dialog-close']",
                         selectors.FECHAR_PAREDE[0])


class OGuardaDoPlaywright(unittest.TestCase):

    def setUp(self):
        dorme = mock.patch.object(client.time, "sleep")
        dorme.start()
        self.addCleanup(dorme.stop)

    def test_o_cliente_instala_o_guarda_ao_nascer(self):
        pagina = _Pagina()
        cliente = client.DigenClient(None, pagina, {})
        self.assertTrue(cliente.guarda_instalado)
        self.assertEqual(1, len(pagina.guardas))
        locator, handler = pagina.guardas[0]
        self.assertIs(pagina.parede, locator)
        # O guarda e o mesmo fechamento: chamado, a parede some.
        handler(locator)
        self.assertFalse(pagina.aberta)

    def test_guarda_tambem_aceita_ser_chamado_sem_argumento(self):
        pagina = _Pagina()
        client.instalar_guarda(pagina)
        pagina.guardas[0][1]()
        self.assertFalse(pagina.aberta)


class AntesDeCadaClique(unittest.TestCase):
    """A chamada explicita existe em cada ponto do fluxo que clica. O guarda
    do Playwright cobre o resto, mas depende do driver; esta camada nao."""

    def _antes(self, metodo, marco):
        fonte = inspect.getsource(metodo)
        self.assertIn("tirar_parede_da_frente(", fonte, metodo.__name__)
        self.assertLess(fonte.index("tirar_parede_da_frente("),
                        fonte.index(marco), metodo.__name__)

    def test_new_space(self):
        self._antes(client.DigenClient.novo_espaco, "BOTAO_NOVO_ESPACO")

    def test_anexo(self):
        self._antes(client.DigenClient.anexar_referencias,
                    "referencias.anexar(")

    def test_escrever_e_enviar(self):
        fonte = inspect.getsource(client.DigenClient.submit_prompt)
        chamadas = [i for i in range(len(fonte))
                    if fonte.startswith("tirar_parede_da_frente(", i)]
        self.assertLess(chamadas[0], fonte.index("escrever(page, campo"))
        self.assertLess(fonte.index("botao.is_disabled()"), chamadas[-1])
        self.assertLess(chamadas[-1], fonte.index("botao.click()"))

    def test_durante_a_espera_e_no_download(self):
        self._antes(client.DigenClient.wait_for_render, "selectors.GERANDO")
        self._antes(client.DigenClient.download, "_liberar_botao_de_download")

    def test_composer(self):
        self._antes(client.DigenClient._limpar_composer, "campo.click()")


if __name__ == "__main__":
    unittest.main()
