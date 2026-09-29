# -*- coding: utf-8 -*-
"""A IMAGEM DA RESPOSTA TEM DE SER A DO NOSSO TURNO (29/09/2026, 16:02).

"Crie um gato para mim" ao ChatGPT (correio `d228c94f`) voltou "imagem
pronta · 512x512" com a foto de uma MESA DE SOM: a miniatura de um ANUNCIO
("CAVN AI · AI Music Videos · Anuncio") que o ChatGPT poe embaixo da resposta,
dentro do MESMO section[data-turn=assistant] do gato. O gato de verdade
(1254x1254) estava la e foi ignorado. Medido na tela, sem mandar nada
(scratchpad/diag_chatgpt_imagem.py, diag_chatgpt_baixar.py).

A espera (`ClienteLLM.esperar_resposta`) agora so aceita imagem que:
- esta na resposta ao NOSSO turno, num recipiente de imagem gerada (o JS
  devolve so essas; o anuncio vira `fora`);
- tem src que NAO estava na pagina antes do envio (`_srcs_antes_do_envio`);
- e a final: carregada, sem borrao, com o alt de imagem final (ChatGPT),
  sem "Criando imagem", sem botao de parar e estavel.

Dubles: a pagina responde ao script pelo que ele e; nenhum navegador.
"""
from __future__ import annotations

import types
import unittest

from contos.llm import cliente as llm_cliente                      # noqa: E402
from contos.llm import seletores                                   # noqa: E402

GATO = {"src": "https://chatgpt.com/backend-api/estuary/content?id=file_gato",
        "src_attr": "https://chatgpt.com/backend-api/estuary/content?id=file_gato",
        "w": 1254, "h": 1254, "pronta": True, "borrada": False,
        "alt": "Imagem gerada: Retrato Aconchegante de Gato Tigrado"}
PREVIA = dict(GATO, borrada=True, alt="")
ANTIGA = {"src": "https://chatgpt.com/backend-api/estuary/content?id=file_antigo",
          "w": 1024, "h": 1024, "pronta": True, "borrada": False,
          "alt": "Imagem gerada: um cachorro de ontem"}
PEDIDO = "Crie uma imagem na proporção 1:1. Responda só com a imagem, sem texto.\n\nCrie um gato"


def _estado(imagens=(), *, resposta=True, gerando=False, fora=0, ancorado=True):
    return {"ancorado": ancorado, "turno": PEDIDO if ancorado else "", "resposta": resposta,
            "gerando": gerando, "fora": fora, "imagens": list(imagens)}


class _Pagina:
    """`evaluate` responde pelo script: a foto das imagens (antes do envio),
    as imagens da resposta (um estado por volta) e o texto."""

    def __init__(self, estados, texto="", antes=()):
        self.estados = iter(estados)
        self.ultimo = _estado()
        self.texto = texto
        self.antes = list(antes)
        self.voltas = 0

    def evaluate(self, script, argumento=None):
        script = str(script)
        if "out.push(im.currentSrc)" in script:
            return list(self.antes)
        if "naturalWidth" in script:
            self.voltas += 1
            self.ultimo = next(self.estados, self.ultimo)
            return self.ultimo
        if argumento is not None:
            return {"texto": self.texto, "ancorado": True}
        return None


class _Base(unittest.TestCase):
    provedor = "chatgpt"

    def setUp(self):
        agora = [0.0]

        def monotonic():
            agora[0] += 1.0
            return agora[0]

        falso = types.SimpleNamespace(monotonic=monotonic, sleep=lambda _s: None,
                                      strftime=__import__("time").strftime)
        self.addCleanup(setattr, llm_cliente, "time", llm_cliente.time)
        llm_cliente.time = falso
        self.parar = [False]
        self.addCleanup(setattr, seletores, "encontrar", seletores.encontrar)
        seletores.encontrar = (lambda *a, **k: object() if self.parar[0] else None)
        self.logs = []

    def _cliente(self, pagina):
        c = llm_cliente.ClienteLLM(self.provedor, None, pagina, log=self.logs.append)
        c._envio_devolvido = lambda: False
        c._envio_truncado = lambda: False
        c._responder_agora = lambda: False
        c._diagnosticar_calado = lambda: None
        # a foto de antes do envio, como `enviar` tira
        c._srcs_antes_do_envio = c._foto_das_imagens() if c.olha_imagem() else None
        return c


