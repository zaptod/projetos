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

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import (acoes, biblioteca, claude_estado, comandos_app, decisoes, delegar, orquestrador,
               painel_dados, tarefas, vila_dados, vila_nova)
from .config import runtime_dir
from esteira_sprites import aprovar as sprites_aprovar
from esteira_sprites import config as sprites_config
from esteira_sprites import juiz as sprites_juiz
from painel.sprites import importar as sprites_importar
from painel.sprites import recortador as sprites_recortador
from neural_fights.tools import manifesto_sprites

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
PARTES_BIBLIOTECA = Path(__file__).resolve().parents[1] / "palco" / "biblioteca"
MANIFESTO_SPRITES = PARTES_BIBLIOTECA / "manifesto_slots.json"
GODOT_PREVIA = Path("E:/ferramentas/godot/Godot_v4.7.2-stable_win64_console.exe")
GODOT_RAIZ = Path(__file__).resolve().parents[1] / "palco"
# A folha do Godot com o PC ocupado levou 62 s (conferente, 06/10/2026); com
# 45 s ela era parada no meio. A tela espera um pouco mais que isto.
GODOT_TIMEOUT_S = 150
SPRITE_MAX = 20 * 1024 * 1024
RECORTADOR_SESSOES = 4               # folhas do recortador guardadas por aparelho
# A resposta do Adrian sobre o par de olhos desenhado de frente (o padrao da
# tela do recortador); pendente = "separar", a recomendada.
DECISAO_OLHOS = ("builds", "recortador-par-de-olhos")
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
# O celular que fecha a conexao no meio da resposta (trocou de tela, perdeu a
# rede, o `tailscale serve` desistiu) nao e erro do servidor. Varredura de
# 05/10/2026 (item 22): 221 linhas de ConnectionAbortedError no
# app_celular.txt; cada uma era "GET /api/equipe 200" seguido de "500" e de
# DOIS tracebacks, porque o `except Exception` da rota chamava `_erro`, que
# escrevia de novo no socket morto. Agora vira uma linha "saiu" e mais nada.
CLIENTE_SAIU = (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)

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
    "/provador.js": ("provador.js", "text/javascript; charset=utf-8"),
    # o desenho de hoje da bolinha (folha do Godot sem pecas), para a previa vazia
    "/bolinha_hoje.png": ("bolinha_hoje.png", "image/png"),
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


# ============================================================ sprites modulares
# Indice em memoria do que existe no disco: o manifesto (1.867 lugares) e
# lido uma vez por versao do arquivo, e o que existe sai de UMA varredura da
# arvore partes/ (em 06/10 cada pedido fazia 1.299 is_file + heranca e levava
# 2,8-3,0 s). Anexar, apagar e desfazer atualizam o indice na hora; quem mexe
# no disco por fora (importar-antigas) aparece em ate INDICE_VALIDADE_S.
GRUPOS_SPRITES = ("lutador", "arma", "skill", "efeito", "camada_estado", "arena", "hud")
INDICE_VALIDADE_S = 20.0
_INDICE_SPRITES: dict = {"chave": None, "base": None, "existe": None, "quando": 0.0, "geracao": 0}
_TRAVA_INDICE = threading.Lock()


