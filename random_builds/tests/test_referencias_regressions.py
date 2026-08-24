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
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image                                              # noqa: E402

from src.identity import artefato                                  # noqa: E402
from src.identity import config as icfg                            # noqa: E402
from src.identity import queue as fila                             # noqa: E402
from src.identity import slots                                     # noqa: E402

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
        for slot in slots.SLOTS:
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

    def test_o_payoff_espera_as_duas_imagens(self):
        self._enfileirar()
        pegos = self._drenar()
        self.assertIn(slots.CHARACTER, pegos)
        self.assertIn(slots.WEAPON, pegos)
        self.assertNotIn(slots.CHARACTER_WEAPON, pegos,
                         "o payoff saiu antes das imagens existirem")

    def test_uma_imagem_so_ainda_segura_o_payoff(self):
        self._enfileirar()
        self._imagem(slots.CHARACTER)
        self.assertNotIn(slots.CHARACTER_WEAPON, self._drenar())

    def test_com_as_duas_imagens_o_payoff_libera(self):
        self._enfileirar()
        for slot in (slots.CHARACTER, slots.WEAPON):
            self._imagem(slot)
        self.assertIn(slots.CHARACTER_WEAPON, self._drenar())

    def test_disco_manda_mais_que_a_fila(self):
        """`identity queue --limpar` apaga as linhas `done`.

        Se a prova de que a imagem existe fosse a linha da fila, uma limpeza de
        rotina deixaria o payoff pendente para sempre.
        """
        self._enfileirar()
        for slot in (slots.CHARACTER, slots.WEAPON):
            self._imagem(slot)
            fila.concluir(slots.job_id(GID, slot), "x.png")
        self.assertEqual(2, fila.limpar_concluidos())
        self.assertIn(slots.CHARACTER_WEAPON, self._drenar())

    def test_prazo_vencido_degrada_para_texto(self):
        """Sem imagem nenhuma, vencido o prazo o payoff sai assim mesmo."""
        self._enfileirar(prazo=PASSADO)
        self.assertIn(slots.CHARACTER_WEAPON, self._drenar())

    def test_dependencia_que_falhou_nao_mata_o_payoff(self):
        self._enfileirar()
        for slot in (slots.CHARACTER, slots.WEAPON):
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
        pendentes = [j for j in fila.listar() if j["status"] == fila.PENDENTE]
        self.assertEqual([slots.CHARACTER_WEAPON], [j["slot"] for j in pendentes])
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
        self.assertEqual(sorted(slots.job_id(GID, s)
                                for s in (slots.CHARACTER, slots.WEAPON)),
                         sorted(linha["depends_on"]))
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
        self.assertEqual([slots.job_id(GID, s)
                          for s in (slots.CHARACTER, slots.WEAPON)],
                         linha["depends_on"])


class _LocatorFake:
    """Locator de mentira: N elementos, e um `set_input_files` controlavel."""

    def __init__(self, quantidade: int = 1, aceita_varios: bool = True):
        self.quantidade = quantidade
        self.aceita_varios = aceita_varios
        self.recebidos: list[list[str]] = []

    def count(self):
        return self.quantidade

    def nth(self, indice):
        return self

    def set_input_files(self, arquivos):
        if not self.aceita_varios and len(arquivos) > 1:
            raise ValueError("non-multiple input can only accept single file")
        self.recebidos.append(list(arquivos))


class _PaginaComInput:
    def __init__(self, entrada):
        self.entrada = entrada

    def locator(self, seletor):
        if "file" in seletor:
            return self.entrada
        return _LocatorFake(quantidade=0)


class AnexoTests(unittest.TestCase):
    """O anexo nunca levanta: ele devolve o que conseguiu."""

    def setUp(self):
        from src.identity import referencias, selectors
        self.referencias = referencias
        self.sel = selectors
        self._tmp = tempfile.TemporaryDirectory()
        self.imagens = []
        for nome in ("character_image.png", "weapon_image.png"):
            destino = Path(self._tmp.name) / nome
            Image.new("RGB", (600, 1064), (30, 30, 60)).save(destino)
            self.imagens.append(destino)

    def tearDown(self):
        self._tmp.cleanup()

    def test_usa_o_input_escondido_sem_clicar_em_nada(self):
        """O caminho mais curto: nada de popover, timing nem idioma."""
        entrada = _LocatorFake()
        anexadas = self.referencias.anexar(
            _PaginaComInput(entrada), self.imagens, self.sel)
        self.assertEqual(self.imagens, anexadas)
        self.assertEqual([[str(c) for c in self.imagens]], entrada.recebidos)

    def test_formulario_de_um_arquivo_so_anexa_o_primeiro(self):
        """Uma referencia e melhor que nenhuma - e a ordem poe o rosto na frente."""
        entrada = _LocatorFake(aceita_varios=False)
        anexadas = self.referencias.anexar(
            _PaginaComInput(entrada), self.imagens, self.sel)
        self.assertEqual([self.imagens[0]], anexadas)

    def test_sem_ponto_de_anexo_devolve_vazio_e_nao_levanta(self):
        """Hoje esse video sai. Falhar aqui seria trocar imperfeito por nada."""
        pagina = _PaginaComInput(_LocatorFake(quantidade=0))
        self.assertEqual([], self.referencias.anexar(pagina, self.imagens, self.sel))

    def test_pagina_que_explode_nao_derruba_a_geracao(self):
        class _PaginaQuebrada:
            def locator(self, seletor):
                raise RuntimeError("target closed")
        self.assertEqual([], self.referencias.anexar(
            _PaginaQuebrada(), self.imagens, self.sel))

    def test_sem_imagem_nenhuma_nem_tenta(self):
        entrada = _LocatorFake()
        self.assertEqual([], self.referencias.anexar(
            _PaginaComInput(entrada), [], self.sel))
        self.assertEqual([], entrada.recebidos)

    def test_imagem_dentro_do_teto_sobe_como_esta(self):
        original = self.imagens[0]
        self.assertEqual(original, self.referencias.para_upload(original))

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
            padrao = self.referencias.disponiveis(GID)
            self.assertEqual([slots.ARQUIVO[slots.CHARACTER],
                              slots.ARQUIVO[slots.WEAPON]],
                             [c.name for c in padrao])
            invertida = self.referencias.disponiveis(
                GID, ordem=[slots.WEAPON, slots.CHARACTER])
            self.assertEqual(slots.ARQUIVO[slots.WEAPON], invertida[0].name)
        finally:
            icfg.OUTPUTS = anterior

    def test_slot_de_video_nunca_entra_como_referencia(self):
        """O payoff nao pode ser referencia de si mesmo."""
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
        from src.identity import selectors
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
        self.assertTrue(any("Upload image" in v for v in alvos))

    def test_o_botao_de_anexo_prefere_a_ancora_mais_especifica(self):
        """Icone + data-slot primeiro; so o icone depois, como rede."""
        primeiro = self.sel.BOTAO_ANEXO[0][1]
        self.assertIn("popover-trigger", primeiro)
        self.assertIn(self.sel.ICONE_MAIS, primeiro)
