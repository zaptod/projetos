# -*- coding: utf-8 -*-
"""A vistoria mede no pixel se a imagem da historia ficou preta.

17/09/2026: o 09003 p1 saiu com as cenas 12 a 14 com a metade de cima preta
(11 de 14 imagens; a aba fechou no meio da geracao). Audio, duracao e ritmo
estavam certos; so o Gemini viu. O teste com video de verdade gera um mp4
minusculo com o ffmpeg e PULA se ele nao estiver instalado.
"""
from __future__ import annotations

import inspect
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from contos.publicar import qualidade as Q

SAIDA_DO_FFMPEG = """\
[Parsed_blackdetect_3 @ 000001] black_start:1 black_end:2.25 black_duration:1.25
frame=   12 fps=0.0 q=-0.0 size=N/A time=00:00:03.00
[Parsed_blackdetect_3 @ 000001] black_start:x black_end:y black_duration:z
[Parsed_blackdetect_3 @ 000001] black_start:5.5 black_end:6.25 black_duration:0.75
"""


class LeituraDoFiltro(unittest.TestCase):

    def test_le_os_intervalos_e_ignora_linha_quebrada(self):
        self.assertEqual([(1.0, 2.25), (5.5, 6.25)],
                         Q._intervalos_pretos(SAIDA_DO_FFMPEG))

    def test_sem_nada_preto(self):
        self.assertEqual([], Q._intervalos_pretos("frame= 10\n"))

    def test_dividido_olha_so_a_metade_de_cima(self):
        visto = {}

        def _rodar(cmd, **_kw):
            visto["filtro"] = cmd[cmd.index("-vf") + 1]
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(Q.subprocess, "run", side_effect=_rodar):
            Q.trechos_pretos(Path("x.mp4"), "dividido")
            self.assertIn("crop=iw:ih/2:0:0", visto["filtro"])
            Q.trechos_pretos(Path("x.mp4"), "vertical")
            self.assertNotIn("crop=", visto["filtro"])
        self.assertIn(f"pic_th={Q.PRETO_AREA}", visto["filtro"])
        self.assertIn(f"d={Q.PRETO_MIN_S}", visto["filtro"])

    def test_ffmpeg_ausente_nao_barra(self):
        with mock.patch.object(Q.subprocess, "run",
                               side_effect=FileNotFoundError("ffmpeg")):
            self.assertIsNone(Q.trechos_pretos(Path("x.mp4"), "vertical"))


class LaudoDoPreto(unittest.TestCase):

    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.mp4 = Path(pasta.name) / "final_celular_p01.mp4"
        self.mp4.write_bytes(b"x" * 10)
        Q._PRETOS_MEDIDOS.clear()
        self.addCleanup(Q._PRETOS_MEDIDOS.clear)

    def test_trecho_preto_vira_erro(self):
        with mock.patch.object(Q, "trechos_pretos",
                               return_value=[(12.0, 14.5)]):
            laudo = Q.erros_de_preto(self.mp4, "dividido")
        self.assertEqual(1, len(laudo["erros"]))
        self.assertIn("metade de cima", laudo["erros"][0])
        self.assertIn("12.0-14.5s", laudo["erros"][0])

    def test_sem_medida_e_aviso_e_nao_erro(self):
        with mock.patch.object(Q, "trechos_pretos", return_value=None):
            laudo = Q.erros_de_preto(self.mp4, "vertical")
        self.assertEqual([], laudo["erros"])
        self.assertEqual(1, len(laudo["avisos"]))

    def test_mede_uma_vez_por_arquivo_e_de_novo_se_ele_mudar(self):
        with mock.patch.object(Q, "trechos_pretos",
                               return_value=[]) as medir:
            Q.erros_de_preto(self.mp4, "dividido")
            Q.erros_de_preto(self.mp4, "dividido")
            self.assertEqual(1, medir.call_count)
            # O reparo re-renderiza NO MESMO CAMINHO.
            self.mp4.write_bytes(b"y" * 20)
            Q.erros_de_preto(self.mp4, "dividido")
            self.assertEqual(2, medir.call_count)

    def test_a_vistoria_da_parte_usa_o_layout_feito(self):
        fonte = inspect.getsource(Q.vistoriar_parte)
        self.assertIn('erros_de_preto(caminho, str(feito.get("layout")',
                      fonte)