def _base_do_indice(chave) -> dict:
    try:
        dados = json.loads(MANIFESTO_SPRITES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    if not isinstance(dados, dict) or not isinstance(dados.get("slots"), list):
        dados = {"slots": []}
    por_id, id_por_arquivo, por_alvo, alvos = {}, {}, {}, {}
    raiz = os.path.normcase(os.path.abspath(PARTES_BIBLIOTECA))
    for slot in dados["slots"]:
        if not isinstance(slot, dict) or not slot.get("id"):
            continue
        sid = str(slot["id"])
        por_id[sid] = slot
        partes = Path(str(slot.get("destino", "")).replace("\\", "/")).parts
        if "biblioteca" in partes:
            relativo = os.path.join(*partes[partes.index("biblioteca") + 1:])
            id_por_arquivo[os.path.normcase(os.path.join(raiz, relativo))] = sid
        grupo = str(slot.get("grupo", ""))
        alvo = slot.get("alvo") or {}
        chave_alvo = str(alvo.get("chave", "_"))
        por_alvo.setdefault((grupo, chave_alvo), []).append(slot)
        lista = alvos.setdefault(grupo, {})
        if chave_alvo not in lista:
            lista[chave_alvo] = {"chave": chave_alvo, "nivel": alvo.get("nivel"),
                                 "rotulo": manifesto_sprites.nome_do_alvo(alvo, grupo)}
    for grupo, lista in alvos.items():
        # O comum primeiro; o resto na ordem do manifesto.
        alvos[grupo] = sorted(lista.values(), key=lambda a: a["chave"] != "_")
    return {"chave": chave, "manifesto": dados, "por_id": por_id, "id_por_arquivo": id_por_arquivo,
            "por_alvo": por_alvo, "alvos": alvos, "raiz": raiz}


def _varrer_existentes(base: dict) -> tuple[set, set, dict, dict]:
    existe, com_versao, variantes, apagadas = set(), set(), {}, {}
    mapa = base["id_por_arquivo"]
    for pasta, subpastas, arquivos in os.walk(os.path.join(base["raiz"], "partes")):
        if os.path.basename(pasta) == APAGADAS:
            # Variantes apagadas (o Desfazer as traz): so contam, nunca existem.
            relativo = Path(pasta).relative_to(base["raiz"]).parts
            if len(relativo) == 6 and relativo[:2] == ("partes", "lutador"):
                total = sum(1 for nome in subpastas if _APAGADA_RE.fullmatch(nome))
                if total:
                    apagadas[(relativo[2], relativo[3], relativo[4])] = total
            subpastas[:] = []
            continue
        if pasta.lower().endswith(".png.historico"):
            subpastas[:] = []
            if any(a.lower().endswith(".png") for a in arquivos):
                sid = mapa.get(os.path.normcase(pasta[:-len(".historico")]))
                if sid:
                    com_versao.add(sid)
            continue
        for nome in arquivos:
            if nome.lower().endswith(".png"):
                sid = mapa.get(os.path.normcase(os.path.join(pasta, nome)))
                if sid:
                    existe.add(sid)
                # Variantes alem de v01 nao existem no manifesto: o nome do
                # diretorio e a autoridade, e o indice continua uma varredura.
                relativo = Path(pasta).relative_to(base["raiz"]).parts
                if len(relativo) == 6 and relativo[:2] == ("partes", "lutador") and relativo[5].startswith("v"):
                    chave = (relativo[2], relativo[3], relativo[4])
                    variantes.setdefault(chave, {}).setdefault(relativo[5], set()).add(Path(nome).stem)
                    existe.add("lutador/%s/%s/%s/%s" % (relativo[2], relativo[3], relativo[4], Path(nome).stem))
    return existe, com_versao, variantes, apagadas


def _indice_sprites(mudou: str | None = None) -> dict:
    """O indice atual; `mudou` = id de um lugar que esta resposta acabou de mexer."""
    try:
        marca = MANIFESTO_SPRITES.stat().st_mtime_ns
    except OSError:
        marca = None
    chave = (str(PARTES_BIBLIOTECA), str(MANIFESTO_SPRITES), marca)
    with _TRAVA_INDICE:
        estado = _INDICE_SPRITES
        if estado["chave"] != chave:
            estado.update({"chave": chave, "base": _base_do_indice(chave), "existe": None})
        base = estado["base"]
        agora = time.monotonic()
        if estado["existe"] is None or agora - estado["quando"] > INDICE_VALIDADE_S:
            (estado["existe"], estado["com_versao"], estado["variantes"],
             estado["apagadas"]) = _varrer_existentes(base)
            estado["quando"] = agora
        if mudou and mudou in base["por_id"]:
            # Uma variante nova nao tem id no manifesto; revarrer mantem a
            # escolha e a galeria coerentes logo na resposta que a criou.
            (estado["existe"], estado["com_versao"], estado["variantes"],
             estado["apagadas"]) = _varrer_existentes(base)
            estado["quando"] = agora
            estado["geracao"] += 1
        return {**base, "existe": set(estado["existe"]), "com_versao": set(estado["com_versao"]),
                "variantes": {k: {v: set(e) for v, e in valores.items()} for k, valores in estado.get("variantes", {}).items()},
                "apagadas": dict(estado.get("apagadas", {})), "geracao": estado["geracao"]}


def _existe_no_indice(indice: dict):
    existe = indice["existe"]
    return lambda parte, nivel, alvo, estado: f"lutador/{parte}/{nivel}/{alvo}/{estado}" in existe


def _variantes_no_indice(indice: dict):
    return lambda parte, nivel, alvo: indice["variantes"].get((parte, nivel, alvo), {})


# "Carinha" e feminino: "a carinha neutra", nao "neutro". Os nomes que sao
# substantivos (fúria, pânico, dor) ficam como estao.
_CARINHA_FEMININA = {
    "neutro": "neutra", "focado": "focada", "determinado": "determinada", "animado": "animada",
    "eufórico": "eufórica", "nervoso": "nervosa", "morto": "morta", "tonto": "tonta",
    "confuso": "confusa", "concentrado": "concentrada",
}


def _situacao_do_slot(slot: dict, indice: dict) -> tuple[str, str]:
    """anexado | herdando | vazio. 'Herdando' so quando o jogo de fato usa
    outra peca no lugar desta (a regra do palco, partes_lutador.gd)."""
    sid = str(slot.get("id"))
    if sid in indice["existe"]:
        return "anexado", ""
    alvo = slot.get("alvo") or {}
    if slot.get("grupo") == "lutador":
        parte = str(slot.get("parte"))
        estado = str(slot.get("estado") or "base")
        classe = str(alvo.get("chave")) if alvo.get("nivel") == "classe" else ""
        achado = manifesto_sprites.resolver_parte(
            parte, classe, estado if estado != "base" else "neutro", _existe_no_indice(indice))
        if achado is None:
            return "vazio", ""
        if achado["nivel"] != alvo.get("nivel"):
            return "herdando", "o jogo usa a peça comum"
        nome = manifesto_sprites.nome_do_estado(achado["estado"]) or "base"
        return "herdando", f"o jogo usa a carinha {_CARINHA_FEMININA.get(nome, nome)} deste estilo"
    for outro in slot.get("fallback") or []:
        if outro in indice["existe"]:
            outro_slot = indice["por_id"].get(outro) or {}
            nome = manifesto_sprites.nome_do_alvo(outro_slot.get("alvo") or {}, str(slot.get("grupo")))
            return "herdando", f"o jogo usa a peça de {nome.lower()}"
    return "vazio", ""


def _progresso_sprites(indice: dict) -> dict:
    """Os tres contadores do topo, pela tabela 'Quantos o Adrian precisa'
    do CONTRATO_SLOTS.md: 3 basicos, 14 do rosto que reage, 16 classes."""
    existe = indice["existe"]
    basico = ["lutador/pele/comum/_/base", "lutador/olhos/comum/_/neutro", "lutador/boca/comum/_/neutro"]
    rosto = ["lutador/pele/comum/_/base", "lutador/sombra/comum/_/base"] + [
        f"lutador/{parte}/comum/_/{e}" for parte in ("olhos", "boca")
        for e in manifesto_sprites.REPRESENTANTES]
    classes = [a["chave"] for a in indice["alvos"].get("lutador", []) if a.get("nivel") == "classe"]
    com_identidade = [c for c in classes if any(
        f"lutador/{parte}/classe/{c}/base" in existe for parte in ("acessorio_cabeca", "acessorio_costas"))]
    return {"basico": [sum(s in existe for s in basico), len(basico)],
            "rosto": [sum(s in existe for s in rosto), len(rosto)],
            "classes": [len(com_identidade), len(classes)]}


# A previa do Godot (~2-7 s): uma por vez, mais UMA na fila. O estado e por
# estilo (alvo): pedir a folha do Berserker nao devolve a do comum. Uma folha
# pronta vale enquanto a geracao do indice for a mesma (anexou: refaz).
_PREVIAS_GODOT: dict[str, dict] = {}
_FILA_GODOT: list[str] = []
_TRAVA_PREVIA_GODOT = threading.Lock()
_GODOT_OCUPADO = {"alvo": None}


_PEDIDOS_GODOT: dict[str, dict] = {}       # chave "prov:..." -> o lutador e a combinacao


def pedir_previa_godot(alvo: str, pedido: dict | None = None) -> tuple[str, object]:
    """('pronta', bytes) | ('erro', frase) | ('montando'|'na_fila', None).

    `alvo` e o estilo (painel de anexo) ou a chave de um pedido do provador
    (`prov:<lutador>:<combinacao>`, com o `pedido` junto)."""
    geracao = _indice_sprites()["geracao"]
    with _TRAVA_PREVIA_GODOT:
        if pedido is not None:
            _PEDIDOS_GODOT[alvo] = pedido
            # Combinacoes velhas do provador nao se acumulam: so as 12 ultimas.
            velhas = [c for c in _PREVIAS_GODOT if c.startswith("prov:") and c != alvo
                      and _PREVIAS_GODOT[c].get("estado") not in ("montando", "na_fila")]
            for chave in velhas[:-12]:
                _PREVIAS_GODOT.pop(chave, None)
                _PEDIDOS_GODOT.pop(chave, None)
        atual = _PREVIAS_GODOT.get(alvo)
        if atual and atual["estado"] in ("montando", "na_fila"):
            return atual["estado"], None
        if atual and atual.get("geracao") == geracao:
            if atual["estado"] == "pronta":
                with contextlib.suppress(OSError):
                    return "pronta", Path(atual["arquivo"]).read_bytes()
            elif atual["estado"] == "erro":
                _PREVIAS_GODOT.pop(alvo, None)   # o proximo toque tenta de novo
                return "erro", atual["erro"]
        if _GODOT_OCUPADO["alvo"] is None:
            _GODOT_OCUPADO["alvo"] = alvo
            _PREVIAS_GODOT[alvo] = {"estado": "montando", "geracao": geracao}
            threading.Thread(target=_trabalhar_previas_godot, args=(alvo,), daemon=True).start()
            return "montando", None
        for antigo in _FILA_GODOT:          # fila de 1: o pedido novo toma o lugar
            _PREVIAS_GODOT.pop(antigo, None)
        _FILA_GODOT[:] = [alvo]
        _PREVIAS_GODOT[alvo] = {"estado": "na_fila", "geracao": geracao}
        return "na_fila", None


def _trabalhar_previas_godot(alvo: str) -> None:
    while alvo is not None:
        geracao = _indice_sprites()["geracao"]
        with _TRAVA_PREVIA_GODOT:
            pedido = _PEDIDOS_GODOT.get(alvo)
        if alvo.startswith("prov:") and pedido is not None:
            resultado = _rodar_previa_provador(pedido)
        else:
            resultado = _rodar_previa_godot(alvo, PARTES_BIBLIOTECA)
        with _TRAVA_PREVIA_GODOT:
            _PREVIAS_GODOT[alvo] = {**resultado, "geracao": geracao}
            alvo = _FILA_GODOT.pop(0) if _FILA_GODOT else None
            _GODOT_OCUPADO["alvo"] = alvo
            if alvo is not None:
                _PREVIAS_GODOT[alvo] = {"estado": "montando", "geracao": geracao}


def _rodar_previa_godot(alvo: str, biblioteca: Path) -> dict:
    """Roda a folha das seis carinhas no Godot e devolve o estado final."""
    try:
        pasta = runtime_dir() / "previas_sprites"
        pasta.mkdir(parents=True, exist_ok=True)
        saida = pasta / f"folha_{re.sub(r'[^a-z0-9_]', '_', alvo.lower()) or 'comum'}.png"
    except OSError:
        return {"estado": "erro", "erro": "não consegui abrir o Godot neste PC"}
    return _godot_folha('' if alvo == '_' else alvo, "", biblioteca, saida)


def _olhos_padrao() -> str:
    """O modo do par de olhos que a tela abre: a resposta vigente do Adrian no
    Grimorio, ou "separar" (a recomendada) enquanto ele nao responde."""
    try:
        item = json.loads(decisoes.caminho_item(*DECISAO_OLHOS).read_text(encoding="utf-8"))
        opcao = str(((item.get("vigente") or {}).get("opcao")) or "")
    except (OSError, ValueError, AttributeError):
        opcao = ""
    return opcao if opcao in sprites_recortador.MODOS_OLHOS else "separar"


def _parar_arvore(processo: subprocess.Popen) -> None:
    """O `_console.exe` do Godot abre o Godot de verdade como FILHO: matar so
    o console deixava o Godot rodando (e a GPU ocupada) depois do estouro."""
    if os.name == "nt":
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(["taskkill", "/PID", str(processo.pid), "/T", "/F"],
                           capture_output=True, timeout=20, creationflags=NO_WINDOW)
    with contextlib.suppress(OSError):
        processo.kill()
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        processo.communicate(timeout=10)


def _godot_folha(classe: str, personagem: str, biblioteca: Path, saida: Path, cor=None) -> dict:
    """O Godot de verdade: a folha das seis carinhas de `classe`/`personagem`.

    `cor` (r, g, b) vai como `--cor=#RRGGBB`: a folha pinta as seis bolinhas
    com a cor DELE (bfb6b35, parte builds); sem ela o Godot procura o nome no
    banco, e o lutador de exemplo fica com as cores de exemplo."""
    try:
        with contextlib.suppress(OSError):
            saida.unlink()
        cmd = [str(GODOT_PREVIA), "--path", str(GODOT_RAIZ),
               "res://ferramentas/previa_sprites.tscn", "--",
               f"--classe={classe}", f"--personagem={personagem}",
               f"--biblioteca={biblioteca}", f"--saida={saida}"]
        if cor is not None:
            cmd.append("--cor=#%02X%02X%02X" % tuple(max(0, min(255, int(c))) for c in tuple(cor)[:3]))
        processo = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                    encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        try:
            processo.communicate(timeout=GODOT_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            _parar_arvore(processo)
            with contextlib.suppress(OSError):
                saida.unlink()
            return {"estado": "erro", "erro": f"o Godot passou de {GODOT_TIMEOUT_S // 60} minutos e foi "
                                              "parado; tente de novo quando o PC estiver mais livre"}
        if processo.returncode == 0 and saida.is_file():
            return {"estado": "pronta", "arquivo": str(saida)}
        return {"estado": "erro", "erro": "o Godot não conseguiu desenhar a folha; tente de novo daqui a pouco"}
    except (OSError, subprocess.SubprocessError):
        return {"estado": "erro", "erro": "não consegui abrir o Godot neste PC"}


# ================================================================ provador
# O "jogo de vestir" do Ateliê (decisão builds/sprites-guarda-roupa, 06/10):
# para UM lutador, de qual nível vem cada peça e qual variante o jogo usa (a
# fixada no guarda-roupa ou o sorteio fixo de `personagem:parte`). O que ele
# experimenta nas setas e no dado mora só na tela (`escolha`, devolvida a cada
# pedido); só o Fixar grava `partes/guarda_roupa.json`, que o palco lê.
ARQUIVO_PERSONAGENS: Path | None = None      # os testes trocam; None = o banco do jogo
PREFIXO_EXEMPLO = "exemplo-"
COR_EXEMPLO = (216, 101, 101)                # a primeira bolinha da folha do Godot
PROVADOR_PASTAS_GUARDADAS = 6                # bibliotecas temporárias do "Ver no Godot"
VARIANTE_RE = re.compile(r"v[0-9a-z_-]{1,20}")
APAGADAS = ".apagadas"                       # variante apagada (o Desfazer a traz de volta)
_APAGADA_RE = re.compile(r"(\d{20})-(v[0-9a-z_-]{1,20})")
_PERSONAGENS: dict = {"chave": None, "lista": [], "por_id": {}}
_TRAVA_PERSONAGENS = threading.Lock()
_TRAVA_GUARDA_ROUPA = threading.Lock()


class GuardaRoupaIlegivel(ValueError):
    """O guarda_roupa.json existe e não abre: nada é gravado por cima dele."""


def _arquivo_personagens() -> Path:
    """O mesmo par que o jogo lê: o do usuário quando existe, senão o do pacote."""
    if ARQUIVO_PERSONAGENS is not None:
        return Path(ARQUIVO_PERSONAGENS)
    from neural_fights.data import database
    runtime = Path(database.resolver_runtime_data_dir())
    if (runtime / "personagens.json").is_file() and (runtime / "armas.json").is_file():
        return runtime / "personagens.json"
    return Path(database.ARQUIVO_CHARS)


def _personagens() -> dict:
    """Os lutadores do banco: `id` é o slug do nome (a chave do guarda-roupa)."""
    arquivo = _arquivo_personagens()
    try:
        marca = arquivo.stat().st_mtime_ns
    except OSError:
        marca = None
    chave = (str(arquivo), marca)
    with _TRAVA_PERSONAGENS:
        if _PERSONAGENS["chave"] == chave:
            return _PERSONAGENS
        try:
            bruto = json.loads(arquivo.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            bruto = []
        lista, por_id = [], {}
        for item in bruto if isinstance(bruto, list) else []:
            nome = str(item.get("nome") or "").strip() if isinstance(item, dict) else ""
            ident = manifesto_sprites.slug(nome)
            if not ident or ident in por_id:
                continue
            cor = []
            for campo in ("cor_r", "cor_g", "cor_b"):
                try:
                    cor.append(max(0, min(255, int(float(item.get(campo, 200))))))
                except (TypeError, ValueError):
                    cor.append(200)
            por_id[ident] = {"id": ident, "nome": nome, "classe": manifesto_sprites.slug(item.get("classe")),
                             "cor": tuple(cor)}
            lista.append(por_id[ident])
        lista.sort(key=lambda p: p["id"])
        _PERSONAGENS.update({"chave": chave, "lista": lista, "por_id": por_id})
        return _PERSONAGENS


def _classes_do_lutador(indice: dict) -> dict:
    """{chave: "Berserker (Fúria)"}, na ordem do manifesto."""
    return {a["chave"]: a["rotulo"] for a in indice["alvos"].get("lutador", []) if a.get("nivel") == "classe"}


def _lutador_do_provador(ident: str, indice: dict) -> dict | None:
    classes = _classes_do_lutador(indice)
    if ident.startswith(PREFIXO_EXEMPLO):
        classe = ident[len(PREFIXO_EXEMPLO):]
        if classe not in classes:
            return None
        # Sem personagem o jogo sorteia pela classe (a folha do Godot faz igual).
        return {"id": ident, "nome": "Lutador de exemplo", "classe": classe, "classe_nome": classes[classe],
                "exemplo": True, "cor": COR_EXEMPLO, "chave_sorteio": classe, "nome_jogo": ""}
    achado = _personagens()["por_id"].get(ident)
    if achado is None:
        return None
    return {**achado, "classe_nome": classes.get(achado["classe"], manifesto_sprites.texto_humano(achado["classe"])),
            "exemplo": False, "chave_sorteio": achado["nome"], "nome_jogo": achado["nome"]}


def _arquivo_guarda_roupa() -> Path:
    return PARTES_BIBLIOTECA / "partes" / "guarda_roupa.json"


def _ler_guarda_roupa(estrito: bool = False) -> dict:
    """{personagem: {parte: variante}}. Ilegível: {} na leitura da tela, erro
    quando a resposta vai gravar (`estrito`), para não apagar o que ele fixou."""
    try:
        dados = json.loads(_arquivo_guarda_roupa().read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        if estrito:
            raise GuardaRoupaIlegivel("o guarda-roupa do PC não abre; nada foi mudado") from None
        return {}
    if not isinstance(dados, dict):
        if estrito:
            raise GuardaRoupaIlegivel("o guarda-roupa do PC não abre; nada foi mudado")
        return {}
    return {str(p): {str(k): str(v) for k, v in f.items()} for p, f in dados.items() if isinstance(f, dict)}


def _gravar_guarda_roupa(dados: dict) -> None:
    """Escrita atômica (arquivo novo + os.replace): o Godot nunca lê meio arquivo."""
    arquivo = _arquivo_guarda_roupa()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    limpo = {p: dict(sorted(f.items())) for p, f in sorted(dados.items()) if f}
    texto = json.dumps(limpo, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporario = arquivo.with_name(f".{arquivo.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    with open(temporario, "w", encoding="utf-8", newline="\n") as saida:
        saida.write(texto)
        saida.flush()
        os.fsync(saida.fileno())
    for tentativa in range(5):
        try:
            os.replace(temporario, arquivo)
            return
        except PermissionError:                  # o Godot lendo naquele instante
            if tentativa == 4:
                with contextlib.suppress(OSError):
                    temporario.unlink()
                raise
            time.sleep(0.05)


def _mudar_guarda_roupa(mudar) -> dict:
    """Lê (estrito), aplica `mudar(dados)` e grava, sob a trava; sem mudança, não grava."""
    with _TRAVA_GUARDA_ROUPA:
        dados = _ler_guarda_roupa(estrito=True)
        antes = json.dumps(dados, sort_keys=True)
        mudar(dados)
        if json.dumps(dados, sort_keys=True) != antes:
            _gravar_guarda_roupa(dados)
        return dados


def _escolha_normalizada(bruto) -> dict:
    """'olhos:v02,boca:v01' ou {"olhos": "v02"} -> {parte: variante}; o resto cai fora."""
    if isinstance(bruto, dict):
        pares = list(bruto.items())
    else:
        pares = [pedaco.partition(":")[::2] for pedaco in str(bruto or "").split(",")]
    return {str(p): str(v) for p, v in pares[:20]
            if str(p) in manifesto_sprites.CAMADA_Z and VARIANTE_RE.fullmatch(str(v))}


def _texto_da_escolha(escolha: dict) -> str:
    return ",".join(f"{p}:{v}" for p, v in sorted(escolha.items()))


def _pecas_do_lutador(lutador: dict, indice: dict, escolha: dict, fixadas: dict) -> list[dict]:
    """Cada peça com desenho: o dono, as variantes, a do sorteio, a fixada e a da tela."""
    variantes = _variantes_no_indice(indice)
    pecas = []
    for parte in sorted(manifesto_sprites.CAMADA_Z, key=manifesto_sprites.CAMADA_Z.get):
        dono = manifesto_sprites.dono_da_parte(parte, lutador["classe"], variantes, lutador["nome_jogo"])
        if dono is None:
            continue
        nivel, alvo, colecao = dono
        sorteada = manifesto_sprites.variante_escolhida(colecao, "", lutador["chave_sorteio"], parte)
        fixada = str(fixadas.get(parte) or "")
        valida = fixada if fixada in colecao else ""
        pedida = escolha.get(parte) if escolha.get(parte) in colecao else ""
        guardada = valida or sorteada
        atual = pedida or guardada
        situacao = "experimento" if pedida and pedida != guardada else ("fixada" if valida else "sorteio")
        pecas.append({"parte": parte, "nivel": nivel, "alvo": alvo, "colecao": colecao,
                      "ordem": sorted(colecao), "sorteada": sorteada, "fixada": valida, "atual": atual,
                      "situacao": situacao, "fixa_perdida": bool(fixada) and not valida})
    return pecas


def _arquivo_da_variante(parte: str, nivel: str, alvo: str, variante: str, estado: str) -> Path | None:
    """`partes/lutador/<parte>/<nivel>/<alvo>/<vNN>/<estado>.png`, o mesmo nome
    que o palco procura; cada pedaço é conferido antes de virar caminho."""
    if (parte not in manifesto_sprites.CAMADA_Z or nivel not in ("personagem", "classe", "comum")
            or not re.fullmatch(r"[a-z0-9_]{1,80}", alvo or "") or not VARIANTE_RE.fullmatch(variante or "")
            or not re.fullmatch(r"[a-z_]{1,30}", estado or "")):
        return None
    return PARTES_BIBLIOTECA / "partes" / "lutador" / parte / nivel / alvo / variante / f"{estado}.png"


def _tingir_da_peca(arquivo: Path, nivel: str) -> str:
    """O mesmo `PartesLutador.tingir`: o .json ao lado manda; sem ele, a pele
    comum é máscara tingida pela cor do personagem."""
    with contextlib.suppress(OSError, ValueError, AttributeError):
        dados = json.loads(arquivo.with_suffix(".json").read_text(encoding="utf-8-sig"))
        return str(dados.get("tingir", "nenhum"))
    return "cor_personagem" if nivel == "comum" else "nenhum"


MINIATURA_PX = 160


def _miniatura_png(peca: Image.Image, lado: int = MINIATURA_PX, parte: str = "") -> bytes:
    """A miniatura do cartão, da galeria e do Provador: RECORTADA e ampliada
    até `lado`. A peça vem no gabarito 1024 (o olho mora numa zona de 165
    px): inteira, a miniatura de 64 px mostrava um olho de ~15 px
    (conferente, 07/10). A margem de 6% deixa ver a borda do desenho.

    Peça de lutador com zona no CONTRATO 2.3 (olhos, boca, sombra…): o recorte
    é a ZONA (mais o que passar dela), igual para todas as variantes. Assim
    as miniaturas lado a lado ficam na MESMA escala e um olho menor aparece
    menor (v54 recortava cada uma no próprio desenho e escondia a diferença;
    conferente, 07/10)."""
    caixa = peca.getchannel("A").point(lambda v: 255 if v >= 16 else 0).getbbox()
    zona = sprites_recortador.ZONAS.get(parte) if peca.size == (1024, 1024) else None
    if zona and zona != (0, 0, 1024, 1024):
        caixa = zona if not caixa else (min(caixa[0], zona[0]), min(caixa[1], zona[1]),
                                        max(caixa[2], zona[2]), max(caixa[3], zona[3]))
    if caixa:
        x0, y0, x1, y1 = caixa
        margem = max(2, round(0.06 * max(x1 - x0, y1 - y0)))
        peca = peca.crop((max(0, x0 - margem), max(0, y0 - margem),
                          min(peca.width, x1 + margem), min(peca.height, y1 + margem)))
    escala = lado / max(peca.size)
    tamanho = (max(1, round(peca.width * escala)), max(1, round(peca.height * escala)))
    peca = peca.resize(tamanho, Image.Resampling.LANCZOS)
    saida = io.BytesIO()
    peca.save(saida, "PNG", optimize=True)
    return saida.getvalue()


def _abrir_peca(arquivo: Path, parte: str, nivel: str, cor) -> Image.Image | None:
    try:
        with Image.open(arquivo) as imagem:
            peca = imagem.convert("RGBA")
    except (OSError, ValueError):
        return None
    if parte == "pele" and _tingir_da_peca(arquivo, nivel) == "cor_personagem":
        # O Godot desenha a pele com `modulate` = cor do personagem (multiplica).
        r, g, b, a = peca.split()
        r, g, b = (canal.point(lambda v, k=k: v * k // 255) for canal, k in zip((r, g, b), cor))
        peca = Image.merge("RGBA", (r, g, b, a))
    return peca


def _lutador_publico(lutador: dict, fixadas: dict | None = None) -> dict:
    return {"id": lutador["id"], "nome": lutador["nome"], "classe": lutador["classe"],
            "classe_nome": lutador["classe_nome"], "exemplo": lutador["exemplo"],
            "fixadas": len(fixadas or {})}


def _expressoes_publicas() -> list[dict]:
    """As 24 carinhas, por família (as 6 principais na ordem do contrato)."""
    return [{"id": e, "nome": manifesto_sprites.NOMES_DAS_EXPRESSOES[e],
             "familia": manifesto_sprites.FAMILIA[e],
             "representante": e in manifesto_sprites.REPRESENTANTES}
            for e in sorted(manifesto_sprites.EXPRESSOES, key=lambda e: (
                manifesto_sprites.REPRESENTANTES.index(manifesto_sprites.FAMILIA[e]),
                e not in manifesto_sprites.REPRESENTANTES))]


def _dono_humano(nivel: str, lutador: dict) -> str:
    if nivel == "comum":
        return "peça comum (todos os lutadores)"
    if nivel == "classe":
        return f"peça da classe {lutador['classe_nome']}"
    return "peça só deste lutador"


def provador_resposta(lutador: dict, escolha: dict, expressao: str, aviso: str = "") -> dict:
    """O que a tela do provador precisa: curto (poucos KB) e sem caminho do PC."""
    from urllib.parse import quote
    indice = _indice_sprites()
    guarda = {} if lutador["exemplo"] else _ler_guarda_roupa()
    fixadas = guarda.get(lutador["id"], {})
    pecas = _pecas_do_lutador(lutador, indice, escolha, fixadas)
    efetiva = {p["parte"]: p["atual"] for p in pecas if p["situacao"] == "experimento"}
    base = (f"lutador={quote(lutador['id'])}&expressao={quote(expressao)}"
            f"&escolha={quote(_texto_da_escolha(efetiva))}&v={indice['geracao']}")
    publicas = []
    for p in pecas:
        publicas.append({
            "parte": p["parte"], "nome": manifesto_sprites.nome_da_parte(p["parte"]),
            "dono": _dono_humano(p["nivel"], lutador), "ordem": p["ordem"], "atual": p["atual"],
            "indice": p["ordem"].index(p["atual"]) + 1, "total": len(p["ordem"]),
            "sorteada_indice": p["ordem"].index(p["sorteada"]) + 1,
            "situacao": p["situacao"], "tem_fixa": bool(p["fixada"]), "fixa_perdida": p["fixa_perdida"],
            # A variante sem esta carinha (nem a família, nem a neutra) some na luta.
            "sem_carinha": manifesto_sprites.estado_na_variante(
                p["parte"], expressao, p["colecao"][p["atual"]]) is None,
            "imagens": {v: (f"/api/sprites/provador/peca?lutador={quote(lutador['id'])}&parte={p['parte']}"
                            f"&variante={v}&expressao={quote(expressao)}&v={indice['geracao']}")
                        for v in p["ordem"]}})
    com_desenho = {p["parte"] for p in pecas}
    return {"lutador": _lutador_publico(lutador, {k: v for k, v in fixadas.items()
                                                  if any(p["parte"] == k and p["fixada"] for p in pecas)}),
            "pecas": publicas, "escolha": efetiva, "expressao": expressao,
            "sem_desenho": [manifesto_sprites.nome_da_parte(p) for p in
                            sorted(manifesto_sprites.CAMADA_Z, key=manifesto_sprites.CAMADA_Z.get)
                            if p not in com_desenho],
            "expressoes": _expressoes_publicas(), "pode_fixar": not lutador["exemplo"],
            "previa": "/api/sprites/provador/previa?" + base,
            "godot": "/api/sprites/provador/godot?" + base,
            "godot_previa": GODOT_PREVIA.is_file(), "aviso": aviso}


def provador_lutadores() -> dict:
    indice = _indice_sprites()
    classes = _classes_do_lutador(indice)
    guarda = _ler_guarda_roupa()
    lutadores = []
    for p in _personagens()["lista"]:
        lutadores.append({"id": p["id"], "nome": p["nome"], "classe": p["classe"],
                          "classe_nome": classes.get(p["classe"], manifesto_sprites.texto_humano(p["classe"])),
                          "fixadas": len(guarda.get(p["id"], {}))})
    return {"lutadores": lutadores,
            "classes": [{"chave": c, "rotulo": r} for c, r in classes.items()],
            "exemplos": [{"id": PREFIXO_EXEMPLO + c, "nome": "Lutador de exemplo", "classe": c,
                          "classe_nome": r, "fixadas": 0} for c, r in classes.items()]}


def _previa_do_provador(lutador: dict, escolha: dict, expressao: str) -> tuple[bytes, int]:
    indice = _indice_sprites()
    fixadas = {} if lutador["exemplo"] else _ler_guarda_roupa().get(lutador["id"], {})
    quadro = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    pecas = 0
    for p in _pecas_do_lutador(lutador, indice, escolha, fixadas):
        estado = manifesto_sprites.estado_na_variante(p["parte"], expressao, p["colecao"][p["atual"]])
        arquivo = _arquivo_da_variante(p["parte"], p["nivel"], p["alvo"], p["atual"], estado or "")
        peca = _abrir_peca(arquivo, p["parte"], p["nivel"], lutador["cor"]) if arquivo else None
        if peca is None:
            continue
        if peca.size != (1024, 1024):
            peca.thumbnail((1024, 1024))
        quadro.alpha_composite(peca, ((1024 - peca.width) // 2, (1024 - peca.height) // 2))
        pecas += 1
    saida = io.BytesIO()
    quadro.resize((512, 512), Image.Resampling.LANCZOS).save(saida, "PNG", optimize=True)
    return saida.getvalue(), pecas


def _pasta_do_alvo(slot: dict) -> Path | None:
    """A pasta das variantes de um lugar de lutador (`.../<parte>/<nivel>/<alvo>`)."""
    if not isinstance(slot, dict) or slot.get("grupo") != "lutador":
        return None
    alvo = slot.get("alvo") or {}
    arquivo = _arquivo_da_variante(str(slot.get("parte")), str(alvo.get("nivel")), str(alvo.get("chave")),
                                   "v01", "neutro")
    return arquivo.parent.parent if arquivo else None


def _proxima_variante(pasta: Path) -> str:
    """O menor vNN livre NO DISCO (a mesma regra do anexo `nova`)."""
    numero = 1
    while (pasta / f"v{numero:02d}").exists():
        numero += 1
    return f"v{numero:02d}"


def _quem_fixou(parte: str, nivel: str, alvo: str, variante: str, indice: dict) -> list[str]:
    """Os lutadores cuja escolha fixada de `parte` é ESTA variante deste dono."""
    afetados = []
    personagens = _personagens()["por_id"]
    variantes = _variantes_no_indice(indice)
    for ident, fixas in _ler_guarda_roupa().items():
        if fixas.get(parte) != variante:
            continue
        achado = personagens.get(ident)
        if achado is None:          # fora do banco: só dá para saber no nível dele ou no comum
            dono = (nivel, alvo) if nivel == "comum" or (nivel == "personagem" and alvo == ident) else None
        else:
            dono = manifesto_sprites.dono_da_parte(parte, achado["classe"], variantes, achado["nome"])
            dono = dono[:2] if dono else None
        if dono == (nivel, alvo):
            afetados.append(ident)
    return afetados


def _nomes_dos_lutadores(idents: list[str]) -> list[str]:
    personagens = _personagens()["por_id"]
    return [personagens[i]["nome"] if i in personagens else manifesto_sprites.texto_humano(i) for i in idents]


def _frase_do_sorteio(nomes: list[str]) -> str:
    if not nomes:
        return ""
    if len(nomes) == 1:
        return f" {nomes[0]} usava esta variante fixa e voltou ao sorteio."
    if len(nomes) <= 3:
        return f" {', '.join(nomes[:-1])} e {nomes[-1]} usavam esta variante fixa e voltaram ao sorteio."
    return f" {len(nomes)} lutadores usavam esta variante fixa e voltaram ao sorteio."


def apagar_variante(slot: dict, variante: str) -> dict:
    """Tira a variante INTEIRA (todas as carinhas) para `.apagadas/`; quem a
    tinha fixa volta ao sorteio. Devolve os nomes de quem voltou."""
    pasta = _pasta_do_alvo(slot)
    if pasta is None or not VARIANTE_RE.fullmatch(variante) or not (pasta / variante).is_dir():
        raise LookupError("esta variante não existe mais")
    parte = str(slot.get("parte"))
    alvo = slot.get("alvo") or {}
    afetados = _quem_fixou(parte, str(alvo.get("nivel")), str(alvo.get("chave")), variante, _indice_sprites())
    lixeira = pasta / APAGADAS / f"{time.time_ns():020d}-{variante}"
    lixeira.parent.mkdir(parents=True, exist_ok=True)
    os.replace(pasta / variante, lixeira)
    with contextlib.suppress(OSError):
        (lixeira / "_apagada.json").write_text(json.dumps({"variante": variante, "fixadas": afetados}),
                                               encoding="utf-8")
    if afetados:
        def soltar(dados):
            for ident in afetados:
                if dados.get(ident, {}).get(parte) == variante:
                    dados[ident].pop(parte)
        with contextlib.suppress(GuardaRoupaIlegivel):
            _mudar_guarda_roupa(soltar)
    return {"nomes": _nomes_dos_lutadores(afetados)}


def desfazer_variante(slot: dict) -> dict:
    """Traz de volta a última variante apagada deste lugar (com o nome dela,
    ou o próximo livre) e devolve a escolha fixa a quem a tinha."""
    pasta = _pasta_do_alvo(slot)
    lixeira = pasta / APAGADAS if pasta else None
    entradas = sorted(d for d in lixeira.iterdir() if d.is_dir() and _APAGADA_RE.fullmatch(d.name)) \
        if lixeira and lixeira.is_dir() else []
    if not entradas:
        raise LookupError("não há variante apagada para trazer de volta")
    ultima = entradas[-1]
    original = _APAGADA_RE.fullmatch(ultima.name).group(2)
    meta = {}
    with contextlib.suppress(OSError, ValueError):
        meta = json.loads((ultima / "_apagada.json").read_text(encoding="utf-8"))
    with contextlib.suppress(OSError):
        (ultima / "_apagada.json").unlink()
    nome = original if not (pasta / original).exists() else _proxima_variante(pasta)
    os.replace(ultima, pasta / nome)
    parte = str(slot.get("parte"))
    devolvidos = [str(i) for i in (meta.get("fixadas") or []) if isinstance(i, str)]
    if devolvidos:
        def devolver(dados):
            for ident in devolvidos:
                if parte not in dados.get(ident, {}):
                    dados.setdefault(ident, {})[parte] = nome
        with contextlib.suppress(GuardaRoupaIlegivel):
            _mudar_guarda_roupa(devolver)
    return {"variante": nome, "nomes": _nomes_dos_lutadores(devolvidos)}


def _rodar_previa_provador(pedido: dict) -> dict:
    """A folha do Godot para UM lutador com UMA combinação: uma biblioteca
    temporária só com a variante escolhida de cada peça (o palco não muda e o
    guarda-roupa de verdade não entra)."""
    try:
        base = runtime_dir() / "previas_sprites" / "provador"
        pasta = base / hashlib.sha1(pedido["chave"].encode("utf-8")).hexdigest()[:12]
        shutil.rmtree(pasta, ignore_errors=True)
        for parte, nivel, alvo, variante in pedido["pecas"]:
            origem = _arquivo_da_variante(parte, nivel, alvo, variante, "neutro")
            if origem is None or not origem.parent.is_dir():
                continue
            destino = pasta / "partes" / "lutador" / parte / nivel / alvo / variante
            destino.mkdir(parents=True, exist_ok=True)
            for arquivo in origem.parent.iterdir():
                if arquivo.is_file() and arquivo.suffix.lower() in (".png", ".json"):
                    shutil.copy2(arquivo, destino / arquivo.name)
        pasta.mkdir(parents=True, exist_ok=True)
        velhas = sorted((d for d in base.iterdir() if d.is_dir() and d != pasta),
                        key=lambda d: d.stat().st_mtime, reverse=True)
        for velha in velhas[PROVADOR_PASTAS_GUARDADAS - 1:]:
            shutil.rmtree(velha, ignore_errors=True)
    except OSError:
        return {"estado": "erro", "erro": "não consegui preparar a prévia neste PC"}
    lutador = pedido["lutador"]
    if lutador.get("exemplo") or lutador.get("cor") is None:
        return _godot_folha(lutador["classe"], lutador["nome_jogo"], pasta, pasta / "folha.png")
    return _godot_folha(lutador["classe"], lutador["nome_jogo"], pasta, pasta / "folha.png",
                        cor=lutador["cor"])


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

    # O cliente fechou a conexao (CLIENTE_SAIU): uma linha no log, a conexao
    # marcada para fechar, e nenhuma escrita a mais neste socket.
    _saiu = False

    def _cliente_saiu(self) -> None:
        self.close_connection = True
        if not self._saiu:
            self._saiu = True
            self._log("saiu")

    def _json(self, dados, status: int = 200):
        if self._saiu:
            return
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self._cabecalhos_comuns("application/json; charset=utf-8", len(corpo))
            # a casca do disco e o fuso do PC: o app confere os dois (o `Date`,
            # com o relogio do PC, a biblioteca ja manda)
            with contextlib.suppress(Exception):
                self.send_header("X-Casca", versao_da_casca())
                self.send_header("X-Fuso-Min", str(fuso_do_pc_min()))
            self.end_headers()
            self.wfile.write(corpo)
        except CLIENTE_SAIU:
            self._cliente_saiu()

    def _bytes(self, corpo: bytes, tipo: str):
        if self._saiu:
            return
        try:
            self.send_response(200)
            self._cabecalhos_comuns(tipo, len(corpo))
            self.end_headers()
            self.wfile.write(corpo)
        except CLIENTE_SAIU:
            self._cliente_saiu()

    def _erro(self, status: int, motivo: str):
        # Chamado de dentro de um `except Exception` cuja excecao e o cliente
        # que saiu (uma escrita fora do `_json`): nao ha a quem responder.
        if self._saiu or isinstance(sys.exc_info()[1], CLIENTE_SAIU):
            return self._cliente_saiu()
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

    # --------------------------------------------- o cliente que foi embora
    # Toda escrita fora do `_json` (estaticos, paginas, imagens) cai aqui
    # quando o celular ja fechou: sem isto, o `handle_error` da biblioteca
    # imprimia o traceback inteiro a cada troca de tela.
    def do_GET(self):
        try:
            self._get()
        except CLIENTE_SAIU:
            self._cliente_saiu()

    def do_POST(self):
        try:
            self._post()
        except CLIENTE_SAIU:
            self._cliente_saiu()

    # ------------------------------------------------------------- GET
    def _get(self):
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
            if rota == "/api/sprites/modulares":
                return self._sprites_modulares_catalogo(consulta)
            if rota == "/api/sprites/modulares/previa":
                return self._sprites_modulares_previa(consulta)
            achado = re.fullmatch(r"/api/sprites/modulares/(.+)/imagem", rota)
            if achado:
                return self._sprites_modulares_imagem(unquote(achado.group(1)), consulta)
            if rota == "/api/sprites/provador/lutadores":
                return self._json(provador_lutadores())
            if rota in ("/api/sprites/provador", "/api/sprites/provador/previa",
                        "/api/sprites/provador/peca", "/api/sprites/provador/godot"):
                return self._provador_get(rota.rsplit("/", 1)[-1], consulta)
            achado = re.fullmatch(r"/api/sprites/modulares/(.+)/gabarito", rota)
            if achado:
                return self._sprites_modulares_gabarito(unquote(achado.group(1)))
            achado = re.fullmatch(r"/api/atelie/arquivo/([a-z0-9_-]{8,40})/(original|limpa|folha|previa|quadro-\d+)", rota)
            if achado:
                return self._atelie_arquivo(*achado.groups())
            achado = re.fullmatch(r"/api/sprites/recortar/arquivo/([A-Za-z0-9_-]{8,40})/(limpa|marcada|recorte-\d+)", rota)
            if achado:
                return self._recortador_arquivo(*achado.groups(), consulta)
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
                # quem le as respostas dele: o SERVIDOR (o pulso do coordenador,
                # `pedidos.ler_grimorio`), desde 04/10; nao a sessao do VS Code
                try:
                    servidor = orquestrador.situacao_do_servidor(
                        pedidos_vivos=[], trabalhadores=([], []), uso={},
                        estado={}, vigia={})
                    dados["servidor"] = {"situacao": servidor["situacao"],
                                         "texto": servidor["texto"]}
                except Exception:                            # noqa: BLE001
                    dados["servidor"] = None
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

    def _post(self):
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
        if rota == "/api/sprites/recortar":
            return self._recortador_importar()
        achado = re.fullmatch(r"/api/sprites/provador/(sortear|fixar|desfixar)", rota)
        if achado:
            return self._provador_post(achado.group(1))
        # Antes do anexar/apagar: o `(.+)` de la engoliria o "/variante/vNN".
        achado = re.fullmatch(r"/api/sprites/modulares/(.+)/variante/(?:(v[0-9a-z_-]{1,20})/apagar|(desfazer))", rota)
        if achado:
            return self._variante_mutar(unquote(achado.group(1)), achado.group(2))
        achado = re.fullmatch(r"/api/sprites/modulares/(.+)/(anexar|apagar|desfazer)", rota)
        if achado:
            return self._sprites_modulares_mutar(unquote(achado.group(1)), achado.group(2))
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
        achado = re.fullmatch(r"/api/coordenador/pedido/(pedido-[0-9a-f]{8})/responder", rota)
        if achado:
            return self._coordenador_responder_pedido(achado.group(1))
        achado = re.fullmatch(r"/api/coordenador/pedido/(pedido-[0-9a-f]{8})/equipe", rota)
        if achado:
            return self._coordenador_passar_para_equipe(achado.group(1))
        achado = re.fullmatch(r"/api/coordenador/proposta/([0-9a-f]{12})", rota)
        if achado:
            return self._coordenador_proposta(achado.group(1))
        if rota == "/api/claude":
            return self._interruptor_claude()
        if rota == "/api/equipe/contratar":
            return self._equipe("contratar")
        if rota == "/api/equipe/config":
            return self._equipe("config")
        if rota == "/api/equipe/permissoes":
            return self._equipe("permissoes")
        achado = re.fullmatch(r"/api/equipe/([a-z0-9][a-z0-9-]{2,39})/permissao", rota)
        if achado:
            return self._equipe("permissao", achado.group(1))
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

    # --------------------------------------------------- sprites modulares
    @staticmethod
    def _manifesto_sprites() -> dict:
        return _indice_sprites()["manifesto"]

    @staticmethod
    def _arquivo_do_slot(slot: dict, variante: str = "v01") -> Path | None:
        # O manifesto e a unica autoridade para destino; ainda assim a API
        # confere que um manifesto corrompido nao a faca sair da biblioteca.
        try:
            destino = str(slot["destino"])
            if slot.get("grupo") == "lutador":
                destino = destino.replace("/v01/", f"/{variante}/")
            return manifesto_sprites.arquivo_do_destino(PARTES_BIBLIOTECA, destino)
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _slot_publico(slot: dict, indice: dict) -> dict:
        """O telefone recebe o lugar da peca, nunca o caminho do PC."""
        situacao, aviso = _situacao_do_slot(slot, indice)
        sid = str(slot.get("id"))
        alvo = slot.get("alvo") or {}
        chave = (str(slot.get("parte", "")), str(alvo.get("nivel", "")), str(alvo.get("chave", "")))
        lutador = slot.get("grupo") == "lutador"
        # A mesma regra do palco (`dono_da_parte`): so conta a pasta vNN com
        # alguma carinha valida da peca (um base.png nos olhos nao e variante).
        validos = set(manifesto_sprites.EXPRESSOES if chave[0] in manifesto_sprites.PARTES_DE_EXPRESSAO
                      else ("base",))
        colecao = indice.get("variantes", {}).get(chave, {})
        variantes = sorted(v for v, estados in colecao.items()
                           if VARIANTE_RE.fullmatch(v) and set(estados) & validos) if lutador else []
        # A variante que nao tem esta carinha (nem a familia, nem a neutra): a
        # galeria do cartao mostra "sem esta carinha" em vez de pedir uma
        # miniatura que nao existe (07/10: bocas mandadas so a furia davam 404
        # e figuras vazias no cartao da neutra). A mesma regra da `/imagem`.
        estado = str(slot.get("estado") or "base")
        sem_carinha = [v for v in variantes
                       if not (estado == "base" and "base" in colecao.get(v, set()))
                       and not manifesto_sprites.estado_na_variante(
                           chave[0], estado if estado != "base" else "neutro", colecao.get(v, set()))]
        return {"id": sid, "rotulo": manifesto_sprites.rotulo_humano(slot),
                "sem_carinha": sem_carinha,
                "parte": slot.get("parte"), "estado": slot.get("estado"),
                "nivel": (slot.get("alvo") or {}).get("nivel"), "papel": slot.get("papel"),
                "situacao": situacao, "aviso": aviso,
                "tem_anterior": sid in indice["com_versao"], "variantes": variantes,
                # a galeria do cartao: "Desfazer" traz a ultima variante apagada
                "variantes_apagadas": indice.get("apagadas", {}).get(chave, 0) if lutador else 0}

    def _sprites_modulares_catalogo(self, consulta: dict):
        indice = _indice_sprites()
        grupo = str((consulta.get("grupo") or ["lutador"])[0]) or "lutador"
        if grupo not in GRUPOS_SPRITES:
            return self._erro(400, "grupo desconhecido")
        alvos = indice["alvos"].get(grupo, [])
        chaves = [a["chave"] for a in alvos]
        alvo = str((consulta.get("alvo") or [""])[0])
        if alvo not in chaves:
            alvo = "_" if "_" in chaves else (chaves[0] if chaves else "_")
        slots = [self._slot_publico(slot, indice) for slot in indice["por_alvo"].get((grupo, alvo), [])]
        resposta = {"grupo": grupo, "alvo": alvo, "alvos": alvos, "slots": slots,
                    "godot_previa": grupo == "lutador" and GODOT_PREVIA.is_file()}
        if grupo == "lutador":
            resposta["progresso"] = _progresso_sprites(indice)
            resposta["expressoes"] = _expressoes_publicas()
            resposta["recortador_olhos"] = _olhos_padrao()
        return self._json(resposta)

    def _sprites_modulares_gabarito(self, slot_id: str):
        slot = _indice_sprites()["por_id"].get(slot_id)
        if not isinstance(slot, dict) or slot.get("grupo") != "lutador":
            return self._erro(404, "não há gabarito para esta peça")
        parte = str(slot.get("parte", ""))
        corpo = manifesto_sprites.gabarito_lutador(parte)
        if self._saiu:
            return
        try:
            self.send_response(200)
            self._cabecalhos_comuns("image/png", len(corpo))
            self.send_header("Content-Disposition", f'attachment; filename="gabarito_{parte}.png"')
            self.end_headers()
            self.wfile.write(corpo)
        except CLIENTE_SAIU:
            self._cliente_saiu()

    def _sprites_modulares_imagem(self, slot_id: str, consulta: dict | None = None):
        """A miniatura do cartao: so a peca deste lugar, em 160 px.

        `?variante=vNN` e a galeria de variantes: a carinha do lugar DENTRO
        da variante (exata -> familia -> neutra), como o jogo a usaria."""
        indice = _indice_sprites()
        slot = indice["por_id"].get(slot_id)
        if not isinstance(slot, dict):
            return self._erro(404, "este lugar não tem desenho")
        pedida = str(((consulta or {}).get("variante") or [""])[0])
        arquivo = None
        if slot.get("grupo") == "lutador":
            alvo = slot.get("alvo") or {}
            chave = (str(slot.get("parte")), str(alvo.get("nivel")), str(alvo.get("chave")))
            colecao = indice["variantes"].get(chave, {})
            estado = str(slot.get("estado") or "base")
            # Sem variante pedida: a v01 (a arte-base) ou, apagada ela, a primeira.
            ordem = [pedida] if pedida else ["v01"] + sorted(v for v in colecao if v != "v01")
            for variante in ordem:
                achado = manifesto_sprites.estado_na_variante(
                    chave[0], estado if estado != "base" else "neutro", colecao.get(variante, set()))
                if estado == "base" and "base" in colecao.get(variante, set()):
                    achado = "base"
                if achado:
                    arquivo = _arquivo_da_variante(*chave, variante, achado)
                    break
            if pedida and arquivo is None:
                return self._erro(404, "esta variante não tem esta carinha")
        if arquivo is None:
            arquivo = self._arquivo_do_slot(slot)
        if arquivo is None or not arquivo.is_file():
            return self._erro(404, "este lugar não tem desenho")
        try:
            with Image.open(arquivo) as imagem:
                peca = imagem.convert("RGBA")
        except (OSError, ValueError):
            return self._erro(404, "não consegui abrir este desenho")
        parte = str(slot.get("parte") or "") if slot.get("grupo") == "lutador" else ""
        return self._bytes(_miniatura_png(peca, parte=parte), "image/png")

    def _sprites_modulares_previa(self, consulta: dict):
        if str((consulta.get("godot") or [""])[0]) == "1":
            return self._sprites_modulares_previa_godot(consulta)
        indice = _indice_sprites()
        alvo = str((consulta.get("alvo") or ["_"])[0])
        expressao = str((consulta.get("expressao") or ["neutro"])[0])
        if expressao not in manifesto_sprites.FAMILIA:
            expressao = "neutro"
        quadro = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        pecas = 0
        for parte in sorted(manifesto_sprites.CAMADA_Z, key=manifesto_sprites.CAMADA_Z.get):
            achado = manifesto_sprites.resolver_parte(
                parte, alvo, expressao, _existe_no_indice(indice), personagem=alvo,
                variantes=_variantes_no_indice(indice))
            if achado is None:
                continue
            slot = indice["por_id"].get(f"lutador/{parte}/{achado['nivel']}/{achado['alvo']}/{achado['estado']}")
            arquivo = self._arquivo_do_slot(slot, achado.get("variante", "v01")) if slot else None
            if arquivo is None:
                continue
            try:
                with Image.open(arquivo) as imagem:
                    peca = imagem.convert("RGBA")
            except (OSError, ValueError):
                continue
            if peca.size != (1024, 1024):
                peca.thumbnail((1024, 1024))
            quadro.alpha_composite(peca, ((1024 - peca.width) // 2, (1024 - peca.height) // 2))
            pecas += 1
        saida = io.BytesIO()
        quadro.resize((512, 512), Image.Resampling.LANCZOS).save(saida, "PNG", optimize=True)
        corpo = saida.getvalue()
        if self._saiu:
            return
        try:
            self.send_response(200)
            self._cabecalhos_comuns("image/png", len(corpo))
            # Zero pecas: o telefone diz que o jogo ainda usa o desenho de hoje.
            self.send_header("X-Previa-Pecas", str(pecas))
            self.end_headers()
            self.wfile.write(corpo)
        except CLIENTE_SAIU:
            self._cliente_saiu()

    def _sprites_modulares_previa_godot(self, consulta: dict):
        if not GODOT_PREVIA.is_file():
            return self._erro(503, "a prévia do Godot não está instalada neste PC")
        alvo = str((consulta.get("alvo") or ["_"])[0])
        if alvo not in {a["chave"] for a in _indice_sprites()["alvos"].get("lutador", [])}:
            return self._erro(400, "estilo desconhecido")
        situacao, dado = pedir_previa_godot(alvo)
        if situacao == "pronta":
            return self._bytes(dado, "image/png")
        if situacao == "erro":
            return self._erro(502, dado)
        texto = ("na fila: o Godot está montando outro estilo…" if situacao == "na_fila"
                 else "montando no Godot…")
        return self._json({"situacao": situacao, "mensagem": texto}, 202)

    def _sprites_modulares_mutar(self, slot_id: str, acao: str):
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as ações estão desligadas neste servidor")
        # O recortador manda `nova=1` na URL (e `nova: true` nas opcoes): os
        # dois viram variante nova da colecao, nunca troca da arte-base.
        nova_na_url = (parse_qs(urlsplit(self.path).query).get("nova") or [""])[0] == "1"
        slot =_indice_sprites()["por_id"].get(slot_id)
        arquivo = self._arquivo_do_slot(slot) if isinstance(slot, dict) else None
        if arquivo is None:
            return self._erro(404, "peça desconhecida")
        avisos: list[str] = []
        if acao == "anexar":
            pedido = self._atelie_corpo()
            if pedido is None:
                return
            bruto, opcoes = pedido
            variante = "v01"
            if slot.get("grupo") == "lutador":
                pedido_variante = str(opcoes.get("variante", ""))
                if opcoes.get("nova") or nova_na_url:
                    usadas = _variantes_no_indice(_indice_sprites())(
                        str(slot.get("parte")), str((slot.get("alvo") or {}).get("nivel")),
                        str((slot.get("alvo") or {}).get("chave")))
                    numero = 1
                    while f"v{numero:02d}" in usadas:
                        numero += 1
                    variante = f"v{numero:02d}"
                elif re.fullmatch(r"v[0-9a-z_-]{1,20}", pedido_variante):
                    variante = pedido_variante
                arquivo = self._arquivo_do_slot(slot, variante)
                if arquivo is None:
                    return self._erro(400, "variante invalida")
            if len(bruto) > SPRITE_MAX:
                return self._erro(413, "a imagem passa de 20 MB")
            if arquivo.exists() and not bool(opcoes.get("substituir")):
                return self._erro(409, "já há um desenho aqui; confirme a troca")
            try:
                with Image.open(io.BytesIO(bruto)) as aberta:
                    if aberta.format != "PNG":
                        return self._erro(400, "mande uma imagem PNG")
                    imagem = aberta.convert("RGBA")
            except (OSError, ValueError):
                return self._erro(400, "não consegui abrir esta imagem")
            if imagem.getchannel("A").getextrema()[0] == 255:
                return self._erro(400, "a imagem precisa ter fundo transparente")
            esperado = tuple(slot.get("tamanho_px") or (1024, 1024))
            if abs(imagem.width / imagem.height - esperado[0] / esperado[1]) > .02:
                return self._erro(400, "o formato não combina com este lugar; use o gabarito")
            if imagem.size != esperado:
                imagem = imagem.resize(esperado, Image.Resampling.LANCZOS)
                avisos.append("ajustei o tamanho para caber no gabarito")
            manifesto_sprites.guardar_versao(arquivo)
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            temporario = arquivo.with_suffix(".novo.png")
            imagem.save(temporario, "PNG", optimize=True)
            os.replace(temporario, arquivo)
        elif acao == "desfazer":
            anteriores = manifesto_sprites.versoes(arquivo)
            if not anteriores:
                return self._erro(404, "não há versão anterior")
            if arquivo.is_file():
                # O desenho desfeito nao some: fica guardado fora da fila.
                desfeitos = manifesto_sprites.pasta_de_versoes(arquivo) / "desfeitos"
                desfeitos.mkdir(parents=True, exist_ok=True)
                os.replace(arquivo, manifesto_sprites.nome_de_versao(desfeitos))
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            os.replace(anteriores[-1], arquivo)
        else:
            if not arquivo.is_file():
                return self._erro(404, "este lugar já está vazio")
            manifesto_sprites.guardar_versao(arquivo, mover=True)
        indice = _indice_sprites(mudou=slot_id)
        return self._json({"feito": True, "avisos": avisos,
                           "slot": self._slot_publico(slot, indice),
                           "progresso": _progresso_sprites(indice)})

    def _variante_mutar(self, slot_id: str, variante: str | None):
        """Apagar a variante INTEIRA (todas as carinhas) ou trazer de volta a
        ultima apagada. Quem a tinha fixa volta ao sorteio, e a tela diz quem."""
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as ações estão desligadas neste servidor")
        slot = _indice_sprites()["por_id"].get(slot_id)
        if _pasta_do_alvo(slot) is None:
            return self._erro(404, "peça desconhecida")
        try:
            if variante:
                ordem = sorted(_indice_sprites()["variantes"].get(
                    (str(slot.get("parte")), str((slot.get("alvo") or {}).get("nivel")),
                     str((slot.get("alvo") or {}).get("chave"))), {}))
                numero = ordem.index(variante) + 1 if variante in ordem else 0
                feito = apagar_variante(slot, variante)
                nome = f"A variante {numero}" if numero else "A variante"
                mensagem = (f"{nome} de {manifesto_sprites.nome_da_parte(str(slot.get('parte'))).lower()} "
                            f"foi apagada (todas as carinhas dela).{_frase_do_sorteio(feito['nomes'])} "
                            "Desfazer traz de volta.")
            else:
                feito = desfazer_variante(slot)
                mensagem = "Pronto: a variante apagada voltou." + (
                    f" A escolha fixa voltou para {', '.join(feito['nomes'])}." if feito["nomes"] else "")
        except LookupError as exc:
            return self._erro(404, str(exc))
        except OSError:
            return self._erro(409, "o desenho está aberto em outro programa; tente de novo")
        indice = _indice_sprites(mudou=slot_id)
        return self._json({"feito": True, "mensagem": mensagem, "voltaram_ao_sorteio": feito["nomes"] if variante else [],
                           "slot": self._slot_publico(slot, indice),
                           "progresso": _progresso_sprites(indice)})

    # ------------------------------------------------------------ provador
    def _provador_get(self, tipo: str, consulta: dict):
        indice = _indice_sprites()
        lutador = _lutador_do_provador(str((consulta.get("lutador") or [""])[0]), indice)
        if lutador is None:
            return self._erro(404, "lutador não encontrado")
        expressao = str((consulta.get("expressao") or ["neutro"])[0])
        if expressao not in manifesto_sprites.FAMILIA:
            expressao = "neutro"
        escolha = _escolha_normalizada((consulta.get("escolha") or [""])[0])
        if tipo == "provador":
            return self._json(provador_resposta(lutador, escolha, expressao))
        if tipo == "previa":
            corpo, pecas = _previa_do_provador(lutador, escolha, expressao)
            if self._saiu:
                return
            try:
                self.send_response(200)
                self._cabecalhos_comuns("image/png", len(corpo))
                self.send_header("X-Previa-Pecas", str(pecas))
                self.end_headers()
                self.wfile.write(corpo)
            except CLIENTE_SAIU:
                self._cliente_saiu()
            return
        fixadas = {} if lutador["exemplo"] else _ler_guarda_roupa().get(lutador["id"], {})
        pecas = _pecas_do_lutador(lutador, indice, escolha, fixadas)
        if tipo == "peca":
            parte = str((consulta.get("parte") or [""])[0])
            variante = str((consulta.get("variante") or [""])[0])
            achada = next((p for p in pecas if p["parte"] == parte), None)
            if achada is None or variante not in achada["colecao"]:
                return self._erro(404, "esta peça não tem esta variante")
            estado = manifesto_sprites.estado_na_variante(parte, expressao, achada["colecao"][variante])
            arquivo = _arquivo_da_variante(parte, achada["nivel"], achada["alvo"], variante, estado or "")
            peca = _abrir_peca(arquivo, parte, achada["nivel"], lutador["cor"]) if arquivo else None
            if peca is None:
                return self._erro(404, "esta variante não tem esta carinha")
            return self._bytes(_miniatura_png(peca, parte=parte), "image/png")
        # "Ver no Godot" para ESTE lutador, com a combinacao da tela.
        if not GODOT_PREVIA.is_file():
            return self._erro(503, "a prévia do Godot não está instalada neste PC")
        combinacao = [(p["parte"], p["nivel"], p["alvo"], p["atual"]) for p in pecas]
        chave = f"prov:{lutador['id']}:" + ",".join("%s=%s/%s/%s" % (p, n, a, v) for p, n, a, v in combinacao)
        situacao, dado = pedir_previa_godot(chave, {"chave": chave, "lutador": lutador, "pecas": combinacao})
        if situacao == "pronta":
            return self._bytes(dado, "image/png")
        if situacao == "erro":
            return self._erro(502, dado)
        texto = ("na fila: o Godot está montando outra folha…" if situacao == "na_fila"
                 else "montando no Godot…")
        return self._json({"situacao": situacao, "mensagem": texto}, 202)

    def _provador_post(self, acao: str):
        if self._aparelho() is None:
            return
        corpo = self._corpo()
        if corpo is None:
            return
        indice = _indice_sprites()
        lutador = _lutador_do_provador(str(corpo.get("lutador") or ""), indice)
        if lutador is None:
            return self._erro(404, "lutador não encontrado")
        expressao = str(corpo.get("expressao") or "neutro")
        if expressao not in manifesto_sprites.FAMILIA:
            expressao = "neutro"
        escolha = _escolha_normalizada(corpo.get("escolha") or {})
        parte = str(corpo.get("parte") or "")
        if parte and parte not in manifesto_sprites.CAMADA_Z:
            return self._erro(400, "peça desconhecida")
        if acao == "sortear":
            # So na tela: experimentar nao grava nada (vale quando ele Fixa).
            fixadas = {} if lutador["exemplo"] else _ler_guarda_roupa().get(lutador["id"], {})
            pecas = _pecas_do_lutador(lutador, indice, escolha, fixadas)
            nova = {p["parte"]: p["atual"] for p in pecas if p["situacao"] == "experimento"}
            sorteio = secrets.SystemRandom()
            mudou = []
            for p in pecas:
                if (parte and p["parte"] != parte) or len(p["ordem"]) < 2:
                    continue
                nova[p["parte"]] = sorteio.choice([v for v in p["ordem"] if v != p["atual"]])
                mudou.append(p["parte"])
            aviso = ("Sorteado só na tela: toque em Fixar para o jogo usar." if mudou
                     else "Esta peça só tem um desenho: não há o que sortear.")
            return self._json(provador_resposta(lutador, nova, expressao, aviso))
        if not self.estado.com_acoes:
            return self._erro(403, "as ações estão desligadas neste servidor")
        if lutador["exemplo"]:
            return self._erro(400, "o lutador de exemplo não guarda escolha; escolha um lutador de verdade para fixar")
        try:
            if acao == "fixar":
                fixadas = _ler_guarda_roupa(estrito=True).get(lutador["id"], {})
                pecas = _pecas_do_lutador(lutador, indice, escolha, fixadas)
                alvos = [p for p in pecas if (p["parte"] == parte if parte else len(p["ordem"]) > 1)]
                if not alvos:
                    return self._erro(400, "não há peça com mais de um desenho para fixar"
                                      if not parte else "esta peça não tem desenho")

                def fixar(dados):
                    for p in alvos:
                        dados.setdefault(lutador["id"], {})[p["parte"]] = p["atual"]
                _mudar_guarda_roupa(fixar)
                for p in alvos:
                    escolha.pop(p["parte"], None)
                if parte:
                    p = alvos[0]
                    aviso = (f"Fixado em {lutador['nome']}: {manifesto_sprites.nome_da_parte(parte).lower()} "
                             f"{p['ordem'].index(p['atual']) + 1} de {len(p['ordem'])}. O jogo usa sempre este desenho.")
                else:
                    aviso = (f"Combinação fixada ({len(alvos)} peças). O jogo usa sempre esta combinação "
                             f"em {lutador['nome']}.")
            else:
                def soltar(dados):
                    fixas = dados.get(lutador["id"], {})
                    for nome in ([parte] if parte else list(fixas)):
                        fixas.pop(nome, None)
                _mudar_guarda_roupa(soltar)
                if parte:
                    escolha.pop(parte, None)
                    aviso = (f"{manifesto_sprites.nome_da_parte(parte)} de volta ao sorteio: o jogo escolhe "
                             f"por {lutador['nome']}.")
                else:
                    escolha = {}
                    aviso = f"Tudo voltou ao sorteio: o jogo escolhe cada peça de {lutador['nome']}."
        except GuardaRoupaIlegivel as exc:
            return self._erro(409, str(exc))
        except OSError:
            return self._erro(409, "não consegui gravar o guarda-roupa no PC; tente de novo")
        return self._json(provador_resposta(lutador, escolha, expressao, aviso))

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

    # ------------------------------------------------ folha verde ou magenta
    def _recortador_arquivo(self, sessao: str, parte: str, consulta: dict | None = None):
        """Previa temporaria do recortador; nunca e arquivo da biblioteca.

        `recorte-N` sai CRU; com `?destino=<lugar>` (e `olhos=<modo>` quando o
        lugar e de olhos) sai encaixado no gabarito DAQUELE lugar. O encaixe e
        feito aqui, na hora de mandar: em 06/10 ele era feito ao subir a folha,
        com a peca que estava no seletor, e olhos cairam na zona da sombra."""
        with self.estado.trava:
            dados = self.estado.atelie.get(sessao)
        if not dados or dados["dono"] != self._dono or "recortador" not in dados:
            return self._erro(404, "previa nao existe")
        corpo = dados["recortador"].get(parte)
        if corpo is None:
            return self._erro(404, "recorte nao existe")
        destino = str(((consulta or {}).get("destino") or [""])[0])
        if not destino or not parte.startswith("recorte-"):
            return self._bytes(corpo, "image/png")
        slot = _indice_sprites()["por_id"].get(destino)
        if not isinstance(slot, dict):
            return self._erro(404, "peça desconhecida")
        modo = str(((consulta or {}).get("olhos") or [_olhos_padrao()])[0])
        if modo not in sprites_recortador.MODOS_OLHOS:
            return self._erro(400, "modo de olhos desconhecido")
        recorte = dados["recortes"][int(parte.split("-", 1)[1])]
        pronto = sprites_recortador.encaixar(
            recorte, str(slot.get("parte") or ""), grupo=str(slot.get("grupo") or ""),
            tamanho=tuple(slot.get("tamanho_px") or (1024, 1024)), olhos=modo)
        return self._bytes(self._atelie_png(pronto), "image/png")

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
        # O recortador de folhas usa os campos diretos do multipart; a tela
        # antiga continua mandando o objeto `opcoes`.
        if isinstance(opcoes, dict):
            for chave in ("variante", "nova"):
                if chave in campos and chave not in opcoes:
                    valor = campos[chave].decode("utf-8", "ignore")
                    opcoes[chave] = valor in ("1", "true", "True") if chave == "nova" else valor
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

    def _recortador_importar(self):
        """Sobe uma folha e guarda so as previas na memoria deste aparelho."""
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as acoes estao desligadas neste servidor")
        pedido = self._atelie_corpo()
        if pedido is None:
            return
        imagem, opcoes = pedido
        nivel = str(opcoes.get("juncao") or "medio")
        if nivel not in sprites_recortador.NIVEIS:
            return self._erro(400, "juncao precisa ser pouco, medio, muito ou pares")
        try:
            origem = sprites_importar.abrir_bytes(imagem)
            resultado = sprites_recortador.recortar(
                origem, juntar=sprites_recortador.JUNCAO.get(nivel, sprites_recortador.JUNCAO["medio"]),
                area_min=max(1, int(opcoes.get("area_min") or 50)),
                margem=max(0, int(opcoes.get("margem") or 8)), pares=nivel == "pares")
        except (TypeError, ValueError) as exc:
            return self._erro(400, str(exc))
        # Os recortes ficam CRUS: o encaixe no gabarito e do destino, na hora
        # de mandar (`_recortador_arquivo` com `?destino=`). A `parte` que a
        # casca antiga ainda manda aqui e ignorada de proposito.
        imagens = [r.imagem for r in resultado.recortes]
        marcada = Image.fromarray(resultado.limpo, "RGBA")
        caneta = ImageDraw.Draw(marcada)
        # O numero do recorte legivel no celular: a folha de 900-2048 px cabe
        # em ~330 px de tela, e a fonte padrao de 10 px virava um risco
        # (passada de uso, 07/10). ~1/28 da largura, como a lista "Recorte N".
        fonte = ImageFont.load_default(size=max(14, marcada.width // 28))
        traco = max(3, marcada.width // 300)
        for i, recorte in enumerate(resultado.recortes, 1):
            caneta.rectangle(recorte.caixa, outline=(20, 20, 26, 255), width=traco)
            caneta.text((recorte.caixa[0] + traco + 2, recorte.caixa[1] + traco), str(i), font=fonte,
                        fill=(255, 255, 255, 255), stroke_width=max(2, traco), stroke_fill=(20, 20, 26, 255))
        sessao = secrets.token_urlsafe(12).replace("-", "_")
        arquivos = {"limpa": self._atelie_png(resultado.limpo),
                    "marcada": self._atelie_png(np.asarray(marcada, np.uint8))}
        arquivos.update({f"recorte-{i}": self._atelie_png(q) for i, q in enumerate(imagens)})
        with self.estado.trava:
            # Cada folha guarda os recortes crus na memoria: so as ultimas
            # RECORTADOR_SESSOES deste aparelho ficam (antes nada saia).
            minhas = [s for s, d in self.estado.atelie.items()
                      if d.get("dono") == self._dono and "recortador" in d]
            for velha in minhas[:max(0, len(minhas) - RECORTADOR_SESSOES + 1)]:
                self.estado.atelie.pop(velha, None)
            self.estado.atelie[sessao] = {"dono": self._dono, "recortador": arquivos,
                                          "recortes": resultado.recortes}
        raiz = f"/api/sprites/recortar/arquivo/{sessao}"
        return self._json({"sessao": sessao, "fundo": resultado.fundo, "juncao": nivel,
                           "avisos": resultado.avisos, "limpa": f"{raiz}/limpa",
                           "folha": f"{raiz}/marcada", "olhos_padrao": _olhos_padrao(),
                           "recortes": [{"id": i, "caixa": list(r.caixa), "area": r.area,
                                         "tamanho": [int(q.shape[1]), int(q.shape[0])],
                                         "tipo": r.tipo, "orientacao": r.orientacao,
                                         "url": f"{raiz}/recorte-{i}"}
                                        for i, (r, q) in enumerate(zip(resultado.recortes, imagens))]})

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
        # Uma decisao de produto pedida pelo trabalhador tambem e permissao:
        # responder o no fecha o cartao e retoma (ou encerra) a tarefa.
        for trabalhador in delegar.listar():
            pedido = trabalhador.get("pedido_permissao") or {}
            if pedido.get("decisao_id") != item_id:
                continue
            try:
                retomada = delegar.decidir_permissao(trabalhador["id"], evento["opcao"] == "permitir")
                if retomada.get("situacao") == "criado":
                    delegar.no_fundo(["retomar", "--id", trabalhador["id"]], trabalhador["id"])
            except delegar.Recusa:
                pass
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
            if acao_equipe == "permissoes":
                return self._json({"feito": True, "permissoes": delegar.gravar_permissoes(corpo)})
            if acao_equipe == "contratar":
                cargo = str(corpo.get("cargo") or "").lower()
                ia = str(corpo.get("ia") or "codex").lower()
                tarefa = str(corpo.get("tarefa") or "").strip()
                repo_tarefa = str(corpo.get("repo") or "").strip() or None
                if not tarefa or len(tarefa) > 12_000:
                    return self._erro(400, "tarefa invalida")
                if cargo not in delegar.cargos() or ia not in delegar.IAS:
                    return self._erro(400, "cargo ou ia desconhecido")
                from coordenador import pedidos
                item = pedidos.contratar(
                    tarefa, "equipe", cargo=cargo,
                    permitidos=["remoto/**", "coordenador/**", "docs/**"], ia=ia,
                    titulo=tarefa.splitlines()[0], alvo=repo_tarefa)
                return self._json({"feito": True, "pedido": item["id"],
                                   "recibo": item["recibo"], "duplicado": item.get("duplicado", False)})
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
            if acao_equipe == "permissao":
                decisao = str(corpo.get("decisao") or "").lower()
                if decisao not in ("permitir", "negar"):
                    return self._erro(400, "decisao de permissao invalida")
                atual = delegar.ler_estado(ident)
                if (atual.get("pedido_permissao") or {}).get("decisao_id"):
                    return self._erro(409, "responda a decisao no Grimorio para retomar a tarefa")
                estado = delegar.decidir_permissao(ident, decisao == "permitir",
                                                    sempre=bool(corpo.get("sempre")))
                if decisao == "permitir" and estado.get("situacao") == "criado":
                    delegar.no_fundo(["retomar", "--id", ident], ident)
                return self._json({"feito": True, "trabalhador": _limpo(estado)})
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
                # quem aplica: o pulso do servidor; a tela diz na hora se ele esta no ar
                try:
                    servidor = orquestrador.situacao_do_servidor(
                        pedidos_vivos=[], trabalhadores=([], []), uso={},
                        estado={}, vigia={})
                    servidor = {"situacao": servidor["situacao"], "texto": servidor["texto"]}
                except Exception:                            # noqa: BLE001
                    servidor = None
                return self._json({"feito": True, "comando": linha, "servidor": servidor})
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
            # o "Novo assunto" (casca velha): desde 05/10/2026 todo texto solto
            # ja abre pedido novo; nada a marcar
            return self._json({"feito": True, "novo_assunto": False,
                               "aviso": "todo texto já abre um pedido novo"})
        if not isinstance(texto, str) or not texto.strip():
            return self._erro(400, "a mensagem está vazia")
        if len(texto) > 4000:
            return self._erro(400, "a mensagem passa de 4000 caracteres")
        # 03/10: pergunta curta de estado ("o app está no ar?") vai ao cerebro,
        # que responde em segundos; o resto é PEDIDO e vai a um trabalhador
        # `orquestrador` do servidor (coordenador/pedidos.py)
        from coordenador import cerebro as coord_cerebro, pedidos
        try:
            if pedidos.e_de_estado(texto) and not pedidos.e_conversa_solta(texto):
                entrada = coord_cerebro.registrar_entrada(texto, "app")
                return self._json({"feito": True, "id": entrada["id"], "em": entrada["em"],
                                   "situacao": "recebido", "para": "cerebro"})
            item = pedidos.registrar(texto, "app")
        except (OSError, ValueError) as exc:
            return self._erro(503, f"não consegui guardar a mensagem: {exc}")
        # 05/10 (conferente 3): texto solto nunca continua um pedido; volta o
        # id e o titulo, para o aviso dizer QUAL pedido nasceu
        return self._json({"feito": True, "id": item["id"], "em": item["atualizado_em"],
                           "situacao": item["situacao"],
                           "para": "conversa" if item.get("conversa") else "orquestrador",
                           # agradecimento solto da lista fixa: ninguem contratado
                           "curto": bool(item.get("curto")),
                           "titulo": _titulo_do_pedido(item),
                           "continuacao": bool(item.get("continuacao"))})

    def _coordenador_responder_pedido(self, ident: str):
        """O botao Responder do cartao de um pedido: a mensagem vai a ESTE
        pedido (o id vem na rota), mesmo que ele esteja esperando voce,
        entregue ou falhou. 05/10/2026 (v2): texto livre so continua pedido
        ativo; o que ja parou so recebe a resposta explicita. Conferente 3:
        texto livre nunca continua pedido nenhum; esta rota e o caminho. 409
        quando o pedido espera a permissao do estado do servidor (Permitir/
        Negar, nao texto). Exige pareamento e `--acoes` (relanca um trabalhador)."""
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as ações estão desligadas neste servidor")
        corpo = self._corpo(maximo=20_000)
        if corpo is None:
            return
        texto = corpo.get("texto")
        if not isinstance(texto, str) or not texto.strip():
            return self._erro(400, "a resposta está vazia")
        if len(texto) > 4000:
            return self._erro(400, "a resposta passa de 4000 caracteres")
        from coordenador import pedidos
        try:
            item = pedidos.registrar(texto, "app", responde_a=ident)
        except KeyError:
            return self._erro(404, "pedido desconhecido")
        except ValueError as exc:
            return self._erro(409, str(exc))
        except OSError as exc:
            return self._erro(503, f"não consegui guardar a resposta: {exc}")
        return self._json({"feito": True, "id": item["id"], "em": item["atualizado_em"],
                           "situacao": item["situacao"], "titulo": _titulo_do_pedido(item),
                           "continuacao": True})

    def _coordenador_passar_para_equipe(self, ident: str):
        """«Passar para a equipe» (07/10/2026, Grimório
        app-e-bot/conversa-pergunta-livre = "O modelo decide"): a pergunta
        livre que ficou como conversa -- o modelo a leu como conversa ou não
        conseguiu ler -- vira pedido de trabalho pelo toque DELE. É o mesmo
        pedido (o mesmo id), não um segundo: nenhum trabalhador a mais.
        Pareamento e `--acoes` (contrata um trabalhador, como o falar); 404
        desconhecida, 409 já é trabalho ou é saudação/agradecimento."""
        if self._aparelho() is None:
            return
        if not self.estado.com_acoes:
            return self._erro(403, "as ações estão desligadas neste servidor")
        if self._corpo() is None:                 # "{}": JSON, como as outras rotas
            return
        from coordenador import pedidos
        try:
            item = pedidos.passar_para_equipe(ident, "app")
        except KeyError:
            return self._erro(404, "mensagem desconhecida")
        except ValueError as exc:
            return self._erro(409, str(exc))
        except OSError as exc:
            return self._erro(503, f"não consegui passar para a equipe: {exc}")
        return self._json({"feito": True, "id": item["id"], "em": item["atualizado_em"],
                           "situacao": item["situacao"], "para": "orquestrador",
                           "titulo": _titulo_do_pedido(item), "continuacao": False})

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


def _titulo_do_pedido(item) -> str:
    """A primeira mensagem do Adrian no pedido (a 1a linha), para o aviso do
    app dizer DE QUAL pedido fala."""
    primeiro = (item.get("do_adrian") or [item.get("texto") or ""])[0]
    return (str(primeiro).strip().splitlines() or [""])[0][:90]


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

    def handle_error(self, request, client_address):
        """O cliente que saiu antes de o pedido ser lido (o reset chega na
        leitura da linha do pedido, fora do `do_GET`) vira uma linha, nao um
        traceback. Qualquer outra excecao continua com o traceback inteiro."""
        if isinstance(sys.exc_info()[1], CLIENTE_SAIU):
            ip = client_address[0] if client_address else "?"
            sys.stderr.write(f"{datetime.now():%d/%m %H:%M:%S} {ip} - saiu\n")
            return
        super().handle_error(request, client_address)


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
    # comando pendente ha mais de 2 min (o servidor sem pulso ou preso): um
    # aviso no Telegram por ocorrencia (e um quando ele aplica)
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
