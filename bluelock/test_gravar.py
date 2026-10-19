# -*- coding: utf-8 -*-
"""O gravador do Blue Lock sem navegador: o que ele recusa e o que monta.

A gravacao de verdade (Vite + Chrome + ffmpeg) e PESADA e foi provada a mao
(ver docs/sessoes/blue-lock.md, "Gravar uma partida"); aqui ficam as guardas.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from bluelock import comum, gravar


def _args(**mudar):
    base = dict(saida="x.mp4", resultado=None, espelho="E:/nao-usado", semente=42, formato=3,
                azul="isagi,bachira,nagi", vermelho="rin,barou,reo", sem_goleiros=False,
                so_basico=False, camera="bola", resolucao="1080x1920", qualidade="high", fps=30,
                segundos=5.0, pular=0.0, porta=5199, software=False, forcar=False, progresso=False)
    base.update(mudar)
    return SimpleNamespace(**base)


def test_config_padrao_e_3x3_vertical_com_tudo_ligado():
    cfg = gravar.config_da_pagina(_args())
    assert (cfg["largura"], cfg["altura"]) == (1080, 1920)
    assert cfg["azul"] == ["isagi", "bachira", "nagi"] and cfg["vermelho"] == ["rin", "barou", "reo"]
    assert cfg["goleiros"] and cfg["tudo"] and cfg["camera"] == "bola"


def test_personagem_desconhecido_e_recusado_antes_de_abrir_navegador():
    with pytest.raises(ValueError, match="desconhecido"):
        gravar.config_da_pagina(_args(azul="isagi,goku,nagi"))


def test_time_curto_para_o_formato_e_recusado():
    with pytest.raises(ValueError, match="3x3"):
        gravar.config_da_pagina(_args(vermelho="rin,barou"))
    cfg = gravar.config_da_pagina(_args(formato=1, azul="isagi", vermelho="rin"))
    assert cfg["azul"] == ["isagi"]


def test_fps_que_nao_divide_60_e_recusado():
    with pytest.raises(ValueError, match="dividir 60"):
        gravar.config_da_pagina(_args(fps=24))


def test_ffmpeg_tem_audio_mudo_e_faststart(tmp_path):
    comando = gravar.comando_ffmpeg(tmp_path / "a.mp4", 30)
    assert "anullsrc=r=44100:cl=stereo" in comando and "+faststart" in comando
    assert comando[comando.index("-framerate") + 1] == "30"
    assert "yuv420p" in comando


def test_recusa_na_janela_das_postagens_sem_forcar(monkeypatch):
    monkeypatch.setattr(comum, "pode_pesado", lambda *a, **k: (False, "janela das postagens (09:37, em 5 min)"))
    resultado = gravar.gravar(_args())
    assert resultado["sucesso"] is False and "janela das postagens" in resultado["motivo"]


def test_pode_pesado_respeita_janela_e_league():
    agora = None
    assert comum.pode_pesado(agora, league=lambda: False, janela=lambda a: (False, "")) == (True, "")
    assert comum.pode_pesado(agora, league=lambda: True, janela=lambda a: (False, ""))[0] is False
    dentro = comum.pode_pesado(agora, league=lambda: False, janela=lambda a: (True, "janela X"))
    assert dentro == (False, "janela X")


def test_janela_larga_vai_de_19_a_55_nas_postagens_de_37():
    from datetime import datetime
    assert comum.janela_das_postagens(datetime(2026, 10, 19, 9, 18))[0] is False
    assert comum.janela_das_postagens(datetime(2026, 10, 19, 9, 19))[0] is True
    assert comum.janela_das_postagens(datetime(2026, 10, 19, 9, 54))[0] is True
    assert comum.janela_das_postagens(datetime(2026, 10, 19, 9, 55))[0] is False


def test_league_aberto_le_o_tasklist():
    class Saida:
        returncode = 0

        def __init__(self, texto):
            self.stdout = texto.encode("ascii")
    assert comum.league_aberto(lambda *a, **k: Saida('"League of Legends.exe","123","Console"')) is True
    assert comum.league_aberto(lambda *a, **k: Saida("INFO: No tasks are running")) is False

    def quebra(*a, **k):
        raise OSError("sem tasklist")
    assert comum.league_aberto(quebra) is True          # na duvida, nao atrapalha o jogo
