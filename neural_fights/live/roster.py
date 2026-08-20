"""Resolucao de lutadores para uma sessao de live.

O motor e name-keyed: ``match_config["p1_nome"]`` e uma string, e por padrao
``carregar_luta_dados`` varre o catalogo JSON inteiro a cada ``recarregar_tudo``.
Medido neste projeto: 21 ms com 64 personagens, o que projeta para mais de 300 ms
-- vinte frames congelados na troca de partida -- com um milhar de lutadores de
espectador. Numa transmissao isso e visivel.

Este modulo e o provedor que o ``Simulador`` aceita por injecao. Ele:

* carrega o catalogo curado **uma vez** e indexa por nome, trocando varredura
  linear por busca em dicionario;
* resolve lutadores de espectador do SQLite, materializando ``Personagem`` sob
  demanda a partir da spec guardada;
* mantem os dois espacos de nome separados -- o prefixo reservado ``@`` decide
  qual lado consultar, sem ambiguidade possivel.
"""

from __future__ import annotations

import logging

from neural_fights.data import database
from neural_fights.live.identity import eh_lutador_de_espectador
from neural_fights.live.registry import LiveRegistry
from neural_fights.models.characters import Personagem

logger = logging.getLogger(__name__)


class LiveRoster:
    """Resolve nomes de lutador para a sessao, com cache.

    Instancias sao criadas uma vez por sessao e reusadas em toda troca de
    partida; e o cache que torna a troca barata.
    """

    def __init__(self, registry: LiveRegistry | None = None) -> None:
        self.registry = registry
        self._armas: dict[str, object] = {}
        self._curados: dict[str, Personagem] = {}
        self._carregar_catalogo()

    def _carregar_catalogo(self) -> None:
        """Le o catalogo curado uma unica vez e o indexa por nome."""
        self._armas = {arma.nome: arma for arma in database.carregar_armas()}
        self._curados = {p.nome: p for p in database.carregar_personagens()}

    def recarregar_catalogo(self) -> None:
        """Reexecuta a leitura; util se a UI editar o catalogo durante a live."""
        self._carregar_catalogo()

    # ---------------------------------------------------------------- consulta

    @property
    def nomes_curados(self) -> tuple[str, ...]:
        return tuple(self._curados)

    def nomes_de_espectadores(self, limite: int | None = None) -> tuple[str, ...]:
        if self.registry is None:
            return ()
        return tuple(
            fighter.catalog_name
            for fighter in self.registry.listar_lutadores_ativos(limite=limite)
        )

    def todos_os_nomes(self, limite_espectadores: int | None = None) -> tuple[str, ...]:
        return self.nomes_curados + self.nomes_de_espectadores(limite_espectadores)

    # --------------------------------------------------------------- resolucao

    def __call__(self, nome: str) -> Personagem:
        """Contrato de ``roster_provider``: nome -> ``Personagem`` com arma."""
        return self.resolver(nome)

    def resolver(self, nome: str) -> Personagem:
        nome = str(nome)
        if eh_lutador_de_espectador(nome):
            personagem = self._resolver_espectador(nome)
        else:
            personagem = self._curados.get(nome)
        if personagem is None:
            raise ValueError(f"Personagem não encontrado na configuração: {nome}")
        self._equipar(personagem)
        return personagem

    def _resolver_espectador(self, catalog_name: str) -> Personagem | None:
        if self.registry is None:
            return None
        fighter = self.registry.obter_lutador_por_catalogo(catalog_name)
        if fighter is None:
            return None
        return self._materializar(fighter.spec)

    def _materializar(self, spec: dict) -> Personagem:
        """Constroi o ``Personagem`` como o catalogo curado faria.

        O peso da arma **precisa** ser passado: ``Personagem.calcular_status``
        deriva velocidade e resistencia dele. Omitir zeraria o peso e daria ao
        lutador de espectador atributos que nenhum lutador curado teria.
        """
        arma = self._armas.get(spec.get("nome_arma", ""))
        return Personagem(
            spec["nome"],
            spec["tamanho"],
            spec["forca"],
            spec["mana"],
            spec.get("nome_arma", ""),
            float(getattr(arma, "peso", 0.0)) if arma is not None else 0.0,
            spec.get("cor_r", 200),
            spec.get("cor_g", 50),
            spec.get("cor_b", 50),
            spec.get("classe", "Guerreiro (Força Bruta)"),
            spec.get("personalidade", "Aleatório"),
        )

    def _equipar(self, personagem: Personagem) -> None:
        """Anexa a arma pelo indice; nome desconhecido vira ``None``, nao erro."""
        nome_arma = getattr(personagem, "nome_arma", "")
        personagem.arma_obj = self._armas.get(nome_arma) if nome_arma else None


def montar_provider(registry: LiveRegistry | None) -> LiveRoster:
    return LiveRoster(registry)


__all__ = ["LiveRoster", "montar_provider"]
