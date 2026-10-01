# -*- coding: utf-8 -*-
"""Corrente V2: bola física com momento e enlace (rework de 01/10/2026).

Antes do rework a corrente não tinha mecânica própria. O golpe era o setor
instantâneo da espada com outros números e conectava no 1º tick da janela,
com a bola longe do alvo: na linha de base (corpus completo, fixture
engine), só 60 de 1095 acertos (5,5%) tinham a bola encostada no corpo, e a
folga mediana era de 1,10 m.

Decisões do Adrian (Grimório, 01/10):
- ``corrente-mecanica``: bola física;
- ``corrente-estilos``: pesadas com momento, leves com enlace;
- ``corrente-seeds-antigas``: a chave vale só para lutas novas.

Daí os quatro grupos de teste: a física isolada (pêndulo), os fakes de
contrato, a luta antiga idêntica com a chave desligada e a sonda que não
muda a luta.
"""

from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from neural_fights.core import agarrao, corrente
from neural_fights.simulation.simulacao import Simulador

RAIZ = Path(__file__).resolve().parents[1]
DT = 1.0 / 60.0


def _arma(estilo="Mangual", comp_corrente=40.0, comp_ponta=34.0, peso=5.3):
    return SimpleNamespace(
        tipo="Corrente", estilo=estilo, nome=f"Teste {estilo}",
        comp_corrente=comp_corrente, comp_ponta=comp_ponta, peso=peso,
        largura_ponta=9.0, dano=15.0,
    )


def _lutador(arma, x=0.0, y=0.0, tamanho=1.8):
    return SimpleNamespace(
        dados=SimpleNamespace(arma_obj=arma, tamanho=tamanho, forca=6.5, nome="t"),
        pos=[x, y], vel=[0.0, 0.0], angulo_olhar=0.0, angulo_arma_visual=0.0,
        atacando=False, timer_animacao=0.0, ataque_id=0, corrente_v2=True,
        morto=False,
    )


def _golpe(arma, distancia, *, dt=DT, guarda_s=0.5, dono=None):
    """Guarda parada e UM golpe contra um alvo parado a ``distancia`` (m).

    Devolve ``(primeiro_acerto, trajetoria)``: o acerto é ``(t, contato)``
    ou None; a trajetória tem ``(t, distancia_bola_mao, comprimento)``.
    """
    a = dono or _lutador(arma)
    alvo = _lutador(arma, distancia, 0.0)
    for _ in range(int(round(guarda_s / dt))):
        corrente.atualizar_bola(a, alvo, dt)
    _, _, _, total = corrente._fases()
    a.atacando, a.ataque_id, a.timer_animacao = True, a.ataque_id + 1, total
    comp = corrente.comprimento(arma, corrente.raio_corpo(a))
    t, acerto, trajetoria = 0.0, None, []
    while a.timer_animacao > 0.0:
        a.timer_animacao -= dt
        t += dt
        bola = corrente.atualizar_bola(a, alvo, dt)
        hx, hy = corrente.mao(a)
        trajetoria.append((t, math.hypot(bola.x - hx, bola.y - hy), comp))
        if acerto is None:
            ok, _ = corrente.verificar_golpe(a, alvo)
            if ok:
                acerto = (t, dict(corrente.contato_do_golpe(a)))
    return acerto, trajetoria


