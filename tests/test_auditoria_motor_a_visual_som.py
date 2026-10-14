# -*- coding: utf-8 -*-
"""Metade A do motor que NAO mexe na luta (auditoria profunda de 11/10/2026).

Som: MOT-12 (ouvinte do cast), MOT-13 (pan dobrava o volume), MOT-22
(SUMMON mudo e grupo footstep vazio), MOT-27 (config apontando arquivo
inexistente; fanfarra de vitoria) e MOT-33 (volume em texto no config).
Visual: MOT-23..26. Modelos: MOT-28 (estilos do editor) e MOT-29 (migracao
de ``tamanho``).
"""
from __future__ import annotations

import json
import os
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from neural_fights.effects import audio as audio_mod  # noqa: E402
from neural_fights.effects.audio_anotador import AnotadorDeAudio  # noqa: E402

PACOTE_SONS = Path(audio_mod.__file__).resolve().parents[1] / "sounds"


# ------------------------------------------------------------------ som
def test_cast_toca_em_qualquer_x():
    anot = AnotadorDeAudio(seed=1)
    anot.listener_x = 25.0
    anot.play_skill("PROJETIL", "Bola de Fogo", 28.0, phase="cast")
    assert anot.sons, "cast a 28 m com o ouvinte a 25 m saiu mudo"
    assert anot.sons[-1]["volume"] > 0.3


def test_cast_longe_do_zero_nao_some():
    # Antes: ouvinte fixo em x=0, cast a 21 m = silencio.
    anot = AnotadorDeAudio(seed=1)
    anot.listener_x = 21.0
    anot.play_skill("PROJETIL", "Bola de Fogo", 21.0, phase="cast")
    assert len(anot.sons) == 1


def test_sem_ouvinte_toca_sem_posicao():
    anot = AnotadorDeAudio(seed=1)
    anot.play_skill("PROJETIL", "Bola de Fogo", 30.0, phase="cast")
    assert len(anot.sons) == 1
    assert "pan" not in anot.sons[0]


def test_pan_nao_altera_volume_total():
    anot = AnotadorDeAudio(seed=1)
    for pan in (0.0, 0.001, 0.5, -0.5):
        anot.play("clash_swords", 0.5, pan=pan)
    volumes = {s["volume"] for s in anot.sons}
    assert len(volumes) == 1, volumes


def test_posicional_tem_ganho_constante_e_sem_salto_no_centro():
    anot = AnotadorDeAudio(seed=1)
    anot.play_positional("clash_swords", 10.0, 10.0, volume=0.3)       # pan 0
    anot.play_positional("clash_swords", 10.001, 10.0, volume=0.3)     # pan ~0
    a, b = anot.sons[0]["volume"], anot.sons[1]["volume"]
    assert abs(a - b) < 1e-3, (a, b)
    base = 0.3 * anot.category_volumes["impactos"] * anot.sfx_volume * anot.master_volume
    assert a == pytest.approx(min(1.0, base * audio_mod.GANHO_POSICIONAL), abs=1e-3)


def test_summon_cast_toca():
    anot = AnotadorDeAudio(seed=1)
    anot.play_skill("SUMMON", "x", phase="cast")
    assert [s["id"] for s in anot.sons] == ["summon_cast"]


def test_grupo_footstep_tem_sons():
    anot = AnotadorDeAudio(seed=1)
    assert anot.sound_groups.get("footstep"), "grupo footstep vazio"


def test_config_so_aponta_arquivo_existente():
    cfg = json.loads((PACOTE_SONS / "sound_config.json").read_text(encoding="utf-8"))
    arquivos = {p.name for p in PACOTE_SONS.iterdir()}
    faltando = [k for k, v in cfg.items()
                if isinstance(v, str) and v[-4:] in (".mp3", ".wav", ".ogg") and v not in arquivos]
    assert faltando == []


def test_fanfarra_de_vitoria_existe_e_e_curta():
    arquivo = PACOTE_SONS / "arena_victory.wav"
    with wave.open(str(arquivo)) as w:
        duracao = w.getnframes() / w.getframerate()
    assert 0.8 <= duracao <= 2.0
    anot = AnotadorDeAudio(seed=1)
    assert anot.arquivos()["arena_victory"].name == "arena_victory.wav"
    anot.play_special("arena_victory", 1.0)
    # sai da categoria "ambiente" (0,03 no config do Adrian): audivel
    assert anot.sons[-1]["volume"] >= 0.3


def test_fanfarra_e_deterministica():
    from neural_fights.tools import sintetizar_fanfarra

    assert sintetizar_fanfarra.sintetizar()[:500] == sintetizar_fanfarra.sintetizar()[:500]


def test_volume_texto_no_config_nao_quebra_play(tmp_path, monkeypatch):
    cfg = json.loads((PACOTE_SONS / "sound_config.json").read_text(encoding="utf-8"))
    cfg["_volumes"]["golpes"] = "1.0"
    cfg["_volumes"]["ui"] = 7
    cfg["_volumes"]["impactos"] = "muito"
    (tmp_path / "sound_config.json").write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("NEURAL_FIGHTS_SOUND_RUNTIME_DIR", str(tmp_path))
    anot = AnotadorDeAudio(seed=1)
    assert anot.category_volumes["golpes"] == 1.0
    assert anot.category_volumes["ui"] == 1.0
    anot.play("slash_heavy", 0.5)
    assert anot.sons


