"""Atributos escolhidos em vez de sorteados.

O que este arquivo trava:

1. **O sorteio nao se desloca.** Fixar um atributo muda ELE e o que
   legitimamente depende dele — nunca o resto por efeito colateral. E por
   isso que a roleta fixada continua girando e consumindo o rng dela.
2. **A entrada e a de TELA.** Quem digita ve "1,80 m" e "7,4 de forca", nao
   os inteiros escalados (180, 74) que o motor guarda.
3. **Escolha invalida para alto.** Atributo que nao existe, valor fora da
   faixa ou opcao inexistente erram na entrada, nunca viram sorteio silencioso.
4. **O video nao mente.** Havendo escolha, o gancho para de dizer "100%
   aleatorio" e a legenda da roleta fixada para de creditar a sorte.
5. **O catalogo sai das roletas**, nao de uma lista paralela.

Rode de dentro de random_builds/:
    python -m pytest tests/test_escolhas_regressions.py -q
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.content.caption_generator import CaptionGenerator               # noqa: E402
from src.generation import escolhas as mod                               # noqa: E402
from src.generation.session_generator import (SessionGenerator,          # noqa: E402
                                              load_config)

SEED = 4242
CAPTIONS = CaptionGenerator(load_config("captions.json"), load_config("frases.json"))


class CatalogoTests(unittest.TestCase):
    def test_o_catalogo_vem_das_roletas(self):
        """Lista paralela divergiria no dia em que o jogo ganhasse uma classe."""
        from src.nf_bridge import roulette_factory

        catalogo = mod.catalogo()
        ids_das_roletas = {r["id"] for config in
                           (roulette_factory.character_roulettes(),
                            roulette_factory.weapon_roulettes())
                           for r in config["roulettes"]}
        self.assertTrue(ids_das_roletas <= set(catalogo))
        classes = catalogo["classe"]["opcoes"]
        self.assertEqual(classes,
                         [o["label"] for o in
                          roulette_factory.character_roulettes()["roulettes"][0]["options"]])

    def test_genero_entra_mesmo_sem_ser_roleta(self):
        entrada = mod.catalogo()["genero"]
        self.assertTrue(entrada["fora_da_roleta"])
        self.assertEqual(["masculino", "feminino"], entrada["opcoes"])

    def test_a_faixa_e_a_de_TELA_e_nao_a_interna(self):
        """A roleta guarda cm; quem digita ve metros."""
        tamanho = mod.catalogo()["tamanho"]
        self.assertEqual((1.4, 2.2), (tamanho["minimo"], tamanho["maximo"]))
        self.assertEqual("m", tamanho["unidade"])
        self.assertEqual(100, tamanho["escala"])

    def test_descrever_lista_todos_sem_quebrar(self):
        linhas = mod.descrever()
        self.assertEqual(len(mod.catalogo()), len(linhas))
        self.assertTrue(any("genero" in linha for linha in linhas))


class InterpretarTests(unittest.TestCase):
    def test_valor_de_tela_vira_inteiro_escalado(self):
        escolha = mod.interpretar(["tamanho=1,80", "forca=7,4"])
        self.assertEqual(180, escolha["roletas"]["tamanho"])
        self.assertEqual(74, escolha["roletas"]["forca"])

    def test_ponto_e_virgula_valem_o_mesmo(self):
        self.assertEqual(mod.interpretar(["tamanho=1.80"])["roletas"],
                         mod.interpretar(["tamanho=1,80"])["roletas"])

    def test_acento_e_caixa_nao_atrapalham(self):
        self.assertEqual("Mítico", mod.interpretar(["raridade=mitico"])["roletas"]["raridade"])

    def test_prefixo_unico_serve(self):
        """"Cavaleiro" acha "Cavaleiro (Defesa)" — ninguem decora o parentese."""
        self.assertEqual("Cavaleiro (Defesa)",
                         mod.interpretar(["classe=Cavaleiro"])["roletas"]["classe"])

    def test_prefixo_ambiguo_erra_dizendo_entre_quais(self):
        """"A" serve a Agressivo, Assassino, Acrobatico... escolher por voce
        seria pior do que perguntar."""
        with self.assertRaises(ValueError) as caso:
            mod.interpretar(["personalidade=A"])
        self.assertIn("ambiguo", str(caso.exception))

    def test_genero_aceita_as_formas_que_uma_pessoa_digita(self):
        for texto in ("f", "feminino", "Feminino", "mulher"):
            self.assertEqual("f", mod.interpretar([f"genero={texto}"])["genero"])

    def test_atributo_desconhecido_erra_alto(self):
        with self.assertRaises(ValueError):
            mod.interpretar(["altura=1,80"])

    def test_valor_fora_da_faixa_erra_alto(self):
        with self.assertRaises(ValueError) as caso:
            mod.interpretar(["tamanho=3,50"])
        self.assertIn("faixa", str(caso.exception))

    def test_opcao_inexistente_lista_o_que_existe(self):
        with self.assertRaises(ValueError) as caso:
            mod.interpretar(["classe=Necromante Sombrio"])
        self.assertIn("Opcoes:", str(caso.exception))

    def test_par_sem_igual_erra_alto(self):
        with self.assertRaises(ValueError):
            mod.interpretar(["classe"])

    def test_sem_escolha_nenhuma_o_formato_continua_sorteado(self):
        self.assertFalse(mod.houve(mod.interpretar([])))
        self.assertFalse(mod.houve(None))
        self.assertTrue(mod.houve(mod.interpretar(["genero=f"])))

    def test_cada_gerador_ve_so_as_proprias_roletas(self):
        escolha = mod.interpretar(["classe=Mago (Arcano)", "raridade=Comum"])
        self.assertEqual({"classe"}, set(mod.por_entidade(escolha, "character")))
        self.assertEqual({"raridade"}, set(mod.por_entidade(escolha, "weapon")))


class SorteioTests(unittest.TestCase):
    """A promessa central: escolher um atributo nao remexe os outros."""

    @classmethod
    def setUpClass(cls):
        cls.gerador = SessionGenerator()
        cls.base = cls.gerador.generate(seed=SEED, generation_id="base")

    def _com(self, *pares):
        return self.gerador.generate(seed=SEED, generation_id="novo",
                                     escolhas=mod.interpretar(list(pares)))

    def _valores(self, geracao):
        return {r["roulette_id"]: r["value"] for r in geracao["rolls"]}

    def test_fixar_altura_muda_SO_a_altura(self):
        novo = self._com("tamanho=1,92")
        antes, depois = self._valores(self.base), self._valores(novo)
        diferentes = {k for k in antes if antes[k] != depois[k]}
        self.assertEqual({"tamanho"}, diferentes)
        self.assertEqual(192, depois["tamanho"])

    def test_fixar_altura_nao_mexe_no_registro_do_jogo(self):
        """Nome, arma e cor saem do mesmo rng: um `choice` a menos deslocaria tudo."""
        novo = self._com("tamanho=1,92")
        for campo in ("nome", "nome_arma", "cor_r", "cor_g", "cor_b"):
            self.assertEqual(self.base["character"][campo],
                             novo["character"][campo], campo)

    def test_fixar_genero_nao_muda_nenhuma_roleta(self):
        novo = self._com("genero=feminino")
        self.assertEqual(self._valores(self.base), self._valores(novo))
        self.assertEqual("f", novo["naming"]["character_gender"])

    def test_fixar_genero_nao_muda_a_arma(self):
        """Sem consumir o sorteio de genero, a arma e a cor mudariam junto."""
        novo = self._com("genero=feminino")
        self.assertEqual(self.base["weapon"]["nome"], novo["weapon"]["nome"])
        self.assertEqual(self.base["character"]["cor_r"], novo["character"]["cor_r"])

    def test_o_genero_sorteado_fica_registrado(self):
        novo = self._com("genero=feminino")
        self.assertEqual(self.base["naming"]["character_gender"],
                         novo["naming"]["generated_character_gender"])

    def test_a_roleta_fixada_ainda_gira(self):
        """Roda de um segmento so denunciaria a escolha na tela."""
        novo = self._com("classe=Cavaleiro")
        roll = next(r for r in novo["rolls"] if r["roulette_id"] == "classe")
        self.assertIsNotNone(roll["wheel"])
        self.assertGreater(len(roll["wheel"]["labels"]), 1)
        self.assertEqual("Cavaleiro (Defesa)",
                         roll["wheel"]["labels"][roll["wheel"]["winner"]])

    def test_o_evento_guarda_o_que_teria_saido(self):
        novo = self._com("tamanho=1,92")
        roll = next(r for r in novo["rolls"] if r["roulette_id"] == "tamanho")
        self.assertTrue(roll["escolhido"])
        base_roll = next(r for r in self.base["rolls"]
                         if r["roulette_id"] == "tamanho")
        self.assertEqual(base_roll["display_value"], roll["sorteado"])

    def test_o_generation_json_registra_a_escolha(self):
        novo = self._com("tamanho=1,92", "genero=feminino")
        registro = novo["escolhas"]
        self.assertEqual("f", registro["genero"])
        self.assertEqual({"tamanho": 192}, registro["roletas"])
        self.assertEqual("1,92", registro["tela"]["tamanho"])
        self.assertIn("tamanho", registro["sorteado"])

    def test_sem_escolha_a_chave_nem_existe(self):
        self.assertNotIn("escolhas", self.base)

    def test_a_escolha_chega_ao_personagem_do_jogo(self):
        novo = self._com("tamanho=1,92", "classe=Cavaleiro", "genero=feminino")
        self.assertEqual(1.92, novo["character"]["tamanho"])
        self.assertEqual("Cavaleiro (Defesa)", novo["character"]["classe"])
        self.assertEqual("f", novo["character"]["genero"])

    def test_regra_dependente_continua_valendo(self):
        """Raridade fixada estreita o dano — a regra manda, nao a escolha."""
        novo = self._com("raridade=Comum")
        dano = self._valores(novo)["dano"]
        alto = self._valores(self._com("raridade=Mítico"))["dano"]
        self.assertLess(dano, alto)

    def test_escolha_impossivel_depois_das_regras_erra_alto(self):
        """Estilo que o tipo sorteado nao oferece nao pode virar outro valor."""
        with self.assertRaises(ValueError) as caso:
            self.gerador.generate(seed=SEED, generation_id="x",
                                  escolhas=mod.interpretar(
                                      ["tipo=Arco", "estilo=Katana"]))
        self.assertIn("estilo", str(caso.exception))


class HonestidadeTests(unittest.TestCase):
    """O video nao pode dizer que sorteou o que foi escolhido."""

    def _ganchos(self, escolhas):
        return {CAPTIONS.hook(random.Random(s), None, escolhas)
                for s in range(60)}

    def test_sem_escolha_o_gancho_pode_afirmar_o_sorteio(self):
        ganchos = self._ganchos(None)
        self.assertTrue(any("ALEATORIO" in g or "SORTEADO" in g for g in ganchos))

    def test_com_escolha_o_gancho_nunca_diz_100_por_cento_aleatorio(self):
        for gancho in self._ganchos({"roletas": {"classe": "Mago (Arcano)"}}):
            self.assertNotIn("100% ALEATORIO", gancho)
            self.assertNotIn("NADA ESCOLHIDO", gancho)

    def test_o_pedido_de_nome_continua_mandando_no_gancho(self):
        """Pedido e escolha juntos: o credito ao comentario vem primeiro."""
        escolhidos = set(load_config("captions.json")["hook_escolhido"])
        for seed in range(40):
            gancho = CAPTIONS.hook(random.Random(seed), {"nome": "KAELEN"},
                                   {"roletas": {"classe": "Mago (Arcano)"}})
            self.assertNotIn(gancho, escolhidos)
            self.assertNotIn("100% ALEATORIO", gancho)

    def test_a_legenda_da_roleta_fixada_nao_credita_a_sorte(self):
        evento = {"roulette_id": "classe", "category": "CLASSE",
                  "display_value": "Cavaleiro (Defesa)", "tier": "AVERAGE",
                  "score": 50, "evaluation": {"method": "neutral"},
                  "escolhido": True, "sorteado": "Mago (Arcano)"}
        for seed in range(40):
            legenda = CAPTIONS.for_event(random.Random(seed), dict(evento))
            self.assertNotIn("roleta escolheu", legenda)
            self.assertNotIn("sorte", legenda.lower())
            self.assertIn("Cavaleiro (Defesa)", legenda)

    def test_legenda_de_roleta_normal_nao_muda(self):
        evento = {"roulette_id": "classe", "category": "CLASSE",
                  "display_value": "Mago (Arcano)", "tier": "AVERAGE",
                  "score": 50, "evaluation": {"method": "neutral"}}
        antes = CAPTIONS.for_event(random.Random(7), dict(evento))
        depois = CAPTIONS.for_event(random.Random(7), dict(evento))
        self.assertEqual(antes, depois)
        self.assertTrue(antes)


if __name__ == "__main__":
    unittest.main()
