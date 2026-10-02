# -*- coding: utf-8 -*-
"""O coordenador residente: adota, vigia e religa os quatro servicos."""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import acoes_pc
from .estado import gravar_estado, pasta

RAIZ = Path(r"E:\projetos")
ESPERAS = (5, 15, 60, 300)
LIMITE_FALHAS_HORA = 5
FALHAS_SAUDE = 3
PULSO_S = 5


def agora_iso(agora=None):
    return (agora or datetime.now()).isoformat(timespec="seconds")


def carregar_servicos(caminho=None):
    caminho = Path(caminho or Path(__file__).with_name("servicos.json"))
    return {s["nome"]: s for s in json.loads(caminho.read_text(encoding="utf-8"))["servicos"]}


def processos_windows(rodar=subprocess.run):
    """[{pid, comando}], isolado para que testes nao dependam do Windows."""
    script = "Get-CimInstance Win32_Process | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    try:
        resultado = rodar(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True, check=False)
        dados = json.loads(resultado.stdout or "[]")
    except (OSError, ValueError, TypeError):
        return []
    if isinstance(dados, dict):
        dados = [dados]
    return [{"pid": int(p.get("ProcessId")), "comando": str(p.get("CommandLine") or "")}
            for p in dados if p.get("ProcessId")]


def publicacao_rodando(processos):
    return any(re.search(r"postar\.py|publicacao_filha|main\.py.*\bpublicar\b", p.get("comando", ""), re.I)
               for p in processos)


class TravaUnica:
    def __init__(self, caminho=None):
        self.caminho = Path(caminho or pasta() / "coordenador.lock")
        self.adquirida = False

    def adquirir(self):
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(str(os.getpid()))
            self.adquirida = True
            return True
        except FileExistsError:
            return False

    def soltar(self):
        if self.adquirida:
            try:
                self.caminho.unlink()
            except OSError:
                pass
            self.adquirida = False


