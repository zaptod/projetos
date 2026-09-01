"""O grafo de dependencia: o payoff espera as imagens - mas nunca para sempre.

O que este arquivo trava:

1. O video de personagem+arma NAO sai enquanto faltar imagem: e ela que vai
   anexada como referencia, e sem ela o modelo entrega outro rosto (foi o que
   aconteceu em generation_00020, cabelo branco no clipe e preto no payoff).
2. Esperar tem PRAZO. Vencido, o payoff vai ao ar so com texto - que e
   exatamente o video que ja saia antes desta mudanca. Degradar e obrigatorio;
   travar a fila nao.
3. "Satisfeita" nunca pode significar "existe linha `done` na fila":
   `identity queue --limpar` APAGA essas linhas, e uma limpeza de rotina nao
   pode deixar o payoff pendente para sempre.
4. Dependencia que falhou de vez NAO derruba o dependente. O payoff sabe rodar
   sem referencia; mata-lo junto tiraria o unico video que restou.

Rode de dentro de random_builds/:
    python -m unittest discover -s tests -p "test_*.py"
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from PIL import Image                                              # noqa: E402

from builds.identity import artefato                                  # noqa: E402
from builds.identity import config as icfg                            # noqa: E402
from builds.identity import queue as fila                             # noqa: E402
from builds.identity import slots                                     # noqa: E402

GID = "generation_77777"
LONGE = "2999-01-01T00:00:00+00:00"
PASSADO = "2000-01-01T00:00:00+00:00"


class GrafoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        self._fila = fila.ARQUIVO_FILA
        self._outputs = icfg.OUTPUTS
        fila.ARQUIVO_FILA = self.raiz / "queue.json"
        icfg.OUTPUTS = self.raiz / "outputs"
        (icfg.OUTPUTS / GID).mkdir(parents=True)

    def tearDown(self):
        fila.ARQUIVO_FILA = self._fila
        icfg.OUTPUTS = self._outputs
        self._tmp.cleanup()

    def _enfileirar(self, prazo=LONGE):
        for slot in slots.JOBS:
            fila.enqueue(GID, f"prompt {slot}", slot=slot,
                         aguardar_ate=prazo if slots.depende_de(slot) else None)

    def _imagem(self, slot: str):
        Image.new("RGB", (600, 1064), (40, 30, 80)).save(
            icfg.OUTPUTS / GID / slots.ARQUIVO[slot])
        self.assertTrue(artefato.utilizavel(GID, slot))

    def _drenar(self) -> list:
        pegos = []
        while (job := fila.claim()) is not None:
            pegos.append(job["slot"])
        return pegos

    def test_a_corrente_libera_um_elo_por_vez(self):
        """imagens -> juncao -> video. Nada fura a fila."""
        self._enfileirar()
        pegos = self._drenar()
        self.assertIn(slots.CHARACTER, pegos)
        self.assertIn(slots.WEAPON, pegos)
        self.assertNotIn(slots.REFERENCIA, pegos,
                         "a juncao saiu antes das imagens existirem")
        self.assertNotIn(slots.CHARACTER_WEAPON, pegos,
                         "o payoff saiu antes da juncao existir")

    def test_uma_imagem_so_ainda_segura_a_juncao(self):
        self._enfileirar()
        self._imagem(slots.CHARACTER)
        self.assertNotIn(slots.REFERENCIA, self._drenar())

    def test_com_as_duas_imagens_a_juncao_libera(self):
        self._enfileirar()
        for slot in (slots.CHARACTER, slots.WEAPON):
            self._imagem(slot)
        pegos = self._drenar()
        self.assertIn(slots.REFERENCIA, pegos)
        self.assertNotIn(slots.CHARACTER_WEAPON, pegos,
                         "o payoff nao pode sair so porque as imagens existem")

    def test_com_a_juncao_pronta_o_payoff_libera(self):
        self._enfileirar()
        for slot in (slots.CHARACTER, slots.WEAPON, slots.REFERENCIA):
            self._imagem(slot)
        self.assertIn(slots.CHARACTER_WEAPON, self._drenar())

    def test_a_referencia_do_payoff_e_a_imagem_COMPOSTA(self):
        """Com a juncao pronta, o Digen recebe UMA imagem, nao as duas cruas."""
        from builds.identity import referencias
        for slot in (slots.CHARACTER, slots.WEAPON, slots.REFERENCIA):
            self._imagem(slot)
        escolhidas = referencias.disponiveis(GID)
        self.assertEqual([slots.ARQUIVO[slots.REFERENCIA]],
                         [c.name for c in escolhidas])
        # e o editor continua recebendo as duas cruas
        entradas = referencias.entradas_do_editor(GID)
        self.assertEqual([slots.ARQUIVO[slots.CHARACTER],
                          slots.ARQUIVO[slots.WEAPON]],
                         [c.name for c in entradas])

    def test_disco_manda_mais_que_a_fila(self):
        """`identity queue --limpar` apaga as linhas `done`.

        Se a prova de que a imagem existe fosse a linha da fila, uma limpeza de
        rotina deixaria o payoff pendente para sempre.
        """
        self._enfileirar()
        for slot in (slots.CHARACTER, slots.WEAPON, slots.REFERENCIA):
            self._imagem(slot)
            fila.concluir(slots.job_id(GID, slot), "x.png")
        self.assertEqual(3, fila.limpar_concluidos())
        self.assertIn(slots.CHARACTER_WEAPON, self._drenar())

    def test_prazo_vencido_degrada_para_texto(self):
        """Sem imagem nenhuma, vencido o prazo o payoff sai assim mesmo."""
        self._enfileirar(prazo=PASSADO)
        self.assertIn(slots.CHARACTER_WEAPON, self._drenar())

    def test_dependencia_que_falhou_nao_mata_o_payoff(self):
        self._enfileirar()
        for slot in (slots.CHARACTER, slots.WEAPON, slots.REFERENCIA):
            fila.claim()
            fila.falhar(slots.job_id(GID, slot), "boom", max_attempts=0)
        self.assertIn(slots.CHARACTER_WEAPON, self._drenar())

    def test_payoff_bloqueado_nao_conta_como_trabalho(self):
        """Senao o `--watch` recua ate o teto abrindo o Chrome a esmo.

        O caso real: o worker pegou as duas imagens e elas estao SENDO
        geradas (`running`). Nesse instante a fila tem uma linha `pending` — o
        payoff — mas ninguem consegue pega-la, e `havia trabalho` tem que ser
        falso para a rodada nao ser contada como improdutiva.
        """
        self._enfileirar()
        self.assertIsNotNone(fila.claim())
        self.assertIsNotNone(fila.claim())
        pendentes = [j["slot"] for j in fila.listar()
                     if j["status"] == fila.PENDENTE]
        self.assertEqual([slots.REFERENCIA, slots.CHARACTER_WEAPON],
                         sorted(pendentes, key=slots.JOBS.index))
        self.assertFalse(fila.tem_reivindicavel())

    def test_claim_por_provedor_nao_mistura_os_dois_sites(self):
        self._enfileirar()
        self.assertIsNone(fila.claim(provedor=slots.DIGEN),
                          "o payoff do Digen saiu antes das imagens")
        job = fila.claim(provedor=slots.PICASSO)
        self.assertIsNotNone(job)
        self.assertEqual(slots.PICASSO, job["provider"])

    def test_reenfileirar_nao_perde_o_grafo(self):
        """`identity run` ressuscita o job; sem o grafo ele fura a fila."""
        self._enfileirar()
        payoff = slots.job_id(GID, slots.CHARACTER_WEAPON)
        fila.claim()
        fila.falhar(payoff, "x", max_attempts=0)
        fila.enqueue(GID, "prompt novo", slot=slots.CHARACTER_WEAPON,
                     aguardar_ate=LONGE)
        linha = [j for j in fila.listar() if j["job_id"] == payoff][0]
        self.assertEqual([slots.job_id(GID, slots.REFERENCIA)],
                         linha["depends_on"])
        self.assertEqual(slots.DIGEN, linha["provider"])

    def test_fila_antiga_ganha_provedor_e_grafo_na_leitura(self):
        fila.ARQUIVO_FILA.parent.mkdir(parents=True, exist_ok=True)
        fila.ARQUIVO_FILA.write_text(json.dumps([{
            "generation_id": GID, "slot": slots.CHARACTER_WEAPON,
            "job_id": slots.job_id(GID, slots.CHARACTER_WEAPON),
            "status": "pending", "prompt": "p", "aspect": "9:16", "attempts": 0,
        }]), encoding="utf-8")
        linha = fila.listar()[0]
        self.assertEqual(slots.DIGEN, linha["provider"])
        self.assertEqual([slots.job_id(GID, slots.REFERENCIA)],
                         linha["depends_on"])


class _ChooserFake:
    def __init__(self, varios=False):
        self.varios = varios
        self.recebidos = []

    def is_multiple(self):
        return self.varios

    def set_files(self, arquivos):
        self.recebidos.append(arquivos)


class _EsperaChooser:
    def __init__(self, pagina, abre: bool):
        self.pagina, self.abre = pagina, abre

    def __enter__(self):
        return self

    def __exit__(self, *a):
        if not self.abre:
            raise TimeoutError("nenhum dialogo de arquivo abriu")
        return False

    @property
    def value(self):
        return self.pagina.chooser


class _PaginaDigenFake:
    """Composer de mentira: dialogo de arquivo + miniatura como prova.

    Reproduz o que o site faz de verdade (levantado em 24/08/2026): clicar em
    "Upload Image" abre o seletor do sistema, e o composer so mostra miniatura
    quando o app ACEITA o arquivo.
    """

    def __init__(self, abre_dialogo=True, aceita=1):
        self.chooser = _ChooserFake()
        self.abre_dialogo = abre_dialogo
        self.aceita = aceita
        self.thumbs = []
        self.cliques = []

    def expect_file_chooser(self, timeout=None):
        return _EsperaChooser(self, self.abre_dialogo)

    def registrar_clique(self, alvo):
        self.cliques.append(alvo)
        if alvo == "opcao" and self.abre_dialogo and len(self.thumbs) < self.aceita:
            self.thumbs.append(f"blob:fake/{len(self.thumbs)}")

    def locator(self, seletor):
        return _LocatorFake(quantidade=0)


class _SelFake:
    """Modulo de seletores de mentira, com a mesma superficie que o real."""

    BOTAO_ANEXO = [("css", "botao")]
    OPCAO_ENVIAR_IMAGEM = [("css", "opcao")]
    ENTRADA_ARQUIVO = 'input[type="file"]'

    def __init__(self, pagina, tem_botao=True):
        self.pagina, self.tem_botao = pagina, tem_botao

    def encontrar(self, page, candidatos, timeout=2.0):
        if not self.tem_botao:
            return None
        alvo = candidatos[0][1]
        pagina = self.pagina

        class _Clicavel:
            def click(self):
                pagina.registrar_clique(alvo)
        return _Clicavel()

    def entrada_de_arquivo(self, page, indice=0):
        return None

    @staticmethod
    def miniaturas(page):
        return list(page.thumbs)


class _LocatorFake:
    def __init__(self, quantidade=0):
        self.quantidade = quantidade

    def count(self):
        return self.quantidade

    def nth(self, indice):
        return self


class AnexoTests(unittest.TestCase):
    """O anexo so conta quando o COMPOSER mostra a miniatura."""

    def setUp(self):
        from builds.identity import referencias
        self.referencias = referencias
        self._tmp = tempfile.TemporaryDirectory()
        self.imagens = []
        for nome in ("character_image.png", "weapon_image.png"):
            destino = Path(self._tmp.name) / nome
            Image.new("RGB", (600, 1064), (30, 30, 60)).save(destino)
            self.imagens.append(destino)

    def tearDown(self):
        self._tmp.cleanup()

    def test_anexa_pelo_dialogo_e_confirma_pela_miniatura(self):
        pagina = _PaginaDigenFake(aceita=2)
        anexadas = self.referencias.anexar(pagina, self.imagens, _SelFake(pagina),
                                           espera_miniatura=0.5)
        self.assertEqual([self.imagens[0]], anexadas)
        self.assertEqual(1, len(pagina.thumbs))

    def test_nunca_tenta_a_segunda_imagem(self):
        """A segunda SUBSTITUI a primeira: insistir troca o personagem pela arma.

        E a substituicao nao aparece na contagem de miniaturas (continua 1),
        entao o codigo achava que tinha recusado quando tinha trocado.
        """
        pagina = _PaginaDigenFake(aceita=2)
        self.referencias.anexar(pagina, self.imagens, _SelFake(pagina),
                                espera_miniatura=0.5)
        self.assertEqual(1, pagina.cliques.count("opcao"),
                         "abriu o menu de anexo mais de uma vez")

    def test_teto_maior_permite_mais_de_um_quando_o_site_deixar(self):
        pagina = _PaginaDigenFake(aceita=2)
        anexadas = self.referencias.anexar(pagina, self.imagens, _SelFake(pagina),
                                           espera_miniatura=0.5, maximo=2)
        self.assertEqual(self.imagens, anexadas)

    def test_arquivo_entregue_sem_miniatura_NAO_conta(self):
        """O bug real: o arquivo foi entregue e o composer ficou vazio.

        Uma rodada inteira reportou "1 referencia anexada" com nada anexado,
        porque a prova era "nao levantou excecao".
        """
        pagina = _PaginaDigenFake(aceita=0)
        self.assertEqual([], self.referencias.anexar(
            pagina, self.imagens, _SelFake(pagina), espera_miniatura=0.5))

    def test_composer_de_uma_referencia_so_para_na_primeira(self):
        """`multiple: false` - descobrir na pratica, nao supor."""
        pagina = _PaginaDigenFake(aceita=1)
        anexadas = self.referencias.anexar(pagina, self.imagens, _SelFake(pagina),
                                           espera_miniatura=0.5)
        self.assertEqual([self.imagens[0]], anexadas,
                         "a ordem poe o personagem na frente")

    def test_sem_ponto_de_anexo_devolve_vazio_e_nao_levanta(self):
        pagina = _PaginaDigenFake(abre_dialogo=False)
        self.assertEqual([], self.referencias.anexar(
            pagina, self.imagens, _SelFake(pagina, tem_botao=False),
            espera_miniatura=0.5))

    def test_pagina_que_explode_nao_derruba_a_geracao(self):
        class _Quebrada:
            def expect_file_chooser(self, timeout=None):
                raise RuntimeError("target closed")

            def locator(self, seletor):
                raise RuntimeError("target closed")

        self.assertEqual([], self.referencias.anexar(
            _Quebrada(), self.imagens,
            _SelFake(_PaginaDigenFake(), tem_botao=False),
            espera_miniatura=0.5))

    def test_sem_imagem_nenhuma_nem_tenta(self):
        pagina = _PaginaDigenFake()
        self.assertEqual([], self.referencias.anexar(pagina, [], _SelFake(pagina)))
        self.assertEqual([], pagina.cliques)

    def test_imagem_dentro_do_teto_sobe_como_esta(self):
        self.assertEqual(self.imagens[0],
                         self.referencias.para_upload(self.imagens[0]))

    def test_imagem_grande_demais_e_reduzida_antes_de_subir(self):
        grande = Path(self._tmp.name) / "gigante.png"
        Image.new("RGB", (2400, 4200), (10, 60, 10)).save(grande)
        saida = self.referencias.para_upload(grande)
        self.assertNotEqual(grande, saida)
        with Image.open(saida) as img:
            self.assertLessEqual(max(img.size), self.referencias.LADO_MAXIMO)

    def test_a_ordem_decide_quem_vai_quando_so_cabe_um(self):
        """Rosto errado se nota muito mais que lamina errada."""
        outputs = Path(self._tmp.name) / "outputs"
        (outputs / GID).mkdir(parents=True)
        anterior = icfg.OUTPUTS
        icfg.OUTPUTS = outputs
        try:
            for slot in (slots.CHARACTER, slots.WEAPON):
                Image.new("RGB", (400, 700), (50, 50, 90)).save(
                    outputs / GID / slots.ARQUIVO[slot])
            self.assertEqual([slots.ARQUIVO[slots.CHARACTER],
                              slots.ARQUIVO[slots.WEAPON]],
                             [c.name for c in self.referencias.disponiveis(GID)])
            invertida = self.referencias.disponiveis(
                GID, ordem=[slots.WEAPON, slots.CHARACTER])
            self.assertEqual(slots.ARQUIVO[slots.WEAPON], invertida[0].name)
        finally:
            icfg.OUTPUTS = anterior

    def test_slot_de_video_nunca_entra_como_referencia(self):
        outputs = Path(self._tmp.name) / "outputs2"
        (outputs / GID).mkdir(parents=True)
        anterior = icfg.OUTPUTS
        icfg.OUTPUTS = outputs
        try:
            (outputs / GID / slots.ARQUIVO[slots.CHARACTER_WEAPON]).write_bytes(
                b"mp4 de mentira" * 900)
            self.assertEqual([], self.referencias.disponiveis(GID))
        finally:
            icfg.OUTPUTS = anterior


class SeletorDeAnexoTests(unittest.TestCase):
    """As ancoras do fluxo "+" -> "Enviar imagem"."""

    def setUp(self):
        from builds.identity import selectors
        self.sel = selectors

    def test_o_mais_nao_colide_com_o_download(self):
        """Bandeja com seta para cima e para baixo comecam parecido."""
        self.assertFalse(self.sel.ICONE_DOWNLOAD.startswith(self.sel.ICONE_MAIS))
        self.assertFalse(self.sel.ICONE_MAIS.startswith(self.sel.ICONE_DOWNLOAD))

    def test_enviar_imagem_tem_ancora_que_nao_depende_de_idioma(self):
        """A conta pode estar em pt ou en; o icone nao muda de lingua."""
        estrategias = [e for e, _ in self.sel.OPCAO_ENVIAR_IMAGEM]
        self.assertIn("css", estrategias)
        alvos = [v for _, v in self.sel.OPCAO_ENVIAR_IMAGEM]
        self.assertTrue(any(self.sel.SETA_PARA_CIMA in v for v in alvos))
        self.assertTrue(any("Enviar imagem" in v for v in alvos))
        self.assertTrue(any("upload image" in v.lower() for v in alvos))

    def test_o_botao_de_anexo_prefere_a_ancora_mais_especifica(self):
        """Icone + data-slot primeiro; so o icone depois, como rede."""
        primeiro = self.sel.BOTAO_ANEXO[0][1]
        self.assertIn("popover-trigger", primeiro)
        self.assertIn(self.sel.ICONE_MAIS, primeiro)


class _ClienteFake:
    """Cliente de mentira que registra a ORDEM em que foi chamado."""

    def __init__(self, anexa=()):
        self.anexa = list(anexa)
        self.chamadas = []
        self.enviado = None

    def preparar_espaco(self, espaco):
        self.chamadas.append("preparar")
        return ["ja_estava.jpg"]

    def anexar_referencias(self, caminhos):
        self.chamadas.append("anexar")
        return list(self.anexa)

    def submit_prompt(self, texto, *a, **k):
        self.chamadas.append("submit")
        self.enviado = texto
        return k.get("antes") or []


class LateBindingTests(unittest.TestCase):
    """O texto do payoff e decidido DEPOIS de saber o que foi anexado."""

    def setUp(self):
        from builds.identity import worker
        self.worker = worker
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        self._fila, self._outputs = fila.ARQUIVO_FILA, icfg.OUTPUTS
        fila.ARQUIVO_FILA = self.raiz / "queue.json"
        icfg.OUTPUTS = self.raiz / "outputs"
        (icfg.OUTPUTS / GID).mkdir(parents=True)
        # generation.json real, senao nao ha identidade para descrever
        from builds.generation.session_generator import SessionGenerator
        generation = SessionGenerator().generate(seed=7, generation_id=GID)
        (icfg.OUTPUTS / GID / "generation.json").write_text(
            json.dumps(generation, ensure_ascii=False), encoding="utf-8")
        self.ajustes = icfg.settings()
        self.job = fila.enqueue(GID, "TEXTO ORIGINAL DA FILA",
                                slot=slots.CHARACTER_WEAPON, aguardar_ate=LONGE)

    def tearDown(self):
        fila.ARQUIVO_FILA, icfg.OUTPUTS = self._fila, self._outputs
        self._tmp.cleanup()

    def _imagem(self, slot):
        destino = icfg.OUTPUTS / GID / slots.ARQUIVO[slot]
        Image.new("RGB", (600, 1064), (20, 40, 70)).save(destino)
        return destino

    def test_anexa_antes_de_escrever_o_prompt(self):
        """Ordem: preparar -> anexar -> texto. Anexar depois perderia o anexo."""
        self._imagem(slots.CHARACTER)
        self._imagem(slots.WEAPON)
        cliente = _ClienteFake(anexa=[icfg.OUTPUTS / GID / slots.ARQUIVO[s]
                                      for s in (slots.CHARACTER, slots.WEAPON)])
        texto, antes, _modelo = self.worker._texto_com_referencias(
            cliente, self.job, self.ajustes, None)
        self.assertEqual(["preparar", "anexar"], cliente.chamadas)
        self.assertEqual(["ja_estava.jpg"], antes)
        self.assertIn("reference", texto.lower())

    def test_duas_referencias_encurtam_o_texto(self):
        """Com as duas imagens, a aparencia vai nos pixels, nao nas palavras."""
        self._imagem(slots.CHARACTER)
        self._imagem(slots.WEAPON)
        cliente = _ClienteFake(anexa=[icfg.OUTPUTS / GID / slots.ARQUIVO[s]
                                      for s in (slots.CHARACTER, slots.WEAPON)])
        com_duas, _, _modelo = self.worker._texto_com_referencias(
            cliente, self.job, self.ajustes, None)

        sem_nenhuma, _, _modelo = self.worker._texto_com_referencias(
            _ClienteFake(anexa=[]), self.job, self.ajustes, None)
        self.assertLess(len(com_duas), len(sem_nenhuma),
                        "com imagem o texto tinha que encurtar")

    def test_uma_referencia_so_nao_encurta_o_lado_sem_imagem(self):
        """A arma sem imagem continua descrita por inteiro."""
        self._imagem(slots.CHARACTER)
        cliente = _ClienteFake(
            anexa=[icfg.OUTPUTS / GID / slots.ARQUIVO[slots.CHARACTER]])
        texto, _, _modelo = self.worker._texto_com_referencias(
            cliente, self.job, self.ajustes, None)
        from builds.identity.prompt import campos
        generation = json.loads(
            (icfg.OUTPUTS / GID / "generation.json").read_text(encoding="utf-8"))
        valores = campos(generation, self.ajustes)
        self.assertIn(valores["ARMA_ESTILO"].lower(), texto.lower())
        self.assertIn("reference", texto.lower())

    def test_sem_anexo_vai_o_texto_completo_de_sempre(self):
        """Degradacao = o video que ja saia antes desta mudanca."""
        texto, _, _modelo = self.worker._texto_com_referencias(
            _ClienteFake(anexa=[]), self.job, self.ajustes, None)
        from builds.identity.prompt import campos
        generation = json.loads(
            (icfg.OUTPUTS / GID / "generation.json").read_text(encoding="utf-8"))
        valores = campos(generation, self.ajustes)
        for chave in ("NOME", "CLASSE", "ARMA_ESTILO", "RARIDADE"):
            self.assertIn(str(valores[chave]).lower(), texto.lower(), chave)

    def test_o_texto_enviado_fica_gravado_na_fila(self):
        """Senao a retomada mandaria outro texto para o video em voo."""
        self._imagem(slots.CHARACTER)
        cliente = _ClienteFake(
            anexa=[icfg.OUTPUTS / GID / slots.ARQUIVO[slots.CHARACTER]])
        texto, _, _modelo = self.worker._texto_com_referencias(
            cliente, self.job, self.ajustes, None)
        linha = fila.listar()[0]
        self.assertEqual(texto, linha["prompt"])
        self.assertEqual(1, len(linha["referencias"]))

    def test_generation_sumida_nao_derruba_o_payoff(self):
        (icfg.OUTPUTS / GID / "generation.json").unlink()
        texto, _, _modelo = self.worker._texto_com_referencias(
            _ClienteFake(anexa=[]), self.job, self.ajustes, None)
        self.assertEqual("TEXTO ORIGINAL DA FILA", texto)


class InterfaceDeProvedorTests(unittest.TestCase):
    """Os dois clientes atendem pela MESMA porta — e ela nao pode derivar.

    `worker.processar` anota `DigenClient` mas so usa NOMES: quem chega la
    pode ser o PicassoClient. Nada no Python confere isso, entao a divergencia
    aparece em producao, no meio de uma rodada, como
    `submit_prompt() got an unexpected keyword argument`. Foi exatamente o que
    aconteceu ao adicionar `antes` num cliente e nao no outro.
    """

    # O que o worker chama num cliente, seja ele qual for.
    METODOS = ("preparar_espaco", "abrir_espaco", "submit_prompt",
               "wait_for_render", "comprovar_origem", "download", "creditos",
               "presets_atuais")
    ATRIBUTOS = ("url_do_espaco", "presets_aplicados", "prompt_enviado",
                 "enviado_em")

    def setUp(self):
        from builds.identity.client import DigenClient
        from builds.identity.picasso_client import PicassoClient
        self.classes = {"digen": DigenClient, "picasso": PicassoClient}

    def test_os_dois_tem_todos_os_metodos(self):
        for nome, classe in self.classes.items():
            for metodo in self.METODOS:
                self.assertTrue(callable(getattr(classe, metodo, None)),
                                f"{nome} nao tem {metodo}()")

    def test_as_assinaturas_batem_parametro_a_parametro(self):
        import inspect
        for metodo in self.METODOS:
            nomes = {}
            for provedor, classe in self.classes.items():
                nomes[provedor] = list(
                    inspect.signature(getattr(classe, metodo)).parameters)
            self.assertEqual(nomes["digen"], nomes["picasso"],
                             f"{metodo}() divergiu entre os provedores")

    def test_o_construtor_aceita_o_que_o_registro_passa(self):
        import inspect
        for nome, classe in self.classes.items():
            parametros = list(inspect.signature(classe.__init__).parameters)
            for esperado in ("ctx", "page", "ajustes", "rng",
                             "ao_descobrir_espaco"):
                self.assertIn(esperado, parametros, f"{nome}.__init__")

    def test_toda_instancia_nasce_com_os_atributos_que_o_worker_le(self):
        for nome, classe in self.classes.items():
            instancia = classe(None, None, {"referencias": {}}, None)
            for atributo in self.ATRIBUTOS:
                self.assertTrue(hasattr(instancia, atributo),
                                f"{nome} nao expoe {atributo}")

    def test_o_registro_devolve_a_classe_certa_para_cada_slot(self):
        from builds.identity import provedores
        for slot in slots.SLOTS:
            provedor = slots.provedor(slot)
            self.assertIn(slot, provedores.slots_de(provedor))
            self.assertIsNotNone(provedores.seletores(provedor))


class MapeamentoDeReferenciaTests(unittest.TestCase):
    """O arquivo anexado tem que voltar a dizer de que slot ele veio.

    Bug real, visto na primeira rodada de verdade: `para_upload` reduz a
    imagem e grava `character_image_ref.jpg`, e o mapeamento comparava o nome
    INTEIRO. Resultado: a imagem era anexada com sucesso e o prompt caia na
    variante de ZERO referencia — o anexo funcionava e o texto nao ficava
    sabendo. Nada levantava erro; so o log dizia "1 referencia" ao lado de um
    prompt do tamanho de "nenhuma".
    """

    def setUp(self):
        from builds.identity import referencias
        self.referencias = referencias

    def test_o_arquivo_reduzido_ainda_aponta_para_o_slot(self):
        self.assertEqual(slots.CHARACTER,
                         self.referencias.slot_do_arquivo("character_image_ref.jpg"))
        self.assertEqual(slots.WEAPON,
                         self.referencias.slot_do_arquivo("weapon_image_ref.jpg"))

    def test_o_nome_canonico_continua_valendo(self):
        for slot in slots.SLOTS:
            self.assertEqual(
                slot, self.referencias.slot_do_arquivo(slots.ARQUIVO[slot]))

    def test_arquivo_de_fora_nao_vira_slot_por_acidente(self):
        self.assertIsNone(self.referencias.slot_do_arquivo("qualquer.png"))
        self.assertIsNone(self.referencias.slot_do_arquivo("logo.jpg"))

    def test_todo_arquivo_que_para_upload_gera_e_reconhecivel(self):
        """A trava real: o que sai do preparo tem que voltar a ser mapeavel."""
        with tempfile.TemporaryDirectory() as tmp:
            for slot in (slots.CHARACTER, slots.WEAPON):
                origem = Path(tmp) / slots.ARQUIVO[slot]
                # grande de proposito, para forcar o reencode
                Image.new("RGB", (2400, 4200), (10, 10, 40)).save(origem)
                preparado = self.referencias.para_upload(origem)
                self.assertNotEqual(origem, preparado, "nao reduziu")
                self.assertEqual(slot,
                                 self.referencias.slot_do_arquivo(preparado),
                                 f"{preparado.name} perdeu o slot de origem")


class ReenfileirarTests(unittest.TestCase):
    """Reenfileirar um job concluido quer dizer FAZER DE NOVO."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._fila = fila.ARQUIVO_FILA
        fila.ARQUIVO_FILA = Path(self._tmp.name) / "queue.json"

    def tearDown(self):
        fila.ARQUIVO_FILA = self._fila
        self._tmp.cleanup()

    def test_reenfileirar_zera_o_envio_anterior(self):
        """Sem zerar, o worker RETOMA e rebaixa o mesmo arquivo.

        Bug real: ao refazer um payoff, o `space_url` antigo continuava na
        linha e o worker reabriu aquele espaco em vez de gerar. O video novo
        saiu byte por byte igual ao velho, sem uma linha de log dizendo isso.
        """
        job = fila.enqueue(GID, "prompt v1", slot=slots.CHARACTER_WEAPON)
        fila.claim()
        fila.registrar_envio(job["job_id"], "https://digen.ai/en/space/9", ["a"])
        fila.concluir(job["job_id"], "x.mp4")
        self.assertTrue(fila.listar()[0]["enviado"])

        fila.enqueue(GID, "prompt v2", slot=slots.CHARACTER_WEAPON)
        linha = fila.listar()[0]
        self.assertEqual(fila.PENDENTE, linha["status"])
        self.assertEqual("prompt v2", linha["prompt"])
        self.assertFalse(linha["enviado"], "voltou como retomada, nao como nova")
        self.assertIsNone(linha["videos_antes"])
        self.assertIsNone(linha["referencias"])

    def test_job_em_andamento_nao_e_reiniciado_por_engano(self):
        """Idempotencia: enfileirar de novo o que ja esta em voo nao mexe nele."""
        job = fila.enqueue(GID, "prompt", slot=slots.CHARACTER)
        fila.claim()
        fila.registrar_envio(job["job_id"], "https://x/space/1", [])
        fila.enqueue(GID, "outro prompt", slot=slots.CHARACTER)
        linha = fila.listar()[0]
        self.assertTrue(linha["enviado"], "um job em voo foi reiniciado")
        self.assertEqual("prompt", linha["prompt"])


