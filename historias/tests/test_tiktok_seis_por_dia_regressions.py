# -*- coding: utf-8 -*-
"""TikTok com SEIS por dia e fila propria (decisao `tiktok-seis-por-dia`, 19/10).

O que a decisao pede, e o que cada teste prende:

- a grade do TikTok tem seis horarios, so de dia (09:37 12:07 15:37 17:57
  20:37 21:37), ~12 h sem postar a noite; o YouTube continua com os dez;
- com seis contra dez, o TikTok NAO pode levar "o video da rodada": os
  quatro horarios so do YouTube deixam quatro partes por dia fora dele. Ele
  tem FILA PROPRIA — o que saiu no YouTube e falta ao TikTok, na ordem —, e
  nunca pula parte nem poe a N+1 antes da N;
- a recuperacao do TikTok, que era UM EXTRA POR RODADA, so tapa buraco num
  horario da grade dele: sem isto ela postaria nos quatro horarios do
  YouTube e o "seis por dia" seria dez.

Medido no ledger em 19/10/2026 13:55: zero atrasados no TikTok nos dois
canais (o TikTok estava em dia), e nesta semana simulada (10 partes por dia
no YouTube) o TikTok fecha cada dia com 6 posts, 4 partes a mais na fila
dele por dia, e nenhuma parte fora de ordem.
"""
from __future__ import annotations

import importlib.util
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_seis", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    modulo._linha = lambda *a, **k: None
    return modulo


class _Parte:
    def __init__(self, fonte, parte, partes=6):
        self.fonte_id = fonte
        self.parte = parte
        self.partes = partes
        self.id = f"{fonte}:celular:p{parte:02d}"
        self.titulo = f"{fonte} (Parte {parte}/{partes})"
        self.perfil = "celular"
        self.descricao = "Parte {} de {}".format(parte, partes)
        self.quando = 0.0


def _linha(alvo, plataforma, quando):
    return {"video_id": alvo.id, "fonte_id": alvo.fonte_id,
            "parte": alvo.parte, "plataforma": plataforma,
            "titulo": alvo.titulo, "quando": quando,
            "url": ("publicado no TikTok" if plataforma == "tiktok"
                    else "https://youtu.be/x"), "publicado": True}


