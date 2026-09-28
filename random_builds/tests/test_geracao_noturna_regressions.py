# -*- coding: utf-8 -*-
"""Geracao noturna do canal de builds: duelos em rodizio, ate o teto.

Por que existe (27/09/2026): o canal de builds publicou ZERO videos em 22,
23, 25 e 26/09. Havia 14 tarefas `Historias_auto_*` e 10 de postagem, e
nenhuma que gerasse duelo ou build. E os 8 duelos feitos a mao naquele dia
tinham 5 com o mesmo p1 (Wren Telgyll), porque sem `--p1` o duelo pegava "o
ultimo criado na roleta" — e a ultima roleta era de 24/09.

O que este arquivo trava:

1. O RODIZIO: quem apareceu menos luta primeiro; o p2 tambem gira; par com
   titulo ja ocupado (em qualquer ordem) nunca e escolhido.
2. O RELOGIO: nada comeca se nao termina antes de :25 e dentro de 01h-06h.
3. O ESTOQUE: conta so o que a publicacao escolheria (o caso ZERO incluido).
4. A RODADA: teto, falhas, worker, ensaio que nao escreve no diario
   compartilhado, saida no arquivo com hora e nunca no console.
5. A TRAVA ENTRE PROCESSOS, com subprocesso de verdade: `travas.trava` e
   reentrante no mesmo processo, e um teste que segurasse a trava aqui
   mesmo nao provaria nada (e ja custou uma historia inteira em 08/09).
6. O LANCADOR: `--saida` aberto pelo Python, console para NUL, sem `>>`.

Nenhum teste aqui simula luta, abre navegador ou chama o schtasks.
"""
from __future__ import annotations

import inspect
import os
import random
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from builds.arena import rodizio
from builds.pipeline import noite, tarefas_noite
from builds.publicar import titulos

RAIZ = Path(__file__).resolve().parents[1]

CONFIG_PUB = {"titulos": {"duelo": "{p1} x {p2}"}}


def _fichas(*nomes, poder=None):
    poder = poder or {}
    return {n: {"nome": n, "forca": poder.get(n, 5.0), "mana": 5.0}
            for n in nomes}


class _Video:
    def __init__(self, id_, titulo, origem="duelo", perfil="celular",
                 quando=0.0, pendencias=None):
        self.id, self.titulo, self.origem, self.perfil = id_, titulo, origem, perfil
        self.quando, self.pendencias = quando, list(pendencias or [])


# ================================================================ rodizio
class RodizioDoP1(unittest.TestCase):

    def test_o_caso_de_27_09_wren_nao_volta_a_ser_p1(self):
        # Os 8 duelos daquele dia, na ordem real.
        pares = [("Wren", "Hakon"), ("Wren", "Emi"), ("Wren", "Otavio"),
                 ("Wren", "Aventino"), ("Wren", "Nyxaris"),
                 ("Roland", "Tyr"), ("Valkyrie", "Beatrix"), ("Hana", "Magnus")]
        fichas = _fichas("Wren", "Hakon", "Emi", "Otavio", "Aventino",
                         "Nyxaris", "Roland", "Tyr", "Valkyrie", "Beatrix",
                         "Hana", "Magnus", "Isandro", "Silas", "Kael")
        gerados = ["Silas", "Isandro", "Nyxaris", "Aventino", "Otavio",
                   "Emi", "Hakon", "Wren"]
        p1 = rodizio.escolher_p1(fichas, gerados, pares, random.Random(1),
                                 ocupados=set(), config=CONFIG_PUB)
        # Quem nunca lutou vem antes; entre eles, o da roleta mais recente.
        self.assertEqual("Isandro", p1)

    def test_o_ultimo_criado_nao_e_mais_o_padrao(self):
        # Todos com uso zero: o gerado mais recente ganha o EMPATE — mas so
        # o empate. Com uma luta a mais, ele vai para o fim da fila.
        fichas = _fichas("A", "B", "C", "Novo")
        p1 = rodizio.escolher_p1(fichas, ["A", "Novo"], [("Novo", "B")],
                                 random.Random(3), ocupados=set(),
                                 config=CONFIG_PUB)
        self.assertEqual("A", p1)

    def test_dez_duelos_seguidos_sem_repetir_protagonista(self):
        fichas = _fichas(*[f"P{i:02d}" for i in range(30)])
        pares, ocupados = [], set()
        vistos = []
        for i in range(10):
            p1, p2 = rodizio.escolher_par(fichas, [], random.Random(i),
                                          pares=pares, ocupados=ocupados,
                                          config=CONFIG_PUB)
            vistos += [p1, p2]
            pares.append((p1, p2))
            ocupados.add(titulos.chave(f"{p1} x {p2}"))
        # 10 duelos, 20 lugares, 30 nomes: ninguem pode repetir.
        self.assertEqual(len(vistos), len(set(vistos)), vistos)

    def test_banco_vazio_nao_inventa_ninguem(self):
        self.assertIsNone(rodizio.escolher_p1({}, [], [], random.Random(1),
                                              ocupados=set(),
                                              config=CONFIG_PUB))
        self.assertEqual((None, None),
                         rodizio.escolher_par({}, [], random.Random(1),
                                              pares=[], ocupados=set(),
                                              config=CONFIG_PUB))

    def test_quem_passa_p1_manda(self):
        fichas = _fichas("A", "B", "C")
        p1, p2 = rodizio.escolher_par(fichas, [], random.Random(1), pares=[],
                                      ocupados=set(), config=CONFIG_PUB,
                                      p1="C")
        self.assertEqual("C", p1)
        self.assertIn(p2, ("A", "B"))


