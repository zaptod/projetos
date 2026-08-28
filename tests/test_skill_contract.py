# -*- coding: utf-8 -*-
"""Regressões do contrato de skills (Onda 11A) — o "MCP interno".

O teste-chave é PARIDADE contrato×runtime: quando a conta do contrato
divergir do que o runtime realmente cobra/faz, quebra teste, não gameplay.
"""

from __future__ import annotations

import random
import unittest
from types import SimpleNamespace

from neural_fights.ai.skill_strategy import SkillPurpose, SkillStrategySystem
from neural_fights.core.combat import Projetil, alvo_cumpre_condicao
from neural_fights.core.skill_contract import (
    CATEGORIAS_CONTROLE,
    catalogo_de_contratos,
    custo_efetivo,
    derivar_contrato,
)
from neural_fights.core.skills import SKILL_DB, get_skill_data
from neural_fights.utils.config import ALCANCE_CAST_PADRAO
from tests import test_remaining_skill_regressions as _helpers


def _estrategia(*skill_names):
    skills = [
        {
            "nome": nome,
            "data": get_skill_data(nome),
            "custo": get_skill_data(nome).get("custo", 15.0),
        }
        for nome in skill_names
    ]
    parent = SimpleNamespace(
        skills_arma=[],
        skills_classe=skills,
        mana=100.0,
        mana_max=100.0,
        vida=100.0,
        vida_max=100.0,
        cd_skills={},
    )
    return SkillStrategySystem(parent, SimpleNamespace(rng=random.Random(7)))


class SkillContractTests(unittest.TestCase):
    def test_todas_as_skills_derivam_contrato_serializavel(self):
        contratos = catalogo_de_contratos()
        self.assertEqual(len(contratos), len(SKILL_DB) - 1)  # sem "Nenhuma"
        for nome, contrato in contratos.items():
            dump = contrato.to_dict()
            self.assertEqual(dump["nome"], nome)
            self.assertIsInstance(dump["consequencias"], list)
            self.assertTrue(dump["descricao"], nome)

    def test_geometria_de_area_usa_alcance_de_cast(self):
        jc = derivar_contrato("Julgamento Celestial")
        self.assertEqual(jc.alcance_lancamento, 8.0)  # alcance_cast declarado
        self.assertEqual(jc.raio_efeito, 3.0)
        self.assertTrue(jc.ancorado_no_alvo)
        self.assertEqual(jc.pilares, 5)

        generica = derivar_contrato("Inferno")
        self.assertEqual(generica.alcance_lancamento, ALCANCE_CAST_PADRAO)

        centrada = derivar_contrato("Medo Profundo")
        self.assertTrue(centrada.centrado_no_caster)
        self.assertEqual(centrada.alcance_lancamento, 0.0)
        self.assertGreater(centrada.raio_efeito, 0.0)

    def test_skills_de_cc_ganham_proposito_de_controle_na_estrategia(self):
        # As listas literais antigas perdiam SILENCIADO, ENRAIZADO, KNOCK_UP,
        # TEMPO_PARADO... Agora a categoria do STATUS_RUNTIME decide.
        vitimas_da_lista_antiga = [
            "Explosão Arcana",   # SILENCIADO (cc)
            "Raízes",            # ENRAIZADO (cc)
            "Terremoto",         # KNOCK_UP (cc)
            "Parar o Tempo",     # TEMPO_PARADO (cc)
        ]
        strategy = _estrategia(*vitimas_da_lista_antiga)
        for nome in vitimas_da_lista_antiga:
            self.assertIn(
                SkillPurpose.CONTROL,
                strategy.skills[nome].propositos,
                nome,
            )

    def test_paridade_categoria_controle_no_catalogo_inteiro(self):
        for nome, contrato in catalogo_de_contratos().items():
            eh_cc = contrato.categoria_efeito in CATEGORIAS_CONTROLE
            if not eh_cc:
                continue
            strategy = None
            if contrato.tipo in ("PROJETIL", "BEAM", "AREA", "CHANNEL"):
                strategy = _estrategia(nome)
                if nome in strategy.skills:
                    self.assertIn(
                        SkillPurpose.CONTROL,
                        strategy.skills[nome].propositos,
                        nome,
                    )

    def test_combo_declarado_entra_no_contrato(self):
        shatter = derivar_contrato("Shatter")
        self.assertIn("Zero Absoluto", shatter.combo_apos)
        execucao = derivar_contrato("Execução")
        self.assertIn("Medo Profundo", execucao.combo_apos)

        # A estratégia consome o declarado E o derivado (status→condição),
        # com efeitos normalizados, sem duplicar pares.
        strategy = _estrategia("Zero Absoluto", "Shatter")
        pares = [(s1, s2) for s1, s2, _ in strategy.plano.combos]
        self.assertIn(("Zero Absoluto", "Shatter"), pares)
        self.assertEqual(len(pares), len(set(pares)))

    def test_finisher_em_qualquer_tipo_com_limiar_declarado(self):
        strategy = _estrategia("Execução")
        perfil = strategy.skills["Execução"]
        self.assertIn(SkillPurpose.FINISHER, perfil.propositos)
        self.assertAlmostEqual(perfil.hp_inimigo_max, 0.3)

    def test_consequencias_declaradas_por_tipo(self):
        self.assertIn(
            "objeto:projetil",
            derivar_contrato("Bola de Fogo").consequencias,
        )
        self.assertIn(
            "deslocamento:puxa",
            derivar_contrato("Buraco Negro").consequencias,
        )
        self.assertIn("terreno", derivar_contrato("Inferno").consequencias)
        self.assertIn(
            "bloqueio_projeteis",
            derivar_contrato("Muralha de Gelo").consequencias,
        )
        self.assertIn("cura", derivar_contrato("Fotossíntese").consequencias)


