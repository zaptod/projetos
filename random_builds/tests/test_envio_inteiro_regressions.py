# -*- coding: utf-8 -*-
"""O envio cortado do YouTube pelo Studio (21/10/2026).

O caso medido nos laudos do ledger (`prova[].texto_da_barra`, 14 a 21/10):

  * historias: 25 de 25 envios clicaram com o rodape em "envio em N%" (de
    0% a 98%) e `esperou_s` 0 — "envio em" nao estava em FASES, e o
    classificador caia em "hd";
  * builds: 7 de 60 assim (a estreia `generation_00121` das 23:43 de 19/10
    com "envio em 3% ..."), e 12 de 60 com o CABECALHO do dialogo lido como
    barra ("drusila vyrhordan x sigrid brasbalmirn salvo como privado
    detalhes...") — `hd` as cegas, sempre logo depois de "sd, 3 minutos
    restantes";
  * depois do clique, `_confirmar` aceitava "Link do video" (que existe na
    tela desde o primeiro segundo do envio) e o `return` saia do `with
    contexto_persistente`, fechando o navegador e CORTANDO o envio. Saldo:
    2 estreias publicas e vazias (8Rp3WUDsBgA, CHogZyWtA8I), 3 builds
    sumidos, 27 partes de historia so no ledger.

Decisao `publicacao/esperar-envio-terminar`: segurar o navegador ate o
arquivo estar inteiro, no maximo 10 min; estourou, sem confirmacao, "a
conferir" e sem [POSTADO].

Rode de dentro de random_builds/:
    python -m unittest tests.test_envio_inteiro_regressions -v
"""
from __future__ import annotations

import contextlib
import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from builds.publicar import conferencia, metricas, youtube_web

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"
Y = youtube_web


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


# ------------------------------------------------------------ o classificador
# Os rodapes como os laudos os gravaram (sem acento, minusculas).
MEDIDOS_SUBINDO = (
    "envio em 3% ...",                                   # generation_00121
    "envio em 20% ...",                                  # generation_00120
    "envio em 94% ... tempo restante: 2 segundos",       # generation_00177
    "envio em 47% ... tempo restante: 20 segundos",      # historia_00048 p04
    "envio em 0% ...",                                   # historia_00082 p04
    "Envio em 33% ... Tempo restante: 3 minutos",        # com acento e caixa
    "Uploading 12% ... 2 minutes left",
)
CABECALHO_REAL = (
    "drusila vyrhordan x sigrid brasbalmirn\nsalvo como privado\ndetalhes\n"
    "elementos do video\nverificacoes\nvisibilidade\n"
    "link do video\nhttps://youtu.be/AbCdEfGhIjK\nnome do arquivo\n"
    "final_celular.mp4\n")


