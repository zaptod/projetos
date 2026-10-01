"""Onda 16A: o som REAL do jogo atravessa o corte, a montagem e o render.

Medido em 28/09/2026: o gravador tinha trilha `anullsrc`, o corte de tedio
aplicava `-an`, e o som que entrava na luta era o sintetizado (25 vezes o
mesmo hit por duelo). O transcode simples do renderer ainda saia com codigo 0
e SEM faixa de audio, e a segunda tentativa nunca rodava.

O que este arquivo trava:

1. um som em t=X da gravacao cai no lugar certo depois do corte — na lista
   (`remapear_gravacao`) e no AUDIO do clipe cortado (`extrair`, sem `-an`);
2. a luta com `sons` soa com os arquivos reais; sem `sons`, segue no
   sintetizado; o sintetizado so volta como reforco se o knob ligar;
3. transcode com codigo 0 e sem faixa de audio e refeito, e sem audio mesmo
   assim e ERRO;
4. o sintetizado do trecho de luta no fim do build respeita o `start_offset`;
5. a re-anotacao recusa luta que nao e a do clipe; o plano e remendado por
   `match_id`; o relogio (:25-:55) segura o re-render.

Rode de dentro de random_builds/:
    python -m unittest discover -s tests -p "test_*.py"
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import types
import unittest
import wave
from datetime import datetime
from pathlib import Path
from unittest import mock

from builds.generation.session_generator import load_config
from builds.pipeline import sonorizar
from builds.tournament import highlights, som_real
from builds.tournament.timeline import evento_gameplay
from builds.video import medidas, som_da_luta, trilha
from builds.video import renderer as renderer_mod

TAXA = 44100


def _ffmpeg_ok() -> bool:
    try:
        return subprocess.run(["ffmpeg", "-version"], capture_output=True,
                              timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


FFMPEG = _ffmpeg_ok()


def _numpy_ok() -> bool:
    try:
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


NUMPY = _numpy_ok()


def _wav_de_clique(destino: Path, duracao: float = 0.3) -> Path:
    n = int(duracao * TAXA)
    quadros = bytearray()
    for i in range(n):
        valor = int(0.5 * 32767) if i < 64 else 0
        quadros += int(valor).to_bytes(2, "little", signed=True) * 2
    with wave.open(str(destino), "wb") as arquivo:
        arquivo.setnchannels(2)
        arquivo.setsampwidth(2)
        arquivo.setframerate(TAXA)
        arquivo.writeframes(bytes(quadros))
    return destino


def _onset(caminho: Path, limiar: float = 0.05) -> float | None:
    """Primeiro instante (s) em que o audio passa do limiar."""
    import numpy as np
    saida = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(caminho), "-f", "f32le", "-ac", "1",
         "-ar", str(TAXA), "pipe:1"], capture_output=True, timeout=60)
    amostras = np.frombuffer(saida.stdout, dtype="<f4")
    acima = np.flatnonzero(np.abs(amostras) > limiar)
    return float(acima[0]) / TAXA if len(acima) else None


def _clipe_com_estalo(destino: Path, *, estalo_em: float, duracao: float = 6.0,
                      com_audio: bool = True) -> Path:
    """mp4 pequeno; com audio, silencio e um tom de 0,2 s em `estalo_em`."""
    comando = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
               f"testsrc=size=64x64:rate=30:duration={duracao}"]
    if com_audio:
        fim = estalo_em + 0.2
        expr = (f"if(between(t\\,{estalo_em}\\,{fim})\\,0.5*sin(2*PI*1000*t)\\,0)")
        comando += ["-f", "lavfi", "-i",
                    f"aevalsrc=exprs={expr}:s={TAXA}:c=stereo:d={duracao}",
                    "-c:a", "aac", "-b:a", "128k"]
    comando += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-shortest", str(destino)]
    subprocess.run(comando, check=True, capture_output=True, timeout=120)
    return destino


# ---------------------------------------------------------------- 1. o corte
class CorteLevaOSomTests(unittest.TestCase):
    TRECHOS = [(0.0, 4.0), (9.0, 3.0), (19.0, 2.0)]

    def test_som_em_t_x_cai_no_relogio_do_clipe(self):
        gravacao = {"duracao_video": 22.0, "sons": [
            {"t": 1.5, "id": "slash_light", "volume": 0.5, "pitch": 1.02},
            {"t": 6.0, "id": "slash_heavy", "volume": 0.6, "pitch": 0.98},   # no corte
            {"t": 10.2, "id": "impact_heavy", "volume": 0.7, "pitch": 1.0, "x": 3.1},
            {"t": 20.5, "id": "ko_impact", "volume": 0.8, "pitch": 1.0},
        ]}
        sons = highlights.remapear_gravacao(gravacao, self.TRECHOS)["sons"]
        self.assertEqual(["slash_light", "impact_heavy", "ko_impact"], [s["id"] for s in sons])
        self.assertAlmostEqual(1.5, sons[0]["t"], places=3)
        self.assertAlmostEqual(4.0 + 1.2, sons[1]["t"], places=3)
        self.assertAlmostEqual(4.0 + 3.0 + 1.5, sons[2]["t"], places=3)
        # o resto da linha atravessa intacto
        self.assertEqual({"id": "impact_heavy", "volume": 0.7, "pitch": 1.0, "x": 3.1},
                         {k: v for k, v in sons[1].items() if k != "t"})

    def test_gravacao_antiga_sem_sons_continua_valendo(self):
        remap = highlights.remapear_gravacao({"duracao_video": 5.0}, [(0.0, 5.0)])
        self.assertEqual([], remap["sons"])

    @unittest.skipUnless(FFMPEG and NUMPY, "ffmpeg e numpy")
    def test_o_audio_atravessa_o_corte_no_lugar_certo(self):
        """Quatro partes com duracao fora do passo de quadro: com partes aac o
        estalo chegava 67 ms atrasado ja na segunda (medido em 28/09/2026)."""
        with tempfile.TemporaryDirectory() as pasta:
            bruto = _clipe_com_estalo(Path(pasta) / "bruto.mp4", estalo_em=10.3,
                                      duracao=16.0)
            trechos = [(0.0, 2.03), (4.11, 2.49), (9.0, 3.37), (14.0, 1.5)]
            cortado = Path(pasta) / "luta.mp4"
            duracao = highlights.extrair(bruto, cortado, trechos, preset="ultrafast", crf=35)
            self.assertAlmostEqual(9.39, duracao, places=2)
            self.assertTrue(medidas.tem_audio(cortado), "o corte tirou o audio (-an)")
            self.assertEqual([], sorted(p.name for p in Path(pasta).iterdir()
                                        if p.suffix in (".mov", ".txt")))
            esperado = highlights.mapear_tempo(trechos, 10.3)
            self.assertAlmostEqual(esperado, _onset(cortado), delta=0.01)
            # quadro a quadro no passo de 30 fps (o .mkv dava 33 e 34 ms)
            saida = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                 "packet=pts_time", "-of", "csv=p=0", str(cortado)],
                capture_output=True, text=True, timeout=60)
            tempos = sorted(float(x) for x in saida.stdout.split() if x.strip())
            passos = [round(b - a, 4) for a, b in zip(tempos, tempos[1:])]
            comuns = [p for p in passos if p < 0.05]
            self.assertTrue(comuns)
            self.assertTrue(all(abs(p - 1 / 30) < 0.0005 for p in comuns), set(comuns))

    @unittest.skipUnless(FFMPEG and NUMPY, "ffmpeg e numpy")
    def test_trecho_unico_copia_o_audio_junto(self):
        with tempfile.TemporaryDirectory() as pasta:
            bruto = _clipe_com_estalo(Path(pasta) / "bruto.mp4", estalo_em=1.0,
                                      duracao=3.0)
            cortado = Path(pasta) / "luta.mp4"
            highlights.extrair(bruto, cortado, [(0.0, 3.0)])
            self.assertTrue(medidas.tem_audio(cortado))
            self.assertAlmostEqual(1.0, _onset(cortado), delta=0.01)


# -------------------------------------------------------- 2. som da luta real
@unittest.skipUnless(FFMPEG and NUMPY, "ffmpeg e numpy")
class SomRealNoSegmentoTests(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        clique = _wav_de_clique(self.pasta / "clique.wav")
        patcher = mock.patch("neural_fights.effects.audio_anotador.arquivos_de_som",
                             return_value={"slash_heavy": clique})
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _evento(sons=None, **extra):
        luta = {"eventos_dano": [[1.0, "p1", 50.0, "ataque_corpo_a_corpo"]],
                "serie_hp": [[0.0, 100.0, 100.0], [4.0, 0.0, 100.0]],
                "eventos_narrativos": []}
        if sons is not None:
            luta["sons"] = sons
        return {"type": "gameplay", "duration": 4.0, "luta": luta, **extra}

    def test_luta_com_sons_soa_com_o_arquivo_real_no_instante(self):
        evento = self._evento([{"t": 2.0, "id": "slash_heavy", "volume": 0.9,
                                "pitch": 1.0}])
        wav = som_da_luta.gravar(evento, self.pasta / "seg_000.mp4", TAXA)
        self.assertEqual(self.pasta / "seg_000.wav", wav)
        self.assertAlmostEqual(2.0, _onset(wav), delta=0.002)

    def test_start_offset_leva_o_som_para_o_relogio_do_trecho(self):
        evento = self._evento([{"t": 12.5, "id": "slash_heavy", "volume": 0.9}],
                              start_offset=10.0)
        wav = som_da_luta.gravar(evento, self.pasta / "seg_001.mp4", TAXA)
        self.assertAlmostEqual(2.5, _onset(wav), delta=0.002)

    def test_luta_antiga_sem_sons_cai_no_sintetizado(self):
        self.assertIsNone(som_da_luta.gravar(self._evento(None), self.pasta / "a.mp4"))

    def test_knob_desligado_volta_ao_sintetizado(self):
        evento = self._evento([{"t": 2.0, "id": "slash_heavy", "volume": 0.9}],
                              som_da_luta={"real": False})
        self.assertIsNone(som_da_luta.gravar(evento, self.pasta / "b.mp4"))

    def test_o_renderer_usa_o_real_e_nao_chama_o_sintetizado(self):
        evento = self._evento([{"t": 2.0, "id": "slash_heavy", "volume": 0.9}])
        render = renderer_mod.VideoRenderer(load_config("render.json"), "celular",
                                            preview=True)
        with mock.patch.object(trilha, "sfx_do_evento",
                               side_effect=AssertionError("sintetizado")):
            wav = render._audio_do_evento(evento, self.pasta / "seg_002.mp4")
        self.assertEqual(self.pasta / "seg_002.wav", wav)

    def test_defeito_no_som_real_cai_no_sintetizado_e_nunca_no_mudo(self):
        evento = self._evento([{"t": 2.0, "id": "slash_heavy", "volume": 0.9}])
        render = renderer_mod.VideoRenderer(load_config("render.json"), "celular",
                                            preview=True)
        with mock.patch.object(som_da_luta, "gravar", side_effect=RuntimeError("x")):
            wav = render._audio_do_evento(evento, self.pasta / "seg_003.mp4")
        self.assertEqual(self.pasta / "seg_003.wav", wav)
        self.assertTrue(wav.is_file())

    def test_reforco_sintetizado_so_com_o_knob(self):
        evento = self._evento([{"t": 2.0, "id": "slash_heavy", "volume": 0.9}])
        with mock.patch.object(trilha, "sfx_da_luta", return_value=[]) as sintetico:
            som_da_luta.gravar(evento, self.pasta / "c.mp4")
            sintetico.assert_not_called()
            evento["som_da_luta"] = {"sintetizado_de_reforco": True}
            som_da_luta.gravar(evento, self.pasta / "d.mp4")
            sintetico.assert_called_once()

    def test_o_padrao_do_config_e_real_sem_reforco(self):
        bloco = load_config("editing.json")["som_da_luta"]
        self.assertTrue(bloco["real"])
        self.assertFalse(bloco["sintetizado_de_reforco"])

    def test_a_montagem_leva_o_knob_para_o_evento(self):
        luta = {"clipes": {"celular": {"path": "x.mp4", "duracao": 3.0}},
                "p1": "A", "p2": "B", "match_id": 0}
        evento = evento_gameplay(mock.Mock(), luta,
                                 {"som_da_luta": {"real": True}}, mock.Mock())
        self.assertEqual({"real": True}, evento["som_da_luta"])


# ------------------------------------------------- 3. transcode sem audio
@unittest.skipUnless(FFMPEG, "ffmpeg")
class TranscodeSemAudioTests(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.clipe = _clipe_com_estalo(self.pasta / "mudo.mp4", estalo_em=0.5,
                                       duracao=1.5, com_audio=False)
        self.render = renderer_mod.VideoRenderer(load_config("render.json"),
                                                 "celular", preview=True)
        self.evento = {"type": "reaction", "duration": 1.0,
                       "asset": {"path": str(self.clipe), "synthetic": False}}

    def test_clipe_sem_faixa_de_audio_sai_com_faixa(self):
        self.assertIs(False, medidas.tem_audio(self.clipe))
        destino = self.pasta / "seg_000.mp4"
        self.render._transcode_asset(dict(self.evento), destino)
        self.assertTrue(medidas.tem_audio(destino),
                        "codigo 0 sem faixa de audio passou calado")

    def test_sem_audio_mesmo_na_segunda_tentativa_e_erro(self):
        with mock.patch.object(renderer_mod.medidas, "tem_audio", return_value=False):
            with self.assertRaises(RuntimeError):
                self.render._transcode_asset(dict(self.evento), self.pasta / "seg_001.mp4")


# ------------------------------------------- 4. sintetizado e start_offset
class SinteticoRespeitaOTrechoTests(unittest.TestCase):
    def test_golpe_e_ko_descontam_o_start_offset(self):
        luta = {"eventos_dano": [[12.0, "p1", 600.0, "ataque_corpo_a_corpo"],
                                 [2.0, "p1", 600.0, "ataque_corpo_a_corpo"]],
                "serie_hp": [[0.0, 100.0, 100.0], [20.0, 0.0, 100.0]],
                "ko_em_clipe": 15.0}
        evento = {"type": "gameplay", "duration": 6.5, "start_offset": 10.0, "luta": luta}
        instantes = sorted(round(t, 2) for t, _a, _g in trilha.sfx_da_luta(evento, TAXA))
        self.assertIn(2.0, instantes)          # o golpe de 12,0 s, no relogio do trecho
        self.assertIn(5.0, instantes)          # o KO de 15,0 s
        self.assertNotIn(12.0, instantes)
        self.assertTrue(all(t <= 6.5 for t in instantes), instantes)


# ------------------------------------------------- 5. re-anotacao e relogio
def _luta_gravada() -> dict:
    return {"p1": "A", "p2": "B", "vencedor": "A", "duracao": 20.3, "seed": 7,
            "cenario": "Duto", "match_id": 0, "camera": "DIRETOR",
            "eventos_dano": [[1.0, "p2", 30.0, "x"], [5.0, "p1", 12.5, "y"]],
            "clipes": {"celular": {"path": "c.mp4", "duracao": 20.0,
                                   "trechos": [[0.0, 20.0]], "resolucao": [1080, 1920]}}}


class ReanotacaoTests(unittest.TestCase):
    def test_confere_a_mesma_luta(self):
        luta = _luta_gravada()
        resultado = {"vencedor": "A", "duracao_jogo": 20.31,
                     "eventos_dano": [[1.0, "p2", 30.0, "x"], [5.0, "p1", 12.5, "y"]]}
        som_real.conferir(luta, resultado, [(0.0, 20.0)])      # nao levanta

    def test_recusa_luta_que_nao_e_a_do_clipe(self):
        luta = _luta_gravada()
        base = {"vencedor": "A", "duracao_jogo": 20.3,
                "eventos_dano": [[1.0, "p2", 30.0, "x"], [5.0, "p1", 12.5, "y"]]}
        for mudanca in ({"vencedor": "B"}, {"duracao_jogo": 25.0},
                        {"eventos_dano": [[1.0, "p2", 30.0, "x"]]},
                        {"eventos_dano": [[1.0, "p2", 30.0, "x"], [5.2, "p1", 12.5, "y"]]}):
            with self.subTest(mudanca=mudanca):
                with self.assertRaises(som_real.LutaDiferente):
                    som_real.conferir(luta, {**base, **mudanca}, [(0.0, 20.0)])

    def test_anota_so_quem_nao_tem_sons_a_menos_de_forcar(self):
        fight = {"lutas": [_luta_gravada(), {**_luta_gravada(), "match_id": 1,
                                             "sons": [{"t": 0.0, "id": "x"}]}]}
        fight["luta"] = dict(fight["lutas"][-1])
        with mock.patch.object(som_real, "anotar_luta",
                               return_value=[{"t": 1.0, "id": "novo"}]) as anotar:
            self.assertEqual(1, som_real.anotar_fight(fight, {}, "duelo"))
            self.assertEqual(1, anotar.call_count)
            self.assertEqual(2, som_real.anotar_fight(fight, {}, "duelo", forcar=True))
        self.assertEqual([{"t": 1.0, "id": "novo"}], fight["luta"]["sons"])

    def test_plano_remendado_por_match_id_sem_remontar(self):
        plano = {"events": [
            {"type": "hook", "caption": "x"},
            {"type": "gameplay", "luta": {"match_id": 1}, "callouts": ["intocado"]},
            {"type": "gameplay", "luta": {"match_id": 2}},
        ]}
        feitos = som_real.aplicar_no_plano(plano, {1: [{"t": 0.5, "id": "a"}]},
                                           {"real": True})
        self.assertEqual(1, feitos)
        self.assertEqual([{"t": 0.5, "id": "a"}], plano["events"][1]["luta"]["sons"])
        self.assertEqual(["intocado"], plano["events"][1]["callouts"])
        self.assertEqual({"real": True}, plano["events"][1]["som_da_luta"])
        self.assertNotIn("sons", plano["events"][2]["luta"])


class SonorizarTests(unittest.TestCase):
    """`main.py som-da-luta` sem render: onde escreve e o que nao toca."""

    SONS = [{"t": 0.5, "id": "slash_heavy", "volume": 0.5, "pitch": 1.0}]

    def _geracao(self, raiz: Path) -> Path:
        dono = raiz / "generation_00001"
        (dono / "estreia").mkdir(parents=True)
        luta = _luta_gravada()
        fight = {"seed": 7, "origem": "estreia", "lutas": [luta], "luta": dict(luta)}
        (dono / "estreia" / "fight.json").write_text(json.dumps(fight), encoding="utf-8")
        plano = {"events": [{"type": "gameplay", "luta": dict(luta)}]}
        for caminho in (dono / "estreia" / "edit_plan.json", dono / "edit_plan.json"):
            caminho.write_text(json.dumps(plano), encoding="utf-8")
        return dono

    def _sonorizar(self, dono: Path, **kwargs) -> dict:
        controller = types.SimpleNamespace(
            editing_config={"som_da_luta": {"real": True}}, perfis=("celular",))
        with mock.patch.object(som_real, "anotar_luta", return_value=list(self.SONS)):
            return sonorizar.sonorizar(controller, str(dono), renderizar=False,
                                       log=lambda *_a: None, **kwargs)

    def test_na_copia_o_original_fica_intocado_e_os_dois_planos_chegam(self):
        with tempfile.TemporaryDirectory() as pasta:
            dono = self._geracao(Path(pasta))
            antes = {p: p.read_bytes() for p in dono.rglob("*.json")}
            copia = Path(pasta) / "copia"
            self._sonorizar(dono, destino=copia)
            self.assertEqual(antes, {p: p.read_bytes() for p in dono.rglob("*.json")})
            fight = json.loads((copia / "estreia" / "fight.json").read_text(encoding="utf-8"))
            self.assertEqual(self.SONS, fight["lutas"][0]["sons"])
            self.assertEqual(self.SONS, fight["luta"]["sons"])
            for nome in ("edit_plan.json", "estreia/edit_plan.json"):
                plano = json.loads((copia / nome).read_text(encoding="utf-8"))
                self.assertEqual(self.SONS, plano["events"][0]["luta"]["sons"], nome)

    def test_so_anotar_no_lugar_nao_envelhece_o_mp4_da_build(self):
        """O catalogo compara o mp4 da build com o `estreia/fight.json`: anotar
        sem renderizar nao pode tirar a build da fila como 'mp4 mais velho'."""
        with tempfile.TemporaryDirectory() as pasta:
            dono = self._geracao(Path(pasta))
            fight = dono / "estreia" / "fight.json"
            data = fight.stat().st_mtime_ns
            self._sonorizar(dono)
            self.assertEqual(data, fight.stat().st_mtime_ns)
            self.assertEqual(self.SONS, json.loads(
                fight.read_text(encoding="utf-8"))["lutas"][0]["sons"])


class RelogioEEstoqueTests(unittest.TestCase):
    def test_nada_comeca_se_encosta_na_folga_da_postagem(self):
        # Desde 30/09/2026 a regra e a meia hora em volta de cada horario da
        # grade (config real), e nao ":25 a :55 de toda hora": sem post
        # perto, 03:20 pode; o post das 09:37 fecha 09:22 a 09:52.
        self.assertTrue(sonorizar.cabe_agora(10, datetime(2026, 9, 28, 3, 20)))
        self.assertTrue(sonorizar.cabe_agora(10, datetime(2026, 9, 28, 9, 0)))
        self.assertFalse(sonorizar.cabe_agora(10, datetime(2026, 9, 28, 9, 15)))
        self.assertFalse(sonorizar.cabe_agora(2, datetime(2026, 9, 28, 9, 40)))
        self.assertTrue(sonorizar.cabe_agora(4, datetime(2026, 9, 28, 9, 53)))
        # 12:07 e 17:57 nao sao :37 — a regra velha nao os via.
        self.assertFalse(sonorizar.cabe_agora(5, datetime(2026, 9, 28, 12, 0)))
        self.assertFalse(sonorizar.cabe_agora(5, datetime(2026, 9, 28, 18, 5)))

    def test_alvos(self):
        raiz = Path("out")
        self.assertEqual("build", sonorizar.resolver("generation_00083", raiz)["tipo"])
        self.assertEqual("build", sonorizar.resolver("generation_00083/estreia", raiz)["tipo"])
        self.assertEqual("duelo", sonorizar.resolver("duelo_00012", raiz)["tipo"])
        self.assertEqual("torneio", sonorizar.resolver("tournament_00006", raiz)["tipo"])
        self.assertEqual("luta", sonorizar.resolver("fight_00004", raiz)["tipo"])
        self.assertEqual("python main.py som-da-luta duelo_00001 generation_00083",
                         sonorizar.comando(["duelo_00001", "generation_00083",
                                            "generation_00083", ""]))

    def test_estoque_lista_so_o_nao_publicado_e_separa_mudo_de_sintetizado(self):
        with tempfile.TemporaryDirectory() as pasta:
            videos = []
            for nome, sons in (("duelo_00001", None), ("duelo_00002", None),
                               ("duelo_00003", []), ("duelo_00004", None)):
                dono = Path(pasta) / nome
                dono.mkdir()
                (dono / "final_celular.mp4").write_bytes(b"x")
                luta = {"match_id": 0, "p1": "Vivo", "p2": "Vivo"}
                if nome == "duelo_00002":
                    luta["p2"] = "Sumido"                 # saiu quando o banco foi refeito
                if sons is not None:
                    luta["sons"] = sons
                (dono / "edit_plan.json").write_text(json.dumps({"events": [
                    {"type": "gameplay", "luta": luta,
                     "asset": {"path_celular": str(dono / "gameplay" / "luta_00_celular.mp4")}}
                ]}), encoding="utf-8")
                videos.append(types.SimpleNamespace(
                    id=f"{nome}:duelo:celular", origem="duelo", perfil="celular",
                    caminho=dono / "final_celular.mp4", fonte_id=nome, pendencias=[]))
            # 00002: golpes a -21 dB com silencio entre eles (63% calado) NAO
            # e luta muda — a regua da luta da guarda so olha a media (6f09b80)
            medidas_falsas = {"duelo_00001": {"media_db": -91.0, "calado": 1.0},
                              "duelo_00002": {"media_db": -21.0, "calado": 0.63},
                              "duelo_00003": {"media_db": -20.0, "calado": 0.0},
                              "duelo_00004": {"media_db": -91.0, "calado": 1.0}}

            def medir(caminho):
                return medidas_falsas[Path(caminho).parents[1].name]

            publicados = [{"video_id": "duelo_00004:duelo:celular", "publicado": True,
                           "url": "publicado no YouTube", "plataforma": "youtube"}]
            with mock.patch("builds.publicar.metricas.publicado",
                            side_effect=lambda linha: bool(linha.get("publicado"))):
                itens = sonorizar.estoque(medir=medir, videos=videos,
                                          publicados=publicados, nomes={"Vivo"})
        por_id = {i["alvo"]: i for i in itens}
        self.assertNotIn("duelo_00004", por_id)              # ja publicado
        self.assertTrue(por_id["duelo_00001"]["muda"])
        self.assertFalse(por_id["duelo_00002"]["muda"])
        self.assertFalse(por_id["duelo_00002"]["som_real"])
        self.assertTrue(por_id["duelo_00003"]["som_real"])
        self.assertTrue(por_id["duelo_00001"]["clipes"][0]["path"].endswith(
            "luta_00_celular.mp4"))
        # sem o lutador no banco a luta nao re-simula: som real impossivel
        self.assertEqual([], por_id["duelo_00001"]["fora_do_banco"])
        self.assertEqual(["Sumido"], por_id["duelo_00002"]["fora_do_banco"])
        self.assertEqual("python main.py duelo --rerender duelo_00002",
                         por_id["duelo_00002"]["rerender_sintetizado"])


if __name__ == "__main__":
    unittest.main()
