"""Contratos da CTA "seu personagem" que nao podem regredir.

O que este arquivo trava:

1. NENHUMA frase desenhavel fala em SEED. Seed e detalhe de reproducao do
   pipeline; o espectador nao tem o que fazer com ela. A CTA agora pede um
   NOME, que e uma coisa que ele consegue comentar.
2. O placeholder do nome NUNCA vaza cru para a tela. A substituicao dos bancos
   e literal (str.replace), entao a unica defesa possivel e a rede de
   seguranca: sobrou chave -> descarta a frase e usa o banco neutro.
3. Banco neutro nao tem placeholder nenhum. Se tivesse, um video sem nome
   pedido mostraria as chaves e nao haveria de onde tirar o valor.
4. O campo do nome pedido e lido de forma defensiva: ele nasce em outra etapa
   do pipeline e geracoes antigas nao o tem. Sem ele o video se comporta como
   antes - convida, nao credita.
5. As frases cabem na tela: <= 38 caracteres depois de substituir o pior nome.

Rode de dentro de random_builds/:
    python -m pytest tests/test_cta_regressions.py -q
"""
from __future__ import annotations

import json
import random
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from builds.assets.catalog import AssetCatalog                             # noqa: E402
from builds.assets.selector import AssetSelector                           # noqa: E402
from builds.content import caption_generator as cg                         # noqa: E402
from builds.content.caption_generator import CaptionGenerator, pedido_de   # noqa: E402
from builds.editing.timeline_builder import TimelineBuilder                # noqa: E402
from builds.generation.random_engine import RandomEngine                   # noqa: E402
from builds.generation.session_generator import (SessionGenerator,         # noqa: E402
                                              load_config)
from builds.identity import slots as identity_slots                        # noqa: E402

CAPTIONS = load_config("captions.json")
FRASES = load_config("frases.json")
EDICAO = load_config("editing.json")

# Teto do texto FIXO dos bancos, sem nome pedido dentro. Medido com as fontes
# reais do perfil celular (1080x1920).
TETO_CHARS = 38

# Teto da frase JA com o pior nome/autor dentro. Medido (nao estimado) com
# ariblk.ttf, largura util 972 px, `fit_font_wrap(start=91, max_lines=3)`: a
# pior das 51 frases da CTA fica em 46 px e 3 linhas, sem estourar a largura.
# Encolher a fonte e o preco aceito por mostrar o nome INTEIRO - o preco de
# nao encolher seria "CRIANDO BARTOLOMEU AGU" na tela.
TETO_CHARS_COM_NOME = 52

# Bancos da CTA - os que este arquivo possui.
BANCOS_NEUTROS = ("hook", "outro")
BANCOS_PEDIDO = ("hook_pedido", "outro_pedido", "outro_pedido_autor",
                 "identity_pedido", "nameplate_pedido")

# Pior caso REAL: o teto de cg.LIMITE_NOME, que e o mesmo teto com que o nome
# foi aceito (nomes.MAX_CHARS_PEDIDO). Derivado da constante e nao escrito a
# mao: um teto que subir sem este arquivo saber deixaria o "pior caso" de ser
# o pior caso, e o teste passaria medindo a coisa errada.
def _pior_caso(base: str) -> str:
    """Exatamente cg.LIMITE_NOME caracteres, sem espaco pendurado na ponta."""
    texto = (base * 8)[:cg.LIMITE_NOME].rstrip()
    return texto + "X" * (cg.LIMITE_NOME - len(texto))


PIOR_NOME = _pior_caso("MARIA FERNANDA DA SILVA ")
PIOR_AUTOR = _pior_caso("@JOAOZINHOMARIAFERNANDA2010")


def _frases(objeto, caminho=""):
    """Toda string folha do captions.json, com o caminho ate ela."""
    if isinstance(objeto, dict):
        for chave, valor in objeto.items():
            if str(chave).startswith("_"):
                continue      # `_comment_*` explica o banco, nao vai na tela
            yield from _frases(valor, caminho + "/" + chave)
    elif isinstance(objeto, list):
        for indice, valor in enumerate(objeto):
            yield from _frases(valor, caminho + "[%d]" % indice)
    elif isinstance(objeto, str):
        yield caminho, objeto


class RngFixo(random.Random):
    """rng que escolhe sempre a MESMA posicao do pool.

    Serve para varrer banco por banco: com rng de verdade um banco de 8 frases
    passaria no teste sem que a oitava fosse olhada uma vez.
    """

    def __init__(self, indice: int):
        super().__init__(0)
        self.indice = indice

    def choice(self, seq):
        return seq[self.indice % len(seq)]


def _gerador() -> CaptionGenerator:
    return CaptionGenerator(json.loads(json.dumps(CAPTIONS)), FRASES)


