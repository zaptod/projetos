# -*- coding: utf-8 -*-
"""O controller aplica o formato antes de o plano ir para o disco (14/09/2026).

Rode de dentro de historias/:
    python -m unittest tests.test_formato_controller_regressions -v
"""
from __future__ import annotations

import inspect
import json
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from contos.pipeline import controller
from contos.video import timeline

RENDER = timeline.carregar_config("render.json")
DIVIDIDO = {"velocidade": 1.7, "layout": "dividido"}
LEGADO = {"velocidade": 1.0, "layout": "vertical"}


def _plano():
    return {"total_duration": 34.0, "events": [
        {"type": "cena", "n": 1, "start": 0.0, "duration": 17.0,
         "fala_medida": 17.0, "narracao": "um", "titulo": "T",
         "titulo_duracao": 2.2},
        {"type": "cena", "n": 2, "start": 17.0, "duration": 17.0,
         "fala_medida": 17.0, "narracao": "dois"}]}


class _Base(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        # O diario de atividade vai para o bot e para o apurador: nada de
        # aviso de teste chegando no Telegram.
        self.avisos = []
        antes = controller._rb_atividade.registrar
        self.addCleanup(setattr, controller._rb_atividade, "registrar", antes)
        controller._rb_atividade.registrar = (
            lambda *a, **_k: self.avisos.append(a))

    def _cfg(self, **formato):
        cfg = json.loads(json.dumps(RENDER))
        cfg["formato"] = {**cfg.get("formato", {}), **formato}
        return cfg

    def _aplicar(self, pedido, cfg, **kw):
        return controller.aplicar_formato(
            _plano(), pedido, cfg, historia_id="historia_00077", parte=2,
            log=lambda *_a: None, **kw)


class FormatoAntigoTests(_Base):

    def test_formato_antigo_so_carimba_o_plano(self):
        plano, efetivo = self._aplicar(LEGADO, self._cfg())
        self.assertEqual(LEGADO, efetivo)
        self.assertEqual(34.0, plano["total_duration"])
        self.assertNotIn("fundo", plano)
        self.assertEqual(LEGADO, plano["formato"])
        self.assertEqual(LEGADO, plano["formato_efetivo"])


class SemFundoTests(_Base):

    def test_video_de_fundo_ausente_sai_na_tela_inteira(self):
        cfg = self._cfg(fundo_video={"arquivo": str(self.pasta / "nao.mp4")})
        plano, efetivo = self._aplicar({"velocidade": 1.0,
                                        "layout": "dividido"}, cfg)
        self.assertEqual("vertical", efetivo["layout"])
        self.assertEqual("dividido", plano["formato"]["layout"])
        self.assertNotIn("fundo", plano)
        self.assertTrue(self.avisos)
        self.assertEqual("aviso", self.avisos[0][1])


def _tom(caminho: Path, segundos: float = 3.4, taxa: int = 44100) -> None:
    import numpy as np
    t = np.arange(int(segundos * taxa)) / taxa
    mono = (0.4 * np.sin(2 * np.pi * 220 * t) * 32767).astype(np.int16)
    with wave.open(str(caminho), "wb") as fh:
        fh.setnchannels(2)
        fh.setsampwidth(2)
        fh.setframerate(taxa)
        fh.writeframes(np.stack([mono, mono], axis=1).tobytes())


@unittest.skipUnless(shutil.which("ffmpeg"), "sem ffmpeg")
class FormatoNovoTests(_Base):

    def setUp(self):
        super().setUp()
        self.voz = self.pasta / "voz.wav"
        _tom(self.voz)
        self.palavras = self.pasta / "voz_palavras.json"
        self.palavras.write_text(json.dumps(
            [{"t0": 17.0, "t1": 18.7, "texto": "dois", "linha": 1}]),
            encoding="utf-8")
        self.fundo = self.pasta / "fundo.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=blue:s=320x180:d=90:r=5", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", str(self.fundo)],
                       check=True, capture_output=True)

    def test_acelera_escolhe_o_fundo_e_carimba(self):
        cfg = self._cfg(fundo_video={"arquivo": str(self.fundo),
                                     "margem_inicio_s": 5,
                                     "margem_fim_s": 5})
        plano, efetivo = self._aplicar(DIVIDIDO, cfg, voz_wav=self.voz,
                                       palavras=self.palavras)
        self.assertEqual(DIVIDIDO, efetivo)
        self.assertAlmostEqual(20.0, plano["total_duration"], places=2)
        self.assertEqual(str(self.fundo), plano["fundo"]["arquivo"])
        self.assertGreaterEqual(plano["fundo"]["offset_s"], 5.0)
        palavra = json.loads(self.palavras.read_text(encoding="utf-8"))[0]
        self.assertAlmostEqual(10.0, palavra["t0"], places=2)
        with wave.open(str(self.voz)) as fh:
            self.assertAlmostEqual(2.0, fh.getnframes() / fh.getframerate(),
                                   delta=0.05)

    def test_voz_que_nao_estica_sai_1x_com_plano_coerente(self):
        cfg = self._cfg(velocidade_filtro="naoexiste={fator}",
                        velocidade_reserva="tambemnao={fator}",
                        fundo_video={"arquivo": str(self.fundo)})
        plano, efetivo = self._aplicar(DIVIDIDO, cfg, voz_wav=self.voz,
                                       palavras=self.palavras)
        self.assertEqual(1.0, efetivo["velocidade"])
        self.assertEqual(34.0, plano["total_duration"])
        palavra = json.loads(self.palavras.read_text(encoding="utf-8"))[0]
        self.assertEqual(17.0, palavra["t0"])


class OrdemNoRenderTests(unittest.TestCase):

    def test_o_plano_so_vai_ao_disco_depois_do_formato(self):
        fonte = inspect.getsource(controller.Pipeline.render)
        self.assertLess(fonte.index("formato_mod.resolver("),
                        fonte.index("aplicar_formato("))
        self.assertLess(fonte.index("aplicar_formato("),
                        fonte.index('"edit_plan.json"'))
        self.assertLess(fonte.index("aplicar_formato("),
                        fonte.index("legenda_srt("))
        self.assertIn("formato=efetivo", fonte)

    def test_render_json_tem_o_bloco_de_formato(self):
        bloco = RENDER["formato"]
        for chave in ("velocidade", "layout", "ajuste_imagem",
                      "legenda_y_painel", "titulo_minimo_s",
                      "velocidade_filtro", "velocidade_reserva"):
            self.assertIn(chave, bloco)
        self.assertEqual("fundo/videoMaquiagem.mp4",
                         bloco["fundo_video"]["arquivo"])


if __name__ == "__main__":
    unittest.main()