class ClassificadorTests(unittest.TestCase):

    def test_envio_em_N_por_cento_e_subindo(self):
        for rodape in MEDIDOS_SUBINDO:
            with self.subTest(rodape=rodape):
                fim = Y._classificar_rodape(CABECALHO_REAL, Y._sem_acento(rodape))
                self.assertEqual("subindo", fim["qualidade"])
                self.assertEqual("subindo", fim["envio"])
                self.assertTrue(Y._nao_publicar_ainda(fim))

    def test_envio_em_3_por_cento_com_a_contagem_no_dialogo(self):
        """Sem rodape pelo seletor, a janela da contagem tambem segura."""
        texto = CABECALHO_REAL + "envio em 3% ... 4 minutos restantes"
        self.assertEqual("subindo", Y._classificar_rodape(texto)["qualidade"])

    def test_cem_por_cento_nao_e_pronto(self):
        fim = Y._classificar_rodape(CABECALHO_REAL, "envio em 100% ...")
        self.assertEqual("processando", fim["qualidade"])
        self.assertEqual("concluido", fim["envio"])

    def test_cabecalho_lido_como_barra_nao_e_hd(self):
        """Os 12 de 60 dos builds: sem rodape, sem contagem, so o cabecalho
        (com o "link do video" que `SINAIS_PUBLICADO` reconhecia)."""
        fim = Y._classificar_rodape(Y._sem_acento(CABECALHO_REAL))
        self.assertEqual("desconhecida", fim["qualidade"])
        self.assertFalse(fim["reconhecido"])
        self.assertEqual("", fim["envio"])

    def test_porcentagem_sem_frase_nao_vale_como_pronta(self):
        fim = Y._classificar_rodape(CABECALHO_REAL, "verificacao 43%")
        self.assertEqual("desconhecida", fim["qualidade"])

    def test_texto_desconhecido_no_rodape_nao_vale_como_pronto(self):
        fim = Y._classificar_rodape(CABECALHO_REAL, "bem-vindo ao novo studio")
        self.assertEqual("desconhecida", fim["qualidade"])
        self.assertEqual("", fim["envio"])

    def test_verificacoes_concluidas_e_hd_e_prova_o_arquivo(self):
        """47 de 60 envios dos builds: o caso normal, que nao pode mudar."""
        fim = Y._classificar_rodape(
            CABECALHO_REAL,
            "verificacoes concluidas. nenhum problema foi encontrado.")
        self.assertEqual("hd", fim["qualidade"])
        self.assertTrue(fim["reconhecido"])
        self.assertEqual("concluido", fim["envio"])

    def test_fases_do_processamento_provam_o_arquivo_inteiro(self):
        for rodape in ("processando ate hd ... 3 minutos restantes",
                       "envio concluido ... o processamento vai comecar em breve",
                       "processando ate sd ... 2 minutos restantes"):
            with self.subTest(rodape=rodape):
                self.assertEqual(
                    "concluido",
                    Y._classificar_rodape(CABECALHO_REAL, rodape)["envio"])

    def test_caso_zero_nada_prova_nada(self):
        self.assertEqual("", Y._progresso_do_envio("")["envio"])
        self.assertEqual("", Y._envio_pelos_textos()["envio"])
        self.assertEqual("", Y._envio_pelos_textos(
            "", "", "conteudo do canal\nvideo\nvisibilidade")["envio"])


class EnvioDepoisDoCliqueTests(unittest.TestCase):

    def test_qualquer_escopo_com_menos_de_100_segura(self):
        for args in (("envio em 47% ...", "", ""),
                     ("", "enviando 47%", ""),
                     ("", "", "video publicado\nenvio em 47% ...")):
            with self.subTest(args=args):
                self.assertEqual("subindo", Y._envio_pelos_textos(*args)["envio"])

    def test_concluido_vem_do_rodape_do_painel_ou_da_frase_do_envio(self):
        self.assertEqual("concluido", Y._envio_pelos_textos(
            "processando ate hd")["envio"])
        self.assertEqual("concluido", Y._envio_pelos_textos(
            "", "1 envio concluido")["envio"])
        self.assertEqual("concluido", Y._envio_pelos_textos(
            "", "", "video publicado\nenvio concluido")["envio"])

    def test_a_pagina_inteira_nao_libera_pela_fase_do_processamento(self):
        """A lista de videos atras do dialogo nao fala do envio DESTE."""
        self.assertEqual("", Y._envio_pelos_textos(
            "", "", "processando ate hd\nverificacoes concluidas")["envio"])

    def test_a_frase_e_de_clique_e_nao_de_rede(self):
        laudo = {"envio_nao_terminou": {"espera_s": 600.0,
                                        "ultimo": "envio em 47% ...",
                                        "pagina_fechou": False}}
        frase = Y.falha_do_envio_cortado(laudo)
        self.assertTrue(frase.startswith("cliquei em publicar"), frase)
        from builds.publicar import desfecho
        self.assertEqual("sem_confirmacao", desfecho.classificar(frase))
        spec = importlib.util.spec_from_file_location("postar_envio", POSTAR)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertFalse(m._e_de_rede(f"EnvioNaoTerminou: {frase}"))
        ficha = {"canal": "builds", "feito": False, "youtube_falhou": True,
                 "youtube_clicou": True,
                 "motivo": f"YouTube falhou: {frase}"[:200],
                 "tiktok": "fora da grade do TikTok neste horario"}
        self.assertEqual([], m._derrubados_pela_rede(ficha))


# ------------------------------------------------- publicar() de verdade
class Relogio:
    """`time` do youtube_web: dormir faz o relogio andar."""

    def __init__(self):
        self.agora = 1000.0

    def monotonic(self):
        return self.agora

    def time(self):
        return self.agora

    def sleep(self, s):
        self.agora += s


