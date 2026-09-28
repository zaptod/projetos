# -*- coding: utf-8 -*-
"""Metricas do TikTok lidas do Studio (13/09/2026).

Metade das publicacoes do sistema nao tinha medicao nenhuma: o TikTok nao
devolve id ao publicar, e o ledger guardava so a frase de status. O Studio,
aberto com o login que ja publica, entrega a lista de posts com a hora exata
e a analise de cada video. Estes testes travam as partes que nao precisam
de navegador: o casamento com o ledger e a leitura dos numeros.
"""
from __future__ import annotations

import inspect
import unittest
from datetime import datetime

from builds.publicar import metricas
from builds.publicar import tiktok_metricas as T


def _quando(post_time: int, deslocamento: int = 0) -> str:
    """O `quando` do ledger: hora LOCAL sem fuso, como o postar grava."""
    return datetime.fromtimestamp(post_time + deslocamento).isoformat(
        timespec="seconds")


def _item(tid: str, post_time: int, legenda: str = "", views: int = 0) -> dict:
    return {"tiktok_id": tid, "post_time": post_time, "duracao_ms": 143081,
            "legenda": legenda, "views": views}


class CasamentoTests(unittest.TestCase):
    """O post vira video nosso pela HORA, e a legenda confirma a parte."""

    def test_casa_pela_hora_com_segundos_de_diferenca(self):
        """Medido: o Studio registra 1 a 7 s antes do `quando` do ledger."""
        itens = [_item("a", 1_789_000_000), _item("b", 1_789_010_000)]
        pub = {"quando": _quando(1_789_010_000, 3), "video_id": "x"}
        pares = T.casar([pub], itens)
        self.assertEqual(1, len(pares))
        self.assertEqual("b", pares[0][1]["tiktok_id"])

    def test_fora_da_janela_nao_casa(self):
        """Casar com o post errado grava numero de outro video — pior que nada."""
        itens = [_item("a", 1_789_000_000)]
        pub = {"quando": _quando(1_789_000_000, T.JANELA_DE_CASAMENTO_S + 60)}
        self.assertEqual([], T.casar([pub], itens))

    def test_duas_partes_no_mesmo_minuto_casam_pela_legenda(self):
        """O escoamento de 10/09 soltou seis partes em seis minutos.

        So a hora trocaria vizinhas; "Parte N de M" na legenda desempata.
        """
        base = 1_789_000_000
        itens = [_item("p1", base, "... Parte 1 de 6 ..."),
                 _item("p2", base + 40, "... Parte 2 de 6 ...")]
        # a linha da parte 2 ficou mais perto do post da parte 1
        pub = {"quando": _quando(base, 5), "parte": 2, "partes": 6}
        pares = T.casar([pub], itens)
        self.assertEqual("p2", pares[0][1]["tiktok_id"])

    def test_cada_post_casa_uma_vez_so(self):
        base = 1_789_000_000
        itens = [_item("unico", base)]
        pubs = [{"quando": _quando(base, 1)}, {"quando": _quando(base, 2)}]
        self.assertEqual(1, len(T.casar(pubs, itens)))

    def test_build_sem_marca_de_parte_casa_so_pela_hora(self):
        base = 1_789_000_000
        itens = [_item("duelo", base, "Ylva Brumalok x Pandora #shorts")]
        pub = {"quando": _quando(base, 2), "video_id": "duelo_00007"}
        self.assertEqual(1, len(T.casar([pub], itens)))


