"""Evidencia de runtime dos encantamentos revividos e do golpe duplo.

Antes da Onda 3, seis dos doze encantamentos e a passiva "Eco" eram catalogo
morto: ``aplicar_efeitos_encantamento`` nao tinha nenhum chamador (DoT era
0,0% de todo o dano do jogo), Critico/Execucao/Espelhamento/Velocidade nunca
eram lidos, e ``hits_por_ataque`` da Dupla tampouco. Estes testes sao a
evidencia cobravel de que cada um agora existe em combate.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from neural_fights.core.entities import RECUPERACAO_CONJURACAO_S, Lutador
from neural_fights.core.skills import get_skill_data
from neural_fights.simulation.simulacao import Simulador


class RngFixo:
    """RNG deterministico para atravessar o gate de 50% dos encantamentos."""

    def __init__(self, valor: float = 0.0) -> None:
        self.valor = valor

    def random(self) -> float:
        return self.valor

    def uniform(self, a, b):
        return a

    def choice(self, seq):
        return seq[0]

    def randint(self, a, b):
        return a

    def sample(self, seq, k):
        return list(seq)[:k]


def arma(**overrides) -> SimpleNamespace:
    base = dict(
        nome="Lamina de Teste",
        tipo="Reta",
        dano=10.0,
        peso=3.0,
        critico=5.0,
        velocidade_ataque=1.0,
        encantamentos=[],
        passiva=None,
        habilidade="Nenhuma",
        habilidades=[],
        custo_mana=0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def lutador(arma_obj=None, classe="Guerreiro (Força Bruta)") -> Lutador:
    dados = SimpleNamespace(
        nome="Alvo",
        tamanho=1.7,
        forca=6.0,
        mana=5.0,
        resistencia=5.0,
        velocidade=5.0,
        classe=classe,
        personalidade="Aleatório",
        nome_arma=arma_obj.nome if arma_obj else "",
        arma_obj=arma_obj,
    )
    with patch("neural_fights.ai.AIBrain", return_value=None):
        return Lutador(dados, 5.0, 5.0)


class EncantamentoOnHitTests(unittest.TestCase):
    def test_chamas_aplica_dot_de_queimadura(self) -> None:
        atacante = lutador(arma(encantamentos=["Chamas"]))
        alvo = lutador()
        atacante.rng_runtime = RngFixo(0.0)  # atravessa o gate de 50%

        atacante.aplicar_efeitos_encantamento(alvo, 30.0)

        tipos = {dot.tipo for dot in alvo.dots_ativos}
        self.assertIn("QUEIMANDO", tipos)

    def test_veneno_aplica_dot_com_contexto_de_encantamento(self) -> None:
        atacante = lutador(arma(encantamentos=["Veneno"]))
        alvo = lutador()
        atacante.rng_runtime = RngFixo(0.0)

        atacante.aplicar_efeitos_encantamento(alvo, 30.0)

        dots = [d for d in alvo.dots_ativos if d.tipo == "ENVENENADO"]
        self.assertEqual(len(dots), 1)

    def test_lifesteal_cura_pelo_dano_causado(self) -> None:
        """A semantica antiga drenava a vida ATUAL do alvo — quanto mais
        ferido o alvo, menos curava. Agora e percentual do dano do golpe."""
        atacante = lutador(arma(encantamentos=["Vampirismo"]))
        alvo = lutador()
        atacante.rng_runtime = RngFixo(0.0)
        atacante.vida = atacante.vida_max - 50.0

        atacante.aplicar_efeitos_encantamento(alvo, 100.0)

        # Vampirismo: lifesteal_percent = 15
        self.assertAlmostEqual(
            atacante.vida, atacante.vida_max - 50.0 + 15.0, places=5
        )

    def test_gate_de_50_por_cento_segue_valendo(self) -> None:
        atacante = lutador(arma(encantamentos=["Chamas"]))
        alvo = lutador()
        atacante.rng_runtime = RngFixo(0.99)  # nunca passa

        atacante.aplicar_efeitos_encantamento(alvo, 30.0)

        self.assertEqual(alvo.dots_ativos, [])


class CriticoEncantadoTests(unittest.TestCase):
    def test_encantamento_soma_chance_e_multiplicador(self) -> None:
        """Critico enchant: +15pp de chance e x1,75 em vez de x1,5."""
        com = lutador(arma(critico=5.0, encantamentos=["Crítico"]))
        sem = lutador(arma(critico=5.0))

        # chance: 0,05 base + 0,15 do encantamento = 0,20
        com.rng_runtime = RngFixo(0.19)
        dano_com, critico_com = com.calcular_dano_ataque(100.0)
        self.assertTrue(critico_com)

        sem.rng_runtime = RngFixo(0.19)  # 0,19 >= 0,05 -> nao crita
        _dano_sem, critico_sem = sem.calcular_dano_ataque(100.0)
        self.assertFalse(critico_sem)

        # multiplicador: 1,5 + 0,25
        base = 100.0 * com.mod_dano
        self.assertAlmostEqual(dano_com, base * 1.75, places=5)

    def test_sem_encantamento_multiplicador_continua_1_5(self) -> None:
        alvo = lutador(arma(critico=5.0))
        alvo.rng_runtime = RngFixo(0.01)
        dano, critico = alvo.calcular_dano_ataque(100.0)
        self.assertTrue(critico)
        self.assertAlmostEqual(dano, 100.0 * alvo.mod_dano * 1.5, places=5)


class ExecucaoTests(unittest.TestCase):
    def test_alvo_abaixo_do_limiar_e_finalizado(self) -> None:
        atacante = lutador(arma(dano=1.0, critico=0.0, encantamentos=["Execução"]))
        vitima = lutador()
        vitima.vida = vitima.vida_max * 0.15  # abaixo dos 20%
        atacante.rng_runtime = RngFixo(0.99)  # sem critico

        dano, _critico = atacante.calcular_dano_ataque(1.0, vitima)

        # atravessa ate a maior reducao de classe (Cavaleiro x0,75)
        self.assertGreaterEqual(dano, vitima.vida / 0.7 - 1e-6)

    def test_alvo_saudavel_nao_e_executado(self) -> None:
        atacante = lutador(arma(dano=1.0, critico=0.0, encantamentos=["Execução"]))
        vitima = lutador()
        vitima.vida = vitima.vida_max * 0.9
        atacante.rng_runtime = RngFixo(0.99)

        dano, _critico = atacante.calcular_dano_ataque(1.0, vitima)

        self.assertLess(dano, vitima.vida * 0.5)


class EspelhamentoTests(unittest.TestCase):
    def test_defensor_encantado_reflete_parte_do_dano(self) -> None:
        defensor = lutador(arma(encantamentos=["Espelhamento"]))
        atacante = lutador()
        vida_atacante = atacante.vida

        defensor.tomar_dano(40.0, 0.0, 0.0, atacante=atacante)

        # 25% do dano final volta para o atacante
        self.assertLess(atacante.vida, vida_atacante)
        refletido = vida_atacante - atacante.vida
        self.assertGreater(refletido, 40.0 * 0.25 * 0.5)


class VelocidadeTests(unittest.TestCase):
    def _cooldown_apos_ataque(self, com_encantamento: bool) -> float:
        enc = ["Velocidade"] if com_encantamento else []
        atacante = lutador(arma(encantamentos=enc))
        inimigo = lutador()
        inimigo.pos = [5.8, 5.0]  # dentro do alcance melee
        atacante.brain = SimpleNamespace(
            acao_atual="MATAR", arquetipo="", tracos=[], dir_circular=1
        )
        atacante.rng_runtime = RngFixo(0.0)
        atacante.cooldown_ataque = 0.0
        atacante.executar_ataques(1.0 / 60.0, 0.8, inimigo)
        return atacante.cooldown_ataque

    def test_encantamento_reduz_o_cooldown_em_20_por_cento(self) -> None:
        sem = self._cooldown_apos_ataque(False)
        com = self._cooldown_apos_ataque(True)
        self.assertGreater(sem, 0.0)
        self.assertAlmostEqual(com, sem * 0.8, places=5)


class KitDestravadoTests(unittest.TestCase):
    def test_cast_grava_cooldown_real_por_skill_e_recuperacao_curta(self) -> None:
        """O lock que matava 71% das tentativas de skill morreu."""
        conjurador = lutador()
        data = get_skill_data("Bola de Fogo")
        conjurador.skills_classe.append(
            {"nome": "Bola de Fogo", "custo": 0.0, "data": data}
        )
        conjurador.cd_skills["Bola de Fogo"] = 0.0
        conjurador.rng_runtime = RngFixo(0.99)

        with patch(
            "neural_fights.effects.audio.AudioManager.get_instance",
            return_value=None,
        ):
            self.assertTrue(conjurador.usar_skill_classe("Bola de Fogo"))

        self.assertAlmostEqual(
            conjurador.cd_skills["Bola de Fogo"], data["cooldown"], places=5
        )
        self.assertEqual(conjurador.cd_skill_arma, RECUPERACAO_CONJURACAO_S)
        self.assertLess(conjurador.cd_skill_arma, data["cooldown"])


class JanelaDeQualidadeTests(unittest.TestCase):
    def test_qualidade_zera_quando_a_janela_fecha(self) -> None:
        """Sem isso, uma janela de stun (1,0) travava todas as futuras."""
        dados = SimpleNamespace(
            nome="Alvo",
            tamanho=1.7,
            forca=6.0,
            mana=5.0,
            resistencia=5.0,
            velocidade=5.0,
            classe="Guerreiro (Força Bruta)",
            personalidade="Aleatório",
            nome_arma="",
            arma_obj=None,
        )
        brain = Lutador(dados, 5.0, 5.0).brain
        brain.janela_ataque.update(
            {"aberta": True, "tipo": "stunado", "qualidade": 1.0, "duracao": 0.01}
        )
        inimigo = SimpleNamespace(
            atacando=False,
            cooldown_ataque=0.0,
            canalizando=False,
            stun_timer=0.0,
            congelado=False,
            z=0.0,
            vida=100.0,
            vida_max=100.0,
            acao_atual=None,
            mana=50.0,
            cd_skill_arma=0.0,
        )

        brain._atualizar_janelas_oportunidade(0.05, 3.0, inimigo)

        self.assertEqual(brain.janela_ataque["qualidade"], 0.0)


class EcoTests(unittest.TestCase):
    def setUp(self) -> None:
        import pygame

        pygame.font.init()  # FloatingText do eco renderiza texto

    def _sim_minimo(self) -> Simulador:
        sim = object.__new__(Simulador)
        sim.hits_ecoados = []
        sim.textos = []
        sim.game_feel = None
        return sim

    def test_dupla_agenda_eco_pelo_knob_do_catalogo(self) -> None:
        """``hits_por_ataque: 2`` da Dupla era um knob morto do catalogo."""
        sim = self._sim_minimo()
        atacante = lutador(arma(tipo="Dupla"))
        defensor = lutador()

        sim._agendar_eco_melee(atacante, defensor, 40.0)

        self.assertEqual(len(sim.hits_ecoados), 1)
        self.assertAlmostEqual(sim.hits_ecoados[0]["dano"], 20.0)

    def test_passiva_eco_agenda_golpe_duplo_por_chance(self) -> None:
        sim = self._sim_minimo()
        atacante = lutador(
            arma(passiva={"nome": "Eco", "efeito": "double_hit", "valor": 20})
        )
        defensor = lutador()
        atacante.rng_runtime = RngFixo(0.1)  # dentro dos 20%

        sim._agendar_eco_melee(atacante, defensor, 40.0)

        self.assertEqual(len(sim.hits_ecoados), 1)

    def test_arma_comum_nao_agenda_eco(self) -> None:
        sim = self._sim_minimo()
        atacante = lutador(arma(tipo="Reta"))
        atacante.rng_runtime = RngFixo(0.99)
        sim._agendar_eco_melee(atacante, lutador(), 40.0)
        self.assertEqual(sim.hits_ecoados, [])

    def test_eco_aplica_dano_real_apos_o_atraso(self) -> None:
        sim = self._sim_minimo()
        atacante = lutador(arma(tipo="Dupla"))
        defensor = lutador()
        vida_antes = defensor.vida

        sim._agendar_eco_melee(atacante, defensor, 40.0)
        sim._processar_hits_ecoados(0.2)  # atraso de 0,12s vencido

        self.assertEqual(sim.hits_ecoados, [])
        self.assertLess(defensor.vida, vida_antes)

    def test_eco_nao_acerta_defensor_morto(self) -> None:
        sim = self._sim_minimo()
        atacante = lutador(arma(tipo="Dupla"))
        defensor = lutador()
        sim._agendar_eco_melee(atacante, defensor, 40.0)
        defensor.morto = True

        sim._processar_hits_ecoados(0.2)

        self.assertEqual(sim.hits_ecoados, [])
        self.assertEqual(sim.textos, [])


if __name__ == "__main__":
    unittest.main()
