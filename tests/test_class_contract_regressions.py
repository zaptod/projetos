# -*- coding: utf-8 -*-
"""Evidência de runtime dos contratos de classe (Onda 6, fase 1).

O baseline da O5 fechou com Cavaleiro INVICTO (21/21 — redução x0,75 +
super armor, ambos sempre-ativos), Duelista em 0,327 (a passiva declarada
"nunca erra, +10% em 1v1" nunca existiu em código) e Paladino em 0,714
(regen de 0,5%/s sem teto = imortalidade prática com o pool 2,15x).
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from neural_fights.core.entities import Lutador


class RngFixo:
    def __init__(self, valor: float = 0.0):
        self.valor = valor

    def random(self) -> float:
        return self.valor

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self.valor

    def choice(self, opcoes):
        return opcoes[0]


def lutador(classe="Guerreiro (Força Bruta)") -> Lutador:
    dados = SimpleNamespace(
        nome="Alvo",
        tamanho=1.7,
        forca=6.0,
        mana=5.0,
        resistencia=5.0,
        velocidade=5.0,
        classe=classe,
        personalidade="Aleatório",
        nome_arma="",
        arma_obj=None,
    )
    with patch("neural_fights.ai.AIBrain", return_value=None):
        return Lutador(dados, 5.0, 5.0)


class BrainPostura:
    """Fake mínimo para a postura do Cavaleiro (Onda 6): ação fixa e
    qualquer outro atributo lido vira 0.0 (aritmética-neutro)."""

    def __init__(self, acao: str):
        self.acao_atual = acao

    def __getattr__(self, nome):
        return 0.0


class CavaleiroPosturaTests(unittest.TestCase):
    def test_reducao_vale_quando_defende(self) -> None:
        cavaleiro = lutador("Cavaleiro (Defesa)")
        # Postura v2 e OPT-IN: escudo so em intencao defensiva explicita.
        cavaleiro.brain = BrainPostura("BLOQUEAR")
        cavaleiro.atacando = False
        vida_antes = cavaleiro.vida
        cavaleiro.tomar_dano(100.0, 0.0, 0.0)
        self.assertAlmostEqual(vida_antes - cavaleiro.vida, 75.0, delta=1.0)

    def test_reducao_dorme_durante_o_proprio_golpe(self) -> None:
        """Invicto 21/21 com a redução sempre-ativa: agora ataque = janela."""
        cavaleiro = lutador("Cavaleiro (Defesa)")
        cavaleiro.atacando = True  # no meio do proprio golpe
        vida_antes = cavaleiro.vida
        cavaleiro.tomar_dano(100.0, 0.0, 0.0)
        self.assertAlmostEqual(vida_antes - cavaleiro.vida, 100.0, delta=1.0)


class DuelistaContratoTests(unittest.TestCase):
    def test_esquiva_do_ladino_nao_vale_contra_duelista(self) -> None:
        """'Ataques nunca erram': a esquiva de 20% é o único errar do
        motor, e o Duelista a atravessa."""
        ladino = lutador("Ladino (Evasão)")
        ladino.rng_runtime = RngFixo(0.0)  # rolaria esquiva SEMPRE
        duelista = lutador("Duelista (Precisão)")
        vida_antes = ladino.vida
        ladino.tomar_dano(50.0, 0.0, 0.0, atacante=duelista)
        self.assertLess(ladino.vida, vida_antes)

    def test_esquiva_continua_valendo_contra_outros(self) -> None:
        ladino = lutador("Ladino (Evasão)")
        ladino.rng_runtime = RngFixo(0.0)
        guerreiro = lutador()
        vida_antes = ladino.vida
        ladino.tomar_dano(50.0, 0.0, 0.0, atacante=guerreiro)
        self.assertEqual(ladino.vida, vida_antes)

    def test_dez_por_cento_no_dano_do_duelista(self) -> None:
        duelista = lutador("Duelista (Precisão)")
        duelista.arma_critico = 0.0
        duelista.rng_runtime = RngFixo(0.99)  # nunca crita
        guerreiro = lutador()
        guerreiro.arma_critico = 0.0
        guerreiro.rng_runtime = RngFixo(0.99)

        dano_d, _ = duelista.calcular_dano_ataque(30.0)
        dano_g, _ = guerreiro.calcular_dano_ataque(30.0)
        # mesmos insumos, classes com mod_forca distinto: compara a RAZÃO
        # do bônus isolando os mods (10% na frente do resto da fórmula).
        razao = dano_d / dano_g
        mods = (
            duelista.class_data.get("mod_forca", 1.0)
            / guerreiro.class_data.get("mod_forca", 1.0)
        )
        self.assertAlmostEqual(razao / mods, 1.10, delta=0.02)


class CasterContratoTests(unittest.TestCase):
    """Onda 6 fase 2b: as passivas-fantasma dos casters do porão.

    Feiticeiro 2/40 (imóvel por três medições) declarava "magias têm 15%
    de chance de lançar duas vezes" sem implementação; Piromante 0,103
    declarava "+15% dano de fogo" — também fantasma (e o catálogo usa
    elemento "FOGO" em caixa alta, armadilha de case)."""

    def _conjurador(self, classe):
        p = lutador(classe)
        from neural_fights.core.skills import get_skill_data

        data = get_skill_data("Bola de Fogo")
        p.skills_classe.append(
            {"nome": "Bola de Fogo", "custo": 25.0, "data": data}
        )
        p.cd_skills["Bola de Fogo"] = 0.0
        p.mana = 200.0
        return p

    def test_eco_do_caos_lanca_duas_vezes_com_um_custo(self) -> None:
        from unittest.mock import patch as _patch

        feiticeiro = self._conjurador("Feiticeiro (Caos)")
        feiticeiro.rng_runtime = RngFixo(0.0)  # eco sempre proca
        mana_antes = feiticeiro.mana
        with _patch(
            "neural_fights.effects.audio.AudioManager.get_instance",
            return_value=None,
        ):
            self.assertTrue(feiticeiro.usar_skill_classe("Bola de Fogo"))
        self.assertEqual(len(feiticeiro.buffer_projeteis), 2)
        # um unico custo, um unico cast contado, um unico cooldown
        self.assertAlmostEqual(mana_antes - feiticeiro.mana, 25.0, delta=5.0)
        self.assertEqual(feiticeiro.contadores_luta["skills_lancadas"], 1)

    def test_fogo_do_piromante_queima_mais(self) -> None:
        from unittest.mock import patch as _patch

        piromante = self._conjurador("Piromante (Fogo)")
        piromante.rng_runtime = RngFixo(0.99)
        mago = self._conjurador("Mago (Arcano)")
        mago.rng_runtime = RngFixo(0.99)
        with _patch(
            "neural_fights.effects.audio.AudioManager.get_instance",
            return_value=None,
        ):
            self.assertTrue(piromante.usar_skill_classe("Bola de Fogo"))
            self.assertTrue(mago.usar_skill_classe("Bola de Fogo"))
        dano_piro = piromante.buffer_projeteis[0].dano
        dano_mago = mago.buffer_projeteis[0].dano
        self.assertAlmostEqual(dano_piro / dano_mago, 1.25, delta=0.02)  # r2 da O6


class FuriaDoEncurraladoTests(unittest.TestCase):
    def test_atras_25pp_bate_15_mais_forte(self) -> None:
        """Variância mecânica (O6): o dente físico das viradas D1/D2."""
        alvo = lutador()
        atacante_atras = lutador()
        atacante_atras.vida = atacante_atras.vida_max * 0.5  # 50pp atras

        vida_antes = alvo.vida
        alvo.tomar_dano(100.0, 0.0, 0.0, atacante=atacante_atras)
        dano_furioso = vida_antes - alvo.vida

        alvo2 = lutador()
        atacante_igual = lutador()
        vida_antes = alvo2.vida
        alvo2.tomar_dano(100.0, 0.0, 0.0, atacante=atacante_igual)
        dano_normal = vida_antes - alvo2.vida

        self.assertAlmostEqual(dano_furioso / dano_normal, 1.15, delta=0.02)


class PenetracaoTests(unittest.TestCase):
    def test_penetracao_recupera_parte_da_reducao_defensiva(self) -> None:
        """O encantamento mais comum do catálogo nunca foi lido (deferido
        da O3). 'Ignora 30% da defesa': recupera 30% do que as reduções
        defensivas tiraram."""
        alvo = lutador()
        alvo.mod_defesa = 0.5

        comum = lutador()
        vida_antes = alvo.vida
        alvo.tomar_dano(100.0, 0.0, 0.0, atacante=comum)
        dano_comum = vida_antes - alvo.vida  # 50

        perfurador = lutador()
        perfurador.arma_encantamentos = ["Penetração"]
        vida_antes = alvo.vida
        alvo.tomar_dano(100.0, 0.0, 0.0, atacante=perfurador)
        dano_pen = vida_antes - alvo.vida  # 50 + 50*0.3 = 65

        self.assertAlmostEqual(dano_comum, 50.0, delta=2.0)
        self.assertAlmostEqual(dano_pen, 65.0, delta=2.0)


class PaladinoPocoTests(unittest.TestCase):
    def test_cura_seca_no_teto_do_poco(self) -> None:
        """Regen infinita era imortalidade prática; o poço agora SECA."""
        paladino = lutador("Paladino (Sagrado)")
        paladino.vida = paladino.vida_max * 0.2
        # ~200s de regen a 0,5%/s pediriam 100% da vida; o poço dá 18%
        # (0,25 -> 0,18 na rodada 2 de knobs: Paladino imóvel em 0,743).
        for _ in range(200 * 10):
            paladino._regenerar_cura_passiva(0.1)
        curado = paladino.vida - paladino.vida_max * 0.2
        self.assertLessEqual(curado, paladino.vida_max * 0.15 + 1.0)  # r3
        self.assertGreater(curado, paladino.vida_max * 0.12)


if __name__ == "__main__":
    unittest.main()
