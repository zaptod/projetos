# -*- coding: utf-8 -*-
"""Estado pequeno e tolerante a falhas, consumido pela tela do celular."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def pasta() -> Path:
    teste = os.environ.get("NF_COORDENADOR_PASTA")
    if teste:
        return Path(teste)
    if os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("NEURAL_FIGHTS_RUNTIME_DIR"):
        # 02/10: o texto livre do Telegram virou entrada do cerebro, e um
        # teste antigo do bot ("apaga tudo por favor") escreveria na entrada
        # REAL, que o coordenador de verdade atenderia com o Codex. Sob o
        # pytest, sem pasta escolhida, vale a pasta descartavel do conftest.
        return Path(os.environ["NEURAL_FIGHTS_RUNTIME_DIR"]) / "coordenador"
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "neural-fights" / "coordenador"


def caminho() -> Path:
    return pasta() / "estado.json"


def ler_estado() -> dict:
    """Le o contrato; arquivo ausente ou ruim nunca derruba quem consulta."""
    try:
        dados = json.loads(caminho().read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


GRAVAR_TENTATIVAS = 5
GRAVAR_PAUSA_S = 0.15


def gravar_estado(dados: dict, *, tentativas: int = GRAVAR_TENTATIVAS, pausa=None) -> None:
    """tmp + replace, com nova tentativa no PermissionError do Windows.

    O app le `estado.json` a cada tela (api_http) e `coordenador status`
    tambem; a leitura que coincide com o `os.replace` da PermissionError e,
    ate 13/10/2026, derrubava o coordenador inteiro (auditoria, item 1).
    """
    alvo = caminho()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    temporario = alvo.with_name("." + alvo.name + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")),
                          encoding="utf-8")
    pausa = time.sleep if pausa is None else pausa
    for tentativa in range(1, max(1, int(tentativas)) + 1):
        try:
            os.replace(temporario, alvo)
            return
        except PermissionError:
            if tentativa >= tentativas:
                raise
            pausa(GRAVAR_PAUSA_S)


def caminho_reinicios_pendentes() -> Path:
    return pasta() / "reinicios_pendentes.json"


def pedir_reinicio_pendente(nome: str) -> None:
    """Um `coordenador reiniciar <svc>` recusado pela janela fica aqui ate o
    coordenador residente o ler (`tomar_reinicios_pendentes`)."""
    alvo = caminho_reinicios_pendentes()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    try:
        atuais = json.loads(alvo.read_text(encoding="utf-8"))
        atuais = [str(x) for x in atuais] if isinstance(atuais, list) else []
    except (OSError, ValueError):
        atuais = []
    if nome not in atuais:
        atuais.append(nome)
    alvo.write_text(json.dumps(atuais), encoding="utf-8")


def tomar_reinicios_pendentes() -> list[str]:
    """Le E apaga a lista; vazia (ou ilegivel) quando nao ha nada."""
    alvo = caminho_reinicios_pendentes()
    try:
        dados = json.loads(alvo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    try:
        alvo.unlink()
    except OSError:
        pass
    return [str(x) for x in dados] if isinstance(dados, list) else []


def gravar_comando_servico(comando: str, valor: str, aparelho: str = "") -> dict:
    """Atalho para clientes locais: usa a mesma fila e validacao do app."""
    from remoto.orquestrador import gravar_comando
    return gravar_comando(comando, valor, aparelho)
