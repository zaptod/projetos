# -*- coding: utf-8 -*-
"""A SONDA ACHA A IMAGEM PELO MESMO CAMINHO DO CARTEIRO (29/09/2026).

O defeito do gato (d228c94f, 16:02): "Crie um gato para mim" ao ChatGPT
voltou "imagem pronta 512x512" com a miniatura de um ANUNCIO que o ChatGPT
poe DENTRO do mesmo section[data-turn=assistant] da resposta. O carteiro foi
consertado em 136730b (recipiente de imagem gerada, src novo, geracao
terminada); a sonda das fichas ainda tinha a regra antiga
(`_imagens_da_resposta`: toda img de 64+ px do ultimo turno do assistente) e
mediria o anuncio como "o ChatGPT gera imagem".

Dublê: a pagina responde a cada script pelo que ele PERGUNTA, com a verdade
do DOM medido (o anuncio no mesmo section, fora do recipiente). A regra
antiga ve o anuncio; a do cliente o conta como `fora`. Nenhum navegador,
nenhuma conta, nada fora do tempdir.
"""
from __future__ import annotations

import base64
import inspect
import tempfile
import types
import unittest
from pathlib import Path

from contos.llm import cliente as llm_cliente                      # noqa: E402
from contos.llm import seletores                                   # noqa: E402

from ias import ficha as fichas, imagem, sonda

ANUNCIO = {"src": "https://images.openai.com/static-rsc/cavn-ai-anuncio.png",
           "w": 512, "h": 512, "alt": ""}
CIRCULO = {"src": "https://chatgpt.com/backend-api/estuary/content?id=file_circulo",
           "src_attr": "https://chatgpt.com/backend-api/estuary/content?id=file_circulo",
           "w": 300, "h": 300, "pronta": True, "borrada": False,
           "alt": "Imagem gerada: Circulo vermelho"}
BYTES = {ANUNCIO["src"]: imagem.png_de_teste(512, 512, cor=(40, 40, 40)),
         CIRCULO["src"]: imagem.png_de_teste(300, 300, cor=(220, 30, 30))}


class _PaginaChatGPT:
    """O ChatGPT depois do nosso pedido. O anuncio esta SEMPRE no mesmo
    section do assistente, fora do recipiente `imagegen-image`."""

    url = "https://chatgpt.com/c/sonda-duble"

    def __init__(self, geradas=(), texto="", antes=()):
        self.geradas = [dict(i) for i in geradas]
        self.texto = texto
        self.antes = list(antes)
        self.scripts = []

    def evaluate(self, script, argumento=None):
        s = str(script)
        self.scripts.append(s)
        if "fetch(" in s:
            # baixar pelo src (o `_JS_BAIXAR` do carteiro e o da regra antiga)
            corpo = BYTES.get(str(argumento))
            if corpo is None:
                return {"erro": 404}
            return {"b64": base64.b64encode(corpo).decode("ascii")}
        if "data-nf-imagem" in s:
            # o botao de baixar do ChatGPT e na tela cheia: sem ela, cai no src
            return {"imagem": False, "botao": False}
        if "[respostas, usuarios]" in s:
            # a regra ANTIGA: toda img do ultimo turno do assistente (o
            # anuncio incluido, como no d228c94f)
            return [{"src": i["src"], "w": i["w"], "h": i["h"], "alt": i.get("alt", "")}
                    for i in self.geradas + [ANUNCIO]]
        if "out.push(im.currentSrc)" in s:
            return list(self.antes)
        if "naturalWidth" in s:
            # `ClienteLLM._JS_IMAGENS`: so o recipiente de imagem gerada; o
            # anuncio e contado como `fora`
            return {"ancorado": True, "turno": sonda.PEDIDO_IMAGEM, "resposta": True,
                    "gerando": False, "imagens": [dict(i) for i in self.geradas],
                    "fora": 1}
        if argumento is not None:
            return {"texto": self.texto, "ancorado": True}
        return None

    def screenshot(self, path=None, **_k):
        raise RuntimeError("dublê sem tela")


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
        self.addCleanup(setattr, seletores, "encontrar", seletores.encontrar)
        seletores.encontrar = lambda *a, **k: None          # sem botao de parar
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name) / self.provedor
        self.pasta.mkdir(parents=True)
        self.logs = []
        self.enviados = []

    def _sondar(self, pagina):
        c = llm_cliente.ClienteLLM(self.provedor, None, pagina, log=self.logs.append)
        c._envio_devolvido = lambda: False
        c._envio_truncado = lambda: False
        c._responder_agora = lambda: False
        c._diagnosticar_calado = lambda: None

        def enviar(prompt):
            # o que o `enviar` de verdade faz antes de colar: a foto de antes
            self.enviados.append(prompt)
            c._srcs_antes_do_envio = c._foto_das_imagens() if c.olha_imagem() else None
        c.enviar = enviar
        ficha = fichas.vazia(self.provedor)
        ficha["pendencias"] = []
        sonda._imagem_no_chat(self.provedor, c, ficha, self.pasta, self.logs.append)
        return ficha

    def _arquivos(self):
        return sorted(p.name for p in self.pasta.iterdir()
                      if p.suffix.lower() in (".png", ".jpg", ".webp"))


