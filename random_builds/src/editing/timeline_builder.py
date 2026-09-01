"""TimelineBuilder: generation.json + decisoes de edicao -> edit_plan.json.

O plano e uma lista plana de eventos com tempo (secao 47). O renderer so le o
plano - ele nunca redecide nada.

A ESTRUTURA (secao 8, revisada em 29/08/2026 para retencao) e:

    gancho COM O PAYOFF        a imagem do personagem pronto por cima do texto
    CLASSE, PERSONALIDADE      roletas cheias, com a tensao durante o giro
    CHARACTER_IMAGE            rosto na tela cedo (~8 s), quando existe
    TAMANHO, FORCA, MANA       roleta-relampago se a rolagem for NORMAL
    "agora a arma"             batida curta de virada
    roletas da arma            cheias onde ha noticia, relampago onde e so numero
    WEAPON_IMAGE               segunda recompensa
    [sinergia, so se extrema]
    CHARACTER_WEAPON_VIDEO     payoff final
    "hora da verdade" + LUTA   o round decisivo da estreia, com HUD e callouts
    nota final curta
    outro                      convida para a estreia completa

O que mudou e por que: o video tinha 73 s de media com 14 roletas identicas
de 3,3 s, o melhor material (as imagens) aparecia aos 62 s e 40 de 64 videos
nao tinham nenhuma reacao real. O tempo de tela agora e proporcional ao PESO
editorial que a secao 11 ja calcula, e o payoff abre o video em vez de
fecha-lo. Enquanto um clipe nao existe, o lugar dele e ocupado por um
`nameplate` (secao 3) - o video da roleta nunca espera o Digen.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from . import comentario
from .editing_director import EditingDirector
from ..assets.selector import AssetSelector
from ..content.caption_generator import CaptionGenerator, pedido_de
from ..identity import artefato as identity_artefato
from ..identity import slots as identity_slots

# Roletas de "abertura" do personagem: as duas que dizem QUEM ele e. Com a
# imagem no disco, a revelacao entra logo depois delas.
ROLETAS_DE_ABERTURA = ("classe", "personalidade")

# Eventos cuja duracao PODE crescer para a fala caber. Clipe de video real
# (reacao, gameplay, payoff em mp4) tem o tamanho do arquivo e fica de fora.
ESTICAVEIS = ("hook", "roulette", "stinger", "synergy", "final", "outro",
              "nameplate", "identity", "comentario")


def ajustar_ao_roteiro(plano: dict, linhas: list[dict], medidas: dict,
                       config: dict | None = None) -> dict:
    """A cena espera a fala: estica cada evento ate a narracao dele caber.

    Antes a cena era cronometrada primeiro e a voz espremida no que sobrava
    — medido em 29/08: ~29 de 33 falas por video nao cabiam nem acelerando
    1,35x, e saiam cortadas no meio da palavra. Aqui a ordem inverte:
    `medidas` traz a duracao real de cada linha (indice -> segundos, na
    velocidade natural) e o evento cresce ate ela terminar com folga.

    Roleta: a pergunta cabe no GIRO (`spin_duration` cresce se precisar) e
    o comentario cabe no RESULTADO. Clipe de video nao estica (o arquivo
    tem o tamanho que tem); a fala dele continua como estava.
    Os `start` sao recomputados em cadeia e as linhas voltam a ser geradas
    pelo chamador a partir do plano ajustado.
    """
    cfg = (config or {}).get("narracao") or {}
    margem = float(cfg.get("margem", 0.3))
    margem_giro = float(cfg.get("margem_giro", 0.15))
    eventos = plano["events"]
    if not eventos or not medidas:
        return plano

    # Linhas por evento: a linha pertence ao evento em cujo intervalo comeca.
    por_evento: dict[int, list[tuple[float, float]]] = {}
    inicios = [float(e["start"]) for e in eventos]
    for indice, linha in enumerate(linhas):
        dur = medidas.get(indice)
        if dur is None:
            continue
        t = float(linha["start"])
        alvo = None
        for i, ini in enumerate(inicios):
            if ini <= t + 1e-6:
                alvo = i
            else:
                break
        if alvo is None:
            continue
        por_evento.setdefault(alvo, []).append((round(t - inicios[alvo], 3), float(dur)))

    cursor = 0.0
    for i, evento in enumerate(eventos):
        duracao = float(evento["duration"])
        falas = por_evento.get(i, [])
        asset = evento.get("asset") or {}
        esticavel = (evento["type"] in ESTICAVEIS
                     and not (evento["type"] == "identity"
                              and asset.get("media", "video") == "video"))
        if falas and esticavel:
            if evento["type"] == "roulette":
                spin = float(evento.get("spin_duration") or 0.0)
                resultado = duracao - spin
                for offset, dur in falas:
                    if offset < spin - 1e-6:          # pergunta, durante o giro
                        spin = max(spin, offset + dur + margem_giro)
                for offset, dur in falas:
                    if offset >= float(evento.get("spin_duration") or 0.0) - 1e-6:
                        resultado = max(resultado, dur + margem)
                evento["spin_duration"] = round(spin, 3)
                duracao = round(spin + resultado, 3)
            else:
                for offset, dur in falas:
                    duracao = max(duracao, offset + dur + margem)
        evento["start"] = round(cursor, 3)
        evento["duration"] = round(duracao, 3)
        cursor += duracao
    plano["total_duration"] = round(cursor, 3)
    if plano.get("gancho_b"):
        plano["gancho_b"]["duration"] = eventos[0]["duration"]
    return plano


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

        rolls = generation["rolls"]
        decisions = director.decide_rolls(rng, rolls)

        self._marcar_cheias(rolls, decisions)
        gancho_a, gancho_b = self._ganchos(rng, generation, out_dir, rolls,
                                          decisions, pedido, escolhas)
        push(gancho_a, durations["hook"])
        self._push_comentario(push, out_dir, durations, pedido)

        # Personagem: rosto na tela cedo quando a imagem existe.
        revelar_cedo = (self.config.get("revelacao_cedo", True)
                        and self._artefato(out_dir, identity_slots.CHARACTER) is not None)
        if revelar_cedo:
            self._push_rolls(push, rng, rolls, decisions, "character", durations,
                             apenas=set(ROLETAS_DE_ABERTURA))
            self._push_reveal(push, generation, out_dir, durations,
                              identity_slots.CHARACTER, rng, pedido, cedo=True)
            self._push_rolls(push, rng, rolls, decisions, "character", durations,
                             exceto=set(ROLETAS_DE_ABERTURA))
        else:
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

        luta = self._push_luta(push, rng, generation, out_dir, durations)

        build = generation["build"]
        push({"type": "final", "build": build,
              "caption": self.captions.for_final(rng, build)},
             durations["final"])
        outro = {"type": "outro",
                 "caption": (self.captions.outro_com_estreia(rng, pedido) if luta
                             else self.captions.outro(rng, pedido))}
        final_img = self._imagem_do_final(out_dir)
        if final_img is not None:
            outro["asset"] = {"path": str(final_img), "synthetic": False,
                              "media": identity_slots.IMAGEM}
            outro["fit"] = "contain"
            outro["motion"] = {"zoom": [1.06, 1.0],
                               "centro": [[0.5, 0.42], [0.5, 0.42]]}
            outro["flash_frames"] = 0
        push(outro, durations["outro"])

        self._marcar_avatares(events_out, generation)
        plano = {
            "generation_id": generation["generation_id"],
            "seed": generation["seed"],
            "total_duration": round(cursor, 3),
            "events": events_out,
        }
        if gancho_b is not None:
            gancho_b["start"], gancho_b["duration"] = 0.0, gancho_a["duration"]
            plano["gancho_b"] = gancho_b
        return plano

    # --------------------------------------------------------------- avatares
    EVENTOS_COM_AVATAR = ("roulette", "stinger", "synergy", "final", "outro",
                          "nameplate")

    @staticmethod
    def _marcar_avatares(eventos: list[dict], generation: dict) -> None:
        """Depois de revelado, o personagem NAO some da tela.

        A imagem dele (e depois a da arma) vira um avatar de canto em toda
        cena desenhada que vem depois — a roleta continua girando com o rosto
        de quem ela esta montando. Sem imagem no disco, nada e marcado.
        """
        atual: dict[str, dict] = {}
        nomes = {identity_slots.CHARACTER: generation.get("character", {}).get("nome", ""),
                 identity_slots.WEAPON: generation.get("weapon", {}).get("nome", "")}
        for evento in eventos:
            asset = evento.get("asset") or {}
            if (evento.get("type") == "identity"
                    and asset.get("media") == identity_slots.IMAGEM
                    and evento.get("slot") in nomes):
                atual[evento["slot"]] = {"path": asset["path"],
                                         "nome": str(nomes[evento["slot"]])}
                continue
            if atual and evento.get("type") in TimelineBuilder.EVENTOS_COM_AVATAR:
                evento["avatares"] = {slot: dict(dado) for slot, dado in atual.items()}

    # ----------------------------------------------------------------- gancho
    def _ganchos(self, rng: random.Random, generation: dict, out_dir: Path | None,
                 rolls: list[dict], decisions: list[dict], pedido: dict | None,
                 escolhas: dict | None) -> tuple[dict, dict | None]:
        """O gancho (A) e, quando `gancho.ab` esta ligado, o alternativo (B).

        A prioridade e conteudo antes de slogan: a IMAGEM do personagem
        pronto (payoff), depois a rolagem de maior peso quando e absurda, e so
        entao o cartao de texto de sempre. B e sempre de OUTRO tipo que A —
        dois textos diferentes nao medem nada.
        """
        cfg = self.config.get("gancho") or {}
        candidatos: list[dict] = []

        imagem = self._imagem_do_gancho(out_dir) if cfg.get("payoff", True) else None
        if imagem is not None:
            candidatos.append({
                "type": "hook", "variante": "payoff",
                "caption": self.captions.hook_payoff(rng, pedido, escolhas),
                "asset": {"path": str(imagem), "synthetic": False,
                          "media": identity_slots.IMAGEM},
                "fit": "contain",
                "motion": cfg.get("motion") or {"zoom": [1.0, 1.14],
                                                 "centro": [[0.5, 0.45], [0.5, 0.38]]},
                "flash_frames": 0,
            })

        absurda = self._rolagem_mais_pesada(rolls, decisions)
        if absurda is not None and not (pedido or {}).get("nome"):
            candidatos.append({"type": "hook", "variante": "absurdo",
                               "caption": self.captions.hook_absurdo(rng, absurda),
                               "destaque": {"category": absurda["category"],
                                            "value": absurda["display_value"]}})

        candidatos.append({"type": "hook", "variante": "texto",
                           "caption": self.captions.hook(rng, pedido, escolhas)})

        gancho_a = candidatos[0]
        gancho_b = candidatos[1] if cfg.get("ab", False) and len(candidatos) > 1 else None
        return gancho_a, (dict(gancho_b) if gancho_b else None)

    def _imagem_do_final(self, out_dir: Path | None) -> Path | None:
        """A imagem que fica atras do CTA: o build PRONTO, de preferencia.

        Ao contrario do gancho, aqui a referencia (personagem COM a arma) e
        a melhor escolha mesmo quando ela ja apareceu: e a foto do produto
        acabado, e o CTA pede o like justamente sobre ela.
        """
        for slot in (identity_slots.REFERENCIA, identity_slots.CHARACTER,
                     identity_slots.WEAPON):
            achado = self._artefato(out_dir, slot)
            # `_artefato` devolve (arquivo, midia) — a midia vem da EXTENSAO,
            # entao um slot de imagem pode trazer mp4 de geracao antiga.
            if achado is not None and achado[1] == identity_slots.IMAGEM:
                return achado[0]
        return None

    def _imagem_do_gancho(self, out_dir: Path | None) -> Path | None:
        """Referencia (personagem COM a arma) > personagem > arma — a menos que
        a referencia va ser o proprio payoff (sem video do Digen): ai o gancho
        abre pelo personagem, para a mesma imagem nao abrir E fechar o video."""
        tem_video = self._artefato(out_dir, identity_slots.CHARACTER_WEAPON) is not None
        ordem = ((identity_slots.REFERENCIA, identity_slots.CHARACTER, identity_slots.WEAPON)
                 if tem_video else
                 (identity_slots.CHARACTER, identity_slots.REFERENCIA, identity_slots.WEAPON))
        for slot in ordem:
            achado = self._artefato(out_dir, slot)
            if achado is not None and achado[1] == identity_slots.IMAGEM:
                return achado[0]
        return None

    @staticmethod
    def _rolagem_mais_pesada(rolls: list[dict], decisions: list[dict]) -> dict | None:
        """A rolagem ABSURD/CONTRADICTORY de maior peso, se houver."""
        melhor, peso = None, 0
        for roll, decision in zip(rolls, decisions):
            if decision["classification"] in ("ABSURD", "CONTRADICTORY") \
                    and decision["weight"] > peso:
                melhor, peso = roll, decision["weight"]
        return melhor

    # ---------------------------------------------------------------- roletas
    def _marcar_cheias(self, rolls: list, decisions: list) -> None:
        """Decide QUAIS roletas merecem o giro cheio. As outras passam voando.

        A regra antiga era ao contrario ("relampago se for numero de peso
        baixo") e so 16% das roletas passavam rapido: sobravam 11,8 giros
        cheios por video, 40,4 s da MESMA roda roxa — 55% do tempo de tela,
        em blocos de ate 31 s seguidos. O espectador nao abandona porque a
        roleta e ruim; abandona porque a decima roleta e identica a primeira.

        Agora o giro cheio e um ORCAMENTO (`roletas_cheias_max`): ficam com
        ele as rolagens que sao NOTICIA — as escolhidas a dedo, as que
        ganharam reacao, e as de maior peso editorial ate o teto. O resto e
        relampago, que continua mostrando o resultado (nada se perde da
        build) em 1,05 s em vez de 3,43 s.
        """
        teto = int(self.config.get("roletas_cheias_max", 4))
        obrigatorias, candidatas = set(), []
        for roll, decision in zip(rolls, decisions):
            chave = (roll.get("entity"), roll.get("roulette_id"))
            if roll.get("escolhido") or decision.get("reaction"):
                obrigatorias.add(chave)
            else:
                candidatas.append((float(decision.get("weight", 0)), chave))
        # maior peso primeiro; empate resolve pela ordem de rolagem (estavel)
        candidatas.sort(key=lambda par: -par[0])
        sobra = max(0, teto - len(obrigatorias))
        self._cheias = obrigatorias | {c for _p, c in candidatas[:sobra]}

    def _duracoes_da_roleta(self, roll: dict, decision: dict,
                            durations: dict) -> tuple[float, float, bool]:
        """(giro, resultado, rapida): tempo de tela proporcional ao peso.

        O giro cheio e o que `_marcar_cheias` escolheu; todo o resto passa
        em relampago. Sem a marcacao (chamada fora do fluxo normal), cai na
        regra antiga para nao mudar o comportamento de quem chama direto.
        """
        cheias = getattr(self, "_cheias", None)
        if cheias is not None:
            rapida = ((roll.get("entity"), roll.get("roulette_id")) not in cheias
                      and "roulette_spin_fast" in durations)
            if rapida:
                return (float(durations["roulette_spin_fast"]),
                        float(durations.get("roulette_result_fast", 0.55)), True)
            chave = ("roulette_result_extreme" if decision["extreme"]
                     else "roulette_result")
            return float(durations["roulette_spin"]), float(durations[chave]), False
        rapidas = set(self.config.get("roletas_rapidas") or [])
        peso_max = float(self.config.get("roletas_rapidas_peso_max", 0))
        rapida = (roll.get("roulette_id") in rapidas
                  and float(decision.get("weight", 0)) <= peso_max
                  and not roll.get("escolhido")
                  and not decision["reaction"]
                  and "roulette_spin_fast" in durations)
        if rapida:
            return (float(durations["roulette_spin_fast"]),
                    float(durations.get("roulette_result_fast", 0.55)), True)
        chave = "roulette_result_extreme" if decision["extreme"] else "roulette_result"
        return float(durations["roulette_spin"]), float(durations[chave]), False

    def _push_rolls(self, push, rng: random.Random, rolls: list[dict],
                    decisions: list[dict], entity: str, durations: dict,
                    apenas: set | None = None, exceto: set | None = None) -> None:
        for indice, roll in enumerate(rolls):
            if roll["entity"] != entity:
                continue
            if apenas is not None and roll.get("roulette_id") not in apenas:
                continue
            if exceto is not None and roll.get("roulette_id") in exceto:
                continue
            decision = decisions[indice]
            spin, resultado, rapida = self._duracoes_da_roleta(roll, decision, durations)
            evento = {
                "type": "roulette",
                "roll": roll,
                "spin_duration": spin,
                "rapida": rapida,
                "effects": decision["effects"],
                "classification": decision["classification"],
                "caption": self.captions.for_event(rng, roll),
            }
            if not rapida:
                # Tensao ANTES do resultado: o que esta em jogo nesta roda.
                evento["caption_spin"] = self.captions.stakes(rng, roll)
            push(evento, spin + resultado)
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
            if duracao > restante + 1e-6:
                # Sem espaco para a reacao INTEIRA, ela nao entra: uma piada
                # cortada no meio e pior que nenhuma (o espectador ve um
                # tranco sem entender o que passou). Com o orcamento de ~10 s
                # de um video de 40 s isso significa uma ou duas reacoes
                # por video, tocando ate o punchline.
                return
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
            # Por que este meme entrou: "RARO · 5% de chance" numa pilula no
            # topo. Sem isso a reacao parece aleatoria; com isso ela e a
            # piada explicada em tres palavras.
            "badge": self._badge_da_reacao(decision),
        }, duracao)

    _ROTULO_CLASSE = {"ABSURD": "ABSURDO", "CONTRADICTORY": "CONTRADITÓRIO",
                      "RARE": "RARO", "FUNNY": "ENGRAÇADO", "VERY_GOOD": "MUITO BOM",
                      "GOOD": "BOM", "BAD": "RUIM", "NORMAL": ""}

    @classmethod
    def _badge_da_reacao(cls, decision: dict) -> str:
        rotulo = cls._ROTULO_CLASSE.get(str(decision.get("classification")), "")
        motivo = str(decision.get("reason") or "").strip()
        m = re.match(r"probabilidade\s+([0-9.,]+)", motivo)
        if m:
            try:
                motivo = f"{round(float(m.group(1).replace(',', '.')) * 100)}% de chance"
            except ValueError:
                pass
        m = re.match(r"surpresa\s+(\d+)", motivo)
        if m:
            motivo = f"surpresa {m.group(1)}/100"
        m = re.match(r"score\s+(\d+)\s+no extremo", motivo)
        if m:
            motivo = f"{m.group(1)} de 100"
        if motivo.startswith("resultado briga"):
            motivo = "briga com o resto da build"
        if motivo.startswith("score "):
            motivo = motivo.replace("score ", "") + " de 100"
        partes = [p for p in (rotulo, motivo) if p]
        return " · ".join(partes)

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

    # ------------------------------------------------------------------- luta
    def _push_luta(self, push, rng: random.Random, generation: dict,
                   out_dir: Path | None, durations: dict) -> dict | None:
        """O round decisivo da estreia no FIM do video de build.

        E o loop que faltava: a roleta cria, a arena responde. O trecho e
        `segundos` terminando `depois_do_ko` s apos o nocaute (ou a janela
        mais quente, se a gravacao nao marcou o KO); HUD e callouts sao
        levados para o relogio do trecho, como o torneio faz com o corte de
        tedio. Sem estreia gravada, nada entra — nunca um cartao no lugar.
        """
        cfg = self.config.get("luta_no_build") or {}
        if not cfg.get("ativa", True) or out_dir is None:
            return None
        caminho = Path(out_dir) / "estreia" / "fight.json"
        if not caminho.is_file():
            return None
        try:
            with open(caminho, encoding="utf-8-sig") as fh:
                fight = json.load(fh)
        except (OSError, ValueError):
            return None
        rounds = list(fight.get("lutas") or ([fight["luta"]] if fight.get("luta") else []))
        if not rounds:
            return None
        luta = rounds[-1]
        clipes = luta.get("clipes") or {}
        if not clipes or not any(Path(c.get("path", "")).is_file() for c in clipes.values()):
            return None

        from ..tournament.highlights import janela_mais_quente
        from ..tournament.timeline import evento_gameplay
        evento = evento_gameplay(rng, luta, self.config, self.captions)
        if evento is None:
            return None

        janela = float(cfg.get("segundos", 7.0))
        total = max(float(c.get("duracao") or 0.0) for c in clipes.values())
        if total <= 0:
            return None
        ko = luta.get("ko_em_clipe")
        if ko:
            fim = min(total, float(ko) + float(cfg.get("depois_do_ko", 1.2)))
            inicio = max(0.0, fim - janela)
        else:
            inicio, _ = janela_mais_quente(luta.get("eventos_dano") or [], janela)
            inicio = max(0.0, min(float(inicio), max(0.0, total - janela)))
            fim = min(total, inicio + janela)
        duracao = round(fim - inicio, 2)
        if duracao < 2.0:
            return None

        evento["start_offset"] = round(inicio, 2)
        evento["recorte_no_build"] = [round(inicio, 2), duracao]
        hud = evento.get("hud")
        if hud:
            hud["serie_hp"] = self._deslocar_serie(hud.get("serie_hp"), inicio, fim)
            if hud.get("serie_plano"):
                hud["serie_plano"] = self._deslocar_serie(hud["serie_plano"], inicio, fim)
        evento["callouts"] = [
            {**c, "t": round(float(c["t"]) - inicio, 2)}
            for c in (evento.get("callouts") or [])
            if inicio <= float(c.get("t", 0.0)) <= fim - 0.3]
        nome = generation["character"].get("nome", "")
        adversario = luta.get("p2") if luta.get("p1") == nome else luta.get("p1")
        evento["narracao"] = (f"Agora {nome} luta de verdade, contra {adversario}."
                              if adversario else f"Agora {nome} luta de verdade.")
        evento["caption"] = ""

        if cfg.get("stinger", True):
            push({"type": "stinger", "entity": "character",
                  "caption": self.captions.stinger(rng, "luta")},
                 float(durations.get("luta_stinger", 1.0)))
        push(evento, duracao)
        return luta

    @staticmethod
    def _deslocar_serie(serie, inicio: float, fim: float) -> list:
        """Amostras (t, ...) para o relogio do trecho [inicio, fim].

        A ultima amostra ANTES do inicio entra em t=0: e ela que diz quanto
        HP cada um tinha quando o trecho comeca.
        """
        ordenada = sorted((tuple(a) for a in (serie or []) if len(a) >= 2),
                          key=lambda a: float(a[0]))
        saida = []
        anterior = None
        for amostra in ordenada:
            t = float(amostra[0])
            if t < inicio:
                anterior = amostra
                continue
            if t > fim:
                break
            saida.append((round(t - inicio, 3), *amostra[1:]))
        if anterior is not None and (not saida or saida[0][0] > 0.0):
            saida.insert(0, (0.0, *anterior[1:]))
        return saida

    # ------------------------------------------------------------- recompensa
    def _push_reveal(self, push, generation: dict, out_dir: Path | None,
                     durations: dict, slot: str, rng: random.Random,
                     pedido: dict | None = None, cedo: bool = False) -> None:
        """O clipe daquele slot; sem ele, o nameplate no lugar.

        O renderer decide por CAPACIDADE, nao por tipo (`_asset_de_video`):
        basta o evento apontar para um mp4 real com `synthetic: False`.

        `fit: "contain"` porque os clipes sao gerados em 9:16 - no perfil
        `normal` (16:9) o crop-para-preencher comeria as laterais.

        `cedo`: a revelacao do personagem antes das roletas de atributo. A
        placa nao pode entregar a altura que a roleta de TAMANHO ainda vai
        sortear, entao a segunda linha fica so com a classe.
        """
        placa = self._nameplate(generation, slot, rng, pedido, cedo=cedo)
        achado = self._artefato(out_dir, slot)
        if achado is None and slot == identity_slots.CHARACTER_WEAPON:
            # Sem o video do Digen (desligado, ou ainda nao chegou), o payoff
            # e a IMAGEM do personagem com a arma, com camera — a mesma cena,
            # em vez de um nameplate. A recompensa nao depende do site.
            achado = self._artefato(out_dir, identity_slots.REFERENCIA)
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
                   rng: random.Random, pedido: dict | None = None,
                   cedo: bool = False) -> dict:
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
        if cedo:
            return {"titulo": str(personagem.get("nome", "")).upper(),
                    "subtitulo": classe}
        return {"titulo": str(personagem.get("nome", "")).upper(),
                "subtitulo": f"{classe} - {altura} m"}
