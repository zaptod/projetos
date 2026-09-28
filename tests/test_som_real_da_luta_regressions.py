"""Onda 16A: o som REAL do jogo no video da luta.

O som do jogo nunca tinha entrado num mp4: o gravador roda com o driver de
audio `dummy` e a trilha `anullsrc`. Agora o `AudioManager` da partida e um
`AnotadorDeAudio`, que herda toda a decisao de som do jogo e anota em vez de
tocar; a lista vira audio com os arquivos reais (`effects/mixagem.py`).

O que este arquivo trava:

1. o anotador conhece EXATAMENTE os mesmos sons e grupos que o AudioManager
   de verdade (mesmas chaves, mesmos tamanhos de grupo, mesma ordem);
2. a luta com o anotador e a MESMA luta sem ele — vencedor, duracao, HP,
   golpes E o consumo do `random` global (as particulas saem iguais);
3. o pitch vem de um Random proprio com semente e nunca mexe no global;
4. o formato de `sons` (a secao `sons` da timeline da 16C);
5. a mistura poe cada som no instante certo, com pitch, e nunca estoura;
6. o mp4 gravado sai com o som da luta na trilha, nao com silencio.
"""
from __future__ import annotations

import hashlib
import math
import os
import random
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from neural_fights.data.database import carregar_personagens  # noqa: E402
from neural_fights.effects import mixagem  # noqa: E402
from neural_fights.effects.audio import AudioManager  # noqa: E402
from neural_fights.effects.audio_anotador import (  # noqa: E402
    VARIACAO_DE_PITCH,
    AnotadorDeAudio,
)
from neural_fights.recording.fight_recorder import gravar_luta  # noqa: E402
from neural_fights.simulation import simulacao  # noqa: E402

TAXA = mixagem.TAXA


