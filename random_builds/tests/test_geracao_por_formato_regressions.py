# -*- coding: utf-8 -*-
"""A geracao decide POR FORMATO, nao pelo total do canal (19/10/2026).

Medido nos diarios `outputs/_logs/gerar_*.txt` de 13 a 19/10/2026: 14 duelos
em 7 dias (todos no dia 19), 39 roletas, 38 estreias. O estoque de duelos da
publicacao caiu de 43 (13/10) para 13 (19/10, 01h) sem a geracao fazer um so,
porque o gatilho era o TOTAL: as estreias paradas (26 -> 54; o YouTube nao
posta mais estreia) enchiam o piso de 20 da reposicao e o alvo do lote. O que
este arquivo trava, sempre com relogio congelado e dubles:

  - caso ZERO: sem duelo no estoque, a proxima rodada faz DUELO primeiro, com
    50 estreias e builds sobrando;
  - estreia parada nao conta para o YouTube (nem no estoque zero da noite);
  - o consumo de cada formato e o da publicacao (em 19/10 duelo 6,25, build
    3,75, estreia 0,75 por dia; desde 20/10, canal de duelos, duelo 3 e o
    resto 0) e a troca e a mesma do `postar.py`;
  - a ordem e refeita a cada passo: a roleta nao come a rodada do duelo;
  - a estreia so vira video com estreias em falta, e a luta continua gravada;
  - nada pesado com o League of Legends aberto, menos no estoque zero.
"""
from __future__ import annotations

import os
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from builds.pipeline import noite

COTA = {"duelo": 4, "build": 3, "estreia": 1, "torneio": 0}
PUB = {"grade": {"mistura": dict(COTA)}}

SEG = datetime(2026, 10, 19)        # segunda (dia de lote)
QUI = datetime(2026, 10, 22)        # quinta (reposicao)
SEG2 = datetime(2026, 10, 26)       # segunda, ja com a grade dos duelos


class _MisturaDe19De10:
    """A mistura e a grade de 19/10 (YouTube 5/3/0 nos 10 horarios, TikTok
    4/3/1 nos 6), para os testes do MECANISMO da roleta: desde 20/10/2026 a
    publicacao nao pede roleta (build e estreia de cota zero), mas a ordem
    por passo e a estreia so abaixo da meta continuam no codigo."""

    def _mistura_de_19_10(self):
        from builds import grade
        for alvo, valor in (
                ("TROCAS_NA_COTA", {"youtube": {"estreia": "duelo"}}),
                ("_horas_dos_builds",
                 lambda g, plataforma, quando=None:
                 grade.horas_da_plataforma(plataforma))):
            patcher = mock.patch.object(noite, alvo, valor)
            patcher.start()
            self.addCleanup(patcher.stop)

# Guardadas na coleta: outros modulos trocam estas por bombas no
# `setUpModule`, e no pytest a troca pode vazar.
_BUILD_DE_VERDADE = noite._build_de_verdade
_JOGO_ABERTO = noite.jogo_aberto


def _as(dia, h, m):
    return dia.replace(hour=h, minute=m, second=0, microsecond=0)


def _fixar_a_grade(caso, dia):
    """Fixa o DIA que `grade.tabela_do_canal(None)` (o relogio) enxerga: o
    consumo e o piso leem a tabela de hoje, que mudou em 27/10/2026 (3 -> 8
    duelos por dia). Sem isto o teste que e sobre OUTRA coisa quebra sozinho
    no dia da troca."""
    from builds import grade
    original = grade.tabela_do_canal
    caso.addCleanup(setattr, grade, "tabela_do_canal", original)
    grade.tabela_do_canal = lambda quando=None: original(
        dia if quando is None else quando)


def _contagem(duelo=0, build=0, estreia=0):
    return {"total": duelo + build + estreia, "duelo": duelo, "build": build,
            "estreia": estreia, "torneio": 0, "fonte": "duble"}


class _Relogio:
    def __init__(self, inicio):
        self.agora = inicio

    def __call__(self):
        return self.agora

    def andar(self, minutos):
        self.agora += timedelta(minutes=minutos)


