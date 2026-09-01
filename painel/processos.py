# -*- coding: utf-8 -*-
"""Um supervisor de processos e uma fila. Nao cinco.

O painel antigo tinha CINCO filas: `_fila` (a generica) e mais quatro --
`_fluxo_fila`, `_pub_fila`, `_vila_fila`, `_hist_fila` -- que eram o MESMO
bloco de vinte linhas copiado, cada um com o seu `_lendo`, o seu `after(N)` e
o seu `except Exception` pelado devolvendo `{"erro": ...}`.

Repeticao ja seria motivo. O motivo maior sao os dois defeitos que ela
escondia: em dois lugares o `after()` era chamado DE DENTRO da thread
trabalhadora (`_importar_em_thread` e `JanelaTriagem._sondar`) -- o que os
proprios comentarios do arquivo proibiam, com o motivo escrito ao lado
("estoura *main thread is not in main loop*"). Com uma unica porta de
entrada, isso deixa de ser possivel: so o supervisor toca em `after`.

A REGRA, e e uma so:

    quem trabalha PUBLICA um recado na fila;
    quem desenha LE a fila, sempre na thread da interface.

Nenhuma thread trabalhadora recebe o widget, o `after`, nem o proprio
supervisor -- so uma funcao que devolve um valor.
"""
from __future__ import annotations

import queue
import subprocess
import threading
import time

SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# De quanto em quanto a interface esvazia a fila. 120 ms e o que o painel ja
# usava: rapido para o console parecer ao vivo, devagar para nao pesar.
INTERVALO_MS = 120


class Supervisor:
    """Roda comando e tarefa de fundo, e devolve tudo pela mesma porta."""

    def __init__(self, raiz, ao_registrar=None, ao_terminar=None):
        self.raiz = raiz
        self._fila: queue.Queue = queue.Queue()
        self._processos: list = []
        self._ao_registrar = ao_registrar or (lambda _t, _tipo: None)
        self._ao_terminar = ao_terminar or (lambda _n, _c: None)
        self._rodando = True
        self._agendado = self.raiz.after(INTERVALO_MS, self._drenar)

    # --------------------------------------------------------- comandos
    def rodar(self, argumentos: list, *, cwd=None, rotulo: str = "",
              depois=None) -> None:
        """Dispara um comando. `depois()` roda NA THREAD DA INTERFACE."""
        nome = rotulo or " ".join(str(a) for a in argumentos)
        self._fila.put(("linha", f">>> {nome}", "cmd"))
        try:
            processo = subprocess.Popen(
                [str(a) for a in argumentos],
                cwd=str(cwd) if cwd else None,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=SEM_JANELA)
        except OSError as erro:
            self._fila.put(("linha", f"nao consegui iniciar: {erro}", "erro"))
            return
        self._processos.append(processo)
        threading.Thread(target=self._ler, daemon=True,
                         args=(processo, nome, depois)).start()

    def _ler(self, processo, nome: str, depois) -> None:
        """THREAD TRABALHADORA. So publica na fila; nao toca em widget."""
        for linha in processo.stdout:
            self._fila.put(("linha", linha.rstrip(), "saida"))
        codigo = processo.wait()
        self._fila.put(("fim", nome, codigo, depois))

    # ------------------------------------------------------- tarefas
    def tarefa(self, funcao, ao_pronto, *, rotulo: str = "") -> None:
        """Roda `funcao()` fora da interface e entrega o valor a `ao_pronto`.

        Substitui os quatro pares fila+coletor copiados. `ao_pronto` sempre
        roda na thread da interface — e por isso que ele pode desenhar.
        """
        def trabalho():
            try:
                valor = funcao()
            except Exception as erro:                       # noqa: BLE001
                valor = {"erro": f"{type(erro).__name__}: {erro}"}
            self._fila.put(("valor", ao_pronto, valor, rotulo))

        threading.Thread(target=trabalho, daemon=True).start()

    # --------------------------------------------------------- interface
    def _drenar(self) -> None:
        """THREAD DA INTERFACE. O unico lugar que chama widget e `after`."""
        try:
            while True:
                item = self._fila.get_nowait()
                tipo = item[0]
                if tipo == "linha":
                    self._ao_registrar(item[1], item[2])
                elif tipo == "valor":
                    _, entregar, valor, _rotulo = item
                    self._chamar(entregar, valor)
                elif tipo == "fim":
                    _, nome, codigo, depois = item
                    self._processos = [p for p in self._processos
                                       if p.poll() is None]
                    self._ao_registrar(f"({nome}) terminou com codigo {codigo}",
                                       "fim" if codigo == 0 else "erro")
                    self._ao_terminar(nome, codigo)
                    if depois is not None:
                        self._chamar(depois)
        except queue.Empty:
            pass
        if self._rodando:
            self._agendado = self.raiz.after(INTERVALO_MS, self._drenar)

    def _chamar(self, funcao, *args) -> None:
        """Um callback que estoura nao pode derrubar o laco da interface."""
        try:
            funcao(*args)
        except Exception as erro:                           # noqa: BLE001
            self._ao_registrar(f"[painel] {type(erro).__name__}: {erro}",
                               "erro")

    # ----------------------------------------------------------- estado
    @property
    def ativos(self) -> int:
        self._processos = [p for p in self._processos if p.poll() is None]
        return len(self._processos)

    def parar_tudo(self) -> int:
        quantos = 0
        for processo in list(self._processos):
            if processo.poll() is None:
                try:
                    processo.kill()
                    quantos += 1
                except OSError:
                    pass
        return quantos

    def encerrar(self) -> None:
        """Para o laco E CANCELA o que ja estava agendado.

        So baixar a bandeira nao basta: o `after` marcado antes ainda dispara,
        e se a janela ja morreu o Tk reclama ("invalid command name"). Em
        producao isso vira ruido no fechamento; no teste, saida suja.
        """
        self._rodando = False
        if self._agendado is not None:
            try:
                self.raiz.after_cancel(self._agendado)
            except Exception:                               # noqa: BLE001
                pass
            self._agendado = None


class Periodico:
    """Uma coisa que se repete, com um interruptor de verdade.

    O painel antigo tinha cinco temporizadores que se reagendavam sozinhos,
    e dois deles NUNCA paravam: o do interruptor da pipeline lia disco na
    thread da interface a cada 3 s pela vida inteira do programa, mesmo com a
    pagina invisivel.
    """

    def __init__(self, raiz, intervalo_ms: int, funcao):
        self.raiz, self.intervalo_ms, self.funcao = raiz, intervalo_ms, funcao
        self._ligado = False
        self._agendado = None

    def ligar(self) -> None:
        if self._ligado:
            return
        self._ligado = True
        self._bater()

    def desligar(self) -> None:
        self._ligado = False
        if self._agendado is not None:
            try:
                self.raiz.after_cancel(self._agendado)
            except Exception:                               # noqa: BLE001
                pass
            self._agendado = None

    def _bater(self) -> None:
        if not self._ligado:
            return
        try:
            self.funcao()
        except Exception:                                   # noqa: BLE001
            pass
        if self._ligado:
            self._agendado = self.raiz.after(self.intervalo_ms, self._bater)


def agora_ms() -> int:
    return int(time.monotonic() * 1000)


__all__ = ["INTERVALO_MS", "Periodico", "Supervisor", "agora_ms"]
