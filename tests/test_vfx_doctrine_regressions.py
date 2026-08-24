# -*- coding: utf-8 -*-
"""Contratos da DOUTRINA DE EFEITOS (reforma "luta limpa").

A poluição visual foi medida antes da reforma: p50=80 objetos de VFX na
tela, p90=166, p99=321, até 10 textos simultâneos. A causa não era volume
de partículas — era REDUNDÂNCIA DE CANAL (um hit disparava 4 sistemas de
faísca e 2 ondas de choque) somada a 11 listas sem teto nenhum.

Este arquivo trava a doutrina: um evento = uma leitura por canal; toda
lista tem teto; a camada de atmosfera congela no hit-stop.
"""

import unittest
from types import SimpleNamespace

import pygame

from neural_fights.effects.budget import (
    PRIORIDADE_AMBIENTE,
    PRIORIDADE_IMPACTO,
    PRIORIDADE_SKILL,
    TETO_POR_LISTA,
    FrameBudget,
)
from neural_fights.effects.magic_vfx import (
    DramaticProjectileTrail,
    MagicVFXManager,
)
from neural_fights.effects.visual import Decal, FloatingText
from neural_fights.simulation.simulacao import Simulador


class OrcamentoTests(unittest.TestCase):
    def test_prioridade_manda_no_que_cabe(self) -> None:
        """Impacto ocupa o teto; ambiente para bem antes."""
        b = FrameBudget(teto=100)
        self.assertEqual(b.permitidas(90, 10, PRIORIDADE_IMPACTO), 10)
        self.assertEqual(b.permitidas(90, 10, PRIORIDADE_AMBIENTE), 0)

    def test_camada_c_congela_no_hit_stop(self) -> None:
        """Atmosfera e skill não nascem com o jogo congelado."""
        b = FrameBudget(teto=100)
        b.congelado = True
        self.assertEqual(b.permitidas(0, 10, PRIORIDADE_SKILL), 0)
        self.assertEqual(b.permitidas(0, 10, PRIORIDADE_AMBIENTE), 0)
        self.assertGreater(b.permitidas(0, 10, PRIORIDADE_IMPACTO), 0)

    def test_toda_lista_de_vfx_tem_teto(self) -> None:
        """As 11 listas que cresciam sem limite agora têm teto — e o
        funil descarta o MAIS ANTIGO (o evento novo é o relevante)."""
        fake = SimpleNamespace(budget=FrameBudget())
        for nome, teto in TETO_POR_LISTA.items():
            setattr(fake, nome, [])
            for i in range(teto + 25):
                Simulador._push_vfx(fake, nome, i, PRIORIDADE_IMPACTO)
            lista = getattr(fake, nome)
            self.assertEqual(len(lista), teto, nome)
            self.assertEqual(lista[-1], teto + 24, f"{nome}: perdeu o novo")


class TextosTests(unittest.TestCase):
    def _sim(self):
        sim = SimpleNamespace(
            budget=FrameBudget(), textos=[], tempo_visual=0.0,
            _texto_por_alvo={},
        )
        # o funil de texto chama o funil de VFX por dentro
        sim._push_vfx = lambda *a, **k: Simulador._push_vfx(sim, *a, **k)
        sim._push_texto = lambda *a, **k: Simulador._push_texto(sim, *a, **k)
        return sim

    def test_textos_simultaneos_nunca_passam_de_tres(self) -> None:
        sim = self._sim()
        for i in range(30):
            Simulador._push_texto(sim, 0, 0, f"T{i}", (255, 255, 255), 20)
        self.assertLessEqual(len(sim.textos), 3)

    def test_dano_no_mesmo_alvo_acumula_em_um_texto(self) -> None:
        """Ticks de canalização/DoT enchiam a tela a 10 textos/s."""
        sim = self._sim()
        alvo = SimpleNamespace()
        for _ in range(10):
            Simulador._push_texto(sim, 0, 0, 5, (255, 255, 255), alvo=alvo)
        self.assertEqual(len(sim.textos), 1)
        self.assertEqual(sim.textos[0].texto, "50")

    def test_alvos_diferentes_nao_se_misturam(self) -> None:
        sim = self._sim()
        a, b = SimpleNamespace(), SimpleNamespace()
        Simulador._push_texto(sim, 0, 0, 10, (255, 255, 255), alvo=a)
        Simulador._push_texto(sim, 0, 0, 10, (255, 255, 255), alvo=b)
        self.assertEqual(len(sim.textos), 2)

    def test_fatal_unico_por_morte(self) -> None:
        """Nasciam DOIS "FATAL!" no mesmo evento, sobrepostos."""
        sim = self._sim()
        for _ in range(4):
            Simulador._texto_fatal(sim, 0, 0)
        fatais = [t for t in sim.textos if t.texto == "FATAL!"]
        self.assertEqual(len(fatais), 1)

    def test_tiers_mandam_no_tamanho_do_numero(self) -> None:
        leve = FloatingText(0, 0, 12, (255, 255, 255), 99)
        pesado = FloatingText(0, 0, 250, (255, 255, 255), 99)
        self.assertLess(leve.fonte.get_height(), pesado.fonte.get_height())