class ImagemDoNossoTurno(_Base):
    def test_imagem_antiga_e_nova_no_nosso_turno_pega_a_nova(self):
        # a antiga ja estava na pagina antes do envio; o anuncio fica "fora"
        pagina = _Pagina([_estado(fora=1)] * 3 + [_estado([ANTIGA, GATO], fora=1)] * 40,
                         antes=[ANTIGA["src"]])
        c = self._cliente(pagina)
        texto = c.esperar_resposta(timeout=420, estabilidade=2)
        self.assertEqual("", texto)
        self.assertEqual([GATO], c.imagens_na_resposta)
        self.assertTrue(any("FORA da resposta" in m for m in self.logs), self.logs)

    def test_geracao_em_andamento_espera(self):
        # previa borrada com "Criando imagem", depois nitida mas ainda
        # "gerando", e so entao a final
        estados = ([_estado([PREVIA], gerando=True)] * 6
                   + [_estado([GATO], gerando=True)] * 6
                   + [_estado([GATO])] * 40)
        pagina = _Pagina(estados)
        c = self._cliente(pagina)
        c.esperar_resposta(timeout=420, estabilidade=2)
        self.assertEqual([GATO], c.imagens_na_resposta)
        self.assertGreater(pagina.voltas, 12, "nao aceitou durante a geracao")

    def test_botao_de_parar_na_tela_espera(self):
        pagina = _Pagina([_estado([GATO])] * 80)
        c = self._cliente(pagina)
        self.parar[0] = True
        with self.assertRaises(llm_cliente.LLMFalhou):
            c.esperar_resposta(timeout=30, estabilidade=2)
        self.assertEqual([], c.imagens_na_resposta)

    def test_sem_imagem_nova_falha(self):
        # so a imagem de antes do envio: nada e resposta, e sem texto falha
        pagina = _Pagina([_estado([ANTIGA], fora=1)] * 200, antes=[ANTIGA["src"]])
        c = self._cliente(pagina)
        with self.assertRaises(llm_cliente.LLMFalhou):
            c.esperar_resposta(timeout=40, estabilidade=2)
        self.assertEqual([], c.imagens_na_resposta)

    def test_sem_o_alt_de_imagem_final_nao_vale_no_chatgpt(self):
        sem_alt = dict(GATO, alt="")
        pagina = _Pagina([_estado([sem_alt])] * 200)
        c = self._cliente(pagina)
        with self.assertRaises(llm_cliente.LLMFalhou):
            c.esperar_resposta(timeout=40, estabilidade=2)

    def test_sem_a_resposta_ao_nosso_turno_nao_vale(self):
        pagina = _Pagina([_estado([GATO], resposta=False)] * 200)
        c = self._cliente(pagina)
        with self.assertRaises(llm_cliente.LLMFalhou):
            c.esperar_resposta(timeout=40, estabilidade=2)
        self.assertEqual([], c.imagens_na_resposta)

    def test_texto_parado_espera_a_imagem_terminar(self):
        # "Aqui esta o seu gato!" para cedo; a imagem ainda esta borrada
        estados = [_estado([PREVIA], gerando=True)] * 10 + [_estado([GATO])] * 40
        pagina = _Pagina(estados, texto="Aqui está o seu gato! " * 3)
        c = self._cliente(pagina)
        texto = c.esperar_resposta(timeout=420, estabilidade=2)
        self.assertIn("gato", texto)
        self.assertEqual([GATO], c.imagens_na_resposta)

    def test_estouro_usa_a_mesma_regua(self):
        # o prazo acaba com a IA dizendo que ainda gera: a previa nao vai
        pagina = _Pagina([_estado([GATO], gerando=True)] * 200,
                         texto="Estou criando a imagem do seu gato agora. " * 2)
        c = self._cliente(pagina)
        c.esperar_resposta(timeout=40, estabilidade=2)
        self.assertEqual([], c.imagens_na_resposta)


class CasoZero(_Base):
    def test_ia_sem_recipiente_medido_nao_procura_imagem(self):
        self.provedor = "deepseek"
        pagina = _Pagina([_estado([GATO])] * 200, texto="Uma resposta comum. " * 5)
        c = self._cliente(pagina)
        self.assertFalse(c.olha_imagem())
        self.assertIsNone(c._srcs_antes_do_envio)
        c.esperar_resposta(timeout=100, estabilidade=2)
        self.assertEqual([], c.imagens_na_resposta)
        self.assertEqual(0, pagina.voltas, "nem perguntou pelas imagens")

    def test_pagina_sem_turno_nosso_nenhuma_imagem(self):
        c = self._cliente(_Pagina([]))
        self.assertEqual([], c.imagens_prontas(_estado([GATO], ancorado=False)))
        self.assertEqual([], c.imagens_prontas({}))

    def test_turno_so_de_texto_nao_suja_o_log(self):
        # a pipeline reescrevendo prompt no ChatGPT: nenhuma linha "imagem:"
        pagina = _Pagina([_estado()] * 200, texto="Um prompt reescrito, calmo e seguro. " * 3)
        c = self._cliente(pagina)
        c.esperar_resposta(timeout=100, estabilidade=2)
        self.assertEqual([], [m for m in self.logs if "imagem:" in m])

    def test_pagina_que_nao_responde_e_vazio(self):
        class _Quebrada:
            def evaluate(self, *_a):
                raise RuntimeError("pagina fechou")
        c = llm_cliente.ClienteLLM("chatgpt", None, _Quebrada(), log=lambda *_a: None)
        self.assertEqual([], c.imagens_da_resposta()["imagens"])
        self.assertFalse(c.imagens_da_resposta()["resposta"])
        self.assertEqual(set(), c._foto_das_imagens())

    def test_as_tres_ias_de_imagem_tem_os_recipientes(self):
        for ia in ("chatgpt", "gemini", "grok"):
            s = seletores.do_provedor(ia)
            self.assertTrue(s.get("imagem_turno"), ia)
            self.assertTrue(s.get("imagem_gerada"), ia)
        self.assertFalse(seletores.do_provedor("deepseek").get("imagem_gerada"))


if __name__ == "__main__":
    unittest.main()
