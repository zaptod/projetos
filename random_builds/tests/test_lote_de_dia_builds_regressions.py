# -*- coding: utf-8 -*-
"""O lote semanal de dia do canal de builds (decisoes do Adrian, 30/09/2026).

O trabalho pesado saiu da madrugada (barulho): janela 07h-22h; seg-ter o
lote gera ate cobrir a proxima segunda 07h + o piso; os outros dias so
repoem abaixo do piso de 20; estoque ZERO fora da janela libera tudo; a
madrugada antiga continua na transicao; nada roda na meia hora em volta de
cada horario da grade. O que este arquivo trava, sempre com relogio
congelado e dubles (nada e gerado de verdade):

  - os casos do plano: quinta 10:02 com 0, quinta 00:02 com 0, segunda
    07:02 com 60, segunda 09:30, quarta 22:00 e C: com menos de 5 GB;
  - o numero que decide e o da PUBLICACAO (`postar._builds_prontos`), nao
    um criterio proprio — o erro das historias em 30/09 (27 x 8);
  - o config de verdade (`geracao.json`) tem as decisoes.
"""
from __future__ import annotations

import os
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from builds.pipeline import noite, tarefas_noite

COTA = {"duelo": 4, "build": 3, "estreia": 1, "torneio": 0}

QUI = datetime(2026, 10, 1)          # quinta
SEG = datetime(2026, 10, 5)          # segunda do 1o lote
TER = datetime(2026, 10, 6)
QUA = datetime(2026, 10, 7)
SEG_ANTES = datetime(2026, 9, 28)    # segunda antes de `lote_a_partir_de`


def _as(dia, h, m, s=0):
    return dia.replace(hour=h, minute=m, second=s)


def _contagem(duelo=0, build=0, estreia=0):
    return {"total": duelo + build + estreia, "duelo": duelo,
            "build": build, "estreia": estreia, "torneio": 0,
            "fonte": "duble"}


def setUpModule():
    """Nenhum teste daqui gera, abre navegador ou le o catalogo de verdade."""
    for alvo in ("_duelo_de_verdade", "_build_de_verdade",
                 "_worker_de_verdade", "contar_estoque"):
        patcher = mock.patch.object(noite, alvo, side_effect=AssertionError(
            f"teste chamou noite.{alvo}: passe um duble"))
        patcher.start()
        unittest.addModuleCleanup(patcher.stop)


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
                  ("TRAVA", f"teste_lote_{os.getpid()}"),
                  ("cota", lambda *a, **k: dict(COTA)),
                  ("duelos_por_dia", lambda *a, **k: 5.0),
                  ("builds_por_dia", lambda *a, **k: 3.75),
                  ("builds_em_preparo", lambda *a, **k: []),
                  ("_livre_gb", lambda caminho: 100.0))
        for alvo, valor in trocas:
            patcher = mock.patch.object(noite, alvo, valor)
            patcher.start()
            self.addCleanup(patcher.stop)
        pausa = mock.patch("builds.identity.controle.pausado_para",
                           return_value=False)
        pausa.start()
        self.addCleanup(pausa.stop)
        self.registros = []
        registrar = mock.patch.object(
            noite, "_registrar",
            side_effect=lambda *a, **k: self.registros.append(a))
        registrar.start()
        self.addCleanup(registrar.stop)

    def _rodar(self, relogio, contagem, config=None, jobs=(), drenar=None,
               proximo=None, **kw):
        self.ordem, self.instantes = [], []

        def gerar_duelo():
            self.instantes.append(relogio())
            relogio.andar(4.3)
            self.ordem.append("duelo")
            return Path(f"duelo_{len(self.ordem):05d}")

        def gerar_build():
            self.instantes.append(relogio())
            relogio.andar(10)
            self.ordem.append("build")
            return Path(f"generation_{len(self.ordem):05d}")

        lista = list(jobs)
        return noite.rodar(config=config or self.config, relogio=relogio,
                           contagem=contagem, gerar_duelo=gerar_duelo,
                           gerar_build=gerar_build,
                           jobs=lambda: list(lista),
                           drenar_worker=drenar or (lambda **k: 0),
                           proximo=proximo or (lambda excluir=(): None),
                           tela=None, **kw)


