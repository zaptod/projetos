# -*- coding: utf-8 -*-
"""Luta muda debaixo de musica nao sai.

MEDIDO PELA PARTE BUILDS EM 28/09/2026: 38 de 129 publicacoes desde 15/09
sairam com a luta calada, inclusive a `generation_00083:build:celular:B` das
00:45 — o `seg_021` (a luta) a -91 dB. A guarda antiga (`postar._audio_mudo`)
media o arquivo INTEIRO, e a musica de fundo cobria o buraco: media acima de
-60 dB, pouco silencio, "tem som".

Conferido nesta maquina antes de escrever (28/09, 00:59): das 22 candidatas
da fila, 21 tinham luta entre -12,8 e -21 dB; a estreia da generation_00066
tinha os dois trechos de luta a -91 dB (a guarda antiga ja a barrava, por
estar calada em 95% do arquivo). A `generation_00083:build:celular:B`, a que
saiu as 00:45, mede -91 dB no `seg_021`.

Os mp4 aqui sao de verdade (ffmpeg), como no teste da guarda antiga: a
pergunta e sobre som, e um duble de som responderia o que o teste quisesse.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from builds.publicar import audio, desfecho

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_luta", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


def _mp4(destino: Path, som: str, segundos: int = 2) -> Path:
    """`som`: "musica" (seno), "mudo" (anullsrc, -91 dB)."""
    fonte = ("sine=frequency=440:duration=%d" % segundos if som == "musica"
             else "anullsrc=r=44100:cl=mono")
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"color=c=black:s=64x64:d={segundos}", "-f", "lavfi",
                    "-i", fonte, "-t", str(segundos), "-shortest",
                    str(destino)], check=True)
    return destino


class _Video:
    def __init__(self, caminho, vid="generation_00083:build:celular:B"):
        self.id, self.caminho, self.perfil = vid, str(caminho), "celular"
        self.titulo, self.descricao_completa = "T", "D"
        self.vertical, self.capa = True, None
        self.pendencias, self.origem, self.quando = None, "build", 0.0


def _build(pasta: Path, *, luta: str, com_trecho=True) -> _Video:
    """Um build de mentira com a forma do real: final mixado com musica e o
    trecho da luta (`seg_001`) separado em `_segments_celular/`."""
    final = _mp4(pasta / "final_celular.mp4", "musica")
    (pasta / "edit_plan.json").write_text(json.dumps({"events": [
        {"type": "roulette", "start": 0, "duration": 1},
        {"type": "gameplay", "start": 1, "duration": 1},
        {"type": "outro", "start": 2, "duration": 0.5}]}), encoding="utf-8")
    if com_trecho:
        _mp4(pasta / "_segments_celular" / "seg_001.mp4", luta)
    return _Video(final)


class _Isolado(unittest.TestCase):
    """Pasta descartavel e a lembranca da medida fora do runtime de verdade."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        _trocar(self, audio, "_arquivo_lembrado",
                lambda: self.pasta / "audio_medido.json")
        _trocar(self, audio, "_LEMBRADO", {})


@unittest.skipUnless(shutil.which("ffmpeg"), "precisa do ffmpeg")
class LutaMudaTests(_Isolado):
    def test_caso_zero_musica_ok_e_luta_a_91db_e_barrado(self):
        video = _build(self.pasta, luta="mudo")
        self.assertEqual("", audio.medir(Path(video.caminho)),
                         "o arquivo inteiro TEM som: era por aqui que passava")
        motivo = audio.luta_muda(video)
        self.assertTrue(motivo.startswith(audio.MARCA_DA_LUTA), motivo)
        self.assertIn("seg_001", motivo)
        self.assertIn("-91", motivo)
        self.assertEqual(motivo, _postar()._audio_mudo(video),
                         "a fila da grade tem de barrar o mesmo video")

    def test_luta_com_som_passa(self):
        video = _build(self.pasta, luta="musica")
        self.assertEqual("", audio.luta_muda(video))
        self.assertEqual("", audio.veredito(video))
        self.assertEqual("", _postar()._audio_mudo(video))

    def test_sem_plano_nao_ha_luta_a_medir(self):
        final = _mp4(self.pasta / "final_celular.mp4", "musica")
        self.assertEqual("", audio.luta_muda(_Video(final)))

    def test_trecho_apagado_e_nao_sei_e_nao_barra(self):
        video = _build(self.pasta, luta="mudo", com_trecho=False)
        self.assertIsNone(audio.luta_muda(video))
        self.assertIsNone(audio.veredito(video),
                          "'nao sei' nao pode soltar marca")
        self.assertEqual("", _postar()._audio_mudo(video),
                         "'nao sei' nunca barra video na grade")


