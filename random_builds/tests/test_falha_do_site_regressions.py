# -*- coding: utf-8 -*-
"""O cartao de falha do PicassoIA: o site ja respondeu, pare de esperar.

Em 09/09/2026 o Adrian mandou o icone: `lucide-image` quebrado, pintado de
`text-destructive`. E o cartao que o site poe NO LUGAR da imagem quando a
geracao morre do lado dele.

O detector ja existia. `JS_BLOQUEIO` devolvia o sinal separado do escudo
(`escudo: false`) e o comentario dele ja dizia por que a diferenca importa:

    ESCUDO             bloqueio de CONTEUDO — reescrever o prompt resolve.
    text-destructive   "deu ruim" (credito, rede, o que for) — reescrever
                       NAO adianta.

So que ninguem usava a distincao: `_recusou` descartava o sinal quando nao
era escudo, e a espera seguia ate estourar o timeout **com a resposta ja na
tela**. 180 s olhando um cartao de erro.

O que este arquivo trava:

1. FALHA DO SITE PARA A ESPERA NA HORA, e para com `EsperaEstourou` — que e
   a excecao que `_gerar_esperando` REENVIA. Reenviar e o certo aqui: a falha
   e do site, nao do prompt.
2. O ESCUDO NAO ENTRA POR AQUI. Ele e recusa de conteudo e sai por
   `_recusou`, com outra resposta (suavizar/reescrever).
3. O CARTAO VELHO NAO CONTA. A pagina e a mesma da cena anterior: se ela
   terminou em erro, o cartao ainda esta la quando a proxima espera comeca.
4. DUAS VOLTAS SEGUIDAS. O cartao pisca durante o carregamento; desistir no
   primeiro relance jogaria fora imagem boa.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from builds.identity import picasso_client
from builds.identity.client import EsperaEstourou

RAIZ = Path(__file__).resolve().parents[2]
FONTE = (RAIZ / "random_builds" / "builds" / "identity"
         / "picasso_client.py").read_text(encoding="utf-8")


class PaginaFalsa:
    def __init__(self):
        self.fechada = False

    def is_closed(self):
        return self.fechada

    def locator(self, _seletor):
        class _Vazio:
            def count(self_inner):
                return 0
        return _Vazio()

    def wait_for_timeout(self, _ms):
        pass


def _cliente(sinais, resultados=None):
    """Cliente com `bloqueio_na_tela` roteirizado, uma resposta por volta."""
    cliente = picasso_client.PicassoClient.__new__(picasso_client.PicassoClient)
    cliente.page = PaginaFalsa()
    cliente.ajustes = {"render_timeout": 30, "poll_interval": 0}
    import random
    cliente.rng = random.Random(0)
    cliente._modal_fechado = 0

    fila = list(sinais)
    cliente._falha_do_site = lambda: (fila.pop(0) if fila else "")
    cliente._recusou = lambda: None
    cliente._tirar_parede_da_frente = lambda: ""
    cliente._checar_vivo = lambda: None
    return cliente


class FalhaDoSiteTests(unittest.TestCase):
    def _esperar(self, cliente, resultados=()):
        original = picasso_client.selectors.resultados_na_tela
        picasso_client.selectors.resultados_na_tela = lambda _p: list(resultados)
        try:
            return cliente.wait_for_render(timeout=5)
        finally:
            picasso_client.selectors.resultados_na_tela = original

    def test_falha_repetida_para_a_espera(self):
        cliente = _cliente(["", "Erro ao gerar", "Erro ao gerar"])
        with self.assertRaises(EsperaEstourou) as caso:
            self._esperar(cliente)
        self.assertIn("marcou esta geracao como falha", str(caso.exception))
        self.assertIn("Erro ao gerar", str(caso.exception))

    def test_um_relance_so_NAO_desiste(self):
        """O cartao pisca no carregamento; a imagem boa vem logo depois."""
        cliente = _cliente(["Erro ao gerar", "", "", "", "", "", ""])
        imagem = {"src": "https://picassoia/nova.png", "w": 1088, "h": 1920}
        self.assertEqual("https://picassoia/nova.png",
                         self._esperar(cliente, [imagem]))

    def test_cartao_que_JA_estava_na_tela_e_ignorado(self):
        """Sobra da cena anterior: a pagina e a mesma."""
        velho = "Erro ao gerar"
        cliente = _cliente([velho] * 8)
        imagem = {"src": "https://picassoia/nova.png", "w": 1088, "h": 1920}
        self.assertEqual("https://picassoia/nova.png",
                         self._esperar(cliente, [imagem]))


class SeparacaoDosSinaisTests(unittest.TestCase):
    def test_o_escudo_NAO_sai_por_falha_do_site(self):
        """Escudo e recusa de conteudo: a resposta e reescrever, nao reenviar."""
        cliente = picasso_client.PicassoClient.__new__(
            picasso_client.PicassoClient)
        cliente.page = PaginaFalsa()
        original = picasso_client.selectors.bloqueio_na_tela
        picasso_client.selectors.bloqueio_na_tela = lambda _p: {
            "escudo": True, "texto": "CONTEUDO ILEGAL"}
        try:
            self.assertEqual("", cliente._falha_do_site())
        finally:
            picasso_client.selectors.bloqueio_na_tela = original

    def test_destructive_sem_escudo_e_falha_do_site(self):
        cliente = picasso_client.PicassoClient.__new__(
            picasso_client.PicassoClient)
        cliente.page = PaginaFalsa()
        original = picasso_client.selectors.bloqueio_na_tela
        picasso_client.selectors.bloqueio_na_tela = lambda _p: {
            "escudo": False, "texto": "  Erro   ao gerar  "}
        try:
            self.assertEqual("Erro ao gerar", cliente._falha_do_site())
        finally:
            picasso_client.selectors.bloqueio_na_tela = original

    def test_tela_limpa_nao_e_falha(self):
        cliente = picasso_client.PicassoClient.__new__(
            picasso_client.PicassoClient)
        cliente.page = PaginaFalsa()
        original = picasso_client.selectors.bloqueio_na_tela
        picasso_client.selectors.bloqueio_na_tela = lambda _p: None
        try:
            self.assertEqual("", cliente._falha_do_site())
        finally:
            picasso_client.selectors.bloqueio_na_tela = original


class ReenvioTests(unittest.TestCase):
    def test_a_excecao_escolhida_e_a_que_o_worker_REENVIA(self):
        """`EsperaEstourou` e o que `_gerar_esperando` tenta de novo."""
        trecho = FONTE[FONTE.index("def wait_for_render("):]
        alvo = trecho[trecho.index("falha = self._falha_do_site()"):]
        self.assertIn("raise EsperaEstourou(", alvo[:600])

    def test_a_checagem_vem_ANTES_de_procurar_imagem(self):
        """Procurar imagem numa tela de erro e so gastar volta."""
        trecho = FONTE[FONTE.index("def wait_for_render("):]
        self.assertLess(trecho.index("falha = self._falha_do_site()"),
                        trecho.index("resultados_na_tela"))


if __name__ == "__main__":
    unittest.main()
