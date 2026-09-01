# -*- coding: utf-8 -*-
"""Criar -> Enviar videos: os dois passos que faltavam para ser automatico.

O que estava errado: `/videos/upload` parecia ser a tela de envio, mas nao e.
Ela so FILTRA a lista de videos do canal. Medido em 01/09/2026 na sessao de
verdade: o campo de arquivo era 0 ali, e virava 1 depois de clicar em Criar
e em "Enviar videos". Sem esses dois passos o robo procurava para sempre um
campo que nunca ia existir.

Dois caminhos, os dois testados no navegador:

- `?d=ud` na URL abre o dialogo direto, sem clique nenhum;
- sem o parametro, os cliques abrem — e ficam de reserva, porque `d=ud` nao
  e documentado e pode sumir.

Rode de dentro de random_builds/:
    python -m unittest tests.test_abrir_upload_regressions -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.publicar import youtube_web                            # noqa: E402


class PaginaFalsa:
    """Um Studio de mentira: conta quantos campos de arquivo existem."""

    def __init__(self, campos=0, aparece_apos=None):
        self.campos = campos
        self.aparece_apos = aparece_apos   # nome do clique que faz aparecer
        self.cliques = []

    def locator(self, _seletor):
        pagina = self

        class Alvo:
            @staticmethod
            def count():
                return pagina.campos
        return Alvo()

    def clicou(self, qual):
        self.cliques.append(qual)
        if self.aparece_apos == qual:
            self.campos = 1


class Botao:
    def __init__(self, pagina, nome):
        self.pagina, self.nome = pagina, nome

    def click(self):
        self.pagina.clicou(self.nome)


class AbrirDialogoTests(unittest.TestCase):
    def setUp(self):
        # Sem isto cada teste esperaria 20 s pelo dialogo.
        anterior = youtube_web.ESPERA_DIALOGO_S
        youtube_web.ESPERA_DIALOGO_S = 0.05
        self.addCleanup(
            lambda: setattr(youtube_web, "ESPERA_DIALOGO_S", anterior))
        self.linhas = []

    def _com_primeiro(self, resposta):
        """Troca `_primeiro` por um que devolve o que o teste mandar."""
        original = youtube_web._primeiro
        youtube_web._primeiro = resposta
        self.addCleanup(lambda: setattr(youtube_web, "_primeiro", original))

    def test_dialogo_ja_aberto_nao_clica_em_nada(self):
        """Com `?d=ud` o campo ja esta la; clicar seria mexer a toa."""
        pagina = PaginaFalsa(campos=1)
        self._com_primeiro(lambda *a, **k: self.fail("nao devia procurar botao"))
        self.assertTrue(
            youtube_web._abrir_dialogo_de_upload(pagina, self.linhas.append))
        self.assertEqual([], pagina.cliques)

    def test_sem_dialogo_clica_criar_e_enviar(self):
        pagina = PaginaFalsa(campos=0, aparece_apos="enviar")

        def primeiro(_page, seletores, **_kw):
            qual = ("criar" if seletores is youtube_web.BOTAO_CRIAR
                    else "enviar")
            return Botao(pagina, qual)

        self._com_primeiro(primeiro)
        self.assertTrue(
            youtube_web._abrir_dialogo_de_upload(pagina, self.linhas.append))
        self.assertEqual(["criar", "enviar"], pagina.cliques)

    def test_sem_o_botao_criar_ele_desiste_em_vez_de_travar(self):
        pagina = PaginaFalsa(campos=0)
        self._com_primeiro(lambda *a, **k: None)
        self.assertFalse(
            youtube_web._abrir_dialogo_de_upload(pagina, self.linhas.append))

    def test_clicou_mas_o_campo_nao_veio_e_falha(self):
        """Clicar nao e sucesso; sucesso e o campo aparecer."""
        pagina = PaginaFalsa(campos=0, aparece_apos="nunca")

        def primeiro(_page, seletores, **_kw):
            return Botao(pagina, "criar" if seletores is youtube_web.BOTAO_CRIAR
                         else "enviar")

        self._com_primeiro(primeiro)
        self.assertFalse(
            youtube_web._abrir_dialogo_de_upload(pagina, self.linhas.append))


class SeletoresTests(unittest.TestCase):
    def test_o_item_por_TEXTO_vem_antes_do_posicional(self):
        """`#text-item-1` do mesmo menu e "Transmitir ao vivo".

        Se o posicional viesse primeiro e o YouTube trocasse a ordem, o robo
        abriria uma LIVE em vez de um upload. Errar assim e muito pior do
        que nao achar o botao.
        """
        primeiro = youtube_web.MENU_ENVIAR_VIDEOS[0]
        self.assertIn("has-text", primeiro)
        self.assertNotIn("text-item-0", primeiro)
        self.assertIn("tp-yt-paper-item#text-item-0",
                      youtube_web.MENU_ENVIAR_VIDEOS)

    def test_criar_procura_pelo_rotulo_nos_dois_idiomas(self):
        junto = " ".join(youtube_web.BOTAO_CRIAR)
        self.assertIn("Criar", junto)
        self.assertIn("Create", junto)

    def test_enviar_videos_nos_dois_idiomas(self):
        junto = " ".join(youtube_web.MENU_ENVIAR_VIDEOS)
        self.assertIn("Enviar vídeos", junto)
        self.assertIn("Upload videos", junto)


class UrlTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from src import contas
        from src.publicar import youtube_web as yw
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        anterior = contas.ARQUIVO
        contas.ARQUIVO = str(Path(pasta.name) / "contas.json")
        self.addCleanup(lambda: setattr(contas, "ARQUIVO", anterior))
        yw.usar_canal("builds", {"nome": "Neural fights",
                                 "arroba": "Neural_fights",
                                 "id": "UCA3Y1SaahhDsMj4JKGLbQ-Q"})

    def test_a_url_ja_pede_o_dialogo(self):
        url = youtube_web.url_de_upload("builds")
        self.assertIn(youtube_web.PARAMETRO_DIALOGO, url)

    def test_o_parametro_nao_atrapalha_a_leitura_do_id(self):
        """A trava do canal le o id DESSA url; se quebrar, ela para tudo."""
        url = youtube_web.url_de_upload("builds")
        self.assertEqual("UCA3Y1SaahhDsMj4JKGLbQ-Q",
                         youtube_web.id_do_canal(url))


class PublicarAvisaTests(unittest.TestCase):
    def test_publicar_para_com_recado_util_se_o_envio_nao_abrir(self):
        fonte = Path(youtube_web.__file__).read_text(encoding="utf-8")
        i = fonte.index("def publicar(")
        trecho = fonte[i:i + 5000]
        self.assertIn("_abrir_dialogo_de_upload(page, passo)", trecho)
        self.assertIn("so", trecho)
        self.assertIn("--sondar", trecho)


if __name__ == "__main__":
    unittest.main()