class ModeloComReferenciaTests(unittest.TestCase):
    """Anexar imagem so adianta com um modelo que OLHA para ela.

    Descoberta cara: com Real Motion (text-to-video da casa) o anexo funciona
    mecanicamente — miniatura no composer, tudo confirmado — e o video sai com
    OUTRO personagem. Em generation_00021 a referencia era um guerreiro
    barbudo de tunica azul e brilho ciano, e o payoff entregou um elfo de
    cabelo branco com armadura vermelha. O modelo tem que trocar junto.
    """

    def setUp(self):
        from builds.identity import worker
        self.worker = worker
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        self._fila, self._outputs = fila.ARQUIVO_FILA, icfg.OUTPUTS
        fila.ARQUIVO_FILA = self.raiz / "queue.json"
        icfg.OUTPUTS = self.raiz / "outputs"
        (icfg.OUTPUTS / GID).mkdir(parents=True)
        from builds.generation.session_generator import SessionGenerator
        generation = SessionGenerator().generate(seed=11, generation_id=GID)
        (icfg.OUTPUTS / GID / "generation.json").write_text(
            json.dumps(generation, ensure_ascii=False), encoding="utf-8")
        self.ajustes = icfg.settings()
        self.job = fila.enqueue(GID, "texto da fila",
                                slot=slots.CHARACTER_WEAPON, aguardar_ate=LONGE)

    def tearDown(self):
        fila.ARQUIVO_FILA, icfg.OUTPUTS = self._fila, self._outputs
        self._tmp.cleanup()

    def _imagem(self, slot):
        destino = icfg.OUTPUTS / GID / slots.ARQUIVO[slot]
        Image.new("RGB", (600, 1064), (20, 40, 70)).save(destino)
        return destino

    def test_o_modelo_com_referencia_vem_do_config(self):
        """`null` = nao troca. Hoje e null porque image-to-video e pago."""
        self._imagem(slots.CHARACTER)
        cliente = _ClienteFake(
            anexa=[icfg.OUTPUTS / GID / slots.ARQUIVO[slots.CHARACTER]])
        _, _, modelo = self.worker._texto_com_referencias(
            cliente, self.job, self.ajustes, None)
        self.assertEqual(self.ajustes["referencias"].get("modelo"), modelo)

    def test_sem_referencia_mantem_o_modelo_da_raiz(self):
        """`None` = nao mexe; o cliente usa o modelo padrao do config."""
        _, _, modelo = self.worker._texto_com_referencias(
            _ClienteFake(anexa=[]), self.job, self.ajustes, None)
        self.assertIsNone(modelo)

    def test_todo_modelo_configurado_esta_na_lista_branca(self):
        """Modelo pago escolhido por engano custa dinheiro de verdade."""
        permitidos = self.ajustes["modelos_permitidos"]
        self.assertIn(self.ajustes["modelo"], permitidos)
        referencia = self.ajustes["referencias"].get("modelo")
        if referencia:
            self.assertIn(referencia, permitidos)

    def test_a_lista_branca_so_tem_o_modelo_incluso(self):
        """Kling, Runway, Sora, Veo e Seedance sao por geracao."""
        pagos = ("Kling", "Runway", "Sora", "Veo", "Seedance", "Grok",
                 "MiniMax", "FLUX", "Gemini")
        for nome in self.ajustes["modelos_permitidos"]:
            for pago in pagos:
                self.assertNotIn(pago, nome, f"{nome} e cobrado por geracao")

    def test_modelo_fora_da_lista_e_recusado_antes_de_gerar(self):
        from builds.identity.client import DigenClient, GeracaoFalhou
        cliente = DigenClient.__new__(DigenClient)
        cliente.ajustes = {"modelos_permitidos": ["Real Motion 3.5"]}
        with self.assertRaises(GeracaoFalhou) as ctx:
            cliente._ajustar_modelo("Kling 3.0")
        self.assertIn("lista branca", str(ctx.exception))


