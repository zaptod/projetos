# -*- coding: utf-8 -*-
"""A vistoria guarda as medidas que so dependem do arquivo (28/09/2026).

`aprovados_no_estoque()` levou 107 s as 02:55 de 28/09 para 19 videos: 51 s
no decode do audio, 35 s nas 266 imagens do detector de colagem, 17 s no
ffprobe, 4 s no resto. A mesma passada roda 2 a 5 vezes por rodada da agenda,
cada rodada num processo novo (71 a 400 s de log parado por rodada no diario
de 27/09). As tres medidas passam a ficar em memoria e em `outputs/`, como o
memo dos trechos pretos: chave = caminho + mtime + tamanho + versao.

    cd e:\\projetos\\historias
    python -m pytest tests/test_vistoria_memo_regressions.py -q
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from contos.publicar import qualidade as Q

SAIDA_DO_AUDIO = """\
[Parsed_volumedetect_0 @ 0] mean_volume: -17.5 dB
[silencedetect @ 0] silence_start: 98.2
[silencedetect @ 0] silence_end: 100.0 | silence_duration: 1.8
"""


def _zerar_memo():
    Q._MEDIDAS.clear()
    Q._MEDIDAS_DO_DISCO.clear()
    Q._ESTADO_DO_MEMO.update({"lido": False, "sujo": False, "pasta": None})


class _ComOutputs(unittest.TestCase):
    """`outputs/` numa pasta temporaria: o memo de verdade nunca e tocado."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.outputs = Path(self._tmp.name) / "outputs"
        self.outputs.mkdir()
        from contos.pipeline import controller
        patcher = mock.patch.object(controller, "OUTPUTS", self.outputs)
        patcher.start()
        self.addCleanup(patcher.stop)
        _zerar_memo()
        self.addCleanup(_zerar_memo)
        self.mp4 = self.outputs / "historia_00001" / "final_celular_p01.mp4"
        self.mp4.parent.mkdir()
        self.mp4.write_bytes(b"um video" * 100)

    def _mudar(self, arquivo: Path, conteudo: bytes):
        arquivo.write_bytes(conteudo)
        futuro = time.time() + 60
        os.utime(arquivo, (futuro, futuro))

    def _memo_no_disco(self) -> dict:
        destino = self.outputs / Q.MEMO_MEDIDAS_NOME
        if not destino.is_file():
            return {}
        return json.loads(destino.read_text(encoding="utf-8"))


class FfprobeTests(_ComOutputs):

    def _rodar_ffprobe(self, dados):
        chamadas = []

        def falso(cmd, **_k):
            chamadas.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, json.dumps(dados), "")
        return chamadas, mock.patch.object(Q.subprocess, "run",
                                           side_effect=falso)

    def test_o_mesmo_arquivo_e_medido_uma_vez(self):
        chamadas, patcher = self._rodar_ffprobe({"format": {"duration": "9"}})
        with patcher:
            a = Q._ffprobe(self.mp4)
            b = Q._ffprobe(self.mp4)
        self.assertEqual(1, len(chamadas))
        self.assertEqual(a, b)

    def test_arquivo_refeito_e_medido_de_novo(self):
        chamadas, patcher = self._rodar_ffprobe({"format": {"duration": "9"}})
        with patcher:
            Q._ffprobe(self.mp4)
            self._mudar(self.mp4, b"outro video, re-renderizado" * 50)
            Q._ffprobe(self.mp4)
        self.assertEqual(2, len(chamadas))

    def test_outro_processo_le_do_disco(self):
        chamadas, patcher = self._rodar_ffprobe({"format": {"duration": "9"}})
        with patcher:
            Q._ffprobe(self.mp4)
            Q._gravar_medidas()                # a vistoria grava no fim
            _zerar_memo()                      # "outro processo"
            self.assertEqual({"format": {"duration": "9"}}, Q._ffprobe(self.mp4))
        self.assertEqual(1, len(chamadas))

    def test_falha_nao_vai_ao_memo(self):
        with mock.patch.object(Q.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("x", 60)):
            self.assertIsNone(Q._ffprobe(self.mp4))
        chamadas, patcher = self._rodar_ffprobe({"format": {"duration": "9"}})
        with patcher:
            self.assertEqual({"format": {"duration": "9"}}, Q._ffprobe(self.mp4))
        self.assertEqual(1, len(chamadas))

    def test_timeout_declara_que_nao_mediu_sem_inventar_video_mudo(self):
        with mock.patch.object(Q, "_ffprobe", return_value=None):
            laudo = Q.vistoriar_arquivo(self.mp4)
        self.assertIn("nao consegui medir o arquivo (ffprobe)", laudo["erros"])
        self.assertNotIn("sem faixa de audio: o video vai ao ar mudo",
                         laudo["erros"])

    def test_quem_chama_nao_suja_o_memo(self):
        chamadas, patcher = self._rodar_ffprobe({"format": {"duration": "9"}})
        with patcher:
            Q._ffprobe(self.mp4)["format"]["duration"] = "999"
            self.assertEqual("9", Q._ffprobe(self.mp4)["format"]["duration"])

    def test_o_comando_ainda_pede_a_etiqueta(self):
        chamadas, patcher = self._rodar_ffprobe({"format": {}})
        with patcher:
            Q._ffprobe(self.mp4)
        self.assertIn("format_tags=comment", " ".join(chamadas[0]))


