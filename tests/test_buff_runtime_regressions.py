"""Regression tests for the simple buff bridge and the shared status contract."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.combat import Buff, Channel, DotEffect
from core.entities import Lutador
from core.magic_system import STATUS_EFFECTS_DB, criar_status_effect, verificar_condicao
from core.skills import get_skill_data
from core.status_runtime import STATUS_RUNTIME


class BuffRuntimeRegressionTests(unittest.TestCase):
    @staticmethod
    def _fighter(name: str) -> Lutador:
        data = SimpleNamespace(
            nome=name,
            tamanho=1.7,
            forca=5.0,
            mana=5.0,
            resistencia=5.0,
            velocidade=5.0,
            classe="Guerreiro (Forca Bruta)",
            personalidade="Aleatorio",
            nome_arma="",
            arma_obj=None,
        )
        with patch("ai.AIBrain", return_value=None):
            return Lutador(data, 5.0, 5.0)

    @staticmethod
    def _add_class_skill(fighter: Lutador, name: str, cost: float | None = None) -> None:
        data = get_skill_data(name)
        fighter.skills_classe.append(
            {"nome": name, "custo": data.get("custo", 0.0) if cost is None else cost, "data": data}
        )
        fighter.cd_skills[name] = 0.0

    def test_simple_buff_aliases_are_consumed(self) -> None:
        fighter = self._fighter("Aliases")

        haste = Buff("Acelerar", fighter)
        overload = Buff("Sobrecarga", fighter)
        barrier = Buff("Barreira Divina", fighter)

        self.assertAlmostEqual(haste.buff_velocidade, 1.8)
        self.assertAlmostEqual(overload.buff_velocidade, 1.3)
        self.assertAlmostEqual(overload.buff_velocidade_ataque, 1.5)
        self.assertAlmostEqual(overload.mod_dano_recebido, 1.2)
        self.assertAlmostEqual(barrier.refletir, 0.3)

    def test_fury_modifies_melee_and_incoming_damage_once(self) -> None:
        fighter = self._fighter("Furious")
        fury = Buff("Grito de Guerra", fighter)
        fighter.buffs_ativos.append(fury)

        with patch("core.entities.random.random", return_value=1.0):
            damage, critical = fighter.calcular_dano_ataque(10.0)
        self.assertFalse(critical)
        self.assertAlmostEqual(damage, 10.0 * fighter.mod_dano * 1.8)

        life_before = fighter.vida
        fighter.tomar_dano(10.0, 0.0, 0.0)
        self.assertAlmostEqual(life_before - fighter.vida, 13.0)

    def test_buff_lifesteal_uses_central_healing_rules(self) -> None:
        attacker = self._fighter("Blood pact")
        target = self._fighter("Target")
        attacker.buffs_ativos.append(Buff("Pacto de Sangue", attacker))
        attacker.vida = attacker.vida_max - 20.0

        target.tomar_dano(10.0, 0.0, 0.0, atacante=attacker)
        self.assertAlmostEqual(attacker.vida, attacker.vida_max - 18.0)

        attacker._aplicar_efeito_status("NECROSE")
        target.invencivel_timer = 0.0
        life_before = attacker.vida
        target.tomar_dano(10.0, 0.0, 0.0, atacante=attacker)
        self.assertEqual(attacker.vida, life_before)

    def test_immortality_is_consumed_by_one_lethal_hit(self) -> None:
        fighter = self._fighter("Guardian angel")
        immortal = Buff("Anjo Guardi\u00e3o", fighter)
        fighter.buffs_ativos.append(immortal)
        fighter.vida = 20.0

        fighter.tomar_dano(100.0, 0.0, 0.0)

        self.assertFalse(fighter.morto)
        self.assertEqual(fighter.vida, 1.0)
        self.assertFalse(immortal.ativo)

        fighter.invencivel_timer = 0.0
        fighter.tomar_dano(2.0, 0.0, 0.0)
        self.assertTrue(fighter.morto)

        dot_target = self._fighter("Immortal against dot")
        dot_target.vida = 20.0
        dot_target.buffs_ativos.append(Buff("Anjo Guardi\u00e3o", dot_target))
        DotEffect("TEST", dot_target, 100.0, 0.5, (255, 255, 255)).atualizar(0.5)
        self.assertFalse(dot_target.morto)
        self.assertEqual(dot_target.vida, 1.0)

    def test_cast_is_atomic_and_determination_reduces_new_cooldown(self) -> None:
        insufficient = self._fighter("No mana")
        self._add_class_skill(insufficient, "Pacto de Sangue", cost=50.0)
        insufficient.mana = 0.0
        life_before = insufficient.vida

        self.assertFalse(insufficient.usar_skill_classe("Pacto de Sangue"))
        self.assertEqual(insufficient.vida, life_before)

        determined = self._fighter("Determined")
        determined.buffs_ativos.append(Buff("Determina\u00e7\u00e3o", determined))
        self._add_class_skill(determined, "Cura Menor", cost=0.0)
        determined.vida -= 30.0
        with patch("effects.audio.AudioManager.get_instance", return_value=None):
            self.assertTrue(determined.usar_skill_classe("Cura Menor"))
        self.assertAlmostEqual(determined.cd_skills["Cura Menor"], 7.5)

    def test_channel_healing_also_respects_necrosis(self) -> None:
        fighter = self._fighter("Photosynthesis")
        fighter.vida -= 20.0
        fighter._aplicar_efeito_status("NECROSE")
        channel = Channel("Fotoss\u00edntese", fighter)

        blocked = channel.atualizar(0.1)
        self.assertEqual(blocked[0]["valor"], 0.0)

        fighter.remover_debuffs()
        restored = channel.atualizar(0.1)
        self.assertAlmostEqual(restored[0]["valor"], 1.5)

    def test_legacy_catalog_is_a_synced_compatibility_view(self) -> None:
        self.assertEqual(
            STATUS_EFFECTS_DB["FRACO"]["mod_dano_causado"],
            STATUS_RUNTIME["FRACO"]["mod_dano_causado"],
        )
        self.assertEqual(STATUS_EFFECTS_DB["EXPOSTO"]["duracao"], 4.0)
        self.assertNotIn("mod_dano_causado", STATUS_EFFECTS_DB["MALDITO"])
        self.assertEqual(STATUS_EFFECTS_DB["MALDITO"]["mod_dano_recebido"], 1.3)

        overridden = criar_status_effect("FRACO", duracao_override=9.0)
        self.assertEqual(overridden.duracao, 9.0)
        self.assertEqual(overridden.tempo_restante, 9.0)

        regeneration = criar_status_effect("REGENERANDO")
        active, value = regeneration.update(1.0, None)
        self.assertTrue(active)
        self.assertEqual(value, -8.0)

        runtime_target = self._fighter("Runtime condition")
        runtime_target._aplicar_efeito_status("VENENO")
        self.assertTrue(verificar_condicao("ALVO_ENVENENADO", None, runtime_target))
        self.assertTrue(verificar_condicao("ALVO_DEBUFFADO", None, runtime_target))


if __name__ == "__main__":
    unittest.main()