class PenduloTests(unittest.TestCase):
    """A bola isolada: corrente presa, momento, zona morta e v²."""

    def test_a_bola_nunca_passa_do_comprimento_da_corrente(self):
        for estilo, cc, cp, peso in (("Mangual", 40, 34, 5.3), ("Chicote", 123, 7, 1.9)):
            with self.subTest(estilo=estilo):
                arma = _arma(estilo, cc, cp, peso)
                _, trajetoria = _golpe(arma, 3.2)
                for _, r, comp in trajetoria:
                    self.assertLessEqual(r, comp + 1e-9)

    def test_na_guarda_a_corrente_gira_recolhida(self):
        arma = _arma()
        a = _lutador(arma)
        for _ in range(90):
            bola = corrente.atualizar_bola(a, None, DT)
        hx, hy = corrente.mao(a)
        comp = corrente.comprimento(arma, corrente.raio_corpo(a))
        r = math.hypot(bola.x - hx, bola.y - hy)
        self.assertAlmostEqual(r / comp, corrente.RAIO_OCIOSO_FRAC, delta=0.08)
        self.assertGreater(bola.velocidade(), 0.5 * corrente.OMEGA_OCIOSO * r)

    def test_golpe_da_distancia_ideal_sai_forte_e_na_fase_de_golpe(self):
        arma = _arma()
        ideal = corrente.alcances(_lutador(arma))["ideal"]
        acerto, _ = _golpe(arma, ideal)
        self.assertIsNotNone(acerto)
        t, contato = acerto
        preparo, golpe, _, _ = corrente._fases()
        self.assertGreaterEqual(t, preparo)
        self.assertLessEqual(t, preparo + golpe)
        # do meio do anel a corrente sai quase toda: acima da referência
        self.assertGreater(contato["v"], contato["v_ref"])
        self.assertGreater(contato["mult"], 1.2)
        self.assertLessEqual(contato["folga_m"], 0.0)

    def test_zona_morta_natural_e_fim_do_alcance(self):
        arma = _arma("Corrente com Peso", 70, 29, 7.5)
        alc = corrente.alcances(_lutador(arma))
        self.assertGreater(alc["morta"], 0.5)
        perto, _ = _golpe(arma, alc["morta"] * 0.7)
        longe, _ = _golpe(arma, alc["max"] * 1.1)
        self.assertIsNone(perto, "perto demais a bola passa por fora do corpo")
        self.assertIsNone(longe)

    def test_dano_cresce_com_a_velocidade_da_bola(self):
        arma = _arma("Meteor Hammer", 88, 42, 5.5)
        alc = corrente.alcances(_lutador(arma))
        mults = []
        for d in (alc["morta"] + 0.4, alc["ideal"] - 0.9, alc["ideal"]):
            acerto, _ = _golpe(arma, d)
            self.assertIsNotNone(acerto, d)
            mults.append((acerto[1]["v"], acerto[1]["mult"]))
        # corrente encurtada para o alvo perto = bola lenta = menos dano
        self.assertLess(mults[0][0], mults[1][0])
        self.assertLess(mults[1][0], mults[2][0])
        self.assertLess(mults[0][1], mults[1][1])
        self.assertLess(mults[1][1], mults[2][1])
        self.assertGreaterEqual(mults[0][1], corrente.MULT_DANO_MIN)
        self.assertEqual(mults[2][1], corrente.MULT_DANO_MAX)

    def test_nao_acerta_no_preparo_nem_parado(self):
        arma = _arma()
        a = _lutador(arma)
        for _ in range(30):
            bola = corrente.atualizar_bola(a, None, DT)
        alvo = _lutador(arma, bola.x, bola.y)  # o alvo EM CIMA da bola
        corrente.atualizar_bola(a, alvo, DT)
        self.assertFalse(corrente.verificar_golpe(a, alvo)[0])  # sem golpe
        _, _, _, total = corrente._fases()
        a.atacando, a.ataque_id, a.timer_animacao = True, 1, total
        a.timer_animacao -= DT
        corrente.atualizar_bola(a, alvo, DT)
        ok, motivo = corrente.verificar_golpe(a, alvo)
        self.assertFalse(ok)
        self.assertIn("fase de golpe", motivo)

    def test_empurrao_vai_na_direcao_da_bola(self):
        arma = _arma()
        acerto, _ = _golpe(arma, corrente.alcances(_lutador(arma))["ideal"])
        contato = acerto[1]
        # A bola varre de lado: o empurrão NÃO é o eixo atacante→alvo (0°).
        self.assertGreater(abs(math.degrees(contato["direcao"])), 30.0)

    def test_forehand_e_backhand_alternam_sem_rng(self):
        arma = _arma()
        a = _lutador(arma)
        d = corrente.alcances(a)["ideal"]
        primeiro, _ = _golpe(arma, d, dono=a)
        segundo, _ = _golpe(arma, d, dono=a)
        self.assertIsNotNone(primeiro)
        self.assertIsNotNone(segundo)
        # sentidos opostos: o empurrão troca de lado
        self.assertLess(math.sin(primeiro[1]["direcao"]) * math.sin(segundo[1]["direcao"]), 0.0)

    def test_deterministico_sem_rng_e_sem_animador(self):
        def proibido(*_a, **_k):
            raise AssertionError("a corrente V2 não pode sortear nem ler o animador")

        arma = _arma("Rope Dart", 113, 14, 2.1)
        with patch.object(random, "random", proibido), \
                patch.object(random, "uniform", proibido), \
                patch("neural_fights.effects.weapon_animations.get_weapon_animation_manager",
                      proibido):
            um, traj_um = _golpe(arma, 3.3)
            dois, traj_dois = _golpe(arma, 3.3)
        self.assertEqual(um, dois)
        self.assertEqual(traj_um, traj_dois)

    def test_subpassos_seguram_o_resultado_com_dt_maior(self):
        arma = _arma()
        ideal = corrente.alcances(_lutador(arma))["ideal"]
        fino, _ = _golpe(arma, ideal, dt=1 / 60)
        grosso, _ = _golpe(arma, ideal, dt=1 / 30)
        self.assertIsNotNone(fino)
        self.assertIsNotNone(grosso)
        self.assertAlmostEqual(fino[0], grosso[0], delta=1 / 30 + 1e-9)
        self.assertAlmostEqual(fino[1]["mult"], grosso[1]["mult"], delta=0.15)


