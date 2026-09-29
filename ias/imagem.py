# -*- coding: utf-8 -*-
"""PEDIR IMAGEM pelo correio (Vila das IAs, 29/09/2026, demanda urgente do
Adrian: "os modelos que geram imagem e etc, eu preciso ter suporte para isso
tambem").

Tres pecas, e nenhuma reescreve cliente que ja funciona em producao:

  QUEM GERA       `gerador(ia)` / `geradores()`: o que cada IA faz HOJE, lido
                  da FICHA (`ias/fichas/<ia>.json`, fase 1): gera ou nao, por
                  que nao, as proporcoes que oferece, o modelo, o teto do
                  prompt e que prova de origem vale. O app desenha a acao
                  "Criar" disto: habilitada, ou desabilitada com o motivo.
  COMO GERA       as SESSOES. PicassoIA: o `PicassoClient` do identity, com
                  a espera que reenvia (`contos.imagens.worker`) e a PROVA DE
                  ORIGEM forte (`proveniencia.comprovar`: o card do historico
                  com o NOSSO prompt), Aprimorador desligado. Grok, Gemini e
                  ChatGPT: o `ClienteLLM` na CASA da IA (`carteiro.SessaoReal`
                  ganha `gerar_imagem`): a prova e o turno nosso na tela, e a
                  imagem e a que nasce DEPOIS dele. O dublê gera um PNG sem
                  abrir navegador (testes e prova de tela).
  ONDE FICA       `guardar`: `<raiz>/<gerador>/imagens/<id>.<ext>`, com os
                  BYTES ORIGINAIS (sem recomprimir) e `<id>.prova.json` ao
                  lado. Sem prova, nada vai ao disco (conta compartilhada:
                  memoria `contas-compartilhadas-prova-de-origem`).

O rodizio ("qualquer um livre") e do carteiro; daqui ele usa `gerador()` e
`fora_de_cota()`.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import struct
import time
import zlib
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from . import correio, ficha as fichas

# Por onde cada IA gera. `None` = nao ha cliente que gere imagem com prova
# de origem hoje (a ficha diz por que).
VIA = {"picasso": "picasso", "grok": "chat", "gemini": "chat", "chatgpt": "chat",
       "dreamface": None, "digen": None}
# O chat nao tem seletor de proporcao: ela vai escrita no pedido.
PROPORCOES_DO_CHAT = ("1:1", "3:4", "4:3", "9:16", "16:9")
PROPORCOES_DO_PICASSO = ("1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3")
PROVA_DA_VIA = {
    "picasso": "o card do histórico da conta com o SEU prompt (prova forte)",
    "chat": "o turno do pedido na casa da IA; vale a imagem que nasce depois dele",
}
# Categorias de falha que tiram o gerador do rodizio por `cota_pausa_h`.
CATEGORIAS_DE_COTA = ("limite", "upgrade", "parede")


class ImagemFalhou(RuntimeError):
    """Falha com categoria legivel (`categoria`) e motivo para o Adrian."""

    categoria = "erro"

    def __init__(self, motivo: str, categoria: str | None = None):
        super().__init__(motivo)
        if categoria:
            self.categoria = categoria


class SemProva(ImagemFalhou):
    categoria = "sem_prova"


class SemImagem(ImagemFalhou):
    categoria = "sem_imagem"


class Pausado(ImagemFalhou):
    categoria = "pausado"


class ImagemInvalida(ImagemFalhou):
    categoria = "arquivo"


# ================================================================ quem gera
def _medido(f: dict) -> str:
    return str(f.get("medido_em") or "")[:10]


def gerador(ia: str) -> dict:
    """O que a IA faz HOJE com um pedido de imagem, pela ficha. Nunca levanta.

    {ia, rotulo, emoji, via, disponivel, motivo, nota, proporcoes,
     proporcao_padrao, modelos, prompt_max, prova, proximo_passo}
    """
    ia = str(ia or "").lower()
    try:
        f = fichas.carregar(ia)
    except Exception:                                          # noqa: BLE001
        f = {}
    img = f.get("imagem") if isinstance(f.get("imagem"), dict) else {}
    cota = f.get("cota") if isinstance(f.get("cota"), dict) else {}
    origem = img.get("prova_origem") if isinstance(img.get("prova_origem"), dict) else {}
    video = f.get("video") if isinstance(f.get("video"), dict) else {}
    via = VIA.get(ia)
    info = {"ia": ia, "rotulo": correio.ROTULOS.get(ia, ia),
            "emoji": correio.EMOJIS.get(ia, "•"), "via": via, "disponivel": False,
            "motivo": "", "nota": "", "proporcoes": [], "proporcao_padrao": "1:1",
            "modelos": [], "prompt_max": correio.PROMPT_IMAGEM_MAX,
            "prova": PROVA_DA_VIA.get(via or "", ""), "proximo_passo": False}
    if ia not in correio.GERADORES:
        info["motivo"] = "não gera imagem"
        return info
    modelos = f.get("modelos") if isinstance(f.get("modelos"), dict) else {}
    ativo = str(modelos.get("ativo") or "").strip()
    info["modelos"] = [ativo] if ativo else []
    if ia == "digen":
        info["motivo"] = ("o Digen gera VÍDEO a partir de uma imagem (Real Motion 3.5), "
                          "não imagem: fica como próximo passo")
        info["proximo_passo"] = True
        info["nota"] = str(video.get("fonte") or "")[:200]
        return info
    if via is None:
        partes = []
        if cota.get("creditos") == 0:
            partes.append(f"créditos 0 (ficha de {_medido(f) or '?'}; "
                          f"{'; '.join(cota.get('o_que_o_site_diz') or [])[:120]})")
        partes.append(str(origem.get("nota") or "sem cliente que gere com prova de origem"))
        info["motivo"] = " · ".join(p for p in partes if p)[:400]
        return info
    if img.get("gera") is False:
        info["motivo"] = str(origem.get("motivo") or "a ficha diz que não gera imagem")
        return info
    info["disponivel"] = True
    if via == "picasso":
        info["proporcoes"] = list(img.get("proporcoes") or PROPORCOES_DO_PICASSO)
        info["proporcao_padrao"] = "1:1"
        info["nota"] = ("Aprimorador desligado (ele trocava a ação por retrato); "
                        "o site aceita 2 gerações em paralelo")
    else:
        info["proporcoes"] = list(img.get("proporcoes") or PROPORCOES_DO_CHAT)
        info["nota"] = "a proporção vai escrita no pedido (o chat não tem seletor)"
        if img.get("gera") is None:
            info["nota"] += "; ainda não medido: a primeira imagem mede"
    return info


def geradores() -> list:
    """Todos os geradores, na ordem do correio."""
    return [gerador(ia) for ia in correio.GERADORES]


def conferir_pedido(caixa: str, proporcao: str) -> dict:
    """O pedido pode entrar? Devolve o `gerador` (ou o rodizio). Levanta
    `correio.CorreioInvalido` com o motivo legivel."""
    caixa = str(caixa or "").lower()
    if caixa == correio.LIVRE:
        todas = set()
        for g in rodizio_ordem():
            info = gerador(g)
            if info["disponivel"]:
                todas.update(info["proporcoes"])
        if not todas:
            raise correio.CorreioInvalido("nenhum gerador do rodízio gera imagem hoje")
        if proporcao not in todas:
            raise correio.CorreioInvalido(
                f"proporção {proporcao!r}: o rodízio aceita {', '.join(sorted(todas))}")
        return {"ia": correio.LIVRE, "disponivel": True}
    info = gerador(caixa)
    if not info["disponivel"]:
        raise correio.CorreioInvalido(
            f"{info['rotulo']} não gera imagem hoje: {info['motivo']}")
    if proporcao not in info["proporcoes"]:
        raise correio.CorreioInvalido(
            f"proporção {proporcao!r}: o {info['rotulo']} oferece "
            f"{', '.join(info['proporcoes'])}")
    return info


# ================================================================== rodizio
def _config() -> dict:
    try:
        from .carteiro import config
        return config()
    except Exception:                                          # noqa: BLE001
        return {}


def rodizio_ordem() -> list:
    ordem = _config().get("rodizio_imagem") or ["picasso", "gemini", "grok", "chatgpt"]
    return [str(g).lower() for g in ordem if str(g).lower() in correio.GERADORES]


def fora_de_cota(ia: str, horas: float | None = None, agora: datetime | None = None) -> str:
    """"" se o gerador esta em cota; senao, o motivo (a ultima falha de cota,
    limite ou parede dele nas ultimas `horas`)."""
    horas = float(_config().get("cota_pausa_h", 6) if horas is None else horas)
    limite = (agora or datetime.now()) - timedelta(hours=horas)
    ultima = None
    for caixa in correio.CAIXAS:
        for m in correio.ler(caixa):
            if correio.tipo(m) != "imagem" or m.get("gerador") != ia:
                continue
            if m.get("situacao") != "falhou" or m.get("categoria") not in CATEGORIAS_DE_COTA:
                continue
            try:
                quando = datetime.fromisoformat(str(m.get("falhou_em") or m.get("em")))
            except ValueError:
                continue
            if quando >= limite and (ultima is None or quando > ultima[0]):
                ultima = (quando, m)
    if ultima is None:
        return ""
    quando, m = ultima
    return (f"{m.get('categoria')} às {quando:%H:%M} ({str(m.get('erro') or '')[:80]}); "
            f"fica fora do rodízio por {horas:.0f} h")


# ==================================================================== disco
_ASSINATURAS = ((b"\x89PNG\r\n\x1a\n", ".png"), (b"\xff\xd8\xff", ".jpg"))
TIPOS_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}
BYTES_MIN = 512
BYTES_MAX = 40 * 1024 * 1024


def extensao(corpo: bytes) -> str | None:
    for assinatura, ext in _ASSINATURAS:
        if corpo.startswith(assinatura):
            return ext
    if corpo[:4] == b"RIFF" and corpo[8:12] == b"WEBP":
        return ".webp"
    return None


def dimensoes(caminho: Path) -> tuple:
    """(largura, altura) lidas do cabecalho, sem decodificar nem regravar."""
    try:
        from PIL import Image
        with Image.open(caminho) as img:
            return tuple(int(x) for x in img.size)
    except Exception:                                          # noqa: BLE001
        return (None, None)


def guardar(gerador_ia: str, mensagem_id: str, corpo: bytes, prova: dict) -> dict:
    """Grava os BYTES ORIGINAIS e a prova ao lado. Devolve o resumo da imagem
    que vai para o correio: {arquivo, largura, altura, bytes, formato, sha256,
    prova}. Levanta `ImagemInvalida` se nao for imagem."""
    corpo = bytes(corpo or b"")
    if not re.fullmatch(r"[0-9a-f]{8}", str(mensagem_id)):
        raise ImagemInvalida(f"id de mensagem inválido: {mensagem_id!r}")
    if len(corpo) < BYTES_MIN:
        raise ImagemInvalida(f"o download veio com {len(corpo)} bytes: não é imagem")
    if len(corpo) > BYTES_MAX:
        raise ImagemInvalida(f"imagem de {len(corpo) // (1024 * 1024)} MB: grande demais")
    ext = extensao(corpo)
    if ext is None:
        raise ImagemInvalida("o arquivo baixado não é PNG, JPG nem WEBP")
    if not prova or not prova.get("comprovada"):
        raise SemProva("sem prova de origem: nada foi gravado")
    pasta = correio.pasta_imagens(gerador_ia)
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / f"{mensagem_id}{ext}"
    tmp = alvo.with_name(f".{alvo.name}.{os.getpid()}.tmp")
    tmp.write_bytes(corpo)
    os.replace(tmp, alvo)
    largura, altura = dimensoes(alvo)
    sha = hashlib.sha256(corpo).hexdigest()
    registro = {"id": mensagem_id, "gerador": gerador_ia, "arquivo": alvo.name,
                "bytes": len(corpo), "sha256": sha, "formato": ext.lstrip("."),
                "largura": largura, "altura": altura, "gravado_em": correio.agora(),
                "prova": prova}
    ptmp = pasta / f".{mensagem_id}.prova.json.tmp"
    ptmp.write_text(json.dumps(registro, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8")
    os.replace(ptmp, pasta / f"{mensagem_id}.prova.json")
    return {"arquivo": alvo.name, "largura": largura, "altura": altura,
            "bytes": len(corpo), "formato": ext.lstrip("."), "sha256": sha[:16],
            "prova": str(prova.get("metodo") or ""), "forca": prova.get("forca")}


# ================================================================ erro legivel
def classificar(ia: str, exc: BaseException, tela: str = "") -> tuple:
    """(categoria, motivo legivel) de um pedido de imagem que falhou."""
    rotulo = correio.ROTULOS.get(ia, ia)
    nome = type(exc).__name__
    texto = " ".join(str(exc).split())
    if isinstance(exc, ImagemFalhou):
        return (exc.categoria, texto[:400])
    if nome == "ConteudoRecusado":
        return ("conteudo", f"o {rotulo} recusou o prompt (filtro de conteúdo, "
                            f"«CONTEÚDO ILEGAL»): reescreva o pedido. {texto[:160]}")
    if nome == "ParedeDePlanos":
        return ("parede", f"o {rotulo} pediu assinatura («Assine para Gerar») mesmo "
                          "depois de reabrir o perfil: confira a conta logada no PC")
    from .carteiro import classificar_erro, motivo_da_tela
    achado = motivo_da_tela(ia, tela)
    if achado:
        return achado
    if nome == "EsperaEstourou":
        return ("indisponivel", f"o {rotulo} não devolveu a imagem (3 tentativas): "
                                f"{texto[:160]}")
    return classificar_erro(ia, exc, tela)


# ================================================================== dublê
def png_de_teste(largura: int = 64, altura: int = 64, cor=(220, 30, 30)) -> bytes:
    """Um PNG de verdade (cor lisa), sem PIL: o que o dublê "gera"."""
    linha = b"\x00" + bytes(cor) * largura
    cru = linha * altura

    def pedaco(tipo: bytes, dados: bytes) -> bytes:
        return (struct.pack(">I", len(dados)) + tipo + dados
                + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF))

    cabeca = struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0)
    corpo = (b"\x89PNG\r\n\x1a\n" + pedaco(b"IHDR", cabeca)
             + pedaco(b"IDAT", zlib.compress(cru, 9)) + pedaco(b"IEND", b""))
    # passa do piso de bytes de `guardar` (imagem lisa comprime demais)
    if len(corpo) < BYTES_MIN:
        corpo = (corpo[:-12] + pedaco(b"tEXt", b"Comment\x00" + b"duble " * 100)
                 + corpo[-12:])
    return corpo


class SessaoImagemDuble:
    """Gera sem navegador. `falhar` (excecao), `sem_prova`, `tela` (texto
    que o classificador le), `corpo` (bytes a devolver)."""

    def __init__(self, ia: str, *, falhar=None, sem_prova: bool = False, tela: str = "",
                 corpo: bytes | None = None, demora_s: float = 0.0, dormir=time.sleep):
        self.ia = ia
        self.falhar = falhar
        self.sem_prova = sem_prova
        self.tela = tela
        self.corpo = corpo
        self.demora_s = demora_s
        self.dormir = dormir
        self.modelo = "dublê"
        self.pedidos: list = []
        self.reivindicadas: list = []

    def gerar_imagem(self, prompt: str, proporcao: str, mensagem_id: str = "") -> dict:
        self.pedidos.append({"prompt": prompt, "proporcao": proporcao, "id": mensagem_id})
        if self.demora_s:
            self.dormir(self.demora_s)
        if self.falhar is not None:
            raise self.falhar
        if self.sem_prova:
            raise SemProva(f"a imagem apareceu no {correio.ROTULOS.get(self.ia, self.ia)}, "
                           "mas nenhum card do histórico traz o seu prompt (conta "
                           "compartilhada): nada foi baixado")
        largura, altura = _tamanho_da_proporcao(proporcao)
        corpo = self.corpo if self.corpo is not None else png_de_teste(largura, altura)
        return {"bytes": corpo, "modelo": "dublê",
                "prova": {"comprovada": True, "metodo": "duble", "forca": "duble",
                          "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()[:16],
                          "verificado_em": correio.agora()}}

    def reivindicar(self, resultado: dict, mensagem_id: str) -> None:
        self.reivindicadas.append(mensagem_id)

    def texto_visivel(self) -> str:
        return self.tela


def _tamanho_da_proporcao(proporcao: str) -> tuple:
    try:
        a, b = (int(x) for x in str(proporcao).split(":"))
        escala = 64 / max(a, b)
        return (max(8, round(a * escala)), max(8, round(b * escala)))
    except (ValueError, ZeroDivisionError):
        return (64, 64)


def fabrica_imagem_duble(**ajustes):
    criadas = []

    @contextmanager
    def _abrir(ia):
        sessao = SessaoImagemDuble(ia, **ajustes)
        criadas.append(sessao)
        yield sessao

    _abrir.criadas = criadas
    return _abrir


# ============================================================ PicassoIA real
class SessaoPicasso:
    """O PicassoIA aberto no perfil das historias, pelo cliente de producao.

    A trava da conta e de quem chama (o carteiro). Aqui: interruptor da
    pipeline, espera que reenvia no estouro (`_gerar_esperando`), prova de
    origem FORTE e o download dos bytes pela propria sessao.
    """

    def __init__(self, cliente, ajustes: dict, config: dict, log=print):
        self.cliente = cliente
        self.ajustes = ajustes
        self.config = config
        self.log = log
        self.modelo = "PicassoIA Image"

    def gerar_imagem(self, prompt: str, proporcao: str, mensagem_id: str = "") -> dict:
        from builds.identity import proveniencia
        from contos.imagens import worker
        pausado, motivo = worker._pausado("picasso")
        if pausado:
            raise Pausado(f"o PicassoIA está pausado no painel ({motivo}): "
                          "retome para gerar")
        config = dict(self.config, aspect=str(proporcao))
        rotulo = f"ias_{mensagem_id}"
        alvo, _antes = worker._gerar_esperando(self.cliente, prompt, config, self.ajustes,
                                               self.log, rotulo)
        self.modelo = str((self.cliente.presets_aplicados or {}).get("modelo")
                          or "PicassoIA Image")
        prova = proveniencia.comprovar(self.cliente, rotulo, "imagem",
                                       self.cliente.prompt_enviado,
                                       self.cliente.enviado_em, alvo, self.ajustes)
        if not prova.get("comprovada") or not prova.get("url"):
            raise SemProva("a imagem apareceu no PicassoIA, mas a prova de origem falhou "
                           f"({prova.get('motivo') or 'sem motivo'}): conta "
                           "compartilhada, nada foi baixado")
        corpo = baixar(self.cliente.ctx, None, prova["url"],
                       float(self.ajustes.get("download_timeout", 120)))
        prova = dict(prova, proporcao=str(proporcao),
                     presets=dict(self.cliente.presets_aplicados or {}),
                     prompt_enviado_chars=len(self.cliente.prompt_enviado or ""))
        return {"bytes": corpo, "prova": prova, "modelo": self.modelo, "url": prova["url"]}

    def reivindicar(self, resultado: dict, mensagem_id: str) -> None:
        """A URL fica desta imagem: nenhuma build nem historia a pega depois."""
        try:
            from builds.identity import proveniencia
            proveniencia.reivindicar(resultado.get("prova"), f"ias_{mensagem_id}", "imagem")
        except Exception:                                      # noqa: BLE001
            pass

    def texto_visivel(self) -> str:
        try:
            return self.cliente.page.evaluate(
                "() => document.body ? document.body.innerText : ''") or ""
        except Exception:                                      # noqa: BLE001
            return ""


def config_do_picasso() -> dict:
    """O imagens.json das historias (esperas medidas), com o Aprimorador
    DESLIGADO a forca: ele trocava a acao da cena por retrato (14/09)."""
    try:
        from contos.imagens import fila
        base = dict(fila.carregar_config())
    except Exception:                                          # noqa: BLE001
        base = {}
    base = {k: v for k, v in base.items() if not str(k).startswith("_")}
    base.update({"aprimorar_prompt": False, "quantidade": 1,
                 "tentativas_por_espera": int(base.get("tentativas_por_espera", 3))})
    return base


@contextmanager
def sessao_picasso(*, headless: bool = False, log=print):
    from builds.identity import browser, config as icfg, picasso_client
    from builds.identity import provedores, session
    config = config_do_picasso()
    ajustes = {**icfg.settings("picasso"), **config}
    ajustes["aprimorar_prompt"] = False
    with browser.contexto_persistente(
            headless=headless, profile=icfg.profile_dir("picasso", canal="historias")) as ctx:
        page = browser.pagina(ctx)
        session.ensure_logged_in(page, ajustes, sel=provedores.seletores("picasso"),
                                 provedor="picasso")
        cliente = picasso_client.PicassoClient(ctx, page, ajustes)
        yield SessaoPicasso(cliente, ajustes, config, log)


# ============================================================ chat (casa)
def pedido_de_imagem(prompt: str, proporcao: str) -> str:
    """O texto que vai para a casa. Sem "PEDIDO DE TEXTO" (e o contrario):
    aqui a IA TEM de desenhar."""
    return (f"Crie uma imagem na proporção {proporcao}. Responda só com a imagem, "
            f"sem texto.\n\n{str(prompt).strip()}")


_JS_BAIXAR = (
    "async (src) => { const r = await fetch(src); if (!r.ok) return {erro: r.status};"
    " const b = new Uint8Array(await r.arrayBuffer()); let s = '';"
    " for (let i = 0; i < b.length; i += 32768)"
    "   s += String.fromCharCode.apply(null, b.subarray(i, i + 32768));"
    " return {b64: btoa(s)}; }")


def baixar(ctx, page, src: str, timeout_s: float = 120.0) -> bytes:
    """Os bytes da imagem, como o site serve (sem recomprimir). http(s) pela
    sessao do navegador (os cookies da conta); blob:/data:, ou http recusado,
    pelo `fetch` dentro da propria pagina. O erro diz o que cada caminho deu."""
    src = str(src or "")
    tentativas = []
    if not src.startswith(("http", "blob:", "data:image/")):
        # medido em 29/09 15:4x: `fetch("")` na pagina baixa a PROPRIA pagina
        # (864 KB de HTML); sem URL de imagem nao ha o que baixar
        raise ImagemFalhou(f"sem URL de imagem para baixar ({src[:40]!r})", "download")
    if src.startswith("http"):
        try:
            resposta = ctx.request.get(src, timeout=float(timeout_s) * 1000)
            corpo = resposta.body() if resposta.ok else b""
            if len(corpo) >= BYTES_MIN and extensao(corpo):
                return corpo
            tentativas.append(f"sessão: HTTP {resposta.status}, {len(corpo)} bytes"
                              + ("" if not corpo or extensao(corpo) else ", não é imagem"))
        except Exception as exc:                               # noqa: BLE001
            tentativas.append(f"sessão: {type(exc).__name__}")
    if page is None:
        raise ImagemFalhou(f"o download de {src[:80]} falhou ({'; '.join(tentativas)})",
                           "download")
    try:
        achado = page.evaluate(_JS_BAIXAR, src) or {}
    except Exception as exc:                                   # noqa: BLE001
        achado = {"erro": " ".join(str(exc).split())[:80]}
    if achado.get("b64"):
        corpo = base64.b64decode(achado["b64"])
        if len(corpo) >= BYTES_MIN and extensao(corpo):
            return corpo
        achado = {"erro": f"{len(corpo)} bytes que não são imagem"}
    tentativas.append(f"página: {achado.get('erro')}")
    raise ImagemFalhou(f"o download da imagem falhou ({'; '.join(tentativas)})", "download")


# O BOTAO DE BAIXAR NO TAMANHO ORIGINAL, por IA: `imagem_baixar` nos
# seletores do cliente (`contos/llm/seletores.py`).
# - Gemini (medido em 29/09 15:3x, scratchpad/diag_gemini_imagem.py): cada
#   imagem gerada tem "Baixar imagem no tamanho original" no seu
#   `single-image`, no DOM sem hover. E o caminho da qualidade original: as
#   15:23 o `src` da tela (1024x559) nao baixou nem pela sessao nem pelo fetch
#   da pagina (CORS do googleusercontent).
# - ChatGPT (medido em 29/09 16:1x, scratchpad/diag_chatgpt_baixar.py): o
#   botao "Baixar" so existe na visualizacao em tela cheia, que abre com o
#   clique na imagem (`imagem_abrir_para_baixar`); o arquivo e o PNG original
#   (1254x1254, os mesmos bytes do src `estuary/content`).
# - Grok: nao medido; baixa pelo `src`.
def botoes_de_baixar(cliente) -> list:
    """Os seletores do botao de baixar desta IA (vazio = nao medido)."""
    return list((getattr(cliente, "sel", None) or {}).get("imagem_baixar") or [])


# Marca a imagem escolhida (pelo src) DENTRO da resposta ao nosso turno, no
# recipiente de imagem gerada, e o botao de baixar do MESMO recipiente (sem
# ele, o ultimo da resposta). A mesma prova de posicao de
# `ClienteLLM._JS_IMAGENS`. Devolve {imagem, botao}.
_JS_MARCAR = (
    "([usuarios, turnos, recipientes, src, botoes]) => {"
    " const depois = (a, b) => !!(a.compareDocumentPosition(b)"
    "   & Node.DOCUMENT_POSITION_FOLLOWING);"
    " const todos = (raiz, lista) => { let out = [];"
    "   for (const s of lista) {"
    "     try { if (raiz !== document && raiz.matches(s)) out.push(raiz); } catch (e) {}"
    "     try { out = out.concat([...raiz.querySelectorAll(s)]); } catch (e) {} }"
    "   return out; };"
    " for (const v of document.querySelectorAll('[data-nf-baixar], [data-nf-imagem]')) {"
    "   v.removeAttribute('data-nf-baixar'); v.removeAttribute('data-nf-imagem'); }"
    " let usuario = null;"
    " for (const s of usuarios) {"
    "   let els = [];"
    "   try { els = [...document.querySelectorAll(s)]; } catch (e) { continue; }"
    "   const ultimo = els[els.length - 1];"
    "   if (ultimo && (!usuario || depois(usuario, ultimo))) usuario = ultimo;"
    " }"
    " if (!usuario) return {imagem: false, botao: false};"
    " let resposta = null;"
    " for (const t of todos(document, turnos)) {"
    "   if (!depois(usuario, t) || t.contains(usuario) || usuario.contains(t)) continue;"
    "   if (!resposta || depois(t, resposta)) resposta = t;"
    " }"
    " if (!resposta) return {imagem: false, botao: false};"
    " let alvo = null, caixa = null;"
    " for (const cx of todos(resposta, recipientes)) {"
    "   for (const im of cx.querySelectorAll('img')) {"
    "     if (!alvo && (im.currentSrc || im.src || '') === src) { alvo = im; caixa = cx; } } }"
    " if (!alvo) return {imagem: false, botao: false};"
    " alvo.setAttribute('data-nf-imagem', '1');"
    " let botao = null;"
    " if (botoes.length) {"
    "   let achados = todos(caixa, botoes);"
    "   if (!achados.length) achados = todos(resposta, botoes);"
    "   if (achados.length) botao = achados[achados.length - 1]; }"
    " if (botao) botao.setAttribute('data-nf-baixar', '1');"
    " return {imagem: true, botao: !!botao}; }")


def _primeiro_presente(page, seletores):
    for seletor in seletores:
        try:
            alvo = page.locator(seletor)
            if alvo.count():
                return alvo.first
        except Exception:                                      # noqa: BLE001
            continue
    return None


def _dimensoes_dos_bytes(corpo: bytes) -> tuple:
    try:
        import io

        from PIL import Image
        with Image.open(io.BytesIO(corpo)) as img:
            return tuple(int(x) for x in img.size)
    except Exception:                                          # noqa: BLE001
        return (None, None)


def mesma_proporcao(corpo: bytes, visto: dict, folga: float = 0.03) -> bool:
    """Os bytes baixados tem a proporcao da imagem que a tela mostrava? (o
    Gemini mostra 1024x559 e o original e 2816x1536: a mesma forma). Sem
    medida de um dos lados, nao ha como recusar: True."""
    largura, altura = _dimensoes_dos_bytes(corpo)
    w, h = int((visto or {}).get("w") or 0), int((visto or {}).get("h") or 0)
    if not (largura and altura and w and h):
        return True
    return abs((largura / altura) / (w / h) - 1.0) <= folga


def baixar_pelo_botao(cliente, visto: dict | None = None, timeout_s: float = 90.0,
                      log=print) -> bytes | None:
    """Os bytes pelo botao do proprio site (tamanho original), ou None quando a
    IA nao tem o botao medido ou ele nao esta junto da imagem da resposta.

    Medido no Gemini em 29/09 15:5x (scratchpad/diag_botao_gemini.py): o
    botao nasce `disabled` ate a imagem carregar; o clique mostra "Fazendo o
    download no tamanho original...", o site busca `gg` (texto, ~500 bytes) e
    depois `rd-gg` (o JPEG inteiro: 2.992.466 bytes para a imagem que a tela
    mostrava em 1024x559) e so entao sai o evento de download
    (`Gemini_Generated_Image_*.jfif`). Com a API sincrona os eventos so
    chegam DENTRO de uma chamada: a espera e `wait_for_timeout`, nunca
    `time.sleep`. Se o download nao vier, vale a maior resposta de imagem que
    o clique buscou (os mesmos bytes). No ChatGPT o botao esta na tela cheia:
    clica na imagem, baixa e fecha com Escape.
    """
    seletores = botoes_de_baixar(cliente)
    if not seletores:
        return None
    s = getattr(cliente, "sel", None) or {}
    abrir = bool(s.get("imagem_abrir_para_baixar"))
    page = cliente.page
    marcado = page.evaluate(_JS_MARCAR, [
        list(s.get("turno_usuario") or []), list(s.get("imagem_turno") or []),
        list(s.get("imagem_gerada") or []), str((visto or {}).get("src") or ""),
        [] if abrir else list(seletores)])
    if not isinstance(marcado, dict) or not marcado.get("imagem"):
        return None
    if abrir:
        imagem_na_tela = page.locator("[data-nf-imagem='1']").first
        try:
            imagem_na_tela.scroll_into_view_if_needed(timeout=5000)
        except Exception:                                      # noqa: BLE001
            pass
        page.wait_for_timeout(700)
        imagem_na_tela.click(timeout=10000)
        alvo = None
        for _ in range(40):                     # ate 20 s: a tela cheia abrindo
            alvo = _primeiro_presente(page, seletores)
            if alvo is not None:
                break
            page.wait_for_timeout(500)
        if alvo is None:
            _fechar_tela_cheia(page)
            raise ImagemFalhou("abri a imagem e o botão de baixar não apareceu em 20 s",
                               "download")
    else:
        if not marcado.get("botao"):
            return None
        alvo = page.locator("[data-nf-baixar='1']").first
        try:
            alvo.scroll_into_view_if_needed(timeout=5000)
        except Exception:                                      # noqa: BLE001
            pass
    habilitado = False
    for volta in range(60):                     # ate 30 s: a imagem carregando
        if volta % 10 == 0 and not abrir:
            # a imagem so carrega NA VISTA do container com rolagem propria:
            # "rolar se preciso" nem sempre rola (o botao ja parece visivel)
            try:
                alvo.evaluate("el => el.scrollIntoView({block: 'center'})")
                alvo.hover(timeout=2000, force=True)
            except Exception:                                  # noqa: BLE001
                pass
        try:
            habilitado = bool(alvo.evaluate(
                "el => !el.disabled && el.getAttribute('disabled') === null"))
        except Exception:                                      # noqa: BLE001
            habilitado = False
        if habilitado:
            break
        page.wait_for_timeout(500)
    if not habilitado:
        if abrir:
            _fechar_tela_cheia(page)
        raise ImagemFalhou("o botão de baixar ficou desabilitado por 30 s (a imagem "
                           "não carregou na tela)", "download")
    baixados, respostas = [], []

    def _baixou(download):
        baixados.append(download)

    def _respondeu(resposta):
        try:
            if (resposta.request.resource_type in ("fetch", "xhr")
                    and str(resposta.headers.get("content-type") or "").startswith("image/")):
                respostas.append(resposta)
        except Exception:                                      # noqa: BLE001
            pass

    page.on("download", _baixou)
    page.on("response", _respondeu)
    try:
        alvo.click(timeout=10000)
        fim = time.monotonic() + float(timeout_s)
        while time.monotonic() < fim and not baixados:
            page.wait_for_timeout(500)
        if baixados:
            caminho = baixados[-1].path()
            corpo = Path(caminho).read_bytes() if caminho else b""
            log(f"[{cliente.provedor}] baixada pelo botão do site: "
                f"{baixados[-1].suggested_filename} ({len(corpo)} bytes)")
            return corpo
        melhor = b""
        for resposta in respostas:
            try:
                corpo = resposta.body()
            except Exception:                                  # noqa: BLE001
                continue
            if len(corpo) > len(melhor) and extensao(corpo):
                melhor = corpo
        if melhor:
            log(f"[{cliente.provedor}] o download não veio em {timeout_s:.0f}s; uso a "
                f"resposta de imagem que o botão buscou ({len(melhor)} bytes)")
            return melhor
        raise ImagemFalhou(f"cliquei em baixar e nada veio em {timeout_s:.0f}s", "download")
    finally:
        for evento, funcao in (("download", _baixou), ("response", _respondeu)):
            try:
                page.remove_listener(evento, funcao)
            except Exception:                                  # noqa: BLE001
                pass
        if abrir:
            _fechar_tela_cheia(page)


def _fechar_tela_cheia(page) -> None:
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)
    except Exception:                                          # noqa: BLE001
        pass


def _normal(texto: str) -> str:
    return " ".join(str(texto or "").split()).lower()


def baixar_da_resposta(cliente, prompt: str, proporcao: str | None = None,
                       log=print) -> dict | None:
    """A imagem que a ULTIMA resposta do chat trouxe (`cliente.imagens_na_resposta`,
    que `ClienteLLM.esperar_resposta` preenche), baixada com a PROVA:

    1. o ultimo turno do usuario na tela e o NOSSO pedido;
    2. a imagem esta, agora, DENTRO da resposta a ele, no recipiente de imagem
       gerada (d228c94f, 29/09 16:02: um ANUNCIO no mesmo turno virou "o
       gato");
    3. o src dela NAO existia na pagina antes do envio;
    4. a IA nao diz mais que esta gerando.

    None se a resposta nao trouxe imagem. Levanta `SemProva` (nada vai ao
    disco) se uma das quatro falhar."""
    imagens = list(getattr(cliente, "imagens_na_resposta", None) or [])
    if not imagens:
        return None
    visto = imagens[-1]
    achado = (cliente.imagens_da_resposta() if hasattr(cliente, "imagens_da_resposta")
              else {}) or {}
    turno = str(achado.get("turno") or "")
    trecho = _normal(prompt)[:60]
    if not achado.get("ancorado") or (trecho and trecho not in _normal(turno)):
        raise SemProva("o último turno na casa não é o seu pedido: não baixo imagem "
                       "que não sei de onde veio")
    src = str(visto.get("src") or "")
    na_resposta = {str(i.get("src") or "") for i in achado.get("imagens") or []}
    if not achado.get("resposta") or not src or src not in na_resposta:
        raise SemProva("a imagem não está dentro da resposta ao seu pedido (anúncio, "
                       "sugestão ou imagem de outro turno): nada foi gravado")
    antes = getattr(cliente, "_srcs_antes_do_envio", None)
    if antes is None:
        raise SemProva("sem a foto da página antes do envio, não sei se a imagem é "
                       "nova: nada foi gravado")
    if src in antes or (visto.get("src_attr") and visto.get("src_attr") in antes):
        raise SemProva("a imagem já estava na página antes do envio: não é a resposta "
                       "ao seu pedido; nada foi gravado")
    if achado.get("gerando"):
        raise SemProva("a IA ainda diz que está gerando a imagem: não baixo a prévia")
    # primeiro o botao do site (tamanho original); depois o `src` da tela
    corpo, como, falhas = b"", "", []
    try:
        corpo = baixar_pelo_botao(cliente, visto, log=log)
        if corpo is None:
            falhas.append("botão: não há botão de baixar junto da imagem")
            corpo = b""
        elif not (len(corpo) >= BYTES_MIN and extensao(corpo)):
            falhas.append(f"botão: {len(corpo)} bytes que não são imagem")
            corpo = b""
        elif not mesma_proporcao(corpo, visto):
            falhas.append("botão: o arquivo baixado não tem a forma da imagem da tela "
                          f"({_dimensoes_dos_bytes(corpo)} contra {visto.get('w')}x"
                          f"{visto.get('h')})")
            corpo = b""
        else:
            como = "botao_tamanho_original"
    except Exception as exc:                                   # noqa: BLE001
        falhas.append(f"botão: {type(exc).__name__}: {' '.join(str(exc).split())[:100]}")
    if not como:
        if falhas and botoes_de_baixar(cliente):
            log(f"[{cliente.provedor}] {falhas[-1]}; tento o src da tela")
        try:
            corpo = baixar(cliente.ctx, cliente.page, src,
                           float((cliente.ajustes or {}).get("download_timeout", 120)))
            como = "src_da_tela"
        except ImagemFalhou as exc:
            raise ImagemFalhou("; ".join(falhas + [str(exc)]), "download") from exc
    log(f"[{cliente.provedor}] imagem da resposta baixada ({como}; na tela "
        f"{visto.get('w')}x{visto.get('h')}, {len(corpo)} bytes)")
    prova = {"comprovada": True, "metodo": "turno_na_casa", "forca": "casa",
             "provedor": cliente.provedor, "casa_url": str(cliente.page.url or ""),
             "turno_usuario": turno[:200],
             "prompt_sha256": hashlib.sha256(_normal(prompt).encode("utf-8")).hexdigest()[:16],
             "src": src[:300], "na_tela": [visto.get("w"), visto.get("h")],
             "alt": str(visto.get("alt") or "")[:160],
             "dentro_da_resposta": True, "src_novo": True,
             "imagens_antes_do_envio": len(antes),
             "ignoradas_fora_da_resposta": int(achado.get("fora") or 0),
             "imagens_na_resposta": len(imagens), "download": como,
             "verificado_em": correio.agora()}
    if proporcao:
        prova["proporcao"] = str(proporcao)
    return {"bytes": corpo, "prova": prova,
            "modelo": getattr(cliente, "modelo_atual", "") or cliente.provedor}


def gerar_no_chat(cliente, prompt: str, proporcao: str, *, log=print) -> dict:
    """Pede a imagem na casa (o chat ja aberto) pelo `perguntar` de sempre
    (diario, envio com prova, espera que agora reconhece imagem) e baixa a
    imagem que nasceu depois do NOSSO turno. `SemImagem` quando a IA respondeu
    so com texto."""
    pedido = pedido_de_imagem(prompt, proporcao)
    texto = cliente.perguntar(pedido)
    saida = baixar_da_resposta(cliente, pedido, proporcao, log=log)
    if saida is None:
        rotulo = correio.ROTULOS.get(cliente.provedor, cliente.provedor)
        raise SemImagem(f"o {rotulo} respondeu sem imagem: "
                        f"«{' '.join(str(texto or '').split())[:220]}»")
    return saida


__all__ = ["VIA", "gerador", "geradores", "conferir_pedido", "rodizio_ordem",
           "fora_de_cota", "guardar", "classificar", "extensao", "dimensoes",
           "png_de_teste", "SessaoImagemDuble", "fabrica_imagem_duble", "SessaoPicasso",
           "baixar_da_resposta",
           "sessao_picasso", "config_do_picasso", "gerar_no_chat", "pedido_de_imagem",
           "baixar", "ImagemFalhou", "SemProva", "SemImagem", "Pausado", "ImagemInvalida",
           "TIPOS_MIME"]