@unittest.skipUnless(shutil.which("ffmpeg"), "precisa do ffmpeg")
class AGuardaEstaNoFunilTests(_Isolado):
    """Os caminhos que nunca mediram audio — recuperacao, reserva, `main.py
    publicar`, bot, app — passam pelos dois publicadores. A guarda mora la,
    ANTES de abrir o navegador, e o motivo vai para a lista "a conferir"."""

    def setUp(self):
        super().setUp()
        self.video = _build(self.pasta, luta="mudo")
        self.marcas = []
        _trocar(self, desfecho, "marcar_para_conferir",
                lambda canal, vid, estado, plataforma="tiktok", **k:
                self.marcas.append((canal, vid, plataforma, estado, k)) or True)

    def test_tiktok_nao_abre_o_chrome(self):
        from builds.publicar import tiktok

        def nao_abra(*_a, **_k):
            raise AssertionError("abriu o Chrome com a luta muda")
        _trocar(self, tiktok, "contexto_persistente", nao_abra)
        with self.assertRaises(audio.LutaMuda):
            tiktok.publicar(self.video, postar=True, canal="builds",
                            config={"tiktok": {}})
        self.assertEqual([("builds", self.video.id, "tiktok")],
                         [m[:3] for m in self.marcas])
        estado, extra = self.marcas[0][3], self.marcas[0][4]
        self.assertTrue(estado.startswith(audio.PREFIXO_DA_MARCA + audio.MARCA_DA_LUTA))
        self.assertFalse(extra.get("erro", True),
                         "guarda funcionando nao e falha: nao aciona a apuracao")

    def test_youtube_nao_abre_o_studio(self):
        from builds.publicar import youtube, youtube_web

        def nao_suba(*_a, **_k):
            raise AssertionError("subiu ao YouTube com a luta muda")
        _trocar(self, youtube_web, "publicar", nao_suba)
        with self.assertRaises(audio.LutaMuda):
            youtube.publicar_como_configurado(
                self.video, canal="builds", visibilidade="public",
                config={"youtube": {"modo": "navegador"}})
        self.assertEqual([("builds", self.video.id, "youtube")],
                         [m[:3] for m in self.marcas])

    def test_luta_com_som_segue_para_o_publicador(self):
        from builds.publicar import youtube, youtube_web
        video = _build(self.pasta / "outro", luta="musica")
        subiu = []
        _trocar(self, youtube_web, "publicar",
                lambda *a, **k: subiu.append(a) or "nao confirmou")
        youtube.publicar_como_configurado(
            video, canal="builds", visibilidade="public",
            config={"youtube": {"modo": "navegador"}})
        self.assertEqual(1, len(subiu))
        self.assertEqual([], self.marcas)


class _Fila(unittest.TestCase):
    """`proximo_build` de verdade, com catalogo, ledger e lista dublados."""

    MOTIVO = f"{audio.MARCA_DA_LUTA} (seg_021: o audio esta mudo (media -91.0 dB))"

    def setUp(self):
        from builds.publicar import catalogo, metricas
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.m.repetir_titulo = lambda *_a, **_k: False
        self.m._servidos_recentes = lambda n=16: {}
        self.m.cota_da_grade = lambda config=None: {}
        self.m.a_conferir_no_tiktok = lambda canal="historias", plataforma="tiktok": set()
        self.video = _Video(Path("x.mp4"), vid="g1:build:celular")
        _trocar(self, catalogo, "listar", lambda *a, **k: [self.video])
        _trocar(self, metricas, "publicados", lambda *a, **k: [])
        self.marcas, self.revistas = [], []
        _trocar(self, audio, "marcar", lambda *a, **k: self.marcas.append(a))
        _trocar(self, audio, "revisar_marcas",
                lambda canal, videos, **k: self.revistas.append(
                    [v.id for v in videos]) or [])