class FamiliasEEnlaceTests(unittest.TestCase):
    def test_familias_seguem_a_decisao(self):
        for estilo in ("Mangual", "Meteor Hammer", "Corrente com Peso", "Flail (Mangual)"):
            self.assertEqual(corrente.familia(_arma(estilo)), "pesada", estilo)
        for estilo in ("Chicote", "Kusarigama", "Rope Dart"):
            self.assertEqual(corrente.familia(_arma(estilo)), "leve", estilo)

    def test_physics_chain_do_catalogo_decide_quem_tem_bola(self):
        self.assertTrue(corrente.eh_corrente(_arma()))
        self.assertFalse(corrente.eh_corrente(SimpleNamespace(tipo="Reta")))
        self.assertFalse(corrente.eh_corrente(None))

    def test_enlace_dura_entre_04_e_06_s(self):
        for cc, cp in ((20, 5), (40, 34), (86, 20), (123, 7), (300, 60)):
            dur = agarrao.duracao_enlace(_arma("Chicote", cc, cp))
            self.assertGreaterEqual(dur, 0.4)
            self.assertLessEqual(dur, 0.6)

    def test_passo_do_enlace_puxa_ate_a_distancia_no_tempo_do_enlace(self):
        ini, alvo = [0.0, 0.0], [5.0, 0.0]
        restante = 0.5
        while restante > 0.0:
            restante -= DT
            dx, dy = agarrao.passo_enlace(ini, alvo, 3.0, max(0.0, restante), DT)
            alvo[0] += dx
            alvo[1] += dy
        self.assertAlmostEqual(alvo[0], 3.0, places=6)
        self.assertEqual(agarrao.passo_enlace(ini, [2.0, 0.0], 3.0, 0.3, DT), (0.0, 0.0))


def _sim_fake(p1, p2):
    sim = object.__new__(Simulador)
    sim.p1, sim.p2 = p1, p2
    return sim


def _par_lutadores(distancia=4.0):
    from tests import test_remaining_skill_regressions as _helpers

    p1 = _helpers.RemainingSkillRegressionTests._fighter("Dono", x=0.0)
    p2 = _helpers.RemainingSkillRegressionTests._fighter("Alvo", x=distancia)
    p1.dados.arma_obj = _arma("Chicote", 123, 7, 1.9)
    return p1, p2


