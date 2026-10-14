# -*- coding: utf-8 -*-
"""Metade B do motor (auditoria profunda de 11/10/2026): gravacao, CLI e
ferramentas.

MOT-109 (ffmpeg falha e o gravador diz sucesso), MOT-110 (skill_demo destroi
a demo boa), MOT-111/112 (Atelie com NaN e ajuste malformado), MOT-121
(fps que nao divide 60), MOT-122 (CLIs aceitam argumento invalido), MOT-123
(exit 0 sem a timeline pedida), MOT-127 (OAuth recusado espera para sempre)
e MOT-128 (temporario com nome fixo).
"""
from __future__ import annotations

import io
import json
import socket
import threading
import urllib.request
from pathlib import Path

import pytest

from neural_fights.recording import fight_recorder, skill_demo, timeline_arquivo


# ------------------------------------------------------------------ ffmpeg
class _PopenFalso:
    """Imita o Popen do ffmpeg: aceita os quadros e sai com ``codigo``."""

    def __init__(self, codigo=1, stderr=b"Error writing trailer: Permission denied"):
        self.stdin = io.BytesIO()
        self._codigo = codigo
        self.arquivo_de_erros = io.BytesIO(stderr)
        self.mortos = 0

    def wait(self, timeout=None):
        return self._codigo

    def kill(self):
        self.mortos += 1


def _dois_nomes():
    from neural_fights.data import database

    nomes = [p.nome for p in database.carregar_personagens()][:2]
    if len(nomes) < 2:
        pytest.skip("roster insuficiente")
    return nomes


def test_ffmpeg_que_falha_no_trailer_nao_e_sucesso(tmp_path, monkeypatch):
    p1, p2 = _dois_nomes()
    monkeypatch.setattr(fight_recorder, "_abrir_ffmpeg", lambda *a, **k: _PopenFalso())
    resultado = fight_recorder.gravar_luta(
        p1=p1, p2=p2, saida=tmp_path / "x.mp4", max_duracao=0.5, anotar_som=False,
    )
    assert resultado["sucesso"] is False
    assert "trailer" in resultado["erro"]


def test_ffmpeg_com_codigo_zero_e_sem_arquivo_nao_e_sucesso(tmp_path, monkeypatch):
    p1, p2 = _dois_nomes()
    monkeypatch.setattr(fight_recorder, "_abrir_ffmpeg", lambda *a, **k: _PopenFalso(0, b""))
    resultado = fight_recorder.gravar_luta(
        p1=p1, p2=p2, saida=tmp_path / "x.mp4", max_duracao=0.5, anotar_som=False,
    )
    assert resultado["sucesso"] is False
    assert "nao existe" in resultado["erro"]


def test_pipe_quebrado_diz_o_motivo_do_ffmpeg():
    class Quebrado(_PopenFalso):
        class _Stdin:
            def write(self, _dados):
                raise BrokenPipeError(32, "pipe")

            def close(self):
                pass

        def __init__(self):
            super().__init__(1, b"Unknown encoder 'nao_existe'")
            self.stdin = self._Stdin()

    with pytest.raises(RuntimeError, match="nao_existe"):
        fight_recorder._escrever_quadro(Quebrado(), b"x")


# --------------------------------------------------------- fps e duracao
@pytest.mark.parametrize("fps", [-30, 0, 24, 25, 50, 120])
def test_fps_que_nao_divide_60_e_recusado(fps):
    with pytest.raises(ValueError):
        fight_recorder.gravar_luta(p1="a", p2="b", saida=None, fps_saida=fps)


def test_duracao_zero_e_recusada():
    with pytest.raises(ValueError):
        fight_recorder.gravar_luta(p1="a", p2="b", saida=None, max_duracao=0)


def test_timeline_recusa_fps_invalido():
    from neural_fights.recording.timeline import gravar_timeline

    with pytest.raises(ValueError):
        gravar_timeline(p1="a", p2="b", fps_video=24)


@pytest.mark.parametrize("argv", [
    ["--fps", "-30"], ["--fps", "24"], ["--max-duracao", "0"], ["--resolucao", "1080"],
])
def test_cli_do_gravador_recusa_argumento_invalido(argv):
    with pytest.raises(SystemExit) as saida:
        fight_recorder.main(["--p1", "a", "--p2", "b", "--sem-video", *argv])
    assert saida.value.code == 2


def test_timeline_que_falha_da_exit_3(monkeypatch, capsys):
    monkeypatch.setattr(fight_recorder, "gravar_luta", lambda **k: {
        "sucesso": True, "timeline": None, "erro_timeline": "OSError: Z: nao existe",
    })
    codigo = fight_recorder.main([
        "--p1", "a", "--p2", "b", "--sem-video", "--timeline", r"Z:\nao_existe\x.gcpf",
        "--max-duracao", "0.5",
    ])
    assert codigo == 3


def test_som_pedido_que_nao_entrou_da_exit_3(monkeypatch, tmp_path):
    monkeypatch.setattr(fight_recorder, "gravar_luta", lambda **k: {
        "sucesso": True, "som_no_video": False, "erro_som": "numpy ausente",
    })
    assert fight_recorder.main(["--p1", "a", "--p2", "b", "--saida", str(tmp_path / "x.mp4")]) == 3
    monkeypatch.setattr(fight_recorder, "gravar_luta", lambda **k: {"sucesso": True})
    assert fight_recorder.main(["--p1", "a", "--p2", "b", "--sem-video"]) == 0


