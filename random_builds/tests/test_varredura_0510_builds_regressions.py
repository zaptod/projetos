# -*- coding: utf-8 -*-
"""Varredura de erros de 05/10/2026, parte de builds (itens 15 e 16).

Medido em `outputs/_identity/queue.json` (05/10/2026, 13:20):

- juncoes `failed` com as duas imagens JA no disco: `generation_00078`,
  `00090` e `00095` ("achei 1 em ..."). O prazo do enqueue liberou a juncao
  com uma imagem ainda a caminho, a falta de entrada gastou as tres
  tentativas, e `failed` era terminal;
- `generation_00098`: personagem e arma "falharam" 3x cada em 22 s pela
  parede de planos do PicassoIA (04/10 01:16) e a juncao, liberada pelas
  duas falhas, queimou as tres dela com "achei 0";
- 7 payoffs do Digen `pending` com `payoff_video=false` contados como
  trabalho do worker;
- a rodada dizia "[noite] fim: 0 erro(s)" com tudo isso no log.

E o diario (`atividade.jsonl`): poda por numero de linhas (cobria ~23,6 h e
caia para ~12 h), `recentes(n)` limitado as ultimas 1200 linhas.
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from PIL import Image

from builds import atividade
from builds.identity import artefato
from builds.identity import config as icfg
from builds.identity import queue as fila
from builds.identity import slots

from builds.pipeline import noite as _noite

# A funcao REAL, guardada na coleta: `test_geracao_noturna_regressions`
# troca `noite._worker_de_verdade` por uma bomba no `setUpModule` (nenhum
# teste pode drenar de verdade), e no pytest a troca vaza para os modulos
# seguintes. Aqui o `worker.drenar` por baixo dela e um duble.
_WORKER_DE_VERDADE = _noite._worker_de_verdade

GID = "generation_77701"
LONGE = "2999-01-01T00:00:00+00:00"
PASSADO = "2000-01-01T00:00:00+00:00"


class _FilaNoTemp(unittest.TestCase):
    """Fila e outputs numa pasta descartavel, com o payoff LIGADO."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        raiz = Path(self._tmp.name)
        for objeto, alvo, valor in ((fila, "ARQUIVO_FILA", raiz / "queue.json"),
                                    (icfg, "OUTPUTS", raiz / "outputs")):
            patcher = mock.patch.object(objeto, alvo, valor)
            patcher.start()
            self.addCleanup(patcher.stop)
        (icfg.OUTPUTS / GID).mkdir(parents=True)
        for alvo, valor in (("jobs_desligados", lambda: frozenset()),
                            ("geracoes_descartadas", lambda: set()),
                            ("geracoes_publicadas", lambda: set())):
            patcher = mock.patch.object(fila, alvo, valor)
            patcher.start()
            self.addCleanup(patcher.stop)
        pausa = mock.patch("builds.identity.controle.pausado_para",
                           return_value=False)
        pausa.start()
        self.addCleanup(pausa.stop)

    def _enfileirar(self, prazo=LONGE):
        for slot in slots.JOBS:
            fila.enqueue(GID, f"prompt {slot}", slot=slot,
                         aguardar_ate=prazo if slots.depende_de(slot) else None)

    def _imagem(self, slot: str):
        Image.new("RGB", (600, 1064), (40, 30, 80)).save(
            icfg.OUTPUTS / GID / slots.ARQUIVO[slot])
        self.assertTrue(artefato.utilizavel(GID, slot))

    def _drenar(self) -> list:
        pegos = []
        while (job := fila.claim()) is not None:
            pegos.append(job["slot"])
        return pegos

    def _linha(self, slot):
        return next(j for j in fila.listar()
                    if j["job_id"] == slots.job_id(GID, slot))