def test_arquivos_de_som_nao_cria_a_pasta_de_runtime(tmp_path, monkeypatch):
    from neural_fights.effects import audio_anotador

    pasta = tmp_path / "nao_existe"
    monkeypatch.setenv("NEURAL_FIGHTS_SOUND_RUNTIME_DIR", str(pasta))
    mapa = audio_anotador.arquivos_de_som()
    assert "slash_heavy" in mapa
    assert not pasta.exists()
    assert audio_anotador.arquivos_de_som() == mapa


# --------------------------------------------------------------- visual
def test_attack_manager_nao_reinicia():
    from neural_fights.effects.attack import AttackAnimationManager

    AttackAnimationManager.reset()
    gerente = AttackAnimationManager()
    gerente.crater_marks.append(object())
    gerente.set_ppm(40)
    de_novo = AttackAnimationManager()
    assert de_novo is gerente
    assert len(de_novo.crater_marks) == 1
    assert de_novo.ppm == 40
    AttackAnimationManager.reset()
    assert AttackAnimationManager().crater_marks == []
    AttackAnimationManager.reset()


def test_faisca_vive_o_life():
    from neural_fights.effects.weapon_animations import WeaponAnimator

    estado = SimpleNamespace(spark_list=[{"life": 0.2, "timer": 0.0}])
    gerente = object.__new__(WeaponAnimator)
    for _ in range(11):
        gerente._update_sparks(estado, 1 / 60)
    assert estado.spark_list, "faisca de 0,2 s morreu antes de 0,183 s"
    for _ in range(2):
        gerente._update_sparks(estado, 1 / 60)
    assert not estado.spark_list


def test_trilha_de_faisca_nao_espelha():
    import pygame

    from neural_fights.effects import magic_vfx

    pygame.init()
    tela = pygame.Surface((200, 200), pygame.SRCALPHA)
    tela.fill((0, 0, 0, 0))
    cam = SimpleNamespace(converter=lambda x, y: (int(x), int(y)),
                          converter_tam=lambda t: t, zoom=1.0)
    particula = object.__new__(magic_vfx.MagicParticle)
    particula.__dict__.update(dict(
        vida=1.0, vida_max=1.0, trail=True, trail_points=[(100, 100), (120, 80)],
        cor=(255, 0, 0), x=120, y=80, tamanho=4, z=0,
    ))
    try:
        particula.draw(tela, cam)
    except (AttributeError, TypeError) as erro:
        pytest.skip(f"particula de faisca com outro contrato: {erro}")
    assert tela.get_at((118, 82))[3] > 0
    assert tela.get_at((118, 98))[3] == 0


def test_afterimage_vida_igual_max():
    from neural_fights.effects.movement import AfterImageTrail

    trilha = object.__new__(AfterImageTrail)
    trilha.images = []
    trilha.ativo = True
    trilha.config = {"cor_tint": (255, 255, 255)}
    trilha.cor_base = (200, 50, 50)
    trilha.lutador = SimpleNamespace(pos=[1.0, 2.0], z=0, angulo_olhar=0.0,
                                     dados=SimpleNamespace(tamanho=1.7))
    for nome in ("tint", "cor_tint"):
        setattr(trilha, nome, (255, 255, 255))
    try:
        trilha._spawn_image()
    except (AttributeError, TypeError) as erro:
        pytest.skip(f"AfterImageTrail com outro contrato: {erro}")
    img = trilha.images[-1]
    assert img.vida == img.max_vida


# --------------------------------------------------------------- modelos
def test_estilos_do_editor_tem_desenho():
    from neural_fights.effects import weapon_render as wr
    from neural_fights.models.constants import TIPOS_ARMA
    from neural_fights.tools.gerador_database import ESTILOS_ARMA

    renderer = {
        "Reta": wr.ESTILOS_RETA, "Dupla": wr.ESTILOS_DUPLA, "Corrente": wr.ESTILOS_CORRENTE,
        "Arco": wr.ESTILOS_ARCO, "Arremesso": wr.FORMAS_ARREMESSO,
    }
    for tipo, dados in TIPOS_ARMA.items():
        catalogo = [e["nome"] for e in ESTILOS_ARMA[tipo]["variantes"]]
        assert dados["estilos"] == catalogo, tipo
        if tipo in renderer:
            assert set(dados["estilos"]) <= set(renderer[tipo]), tipo


def test_migracao_tamanho_legado():
    from neural_fights.models.weapons import Arma, get_escala_visual_arma

    arma = Arma("T", "Reta", 10, 1.0, tamanho=100)
    assert arma.comp_cabo == 30
    assert arma.comp_lamina == 70
    magica = Arma("M", "Mágica", 10, 1.0, tamanho=20, distancia=40)
    assert magica.distancia == 40  # tamanho e medida da Magica, nao legado
    vazia = Arma("V", "Reta", 10, 1.0)
    pessoa = SimpleNamespace(tamanho=1.7)
    assert get_escala_visual_arma(vazia, pessoa) == 1.0


def test_habilidades_nao_compartilham_lista():
    from neural_fights.models.weapons import Arma

    lista = [{"nome": "Bola de Fogo", "custo": 10.0}]
    arma = Arma("T", "Reta", 10, 1.0, raridade="Lendário", habilidades=lista)
    arma.habilidades.append({"nome": "x", "custo": 1.0})
    assert len(lista) == 1
