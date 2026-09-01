# -*- coding: utf-8 -*-
"""Contratos da âncora de estilo e da divisão entre dois geradores.

Com DOIS sites gerando as imagens da mesma história, o risco novo não é a
fila travar — é o **estilo trocar no meio**. Dois modelos diferentes, com o
mesmo texto, entregam luz, cor e traço diferentes.

O que este arquivo trava:

1. DIVISÃO POR PARTE, nunca por cena. Cada parte é um vídeo inteiro; se os
   geradores se revezassem cena a cena, a diferença entre eles apareceria
   a cada troca de imagem DENTRO do mesmo vídeo. Por parte, o vídeo sai
   coerente e a diferença cai entre vídeos vistos em dias diferentes.
2. ESTILO CONGELADO. Mexer no config no meio de uma história de 140 cenas
   não pode mudar o visual das cenas que faltam.
3. A ÂNCORA aparece sozinha na primeira imagem boa, e não se perde depois.

Rode de dentro de historias/:
    python -m unittest tests.test_referencia_regressions -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.imagens import referencia                              # noqa: E402


def _cenas(por_parte: dict) -> list:
    saida = []
    for parte, quantas in por_parte.items():
        saida += [{"parte": parte, "n": i} for i in range(1, quantas + 1)]
    return saida


class DivisaoTests(unittest.TestCase):
    def test_cada_parte_fica_com_UM_gerador(self):
        divisao = referencia.dividir_por_parte(
            _cenas({1: 14, 2: 14, 3: 14}), ["picasso", "dreamface"])
        for provedor, linhas in divisao.items():
            for parte in {l["parte"] for l in linhas}:
                donos = {p for p, ls in divisao.items()
                         if any(l["parte"] == parte for l in ls)}
                self.assertEqual({provedor}, donos,
                                 f"a parte {parte} ficou com dois geradores")

    def test_as_partes_se_alternam_para_os_dois_trabalharem_juntos(self):
        divisao = referencia.dividir_por_parte(
            _cenas({1: 2, 2: 2, 3: 2, 4: 2}), ["a", "b"])
        self.assertEqual({1, 3}, {l["parte"] for l in divisao["a"]})
        self.assertEqual({2, 4}, {l["parte"] for l in divisao["b"]})

    def test_nenhuma_cena_se_perde_nem_se_repete(self):
        cenas = _cenas({1: 5, 2: 7, 3: 3})
        divisao = referencia.dividir_por_parte(cenas, ["a", "b"])
        juntas = [l for linhas in divisao.values() for l in linhas]
        self.assertEqual(len(cenas), len(juntas))
        chaves = {(l["parte"], l["n"]) for l in juntas}
        self.assertEqual(len(cenas), len(chaves))

    def test_um_gerador_so_leva_tudo(self):
        cenas = _cenas({1: 3, 2: 3})
        self.assertEqual({"picasso": cenas},
                         referencia.dividir_por_parte(cenas, ["picasso"]))

    def test_sem_gerador_nenhum_devolve_vazio(self):
        self.assertEqual({}, referencia.dividir_por_parte(_cenas({1: 2}), []))
        self.assertEqual({}, referencia.dividir_por_parte(_cenas({1: 2}), None))

    def test_lista_vazia_nao_quebra(self):
        divisao = referencia.dividir_por_parte([], ["a", "b"])
        self.assertEqual({"a": [], "b": []}, divisao)

    def test_uma_parte_so_nao_e_repartida(self):
        """Uma parte inteira num gerador — nunca meia parte em cada."""
        divisao = referencia.dividir_por_parte(_cenas({7: 14}), ["a", "b"])
        cheios = [p for p, ls in divisao.items() if ls]
        self.assertEqual(1, len(cheios))
        self.assertEqual(14, len(divisao[cheios[0]]))


class EstiloCongeladoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._outputs = referencia.OUTPUTS
        referencia.OUTPUTS = Path(self._tmp.name)
        self.addCleanup(lambda: setattr(referencia, "OUTPUTS", self._outputs))
        (Path(self._tmp.name) / "h1").mkdir()

    def test_congela_no_primeiro_uso(self):
        primeiro = referencia.estilo("h1", {"estilo": "cinematic, 35mm",
                                            "aspect": "9:16"})
        self.assertEqual("cinematic, 35mm", primeiro["estilo"])
        self.assertTrue(referencia.caminho_estilo("h1").is_file())

    def test_mudar_o_config_depois_NAO_muda_a_historia(self):
        referencia.estilo("h1", {"estilo": "cinematic, 35mm"})
        depois = referencia.estilo("h1", {"estilo": "anime, flat colors"})
        self.assertEqual("cinematic, 35mm", depois["estilo"],
                         "a historia mudou de visual no meio")

    def test_arquivo_corrompido_recongelamento(self):
        referencia.caminho_estilo("h1").write_text("{nao e json",
                                                   encoding="utf-8")
        novo = referencia.estilo("h1", {"estilo": "cinematic"})
        self.assertEqual("cinematic", novo["estilo"])

    def test_o_arquivo_explica_por_que_existe(self):
        referencia.estilo("h1", {"estilo": "x"})
        with open(referencia.caminho_estilo("h1"), encoding="utf-8") as fh:
            self.assertIn("Congelado", json.load(fh)["_comment"])


class AncoraTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)
        self._outputs = referencia.OUTPUTS
        referencia.OUTPUTS = self.raiz
        self.addCleanup(lambda: setattr(referencia, "OUTPUTS", self._outputs))
        (self.raiz / "h1").mkdir()

    def _imagem(self, nome: str, bytes_=20_000) -> Path:
        alvo = self.raiz / nome
        alvo.write_bytes(b"\x89PNG" + b"0" * bytes_)
        return alvo

    def test_adota_a_primeira_imagem_boa(self):
        a, b = self._imagem("a.png"), self._imagem("b.png")
        escolhida = referencia.adotar_primeira("h1", [a, b])
        self.assertEqual(referencia.caminho("h1"), escolhida)
        self.assertTrue(referencia.tem_referencia("h1"))

    def test_nao_troca_a_ancora_depois(self):
        """Trocar a referencia no meio derrubaria a consistencia inteira."""
        primeira = self._imagem("a.png")
        referencia.adotar_primeira("h1", [primeira])
        antes = referencia.caminho("h1").read_bytes()
        referencia.adotar_primeira("h1", [self._imagem("b.png", 30_000)])
        self.assertEqual(antes, referencia.caminho("h1").read_bytes())

    def test_ignora_arquivo_quebrado(self):
        ruim = self.raiz / "ruim.png"
        ruim.write_bytes(b"curto")
        boa = self._imagem("boa.png")
        referencia.adotar_primeira("h1", [ruim, boa])
        self.assertTrue(referencia.tem_referencia("h1"))

    def test_sem_imagem_nenhuma_devolve_none(self):
        self.assertIsNone(referencia.adotar_primeira("h1", []))
        self.assertFalse(referencia.tem_referencia("h1"))

    def test_definir_escolhe_a_dedo(self):
        escolhida = self._imagem("escolhida.png")
        referencia.definir("h1", escolhida)
        self.assertTrue(referencia.tem_referencia("h1"))

    def test_definir_imagem_inexistente_avisa(self):
        with self.assertRaises(FileNotFoundError):
            referencia.definir("h1", self.raiz / "fantasma.png")


if __name__ == "__main__":
    unittest.main()