# ============================================================ os casos ZERO
class CasosDoPlano(_Base):

    def test_quinta_10h02_com_zero_gera_duelos(self):
        relogio = _Relogio(_as(QUI, 10, 2))
        resultado = self._rodar(relogio, _contagem())
        self.assertEqual("reposicao", resultado["modo"])
        self.assertEqual("duelo", self.ordem[0])
        # meta do duelo na reposicao = ceil(20 x 4/8) = 10; a rodada dura
        # ate 10:57 e a roleta (15 min) nao cabe depois deles.
        self.assertEqual(10, len(resultado["duelos"]))
        self.assertEqual({"duelo": 10, "build": 8, "estreia": 3},
                         resultado["plano"]["metas"])
        self.assertTrue(all(i < _as(QUI, 10, 57) for i in self.instantes))
        self.assertTrue(any(r[0] == "ok" and "reposicao" in r[1]
                            for r in self.registros))

    def test_quinta_00h02_com_zero_libera_tudo(self):
        relogio = _Relogio(_as(QUI, 0, 2))
        resultado = self._rodar(relogio, _contagem())
        self.assertEqual("zero", resultado["modo"])
        self.assertTrue(resultado["duelos"])
        # O post das 00:37 fecha 00:22-00:52: todo duelo termina antes.
        for inicio in self.instantes:
            self.assertLessEqual(inicio + timedelta(minutes=5),
                                 _as(QUI, 0, 22))

    def test_quinta_00h02_com_estoque_nao_faz_barulho(self):
        relogio = _Relogio(_as(QUI, 0, 2))
        resultado = self._rodar(relogio, _contagem(duelo=5))
        self.assertEqual("fora da janela", resultado["motivo"])
        self.assertEqual([], self.ordem)
        self.assertEqual([], self.registros)

    def test_segunda_07h02_com_60_gera_ate_o_alvo(self):
        relogio = _Relogio(_as(SEG, 7, 2))
        resultado = self._rodar(relogio, _contagem(duelo=30, build=22,
                                                   estreia=8))
        plano = resultado["plano"]
        self.assertEqual("lote", resultado["modo"])
        # 70 horarios ate a proxima segunda 07h + piso 20 = 90, pela cota.
        self.assertEqual(90, plano["meta"])
        self.assertEqual({"duelo": 45, "build": 34, "estreia": 12},
                         plano["metas"])
        # build 22/3,75 = 5,9 dias < duelo 30/5 = 6: a roleta primeiro,
        # ate o maximo de dia (3), depois os duelos ate 07:57.
        self.assertEqual(["build"] * 3, self.ordem[:3])
        self.assertEqual(3, len(resultado["builds"]))
        self.assertTrue(resultado["duelos"])
        self.assertTrue(all(i < _as(SEG, 7, 57) for i in self.instantes))

    def test_segunda_com_o_alvo_cheio_nao_gera(self):
        relogio = _Relogio(_as(SEG, 7, 2))
        resultado = self._rodar(relogio, _contagem(duelo=50, build=35,
                                                   estreia=12))
        self.assertEqual("lote", resultado["modo"])
        self.assertEqual([], self.ordem)
        self.assertEqual("estoque cheio", resultado["motivo"])

    def test_antes_do_primeiro_lote_a_segunda_e_reposicao(self):
        relogio = _Relogio(_as(SEG_ANTES, 7, 2))
        resultado = self._rodar(relogio, _contagem(duelo=40, build=20))
        self.assertEqual("reposicao", resultado["modo"])
        self.assertEqual([], self.ordem)

    def test_terca_herda_o_alvo_se_a_segunda_nao_produziu(self):
        # PC desligado na segunda: a terca mira a MESMA segunda 07h.
        self.assertEqual(80, noite.alvo_do_lote(self.config, _as(TER, 7, 2)))
        relogio = _Relogio(_as(TER, 7, 2))
        resultado = self._rodar(relogio, _contagem(duelo=10, build=10))
        self.assertEqual("lote", resultado["modo"])
        self.assertTrue(self.ordem)

    def test_segunda_09h30_nao_comeca_passo_novo(self):
        relogio = _Relogio(_as(SEG, 9, 30))
        resultado = self._rodar(relogio, _contagem())
        self.assertEqual("lote", resultado["modo"])
        self.assertEqual([], self.ordem)
        self.assertEqual("janela", resultado["parou"])

    def test_quarta_22h00_para(self):
        relogio = _Relogio(_as(QUA, 22, 0))
        resultado = self._rodar(relogio, _contagem(duelo=10))
        self.assertEqual("noite", resultado["modo"])
        self.assertEqual("fora da janela", resultado["motivo"])
        self.assertEqual([], self.ordem)

    def test_a_rodada_para_nas_22h(self):
        # 21:53 (depois da folga do 21:37): um duelo termina 21:57; o
        # seguinte terminaria 22:02 — fora da janela.
        relogio = _Relogio(_as(QUA, 21, 53))
        resultado = self._rodar(relogio, _contagem())
        self.assertEqual(["duelo"], self.ordem)
        self.assertEqual("janela", resultado["parou"])

    def test_disco_c_abaixo_de_5gb_nao_comeca(self):
        relogio = _Relogio(_as(QUI, 10, 2))
        with mock.patch.object(noite, "_livre_gb", lambda caminho: 3.2):
            resultado = self._rodar(relogio, _contagem())
        self.assertEqual([], self.ordem)
        self.assertEqual("impedido", resultado["motivo"])
        self.assertIn("3.2 GB", resultado["plano"]["impedimento"])
        # De madrugada, com zero: tambem nao.
        relogio = _Relogio(_as(QUI, 0, 2))
        with mock.patch.object(noite, "_livre_gb", lambda caminho: 3.2):
            resultado = self._rodar(relogio, _contagem())
        self.assertEqual([], self.ordem)
        self.assertEqual("impedido", resultado["motivo"])

    def test_madrugada_da_transicao_roda_o_esquema_antigo(self):
        relogio = _Relogio(_as(QUI, 1, 2))
        resultado = self._rodar(relogio, _contagem(duelo=9, build=6))
        self.assertEqual("madrugada", resultado["modo"])
        # teto de gordura: duelo 10 - 9 = 1; build 8 - 6 = 2, maximo 1.
        self.assertEqual(["build", "duelo"], self.ordem)

    def test_sem_a_chave_da_transicao_a_madrugada_so_ve_o_zero(self):
        config = {k: v for k, v in self.config.items()
                  if k != "madrugada_na_transicao"}
        relogio = _Relogio(_as(QUI, 1, 2))
        resultado = self._rodar(relogio, _contagem(duelo=9, build=6),
                                config=config)
        self.assertEqual("noite", resultado["modo"])
        self.assertEqual([], self.ordem)

    def test_com_job_esperando_o_worker_tem_a_reserva(self):
        relogio = _Relogio(_as(QUI, 10, 2))
        chamadas = []
        fila = ["picasso"]

        def drenar(so_provedor=None, prazo=None):
            chamadas.append((so_provedor, datetime.fromtimestamp(prazo)
                             .replace(second=0, microsecond=0)))
            relogio.andar(5)
            fila.clear()
            return 1

        resultado = self._rodar(
            relogio, _contagem(), jobs=[{"generation_id": "generation_00086"}],
            drenar=drenar,
            proximo=lambda excluir=(): next(
                (p for p in fila if p not in excluir), None))
        # geracao ate 10:37 (55 - 20 de reserva), o worker ate 10:57.
        self.assertTrue(all(i + timedelta(minutes=5) <= _as(QUI, 10, 37)
                            for i in self.instantes))
        self.assertEqual([("picasso", _as(QUI, 10, 49))], chamadas)
        self.assertEqual(1, resultado["jobs_do_worker"])


