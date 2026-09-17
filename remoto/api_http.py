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
  4. rotas: tabela FECHADA, nenhuma recebe texto para executar. Nesta fase
     todas sao de LEITURA.

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

from . import painel_dados
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
}


# ================================================================ config
def caminho() -> Path:
    return Path(ARQUIVO) if ARQUIVO else runtime_dir() / "app_celular.json"


_TRAVA_CONFIG = threading.Lock()


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
    with _TRAVA_CONFIG:
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
    with _TRAVA_CONFIG:
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

    def __init__(self, ip: str, local: bool):
        self.ip = ip
        self.local = local
        self.trava = threading.Lock()
        self.bilhetes: dict[str, tuple] = {}     # bilhete -> (caminho, expira)
        self.falhas: dict[str, list] = {}        # ip -> [instantes]

    def bilhete(self, arquivo: Path) -> str:
        agora = time.time()
        with self.trava:
            self.bilhetes = {k: v for k, v in self.bilhetes.items()
                             if v[1] > agora}
            chave = secrets.token_urlsafe(24)
            self.bilhetes[chave] = (arquivo, agora + BILHETE_VALE_S)
        return chave

    def arquivo_do_bilhete(self, chave: str) -> Path | None:
        with self.trava:
            achado = self.bilhetes.get(chave)
        if not achado or achado[1] < time.time():
            return None
        return achado[0]

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

    # ------------------------------------------------------------ saida
    def log_message(self, formato, *args):
        # So metodo e caminho SEM consulta, e nunca o bilhete do video.
        caminho = urlsplit(self.path).path
        if caminho.startswith("/v/"):
            caminho = "/v/…"
        sys.stderr.write(f"{datetime.now():%H:%M:%S} {self.client_address[0]} "
                         f"{self.command} {caminho} {args[1] if len(args) > 1 else ''}\n")

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
        if self.estado.bloqueado(ip):
            self._erro(429, "tentativas demais; espere alguns minutos")
            return False
        return True

    def _aparelho(self) -> str | None:
        bruto = self.headers.get("Authorization", "")
        token = bruto[7:].strip() if bruto.lower().startswith("bearer ") else ""
        aparelho = aparelho_do_token(token)
        if aparelho is None:
            self.estado.falhou(self.client_address[0])
            self._erro(401, "nao pareado")
        return aparelho

    # ------------------------------------------------------------- GET
    def do_GET(self):
        if not self._passou_rede():
            return
        partes = urlsplit(self.path)
        rota, consulta = partes.path, parse_qs(partes.query)

        if rota in ESTATICOS:
            return self._estatico(*ESTATICOS[rota])
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
                return self._json(painel_dados.diario(
                    desde, _inteiro(consulta, "n", 60)))
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
                return self._json({"url": f"/v/{self.estado.bilhete(arquivo)}",
                                   "vale_s": BILHETE_VALE_S})
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
    def do_POST(self):
        if not self._passou_rede():
            return
        rota = urlsplit(self.path).path
        if rota != "/api/parear":
            return self._erro(404, "nao existe")
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            tamanho = -1
        if not 0 < tamanho <= CORPO_MAX:
            return self._erro(413, "corpo invalido")
        try:
            corpo = json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self._erro(400, "json invalido")
        if not isinstance(corpo, dict):
            return self._erro(400, "json invalido")
        token = trocar_codigo(corpo.get("codigo", ""), corpo.get("nome", ""))
        if token is None:
            self.estado.falhou(self.client_address[0])
            return self._erro(403, "codigo errado ou vencido")
        return self._json({"token": token})

    # ------------------------------------------------------- arquivos
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
                "default-src 'self'; img-src 'self' data:; media-src 'self'; "
                "style-src 'self' 'unsafe-inline'; script-src 'self' "
                "'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(corpo)

    def _video_por_bilhete(self, chave: str):
        arquivo = self.estado.arquivo_do_bilhete(chave)
        if arquivo is None:
            return self._erro(404, "bilhete vencido")
        try:
            total = arquivo.stat().st_size
        except OSError:
            return self._erro(404, "arquivo sumiu")
        inicio, fim = intervalo(self.headers.get("Range", ""), total)
        if inicio is None:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{total}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        tamanho = fim - inicio + 1
        self.send_response(206)
        self._cabecalhos_comuns("video/mp4", tamanho)
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


def intervalo(cabecalho: str, total: int) -> tuple:
    """(inicio, fim) inclusivos, com no maximo FATIA_MAX bytes.

    Sem Range, a resposta e o comeco do arquivo — o navegador pede o resto.
    (None, None) quando o pedido nao cabe no arquivo (416).
    """
    if total <= 0:
        return (None, None)
    achado = re.fullmatch(r"\s*bytes=(\d*)-(\d*)\s*", cabecalho or "")
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


def criar_servidor(host: str, porta: int, local: bool) -> ThreadingHTTPServer:
    if not endereco_permitido(host, local):
        raise ValueError(f"endereco recusado: {host}")
    if porta in PORTAS_PROIBIDAS:
        raise ValueError(f"a porta {porta} e do login do YouTube")

    class _Manipulador(Manipulador):
        estado = Estado(host, local)

    servidor = ThreadingHTTPServer((host, porta), _Manipulador)
    servidor.daemon_threads = True
    return servidor


# ================================================================= CLI
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m remoto.api_http")
    parser.add_argument("--local", action="store_true",
                        help="escuta em 127.0.0.1 (teste, ou atras de `tailscale serve`)")
    parser.add_argument("--porta", type=int, default=None)
    parser.add_argument("--parear", action="store_true")
    parser.add_argument("--aparelhos", action="store_true")
    parser.add_argument("--esquecer", metavar="NOME")
    args = parser.parse_args(argv)

    if args.parear:
        codigo = novo_codigo()
        print(f"Código: {codigo[:3]} {codigo[3:]}  (vale 5 minutos, uma vez)")
        print("No app, toque em Parear e digite o código.")
        return 0
    if args.aparelhos:
        for aparelho in ler_config()["aparelhos"]:
            print(f"{aparelho.get('nome')}  desde {aparelho.get('criado')}")
        return 0
    if args.esquecer:
        with _TRAVA_CONFIG:
            dados = ler_config()
            antes = len(dados["aparelhos"])
            dados["aparelhos"] = [a for a in dados["aparelhos"]
                                  if a.get("nome") != args.esquecer]
            gravar_config(dados)
        print(f"removidos: {antes - len(dados['aparelhos'])}")
        return 0

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
        servidor = criar_servidor(host, porta, args.local)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    print(f"App do celular em http://{host}:{porta}/  (Ctrl+C para parar)")
    if not ler_config()["aparelhos"]:
        print("Nenhum celular pareado: rode `python -m remoto.api_http --parear`.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
