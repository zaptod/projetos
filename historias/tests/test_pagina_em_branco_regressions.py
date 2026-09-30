# -*- coding: utf-8 -*-
"""A PAGINA QUE NAO MONTOU NAO E LOGIN CAIDO (30/09/2026).

09:16, so leitura no perfil `grok__principal`: o grok.com abriu EM BRANCO
(titulo "Grok", nenhum elemento na tela, o app nao montou em 45 s, nenhum
HTTP >= 400; captura no scratchpad da tarefa 04c55648). As tres casas e a
pagina inicial, iguais.

Com a pagina assim, `ClienteLLM.abrir()` perguntava `logado()`: sem o campo
logado e sem a tela de login, a resposta era **True** — "nao vi a tela de
login, entao esta logado". O `None` (nao deu para olhar) virava True, a
abertura dizia "chat novo aberto", a troca de modelo tentava 3 vezes e o
envio morria depois em `SeletorNaoEncontrado` ("o site provavelmente mudou").
E quem lesse "a sessao nao esta valida" num caso vizinho refaria o login
de uma conta viva (memoria "Login do LLM: tres estados": `None` nunca vira
`False`).

Agora `estado_da_pagina()` tem cinco respostas, e `conferir_sessao()`:
  logado     -> segue
  deslogado  -> `NaoLogado`, SO com a tela de login visivel (prova positiva)
  em_branco  -> `SiteIndisponivel` (pausa o rodizio, como o "Alta procura"),
                com a tela salva
  barrado    -> `SiteIndisponivel` (o desafio anti-bot: "Um momento...")
  nao_sei    -> segue como antes (pagina com conteudo que nao reconheco: se o
                site mudou, o envio diz qual seletor faltou)

Dubles: a pagina responde ao que se pergunta; nenhum navegador, relogio falso.
"""
from __future__ import annotations

import shutil
import tempfile
import types
import unittest
from pathlib import Path

from contos.llm import cliente as llm_cliente                      # noqa: E402
from contos.llm import seletores                                   # noqa: E402

CHEIA = ("Pergunte qualquer coisa · Histórico · Ontem · Círculo de cor vermelha · "
         "Gato laranja dormindo · Configurações · Ajuda · Projetos · Imagine")


class _Pagina:
    """`visiveis`: quais listas de seletor do provedor estao na tela."""

    def __init__(self, visiveis=(), titulo="Grok", texto="", quebrada=False,
                 foto_falha=False):
        self.visiveis = set(visiveis)
        self.titulo = titulo
        self.texto = texto
        self.quebrada = quebrada
        self.foto_falha = foto_falha
        self.url = "about:blank"
        self.fotos = []

    def goto(self, url, **_k):
        self.url = url

    def title(self):
        if self.quebrada:
            raise RuntimeError("Target page, context or browser has been closed")
        return self.titulo

    def evaluate(self, script, *_a):
        if self.quebrada:
            raise RuntimeError("Target page, context or browser has been closed")
        if "innerText" in str(script):
            return self.texto
        return None

    def screenshot(self, path=None, **_k):
        if self.foto_falha:
            raise RuntimeError("screenshot falhou")
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n")
        self.fotos.append(path)


class _Base(unittest.TestCase):
    provedor = "grok"

    def setUp(self):
        self.agora = [0.0]

        def monotonic():
            self.agora[0] += 1.0
            return self.agora[0]

        falso = types.SimpleNamespace(monotonic=monotonic, sleep=lambda _s: None,
                                      strftime=__import__("time").strftime)
        self.addCleanup(setattr, llm_cliente, "time", llm_cliente.time)
        llm_cliente.time = falso
        self.addCleanup(setattr, seletores, "encontrar", seletores.encontrar)
        self.pasta = Path(tempfile.mkdtemp(prefix="em_branco_"))
        self.addCleanup(shutil.rmtree, self.pasta, True)
        # a tela salva NUNCA vai para outputs/ de producao num teste
        self.addCleanup(setattr, llm_cliente, "PASTA_EM_BRANCO",
                        llm_cliente.PASTA_EM_BRANCO)
        llm_cliente.PASTA_EM_BRANCO = self.pasta
        self.logs = []

    def _cliente(self, pagina, provedor=None):
        c = llm_cliente.ClienteLLM(provedor or self.provedor, None, pagina,
                                   log=self.logs.append)
        # `encontrar` responde pela LISTA pedida: visivel se ela e uma das
        # listas do provedor que a pagina diz ter na tela
        visiveis = [c.sel[k] for k in pagina.visiveis]
        seletores.encontrar = (lambda _p, candidatos, timeout=3.0:
                               object() if any(candidatos is v for v in visiveis)
                               else None)
        self.modelos = []
        c.escolher_modelo = lambda *_a: self.modelos.append(1) or "modelo"
        return c


