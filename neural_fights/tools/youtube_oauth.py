#!/usr/bin/env python3
"""Obtém o ``refresh_token`` do YouTube e grava o arquivo de credenciais.

A fonte de chat (``live/sources/youtube.py``) precisa de três campos no
``youtube_credentials.json`` do diretório de runtime: ``client_id``,
``client_secret`` e ``refresh_token``. Os dois primeiros saem do Google
Cloud Console; o terceiro exige o fluxo de consentimento OAuth — que esta
ferramenta executa uma única vez, com loopback local e ``urllib`` puro
(mesma regra da fonte: nenhuma dependência nova).

Uso:
    python -m neural_fights.tools.youtube_oauth \
        --client-id SEU_ID --client-secret SEU_SECRET

Abre o navegador no consentimento do Google; ao autorizar, o código volta
no loopback, é trocado pelo refresh_token e o arquivo é gravado no
diretório de runtime (nunca no pacote nem no git — o .gitignore já o
protege).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from neural_fights.utils.console import SafeArgumentParser, safe_print

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ESCOPO = "https://www.googleapis.com/auth/youtube.readonly"
# Publicar exige escrita. Pedir os DOIS de uma vez mantem o mesmo arquivo de
# credenciais servindo a live (le o chat) e a publicacao (sobe o video): um
# token so de upload quebraria a live, e vice-versa.
ESCOPO_UPLOAD = "https://www.googleapis.com/auth/youtube.upload"
ESCOPO_COMPLETO = f"{ESCOPO} {ESCOPO_UPLOAD}"
# Retencao por segundo (curva de audiencia) vive em OUTRA API, com escopo
# proprio. Sem ele o `main.py metricas` mostra so views/likes.
ESCOPO_ANALYTICS = "https://www.googleapis.com/auth/yt-analytics.readonly"


def escopos(com_upload: bool, com_analytics: bool = False) -> str:
    partes = [ESCOPO]
    if com_upload:
        partes.append(ESCOPO_UPLOAD)
    if com_analytics:
        partes.append(ESCOPO_ANALYTICS)
    return " ".join(partes)


def _caminho_padrao() -> Path:
    from neural_fights.data.database import RUNTIME_DIR

    return Path(RUNTIME_DIR) / "youtube_credentials.json"


def _receber_codigo(porta: int) -> str:
    """Servidor de um tiro só: espera o redirect com ?code=..."""
    codigo: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (nome da stdlib)
            params = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if "code" in params:
                codigo["code"] = params["code"][0]
                self.wfile.write(
                    "<h2>Autorizado. Pode voltar para o terminal.</h2>".encode()
                )
            else:
                self.wfile.write(
                    "<h2>Sem codigo na resposta - tente de novo.</h2>".encode()
                )

        def log_message(self, *args):  # silencioso
            return

    with HTTPServer(("127.0.0.1", porta), Handler) as servidor:
        while "code" not in codigo:
            servidor.handle_request()
    return codigo["code"]


def build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(
        description="Fluxo OAuth unico do YouTube (gera o refresh_token)"
    )
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    parser.add_argument("--porta", type=int, default=8765)
    parser.add_argument(
        "--out",
        help="destino do JSON (padrao: youtube_credentials.json no runtime)",
    )
    parser.add_argument(
        "--com-upload",
        action="store_true",
        help="pede tambem o escopo de UPLOAD (publicar video), alem da "
             "leitura do chat. Necessario uma unica vez, antes de publicar.",
    )
    parser.add_argument(
        "--com-analytics",
        action="store_true",
        help="pede tambem o escopo do YouTube Analytics (curva de retencao "
             "para `random_builds/main.py metricas`).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    redirect = f"http://localhost:{args.porta}"

    url = AUTH_URL + "?" + urllib.parse.urlencode(
        {
            "client_id": args.client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": escopos(args.com_upload, getattr(args, "com_analytics", False)),
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    safe_print("Abrindo o navegador para o consentimento do Google...")
    safe_print(f"(se nao abrir sozinho, visite: {url})")
    webbrowser.open(url)

    codigo = _receber_codigo(args.porta)
    safe_print("Codigo recebido; trocando pelo refresh_token...")

    corpo = urllib.parse.urlencode(
        {
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "code": codigo,
            "grant_type": "authorization_code",
            "redirect_uri": redirect,
        }
    ).encode()
    req = urllib.request.Request(TOKEN_URL, data=corpo, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as resp:
        dados = json.loads(resp.read().decode("utf-8"))

    refresh = dados.get("refresh_token")
    if not refresh:
        safe_print(
            "Google nao devolveu refresh_token (conta ja consentida sem "
            "prompt=consent?). Revogue o acesso em myaccount.google.com/"
            "permissions e rode de novo."
        )
        return 1

    destino = Path(args.out) if args.out else _caminho_padrao()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(
            {
                "client_id": args.client_id,
                "client_secret": args.client_secret,
                "refresh_token": refresh,
                # Fica gravado o que este token PODE fazer: quem for publicar
                # confere aqui em vez de descobrir com um 403 no meio do
                # upload de 30 MB.
                "escopo": escopos(args.com_upload,
                                  getattr(args, "com_analytics", False)),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    safe_print(f"Credenciais gravadas em: {destino}")
    if args.com_upload:
        safe_print("Escopo com UPLOAD: da para publicar pelo painel.")
    safe_print("Pronto: neural-fights-live --source youtube")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
