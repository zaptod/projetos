"""TimelineBuilder: generation.json + decisoes de edicao -> edit_plan.json.

O plano e uma lista plana de eventos com tempo (secao 47). O renderer so le o
plano - ele nunca redecide nada.

A ESTRUTURA (secao 8) e:

    gancho curto
    roletas do personagem      (com reacao onde vale a pena)
    CHARACTER_VIDEO            primeira recompensa
    "agora a arma"             batida curta de virada
    roletas da arma
    WEAPON_VIDEO               segunda recompensa
    [sinergia, so se extrema]
    CHARACTER_WEAPON_VIDEO     payoff final
    nota final curta
    outro

O que saiu: a ficha de personagem, a ficha da arma, a tela longa de
compatibilidade e a tela de estatisticas do fim (secoes 2 e 15). No lugar delas
entram os tres clipes. Enquanto um clipe nao existe, o lugar dele e ocupado por
um `nameplate`: nome grande e uma linha de dado, sem avatar e sem cartao
(secao 3) - o video da roleta nunca espera o Digen.
"""
from __future__ import annotations

import random
from pathlib import Path

from .editing_director import EditingDirector
from ..assets.selector import AssetSelector
from ..content.caption_generator import CaptionGenerator
from ..identity import artefato as identity_artefato
from ..identity import slots as identity_slots


