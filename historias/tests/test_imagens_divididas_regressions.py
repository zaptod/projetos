# -*- coding: utf-8 -*-
"""Gemini, ChatGPT e PicassoIA dividem imagens sem abrir navegador."""
from __future__ import annotations

import os
import json
import tempfile
import unittest
from pathlib import Path

from contos.imagens import fila, worker
from contos.roteiro import roteiro
from ias import correio, imagem


class ImagensDivididasTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.anterior_ias = os.environ.get("NF_IAS_PASTA")
        os.environ["NF_IAS_PASTA"] = str(self.raiz / "correio")
        self.anterior_outputs = fila.OUTPUTS
        self.anterior_config = fila.carregar_config
        self.anterior_ordem = worker._ordem_de_geradores
        self.anterior_carregar = roteiro.carregar
        fila.OUTPUTS = self.raiz / "outputs"
        fila.carregar_config = lambda: {
            "geradores_imagem": ["gemini", "chatgpt", "picasso"],
            "divisao": "por-historia", "aspect": "1:1",
            "reescrever_com_llm": False, "suavizacao_max": 0,
        }
        worker._ordem_de_geradores = lambda _cfg: ["gemini", "chatgpt", "picasso"]
        roteiro.carregar = lambda _id: self.roteiro(2)

    def tearDown(self):
        fila.OUTPUTS = self.anterior_outputs
        fila.carregar_config = self.anterior_config
        worker._ordem_de_geradores = self.anterior_ordem
        roteiro.carregar = self.anterior_carregar
        if self.anterior_ias is None:
            os.environ.pop("NF_IAS_PASTA", None)
        else:
            os.environ["NF_IAS_PASTA"] = self.anterior_ias
        self.tmp.cleanup()

    @staticmethod
    def roteiro(quantas):
        return {"titulo": "Teste", "protagonista": "", "partes": [{"n": 1,
                "cenas": [{"n": n, "imagem": f"scene {n}", "tempo": 4,
                           "narracao": "texto"} for n in range(1, quantas + 1)]}]}

    @staticmethod
    def _bytes():
        return imagem.png_de_teste() + b"x" * 10_000

    def entregador(self, chamadas, *, falhar=(), sem_prova=False):
        falhar = list(falhar)

        def entregar(pedido, _prazo):
            chamadas.append((pedido["para"], pedido["texto"]))
            gerador = "gemini" if pedido["para"] == correio.LIVRE else pedido["para"]
            if falhar and gerador == falhar[0]:
                falhar.pop(0)
                return correio.atualizar(pedido["para"], pedido["id"],
                                         situacao="falhou", gerador=gerador,
                                         categoria="indisponivel", erro="duble falhou")
            pasta = correio.pasta_imagens(gerador)
            pasta.mkdir(parents=True, exist_ok=True)
            (pasta / f"{pedido['id']}.png").write_bytes(self._bytes())
            (pasta / f"{pedido['id']}.prova.json").write_text(
                json.dumps({"prova": {"comprovada": not sem_prova,
                                       "forca": "duble"}}), encoding="utf-8")
            info = {"arquivo": f"{pedido['id']}.png"}
            if not sem_prova:
                info["prova"] = "turno do duble"
            return correio.atualizar(pedido["para"], pedido["id"],
                                     situacao="respondida", gerador=gerador,
                                     imagem=info)

        return entregar

    def test_por_historia_fixa_gerador_e_copia_as_cenas(self):
        chamadas = []
        saida = worker.gerar("historia_teste", entregador=self.entregador(chamadas),
                             log=lambda _msg: None)

        self.assertEqual(2, saida["geradas"])
        self.assertEqual(["gemini", "gemini"], [caixa for caixa, _ in chamadas])
        self.assertEqual("gemini", fila.gerador_da_historia("historia_teste"))
        for linha in fila.estado("historia_teste", self.roteiro(2)):
            self.assertTrue(linha["arquivo"].is_file())
            self.assertEqual("gemini", fila._meta("historia_teste")["cenas"]
                             [f"1:{linha['n']}"]["gerador"])

    def test_duas_falhas_da_cena_vao_ao_proximo_gerador(self):
        roteiro.carregar = lambda _id: self.roteiro(1)
        chamadas = []
        saida = worker.gerar("historia_teste", entregador=self.entregador(
            chamadas, falhar=("gemini", "gemini")), log=lambda _msg: None)

        self.assertEqual(1, saida["geradas"])
        self.assertEqual(["gemini", "gemini", "chatgpt"],
                         [caixa for caixa, _ in chamadas])
        meta = fila._meta("historia_teste")
        self.assertEqual("chatgpt", meta["cenas"]["1:1"]["gerador"])
        self.assertEqual(2, len(meta["falhas_de_geracao"]["1:1"]))

    def _cena_antiga_pronta(self, registro):
        """Cena 1 ja feita, registrada no formato que a historia guardou."""
        linha = fila.estado("historia_teste", self.roteiro(2))[0]
        linha["arquivo"].parent.mkdir(parents=True, exist_ok=True)
        linha["arquivo"].write_bytes(self._bytes())
        fila._gravar_meta("historia_teste", {"cenas": {"1:1": registro}})

    def test_historia_antiga_sem_gerador_herda_o_picasso(self):
        # Antes de 03/10 o PicassoIA era o unico gerador e a cena nao
        # registrava qual foi; a parte que falta nao pode mudar de gerador.
        self._cena_antiga_pronta({"prompt": "scene 1", "arquivo": "cena_01.png"})
        chamadas = []
        saida = worker.gerar("historia_teste", entregador=self.entregador(chamadas),
                             log=lambda _msg: None)

        self.assertEqual(1, saida["geradas"])
        self.assertEqual(["picasso"], [caixa for caixa, _ in chamadas])
        self.assertEqual("picasso", fila.gerador_da_historia("historia_teste"))

    def test_historia_em_andamento_herda_o_gerador_registrado(self):
        self._cena_antiga_pronta({"prompt": "scene 1", "arquivo": "cena_01.png",
                                  "gerador": "chatgpt"})
        chamadas = []
        worker.gerar("historia_teste", entregador=self.entregador(chamadas),
                     log=lambda _msg: None)

        self.assertEqual(["chatgpt"], [caixa for caixa, _ in chamadas])
        self.assertEqual("chatgpt", fila.gerador_da_historia("historia_teste"))

    def test_gerador_herdado_fica_com_o_mais_frequente(self):
        self.assertEqual("", fila.gerador_herdado("historia_teste"))
        fila._gravar_meta("historia_teste", {"cenas": {
            "1:1": {"gerador": "gemini"}, "1:2": {}, "1:3": {"gerador": ""}}})
        self.assertEqual("picasso", fila.gerador_herdado("historia_teste"))

    def test_por_cena_pede_a_caixa_livre(self):
        fila.carregar_config = lambda: {
            "geradores_imagem": ["gemini", "chatgpt", "picasso"],
            "divisao": "por-cena", "reescrever_com_llm": False,
            "suavizacao_max": 0,
        }
        chamadas = []
        worker.gerar("historia_teste", entregador=self.entregador(chamadas),
                     log=lambda _msg: None)

        self.assertEqual([correio.LIVRE, correio.LIVRE],
                         [caixa for caixa, _ in chamadas])

    def test_imagem_sem_prova_nao_entra_na_cena(self):
        roteiro.carregar = lambda _id: self.roteiro(1)
        chamadas = []
        saida = worker.gerar("historia_teste", entregador=self.entregador(
            chamadas, sem_prova=True), log=lambda _msg: None)

        self.assertEqual(0, saida["geradas"])
        self.assertEqual(1, saida["faltam"])
        self.assertFalse((fila.OUTPUTS / "historia_teste" / "cenas" /
                          "cena_01.png").exists())


if __name__ == "__main__":
    unittest.main()
