# -*- coding: utf-8 -*-
"""O que o bot sabe fazer. Tabela FECHADA de comandos, nunca shell.

Decisao de projeto, escrita aqui para nao se perder: este bot nao executa
texto vindo do celular. Cada comando e uma funcao Python desta tabela, e os
argumentos sao validados (um id de video so pode ser um id que existe no
catalogo). Um `/rodar <qualquer coisa>` seria conveniente por cinco minutos
e um buraco para sempre — a maquina do outro lado tem YouTube, TikTok,
ChatGPT e PicassoIA logados.

As funcoes devolvem TEXTO (e, as vezes, um caminho de arquivo para enviar).
Elas nao falam com o Telegram: isso deixa cada uma testavel sem rede, que e
como os testes deste arquivo rodam.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RANDOM_BUILDS = RAIZ / "random_builds"
HISTORIAS = RAIZ / "historias"
PY = sys.executable
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


from builds import atividade                                      # noqa: E402
from builds.identity import controle                              # noqa: E402

MAX_LINHAS = 18          # o celular nao le mais que isso de uma vez


# --------------------------------------------------------------- ajudantes
def _catalogo():
    from builds.publicar import catalogo
    return catalogo


def _tabela_videos(quantos: int = 8) -> list:
    try:
        videos = _catalogo().listar()
    except Exception:
        return []
    return sorted(videos, key=lambda v: v.quando, reverse=True)[:quantos]


def _rodar(args: list, cwd: Path, rotulo: str) -> str:
    """Dispara e NAO espera: uma geracao leva minutos, o celular nao espera.

    O resultado chega depois pelos alertas do diario — que e justamente o
    motivo de o diario existir.
    """
    try:
        subprocess.Popen(args, cwd=str(cwd), creationflags=NO_WINDOW,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return f"nao consegui iniciar {rotulo}: {exc}"
    return (f"comecei: {rotulo}\n"
            "Leva minutos. Eu aviso aqui quando terminar ou der erro.")


# ---------------------------------------------------------------- comandos
def ajuda(_args: str = "") -> str:
    return (
        "*O que eu faço*\n"
        "/status — o que está rodando agora\n"
        "/vila — as 7 fábricas, uma linha cada\n"
        "/erros — os últimos problemas\n"
        "/videos — os vídeos prontos, com id\n"
        "/ver <id> — manda o mp4 aqui pra você assistir\n"
        "/publicar <id> [youtube|tiktok|ambos] — sobe aquele vídeo\n"
        "/gerar — uma build nova (roleta + vídeo)\n"
        "/historias — em que pé está o canal de histórias\n"
        "/pausar [minutos] · /retomar · /parar\n"
        "/ajuda — isto aqui")


def status(_args: str = "") -> str:
    estado = atividade.estado_das_fabricas()
    trabalhando = [n for n, e in estado.items() if e["status"] == "trabalhando"]
    com_erro = [n for n, e in estado.items() if e["status"] == "erro"]
    pausa = controle.estado()

    linhas = []
    if trabalhando:
        for nome in trabalhando:
            dados = atividade.FABRICAS.get(nome, {})
            detalhe = (estado[nome].get("detalhe") or "")[:60]
            linhas.append(f"{dados.get('emoji', '•')} {dados.get('rotulo', nome)}"
                          f" — {detalhe}" if detalhe else
                          f"{dados.get('emoji', '•')} {dados.get('rotulo', nome)}")
        cabeca = f"⚙ {len(trabalhando)} fábrica(s) trabalhando"
    else:
        cabeca = "😴 nada rodando agora"
    if com_erro:
        linhas.append("")
        for nome in com_erro:
            dados = atividade.FABRICAS.get(nome, {})
            linhas.append(f"❗ {dados.get('rotulo', nome)}: "
                          f"{(estado[nome].get('detalhe') or '')[:70]}")
    resumo_pausa = pausa.get("resumo") or ""
    if resumo_pausa and "rodando" not in resumo_pausa.lower():
        linhas.append("")
        linhas.append(f"⏸ {resumo_pausa}")
    return "\n".join([cabeca] + linhas)


def vila(_args: str = "") -> str:
    estado = atividade.estado_das_fabricas()
    icone = {"trabalhando": "⚙", "erro": "❗", "ocioso": "·"}
    linhas = []
    for nome, dados in atividade.FABRICAS.items():
        info = estado.get(nome, {})
        situacao = info.get("status", "ocioso")
        detalhe = (info.get("detalhe") or "")[:40]
        linhas.append(f"{icone.get(situacao, '·')} {dados['emoji']} "
                      f"{dados['rotulo']:<11} {detalhe}".rstrip())
    return "\n".join(linhas)


def erros(args: str = "") -> str:
    try:
        quantos = min(int(args.strip()), MAX_LINHAS)
    except (TypeError, ValueError):
        quantos = 6
    eventos = [e for e in atividade.recentes(200)
               if e.get("status") == "erro"][:quantos]
    if not eventos:
        return "✓ nenhum erro registrado."
    linhas = []
    for evento in eventos:
        hora = str(evento.get("ts", ""))[11:16]
        fabrica = atividade.FABRICAS.get(evento.get("fabrica"), {})
        linhas.append(f"{hora} {fabrica.get('emoji', '•')} "
                      f"{(evento.get('detalhe') or '')[:110]}")
    return "\n".join(linhas)


def videos(_args: str = "") -> str:
    prontos = _tabela_videos()
    if not prontos:
        return "nenhum vídeo pronto ainda."
    linhas = ["*Prontos* (use /ver ou /publicar com o id)"]
    for video in prontos:
        linhas.append(f"`{video.id}`\n   {video.titulo[:58]}")
    return "\n".join(linhas)


def procurar_video(pedaco: str):
    """O video cujo id COMECA com o que veio do celular (id inteiro e longo)."""
    pedaco = (pedaco or "").strip()
    if not pedaco:
        return None
    try:
        for video in _catalogo().listar():
            if video.id.startswith(pedaco) or pedaco in video.id:
                return video
    except Exception:
        return None
    return None


def ver(args: str = "") -> tuple:
    """(texto, caminho): o bot manda o arquivo quando ha caminho."""
    video = procurar_video(args)
    if video is None:
        return ("não achei esse id. Use /videos para ver a lista.", None)
    return (f"{video.titulo}", Path(video.caminho))


def publicar(args: str = "") -> str:
    partes = (args or "").split()
    if not partes:
        return "diga o id: /publicar <id> [youtube|tiktok|ambos]"
    video = procurar_video(partes[0])
    if video is None:
        return "não achei esse id. Use /videos para ver a lista."
    onde = (partes[1] if len(partes) > 1 else "youtube").lower()
    if onde not in ("youtube", "tiktok", "ambos"):
        return "onde? youtube, tiktok ou ambos."

    comando = [PY, "main.py", "publicar", video.id]
    if onde in ("youtube", "ambos"):
        comando += ["--youtube"]
    if onde in ("tiktok", "ambos"):
        comando += ["--tiktok", "--postar"]
    return _rodar(comando, RANDOM_BUILDS,
                  f"publicar «{video.titulo[:40]}» em {onde}")


def gerar(_args: str = "") -> str:
    return _rodar([PY, "main.py", "generate-video"], RANDOM_BUILDS,
                  "uma build nova")


def historias(_args: str = "") -> str:
    try:
        saida = subprocess.run(
            [PY, "-X", "utf8", "main.py", "status"], cwd=str(HISTORIAS),
            capture_output=True, text=True, encoding="utf-8", timeout=120,
            creationflags=NO_WINDOW).stdout or ""
    except (OSError, subprocess.SubprocessError) as exc:
        return f"não consegui ler as histórias: {exc}"
    linhas = [l.rstrip() for l in saida.splitlines() if l.strip()]
    return "\n".join(linhas[:MAX_LINHAS]) or "nenhuma história ainda."


def pausar(args: str = "") -> str:
    try:
        minutos = float(args.strip()) if args.strip() else None
    except ValueError:
        minutos = None
    estado = controle.pausar(motivo="pelo celular", minutos=minutos)
    return f"⏸ {estado.get('resumo', 'pausado')}"


def retomar(_args: str = "") -> str:
    estado = controle.retomar()
    return f"▶ {estado.get('resumo', 'retomado')}"


def parar(_args: str = "") -> str:
    estado = controle.pedir_parada("pelo celular")
    return (f"⏹ {estado.get('resumo', 'parada pedida')}\n"
            "O job atual termina antes de encerrar.")


# A tabela. Nada fora daqui roda — e de proposito.
TABELA = {
    "ajuda": ajuda, "start": ajuda, "help": ajuda,
    "status": status,
    "vila": vila,
    "erros": erros,
    "videos": videos,
    "ver": ver,
    "publicar": publicar,
    "gerar": gerar,
    "historias": historias,
    "pausar": pausar,
    "retomar": retomar,
    "parar": parar,
}


def executar(texto: str):
    """(resposta, arquivo_ou_None) para o texto que chegou do celular."""
    texto = (texto or "").strip()
    if not texto.startswith("/"):
        return ("mande /ajuda para ver o que eu faço.", None)
    corpo = texto[1:]
    nome, _, args = corpo.partition(" ")
    nome = nome.split("@")[0].lower()       # /status@meubot
    funcao = TABELA.get(nome)
    if funcao is None:
        return (f"não conheço /{nome}. Veja /ajuda.", None)
    try:
        resultado = funcao(args.strip())
    except Exception as exc:      # nenhum comando pode derrubar o bot
        return (f"o comando /{nome} falhou: {type(exc).__name__}: {exc}", None)
    if isinstance(resultado, tuple):
        return resultado
    return (resultado, None)