@unittest.skipUnless(shutil.which("ffmpeg"),
                     "ffmpeg ausente: o video sintetico nao pode ser gerado")
class VideoSintetico(unittest.TestCase):
    """90x160, 3 s: cinza, com uma faixa na cor do cartao de 1 a 2,2 s."""

    def _gerar(self, regiao: str) -> Path:
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        destino = Path(pasta.name) / "sintetico.mp4"
        y, h = {"cima": ("0", "ih/2"), "baixo": ("ih/2", "ih/2"),
                "tudo": ("0", "ih")}[regiao]
        caixa = (f"drawbox=x=0:y={y}:w=iw:h={h}:color=0x141019:t=fill:"
                 "enable='between(t,1,2.2)'")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "color=c=0x808080:s=90x160:r=10:d=3", "-vf", caixa,
             "-pix_fmt", "yuv420p", str(destino)],
            check=True, capture_output=True, timeout=60,
            creationflags=Q.NO_WINDOW)
        return destino

    def test_metade_de_cima_preta_no_dividido(self):
        trechos = Q.trechos_pretos(self._gerar("cima"), "dividido")
        self.assertEqual(1, len(trechos))
        inicio, fim = trechos[0]
        self.assertAlmostEqual(1.0, inicio, delta=0.3)
        self.assertAlmostEqual(2.2, fim, delta=0.3)

    def test_metade_de_baixo_e_o_fundo_e_nao_conta_no_dividido(self):
        self.assertEqual([], Q.trechos_pretos(self._gerar("baixo"),
                                              "dividido"))

    def test_no_vertical_meia_tela_escura_nao_basta(self):
        # Cena noturna com laterais escuras chega a ~62% da area.
        self.assertEqual([], Q.trechos_pretos(self._gerar("cima"),
                                              "vertical"))

    def test_o_cartao_de_cena_sem_imagem_do_renderer_e_pego(self):
        """O defeito de verdade: o painel de cima vira o cartao tipografico."""
        import json

        from contos.video.renderer import VideoRenderer
        raiz = Path(Q.__file__).resolve().parents[2]
        cfg = json.loads((raiz / "config" / "render.json")
                         .read_text(encoding="utf-8-sig"))
        r = VideoRenderer(cfg, "celular", formato={"layout": "dividido",
                                                   "velocidade": 1.5})
        texto = ("Ela abriu a fatura na minha frente e perguntou quem tinha "
                 "gasto seis mil reais no cartao, e eu fiquei calado.")
        quadro = list(r._cena_sem_imagem({"narracao": texto, "start": 0.0},
                                         3))[-1]
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        png = Path(pasta.name) / "cartao.png"
        quadro.resize((quadro.width // 6, quadro.height // 6)).save(png)
        destino = Path(pasta.name) / "cartao.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-r", "10", "-t",
             "1.5", "-i", str(png), "-vf",
             "pad=iw:ih*2:0:0:color=0x808080,scale=trunc(iw/2)*2:"
             "trunc(ih/2)*2", "-pix_fmt", "yuv420p", str(destino)],
            check=True, capture_output=True, timeout=60,
            creationflags=Q.NO_WINDOW)
        self.assertEqual(1, len(Q.trechos_pretos(destino, "dividido")))

    def test_no_vertical_a_tela_inteira_preta_conta(self):
        self.assertEqual(1, len(Q.trechos_pretos(self._gerar("tudo"),
                                                 "vertical")))


if __name__ == "__main__":
    unittest.main()
