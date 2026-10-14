# -*- coding: utf-8 -*-
"""HIS-3 (alto): num chat com turnos, a resposta ANTERIOR nao volta como nova.

Auditoria de 11/10/2026: `_envio_devolvido` desistia se havia QUALQUER turno
do usuario na tela, e `_resposta_nova` aceitava o texto "ancorado" depois do
ULTIMO turno do usuario sem conferir que ele era o prompt de agora. Se o site
devolvia a pergunta para a caixa SEM criar turno (o "Algo deu errado" do
Gemini, 14/09), a resposta da parte N voltava como a da parte N+1 — em ~12 s —
e a parte duplicada virava video. E a mesma familia do `.nth(total-1)` de
10/09 (memoria "gemini-resposta-anterior-multiplasturnos").

Sem navegador: uma pagina dublada do Gemini com a conversa (turnos do usuario
e respostas na ordem do documento), a caixa de texto e o botao de enviar. O
cliente e o `ClienteLLM` de verdade, com `enviar` e `esperar_resposta` reais.
"""
from __future__ import annotations

import time
import unittest
from unittest import mock

from contos.llm import cliente as llm_cliente
from contos.llm import seletores

RESPOSTA_ANTERIOR = ("CENA 1\nNARRACAO: a parte 1 inteira. " * 60)[:1842]
PROMPT_ANTERIOR = ("ETAPA 2 - escreva agora a PARTE 1 de 6, e SO ela. Siga a "
                   "biblia e o formato combinado.")
PROMPT = ("ETAPA 2 - escreva agora a PARTE 2 de 6, e SO ela. Siga a biblia e "
          "o formato combinado.")
RESPOSTA_NOVA = "CENA 1\nNARRACAO: a parte 2, nova. " * 20


class _Elemento:
    def __init__(self, conversa, papel, indice=0):
        self.conversa, self.papel, self.indice = conversa, papel, indice

    def is_visible(self):
        return True

    def inner_text(self, timeout=None):
        if self.papel == "usuario":
            return self.conversa.usuarios[self.indice]
        return ""

    # o campo
    def input_value(self):
        return self.conversa.ler_caixa()

    def click(self, timeout=None):
        if self.papel == "enviar":
            self.conversa.enviou()

    def fill(self, texto):
        self.conversa.caixa = texto

    def evaluate(self, _js):
        return True                         # `_aceita_fill`: e editavel


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
    def __init__(self, conversa):
        self.conversa = conversa

    def press(self, tecla):
        if tecla in ("Delete", "Backspace"):
            self.conversa.caixa = ""

    def insert_text(self, texto):
        self.conversa.caixa = texto


class ConversaDoGemini:
    """A pagina: `usuarios` e `respostas` alternam na ordem do documento
    (u1, r1, u2, r2...). `como` decide o que o clique em enviar faz:

      "devolvido"   o campo esvazia (o envio "confirma"), nenhum turno nasce,
                    e o prompt VOLTA para a caixa logo depois;
      "normal"      nasce o turno nosso e, depois, a resposta nova;
      "descarrega"  nasce o nosso turno e a pagina descarrega o turno mais
                    velho (a contagem nao sobe): o texto do turno prova.
    """

    def __init__(self, como: str):
        self.como = como
        self.usuarios = [PROMPT_ANTERIOR]
        self.respostas = [RESPOSTA_ANTERIOR]
        self.caixa = ""
        self.volta = ""
        self.sel = seletores.do_provedor("gemini")
        self.campo = _Elemento(self, "campo")
        self.botao = _Elemento(self, "enviar")
        self.keyboard = _Teclado(self)

    def enviou(self):
        prompt, self.caixa = self.caixa, ""
        if self.como == "devolvido":
            self.volta = prompt              # volta na proxima leitura
            return
        self.usuarios.append(prompt)
        self.respostas.append(RESPOSTA_NOVA)
        if self.como == "descarrega":
            self.usuarios.pop(0)
            self.respostas.pop(0)

    def ler_caixa(self):
        texto = self.caixa
        if self.volta:                       # o "Algo deu errado" do Gemini
            self.caixa, self.volta = self.volta, ""
        return texto

    def locator(self, seletor):
        if seletor in self.sel["campo"]:
            return _Lista([self.campo])
        if seletor in self.sel["enviar"]:
            return _Lista([self.botao])
        if seletor in self.sel["turno_usuario"]:
            return _Lista(_Elemento(self, "usuario", i)
                          for i in range(len(self.usuarios)))
        return _Lista([])

    def evaluate(self, js, arg=None):
        if js == llm_cliente.ClienteLLM._JS_RESPOSTA:
            # a resposta que vem DEPOIS do ultimo turno do usuario
            texto = (self.respostas[-1]
                     if len(self.respostas) >= len(self.usuarios) else "")
            return {"texto": texto, "ancorado": True}
        if js == llm_cliente.ClienteLLM._JS_TODAS_AS_IMAGENS:
            return []
        if js == llm_cliente.ClienteLLM._JS_IMAGENS:
            return {"ancorado": True, "turno": "", "resposta": True,
                    "gerando": False, "imagens": [], "fora": 0}
        return None


