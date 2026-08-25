"""Contratos de "roleta responsiva ao banco" que nao podem regredir.

O que este arquivo trava:

1. VALOR NOVO NAO DERRUBA NADA. Raridade, classe, tipo de arma, encantamento,
   elemento e skill que nao existiam entram no banco e as roletas continuam
   montando. Antes, uma raridade nova estourava KeyError dentro do
   __init__ do SessionGenerator - o programa inteiro morria antes de rolar a
   primeira roleta.
2. VALOR NOVO APARECE NA ROLETA. Nao basta nao quebrar: o item novo tem que
   estar nas opcoes, com peso e score coerentes.
3. PESO E SCORE DE RARIDADE SAEM DA POSICAO. Mais no fim da lista canonica =
   mais raro = peso menor e score maior, para qualquer tamanho de lista.
4. TIPO SEM ESTILO NAO ROUBA O ESTILO DE OUTRO TIPO. Herdar as variantes da
   Reta duplicava os 12 nomes dela na roleta, colidia id de regra de peso e
   fazia a roda destacar o segmento errado.
5. ID DE REGRA GERADA E UNICO. Id repetido nao levanta erro: a segunda regra
   sobrescreve a primeira e o efeito some sem ninguem ver.
6. A CURVA DE DANO NAO E COPIA. Ela e lida do proprio fonte de gerar_arma, e
   uma raridade fora da curva e extrapolada pela posicao.
7. O RELATORIO DE COBERTURA DIZ O NOME EXATO E O LUGAR EXATO. E funciona
   antes e depois de config/identity.json ganhar as traducoes de habilidade.
8. O relatorio nao arrasta a fila de identidade nem browser.

Rode de dentro de random_builds/:
    python -m pytest tests/test_cobertura_regressions.py -q
"""
from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.generation.entity_generator import EntityGenerator          # noqa: E402
from src.generation.probability_engine import ProbabilityEngine      # noqa: E402
from src.generation.random_engine import RandomEngine                # noqa: E402
from src.generation.rule_engine import RuleEngine                    # noqa: E402
from src.generation.session_generator import load_config             # noqa: E402
from src.generation.validation_engine import ValidationEngine        # noqa: E402
from src.evaluation.roll_evaluator import RollEvaluator              # noqa: E402
from src.nf_bridge import cobertura as cob                           # noqa: E402
from src.nf_bridge import loader as nf                               # noqa: E402
from src.nf_bridge import roulette_factory as rf                     # noqa: E402

RARIDADE_NOVA = "Divino"
CLASSE_NOVA = "Tecnomante (Plasma)"
TIPO_NOVO = "Escudo"
ENCANTAMENTO_NOVO = "Plasma"
GRUPO_NOVO = "PLASMA"
SKILL_NOVA = "Pulso de Plasma"
GRUPO_ORFAO = "SONICO"
SKILL_ORFA = "Grito Sonico"


@contextlib.contextmanager
def banco_ampliado():
    """Injeta no banco VIVO do jogo um item de cada categoria e desfaz depois.

    Mutacao no lugar de proposito: as listas canonicas sao o MESMO objeto que
    o neural_fights usa, entao o teste reproduz o cenario real (o jogo ganhou
    conteudo) em vez de um dado falso que so a roleta enxerga.
    """
    nf.LISTA_RARIDADES.append(RARIDADE_NOVA)
    nf.LISTA_CLASSES.append(CLASSE_NOVA)
    nf.LISTA_TIPOS_ARMA.append(TIPO_NOVO)
    nf.LISTA_ENCANTAMENTOS.append(ENCANTAMENTO_NOVO)
    nf.ENCANTAMENTOS[ENCANTAMENTO_NOVO] = {"elemento": "Plasma", "dano_bonus": 5.0}
    nf.SKILL_DB[SKILL_NOVA] = {"dano": 42, "tipo": "PROJETIL", "custo": 22}
    nf.SKILL_DB[SKILL_ORFA] = {"dano": 30, "tipo": "AREA", "custo": 18}
    nf.SKILLS_OFENSIVAS[GRUPO_NOVO] = [SKILL_NOVA]
    nf.SKILLS_OFENSIVAS[GRUPO_ORFAO] = [SKILL_ORFA]
    try:
        yield
    finally:
        nf.LISTA_RARIDADES.remove(RARIDADE_NOVA)
        nf.LISTA_CLASSES.remove(CLASSE_NOVA)
        nf.LISTA_TIPOS_ARMA.remove(TIPO_NOVO)
        nf.LISTA_ENCANTAMENTOS.remove(ENCANTAMENTO_NOVO)
        del nf.ENCANTAMENTOS[ENCANTAMENTO_NOVO]
        del nf.SKILL_DB[SKILL_NOVA]
        del nf.SKILL_DB[SKILL_ORFA]
        del nf.SKILLS_OFENSIVAS[GRUPO_NOVO]
        del nf.SKILLS_OFENSIVAS[GRUPO_ORFAO]


