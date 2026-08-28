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

from . import comentario
from .editing_director import EditingDirector
from ..assets.selector import AssetSelector
from ..content.caption_generator import CaptionGenerator, pedido_de
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
        # Orcamento de reacao do VIDEO (segundos), zerado a cada build: e ele
        # que segura o teto de duracao agora que cada clipe toca inteiro.
        self._reacao_restante_s = float(
            (self.config.get("reaction_budget") or {}).get("max_segundos", 14.0))
        # Nome escolhido nos comentarios, quando existe. Lido uma vez: gancho,
        # placa do personagem e CTA precisam falar do MESMO pedido.
        pedido = pedido_de(generation)
        # Atributos escolhidos em vez de sorteados: o gancho precisa saber
        # para nao abrir o video afirmando que a roleta decidiu tudo.
        escolhas = generation.get("escolhas") or None

        def push(event: dict, duration: float) -> None:
            nonlocal cursor
            event["start"] = round(cursor, 3)
            event["duration"] = round(duration, 3)
            events_out.append(event)
            cursor += duration

        push({"type": "hook",
              "caption": self.captions.hook(rng, pedido, escolhas)},
             durations["hook"])
        self._push_comentario(push, out_dir, durations, pedido)

        rolls = generation["rolls"]
        decisions = director.decide_rolls(rng, rolls)

        self._push_rolls(push, rng, rolls, decisions, "character", durations)
        self._push_reveal(push, generation, out_dir, durations,
                          identity_slots.CHARACTER, rng, pedido)

        if beats.get("stinger_between_sections", True):
            push({"type": "stinger", "entity": "weapon",
                  "caption": self.captions.stinger(rng, "weapon")},
                 durations["stinger"])

        self._push_rolls(push, rng, rolls, decisions, "weapon", durations)
        self._push_reveal(push, generation, out_dir, durations,
                          identity_slots.WEAPON, rng, pedido)

        self._push_synergy(push, rng, generation, durations, beats)
        self._push_reveal(push, generation, out_dir, durations,
                          identity_slots.CHARACTER_WEAPON, rng, pedido)

        build = generation["build"]
        push({"type": "final", "build": build,
              "caption": self.captions.for_final(rng, build)},
             durations["final"])
        push({"type": "outro", "caption": self.captions.outro(rng, pedido)},
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
        """REACTION_CLIP: o clipe toca INTEIRO enquanto o video tiver espaco.

        O teto de 2 s cortava 96% da biblioteca (mediana de 6,5 s): a piada
        entrava e era arrancada antes do punchline. O que protege o formato
        agora nao e o corte de cada clipe, e o ORCAMENTO do video inteiro
        (`reaction_budget.max_segundos`): as primeiras reacoes tocam inteiras
        e, quando o orcamento acaba, a proxima simplesmente nao entra. Assim
        o teto de duracao do video continua valendo sem que nenhuma reacao
        vire um flash de 2 s.
        """
        asset = self.selector.select_reaction(
            rng, decision["tier"], decision["sentiment"], decision["intensity"],
            category=decision.get("reaction_category"))
        minimo = float(durations.get("reaction_min", 0.5))
        util = float((self.config.get("reaction_budget") or {})
                     .get("min_util_segundos", 2.5))
        if asset.get("synthetic", True):
            # Cartão desenhado: não é clipe, tem duração própria e curta.
            duracao = durations["reaction"]
        else:
            duracao = asset.get("duration")
            if not duracao:
                from ..assets.importer import _probe_duration
                duracao = _probe_duration(Path(asset["path"])) or durations["reaction"]
            duracao = min(float(duracao) + 0.05, durations.get("reaction_max", 8.0))
            if duracao < util:
                # A biblioteca tem clipes de fração de segundo (import torto,
                # corte errado). Esticar um clipe de 0,1 s até o piso só
                # produz um tranco na tela: melhor não ter reação.
                return
            duracao = max(duracao, minimo)

        restante = getattr(self, "_reacao_restante_s", None)
        if restante is not None:
            if duracao > restante:
                # Sem espaco para a reacao inteira: ela entra pelo que sobrou
                # SE o resto ainda der uma reacao — abaixo disso e flash, e
                # flash e pior que nao ter reacao nenhuma (o espectador ve um
                # tranco sem entender o que passou).
                util = float((self.config.get("reaction_budget") or {})
                             .get("min_util_segundos", 2.5))
                if restante < max(minimo, util):
                    return
                duracao = restante
            self._reacao_restante_s = max(0.0, restante - duracao)

        push({
            "type": "reaction",
            "asset": asset,
            # Reacao e video de OUTRO formato (quase sempre deitado): cabe
            # inteiro na tela, com barras, em vez de ser recortado no meio.
            "fit": "contain",
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
                     durations: dict, slot: str, rng: random.Random,
                     pedido: dict | None = None) -> None:
        """O clipe daquele slot; sem ele, o nameplate no lugar.

        O renderer decide por CAPACIDADE, nao por tipo (`_asset_de_video`):
        basta o evento apontar para um mp4 real com `synthetic: False`.

        `fit: "contain"` porque os clipes sao gerados em 9:16 - no perfil
        `normal` (16:9) o crop-para-preencher comeria as laterais.
        """
        placa = self._nameplate(generation, slot, rng, pedido)
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

        if midia == identity_slots.VIDEO:
            # Decisao do PLANO, nao do renderer: quem sabe que existe trilha
            # de fundo e a edicao.
            evento["sem_som"] = bool(
                (self.config.get("identity_som") or {}).get("payoff_mudo", True))

        if midia == identity_slots.IMAGEM:
            # Imagem nao tem duracao para medir: quem decide e a direcao. E ela
            # NAO fica o teto da janela - parada, ela vira o cartao que a
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

    def _push_comentario(self, push, out_dir: Path | None, durations: dict,
                         pedido: dict | None) -> None:
        """O print do comentario, logo depois do gancho — quando existe.

        E a PROVA do pedido: o gancho acabou de dizer que o nome veio de
        voces, e a tela seguinte mostra o comentario de verdade. Vem cedo de
        proposito; no fim do video ninguem mais precisa ser convencido.

        O arquivo e opcional e vive na propria pasta da geracao
        (`comentario.png|jpg|jpeg|webp`): largar o print ali e re-render com
        `--refazer-edicao` basta para ele entrar, sem regerar nada.

        Sem placa por cima: uma cortina no terco de baixo cobriria justamente
        o texto do comentario, que e a unica coisa que a tela tem para
        mostrar. O credito vai numa etiqueta pequena no topo.
        """
        arquivo = comentario.encontrar(out_dir)
        if arquivo is None:
            return
        direcao = self.config.get("comentario", {})
        autor = str((pedido or {}).get("autor") or "").strip()
        evento = {
            "type": "comentario",
            "asset": {"path": str(arquivo), "synthetic": False,
                      "media": identity_slots.IMAGEM},
            "fit": "contain",
            "badge": (f"PEDIDO DE {autor}" if autor
                      else str(direcao.get("etiqueta", "PEDIDO NOS COMENTARIOS"))),
            "caption": "",
            # Zoom quase parado: texto pequeno com Ken Burns de revelacao
            # fica ilegivel, e aqui a tela existe para ser LIDA.
            "motion": direcao.get("motion", {"zoom": [1.0, 1.03],
                                             "centro": [[0.5, 0.5], [0.5, 0.5]]}),
            "flash_frames": int(
                self.config.get("identity_still", {}).get("flash_frames", 2)),
        }
        push(evento, float(direcao.get("duracao", 3.2)))

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

    def _nameplate(self, generation: dict, slot: str,
                   rng: random.Random, pedido: dict | None = None) -> dict:
        """Duas linhas, curtas: o que identifica, nao o que descreve."""
        personagem = generation["character"]
        arma = generation["weapon"]
        classe = str(personagem.get("classe", "")).split(" (")[0]
        altura = f"{personagem.get('tamanho', 0):.2f}".replace(".", ",")
        if slot == identity_slots.WEAPON:
            # O nome da arma JA carrega estilo e raridade ("Lancas de Mana
            # Comum"), entao repeti-los embaixo e ruido: a segunda linha custa
            # o mesmo tempo de tela e nao acrescenta nada. Quem entra sao o
            # encantamento e a habilidade - o que a arma FAZ, que nao esta no
            # nome e e o que o espectador ainda nao sabe.
            encantamentos = arma.get("encantamentos") or []
            encantamento = (arma.get("afinidade_elemento")
                            or (encantamentos[0] if encantamentos else ""))
            detalhes = [str(d) for d in (encantamento, arma.get("habilidade"))
                        if d]
            return {"titulo": str(arma.get("nome", "")).upper(),
                    "subtitulo": " - ".join(detalhes)
                                 or str(arma.get("raridade", ""))}
        if slot == identity_slots.CHARACTER_WEAPON:
            return {"titulo": str(personagem.get("nome", "")).upper(),
                    "subtitulo": f"+ {arma.get('nome', '')}"}
        if (pedido or {}).get("nome"):
            # O titulo JA e o nome que veio do comentario, entao classe e
            # altura embaixo dele nao dizem de onde ele veio - e essa e a
            # unica linha que aparece por cima do clipe do personagem. O
            # credito rende mais comentario do que o dado da ficha, que as
            # roletas de classe e tamanho ja mostraram.
            credito = self.captions.nameplate_pedido(rng)
            if credito:
                return {"titulo": str(personagem.get("nome", "")).upper(),
                        "subtitulo": credito}
        return {"titulo": str(personagem.get("nome", "")).upper(),
                "subtitulo": f"{classe} - {altura} m"}
