# -*- coding: utf-8 -*-
"""A RESPOSTA PODE SER UMA IMAGEM (29/09/2026).

As 14:24 o Adrian pediu pelo app, na conversa com o Gemini: "Tudo otimo,
gere uma imagem de um gato pra mim" (correio `dde066f1`). O Gemini desenhou;
a tela ficou com 0 caracteres de texto; `esperar_resposta` gastou os 420 s
inteiros e o carteiro disse "raciocinio preso ou limite". Agora a espera
reconhece a imagem que nasce DEPOIS do nosso turno e volta com ela em
`imagens_na_resposta` (quem chama baixa, com a prova do turno).
"""
from __future__ import annotations

import types
import unittest

from contos.llm import cliente as llm_cliente                      # noqa: E402
from contos.llm import seletores                                   # noqa: E402

GATO = {"src": "https://lh3.googleusercontent.com/gato=s1024", "w": 1024, "h": 1024,
        "pronta": True}
MINIATURA_DO_ANEXO = {"src": "blob:https://gemini.google.com/anexo", "w": 512, "h": 512,
                      "pronta": True}


class _Pagina:
    """`evaluate` responde pelo script: o das imagens e o do texto."""

    def __init__(self, imagens_por_volta, texto=""):
        self.imagens = imagens_por_volta
        self.texto = texto
        self.chamadas = 0

    def evaluate(self, script, argumento=None):
        if "naturalWidth" in str(script):
            self.chamadas += 1
            lista = next(self.imagens, None)
            return {"ancorado": True, "turno": "gere uma imagem de um gato",
                    "resposta": True, "gerando": False, "fora": 0,
                    "imagens": lista if lista is not None else []}
        if argumento is not None:
            return {"texto": self.texto, "ancorado": True}
        return None


class RespostaComImagem(unittest.TestCase):
    def setUp(self):
        agora = [0.0]

        def monotonic():
            agora[0] += 1.0
            return agora[0]

        falso = types.SimpleNamespace(monotonic=monotonic, sleep=lambda _s: None,
                                      strftime=__import__("time").strftime)
        self.addCleanup(setattr, llm_cliente, "time", llm_cliente.time)
        llm_cliente.time = falso
        self.addCleanup(setattr, seletores, "encontrar", seletores.encontrar)
        seletores.encontrar = lambda *a, **k: None          # sem botao de parar

    def _cliente(self, pagina):
        c = llm_cliente.ClienteLLM("gemini", None, pagina, log=lambda *_a: None)
        c._envio_devolvido = lambda: False
        c._envio_truncado = lambda: False
        c._responder_agora = lambda: False
        c._diagnosticar_calado = lambda: None
        return c

    def test_imagem_sem_texto_volta_logo_e_nao_espera_o_prazo(self):
        # nada na largada, nada por 3 voltas, e o gato aparece
        voltas = iter([[]] + [[]] * 3 + [[GATO]] * 50)
        pagina = _Pagina(voltas)
        c = self._cliente(pagina)
        texto = c.esperar_resposta(timeout=420, estabilidade=2)
        self.assertEqual("", texto)
        self.assertEqual([GATO], c.imagens_na_resposta)
        self.assertLess(pagina.chamadas, 20, "voltou logo, e nao aos 420 s")

    def test_imagem_que_ja_estava_na_tela_nao_e_resposta(self):
        # a miniatura de um anexo nosso, renderizada fora do balao, estava la
        # desde a largada: nao conta, e a espera estoura como antes
        voltas = iter([[MINIATURA_DO_ANEXO]] * 200)
        c = self._cliente(_Pagina(voltas))
        with self.assertRaises(llm_cliente.LLMFalhou):
            c.esperar_resposta(timeout=30, estabilidade=2)
        self.assertEqual([], c.imagens_na_resposta)

    def test_texto_e_imagem_juntos_vem_os_dois(self):
        voltas = iter([[]] + [[GATO]] * 50)
        c = self._cliente(_Pagina(voltas, texto="Aqui está o seu gato! " * 3))
        texto = c.esperar_resposta(timeout=420, estabilidade=2)
        self.assertIn("gato", texto)
        self.assertEqual([GATO], c.imagens_na_resposta)

    def test_resposta_so_de_texto_segue_sem_imagem(self):
        voltas = iter([[]] * 50)
        c = self._cliente(_Pagina(voltas, texto="Uma resposta comum. " * 5))
        texto = c.esperar_resposta(timeout=100, estabilidade=2)
        self.assertIn("comum", texto)
        self.assertEqual([], c.imagens_na_resposta)


if __name__ == "__main__":
    unittest.main()
