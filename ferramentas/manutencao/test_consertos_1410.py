# -*- coding: utf-8 -*-
"""SCR-F1, SCR-F2 e SCR-F3 da auditoria profunda (14/10/2026)."""
from __future__ import annotations

import contextlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

FERRAMENTAS = Path(__file__).resolve().parents[1]


def _modulo(nome: str, arquivo: Path):
    spec = importlib.util.spec_from_file_location(nome, arquivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# ------------------------------------------------------------- SCR-F2
def test_copiar_recusa_caminho_que_escapa(tmp_path: Path) -> None:
    """`destino / "../fora.txt"` sobrescrevia um irmao da arvore, sem copia."""
    copiar = _modulo("copiar_f2", FERRAMENTAS / "manutencao" / "copiar.py")
    origem, destino = tmp_path / "origem", tmp_path / "destino"
    origem.mkdir()
    destino.mkdir()
    (tmp_path / "fora.txt").write_text("original", encoding="utf-8")
    (origem / "ok.txt").write_text("novo", encoding="utf-8")
    with pytest.raises(ValueError):
        copiar.copiar(origem, destino, ["ok.txt", "../fora.txt"])
    assert (tmp_path / "fora.txt").read_text(encoding="utf-8") == "original"
    assert not (destino / "ok.txt").exists(), "conferiu todos ANTES de escrever"
    with pytest.raises(ValueError):
        copiar.copiar(origem, destino, [str(tmp_path / "fora.txt")])


# ------------------------------------------------------------- SCR-F3
def test_obsidian_cofre_ausente_sai_1(tmp_path: Path) -> None:
    obsidian = _modulo("obsidian_f3", FERRAMENTAS / "obsidian.py")
    assert obsidian.main(["--cofre", str(tmp_path / "ausente"), "instalar"]) == 1


# ------------------------------------------------------------- SCR-F1
def test_conciliar_duas_vezes_grava_uma(tmp_path: Path, monkeypatch) -> None:
    """A proposta e feita SEM a trava; a 2a conciliacao, com o ledger lido
    antes de a 1a gravar, gravava o mesmo `tiktok_id` de novo (2 linhas)."""
    conciliar = _modulo("conciliar_f1", FERRAMENTAS / "conciliar_tiktok.py")
    from builds import travas
    from builds.publicar import metricas

    ledger = tmp_path / "publicados.jsonl"
    ledger.write_text("", encoding="utf-8")
    captura = tmp_path / "captura.json"
    captura.write_text(json.dumps({"builds": [
        {"tiktok_id": "777", "post_time": 1760400000,
         "legenda": "Duelo do fogo contra o gelo"}]}), encoding="utf-8")
    video = SimpleNamespace(id="g1:duelo:celular", fonte_id="g1",
                            titulo="Duelo do fogo contra o gelo",
                            descricao_completa="Duelo do fogo contra o gelo",
                            perfil="celular")
    monkeypatch.setattr(metricas, "registro_do_canal", lambda canal: ledger)
    monkeypatch.setattr(conciliar, "_catalogo",
                        lambda canal: [video] if canal == "builds" else [])

    @contextlib.contextmanager
    def trava(nome, esperar=0.0):
        yield True
    monkeypatch.setattr(travas, "trava", trava)

    assert conciliar.main(["--captura", str(captura), "--gravar"]) == 0
    real = conciliar._ledger_lido
    chamadas = {"n": 0}

    def velho_fora_da_trava(caminho):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            return [], set()           # o estado de ANTES da 1a gravar
        return real(caminho)
    monkeypatch.setattr(conciliar, "_ledger_lido", velho_fora_da_trava)
    assert conciliar.main(["--captura", str(captura), "--gravar"]) == 0
    linhas = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()
              if l.strip()]
    assert [l["tiktok_id"] for l in linhas] == ["777"]
