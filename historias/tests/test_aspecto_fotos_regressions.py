# -*- coding: utf-8 -*-
"""Fotos 1:1 na metade de cima, e fim do estilo Pixar (14/09/2026).

Pedidos dele: "nao gostei como ficou o 9:16 nesse modelo, quero algo que
encaixe bem" (escolheu 1:1) e "abandone completamente essa ideia da pixar".

Rode de dentro de historias/:
    python -m unittest tests.test_aspecto_fotos_regressions -v
"""
from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from contos.imagens import fila, worker
from contos.pipeline import controller
from contos.video import capa, formato, timeline

RAIZ = Path(__file__).resolve().parents[1]


class AspectoDaHistoriaTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name) / "historia_00077"
        self.pasta.mkdir()
        self.cfg = {"formato": {"velocidade": 1.5, "layout": "dividido",
                                "aspecto": "1:1"}}

    def _plano(self, parte, dados):
        destino = self.pasta / "partes" / f"p{parte:02d}"
        destino.mkdir(parents=True)
        (destino / "edit_plan.json").write_text(json.dumps(dados),
                                                encoding="utf-8")

    def test_historia_nova_segue_o_render_json(self):
        self.assertEqual("1:1", formato.resolver("h", self.cfg,
                                                 self.pasta)["aspecto"])

    def test_historia_antiga_fica_9_16(self):
        self._plano(1, {"events": []})
        self.assertEqual("9:16", formato.resolver("h", self.cfg,
                                                  self.pasta)["aspecto"])

    def test_formato_json_converte_uma_historia(self):
        """A historia 12: fotos refeitas em 1:1 por pedido dele."""
        self._plano(1, {"formato": {"velocidade": 1.5, "layout": "dividido"}})
        (self.pasta / "formato.json").write_text(json.dumps(
            {"velocidade": 1.5, "layout": "dividido", "aspecto": "1:1"}),
            encoding="utf-8")
        self.assertEqual("1:1", formato.resolver("h", {}, self.pasta)["aspecto"])

    def test_o_plano_guarda_a_proporcao_para_o_reparo(self):
        self._plano(1, {"formato": {"velocidade": 1.5, "layout": "dividido"},
                        "aspecto_imagem": "1:1"})
        self.assertEqual("1:1", formato.resolver("h", {}, self.pasta)["aspecto"])

    def test_aplicar_formato_grava_a_proporcao_no_plano(self):
        antes = controller._rb_atividade.registrar
        self.addCleanup(setattr, controller._rb_atividade, "registrar", antes)
        controller._rb_atividade.registrar = lambda *a, **k: None
        plano, _ = controller.aplicar_formato(
            {"total_duration": 10.0, "events": []},
            {"velocidade": 1.0, "layout": "vertical", "aspecto": "1:1"},
            {}, historia_id="h", parte=1, log=lambda *_a: None)
        self.assertEqual("1:1", plano["aspecto_imagem"])

    def test_valor_desconhecido_vira_9_16(self):
        self.assertEqual("9:16", formato.aspecto("5:7"))
        self.assertEqual("9:16", formato.aspecto(None))


class ProporcaoDaImagemTests(unittest.TestCase):

    def _png(self, tamanho):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        caminho = Path(tmp.name) / "c.png"
        Image.new("RGB", tamanho, (90, 90, 90)).save(caminho)
        return caminho

    def test_quadrada_serve_para_1_1_e_nao_para_9_16(self):
        quadrada = self._png((1088, 1088))
        self.assertTrue(fila.proporcao_ok(quadrada, "1:1"))
        self.assertFalse(fila.proporcao_ok(quadrada, "9:16"))

    def test_retrato_nao_serve_para_1_1(self):
        retrato = self._png((1088, 1920))
        self.assertFalse(fila.proporcao_ok(retrato, "1:1"))
        self.assertTrue(fila.proporcao_ok(retrato, "9:16"))

    def test_quem_decide_pronta_usa_a_proporcao_da_historia(self):
        self.assertIn("aspecto_da_historia(",
                      inspect.getsource(fila.estado))
        self.assertIn("aspecto_da_historia(",
                      inspect.getsource(timeline.montar))
        self.assertIn("utilizavel(arquivo, aspecto)",
                      inspect.getsource(timeline.montar))
        self.assertIn('config["aspect"] = fila.aspecto_da_historia(',
                      inspect.getsource(worker.gerar))


