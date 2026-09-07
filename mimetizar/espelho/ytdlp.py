# -*- coding: utf-8 -*-
"""A porta unica para o yt-dlp — sempre por subprocess, nunca por import.

Mesma doutrina do ffmpeg no resto do repositorio, e pelos mesmos dois motivos:

  1. O YouTube muda o site quase toda semana, e a correcao vem numa versao
     nova do yt-dlp. `pip install -U yt-dlp` conserta sem tocar neste codigo.
     Importar a API interna prende a ferramenta a uma versao.
  2. Um extractor que estoura derruba o processo dele, nao o nosso. Numa
     coleta de 300 videos, um video quebrado nao pode matar os outros 299.

Toda saida crua e devolvida junto com o codigo: quem chama decide o que e
falha e o que e aviso. `NaoInstalado` existe para separar "o yt-dlp nao esta
ai" (que tem conserto de uma linha) de "o download falhou" (que nao tem).
"""
from __future__ import annotations

import json
import subprocess
import sys

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

CONSERTO = (f"{sys.executable} -m pip install -U yt-dlp")


class NaoInstalado(RuntimeError):
    """O yt-dlp nao esta no ambiente."""


class Falhou(RuntimeError):
    """O yt-dlp rodou e devolveu erro."""


def comando_base() -> list:
    return [sys.executable, "-X", "utf8", "-m", "yt_dlp"]


def versao() -> str:
    """A versao instalada, ou "" quando o yt-dlp nao esta no ambiente."""
    try:
        proc = subprocess.run(comando_base() + ["--version"],
                              capture_output=True, text=True, timeout=60,
                              encoding="utf-8", errors="replace",
                              creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (proc.stdout or "").strip() if proc.returncode == 0 else ""


def exigir() -> str:
    """A versao instalada; levanta com o conserto quando falta."""
    marca = versao()
    if not marca:
        raise NaoInstalado(
            "o yt-dlp nao esta instalado neste Python.\n"
            f"  {CONSERTO}\n"
            "(ele e chamado por linha de comando, entao a versao nova entra "
            "sem mexer em codigo nenhum.)")
    return marca


def rodar(argumentos: list, *, timeout: float = 900.0) -> tuple:
    """Roda o yt-dlp. Devolve (codigo, stdout, stderr) — nao levanta por erro
    do YouTube, so por o yt-dlp nao existir."""
    exigir()
    try:
        proc = subprocess.run(comando_base() + list(argumentos),
                              capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace",
                              creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        return 124, "", f"o yt-dlp passou de {timeout:.0f}s e foi interrompido."
    except OSError as exc:
        raise NaoInstalado(f"nao consegui executar o yt-dlp: {exc}") from exc
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def rodar_streaming(argumentos: list, ao_linha=None, *,
                    timeout: float = 86400.0) -> int:
    """Roda mostrando a saida enquanto ela sai. Devolve o codigo.

    `rodar` acima segura tudo ate o fim, e para um download de tres horas
    isso significa uma tela parada por tres horas — indistinguivel de travado.
    Aqui cada linha chega na hora. `--newline` (quem chama poe) e o que faz o
    yt-dlp separar o progresso por quebra de linha em vez de `\\r`.
    """
    exigir()
    if ao_linha is None:
        ao_linha = print
    try:
        proc = subprocess.Popen(
            comando_base() + list(argumentos), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", bufsize=1, creationflags=NO_WINDOW)
    except OSError as exc:
        raise NaoInstalado(f"nao consegui executar o yt-dlp: {exc}") from exc
    try:
        for linha in proc.stdout:
            texto = linha.rstrip()
            if texto:
                ao_linha(texto)
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        ao_linha(f"[yt-dlp] passou de {timeout / 3600:.1f}h e foi interrompido.")
        return 124
    except KeyboardInterrupt:
        # Ctrl+C no meio de um acervo: mata o filho e devolve o controle. O
        # que ja baixou fica em disco e o arquivo de retomada tambem.
        proc.kill()
        raise
    finally:
        if proc.stdout:
            proc.stdout.close()


def json_de(argumentos: list, *, timeout: float = 900.0) -> dict:
    """Roda com `-J` e devolve o JSON. Levanta `Falhou` com a saida crua."""
    codigo, saida, erro = rodar(argumentos, timeout=timeout)
    texto = (saida or "").strip()
    if not texto:
        raise Falhou(_mensagem(codigo, erro))
    try:
        return json.loads(texto)
    except json.JSONDecodeError as exc:
        raise Falhou(
            f"o yt-dlp respondeu algo que nao e JSON ({exc.msg}). "
            f"Primeiros 200 caracteres: {texto[:200]!r}") from exc


def _mensagem(codigo: int, erro: str) -> str:
    """A queixa do yt-dlp, traduzida quando da para reconhecer."""
    bruto = (erro or "").strip()
    baixo = bruto.lower()
    if "is not a valid url" in baixo or "unsupported url" in baixo:
        return ("essa URL nao parece de um canal do YouTube.\n"
                "  Formatos que funcionam: https://www.youtube.com/@nome, "
                ".../channel/UC..., .../c/nome")
    if "private" in baixo or "sign in" in baixo or "cookies" in baixo:
        return ("o YouTube pediu sessao para ver isso (video privado, restrito "
                "por idade, ou so para inscritos).\n"
                "  Faca o login uma vez na pagina Contas (servico youtube_web) "
                "e rode de novo — a coleta reusa aquele perfil de Chrome.")
    if "http error 429" in baixo or "too many requests" in baixo:
        return ("o YouTube estrangulou a coleta (429). Espere alguns minutos e "
                "retome — o que ja veio fica em disco.")
    if not bruto:
        return f"o yt-dlp saiu com codigo {codigo} e nao explicou."
    return f"o yt-dlp falhou (codigo {codigo}):\n  {bruto[-800:]}"