class CustoEfetivoParidadeTests(unittest.TestCase):
    def _cast(self, classe_nome=None):
        p = _helpers.RemainingSkillRegressionTests._fighter("Caster", x=0.0)
        alvo = _helpers.RemainingSkillRegressionTests._fighter("Alvo", x=3.0)
        if classe_nome:
            p.classe_nome = classe_nome
        _helpers.RemainingSkillRegressionTests._add_class_skill(p, "Bola de Fogo")
        custo_base = get_skill_data("Bola de Fogo").get("custo", 0.0)
        esperado = custo_efetivo(custo_base, p)
        mana_antes = p.mana
        self.assertTrue(p.usar_skill_classe("Bola de Fogo", alvo=alvo))
        return mana_antes - p.mana, esperado

    def test_paridade_com_o_debito_real_de_mana(self):
        debitado, esperado = self._cast()
        self.assertAlmostEqual(debitado, esperado)

    def test_paridade_com_desconto_de_mago(self):
        debitado, esperado = self._cast("Mago (Arcano)")
        custo_base = get_skill_data("Bola de Fogo").get("custo", 0.0)
        self.assertAlmostEqual(esperado, custo_base * 0.8)
        self.assertAlmostEqual(debitado, esperado)


class KnobsDeclaradosTests(unittest.TestCase):
    """Onda 11B: knobs que eram literais no motor agora fluem do catálogo."""

    def _area(self, nome):
        from neural_fights.core.combat import AreaEffect

        dono = _helpers.RemainingSkillRegressionTests._fighter("Caster", x=0.0)
        return AreaEffect(nome, 0.0, 0.0, dono)

    def test_forca_de_puxar_declarada_flui_para_a_area(self):
        area = self._area("Buraco Negro")
        self.assertAlmostEqual(
            area.forca_puxar,
            float(get_skill_data("Buraco Negro")["forca_puxar"]),
        )
        # Área sem puxão nenhum continua com força zero.
        self.assertEqual(self._area("Inferno").forca_puxar, 0.0)

    def test_ritmo_de_tick_declarado_flui_para_a_area(self):
        area = self._area("Inferno")
        self.assertAlmostEqual(
            area.tick_interval,
            float(get_skill_data("Inferno")["tick_interval"]),
        )
        # Sem declaração, o default de 0,5 s permanece.
        self.assertAlmostEqual(self._area("Buraco Negro").tick_interval, 0.5)


class CondicaoLimiarRuntimeTests(unittest.TestCase):
    def test_limiar_declarado_e_consumido_pelo_runtime(self):
        p = _helpers.RemainingSkillRegressionTests._fighter("Caster", x=0.0)
        alvo = _helpers.RemainingSkillRegressionTests._fighter("Alvo", x=3.0)
        proj = Projetil("Execução", 0.0, 0.0, 0.0, p)
        self.assertAlmostEqual(proj.condicao_limiar, 0.3)

        alvo.vida = alvo.vida_max * 0.31
        self.assertEqual(proj.verificar_condicao(alvo), 1.0)
        alvo.vida = alvo.vida_max * 0.29
        self.assertEqual(proj.verificar_condicao(alvo), 2.0)

        # O limiar flui como parâmetro declarado, não literal no código.
        self.assertTrue(alvo_cumpre_condicao(alvo, "ALVO_BAIXA_VIDA", 0.3))
        self.assertFalse(alvo_cumpre_condicao(alvo, "ALVO_BAIXA_VIDA", 0.2))


if __name__ == "__main__":
    unittest.main()