def roleta(config: dict, rid: str) -> dict:
    return next(r for r in config["roulettes"] if r["id"] == rid)


def valores(config: dict, rid: str) -> list:
    return [o["value"] for o in roleta(config, rid)["options"]]


class BancoAmpliadoNaoQuebra(unittest.TestCase):
    """Exigencia 1: nenhum valor novo pode causar excecao."""

    def test_roletas_montam_com_valor_novo_de_toda_categoria(self):
        with banco_ampliado():
            personagem = rf.character_roulettes()
            arma = rf.weapon_roulettes()
            regras = rf.generated_rules()
        self.assertTrue(personagem["roulettes"])
        self.assertTrue(arma["roulettes"])
        self.assertTrue(regras)

    def test_valor_novo_aparece_nas_opcoes(self):
        with banco_ampliado():
            personagem = rf.character_roulettes()
            arma = rf.weapon_roulettes()
            self.assertIn(CLASSE_NOVA, valores(personagem, "classe"))
            self.assertIn(RARIDADE_NOVA, valores(arma, "raridade"))
            self.assertIn(TIPO_NOVO, valores(arma, "tipo"))
            self.assertIn(ENCANTAMENTO_NOVO, valores(arma, "encantamento"))
            self.assertIn(SKILL_NOVA, valores(arma, "habilidade"))
            # tipo sem catalogo de estilo entra com uma variante propria
            self.assertIn(TIPO_NOVO, valores(arma, "estilo"))

    def test_skill_nova_so_e_liberada_pelo_encantamento_do_seu_elemento(self):
        with banco_ampliado():
            arma = rf.weapon_roulettes()
            opcao = next(o for o in roleta(arma, "habilidade")["options"]
                         if o["value"] == SKILL_NOVA)
            self.assertEqual(opcao["encs"], [ENCANTAMENTO_NOVO])
            # grupo que nenhum encantamento alcanca fica sem tag: a regra
            # habilidade_do_encantamento nunca o mantem
            orfa = next(o for o in roleta(arma, "habilidade")["options"]
                        if o["value"] == SKILL_ORFA)
            self.assertEqual(orfa["encs"], [])
            self.assertIn(GRUPO_ORFAO, nf.grupos_sem_encantamento())

    def test_ids_de_regra_gerada_nao_colidem(self):
        with banco_ampliado():
            regras = rf.generated_rules()
        ids = [r["id"] for r in regras]
        self.assertEqual(len(ids), len(set(ids)), "id de regra duplicado")

    def test_raridade_nova_ganha_regra_de_dano_e_piso_de_critico(self):
        with banco_ampliado():
            regras = rf.generated_rules()
            por_id = {r["id"]: r for r in regras}
            self.assertIn("dano_divino", por_id)
            critico = por_id["critico_raridade_alta"]
            self.assertIn(RARIDADE_NOVA, critico["when"]["value"])
            # a faixa da roleta de dano envolve a curva inteira
            arma = rf.weapon_roulettes()
            faixa = roleta(arma, "dano")
            clamp = por_id["dano_divino"]["then"][0]
            self.assertLessEqual(faixa["min"], clamp["min"])
            self.assertGreaterEqual(faixa["max"], clamp["max"])


