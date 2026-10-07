# -*- coding: utf-8 -*-
"""A ponte do Atelie para o palco (07/10/2026).

O Atelie grava o PNG em palco/biblioteca/partes/<grupo>/... (o destino do
manifesto). Ate aqui so o LUTADOR era lido: arma, skill, efeito e camada
anexados ficavam no disco e o video saia com o desenho de antes (medido:
render do duelo_00091 com garras/sai no destino saiu com `armas/_padrao`).

- a parte estatica le os .gd como texto (como test_buscas.py) e confere que
  os ids que o Godot monta existem no manifesto real;
- com Godot, `palco/testes/partes_palco.gd` roda headless numa biblioteca de
  mentira (manifesto + PNGs aqui gerados) e confere a cadeia inteira.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
MANIFESTO = RAIZ / "biblioteca" / "manifesto_slots.json"


def _godot():
    try:
        from builds.palco import config
        return config.godot_disponivel()
    except Exception:                                        # noqa: BLE001
        caminho = Path("E:/ferramentas/godot/Godot_v4.7.2-stable_win64_console.exe")
        return caminho if caminho.is_file() else None


GODOT = _godot()
precisa_godot = pytest.mark.skipif(GODOT is None, reason="Godot nao encontrado (config/palco.json ou NF_GODOT)")


def _texto(*partes: str) -> str:
    return RAIZ.joinpath(*partes).read_text(encoding="utf-8")


def test_a_biblioteca_procura_o_png_do_atelie_antes_da_cena_do_mesmo_nivel():
    bib = _texto("nucleo", "biblioteca.gd")
    corpo_arma = bib.split("func arma(", 1)[1].split("\nfunc ", 1)[0]
    assert corpo_arma.index('_id_slot("arma", "arma", "estilo"') < corpo_arma.index('"estilos/" + UtilPalco.slug(estilo)')
    assert corpo_arma.index('"estilos/" + UtilPalco.slug(estilo)') < corpo_arma.index('_id_slot("arma", "arma", "tipo"')
    assert corpo_arma.index('_id_slot("arma", "arma", "tipo"') < corpo_arma.index('"tipos/" + UtilPalco.slug(tipo)')
    # a corrente continua sendo a peca de Verlet
    assert 'UtilPalco.slug(tipo) != "corrente"' in corpo_arma
    corpo_obj = bib.split("func objeto(", 1)[1].split("\nfunc ", 1)[0]
    assert corpo_obj.index("png[0]") < corpo_obj.index('"skills/"') < corpo_obj.index("png[1]")
    # o comum do Atelie vem antes da cena CC0 por elemento (contrato §5.3)
    assert corpo_obj.index("png[2]") < corpo_obj.index('"objetos/%s/%s" % [tipo, UtilPalco.slug(elemento)]')
    assert corpo_obj.index("png[2]") < corpo_obj.index('"objetos/%s/_padrao" % tipo')
    # o manifesto e quem diz o destino; o .json do painel e lido, nao exigido
    assert '"manifesto_slots.json"' in bib
    assert "func opcoes_do_png(" in bib
    assert "func _cena_png(" in bib
    # beam e portal nao tem peca de um PNG so
    assert '"beam"' not in bib.split("const PARTE_DO_OBJETO", 1)[1].split("\n", 1)[0]
    palco = _texto("nucleo", "palco.gd")
    assert 'bib.objeto(tipo, str(t.get("elemento", "")), str(t.get("nome", "")), str(t.get("forma", "")))' in palco
    assert '"rosto_herdado": rosto_herdado' in palco
    lutador = _texto("biblioteca", "lutadores", "lutador_padrao.gd")
    assert "_anotar_heranca(nome, expr, _partes_modulares[chave])" in lutador
    render = (RAIZ.parent / "random_builds" / "builds" / "palco" / "render.py").read_text(encoding="utf-8")
    assert '"rosto_herdado": rel.get("rosto_herdado") or {}' in render


def test_os_ids_que_o_palco_monta_existem_no_manifesto():
    ids = {s["id"] for s in json.loads(MANIFESTO.read_text(encoding="utf-8"))["slots"]}
    esperados = [
        "arma/arma/estilo/garras/base", "arma/arma/estilo/sai/base", "arma/arma/tipo/dupla/base",
        "arma/projetil_arma/forma/faca/base", "arma/orbe/tipo/magica/orbitando",
        "skill/projetil/comum/_/base", "skill/projetil/elemento/fogo/base",
        "skill/projetil/skill/bola_de_fogo/base", "skill/area_chao/comum/_/base",
        "skill/invocacao/comum/_/base", "skill/estrutura/comum/_/base",
        "efeito/evento/tipo/acerto/base", "efeito/evento/variante/acerto_heavy/base",
        "efeito/evento/variante/acerto_corte/base", "efeito/evento/variante/movimento_aterrissagem/base",
        "efeito/evento/variante/projetil_fim_expirou/base",
        "efeito/conjuracao/elemento/fogo/base", "efeito/conjuracao/comum/_/base",
        "efeito/impacto/elemento/gelo/base", "efeito/impacto/comum/_/base",
        "camada_estado/estado/comum/_/atordoado", "camada_estado/status/comum/_/envenenado",
        "camada_estado/buffs/skill/escudo_de_brasas/base",
    ]
    faltam = [i for i in esperados if i not in ids]
    assert not faltam, faltam
    # os 54 estilos e os 8 tipos tem lugar (o que o Atelie oferece e o que o palco procura)
    estilos = [i for i in ids if i.startswith("arma/arma/estilo/")]
    tipos = [i for i in ids if i.startswith("arma/arma/tipo/")]
    assert len(estilos) == 54 and len(tipos) == 8


def _png(caminho: Path, tamanho, cor) -> None:
    Image = pytest.importorskip("PIL.Image")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", tamanho, (0, 0, 0, 0))
    w, h = tamanho
    im.paste(Image.new("RGBA", (w // 2, h // 2), cor), (w // 4, h // 4))
    im.save(caminho)


def _biblioteca_de_mentira(tmp_path: Path) -> Path:
    real = {s["id"]: s for s in json.loads(MANIFESTO.read_text(encoding="utf-8"))["slots"]}
    bib = tmp_path / "biblioteca"
    com_png = [
        "arma/arma/estilo/garras/base", "arma/arma/tipo/dupla/base", "arma/arma/tipo/corrente/base",
        "arma/projetil_arma/forma/faca/base",
        "skill/projetil/comum/_/base", "skill/projetil/elemento/fogo/base", "skill/area_chao/comum/_/base",
        "efeito/evento/tipo/acerto/base", "efeito/evento/variante/acerto_corte/base",
        "efeito/conjuracao/comum/_/base",
        "camada_estado/estado/comum/_/atordoado", "camada_estado/buffs/skill/escudo_de_brasas/base",
        # as trilhas reais (trilhas_reais.json): invocacao, trap e orbe
        "skill/invocacao/comum/_/base", "skill/estrutura/comum/_/base", "arma/orbe/tipo/magica/orbitando",
    ]
    sem_png = ["arma/arma/estilo/sai/base", "arma/arma/estilo/sabre/base", "arma/arma/tipo/reta/base",
               "camada_estado/status/comum/_/envenenado", "efeito/evento/tipo/parede/base"]
    quebrado = "camada_estado/status/comum/_/queimando"
    slots = []
    for i in com_png + sem_png + [quebrado]:
        slot = dict(real[i])
        slots.append(slot)
        if i in com_png:
            _png(bib / slot["destino"].split("palco/biblioteca/", 1)[1], tuple(slot["tamanho_px"]), (255, 0, 255, 255))
    # um PNG que nao abre (download cortado): tem de cair no desenho de hoje
    ruim = bib / real[quebrado]["destino"].split("palco/biblioteca/", 1)[1]
    ruim.parent.mkdir(parents=True, exist_ok=True)
    ruim.write_bytes(b"\x89PNG\r\n\x1a\n isto nao e um png")
    # duas cenas por elemento: uma CC0 provisoria e uma arte da Oficina
    for nome, script in (("trevas", "res://biblioteca/efeitos/objetos/objeto_cc0.gd"),
                         ("gelo", "res://biblioteca/efeitos/folha_animada.gd")):
        cena = bib / "efeitos" / "objetos" / "projetil" / f"{nome}.tscn"
        cena.parent.mkdir(parents=True, exist_ok=True)
        cena.write_text("[gd_scene load_steps=2 format=3]\n\n"
                        f'[ext_resource type="Script" path="{script}" id="1_x"]\n\n'
                        f'[node name="{nome.title()}" type="Node2D"]\nscript = ExtResource("1_x")\n',
                        encoding="utf-8")
    # o .json do painel ao lado da garras: a mao e a ponta marcadas a mao
    garras = bib / real["arma/arma/estilo/garras/base"]["destino"].split("palco/biblioteca/", 1)[1]
    garras.with_suffix(".json").write_text(json.dumps({"empunhadura": [100, 128], "ponta": [900, 128],
                                                       "origem": "teste"}), encoding="utf-8")
    (bib / "manifesto_slots.json").write_text(json.dumps({"slots": slots}), encoding="utf-8")
    return bib


@precisa_godot
def test_a_cadeia_com_png_no_godot(tmp_path):
    bib = _biblioteca_de_mentira(tmp_path)
    env = dict(os.environ, APPDATA=str(tmp_path / "appdata"))
    if not (RAIZ / ".godot").is_dir():
        subprocess.run([str(GODOT), "--headless", "--path", str(RAIZ), "--import"], env=env,
                       capture_output=True, timeout=600)
    p = subprocess.run([str(GODOT), "--headless", "--path", str(RAIZ), "--script",
                        "res://testes/partes_palco.gd", "--", f"--biblioteca={bib.as_posix()}",
                        f"--trilhas={(RAIZ / 'testes' / 'trilhas_reais.json').as_posix()}"],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    saida = (p.stdout or "") + (p.stderr or "")
    assert p.returncode == 0, saida[-3000:]
    assert "0 falha(s)" in saida, saida[-3000:]
    # erro de script no configurar/atualizar nao derruba o Godot (a funcao so
    # aborta): e o log que acusa. Foi assim que a invocacao saiu com 57%.
    assert "SCRIPT ERROR" not in saida, saida[-3000:]


def test_as_trilhas_do_teste_sao_cabecalhos_de_verdade():
    """O teste Godot so pega o erro de tipo se a trilha trouxer os canais
    como LISTA, como o palco.gd passa ao configurar."""
    dados = json.loads((RAIZ / "testes" / "trilhas_reais.json").read_text(encoding="utf-8"))
    trilhas = dados["trilhas"]
    assert {"projetil", "summon", "orbe", "area", "trap", "projetil_arma"} <= set(trilhas)
    for tipo, t in trilhas.items():
        assert t["tipo"] == tipo and "i0" in t and "i1" in t
        canais = [c for c, v in t.items() if isinstance(v, list)]
        assert canais, tipo
    assert isinstance(trilhas["projetil"]["ang"], list) and isinstance(trilhas["summon"]["ang"], list)
    assert dados["_origem"]["summon"].startswith("duelo_")


def test_ordem_do_comum_e_uma_constante():
    bib = _texto("nucleo", "biblioteca.gd")
    assert 'const ORDEM_DO_COMUM := "seu-vence"' in bib
    for ordem in ('"comum-vence"', '"provisoria-fica"'):
        assert ordem in bib.split("static func ordem_comum_e_elemento", 1)[1]
    assert 'const SCRIPTS_PROVISORIOS := ["res://biblioteca/efeitos/objetos/objeto_cc0.gd"]' in bib
    # a falha do PNG fica guardada e a borda transparente e corrigida
    assert "imagem.premultiply_alpha()" in bib
    assert "_texturas[caminho] = tex" in bib
    peca = _texto("nucleo", "peca_png.gd")
    assert "static func _numero(" in peca
    assert 'float(dados.get("dir", dados.get("ang"' not in peca
    assert "BLEND_MODE_PREMULT_ALPHA" in peca
