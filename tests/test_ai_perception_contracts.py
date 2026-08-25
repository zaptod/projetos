"""Contratos da percepção honesta (Onda 8A).

Garante que:
- a IA não lê mais a intenção interna do oponente (telepatia);
- a janela de mundo (PercepcaoMundo) sobrevive à reatribuição das listas
  do Simulador e filtra por dono;
- a observação funciona contra um lutador SEM brain (dummy físico);
- a fase de ataque observada espelha a janela de hit do motor;
- o detector de projéteis exige direção + tempo de impacto (não dispara
  para projétil se afastando).
"""

from __future__ import annotations

import inspect
import math
import random
import unittest
from types import SimpleNamespace

from neural_fights.ai import brain as brain_module
from neural_fights.ai.brain import AIBrain
from neural_fights.ai.percepcao import (
    FASE_GOLPEANDO,
    FASE_PREPARANDO,
    FASE_RECUPERANDO,
    ObservacaoInimigo,
    PercepcaoMundo,
    classificar_fase_ataque,
    construir_observacao,
)
from neural_fights.effects.weapon_animations import WEAPON_PROFILES


def _dummy_lutador(x=0.0, y=0.0, vx=0.0, vy=0.0, atacando=False,
                   timer_animacao=0.0, arma_tipo="Reta"):
    """Lutador-fantoche puramente físico: sem brain, sem motor."""
    return SimpleNamespace(
        pos=[x, y],
        vel=[vx, vy],
        z=0.0,
        vida=100.0,
        vida_max=100.0,
        estamina=100.0,
        stun_timer=0.0,
        canalizando=False,
        atacando=atacando,
        timer_animacao=timer_animacao,
        ataque_id=1 if atacando else 0,
        pos_historico=[(x, y)] * 15,
        dados=SimpleNamespace(arma_obj=SimpleNamespace(tipo=arma_tipo)),
        percepcao=None,
    )


def _brain_minimo(parent, habilidade_leitura=0.95):
    brain = object.__new__(AIBrain)
    brain.parent = parent
    brain.rng = random.Random(42)
    brain.tempo_combate = 1.0
    brain.habilidade_leitura = habilidade_leitura
    brain._obs_cache = None
    brain._obs_cache_tempo = -1.0
    brain._obs_ataque_id_visto = -1
    brain._obs_ataque_mal_lido = False
    return brain


class SemTelepatiaTests(unittest.TestCase):
    def test_brain_nao_le_acao_atual_do_oponente(self):
        """O único uso de _obter_brain em brain.py deve ser o import
        (re-export para testes legados): nenhum call site de telepatia."""
        fonte = inspect.getsource(brain_module)
        chamadas = [
            linha for linha in fonte.splitlines()
            if "_obter_brain(" in linha and "import" not in linha
        ]
        self.assertEqual(chamadas, [], "telepatia reintroduzida em brain.py")


class PercepcaoMundoTests(unittest.TestCase):
    def test_sobrevive_a_reatribuicao_das_listas(self):
        fonte = SimpleNamespace(projeteis=[], areas=[], beams=[], arena=None)
        percepcao = PercepcaoMundo(fonte)
        # O Simulador troca a identidade da lista a cada partida.
        fonte.projeteis = [SimpleNamespace(ativo=True, dono=None)]
        self.assertEqual(len(percepcao.projeteis), 1)

    def test_filtra_projeteis_por_dono_e_ativo(self):
        eu = _dummy_lutador()
        meu = SimpleNamespace(ativo=True, dono=eu)
        hostil = SimpleNamespace(ativo=True, dono="outro")
        morto = SimpleNamespace(ativo=False, dono="outro")
        fonte = SimpleNamespace(projeteis=[meu, hostil, morto])
        percepcao = PercepcaoMundo(fonte)
        self.assertEqual(percepcao.projeteis_hostis(eu), [hostil])

    def test_fonte_sem_atributos_e_null_safe(self):
        percepcao = PercepcaoMundo(SimpleNamespace())
        self.assertEqual(list(percepcao.projeteis), [])
        self.assertEqual(percepcao.areas_hostis(_dummy_lutador()), [])


class FaseAtaqueTests(unittest.TestCase):
    def test_espelha_janela_de_hit_do_motor(self):
        profile = WEAPON_PROFILES["Reta"]
        total = profile.total_time
        alvo = _dummy_lutador(atacando=True, timer_animacao=total)

        # Início absoluto do golpe: ainda no wind-up (antes da janela).
        fase, t_impacto, _ = classificar_fase_ataque(alvo, "Reta")
        self.assertEqual(fase, FASE_PREPARANDO)
        self.assertGreater(t_impacto, 0.0)

        # Meio da fase de attack: dentro da janela de hit.
        alvo.timer_animacao = total - (
            profile.anticipation_time + profile.attack_time * 0.5
        )
        fase, _, _ = classificar_fase_ataque(alvo, "Reta")
        self.assertEqual(fase, FASE_GOLPEANDO)

        # Fim da animação: recovery (janela fechada).
        alvo.timer_animacao = profile.recovery_time * 0.05
        fase, _, _ = classificar_fase_ataque(alvo, "Reta")
        self.assertEqual(fase, FASE_RECUPERANDO)

    def test_sem_ataque_nao_tem_fase(self):
        alvo = _dummy_lutador(atacando=False)
        self.assertEqual(classificar_fase_ataque(alvo, "Reta"), (None, None, None))