class PesoEScoreSaemDaPosicao(unittest.TestCase):
    """Exigencia 2: item novo entra sozinho com peso coerente."""

    def test_mais_raro_tem_peso_menor_e_score_maior(self):
        for lista in ([], [RARIDADE_NOVA]):
            with self.subTest(extra=lista):
                ctx = banco_ampliado() if lista else contextlib.nullcontext()
                with ctx:
                    ordem = list(nf.LISTA_RARIDADES)
                    pesos = [nf.raridade_peso(r) for r in ordem]
                    scores = [nf.raridade_score(r) for r in ordem]
                self.assertEqual(pesos, sorted(pesos, reverse=True))
                self.assertEqual(scores, sorted(scores))
                self.assertEqual(len(set(scores)), len(scores))

    def test_raridade_no_topo_e_mais_rara_que_a_antiga_do_topo(self):
        antigo_topo = nf.LISTA_RARIDADES[-1]
        with banco_ampliado():
            self.assertLess(nf.raridade_peso(RARIDADE_NOVA),
                            nf.raridade_peso(antigo_topo))
            self.assertGreater(nf.raridade_score(RARIDADE_NOVA),
                               nf.raridade_score(antigo_topo))

    def test_raridade_no_meio_herda_peso_do_vizinho(self):
        meio = len(nf.LISTA_RARIDADES) // 2
        nf.LISTA_RARIDADES.insert(meio, RARIDADE_NOVA)
        try:
            peso = nf.raridade_peso(RARIDADE_NOVA)
            self.assertLess(peso, nf.raridade_peso(nf.LISTA_RARIDADES[meio - 1]))
            self.assertGreater(peso, nf.raridade_peso(nf.LISTA_RARIDADES[meio + 1]))
        finally:
            nf.LISTA_RARIDADES.remove(RARIDADE_NOVA)

    def test_metade_rara_e_a_lista_literal_do_gerar_arma_hoje(self):
        self.assertEqual(nf.raridades_de_elite(),
                         ["Épico", "Lendário", "Mítico"])


class CurvaDeDanoNaoECopia(unittest.TestCase):
    def test_curva_vem_do_fonte_de_gerar_arma(self):
        self.assertTrue(nf.DANO_BASE_POR_RARIDADE,
                        "a curva oficial nao foi lida do fonte de gerar_arma")
        for raridade in nf.LISTA_RARIDADES:
            self.assertIn(raridade, nf.DANO_BASE_POR_RARIDADE)

    def test_raridade_fora_da_curva_e_extrapolada_e_nao_cai_no_padrao(self):
        topo = nf.DANO_BASE_POR_RARIDADE[nf.LISTA_RARIDADES[-1]]
        with banco_ampliado():
            base = nf.dano_base(RARIDADE_NOVA)
        self.assertGreater(base, topo)
        self.assertNotEqual(base, nf.DANO_BASE_PADRAO)

    def test_envelope_de_hoje_bate_com_a_curva(self):
        bases = [nf.dano_base(r) for r in nf.LISTA_RARIDADES]
        self.assertEqual(nf.dano_envelope(),
                         (round(min(bases) - 3), round(max(bases) + 3)))


class EstiloNaoEHerdado(unittest.TestCase):
    def test_tipo_sem_catalogo_nao_rouba_variante_de_outro_tipo(self):
        with banco_ampliado():
            variantes = nf.variantes_do_tipo(TIPO_NOVO)
            self.assertEqual([v["nome"] for v in variantes], [TIPO_NOVO])
            por_estilo = nf.tipos_por_estilo()
        # nenhum estilo de outro tipo passou a pertencer ao tipo novo
        self.assertNotIn(TIPO_NOVO, por_estilo.get("Espada Longa", []))

    def test_nenhum_estilo_duplicado_na_roleta(self):
        with banco_ampliado():
            estilos = valores(rf.weapon_roulettes(), "estilo")
        self.assertEqual(len(estilos), len(set(estilos)))

    def test_cada_estilo_carrega_o_indice_da_variante_por_tipo(self):
        arma = rf.weapon_roulettes()
        for opcao in roleta(arma, "estilo")["options"]:
            for tipo in opcao["tipos"]:
                idx = opcao["variante_idx_por_tipo"][tipo]
                self.assertEqual(nf.variantes_do_tipo(tipo)[idx]["nome"],
                                 opcao["value"])


