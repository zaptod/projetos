"""Lutas como CONTEUDO: torneio, luta unica e estreia sobre o mesmo motor.

Nada de chaveamento e reimplementado aqui — o motor e o `Tournament` do
neural_fights (com toda a validacao dele) e as lutas rodam no gravador oficial
(`neural_fights.recording.fight_recorder`), o mesmo motor da simulacao visual.
O que esta camada acrescenta e a leitura NARRATIVA: quem era favorito, quem
virou no ultimo fio de vida, quem atropelou — gerando score/tier/surpresa para
a edicao reagir.

Onda 9: a gravacao e uma so para os tres formatos (`gravar_confronto`). Ela
sai em resolucao nativa, com a camera DIRETOR e sem o HUD do jogo, e devolve
alem do mp4 a serie de HP, os eventos narrativos e as metricas de camera —
ja no relogio do clipe cortado, que e o que o renderer ve.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from ..nf_bridge import loader as nf
from ..generation.random_engine import RandomEngine
from ..evaluation.roll_evaluator import RollEvaluator
from . import capture, highlights

OUTPUTS = Path(__file__).resolve().parents[2] / "outputs"

# Arenas usadas nos videos. Sao mais compactas que a "Arena" padrao (30x20 m)
# porque enquadram melhor — e a escolha e sorteada por luta, dando variedade
# visual como a live ja tem. ATENCAO: a arena MUDA o resultado da luta (o
# terreno e diferente), entao ela e decidida uma vez e vale para os dois
# formatos de video. So resolucao e modo de camera podem variar entre eles.
# As arenas do video sao as VERTICAIS (9:16), desenhadas no motor para este
# uso — ver `ARENAS_VERTICAIS` em neural_fights/core/arena.py. Elas encaixam
# exatamente no quadro do celular: com a camera presa a arena inteira enche a
# tela sem faixa morta, e o lutador sai com ~16-20% da largura contra 6,2% do
# Templo e 10,0% do Ringue (medido em 1080x1920). Os numeros estavam pela
# METADE aqui ate 10/09/2026 porque a SondaCamera media o raio desenhado e
# chamava de diametro — ver `SondaCamera.on_frame` no fight_recorder.
#
# A MESMA arena vale para os dois formatos, e isso e obrigatorio: a arena
# muda o terreno e portanto o RESULTADO da luta, e `gravar_confronto` aborta
# se os formatos divergirem no vencedor. Nao custa nada ao 16:9 porque la a
# camera e a DIRETOR, que enquadra os lutadores e nao a arena — o formato do
# palco lhe e indiferente.
#
# As paisagens antigas ficam registradas para re-render de video ja gravado
# (o cenario vem do fight.json) e para quem quiser o catalogo antigo.
# Os nomes sao repetidos aqui em vez de importados de `core.arena` de
# proposito: importar o motor no topo puxaria pygame para dentro de quem so
# gera DADOS (`--generation-only`, os lotes de balanceamento), que hoje roda
# sem ele. O contrato — nomes existem no motor, sao 9:16 e tem o mesmo
# tamanho — e garantido por teste (test_arenas_verticais_regressions.py).
ARENAS_DE_VIDEO = ("Duto", "Poco", "Torre")
ARENAS_DE_VIDEO_LEGADO = ("Arena Pequena", "Ringue", "Cyberpunk", "Dojo", "Templo")

# A estreia usa o mesmo catalogo vertical; a constante fica porque a estreia
# e o formato de camera presa e pode querer um subconjunto proprio depois.
ARENAS_DE_ESTREIA = ARENAS_DE_VIDEO

# Enquadramento de VIDEO (Onda 9): a camera DIRETOR — zona morta, pan lento,
# zoom-in so apos estabilidade, zoom-out rapido, sem tremor. O ARENA (quadro
# travado) deixava o lutador com 5% da largura no 9:16; o AUTO (camera de
# jogo) cansa. Medido: nenhum modo altera o resultado da luta.
CAMERA_DE_VIDEO = "DIRETOR"
# Resolucao NATIVA por perfil — a mesma do render.json, para nao haver
# upscale. O perfil que nao estiver aqui grava no par padrao do modo.
RESOLUCAO_POR_PERFIL = {"celular": (1080, 1920), "normal": (1920, 1080)}
PORTRAIT_POR_PERFIL = {"celular": True, "normal": False}

# Excecoes ao CAMERA_DE_VIDEO, por origem e por perfil. Decisao do Adrian:
# na ESTREIA vertical a camera fica PRESA na arena — a luta de apresentacao
# mostra o palco inteiro, nao persegue os corpos. Como o quadro e fixo, o
# gravador ainda devolve `recorte_util`, que apara so a faixa morta embaixo
# (a largura fica inteira): arena toda, sem tarja.
# Origem ausente aqui, ou perfil ausente na origem, cai no `camera` de cima.
CAMERA_POR_ORIGEM = {
    "estreia": {"celular": "ARENA"},
}

GAMEPLAY_PADRAO = {
    "max_total": 45.0, "seca": 4.0, "contexto": 1.0, "protecao_ko": 8.0,
    "abertura": 0.8, "camera": CAMERA_DE_VIDEO, "sem_hud": True,
    # None = o default da classe Camera (7,0 m). Ver GAMEPLAY_POR_ORIGEM.
    "camera_largura_min": None,
    "camera_por_origem": CAMERA_POR_ORIGEM,
    # Luta curta (<= isto) entra inteira, sem corte de tedio. Era fixo em
    # 12 s dentro de `highlights.planejar_corte_tedio`; virou knob na 15B
    # porque no formato de 25 s o degrau aparece: 11 s passavam inteiros e
    # 13 s eram cortados.
    "minimo_para_cortar": 12.0,
}

# Onda 15B: o DUELO e um formato proprio — a luta inteira em 20-35 s, sem
# cena parada. Medido em 11/09/2026: a retencao media do build e 28,1% (19,4 s
# vistos de 74) e a da estreia e 3,4% (mediana ZERO, 3,3 s de 103). O publico
# entrega ~20 s a este canal, entao o video tem que caber nisso.
#
# Escopar por ORIGEM e o que mantem build, estreia e torneio intactos: eles
# continuam lendo `GAMEPLAY_PADRAO` sem enxergar nada disto. Ha teste
# cobrando que a estreia nao mudou.
GAMEPLAY_POR_ORIGEM = {
    "duelo": {
        # 28 s de teto: sobra folga para a identidade de 1,5 s e o veredito
        # de 1,2 s cabendo nos 20-35 s do formato.
        "max_total": 28.0,
        # `seca` de 4,0 para 2,0 e o que transforma 45 s de luta em ~25 s de
        # pancada: qualquer janela de 2 s sem dano vira corte.
        "seca": 2.0,
        "contexto": 0.5,
        "protecao_ko": 6.0,
        "abertura": 0.4,
        "minimo_para_cortar": 8.0,
        # O DIRETOR pode fechar ate 5,0 m de largura visivel, contra os
        # 7,0 m do default. Medido em 11/09/2026: com 7,0 m o corpo do
        # lutador ocupa ~20% da largura no 9:16; a 5,0 m passa de 30%.
        # So o duelo — mexer no default re-enquadraria estreia e torneio.
        "camera_largura_min": 5.0,
    },
}


def camera_do_perfil(gameplay: dict, origem: str, perfil: str) -> str:
    """Modo de camera desta gravacao. Varia por perfil de proposito.

    A arena e a seed sao as mesmas nos dois formatos — so o enquadramento
    muda, e enquadramento comprovadamente nao altera o resultado da luta
    (`gravar_confronto` ainda checa que os formatos concordam no vencedor).
    """
    por_origem = (gameplay.get("camera_por_origem") or {}).get(str(origem)) or {}
    return por_origem.get(perfil) or gameplay.get("camera") or CAMERA_DE_VIDEO


def config_gameplay(editing_config: dict | None,
                    origem: str | None = None) -> dict:
    """Bloco `gameplay` do editing.json com os padroes preenchidos.

    `origem` sobrepoe o bloco por formato, na ordem padrao -> editing.json ->
    padrao da origem -> editing.json da origem. Sem `origem`, a resposta e
    exatamente a de sempre: build, estreia e torneio nao mudam de ritmo
    porque o duelo existe.
    """
    bloco = dict(GAMEPLAY_PADRAO)
    if editing_config:
        bloco.update({k: v for k, v in (editing_config.get("gameplay") or {}).items()
                      if k in bloco})
    if origem:
        bloco.update({k: v for k, v in GAMEPLAY_POR_ORIGEM.get(origem, {}).items()
                      if k in bloco})
        if editing_config:
            por_origem = (editing_config.get("gameplay_por_origem") or {})
            bloco.update({k: v for k, v in (por_origem.get(origem) or {}).items()
                          if k in bloco})
    return bloco


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


def fichas_do_banco() -> dict[str, dict]:
    _, personagens = nf.database.carregar_database()
    fichas = {}
    for p in personagens:
        ficha = dict(p)
        # Onda 11D: a ficha carrega o KIT (sorteado ou fixo) com descrição —
        # o fight_card lista os nomes e o showcase da estreia descreve.
        ficha["kit"] = nf.kit_do_personagem(p)
        fichas[p["nome"]] = ficha
    return fichas


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


# ---------------------------------------------------------------- gravacao
def simular_luta(p1: str, p2: str, cenario: str, base_seed: int) -> dict:
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


def gravar_confronto(p1: str, p2: str, cenario: str, base_seed: int,
                     pasta: Path, prefixo: str,
                     perfis: tuple[str, ...] = ("celular", "normal"), *,
                     gameplay: dict | None = None,
                     resolucoes: dict | None = None,
                     origem: str = "luta") -> dict:
    """Grava a luta (um mp4 por formato), corta o tedio e devolve o bruto.

    A gravacao e a fonte da verdade do resultado: a luta e simulada uma vez
    so, desenhando. Os formatos compartilham arena e seed — logo, sao a MESMA
    luta. So mudam a resolucao e o enquadramento, que comprovadamente nao
    afetam o combate.

    O corte e decidido UMA vez, na gravacao de referencia, e aplicado aos
    dois formatos: mesmos golpes, mesmos segundos. A serie de HP e os eventos
    narrativos voltam ja no relogio do clipe cortado.
    """
    gameplay = {**GAMEPLAY_PADRAO, **(gameplay or {})}
    resolucoes = resolucoes or RESOLUCAO_POR_PERFIL
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)

    gravacoes: list[dict] = []
    for tentativa in range(3):
        semente = base_seed + tentativa
        tarefas = [{
            "p1": p1, "p2": p2, "seed": semente, "cenario": cenario,
            "saida": pasta / f"bruto_{prefixo}_{perfil}.mp4",
            "portrait": PORTRAIT_POR_PERFIL.get(perfil, False),
            "camera_modo": camera_do_perfil(gameplay, origem, perfil),
            "resolucao": resolucoes.get(perfil),
            "sem_hud": bool(gameplay.get("sem_hud", True)),
            "camera_largura_min": gameplay.get("camera_largura_min"),
        } for perfil in perfis]
        gravacoes = capture.gravar_em_paralelo(tarefas, trabalhadores=len(tarefas))

        falhas = [g for g in gravacoes if not g.get("sucesso")]
        if falhas:
            raise RuntimeError(
                f"gravacao falhou em {p1} vs {p2}: {falhas[0].get('erro')}")
        if not gravacoes[0].get("empate"):
            break

    referencia = gravacoes[0]
    # Invariante barata: os formatos precisam contar a mesma historia.
    vencedores = {g.get("vencedor") for g in gravacoes}
    if len(vencedores) > 1:
        raise RuntimeError(
            f"formatos divergiram em {p1} vs {p2}: {vencedores}")

    trechos = highlights.planejar_corte_tedio(
        referencia, max_total=float(gameplay["max_total"]),
        seca_min=float(gameplay["seca"]), contexto=float(gameplay["contexto"]),
        protecao_ko=float(gameplay["protecao_ko"]),
        abertura=float(gameplay["abertura"]),
        minimo_para_cortar=float(gameplay.get("minimo_para_cortar", 12.0)))
    remap = highlights.remapear_gravacao(referencia, trechos)

    clipes = {}
    for perfil, gravacao in zip(perfis, gravacoes):
        destino = pasta / f"luta_{prefixo}_{perfil}.mp4"
        duracao = highlights.extrair(gravacao["arquivo"], destino, trechos)
        if duracao > 0:
            clipes[perfil] = {"path": str(destino), "duracao": duracao,
                              "trechos": trechos,
                              "crop": gravacao.get("recorte_util"),
                              "resolucao": gravacao.get("resolucao")}
        Path(gravacao["arquivo"]).unlink(missing_ok=True)  # bruto ja foi cortado

    return {
        "vencedor": referencia.get("vencedor"),
        "duracao": referencia.get("duracao_jogo", 0.0),
        "motivo": referencia.get("motivo", "knockout"),
        "seed": referencia.get("seed", base_seed),
        "hp_vencedor": referencia.get("hp_vencedor") or 0.0,
        "clipes": clipes,
        "serie_hp": remap["serie_hp"],
        "serie_plano": remap.get("serie_plano") or [],
        "eventos_narrativos": remap["eventos_narrativos"],
        "eventos_dano": remap["eventos_dano"],
        "ko_em_clipe": remap["ko_em_video"],
        "duracao_clipe": remap["duracao"],
        "duracao_gravacao": referencia.get("duracao_video"),
        # A camera pode DIVERGIR entre os formatos (estreia vertical grava
        # em ARENA). `camera`/`metricas_video` continuam sendo os da
        # referencia, para quem so sabe ler uma luta; o dicionario por perfil
        # e o registro honesto de quem gravou o que.
        "camera": referencia.get("camera_modo"),
        "metricas_video": referencia.get("metricas_video"),
        "camera_por_perfil": {perfil: g.get("camera_modo")
                              for perfil, g in zip(perfis, gravacoes)},
    }


# ---------------------------------------------------------------- narrativa
def favorito(evento: dict, fichas: dict):
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


def dramatizar(evento: dict, fichas: dict, cfg: dict) -> dict:
    """Le a luta como historia: score 0-100 e rotulos do momento.

    Os limiares vivem em scoring.json e foram calibrados sobre a
    distribuicao real do motor (ver _comment_drama la).
    """
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
    fav, poder_fav, poder_zebra = favorito(evento, fichas)
    zebra = fav is not None and fav == evento["perdedor"]
    if zebra:
        vantagem = poder_fav - poder_zebra
        score += min(cfg.get("zebra_max", 25),
                     vantagem * cfg.get("zebra_por_ponto", 4))
        marcas.append("ZEBRA")

    # Onda 9: viradas de lideranca lidas da propria gravacao — uma luta que
    # trocou de lider 3 vezes e melhor conteudo que o placar final sugere.
    viradas = sum(1 for e in (evento.get("eventos_narrativos") or [])
                  if e.get("tipo") == "virada")
    if viradas >= 2:
        score += min(cfg.get("viradas_max", 12), viradas * cfg.get("virada_por_ponto", 4))
        marcas.append("luta de viradas")

    if evento.get("rodada_nome") == "FINAL":
        score += bonus.get("final", 8)

    score = max(0, min(100, round(score)))
    surpresa = min(100, round(abs(score - 50) * 1.6
                              + (cfg.get("zebra_surpresa", 30) if zebra else 0)))
    return {"score": score, "marcas": marcas, "zebra": zebra,
            "favorito": fav, "surpresa": surpresa}


def _ko_type(motivo: str) -> str:
    return {"knockout": "KO", "double_ko": "DUPLO KO"}.get(motivo, "Decisao por HP")


def _evento_base(p1: str, p2: str, bruto: dict, fichas: dict, gerados: set,
                 cenario: str) -> dict:
    vencedor = bruto["vencedor"] or p1
    perdedor = p2 if vencedor == p1 else p1
    evento = {
        "p1": p1, "p2": p2,
        "p1_ficha": fichas.get(p1, {}), "p2_ficha": fichas.get(p2, {}),
        "vencedor": vencedor, "perdedor": perdedor,
        "vencedor_gerado": vencedor in gerados,
        "duracao": round(bruto["duracao"], 1),
        "motivo": bruto["motivo"],
        "ko_type": _ko_type(bruto["motivo"]),
        "hp_vencedor": round(bruto["hp_vencedor"]),
        "seed": bruto["seed"],
        "cenario": cenario,
    }
    for chave in ("clipes", "serie_hp", "serie_plano", "eventos_narrativos",
                  "eventos_dano", "ko_em_clipe", "duracao_clipe", "camera",
                  "metricas_video"):
        if bruto.get(chave) is not None:
            evento[chave] = bruto[chave]
    return evento


# ------------------------------------------------------------------ torneio
class TournamentSession:
    """Roda o torneio inteiro e devolve o JSON pronto para virar video."""

    def __init__(self, scoring: dict, alvo_gameplay: float = 10.0,
                 gameplay: dict | None = None):
        self.evaluator = RollEvaluator(scoring, {"compatibility": {}})
        self.drama = scoring.get("tournament_drama", {})
        self.alvo_gameplay = alvo_gameplay
        self.gameplay = {**GAMEPLAY_PADRAO, **(gameplay or {})}
        self._gravar_em: Path | None = None
        self._perfis: tuple[str, ...] = ("celular", "normal")

    # ------------------------------------------------------------------ dados
    def gerar(self, seed: int | None = None, fonte: str = "misto",
              quantidade: int = 8, nome: str = "Torneio Neural Fights",
              progresso=None, gravar_em: Path | None = None,
              perfis: tuple[str, ...] = ("celular", "normal")) -> dict:
        """Roda o torneio. Com `gravar_em`, cada luta e GRAVADA em video."""
        from neural_fights.tournament.tournament_mode import Tournament

        seed = seed if seed is not None else RandomEngine.new_seed()
        engine = RandomEngine(seed)
        rng = engine.fork("torneio:participantes")
        self._gravar_em = Path(gravar_em) if gravar_em else None
        self._perfis = tuple(perfis)
        self._rng_arena = engine.fork("torneio:arenas")

        participantes = selecionar_participantes(fonte, quantidade, rng)
        fichas = fichas_do_banco()

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
            bruto = gravar_confronto(p1, p2, cenario, base_seed,
                                     self._gravar_em / "gameplay",
                                     f"{match.match_id:02d}", self._perfis,
                                     gameplay=self.gameplay, origem="torneio")
        else:
            bruto = simular_luta(p1, p2, cenario, base_seed)

        evento = {
            "match_id": match.match_id,
            "rodada": match.round_num,
            "rodada_nome": self._nome_rodada(match.round_num, total_rodadas),
            **_evento_base(p1, p2, bruto, fichas, gerados, cenario),
        }
        evento.update(dramatizar(evento, fichas, self.drama))
        return self.evaluator.decorate(evento)

    @staticmethod
    def _nome_rodada(numero: int, total: int) -> str:
        faltam = total - numero
        return {1: "FINAL", 2: "SEMIFINAL", 3: "QUARTAS DE FINAL",
                4: "OITAVAS DE FINAL"}.get(faltam, f"RODADA {numero + 1}")

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


# --------------------------------------------------------------- luta unica
class FightSession:
    """Um confronto como video: estreia de um personagem, revanche, avulsa.

    Cada round devolve o mesmo formato de `luta` do torneio (o renderer e as
    legendas nao sabem a diferenca) embrulhado num JSON com `kind: "fight"`.
    Com `melhor_de > 1` o confronto vira uma SERIE e o JSON ganha `lutas`
    (um round por item) e `placar`; `luta` continua existindo e aponta para
    o round que fechou a serie, para quem so sabe ler uma luta.
    """

    def __init__(self, scoring: dict, gameplay: dict | None = None):
        self.evaluator = RollEvaluator(scoring, {"compatibility": {}})
        self.drama = scoring.get("tournament_drama", {})
        self.gameplay = {**GAMEPLAY_PADRAO, **(gameplay or {})}

    def gerar(self, *, p1: str, p2: str, seed: int | None = None,
              cenario: str | None = None, gravar_em: Path | None = None,
              perfis: tuple[str, ...] = ("celular", "normal"),
              origem: str = "luta", estreia_de: str | None = None,
              ledger=None, progresso=None, melhor_de: int = 1) -> dict:
        """Roda o confronto. `melhor_de` precisa ser impar.

        A serie para assim que alguem chega a `melhor_de // 2 + 1` vitorias:
        um 2 x 0 nao gasta gravacao com o terceiro round. Cada round e uma
        gravacao propria (seed derivada e prefixo distintos) na MESMA arena —
        e o mesmo confronto, nao tres lutas soltas.
        """
        if melhor_de < 1 or melhor_de % 2 == 0:
            raise ValueError(f"melhor_de precisa ser impar e >= 1: {melhor_de}")
        seed = seed if seed is not None else RandomEngine.new_seed()
        engine = RandomEngine(seed)
        # A estreia tem catalogo proprio (hoje igual ao de video) porque e o
        # formato de camera presa: se um dia so um subconjunto das verticais
        # servir para ela, muda aqui. Um `cenario` explicito continua mandando.
        catalogo = (ARENAS_DE_ESTREIA if origem == "estreia" else ARENAS_DE_VIDEO)
        cenario = cenario or engine.fork("luta:arena").choice(catalogo)
        fichas = fichas_do_banco()
        for nome in (p1, p2):
            if nome not in fichas:
                raise ValueError(f"personagem nao encontrado no banco: {nome}")
        gerados = set(personagens_gerados())
        # Carreira ANTES de registrar o confronto: o card mostra o cartel com
        # que cada um ENTROU na arena — o mesmo em todos os rounds da serie.
        carreira = self._carreira(p1, p2, ledger)

        precisa = melhor_de // 2 + 1
        placar = {p1: 0, p2: 0}
        rounds: list[dict] = []
        for indice in range(melhor_de):
            semente = seed + indice * 17
            if gravar_em:
                bruto = gravar_confronto(p1, p2, cenario, semente,
                                         Path(gravar_em) / "gameplay",
                                         f"{indice:02d}", tuple(perfis),
                                         gameplay=self.gameplay, origem=origem)
            else:
                bruto = simular_luta(p1, p2, cenario, semente)

            evento = {
                "match_id": indice, "rodada": indice,
                "rodada_nome": (f"ROUND {indice + 1}" if melhor_de > 1
                                else ("ESTREIA" if origem == "estreia" else "LUTA")),
                "origem": origem,
                **_evento_base(p1, p2, bruto, fichas, gerados, cenario),
                **carreira,
            }
            if estreia_de:
                evento["estreia_de"] = estreia_de
            if melhor_de > 1:
                evento["round"] = indice + 1
                evento["melhor_de"] = melhor_de
            evento.update(dramatizar(evento, fichas, self.drama))
            evento = self.evaluator.decorate(evento)
            placar[evento["vencedor"]] += 1
            if melhor_de > 1:
                # placar DEPOIS deste round: e o que a tela do round mostra.
                evento["placar"] = [placar[p1], placar[p2]]
            rounds.append(evento)
            if progresso:
                progresso(indice + 1, melhor_de, evento)
            if placar[evento["vencedor"]] >= precisa:
                break

        vencedor = p1 if placar[p1] >= placar[p2] else p2
        decisiva = rounds[-1]
        return {
            "seed": seed,
            "kind": "fight",
            "origem": origem,
            "estreia_de": estreia_de,
            "p1": p1, "p2": p2,
            "cenario": cenario,
            "melhor_de": melhor_de,
            "placar": [placar[p1], placar[p2]],
            "lutas": rounds,
            "luta": decisiva,
            "vencedor": vencedor,
            "vencedor_gerado": vencedor in gerados,
        }

    @staticmethod
    def _carreira(p1: str, p2: str, ledger) -> dict:
        """Cartel, revanche e titulo em jogo — o contexto que o card conta."""
        if ledger is None:
            return {}
        contexto = {
            "p1_cartel": ledger.cartel(p1),
            "p2_cartel": ledger.cartel(p2),
            "p1_recorde": ledger.recorde(p1),
            "p2_recorde": ledger.recorde(p2),
            "revanche": bool(ledger.confrontos(p1, p2)),
        }
        campeao = ledger.campeao_atual()
        contexto["titulo"] = bool(campeao and campeao in (p1, p2))
        if contexto["titulo"] and campeao == p2:
            # o campeao entra como P1 na narrativa ("X defende o titulo")
            contexto["campeao_em_jogo"] = campeao
        return contexto
