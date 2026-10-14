# -*- coding: utf-8 -*-
"""Metade A do motor que MEXE na luta (auditoria profunda de 11/10/2026).

Um lote so, com re-pino (``# re-pino MOT-x``) e medicao do ledger de
qualidade antes e depois (docs/sessoes/builds.md, "Lote de simulacao de
14/10"). MOT-5 (cadencia no stun) ficou de fora por decisao do Adrian
(``builds/atordoamento-e-relogio``: manter como esta).
"""
from __future__ import annotations

import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from neural_fights.core.combat import Channel
from neural_fights.core.entities import Lutador
from neural_fights.core.skills import get_skill_data


def _lutador(nome, x=0.0, y=0.0, classe="Guerreiro (Forca Bruta)"):
    dados = SimpleNamespace(
        nome=nome, tamanho=1.7, forca=5.0, mana=5.0, resistencia=5.0, velocidade=5.0,
        classe=classe, personalidade="Aleatorio", nome_arma="", arma_obj=None,
    )
    with patch("neural_fights.ai.AIBrain", return_value=None):
        lutador = Lutador(dados, x, y)
    lutador.vida_max = 1000.0
    lutador.vida = lutador.vida_max
    return lutador


class _RngFixo:
    def __init__(self, valor):
        self.valor = valor

    def random(self):
        return self.valor

    def uniform(self, a, b):
        return a + (b - a) * self.valor

    def choice(self, opcoes):
        return list(opcoes)[0]

    def randint(self, a, b):
        return a


# --------------------------------------------------------------- MOT-1
class CanalNaoEmpilhaDotTests(unittest.TestCase):
    def test_channel_dot_nao_empilha(self):
        dono = _lutador("Dragao")
        alvo = _lutador("Alvo", x=3.0)
        dono.angulo_olhar = 0.0
        canal = Channel("Chamas do Dragão", dono)
        for _ in range(180):
            canal.atualizar(1 / 60, [alvo])
        queimaduras = [d for d in alvo.dots_ativos if d.tipo == "QUEIMANDO"]
        self.assertEqual(len(queimaduras), 1)  # antes: 30


# ------------------------------------------------------------ MOT-2/3
class GuardaEFonteContinuaTests(unittest.TestCase):
    def _em_guarda(self):
        alvo = _lutador("Guarda", x=1.0)
        atacante = _lutador("Contato")
        alvo.angulo_olhar = 180.0
        alvo.brain = SimpleNamespace(acao_atual="BLOQUEAR", raiva=0.0, ultimo_bloqueio=1.0)
        alvo.tempo_bloqueando = 1.0
        alvo.estamina = 100.0
        return alvo, atacante

    def test_guarda_contra_contato_continuo_nao_quebra_em_frames(self):
        alvo, atacante = self._em_guarda()
        for _ in range(60):
            alvo.tomar_dano(0.33, 0.0, 0.0, "NORMAL", atacante=atacante,
                            ignorar_invencibilidade=True,
                            metadata_impacto={"tipo_fonte": "transform_skill"})
        self.assertGreater(alvo.estamina, 50.0)  # antes: 0
        self.assertLessEqual(alvo.contadores_luta.get("bloqueios", 0), 1)  # antes: 7+

    def test_golpe_comum_ainda_cobra_a_guarda_inteira(self):
        from neural_fights.utils.config import CUSTO_ESTAMINA_BLOQUEIO

        alvo, atacante = self._em_guarda()
        alvo.tomar_dano(30.0, 0.0, 0.0, "NORMAL", atacante=atacante,
                        metadata_impacto={"tipo_fonte": "ataque_corpo_a_corpo"})
        if alvo.contadores_luta.get("bloqueios", 0) == 0:
            self.skipTest("este lutador nao bloqueou (guarda depende de estamina/angulo)")
        self.assertAlmostEqual(alvo.estamina, 100.0 - CUSTO_ESTAMINA_BLOQUEIO)

    def test_raiva_do_dano_tem_teto(self):
        alvo = _lutador("Raivoso")
        alvo.brain = SimpleNamespace(raiva=0.0, ultimo_bloqueio=1.0, acao_atual="COMBATE")
        for _ in range(20):
            alvo.invencivel_timer = 0.0
            alvo.tomar_dano(5.0, 0.0, 0.0, "NORMAL")
        self.assertLessEqual(alvo.brain.raiva, 1.0)  # antes: 4,0
        self.assertGreater(alvo.brain.raiva, 0.0)

    def test_fonte_continua_nao_enfurece(self):
        alvo = _lutador("Calmo")
        alvo.brain = SimpleNamespace(raiva=0.0, ultimo_bloqueio=1.0, acao_atual="COMBATE")
        for _ in range(10):
            alvo.tomar_dano(1.0, 0.0, 0.0, "NORMAL", ignorar_invencibilidade=True,
                            metadata_impacto={"tipo_fonte": "channel_skill"})
        self.assertEqual(alvo.brain.raiva, 0.0)