class RoletasGiramComBancoAmpliado(unittest.TestCase):
    """Nao basta montar: as 14 roletas tem que GIRAR com o banco maior."""

    def _motor(self, config):
        rules_config = load_config("rules.json")
        rules_config = {**rules_config,
                        "rules": rf.generated_rules() + rules_config.get("rules", [])}
        scoring = load_config("scoring.json")
        synergies = load_config("synergies.json")
        return EntityGenerator(
            config, ProbabilityEngine(load_config("probability.json")),
            RuleEngine(rules_config), ValidationEngine(rules_config),
            RollEvaluator(scoring, synergies))

    def test_200_seeds_sem_excecao_e_com_o_valor_novo_saindo(self):
        with banco_ampliado():
            char_gen = self._motor(rf.character_roulettes())
            weapon_gen = self._motor(rf.weapon_roulettes())
            vistos = set()
            for seed in range(200):
                engine = RandomEngine(seed)
                char, _ = char_gen.generate(engine.fork)
                arma, eventos = weapon_gen.generate(engine.fork,
                                                    extra_context={"character": char})
                vistos.add(char["classe"])
                vistos.update((arma["raridade"], arma["tipo"], arma["estilo"],
                               arma["encantamento"], arma["habilidade"]))
                for evento in eventos:
                    self.assertIsNotNone(evento["wheel"] or evento["value"])
        for novo in (CLASSE_NOVA, RARIDADE_NOVA, TIPO_NOVO,
                     ENCANTAMENTO_NOVO, SKILL_NOVA):
            self.assertIn(novo, vistos, f"{novo} nunca saiu em 200 seeds")
        self.assertNotIn(SKILL_ORFA, vistos,
                         "skill de grupo sem encantamento nao pode ser sorteada")