class Alvo:
    def __init__(self, studio, seletor):
        self.studio, self.seletor = studio, seletor

    @property
    def first(self):
        return self

    def nth(self, _i):
        return self

    def count(self):
        return 1 if self.studio.existe(self.seletor) else 0

    def is_visible(self):
        return self.studio.existe(self.seletor)

    def wait_for(self, state="visible", timeout=None):
        if not self.studio.existe(self.seletor):
            raise TimeoutError(self.seletor)

    def click(self, timeout=None):
        if self.seletor in Y.SINAIS_PRONTO:
            self.studio.clicar()

    def get_attribute(self, _nome):
        return "https://youtu.be/AbCdEfGhIjK"

    def inner_text(self, timeout=None):
        return ""

    def set_input_files(self, _caminho):
        self.studio.entregue_em = self.studio.relogio.agora


class Studio:
    """O Studio como os laudos de 14 a 21/10 mediram.

    `rodape(t, clique)`: o texto do rodape `t` s depois do arquivo entregue
    (`clique`: `t` do clique, ou None). O botao Publicar HABILITA com o
    arquivo subindo — e o que o Studio faz hoje. `envio_s`: quando o arquivo
    chega a 100% (None = nunca se sabe).
    """
    url = "https://studio.youtube.com/video/AbCdEfGhIjK/edit?d=ud"

    def __init__(self, relogio, rodape, envio_s):
        self.relogio, self._rodape, self.envio_s = relogio, rodape, envio_s
        self.entregue_em = None
        self.clique = None
        self.porcento_no_clique = None

    def t(self):
        return self.relogio.agora - self.entregue_em

    def porcento(self):
        if self.envio_s is None:
            return None
        return min(100, int(100 * self.t() / self.envio_s)) if self.envio_s else 100

    def rodape(self):
        return self._rodape(self.t(), self.clique)

    def clicar(self):
        self.clique = self.t()
        self.porcento_no_clique = self.porcento()

    def existe(self, seletor):
        entregue = self.entregue_em is not None
        if seletor == Y.ENTRADA_ARQUIVO:
            return True
        if seletor in Y.CAMPO_TITULO or seletor in Y.CAMPO_DESCRICAO:
            return entregue
        if (seletor in Y.NAO_E_PARA_CRIANCAS or seletor in Y.BOTAO_PROXIMO
                or any(seletor in v for v in Y.VISIBILIDADE.values())):
            return entregue
        if seletor in Y.SINAIS_PRONTO:
            return entregue
        if seletor in Y.LINK_DO_VIDEO:
            return True
        return False

    def evaluate(self, script, *_a):
        script = str(script)
        rodape = self.rodape()
        if "monitor" in script:
            return {"rodape": rodape, "monitor": "",
                    "corpo": CABECALHO_REAL + rodape}
        if "ytcp-uploads-dialog" in script:
            return {"dialogo": CABECALHO_REAL + rodape, "rodape": rodape}
        if "document.body" in script:
            return CABECALHO_REAL + rodape
        return ""

    def locator(self, seletor):
        return Alvo(self, seletor)


def _envio_real(envio_s, *, processa_s=10.0, hd_s=40.0):
    """O rodape de um envio que leva `envio_s` s e depois processa."""
    def rodape(t, _clique):
        if t < envio_s:
            return (f"Envio em {int(100 * t / envio_s)}% ... Tempo restante: "
                    f"{int(envio_s - t)} segundos")
        if t < envio_s + processa_s:
            return "Envio concluído ... O processamento vai começar em breve"
        if t < envio_s + hd_s:
            return "Processando até HD ... 1 minuto restante"
        return "Verificações concluídas. Nenhum problema foi encontrado."
    return rodape


# Do arquivo entregue ao clique, sem espera nenhuma: as 3 etapas do
# assistente dormem 2,5 s cada (`publicar`, laco do "Proximo").
SEM_ESPERA_S = 3 * 2.5