class LeituraDosNumerosTests(unittest.TestCase):

    def test_o_item_do_studio_vem_em_texto_e_vira_numero(self):
        """`play_count` chega como "79", string. Somar string nao soma."""
        item = T.item_do_studio({"item_id": 7684718911878728976,
                                 "post_time": "1789238110", "duration": 143081,
                                 "play_count": "79", "like_count": "2",
                                 "comment_count": "0", "share_count": "0",
                                 "favorite_count": "1", "desc": "legenda"})
        self.assertEqual("7684718911878728976", item["tiktok_id"])
        self.assertEqual(79, item["views"])
        self.assertEqual(1789238110, item["post_time"])
        self.assertEqual(1, item["salvos"])

    def test_sem_dado_nao_e_zero(self):
        """`status` diferente de zero e "o TikTok nao tem"; gravar 0 mentiria."""
        self.assertIsNone(T._valor({"status": 2, "value": None}))
        self.assertIsNone(T._valor({"status": 2}))
        self.assertEqual(8, T._valor({"status": 0, "value": 8}))
        self.assertEqual(16.65, T._valor(
            {"is_after_7d": False, "value": {"status": 0, "value": 16.65}}))

    def test_a_curva_fica_no_formato_da_do_youtube(self):
        """Pares (fracao do video, fracao assistindo), como a Analytics."""
        analise = T.analise_do_insight([{
            "video_retention_rate_realtime": {"value": {"status": 0, "list": [
                {"timestamp": "0", "value": 1},
                {"timestamp": "71540", "value": 0.2}]}}}], 143081)
        self.assertEqual([(0.0, 1.0), (0.5, 0.2)], analise["curva"])

    def test_media_e_conclusao_e_origem(self):
        analise = T.analise_do_insight([
            {"video_per_duration_realtime": {"value": {"status": 0,
                                                       "value": 14.3}}},
            {"video_finish_rate_realtime": {"value": {"status": 0,
                                                      "value": 0.0556}},
             "video_traffic_source_percent_realtime": {"value": {
                 "status": 0, "value": [{"key": "For You", "value": 0.934},
                                        {"key": "Search", "value": 0.005}]}}},
        ], 143000)
        self.assertEqual(14.3, analise["media_segundos"])
        self.assertEqual(10.0, analise["media_percentual"])
        self.assertEqual(0.0556, analise["taxa_de_conclusao"])
        self.assertEqual(0.934, analise["origem_do_trafego"]["For You"])

    def test_resposta_sem_analise_nao_inventa_campo(self):
        self.assertEqual({}, T.analise_do_insight(
            [{"video_rewards_data": {"status": 100}}], 143081))


class OrcamentoDaAnaliseTests(unittest.TestCase):
    """A analise custa 8,8 s por video e roda dentro da tarefa das 06:07."""

    AGORA = 1_789_300_000.0

    def _par(self, tid: str, dias_atras: float):
        item = _item(tid, int(self.AGORA - dias_atras * 86400))
        return ({"quando": _quando(item["post_time"])}, item)

    def test_video_velho_nao_ganha_pagina(self):
        pares = [self._par("novo", 1), self._par("velho", T.DIAS_DE_ANALISE + 2)]
        self.assertEqual({"novo"}, T.escolher_para_analise(
            pares, {}, agora=self.AGORA))

    def test_ja_analisado_hoje_nao_repete(self):
        hoje = datetime.fromtimestamp(self.AGORA).isoformat(timespec="seconds")
        pares = [self._par("a", 1)]
        anteriores = {"a": {"analisado_em": hoje}}
        self.assertEqual(set(), T.escolher_para_analise(
            pares, anteriores, agora=self.AGORA))

    def test_arquivo_antigo_sem_a_data_conta_pela_atualizacao(self):
        """Os primeiros arquivos nao tinham `analisado_em`."""
        hoje = datetime.fromtimestamp(self.AGORA).isoformat(timespec="seconds")
        anteriores = {"a": {"media_segundos": 4.5, "atualizado": hoje}}
        self.assertEqual(set(), T.escolher_para_analise(
            [self._par("a", 1)], anteriores, agora=self.AGORA))

    def test_nunca_analisado_passa_na_frente_dentro_do_teto(self):
        ontem = datetime.fromtimestamp(self.AGORA - 86400).isoformat()
        pares = [self._par("recente_ja_visto", 0.5),
                 self._par("recente_ja_visto_2", 0.6),
                 self._par("velho_nunca_visto", 5)]
        anteriores = {"recente_ja_visto": {"analisado_em": ontem},
                      "recente_ja_visto_2": {"analisado_em": ontem}}
        escolhidos = T.escolher_para_analise(pares, anteriores,
                                             agora=self.AGORA, maximo=2)
        self.assertEqual(2, len(escolhidos))
        self.assertIn("velho_nunca_visto", escolhidos)

    def test_quem_fica_de_fora_nao_perde_a_curva(self):
        """Regravar sem a analise apagava a curva ja coletada."""
        anterior = {"views": 90, "curva": [(0.0, 1.0), (0.5, 0.2)],
                    "media_segundos": 5.67, "atualizado": "2026-09-13T00:40:00"}
        guardada = T.analise_anterior(anterior)
        self.assertEqual(anterior["curva"], guardada["curva"])
        self.assertEqual(5.67, guardada["media_segundos"])
        self.assertNotIn("views", guardada)
        dado = T.montar({"quando": "2026-09-10T14:45:00"},
                        _item("x", 1_789_000_000, views=91), guardada,
                        "historias")
        self.assertEqual(anterior["curva"], dado["curva"])
        self.assertEqual(91, dado["views"])

    def test_o_teto_cabe_antes_do_proximo_horario(self):
        """2 canais x teto x 8,8 s medidos precisa caber longe da hora cheia."""
        pior_caso_min = 2 * T.MAXIMO_DE_ANALISES * 8.8 / 60
        self.assertLessEqual(pior_caso_min, 20)


