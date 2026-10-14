# -*- coding: utf-8 -*-
"""IAS-3 (auditoria de 11/10/2026): o download pelo botao caia
(`TargetClosedError: Download.path`) e a previa do `src` entrava calada como
a imagem final.

Em 12/10, 118 linhas `Download.path` no log e 47 imagens do Gemini pela
previa (metade da resolucao) contra 42 pelo botao; o resumo no correio so
dizia `prova: turno_na_casa`, e o carteiro fechava e reabria o navegador
(~1 min) com a pagina viva.

DECISAO DO ADRIAN (Grimorio `historias/previa-do-gemini`, 14/10/2026):
quando o original nao baixa, a previa e ACEITA, MARCADA como "previa" no
registro, no correio e no resumo, sem gerar de novo.

Com dublê: nenhum navegador, conta ou Telegram (`NF_IAS_PASTA`).
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from ias import carteiro as carteiro_mod, correio, imagem

PEDIDO = imagem.pedido_de_imagem("um gato laranja dormindo no sofá", "1:1")
SRC = "https://lh3.googleusercontent.com/gg/previa-do-gato"


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._antes = os.environ.get("NF_IAS_PASTA")
        os.environ["NF_IAS_PASTA"] = str(Path(self._tmp.name) / "ias")

    def tearDown(self):
        if self._antes is None:
            os.environ.pop("NF_IAS_PASTA", None)
        else:
            os.environ["NF_IAS_PASTA"] = self._antes
        self._tmp.cleanup()


class _DownloadQueCai:
    """O `Download` do Playwright depois do TargetClosed: path e save_as morrem."""
    suggested_filename = "Gemini_Generated_Image.jfif"

    @staticmethod
    def path():
        raise RuntimeError("TargetClosedError: Download.path: Target page, context or "
                           "browser has been closed")

    @staticmethod
    def save_as(destino):
        raise RuntimeError("TargetClosedError: Download.save_as: Target page, context or "
                           "browser has been closed")


def _cliente_gemini(*, pagina_fechada=False):
    """Um ClienteLLM dublê do Gemini com a imagem pronta na resposta ao
    nosso turno; o botao de baixar dispara um download que cai."""
    from contos.llm import seletores
    cliques = []
    previa = imagem.png_de_teste(64, 64)

    class _Alvo:
        def __init__(self):
            self.first = self

        def scroll_into_view_if_needed(self, timeout=None):
            pass

        def evaluate(self, script):
            return True                                         # habilitado; rotulo

        def hover(self, timeout=None, force=False):
            pass

        def click(self, timeout=None, force=False):
            cliques.append("baixar")
            pagina.ouvintes["download"](_DownloadQueCai())

    class _Pagina:
        url = "https://gemini.google.com/app/3f2a9b1c0d"

        def __init__(self):
            self.ouvintes = {}

        def evaluate(self, script, arg=None):
            return {"imagem": True, "botao": True}

        def locator(self, seletor):
            return _Alvo()

        def on(self, evento, funcao):
            self.ouvintes[evento] = funcao

        def remove_listener(self, evento, funcao):
            self.ouvintes.pop(evento, None)

        def wait_for_timeout(self, ms):
            pass

        def is_closed(self):
            return pagina_fechada

    pagina = _Pagina()

    class _Ctx:
        class request:                                          # noqa: N801
            @staticmethod
            def get(url, timeout=None):
                class _R:
                    ok, status = True, 200

                    @staticmethod
                    def body():
                        return previa
                return _R()

    class _Cli:
        provedor = "gemini"
        sel = seletores.GEMINI
        ajustes = {}
        modelo_atual = ""
        ctx = _Ctx()
        page = pagina
        imagens_na_resposta = [{"src": SRC, "w": 64, "h": 64, "pronta": True}]
        _srcs_antes_do_envio = set()

        def imagens_da_resposta(self):
            return {"ancorado": True, "turno": PEDIDO, "resposta": True,
                    "imagens": [{"src": SRC}], "fora": 0}
    return _Cli(), cliques, previa


class BotaoComPaginaViva(unittest.TestCase):
    def test_clica_de_novo_e_fica_a_previa_marcada(self):
        cli, cliques, previa = _cliente_gemini()
        falas = []
        saida = imagem.baixar_da_resposta(cli, PEDIDO, "1:1", log=falas.append)
        self.assertEqual(cliques, ["baixar", "baixar"])     # o 2o clique com a pagina viva
        self.assertEqual(saida["bytes"], previa)
        self.assertEqual(saida["prova"]["download"], "src_da_tela")
        self.assertTrue(saida["prova"]["previa"])
        self.assertTrue(any("mais uma vez" in f for f in falas), falas)

    def test_pagina_fechada_nao_clica_de_novo(self):
        cli, cliques, _ = _cliente_gemini(pagina_fechada=True)
        imagem.baixar_da_resposta(cli, PEDIDO, "1:1", log=lambda *_a: None)
        self.assertEqual(cliques, ["baixar"])

    def test_chatgpt_pelo_src_nao_e_previa(self):
        """No ChatGPT o `src` ja e o PNG original (medido em 29/09)."""
        from contos.llm import seletores

        class _Cli:
            provedor = "chatgpt"
            sel = seletores.CHATGPT
        self.assertFalse(imagem.src_e_previa(_Cli()))

        class _Gemini:
            provedor = "gemini"
            sel = seletores.GEMINI
        self.assertTrue(imagem.src_e_previa(_Gemini()))


class PreviaMarcadaNoCorreio(_Base):
    def test_guardar_leva_download_e_previa_ao_resumo_e_ao_registro(self):
        prova = {"comprovada": True, "metodo": "turno_na_casa", "download": "src_da_tela",
                 "previa": True}
        salvo = imagem.guardar("gemini", "abcdef12", imagem.png_de_teste(), prova)
        self.assertEqual(salvo["download"], "src_da_tela")
        self.assertTrue(salvo["previa"])
        registro = json.loads((correio.pasta_imagens("gemini") / "abcdef12.prova.json")
                              .read_text(encoding="utf-8"))
        self.assertTrue(registro["prova"]["previa"])
        self.assertTrue(imagem.ja_guardada("gemini", "abcdef12")["previa"])

    def test_original_nao_ganha_marca(self):
        prova = {"comprovada": True, "metodo": "turno_na_casa",
                 "download": "botao_tamanho_original"}
        salvo = imagem.guardar("gemini", "abcdef13", imagem.png_de_teste(), prova)
        self.assertEqual(salvo["download"], "botao_tamanho_original")
        self.assertNotIn("previa", salvo)

    def test_carteiro_responde_dizendo_previa(self):
        @contextmanager
        def trava(nome, esperar=0.0):
            yield True
        documentos = []
        fabrica = carteiro_mod.fabrica_duble(
            imagem_prova_extra={"download": "src_da_tela", "previa": True})
        c = carteiro_mod.Carteiro(
            fabrica_de_sessao=fabrica, trava=trava,
            nome_da_trava=lambda ia: f"perfil__{ia}__teste",
            avisar=lambda _t: "entregue",
            avisar_arquivo=lambda caminho, legenda: documentos.append(legenda) or True,
            log=lambda m: None, dormir=lambda s: None, de_servico=True,
            ajustes={"janela_conversa_s": 0, "espera_conta_max_s": 100})
        c._diario = lambda *a: None
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
        fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual(fim["situacao"], "respondida")    # aceita, sem gerar de novo
        self.assertIn("prévia", fim["resposta"])
        self.assertTrue(fim["previa"])
        self.assertEqual(fim["imagem"]["download"], "src_da_tela")
        self.assertTrue(fim["imagem"]["previa"])
        self.assertEqual(len(fabrica.criadas[0]._imagem.pedidos), 1)
        self.assertTrue(any("prévia" in legenda for legenda in documentos), documentos)


class CarteiroNaoFechaONavegadorComAPaginaViva(_Base):
    def test_targetclosed_com_pagina_viva_recupera_na_mesma_sessao(self):
        criadas = []

        class _Pagina:
            def is_closed(self):
                return False

            def evaluate(self, script, arg=None):
                return 1

        class _Sessao:
            def __init__(self):
                self.cliente = type("C", (), {"page": _Pagina()})()
                self.geradas = self.recuperadas = 0

            def novo_chat(self, imagem=False):
                pass

            def gerar_imagem(self, prompt, proporcao, mensagem_id):
                self.geradas += 1
                raise RuntimeError("TargetClosedError: Download.path: Target page, "
                                   "context or browser has been closed")

            def recuperar_imagem(self, prompt, proporcao):
                self.recuperadas += 1
                return {"bytes": imagem.png_de_teste(),
                        "prova": {"comprovada": True, "metodo": "duble", "forca": "teste"}}

            def url(self):
                return "https://gemini.google.com/app/conversa-da-imagem"

        @contextmanager
        def fabrica(ia):
            sessao = _Sessao()
            criadas.append(sessao)
            yield sessao

        @contextmanager
        def trava(nome, esperar=0.0):
            yield True
        c = carteiro_mod.Carteiro(
            fabrica_de_sessao=fabrica, trava=trava,
            nome_da_trava=lambda ia: f"perfil__{ia}__teste",
            avisar=lambda _t: "entregue", avisar_arquivo=lambda *_a: True,
            log=lambda m: None, dormir=lambda s: None, de_servico=True,
            ajustes={"janela_conversa_s": 0, "espera_conta_max_s": 100})
        c._diario = lambda *a: None
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
        fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(len(criadas), 1)                  # o navegador NAO reabriu
        self.assertEqual((criadas[0].geradas, criadas[0].recuperadas), (1, 1))


if __name__ == "__main__":
    unittest.main()
