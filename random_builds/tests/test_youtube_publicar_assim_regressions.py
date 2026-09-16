"""O aviso "Publicar mesmo assim" do Studio, e os 30 rascunhos que ele criou.

15/09/2026, canal Neural fights: 30 rascunhos na aba Shorts, 29 deles com um
gemeo publicado — um por postagem, todo dia, desde 10/09. O Adrian percebeu
porque estava perdendo views.

O QUE ACONTECIA. No instante em que o codigo achava que tinha publicado, o
Studio abria um aviso com o botao "Publicar mesmo assim" (aparece com o video
ainda processando, e mais ainda quando ha pouco texto e a publicacao e
publica). O `_confirmar` nunca clicou em nada: ele so procurava texto de
sucesso. E aqui esta a parte cruel — com o aviso aberto, a pagina ATRAS ja
mostra "video publicado", entao a funcao devolvia SUCESSO, o ledger registrava
a postagem, a janela fechava e o video ficava como RASCUNHO. Video que ninguem
viu, contado como publicado.

O ROTULO E UM `div` DENTRO DO BOTAO, o que ja tinha nos enganado uma vez no
TikTok ("Publicar agora", 31/08/2026):

    <div class="ytcpButtonShapeImpl__button-text-content">Publicar mesmo assim</div>

Por isso este arquivo existe: o mesmo erro voltou num segundo publicador.
"""
from __future__ import annotations

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from builds.publicar import youtube_web                           # noqa: E402


class LocalizadorFalso:
    def __init__(self, pagina, existe: bool, rotulo: str = ""):
        self._pagina = pagina
        self._existe = existe
        self._rotulo = rotulo

    @property
    def first(self):
        return self

    def count(self):
        return 1 if self._existe else 0

    def wait_for(self, **_kw):
        if not self._existe:
            raise RuntimeError("nao esta na tela")

    def get_attribute(self, _nome):
        return self._pagina.link

    def click(self, **_kw):
        self._pagina.cliques.append(self._rotulo or "assim")
        self._pagina.depois_do_clique()


class PaginaFalsa:
    """So o que `_confirmar` usa: locator, evaluate e o texto da pagina."""

    def __init__(self, *, aviso: bool, texto: str, texto_apos: str | None = None,
                 link: str | None = None):
        self.aviso = aviso
        self.texto = texto
        self._apos = texto_apos
        self.link = link
        self.cliques: list[str] = []

    def depois_do_clique(self):
        self.aviso = False
        if self._apos is not None:
            self.texto = self._apos

    def locator(self, seletor: str):
        if "mesmo assim" in seletor or "anyway" in seletor.lower():
            return LocalizadorFalso(self, self.aviso, "assim")
        if "href" in seletor:
            return LocalizadorFalso(self, self.link is not None, "link")
        return LocalizadorFalso(self, False)

    def evaluate(self, _js):
        return self.texto


def _confirmar(pagina, espera: float = 6.0):
    registro: list[str] = []
    antes = youtube_web.ESPERA_CONFIRMAR_S
    youtube_web.ESPERA_CONFIRMAR_S = espera
    try:
        estado = youtube_web._confirmar(pagina, registro.append)
    finally:
        youtube_web.ESPERA_CONFIRMAR_S = antes
    return estado, registro


class PublicarMesmoAssimTests(unittest.TestCase):
    def test_clica_no_aviso_em_vez_de_deixar_virar_rascunho(self):
        pagina = PaginaFalsa(
            aviso=True,
            texto="Publicar mesmo assim",
            texto_apos="Vídeo publicado")
        estado, registro = _confirmar(pagina)
        self.assertEqual(["assim"], pagina.cliques)
        self.assertTrue(youtube_web.confirmado(estado), estado)
        self.assertIn("confirmacao extra", estado)
        self.assertTrue(any("mesmo assim" in l for l in registro), registro)

    def test_o_aviso_vem_ANTES_da_prova_de_sucesso(self):
        """A ordem e a coisa toda.

        Com o aviso aberto, a pagina de tras JA diz "video publicado". Se a
        prova fosse conferida primeiro, a funcao devolveria sucesso sem clicar
        — que e exatamente o que produziu os 30 rascunhos.
        """
        pagina = PaginaFalsa(
            aviso=True,
            texto="Vídeo publicado\nPublicar mesmo assim",
            texto_apos="Vídeo publicado")
        estado, _ = _confirmar(pagina)
        self.assertEqual(["assim"], pagina.cliques,
                         "devolveu sucesso sem clicar no aviso")
        self.assertIn("confirmacao extra", estado)

    def test_sem_aviso_nada_muda(self):
        pagina = PaginaFalsa(aviso=False, texto="Vídeo publicado")
        estado, _ = _confirmar(pagina)
        self.assertTrue(youtube_web.confirmado(estado))
        self.assertEqual([], pagina.cliques)
        self.assertNotIn("confirmacao extra", estado)

    def test_aviso_que_nao_sai_vira_FALHA_e_fala_em_rascunho(self):
        """Nao adianta clicar se o Studio nao publicar: quem le tem que saber
        onde procurar o video."""
        pagina = PaginaFalsa(aviso=True, texto="Publicar mesmo assim")
        pagina.depois_do_clique = lambda: None      # o aviso nao sai
        estado, _ = _confirmar(pagina, espera=3.0)
        self.assertFalse(youtube_web.confirmado(estado), estado)
        self.assertIn("RASCUNHO", estado)

    def test_o_rotulo_dentro_do_botao_esta_nos_seletores(self):
        """O texto nao esta no <button>, e sim num <div> dentro dele — foi
        assim que o "Publicar agora" do TikTok escapou em 31/08/2026."""
        juntos = " ".join(youtube_web.BOTAO_PUBLICAR_ASSIM)
        self.assertIn("button-text-content", juntos)
        self.assertIn("Publicar mesmo assim", juntos)
        self.assertIn("Publish anyway", juntos)


if __name__ == "__main__":
    unittest.main()
