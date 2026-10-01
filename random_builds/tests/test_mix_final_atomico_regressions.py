"""Regressoes da publicacao atomica do MP4 final."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parents[1]
_NOME_MODULO = "builds.video._renderer_atomico_regressions"
sys.path.insert(0, str(RAIZ))
try:
    _SPEC = importlib.util.spec_from_file_location(
        _NOME_MODULO, RAIZ / "builds" / "video" / "renderer.py")
    assert _SPEC is not None and _SPEC.loader is not None
    renderer_mod = importlib.util.module_from_spec(_SPEC)
    sys.modules[_NOME_MODULO] = renderer_mod
    _SPEC.loader.exec_module(renderer_mod)
finally:
    sys.path.remove(str(RAIZ))
    sys.modules.pop(_NOME_MODULO, None)


def _renderer() -> renderer_mod.VideoRenderer:
    renderer = renderer_mod.VideoRenderer.__new__(renderer_mod.VideoRenderer)
    renderer.audio_cfg = {}
    return renderer


@pytest.fixture
def pasta_temporaria():
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as pasta:
        yield Path(pasta)


def test_sucesso_publica_por_troca_atomica_e_limpa_temporario(
        pasta_temporaria, monkeypatch):
    video = pasta_temporaria / "concat.mp4"
    destino = pasta_temporaria / "final_celular.mp4"
    video.write_bytes(b"video de entrada")
    destino.write_bytes(b"final antigo")
    chamada = {}

    def ffmpeg_falso(cmd, **_kwargs):
        temporario = Path(cmd[-1])
        chamada["temporario"] = temporario
        temporario.write_bytes(b"final novo")
        return SimpleNamespace(returncode=0, stderr="")

    replace_real = os.replace
    trocas = []

    def replace_registrado(origem, alvo):
        trocas.append((Path(origem), Path(alvo)))
        replace_real(origem, alvo)

    monkeypatch.setattr(renderer_mod.subprocess, "run", ffmpeg_falso)
    monkeypatch.setattr(renderer_mod.os, "replace", replace_registrado)

    _renderer()._mix_final(video, None, None, destino)

    temporario = chamada["temporario"]
    assert destino.read_bytes() == b"final novo"
    assert not temporario.exists()
    assert temporario != destino
    assert temporario.parent == destino.parent
    assert temporario.suffix == ".mp4"
    assert trocas == [(temporario, destino)]


def test_falha_publica_concat_e_remove_temporario(pasta_temporaria, monkeypatch):
    video = pasta_temporaria / "concat.mp4"
    destino = pasta_temporaria / "final_celular.mp4"
    video.write_bytes(b"video de entrada")
    destino.write_bytes(b"final antigo")
    chamada = {}

    def ffmpeg_falso(cmd, **_kwargs):
        temporario = Path(cmd[-1])
        chamada["temporario"] = temporario
        temporario.write_bytes(b"mp4 pela metade")
        return SimpleNamespace(returncode=1, stderr="falha simulada")

    replace_real = os.replace
    trocas = []

    def replace_registrado(origem, alvo):
        trocas.append((Path(origem), Path(alvo)))
        replace_real(origem, alvo)

    monkeypatch.setattr(renderer_mod.subprocess, "run", ffmpeg_falso)
    monkeypatch.setattr(renderer_mod.os, "replace", replace_registrado)

    _renderer()._mix_final(video, None, None, destino)

    temporario = chamada["temporario"]
    assert destino.read_bytes() == b"video de entrada"
    assert not temporario.exists()
    assert trocas == [(temporario, destino)]


def test_falha_sem_destino_anterior_ainda_entrega_concat(
        pasta_temporaria, monkeypatch):
    video = pasta_temporaria / "concat.mp4"
    destino = pasta_temporaria / "final_celular.mp4"
    video.write_bytes(b"video de entrada")
    chamada = {}

    def ffmpeg_falso(cmd, **_kwargs):
        temporario = Path(cmd[-1])
        chamada["temporario"] = temporario
        temporario.write_bytes(b"mp4 pela metade")
        return SimpleNamespace(returncode=1, stderr="falha simulada")

    replace_real = os.replace
    trocas = []

    def replace_registrado(origem, alvo):
        trocas.append((Path(origem), Path(alvo)))
        replace_real(origem, alvo)

    monkeypatch.setattr(renderer_mod.subprocess, "run", ffmpeg_falso)
    monkeypatch.setattr(renderer_mod.os, "replace", replace_registrado)

    _renderer()._mix_final(video, None, None, destino)

    temporario = chamada["temporario"]
    assert destino.is_file()
    assert destino.read_bytes() == b"video de entrada"
    assert not temporario.exists()
    assert trocas == [(temporario, destino)]
