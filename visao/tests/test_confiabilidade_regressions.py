# -*- coding: utf-8 -*-
"""A familia de confiabilidade: o que foi afirmado e o que da para provar.

Tudo e injetado — ledgers, diario e conferencias. Nenhum caso toca disco de
verdade, rede ou subprocesso, e ha um caso que prova isso, porque esta
familia entra no pulso de 3 s do painel.
"""
import subprocess
import unittest

from panorama import confiabilidade as C

DIA = "2026-09-16"


def _yt(video_id, *, hora="09:40", prova_ok=True, qualidade="hd",
        reconhecido=True, url="https://youtu.be/x", laudo=True):
    linha = {"quando": f"{DIA}T{hora}:00", "plataforma": "youtube",
             "video_id": video_id, "titulo": video_id, "url": url}
    if laudo:
        linha["prova_ok"] = prova_ok
        linha["prova"] = [{"qualidade_no_clique": qualidade,
                           "reconhecido": reconhecido}]
    return linha


def _tk(video_id, *, hora="09:41", dia=DIA):
    return {"quando": f"{dia}T{hora}:00", "plataforma": "tiktok",
            "video_id": video_id, "titulo": video_id,
            "url": "publicado no TikTok", "prova_ok": True,
            "prova": [{"confirmado": True}]}


def _limpo():
    return {"veredito": "limpo", "dia": DIA, "casados": 1, "no_ledger": 1,
            "fantasmas": [], "rascunhos": [], "orfaos": [], "so_sd": []}


def _marca_boa(quando=f"{DIA}T01:20:00"):
    """A marca de uma noite em que as quatro partes da coleta deram certo."""
    partes = {nome: {"chave": "noite", "estado": "ok", "videos": 5,
                     "quando": quando, "ultimo_ok": quando,
                     "videos_no_ultimo_ok": 5}
              for nome in ("builds", "builds_tiktok", "historias",
                           "historias_tiktok")}
    return {"dia": "noite", "completa": True, "partes": partes}


def _retrato(builds=(), historias=(), eventos=(), conferencias=None,
             marca=None, agora=None):
    if conferencias is None:
        conferencias = {"builds": _limpo(), "historias": _limpo()}
    return C.hoje(DIA, builds=builds, historias=historias,
                  eventos=eventos, conferencias=conferencias,
                  marca=_marca_boa() if marca is None else marca,
                  agora=agora)


class OQueFoiAfirmado(unittest.TestCase):

    def test_dia_limpo_e_ok_sem_alerta(self):
        ficha = _retrato(builds=[_yt("g1"), _tk("g1")])
        self.assertEqual(ficha["veredito"], "ok")
        self.assertEqual(ficha["alertas"], [])
        self.assertEqual((ficha["prometido"], ficha["provado"]), (2, 2))

    def test_linha_antiga_e_nao_sei_e_nao_sem_prova(self):
        # O TERCEIRO ESTADO. Linha anterior ao laudo conta em `sem_campo` e
        # NAO em `sem_prova`: se ausencia valesse reprovacao, o alarme
        # acenderia para o acervo inteiro e ninguem o olharia de novo.
        ficha = _retrato(builds=[_yt("g1", laudo=False), _tk("g1")])
        self.assertEqual(ficha["sem_campo"], 1)
        self.assertEqual(ficha["sem_prova"], 0)

    def test_publicacao_sem_prova_acende(self):
        ficha = _retrato(builds=[_yt("g1", prova_ok=False), _tk("g1")])
        self.assertEqual(ficha["sem_prova"], 1)
        self.assertEqual(ficha["veredito"], "atencao")

    def test_outro_dia_nao_entra(self):
        ontem = _yt("g0")
        ontem["quando"] = "2026-09-15T23:40:00"
        ficha = _retrato(builds=[ontem, _tk("g0", dia="2026-09-15")])
        self.assertEqual(ficha["prometido"], 0)

    def test_linha_sem_url_nao_foi_ao_ar(self):
        ficha = _retrato(builds=[_yt("g1", url="")])
        self.assertEqual(ficha["prometido"], 0)


