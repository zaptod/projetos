# -*- coding: utf-8 -*-
"""O Criar coberto pelo dialogo de envio do proprio Studio (06/10/2026).

O caso medido: na rodada das 00:37 de 06/10 o YouTube de historias falhou com

    TimeoutError: Locator.click: Timeout 30000ms exceeded.
      - waiting for locator("button[aria-label*="Criar" i]").first
        - locator resolved to <button ... aria-label="Criar" aria-disabled="false" ...>

O botao estava HABILITADO. Medido depois, na sessao de verdade do canal de
historias (tres aberturas, sem enviar nada): com o dialogo `?d=ud` aberto, o
elemento por cima do centro do Criar e `tp-yt-iron-overlay-backdrop` — o
backdrop do proprio dialogo. A pagina daquela rodada levou ~126 s para abrir
e montar (181 s de tentativa - 20 s de espera do dialogo - 30 s do clique -
~5 s do Chrome; o normal medido e 8-30 s), o campo de arquivo nao veio em
20 s, e o reserva "Criar -> Enviar videos" era impossivel: o backdrop engolia
o clique. O builds publicou 9 min depois, com o MESMO perfil.

E a falha nao era de rede para a rodada (`postar._e_de_rede`): nem "a pagina
de upload nao carregou" nem o TimeoutError do clique repunham o horario, e
o YouTube de historias ficou vazio no 23:37 e no 00:37.

Rode de dentro de random_builds/:
    python -m unittest tests.test_parede_no_criar_regressions -v
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from builds.publicar import youtube_web

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


class Teclado:
    def __init__(self, pagina):
        self.pagina = pagina

    def press(self, tecla):
        self.pagina.teclas.append(tecla)
        if tecla == "Escape":
            self.pagina.parede = None


class Studio:
    """Um Studio de mentira com o que importa: campo, dialogo e parede.

    `campo_em`: o campo de arquivo aparece na N-esima pergunta (None = nunca).
    `parede`: o dict que `JS_PAREDE_NO_CRIAR` devolveria; o ESC a tira.
    """

    def __init__(self, *, campo_em=None, envio=False, parede=None,
                 clique_engolido=False, campo_apos_enviar=True):
        self.campo_em = campo_em
        self.perguntas = 0
        self.envio = envio
        self.parede = parede
        self.clique_engolido = clique_engolido
        self.campo_apos_enviar = campo_apos_enviar
        self.campo = False
        self.cliques = []
        self.prazos = []
        self.teclas = []
        self.keyboard = Teclado(self)

    def locator(self, _seletor):
        pagina = self

        class Alvo:
            @staticmethod
            def count():
                pagina.perguntas += 1
                if (pagina.campo_em is not None
                        and pagina.perguntas >= pagina.campo_em):
                    pagina.campo = True
                return 1 if pagina.campo else 0
        return Alvo()

    def evaluate(self, _js, _arg=None):
        if self.parede:
            return dict(self.parede, criar=True, envio=self.envio)
        return {"criar": True, "coberto": False, "por": "",
                "envio": self.envio, "texto": ""}


class Botao:
    def __init__(self, pagina, nome):
        self.pagina, self.nome = pagina, nome

    def click(self, **kw):
        self.pagina.prazos.append((self.nome, kw.get("timeout")))
        if self.nome == "criar" and (self.pagina.parede
                                     or self.pagina.clique_engolido):
            # Sem `timeout` o Playwright espera o padrao dele, 30 s: o tempo
            # morto da rodada das 00:37.
            ms = kw.get("timeout", 30000)
            raise TimeoutError(f"Locator.click: Timeout {ms:.0f}ms exceeded.")
        self.pagina.cliques.append(self.nome)
        if self.nome == "enviar" and self.pagina.campo_apos_enviar:
            self.pagina.campo = True


BACKDROP = {"coberto": True, "por": "tp-yt-iron-overlay-backdrop",
            "texto": ""}


class AbrirDialogoComParedeTests(unittest.TestCase):
    def setUp(self):
        _trocar(self, youtube_web, "ESPERA_DIALOGO_S", 0.05)
        _trocar(self, youtube_web, "ESPERA_DIALOGO_CARREGANDO_S", 3.0)
        _trocar(self, youtube_web.time, "sleep", lambda _s: None)
        _trocar(self, youtube_web.escrita, "fotografar",
                lambda _p, rotulo, **_k: f"telas/{rotulo}.png")
        self.linhas = []

    def _botoes(self, pagina):
        def primeiro(_page, seletores, **_kw):
            return Botao(pagina, "criar" if seletores is youtube_web.BOTAO_CRIAR
                         else "enviar")
        _trocar(self, youtube_web, "_primeiro", primeiro)

    def test_dialogo_do_studio_carregando_espera_e_nao_clica(self):
        """O caso das 00:37: dialogo na tela, campo atrasado. Espera; o
        Criar nem e tocado (o backdrop engoliria o clique)."""
        pagina = Studio(envio=True, parede=BACKDROP)
        self._botoes(pagina)
        # O campo chega durante a espera longa (depois que a tela foi lida),
        # nunca na curta.
        ler = pagina.evaluate

        def evaluate(js, arg=None):
            lido = ler(js, arg)
            pagina.campo_em = pagina.perguntas + 2
            return lido
        pagina.evaluate = evaluate
        laudo = {}
        self.assertTrue(youtube_web._abrir_dialogo_de_upload(
            pagina, self.linhas.append, laudo))
        self.assertEqual([], pagina.cliques)
        self.assertEqual([], pagina.teclas)
        self.assertTrue(laudo.get("dialogo_sem_campo"))

    def test_parede_sai_com_esc_antes_do_clique_no_criar(self):
        """Antes: clique direto, 30 s, TimeoutError cru. Agora a parede e
        lida (texto ao laudo, foto) e fechada com ESC, e o clique passa."""
        pagina = Studio(parede={"coberto": True, "por": "tp-yt-paper-dialog",
                                "texto": "Novidades no Studio Entendi"})
        self._botoes(pagina)
        laudo = {}
        self.assertTrue(youtube_web._abrir_dialogo_de_upload(
            pagina, self.linhas.append, laudo))
        self.assertEqual(["Escape"], pagina.teclas)
        self.assertEqual(["criar", "enviar"], pagina.cliques)
        self.assertIn("Novidades no Studio", laudo["parede"])
        self.assertTrue(laudo["tela"].endswith(".png"))
        self.assertTrue(any("por cima do Criar" in l for l in self.linhas))

    def test_clique_engolido_vira_false_com_motivo_e_nao_excecao(self):
        """O TimeoutError do Playwright nao sobe mais cru: vira motivo."""
        pagina = Studio(clique_engolido=True)
        self._botoes(pagina)
        laudo = {}
        self.assertFalse(youtube_web._abrir_dialogo_de_upload(
            pagina, self.linhas.append, laudo))
        self.assertIn("clique no Criar nao passou", laudo["motivo"])
        self.assertIn("TimeoutError", laudo["motivo"])
        self.assertTrue(laudo["tela"])

    def test_clique_no_criar_tem_prazo_de_10_s_e_nao_os_30_do_playwright(self):
        """O prazo e o numero, nao o nome da constante: com `criar.click()`
        (sem prazo) o clique engolido gastava 30 s — 30 de 181 s da rodada
        das 00:37. Conferente de 06/10: tirar o `timeout=` passava 24/24."""
        pagina = Studio(clique_engolido=True)
        self._botoes(pagina)
        laudo = {}
        self.assertFalse(youtube_web._abrir_dialogo_de_upload(
            pagina, self.linhas.append, laudo))
        self.assertEqual([("criar", 10000)], pagina.prazos)
        self.assertIn("TimeoutError", laudo["motivo"])

    def test_clique_que_passa_tambem_leva_o_prazo(self):
        pagina = Studio()
        self._botoes(pagina)
        self.assertTrue(youtube_web._abrir_dialogo_de_upload(
            pagina, self.linhas.append, {}))
        self.assertEqual(("criar", 10000), pagina.prazos[0])

    def test_sem_parede_e_sem_dialogo_o_caminho_antigo_continua(self):
        """Caso ZERO: nada na frente, nenhum dialogo — nenhum ESC."""
        pagina = Studio()
        self._botoes(pagina)
        laudo = {}
        self.assertTrue(youtube_web._abrir_dialogo_de_upload(
            pagina, self.linhas.append, laudo))
        self.assertEqual([], pagina.teclas)
        self.assertEqual(["criar", "enviar"], pagina.cliques)
        self.assertEqual({}, laudo)

    def test_pagina_sem_evaluate_nao_derruba(self):
        """Duble (ou pagina morta) sem `evaluate`: a leitura devolve {}."""
        self.assertEqual({}, youtube_web._parede_no_criar(object()))


class FraseDaFalhaTests(unittest.TestCase):
    def test_caso_medido_das_0037_e_de_rede(self):
        frase = youtube_web.falha_do_envio(
            {"motivo": "o clique no Criar nao passou (TimeoutError)",
             "parede": "tp-yt-iron-overlay-backdrop",
             "tela": "telas/x.png"}, 126.0)
        self.assertTrue(frase.startswith("infraestrutura: "))
        self.assertIn("126 s", frase)
        self.assertIn("tp-yt-iron-overlay-backdrop", frase)
        self.assertIn("Tela: telas/x.png", frase)
        self.assertNotIn("--sondar", frase)

    def test_dialogo_sem_campo_com_pagina_rapida_NAO_e_rede(self):
        """Conferente de 06/10: na sonda de verdade (amostra a cada 0,25 s) o
        campo nasce JUNTO com o dialogo — nenhuma amostra viu dialogo sem
        campo. Dialogo sem campo numa pagina que abriu em 12 s nao tem
        medida de rede atras; se o Studio mudar o campo, chamar isso de rede
        reporia todo horario a toa e esconderia a dica do --sondar."""
        frase = youtube_web.falha_do_envio({"dialogo_sem_campo": True}, 12.0)
        self.assertFalse(frase.startswith("infraestrutura"))
        self.assertIn("--sondar", frase)
        self.assertIn("abriu sem o campo de arquivo", frase)

    def test_dialogo_sem_campo_com_pagina_lenta_e_rede(self):
        frase = youtube_web.falha_do_envio({"dialogo_sem_campo": True}, 126.0)
        self.assertTrue(frase.startswith("infraestrutura: "))
        self.assertNotIn("--sondar", frase)

    def test_borda_do_limiar(self):
        """`lento` e abertura >= 60 s: 59,9 nao e rede, 60,0 e."""
        self.assertFalse(youtube_web.falha_do_envio(
            {"dialogo_sem_campo": True}, 59.9).startswith("infraestrutura"))
        self.assertTrue(youtube_web.falha_do_envio(
            {"dialogo_sem_campo": True}, 60.0).startswith("infraestrutura"))

    def test_pagina_rapida_sem_botao_e_tela_mudada_nao_rede(self):
        """Repetir em 60 s nao muda layout: a frase pede o --sondar."""
        frase = youtube_web.falha_do_envio(
            {"motivo": "o botao Criar nao esta na tela"}, 12.0)
        self.assertFalse(frase.startswith("infraestrutura"))
        self.assertIn("--sondar", frase)

    def test_caso_zero_laudo_vazio(self):
        frase = youtube_web.falha_do_envio({}, 0.0)
        self.assertFalse(frase.startswith("infraestrutura"))
        self.assertIn("nao consegui abrir o envio", frase)

    def test_limiar_de_pagina_lenta(self):
        """Normal medido 8-30 s; a falha, ~126 s."""
        self.assertGreater(youtube_web.PAGINA_LENTA_S, 30.0)
        self.assertLess(youtube_web.PAGINA_LENTA_S, 126.0)

    def test_em_branco_e_de_rede_e_nao_manda_para_botao_que_nao_existe(self):
        frase = youtube_web.falha_da_montagem(47.0, "telas/b.png")
        self.assertTrue(frase.startswith("infraestrutura: "))
        self.assertNotIn("Reparar perfil", frase)
        self.assertIn("Tela: telas/b.png", frase)


class Relogio:
    """`time` do youtube_web: o relogio so anda quando a pagina mexe."""

    def __init__(self):
        self.agora = 1000.0

    def monotonic(self):
        return self.agora

    def time(self):
        return self.agora

    def sleep(self, _s):
        pass


class PaginaDoStudio:
    url = "https://studio.youtube.com/channel/UCteste/videos/upload?d=ud"


class PublicarLigacaoTests(unittest.TestCase):
    """`publicar()` de verdade, com o navegador de mentira: QUANTO a abertura
    mediu e QUAL frase sobe. Conferente de 06/10: o teste antigo lia o fonte
    ("falha_do_envio(envio, abertura_s)" esta escrito la?) e nao media nada.

    O relogio so anda dentro de `_abrir` e `_esperar_montar`: a abertura e
    a soma dos dois e nada mais (o caso das 00:37: ~100 s abrindo, ~26 s
    montando = 126 s).
    """

    def setUp(self):
        import contextlib
        import tempfile
        from builds import contas
        self.relogio = Relogio()
        _trocar(self, youtube_web, "time", self.relogio)
        _trocar(self, youtube_web.atividade, "fabrica",
                lambda *a, **k: contextlib.nullcontext())
        _trocar(self, youtube_web, "contexto_persistente",
                lambda **k: contextlib.nullcontext(object()))
        _trocar(self, youtube_web, "perfil_da_conta", lambda canal: "perfil")
        _trocar(self, youtube_web, "_conta_ativa", lambda canal: "historias")
        _trocar(self, youtube_web, "url_de_upload",
                lambda canal: PaginaDoStudio.url)
        _trocar(self, youtube_web.escrita, "fotografar",
                lambda _p, rotulo, **_k: f"telas/{rotulo}.png")
        _trocar(self, contas, "ativa", lambda *a, **k: "historias")
        _trocar(self, contas, "identidade", lambda *a, **k: {})
        self.abrir_s, self.montar_s, self.montou = 100.0, 26.0, True

        def abrir(_ctx, _url):
            self.relogio.agora += self.abrir_s
            return PaginaDoStudio()

        def montar(_page, *a, **k):
            self.relogio.agora += self.montar_s
            return self.montou
        _trocar(self, youtube_web, "_abrir", abrir)
        _trocar(self, youtube_web, "_esperar_montar", montar)
        self.envio = {}

        def dialogo(_page, _passo, laudo=None):
            # O dialogo gasta o tempo DELE, que nao e abertura.
            self.relogio.agora += 50.0
            laudo.update(self.envio)
            return False
        _trocar(self, youtube_web, "_abrir_dialogo_de_upload", dialogo)
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        arquivo = Path(pasta.name) / "parte.mp4"
        arquivo.write_bytes(b"x")
        self.video = type("V", (), {"id": "historia_x:celular:p02",
                                    "caminho": str(arquivo),
                                    "titulo": "t"})()

    def _publicar(self):
        laudo = {}
        with self.assertRaises(youtube_web.YouTubeWebFalhou) as caso:
            youtube_web.publicar(self.video, config={}, canal="historias",
                                 postar=True, progresso=lambda _t: None,
                                 prova=laudo)
        return str(caso.exception), laudo

    def test_caso_das_0037_abertura_126_s_e_frase_de_rede(self):
        self.envio = {"motivo": "o clique no Criar nao passou (TimeoutError)",
                      "parede": "tp-yt-iron-overlay-backdrop",
                      "dialogo_sem_campo": True}
        frase, laudo = self._publicar()
        self.assertEqual(126.0, laudo["abertura_s"])
        self.assertTrue(frase.startswith("infraestrutura: "), frase)
        self.assertIn("levou 126 s", frase)
        self.assertNotIn("--sondar", frase)
        self.assertEqual("tp-yt-iron-overlay-backdrop",
                         laudo["envio_nao_abriu"]["parede"])
        self.assertTrue(laudo["envio_nao_abriu"]["dialogo_sem_campo"])

    def test_pagina_rapida_com_dialogo_sem_campo_pede_o_sondar(self):
        """12 s de abertura: os 50 s do dialogo NAO contam como abertura."""
        self.abrir_s, self.montar_s = 8.0, 4.0
        self.envio = {"dialogo_sem_campo": True,
                      "motivo": "cliquei em Criar -> Enviar videos e o campo "
                                "nao veio"}
        frase, laudo = self._publicar()
        self.assertEqual(12.0, laudo["abertura_s"])
        self.assertFalse(frase.startswith("infraestrutura"), frase)
        self.assertIn("--sondar", frase)

    def test_pagina_em_branco_mede_e_e_rede(self):
        self.abrir_s, self.montar_s, self.montou = 2.0, 45.0, False
        frase, laudo = self._publicar()
        self.assertEqual(47.0, laudo["abertura_s"])
        self.assertTrue(frase.startswith(
            "infraestrutura: a pagina de upload abriu e ficou em branco "
            "(sem texto depois de 47 s)"), frase)
        self.assertIn("Tela: telas/youtube_em_branco.png", frase)
        self.assertNotIn("envio_nao_abriu", laudo)


class RodadaRepoeTests(unittest.TestCase):
    """A frase chega a `postar._derrubados_pela_rede` cortada em 200: a marca
    tem de sobreviver ao corte, nos dois canais."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("postar_parede_criar",
                                                      POSTAR)
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    def _ficha(self, frase):
        falha_yt = f"YouTubeWebFalhou: {frase}"[:200]
        return {"canal": "historias", "feito": True, "youtube_falhou": True,
                "motivo": f"YouTube falhou: {falha_yt}"[:200],
                "tiktok": "publicado no TikTok"}

    def test_envio_que_nao_abriu_com_pagina_lenta_repoe_o_youtube(self):
        frase = youtube_web.falha_do_envio(
            {"motivo": "o clique no Criar nao passou (TimeoutError)",
             "parede": "tp-yt-iron-overlay-backdrop"}, 126.0)
        self.assertEqual(["youtube"],
                         self.m._derrubados_pela_rede(self._ficha(frase)))

    def test_pagina_em_branco_repoe_o_youtube(self):
        frase = youtube_web.falha_da_montagem(47.0)
        self.assertEqual(["youtube"],
                         self.m._derrubados_pela_rede(self._ficha(frase)))

    def test_dialogo_sem_campo_em_pagina_rapida_nao_repoe(self):
        frase = youtube_web.falha_do_envio({"dialogo_sem_campo": True}, 12.0)
        self.assertEqual([], self.m._derrubados_pela_rede(self._ficha(frase)))

    def test_tela_mudada_nao_repoe(self):
        frase = youtube_web.falha_do_envio(
            {"motivo": "o botao Criar nao esta na tela"}, 12.0)
        self.assertEqual([], self.m._derrubados_pela_rede(self._ficha(frase)))


if __name__ == "__main__":
    unittest.main()
