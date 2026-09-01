"""Contratos da edicao em ritmo de TikTok que nao podem regredir.

O que este arquivo trava:

1. A CLASSE EDITORIAL de uma rolagem sai dos dados (score, raridade, surpresa,
   metodo de avaliacao) e a precedencia e narrativa: contradicao ganha de
   extremo, extremo ganha de raro.
2. Reacao NAO sai depois de toda roleta: teto por video, distancia minima e
   nunca duas seguidas. Sem isso ela vira formato e para de ter graca.
3. Nenhuma cena parada passa de 2 s. E a regra de retencao da secao 20 em
   forma de teste: se por varios segundos nada novo aparece, a cena e longa
   demais.
4. Os tres prompts sao independentes e completos: o do personagem nao entrega
   a arma, o da arma nao entrega o personagem, e o do payoff carrega as duas
   identidades inteiras (secao 16).
5. `evaluation.json` casa cada reacao com a rolagem certa - `index` reinicia
   na primeira rolagem da arma, entao ele sozinho nao serve de chave.

Rode de dentro de random_builds/:
    python -m unittest discover -s tests -p "test_*.py"
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from builds.assets.catalog import CATEGORIES, AssetCatalog                 # noqa: E402
from builds.assets.selector import FALLBACKS, AssetSelector                # noqa: E402
from builds.content.caption_generator import CaptionGenerator              # noqa: E402
from builds.editing import artifacts                                       # noqa: E402
from builds.editing.timeline_builder import TimelineBuilder                # noqa: E402
from builds.evaluation import reaction_classifier as rc                    # noqa: E402
from builds.generation.random_engine import RandomEngine                   # noqa: E402
from builds.generation.session_generator import (SessionGenerator,         # noqa: E402
                                              load_config)
from builds.identity import identity_model, slots                          # noqa: E402
from builds.identity import prompt as identity_prompt                      # noqa: E402

EDICAO = load_config("editing.json")

# Cenas sem movimento proprio: elas so mostram texto. A roleta gira e os
# clipes sao video, entao os dois tem licenca para durar mais.
CENAS_PARADAS = ("hook", "stinger", "nameplate", "synergy", "final", "outro")

# Subiu de 2,0 para 2,5 s depois de ver o video pronto: 2 s nao davam tempo de
# LER. O teto continua existindo porque sem ele a tela parada volta a crescer
# sem limite — o que a secao 20 manda evitar. O que mudou foi o numero, nao a
# regra.
TETO_CENA_PARADA = 2.5


def _gerar(seed: int):
    return SessionGenerator().generate(seed=seed,
                                       generation_id=f"generation_{seed}")


def _plano(generation: dict, out_dir=None) -> dict:
    builder = TimelineBuilder(
        EDICAO,
        CaptionGenerator(load_config("captions.json"), load_config("frases.json")),
        AssetSelector(AssetCatalog(ROOT / "assets")))
    rng = RandomEngine(generation["seed"]).fork("editing")
    return builder.build(rng, generation, out_dir)


def _roll(**campos) -> dict:
    base = {"score": 50, "sentiment": "neutral", "tier": "AVERAGE",
            "rarity": 0.5, "surprise": 10, "roulette_id": "classe",
            "evaluation": {"method": "categorical"}}
    base.update(campos)
    return base


class ClassificacaoTests(unittest.TestCase):
    def test_extremos_da_escala_sao_absurdos(self):
        self.assertEqual(rc.ABSURD, rc.classify(_roll(score=97), EDICAO)["classification"])
        self.assertEqual(rc.ABSURD, rc.classify(_roll(score=2), EDICAO)["classification"])

    def test_absurdo_escolhe_a_reacao_pelo_lado_da_escala(self):
        """97 e 2 sao os dois absurdos - e pedem reacoes opostas."""
        alto = rc.classify(_roll(score=97, sentiment="positive"), EDICAO)
        baixo = rc.classify(_roll(score=2, sentiment="negative"), EDICAO)
        self.assertEqual("insane", alto["reaction_category"])
        self.assertEqual("terrible", baixo["reaction_category"])

    def test_contradicao_ganha_do_extremo(self):
        """Arma que ele nao levanta e piada de contradicao, nao de fraqueza."""
        contraditoria = _roll(score=3, roulette_id="peso", sentiment="negative",
                              evaluation={"method": "contextual",
                                          "context_fn": "peso_vs_forca"})
        self.assertEqual(rc.CONTRADICTORY,
                         rc.classify(contraditoria, EDICAO)["classification"])

    def test_improvavel_e_raro_mesmo_sem_ser_extremo(self):
        raro = _roll(score=55, rarity=0.01)
        self.assertEqual(rc.RARE, rc.classify(raro, EDICAO)["classification"])

    def test_raro_e_ruim_pede_reacao_de_desastre(self):
        """5 de forca com surpresa 90 e raro E desastre. Reage-se ao desastre."""
        linha = rc.classify(_roll(score=5, surprise=95, sentiment="negative"),
                            EDICAO)
        self.assertEqual("terrible", linha["reaction_category"])

    def test_faixa_comica_configurada_vira_funny(self):
        regra = EDICAO["classification"]["funny"]["tamanho"]
        anao = _roll(score=regra["below"] - 1, roulette_id="tamanho")
        self.assertEqual(rc.FUNNY, rc.classify(anao, EDICAO)["classification"])

    def test_toda_classe_aponta_para_categoria_que_existe(self):
        """Categoria fantasma faria o seletor cair no fallback para sempre."""
        for classe in rc.CLASSES:
            destino = rc.CATEGORIA_POR_CLASSE[classe]
            candidatas = ([destino] if isinstance(destino, str)
                          else list(destino.values()))
            for categoria in candidatas:
                self.assertIn(categoria, CATEGORIES, classe)
                self.assertIn(categoria, FALLBACKS, classe)


class RitmoTests(unittest.TestCase):
    """Secoes 9, 10 e 20: o video precisa entregar novidade o tempo todo."""

    SEEDS = (20260822, 7, 999, 123456, 42)

    def test_reacao_nao_sai_depois_de_toda_roleta(self):
        orcamento = EDICAO["reaction_budget"]
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                eventos = _plano(_gerar(seed))["events"]
                tipos = [e["type"] for e in eventos]
                roletas = tipos.count("roulette")
                reacoes = tipos.count("reaction")
                self.assertLessEqual(reacoes, orcamento["max_total"])
                self.assertLess(reacoes, roletas / 2,
                                "reacao em metade das roletas vira formato")

    def test_nunca_duas_reacoes_seguidas(self):
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                tipos = [e["type"] for e in _plano(_gerar(seed))["events"]]
                seguidas = [i for i in range(len(tipos) - 1)
                            if tipos[i] == tipos[i + 1] == "reaction"]
                self.assertEqual([], seguidas)

    def test_reacoes_respeitam_a_distancia_minima(self):
        minimo = EDICAO["reaction_budget"]["min_gap_rolls"]
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                eventos = _plano(_gerar(seed))["events"]
                indices, roletas = [], 0
                for evento in eventos:
                    if evento["type"] == "roulette":
                        roletas += 1
                    elif evento["type"] == "reaction":
                        indices.append(roletas)
                for anterior, seguinte in zip(indices, indices[1:]):
                    self.assertGreater(seguinte - anterior, minimo)

    def test_reacao_cabe_inteira_na_tela_sem_ser_recortada(self):
        """A reacao e video de OUTRO formato (deitado): `fit: contain`.

        Sem isso o renderer cai no crop-para-preencher e come ~62% da largura
        de um 16:9 num quadro 9:16 — some justamente o rosto, que e o que a
        reacao tem para mostrar.
        """
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                for evento in _plano(_gerar(seed))["events"]:
                    if evento["type"] == "reaction":
                        self.assertEqual("contain", evento.get("fit"))

    def test_reacao_toca_ate_o_fim_dentro_do_orcamento(self):
        """O clipe toca INTEIRO ate o teto; quem segura o video e o orcamento.

        O teto de 2 s cortava 96% da biblioteca (mediana 6,5 s) e a piada
        morria antes do punchline. As duas garantias que substituem o corte:
        nenhuma reacao entra como flash, e a soma delas respeita o orcamento
        do video.
        """
        orcamento = EDICAO["reaction_budget"]
        teto_clipe = EDICAO["durations"]["reaction_max"]
        util = orcamento["min_util_segundos"]
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                reacoes = [e for e in _plano(_gerar(seed))["events"]
                           if e["type"] == "reaction"]
                soma = 0.0
                for evento in reacoes:
                    duracao = evento["duration"]
                    soma += duracao
                    if (evento.get("asset") or {}).get("synthetic", True):
                        continue  # cartão desenhado tem duração própria
                    self.assertGreaterEqual(duracao, util,
                                            "reacao virou flash")
                    self.assertLessEqual(duracao, teto_clipe + 0.01)
                    clipe = float((evento.get("asset") or {}).get("duration") or 0)
                    if clipe and clipe + 0.05 <= teto_clipe:
                        # Coube no teto: tem que ter tocado INTEIRO.
                        self.assertGreaterEqual(duracao, min(clipe, teto_clipe))
                self.assertLessEqual(soma, orcamento["max_segundos"] + 0.01)

    def test_nenhuma_cena_parada_passa_de_dois_segundos(self):
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                for evento in _plano(_gerar(seed))["events"]:
                    if evento["type"] in CENAS_PARADAS:
                        self.assertLessEqual(evento["duration"], TETO_CENA_PARADA,
                                             f"{evento['type']} em {seed}")

    def test_o_gancho_entra_e_sai(self):
        """Secao 8: no maximo ~2 s antes da primeira roleta."""
        eventos = _plano(_gerar(self.SEEDS[0]))["events"]
        self.assertEqual("hook", eventos[0]["type"])
        self.assertLessEqual(eventos[0]["duration"], 2.0)
        self.assertEqual("roulette", eventos[1]["type"])

    def test_o_video_cabe_num_tiktok(self):
        """Com os tres clipes o total fica na faixa de um video vertical."""
        janelas = EDICAO["identity_slots"]
        extra = sum(j["max"] for j in janelas.values())
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                total = _plano(_gerar(seed))["total_duration"]
                # o plano sem clipe ja tem 3 nameplates no lugar deles
                cheio = total + extra - 3 * EDICAO["durations"]["nameplate"]
                # Teto subiu de 75 para 95 s quando a roleta foi alongada de
                # proposito (giro de 1,8 s, resultado de 1,5 s) para dar tempo
                # de LER. O teto segue existindo para pegar crescimento
                # acidental — 14 rolagens que dobrassem de duracao passariam
                # dele e apareceriam aqui.
                self.assertLess(cheio, 95, "video longo demais para o formato")
                self.assertGreater(cheio, 30, "video curto demais para a build")

    def test_metade_do_video_e_roleta(self):
        """Secao 1: a roleta e o elemento dominante, nao as telas de apoio."""
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                plano = _plano(_gerar(seed))
                girando = sum(e["duration"] for e in plano["events"]
                              if e["type"] == "roulette")
                self.assertGreater(girando, plano["total_duration"] * 0.5)


class PromptSlotTests(unittest.TestCase):
    """Secoes 4, 6, 7 e 16: tres prompts, uma identidade so."""

    @classmethod
    def setUpClass(cls):
        cls.generation = _gerar(20260822)
        cls.prompts = identity_prompt.build_prompts(cls.generation)
        cls.ajustes = identity_prompt.config.settings()
        cls.valores = identity_prompt.campos(cls.generation, cls.ajustes)

    def test_existe_um_prompt_por_job(self):
        """Inclui a juncao, que e trabalho sem ser cena."""
        self.assertEqual(sorted(slots.JOBS), sorted(self.prompts))
        for slot, texto in self.prompts.items():
            self.assertTrue(texto.strip(), slot)
            self.assertEqual([], identity_prompt.PLACEHOLDER.findall(texto), slot)

    def test_o_clipe_do_personagem_nao_entrega_a_arma(self):
        """O payoff e mostrar os dois juntos - a arma nao pode vazar antes."""
        texto = self.prompts[slots.CHARACTER]
        self.assertNotIn(self.valores["ARMA_ESTILO"].lower(), texto.lower())
        self.assertIn("no weapon", texto.lower())

    def test_o_clipe_da_arma_nao_traz_o_personagem(self):
        texto = self.prompts[slots.WEAPON]
        self.assertNotIn(self.valores["NOME"].lower(), texto.lower())
        self.assertNotIn(self.valores["CLASSE"].lower(), texto.lower())
        self.assertIn("no character", texto.lower())

    def test_a_juncao_manda_seguir_as_DUAS_referencias(self):
        """A imagem composta so presta se ela preservar os dois lados."""
        texto = self.prompts[slots.REFERENCIA].lower()
        self.assertIn("reference", texto)
        self.assertIn("holding", texto)
        for exigencia in ("same face", "same shape", "single continuous scene"):
            self.assertIn(exigencia, texto, exigencia)
        # colagem e o modo de falha classico do editor: precisa ser proibida
        for proibido in ("no collage", "no split frame", "no side-by-side"):
            self.assertIn(proibido, texto, proibido)

    def test_o_payoff_carrega_as_duas_identidades_inteiras(self):
        """Gerar o terceiro de um resumo e o que troca o rosto e a lamina."""
        texto = self.prompts[slots.CHARACTER_WEAPON].lower()
        personagem, arma = identity_model.identidades(self.generation,
                                                      self.ajustes)
        for chave in ("NOME", "CLASSE", "PERSONALIDADE", "PORTE", "COR_HEX"):
            self.assertIn(str(personagem[chave]).lower(), texto, chave)
        for chave in ("ARMA_ESTILO", "RARIDADE", "ELEMENTO", "AURA"):
            self.assertIn(str(arma[chave]).lower(), texto, chave)
        self.assertIn("same character", texto)

    def test_a_identidade_cobre_todo_campo_permanente(self):
        personagem, arma = identity_model.identidades(self.generation,
                                                      self.ajustes)
        self.assertEqual(sorted(identity_model.CAMPOS_PERSONAGEM),
                         sorted(personagem))
        self.assertEqual(sorted(identity_model.CAMPOS_ARMA), sorted(arma))
        self.assertTrue(all(str(v).strip() for v in personagem.values()))

    def test_artigo_segue_a_palavra_que_ele_acompanha(self):
        """'an epic-grade' nao pode virar 'a epic-grade' por copiar o do porte."""
        self.assertEqual("an", identity_prompt.artigo("epic"))
        self.assertEqual("a", identity_prompt.artigo("mythic"))
        self.assertEqual(identity_prompt.artigo(self.valores["RARIDADE"]),
                         self.valores["ARTIGO_RARIDADE"])


class ArtefatosTests(unittest.TestCase):
    """Secoes 18 e 19: o que a build entrega alem do mp4."""

    @classmethod
    def setUpClass(cls):
        cls.generation = _gerar(20260822)
        cls.plano = _plano(cls.generation)

    def test_timeline_tem_uma_linha_por_evento(self):
        linhas = artifacts.timeline(self.plano)
        self.assertEqual(len(self.plano["events"]), len(linhas))
        roletas = [ln for ln in linhas if ln["type"] == "roulette"]
        self.assertTrue(roletas)
        for linha in roletas:
            self.assertIn("category", linha)
            self.assertIn("result", linha)
            self.assertIn("classification", linha)

    def test_artefato_vira_evento_do_TIPO_certo_apontando_para_o_arquivo(self):
        """Duas imagens e um video: o timeline.json nao pode chamar tudo de video."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _escrever_artefatos(Path(tmp))
            plano = _plano(self.generation, Path(tmp))
        linhas = [ln for ln in artifacts.timeline(plano)
                  if ln["type"] in ("image", "video")]
        self.assertEqual([slots.ARQUIVO[s] for s in slots.SLOTS],
                         [ln["asset"] for ln in linhas])
        por_slot = {ln["slot"]: ln["type"] for ln in linhas}
        self.assertEqual("image", por_slot[slots.CHARACTER])
        self.assertEqual("image", por_slot[slots.WEAPON])
        self.assertEqual("video", por_slot[slots.CHARACTER_WEAPON])

    def test_srt_e_monotonico_e_bem_formado(self):
        texto = artifacts.srt(self.plano)
        blocos = [b for b in texto.split("\n\n") if b.strip()]
        self.assertTrue(blocos)
        anterior = -1.0
        for indice, bloco in enumerate(blocos, start=1):
            linhas = bloco.splitlines()
            self.assertEqual(str(indice), linhas[0])
            self.assertIn(" --> ", linhas[1])
            inicio = linhas[1].split(" --> ")[0]
            self.assertRegex(inicio, r"^\d{2}:\d{2}:\d{2},\d{3}$")
            h, m, resto = inicio.split(":")
            s, ms = resto.split(",")
            agora = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
            self.assertGreaterEqual(agora, anterior)
            anterior = agora

    def test_evaluation_casa_a_reacao_com_a_rolagem_certa(self):
        """`index` reinicia na arma: sozinho ele daria a reacao a outra roleta."""
        evaluation = artifacts.evaluation(self.generation, self.plano, EDICAO)
        self.assertEqual(len(self.generation["rolls"]), len(evaluation["rolls"]))

        esperado, ultima = {}, None
        for evento in self.plano["events"]:
            if evento["type"] == "roulette":
                ultima = (evento["roll"]["entity"], evento["roll"]["index"])
            elif evento["type"] == "reaction":
                esperado[ultima] = evento.get("category")
        obtido = {(ln["entity"], ln["index"]): ln["reaction"]["category"]
                  for ln in evaluation["rolls"] if ln["reaction"]}
        self.assertEqual(esperado, obtido)
        self.assertEqual(len(esperado), evaluation["reaction_count"])

    def test_posicao_identifica_a_rolagem_sem_ambiguidade(self):
        linhas = rc.classify_all(self.generation["rolls"], EDICAO)
        self.assertEqual(list(range(len(linhas))), [ln["position"] for ln in linhas])