class AQualidadeNoClique(unittest.TestCase):

    def test_conta_quem_foi_ao_ar_antes_do_processamento(self):
        ficha = _retrato(builds=[
            _yt("g1", qualidade="processando"), _tk("g1"),
            _yt("g2", qualidade="subindo"), _tk("g2"),
            _yt("g3", qualidade="hd"), _tk("g3"),
            # "desconhecida" NAO e fora de HD: e "nao sei".
            _yt("g4", qualidade="desconhecida", reconhecido=False), _tk("g4"),
        ])
        self.assertEqual(ficha["fora_de_hd"], 2)

    def test_a_barra_que_ninguem_entendeu_vira_alerta(self):
        # O ALARME PROMETIDO NA ETAPA 1: se o Studio mudar o texto da barra,
        # a medida inteira vira palpite, e so este contador avisa.
        ficha = _retrato(builds=[
            _yt("g1", qualidade="desconhecida", reconhecido=False), _tk("g1")])
        self.assertEqual(ficha["barra_nao_entendida"], 1)
        self.assertTrue(any("barra do Studio" in a for a in ficha["alertas"]))

    def test_linha_sem_laudo_nao_conta_como_barra_nao_entendida(self):
        ficha = _retrato(builds=[_yt("g1", laudo=False), _tk("g1")])
        self.assertEqual(ficha["barra_nao_entendida"], 0)


class OEstadoGanhaDoEvento(unittest.TestCase):

    def test_video_num_destino_so_e_estado(self):
        # O que a outra sessao pediu: 14 de 59 partes estavam so no YouTube,
        # e isso nao aparecia em lugar nenhum.
        ficha = _retrato(historias=[_yt("h12:p4")])
        self.assertEqual(ficha["num_destino_so"]["historias"], ["h12:p4"])
        self.assertTrue(any("destino só" in a for a in ficha["alertas"]))

    def test_nos_dois_destinos_nao_entra(self):
        ficha = _retrato(historias=[_yt("h12:p4"), _tk("h12:p4")])
        self.assertEqual(ficha["num_destino_so"]["historias"], [])

    def test_fora_da_janela_nao_conta(self):
        # O acervo de antes do TikTok entrar na grade nao pode inflar isto.
        velho = _yt("h1:p1")
        velho["quando"] = "2026-08-01T10:00:00"
        ficha = _retrato(historias=[velho])
        self.assertEqual(ficha["num_destino_so"]["historias"], [])

    def test_falha_do_tiktok_e_contada_mas_nao_acende_sozinha(self):
        # Evento e ruido; o estado (destino so) e quem alarma.
        eventos = [{"ts": f"{DIA}T12:40:00", "fabrica": "publicacao",
                    "status": "erro",
                    "detalhe": "TikTok: o botão de publicar não ficou clicável"}]
        ficha = _retrato(builds=[_yt("g1"), _tk("g1")], eventos=eventos)
        self.assertEqual(ficha["falhas_tiktok"], 1)
        self.assertEqual(ficha["veredito"], "ok")


def _falha(detalhe, *, etapa=None, fabrica="publicacao", status="erro"):
    ev = {"ts": f"{DIA}T12:40:00", "fabrica": fabrica, "status": status,
          "detalhe": detalhe}
    if etapa is not None:
        ev["etapa"] = etapa
    return ev


class AsFalhasPorDestino(unittest.TestCase):
    """Por etapa quando o publicador grava; pelo nome enquanto nao grava."""

    def _falhas(self, *eventos):
        ficha = _retrato(builds=[_yt("g1"), _tk("g1")], eventos=eventos)
        return ficha["falhas_tiktok"], ficha["falhas_youtube"]

    def test_etapa_decide_o_destino(self):
        self.assertEqual((1, 1), self._falhas(
            _falha("TimeoutError: page.goto", etapa="publicar.tiktok"),
            _falha("TimeoutError: page.goto", etapa="publicar.youtube")))

    def test_erro_cru_do_navegador_so_e_contado_com_etapa(self):
        # O buraco do criterio antigo: um TimeoutError do Playwright nao tem
        # "tiktok" no texto e sumia da conta.
        self.assertEqual((0, 0), self._falhas(_falha("TimeoutError: x")))
        self.assertEqual((1, 0), self._falhas(
            _falha("TimeoutError: x", etapa="publicar.tiktok")))

    def test_com_etapa_o_texto_nao_manda_mais(self):
        # Julgado pela etapa, e so por ela: a mensagem do YouTube pode citar
        # o TikTok sem virar falha do TikTok.
        self.assertEqual((0, 1), self._falhas(_falha(
            "YouTubeWebFalhou: o TikTok ja saiu, o YouTube nao",
            etapa="publicar.youtube")))

    def test_sem_etapa_o_criterio_antigo_continua_contando(self):
        # TRANSICAO: ate o publicador gravar a etapa, zerar a contagem
        # esconderia exatamente as falhas que se quer ver.
        self.assertEqual((1, 0), self._falhas(
            _falha("TikTokFalhou: a legenda não entrou (falhou: X)")))
        self.assertEqual((0, 2), self._falhas(
            _falha("YouTubeWebFalhou: o Studio nao carregou"),
            _falha("LimiteDiarioDoYouTube: cota do dia")))

    def test_a_conferencia_nao_vira_falha_de_publicar(self):
        # Ela grava na MESMA fabrica, com "youtube" no texto. Casar por
        # substring contaria cada noite suja como uma publicacao falhada.
        self.assertEqual((0, 0), self._falhas(_falha(
            "conferencia builds/youtube: 1 no ledger sem video no canal")))

    def test_etapa_desconhecida_e_log_nao_contam(self):
        self.assertEqual((0, 0), self._falhas(
            _falha("TikTokFalhou: x", etapa="render"),
            _falha("TikTokFalhou: x", status="log"),
            _falha("TikTokFalhou: x", fabrica="estudio")))

    def test_evento_de_outro_dia_nao_conta(self):
        ontem = _falha("TikTokFalhou: x", etapa="publicar.tiktok")
        ontem["ts"] = "2026-09-15T12:40:00"
        self.assertEqual((0, 0), self._falhas(ontem))


