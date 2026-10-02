# -*- coding: utf-8 -*-
"""Allowlist das poucas acoes locais que o telefone pode pedir."""
from __future__ import annotations

import subprocess

PREFIXOS_TAREFA = ("Historias_auto_", "NeuralFights_gerar_", "NeuralFights_postar_")
ACOES = (
    {"id": "reiniciar_tudo_seguro", "rotulo": "Reiniciar tudo com seguranca", "perigo": True},
    {"id": "abrir_vscode", "rotulo": "Abrir o VS Code", "perigo": False},
    {"id": "bloquear_tela", "rotulo": "Bloquear a tela", "perigo": False},
    {"id": "cancelar_desligamento", "rotulo": "Cancelar desligamento", "perigo": False},
    {"id": "suspender", "rotulo": "Suspender o PC", "perigo": True},
    {"id": "status", "rotulo": "Ver status", "perigo": False},
)


def catalogo() -> list[dict]:
    return [dict(a) for a in ACOES]


def tarefa_permitida(nome: str) -> bool:
    return isinstance(nome, str) and nome.startswith(PREFIXOS_TAREFA) and "\\" not in nome and "/" not in nome


def validar(acao: str) -> str:
    if acao.startswith("rodar_tarefa:"):
        nome = acao.partition(":")[2]
        if tarefa_permitida(nome):
            return acao
        raise ValueError("tarefa fora da lista permitida")
    if acao in {a["id"] for a in ACOES}:
        return acao
    raise ValueError("acao fora do catalogo")


def executar(acao: str, *, rodar=subprocess.run, publicar_ativo=lambda: False,
             render_ativo=lambda: False, reiniciar_tudo=lambda: None, resumo=lambda: {}) -> dict:
    """Executa somente a allowlist. `rodar` e dublavel nos testes."""
    acao = validar(acao)
    if acao == "status":
        return {"ok": True, "nota": "status", "status": resumo()}
    if acao == "reiniciar_tudo_seguro":
        reiniciar_tudo()
        return {"ok": True, "nota": "reinicio seguro solicitado"}
    if acao == "suspender" and (publicar_ativo() or render_ativo()):
        raise ValueError("ha publicacao ou render em andamento")
    if acao.startswith("rodar_tarefa:"):
        comando = ["schtasks", "/run", "/tn", acao.partition(":")[2]]
    elif acao == "abrir_vscode":
        comando = ["code", r"E:\projetos"]
    elif acao == "bloquear_tela":
        comando = ["rundll32.exe", "user32.dll,LockWorkStation"]
    elif acao == "cancelar_desligamento":
        comando = ["shutdown", "/a"]
    else:
        comando = ["rundll32", "powrprof.dll,SetSuspendState", "0,1,0"]
    rodar(comando, check=True)
    return {"ok": True, "nota": acao}
