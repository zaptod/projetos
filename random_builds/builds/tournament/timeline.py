"""Torneio e luta unica -> edit_plan.json, no MESMO formato dos videos de build.

A edicao reage ao drama da luta exatamente como reage a uma rolagem: tier
define probabilidade de reacao, o banco de clipes entra por categoria e as
legendas saem do banco shitposter.

Onda 9: a luta e o elemento dominante. O evento `gameplay` carrega o que o
renderer precisa para desenhar POR CIMA do jogo, no relogio do clipe:

    hud       serie de HP (t, hp1, hp2) + nomes/cores dos dois lados;
    callouts  legendas sincronizadas com os eventos narrativos do motor
              (PARRY!, COMBO x4, VIROU!, K.O.), com orcamento por 10 s.
"""
from __future__ import annotations

import random
from pathlib import Path

from ..editing.editing_director import EditingDirector
from ..assets.selector import AssetSelector
from ..content.caption_generator import CaptionGenerator


# ----------------------------------------------------------------- callouts
def planejar_callouts(rng: random.Random, luta: dict, duracao: float,
                      cfg: dict | None, captions: CaptionGenerator) -> list[dict]:
    """Quais momentos da luta viram texto grande, e quando.

    Regras (config/editing.json -> fight_callouts):
    - so tipos com prioridade declarada; combo so a partir de `combo_minimo`
      e um combo que cresce (x3, x4, x5) vira UM callout com o maior N;
    - `gap_min` entre dois callouts e no maximo `por_10s` por janela de 10 s;
      quando disputam, a prioridade decide (KO > virada > combo > parry ...).
    """
    eventos = luta.get("eventos_narrativos") or []
    if not eventos or not cfg:
        return []
    prioridade = cfg.get("prioridade") or {}
    textos = cfg.get("textos") or {}
    cores = cfg.get("cores") or {}
    gap = float(cfg.get("gap_min", 1.2))
    por_10s = int(cfg.get("por_10s", 3))
    dur = float(cfg.get("duracao", 0.9))
    combo_min = int(cfg.get("combo_minimo", 3))
    # Onda 10C: troca de plano e callout de fundo — no maximo um a cada
    # `gap_min_por_lutador` s por lutador, e cede a qualquer evento maior
    # que aconteca a menos de `cede_se_maior_em` s.
    plano_cfg = cfg.get("plano") or {}
    plano_gap = float(plano_cfg.get("gap_min_por_lutador", 4.0))
    plano_cede = float(plano_cfg.get("cede_se_maior_em", 1.5))

    candidatos: list[dict] = []
    ultimo_combo: dict[str, dict] = {}
    ultimo_plano: dict[str, float] = {}
    for e in sorted(eventos, key=lambda x: float(x.get("t", 0.0))):
        tipo = str(e.get("tipo", ""))
        t = float(e.get("t", 0.0))
        if tipo not in prioridade or t < 0.0 or t > duracao - 0.3:
            continue
        slot = e.get("slot")
        if tipo == "combo":
            n = int(e.get("n") or 0)
            if n < combo_min:
                continue
            anterior = ultimo_combo.get(str(slot))
            if anterior is not None and t - anterior["t"] < 1.5:
                anterior["t"], anterior["n"] = t, max(n, anterior["n"])
                continue
            cand = {"t": t, "tipo": tipo, "slot": slot, "n": n,
                    "prio": float(prioridade[tipo])}
            ultimo_combo[str(slot)] = cand
            candidatos.append(cand)
            continue
        cand = {"t": t, "tipo": tipo, "slot": slot, "n": None,
                "prio": float(prioridade[tipo])}
        if tipo == "plano":
            anterior = ultimo_plano.get(str(slot))
            if anterior is not None and t - anterior < plano_gap:
                continue
            ultimo_plano[str(slot)] = t
            cand["rotulo"] = str(e.get("rotulo") or "").strip()
            if not cand["rotulo"]:
                continue
        candidatos.append(cand)

    # Plano cede a evento maior proximo (o KO/virada/combo e a noticia).
    candidatos = [
        c for c in candidatos
        if c["tipo"] != "plano" or not any(
            o["prio"] > c["prio"] and abs(o["t"] - c["t"]) < plano_cede
            for o in candidatos if o is not c
        )
    ]

    def _estoura_janela(tempos: list[float]) -> bool:
        """Alguma janela de 10 s tem mais de `por_10s`? Basta olhar as
        janelas que COMECAM em cada callout: toda janela cheia demais tem
        um elemento mais a esquerda, e a janela que comeca nele tambem esta."""
        for inicio in tempos:
            if sum(1 for t in tempos if inicio <= t <= inicio + 10.0) > por_10s:
                return True
        return False

    escolhidos: list[dict] = []
    for cand in sorted(candidatos, key=lambda c: (-c["prio"], c["t"])):
        if any(abs(cand["t"] - x["t"]) < gap for x in escolhidos):
            continue
        if _estoura_janela([x["t"] for x in escolhidos] + [cand["t"]]):
            continue
        escolhidos.append(cand)
    escolhidos.sort(key=lambda c: c["t"])

    return [{
        "t": round(c["t"], 2),
        "duracao": dur,
        "tipo": c["tipo"],
        "slot": c["slot"],
        "n": c["n"],
        "rotulo": c.get("rotulo"),
        "texto": captions.callout(rng, c["tipo"], textos, c["n"],
                                  rotulo=c.get("rotulo")),
        "cor": cores.get(c["tipo"], "#ffffff"),
    } for c in escolhidos]


