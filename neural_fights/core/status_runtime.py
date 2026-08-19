"""Contrato canônico dos efeitos executados pelo runtime de combate.

Este é o catálogo único de status do projeto: IDs, aliases e números que o
runtime de combate realmente consome. O estado por luta vive em ``Lutador``.
"""

from __future__ import annotations

import math


STATUS_ALIASES = {
    "VENENO": "ENVENENADO",
    "SANGRAMENTO": "SANGRANDO",
    "QUEIMAR": "QUEIMANDO",
    "CONGELAR": "CONGELADO",
    "ATORDOAR": "ATORDOADO",
}


# ``dano_base`` é o valor entregue a DotEffect antes do redutor histórico de
# 50%. Mantê-lo aqui preserva exatamente o balanceamento já usado no runtime.
STATUS_RUNTIME = {
    "ENVENENADO": {
        "categoria": "dot",
        "duracao": 4.0,
        "dano_base": 1.5,
        "mod_cura_recebida": 0.5,
    },
    "SANGRANDO": {"categoria": "dot", "duracao": 3.0, "dano_base": 2.0},
    "QUEIMANDO": {"categoria": "dot", "duracao": 2.5, "dano_base": 2.5},
    "CORROENDO": {
        "categoria": "dot",
        "duracao": 4.0,
        "dano_base": 1.5,
        "mod_dano_recebido": 1.2,
    },
    "NECROSE": {
        "categoria": "dot",
        "duracao": 5.0,
        "dano_base": 3.0,
        "mod_cura_recebida": 0.0,
    },
    "MALDITO": {
        "categoria": "dot",
        "duracao": 6.0,
        "dano_base": 1.0,
        "mod_dano_recebido": 1.3,
        "mod_cura_recebida": 0.5,
    },
    "CONGELADO": {"categoria": "cc", "duracao": 2.0},
    "LENTO": {"categoria": "cc", "duracao": 2.0, "mod_velocidade": 0.5},
    "ATORDOADO": {"categoria": "cc", "duracao": 0.8},
    "PARALISIA": {"categoria": "cc", "duracao": 0.5},
    "ENRAIZADO": {"categoria": "cc", "duracao": 2.5},
    "SILENCIADO": {"categoria": "cc", "duracao": 3.0},
    "CEGO": {
        "categoria": "debuff",
        "duracao": 2.0,
        "desvio_mira_graus": 35.0,
    },
    "MEDO": {"categoria": "cc", "duracao": 2.5},
    "CHARME": {"categoria": "controle_mental", "duracao": 2.0},
    "SONO": {"categoria": "cc", "duracao": 4.0},
    "KNOCK_UP": {"categoria": "cc", "duracao": 0.5},
    "TEMPO_PARADO": {"categoria": "cc", "duracao": 2.0},
    "FRACO": {
        "categoria": "debuff",
        "duracao": 4.0,
        "mod_dano_causado": 0.7,
    },
    "VULNERAVEL": {
        "categoria": "debuff",
        "duracao": 4.0,
        "mod_dano_recebido": 1.5,
    },
    "EXAUSTO": {
        "categoria": "debuff",
        "duracao": 5.0,
        "mod_regen_mana": 0.3,
    },
    "MARCADO": {
        "categoria": "debuff",
        "duracao": 6.0,
        "mod_proximo_dano_recebido": 1.5,
    },
    "EXPOSTO": {
        "categoria": "debuff",
        "duracao": 4.0,
        "mod_dano_recebido": 2.0,
    },
    "BOMBA_RELOGIO": {
        "categoria": "especial",
        "duracao": 3.0,
        "raio_explosao": 2.5,
    },
    "LINK_ALMA": {
        "categoria": "especial",
        "duracao": 6.0,
        "percentual_compartilhado": 0.5,
    },
    "POSSESSO": {"categoria": "controle_mental", "duracao": 3.0},
    "TROCAR_POS": {"categoria": "transporte"},
    # O deslocamento real destes efeitos é processado fora do status. As flags
    # legadas ainda são aceitas, mas não são a fonte da força física.
    "PUXADO": {"categoria": "transporte"},
    "VORTEX": {"categoria": "transporte"},
}


BUFF_EFFECT_RUNTIME = {
    "ABENÇOADO": {
        "mod_cura_recebida": 1.5,
        "cura_por_segundo": 3.0,
    },
    "ACELERADO": {"buff_velocidade": 1.5},
    "DETERMINADO": {"mod_cooldown": 0.5},
    "FURIA": {
        "buff_dano": 1.8,
        "buff_velocidade": 1.2,
        "mod_dano_recebido": 1.3,
    },
    "IMORTAL": {"imortal": True},
    "REGENERANDO": {"cura_por_segundo": 8.0},
}


EFEITOS_TRATADOS_FORA_DO_STATUS = {
    "NORMAL",
    "PERFURAR",
    "DRENAR",
    "EMPURRAO",
    "EXPLOSAO",
}


DEBUFF_FAMILY_ORDER = (
    "NECROSE",
    "TEMPO_PARADO",
    "CONGELADO",
    "SONO",
    "ATORDOADO",
    "ENRAIZADO",
    "SILENCIADO",
    "EXPOSTO",
    "VULNERAVEL",
    "MALDITO",
    "CORROENDO",
    "ENVENENADO",
    "SANGRANDO",
    "QUEIMANDO",
    "FRACO",
    "EXAUSTO",
    "LENTO",
    "CEGO",
    "MEDO",
    "CHARME",
    "MARCADO",
    "POSSESSO",
    "LINK_ALMA",
    "BOMBA_RELOGIO",
)


