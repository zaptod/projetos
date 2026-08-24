#!/usr/bin/env python3
"""Harness de qualidade de luta.

Roda corpora deterministicos de lutas headless com a sonda
(``simulation.probes.FightQualityProbe``), agrega as metricas de ritmo, drama,
sistemas e "vida" da IA, e compara com os alvos versionados em
``neural_fights/data/alvos_qualidade.json``.

E o instrumento central do programa "lutas vivas": cada onda de mudanca no
combate re-fotografa o mesmo corpus e anexa o diff. Os alvos LIGAM por onda
(``--onda N`` habilita os que tem ``enforce_onda <= N``); antes disso sao
apenas reportados — medir sempre, cobrar quando a onda responsavel entregar.

Dois modos de dados:

``--dados engine`` (padrao)
    Fixture congelada em ``tests/fixtures/corpus_engine/``. Mudou a metrica?
    Foi o CODIGO. E o modo do CI.
``--dados roster``
    Catalogo vivo (empacotado/runtime). Mudou a metrica sem mudar codigo?
    Foi o DADO.
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from neural_fights.data import database
from neural_fights.models.characters import Personagem
from neural_fights.simulation.probes import FightQualityProbe, percentil
from neural_fights.utils.console import SafeArgumentParser, safe_print

RAIZ_CHECKOUT = Path(__file__).resolve().parents[2]
FIXTURE_ENGINE = RAIZ_CHECKOUT / "tests" / "fixtures" / "corpus_engine"
ARQUIVO_ALVOS = Path(__file__).resolve().parents[1] / "data" / "alvos_qualidade.json"

CENARIO_PADRAO = "Arena"
ARENAS_DO_CORPUS = ("Arena", "Arena Pequena", "Labirinto")
PRESETS_DO_CORPUS = ("Agressivo", "Defensivo", "Berserker", "Artista Marcial")


# ------------------------------------------------------------------- dados


class FonteDeDados:
    """Personagens e armas de um snapshot, com resolucao por nome.

    Materializa um ``Personagem`` NOVO a cada resolucao — o motor anota
    ``arma_obj`` no objeto, e reusar a mesma instancia entre lutas faria uma
    luta enxergar estado da anterior.
    """

    def __init__(self, modo: str) -> None:
        if modo == "engine":
            arquivo_armas = str(FIXTURE_ENGINE / "armas.json")
            arquivo_chars = str(FIXTURE_ENGINE / "personagens.json")
            if not (FIXTURE_ENGINE / "armas.json").is_file():
                raise FileNotFoundError(
                    f"fixture do corpus engine ausente em {FIXTURE_ENGINE}"
                )
            armas_raw, chars_raw = database.carregar_database(
                arquivo_armas=arquivo_armas,
                arquivo_personagens=arquivo_chars,
            )
            armas_obj = database.carregar_armas(
                arquivo_armas=arquivo_armas,
                arquivo_personagens=arquivo_chars,
            )
        else:
            armas_raw, chars_raw = database.carregar_database()
            armas_obj = database.carregar_armas()

        self.modo = modo
        self._armas = {arma.nome: arma for arma in armas_obj}
        self._chars = {item["nome"]: item for item in chars_raw}
        self.nomes = [item["nome"] for item in chars_raw]
        del armas_raw

    def classe_de(self, nome: str) -> str:
        return str(self._chars[nome].get("classe", ""))

    def tipo_arma_de(self, nome: str) -> str:
        arma = self._armas.get(self._chars[nome].get("nome_arma", ""))
        return str(getattr(arma, "tipo", "")) if arma is not None else ""

    def nomes_por_tipo(self) -> dict[str, list[str]]:
        grupos: dict[str, list[str]] = {}
        for nome in self.nomes:
            grupos.setdefault(self.tipo_arma_de(nome), []).append(nome)
        grupos.pop("", None)
        return grupos

    def provider(
        self, personalidade_override: dict[str, str] | None = None
    ) -> Callable[[str], Personagem]:
        overrides = dict(personalidade_override or {})

        def resolver(nome: str) -> Personagem:
            bruto = self._chars.get(nome)
            if bruto is None:
                raise ValueError(f"Personagem não encontrado na configuração: {nome}")
            arma = self._armas.get(bruto.get("nome_arma", ""))
            personagem = Personagem(
                bruto["nome"],
                bruto["tamanho"],
                bruto["forca"],
                bruto["mana"],
                bruto.get("nome_arma", ""),
                float(getattr(arma, "peso", 0.0)) if arma is not None else 0.0,
                bruto.get("cor_r", 200),
                bruto.get("cor_g", 50),
                bruto.get("cor_b", 50),
                bruto.get("classe", "Guerreiro (Força Bruta)"),
                overrides.get(nome, bruto.get("personalidade", "Aleatório")),
            )
            personagem.arma_obj = arma
            return personagem

        return resolver


# ------------------------------------------------------------------ corpora


def _pares(nomes: list[str], quantidade: int, semente: int) -> list[tuple[str, str]]:
    sorteio = random.Random(semente)
    return [tuple(sorteio.sample(nomes, 2)) for _ in range(quantidade)]


def corpus_smoke(fonte: FonteDeDados) -> list[dict[str, Any]]:
    """48 lutas espelhadas: rapido o bastante para o CI, honesto sobre lado."""
    lutas = []
    for indice, (a, b) in enumerate(_pares(fonte.nomes, 24, 42)):
        seed = 9000 + indice
        lutas.append({"p1": a, "p2": b, "seed": seed, "bloco": "espelho"})
        lutas.append({"p1": b, "p2": a, "seed": seed, "bloco": "espelho"})
    return lutas


def corpus_completo(fonte: FonteDeDados) -> list[dict[str, Any]]:
    lutas: list[dict[str, Any]] = []

    # Espelhos: base do vies de lado (B4).
    for indice, (a, b) in enumerate(_pares(fonte.nomes, 60, 21)):
        seed = 21000 + indice
        lutas.append({"p1": a, "p2": b, "seed": seed, "bloco": "espelho"})
        lutas.append({"p1": b, "p2": a, "seed": seed, "bloco": "espelho"})

    # Matriz 8x8 por tipo de arma (B2/B3).
    por_tipo = fonte.nomes_por_tipo()
    tipos = sorted(por_tipo)
    combo = 0
    for i, tipo_a in enumerate(tipos):
        for tipo_b in tipos[i:]:
            for k in range(4):
                sorteio = random.Random(9500 + combo * 10 + k)
                if tipo_a == tipo_b and len(por_tipo[tipo_a]) < 2:
                    continue
                if tipo_a == tipo_b:
                    a, b = sorteio.sample(por_tipo[tipo_a], 2)
                else:
                    a = sorteio.choice(por_tipo[tipo_a])
                    b = sorteio.choice(por_tipo[tipo_b])
                if k % 2:
                    a, b = b, a
                lutas.append(
                    {
                        "p1": a,
                        "p2": b,
                        "seed": 30000 + combo * 10 + k,
                        "bloco": "matriz",
                    }
                )
            combo += 1

    # Cobertura de classes (B1).
    for indice, (a, b) in enumerate(_pares(fonte.nomes, 150, 11)):
        lutas.append({"p1": a, "p2": b, "seed": 12000 + indice, "bloco": "classes"})

    # Arenas: mesmos pares/seeds em tres arenas.
    for indice, (a, b) in enumerate(_pares(fonte.nomes, 20, 31)):
        for cenario in ARENAS_DO_CORPUS:
            lutas.append(
                {
                    "p1": a,
                    "p2": b,
                    "seed": 31000 + indice,
                    "cenario": cenario,
                    "bloco": "arenas",
                }
            )

    # Divergencia entre presets (V3): mesmo par, personalidade do p1 trocada.
    from neural_fights.ai.personalities import PERSONALIDADES_PRESETS

    presets = [p for p in PRESETS_DO_CORPUS if p in PERSONALIDADES_PRESETS]
    # Onda 6 (primeira tarefa de harness): 24 -> 72 lutas em TRES pares.
    # Com um unico par, o estimador L1 da divergencia era coin-flip entre
    # builds (serie medida na O5: 0,311...0,610...0,324 — 2,4% de vida
    # balancava +-0,29). Tres matchups diversificam o histograma alem de
    # triplicar a amostra.
    pares = [
        (fonte.nomes[0], fonte.nomes[1]),
        (fonte.nomes[2], fonte.nomes[3]),
        (fonte.nomes[4], fonte.nomes[5]),
    ]
    for indice_par, par in enumerate(pares):
        for preset in presets:
            for k in range(6):
                lutas.append(
                    {
                        "p1": par[0],
                        "p2": par[1],
                        "seed": 32000 + indice_par * 100 + k,
                        "bloco": "presets",
                        "preset_p1": preset,
                    }
                )
    return lutas


# ----------------------------------------------------------------- execucao


def executar_luta(spec: dict[str, Any], fonte: FonteDeDados) -> dict[str, Any]:
    from neural_fights.simulation.headless import HeadlessMatchRunner

    overrides = {spec["p1"]: spec["preset_p1"]} if spec.get("preset_p1") else None
    probe = FightQualityProbe()
    resultado = HeadlessMatchRunner(
        {
            "p1_nome": spec["p1"],
            "p2_nome": spec["p2"],
            "cenario": spec.get("cenario", CENARIO_PADRAO),
            "best_of": 1,
        },
        seed=spec["seed"],
        max_duration=120.0,
        probe=probe,
        roster_provider=fonte.provider(overrides),
    ).run()

    luta: dict[str, Any] = {
        "spec": {k: v for k, v in spec.items()},
        "success": resultado.success,
        "error": resultado.error,
    }
    if resultado.success:
        luta.update(probe.metricas(resultado))
        luta["classe_p1"] = fonte.classe_de(spec["p1"])
        luta["classe_p2"] = fonte.classe_de(spec["p2"])
        luta["tipo_p1"] = fonte.tipo_arma_de(spec["p1"])
        luta["tipo_p2"] = fonte.tipo_arma_de(spec["p2"])
    return luta


def rodar_corpus(
    lutas: Iterable[dict[str, Any]],
    fonte: FonteDeDados,
    *,
    progresso: bool = False,
) -> list[dict[str, Any]]:
    saida = []
    lutas = list(lutas)
    inicio = time.perf_counter()
    for indice, spec in enumerate(lutas, 1):
        saida.append(executar_luta(spec, fonte))
        if progresso and indice % 50 == 0:
            decorrido = time.perf_counter() - inicio
            safe_print(f"  {indice}/{len(lutas)} lutas ({decorrido:.0f}s)")
    return saida


# ---------------------------------------------------------------- agregacao


def _media(valores: list[float]) -> float | None:
    dados = [v for v in valores if v is not None]
    return sum(dados) / len(dados) if dados else None


def _winrates_por_rotulo(lutas, chave_p1, chave_p2) -> dict[str, dict[str, int]]:
    quadro: dict[str, dict[str, int]] = {}
    for luta in lutas:
        vencedor = luta.get("vencedor_slot")
        if vencedor is None:
            continue
        for slot, chave in (("p1", chave_p1), ("p2", chave_p2)):
            rotulo = luta.get(chave)
            if not rotulo:
                continue
            registro = quadro.setdefault(rotulo, {"lutas": 0, "vitorias": 0})
            registro["lutas"] += 1
            if vencedor == slot:
                registro["vitorias"] += 1
    return quadro


def _extremos_de_winrate(quadro, minimo_lutas: int = 8):
    taxas = [
        registro["vitorias"] / registro["lutas"]
        for registro in quadro.values()
        if registro["lutas"] >= minimo_lutas
    ]
    if not taxas:
        return None, None
    return min(taxas), max(taxas)


def _divergencia_presets(lutas) -> float | None:
    """L1 entre os histogramas de acao do lutador com preset trocado."""
    por_preset: dict[str, dict[str, float]] = {}
    contagem: dict[str, int] = {}
    for luta in lutas:
        preset = luta["spec"].get("preset_p1")
        historico = luta.get("acoes_pct_p1") or {}
        if not preset or not historico:
            continue
        acumulado = por_preset.setdefault(preset, {})
        for acao, fracao in historico.items():
            acumulado[acao] = acumulado.get(acao, 0.0) + fracao
        contagem[preset] = contagem.get(preset, 0) + 1

    medias = {
        preset: {acao: total / contagem[preset] for acao, total in histograma.items()}
        for preset, histograma in por_preset.items()
    }
    if "Agressivo" not in medias or "Defensivo" not in medias:
        return None
    a, d = medias["Agressivo"], medias["Defensivo"]
    return sum(abs(a.get(acao, 0.0) - d.get(acao, 0.0)) for acao in set(a) | set(d))


def _razao_duracao_matriz(lutas) -> float | None:
    celulas: dict[tuple[str, str], list[float]] = {}
    for luta in lutas:
        if luta["spec"].get("bloco") != "matriz":
            continue
        chave = tuple(sorted((luta.get("tipo_p1", ""), luta.get("tipo_p2", ""))))
        celulas.setdefault(chave, []).append(luta["duracao"])
    medianas = [
        percentil(duracoes, 0.5) for duracoes in celulas.values() if len(duracoes) >= 3
    ]
    medianas = [m for m in medianas if m]
    if len(medianas) < 2:
        return None
    return max(medianas) / min(medianas)


def agregar(lutas: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [luta for luta in lutas if luta.get("success")]
    falhas = [luta for luta in lutas if not luta.get("success")]

    duracoes = [luta["duracao"] for luta in ok]
    com_vencedor = [luta for luta in ok if luta.get("vencedor_slot")]
    espelhos = [
        luta
        for luta in com_vencedor
        if luta["spec"].get("bloco") == "espelho"
    ]

    resumo: dict[str, Any] = {
        "lutas": len(lutas),
        "lutas_ok": len(ok),
        "falhas": len(falhas),
        "duracao_p50": percentil(duracoes, 0.5),
        "duracao_p90": percentil(duracoes, 0.9),
        "pct_sob_5s": (
            sum(1 for d in duracoes if d < 5.0) / len(duracoes) if duracoes else None
        ),
        "pct_timeout": (
            sum(1 for luta in ok if luta["reason"].startswith("time_limit")) / len(ok)
            if ok
            else None
        ),
        "pct_ko": (
            sum(1 for luta in ok if luta["reason"] in ("knockout", "double_ko"))
            / len(ok)
            if ok
            else None
        ),
        "primeiro_hit_p50": percentil(
            [luta["primeiro_hit_t"] for luta in ok], 0.5
        ),
        # Onda 5C: uniao de humores do corpus e media da saturacao.
        "humores_distintos_corpus": len(
            set().union(*[set(luta.get("humores_vistos", [])) for luta in ok])
        ) if ok else None,
        "pct_momentum_saturado_media": (
            sum(luta.get("pct_momentum_saturado", 0.0) for luta in ok) / len(ok)
        ) if ok else None,
        "pct_vencedor_acima_80": (
            sum(1 for luta in com_vencedor if luta["hp_final_vencedor"] > 0.8)
            / len(com_vencedor)
            if com_vencedor
            else None
        ),
        "pct_vencedor_abaixo_30": (
            sum(1 for luta in com_vencedor if luta["hp_final_vencedor"] < 0.3)
            / len(com_vencedor)
            if com_vencedor
            else None
        ),
        "pct_com_lead_change": (
            sum(1 for luta in ok if luta["lead_changes"] >= 1) / len(ok)
            if ok
            else None
        ),
        "pct_comeback_25pp": (
            sum(
                1
                for luta in com_vencedor
                if (luta.get("max_deficit_vencedor") or 0.0) >= 0.25
            )
            / len(com_vencedor)
            if com_vencedor
            else None
        ),
        "maior_seca_p90": percentil([luta["maior_seca"] for luta in ok], 0.9),
        "cv_intervalos_p50": percentil(
            [luta["cv_intervalos"] for luta in ok], 0.5
        ),
        "taxa_anulacao_iframes_media": _media(
            [luta["taxa_anulacao_iframes"] for luta in ok]
        ),
        "skills_por_luta_p50": percentil(
            [float(luta["skills_lancadas"]) for luta in ok], 0.5
        ),
        "taxa_pilha_media": _media([luta["taxa_pilha"] for luta in ok]),
        "acao_mediana_ms_p50": percentil(
            [luta["acao_mediana_ms"] for luta in ok], 0.5
        ),
        "pct_trocas_curtas_media": _media(
            [luta["pct_trocas_curtas"] for luta in ok]
        ),
        "winrate_p1": (
            sum(1 for luta in espelhos if luta["vencedor_slot"] == "p1")
            / len(espelhos)
            if espelhos
            else None
        ),
        "lutas_espelho": len(espelhos),
    }

    # Taxa de critico agregada por golpe, nao por luta.
    golpes = sum(luta["golpes_melee"] for luta in ok)
    criticos = sum(luta["criticos_melee"] for luta in ok)
    resumo["taxa_critico_global"] = (criticos / golpes) if golpes else None
    absorcoes = sum(luta["super_armor_absorcoes"] for luta in ok)
    resumo["taxa_super_armor"] = (absorcoes / golpes) if golpes else None

    # Origem do dano.
    total_dano = sum(luta["dano_total"] for luta in ok)
    if total_dano:
        for grupo in ("basico", "skill", "dot_encanto"):
            resumo[f"share_dano_{grupo if grupo != 'dot_encanto' else 'dot'}"] = (
                sum(luta["dano_por_grupo"][grupo] for luta in ok) / total_dano
            )

    # Balance por rotulo.
    quadro_classes = _winrates_por_rotulo(com_vencedor, "classe_p1", "classe_p2")
    quadro_tipos = _winrates_por_rotulo(com_vencedor, "tipo_p1", "tipo_p2")
    resumo["winrate_classe_min"], resumo["winrate_classe_max"] = _extremos_de_winrate(
        quadro_classes, minimo_lutas=10
    )
    resumo["winrate_tipo_min"], resumo["winrate_tipo_max"] = _extremos_de_winrate(
        quadro_tipos, minimo_lutas=12
    )
    resumo["divergencia_presets_l1"] = _divergencia_presets(ok)
    resumo["razao_duracao_celulas"] = _razao_duracao_matriz(ok)

    resumo["_quadros"] = {
        "classes": quadro_classes,
        "tipos": quadro_tipos,
    }
    return resumo


# --------------------------------------------------------------- avaliacao


def carregar_alvos() -> dict[str, Any]:
    dados = json.loads(ARQUIVO_ALVOS.read_text(encoding="utf-8"))
    dados.pop("_doc", None)
    return dados


def avaliar(
    resumo: dict[str, Any], alvos: dict[str, Any], onda: int
) -> list[dict[str, Any]]:
    saida = []
    for nome, alvo in sorted(alvos.items()):
        valor = resumo.get(alvo["metrica"])
        enforced = int(alvo.get("enforce_onda", 99)) <= onda
        minimo_lutas = int(alvo.get("min_lutas", 0))

        if valor is None:
            status = "sem_dados"
        elif resumo.get("lutas_ok", 0) < minimo_lutas:
            status = "amostra_insuficiente"
        else:
            dentro = True
            if "min" in alvo and valor < alvo["min"]:
                dentro = False
            if "max" in alvo and valor > alvo["max"]:
                dentro = False
            if dentro:
                status = "ok"
            else:
                status = "violado" if enforced else "fora_da_faixa"

        saida.append(
            {
                "alvo": nome,
                "metrica": alvo["metrica"],
                "valor": valor,
                "faixa": {
                    k: alvo[k] for k in ("min", "max") if k in alvo
                },
                "enforced": enforced,
                "status": status,
            }
        )
    return saida


# ------------------------------------------------------------------ saida


def _formatar_valor(valor: Any) -> str:
    if valor is None:
        return "-"
    if isinstance(valor, float):
        return f"{valor:.3f}"
    return str(valor)


def imprimir_relatorio(resumo, avaliacoes) -> None:
    safe_print(f"lutas: {resumo['lutas_ok']}/{resumo['lutas']} ok")
    safe_print("")
    safe_print("== resumo ==")
    for chave in sorted(resumo):
        if chave.startswith("_") or chave in ("lutas", "lutas_ok", "falhas"):
            continue
        safe_print(f"  {chave:32} {_formatar_valor(resumo[chave])}")
    safe_print("")
    safe_print("== alvos ==")
    for item in avaliacoes:
        faixa = item["faixa"]
        faixa_txt = "/".join(
            f"{k}={faixa[k]}" for k in ("min", "max") if k in faixa
        )
        marcador = {
            "ok": "OK ",
            "violado": "ERRO",
            "fora_da_faixa": "info",
            "sem_dados": "s/d ",
            "amostra_insuficiente": "n<  ",
        }[item["status"]]
        safe_print(
            f"  [{marcador}] {item['alvo']:28} {item['metrica']:30} "
            f"valor={_formatar_valor(item['valor'])} ({faixa_txt})"
        )


def dump_timeline(args, fonte: FonteDeDados) -> int:
    from neural_fights.simulation.headless import HeadlessMatchRunner

    probe = FightQualityProbe()
    resultado = HeadlessMatchRunner(
        {
            "p1_nome": args.p1,
            "p2_nome": args.p2,
            "cenario": args.cenario,
            "best_of": 1,
        },
        seed=args.dump_timeline,
        max_duration=120.0,
        probe=probe,
        roster_provider=fonte.provider(),
    ).run()

    safe_print(f"{args.p1} vs {args.p2} | seed {args.dump_timeline} | {args.cenario}")
    safe_print(
        f"resultado: {resultado.reason} vencedor={resultado.winner or 'EMPATE'} "
        f"em {resultado.duration:.2f}s"
    )
    safe_print("")
    safe_print("t(s)   quem   dano    fonte")
    for t, slot, dano, categoria in probe._eventos:
        safe_print(f"{t:6.2f} {slot:4} {dano:7.1f}  {categoria}")
    safe_print("")
    metricas = probe.metricas(resultado)
    for chave in (
        "lead_changes",
        "hp_final_vencedor",
        "maior_seca",
        "taxa_critico",
        "skills_lancadas",
        "taxa_pilha",
        "acao_mediana_ms",
    ):
        safe_print(f"{chave:22} {_formatar_valor(metricas.get(chave))}")
    return 0


# -------------------------------------------------------------------- CLI


def build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(
        description="Harness de qualidade de luta (metricas de drama e alvos por onda)"
    )
    parser.add_argument("--corpus", choices=("smoke", "completo"), default="smoke")
    parser.add_argument(
        "--dados",
        choices=("engine", "roster"),
        default="engine",
        help="engine = fixture congelada (CI); roster = catalogo vivo",
    )
    parser.add_argument(
        "--onda",
        type=int,
        default=0,
        help="habilita os alvos com enforce_onda <= N",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="metricas fora de faixa ainda nao habilitadas tambem bloqueiam (exit 2)",
    )
    parser.add_argument("--out", help="grava o relatorio completo em JSON")
    parser.add_argument("--progresso", action="store_true")
    parser.add_argument(
        "--vfx",
        action="store_true",
        help="mede o volume visual (objetos de VFX por frame) e avalia os alvos de limpeza da luta",
    )
    parser.add_argument(
        "--dump-timeline",
        type=int,
        metavar="SEED",
        help="imprime a linha do tempo de uma unica luta (requer --p1/--p2)",
    )
    parser.add_argument("--p1")
    parser.add_argument("--p2")
    parser.add_argument("--cenario", default=CENARIO_PADRAO)
    return parser


def medir_vfx(fonte: FonteDeDados, pares: int = 3, segundos: float = 25.0
              ) -> dict[str, Any]:
    """Mede o VOLUME VISUAL da luta (reforma "luta limpa").

    O corpus normal roda headless — e o Simulador pula todo o VFX nesse
    modo. Este passe roda partidas COM render (SDL dummy) e conta os
    objetos vivos por frame, com a mesma sonda usada na reforma.
    """
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from neural_fights.simulation.simulacao import Simulador
    from neural_fights.simulation.vfx_probe import VFXCountProbe

    nomes = list(fonte.nomes)
    casters = [n for n in nomes if fonte.classe_de(n) and any(
        c in fonte.classe_de(n)
        for c in ("Mago", "Piromante", "Necromante", "Feiticeiro", "Criomante")
    )]
    melee = [n for n in nomes if n not in casters]
    duplas = []
    if len(casters) >= 2:
        duplas.append((casters[0], casters[1]))     # magia pesada
    if len(melee) >= 2:
        duplas.append((melee[0], melee[1]))         # corpo a corpo
    if casters and melee:
        duplas.append((casters[-1], melee[-1]))     # misto
    duplas = duplas[:pares] or [(nomes[0], nomes[1])]

    probe = VFXCountProbe()
    for p1, p2 in duplas:
        sim = Simulador(
            match_config={
                "p1_nome": p1, "p2_nome": p2,
                "cenario": CENARIO_PADRAO, "best_of": 1,
            },
            # mesmo roster do corpus (a fixture congelada em --dados engine)
            roster_provider=fonte.provider(None),
        )
        try:
            t = 0.0
            while sim.rodando and t < segundos:
                dt = 1 / 60
                t += dt
                sim.processar_inputs()
                sim.avancar_relogio(dt)
                sim.update(dt)
                sim.desenhar()
                probe.amostrar(sim)
                if getattr(sim, "round_finalizado", False):
                    break
        finally:
            sim.close()
    return probe.resumo()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fonte = FonteDeDados(args.dados)

    if args.dump_timeline is not None:
        if not args.p1 or not args.p2:
            safe_print("Erro: --dump-timeline exige --p1 e --p2", file=sys.stderr)
            return 2
        return dump_timeline(args, fonte)

    specs = corpus_smoke(fonte) if args.corpus == "smoke" else corpus_completo(fonte)
    inicio = time.perf_counter()
    lutas = rodar_corpus(specs, fonte, progresso=args.progresso)
    duracao_execucao = time.perf_counter() - inicio

    resumo = agregar(lutas)
    if args.vfx:
        # Passe visual: o corpus roda headless e não gera VFX nenhum.
        vfx = medir_vfx(fonte)
        resumo.update(vfx)
    avaliacoes = avaliar(resumo, carregar_alvos(), args.onda)
    imprimir_relatorio(resumo, avaliacoes)
    safe_print("")
    safe_print(f"execucao: {duracao_execucao:.0f}s | corpus={args.corpus} dados={fonte.modo} onda={args.onda}")

    if args.out:
        relatorio = {
            "config": {
                "corpus": args.corpus,
                "dados": fonte.modo,
                "onda": args.onda,
            },
            "resumo": {k: v for k, v in resumo.items() if not k.startswith("_")},
            "quadros": resumo.get("_quadros", {}),
            "alvos": avaliacoes,
            "lutas": [
                {
                    "spec": luta["spec"],
                    "duracao": luta.get("duracao"),
                    "vencedor_slot": luta.get("vencedor_slot"),
                    "reason": luta.get("reason"),
                    "error": luta.get("error"),
                }
                for luta in lutas
            ],
        }
        Path(args.out).write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        safe_print(f"relatorio: {args.out}")

    if resumo["falhas"]:
        safe_print(f"ERRO: {resumo['falhas']} luta(s) falharam", file=sys.stderr)
        return 1
    if any(item["status"] == "violado" for item in avaliacoes):
        return 1
    if args.strict and any(
        item["status"] == "fora_da_faixa" for item in avaliacoes
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
