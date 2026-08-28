"""O print do comentario que pediu o nome.

O que este arquivo trava:

1. O print e OPCIONAL: sem ele o video sai exatamente como antes.
2. Com ele, a prova entra logo depois do gancho — cedo, enquanto ainda vale
   convencer — e leva o credito de quem pediu.
3. `guardar` COPIA para dentro da geracao e falha alto quando o arquivo nao
   existe ou nao e imagem; trocar de formato nao deixa dois prints na pasta.
4. A tela nao leva a placa do rodape, que cobriria o proprio comentario, e
   desenha mesmo quando a imagem esta ilegivel.

Rode de dentro de random_builds/:
    python -m pytest tests/test_comentario_regressions.py -q
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image                                                    # noqa: E402

from src.assets.catalog import AssetCatalog                              # noqa: E402
from src.assets.selector import AssetSelector                            # noqa: E402
from src.content.caption_generator import CaptionGenerator               # noqa: E402
from src.editing import comentario                                       # noqa: E402
from src.editing.timeline_builder import TimelineBuilder                 # noqa: E402
from src.generation.random_engine import RandomEngine                    # noqa: E402
from src.generation.session_generator import (SessionGenerator,          # noqa: E402
                                              load_config)
from src.video.renderer import VideoRenderer                             # noqa: E402

EDICAO = load_config("editing.json")
CAPTIONS = CaptionGenerator(load_config("captions.json"), load_config("frases.json"))
SEED = 4242


def _print_falso(destino: Path, tamanho=(900, 420)) -> Path:
    """Um "print de comentario": deitado, como um recorte de tela real."""
    Image.new("RGB", tamanho, (28, 26, 44)).save(destino)
    return destino


class GuardarTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name) / "generation_00001"
        self.pasta.mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    def test_sem_print_nao_faz_nada(self):
        self.assertIsNone(comentario.guardar(self.pasta, None))
        self.assertIsNone(comentario.encontrar(self.pasta))

    def test_copia_para_dentro_da_geracao(self):
        """O original costuma estar na area de trabalho e some depois."""
        origem = _print_falso(Path(self._tmp.name) / "Captura de tela.png")
        destino = comentario.guardar(self.pasta, origem)
        self.assertEqual(self.pasta / "comentario.png", destino)
        origem.unlink()
        self.assertEqual(destino, comentario.encontrar(self.pasta))

    def test_trocar_de_formato_nao_deixa_dois_prints(self):
        comentario.guardar(self.pasta, _print_falso(
            Path(self._tmp.name) / "a.png"))
        comentario.guardar(self.pasta, _print_falso(
            Path(self._tmp.name) / "b.jpg"))
        achados = [p.name for p in self.pasta.glob("comentario.*")]
        self.assertEqual(["comentario.jpg"], achados)

    def test_arquivo_que_nao_existe_falha_alto(self):
        with self.assertRaises(ValueError):
            comentario.guardar(self.pasta, Path(self._tmp.name) / "nada.png")

    def test_mp4_no_lugar_do_print_falha_alto(self):
        """Render silencioso sem a prova seria descoberto so ao publicar."""
        video = Path(self._tmp.name) / "clipe.mp4"
        video.write_bytes(b"0" * 20000)
        with self.assertRaises(ValueError):
            comentario.guardar(self.pasta, video)

    def test_imagem_truncada_nao_e_aceita(self):
        falso = Path(self._tmp.name) / "truncado.png"
        falso.write_bytes(b"nao sou png")
        with self.assertRaises(ValueError):
            comentario.guardar(self.pasta, falso)
        self.assertEqual([], list(self.pasta.glob("comentario.*")))


class TimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geracao = SessionGenerator().generate(seed=SEED,
                                                  generation_id="comentario_teste")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _plano(self, pedido: dict | None = None) -> dict:
        geracao = dict(self.geracao)
        if pedido is not None:
            geracao["nome_pedido"] = pedido
        builder = TimelineBuilder(EDICAO, CAPTIONS,
                                  AssetSelector(AssetCatalog(ROOT / "assets")))
        return builder.build(RandomEngine(SEED).fork("editing"), geracao,
                             self.pasta)

    def test_sem_print_o_video_sai_como_antes(self):
        tipos = [e["type"] for e in self._plano()["events"]]
        self.assertNotIn("comentario", tipos)

    def test_o_print_entra_logo_depois_do_gancho(self):
        _print_falso(self.pasta / "comentario.png")
        eventos = self._plano()["events"]
        tipos = [e["type"] for e in eventos]
        self.assertEqual("hook", tipos[0])
        self.assertEqual("comentario", tipos[1])
        self.assertEqual(str(self.pasta / "comentario.png"),
                         eventos[1]["asset"]["path"])
        self.assertEqual("imagem", eventos[1]["asset"]["media"])
        self.assertEqual("contain", eventos[1]["fit"])
        self.assertGreater(eventos[1]["duration"], 0.0)

    def test_a_etiqueta_credita_quem_pediu(self):
        _print_falso(self.pasta / "comentario.png")
        plano = self._plano({"nome": "Kaelen", "autor": "@zeca",
                             "origem": "comentario"})
        evento = next(e for e in plano["events"] if e["type"] == "comentario")
        # caixa alta vem de `pedido_de`, a mesma do credito na placa e na CTA
        self.assertEqual("PEDIDO DE @ZECA", evento["badge"])

    def test_sem_autor_a_etiqueta_ainda_diz_de_onde_veio(self):
        _print_falso(self.pasta / "comentario.png")
        evento = next(e for e in self._plano()["events"]
                      if e["type"] == "comentario")
        self.assertTrue(evento["badge"])
        self.assertNotIn("{", evento["badge"])

    def test_o_zoom_e_quase_parado_para_o_texto_ficar_legivel(self):
        """Ken Burns de revelacao em texto pequeno deixa o print ilegivel."""
        _print_falso(self.pasta / "comentario.png")
        evento = next(e for e in self._plano()["events"]
                      if e["type"] == "comentario")
        inicio, fim = evento["motion"]["zoom"][:2]
        self.assertLessEqual(fim - inicio, 0.05)

    def test_arquivo_que_nao_e_imagem_nao_vira_tela(self):
        (self.pasta / "comentario.png").write_bytes(b"lixo")
        self.assertNotIn("comentario",
                         [e["type"] for e in self._plano()["events"]])


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.renderer = VideoRenderer(load_config("render.json"), "celular",
                                      preview=True)
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _evento(self, **extra) -> dict:
        evento = {
            "type": "comentario", "duration": 0.2,
            "asset": {"path": str(_print_falso(self.pasta / "comentario.png")),
                      "synthetic": False, "media": "imagem"},
            "fit": "contain", "badge": "PEDIDO DE @zeca", "caption": "",
            "motion": {"zoom": [1.0, 1.03], "centro": [[0.5, 0.5], [0.5, 0.5]]},
            "flash_frames": 2,
        }
        evento.update(extra)
        return evento

    def test_a_tela_desenha(self):
        frames = list(self.renderer._frames_for(self._evento(), {}, self.pasta))
        self.assertTrue(frames)
        self.assertEqual((self.renderer.width, self.renderer.height),
                         frames[0].size)

    def test_nao_leva_a_placa_que_cobriria_o_comentario(self):
        """A cortina do rodape da revelacao engoliria o texto do print."""
        evento = self._evento(nameplate={"titulo": "KAELEN", "subtitulo": "x"})
        placa = self.renderer._placa_imagem(evento)
        self.assertIsNotNone(placa, "a etiqueta do topo sumiu")
        # tudo que a etiqueta desenha vive no topo: o rodape fica limpo
        rodape = placa.crop((0, int(self.renderer.height * 0.6),
                             self.renderer.width, self.renderer.height))
        self.assertEqual((0, 0), rodape.getchannel("A").getextrema())

    def test_sem_etiqueta_nao_desenha_nada_por_cima(self):
        self.assertIsNone(self.renderer._placa_imagem(self._evento(badge="")))

    def test_print_ilegivel_nao_derruba_o_render(self):
        (self.pasta / "comentario.png").write_bytes(b"lixo")
        frames = list(self.renderer._frames_for(self._evento(), {}, self.pasta))
        self.assertTrue(frames)


if __name__ == "__main__":
    unittest.main()
