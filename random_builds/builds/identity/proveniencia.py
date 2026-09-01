"""Prova de origem: o que foi baixado nasceu MESMO do prompt que enviamos?

As contas do PicassoIA e do Digen sao COMPARTILHADAS com outras pessoas. Isso
muda a pergunta que o worker faz na hora de baixar. Nao basta "apareceu um
resultado novo depois do meu clique": e preciso "este resultado nasceu do MEU
prompt". A resposta errada a primeira pergunta gravou, em generation_00044,
uma foto de outra pessoa como referencia da build - ela entrou no historico da
conta 0,1 s depois do envio, era retrato, e passou por toda guarda de tela.
O payoff foi ao Digen com ela anexada.

Duas forcas de prova, e o worker registra qual valeu:

  forte   o provedor mostra o PROMPT ao lado do resultado (aba Historico do
          PicassoIA). O card que traz o nosso prompt, com data igual ou
          posterior ao envio, e o nosso - e a imagem DELE e a que se baixa.
          Se o candidato que a espera devolveu for outro, ele e descartado.
  media   o provedor isola por container (space do Digen) e o card nao mostra
          o prompt. Vale o card novo no espaco que este worker criou, com os
          presets que ele mesmo aplicou (modelo/duracao/resolucao).

Sem prova, NADA e baixado nem gravado; a tentativa conta como falha e a
proxima gera de novo. Uma URL ja reivindicada por outra build nunca e aceita
de novo (origens.jsonl): a mesma imagem nao pode ser personagem de duas
roletas.

Este modulo e PURO de proposito (sem browser): quem fala com a tela sao os
clientes, que entregam listas de cards; a decisao mora aqui, onde da para
testar sem abrir o Chrome.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

from . import config

FORTE, MEDIA, FRACA = "forte", "media", "fraca"
METODO_HISTORICO = "historico_prompt"
METODO_ESPACO = "espaco_proprio"

# Toda URL aceita, uma linha por reivindicacao. Append-only pelos mesmos
# motivos do history.jsonl: sem read-modify-write, sem lock.
ARQUIVO_ORIGENS = config.IDENTITY_DIR / "origens.jsonl"

# Bloco `proveniencia` do config/identity.json. `exigir: false` volta ao
# comportamento antigo (a prova e registrada, mas nao barra) - e rollback,
# nao modo normal.
PADRAO = {
    "exigir": True,
    "espera_historico_s": 240,
    "cards_inspecionados": 12,
    "tolerancia_data_min": 3,
}

# Data do card do PicassoIA, no formato que a tela mostra em pt-BR:
# "25 DE AGO. DE 2026, 22:26". Minuto e a precisao que existe.
MESES = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
         "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}
_DATA_CARD = re.compile(
    r"(\d{1,2})\s+DE\s+([A-ZÇ]{3})[A-ZÇ]*\.?\s+DE\s+(\d{4}),?\s+(\d{1,2}):(\d{2})",
    re.IGNORECASE)

# Um card truncado pela tela ainda identifica o prompt se tiver ao menos isto.
PREFIXO_MINIMO = 120

# Reticencias que a tela usa ao truncar (um caractere ou tres pontos).
_RETICENCIAS = "…."


def ajustes(raiz: dict | None) -> dict:
    bloco = (raiz or {}).get("proveniencia") or {}
    saida = dict(PADRAO)
    saida.update({k: v for k, v in bloco.items() if not k.startswith("_")})
    return saida


def exigida(raiz: dict | None) -> bool:
    return bool(ajustes(raiz)["exigir"])


# ------------------------------------------------------------- comparacoes
def normalizar(texto) -> str:
    return " ".join(str(texto or "").split()).strip().lower()


def prompt_bate(no_card, enviado) -> bool:
    """O texto do card e o prompt enviado (ou um prefixo longo dele)?

    O prefixo cobre a tela truncando com reticencias; o piso evita que um
    card de duas palavras "case" com qualquer prompt.
    """
    a, b = normalizar(no_card), normalizar(enviado)
    if not a or not b:
        return False
    if a == b:
        return True
    a = a.rstrip(_RETICENCIAS).strip()
    return len(a) >= PREFIXO_MINIMO and b.startswith(a)


def data_do_card(texto) -> datetime | None:
    """Data/hora LOCAL (naive) que o card mostra, ou None se nao der para ler."""
    achado = _DATA_CARD.search(str(texto or ""))
    if not achado:
        return None
    dia, mes, ano, hora, minuto = achado.groups()
    numero = MESES.get(mes.upper()[:3])
    if numero is None:
        return None
    try:
        return datetime(int(ano), numero, int(dia), int(hora), int(minuto))
    except ValueError:
        return None


def _local(quando) -> datetime | None:
    """Datetime aware (ou ISO) -> hora local naive, comparavel com o card."""
    if quando is None:
        return None
    if isinstance(quando, str):
        try:
            quando = datetime.fromisoformat(quando)
        except ValueError:
            return None
    if quando.tzinfo is None:
        return quando
    return quando.astimezone().replace(tzinfo=None)


def escolher_card(cards: list[dict], prompt: str, enviado_em=None,
                  tolerancia_min: float = 3.0) -> dict:
    """O card do historico que e NOSSO, ou por que nenhum e.

    `cards` vem na ordem da tela (mais novo primeiro). Um card so vale se
    traz o prompt enviado E nao e anterior ao envio (quando a data e legivel;
    `tolerancia_min` absorve relogio do site vs. da maquina). Devolve
    {"card": dict | None, "motivo": str}.
    """
    candidatos = [c for c in cards if prompt_bate(c.get("prompt"), prompt)]
    if not candidatos:
        return {"card": None,
                "motivo": f"nenhum dos {len(cards)} card(s) do historico traz "
                          "o prompt enviado"}
    envio = _local(enviado_em)
    limite = envio - timedelta(minutes=float(tolerancia_min)) if envio else None
    motivo = ""
    for card in candidatos:
        data = data_do_card(card.get("data") or card.get("texto"))
        if limite is not None and data is not None and data < limite:
            motivo = (f"o card com o prompt e de {data:%d/%m %H:%M}, anterior "
                      f"ao envio ({envio:%d/%m %H:%M})")
            continue
        return {"card": card, "motivo": ""}
    return {"card": None,
            "motivo": motivo or "nenhum card com o prompt e posterior ao envio"}


def presets_batem(texto_do_card, presets: dict | None) -> bool | None:
    """Os presets aplicados (modelo/duracao/resolucao) aparecem no card?

    None = nao da para conferir (card sem texto ou nada aplicado). False e
    evidencia POSITIVA de card alheio; None e so ausencia de evidencia.
    """
    texto = normalizar(texto_do_card)
    esperados = [normalizar(v) for k, v in (presets or {}).items()
                 if k in ("modelo", "duracao", "resolucao") and v]
    if not texto or not esperados:
        return None
    tokens = set(texto.split())
    return all(e in tokens or (" " in e and e in texto) for e in esperados)


# ------------------------------------------------------------------ provas
def _hash(texto) -> str:
    return hashlib.sha256(normalizar(texto).encode("utf-8")).hexdigest()[:16]


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _iso(quando) -> str | None:
    if isinstance(quando, datetime):
        return quando.isoformat(timespec="seconds")
    return str(quando) if quando else None


def prova_forte(provedor: str, card: dict, url: str, candidato, prompt: str,
                enviado_em=None) -> dict:
    data = data_do_card(card.get("data") or card.get("texto"))
    return {
        "comprovada": True,
        "forca": FORTE,
        "metodo": METODO_HISTORICO,
        "provedor": provedor,
        "alvo": url,
        "url": url,
        "candidato": candidato,
        "candidato_descartado": bool(candidato) and candidato != url,
        "prompt_sha256": _hash(prompt),
        "enviado_em": _iso(enviado_em),
        "verificado_em": _agora(),
        "card": {"posicao": card.get("indice"),
                 "data": data.isoformat(timespec="minutes") if data else None,
                 "prompt_bate": True},
        "motivo": "",
    }


def prova_media(provedor: str, alvo, espaco: str, presets: dict | None,
                texto_do_card, conferidos: bool | None, prompt: str,
                enviado_em=None) -> dict:
    return {
        "comprovada": True,
        "forca": MEDIA if conferidos else FRACA,
        "metodo": METODO_ESPACO,
        "provedor": provedor,
        "alvo": alvo,
        "url": None,
        "candidato": alvo,
        "candidato_descartado": False,
        "prompt_sha256": _hash(prompt),
        "enviado_em": _iso(enviado_em),
        "verificado_em": _agora(),
        "card": {"posicao": alvo, "espaco": espaco,
                 "presets": dict(presets or {}),
                 "texto": " ".join(str(texto_do_card or "").split())[:160],
                 "presets_conferidos": conferidos},
        "motivo": "" if conferidos else "presets do card nao conferiveis",
    }


def sem_prova(provedor: str, motivo: str, candidato, prompt: str | None = None,
              enviado_em=None) -> dict:
    return {
        "comprovada": False,
        "forca": None,
        "metodo": None,
        "provedor": provedor,
        "alvo": None,
        "url": None,
        "candidato": candidato,
        "candidato_descartado": False,
        "prompt_sha256": _hash(prompt) if prompt else None,
        "enviado_em": _iso(enviado_em),
        "verificado_em": _agora(),
        "card": None,
        "motivo": str(motivo),
    }


# --------------------------------------------------------------- registro
def reivindicadas() -> dict[str, tuple[str, str]]:
    """{url: (generation_id, slot)} de tudo que ja foi aceito. Nunca levanta."""
    saida: dict[str, tuple[str, str]] = {}
    if not ARQUIVO_ORIGENS.is_file():
        return saida
    try:
        with open(ARQUIVO_ORIGENS, encoding="utf-8-sig") as fh:
            for linha in fh:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    dado = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                url = dado.get("url")
                if url:
                    saida[url] = (str(dado.get("generation_id")),
                                  str(dado.get("slot")))
    except OSError:
        pass
    return saida


def reivindicar(prova: dict | None, generation_id: str, slot: str) -> None:
    """Anota que ESTA build ficou com aquela URL. Nunca levanta."""
    if not prova or not prova.get("url"):
        return
    linha = {"ts": _agora(), "generation_id": generation_id, "slot": slot,
             "url": prova["url"], "provedor": prova.get("provedor"),
             "forca": prova.get("forca"),
             "prompt_sha256": prova.get("prompt_sha256")}
    try:
        ARQUIVO_ORIGENS.parent.mkdir(parents=True, exist_ok=True)
        with open(ARQUIVO_ORIGENS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except OSError:
        pass


def comprovar(client, generation_id: str, slot: str, prompt: str,
              enviado_em, alvo, raiz_ajustes: dict | None) -> dict:
    """A prova do cliente, mais o portao que nenhum cliente enxerga sozinho:
    uma URL ja reivindicada por OUTRA build e imagem alheia por definicao."""
    provedor = getattr(client, "PROVEDOR", None) or "?"
    comprovar_origem = getattr(client, "comprovar_origem", None)
    if not callable(comprovar_origem):
        return sem_prova(provedor, "o cliente nao sabe comprovar origem", alvo,
                         prompt, enviado_em)
    prova = comprovar_origem(alvo, prompt, enviado_em)
    if not isinstance(prova, dict):
        return sem_prova(provedor, "o cliente nao devolveu prova", alvo,
                         prompt, enviado_em)
    url = prova.get("url")
    if prova.get("comprovada") and url:
        dona = reivindicadas().get(url)
        if dona and tuple(dona) != (generation_id, slot):
            return sem_prova(
                prova.get("provedor") or provedor,
                f"a imagem ...{url[-48:]} ja e de {dona[0]}/{dona[1]}",
                alvo, prompt, enviado_em)
    return prova