def _escrever_artefatos(pasta: Path) -> None:
    """Um arquivo por slot, com a MIDIA que aquele slot pede.

    PNG de verdade (8x8) e nao b"x": a imagem passa por validacao de magic
    bytes, e um arquivo de mentira seria descartado como download truncado.
    """
    from PIL import Image
    for slot in slots.SLOTS:
        destino = pasta / slots.ARQUIVO[slot]
        if slots.midia(slot) == slots.IMAGEM:
            Image.new("RGB", (8, 8), (30, 20, 60)).save(destino)
        else:
            destino.write_bytes(b"nao e um mp4 valido" * 700)


class _PaginaFake:
    """Pagina de mentira: `evaluate` devolve sempre a mesma lista de cards."""

    def __init__(self, cards):
        self.cards = list(cards)

    def evaluate(self, js, arg=None):
        return list(self.cards)


class EspacoCompartilhadoTests(unittest.TestCase):
    """Os tres clipes no MESMO space: como saber qual card e o nosso."""

    @staticmethod
    def _client(cards):
        from builds.identity.client import DigenClient
        cliente = DigenClient.__new__(DigenClient)
        cliente.page = _PaginaFake(cards)
        return cliente

    def test_espaco_novo_com_um_card_e_o_nosso(self):
        self.assertEqual(0, self._client(["a"])._indice_do_novo([]))

    def test_acha_o_card_novo_no_meio_da_lista(self):
        """A ordem nao importa: o que conta e nao estar na foto de antes."""
        cliente = self._client(["a", "novo", "b"])
        self.assertEqual(1, cliente._indice_do_novo(["a", "b"]))

    def test_sem_card_novo_continua_esperando(self):
        cliente = self._client(["a", "b"])
        self.assertIsNone(cliente._indice_do_novo(["a", "b"]))

    def test_miniaturas_repetidas_nao_escondem_o_card_novo(self):
        """Consumo um a um, nao por conjunto: dois 'a' antes, tres agora."""
        cliente = self._client(["a", "a", "b"])
        self.assertEqual(2, cliente._indice_do_novo(["a", "a"]))

    def test_ambiguidade_persistente_vira_erro_em_vez_de_palpite(self):
        """Dois cards novos para um video pedido: baixar no chute e pior."""
        from builds.identity.client import GeracaoFalhou
        cliente = self._client(["x", "y"])
        self.assertIsNone(cliente._indice_do_novo([]))
        self.assertIsNone(cliente._indice_do_novo([]))
        with self.assertRaises(GeracaoFalhou):
            cliente._indice_do_novo([])

    def test_espaco_so_e_reaproveitado_se_der_para_distinguir(self):
        from builds.identity.client import DigenClient
        self.assertTrue(DigenClient._distinguiveis([]))
        self.assertTrue(DigenClient._distinguiveis(["a", "b"]))
        self.assertFalse(DigenClient._distinguiveis(["a", "a"]))
        self.assertFalse(DigenClient._distinguiveis(["a", ""]))