class BancoDeFrasesTests(unittest.TestCase):
    def test_nenhuma_frase_fala_em_seed(self):
        achados = [(c, f) for c, f in _frases(CAPTIONS)
                   if "seed" in f.lower()]
        self.assertEqual([], achados)

    def test_nenhuma_frase_estoura_a_tela(self):
        longas = [(len(f), c, f) for c, f in _frases(CAPTIONS)
                  if len(f) > TETO_CHARS]
        self.assertEqual([], longas)

    def test_frase_da_cta_com_o_pior_nome_ainda_cabe(self):
        longas = []
        for banco in BANCOS_NEUTROS + BANCOS_PEDIDO:
            for frase in CAPTIONS[banco]:
                rendido = (frase.replace("{NOME_PEDIDO}", PIOR_NOME)
                                .replace("{AUTOR}", PIOR_AUTOR))
                if len(rendido) > TETO_CHARS_COM_NOME:
                    longas.append((len(rendido), banco, rendido))
        self.assertEqual([], longas)

    def test_o_pior_nome_e_de_fato_o_maior_que_o_pipeline_deixa_passar(self):
        """Guarda do proprio "pior caso" acima.

        Se PIOR_NOME for menor que o que `pedido_de` deixa chegar a tela, os
        dois testes de largura passam medindo um caso que nao e o pior.
        """
        gigante = pedido_de({"nome_pedido": {"nome": "M" * 200,
                                             "autor": "@" + "J" * 200}})
        self.assertLessEqual(len(gigante["nome"]), len(PIOR_NOME))
        self.assertLessEqual(len(gigante["autor"]), len(PIOR_AUTOR))

    def test_bancos_da_cta_sao_ascii_e_caixa_alta(self):
        problemas = []
        for banco in BANCOS_NEUTROS + BANCOS_PEDIDO:
            for frase in CAPTIONS[banco]:
                if any(ord(c) > 127 for c in frase):
                    problemas.append(("nao-ascii", banco, frase))
                if frase != frase.upper():
                    problemas.append(("caixa-baixa", banco, frase))
        self.assertEqual([], problemas)

    def test_banco_neutro_nao_tem_placeholder(self):
        """Sem nome pedido nao existe valor para substituir.

        Um placeholder aqui iria cru para a tela em TODO video sem pedido.
        """
        sujos = [(banco, frase) for banco in BANCOS_NEUTROS
                 for frase in CAPTIONS[banco] if "{" in frase or "}" in frase]
        self.assertEqual([], sujos)

    def test_banco_de_pedido_so_usa_placeholder_conhecido(self):
        import re
        conhecidos = {"{NOME_PEDIDO}", "{AUTOR}"}
        estranhos = []
        for banco in BANCOS_PEDIDO:
            for frase in CAPTIONS[banco]:
                for marca in re.findall(r"\{[^}]*\}", frase):
                    if marca not in conhecidos:
                        estranhos.append((banco, marca, frase))
        self.assertEqual([], estranhos)


class PedidoDeTests(unittest.TestCase):
    def test_generation_sem_o_campo_nao_credita_ninguem(self):
        self.assertEqual({"nome": "", "autor": ""}, pedido_de({}))

    def test_campo_como_string_simples(self):
        self.assertEqual({"nome": "LYRA", "autor": ""},
                         pedido_de({"nome_pedido": "Lyra"}))

    def test_campo_como_dict_com_nome_e_autor(self):
        pedido = pedido_de({"nome_pedido": {"nome": "Kaelen",
                                            "autor": "joaozinho"}})
        self.assertEqual({"nome": "KAELEN", "autor": "JOAOZINHO"}, pedido)

    def test_acento_sai_e_caixa_sobe(self):
        # O console e cp1252: acento em texto que vai para frame quebra a saida.
        pedido = pedido_de({"nome_pedido": "  Nicol\u00e1s \u00c7\u00e3o  "})
        self.assertEqual("NICOLAS CAO", pedido["nome"])

    def test_nome_longo_e_cortado_no_limite(self):
        pedido = pedido_de({"nome_pedido": "A" * 60})
        self.assertEqual(cg.LIMITE_NOME, len(pedido["nome"]))

    def test_chaves_no_nome_sao_removidas(self):
        """Sem isso um nome com chave derrubaria a rede de seguranca."""
        pedido = pedido_de({"nome_pedido": "{AUTOR}"})
        self.assertNotIn("{", pedido["nome"])
        self.assertNotIn("}", pedido["nome"])

    def test_origem_que_nao_e_comentario_nao_credita(self):
        pedido = pedido_de({"nome_pedido": {"nome": "Lyra",
                                            "origem": "aleatorio"}})
        self.assertEqual({"nome": "", "autor": ""}, pedido)

    def test_origem_de_comentario_credita(self):
        pedido = pedido_de({"nome_pedido": {"nome": "Lyra",
                                            "origem": "comentario"}})
        self.assertEqual("LYRA", pedido["nome"])

    def test_lixo_no_campo_nao_explode(self):
        for lixo in (0, [], 12, ["Lyra"], {"origem": "comentario"},
                     {"nome": ""}, {"nome": 42}, None, True):
            with self.subTest(lixo=lixo):
                self.assertEqual({"nome": "", "autor": ""},
                                 pedido_de({"nome_pedido": lixo}))