class GradeDeSeisTests(unittest.TestCase):
    def test_seis_horarios_de_dia_no_tiktok_e_dez_no_youtube(self):
        from builds import grade
        self.assertEqual((9, 12, 15, 17, 20, 21), grade.HORAS_DO_TIKTOK)
        self.assertEqual(["09:37", "12:07", "15:37", "17:57", "20:37",
                          "21:37"], grade.horarios("tiktok"))
        self.assertEqual(10, len(grade.horas_da_plataforma("youtube")))
        for h in (0, 6, 22, 23):
            self.assertFalse(grade.publica_em("tiktok", h), h)
            self.assertTrue(grade.publica_em("youtube", h), h)
        self.assertEqual(6, grade.META_DIARIA_POR_PLATAFORMA["tiktok"])
        self.assertEqual(10, grade.META_DIARIA_POR_PLATAFORMA["youtube"])
        # historias 10 + 6; builds 3 + 1 desde 20/10/2026 (grade do canal,
        # `test_grade_dos_duelos_regressions`)
        self.assertEqual(10 + 6 + 3 + 1, grade.META_DIARIA_TOTAL)

    def test_doze_horas_sem_postar_a_noite(self):
        """21:37 -> 09:37 = 12 h: o "~12 h sem postar" da decisao."""
        from builds import grade
        ultimo, primeiro = grade.HORAS_DO_TIKTOK[-1], grade.HORAS_DO_TIKTOK[0]
        pausa = ((primeiro * 60 + grade.minuto(primeiro))
                 - (ultimo * 60 + grade.minuto(ultimo))) % (24 * 60)
        self.assertEqual(12 * 60, pausa)

    def test_o_dia_de_grade_do_tiktok_abre_as_0937(self):
        """O maior buraco da grade dele e a noite: o dia abre 09:37 e fecha
        21:37. Conta de mao: 22:40 -> (dia, 21); 08:00 do dia seguinte ->
        (dia, 21); 09:40 -> (dia seguinte, 9)."""
        from builds.publicar import conferencia
        self.assertEqual((9, 21), conferencia.abertura_e_fechamento("tiktok"))
        self.assertEqual((date(2026, 10, 20), 21), conferencia.chave_do_horario(
            datetime(2026, 10, 20, 22, 40), "tiktok"))
        self.assertEqual((date(2026, 10, 20), 21), conferencia.chave_do_horario(
            datetime(2026, 10, 21, 8, 0), "tiktok"))
        self.assertEqual((date(2026, 10, 21), 9), conferencia.chave_do_horario(
            datetime(2026, 10, 21, 9, 40), "tiktok"))
        # o YouTube nao mudou: 22:40 e o horario das 22:37
        self.assertEqual((date(2026, 10, 20), 22), conferencia.chave_do_horario(
            datetime(2026, 10, 20, 22, 40), "youtube"))

    def test_rodada_fora_da_grade_do_tiktok(self):
        m = _postar()
        self.assertFalse(m._tiktok_neste_horario(datetime(2026, 10, 20, 22, 40)))
        self.assertFalse(m._tiktok_neste_horario(datetime(2026, 10, 20, 0, 40)))
        self.assertFalse(m._tiktok_neste_horario(datetime(2026, 10, 20, 6, 40)))
        self.assertTrue(m._tiktok_neste_horario(datetime(2026, 10, 20, 21, 40)))
        # a rodada das 17:57 que cruza a hora continua sendo do TikTok
        self.assertTrue(m._tiktok_neste_horario(datetime(2026, 10, 20, 18, 3)))


class DatasDoTesteTests(unittest.TestCase):
    def test_le_as_datas(self):
        from builds import grade
        cfg = {"testes": {"tiktok_6_por_dia": {"inicio": "2026-10-20",
                                               "fim": "2026-10-26"}}}
        self.assertEqual({"inicio": date(2026, 10, 20), "fim": date(2026, 10, 26)},
                         grade.teste_do_tiktok(cfg))

    def test_zero_e_torto_sao_none(self):
        """Sem bloco, data torta ou fim antes do inicio: `None` — "nao sei"
        nao inventa teste."""
        from builds import grade
        self.assertIsNone(grade.teste_do_tiktok({}))
        self.assertIsNone(grade.teste_do_tiktok({"testes": {}}))
        self.assertIsNone(grade.teste_do_tiktok(
            {"testes": {"tiktok_6_por_dia": {"inicio": "amanha", "fim": "x"}}}))
        self.assertIsNone(grade.teste_do_tiktok(
            {"testes": {"tiktok_6_por_dia": {"inicio": "2026-10-26",
                                             "fim": "2026-10-20"}}}))

    def test_o_config_do_repositorio_tem_as_datas(self):
        from builds import grade
        t = grade.teste_do_tiktok()
        self.assertIsNotNone(t)
        self.assertEqual(6, (t["fim"] - t["inicio"]).days, "uma semana")