class PresetsTests(unittest.TestCase):
    """Duracao e resolucao sao pedidas POR SLOT - e conferidas."""

    def setUp(self):
        from builds.identity import config as icfg
        self.ajustes = icfg.settings()

    def test_todo_slot_tem_duracao_declarada(self):
        from builds.identity.worker import preset_do_slot
        for slot in slots.SLOTS:
            self.assertTrue(preset_do_slot(self.ajustes, "duracao", slot), slot)

    def test_duracao_pedida_cabe_na_janela_da_montagem(self):
        """Pedir 15 s para um slot que a edicao corta em 4 e gerar para o lixo."""
        from builds.identity.selectors import valor_numerico
        from builds.identity.worker import preset_do_slot
        janelas = EDICAO["identity_slots"]
        for slot in slots.SLOTS:
            preferencia = preset_do_slot(self.ajustes, "duracao", slot)
            primeiro = (preferencia[0] if isinstance(preferencia, list)
                        else preferencia)
            segundos = valor_numerico(str(primeiro))
            if segundos is None:      # "max": quem decide e o menu do modelo
                continue
            with self.subTest(slot=slot):
                self.assertGreaterEqual(segundos, janelas[slot]["min"])
                # uma opcao de folga acima do teto e aceitavel (a edicao apara)
                self.assertLessEqual(segundos, janelas[slot]["max"] + 3)

    def test_max_vale_em_qualquer_posicao_da_lista(self):
        """'max' no fim da lista era texto de menu que nunca existe."""
        from builds.identity import selectors
        for slot in slots.SLOTS:
            from builds.identity.worker import preset_do_slot
            preferencia = preset_do_slot(self.ajustes, "duracao", slot)
            if isinstance(preferencia, list) and selectors.MAXIMO in preferencia:
                self.assertNotEqual(selectors.MAXIMO, preferencia[-1:][0:1],
                                    "lista so com max nao e lista")

    def test_proporcao_deitada_e_reconhecida(self):
        from builds.identity import selectors
        self.assertTrue(selectors.valor_deitado("16:9"))
        self.assertTrue(selectors.valor_deitado("4:3"))
        self.assertFalse(selectors.valor_deitado("9:16"))
        self.assertFalse(selectors.valor_deitado("Auto"))
        self.assertFalse(selectors.valor_deitado(""))


