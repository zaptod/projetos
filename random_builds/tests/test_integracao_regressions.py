# -*- coding: utf-8 -*-
# Codigo e comentarios em ASCII; valores de catalogo mantem acento.
"""As COSTURAS entre as frentes - o que nenhum dono unico cobria.

Cada frente foi construida e atacada isolada, e cada uma passou sozinha. O que
ninguem testava e o ponto onde uma entrega o dado e a outra consome:

1. NOME PEDIDO: nasce em src/character/nomes, e gravado por SessionGenerator,
   atravessa PipelineController e e lido por caption_generator.pedido_de e
   pelo timeline_builder. Um teto de tamanho diferente em qualquer ponto do
   caminho fazia o segundo 1 do video dizer "CRIANDO BARTOLOMEU AGU" e o
   segundo 20 mostrar "BARTOLOMEU AGUIAR NETO".
2. TRADUCAO x COBERTURA: quem preenche config/identity.json e a frente de
   prompt; quem cobra a falta e o relatorio da frente de roletas. Se os dois
   nao apontarem para a MESMA chave, o relatorio diz OK sobre prompt quebrado.
3. ESTILO: a roleta escolhe, gerar_arma monta o registro e o prompt descreve.
   Os tres tem que dizer a mesma palavra, inclusive quando o banco cresce.

Rode de dentro de random_builds/:
    python -m pytest tests/test_integracao_regressions.py -q
"""
from __future__ import annotations

import copy
import json
import random
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

from builds.assets.catalog import AssetCatalog                            # noqa: E402
from builds.assets.selector import AssetSelector                          # noqa: E402
from builds.character import nomes                                        # noqa: E402
from builds.content import caption_generator as cg                        # noqa: E402
from builds.content.caption_generator import CaptionGenerator, pedido_de  # noqa: E402
from builds.editing.timeline_builder import TimelineBuilder               # noqa: E402
from builds.generation.random_engine import RandomEngine                  # noqa: E402
from builds.generation.session_generator import (SessionGenerator,        # noqa: E402
                                              load_config)
from builds.identity import prompt as P                                   # noqa: E402
from builds.nf_bridge import cobertura as cob                             # noqa: E402
from builds.nf_bridge import exporter                                     # noqa: E402
from builds.nf_bridge import loader as nf                                 # noqa: E402
from builds.nf_bridge import roulette_factory as rf                       # noqa: E402
from builds.pipeline.controller import PipelineController                 # noqa: E402

SEED = 4242
# Escapado de proposito: o fonte deste projeto e ASCII puro (console cp1252).
CIRILICO = "\u041a\u0438\u0440\u0438\u043b\u043b"


def _sessao():
    return SessionGenerator()


def _plano(generation):
    captions = CaptionGenerator(load_config("captions.json"),
                                load_config("frases.json"))
    selector = AssetSelector(AssetCatalog(ROOT / "assets"))
    builder = TimelineBuilder(load_config("editing.json"), captions, selector)
    engine = RandomEngine(generation["seed"])
    return builder.build(engine.fork("editing"), generation, ROOT / "outputs")


def _placa_do_personagem(plano):
    """A primeira placa do plano e a do personagem (ordem: personagem, arma,
    personagem+arma). O evento nao carrega o slot, entao a ordem e o que ha."""
    for evento in plano["events"]:
        if evento.get("nameplate"):
            return evento["nameplate"]
    return {}


def _textos_desenhaveis(plano):
    """Tudo que o renderer desenha: legenda do evento e as 2 linhas da placa."""
    textos = []
    for evento in plano["events"]:
        if evento.get("caption"):
            textos.append(evento["caption"])
        placa = evento.get("nameplate") or {}
        textos.extend(str(v) for v in placa.values() if v)
    return textos


