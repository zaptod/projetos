"""Contratos da obediência ao diretor de combate.

O ``CombatChoreographer`` dá ritmo cinematográfico à luta, e isso é desejável.
Mas a marcação dele era um override incondicional: em 53% dos frames a
personalidade do lutador não era sequer consultada, então metade da luta era
igual para todo mundo por construção.

Estes testes fixam a regra que quebrou esse teto -- o perfil decide se o lutador
obedece -- e as duas propriedades que a tornam utilizável numa transmissão: a
decisão é estável dentro de uma batida, e o diretor nunca perde nem controla a
luta por completo.
"""

from __future__ import annotations

import os
import random
import unittest
from types import SimpleNamespace

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from neural_fights.ai.brain import AIBrain
from neural_fights.core.entities import Lutador


def cerebro(tracos, semente: int = 1) -> AIBrain:
    dados = SimpleNamespace(
        nome="Alvo",
        tamanho=1.7,
        forca=5.0,
        mana=5.0,
        resistencia=5.0,
        velocidade=5.0,
        classe="Guerreiro (Força Bruta)",
        personalidade="Aleatório",
        nome_arma="",
        arma_obj=None,
    )
    brain = Lutador(dados, 5.0, 5.0).brain
    brain.tracos = list(tracos)
    brain.rng = random.Random(semente)
    return brain


def taxa_de_aceitacao(tracos, acao, amostras: int = 4000) -> float:
    """Fração de batidas em que o lutador obedece à marcação."""
    brain = cerebro(tracos)
    aceitas = 0
    for _ in range(amostras):
        brain._direcao_avaliada = None  # cada iteração é uma batida nova
        if brain._aceita_direcao(acao):
            aceitas += 1
    return aceitas / amostras


class NaturezaDaDirecaoTests(unittest.TestCase):
    def test_toda_acao_do_diretor_tem_natureza_declarada(self) -> None:
        """Marcação sem natureza cairia em 'neutra' e perderia o contraste."""
        import inspect

        fonte = inspect.getsource(AIBrain._executar_acao_sincronizada)
        declaradas = set(AIBrain.NATUREZA_DA_DIRECAO)
        for acao in ("PREPARAR_ATAQUE", "FUGIR_DRAMATICO", "CLASH", "ATAQUE_FINAL"):
            with self.subTest(acao=acao):
                self.assertIn(f'"{acao}"', fonte)
                self.assertIn(acao, declaradas)

    def test_naturezas_sao_do_vocabulario_conhecido(self) -> None:
        self.assertTrue(
            set(AIBrain.NATUREZA_DA_DIRECAO.values())
            <= {"passiva", "recuo", "agressiva"}
        )


class CaraterTests(unittest.TestCase):
    def test_agressivo_recusa_marcacao_passiva(self) -> None:
        """Um berserker não circula devagar porque o roteiro pediu."""
        agressivo = taxa_de_aceitacao(["BERSERKER", "KAMIKAZE"], "CIRCULAR_LENTO")
        defensivo = taxa_de_aceitacao(["CAUTELOSO", "PRUDENTE"], "CIRCULAR_LENTO")
        self.assertLess(agressivo, 0.5)
        self.assertGreater(defensivo, 0.8)
        self.assertLess(agressivo, defensivo)

    def test_agressivo_recusa_recuar(self) -> None:
        agressivo = taxa_de_aceitacao(["BERSERKER", "IMPLACAVEL"], "RECUPERAR")
        self.assertLess(agressivo, 0.5)

    def test_cauteloso_recusa_entrar_no_clash(self) -> None:
        cauteloso = taxa_de_aceitacao(["CAUTELOSO", "COVARDE"], "CLASH")
        agressivo = taxa_de_aceitacao(["BERSERKER"], "CLASH")
        self.assertLess(cauteloso, agressivo)

    def test_caotico_improvisa_em_qualquer_marcacao(self) -> None:
        for acao in ("CIRCULAR_LENTO", "CLASH", "RECUPERAR"):
            with self.subTest(acao=acao):
                caotico = taxa_de_aceitacao(["CAOTICO", "ERRATICO"], acao)
                comum = taxa_de_aceitacao(["PACIENTE"], acao)
                self.assertLess(caotico, comum)

    def test_frieza_segura_o_plano(self) -> None:
        frio = taxa_de_aceitacao(["FRIO", "ZEN"], "CIRCULAR_LENTO")
        neutro = taxa_de_aceitacao(["SALTADOR"], "CIRCULAR_LENTO")
        self.assertGreater(frio, neutro)

    def test_perfis_opostos_divergem_de_verdade(self) -> None:
        agressivo = taxa_de_aceitacao(["BERSERKER", "KAMIKAZE"], "CIRCULAR_LENTO")
        defensivo = taxa_de_aceitacao(["CAUTELOSO", "PRUDENTE"], "CIRCULAR_LENTO")
        self.assertGreater(defensivo - agressivo, 0.3)


class EstabilidadeTests(unittest.TestCase):
    def test_decisao_e_mantida_dentro_da_batida(self) -> None:
        """Sortear por frame viraria tremor na tela, não personalidade."""
        brain = cerebro(["CAOTICO", "ERRATICO"])
        primeira = brain._aceita_direcao("CIRCULAR_LENTO")
        for _ in range(500):
            self.assertIs(brain._aceita_direcao("CIRCULAR_LENTO"), primeira)

    def test_batida_nova_e_reavaliada(self) -> None:
        brain = cerebro(["CAOTICO"])
        brain._aceita_direcao("CIRCULAR_LENTO")
        avaliada = brain._direcao_avaliada
        brain._aceita_direcao("CLASH")
        self.assertNotEqual(brain._direcao_avaliada, avaliada)


class LimitesTests(unittest.TestCase):
    def test_diretor_nunca_perde_a_luta_inteira(self) -> None:
        """Piso de obediência: sem ele o ritmo cinematográfico desaparece."""
        extremo = ["BERSERKER", "KAMIKAZE", "IMPLACAVEL", "CAOTICO", "ERRATICO"]
        self.assertGreater(taxa_de_aceitacao(extremo, "CIRCULAR_LENTO"), 0.10)

    def test_diretor_nunca_controla_por_completo(self) -> None:
        """Teto de obediência: sempre sobra imprevisibilidade."""
        disciplinado = ["FRIO", "ZEN", "METODICO", "PACIENTE"]
        self.assertLess(taxa_de_aceitacao(disciplinado, "CIRCULAR_LENTO"), 1.0)

    def test_marcacao_desconhecida_nao_quebra(self) -> None:
        brain = cerebro(["BERSERKER"])
        self.assertIn(brain._aceita_direcao("MARCACAO_INVENTADA"), (True, False))

    def test_lutador_sem_traco_obedece_na_maior_parte(self) -> None:
        self.assertGreater(taxa_de_aceitacao([], "CIRCULAR_LENTO"), 0.75)


if __name__ == "__main__":
    unittest.main()