class AFilaMarcaSoQuandoPublicaTests(_Fila):
    """A fila da grade pula o video mudo; so a rodada de VERDADE o poe na
    lista "a conferir" e revisa as marcas — `--ver` e o painel perguntam,
    nao mexem."""

    def test_rodada_de_verdade_marca_no_youtube(self):
        self.m._audio_mudo = lambda v: self.MOTIVO
        self.assertIsNone(self.m.proximo_build(marcar=True))
        self.assertEqual([("builds", "g1:build:celular", self.MOTIVO, "youtube")],
                         self.marcas)
        self.assertEqual([["g1:build:celular"]], self.revistas)

    def test_so_ver_nao_marca_nem_revisa(self):
        self.m._audio_mudo = lambda v: self.MOTIVO
        self.assertIsNone(self.m.proximo_build())
        self.assertEqual([], self.marcas)
        self.assertEqual([], self.revistas)

    def test_com_som_sai_e_nao_marca(self):
        self.m._audio_mudo = lambda v: ""
        self.assertEqual("g1:build:celular", self.m.proximo_build(marcar=True).id)
        self.assertEqual([], self.marcas)

    def test_a_rodada_pede_para_marcar(self):
        """`postar_build` e quem publica: tem de chamar com `marcar`."""
        import inspect
        fonte = inspect.getsource(self.m.postar_build)
        self.assertIn("proximo_build(marcar=not so_ver)", fonte)


