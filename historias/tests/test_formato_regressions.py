# -*- coding: utf-8 -*-
"""Historia 1,7x e tela dividida, sem trocar de formato no meio (14/09/2026).

Pedido dele: "acelere o video em 1.7 na velocidade, isso inclui a narracao e
tudo mais" e "corte a tela no meio ... na parte de baixo uma parte aleatoria
retirada desse video", em todos os videos daqui pra frente.

Rode de dentro de historias/:
    python -m unittest tests.test_formato_regressions -v
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import wave
from pathlib import Path

from contos.video import formato, fundo, timeline, velocidade


def _plano():
    """Tres cenas encadeadas, a segunda dividida em dois planos."""
    return {
        "total_duration": 30.0,
        "events": [
            {"type": "cena", "n": 1, "start": 0.0, "duration": 8.5,
             "fala_medida": 8.5, "narracao": "um", "titulo": "T",
             "titulo_duracao": 2.2},
            {"type": "cena", "n": 2, "start": 8.5, "duration": 6.25,
             "fala_medida": 12.5, "narracao": "dois"},
            {"type": "cena", "n": 2, "start": 14.75, "duration": 6.25,
             "fala_medida": 12.5, "narracao": "dois", "continuacao": True},
            {"type": "cena", "n": 3, "start": 21.0, "duration": 9.0,
             "fala_medida": None, "narracao": "tres"},
        ],
    }


class EscalarPlanoTests(unittest.TestCase):

    def test_o_plano_continua_encadeado_e_o_total_encolhe(self):
        novo = velocidade.escalar_plano(_plano(), 1.7)
        eventos = novo["events"]
        for atual, proximo in zip(eventos, eventos[1:]):
            self.assertAlmostEqual(proximo["start"],
                                   atual["start"] + atual["duration"], places=3)
        self.assertAlmostEqual(30.0 / 1.7, novo["total_duration"], places=3)
        fim = eventos[-1]["start"] + eventos[-1]["duration"]
        self.assertAlmostEqual(novo["total_duration"], fim, places=2)

    def test_fator_um_nao_muda_nada(self):
        self.assertEqual(_plano(), velocidade.escalar_plano(_plano(), 1.0))

    def test_nao_mexe_no_plano_original(self):
        original = _plano()
        velocidade.escalar_plano(original, 1.7)
        self.assertEqual(_plano(), original)

    def test_fala_medida_encolhe_e_vazia_continua_vazia(self):
        eventos = velocidade.escalar_plano(_plano(), 1.7)["events"]
        self.assertAlmostEqual(8.5 / 1.7, eventos[0]["fala_medida"], places=3)
        self.assertIsNone(eventos[3]["fala_medida"])

    def test_titulo_tem_piso_de_leitura_e_nunca_passa_do_plano(self):
        novo = velocidade.escalar_plano(_plano(), 1.7, titulo_minimo_s=1.4)
        self.assertAlmostEqual(1.4, novo["events"][0]["titulo_duracao"])
        curto = _plano()
        curto["events"][0]["duration"] = 2.0
        curto["events"][1]["start"] = 2.0
        novo = velocidade.escalar_plano(curto, 1.7, titulo_minimo_s=1.4)
        self.assertLessEqual(novo["events"][0]["titulo_duracao"],
                             novo["events"][0]["duration"])

    def test_a_legenda_srt_termina_no_fim_do_video_acelerado(self):
        novo = velocidade.escalar_plano(_plano(), 1.7)
        srt = timeline.legenda_srt(novo)
        # 30 s / 1,7 = 17,647 s; o formatador trunca o milissegundo.
        self.assertRegex(srt.strip().splitlines()[-2], r"--> 00:00:17,64[67]$")


class EscalarPalavrasTests(unittest.TestCase):

    def test_divide_os_tempos_e_guarda_o_resto(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "voz_palavras.json"
            caminho.write_text(json.dumps([
                {"t0": 1.7, "t1": 3.4, "texto": "oi", "linha": 0}]),
                encoding="utf-8")
            self.assertEqual(1, velocidade.escalar_palavras(caminho, 1.7))
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        self.assertEqual({"t0": 1.0, "t1": 2.0, "texto": "oi", "linha": 0},
                         dados[0])


class FundoTests(unittest.TestCase):

    def test_o_mesmo_trecho_para_a_mesma_parte(self):
        a = fundo.offset("historia_00012", 3, 82.0, 3668.0)
        self.assertEqual(a, fundo.offset("historia_00012", 3, 82.0, 3668.0))

    def test_partes_diferentes_pegam_trechos_diferentes(self):
        trechos = {fundo.offset("historia_00012", p, 82.0, 3668.0)
                   for p in range(1, 7)}
        self.assertEqual(6, len(trechos))

    def test_o_trecho_cabe_longe_das_pontas(self):
        for parte in range(1, 40):
            inicio = fundo.offset("historia_00099", parte, 82.0, 3668.0,
                                  20.0, 20.0)
            self.assertGreaterEqual(inicio, 20.0)
            self.assertLessEqual(inicio + 82.0, 3668.0 - 20.0)

    def test_clipe_mais_curto_que_o_video_comeca_do_zero(self):
        self.assertEqual(0.0, fundo.offset("h", 1, 82.0, 30.0))

    def test_sem_arquivo_nao_ha_fundo(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(fundo.escolher(
                "h", 1, 82.0, {"arquivo": "fundo/nao_existe.mp4"}, Path(tmp)))
            self.assertIsNone(fundo.escolher("h", 1, 82.0, {}, Path(tmp)))

    def test_caminho_relativo_e_dentro_de_assets(self):
        assets = Path("E:/x/assets")
        self.assertEqual(assets / "fundo" / "v.mp4",
                         fundo.caminho({"arquivo": "fundo/v.mp4"}, assets))


class FormatoTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name) / "historia_00050"
        self.pasta.mkdir()
        self.cfg = {"formato": {"velocidade": 1.7, "layout": "dividido"}}

    def _plano_da_parte(self, parte: int, dados: dict) -> None:
        destino = self.pasta / "partes" / f"p{parte:02d}"
        destino.mkdir(parents=True)
        (destino / "edit_plan.json").write_text(json.dumps(dados),
                                                encoding="utf-8")

    def test_historia_nova_segue_o_config(self):
        f = formato.resolver("historia_00050", self.cfg, self.pasta)
        self.assertEqual((1.7, "dividido"), (f["velocidade"], f["layout"]))

    def test_historia_com_parte_antiga_fica_no_formato_antigo(self):
        """A historia_00011: p02 publicada antes da mudanca."""
        self._plano_da_parte(2, {"events": []})
        f = formato.resolver("historia_00050", self.cfg, self.pasta)
        self.assertEqual((1.0, "vertical"), (f["velocidade"], f["layout"]))

    def test_mp4_antigo_sem_plano_tambem_trava(self):
        (self.pasta / "final_celular_p01.mp4").write_bytes(b"x")
        f = formato.resolver("historia_00050", self.cfg, self.pasta)
        self.assertEqual("vertical", f["layout"])

    def test_a_primeira_parte_nova_decide_pelas_outras(self):
        self._plano_da_parte(1, {"formato": {"velocidade": 1.5,
                                             "layout": "dividido"}})
        f = formato.resolver("historia_00050", self.cfg, self.pasta)
        self.assertEqual((1.5, "dividido"), (f["velocidade"], f["layout"]))

    def test_uma_parte_convertida_nao_arrasta_as_irmas_antigas(self):
        """14/09/2026: um render de prova gravou 1,7x/dividido no plano da
        p03 da historia 10, que tinha as outras cinco partes no formato
        antigo. A regra antiga ("o primeiro plano com formato decide") faria
        o reparo refazer as irmas no formato novo."""
        self._plano_da_parte(1, {"events": []})
        self._plano_da_parte(3, {"formato": {"velocidade": 1.7,
                                             "layout": "dividido"}})
        f = formato.resolver("historia_00050", self.cfg, self.pasta)
        self.assertEqual((1.0, "vertical"), (f["velocidade"], f["layout"]))

    def test_formato_json_vence_tudo(self):
        self._plano_da_parte(2, {"events": []})
        (self.pasta / "formato.json").write_text(
            json.dumps({"velocidade": 1.7, "layout": "dividido"}),
            encoding="utf-8")
        f = formato.resolver("historia_00050", self.cfg, self.pasta)
        self.assertEqual((1.7, "dividido"), (f["velocidade"], f["layout"]))

    def test_config_sem_bloco_e_o_formato_antigo(self):
        f = formato.resolver("historia_00050", {}, self.pasta)
        self.assertEqual((1.0, "vertical"), (f["velocidade"], f["layout"]))

    def test_valores_absurdos_ficam_dentro_da_faixa(self):
        self.assertEqual(2.0, formato.normalizar({"velocidade": 9})["velocidade"])
        self.assertEqual("vertical",
                         formato.normalizar({"layout": "diagonal"})["layout"])

    def test_rotulo_do_arquivo_ida_e_volta(self):
        texto = formato.rotulo({"velocidade": 1.7, "layout": "dividido"})
        self.assertEqual("contos:velocidade=1.700;layout=dividido", texto)
        self.assertEqual({"velocidade": 1.7, "layout": "dividido"},
                         formato.ler_rotulo(texto))
        self.assertIsNone(formato.ler_rotulo("outro comentario"))


def _tom(caminho: Path, taxa: int = 44100) -> None:
    """0,5 s de silencio e 2,5 s de tom: um 'narrador' que o teste mede."""
    import numpy as np
    t = np.arange(int(2.5 * taxa)) / taxa
    som = (0.4 * np.sin(2 * np.pi * 220 * t) * 32767).astype(np.int16)
    silencio = np.zeros(int(0.5 * taxa), dtype=np.int16)
    mono = np.concatenate([silencio, som])
    estereo = np.stack([mono, mono], axis=1)
    with wave.open(str(caminho), "wb") as fh:
        fh.setnchannels(2)
        fh.setsampwidth(2)
        fh.setframerate(taxa)
        fh.writeframes(estereo.tobytes())


@unittest.skipUnless(shutil.which("ffmpeg"), "sem ffmpeg")
class AcelerarVozTests(unittest.TestCase):

    def _medir(self, filtro: str):
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "voz.wav"
            _tom(wav)
            info = velocidade.acelerar_voz(wav, 1.7, filtro=filtro,
                                           reserva="", log=lambda *_a: None)
            amostras, taxa = velocidade._ler(wav)
            return info, len(amostras) / taxa, velocidade.inicio_da_fala(
                amostras, taxa)

    def test_atempo_o_principal_encolhe_e_nao_desloca_a_fala(self):
        self.assertTrue(velocidade.FILTRO_PADRAO.startswith("atempo"))
        info, duracao, inicio = self._medir(velocidade.FILTRO_PADRAO)
        self.assertIsNotNone(info)
        self.assertAlmostEqual(3.0 / 1.7, duracao, delta=0.03)
        self.assertAlmostEqual(0.5 / 1.7, inicio, delta=0.04)

    def test_rubberband_serve_de_reserva(self):
        """A reserva mede o atraso do filtro: o rubberband entrega atrasado."""
        self.assertTrue(velocidade.RESERVA_PADRAO.startswith("rubberband"))
        info, duracao, inicio = self._medir(velocidade.RESERVA_PADRAO)
        self.assertIsNotNone(info)
        self.assertAlmostEqual(3.0 / 1.7, duracao, delta=0.03)
        self.assertAlmostEqual(0.5 / 1.7, inicio, delta=0.04)

    def test_fator_um_nao_toca_no_arquivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "voz.wav"
            _tom(wav)
            antes = wav.read_bytes()
            velocidade.acelerar_voz(wav, 1.0, log=lambda *_a: None)
            self.assertEqual(antes, wav.read_bytes())

    def test_filtro_que_nao_existe_devolve_none_e_nao_estraga(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "voz.wav"
            _tom(wav)
            antes = wav.read_bytes()
            info = velocidade.acelerar_voz(wav, 1.7, filtro="naoexiste=1",
                                           reserva="", log=lambda *_a: None)
            self.assertIsNone(info)
            self.assertEqual(antes, wav.read_bytes())
            self.assertEqual(["voz.wav"], [p.name for p in Path(tmp).iterdir()])


if __name__ == "__main__":
    unittest.main()