class HookEOutroTests(unittest.TestCase):
    def test_sem_pedido_usa_o_banco_de_convite(self):
        gerador = _gerador()
        for semente in range(40):
            rng = random.Random(semente)
            self.assertIn(gerador.hook(rng), CAPTIONS["hook"])
            self.assertIn(gerador.outro(rng), CAPTIONS["outro"])

    def test_sem_pedido_e_igual_a_nao_passar_pedido(self):
        """Geracao antiga (sem o campo) nao pode mudar de comportamento."""
        gerador = _gerador()
        vazio = {"nome": "", "autor": ""}
        self.assertEqual(gerador.hook(random.Random(7)),
                         gerador.hook(random.Random(7), vazio))
        self.assertEqual(gerador.outro(random.Random(7)),
                         gerador.outro(random.Random(7), vazio))

    def test_com_nome_o_outro_muda_de_banco(self):
        gerador = _gerador()
        pedido = {"nome": PIOR_NOME, "autor": ""}
        vistos = {gerador.outro(random.Random(s), pedido) for s in range(60)}
        self.assertTrue(vistos)
        for frase in vistos:
            self.assertNotIn(frase, CAPTIONS["outro"])

    def test_com_autor_credita_quem_pediu(self):
        gerador = _gerador()
        pedido = {"nome": "LYRA", "autor": PIOR_AUTOR}
        vistos = {gerador.outro(random.Random(s), pedido) for s in range(60)}
        for frase in vistos:
            self.assertIn(PIOR_AUTOR, frase)

    def test_sem_autor_nunca_cai_no_banco_que_credita_autor(self):
        gerador = _gerador()
        pedido = {"nome": "LYRA", "autor": ""}
        cru = set(CAPTIONS["outro_pedido_autor"])
        for semente in range(60):
            frase = gerador.outro(random.Random(semente), pedido)
            self.assertNotIn(frase, cru)
            self.assertNotIn("{", frase)

    def test_hook_com_nome_anuncia_o_pedido(self):
        gerador = _gerador()
        pedido = {"nome": "KAELEN", "autor": ""}
        vistos = {gerador.hook(random.Random(s), pedido) for s in range(60)}
        for frase in vistos:
            self.assertNotIn(frase, CAPTIONS["hook"])
            self.assertNotIn("{", frase)
        self.assertTrue(any("KAELEN" in f for f in vistos))


class PlaceholderNuncaVazaTests(unittest.TestCase):
    def test_toda_frase_de_todo_banco_pedido_sai_preenchida(self):
        """Varredura exaustiva: cada posicao de cada banco, um por um."""
        gerador = _gerador()
        pedido = {"nome": PIOR_NOME, "autor": PIOR_AUTOR}
        maior = max(len(CAPTIONS[b]) for b in BANCOS_PEDIDO)
        for indice in range(maior):
            rng = RngFixo(indice)
            for frase in (gerador.hook(rng, pedido),
                          gerador.outro(rng, pedido),
                          gerador.outro(rng, {"nome": PIOR_NOME, "autor": ""}),
                          gerador.for_identity(rng, {"nome": "X"}, pedido),
                          gerador.nameplate_pedido(rng)):
                with self.subTest(indice=indice, frase=frase):
                    self.assertNotIn("{", frase)
                    self.assertNotIn("}", frase)

    def test_banco_pedido_com_placeholder_desconhecido_cai_no_neutro(self):
        """A rede de seguranca do _pick_pedido, sem a qual a chave vai a tela."""
        gerador = _gerador()
        gerador.config["outro_pedido"] = ["OLHA O {CLASSE} DE {NOME_PEDIDO}"]
        pedido = {"nome": "LYRA", "autor": ""}
        for semente in range(30):
            frase = gerador.outro(random.Random(semente), pedido)
            self.assertIn(frase, CAPTIONS["outro"])

    def test_banco_pedido_vazio_cai_no_neutro(self):
        gerador = _gerador()
        gerador.config["hook_pedido"] = []
        frase = gerador.hook(random.Random(3), {"nome": "LYRA", "autor": ""})
        self.assertIn(frase, CAPTIONS["hook"])

    def test_banco_pedido_ausente_cai_no_neutro(self):
        gerador = _gerador()
        del gerador.config["outro_pedido"]
        frase = gerador.outro(random.Random(3), {"nome": "LYRA", "autor": ""})
        self.assertIn(frase, CAPTIONS["outro"])