def _tem_ffmpeg() -> bool:
    try:
        return subprocess.run(["ffmpeg", "-version"], capture_output=True,
                              timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


FFMPEG = _tem_ffmpeg()


def _wav_de_clique(destino: Path, duracao: float = 0.2, taxa: int = TAXA) -> Path:
    """Um estalo de amplitude 0,5 no PRIMEIRO sample e silencio depois."""
    n = int(duracao * taxa)
    quadros = bytearray()
    for i in range(n):
        valor = int(0.5 * 32767) if i < 4 else 0
        quadros += int(valor).to_bytes(2, "little", signed=True) * 2
    with wave.open(str(destino), "wb") as arquivo:
        arquivo.setnchannels(2)
        arquivo.setsampwidth(2)
        arquivo.setframerate(taxa)
        arquivo.writeframes(bytes(quadros))
    return destino


class RegistroIgualAoDoJogoTests(unittest.TestCase):
    """O anotador herda a decisao; aqui se prova que herdou por inteiro."""

    def test_mesmas_chaves_e_mesmos_grupos_do_audiomanager(self) -> None:
        inicializado = pygame.mixer.get_init() is not None
        AudioManager.reset()
        try:
            real = AudioManager()
            if not real.enabled:
                self.skipTest("sem mixer nesta maquina")
            anotador = AnotadorDeAudio(seed=1)
            self.assertEqual(sorted(real.sounds), sorted(anotador.sounds))
            self.assertEqual(sorted(real.sound_groups), sorted(anotador.sound_groups))
            for grupo, membros in real.sound_groups.items():
                self.assertEqual(len(membros), len(anotador.sound_groups[grupo]), grupo)
            # nada do anotador passou pelo decodificador do pygame
            self.assertTrue(all(hasattr(s, "arquivo") for s in anotador.sounds.values()))
        finally:
            AudioManager.reset()
            AudioManager.descartar_cache()
            if not inicializado and pygame.mixer.get_init() is not None:
                pygame.mixer.quit()

    def test_variante_de_grupo_e_sorteada_pelo_random_global_como_no_jogo(self) -> None:
        """E isso que mantem as particulas iguais as da gravacao sem anotador."""
        anotador = AnotadorDeAudio(seed=1)
        membros = [s.id for s in anotador.sound_groups["impact"]]
        random.seed(99)
        esperado = random.choice(membros)
        random.seed(99)
        anotador.play("impact", 0.6)
        self.assertEqual(esperado, anotador.sons[-1]["id"])

    def test_pitch_nao_consome_o_random_global(self) -> None:
        anotador = AnotadorDeAudio(seed=1)
        random.seed(5)
        antes = random.getstate()
        for _ in range(20):
            anotador.play("slash_heavy", 0.8)      # som avulso: nenhum sorteio do jogo
        self.assertEqual(antes, random.getstate())
        pitches = {s["pitch"] for s in anotador.sons}
        self.assertGreater(len(pitches), 1, "o pitch nao varia")

    def test_pitch_deterministico_pela_seed(self) -> None:
        a, b, c = AnotadorDeAudio(seed=7), AnotadorDeAudio(seed=7), AnotadorDeAudio(seed=8)
        for anotador in (a, b, c):
            for _ in range(10):
                anotador.play("slash_light", 0.7)
        self.assertEqual([s["pitch"] for s in a.sons], [s["pitch"] for s in b.sons])
        self.assertNotEqual([s["pitch"] for s in a.sons], [s["pitch"] for s in c.sons])
        limite = VARIACAO_DE_PITCH["golpes"]
        for som in a.sons:
            self.assertLessEqual(abs(som["pitch"] - 1.0), limite + 1e-9)


class FormatoDosSonsTests(unittest.TestCase):
    """O contrato de `sons`, que a timeline da 16C herda."""

    def test_uma_linha_por_som_com_t_id_volume_pitch(self) -> None:
        anotador = AnotadorDeAudio(seed=3)
        anotador.t_video = 12.5
        anotador.play("slash_heavy", 0.8)
        som = anotador.sons[-1]
        self.assertEqual({"t", "id", "volume", "pitch"}, set(som))
        self.assertEqual(12.5, som["t"])
        self.assertEqual("slash_heavy", som["id"])
        esperado = 0.8 * anotador.category_volumes["golpes"] * anotador.sfx_volume \
            * anotador.master_volume
        self.assertAlmostEqual(esperado, som["volume"], places=3)

    def test_som_posicional_leva_x_e_pan(self) -> None:
        anotador = AnotadorDeAudio(seed=3)
        anotador.play_positional("slash_light", 12.0, 10.0, volume=0.7)
        som = anotador.sons[-1]
        self.assertEqual(12.0, som["x"])
        self.assertAlmostEqual(0.1, som["pan"], places=3)
        self.assertLessEqual(som["volume"], 1.0)

    def test_fora_do_alcance_nao_toca_como_no_jogo(self) -> None:
        anotador = AnotadorDeAudio(seed=3)
        anotador.play_positional("slash_light", 40.0, 0.0, volume=0.7)
        self.assertEqual([], anotador.sons)

    def test_som_sem_arquivo_nao_vira_linha(self) -> None:
        anotador = AnotadorDeAudio(seed=3)
        anotador.play("nao_existe_este_som", 1.0)
        self.assertEqual([], anotador.sons)


class LutaIgualComESemAnotadorTests(unittest.TestCase):
    """Determinismo: o anotador nao mexe na luta nem no que a tela mostra."""

    def _gravar(self, anotar: bool) -> tuple[dict, str]:
        estados: list[str] = []
        original = simulacao.Simulador.close

        def espiao(sim):
            if not getattr(sim, "_closed", True):
                estados.append(hashlib.md5(repr(random.getstate()).encode()).hexdigest())
            return original(sim)

        personagens = carregar_personagens()
        with mock.patch.object(simulacao.Simulador, "close", espiao):
            resultado = gravar_luta(
                p1=personagens[0].nome, p2=personagens[1].nome, saida=None,
                seed=4242, cenario="Duto", resolucao=(270, 480),
                camera_modo="DIRETOR", max_duracao=10.0, anotar_som=anotar)
        return resultado, estados[-1]

    def test_mesma_luta_e_mesmo_consumo_do_random_global(self) -> None:
        sem, estado_sem = self._gravar(False)
        com, estado_com = self._gravar(True)
        for chave in ("vencedor", "duracao_jogo", "hp_final", "eventos_dano",
                      "ko_em_video", "duracao_video"):
            self.assertEqual(sem[chave], com[chave], chave)
        # O mesmo estado do random global no fim: particulas e tremor de camera
        # sorteados com os mesmos numeros, quadro a quadro.
        self.assertEqual(estado_sem, estado_com)
        self.assertNotIn("sons", sem)
        self.assertTrue(com["sons"], "a luta nao pediu som nenhum")
        tempos = [s["t"] for s in com["sons"]]
        self.assertEqual(sorted(tempos), tempos)
        self.assertEqual(0.0, tempos[0])                    # arena_start, na abertura
        self.assertLessEqual(tempos[-1], com["duracao_video"])
        for som in com["sons"]:
            self.assertTrue(0.0 <= som["volume"] <= 1.0, som)
            self.assertGreater(som["pitch"], 0.0)


@unittest.skipUnless(mixagem.disponivel() and FFMPEG, "numpy e ffmpeg")
class MixagemTests(unittest.TestCase):
    def setUp(self) -> None:
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.clique = _wav_de_clique(self.pasta / "clique.wav")
        self.arquivos = {"clique": self.clique}

    def _onset(self, buf) -> int:
        import numpy as np
        return int(np.argmax(np.abs(buf[:, 0]) > 0.05))

    def test_o_som_cai_no_sample_do_instante(self) -> None:
        buf, rel = mixagem.mixar([{"t": 1.25, "id": "clique", "volume": 1.0, "pitch": 1.0}],
                                 2.0, arquivos=self.arquivos)
        self.assertEqual(1, rel["sons"])
        self.assertLessEqual(abs(self._onset(buf) - int(1.25 * TAXA)), 1)

    def test_inicio_desloca_a_janela_e_a_cauda_de_antes_entra(self) -> None:
        sons = [{"t": 3.0, "id": "clique", "volume": 1.0, "pitch": 1.0}]
        buf, _rel = mixagem.mixar(sons, 2.0, arquivos=self.arquivos, inicio=2.5)
        self.assertLessEqual(abs(self._onset(buf) - int(0.5 * TAXA)), 1)
        # som que comecou ANTES do trecho: so a cauda (aqui silencio) entra
        buf2, rel2 = mixagem.mixar([{"t": 2.4, "id": "clique", "volume": 1.0}], 2.0,
                                   arquivos=self.arquivos, inicio=2.5)
        self.assertEqual(1, rel2["sons"])
        self.assertLess(float(abs(buf2).max()), 1e-6)

    def test_pitch_acelera_a_leitura(self) -> None:
        amostras = mixagem.decodificar(self.clique)
        self.assertEqual(len(amostras) // 2, len(mixagem.com_pitch(amostras, 2.0)))
        self.assertIs(amostras, mixagem.com_pitch(amostras, 1.0))

    def test_id_sem_arquivo_fica_de_fora_e_e_relatado(self) -> None:
        _buf, rel = mixagem.mixar([{"t": 0.1, "id": "fantasma", "volume": 1.0}], 1.0,
                                  arquivos=self.arquivos)
        self.assertEqual(0, rel["sons"])
        self.assertEqual(["fantasma"], rel["sem_arquivo"])

    def test_soma_de_muitos_golpes_nunca_estoura(self) -> None:
        sons = [{"t": 0.5, "id": "clique", "volume": 1.0} for _ in range(40)]
        buf, _rel = mixagem.mixar(sons, 1.0, arquivos=self.arquivos)
        self.assertGreater(float(abs(buf).max()), 1.0, "o teste precisa de soma > 1")
        normal, _ganho = mixagem.normalizar(buf)
        self.assertLessEqual(float(abs(normal).max()), mixagem.TETO + 1e-6)

    def test_o_limitador_nao_achata_o_pico(self) -> None:
        """Pico achatado (varias amostras seguidas no teto) e canto que o aac
        devolve com dB a mais. O ganho entre fronteiras nunca passa do teto,
        entao o `clip` final nao age: no maximo o pico de cada ciclo toca nele."""
        import numpy as np
        # Rajadas curtas e fortes (pico 3,0) depois de silencio, em posicoes
        # soltas dentro do bloco de 5 ms: e o golpe real. Com o ganho
        # interpolado entre os CENTROS dos blocos, este sinal saia com 50
        # amostras acima do teto e picos achatados de 5 amostras.
        rng = np.random.default_rng(3)
        sinal = np.zeros(TAXA, dtype=np.float32)
        n = int(0.004 * TAXA)
        rajada = (3.0 * np.sin(2 * math.pi * 1000 * np.arange(n) / TAXA)).astype(np.float32)
        for k in range(9):
            inicio = int(k * 0.1 * TAXA) + int(rng.integers(0, 220))
            sinal[inicio:inicio + n] += rajada
        saida = mixagem.limitar(np.stack([sinal, sinal], axis=1))
        no_teto = np.abs(saida[:, 0]) >= mixagem.TETO - 1e-6
        seguidas = 0
        maior = 0
        for valor in no_teto:
            seguidas = seguidas + 1 if valor else 0
            maior = max(maior, seguidas)
        self.assertLess(maior, 3, "o limitador cortou em vez de reduzir o ganho")
        self.assertLessEqual(float(np.abs(saida).max()), mixagem.TETO + 1e-6)

    def test_nivel_ativo_vai_para_o_alvo(self) -> None:
        import numpy as np
        t = np.arange(TAXA) / TAXA
        tom = (0.05 * np.sin(2 * math.pi * 220 * t)).astype(np.float32)
        buf = np.stack([tom, tom], axis=1)
        normal, _ganho = mixagem.normalizar(buf, alvo_db=-20.0)
        self.assertAlmostEqual(-20.0, mixagem.nivel_ativo_db(normal), delta=0.5)

    def test_trilha_da_luta_grava_wav_estereo(self) -> None:
        destino = self.pasta / "luta.wav"
        rel = mixagem.trilha_da_luta([{"t": 0.3, "id": "clique", "volume": 0.8}], 1.0,
                                     destino, arquivos=self.arquivos)
        self.assertIsNotNone(rel)
        with wave.open(str(destino)) as arquivo:
            self.assertEqual(2, arquivo.getnchannels())
            self.assertEqual(TAXA, arquivo.getframerate())
        # nenhum som no trecho: nada de fingir que ha som
        self.assertIsNone(mixagem.trilha_da_luta([], 1.0, self.pasta / "vazio.wav",
                                                 arquivos=self.arquivos))


@unittest.skipUnless(mixagem.disponivel() and FFMPEG, "numpy e ffmpeg")
class GravacaoComSomTests(unittest.TestCase):
    def test_o_mp4_gravado_tem_o_som_da_luta_e_nao_silencio(self) -> None:
        personagens = carregar_personagens()
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "luta.mp4"
            resultado = gravar_luta(
                p1=personagens[0].nome, p2=personagens[1].nome, saida=destino,
                seed=4242, cenario="Duto", resolucao=(270, 480),
                camera_modo="DIRETOR", max_duracao=6.0, preset="ultrafast", crf=35)
            self.assertTrue(resultado["sucesso"], resultado.get("erro"))
            self.assertTrue(resultado.get("som_no_video"), resultado.get("erro_som"))
            saida = subprocess.run(
                ["ffmpeg", "-v", "info", "-i", str(destino), "-vn", "-af",
                 "volumedetect", "-f", "null", "-"],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            linha = next((ln for ln in saida.stderr.splitlines() if "mean_volume" in ln), "")
            self.assertTrue(linha, "o mp4 saiu sem faixa de audio")
            media = float(linha.split("mean_volume:")[1].split("dB")[0])
            self.assertGreater(media, -60.0, "a trilha continua muda")
            # o arquivo intermediario nao fica para tras
            self.assertEqual(["luta.mp4"], sorted(p.name for p in Path(pasta).iterdir()))


if __name__ == "__main__":
    unittest.main()