class PastaPropriaTests(unittest.TestCase):

    def test_o_tiktok_nao_grava_junto_com_o_youtube(self):
        """Os experimentos indexam `_metricas/` por `youtube_id`.

        Um arquivo do TikTok ali dentro, sem esse campo, entraria nas medias
        do YouTube em silencio.
        """
        for canal in metricas.CANAIS:
            self.assertNotEqual(metricas.pasta_do_canal(canal),
                                T.pasta_do_canal(canal))
            self.assertEqual("_metricas_tiktok", T.pasta_do_canal(canal).name)


class AtualizacaoDiariaTests(unittest.TestCase):
    """O TikTok entra na atualizacao de todo dia sem poder derruba-la."""

    def setUp(self):
        self._orig = (metricas.reconciliar, metricas.atualizar, T.coletar)
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        metricas.reconciliar, metricas.atualizar, T.coletar = self._orig

    def test_o_tiktok_quebrado_nao_leva_o_youtube_junto(self):
        """Login caido no TikTok e comum; nao pode apagar a metrica do YouTube.

        E dubla `coletar`: ele abre navegador de verdade.
        """
        metricas.reconciliar = lambda canal, log=print: 0
        metricas.atualizar = lambda log=print, canal="builds": [{"ok": canal}]

        def quebra(canal, log=print, **_k):
            raise RuntimeError("o TikTok pediu login")
        T.coletar = quebra

        saida = metricas.atualizar_tudo(log=lambda *_a: None)
        for canal in metricas.CANAIS:
            self.assertEqual([{"ok": canal}], saida[canal])
            self.assertEqual([], saida[f"{canal}_tiktok"])

    def test_o_tiktok_e_chamado_para_os_dois_canais(self):
        chamados = []
        metricas.reconciliar = lambda canal, log=print: 0
        metricas.atualizar = lambda log=print, canal="builds": []
        T.coletar = lambda canal, log=print, **_k: chamados.append(canal) or []
        metricas.atualizar_tudo(log=lambda *_a: None)
        self.assertEqual(sorted(metricas.CANAIS), sorted(chamados))

    def test_coletar_abre_navegador_e_por_isso_avisa(self):
        """Quem ler a funcao precisa saber que teste nenhum pode chama-la crua."""
        self.assertIn("nunca chamar de teste sem dublar",
                      inspect.getdoc(T.coletar))


# ------------------------------------------------------ o Studio de mentira
BASE = 1_790_000_000   # um instante qualquer; os posts vao para tras dele


def _bruto(n: int) -> dict:
    """O item cru do `item_list`, do mais novo (n=0) para o mais velho."""
    return {"item_id": f"t{n:04d}", "post_time": str(BASE - n * 3600),
            "desc": f"post {n}", "duration": "60000", "play_count": "5"}