# ============================================================ a juncao espera
class AJuncaoNaoSaiSemAsDuasImagens(_FilaNoTemp):

    def test_prazo_vencido_nao_libera_a_juncao_com_imagem_a_caminho(self):
        # 00078/00090/00095: uma imagem pronta, a outra ainda pendente, prazo
        # vencido -> a juncao saia e morria com "achei 1".
        self._enfileirar(prazo=PASSADO)
        self._imagem(slots.CHARACTER)
        fila.claim()                              # personagem (ja no disco)
        pegos = self._drenar()
        self.assertNotIn(slots.REFERENCIA, pegos)

    def test_imagens_que_falharam_nao_liberam_a_juncao(self):
        # 00098: personagem e arma `failed`, nenhum arquivo -> a juncao era
        # liberada pelo caminho "nao se espera defunto" e queimava 3 tentativas.
        self._enfileirar()
        for slot in (slots.CHARACTER, slots.WEAPON):
            fila.falhar(slots.job_id(GID, slot), "parede", max_attempts=0)
        self.assertNotIn(slots.REFERENCIA, self._drenar())
        juncao = self._linha(slots.REFERENCIA)
        self.assertEqual(fila.PENDENTE, juncao["status"])
        self.assertEqual(0, juncao["attempts"])
        self.assertTrue(fila.espera_impossivel(juncao, fila.listar()))

    def test_o_payoff_continua_degradando_pelo_prazo(self):
        # A juncao espera; quem degrada e o payoff (so texto), como antes.
        self._enfileirar(prazo=PASSADO)
        self.assertIn(slots.CHARACTER_WEAPON, self._drenar())

    def test_com_as_duas_imagens_a_juncao_sai(self):
        self._enfileirar()
        self._imagem(slots.CHARACTER)
        self._imagem(slots.WEAPON)
        self.assertIn(slots.REFERENCIA, self._drenar())
        self.assertFalse(fila.espera_impossivel(
            self._linha(slots.REFERENCIA), fila.listar()))

    def test_espera_viva_nao_e_impossivel(self):
        self._enfileirar()
        self.assertFalse(fila.espera_impossivel(
            self._linha(slots.REFERENCIA), fila.listar()))


class OSlotDesligado(_FilaNoTemp):

    def test_payoff_desligado_nao_e_reivindicado(self):
        self._enfileirar(prazo=PASSADO)
        for slot in (slots.CHARACTER, slots.WEAPON, slots.REFERENCIA):
            self._imagem(slot)
        with mock.patch.object(fila, "jobs_desligados",
                               lambda: frozenset({slots.CHARACTER_WEAPON})):
            self.assertFalse(fila.tem_reivindicavel(provedor=slots.DIGEN))
            self.assertNotIn(slots.CHARACTER_WEAPON, self._drenar())
        # Nada e apagado: religar o video devolve o job.
        self.assertEqual(fila.PENDENTE, self._linha(slots.CHARACTER_WEAPON)["status"])
        self.assertTrue(fila.tem_reivindicavel(provedor=slots.DIGEN))

    def test_jobs_desligados_le_a_config(self):
        # A funcao de verdade (a classe base troca a de `fila` por um duble).
        with mock.patch.object(icfg, "settings",
                               return_value={"payoff_video": False}):
            self.assertEqual(frozenset({slots.CHARACTER_WEAPON}),
                             _JOBS_DESLIGADOS())
        with mock.patch.object(icfg, "settings",
                               return_value={"payoff_video": True}):
            self.assertEqual(frozenset(), _JOBS_DESLIGADOS())
        with mock.patch.object(icfg, "jobs_ativos",
                               side_effect=OSError("config ilegivel")):
            self.assertEqual(frozenset(), _JOBS_DESLIGADOS())


_JOBS_DESLIGADOS = fila.jobs_desligados


class ReabrirFalha(_FilaNoTemp):

    def test_failed_volta_pending_com_tentativas_zeradas(self):
        self._enfileirar()
        jid = slots.job_id(GID, slots.CHARACTER)
        fila.claim()
        fila.falhar(jid, "boom", max_attempts=1)
        self.assertEqual(fila.FALHOU, self._linha(slots.CHARACTER)["status"])
        fila.reabrir_falha(jid, "teste")
        linha = self._linha(slots.CHARACTER)
        self.assertEqual(fila.PENDENTE, linha["status"])
        self.assertEqual(0, linha["attempts"])
        self.assertIn("reaberto", linha["error"])

    def test_job_que_nao_falhou_fica_como_esta(self):
        self._enfileirar()
        jid = slots.job_id(GID, slots.WEAPON)
        antes = self._linha(slots.WEAPON)
        fila.reabrir_falha(jid, "teste")
        self.assertEqual(antes, self._linha(slots.WEAPON))