class PublicarTests(unittest.TestCase):
    """`publicar()` de verdade, com o Studio de mentira e o relogio dublado."""

    def setUp(self):
        from builds import contas
        from builds.publicar import desfecho
        self.relogio = Relogio()
        _trocar(self, Y, "time", self.relogio)
        _trocar(self, Y.atividade, "fabrica",
                lambda *a, **k: contextlib.nullcontext())
        self.diario = []
        _trocar(self, Y.atividade, "registrar",
                lambda *a, **k: self.diario.append(a))
        self.fechou = []

        @contextlib.contextmanager
        def contexto(**_k):
            try:
                yield object()
            finally:
                # O NAVEGADOR FECHA AQUI, com ou sem excecao: e o instante
                # que corta o envio.
                self.fechou.append((self.studio.t(), self.studio.porcento()))
        _trocar(self, Y, "contexto_persistente", contexto)
        _trocar(self, Y, "perfil_da_conta", lambda canal: "perfil")
        _trocar(self, Y, "_conta_ativa", lambda canal: "builds")
        _trocar(self, Y, "url_de_upload", lambda canal: Studio.url)
        _trocar(self, Y.escrita, "fotografar", lambda *a, **k: "")
        _trocar(self, contas, "ativa", lambda *a, **k: "builds")
        _trocar(self, contas, "identidade", lambda *a, **k: {})
        _trocar(self, Y, "_abrir", lambda _ctx, _url: self.studio)
        _trocar(self, Y, "_esperar_montar", lambda *a, **k: True)
        _trocar(self, Y, "_abrir_dialogo_de_upload", lambda *a, **k: True)
        _trocar(self, Y, "_escrever", lambda *a, **k: {"modo": "colado"})
        # O teto sai da grade e do relogio REAL: fixo, para o caso nao
        # depender da hora em que a suite roda.
        _trocar(self, Y, "_teto_da_espera", lambda: 300.0)
        self.marcas = []
        _trocar(self, desfecho, "resolver",
                lambda canal, video, estado, laudo=None, falha=None,
                plataforma="tiktok": self.marcas.append(
                    (video.id, estado, plataforma)) or desfecho.classificar(
                        estado, falha, laudo))
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        arquivo = Path(pasta.name) / "final_celular.mp4"
        arquivo.write_bytes(b"x")
        self.video = type("V", (), {
            "id": "generation_00121:estreia:celular", "caminho": str(arquivo),
            "titulo": "Estreia", "descricao_completa": "d"})()

    def _publicar(self, rodape, envio_s):
        self.studio = Studio(self.relogio, rodape, envio_s)
        self.laudo = {}
        return Y.publicar(self.video, config={}, canal="builds", postar=True,
                          progresso=lambda _t: None, prova=self.laudo)

    def test_envio_em_3_por_cento_no_clique_espera_o_arquivo(self):
        """generation_00121, 19/10 23:43: o clique saiu com "envio em 3%"."""
        estado = self._publicar(_envio_real(250.0), 250.0)
        self.assertTrue(Y.confirmado(estado), estado)
        self.assertGreaterEqual(self.studio.clique, 250.0)
        self.assertEqual(100, self.studio.porcento_no_clique)
        self.assertEqual("hd", self.laudo["qualidade_no_clique"])
        self.assertTrue(self.laudo["envio_concluido"])
        (fechou_t, fechou_pct), = self.fechou
        self.assertEqual(100, fechou_pct, "o navegador fechou com o envio "
                         "pela metade")
        self.assertEqual(self.studio.clique, fechou_t)

    def test_caso_normal_nao_fica_mais_lento(self):
        """Duelo de 20/10 21:45: arquivo inteiro antes da visibilidade e
        "verificacoes concluidas" no rodape (47 de 60 envios dos builds).
        Clique e fechamento no mesmo instante de antes do conserto."""
        estado = self._publicar(_envio_real(5.0, processa_s=1.0, hd_s=2.0), 5.0)
        self.assertTrue(Y.confirmado(estado), estado)
        self.assertEqual(SEM_ESPERA_S, self.studio.clique)
        self.assertEqual(0.0, self.laudo["esperou_s"])
        self.assertEqual(0.0, self.laudo["envio_depois_do_clique_s"])
        (fechou_t, fechou_pct), = self.fechou
        self.assertEqual(SEM_ESPERA_S, fechou_t)
        self.assertEqual(100, fechou_pct)
        self.assertEqual([], self.marcas[1:])
        self.assertEqual("publicado", self.laudo["desfecho"])

    def test_cabecalho_lido_como_barra_espera_o_rodape_voltar(self):
        """duelo_00111, 20/10 01:21: "sd, 3 minutos restantes" e, 5 s depois,
        o rodape vazio — o cabecalho virava "hd" e o clique saia."""
        def rodape(t, _clique):
            if t < 5.0:
                return "Envio em 50% ..."
            if t < 20.0:
                return "Processando até HD ... 3 minutos restantes"
            if t < 40.0:
                return ""
            return "Verificações concluídas. Nenhum problema foi encontrado."
        estado = self._publicar(rodape, 5.0)
        self.assertTrue(Y.confirmado(estado), estado)
        self.assertGreaterEqual(self.studio.clique, 40.0,
                                "clicou lendo o cabecalho")
        self.assertEqual("hd", self.laudo["qualidade_no_clique"])
        # O arquivo ja estava inteiro (o "processando ate hd" provou): o
        # depois do clique nao espera nada.
        self.assertEqual(0.0, self.laudo["envio_depois_do_clique_s"])

    def test_estouro_de_10_min_fica_sem_confirmacao_e_a_conferir(self):
        """Studio que ninguem entende do comeco ao fim: a regra de 16/09
        publica no estouro do teto, e o arquivo nunca prova que chegou."""
        estado = None
        with self.assertRaises(Y.EnvioNaoTerminou) as caso:
            estado = self._publicar(lambda t, c: "bem-vindo ao novo studio",
                                    None)
        self.assertIsNone(estado)
        self.assertIsInstance(caso.exception, Y.YouTubeWebFalhou)
        frase = str(caso.exception)
        self.assertTrue(frase.startswith("cliquei em publicar"), frase)
        self.assertEqual("sem_confirmacao", self.laudo["estado"])
        self.assertTrue(self.laudo["clicou"])
        espera = self.laudo["envio_nao_terminou"]["espera_s"]
        self.assertGreaterEqual(espera, Y.ESPERA_ENVIO_DEPOIS_DO_CLIQUE_S)
        self.assertLess(espera, Y.ESPERA_ENVIO_DEPOIS_DO_CLIQUE_S + 10)
        # Segurou o navegador os 10 min, e nao fechou antes.
        (fechou_t, _), = self.fechou
        self.assertGreaterEqual(fechou_t - self.studio.clique,
                                Y.ESPERA_ENVIO_DEPOIS_DO_CLIQUE_S)
        # "a conferir" no YouTube com a frase do envio, e nenhum "publicado".
        (marca,) = self.marcas
        self.assertEqual((self.video.id, "youtube"), (marca[0], marca[2]))
        self.assertTrue(marca[1].startswith("cliquei em publicar"))
        self.assertNotIn("desfecho", self.laudo)

    def test_envio_que_termina_depois_do_clique_segura_e_publica(self):
        """Clique sem prova do arquivo (Studio ilegivel antes) e o envio
        aparecendo depois: o navegador so fecha no "envio concluido"."""
        def rodape(t, clique):
            if clique is None:
                return "bem-vindo ao novo studio"
            if t < clique + 120.0:
                return "Envio em 60% ..."
            return "Envio concluído ... O processamento vai começar em breve"
        estado = self._publicar(rodape, None)
        self.assertTrue(Y.confirmado(estado), estado)
        espera = self.laudo["envio_depois_do_clique_s"]
        self.assertGreaterEqual(espera, 120.0)
        self.assertLess(espera, 130.0)
        (fechou_t, _), = self.fechou
        self.assertGreaterEqual(fechou_t, self.studio.clique + 120.0)

    def test_arquivo_que_nao_sobe_em_900_s_nao_e_clicado(self):
        """Envio parado em 3%: nenhum clique, o video volta a fila."""
        with self.assertRaises(Y.YouTubeWebFalhou) as caso:
            self._publicar(lambda t, c: "Envio em 3% ...", 10 ** 6)
        self.assertNotIsInstance(caso.exception, Y.EnvioNaoTerminou)
        self.assertIsNone(self.studio.clique)
        self.assertNotIn("clicou", self.laudo)
        self.assertIn("ainda subia", str(caso.exception))


