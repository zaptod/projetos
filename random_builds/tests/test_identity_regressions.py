"""Contratos da identidade visual (Digen) que nao podem regredir.

O que este arquivo trava:

1. O prompt sai dos DADOS SORTEADOS, nunca de texto inventado, e nenhum
   placeholder do template escapa para dentro dele.
2. Geracao de esquema antigo falha com mensagem legivel, nao com KeyError cru.
3. A fila sobrevive a processo morto, a arquivo corrompido e a chamada dupla.
4. **Sem o clipe, a timeline sai IDENTICA a de antes.** Este e o contrato mais
   importante: o video da roleta nunca espera o Digen, e ligar a identidade nao
   pode mudar um video que ja estava certo.
5. Com o clipe, o evento nasce entre `final` e `outro` e o renderer o aceita
   como video real (`_asset_de_video`), sem que o renderer precise conhecer o
   tipo `identity`.

Rode de dentro de random_builds/:
    python -m unittest discover -s tests -p "test_*.py"
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from builds.assets.catalog import AssetCatalog                         # noqa: E402
from builds.assets.selector import AssetSelector                       # noqa: E402
from builds.content.caption_generator import CaptionGenerator          # noqa: E402
from builds.editing.timeline_builder import TimelineBuilder            # noqa: E402
from builds.generation.random_engine import RandomEngine               # noqa: E402
from builds.generation.session_generator import SessionGenerator, load_config  # noqa: E402
from builds.identity import prompt as identity_prompt                  # noqa: E402
from builds.identity import slots as identity_slots                    # noqa: E402
from builds.identity import queue as identity_queue                    # noqa: E402
from builds.identity import selectors                                  # noqa: E402
from builds.video.renderer import VideoRenderer                        # noqa: E402

SEED = 20260822


def _gerar(seed: int = SEED) -> dict:
    """Uma geracao real e deterministica, sem tocar no disco."""
    return SessionGenerator().generate(seed=seed, generation_id="generation_99999")


def _timeline() -> TimelineBuilder:
    return TimelineBuilder(
        load_config("editing.json"),
        CaptionGenerator(load_config("captions.json"), load_config("frases.json")),
        AssetSelector(AssetCatalog(ROOT / "assets")))


class PromptTests(unittest.TestCase):
    """O prompt e uma traducao dos dados sorteados, nada mais."""

    @classmethod
    def setUpClass(cls):
        cls.generation = _gerar()
        cls.ajustes = identity_prompt.config.settings()
        cls.texto = identity_prompt.build_prompt(cls.generation)

    def test_cita_os_dados_do_personagem(self):
        personagem = self.generation["character"]
        traducoes = self.ajustes["traducoes"]
        self.assertIn(personagem["nome"], self.texto)
        self.assertIn(traducoes["classe"][personagem["classe"]], self.texto)
        self.assertIn(traducoes["personalidade"][personagem["personalidade"]],
                      self.texto)
        self.assertIn("%.2f" % personagem["tamanho"], self.texto)

    def test_cita_os_dados_da_arma(self):
        arma = self.generation["weapon"]
        traducoes = self.ajustes["traducoes"]
        self.assertIn(traducoes["raridade"][arma["raridade"]], self.texto)
        self.assertIn(traducoes["estilo"][arma["estilo"]], self.texto)

    def test_nenhum_placeholder_escapa(self):
        """Placeholder vazado apareceria literal dentro do prompt do video."""
        self.assertEqual([], identity_prompt.PLACEHOLDER.findall(self.texto))

    def test_todo_encantamento_do_catalogo_tem_elemento_e_aura(self):
        """Encantamento sem aura mapeada geraria prompt com descricao vazia."""
        from builds.nf_bridge.loader import LISTA_ENCANTAMENTOS
        for encantamento in LISTA_ENCANTAMENTOS:
            elemento = identity_prompt.elemento_da_arma(
                {"afinidade_elemento": encantamento})
            self.assertIn(elemento, self.ajustes["aura"], encantamento)
            self.assertIn(elemento, self.ajustes["traducoes"]["elemento"],
                          encantamento)

    def test_toda_categoria_canonica_esta_traduzida(self):
        """Categoria nova no neural_fights sem traducao vazaria portugues."""
        from builds.nf_bridge import loader
        traducoes = self.ajustes["traducoes"]
        for classe in loader.LISTA_CLASSES:
            self.assertIn(classe, traducoes["classe"])
        for personalidade in loader.LISTA_PERSONALIDADES:
            self.assertIn(personalidade, traducoes["personalidade"])
        for tipo in loader.LISTA_TIPOS_ARMA:
            self.assertIn(tipo, traducoes["tipo_arma"])
        for raridade in loader.LISTA_RARIDADES:
            self.assertIn(raridade, traducoes["raridade"])
        for tipo, dados in loader.ESTILOS_ARMA.items():
            for variante in dados["variantes"]:
                self.assertIn(variante["nome"], traducoes["estilo"])

    def test_esquema_antigo_falha_explicando(self):
        antiga = {"generation_id": "generation_00002",
                  "character": {"name": "X", "stats": {}}, "weapon": {}}
        with self.assertRaises(identity_prompt.GeracaoIncompativel) as ctx:
            identity_prompt.build_prompt(antiga)
        self.assertIn("generation_00002", str(ctx.exception))

    def test_cor_dessaturada_nao_vira_matiz_aleatorio(self):
        """Cinza tem matiz instavel: sem o corte de saturacao viraria 'red'."""
        tabela = self.ajustes["cores"]
        self.assertEqual("steel gray",
                         identity_prompt.nome_da_cor(128, 130, 127, tabela))
        self.assertEqual("near-black",
                         identity_prompt.nome_da_cor(5, 5, 5, tabela))
        self.assertEqual("crimson red",
                         identity_prompt.nome_da_cor(220, 20, 20, tabela))


class FilaTests(unittest.TestCase):
    """A fila vive entre processos: precisa aguentar morte e corrupcao."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original = identity_queue.ARQUIVO_FILA
        identity_queue.ARQUIVO_FILA = Path(self._tmp.name) / "queue.json"

    def tearDown(self):
        identity_queue.ARQUIVO_FILA = self._original
        self._tmp.cleanup()

    def test_enqueue_e_idempotente(self):
        identity_queue.enqueue("generation_00001", "prompt A")
        identity_queue.enqueue("generation_00001", "prompt B")
        self.assertEqual(1, len(identity_queue.listar()))

    def test_claim_marca_rodando_para_ninguem_pegar_duas_vezes(self):
        identity_queue.enqueue("generation_00001", "p")
        primeiro = identity_queue.claim()
        self.assertEqual(identity_queue.RODANDO, primeiro["status"])
        self.assertIsNone(identity_queue.claim())

    def test_worker_morto_devolve_o_job(self):
        identity_queue.enqueue("generation_00001", "p")
        identity_queue.claim()
        self.assertEqual(1, identity_queue.reabrir())
        self.assertEqual(identity_queue.PENDENTE,
                         identity_queue.listar()[0]["status"])

    def test_worker_morto_devolve_tambem_a_tentativa(self):
        """Senao o job vira zumbi: `pending` e inclaimavel para sempre.

        `claim` incrementa a tentativa; morrer antes de concluir nao produziu
        nada. Sem devolver, tres mortes levam `attempts` ao teto e `claim`
        nunca mais pega o job — ele fica na fila sem andar e sem falhar, que e
        o pior estado possivel porque nao aparece em lugar nenhum como erro.
        """
        identity_queue.enqueue("generation_00001", "p")
        for _ in range(5):
            self.assertIsNotNone(identity_queue.claim(max_attempts=3),
                                 "job virou zumbi: pending mas inclaimavel")
            identity_queue.reabrir()
        self.assertEqual(0, identity_queue.listar()[0]["attempts"])

    def test_falha_reenfileira_ate_esgotar_tentativas(self):
        identity_queue.enqueue("generation_00001", "p")
        job = None
        for _ in range(3):
            pego = identity_queue.claim()
            job = identity_queue.falhar(pego["job_id"], "boom", max_attempts=3)
        self.assertEqual(identity_queue.FALHOU, job["status"])
        self.assertIsNone(identity_queue.claim(max_attempts=3))

    def test_fila_corrompida_nao_derruba_ninguem(self):
        identity_queue.ARQUIVO_FILA.parent.mkdir(parents=True, exist_ok=True)
        identity_queue.ARQUIVO_FILA.write_text("{lixo", encoding="utf-8")
        self.assertEqual([], identity_queue.listar())
        identity_queue.enqueue("generation_00001", "p")
        self.assertEqual(1, len(identity_queue.listar()))

    def test_espaco_e_guardado_para_retomada(self):
        """Sem `space_url` a retomada mandaria gerar um SEGUNDO video.

        Foi o que aconteceu na rodada de 22/08: a espera estourou em 600 s com
        o video ainda na fila do Digen, e a tentativa seguinte reenviou o
        prompt em vez de voltar a olhar o mesmo espaco.
        """
        job = identity_queue.enqueue("generation_00001", "p")
        self.assertIsNone(identity_queue.listar()[0]["space_url"])
        identity_queue.registrar_espaco(job["job_id"],
                                        "https://digen.ai/en/space/123")
        self.assertEqual("https://digen.ai/en/space/123",
                         identity_queue.listar()[0]["space_url"])

    def test_esquecer_envio_libera_para_gerar_de_novo(self):
        """Falha real do render: retomar aquele video esperaria para sempre.

        O ESPACO continua gravado de proposito: ele e da build, nao daquela
        tentativa, e os outros dois clipes ainda vao nascer dentro dele.
        """
        job = identity_queue.enqueue("generation_00001", "p")
        identity_queue.registrar_envio(job["job_id"], "https://x/space/1", ["a"])
        self.assertTrue(identity_queue.listar()[0]["enviado"])
        identity_queue.esquecer_envio(job["job_id"])
        atual = identity_queue.listar()[0]
        self.assertFalse(atual["enviado"])
        self.assertIsNone(atual["videos_antes"])
        self.assertEqual("https://x/space/1", atual["space_url"])

    def test_os_tres_slots_compartilham_o_espaco_da_build(self):
        """Secao 16: personagem, arma e os dois juntos no MESMO space."""
        for slot in identity_slots.SLOTS:
            identity_queue.enqueue("generation_00001", "p", slot=slot)
        identity_queue.enqueue("generation_00002", "p")
        self.assertIsNone(identity_queue.espaco_da_geracao("generation_00001"))

        primeiro = identity_slots.job_id("generation_00001",
                                         identity_slots.CHARACTER)
        identity_queue.registrar_envio(primeiro, "https://digen.ai/en/space/7", [])
        self.assertEqual("https://digen.ai/en/space/7",
                         identity_queue.espaco_da_geracao("generation_00001"))
        # a build vizinha nao herda o espaco de outra
        self.assertIsNone(identity_queue.espaco_da_geracao("generation_00002"))

    def test_espaco_de_irmao_nao_conta_como_prompt_enviado(self):
        """Sem `enviado`, o slot da arma abriria o espaco que o personagem
        criou e esperaria para sempre por um video que ninguem pediu."""
        for slot in identity_slots.SLOTS:
            identity_queue.enqueue("generation_00001", "p", slot=slot)
        identity_queue.registrar_envio(
            identity_slots.job_id("generation_00001", identity_slots.CHARACTER),
            "https://digen.ai/en/space/7", [])
        arma = [j for j in identity_queue.listar()
                if j["slot"] == identity_slots.WEAPON][0]
        self.assertFalse(arma["enviado"])
        self.assertEqual("https://digen.ai/en/space/7",
                         identity_queue.espaco_da_geracao("generation_00001"))

    def test_reagendar_nao_gasta_tentativa(self):
        """Video lento nao e falha.

        Se cada estouro de espera descontasse uma tentativa, um render que
        demora mais que o timeout queimaria as tres e o job morreria esperando
        algo que ia chegar.
        """
        identity_queue.enqueue("generation_00001", "p")
        for _ in range(5):
            job = identity_queue.claim(max_attempts=3)
            self.assertIsNotNone(job, "job morreu apesar de nunca ter falhado")
            identity_queue.reagendar(job["job_id"], "ainda na fila")
        self.assertEqual(identity_queue.PENDENTE,
                         identity_queue.listar()[0]["status"])

    def test_dois_workers_nao_rodam_ao_mesmo_tempo(self):
        """Dois workers se sabotam.

        `reabrir()` devolve a fila todo job em `running`, presumindo worker
        morto. Com dois vivos, um considera orfao o job que o OUTRO esta
        processando e o rouba — foi assim que `generation_00014` foi baixado
        duas vezes e concluido duas vezes.
        """
        with identity_queue.instancia_unica() as primeiro:
            if not primeiro:
                # O lock e do MAQUINA, nao do teste: com um `identity worker`
                # de verdade rodando (o painel deixa um em pe), a premissa do
                # teste nao existe. Pular e honesto; falhar so ensinaria a
                # ignorar a suite com o app aberto.
                self.skipTest("ha um `identity worker` real segurando o lock")
            self.assertTrue(primeiro, "o primeiro worker deveria entrar")
            with identity_queue.instancia_unica() as segundo:
                self.assertFalse(segundo, "o segundo worker entrou junto")
        # liberado depois que o primeiro sai
        with identity_queue.instancia_unica() as depois:
            self.assertTrue(depois)

    def test_job_adiado_nao_e_repescado_na_mesma_rodada(self):
        """Video ainda gerando volta para `pending` — e nao pode ser repescado.

        Sem isso a rodada vira ping-pong: o mesmo job a cada ~50 s, sem nunca
        dar tempo do Digen terminar, e ocupando o worker a toa.
        """
        identity_queue.enqueue("generation_00001", "p")
        identity_queue.enqueue("generation_00002", "p")
        primeiro = identity_queue.claim()
        identity_queue.reagendar(primeiro["job_id"], "ainda gerando")

        adiados = {primeiro["job_id"]}
        seguinte = identity_queue.claim(ignorar=adiados)
        self.assertIsNotNone(seguinte)
        self.assertNotEqual(primeiro["job_id"], seguinte["job_id"])
        # sem mais nada elegivel, a rodada acaba em vez de repescar
        self.assertIsNone(identity_queue.claim(ignorar=adiados))

    def test_concluir_registra_o_arquivo(self):
        enfileirado = identity_queue.enqueue("generation_00001", "p")
        identity_queue.claim()
        job = identity_queue.concluir(enfileirado["job_id"],
                                      "x/character_video.mp4")
        self.assertEqual(identity_queue.PRONTO, job["status"])
        self.assertEqual(1, identity_queue.limpar_concluidos())

    def test_os_tres_slots_sao_jobs_independentes(self):
        """Uma geracao rende TRES clipes, e o payoff pode falhar sozinho.

        Com a fila chaveada por geracao, enfileirar a arma sobrescreveria o
        job do personagem e a build sairia com um clipe so.
        """
        for slot in identity_slots.SLOTS:
            identity_queue.enqueue("generation_00001", f"prompt {slot}", slot=slot)
        jobs = identity_queue.listar()
        self.assertEqual(3, len(jobs))
        self.assertEqual(sorted(identity_slots.SLOTS),
                         sorted(j["slot"] for j in jobs))

        arma = identity_slots.job_id("generation_00001", identity_slots.WEAPON)
        identity_queue.claim()
        identity_queue.falhar(arma, "boom", max_attempts=0)
        estados = {j["slot"]: j["status"] for j in identity_queue.listar()}
        self.assertEqual(identity_queue.FALHOU, estados[identity_slots.WEAPON])
        self.assertNotEqual(identity_queue.FALHOU,
                            estados[identity_slots.CHARACTER_WEAPON])

    def test_job_do_formato_antigo_vira_slot_de_personagem(self):
        """Fila gravada pela versao de um clipe so continua sendo processada."""
        identity_queue.ARQUIVO_FILA.parent.mkdir(parents=True, exist_ok=True)
        identity_queue.ARQUIVO_FILA.write_text(json.dumps([{
            "generation_id": "generation_00001", "status": "pending",
            "prompt": "p", "aspect": "9:16", "attempts": 0,
        }]), encoding="utf-8")
        job = identity_queue.listar()[0]
        self.assertEqual(identity_slots.CHARACTER, job["slot"])
        self.assertEqual("generation_00001#character", job["job_id"])


