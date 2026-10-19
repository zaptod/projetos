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


def _rodadas_do_tiktok(canal="builds", bons=6, total=9, dias=12, views_bons=100):
    regs = []
    inicio = AGORA - timedelta(days=dias + 4)
    for d in range(dias):
        for i in range(total):
            quando = inicio + timedelta(days=d, hours=9 + i)
            regs.append(tk(f"{canal}{d}-{i}", quando, views_bons if i < bons else 1, canal))
    return regs


class PausaDoTikTokTests(unittest.TestCase):

    def test_so_os_primeiros_depois_da_pausa_recebem_views(self):
        a, _ = analise.achado_pausa_tiktok(_rodadas_do_tiktok(), AGORA, "builds")
        self.assertIsNotNone(a)
        self.assertEqual(6, a["numeros"]["corte"])
        self.assertEqual(100, a["numeros"]["mediana_primeiros"])
        self.assertEqual("claro", a["confianca"])
        self.assertIn("no máximo 6", a["mudar"])

    def test_perfil_parado_por_igual_nao_vira_achado(self):
        regs = _rodadas_do_tiktok(views_bons=1)
        a, _ = analise.achado_pausa_tiktok(regs, AGORA, "builds")
        self.assertIsNone(a)

    def test_poucos_posts_vai_para_ainda_nao_da(self):
        a, incerto = analise.achado_pausa_tiktok(_rodadas_do_tiktok(dias=1), AGORA, "builds")
        self.assertIsNone(a)
        self.assertTrue(incerto)

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

    def test_formatos_iguais_vao_para_ainda_nao_da(self):
        a, incerto = analise.achado_formato(self._regs(12, 12, 50, 50), AGORA,
                                            "builds", "youtube")
        self.assertIsNone(a)
        self.assertIn("dentro do acaso", incerto)


class ConcentracaoESeguimentoTests(unittest.TestCase):

    def test_o_dia_decidido_pelo_video_das_21h(self):
        regs = []
        for d in range(12):
            dia = AGORA - timedelta(days=4 + d)
            for h in (6, 9, 12, 15, 18, 20, 21, 23):
                regs.append(yt(f"{d}-{h}", dia.replace(hour=h, minute=37),
                               300 if h == 21 else 2, "historia", canal="historias"))
        a, _ = analise.achado_concentracao(regs, AGORA, "historias", "youtube")
        self.assertEqual(21, a["numeros"]["hora"])
        self.assertIn("vitrine", a["mudar"])
        # Os dias 1 a 3 atras nao tem post: a vitrine ficou vazia, e isso e dito.
        self.assertEqual(3, len(a["numeros"]["dias_sem_a_vitrine"]))
        self.assertIn("Nunca deixe o horário das 21h vazio", a["mudar"])

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