class _OpcaoFake:
    def __init__(self):
        self.cliques = 0

    def click(self):
        self.cliques += 1


class ConferenciaDePresetTests(unittest.TestCase):
    """Setar o controle nao basta: tem que conferir que ele virou.

    Era o buraco: `_ajustar_modelo` conferia, `duracao` e `resolucao` nao. Um
    clique que o popover engoliu entregava um clipe de 3 s onde se pediu 8, com
    a geracao ja gasta e nada no log dizendo isso.
    """

    def setUp(self):
        import random as _random
        from builds.identity import client as client_mod
        self.mod = client_mod
        self._pausa = client_mod.pausa_humana
        client_mod.pausa_humana = lambda *a, **k: None
        self.rng = _random.Random(1)

    def tearDown(self):
        self.mod.pausa_humana = self._pausa

    def _client(self, leituras):
        cliente = self.mod.DigenClient.__new__(self.mod.DigenClient)
        cliente.rng = self.rng
        cliente.page = _PaginaFake([])
        sequencia = iter(leituras)
        cliente._valor_do_controle = lambda *a, **k: next(sequencia, leituras[-1])
        return cliente

    def test_controle_que_virou_e_aceito(self):
        cliente = self._client(["8s"])
        opcao = _OpcaoFake()
        self.assertEqual("8s", cliente._clicar_e_conferir(
            "duracao", opcao, "8s", [], ()))
        self.assertEqual(1, opcao.cliques)

    def test_controle_que_nao_virou_derruba_a_geracao(self):
        cliente = self._client(["3s", "3s"])
        with self.assertRaises(self.mod.GeracaoFalhou) as ctx:
            cliente._clicar_e_conferir("duracao", _OpcaoFake(), "8s", [], ())
        mensagem = str(ctx.exception)
        self.assertIn("duracao", mensagem)
        self.assertIn("8s", mensagem)
        self.assertIn("3s", mensagem)

    def test_presets_aplicados_ficam_registrados(self):
        """`identity/<slot>.json` guarda o que o Digen mostrava no envio."""
        cliente = self.mod.DigenClient.__new__(self.mod.DigenClient)
        cliente.page = _PaginaFake([])
        cliente.presets_aplicados = {}
        cliente._modelo_atual = lambda: "RM3.5"
        cliente._aspecto_atual = lambda: "9:16"
        cliente._valor_do_controle = lambda *a, **k: "5s"
        aplicados = cliente._conferir_presets()
        self.assertEqual("RM3.5", aplicados["modelo"])
        self.assertEqual("9:16", aplicados["aspecto"])
        self.assertEqual(aplicados, cliente.presets_aplicados)

    def test_proporcao_deitada_aborta_antes_de_gastar_a_geracao(self):
        cliente = self.mod.DigenClient.__new__(self.mod.DigenClient)
        cliente.page = _PaginaFake([])
        cliente.presets_aplicados = {}
        cliente._modelo_atual = lambda: "RM3.5"
        cliente._aspecto_atual = lambda: "16:9"
        cliente._valor_do_controle = lambda *a, **k: "5s"
        with self.assertRaises(self.mod.GeracaoFalhou):
            cliente._conferir_presets()
