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

import hashlib
import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# De quanto em quanto a interface esvazia a fila. 120 ms e o que o painel ja
# usava: rapido para o console parecer ao vivo, devagar para nao pesar.
INTERVALO_MS = 120

# Uma ficha recem-criada e ainda vazia e de quem esta DISPARANDO agora (entre
# o `O_EXCL` e o `Popen`). Mais velha que isto, vazia, e resto de queda.
FICHA_NASCENDO_S = 30.0


# ------------------------------------------------------------- processos
def criado_em(pid) -> float | None:
    """Quando o processo nasceu (epoch), ou None se nao deu para saber.

    PID igual com nascimento diferente e OUTRO processo (o Windows recicla
    PID): sem isso, uma ficha velha travaria o botao para sempre.
    """
    try:
        numero = int(pid)
    except (TypeError, ValueError):
        return None
    if os.name != "nt" or numero <= 0:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, numero)  # QUERY_LIMITED_INFO
        if not handle:
            return None
        try:
            tempos = [wintypes.FILETIME() for _ in range(4)]
            if not k32.GetProcessTimes(handle, *(ctypes.byref(t)
                                                 for t in tempos)):
                return None
        finally:
            k32.CloseHandle(handle)
        cem_ns = (tempos[0].dwHighDateTime << 32) | tempos[0].dwLowDateTime
        return cem_ns / 1e7 - 11644473600.0
    except Exception:                                       # noqa: BLE001
        return None


def processo_vivo(pid, criado: float | None = None) -> bool:
    """O processo `pid` ainda roda (e e o mesmo que nasceu em `criado`)?"""
    try:
        numero = int(pid)
    except (TypeError, ValueError):
        return False
    if numero <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(numero, 0)
        except PermissionError:
            return True
        except OSError:
            return False
        return True
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, numero)
        if not handle:
            # 5 = acesso negado: existe, so nao e nosso. Na duvida, vivo.
            return k32.GetLastError() == 5
        try:
            codigo = wintypes.DWORD()
            if not k32.GetExitCodeProcess(handle, ctypes.byref(codigo)):
                return True
            if codigo.value != 259:                         # STILL_ACTIVE
                return False
        finally:
            k32.CloseHandle(handle)
    except Exception:                                       # noqa: BLE001
        return True
    if criado is None:
        return True
    agora = criado_em(numero)
    return agora is None or abs(agora - float(criado)) < 2.0


def pasta_dos_processos() -> Path:
    """Onde as janelas do painel contam umas as outras o que esta rodando.

    Fica no runtime (`%LOCALAPPDATA%/neural-fights`), fora do git. Cada
    janela e um processo: sem um lugar comum, a Criacao aberta duas vezes
    publicaria o mesmo video duas vezes.
    """
    fixa = os.environ.get("NF_PAINEL_PROCESSOS")
    if fixa:
        return Path(fixa)
    try:
        from .flutuante.caminhos import runtime
        return runtime() / "painel" / "processos"
    except Exception:                                       # noqa: BLE001
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "neural-fights" / "painel" / "processos"