class TimelineTests(unittest.TestCase):
    """A montagem: onde cada clipe entra e o que acontece sem ele."""

    @classmethod
    def setUpClass(cls):
        cls.generation = _gerar()

    def _plan(self, out_dir):
        rng = RandomEngine(self.generation["seed"]).fork("editing")
        return _timeline().build(rng, self.generation, out_dir)

    @staticmethod
    def _com_clipes(pasta: Path, *quais) -> None:
        for slot in (quais or identity_slots.SLOTS):
            # ffprobe falha num arquivo assim -> o builder cai na janela do slot
            (pasta / identity_slots.ARQUIVO[slot]).write_bytes(b"nao e um mp4")

    def test_sem_clipe_a_timeline_sai_identica(self):
        """Ligar a identidade nao pode mudar um video que ja estava certo."""
        with tempfile.TemporaryDirectory() as tmp:
            com_dir = self._plan(Path(tmp))
        sem_dir = self._plan(None)
        self.assertEqual(json.dumps(sem_dir, sort_keys=True),
                         json.dumps(com_dir, sort_keys=True))
        self.assertNotIn("identity", [e["type"] for e in sem_dir["events"]])

    def test_estrutura_e_roleta_clipe_roleta_clipe_payoff(self):
        """A ordem da secao 8, do gancho ao payoff."""
        with tempfile.TemporaryDirectory() as tmp:
            self._com_clipes(Path(tmp))
            plan = self._plan(Path(tmp))
        tipos = [e["type"] for e in plan["events"]]

        self.assertEqual("hook", tipos[0])
        self.assertEqual(["identity", "final", "outro"], tipos[-3:])

        clipes = [e for e in plan["events"] if e["type"] == "identity"]
        self.assertEqual(list(identity_slots.SLOTS), [e["slot"] for e in clipes])

        posicoes = {e["slot"]: plan["events"].index(e) for e in clipes}
        virada = tipos.index("stinger")
        self.assertLess(posicoes[identity_slots.CHARACTER], virada,
                        "o clipe do personagem vem antes da virada para a arma")
        self.assertLess(virada, posicoes[identity_slots.WEAPON])
        self.assertLess(posicoes[identity_slots.WEAPON],
                        posicoes[identity_slots.CHARACTER_WEAPON])

        # cada metade so tem as roletas dela, e nessa ordem
        entidades = [e["roll"]["entity"] for e in plan["events"]
                     if e["type"] == "roulette"]
        self.assertEqual(sorted(set(entidades)), ["character", "weapon"])
        self.assertEqual(entidades, sorted(entidades, key="character weapon".split().index))

    def test_a_ficha_de_personagem_nao_volta(self):
        """Secoes 2, 3 e 15: a revelacao nao pode ser um cartao com avatar."""
        with tempfile.TemporaryDirectory() as tmp:
            self._com_clipes(Path(tmp))
            plan = self._plan(Path(tmp))
        tipos = {e["type"] for e in plan["events"]}
        self.assertNotIn("reveal_character", tipos)
        self.assertNotIn("reveal_weapon", tipos)
        # e nenhum evento aponta para os PNGs de cartao
        imagens = [e.get("image") for e in plan["events"] if e.get("image")]
        self.assertEqual([], imagens)

    def test_clipe_que_falta_vira_nameplate_no_lugar(self):
        """O video da roleta nunca espera o Digen."""
        with tempfile.TemporaryDirectory() as tmp:
            self._com_clipes(Path(tmp), identity_slots.CHARACTER)
            plan = self._plan(Path(tmp))
        por_slot = {e["slot"]: e for e in plan["events"]
                    if e["type"] in ("identity", "nameplate")}
        self.assertEqual(3, len(por_slot))
        self.assertEqual("identity", por_slot[identity_slots.CHARACTER]["type"])
        self.assertEqual("nameplate", por_slot[identity_slots.WEAPON]["type"])
        placa = por_slot[identity_slots.WEAPON]["nameplate"]
        self.assertTrue(placa["titulo"])
        self.assertNotIn("image", por_slot[identity_slots.WEAPON])

    def test_clipe_do_formato_antigo_ainda_vale_como_personagem(self):
        """Geracao anterior nao perde o clipe que tinha, nem vira imagem.

        O `digen.mp4` de quando havia um clipe so, e o `character_video.mp4` de
        quando os tres eram video, continuam entrando — e entrando como VIDEO,
        porque a midia sai da extensao do arquivo achado, nao do slot.
        """
        for nome in ("identity/digen.mp4", "character_video.mp4"):
            with self.subTest(arquivo=nome), tempfile.TemporaryDirectory() as tmp:
                legado = Path(tmp) / nome
                legado.parent.mkdir(parents=True, exist_ok=True)
                legado.write_bytes(b"nao e um mp4")
                plan = self._plan(Path(tmp))
                clipes = [e for e in plan["events"] if e["type"] == "identity"]
                self.assertEqual([identity_slots.CHARACTER],
                                 [e["slot"] for e in clipes])
                self.assertEqual(identity_slots.VIDEO,
                                 clipes[0]["asset"]["media"])

    def test_clipe_nunca_passa_do_teto_do_slot(self):
        """Secoes 4, 6 e 7: 5 s de personagem, 4 s de arma, 6 s de payoff."""
        with tempfile.TemporaryDirectory() as tmp:
            self._com_clipes(Path(tmp))
            plan = self._plan(Path(tmp))
        tetos = load_config("editing.json")["identity_slots"]
        for evento in plan["events"]:
            if evento["type"] == "identity":
                self.assertLessEqual(evento["duration"],
                                     tetos[evento["slot"]]["max"] + 0.001,
                                     evento["slot"])

    def test_o_renderer_aceita_o_evento_como_video_real(self):
        """`_asset_de_video` e teste de CAPACIDADE: nada de `if type == ...`."""
        renderer = VideoRenderer(load_config("render.json"), "celular", preview=True)
        with tempfile.TemporaryDirectory() as tmp:
            clipe = Path(tmp) / "character_video.mp4"
            clipe.write_bytes(b"x")
            evento = {"type": "identity",
                      "asset": {"path": str(clipe), "synthetic": False}}
            self.assertTrue(renderer._asset_de_video(evento))
            evento["asset"]["path"] = str(clipe) + ".sumiu"
            self.assertFalse(renderer._asset_de_video(evento))

    def test_duracao_total_bate_com_a_soma_dos_eventos(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._com_clipes(Path(tmp))
            plan = self._plan(Path(tmp))
        soma = sum(e["duration"] for e in plan["events"])
        self.assertAlmostEqual(soma, plan["total_duration"], places=2)


class _FakeLocator:
    """Locator de mentira: N elementos, alguns invisiveis."""

    def __init__(self, visiveis: list[bool], eu: int | None = None):
        self._visiveis = visiveis
        self._eu = eu

    def count(self):
        return len(self._visiveis)

    def nth(self, i):
        return _FakeLocator(self._visiveis, i)

    @property
    def first(self):
        return self.nth(0)

    def is_visible(self, timeout=None):
        return self._visiveis[self._eu]


class DuplicatasTests(unittest.TestCase):
    """O Digen renderiza o mesmo controle duas vezes (mobile + desktop).

    A variante escondida vem PRIMEIRO no DOM. Olhar so `.first` fazia
    `encontrar` devolver None para elementos que estavam na tela — foi assim
    que o contador de creditos "sumiu" mesmo visivel, e o mesmo erro derrubaria
    qualquer outro seletor.
    """

    def test_pula_a_duplicata_escondida(self):
        achado = selectors.primeiro_visivel(
            _FakeLocator([False, True]), timeout=0.1)
        self.assertIsNotNone(achado)
        self.assertEqual(1, achado._eu)

    def test_todas_escondidas_devolve_none(self):
        self.assertIsNone(selectors.primeiro_visivel(
            _FakeLocator([False, False]), timeout=0.1))

    def test_sem_elemento_nenhum_devolve_none(self):
        self.assertIsNone(selectors.primeiro_visivel(
            _FakeLocator([]), timeout=0.1))

    def test_encontrar_usa_a_varredura(self):
        class FakePage:
            def locator(self, _):
                return _FakeLocator([False, True])

        achado = selectors.encontrar(
            FakePage(), [("css", "qualquer")], timeout=0.1)
        self.assertIsNotNone(achado)


class ModeloTests(unittest.TestCase):
    """Escolher o modelo errado gasta uma geracao e entrega outra coisa."""

    def setUp(self):
        self.ajustes = identity_prompt.config.settings()

    def test_o_modelo_configurado_existe_no_menu_do_digen(self):
        """O nome tem que bater EXATO com o item do menu.

        Um typo ("Real motion 3.5") so apareceria na hora de gerar, e ai o job
        falha depois de abrir o browser e criar um Space a toa.
        """
        modelo = self.ajustes.get("modelo")
        self.assertTrue(modelo, "config/identity.json sem `modelo`")
        self.assertIn(modelo, selectors.MODELOS_CONHECIDOS)

    def test_o_turbo_vem_antes_do_normal_na_lista(self):
        """Este teste documenta a armadilha que motivou o match exato.

        No menu do Digen "Real Motion 3.5 Turbo" aparece ANTES de "Real Motion
        3.5". Qualquer busca por substring pega o primeiro — ou seja, o Turbo —
        quando o pedido e o normal.
        """
        conhecidos = list(selectors.MODELOS_CONHECIDOS)
        self.assertLess(conhecidos.index("Real Motion 3.5 Turbo"),
                        conhecidos.index("Real Motion 3.5"))

    def test_selecao_de_modelo_e_exata_e_escopada(self):
        """Duas defesas: `:text-is` (exato) e o escopo no popover.

        Sem exato pega o Turbo. Sem escopo pega o card "Real Motion 3.5" da
        galeria "Need some inspiration?", que fica ATRAS do menu — foi
        exatamente o que impediu a primeira troca de funcionar.
        """
        candidatos = selectors.opcao_de_modelo("Real Motion 3.5")
        css = [v for e, v in candidatos if e == "css"]
        self.assertTrue(css)
        for valor in css:
            self.assertIn(":text-is('Real Motion 3.5')", valor)
            self.assertTrue(any(caixa in valor for caixa in selectors.POPOVER),
                            f"seletor sem escopo de popover: {valor}")
        for _, valor in candidatos:
            self.assertNotIn("has-text", valor)

    def test_abreviacao_bate_com_o_texto_do_botao(self):
        """O botao mostra "RM3.5"; o menu diz "Real Motion 3.5"."""
        self.assertEqual("RM3.5", selectors.abreviar_modelo("Real Motion 3.5"))
        self.assertEqual("RM3.5 Turbo",
                         selectors.abreviar_modelo("Real Motion 3.5 Turbo"))
        self.assertEqual("Sora 2", selectors.abreviar_modelo("Sora 2"))

    def test_modelo_e_ajustado_antes_dos_outros_controles(self):
        """Trocar o modelo RESETA duracao, proporcao e resolucao.

        Medido em 22/08: RM3.2 -> RM3.5 derrubou 5s para 3s, 9:16 para Auto e
        720P para 480P. Se o modelo for ajustado por ultimo, ele apaga tudo que
        foi configurado antes e o video sai com os padroes do modelo.
        """
        import inspect
        from builds.identity.client import DigenClient
        corpo = inspect.getsource(DigenClient.submit_prompt)
        ordem = [corpo.index(f"self._ajustar_{c}(")
                 for c in ("modelo", "duracao", "resolucao", "aspecto")]
        self.assertEqual(sorted(ordem), ordem,
                         "o modelo precisa ser o PRIMEIRO ajuste")

    def test_duracao_e_resolucao_pedem_o_maximo(self):
        """O padrao acordado: sempre o maior tempo e a melhor qualidade.

        `"max"` le o menu do modelo em vez de listar valores fixos — assim um
        modelo novo que ofereça 12s ou 1080P e aproveitado sem ninguem precisar
        catalogar nada aqui.
        """
        for chave in ("duracao", "resolucao"):
            self.assertEqual(selectors.MAXIMO, self.ajustes.get(chave),
                             f"{chave} deveria pedir o maximo")

    def test_config_de_controle_aceita_string_ou_lista(self):
        from builds.identity.client import DigenClient
        self.assertEqual(["max"], DigenClient._preferencias("max"))
        self.assertEqual(["8s", "5s"], DigenClient._preferencias(["8s", "5s"]))
        self.assertEqual([], DigenClient._preferencias(None))
        self.assertEqual([], DigenClient._preferencias(""))

    def test_maior_opcao_escolhe_pelo_numero(self):
        """"8s" > "5s" > "3s" e "1080P" > "720P" — comparacao numerica.

        Ordem alfabetica diria que "480P" > "1080P", que e exatamente o erro
        que este helper existe para evitar.
        """
        self.assertEqual(8.0, selectors.valor_numerico("8s"))
        self.assertEqual(1080.0, selectors.valor_numerico("1080P"))
        self.assertIsNone(selectors.valor_numerico("Auto"))
        self.assertIsNone(selectors.valor_numerico("9:16"))
        self.assertGreater(selectors.valor_numerico("1080P"),
                           selectors.valor_numerico("480P"))
        self.assertLess("1080P", "480P")   # prova que alfabetico erraria

    def test_proporcao_nunca_cai_em_paisagem(self):
        """"Sempre em pe": todo fallback tambem e vertical.

        O menu tem 16:9, 3:2, 21:9 e Auto. Se o 9:16 sumisse de um modelo, um
        fallback descuidado deitaria o video — e `max` seria pior ainda, porque
        o maior numero do menu e 21:9.
        """
        for aspecto in selectors.ASPECTOS_VERTICAIS:
            largura, altura = (int(n) for n in aspecto.split(":"))
            self.assertLess(largura, altura, f"{aspecto} nao e vertical")
        self.assertEqual("9:16", selectors.ASPECTOS_VERTICAIS[0])
        self.assertEqual("9:16", self.ajustes.get("aspect"))


class SeletoresTests(unittest.TestCase):
    """Seletor vazio some silenciosamente; melhor quebrar aqui."""

    LISTAS = ("SESSAO_VIVA", "TELA_LOGIN", "CAMPO_EMAIL", "CAMPO_SENHA",
              "BOTAO_LOGIN", "DESAFIO", "BOTAO_NOVO_ESPACO", "CAMPO_PROMPT",
              "BOTAO_GERAR", "BOTAO_MODELO", "BOTAO_ASPECTO", "BOTAO_DURACAO",
              "BOTAO_RESOLUCAO", "GERANDO", "VIDEO_PRONTO", "BOTAO_DOWNLOAD",
              "ERRO_GERACAO", "CREDITOS")

    def test_toda_lista_tem_candidato_com_estrategia_conhecida(self):
        listas = [(n, getattr(selectors, n)) for n in self.LISTAS]
        listas += [("popover[%s]" % a, selectors.opcao_de_popover(a))
                   for a in selectors.ASPECTOS_CONHECIDOS]
        for nome, candidatos in listas:
            self.assertTrue(candidatos, "%s esta vazia" % nome)
            for estrategia, valor in candidatos:
                self.assertIn(estrategia, selectors.ESTRATEGIAS, nome)
                self.assertTrue(valor, nome)

    def test_candidato_de_role_declara_o_nome(self):
        """('role', 'button') sem nome casaria com QUALQUER botao da pagina."""
        todas = [c for n in self.LISTAS for c in getattr(selectors, n)]
        for estrategia, valor in todas:
            if estrategia == "role":
                self.assertIn("|", valor, "role sem nome: %r" % (valor,))

    def test_o_composer_mora_na_pagina_de_spaces(self):
        """Ancora do fluxo: nao existe rota separada de criacao no Space."""
        self.assertEqual(selectors.URL_SPACES, selectors.URL_CRIACAO)
        self.assertTrue(selectors.URL_SPACES.endswith("/space"))

    def test_o_prompt_e_contenteditable_nao_textarea(self):
        """`get_by_placeholder` nao casa aqui: nao ha atributo `placeholder`.

        Trocar isto por ('placeholder', ...) faz a automacao falhar de um jeito
        silencioso e confuso, entao o contrato fica travado.
        """
        estrategias = {e for e, _ in selectors.CAMPO_PROMPT}
        self.assertNotIn("placeholder", estrategias)
        self.assertTrue(
            any("aria-placeholder" in v or "contenteditable" in v
                for _, v in selectors.CAMPO_PROMPT))

    def test_o_submit_usa_a_classe_de_componente(self):
        """`submit-btn` e nome de componente; as utilitarias mudam por build."""
        self.assertTrue(any("submit-btn" in v for _, v in selectors.BOTAO_GERAR))

    def test_pronto_nao_depende_de_video_com_src(self):
        """Na galeria os <video> sao lazy e nascem SEM `src`.

        Se `video[src]` virar o primeiro candidato, a espera nunca termina e o
        job morre por timeout depois de 10 minutos. O sinal e o botao de
        download aparecer.
        """
        primeiro = selectors.VIDEO_PRONTO[0]
        self.assertNotIn("video[src]", primeiro[1])
        self.assertTrue(
            any("Download" in v or "download" in v
                for _, v in selectors.VIDEO_PRONTO[:2]))

    def test_estado_de_geracao_e_detectavel(self):
        """Sem detectar 'gerando', a espera confundiria card vazio com pronto."""
        textos = [v for e, v in selectors.GERANDO if e == "text"]
        self.assertTrue(any("Generating" in t for t in textos))

    def test_a_fila_conta_como_ainda_nao_terminou(self):
        """A fila vem ANTES do render.

        Na rodada de 22/08 o estado era "Waiting in generation queue..." e
        depois "You are in the priority generation queue". Sem cobrir os dois,
        a espera acha que ja acabou antes de comecar.
        """
        textos = [v.lower() for e, v in selectors.GERANDO if e == "text"]
        self.assertTrue(any("queue" in t for t in textos))

    def test_download_nao_casa_com_o_botao_do_app(self):
        """"Download Digen App" fica no topo da pagina e existe SEMPRE.

        Um candidato ('role', 'button|Download') casa com ele (a busca por
        nome nao e exata) e declara o video pronto ainda na fila — foi
        exatamente o que travou a primeira rodada real por 120 s.
        """
        for candidato in selectors.BOTAO_DOWNLOAD + selectors.VIDEO_PRONTO:
            self.assertNotEqual(("role", "button|Download"), candidato)
            self.assertNotEqual(("role", "link|Download"), candidato)

    def test_o_download_do_card_e_ancorado_no_icone(self):
        """O botao do card nao tem texto, aria-label nem title: so o path."""
        self.assertTrue(selectors.ICONE_DOWNLOAD.startswith("M228,144"))
        self.assertIn(selectors.ICONE_DOWNLOAD, selectors.BOTAO_DOWNLOAD[0][1])


if __name__ == "__main__":
    unittest.main()
