"""Ledger da arena: a carreira dos personagens ENTRE videos.

A live tem `neural_fights/live/standings.py` (SQLite, por espectador). O
conteudo nao tinha nada: um personagem criado na roleta lutava num torneio e
o resultado morria no `tournament.json` daquela pasta. Aqui toda luta gravada
para video (estreia, luta avulsa, torneio) vira uma linha, e e dela que saem
o cartel ("3V-1D"), a revanche, o campeao que defende o titulo e o ranking.

Um JSON so, em `outputs/_arena/ledger.json`, gravado de forma atomica (tmp +
replace). E pequeno de proposito: um video por dia rende centenas de linhas
por ano, nao milhoes.
"""
from __future__ import annotations

import json
import os
import random
import tempfile
from datetime import datetime, timezone
from pathlib import Path

OUTPUTS = Path(__file__).resolve().parents[2] / "outputs"
ARQUIVO = OUTPUTS / "_arena" / "ledger.json"


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Ledger:
    def __init__(self, caminho: Path | None = None):
        self.caminho = Path(caminho) if caminho else ARQUIVO
        self.dados: dict = {"versao": 1, "lutas": []}
        if self.caminho.is_file():
            try:
                lido = json.loads(self.caminho.read_text(encoding="utf-8"))
                if isinstance(lido, dict) and isinstance(lido.get("lutas"), list):
                    self.dados = lido
            except (OSError, ValueError):
                # Ledger corrompido nunca derruba um video; ele recomeça e o
                # arquivo antigo fica de lado para quem quiser recuperar.
                try:
                    self.caminho.replace(self.caminho.with_suffix(".corrompido.json"))
                except OSError:
                    pass
        self.dados.setdefault("lutas", [])

    # ------------------------------------------------------------- escrita
    @property
    def lutas(self) -> list[dict]:
        return self.dados["lutas"]

    def registrar(self, luta: dict, *, origem: str, video: str | None = None) -> dict:
        """Grava (ou substitui) a linha desta luta. Idempotente por id."""
        registro = {
            "id": f"{origem}:{luta.get('match_id', 0)}:{luta.get('seed')}:"
                  f"{luta.get('p1')}:{luta.get('p2')}",
            "origem": origem,
            "p1": luta.get("p1"),
            "p2": luta.get("p2"),
            "vencedor": luta.get("vencedor"),
            "perdedor": luta.get("perdedor"),
            "empate": not luta.get("vencedor"),
            "duracao": luta.get("duracao"),
            "ko_type": luta.get("ko_type"),
            "hp_vencedor": luta.get("hp_vencedor"),
            "seed": luta.get("seed"),
            "cenario": luta.get("cenario"),
            "marcas": list(luta.get("marcas") or []),
            "score": luta.get("score"),
            "tier": luta.get("tier"),
            "video": video,
            "quando": _agora(),
        }
        self.dados["lutas"] = [r for r in self.lutas if r.get("id") != registro["id"]]
        self.lutas.append(registro)
        self.salvar()
        return registro

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.caminho.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.dados, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.caminho)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------- leitura
    def recorde(self, nome: str) -> dict:
        """{"vitorias", "derrotas", "empates", "lutas", "sequencia"}.

        `sequencia` e a serie atual: +3 = tres vitorias seguidas, -2 = duas
        derrotas seguidas, 0 = sem lutas ou ultima foi empate.
        """
        v = d = e = 0
        sequencia = 0
        for r in self.lutas:
            if nome not in (r.get("p1"), r.get("p2")):
                continue
            if r.get("empate"):
                e += 1
                sequencia = 0
            elif r.get("vencedor") == nome:
                v += 1
                sequencia = sequencia + 1 if sequencia >= 0 else 1
            else:
                d += 1
                sequencia = sequencia - 1 if sequencia <= 0 else -1
        return {"vitorias": v, "derrotas": d, "empates": e,
                "lutas": v + d + e, "sequencia": sequencia}

    def cartel(self, nome: str) -> str:
        r = self.recorde(nome)
        return f"{r['vitorias']}V-{r['derrotas']}D"

    def confrontos(self, a: str, b: str) -> list[dict]:
        return [r for r in self.lutas
                if {r.get("p1"), r.get("p2")} == {a, b}]

    def ranking(self, limite: int = 10) -> list[dict]:
        nomes: dict[str, dict] = {}
        for r in self.lutas:
            for nome in (r.get("p1"), r.get("p2")):
                if nome and nome not in nomes:
                    nomes[nome] = {"nome": nome, **self.recorde(nome)}
        ordem = sorted(nomes.values(),
                       key=lambda x: (-x["vitorias"], x["derrotas"], -x["lutas"], x["nome"]))
        return ordem[:limite]

    def campeao_atual(self) -> str | None:
        """Quem venceu a ultima luta registrada (o "titulo" em disputa)."""
        for r in reversed(self.lutas):
            if r.get("vencedor"):
                return r["vencedor"]
        return None


def escolher_adversario(nome: str, candidatos: list[str], rng: random.Random, *,
                        gerados: list[str] | tuple[str, ...] = (),
                        fichas: dict | None = None,
                        ledger: Ledger | None = None) -> str | None:
    """Quem enfrenta `nome` na estreia (ou numa luta avulsa sem --p2).

    1. Continuidade: o personagem GERADO mais recente que ainda nao lutou
       contra ele — "o de ontem contra o de hoje" liga um video ao outro.
    2. Senao, poder proximo (forca+mana), sorteado entre os 3 mais parecidos:
       estreia nao pode ser atropelo por construcao.
    """
    pool = [c for c in candidatos if c and c != nome]
    if not pool:
        return None
    vistos: set[str] = set()
    for gerado in reversed(list(gerados)):
        if gerado == nome or gerado not in pool or gerado in vistos:
            continue
        vistos.add(gerado)
        if ledger is None or not ledger.confrontos(nome, gerado):
            return gerado
    if fichas and nome in fichas:
        def poder(n: str) -> float:
            f = fichas.get(n) or {}
            return float(f.get("forca", 5.0)) + float(f.get("mana", 5.0))
        alvo = poder(nome)
        proximos = sorted(pool, key=lambda n: (abs(poder(n) - alvo), n))[:3]
        return rng.choice(proximos)
    return rng.choice(sorted(pool))