class Registro:
    """Fichas `{nome, pid, criado}` por rotulo, uma por arquivo.

    So LE e escreve arquivo proprio; nao usa `builds.travas` (sondar trava
    pegando a trava derruba o dono). A ficha vive enquanto o FILHO vive,
    nao enquanto a janela vive: se o painel cair no meio de um upload, o
    upload continua, e o botao das outras janelas tem que continuar recusando.
    """

    def __init__(self, pasta: Path | None = None):
        self._pasta = Path(pasta) if pasta else None

    @property
    def pasta(self) -> Path:
        if self._pasta is None:
            self._pasta = pasta_dos_processos()
        return self._pasta

    def _arquivo(self, nome: str) -> Path:
        chave = hashlib.sha1(nome.encode("utf-8")).hexdigest()[:20]
        return self.pasta / f"{chave}.json"

    def _ler(self, arquivo: Path):
        """(ficha | None, idade_s). Ficha None = vazia ou ilegivel."""
        try:
            idade = time.time() - arquivo.stat().st_mtime
            texto = arquivo.read_text(encoding="utf-8")
        except OSError:
            return None, None
        try:
            ficha = json.loads(texto) if texto.strip() else None
        except ValueError:
            ficha = None
        return (ficha if isinstance(ficha, dict) else None), idade

    def ocupado(self, nome: str) -> dict | None:
        """A ficha viva de `nome` (de qualquer janela), ou None."""
        arquivo = self._arquivo(nome)
        if not arquivo.exists():
            return None
        ficha, idade = self._ler(arquivo)
        if idade is None:
            return None
        if ficha is None:
            return {"nome": nome, "pid": None} if idade < FICHA_NASCENDO_S \
                else None
        if processo_vivo(ficha.get("pid"), ficha.get("criado")):
            return ficha
        return None

    def reservar(self, nome: str) -> bool:
        """Cria a ficha de forma atomica. False se outro chegou antes."""
        arquivo = self._arquivo(nome)
        try:
            self.pasta.mkdir(parents=True, exist_ok=True)
        except OSError:
            return True        # sem pasta, a guarda local ainda vale
        for _tentativa in range(2):
            try:
                os.close(os.open(str(arquivo),
                                 os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return True
            except FileExistsError:
                if self.ocupado(nome) is not None:
                    return False
                try:
                    arquivo.unlink()                       # resto de queda
                except OSError:
                    return False
            except OSError:
                return True
        return False

    def gravar(self, nome: str, pid: int) -> None:
        arquivo = self._arquivo(nome)
        dados = {"nome": nome, "pid": int(pid), "criado": criado_em(pid),
                 "janela": os.getpid(),
                 "desde": time.strftime("%Y-%m-%dT%H:%M:%S")}
        try:
            temporario = arquivo.with_suffix(f".{os.getpid()}.tmp")
            temporario.write_text(json.dumps(dados, ensure_ascii=False),
                                  encoding="utf-8")
            os.replace(temporario, arquivo)
        except OSError:
            pass

    def soltar(self, nome: str, pid: int | None = None) -> None:
        """Apaga a ficha de `nome` -- so se ela ainda for do `pid` dado."""
        arquivo = self._arquivo(nome)
        if pid is not None:
            ficha, _idade = self._ler(arquivo)
            if ficha is not None and ficha.get("pid") not in (None, pid):
                return
        try:
            arquivo.unlink()
        except OSError:
            pass


def _matar_arvore(processo) -> bool:
    """Encerra o processo E os filhos dele (Chrome, ffmpeg, worker).

    `kill()` sozinho so mata o `python main.py`; os netos ficavam orfaos
    segurando o perfil do navegador e os arquivos. So e chamado com o filho
    ainda vivo (`poll() is None`), e ai o PID ainda e dele: o Popen segura o
    handle, entao o Windows nao recicla o numero.
    """
    if os.name == "nt":
        try:
            feito = subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(processo.pid)],
                capture_output=True, creationflags=SEM_JANELA, timeout=30)
            if feito.returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        processo.kill()
        return True
    except OSError:
        return False


