"""Contrato de evento de espectador, agnostico de plataforma.

Este e o unico vocabulario que o resto da camada de live conhece. Um adaptador
novo (TikTok, Twitch, um bot proprio) so precisa produzir ``ViewerEvent``; nada
alem de ``sources/`` deve saber o formato bruto de nenhuma plataforma.

O evento e imutavel e validado na fronteira: dados de plataforma sao entrada
nao confiavel, e um payload malformado tem que falhar aqui, longe do motor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


_MAPA_VAZIO: Mapping[str, Any] = MappingProxyType({})

# O nome de exibicao vira texto renderizado na transmissao. O limite aqui e de
# sanidade estrutural; a sanitizacao de conteudo acontece no registro de
# espectadores, que e quem decide o nome final do lutador.
LIMITE_NOME = 200
LIMITE_TEXTO = 2000


class EventKind(str, Enum):
    """Categorias de interacao que a sessao sabe interpretar."""

    CHAT = "chat"
    GIFT = "gift"
    SUPERCHAT = "superchat"
    MEMBERSHIP = "membership"
    FOLLOW = "follow"

    @classmethod
    def de_valor(cls, valor: object) -> "EventKind":
        if isinstance(valor, cls):
            return valor
        try:
            return cls(str(valor).strip().lower())
        except ValueError as exc:
            conhecidas = ", ".join(sorted(item.value for item in cls))
            raise ValueError(
                f"kind de evento desconhecido: {valor!r} (conhecidos: {conhecidas})"
            ) from exc


def _texto(valor: object, campo: str, limite: int, *, obrigatorio: bool = False) -> str:
    if valor is None:
        texto = ""
    elif isinstance(valor, str):
        texto = valor
    else:
        raise TypeError(f"{campo} precisa ser texto, recebido {type(valor).__name__}")
    texto = texto.strip()
    if obrigatorio and not texto:
        raise ValueError(f"{campo} nao pode ser vazio")
    if len(texto) > limite:
        raise ValueError(f"{campo} excede {limite} caracteres")
    return texto


def _inteiro(valor: object, campo: str, *, minimo: int = 0) -> int:
    if valor is None:
        return 0
    if isinstance(valor, bool):
        raise TypeError(f"{campo} precisa ser inteiro, recebido bool")
    try:
        numero = int(valor)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{campo} precisa ser inteiro, recebido {valor!r}") from exc
    if numero < minimo:
        raise ValueError(f"{campo} nao pode ser menor que {minimo}")
    return numero


def _numero(valor: object, campo: str, *, minimo: float = 0.0) -> float:
    if valor is None:
        return 0.0
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{campo} precisa ser numerico, recebido {valor!r}") from exc
    if not math.isfinite(numero):
        raise ValueError(f"{campo} precisa ser finito")
    if numero < minimo:
        raise ValueError(f"{campo} nao pode ser menor que {minimo}")
    return numero


@dataclass(frozen=True, slots=True)
class ViewerEvent:
    """Uma interacao de espectador, ja normalizada.

    Tres campos carregam peso especial:

    ``event_id``
        Chave de idempotencia. Uma reconexao faz a plataforma reentregar o que
        ja tinha sido lido; aplicar um gift duas vezes seria cobrar a pessoa
        duas vezes. Toda decisao gravada e chaveada por este id.
    ``viewer_id``
        Identidade estavel da plataforma e a unica chave confiavel:
        ``viewer_name`` muda quando a pessoa troca o nome de exibicao e pode
        colidir entre espectadores diferentes.
    ``value_units``
        Valor ja normalizado em creditos inteiros. E o **unico** numero que a
        camada de comandos enxerga: converter moeda e responsabilidade do
        adaptador, para que o vocabulario de jogo nao aprenda nada sobre
        cambio nem sobre tabela de gift de plataforma.
    """

    platform: str
    viewer_id: str
    viewer_name: str
    kind: EventKind
    event_id: str = ""
    sequence: int = 0
    text: str = ""
    value_units: int = 0
    is_moderator: bool = False
    is_owner: bool = False
    gift_id: str = ""
    raw_amount: float = 0.0
    raw_currency: str = ""
    timestamp: float = 0.0
    raw: Mapping[str, Any] = field(default=_MAPA_VAZIO, repr=False, compare=False)

    def __post_init__(self) -> None:
        definir = object.__setattr__
        definir(self, "platform", _texto(self.platform, "platform", 40, obrigatorio=True))
        definir(self, "viewer_id", _texto(self.viewer_id, "viewer_id", 200, obrigatorio=True))
        definir(self, "viewer_name", _texto(self.viewer_name, "viewer_name", LIMITE_NOME))
        definir(self, "kind", EventKind.de_valor(self.kind))
        definir(self, "text", _texto(self.text, "text", LIMITE_TEXTO))
        definir(self, "gift_id", _texto(self.gift_id, "gift_id", 100))
        definir(self, "raw_amount", _numero(self.raw_amount, "raw_amount"))
        definir(self, "raw_currency", _texto(self.raw_currency, "raw_currency", 10))
        definir(self, "timestamp", _numero(self.timestamp, "timestamp"))
        definir(self, "value_units", _inteiro(self.value_units, "value_units"))
        definir(self, "sequence", _inteiro(self.sequence, "sequence"))
        definir(self, "is_moderator", bool(self.is_moderator))
        definir(self, "is_owner", bool(self.is_owner))
        # Uma fonte sem id proprio (script de teste, chat sem id estavel) ganha
        # um derivado deterministico: idempotencia nunca pode ficar opcional.
        event_id = _texto(self.event_id, "event_id", 200)
        if not event_id:
            event_id = f"{self.platform}:{self.viewer_id}:{self.sequence}"
        definir(self, "event_id", event_id)
        raw = self.raw if isinstance(self.raw, Mapping) else _MAPA_VAZIO
        definir(self, "raw", MappingProxyType(dict(raw)))

    @property
    def tem_valor(self) -> bool:
        """Eventos com valor normalizado movem comandos pagos."""
        return self.value_units > 0

    @property
    def privilegiado(self) -> bool:
        """Moderador e dono do canal escapam de rate limit, nunca de auditoria."""
        return self.is_moderator or self.is_owner

    @property
    def chave_identidade(self) -> tuple[str, str]:
        """Identidade global: o mesmo id pode existir em duas plataformas."""
        return (self.platform, self.viewer_id)

    def to_dict(self) -> dict[str, Any]:
        """Forma serializavel usada pelas gravacoes de replay."""
        return {
            "platform": self.platform,
            "viewer_id": self.viewer_id,
            "viewer_name": self.viewer_name,
            "kind": self.kind.value,
            "event_id": self.event_id,
            "sequence": self.sequence,
            "text": self.text,
            "value_units": self.value_units,
            "is_moderator": self.is_moderator,
            "is_owner": self.is_owner,
            "gift_id": self.gift_id,
            "raw_amount": self.raw_amount,
            "raw_currency": self.raw_currency,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, dados: Mapping[str, Any]) -> "ViewerEvent":
        if not isinstance(dados, Mapping):
            raise TypeError("evento precisa ser um mapeamento")
        desconhecidas = set(dados) - _CAMPOS_ACEITOS
        if desconhecidas:
            raise ValueError(
                "campos desconhecidos no evento: " + ", ".join(sorted(desconhecidas))
            )
        return cls(
            platform=dados.get("platform", ""),
            viewer_id=dados.get("viewer_id", ""),
            viewer_name=dados.get("viewer_name", ""),
            kind=dados.get("kind", EventKind.CHAT),
            event_id=dados.get("event_id", ""),
            sequence=dados.get("sequence", 0),
            text=dados.get("text", ""),
            value_units=dados.get("value_units", 0),
            is_moderator=dados.get("is_moderator", False),
            is_owner=dados.get("is_owner", False),
            gift_id=dados.get("gift_id", ""),
            raw_amount=dados.get("raw_amount", 0.0),
            raw_currency=dados.get("raw_currency", ""),
            timestamp=dados.get("timestamp", 0.0),
            raw=dados.get("raw") or _MAPA_VAZIO,
        )


_CAMPOS_ACEITOS = frozenset(
    {
        "platform",
        "viewer_id",
        "viewer_name",
        "kind",
        "event_id",
        "sequence",
        "text",
        "value_units",
        "is_moderator",
        "is_owner",
        "gift_id",
        "raw_amount",
        "raw_currency",
        "timestamp",
        "raw",
    }
)


__all__ = ["EventKind", "ViewerEvent", "LIMITE_NOME", "LIMITE_TEXTO"]
