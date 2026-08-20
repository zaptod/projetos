# -*- coding: utf-8 -*-
"""Contratos do Passe 5 do programa de arte (a magia fala seu elemento).

O que se trava aqui: o catálogo de skills nunca mais regride para cores
pálidas/quase-pretas/colididas (o saneamento medido vira gate); as
silhuetas por elemento e o ritual de canalização não explodem para
nenhum elemento/padrão; o trail dramático é keyed por projétil e
removível; decals só nascem para elementos com cicatriz definida.
"""

import collections
import unittest
from types import SimpleNamespace

import pygame

from neural_fights.core.skills import SKILL_DB
from neural_fights.simulation.simulacao import Simulador
from neural_fights.utils.palette import ELEMENT_PALETTES


def _lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _sat(c):
    mx, mn = max(c), min(c)
    return (mx - mn) / max(mx, 1)


class CatalogoDeCoresTests(unittest.TestCase):
    def test_nenhuma_skill_palida(self) -> None:
        """Saneamento do Passe 5: 21 skills tinham sat<0,25 (Benção era
        quase branco). O gate impede regressão."""
        palidas = [
            n for n, d in SKILL_DB.items()
            if d.get("cor") and _sat(d["cor"]) < 0.25
        ]
        self.assertEqual(palidas, [])

    def test_nenhuma_skill_quase_preta(self) -> None:
        """14 skills tinham lum<60 — invisíveis no chão escuro da arena
        neon (Buraco Negro era literalmente preto)."""
        escuras = [
            n for n, d in SKILL_DB.items()
            if d.get("cor") and _lum(d["cor"]) < 70
        ]
        self.assertEqual(escuras, [])

    def test_nenhuma_cor_com_tres_ou_mais_skills(self) -> None:
        """5 skills dividiam (255,255,150) — Mjolnir e Smite eram o mesmo
        pixel. Cada cor serve no máximo 2 skills."""
        grupos = collections.defaultdict(list)
        for n, d in SKILL_DB.items():
            if d.get("cor"):
                grupos[tuple(d["cor"])].append(n)
        colisoes = {c: ns for c, ns in grupos.items() if len(ns) >= 3}
        self.assertEqual(colisoes, {})


class SilhuetaPorElementoTests(unittest.TestCase):
    def test_todas_as_silhuetas_desenham_sem_explodir(self) -> None:
        fake = SimpleNamespace(tela=pygame.Surface((200, 200)))
        for elem in list(ELEMENT_PALETTES):
            proj = SimpleNamespace(nome="X", elemento=elem)
            Simulador._desenhar_projetil_skill_elemento(
                fake, proj, 100.0, 100.0, 6.0, (255, 120, 40), 0.7, 1.25
            )


class RitualDeCanalizacaoTests(unittest.TestCase):
    def test_todos_os_padroes_desenham_sem_explodir(self) -> None:
        """5 padrões (anéis/espiral/cristais/vórtice/faíscas) cobrindo os
        12 elementos, em qualquer progresso."""
        fake = SimpleNamespace(tela=pygame.Surface((400, 400)))
        for elem in list(ELEMENT_PALETTES):
            for vida in (3.0, 1.5, 0.1):
                canal = SimpleNamespace(
                    nome="Canal X", elemento=elem, cor=(200, 100, 255),
                    duracao_max=3.0, vida=vida, ativo=True,
                )
                lut = SimpleNamespace()
                Simulador._desenhar_canalizacao(
                    fake, lut, canal, (200, 200), 20
                )


class TrailDramaticoTests(unittest.TestCase):
    def test_trail_keyed_por_projetil_e_removivel(self) -> None:
        from neural_fights.effects.magic_vfx import MagicVFXManager

        MagicVFXManager.reset()
        try:
            mgr = MagicVFXManager.get_instance()
            t1 = mgr.get_or_create_trail(111, "FOGO")
            t2 = mgr.get_or_create_trail(222, "GELO")
            self.assertIsNot(t1, t2)
            self.assertIs(mgr.get_or_create_trail(111, "FOGO"), t1)
            mgr.remove_trail(111)
            self.assertNotIn(111, mgr.trails)
            mgr.remove_trail(999)  # remover inexistente não explode
        finally:
            MagicVFXManager.reset()


class DecalPorElementoTests(unittest.TestCase):
    def test_elementos_com_cicatriz_geram_decal(self) -> None:
        fake = SimpleNamespace(
            decals=[], _DECAL_ELEMENTO=Simulador._DECAL_ELEMENTO
        )
        Simulador._decal_elemento(fake, 100, 100, "FOGO", 14)
        self.assertEqual(len(fake.decals), 1)
        self.assertEqual(fake.decals[0].cor, (60, 30, 15))

    def test_default_nao_gera_decal(self) -> None:
        """Elemento sem identidade não suja o chão (e não estoura o teto
        de 40 decals com manchas genéricas)."""
        fake = SimpleNamespace(
            decals=[], _DECAL_ELEMENTO=Simulador._DECAL_ELEMENTO
        )
        Simulador._decal_elemento(fake, 100, 100, "DEFAULT", 14)
        self.assertEqual(fake.decals, [])


if __name__ == "__main__":
    unittest.main()