class PortaDoTiktokTests(unittest.TestCase):
    """`_recusa_do_tiktok`: a guarda no FUNIL, para todo caminho."""

    def setUp(self):
        self.m = m = _postar()
        self.ledger = []
        self.marcados = set()
        m._tiktok_neste_horario = lambda agora=None: True
        # A grade dos builds (20/10/2026) nao e o assunto aqui: sem relogio.
        m._fora_da_grade_do_canal = lambda *a, **k: ""
        m._publicados_do_canal = lambda canal: list(self.ledger)
        m.a_conferir_no_tiktok = lambda canal="historias", p="tiktok": set(
            self.marcados)

    def test_tudo_certo_pode(self):
        self.assertEqual("", self.m._recusa_do_tiktok("historias",
                                                      _Parte("h1", 1)))

    def test_fora_da_grade_recusa(self):
        self.m._tiktok_neste_horario = lambda agora=None: False
        self.assertIn("grade", self.m._recusa_do_tiktok("historias",
                                                        _Parte("h1", 1)))

    def test_horario_ja_pago_recusa(self):
        agora = datetime.now()
        self.ledger.append(_linha(_Parte("h9", 1), "tiktok",
                                  agora.isoformat(timespec="seconds")))
        self.assertIn("ja saiu neste horario",
                      self.m._recusa_do_tiktok("historias", _Parte("h1", 1)))

    def test_ledger_ilegivel_recusa(self):
        def quebra(canal):
            raise self.m.LedgerIlegivel("preso")
        self.m._publicados_do_canal = quebra
        self.assertTrue(self.m._recusa_do_tiktok("historias", _Parte("h1", 1)))

    def test_a_conferir_recusa_e_lista_ilegivel_tambem(self):
        self.marcados.add("h1:celular:p01")
        self.assertIn("a conferir", self.m._recusa_do_tiktok(
            "historias", _Parte("h1", 1)))

        def quebra(canal="historias", p="tiktok"):
            raise OSError("trancado")
        self.m.a_conferir_no_tiktok = quebra
        self.assertIn("conferencia", self.m._recusa_do_tiktok(
            "historias", _Parte("h2", 1)))

    def test_parte_n_mais_1_nunca_antes_da_n_no_tiktok(self):
        self.ledger.append(_linha(_Parte("h1", 1), "tiktok", "2026-10-01T09:40:00"))
        self.ledger.append(_linha(_Parte("h1", 2), "youtube", "2026-10-01T12:10:00"))
        motivo = self.m._recusa_do_tiktok("historias", _Parte("h1", 3))
        self.assertIn("parte 2", motivo)
        self.assertEqual("", self.m._recusa_do_tiktok("historias", _Parte("h1", 2)))
        # builds nao tem ordem de serie
        self.assertEqual("", self.m._recusa_do_tiktok("builds", _Parte("g1", 3)))

    def test_o_funil_recusa_e_nao_publica(self):
        """`_tiktok_das_historias` passa pela porta: fora da grade, nada sobe e
        a falha diz que e recusa (nao conta tentativa)."""
        from contos.publicar import catalogo, serie
        subiu = []
        originais = (catalogo.publicar_tiktok, serie.ja_publicado)
        catalogo.publicar_tiktok = lambda *a, **k: subiu.append(1) or "x"
        serie.ja_publicado = lambda *a, **k: False
        self.addCleanup(setattr, catalogo, "publicar_tiktok", originais[0])
        self.addCleanup(setattr, serie, "ja_publicado", originais[1])
        self.m._tiktok_neste_horario = lambda agora=None: False
        falha = {}
        self.assertEqual("", self.m._tiktok_das_historias(_Parte("h1", 1), falha))
        self.assertEqual([], subiu)
        self.assertTrue(falha.get("recusa"))


