# -*- coding: utf-8 -*-
"""DUAS REFERENCIAS NUM INPUT SEM `multiple` (14/10/2026).

Visto pelo conferente no app ("IAs > Livre", Rodizio de imagem): pedido de
imagem com DUAS imagens de referencia falhava com

    falhou: Error: Locator.set_input_files: Error: Non-multiple file input
    can only accept single file

O `ClienteLLM.anexar` (historias/contos/llm/cliente.py), que o carteiro usa
para o ChatGPT, o Gemini, o DeepSeek e o Grok, mandava as duas de uma vez no
`input[type=file]`, e o do ChatGPT nao tem `multiple`. E a excecao crua ia
inteira para o app e para o Telegram.

O que este arquivo trava:
1. input SEM `multiple` + 2 arquivos -> dois `set_input_files`, um arquivo
   cada, e o segundo so depois de a miniatura do primeiro aparecer;
2. input COM `multiple` -> uma chamada so, com os dois;
3. `multiple` ilegivel -> tenta os dois, o site recusa, cai para um por vez;
4. o site fica so com o primeiro -> `AnexoRecusado` com a frase "o ChatGPT
   so aceitou 1 das 2 imagens de referencia" (e e ELA que chega ao app, sem
   o nome da classe na frente, pelo caminho real carteiro -> SessaoReal ->
   gerar_no_chat -> perguntar -> anexar);
5. erro tecnico do navegador -> frase simples no app/Telegram, a excecao
   crua so no log.

Sem navegador, sem conta, sem cota: a pagina e um duble com relogio falso.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from contos.llm import cliente as llm_cliente

from ias import carteiro as carteiro_mod, correio


class Error(Exception):
    """O mesmo nome e modulo da excecao do Playwright."""


Error.__module__ = "playwright._impl._errors"

NAO_MULTIPLO = ("Locator.set_input_files: Error: Non-multiple file input can "
                "only accept single file")


class _Relogio:
    """Substitui o `time` do cliente: dormir so anda o ponteiro."""

    def __init__(self):
        self.agora = 1000.0

    def monotonic(self):
        return self.agora

    def sleep(self, s):
        self.agora += float(s)


class _Entrada:
    """O `input[type=file]` do compositor."""

    def __init__(self, pagina):
        self.pagina = pagina

    def count(self):
        return 1

    @property
    def first(self):
        return self

    def evaluate(self, _js):
        if self.pagina.multiple_legivel is False:
            raise RuntimeError("elemento sem DOM legivel")
        return self.pagina.multiple

    def get_attribute(self, nome):
        if self.pagina.multiple_legivel is False:
            raise RuntimeError("elemento sem DOM legivel")
        return "" if (nome == "multiple" and self.pagina.multiple) else None

    def set_input_files(self, arquivos):
        self.pagina.receber(arquivos)


class _Nada:
    def count(self):
        return 0

    @property
    def first(self):
        return self


class _Miniaturas:
    def __init__(self, pagina):
        self.pagina = pagina

    def count(self):
        return self.pagina.miniaturas()


class _Compositor:
    """O compositor do ChatGPT: `multiple` como o site diz; cada arquivo
    aceito vira miniatura `atraso_s` depois; `aceita` limita quantos ficam."""

    def __init__(self, relogio, *, multiple, multiple_legivel=True, aceita=99,
                 atraso_s=1.5):
        self.relogio = relogio
        self.multiple, self.multiple_legivel = multiple, multiple_legivel
        self.aceita, self.atraso_s = aceita, atraso_s
        self.sel = llm_cliente.sel.do_provedor("chatgpt")
        self.chamadas: list = []          # (nomes, miniaturas na tela na hora)
        self._prontas: list = []          # instante em que cada miniatura sai
        self.url = "https://chatgpt.com/"

    def locator(self, seletor):
        if seletor in self.sel["anexo_input"]:
            return _Entrada(self)
        if seletor in self.sel["anexo_prova"]:
            return _Miniaturas(self)
        return _Nada()

    def evaluate(self, *_a, **_k):           # texto_visivel da SessaoReal
        return ""

    def receber(self, arquivos):
        lista = list(arquivos) if isinstance(arquivos, (list, tuple)) else [arquivos]
        self.chamadas.append(([Path(a).name for a in lista], self.miniaturas()))
        if len(lista) > 1 and not self.multiple:
            raise Error(NAO_MULTIPLO)
        for _ in lista:
            if len(self._prontas) < self.aceita:
                self._prontas.append(self.relogio.monotonic() + self.atraso_s)

    def miniaturas(self):
        return sum(1 for t in self._prontas if t <= self.relogio.monotonic())


class _ComRelogio(unittest.TestCase):
    def setUp(self):
        self.relogio = _Relogio()
        self.addCleanup(setattr, llm_cliente, "time", llm_cliente.time)
        llm_cliente.time = self.relogio
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._antes = os.environ.get("NF_IAS_PASTA")
        os.environ["NF_IAS_PASTA"] = str(Path(self._tmp.name) / "ias")
        self.addCleanup(self._restaurar)
        self.refs = []
        for nome in ("personagem.png", "arma.png"):
            caminho = Path(self._tmp.name) / nome
            caminho.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 64)
            self.refs.append(caminho)
        self.linhas: list = []

    def _restaurar(self):
        if self._antes is None:
            os.environ.pop("NF_IAS_PASTA", None)
        else:
            os.environ["NF_IAS_PASTA"] = self._antes

    def _cliente(self, pagina):
        return llm_cliente.ClienteLLM("chatgpt", None, pagina, log=self.linhas.append)


# ============================================================ o anexar
class AnexarUmPorVez(_ComRelogio):

    def test_input_sem_multiple_anexa_os_dois_em_sequencia(self):
        pagina = _Compositor(self.relogio, multiple=False)
        self.assertEqual(2, self._cliente(pagina).anexar(self.refs, espera=30.0))
        # duas chamadas, UM arquivo cada, na ordem
        self.assertEqual([n for n, _ in pagina.chamadas],
                         [["personagem.png"], ["arma.png"]])
        # o segundo so foi depois de a miniatura do primeiro aparecer
        self.assertEqual([m for _, m in pagina.chamadas], [0, 1])
        self.assertEqual(pagina.miniaturas(), 2)

    def test_input_com_multiple_e_uma_chamada_so(self):
        pagina = _Compositor(self.relogio, multiple=True)
        self.assertEqual(2, self._cliente(pagina).anexar(self.refs, espera=30.0))
        self.assertEqual([n for n, _ in pagina.chamadas],
                         [["personagem.png", "arma.png"]])

    def test_multiple_ilegivel_tenta_junto_e_cai_para_um_por_vez(self):
        pagina = _Compositor(self.relogio, multiple=False, multiple_legivel=False)
        self.assertEqual(2, self._cliente(pagina).anexar(self.refs, espera=30.0))
        self.assertEqual([n for n, _ in pagina.chamadas],
                         [["personagem.png", "arma.png"],      # recusada
                          ["personagem.png"], ["arma.png"]])
        self.assertEqual(pagina.miniaturas(), 2)

    def test_um_arquivo_continua_uma_chamada(self):
        pagina = _Compositor(self.relogio, multiple=False)
        self.assertEqual(1, self._cliente(pagina).anexar(self.refs[:1], espera=30.0))
        self.assertEqual([n for n, _ in pagina.chamadas], [["personagem.png"]])

    def test_site_que_so_fica_com_uma_falha_com_frase_simples(self):
        pagina = _Compositor(self.relogio, multiple=False, aceita=1)
        with self.assertRaises(llm_cliente.AnexoRecusado) as erro:
            self._cliente(pagina).anexar(self.refs, espera=30.0)
        self.assertEqual(str(erro.exception),
                         "o ChatGPT só aceitou 1 das 2 imagens de referência")
        # o detalhe (qual miniatura faltou) fica no log
        self.assertTrue(any("detalhe" in l and "miniatura do anexo 2" in l
                            for l in self.linhas), self.linhas)

    def test_input_multiple_que_fica_com_uma_tambem_falha(self):
        # antes: "sigo com o que subiu" — a imagem sairia sem a arma
        pagina = _Compositor(self.relogio, multiple=True, aceita=1)
        with self.assertRaises(llm_cliente.AnexoRecusado) as erro:
            self._cliente(pagina).anexar(self.refs, espera=30.0)
        self.assertIn("só aceitou 1 das 2", str(erro.exception))


# ======================================================= pelo carteiro
class _SessaoSemNavegar(carteiro_mod.SessaoReal):
    def novo_chat(self) -> None:                # sem navegar de verdade
        pass


@contextmanager
def _trava_livre(nome, esperar=0.0):
    yield True


class PeloCarteiro(_ComRelogio):
    """O caminho real do pedido com referencias: carteiro -> SessaoReal ->
    imagem.gerar_no_chat -> ClienteLLM.perguntar -> anexar."""

    def _carteiro(self, fabrica):
        avisos = []
        c = carteiro_mod.Carteiro(
            fabrica_de_sessao=fabrica, trava=_trava_livre,
            nome_da_trava=lambda ia: f"perfil__{ia}__teste", avisar=avisos.append,
            log=self.linhas.append, dormir=lambda s: None, de_servico=True,
            ajustes={"janela_conversa_s": 0, "resumo_a_cada": 50,
                     "espera_conta_max_s": 100})
        c.avisos = avisos
        return c

    def _fabrica_real(self, pagina):
        @contextmanager
        def _abrir(ia):
            cli = llm_cliente.ClienteLLM(ia, None, pagina, log=self.linhas.append)
            yield _SessaoSemNavegar(cli, log=self.linhas.append)
        return _abrir

    def test_chatgpt_que_recusa_a_segunda_chega_ao_app_em_portugues(self):
        pagina = _Compositor(self.relogio, multiple=False, aceita=1)
        c = self._carteiro(self._fabrica_real(pagina))
        correio.pedir_imagem("chatgpt", "o personagem segurando a arma",
                             proporcao="1:1", anexos=self.refs)
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "anexo")
        self.assertEqual(fim["erro"], "o ChatGPT só aceitou 1 das 2 imagens de referência")
        # e foi um por vez: nunca as duas juntas no input sem multiple
        self.assertEqual([n for n, _ in pagina.chamadas],
                         [["personagem.png"], ["arma.png"]])
        self.assertTrue(c.avisos)
        for aviso in c.avisos:
            self.assertNotIn("AnexoRecusado", aviso)
            self.assertNotIn("set_input_files", aviso)

    def test_erro_cru_do_navegador_vira_frase_e_o_detalhe_vai_ao_log(self):
        fabrica = carteiro_mod.fabrica_duble(imagem_falhar=Error(NAO_MULTIPLO))
        c = self._carteiro(fabrica)
        correio.pedir_imagem("chatgpt", "um gato", proporcao="1:1", anexos=self.refs)
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertNotIn("set_input_files", fim["erro"])
        self.assertNotIn("Non-multiple", fim["erro"])
        self.assertIn("o ChatGPT não aceitou o anexo", fim["erro"])
        for aviso in c.avisos:
            self.assertNotIn("set_input_files", aviso)
        self.assertTrue(any("detalhe técnico" in l and "Non-multiple" in l
                            for l in self.linhas), self.linhas)

    def test_classificar_erro_traduz_o_erro_do_playwright(self):
        for exc, esperado in (
                (Error(NAO_MULTIPLO), "não aceitou o anexo"),
                (Error("Timeout 30000ms exceeded."), "demorou demais"),
                (Error("Target page, context or browser has been closed"),
                 "fechou no meio do pedido"),
                (Error("algo que ninguem previu"), "erro inesperado no navegador")):
            categoria, motivo = carteiro_mod.classificar_erro("chatgpt", exc)
            self.assertIn(esperado, motivo)
            self.assertNotIn("Error:", motivo)
            self.assertTrue(carteiro_mod.detalhe_tecnico(exc).startswith("Error: "))

    def test_mensagem_nossa_continua_como_era(self):
        exc = llm_cliente.LLMFalhou("o prompt nao entrou no editor")
        self.assertEqual(carteiro_mod.detalhe_tecnico(exc), "")
        _, motivo = carteiro_mod.classificar_erro("chatgpt", exc)
        self.assertIn("o prompt nao entrou no editor", motivo)


if __name__ == "__main__":
    unittest.main()
