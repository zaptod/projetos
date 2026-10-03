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
import base64
import contextlib
import hashlib
import hmac
import ipaddress
import io
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

from PIL import Image

from . import (acoes, biblioteca, claude_estado, comandos_app, decisoes, delegar, orquestrador,
               painel_dados, tarefas, vila_dados, vila_nova)
from .config import runtime_dir
from esteira_sprites import aprovar as sprites_aprovar
from esteira_sprites import config as sprites_config
from esteira_sprites import juiz as sprites_juiz
from painel.sprites import importar as sprites_importar

PORTA_PADRAO = 8931
PORTAS_PROIBIDAS = {8765}                # OAuth do YouTube
REDE_TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
APP = Path(__file__).resolve().parent / "app"
PASTA_ARENA = None                    # os testes apontam para outro lugar
ID_DE_LUTA = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,59}")   # a lista e a rota do video, iguais
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

CODIGO_VALE_S = 5 * 60
CODIGO_TENTATIVAS = 5
BILHETE_VALE_S = 10 * 60
FATIA_MAX = 4 * 1024 * 1024
IMAGEM_INTEIRA_MAX = 24 * 1024 * 1024
CORPO_MAX = 4096
# A conversa com uma IA leva imagem anexada (base64): so essa rota aceita
# um corpo grande, e so com token.
CORPO_CORREIO_MAX = 12 * 1024 * 1024
ATELIE_MAX = sprites_importar.MAX_BYTES
ATELIE_BIBLIOTECA = Path(__file__).resolve().parents[1] / "palco" / "biblioteca" / "sprites_usuario"
IAS_DE_CONVERSA = ("deepseek", "chatgpt", "gemini", "grok")
# As caixas do correio (29/09, tarde: pedidos de imagem). Texto fixo aqui,
# e nao lido do `ias`, para a rota nunca aceitar o que o correio nao conhece;
# `test_imagem_app` confere que as duas listas batem.
CAIXAS_DO_CORREIO = ("deepseek", "chatgpt", "gemini", "grok", "picasso", "dreamface",
                     "digen", "livre")
GERADORES_DE_IMAGEM = ("picasso", "grok", "gemini", "chatgpt", "dreamface", "digen")
CAIXAS_RE = "|".join(CAIXAS_DO_CORREIO)
GERADORES_RE = "|".join(GERADORES_DE_IMAGEM)
CORPO_PEDIDO_IMAGEM_MAX = 32 * 1024
FALHAS_MAX = 20                          # por IP, na janela abaixo
FALHAS_JANELA_S = 10 * 60
# Uma conexao lenta (ou um POST que promete corpo e nao manda) nao pode
# prender uma thread para sempre, nem abrir threads sem fim.
TIMEOUT_S = 15
CONEXOES_MAX = 32
VENCIDOS_MAX = 1000                      # bilhetes vencidos que ainda lembramos

ARQUIVO = None                           # os testes apontam para outro lugar

# A esteira ainda escolhe o perfil por modulo. As chamadas do celular podem
# chegar em threads diferentes, entao a troca fica inteira dentro desta trava.
_TRAVA_SPRITES = threading.Lock()
_SPRITES_ARQUIVOS = {
    "limpo.png": ("limpo", "image/png"),
    "previa.gif": ("previa_gif", "image/gif"),
    "previa.webp": ("previa_webp", "image/webp"),
    "tamanho_real.png": ("tamanho_real", "image/png"),
    "para_juiz.png": ("para_juiz", "image/png"),
}
_SPRITES_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")


def _ficha_sprite(perfil: str, item_id: str) -> dict | None:
    """Le uma ficha sem mudar o perfil global da esteira."""
    if perfil not in sprites_config.PERFIS or not _SPRITES_ID_RE.fullmatch(item_id):
        return None
    subpasta = sprites_config.PERFIS[perfil].subpasta
    caminho_ficha = sprites_config.RAIZ / subpasta / item_id / "ficha.json"
    try:
        dados = json.loads(caminho_ficha.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) and dados.get("item_id") == item_id else None


def _arquivo_sprite(dados: dict, nome: str) -> Path | None:
    chave_tipo = _SPRITES_ARQUIVOS.get(nome)
    if chave_tipo is None:
        return None
    perfil, item_id = dados.get("perfil"), dados.get("item_id")
    if nome in ("tamanho_real.png", "para_juiz.png") and perfil in sprites_config.PERFIS:
        subpasta = sprites_config.PERFIS[perfil].subpasta
        arquivo = sprites_config.RAIZ / subpasta / str(item_id) / nome
        return arquivo if arquivo.is_file() else None
    tentativa = (dados.get("tentativas") or [{}])[-1]
    caminhos = tentativa.get("caminhos") if isinstance(tentativa, dict) else None
    caminho = caminhos.get(chave_tipo[0]) if isinstance(caminhos, dict) else None
    try:
        arquivo = Path(caminho)
    except TypeError:
        return None
    return arquivo if arquivo.name == nome and arquivo.is_file() else None