class CosturaDoNomePedido(unittest.TestCase):
    """nomes -> SessionGenerator -> caption_generator -> timeline_builder."""

    @classmethod
    def setUpClass(cls):
        cls.sessao = _sessao()

    def test_o_teto_do_nome_e_UM_SO_no_caminho_inteiro(self):
        """Dois tetos = dois nomes diferentes no mesmo video.

        Era o defeito real: nomes aceitava 28 chars e a legenda cortava em 14,
        entao a legenda e a placa do MESMO video mostravam nomes diferentes.
        """
        self.assertEqual(nomes.MAX_CHARS_PEDIDO, cg.LIMITE_NOME)

    def test_a_legenda_e_a_placa_mostram_o_MESMO_nome(self):
        geracao = self.sessao.generate(seed=SEED, generation_id="costura_01",
                                       nome_pedido="Bartolomeu Aguiar Neto",
                                       autor_pedido="@zeca")
        placa = _placa_do_personagem(_plano(geracao))
        self.assertEqual("Bartolomeu Aguiar Neto", geracao["character"]["nome"])
        self.assertEqual("BARTOLOMEU AGUIAR NETO", placa["titulo"])
        self.assertEqual("BARTOLOMEU AGUIAR NETO", pedido_de(geracao)["nome"])
        # a placa do personagem troca a ficha pelo credito quando ha pedido
        self.assertIn(placa["subtitulo"],
                      load_config("captions.json")["nameplate_pedido"])

    def test_nenhum_texto_mostra_o_nome_cortado_no_meio(self):
        geracao = self.sessao.generate(seed=SEED, generation_id="costura_01b",
                                       nome_pedido="Bartolomeu Aguiar Neto",
                                       autor_pedido="@mariafernandadasilva")
        for texto in _textos_desenhaveis(_plano(geracao)):
            for pedaco in ("BARTOLOMEU AGU ", "BARTOLOMEU AGU."):
                self.assertNotIn(pedaco, texto + " ")

    def test_o_formato_gravado_e_exatamente_o_que_a_CTA_le(self):
        """O contrato entre as duas frentes, cobrado nos dois sentidos."""
        geracao = self.sessao.generate(seed=SEED, generation_id="costura_02",
                                       nome_pedido="Kaelen",
                                       autor_pedido="joaozinho")
        self.assertEqual({"nome": "Kaelen", "autor": "joaozinho",
                          "origem": "comentario"},
                         geracao["nome_pedido"])
        self.assertEqual({"nome": "KAELEN", "autor": "JOAOZINHO"},
                         pedido_de(geracao))

    def test_pedido_recusado_nao_credita_ninguem(self):
        """Cirilico entra pelo comentario e nao chega a tela em lugar nenhum.

        Antes o pipeline ACEITAVA (a placa mostrava o nome, em quadradinho no
        caso do CJK) e a legenda o descartava: o video exibia o nome do
        comentarista e ao mesmo tempo pedia "SEU NOME NOS COMENTARIOS".
        """
        geracao = self.sessao.generate(seed=SEED, generation_id="costura_03",
                                       nome_pedido=CIRILICO,
                                       autor_pedido="@vasya")
        self.assertNotIn("nome_pedido", geracao)
        self.assertEqual("generated", geracao["naming"]["character_name_origin"])
        self.assertEqual("fora do alfabeto latino",
                         geracao["naming"]["requested_name_reason"])
        # Acento de valor de catalogo ("Tatico") e esperado e legitimo; o que
        # nao pode aparecer e o nome recusado.
        for texto in _textos_desenhaveis(_plano(geracao)):
            self.assertNotIn(CIRILICO, texto)
            for letra in CIRILICO:
                self.assertNotIn(letra, texto)

    def test_o_pedido_nao_muda_a_build(self):
        """Mesma seed, com e sem pedido: mesma arma, mesmas rolagens."""
        sem = self.sessao.generate(seed=SEED, generation_id="costura_04")
        com = self.sessao.generate(seed=SEED, generation_id="costura_04",
                                   nome_pedido="Kaelen")
        self.assertEqual(sem["weapon"], com["weapon"])
        self.assertEqual(sem["rolls"], com["rolls"])
        self.assertEqual(sem["final_score"], com["final_score"])
        self.assertEqual(sem["character"]["nome"],
                         com["naming"]["generated_character_name"])

    def test_o_controller_repassa_o_pedido(self):
        """O salto que faltava: main.py -> controller -> session.

        Sem ele o argumento do CLI existia e nao chegava a lugar nenhum.
        """
        visto = {}

        class FalsaSessao:
            def generate(self, **kwargs):
                visto.update(kwargs)
                raise RuntimeError("parar aqui: so interessa o que chegou")

        controller = PipelineController()
        controller.session = FalsaSessao()
        with self.assertRaises(RuntimeError):
            controller.generate(seed=1, generation_only=True,
                                nome_pedido="Kaelen", autor_pedido="@zeca")
        self.assertEqual("Kaelen", visto["nome_pedido"])
        self.assertEqual("@zeca", visto["autor_pedido"])