class RecuperacaoSoTapaBuracoTests(unittest.TestCase):
    def setUp(self):
        self.m = m = _postar()
        self.chamadas = []
        m.atrasados_no_tiktok = lambda **k: [_Parte("h1", 2)]
        m._tiktok_das_historias = lambda alvo, falha=None: (
            self.chamadas.append(alvo.id) or "publicado no TikTok")
        m._tiktok_dos_builds = m._tiktok_das_historias
        m._anotar_falha_no_tiktok = lambda *a: self.fail("nao conta falha")

    def test_fora_da_grade_do_tiktok_nao_posta(self):
        """Era o furo: a recuperacao nao olhava a grade e postaria nos quatro
        horarios so do YouTube (22:37, 23:37, 00:37, 06:37)."""
        self.m._tiktok_neste_horario = lambda agora=None: False
        r = self.m.recuperar_no_tiktok(canal="historias")
        self.assertFalse(r["feito"])
        self.assertEqual([], self.chamadas)

    def test_horario_do_tiktok_ja_pago_nao_posta(self):
        self.m._tiktok_neste_horario = lambda agora=None: True
        self.m.publicou_neste_horario = lambda *a, **k: {"video_id": "x"}
        r = self.m.recuperar_no_tiktok(canal="builds")
        self.assertFalse(r["feito"])
        self.assertEqual([], self.chamadas)

    def test_horario_do_tiktok_vazio_tapa(self):
        self.m._tiktok_neste_horario = lambda agora=None: True
        self.m.publicou_neste_horario = lambda *a, **k: None
        self.m._retida_chegou_ao_tiktok = lambda *a: None
        self.m._esquecer_falhas_no_tiktok = lambda *a: None
        r = self.m.recuperar_no_tiktok(canal="historias")
        self.assertTrue(r["feito"])
        self.assertEqual(["h1:celular:p02"], self.chamadas)


class FilaPropriaDasHistoriasTests(unittest.TestCase):
    def setUp(self):
        self.m = m = _postar()
        self.ledger = []
        self.catalogo = {}
        m._fontes_de_atraso = lambda canal: (list(self.ledger), dict(self.catalogo))
        m.desistencias_do_tiktok = lambda canal="historias": set()
        m.a_conferir_no_tiktok = lambda canal="historias", p="tiktok": set()

    def _tem(self, *partes):
        for p in partes:
            self.catalogo[p.id] = p
        return partes

    def test_o_atrasado_vem_antes_da_parte_nova(self):
        """O YouTube subiu a p02 num horario so dele; no horario seguinte do
        TikTok, a vez e a p02 — nao a parte nova da rodada."""
        p1, p2 = self._tem(_Parte("h1", 1), _Parte("h1", 2))
        nova, = self._tem(_Parte("h2", 1))
        self.ledger += [_linha(p1, "youtube", "2026-10-01T21:40:00"),
                        _linha(p1, "tiktok", "2026-10-01T21:42:00"),
                        _linha(p2, "youtube", "2026-10-01T22:40:00")]
        alvo, motivo = self.m._vez_do_tiktok_historias(nova)
        self.assertEqual(p2.id, alvo.id)
        self.assertEqual("", motivo)

    def test_em_dia_leva_a_parte_nova(self):
        nova, = self._tem(_Parte("h2", 1))
        alvo, _motivo = self.m._vez_do_tiktok_historias(nova)
        self.assertEqual(nova.id, alvo.id)

    def test_parte_nova_sem_a_anterior_no_tiktok_nao_vai(self):
        """A p03 nova com a p02 so no YouTube e desistida no TikTok: a p03 nao
        sai no TikTok (nunca pula parte)."""
        p1, p2, p3 = self._tem(_Parte("h1", 1), _Parte("h1", 2), _Parte("h1", 3))
        self.ledger += [_linha(p1, "youtube", "2026-10-01T09:40:00"),
                        _linha(p1, "tiktok", "2026-10-01T09:42:00"),
                        _linha(p2, "youtube", "2026-10-01T12:10:00")]
        self.m.desistencias_do_tiktok = lambda canal="historias": {p2.id}
        alvo, motivo = self.m._vez_do_tiktok_historias(p3)
        self.assertIsNone(alvo)
        self.assertTrue(motivo)

    def test_zero_estoque_vazio(self):
        alvo, motivo = self.m._vez_do_tiktok_historias(None)
        self.assertIsNone(alvo)
        self.assertIn("vazia", motivo)

    def test_lista_a_conferir_ilegivel_nao_leva_nada(self):
        def quebra(canal="historias", p="tiktok"):
            raise OSError("trancado")
        self.m.a_conferir_no_tiktok = quebra
        nova, = self._tem(_Parte("h2", 1))
        alvo, motivo = self.m._vez_do_tiktok_historias(nova)
        self.assertIsNone(alvo)
        self.assertIn("nao consegui", motivo)


