# -*- coding: utf-8 -*-
"""Postagem de 15/09/2026: video mudo, YouTube caido e a fila por plataforma.

A auditoria da noite de 14 para 15/09 achou tres coisas na grade:

1. VIDEO MUDO IA AO AR. A estreia da generation_00065 media -91 dB e estava
   marcada para as 10:07, no YouTube e no TikTok. `proximo_build` nao olhava
   o audio.
2. YOUTUBE CAIDO DERRUBAVA O TIKTOK. So a cota tinha tratamento: qualquer
   outra falha do Studio subia ate `main`, e o TikTok daquele horario nunca
   rodava (nos dois canais).
3. A FILA CONTAVA QUALQUER PLATAFORMA. Parte que so ia ao TikTok saia da fila
   do YouTube para sempre. Agora a fila do YouTube conta so o YouTube, e o
   TikTok nao posta de novo o que ja esta la.

Rode de dentro de historias/:
    python -m unittest tests.test_postagem_resiliente_regressions -v
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
POSTAR = RAIZ.parent / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_resiliente", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _Video:
    def __init__(self, id_, *, fonte_id="f", parte=1, partes=6, caminho="",
                 origem="build", quando=0.0):
        self.id, self.fonte_id, self.parte, self.partes = id_, fonte_id, parte, partes
        self.titulo, self.caminho, self.origem, self.quando = id_, caminho, origem, quando
        self.perfil, self.pendencias = "celular", None


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


@unittest.skipUnless(shutil.which("ffmpeg"), "precisa do ffmpeg")
class AudioMudoTests(unittest.TestCase):
    """A medida e a de verdade: mp4 gerado pelo ffmpeg, sem duble."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name)
        video = ["-f", "lavfi", "-i", "color=c=black:s=64x64:d=1"]
        cls.mudo = base / "mudo.mp4"
        cls.com_som = base / "som.mp4"
        cls.sem_faixa = base / "sem_faixa.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", *video, "-f", "lavfi",
                        "-i", "anullsrc=r=44100:cl=mono", "-t", "1",
                        "-shortest", str(cls.mudo)], check=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", *video, "-f", "lavfi",
                        "-i", "sine=frequency=440:duration=1", "-t", "1",
                        "-shortest", str(cls.com_som)], check=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", *video, "-t", "1",
                        str(cls.sem_faixa)], check=True)
        # 3,5 s calados e 0,5 s de som: o defeito das estreias do render antigo
        # (media -27 a -30 dB, 93% a 95% de silencio).
        cls.quase_mudo = base / "quase_mudo.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=64x64:d=4", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=4", "-af",
                        "volume=enable='lt(t,3.5)':volume=0", "-t", "4",
                        "-shortest", str(cls.quase_mudo)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.m = _postar()

    def test_mudo_e_barrado(self):
        self.assertIn("mudo", self.m._audio_mudo(_Video("a", caminho=self.mudo)))

    def test_sem_faixa_de_audio_e_barrado(self):
        self.assertIn("faixa", self.m._audio_mudo(_Video("a", caminho=self.sem_faixa)))

    def test_quase_mudo_e_barrado_mesmo_com_media_alta(self):
        motivo = self.m._audio_mudo(_Video("a", caminho=self.quase_mudo))
        self.assertIn("calado", motivo)

    def test_com_som_passa(self):
        self.assertEqual("", self.m._audio_mudo(_Video("a", caminho=self.com_som)))

    def test_arquivo_que_nao_existe_nao_barra(self):
        """Quem cuida de arquivo sumido e outra guarda; aqui nao se inventa mudo."""
        self.assertEqual("", self.m._audio_mudo(_Video("a", caminho="nao/existe.mp4")))


class ProximoBuildPulaMudoTests(unittest.TestCase):

    def setUp(self):
        from builds.publicar import catalogo, metricas
        self.m = _postar()
        _trocar(self, metricas, "publicados", lambda canal="builds": [])
        self.catalogo = catalogo
        _trocar(self, self.m, "_servidos_recentes", lambda n=16: {})
        _trocar(self, self.m, "cota_da_grade", lambda config=None: {})

    def _catalogo(self, videos):
        _trocar(self, self.catalogo, "listar", lambda *a, **k: list(videos))

    def test_o_mais_antigo_mudo_e_pulado(self):
        # o catalogo vem do mais NOVO para o mais velho
        self._catalogo([_Video("novo_ok"), _Video("velho_mudo")])
        self.m._audio_mudo = lambda v: "o audio esta mudo" if v.id == "velho_mudo" else ""
        self.assertEqual("novo_ok", self.m.proximo_build().id)

    def test_todos_mudos_nao_ha_video(self):
        self._catalogo([_Video("a"), _Video("b")])
        self.m._audio_mudo = lambda v: "o audio esta mudo"
        self.assertIsNone(self.m.proximo_build())

    def test_video_que_saiu_no_tiktok_sai_da_fila(self):
        """Contar so o YouTube repetia o video em todo horario de cota
        (revisao de 15/09/2026): o TikTok postava 1 de 6."""
        from builds.publicar import metricas
        _trocar(self, metricas, "publicados", lambda canal="builds": [
            {"video_id": "so_tk", "url": "publicado no TikTok", "plataforma": "tiktok"}])
        self._catalogo([_Video("so_tk")])
        self.m._audio_mudo = lambda v: ""
        self.assertIsNone(self.m.proximo_build())


