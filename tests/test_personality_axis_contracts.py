"""Contratos dos eixos de comportamento.

Antes destes eixos, um traço só existia se alguém tivesse escrito
``"NOME" in self.tracos`` em algum ponto do ``brain.py`` -- e 107 dos 162 traços
declarados não tinham consumidor algum. Estes testes fixam o contrato que faz
todo traço valer por construção, e a propriedade de mistura que ele habilita.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from neural_fights.ai.personalities import (
    EIXOS_COMPORTAMENTO,
    PERSONALIDADES_PRESETS,
    TODOS_TRACOS,
    TRACO_EIXOS,
    perfil_de_tracos,
)
from neural_fights.core.entities import Lutador
from neural_fights.tools import auditoria_personalidades


def lutador(personalidade: str = "Aleatório") -> Lutador:
    dados = SimpleNamespace(
        nome="Alvo",
        tamanho=1.7,
        forca=5.0,
        mana=5.0,
        resistencia=5.0,
        velocidade=5.0,
        classe="Guerreiro (Força Bruta)",
        personalidade=personalidade,
        nome_arma="",
        arma_obj=None,
    )
    return Lutador(dados, 5.0, 5.0)


class CoberturaDoCatalogoTests(unittest.TestCase):
    def test_todo_traco_declarado_tem_eixos(self) -> None:
        """A propriedade central: nenhum traço nasce inerte."""
        sem_eixos = sorted(set(TODOS_TRACOS) - set(TRACO_EIXOS))
        self.assertEqual(sem_eixos, [])

    def test_nenhum_eixo_orfao(self) -> None:
        orfaos = sorted(set(TRACO_EIXOS) - set(TODOS_TRACOS))
        self.assertEqual(orfaos, [])

    def test_todo_traco_opina_sobre_algo(self) -> None:
        """Dict vazio devolveria o traço à inércia, só que escondida."""
        vazios = sorted(t for t, v in TRACO_EIXOS.items() if not v)
        self.assertEqual(vazios, [])

    def test_eixos_e_valores_sao_validos(self) -> None:
        conhecidos = set(EIXOS_COMPORTAMENTO)
        for traco, valores in TRACO_EIXOS.items():
            with self.subTest(traco=traco):
                self.assertTrue(set(valores) <= conhecidos)
                for valor in valores.values():
                    self.assertGreaterEqual(valor, -1.0)
                    self.assertLessEqual(valor, 1.0)

    def test_catalogo_passa_na_propria_auditoria(self) -> None:
        erros, avisos = auditoria_personalidades.auditar()
        self.assertEqual(erros, [])
        self.assertEqual(avisos, [])


class PerfilTests(unittest.TestCase):
    def test_perfil_cobre_todos_os_eixos(self) -> None:
        perfil = perfil_de_tracos(["BERSERKER"])
        self.assertEqual(set(perfil), set(EIXOS_COMPORTAMENTO))

    def test_lista_vazia_produz_perfil_neutro(self) -> None:
        self.assertEqual(set(perfil_de_tracos([]).values()), {0.0})
        self.assertEqual(set(perfil_de_tracos(None).values()), {0.0})

    def test_tracos_opostos_se_misturam(self) -> None:
        """Antes, um ``elif`` fazia só o primeiro traço valer."""
        agressivo = perfil_de_tracos(["BERSERKER"])["agressao"]
        misto = perfil_de_tracos(["BERSERKER", "COVARDE"])["agressao"]
        self.assertLess(misto, agressivo)
        self.assertGreater(perfil_de_tracos(["BERSERKER", "COVARDE"])["medo"], 0.0)

    def test_perfil_satura_em_um(self) -> None:
        empilhados = ["BERSERKER", "KAMIKAZE", "IMPLACAVEL", "AGRESSIVO", "VIKING"]
        self.assertEqual(perfil_de_tracos(empilhados)["agressao"], 1.0)

    def test_traco_desconhecido_e_ignorado_sem_erro(self) -> None:
        """O perfil é lido no caminho quente; não pode derrubar a luta."""
        perfil = perfil_de_tracos(["BERSERKER", "TRACO_QUE_NAO_EXISTE"])
        self.assertEqual(perfil["agressao"], 0.9)

    def test_traços_antes_inertes_agora_produzem_perfil(self) -> None:
        """O preset 'Artista Marcial' fixava cinco traços sem consumidor."""
        antes_inertes = ["ARTISTA_MARCIAL", "CRIATIVO", "STYLIST", "ZEN"]
        perfil = perfil_de_tracos(antes_inertes)
        self.assertNotEqual(set(perfil.values()), {0.0})
        self.assertGreater(perfil["frieza"], 0.0)
        self.assertGreater(perfil["mobilidade"], 0.0)


class PerfilNoCerebroTests(unittest.TestCase):
    def test_cerebro_expoe_perfil_dos_proprios_tracos(self) -> None:
        brain = lutador().brain
        self.assertEqual(brain.perfil, perfil_de_tracos(brain.tracos))

    def test_perfil_acompanha_traco_ganho_durante_a_luta(self) -> None:
        """O cérebro adiciona traços ao evoluir; o cache precisa invalidar."""
        brain = lutador().brain
        brain.tracos = ["CAUTELOSO"]
        antes = brain.perfil["agressao"]
        brain.tracos.append("KAMIKAZE")
        self.assertGreater(brain.perfil["agressao"], antes)

    def test_perfil_e_reusado_enquanto_os_tracos_nao_mudam(self) -> None:
        brain = lutador().brain
        self.assertIs(brain.perfil, brain.perfil)


class PresetsTests(unittest.TestCase):
    def test_nenhum_preset_fixa_traco_inerte(self) -> None:
        """Era o sintoma mais visível: preset rico, comportamento neutro."""
        inertes = []
        for nome, preset in PERSONALIDADES_PRESETS.items():
            for traco in preset.get("tracos_fixos", ()):
                if not TRACO_EIXOS.get(traco):
                    inertes.append(f"{nome}: {traco}")
        self.assertEqual(inertes, [])

    def test_todo_preset_produz_perfil_nao_neutro(self) -> None:
        for nome, preset in PERSONALIDADES_PRESETS.items():
            fixos = list(preset.get("tracos_fixos", ()))
            if not fixos:
                continue
            with self.subTest(preset=nome):
                perfil = perfil_de_tracos(fixos)
                self.assertNotEqual(
                    set(perfil.values()), {0.0}, f"preset {nome} não muda nada"
                )

    def test_presets_distintos_produzem_perfis_distintos(self) -> None:
        agressivo = perfil_de_tracos(
            PERSONALIDADES_PRESETS["Agressivo"]["tracos_fixos"]
        )
        defensivo = perfil_de_tracos(
            PERSONALIDADES_PRESETS["Defensivo"]["tracos_fixos"]
        )
        self.assertNotEqual(agressivo, defensivo)
        self.assertGreater(agressivo["agressao"], defensivo["agressao"])


if __name__ == "__main__":
    unittest.main()
