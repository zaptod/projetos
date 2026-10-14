# -*- coding: utf-8 -*-
"""A catraca de arquitetura (SCR-3, 14/10/2026).

Medido: rodada de DENTRO de uma worktree (`E:\\projetos\\.claude\\worktrees\\X`)
a catraca dizia "0 cirurgias de sys.path, nada piorou" — o `.claude` do
PROPRIO caminho fazia o `IGNORAR` pular o repositorio inteiro. No checkout
principal eram 19 (teto 2). Agora ela olha so as partes abaixo da raiz, e o
teto e o numero real (12, depois de tirar 7 dos testes e os prototipos de
`docs/`), para nao deixar crescer.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

FERRAMENTA = Path(__file__).resolve().parent / "auditoria_arquitetura.py"


def _auditoria():
    spec = importlib.util.spec_from_file_location("auditoria_arq_teste", FERRAMENTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_raiz_dentro_de_pasta_ignorada_ainda_e_varrida(tmp_path, monkeypatch):
    a = _auditoria()
    raiz = tmp_path / ".claude" / "worktrees" / "x"
    (raiz / "pacote").mkdir(parents=True)
    # o literal montado em pedacos: escrito inteiro aqui, a catraca contaria
    # ESTE arquivo
    cirurgia = "sys.path." + "insert(0, 'x')"
    (raiz / "pacote" / "mod.py").write_text(
        f"import sys\n{cirurgia}\n", encoding="utf-8")
    (raiz / ".venv").mkdir()
    (raiz / ".venv" / "lib.py").write_text(f"import sys\n{cirurgia}\n",
                                          encoding="utf-8")
    monkeypatch.setattr(a, "RAIZ", raiz.resolve())
    assert a.mutacoes_de_path() == ["pacote/mod.py:2"]


def test_o_repositorio_nao_passa_do_teto():
    a = _auditoria()
    teto = a._ler_baseline()
    agora = a._contagens(a.medir())
    assert agora["sys_path"] > 0, "a catraca nao viu nada: esta olhando?"
    assert all(agora[c] <= teto[c] for c in teto if c in agora), (agora, teto)
