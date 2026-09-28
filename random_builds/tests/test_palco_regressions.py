# -*- coding: utf-8 -*-
"""Onda 16D: o palco (Godot) que desenha a luta a partir da timeline.

Sem Godot na maquina, o que precisa dele e PULADO com o motivo (o resto roda
em qualquer lugar). Com Godot:
  - os testes do nucleo em GDScript (plano de quadros, descoberta por nome
    com reserva, validacao) rodam headless;
  - a validacao headless aceita timeline boa e recusa ruim;
  - as duas guardas do Movie Maker saem com o codigo certo (rc 3 sem
    --fixed-fps, rc 4 com a janela minimizada), nunca com rc 0 calado;
  - um render de 2 s e conferido com ffprobe e ebur128, e a janela do Godot
    nunca fica com o foco.
Render so fora de :25-:55 (a janela das postagens da grade): dentro dela, pula.
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from builds.palco import checagens, config, godot, plano, render, sintetica, sons
from builds.palco.config import ErroPalco

GODOT = config.godot_disponivel()
precisa_godot = pytest.mark.skipif(GODOT is None, reason="Godot nao encontrado (config/palco.json ou NF_GODOT)")
TEM_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _na_janela_da_grade() -> bool:
    return 25 <= time.localtime().tm_min < 55


pode_renderizar = pytest.mark.skipif(
    _na_janela_da_grade(), reason="render so fora de :25-:55 (janela das postagens da grade)")


@pytest.fixture
def pasta_e(tmp_path):
    """Pasta de trabalho no E: quando houver (o C: esta quase cheio)."""
    base = Path("E:/projetos/palco/_saida/_testes") if Path("E:/").exists() else tmp_path
    pasta = base / f"t{os.getpid()}_{time.time_ns()}"
    pasta.mkdir(parents=True, exist_ok=True)
    yield pasta
    shutil.rmtree(pasta, ignore_errors=True)


# ------------------------------------------------------------ sem Godot
def test_plano_de_quadros_bate_com_o_do_duelo_publicado():
    # duelo_00016: 1456 passos, corte [[0, 2,43], [3,47, 20,8]] = 23,23 s de clipe
    assert plano.quadros(1456 / 60, None) == 728
    assert plano.quadros(1456 / 60, {"trechos": [[0.0, 2.43], [3.47, 20.8]]}) == 73 + 624
    assert plano.mapear(3.0, 1456 / 60, [[0.0, 2.43], [3.47, 20.8]]) == -1
    assert plano.mapear(3.47, 1456 / 60, [[0.0, 2.43], [3.47, 20.8]]) == 73
    assert plano.quadros(2.0, [[0, 1, 1], [1, 1, 0.5]]) == 90


def test_arredondamento_e_o_do_gdscript_nao_o_bancario():
    assert plano.arredondar(2.5) == 3 and round(2.5) == 2
    assert plano.arredondar(72.9) == 73


def test_hitstop_do_render_ligado_pela_decisao_do_adrian():
    # Grimorio `hitstop` = ligar (28/09/2026): o estilo GLOBAL tem pausa nos
    # golpes que contam e nenhuma no leve (Onda 10: pausa em todo golpe
    # quebrava o fluxo)
    seg = plano.hitstop_do_estilo(config.projeto())
    assert seg["light"] == 0.0
    assert 0.0 < seg["medium"] <= seg["heavy"] <= seg["colossal"] <= 0.2
    assert seg["dano_min"] > 0.0
    # o job ainda sobrepoe campo a campo (e o "desligado" de um render so)
    zero = plano.hitstop_do_estilo(config.projeto(), {"hitstop_medio": 0, "hitstop_pesado": 0,
                                                       "hitstop_colossal": 0})
    assert zero["medium"] == zero["heavy"] == zero["colossal"] == 0.0


def test_hitstop_em_python_conta_como_o_plano_do_godot():
    seg = {"light": 0.0, "medium": 0.03, "heavy": 0.07, "colossal": 0.13, "dano_min": 0.03}
    doc = {"hz": 60, "n": 600, "eventos": [
        {"i": 60, "tipo": "acerto", "tier": "heavy", "dano_pct": 0.05},      # 2 quadros
        {"i": 60, "tipo": "acerto", "tier": "colossal", "dano_pct": 0.2},    # mesmo quadro: o maior, 4
        {"i": 120, "tipo": "acerto", "tier": "colossal", "dano_pct": 0.01},  # raspao: nao para
        {"i": 180, "tipo": "acerto", "tier": "light", "dano_pct": 0.5},      # leve: 0 s
        {"i": 240, "tipo": "acerto", "tier": "medium", "dano_pct": 0.1},     # 1 quadro
        {"i": 330, "tipo": "acerto", "tier": "colossal", "dano_pct": 0.3},   # 4, ou nada no corte
        {"i": 240, "tipo": "dano", "tier": "colossal", "dano_pct": 0.3},     # so acerto conta
    ]}
    assert plano.quadros_de_hitstop(doc, seg) == 4 + 1 + 4
    assert plano.quadros_de_hitstop(doc, seg, [[0.0, 5.0], [6.0, 4.0]]) == 5
    assert plano.quadros_de_hitstop(doc, seg, [[0.0, 5.0], [5.2, 4.0]]) == 5 + 4


def test_timeline_sintetica_segue_o_schema_da_16c():
    doc = sintetica.timeline_sintetica(2.0)
    assert doc["n"] == 120 and doc["formato"] == "neural-fights/timeline"
    timeline_arquivo = pytest.importorskip("neural_fights.recording.timeline_arquivo")
    assert timeline_arquivo.validar(doc) == []


def test_sons_de_reserva_seguem_o_formato_da_16a_e_sao_deterministicos():
    doc = sintetica.timeline_sintetica(2.0)
    a = sons.sons_dos_eventos(doc)
    assert a == sons.sons_dos_eventos(doc)
    tempos = [s["t"] for s in a]
    assert tempos == sorted(tempos)
    for s in a:
        assert abs(s["t"] * 30 - round(s["t"] * 30)) < 1e-6        # quantizado ao quadro
        assert 0.0 <= s["volume"] <= 1.0 and s["pitch"] > 0
    assert len({s["id"] for s in a}) >= 6


def test_arquivos_de_som_pela_cadeia_do_jogo():
    mapa = sons.arquivos_de_som(["slash_heavy", "impact_flesh", "nao_existe_mesmo"])
    assert "nao_existe_mesmo" not in mapa
    assert Path(mapa["slash_heavy"]).is_file()
    # impact_flesh nao tem arquivo: cai no fallback do jogo (wall_impact_light)
    assert Path(mapa["impact_flesh"]).stem == "wall_impact_light"


def test_godot_vem_do_config_ou_da_variavel_nunca_do_codigo(monkeypatch, tmp_path):
    falso = tmp_path / "godot_falso.exe"
    falso.write_bytes(b"")
    monkeypatch.setenv(config.VARIAVEL_GODOT, str(falso))
    assert config.godot() == falso
    monkeypatch.setenv(config.VARIAVEL_GODOT, str(tmp_path / "sumiu.exe"))
    with pytest.raises(ErroPalco, match="nao encontrado"):
        config.godot()
    fonte = (Path(config.__file__).parent).glob("*.py")
    for arquivo in fonte:
        assert "Godot_v4" not in arquivo.read_text(encoding="utf-8"), arquivo


@pytest.mark.skipif(not TEM_FFMPEG, reason="sem ffmpeg/ffprobe")
def test_conferencia_acusa_video_mudo_e_quadros_errados(tmp_path):
    mudo = tmp_path / "mudo.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=2",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "2", "-c:v", "libx264",
                    "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(mudo)], check=True)
    problemas, medidas = checagens.conferir(mudo, quadros=61, fps=30, largura=1080, altura=1920,
                                            piso_lufs=-40.0, piso_media_db=-45.0)
    texto = " | ".join(problemas)
    assert "luta muda" in texto
    assert "60 quadros no mp4, o plano pede 61" in texto
    assert checagens.energia_ativa_db(checagens.audio_mono(mudo)) is None


# ------------------------------------------------------------ com Godot
@precisa_godot
def test_nucleo_do_palco_em_gdscript():
    rc, saida = godot.rodar_script("res://ferramentas/testes.gd")
    assert rc == 0, saida[-2000:]
    assert "0 falha(s)" in saida


@precisa_godot
def test_validacao_headless_aceita_boa_e_recusa_ruim(pasta_e):
    boa = pasta_e / "boa.json"
    boa.write_text(json.dumps(sintetica.timeline_sintetica(1.0)), encoding="utf-8")
    ruim_doc = sintetica.timeline_sintetica(1.0)
    ruim_doc["trilhas"]["lutadores"]["p2"]["x"].pop()
    ruim_doc["eventos"].append({"i": 10_000, "t": 999.0, "tipo": "acerto"})
    ruim = pasta_e / "ruim.json"
    ruim.write_text(json.dumps(ruim_doc), encoding="utf-8")
    rc, saida = godot.rodar_script("res://ferramentas/validar.gd", [f"--timeline={boa}"])
    assert rc == 0, saida[-1500:]
    rc, saida = godot.rodar_script("res://ferramentas/validar.gd", [f"--timeline={ruim}"])
    assert rc == 1
    assert "trilhas.lutadores.p2.x tem 59 amostras" in saida
    assert "fora de [0, 60)" in saida
    rc, _ = godot.rodar_script("res://ferramentas/validar.gd", [f"--timeline={pasta_e / 'nao_existe.json'}"])
    assert rc == 2


@precisa_godot
def test_hitstop_do_godot_bate_com_a_conta_em_python(pasta_e):
    doc = sintetica.timeline_sintetica(3.0)
    arquivo = pasta_e / "t.json"
    arquivo.write_text(json.dumps(doc), encoding="utf-8")
    rc, saida = godot.rodar_script("res://ferramentas/validar.gd",
                                   [f"--timeline={arquivo}", f"--saida={pasta_e / 'v.json'}"])
    assert rc == 0, saida[-1500:]
    rel = json.loads((pasta_e / "v.json").read_text(encoding="utf-8"))
    esperado = plano.quadros_de_hitstop(doc, plano.hitstop_do_estilo(config.projeto()))
    assert esperado > 0, "a sintetica tem acertos pesados de 5%: o hitstop ligado tem de parar"
    assert rel["quadros_de_hitstop"] == esperado
    assert rel["quadros"] == plano.quadros(3.0) + esperado


def _job(pasta: Path, segundos: float = 1.0) -> Path:
    tl = pasta / "t.json"
    tl.write_text(json.dumps(sintetica.timeline_sintetica(segundos)), encoding="utf-8")
    job = pasta / "job.json"
    job.write_text(json.dumps({"timeline": str(tl), "relatorio": str(pasta / "rel.json")}), encoding="utf-8")
    return job


@precisa_godot
@pode_renderizar
def test_guarda_sem_fixed_fps_sai_com_rc_3(pasta_e):
    cfg = config.carregar()
    godot.garantir_importado(cfg)
    comando = [config.godot(cfg), "--path", config.projeto(cfg), "--position", "1070,200",
               "--write-movie", pasta_e / "x.avi", "--", f"--job={_job(pasta_e)}"]
    rc, saida = godot._rodar(comando, timeout=120, cfg=cfg)
    assert rc == 3, saida[-1500:]
    assert json.loads((pasta_e / "rel.json").read_text(encoding="utf-8"))["ok"] is False


@precisa_godot
@pode_renderizar
def test_guarda_janela_minimizada_sai_com_rc_4(pasta_e):
    cfg = config.carregar()
    godot.garantir_importado(cfg)
    comando = [config.godot(cfg), "--path", config.projeto(cfg), "--position", "1070,200", "--fixed-fps", "30",
               "--write-movie", pasta_e / "x.avi", "--", f"--job={_job(pasta_e)}", "--minimizar=1"]
    rc, saida = godot._rodar(comando, timeout=120, cfg=cfg)
    assert rc == 4, saida[-1500:]
    assert "janela minimizada" in " ".join(json.loads((pasta_e / "rel.json").read_text(encoding="utf-8"))["avisos"])


def _foco_do_godot(parar: threading.Event, visto: list) -> None:
    if sys.platform != "win32":
        return
    user32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    while not parar.is_set():
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
        h = k32.OpenProcess(0x1000, False, pid.value)
        if h:
            buf = ctypes.create_unicode_buffer(1024)
            n = ctypes.c_ulong(1024)
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) and "godot" in buf.value.lower():
                visto.append(buf.value)
            k32.CloseHandle(h)
        time.sleep(0.05)


@precisa_godot
@pode_renderizar
@pytest.mark.skipif(not TEM_FFMPEG, reason="sem ffmpeg/ffprobe")
def test_render_curto_conferido_e_sem_roubar_foco(pasta_e):
    tl = pasta_e / "sint2.json"
    tl.write_text(json.dumps(sintetica.timeline_sintetica(2.0)), encoding="utf-8")
    parar, visto = threading.Event(), []
    vigia = threading.Thread(target=_foco_do_godot, args=(parar, visto), daemon=True)
    vigia.start()
    try:
        resumo = render.renderizar(tl, pasta_e / "sint2.mp4")
    finally:
        parar.set()
        vigia.join(2)
    assert resumo["ok"] and resumo["quadros"] == 60
    assert resumo["sons"]["ids_distintos"] >= 6 and not resumo["sons"]["faltando"]
    m = resumo["medidas"]
    assert m["quadros"] == 60 and abs(m["duracao_video"] - 2.0) < 0.05
    assert m["lufs"] > -40 and m["media_db"] > -45
    info = checagens.sonda(pasta_e / "sint2.mp4")
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1080, 1920)
    assert any(s["codec_type"] == "audio" for s in info["streams"])
    assert not (pasta_e / "_sint2_trabalho").exists(), "o AVI intermediario tem de ser apagado"
    assert visto == [], f"a janela do Godot pegou o foco: {visto[:3]}"