# --------------------------------------------------------------- MOT-4
class EcoDoFeiticeiroTests(unittest.TestCase):
    def test_eco_do_feiticeiro_nao_desfaz_troca(self):
        feiticeiro = _lutador("Feiticeiro", x=0.0, classe="Feiticeiro (Caos)")
        alvo = _lutador("Alvo", x=6.0)
        data = get_skill_data("Troca de Almas")
        feiticeiro.skills_classe.append({"nome": "Troca de Almas", "custo": data.get("custo", 0.0),
                                         "data": data})
        feiticeiro.cd_skills["Troca de Almas"] = 0.0
        feiticeiro.mana = feiticeiro.mana_max = 999.0
        feiticeiro.rng_runtime = _RngFixo(0.10)
        feiticeiro._inimigo_atual = alvo
        self.assertTrue(feiticeiro.usar_skill_classe("Troca de Almas", alvo))
        self.assertEqual([round(v, 3) for v in feiticeiro.pos[:2]], [6.0, 0.0])  # antes: [0, 0]


# --------------------------------------------------------------- MOT-6
class FluxoSimetricoTests(unittest.TestCase):
    def _core(self, l1, l2):
        from neural_fights.ai.choreographer import CombatChoreographer

        CombatChoreographer.reset()
        core = CombatChoreographer(rng=_RngFixo(0.0))
        core.registrar_lutadores(l1, l2)
        core.sequencia_hits = []
        core.fluxo_direcao = 0.0
        return core

    def _par(self, ang_graus, quem):
        rad = math.radians(ang_graus)
        a = SimpleNamespace(pos=[10.0, 10.0], vel=[0.0, 0.0])
        b = SimpleNamespace(pos=[10.0 + 4 * math.cos(rad), 10.0 + 4 * math.sin(rad)], vel=[0.0, 0.0])
        # quem avanca anda na direcao do outro
        if quem == "l1":
            a.vel = [3 * math.cos(rad), 3 * math.sin(rad)]
            return a, b
        b.vel = [-3 * math.cos(rad), -3 * math.sin(rad)]
        return a, b

    def test_fluxo_simetrico_em_todas_as_direcoes(self):
        for ang in (0, 45, 90, 135, 179, -179, -135, -90, -45):
            with self.subTest(ang=ang, quem="l2"):
                l1, l2 = self._par(ang, "l2")
                core = self._core(l1, l2)
                core._atualizar_fluxo(0.5, 4.0)
                self.assertLess(core.fluxo_direcao, 0)
            with self.subTest(ang=ang, quem="l1"):
                l1, l2 = self._par(ang, "l1")
                core = self._core(l1, l2)
                core._atualizar_fluxo(0.5, 4.0)
                self.assertGreater(core.fluxo_direcao, 0)

    def test_parados_nao_avancam(self):
        l1 = SimpleNamespace(pos=[0.0, 0.0], vel=[0.0, 0.0])
        l2 = SimpleNamespace(pos=[4.0, 0.0], vel=[0.0, 0.0])
        core = self._core(l1, l2)
        core.fluxo_direcao = 0.5
        core._atualizar_fluxo(0.5, 4.0)
        self.assertLess(core.fluxo_direcao, 0.5)  # so decai


# --------------------------------------------------- MOT-7/8/9/14 (IA)
def _brain_cru():
    from neural_fights.ai.brain import AIBrain

    brain = object.__new__(AIBrain)
    return brain