class FalhasDeTesteFicamForaDaConta(unittest.TestCase):
    """16/09/2026: dois testes escreveram no diario de producao falhas do
    TikTok para "trava:build:celular", e elas contavam como falhas reais."""

    def _falha_com_ref(self, ref, destino="publicar.tiktok"):
        ev = _falha("TikTokFalhou: desisti", etapa=destino)
        ev["ref"] = ref
        ev["pid"] = 11624
        return ev

    def test_ref_de_duble_nao_conta_e_fica_registrada(self):
        ficha = _retrato(builds=[_yt("g1"), _tk("g1")], eventos=[
            self._falha_com_ref("trava:build:celular"),
            self._falha_com_ref("trava:build:celular")])
        self.assertEqual(0, ficha["falhas_tiktok"])
        self.assertEqual(2, len(ficha["falhas_ignoradas"]))
        self.assertEqual("trava:build:celular",
                         ficha["falhas_ignoradas"][0]["ref"])
        self.assertEqual(11624, ficha["falhas_ignoradas"][0]["pid"])

    def test_ids_de_verdade_continuam_contando(self):
        # Os formatos de id que o projeto usa hoje. Canal novo com outro
        # formato precisa entrar em ID_DE_VIDEO, senao as falhas dele somem.
        refs = ["generation_00081:build:celular:B",
                "historia_00012:celular:p02",
                "duelo_00001:celular", "tournament_00003:celular"]
        ficha = _retrato(builds=[_yt("g1"), _tk("g1")],
                         eventos=[self._falha_com_ref(r) for r in refs])
        self.assertEqual(4, ficha["falhas_tiktok"])
        self.assertEqual([], ficha["falhas_ignoradas"])

    def test_falha_sem_ref_continua_contando(self):
        # A maior parte do diario antigo nao tem ref; descarta-la apagaria
        # falha verdadeira.
        ficha = _retrato(builds=[_yt("g1"), _tk("g1")],
                         eventos=[_falha("TikTokFalhou: x",
                                         etapa="publicar.tiktok")])
        self.assertEqual(1, ficha["falhas_tiktok"])
        self.assertEqual([], ficha["falhas_ignoradas"])


class AValvula(unittest.TestCase):

    def test_cada_abertura_aparece_com_o_motivo(self):
        eventos = [{"ts": f"{DIA}T12:10:00", "fabrica": "publicacao",
                    "status": "log", "canal": "builds", "etapa": "valvula",
                    "ref": "g1:build:celular:B|titulo_repetido",
                    "detalhe": "titulo ja publicado"}]
        ficha = _retrato(builds=[_yt("g1"), _tk("g1")], eventos=eventos)
        self.assertEqual(len(ficha["valvula"]), 1)
        self.assertEqual(ficha["valvula"][0]["marca"], "titulo_repetido")
        self.assertEqual(ficha["valvula"][0]["alvo"], "g1:build:celular:B")
        self.assertEqual(ficha["veredito"], "atencao")