class _Base(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = noite.carregar()
        trocas = (("LOGS", Path(self.tmp.name)),
                  ("TRAVA", f"teste_formato_{os.getpid()}"),
                  ("cota", lambda *a, **k: dict(COTA)),
                  ("builds_em_preparo", lambda *a, **k: []),
                  ("jogo_aberto", lambda *a, **k: None),
                  ("_livre_gb", lambda caminho: 100.0),
                  ("_duelo_de_verdade", mock.Mock(side_effect=AssertionError(
                      "duelo de verdade"))),
                  ("_worker_de_verdade", mock.Mock(side_effect=AssertionError(
                      "worker de verdade"))),
                  ("contar_estoque", mock.Mock(side_effect=AssertionError(
                      "passe a contagem"))))
        for alvo, valor in trocas:
            patcher = mock.patch.object(noite, alvo, valor)
            patcher.start()
            self.addCleanup(patcher.stop)
        pausa = mock.patch("builds.identity.controle.pausado_para",
                           return_value=False)
        pausa.start()
        self.addCleanup(pausa.stop)
        registrar = mock.patch.object(noite, "_registrar")
        registrar.start()
        self.addCleanup(registrar.stop)

    def _rodar(self, relogio, contagem, *, gerar_build="duble", config=None,
               jogo=None, drenar=None, jobs=(), proximo=None, **kw):
        self.ordem = []

        def gerar_duelo():
            relogio.andar(4.5)                 # medido: 4,35-5,0 min (19/10)
            self.ordem.append("duelo")
            return Path(f"duelo_{len(self.ordem):05d}")

        def gerar_build_padrao():
            relogio.andar(26)                  # medido: 24,9-28,9 min (19/10)
            self.ordem.append("build")
            return Path(f"generation_{len(self.ordem):05d}")

        lista = list(jobs)
        return noite.rodar(config=config or self.config, relogio=relogio,
                           contagem=contagem, gerar_duelo=gerar_duelo,
                           gerar_build=(gerar_build_padrao
                                        if gerar_build == "duble"
                                        else gerar_build),
                           jobs=lambda: list(lista),
                           drenar_worker=drenar or (lambda **k: 0),
                           proximo=proximo or (lambda excluir=(): None),
                           tela=None, jogo=jogo, **kw)


# ================================================================ caso ZERO
class EstoqueDeDuelosZerado(_Base):

    def test_reposicao_com_zero_duelo_faz_duelo_primeiro(self):
        # O retrato de 19/10 sem os duelos: builds e estreias sobrando.
        relogio = _Relogio(_as(QUI, 10, 2))
        resultado = self._rodar(relogio, _contagem(duelo=0, build=10,
                                                   estreia=52))
        self.assertEqual("reposicao", resultado["modo"])
        self.assertTrue(resultado["plano"]["criar"])
        self.assertEqual("duelo", self.ordem[0])
        # e so duelo: builds 10 >= piso 8
        self.assertEqual({"duelo"}, set(self.ordem))
        self.assertGreaterEqual(len(resultado["duelos"]), 8)

    def test_lote_com_zero_duelo_faz_duelo_primeiro(self):
        relogio = _Relogio(_as(SEG, 7, 2))
        resultado = self._rodar(relogio, _contagem(duelo=0, build=10,
                                                   estreia=52))
        self.assertEqual("lote", resultado["modo"])
        self.assertEqual("duelo", self.ordem[0])

    def test_zero_e_zero_empate_vai_ao_duelo(self):
        relogio = _Relogio(_as(QUI, 10, 2))
        self._rodar(relogio, _contagem())
        self.assertEqual("duelo", self.ordem[0])

    def test_caso_zero_o_total_antigo_nao_criava(self):
        _fixar_a_grade(self, QUI)                    # 22/10: a grade de tres
        # A conta antiga (o total contra o piso de 20) com o mesmo estoque:
        # 0 + 10 + 52 = 62 >= 20 -> "so o worker". A nova cria.
        contagem = _contagem(duelo=0, build=10, estreia=52)
        self.assertGreaterEqual(contagem["total"],
                                noite.piso_de_reposicao(self.config))
        plano = noite.planejar(self.config, _as(QUI, 10, 2),
                               contagem=contagem, config_publicacao=PUB)
        self.assertTrue(plano["criar"])
        # Piso do duelo: 4 dias x 3 por dia (20/10/2026, canal de duelos) = 12
        # (era 4 x 6,25 = 25).
        self.assertEqual(12, plano["metas"]["duelo"])
        self.assertEqual(12, plano["faltas"]["duelo"])

    def test_noite_sem_duelo_nem_build_libera_mesmo_com_estreias(self):
        # 23:02: fora da janela. 52 estreias nao seguram o YouTube.
        relogio = _Relogio(_as(QUI, 23, 2))
        resultado = self._rodar(relogio, _contagem(estreia=52))
        self.assertEqual("zero", resultado["modo"])
        self.assertEqual("duelo", self.ordem[0])

    def test_noite_com_build_nao_faz_barulho(self):
        relogio = _Relogio(_as(QUI, 23, 2))
        resultado = self._rodar(relogio, _contagem(build=4, estreia=52))
        self.assertEqual("noite", resultado["modo"])
        self.assertEqual([], self.ordem)


# ============================================================ o consumo
class OConsumoEDaPublicacao(unittest.TestCase):

    # Desde 20/10/2026 (docs/PLANO.md, canal de duelos): YouTube dos builds
    # 3 horarios, TikTok 1, as duas misturas so com duelo (8/8). Em 19/10
    # eram duelo 6,25, build 3,75, estreia 0,75 e pisos 25, 8, 2.
    # DESDE 27/10/2026 (`publicacao/semana-2-volume`) sao 8 horarios no
    # YouTube: duelo 8, piso 4 x 8 = 32 (ver os testes `_oito_` abaixo).
    # Os testes sem data leem `grade.tabela_do_canal(None)`, o RELOGIO: sem
    # fixar o dia eles davam 3 em 24/10 e 8 em 27/10, sozinhos.
    def setUp(self):
        from builds import grade
        original = grade.tabela_do_canal
        self.addCleanup(setattr, grade, "tabela_do_canal", original)
        self.dia = SEG2 - timedelta(days=5)          # 21/10, a grade de tres
        grade.tabela_do_canal = lambda quando=None: original(
            self.dia if quando is None else quando)

    def test_consumo_por_dia(self):
        consumo = noite.consumo_por_dia(PUB)
        self.assertEqual(3.0, consumo["duelo"])      # 3 x 8/8 (YouTube)
        self.assertEqual(0.0, consumo["build"])      # cota zero
        self.assertEqual(0.0, consumo["estreia"])    # cota zero

    def test_pisos_por_formato(self):
        config = noite.carregar()
        self.assertEqual(
            (12, 0, 0),
            tuple(noite.piso_do_formato(f, config, PUB)
                  for f in ("duelo", "build", "estreia")))

    def test_troca_do_youtube_e_a_do_postar(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("_postar_formato",
                                                      noite.POSTAR)
        postar = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(postar)
        self.assertEqual(postar.TROCAS_NA_COTA, noite.TROCAS_NA_COTA)
        for plataforma in ("youtube", "tiktok"):
            self.assertEqual(postar.cota_da_plataforma(COTA, plataforma),
                             noite.cota_da_plataforma(COTA, plataforma))

    def test_metas_do_lote_de_segunda(self):
        """Segunda 26/10 07:02 -> 02/11 07:00 (a segunda ja na grade de
        oito): 26/10 tem 3 (09:37, 17:57, 21:37), de 27/10 a 01/11 sao 6 dias
        x 8 = 48 e 02/11 ainda tem o 06:37 = 52 duelos, + o piso 32 (4 dias x
        8: a geracao olha a grade a frente) = 84 (em 19/10 eram 69/35/8)."""
        config = noite.carregar()
        metas = noite.metas_do_plano(config, _as(SEG2, 7, 2), "lote", PUB)
        self.assertEqual({"duelo": 84, "build": 0, "estreia": 0}, metas)

    def test_oito_duelos_por_dia_desde_27_10(self):
        """YouTube 8 horarios x 8/8 = 8 duelos por dia; o piso de 4 dias (a
        decisao do lote) e 32. Fixado em 28/10 e em 01/11 (o fim do horario
        de verao nao muda a conta)."""
        for dia in (SEG2 + timedelta(days=2), SEG2 + timedelta(days=6)):
            self.dia = dia
            config = noite.carregar()
            self.assertEqual(8.0, noite.consumo_por_dia(PUB)["duelo"])
            self.assertEqual(0.0, noite.consumo_por_dia(PUB)["build"])
            self.assertEqual(
                (32, 0, 0),
                tuple(noite.piso_do_formato(f, config, PUB)
                      for f in ("duelo", "build", "estreia")))

    def test_horarios_do_tiktok(self):
        # segunda 07:02 -> segunda seguinte 07:00, na grade DOS BUILDS: 1 por
        # dia no TikTok (o mesmo antes e depois de 27/10), no YouTube 3 por
        # dia ate 26/10 e 8 desde 27/10 (antes de 20/10: 6 e 10, os da
        # plataforma). Segunda 26/10: 3 + 6 x 8 + o 06:37 de 02/11 = 52.
        self.assertEqual(7, noite.postagens_da_plataforma(
            _as(SEG2, 7, 2), _as(SEG2 + timedelta(days=7), 7, 0), "tiktok"))
        self.assertEqual(52, noite.postagens_da_plataforma(
            _as(SEG2, 7, 2), _as(SEG2 + timedelta(days=7), 7, 0), "youtube"))
        self.assertEqual(42, noite.postagens_da_plataforma(
            _as(SEG - timedelta(days=7), 7, 2), _as(SEG, 7, 0), "tiktok"))


# ============================================================ a ordem
class AOrdemEPorPasso(_Base, _MisturaDe19De10):

    def setUp(self):
        super().setUp()
        self._mistura_de_19_10()

    def test_a_roleta_nao_come_a_rodada(self):
        # Antes de 19/10 cada formato ia ate o fim do alvo dele: com a build
        # com menos dias, as 3 roletas da rodada saiam em fila e o duelo so
        # depois (no 19/10 as 10:03 e as 12:34 a roleta levou a rodada
        # inteira). Agora a ordem e refeita a cada passo: builds 11 (2,9
        # dias) x duelos 20 (3,2 dias) -> uma roleta (+2 = 13, 3,5 dias) e
        # o duelo passa a frente.
        relogio = _Relogio(_as(SEG, 10, 3))
        self._rodar(relogio, _contagem(duelo=20, build=11, estreia=52))
        self.assertEqual(["build", "duelo"], self.ordem[:2])
        self.assertEqual(1, self.ordem.count("build"))

    def test_cada_roleta_conta_dois_videos(self):
        planos = noite.planos(noite._config_de_dia(self.config),
                              metas={"duelo": 0, "build": 20, "estreia": 2},
                              contagem=_contagem(build=10))
        build = next(p for p in planos if p["formato"] == "build")
        # faltam 10 videos = 5 roletas, ate o maximo de dia (3)
        self.assertEqual(2, build["por_roleta"])
        self.assertEqual(3, build["alvo"])


# ============================================================ a estreia
class AEstreiaSoAbaixoDaMeta(_Base, _MisturaDe19De10):

    def setUp(self):
        super().setUp()
        self._mistura_de_19_10()

    def test_com_estreias_sobrando_a_roleta_nao_renderiza_a_estreia(self):
        chamadas = []

        class _Controlador:
            def generate(self, **kw):
                chamadas.append(kw)
                return Path("generation_99001")

        relogio = _Relogio(_as(QUI, 10, 2))
        with mock.patch.object(noite, "_build_de_verdade", _BUILD_DE_VERDADE), \
                mock.patch("builds.pipeline.controller.PipelineController",
                           _Controlador):
            resultado = self._rodar(
                relogio, _contagem(duelo=40, build=0, estreia=52),
                gerar_build=None,
                config={**self.config, "rodada_de_dia": {
                    **self.config["rodada_de_dia"], "maximo_de_builds": 1}})
        self.assertEqual(["generation_99001"], resultado["builds"])
        self.assertEqual([{"estreia_render": False}], chamadas)
        build = next(p for p in resultado["planos"]
                     if p["formato"] == "build")
        self.assertFalse(noite.renderizar_estreia(build, self.config))
        self.assertEqual(20.0, noite.minutos_do_passo(build, self.config))

    def test_com_estreias_em_falta_renderiza(self):
        chamadas = []

        class _Controlador:
            def generate(self, **kw):
                chamadas.append(kw)
                return Path("generation_99002")

        relogio = _Relogio(_as(QUI, 10, 2))
        with mock.patch.object(noite, "_build_de_verdade", _BUILD_DE_VERDADE), \
                mock.patch("builds.pipeline.controller.PipelineController",
                           _Controlador):
            self._rodar(relogio, _contagem(duelo=40, build=0, estreia=0),
                        gerar_build=None,
                        config={**self.config, "rodada_de_dia": {
                            **self.config["rodada_de_dia"],
                            "maximo_de_builds": 1}})
        self.assertEqual([{"estreia_render": True}], chamadas)

    def test_sem_a_chave_renderiza_como_antes(self):
        plano = {"formato": "build", "estreias_no_estoque": 52,
                 "estreias_meta": 2, "minutos": 27,
                 "minutos_sem_estreia": 20}
        self.assertTrue(noite.renderizar_estreia(plano, {}))
        self.assertEqual(27.0, noite.minutos_do_passo(plano, {}))

    def test_a_luta_e_gravada_mas_o_video_nao(self):
        from builds.pipeline import controller as ctl

        tmp = Path(self.tmp.name) / "generation_99003"
        entregas = []

        def entregar(pasta, fight, preview, renderizar=True, **kw):
            entregas.append(renderizar)

        sessao = mock.Mock()
        sessao.return_value.gerar.return_value = {
            "lutas": [{"round": 1, "vencedor": "Ana", "ko_type": "KO",
                       "duracao": 9.0, "hp_vencedor": 10, "tier": "x",
                       "seed": 1}],
            "luta": {"ko_type": "KO", "duracao": 9.0, "hp_vencedor": 10,
                     "marcas": [], "tier": "x"},
            "vencedor": "Ana", "seed": 1, "cenario": "Arena",
            "melhor_de": 3, "placar": [2, 0]}
        controlador = ctl.PipelineController.__new__(ctl.PipelineController)
        controlador.scoring, controlador.editing_config = {}, {}
        controlador.render_config = {"profiles": ["celular"]}
        with mock.patch.object(controlador, "_entregar_luta",
                               side_effect=entregar), \
                mock.patch("builds.tournament.runner.FightSession", sessao), \
                mock.patch("builds.tournament.runner.fichas_do_banco",
                           return_value={"Ana": {}, "Bia": {}}), \
                mock.patch("builds.tournament.runner.personagens_gerados",
                           return_value=["Bia"]), \
                mock.patch("builds.arena.ledger.escolher_adversario",
                           return_value="Bia"), \
                mock.patch("builds.arena.ledger.Ledger", **{
                    "return_value.cartel.return_value": {}}), \
                mock.patch("builds.atividade.registrar"):
            pasta = controlador._gravar_estreia(
                tmp, {"generation_id": "generation_99003", "seed": 7},
                "Ana", False, renderizar=False)
        self.assertEqual(tmp / "estreia", pasta)
        self.assertEqual([False], entregas)
        self.assertTrue((tmp / "estreia.json").is_file())

    def test_entregar_sem_render_grava_a_edicao(self):
        from builds.pipeline import controller as ctl

        pasta = Path(self.tmp.name) / "estreia"
        pasta.mkdir()
        controlador = ctl.PipelineController.__new__(ctl.PipelineController)
        controlador.editing_config, controlador.captions = {}, None
        controlador.render_config = {"profiles": ["celular"]}
        construtor = mock.Mock()
        construtor.return_value.build.return_value = {
            "events": [{"start": 0, "duration": 1, "caption": "oi"}],
            "total_duration": 1.0}
        with mock.patch("builds.tournament.timeline.FightTimelineBuilder",
                        construtor), \
                mock.patch.object(ctl, "AssetCatalog"), \
                mock.patch.object(ctl, "AssetSelector"), \
                mock.patch.object(ctl, "VideoRenderer",
                                  side_effect=AssertionError("renderizou")):
            controlador._entregar_luta(pasta, {"seed": 3, "lutas": []},
                                       False, renderizar=False)
        for nome in ("edit_plan.json", "captions.json", "fight.json"):
            self.assertTrue((pasta / nome).is_file(), nome)

    def test_fluxo_nao_chama_de_pendencia(self):
        from builds.pipeline import fluxo

        gid = Path(self.tmp.name) / "generation_99004"
        (gid / "estreia").mkdir(parents=True)
        (gid / "estreia" / "fight.json").write_text("{}", encoding="utf-8")
        geracao = fluxo._geracao(gid, {})
        self.assertEqual(fluxo.OK, geracao["etapas"]["estreia"]["estado"])
        self.assertIn("fight --rerender generation_99004/estreia",
                      geracao["etapas"]["estreia"]["detalhe"])


# ============================================= quem derruba a gravacao
class QuemDerrubaAGravacaoSaiDoRodizio(unittest.TestCase):
    """19/10/2026, 16:23 e 16:34: Ardeth Morturth x Zael Ossarvarn estourou
    os 600 s da gravacao duas vezes; sem `fight.json`, o rodizio escolhia o
    mesmo par de novo e a rodada fechava com 0 duelos."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.outputs = Path(self.tmp.name)

    def _falha(self, n, p1, p2, quando):
        import json
        pasta = self.outputs / f"duelo_{n:05d}"
        pasta.mkdir()
        (pasta / "falhou.json").write_text(json.dumps(
            {"p1": p1, "p2": p2, "motivo": "RuntimeError: passou de 600.0s",
             "em": quando.isoformat(timespec="seconds")}), encoding="utf-8")

    def test_duas_falhas_na_semana_suspendem(self):
        from builds.arena import rodizio
        agora = datetime(2026, 10, 19, 17, 0)
        self._falha(135, "Ardeth Morturth", "Zael Ossarvarn",
                    agora - timedelta(minutes=37))
        self._falha(136, "Ardeth Morturth", "Zael Ossarvarn",
                    agora - timedelta(minutes=26))
        self._falha(90, "Velho", "Antigo", agora - timedelta(days=8))
        self._falha(91, "Velho", "Outro", agora - timedelta(days=8))
        self.assertEqual({"Ardeth Morturth": 2, "Zael Ossarvarn": 2},
                         rodizio.suspensos(self.outputs, agora))
        # caso zero: uma falha so nao suspende
        self.assertEqual({}, rodizio.suspensos(self.outputs, agora, limite=3))

    def test_o_rodizio_nao_escolhe_o_suspenso(self):
        from builds.arena import rodizio
        from builds.generation.random_engine import RandomEngine
        agora = datetime.now()
        for n in (135, 136):
            self._falha(n, "Ardeth Morturth", "Zael Ossarvarn", agora)
        fichas = {"Ardeth Morturth": {}, "Zael Ossarvarn": {}, "Bia": {},
                  "Caio": {}}
        config = {"titulos": {"duelo": "{p1} x {p2}"}}
        with mock.patch.object(rodizio, "OUTPUTS", self.outputs), \
                mock.patch("builds.publicar.metricas.publicados",
                           return_value=[]):
            p1, p2 = rodizio.escolher_par(
                fichas, ["Ardeth Morturth", "Zael Ossarvarn"],
                RandomEngine(1).fork("t"), config=config)
            self.assertEqual({"Bia", "Caio"}, {p1, p2})
            # caso zero: sem as falhas no disco, o menos usado e o gerado
            for pasta in self.outputs.glob("duelo_*"):
                (pasta / "falhou.json").unlink()
            p1, _p2 = rodizio.escolher_par(
                fichas, ["Ardeth Morturth", "Zael Ossarvarn"],
                RandomEngine(1).fork("t"), config=config)
            self.assertIn(p1, {"Ardeth Morturth", "Zael Ossarvarn"})

    def test_o_duelo_que_falha_deixa_a_ficha(self):
        import json

        from builds.arena import rodizio
        from builds.pipeline import controller as ctl
        sessao = mock.Mock()
        sessao.return_value.gerar.side_effect = RuntimeError(
            "gravacao falhou em A vs B: gravacao passou de 600.0s")
        controlador = ctl.PipelineController.__new__(ctl.PipelineController)
        controlador.scoring, controlador.editing_config = {}, {}
        controlador.render_config = {"profiles": ["celular"]}
        with mock.patch.object(ctl, "OUTPUTS", self.outputs), \
                mock.patch.object(rodizio, "escolher_par",
                                  return_value=("A", "B")), \
                mock.patch("builds.tournament.runner.FightSession", sessao), \
                mock.patch("builds.tournament.runner.fichas_do_banco",
                           return_value={"A": {}, "B": {}}), \
                mock.patch("builds.tournament.runner.personagens_gerados",
                           return_value=[]), \
                mock.patch("builds.tournament.runner.config_gameplay",
                           return_value={}), \
                mock.patch("builds.arena.ledger.Ledger"):
            with self.assertRaises(RuntimeError):
                controlador.duelo(seed=5)
        fichas = list(self.outputs.glob("duelo_*/falhou.json"))
        self.assertEqual(1, len(fichas))
        dados = json.loads(fichas[0].read_text(encoding="utf-8"))
        self.assertEqual(("A", "B", 5), (dados["p1"], dados["p2"],
                                         dados["seed"]))
        self.assertIn("600.0s", dados["motivo"])


# ============================================================ o jogo
class OJogoSegura(_Base):

    def test_com_o_jogo_aberto_nada_comeca(self):
        relogio = _Relogio(_as(QUI, 10, 2))
        drenar = mock.Mock(return_value=1)
        resultado = self._rodar(
            relogio, _contagem(duelo=0, build=0, estreia=0),
            jogo=lambda: "League of Legends.exe", drenar=drenar,
            jobs=[{"generation_id": "generation_1"}],
            proximo=lambda excluir=(): "correio")
        self.assertEqual([], self.ordem)
        self.assertEqual("jogo", resultado["parou"])
        self.assertEqual("jogo aberto", resultado["motivo"])
        drenar.assert_not_called()

    def test_o_jogo_abre_no_meio_e_a_rodada_para(self):
        relogio = _Relogio(_as(QUI, 10, 2))
        estados = iter([None, None, "League of Legends.exe"])
        self._rodar(relogio, _contagem(duelo=0, build=10),
                    jogo=lambda: next(estados, "League of Legends.exe"))
        self.assertEqual(["duelo", "duelo"], self.ordem)

    def test_no_estoque_zero_o_canal_vem_primeiro(self):
        relogio = _Relogio(_as(QUI, 23, 2))
        resultado = self._rodar(relogio, _contagem(estreia=52),
                                jogo=lambda: "League of Legends.exe")
        self.assertEqual("zero", resultado["modo"])
        self.assertEqual("duelo", self.ordem[0])

    def test_jogo_aberto_le_o_tasklist(self):
        config = {"jogo_que_segura": "League of Legends.exe"}
        aberto = types.SimpleNamespace(
            returncode=0, stdout=b'"League of Legends.exe","123","Console"')
        fechado = types.SimpleNamespace(
            returncode=0, stdout=b"INFORMACOES: nenhuma tarefa")
        self.assertEqual("League of Legends.exe",
                         _JOGO_ABERTO(config, rodar=lambda *a, **k: aberto))
        self.assertIsNone(_JOGO_ABERTO(config, rodar=lambda *a, **k: fechado))

        def quebra(*a, **k):
            raise OSError("sem tasklist")
        # na duvida NAO segura: a duvida pararia o canal
        self.assertIsNone(_JOGO_ABERTO(config, rodar=quebra))
        # sem a chave (o PADRAO), nao ha guarda nem tasklist
        self.assertIsNone(_JOGO_ABERTO({}, rodar=quebra))

    def test_o_config_de_verdade_tem_as_regras(self):
        config = noite.carregar()
        self.assertEqual("League of Legends.exe", config["jogo_que_segura"])
        self.assertEqual({"antes": 18, "depois": 18}, config["folga_da_grade"])
        self.assertTrue(config["estreia_so_abaixo_da_meta"])
        self.assertEqual(2, config["videos_por_roleta"])
        self.assertEqual(4, config["piso_por_formato_em_dias"]["duelo"])


if __name__ == "__main__":
    unittest.main()