class _Resposta:
    def __init__(self, corpo):
        self.url = ("https://www.tiktok.com/tiktok/creator/manage/item_list/"
                    "v1/?locale=pt-BR")
        self._corpo = corpo

    def json(self):
        return self._corpo


class _Teclado:
    def __init__(self, pagina):
        self.pagina = pagina

    def press(self, tecla):
        self.pagina.teclas.append(tecla)
        if self.pagina.end_carrega and tecla == "End":
            self.pagina._proxima()


class _Mouse:
    def wheel(self, *_a):
        # O DEFEITO MEDIDO: a roda sem o ponteiro sobre a lista nao rola o
        # DIV dela, e nenhuma pagina nova e pedida.
        pass


class StudioDeMentira:
    """Pagina com `total` posts: 50 na primeira resposta, 10 nas seguintes.

    Cada rolagem do DIV (o `evaluate` do JS) pede a proxima pagina — e,
    como o Studio de verdade, pede a primeira de novo junto (cursor 0,
    `has_more=true`), o que nao pode apagar o fim da lista.
    """

    def __init__(self, total: int, *, end_carrega: bool = False):
        self.total, self.cursor = total, 0
        self.end_carrega = end_carrega
        self.handlers, self.teclas = [], []
        self.url = "https://www.tiktok.com/tiktokstudio/content"
        self.keyboard, self.mouse = _Teclado(self), _Mouse()

    def on(self, _evento, handler):
        self.handlers.append(handler)

    def _responder(self, inicio: int, tamanho: int):
        fim = min(self.total, inicio + tamanho)
        corpo = {"item_list": [_bruto(n) for n in range(inicio, fim)],
                 "cursor": fim, "has_more": fim < self.total,
                 "status_code": 0}
        for handler in self.handlers:
            handler(_Resposta(corpo))
        return fim

    def goto(self, *_a, **_k):
        self.cursor = self._responder(0, 50)

    def _proxima(self):
        self._responder(0, 50)          # a repeticao da primeira pagina
        if self.cursor < self.total:
            self.cursor = self._responder(self.cursor, 10)

    def evaluate(self, _js):
        self._proxima()

    def wait_for_timeout(self, _ms):
        pass


class AListaInteiraTests(unittest.TestCase):
    """De 17 a 28/09/2026 a lista parou em 50 ou 60 posts toda noite: 60 de
    119 envios casados em builds, 50 de 165 em historias."""

    def _ler(self, pagina, **kw):
        lista = T.Lista()
        pagina.on("response", lambda r: lista.receber(r.json()))
        pagina.goto()
        motivo = T.ler_a_lista(pagina, lista, pausa_ms=0, **kw)
        return lista, motivo

    def test_a_rolagem_antiga_parava_na_primeira_pagina(self):
        """O defeito, reproduzido: `mouse.wheel` nao pede pagina nova."""
        pagina = StudioDeMentira(165)
        lista = T.Lista()
        pagina.on("response", lambda r: lista.receber(r.json()))
        pagina.goto()
        parado = 0
        while parado < 3:                    # o laco que existia ate 28/09
            antes = len(lista.itens)
            pagina.mouse.wheel(0, 4000)
            parado = parado + 1 if len(lista.itens) == antes else 0
        self.assertEqual(50, len(lista.itens))
        self.assertTrue(lista.tem_mais)

    def test_le_ate_o_studio_dizer_que_acabou(self):
        lista, motivo = self._ler(StudioDeMentira(165))
        self.assertEqual(165, len(lista.itens))
        self.assertEqual("completa", motivo)
        self.assertIs(False, lista.tem_mais)

    def test_a_repeticao_da_primeira_pagina_nao_apaga_o_fim(self):
        # O Studio repede a primeira pagina a cada rolagem, com
        # `has_more=true`. Se a ultima resposta mandasse, a lista nunca
        # acabaria.
        lista = T.Lista()
        lista.receber({"item_list": [], "cursor": 172, "has_more": False})
        lista.receber({"item_list": [_bruto(0)], "cursor": 50,
                       "has_more": True})
        self.assertIs(False, lista.tem_mais)
        self.assertEqual(172, lista.fronteira)

    def test_para_quando_ja_cobre_o_envio_mais_velho(self):
        # So interessa o post que pode casar com o ledger: sem isto, uma
        # conta com mil posts antigos seguraria o perfil a noite inteira.
        antes_de = BASE - 70 * 3600
        lista, motivo = self._ler(StudioDeMentira(400),
                                  basta_antes_de=antes_de)
        self.assertEqual("suficiente", motivo)
        self.assertLessEqual(lista.mais_velho(), antes_de)
        self.assertLess(len(lista.itens), 400)

    def test_lista_que_empaca_diz_que_ficou_incompleta(self):
        # Se o Studio mudar e a rolagem parar de pedir pagina, o resultado
        # nao pode parecer lista inteira: e `parada`, com `has_more` ainda
        # verdadeiro.
        pagina = StudioDeMentira(165)
        pagina.evaluate = lambda _js: None
        lista, motivo = self._ler(pagina)
        self.assertEqual("parada", motivo)
        self.assertEqual(50, len(lista.itens))
        self.assertTrue(lista.tem_mais)

    def test_alterna_o_div_com_a_tecla_end(self):
        pagina = StudioDeMentira(165, end_carrega=True)
        pagina.evaluate = lambda _js: None
        lista, motivo = self._ler(pagina)
        self.assertEqual("completa", motivo)
        self.assertIn("End", pagina.teclas)