class ZumbiTests(unittest.TestCase):
    """Job `pending` que o `claim` nunca pega e o pior estado possivel.

    Ele nao roda e nao aparece como falha — some do radar. `reabrir` existe
    justamente para evitar isso quando o worker morre; reenfileirar precisava
    da mesma cortesia e nao tinha: um job que falhou tres vezes voltava como
    `pending` com as tentativas no teto e ficava parado para sempre.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._fila = fila.ARQUIVO_FILA
        fila.ARQUIVO_FILA = Path(self._tmp.name) / "queue.json"

    def tearDown(self):
        fila.ARQUIVO_FILA = self._fila
        self._tmp.cleanup()

    def test_reenfileirar_zera_as_tentativas(self):
        job = fila.enqueue(GID, "p", slot=slots.CHARACTER)
        for _ in range(3):
            fila.claim(max_attempts=3)
            fila.falhar(job["job_id"], "boom", max_attempts=3)
        self.assertEqual(fila.FALHOU, fila.listar()[0]["status"])

        fila.enqueue(GID, "p de novo", slot=slots.CHARACTER)
        linha = fila.listar()[0]
        self.assertEqual(fila.PENDENTE, linha["status"])
        self.assertEqual(0, linha["attempts"])
        self.assertIsNotNone(fila.claim(max_attempts=3),
                             "voltou zumbi: pending e inclaimavel")

    def test_reenfileirar_destrava_pending_com_tentativas_no_teto(self):
        """O caso que o conserto anterior nao alcancava.

        `enqueue` devolvia cedo por idempotencia sempre que o job estava
        `pending` — inclusive quando ele estava pending E inclaimavel. O unico
        comando capaz de destravar dizia OK e nao mudava nada.
        """
        job = fila.enqueue(GID, "p", slot=slots.CHARACTER)
        for _ in range(3):
            fila.claim(max_attempts=3)
            fila.reagendar(job["job_id"], "estourou")
        # `reagendar` devolve a tentativa, entao forco o estado travado
        linhas = fila.listar()
        linhas[0]["attempts"] = 3
        linhas[0]["status"] = fila.PENDENTE
        fila.ARQUIVO_FILA.write_text(json.dumps(linhas), encoding="utf-8")
        self.assertIsNone(fila.claim(max_attempts=3), "premissa: esta travado")

        fila.enqueue(GID, "p", slot=slots.CHARACTER)
        self.assertEqual(0, fila.listar()[0]["attempts"])
        self.assertIsNotNone(fila.claim(max_attempts=3))

    def test_job_em_voo_continua_intocado(self):
        """Destravar zumbi nao pode virar reiniciar o que esta rodando."""
        job = fila.enqueue(GID, "prompt", slot=slots.CHARACTER)
        fila.claim(max_attempts=3)
        fila.registrar_envio(job["job_id"], "https://x/space/1", [])
        fila.enqueue(GID, "prompt novo", slot=slots.CHARACTER)
        linha = fila.listar()[0]
        self.assertEqual("prompt", linha["prompt"])
        self.assertTrue(linha["enviado"])

    def test_o_worker_explica_por_que_parou(self):
        """Rodada muda e indistinguivel de rodada que nao teve trabalho."""
        import inspect
        from builds.identity import worker
        fonte = inspect.getsource(worker._explicar_parada)
        self.assertIn("fila vazia", fonte)
        self.assertIn("tentativas esgotadas", fonte)
        self.assertIn("esperando", fonte)
        self.assertIn("_explicar_parada", inspect.getsource(worker._drenar))


class BotaoDeModeloTests(unittest.TestCase):
    """O botao de modelo tem que ser legivel com QUALQUER modelo escolhido.

    Bug real: a ancora era o icone "D" da Digen mais `has-text('RM')` e
    `'Real Motion'` — tudo especifico da casa. Trocar para Kling funcionava, e
    entao a conferencia lia None e derrubava o job com "ficou em None". A
    conferencia estava certa; a lista e que so enxergava um fabricante.
    """

    def setUp(self):
        from builds.identity import selectors
        self.sel = selectors

    def test_toda_familia_conhecida_tem_como_ser_lida(self):
        alvos = " ".join(v for _, v in self.sel.BOTAO_MODELO)
        for modelo in self.sel.MODELOS_CONHECIDOS:
            mostrado = self.sel.abreviar_modelo(modelo)
            with self.subTest(modelo=modelo):
                self.assertTrue(
                    any(f.lower() in mostrado.lower()
                        for f in self.sel.FAMILIAS_DE_MODELO),
                    f"{mostrado} nao cai em nenhuma familia")
                self.assertTrue(
                    any(f in alvos for f in self.sel.FAMILIAS_DE_MODELO
                        if f.lower() in mostrado.lower()),
                    f"nenhum candidato do BOTAO_MODELO leria {mostrado}")

    def test_o_modelo_de_referencia_e_legivel(self):
        """Vale so quando ha troca configurada; hoje nao ha (image-to-video e pago)."""
        from builds.identity import config
        nome = (config.settings().get("referencias") or {}).get("modelo")
        if not nome:
            self.skipTest("sem troca de modelo configurada")
        mostrado = self.sel.abreviar_modelo(nome)
        alvos = " ".join(v for _, v in self.sel.BOTAO_MODELO)
        self.assertTrue(any(f in alvos for f in self.sel.FAMILIAS_DE_MODELO
                            if f.lower() in mostrado.lower()),
                        f"o botao ficaria ilegivel com {mostrado}")

    def test_o_icone_da_casa_continua_sendo_a_primeira_ancora(self):
        """Mais preciso que texto quando o modelo E da casa."""
        self.assertIn(self.sel.ICONE_MODELO, self.sel.BOTAO_MODELO[0][1])


class NomeDeModeloTests(unittest.TestCase):
    """O menu diz "Kling 3.0" e o botao mostra "Kling3.0".

    Comparar literal fazia a conferencia reprovar uma troca que DEU CERTO: o
    modelo ja estava correto na tela e o job caia dizendo que nao estava.
    """

    def setUp(self):
        from builds.identity.client import DigenClient
        self.mesmo = DigenClient._mesmo_modelo

    def test_espaco_nao_faz_diferenca(self):
        self.assertTrue(self.mesmo("Kling3.0", "Kling 3.0"))
        self.assertTrue(self.mesmo("Runway Gen-4.5", "RunwayGen-4.5"))
        self.assertTrue(self.mesmo("RM3.5", "RM 3.5"))

    def test_caixa_nao_faz_diferenca(self):
        self.assertTrue(self.mesmo("kling3.0", "Kling 3.0"))

    def test_modelo_diferente_continua_diferente(self):
        """Tolerar espaco nao pode virar tolerar modelo errado."""
        self.assertFalse(self.mesmo("Kling 3.0", "Kling 2.0"))
        self.assertFalse(self.mesmo("RM3.5", "RM3.1"))
        self.assertFalse(self.mesmo("Real Motion 3.5 Turbo", "Real Motion 3.5"))

    def test_ausencia_nunca_e_igualdade(self):
        self.assertFalse(self.mesmo(None, "Kling 3.0"))
        self.assertFalse(self.mesmo("Kling 3.0", None))


class FolhaDeReferenciaTests(unittest.TestCase):
    """Uma imagem so, com as duas identidades dentro.

    O composer aceita um arquivo e a segunda entrega substitui a primeira —
    entao levar personagem E arma exige compor as duas antes de subir.
    """

    def setUp(self):
        from builds.identity import referencias
        self.referencias = referencias
        self._tmp = tempfile.TemporaryDirectory()
        self._outputs = icfg.OUTPUTS
        icfg.OUTPUTS = Path(self._tmp.name) / "outputs"
        (icfg.OUTPUTS / GID).mkdir(parents=True)

    def tearDown(self):
        icfg.OUTPUTS = self._outputs
        self._tmp.cleanup()

    def _imagem(self, slot, cor):
        Image.new("RGB", (544, 960), cor).save(
            icfg.OUTPUTS / GID / slots.ARQUIVO[slot])

    def test_com_as_duas_imagens_nasce_a_folha(self):
        self._imagem(slots.CHARACTER, (10, 60, 120))
        self._imagem(slots.WEAPON, (140, 20, 90))
        folha = self.referencias.folha_de_referencia(GID)
        self.assertIsNotNone(folha)
        with Image.open(folha) as img:
            self.assertEqual((544, 960), img.size,
                             "a folha tem que manter o enquadramento 9:16")
            # o canto de baixo a direita deixou de ser o fundo do personagem
            self.assertNotEqual((10, 60, 120), img.getpixel((470, 880)))
            # e o topo continua sendo o personagem
            self.assertEqual((10, 60, 120), img.getpixel((272, 200)))

    def test_com_uma_imagem_so_nao_ha_folha(self):
        """Sem as duas, quem chama usa a que existe e descreve a outra."""
        self._imagem(slots.CHARACTER, (10, 60, 120))
        self.assertIsNone(self.referencias.folha_de_referencia(GID))

    def test_a_folha_e_reconhecida_como_das_duas(self):
        """Ela nao mapeia para um slot: representa os dois."""
        self._imagem(slots.CHARACTER, (10, 60, 120))
        self._imagem(slots.WEAPON, (140, 20, 90))
        folha = self.referencias.folha_de_referencia(GID)
        self.assertIsNone(self.referencias.slot_do_arquivo(folha),
                          "a folha nao pode ser confundida com um slot so")

    def test_folha_quebrada_nao_derruba_o_payoff(self):
        self._imagem(slots.CHARACTER, (10, 60, 120))
        (icfg.OUTPUTS / GID / slots.ARQUIVO[slots.WEAPON]).write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"lixo" * 400)
        self.assertIsNone(self.referencias.folha_de_referencia(GID))


class CaminhoDeAnexoPorProvedorTests(unittest.TestCase):
    """Cada site anexa de um jeito, e esperar pelo do outro custa tempo.

    Digen: menu "+" -> "Upload Image" -> dialogo nativo (o input escondido de
    la nao registra nada). PicassoIA: zona de arraste que E um input de
    verdade, sem menu. Sem distinguir, cada imagem do PicassoIA pagava o
    timeout inteiro do dialogo antes de cair no caminho certo.
    """

    def test_digen_declara_menu_de_anexo(self):
        from builds.identity import selectors
        self.assertTrue(selectors.BOTAO_ANEXO)
        self.assertTrue(selectors.OPCAO_ENVIAR_IMAGEM)

    def test_picasso_declara_botao_direto_sem_menu(self):
        """Desde 26/08/2026 o Editor Pro tem botao "Carregar imagem" que abre
        o seletor de arquivo DIRETO: BOTAO_ANEXO declarado, OPCAO (menu)
        vazia de proposito — clicar no botao encerra o caminho."""
        from builds.identity import picasso_selectors
        self.assertTrue(picasso_selectors.BOTAO_ANEXO)
        self.assertEqual([], picasso_selectors.OPCAO_ENVIAR_IMAGEM)

    def test_sem_menu_nao_espera_dialogo(self):
        """A guarda: lista vazia significa "va direto ao input"."""
        import inspect
        from builds.identity import referencias
        fonte = inspect.getsource(referencias.anexar)
        self.assertIn("BOTAO_ANEXO", fonte)
        self.assertIn("tem_menu", fonte)

    def test_o_editor_recebe_as_duas_e_o_digen_uma(self):
        """Os tetos vem do que cada site aceita, nao de precaucao."""
        import inspect
        from builds.identity.client import DigenClient
        from builds.identity.picasso_client import PicassoClient
        self.assertIn("maximo=len(prontos)",
                      inspect.getsource(PicassoClient.anexar_referencias))
        # o Digen usa o default (1), documentado como observacao de tela
        self.assertNotIn("maximo=",
                         inspect.getsource(DigenClient.anexar_referencias))


class DuplicataTests(unittest.TestCase):
    """O provedor pode devolver o artefato de OUTRO slot.

    Aconteceu em generation_00022: a imagem do personagem carregou no
    historico da conta DEPOIS da foto de referencia, o job da arma a viu como
    nova, ela era retrato como qualquer outra e passou por todas as guardas de
    tela. So comparar o conteudo pega isso — e a arma tinha sido gravada como
    copia byte a byte do personagem, contaminando a juncao e o video.
    """

    def setUp(self):
        from builds.identity import artefato
        self.artefato = artefato
        self._tmp = tempfile.TemporaryDirectory()
        self._outputs = icfg.OUTPUTS
        icfg.OUTPUTS = Path(self._tmp.name) / "outputs"
        (icfg.OUTPUTS / GID).mkdir(parents=True)

    def tearDown(self):
        icfg.OUTPUTS = self._outputs
        self._tmp.cleanup()

    def _caminho(self, slot):
        return icfg.OUTPUTS / GID / slots.ARQUIVO[slot]

    def test_arquivo_identico_ao_de_outro_slot_e_apontado(self):
        Image.new("RGB", (400, 700), (10, 90, 40)).save(
            self._caminho(slots.CHARACTER))
        conteudo = self._caminho(slots.CHARACTER).read_bytes()
        self._caminho(slots.WEAPON).write_bytes(conteudo)
        self.assertEqual(
            slots.CHARACTER,
            self.artefato.duplicado_de(self._caminho(slots.WEAPON), GID,
                                       slots.WEAPON))

    def test_arquivos_diferentes_passam(self):
        Image.new("RGB", (400, 700), (10, 90, 40)).save(
            self._caminho(slots.CHARACTER))
        Image.new("RGB", (400, 700), (200, 20, 60)).save(
            self._caminho(slots.WEAPON))
        self.assertIsNone(
            self.artefato.duplicado_de(self._caminho(slots.WEAPON), GID,
                                       slots.WEAPON))

    def test_ele_nao_se_acusa(self):
        Image.new("RGB", (400, 700), (10, 90, 40)).save(
            self._caminho(slots.CHARACTER))
        self.assertIsNone(
            self.artefato.duplicado_de(self._caminho(slots.CHARACTER), GID,
                                       slots.CHARACTER))

    def test_o_worker_descarta_e_falha_em_vez_de_aceitar(self):
        import inspect
        from builds.identity import worker
        fonte = inspect.getsource(worker.processar)
        self.assertIn("duplicado_de", fonte)
        self.assertIn("unlink", fonte, "o arquivo errado tem que sair do disco")


class LeituraDeControleTests(unittest.TestCase):
    """O que o pill MOSTRA nem sempre e como o catalogo ESCREVE.

    O botao de resolucao mostra "720p" e o catalogo tem "720P". A comparacao
    literal devolvia None, o codigo concluia "controle nao encontrado" e a
    resolucao NUNCA era ajustada — o site rebaixava calado para o teto do
    modelo. Mesmo defeito do "Kling3.0" contra "Kling 3.0".
    """

    def setUp(self):
        from builds.identity import selectors
        from builds.identity.client import DigenClient
        self.sel = selectors
        self.canonico = DigenClient._canonico

    def test_caixa_diferente_ainda_e_o_mesmo_valor(self):
        self.assertEqual("720P", self.canonico("720p", self.sel.RESOLUCOES_CONHECIDAS))
        self.assertEqual("480P", self.canonico("480P", self.sel.RESOLUCOES_CONHECIDAS))
        self.assertEqual("5s", self.canonico("5S", self.sel.DURACOES_CONHECIDAS))

    def test_espaco_em_volta_nao_atrapalha(self):
        self.assertEqual("540P", self.canonico(" 540P ", self.sel.RESOLUCOES_CONHECIDAS))

    def test_valor_de_fora_do_catalogo_continua_None(self):
        """Tolerar caixa nao pode virar aceitar qualquer coisa."""
        self.assertIsNone(self.canonico("Auto", self.sel.RESOLUCOES_CONHECIDAS))
        self.assertIsNone(self.canonico("", self.sel.RESOLUCOES_CONHECIDAS))
        self.assertIsNone(self.canonico("12s", self.sel.DURACOES_CONHECIDAS[:3]))


class TempoDoPayoffTests(unittest.TestCase):
    """O payoff e o unico clipe da build: ele merece o maior tempo possivel."""

    def setUp(self):
        from builds.generation.session_generator import load_config
        self.identidade = icfg.settings()
        self.edicao = load_config("editing.json")

    def test_o_payoff_pede_o_maior_tempo_do_modelo(self):
        """Lista comecando em '5s' entregava 5s com 8s disponivel."""
        from builds.identity import selectors
        pedido = self.identidade["duracao_por_slot"][slots.CHARACTER_WEAPON]
        self.assertEqual(selectors.MAXIMO, pedido[0],
                         "a primeira preferencia ganha; `max` tem que vir antes")

    def test_a_janela_da_montagem_cabe_o_clipe_inteiro(self):
        """Pedir 8s e cortar em 6s joga fora dois segundos gerados."""
        from builds.identity import selectors
        janela = self.edicao["identity_slots"][slots.CHARACTER_WEAPON]
        maior = max(selectors.valor_numerico(d) or 0
                    for d in selectors.DURACOES_CONHECIDAS[:3])
        self.assertGreaterEqual(janela["max"], maior,
                                "a janela corta antes do clipe acabar")


class RodapeTests(unittest.TestCase):
    """O Editor Pro carimba texto no rodape mesmo com "no text" no prompt.

    Verificado em generation_00022: a imagem do personagem tinha o rodape
    limpo e a COMPOSTA veio com "FEKRAN | OK T ... /DigMor". Como ela vira
    video, o carimbo iria junto — e pedir e torcer nao e verificacao.
    """

    def setUp(self):
        from builds.identity import referencias
        self.referencias = referencias
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def _com_carimbo(self) -> Path:
        from PIL import ImageDraw
        caminho = Path(self._tmp.name) / "ref.png"
        img = Image.new("RGB", (544, 960), (20, 60, 30))
        desenho = ImageDraw.Draw(img)
        desenho.rectangle([0, 920, 544, 960], fill=(240, 240, 240))
        img.save(caminho)
        return caminho

    def test_o_tamanho_e_a_proporcao_sobrevivem(self):
        """Cortar so embaixo e esticar deformaria o personagem."""
        caminho = self._com_carimbo()
        self.referencias.aparar_rodape(caminho)
        with Image.open(caminho) as img:
            self.assertEqual((544, 960), img.size)

    def test_a_faixa_de_baixo_some(self):
        caminho = self._com_carimbo()
        with Image.open(caminho) as antes:
            self.assertEqual((240, 240, 240), antes.getpixel((272, 940)))
        self.referencias.aparar_rodape(caminho)
        with Image.open(caminho) as depois:
            self.assertNotEqual((240, 240, 240), depois.getpixel((272, 940)))

    def test_arquivo_ilegivel_nao_derruba_nada(self):
        ruim = Path(self._tmp.name) / "ruim.png"
        ruim.write_bytes(b"\x89PNG\r\n\x1a\n" + b"lixo" * 100)
        self.assertEqual(ruim, self.referencias.aparar_rodape(ruim))

    def test_so_a_imagem_COMPOSTA_e_aparada(self):
        """As imagens de origem vem limpas; aparar todas seria perda a toa."""
        import inspect
        from builds.identity import worker
        fonte = inspect.getsource(worker.processar)
        self.assertIn("slot == slots.REFERENCIA", fonte)
        self.assertIn("aparar_rodape", fonte)


class BotaoTapadoTests(unittest.TestCase):
    """A barra flutuante do rodape fica POR CIMA do botao de baixar.

    Sintoma no log: "subtree intercepts pointer events" numa div z-30 com
    `pointer-events` — a barra do RealDance / Lip Gen. Com imagem anexada e
    texto escrito o composer cresce e empurra tudo, e forcar o clique so
    acerta a barra. A sequencia que funciona (observada na tela) e esvaziar o
    composer, rolar um pouco e so entao mirar no card.
    """

    def test_o_cliente_esvazia_antes_de_baixar(self):
        import inspect
        from builds.identity.client import DigenClient
        fonte = inspect.getsource(DigenClient._liberar_botao_de_download)
        self.assertIn("esvaziar_composer", fonte)
        self.assertIn("_limpar_composer", fonte, "o texto tambem empurra a caixa")
        self.assertIn("wheel", fonte, "rolar faz parte da sequencia")
        self.assertIn("hover_no_card", fonte)

    def test_a_ordem_importa(self):
        """Passar o mouse antes de esvaziar mira num alvo que ainda esta coberto."""
        import inspect
        from builds.identity.client import DigenClient
        fonte = inspect.getsource(DigenClient._liberar_botao_de_download)
        self.assertLess(fonte.index("esvaziar_composer"),
                        fonte.index("hover_no_card"))

    def test_baixar_chama_a_liberacao_primeiro(self):
        import inspect
        from builds.identity.client import DigenClient
        fonte = inspect.getsource(DigenClient.download)
        self.assertLess(fonte.index("_liberar_botao_de_download"),
                        fonte.index("botao_download"))

    def test_esvaziar_nao_levanta_com_pagina_quebrada(self):
        from builds.identity import selectors

        class _Quebrada:
            def evaluate(self, *a, **k):
                raise RuntimeError("target closed")
        self.assertEqual(0, selectors.esvaziar_composer(_Quebrada()))