def _plano(generation: dict) -> dict:
    builder = TimelineBuilder(EDICAO, _gerador(),
                              AssetSelector(AssetCatalog(ROOT / "assets")))
    rng = RandomEngine(generation["seed"]).fork("editing")
    return builder.build(rng, generation, None)


def _evento(plano: dict, tipo: str) -> dict:
    return next(e for e in plano["events"] if e["type"] == tipo)


class PlanoCompletoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = SessionGenerator().generate(
            seed=847293847, generation_id="generation_cta")

    def _com_pedido(self, pedido) -> dict:
        copia = json.loads(json.dumps(self.base))
        copia["nome_pedido"] = pedido
        return copia

    def test_plano_sem_pedido_nao_fala_em_seed(self):
        plano = _plano(self.base)
        for evento in plano["events"]:
            texto = str(evento.get("caption", "")) + str(evento.get("nameplate", ""))
            self.assertNotIn("SEED", texto.upper())

    def test_plano_sem_pedido_usa_o_banco_de_convite(self):
        plano = _plano(self.base)
        self.assertIn(_evento(plano, "outro")["caption"], CAPTIONS["outro"])
        # Revisao 29/08: sem pedido o gancho pode abrir pela imagem do payoff
        # ou pela rolagem absurda (variantes `payoff`/`absurdo`); o cartao de
        # texto continua vindo do banco neutro. O que NUNCA pode acontecer e
        # creditar um comentario que nao existe.
        gancho = _evento(plano, "hook")
        if gancho.get("variante", "texto") == "texto":
            self.assertIn(gancho["caption"], CAPTIONS["hook"])
        else:
            self.assertIn(gancho["variante"], ("payoff", "absurdo"))
        for banco in ("hook_pedido", "outro_pedido", "outro_pedido_autor"):
            for frase in CAPTIONS.get(banco, []):
                self.assertNotEqual(gancho["caption"], frase)

    def test_plano_com_pedido_muda_gancho_e_cta(self):
        plano = _plano(self._com_pedido({"nome": "Kaelen",
                                         "autor": "joaozinho",
                                         "origem": "comentario"}))
        self.assertNotIn(_evento(plano, "outro")["caption"], CAPTIONS["outro"])
        self.assertNotIn(_evento(plano, "hook")["caption"], CAPTIONS["hook"])
        self.assertIn("JOAOZINHO", _evento(plano, "outro")["caption"])
        # Nem toda frase do banco cita o nome ("HOJE O NOME VEIO DE VOCES"),
        # entao o que se cobra e a origem: o gancho saiu do banco de pedido.
        rendido = [f.replace("{NOME_PEDIDO}", "KAELEN")
                   for f in CAPTIONS["hook_pedido"]]
        self.assertIn(_evento(plano, "hook")["caption"], rendido)

    def test_plano_com_pedido_credita_na_placa_do_personagem(self):
        plano = _plano(self._com_pedido("Kaelen"))
        placas = {e["slot"]: e["nameplate"] for e in plano["events"]
                  if e["type"] in ("identity", "nameplate")}
        self.assertIn(placas[identity_slots.CHARACTER]["subtitulo"],
                      CAPTIONS["nameplate_pedido"])
        # arma e payoff continuam mostrando o dado deles
        self.assertNotIn(placas[identity_slots.WEAPON]["subtitulo"],
                         CAPTIONS["nameplate_pedido"])

    def test_plano_sem_pedido_mantem_a_ficha_na_placa(self):
        plano = _plano(self.base)
        placas = {e["slot"]: e["nameplate"] for e in plano["events"]
                  if e["type"] in ("identity", "nameplate")}
        self.assertNotIn(placas[identity_slots.CHARACTER]["subtitulo"],
                         CAPTIONS["nameplate_pedido"])
        self.assertIn(" m", placas[identity_slots.CHARACTER]["subtitulo"])

    def test_campo_do_pedido_ausente_gera_o_plano_de_sempre(self):
        """O outro lado do pipeline pode nunca gravar o campo."""
        sem = _plano(self.base)
        vazio = _plano(self._com_pedido(None))
        self.assertEqual(sem["events"], vazio["events"])

    def test_nenhum_texto_do_plano_com_pedido_tem_placeholder(self):
        plano = _plano(self._com_pedido({"nome": "Nicol\u00e1s \u00c7\u00e3o",
                                         "autor": "maria"}))
        for evento in plano["events"]:
            texto = str(evento.get("caption", "")) + str(evento.get("nameplate", ""))
            self.assertNotIn("{NOME", texto)
            self.assertNotIn("{AUTOR", texto)


if __name__ == "__main__":
    unittest.main()