class EnvioDevolvidoComTurnos(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(llm_cliente, "_pausa", lambda *a, **k: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _cliente(self, como: str):
        conversa = ConversaDoGemini(como)
        cli = llm_cliente.ClienteLLM(
            "gemini", None, conversa,
            {"devolvido_apos_s": 1.0, "pensar_ate": 300}, log=lambda *_a: None)
        cli.diagnosticos = []
        cli._diagnosticar_calado = lambda: cli.diagnosticos.append(1)
        # o chat ja tinha a parte 1: o cliente a leu no turno anterior
        cli._ultimo_prompt = PROMPT_ANTERIOR
        cli._ultima_resposta = RESPOSTA_ANTERIOR
        return cli, conversa

    def test_devolvido_levanta_em_vez_de_devolver_a_resposta_anterior(self):
        cli, conversa = self._cliente("devolvido")
        cli.enviar(PROMPT)
        self.assertEqual(PROMPT, conversa.ler_caixa())   # voltou para a caixa
        comeco = time.monotonic()
        with self.assertRaises(llm_cliente.LLMFalhou) as caso:
            cli.esperar_resposta(timeout=30, estabilidade=0.5)
        self.assertIn("nenhum turno novo", str(caso.exception))
        self.assertLess(time.monotonic() - comeco, 15)
        self.assertEqual([1], cli.diagnosticos)

    def test_com_o_turno_novo_devolve_a_resposta_nova(self):
        cli, _conversa = self._cliente("normal")
        cli.enviar(PROMPT)
        texto = cli.esperar_resposta(timeout=30, estabilidade=0.5)
        self.assertEqual(RESPOSTA_NOVA, texto)

    def test_pagina_que_descarrega_turno_velho_vale_pelo_texto(self):
        """A contagem nao subiu, mas o ultimo turno e, sem duvida, o prompt de
        agora: nao e devolvido (sem falso alarme)."""
        cli, _conversa = self._cliente("descarrega")
        cli.enviar(PROMPT)
        self.assertEqual(RESPOSTA_NOVA,
                         cli.esperar_resposta(timeout=30, estabilidade=0.5))

    def test_quem_espera_sem_enviar_segue_como_antes(self):
        """`esperar_resposta` sem `enviar` por este cliente (a sonda, testes
        antigos): nada a conferir, a espera e a de sempre."""
        cli, _conversa = self._cliente("devolvido")
        self.assertIsNone(cli._turnos_usuario_antes)
        self.assertEqual(RESPOSTA_ANTERIOR,
                         cli.esperar_resposta(timeout=30, estabilidade=0.5))

    def test_chat_novo_esquece_a_contagem(self):
        cli, conversa = self._cliente("normal")
        cli.enviar(PROMPT)
        self.assertEqual(1, cli._turnos_usuario_antes)
        conversa.goto = lambda *a, **k: None
        cli.sel = dict(cli.sel, url="https://x", url_novo_chat="https://x")
        cli._esperar_montar = lambda *a, **k: None
        cli.conferir_sessao = lambda: "logado"
        cli.escolher_modelo = lambda preferido=None: "3.1 Pro"
        cli.modelo_forte = True
        cli.abrir()
        self.assertIsNone(cli._turnos_usuario_antes)


if __name__ == "__main__":
    unittest.main()
