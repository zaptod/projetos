# -*- coding: utf-8 -*-
"""A Oficina exporta ARMA (16F): peca parada no lugar que o palco procura.

O que este arquivo trava (a arte e gerada aqui, por codigo):

1. O DESTINO: `armas/estilos/<estilo>`, o primeiro candidato de
   `palco/nucleo/biblioteca.gd arma()`.
2. A CENA nas regras de docs/palco/COMO-EDITAR.md §3: a empunhadura cai na
   origem (0, 0) e a ponta em +x, a `comprimento_ref` px -- conferido
   passando os dois pontos da ARTE pela transformacao escrita na cena.
3. O JSON: empunhadura, ponta, comprimento_ref, prova.
4. As recusas: arma em mais de um quadro, sem prova, sem estilo.

O palco esticar a peca ate o comprimento da timeline e o
`palco/testes/test_arma_estica.py` (com o Godot).

Rode da raiz:  python -m pytest painel/test_oficina_armas.py -q -p no:cacheprovider
"""
from __future__ import annotations

import json
import math
import re
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from painel.sprites import exportar
from painel.sprites.receita import processar

MAGENTA = (255, 0, 255, 255)
TOL = 1.5


def espada_em_magenta() -> Image.Image:
    """Uma espada deitada, empunhadura a esquerda e ponta a direita, no
    fundo magenta que o inventario pede (docs/palco/inventario_sprites.md)."""
    img = Image.new("RGBA", (420, 140), MAGENTA)
    d = ImageDraw.Draw(img)
    d.rectangle([20, 62, 90, 78], fill=(112, 80, 46, 255))          # cabo
    d.rectangle([86, 44, 96, 96], fill=(214, 170, 40, 255))         # guarda
    d.polygon([(96, 58), (360, 58), (380, 70), (360, 82), (96, 82)],
              fill=(200, 204, 214, 255))                             # lamina
    return img


def ler_cena(texto: str) -> dict:
    """O que a cena da arma diz da geometria (sem Godot)."""
    ref = float(re.search(r"^comprimento_ref = ([-\d.e]+)$", texto, re.M)[1])
    rot = re.search(r"^rotation = ([-\d.e]+)$", texto, re.M)
    off = re.search(r"^offset = Vector2\(([-\d.e]+), ([-\d.e]+)\)$", texto,
                    re.M)
    return {"ref": ref, "rotacao": float(rot[1]) if rot else 0.0,
            "offset": (float(off[1]), float(off[2]))}


def na_peca(cena: dict, ponto) -> tuple:
    """Ponto da ARTE -> coordenada da peca (Sprite2D sem centro: o ponto p
    da textura fica em p + offset, e a rotacao gira em volta da origem)."""
    x = float(ponto[0]) + cena["offset"][0]
    y = float(ponto[1]) + cena["offset"][1]
    c, s = math.cos(cena["rotacao"]), math.sin(cena["rotacao"])
    return (c * x - s * y, s * x + c * y)


