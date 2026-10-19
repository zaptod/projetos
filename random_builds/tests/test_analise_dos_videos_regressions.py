# -*- coding: utf-8 -*-
"""A pagina "Analise dos videos" nao pode dar nota boa para maquina parada.

19/10/2026, pedido do Adrian: "quero poder ver onde estou acertando,
errando, o que mudar". A analise (`builds.publicar.analise`) le a coleta da
manha e escreve achados com recomendacao. Os tres jeitos de ela mentir, e o
teste de cada um:

- CASO ZERO: sem video nenhum, a pagina diz "Sem dados" em vermelho; nunca
  "coleta completa", nunca achado. Ledger com video e sem numero acende.
- AMOSTRA PEQUENA: diferenca com poucos videos vai para "ainda nao da para
  dizer", nao vira recomendacao.
- EXCECAO: o que falha (serie do canal, Biblioteca) vira linha de erro no
  diario, nao silencio.

E os achados medidos em 19/10 nos dados reais, reproduzidos com dados
sinteticos para travar a conta: o TikTok que so entrega os 6 primeiros
posts depois de uma pausa de 10 h, o duelo contra a estreia, o dia decidido
por um video so, e a parte seguinte que ninguem ve.

Nada aqui toca rede, navegador, o diario ou as pastas de verdade.
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from builds import atividade, grade
from builds.publicar import analise

AGORA = datetime(2026, 10, 19, 9, 0)


def yt(id_, quando, views, formato="duelo", canal="builds", ret=None, dur=20,
       priv="public", **extra):
    d = {"youtube_id": id_, "quando": quando.isoformat(timespec="seconds"),
         "views": views, "origem": formato, "duracao": dur, "privacidade": priv,
         "titulo": f"video {id_}", "video_id": f"{id_}:{formato}:celular",
         "fonte_id": extra.pop("fonte_id", id_)}
    if ret is not None:
        d["media_percentual"] = ret
    d.update(extra)
    return analise.registro(d, canal, "youtube", AGORA)


def tk(id_, quando, views, canal="builds", formato="duelo"):
    d = {"tiktok_id": id_, "post_time": int(quando.timestamp()), "views": views,
         "origem": formato, "duracao": 20, "titulo": f"tk {id_}",
         "video_id": f"{id_}:{formato}:celular", "fonte_id": id_}
    return analise.registro(d, canal, "tiktok", AGORA)


def entrada_vazia(**muda):
    base = {"agora": AGORA, "salvas": {}, "ledger": {}, "marca": None,
            "falhas": [], "series": {}, "historico": {}}
    base.update(muda)
    return base


MARCA_BOA = {"completa": True, "partes": {
    nome: {"estado": "ok", "ultimo_ok": "2026-10-19T07:30:00", "chave": "dia-2026-10-19"}
    for nome in ("builds", "builds_tiktok", "historias", "historias_tiktok")}}


class CasoZeroTests(unittest.TestCase):

    def test_sem_video_nenhum_nao_e_nota_boa(self):
        cob = analise.cobertura(entrada_vazia(marca=MARCA_BOA))
        a = analise.analisar([], cob, AGORA)
        self.assertEqual("sem_dados", a["estado"])
        self.assertEqual([], a["achados"])
        self.assertIn("Nenhum vídeo", a["avisos"][0])
        pagina = analise.pagina(a)
        self.assertIn("Sem dados", pagina)
        self.assertIn("não quer dizer que está tudo bem", pagina)
        self.assertNotIn("Coleta de hoje completa", pagina)

    def test_parte_sem_video_e_falta_de_dado_nao_zero_views(self):
        a = analise.analisar([], analise.cobertura(entrada_vazia(marca=MARCA_BOA)), AGORA)
        pagina = analise.pagina(a)
        self.assertIn("Isso não é zero views: é falta de dado", pagina)

    def test_ledger_com_videos_e_nenhum_numero_acende(self):
        linhas = [{"plataforma": "youtube", "youtube_id": f"id{i}", "url": "x",
                   "quando": "2026-10-10T12:07:00"} for i in range(3)]
        cob = analise.cobertura(entrada_vazia(marca=MARCA_BOA,
                                              ledger={"builds": linhas}))
        parte = cob["partes"]["builds"]
        self.assertEqual((3, 0, 3), (parte["linhas_no_ledger"], parte["medidos"],
                                     parte["sem_arquivo"]))
        a = analise.analisar([], cob, AGORA)
        self.assertTrue(any("NENHUM com número" in x for x in a["avisos"]), a["avisos"])

    def test_video_postado_depois_da_coleta_nao_e_buraco(self):
        linhas = [{"plataforma": "youtube", "youtube_id": "velho", "url": "x",
                   "quando": "2026-10-18T21:37:00"},
                  {"plataforma": "youtube", "youtube_id": "novo", "url": "x",
                   "quando": "2026-10-19T09:37:00"}]
        cob = analise.cobertura(entrada_vazia(marca=MARCA_BOA, ledger={"builds": linhas}))
        parte = cob["partes"]["builds"]
        self.assertEqual((1, 1), (parte["sem_arquivo"], parte["depois_da_coleta"]))

    def test_coleta_sem_marca_e_velha_mesmo_com_numero(self):
        d = {"youtube_id": "a", "quando": "2026-10-10T12:07:00", "views": 50,
             "privacidade": "public", "atualizado": "2026-10-10T07:00:00"}
        cob = analise.cobertura(entrada_vazia(salvas={("builds", "youtube"): [d]}))
        self.assertEqual("velha", cob["estado"])
        self.assertTrue(cob["partes_que_nunca_coletaram"])

    def test_coleta_com_erro_e_incompleta(self):
        marca = json.loads(json.dumps(MARCA_BOA))
        marca["partes"]["historias"]["estado"] = "erro"
        d = {"youtube_id": "a", "quando": "2026-10-10T12:07:00", "views": 50,
             "privacidade": "public"}
        cob = analise.cobertura(entrada_vazia(marca=marca,
                                              salvas={("builds", "youtube"): [d]}))
        self.assertEqual("incompleta", cob["estado"])

    def test_do_dia_vazio_grava_a_pagina_e_avisa_no_diario(self):
        pasta = Path(tempfile.mkdtemp(prefix="analise-"))
        linhas = []
        originais = (analise.PASTA, analise.carregar, atividade.registrar)
        self.addCleanup(lambda: (setattr(analise, "PASTA", originais[0]),
                                 setattr(analise, "carregar", originais[1]),
                                 setattr(atividade, "registrar", originais[2])))
        analise.PASTA = pasta
        analise.carregar = lambda agora=None: entrada_vazia(marca=MARCA_BOA)
        atividade.registrar = lambda *a, **k: linhas.append(a)
        a = analise.do_dia(log=lambda *_: None, agora=AGORA, rede=False, biblioteca=False)
        self.assertEqual("sem_dados", a["estado"])
        gravada = json.loads((pasta / "analise.json").read_text(encoding="utf-8"))
        self.assertEqual("sem_dados", gravada["estado"])
        self.assertIn("Sem dados", (pasta / "index.html").read_text(encoding="utf-8"))
        self.assertTrue((pasta / "historico" / "2026-10-19.json").is_file())
        self.assertEqual(1, len(linhas))
        self.assertEqual(("metricas", atividade.ERRO), linhas[0][:2])
        self.assertTrue(linhas[0][2].startswith("[analise]"))

    def test_falha_da_serie_e_da_biblioteca_vira_aviso(self):
        pasta = Path(tempfile.mkdtemp(prefix="analise-"))
        linhas = []
        originais = (analise.PASTA, analise.carregar, atividade.registrar,
                     analise.buscar_serie_do_canal, analise.publicar_na_biblioteca)
        self.addCleanup(lambda: (setattr(analise, "PASTA", originais[0]),
                                 setattr(analise, "carregar", originais[1]),
                                 setattr(atividade, "registrar", originais[2]),
                                 setattr(analise, "buscar_serie_do_canal", originais[3]),
                                 setattr(analise, "publicar_na_biblioteca", originais[4])))
        analise.PASTA = pasta
        regs_d = {"youtube_id": "a", "quando": "2026-10-10T12:07:00", "views": 50,
                  "privacidade": "public", "origem": "duelo"}
        analise.carregar = lambda agora=None: entrada_vazia(
            marca=MARCA_BOA, salvas={("builds", "youtube"): [regs_d]})
        atividade.registrar = lambda *a, **k: linhas.append(a)

        def _cai(*a, **k):
            raise RuntimeError("sem rede")
        analise.buscar_serie_do_canal = _cai
        analise.publicar_na_biblioteca = _cai
        a = analise.do_dia(log=lambda *_: None, agora=AGORA, rede=True, biblioteca=True)
        self.assertTrue(any("série diária do canal builds" in x for x in a["avisos"]))
        self.assertEqual(1, len(linhas))
        self.assertIn("série diária", linhas[0][2])
        self.assertIn("Biblioteca", linhas[0][2])

    def test_main_sai_com_1_sem_dados(self):
        original = analise.carregar
        self.addCleanup(setattr, analise, "carregar", original)
        analise.carregar = lambda agora=None: entrada_vazia()
        self.assertEqual(1, analise.main(["--ver"]))


class EstatisticaTests(unittest.TestCase):

    def test_sem_amostra_nada_esta_provado(self):
        self.assertEqual(1.0, analise.p_valor([], [1, 2]))
        self.assertEqual(1.0, analise.p_valor([3] * 10, [3] * 10))
        self.assertEqual("incerto", analise.confianca([1, 2, 3], [100, 200, 300]))

    def test_diferenca_grande_com_amostra_e_clara(self):
        self.assertEqual("claro", analise.confianca(list(range(100, 112)),
                                                    list(range(0, 12))))

    def test_mediana(self):
        self.assertIsNone(analise.mediana([]))
        self.assertEqual(2.5, analise.mediana([1, 2, 3, 4]))
        self.assertEqual(3.0, analise.mediana([1, 3, 12572]))


class RegistroTests(unittest.TestCase):

    def test_retencao_com_poucas_views_nao_conta(self):
        self.assertIsNone(yt("a", AGORA - timedelta(days=5), 5, ret=80.0)["retencao"])
        self.assertEqual(80.0, yt("b", AGORA - timedelta(days=5), 50, ret=80.0)["retencao"])

    def test_rascunho_e_video_sem_status_nao_sao_amostra(self):
        q = AGORA - timedelta(days=5)
        regs = [yt("a", q, 10), yt("b", q, 10, priv="private"), yt("c", q, 10, priv=None)]
        self.assertEqual(["a"], [r["id"] for r in analise._na_janela(regs, AGORA)])

    def test_video_de_ontem_nao_entra_na_comparacao(self):
        regs = [yt("a", AGORA - timedelta(days=1), 10)]
        self.assertEqual([], analise._na_janela(regs, AGORA))

    def test_hora_do_tiktok_vem_do_post_time_local(self):
        r = tk("t", datetime(2026, 10, 10, 21, 37), 5)
        self.assertEqual((21, 5), (r["hora"], r["dia_semana"]))   # 10/10/2026: sabado


def _blocos_do_tiktok(canal="builds", rodadas=6, views_descansado=100, views_cansado=1,
                     inicio=None):
    """Cada rodada: 3 posts depois de 23 h sem postar (descansado) e 3 posts
    6 h depois (a pausa da madrugada da grade de 10)."""
    regs = []
    q = inicio or (AGORA - timedelta(days=rodadas * 2 + 6))
    for d in range(rodadas):
        for i in range(3):
            regs.append(tk(f"{canal}{d}a{i}", q + timedelta(hours=i), views_descansado, canal))
        q2 = q + timedelta(hours=2 + 6)
        for i in range(3):
            regs.append(tk(f"{canal}{d}b{i}", q2 + timedelta(hours=i), views_cansado, canal))
        q = q2 + timedelta(hours=2 + 23)
    return regs


class PausaDoTikTokTests(unittest.TestCase):

    def test_por_bloco_e_por_faixa_fixa_de_pausa(self):
        a, _ = analise.achado_pausa_tiktok(_blocos_do_tiktok(), AGORA, "builds")
        self.assertIsNotNone(a)
        faixas = {f["faixa"]: (f["deram_certo"], f["blocos"]) for f in a["numeros"]["faixas"]}
        self.assertEqual((5, 5), faixas["22 h ou mais"])      # o 1o bloco nao tem pausa antes
        self.assertEqual((0, 6), faixas["5 a 10 h"])
        # A unidade e o BLOCO (~10), nao o post: nunca "clara".
        self.assertEqual("provavel", a["confianca"])
        self.assertIn("Testar por 1 semana", a["mudar"])
        self.assertNotIn("sem nenhuma pausa longa", a["vimos"])
        self.assertNotIn("corte", a["numeros"])

    def test_a_pausa_e_medida_em_segundos_nao_no_minuto(self):
        # 14 -> 15/09/2026, TikTok de builds: 20:09:00 -> 06:08:52 = 9,9978 h.
        # Cortado no minuto virava 10 h e abria um bloco "de 10 a 16 h".
        a = tk("a", datetime(2026, 9, 14, 20, 9, 0), 5)
        b = tk("b", datetime(2026, 9, 15, 6, 8, 52), 5)
        self.assertEqual("2026-09-15T06:08:52", b["quando"])
        blocos = analise.blocos_do_tiktok([a, b])
        self.assertLess(blocos[1]["pausa"], 10.0)
        self.assertEqual("5 a 10 h", analise._faixa(blocos[1]["pausa"]))

    def test_projecao_sai_so_dos_dias_de_6_e_nao_se_sobrepoe_aos_de_9(self):
        # Medido pelo conferente em 19/10: TikTok de builds de 11 a 15/09 teve
        # 8, 4, 6, 6, 9 posts por dia. O regime de 6 por dia (grade.py) foi de
        # 13/09 ate a grade de 10 em 15/09: so 13 e 14/09 (331 e 581 views).
        # O "piso" de 18 (11/09, 8 posts) e os 12.821 (15/09, 9 posts) saem, e o
        # 15/09 conta so nos "9 ou mais".
        regs = _blocos_do_tiktok()
        for dia, n, total in ((11, 8, 18), (12, 4, 331), (13, 6, 331), (14, 6, 581),
                              (15, 9, 12821)):
            for i in range(n):
                regs.append(tk(f"s{dia}-{i}", datetime(2026, 9, dia, 6, 5) + timedelta(hours=2 * i),
                               total - (n - 1) if i == 0 else 1))
        a, _ = analise.achado_pausa_tiktok(regs, AGORA, "builds")
        self.assertEqual(["2026-09-13", "2026-09-14"], a["numeros"]["dias_de_6"])
        self.assertEqual([331, 581], a["numeros"]["semana_de_6"])
        self.assertEqual(12821, a["numeros"]["dias_com_9_ou_mais"])
        self.assertIn("só 2 dias inteiros", a["quanto"])
        self.assertIn("331 views em 13/09 e 581 em 14/09", a["quanto"])
        self.assertIn("entre ~331 e ~581 views por dia", a["quanto"])
        self.assertIn("Com só 2 dias, é um sinal", a["quanto"])
        self.assertNotIn("~18 ", a["quanto"])
        self.assertNotIn("12.821 em", a["quanto"])

    def test_dia_de_9_dentro_do_regime_nao_entra_nos_dois_grupos(self):
        regs = _blocos_do_tiktok()
        for dia, n in ((13, 6), (14, 9)):
            for i in range(n):
                regs.append(tk(f"r{dia}-{i}", datetime(2026, 9, dia, 6, 5) + timedelta(hours=2 * i),
                               40))
        a, _ = analise.achado_pausa_tiktok(regs, AGORA, "builds")
        self.assertEqual(["2026-09-13"], a["numeros"]["dias_de_6"])
        self.assertEqual(360, a["numeros"]["dias_com_9_ou_mais"])
        self.assertIn("só 1 dia inteiro", a["quanto"])

    def test_dia_com_video_novo_nao_entra_nos_9_ou_mais(self):
        # Dia maduro pela IDADE de cada video: 16/10 tem a noite com 2,4 dias.
        regs = _blocos_do_tiktok()
        for i in range(9):
            regs.append(tk(f"n{i}", datetime(2026, 9, 20, 6, 5) + timedelta(hours=2 * i), 2))
            regs.append(tk(f"m{i}", datetime(2026, 10, 16, 6, 37) + timedelta(hours=2 * i), 50))
        a, _ = analise.achado_pausa_tiktok(regs, AGORA, "builds")
        self.assertEqual(18, a["numeros"]["dias_com_9_ou_mais"])

    def test_a_pausa_do_teste_contra_um_dia_inteiro_parado(self):
        # A frase "pausa longa nao garante" era desmentida pelos exemplos dela
        # (30,1 h e 22,2 h deram certo; a de 12,1 h nao tinha 3 dias).
        regs = _blocos_do_tiktok()
        q = AGORA - timedelta(days=40)
        # O primeiro post de todos nao tem pausa antes (nao conta); depois dele,
        # 5 blocos de ~12 h sem postar, e so o primeiro da certo: 1 de 5.
        regs.append(tk("abre", q - timedelta(hours=12), 1))
        for d in range(5):
            for i in range(3):
                regs.append(tk(f"doze{d}-{i}", q + timedelta(hours=i), 100 if d == 0 else 1))
            q += timedelta(hours=2 + 12)
        a, _ = analise.achado_pausa_tiktok(regs, AGORA, "builds")
        self.assertEqual(12.0, a["numeros"]["pausa_do_teste"])
        self.assertEqual("10 a 16 h", a["numeros"]["faixa_do_teste"])
        self.assertNotIn("Pausa longa não garante", a["vimos"])
        self.assertIn("A pausa de ~12 h do teste é a que menos se provou (deu certo 1 de 5 vezes",
                      a["vimos"])
        self.assertIn("a de um dia inteiro parado (22 h ou mais) deu certo", a["vimos"])
        self.assertIn("o próximo teste é um dia inteiro sem postar", a["vimos"])

    def test_bloco_do_teste_que_ainda_junta_views_e_dito_e_nao_conta(self):
        # Como o 18/10 12:47 (12,1 h): um bloco de ~12 h que ainda junta views.
        regs = _blocos_do_tiktok()
        base = AGORA - timedelta(days=1, hours=12) - timedelta(hours=12, minutes=6)
        regs.append(tk("base", base, 1))
        regs.append(tk("ontem", base + timedelta(hours=12, minutes=6), 1))
        self.assertLess(regs[-1]["idade_dias"], analise.MADURO_DIAS)
        a, _ = analise.achado_pausa_tiktok(regs, AGORA, "builds")
        self.assertEqual(1, len(a["numeros"]["blocos_do_teste_juntando"]))
        self.assertIn("ainda não tem 3 dias e não entra na conta", a["vimos"])
        self.assertIn("ainda não foi medida", a["vimos"])

    def test_sem_a_semana_de_comparacao_nao_projeta(self):
        a, _ = analise.achado_pausa_tiktok(_blocos_do_tiktok(), AGORA, "builds")
        self.assertIn("Não dá para estimar", a["quanto"])

    def test_o_maior_sucesso_fora_da_regra_e_dito(self):
        regs = _blocos_do_tiktok(canal="historias")
        dia = datetime(2026, 9, 25, 6, 0)
        for i in range(9):
            regs.append(tk(f"v{i}", dia + timedelta(hours=2 * i), 12572 if i == 8 else 1,
                           "historias"))
        a, _ = analise.achado_pausa_tiktok(regs, AGORA, "historias")
        self.assertEqual(9, a["numeros"]["posicao_do_maior"])
        self.assertIn("foi o 9º post do dia", a["vimos"])

    def test_perfil_parado_por_igual_nao_vira_achado(self):
        a, incerto = analise.achado_pausa_tiktok(_blocos_do_tiktok(views_descansado=1),
                                                 AGORA, "builds")
        self.assertIsNone(a)
        self.assertIn("ainda não separa do acaso", incerto)

    def test_poucos_blocos_diz_o_canal(self):
        # Caso zero: a mensagem saia igual para os dois canais, sem dizer qual.
        _, b = analise.achado_pausa_tiktok([], AGORA, "builds")
        _, h = analise.achado_pausa_tiktok([], AGORA, "historias")
        self.assertIn("TikTok de builds", b)
        self.assertIn("TikTok de histórias", h)
        self.assertIn("só 0 bloco", b)

    def test_horarios_sugeridos_saem_da_grade_e_respeitam_a_pausa(self):
        self.assertEqual(["09:37", "12:07", "15:37", "17:57", "20:37", "21:37"],
                         analise.horarios_sugeridos(6, grade.GRADE))
        self.assertEqual([], analise.horarios_sugeridos(len(grade.GRADE), grade.GRADE))
        for k in range(1, len(grade.GRADE)):
            horas = analise.horarios_sugeridos(k, grade.GRADE)
            if not horas:
                continue
            ini = int(horas[0][:2]) * 60 + int(horas[0][3:])
            fim = int(horas[-1][:2]) * 60 + int(horas[-1][3:])
            self.assertGreaterEqual((ini - fim) % 1440, analise.PAUSA_TIKTOK_H * 60, horas)

    def test_a_grade_de_dez_nao_tem_a_pausa_que_o_tiktok_pede(self):
        # O porque do achado: com os 10 horarios, a maior pausa e 6 h.
        minutos = sorted(h * 60 + m for h, m in grade.GRADE)
        maior = max((minutos[(i + 1) % len(minutos)] - minutos[i]) % 1440
                    for i in range(len(minutos)))
        self.assertLess(maior, analise.PAUSA_TIKTOK_H * 60)


class FormatoTests(unittest.TestCase):

    def _regs(self, n_duelo, n_estreia, v_duelo=100, v_estreia=20):
        regs = []
        for i in range(n_duelo):
            regs.append(yt(f"d{i}", AGORA - timedelta(days=4 + i % 20), v_duelo + i % 5,
                           "duelo", ret=50.0))
        for i in range(n_estreia):
            regs.append(yt(f"e{i}", AGORA - timedelta(days=4 + i % 20, hours=3),
                           v_estreia + i % 5, "estreia", ret=12.0))
        return regs

    def test_duelo_contra_estreia(self):
        a, _ = analise.achado_formato(self._regs(20, 20), AGORA, "builds", "youtube")
        self.assertEqual(("duelo", "estreia"), (a["numeros"]["melhor"], a["numeros"]["pior"]))
        self.assertIn("a estreia é o que menos rende", a["titulo"])
        self.assertGreater(a["peso"], 0)

    def test_poucos_videos_nao_recomendam_nada(self):
        a, incerto = analise.achado_formato(self._regs(5, 5), AGORA, "builds", "youtube")
        self.assertIsNone(a)
        self.assertIsNone(incerto)

    def test_melhor_formato_caindo_vira_faixa_e_aviso(self):
        # Duelo 119,5 -> 102 -> 86,5 (medido em 19/10): "+105/dia" vira faixa.
        regs = []
        segunda = (AGORA - timedelta(days=25)).date()
        segunda -= timedelta(days=segunda.weekday())
        for s, base in enumerate((120, 100, 85)):
            for i in range(7):
                q = datetime.combine(segunda + timedelta(weeks=s, days=i), datetime.min.time()) \
                    + timedelta(hours=12)
                if (AGORA - q).days >= 3 and q >= AGORA - timedelta(days=analise.JANELA_DIAS):
                    regs.append(yt(f"d{s}{i}", q, base, "duelo"))
                    regs.append(yt(f"e{s}{i}", q + timedelta(hours=2), 20, "estreia"))
        a, _ = analise.achado_formato(regs, AGORA, "builds", "youtube")
        self.assertTrue(a["numeros"]["caindo"], a["numeros"]["semanas_do_melhor"])
        self.assertIn("vem caindo semana a semana", a["vimos"])
        self.assertIn("Entre +", a["quanto"])
        self.assertIn("não se compara direto", a["vimos"])

    def test_formatos_iguais_vao_para_ainda_nao_da(self):
        a, incerto = analise.achado_formato(self._regs(12, 12, 50, 50), AGORA,
                                            "builds", "youtube")
        self.assertIsNone(a)
        self.assertIn("dentro do acaso", incerto)


class ConcentracaoESeguimentoTests(unittest.TestCase):

    def test_um_video_da_noite_leva_o_dia_nao_so_o_das_21h(self):
        # Como em 13/10 (22:30 = 286) e 15/10 (23:38 = 215): a noite, nao a hora.
        regs = []
        for d in range(12):
            dia = AGORA - timedelta(days=4 + d)
            vencedora = (21, 22, 23)[d % 3]
            for h in (6, 9, 12, 15, 18, 20, 21, 22, 23):
                regs.append(yt(f"{d}-{h}", dia.replace(hour=h, minute=37),
                               300 if h == vencedora else 2, "historia", canal="historias"))
        a, _ = analise.achado_concentracao(regs, AGORA, "historias", "youtube")
        self.assertIn("um vídeo da noite (21h às 23h) leva o dia", a["titulo"])
        self.assertEqual(12, a["numeros"]["dias_na_noite"])
        self.assertIn("nunca deixe a noite sem vídeo", a["mudar"])
        self.assertEqual(7, len(a["numeros"]["ultimos_7_dias"]))
        # Os dias 1 a 3 atras nao tem post nenhum: "nenhum vídeo à noite".
        self.assertIn("nenhum vídeo à noite", a["vimos"])

    def _noites(self):
        regs = []
        for d in range(12):
            dia = AGORA - timedelta(days=4 + d)
            for h in (6, 9, 12, 15, 18, 21, 22):
                regs.append(yt(f"{d}-{h}", dia.replace(hour=h, minute=37),
                               300 if h == 21 else 2, "historia", canal="historias"))
        return regs

    def test_maduro_e_a_idade_do_video_nao_o_dia_no_calendario(self):
        # 19/10 09:00: "16/10 23:42 = 5" tem 2,4 dias no ar. Ficava sem "(ainda
        # juntando views)" e contado como dia perdido porque o dia esta a 3
        # dias no calendario.
        regs = self._noites()
        regs.append(yt("tarde", datetime(2026, 10, 16, 23, 42), 5, "historia", canal="historias"))
        self.assertLess(regs[-1]["idade_dias"], analise.MADURO_DIAS)
        a, _ = analise.achado_concentracao(regs, AGORA, "historias", "youtube")
        dia = next(d for d in a["numeros"]["ultimos_7_dias"] if d["dia"] == "2026-10-16")
        self.assertFalse(dia["maduro"])
        self.assertIn("16/10 23:42 = 5 (ainda juntando views)", a["vimos"])
        self.assertNotIn("2026-10-16", a["numeros"]["dias_perdidos"])

    def test_dia_pela_metade_nao_entra_no_vencedor_do_dia(self):
        # 16/10 tinha 3 de 8 videos com 3+ dias (a manha): o "vencedor" dele era
        # da manha. Dia so entra inteiro.
        regs = self._noites()
        for h, v in ((0, 100), (3, 2), (6, 2)):
            regs.append(yt(f"m{h}", datetime(2026, 10, 16, h, 37), v, "historia",
                           canal="historias"))
        regs.append(yt("noite", datetime(2026, 10, 16, 21, 38), 300, "historia",
                       canal="historias"))
        a, _ = analise.achado_concentracao(regs, AGORA, "historias", "youtube")
        self.assertEqual(12, a["numeros"]["dias"])
        self.assertEqual(12, a["numeros"]["dias_na_noite"])

    def test_vencedor_que_nao_e_da_noite_nao_vira_este_achado(self):
        regs = []
        for d in range(12):
            dia = AGORA - timedelta(days=4 + d)
            for h in (6, 9, 12, 15, 18, 21):
                regs.append(yt(f"{d}-{h}", dia.replace(hour=h, minute=37),
                               300 if h == 9 else 2, "historia", canal="historias"))
        a, _ = analise.achado_concentracao(regs, AGORA, "historias", "youtube")
        self.assertIsNone(a)

    def test_views_espalhadas_nao_viram_concentracao(self):
        regs = [yt(f"{d}-{h}", (AGORA - timedelta(days=4 + d)).replace(hour=h), 50,
                   "historia", canal="historias")
                for d in range(12) for h in (6, 9, 12, 15, 18, 21)]
        a, _ = analise.achado_concentracao(regs, AGORA, "historias", "youtube")
        self.assertIsNone(a)

    def test_quem_ve_uma_parte_nao_ve_a_proxima(self):
        regs = []
        for s in range(6):
            q = AGORA - timedelta(days=10 + s)
            regs.append(yt(f"s{s}p1", q, 500, "historia", canal="historias",
                           fonte_id=f"hist{s}", parte=1, partes=2))
            regs.append(yt(f"s{s}p2", q + timedelta(hours=3), 3, "historia",
                           canal="historias", fonte_id=f"hist{s}", parte=2, partes=2))
        a, _ = analise.achado_seguimento(regs, AGORA, "historias", "youtube")
        self.assertEqual(6, a["numeros"]["pares"])
        self.assertAlmostEqual(0.006, a["numeros"]["razao_mediana"])
        # Vies do horario: nao vira conclusao, vira TESTE.
        self.assertEqual("incerto", a["confianca"])
        self.assertIn("Testar por 1 semana", a["mudar"])
        self.assertIn("não dá para separar isso do horário", a["titulo"])

    def test_par_sem_status_ou_fora_de_ordem_nao_conta(self):
        # 00064 p2 e 00058 p2 (sem status) e 00010 (a seguinte saiu ANTES).
        regs = []
        for s in range(5):
            q = AGORA - timedelta(days=10 + s)
            regs.append(yt(f"s{s}p1", q, 500, "historia", canal="historias",
                           fonte_id=f"h{s}", parte=1, partes=2))
            regs.append(yt(f"s{s}p2", q + timedelta(hours=3), 3, "historia",
                           canal="historias", fonte_id=f"h{s}", parte=2, partes=2))
        q = AGORA - timedelta(days=20)
        regs.append(yt("x1", q, 500, "historia", canal="historias", fonte_id="semstatus",
                       parte=1, partes=2))
        regs.append(yt("x2", q + timedelta(hours=3), 400, "historia", canal="historias",
                       fonte_id="semstatus", parte=2, partes=2, priv=None))
        regs.append(yt("y1", q, 500, "historia", canal="historias", fonte_id="foradeordem",
                       parte=1, partes=2))
        regs.append(yt("y2", q - timedelta(hours=5), 400, "historia", canal="historias",
                       fonte_id="foradeordem", parte=2, partes=2))
        a, _ = analise.achado_seguimento(regs, AGORA, "historias", "youtube")
        self.assertEqual(5, a["numeros"]["pares"])


class ColetaETextoTests(unittest.TestCase):

    def test_dias_de_coleta_pelo_log(self):
        pasta = Path(tempfile.mkdtemp(prefix="logs-"))
        (pasta / "auto_20261009.txt").write_text(
            "07:08:36 [metricas] dia-2026-10-09: builds erro 0 (2 data) · builds_tiktok erro 0 · "
            "historias erro 0 · historias_tiktok erro 0 — noite PENDENTE\n", encoding="utf-8")
        (pasta / "auto_20261011.txt").write_text(
            "07:39 [metricas] dia-2026-10-11: builds ok 245 (461 analytics) · builds_tiktok ok 235 "
            "(235 de 235 envios, lista suficiente) · historias ok 264 · historias_tiktok ok 268\n",
            encoding="utf-8")
        (pasta / "auto_20261014.txt").write_text(
            "10:13 [metricas] dia-2026-10-14: builds ok 267 · builds_tiktok ok 258 · historias "
            "erro 0 (252 analytics) · historias_tiktok ok 293\n", encoding="utf-8")
        dias = {d["dia"]: d["estado"] for d in analise.dias_de_coleta(
            datetime(2026, 10, 14, 12), dias=7, pasta_dos_logs=pasta)}
        self.assertEqual({"2026-10-08": "nao_medido", "2026-10-09": "falhou",
                          "2026-10-10": "nao_rodou", "2026-10-11": "completa",
                          "2026-10-12": "nao_rodou", "2026-10-13": "nao_rodou",
                          "2026-10-14": "parcial"}, dias)

    def test_sem_log_nenhum_e_nao_medido_nunca_completa(self):
        vazio = Path(tempfile.mkdtemp(prefix="logs-"))
        estados = {d["estado"] for d in analise.dias_de_coleta(AGORA, 5, vazio)}
        self.assertEqual({"nao_medido"}, estados)

    def test_conta_video_nao_linha_e_separa_o_numero_parado(self):
        linhas = [{"plataforma": "youtube", "youtube_id": "a", "url": "x",
                   "quando": "2026-10-10T12:07:00"},
                  {"plataforma": "youtube", "youtube_id": "a", "url": "x",
                   "quando": "2026-10-10T12:08:00"},
                  {"plataforma": "tiktok", "url": "x", "quando": "2026-10-10T12:07:00"},
                  {"plataforma": "tiktok", "url": "x", "quando": "2026-10-19T09:00:00"}]
        salvas = {("builds", "youtube"): [{"youtube_id": "a", "quando": "2026-10-10T12:07:00",
                                           "views": 5, "privacidade": "public",
                                           "atualizado": "2026-10-19T07:30:00"}],
                  ("builds", "tiktok"): [{"tiktok_id": "t", "post_time": 1, "views": 5,
                                          "atualizado": "2026-09-17T07:00:00"}]}
        cob = analise.cobertura(entrada_vazia(marca=MARCA_BOA, ledger={"builds": linhas},
                                              salvas=salvas))
        yt_, tk_ = cob["partes"]["builds"], cob["partes"]["builds_tiktok"]
        self.assertEqual((1, 1), (yt_["videos_postados"], yt_["linhas_repetidas"]))
        self.assertEqual((1, 0, ["2026-09-17"]), (tk_["parados"], tk_["medidos_hoje"],
                                                  tk_["parados_desde"]))
        self.assertEqual((1, 0), (tk_["depois_da_coleta"], tk_["nunca_medidos"]))
        a = analise.analisar([], cob, AGORA)
        self.assertTrue(any("não mostra mais; o número deles parou em 17/09" in x
                            for x in a["avisos"]), a["avisos"])
        self.assertFalse(any("nunca tiveram número" in x for x in a["avisos"]))

    def test_retencao_conta_os_mesmos_videos_do_numero_de_hoje(self):
        # Historias TikTok em 19/10: "336 com número desta coleta; em 338 dá
        # para saber quanto as pessoas assistem" — a 2a conta incluia os 3
        # parados. Agora: 3 com numero de hoje, 2 deles com retencao, e o
        # parado dito a parte. E "1 postado" no singular.
        hoje = [{"tiktok_id": f"t{i}", "post_time": 1, "views": 50,
                 "media_percentual": 40.0 if i < 2 else None,
                 "atualizado": "2026-10-19T07:30:00"} for i in range(3)]
        parado = {"tiktok_id": "velho", "post_time": 1, "views": 5, "media_percentual": 30.0,
                  "atualizado": "2026-09-17T07:00:00"}
        linhas = [{"plataforma": "tiktok", "url": "x", "quando": "2026-10-10T12:07:00"}] * 4 + [
            {"plataforma": "tiktok", "url": "x", "quando": "2026-10-19T09:37:00"}]
        cob = analise.cobertura(entrada_vazia(
            marca=MARCA_BOA, ledger={"historias": linhas},
            salvas={("historias", "tiktok"): hoje + [parado]}))
        parte = cob["partes"]["historias_tiktok"]
        self.assertEqual((3, 3, 2, 1), (parte["medidos_hoje"], parte["com_retencao"],
                                        parte["com_retencao_hoje"], parte["parados"]))
        html_ = analise._cobertura_html(cob)
        self.assertIn("3 vídeos têm número desta coleta; em 2 deles dá para saber quanto as "
                      "pessoas assistem. Outro vídeo tem só o número antigo: o TikTok parou de "
                      "mostrá-lo.", html_)
        self.assertNotIn("em 3 dá para saber", html_)
        self.assertIn("1 postado depois da coleta (entra na próxima)", html_)
        self.assertNotIn("1 postados", html_)

    def test_view_no_singular(self):
        self.assertEqual("1 view", analise._v(1))
        self.assertEqual("1,5 view", analise._v(1.5))
        self.assertEqual("0 views", analise._v(0))
        self.assertEqual("12.572 views", analise._v(12572))
        self.assertEqual("1 vídeo", analise._qtd(1, "vídeo", "vídeos"))

    def test_pagina_sem_jargao_e_poucos_em_linha_propria(self):
        regs = [yt(f"v{i}", AGORA - timedelta(days=4 + i), 10 + i, ret=50.0) for i in range(12)]
        cob = analise.cobertura(entrada_vazia(
            marca=MARCA_BOA, dias_de_coleta=[{"dia": "2026-10-13", "estado": "nao_rodou"}]))
        pagina = analise.pagina(analise.analisar(regs, cob, AGORA))
        for jargao in ("sem par no Studio", "sem status", "com %", "Formato × formato",
                       "(poucos)", " 1 views"):
            self.assertNotIn(jargao, pagina)
        self.assertIn("<br><span class=poucos>poucos</span>", pagina)
        self.assertIn("13/10<br>○", pagina)
        self.assertNotIn("white-space:nowrap", analise.CSS)

    def test_achado_que_pede_teste_vem_depois_dos_firmes(self):
        firme = analise._achado("a", "p", "erro", "t", "v", "m", "q", "provavel", 1)
        teste = analise._achado("b", "p", "atencao", "t", "v", "m", "q", "incerto", 999)
        cob = analise.cobertura(entrada_vazia(marca=MARCA_BOA))
        originais = analise.achado_pausa_tiktok
        self.addCleanup(setattr, analise, "achado_pausa_tiktok", originais)
        fila = [(teste, None), (firme, None)]
        analise.achado_pausa_tiktok = lambda *a, **k: fila.pop(0) if fila else (None, None)
        regs = [yt("x", AGORA - timedelta(days=4), 10)]
        ordem = [a["id"] for a in analise.analisar(regs, cob, AGORA)["achados"]]
        self.assertEqual(["a", "b"], ordem)


class TendenciaTests(unittest.TestCase):

    def _serie(self, valores):
        inicio = AGORA.date() - timedelta(days=len(valores))
        return {"dias": [[(inicio + timedelta(days=i)).isoformat(), v, 0, 0, 0]
                         for i, v in enumerate(valores)]}

    def test_zero_contra_zero_e_parado_nao_estavel(self):
        t = analise.tendencia([], AGORA, self._serie([0] * 20))
        self.assertEqual("parado", t["sentido"])

    def test_queda_do_canal(self):
        t = analise.tendencia([], AGORA, self._serie([150] * 7 + [100] * 7))
        self.assertEqual(("caindo", 700, 1050), (t["sentido"], t["ultimos_7"],
                                                 t["anteriores_7"]))

    def test_sem_serie_e_sem_video_e_sem_dados(self):
        self.assertEqual("sem_dados", analise.tendencia([], AGORA)["sentido"])


class BibliotecaTests(unittest.TestCase):

    def _dublê(self, itens, codigo=0):
        chamadas = []

        def executar(args):
            chamadas.append(args)
            if args[0] == "listar":
                return SimpleNamespace(returncode=0, stdout=json.dumps(itens), stderr="")
            return SimpleNamespace(returncode=codigo, stdout="novo123\n", stderr="recusou")
        return chamadas, executar

    def test_primeira_vez_adiciona_com_a_etiqueta(self):
        chamadas, executar = self._dublê([])
        self.assertEqual("novo123", analise.publicar_na_biblioteca(Path("x.html"), executar))
        self.assertEqual("adicionar", chamadas[1][0])
        self.assertIn(analise.TAG_DA_BIBLIOTECA, chamadas[1])

    def test_depois_troca_a_mesma_pagina(self):
        item = {"id": "abc", "tipo": "pagina", "tags": [analise.TAG_DA_BIBLIOTECA]}
        chamadas, executar = self._dublê([item])
        self.assertEqual("abc", analise.publicar_na_biblioteca(Path("x.html"), executar))
        self.assertEqual(["guardar", "--id", "abc", "--html", "x.html"], chamadas[1])

    def test_caminho_real_da_biblioteca_numa_pasta_descartavel(self):
        # O processo de verdade (`python -m remoto.biblioteca`), com o runtime
        # apontado para um tmpdir: duas rodadas = UMA pagina, trocada.
        import os
        runtime = Path(tempfile.mkdtemp(prefix="biblioteca-"))
        antes = os.environ.get("NEURAL_FIGHTS_RUNTIME_DIR")
        self.addCleanup(lambda: os.environ.__setitem__("NEURAL_FIGHTS_RUNTIME_DIR", antes)
                        if antes is not None else os.environ.pop("NEURAL_FIGHTS_RUNTIME_DIR", None))
        os.environ["NEURAL_FIGHTS_RUNTIME_DIR"] = str(runtime)
        html_ = runtime / "pagina.html"
        html_.write_text("<p>Análise 1 🎬</p>", encoding="utf-8")
        primeiro = analise.publicar_na_biblioteca(html_)
        html_.write_text("<p>Análise 2</p>", encoding="utf-8")
        segundo = analise.publicar_na_biblioteca(html_)
        self.assertEqual(primeiro, segundo)
        itens = json.loads((runtime / "biblioteca" / "itens.json").read_text(encoding="utf-8"))
        self.assertEqual(1, len(itens))
        self.assertEqual(analise.TITULO_DA_PAGINA, itens[0]["titulo"])
        copia = runtime / "biblioteca" / "paginas" / f"{primeiro}.html"
        self.assertIn("Análise 2", copia.read_text(encoding="utf-8"))

    def test_recusa_levanta(self):
        _chamadas, executar = self._dublê([], codigo=2)
        with self.assertRaises(RuntimeError):
            analise.publicar_na_biblioteca(Path("x.html"), executar)


class PaginaTests(unittest.TestCase):

    def test_titulo_do_video_e_escapado(self):
        regs = [yt(f"v{i}", AGORA - timedelta(days=4 + i), 10 + i) for i in range(3)]
        regs[0]["titulo"] = "<script>alert(1)</script>"
        cob = analise.cobertura(entrada_vazia(marca=MARCA_BOA))
        pagina = analise.pagina(analise.analisar(regs, cob, AGORA))
        self.assertNotIn("<script>alert", pagina)
        self.assertIn("&lt;script&gt;", pagina)


if __name__ == "__main__":
    unittest.main()