class FakesDeContratoTests(unittest.TestCase):
    """Fakes sem ``__init__`` não podem quebrar: tudo é lido com padrão."""

    def test_simulador_fake_sem_atributos_novos(self):
        p1, p2 = _par_lutadores()
        sim = _sim_fake(p1, p2)
        sim._atualizar_enlaces(DT)  # sem _enlaces: nada a fazer
        sim._atualizar_correntes(DT)  # sem a chave no lutador: nada a fazer
        self.assertNotIn("corrente_bola", p1.__dict__)

    def test_verificar_golpe_sem_bola_nao_acerta(self):
        arma = _arma()
        a = _lutador(arma)
        a.atacando = True
        a.timer_animacao = corrente._fases()[3] - 0.3
        ok, motivo = corrente.verificar_golpe(a, _lutador(arma, 3.0))
        self.assertFalse(ok)
        self.assertIn("bola", motivo)

    def test_hitbox_sem_a_chave_usa_o_setor_antigo(self):
        from neural_fights.core.hitbox import sistema_hitbox

        p1, p2 = _par_lutadores(2.0)
        p1.dados.arma_obj.tipo = "Corrente"
        p1.atacando = True
        p1.timer_animacao = 0.95 - 0.12  # 0,12 s: ainda no preparo (0,20 s)
        p1.angulo_olhar = 0.0
        self.assertNotIn("corrente_v2", p1.__dict__)
        acertou, motivo = sistema_hitbox.verificar_colisao(p1, p2)
        # o setor antigo acerta no preparo, com a bola onde estiver
        self.assertTrue(acertou, motivo)
        self.assertIn("arco", motivo)
        p1.corrente_v2 = True
        acertou, motivo = sistema_hitbox.verificar_colisao(p1, p2)
        self.assertFalse(acertou)

    def test_enlace_trava_puxa_e_solta(self):
        p1, p2 = _par_lutadores(4.5)
        sim = _sim_fake(p1, p2)
        sim._enlaces = []
        self.assertTrue(sim._iniciar_enlace(p1, p2))
        self.assertFalse(sim._iniciar_enlace(p1, p2), "não enlaça duas vezes")
        self.assertEqual(p2.agarrao_papel, "enlacado")
        self.assertFalse(p2.pode_iniciar_acao())
        self.assertEqual(p1.contadores_luta["enlaces"], 1)
        dur = agarrao.duracao_enlace(p1.dados.arma_obj)
        alvo_d = agarrao.distancia_do_enlace(p1, p2)
        t = 0.0
        while t < dur + 2 * DT:
            sim._atualizar_enlaces(DT)
            t += DT
        self.assertEqual(sim._enlaces, [])
        self.assertIsNone(p2.agarrao_papel)
        self.assertEqual(p2.agarrao_timer, 0.0)
        self.assertAlmostEqual(math.hypot(p2.pos[0] - p1.pos[0], p2.pos[1] - p1.pos[1]),
                               alvo_d, delta=0.05)

    def test_dano_no_enlacado_solta_o_enlace(self):
        p1, p2 = _par_lutadores(4.5)
        sim = _sim_fake(p1, p2)
        sim._enlaces = []
        sim._iniciar_enlace(p1, p2)
        p2.agarrao_interrompido = True
        sim._atualizar_enlaces(DT)
        self.assertEqual(sim._enlaces, [])
        self.assertIsNone(p2.agarrao_papel)


class GeometriaCompartilhadaTests(unittest.TestCase):
    def test_empunhadura_e_ponta_antiga_batem_com_o_desenho_e_a_timeline(self):
        from neural_fights.recording import timeline

        self.assertEqual(
            Simulador.GRIP_PROFILES["Corrente"],
            {"offset_r": corrente.GRIP_OFFSET_R, "lateral_r": corrente.GRIP_LATERAL_R},
        )
        self.assertEqual(
            timeline.GRIP_PROFILES_PADRAO["Corrente"], Simulador.GRIP_PROFILES["Corrente"]
        )
        a = _lutador(_arma(), 1.0, 2.0)
        a.angulo_arma_visual = 37.0
        a.weapon_anim_lunge = 0.2
        _, _, px, py, _ = timeline.geometria_da_arma(
            1.0, 2.0, 37.0, 0.9, "Corrente", timeline.GRIP_PROFILES_PADRAO,
            corrente.ALCANCE_LEGADO_R, lunge=0.2)
        self.assertEqual(corrente.ponta_legada(a), (px, py))