# Timers de status mantidos por lutador. A chave e o atributo historico que
# ``Lutador`` continua expondo; o valor e o ID canonico deste modulo. Timers de
# mecanica (dash, flash, invencibilidade, provocacao, bloqueio de cura) ficam
# fora do container por nao serem status do catalogo.
STATUS_TIMER_ATTRS = {
    "stun_timer": "ATORDOADO",
    "slow_timer": "LENTO",
    "enraizado_timer": "ENRAIZADO",
    "congelado_timer": "CONGELADO",
    "tempo_parado_timer": "TEMPO_PARADO",
    "silenciado_timer": "SILENCIADO",
    "exausto_timer": "EXAUSTO",
    "cego_timer": "CEGO",
    "medo_timer": "MEDO",
    "sono_timer": "SONO",
    "marcado_timer": "MARCADO",
    "fraco_timer": "FRACO",
    "vulneravel_timer": "VULNERAVEL",
    "maldito_timer": "MALDITO",
    "corroendo_timer": "CORROENDO",
    "exposto_timer": "EXPOSTO",
    "charme_timer": "CHARME",
    "possesso_timer": "POSSESSO",
    "bomba_relogio_timer": "BOMBA_RELOGIO",
    "link_alma_timer": "LINK_ALMA",
}


STATUS_TIMER_BY_ID = {status: attr for attr, status in STATUS_TIMER_ATTRS.items()}


class StatusTimers:
    """Tempo restante de cada status ativo, indexado pelo ID canonico.

    Substitui os campos ``*_timer`` soltos do ``Lutador``: um status ausente do
    mapa simplesmente nao esta ativo, entao nao existe estado espelhado para
    sincronizar a mao.
    """

    __slots__ = ("_restante",)

    def __init__(self) -> None:
        self._restante: dict[str, float] = {}

    def get(self, status_id: str) -> float:
        return self._restante.get(status_id, 0.0)

    def set(self, status_id: str, valor: object) -> float:
        """Grava o tempo restante; valores nao positivos removem o status."""
        try:
            restante = float(valor)
        except (TypeError, ValueError):
            restante = 0.0
        if not math.isfinite(restante) or restante <= 0.0:
            self._restante.pop(status_id, None)
            return 0.0
        self._restante[status_id] = restante
        return restante

    def estender(self, status_id: str, duracao: object) -> float:
        """Renova o status mantendo a maior duracao, como o runtime ja fazia."""
        try:
            nova = float(duracao)
        except (TypeError, ValueError):
            return self.get(status_id)
        return self.set(status_id, max(self.get(status_id), nova))

    def ativo(self, status_id: str) -> bool:
        return self._restante.get(status_id, 0.0) > 0.0

    def ativos(self) -> frozenset:
        return frozenset(self._restante)

    def limpar(self, *status_ids: str) -> None:
        if not status_ids:
            self._restante.clear()
            return
        for status_id in status_ids:
            self._restante.pop(status_id, None)

    def tick(self, dt: float, *, exceto=()) -> tuple:
        """Desconta ``dt`` e devolve os IDs que expiraram neste passo."""
        if dt <= 0.0 or not self._restante:
            return ()
        ignorados = frozenset(exceto)
        expirados = []
        for status_id in tuple(self._restante):
            if status_id in ignorados:
                continue
            restante = self._restante[status_id] - dt
            if restante > 0.0:
                self._restante[status_id] = restante
            else:
                del self._restante[status_id]
                expirados.append(status_id)
        return tuple(expirados)

    def modificador(self, campo: str, *, combinar=max, padrao: float = 1.0) -> float:
        """Agrega ``campo`` de ``STATUS_RUNTIME`` sobre os status ativos.

        Debuffs da mesma familia nao se multiplicam: ``combinar`` escolhe um
        unico valor entre os ativos, preservando a regra historica.
        """
        valores = [padrao]
        for status_id in self._restante:
            definicao = STATUS_RUNTIME.get(status_id)
            if definicao is not None and campo in definicao:
                valores.append(float(definicao[campo]))
        return combinar(valores)


def normalizar_efeito(efeito: object) -> str:
    """Converte aliases de transporte/catálogo no ID usado pelo runtime."""
    nome = str(efeito or "NORMAL").upper()
    return STATUS_ALIASES.get(nome, nome)


def get_status_runtime(efeito: object) -> dict:
    """Retorna a definição compartilhada, sem expor o dicionário mutável."""
    return STATUS_RUNTIME.get(normalizar_efeito(efeito), {}).copy()


def get_duracao_padrao(efeito: object, fallback: float) -> float:
    return float(get_status_runtime(efeito).get("duracao", fallback))


def efeito_bloqueado_por_imunidade(efeito: object) -> bool:
    """Dano/transporte físico continuam válidos durante imunidade a debuffs."""
    nome = normalizar_efeito(efeito)
    if nome in EFEITOS_TRATADOS_FORA_DO_STATUS:
        return False
    definicao = STATUS_RUNTIME.get(nome)
    return bool(definicao and definicao.get("categoria") != "transporte")


__all__ = [
    "BUFF_EFFECT_RUNTIME",
    "DEBUFF_FAMILY_ORDER",
    "EFEITOS_TRATADOS_FORA_DO_STATUS",
    "STATUS_ALIASES",
    "STATUS_RUNTIME",
    "STATUS_TIMER_ATTRS",
    "STATUS_TIMER_BY_ID",
    "StatusTimers",
    "efeito_bloqueado_por_imunidade",
    "get_duracao_padrao",
    "get_status_runtime",
    "normalizar_efeito",
]
