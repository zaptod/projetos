"""Torneio como CONTEUDO: roda o chaveamento oficial do neural_fights e
transforma cada luta em um evento avaliado, do mesmo jeito que as roletas.

Nada de chaveamento e reimplementado aqui — o motor e o `Tournament` do
neural_fights (com toda a validacao dele) e as lutas rodam no `run_headless_match`,
o mesmo motor da simulacao visual. O que esta camada acrescenta e a leitura
NARRATIVA: quem era favorito, quem virou no ultimo fio de vida, quem atropelou
— gerando score/tier/surpresa para a edicao reagir.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from ..nf_bridge import loader as nf
from ..generation.random_engine import RandomEngine
from ..evaluation.roll_evaluator import RollEvaluator

OUTPUTS = Path(__file__).resolve().parents[2] / "outputs"

# Arenas usadas nos videos. Sao mais compactas que a "Arena" padrao (30x20 m)
# porque enquadram melhor — e a escolha e sorteada por luta, dando variedade
# visual como a live ja tem. ATENCAO: a arena MUDA o resultado da luta (o
# terreno e diferente), entao ela e decidida uma vez e vale para os dois
# formatos de video. So resolucao e modo de camera podem variar entre eles.
ARENAS_DE_VIDEO = ("Arena Pequena", "Ringue", "Cyberpunk", "Dojo", "Templo")

# Enquadramento: os dois formatos usam a camera padrao (ARENA), travada na
# arena inteira. Uma camera que persegue os lutadores enche o quadro, mas
# cansa de assistir — a luta fica legivel quando o cenario fica parado.
CAMERA_POR_PERFIL = {"celular": None, "normal": None}
PORTRAIT_POR_PERFIL = {"celular": True, "normal": False}


def _potencia_de_dois(n: int) -> int:
    potencia = 1
    while potencia * 2 <= n:
        potencia *= 2
    return potencia


def personagens_gerados() -> list[str]:
    """Nomes criados pelos videos de roleta (registrados em insercao.json)."""
    nomes = []
    for arquivo in sorted(OUTPUTS.glob("generation_*/insercao.json")):
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if dados.get("personagem"):
            nomes.append(dados["personagem"])
    return nomes


def selecionar_participantes(fonte: str, quantidade: int, rng) -> list[str]:
    """fonte: 'gerados' | 'banco' | 'misto'."""
    _, personagens = nf.database.carregar_database()
    por_nome = {p["nome"]: p for p in personagens}
    gerados = [nome for nome in personagens_gerados() if nome in por_nome]

    if fonte == "gerados":
        pool = list(dict.fromkeys(gerados))
    elif fonte == "misto":
        resto = [p["nome"] for p in personagens if p["nome"] not in set(gerados)]
        rng.shuffle(resto)
        pool = list(dict.fromkeys(gerados)) + resto
    else:
        pool = [p["nome"] for p in personagens]
        rng.shuffle(pool)

    if len(pool) < 2:
        raise ValueError(
            f"fonte '{fonte}' tem apenas {len(pool)} participante(s). "
            "Gere mais builds ou use --fonte banco.")

    alvo = _potencia_de_dois(min(quantidade, len(pool)))
    if alvo < 2:
        raise ValueError("sao necessarios ao menos 2 participantes")
    return pool[:alvo]


class TournamentSession:
    """Roda o torneio inteiro e devolve o JSON pronto para virar video."""

    def __init__(self, scoring: dict, alvo_gameplay: float = 10.0):
        self.evaluator = RollEvaluator(scoring, {"compatibility": {}})
        self.drama = scoring.get("tournament_drama", {})
        self.alvo_gameplay = alvo_gameplay
        self._gravar_em: Path | None = None
        self._perfis: tuple[str, ...] = ("celular", "normal")

    # ------------------------------------------------------------------ dados
    def gerar(self, seed: int | None = None, fonte: str = "misto",
              quantidade: int = 8, nome: str = "Torneio Neural Fights",
              progresso=None, gravar_em: Path | None = None,
              perfis: tuple[str, ...] = ("celular", "normal")) -> dict:
        """Roda o torneio. Com `gravar_em`, cada luta e GRAVADA em video.

        Quando grava, a gravacao e a fonte da verdade do resultado: a luta e
        simulada uma vez so, desenhando. Simular em headless e depois gravar
        de novo seriam dois caminhos de codigo, e qualquer divergencia daria
        um video que contradiz o placar exibido logo em seguida.
        """
        from neural_fights.tournament.tournament_mode import Tournament

        seed = seed if seed is not None else RandomEngine.new_seed()
        engine = RandomEngine(seed)
        rng = engine.fork("torneio:participantes")
        self._gravar_em = Path(gravar_em) if gravar_em else None
        self._perfis = tuple(perfis)
        self._rng_arena = engine.fork("torneio:arenas")

        participantes = selecionar_participantes(fonte, quantidade, rng)
        _, personagens = nf.database.carregar_database()
        fichas = {p["nome"]: p for p in personagens}

        torneio = Tournament(nome)
        torneio.participants = list(participantes)
        # generate_bracket() embaralha com o `random` GLOBAL do neural_fights:
        # sem prender o estado global, a mesma seed produziria chaves
        # diferentes e o torneio deixaria de ser reproduzivel.
        estado = random.getstate()
        random.seed(rng.randrange(2**31))
        try:
            torneio.generate_bracket()
            torneio.start_tournament()
        finally:
            random.setstate(estado)

        gerados = set(personagens_gerados())
        lutas: list[dict] = []
        total = sum(len(r.matches) for r in torneio.bracket)
        feitas = 0

        while True:
            match = torneio.get_current_match()
            if match is None:
                break
            resultado = self._rodar_luta(match, seed, fichas, gerados,
                                         len(torneio.bracket))
            torneio.record_match_result(
                winner_name=resultado["vencedor"],
                duration=resultado["duracao"],
                ko_type=resultado["ko_type"])
            lutas.append(resultado)
            feitas += 1
            if progresso:
                progresso(feitas, total, resultado)

        campeao = torneio.champion
        return {
            "seed": seed,
            "nome": nome,
            "fonte": fonte,
            "participantes": participantes,
            "rodadas": [
                {"nome": r.name, "numero": r.round_num,
                 "lutas": [m.match_id for m in r.matches]}
                for r in torneio.bracket
            ],
            "lutas": lutas,
            "campeao": campeao,
            "campeao_ficha": fichas.get(campeao, {}),
            "campeao_gerado": campeao in gerados,
            "estatisticas": self._estatisticas(lutas, campeao),
        }

    # ------------------------------------------------------------------ luta
    def _rodar_luta(self, match, seed: int, fichas: dict, gerados: set,
                    total_rodadas: int) -> dict:
        p1, p2 = match.fighter1_name, match.fighter2_name
        cenario = self._rng_arena.choice(ARENAS_DE_VIDEO)
        base_seed = seed + match.match_id * 17

        if getattr(self, "_gravar_em", None):
            bruto = self._gravar_luta(p1, p2, cenario, base_seed, match.match_id)
        else:
            bruto = self._simular_luta(p1, p2, cenario, base_seed)

        vencedor = bruto["vencedor"] or p1
        perdedor = p2 if vencedor == p1 else p1
        evento = {
            "match_id": match.match_id,
            "rodada": match.round_num,
            "rodada_nome": self._nome_rodada(match.round_num, total_rodadas),
            "p1": p1, "p2": p2,
            "p1_ficha": fichas.get(p1, {}), "p2_ficha": fichas.get(p2, {}),
            "vencedor": vencedor, "perdedor": perdedor,
            "vencedor_gerado": vencedor in gerados,
            "duracao": round(bruto["duracao"], 1),
            "motivo": bruto["motivo"],
            "ko_type": self._ko_type(bruto["motivo"]),
            "hp_vencedor": round(bruto["hp_vencedor"]),
            "seed": bruto["seed"],
            "cenario": cenario,
        }
        if bruto.get("clipes"):
            evento["clipes"] = bruto["clipes"]
        evento.update(self._dramatizar(evento, fichas))
        return self.evaluator.decorate(evento)

    def _simular_luta(self, p1: str, p2: str, cenario: str, base_seed: int) -> dict:
        """Caminho rapido, sem video: usado por --generation-only e lotes."""
        from neural_fights.simulation.headless import run_headless_match

        config = {"p1_nome": p1, "p2_nome": p2, "cenario": cenario,
                  "best_of": 1, "portrait_mode": False}
        resultado = None
        for tentativa in range(3):  # empate = refaz com seed derivada
            resultado = run_headless_match(
                config, fixed_dt=1 / 60, max_duration=120.0,
                seed=base_seed + tentativa)
            if not resultado.success:
                raise RuntimeError(f"motor falhou em {p1} vs {p2}: {resultado.error}")
            if resultado.winner is not None:
                break
        vencedor = resultado.winner or p1
        hp = (resultado.p1_hp_ratio if vencedor == p1 else resultado.p2_hp_ratio)
        return {"vencedor": resultado.winner, "duracao": resultado.duration,
                "motivo": resultado.reason, "seed": resultado.seed,
                "hp_vencedor": max(0.0, hp) * 100}

    def _gravar_luta(self, p1: str, p2: str, cenario: str, base_seed: int,
                     match_id: int) -> dict:
        """Grava a luta (um mp4 por formato) e devolve o resultado dela.

        Os formatos compartilham arena e seed — logo, sao a MESMA luta. So
        mudam a resolucao e o enquadramento, que comprovadamente nao afetam o
        combate.
        """
        from . import capture, highlights

        pasta = self._gravar_em / "gameplay"
        for tentativa in range(3):
            semente = base_seed + tentativa
            tarefas = [{
                "p1": p1, "p2": p2, "seed": semente, "cenario": cenario,
                "saida": pasta / f"bruto_{match_id:02d}_{perfil}.mp4",
                "portrait": PORTRAIT_POR_PERFIL.get(perfil, False),
                "camera_modo": CAMERA_POR_PERFIL.get(perfil),
            } for perfil in self._perfis]
            gravacoes = capture.gravar_em_paralelo(tarefas, trabalhadores=len(tarefas))

            falhas = [g for g in gravacoes if not g.get("sucesso")]
            if falhas:
                raise RuntimeError(
                    f"gravacao falhou em {p1} vs {p2}: {falhas[0].get('erro')}")
            referencia = gravacoes[0]
            if not referencia.get("empate"):
                break

        # Invariante barata: os formatos precisam contar a mesma historia.
        vencedores = {g.get("vencedor") for g in gravacoes}
        if len(vencedores) > 1:
            raise RuntimeError(
                f"formatos divergiram em {p1} vs {p2}: {vencedores}")

        clipes = {}
        for perfil, gravacao in zip(self._perfis, gravacoes):
            trechos = highlights.planejar_recorte(gravacao, alvo=self.alvo_gameplay)
            destino = pasta / f"luta_{match_id:02d}_{perfil}.mp4"
            duracao = highlights.extrair(gravacao["arquivo"], destino, trechos)
            if duracao > 0:
                clipes[perfil] = {"path": str(destino), "duracao": duracao,
                                  "trechos": trechos,
                                  "crop": gravacao.get("recorte_util")}
            Path(gravacao["arquivo"]).unlink(missing_ok=True)  # bruto ja foi cortado

        return {"vencedor": referencia.get("vencedor"),
                "duracao": referencia.get("duracao_jogo", 0.0),
                "motivo": referencia.get("motivo", "knockout"),
                "seed": referencia.get("seed", base_seed),
                "hp_vencedor": referencia.get("hp_vencedor") or 0.0,
                "clipes": clipes}

    @staticmethod
    def _nome_rodada(numero: int, total: int) -> str:
        faltam = total - numero
        return {1: "FINAL", 2: "SEMIFINAL", 3: "QUARTAS DE FINAL",
                4: "OITAVAS DE FINAL"}.get(faltam, f"RODADA {numero + 1}")

    @staticmethod
    def _ko_type(motivo: str) -> str:
        return {"knockout": "KO", "double_ko": "DUPLO KO"}.get(
            motivo, "Decisao por HP")

    # -------------------------------------------------------------- narrativa
    def _dramatizar(self, evento: dict, fichas: dict) -> dict:
        """Le a luta como historia: score 0-100 e rotulos do momento.

        Os limiares vivem em scoring.json e foram calibrados sobre a
        distribuicao real do motor (ver _comment_drama la).
        """
        cfg = self.drama
        bonus = cfg.get("bonus", {})
        hp = evento["hp_vencedor"]
        duracao = evento["duracao"]
        score = 50.0
        marcas: list[str] = []

        if evento["motivo"] == "double_ko":
            score += bonus.get("duplo_ko", 45)
            marcas.append("DUPLO KO")
        elif evento["motivo"] != "knockout":
            score += bonus.get("decisao", -18)
            marcas.append("decisao por pontos")

        if hp <= cfg.get("hp_clutch", 15) and evento["motivo"] == "knockout":
            score += bonus.get("clutch", 32)
            marcas.append("virada no fio de vida")
        elif hp >= cfg.get("hp_flawless", 70):
            score += bonus.get("flawless", 22)
            marcas.append("atropelou sem tomar dano")

        if duracao <= cfg.get("duracao_speedrun", 20):
            score += bonus.get("speedrun", 14)
            marcas.append("speedrun")
        elif duracao >= cfg.get("duracao_maratona", 60):
            score += bonus.get("maratona", 10)
            marcas.append("maratona")

        # gradiente continuo: quanto mais longe da luta mediana, mais interessante
        mediana = cfg.get("hp_mediana", 34)
        distancia = abs(hp - mediana) / max(1, 100 - mediana)
        score += distancia * cfg.get("gradiente_max", 10)

        # zebra: o favorito (forca+mana) perdeu
        favorito, poder_fav, poder_zebra = self._favorito(evento, fichas)
        zebra = favorito is not None and favorito == evento["perdedor"]
        if zebra:
            vantagem = poder_fav - poder_zebra
            score += min(cfg.get("zebra_max", 25),
                         vantagem * cfg.get("zebra_por_ponto", 4))
            marcas.append("ZEBRA")

        if evento["rodada_nome"] == "FINAL":
            score += bonus.get("final", 8)

        score = max(0, min(100, round(score)))
        surpresa = min(100, round(abs(score - 50) * 1.6
                                  + (cfg.get("zebra_surpresa", 30) if zebra else 0)))
        return {"score": score, "marcas": marcas, "zebra": zebra,
                "favorito": favorito, "surpresa": surpresa}

    @staticmethod
    def _favorito(evento: dict, fichas: dict):
        f1, f2 = evento["p1_ficha"], evento["p2_ficha"]
        if not f1 or not f2:
            return None, 0.0, 0.0
        poder1 = f1.get("forca", 5) + f1.get("mana", 5)
        poder2 = f2.get("forca", 5) + f2.get("mana", 5)
        if abs(poder1 - poder2) < 1.5:
            return None, 0.0, 0.0
        if poder1 > poder2:
            return evento["p1"], poder1, poder2
        return evento["p2"], poder2, poder1

    # ----------------------------------------------------------- estatisticas
    @staticmethod
    def _estatisticas(lutas: list[dict], campeao: str | None) -> dict:
        if not lutas:
            return {}
        mais_rapida = min(lutas, key=lambda l: l["duracao"])
        mais_longa = max(lutas, key=lambda l: l["duracao"])
        melhor = max(lutas, key=lambda l: l["score"])
        caminho = [l for l in lutas if l["vencedor"] == campeao]
        return {
            "total_lutas": len(lutas),
            "kos": sum(1 for l in lutas if "KO" in l["ko_type"]),
            "zebras": sum(1 for l in lutas if l["zebra"]),
            "mais_rapida": {"luta": f"{mais_rapida['vencedor']} venceu",
                            "duracao": mais_rapida["duracao"]},
            "mais_longa": {"luta": f"{mais_longa['vencedor']} venceu",
                           "duracao": mais_longa["duracao"]},
            "melhor_luta": {"luta": f"{melhor['p1']} vs {melhor['p2']}",
                            "score": melhor["score"], "marcas": melhor["marcas"]},
            "hp_medio_campeao": round(
                sum(l["hp_vencedor"] for l in caminho) / len(caminho)) if caminho else 0,
        }
