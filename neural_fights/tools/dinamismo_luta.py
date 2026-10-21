# -*- coding: utf-8 -*-
"""Medidor de DINAMISMO da luta: quanto tempo os corpos ficam colados.

Pedido do Adrian (21/10/2026): "não quero os personagens colados um no
outro muito tempo; quero movimento e dinamismo nas lutas". Esta sonda só
LÊ o estado do Simulador a cada passo (headless, 60 Hz) e mede:

- ``pct_colado``: fração da luta com os corpos DESENHADOS a menos de ``X``
  de borda a borda, ``X = COLADO_FRACAO_RAIO × raio desenhado médio``. O
  raio que o vídeo desenha é ``tamanho / 2`` (≈ 0,9 m) e o da física é
  ``tamanho / 4`` (``raio_fisico``): a física deixa os discos desenhados se
  sobreporem até a metade, e é isso que o Adrian vê como "colado". Medido
  pelo raio da física (0,5 raio ≈ 0,22 m), o pior trecho do lote era 1,9 s;
  pelo desenhado, 9 s (``docs/sessoes/builds.md`` §14);
- ``pct_sobreposto``: os discos desenhados se cobrindo (borda < 0);
- ``maior_colado_s``: o maior trecho contínuo colado (buracos menores que
  ``COLADO_EMENDA_S`` não quebram o trecho: o olho não vê 0,1 s de folga);
- ``trechos_2s``: trechos colados com mais de 2 s;
- agarrões, clinches e enlaces (``contadores_luta`` do motor);
- velocidade média (m/s, pela posição de verdade) e % do tempo parado
  (velocidade suavizada < ``PARADO_MS``);
- aproximações e afastamentos (histerese: colado ↔ mais de
  ``LONGE_FRACAO_RAIO`` raio desenhado de borda a borda);
- duração, vencedor, classe e tipo de arma de cada lado.

Nada aqui muda a luta: a sonda não escreve no Simulador nem sorteia.

Uso (de ``<repo>``; com ``NEURAL_FIGHTS_RUNTIME_DIR`` numa cópia do banco)::

    python -m neural_fights.tools.dinamismo_luta lote.json --saida medida.json

``lote.json`` é uma lista de ``{"p1", "p2", "seed", "cenario"}``.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

COLADO_FRACAO_RAIO = 0.5
COLADO_EMENDA_S = 0.25
LONGE_FRACAO_RAIO = 1.0
PARADO_MS = 0.3
PARADO_TAU_S = 0.2
PAREDE_M = 0.35


def raio_desenhado(lutador) -> float:
    """O raio do disco que o vídeo desenha (``Simulador.desenhar_lutador``:
    ``tamanho / 2``), em metros; sem ``dados``, o dobro do da física."""
    try:
        return float(lutador.dados.tamanho) / 2.0
    except (AttributeError, TypeError, ValueError):
        return 2.0 * float(getattr(lutador, "raio_fisico", 0.45) or 0.45)


def _em_hitstop(sim) -> bool:
    """O passo foi a pausinha do impacto (decisão ``hitstop``): a imagem
    para, os corpos ficam onde estavam."""
    hs = getattr(getattr(sim, "game_feel", None), "hit_stop", None)
    try:
        return float(getattr(hs, "timer_ativo", 0.0) or 0.0) > 0.0
    except (TypeError, ValueError):
        return False


class SondaDinamismo:
    """Coleta por passo; ``metricas()`` fecha o relatório da luta."""

    def __init__(self) -> None:
        self.t = 0.0
        self.frames = 0
        self._colado: list[bool] = []
        self._sobreposto = 0
        self._detalhe: list[tuple] = []
        self._vel_soma = 0.0
        self._vel_n = 0
        self._parado = 0
        self._parado_n = 0
        self._ema = {"p1": None, "p2": None}
        self._pos_ant = {}
        self._estado_dist = None
        self.aproximacoes = 0
        self.afastamentos = 0
        # golpes (o mesmo registro do gravador: SondaDeDano) e a vida a 10 Hz
        self.eventos: list[tuple[float, str, float]] = []
        self.serie_hp: list[tuple[float, float, float]] = []
        self._registros: dict[str, list] = {}
        self._dist: list[float] = []

    def on_inicio(self, sim) -> None:
        self._sim = sim
        for slot in ("p1", "p2"):
            lutador = getattr(sim, slot)
            self._pos_ant[slot] = (float(lutador.pos[0]), float(lutador.pos[1]))
            lista: list = []
            lutador.registro_eventos_dano = lista
            self._registros[slot] = lista

    def _drenar(self, sim) -> None:
        for slot in ("p1", "p2"):
            lista = self._registros.get(slot)
            if lista:
                for dano, _categoria in lista:
                    self.eventos.append((round(self.t, 3), slot, float(dano)))
                lista.clear()

    @staticmethod
    def _na_parede(arena, lutador) -> bool:
        if arena is None:
            return False
        r = float(getattr(lutador, "raio_fisico", 0.45) or 0.45)
        x, y = float(lutador.pos[0]), float(lutador.pos[1])
        return (
            x - r - getattr(arena, "min_x", 0.0) < PAREDE_M
            or getattr(arena, "max_x", 1e9) - (x + r) < PAREDE_M
            or y - r - getattr(arena, "min_y", 0.0) < PAREDE_M
            or getattr(arena, "max_y", 1e9) - (y + r) < PAREDE_M
        )

    def on_frame(self, sim, dt: float) -> None:
        p1, p2 = sim.p1, sim.p2
        if getattr(sim, "round_finalizado", False) or p1.morto or p2.morto:
            self._drenar(sim)   # o golpe do K.O.
            return
        self.t += dt
        self.frames += 1
        self._drenar(sim)
        if self.frames % 6 == 1:
            self.serie_hp.append((round(self.t, 2),
                                  round(100 * float(p1.vida) / max(1e-9, float(p1.vida_max)), 1),
                                  round(100 * float(p2.vida) / max(1e-9, float(p2.vida_max)), 1)))
        r1 = raio_desenhado(p1)
        r2 = raio_desenhado(p2)
        # o disco de quem pula/voa e desenhado ``z`` acima do chao (off_y)
        dist = math.hypot(p2.pos[0] - p1.pos[0],
                          (p2.pos[1] - float(p2.z or 0.0)) - (p1.pos[1] - float(p1.z or 0.0)))
        self._dist.append(dist)
        borda = dist - (r1 + r2)
        limite = COLADO_FRACAO_RAIO * (r1 + r2) / 2.0
        colado = borda < limite
        self._colado.append(colado)
        self._sobreposto += 1 if borda < 0.0 else 0

        if colado:
            if self._estado_dist == "longe":
                self.aproximacoes += 1
            self._estado_dist = "perto"
        elif borda > LONGE_FRACAO_RAIO * (r1 + r2) / 2.0:
            if self._estado_dist == "perto":
                self.afastamentos += 1
            self._estado_dist = "longe"

        alpha = min(1.0, dt / PARADO_TAU_S)
        for slot, lutador in (("p1", p1), ("p2", p2)):
            x, y = float(lutador.pos[0]), float(lutador.pos[1])
            ax, ay = self._pos_ant[slot]
            v = math.hypot(x - ax, y - ay) / max(dt, 1e-9)
            self._pos_ant[slot] = (x, y)
            ema = self._ema[slot]
            ema = v if ema is None else ema + (v - ema) * alpha
            self._ema[slot] = ema
            self._vel_soma += v
            self._vel_n += 1
            self._parado += 1 if ema < PARADO_MS else 0
            self._parado_n += 1

        arena = getattr(sim, "arena", None)
        b1 = getattr(p1, "brain", None)
        b2 = getattr(p2, "brain", None)
        self._detalhe.append((
            bool(sim.__dict__.get("_agarrao") is not None
                 or getattr(p1, "agarrao_timer", 0.0) > 0.0
                 or getattr(p2, "agarrao_timer", 0.0) > 0.0),
            self._na_parede(arena, p1) or self._na_parede(arena, p2),
            str(getattr(b1, "acao_atual", "") or ""),
            str(getattr(b2, "acao_atual", "") or ""),
            int(p1.contadores_luta.get("hits_sofridos", 0)
                + p2.contadores_luta.get("hits_sofridos", 0)),
            bool(getattr(p1, "atacando", False) or getattr(p2, "atacando", False)),
            _em_hitstop(sim),
        ))

    def trechos(self, dt: float) -> list[tuple[int, int]]:
        """(início, fim) em passos dos trechos colados, já emendados."""
        emenda = max(0, int(round(COLADO_EMENDA_S / dt)))
        brutos = []
        inicio = None
        for i, c in enumerate(self._colado):
            if c and inicio is None:
                inicio = i
            elif not c and inicio is not None:
                brutos.append((inicio, i))
                inicio = None
        if inicio is not None:
            brutos.append((inicio, len(self._colado)))
        emendados: list[list[int]] = []
        for ini, fim in brutos:
            if emendados and ini - emendados[-1][1] < emenda:
                emendados[-1][1] = fim
            else:
                emendados.append([ini, fim])
        return [(a, b) for a, b in emendados]

    def metricas(self, dt: float = 1.0 / 60.0) -> dict:
        n = max(1, len(self._colado))
        trechos = self.trechos(dt)
        duracoes = [(b - a) * dt for a, b in trechos]
        maior = max(duracoes, default=0.0)
        longos = []
        for (a, b), dur in zip(trechos, duracoes):
            if dur < 1.5:
                continue
            fatia = self._detalhe[a:b]
            acoes = Counter()
            for d in fatia:
                acoes[d[2]] += 1
                acoes[d[3]] += 1
            longos.append({
                "inicio_s": round(a * dt, 2),
                "dur_s": round(dur, 2),
                "agarrao_frac": round(sum(d[0] for d in fatia) / max(1, len(fatia)), 2),
                "parede_frac": round(sum(d[1] for d in fatia) / max(1, len(fatia)), 2),
                "atacando_frac": round(sum(d[5] for d in fatia) / max(1, len(fatia)), 2),
                "hits": (fatia[-1][4] - fatia[0][4]) if fatia else 0,
                "acoes": dict(acoes.most_common(5)),
            })
        colado_n = sum(self._colado)
        parede_colado = sum(1 for c, d in zip(self._colado, self._detalhe) if c and d[1])
        agarrao_colado = sum(1 for c, d in zip(self._colado, self._detalhe) if c and d[0])
        hitstop_colado = sum(1 for c, d in zip(self._colado, self._detalhe) if c and d[6])
        # golpes: por segundo de luta, os de 10+ de dano (o que o olho conta
        # como impacto) e o maior trecho sem golpe (do início ao K.O.)
        tempos = sorted(t for t, _s, d in self.eventos if d > 0.0)
        marcos = [0.0, *tempos, self.t]
        sem_golpe = max((b - a for a, b in zip(marcos, marcos[1:])), default=self.t)
        dists = sorted(self._dist)
        return {
            "frames": len(self._colado),
            "golpes": len(tempos),
            "golpes_10": sum(1 for _t, _s, d in self.eventos if d >= 10.0),
            "golpes_por_s": round(len(tempos) / max(self.t, 1e-9), 3),
            "maior_sem_golpe_s": round(sem_golpe, 2),
            "dist_centros_p50_m": round(dists[len(dists) // 2], 3) if dists else 0.0,
            "eventos": self.eventos,
            "serie_hp": self.serie_hp,
            "pct_colado": round(colado_n / n, 4),
            "pct_sobreposto": round(self._sobreposto / n, 4),
            "maior_colado_s": round(maior, 2),
            "trechos_colados": len(trechos),
            "trechos_2s": sum(1 for d in duracoes if d > 2.0),
            # tempo colado por tamanho de trecho (s): de onde vem o total
            "colado_por_trecho_s": {
                faixa: round(sum(d for d in duracoes if lo <= d < hi), 2)
                for faixa, lo, hi in (("<0,5", 0.0, 0.5), ("0,5-1", 0.5, 1.0),
                                      ("1-2", 1.0, 2.0), (">2", 2.0, 1e9))
            },
            "colado_na_parede_frac": round(parede_colado / max(1, colado_n), 3),
            "colado_em_agarrao_frac": round(agarrao_colado / max(1, colado_n), 3),
            "colado_em_hitstop_frac": round(hitstop_colado / max(1, colado_n), 3),
            "vel_media_ms": round(self._vel_soma / max(1, self._vel_n), 3),
            "pct_parado": round(self._parado / max(1, self._parado_n), 4),
            "aproximacoes": self.aproximacoes,
            "afastamentos": self.afastamentos,
            "longos": longos,
        }


def _classe(lutador) -> str:
    return str(getattr(lutador, "classe_nome", "") or "").split(" (")[0]


def _tipo_arma(lutador) -> str:
    arma = getattr(getattr(lutador, "dados", None), "arma_obj", None)
    return str(getattr(arma, "tipo", "") or "")


def medir_luta(p1: str, p2: str, seed: int, cenario: str,
               corrente_v2: bool = False, max_duracao: float = 120.0,
               extra_config: dict | None = None, roster_provider=None) -> dict:
    """Uma luta headless com a sonda; devolve resultado + métricas.

    ``roster_provider`` (o de ``qualidade_luta.FonteDeDados``) troca o banco
    vivo por um snapshot — é como o teste roda sem o banco do Adrian."""
    from neural_fights.simulation.headless import HeadlessMatchRunner

    sonda = SondaDinamismo()
    info: dict = {}

    class _Sonda:
        def on_inicio(self, sim):
            sonda.on_inicio(sim)
            info["classe"] = {"p1": _classe(sim.p1), "p2": _classe(sim.p2)}
            info["arma"] = {"p1": _tipo_arma(sim.p1), "p2": _tipo_arma(sim.p2)}

        def on_frame(self, sim, dt):
            sonda.on_frame(sim, dt)
            info["contadores"] = (sim.p1.contadores_luta, sim.p2.contadores_luta)

    config = {"p1_nome": p1, "p2_nome": p2, "cenario": cenario,
              "best_of": 1, "portrait_mode": False,
              "corrente_v2": bool(corrente_v2), **(extra_config or {})}
    res = HeadlessMatchRunner(config, fixed_dt=1 / 60, max_duration=max_duracao,
                              seed=int(seed), probe=_Sonda(),
                              roster_provider=roster_provider).run()
    c1, c2 = info.get("contadores", ({}, {}))
    soma = lambda chave: int(c1.get(chave, 0) or 0) + int(c2.get(chave, 0) or 0)  # noqa: E731
    vencedor_slot = res.winner_slot
    return {
        "p1": p1, "p2": p2, "seed": int(seed), "cenario": cenario,
        "sucesso": res.success, "erro": res.error,
        "vencedor": res.winner, "vencedor_slot": vencedor_slot,
        "motivo": res.reason, "duracao": round(res.duration, 3),
        "hp": [round(res.p1_hp_ratio, 4), round(res.p2_hp_ratio, 4)],
        "classe": info.get("classe", {}), "arma": info.get("arma", {}),
        "agarroes": soma("agarroes"), "clinches": soma("clinches"),
        "enlaces": soma("enlaces"), "respiros": soma("respiros"),
        "choques": soma("choques"),
        "hits": soma("hits_sofridos"),
        **sonda.metricas(),
    }


def _medir_item(item: dict) -> dict:
    try:
        extra = {"dinamismo": bool(item["dinamismo"])} if "dinamismo" in item else None
        provedor = None
        if item.get("dados") == "engine":
            # o corpus do harness de qualidade (fixture engine, 64 fichas)
            from neural_fights.tools.qualidade_luta import FonteDeDados

            overrides = {item["p1"]: item["preset_p1"]} if item.get("preset_p1") else None
            provedor = FonteDeDados("engine").provider(overrides)
        return medir_luta(item["p1"], item["p2"], int(item["seed"]), item["cenario"],
                          corrente_v2=bool(item.get("corrente_v2", False)),
                          extra_config=extra, roster_provider=provedor)
    except Exception as erro:  # a medida de uma luta nunca derruba o lote
        return {**item, "sucesso": False, "erro": f"{type(erro).__name__}: {erro}"}


def medir_lote(itens: list[dict], trabalhadores: int = 3) -> list[dict]:
    """Um processo por luta (como o gravador): o animador de arma é por processo."""
    with ProcessPoolExecutor(max_workers=max(1, trabalhadores),
                             max_tasks_per_child=1) as pool:
        return list(pool.map(_medir_item, itens))


def resumo(medidas: list[dict]) -> dict:
    ok = [m for m in medidas if m.get("sucesso")]
    if not ok:
        return {"n": 0}

    def med(chave):
        return round(statistics.median(m[chave] for m in ok), 3)

    def media(chave):
        return round(statistics.fmean(m[chave] for m in ok), 3)

    duracoes = sorted(m["duracao"] for m in ok)
    return {
        "n": len(ok),
        "falhas": len(medidas) - len(ok),
        "pct_colado_media": media("pct_colado"),
        "pct_colado_mediana": med("pct_colado"),
        "pct_sobreposto_media": media("pct_sobreposto"),
        "maior_colado_mediana_s": med("maior_colado_s"),
        "maior_colado_pior_s": max(m["maior_colado_s"] for m in ok),
        "trechos_2s_total": sum(m["trechos_2s"] for m in ok),
        "lutas_com_trecho_2s": sum(1 for m in ok if m["trechos_2s"]),
        "agarroes_media": media("agarroes"),
        "respiros_media": round(statistics.fmean(m.get("respiros", 0) for m in ok), 3),
        "vel_media_ms": media("vel_media_ms"),
        "pct_parado_media": media("pct_parado"),
        "aproximacoes_media": media("aproximacoes"),
        "afastamentos_media": media("afastamentos"),
        "duracao_mediana": med("duracao"),
        "duracao_p90": duracoes[min(len(duracoes) - 1, int(0.9 * len(duracoes)))],
        "duracao_max": duracoes[-1],
        "duracao_min": duracoes[0],
        "lutas_acima_90s": sum(1 for d in duracoes if d > 90.0),
        "time_limit": sum(1 for m in ok if str(m["motivo"]).startswith("time_limit")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("lote", type=Path, nargs="?",
                        help="lista de lutas; sem ela, use --corpus")
    parser.add_argument("--corpus", choices=("smoke", "completo"), default=None,
                        help="o corpus do harness de qualidade (fixture engine)")
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--trabalhadores", type=int, default=3)
    chave = parser.add_mutually_exclusive_group()
    chave.add_argument("--dinamismo", dest="dinamismo", action="store_const", const=True,
                       default=None, help="carimba dinamismo=True em toda luta do lote")
    chave.add_argument("--sem-dinamismo", dest="dinamismo", action="store_const", const=False,
                       help="carimba dinamismo=False em toda luta do lote")
    args = parser.parse_args(argv)
    if args.corpus:
        from neural_fights.tools import qualidade_luta as ql

        fonte = ql.FonteDeDados("engine")
        specs = ql.corpus_smoke(fonte) if args.corpus == "smoke" else ql.corpus_completo(fonte)
        itens = [{"p1": sp["p1"], "p2": sp["p2"], "seed": sp["seed"],
                  "cenario": sp.get("cenario", ql.CENARIO_PADRAO), "dados": "engine",
                  **({"preset_p1": sp["preset_p1"]} if sp.get("preset_p1") else {})}
                 for sp in specs]
    elif args.lote is not None:
        itens = json.loads(args.lote.read_text(encoding="utf-8"))
    else:
        parser.error("passe o lote ou --corpus")
    if args.dinamismo is not None:
        itens = [{**item, "dinamismo": args.dinamismo} for item in itens]
    medidas = medir_lote(itens, trabalhadores=args.trabalhadores)
    args.saida.write_text(json.dumps({"resumo": resumo(medidas), "lutas": medidas},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resumo(medidas), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
