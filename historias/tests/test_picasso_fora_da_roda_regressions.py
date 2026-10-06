# -*- coding: utf-8 -*-
"""PicassoIA fora da roda de imagens (06/10/2026).

Decisao do Adrian no Grimorio, `geral/picasso-fora-da-roda` = "Tirar o
PicassoIA de vez" ("aparentemente o picasso morreu tambem, nao podemos mais
contar com ele"): Gemini e ChatGPT fazem todas as imagens.

O que se mede aqui:
- os dois lugares de configuracao que escolhem gerador (o `imagens.json`
  das historias e o `rodizio_imagem` do carteiro) nao tem o PicassoIA;
- historia FIXADA no PicassoIA (`gerador_imagem` no imagens.json) nao pede
  mais a ele: antes o fixado ia na frente das caixas mesmo fora da lista, e
  cada cena gastava 2 pedidos num site morto antes de passar ao proximo;
- historia sem fixado cujas cenas antigas sao do PicassoIA (o herdado) idem;
- `geradores_imagem: []` nao cai no caminho antigo, que abre o PicassoIA.

Sem navegador: o entregador e um duble que grava no correio de teste.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from contos.imagens import fila, worker
from contos.roteiro import roteiro
from ias import correio

HISTORIAS = Path(__file__).resolve().parents[1]
REPO = HISTORIAS.parent


def _png(semente: int = 1) -> bytes:
    import numpy as np
    from PIL import Image
    gerador = np.random.default_rng(semente)
    pixels = gerador.integers(0, 256, size=(341, 192), dtype=np.uint8)
    saida = io.BytesIO()
    Image.fromarray(pixels, mode="L").convert("RGB").save(saida, format="PNG")
    return saida.getvalue()


class ConfiguracaoSemPicasso(unittest.TestCase):

    def test_imagens_json_das_historias_sem_picasso(self):
        dados = json.loads((HISTORIAS / "config" / "imagens.json").read_text(
            encoding="utf-8-sig"))
        geradores = [str(g).lower() for g in dados["geradores_imagem"]]
        self.assertNotIn("picasso", geradores)
        self.assertEqual(geradores, ["gemini", "chatgpt"])

    def test_rodizio_do_carteiro_sem_picasso(self):
        dados = json.loads((REPO / "ias" / "config.json").read_text(encoding="utf-8-sig"))
        rodizio = [str(g).lower() for g in dados["rodizio_imagem"]]
        self.assertNotIn("picasso", rodizio)
        self.assertEqual(rodizio, ["gemini", "chatgpt"])


class HistoriaQueEraDoPicasso(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.anterior_ias = os.environ.get("NF_IAS_PASTA")
        os.environ["NF_IAS_PASTA"] = str(self.raiz / "correio")
        self.anterior_outputs = fila.OUTPUTS
        self.anterior_config = fila.carregar_config
        self.anterior_ordem = worker._ordem_de_geradores
        self.anterior_carregar = roteiro.carregar
        self.anterior_registrar = worker._rb_atividade.registrar
        self.diario = []
        worker._rb_atividade.registrar = lambda *a, **k: self.diario.append((a, k))
        fila.OUTPUTS = self.raiz / "outputs"
        self.config = {
            "geradores_imagem": ["gemini", "chatgpt"],
            "divisao": "por-historia", "aspect": "9:16",
            "reescrever_com_llm": False, "suavizacao_max": 0,
        }
        fila.carregar_config = lambda: dict(self.config)
        # a ordem real filtra pelo `geradores_imagem`; o duble devolve o que
        # o rodizio daria com o PicassoIA fora (o filtro e o da lista acima)
        worker._ordem_de_geradores = lambda cfg: [
            g for g in ("gemini", "chatgpt", "picasso") if g in cfg["geradores_imagem"]]
        roteiro.carregar = lambda _id: {
            "titulo": "Teste", "protagonista": "", "partes": [{"n": 1, "cenas": [
                {"n": 1, "imagem": "scene 1", "tempo": 4, "narracao": "texto"},
                {"n": 2, "imagem": "scene 2", "tempo": 4, "narracao": "texto"}]}]}

    def tearDown(self):
        fila.OUTPUTS = self.anterior_outputs
        fila.carregar_config = self.anterior_config
        worker._ordem_de_geradores = self.anterior_ordem
        roteiro.carregar = self.anterior_carregar
        worker._rb_atividade.registrar = self.anterior_registrar
        if self.anterior_ias is None:
            os.environ.pop("NF_IAS_PASTA", None)
        else:
            os.environ["NF_IAS_PASTA"] = self.anterior_ias
        self.tmp.cleanup()

    def entregador(self, chamadas):
        def entregar(pedido, _prazo):
            chamadas.append(dict(pedido))
            gerador = pedido["para"]
            pasta = correio.pasta_imagens(gerador)
            pasta.mkdir(parents=True, exist_ok=True)
            (pasta / f"{pedido['id']}.png").write_bytes(_png(len(chamadas)))
            (pasta / f"{pedido['id']}.prova.json").write_text(
                json.dumps({"prova": {"comprovada": True, "forca": "duble"}}),
                encoding="utf-8")
            return correio.atualizar(gerador, pedido["id"], situacao="respondida",
                                     gerador=gerador,
                                     imagem={"arquivo": f"{pedido['id']}.png",
                                             "prova": "turno do duble"})
        return entregar

    def test_fixada_no_picasso_passa_ao_primeiro_da_roda(self):
        fila.definir_gerador_da_historia("historia_teste", "picasso")
        chamadas, linhas = [], []
        saida = worker.gerar("historia_teste", entregador=self.entregador(chamadas),
                             log=linhas.append)
        self.assertEqual(saida["geradas"], 2)
        self.assertEqual([c["para"] for c in chamadas], ["gemini", "gemini"])
        self.assertEqual(fila.gerador_da_historia("historia_teste"), "gemini")
        self.assertTrue(any("saiu da roda" in linha for linha in linhas))
        self.assertEqual([k.get("etapa") for _a, k in self.diario],
                         ["imagens.gerador_fora_da_roda"])

    def test_herdado_do_picasso_tambem_passa(self):
        # historia de antes de 03/10: cena sem o campo `gerador` conta como picasso
        dados = fila._meta("historia_teste")
        dados["cenas"] = {"1:1": {"prompt": "scene 1", "arquivo": "x.png"}}
        fila._gravar_meta("historia_teste", dados)
        self.assertEqual(fila.gerador_herdado("historia_teste"), "picasso")
        chamadas = []
        worker.gerar("historia_teste", entregador=self.entregador(chamadas),
                     log=lambda _m: None)
        self.assertTrue(chamadas)
        self.assertNotIn("picasso", {c["para"] for c in chamadas})
        self.assertEqual(fila.gerador_da_historia("historia_teste"), "gemini")

    def test_fixada_num_gerador_da_roda_nao_muda(self):
        fila.definir_gerador_da_historia("historia_teste", "chatgpt")
        chamadas = []
        worker.gerar("historia_teste", entregador=self.entregador(chamadas),
                     log=lambda _m: None)
        self.assertEqual({c["para"] for c in chamadas}, {"chatgpt"})
        self.assertEqual(self.diario, [])

    def test_lista_vazia_nao_abre_o_picasso(self):
        self.config["geradores_imagem"] = []

        def nao_abra(*_a, **_k):
            raise AssertionError("abriu o caminho antigo do PicassoIA")

        anterior = worker._gerar
        worker._gerar = nao_abra
        try:
            with self.assertRaises(worker.NaoRodou):
                worker.gerar("historia_teste", entregador=self.entregador([]),
                             log=lambda _m: None)
        finally:
            worker._gerar = anterior


if __name__ == "__main__":
    unittest.main()