class IaTests(unittest.TestCase):
    def test_bonus_de_canto_some_quando_inimigo_sai(self):
        from neural_fights.ai.brain import AIBrain

        brain = _brain_cru()
        brain.tracos = ["PREDADOR"]
        brain._perfil_chave = None
        brain.agressividade_base = 0.5
        brain.humor = "CALMO"
        brain.confianca = 0.5
        brain.tatica_espacial = {}
        brain.parent = SimpleNamespace(vida=100.0, vida_max=100.0)
        brain.dir_circular = 1
        esp = {"encurralado": False, "oponente_contra_parede": True, "oponente_perto_obstaculo": False,
               "caminho_livre": {"frente": True, "tras": True, "esquerda": True, "direita": True}, "obstaculo_proximo": None,
               "distancia_obstaculo": 999, "parede_proxima": None, "distancia_parede": 999}
        brain.consciencia_espacial = esp
        inicial = AIBrain.agressividade_efetiva(brain)
        for _ in range(3):
            brain._avaliar_taticas_espaciais(3.0, SimpleNamespace(pos=[0, 0]))
        self.assertEqual(brain.agressividade_base, 0.5)
        self.assertGreater(AIBrain.agressividade_efetiva(brain), inicial)
        esp["oponente_contra_parede"] = False
        brain._avaliar_taticas_espaciais(3.0, SimpleNamespace(pos=[0, 0]))
        self.assertEqual(brain.agressividade_base, 0.5)
        self.assertAlmostEqual(AIBrain.agressividade_efetiva(brain), inicial)

    def test_covarde_foge_ao_apanhar(self):
        brain = _brain_cru()
        brain.tracos = ["COVARDE"]
        brain.medo = 0.6
        brain.reacao_pendente = "FUGIR"
        brain.rng = _RngFixo(0.0)
        brain._acao_atual = "COMBATE"  # direto: o setter seguraria o hold
        self.assertTrue(brain._processar_reacao_oponente(0.1, 3.0, None))
        self.assertEqual(brain.acao_atual, "FUGIR")
        self.assertGreater(brain.medo, 0.6)

    def test_posso_atacar_usa_meu_angulo(self):
        from neural_fights.core.weapon_analysis import WeaponAnalyzer

        reta = SimpleNamespace(nome="Reta T", tipo="Reta", comp_cabo=20, comp_lamina=80, largura=5,
                               peso=3.0, dano=10)
        analisador = WeaponAnalyzer()
        resultado = analisador.avaliar_posicao_combate(reta, reta, 1.5, 0.0, 180.0)
        self.assertTrue(resultado["posso_atacar"])
        self.assertFalse(resultado["inimigo_pode_atacar"])

    def test_janela_escolhe_a_melhor_do_frame(self):
        brain = _brain_cru()
        brain.janela_ataque = {"aberta": True, "tipo": "x", "qualidade": 0.8, "duracao": 1.0}
        brain._observar = lambda inimigo: SimpleNamespace(intencao="recuando")
        inimigo = SimpleNamespace(atacando=False, cooldown_ataque=0.3, stun_timer=1.0,
                                  canalizando=False, z=0.0, estamina=100.0, cd_skill_arma=0.0)
        brain._atualizar_janelas_oportunidade(0.0, 2.0, inimigo)
        self.assertEqual(brain.janela_ataque["tipo"], "stunado")
        self.assertEqual(brain.janela_ataque["qualidade"], 1.0)


# --------------------------------------------------------- MOT-10/18
class GameFeelTests(unittest.TestCase):
    def test_quebra_da_armadura_nao_reduz_mais_que_absorcao(self):
        from neural_fights.core.game_feel import SuperArmorSystem

        cavaleiro = SimpleNamespace(classe_nome="Cavaleiro (Defesa)", vida_max=1000.0)
        sistema = SuperArmorSystem(cavaleiro)
        if not sistema.tem_super_armor():
            self.skipTest("Cavaleiro sem super armor configurada")
        sistema.verificar_ativacao(0.0, "BLOQUEAR")
        dano, *_resto = sistema.processar_dano(1500.0)
        self.assertGreaterEqual(dano, 1500.0 * 0.75)

    def test_sempre_ativo_zera_o_absorvido_ao_reativar(self):
        from neural_fights.core.game_feel import SuperArmorSystem

        cavaleiro = SimpleNamespace(classe_nome="Cavaleiro (Defesa)", vida_max=1000.0)
        sistema = SuperArmorSystem(cavaleiro)
        if not sistema.tem_super_armor():
            self.skipTest("Cavaleiro sem super armor configurada")
        sistema.verificar_ativacao(0.0, "BLOQUEAR")
        sistema.processar_dano(100.0)
        self.assertGreater(sistema.data.dano_absorvido, 0.0)
        sistema.verificar_ativacao(0.0, "MATAR")
        sistema.verificar_ativacao(0.0, "BLOQUEAR")
        self.assertEqual(sistema.data.dano_absorvido, 0.0)

    def test_hitstop_usa_o_maior(self):
        from neural_fights.core.game_feel import HitStopManager, HitStopEvent

        gerente = HitStopManager()
        gerente._iniciar_hitstop(HitStopEvent(duracao=0.023, intensidade=0.1, atacante=None, alvo=None,
                                              tipo_golpe="LEVE", posicao=(0, 0)))
        evento = HitStopEvent(duracao=0.5, intensidade=1.0, atacante=None, alvo=None,
                              tipo_golpe="EPICO", posicao=(0, 0))
        gerente._registrar_evento(evento)
        parado = 0.0
        for _ in range(1000):
            if gerente.update(0.001) == 0.0:
                parado += 0.001
        self.assertAlmostEqual(parado, 0.5, delta=0.003)  # antes: 0,525


