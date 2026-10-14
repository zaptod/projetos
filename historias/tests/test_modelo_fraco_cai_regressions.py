# -*- coding: utf-8 -*-
"""HIS-2 (alto): o Gemini fora do modelo forte NAO escreve o roteiro.

Decisao do Adrian no Grimorio, `historias/gemini-sem-pro-escreve` = "cair"
(13/10/2026, commit b339bbb): "Pular para o proximo provedor (DeepSeek/
ChatGPT) e avisar no Telegram. Nunca escreve no Flash; se nenhum provedor
forte estiver disponivel, a rodada espera."

Ate aqui o Gemini que nao entrava no Pro escrevia a historia inteira no
Flash, calado (224 vezes de 06 a 08/10), e pior: `_tentar_modelo` devolvia
"confirmado" quando caia no 2o da preferencia ("flash"), entao nem o
"NAO CONFIRMADO" do roteiro aparecia.

Sem navegador nem LLM: o Gemini e um `ClienteLLM` de verdade sobre uma pagina
dublada cujo menu so oferece "3.5 Flash"; o DeepSeek e um cliente enlatado.
OUTPUTS, o diario e o Telegram sao desviados.
"""
from __future__ import annotations

import contextlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from contos.llm import cliente as llm_cliente
from contos.llm import seletores
from contos.pipeline import agenda
from contos.roteiro import gerar as G
from contos.roteiro import roteiro as R

BIBLIA = ("TITULO DA SERIE: O vestido\nNOME DA SERIE: O Vestido\n"
          "PREMISSA: a irma pegou o vestido. Quem errou?\n"
          "PROTAGONISTA: Joao | a Brazilian man in his forties, bald\n"
          "NARRADOR: Homem, 41 anos\n"
          "CENARIO: a small apartment in Sao Paulo\n"
          "FATOS: idade = 41\n\nPARTE 1\nTITULO: O vestido\n"
          "RESUMO: r\nGANCHO: g\nCLIFFHANGER: c\n")
PARTE = "TITULO: O vestido (Parte 1)\n\n" + "\n\n".join(
    f"CENA {i}\nIMAGEM: a bald Brazilian man in a small kitchen, "
    f"moment {i}\nTEMPO: 4\nNARRACAO: Eu nunca achei que ia contar "
    f"isso, parte {i}." for i in (1, 2))


# ------------------------------------------------------------ pagina dublada
class _Elemento:
    def __init__(self, texto, ao_clicar=None):
        self.texto = texto
        self.ao_clicar = ao_clicar
        self.cliques = 0

    def is_visible(self):
        return True

    def inner_text(self, timeout=None):
        return self.texto

    def click(self, timeout=None):
        self.cliques += 1
        if self.ao_clicar:
            self.ao_clicar()


class _Lista:
    def __init__(self, elementos):
        self.elementos = list(elementos)

    def count(self):
        return len(self.elementos)

    def nth(self, i):
        return self.elementos[i]

    @property
    def first(self):
        return self.elementos[0]


class _Teclado:
    def press(self, _tecla):
        pass


class PaginaDoMenu:
    """O Gemini aberto: botao de modelo e um menu so com `opcoes`."""

    def __init__(self, atual="3.5 Flash", opcoes=("3.5 Flash",)):
        self.menu_aberto = False
        self.botao = _Elemento(atual, ao_clicar=self._abrir_menu)
        self.opcoes = [_Elemento(t) for t in opcoes]
        self.keyboard = _Teclado()
        self.sel = seletores.do_provedor("gemini")

    def _abrir_menu(self):
        self.menu_aberto = True

    def goto(self, *_a, **_k):
        self.menu_aberto = False

    def locator(self, seletor):
        if seletor in self.sel["modelo_botao"]:
            return _Lista([self.botao])
        if seletor in self.sel["modelo_opcao"]:
            return _Lista(self.opcoes if self.menu_aberto else [])
        return _Lista([])


def _gemini(pagina, papel="roteiro", ref="nova"):
    cli = llm_cliente.ClienteLLM("gemini", None, pagina, {},
                                 log=lambda *_a: None)
    cli._esperar_montar = lambda *a, **k: None
    cli.conferir_sessao = lambda: "logado"
    cli.diario = True
    cli.papel, cli.ref, cli.canal = papel, ref, "historias"
    return cli