class Supervisor:
    """Nucleo injetavel. Os efeitos externos entram pelas funcoes do construtor."""
    def __init__(self, *, servicos=None, relogio=datetime.now, processos=processos_windows,
                 iniciar=None, parar=None, avisar=None, porta=None, carteiro=None,
                 git=None, comandos=None, aplicar=None, claude_proibido=None,
                 delegados=None, parar_delegado=None, executar_acao=None, gravar=None, log=None, raiz=RAIZ):
        self.servicos = servicos or carregar_servicos()
        self.relogio, self.processos = relogio, processos
        self.iniciar = iniciar or self._iniciar
        self.parar = parar or self._parar
        self.avisar = avisar or self._avisar
        self.porta = porta or self._porta_8931
        self.carteiro = carteiro or self._carteiro
        self.git = git or self._mudou_codigo
        self.comandos, self.aplicar = comandos, aplicar
        self.claude_proibido = claude_proibido or self._claude_proibido
        self.delegados = delegados or self._delegados
        self.parar_delegado = parar_delegado or self._parar_delegado
        self.executar_acao = executar_acao or self._executar_acao
        self.gravar = gravar or gravar_estado
        self.log = log or self._log
        self.raiz = Path(raiz)
        self.desde = agora_iso(self.relogio())
        self.falhas = {n: [] for n in self.servicos}
        self.saudes_ruins = {n: 0 for n in self.servicos}
        self.eventos = []
        self.avisos_mensagem = set()
        self.estado = {n: {"situacao": "parado", "pid": None, "desde": None,
                           "reinicios_24h": 0, "ultimo_erro": "", "codigo_velho": False,
                           "saude": "desconhecida", "proximo_reinicio": None,
                           "motivo_espera": ""} for n in self.servicos}

    def evento(self, servico, tipo, texto):
        self.eventos.append({"em": agora_iso(self.relogio()), "servico": servico,
                             "tipo": tipo, "texto": str(texto)[:300]})
        self.eventos = self.eventos[-100:]
        self.log(f"{servico or 'coordenador'} {tipo}: {texto}")

    @staticmethod
    def _log(texto):
        alvo = Path(r"E:\projetos\outputs\coordenador.txt")
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with open(alvo, "a", encoding="utf-8") as fh:
            fh.write(f"{agora_iso()} {texto}\n")

    def _iniciar(self, ficha):
        log = Path(ficha["log"])
        log.parent.mkdir(parents=True, exist_ok=True)
        fh = open(log, "a", encoding="utf-8")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if ficha["janela"] == "oculta" else 0
        try:
            proc = subprocess.Popen(ficha["comando"], cwd=ficha["cwd"], stdout=fh, stderr=subprocess.STDOUT,
                                    creationflags=flags)
            return proc.pid
        finally:
            fh.close()

    def _parar(self, pid):
        subprocess.run(["taskkill", "/pid", str(pid), "/t", "/f"], check=False,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    @staticmethod
    def _porta_8931():
        try:
            with socket.create_connection(("127.0.0.1", 8931), timeout=1):
                return True
        except OSError:
            return False

    @staticmethod
    def _carteiro():
        try:
            from ias.correio import estado_do_carteiro
            return estado_do_carteiro()
        except Exception:
            return {"situacao": "nunca", "pulso_em": None}

    @staticmethod
    def _avisar(texto):
        try:
            from ias.carteiro import avisar_telegram
            return avisar_telegram(texto)
        except Exception:
            return False

    @staticmethod
    def _claude_proibido():
        from remoto.claude_estado import motivo_proibido
        return motivo_proibido()

    @staticmethod
    def _delegados():
        try:
            from remoto.orquestrador import ler_estado
            return [a["id"] for a in ler_estado().get("agora", []) if a.get("situacao") == "trabalhando"]
        except Exception:
            return []

    @staticmethod
    def _parar_delegado(ident):
        subprocess.run(["python", "-m", "remoto.delegar", "parar", "--id", str(ident)], check=False)

    def _mudou_codigo(self, ficha, desde):
        inicio = datetime.fromisoformat(desde).timestamp() if desde else 0
        for modulo in ficha.get("modulos", []):
            alvo = self.raiz / modulo
            if alvo.exists() and any(p.stat().st_mtime > inicio for p in alvo.rglob("*.py")):
                return True
        return False

    def _executar_acao(self, acao):
        return acoes_pc.executar(acao, publicar_ativo=lambda: publicacao_rodando(self.processos()),
                                 reiniciar_tudo=self.reiniciar_tudo, resumo=self.resumo)

    def _adotar(self, ficha, processos):
        padrao = re.compile(ficha["assinatura"], re.I)
        return next((p for p in processos if padrao.search(p["comando"])), None)

    def _saude(self, nome, vivo):
        if not vivo:
            return "ruim"
        if nome == "app":
            return "ok" if self.porta() else "ruim"
        if nome == "carteiro":
            estado = self.carteiro()
            return "ok" if estado.get("situacao") not in ("parado", "nunca") else "ruim"
        return "ok"

    def seguro(self, nome, processos=None):
        processos = self.processos() if processos is None else processos
        if publicacao_rodando(processos):
            return False, "publicacao em andamento"
        agora = self.relogio()
        try:
            from random_builds.builds.grade import GRADE
            for h, m in GRADE:
                horario = agora.replace(hour=h, minute=m, second=0, microsecond=0)
                if horario - timedelta(minutes=12) <= agora <= horario + timedelta(minutes=18):
                    return False, "janela da grade"
        except ImportError:
            pass
        if nome == "carteiro" and self.carteiro().get("situacao") == "entregando":
            return False, "carteiro entregando"
        return True, ""

    def _limite(self, nome):
        agora = self.relogio().timestamp()
        self.falhas[nome] = [x for x in self.falhas[nome] if agora - x < 3600]
        return len(self.falhas[nome]) >= LIMITE_FALHAS_HORA

    def religar(self, nome, motivo="caiu", forcar=False):
        ficha, estado = self.servicos[nome], self.estado[nome]
        proximo = estado.get("proximo_reinicio")
        if not forcar and proximo:
            try:
                if self.relogio() < datetime.fromisoformat(proximo):
                    return False
            except ValueError:
                pass
        if ficha.get("reinicio_seguro") and not forcar:
            ok, espera = self.seguro(nome)
            if not ok:
                estado.update(situacao="reiniciando", motivo_espera=espera)
                return False
        if self._limite(nome):
            estado.update(situacao="falhou", ultimo_erro="limite de 5 falhas por hora")
            self.avisar(f"Coordenador: {nome} falhou 5 vezes em uma hora; parei de tentar.")
            return False
        try:
            pid = self.iniciar(ficha)
        except Exception as exc:  # o processo nao pode matar o coordenador
            self.falhas[nome].append(self.relogio().timestamp())
            espera = ESPERAS[min(len(self.falhas[nome]) - 1, len(ESPERAS) - 1)]
            estado.update(situacao="caiu", ultimo_erro=str(exc),
                          proximo_reinicio=agora_iso(self.relogio() + timedelta(seconds=espera)))
            self.evento(nome, "caiu", str(exc))
            return False
        estado.update(situacao="rodando", pid=pid, desde=agora_iso(self.relogio()), saude="desconhecida",
                      proximo_reinicio=None, motivo_espera="", codigo_velho=False,
                      reinicios_24h=estado["reinicios_24h"] + 1)
        self.evento(nome, "religou", f"PID {pid}")
        return True

    def verificar_servico(self, nome, processos):
        ficha, estado = self.servicos[nome], self.estado[nome]
        achado = self._adotar(ficha, processos)
        if achado is None:
            if estado["situacao"] != "falhou":
                estado.update(situacao="caiu", pid=None, saude="ruim")
                self.evento(nome, "caiu", "processo ausente")
                # A primeira subida e imediata; uma queda depois de adotado
                # respeita o primeiro degrau do backoff.
                if estado.get("desde") and not estado.get("proximo_reinicio"):
                    self.falhas[nome].append(self.relogio().timestamp())
                    estado["proximo_reinicio"] = agora_iso(self.relogio() + timedelta(seconds=ESPERAS[0]))
                self.religar(nome, "ausente")
            return
        if state_pid := achado.get("pid"):
            if estado["pid"] != state_pid:
                estado.update(pid=state_pid, desde=estado["desde"] or agora_iso(self.relogio()), situacao="rodando")
        estado["saude"] = self._saude(nome, True)
        if estado["saude"] == "ruim":
            self.saudes_ruins[nome] += 1
            if self.saudes_ruins[nome] >= FALHAS_SAUDE:
                estado["situacao"] = "caiu"
                self.parar(achado["pid"])
                self.falhas[nome].append(self.relogio().timestamp())
                estado["proximo_reinicio"] = agora_iso(self.relogio() + timedelta(seconds=ESPERAS[0]))
                self.religar(nome, "saude ruim")
            return
        self.saudes_ruins[nome] = 0
        if self.git(ficha, estado["desde"]):
            if not estado["codigo_velho"]:
                estado["codigo_velho"] = True
                self.evento(nome, "codigo_velho", "codigo mudou desde o inicio")
            ok, espera = self.seguro(nome, processos)
            if ok:
                self.parar(achado["pid"])
                self.religar(nome, "codigo velho", forcar=True)
                self.evento(nome, "reiniciou", "codigo atualizado")
            else:
                estado.update(motivo_espera=espera, proximo_reinicio=None)

    def processar_comandos(self):
        if not self.comandos or not self.aplicar:
            return
        meus = {"servico_reiniciar", "servico_parar", "servico_ligar", "pc_acao"}
        for comando in self.comandos():
            if comando.get("comando") not in meus:
                continue
            try:
                nome, valor = comando["comando"], comando.get("valor")
                if nome == "servico_parar":
                    pid = self.estado.get(valor, {}).get("pid")
                    if pid:
                        self.parar(pid)
                    self.estado[valor].update(situacao="desligado", pid=None)
                elif nome == "servico_ligar":
                    self.religar(valor)
                elif nome == "servico_reiniciar":
                    self.reiniciar_servico(valor)
                else:
                    self._executar_acao(valor)
                self.aplicar(comando["id"], nota="executado pelo coordenador")
                self.evento(str(valor), "comando", nome)
            except (KeyError, ValueError, OSError, subprocess.SubprocessError) as exc:
                self.aplicar(comando["id"], recusado=str(exc))

    def avisar_mensagem_sem_ouvinte(self):
        """O alerta e uma vez por mensagem; ela continua pendente para Claude."""
        if not self.comandos:
            return
        try:
            from remoto.orquestrador import sem_ouvinte, situacao_do_vigia
            aviso = sem_ouvinte(self.comandos(), situacao_do_vigia())
        except Exception:
            return
        ident = (aviso or {}).get("comando")
        mensagem = next((c for c in self.comandos() if c.get("id") == ident and
                         c.get("comando") == "mensagem"), None)
        if mensagem and ident not in self.avisos_mensagem:
            self.avisar("o Claude nao esta aberto; sua mensagem ficou guardada; "
                        "o coordenador executa so comandos do app")
            self.avisos_mensagem.add(ident)
            self.evento("", "aviso", "mensagem guardada sem ouvinte")

    def reiniciar_tudo(self):
        for nome in self.servicos:
            self.reiniciar_servico(nome)

    def reiniciar_servico(self, nome, *, forcar=False):
        """Para o processo adotado antes de subir outro, sem duplicar servico."""
        if self.servicos[nome].get("reinicio_seguro") and not forcar:
            ok, espera = self.seguro(nome)
            if not ok:
                self.estado[nome].update(situacao="reiniciando", motivo_espera=espera)
                return False
        achado = self._adotar(self.servicos[nome], self.processos())
        if achado:
            self.parar(achado["pid"])
            self.estado[nome]["pid"] = None
        return self.religar(nome, "pedido", forcar=forcar)

    def pulso(self):
        processos = self.processos()
        for nome in self.servicos:
            if self.estado[nome]["situacao"] != "desligado":
                self.verificar_servico(nome, processos)
        if self.claude_proibido():
            for ident in self.delegados():
                self.parar_delegado(ident)
        self.processar_comandos()
        self.avisar_mensagem_sem_ouvinte()
        self.gravar(self.resumo())

    def resumo(self):
        return {"pid": os.getpid(), "desde": self.desde, "pulso_em": agora_iso(self.relogio()),
                "versao": self._versao(), "servicos": self.estado,
                "acoes_pc": acoes_pc.catalogo(), "eventos": self.eventos[-100:]}

    @staticmethod
    def _versao():
        try:
            return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                  text=True, check=False).stdout.strip() or "desconhecida"
        except OSError:
            return "desconhecida"

    def rodar(self, parar=lambda: False):
        trava = TravaUnica()
        if not trava.adquirir():
            return 1
        try:
            while not parar():
                self.pulso()
                time.sleep(PULSO_S)
        finally:
            trava.soltar()
        return 0