class PromptSemPixarTests(unittest.TestCase):

    def test_o_molde_quebrada_nao_tem_mais_estilo_pixar(self):
        texto = (RAIZ / "config" / "roteiro.json").read_text(encoding="utf-8")
        self.assertNotIn("Pixar", texto)
        self.assertNotIn("3D cartoon", texto)
        moldes = json.loads(texto)["modelos"]
        self.assertNotIn("estilo_imagem", moldes["quebrada"])

    def test_enquadramento_acompanha_a_proporcao(self):
        cena = {"imagem": "a woman holding a pink pressure cooker"}
        quadrado = fila.prompt_da_cena(cena, {"estilo": "photo", "aspect": "1:1"})
        retrato = fila.prompt_da_cena(cena, {"estilo": "photo", "aspect": "9:16"})
        self.assertIn("square composition", quadrado)
        self.assertNotIn("vertical composition", quadrado)
        self.assertIn("vertical composition", retrato)

    def test_a_barra_do_personagem_vira_virgula(self):
        """"A | B" era lido como folha de personagens e saia em diptico
        (historia_00012 p01_cena_03, 14/09/2026 23:53)."""
        cena = {"imagem": "Suelen | blonde woman in pink, pointing at Rosa | "
                          "curly-haired woman in a yellow apron"}
        prompt = fila.prompt_da_cena(cena, {"estilo": "photo", "aspect": "1:1"})
        self.assertNotIn("|", prompt)
        self.assertIn("Suelen, blonde woman in pink", prompt)
        self.assertIn("one continuous photograph", prompt)
        self.assertNotIn("subject centered", prompt)

    def test_protagonista_com_barra_nao_sai_repetido(self):
        cena = {"imagem": "Tiago | a man with a red scarf, opening a door"}
        prompt = fila.prompt_da_cena(cena, {"estilo": "photo"},
                                     "Tiago | a man with a red scarf")
        self.assertEqual(1, prompt.lower().count("a man with a red scarf"))

    def test_o_estilo_padrao_nao_fixa_enquadramento_vertical(self):
        self.assertNotIn("vertical composition",
                         fila.carregar_config().get("estilo", ""))


class CapaComFotoQuadradaTests(unittest.TestCase):

    def test_foto_quadrada_entra_inteira_na_capa(self):
        """Recortar 1:1 para 9:16 jogaria fora quase metade da largura."""
        imagem = Image.new("RGB", (1088, 1088), (200, 40, 40))
        imagem.paste(Image.new("RGB", (100, 1088), (20, 20, 230)), (0, 0))
        base = capa._preencher(imagem)
        self.assertEqual((1080, 1920), base.size)
        azuis = [p for p in base.crop((0, 0, 200, 1920)).getdata()
                 if p[2] > 180 and p[0] < 80]
        self.assertGreater(len(azuis), 1000, "a lateral da foto foi cortada")


class PicassoConfereAProporcaoTests(unittest.TestCase):

    def test_pedido_vertical_aceita_qualquer_vertical(self):
        from builds.identity import picasso_client as pc
        self.assertTrue(pc.proporcao_confere("9:16", "3:4"))
        self.assertFalse(pc.proporcao_confere("9:16", "1:1"))

    def test_pedido_quadrado_precisa_ser_quadrado(self):
        from builds.identity import picasso_client as pc
        self.assertTrue(pc.proporcao_confere("1:1", "1:1"))
        self.assertFalse(pc.proporcao_confere("1:1", "9:16"))


if __name__ == "__main__":
    unittest.main()