# --------------------------------------------------------------- CLIs
def test_cli_live_recusa_roster_menor_que_dois():
    from neural_fights.cli import live

    for valor in ("1", "-1", "0"):
        with pytest.raises(SystemExit):
            live.build_parser().parse_args(["--roster", valor])
    with pytest.raises(SystemExit):
        live.build_parser().parse_args(["--max-partidas", "0"])
    assert live.build_parser().parse_args(["--roster", "2"]).roster == 2


def test_cli_live_corte_com_um_lutador_e_erro(monkeypatch):
    from types import SimpleNamespace

    from neural_fights.cli import live

    monkeypatch.setattr(
        live.database, "carregar_personagens",
        lambda: [SimpleNamespace(nome="A"), SimpleNamespace(nome="B"), SimpleNamespace(nome="C")],
    )
    assert live._roster(2) == ["A", "B"]
    with pytest.raises(RuntimeError):
        live._roster(1)


def test_cli_timeline_recusa_camera_e_resolucao_invalidas():
    from neural_fights.recording import timeline

    with pytest.raises(SystemExit):
        timeline.build_parser().parse_args(["--p1", "a", "--p2", "b", "--saida", "x", "--camera", "foo"])
    with pytest.raises(SystemExit):
        timeline.main(["--p1", "a", "--p2", "b", "--saida", "x", "--resolucao", "1080"])


def test_skill_desconhecida_nao_vira_sentinela():
    resultado = skill_demo.gravar_demo("Nao Existe", sem_video=True)
    assert resultado["erro"] == "skill desconhecida"


# ----------------------------------------------------------- skill_demo
def test_demo_anterior_sobrevive_a_cast_recusado(tmp_path, monkeypatch):
    from neural_fights.core import entities

    destino = tmp_path / "bola.mp4"
    destino.write_bytes(b"demo-anterior-boa")
    monkeypatch.setattr(fight_recorder, "_abrir_ffmpeg", lambda *a, **k: _PopenFalso(0, b""))
    monkeypatch.setattr(entities.Lutador, "usar_skill_classe", lambda self, *a, **k: False)
    resultado = skill_demo.gravar_demo("Bola de Fogo", saida=destino)
    assert resultado["ok"] is False
    assert destino.read_bytes() == b"demo-anterior-boa"
    assert not list(tmp_path.glob("*.tmp.mp4"))


# ---------------------------------------------------------------- Atelie
def _contrato(**extra):
    base = {"quadros": [{"x": 0, "y": 0, "w": 1, "h": 1}], "fps": 12, "ancora": {"x": 0, "y": 0}}
    base.update(extra)
    return base


@pytest.mark.parametrize("extra", [
    {"fps": "nan"}, {"fps": "inf"}, {"escala": "inf"}, {"rotacao": float("nan")},
    {"ancora": {"x": float("nan"), "y": 0}}, {"duracao_por_quadro": {"0": "nan"}},
])
def test_atelie_recusa_nan_e_infinito(extra):
    from neural_fights.tools import atelie_animacoes as atelie

    with pytest.raises(ValueError):
        atelie.validar(_contrato(**extra), (1, 1))


def test_atelie_ajuste_malformado(tmp_path, monkeypatch):
    from neural_fights.tools import atelie_animacoes as atelie

    monkeypatch.setattr(atelie, "AJUSTES", tmp_path / "ajustes.json")
    with pytest.raises(ValueError):
        atelie.salvar_ajustes({"novas": ["x"], "escondidas": []})
    with pytest.raises(ValueError):
        atelie.salvar_ajustes({"novas": [], "escondidas": [3]})
    (tmp_path / "ajustes.json").write_text(json.dumps({"novas": ["x", {"a": 1}], "escondidas": [3, "p/e/a"]}))
    dados = atelie.ajustes()
    assert dados == {"novas": [], "escondidas": ["p/e/a"]}
    atelie.arvore()  # nao levanta


# ----------------------------------------------------------------- OAuth
def test_oauth_recusado_encerra():
    from neural_fights.tools import youtube_oauth

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    erros = []

    def rodar():
        try:
            youtube_oauth._receber_codigo(porta)
        except RuntimeError as erro:
            erros.append(str(erro))

    thread = threading.Thread(target=rodar, daemon=True)
    thread.start()
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{porta}/?error=access_denied", timeout=2).read()
            break
        except OSError:
            threading.Event().wait(0.05)
    thread.join(5)
    assert not thread.is_alive()
    assert erros and "access_denied" in erros[0]


# ------------------------------------------------------------- timeline
def test_salvar_timeline_nao_usa_tmp_fixo(tmp_path, monkeypatch):
    nomes = []
    original = Path.write_bytes

    def espiar(self, dados):
        nomes.append(self.name)
        return original(self, dados)

    monkeypatch.setattr(Path, "write_bytes", espiar)
    destino = tmp_path / "t.json"
    timeline_arquivo.salvar({"a": 1}, destino)
    timeline_arquivo.salvar({"a": 2}, destino)
    assert len(nomes) == 2 and nomes[0] != nomes[1]
    assert all(n.endswith(".tmp") and n != "t.json.tmp" for n in nomes)
    assert not list(tmp_path.glob("*.tmp"))