class AudioTests(_ComOutputs):

    def test_mede_uma_vez_e_guarda_media_e_calado(self):
        chamadas = []

        def falso(cmd, **_k):
            chamadas.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", SAIDA_DO_AUDIO)
        with mock.patch.object(Q.subprocess, "run", side_effect=falso):
            primeira = Q._audio(self.mp4, 100.0)
            segunda = Q._audio(self.mp4, 100.0)
        self.assertEqual(1, len(chamadas))
        self.assertEqual((-17.5, 1.8), (primeira[0], round(primeira[1], 1)))
        self.assertEqual(primeira, segunda)
        Q._gravar_medidas()
        _zerar_memo()
        with mock.patch.object(Q.subprocess, "run", side_effect=falso):
            self.assertEqual(primeira[0], Q._audio(self.mp4, 100.0)[0])
        self.assertEqual(1, len(chamadas), "o segundo processo leu do disco")

    def test_sem_media_nao_vai_ao_memo(self):
        chamadas = []

        def falso(cmd, **_k):
            chamadas.append(cmd)
            return subprocess.CompletedProcess(cmd, 1, "", "erro qualquer")
        with mock.patch.object(Q.subprocess, "run", side_effect=falso):
            Q._audio(self.mp4, 100.0)
            Q._audio(self.mp4, 100.0)
        self.assertEqual(2, len(chamadas))

    def test_leitura_da_saida_nao_mudou(self):
        self.assertEqual((-17.5, 0.0), Q._ler_audio(SAIDA_DO_AUDIO, 110.0))
        self.assertEqual((None, 0.0), Q._ler_audio("", 110.0))

    def test_ffmpeg_que_estoura_o_prazo_e_nao_medi_e_nao_sem_defeito(self):
        """Auditoria de 11/10/2026 (p3): mp4 MUDO de verdade reprovava
        ("audio a -91.0 dB"); com o ffmpeg estourando os 300 s (disco a 0%
        ocioso em 06/10) a vistoria devolvia `erros = []`, `media_db = None`
        e o video mudo seguia para a grade. Agora a vistoria diz que nao
        mediu — e nao afirma nem "mudo" nem "sem defeito"."""
        sonda = {"format": {"duration": "120"},
                 "streams": [{"codec_type": "video"}, {"codec_type": "audio"}]}

        def estoura(cmd, **_k):
            if cmd[0] == "ffmpeg":
                raise subprocess.TimeoutExpired(cmd, 300)
            return subprocess.CompletedProcess(cmd, 0, json.dumps(sonda), "")
        with mock.patch.object(Q.subprocess, "run", side_effect=estoura), \
                mock.patch.object(Q, "erros_de_preto", return_value=[]):
            laudo = Q.vistoriar_arquivo(self.mp4)
        self.assertIn("nao consegui medir o audio (ffmpeg)", laudo["erros"])
        self.assertFalse(any("mudo" in e for e in laudo["erros"]), laudo["erros"])
        self.assertIsNone(laudo["media_db"])
        self.assertIsNone(laudo["silencio_final"])
        self.assertTrue(laudo["audio"])

    def test_caso_zero_ffmpeg_que_mede_segue_reprovando_o_mudo(self):
        sonda = {"format": {"duration": "120"},
                 "streams": [{"codec_type": "video"}, {"codec_type": "audio"}]}

        def mede_mudo(cmd, **_k):
            if cmd[0] == "ffmpeg":
                return subprocess.CompletedProcess(
                    cmd, 0, "", "[Parsed_volumedetect_0 @ 0] mean_volume: -91.0 dB\n")
            return subprocess.CompletedProcess(cmd, 0, json.dumps(sonda), "")
        with mock.patch.object(Q.subprocess, "run", side_effect=mede_mudo), \
                mock.patch.object(Q, "erros_de_preto", return_value=[]):
            laudo = Q.vistoriar_arquivo(self.mp4)
        self.assertTrue(any("praticamente mudo" in e for e in laudo["erros"]),
                        laudo["erros"])