# ================================================================ o worker
class OWorkerReabreOQueJaPodeAndar(_FilaNoTemp):

    def _falhar(self, slot, erro):
        fila.falhar(slots.job_id(GID, slot), erro, max_attempts=0)

    def test_juncao_por_falta_de_entrada_volta_com_as_imagens(self):
        from builds.identity import worker
        self._enfileirar()
        self._imagem(slots.CHARACTER)
        self._imagem(slots.WEAPON)
        self._falhar(slots.REFERENCIA,
                     f"a juncao precisa das duas imagens e achei 1 em {GID}.")
        self.assertEqual(1, worker._reabrir_falhas_superadas())
        self.assertEqual(fila.PENDENTE, self._linha(slots.REFERENCIA)["status"])
        self.assertIn(slots.REFERENCIA, self._drenar())

    def test_juncao_sem_as_imagens_continua_failed(self):
        from builds.identity import worker
        self._enfileirar()
        self._imagem(slots.CHARACTER)
        self._falhar(slots.REFERENCIA,
                     f"a juncao precisa das duas imagens e achei 1 em {GID}.")
        self.assertEqual(0, worker._reabrir_falhas_superadas())
        self.assertEqual(fila.FALHOU, self._linha(slots.REFERENCIA)["status"])

    def test_juncao_que_falhou_por_outro_motivo_nao_e_reaberta(self):
        # Reabrir toda rodada uma juncao que falha de verdade queimaria tres
        # tentativas por hora para sempre.
        from builds.identity import worker
        self._enfileirar()
        self._imagem(slots.CHARACTER)
        self._imagem(slots.WEAPON)
        self._falhar(slots.REFERENCIA, "o PicassoIA recusou o prompt")
        self.assertEqual(0, worker._reabrir_falhas_superadas())

    def test_falha_pela_parede_de_planos_volta(self):
        from builds.identity import worker
        self._enfileirar()
        for slot in (slots.CHARACTER, slots.WEAPON):
            self._falhar(slot, "PicassoIA mostrando parede de planos (sessao "
                               "FREE?): o botao de gerar virou 'Assine para Gerar'")
        self.assertEqual(2, worker._reabrir_falhas_superadas())
        for slot in (slots.CHARACTER, slots.WEAPON):
            self.assertEqual(fila.PENDENTE, self._linha(slot)["status"])
            self.assertEqual(0, self._linha(slot)["attempts"])

    def test_o_pre_passe_chama_a_reabertura(self):
        from builds.identity import worker
        self._enfileirar()
        self._imagem(slots.CHARACTER)
        self._imagem(slots.WEAPON)
        self._falhar(slots.REFERENCIA,
                     f"a juncao precisa das duas imagens e achei 1 em {GID}.")
        worker._resolver_no_disco(rerender=False, preview=True)
        self.assertEqual(fila.PENDENTE, self._linha(slots.REFERENCIA)["status"])


class PrepararJuncao(unittest.TestCase):

    def test_falta_de_entrada_e_conferida_antes_de_mexer_na_pagina(self):
        from builds.identity import referencias, worker
        cliente = mock.Mock()
        with mock.patch.object(referencias, "entradas_do_editor",
                               return_value=[Path("so_uma.png")]):
            with self.assertRaises(worker.EntradasFaltando):
                worker._preparar_juncao(cliente, {"generation_id": GID})
        cliente.preparar_espaco.assert_not_called()
        cliente.anexar_referencias.assert_not_called()