def sprites_a_conferir() -> list[dict]:
    """Resumo publico ao celular; nunca devolve caminhos do PC."""
    saida = []
    for perfil, definicao in sprites_config.PERFIS.items():
        pasta = sprites_config.RAIZ / definicao.subpasta
        try:
            fichas = list(pasta.glob("*/ficha.json"))
        except OSError:
            continue
        for caminho_ficha in fichas:
            try:
                dados = json.loads(caminho_ficha.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            item_id = str(dados.get("item_id") or "")
            if (dados.get("estado") != "a_conferir" or not _SPRITES_ID_RE.fullmatch(item_id)
                    or dados.get("perfil") != perfil):
                continue
            tentativa = (dados.get("tentativas") or [{}])[-1]
            urls = {}
            for nome in _SPRITES_ARQUIVOS:
                if _arquivo_sprite(dados, nome) is not None:
                    urls[nome] = f"/api/sprites/arquivo/{perfil}/{item_id}/{nome}"
            item = dados.get("item") if isinstance(dados.get("item"), dict) else {}
            saida.append({"perfil": perfil, "id": item_id,
                          "descricao": item.get("descricao") or item_id,
                          "tentativas": sprites_juiz.tentativas_contadas(dados),
                          "veredito": tentativa.get("veredito") if isinstance(tentativa, dict) else None,
                          "portao_reprovou": tentativa.get("portao_reprovou") if isinstance(tentativa, dict) else [],
                          "imagens": urls, "limpo_url": urls.get("limpo.png"),
                          "previa_url": urls.get("previa.gif") or urls.get("previa.webp"),
                          "tamanho_real_url": urls.get("tamanho_real.png")})
    return sorted(saida, key=lambda d: (d["perfil"], d["id"]))


def pasta_da_arena() -> Path:
    """A Arena fica nos outputs do palco, separada das tarefas do app."""
    if PASTA_ARENA:
        return Path(PASTA_ARENA)
    return Path(__file__).resolve().parents[1] / "random_builds" / "outputs" / "_palco" / "arena"


def opcoes_da_arena() -> dict:
    """Catalogo pequeno, so com os campos que a tela precisa para montar a luta."""
    from neural_fights.core.arena import LISTA_MAPAS, get_mapa_info
    from neural_fights.data.database import carregar_armas, carregar_personagens
    from neural_fights.utils.palette import cor_classe, rgb_to_hex

    armas = {arma.nome: arma for arma in carregar_armas()}
    personagens = []
    for personagem in carregar_personagens():
        arma = armas.get(personagem.nome_arma)
        personagens.append({"nome": personagem.nome, "classe": personagem.classe,
                            "cor_classe": rgb_to_hex(cor_classe(personagem.classe)),
                            "arma": personagem.nome_arma,
                            "tipo_arma": getattr(arma, "tipo", "")})
    mapas = [{"id": nome, **get_mapa_info(nome)} for nome in LISTA_MAPAS]
    return {"personagens": sorted(personagens, key=lambda p: p["nome"].casefold()), "mapas": mapas}


def _ler_json(caminho: Path) -> dict:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def lutas_da_arena(n: int = 20) -> list[dict]:
    """As ultimas lutas, com a situacao da tarefa que realmente as produziu."""
    try:
        # so o que a rota do video aceita (02/10: uma pasta "_prova" aparecia na
        # lista e o video dela caia no 401)
        pastas = sorted((p for p in pasta_da_arena().iterdir()
                         if p.is_dir() and ID_DE_LUTA.fullmatch(p.name)), reverse=True)
    except OSError:
        return []
    saida = []
    for pasta in pastas[:max(1, min(n, 20))]:
        ficha = _ler_json(pasta / "luta.json")
        if not ficha:
            continue
        tarefa = tarefas.uma(str(ficha.get("tarefa") or "")) or {}
        mp4 = pasta / "luta.mp4"
        if mp4.is_file():
            situacao = "pronta"
        elif tarefa.get("situacao") == "rodando":
            situacao = "rodando"
        else:
            situacao = "falhou"
        saida.append({"id": pasta.name, "p1": ficha.get("p1"), "p2": ficha.get("p2"),
                      "mapa": ficha.get("mapa"), "semente": ficha.get("semente"),
                      "vencedor": ficha.get("vencedor"), "situacao": situacao,
                      "video": mp4.is_file()})
    return saida

# Rotas estaticas: nome publico -> (arquivo, tipo). Nada de juntar a URL
# com uma pasta.
ESTATICOS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/manifest.webmanifest": ("manifest.webmanifest",
                              "application/manifest+json"),
    "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
    # o icone (29/09: o cerebro de circuitos com as casinhas), gerado de uma
    # fonte que fica fora do repositorio (docs/sessoes/app-e-bot.md §12)
    "/icones/icone-192.png": ("icones/icone-192.png", "image/png"),
    "/icones/icone-512.png": ("icones/icone-512.png", "image/png"),
    "/icones/icone-maskable-512.png": ("icones/icone-maskable-512.png",
                                       "image/png"),
    "/icones/apple-touch-icon.png": ("icones/apple-touch-icon.png",
                                     "image/png"),
    "/apple-touch-icon.png": ("icones/apple-touch-icon.png", "image/png"),
    "/icones/favicon-32.png": ("icones/favicon-32.png", "image/png"),
    "/icones/favicon-16.png": ("icones/favicon-16.png", "image/png"),
    "/favicon.ico": ("icones/favicon.ico", "image/x-icon"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/vila.js": ("vila.js", "text/javascript; charset=utf-8"),
    "/comandos.js": ("comandos.js", "text/javascript; charset=utf-8"),
    "/decisoes.js": ("decisoes.js", "text/javascript; charset=utf-8"),
    "/assembleia.js": ("assembleia.js", "text/javascript; charset=utf-8"),
    "/orquestrador.js": ("orquestrador.js", "text/javascript; charset=utf-8"),
    "/coordenador.js": ("coordenador.js", "text/javascript; charset=utf-8"),
    "/conversa.js": ("conversa.js", "text/javascript; charset=utf-8"),
    "/oficina.js": ("oficina.js", "text/javascript; charset=utf-8"),
    "/equipe.js": ("equipe.js", "text/javascript; charset=utf-8"),
    "/biblioteca.js": ("biblioteca.js", "text/javascript; charset=utf-8"),
    "/atelie.js": ("atelie.js", "text/javascript; charset=utf-8"),
}


# ================================================================ casca
# A casca que o celular tem aberta pode ser mais velha que o servidor: o PWA
# volta do fundo com o MESMO JavaScript de horas atras (em 28/09 o cache foi
# do v8 ao v13), e uma casca velha ignora os campos novos da API calada. Toda
# resposta JSON leva a versao da casca que esta no disco (`X-Casca`), e o
# index.html sai com a sua (`<meta name="casca">`): diferente, o app recarrega.
_CASCA = {"chave": None, "versao": ""}
_CASCA_TRAVA = threading.Lock()


def versao_da_casca() -> str:
    """Um resumo do CONTEUDO dos arquivos da casca (refeito so quando o nome,
    o tamanho ou a data de algum deles muda)."""
    nomes = sorted({arquivo for arquivo, _tipo in ESTATICOS.values()})
    chave = []
    for nome in nomes:
        try:
            info = (APP / nome).stat()
            chave.append((nome, info.st_size, info.st_mtime_ns))
        except OSError:
            chave.append((nome, None, None))
    chave = tuple(chave)
    with _CASCA_TRAVA:
        if _CASCA["chave"] == chave:
            return _CASCA["versao"]
    resumo = hashlib.sha256()
    for nome in nomes:
        resumo.update(nome.encode("utf-8") + b"\0")
        try:
            resumo.update((APP / nome).read_bytes())
        except OSError:
            resumo.update(b"-")
    versao = resumo.hexdigest()[:12]
    with _CASCA_TRAVA:
        _CASCA.update(chave=chave, versao=versao)
    return versao


