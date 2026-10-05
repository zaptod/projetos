# -*- coding: utf-8 -*-
"""Worker das imagens pelo correio, varredura de 05/10/2026 (itens 8, 9 e 18).

- o pedido nasce RESERVADO para o processo do worker e o Carteiro dele nao
  leva a fila do Adrian (`janela_conversa_s: 0`): desde 02/10, 36 de 173
  imagens do PicassoIA tinham sido geradas duas vezes;
- a queda do Chrome nao conta como falha do gerador (trocaria o gerador
  fixado da historia, e o rosto do personagem);
- colagem pelo correio se refaz com o mesmo prompt, como no caminho antigo
  (pedido bffbf4ae: calha em 19% e o reparo culpou o PicassoIA).

Sem navegador: o entregador e um dublê que grava no correio de teste.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from contos.imagens import composicao, fila, worker
from contos.roteiro import roteiro
from ias import correio


def _png(colagem: bool, semente: int = 1) -> bytes:
    """Ruido (cena real: nada liso) com, se `colagem`, uma calha clara no meio."""
    import numpy as np
    from PIL import Image
    gerador = np.random.default_rng(semente)
    pixels = gerador.integers(0, 256, size=(341, 192), dtype=np.uint8)
    if colagem:
        pixels[168:171, :] = 255
    saida = io.BytesIO()
    Image.fromarray(pixels, mode="L").convert("RGB").save(saida, format="PNG")
    return saida.getvalue()


class ImagensPeloCorreioVarredura(unittest.TestCase):

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
            "divisao": "por-historia", "aspect": "9:16",
            "reescrever_com_llm": False, "suavizacao_max": 0,
        }
        worker._ordem_de_geradores = lambda _cfg: ["gemini", "chatgpt", "picasso"]
        roteiro.carregar = lambda _id: {
            "titulo": "Teste", "protagonista": "", "partes": [{"n": 1, "cenas": [
                {"n": 1, "imagem": "scene 1", "tempo": 4, "narracao": "texto"}]}]}

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

    def entregador(self, chamadas, respostas):
        """`respostas`: por pedido, "colagem", "limpa", "sem_prova" ou um erro
        (texto) que vira falha do correio."""
        respostas = list(respostas)

        def entregar(pedido, _prazo):
            chamadas.append(dict(pedido))
            gerador = pedido["para"]
            o_que = respostas.pop(0) if respostas else "limpa"
            if o_que not in ("colagem", "limpa", "sem_prova"):
                return correio.atualizar(gerador, pedido["id"], situacao="falhou",
                                         gerador=gerador, categoria="erro", erro=o_que)
            pasta = correio.pasta_imagens(gerador)
            pasta.mkdir(parents=True, exist_ok=True)
            corpo = _png(o_que == "colagem", semente=len(chamadas))
            (pasta / f"{pedido['id']}.png").write_bytes(corpo)
            comprovada = o_que != "sem_prova"
            (pasta / f"{pedido['id']}.prova.json").write_text(
                json.dumps({"prova": {"comprovada": comprovada, "forca": "duble"}}),
                encoding="utf-8")
            info = {"arquivo": f"{pedido['id']}.png"}
            if comprovada:
                info["prova"] = "turno do duble"
            return correio.atualizar(gerador, pedido["id"], situacao="respondida",
                                     gerador=gerador, imagem=info)

        return entregar

    def _cena(self) -> Path:
        return fila.estado("historia_teste", roteiro.carregar("x"))[0]["arquivo"]

    def test_a_calha_do_teste_e_mesmo_colagem(self):
        alvo = self.raiz / "a.png"
        alvo.write_bytes(_png(True))
        self.assertTrue(composicao.motivo(alvo))
        alvo.write_bytes(_png(False))
        self.assertEqual(composicao.motivo(alvo), "")

    def test_colagem_pelo_correio_se_refaz_com_o_mesmo_prompt(self):
        chamadas = []
        saida = worker.gerar("historia_teste", entregador=self.entregador(
            chamadas, ["colagem", "limpa"]), log=lambda _m: None)
        self.assertEqual(saida["geradas"], 1)
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(chamadas[0]["texto"], chamadas[1]["texto"])   # o MESMO texto
        self.assertEqual({c["para"] for c in chamadas}, {"gemini"})   # o mesmo gerador
        self.assertEqual(composicao.motivo(self._cena()), "")
        cena = fila._meta("historia_teste")["cenas"]["1:1"]
        self.assertEqual(cena["pedido"], chamadas[1]["id"])           # a imagem que ficou
        self.assertEqual(cena["refeita"]["voltas"], 1)
        self.assertFalse(cena["refeita"]["colagem_no_fim"])

    def test_colagem_que_insiste_fica_e_mede(self):
        chamadas = []
        worker.gerar("historia_teste", entregador=self.entregador(
            chamadas, ["colagem", "colagem", "colagem"]), log=lambda _m: None)
        self.assertEqual(len(chamadas), worker.TENTATIVAS_DE_COMPOSICAO)
        self.assertIn(worker.VARIACAO_DA_REFEITA, chamadas[-1]["texto"])
        cena = fila._meta("historia_teste")["cenas"]["1:1"]
        self.assertTrue(cena["refeita"]["variacao"])
        self.assertTrue(cena["refeita"]["colagem_no_fim"])
        self.assertTrue(self._cena().is_file())        # colagem no ar > cena sem imagem

    def test_refeita_sem_prova_deixa_a_imagem_provada(self):
        chamadas = []
        worker.gerar("historia_teste", entregador=self.entregador(
            chamadas, ["colagem", "sem_prova"]), log=lambda _m: None)
        cena = fila._meta("historia_teste")["cenas"]["1:1"]
        self.assertEqual(cena["pedido"], chamadas[0]["id"])
        origem = correio.arquivo_da_imagem("gemini", chamadas[0]["id"])
        self.assertEqual(self._cena().read_bytes(), origem.read_bytes())

    def test_queda_do_chrome_nao_conta_contra_o_gerador(self):
        chamadas = []
        saida = worker.gerar("historia_teste", entregador=self.entregador(
            chamadas, ["TargetClosedError: Target page, context or browser has been closed",
                       "limpa"]), log=lambda _m: None)
        self.assertEqual(saida["geradas"], 1)
        meta = fila._meta("historia_teste")
        self.assertEqual(meta.get("falhas_de_geracao", {}).get("1:1", []), [])
        self.assertEqual(meta["cenas"]["1:1"]["gerador"], "gemini")

    def test_duas_quedas_do_chrome_ficam_no_mesmo_gerador(self):
        # conferencia 05/10/2026: com 2 quedas seguidas no gemini a cena ia para
        # o chatgpt (PARA: gemini, gemini, chatgpt) -- outro rosto
        chamadas = []
        queda = "TargetClosedError: Target page, context or browser has been closed"
        saida = worker.gerar("historia_teste", entregador=self.entregador(
            chamadas, [queda, queda, "limpa"]), log=lambda _m: None)
        self.assertEqual([c["para"] for c in chamadas], ["gemini", "gemini", "gemini"])
        self.assertEqual(saida["geradas"], 1)
        meta = fila._meta("historia_teste")
        self.assertEqual(meta["cenas"]["1:1"]["gerador"], "gemini")
        self.assertEqual(meta.get("falhas_de_geracao", {}).get("1:1", []), [])

    def test_quedas_demais_deixam_a_cena_sem_trocar_de_gerador(self):
        chamadas = []
        queda = "TargetClosedError: Target page, context or browser has been closed"
        saida = worker.gerar("historia_teste", entregador=self.entregador(
            chamadas, [queda] * 10), log=lambda _m: None)
        self.assertEqual([c["para"] for c in chamadas],
                         ["gemini"] * worker.QUEDAS_DO_CHROME_MAX)
        self.assertEqual(saida["geradas"], 0)
        self.assertEqual(saida["faltam"], 1)
        self.assertIn("Chrome caiu", saida["erros"][0])

    def test_falha_de_verdade_ainda_passa_ao_proximo(self):
        chamadas = []
        worker.gerar("historia_teste", entregador=self.entregador(
            chamadas, ["site fora", "site fora", "limpa"]), log=lambda _m: None)
        self.assertEqual([c["para"] for c in chamadas], ["gemini", "gemini", "chatgpt"])

    def test_pedido_nasce_reservado_para_o_worker(self):
        chamadas = []
        worker.gerar("historia_teste", entregador=self.entregador(chamadas, ["limpa"]),
                     log=lambda _m: None)
        self.assertEqual(chamadas[0]["dono"], os.getpid())
        self.assertFalse(correio.reservado_por_outro(chamadas[0]))

    def test_carteiro_do_worker_nao_leva_a_fila_do_adrian(self):
        import ias.carteiro as carteiro_mod
        criados = []

        class _Carteiro:
            def __init__(self, **kw):
                criados.append(kw)

            def entregar(self, pedido):
                return pedido

        original = carteiro_mod.Carteiro
        carteiro_mod.Carteiro = _Carteiro
        try:
            worker._entregar_imagem({"id": "abcdef12"}, 300.0)
        finally:
            carteiro_mod.Carteiro = original
        self.assertEqual(criados[0]["ajustes"]["janela_conversa_s"], 0)
        self.assertEqual(criados[0]["ajustes"]["resposta_timeout_s"], 300.0)


if __name__ == "__main__":
    unittest.main()