class SemPostadoTests(unittest.TestCase):
    """A porta dos builds (`youtube.publicar_como_configurado`): o envio que
    nao terminou sobe como excecao e nao vira linha no ledger."""

    def test_nao_registra(self):
        from builds.publicar import audio, youtube
        registros = []
        _trocar(self, audio, "barrar_luta_muda", lambda *a, **k: None)
        _trocar(self, metricas, "registrar_publicado",
                lambda *a, **k: registros.append(a))

        def publicar(_video, **kw):
            kw["prova"].update(clicou=True, estado="sem_confirmacao")
            raise Y.EnvioNaoTerminou(Y.falha_do_envio_cortado({}))
        _trocar(self, Y, "publicar", publicar)
        video = type("V", (), {"id": "duelo_00140:duelo:celular",
                               "titulo": "t", "capa": None})()
        laudo = {}
        with self.assertRaises(Y.EnvioNaoTerminou):
            youtube.publicar_como_configurado(
                video, config={"youtube": {"modo": "navegador"}},
                canal="builds", prova=laudo)
        self.assertEqual([], registros)
        self.assertTrue(laudo["clicou"])


# ------------------------------------------------------------ a conferencia
AGORA = datetime(2026, 10, 21, 13, 0)


def _linha(video_id, youtube_id, horas_atras):
    quando = (AGORA - timedelta(hours=horas_atras)).isoformat(timespec="seconds")
    return {"plataforma": "youtube", "video_id": video_id,
            "titulo": f"titulo {video_id}", "youtube_id": youtube_id,
            "quando": quando, "url": f"https://youtu.be/{youtube_id}",
            "publicado": True}


