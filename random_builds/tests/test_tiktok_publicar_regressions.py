# -*- coding: utf-8 -*-
"""Contratos da publicação no TikTok: a confirmação e a PROVA.

O caso real (31/08/2026, relatado pelo Adrian): quando o fluxo vai rápido, o
TikTok abre um segundo botão — `<div class="TUXButton-label">Publicar
agora</div>` — e sem clicar nele o vídeo NÃO sobe. Pior: o código clicava em
"Publicar", dormia 15 s e devolvia "publicado no TikTok" sem olhar a tela.
Uma promessa, não um fato: o vídeo ficava parado no modal e o painel
registrava sucesso.

O que este arquivo trava:

1. O modal de confirmação é clicado quando aparece (em português e inglês, e
   pelo rótulo TUX que é um `div` dentro do botão).
2. Sem prova de sucesso, a função DIZ que não conseguiu confirmar. Nunca
   inventa "publicado".
3. Quando não há modal (fluxo normal), nada quebra e o sucesso é detectado.

Rode de dentro de random_builds/:
    python -m unittest tests.test_tiktok_publicar_regressions -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from builds.publicar import tiktok                                 # noqa: E402


class LocalizadorFalso:
    def __init__(self, pagina, existe: bool):
        self._pagina = pagina
        self._existe = existe

    @property
    def first(self):
        return self

    def count(self):
        return 1 if self._existe else 0

    def wait_for(self, **_kw):
        if not self._existe:
            raise RuntimeError("nao esta na tela")

    def click(self, **_kw):
        self._pagina.cliques.append("confirmar")
        self._pagina.depois_do_clique()


class PaginaFalsa:
    """So o que o fluxo de publicacao usa: locator, url e evaluate."""

    def __init__(self, *, modal: str | None = None, texto: str = "",
                 url: str = "https://www.tiktok.com/tiktokstudio/upload",
                 texto_apos_clique: str | None = None,
                 url_apos_clique: str | None = None):
        self.modal = modal
        self.texto = texto
        self.url = url
        self._texto_apos = texto_apos_clique
        self._url_apos = url_apos_clique
        self.cliques: list[str] = []

    def depois_do_clique(self):
        if self._texto_apos is not None:
            self.texto = self._texto_apos
        if self._url_apos is not None:
            self.url = self._url_apos

    def locator(self, seletor: str):
        achou = self.modal is not None and self.modal in seletor
        return LocalizadorFalso(self, achou)

    def evaluate(self, _js):
        return self.texto


def _publicar(pagina, espera=0.2):
    registro: list[str] = []
    estado = tiktok._confirmar_publicacao(pagina, registro.append, espera=espera)
    return estado, registro


class ConfirmacaoTests(unittest.TestCase):
    def test_clica_no_publicar_agora_em_portugues(self):
        pagina = PaginaFalsa(
            modal="Publicar agora",
            texto_apos_clique="Seu vídeo está sendo enviado")
        estado, registro = _publicar(pagina, espera=5)
        self.assertEqual(["confirmar"], pagina.cliques)
        self.assertIn("publicado no TikTok", estado)
        self.assertIn("confirmacao extra", estado)
        self.assertTrue(any("Publicar agora" in linha for linha in registro))

    def test_clica_no_post_now_em_ingles(self):
        pagina = PaginaFalsa(
            modal='Post now',
            texto_apos_clique="Your video is being uploaded")
        estado, _ = _publicar(pagina, espera=5)
        self.assertEqual(["confirmar"], pagina.cliques)
        self.assertIn("publicado no TikTok", estado)

    def test_o_rotulo_tux_tambem_serve(self):
        """O texto vive num div DENTRO do botao; clicar nele sobe pro botao."""
        pagina = PaginaFalsa(
            modal='div.TUXButton-label:has-text("Publicar agora")',
            texto_apos_clique="Vídeo publicado")
        estado, _ = _publicar(pagina, espera=5)
        self.assertEqual(["confirmar"], pagina.cliques)
        self.assertIn("publicado", estado)

    def test_sem_modal_o_fluxo_normal_funciona(self):
        pagina = PaginaFalsa(texto="Seu vídeo está sendo enviado")
        estado, _ = _publicar(pagina, espera=5)
        self.assertEqual([], pagina.cliques)
        self.assertEqual("publicado no TikTok", estado)

    def test_redirecionar_para_fora_do_upload_conta_como_sucesso(self):
        pagina = PaginaFalsa(url="https://www.tiktok.com/tiktokstudio/content")
        pagina.url = "https://www.tiktok.com/tiktokstudio/upload"
        pagina.texto = ""
        pagina.modal = "Publicar agora"
        pagina._url_apos = "https://www.tiktok.com/tiktokstudio/content"
        estado, _ = _publicar(pagina, espera=5)
        self.assertIn("publicado no TikTok", estado)


class HonestidadeTests(unittest.TestCase):
    """O ponto do conserto: nao dizer que publicou quando nao publicou."""

    def test_sem_prova_nenhuma_admite_que_nao_confirmou(self):
        pagina = PaginaFalsa(texto="Enviar vídeo   Rascunhos")
        estado, _ = _publicar(pagina, espera=0.5)
        self.assertNotIn("publicado no TikTok", estado)
        self.assertIn("nao confirmou", estado)

    def test_confirmou_mas_sem_sucesso_diz_para_conferir(self):
        pagina = PaginaFalsa(modal="Publicar agora", texto="")
        estado, _ = _publicar(pagina, espera=0.5)
        self.assertEqual(["confirmar"], pagina.cliques)
        self.assertIn("Confira o perfil", estado)
        self.assertNotIn("publicado no TikTok", estado)

    def test_pagina_que_explode_nao_vira_sucesso(self):
        class Morta(PaginaFalsa):
            def evaluate(self, _js):
                raise RuntimeError("Execution context was destroyed")

        estado, _ = _publicar(Morta(), espera=0.5)
        self.assertIn("nao confirmou", estado)


class ConfirmadoTests(unittest.TestCase):
    """Quem chama precisa PERGUNTAR se publicou, nao adivinhar pelo texto.

    `historias/publicar/serie.py` registra o retorno como se fosse a URL da
    publicacao — sem este marcador, um "nao consegui confirmar" entrava no
    `publicados.jsonl` como sucesso e a parte nunca mais seria tentada.
    """

    def test_so_o_sucesso_e_confirmado(self):
        self.assertTrue(tiktok.confirmado(tiktok.SUCESSO))
        self.assertTrue(tiktok.confirmado(
            tiktok.SUCESSO + " (com a confirmacao extra)"))

    def test_duvida_nao_e_confirmacao(self):
        for estado in ("cliquei em publicar, mas o TikTok nao confirmou.",
                       "cliquei em publicar e na confirmacao, mas o TikTok "
                       "nao mostrou o aviso de sucesso.",
                       "vídeo carregado e legenda escrita; a publicação final "
                       "ficou com você",
                       "", None):
            self.assertFalse(tiktok.confirmado(estado), repr(estado))

    def test_o_fluxo_devolve_frases_que_a_checagem_entende(self):
        pagina = PaginaFalsa(texto="Seu vídeo está sendo enviado")
        estado, _ = _publicar(pagina, espera=5)
        self.assertTrue(tiktok.confirmado(estado))
        duvida, _ = _publicar(PaginaFalsa(texto="Rascunhos"), espera=0.5)
        self.assertFalse(tiktok.confirmado(duvida))


class SeletoresTests(unittest.TestCase):
    def test_a_lista_cobre_os_dois_idiomas_e_o_data_e2e(self):
        junto = " ".join(tiktok.BOTAO_CONFIRMAR)
        self.assertIn("Publicar agora", junto)
        self.assertIn("Post now", junto)
        self.assertIn("TUXButton-label", junto)
        self.assertIn("data-e2e", junto)

    def test_sinais_de_sucesso_sem_acento(self):
        """A comparacao normaliza acento: o banco tem que estar normalizado."""
        for sinal in tiktok.SINAIS_DE_SUCESSO:
            self.assertEqual(tiktok._sem_acento(sinal), sinal,
                             f"{sinal!r} nunca casaria")


if __name__ == "__main__":
    unittest.main()
