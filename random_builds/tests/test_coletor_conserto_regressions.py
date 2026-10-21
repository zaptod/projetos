# -*- coding: utf-8 -*-
"""Os defeitos que o conferente achou no "coletor que mede sozinho" (21/10/2026).

Cada classe e um defeito, com o caso que a versao anterior errava e o caso
ZERO. Nada aqui toca rede, navegador, o diario ou as pastas de verdade.

1. /semana cortado no Telegram (8.398 caracteres na semana cheia; o corte de
   4.000 comia o TikTok e TODOS os avisos "!", inclusive "PARADA");
3. a serie da conta do TikTok vem SEM datas — a pagina dizia "16 dia(s)";
4. a visao geral saia do laco com a chave `vv_history` existindo (e nula), e
   punicao/qualidade so chegam na analise de um post;
5. o tipo do aviso de hora em hora era o nome da excecao (toda recusa e
   RuntimeError: so a 1a do dia avisava) e o motivo dizia "Analytics" fixo;
6. views nao numericas derrubavam a medida inteira;
7. "ainda juntando" usava `x - tol` (a janela de X vai ate `x + tol`);
8. titulo cortado deixava "— —", e a pagina tirava o recuo (YouTube e TikTok
   viravam uma lista so no celular).
(O 2, horario das 21:05, esta em `remoto/test_relatorio_semana.py`.)
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


def _semana(inicio=INICIO, idades=(6.0, 12.0, 24.0, 48.0, 72.0, 168.0)):
    return {"semana": 1, "inicio": inicio, "fim": inicio + timedelta(days=7),
            "antes_de": inicio - timedelta(days=7), "mudanca": "inglês",
            "canal": "builds", "formato": "duelo", "plataformas": ["youtube", "tiktok"],
            "idades_h": list(idades), "tolerancia_h": 5.0}


SEMANA = _semana(idades=(6.0, 12.0, 24.0, 48.0))


def _reg(id_, quando, views, plataforma="youtube", medido=None, titulo=None, agora=AGORA):
    return {"id": id_, "canal": "builds", "plataforma": plataforma, "formato": "duelo",
            "quando": quando.isoformat(timespec="seconds"), "views": views, "likes": 0,
            "retencao": 50.0, "publico": True, "titulo": titulo or f"t {id_}",
            "idade_dias": round((agora - quando).total_seconds() / 86400, 2),
            "medido_em": (medido or agora).isoformat(timespec="seconds")}


def _leitura(quando, videos):
    return {"quando": quando.isoformat(timespec="seconds"), "canal": "builds",
            "estado": "ok", "videos": {k: {"views": v} for k, v in videos.items()}}


class _Diario:
    def __init__(self, caso):
        self.linhas = []
        real = atividade.registrar
        atividade.registrar = lambda *a, **k: self.linhas.append((a, k))
        caso.addCleanup(setattr, atividade, "registrar", real)


class _Pasta:
    def __init__(self, caso):
        self._tmp = tempfile.TemporaryDirectory()
        caso.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)


def semana_cheia(com_leituras=True):
    """A semana do conferente (semana_cheia.py): 21 duelos no YouTube e 7 no
    TikTok de cada lado, 6 h antes do fim da semana."""
    sem = _semana()
    ini = sem["inicio"]
    agora = ini + timedelta(days=6, hours=23)
    titulo = "Throwing Axes VS Tactical Knives — who wins?"
    regs, k = [], 0
    for d in range(7):
        for h in (0.7, 8.9, 12.9):
            q = ini + timedelta(days=d, hours=h)
            regs.append(_reg(f"yt{k:09d}", q, 100, titulo=titulo, agora=agora))
            if h == 12.9:
                regs.append(_reg(f"tk{k:09d}", q + timedelta(minutes=1), 100, "tiktok",
                                 titulo=titulo, agora=agora))
            k += 1
    for d in range(-7, 0):
        for h in (0.7, 8.9, 12.9):
            q = ini + timedelta(days=d, hours=h)
            regs.append(_reg(f"yt{k:09d}", q, 100, titulo=titulo, agora=agora))
            regs.append(_reg(f"tk{k + 500:09d}", q, 100, "tiktok", titulo=titulo, agora=agora))
            k += 1
    leituras = []
    if com_leituras:
        t = ini
        while t < agora:
            vids = {r["id"]: 50 for r in regs if r["plataforma"] == "youtube"
                    and timedelta(0) <= t - datetime.fromisoformat(r["quando"])
                    <= timedelta(hours=48)}
            leituras.append(_leitura(t, vids))
            t += timedelta(hours=1)
    fotos = {}
    for d in range(-8, 7):
        dia = (ini + timedelta(days=d)).date().isoformat()
        hora = f"{dia}T07:20:00"
        fotos[dia] = {"quando_das_partes": {"builds": hora, "builds_tiktok": hora},
                      "builds": {r["id"]: [80, 1, 50.0, hora] for r in regs
                                 if r["plataforma"] == "youtube" and r["quando"] < hora},
                      "builds_tiktok": {r["id"]: [80, 1, 50.0, hora] for r in regs
                                        if r["plataforma"] == "tiktok" and r["quando"] < hora}}
    return mesma_idade.comparar(regs, agora, sem, fotos=fotos, leituras=leituras)


# ======================================================== 1. Telegram
class SemanaNoTelegramTests(unittest.TestCase):

    def test_semana_cheia_cabe_e_nao_perde_tiktok_nem_aviso(self):
        c = semana_cheia(com_leituras=False)        # -> "leitura de hora em hora PARADA"
        longo = mesma_idade.texto(c)
        curto = "📏 *Medida da semana*\n" + mesma_idade.texto(c, por_video=False)
        self.assertGreater(len(longo), 4000, "o caso tem de ser o que estourava")
        self.assertLessEqual(len(curto), 4000)
        linhas = curto.splitlines()
        self.assertTrue(any(l.startswith("TikTok:") for l in linhas))
        self.assertTrue(any(l.startswith("Leituras de hora em hora") for l in linhas))
        parada = next(i for i, l in enumerate(linhas) if "PARADA" in l)
        youtube = next(i for i, l in enumerate(linhas) if l.startswith("YouTube:"))
        self.assertLess(parada, youtube, "aviso no TOPO, antes de qualquer numero")
        self.assertNotIn("yt000000000", curto, "sem linha por video no Telegram")
        self.assertIn("Biblioteca", curto, "diz onde esta o detalhe")
        self.assertIn("yt000000000", longo, "a pagina e o --semana mantem o detalhe")

    def test_semana_cheia_com_leituras_tambem_cabe(self):
        curto = mesma_idade.texto(semana_cheia(), por_video=False)
        self.assertLessEqual(len(curto), 4000)

    def test_caso_zero_nao_manda_ver_detalhe_que_nao_existe(self):
        c = mesma_idade.comparar([], AGORA, SEMANA, fotos={}, leituras=[])
        curto = mesma_idade.texto(c, por_video=False)
        self.assertIn("NÃO há comparação", curto)
        self.assertNotIn("Vídeo a vídeo", curto)

    def test_texto_da_semana_e_o_curto(self):
        real = analise.medida_da_semana
        self.addCleanup(setattr, analise, "medida_da_semana", real)
        analise.medida_da_semana = lambda agora=None: {"texto": "LONGO", "texto_curto": "CURTO"}
        self.assertEqual("CURTO", analise.texto_da_semana(AGORA))
        self.assertEqual("LONGO", analise.texto_da_semana(AGORA, por_video=True))

    def test_falha_de_disco_vai_para_o_topo(self):
        reais = analise.carregar, analise.registros
        self.addCleanup(lambda: (setattr(analise, "carregar", reais[0]),
                                 setattr(analise, "registros", reais[1])))
        analise.carregar = lambda agora: {"semana": SEMANA, "fotos": {}, "leituras_hora": [],
                                          "horas_das_fotos": {}, "series": {},
                                          "erro_da_semana": "",
                                          "falhas": ["ledger de builds ilegível"]}
        novo = _reg("n", AGORA - timedelta(hours=6), 10)
        analise.registros = lambda entrada, meta=None: [novo]
        c = analise.medida_da_semana(AGORA)
        for texto in (c["texto"], c["texto_curto"]):
            linhas = texto.splitlines()
            falha = next(i for i, l in enumerate(linhas) if "ilegível" in l)
            youtube = next(i for i, l in enumerate(linhas) if l.startswith("YouTube:"))
            self.assertLess(falha, youtube)


# ======================================================== 3 e 4. TikTok
def _corpos_da_1a_coleta():
    """O que o Studio mandou na 1a coleta de verdade (escuta do conferente,
    21/10 13:38): 5 `data/insight`, so o 3o com a serie e so o 5o com os
    seguidores."""
    serie = [{"status": 0, "value": v} for v in
             (11, 15, 23, 10, 14, 722, 163, 16, 9, 18, 16, 13, 17, 12, 23)] + [{"status": 2}]
    vazio = {"vv_history": None, "follower_num_history": None, "status_code": 0}
    return [dict(vazio), dict(vazio), {**vazio, "vv_history": serie}, dict(vazio),
            {**vazio, "follower_num": {"status": 0, "value": 10}}]


def _pedido(tipos=None, url="https://www.tiktok.com/aweme/v2/data/insight/?locale=pt-BR"):
    if tipos is not None:
        from urllib.parse import quote
        url += "&type_requests=" + quote(json.dumps(tipos))
    return {"url": url, "ouvido_em": "2026-10-21T13:38:00"}


class SerieDaContaTests(unittest.TestCase):

    def test_serie_sem_data_guarda_o_corpo_que_a_trouxe_e_o_pedido(self):
        corpos = _corpos_da_1a_coleta()
        pedidos = [_pedido(url=f"https://www.tiktok.com/aweme/v2/data/insight/?n={i}")
                   for i in range(5)]
        ficha = T.ficha_da_conta("builds", punicoes=[], qualidades=[], insights=corpos,
                                 pedidos=pedidos, agora=AGORA)
        self.assertEqual(16, len(ficha["vv_history"]))
        self.assertTrue(ficha["vv_history_sem_datas"])
        self.assertEqual("sem", ficha["vv_history_datas"])
        self.assertEqual(10, ficha["seguidores"])
        guardados = ficha["insights_da_conta"]
        # a versao anterior guardava as 3 ULTIMAS — nenhuma com a serie
        self.assertEqual(2, len(guardados))
        self.assertTrue(guardados[0]["pedido"]["url"].endswith("n=2"))
        self.assertIsNotNone(guardados[0]["corpo"]["vv_history"])
        self.assertTrue(guardados[1]["pedido"]["url"].endswith("n=4"))
        self.assertEqual({"serie_pontos": 16, "serie_datas": "sem", "seguidores": 10,
                          "punicao": "nao_lida", "qualidade": "nao_lida"},
                         T.resumo_da_conta(ficha))

    def test_a_pagina_diz_serie_sem_datas_e_nao_16_dias(self):
        ficha = T.ficha_da_conta("builds", punicoes=[], qualidades=[],
                                 insights=_corpos_da_1a_coleta(), agora=AGORA)
        conta = analise.conta_tiktok({"builds": {"2026-10-21": ficha}}, [], AGORA)
        html = analise._conta_html(conta)
        self.assertIn("série sem datas (16 pontos", html)
        self.assertNotIn("16 dia(s)", html)
        self.assertTrue(any("SEM datas" in a for a in conta["avisos"]))

    def test_datas_so_quando_o_pedido_diz_o_intervalo(self):
        quando = datetime(2026, 10, 21, 13, 38)
        com_fim = T.datas_da_serie(16, _pedido([{"insigh_type": "vv_history", "days": 16,
                                                 "end_days": 1}]), quando)
        self.assertEqual("deduzidas", com_fim["origem"])
        self.assertEqual("2026-10-20", com_fim["datas"][-1])
        self.assertEqual("2026-10-05", com_fim["datas"][0])
        datado = T.datas_da_serie(3, _pedido([{"insight_type": "vv_history",
                                               "start_date": "2026-10-18",
                                               "end_date": "2026-10-20"}]), quando)
        self.assertEqual(("do_pedido", ["2026-10-18", "2026-10-19", "2026-10-20"]),
                         (datado["origem"], datado["datas"]))
        # `days` sem o fim: NAO deduz (errar o fim em 1 dia poe tudo no dia errado)
        so_dias = T.datas_da_serie(16, _pedido([{"insigh_type": "vv_history", "days": 16}]),
                                   quando)
        self.assertEqual(("sem", None), (so_dias["origem"], so_dias["datas"]))
        self.assertIn("days=16", so_dias["regra"])
        # intervalo que nao bate com o numero de pontos: nao deduz
        torto = T.datas_da_serie(15, _pedido([{"insigh_type": "vv_history", "days": 16,
                                               "end_days": 0}]), quando)
        self.assertEqual("sem", torto["origem"])
        # caso zero: sem pedido
        self.assertEqual("sem", T.datas_da_serie(16, None, quando)["origem"])

    def test_pedido_com_intervalo_poe_a_data_na_serie(self):
        corpos = _corpos_da_1a_coleta()
        pedidos = [None, None, _pedido([{"insigh_type": "vv_history", "days": 16,
                                         "end_days": 0}]), None, None]
        ficha = T.ficha_da_conta("builds", punicoes=[], qualidades=[], insights=corpos,
                                 pedidos=pedidos, agora=AGORA)
        self.assertEqual("deduzidas", ficha["vv_history_datas"])
        self.assertEqual(["2026-10-21", None], ficha["vv_history"][-1])
        self.assertFalse(ficha["vv_history_sem_datas"])

    def test_pedido_da_resposta_guarda_url_metodo_e_corpo(self):
        class _Req:
            method, post_data = "POST", '{"type_requests": [{"insigh_type": "vv_history"}]}'

        class _Resp:
            url, request = "https://x/aweme/v2/data/insight/?a=1", _Req()
        p = T.pedido_da_resposta(_Resp())
        self.assertEqual("POST", p["metodo"])
        self.assertIn("type_requests", p["corpo"])
        self.assertEqual([{"insigh_type": "vv_history"}], T._tipos_pedidos(p))

        class _SemRequest:
            url = "https://x/y"
        self.assertEqual("https://x/y", T.pedido_da_resposta(_SemRequest())["url"])


class _PaginaEmPingos:
    """Visao geral que manda as respostas uma a uma, a cada espera."""

    def __init__(self, fila, ouvidos):
        self.fila, self.ouvidos, self.esperas = list(fila), ouvidos, 0

    def goto(self, _url, **_k):
        self.ouvidos.append(self.fila.pop(0))

    def wait_for_timeout(self, _ms):
        self.esperas += 1
        if self.fila:
            self.ouvidos.append(self.fila.pop(0))


class VisaoGeralTests(unittest.TestCase):

    def test_espera_a_serie_e_os_seguidores_com_valor(self):
        ouvidos = []
        pagina = _PaginaEmPingos(_corpos_da_1a_coleta(), ouvidos)
        self.assertEqual("", T.visitar_a_visao_geral(pagina, ouvidos, espera=20))
        self.assertEqual(5, len(ouvidos), "a versao anterior saia na 1a (chave nula)")
        self.assertTrue(T.conta_completa(ouvidos))

    def test_caso_zero_espera_o_teto_e_nao_inventa(self):
        ouvidos = []
        pagina = _PaginaEmPingos([{"vv_history": None}], ouvidos)
        self.assertEqual("", T.visitar_a_visao_geral(pagina, ouvidos, espera=3))
        self.assertEqual(3, pagina.esperas)
        self.assertFalse(T.conta_completa(ouvidos))
        self.assertFalse(T.conta_completa([]))

    def test_sem_post_para_analisar_abre_o_mais_novo_para_ler_a_conta(self):
        pares = [({}, {"tiktok_id": "velho", "post_time": 10}),
                 ({}, {"tiktok_id": "novo", "post_time": 20})]
        self.assertEqual(({"novo"}, ""), T.garantir_uma_analise(set(), pares, analisar=True))
        self.assertEqual(({"x"}, ""), T.garantir_uma_analise({"x"}, pares, analisar=True))
        self.assertEqual((set(), ""), T.garantir_uma_analise(set(), pares, analisar=True,
                                                             ja_lida=True))
        nada, por_que = T.garantir_uma_analise(set(), pares, analisar=False)
        self.assertEqual(set(), nada)
        self.assertIn("análise de post desligada", por_que)
        nada, por_que = T.garantir_uma_analise(set(), [], analisar=True)
        self.assertIn("nenhum post", por_que)

    def test_punicao_nao_lida_diz_por_que(self):
        ficha = T.ficha_da_conta("builds", punicoes=[], qualidades=[], insights=[],
                                 agora=AGORA, por_que_sem_punicao="análise desligada")
        self.assertEqual({"lida": False, "por_que": "análise desligada"}, ficha["punicao"])
        conta = analise.conta_tiktok({"builds": {"2026-10-21": ficha}}, [], AGORA)
        self.assertTrue(any("análise desligada" in a for a in conta["avisos"]))
        self.assertIn("análise desligada", analise._conta_html(conta))


class _RespostaTk:
    def __init__(self, url, corpo):
        self.url, self._corpo = url, corpo

    def json(self):
        return self._corpo


class _Studio:
    """Studio de mentira: a punicao so chega na ANALISE de um post (como no
    de verdade); a visao geral manda a serie sem data."""

    def __init__(self, post_time):
        self.handlers, self.post_time, self.visitas = [], post_time, []
        self.url = "https://www.tiktok.com/tiktokstudio/content"

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
                                        "play_count": "9"}], "cursor": 1, "has_more": False})
        elif url == T.URL_VISAO_GERAL:
            for corpo in _corpos_da_1a_coleta():
                self._manda("https://x/aweme/v2/data/insight/?locale=pt-BR", corpo)
        elif url == T.URL_ANALISE.format(item_id="t1"):
            self._manda("https://x/aweme/v2/data/insight/?item=t1",
                        {"video_per_duration_realtime": {"status": 0, "value": 7}})
            self._manda("https://x/tiktok/creator/getPenaltyDetails/", {"penalty_type": 0})
            self._manda("https://x/tiktok/creator/quality_advisor/", {"status_code": 0})

    def evaluate(self, _js):
        pass

    def wait_for_timeout(self, _ms):
        pass

    def get_by_text(self, *_a, **_k):
        raise LookupError("sem abas no dublê")


class ColetaComAnaliseTests(unittest.TestCase):

    def setUp(self):
        from builds.identity import browser
        tmp = _Pasta(self).raiz
        reais = (browser.contexto_persistente, browser.pagina, metricas.publicados,
                 metricas.PASTA)

        def volta():
            (browser.contexto_persistente, browser.pagina, metricas.publicados,
             metricas.PASTA) = reais
        self.addCleanup(volta)
        self.post = 1789600000          # mais velho que 7 dias: ninguem "escolhido"
        self.pagina = _Studio(self.post)

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

    def test_sem_escolhido_abre_um_post_e_le_punicao_e_qualidade(self):
        resumo = {}
        T.coletar("builds", log=lambda *_a: None, analisar=True, resumo=resumo)
        self.assertIn(T.URL_ANALISE.format(item_id="t1"), self.pagina.visitas)
        self.assertEqual("lida", resumo["conta"]["punicao"])
        self.assertEqual("lida", resumo["conta"]["qualidade"])
        self.assertEqual(10, resumo["conta"]["seguidores"])
        self.assertEqual("sem", resumo["conta"]["serie_datas"])
        ficha = next(iter(T.carregar_contas("builds").values()))
        self.assertIn("data/insight", ficha["insights_da_conta"][0]["pedido"]["url"])

    def test_analise_desligada_diz_por_que_nao_leu(self):
        resumo = {}
        T.coletar("builds", log=lambda *_a: None, analisar=False, resumo=resumo)
        self.assertNotIn(T.URL_ANALISE.format(item_id="t1"), self.pagina.visitas)
        ficha = next(iter(T.carregar_contas("builds").values()))
        self.assertFalse(ficha["punicao"]["lida"])
        self.assertIn("desligada", ficha["punicao"]["por_que"])


# ======================================================== 5. aviso por tipo
class _RespostaApi:
    def __init__(self, status, corpo, url=metricas.API_VIDEOS):
        self.status_code, self._corpo, self.url = status, corpo, url
        self.ok = 200 <= status < 300
        self.text = json.dumps(corpo)

    def json(self):
        return self._corpo


def _recusa(status, razao, msg="detalhe"):
    return _RespostaApi(status, {"error": {"code": status, "message": msg,
                                           "errors": [{"reason": razao}]}})


class AvisoDeHoraEmHoraTests(unittest.TestCase):

    def setUp(self):
        self.pasta = _Pasta(self).raiz
        reais = hora_a_hora.PASTA, metricas._get, metricas._token
        hora_a_hora.PASTA = self.pasta / "_metricas_hora"

        def volta():
            hora_a_hora.PASTA, metricas._get, metricas._token = reais
        self.addCleanup(volta)
        self.resposta = None
        metricas._get = lambda *_a, **_k: self.resposta
        self.diario = _Diario(self)
        self.linhas = [{"youtube_id": "abc", "plataforma": "youtube", "publicado": True,
                        "url": "https://youtu.be/abc",
                        "quando": (AGORA - timedelta(hours=3)).isoformat(timespec="seconds")}]

    def _dispara(self, horas, **k):
        return hora_a_hora.disparo("builds", AGORA + timedelta(hours=horas),
                                   log=lambda *_a: None, linhas=self.linhas, **k)

    def test_cada_motivo_avisa_uma_vez_e_o_403_das_15h_nao_fica_calado(self):
        def sem_credencial(canal="builds"):
            raise RuntimeError("sem credencial")
        metricas._token = sem_credencial
        self._dispara(0)                                    # RuntimeError: avisa
        metricas._token = lambda canal="builds": ("tok", None)
        self.resposta = _recusa(403, "quotaExceeded", "quota")
        leitura = self._dispara(5)                          # 403 quotaExceeded: AVISA
        self.assertEqual("403 quotaExceeded", leitura["avisado"])
        self._dispara(6)                                    # o mesmo 403: calado
        self.resposta = _recusa(401, "authError")
        self._dispara(7)                                    # 401: avisa
        self.resposta = _RespostaApi(500, {"error": {"code": 500, "message": "x"}})
        self._dispara(8)                                    # 500: avisa
        textos = [a[2] for a, _k in self.diario.linhas]
        self.assertEqual(4, len(textos), textos)
        self.assertTrue(any("quotaExceeded" in t and "Data API" in t for t in textos))
        self.assertFalse(any("Analytics" in t for t in textos[1:]),
                         "videos.list e Data API, nunca 'Analytics'")

    def test_caso_zero_sem_video_novo_nao_avisa_nada(self):
        self.linhas = []
        self.assertEqual("vazio", self._dispara(0)["estado"])
        self.assertEqual([], self.diario.linhas)


class MotivoDaRecusaTests(unittest.TestCase):

    def test_rotula_pela_api_de_verdade(self):
        r = _recusa(403, "quotaExceeded")
        self.assertIn("YouTube Data API v3", metricas.motivo_da_recusa(r))       # pela URL
        self.assertIn("YouTube Analytics API", metricas.motivo_da_recusa(r, api="analytics"))
        r.url = ""
        self.assertIn("nao sei qual", metricas.motivo_da_recusa(r))
        desligada = _recusa(403, "accessNotConfigured")
        self.assertIn("youtube.googleapis.com", metricas.motivo_da_recusa(desligada))
        self.assertNotIn("youtubeanalytics", metricas.motivo_da_recusa(desligada))

    def test_tipo_e_codigo_e_motivo(self):
        self.assertEqual("403 quotaExceeded", metricas.tipo_da_recusa(_recusa(403, "quotaExceeded")))
        self.assertEqual("500", metricas.tipo_da_recusa(_RespostaApi(500, "<html>")))
        erro = metricas.RecusaDaAPI(_recusa(401, "authError"), api="data")
        self.assertIsInstance(erro, RuntimeError)
        self.assertEqual(("401 authError", "data"), (erro.tipo, erro.api))


# ======================================================== 6 e 7. a comparacao
class LeituraRuimTests(unittest.TestCase):

    def test_views_ilegivel_fica_de_fora_e_o_resto_segue(self):
        novo = _reg("n", AGORA - timedelta(hours=12), 50, medido=AGORA - timedelta(hours=6))
        outro = _reg("m", AGORA - timedelta(hours=12), 70, medido=AGORA - timedelta(hours=6))
        lei = [_leitura(AGORA - timedelta(hours=6), {"n": "muitas", "m": 33})]
        c = mesma_idade.comparar([novo, outro], AGORA, SEMANA, leituras=lei)
        self.assertNotEqual("erro", c["estado"])
        self.assertEqual(1, c["leituras_ruins"]["n"])
        self.assertTrue(any("ilegíveis" in a for a in c["avisos"]))
        seis = c["plataformas"]["youtube"]["idades"][0]
        self.assertEqual(2, seis["novos"]["n"], "o 'n' veio da coleta do dia; o 'm' das duas")

    def test_valores_ruins_conhecidos(self):
        for ruim in ("muitas", True, -3, float("nan"), 2.5, [], {}):
            self.assertIsNone(mesma_idade._views_validas(ruim), ruim)
        for bom, valor in ((0, 0), ("12", 12), (7.0, 7), (41, 41)):
            self.assertEqual(valor, mesma_idade._views_validas(bom))

    def test_foto_com_views_texto_conta_como_ruim_e_nao_derruba(self):
        fotos = {"2026-10-21": {"quando_das_partes": {"builds": "2026-10-21T07:20:00"},
                                "builds": {"n": ["x", 0, None, "2026-10-21T07:20:00"]}}}
        ruins = []
        obs, _sem = mesma_idade.observacoes([], fotos, [], ruins=ruins)
        self.assertEqual({}, obs)
        self.assertEqual(1, len(ruins))


class AindaJuntandoTests(unittest.TestCase):

    def test_19_h_sem_leitura_aos_24_e_ainda_juntando(self):
        # HyZJCselaKY: 19,1 h no ar, sem leitura perto de 24 h — a janela vai ate 29 h.
        novo = _reg("HyZJCselaKY", AGORA - timedelta(hours=19.1), 43,
                    medido=AGORA - timedelta(hours=3.2))
        c = mesma_idade.comparar([novo], AGORA, SEMANA)
        vinte_e_quatro = c["plataformas"]["youtube"]["idades"][2]
        self.assertEqual(24.0, vinte_e_quatro["idade_h"])
        self.assertEqual(1, vinte_e_quatro["novos"]["juntando"])
        self.assertEqual(0, vinte_e_quatro["novos"]["sem_leitura"])

    def test_janela_fechada_sem_leitura_e_sem_leitura(self):
        # 30 h no ar, a unica leitura e a de agora (aos 30 h: fora de 24 +- 5)
        agora = INICIO + timedelta(hours=31)
        novo = _reg("v", INICIO + timedelta(hours=1), 43, medido=agora, agora=agora)
        c = mesma_idade.comparar([novo], agora, SEMANA)
        self.assertEqual(1, c["plataformas"]["youtube"]["novos"])
        vinte_e_quatro = c["plataformas"]["youtube"]["idades"][2]
        self.assertEqual(0, vinte_e_quatro["novos"]["juntando"])
        self.assertEqual(1, vinte_e_quatro["novos"]["sem_leitura"])


# ======================================================== 8. titulo e pagina
class TituloEPaginaTests(unittest.TestCase):

    def test_titulo_cortado_nao_deixa_travessao_solto(self):
        for t in ("Throwing Axes VS Tactical Knives — who wins?",
                  "Heavy Crossbow VS Throwing Knives Extra —",
                  "Longsword VS Heavy Crossbow Bolts of Doom — who wins?"):
            curto = mesma_idade.titulo_curto(t)
            self.assertLessEqual(len(curto), mesma_idade.TITULO_CURTO + 1)
            self.assertFalse(curto.rstrip("…").endswith(("—", " ", "-")), curto)
        self.assertEqual("", mesma_idade.titulo_curto(None))
        self.assertNotIn("— —", mesma_idade.texto(semana_cheia()))

    def test_a_pagina_separa_youtube_e_tiktok(self):
        html = analise._semana_html(semana_cheia(com_leituras=False))
        self.assertEqual(2, html.count("semana-plataforma"))
        self.assertIn("<h3>YouTube: 21 novo(s)", html)
        self.assertIn("<h3>TikTok: 7 novo(s)", html)
        self.assertIn("class='sub video'", html)
        self.assertLess(html.index("PARADA"), html.index("<h3>YouTube"))

    def test_caso_zero_na_pagina(self):
        c = mesma_idade.comparar([], AGORA, SEMANA, fotos={}, leituras=[])
        html = analise._semana_html(c)
        self.assertIn("NÃO há comparação", html)
        self.assertEqual("", analise._semana_html({}))
        sem = mesma_idade.comparar([], AGORA, None)
        self.assertIn("não há comparação", analise._semana_html(sem))


if __name__ == "__main__":
    unittest.main()