def _video(youtube_id, video_id, upload="processed"):
    return {"id": youtube_id, "titulo": f"titulo {video_id}",
            "privacidade": "public", "upload": upload, "definicao": "hd",
            "publicado_em": "2026-10-20T22:00:00Z"}


_CONFERIR = conferencia.conferir        # o de verdade, mesmo com o duble


def _conferir(publicados, no_canal):
    return _CONFERIR("builds", publicados=publicados, no_canal=no_canal,
                     agora=AGORA, aceitos={})


class ConferenciaTests(unittest.TestCase):

    def test_estreia_publica_e_vazia_de_19_10_vai_a_conferir(self):
        """8Rp3WUDsBgA: `uploaded` desde 19/10, publica, 0 views."""
        ficha = _conferir([_linha("generation_00121:estreia:celular",
                                  "8Rp3WUDsBgA", 13.0)],
                          [_video("8Rp3WUDsBgA",
                                  "generation_00121:estreia:celular",
                                  upload="uploaded")])
        (item,) = ficha["envio_cortado"]
        self.assertEqual("8Rp3WUDsBgA", item["youtube_id"])
        self.assertEqual("sujo", ficha["veredito"])

    def test_uploaded_de_4h40_ainda_pode_estar_processando(self):
        """6-APf13ZQXc (05/10): `uploaded` 4h40 depois e terminou
        `processed`. Com o limite de 2 h seria alarme falso."""
        ficha = _conferir([_linha("d1", "6-APf13ZQXc", 4 + 40 / 60)],
                          [_video("6-APf13ZQXc", "d1", upload="uploaded")])
        self.assertEqual([], ficha["envio_cortado"])
        self.assertEqual(12.0, conferencia.HORAS_ATE_O_ENVIO_CORTADO)

    def test_processado_nao_e_cortado_e_vai_para_envio_ok(self):
        ficha = _conferir([_linha("d1", "aaaaaaaaaaa", 13.0)],
                          [_video("aaaaaaaaaaa", "d1")])
        self.assertEqual([], ficha["envio_cortado"])
        self.assertEqual(["d1"], ficha["envio_ok"])
        self.assertEqual("limpo", ficha["veredito"])

    def test_sem_video_no_canal_com_a_lista_provada_inteira(self):
        """So com `declarados` > 0 e todos os publicos na lista."""
        lista = metricas.ListaDoCanal(
            [_video("bbbbbbbbbbb", "outro")])
        lista.declarados = 1
        ficha = _conferir([_linha("d1", "aaaaaaaaaaa", 13.0)], lista)
        (item,) = ficha["envio_cortado"]
        self.assertEqual("sem video no canal", item["motivo"])

    def test_sem_video_sem_declarados_nao_prova(self):
        """CASO ZERO (conferente, 21/10): `conferir_lista` = None (lista sem
        `declarados`) dava o ledger inteiro como "sem video" — 21 linhas de
        builds e 28 de historias marcadas."""
        ficha = _conferir([_linha("d1", "aaaaaaaaaaa", 13.0),
                           _linha("d2", "ccccccccccc", 20.0)], [])
        self.assertEqual([], ficha["envio_cortado"])

    def test_sem_video_com_zero_declarados_nao_prova(self):
        """Lista vazia com `declarados == 0` (o token de OUTRO canal) e
        "inteira" para `conferir_lista`, e nao prova nada."""
        lista = metricas.ListaDoCanal()
        lista.declarados = 0
        ficha = _conferir([_linha("d1", "aaaaaaaaaaa", 13.0)], lista)
        self.assertEqual([], ficha["envio_cortado"])

    def test_sem_video_com_a_lista_incompleta_nao_prova(self):
        lista = metricas.ListaDoCanal()
        lista.declarados = 5
        ficha = _conferir([_linha("d1", "aaaaaaaaaaa", 13.0)], lista)
        self.assertEqual([], ficha["envio_cortado"])

    def test_pedaco_preso_segura_o_envio_ok(self):
        linha = _linha("h1", "aaaaaaaaaaa", 13.0)
        linha["youtube_ids"] = ["aaaaaaaaaaa", "ddddddddddd"]
        ficha = _conferir([linha], [_video("aaaaaaaaaaa", "h1"),
                                    _video("ddddddddddd", "h1",
                                           upload="uploaded")])
        self.assertEqual([], ficha["envio_ok"])
        (item,) = ficha["envio_cortado"]
        self.assertEqual("ddddddddddd", item["youtube_id"])

    def test_duas_linhas_do_mesmo_video_cortado_manda(self):
        """Conferente, 21/10: linha velha presa em `uploaded` ha 30 h e linha
        nova `processed` ha 13 h, mesmo `video_id`. O video caia nas duas
        listas e cada passada soltava e marcava de novo, com um ERRO."""
        ficha = _conferir([_linha("Z", "zzzzzzzzzz1", 30.0),
                           _linha("Z", "zzzzzzzzzz2", 13.0)],
                          [_video("zzzzzzzzzz1", "Z", upload="uploaded"),
                           _video("zzzzzzzzzz2", "Z")])
        self.assertEqual(["Z"], [i["video_id"] for i in ficha["envio_cortado"]])
        self.assertEqual([], ficha["envio_ok"])

    def test_linha_nao_publicada_nao_entra(self):
        linha = _linha("d1", "aaaaaaaaaaa", 13.0)
        linha["publicado"] = False
        ficha = _conferir([linha], [_video("aaaaaaaaaaa", "d1",
                                           upload="uploaded")])
        self.assertEqual([], ficha["envio_cortado"])

    def test_caso_zero(self):
        ficha = _conferir([], [])
        self.assertEqual([], ficha["envio_cortado"])
        self.assertEqual("limpo", ficha["veredito"])