class AConferencia(unittest.TestCase):

    def test_sujo_acende(self):
        sujo = dict(_limpo(), veredito="sujo", rascunhos=[{}, {}])
        ficha = _retrato(conferencias={"builds": sujo,
                                       "historias": _limpo()})
        self.assertTrue(any("2 rascunho" in a for a in ficha["alertas"]))

    def test_suja_so_por_privado_fora_do_ledger_diz_isso(self):
        # Sem isto o alerta dizia "0 fantasma(s), 0 rascunho(s)" para uma
        # conferencia suja — e ninguem saberia o que olhar.
        sujo = dict(_limpo(), veredito="sujo",
                    orfaos_privados=[{}, {}, {}])
        ficha = _retrato(conferencias={"builds": sujo,
                                       "historias": _limpo()})
        (alerta,) = [a for a in ficha["alertas"] if "builds" in a]
        self.assertIn("3 privado(s) fora do ledger", alerta)
        self.assertNotIn("0 fantasma", alerta)

    def test_falha_de_oauth_aparece_em_vez_de_passar_por_limpa(self):
        # O caso REAL de 16/09/2026: os tres tokens revogados. Uma
        # conferencia que nao rodou nao pode aparecer como "tudo certo".
        ficha = _retrato(conferencias={
            "builds": {"canal": "builds", "erro": "token invalido"},
            "historias": _limpo()})
        self.assertEqual(ficha["conferencia"]["builds"]["estado"], "falhou")
        self.assertTrue(any("não rodou" in a for a in ficha["alertas"]))

    def test_nunca_rodou_e_alerta(self):
        ficha = _retrato(conferencias={"builds": {}, "historias": _limpo()})
        self.assertTrue(any("nunca rodou" in a for a in ficha["alertas"]))

    def test_conferencia_parada_ha_dias_e_alerta(self):
        velha = dict(_limpo(), dia="2026-09-10")
        ficha = _retrato(conferencias={"builds": velha,
                                       "historias": _limpo()})
        self.assertTrue(any("parada desde" in a for a in ficha["alertas"]))

    def test_uma_noite_so_sem_conferencia_ja_acende(self):
        # A noite de 21/09/2026 faltou e a regra antiga (mais de dois dias)
        # nunca teria dito nada: a ficha de 20/09 tinha um dia de idade.
        ontem = dict(_limpo(), dia="2026-09-15")
        ficha = _retrato(conferencias={"builds": ontem,
                                       "historias": _limpo()})
        (alerta,) = [a for a in ficha["alertas"] if "builds" in a]
        self.assertIn("a noite de 16/09 não rodou", alerta)

    def test_a_noite_nao_e_cobrada_antes_de_acabar(self):
        # As 03:00 a noite de hoje ainda esta rodando: a ficha de ontem basta.
        ontem = dict(_limpo(), dia="2026-09-15")
        ficha = _retrato(conferencias={"builds": ontem,
                                       "historias": dict(_limpo(),
                                                         dia="2026-09-15")},
                         agora=C.datetime(2026, 9, 16, 3, 0))
        self.assertFalse(any("não rodou" in a for a in ficha["alertas"]))


class AGradeNaPagina(unittest.TestCase):
    """Ate 28/09/2026 a pagina mostrava "✓ 5/5" para um canal que cumpriu 5
    de 10 horarios: so o veredito do ledger entrava no resumo."""

    def _em_falta(self):
        return dict(_limpo(), grade="em falta", dia_de_grade="2026-09-15",
                    horarios_cumpridos=5, slots_da_grade=10,
                    horarios_em_falta=["21:37", "22:37", "23:37", "00:37",
                                       "20:37"])

    def test_grade_em_falta_com_ledger_limpo_acende(self):
        ficha = _retrato(conferencias={"builds": self._em_falta(),
                                       "historias": _limpo()})
        (alerta,) = [a for a in ficha["alertas"] if "grade de builds" in a]
        self.assertIn("5 de 10 horários", alerta)
        self.assertIn("15/09", alerta)
        self.assertIn("00:37", alerta)
        self.assertEqual("atencao", ficha["veredito"])
        self.assertEqual("em falta", ficha["conferencia"]["builds"]["grade"])

    def test_grade_cumprida_nao_acende(self):
        cumprida = dict(self._em_falta(), grade="cumprida",
                        horarios_cumpridos=10, horarios_em_falta=[])
        ficha = _retrato(conferencias={"builds": cumprida,
                                       "historias": _limpo()})
        self.assertEqual([], ficha["alertas"])