class _ListaNoDisco(unittest.TestCase):
    """A lista "a conferir" de verdade (`desfecho`), numa pasta descartavel."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        pasta = Path(self._tmp.name)
        _trocar(self, desfecho, "arquivo_a_conferir",
                lambda canal, plataforma="tiktok":
                pasta / f"_{plataforma}_a_conferir.json")
        self.diario = []
        _trocar(self, desfecho, "_avisar",
                lambda canal, texto, ref="", atividade_erro=True, etapa=None:
                self.diario.append((texto, atividade_erro, etapa)))
        # O diario de verdade nunca: `unittest` avulso nao isola o runtime.
        _trocar(self, audio, "_diario", lambda *a, **k: None)

    def _lista(self, plataforma="youtube") -> dict:
        caminho = desfecho.arquivo_a_conferir("builds", plataforma)
        return json.loads(caminho.read_text(encoding="utf-8")) if caminho.is_file() else {}


class MarcaDeAudioTests(_ListaNoDisco):
    def test_a_marca_de_audio_leva_o_prefixo_e_nao_e_erro(self):
        audio.marcar("builds", "g1:build:celular", "a luta esta muda (x)", "youtube")
        marca = self._lista()["g1:build:celular"]
        self.assertTrue(marca["estado"].startswith(audio.PREFIXO_DA_MARCA))
        self.assertEqual(1, len(self.diario))
        texto, erro, etapa = self.diario[0]
        self.assertFalse(erro)
        self.assertEqual("publicar.audio", etapa)
        self.assertNotIn("cliquei", texto, "o aviso de clique sem confirmacao "
                                           "diria 'pode estar no ar' — falso")

    def test_soltar_so_tira_marca_com_o_prefixo(self):
        desfecho.marcar_para_conferir("builds", "clique", "cliquei em publicar, "
                                      "mas o Studio nao mostrou", "youtube")
        audio.marcar("builds", "som", "a luta esta muda (x)", "youtube")
        prefixo = audio.PREFIXO_DA_MARCA
        self.assertFalse(desfecho.soltar_marca("builds", "clique", "youtube",
                                               prefixo=prefixo),
                         "clique sem confirmacao so sai por conferencia humana")
        self.assertFalse(desfecho.soltar_marca("builds", "som", "youtube",
                                               prefixo=""),
                         "prefixo vazio casaria com toda marca")
        self.assertTrue(desfecho.soltar_marca("builds", "som", "youtube",
                                              prefixo=prefixo))
        self.assertEqual({"clique"}, set(self._lista()))

    def test_revisar_solta_quem_voltou_a_ter_som_e_so_ele(self):
        for vid in ("voltou", "ainda_mudo", "nao_sei"):
            audio.marcar("builds", vid, "a luta esta muda (x)", "youtube")
        desfecho.marcar_para_conferir("builds", "clique", "cliquei em publicar",
                                      "youtube")
        julgamento = {"voltou": "", "ainda_mudo": "a luta esta muda (y)",
                      "nao_sei": None, "clique": ""}
        videos = [_Video(Path("x.mp4"), vid=v) for v in julgamento]
        soltos = audio.revisar_marcas("builds", videos,
                                      julgar=lambda v: julgamento[v.id],
                                      plataformas=("youtube",))
        self.assertEqual([("voltou", "youtube")], soltos)
        self.assertEqual({"ainda_mudo", "nao_sei", "clique"}, set(self._lista()))

    def test_lista_ilegivel_nao_solta_nada(self):
        caminho = desfecho.arquivo_a_conferir("builds", "youtube")
        caminho.write_text("{corrompido", encoding="utf-8")
        self.assertEqual([], audio.revisar_marcas(
            "builds", [_Video(Path("x.mp4"), vid="v")], julgar=lambda v: ""))
        self.assertEqual("{corrompido", caminho.read_text(encoding="utf-8"),
                         "arquivo ilegivel fica onde esta")


class MedidaLembradaTests(_Isolado):
    """A lembranca e por ARQUIVO e por CRITERIO, entre processos, e so guarda
    medida de verdade."""

    def setUp(self):
        super().setUp()
        self.mp4 = self.pasta / "v.mp4"
        self.mp4.write_bytes(b"x")

    def test_mede_uma_vez_e_vale_entre_processos(self):
        medidas = []
        medir = lambda c: medidas.append(c) or "calado"      # noqa: E731
        self.assertEqual("calado", audio.medir_lembrado(self.mp4, medir=medir))
        self.assertEqual("calado", audio.medir_lembrado(self.mp4, medir=medir))
        audio._LEMBRADO.clear()                   # "outro processo"
        self.assertEqual("calado", audio.medir_lembrado(self.mp4, medir=medir))
        self.assertEqual(1, len(medidas))

    def test_falha_da_ferramenta_nao_e_lembrada(self):
        respostas = [None, "calado"]
        medir = lambda c: respostas.pop(0)                    # noqa: E731
        self.assertIsNone(audio.medir_lembrado(self.mp4, medir=medir))
        self.assertEqual("calado", audio.medir_lembrado(self.mp4, medir=medir),
                         "a proxima pergunta mede de novo")

    def test_arquivo_trocado_e_medido_de_novo(self):
        import os
        medidas = []
        medir = lambda c: medidas.append(c) or ""             # noqa: E731
        audio.medir_lembrado(self.mp4, medir=medir)
        self.mp4.write_bytes(b"re-render maior")
        os.utime(self.mp4, ns=(1, 1))
        audio.medir_lembrado(self.mp4, medir=medir)
        self.assertEqual(2, len(medidas))

    def test_criterio_novo_mede_de_novo(self):
        medidas = []
        medir = lambda c: medidas.append(c) or ""             # noqa: E731
        audio.medir_lembrado(self.mp4, medir=medir)
        _trocar(self, audio, "LIMIAR_MUDO_DB", -55.0)
        audio.medir_lembrado(self.mp4, medir=medir)
        self.assertEqual(2, len(medidas))


if __name__ == "__main__":
    unittest.main()