class APassada(unittest.TestCase):
    """O que a passada faz com a falta de entrada e com a parede de planos."""

    def _passada(self, erros):
        from builds.identity import worker
        jobs = [{"job_id": f"{GID}#character", "generation_id": GID,
                 "slot": "character", "attempts": 1},
                {"job_id": f"{GID}#weapon", "generation_id": GID,
                 "slot": "weapon", "attempts": 1}]
        reivindicados, diario, ignorados = [], [], []
        erros = list(erros)

        def claim(max_attempts=3, ignorar=None, provedor=None):
            ignorados.append(set(ignorar or ()))
            livres = [j for j in jobs if j["job_id"] not in (ignorar or ())]
            if not livres:
                return None
            job = livres[0]
            jobs.remove(job)
            reivindicados.append(job["job_id"])
            return job

        def processar(*a, **k):
            erro = erros.pop(0) if erros else None
            if erro is not None:
                raise erro
            return Path("feito.png")

        cliente = mock.Mock()
        cliente.creditos.return_value = None
        ajustes = {"max_attempts": 3, "min_interval": 0,
                   "pausa_na_parede_min": 30}
        worker._FALHAS.clear()
        with mock.patch.object(worker.queue, "claim", side_effect=claim), \
                mock.patch.object(worker.queue, "falhar") as falhar, \
                mock.patch.object(worker.queue, "reagendar") as reagendar, \
                mock.patch.object(worker.queue, "concluir"), \
                mock.patch.object(worker.history, "registrar"), \
                mock.patch.object(worker.config, "settings",
                                  return_value=ajustes), \
                mock.patch.object(worker.time, "sleep"), \
                mock.patch.object(worker, "pausa_humana"), \
                mock.patch.object(worker, "processar", side_effect=processar), \
                mock.patch.object(worker, "contexto_persistente",
                                  side_effect=lambda **k:
                                  contextlib.nullcontext(object())), \
                mock.patch.object(worker, "pagina", return_value=object()), \
                mock.patch.object(worker, "ensure_logged_in"), \
                mock.patch.object(worker.provedores, "cliente",
                                  return_value=cliente), \
                mock.patch.object(worker.provedores, "seletores",
                                  return_value=None), \
                mock.patch.object(worker.controle, "pausado_para",
                                  return_value=False), \
                mock.patch.object(worker.controle, "parada_pedida",
                                  return_value=False), \
                mock.patch.object(worker.controle, "pausar") as pausar, \
                mock.patch("builds.travas.do_perfil",
                           return_value=f"teste_varredura_{os.getpid()}"), \
                mock.patch("builds.atividade.registrar",
                           side_effect=lambda *a, **k: diario.append((a, k))):
            resultado = worker._passada("picasso", False, True, False, None)
        return {"resultado": resultado, "reivindicados": reivindicados,
                "falhar": falhar, "reagendar": reagendar, "pausar": pausar,
                "diario": diario, "ignorados": ignorados,
                "falhas": worker.falhas_da_ultima_rodada()}

    def test_falta_de_entrada_reagenda_sem_gastar_tentativa(self):
        from builds.identity import worker
        feito = self._passada([worker.EntradasFaltando("achei 1"), None])
        feito["falhar"].assert_not_called()
        feito["reagendar"].assert_called_once()
        self.assertEqual(f"{GID}#character",
                         feito["reagendar"].call_args.args[0])
        # Adiado nesta passada: nao e repescado (ping-pong).
        self.assertIn(f"{GID}#character", feito["ignorados"][-1])
        self.assertEqual((1, None), feito["resultado"])
        self.assertEqual([], feito["falhas"])

    def test_parede_de_planos_pausa_e_nao_queima_tentativa(self):
        from builds.identity.picasso_client import ParedeDePlanos
        parede = ParedeDePlanos("PicassoIA mostrando parede de planos (sessao "
                                "FREE?): o botao de gerar virou 'Assine para Gerar'")
        feito = self._passada([parede])
        # Um job so: o proximo bateria na mesma parede.
        self.assertEqual([f"{GID}#character"], feito["reivindicados"])
        feito["falhar"].assert_not_called()
        feito["reagendar"].assert_called_once()
        self.assertIn("parede de planos", feito["reagendar"].call_args.args[1])
        feito["pausar"].assert_called_once()
        p_args, p_kwargs = feito["pausar"].call_args
        self.assertEqual("picasso", p_args[0] if p_args else p_kwargs.get("alvo"))
        self.assertEqual(30.0, p_kwargs.get("minutos"))
        self.assertIn("parede de planos", p_kwargs.get("motivo", ""))
        # A rodada de geracao conta a parede como erro.
        self.assertEqual(1, len(feito["falhas"]))
        self.assertIn("ParedeDePlanos", feito["falhas"][0])
        # O ULTIMO evento do diario e o erro (a fabrica anota `ok` antes).
        ultimo_args, ultimo_kw = feito["diario"][-1]
        self.assertEqual(("picasso", atividade.ERRO), ultimo_args[:2])
        self.assertEqual("identity.parede_de_planos", ultimo_kw.get("etapa"))
        self.assertFalse(ultimo_kw.get("ref"))

    def test_falha_comum_continua_contando_e_aparece_nas_falhas(self):
        from builds.identity.client import GeracaoFalhou
        feito = self._passada([GeracaoFalhou("Generation failed"), None])
        self.assertEqual(1, feito["falhar"].call_count)
        feito["pausar"].assert_not_called()
        self.assertEqual(1, len(feito["falhas"]))
        self.assertIn("GeracaoFalhou", feito["falhas"][0])