class CosturaEstreiaMelhorDeTests(unittest.TestCase):
    """A estreia pede a SERIE, registra todo round e resume o placar.

    Sem esta costura o `estreia_melhor_de` do editing.json existiria e nao
    chegaria ao `FightSession` — e o cartel contaria uma luta so.
    """

    def _rodar(self, vencedores: tuple[str, ...]) -> dict:
        from builds.pipeline import controller as mod

        pedido = {}
        registrados = []

        class FalsaSessao:
            def __init__(self, *a, **k):
                pass

            def gerar(self, **kwargs):
                pedido.update(kwargs)
                melhor_de = kwargs["melhor_de"]
                placar = {"Novo": 0, "Rival": 0}
                rounds = []
                for indice, vencedor in enumerate(vencedores[:melhor_de]):
                    placar[vencedor] += 1
                    rounds.append({
                        "match_id": indice, "round": indice + 1,
                        "vencedor": vencedor, "seed": 100 + indice,
                        "ko_type": "KO", "duracao": 20.0, "hp_vencedor": 40,
                        "marcas": [], "tier": "GOOD", "p1": "Novo",
                        "p2": "Rival", "placar": [placar["Novo"], placar["Rival"]]})
                    if placar[vencedor] >= melhor_de // 2 + 1:
                        break
                campeao = max(placar, key=placar.get)
                return {"seed": 1, "melhor_de": melhor_de, "lutas": rounds,
                        "luta": rounds[-1], "vencedor": campeao,
                        "placar": [placar["Novo"], placar["Rival"]],
                        "cenario": "Dojo"}

        class FalsoLedger:
            def registrar(self, luta, **kwargs):
                registrados.append(luta["match_id"])

            def cartel(self, nome):
                return "1V-0D"

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        controller = PipelineController()
        with mock.patch.object(mod, "FightSession", FalsaSessao, create=True), \
                mock.patch.object(mod.PipelineController, "_entregar_luta",
                                  lambda *a, **k: None), \
                mock.patch("builds.arena.ledger.Ledger", lambda *a, **k: FalsoLedger()), \
                mock.patch("builds.arena.ledger.escolher_adversario",
                           lambda *a, **k: "Rival"), \
                mock.patch("builds.tournament.runner.FightSession", FalsaSessao), \
                mock.patch("builds.tournament.runner.fichas_do_banco",
                           lambda: {"Novo": {}, "Rival": {}}), \
                mock.patch("builds.tournament.runner.personagens_gerados",
                           lambda: ["Novo", "Rival"]):
            pasta = controller._gravar_estreia(
                tmp, {"seed": 5, "generation_id": "generation_09999"},
                "Novo", preview=True)
        self.assertIsNotNone(pasta, "a estreia nao foi gravada")
        with open(tmp / "estreia.json", encoding="utf-8") as fh:
            resumo = json.load(fh)
        return {"pedido": pedido, "registrados": registrados, "resumo": resumo}

    def test_o_formato_do_config_chega_a_sessao_de_luta(self):
        saida = self._rodar(("Novo", "Rival", "Novo"))
        self.assertEqual(3, saida["pedido"]["melhor_de"])
        self.assertEqual("estreia", saida["pedido"]["origem"])

    def test_cada_round_vira_uma_linha_no_ledger(self):
        saida = self._rodar(("Novo", "Rival", "Novo"))
        self.assertEqual([0, 1, 2], saida["registrados"])

    def test_o_resumo_guarda_placar_e_rounds(self):
        resumo = self._rodar(("Novo", "Rival", "Novo"))["resumo"]
        self.assertEqual([2, 1], resumo["placar"])
        self.assertEqual(3, resumo["melhor_de"])
        self.assertEqual("Novo", resumo["vencedor"])
        self.assertEqual([1, 2, 3], [r["round"] for r in resumo["rounds"]])

    def test_serie_varrida_nao_grava_o_terceiro_round(self):
        saida = self._rodar(("Novo", "Novo", "Novo"))
        self.assertEqual([0, 1], saida["registrados"])
        self.assertEqual([2, 0], saida["resumo"]["placar"])