class RelatorioDeCobertura(unittest.TestCase):
    def test_acusa_o_valor_novo_com_nome_e_lugar_exatos(self):
        with banco_ampliado():
            texto = cob.relatorio()
        esperados = [
            'config/identity.json -> traducoes.raridade["Divino"]',
            'config/identity.json -> traducoes.classe["Tecnomante (Plasma)"]',
            'config/identity.json -> traducoes.tipo_arma["Escudo"]',
            'config/identity.json -> traducoes.estilo["Escudo"]',
            'config/identity.json -> traducoes.elemento["PLASMA"]',
            'config/identity.json -> traducoes.habilidade["Pulso de Plasma"]',
            'config/identity.json -> traducoes.encantamento["Plasma"]',
            'config/identity.json -> aura["PLASMA"]',
            'neural_fights/tools/gerador_database.py -> ESTILOS_ARMA["Escudo"]',
            "ENCANTAMENTOS: um encantamento com elemento 'SONICO'",
        ]
        for linha in esperados:
            self.assertIn(linha, texto)

    def test_banco_de_hoje_nao_tem_buraco_de_classe_estilo_e_tier(self):
        dados = cob.cobertura()
        por_id = {g["id"]: g for g in dados["grupos"]}
        for gid in ("traducoes.classe", "traducoes.personalidade",
                    "traducoes.tipo_arma", "traducoes.raridade",
                    "traducoes.estilo", "captions.by_tier",
                    "captions.final_by_verdict",
                    "editing.reaction_chance_by_tier",
                    "editing.effects_by_tier", "nf.estilos"):
            with self.subTest(grupo=gid):
                self.assertEqual(por_id[gid]["faltando"], [],
                                 f"{gid} regrediu: {por_id[gid]['faltando']}")

    def test_habilidade_lista_exatamente_o_que_falta_traduzir(self):
        """Vale antes e depois do agente de prompt preencher identity.json."""
        dados = cob.cobertura()
        grupo = next(g for g in dados["grupos"] if g["id"] == "traducoes.habilidade")
        with open(ROOT / "config" / "identity.json", encoding="utf-8") as fh:
            traduzidas = set((json.load(fh).get("traducoes") or {})
                             .get("habilidade") or {})
        esperado = [s for s in nf.skills_rolaveis() if s not in traduzidas]
        self.assertEqual([i["nome"] for i in grupo["faltando"]], esperado)
        self.assertEqual(grupo["total"], len(nf.skills_rolaveis()))
        for item in grupo["faltando"]:
            self.assertEqual(
                item["onde"],
                f'config/identity.json -> traducoes.habilidade["{item["nome"]}"]')

    def test_grupo_fica_ok_quando_as_traducoes_existem(self):
        """Prova o outro lado: cheio o grupo, o relatorio para de acusar."""
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp)
            for nome in ("identity.json", "scoring.json", "captions.json",
                         "editing.json"):
                shutil.copy(ROOT / "config" / nome, destino / nome)
            with open(destino / "identity.json", encoding="utf-8") as fh:
                identity = json.load(fh)
            identity["traducoes"]["habilidade"] = {
                s: "placeholder" for s in nf.skills_rolaveis()}
            identity["traducoes"]["encantamento"] = {
                e: "placeholder" for e in nf.LISTA_ENCANTAMENTOS}
            for elemento in nf.elementos_do_banco():
                identity["traducoes"]["elemento"].setdefault(elemento, "x")
                identity["aura"].setdefault(elemento, "x")
            with open(destino / "identity.json", "w", encoding="utf-8") as fh:
                json.dump(identity, fh, ensure_ascii=False)
            dados = cob.cobertura(config_dir=destino)
        por_id = {g["id"]: g for g in dados["grupos"]}
        for gid in ("traducoes.habilidade", "traducoes.encantamento",
                    "traducoes.elemento", "aura"):
            with self.subTest(grupo=gid):
                self.assertEqual(por_id[gid]["faltando"], [])

    def test_config_ausente_vira_erro_e_nao_excecao(self):
        with tempfile.TemporaryDirectory() as tmp:
            dados = cob.cobertura(config_dir=Path(tmp))
        self.assertFalse(dados["ok"])
        self.assertTrue(any(g["erro"] for g in dados["grupos"]))

    def test_relatorio_sai_no_console_do_windows(self):
        """O console e cp1252. A prosa e ASCII; o NOME do banco mantem o
        acento, senao o caminho copiado nao existe no JSON."""
        texto = cob.relatorio()
        texto.encode("cp1252")
        for linha in texto.splitlines():
            if "->" not in linha:  # linha de prosa, sem nome de banco
                linha.encode("ascii")
        with tempfile.TemporaryDirectory() as vazio:
            sem_config = cob.relatorio(config_dir=Path(vazio))
        self.assertIn('traducoes.raridade["Épico"]', sem_config)

    def test_relatorio_nao_arrasta_fila_de_identidade_nem_browser(self):
        codigo = (
            "import sys; sys.path.insert(0, r'%s');"
            "from src.nf_bridge.cobertura import relatorio, cobertura;"
            "relatorio(); cobertura();"
            "proibidos=[m for m in sys.modules if m in "
            "('src.identity.queue','src.identity.browser','patchright','playwright')];"
            "print('PROIBIDOS=' + ','.join(proibidos))" % ROOT
        )
        saida = subprocess.run([sys.executable, "-X", "utf8", "-c", codigo],
                               capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(saida.returncode, 0, saida.stderr)
        self.assertIn("PROIBIDOS=\n", saida.stdout.replace("\r\n", "\n"))


if __name__ == "__main__":
    unittest.main()
