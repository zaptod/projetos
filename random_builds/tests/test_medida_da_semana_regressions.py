# -*- coding: utf-8 -*-
"""A comparacao da semana tem de sair SOZINHA, e nunca dar nota boa a nada.

21/10/2026. O PLANO mede UMA mudanca por semana (views por video, % que
assistiu, inscritos por mil views), e o Adrian nao le numero a mao. O que
faltava no coletor, e o teste de cada um:

- a HORA de cada numero (fotografia diaria por parte e por video; views do
  YouTube e do TikTok com `views_medidas_em`);
- a leitura de HORA EM HORA dos videos com menos de 48 h (1 unidade de cota),
  pendurada no disparo de hora em hora da geracao de builds;
- `engagedViews` na Analytics (vazio = nao medido, recusa nao derruba a
  retencao);
- TikTok: situacao de cada post, punicao, conselho de qualidade, serie
  diaria e seguidores da conta (vazio = NAO MEDI, nunca "sem punicao");
- a serie de inscritos na fotografia;
- a comparacao NA MESMA IDADE (+-5 h, sem interpolar) com o rotulo de
  certeza da analise.

Em cada um, o caso ZERO: nenhum video novo, API vazia, Studio mudo.
Nada aqui toca rede, navegador, o diario ou as pastas de verdade.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from builds import atividade
from builds.publicar import analise, hora_a_hora, mesma_idade, metricas
from builds.publicar import tiktok_metricas as T

AGORA = datetime(2026, 10, 21, 10, 2)
INICIO = datetime(2026, 10, 20, 9, 0)
SEMANA = {"semana": 1, "inicio": INICIO, "fim": INICIO + timedelta(days=7),
          "antes_de": INICIO - timedelta(days=7), "mudanca": "inglês",
          "canal": "builds", "formato": "duelo", "plataformas": ["youtube", "tiktok"],
          "idades_h": [6.0, 12.0, 24.0, 48.0], "tolerancia_h": 5.0}


class _Resposta:
    def __init__(self, corpo, status=200, url=""):
        self._corpo, self.status_code, self.url = corpo, status, url
        self.ok = 200 <= status < 300
        self.text = json.dumps(corpo)

    def json(self):
        return self._corpo


class _Diario:
    """Troca `atividade.registrar` por uma lista (nada vai ao diario real)."""

    def __init__(self, caso):
        self.linhas = []
        real = atividade.registrar
        atividade.registrar = lambda *a, **k: self.linhas.append((a, k))
        caso.addCleanup(setattr, atividade, "registrar", real)


def _ledger(*itens):
    """`(id, quando, plataforma)` -> linhas publicadas do ledger."""
    return [{"youtube_id": yid, "quando": q.isoformat(timespec="seconds"),
             "plataforma": p, "url": "https://youtu.be/x", "publicado": True}
            for yid, q, p in itens]


def _api(ids_views):
    corpo = {"items": [{"id": yid, "statistics": {"viewCount": str(v), "likeCount": "1",
                                                  "commentCount": "0"},
                        "status": {"privacyStatus": "public"}}
                       for yid, v in ids_views.items()]}
    return _Resposta(corpo)


class _Pasta:
    def __init__(self, caso):
        self._tmp = tempfile.TemporaryDirectory()
        caso.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)


# ===================================================== hora em hora
class HoraEmHoraTests(unittest.TestCase):

    def setUp(self):
        self.pasta = _Pasta(self).raiz
        real_pasta, real_get = hora_a_hora.PASTA, metricas._get
        hora_a_hora.PASTA = self.pasta / "_metricas_hora"
        self.addCleanup(setattr, hora_a_hora, "PASTA", real_pasta)
        self.chamadas = []

        def get(api, url, **k):
            self.chamadas.append(k.get("params") or {})
            return self.resposta
        metricas._get = get
        self.addCleanup(setattr, metricas, "_get", real_get)
        self.resposta = _api({})
        self.diario = _Diario(self)

    def _gravadas(self):
        return hora_a_hora.carregar(dias=2, hoje=AGORA.date())

    def test_zero_video_novo_e_um_evento_sem_gastar_cota(self):
        velho = _ledger(("antigo", AGORA - timedelta(hours=49), "youtube"))
        leitura = hora_a_hora.disparo("builds", AGORA, log=lambda *_a: None,
                                      linhas=velho, token="t")
        self.assertEqual("vazio", leitura["estado"])
        self.assertEqual(0, leitura["chamadas"])
        self.assertEqual([], self.chamadas, "sem video novo nao vai a rede")
        # Ausencia de video e um evento COM numero, gravado.
        self.assertEqual(1, len(self._gravadas()))
        self.assertEqual(0, self._gravadas()[0]["pedidos"])
        self.assertIn("nenhuma cota", hora_a_hora.texto(leitura))

    def test_le_os_novos_numa_chamada_so_com_a_idade_em_horas(self):
        linhas = _ledger(("a", AGORA - timedelta(hours=24, minutes=19), "youtube"),
                         ("a", AGORA - timedelta(hours=20), "youtube"),     # repetida
                         ("b", AGORA - timedelta(hours=12), "youtube"),
                         ("tk", AGORA - timedelta(hours=2), "tiktok"),
                         (None, AGORA - timedelta(hours=3), "youtube"),     # sem id
                         ("velho", AGORA - timedelta(hours=60), "youtube"))
        self.resposta = _api({"a": 150, "b": 40})
        leitura = hora_a_hora.disparo("builds", AGORA, log=lambda *_a: None,
                                      linhas=linhas, token="t")
        self.assertEqual("ok", leitura["estado"])
        self.assertEqual(1, len(self.chamadas))
        self.assertEqual({"a", "b"}, set(self.chamadas[0]["id"].split(",")))
        self.assertEqual("statistics,status", self.chamadas[0]["part"])
        self.assertEqual(24.32, leitura["videos"]["a"]["idade_h"])  # a linha MAIS VELHA manda
        self.assertEqual(150, leitura["videos"]["a"]["views"])
        self.assertEqual(1, leitura["sem_id"])
        self.assertEqual([], self.diario.linhas)

    def test_api_que_nao_devolve_ninguem_e_erro_e_nao_zero_views(self):
        linhas = _ledger(("a", AGORA - timedelta(hours=5), "youtube"))
        self.resposta = _api({})
        leitura = hora_a_hora.disparo("builds", AGORA, log=lambda *_a: None,
                                      linhas=linhas, token="t")
        self.assertEqual("erro", leitura["estado"])
        self.assertIn("NadaDevolvido", leitura["erro"])
        self.assertEqual(["a"], leitura["nao_devolvidos"])
        self.assertEqual(1, len(self.diario.linhas))

    def test_excecao_vira_alarme_uma_vez_por_dia_e_nunca_levanta(self):
        linhas = _ledger(("a", AGORA - timedelta(hours=5), "youtube"))

        def cai(*_a, **_k):
            raise ConnectionError("rede fora")
        metricas._get = cai
        for minutos in (0, 60, 120):
            leitura = hora_a_hora.disparo("builds", AGORA + timedelta(minutes=minutos),
                                          log=lambda *_a: None, linhas=linhas, token="t")
            self.assertEqual("erro", leitura["estado"])
        self.assertEqual(3, len(self._gravadas()), "cada falha fica gravada")
        self.assertEqual(1, len(self.diario.linhas), "mas avisa UMA vez por dia")
        self.assertEqual("metricas", self.diario.linhas[0][0][0])
        self.assertEqual(atividade.ERRO, self.diario.linhas[0][0][1])

    def test_segunda_leitura_em_menos_de_30_min_nao_gasta_cota(self):
        linhas = _ledger(("a", AGORA - timedelta(hours=5), "youtube"))
        self.resposta = _api({"a": 10})
        hora_a_hora.disparo("builds", AGORA, log=lambda *_a: None, linhas=linhas, token="t")
        segunda = hora_a_hora.disparo("builds", AGORA + timedelta(minutes=10),
                                      log=lambda *_a: None, linhas=linhas, token="t")
        self.assertEqual("pulada", segunda["estado"])
        self.assertEqual(1, len(self.chamadas))

    def test_mais_de_50_fica_o_mais_novo_e_o_corte_e_dito(self):
        linhas = _ledger(*[(f"v{i:02d}", AGORA - timedelta(minutes=10 + i), "youtube")
                           for i in range(53)])
        self.resposta = _api({f"v{i:02d}": i for i in range(53)})
        leitura = hora_a_hora.ler("builds", AGORA, linhas=linhas, token="t")
        self.assertEqual(50, len(self.chamadas[0]["id"].split(",")))
        self.assertEqual(3, leitura["fora_do_teto"])
        self.assertIn("v00", leitura["videos"])


class GanchoDoDisparoTests(unittest.TestCase):
    """A leitura mora no disparo de hora em hora da geracao (`main.py noite`)
    e acontece ANTES de qualquer saida dele — sem tarefa nova no Agendador."""

    def _rodar(self, **kw):
        from builds.pipeline import noite
        tmp = _Pasta(self).raiz
        real = noite.diario_do_dia
        noite.diario_do_dia = lambda agora=None: tmp / "noite.txt"
        self.addCleanup(setattr, noite, "diario_do_dia", real)
        return noite.rodar(config={"ativo": False}, relogio=lambda: AGORA,
                           tela=lambda *_a, **_k: None, **kw)

    def test_le_mesmo_com_a_geracao_desligada(self):
        chamadas = []
        resultado = self._rodar(leitura_da_hora=lambda: chamadas.append(1))
        self.assertEqual("desligada", resultado["motivo"])
        self.assertEqual([1], chamadas)

    def test_leitura_que_quebra_nao_derruba_o_disparo(self):
        def quebra():
            raise RuntimeError("boom")
        resultado = self._rodar(leitura_da_hora=quebra)
        self.assertEqual("desligada", resultado["motivo"])

    def test_sem_o_gancho_e_no_ensaio_nao_le(self):
        chamadas = []
        self._rodar()                                     # o padrao: nada
        self._rodar(ensaio=True, leitura_da_hora=lambda: chamadas.append(1))
        self.assertEqual([], chamadas)

    def test_a_tarefa_do_agendador_liga_o_gancho(self):
        fonte = (Path(metricas.RAIZ) / "main.py").read_text(encoding="utf-8")
        self.assertIn("leitura_da_hora=lambda: hora_a_hora.disparo(\"builds\")", fonte)


# ===================================================== YouTube: Analytics
class EngajadasTests(unittest.TestCase):

    def setUp(self):
        real_get, real_flag = metricas._get, metricas.ENGAJADAS_RECUSADAS
        self.addCleanup(setattr, metricas, "_get", real_get)
        self.addCleanup(setattr, metricas, "ENGAJADAS_RECUSADAS", real_flag)
        metricas.ENGAJADAS_RECUSADAS = False
        self.pedidos, self.respostas = [], []

        def get(api, url, **k):
            self.pedidos.append((k.get("params") or {}).get("metrics"))
            return self.respostas.pop(0)
        metricas._get = get

    def _curva(self):
        return _Resposta({"rows": [[0.0, 1.0], [1.0, 0.4]]})

    def test_engaged_views_pelo_cabecalho(self):
        cab = [{"name": n} for n in ("views", "averageViewDuration",
                                     "averageViewPercentage", "engagedViews")]
        self.respostas = [_Resposta({"columnHeaders": cab, "rows": [[120, 11.0, 52.5, 80]]}),
                          self._curva()]
        dado = metricas.retencao("x", "t", "2026-10-20")
        self.assertEqual(80, dado["engaged_views"])
        self.assertEqual(52.5, dado["media_percentual"])
        self.assertIn("engagedViews", self.pedidos[0])

    def test_recusa_das_engajadas_nao_derruba_a_retencao(self):
        recusa = _Resposta({"error": {"message": "Unknown identifier (engagedViews)",
                                      "errors": [{"reason": "badRequest"}]}}, status=400)
        self.respostas = [recusa, _Resposta({"rows": [[120, 11.0, 52.5]]}), self._curva(),
                          _Resposta({"rows": [[30, 9.0, 40.0]]}), self._curva()]
        dado = metricas.retencao("x", "t", "2026-10-20")
        self.assertEqual(52.5, dado["media_percentual"])
        self.assertNotIn("engaged_views", dado, "recusa nao e zero")
        self.assertIn("engagedViews", dado["engaged_views_erro"])
        # O proximo video nao paga duas consultas.
        dado2 = metricas.retencao("y", "t", "2026-10-20")
        self.assertNotIn("engagedViews", self.pedidos[3])
        self.assertEqual(40.0, dado2["media_percentual"])

    def test_sem_linha_e_linha_de_zeros_nao_tem_engajada(self):
        self.respostas = [_Resposta({"rows": []})]
        self.assertNotIn("engaged_views", metricas.retencao("x", "t", "2026-10-20"))
        self.respostas = [_Resposta({"rows": [[0, 0, 0, 0]]})]
        self.assertNotIn("engaged_views", metricas.retencao("x", "t", "2026-10-20"))

    def test_estatisticas_guardam_a_hora_das_views(self):
        self.respostas = [_Resposta({"items": [{"id": "x", "statistics": {"viewCount": "3"},
                                                "contentDetails": {}, "snippet": {},
                                                "status": {}}]})]
        antes = datetime.now().isoformat(timespec="seconds")
        dado = metricas.estatisticas(["x"], "t")["x"]
        self.assertGreaterEqual(dado["views_medidas_em"], antes)


# ===================================================== TikTok: post e conta
class SituacaoDoPostTests(unittest.TestCase):

    def test_guarda_status_visibilidade_revisao_e_permissoes_crus(self):
        bruto = {"item_id": "1", "post_time": "1789600000", "play_count": "4",
                 "status": 102, "visibility": 1, "in_review": True,
                 "permissions": {"duet": False}, "lixo": "x"}
        item = T.item_do_studio(bruto)
        self.assertEqual({"status": 102, "visibility": 1, "in_review": True,
                          "permissions": {"duet": False}}, item["situacao"])

    def test_sem_os_campos_e_nao_medi_e_nao_post_normal(self):
        item = T.item_do_studio({"item_id": "1", "play_count": "4"})
        self.assertNotIn("situacao", item)
        self.assertIsNone(T.situacao_do_item({"item_id": "1"}))

    def test_a_lista_guarda_a_hora_em_que_as_views_chegaram(self):
        lista = T.Lista()
        lista.receber({"item_list": [{"item_id": "1", "play_count": "2"}], "cursor": 1})
        self.assertTrue(lista.itens["1"]["views_medidas_em"])


class ContaDoTikTokTests(unittest.TestCase):

    def test_serie_com_data(self):
        corpo = {"vv_history": {"status": 0, "value": [
            {"date": "2026-10-19", "value": 12}, {"date": "2026-10-20", "value": 3}]},
            "follower_num": {"status": 0, "value": 41}}
        s = T.serie_da_conta([corpo])
        self.assertEqual([["2026-10-19", 12], ["2026-10-20", 3]], s["vv_history"])
        self.assertEqual(41, s["seguidores"])
        self.assertFalse(s["vv_history_sem_datas"])

    def test_serie_sem_data_nao_inventa_o_dia(self):
        s = T.serie_da_conta([{"vv_history": {"value": [5, 0, 7]}}])
        self.assertEqual([[None, 5], [None, 0], [None, 7]], s["vv_history"])
        self.assertTrue(s["vv_history_sem_datas"])

    def test_status_de_erro_e_campo_ausente_sao_nao_medidos(self):
        s = T.serie_da_conta([{"vv_history": {"status": 5, "value": []}}])
        self.assertIsNone(s["vv_history"])
        self.assertIsNone(T.serie_da_conta([])["vv_history"])
        self.assertIsNone(T.serie_da_conta([])["seguidores"])

    def test_sem_resposta_de_punicao_e_nao_lida_nunca_limpa(self):
        ficha = T.ficha_da_conta("builds", punicoes=[], qualidades=[], insights=[], agora=AGORA)
        self.assertEqual({"lida": False}, ficha["punicao"])
        self.assertEqual({"lida": False}, ficha["qualidade"])
        self.assertEqual("nao_lida", T.resumo_da_conta(ficha)["punicao"])

    def test_punicao_lida_guarda_o_bruto(self):
        ficha = T.ficha_da_conta("builds", punicoes=[{"penalty_list": []}],
                                 qualidades=[{"advice": []}], insights=[], agora=AGORA)
        self.assertTrue(ficha["punicao"]["lida"])
        self.assertEqual({"penalty_list": []}, ficha["punicao"]["bruto"])


class _RespostaTk:
    def __init__(self, url, corpo):
        self.url, self._corpo = url, corpo

    def json(self):
        return self._corpo


class StudioComConta:
    """O Studio de mentira com a lista (1 post), a punicao chegando no
    conteudo e a visao geral mandando `vv_history` — ou caindo."""

    def __init__(self, post_time, *, visao_quebra=False):
        self.handlers, self.post_time, self.visao_quebra = [], post_time, visao_quebra
        self.url = "https://www.tiktok.com/tiktokstudio/content"
        self.visitas = []

    def on(self, _evento, handler):
        self.handlers.append(handler)

    def _manda(self, url, corpo):
        for h in self.handlers:
            h(_RespostaTk(url, corpo))

    def goto(self, url, **_k):
        self.visitas.append(url)
        if url == T.URL_CONTEUDO:
            self._manda("https://x/tiktok/creator/manage/item_list/v1/",
                        {"item_list": [{"item_id": "t1", "post_time": str(self.post_time),
                                        "play_count": "9", "in_review": False}],
                         "cursor": 1, "has_more": False})
            self._manda("https://x/tiktok/creator/getPenaltyDetails/", {"penalty": 0})
        elif url == T.URL_VISAO_GERAL:
            if self.visao_quebra:
                raise TimeoutError("visao geral nao carregou")
            self._manda("https://x/aweme/v2/data/insight/",
                        {"vv_history": {"value": [{"date": "2026-10-20", "value": 14}]},
                         "follower_num": {"value": 7}})

    def evaluate(self, _js):
        pass

    def wait_for_timeout(self, _ms):
        pass


class ColetaDaContaTests(unittest.TestCase):

    def setUp(self):
        from builds.identity import browser
        tmp = _Pasta(self).raiz
        reais = (browser.contexto_persistente, browser.pagina, metricas.publicados,
                 metricas.PASTA)

        def volta():
            (browser.contexto_persistente, browser.pagina, metricas.publicados,
             metricas.PASTA) = reais
        self.addCleanup(volta)
        self.post = 1789600000
        self.pagina = StudioComConta(self.post)

        class _Ctx:
            def __enter__(self):
                return object()

            def __exit__(self, *_a):
                return False
        browser.contexto_persistente = lambda **_k: _Ctx()
        browser.pagina = lambda _c: self.pagina
        metricas.PASTA = tmp / "_metricas"
        quando = datetime.fromtimestamp(self.post + 2).isoformat(timespec="seconds")
        metricas.publicados = lambda canal="builds": [
            {"plataforma": "tiktok", "quando": quando, "video_id": "d:duelo:celular"}]
        self.diario = _Diario(self)

    def test_grava_a_situacao_do_post_e_a_ficha_da_conta(self):
        resumo = {}
        salvos = T.coletar("builds", log=lambda *_a: None, analisar=False, resumo=resumo)
        self.assertEqual({"in_review": False}, salvos[0]["situacao"])
        fichas = T.carregar_contas("builds")
        self.assertEqual(1, len(fichas))
        ficha = next(iter(fichas.values()))
        self.assertEqual([["2026-10-20", 14]], ficha["vv_history"])
        self.assertEqual(7, ficha["seguidores"])
        self.assertTrue(ficha["punicao"]["lida"])
        self.assertFalse(ficha["qualidade"]["lida"])
        self.assertEqual({"serie_dias": 1, "seguidores": 7, "punicao": "lida",
                          "qualidade": "nao_lida"}, resumo["conta"])
        self.assertIn(T.URL_VISAO_GERAL, self.pagina.visitas)
        self.assertEqual([], self.diario.linhas)

    def test_visao_geral_que_cai_nao_leva_os_posts_e_vira_alarme(self):
        self.pagina.visao_quebra = True
        resumo = {}
        salvos = T.coletar("builds", log=lambda *_a: None, analisar=False, resumo=resumo)
        self.assertEqual(1, len(salvos), "os posts continuam gravados")
        self.assertIn("visao geral", resumo["conta"]["erro"])
        self.assertIsNone(resumo["conta"]["serie_dias"])
        self.assertEqual(1, len(self.diario.linhas))


# ===================================================== fotografia
def _reg(id_, quando, views, plataforma="youtube", formato="duelo", medido=None,
         publico=True, ret=None, engaged=None, canal="builds"):
    return {"id": id_, "canal": canal, "plataforma": plataforma, "formato": formato,
            "quando": quando.isoformat(timespec="seconds"), "views": views, "likes": 0,
            "retencao": ret, "publico": publico, "titulo": f"t {id_}",
            "idade_dias": round((AGORA - quando).total_seconds() / 86400, 2),
            "medido_em": (medido or AGORA).isoformat(timespec="seconds"),
            "engaged_views": engaged}


class FotografiaTests(unittest.TestCase):

    def test_hora_por_parte_e_por_video_e_inscritos(self):
        cob = {"estado": "ok", "partes": {"builds": {"ultimo_ok": "2026-10-21T07:19:45"},
                                          "builds_tiktok": {"ultimo_ok": ""}}}
        serie = {"builds": {"inscritos": 15, "buscado_em": "2026-10-21T08:00:00",
                            "dias": [["2026-10-17", 900, 10, 2, 1]]}}
        foto = analise.fotografia([_reg("a", AGORA - timedelta(days=1), 40, engaged=30)],
                                  cob, serie, AGORA)
        self.assertEqual(40, foto["builds"]["a"][0], "quem le [0] continua lendo views")
        self.assertEqual(AGORA.isoformat(timespec="seconds"), foto["builds"]["a"][3])
        self.assertEqual(30, foto["builds"]["a"][4])
        self.assertEqual("2026-10-21T07:19:45", foto["quando_das_partes"]["builds"])
        self.assertIsNone(foto["quando_das_partes"]["builds_tiktok"])
        self.assertEqual(15, foto["canal"]["builds"]["inscritos"])
        self.assertEqual([["2026-10-17", 2, 1]], foto["canal"]["builds"]["dias"])

    def test_registro_leva_a_hora_e_as_engajadas_so_quando_vieram(self):
        base = {"youtube_id": "a", "quando": "2026-10-20T09:43:33", "views": 5,
                "privacidade": "public", "atualizado": "2026-10-21T07:10:00"}
        r = analise.registro({**base, "views_medidas_em": "2026-10-21T07:05:41"},
                             "builds", "youtube", AGORA)
        self.assertEqual("2026-10-21T07:05:41", r["medido_em"])
        self.assertIsNone(r["engaged_views"])
        r = analise.registro({**base, "engaged_views": 0}, "builds", "youtube", AGORA)
        self.assertEqual("2026-10-21T07:10:00", r["medido_em"])
        self.assertEqual(0, r["engaged_views"])


# ===================================================== mesma idade
def _leitura(quando, videos):
    return {"quando": quando.isoformat(timespec="seconds"), "canal": "builds",
            "estado": "ok", "videos": {k: {"views": v} for k, v in videos.items()}}


class MesmaIdadeTests(unittest.TestCase):

    def test_sem_semana_no_config_nao_ha_comparacao(self):
        c = mesma_idade.comparar([], AGORA, None)
        self.assertEqual("sem_semana", c["estado"])
        self.assertIn("não há comparação", c["texto"])

    def test_zero_video_novo_nao_e_sem_efeito(self):
        antigo = _reg("v", INICIO - timedelta(days=2), 100)
        c = mesma_idade.comparar([antigo], AGORA, SEMANA)
        self.assertEqual("sem_novos", c["estado"])
        self.assertIn("NÃO há comparação", c["texto"])
        self.assertNotIn("SUBIU", c["texto"])
        self.assertNotIn("CAIU", c["texto"])

    def test_api_vazia_nenhuma_leitura_e_nenhum_video(self):
        c = mesma_idade.comparar([], AGORA, SEMANA, fotos={}, leituras=[])
        self.assertEqual("sem_novos", c["estado"])
        for i in c["plataformas"]["youtube"]["idades"]:
            self.assertEqual("sem_comparacao", i["sentido"])

    def test_compara_na_mesma_idade_e_nao_pelo_total_de_hoje(self):
        novo = _reg("n", AGORA - timedelta(hours=24, minutes=20), 300)
        antigo = _reg("a", INICIO - timedelta(days=3), 5000)   # 4 dias no ar: total alto
        leituras = [_leitura(AGORA - timedelta(minutes=20), {"n": 300})]
        fotos = {"2026-10-18": {"quando_das_partes": {"builds": "2026-10-18T07:30:00"},
                                "builds": {"a": [120, 0, None]}}}
        semana = {**SEMANA, "antes_de": INICIO - timedelta(days=7)}
        antigo["quando"] = datetime(2026, 10, 17, 7, 0).isoformat()
        c = mesma_idade.comparar([novo, antigo], AGORA, semana, fotos=fotos, leituras=leituras)
        i24 = next(i for i in c["plataformas"]["youtube"]["idades"] if i["idade_h"] == 24)
        self.assertEqual(300, i24["novos"]["mediana"])
        self.assertEqual(120, i24["antigos"]["mediana"], "o antigo AOS 24,5 h, nao os 5000 de hoje")
        self.assertEqual(2.5, i24["razao"])
        self.assertEqual("incerto", i24["confianca"], "1 contra 1 nao e conclusao")
        self.assertIn("INCERTO", c["texto"])

    def test_tolerancia_de_5_h_sem_interpolar(self):
        nasceu = datetime(2026, 10, 20, 10, 0)
        pontos = [(nasceu + timedelta(hours=18), 10, "x"), (nasceu + timedelta(hours=30), 50, "x")]
        self.assertIsNone(mesma_idade.views_na_idade(pontos, nasceu, 24, 5.0),
                          "18 e 30 h ficam a 6 h de 24: nao se inventa o meio")
        pontos.append((nasceu + timedelta(hours=28), 40, "x"))
        self.assertEqual((40, 28.0, "x"), mesma_idade.views_na_idade(pontos, nasceu, 24, 5.0))

    def test_novo_que_ainda_nao_chegou_na_idade_esta_juntando(self):
        novo = _reg("n", AGORA - timedelta(hours=10), 30)
        antigo = _reg("a", datetime(2026, 10, 17, 9, 0), 80,
                      medido=datetime(2026, 10, 19, 9, 0))
        c = mesma_idade.comparar([novo, antigo], AGORA, SEMANA,
                                 leituras=[_leitura(AGORA - timedelta(minutes=2), {"n": 30})])
        i48 = next(i for i in c["plataformas"]["youtube"]["idades"] if i["idade_h"] == 48)
        self.assertEqual(1, i48["novos"]["juntando"])
        self.assertEqual(0, i48["novos"]["n"])
        self.assertIn("48 h: ainda juntando", c["texto"])

    def test_privado_fica_fora_e_e_contado(self):
        regs = [_reg("p", AGORA - timedelta(hours=8), 0, publico=False),
                _reg("s", AGORA - timedelta(hours=8), 0, publico=None),
                _reg("ok", AGORA - timedelta(hours=8), 9)]
        c = mesma_idade.comparar(regs, AGORA, SEMANA)
        b = c["plataformas"]["youtube"]
        self.assertEqual(1, b["novos"])
        self.assertEqual({"privados": 1, "sem_status": 1}, b["fora"]["novos"])

    def test_muitos_de_cada_lado_e_diferenca_grande_da_certeza(self):
        # 12 novos lidos de hora em hora aos 24 h; 12 antigos que a
        # fotografia diaria pegou aos 24 h (o total de hoje, 999, e de 6 dias).
        agora = INICIO + timedelta(days=2)
        regs, leituras, fotos = [], [], {}
        for k in range(12):
            nasceu = INICIO + timedelta(hours=2 + k)
            regs.append(_reg(f"n{k}", nasceu, 200 + k, medido=agora))
            leituras.append(_leitura(nasceu + timedelta(hours=24), {f"n{k}": 200 + k}))
            velho = INICIO - timedelta(days=6) + timedelta(hours=k)
            regs.append(_reg(f"a{k}", velho, 999, medido=agora))
            dia = (velho + timedelta(hours=24)).date().isoformat()
            fotos.setdefault(dia, {"builds": {}})["builds"][f"a{k}"] = [
                20 + k, 0, None, (velho + timedelta(hours=24)).isoformat()]
        c = mesma_idade.comparar(regs, agora, SEMANA, leituras=leituras, fotos=fotos)
        i24 = next(i for i in c["plataformas"]["youtube"]["idades"] if i["idade_h"] == 24)
        self.assertEqual((12, 12), (i24["novos"]["n"], i24["antigos"]["n"]))
        self.assertEqual("claro", i24["confianca"])
        self.assertEqual("subiu", i24["sentido"])
        self.assertIn("SUBIU [certeza clara]", c["texto"])

    def test_fotografia_antiga_sem_hora_usa_o_log_ou_fica_fora(self):
        tmp = _Pasta(self).raiz
        (tmp / "auto_20261020.txt").write_text(
            "07:02:02 [auto] disparo das 07:02\n"
            "07:27:29 327 video(s) atualizados em E:\\projetos\\random_builds\\outputs\\_metricas\n"
            "07:36:18 [tiktok-metricas] builds: 312 video(s) gravados em E:\\x\n"
            "07:51:05 341 video(s) atualizados em E:\\projetos\\historias\\outputs\\_metricas\n"
            "15:00:00 330 video(s) atualizados em E:\\projetos\\random_builds\\outputs\\_metricas\n",
            encoding="utf-8")
        horas = mesma_idade.horas_pelo_log(["2026-10-20", "2026-10-19"],
                                           {"2026-10-20": "2026-10-20T08:01:43"}, tmp)
        self.assertEqual({"builds": "2026-10-20T07:27:29",
                          "builds_tiktok": "2026-10-20T07:36:18",
                          "historias": "2026-10-20T07:51:05"}, horas["2026-10-20"],
                         "a coleta das 15h veio DEPOIS da fotografia: nao e a dela")
        self.assertNotIn("2026-10-19", horas)
        fotos = {"2026-10-20": {"builds": {"a": [10, 0, None]}},
                 "2026-10-19": {"builds": {"a": [4, 0, None]}}}
        obs, sem_hora = mesma_idade.observacoes([], fotos, [], horas)
        self.assertEqual(1, sem_hora, "a de 19/10 nao tem hora em lugar nenhum")
        self.assertEqual([(datetime(2026, 10, 20, 7, 27, 29), 10,
                           "fotografia diária (hora do log)")], obs[("builds", "a")])

    def test_inscritos_por_mil_dia_sem_dado_nao_e_zero(self):
        serie = {"dias": [["2026-10-14", 1000, 0, 3, 1], ["2026-10-20", 0, 0, 0, 0]]}
        r = mesma_idade.inscritos_por_mil(serie, SEMANA, AGORA)
        self.assertEqual(2.0, r["anterior"]["por_mil"])
        self.assertEqual(1, r["anterior"]["dias_com_dado"])
        self.assertEqual(6, r["anterior"]["dias_sem_dado"])
        self.assertIsNone(r["semana"]["por_mil"], "0 views nao vira 0 por mil")
        self.assertEqual("sem_serie", mesma_idade.inscritos_por_mil(None, SEMANA, AGORA)["estado"])

    def test_leitura_de_hora_em_hora_parada_acende(self):
        novo = _reg("n", AGORA - timedelta(hours=6), 30)
        c = mesma_idade.comparar([novo], AGORA, SEMANA, leituras=[])
        self.assertTrue(any("PARADA" in a for a in c["avisos"]))
        ok = mesma_idade.comparar([novo], AGORA, SEMANA,
                                  leituras=[_leitura(AGORA - timedelta(hours=1), {"n": 30})])
        self.assertFalse(any("PARADA" in a for a in ok["avisos"]))

    def test_config_escolhe_a_semana_comecada_e_acusa_data_torta(self):
        config = {"semanas": [{"semana": 1, "inicio": "2026-10-20T09:00"},
                              {"semana": 2, "inicio": "2026-10-27T09:00"}]}
        s, erro = mesma_idade.semana_vigente(AGORA, config)
        self.assertEqual((1, ""), (s["semana"], erro))
        self.assertEqual(datetime(2026, 10, 13, 9, 0), s["antes_de"])
        s, erro = mesma_idade.semana_vigente(AGORA, {"semanas": [{"inicio": "ontem"}]})
        self.assertIsNone(s)
        self.assertTrue(erro)
        self.assertEqual((None, ""), mesma_idade.semana_vigente(AGORA, {"semanas": []}))

    def test_o_config_do_repositorio_tem_a_semana_1(self):
        s, erro = mesma_idade.semana_vigente(AGORA)
        self.assertEqual("", erro)
        self.assertEqual(1, s["semana"])
        self.assertEqual(datetime(2026, 10, 20, 9, 0), s["inicio"])


# ===================================================== a pagina e o Telegram
class SaidaTests(unittest.TestCase):

    def test_a_pagina_mostra_a_semana_e_a_conta(self):
        cob = analise.cobertura({"agora": AGORA, "salvas": {}, "ledger": {}, "marca": None,
                                 "falhas": [], "series": {}, "historico": {}})
        a = analise.analisar([], cob, AGORA, semana=SEMANA, leituras=[], contas_tiktok={})
        self.assertEqual("sem_novos", a["mesma_idade"]["estado"])
        pagina = analise.pagina(a)
        self.assertIn("Medida da semana (mesma idade)", pagina)
        self.assertIn("NÃO há comparação", pagina)
        self.assertIn("Conta do TikTok", pagina)
        self.assertTrue(any("nunca foi lida" in x for x in a["avisos"]))

    def test_sem_contas_carregadas_nao_inventa_aviso(self):
        cob = analise.cobertura({"agora": AGORA, "salvas": {}, "ledger": {}, "marca": None,
                                 "falhas": [], "series": {}, "historico": {}})
        a = analise.analisar([], cob, AGORA)
        self.assertEqual("nao_carregado", a["conta_tiktok"]["estado"])
        self.assertEqual("sem_semana", a["mesma_idade"]["estado"])

    def test_conta_sem_punicao_lida_e_aviso_de_nao_medi(self):
        contas = {"builds": {"2026-10-21": {"punicao": {"lida": False},
                                            "qualidade": {"lida": True},
                                            "vv_history": [["2026-10-20", 4]],
                                            "seguidores": 3}}}
        c = analise.conta_tiktok(contas, [], AGORA)
        self.assertTrue(any("não li punição" in a for a in c["avisos"]))
        self.assertFalse(c["perfis"]["builds"]["punicao_lida"])

    def test_texto_da_semana_nunca_levanta(self):
        real = analise.carregar

        def quebra(*_a, **_k):
            raise OSError("disco")
        analise.carregar = quebra
        self.addCleanup(setattr, analise, "carregar", real)
        self.assertIn("FALHOU", analise.texto_da_semana(AGORA))


if __name__ == "__main__":
    unittest.main()