class PaginaEmBranco(_Base):
    def test_em_branco_e_indisponivel_e_nao_login_caido(self):
        c = self._cliente(_Pagina(texto=""))
        with self.assertRaises(llm_cliente.SiteIndisponivel) as caso:
            c.abrir()
        exc = caso.exception
        self.assertNotIsInstance(exc, llm_cliente.NaoLogado)
        self.assertEqual("indisponivel", exc.categoria)
        self.assertTrue(exc.pausa_rodizio, "pausa o rodizio como o 'Alta procura'")
        self.assertIn("não é o login", str(exc))
        self.assertIn("não montou", str(exc))
        self.assertEqual([], self.modelos, "nao tenta trocar de modelo numa pagina vazia")
        self.assertFalse(any("chat novo aberto" in m for m in self.logs), self.logs)

    def test_a_tela_fica_salva_e_o_erro_diz_onde(self):
        pagina = _Pagina(texto="")
        c = self._cliente(pagina)
        with self.assertRaises(llm_cliente.SiteIndisponivel) as caso:
            c.abrir()
        self.assertEqual(1, len(pagina.fotos))
        foto = Path(pagina.fotos[0])
        self.assertEqual(self.pasta, foto.parent)
        self.assertTrue(foto.name.startswith("grok_"))
        self.assertTrue(foto.exists())
        self.assertIn(foto.name, str(caso.exception))

    def test_foto_que_falha_nao_troca_o_diagnostico(self):
        c = self._cliente(_Pagina(texto="", foto_falha=True))
        with self.assertRaises(llm_cliente.SiteIndisponivel):
            c.abrir()

    def test_quase_vazia_tambem_e_em_branco(self):
        # um "Grok" solto ou um "Carregando..." nao e um app montado
        c = self._cliente(_Pagina(texto="  Grok \n Carregando... "))
        self.assertEqual("em_branco", c.estado_da_pagina())

    def test_desafio_anti_bot_e_indisponivel(self):
        c = self._cliente(_Pagina(titulo="Just a moment...",
                                  texto="Verifying you are human. " * 10))
        with self.assertRaises(llm_cliente.SiteIndisponivel) as caso:
            c.abrir()
        self.assertIn("anti-bot", str(caso.exception))
        self.assertNotIsInstance(caso.exception, llm_cliente.NaoLogado)

    def test_o_mesmo_para_todos_os_provedores(self):
        for ia in seletores.PROVEDORES:
            with self.subTest(ia=ia):
                c = self._cliente(_Pagina(texto=""), provedor=ia)
                with self.assertRaises(llm_cliente.SiteIndisponivel):
                    c.abrir()
                c = self._cliente(_Pagina({"login"}, texto=CHEIA), provedor=ia)
                with self.assertRaises(llm_cliente.NaoLogado):
                    c.abrir()


class TelaDeLogin(_Base):
    def test_tela_de_login_visivel_e_nao_logado(self):
        pagina = _Pagina({"login"}, texto="Entrar · Criar conta · Pergunte ao Grok")
        c = self._cliente(pagina)
        with self.assertRaises(llm_cliente.NaoLogado):
            c.abrir()
        self.assertEqual([], pagina.fotos, "login caido nao e pagina em branco")

    def test_anonima_com_campo_e_link_de_entrar_e_nao_logado(self):
        # a pagina anonima do Grok tem o textarea E o "Entrar": o link decide
        c = self._cliente(_Pagina({"campo", "login"}, texto=CHEIA))
        self.assertEqual("deslogado", c.estado_da_pagina())

    def test_logado_vence_a_tela_de_login(self):
        c = self._cliente(_Pagina({"logado", "login"}, texto=CHEIA))
        self.assertEqual("logado", c.estado_da_pagina())


class PaginaNormal(_Base):
    def test_chat_montado_abre(self):
        c = self._cliente(_Pagina({"logado", "campo"}, texto=CHEIA))
        c.abrir()
        self.assertEqual([1], self.modelos)
        self.assertTrue(any("chat novo aberto" in m for m in self.logs), self.logs)

    def test_campo_sem_prova_nem_login_segue_como_antes(self):
        c = self._cliente(_Pagina({"campo"}, texto=CHEIA))
        c.abrir()
        self.assertEqual([1], self.modelos)

    def test_pagina_cheia_que_nao_reconheco_segue_como_antes(self):
        # o site mudou os seletores: nao e em branco nem login; o envio vai
        # dizer qual seletor faltou (SeletorNaoEncontrado), como sempre disse
        pagina = _Pagina(texto=CHEIA)
        c = self._cliente(pagina)
        self.assertEqual("nao_sei", c.estado_da_pagina())
        c.abrir()
        self.assertEqual([], pagina.fotos)
        self.assertTrue(any("não reconheço" in m for m in self.logs), self.logs)

    def test_pagina_que_nao_responde_nao_vira_em_branco(self):
        # sem conseguir ler a pagina, nao concluo nada: segue como antes
        c = self._cliente(_Pagina(quebrada=True))
        self.assertEqual("nao_sei", c.estado_da_pagina())

    def test_logado_compativel(self):
        self.assertFalse(self._cliente(_Pagina({"login"}, texto=CHEIA)).logado())
        self.assertTrue(self._cliente(_Pagina({"logado"}, texto=CHEIA)).logado())


if __name__ == "__main__":
    unittest.main()
