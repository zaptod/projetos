"""Torneio -> edit_plan.json, no MESMO formato dos videos de build.

A edicao reage ao drama da luta exatamente como reage a uma rolagem: tier
define probabilidade de reacao, o banco de clipes entra por categoria e as
legendas saem do banco shitposter.
"""
from __future__ import annotations

import random
from pathlib import Path

from ..editing.editing_director import EditingDirector
from ..assets.selector import AssetSelector
from ..content.caption_generator import CaptionGenerator


class TournamentTimelineBuilder:
    def __init__(self, editing_config: dict, captions: CaptionGenerator,
                 selector: AssetSelector):
        self.config = editing_config
        self.captions = captions
        self.selector = selector

    def build(self, rng: random.Random, torneio: dict) -> dict:
        durations = self.config["durations"]
        eventos: list[dict] = []
        cursor = 0.0

        def push(evento: dict, duracao: float) -> None:
            nonlocal cursor
            evento["start"] = round(cursor, 3)
            evento["duration"] = round(duracao, 3)
            eventos.append(evento)
            cursor += duracao

        push({"type": "hook",
              "caption": self.captions.torneio_hook(rng, len(torneio["participantes"]))},
             durations["hook"])
        push({"type": "participantes",
              "participantes": torneio["participantes"],
              "caption": "OS PARTICIPANTES"},
             durations.get("participantes", 3.4))

        # a edicao decide as reacoes olhando o drama de TODAS as lutas juntas.
        # Tabela propria: o leque de tiers de luta e diferente do das rolagens.
        config_torneio = dict(self.config)
        tabela = self.config.get("reaction_chance_by_tier_tournament")
        if tabela:
            config_torneio["reaction_chance_by_tier"] = tabela
        # As roletas apertaram o teto para 1 (secao 10: reacao tem que parecer
        # espontanea). O torneio tem menos eventos e cada luta e um bloco
        # maior, entao ele mantem o teto de 2 que sempre teve.
        config_torneio["max_consecutive_reactions"] = self.config.get(
            "max_consecutive_reactions_tournament", 2)
        director = EditingDirector(config_torneio)
        normalizados = [{
            "tier": luta["tier"], "sentiment": luta["sentiment"],
            "intensity": luta["intensity"], "surprise": luta["surpresa"],
            # escala centrada em 50 (como as rolagens), senao lutas boas
            # cairiam abaixo da media e PERDERIAM chance de reacao
            "interest": max(0, min(100, round(50 + (luta["score"] - 50) * 0.9
                                              + luta["surpresa"] * 0.25))),
        } for luta in torneio["lutas"]]
        decisoes = director.decide(rng, normalizados)

        rodada_atual = None
        for indice, luta in enumerate(torneio["lutas"]):
            if luta["rodada_nome"] != rodada_atual:
                rodada_atual = luta["rodada_nome"]
                push({"type": "round_title", "titulo": rodada_atual,
                      "caption": rodada_atual},
                     durations.get("round_title", 2.0))

            clipes = luta.get("clipes") or {}
            # Com a luta gravada, o card e o resultado encurtam: quem manda no
            # tempo de tela passa a ser a luta, nao os cartoes sobre ela.
            push({"type": "fight_card", "luta": luta,
                  "caption": self.captions.torneio_card(rng, luta)},
                 durations.get("fight_card_com_clipe" if clipes else "fight_card", 3.0))

            if clipes:
                # Um evento so, com um arquivo por perfil: o renderer escolhe.
                # `fit: contain` porque o gameplay e gravado no formato certo de
                # cada perfil e nao deve ser recortado.
                duracao = max(c["duracao"] for c in clipes.values())
                asset = {"id": f"gameplay_{luta['match_id']:02d}",
                         "synthetic": False}
                for perfil, clipe in clipes.items():
                    asset[f"path_{perfil}"] = clipe["path"]
                asset.setdefault("path", next(iter(clipes.values()))["path"])
                evento = {"type": "gameplay", "asset": asset, "fit": "contain",
                          "luta": luta, "match_id": luta["match_id"],
                          "caption": ""}
                # O recorte e por formato (as resolucoes diferem), entao o
                # renderer le o do perfil dele.
                for perfil, clipe in clipes.items():
                    if clipe.get("crop"):
                        evento[f"crop_{perfil}"] = clipe["crop"]
                push(evento, duracao)

            push({"type": "fight_result", "luta": luta,
                  "caption": self.captions.torneio_resultado(rng, luta)},
                 durations.get("fight_result_com_clipe" if clipes else "fight_result", 3.4))

            decisao = decisoes[indice]
            if decisao["reaction"]:
                asset = self.selector.select_reaction(
                    rng, decisao["tier"], decisao["sentiment"], decisao["intensity"])
                if asset.get("synthetic", True):
                    duracao = durations["reaction"]
                else:
                    duracao = asset.get("duration")
                    if not duracao:
                        from ..assets.importer import _probe_duration
                        duracao = _probe_duration(Path(asset["path"])) or durations["reaction"]
                    duracao += 0.05
                push({"type": "reaction", "asset": asset,
                      "category": asset.get("category"),
                      "sentiment": decisao["sentiment"],
                      "intensity": decisao["intensity"]}, duracao)

        push({"type": "champion", "torneio": torneio,
              "caption": self.captions.torneio_campeao(rng, torneio)},
             durations.get("champion", 4.2))
        push({"type": "tournament_stats", "estatisticas": torneio["estatisticas"],
              "caption": "RESUMO DO TORNEIO"},
             durations.get("tournament_stats", 3.6))
        push({"type": "outro", "caption": self.captions.outro(rng)},
             durations["outro"])

        return {
            "generation_id": torneio.get("tournament_id", "tournament"),
            "seed": torneio["seed"],
            "kind": "tournament",
            "total_duration": round(cursor, 3),
            "events": eventos,
        }
