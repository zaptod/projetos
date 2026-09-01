# -*- coding: utf-8 -*-
"""Travas por RECURSO, para os processos rodarem em paralelo sem se pisar.

Ate aqui existia uma trava so (a do worker de identidade), e ela serializava
tudo: gerar imagem de historia esperava o Digen, que esperava o PicassoIA.
Mas a restricao real nunca foi "um processo por vez" — e "um Chrome por
PERFIL por vez" (o Chrome tranca o user_data_dir) e "um worker por FILA"
(dois roubam os jobs `running` um do outro).

Entao a trava certa tem o nome do recurso:

    picasso__principal     a conta principal do PicassoIA
    chatgpt__historias     a conta do ChatGPT usada pelas historias
    fila_identidade        a fila de jobs do random_builds

Digen + PicassoIA + ChatGPT + render rodam JUNTOS, porque sao perfis
diferentes. Duas coisas na MESMA conta continuam em fila — que e o unico
caso em que precisa.

Lock de arquivo (msvcrt/fcntl), nao-bloqueante por padrao: quem nao pega a
trava recebe False e decide o que dizer ao usuario. `esperar` transforma em
fila com paciencia limitada.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path


def _pasta() -> Path:
    try:
        from .contas import runtime_dir
        base = runtime_dir() / "locks"
    except Exception:
        base = Path(__file__).resolve().parents[1] / "outputs" / "_locks"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _nome_seguro(nome: str) -> str:
    return "".join(c if c.isalnum() or c in "_-." else "_" for c in str(nome))[:80]


@contextmanager
def trava(nome: str, esperar: float = 0.0):
    """`with trava("picasso__principal") as minha:` — True se o recurso e seu.

    Com `esperar`, tenta de novo a cada meio segundo ate o prazo. O arquivo
    nunca e apagado (apagar lock em uso e corrida); ele e minusculo e fica.
    """
    caminho = _pasta() / f"{_nome_seguro(nome)}.lock"
    arquivo = open(caminho, "a+b")
    adquirido = False
    fim = time.monotonic() + max(0.0, float(esperar))
    try:
        arquivo.seek(0, os.SEEK_END)
        if arquivo.tell() == 0:
            arquivo.write(b"\0")
            arquivo.flush()
        while True:
            arquivo.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                adquirido = True
                break
            except OSError:
                if time.monotonic() >= fim:
                    break
                time.sleep(0.5)
        yield adquirido
    finally:
        if adquirido:
            try:
                arquivo.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        arquivo.close()


def ocupada(nome: str) -> bool:
    """O recurso esta em uso agora? (testa sem segurar)."""
    with trava(nome) as minha:
        return not minha


def estado() -> list:
    """Todas as travas conhecidas e quem esta segurando o que.

    E a resposta grafica para "o que esta rodando em paralelo agora?". Sem
    isto, saber se duas coisas podem rodar juntas exigia ler codigo: os
    perfis sao invisiveis, e o unico sintoma de colisao era uma mensagem de
    "em uso" no meio de uma geracao.
    """
    from . import contas

    saida = []
    for servico in ("picasso", "digen", "dreamface", "chatgpt", "gemini",
                    "tiktok", "youtube_web"):
        for canal in ("builds", "historias"):
            try:
                nome = do_perfil(servico, canal)
            except Exception:
                continue
            if any(linha["trava"] == nome for linha in saida):
                continue        # a mesma conta nos dois canais = uma trava so
            canais = [c for c in ("builds", "historias")
                      if _mesma(servico, c, nome)]
            saida.append({"trava": nome, "servico": servico,
                          "canais": canais, "ocupada": ocupada(nome)})
    return sorted(saida, key=lambda linha: linha["trava"])


def _mesma(servico: str, canal: str, nome: str) -> bool:
    try:
        return do_perfil(servico, canal) == nome
    except Exception:
        return False


def do_perfil(servico: str, canal: str = "builds",
              conta: str | None = None) -> str:
    """O nome da trava do PERFIL de Chrome daquele servico/conta.

    Vem do registro de contas: duas coisas na mesma conta disputam a mesma
    trava (correto — e o mesmo user_data_dir); contas diferentes do mesmo
    servico rodam em paralelo.
    """
    try:
        from .contas import ativa
        nome_conta = conta or ativa(servico, canal)
    except Exception:
        nome_conta = conta or "principal"
    return f"{servico}__{nome_conta}"


__all__ = ["do_perfil", "ocupada", "trava"]