class _DeepSeek:
    """O DeepSeek normal: forte, escreve a biblia e a parte."""
    provedor = "deepseek"
    modelo_atual, modelo_confirmado, modelo_forte = "DeepSeek (site)", True, True

    def __init__(self):
        self.perguntas = []

    def abrir(self, novo_chat=True):
        pass

    def perguntar(self, prompt, timeout=None):
        self.perguntas.append(prompt)
        return BIBLIA if len(self.perguntas) == 1 else PARTE


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pasta = Path(tmp.name)
        for modulo in (R, G, agenda):
            self.addCleanup(setattr, modulo, "OUTPUTS", modulo.OUTPUTS)
            modulo.OUTPUTS = self.pasta
        self.diario = []
        patcher = mock.patch.object(
            llm_cliente._rb_atividade, "registrar",
            lambda *a, **k: self.diario.append((a, k)))
        patcher.start()
        self.addCleanup(patcher.stop)
        for alvo in (mock.patch.object(llm_cliente, "_pausa",
                                       lambda *a, **k: None),):
            alvo.start()
            self.addCleanup(alvo.stop)
        llm_cliente._FALHA_DE_MODELO.clear()
        self.addCleanup(llm_cliente._FALHA_DE_MODELO.clear)
        self.deepseek = _DeepSeek()
        self.abertos = []

        def abrir_cliente(provedor, **k):
            self.abertos.append(provedor)
            if provedor == "gemini":
                return contextlib.nullcontext(
                    _gemini(PaginaDoMenu(), papel=k.get("papel", ""),
                            ref=k.get("ref", "")))
            return contextlib.nullcontext(self.deepseek)

        self.addCleanup(setattr, llm_cliente, "abrir_cliente",
                        llm_cliente.abrir_cliente)
        llm_cliente.abrir_cliente = abrir_cliente

    def _erros_de_modelo(self):
        return [(a, k) for (a, k) in self.diario
                if k.get("etapa") == "llm.modelo_fraco"]


class OClienteSabeQueEstaFraco(_Base):
    def test_cair_no_flash_NAO_e_modelo_forte(self):
        cli = _gemini(PaginaDoMenu(), papel="qualidade")
        cli.abrir()
        self.assertEqual("3.5 Flash", cli.modelo_atual)
        # o defeito antigo: "confirmado" porque a escolha terminou
        self.assertTrue(cli.modelo_confirmado)
        self.assertFalse(cli.modelo_forte)

    def test_conta_sem_o_pro_tambem_nao_e_forte(self):
        cli = _gemini(PaginaDoMenu(opcoes=("2.5 Pesquisa",)), papel="qualidade")
        cli.abrir()
        self.assertFalse(cli.modelo_forte)

    def test_no_pro_e_forte(self):
        cli = _gemini(PaginaDoMenu(opcoes=("3.5 Flash", "3.1 Pro")))
        cli.abrir()                                   # papel roteiro: nao levanta
        self.assertTrue(cli.modelo_forte)
        self.assertEqual([], self._erros_de_modelo())

    def test_deepseek_e_site_sem_menu_sao_fortes(self):
        cli = llm_cliente.ClienteLLM.__new__(llm_cliente.ClienteLLM)
        cli.provedor, cli.log = "deepseek", (lambda *_a: None)
        cli.sel = seletores.do_provedor("deepseek")
        cli._ajustar_raciocinio = lambda: cli.RACIOCINIO_DA_CONTA
        cli.escolher_modelo()
        self.assertTrue(cli.modelo_forte)
        cli.provedor, cli.sel = "chatgpt", seletores.do_provedor("chatgpt")
        cli._preferido_do_config = lambda: None
        cli.escolher_modelo()
        self.assertTrue(cli.modelo_forte)

    def test_roteiro_levanta_e_vai_ao_diario_como_erro(self):
        cli = _gemini(PaginaDoMenu(), papel="roteiro", ref="historia_00009")
        with self.assertRaises(llm_cliente.ModeloFraco):
            cli.abrir()
        ((args, kwargs),) = self._erros_de_modelo()
        self.assertEqual(("gemini", "erro"), args[:2])
        self.assertIn("modelo forte", args[2])
        self.assertEqual("historia_00009", kwargs["ref"])
        self.assertTrue(issubclass(llm_cliente.ModeloFraco,
                                   llm_cliente.LLMFalhou))

    def test_outros_papeis_so_avisam(self):
        cli = _gemini(PaginaDoMenu(), papel="qualidade")
        cli.abrir()
        ((args, _k),) = self._erros_de_modelo()
        self.assertEqual("aviso", args[1])