class Supervisor:
    """Roda comando e tarefa de fundo, e devolve tudo pela mesma porta."""

    def __init__(self, raiz, ao_registrar=None, ao_terminar=None,
                 registro: Registro | None = None):
        self.raiz = raiz
        self._fila: queue.Queue = queue.Queue()
        self._processos: list = []
        self._vivos: dict = {}          # nome -> Popen (desta janela)
        self._botoes: dict = {}         # nome -> botao desligado
        self._registro = registro or Registro()
        self._trabalhos: list = []
        self._ao_registrar = ao_registrar or (lambda _t, _tipo: None)
        self._ao_terminar = ao_terminar or (lambda _n, _c: None)
        self._rodando = True
        self._agendado = self.raiz.after(INTERVALO_MS, self._drenar)

    # --------------------------------------------------------- comandos
    def rodar(self, argumentos: list, *, cwd=None, rotulo: str = "",
              depois=None, botao=None) -> bool:
        """Dispara um comando. `depois()` roda NA THREAD DA INTERFACE.

        UM POR ROTULO (PNL-1, 14/10/2026): o duplo clique em PUBLICAR abria
        dois processos, e o `main.py publicar` nao olha se ja publicou -- o
        mesmo video subia duas vezes. Agora, se ja ha um processo vivo com o
        mesmo rotulo, NESTA janela ou em outra do painel, o disparo e
        recusado e a gaveta diz por que. Devolve True se disparou.

        `botao`: fica desligado enquanto o processo roda. Sem ele, vale o
        botao que esta sendo clicado agora (`widgets.botao_em_curso`); passe
        `botao=False` para nao desligar nenhum.
        """
        nome = rotulo or " ".join(str(a) for a in argumentos)
        if botao is None:
            from .widgets import botao_em_curso
            botao = botao_em_curso()
        local = self._vivos.get(nome)
        if local is not None and local.poll() is None:
            self._recusar(nome, "nesta janela")
            return False
        outro = self._registro.ocupado(nome)
        if outro is not None:
            pid = outro.get("pid")
            self._recusar(nome, f"em outra janela do painel"
                                f"{f', processo {pid}' if pid else ''}")
            return False
        if not self._registro.reservar(nome):
            self._recusar(nome, "em outra janela do painel")
            return False
        self._fila.put(("linha", f">>> {nome}", "cmd"))
        try:
            processo = subprocess.Popen(
                [str(a) for a in argumentos],
                cwd=str(cwd) if cwd else None,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=SEM_JANELA)
        except OSError as erro:
            self._registro.soltar(nome)
            self._fila.put(("linha", f"nao consegui iniciar: {erro}", "erro"))
            return False
        self._registro.gravar(nome, processo.pid)
        self._processos.append(processo)
        self._vivos[nome] = processo
        if botao:
            self._desligar_botao(nome, botao)
        threading.Thread(target=self._ler, daemon=True,
                         args=(processo, nome, depois)).start()
        return True

    def rodando(self, nome: str) -> bool:
        """Ha processo vivo com este rotulo (aqui ou em outra janela)?"""
        local = self._vivos.get(nome)
        if local is not None and local.poll() is None:
            return True
        return self._registro.ocupado(nome) is not None

    def segura(self, botao) -> bool:
        """O botao esta desligado porque um processo dele ainda roda?"""
        return any(b is botao for b in self._botoes.values())

    def _recusar(self, nome: str, onde: str) -> None:
        # Direto, sem passar pela fila: a recusa acontece NA thread da
        # interface (quem clica) e tem que aparecer na hora.
        self._ao_registrar(f"já está rodando ({onde}): {nome} — não abri "
                           "outro", "erro")

    def _desligar_botao(self, nome: str, botao) -> None:
        try:
            botao.configure(state="disabled")
        except Exception:                                   # noqa: BLE001
            return
        self._botoes[nome] = botao

    def _religar_botao(self, nome: str) -> None:
        botao = self._botoes.pop(nome, None)
        if botao is None:
            return
        try:
            if botao.winfo_exists():
                botao.configure(state="normal")
        except Exception:                                   # noqa: BLE001
            pass

    def _ler(self, processo, nome: str, depois) -> None:
        """THREAD TRABALHADORA. So publica na fila; nao toca em widget."""
        for linha in processo.stdout:
            self._fila.put(("linha", linha.rstrip(), "saida"))
        codigo = processo.wait()
        self._fila.put(("fim", nome, codigo, depois, processo))

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

        fio = threading.Thread(target=trabalho, daemon=True)
        self._trabalhos = [f for f in self._trabalhos if f.is_alive()]
        self._trabalhos.append(fio)
        fio.start()

    def aguardar(self, limite: float = 30.0) -> bool:
        """Espera as tarefas de fundo acabarem. True se todas acabaram.

        Existe por um motivo do Tk, nao de logica: a thread trabalhadora
        segura a pagina (e com ela a janela) ate terminar. Se ela termina
        DEPOIS de a janela ser destruida, a ultima referencia cai naquela
        thread e o Tcl aborta o processo inteiro ("Windows fatal exception",
        visto nos testes em 17/09/2026). Quem fecha a janela e quer estar
        seguro espera aqui antes do `destroy`.
        """
        fim = time.monotonic() + limite
        for fio in list(self._trabalhos):
            fio.join(max(0.0, fim - time.monotonic()))
        self._trabalhos = [f for f in self._trabalhos if f.is_alive()]
        return not self._trabalhos

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
                    _, nome, codigo, depois = item[:4]
                    processo = item[4] if len(item) > 4 else None
                    self._processos = [p for p in self._processos
                                       if p.poll() is None]
                    if processo is None or self._vivos.get(nome) is processo:
                        self._vivos.pop(nome, None)
                        self._religar_botao(nome)
                    self._registro.soltar(
                        nome, processo.pid if processo is not None else None)
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
        """Encerra cada processo desta janela COM a arvore dele (PNL-6)."""
        nomes = {id(p): n for n, p in self._vivos.items()}
        quantos = 0
        for processo in list(self._processos):
            if processo.poll() is None and _matar_arvore(processo):
                quantos += 1
                self._ao_registrar(
                    f"encerrei a árvore do processo {processo.pid}: "
                    f"{nomes.get(id(processo), '?')}", "fim")
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


__all__ = ["INTERVALO_MS", "Periodico", "Registro", "Supervisor", "agora_ms",
           "criado_em", "pasta_dos_processos", "processo_vivo"]
