"""Identidade de espectador e o nome que vai para a tela.

O nome de exibicao de um espectador e conteudo gerado por terceiro que acaba
renderizado numa transmissao monetizada. Tratar isso como texto confiavel e o
caminho mais curto para um incidente ao vivo, entao esta camada trabalha com
**dois nomes distintos**:

``catalog_name``
    Slug ASCII imutavel derivado do id do lutador, com prefixo reservado. E o
    que o motor usa como chave -- ele e name-keyed de ponta a ponta
    (``match_config["p1_nome"]``, ``nome_arma``, saves de torneio). Como o
    gerador de roster nunca produz um nome comecando com ``@``, colisao com o
    catalogo curado e impossivel por construcao, nao por sorte.

``display_name``
    O texto sanitizado que o overlay mostra. Pode mudar quando a pessoa troca o
    nome na plataforma; nada depende dele para funcionar.

Essa indireccao resolve de uma vez colisao de nome, renome, moderacao e abuso
de Unicode no HUD.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from typing import Iterable

# Prefixo que o gerador de roster nunca produz: ``gerar_nome_personagem`` compoe
# a partir de listas de nomes proprios e titulos, sempre iniciando por letra.
PREFIXO_CATALOGO = "@"

# Teto do nome na tela. Curto de proposito: o HUD ja reduz fonte para caber
# (``_renderizar_texto_ajustado``), e nome longo rouba espaco do combate.
LIMITE_DISPLAY = 16

# Categorias Unicode aceitas depois da normalizacao NFKC.
#   L* -> letras (inclui acentuadas ja compostas)
#   Nd -> digitos decimais
# Tudo que sobra e recusado, o que cobre de uma vez:
#   Cf -> zero-width, joiners e sobrescritas bidirecionais (U+202A-E, U+2066-9)
#   Cc/Co/Cs -> controle, uso privado, substitutos
#   Mn/Mc -> marcas combinantes soltas, o material de "zalgo"
#   S*/P* -> simbolos e pontuacao, que servem para imitar outra pessoa
_CATEGORIAS_ACEITAS = frozenset({"Lu", "Ll", "Lt", "Lm", "Lo", "Nd"})


@dataclass(frozen=True)
class NomeExibicao:
    """Resultado da sanitizacao, com trilha do que aconteceu."""

    valor: str
    original: str
    alterado: bool
    motivo: str = ""

    @property
    def usou_fallback(self) -> bool:
        return bool(self.motivo)


def _apenas_permitidos(texto: str) -> tuple[str, bool]:
    """Filtra por categoria Unicode; devolve o texto e se algo foi removido."""
    saida: list[str] = []
    removeu = False
    for caractere in texto:
        categoria = unicodedata.category(caractere)
        if categoria in _CATEGORIAS_ACEITAS:
            saida.append(caractere)
        elif categoria == "Zs" or caractere in " \t":
            saida.append(" ")
        else:
            removeu = True
    return "".join(saida), removeu


def handle_de(viewer_id: str, platform: str = "") -> str:
    """Apelido determinista e sempre seguro, usado quando o nome nao serve.

    Usa apenas letras e digitos de proposito: o handle e o ultimo recurso, entao
    sanitiza-lo precisa ser uma operacao nula. Um separador como ``-`` seria
    removido pelo proprio filtro e o fallback nao bateria consigo mesmo.
    """
    semente = f"{platform}:{viewer_id}".encode("utf-8")
    return "Lutador" + hashlib.blake2s(semente, digest_size=3).hexdigest().upper()


def catalog_name_de(fighter_id: str) -> str:
    """Chave do lutador no motor: ASCII, estavel e fora do espaco curado."""
    fighter_id = str(fighter_id).strip()
    if not fighter_id:
        raise ValueError("fighter_id nao pode ser vazio")
    return f"{PREFIXO_CATALOGO}{fighter_id}"


def eh_lutador_de_espectador(nome: object) -> bool:
    """Distingue um lutador de espectador do roster curado pelo prefixo."""
    return isinstance(nome, str) and nome.startswith(PREFIXO_CATALOGO)


def sanitizar_display_name(
    bruto: object,
    *,
    fallback: str,
    blocklist: Iterable[str] = (),
) -> NomeExibicao:
    """Normaliza um nome de plataforma para algo seguro de renderizar.

    A ordem importa: normalizar antes de filtrar impede que uma forma
    compatibilidade escape do filtro, e verificar a blocklist depois de
    normalizar impede que caracteres invisiveis quebrem a comparacao.

    Cair no ``fallback`` nunca e silencioso -- ``motivo`` diz o porque, e quem
    chama grava o original para auditoria e moderacao.
    """
    original = bruto if isinstance(bruto, str) else ""

    texto = unicodedata.normalize("NFKC", original)
    texto, removeu = _apenas_permitidos(texto)
    texto = " ".join(texto.split())

    if len(texto) > LIMITE_DISPLAY:
        texto = texto[:LIMITE_DISPLAY].rstrip()
        removeu = True

    if not texto:
        return NomeExibicao(fallback, original, True, "vazio_apos_sanitizacao")

    comparavel = texto.casefold()
    for termo in blocklist:
        termo = str(termo).strip().casefold()
        if termo and termo in comparavel:
            return NomeExibicao(fallback, original, True, "blocklist")

    return NomeExibicao(texto, original, removeu or texto != original)


def resolver_display_name(
    bruto: object,
    *,
    viewer_id: str,
    platform: str = "",
    blocklist: Iterable[str] = (),
) -> NomeExibicao:
    """Sanitiza usando o handle determinista do espectador como fallback."""
    return sanitizar_display_name(
        bruto,
        fallback=handle_de(viewer_id, platform),
        blocklist=blocklist,
    )


__all__ = [
    "LIMITE_DISPLAY",
    "PREFIXO_CATALOGO",
    "NomeExibicao",
    "catalog_name_de",
    "eh_lutador_de_espectador",
    "handle_de",
    "resolver_display_name",
    "sanitizar_display_name",
]
