# -*- coding: utf-8 -*-
"""A refeita por colagem varia o enquadramento da 2a volta em diante.

17/09/2026, EXPERIMENTO: na historia_00018 p04_cena_03 ("as duas face a
face") as tres tentativas com o MESMO texto voltaram com a mesma calha em
~49%. Medido no acervo (1336 imagens): colagem e 3% no total e 0,17% nas
historias novas, e o gatilho antigo (duas descricoes fisicas completas num
prompt so, 14,8%) ja foi consertado. Nao ha caso de refeita por colagem que
tenha dado certo, entao isto e hipotese — e o que estes testes travam e o
MECANISMO e o REGISTRO que vao permitir julga-la com dado.
"""
from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path

from contos.imagens import fila
from contos.imagens import worker as W

PROMPT = ("Dona Neide and Katia Regina standing face to face in the living "
          "room, cinematic photography, no collage")


class VariacaoDoEnquadramento(unittest.TestCase):

    def test_soma_sem_perder_o_pedido(self):
        novo = W.variar_enquadramento(PROMPT)
        self.assertTrue(novo.startswith(PROMPT))
        self.assertIn(W.VARIACAO_DA_REFEITA, novo)

    def test_nao_repete_se_ja_tem(self):
        uma = W.variar_enquadramento(PROMPT)
        self.assertEqual(uma, W.variar_enquadramento(uma))

    def test_prompt_vazio_continua_vazio(self):
        self.assertEqual("", W.variar_enquadramento(""))
        self.assertEqual("", W.variar_enquadramento(None))

    def test_a_primeira_volta_repete_o_texto_e_a_segunda_varia(self):
        fonte = inspect.getsource(W.gerar.__wrapped__
                                  if hasattr(W.gerar, "__wrapped__")
                                  else W._gerar)
        self.assertIn("com_variacao = volta >= 2", fonte)
        self.assertIn("pedido = (variar_enquadramento(tentativa)", fonte)
        # O pedido variado e que vai para o gerador, nao o original.
        self.assertIn("cliente, pedido, config, ajustes, log", fonte)

    def test_o_experimento_esta_datado_e_marcado_como_hipotese(self):
        doc = inspect.getsource(W)[:inspect.getsource(W).index("def ")]
        constante = inspect.getsource(W).split("VARIACAO_DA_REFEITA")[0]
        self.assertIn("EXPERIMENTO SEM MEDIDA (17/09/2026)", constante + doc)
        self.assertIn("HIPOTESE", (constante + doc).upper())


class RegistroParaMedirDepois(unittest.TestCase):
    """Sem registro, o experimento nunca poderia ser julgado — so lembrado."""

    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name)
        original = fila.pasta_da_historia
        fila.pasta_da_historia = lambda _h: self.raiz
        self.addCleanup(setattr, fila, "pasta_da_historia", original)

    def _registrar(self, refeita):
        fila.registrar("historia_teste", 3, prompt=PROMPT,
                       arquivo=self.raiz / "p04_cena_03.png",
                       prova={"comprovada": True}, url="u", parte=4,
                       refeita=refeita)
        return json.loads((self.raiz / "imagens.json")
                          .read_text(encoding="utf-8"))["cenas"]["4:3"]

    def test_grava_voltas_variacao_e_resultado(self):
        cena = self._registrar({"voltas": 2, "variacao": True,
                                "colagem_no_fim": False})
        self.assertEqual({"voltas": 2, "variacao": True,
                          "colagem_no_fim": False}, cena["refeita"])

    def test_cena_sem_refeita_nao_ganha_o_campo(self):
        self.assertNotIn("refeita", self._registrar(None))

    def test_o_worker_registra_no_diario_e_no_json(self):
        fonte = inspect.getsource(W)
        self.assertIn('etapa="imagens.refeita"', fonte)
        self.assertIn('refeita["colagem_no_fim"] = bool(', fonte)
        self.assertIn("refeita=refeita if refeita", fonte)


if __name__ == "__main__":
    unittest.main()
