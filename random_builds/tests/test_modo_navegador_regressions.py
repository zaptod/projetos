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

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

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
    """O painel tem que cobrar o login CERTO.

    Ele cobrava o OAuth antes de publicar a serie. Com a publicacao indo
    pelo navegador, isso bloquearia quem nao precisa de OAuth e liberaria
    quem nao tem login do Studio — o erro so apareceria la na frente, com
    o Chrome ja aberto. O smoke das 12 paginas nao pega isso: ele constroi
    a tela, nao aperta o botao.
    """

    @classmethod
    def setUpClass(cls):
        cls.fonte = (Path(RAIZ).parent / "painel_ui.py").read_text(
            encoding="utf-8")

    def _trecho_da_serie(self):
        i = self.fonte.index("def _historias_publicar")
        return self.fonte[i:i + 2200]

    def test_a_trava_pergunta_o_modo(self):
        trecho = self._trecho_da_serie()
        self.assertIn("self._servico_youtube()", trecho)

    def test_a_trava_nao_fixa_o_servico_na_mao(self):
        trecho = self._trecho_da_serie()
        for errado in ('tem_login("youtube", "historias")',
                       'ativa("youtube", "historias")',
                       'destino("youtube", "historias")'):
            self.assertNotIn(errado, trecho, errado)

    def test_a_linha_de_contas_le_o_servico_do_modo(self):
        """Ela mostrava a conta da API mesmo publicando pelo navegador."""
        i = self.fonte.index("def _pub_contas")
        trecho = self.fonte[i:i + 2200]
        self.assertIn("self._servico_youtube()", trecho)
        self.assertNotIn('(("youtube", self.combo_pub_conta_yt)', trecho)

    def test_a_linha_de_contas_mostra_o_CANAL(self):
        """O nome da conta nao diz para onde o video vai; o canal diz."""
        i = self.fonte.index("def _pub_contas")
        trecho = self.fonte[i:i + 2200]
        self.assertIn('destino.get("identidade")', trecho)
        self.assertIn("destinos_repetidos", trecho)

    def test_o_combo_grava_onde_leu(self):
        """Ler de youtube_web e gravar em youtube perderia a escolha."""
        i = self.fonte.index("def _pub_trocar_conta")
        trecho = self.fonte[i:i + 900]
        self.assertIn("self._servico_youtube()", trecho)

    def test_o_callback_do_processo_roda_no_thread_da_ui(self):
        """`after()` ou widget a partir da thread derruba o Tkinter."""
        i = self.fonte.index("def _drenar_fila")
        trecho = self.fonte[i:i + 1400]
        self.assertIn("depois()", trecho)

    def test_o_painel_oferece_o_login_do_studio(self):
        """Sem botao, a unica coisa que falta fica escondida num comando."""
        self.assertIn("_pub_login_youtube_web", self.fonte)
        self.assertIn("Login YouTube Studio", self.fonte)
        self.assertIn("builds.publicar.youtube_web", self.fonte)


if __name__ == "__main__":
    unittest.main()
