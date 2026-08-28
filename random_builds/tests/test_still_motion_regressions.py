"""A imagem de recompensa entra como CENA, nunca como cartao parado.

O que este arquivo trava:

1. Imagem nao vaza para o caminho de video. `_asset_de_video` e teste de
   CAPACIDADE; um PNG existe no disco igual a um mp4, e sem olhar a midia ele
   iria parar no ffmpeg como se fosse filme.
2. A camera ANDA. Dois quadros do meio do movimento tem que ser diferentes -
   e a trava contra o cartao estatico voltar pela porta dos fundos, que e
   exatamente o que as secoes 9 e 20 mandaram tirar do video.
3. Imagem ilegivel nao derruba o render: cai na placa tipografica, o mesmo
   lugar onde cai quando o arquivo nem existe.
4. A ausencia da chave `media` continua significando video, senao todo asset
   anterior a existir imagem (reacao, gameplay, clipe de geracao antiga) sai
   do ar em silencio.

Rode de dentro de random_builds/:
    python -m unittest discover -s tests -p "test_*.py"
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image                                              # noqa: E402

from src.generation.session_generator import load_config           # noqa: E402
from src.identity import slots                                     # noqa: E402
from src.video.renderer import VideoRenderer                       # noqa: E402

EDICAO = load_config("editing.json")


def _renderer(profile: str = "celular") -> VideoRenderer:
    return VideoRenderer(load_config("render.json"), profile, preview=True)


def _evento(caminho: Path, slot: str = slots.CHARACTER,
            duracao: float = 2.6) -> dict:
    return {
        "type": "identity", "slot": slot, "duration": duracao,
        "asset": {"path": str(caminho), "synthetic": False,
                  "media": slots.IMAGEM},
        "fit": "contain",
        "nameplate": {"titulo": "LYRA DO GELO", "subtitulo": "Cavaleiro - 1,96 m"},
        "motion": EDICAO["identity_still"]["motion"][slot],
        "flash_frames": EDICAO["identity_still"]["flash_frames"],
    }


class CapacidadeTests(unittest.TestCase):
    def test_imagem_nao_entra_pelo_caminho_de_video(self):
        renderer = _renderer()
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "character_image.png"
            Image.new("RGB", (64, 114), (20, 20, 40)).save(png)
            self.assertFalse(renderer._asset_de_video(_evento(png)))

    def test_sem_a_chave_media_continua_sendo_video(self):
        """Todo asset que existia antes de existir imagem depende disso."""
        renderer = _renderer()
        with tempfile.TemporaryDirectory() as tmp:
            mp4 = Path(tmp) / "reacao.mp4"
            mp4.write_bytes(b"x")
            evento = {"type": "reaction",
                      "asset": {"path": str(mp4), "synthetic": False}}
            self.assertTrue(renderer._asset_de_video(evento))


class MovimentoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.png = Path(cls._tmp.name) / "character_image.png"
        # Ruido em vez de cor chapada: com fundo liso, mover a camera nao muda
        # pixel nenhum e o teste de movimento passaria sem movimento.
        imagem = Image.new("RGB", (540, 960))
        imagem.putdata([((x * 7) % 256, (y * 5) % 256, (x * y) % 256)
                        for y in range(960) for x in range(540)])
        imagem.save(cls.png)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_emite_exatamente_os_quadros_da_duracao(self):
        renderer = _renderer()
        evento = _evento(self.png)
        quadros = list(renderer._still_frames(evento))
        self.assertEqual(renderer._n_frames(evento["duration"]), len(quadros))
        for quadro in quadros:
            self.assertEqual((renderer.width, renderer.height), quadro.size)

    def test_a_camera_anda(self):
        """Dois quadros do MEIO do movimento nao podem ser iguais."""
        renderer = _renderer()
        quadros = list(renderer._still_frames(_evento(self.png)))
        meio = len(quadros) // 2
        a, b = quadros[meio], quadros[meio + 3]
        self.assertNotEqual(a.tobytes(), b.tobytes(),
                            "a imagem ficou parada: virou cartao estatico")

    def test_o_movimento_do_inicio_ao_fim_e_visivel(self):
        renderer = _renderer()
        quadros = list(renderer._still_frames(_evento(self.png)))
        # compara depois do estalo de entrada, que clareia os primeiros quadros
        inicio, fim = quadros[4], quadros[-1]
        diferentes = sum(1 for x, y in zip(inicio.tobytes(), fim.tobytes())
                         if x != y)
        self.assertGreater(diferentes, len(inicio.tobytes()) * 0.2,
                           "a camera mal saiu do lugar")

    def test_no_formato_deitado_a_imagem_nao_ganha_tarja_preta(self):
        """9:16 dentro de 16:9: o que sobra e a propria imagem borrada."""
        renderer = _renderer("normal")
        quadro = next(iter(renderer._still_frames(_evento(self.png))))
        largura, altura = quadro.size
        canto = quadro.getpixel((5, altura // 2))
        self.assertNotEqual((0, 0, 0), canto,
                            "sobrou tarja preta no lugar do fundo borrado")

    def test_imagem_ilegivel_cai_na_placa_e_nao_derruba_o_render(self):
        renderer = _renderer()
        with tempfile.TemporaryDirectory() as tmp:
            quebrada = Path(tmp) / "character_image.png"
            quebrada.write_bytes(b"\x89PNG\r\n\x1a\n" + b"lixo" * 400)
            evento = _evento(quebrada)
            quadros = list(renderer._still_frames(evento))
        self.assertEqual(renderer._n_frames(evento["duration"]), len(quadros))
        self.assertTrue(evento["asset"]["synthetic"],
                        "o asset ruim ficou marcado como bom")


class RitmoTests(unittest.TestCase):
    def test_a_still_dura_menos_que_o_teto_da_janela(self):
        """Imagem parada 5 s vale duas rolagens e meia. O teto e do video."""
        janelas = EDICAO["identity_slots"]
        for slot in slots.SLOTS:
            if slots.midia(slot) != slots.IMAGEM:
                continue
            with self.subTest(slot=slot):
                janela = janelas[slot]
                still = janela["still"]
                self.assertGreaterEqual(still, janela["min"])
                self.assertLess(still, janela["max"],
                                "a imagem esta ocupando o tempo de um video")

    def test_todo_slot_de_imagem_tem_movimento_declarado(self):
        motion = EDICAO["identity_still"]["motion"]
        for slot in slots.SLOTS:
            if slots.midia(slot) == slots.IMAGEM:
                self.assertIn(slot, motion)
                self.assertEqual(2, len(motion[slot]["zoom"]))
                self.assertEqual(2, len(motion[slot]["centro"]))


class SomDaRoletaTests(unittest.TestCase):
    """O estalo sai da MESMA curva que gira a imagem.

    Nao e efeito solto por cima: se as duas curvas divergirem, o som fica fora
    do lugar e a roleta deixa de parecer roleta. Por isso `_giro` e a unica
    fonte dos dois.
    """

    def setUp(self):
        from src.video import roleta_som
        self.som = roleta_som
        self.renderer = _renderer()

    def _evento(self, fatias=16, giro=1.8, total=3.3):
        return {"type": "roulette", "duration": total, "spin_duration": giro,
                "roll": {"wheel": {"labels": [str(i) for i in range(fatias)],
                                   "winner": 3}}}

    def test_os_estalos_rareiam_conforme_ela_desacelera(self):
        """E isso que faz soar como roleta de verdade."""
        evento = self._evento()
        giro = self.renderer._giro(evento, evento["roll"]["wheel"]["labels"], 3)
        tempos = self.som.tempos_de_estalo(giro["angulo_em"], giro["duracao"],
                                           giro["fatias"])
        self.assertGreater(len(tempos), 8)
        intervalos = [b - a for a, b in zip(tempos, tempos[1:])]
        primeiros = sum(intervalos[:3]) / 3
        ultimos = sum(intervalos[-3:]) / 3
        self.assertGreater(ultimos, primeiros * 2,
                           "o som nao acompanhou a freada")

    def test_nenhum_estalo_vira_zumbido(self):
        """No inicio a roda cruza fatias rapido demais para cada pino soar."""
        evento = self._evento()
        giro = self.renderer._giro(evento, evento["roll"]["wheel"]["labels"], 3)
        tempos = self.som.tempos_de_estalo(giro["angulo_em"], giro["duracao"],
                                           giro["fatias"])
        for a, b in zip(tempos, tempos[1:]):
            self.assertGreaterEqual(b - a, self.som.INTERVALO_MINIMO - 1e-6)

    def test_a_trilha_cobre_a_cena_inteira(self):
        import tempfile
        import wave
        evento = self._evento()
        with tempfile.TemporaryDirectory() as tmp:
            destino = self.renderer._audio_da_roleta(evento, Path(tmp) / "s.mp4")
            self.assertIsNotNone(destino)
            with wave.open(str(destino)) as w:
                segundos = w.getnframes() / w.getframerate()
            self.assertAlmostEqual(evento["duration"], segundos, places=1)

    def test_evento_que_nao_e_roleta_nao_ganha_trilha(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(self.renderer._audio_da_roleta(
                {"type": "hook", "duration": 1.8}, Path(tmp) / "s.mp4"))

    def test_a_imagem_e_o_som_leem_o_MESMO_giro(self):
        """Duas contas separadas divergem no dia em que uma mudar."""
        import inspect
        from src.video.renderer import VideoRenderer
        for metodo in (VideoRenderer._roulette_frames,
                       VideoRenderer._audio_da_roleta):
            self.assertIn("_giro(", inspect.getsource(metodo))


def _luta_de_teste(**extra) -> dict:
    luta = {
        "match_id": 1, "rodada_nome": "ROUND 2",
        "p1": "Kael", "p2": "Lyra",
        "p1_ficha": {"cor_r": 50, "cor_g": 200, "cor_b": 255},
        "p2_ficha": {"cor_r": 255, "cor_g": 90, "cor_b": 60},
        "vencedor": "Kael", "perdedor": "Lyra",
        "ko_type": "KO", "duracao": 31.2, "hp_vencedor": 22,
        "marcas": ["ZEBRA"], "tier": "GREAT", "tier_color": "#7ed957",
    }
    luta.update(extra)
    return luta


class TelasDeSerieTests(unittest.TestCase):
    """As telas de melhor-de-3 precisam DESENHAR, nao so entrar no plano.

    Um placar que so aparece no edit_plan quebraria na hora do render, que e
    onde ninguem esta olhando.
    """

    def setUp(self):
        self.renderer = _renderer()

    def _desenhar(self, evento: dict) -> list:
        return list(self.renderer._frames_for(evento, {}, Path(".")))

    def test_placar_do_round_desenha(self):
        frames = self._desenhar({
            "type": "round_result", "duration": 0.2,
            "luta": _luta_de_teste(), "placar": [1, 1],
            "caption": "Kael empatou a serie"})
        self.assertTrue(frames)
        self.assertEqual((self.renderer.width, self.renderer.height),
                         frames[0].size)

    def test_veredito_da_serie_desenha_com_placar(self):
        frames = self._desenhar({
            "type": "fight_result", "duration": 0.2,
            "luta": _luta_de_teste(), "placar": [2, 1], "melhor_de": 3,
            "caption": "Kael levou a serie"})
        self.assertTrue(frames)

    def test_veredito_sem_placar_continua_desenhando(self):
        """Luta unica nao passa `placar` — o formato antigo nao pode quebrar."""
        frames = self._desenhar({
            "type": "fight_result", "duration": 0.2,
            "luta": _luta_de_teste(), "caption": "Kael venceu"})
        self.assertTrue(frames)

    def test_card_com_rotulo_longo_de_serie_desenha(self):
        frames = self._desenhar({
            "type": "fight_card", "duration": 0.2,
            "luta": _luta_de_teste(rodada_nome="ESTREIA • MELHOR DE 3"),
            "caption": "Kael vs Lyra"})
        self.assertTrue(frames)
