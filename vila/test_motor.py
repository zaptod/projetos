# -*- coding: utf-8 -*-
"""Contratos do motor da Vila (sprites).

O que este arquivo trava:

1. RECORTE. O indice da celula vira o retangulo certo mesmo com margem e
   espaco entre celulas, e um papel de varios tiles (predio 4x3) recorta a
   regiao inteira. Errar aqui = todo sprite sai deslocado.
2. CHAVE DE TRANSPARENCIA. Arte gerada por IA nunca vem transparente;
   `chave: "auto"` apaga a cor do canto (com tolerancia).
3. MUNDO. `compor_mundo` sai no tamanho exato, `variar` e deterministico
   (o cenario nao pode "fervilhar" entre recomposicoes) e papel sem sprite
   e pulado sem derrubar a composicao.
4. FALLBACK dos bots: `bot.<fabrica>.<dir>` vence `bot.<dir>` quando existe.

Rode da raiz do repo:  python -m unittest vila.test_motor -v
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from vila import motor


def _cfg_de_teste(raiz: Path) -> dict:
    """Folha 4x2 celulas de 8px com margem 2 e espaco 1, cores por celula."""
    (raiz / "sprites").mkdir()
    img = Image.new("RGBA", (2 * 2 + 4 * 8 + 3 * 1, 2 * 2 + 2 * 8 + 1 * 1),
                    (255, 0, 255, 255))          # fundo magenta (a chave)
    cores = [(10 + i * 20, 40, 60, 255) for i in range(8)]
    for i, cor in enumerate(cores):
        col, row = i % 4, i // 4
        x0 = 2 + col * 9
        y0 = 2 + row * 9
        for dx in range(8):
            for dy in range(8):
                img.putpixel((x0 + dx, y0 + dy), cor)
    img.save(raiz / "sprites" / "teste.png")
    return {
        "tile": 8, "escala": 1, "fundo": "#000000",
        "folhas": {"teste": {"arquivo": "sprites/teste.png", "tile_w": 8,
                             "tile_h": 8, "margem": 2, "espaco": 1,
                             "chave": None}},
        "papeis": {
            "chao.grama": {"folha": "teste", "frames": [0, 1], "variar": True},
            "predio.picasso": {"folha": "teste", "frames": [0],
                               "larg": 2, "alt": 2},
            "bot.baixo": {"folha": "teste", "frames": [2, 3], "fps": 6},
            "bot.picasso.baixo": {"folha": "teste", "frames": [4], "fps": 6},
        },
        "mapa": None,
    }


class MotorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)
        self.cfg = _cfg_de_teste(self.raiz)
        self.atlas = motor.Atlas(self.cfg, raiz=self.raiz)

    # ------------------------------------------------------------ recorte
    def test_indice_vira_celula_com_margem_e_espaco(self):
        cols, rows = motor.celulas(self.cfg, "teste", (39, 21))
        self.assertEqual((4, 2), (cols, rows))
        spr = self.atlas.sprite("chao.grama", 1)
        self.assertEqual((8, 8), spr.size)
        self.assertEqual((30, 40, 60, 255), spr.getpixel((0, 0)),
                         "frame 1 tem que ser a SEGUNDA celula, nao a margem")

    def test_papel_de_varios_tiles_recorta_a_regiao_inteira(self):
        spr = self.atlas.sprite("predio.picasso")
        self.assertEqual((16, 16), spr.size)

    def test_escala_e_inteira_e_nearest(self):
        spr = self.atlas.sprite("chao.grama", 0, escala=3)
        self.assertEqual((24, 24), spr.size)
        self.assertEqual(spr.getpixel((0, 0)), spr.getpixel((2, 2)),
                         "NEAREST nao inventa cor nova")

    def test_chave_auto_apaga_o_fundo(self):
        self.cfg["folhas"]["teste"]["chave"] = "auto"
        self.atlas.limpar()
        folha = self.atlas.folha("teste")
        self.assertEqual(0, folha.getpixel((0, 0))[3],
                         "o magenta do canto tinha que sumir")
        self.assertEqual(255, folha.getpixel((2, 2))[3],
                         "a celula de verdade nao pode sumir junto")

    # -------------------------------------------------------------- papeis
    def test_bot_da_fabrica_vence_o_generico(self):
        geral = motor.frames_de(self.cfg, "bot.baixo")
        proprio = motor.frames_de(self.cfg, "bot.baixo", fabrica="picasso")
        self.assertEqual([2, 3], geral["frames"])
        self.assertEqual([4], proprio["frames"])
        sem = motor.frames_de(self.cfg, "bot.baixo", fabrica="digen")
        self.assertEqual([2, 3], sem["frames"], "sem proprio, cai no generico")

    def test_variar_e_deterministico(self):
        a = motor.variar_frame(4, 7, 11)
        self.assertEqual(a, motor.variar_frame(4, 7, 11))
        self.assertEqual(0, motor.variar_frame(1, 7, 11))

    # --------------------------------------------------------------- mundo
    def test_compor_mundo_no_tamanho_exato(self):
        self.cfg["mapa"] = motor.mapa_novo(5, 3, ["chao.grama"])
        mundo = motor.compor_mundo(self.cfg, self.atlas, escala=2)
        self.assertEqual((5 * 8 * 2, 3 * 8 * 2), mundo.size)

    def test_papel_sem_sprite_nao_derruba_a_composicao(self):
        self.cfg["mapa"] = motor.mapa_novo(3, 3, ["chao.grama"])
        self.cfg["mapa"]["decor"] = [{"x": 0, "y": 0, "papel": "decor.fantasma"}]
        self.cfg["mapa"]["predios"] = {"digen": {"x": 1, "y": 1}}
        mundo = motor.compor_mundo(self.cfg, self.atlas, escala=1)
        self.assertEqual((24, 24), mundo.size)

    # -------------------------------------------------------------- config
    def test_salvar_e_carregar_roundtrip(self):
        caminho = self.raiz / "config.json"
        self.cfg["mapa"] = motor.mapa_novo(4, 4, ["chao.grama"])
        motor.salvar(self.cfg, caminho)
        de_novo = motor.carregar(caminho)
        self.assertEqual(self.cfg["papeis"], de_novo["papeis"])
        self.assertEqual(self.cfg["mapa"]["chao"], de_novo["mapa"]["chao"])

    def test_carregar_sem_arquivo_da_o_padrao(self):
        cfg = motor.carregar(self.raiz / "nao_existe.json")
        self.assertEqual(motor.PADRAO["tile"], cfg["tile"])
        self.assertFalse(motor.pronto(cfg))

    def test_pronto_exige_mapa_folha_e_chao(self):
        self.assertFalse(motor.pronto(self.cfg))          # sem mapa
        self.cfg["mapa"] = motor.mapa_novo(2, 2, ["chao.grama"])
        self.assertTrue(motor.pronto(self.cfg))
        sem_chao = dict(self.cfg)
        sem_chao["papeis"] = {"predio.digen": {"folha": "teste", "frames": [0]}}
        self.assertFalse(motor.pronto(sem_chao))


if __name__ == "__main__":
    unittest.main()
