# -*- coding: utf-8 -*-
"""O apagado do canal nunca volta ao YouTube (21/10/2026).

Decisao do Adrian `publicacao/videos-presos-no-canal`: "apagar e NAO
reenviar". O cf4653cf apagou do canal de builds os 5 envios vazios e curou o
ledger (`curar_ledger.py --apagado-do-canal`): a linha do YouTube virou
`publicado: false`, `estado: apagado_do_canal`. A do TikTok seguiu publicada.

O furo medido: "nao publicado" quer dizer "falta subir" para a divida do
YouTube dos builds (TikTok publicado desde 12/10 e nenhum YouTube publicado).
Os 5 so ficavam fora porque `TROCAS_NA_COTA` troca build e estreia por duelo
— reabrir a cota de build os mandaria de volta. Agora todo caminho pergunta a
`metricas.apagado_do_canal`: a divida (builds e historias), a fila dos builds
(`_builds_prontos`), a fila das historias, a recuperacao do YouTube e o funil
`youtube.publicar_como_configurado` (app, bot, `--so-youtube`).

Rode de dentro de historias/:
    python -m unittest tests.test_apagado_do_canal_nao_volta_regressions -v
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"

# Os 5 de 21/10 (cf4653cf), com o id do YouTube que cada um tinha.
APAGADOS = {"generation_00121:estreia:celular": "8Rp3WUDsBgA",
            "generation_00120:estreia:celular": "CHogZyWtA8I",
            "generation_00098:build:celular": "CVN0zvP9dwI",
            "generation_00110:build:celular": "4uL9SZDiZug",
            "generation_00120:build:celular": "HJg-UxbKToc"}
NOVO = "generation_00130:build:celular"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_apagado", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


class _Build:
    def __init__(self, vid):
        self.id = vid
        self.titulo = f"Build {vid}"
        self.perfil = "celular"
        self.formato = self.origem = vid.split(":")[1]
        self.pendencias = []
        self.quando = ""


def _tiktok(vid, quando):
    return {"canal": "builds", "plataforma": "tiktok", "video_id": vid,
            "url": "publicado no TikTok", "publicado": True, "quando": quando}


def _apagado(vid, quando):
    # Como `curar_ledger._curas` grava (cf4653cf).
    return {"canal": "builds", "plataforma": "youtube", "video_id": vid,
            "url": "", "publicado": False, "estado": "apagado_do_canal",
            "youtube_id": None, "apagado_id": APAGADOS[vid], "quando": quando}


class CriterioTests(unittest.TestCase):

    def test_caso_zero_e_o_estado(self):
        from builds.publicar import metricas
        self.assertEqual(set(), metricas.apagados([]))
        self.assertEqual(set(), metricas.apagados(
            [_tiktok(NOVO, "2026-10-21T09:40:00")]))
        linhas = [_apagado(v, "2026-10-20T01:45:00") for v in APAGADOS]
        self.assertEqual(set(APAGADOS), metricas.apagados(linhas))
        self.assertEqual(set(), metricas.apagados(linhas, "tiktok"))
        self.assertFalse(metricas.publicado(linhas[0]))

    def test_o_curar_ledger_grava_o_mesmo_nome(self):
        spec = importlib.util.spec_from_file_location(
            "curar_apagado", POSTAR.parent / "curar_ledger.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        from builds.publicar import metricas
        self.assertEqual(metricas.ESTADO_APAGADO, m.APAGADO)


class _ComLedger(unittest.TestCase):
    """Ledger dublado: os 5 apagados no YouTube e publicados no TikTok desde
    12/10, e a cota de build e estreia REABERTA (`TROCAS_NA_COTA` vazio)."""

    def setUp(self):
        from builds import atividade
        from builds.publicar import audio, desfecho, metricas
        from builds.publicar import catalogo as C
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        pasta = Path(self.tmp.name)
        _trocar(self, desfecho, "arquivo_a_conferir",
                lambda canal, p="tiktok": pasta / f"{canal}_{p}.json")
        self.addCleanup(desfecho._SEM_MARCA.clear)
        _trocar(self, atividade, "registrar", lambda *a, **k: None)
        self.ledger = []
        for vid in APAGADOS:
            self.ledger += [_tiktok(vid, "2026-10-19T22:48:00"),
                            _apagado(vid, "2026-10-19T22:50:00")]
        _trocar(self, metricas, "publicados",
                lambda canal="builds": list(self.ledger))
        self.catalogo = [_Build(v) for v in APAGADOS]
        _trocar(self, C, "listar", lambda *a, **k: list(self.catalogo))
        _trocar(self, audio, "revisar_marcas", lambda *a, **k: None)
        self.m = m = _postar()
        m._linha = lambda *a, **k: None
        m._audio_mudo = lambda v: ""
        m.titulo_repetido = lambda *a, **k: False
        m._fontes_cheias_hoje = lambda *a, **k: set()
        # A COTA DE BUILD E ESTREIA REABERTA: e o que hoje segurava os 5.
        m.TROCAS_NA_COTA = {"youtube": {}, "tiktok": {}}


class DividaDosBuildsTests(_ComLedger):

    def test_com_a_cota_reaberta_o_apagado_nao_e_divida(self):
        v, quando, motivos = self.m._procurar_divida_dos_builds()
        self.assertIsNone(v)
        self.assertEqual("", quando)

    def test_controle_sem_o_estado_seria_divida(self):
        """O mesmo ledger sem a cura: a divida levaria o apagado de volta."""
        for linha in self.ledger:
            if linha.get("estado") == "apagado_do_canal":
                linha.pop("estado")
        v, _quando, _motivos = self.m._procurar_divida_dos_builds()
        self.assertIn(v.id, APAGADOS)


class FilaDosBuildsTests(_ComLedger):

    def test_apagado_so_no_youtube_nunca_e_escolhido(self):
        """Sem linha do TikTok, o build so com a linha apagada era "novo"."""
        self.ledger[:] = [_apagado(v, "2026-10-19T22:50:00")
                          for v in APAGADOS]
        self.catalogo.append(_Build(NOVO))
        prontos = self.m._builds_prontos(medir_audio=False)
        self.assertEqual([NOVO], [v.id for v in prontos])


class RecuperacaoDoYouTubeTests(_ComLedger):

    def test_privado_com_o_id_apagado_nao_volta_ao_ar(self):
        from builds.publicar import recuperar
        m = self.m
        no_canal = [{"id": "8Rp3WUDsBgA", "titulo": "x", "quando": "2026-10-20",
                     "privacidade": "private"},
                    {"id": "OutroPrivad", "titulo": "y", "quando": "2026-10-20",
                     "privacidade": "private"}]
        _trocar(self, recuperar, "recuperaveis",
                lambda canal, conhecidos=None, **k: list(no_canal))
        m._ledger_do_youtube = lambda canal: {}
        m.a_conferir_no_tiktok = lambda canal, plataforma="tiktok": set()
        m._publicados_do_canal = lambda canal: list(self.ledger)
        self.assertEqual(["OutroPrivad"],
                         [v["id"] for v in m.privados_no_youtube("builds")])


class FilaDasHistoriasTests(unittest.TestCase):

    def test_parte_apagada_nao_volta_a_fila(self):
        from contos.publicar import catalogo, serie
        m = _postar()
        m._linha = lambda *a, **k: None
        m._prioridades = lambda: []

        class _Parte:
            def __init__(self, parte):
                self.id = f"historia_00090:celular:p0{parte}"
                self.fonte_id, self.parte, self.perfil = "historia_00090", parte, "celular"
        partes = [_Parte(1), _Parte(2)]
        _trocar(self, catalogo, "listar", lambda *a, **k: list(partes))
        _trocar(self, serie, "publicados", lambda: [
            {"plataforma": "youtube", "video_id": partes[0].id, "parte": 1,
             "fonte_id": "historia_00090", "publicado": False,
             "estado": "apagado_do_canal", "url": ""}])
        m._criado_da_fonte = lambda f, vs: None
        fila = m.fila_de_historias()
        self.assertNotIn(partes[0].id, [v.id for v in fila])
        self.assertIn(partes[1].id, [v.id for v in fila])


class FunilDoYouTubeTests(unittest.TestCase):
    """`youtube.publicar_como_configurado`: a porta de todo upload."""

    def setUp(self):
        from builds.publicar import audio, metricas, youtube, youtube_web
        self.youtube = youtube
        self.ledger = [_apagado(v, "2026-10-19T22:50:00") for v in APAGADOS]
        _trocar(self, metricas, "publicados",
                lambda canal="builds": list(self.ledger))
        _trocar(self, audio, "barrar_luta_muda", lambda *a, **k: None)
        self.subiu = []
        _trocar(self, youtube_web, "publicar",
                lambda video, **k: self.subiu.append(video.id) or "x")

    def _publicar(self, vid):
        video = type("V", (), {"id": vid, "titulo": "t", "capa": None})()
        return self.youtube.publicar_como_configurado(
            video, config={"youtube": {"modo": "navegador"}}, canal="builds")

    def test_o_apagado_nao_sobe_por_caminho_nenhum(self):
        for vid in APAGADOS:
            with self.subTest(vid=vid):
                with self.assertRaises(self.youtube.ApagadoDoCanal):
                    self._publicar(vid)
        self.assertEqual([], self.subiu, "o Studio nem abriu")

    def test_o_pedaco_de_uma_parte_apagada_tambem_nao(self):
        self.ledger.append({"plataforma": "youtube", "publicado": False,
                            "estado": "apagado_do_canal",
                            "video_id": "historia_00090:celular:p01"})
        with self.assertRaises(self.youtube.ApagadoDoCanal):
            self._publicar("historia_00090:celular:p01:corte02")

    def test_outro_video_sobe_normal(self):
        from builds.publicar import metricas
        _trocar(self, metricas, "registrar_publicado", lambda *a, **k: None)
        self._publicar(NOVO)
        self.assertEqual([NOVO], self.subiu)

    def test_ledger_que_nao_abre_barra(self):
        from builds.publicar import metricas

        def quebrado(canal="builds"):
            raise OSError("trancado")
        _trocar(self, metricas, "publicados", quebrado)
        with self.assertRaises(self.youtube.ApagadoDoCanal):
            self._publicar(NOVO)
        self.assertEqual([], self.subiu)


if __name__ == "__main__":
    unittest.main()