class OsSinaisDeAusencia(unittest.TestCase):

    def test_canal_sem_evento_no_diario_acende(self):
        # 25 e 26/09/2026: builds com zero eventos, historias com centenas.
        agora = C.datetime(2026, 9, 16, 22, 30)
        eventos = [{"ts": (agora - C.timedelta(hours=h)).astimezone()
                    .isoformat(), "canal": "historias", "fabrica": "estudio",
                    "status": "ok"} for h in range(0, 30)]
        ficha = _retrato(eventos=eventos, agora=agora)
        self.assertTrue(any(a.startswith("builds: 0 evento(s)")
                            for a in ficha["alertas"]))
        self.assertFalse(any(a.startswith("historias:")
                             for a in ficha["alertas"]))

    def test_diario_vazio_nao_inventa_canal_parado(self):
        ficha = _retrato(eventos=())
        self.assertFalse(any("evento(s) de trabalho" in a
                             for a in ficha["alertas"]))

    def test_linhas_recentes_sem_id_acendem(self):
        velho = [dict(_yt(f"g{n}"), quando="2026-09-13T09:40:00",
                      youtube_id="") for n in range(5)]
        ficha = _retrato(builds=velho)
        self.assertTrue(any("têm youtube_id" in a for a in ficha["alertas"]))


class AMetricaVelha(unittest.TestCase):
    """Onze noites sem metrica do YouTube (17 a 28/09/2026) e a pagina lia o
    disco velho sem avisar."""

    def test_marca_boa_nao_acende(self):
        self.assertEqual([], _retrato()["alertas"])

    def test_coleta_que_falhou_esta_noite_acende(self):
        marca = _marca_boa()
        marca["partes"]["builds"].update(
            estado="erro", erro="ConnectionError: SSLEOFError")
        ficha = _retrato(marca=marca)
        (alerta,) = [a for a in ficha["alertas"] if "métrica" in a]
        self.assertIn("do YouTube de builds", alerta)
        self.assertIn("SSLEOFError", alerta)

    def test_ultima_coleta_boa_antiga_e_velha(self):
        marca = _marca_boa()
        marca["partes"]["historias"]["ultimo_ok"] = "2026-09-14T01:20:00"
        ficha = _retrato(marca=marca)
        (alerta,) = [a for a in ficha["alertas"] if "métrica" in a]
        self.assertIn("velha", alerta)
        self.assertIn("14/09", alerta)

    def test_nunca_coletou_e_alerta_e_nao_silencio(self):
        # CASO ZERO: sem marca nenhuma no disco.
        ficha = _retrato(marca={})
        self.assertEqual(4, sum("nenhuma coleta boa" in a
                                for a in ficha["alertas"]))

    def test_marca_ilegivel_aparece(self):
        # Arquivo que nao abre nao some: vira alerta proprio.
        real = C._marca_das_metricas
        C._marca_das_metricas = lambda: None
        self.addCleanup(lambda: setattr(C, "_marca_das_metricas", real))
        ficha = C.hoje(DIA, builds=(), historias=(), eventos=(),
                       conferencias={"builds": _limpo(),
                                     "historias": _limpo()},
                       agora=C.datetime(2026, 9, 16, 22, 30))
        self.assertTrue(any("não consegui ler a marca" in a
                            for a in ficha["alertas"]))

    def test_lista_incompleta_do_studio_acende(self):
        marca = _marca_boa()
        marca["partes"]["builds_tiktok"].update(lista="parada", casados=60,
                                                envios=119)
        ficha = _retrato(marca=marca)
        self.assertTrue(any("60 de 119" in a for a in ficha["alertas"]))


class ARegraDaCasa(unittest.TestCase):

    def test_nao_abre_subprocesso(self):
        # O pulso do painel e de 3 s. Um ffprobe aqui travaria a tela.
        chamados = []
        reais = (subprocess.run, subprocess.Popen)
        subprocess.run = lambda *a, **k: chamados.append(a)
        subprocess.Popen = lambda *a, **k: chamados.append(a)
        self.addCleanup(lambda: setattr(subprocess, "run", reais[0]))
        self.addCleanup(lambda: setattr(subprocess, "Popen", reais[1]))
        _retrato(builds=[_yt("g1"), _tk("g1")])
        self.assertEqual(chamados, [])

    def test_entrada_torta_nao_levanta(self):
        ficha = C.hoje(DIA, builds=[None, "x", {}], historias=[{"url": "y"}],
                       eventos=[None, 3, {}], conferencias={"builds": None},
                       marca={"partes": {"builds": "torto"}, "videos": 3})
        self.assertIn("veredito", ficha)

    def test_esta_no_resumo_do_panorama(self):
        import panorama
        self.assertIn("confiabilidade", panorama.resumo(forcar=True))


if __name__ == "__main__":
    unittest.main()
