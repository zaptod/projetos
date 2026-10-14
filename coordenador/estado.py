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


GRAVAR_TENTATIVAS = 10
GRAVAR_PAUSA_S = 0.05


def _gravar_atomico(alvo: Path, texto: str, *, tentativas: int = GRAVAR_TENTATIVAS,
                    pausa=None, trocar=None) -> None:
    """Temporario UNICO (pid) + `os.replace`, com nova tentativa no
    PermissionError do Windows (destino aberto por outro processo). Quem le
    nunca ve o arquivo pela metade: ou o velho inteiro, ou o novo inteiro.
    Se todas as tentativas falharem, o temporario e apagado e o erro sobe.

    Sem fsync de proposito: medido 14/10/2026, ~400 ms por gravacao no E:
    (contra ~4 ms sem), a cada pulso de 5 s; o arquivo e regravado no pulso
    seguinte e `ler_estado` ja trata arquivo ruim como vazio.
    Medido tambem, leitor em outro processo: em laco sem pausa (~7 mil
    leituras/s) 5 tentativas nao bastaram (1 falha em 8 gravacoes); com 10
    tentativas curtas (0,05 s, 0,10 s ... teto ~2,3 s) foram 0 falhas, no
    maximo 6 tentativas; lendo ~550/s (muito acima do app), no maximo 4."""
    alvo.parent.mkdir(parents=True, exist_ok=True)
    temporario = alvo.with_name(f".{alvo.name}.{os.getpid()}.tmp")
    with open(temporario, "w", encoding="utf-8") as fh:
        fh.write(texto)
    pausa = time.sleep if pausa is None else pausa
    trocar = os.replace if trocar is None else trocar
    tentativas = max(1, int(tentativas))
    try:
        for tentativa in range(1, tentativas + 1):
            try:
                trocar(temporario, alvo)
                return
            except PermissionError:
                if tentativa >= tentativas:
                    raise
                pausa(GRAVAR_PAUSA_S * tentativa)
    finally:
        if temporario.exists():
            try:
                temporario.unlink()
            except OSError:
                pass


def gravar_estado(dados: dict, *, tentativas: int = GRAVAR_TENTATIVAS, pausa=None,
                  trocar=None) -> None:
    """O `estado.json` que o app le, gravado de forma atomica e com nova
    tentativa.

    O app le `estado.json` a cada tela (api_http) e `coordenador status`
    tambem; a leitura que coincide com o `os.replace` da PermissionError e,
    ate 13/10/2026, derrubava o coordenador inteiro (auditoria, item 1).
    """
    _gravar_atomico(caminho(), json.dumps(dados, ensure_ascii=False, separators=(",", ":")),
                    tentativas=tentativas, pausa=pausa, trocar=trocar)


def caminho_reinicios_pendentes() -> Path:
    return pasta() / "reinicios_pendentes.json"


def pedir_reinicio_pendente(nome: str) -> None:
    """Um `coordenador reiniciar <svc>` recusado pela janela fica aqui ate o
    coordenador residente o ler (`tomar_reinicios_pendentes`)."""
    alvo = caminho_reinicios_pendentes()
    try:
        atuais = json.loads(alvo.read_text(encoding="utf-8"))
        atuais = [str(x) for x in atuais] if isinstance(atuais, list) else []
    except (OSError, ValueError):
        atuais = []
    if nome not in atuais:
        atuais.append(nome)
    _gravar_atomico(alvo, json.dumps(atuais))


def tomar_reinicios_pendentes() -> list[str]:
    """Le E apaga a lista; vazia (ou ilegivel) quando nao ha nada.

    Primeiro TOMA o arquivo (rename para um nome so deste processo), depois
    le: um `pedir` que chegue no meio cria um arquivo novo, que o proximo
    pulso toma, em vez de ser apagado sem leitura."""
    alvo = caminho_reinicios_pendentes()
    tomado = alvo.with_name(f".{alvo.name}.{os.getpid()}.tomado")
    try:
        os.replace(alvo, tomado)
    except OSError:
        return []
    try:
        dados = json.loads(tomado.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = []
    finally:
        try:
            tomado.unlink()
        except OSError:
            pass
    return [str(x) for x in dados] if isinstance(dados, list) else []


def gravar_comando_servico(comando: str, valor: str, aparelho: str = "") -> dict:
    """Atalho para clientes locais: usa a mesma fila e validacao do app."""
    from remoto.orquestrador import gravar_comando
    return gravar_comando(comando, valor, aparelho)