# ================================================================== a noite
class ANoiteContaAsFalhas(unittest.TestCase):

    def test_concluidos_e_falhas_aceita_inteiro_e_dicionario(self):
        from builds.pipeline import noite
        self.assertEqual((2, []), noite._concluidos_e_falhas(2))
        self.assertEqual((0, []), noite._concluidos_e_falhas(None))
        self.assertEqual((1, ["x: Boom: y"]), noite._concluidos_e_falhas(
            {"concluidos": 1, "falhas": ["x: Boom: y"]}))

    def test_worker_de_verdade_devolve_as_falhas(self):
        from builds.identity import worker

        def drenar(**k):
            worker._FALHAS.append("job: ParedeDePlanos: parede")
            return 0

        with mock.patch.object(worker, "drenar", side_effect=drenar):
            worker._FALHAS.clear()
            retorno = _WORKER_DE_VERDADE(so_provedor="picasso")
        self.assertEqual({"concluidos": 0,
                          "falhas": ["job: ParedeDePlanos: parede"]}, retorno)

    def test_o_resumo_conta_as_falhas_do_worker(self):
        from builds.pipeline import noite
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        registros = []
        relogio = lambda: datetime(2026, 10, 5, 3, 2)          # noqa: E731
        provedores = ["picasso"]

        def proximo(excluir=()):
            return next((p for p in provedores if p not in excluir), None)

        def drenar(so_provedor=None, prazo=None):
            return {"concluidos": 0,
                    "falhas": ["generation_00098#character: ParedeDePlanos: "
                               "parede de planos"]}

        with mock.patch.object(noite, "LOGS", Path(tmp.name)), \
                mock.patch.object(noite, "TRAVA", f"teste_varr_{os.getpid()}"), \
                mock.patch.object(noite, "duelos_por_dia", lambda *a, **k: 5.0), \
                mock.patch.object(noite, "builds_por_dia", lambda *a, **k: 3.75), \
                mock.patch.object(noite, "_registrar",
                                  side_effect=lambda *a, **k: registros.append(a)), \
                mock.patch.object(noite, "_duelo_de_verdade",
                                  side_effect=AssertionError("duelo real")), \
                mock.patch.object(noite, "_build_de_verdade",
                                  side_effect=AssertionError("build real")), \
                mock.patch.object(noite, "_worker_de_verdade",
                                  side_effect=AssertionError("worker real")), \
                mock.patch("builds.identity.controle.pausado_para",
                           return_value=False):
            resultado = noite.rodar(
                config=dict(noite.PADRAO), relogio=relogio,
                gerar_duelo=lambda: Path("duelo_00001"),
                estoque=lambda: [0] * 10,
                gerar_build=lambda: Path("generation_00001"),
                estoque_builds=lambda: [0] * 8,
                jobs=lambda: [{"generation_id": "generation_00098"}],
                drenar_worker=drenar, proximo=proximo, tela=None)
        self.assertTrue(any("ParedeDePlanos" in e for e in resultado["erros"]),
                        resultado["erros"])
        self.assertTrue(any(r[0] == "erro" for r in registros), registros)