class AnuncioNaoEImagemGerada(_Base):
    def test_anuncio_no_mesmo_section_nao_conta_como_gera_imagem(self):
        pagina = _PaginaChatGPT(texto="Não consigo criar imagens nesta conversa agora.")
        ficha = self._sondar(pagina)
        self.assertIsNot(True, ficha["imagem"]["gera"])
        self.assertFalse(ficha["imagem"]["gera"])
        self.assertEqual([], self._arquivos(), "o anuncio foi para o disco")
        self.assertIsNone(ficha["imagem"]["resolucao"])
        self.assertNotIn("comprovada", ficha["imagem"]["prova_origem"])
        self.assertIn("sem imagem", ficha["imagem"]["prova_origem"]["motivo"])
        self.assertEqual([], fichas.validar(ficha))

    def test_so_o_anuncio_e_nenhum_texto_fica_nao_medido(self):
        ficha = self._sondar(_PaginaChatGPT())
        self.assertIsNone(ficha["imagem"]["gera"])
        self.assertEqual([], self._arquivos())
        self.assertTrue(any("sem resposta final" in p for p in ficha["pendencias"]),
                        ficha["pendencias"])

    def test_imagem_do_recipiente_com_anuncio_ao_lado_baixa_a_nossa(self):
        pagina = _PaginaChatGPT([CIRCULO], texto="")
        ficha = self._sondar(pagina)
        bloco = ficha["imagem"]
        self.assertIs(True, bloco["gera"])
        self.assertEqual([300, 300], bloco["resolucao"])
        self.assertEqual(BYTES[CIRCULO["src"]], Path(bloco["arquivo"]).read_bytes())
        prova = bloco["prova_origem"]
        self.assertTrue(prova["comprovada"])
        self.assertTrue(prova["dentro_da_resposta"])
        self.assertTrue(prova["src_novo"])
        self.assertEqual(CIRCULO["src"], prova["src"])
        self.assertEqual(1, prova["ignoradas_fora_da_resposta"])   # o anuncio
        self.assertEqual("src_da_tela", prova["download"])
        self.assertEqual([], fichas.validar(ficha))

    def test_imagem_que_ja_estava_antes_do_envio_nao_conta(self):
        pagina = _PaginaChatGPT([CIRCULO], texto="Aqui está o seu círculo vermelho!",
                                antes=[CIRCULO["src"], ANUNCIO["src"]])
        ficha = self._sondar(pagina)
        self.assertFalse(ficha["imagem"]["gera"])
        self.assertEqual([], self._arquivos())

    def test_pede_como_o_carteiro_pede(self):
        self._sondar(_PaginaChatGPT([CIRCULO]))
        self.assertEqual([imagem.pedido_de_imagem(sonda.PROMPT_GERADOR, "1:1")],
                         self.enviados)


class CasoZero(_Base):
    provedor = "deepseek"

    def test_ia_sem_recipiente_medido_nao_gasta_pedido(self):
        ficha = self._sondar(_PaginaChatGPT([CIRCULO], texto="ok"))
        self.assertIsNone(ficha["imagem"]["gera"])
        self.assertEqual([], self.enviados, "gastou cota sem ter onde procurar a imagem")
        self.assertEqual([], self._arquivos())


class SemRegraPropria(unittest.TestCase):
    def test_a_sonda_nao_tem_regra_propria_de_achar_imagem(self):
        # a imagem se acha em `ClienteLLM.imagens_da_resposta` e se baixa em
        # `ias.imagem.baixar_da_resposta`; uma segunda regra aqui divergiria
        self.assertFalse(hasattr(sonda, "_imagens_da_resposta"))
        self.assertFalse(hasattr(sonda, "_baixar_imagem"))
        fonte = inspect.getsource(sonda)
        self.assertNotIn("querySelectorAll('img')", fonte)
        self.assertIn("baixar_da_resposta", inspect.getsource(sonda._imagem_no_chat))


if __name__ == "__main__":
    unittest.main()