class ConsolidacaoTests(unittest.TestCase):
    def test_uma_unica_fonte_de_faisca_e_de_onda(self) -> None:
        """O manager de ataque não cria mais faísca nem onda: sobraram o
        HitSpark e o Shockwave do simulador."""
        from neural_fights.effects.attack import AttackAnimationManager

        AttackAnimationManager.reset()
        try:
            mgr = AttackAnimationManager()
            atacante = SimpleNamespace(dados=SimpleNamespace(forca=20))
            alvo = SimpleNamespace(dados=SimpleNamespace(forca=10))
            mgr.criar_attack_impact(
                atacante=atacante, alvo=alvo, dano=40.0, posicao=(1.0, 1.0),
                direcao=0.0, tipo_dano="physical", is_critico=True,
            )
            self.assertEqual(len(mgr.sparks), 0)
            self.assertEqual(len(mgr.shockwaves), 0)
        finally:
            AttackAnimationManager.reset()

    def test_trilha_de_projetil_tem_teto(self) -> None:
        """Era a maior fonte do jogo: 140-420 partículas/s por projétil."""
        trail = DramaticProjectileTrail("FOGO")
        for _ in range(600):
            trail.update(1 / 60, 100.0, 100.0, 3.0)
        self.assertLessEqual(len(trail.particulas),
                             DramaticProjectileTrail.MAX_PARTICULAS)

    def test_aura_de_transform_nao_empilha(self) -> None:
        """O re-spawn de 0,7s com vida 2,0s empilhava TRÊS auras."""
        MagicVFXManager.reset()
        try:
            mgr = MagicVFXManager.get_instance()
            for _ in range(40):
                mgr.aura_persistente(1, 10.0, 10.0, 30.0, "FOGO")
            self.assertEqual(len(mgr.auras), 1)
            mgr.remover_aura_persistente(1)
            self.assertEqual(len(mgr.auras), 0)
        finally:
            MagicVFXManager.reset()

    def test_decal_faz_fade_e_morre(self) -> None:
        """O alpha era fixo em 200: 40 Surfaces desenhadas para sempre."""
        d = Decal(0, 0, 10, (50, 20, 20))
        alpha_inicial = d.alpha
        for _ in range(int(5.5 * 60)):
            d.update(1 / 60)
        self.assertLess(d.alpha, alpha_inicial)
        for _ in range(60):
            vivo = d.update(1 / 60)
        self.assertFalse(vivo)


class DecoracaoIdleTests(unittest.TestCase):
    def test_prop_de_arma_so_anima_atacando(self) -> None:
        """~20 animações idle giravam para sempre (dobradiça, espinhos,
        LED do drone, olho da sentinela) — movimento sem informação. O
        wrapper passa tempo_s=0 quando o dono NÃO está atacando."""
        from neural_fights.effects import weapon_render

        capturado = []
        original = weapon_render.desenhar
        weapon_render.desenhar = (
            lambda *a, **k: capturado.append(k.get("tempo_s", a[7] if len(a) > 7 else None))
        )
        try:
            fake = SimpleNamespace(
                tela=pygame.Surface((200, 200)),
                GRIP_PROFILES=Simulador.GRIP_PROFILES,
                tempo_visual=9.5,
                _efeito_visual_raridade=lambda *a, **k: None,
            )
            arma = SimpleNamespace(tipo="Reta", estilo="Katana",
                                   r=200, g=120, b=90, raridade="Comum")
            Simulador.desenhar_arma(fake, arma, (100, 100), 0.0, 1.8, 30,
                                    em_ataque=False)
            Simulador.desenhar_arma(fake, arma, (100, 100), 0.0, 1.8, 30,
                                    em_ataque=True)
        finally:
            weapon_render.desenhar = original
        self.assertEqual(capturado[0], 0.0, "prop animou parado")
        self.assertGreater(capturado[1], 0.0, "prop não animou atacando")


if __name__ == "__main__":
    unittest.main()