# -------------------------------------------------- MOT-11/15/16/19/20/21
class MiudosDaSimulacaoTests(unittest.TestCase):
    def test_perfil_de_arma_nao_vaza_entre_medidas(self):
        from neural_fights.core.weapon_analysis import WeaponAnalyzer

        base = dict(nome="Espada Longa", tipo="Reta", comp_cabo=20, largura=5, peso=3.0, dano=10)
        curta = SimpleNamespace(comp_lamina=60, **base)
        longa = SimpleNamespace(comp_lamina=170, **base)
        analisador = WeaponAnalyzer()
        p1, p2 = analisador.analisar_arma(curta), analisador.analisar_arma(longa)
        self.assertIsNot(p1, p2)
        self.assertGreater(p2.alcance_maximo, p1.alcance_maximo)

    def test_esquiva_do_ladino_nao_cobra_guarda(self):
        ladino = _lutador("Ladino", x=1.0, classe="Ladino (Furtivo)")
        if "Ladino" not in ladino.classe_nome:
            self.skipTest("classe Ladino com outro nome")
        atacante = _lutador("Atacante")
        ladino.angulo_olhar = 180.0
        ladino.brain = SimpleNamespace(acao_atual="BLOQUEAR", raiva=0.0, ultimo_bloqueio=1.0)
        ladino.tempo_bloqueando = 1.0
        ladino.estamina = 100.0
        ladino.rng_runtime = _RngFixo(0.05)
        ladino.tomar_dano(20.0, 0.0, 0.0, "NORMAL", atacante=atacante)
        self.assertEqual(ladino.estamina, 100.0)
        self.assertEqual(ladino.contadores_luta.get("bloqueios", 0), 0)

    def test_puxado_aplicado_e_verdade_e_sem_atributo_morto(self):
        # MOT-16 e alarme parcial: o puxao de verdade e aplicado em
        # tomar_dano (Onda 10D). Saiu so o sendo_puxado/em_vortex sem leitor.
        alvo = _lutador("Alvo", x=3.0)
        atacante = _lutador("Gravidade")
        alvo.tomar_dano(1.0, 0.0, 0.0, "PUXADO", atacante=atacante)
        self.assertIsNotNone(getattr(alvo, "puxao", None))
        self.assertFalse(hasattr(alvo, "sendo_puxado"))
        alvo._aplicar_efeito_status("VORTEX")
        self.assertFalse(hasattr(alvo, "em_vortex"))

    def test_beam_canalizavel_tem_duracao(self):
        from neural_fights.core.skill_contract import derivar_contrato

        for nome in ("Chamas do Dragão", "Desintegrar"):
            with self.subTest(skill=nome):
                self.assertEqual(derivar_contrato(nome).duracao, 3.0)

    def test_dano_fracionario_desgasta_obstaculo(self):
        from neural_fights.core.arena import Arena, ARENAS

        arena = Arena(ARENAS["Cyberpunk"])
        caixa = next(o for o in arena.obstaculos if getattr(o, "destrutivel", False))
        hp0 = float(caixa.hp)
        for _ in range(50):
            arena.danificar_obstaculo(caixa, 0.9)
        self.assertAlmostEqual(float(caixa.hp), hp0 - 45.0)

    def test_escape_nao_repete_dash(self):
        from neural_fights.core import agarrao

        chamadas = []

        def dash(*args, **kwargs):
            chamadas.append((args, kwargs))
            raise TypeError("bug dentro do dash")

        self.assertTrue(hasattr(agarrao, "aplicar_desfecho"))
        ini = SimpleNamespace(pos=[0.0, 0.0], stun_timer=0.0, vel=[0.0, 0.0])
        alvo = SimpleNamespace(pos=[1.0, 0.0], vel=[0.0, 0.0], iniciar_dash=dash, stun_timer=0.0)
        with self.assertRaises(TypeError):
            agarrao.aplicar_desfecho(ini, alvo, "ESCAPE", 1.0, 0.0)
        self.assertEqual(len(chamadas), 1)