class AQuedaPassaAoProximo(_Base):
    def test_gemini_fraco_cai_e_o_deepseek_escreve(self):
        feito = G.escrever_serie(["gemini", "deepseek"], partes=1,
                                 cenas_por_parte=2, tipo="babaca",
                                 log=lambda *_a: None)
        self.assertEqual(["gemini", "deepseek"], self.abertos)
        roteiro = R.carregar(feito["historia_id"])
        self.assertEqual("deepseek", roteiro["provedor"])
        self.assertEqual({"deepseek"},
                         {p["provedor"] for p in roteiro["partes"]})
        self.assertEqual("gemini", roteiro["quedas"][0]["provedor"])
        self.assertIn("ModeloFraco", roteiro["quedas"][0]["erro"])
        self.assertEqual(1, len(self._erros_de_modelo()))
        self.assertEqual("erro", self._erros_de_modelo()[0][0][1])

    def test_so_com_o_gemini_levanta_e_nao_grava_roteiro(self):
        with self.assertRaises(llm_cliente.ModeloFraco):
            G.escrever_serie(["gemini"], partes=1, cenas_por_parte=2,
                             tipo="babaca", log=lambda *_a: None)
        self.assertEqual([], list(self.pasta.glob("historia_*/roteiro.json")))
        self.assertEqual([], self.deepseek.perguntas)


class ARodadaEspera(_Base):
    """Passo 4: o ultimo provedor caiu por modelo fraco -> a rodada nao
    escreve, nao vira "roteiro falhou" a cada disparo, e o Telegram ouve UMA
    vez por dia."""

    def test_espera_e_avisa_uma_vez_por_dia(self):
        avisos = []
        self.addCleanup(setattr, agenda, "avisar", agenda.avisar)
        agenda.avisar = lambda texto, log=print: avisos.append(texto) or True
        exc = llm_cliente.ModeloFraco("o gemini nao entrou no modelo forte")
        self.assertTrue(agenda._e_modelo_fraco(exc))
        self.assertFalse(agenda._e_modelo_fraco(G.GeracaoFalhou("x")))
        primeiro = agenda._sem_modelo_forte(exc, {}, lambda *_a: None)
        segundo = agenda._sem_modelo_forte(exc, {}, lambda *_a: None)
        self.assertEqual(agenda.SEM_MODELO_FORTE, primeiro["motivo"])
        self.assertEqual("nada", segundo["feito"])
        self.assertEqual(1, len(avisos))
        self.assertIn("modelo forte", avisos[0])
        # o passo nao vira mensagem de falha nem `erro` da rodada
        self.assertIsNone(agenda.mensagem(primeiro, 10.0))
        registrados = []
        self.addCleanup(setattr, agenda, "_registrar_erro",
                        agenda._registrar_erro)
        agenda._registrar_erro = registrados.append
        agenda._fechar_passo(primeiro, 1.0, {"avisar_telegram": False})
        self.assertEqual([], registrados)

    def test_controller_fecha_o_inicio_com_aviso_e_nao_erro(self):
        from contos.pipeline import controller
        registros = []
        patcher = mock.patch.object(
            controller._rb_atividade, "registrar",
            lambda *a, **k: registros.append((a, k)))
        patcher.start()
        self.addCleanup(patcher.stop)

        def escrever(*_a, **_k):
            raise llm_cliente.ModeloFraco("o gemini nao entrou no modelo forte")

        self.addCleanup(setattr, G, "escrever_serie", G.escrever_serie)
        G.escrever_serie = escrever
        pipeline = controller.Pipeline.__new__(controller.Pipeline)
        pipeline.roteiro_config = {}
        with self.assertRaises(llm_cliente.ModeloFraco):
            pipeline.gerar(provedores=["gemini"], log=lambda *_a: None)
        status = [a[1] for (a, k) in registros if k.get("etapa") == "roteiro"]
        self.assertNotIn("erro", status)


if __name__ == "__main__":
    unittest.main()
