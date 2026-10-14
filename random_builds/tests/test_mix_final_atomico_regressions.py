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


def _eh_medicao(cmd) -> bool:
    # A guarda de pico verdadeiro (14/10/2026) mede o mp4 com o ebur128.
    return any("ebur128" in str(parte) for parte in cmd)


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
        if _eh_medicao(cmd):
            return SimpleNamespace(returncode=0, stderr="")
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
        if _eh_medicao(cmd):
            return SimpleNamespace(returncode=0, stderr="")
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
        if _eh_medicao(cmd):
            return SimpleNamespace(returncode=0, stderr="")
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


def _resumo_ebur128(lufs: float, tp: float) -> str:
    return ("[Parsed_ebur128_0] Summary:\n\n  Integrated loudness:\n"
            f"    I:         {lufs:.1f} LUFS\n    Threshold: -26.0 LUFS\n\n"
            f"  True peak:\n    Peak:      {tp:.1f} dBFS\n")


def test_pico_verdadeiro_acima_do_teto_refaz_sem_baixar_o_integrado(
        pasta_temporaria, monkeypatch):
    """14/10/2026: o loudnorm mira TP -1,5 mas o aac passava (-0,9 a -1,4
    dBTP no video final). A mixagem mede o mp4 e refaz com o teto mais baixo;
    se o integrado cair, a tentativa seguinte devolve a perda no alvo."""
    video = pasta_temporaria / "concat.mp4"
    destino = pasta_temporaria / "final_celular.mp4"
    video.write_bytes(b"video de entrada")
    # (lufs, tp) medido em cada tentativa, na ordem
    medidas_por_arquivo = {}
    roteiro = [(-14.0, -1.0), (-14.4, -2.0), (-14.05, -1.9)]
    comandos = []

    def ffmpeg_falso(cmd, **_kwargs):
        if _eh_medicao(cmd):
            arquivo = Path(cmd[cmd.index("-i") + 1])
            lufs, tp = medidas_por_arquivo[arquivo]
            return SimpleNamespace(returncode=0, stderr=_resumo_ebur128(lufs, tp))
        saida = Path(cmd[-1])
        comandos.append(cmd)
        saida.write_bytes(f"tentativa {len(comandos)}".encode())
        medidas_por_arquivo[saida] = roteiro[len(comandos) - 1]
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(renderer_mod.subprocess, "run", ffmpeg_falso)
    _renderer()._mix_final(video, None, None, destino)

    assert len(comandos) == 3
    filtros = [c[c.index("-filter_complex") + 1] for c in comandos]
    assert "loudnorm=I=-14.00:TP=-1.50" in filtros[0]
    assert "alimiter=limit=0.8900" in filtros[0]
    # passou 0,5 dB: o teto desce 0,5 + 0,3 de folga
    assert "TP=-2.30" in filtros[1]
    assert "loudnorm=I=-14.00" in filtros[1]
    # o integrado caiu 0,4 LU: o alvo sobe 0,4
    assert "loudnorm=I=-13.60:TP=-2.30" in filtros[2]
    assert destino.read_bytes() == b"tentativa 3"
    assert sorted(p.name for p in pasta_temporaria.iterdir()) == ["concat.mp4", "final_celular.mp4"]