class YouTubeCaidoNaoDerrubaTikTokTests(unittest.TestCase):

    def setUp(self):
        from builds.publicar import tiktok
        self.m = _postar()
        self.m.publicou_neste_horario = lambda *a, **k: None
        self.m._tiktok_neste_horario = lambda agora=None: True
        self.avisos = []
        self.m.avisar_limite_diario = lambda texto: self.avisos.append(texto)
        _trocar(self, tiktok, "confirmado", lambda estado: estado == "publicado no TikTok")

    def test_tiktok_nao_confirmado_com_youtube_caido_nao_e_feito(self):
        from builds.publicar import youtube

        def cai(*a, **k):
            raise RuntimeError("Studio caiu")
        _trocar(self, youtube, "publicar_como_configurado", cai)
        self.m.proximo_build = lambda config=None: _Video("g1")
        self.m._tiktok_dos_builds = lambda alvo: ("cliquei em publicar, mas o TikTok "
                                                   "nao confirmou")
        self.assertFalse(self.m.postar_build()["feito"])

    def test_builds_segue_para_o_tiktok_com_falha_comum(self):
        from builds.publicar import youtube

        def cai(*a, **k):
            raise RuntimeError("o YouTube nao terminou de processar o video a tempo")
        _trocar(self, youtube, "publicar_como_configurado", cai)
        self.m.proximo_build = lambda config=None: _Video("g1")
        self.m._tiktok_dos_builds = lambda alvo: "publicado no TikTok"
        ficha = self.m.postar_build()
        self.assertEqual("publicado no TikTok", ficha["tiktok"])
        self.assertTrue(ficha["feito"])
        self.assertTrue(ficha["youtube_falhou"])
        self.assertIn("processar", ficha["motivo"])
        self.assertEqual([], self.avisos)

    def test_builds_na_cota_avisa_e_segue(self):
        from builds.publicar import youtube
        from builds.publicar.youtube_web import LimiteDiarioDoYouTube

        def cota(*a, **k):
            raise LimiteDiarioDoYouTube("O limite diário de envios foi alcançado")
        _trocar(self, youtube, "publicar_como_configurado", cota)
        self.m.proximo_build = lambda config=None: _Video("g1")
        self.m._tiktok_dos_builds = lambda alvo: "publicado no TikTok"
        ficha = self.m.postar_build()
        self.assertTrue(ficha["cota_youtube"])
        self.assertEqual("publicado no TikTok", ficha["tiktok"])
        self.assertEqual(1, len(self.avisos))

    def test_historias_segue_para_o_tiktok_com_falha_comum(self):
        from contos.publicar import catalogo

        def cai(*a, **k):
            raise RuntimeError("o Google pediu login")
        _trocar(self, catalogo, "publicar_youtube", cai)
        video = _Video("historia_00012:celular:p01", fonte_id="historia_00012")
        self.m.proxima_historia = lambda **k: (video, [])
        self.m._visibilidade_das_historias = lambda: "public"
        self.m._veto_vencido = lambda alvo: False
        self.m._veto_lembrado = lambda alvo: ""
        self.m._tiktok_das_historias = lambda alvo: "publicado no TikTok"
        ficha = self.m.postar_historia()
        self.assertEqual("publicado no TikTok", ficha["tiktok"])
        self.assertTrue(ficha["feito"])
        self.assertTrue(ficha["youtube_falhou"])
        self.assertIn("login", ficha["motivo"])