def evento_gameplay(rng: random.Random, luta: dict, config: dict,
                    captions: CaptionGenerator) -> dict | None:
    """O evento de gameplay com HUD e callouts, ou None sem clipe gravado."""
    clipes = luta.get("clipes") or {}
    if not clipes:
        return None
    # Um evento so, com um arquivo por perfil: o renderer escolhe.
    # `fit: contain` porque o gameplay e gravado no formato certo de cada
    # perfil e nao deve ser recortado.
    duracao = max(float(c["duracao"]) for c in clipes.values())
    asset = {"id": f"gameplay_{int(luta.get('match_id', 0)):02d}", "synthetic": False}
    for perfil, clipe in clipes.items():
        asset[f"path_{perfil}"] = clipe["path"]
    asset.setdefault("path", next(iter(clipes.values()))["path"])
    evento = {"type": "gameplay", "asset": asset, "fit": "contain",
              "luta": luta, "match_id": luta.get("match_id", 0), "caption": ""}
    # Recorte por formato (formato antigo, camera ARENA): o renderer le o do
    # perfil dele. Com a camera DIRETOR o recorte vem None e nada e aparado.
    for perfil, clipe in clipes.items():
        if clipe.get("crop"):
            evento[f"crop_{perfil}"] = clipe["crop"]
    hud_cfg = config.get("fight_hud") or {}
    if luta.get("serie_hp") and hud_cfg.get("barras", True):
        evento["hud"] = {
            "p1": luta["p1"], "p2": luta["p2"],
            "nomes": bool(hud_cfg.get("nomes", True)),
            "serie_hp": luta["serie_hp"],
        }
        # Onda 10C: o plano de cada lutador, vivo, sob a barra de vida.
        if luta.get("serie_plano") and hud_cfg.get("plano", True):
            evento["hud"]["serie_plano"] = luta["serie_plano"]
    callouts = planejar_callouts(rng, luta, duracao,
                                 config.get("fight_callouts"), captions)
    if callouts:
        evento["callouts"] = callouts
    return evento


def eventos_skill_card(nome_lutador: str, ficha: dict | None,
                       durations: dict) -> list[dict]:
    """Onda 11D: cards do kit para o showcase da ESTREIA.

    Cada card leva `skill` (nome/papel/descricao/cor da ficha) e `nameplate`
    (a placa que o renderer desenha sobre o clipe). Quando a demo da skill
    existe na biblioteca (`outputs/skill_demos/manifest.json`), o card vira
    clipe de vídeo real; sem demo, o renderer cai na placa sintética.
    """
    kit = list((ficha or {}).get("kit") or [])[:4]
    if not kit:
        return []
    try:
        from neural_fights.recording.skill_demo import caminho_da_demo
    except Exception:
        caminho_da_demo = None
    dur = float(durations.get("skill_card", 2.4))
    saida: list[dict] = []
    for skill in kit:
        evento = {
            "type": "skill_card",
            "skill": dict(skill),
            "lutador": nome_lutador,
            "nameplate": {
                "titulo": skill.get("nome", ""),
                "subtitulo": skill.get("descricao", ""),
            },
            "_duracao": dur,
        }
        caminho = (
            caminho_da_demo(skill.get("nome", ""))
            if caminho_da_demo is not None
            else None
        )
        if caminho is not None:
            # `synthetic: False` NAO e decoracao: `renderer._asset_de_video`
            # assume sintetico quando a chave falta, entao sem ela a demo
            # gravada era ignorada em silencio e o card virava texto. Foram
            # 9,6 s de cartao mudo nos primeiros 15 s de toda estreia, com
            # as 116 demos paradas no disco.
            evento["asset"] = {"path": str(caminho), "synthetic": False,
                               "media": "video"}
            evento["fit"] = "contain"
            evento["sem_som"] = True
        saida.append(evento)
    return saida