class _ComBiblioteca(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.bib = Path(self._tmp.name)
        (self.bib / "LICENCAS.md").write_text("# Licenças\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def assertPerto(self, a, b, tol=TOL):
        self.assertLessEqual(math.dist(a, b), tol, f"{a} != {b}")


class DestinoDaArma(unittest.TestCase):
    def test_estilo_vira_o_caminho_que_a_biblioteca_procura(self):
        E = exportar.Identidade
        self.assertEqual(exportar.destino_da_cena(
            E(tipo="arma", nome="Machado-Martelo")),
            "armas/estilos/machado_martelo")
        self.assertEqual(exportar.destino_da_cena(
            E(tipo="arma", nome="qualquer", estilo="Espada Longa")),
            "armas/estilos/espada_longa")
        self.assertEqual(exportar.destino_da_cena(E(tipo="arma")), "")
        from painel.janelas import RAIZ
        gd = (RAIZ / "palco" / "nucleo" / "biblioteca.gd").read_text(
            encoding="utf-8")
        self.assertIn('"estilos/" + UtilPalco.slug(estilo)', gd)

    def test_a_oficina_oferece_o_tipo_arma(self):
        self.assertIn("arma", exportar.TIPOS)
        self.assertIn("arma", exportar.ROTULOS_DE_TIPO)
        self.assertEqual(exportar.rotulo_dos_arquivos(exportar.Identidade(
            tipo="arma", nome="Katana")),
            "armas/estilos/katana.png\narmas/estilos/katana.tscn")

    def test_recusas(self):
        E = exportar.Identidade
        ok = E(tipo="arma", nome="Katana", prova="conversa de 01/10")
        self.assertEqual(exportar.problemas(ok, 1), [])
        self.assertTrue(any("UMA peça" in p
                            for p in exportar.problemas(ok, 3)))
        self.assertTrue(any("PROVA" in p for p in exportar.problemas(
            E(tipo="arma", nome="Katana"), 1)))
        self.assertTrue(any("ESTILO" in p for p in exportar.problemas(
            E(tipo="arma", prova="p"), 1)))

    def test_estilo_fora_do_jogo_avisa(self):
        if not exportar.estilos_de_arma():
            self.skipTest("o jogo nao carregou (sem lista de estilos)")
        self.assertIn("Espada Longa", exportar.estilos_de_arma())
        self.assertEqual(exportar.avisos(exportar.Identidade(
            tipo="arma", nome="Espada Longa")), [])
        self.assertTrue(exportar.avisos(exportar.Identidade(
            tipo="arma", nome="Espadinha de Pau")))


class ExportarArma(_ComBiblioteca):
    def setUp(self):
        super().setUp()
        self.res = processar(espada_em_magenta())
        self.ident = exportar.Identidade(
            tipo="arma", nome="Espada Longa", prova="conversa do ChatGPT de "
            "01/10 com o nosso prompt", fonte="espada_teste.png")

    def test_um_quadro_so(self):
        self.assertEqual(len(self.res.alinhado.quadros), 1)

    def test_escreve_png_json_e_cena_onde_o_palco_procura(self):
        feito = exportar.exportar(self.res, self.ident, biblioteca=self.bib)
        base = self.bib / "armas" / "estilos"
        self.assertEqual(Path(feito["cena"]), base / "espada_longa.tscn")
        self.assertEqual(Path(feito["folha"]), base / "espada_longa.png")
        self.assertEqual(Path(feito["metadados"]), base / "espada_longa.json")
        self.assertFalse((self.bib / "efeitos").exists())
        quadro = self.res.alinhado.quadros[0]
        with Image.open(base / "espada_longa.png") as img:
            self.assertEqual(img.mode, "RGBA")
            self.assertEqual(img.size, (quadro.shape[1], quadro.shape[0]))

        meta = json.loads((base / "espada_longa.json").read_text(
            encoding="utf-8"))
        self.assertEqual(meta["tipo"], "arma")
        self.assertEqual(meta["estilo"], "Espada Longa")
        self.assertEqual(meta["cena"], "armas/estilos/espada_longa.tscn")
        self.assertIn("nosso prompt", meta["prova"])
        # a espada vai de x=20 a x=380 (360 px de arte), deitada em y=70
        self.assertAlmostEqual(meta["comprimento_ref"], 361, delta=2)
        ex, ey = meta["empunhadura"]
        px, py = meta["ponta"]
        self.assertAlmostEqual(ey, py, delta=1.0)
        self.assertAlmostEqual(meta["angulo_graus"], 0.0, delta=0.2)
        # a empunhadura e a borda ESQUERDA do desenho, a ponta a DIREITA
        alfa = np.asarray(quadro)[..., 3] >= 16
        colunas = np.nonzero(alfa.any(axis=0))[0]
        self.assertEqual(ex, float(colunas.min()))
        self.assertEqual(px, float(colunas.max() + 1))
        self.assertTrue(alfa[int(ey), int(ex)], "empunhadura fora do cabo")

        texto = (base / "espada_longa.tscn").read_text(encoding="utf-8")
        for trecho in ('path="res://nucleo/peca.gd"',
                       'path="res://biblioteca/armas/estilos/espada_longa.png"',
                       'script = ExtResource("1_peca")',
                       '[node name="Arte" type="Sprite2D" parent="."]',
                       'texture = ExtResource("2_arte")', "centered = false"):
            self.assertIn(trecho, texto)
        cena = ler_cena(texto)
        self.assertAlmostEqual(cena["ref"], meta["comprimento_ref"], 2)
        # a ORIGEM e a empunhadura e a ponta fica em +x, a comprimento_ref
        self.assertPerto(na_peca(cena, (ex, ey)), (0.0, 0.0), 0.01)
        self.assertPerto(na_peca(cena, (px, py)), (cena["ref"], 0.0), 0.05)

        licencas = (self.bib / "LICENCAS.md").read_text(encoding="utf-8")
        self.assertEqual(licencas.count("`armas/estilos/espada_longa.png`"), 1)

    def test_a_cena_aponta_para_o_script_que_existe(self):
        from painel.janelas import RAIZ
        gd = (RAIZ / "palco" / "nucleo" / "peca.gd").read_text(encoding="utf-8")
        self.assertIn("var comprimento_ref", gd)

    def test_ancora_clicada_vira_a_empunhadura(self):
        quadro = self.res.alinhado.quadros[0]
        alfa = np.asarray(quadro)[..., 3] >= 16
        x0 = int(np.nonzero(alfa.any(axis=0))[0].min())
        meio = int(np.nonzero(alfa[:, x0 + 20])[0].mean())
        self.ident.ancora = [x0 + 20, meio]     # a mao no meio do cabo
        exportar.exportar(self.res, self.ident, biblioteca=self.bib)
        meta = json.loads((self.bib / "armas/estilos/espada_longa.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(meta["empunhadura"], [x0 + 20, meio])
        texto = (self.bib / "armas/estilos/espada_longa.tscn").read_text(
            encoding="utf-8")
        cena = ler_cena(texto)
        self.assertPerto(na_peca(cena, meta["empunhadura"]), (0.0, 0.0), 0.01)
        self.assertPerto(na_peca(cena, meta["ponta"]), (cena["ref"], 0.0),
                         0.05)

    def test_ja_existe_pede_confirmacao_e_sem_prova_nao_escreve(self):
        exportar.exportar(self.res, self.ident, biblioteca=self.bib)
        with self.assertRaises(FileExistsError):
            exportar.exportar(self.res, self.ident, biblioteca=self.bib)
        outra = exportar.Identidade(tipo="arma", nome="Katana")
        with self.assertRaises(ValueError):
            exportar.exportar(self.res, outra, biblioteca=self.bib)
        self.assertFalse((self.bib / "armas/estilos/katana.png").exists())


class ArmaTorta(_ComBiblioteca):
    """Arte desenhada inclinada: a cena gira a arte em volta da empunhadura
    ate a ponta cair em +x (a peca sempre aponta para +x)."""

    def test_gira_para_mais_x(self):
        img = Image.new("RGBA", (360, 220), (0, 0, 0, 0))
        ImageDraw.Draw(img).line([(30, 190), (330, 40)],
                                 fill=(200, 204, 214, 255), width=9)
        quadro = np.asarray(img).copy()
        geo = exportar.geometria_da_arma(quadro, (30, 190), (330, 40))
        self.assertAlmostEqual(geo["comprimento_ref"],
                               math.hypot(300, 150), 1)
        ident = exportar.Identidade(tipo="arma", nome="Lança")
        cena = ler_cena(exportar.texto_da_cena_arma(
            ident, "res://biblioteca/armas/estilos/lanca.png", geo))
        self.assertNotEqual(cena["rotacao"], 0.0)
        self.assertPerto(na_peca(cena, (30, 190)), (0.0, 0.0), 0.01)
        self.assertPerto(na_peca(cena, (330, 40)), (cena["ref"], 0.0), 0.05)

    def test_quadro_vazio_e_ponta_na_mao_sao_recusados(self):
        vazio = np.zeros((40, 80, 4), np.uint8)
        with self.assertRaises(ValueError):
            exportar.geometria_da_arma(vazio)
        cheio = np.full((40, 80, 4), 255, np.uint8)
        with self.assertRaises(ValueError):
            exportar.geometria_da_arma(cheio, (10, 10), (11, 11))


if __name__ == "__main__":
    unittest.main()