class TimelineBuilder:
    def __init__(self, editing_config: dict, captions: CaptionGenerator,
                 selector: AssetSelector):
        self.config = editing_config
        self.captions = captions
        self.selector = selector

    def build(self, rng: random.Random, generation: dict,
              out_dir: Path | None = None) -> dict:
        director = EditingDirector(self.config)
        durations = self.config["durations"]
        beats = self.config.get("beats", {})
        events_out: list[dict] = []
        cursor = 0.0

        def push(event: dict, duration: float) -> None:
            nonlocal cursor
            event["start"] = round(cursor, 3)
            event["duration"] = round(duration, 3)
            events_out.append(event)
            cursor += duration

        push({"type": "hook", "caption": self.captions.hook(rng)},
             durations["hook"])

        rolls = generation["rolls"]
        decisions = director.decide_rolls(rng, rolls)

        self._push_rolls(push, rng, rolls, decisions, "character", durations)
        self._push_reveal(push, generation, out_dir, durations,
                          identity_slots.CHARACTER)

        if beats.get("stinger_between_sections", True):
            push({"type": "stinger", "entity": "weapon",
                  "caption": self.captions.stinger(rng, "weapon")},
                 durations["stinger"])

        self._push_rolls(push, rng, rolls, decisions, "weapon", durations)
        self._push_reveal(push, generation, out_dir, durations,
                          identity_slots.WEAPON)

        self._push_synergy(push, rng, generation, durations, beats)
        self._push_reveal(push, generation, out_dir, durations,
                          identity_slots.CHARACTER_WEAPON)

        build = generation["build"]
        push({"type": "final", "build": build,
              "caption": self.captions.for_final(rng, build)},
             durations["final"])
        push({"type": "outro", "caption": self.captions.outro(rng)},
             durations["outro"])

        return {
            "generation_id": generation["generation_id"],
            "seed": generation["seed"],
            "total_duration": round(cursor, 3),
            "events": events_out,
        }

    # ---------------------------------------------------------------- roletas
    def _push_rolls(self, push, rng: random.Random, rolls: list[dict],
                    decisions: list[dict], entity: str, durations: dict) -> None:
        for indice, roll in enumerate(rolls):
            if roll["entity"] != entity:
                continue
            decision = decisions[indice]
            chave = ("roulette_result_extreme" if decision["extreme"]
                     else "roulette_result")
            push({
                "type": "roulette",
                "roll": roll,
                "spin_duration": durations["roulette_spin"],
                "effects": decision["effects"],
                "classification": decision["classification"],
                "caption": self.captions.for_event(rng, roll),
            }, durations["roulette_spin"] + durations[chave])
            if decision["reaction"]:
                self._push_reaction(push, rng, decision, durations)

    def _push_reaction(self, push, rng: random.Random, decision: dict,
                       durations: dict) -> None:
        """REACTION_CLIP: 0,5 a 2 s (secao 10).

        O clipe real tocava INTEIRO, e um meme de 6 s parava o video no meio de
        uma sequencia de roletas de 2 s. Agora ele e cortado no teto: a reacao
        interrompe, nao assume.
        """
        asset = self.selector.select_reaction(
            rng, decision["tier"], decision["sentiment"], decision["intensity"],
            category=decision.get("reaction_category"))
        if asset.get("synthetic", True):
            duracao = durations["reaction"]
        else:
            duracao = asset.get("duration")
            if not duracao:
                from ..assets.importer import _probe_duration
                duracao = _probe_duration(Path(asset["path"])) or durations["reaction"]
            duracao = min(float(duracao) + 0.05, durations.get("reaction_max", 2.0))
            duracao = max(duracao, durations.get("reaction_min", 0.5))
        push({
            "type": "reaction",
            "asset": asset,
            "category": asset.get("category"),
            "classification": decision["classification"],
            "reason": decision.get("reason"),
            "sentiment": decision["sentiment"],
            "intensity": decision["intensity"],
        }, duracao)

    # --------------------------------------------------------------- sinergia
    def _push_synergy(self, push, rng: random.Random, generation: dict,
                      durations: dict, beats: dict) -> None:
        """Compatibilidade so quando ela e noticia.

        No formato antigo esta tela aparecia sempre, com barra e lista de
        sinergias, e custava 3,4 s parados em cima de um numero que na maior
        parte das builds e 50 e pouco. Agora ela so entra quando o numero
        surpreende - nos dois sentidos.
        """
        compat = generation["compatibility"]
        score = compat["compatibility_score"]
        if beats.get("synergy_only_when_extreme", True):
            if beats.get("synergy_low", 28) < score < beats.get("synergy_high", 78):
                return
        push({"type": "synergy", "compatibility": compat,
              "caption": self.captions.for_synergy(rng, compat)},
             durations["synergy"])

    # ------------------------------------------------------------- recompensa
    def _push_reveal(self, push, generation: dict, out_dir: Path | None,
                     durations: dict, slot: str) -> None:
        """O clipe daquele slot; sem ele, o nameplate no lugar.

        O renderer decide por CAPACIDADE, nao por tipo (`_asset_de_video`):
        basta o evento apontar para um mp4 real com `synthetic: False`.

        `fit: "contain"` porque os clipes sao gerados em 9:16 - no perfil
        `normal` (16:9) o crop-para-preencher comeria as laterais.
        """
        placa = self._nameplate(generation, slot)
        achado = self._artefato(out_dir, slot)
        if achado is None:
            push({"type": "nameplate", "slot": slot, "nameplate": placa,
                  "caption": placa["titulo"]}, durations["nameplate"])
            return
        arquivo, midia = achado

        janela = (self.config.get("identity_slots", {}).get(slot)
                  or {"min": 2.0, "max": 6.0})
        evento = {
            "type": "identity",
            "slot": slot,
            "asset": {"path": str(arquivo), "synthetic": False, "media": midia},
            "fit": "contain",
            # Nome e classe sobre a revelacao, discretos (secao 15) - nunca uma
            # ficha por cima do personagem.
            "nameplate": placa,
            "caption": "",
        }

        if midia == identity_slots.IMAGEM:
            # Imagem nao tem duracao para medir: quem decide e a direcao. E ela
            # NAO fica o teto da janela — parada, ela vira o cartao que a
            # secao 15 mandou tirar do video.
            duracao = float(janela.get("still", janela["min"]))
            direcao = self.config.get("identity_still", {})
            evento["motion"] = direcao.get("motion", {}).get(slot)
            evento["flash_frames"] = int(direcao.get("flash_frames", 2))
        else:
            from ..assets.importer import _probe_duration
            duracao = _probe_duration(arquivo) or float(janela["max"])
            duracao = min(duracao + 0.05, float(janela["max"]))
        push(evento, duracao)

    @staticmethod
    def _artefato(out_dir: Path | None, slot: str) -> tuple[Path, str] | None:
        """(arquivo, midia) do slot, ou None se ainda nao existe.

        A midia sai da EXTENSAO do arquivo achado, nunca do slot: uma geracao
        feita antes desta mudanca tem mp4 no slot de personagem e continua
        entrando no video como video.
        """
        if out_dir is None:
            return None
        for nome in identity_slots.nomes_aceitos(slot):
            caminho = Path(out_dir) / nome
            if caminho.is_file():
                midia = identity_artefato.midia_do_arquivo(caminho)
                if midia:
                    return caminho, midia
        return None

    @staticmethod
    def _nameplate(generation: dict, slot: str) -> dict:
        """Duas linhas, curtas: o que identifica, nao o que descreve."""
        personagem = generation["character"]
        arma = generation["weapon"]
        classe = str(personagem.get("classe", "")).split(" (")[0]
        altura = f"{personagem.get('tamanho', 0):.2f}".replace(".", ",")
        if slot == identity_slots.WEAPON:
            return {"titulo": str(arma.get("nome", "")).upper(),
                    "subtitulo": f"{arma.get('raridade', '')} - "
                                 f"{arma.get('estilo') or arma.get('tipo', '')}"}
        if slot == identity_slots.CHARACTER_WEAPON:
            return {"titulo": str(personagem.get("nome", "")).upper(),
                    "subtitulo": f"+ {arma.get('nome', '')}"}
        return {"titulo": str(personagem.get("nome", "")).upper(),
                "subtitulo": f"{classe} - {altura} m"}