class ColetaQueNaoMedeTests(unittest.TestCase):
    """Lista vazia e zero casados sao FALHA, e nao "coleta com 0 videos".

    O navegador e dublado inteiro: nada aqui abre Chrome nem grava na pasta
    de verdade.
    """

    def setUp(self):
        import tempfile
        from pathlib import Path

        from builds.identity import browser
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        reais = (browser.contexto_persistente, browser.pagina,
                 metricas.publicados, metricas.PASTA)
        self.addCleanup(self._restaurar, reais)
        self.pagina = StudioDeMentira(0)
        pagina = self.pagina

        class _Contexto:
            def __enter__(self):
                return object()

            def __exit__(self, *_a):
                return False

        browser.contexto_persistente = lambda **_k: _Contexto()
        browser.pagina = lambda _ctx: pagina
        metricas.PASTA = Path(self._tmp.name) / "_metricas"
        self.envios = [{"plataforma": "tiktok",
                        "quando": _quando(BASE - 5 * 3600, 3),
                        "video_id": "g1"}]
        metricas.publicados = lambda canal="builds": self.envios

    @staticmethod
    def _restaurar(reais):
        from builds.identity import browser
        (browser.contexto_persistente, browser.pagina,
         metricas.publicados, metricas.PASTA) = reais

    def test_studio_sem_post_nenhum_e_falha(self):
        from builds.publicar.tiktok import TikTokFalhou
        espera = T.ESPERA_LISTA_S
        T.ESPERA_LISTA_S = 0.0
        self.addCleanup(lambda: setattr(T, "ESPERA_LISTA_S", espera))
        with self.assertRaises(TikTokFalhou) as erro:
            T.coletar("builds", log=lambda *_a: None, analisar=False)
        self.assertIn("nao carregou nenhum post", str(erro.exception))

    def test_nenhum_envio_casado_e_falha(self):
        from builds.publicar.tiktok import TikTokFalhou
        self.pagina.total = 30
        self.envios[0]["quando"] = _quando(BASE + 90 * 86400)
        with self.assertRaises(TikTokFalhou) as erro:
            T.coletar("builds", log=lambda *_a: None, analisar=False)
        self.assertIn("nenhum dos 1 envio", str(erro.exception))

    def test_o_resumo_diz_quantos_casaram_e_por_que_a_lista_parou(self):
        self.pagina.total = 30
        resumo = {}
        salvos = T.coletar("builds", log=lambda *_a: None, analisar=False,
                           resumo=resumo)
        self.assertEqual(1, len(salvos))
        self.assertEqual({"envios": 1, "posts": 30, "lista": "completa",
                          "casados": 1}, resumo)


if __name__ == "__main__":
    unittest.main()
