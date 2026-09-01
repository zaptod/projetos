# -*- coding: utf-8 -*-
"""Contratos do "publicar sempre por navegador" (decisão de 01/09/2026).

Por que a decisão existe: a API do YouTube recusou por cota
(`uploadLimitExceeded`) num canal de um dia de vida, e continuou recusando
depois de o dia virar no Pacífico — enquanto subir pelo Studio funcionava
normalmente. São baldes de cota separados.

O que este arquivo trava:

1. O PADRÃO é navegador. Um config sem `modo` não pode voltar a publicar
   pela API por omissão.
2. A API continua existindo para LER (métricas, identidade do canal). "Não
   publicar por API" não é "arrancar a API".
3. AGENDAMENTO NÃO SE PERDE EM SILÊNCIO. A série agenda as partes de 24 em
   24 h; se o navegador não conseguir agendar, ele precisa FALHAR — publicar
   tudo agora soltaria oito partes no mesmo minuto, o que mata a série.

Rode de dentro de random_builds/:
    python -m unittest tests.test_modo_navegador_regressions -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from builds.publicar import youtube, youtube_web                   # noqa: E402


class ModoTests(unittest.TestCase):
    def test_o_padrao_e_navegador(self):
        """Sem `modo` no config, publica por navegador — nunca por API."""
        self.assertEqual("navegador", youtube.modo({}))
        self.assertEqual("navegador", youtube.modo({"youtube": {}}))

    def test_o_config_manda(self):
        self.assertEqual("api", youtube.modo({"youtube": {"modo": "api"}}))
        self.assertEqual("navegador",
                         youtube.modo({"youtube": {"modo": "NAVEGADOR"}}))

    def test_valor_vazio_cai_no_padrao(self):
        for valor in ("", "   ", None):
            self.assertEqual("navegador",
                             youtube.modo({"youtube": {"modo": valor}}))

    def test_o_config_de_verdade_esta_em_navegador(self):
        """O arquivo do projeto, não um dicionário de teste."""
        from builds.publicar import catalogo
        self.assertEqual("navegador", youtube.modo(catalogo.carregar_config()))


class ApiContinuaParaLerTests(unittest.TestCase):
    """"Não publicar por API" não é "arrancar a API"."""

    def test_metricas_e_identidade_seguem_existindo(self):
        for nome in ("identificar_canal", "canais_da_conta",
                     "cota_disponivel"):
            self.assertTrue(callable(getattr(youtube, nome, None)), nome)

    def test_o_publicar_por_api_continua_disponivel(self):
        """Para quem quiser voltar atrás com uma linha de config."""
        self.assertTrue(callable(youtube.publicar))


class PortaUnicaTests(unittest.TestCase):
    """Um so lugar decide por onde o video sobe, e ele traduz os dois lados.

    A API reporta bytes e o navegador reporta texto. Quando cada chamador
    ramificava sozinho, essa diferenca vivia duplicada em dois arquivos —
    e a funcao que dizia ser "a porta que todos usam" nao era usada por
    ninguem e teria quebrado se fosse.
    """

    def _porta(self, caminho, **kw):
        """Chama a porta com o modo forcado; devolve (destino, linhas, kw)."""
        linhas, visto = [], {}

        def falso(video, **recebidos):
            visto.update(recebidos)
            visto["_video"] = video
            if recebidos.get("progresso"):
                # Cada lado fala do seu jeito: bytes de um lado, texto do outro.
                if caminho == "api":
                    recebidos["progresso"](5_000_000, 10_000_000)
                else:
                    recebidos["progresso"]("etapa qualquer")
            return "https://youtu.be/ok"

        original_publicar = youtube.publicar
        original_web = youtube_web.publicar
        youtube.publicar = falso
        youtube_web.publicar = falso
        self.addCleanup(lambda: setattr(youtube, "publicar", original_publicar))
        self.addCleanup(lambda: setattr(youtube_web, "publicar", original_web))

        url = youtube.publicar_como_configurado(
            "video.mp4", log=linhas.append,
            config={"youtube": {"modo": caminho}}, **kw)
        self.assertEqual("https://youtu.be/ok", url)
        return linhas, visto

    def test_sem_modo_vai_pelo_navegador(self):
        linhas, visto = self._porta("navegador")
        self.assertIn("[youtube] publicando por NAVEGADOR", linhas)
        self.assertTrue(visto.get("postar"), "o navegador tem que POSTAR")

    def test_o_modo_api_ainda_funciona(self):
        linhas, _ = self._porta("api")
        self.assertIn("[youtube] publicando por API", linhas)

    def test_ela_traduz_os_dois_progressos(self):
        """Bytes de um lado, texto do outro, uma linha so para quem chama."""
        linhas_api, _ = self._porta("api")
        self.assertTrue(any("MB" in linha for linha in linhas_api), linhas_api)

        linhas_web, _ = self._porta("navegador")
        self.assertTrue(any("etapa qualquer" in linha for linha in linhas_web),
                        linhas_web)

    def test_postar_nao_vaza_para_a_api(self):
        """`postar` so existe no navegador; mandar para a API seria TypeError."""
        _, visto = self._porta("api")
        self.assertNotIn("postar", visto)

    def test_o_agendamento_atravessa(self):
        for caminho in ("api", "navegador"):
            _, visto = self._porta(caminho, agendar_para="2026-09-02T15:00:00Z")
            self.assertEqual("2026-09-02T15:00:00Z", visto.get("agendar_para"),
                             caminho)

    def test_ninguem_mais_ramifica_por_fora(self):
        """A escolha do caminho mora num lugar so."""
        for arquivo in (Path(RAIZ) / "main.py",
                        Path(RAIZ).parent / "historias/contos/publicar/catalogo.py"):
            fonte = arquivo.read_text(encoding="utf-8")
            self.assertNotIn('caminho == "api"', fonte, arquivo.name)
            self.assertIn("publicar_como_configurado", fonte, arquivo.name)


class AgendamentoTests(unittest.TestCase):
    """O silêncio aqui seria o pior defeito possível."""

    def test_o_navegador_sabe_agendar(self):
        self.assertTrue(callable(getattr(youtube_web, "_agendar", None)))
        junto = " ".join(youtube_web.BOTAO_AGENDAR)
        self.assertIn("Agendar", junto)
        self.assertIn("Schedule", junto)

    def test_publicar_aceita_agendar_para(self):
        import inspect
        parametros = inspect.signature(youtube_web.publicar).parameters
        self.assertIn("agendar_para", parametros)

    def test_data_invalida_nao_agenda(self):
        registro = []

        class PaginaFalsa:
            @staticmethod
            def locator(_s):
                raise RuntimeError("nao devia chegar aqui")

        self.assertFalse(youtube_web._agendar(PaginaFalsa(), "nao e data",
                                              registro.append))
        self.assertTrue(any("invalida" in linha for linha in registro))

    def test_o_codigo_falha_em_vez_de_publicar_agora(self):
        """Se não conseguir agendar, tem que PARAR, não publicar na hora."""
        fonte = Path(youtube_web.__file__).read_text(encoding="utf-8")
        trecho = fonte[fonte.index("if agendar_para:"):][:800]
        self.assertIn("raise YouTubeWebFalhou", trecho)
        self.assertIn("mesmo minuto", trecho)


class ConfirmacaoTests(unittest.TestCase):
    """A lição do TikTok vale aqui: nada de prometer o que não se viu."""

    def test_url_conta_como_sucesso(self):
        self.assertTrue(youtube_web.confirmado("https://youtu.be/abc123"))
        self.assertTrue(youtube_web.confirmado(youtube_web.SUCESSO))

    def test_duvida_nao_conta(self):
        for estado in ("cliquei em publicar, mas o Studio nao mostrou a "
                       "confirmacao.",
                       "video carregado e preenchido; a publicacao final "
                       "ficou com voce",
                       "", None):
            self.assertFalse(youtube_web.confirmado(estado), repr(estado))


class CanalAlvoTests(unittest.TestCase):
    """Com vários canais numa conta Google, a URL é o que separa um do outro."""

    def setUp(self):
        # Este teste JA leu o registro de verdade da maquina e passou a
        # depender dele: quando o login gravou o id do canal, a "URL
        # generica" deixou de ser generica. Registro proprio, entao.
        import tempfile
        from builds import contas
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        anterior = contas.ARQUIVO
        contas.ARQUIVO = str(Path(pasta.name) / "contas.json")
        self.addCleanup(lambda: setattr(contas, "ARQUIVO", anterior))

    def test_sem_id_gravado_usa_a_url_generica(self):
        self.assertEqual(youtube_web.URL_UPLOAD,
                         youtube_web.url_de_upload("canal_que_nao_existe"))

    def test_com_id_mira_o_canal(self):
        from builds import contas
        original = contas.identidade

        def falsa(servico, conta):
            return {"id": "UCteste123", "rotulo": "canal de teste"}

        contas.identidade = falsa
        self.addCleanup(lambda: setattr(contas, "identidade", original))
        url = youtube_web.url_de_upload("builds")
        self.assertIn("/channel/UCteste123/", url)
        self.assertIn("/videos/upload", url)
        # A URL passou a pedir o dialogo de envio junto: sem isso a pagina
        # so mostra a LISTA de videos e nao tem campo de arquivo nenhum.
        self.assertIn(youtube_web.PARAMETRO_DIALOGO, url)


class PainelSegueOModoTests(unittest.TestCase):
    """O painel tem que cobrar o login CERTO e gravar onde leu.

    Estes testes liam o FONTE do painel e procuravam literais
    (`fonte.index("def _historias_publicar")`). Isso nao testava nada:
    passava se alguem escrevesse a mesma coisa de outro jeito, e falhava se
    alguem movesse a funcao. Com o painel virando pacote em 01/09/2026, as
    paginas viraram modulos importaveis -- e o teste honesto ficou
    disponivel pela primeira vez.
    """

    def _pagina(self, modulo, classe="Pagina"):
        """A pagina sem abrir janela: ela so precisa da casca no construtor."""
        import importlib
        mod = importlib.import_module(f"painel.paginas.{modulo}")

        class CascaFalsa:
            oficina = None
            tema = None
            registros = []

            def _registrar(self, texto, tipo="saida"):
                self.registros.append((texto, tipo))

            def mostrar(self, _chave):
                pass

        casca = CascaFalsa()
        pagina = getattr(mod, classe).__new__(getattr(mod, classe))
        pagina.casca = casca
        return pagina, casca

    def _com_modo(self, modo):
        """Forca o modo de publicacao pelo config, sem tocar em disco."""
        from builds.publicar import youtube
        original = youtube.modo
        youtube.modo = lambda _config=None: modo
        self.addCleanup(lambda: setattr(youtube, "modo", original))

    # ---------------------------------------------------------- publicar
    def test_a_pagina_publicar_le_o_servico_do_MODO(self):
        pagina, _ = self._pagina("publicar")
        self._com_modo("navegador")
        self.assertEqual("youtube_web", pagina.servico_youtube())
        self._com_modo("api")
        self.assertEqual("youtube", pagina.servico_youtube())

    def test_modo_desconhecido_cai_no_navegador(self):
        """Melhor cobrar o login do navegador do que o token que nao existe."""
        pagina, _ = self._pagina("publicar")

        from builds.publicar import youtube
        original = youtube.modo

        def explode(_config=None):
            raise RuntimeError("config ilegivel")

        youtube.modo = explode
        self.addCleanup(lambda: setattr(youtube, "modo", original))
        self.assertEqual("youtube_web", pagina.servico_youtube())

    # ---------------------------------------------------------- historias
    def test_publicar_serie_cobra_o_login_DO_MODO(self):
        """Cobrar o OAuth no modo navegador bloqueia quem nao precisa dele."""
        pagina, _ = self._pagina("historias")
        self._com_modo("navegador")
        self.assertEqual("youtube_web", pagina._servico_youtube())
        self._com_modo("api")
        self.assertEqual("youtube", pagina._servico_youtube())

    def test_a_serie_para_sem_conta_PROPRIA(self):
        """Sem conta propria o registro cai na de builds -- irreversivel."""
        from builds import contas
        pagina, casca = self._pagina("historias")
        self._com_modo("navegador")

        pagina.selecionada = lambda: "historia_00001"
        pagina.cli = lambda *a, **k: self.fail("nao podia ter publicado")
        original_login, original_destino = contas.tem_login, contas.destino
        contas.tem_login = lambda *a, **k: True
        contas.destino = lambda *a, **k: {"conta": "principal",
                                          "explicita": False,
                                          "tem_login": True, "identidade": ""}
        self.addCleanup(lambda: (setattr(contas, "tem_login", original_login),
                                 setattr(contas, "destino", original_destino)))

        pagina.publicar_serie()
        self.assertTrue(any("PAREI" in texto for texto, _t in casca.registros),
                        casca.registros)

    # ------------------------------------------------------------ acoes
    def test_o_login_do_studio_existe_como_ACAO(self):
        """A #7 guardava a existencia de um recurso, nao uma logica.

        Reancorada: em vez de procurar o literal no fonte do painel, checa
        que a pagina tem o metodo e que ele aponta para o modulo certo.
        """
        import inspect
        pagina, _ = self._pagina("publicar")
        self.assertTrue(callable(pagina.login_youtube_web))
        fonte = inspect.getsource(type(pagina).login_youtube_web)
        self.assertIn("builds.publicar.youtube_web", fonte)
        self.assertIn("--login", fonte)


if __name__ == "__main__":
    unittest.main()