class JobsDoWorker(_FilaNoTemp):

    def test_nao_conta_desligado_nem_juncao_sem_futuro(self):
        from builds.pipeline import noite
        self._enfileirar()
        for slot in (slots.CHARACTER, slots.WEAPON):
            fila.falhar(slots.job_id(GID, slot), "boom", max_attempts=0)
        with mock.patch.object(fila, "jobs_desligados",
                               lambda: frozenset({slots.CHARACTER_WEAPON})):
            contados = {j["slot"] for j in noite.jobs_do_worker()}
        # imagens `failed`, juncao esperando o que nao vem, payoff desligado.
        self.assertEqual(set(), contados)

    def test_conta_a_juncao_que_espera_imagem_viva(self):
        from builds.pipeline import noite
        self._enfileirar()
        contados = {j["slot"] for j in noite.jobs_do_worker()}
        self.assertEqual(set(slots.JOBS), contados)


# ================================ conferente 05/10: a reabertura sem outro job
class ANoiteChamaOWorkerSoParaReabrir(_FilaNoTemp):
    """Defeito 1 do conferente: numa copia da fila real, com 00104 e 00105
    prontas, `jobs_do_worker()` dava [] e `proximo_do_worker()` dava None — e
    as juncoes `failed` de 00078, 00090 e 00095, com as duas imagens no disco,
    nunca eram reabertas (a reabertura so roda dentro do `drenar`)."""

    FALTA = f"a juncao precisa das duas imagens e achei 1 em {GID}."

    def _so_a_juncao_reabrivel(self):
        self._enfileirar()
        for slot in (slots.CHARACTER, slots.WEAPON):
            self._imagem(slot)
            fila.concluir(slots.job_id(GID, slot), "x.png")
        fila.concluir(slots.job_id(GID, slots.CHARACTER_WEAPON), "x.mp4")
        fila.falhar(slots.job_id(GID, slots.REFERENCIA), self.FALTA,
                    max_attempts=0)
        self.assertFalse(fila.tem_reivindicavel())

    def test_jobs_do_worker_e_proximo_veem_a_juncao_reabrivel(self):
        from builds.pipeline import noite
        self._so_a_juncao_reabrivel()
        self.assertEqual([slots.job_id(GID, slots.REFERENCIA)],
                         [j["job_id"] for j in noite.jobs_do_worker()])
        self.assertEqual(slots.PICASSO, noite.proximo_do_worker())
        # Provedor pausado: a passada nao abriria nada, entao nao conta.
        with mock.patch("builds.identity.controle.pausado_para",
                        return_value=True):
            self.assertIsNone(noite.proximo_do_worker())

    def test_publicada_ou_descartada_nao_conta_nem_reabre(self):
        # Defeito 3: a 00078 esta no ar (6 linhas no ledger); reabrir a juncao
        # dela gastaria uma imagem e re-renderizaria um video publicado.
        from builds.identity import worker
        from builds.pipeline import noite
        self._so_a_juncao_reabrivel()
        for alvo in ("geracoes_publicadas", "geracoes_descartadas"):
            with mock.patch.object(fila, alvo, lambda: {GID}):
                self.assertEqual([], noite.jobs_do_worker())
                self.assertIsNone(noite.proximo_do_worker())
                self.assertEqual(0, worker._reabrir_falhas_superadas())
            self.assertEqual(fila.FALHOU,
                             self._linha(slots.REFERENCIA)["status"])

    def test_a_juncao_volta_quando_a_ultima_imagem_chega(self):
        # 00098: personagem e arma reabertos e gerados NA passada; a juncao
        # (failed, "achei 0") tem de voltar ja, nao so na proxima drenagem.
        self._enfileirar()
        fila.falhar(slots.job_id(GID, slots.REFERENCIA), self.FALTA,
                    max_attempts=0)
        self._imagem(slots.CHARACTER)
        fila.concluir(slots.job_id(GID, slots.CHARACTER), "c.png")
        self.assertEqual(fila.FALHOU, self._linha(slots.REFERENCIA)["status"])
        self._imagem(slots.WEAPON)
        fila.concluir(slots.job_id(GID, slots.WEAPON), "w.png")
        juncao = self._linha(slots.REFERENCIA)
        self.assertEqual(fila.PENDENTE, juncao["status"])
        self.assertEqual(0, juncao["attempts"])
        self.assertIn(slots.REFERENCIA, self._drenar())

    def test_juncao_que_falhou_por_outro_motivo_nao_volta_no_concluir(self):
        self._enfileirar()
        fila.falhar(slots.job_id(GID, slots.REFERENCIA),
                    "o PicassoIA recusou o prompt", max_attempts=0)
        for slot in (slots.CHARACTER, slots.WEAPON):
            self._imagem(slot)
            fila.concluir(slots.job_id(GID, slot), "x.png")
        self.assertEqual(fila.FALHOU, self._linha(slots.REFERENCIA)["status"])


