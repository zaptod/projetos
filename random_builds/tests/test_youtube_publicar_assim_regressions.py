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

    def test_clique_que_falha_NAO_devolve_o_link_da_pagina_de_tras(self):
        """Auditoria de 11/10/2026 (prova2): com o aviso na tela e o
        `click()` levantando, a mesma volta caia na checagem dos sinais; o
        dialogo por tras mostra "Link do video", a funcao devolvia a URL e o
        video entrava no ledger como publicado — e no canal ficava RASCUNHO.
        Medido: `_confirmar -> 'https://youtu.be/AbCdEfGhIjK'`, `confirmado
        -> True`. Agora: tenta de novo ate o prazo e, com o aviso ainda la,
        devolve a frase de RASCUNHO."""
        pagina = PaginaFalsa(
            aviso=True,
            texto="Vídeo publicado\nLink do vídeo\nPublicar mesmo assim",
            link="https://youtu.be/AbCdEfGhIjK")

        def nao_clica():
            raise RuntimeError("backdrop engoliu o clique")
        pagina.depois_do_clique = nao_clica
        estado, registro = _confirmar(pagina, espera=3.0)
        self.assertFalse(youtube_web.confirmado(estado), estado)
        self.assertNotIn("youtu.be", estado)
        self.assertIn("RASCUNHO", estado)
        self.assertTrue(any("nao consegui clicar" in l for l in registro), registro)

    def test_clique_que_falha_uma_vez_e_passa_na_seguinte_confirma(self):
        pagina = PaginaFalsa(
            aviso=True,
            texto="Vídeo publicado\nPublicar mesmo assim",
            texto_apos="Vídeo publicado",
            link="https://youtu.be/AbCdEfGhIjK")
        fechar = PaginaFalsa.depois_do_clique
        tentativas = []

        def falha_so_na_primeira():
            tentativas.append(1)
            if len(tentativas) == 1:
                raise RuntimeError("backdrop engoliu o clique")
            fechar(pagina)
        pagina.depois_do_clique = falha_so_na_primeira
        estado, _ = _confirmar(pagina, espera=8.0)
        self.assertEqual("https://youtu.be/AbCdEfGhIjK", estado)
        self.assertEqual(2, len(tentativas))

    def test_o_rotulo_dentro_do_botao_esta_nos_seletores(self):
        """O texto nao esta no <button>, e sim num <div> dentro dele — foi
        assim que o "Publicar agora" do TikTok escapou em 31/08/2026."""
        juntos = " ".join(youtube_web.BOTAO_PUBLICAR_ASSIM)
        self.assertIn("button-text-content", juntos)
        self.assertIn("Publicar mesmo assim", juntos)
        self.assertIn("Publish anyway", juntos)


class DepoisDoCliqueTests(unittest.TestCase):
    """A prova do clique no laudo do YouTube, como o TikTok ja fazia
    (auditoria de 11/10/2026, prova4: `youtube_web.py grava laudo["clicou"]?
    False`; `classificar('', falha, laudo do YouTube) -> falha`).

    Exceção DEPOIS do clique (em 05/10 foi o `progresso` levantando) apagava
    a frase, a ficha virava falha comum e a fila reescolhia o video no
    horario seguinte: rascunho gemeo ou duplicata.
    """

    def setUp(self):
        from builds.publicar import desfecho
        self.marcas = []
        self.addCleanup(setattr, desfecho, "resolver", desfecho.resolver)
        desfecho.resolver = (
            lambda canal, video, estado, laudo=None, falha=None, plataforma="tiktok":
            self.marcas.append((canal, video.id, estado, dict(laudo or {}),
                                plataforma)) or desfecho.classificar(estado, falha, laudo))
        self.video = type("V", (), {"id": "generation_00099:duelo:celular"})()

    def test_o_laudo_ganha_clicou_antes_do_clique(self):
        fonte = Path(youtube_web.__file__).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def publicar("):]
        corpo = corpo[:corpo.index("\ndef ")]
        self.assertIn('laudo["clicou"] = True', corpo)
        self.assertLess(corpo.index('laudo["clicou"] = True'),
                        corpo.index("pronto.click()"))
        self.assertIn("_depois_do_clique(page, passo, laudo, canal, video)", corpo)

    def test_excecao_depois_do_clique_marca_a_conferir_e_sobe(self):
        pagina = PaginaFalsa(aviso=False, texto="Vídeo publicado",
                             link="https://youtu.be/AbCdEfGhIjK")
        laudo = {"clicou": True, "youtube_id": "", "url": ""}

        def passo(texto):
            if texto.startswith("publicar clicado"):
                raise RuntimeError("o diario nao aceitou a linha")
        with self.assertRaises(RuntimeError):
            youtube_web._depois_do_clique(pagina, passo, laudo, "builds", self.video)
        (marca,) = self.marcas
        self.assertEqual(("builds", self.video.id, "youtube"),
                         (marca[0], marca[1], marca[4]))
        self.assertIn("pode estar no ar", marca[2])
        self.assertEqual("sem_confirmacao", laudo["estado"])
        from builds.publicar import desfecho
        self.assertEqual("sem_confirmacao",
                         desfecho.classificar("", {"tipo": "RuntimeError"}, laudo))

    def test_caminho_bom_segue_igual(self):
        pagina = PaginaFalsa(aviso=False, texto="Vídeo publicado",
                             link="https://youtu.be/AbCdEfGhIjK")
        laudo = {"clicou": True, "youtube_id": "", "url": ""}
        antes = youtube_web.ESPERA_CONFIRMAR_S
        youtube_web.ESPERA_CONFIRMAR_S = 3.0
        self.addCleanup(setattr, youtube_web, "ESPERA_CONFIRMAR_S", antes)
        estado = youtube_web._depois_do_clique(pagina, lambda _t: None, laudo,
                                               "builds", self.video)
        self.assertEqual("https://youtu.be/AbCdEfGhIjK", estado)
        self.assertEqual("publicado", laudo["estado"])
        self.assertEqual("AbCdEfGhIjK", laudo["youtube_id"])
        self.assertEqual("publicado", laudo["desfecho"])
        self.assertEqual(1, len(self.marcas))

    def test_marca_que_nao_grava_nao_esconde_a_excecao_original(self):
        from builds.publicar import desfecho

        def nao_marca(*a, **k):
            raise desfecho.NaoConsegviMarcar("a trava esta ocupada")
        desfecho.resolver = nao_marca
        pagina = PaginaFalsa(aviso=False, texto="Vídeo publicado")
        laudo = {"clicou": True, "youtube_id": "", "url": ""}

        def passo(_texto):
            raise RuntimeError("original")
        with self.assertRaises(RuntimeError) as caso:
            youtube_web._depois_do_clique(pagina, passo, laudo, "builds", self.video)
        self.assertEqual("original", str(caso.exception))


if __name__ == "__main__":
    unittest.main()