def _rodar(codigo: str) -> str:
    """Roda num PROCESSO NOVO, como a regeração de uma luta em produção.

    O animador de arma é um singleton que guarda estado por ``id`` de
    lutador e nunca é zerado; no mesmo processo, ids reciclados de lutas
    anteriores entram na luta seguinte. Processo novo = luta de produção.
    """
    env = dict(os.environ)
    env.setdefault("SDL_VIDEODRIVER", "dummy")
    env.setdefault("SDL_AUDIODRIVER", "dummy")
    env["PYTHONIOENCODING"] = "utf-8"
    saida = subprocess.run(
        [sys.executable, "-c", codigo], cwd=str(RAIZ), env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=600,
    )
    if saida.returncode != 0:
        raise AssertionError(saida.stderr[-2000:])
    return saida.stdout.strip().splitlines()[-1]


_LUTA = """
import json
from neural_fights.tools import qualidade_luta as ql
from neural_fights.simulation.headless import HeadlessMatchRunner
from neural_fights.simulation.probes import FightQualityProbe
fonte = ql.FonteDeDados("engine")
saida = []
for p1, p2, seed, extra, sonda in {lutas!r}:
    mc = {{"p1_nome": p1, "p2_nome": p2, "cenario": "Arena", "best_of": 1}}
    mc.update(extra)
    probe = FightQualityProbe() if sonda else None
    r = HeadlessMatchRunner(mc, seed=seed, max_duration=120.0, probe=probe,
                            roster_provider=fonte.provider()).run()
    item = [p1, p2, seed, r.frames, r.winner_slot, r.reason, r.p1_hp, r.p2_hp]
    if probe is not None:
        m = probe.metricas(r)
        item.append([m["corrente_acertos"], m["corrente_contatos"]])
    saida.append(item)
print(json.dumps(saida))
"""


class DeterminismoAnimadorTests(unittest.TestCase):
    def test_mesma_luta_bate_processo_novo_apos_outra_luta(self):
        principal = (
            "Aurora o Bravo", "Jin a Protetora", 9020, {}, False,
        )
        intermediaria = (
            "Octavia o Lendário", "Nyx a Impiedosa", 30010, {}, False,
        )
        processo_novo = json.loads(_rodar(_LUTA.format(lutas=[principal])))[0]
        mesmo_processo = json.loads(_rodar(_LUTA.format(
            lutas=[principal, intermediaria, principal],
        )))

        self.assertEqual(mesmo_processo[0], processo_novo)
        self.assertEqual(mesmo_processo[2], processo_novo)

    def test_animador_nao_avanca_random_global_e_reseta_estados(self):
        from neural_fights.effects.weapon_animations import WeaponAnimationManager

        random.seed(9182)
        proximo_esperado = random.random()
        random.seed(9182)
        manager = WeaponAnimationManager(seed="luta-teste")
        fighter_id = 777
        manager.start_attack(
            fighter_id, "Reta", (0.0, 0.0), 0.0, weapon_style="Martelo",
        )
        for _ in range(40):
            manager.get_weapon_transform(
                fighter_id, "Reta", 0.0, (1.0, 0.0), 1.0 / 60.0,
                weapon_style="Martelo",
            )

        self.assertEqual(random.random(), proximo_esperado)
        self.assertIn(fighter_id, manager.animator.states)
        manager.reset("outra-luta")
        self.assertEqual(manager.animator.states, {})
        self.assertEqual(manager.active_effects, [])


class LutaAntigaIdenticaTests(unittest.TestCase):
    """Chave desligada (o padrão) = a luta antiga, bit a bit.

    Digitais medidas no código de ANTES do rework (12bcb09, 01/10/2026),
    cada luta num processo novo: Corrente com Peso × Dupla, Rope Dart ×
    Arremesso e Mangual × Chicote (as duas famílias).
    """

    DIGITAIS = [
        ["Aurora o Bravo", "Jin a Protetora", 9020, 1563, "p2", "knockout",
         0.0, 30.961651999999958],
        ["Adelaide a Justa", "Elara o Lendário", 9002, 2698, "p1", "knockout",
         95.87409000000004, 0.0],
        ["Octavia o Lendário", "Nyx a Impiedosa", 30010, 1939, "p1", "knockout",
         528.5279690934153, 0.0],
    ]

    def test_seed_antiga_identica_com_a_chave_desligada(self):
        from neural_fights.utils import config

        self.assertFalse(config.CORRENTE_V2, "a chave não pode nascer ligada")
        lutas = [(d[0], d[1], d[2], {}, False) for d in self.DIGITAIS]
        obtidas = json.loads(_rodar(_LUTA.format(lutas=lutas)))
        self.assertEqual(obtidas, self.DIGITAIS)

    def test_carimbo_falso_e_o_mesmo_que_sem_carimbo(self):
        lutas = [(d[0], d[1], d[2], {"corrente_v2": False}, False) for d in self.DIGITAIS[:1]]
        obtidas = json.loads(_rodar(_LUTA.format(lutas=lutas)))
        self.assertEqual(obtidas, self.DIGITAIS[:1])

    def test_chave_desligada_nao_cria_estado_novo_no_simulador(self):
        from neural_fights.utils import config

        sim = object.__new__(Simulador)
        sim.match_config = {}
        self.assertFalse(corrente.chave_ligada(sim.match_config))
        self.assertTrue(corrente.chave_ligada({"corrente_v2": True}))
        with patch.object(config, "CORRENTE_V2", True):
            self.assertTrue(corrente.chave_ligada({}))
            self.assertFalse(corrente.chave_ligada({"corrente_v2": False}))


