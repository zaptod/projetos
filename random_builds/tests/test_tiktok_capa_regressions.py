# -*- coding: utf-8 -*-
"""26/10/2026: a serie do Blue Lock escolhe a CAPA no upload do TikTok.

Caso medido: a capa do ep. 1 no perfil saiu um quadro do meio (~7 s, legenda
"de Blue Lock."), e nao o gancho "POR QUE ELE PAROU?" do quadro 0. Agora a
serie manda o quadro `capa_s` da ficha (padrao 0) pelo "Editar capa" do
formulario. Contas de mao:
  - pagina simulada com "Editar capa" -> aba "Carregar capa" -> arquivo ->
    "Confirmar": o PNG do quadro chega ao formulario e o laudo diz "enviada";
  - pagina SEM o botao: nao levanta, laudo "padrao (...)" (a publicacao segue);
  - o quadro 0 e o quadro de 2 s do mesmo mp4 sao imagens DIFERENTES;
  - ficha sem `capa_s`: 0; `capa_s` 3,5 chega ao Video; invalido (-1, "x"):
    o episodio sai da fila; duelos/historias nao tem `capa_s` no Video.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from builds.publicar import serie_bluelock as S
from builds.publicar import tiktok as T

FORMULARIO = """
<html><body>
<div id="capa-atual">padrao</div>
<button id="editar" onclick="document.getElementById('modal').style.display='block'">Editar capa</button>
<div id="modal" style="display:none">
  <div role="tab" onclick="document.getElementById('envio').style.display='block'">Carregar capa</div>
  <div id="envio" style="display:none"><input type="file"></div>
  <button onclick="document.getElementById('capa-atual').innerText='enviada:'+window.arq;
                   document.getElementById('modal').style.display='none'">Confirmar</button>
  <button onclick="document.getElementById('modal').style.display='none'">Cancelar</button>
</div>
<script>
document.querySelector('input[type=file]').onchange = e => { window.arq = e.target.files[0].name; };
</script></body></html>
"""


class CapaNoTikTokTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from patchright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.navegador = cls.pw.chromium.launch(channel="chrome", headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.navegador.close()
        cls.pw.stop()

    def _pagina(self, html):
        page = self.navegador.new_page()
        self.addCleanup(page.close)
        page.set_content(html)
        return page

    def test_envia_o_quadro_e_confirma(self):
        with TemporaryDirectory() as d:
            png = Path(d) / "capa.png"
            png.write_bytes(b"\x89PNG\r\n\x1a\n")
            page = self._pagina(FORMULARIO)
            laudo: dict = {}
            self.assertTrue(T._escolher_capa(page, png, lambda *_: None, laudo))
            self.assertEqual(laudo["capa"], "enviada")
            self.assertEqual(page.inner_text("#capa-atual"), "enviada:capa.png")

    def test_sem_o_botao_nao_levanta_e_a_capa_fica_a_do_formulario(self):
        with TemporaryDirectory() as d:
            png = Path(d) / "capa.png"
            png.write_bytes(b"x")
            page = self._pagina("<html><body>sem capa aqui</body></html>")
            laudo: dict = {}
            self.assertFalse(T._escolher_capa(page, png, lambda *_: None, laudo))
            self.assertTrue(laudo["capa"].startswith("padrao"))

    @unittest.skipUnless(shutil.which("ffmpeg"), "sem ffmpeg")
    def test_quadro_0_e_quadro_de_2s_sao_diferentes(self):
        with TemporaryDirectory() as d:
            mp4 = Path(d) / "v.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                            "-i", "testsrc=size=180x320:rate=10:duration=4",
                            "-pix_fmt", "yuv420p", str(mp4)], check=True)
            zero = T.quadro_do_video(mp4, 0)
            dois = T.quadro_do_video(mp4, 2)
            self.assertIsNotNone(zero)
            self.assertIsNotNone(dois)
            self.assertNotEqual(zero.read_bytes(), dois.read_bytes())
            self.assertIsNone(T.quadro_do_video(Path(d) / "nao_existe.mp4", 0))


class CapaNaFichaTests(unittest.TestCase):
    def _ficha(self, pasta: Path, **mais):
        mp4 = pasta / "EP01.mp4"
        mp4.write_bytes(b"video aprovado")
        dados = {"episodio": 1, "arquivo": str(mp4), "sha256": S.sha256_de(mp4),
                 "titulo": "Gancho | Como eu criei um Blue Lock #1",
                 "descricao": "Descricao do episodio.", "tags": ["#bluelock"],
                 "idioma": "pt", "aprovado_por_conferente": True}
        dados.update(mais)
        (pasta / "ep01.json").write_text(json.dumps(dados), encoding="utf-8")

    def test_padrao_zero_e_valor_da_ficha_chegam_ao_video(self):
        with TemporaryDirectory() as d:
            self._ficha(Path(d))
            ep = S.episodios(Path(d))[0][0]
            self.assertEqual(ep.como_video().capa_s, 0.0)
            self._ficha(Path(d), capa_s=3.5)
            ep = S.episodios(Path(d))[0][0]
            self.assertEqual(ep.como_video().capa_s, 3.5)

    def test_capa_invalida_tira_o_episodio_da_fila(self):
        for ruim in (-1, "x", 9999):
            with TemporaryDirectory() as d:
                self._ficha(Path(d), capa_s=ruim)
                aprovados, fora = S.episodios(Path(d))
                self.assertEqual(aprovados, [], ruim)
                self.assertTrue(fora)

    def test_video_de_duelo_nao_tem_capa_s(self):
        from builds.publicar.catalogo import Video
        campos = Video.__dataclass_fields__
        self.assertNotIn("capa_s", campos)


if __name__ == "__main__":
    unittest.main()