class CosturaTraducaoCobertura(unittest.TestCase):
    """Quem preenche identity.json e quem cobra a falta apontam para a mesma
    chave? Se nao, o relatorio diz OK sobre um prompt quebrado."""

    @classmethod
    def setUpClass(cls):
        cls.ajustes = P.config.settings()
        cls.geracao = _sessao().generate(seed=SEED, generation_id="costura_tr")

    def _cobertura_com(self, identity):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        for nome in ("scoring.json", "captions.json", "editing.json"):
            shutil.copy(ROOT / "config" / nome, tmp / nome)
        with open(tmp / "identity.json", "w", encoding="utf-8") as fh:
            json.dump(identity, fh, ensure_ascii=False)
        return cob.cobertura(config_dir=tmp)

    def _grupo(self, dados, gid):
        return next(g for g in dados["grupos"] if g["id"] == gid)

    def test_o_banco_vivo_nao_tem_traducao_de_prompt_pendente(self):
        dados = cob.cobertura()
        for gid in ("traducoes.classe", "traducoes.personalidade",
                    "traducoes.tipo_arma", "traducoes.raridade",
                    "traducoes.estilo", "traducoes.elemento",
                    "traducoes.habilidade", "traducoes.encantamento", "aura"):
            grupo = self._grupo(dados, gid)
            self.assertEqual(
                [], grupo["faltando"],
                gid + ": " + str([f["onde"] for f in grupo["faltando"]]))

    def test_apagar_a_traducao_que_ESTA_geracao_usa_e_acusado_por_nome(self):
        """O caminho impresso e copiavel: some a chave que o prompt usaria."""
        raridade = self.geracao["weapon"]["raridade"]
        mutante = copy.deepcopy(self.ajustes)
        del mutante["traducoes"]["raridade"][raridade]
        grupo = self._grupo(self._cobertura_com(mutante), "traducoes.raridade")
        esperado = 'config/identity.json -> traducoes.raridade["%s"]' % raridade
        self.assertEqual([esperado], [f["onde"] for f in grupo["faltando"]])

    def test_traducao_VAZIA_tambem_e_acusada(self):
        """Chave presente e valor vazio cala o aviso e quebra o prompt igual.

        Com o valor vazio o prompt perde o rotulo e erra o artigo ("an
        -grade"), e o relatorio antigo dizia OK porque so olhava a chave.
        """
        raridade = self.geracao["weapon"]["raridade"]
        mutante = copy.deepcopy(self.ajustes)
        mutante["traducoes"]["raridade"][raridade] = ""
        grupo = self._grupo(self._cobertura_com(mutante), "traducoes.raridade")
        self.assertEqual([raridade], [f["nome"] for f in grupo["faltando"]])
        self.assertNotEqual(
            P.build_prompt(self.geracao, self.ajustes, "weapon", tipo="video"),
            P.build_prompt(self.geracao, mutante, "weapon", tipo="video"))

    def test_toda_habilidade_sorteavel_tem_traducao_usada_no_prompt(self):
        """A roleta de HABILIDADE e o dicionario do prompt olham a mesma lista."""
        traduzidas = set(self.ajustes["traducoes"]["habilidade"])
        na_roleta = set(o["value"] for o in rf.skill_options())
        self.assertEqual(set(), na_roleta - traduzidas)


