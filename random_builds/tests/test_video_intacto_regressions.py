# -*- coding: utf-8 -*-
"""Contratos do "video inteiro": nada de mp4 truncado passando por pronto.

O bug (31/08/2026): um segmento ficou sem `moov atom` (o ffmpeg que o
escrevia morreu no meio) e o `concat` seguinte PAROU nele — imprimindo
"Error during demuxing" no stderr e saindo com codigo **0**. Como o pipeline
so olhava o codigo de saida, a parte 1 de uma historia virou um mp4 de
11,8 s no lugar dos 193 s do plano, o log escreveu "pronto" e ninguem soube.

O que este arquivo trava:

1. `medidas.duracao` responde None para arquivo truncado/vazio/inexistente
   em vez de levantar — quem chama precisa DECIDIR o que fazer.
2. `_concat` recusa a lista quando algum segmento nao abre, dizendo QUAL.
3. `_concat` confere a DURACAO do resultado: um video mais curto que a soma
   dos segmentos nao e sucesso, mesmo com o ffmpeg saindo 0.

Rode de dentro de random_builds/:
    python -m unittest tests.test_video_intacto_regressions -v
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from builds.video import medidas                                  # noqa: E402

TEM_FFMPEG = shutil.which("ffmpeg") is not None and \
    shutil.which("ffprobe") is not None
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _clipe(destino: Path, segundos: float = 1.0) -> Path:
    """Um mp4 minusculo de verdade (o teste precisa de arquivo real)."""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c=black:s=64x64:d={segundos}:r=10",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         str(destino)],
        check=True, capture_output=True, creationflags=NO_WINDOW)
    return destino


@unittest.skipUnless(TEM_FFMPEG, "precisa de ffmpeg/ffprobe no PATH")
class MedidasTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)

    def test_le_a_duracao_de_um_mp4_de_verdade(self):
        alvo = _clipe(self.pasta / "ok.mp4", 1.0)
        self.assertAlmostEqual(1.0, medidas.duracao(alvo), delta=0.3)
        self.assertTrue(medidas.intacto(alvo))

    def test_arquivo_truncado_devolve_none(self):
        """O caso real: mp4 sem o moov atom (ffmpeg morto no meio)."""
        alvo = _clipe(self.pasta / "meio.mp4", 1.0)
        bruto = alvo.read_bytes()
        alvo.write_bytes(bruto[:len(bruto) // 3])
        self.assertIsNone(medidas.duracao(alvo))
        self.assertFalse(medidas.intacto(alvo))

    def test_arquivo_vazio_ou_ausente_devolve_none(self):
        vazio = self.pasta / "vazio.mp4"
        vazio.write_bytes(b"")
        self.assertIsNone(medidas.duracao(vazio))
        self.assertIsNone(medidas.duracao(self.pasta / "nao_existe.mp4"))

    def test_quebrados_lista_so_os_ruins_na_ordem(self):
        bom1 = _clipe(self.pasta / "a.mp4")
        ruim = self.pasta / "b.mp4"
        ruim.write_bytes(b"nao sou um mp4")
        bom2 = _clipe(self.pasta / "c.mp4")
        self.assertEqual([ruim], medidas.quebrados([bom1, ruim, bom2]))
        self.assertEqual([], medidas.quebrados([bom1, bom2]))


@unittest.skipUnless(TEM_FFMPEG, "precisa de ffmpeg/ffprobe no PATH")
class ConcatTests(unittest.TestCase):
    """A montagem nao pode entregar video curto dizendo que deu certo."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)

    def _renderer(self):
        from builds.video.renderer import VideoRenderer
        r = VideoRenderer.__new__(VideoRenderer)
        r.preset, r.crf = "ultrafast", 30
        return r

    def test_junta_tudo_quando_os_segmentos_estao_bons(self):
        segs = [_clipe(self.pasta / f"s{i}.mp4", 1.0) for i in range(3)]
        destino = self.pasta / "junto.mp4"
        self._renderer()._concat(segs, destino)
        self.assertAlmostEqual(3.0, medidas.duracao(destino), delta=0.6)

    def test_segmento_ilegivel_e_recusado_pelo_nome(self):
        segs = [_clipe(self.pasta / "s0.mp4", 1.0),
                self.pasta / "s1.mp4",
                _clipe(self.pasta / "s2.mp4", 1.0)]
        bruto = _clipe(self.pasta / "tmp.mp4", 1.0).read_bytes()
        segs[1].write_bytes(bruto[:len(bruto) // 3])   # sem moov atom
        with self.assertRaises(RuntimeError) as caso:
            self._renderer()._concat(segs, self.pasta / "junto.mp4")
        self.assertIn("s1.mp4", str(caso.exception),
                      "o erro tem que dizer QUAL segmento esta quebrado")

    def test_nao_entrega_video_mais_curto_que_os_segmentos(self):
        """A prova que faltava: o ffmpeg sai 0 e mesmo assim trunca."""
        segs = [_clipe(self.pasta / f"s{i}.mp4", 1.0) for i in range(3)]
        destino = self.pasta / "junto.mp4"
        r = self._renderer()
        r._concat(segs, destino)
        inteiro = medidas.duracao(destino)
        esperado = sum(medidas.duracao(s) for s in segs)
        self.assertGreaterEqual(
            inteiro, esperado - 0.5,
            "o resultado tem que ter a soma dos segmentos, nao so o comeco")


if __name__ == "__main__":
    unittest.main()