class ObservacaoTests(unittest.TestCase):
    def test_funciona_contra_dummy_sem_brain(self):
        observador = _dummy_lutador()
        inimigo = _dummy_lutador(x=4.0, vx=-3.0)  # vindo na minha direção
        obs = construir_observacao(observador, inimigo)
        self.assertIsInstance(obs, ObservacaoInimigo)
        self.assertEqual(obs.intencao, "avancando")
        self.assertTrue(obs.agressivo)

    def test_recuo_e_circular_observados(self):
        observador = _dummy_lutador()
        recuando = construir_observacao(observador, _dummy_lutador(x=4.0, vx=3.0))
        self.assertEqual(recuando.intencao, "recuando")
        circulando = construir_observacao(observador, _dummy_lutador(x=4.0, vy=3.0))
        self.assertEqual(circulando.intencao, "circulando")
        self.assertNotEqual(circulando.lado_circular, 0)

    def test_wind_up_vira_armando_golpe(self):
        observador = _dummy_lutador()
        inimigo = _dummy_lutador(
            x=2.0, atacando=True,
            timer_animacao=WEAPON_PROFILES["Reta"].total_time,
        )
        obs = construir_observacao(observador, inimigo)
        self.assertEqual(obs.intencao, "armando_golpe")

    def test_atraso_amostra_o_historico(self):
        observador = _dummy_lutador()
        inimigo = _dummy_lutador(x=4.0)
        # Histórico registra posição antiga (x=6) — leitor lento vê o passado.
        inimigo.pos_historico = [(6.0, 0.0)] * 15
        obs = construir_observacao(observador, inimigo, atraso_frames=2)
        self.assertEqual(obs.pos[0], 6.0)

    def test_funil_do_brain_cacheia_por_frame(self):
        observador = _dummy_lutador()
        inimigo = _dummy_lutador(x=4.0, vx=-3.0)
        brain = _brain_minimo(observador)
        obs1 = brain._observar(inimigo)
        inimigo.vel[0] = 3.0  # muda no meio do frame
        obs2 = brain._observar(inimigo)
        self.assertIs(obs1, obs2)

    def test_ma_leitura_apaga_o_wind_up(self):
        """Leitor péssimo com sorteio forçado não enxerga a fase preparando."""
        observador = _dummy_lutador()
        inimigo = _dummy_lutador(
            x=2.0, atacando=True,
            timer_animacao=WEAPON_PROFILES["Reta"].total_time,
        )
        brain = _brain_minimo(observador, habilidade_leitura=0.05)
        brain.rng = SimpleNamespace(random=lambda: 0.0)  # sempre erra a leitura
        obs = brain._observar(inimigo)
        self.assertIsNone(obs.fase_ataque)
        self.assertNotEqual(obs.intencao, "armando_golpe")


class DetectorProjetilTests(unittest.TestCase):
    def _preparar(self):
        eu = _dummy_lutador()
        inimigo = _dummy_lutador(x=6.0)
        brain = _brain_minimo(eu)
        return eu, inimigo, brain

    def test_projetil_em_rota_de_colisao_detecta(self):
        eu, inimigo, brain = self._preparar()
        vindo = SimpleNamespace(ativo=True, dono=inimigo, x=5.0, y=0.0,
                                angulo=180.0, vel=20.0)
        eu.percepcao = PercepcaoMundo(SimpleNamespace(projeteis=[vindo]))
        self.assertTrue(brain._detectar_projetil_vindo(inimigo))

    def test_projetil_se_afastando_nao_detecta(self):
        eu, inimigo, brain = self._preparar()
        fugindo = SimpleNamespace(ativo=True, dono=inimigo, x=2.0, y=0.0,
                                  angulo=0.0, vel=20.0)  # voando para +x, longe de mim
        eu.percepcao = PercepcaoMundo(SimpleNamespace(projeteis=[fugindo]))
        self.assertFalse(brain._detectar_projetil_vindo(inimigo))

    def test_sem_percepcao_e_null_safe(self):
        eu, inimigo, brain = self._preparar()
        eu.percepcao = None
        self.assertFalse(brain._detectar_projetil_vindo(inimigo))


if __name__ == "__main__":
    unittest.main()