class PousoNaConferenciaTests(unittest.TestCase):

    def setUp(self):
        from builds import atividade
        from builds.publicar import desfecho, sinais
        self.diario, self.marcas, self.ja = [], [], set()
        ficha = _conferir([_linha("generation_00121:estreia:celular",
                                  "8Rp3WUDsBgA", 13.0)],
                          [_video("8Rp3WUDsBgA",
                                  "generation_00121:estreia:celular",
                                  upload="uploaded")])
        _trocar(self, conferencia, "conferir", lambda *a, **k: dict(ficha))
        _trocar(self, conferencia, "salvar", lambda f: None)
        _trocar(self, conferencia, "ultima", lambda canal="builds": {})
        _trocar(self, sinais, "ler_diario", lambda caminho=None: [])
        _trocar(self, metricas, "publicados", lambda canal="builds": [])
        _trocar(self, atividade, "registrar",
                lambda *a, **k: self.diario.append((a, k)))

        def a_conferir(canal, plataforma="tiktok"):
            return set(self.ja)
        _trocar(self, desfecho, "a_conferir", a_conferir)

        self.no_disco = {}             # {video_id: estado} da lista dublada
        self.soltas = []

        def marcar(canal, video_id, estado, plataforma="tiktok", **k):
            self.marcas.append((canal, video_id, estado, plataforma))
            self.ja.add(video_id)
            self.no_disco[video_id] = estado
            return True
        _trocar(self, desfecho, "marcar_para_conferir", marcar)
        _trocar(self, desfecho, "marcas",
                lambda canal, plataforma="tiktok": {
                    v: {"estado": e} for v, e in self.no_disco.items()})

        def soltar(canal, video_id, plataforma="tiktok", *, prefixo):
            if not self.no_disco.get(video_id, "").startswith(prefixo):
                return False
            self.soltas.append((canal, video_id, plataforma, prefixo))
            self.no_disco.pop(video_id)
            self.ja.discard(video_id)
            return True
        _trocar(self, desfecho, "soltar_marca", soltar)
        self.ficha = ficha

    def _alarmes(self):
        return [a for a, k in self.diario
                if k.get("etapa") == "conferencia.envio_cortado"]

    def test_marca_e_acende_uma_vez(self):
        conferencia.conferir_tudo(("builds",), log=lambda _t: None,
                                  agora=AGORA)
        (marca,) = self.marcas
        self.assertEqual(("builds", "generation_00121:estreia:celular",
                          "youtube"), (marca[0], marca[1], marca[3]))
        self.assertTrue(marca[2].startswith(conferencia.PREFIXO_DO_ENVIO))
        self.assertIn("8Rp3WUDsBgA", marca[2])
        (alarme,) = self._alarmes()
        self.assertEqual("conferencia", alarme[0])
        # A rodada seguinte da noite: ja esta na lista, nao acende de novo.
        conferencia.conferir_tudo(("builds",), log=lambda _t: None,
                                  agora=AGORA)
        self.assertEqual(1, len(self.marcas))
        self.assertEqual(1, len(self._alarmes()))

    def test_a_marca_sai_sozinha_quando_o_video_processa(self):
        """O preso de ontem que terminou: a conferencia o ve `processed` e a
        marca `[envio] ` sai; a de clique (sem prefixo) fica."""
        vid = "generation_00121:estreia:celular"
        conferencia.conferir_tudo(("builds",), log=lambda _t: None,
                                  agora=AGORA)
        self.assertIn(vid, self.no_disco)
        self.no_disco["duelo_00099:duelo:celular"] = (
            "cliquei em publicar e nao veio confirmacao")
        processado = _conferir(
            [_linha(vid, "8Rp3WUDsBgA", 13.0),
             _linha("duelo_00099:duelo:celular", "eeeeeeeeeee", 13.0)],
            [_video("8Rp3WUDsBgA", vid),
             _video("eeeeeeeeeee", "duelo_00099:duelo:celular")])
        self.assertEqual([], processado["envio_cortado"])
        _trocar(self, conferencia, "conferir",
                lambda *a, **k: dict(processado))
        conferencia.conferir_tudo(("builds",), log=lambda _t: None,
                                  agora=AGORA)
        self.assertEqual([("builds", vid, "youtube",
                           conferencia.PREFIXO_DO_ENVIO)], self.soltas)
        self.assertNotIn(vid, self.no_disco)
        self.assertIn("duelo_00099:duelo:celular", self.no_disco,
                      "a marca de clique so sai por conferencia humana")

    def test_duas_linhas_nao_viram_solta_e_marca_a_cada_passada(self):
        vid = "generation_00121:estreia:celular"
        duas = _conferir(
            [_linha(vid, "8Rp3WUDsBgA", 30.0), _linha(vid, "NovoEnvio01", 13.0)],
            [_video("8Rp3WUDsBgA", vid, upload="uploaded"),
             _video("NovoEnvio01", vid)])
        _trocar(self, conferencia, "conferir", lambda *a, **k: dict(duas))
        for _passada in range(3):
            conferencia.conferir_tudo(("builds",), log=lambda _t: None,
                                      agora=AGORA)
        self.assertEqual([], self.soltas)
        self.assertEqual(1, len(self.marcas))
        self.assertEqual(1, len(self._alarmes()), "um ERRO, e nao um por passada")

    def test_lista_ilegivel_acende_e_nao_grava(self):
        from builds.publicar import desfecho

        def ilegivel(*_a, **_k):
            raise desfecho.NaoConsegviLer("corrompido")
        _trocar(self, desfecho, "a_conferir", ilegivel)
        conferencia.conferir_tudo(("builds",), log=lambda _t: None,
                                  agora=AGORA)
        self.assertEqual([], self.marcas)
        (alarme,) = self._alarmes()
        self.assertIn("nao abriu", alarme[2])


if __name__ == "__main__":
    unittest.main()