# ================================================================= relogio
class FolgaDaGrade(unittest.TestCase):

    def setUp(self):
        self.config = noite.carregar()

    def test_meia_hora_em_volta_de_cada_horario(self):
        livre = lambda h, m: noite.fora_da_grade(_as(QUI, h, m), self.config)
        self.assertTrue(livre(9, 21))
        self.assertFalse(livre(9, 22))
        self.assertFalse(livre(9, 52))
        self.assertTrue(livre(9, 53))
        # 12:07 e 17:57 nao sao :37: a regra velha (:25-:55) nao os via.
        self.assertFalse(livre(12, 0))
        self.assertFalse(livre(17, 45))
        self.assertFalse(livre(18, 10))
        # e a regra velha nao vale mais: 10:30 esta longe de tudo.
        self.assertTrue(livre(10, 30))
        # 23:50 enxerga o 00:37 do dia seguinte? nao ha post a 15 min; o
        # 23:37 sim.
        self.assertFalse(livre(23, 50))
        self.assertTrue(livre(0, 5))

    def test_passo_so_comeca_se_termina_antes_da_folga(self):
        self.assertTrue(noite.cabe(_as(QUI, 9, 2), 15, self.config))
        self.assertFalse(noite.cabe(_as(QUI, 9, 8), 15, self.config))
        self.assertFalse(noite.cabe(_as(QUI, 6, 50), 5, self.config))