class CosturaDoEstilo(unittest.TestCase):
    """Roleta, registro do jogo e prompt tem que dizer a MESMA palavra."""

    def setUp(self):
        self.tipos = list(nf.LISTA_TIPOS_ARMA)
        self.dupla = list(nf.ESTILOS_ARMA["Dupla"]["variantes"])
        self.ajustes = P.config.settings()

    def tearDown(self):
        nf.LISTA_TIPOS_ARMA[:] = self.tipos
        nf.ESTILOS_ARMA["Dupla"]["variantes"][:] = self.dupla

    def _registro(self, tipo, estilo):
        opcao = dict((o["value"], o) for o in rf.estilo_options())[estilo]
        arma_rolada = {
            "tipo": tipo, "raridade": "Raro", "estilo": estilo,
            "estilo_meta": dict((k, v) for k, v in opcao.items()
                                if k != "weight"),
            "encantamento": "Chamas", "habilidade": None, "dano": 12.0,
            "peso_x10": 30, "critico_x10": 40, "velocidade_x100": 100,
        }
        personagem_rolado = {
            "classe": nf.LISTA_CLASSES[0],
            "personalidade": nf.lista_personalidades()[0],
            "tamanho_cm": 175, "forca_x10": 50, "mana_x10": 50,
        }
        arma, _, _ = exporter.build_records(personagem_rolado, arma_rolada,
                                            random.Random(7))
        return arma

    def test_estilo_do_banco_de_hoje_bate(self):
        for tipo in nf.LISTA_TIPOS_ARMA:
            for variante in nf.variantes_do_tipo(tipo):
                self.assertEqual(
                    variante["nome"],
                    self._registro(tipo, variante["nome"])["estilo"])

    def test_tipo_NOVO_sem_catalogo_nao_vira_Espada_Longa(self):
        """gerar_arma cai em ESTILOS_ARMA["Reta"] para tipo desconhecido.

        Sem o conserto no exporter, a roleta mostrava "Escudo" e o registro, o
        prompt e a placa diziam "Espada Longa" - o pedido 2 quebrava calado
        justamente no caso que ele existe para atender.
        """
        nf.LISTA_TIPOS_ARMA.append("Escudo")
        self.assertEqual("Escudo", self._registro("Escudo", "Escudo")["estilo"])

    def test_mesmo_nome_de_estilo_em_dois_tipos_nao_troca_a_variante(self):
        """estilo_options() funde os dois numa opcao so e o indice e do
        PRIMEIRO tipo; sorteando o segundo, gerar_arma recebia o indice do
        catalogo errado e gravava outro estilo."""
        nf.ESTILOS_ARMA["Dupla"]["variantes"].append({"nome": "Machado",
                                                      "peso": (2, 3)})
        self.assertEqual("Machado", self._registro("Dupla", "Machado")["estilo"])
        self.assertEqual("Machado", self._registro("Reta", "Machado")["estilo"])

    def test_o_prompt_descreve_o_estilo_que_a_roleta_mostrou(self):
        geracao = _sessao().generate(seed=SEED, generation_id="costura_est")
        estilo = geracao["weapon"]["estilo"]
        rolado = next(r["value"] for r in geracao["rolls"]
                      if r["roulette_id"] == "estilo")
        self.assertEqual(rolado, estilo)
        self.assertIn(self.ajustes["traducoes"]["estilo"][estilo],
                      P.build_prompt(geracao, self.ajustes, "weapon",
                                     tipo="video"))


class CosturaDaCTA(unittest.TestCase):
    def test_nenhum_texto_desenhavel_fala_em_seed(self):
        """Pedido 1, cobrado no plano montado e nao no banco de frases."""
        for pedido in (None, "Kaelen"):
            geracao = _sessao().generate(seed=SEED,
                                         generation_id="costura_cta",
                                         nome_pedido=pedido)
            for texto in _textos_desenhaveis(_plano(geracao)):
                self.assertNotIn("seed", texto.lower(), texto)


if __name__ == "__main__":
    unittest.main()