class GeracoesPublicadas(unittest.TestCase):

    def test_so_a_build_que_saiu_conta(self):
        from builds.publicar import metricas
        linhas = [
            {"video_id": "generation_00078:build:celular", "publicado": True},
            {"video_id": "generation_00090:build:celular", "publicado": False},
            {"video_id": "generation_00095:estreia:celular", "publicado": True},
            {"video_id": "duelo_00012:duelo:celular", "publicado": True},
            {"video_id": None},
        ]
        with mock.patch.object(metricas, "publicados", return_value=linhas):
            self.assertEqual({"generation_00078"}, _GERACOES_PUBLICADAS())
        with mock.patch.object(metricas, "publicados",
                               side_effect=OSError("ledger ilegivel")):
            self.assertEqual(set(), _GERACOES_PUBLICADAS())


_GERACOES_PUBLICADAS = fila.geracoes_publicadas


class AsFalhasNaoVazamEntreDrenagens(unittest.TestCase):
    """Defeito 2 do conferente: com outro worker de pe, `drenar` voltava 0
    sem limpar, e a chamada seguinte da noite (outro provedor) devolvia as
    falhas da anterior, contadas em dobro no "fim: N erro(s)"."""

    def test_drenar_sem_a_trava_limpa_as_falhas_velhas(self):
        from builds.identity import worker
        worker._FALHAS[:] = ["generation_00098#character: ParedeDePlanos: x"]
        self.addCleanup(worker._FALHAS.clear)
        with mock.patch.object(worker.queue, "instancia_unica",
                               lambda: contextlib.nullcontext(False)), \
                mock.patch.object(worker, "_drenar",
                                  side_effect=AssertionError("drenou")):
            self.assertEqual(0, worker.drenar(so_provedor="digen"))
        self.assertEqual([], worker.falhas_da_ultima_rodada())


# ================================================================ o diario
def _linha(ts: datetime, status="log", fabrica="estudio", detalhe="x") -> str:
    return json.dumps({"ts": ts.isoformat(timespec="seconds"), "pid": 1,
                       "fabrica": fabrica, "canal": "builds",
                       "status": status, "detalhe": detalhe})