def _duracao_reacao(asset: dict, durations: dict, teto: float | None = None) -> float:
    """Quanto a reacao fica na tela: o clipe INTEIRO ate o teto.

    O teto padrao e o mesmo do video de build (`reaction_max`). Sem ele, um
    meme de 30 s da biblioteca entrava inteiro no meio do torneio; com o teto
    antigo de 2 s, nenhuma reacao chegava ao punchline.
    """
    if asset.get("synthetic", True):
        return durations["reaction"]
    duracao = asset.get("duration")
    if not duracao:
        from ..assets.importer import _probe_duration
        duracao = _probe_duration(Path(asset["path"])) or durations["reaction"]
    duracao = float(duracao) + 0.05
    if teto is None:
        teto = durations.get("reaction_max", 8.0)
    if teto:
        duracao = min(duracao, teto)
    return max(duracao, durations.get("reaction_min", 0.5))


def evento_reacao(asset: dict, decisao: dict) -> dict:
    """O evento de reacao, com o enquadramento que ele exige.

    `fit: contain` porque reacao e video de outro formato (quase sempre
    deitado): recortar para preencher 9:16 come ~62% da largura e corta o
    rosto, que e justamente o que a reacao tem para mostrar.
    """
    return {
        "type": "reaction",
        "asset": asset,
        "fit": "contain",
        "category": asset.get("category"),
        "sentiment": decisao["sentiment"],
        "intensity": decisao["intensity"],
    }


# ------------------------------------------------------------------ torneio
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

            gameplay = evento_gameplay(rng, luta, self.config, self.captions)
            # Com a luta gravada, o card e o resultado encurtam: quem manda no
            # tempo de tela passa a ser a luta, nao os cartoes sobre ela.
            push({"type": "fight_card", "luta": luta,
                  "caption": self.captions.torneio_card(rng, luta)},
                 durations.get("fight_card_com_clipe" if gameplay else "fight_card", 3.0))
            if gameplay:
                push(gameplay, max(float(c["duracao"]) for c in luta["clipes"].values()))
            push({"type": "fight_result", "luta": luta,
                  "caption": self.captions.torneio_resultado(rng, luta)},
                 durations.get("fight_result_com_clipe" if gameplay else "fight_result", 3.4))

            decisao = decisoes[indice]
            if decisao["reaction"]:
                asset = self.selector.select_reaction(
                    rng, decisao["tier"], decisao["sentiment"], decisao["intensity"])
                push(evento_reacao(asset, decisao),
                     _duracao_reacao(asset, durations))

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