class LutaNovaTests(unittest.TestCase):
    def test_bola_no_corpo_em_todo_acerto(self):
        d = LutaAntigaIdenticaTests.DIGITAIS[2]  # Mangual x Chicote: as duas famílias
        com = json.loads(_rodar(_LUTA.format(
            lutas=[(d[0], d[1], d[2], {"corrente_v2": True}, True)])))[0]
        acertos, contatos = com[-1]
        self.assertGreater(acertos, 0, "a luta tem de ter acerto de corrente para medir")
        self.assertEqual(contatos, acertos)

    def test_sonda_nao_muda_a_luta_nova(self):
        d = LutaAntigaIdenticaTests.DIGITAIS[1]
        sem = json.loads(_rodar(_LUTA.format(
            lutas=[(d[0], d[1], d[2], {"corrente_v2": True}, False)])))[0]
        com = json.loads(_rodar(_LUTA.format(
            lutas=[(d[0], d[1], d[2], {"corrente_v2": True}, True)])))[0]
        self.assertEqual(com[:8], sem)
        self.assertNotEqual(sem, LutaAntigaIdenticaTests.DIGITAIS[1], "a chave muda a luta")


class TimelineV2Tests(unittest.TestCase):
    """Doutrina: a luta nova também é invariante à sonda e ao desenho (VFX).

    Hash do estado da luta em CADA passo (``timeline.hash_estado``), pelo
    mesmo laço do gravador — que zera o animador de arma antes, como um
    processo novo.
    """

    @staticmethod
    def _rodar(**extra):
        from neural_fights.recording import timeline
        from neural_fights.tools import qualidade_luta as ql

        d = LutaAntigaIdenticaTests.DIGITAIS[2]
        return timeline.gravar_timeline(
            p1=d[0], p2=d[1], seed=d[2], cenario="Arena", resolucao=(540, 960),
            roster_provider=ql.FonteDeDados("engine").provider(), corrente_v2=True,
            hashes=True, max_duracao=20.0, **extra)

    def test_sonda_e_desenho_nao_mudam_a_luta_nova(self):
        sem = self._rodar(sonda=False)
        com = self._rodar(sonda=True)
        desenhada = self._rodar(sonda=True, desenhar=True)
        self.assertGreater(len(sem["hashes"]), 600)
        self.assertEqual(sem["hashes"], com["hashes"])
        self.assertEqual([h[0] for h in sem["hashes"]],
                         [h[0] for h in desenhada["hashes"]],
                         "o desenho (VFX) mudou o estado da luta")


class LedgerTests(unittest.TestCase):
    def test_alvos_da_corrente_existem_e_falam_da_chave_da_sonda(self):
        from neural_fights.tools import qualidade_luta as ql

        alvos = ql.carregar_alvos()
        metricas = {a["metrica"]: a for a in alvos.values()}
        self.assertIn("corrente_contato_no_acerto", metricas)
        self.assertEqual(metricas["corrente_contato_no_acerto"]["min"], 1.0)
        self.assertIn("winrate_corrente", metricas)
        resumo = ql.agregar([])
        self.assertIn("corrente_contato_no_acerto", resumo)
        self.assertIn("winrate_corrente", resumo)


if __name__ == "__main__":
    unittest.main()
