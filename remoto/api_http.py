# -*- coding: utf-8 -*-
"""API do app do celular — HTTP da biblioteca padrao, SO dentro do Tailscale.

    python -m remoto.api_http              # sobe no IP do Tailscale
    python -m remoto.api_http --parear     # codigo de 6 digitos para o celular
    python -m remoto.api_http --local      # 127.0.0.1, para teste
    python -m remoto.api_http --aparelhos  # quem esta pareado
    python -m remoto.api_http --esquecer <nome>

POR QUE ASSIM. A maquina tem YouTube, TikTok, ChatGPT e PicassoIA logados.
O bot resolve isso ligando de dentro para fora; um app precisa de mais (ver o
mp4 inteiro, o diario ao vivo), e a resposta e a rede privada do Tailscale:
o servidor escuta SO no IP 100.x dessa rede. Sem esse IP ele NAO sobe — nao
existe "cair para 0.0.0.0". `--local` e o unico outro endereco, e e o
loopback (tambem e o que `tailscale serve` usa para dar HTTPS ao app).

TRANCAS, na ordem em que a requisicao passa por elas:
  1. endereco: so a rede do Tailscale (ou o loopback, com --local);
  2. Host: so o IP, o nome da maquina ou *.ts.net (contra DNS rebinding);
  3. token: `Authorization: Bearer`, comparado em tempo constante. No disco
     fica so o SHA-256 de cada token; o token em si so existe no celular;
  4. rotas: tabela FECHADA, nenhuma recebe texto para executar. As acoes
     (fase 2, `acoes.py`) so existem com `--acoes`, e as que nao se
     desfazem pedem confirmacao em dois passos.

PAREAMENTO. `--parear` grava o hash de um codigo de 6 digitos, valido por
5 minutos e por UMA troca. O app manda o codigo e recebe o token. O token
nunca aparece em URL (historico do navegador, captura de tela). Cinco
codigos errados invalidam o codigo.

VIDEO. `<video src>` nao manda cabecalho, entao o app pede um BILHETE
(autenticado) e usa `/v/<bilhete>`: vale 10 minutos e so para aquele mp4.
Cada resposta leva no maximo `FATIA_MAX` bytes, sempre por Range.

A PORTA NAO E 8765: essa e do login OAuth do YouTube, e um servidor
esquecido nela ja quebrou o login.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from . import (acoes, comandos_app, decisoes, orquestrador, painel_dados, tarefas,
               vila_dados, vila_nova)
from .config import runtime_dir

PORTA_PADRAO = 8931
PORTAS_PROIBIDAS = {8765}                # OAuth do YouTube
REDE_TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
APP = Path(__file__).resolve().parent / "app"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

CODIGO_VALE_S = 5 * 60
CODIGO_TENTATIVAS = 5
BILHETE_VALE_S = 10 * 60
FATIA_MAX = 4 * 1024 * 1024
CORPO_MAX = 4096
FALHAS_MAX = 20                          # por IP, na janela abaixo
FALHAS_JANELA_S = 10 * 60
# Uma conexao lenta (ou um POST que promete corpo e nao manda) nao pode
# prender uma thread para sempre, nem abrir threads sem fim.
TIMEOUT_S = 15
CONEXOES_MAX = 32
VENCIDOS_MAX = 1000                      # bilhetes vencidos que ainda lembramos

ARQUIVO = None                           # os testes apontam para outro lugar

# Rotas estaticas: nome publico -> (arquivo, tipo). Nada de juntar a URL
# com uma pasta.
ESTATICOS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/manifest.webmanifest": ("manifest.webmanifest",
                              "application/manifest+json"),
    "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
    "/icone.svg": ("icone.svg", "image/svg+xml"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/vila.js": ("vila.js", "text/javascript; charset=utf-8"),
    "/comandos.js": ("comandos.js", "text/javascript; charset=utf-8"),
    "/decisoes.js": ("decisoes.js", "text/javascript; charset=utf-8"),
    "/orquestrador.js": ("orquestrador.js", "text/javascript; charset=utf-8"),
}


# ================================================================ config
def caminho() -> Path:
    return Path(ARQUIVO) if ARQUIVO else runtime_dir() / "app_celular.json"


_TRAVAS_THREADS: dict[str, threading.RLock] = {}
TRAVA_PRAZO_S = 15.0
_TRAVAS_GUARDA = threading.Lock()
_PROFUNDIDADE = threading.local()


@contextlib.contextmanager
def trava_arquivo(alvo: Path):
    """Uma escrita por vez — entre threads E entre processos.

    O servidor e o `--parear`/`--esquecer` sao processos diferentes: sem a
    trava de arquivo, o `--esquecer` podia ler, o servidor gravar um
    pareamento, e o `--esquecer` gravar por cima (o celular novo sumia).
    O `.lock` so guarda o byte trancado; o conteudo nao importa.

    Uma trava por ARQUIVO, e reentrante na mesma thread: a acao do app
    segura a sua e, dentro dela, grava o rastro, que pede a mesma. Travar
    o byte duas vezes no mesmo processo esperaria ~10 s e levantaria.
    """
    alvo = Path(alvo)
    chave = os.path.normcase(str(alvo.resolve()))
    with _TRAVAS_GUARDA:
        trava = _TRAVAS_THREADS.setdefault(chave, threading.RLock())
    profundidade = _PROFUNDIDADE.__dict__.setdefault("mapa", {})
    if not trava.acquire(timeout=TRAVA_PRAZO_S):
        raise OSError(f"trava ocupada ha mais de {TRAVA_PRAZO_S:.0f} s: {alvo.name}")
    try:
        if profundidade.get(chave):
            profundidade[chave] += 1
            try:
                yield
            finally:
                profundidade[chave] -= 1
            return
        profundidade[chave] = 1
        try:
            with _trava_de_arquivo(alvo):
                yield
        finally:
            profundidade.pop(chave, None)
    finally:
        trava.release()


@contextlib.contextmanager
def _trava_de_arquivo(alvo: Path):
    alvo.parent.mkdir(parents=True, exist_ok=True)
    with open(alvo, "a+b") as fh:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            # LK_LOCK tenta por ~10 s e entao levanta: melhor que esperar
            # para sempre um processo travado.
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:                                            # pragma: no cover
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _trava_config():
    return trava_arquivo(caminho().with_suffix(".lock"))


def ler_config() -> dict:
    try:
        with open(caminho(), encoding="utf-8") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        dados = {}
    dados.setdefault("porta", PORTA_PADRAO)
    dados.setdefault("aparelhos", [])
    dados.setdefault("pareamento", None)
    return dados


def gravar_config(dados: dict) -> None:
    alvo = caminho()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    temporario = alvo.with_suffix(".tmp")
    with open(temporario, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)
    os.replace(temporario, alvo)


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def novo_codigo(agora: float | None = None) -> str:
    """Gera e grava (so o hash) um codigo de pareamento. Devolve o codigo."""
    codigo = f"{secrets.randbelow(10**6):06d}"
    agora = time.time() if agora is None else agora
    with _trava_config():
        dados = ler_config()
        dados["pareamento"] = {"hash": _hash(codigo),
                               "expira": agora + CODIGO_VALE_S,
                               "tentativas": 0}
        gravar_config(dados)
    return codigo


def trocar_codigo(codigo: str, nome: str, agora: float | None = None) -> str | None:
    """Codigo certo e dentro do prazo -> token novo (e o codigo morre)."""
    agora = time.time() if agora is None else agora
    codigo = re.sub(r"\D", "", str(codigo or ""))
    with _trava_config():
        dados = ler_config()
        pedido = dados.get("pareamento")
        if not pedido or agora > float(pedido.get("expira", 0)):
            return None
        if not hmac.compare_digest(_hash(codigo), str(pedido.get("hash", ""))):
            pedido["tentativas"] = int(pedido.get("tentativas", 0)) + 1
            if pedido["tentativas"] >= CODIGO_TENTATIVAS:
                dados["pareamento"] = None
            gravar_config(dados)
            return None
        token = secrets.token_urlsafe(32)
        nome = re.sub(r"[^\w .-]", "", str(nome or ""))[:40] or "celular"
        dados["aparelhos"].append({
            "nome": nome, "hash": _hash(token),
            "criado": datetime.now().isoformat(timespec="seconds")})
        dados["pareamento"] = None
        gravar_config(dados)
    return token


def id_do_aparelho(aparelho: dict) -> str:
    """Id curto e estavel: o comeco do hash (o nome pode repetir)."""
    return str(aparelho.get("hash", ""))[:8]


def aparelhos() -> list[dict]:
    return [{"id": id_do_aparelho(a), "nome": a.get("nome", ""),
             "criado": a.get("criado", "")} for a in ler_config()["aparelhos"]]


def esquecer(id_curto: str) -> int:
    """Tira da lista o aparelho com esse id. Devolve quantos saíram."""
    id_curto = str(id_curto or "").strip().lower()
    if len(id_curto) < 8:
        return 0
    with _trava_config():
        dados = ler_config()
        antes = len(dados["aparelhos"])
        dados["aparelhos"] = [a for a in dados["aparelhos"]
                              if id_do_aparelho(a) != id_curto]
        if len(dados["aparelhos"]) != antes:
            gravar_config(dados)
    return antes - len(dados["aparelhos"])


def aparelho_existe(hash_token: str) -> bool:
    """O aparelho dono desse hash ainda esta pareado? (`--esquecer` o tira.)"""
    achado = False
    for aparelho in ler_config()["aparelhos"]:
        if hmac.compare_digest(hash_token, str(aparelho.get("hash", ""))):
            achado = True
    return achado


def aparelho_do_token(token: str) -> str | None:
    if not token:
        return None
    alvo = _hash(token)
    achado = None
    for aparelho in ler_config()["aparelhos"]:
        # sem sair no primeiro acerto: o tempo nao conta quantos existem
        if hmac.compare_digest(alvo, str(aparelho.get("hash", ""))):
            achado = aparelho.get("nome") or "celular"
    return achado


# ================================================================ rede
def _tailscale_exe() -> str | None:
    achado = shutil.which("tailscale")
    if achado:
        return achado
    padrao = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) \
        / "Tailscale" / "tailscale.exe"
    return str(padrao) if padrao.is_file() else None


def ip_do_tailscale(rodar=subprocess.run) -> str | None:
    """O IPv4 desta maquina na rede do Tailscale, ou None. Nunca outro."""
    exe = _tailscale_exe()
    if not exe:
        return None
    try:
        saida = rodar([exe, "ip", "-4"], capture_output=True, text=True,
                      timeout=15, creationflags=NO_WINDOW).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return None
    for linha in saida.splitlines():
        try:
            ip = ipaddress.ip_address(linha.strip())
        except ValueError:
            continue
        if ip in REDE_TAILSCALE:
            return str(ip)
    return None


def endereco_permitido(ip: str, local: bool) -> bool:
    try:
        endereco = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if local:
        return endereco.is_loopback
    return endereco in REDE_TAILSCALE


def porta_livre(host: str, porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sonda:
        try:
            sonda.bind((host, porta))
        except OSError:
            return False
    return True


def host_aceito(cabecalho: str, ip_servidor: str, local: bool) -> bool:
    nome = (cabecalho or "").strip().lower()
    nome = nome.rsplit(":", 1)[0] if nome.count(":") == 1 else nome
    if not nome:
        return False
    if nome == ip_servidor:
        return True
    if local and nome in ("localhost", "127.0.0.1"):
        return True
    maquina = socket.gethostname().lower()
    return nome == maquina or nome.endswith(".ts.net")


# ============================================================ servidor
class Estado:
    """O que o servidor guarda em memoria entre requisicoes."""

    def __init__(self, ip: str, local: bool, com_acoes: bool = False,
                 com_publicar: bool = False, com_perigosas: bool = False):
        self.ip = ip
        self.local = local
        # Fase 2: as acoes so existem quando o servidor sobe com --acoes.
        self.com_acoes = com_acoes
        # Publicar e uma chave a parte: da para ligar pausar/parar/gerar
        # enquanto o publicar amadurece.
        self.com_publicar = com_acoes and com_publicar
        # A zona de perigo (apagar, regenerar, mexer em conta) e uma chave a
        # parte: sem ela o catalogo nem mostra esses controles.
        self.com_perigosas = com_acoes and com_perigosas
        self.pendentes = acoes.Pendentes()
        self.trava = threading.Lock()
        # bilhete -> (caminho, expira, hash do token do aparelho)
        self.bilhetes: dict[str, tuple] = {}
        # Bilhetes que EXISTIRAM e venceram. O celular que deixa o video
        # parado 10 minutos e da play de novo nao esta chutando: sem esta
        # lembranca, ele contaria para o bloqueio.
        self.vencidos: dict[str, float] = {}
        self.falhas: dict[str, list] = {}        # ip -> [instantes]

    def _podar(self, agora: float) -> None:
        for chave, (_, expira, _dono) in list(self.bilhetes.items()):
            if expira <= agora:
                del self.bilhetes[chave]
                self.vencidos[chave] = expira
        if len(self.vencidos) > VENCIDOS_MAX:
            antigos = sorted(self.vencidos, key=self.vencidos.get)
            for chave in antigos[:len(self.vencidos) - VENCIDOS_MAX]:
                del self.vencidos[chave]

    def bilhete(self, arquivo: Path, dono: str) -> str:
        agora = time.time()
        with self.trava:
            self._podar(agora)
            chave = secrets.token_urlsafe(24)
            self.bilhetes[chave] = (arquivo, agora + BILHETE_VALE_S, dono)
        return chave

    def arquivo_do_bilhete(self, chave: str) -> tuple:
        """(caminho, motivo): motivo e "ok", "vencido", "revogado" ou "inventado".

        "revogado" e o bilhete de um aparelho que `--esquecer` tirou da
        lista: o `--esquecer` roda em outro processo, entao a conferencia e
        feita aqui, na hora do uso, contra o arquivo de config.
        """
        with self.trava:
            self._podar(time.time())
            achado = self.bilhetes.get(chave)
            vencido = chave in self.vencidos
        if achado is None:
            return (None, "vencido" if vencido else "inventado")
        if not aparelho_existe(achado[2]):
            return (None, "revogado")
        return (achado[0], "ok")

    def bloqueado(self, ip: str) -> bool:
        agora = time.time()
        with self.trava:
            recentes = [t for t in self.falhas.get(ip, [])
                        if agora - t < FALHAS_JANELA_S]
            self.falhas[ip] = recentes
            return len(recentes) >= FALHAS_MAX

    def falhou(self, ip: str) -> None:
        with self.trava:
            self.falhas.setdefault(ip, []).append(time.time())


def _inteiro(consulta: dict, chave: str, padrao: int) -> int:
    try:
        return int((consulta.get(chave) or [padrao])[0])
    except (TypeError, ValueError):
        return padrao


class Manipulador(BaseHTTPRequestHandler):
    server_version = "painel-celular"
    sys_version = ""
    estado: Estado                       # preenchido por `criar_servidor`
    timeout = TIMEOUT_S

    # ------------------------------------------------------------ saida
    # O log nunca repete o que veio do cliente alem de metodo e caminho
    # limpo: a linha de uma requisicao malformada pode carregar o bilhete do
    # video, e as mensagens de erro da classe base a incluem com %r.
    def _log(self, status) -> None:
        bruto = str(getattr(self, "path", "") or "")
        try:
            caminho = urlsplit(bruto).path
        except ValueError:
            caminho = "?"
        if "/v/" in bruto:
            caminho = "/v/…"
        metodo = str(getattr(self, "command", "") or "?")[:10]
        ip = self.client_address[0] if self.client_address else "?"
        sys.stderr.write(f"{datetime.now():%H:%M:%S} {ip} {metodo} "
                         f"{caminho[:80]} {status}\n")

    def log_request(self, code="-", size="-"):
        self._log(int(code) if str(code).isdigit() or hasattr(code, "value")
                  else "-")

    def log_error(self, formato, *args):
        self._log(args[0] if args and isinstance(args[0], int) else "erro")

    def log_message(self, formato, *args):
        self._log("-")

    def _cabecalhos_comuns(self, tipo: str, tamanho: int, cache: bool = False):
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(tamanho))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-cache" if cache else "no-store")

    def _json(self, dados, status: int = 200):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cabecalhos_comuns("application/json; charset=utf-8", len(corpo))
        self.end_headers()
        self.wfile.write(corpo)

    def _erro(self, status: int, motivo: str):
        self._json({"erro": motivo}, status)

    # --------------------------------------------------------- trancas
    def _passou_rede(self) -> bool:
        ip = self.client_address[0]
        if not endereco_permitido(ip, self.estado.local):
            self._erro(403, "fora da rede")
            return False
        if not host_aceito(self.headers.get("Host", ""), self.estado.ip,
                           self.estado.local):
            self._erro(421, "host desconhecido")
            return False
        return True

    def _barrar_chute(self) -> bool:
        """Conta uma tentativa errada; True (e 429) se ja houve demais.

        O bloqueio so pesa sobre quem NAO tem token valido. Atras do
        `tailscale serve` toda requisicao chega de 127.0.0.1: se o 429
        valesse para o IP inteiro, quem chutasse travaria tambem o celular
        pareado. `X-Forwarded-For` nao entra em conta — qualquer processo
        local o escreve. O chute do token nao preocupa (256 bits); o do
        codigo ja morre em 5 erros; o bloqueio e a terceira camada.
        """
        ip = self.client_address[0]
        if self.estado.bloqueado(ip):
            self._erro(429, "tentativas demais; espere alguns minutos")
            return True
        self.estado.falhou(ip)
        return False

    def _aparelho(self) -> str | None:
        bruto = self.headers.get("Authorization", "")
        token = bruto[7:].strip() if bruto.lower().startswith("bearer ") else ""
        aparelho = aparelho_do_token(token)
        if aparelho is None and not self._barrar_chute():
            self._erro(401, "nao pareado")
        self._dono = _hash(token) if aparelho is not None else ""
        self._id = self._dono[:8]
        return aparelho

    # ------------------------------------------------------------- GET
    def do_GET(self):
        if not self._passou_rede():
            return
        partes = urlsplit(self.path)
        rota, consulta = partes.path, parse_qs(partes.query)

        if rota in ESTATICOS:
            return self._estatico(*ESTATICOS[rota])
        if rota in ("/vilanova.png", "/vilanova-atlas.png",
                    "/vilanova-retrato.webp"):
            # Abertas como o resto da casca (a rede ja e a tranca): sao o
            # cenario, nao dado. O que esta NELAS nao diz nada do sistema.
            return self._imagem_da_vila(rota)
        if rota.startswith("/v/"):
            return self._video_por_bilhete(rota[3:])
        if not rota.startswith("/api/"):
            return self._erro(404, "nao existe")
        if self._aparelho() is None:
            return

        try:
            if rota == "/api/estado":
                return self._json(painel_dados.estado())
            if rota == "/api/diario":
                desde = (consulta.get("desde") or [""])[0][:40]
                fabrica = (consulta.get("fabrica") or [""])[0][:40] or None
                return self._json(painel_dados.diario(
                    desde, _inteiro(consulta, "n", 60), fabrica))
            if rota == "/api/vila":
                # o que a Vila mostra em texto: placar, travas e fabricas
                return self._json({"estado": vila_dados.estado()})
            if rota == "/api/vilanova":
                # O retrato e pedido a cada segundo: leve de proposito. O
                # placar e as travas continuam no /api/vila, mais devagar.
                saida = {"retrato": vila_nova.MOTOR.retrato()}
                if (consulta.get("mundo") or ["0"])[0] == "1":
                    saida["mundo"] = vila_nova.mundo()
                return self._json(saida)
            if rota == "/api/acoes":
                if not self.estado.com_acoes:
                    return self._json({"ligadas": False})
                try:
                    restantes = max(0, acoes.LIMITE_POR_HORA
                                    - acoes.usadas_na_ultima_hora(self._id))
                except acoes.Recusa:
                    restantes = None          # rastro ilegivel: a acao recusa
                return self._json({
                    "ligadas": True,
                    "publicar": self.estado.com_publicar,
                    "perigosas": self.estado.com_perigosas,
                    "alvos": acoes.alvos_de_pausa(),
                    "limite_por_hora": acoes.LIMITE_POR_HORA,
                    "restantes": restantes})
            if rota == "/api/catalogo":
                if not self.estado.com_acoes:
                    return self._json({"grupos": [], "acoes": []})
                return self._json(
                    comandos_app.catalogo(self.estado.com_perigosas))
            if rota == "/api/tarefas":
                return self._json({"tarefas": tarefas.listar(
                    _inteiro(consulta, "n", 20))})
            achado = re.fullmatch(r"/api/tarefa/([\w.-]{1,60})", rota)
            if achado:
                ficha = tarefas.uma(achado.group(1))
                if ficha is None:
                    return self._erro(404, "não achei essa tarefa")
                ficha["log"] = tarefas.log(achado.group(1),
                                           _inteiro(consulta, "desde", 0))
                return self._json(ficha)
            if rota == "/api/erros":
                return self._json(painel_dados.erros(_inteiro(consulta, "n", 10)))
            if rota == "/api/videos":
                return self._json(painel_dados.videos(_inteiro(consulta, "n", 40)))
            # O id tem `:` (historia_00017:celular:p06) e chega codificado.
            # Nao precisa ser validado aqui: ele so e COMPARADO com os ids
            # que o catalogo listou.
            achado = re.fullmatch(r"/api/video/(builds|historias)/([^/]{1,200})",
                                  rota)
            if achado:
                arquivo = painel_dados.arquivo_do_video(
                    achado.group(1), unquote(achado.group(2)))
                if arquivo is None:
                    return self._erro(404, "video nao encontrado")
                return self._json({"url": f"/v/{self.estado.bilhete(arquivo, self._dono)}",
                                   "vale_s": BILHETE_VALE_S})
            if rota == "/api/orquestrador":
                # A Mesa de comando: o que o orquestrador publicou, o uso, os
                # comandos e a situacao de cada um. So leitura, e limpo.
                return self._json(_limpo(orquestrador.para_o_app()))
            if rota == "/api/orquestrador/fluxo":
                return self._json(painel_dados.FLUXO.ler())
            if rota == "/api/decisoes":
                try:
                    return self._json(decisoes.para_o_app())
                except decisoes.Recusa as exc:
                    return self._erro(409, str(exc))
            # A MIDIA DE UMA DECISAO: pelo id do item e pelo indice, NUNCA
            # por caminho. O caminho so existe no registro; o celular recebe
            # um bilhete de 10 minutos para aquele arquivo e mais nada.
            achado = re.fullmatch(r"/api/decisao/([a-z0-9-]{1,60})/midia/(\d{1,3})",
                                  rota)
            if achado:
                ficha = decisoes.midia(achado.group(1), int(achado.group(2)))
                if ficha is None:
                    return self._erro(404, "mídia não existe mais")
                caminho, tipo = ficha
                return self._json({"url": f"/v/{self.estado.bilhete(caminho, self._dono)}",
                                   "tipo": tipo, "vale_s": BILHETE_VALE_S})
            achado = re.fullmatch(r"/api/relatorio/(\w{1,30})", rota)
            if achado:
                texto = painel_dados.relatorio(achado.group(1))
                if texto is None:
                    return self._erro(404, "relatorio desconhecido")
                return self._json({"texto": texto})
        except Exception as exc:                             # noqa: BLE001
            return self._erro(500, f"{type(exc).__name__}")
        return self._erro(404, "nao existe")

    # ------------------------------------------------------------ POST
    def _corpo(self) -> dict | None:
        """O JSON do POST, ou None (com a resposta de erro ja enviada)."""
        tipo = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if tipo != "application/json":
            self._erro(415, "envie application/json")
            return None
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            tamanho = -1
        if not 0 < tamanho <= CORPO_MAX:
            self._erro(413, "corpo invalido")
            return None
        try:
            corpo = json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            corpo = None
        if not isinstance(corpo, dict):
            self._erro(400, "json invalido")
            return None
        return corpo

    def do_POST(self):
        if not self._passou_rede():
            return
        rota = urlsplit(self.path).path
        if rota in ("/api/acao", "/api/acao/confirmar"):
            return self._acao(rota)
        if rota == "/api/decisao/responder":
            return self._responder_decisao()
        if rota in ("/api/orquestrador/comando", "/api/orquestrador/contestar"):
            return self._orquestrador(rota)
        if rota != "/api/parear":
            return self._erro(404, "nao existe")
        if self.estado.bloqueado(self.client_address[0]):
            return self._erro(429, "tentativas demais; espere alguns minutos")
        corpo = self._corpo()
        if corpo is None:
            return
        token = trocar_codigo(corpo.get("codigo", ""), corpo.get("nome", ""))
        if token is None:
            self.estado.falhou(self.client_address[0])
            return self._erro(403, "codigo errado ou vencido")
        return self._json({"token": token})

    # ---------------------------------------------------------- acoes
    def _acao(self, rota: str):
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as ações estão desligadas neste servidor")
        corpo = self._corpo()
        if corpo is None:
            return

        if rota == "/api/acao":
            nome = str(corpo.get("acao") or "")[:20]
            if nome == "publicar" and not self.estado.com_publicar:
                return self._erro(403, "publicar está desligado neste servidor")
            if (not self.estado.com_perigosas
                    and comandos_app.e_perigosa(nome, corpo.get("args") or {})):
                return self._erro(403, "a zona de perigo está desligada "
                                       "neste servidor")
            try:
                pedido = acoes.preparar(nome, corpo.get("args") or {}, self._id)
            except acoes.Recusa as exc:
                return self._erro(409, str(exc))
            if pedido["dois_passos"]:
                codigo = self.estado.pendentes.guardar(pedido, self._dono)
                return self._json({"confirmar": codigo, "texto": pedido["texto"],
                                   "vale_s": acoes.CONFIRMAR_VALE_S})
            return self._executar(pedido["acao"], pedido["args"])

        pedido, motivo = self.estado.pendentes.tirar(
            str(corpo.get("codigo") or "")[:64], self._dono)
        if motivo == "encerrado":
            # Toque duplo, ou o "sim" que chegou depois do prazo: do proprio
            # aparelho, nao e chute.
            return self._erro(410, "essa confirmação já foi usada ou venceu; "
                                   "peça de novo")
        if pedido is None:
            if not self._barrar_chute():
                self._erro(404, "confirmação desconhecida; peça de novo")
            return
        return self._executar(pedido["acao"], pedido["args"])

    def _executar(self, nome: str, args: dict):
        """O segundo passo: `acoes.confirmar`.

        Ela prepara DE NOVO dentro da trava, com os args congelados: em 60 s
        a grade pode ter publicado o mesmo video, e duas confirmacoes
        simultaneas (dois aparelhos, ou dois servidores) nao podem passar
        juntas pelas guardas.
        """
        try:
            ok, resultado = acoes.confirmar(nome, args, self._id)
        except acoes.Recusa as exc:
            return self._erro(409, str(exc))
        except OSError:
            return self._erro(503, "outra ação está em andamento; tente de novo")
        acoes.avisar_telegram(self._id, nome, resultado)
        if not ok:
            return self._erro(500, resultado)
        return self._json({"feito": True, "texto": resultado})

    def _responder_decisao(self):
        """A resposta dele a uma decisao: grava, recalcula a arvore, commita
        por caminho e avisa no Telegram.

        So com token. Nao depende de `--acoes`: responder nao executa nada
        na maquina, so registra o que ele decidiu.
        """
        if self._aparelho() is None:
            return
        corpo = self._corpo()
        if corpo is None:
            return
        item_id = str(corpo.get("id") or "")[:60]
        try:
            evento = decisoes.responder(item_id, str(corpo.get("opcao") or "")[:60],
                                        str(corpo.get("comentario") or ""),
                                        aparelho=self._id, origem="app")
        except KeyError:
            return self._erro(404, "decisão desconhecida")
        except decisoes.Recusa as exc:
            return self._erro(409, str(exc))
        except OSError:
            return self._erro(503, "as decisões estão ocupadas; tente de novo")
        acoes.avisar_texto(decisoes.texto_do_aviso(evento))
        return self._json({"feito": True, "evento": evento})

    def _orquestrador(self, rota: str):
        """Um comando para o orquestrador, ou "Contestar" uma decisao dele.

        So com token. Nao depende de `--acoes`: nada aqui executa na maquina.
        O comando fica PENDENTE ate o orquestrador aplicar (ou recusar); o
        Contestar vira no no Grimorio, com commit por caminho.
        """
        if self._aparelho() is None:
            return
        corpo = self._corpo()
        if corpo is None:
            return
        try:
            if rota == "/api/orquestrador/comando":
                nome = str(corpo.get("comando") or "")[:30]
                if nome not in orquestrador.DO_APP:
                    return self._erro(400, "comando desconhecido")
                linha = orquestrador.gravar_comando(nome, corpo.get("valor"), self._id)
                return self._json({"feito": True, "comando": linha})
            feito = orquestrador.contestar(str(corpo.get("id") or "")[:20],
                                           str(corpo.get("comentario") or ""), self._id)
        except orquestrador.Recusa as exc:
            return self._erro(409, str(exc))
        except OSError:
            return self._erro(503, "o orquestrador está ocupado; tente de novo")
        acoes.avisar_texto(f"⚔ Adrian contestou uma decisão do orquestrador: "
                           f"nó {feito['no']} no Grimório")
        return self._json({"feito": True, **feito})

    # ------------------------------------------------------- arquivos
    def _imagem_da_vila(self, rota: str):
        """O fundo da Vila (dia/noite) e o atlas dos personagens.

        As duas sao compostas uma vez e guardadas em memoria; o `?v=` na URL
        (a versao vem no `/api/vilanova`) e o que deixa o app guarda-las por
        um dia sem ficar preso a uma arte velha.
        """
        consulta = parse_qs(urlsplit(self.path).query or "")
        noite = (consulta.get("noite") or ["0"])[0] == "1"
        tipo = "image/png"
        try:
            if rota == "/vilanova.png":
                corpo = vila_nova.png_do_fundo(noite)
            elif rota == "/vilanova-retrato.webp":
                corpo = vila_nova.imagem_do_retrato(noite)
                tipo = "image/webp"
            else:
                # so a escala do celular ou a de 1x: nada de o pedido
                # escolher um tamanho qualquer e fazer o PC desenhar
                escala = (vila_nova.ESCALA_CELULAR
                          if (consulta.get("escala") or ["1"])[0]
                          == str(vila_nova.ESCALA_CELULAR) else 1)
                corpo = vila_nova.atlas(escala)["png"]
        except Exception:                                    # noqa: BLE001
            return self._erro(404, "a vila ainda nao tem cenario")
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "private, max-age=86400")
        self.end_headers()
        self.wfile.write(corpo)

    def _estatico(self, nome: str, tipo: str):
        try:
            corpo = (APP / nome).read_bytes()
        except OSError:
            return self._erro(404, "nao existe")
        self.send_response(200)
        self._cabecalhos_comuns(tipo, len(corpo), cache=True)
        if nome.endswith(".html"):
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self'; media-src 'self'; "
                "style-src 'self'; script-src 'self'; connect-src 'self'; "
                "manifest-src 'self'; worker-src 'self'; base-uri 'none'; "
                "form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(corpo)

    def _video_por_bilhete(self, chave: str):
        arquivo, motivo = self.estado.arquivo_do_bilhete(chave)
        if motivo == "vencido":
            return self._erro(410, "bilhete vencido; abra o video de novo")
        if motivo == "revogado":
            return self._erro(403, "aparelho esquecido")
        if arquivo is None:
            if not self._barrar_chute():
                self._erro(404, "bilhete desconhecido")
            return
        try:
            total = arquivo.stat().st_size
        except OSError:
            return self._erro(404, "arquivo sumiu")
        # O tipo vem da extensao (as decisoes trazem imagem e webm alem do
        # mp4). Imagem pedida sem Range por um `<img>` recebe o arquivo
        # inteiro com 200: um 206 que ninguem pediu nao e garantido de
        # aparecer. Video segue sempre por Range, como antes.
        tipo = decisoes.tipo_da_midia(arquivo) or "video/mp4"
        if (tipo.startswith("image/") and not self.headers.get("Range")
                and total <= FATIA_MAX):
            try:
                corpo = arquivo.read_bytes()
            except OSError:
                return self._erro(404, "arquivo sumiu")
            self.send_response(200)
            self._cabecalhos_comuns(tipo, len(corpo))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with contextlib.suppress(ConnectionError, OSError):
                self.wfile.write(corpo)
            return
        inicio, fim = intervalo(self.headers.get("Range", ""), total)
        if inicio is None:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{total}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        tamanho = fim - inicio + 1
        self.send_response(206)
        self._cabecalhos_comuns(tipo, tamanho)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {inicio}-{fim}/{total}")
        self.end_headers()
        try:
            with open(arquivo, "rb") as fh:
                fh.seek(inicio)
                falta = tamanho
                while falta > 0:
                    pedaco = fh.read(min(65536, falta))
                    if not pedaco:
                        break
                    self.wfile.write(pedaco)
                    falta -= len(pedaco)
        except (ConnectionError, OSError):
            pass          # o celular fechou o video no meio: normal


def _limpo(dados):
    """Todo texto que vai ao celular passa pelo filtro (links, chaves, usuario)."""
    if isinstance(dados, str):
        return painel_dados.limpar(dados)
    if isinstance(dados, list):
        return [_limpo(d) for d in dados]
    if isinstance(dados, dict):
        return {k: _limpo(v) for k, v in dados.items()}
    return dados


def intervalo(cabecalho: str, total: int) -> tuple:
    """(inicio, fim) inclusivos, com no maximo FATIA_MAX bytes.

    Sem Range, a resposta e o comeco do arquivo — o navegador pede o resto.
    (None, None) quando o pedido nao cabe no arquivo (416).
    """
    if total <= 0:
        return (None, None)
    # No maximo 18 digitos: numero maior nem cabe num arquivo, e `int()` de
    # mais de 4300 digitos levanta ValueError no Python 3.11+.
    achado = re.fullmatch(r"\s*bytes=(\d{0,18})-(\d{0,18})\s*", cabecalho or "")
    if not cabecalho:
        inicio, fim = 0, total - 1
    elif not achado or (not achado.group(1) and not achado.group(2)):
        return (None, None)
    elif not achado.group(1):                     # bytes=-500: os ultimos 500
        inicio = max(0, total - int(achado.group(2)))
        fim = total - 1
    else:
        inicio = int(achado.group(1))
        fim = int(achado.group(2)) if achado.group(2) else total - 1
    if inicio >= total or fim < inicio:
        return (None, None)
    fim = min(fim, total - 1, inicio + FATIA_MAX - 1)
    return (inicio, fim)


class Servidor(ThreadingHTTPServer):
    """ThreadingHTTPServer com teto de conexoes simultaneas.

    Passou do teto, a conexao e fechada na hora (sem thread). O celular
    abre poucas; mais que isso e defeito ou abuso.
    """
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        self.vagas = threading.BoundedSemaphore(CONEXOES_MAX)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self.vagas.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.vagas.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.vagas.release()


def criar_servidor(host: str, porta: int, local: bool,
                   com_acoes: bool = False, com_publicar: bool = False,
                   com_perigosas: bool = False) -> ThreadingHTTPServer:
    if not endereco_permitido(host, local):
        raise ValueError(f"endereco recusado: {host}")
    if porta in PORTAS_PROIBIDAS:
        raise ValueError(f"a porta {porta} e do login do YouTube")

    class _Manipulador(Manipulador):
        estado = Estado(host, local, com_acoes, com_publicar, com_perigosas)

    return Servidor((host, porta), _Manipulador)


def _gerar_acessos(com_acoes: bool, com_publicar: bool, com_perigosas: bool) -> None:
    try:
        orquestrador.gerar_acessos({"acoes": com_acoes,
                                    "publicar": com_acoes and com_publicar,
                                    "perigosas": com_acoes and com_perigosas})
    except Exception as exc:                                 # noqa: BLE001
        sys.stderr.write(f"acessos.json: {type(exc).__name__}: {exc}\n")


# ================================================================= CLI
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m remoto.api_http")
    parser.add_argument("--publicar", action="store_true",
                        help="com --acoes, liga tambem o botao de publicar")
    parser.add_argument("--perigosas", action="store_true",
                        help="com --acoes, liga a zona de perigo (apagar, "
                             "regenerar, mexer em conta)")
    parser.add_argument("--confirmo", action="store_true",
                        help="com --liberar: solta de verdade (sem ele, so mostra)")
    parser.add_argument("--acoes", action="store_true",
                        help="liga a fase 2 (pausar, parar, gerar, publicar)")
    parser.add_argument("--local", action="store_true",
                        help="escuta em 127.0.0.1 (teste, ou atras de `tailscale serve`)")
    parser.add_argument("--porta", type=int, default=None)
    parser.add_argument("--parear", action="store_true")
    parser.add_argument("--aparelhos", action="store_true")
    parser.add_argument("--esquecer", metavar="ID",
                        help="o id de 8 letras que --aparelhos mostra")
    parser.add_argument("--em-voo", action="store_true",
                        help="publicações do app sem desfecho (bloqueadas)")
    parser.add_argument("--liberar", metavar="VIDEO_ID",
                        help="solta um vídeo do em-voo, DEPOIS de conferir no perfil")
    parser.add_argument("--soltar-marca", metavar="VIDEO_ID",
                        help="tira a marca “a conferir” que o APP pôs no TikTok, "
                             "depois de conferir no perfil")
    args = parser.parse_args(argv)

    if args.soltar_marca:
        for linha in acoes.relatorio_do_video(args.soltar_marca) or ["nada registrado"]:
            print(linha)
        if not args.confirmo:
            print("\nConfira no perfil do TikTok (tiktok.com/@…) e no ledger acima "
                  "se o vídeo está ou não no ar. Para tirar a marca do app: repita "
                  "com --confirmo. Se ele ESTÁ no ar e o ledger não diz, não tire "
                  "a marca: ela é o que impede a grade de repostar.")
            return 0
        try:
            saiu = acoes.soltar_marca(args.soltar_marca)
        except OSError as exc:
            print(f"não consegui agora: {exc}. Tente de novo em instantes.")
            return 3
        except acoes.Recusa as exc:
            print(str(exc))
            return 1
        print("marca do app retirada" if saiu else "esse vídeo não tem marca")
        return 0 if saiu else 1

    if args.em_voo:
        try:
            voando = acoes.em_voo()
        except acoes.Recusa as exc:
            print(str(exc))
            return 1
        for chave, item in voando.items():
            print(f"{item.get('id')}  {item.get('onde')}  desde {item.get('desde')}"
                  f"  (aparelho {item.get('aparelho')})")
        if not voando:
            print("nada em voo")
        return 0
    if args.liberar:
        for linha in acoes.relatorio_do_video(args.liberar) or ["nada registrado"]:
            print(linha)
        if not args.confirmo:
            print("\nConfira no YouTube Studio / perfil do TikTok. Para soltar do "
                  "app: repita com --confirmo. A marca “a conferir” do TikTok "
                  "NÃO sai por aqui.")
            return 0
        try:
            saiu = acoes.liberar(args.liberar)
        except OSError as exc:
            print(f"não consegui soltar agora: {exc}. Tente de novo em instantes.")
            return 3
        except acoes.Recusa as exc:
            print(str(exc))
            return 1
        print(f"liberados: {saiu}" if saiu else "esse vídeo não está em voo")
        return 0 if saiu else 1

    if args.parear:
        codigo = novo_codigo()
        print(f"Código: {codigo[:3]} {codigo[3:]}  (vale 5 minutos, uma vez)")
        print("No app, toque em Parear e digite o código.")
        return 0
    if args.aparelhos:
        lista = aparelhos()
        for aparelho in lista:
            print(f"{aparelho['id']}  {aparelho['nome']}  desde {aparelho['criado']}")
        if not lista:
            print("nenhum aparelho pareado")
        return 0
    if args.esquecer:
        saiu = esquecer(args.esquecer)
        print(f"removidos: {saiu}" if saiu else
              "nenhum aparelho com esse id (veja --aparelhos)")
        return 0 if saiu else 1

    porta = args.porta or int(ler_config()["porta"])
    host = "127.0.0.1" if args.local else ip_do_tailscale()
    if host is None:
        print("Tailscale sem IP (deslogado ou desligado). Não subo em outro "
              "endereço. Faça login no Tailscale e tente de novo.",
              file=sys.stderr)
        return 2
    if not porta_livre(host, porta):
        print(f"A porta {porta} já está em uso em {host}. Use --porta.",
              file=sys.stderr)
        return 3
    try:
        servidor = criar_servidor(host, porta, args.local, args.acoes,
                                  args.publicar, args.perigosas)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    print(f"App do celular em http://{host}:{porta}/  (Ctrl+C para parar)"
          f"  — ações {'LIGADAS' if args.acoes else 'desligadas'}"
          f"{' (com publicar)' if args.acoes and args.publicar else ''}"
          f"{' (com a zona de perigo)' if args.acoes and args.perigosas else ''}")
    # Sempre, mesmo sem --acoes: uma publicacao que ficou pela metade precisa
    # ser concluida (marca e em-voo) mesmo que o botao esteja desligado.
    voltando = acoes.conciliar()
    if voltando:
        print(f"retomei a vigia de {len(voltando)} publicação(ões) do app")
    with contextlib.suppress(acoes.Recusa):
        presos = [v for v in acoes.em_voo().values() if v.get("estado") != "em_andamento"]
        if presos:
            print(f"ATENÇÃO: {len(presos)} publicação(ões) do app esperando conferência "
                  "(veja --em-voo); o destino delas segue bloqueado no app.")
    if not ler_config()["aparelhos"]:
        print("Nenhum celular pareado: rode `python -m remoto.api_http --parear`.")
    # A Mesa de comando: a sonda de uso (a cada `sonda_min` do config.json do
    # orquestrador; 0 desliga) e o acessos.json com as chaves DESTE servidor.
    orquestrador.SONDA.iniciar()
    threading.Thread(target=_gerar_acessos, args=(args.acoes, args.publicar,
                                                  args.perigosas),
                     name="acessos", daemon=True).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
