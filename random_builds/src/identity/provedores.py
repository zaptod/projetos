"""Registro dos provedores: quem sao, com que seletores e com que cliente.

Existe para nao espalhar `if provedor == "picasso"` por worker, health, probe e
CLI. Quem quiser saber algo de um provedor pergunta aqui.
"""
from __future__ import annotations

from . import (dreamface_selectors, picasso_selectors, selectors,
               slots)

# A ORDEM E A ORDEM DAS PASSADAS DA RODADA, e nao e alfabetica por acaso:
# picasso antes de digen e o que faz as duas imagens ja estarem no disco
# quando o payoff e reivindicado. O grafo de dependencia se resolve sozinho
# dentro da MESMA rodada, sem escalonador e sem estado novo.
TODOS = (slots.PICASSO, slots.DIGEN)

_SELETORES = {
    slots.DIGEN: selectors,
    slots.PICASSO: picasso_selectors,
    slots.DREAMFACE: dreamface_selectors,
}


def seletores(provedor: str):
    try:
        return _SELETORES[provedor]
    except KeyError:
        raise ValueError(f"provedor sem seletores: {provedor!r} "
                         f"(conhecidos: {', '.join(_SELETORES)})") from None


def cliente(provedor: str, ctx, page, ajustes: dict, rng=None,
            ao_descobrir_espaco=None):
    """Instancia o cliente daquele provedor.

    Import tardio: `client` e `picasso_client` puxam o modulo de browser, e
    quem so quer listar provedores (a CLI, o doctor local) nao precisa pagar
    isso.
    """
    if provedor == slots.DIGEN:
        from .client import DigenClient
        return DigenClient(ctx, page, ajustes, rng,
                           ao_descobrir_espaco=ao_descobrir_espaco)
    if provedor == slots.PICASSO:
        from .picasso_client import PicassoClient
        return PicassoClient(ctx, page, ajustes, rng,
                             ao_descobrir_espaco=ao_descobrir_espaco)
    raise ValueError(f"provedor desconhecido: {provedor!r}")


def rotulo(provedor: str) -> str:
    return {slots.DIGEN: "Digen (video)",
            slots.PICASSO: "PicassoIA (imagem)",
            slots.DREAMFACE: "DreamFace (imagem)"}.get(provedor, provedor)


def slots_de(provedor: str) -> tuple[str, ...]:
    """Quais slots aquele provedor atende."""
    return tuple(s for s in slots.SLOTS if slots.provedor(s) == provedor)
