# -*- coding: utf-8 -*-
"""O render da tela dividida (14/09/2026).

Em cima, o painel da historia (imagem, camera, titulo, legenda); embaixo, um
trecho do video de fundo, mudo. Nenhum teste antigo desenhava um quadro, entao
nada prendia tamanho de tela nem posicao de legenda — estes prendem.

Rode de dentro de historias/:
    python -m unittest tests.test_formato_render_regressions -v
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from contos.video import formato, renderer, timeline

RENDER = timeline.carregar_config("render.json")
DIVIDIDO = {"velocidade": 1.7, "layout": "dividido"}


class TamanhosTests(unittest.TestCase):

    def test_dividido_desenha_no_painel_de_cima_sem_encolher_a_letra(self):
        r = renderer.VideoRenderer(RENDER, "celular", formato=DIVIDIDO)
        self.assertTrue(r.dividido)
        self.assertEqual((1080, 960), (r.width, r.height))
        self.assertEqual((1080, 1920), (r.saida_w, r.saida_h))
        self.assertEqual(1080, r.ref)

    def test_preview_divide_na_mesma_proporcao(self):
        r = renderer.VideoRenderer(RENDER, "celular", preview=True,
                                   formato=DIVIDIDO)
        self.assertEqual((540, 480), (r.width, r.height))
        self.assertEqual(960, r.saida_h)

    def test_formato_antigo_fica_como_sempre(self):
        for f in (None, formato.LEGADO):
            r = renderer.VideoRenderer(RENDER, "celular", formato=f)
            self.assertFalse(r.dividido)
            self.assertEqual((1080, 1920), (r.width, r.height))
            self.assertEqual("conter", r.ajuste)
            self.assertEqual(float(RENDER["legenda"]["y"]), r.legenda_y)

    def test_tela_deitada_nao_divide(self):
        r = renderer.VideoRenderer(RENDER, "normal", formato=DIVIDIDO)
        self.assertFalse(r.dividido)
        self.assertEqual((1920, 1080), (r.width, r.height))

    def test_legenda_fica_dentro_do_painel(self):
        r = renderer.VideoRenderer(RENDER, "celular", formato=DIVIDIDO)
        tamanho = int(r.ref * float(RENDER["legenda"]["tamanho"]))
        self.assertLess(r.height * r.legenda_y + tamanho * 1.1, r.height)


class CobrirTests(unittest.TestCase):

    def test_a_imagem_vertical_enche_o_painel(self):
        with tempfile.TemporaryDirectory() as tmp:
            imagem = Path(tmp) / "cena.png"
            Image.new("RGB", (1088, 1920), (200, 30, 30)).save(imagem)
            r = renderer.VideoRenderer(RENDER, "celular", preview=True,
                                       formato=DIVIDIDO)
            evento = {"type": "cena", "n": 1, "start": 0.0, "duration": 0.2,
                      "arquivo": str(imagem), "narracao": "x",
                      "camera": {"zoom": [1.0, 1.15],
                                 "centro": [[0.5, 0.46], [0.54, 0.52]]}}
            quadros = list(r._cena_frames(evento))
        self.assertTrue(quadros)
        for quadro in quadros:
            self.assertEqual((540, 480), quadro.size)
        # Sem faixa borrada nas laterais: a borda e a propria imagem.
        r0, _g, _b = quadros[-1].getpixel((2, 240))
        self.assertGreater(r0, 60)


class EncaixarTests(unittest.TestCase):
    """Pedido dele em 14/09/2026: a foto inteira na metade de cima."""

    def test_topo_e_pe_da_imagem_aparecem_em_todo_quadro(self):
        with tempfile.TemporaryDirectory() as tmp:
            imagem = Image.new("RGB", (1088, 1920), (120, 120, 120))
            faixa = Image.new("RGB", (1088, 120), (20, 230, 20))
            imagem.paste(faixa, (0, 0))
            imagem.paste(Image.new("RGB", (1088, 120), (20, 20, 230)),
                         (0, 1800))
            caminho = Path(tmp) / "cena.png"
            imagem.save(caminho)
            cfg = json.loads(json.dumps(RENDER))
            cfg.setdefault("formato", {})["ajuste_imagem"] = "encaixar"
            # Vinheta e clarao mudam a COR das bordas e dos primeiros quadros;
            # o que se mede aqui e so se a imagem inteira aparece.
            cfg["camera"]["vinheta"] = 0
            cfg["camera"]["flash_frames"] = 0
            r = renderer.VideoRenderer(cfg, "celular", preview=True,
                                       formato=DIVIDIDO)
            self.assertEqual("encaixar", r.ajuste)
            evento = {"type": "cena", "n": 1, "start": 0.0, "duration": 0.3,
                      "arquivo": str(caminho), "narracao": "x",
                      "camera": {"zoom": [1.0, 1.15],
                                 "centro": [[0.5, 0.46], [0.54, 0.52]]}}
            quadros = list(r._cena_frames(evento))

        def tem(quadro, cor):
            alvo = [p for p in quadro.getdata()
                    if all(abs(a - b) < 45 for a, b in zip(p, cor))]
            return len(alvo) > 50

        self.assertTrue(quadros)
        for quadro in quadros:
            self.assertEqual((540, 480), quadro.size)
            self.assertTrue(tem(quadro, (20, 230, 20)), "o topo foi cortado")
            self.assertTrue(tem(quadro, (20, 20, 230)), "o pe foi cortado")

    def test_render_json_pede_a_imagem_inteira(self):
        self.assertEqual("encaixar", RENDER["formato"]["ajuste_imagem"])


def _ffmpeg(*args) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True,
                   capture_output=True)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "sem ffmpeg")
class ComporTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        self.r = renderer.VideoRenderer(RENDER, "celular", preview=True,
                                        formato=DIVIDIDO)
        # O painel: 1,5 s vermelho, com audio mudo, como sai do `_concat`.
        self.cima = self.pasta / "concat.mp4"
        _ffmpeg("-f", "lavfi", "-i", "color=c=red:s=540x480:d=1.5:r=24",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", str(self.cima))
        # O fundo: deitado, sem audio, azul.
        self.fundo = self.pasta / "fundo.mp4"
        _ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=1920x1080:d=6:r=30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(self.fundo))

    def _plano(self, **fundo):
        dados = {"arquivo": str(self.fundo), "offset_s": 2.0}
        dados.update(fundo)
        return {"total_duration": 1.5, "fundo": dados}

    def _probe(self, caminho: Path) -> dict:
        saida = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:format_tags=comment:stream=codec_type,width,height",
             "-of", "json", str(caminho)], capture_output=True, text=True)
        return json.loads(saida.stdout)

    def _quadro(self, caminho: Path) -> Image.Image:
        png = self.pasta / "q.png"
        _ffmpeg("-ss", "0.7", "-i", str(caminho), "-frames:v", "1", str(png))
        with Image.open(png) as imagem:
            return imagem.convert("RGB")

    def test_historia_em_cima_fundo_embaixo_e_duracao_do_painel(self):
        destino = self.pasta / "dividido.mp4"
        self.r._compor_dividido(self.cima, self._plano(), destino)
        info = self._probe(destino)
        video = [s for s in info["streams"] if s["codec_type"] == "video"][0]
        self.assertEqual((540, 960), (video["width"], video["height"]))
        self.assertTrue(any(s["codec_type"] == "audio" for s in info["streams"]))
        self.assertAlmostEqual(1.5, float(info["format"]["duration"]), delta=0.15)
        quadro = self._quadro(destino)
        r1, _g1, b1 = quadro.getpixel((270, 200))
        r2, _g2, b2 = quadro.getpixel((270, 760))
        self.assertGreater(r1, 150)
        self.assertLess(b1, 80)
        self.assertGreater(b2, 150)
        self.assertLess(r2, 80)

    def test_fundo_curto_repete_em_vez_de_acabar(self):
        curto = self.pasta / "curto.mp4"
        _ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=640x360:d=0.5:r=30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(curto))
        destino = self.pasta / "dividido.mp4"
        self.r._compor_dividido(self.cima, self._plano(
            arquivo=str(curto), offset_s=0.0, repetir=True), destino)
        self.assertAlmostEqual(1.5, float(self._probe(destino)["format"]
                                          ["duration"]), delta=0.15)

    def test_sem_arquivo_de_fundo_e_erro_e_nao_video_pela_metade(self):
        with self.assertRaises(RuntimeError):
            self.r._compor_dividido(self.cima, {"fundo": {}},
                                    self.pasta / "x.mp4")

    def test_o_mp4_final_diz_como_foi_feito(self):
        destino = self.pasta / "dividido.mp4"
        self.r._compor_dividido(self.cima, self._plano(), destino)
        # Com voz, como todo render de verdade: so silencio digital faz o aac
        # recusar o quadro e a mixagem cair para "video sem trilha".
        voz = self.pasta / "voz.wav"
        _ffmpeg("-f", "lavfi", "-i", "sine=frequency=220:duration=1.5",
                "-ar", "44100", "-ac", "2", str(voz))
        final = self.pasta / "final.mp4"
        self.r._mix_final(destino, None, voz, final)
        comentario = self._probe(final)["format"]["tags"]["comment"]
        self.assertEqual(DIVIDIDO, formato.ler_rotulo(comentario))


if __name__ == "__main__":
    unittest.main()
