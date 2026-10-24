# -*- coding: utf-8 -*-
"""O canal de DUELOS (builds) em tres horarios no YouTube e um no TikTok.

`docs/PLANO.md`, semana 1 (20/10/2026): "YouTube 3/dia em horario fixo, so
confrontos diferentes; TikTok 1-3/dia". Ajustes do orquestrador no mesmo dia:
o canal fala INGLES com o publico dos EUA (`geral/canal-em-ingles`; horarios
de `docs/pesquisa/som-ganchos-e-musica.md`, recomendacao 7: ~10h, ~19h e ~22h
de Brasilia ate 31/10 e 1 h mais tarde desde 01/11, nos minutos da grade) e
o TikTok de duelos fica em UM por dia (parte metricas: com ~10 por dia, 28
de 36 posts de 12 a 15/10 ficaram em 0 views; so pegaram os que vieram
depois de uma pausa). As historias nao mudam: dez no YouTube, seis no TikTok.

A grade que sai (conta de mao, `python -m builds.grade AAAA-MM-DD`):

    horario  ate 26/10 (builds)     desde 27/10 (builds)
    06:37    -                      youtube
    09:37    youtube                youtube
    12:07    -                      youtube
    15:37    -                      youtube
    17:57    youtube                youtube
    20:37    -                      -
    21:37    youtube + tiktok       youtube + tiktok
    22:37    -                      youtube
    23:37    -                      youtube
    (historias: youtube nos dez; tiktok 09:37 a 21:37)

OITO DUELOS POR DIA DESDE 27/10/2026 (decisao `publicacao/semana-2-volume`,
24/10): a tabela de 27/10 SUBSTITUI a de 01/11 (12:07, 20:37, 22:37; TikTok
20:37), que nunca valeu. O TikTok segue em UM por dia, 21:37, tambem depois de
01/11. Tirados 00:37 e 20:37, os dois piores da razao views / mediana do dia
(0,75 e 0,68; os outros 0,82 a 1,40).

Caso ZERO: canal sem grade propria (historias, ou nome desconhecido) = a da
plataforma inteira; fora da grade o canal de builds NAO le ledger nem
catalogo, nao entra no aviso e nao faz a rodada sair 1.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_duelos", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    modulo._linha = lambda *a, **k: None
    return modulo


def _no_relogio(m, quando: datetime):
    """Fixa o relogio da grade do canal (a UNICA leitura de hora dela)."""
    if not hasattr(m, "_fora_original"):
        m._fora_original = m._fora_da_grade_do_canal
    original = m._fora_original
    m._fora_da_grade_do_canal = (lambda canal, plataforma, agora=None:
                                 original(canal, plataforma, quando))


def _duelo(n: int, classes=("Mago (Arcano)", "Ninja (Velocidade)"),
           quando: float = 0.0):
    return SimpleNamespace(id=f"duelo_{n:05d}:duelo:celular",
                           fonte_id=f"duelo_{n:05d}", origem="duelo",
                           titulo=f"A{n} x B{n}", quando=quando or float(n),
                           caminho=None, _classes=classes)


OUTUBRO = date(2026, 10, 21)
VESPERA = date(2026, 10, 26)
OITO = date(2026, 10, 27)
NOVEMBRO = date(2026, 11, 1)
OS_OITO = (6, 9, 12, 15, 17, 21, 22, 23)


def _relogio_em(caso, dia):
    """Os testes de CONSUMO leem o relogio da grade (`tabela_do_canal(None)`).
    Sem fixar, o que dava 3 por dia em 24/10 daria 8 em 27/10 e o teste
    quebrava sozinho, sem ninguem ter mexido em nada."""
    from builds import grade
    original = grade.tabela_do_canal
    caso.addCleanup(setattr, grade, "tabela_do_canal", original)
    grade.tabela_do_canal = lambda quando=None: original(
        dia if quando is None else quando)


class GradeDoCanalTests(unittest.TestCase):
    def test_builds_tres_no_youtube_e_um_no_tiktok(self):
        from builds import grade
        self.assertEqual((9, 17, 21), grade.horas_do_canal(
            "builds", "youtube", OUTUBRO))
        self.assertEqual((21,), grade.horas_do_canal("builds", "tiktok",
                                                     OUTUBRO))
        self.assertEqual(["09:37", "17:57", "21:37"],
                         grade.horarios("youtube", "builds", OUTUBRO))
        for dia in (OUTUBRO, VESPERA):
            self.assertEqual(3, grade.meta_diaria("builds", "youtube", dia))
            self.assertEqual(1, grade.meta_diaria("builds", "tiktok", dia))

    def test_de_27_10_em_diante_oito_duelos_e_o_tiktok_segue_um(self):
        """Decisao `publicacao/semana-2-volume`: 8 no YouTube a partir de
        27/10 e o TikTok em UM por dia, 21:37. A tabela substitui a de 01/11
        (12:07, 20:37, 22:37; TikTok 20:37), que nunca valeu: 01/11 e depois
        dele ficam nos mesmos oito e no TikTok das 21:37. A troca e pela data,
        sozinha: 26/10 ainda e a de tres."""
        from builds import grade
        self.assertEqual((9, 17, 21), grade.horas_do_canal(
            "builds", "youtube", VESPERA))
        self.assertEqual(OS_OITO, grade.horas_do_canal(
            "builds", "youtube", OITO))
        self.assertEqual(OS_OITO, grade.horas_do_canal(
            "builds", "youtube", NOVEMBRO))
        self.assertEqual(OS_OITO, grade.horas_do_canal(
            "builds", "youtube", datetime(2026, 12, 25, 12, 10)))
        for dia in (OITO, NOVEMBRO, date(2026, 12, 25)):
            self.assertEqual((21,), grade.horas_do_canal("builds", "tiktok",
                                                         dia))
            self.assertEqual(8, grade.meta_diaria("builds", "youtube", dia))
            self.assertEqual(1, grade.meta_diaria("builds", "tiktok", dia))
        self.assertNotIn(20, grade.horas_do_canal("builds", "youtube",
                                                  NOVEMBRO))
        self.assertEqual(["06:37", "09:37", "12:07", "15:37", "17:57",
                          "21:37", "22:37", "23:37"],
                         grade.horarios("youtube", "builds", OITO))
        # o TikTok dos builds e sempre um horario do YouTube dos builds
        for dia in (OUTUBRO, OITO, NOVEMBRO):
            self.assertTrue(set(grade.horas_do_canal("builds", "tiktok", dia))
                            <= set(grade.horas_do_canal("builds", "youtube",
                                                        dia)))
        # historias nao mudam
        for dia in (OUTUBRO, OITO, NOVEMBRO):
            self.assertEqual(grade.HORAS, grade.horas_do_canal(
                "historias", "youtube", dia))
            self.assertEqual(grade.HORAS_DO_TIKTOK, grade.horas_do_canal(
                "historias", "tiktok", dia))

    def test_os_oito_sao_espalhados_e_sem_os_dois_piores(self):
        """Conta de mao: dos dez da grade saem 00:37 e 20:37 (0,75 e 0,68 da
        mediana do dia, builds no YouTube, 15/09 a 24/10). Nenhum buraco de
        mais de 4 h entre 06:37 e 23:37."""
        from builds import grade
        horas = grade.horas_do_canal("builds", "youtube", OITO)
        self.assertEqual({0, 20}, set(grade.HORAS) - set(horas))
        minutos = [h * 60 + grade.minuto(h) for h in horas]
        buracos = [b - a for a, b in zip(minutos, minutos[1:])]
        self.assertLessEqual(max(buracos), 4 * 60, buracos)
        self.assertEqual(8, len(horas))

    def test_antes_de_20_10_os_builds_tinham_os_dez(self):
        """O passado conta pela grade que valia: um dia de setembro com 10
        posts de builds foi um dia cheio (conferencia, placar, analise)."""
        from builds import grade
        self.assertEqual(grade.HORAS, grade.horas_do_canal(
            "builds", "youtube", date(2026, 9, 27)))
        self.assertEqual(grade.HORAS_DO_TIKTOK, grade.horas_do_canal(
            "builds", "tiktok", date(2026, 10, 19)))
        self.assertEqual((9, 17, 21), grade.horas_do_canal(
            "builds", "youtube", date(2026, 10, 20)))

    def test_historias_nao_mudam(self):
        from builds import grade
        self.assertEqual(grade.HORAS, grade.horas_do_canal("historias",
                                                           "youtube"))
        self.assertEqual(grade.HORAS_DO_TIKTOK,
                         grade.horas_do_canal("historias", "tiktok"))
        self.assertEqual(10, grade.meta_diaria("historias", "youtube"))
        self.assertEqual(6, grade.meta_diaria("historias", "tiktok"))

    def test_caso_zero_canal_sem_grade_propria_e_a_da_plataforma(self):
        from builds import grade
        for canal in (None, "", "nao_existe"):
            self.assertEqual(grade.HORAS, grade.horas_do_canal(canal))
            self.assertEqual(grade.HORAS_DO_TIKTOK,
                             grade.horas_do_canal(canal, "tiktok"))

    def test_o_canal_e_sempre_subconjunto_da_plataforma(self):
        """Um horario que o TikTok nao tem nao vira TikTok so porque o canal
        o pede: o canal pedindo 22:37 no TikTok fica sem ele."""
        from builds import grade
        original = grade.HORAS_POR_CANAL
        self.addCleanup(setattr, grade, "HORAS_POR_CANAL", original)
        grade.HORAS_POR_CANAL = {"builds": {"tiktok": (21, 22)}}
        self.assertEqual((21,), grade.horas_do_canal("builds", "tiktok",
                                                     OUTUBRO))
        for _desde, tabela in grade.HORAS_POR_CANAL_DESDE:
            for canal, por in tabela.items():
                for p, horas in por.items():
                    self.assertTrue(set(horas)
                                    <= set(grade.horas_da_plataforma(p)),
                                    (canal, p))

    def test_conta_do_dia(self):
        """historias 10 + 6, builds 3 + 1 = 20 (eram 32 com a grade de dez
        para todos e 6 no TikTok)."""
        from builds import grade
        self.assertEqual(20, grade.META_DIARIA_TOTAL)
        dia = grade.grade_do_dia(OUTUBRO)
        self.assertEqual(10, len(dia))
        builds = {l["horario"]: l["builds"] for l in dia if l["builds"]}
        self.assertEqual({"09:37": ["youtube"], "17:57": ["youtube"],
                          "21:37": ["youtube", "tiktok"]}, builds)
        for dia in (OITO, NOVEMBRO):
            builds = {l["horario"]: l["builds"]
                      for l in grade.grade_do_dia(dia) if l["builds"]}
            self.assertEqual(
                {"06:37": ["youtube"], "09:37": ["youtube"],
                 "12:07": ["youtube"], "15:37": ["youtube"],
                 "17:57": ["youtube"], "21:37": ["youtube", "tiktok"],
                 "22:37": ["youtube"], "23:37": ["youtube"]}, builds)
        self.assertIn("builds youtube 3, tiktok 1",
                      grade.texto_da_grade_do_dia(OUTUBRO))
        self.assertIn("builds youtube 8, tiktok 1",
                      grade.texto_da_grade_do_dia(OITO))

    def test_vencidos_do_canal(self):
        from builds import grade
        self.assertEqual([9, 17], grade.vencidos(
            datetime(2026, 10, 20, 18, 0), "youtube", "builds"))
        self.assertEqual([], grade.vencidos(
            datetime(2026, 10, 20, 18, 0), "tiktok", "builds"))
        self.assertEqual(6, len(grade.vencidos(
            datetime(2026, 10, 20, 18, 0), "youtube", "historias")))

    def test_o_dia_de_grade_do_tiktok_nao_muda(self):
        """O canal so escolhe horarios dentro da grade; o dia de grade (a
        chave de um por horario) continua o da plataforma."""
        from builds.publicar import conferencia
        self.assertEqual((9, 21), conferencia.abertura_e_fechamento("tiktok"))


class ForaDaGradeDoCanalTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()

    def test_cada_horario(self):
        f = self.m._fora_da_grade_do_canal
        casos = {  # quando: (youtube dos builds, tiktok dos builds)
            datetime(2026, 10, 20, 6, 40): (False, False),
            datetime(2026, 10, 20, 9, 40): (True, False),
            datetime(2026, 10, 20, 12, 10): (False, False),
            datetime(2026, 10, 20, 15, 40): (False, False),
            # a rodada das 17:57 que cruza a hora continua dela
            datetime(2026, 10, 20, 18, 3): (True, False),
            datetime(2026, 10, 20, 21, 40): (True, True),
            datetime(2026, 10, 20, 22, 2): (True, True),
            datetime(2026, 10, 20, 22, 40): (False, False),
            datetime(2026, 10, 21, 0, 40): (False, False),
            # 26/10 ainda e a de tres; 27/10 em diante, os oito (TikTok 21:37)
            datetime(2026, 10, 26, 12, 10): (False, False),
            datetime(2026, 10, 27, 6, 40): (True, False),
            datetime(2026, 10, 27, 9, 40): (True, False),
            datetime(2026, 10, 27, 12, 10): (True, False),
            datetime(2026, 10, 27, 15, 40): (True, False),
            datetime(2026, 10, 27, 18, 3): (True, False),
            datetime(2026, 10, 27, 20, 40): (False, False),
            datetime(2026, 10, 27, 21, 40): (True, True),
            datetime(2026, 10, 27, 22, 40): (True, False),
            datetime(2026, 10, 27, 23, 40): (True, False),
            datetime(2026, 10, 28, 0, 40): (False, False),
            datetime(2026, 11, 1, 20, 40): (False, False),
            datetime(2026, 11, 1, 21, 40): (True, True),
            datetime(2026, 11, 1, 22, 40): (True, False),
        }
        for quando, (yt, tk) in casos.items():
            self.assertEqual(yt, f("builds", "youtube", quando) == "", quando)
            self.assertEqual(tk, f("builds", "tiktok", quando) == "", quando)
            # historias: sem grade propria, sempre "" (a da plataforma e de
            # `_tiktok_neste_horario`, que os testes ja fixam)
            self.assertEqual("", f("historias", "youtube", quando))
            self.assertEqual("", f("historias", "tiktok", quando))

    def test_o_motivo_diz_os_horarios_do_canal(self):
        motivo = self.m._fora_da_grade_do_canal(
            "builds", "youtube", datetime(2026, 10, 20, 6, 40))
        self.assertIn("06:37", motivo)
        self.assertIn("09:37, 17:57, 21:37", motivo)


class PostarBuildForaDaGradeTests(unittest.TestCase):
    def setUp(self):
        self.m = m = _postar()

        def nao_le(*a, **k):
            raise AssertionError("fora da grade nao le ledger nem catalogo")
        m.publicou_neste_horario = nao_le
        m.proximo_build = nao_le
        m._vez_do_tiktok_builds = nao_le
        m._divida_do_youtube_dos_builds = nao_le

    def test_fora_da_grade_nao_le_nada_e_marca_a_ficha(self):
        _no_relogio(self.m, datetime(2026, 10, 20, 6, 40))
        r = self.m.postar_build()
        self.assertFalse(r["feito"])
        self.assertTrue(r["fora_da_grade"])
        self.assertIn("09:37", r["motivo"])

    def test_no_horario_so_do_youtube_o_tiktok_fica_fora(self):
        """09:37: o YouTube dos builds posta; o TikTok (so 21:37) nao."""
        m = self.m
        _no_relogio(m, datetime(2026, 10, 20, 9, 40))
        m.publicou_neste_horario = lambda *a, **k: None
        m._tiktok_neste_horario = lambda agora=None: True
        m._divida_do_youtube_dos_builds = lambda: (None, "", [])
        alvo = _duelo(1)
        m.proximo_build = lambda **k: alvo
        m._youtube_dos_builds = lambda a, laudo=None: "https://youtu.be/abc"
        m._tiktok_dos_builds = lambda *a, **k: self.fail("TikTok fora")
        m.titulo_repetido = lambda *a, **k: False
        m._registrar_valvula = lambda ficha: None
        r = m.postar_build()
        self.assertTrue(r["feito"])
        self.assertTrue(r["tiktok_fora_da_grade"])
        self.assertNotIn("fora_da_grade", r)


class RodadaSemOCanalForaDaGradeTests(unittest.TestCase):
    """A ficha `fora_da_grade` sai do aviso e do codigo de saida."""

    def setUp(self):
        self.m = m = _postar()
        m.esperar_a_rede = lambda **k: True
        self.avisos = []
        m.avisar = lambda r: self.avisos.append([x["canal"] for x in r])
        m.avisar_lote_nao_fechou = lambda *a, **k: None
        m.estoque_do_lote = lambda *a, **k: {}
        m.linhas_do_estoque = lambda lote: []
        m.retidos_por_canal = lambda: {}
        m.consertadas_por_canal = lambda: {}
        m.reserva_do_tiktok = lambda *a, **k: []
        m.recuperar_no_tiktok = lambda **k: {"fila": 0}
        self.recuperou = []
        m.recuperar_no_youtube = lambda **k: self.recuperou.append(1) or {
            "fila": 0}
        m.publicar_da_reserva = lambda **k: {}
        m.postar_build = lambda **k: {"canal": "builds", "feito": False,
                                      "fora_da_grade": True,
                                      "motivo": "fora"}

    def test_historias_publicou_e_builds_fora_sai_0_e_avisa_so_historias(self):
        self.m.postar_historia = lambda **k: {"canal": "historias",
                                              "feito": True, "alvo": "h"}
        _no_relogio(self.m, datetime(2026, 10, 20, 6, 40))
        self.assertEqual(0, self.m.main([]))
        self.assertEqual([["historias"]], self.avisos)
        # e a recuperacao do YouTube dos builds nao roda fora da grade
        self.assertEqual([], self.recuperou)

    def test_caso_zero_historias_sem_parte_e_builds_fora_continua_1(self):
        """Historias tentou e nada saiu: a regra de 12/09 nao muda."""
        self.m.postar_historia = lambda **k: {"canal": "historias",
                                              "feito": False, "motivo": "x"}
        _no_relogio(self.m, datetime(2026, 10, 20, 6, 40))
        self.assertEqual(1, self.m.main([]))


class PortaDoTiktokDosBuildsTests(unittest.TestCase):
    """A recuperacao e a reserva entram pela mesma porta: fora das 21:37 o
    TikTok dos builds recusa, as historias nao."""

    def setUp(self):
        self.m = m = _postar()
        m._tiktok_neste_horario = lambda agora=None: True
        m.publicou_neste_horario = lambda *a, **k: None

    def test_porta(self):
        _no_relogio(self.m, datetime(2026, 10, 20, 12, 10))
        self.assertIn("grade de builds",
                      self.m._vaga_do_tiktok("builds"))
        self.assertEqual("", self.m._vaga_do_tiktok("historias"))
        _no_relogio(self.m, datetime(2026, 10, 20, 21, 40))
        self.assertEqual("", self.m._vaga_do_tiktok("builds"))

    def test_reserva_fora_das_21_nao_posta(self):
        m = self.m
        m.RESERVA_LIGADA = True
        _no_relogio(m, datetime(2026, 10, 20, 15, 40))
        m.reserva_do_tiktok = lambda: self.fail("nem monta a fila")
        r = m.publicar_da_reserva()
        self.assertFalse(r["feito"])
        self.assertIn("grade de builds", r["motivo"])


class MisturaSoDeDueloTests(unittest.TestCase):
    def test_duelo_leva_tudo_nos_dois_destinos(self):
        m = _postar()
        cota = {"duelo": 4, "build": 3, "estreia": 1, "torneio": 0}
        for p in ("youtube", "tiktok"):
            self.assertEqual({"duelo": 8, "build": 0, "estreia": 0,
                              "torneio": 0}, m.cota_da_plataforma(cota, p))

    def test_build_so_sem_duelo(self):
        m = _postar()
        cota = m.cota_da_plataforma({"duelo": 4, "build": 3, "estreia": 1},
                                    "youtube")
        build = SimpleNamespace(id="g1:build:celular", origem="build",
                                quando=1.0)
        duelo = _duelo(2, quando=9.0)
        self.assertIs(duelo, m.escolher_por_cota([build, duelo], {}, cota))
        self.assertIs(build, m.escolher_por_cota([build], {}, cota))

    def test_consumo_duelo_tres_por_dia(self):
        """YouTube 3 horarios x 8/8 = 3; o TikTok (1 por dia) leva o que o
        YouTube ja subiu: o ritmo do formato e o maior, 3. O resto, 0."""
        _relogio_em(self, OUTUBRO)
        m = _postar()
        ritmo = m.consumo_por_formato({"duelo": 4, "build": 3, "estreia": 1})
        self.assertAlmostEqual(3.0, ritmo["duelo"])
        self.assertNotIn("build", ritmo)
        self.assertNotIn("estreia", ritmo)

    def test_consumo_duelo_oito_por_dia_desde_27_10(self):
        """YouTube 8 horarios x 8/8 = 8 duelos por dia (o TikTok, 1, leva um
        deles); build e estreia seguem em zero. 8 x 7 = 56 por semana. A
        mistura do YouTube continua toda de duelo: os 8 horarios do dia saem
        de 8 duelos diferentes, nenhum build, nenhuma estreia."""
        _relogio_em(self, OITO)
        m = _postar()
        ritmo = m.consumo_por_formato({"duelo": 4, "build": 3, "estreia": 1})
        self.assertAlmostEqual(8.0, ritmo["duelo"])
        self.assertNotIn("build", ritmo)
        self.assertNotIn("estreia", ritmo)
        cota = m.cota_da_plataforma({"duelo": 4, "build": 3, "estreia": 1},
                                    "youtube")
        self.assertEqual(8, cota["duelo"])
        self.assertEqual(0, cota.get("build", 0) + cota.get("estreia", 0))
        build = SimpleNamespace(id="g1:build:celular", origem="build",
                                quando=0.5)
        pool = [build] + [_duelo(n, quando=float(n)) for n in range(1, 17)]
        saidos = []
        for _ in range(8):
            alvo = m.escolher_por_cota(pool, {}, cota)
            saidos.append(alvo.id)
            pool = [v for v in pool if v.id != alvo.id]
        self.assertEqual(8, len(set(saidos)))
        self.assertTrue(all(i.split(":")[1] == "duelo" for i in saidos))

    def test_a_geracao_conta_igual(self):
        _relogio_em(self, OUTUBRO)
        from builds.pipeline import noite
        m = _postar()
        self.assertEqual(m.TROCAS_NA_COTA, noite.TROCAS_NA_COTA)
        consumo = noite.consumo_por_dia({"grade": {"mistura": {
            "duelo": 4, "build": 3, "estreia": 1, "torneio": 0}}})
        self.assertEqual({"duelo": 3.0, "build": 0.0, "estreia": 0.0},
                         consumo)


class ConfrontosDiferentesTests(unittest.TestCase):
    """"So confrontos diferentes": o par de classe nao repete na semana."""

    def setUp(self):
        self.m = m = _postar()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)
        m._CONFRONTOS.clear()
        original = m.confronto_da_fonte

        def da_pasta(fonte_id, pasta=None):
            return original(fonte_id, self.pasta / str(fonte_id))
        m.confronto_da_fonte = da_pasta

    def _ficha(self, n, a, b):
        pasta = self.pasta / f"duelo_{n:05d}"
        pasta.mkdir()
        (pasta / "fight.json").write_text(json.dumps({"luta": {
            "p1_ficha": {"classe": a}, "p2_ficha": {"classe": b}}}),
            encoding="utf-8")
        return _duelo(n)

    def test_chave_sem_ordem_e_com_a_arma_quando_ha(self):
        self._ficha(1, "Paladino (Sagrado)", "Mago (Arcano)")
        self._ficha(2, "Mago (Arcano)", "Paladino (Sagrado)")
        self.assertEqual("Mago (Arcano) x Paladino (Sagrado)",
                         self.m.confronto_da_fonte("duelo_00001"))
        self.assertEqual(self.m.confronto_da_fonte("duelo_00001"),
                         self.m.confronto_da_fonte("duelo_00002"))
        self.assertEqual("Mago/Arco", self.m._lado_do_confronto(
            {"classe": "Mago", "tipo_arma": "Arco"}))

    def test_caso_zero_sem_ficha_nao_sabe_e_nao_barra(self):
        self.assertEqual("", self.m.confronto_da_fonte("duelo_00099"))
        self.assertEqual("", self.m.confronto_da_fonte("generation_00001"))
        d = _duelo(99)
        self.assertEqual([d], self.m.com_confrontos_diferentes(
            [d], {"x"}, {"x"}))

    def test_camadas(self):
        m = self.m
        a = self._ficha(1, "Mago", "Ninja")
        b = self._ficha(2, "Mago", "Ninja")
        c = self._ficha(3, "Monge", "Ladino")
        build = SimpleNamespace(id="g:build:celular", origem="build")
        k_mn = m.confronto_da_fonte("duelo_00001")
        k_ml = m.confronto_da_fonte("duelo_00003")
        # Mago x Ninja ja saiu na semana: so o Monge x Ladino (e o build)
        self.assertEqual([c, build], m.com_confrontos_diferentes(
            [a, b, c, build], {k_mn}, set()))
        # os dois sairam na semana, so Mago x Ninja HOJE: o de outro dia
        self.assertEqual([c, build], m.com_confrontos_diferentes(
            [a, c, build], {k_mn, k_ml}, {k_mn}))
        # todos hoje: o confronto so repete se nao houver outro video
        self.assertEqual([build], m.com_confrontos_diferentes(
            [a, c, build], {k_mn, k_ml}, {k_mn, k_ml}))
        self.assertEqual([a, c], m.com_confrontos_diferentes(
            [a, c], {k_mn, k_ml}, {k_mn, k_ml}))
        # caso zero: nada no ar, nada muda
        self.assertEqual([a, b, c], m.com_confrontos_diferentes(
            [a, b, c], set(), set()))

    def test_confrontos_no_ar_por_destino_e_por_dia(self):
        m = self.m
        self._ficha(1, "Mago", "Ninja")
        self._ficha(2, "Monge", "Ladino")
        self._ficha(3, "Bardo", "Druida")
        linhas = [
            {"plataforma": "youtube", "origem": "duelo",
             "fonte_id": "duelo_00001", "quando": "2026-10-20T12:09:00",
             "url": "https://youtu.be/a", "publicado": True},
            {"plataforma": "youtube", "origem": "duelo",
             "fonte_id": "duelo_00002", "quando": "2026-10-16T12:09:00",
             "url": "https://youtu.be/b", "publicado": True},
            # fora da semana
            {"plataforma": "youtube", "origem": "duelo",
             "fonte_id": "duelo_00003", "quando": "2026-10-10T12:09:00",
             "url": "https://youtu.be/c", "publicado": True},
            # outro destino
            {"plataforma": "tiktok", "origem": "duelo",
             "fonte_id": "duelo_00003", "quando": "2026-10-20T21:40:00",
             "url": "publicado no TikTok", "publicado": True},
        ]
        m._saiu = lambda l: True
        semana, dia = m.confrontos_no_ar(linhas, "youtube",
                                         datetime(2026, 10, 20, 15, 40))
        self.assertEqual({"Mago x Ninja", "Ladino x Monge"}, semana)
        self.assertEqual({"Mago x Ninja"}, dia)
        self.assertEqual((set(), set()), m.confrontos_no_ar(
            [], "youtube", datetime(2026, 10, 20, 15, 40)))


class OitoPorDiaNaoSeTravaNasGuardasTests(unittest.TestCase):
    """8 duelos por dia contra o estoque de 24/10 (17 sobrando em 27/10, 26
    antes dos 9 de 24 a 26; 18 com confronto livre na semana, 23 confrontos
    distintos). As guardas de repeticao NAO barram duelo bom: a de confronto
    so ordena (semana, depois dia) e nunca troca um duelo por build.

    Conta de mao com 17 duelos de 12 confrontos (n % 12), do mais antigo:
    dia 1 sai n0..n7 (k0..k7, nenhum repete); dia 2 sai n8..n11 (k8..k11, os
    unicos livres da semana) e depois n12..n15 (k0..k3, ja no ar na semana mas
    nao hoje) = 8, 4 deles repetindo o confronto da semana, ZERO no mesmo dia,
    ZERO build; sobra n16."""

    def test_dois_dias_de_oito_sem_build_e_sem_repetir_no_dia(self):
        m = _postar()
        confronto = {}
        pool = []
        for n in range(17):
            v = _duelo(n, quando=float(n))
            confronto[v.id] = f"k{n % 12}"
            pool.append(v)
        build = SimpleNamespace(id="g1:build:celular", origem="build",
                                quando=-1.0)
        pool.append(build)
        m._confronto_do_video = lambda v: confronto.get(v.id, "")
        cota = m.cota_da_plataforma({"duelo": 4, "build": 3, "estreia": 1},
                                    "youtube")
        semana, saiu, repete_semana, repete_dia = set(), [], 0, 0
        for _dia_n in range(2):
            hoje = set()
            for _horario in range(8):
                fila = m.com_confrontos_diferentes(pool, semana, hoje)
                alvo = m.escolher_por_cota(list(fila), {}, cota)
                self.assertEqual("duelo", alvo.origem)
                k = confronto[alvo.id]
                repete_semana += k in semana
                repete_dia += k in hoje
                semana.add(k)
                hoje.add(k)
                saiu.append(alvo.id)
                pool = [v for v in pool if v.id != alvo.id]
        self.assertEqual(16, len(saiu))
        self.assertEqual(4, repete_semana)
        self.assertEqual(0, repete_dia)
        self.assertEqual(["duelo_00016:duelo:celular", "g1:build:celular"],
                         sorted(v.id for v in pool))

    def test_caso_zero_sem_duelo_o_horario_nao_fica_vazio_nem_repete(self):
        """Estoque de duelo ZERO: sai o build (cota zero = so quando ninguem
        mais quer), nao um duelo repetido nem horario em branco."""
        m = _postar()
        build = SimpleNamespace(id="g1:build:celular", origem="build",
                                quando=1.0)
        cota = m.cota_da_plataforma({"duelo": 4, "build": 3, "estreia": 1},
                                    "youtube")
        fila = m.com_confrontos_diferentes([build], set(), set())
        self.assertIs(build, m.escolher_por_cota(fila, {}, cota))
        self.assertIsNone(m.escolher_por_cota([], {}, cota))


class TiktokDosBuildsLevaOMaisNovoTests(unittest.TestCase):
    def test_o_mais_novo_do_youtube(self):
        """Um por dia contra tres: o TikTok leva o MAIS NOVO que o YouTube
        subiu (o das 21:37), e nao o mais velho da fila."""
        m = _postar()
        velho, meio, novo = _duelo(1, quando=1.0), _duelo(2, quando=2.0), \
            _duelo(3, quando=3.0)
        m.atrasados_no_tiktok = lambda **k: [velho, meio, novo]
        m._sem_confronto_repetido = lambda pool, plataforma: pool
        m._servidos_recentes = lambda **k: {}
        m.cota_da_grade = lambda config=None: {"duelo": 4, "build": 3,
                                               "estreia": 1}
        m._audio_mudo = lambda v: ""
        m._builds_prontos = lambda *a, **k: self.fail("com atraso nao vai "
                                                      "ao estoque novo")
        alvo, motivo = m._vez_do_tiktok_builds()
        self.assertIs(novo, alvo)
        self.assertEqual("", motivo)


class IdiomaDoUploadTests(unittest.TestCase):
    def test_corpo_da_api_em_ingles_so_nos_builds(self):
        from builds.publicar import youtube
        cfg = {"youtube": {"idioma_por_canal": {"builds": "en"}}}
        video = SimpleNamespace(titulo="Sword VS Dagger", hashtags=["#shorts"],
                                descricao_completa="d")
        corpo = youtube._corpo(video, cfg, "public", canal="builds")
        self.assertEqual("en", corpo["snippet"]["defaultLanguage"])
        self.assertEqual("en", corpo["snippet"]["defaultAudioLanguage"])
        corpo = youtube._corpo(video, cfg, "public", canal="historias")
        self.assertNotIn("defaultLanguage", corpo["snippet"])
        # caso zero: config sem a chave
        self.assertEqual("", youtube.idioma_do_canal("builds", {}))

    def test_o_config_do_repositorio_poe_os_builds_em_ingles(self):
        from builds.publicar import catalogo, youtube
        cfg = catalogo.carregar_config()
        self.assertEqual("en", youtube.idioma_do_canal("builds", cfg))
        self.assertEqual("", youtube.idioma_do_canal("historias", cfg))
        for formato, tags in cfg["hashtags"].items():
            for t in tags:
                self.assertNotIn(t, ("#luta", "#ia", "#aleatorio",
                                     "#torneio"), formato)

    def test_pelo_navegador_o_idioma_vai_depois_e_nunca_derruba(self):
        from builds.publicar import recuperar, youtube
        pedidos = []
        original = recuperar.definir_idioma
        self.addCleanup(setattr, recuperar, "definir_idioma", original)
        recuperar.definir_idioma = lambda vid, idioma, canal="builds": (
            pedidos.append((vid, idioma, canal)) or {"mudou": True})
        laudo = {}
        cfg = {"youtube": {"idioma_por_canal": {"builds": "en"}}}
        youtube._definir_idioma("abc", "builds", cfg, laudo, lambda t: None)
        self.assertEqual([("abc", "en", "builds")], pedidos)
        self.assertTrue(laudo["idioma"]["mudou"])

        def quebra(*a, **k):
            raise RuntimeError("sem rede")
        recuperar.definir_idioma = quebra
        laudo = {}
        youtube._definir_idioma("abc", "builds", cfg, laudo, lambda t: None)
        self.assertFalse(laudo["idioma"]["mudou"])
        # historias: nada
        laudo = {}
        youtube._definir_idioma("abc", "historias", cfg, laudo,
                                lambda t: None)
        self.assertEqual({}, laudo)

    def test_definir_idioma_devolve_o_snippet_inteiro(self):
        """O PUT de snippet substitui a parte inteira: titulo, descricao,
        categoria e tags voltam como estavam."""
        from builds.publicar import recuperar
        estado = {"snippet": {"title": "T", "description": "D",
                              "categoryId": "20", "tags": ["a"],
                              "channelId": "C"}}
        enviados = []
        nomes = ("_token", "_get", "conferir_o_canal")
        for nome in nomes:
            self.addCleanup(setattr, recuperar, nome, getattr(recuperar, nome))
        recuperar._token = lambda canal, **k: "tk"
        recuperar.conferir_o_canal = lambda canal, aberto: ""

        def get(token, caminho, **params):
            if caminho == "channels":
                return {"items": [{}]}
            return {"items": [{"snippet": dict(estado["snippet"])}]}
        recuperar._get = get

        class _Resp:
            status_code, ok, text = 200, True, ""

        import requests
        original_put = requests.put
        self.addCleanup(setattr, requests, "put", original_put)

        def put(url, **k):
            corpo = json.loads(k["data"])
            enviados.append(corpo)
            estado["snippet"].update(corpo["snippet"])
            return _Resp()
        requests.put = put
        r = recuperar.definir_idioma("v1", "en", canal="builds")
        self.assertTrue(r["mudou"])
        snippet = enviados[0]["snippet"]
        self.assertEqual({"title": "T", "description": "D", "categoryId": "20",
                          "tags": ["a"], "defaultLanguage": "en",
                          "defaultAudioLanguage": "en"}, snippet)
        # idempotente: a segunda vez nao manda nada
        recuperar.definir_idioma("v1", "en", canal="builds")
        self.assertEqual(1, len(enviados))


if __name__ == "__main__":
    unittest.main()