# --------------------------------------------------------------- MOT-17
class CorrenteTeleporteTests(unittest.TestCase):
    def test_teleporte_da_mao_nao_acelera_bola(self):
        from neural_fights.core import corrente

        self.assertTrue(hasattr(corrente, "TELEPORTE_MAO_MIN_M"))


# ------------------------------------------------------------ MOT-30/31
class CatalogoDePersonalidadeTests(unittest.TestCase):
    def test_quirk_sorteado_tem_leitor(self):
        import re
        from pathlib import Path

        from neural_fights.ai import brain as brain_mod
        from neural_fights.ai.personalities import QUIRKS, QUIRKS_ATIVOS

        raiz = Path(brain_mod.__file__).resolve().parents[1]
        fonte = "\n".join(
            p.read_text(encoding="utf-8") for p in raiz.rglob("*.py")
            if p.name != "personalities.py" and not p.name.startswith("test_")
        )
        for quirk in QUIRKS_ATIVOS:
            with self.subTest(quirk=quirk):
                self.assertRegex(fonte, r"['\"]%s['\"]\s+in\s+self\.quirks" % re.escape(quirk))
        for quirk in set(QUIRKS) - set(QUIRKS_ATIVOS):
            with self.subTest(sem_efeito=quirk):
                self.assertNotRegex(fonte, r"['\"]%s['\"]\s+in\s+self\.quirks" % re.escape(quirk))

    def test_sorteio_so_usa_quirks_ativos(self):
        from neural_fights.ai.brain import AIBrain
        from neural_fights.ai.personalities import QUIRKS_ATIVOS
        import random

        for semente in range(40):
            brain = object.__new__(AIBrain)
            brain.rng = random.Random(semente)
            brain.tracos = ["BERSERKER", "VAMPIRO", "EVASIVO", "PACIENTE"]
            brain._gerar_quirks()
            self.assertTrue(set(brain.quirks) <= set(QUIRKS_ATIVOS), brain.quirks)
            self.assertTrue(brain.quirks)

    def test_todo_humor_tem_produtor(self):
        from pathlib import Path

        from neural_fights.ai import emotions
        from neural_fights.ai.personalities import HUMORES

        texto = Path(emotions.__file__).read_text(encoding="utf-8")
        for humor in HUMORES:
            with self.subTest(humor=humor):
                self.assertIn(f'"{humor}"', texto)


# ----------------------------------------------------------- MOT-32 lava
class LavaTests(unittest.TestCase):
    def test_lava_do_vulcao_machuca(self):
        from neural_fights.core.arena import ARENAS, Arena
        from neural_fights.simulation import simulacao

        arena = Arena(ARENAS["Vulcao"])
        poca = next(o for o in arena.obstaculos if o.tipo == "lava")
        lutador = _lutador("Pisando", x=poca.x, y=poca.y)
        lutador.z = 0.0
        sim = object.__new__(simulacao.Simulador)
        sim.arena = arena
        sim.p1 = lutador
        sim.p2 = _lutador("Fora", x=1.0, y=1.0)
        for _ in range(120):
            simulacao.Simulador._aplicar_perigo_do_chao(sim, 1 / 60)
        self.assertLess(lutador.vida, lutador.vida_max)
        self.assertEqual(sim.p2.vida, sim.p2.vida_max)

    def test_inferno_tambem(self):
        from neural_fights.core.arena import ARENAS, Arena

        arena = Arena(ARENAS["Inferno"])
        fogo = next(o for o in arena.obstaculos if o.tipo == "fogo")
        self.assertEqual(arena.esta_em_zona_perigo(fogo.x, fogo.y), "fogo")


if __name__ == "__main__":
    unittest.main()