# --------------------------------------------------------------- luta unica
class FightTimelineBuilder:
    """Um confronto, um video: gancho -> card -> A LUTA -> resultado -> CTA.

    A luta entra quase inteira (corte de tedio feito na gravacao) e e o
    elemento dominante — pelo menos metade do video, como a roleta e no
    video de build. Reacao so no fim, e so quando o tier justifica.

    Numa SERIE (`fight["lutas"]` com mais de um round), o miolo repete por
    round — titulo, gameplay, placar — e o veredito da serie fecha no lugar
    do resultado unico. Card e showcase de kit continuam acontecendo uma vez
    so: quem entra na arena e o mesmo nos tres rounds.
    """

    def __init__(self, editing_config: dict, captions: CaptionGenerator,
                 selector: AssetSelector):
        self.config = editing_config
        self.captions = captions
        self.selector = selector

    def build(self, rng: random.Random, fight: dict) -> dict:
        durations = self.config["durations"]
        rounds = list(fight.get("lutas") or [fight["luta"]])
        luta = rounds[-1]          # a que fechou a serie
        primeira = rounds[0]       # a que abre o confronto (card e kit)
        serie = len(rounds) > 1
        eventos: list[dict] = []
        cursor = 0.0

        def push(evento: dict, duracao: float) -> None:
            nonlocal cursor
            evento["start"] = round(cursor, 3)
            evento["duration"] = round(duracao, 3)
            eventos.append(evento)
            cursor += duracao

        push({"type": "hook", "caption": self.captions.luta_hook(rng, primeira)},
             durations["hook"])
        gameplays = [evento_gameplay(rng, r, self.config, self.captions)
                     for r in rounds]
        tem_clipe = any(gameplays)
        # O topo do card anuncia o formato: "MELHOR DE 3" no lugar do rotulo
        # de rodada, que numa serie so faz sentido round a round.
        card = dict(primeira)
        if serie:
            card["rodada_nome"] = self._rotulo_da_serie(fight, primeira)
        push({"type": "fight_card", "luta": card,
              "caption": self.captions.luta_card(rng, primeira)},
             durations.get("fight_card_luta", 2.2) if tem_clipe
             else durations.get("fight_card", 3.0))

        # Onda 11D: na ESTREIA (e só nela — a roleta tem teto de 95 s), o
        # kit do estreante entra como showcase: um card por skill, com o
        # clipe de demonstração quando gerado e placa sintética quando não.
        estreia_de = fight.get("estreia_de") or primeira.get("estreia_de")
        if (fight.get("origem") or primeira.get("origem")) == "estreia" and estreia_de:
            slot_ficha = (
                "p1_ficha" if primeira.get("p1") == estreia_de else "p2_ficha"
            )
            for skill_card in eventos_skill_card(
                estreia_de, primeira.get(slot_ficha), durations
            ):
                push(skill_card, skill_card.pop("_duracao"))

        # A edicao decide as reacoes olhando o drama de TODOS os rounds
        # juntos — como no torneio, para o teto de reacoes seguidas valer
        # sobre a serie inteira e nao round a round.
        config_luta = dict(self.config)
        tabela = self.config.get("reaction_chance_by_tier_tournament")
        if tabela:
            config_luta["reaction_chance_by_tier"] = tabela
        decisoes = EditingDirector(config_luta).decide(rng, [{
            "tier": r["tier"], "sentiment": r["sentiment"],
            "intensity": r["intensity"], "surprise": r["surpresa"],
            "interest": max(0, min(100, round(50 + (r["score"] - 50) * 0.9
                                              + r["surpresa"] * 0.25))),
        } for r in rounds])

        def reagir(decisao: dict) -> None:
            if not decisao["reaction"]:
                return
            asset = self.selector.select_reaction(
                rng, decisao["tier"], decisao["sentiment"], decisao["intensity"])
            push(evento_reacao(asset, decisao), _duracao_reacao(asset, durations))

        frases_de_round: set[str] = set()
        for indice, (r, gameplay) in enumerate(zip(rounds, gameplays)):
            if serie:
                push({"type": "round_title", "titulo": r["rodada_nome"],
                      "caption": r["rodada_nome"]},
                     durations.get("round_title", 2.0))
            if gameplay:
                push(gameplay,
                     max(float(c["duracao"]) for c in r["clipes"].values()))
            if serie:
                push({"type": "round_result", "luta": r,
                      "placar": r.get("placar") or [0, 0],
                      "caption": self.captions.luta_round(rng, r,
                                                          frases_de_round)},
                     durations.get("round_result", 2.4))
            # A reacao do ULTIMO round espera o veredito da serie: e nele que
            # o video tem o que comemorar.
            if indice < len(rounds) - 1:
                reagir(decisoes[indice])

        resultado = {"type": "fight_result", "luta": luta}
        if serie:
            resultado["placar"] = list(fight.get("placar") or luta.get("placar") or [])
            resultado["melhor_de"] = fight.get("melhor_de", len(rounds))
            resultado["caption"] = self.captions.luta_serie(rng, luta,
                                                            resultado["placar"])
        else:
            resultado["caption"] = self.captions.torneio_resultado(rng, luta)
        push(resultado,
             durations.get("fight_result_luta", 2.8) if tem_clipe
             else durations.get("fight_result", 3.4))
        reagir(decisoes[-1])

        push({"type": "outro", "caption": self.captions.luta_outro(rng, luta)},
             durations["outro"])

        return {
            "generation_id": fight.get("fight_id", "fight"),
            "seed": fight["seed"],
            "kind": "fight",
            "total_duration": round(cursor, 3),
            "events": eventos,
        }

    @staticmethod
    def _rotulo_da_serie(fight: dict, primeira: dict) -> str:
        formato = f"MELHOR DE {fight.get('melhor_de', 3)}"
        if (fight.get("origem") or primeira.get("origem")) == "estreia":
            return f"ESTREIA • {formato}"
        return formato