class ColagemTests(_ComOutputs):

    def setUp(self):
        super().setUp()
        from PIL import Image
        self.png = self.outputs / "historia_00001" / "p01_cena_01.png"
        Image.new("RGB", (64, 64), "gray").save(self.png)

    def test_detector_roda_uma_vez_por_imagem(self):
        from contos.imagens import composicao
        with mock.patch.object(composicao, "motivo",
                               return_value="parece colagem: x") as motivo:
            self.assertEqual("parece colagem: x", Q._motivo_de_colagem(self.png))
            self.assertEqual("parece colagem: x", Q._motivo_de_colagem(self.png))
        self.assertEqual(1, motivo.call_count)

    def test_imagem_ilegivel_nao_guarda_vazio(self):
        """Um "" de imagem que nao abriu faria uma colagem passar para sempre."""
        from contos.imagens import composicao
        self._mudar(self.png, b"\x89PNG meio baixado")
        with mock.patch.object(composicao, "motivo", return_value="") as motivo:
            Q._motivo_de_colagem(self.png)
            Q._motivo_de_colagem(self.png)
        self.assertEqual(2, motivo.call_count)

    def test_detector_novo_mede_de_novo(self):
        from contos.imagens import composicao
        with mock.patch.object(composicao, "motivo", return_value="") as motivo:
            Q._motivo_de_colagem(self.png)
            with mock.patch.object(Q, "_versao_do_fonte", return_value="outra"):
                Q._motivo_de_colagem(self.png)
        self.assertEqual(2, motivo.call_count)

    def test_a_vistoria_usa_o_memo(self):
        import inspect
        fonte = inspect.getsource(Q._erros_das_imagens)
        self.assertIn("_motivo_de_colagem(arquivo)", fonte)
        self.assertNotIn("composicao.motivo(", fonte)


class DiscoTests(_ComOutputs):

    def test_fora_de_outputs_nunca_escreve(self):
        with tempfile.TemporaryDirectory() as fora:
            mp4 = Path(fora) / "x.mp4"
            mp4.write_bytes(b"x" * 100)
            with mock.patch.object(Q.subprocess, "run", return_value=(
                    subprocess.CompletedProcess([], 0, '{"format": {"d": 1}}',
                                                ""))) as rodar:
                Q._ffprobe(mp4)
                Q._ffprobe(mp4)
                Q._gravar_medidas()
            self.assertEqual(1, rodar.call_count, "em memoria vale")
        self.assertFalse((self.outputs / Q.MEMO_MEDIDAS_NOME).exists())

    def test_arquivo_apagado_sai_do_memo(self):
        outro = self.mp4.with_name("final_celular_p02.mp4")
        outro.write_bytes(b"dois" * 100)
        with mock.patch.object(Q.subprocess, "run", return_value=(
                subprocess.CompletedProcess([], 0, '{"format": {"d": 1}}', ""))):
            Q._ffprobe(self.mp4)
            Q._ffprobe(outro)
            Q._gravar_medidas()
            self.assertEqual(2, len(self._memo_no_disco()))
            outro.unlink()
            self._mudar(self.mp4, b"refeito" * 99)
            Q._ffprobe(self.mp4)
            Q._gravar_medidas()
        memo = self._memo_no_disco()
        self.assertEqual(1, len(memo))
        self.assertTrue(all("final_celular_p01.mp4" in k for k in memo))

    def test_memo_quebrado_so_faz_medir(self):
        (self.outputs / Q.MEMO_MEDIDAS_NOME).write_text("{", encoding="utf-8")
        with mock.patch.object(Q.subprocess, "run", return_value=(
                subprocess.CompletedProcess([], 0, '{"format": {"d": 1}}', ""))):
            self.assertEqual({"format": {"d": 1}}, Q._ffprobe(self.mp4))
            Q._gravar_medidas()
        self.assertEqual(1, len(self._memo_no_disco()))

    def test_medida_de_outra_pasta_nao_vai_para_este_memo(self):
        """Um teste que aponta `outputs/` para outra pasta nao pode deixar
        medida no memo de producao, nem levar a de producao para a dele."""
        with mock.patch.object(Q.subprocess, "run", return_value=(
                subprocess.CompletedProcess([], 0, '{"format": {"d": 1}}', ""))):
            Q._ffprobe(self.mp4)                     # sujo, pasta = outputs
            with tempfile.TemporaryDirectory() as outra:
                with mock.patch.object(Q, "_outputs", return_value=Path(outra)):
                    Q._gravar_medidas()
                    self.assertFalse((Path(outra) / Q.MEMO_MEDIDAS_NOME)
                                     .exists())
        self.assertFalse((self.outputs / Q.MEMO_MEDIDAS_NOME).exists(),
                         "a medida esquecida nao reaparece sozinha")

    def test_a_vistoria_grava_no_fim(self):
        import inspect
        self.assertIn("_gravar_medidas()",
                      inspect.getsource(Q.vistoriar_arquivo))
        self.assertIn("_gravar_medidas()",
                      inspect.getsource(Q._erros_das_imagens))


if __name__ == "__main__":
    unittest.main()