class RodizioDoP2(unittest.TestCase):

    def test_o_p2_nao_e_sempre_o_gerado_mais_recente(self):
        # O defeito espelhado: `escolher_adversario` devolve o gerado mais
        # recente que ainda nao lutou com o p1 — o mesmo nome para todo p1.
        fichas = _fichas("Wren", "Ana", "Bia", "Caio")
        pares = [("Ana", "Wren"), ("Bia", "Wren")]
        p2 = rodizio.escolher_p2("Caio", fichas, ["Wren"], pares,
                                 random.Random(1), ocupados=set(),
                                 config=CONFIG_PUB)
        self.assertNotEqual("Wren", p2)

    def test_par_com_titulo_ocupado_nunca_sai(self):
        fichas = _fichas("A", "B", "C")
        ocupados = {titulos.chave("A x B")}
        for semente in range(20):
            p2 = rodizio.escolher_p2("A", fichas, ["B"], [],
                                     random.Random(semente),
                                     ocupados=ocupados, config=CONFIG_PUB)
            self.assertEqual("C", p2)

    def test_a_ordem_inversa_tambem_esta_ocupada(self):
        fichas = _fichas("A", "B", "C")
        ocupados = {titulos.chave("B x A")}
        p2 = rodizio.escolher_p2("A", fichas, ["B"], [], random.Random(1),
                                 ocupados=ocupados, config=CONFIG_PUB)
        self.assertEqual("C", p2)

    def test_sem_par_livre_devolve_none(self):
        fichas = _fichas("A", "B")
        self.assertIsNone(rodizio.escolher_p2(
            "A", fichas, [], [], random.Random(1),
            ocupados={titulos.chave("A x B")}, config=CONFIG_PUB))

    def test_titulos_ocupados_somam_ledger_e_disco(self):
        ledger = [{"titulo": "Ylva x Aldric", "publicado": True},
                  {"titulo": "Nunca saiu x Ninguem", "publicado": False}]
        ocupados = rodizio.titulos_ocupados([("Wren", "Emi")], ledger,
                                            config=CONFIG_PUB)
        self.assertIn(titulos.chave("Ylva x Aldric"), ocupados)
        self.assertIn(titulos.chave("Wren x Emi"), ocupados)
        self.assertNotIn(titulos.chave("Nunca saiu x Ninguem"), ocupados)

    def test_duelos_recentes_le_o_disco_na_ordem_do_id(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            for n, (a, b) in ((2, ("C", "D")), (1, ("A", "B"))):
                pasta = Path(tmp) / f"duelo_{n:05d}"
                pasta.mkdir()
                (pasta / "fight.json").write_text(
                    json.dumps({"luta": {"p1": a, "p2": b}}), encoding="utf-8")
            (Path(tmp) / "duelo_00003").mkdir()          # render interrompido
            self.assertEqual([("A", "B"), ("C", "D")],
                             rodizio.duelos_recentes(Path(tmp), n=None))
            self.assertEqual([("C", "D")],
                             rodizio.duelos_recentes(Path(tmp), n=1))

    def test_o_controller_usa_o_rodizio(self):
        # O duelo sem --p1 era "recentes[0]": o ultimo criado. A rodada
        # automatica nunca passa --p1, entao e aqui que o rodizio tem de estar.
        from builds.pipeline.controller import PipelineController
        fonte = inspect.getsource(PipelineController.duelo)
        self.assertIn("rodizio.escolher_par", fonte)
        self.assertNotIn("recentes[0]", fonte)


# ================================================================ relogio
CONFIG = dict(noite.PADRAO)


def _as(h, m, s=0):
    return datetime(2026, 9, 28, h, m, s)


class Relogio(unittest.TestCase):

    def test_janela_da_grade_e_de_25_a_55(self):
        proibida = CONFIG["grade_proibida"]
        self.assertFalse(noite.na_grade(24, proibida))
        self.assertTrue(noite.na_grade(25, proibida))
        self.assertTrue(noite.na_grade(37, proibida))
        self.assertTrue(noite.na_grade(54, proibida))
        self.assertFalse(noite.na_grade(55, proibida))

    def test_duelo_so_comeca_se_termina_antes_de_25(self):
        self.assertTrue(noite.cabe(_as(1, 2), 5, CONFIG))
        self.assertTrue(noite.cabe(_as(1, 19, 30), 5, CONFIG))
        # Terminar as :25 em ponto ja e encostar.
        self.assertFalse(noite.cabe(_as(1, 20), 5, CONFIG))
        self.assertFalse(noite.cabe(_as(1, 30), 5, CONFIG))
        self.assertTrue(noite.cabe(_as(1, 55), 5, CONFIG))

    def test_fora_da_madrugada_nada_cabe(self):
        self.assertFalse(noite.cabe(_as(0, 2), 5, CONFIG))       # post 00:37
        self.assertFalse(noite.cabe(_as(5, 57), 5, CONFIG))      # fecha 06:00
        self.assertFalse(noite.cabe(_as(23, 2), 5, CONFIG))
        self.assertFalse(noite.cabe(_as(14, 2), 5, CONFIG))

    def test_a_janela_atravessa_a_meia_noite(self):
        janela = {"inicio": 23, "fim": 6}
        self.assertTrue(noite.na_janela(23, janela))
        self.assertTrue(noite.na_janela(2, janela))
        self.assertFalse(noite.na_janela(6, janela))


# ================================================================ estoque
class Estoque(unittest.TestCase):

    def test_o_caso_zero_e_estoque_zero(self):
        # Sem video nenhum, o estoque e ZERO — e a rodada gera ate o teto.
        self.assertEqual([], noite.estoque_de_duelos(videos=[], publicados=[]))

    def test_passa_pelo_mesmo_funil_da_escolha(self):
        videos = [
            _Video("duelo_1:duelo:celular", "A x B", quando=1),     # ja saiu
            _Video("duelo_2:duelo:celular", "C x D", quando=2),     # titulo no ar
            _Video("duelo_3:duelo:celular", "E x F", quando=3),     # conta
            _Video("duelo_4:duelo:celular", "E x F", quando=4),     # gemeo do 3
            _Video("duelo_5:duelo:normal", "G x H", perfil="normal",
                   quando=5),                                    # 16:9
            _Video("generation_9:build:celular", "Build", "build", quando=6),
            _Video("duelo_6:duelo:celular", "I x J", quando=7,
                   pendencias=["mudo"]),
            _Video("duelo_7:duelo:celular", "K x L", quando=8),     # conta
        ]
        ledger = [
            {"video_id": "duelo_1:duelo:celular", "titulo": "A x B",
             "publicado": True},
            {"video_id": "duelo_0:duelo:celular", "titulo": "C x D",
             "publicado": True},
            # Tentativa que nao saiu nao tira ninguem da fila.
            {"video_id": "duelo_7:duelo:celular", "titulo": "K x L",
             "publicado": False},
        ]
        fila = noite.estoque_de_duelos(videos=videos, publicados=ledger)
        self.assertEqual(["duelo_3:duelo:celular", "duelo_7:duelo:celular"],
                         [v.id for v in fila])

    def test_teto_vem_da_cota_sobre_os_horarios(self):
        pub = {"grade": {"mistura": {"duelo": 4, "build": 3, "estreia": 1,
                                     "torneio": 0}}}
        self.assertEqual(5.0, noite.duelos_por_dia(pub, horarios=10))
        self.assertEqual(10, noite.teto_de_duelos({"dias_de_gordura": 2},
                                                  pub, horarios=10))
        sem_duelo = {"grade": {"mistura": {"duelo": 0, "build": 3}}}
        self.assertEqual(0, noite.teto_de_duelos({"dias_de_gordura": 2},
                                                 sem_duelo, horarios=10))


# ================================================================= rodada
class _Relogio:
    """Anda `passo` minutos a cada duelo gerado; parado entre um e outro."""

    def __init__(self, inicio):
        self.agora = inicio

    def __call__(self):
        return self.agora

    def andar(self, minutos):
        self.agora += timedelta(minutes=minutos)


class Rodada(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Diario do dia numa pasta descartavel, e trava com nome proprio:
        # uma rodada de verdade na maquina nao pode derrubar o teste, nem o
        # teste escrever no log dela.
        for alvo, valor in (("LOGS", Path(self.tmp.name)),
                            ("TRAVA", f"teste_noite_{os.getpid()}")):
            patcher = mock.patch.object(noite, alvo, valor)
            patcher.start()
            self.addCleanup(patcher.stop)
        for alvo, valor in (("duelos_por_dia", lambda *a, **k: 5.0),):
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

    def _rodar(self, relogio, na_fila=3, jobs=(), falhar=0, drenar=None,
               proximo=None, **kw):
        self.gerados = []
        falhas = {"n": falhar}

        def gerar():
            if falhas["n"] > 0:
                falhas["n"] -= 1
                raise RuntimeError("pygame caiu")
            relogio.andar(4.3)
            self.gerados.append(relogio())
            return Path(f"duelo_{len(self.gerados):05d}")

        lista = list(jobs)
        return noite.rodar(config=dict(noite.PADRAO), relogio=relogio,
                           gerar_duelo=gerar, estoque=lambda: [0] * na_fila,
                           jobs=lambda: list(lista),
                           drenar_worker=drenar or (lambda **k: 0),
                           proximo=proximo or (lambda excluir=(): None),
                           tela=None, **kw)

    def test_fora_da_janela_nao_gera_nada(self):
        relogio = _Relogio(_as(23, 2))
        resultado = self._rodar(relogio)
        self.assertEqual("fora da janela", resultado["motivo"])
        self.assertEqual([], self.gerados)

    def test_gera_ate_o_teto_e_para_antes_de_25(self):
        relogio = _Relogio(_as(1, 2))
        resultado = self._rodar(relogio, na_fila=3)
        # teto 10 - 3 = 7 (6 pelo maximo da rodada), mas so 5 cabem
        # entre 01:02 e 01:25 a 4,3 min cada.
        self.assertEqual(5, len(resultado["duelos"]))
        self.assertEqual("janela", resultado["parou"])
        for instante in self.gerados:
            self.assertLess(instante, _as(1, 25))
        self.assertEqual(0, noite.codigo_de_saida(resultado))

    def test_estoque_cheio_nao_gera(self):
        relogio = _Relogio(_as(1, 2))
        resultado = self._rodar(relogio, na_fila=10)
        self.assertEqual([], self.gerados)
        self.assertEqual("estoque cheio", resultado["motivo"])
        # Rodada que nao fez nada nao faz barulho no diario compartilhado.
        self.assertEqual([], self.registros)

    def test_o_maximo_por_rodada_segura_o_caso_zero(self):
        relogio = _Relogio(_as(2, 55))
        resultado = self._rodar(relogio, na_fila=0)
        self.assertEqual(noite.PADRAO["maximo_de_duelos_por_rodada"],
                         len(resultado["duelos"]))

    def test_pedido_manual_ignora_o_teto_mas_nao_o_relogio(self):
        relogio = _Relogio(_as(1, 0))
        resultado = self._rodar(relogio, na_fila=10, duelos=8)
        self.assertEqual(5, len(resultado["duelos"]))
        self.assertEqual(8, resultado["alvo"])

    def test_duas_falhas_seguidas_param_e_viram_erro(self):
        relogio = _Relogio(_as(1, 2))
        resultado = self._rodar(relogio, na_fila=0, falhar=5)
        self.assertEqual([], resultado["duelos"])
        self.assertEqual(2, len(resultado["erros"]))
        self.assertEqual(1, noite.codigo_de_saida(resultado))
        self.assertTrue(any(r[0] == "erro" for r in self.registros))

    def _worker(self, relogio, fila, avanco, retorno=None):
        """Roda so o worker: estoque cheio e uma fila de jobs por provedor.

        `proximo(excluir)` devolve o primeiro provedor da fila fora de
        `excluir`; `drenar` que da certo tira um job daquele provedor."""
        chamadas = []
        fila = list(fila)
        retorno = retorno or {}

        def proximo(excluir=()):
            return next((p for p in fila if p not in excluir), None)

        def drenar(so_provedor=None, prazo=None):
            chamadas.append((so_provedor,
                             datetime.fromtimestamp(prazo).replace(second=0)))
            feitos = retorno.get(so_provedor, 1)
            if feitos:
                relogio.andar(avanco[so_provedor])
                fila.remove(so_provedor)
            return feitos

        resultado = self._rodar(relogio, na_fila=10,
                                jobs=[{"generation_id": "generation_00085"}],
                                drenar=drenar, proximo=proximo)
        return chamadas, resultado

    def test_imagem_recebe_prazo_de_8_min_antes_de_25(self):
        relogio = _Relogio(_as(3, 2))
        chamadas, resultado = self._worker(
            relogio, ["picasso", "digen"], {"picasso": 5, "digen": 13})
        # 03:02: imagem cabe (8 min) e so pode COMECAR job ate 03:17.
        # 03:07: o payoff leva 18 e terminaria 03:25 — nao comeca.
        self.assertEqual([("picasso", _as(3, 17))], chamadas)
        self.assertEqual("janela", resultado["parou"])
        self.assertEqual(1, resultado["jobs_do_worker"])

    def test_o_payoff_so_comeca_com_18_min_de_folga(self):
        # O CASO que motivou o orcamento por tipo: com um orcamento so (8
        # min), o payoff do Digen (12-15 min medidos) comecava as :16 e
        # terminava depois de :25.
        relogio = _Relogio(_as(4, 2))
        chamadas, resultado = self._worker(
            relogio, ["digen", "digen"], {"picasso": 5, "digen": 13})
        self.assertEqual([("digen", _as(4, 7))], chamadas)
        relogio = _Relogio(_as(4, 8))
        chamadas, _ = self._worker(relogio, ["digen"], {"digen": 13})
        self.assertEqual([], chamadas)

    def test_provedor_ocupado_passa_a_vez_para_o_proximo(self):
        # 03:03 de 28/09: PicassoIA preso pelas historias, Digen livre.
        relogio = _Relogio(_as(4, 2))
        chamadas, resultado = self._worker(
            relogio, ["picasso", "digen"], {"picasso": 5, "digen": 13},
            retorno={"picasso": 0, "digen": 1})
        self.assertEqual([("picasso", _as(4, 17)), ("digen", _as(4, 7))],
                         chamadas)
        self.assertEqual(1, resultado["jobs_do_worker"])

    def test_nada_anda_em_nenhum_provedor(self):
        relogio = _Relogio(_as(3, 2))
        chamadas, resultado = self._worker(
            relogio, ["picasso", "digen"], {"picasso": 1, "digen": 1},
            retorno={"picasso": 0, "digen": 0})
        self.assertEqual(["picasso", "digen"], [c[0] for c in chamadas])
        self.assertEqual(0, resultado["jobs_do_worker"])

    def test_sem_job_reivindicavel_o_worker_nem_abre(self):
        relogio = _Relogio(_as(3, 2))
        chamadas, resultado = self._worker(relogio, [], {})
        self.assertEqual([], chamadas)
        self.assertEqual(0, resultado["jobs_do_worker"])

    def test_quantos_cabem_conta_o_caso_zero(self):
        self.assertEqual(0, noite.quantos_cabem(_as(1, 20), 8, CONFIG))
        self.assertEqual(0, noite.quantos_cabem(_as(23, 0), 8, CONFIG))
        self.assertEqual(2, noite.quantos_cabem(_as(1, 2), 8, CONFIG))

    def test_fim_da_folga(self):
        self.assertEqual(_as(3, 25), noite.fim_da_folga(_as(3, 2), CONFIG))
        self.assertEqual(_as(3, 25),
                         noite.fim_da_folga(_as(3, 2, 30), CONFIG))
        # Ja dentro da janela da grade, ou fora da madrugada: agora mesmo.
        self.assertEqual(_as(3, 40), noite.fim_da_folga(_as(3, 40), CONFIG))
        self.assertEqual(_as(0, 30), noite.fim_da_folga(_as(0, 30), CONFIG))
        # Perto das 6h, quem manda e o fim da janela pesada.
        self.assertEqual(_as(6, 0), noite.fim_da_folga(_as(5, 56), CONFIG))

    def test_orcamento_por_tipo_de_job(self):
        self.assertEqual(18, noite.minutos_do_job("digen", CONFIG))
        self.assertEqual(8, noite.minutos_do_job("picasso", CONFIG))
        antigo = {"minutos_por_job_do_worker": 7}
        self.assertEqual(7, noite.minutos_do_job("picasso", antigo))

    def test_ensaio_nao_escreve_no_diario_compartilhado(self):
        relogio = _Relogio(_as(1, 2))
        resultado = self._rodar(relogio, na_fila=3, ensaio=True)
        self.assertTrue(resultado["duelos"])
        self.assertEqual([], self.registros)

    def test_ensaio_fora_da_janela_segue_e_diz_o_que_faria(self):
        relogio = _Relogio(_as(23, 2))
        resultado = self._rodar(relogio, na_fila=3, ensaio=True)
        self.assertNotEqual("fora da janela", resultado.get("motivo"))
        texto = noite.diario_do_dia(_as(23, 2)).read_text(encoding="utf-8")
        self.assertIn("Numa rodada real eu sairia aqui", texto)

    def test_a_saida_vai_para_o_diario_com_hora_e_nao_para_o_console(self):
        relogio = _Relogio(_as(1, 2))
        console = mock.Mock()
        console.isatty.return_value = False                 # o do Agendador
        with mock.patch.object(sys, "stdout", console):
            self._rodar(relogio, na_fila=9)
        console.write.assert_not_called()
        texto = noite.diario_do_dia(_as(1, 2)).read_text(encoding="utf-8")
        self.assertRegex(texto, r"\d\d:\d\d:\d\d \[noite\] disparo das 01:02")

    def test_pausa_da_vila_segura_a_rodada(self):
        relogio = _Relogio(_as(1, 2))
        with mock.patch("builds.identity.controle.pausado_para",
                        return_value=True):
            resultado = self._rodar(relogio)
        self.assertEqual("pausado", resultado["motivo"])
        self.assertEqual([], self.gerados)


class PrazoDentroDoWorker(unittest.TestCase):
    """O worker nao comeca job (nem tentativa nova) depois do prazo.

    `limite=1` nao bastava: um job que falha volta para a fila e e
    reivindicado de novo NA MESMA passada, e a passada so para quando algum
    conclui. Tres tentativas de imagem cabem em 15 min.
    """

    def test_drenar_so_do_provedor_pedido(self):
        from builds.identity import worker
        chamadas = []
        with mock.patch.object(worker.queue, "reabrir", return_value=0), \
                mock.patch.object(worker, "_resolver_no_disco", return_value=0), \
                mock.patch.object(worker, "_explicar_parada"), \
                mock.patch.object(worker, "_passada",
                                  side_effect=lambda p, *a, **k:
                                  chamadas.append((p, k.get("prazo"))) or (0, None)):
            worker._drenar(False, True, False, None, so_provedor="digen",
                           prazo=4102444800.0)
        self.assertEqual([("digen", 4102444800.0)], chamadas)

    def test_prazo_vencido_nao_abre_passada(self):
        from builds.identity import worker
        chamadas = []
        with mock.patch.object(worker.queue, "reabrir", return_value=0), \
                mock.patch.object(worker, "_resolver_no_disco", return_value=0), \
                mock.patch.object(worker, "_explicar_parada"), \
                mock.patch.object(worker, "_passada",
                                  side_effect=lambda p, *a, **k:
                                  chamadas.append(p) or (0, None)):
            worker._drenar(False, True, False, None, prazo=1.0)
        self.assertEqual([], chamadas)

    def test_passada_com_prazo_vencido_nem_reivindica(self):
        from builds.identity import worker
        with mock.patch.object(worker.queue, "claim") as claim:
            self.assertEqual((0, None), worker._passada(
                "picasso", False, True, False, None, prazo=1.0))
        claim.assert_not_called()

    def test_o_prazo_para_a_passada_entre_um_job_e_outro(self):
        import contextlib
        from builds.identity import worker
        relogio = {"agora": 1000.0}
        jobs = [{"job_id": "g#character", "generation_id": "g",
                 "slot": "character"},
                {"job_id": "g#weapon", "generation_id": "g", "slot": "weapon"}]
        reivindicados = []

        def claim(*a, **k):
            if not jobs:
                return None
            reivindicados.append(jobs[0]["job_id"])
            return jobs.pop(0)

        def processar(client, job, ajustes, rerender, preview):
            relogio["agora"] = 2000.0              # o job passou do prazo
            return Path("imagem.png")

        cliente = mock.Mock()
        cliente.creditos.return_value = None
        with mock.patch.object(worker.queue, "claim", side_effect=claim), \
                mock.patch.object(worker.queue, "concluir"), \
                mock.patch.object(worker.time, "time",
                                  side_effect=lambda: relogio["agora"]), \
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
                mock.patch("builds.travas.do_perfil",
                           return_value=f"teste_prazo_{os.getpid()}"), \
                mock.patch("builds.atividade.fabrica",
                           side_effect=lambda *a, **k:
                           contextlib.nullcontext()):
            feitos, erro = worker._passada("picasso", False, True, False,
                                           None, prazo=1500.0)
        self.assertEqual((1, None), (feitos, erro))
        # O segundo job NAO foi reivindicado: o prazo venceu no primeiro.
        self.assertEqual(["g#character"], reivindicados)


class TravaEntreProcessos(unittest.TestCase):
    """Com SUBPROCESSO: no mesmo processo a trava e reentrante e o teste
    passaria sem provar nada."""

    def test_segunda_rodada_sai_se_outro_processo_tem_a_trava(self):
        nome = f"teste_noite_trava_{os.getpid()}"
        codigo = ("import sys, time\n"
                  "from builds import travas\n"
                  f"with travas.trava({nome!r}) as minha:\n"
                  "    print('PEGUEI' if minha else 'NAO', flush=True)\n"
                  "    sys.stdin.readline()\n")
        proc = subprocess.Popen([sys.executable, "-c", codigo], cwd=str(RAIZ),
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                text=True)
        try:
            self.assertEqual("PEGUEI", proc.stdout.readline().strip())
            with tempfile.TemporaryDirectory() as tmp, \
                    mock.patch.object(noite, "TRAVA", nome), \
                    mock.patch.object(noite, "LOGS", Path(tmp)), \
                    mock.patch("builds.identity.controle.pausado_para",
                               return_value=False):
                chamado = []
                resultado = noite.rodar(
                    config=dict(noite.PADRAO), relogio=lambda: _as(1, 2),
                    gerar_duelo=lambda: chamado.append(1),
                    estoque=lambda: [], jobs=lambda: [], tela=None)
            self.assertEqual("ja rodando", resultado["motivo"])
            self.assertEqual([], chamado)
        finally:
            proc.stdin.write("\n")
            proc.stdin.flush()
            proc.wait(timeout=30)

    def test_a_trava_de_producao_tem_nome_proprio(self):
        # Nao pode ser a das historias (`historias__auto`): a rodada de
        # builds nao usa o LLM, e dividir a trava faria uma historia de 2 h
        # segurar os duelos da madrugada inteira.
        self.assertEqual("builds__gerar", noite.TRAVA)


# =============================================================== lancador
class Lancador(unittest.TestCase):

    def test_saida_aberta_pelo_python_e_console_em_nul(self):
        texto = tarefas_noite.conteudo_do_lancador(
            r"C:\Python314\python.exe", Path(r"E:\projetos\random_builds"),
            Path(r"E:\projetos\random_builds\outputs\_logs\gerar_saida.txt"))
        self.assertIn("main.py noite %* --saida", texto)
        self.assertIn("> NUL 2>&1", texto)
        self.assertNotIn(">>", texto)
        self.assertIn("-u -X utf8", texto)

    def test_lancador_no_disco_sem_cr_dobrado(self):
        # `write_text` no Windows traduz cada LF de novo: o CRLF viraria
        # CR CR LF. O `auto.cmd` das historias saiu assim.
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(tarefas_noite, "caminho_do_lancador",
                                  return_value=Path(tmp) / "gerar.cmd"), \
                mock.patch.object(tarefas_noite, "caminho_da_saida",
                                  return_value=Path(tmp) / "s.txt"):
            bruto = tarefas_noite.escrever_lancador().read_bytes()
        self.assertNotIn(b"\r\r", bruto)
        self.assertIn(b"\r\n", bruto)

    def test_instalar_esconde_a_janela_e_endurece(self):
        chamadas = []

        class _Proc:
            returncode, stdout, stderr = 0, "OK", ""

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(tarefas_noite, "caminho_do_lancador",
                                  return_value=Path(tmp) / "gerar.cmd"), \
                mock.patch.object(tarefas_noite, "caminho_da_saida",
                                  return_value=Path(tmp) / "s.txt"), \
                mock.patch.object(tarefas_noite, "_schtasks",
                                  side_effect=lambda a: chamadas.append(a)
                                  or _Proc()), \
                mock.patch.object(tarefas_noite.tarefas_windows, "endurecer",
                                  return_value={"ok": True, "mensagem": ""}) \
                as endurecer, \
                mock.patch.object(tarefas_noite.tarefas_windows, "acao_oculta",
                                  side_effect=lambda l: f"wscript {l}"):
            fichas = tarefas_noite.instalar([1, 5], minuto=2)
        self.assertEqual(["NeuralFights_gerar_01", "NeuralFights_gerar_05"],
                         [f["tarefa"] for f in fichas])
        self.assertIn("01:02", chamadas[0])
        self.assertIn("LIMITED", chamadas[0])
        self.assertTrue(chamadas[0][chamadas[0].index("/TR") + 1]
                        .startswith("wscript"))
        self.assertEqual(2, endurecer.call_count)

    def test_as_horas_do_config_ficam_na_madrugada_e_fora_da_grade(self):
        config = noite.carregar()
        for hora in config["horas"]:
            self.assertTrue(noite.na_janela(hora, config["janela_pesada"]),
                            hora)
        self.assertFalse(noite.na_grade(config["minuto"],
                                        config["grade_proibida"]))


class SaidaDoMain(unittest.TestCase):

    def test_saida_sai_do_argv_e_abre_o_arquivo(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("main_rb",
                                                      RAIZ / "main.py")
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "saida.txt"
            argv, arquivo = modulo._redirecionar_saida(
                ["main.py", "noite", "--ensaio", "--saida", str(alvo)])
            try:
                self.assertEqual(["main.py", "noite", "--ensaio"], argv)
                arquivo.write("linha\n")
            finally:
                arquivo.close()
            self.assertEqual("linha\n", alvo.read_text(encoding="utf-8"))
            self.assertEqual((["main.py"], None),
                             modulo._redirecionar_saida(["main.py"]))


if __name__ == "__main__":
    unittest.main()
