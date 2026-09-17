# -*- coding: utf-8 -*-
"""O segundo lancamento TRAZ a janela de volta, em vez de sair calado.

Bug relatado pelo Adrian em 17/09/2026: a janela sem borda nao esta na
barra de tarefas nem no Alt-Tab, e o mutex de instancia unica fazia o
duplo clique no .pyw sair sem fazer nada — sumida, ela nao voltava mais.

Agora a instancia viva escuta em 127.0.0.1 numa porta ESCOLHIDA PELO
SISTEMA (porta 0), e grava porta + um segredo aleatorio em
`flutuante.sinal` no runtime. O segundo processo le o arquivo, manda
"mostrar <segredo>" e sai. Sem o segredo certo, a mensagem e ignorada.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import threading
from pathlib import Path

MENSAGEM = "mostrar"


class Escuta:
    """Servidor minimo, numa thread. `ao_pedir()` roda NESSA thread: quem
    usa so deve publicar numa fila (a janela faz isso)."""

    def __init__(self, arquivo: Path, ao_pedir):
        self.arquivo = Path(arquivo)
        self.ao_pedir = ao_pedir
        self.segredo = secrets.token_hex(16)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(4)
        self._sock.settimeout(1.0)
        self.porta = self._sock.getsockname()[1]
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._laco, daemon=True,
                                        name="flutuante-sinal")

    def iniciar(self) -> "Escuta":
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".tmp")
        temporario.write_text(json.dumps(
            {"porta": self.porta, "segredo": self.segredo,
             "pid": os.getpid()}), encoding="utf-8")
        os.replace(temporario, self.arquivo)
        self._thread.start()
        return self

    def _laco(self) -> None:
        while not self._parar.is_set():
            try:
                conexao, _ = self._sock.accept()
            except (socket.timeout, OSError):
                continue
            with conexao:
                try:
                    conexao.settimeout(2.0)
                    dado = conexao.recv(256).decode("utf-8", "replace")
                except OSError:
                    continue
                if dado.strip() == f"{MENSAGEM} {self.segredo}":
                    try:
                        self.ao_pedir()
                    except Exception:                        # noqa: BLE001
                        pass

    def parar(self) -> None:
        self._parar.set()
        try:
            self._sock.close()
        except OSError:
            pass
        try:
            dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
            if dados.get("pid") == os.getpid():
                self.arquivo.unlink()
        except (OSError, ValueError):
            pass


def pedir_para_mostrar(arquivo: Path, timeout: float = 3.0) -> bool:
    """Manda a instancia viva aparecer. True se alguem recebeu."""
    try:
        dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
        porta, segredo = int(dados["porta"]), str(dados["segredo"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    try:
        with socket.create_connection(("127.0.0.1", porta),
                                      timeout=timeout) as conexao:
            conexao.sendall(f"{MENSAGEM} {segredo}".encode("utf-8"))
        return True
    except OSError:
        return False


__all__ = ["Escuta", "pedir_para_mostrar"]