# ============================================================ o estoque
class OEstoqueEDaPublicacao(unittest.TestCase):

    def test_contar_estoque_agrupa_a_lista_da_publicacao(self):
        videos = [types.SimpleNamespace(origem=o) for o in
                  ("duelo", "duelo", "build", "estreia", "duelo")]
        falso = types.SimpleNamespace(_builds_prontos=lambda: list(videos))
        with mock.patch.object(noite, "_postar", return_value=falso):
            # A `contar_estoque` de verdade (o modulo a dublou para os outros).
            conta = _ORIGINAL_CONTAR()
        self.assertEqual(5, conta["total"])
        self.assertEqual((3, 1, 1), (conta["duelo"], conta["build"],
                                     conta["estreia"]))
        self.assertEqual("publicacao", conta["fonte"])

    def test_pendentes_da_publicacao_e_a_mesma_lista(self):
        # Se a publicacao mudar o que conta como estoque de builds, este
        # teste avisa: a geracao agrupa `_builds_prontos`, e o `--ver` / o
        # alerta de piso contam `pendentes_por_canal()["builds"]`.
        postar = _postar_real()
        with mock.patch.object(postar, "_builds_prontos",
                               return_value=[1, 2, 3]), \
                mock.patch.object(postar, "fila_de_historias",
                                  return_value=[]):
            self.assertEqual(3, postar.pendentes_por_canal()["builds"])

    def test_o_piso_da_publicacao_e_o_daqui(self):
        postar = _postar_real()
        self.assertEqual(noite.carregar()["piso_de_reposicao"],
                         postar.piso_de_alerta("builds"))


def _postar_real():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_postar_teste_lote",
                                                  noite.POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# Guardada no import, antes de `setUpModule` trocar pelo duble que explode.
_ORIGINAL_CONTAR = noite.contar_estoque


# ============================================================ o config
class OConfigTemAsDecisoes(unittest.TestCase):

    def test_decisoes_de_30_09(self):
        config = noite.carregar()
        self.assertEqual({"inicio": 7, "fim": 22}, config["janela_pesada"])
        self.assertEqual([0, 1], config["dias_de_lote"])
        self.assertEqual(20, config["piso_de_reposicao"])
        self.assertTrue(config["estoque_zero_libera_a_noite"])
        self.assertEqual("2026-10-05", config["lote_a_partir_de"])
        self.assertIn("madrugada_na_transicao", config)
        self.assertIsNone(config["grade_proibida"])
        self.assertEqual(5, config["disco_livre_minimo_gb"])

    def test_alvo_de_segunda_e_de_quarta(self):
        config = noite.carregar()
        self.assertEqual(90, noite.alvo_do_lote(config, _as(SEG, 7, 2)))
        self.assertEqual(SEG + timedelta(days=7, hours=7),
                         noite.fim_da_cobertura(config, _as(SEG, 7, 2)))

    def test_horas_de_dia_e_de_noite(self):
        config = noite.carregar()
        pares = [tarefas_noite.hora_e_minuto(h, config["minuto"])
                 for h in config["horas"]]
        for hora in range(7, 22):
            self.assertIn(hora, [h for h, _m in pares], hora)
        self.assertIn((12, 32), pares)
        self.assertIn((18, 22), pares)
        self.assertIn((0, 2), pares)
        for hora in (1, 2, 3, 4, 5):
            self.assertIn((hora, 2), pares)


if __name__ == "__main__":
    unittest.main()