def fuso_do_pc_min() -> int:
    """Minutos a somar ao UTC para ter a hora do PC (-180 em Brasilia). As
    horas da API vao SEM fuso ("2026-09-29T00:58:45"): com isto o celular as
    le como hora do PC, mesmo com outro fuso ou o relogio adiantado."""
    deslocamento = datetime.now().astimezone().utcoffset()
    return int(deslocamento.total_seconds() // 60) if deslocamento else 0


# ================================================================ config
def caminho() -> Path:
    return Path(ARQUIVO) if ARQUIVO else runtime_dir() / "app_celular.json"


COMANDOS_COORDENADOR = ("servico_reiniciar", "servico_parar", "servico_ligar", "pc_acao")


def caminho_coordenador() -> Path:
    """O estado publicado pelo coordenador; esta API so o le."""
    return runtime_dir() / "coordenador" / "estado.json"


def estado_coordenador() -> dict | None:
    """Le o retrato do coordenador sem deixar uma falha de disco virar 500."""
    try:
        with caminho_coordenador().open(encoding="utf-8-sig") as arquivo:
            dados = json.load(arquivo)
    except Exception:                                      # noqa: BLE001 - leitura opcional
        return None
    return dados if isinstance(dados, dict) else None


def _instante_coordenador(valor) -> float | None:
    if not isinstance(valor, str) or not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def coordenador_para_o_app() -> dict:
    """Estado do supervisor com idade e pulso calculados no servidor."""
    dados = estado_coordenador()
    if dados is None:
        return {"vivo": False, "motivo": "o coordenador não está rodando"}
    agora = time.time()
    pulso = _instante_coordenador(dados.get("pulso_em"))
    desde = _instante_coordenador(dados.get("desde"))
    dados["vivo"] = pulso is not None and 0 <= agora - pulso < 30
    dados["idade_s"] = int(max(0, agora - desde)) if desde is not None else None
    return dados


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
        # Paginas usam a mesma ideia, mas nunca aceitam bilhetes de midia.
        self.bilhetes_paginas: dict[str, tuple] = {}
        # Previa ainda nao e biblioteca: fica na memoria, separada por aparelho.
        self.atelie: dict[str, dict] = {}
        # Bilhetes que EXISTIRAM e venceram. O celular que deixa o video
        # parado 10 minutos e da play de novo nao esta chutando: sem esta
        # lembranca, ele contaria para o bloqueio.
        self.vencidos: dict[str, float] = {}
        self.vencidos_paginas: dict[str, float] = {}
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
        for chave, (_, expira, _dono) in list(self.bilhetes_paginas.items()):
            if expira <= agora:
                del self.bilhetes_paginas[chave]
                self.vencidos_paginas[chave] = expira
        if len(self.vencidos_paginas) > VENCIDOS_MAX:
            antigos = sorted(self.vencidos_paginas, key=self.vencidos_paginas.get)
            for chave in antigos[:len(self.vencidos_paginas) - VENCIDOS_MAX]:
                del self.vencidos_paginas[chave]

    def bilhete(self, arquivo: Path, dono: str) -> str:
        agora = time.time()
        with self.trava:
            self._podar(agora)
            chave = secrets.token_urlsafe(24)
            self.bilhetes[chave] = (arquivo, agora + BILHETE_VALE_S, dono)
        return chave

    def bilhete_reusado(self, arquivo: Path, dono: str, folga_s: float = 300.0) -> str:
        """O bilhete que o aparelho ja tem para este arquivo, se ainda vale por
        mais `folga_s`; senao, um novo. A conversa rele a caixa a cada 6 s:
        sem isto, cada imagem ganharia um bilhete novo a cada releitura."""
        agora = time.time()
        with self.trava:
            for chave, (caminho, expira, quem) in self.bilhetes.items():
                if caminho == arquivo and quem == dono and expira - agora > folga_s:
                    return chave
        return self.bilhete(arquivo, dono)

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

    def bilhete_pagina(self, pagina: str, dono: str) -> str:
        agora = time.time()
        with self.trava:
            self._podar(agora)
            chave = secrets.token_urlsafe(24)
            self.bilhetes_paginas[chave] = (pagina, agora + BILHETE_VALE_S, dono)
        return chave

    def pagina_do_bilhete(self, chave: str) -> tuple:
        """(id da pagina, motivo), equivalente a arquivo_do_bilhete."""
        with self.trava:
            self._podar(time.time())
            achado = self.bilhetes_paginas.get(chave)
            vencido = chave in self.vencidos_paginas
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
        if "/v/" in bruto or "/p/" in bruto:
            caminho = "/v/…"
        metodo = str(getattr(self, "command", "") or "?")[:10]
        ip = self.client_address[0] if self.client_address else "?"
        # a data (o log atravessa a meia-noite) e o aparelho (atras do
        # `tailscale serve` todo IP e 127.0.0.1): dois aparelhos se distinguem
        aparelho = getattr(self, "_id", "") or ""
        sys.stderr.write(f"{datetime.now():%d/%m %H:%M:%S} {ip} {metodo} "
                         f"{caminho[:80]} {status}"
                         f"{' ' + aparelho if aparelho else ''}\n")

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
        # a casca do disco e o fuso do PC: o app confere os dois (o `Date`,
        # com o relogio do PC, a biblioteca ja manda)
        with contextlib.suppress(Exception):
            self.send_header("X-Casca", versao_da_casca())
            self.send_header("X-Fuso-Min", str(fuso_do_pc_min()))
        self.end_headers()
        self.wfile.write(corpo)

    def _bytes(self, corpo: bytes, tipo: str):
        self.send_response(200)
        self._cabecalhos_comuns(tipo, len(corpo))
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

    def _aparelho_do_video_da_arena(self, consulta: dict) -> str | None:
        """`video src` nao envia Authorization; esta e a unica rota com `?t`."""
        bruto = self.headers.get("Authorization", "")
        token = bruto[7:].strip() if bruto.lower().startswith("bearer ") else ""
        if not token:
            token = str((consulta.get("t") or [""])[0])
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
                    "/vilanova-retrato.webp", "/vilanova-paisagem.webp"):
            # Abertas como o resto da casca (a rede ja e a tranca): sao o
            # cenario, nao dado. O que esta NELAS nao diz nada do sistema.
            return self._imagem_da_vila(rota)
        if rota.startswith("/arte-vila/"):
            # a arte aprovada pela esteira, so leitura e aberta como o
            # cenario acima (a rede e a tranca)
            return self._arte_da_vila(rota)
        if rota.startswith("/v/"):
            return self._video_por_bilhete(rota[3:])
        if rota.startswith("/p/"):
            return self._pagina_por_bilhete(rota[3:])
        achado = re.fullmatch(r"/api/arena/video/(" + ID_DE_LUTA.pattern + r")\.mp4", rota)
        if achado:
            return self._video_da_arena(achado.group(1), consulta)
        if not rota.startswith("/api/"):
            return self._erro(404, "nao existe")
        if self._aparelho() is None:
            return

        try:
            if rota == "/api/sprites/conferir":
                return self._json({"itens": sprites_a_conferir()})
            if rota == "/api/arena/opcoes":
                return self._json(opcoes_da_arena())
            if rota == "/api/arena/lutas":
                lutas = lutas_da_arena()
                token = self.headers.get("Authorization", "")[7:].strip()
                for luta in lutas:
                    if luta.pop("video"):
                        luta["video_url"] = f"/api/arena/video/{luta['id']}.mp4?t={token}"
                return self._json({"lutas": lutas})
            if rota == "/api/atelie":
                return self._atelie_catalogo(consulta)
            achado = re.fullmatch(r"/api/atelie/arquivo/([a-z0-9_-]{8,40})/(original|limpa|folha|previa|quadro-\d+)", rota)
            if achado:
                return self._atelie_arquivo(*achado.groups())
            achado = re.fullmatch(r"/api/sprites/arquivo/(palco|vila)/([a-z0-9][a-z0-9_-]{0,63})/([^/]+)", rota)
            if achado:
                return self._arquivo_sprite(achado.group(1), achado.group(2), achado.group(3))
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
            if rota == "/api/biblioteca":
                return self._json(biblioteca.para_o_app())
            achado = re.fullmatch(r"/api/biblioteca/estado/([a-z0-9-]{1,64})", rota)
            if achado:
                try:
                    return self._json(biblioteca.ver_estado(achado.group(1)))
                except ValueError:
                    return self._erro(404, "pagina nao encontrada")
            achado = re.fullmatch(r"/api/biblioteca/doc/([a-z0-9-]{1,64})", rota)
            if achado:
                texto = biblioteca.ler_documento(achado.group(1))
                if texto is None:
                    return self._erro(404, "documento nao encontrado")
                return self._json({"texto": texto})
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
            if rota == "/api/coordenador":
                return self._json(_limpo(coordenador_para_o_app()))
            if rota == "/api/coordenador/conversa":
                # O cerebro (02/10): a conversa e as propostas. Os pedidos
                # (03/10): a conversa do orquestrador do servidor, na MESMA
                # linha do tempo, e o estado de cada pedido. So leitura.
                from coordenador import cerebro as coord_cerebro, pedidos
                dados = coord_cerebro.para_o_app()
                mesa = pedidos.para_o_app()
                dados["conversa"] = sorted(
                    list(dados.get("conversa") or []) + list(mesa["conversa"]),
                    key=lambda linha: str(linha.get("em") or ""))[-150:]
                dados["pedidos"] = mesa["pedidos"]
                dados["pedidos_na_fila"] = mesa["na_fila"]
                dados["novo_assunto"] = mesa["novo_assunto"]
                return self._json(_limpo(dados))
            # A OFICINA DO CODEX (01/10): o que foi delegado, ao vivo. So
            # leitura; os eventos novos por offset (`desde`), sem reler o
            # arquivo inteiro a cada 3 s.
            if rota == "/api/delegados":
                return self._json(_limpo(delegar.para_o_app()))
            if rota == "/api/equipe":
                return self._json(_limpo(delegar.equipe_para_o_app()))
            achado = re.fullmatch(r"/api/delegado/([a-z0-9][a-z0-9-]{2,39})", rota)
            if achado:
                ficha = delegar.detalhe_para_o_app(
                    achado.group(1), _inteiro(consulta, "desde", -1),
                    completo=(consulta.get("completo") or ["0"])[0] == "1")
                if ficha is None:
                    return self._erro(404, "essa tarefa não existe")
                return self._json(_limpo(ficha))
            # O CORREIO (Vila das IAs, fase 2): a caixa de cada IA de chat.
            # Ler registra a PRESENCA: o carteiro so manda a resposta ao
            # Telegram quando o app nao esta olhando aquela caixa.
            if rota == "/api/correio":
                return self._json(self._correio_resumo())
            achado = re.fullmatch(rf"/api/correio/({CAIXAS_RE})", rota)
            if achado:
                return self._json(self._correio_caixa(achado.group(1),
                                                      _inteiro(consulta, "n", 60)))
            # A IMAGEM de um pedido: pela caixa e pelo id do pedido, NUNCA por
            # caminho. So pedido registrado e respondido; o celular recebe um
            # bilhete de 10 min para aquele arquivo e mais nada.
            achado = re.fullmatch(rf"/api/imagem/({CAIXAS_RE})/([0-9a-f]{{8}})", rota)
            if achado:
                ficha = self._imagem_do_pedido(achado.group(1), achado.group(2))
                if ficha is None:
                    return self._erro(404, "imagem não existe")
                return self._json(ficha)
            if rota == "/api/imagens":
                ia = (consulta.get("ia") or [""])[0][:20].lower()
                return self._json(self._galeria(ia, _inteiro(consulta, "n", 60)))
            if rota == "/api/claude":
                # o interruptor do Claude (liberado / proibido), com o historico
                return self._json(claude_estado.para_o_app())
            if rota == "/api/orquestrador/fluxo":
                return self._json(painel_dados.FLUXO.ler())
            if rota == "/api/decisoes":
                try:
                    dados = decisoes.para_o_app()
                except decisoes.Recusa as exc:
                    return self._erro(409, str(exc))
                # quem le as respostas dele (o `esperar` acorda com elas)
                try:
                    vigia = orquestrador.situacao_do_vigia()
                    dados["vigia"] = {"situacao": vigia["situacao"],
                                      "texto": vigia["texto"]}
                except Exception:                            # noqa: BLE001
                    dados["vigia"] = None
                return self._json(dados)
            if rota == "/api/assembleias":
                # A assembleia so delibera; este endpoint expõe o estado que
                # tambem vai virar contexto de um no no Grimorio.
                from ias import assembleia
                return self._json({"assembleias": _limpo(assembleia.listar())})
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
    def _corpo(self, maximo: int = CORPO_MAX) -> dict | None:
        """O JSON do POST, ou None (com a resposta de erro ja enviada)."""
        tipo = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if tipo != "application/json":
            self._erro(415, "envie application/json")
            return None
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            tamanho = -1
        if not 0 < tamanho <= maximo:
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
        if rota == "/api/arena/luta":
            return self._arena_luta()
        if rota in ("/api/acao", "/api/acao/confirmar"):
            return self._acao(rota)
        if rota == "/api/decisao/responder":
            return self._responder_decisao()
        if rota == "/api/atelie/importar":
            return self._atelie_importar()
        achado = re.fullmatch(r"/api/sprites/(palco|vila)/([a-z0-9][a-z0-9_-]{0,63})/(aprovar|refazer|descartar)", rota)
        if achado:
            return self._acao_sprite(*achado.groups())
        if rota == "/api/assembleia":
            return self._abrir_assembleia()
        if rota in ("/api/orquestrador/comando", "/api/orquestrador/contestar"):
            return self._orquestrador(rota)
        if rota == "/api/coordenador/comando":
            return self._coordenador_comando()
        if rota == "/api/coordenador/falar":
            return self._coordenador_falar()
        achado = re.fullmatch(r"/api/coordenador/proposta/([0-9a-f]{12})", rota)
        if achado:
            return self._coordenador_proposta(achado.group(1))
        if rota == "/api/claude":
            return self._interruptor_claude()
        if rota == "/api/equipe/contratar":
            return self._equipe("contratar")
        if rota == "/api/equipe/config":
            return self._equipe("config")
        achado = re.fullmatch(r"/api/equipe/([a-z0-9][a-z0-9-]{2,39})/(parar|renovar|corrigir|aplicar)", rota)
        if achado:
            return self._equipe(achado.group(2), achado.group(1))
        achado = re.fullmatch(r"/api/biblioteca/bilhete/([a-z0-9-]{1,64})", rota)
        if achado:
            return self._biblioteca_bilhete(achado.group(1))
        achado = re.fullmatch(r"/api/biblioteca/estado/([a-z0-9-]{1,64})", rota)
        if achado:
            return self._biblioteca_estado(achado.group(1))
        achado = re.fullmatch(rf"/api/correio/({GERADORES_RE}|livre)/imagem", rota)
        if achado:
            return self._pedir_imagem(achado.group(1))
        achado = re.fullmatch(rf"/api/correio/({CAIXAS_RE})/visto", rota)
        if achado:
            return self._correio_post(achado.group(1), True)
        achado = re.fullmatch(r"/api/correio/(deepseek|chatgpt|gemini|grok)", rota)
        if achado:
            return self._correio_post(achado.group(1), False)
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

    # ------------------------------------------------------------ atelie
    def _atelie_catalogo(self, consulta):
        sujeito = (consulta.get("sujeito") or [""])[0]
        try:
            dados = sprites_importar.catalogo()
            if sujeito:
                slots = dados["sujeitos"][sujeito]["slots"]
                nome = (consulta.get("nome") or [""])[0]
                if nome and not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", nome):
                    return self._erro(400, "nome invalido")
                pasta = ATELIE_BIBLIOTECA / sujeito / nome if nome else None
                dados = {"sujeitos": {sujeito: {**dados["sujeitos"][sujeito],
                    "slots": [{**s, "vazio": not bool(pasta and (pasta / f"{s['id']}.png").is_file())}
                              for s in slots]}}}
            return self._json(dados)
        except KeyError:
            return self._erro(400, "sujeito inexistente")

    @staticmethod
    def _atelie_png(arr) -> bytes:
        saida = io.BytesIO()
        Image.fromarray(arr, "RGBA").save(saida, "PNG", optimize=True)
        return saida.getvalue()

    @staticmethod
    def _atelie_gif(quadros, fps: float) -> bytes:
        imagens = [Image.fromarray(q, "RGBA").convert("RGB") for q in quadros]
        if not imagens:
            imagens = [Image.new("RGB", (1, 1))]
        saida = io.BytesIO()
        imagens[0].save(saida, "GIF", save_all=True, append_images=imagens[1:],
                        duration=max(20, round(1000 / max(1, float(fps)))), loop=0)
        return saida.getvalue()

    def _atelie_arquivo(self, sessao: str, parte: str):
        with self.estado.trava:
            dados = self.estado.atelie.get(sessao)
        if not dados or dados["dono"] != self._dono:
            return self._erro(404, "previa nao existe")
        corpo = dados["arquivos"].get(parte)
        if corpo is None:
            return self._erro(404, "imagem nao existe")
        return self._bytes(corpo, "image/gif" if parte == "previa" else "image/png")

    def _atelie_corpo(self):
        """(imagem, opcoes) de JSON/base64 ou multipart, limitado antes de ler."""
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            tamanho = -1
        if not 0 < tamanho <= ATELIE_MAX + 65536:
            self._erro(413, "imagem deve ter ate 20 MB")
            return None
        bruto = self.rfile.read(tamanho)
        tipo = self.headers.get("Content-Type", "")
        if tipo.startswith("application/json"):
            try:
                dados = json.loads(bruto.decode("utf-8"))
                imagem = base64.b64decode(dados.get("imagem", ""), validate=True)
                opcoes = dados.get("opcoes") or dados
            except (ValueError, TypeError, UnicodeDecodeError):
                self._erro(400, "imagem invalida")
                return None
            return imagem, opcoes if isinstance(opcoes, dict) else {}
        achado = re.search(r"boundary=([^;]+)", tipo)
        if not tipo.startswith("multipart/form-data") or not achado:
            self._erro(415, "envie multipart ou JSON/base64")
            return None
        partes = bruto.split(b"--" + achado.group(1).strip('"').encode())
        campos = {}
        for parte in partes:
            cabeca, separador, valor = parte.partition(b"\r\n\r\n")
            nome = re.search(br'name="([^"\\]+)"', cabeca)
            if not separador or not nome:
                continue
            if valor.endswith(b"\r\n"):
                valor = valor[:-2]
            campos[nome.group(1).decode("utf-8", "ignore")] = valor
        try:
            opcoes = json.loads(campos.get("opcoes", b"{}").decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            opcoes = {}
        return campos.get("imagem", b""), opcoes if isinstance(opcoes, dict) else {}

    def _atelie_importar(self):
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as acoes estao desligadas neste servidor")
        pedido = self._atelie_corpo()
        if pedido is None:
            return
        imagem, opcoes = pedido
        try:
            sujeito = str(opcoes.get("sujeito") or "")
            slot_id = str(opcoes.get("slot") or "")
            slot = sprites_importar.slot_do_catalogo(sujeito, slot_id)
            resultado = sprites_importar.processar(
                sprites_importar.abrir_bytes(imagem), tolerancia=float(opcoes.get("tolerancia", 24)),
                modo=str(opcoes.get("modo") or "auto"), colunas=int(opcoes.get("colunas") or 0),
                linhas=int(opcoes.get("linhas") or 0), ancora=slot.get("ancora", "pes"),
                excluir=opcoes.get("excluir") or [], ordem=opcoes.get("ordem") or None)
        except (TypeError, ValueError) as exc:
            return self._erro(400, str(exc))
        nome = str(opcoes.get("nome") or "novo")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", nome):
            return self._erro(400, "nome invalido")
        sessao = secrets.token_urlsafe(12).replace("-", "_")
        arquivos = {"original": self._atelie_png(resultado.original),
                    "limpa": self._atelie_png(resultado.limpo),
                    "folha": self._atelie_png(resultado.folha),
                    "previa": self._atelie_gif(resultado.alinhado.quadros, slot.get("fps", 8))}
        arquivos.update({f"quadro-{i}": self._atelie_png(q)
                         for i, q in enumerate(resultado.alinhado.quadros)})
        if opcoes.get("salvar"):
            try:
                sprites_importar.salvar(resultado, ATELIE_BIBLIOTECA / sujeito / nome,
                                        slot, str(opcoes.get("arquivo") or "imagem"),
                                        substituir=bool(opcoes.get("substituir")))
                if opcoes.get("espelhar") and slot.get("espelho_de"):
                    oposto = sprites_importar.slot_do_catalogo(sujeito, slot["espelho_de"])
                    sprites_importar.salvar(sprites_importar.espelhar(resultado),
                                            ATELIE_BIBLIOTECA / sujeito / nome, oposto,
                                            str(opcoes.get("arquivo") or "imagem"),
                                            substituir=bool(opcoes.get("substituir")))
            except FileExistsError:
                return self._erro(409, "slot ja tem imagem; confirme substituir")
        with self.estado.trava:
            self.estado.atelie[sessao] = {"dono": self._dono, "arquivos": arquivos}
        raiz = f"/api/atelie/arquivo/{sessao}"
        return self._json({"sessao": sessao, "quadros": len(resultado.alinhado.quadros),
                           "avisos": resultado.avisos, "original": f"{raiz}/original",
                           "limpa": f"{raiz}/limpa", "folha": f"{raiz}/folha",
                           "previa": f"{raiz}/previa",
                           "quadros_urls": [f"{raiz}/quadro-{i}" for i in range(len(resultado.alinhado.quadros))],
                           "salvo": bool(opcoes.get("salvar"))})

    def _biblioteca_bilhete(self, pagina: str):
        if self._aparelho() is None:
            return
        if biblioteca.ler_pagina(pagina) is None:
            return self._erro(404, "pagina nao encontrada")
        return self._json({"url": f"/p/{self.estado.bilhete_pagina(pagina, self._dono)}",
                           "vale_s": BILHETE_VALE_S})

    def _biblioteca_estado(self, pagina: str):
        if self._aparelho() is None:
            return
        corpo = self._corpo()
        if corpo is None:
            return
        try:
            dados = biblioteca.marcar(pagina, str(corpo.get("doc_id") or ""),
                                      str(corpo.get("estado") or ""))
        except ValueError as exc:
            return self._erro(400, str(exc))
        return self._json(dados)

    # ---------------------------------------------------------- sprites
    def _arquivo_sprite(self, perfil: str, item_id: str, nome: str):
        dados = _ficha_sprite(perfil, item_id)
        arquivo = _arquivo_sprite(dados, nome) if dados else None
        if arquivo is None:
            return self._erro(404, "arquivo de sprite nao existe")
        try:
            corpo = arquivo.read_bytes()
        except OSError:
            return self._erro(404, "arquivo de sprite sumiu")
        self.send_response(200)
        self._cabecalhos_comuns(_SPRITES_ARQUIVOS[nome][1], len(corpo))
        self.end_headers()
        self.wfile.write(corpo)

    def _acao_sprite(self, perfil: str, item_id: str, acao: str):
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as acoes estao desligadas neste servidor")
        corpo = self._corpo()
        if corpo is None:
            return
        motivo = str(corpo.get("motivo") or "").strip()
        if acao == "refazer" and not motivo:
            return self._erro(400, "diga o que mudar")
        with _TRAVA_SPRITES:
            anterior = sprites_config.PERFIL
            try:
                sprites_config.usar(perfil)
                if acao == "aprovar":
                    resultado = sprites_aprovar.aprovar(item_id)
                elif acao == "refazer":
                    resultado = sprites_aprovar.refazer(item_id, motivo)
                else:
                    resultado = sprites_aprovar.descartar(item_id)
            except ValueError as exc:
                return self._erro(409, str(exc))
            except OSError:
                return self._erro(503, "a esteira esta ocupada; tente de novo")
            finally:
                sprites_config.usar(anterior)
        return self._json({"feito": True, "acao": acao,
                           "estado": resultado.get("estado")})

    # ---------------------------------------------------------- acoes
    def _arena_luta(self):
        """A unica acao da Arena: nao divide a GPU do Godot com outro render."""
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as acoes estao desligadas neste servidor")
        corpo = self._corpo()
        if corpo is None:
            return
        opcoes = opcoes_da_arena()
        nomes = {p["nome"] for p in opcoes["personagens"]}
        mapas = {m["id"] for m in opcoes["mapas"]}
        p1, p2, mapa = corpo.get("p1"), corpo.get("p2"), corpo.get("mapa")
        if p1 not in nomes or p2 not in nomes or p1 == p2 or mapa not in mapas:
            return self._erro(400, "lutadores ou mapa invalidos")
        try:
            semente = int(corpo.get("semente")) if corpo.get("semente") is not None else secrets.randbelow(2 ** 63)
        except (TypeError, ValueError):
            return self._erro(400, "semente invalida")
        if not 0 <= semente < 2 ** 63:
            return self._erro(400, "semente invalida")
        chave = f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"
        pasta = pasta_da_arena() / chave
        with self.estado.trava:
            if tarefas.rodando("arena"):
                return self._erro(409, "ja ha um render da Arena rodando")
            pasta.mkdir(parents=True, exist_ok=True)
            (pasta / "luta.json").write_text(json.dumps({"tarefa": chave, "p1": p1, "p2": p2,
                "mapa": mapa, "semente": semente}, ensure_ascii=False), encoding="utf-8")
            try:
                tarefas.iniciar("arena", f"Arena: {p1} x {p2}",
                    [sys.executable, "-m", "remoto.arena", "--p1", p1, "--p2", p2,
                     "--mapa", mapa, "--semente", str(semente), "--pasta", str(pasta)],
                    Path(__file__).resolve().parents[1], self._id,
                    {"p1": p1, "p2": p2, "mapa": mapa, "semente": semente}, chave)
            except (OSError, ValueError) as exc:
                return self._erro(503, f"nao consegui iniciar a Arena: {exc}")
        return self._json({"id": chave, "semente": semente}, 202)

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
        # O que a tela tinha na mao (a hora da resposta vigente, "" = nenhuma).
        # Outra aba ou outro aparelho respondeu nesse meio-tempo: recusa, em
        # vez de trocar a decisao por cima de uma resposta que ele nao viu.
        extra = {}
        if "esperava" in corpo:
            extra["esperava"] = str(corpo.get("esperava") or "")[:40]
        try:
            evento = decisoes.responder(item_id, str(corpo.get("opcao") or "")[:60],
                                        str(corpo.get("comentario") or ""),
                                        aparelho=self._id, origem="app", **extra)
        except KeyError:
            return self._erro(404, "decisão desconhecida")
        except decisoes.Recusa as exc:
            return self._erro(409, str(exc))
        except OSError:
            return self._erro(503, "as decisões estão ocupadas; tente de novo")
        acoes.avisar_texto(decisoes.texto_do_aviso(evento))
        return self._json({"feito": True, "evento": evento})

    def _abrir_assembleia(self):
        """Convoca a deliberacao pelo correio; so o carteiro a entrega."""
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as acoes estao desligadas neste servidor")
        corpo = self._corpo(maximo=20_000)
        if corpo is None:
            return
        from ias import assembleia
        try:
            ident = assembleia.abrir(corpo.get("pergunta"), corpo.get("opcoes"),
                                     corpo.get("participantes"), corpo.get("projeto", "geral"),
                                     corpo.get("contexto", ""))
        except (assembleia.Recusa, ValueError) as exc:
            return self._erro(400, str(exc))
        except OSError:
            return self._erro(503, "nao consegui guardar a assembleia")
        return self._json({"feito": True, "id": ident})

    def _equipe(self, acao_equipe: str, ident: str = ""):
        """Contratos da Equipe: pareamento e --acoes antes de qualquer mutacao."""
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as acoes estao desligadas neste servidor")
        corpo = self._corpo(maximo=20_000)
        if corpo is None:
            return
        try:
            if acao_equipe == "config":
                return self._json({"feito": True, "config": delegar.gravar_config(corpo)})
            if acao_equipe == "contratar":
                cargo = str(corpo.get("cargo") or "").lower()
                ia = str(corpo.get("ia") or "codex").lower()
                tarefa = str(corpo.get("tarefa") or "").strip()
                if not tarefa or len(tarefa) > 12_000:
                    return self._erro(400, "tarefa invalida")
                if cargo not in delegar.cargos() or ia not in delegar.IAS:
                    return self._erro(400, "cargo ou ia desconhecido")
                ident = "app-" + secrets.token_hex(4)
                pedido = delegar.pasta_da(ident) / "pedido.md"
                pedido.parent.mkdir(parents=True, exist_ok=True)
                pedido.write_text(tarefa, encoding="utf-8")
                estado = delegar.criar(ident, pedido, ["remoto/**", "coordenador/**", "docs/**"],
                                       ia=ia, cargo=cargo, titulo=tarefa.splitlines()[0])
                delegar.no_fundo(["rodar", "--id", ident], ident)
                return self._json({"feito": True, "trabalhador": _limpo(estado)})
            if acao_equipe == "parar":
                return self._json({"feito": True, "resultado": delegar.parar(ident)})
            if acao_equipe == "renovar":
                return self._json({"feito": True, "trabalhador": _limpo(delegar.renovar(ident))})
            if acao_equipe == "corrigir":
                texto = str(corpo.get("texto") or "").strip()
                if not texto:
                    return self._erro(400, "diga a correcao")
                pedido = delegar.pasta_da(ident) / "correcao_app.md"
                pedido.write_text(texto, encoding="utf-8")
                return self._json({"feito": True, "trabalhador": _limpo(delegar.corrigir(ident, pedido))})
            return self._json({"feito": True, "resultado": delegar.aplicar(ident)})
        except delegar.Recusa as exc:
            return self._erro(409, str(exc))
        except OSError:
            return self._erro(503, "a equipe esta ocupada; tente de novo")

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
                # quem vai ler: a tela diz na hora se alguem esta ouvindo
                try:
                    vigia = orquestrador.situacao_do_vigia()
                    vigia = {"situacao": vigia["situacao"], "texto": vigia["texto"]}
                except Exception:                            # noqa: BLE001
                    vigia = None
                return self._json({"feito": True, "comando": linha, "vigia": vigia})
            feito = orquestrador.contestar(str(corpo.get("id") or "")[:20],
                                           str(corpo.get("comentario") or ""), self._id)
        except orquestrador.FilaMudou as exc:
            # a tela distingue pelo codigo: reabre com a fila atual e avisa
            return self._json({"erro": str(exc), "codigo": "fila_mudou",
                               "fila_versao": orquestrador.fila_versao(
                                   orquestrador.ler_estado()["fila"])}, 409)
        except orquestrador.Recusa as exc:
            return self._erro(409, str(exc))
        except OSError:
            return self._erro(503, "o orquestrador está ocupado; tente de novo")
        acoes.avisar_texto(f"⚔ Adrian contestou uma decisão do orquestrador: "
                           f"nó {feito['no']} no Grimório")
        return self._json({"feito": True, **feito})

    def _coordenador_comando(self):
        """Guarda um pedido fechado para o coordenador aplicar no PC."""
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as ações estão desligadas neste servidor")
        corpo = self._corpo()
        if corpo is None:
            return
        comando = corpo.get("cmd")
        valor = corpo.get("valor")
        if not isinstance(comando, str) or comando not in COMANDOS_COORDENADOR:
            return self._erro(400, "comando desconhecido")
        estado = estado_coordenador() or {}
        servicos = estado.get("servicos") if isinstance(estado.get("servicos"), dict) else {}
        acoes_pc = estado.get("acoes_pc") if isinstance(estado.get("acoes_pc"), list) else []
        if comando == "pc_acao":
            acao = next((a for a in acoes_pc if isinstance(a, dict) and a.get("id") == valor), None)
            if acao is None:
                return self._erro(400, "ação desconhecida")
            if acao.get("perigo") is True and corpo.get("confirmar") is not True:
                return self._erro(400, "confirme a ação perigosa")
        elif not isinstance(valor, str) or valor not in servicos:
            return self._erro(400, "serviço desconhecido")
        try:
            linha = orquestrador.gravar_comando(comando, valor, aparelho=self._id)
        except orquestrador.Recusa as exc:
            return self._erro(409, str(exc))
        except OSError:
            return self._erro(503, "o orquestrador está ocupado; tente de novo")
        return self._json({"feito": True, "comando": linha})

    def _coordenador_falar(self):
        """A aba Conversa: a mensagem vai para a entrada do cerebro, a mesma do
        Telegram. Exige `--acoes`: o que ele pensa pode reiniciar servico."""
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as ações estão desligadas neste servidor")
        corpo = self._corpo(maximo=20_000)        # 4000 caracteres com acento passam de 4 KB
        if corpo is None:
            return
        texto = corpo.get("texto")
        novo = corpo.get("novo") is True
        if novo and (texto is None or (isinstance(texto, str) and not texto.strip())):
            # "Novo assunto" sem texto: o proximo pedido abre outro orquestrador
            from coordenador import pedidos
            try:
                pedidos.novo_assunto("app")
            except OSError as exc:
                return self._erro(503, f"não consegui guardar: {exc}")
            return self._json({"feito": True, "novo_assunto": True})
        if not isinstance(texto, str) or not texto.strip():
            return self._erro(400, "a mensagem está vazia")
        if len(texto) > 4000:
            return self._erro(400, "a mensagem passa de 4000 caracteres")
        # 03/10: pergunta curta de estado ("o app está no ar?") vai ao cerebro,
        # que responde em segundos; o resto é PEDIDO e vai a um trabalhador
        # `orquestrador` do servidor (coordenador/pedidos.py)
        from coordenador import cerebro as coord_cerebro, pedidos
        try:
            if not novo and pedidos.e_de_estado(texto):
                entrada = coord_cerebro.registrar_entrada(texto, "app")
                return self._json({"feito": True, "id": entrada["id"], "em": entrada["em"],
                                   "situacao": "recebido", "para": "cerebro"})
            item = pedidos.registrar(texto, "app", novo=novo)
        except (OSError, ValueError) as exc:
            return self._erro(503, f"não consegui guardar a mensagem: {exc}")
        return self._json({"feito": True, "id": item["id"], "em": item["atualizado_em"],
                           "situacao": item["situacao"], "para": "orquestrador",
                           "continuacao": bool(item.get("continuacao"))})

    def _coordenador_proposta(self, ident: str):
        """Confirmar ou recusar uma proposta do cerebro (vence em 30 min)."""
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as ações estão desligadas neste servidor")
        corpo = self._corpo()
        if corpo is None:
            return
        decisao = corpo.get("decisao")
        if decisao not in ("confirmar", "recusar"):
            return self._erro(400, "decisão é confirmar ou recusar")
        from coordenador import cerebro as coord_cerebro
        try:
            feito = coord_cerebro.decidir_proposta(ident, decisao, aparelho=self._id)
        except LookupError:
            return self._erro(404, "proposta desconhecida")
        except OSError:
            return self._erro(503, "o coordenador está ocupado; tente de novo")
        if not feito.get("feito"):
            return self._erro(409, str(feito.get("motivo") or "a proposta não vale mais"))
        return self._json(_limpo(feito))

    # ------------------------------------------------- interruptor do Claude
    def _interruptor_claude(self):
        """Liga ou desliga o uso automatico do Claude (29/09/2026).

        Grava DIRETO no `claude.json`, sem passar pela fila do orquestrador:
        com o Claude proibido o `esperar` nao acorda com comando, e um
        "liberar" que fosse comando nunca seria aplicado. O pedido diz o
        ALVO (`liberar: true|false`), nao "inverter": o toque repetido nao
        desfaz o primeiro. A confirmacao em dois toques e da tela. So com
        token; nao depende de `--acoes` (nada executa na maquina).
        """
        aparelho = self._aparelho()
        if aparelho is None:
            return
        corpo = self._corpo()
        if corpo is None:
            return
        if not isinstance(corpo.get("liberar"), bool):
            return self._erro(400, "diga liberar: true ou false")
        por = f"pelo app ({str(aparelho)[:30]})"
        try:
            feito = claude_estado.mudar(corpo["liberar"], por=por,
                                        motivo=str(corpo.get("motivo") or "")[:200])
        except OSError:
            return self._erro(503, "o interruptor está ocupado; tente de novo")
        estado = feito["estado"]
        if feito["mudou"]:
            acoes.avisar_texto(orquestrador.texto_do_aviso_claude(
                estado["liberado"], "pelo app", estado["em"]))
        return self._json({"feito": True, "mudou": feito["mudou"],
                           "claude": claude_estado.para_o_app()})

    # -------------------------------------------------------- correio
    # A conversa do Adrian com cada IA (Vila das IAs, fase 2). O servidor
    # NUNCA abre navegador: deixa a mensagem na caixa (`ias.correio`) e quem
    # entrega e o carteiro, em processo proprio (`python -m ias carteiro`).
    def _correio_resumo(self) -> dict:
        c = _correio()
        c.registrar_presenca("app")
        caixas = []
        for ia, info in c.resumo().items():
            ultima = info.get("ultima")
            if ultima:
                ultima = {**ultima, "texto": str(ultima.get("texto") or "")[:200],
                          "resposta": (str(ultima["resposta"])[:300]
                                       if ultima.get("resposta") else None),
                          "anexos": len(ultima.get("anexos") or [])}
            caixas.append({"ia": ia, **info, "ultima": ultima})
        # as caixas de imagem (PicassoIA, DreamFace, Digen e o rodizio): a Vila
        # mostra a imagem nova do PicassoIA como mostra a resposta de um chat
        imagens = []
        for ia, info in c.resumo(("picasso", "dreamface", "digen", c.LIVRE)).items():
            ultima = info.get("ultima")
            if ultima:
                ultima = {k: ultima.get(k) for k in (
                    "id", "situacao", "resposta", "erro", "tipo", "gerador", "em",
                    "atualizado_em")}
                ultima["texto"] = str((info.get("ultima") or {}).get("texto") or "")[:200]
            imagens.append({"ia": ia, **info, "ultima": ultima})
        return {"ias": caixas, "imagens": imagens, "geradores": _imagem().geradores(),
                "carteiro": c.estado_do_carteiro(), "enviar": bool(self.estado.com_acoes)}

    def _mensagem_para_o_app(self, c, caixa: str, m: dict) -> dict:
        """A mensagem como o celular a ve: anexo so pelo nome, e a imagem de um
        pedido respondido so por bilhete (nunca o caminho)."""
        saida = {**m, "anexos": [Path(a).name for a in (m.get("anexos") or [])]}
        # o pedido pelo Criar, ou a conversa cuja resposta foi uma imagem
        if isinstance(m.get("imagem"), dict):
            info = {k: m["imagem"].get(k) for k in (
                "arquivo", "largura", "altura", "bytes", "formato", "prova", "forca")}
            caminho = c.arquivo_da_imagem(caixa, m["id"])
            if caminho is not None:
                info["url"] = f"/v/{self.estado.bilhete_reusado(caminho, self._dono)}"
                info["nome"] = f"{m.get('gerador') or caixa}_{caminho.name}"
            else:
                info["url"] = None
                info["sumiu"] = True
            saida["imagem"] = info
        return saida

    def _correio_caixa(self, ia: str, n: int) -> dict:
        c = _correio()
        img = _imagem()
        c.registrar_presenca(f"correio:{ia}")
        casa = c.casa(ia)
        mensagens = [self._mensagem_para_o_app(c, ia, m) for m in c.historico(ia, n)]
        return {"ia": ia, "rotulo": c.ROTULOS.get(ia, ia), "emoji": c.EMOJIS.get(ia, "•"),
                "conversa": ia in c.CHATS,
                "gerador": img.gerador(ia) if ia in c.GERADORES else None,
                "rodizio": img.rodizio_ordem() if ia == c.LIVRE else None,
                "geradores": img.geradores(),
                "mensagens": mensagens,
                "casa": {"geracao": casa.get("geracao"), "mensagens": casa.get("mensagens"),
                         "ultimo_resumo_em": casa.get("ultimo_resumo_em"),
                         "tem_resumo": bool(c.resumo_da_casa(ia).strip())},
                "carteiro": c.estado_do_carteiro(), "ilegiveis": c.ilegiveis(ia),
                "enviar": bool(self.estado.com_acoes)}

    def _imagem_do_pedido(self, caixa: str, mid: str) -> dict | None:
        c = _correio()
        caminho = c.arquivo_da_imagem(caixa, mid)
        if caminho is None:
            return None
        tipo = decisoes.tipo_da_midia(caminho)
        if not tipo or not tipo.startswith("image/"):
            return None
        m = c.uma(caixa, mid) or {}
        return {"url": f"/v/{self.estado.bilhete_reusado(caminho, self._dono)}",
                "tipo": tipo, "nome": f"{m.get('gerador') or caixa}_{caminho.name}",
                "vale_s": BILHETE_VALE_S}

    def _galeria(self, ia: str, n: int) -> dict:
        """As imagens geradas (todas, ou as de um gerador), da mais nova para a
        mais velha, cada uma com o seu bilhete."""
        c = _correio()
        if ia and ia not in GERADORES_DE_IMAGEM:
            return {"ia": ia, "imagens": [], "erro": "não gera imagem"}
        itens = []
        for m in c.imagens(ia or None, n):
            caixa = m.get("caixa") or ""
            item = self._mensagem_para_o_app(c, caixa, m)
            if not (item.get("imagem") or {}).get("url"):
                continue
            itens.append({"caixa": caixa, "id": m["id"], "gerador": m.get("gerador"),
                          "texto": str(m.get("texto") or "")[:300],
                          "proporcao": m.get("proporcao"), "em": m.get("em"),
                          "respondida_em": m.get("respondida_em"),
                          "imagem": item["imagem"]})
        return {"ia": ia or None, "imagens": itens}

    def _pedir_imagem(self, caixa: str):
        """Um PEDIDO DE IMAGEM entra na caixa (o carteiro gera). Faz o PC abrir
        um navegador na conta dele: so com --acoes, como a conversa. Direto,
        sem confirmacao (decisao `mensagem-para-uma-ia-pelo-app-direto-ou`: o
        pedido fica na conta dele e nao sai para o mundo)."""
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as ações estão desligadas neste servidor")
        corpo = self._corpo(CORPO_PEDIDO_IMAGEM_MAX)
        if corpo is None:
            return
        c, img = _correio(), _imagem()
        prompt = str(corpo.get("prompt") or corpo.get("texto") or "")
        proporcao = str(corpo.get("proporcao") or "").strip()
        modelo = corpo.get("modelo")
        try:
            info = img.conferir_pedido(caixa, proporcao)
            if modelo and modelo not in (info.get("modelos") or [modelo]):
                raise c.CorreioInvalido(
                    f"modelo {str(modelo)[:40]!r}: o {info.get('rotulo')} oferece "
                    f"{', '.join(info.get('modelos') or []) or 'só o padrão'}")
            mensagem = c.pedir_imagem(caixa, prompt, proporcao=proporcao,
                                      modelo=str(modelo) if modelo else None)
        except c.CorreioInvalido as exc:
            return self._erro(400, str(exc))
        except OSError:
            return self._erro(503, "o correio está ocupado; tente de novo")
        sys.stderr.write(f"{datetime.now():%d/%m %H:%M:%S} imagem {caixa} {mensagem['id']} "
                         f"({len(prompt)} chars, {proporcao}) {self._id}\n")
        return self._json({"feito": True, "mensagem": mensagem,
                           "carteiro": c.estado_do_carteiro()})

    def _correio_post(self, ia: str, visto: bool):
        if self._aparelho() is None:
            return
        c = _correio()
        if visto:
            corpo = self._corpo()
            if corpo is None:
                return
            return self._json({"feito": True, "vistas": c.marcar_vistas(ia)})
        # Enviar faz o PC abrir um navegador na conta dele: e uma acao, e
        # so existe com --acoes (a leitura fica sempre).
        if not self.estado.com_acoes:
            return self._erro(403, "as ações estão desligadas neste servidor")
        corpo = self._corpo(CORPO_CORREIO_MAX)
        if corpo is None:
            return
        texto = str(corpo.get("texto") or "")
        anexos = []
        try:
            for item in (corpo.get("anexos") or [])[:4]:
                if not isinstance(item, dict):
                    continue
                import base64
                try:
                    conteudo = base64.b64decode(str(item.get("b64") or ""), validate=True)
                except (ValueError, TypeError):
                    return self._erro(400, "anexo ilegível")
                anexos.append(c.guardar_anexo(ia, str(item.get("nome") or "imagem.png"),
                                              conteudo))
            mensagem = c.enviar(ia, texto, de="adrian", anexos=anexos)
        except c.CorreioInvalido as exc:
            return self._erro(400, str(exc))
        except OSError:
            return self._erro(503, "o correio está ocupado; tente de novo")
        sys.stderr.write(f"{datetime.now():%d/%m %H:%M:%S} correio {ia} {mensagem['id']} "
                         f"({len(texto)} chars, {len(anexos)} anexo(s)) {self._id}\n")
        return self._json({"feito": True, "mensagem": mensagem,
                           "carteiro": c.estado_do_carteiro()})

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
            elif rota == "/vilanova-paisagem.webp":
                # o celular deitado: o mundo inteiro numa fileira
                corpo = vila_nova.imagem_da_paisagem(noite)
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

    def _arte_da_vila(self, rota: str):
        """`/arte-vila/<nome_arquivo>`: uma folha aprovada pela esteira.

        Nada de juntar a URL com uma pasta: `arte_pronta.arquivo_publico`
        so devolve o que esta no indice (peca do inventario que existe em
        `painel/flutuante/arte_vila`). O resto e 404, inclusive `..`.
        """
        try:
            from painel.flutuante import arte_pronta
            arquivo = arte_pronta.arquivo_publico(rota)
            corpo = arquivo.read_bytes() if arquivo is not None else None
        except (OSError, ValueError):
            corpo = None
        if corpo is None:
            return self._erro(404, "nao existe")
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
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
        if nome == "index.html":
            corpo = corpo.replace(b'<meta name="casca" content="">',
                                  f'<meta name="casca" content="{versao_da_casca()}">'
                                  .encode("utf-8"), 1)
        self.send_response(200)
        self._cabecalhos_comuns(tipo, len(corpo), cache=True)
        if nome.endswith(".html"):
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' blob:; media-src 'self' blob:; "
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
        # A imagem gerada pelas IAs (29/09) pode passar da fatia (um PNG do
        # ChatGPT tem 2-3 MB, e ha folga): ela vem inteira ate IMAGEM_MAX, que
        # um `<img>` truncado num 206 nao remonta.
        if (tipo.startswith("image/") and not self.headers.get("Range")
                and total <= max(FATIA_MAX, IMAGEM_INTEIRA_MAX)):
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

    def _video_da_arena(self, luta_id: str, consulta: dict):
        """MP4 da Arena pelo id conhecido e token da URL, com Range para avancar."""
        if self._aparelho_do_video_da_arena(consulta) is None:
            return
        arquivo = pasta_da_arena() / luta_id / "luta.mp4"
        if not arquivo.is_file():
            return self._erro(404, "video nao encontrado")
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
                while tamanho > 0:
                    pedaco = fh.read(min(65536, tamanho))
                    if not pedaco:
                        break
                    self.wfile.write(pedaco)
                    tamanho -= len(pedaco)
        except (ConnectionError, OSError):
            pass

    def _pagina_por_bilhete(self, chave: str):
        pagina, motivo = self.estado.pagina_do_bilhete(chave)
        if motivo == "vencido":
            return self._erro(404, "bilhete vencido; abra a pagina de novo")
        if motivo == "revogado":
            return self._erro(403, "aparelho esquecido")
        if pagina is None:
            if not self._barrar_chute():
                self._erro(404, "bilhete desconhecido")
            return
        fragmento = biblioteca.ler_pagina(pagina)
        if fragmento is None:
            return self._erro(404, "pagina nao encontrada")
        if not re.search(r"<html(?:\s|>)", fragmento, re.IGNORECASE):
            fragmento = ("<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n"
                         "<meta charset=\"utf-8\">\n"
                         "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
                         "<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n"
                         "</head>\n<body>\n" + fragmento + "\n</body>\n</html>\n")
        corpo = fragmento.encode("utf-8")
        self.send_response(200)
        self._cabecalhos_comuns("text/html; charset=utf-8", len(corpo))
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
            "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(corpo)


def _imagem():
    """O catalogo dos geradores de imagem (`ias.imagem`, lido das fichas)."""
    from ias import imagem
    return imagem


def _correio():
    """O modulo do correio (tarde, para os testes trocarem e para o servidor
    subir mesmo sem o pacote `ias` no caminho)."""
    from ias import correio
    return correio


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

    A fila de escuta (`listen`) era a do socketserver, 5: no Windows, a
    sexta conexao que chega antes do `accept` leva RST. Uma carga da pagina
    abre ~8 de uma vez (os scripts) com as /api da carga anterior ainda em
    voo, e o `tailscale serve` troca a recusa por 502. Medido em 30/09
    (tarefa 74856214), recarregando no `load` como o app faz: com 5, 22 de
    145 cargas perderam um script por ERR_CONNECTION_REFUSED; com 64, 0 de
    170. Foi assim que o celular ficou sem o conversa.js (sem "Conversar"
    nem "Criar") das 12:01 as 13:15 de 30/09.
    """
    daemon_threads = True
    request_queue_size = 64

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
    print(f"{datetime.now():%d/%m/%Y %H:%M:%S} "
          f"App do celular em http://{host}:{porta}/  (Ctrl+C para parar)"
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
    # comando pendente ha mais de 2 min sem ninguem ouvindo: um aviso no
    # Telegram por ocorrencia (e um quando o orquestrador volta)
    orquestrador.AVISO_SEM_OUVINTE.iniciar()
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