class CotaODiaInteiroTests(unittest.TestCase):
    """Revisao de 15/09/2026: com o YouTube na cota em todos os horarios, o
    TikTok tem que postar uma parte NOVA em cada horario dele, na ordem."""

    def test_o_tiktok_anda_a_serie_mesmo_com_o_youtube_na_cota(self):
        from builds.publicar import tiktok
        from builds.publicar.youtube_web import LimiteDiarioDoYouTube
        from contos.publicar import catalogo, serie
        m = _postar()
        videos = [_Video(f"h:celular:p0{n}", fonte_id="h", parte=n) for n in (1, 2, 3)]
        ledger = []
        _trocar(self, catalogo, "listar", lambda *a, **k: list(videos))

        def cota(*a, **k):
            raise LimiteDiarioDoYouTube("O limite diário de envios foi alcançado")
        _trocar(self, catalogo, "publicar_youtube", cota)
        _trocar(self, catalogo, "publicar_tiktok", lambda alvo, **k: "publicado no TikTok")
        _trocar(self, tiktok, "confirmado", lambda estado: True)
        _trocar(self, serie, "publicados", lambda: list(ledger))
        _trocar(self, serie, "ja_publicado", lambda vid, plataforma="youtube": next(
            (l for l in ledger if l["video_id"] == vid and l["plataforma"] == plataforma), None))
        _trocar(self, serie, "registrar", lambda video, url, plataforma, quando, extra=None:
                ledger.append({"video_id": video.id, "url": url, "plataforma": plataforma,
                               "fonte_id": video.fonte_id, "parte": video.parte}))
        m._prioridades = lambda: []
        m.publicou_neste_horario = lambda *a, **k: None
        m._tiktok_neste_horario = lambda agora=None: True
        m.avisar_limite_diario = lambda texto: None
        m._visibilidade_das_historias = lambda: "public"
        m._veto_vencido = lambda alvo: False
        m._veto_lembrado = lambda alvo: ""

        def proxima(**k):
            fila = m.fila_de_historias()
            return (fila[0] if fila else None), []
        m.proxima_historia = proxima
        for _ in range(3):
            m.postar_historia()
        self.assertEqual(["h:celular:p01", "h:celular:p02", "h:celular:p03"],
                         [l["video_id"] for l in ledger if l["plataforma"] == "tiktok"])


class FilaContaQualquerPlataformaTests(unittest.TestCase):

    def test_parte_que_saiu_no_tiktok_sai_da_fila(self):
        from contos.publicar import catalogo, serie
        m = _postar()
        video = _Video("h:celular:p01", fonte_id="h", parte=1)
        _trocar(self, catalogo, "listar", lambda *a, **k: [video])
        _trocar(self, serie, "publicados", lambda: [
            {"video_id": "h:celular:p01", "url": "publicado no TikTok",
             "plataforma": "tiktok", "fonte_id": "h", "parte": 1}])
        m._prioridades = lambda: []
        self.assertEqual([], m.fila_de_historias())

    def test_parte_no_youtube_sai_da_fila(self):
        from contos.publicar import catalogo, serie
        m = _postar()
        video = _Video("h:celular:p01", fonte_id="h", parte=1)
        _trocar(self, catalogo, "listar", lambda *a, **k: [video])
        _trocar(self, serie, "publicados", lambda: [
            {"video_id": "h:celular:p01", "url": "https://youtu.be/x",
             "fonte_id": "h", "parte": 1}])
        m._prioridades = lambda: []
        self.assertEqual([], m.fila_de_historias())


class TikTokNaoRepeteTests(unittest.TestCase):

    def test_historia_ja_no_tiktok_nao_sobe_de_novo(self):
        from contos.publicar import catalogo, serie
        m = _postar()
        _trocar(self, serie, "ja_publicado",
                lambda video_id, plataforma="youtube": {"url": "x"} if plataforma == "tiktok" else None)

        def nao_era_para_subir(*a, **k):
            raise AssertionError("postou de novo no TikTok")
        _trocar(self, catalogo, "publicar_tiktok", nao_era_para_subir)
        self.assertEqual("", m._tiktok_das_historias(_Video("h:celular:p01")))

    def test_build_ja_no_tiktok_nao_sobe_de_novo(self):
        from builds.publicar import tiktok
        m = _postar()
        m._build_ja_no_tiktok = lambda video_id: True

        def nao_era_para_subir(*a, **k):
            raise AssertionError("postou de novo no TikTok")
        _trocar(self, tiktok, "publicar", nao_era_para_subir)
        self.assertEqual("", m._tiktok_dos_builds(_Video("g1")))


class AvisoDaFalhaDoYouTubeTests(unittest.TestCase):

    def test_o_aviso_diz_que_o_youtube_falhou(self):
        m = _postar()
        enviado = []
        m.estoque = lambda: {}
        m.estoque_por_formato = lambda: {}
        m._conta_do_destino = lambda servico, canal: "conta"
        original = subprocess.run
        subprocess.run = (lambda *a, **k: enviado.append(a[0][-1])
                          or type("R", (), {"returncode": 0})())
        try:
            m.avisar([{"canal": "builds", "feito": True, "alvo": "g1",
                       "titulo": "g1", "url": "", "youtube_falhou": True,
                       "motivo": "YouTube falhou: RuntimeError: Studio caiu",
                       "tiktok": "publicado no TikTok"}])
        finally:
            subprocess.run = original
        self.assertTrue(enviado)
        self.assertIn("falhou", enviado[0])
        self.assertIn("Studio caiu", enviado[0])


if __name__ == "__main__":
    unittest.main()