class SemanaSimuladaTests(unittest.TestCase):
    """Uma semana inteira, a seco: o YouTube sobe a parte seguinte da fila em
    cada um dos dez horarios; o TikTok leva a vez dele nos seis. Conta de
    mao: 70 partes no YouTube, 42 no TikTok (6 por dia), 28 na fila do TikTok
    no fim; cada parte do TikTok com a anterior ja la; nenhuma repetida."""

    def test_seis_por_dia_em_ordem_e_sem_pular(self):
        from collections import Counter
        from builds import grade
        from builds.publicar import conferencia
        m = _postar()
        ledger, catalogo = [], {}
        series = [f"h{n:02d}" for n in range(1, 16)]
        for f in series:
            for p in range(1, 7):
                v = _Parte(f, p)
                catalogo[v.id] = v
        proxima = {f: 1 for f in series}
        no_dia = Counter()

        def youtube_da_vez(quando):
            """A fila do YouTube, resumida: a primeira serie com parte e com
            menos de 2 saidas no dia de grade (o teto), na ordem."""
            dia = conferencia.chave_do_horario(quando, "youtube")[0]
            for f in series:
                if proxima[f] <= 6 and no_dia[(f, dia)] < 2:
                    no_dia[(f, dia)] += 1
                    proxima[f] += 1
                    return catalogo[f"{f}:celular:p{proxima[f] - 1:02d}"]
            return None
        m._fontes_de_atraso = lambda canal: (list(ledger), dict(catalogo))
        m.desistencias_do_tiktok = lambda canal="historias": set()
        m.a_conferir_no_tiktok = lambda canal="historias", p="tiktok": set()
        relogio = [datetime(2026, 10, 20, 9, 37)]
        cheias = m._fontes_cheias_hoje
        m._fontes_cheias_hoje = (lambda pub, plataforma="tiktok", agora=None:
                                 cheias(pub, plataforma, relogio[0]))
        tiktok_por_dia = {}
        for dia in range(7):
            base = datetime(2026, 10, 20) + timedelta(days=dia)
            for h, mi in grade.GRADE:
                quando = base.replace(hour=h, minute=mi) + timedelta(minutes=3)
                relogio[0] = quando
                alvo = youtube_da_vez(quando)
                self.assertIsNotNone(alvo, quando)
                ledger.append(_linha(alvo, "youtube", quando.isoformat()))
                if not grade.publica_em("tiktok", h):
                    continue
                tk, _motivo = m._vez_do_tiktok_historias(alvo)
                self.assertIsNotNone(tk, quando)
                faltam = [n for n in range(1, tk.parte)
                          if not any(l["plataforma"] == "tiktok"
                                     and l["fonte_id"] == tk.fonte_id
                                     and l["parte"] == n for l in ledger)]
                self.assertEqual([], faltam, f"{tk.id} fora de ordem")
                self.assertFalse(any(l["plataforma"] == "tiktok"
                                     and l["video_id"] == tk.id for l in ledger),
                                 f"{tk.id} repetida")
                ledger.append(_linha(tk, "tiktok",
                                     (quando + timedelta(minutes=2)).isoformat()))
                tiktok_por_dia[base.date()] = tiktok_por_dia.get(base.date(), 0) + 1
        self.assertEqual([6] * 7, list(tiktok_por_dia.values()))
        no_youtube = [l for l in ledger if l["plataforma"] == "youtube"]
        no_tiktok = [l for l in ledger if l["plataforma"] == "tiktok"]
        self.assertEqual((70, 42), (len(no_youtube), len(no_tiktok)))
        # nunca pula: no TikTok, cada serie e um prefixo da do YouTube
        for f in series:
            partes = sorted(l["parte"] for l in no_tiktok if l["fonte_id"] == f)
            self.assertEqual(list(range(1, len(partes) + 1)), partes, f)


if __name__ == "__main__":
    unittest.main()