class APodaDoDiario(unittest.TestCase):
    AGORA = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)

    def test_fica_o_recente_e_o_erro_da_semana(self):
        h = lambda horas: self.AGORA - timedelta(hours=horas)  # noqa: E731
        linhas = [
            _linha(h(24 * 8), "erro", detalhe="erro de 8 dias"),
            _linha(h(24 * 5), "erro", detalhe="erro de 5 dias"),
            _linha(h(24 * 4), "ok", detalhe="ok de 4 dias"),
            _linha(h(80), "log", detalhe="log de 80 h"),
            _linha(h(70), "log", detalhe="log de 70 h"),
            "isto nao e json",
            _linha(h(1), "inicio", detalhe="inicio de 1 h"),
        ]
        ficam = [json.loads(x)["detalhe"]
                 for x in atividade._o_que_fica(linhas, self.AGORA)]
        self.assertEqual(["erro de 5 dias", "log de 70 h", "inicio de 1 h"],
                         ficam)

    def test_acima_do_teto_sai_primeiro_o_log_mais_velho(self):
        h = lambda minutos: self.AGORA - timedelta(minutes=minutos)  # noqa: E731
        linhas = [_linha(h(50), "ok", detalhe="ok velho"),
                  _linha(h(40), "log", detalhe="log velho"),
                  _linha(h(30), "log", detalhe="log novo"),
                  _linha(h(20), "erro", detalhe="erro"),
                  _linha(h(10), "inicio", detalhe="inicio")]
        with mock.patch.object(atividade, "_TETO_LINHAS", 2):
            ficam = [json.loads(x)["detalhe"]
                     for x in atividade._o_que_fica(linhas, self.AGORA)]
        # O erro fica fora do teto; dos comuns, sai o log mais velho e depois
        # o outro log antes de qualquer ok/inicio.
        self.assertEqual(["ok velho", "erro", "inicio"], ficam)

    def test_podar_so_mexe_acima_do_limite_e_reescreve_em_ordem(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        caminho = Path(tmp.name) / "atividade.jsonl"
        velho = self.AGORA - timedelta(days=4)
        novo = self.AGORA - timedelta(hours=2)
        caminho.write_text("\n".join([_linha(velho, detalhe="velho"),
                                      _linha(novo, detalhe="novo")]) + "\n",
                           encoding="utf-8")
        atividade._podar(caminho, agora=self.AGORA)        # abaixo do limite
        self.assertEqual(2, len(caminho.read_text(encoding="utf-8").splitlines()))
        with mock.patch.object(atividade, "_LIMITE_BYTES", 10):
            atividade._podar(caminho, agora=self.AGORA)
        restantes = [json.loads(x)["detalhe"]
                     for x in caminho.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(["novo"], restantes)


class Recentes(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.caminho = Path(tmp.name) / "atividade.jsonl"
        patcher = mock.patch.object(atividade, "_arquivo",
                                    return_value=self.caminho)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _escrever(self, eventos):
        with open(self.caminho, "w", encoding="utf-8") as fh:
            for evento in eventos:
                fh.write(evento + "\n")

    def test_respeita_o_n_pedido_alem_de_1200_linhas(self):
        agora = datetime(2026, 10, 5, tzinfo=timezone.utc)
        self._escrever(_linha(agora, detalhe=f"e{i}") for i in range(3000))
        saida = atividade.recentes(2500)
        self.assertEqual(2500, len(saida))
        self.assertEqual("e2999", saida[0]["detalhe"])
        self.assertEqual("e500", saida[-1]["detalhe"])

    def test_filtro_de_fabrica_vai_fundo_no_arquivo(self):
        # Antes: so as ultimas 1200 linhas eram lidas, e um evento do
        # PicassoIA antes delas nao existia para quem perguntava.
        agora = datetime(2026, 10, 5, tzinfo=timezone.utc)
        eventos = [_linha(agora, fabrica="picasso", detalhe="antigo")]
        eventos += [_linha(agora, fabrica="estudio") for _ in range(2000)]
        self._escrever(eventos)
        saida = atividade.recentes(5, fabrica="picasso")
        self.assertEqual(["antigo"], [e["detalhe"] for e in saida])

    def test_acentos_atravessam_a_borda_do_bloco(self):
        agora = datetime(2026, 10, 5, tzinfo=timezone.utc)
        self._escrever(_linha(agora, detalhe="ação " * 40) for _ in range(800))
        saida = atividade.recentes(800)
        self.assertEqual(800, len(saida))
        self.assertTrue(all(e["detalhe"].startswith("ação") for e in saida))

    def test_arquivo_ausente_e_n_zero(self):
        self.assertEqual([], atividade.recentes(10))
        self._escrever([_linha(datetime(2026, 10, 5, tzinfo=timezone.utc))])
        self.assertEqual([], atividade.recentes(0))


if __name__ == "__main__":
    unittest.main()
