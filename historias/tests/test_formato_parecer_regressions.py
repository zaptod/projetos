# -*- coding: utf-8 -*-
"""O revisor entende a tela dividida e a fala acelerada (14/09/2026).

O prompt do parecer reprova "tela dividida", e desde esta data a metade de
baixo de todo video novo e um video de fundo de proposito. Sem avisar, o
Gemini reprovaria todo video novo — e o reparo gastaria PicassoIA refazendo
imagens boas por um defeito que nao existe.

Rode de dentro de historias/:
    python -m unittest tests.test_formato_parecer_regressions -v
"""
from __future__ import annotations

import inspect
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from contos.pipeline import reparo
from contos.publicar import parecer

DIVIDIDO = {"velocidade": 1.7, "layout": "dividido"}
LEGADO = {"velocidade": 1.0, "layout": "vertical"}


class _Video:
    titulo = "A mola frouxa (Parte 1/2)"
    caminho = "x.mp4"


ROTEIRO = {"partes": [{"n": 1, "cenas": [
    {"n": 1, "narracao": "Ela desceu a rua arrastando a cadeira.",
     "imagem": "a woman dragging a chair"}]}]}


def _texto(formato=None):
    laudo = {"duracao": 63, "media_db": -16.2, "palavras_por_s": 4.1}
    if formato is not None:
        laudo["formato"] = formato
    return parecer.prompt(_Video(), ROTEIRO, 1, laudo)


class PromptTests(unittest.TestCase):

    def test_tela_dividida_manda_ignorar_a_metade_de_baixo(self):
        texto = _texto(DIVIDIDO)
        self.assertIn("TELA DIVIDIDA AO MEIO", texto)
        self.assertIn("metade de baixo", texto)
        self.assertIn("IMAGEM DA HISTORIA (metade de cima", texto)

    def test_texto_e_marca_d_agua_do_fundo_nao_reprovam(self):
        """O video de maquiagem tem legenda de tutorial em ingles e a marca
        'babycolor' (visto pelo Gemini na prova de 14/09/2026). Sem isto, o
        motivo "marca d'agua" viraria conserto de uma imagem que esta boa."""
        trecho = _texto(DIVIDIDO).split("TELA DIVIDIDA AO MEIO")[1][:400]
        self.assertIn("marca d'agua", trecho)
        self.assertIn("texto em qualquer lingua", trecho)

    def test_fala_acelerada_e_de_proposito(self):
        texto = _texto(DIVIDIDO)
        self.assertIn("acelerada 1.7x de proposito", texto)
        self.assertIn("acelerado 1.7x", texto)

    def test_video_antigo_pergunta_como_sempre(self):
        for texto in (_texto(LEGADO), _texto(None)):
            self.assertNotIn("metade de baixo", texto)
            self.assertNotIn("acelerad", texto)
            self.assertIn("alguma imagem e colagem, tela dividida", texto)

    def test_a_legenda_do_canal_continua_liberada(self):
        self.assertIn("legenda amarela", _texto(DIVIDIDO))

    def test_o_formato_vem_do_video_quando_o_laudo_nao_traz(self):
        fonte = inspect.getsource(parecer._pedir_em)
        self.assertLess(fonte.index("formato_de("), fonte.index("_montar_folha("))
        self.assertIn('"formato": feito', fonte)


def _video_vermelho_e_azul(destino: Path) -> None:
    """Metade de cima vermelha, metade de baixo azul: 2 s, 160x320."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "color=c=red:s=160x160:d=2:r=10",
         "-f", "lavfi", "-i", "color=c=blue:s=160x160:d=2:r=10",
         "-filter_complex", "[0:v][1:v]vstack=inputs=2,format=yuv420p",
         str(destino)], check=True, capture_output=True)


@unittest.skipUnless(shutil.which("ffmpeg"), "sem ffmpeg")
class FolhaSoDaHistoriaTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        self.video = self.pasta / "v.mp4"
        _video_vermelho_e_azul(self.video)

    @staticmethod
    def _azul(caminho: Path) -> float:
        from PIL import Image
        with Image.open(caminho) as imagem:
            pixels = list(imagem.convert("RGB").getdata())
        return sum(1 for r, g, b in pixels if b > 150 and r < 100) / len(pixels)

    def test_folha_por_cena_mostra_so_a_metade_de_cima(self):
        cenas = [{"n": 1, "inicio": 0.0, "fim": 2.0}]
        com = parecer.folha_por_cena(self.video, self.pasta / "a.jpg", cenas,
                                     painel=0.5)
        sem = parecer.folha_por_cena(self.video, self.pasta / "b.jpg", cenas)
        self.assertLess(self._azul(com), 0.02)
        self.assertGreater(self._azul(sem), 0.3)

    def test_folha_no_tempo_tambem_recorta(self):
        com = parecer.folha_de_contato(self.video, self.pasta / "c.jpg",
                                       quadros=4, painel=0.5)
        self.assertLess(self._azul(com), 0.02)


class ReparoNaoRefazOFormatoTests(unittest.TestCase):

    def setUp(self):
        from contos.imagens import composicao, fila
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.imagem = Path(self._tmp.name) / "p01_cena_03.png"
        self.imagem.write_bytes(b"png")
        self.colagem = False
        for modulo, nome, valor in (
                (fila, "caminho_da_cena", lambda *_a, **_k: self.imagem),
                (composicao, "e_colagem", lambda _p: self.colagem)):
            self.addCleanup(setattr, modulo, nome, getattr(modulo, nome))
            setattr(modulo, nome, valor)

    def test_tela_dividida_sem_colagem_na_imagem_e_o_formato(self):
        self.assertTrue(reparo._colagem_falsa(
            "h", 1, 3, ["cena 3: a imagem mostra uma tela dividida"]))

    def test_colagem_de_verdade_continua_sendo_refeita(self):
        self.colagem = True
        self.assertFalse(reparo._colagem_falsa(
            "h", 1, 3, ["cena 3: a imagem e uma colagem de dois paineis"]))

    def test_marca_d_agua_nao_e_confundida(self):
        self.assertFalse(reparo._colagem_falsa(
            "h", 1, 3, ["cena 3: tela dividida com marca d'agua"]))

    def test_motivo_de_outra_cena_nao_conta(self):
        self.assertFalse(reparo._colagem_falsa(
            "h", 1, 3, ["cena 5: tela dividida"]))

    def test_os_dois_caminhos_do_reparo_passam_pela_guarda(self):
        self.assertIn("_colagem_falsa(",
                      inspect.getsource(reparo._plano_pelo_veto_da_ia))
        self.assertIn("_colagem_falsa(", inspect.getsource(reparo.reparar))


if __name__ == "__main__":
    unittest.main()
