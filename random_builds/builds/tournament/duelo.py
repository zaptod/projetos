"""O DUELO: a luta inteira em 20-35 s, sem nenhuma cena parada.

Por que este formato existe
---------------------------
Medido em 11/09/2026, com a primeira coleta de retencao real do canal:

    build    18 videos  28,1% de retencao media  19,4 s vistos de 74 s
    estreia  12 videos   3,4% de retencao media   3,3 s vistos de 103 s
                         (MEDIANA ZERO: metade nao e assistida por ninguem)

E a curva do unico video com amostra suficiente (143 views, 53 s) mostra
onde a audiencia morre: 86% aos 8,5 s, 60% aos 11,1 s depois de tres roletas
seguidas, e 18,6% quando a LUTA finalmente comeca, aos 50,9 s. O produto
chega a menos de um quinto de quem abriu o video.

O numero que decide o desenho deste formato nao e nenhum desses: e que o
publico entrega ~20 SEGUNDOS a este canal, e isso ja e a media do formato
que vai melhor. Um video de 25-30 s e assistido quase inteiro pela mesma
audiencia que abandona um de 74 s na metade.

O que o duelo e
---------------
UM evento de gameplay. Nao ha gancho, card, titulo de round, reacao nem
outro — nenhuma cena em que o jogo esteja parado. O que seria cena vira
SOBREPOSICAO no proprio clipe da luta:

    identidade  ~1,5 s iniciais: quem e quem, por cor e nome;
    hud         barras de vida e plano, o mesmo de sempre;
    callouts    PARRY!, COMBO x4, K.O., o mesmo de sempre;
    veredito    ~1,2 s finais: quem ganhou, sobre o ultimo frame.

Deriva de `FightTimelineBuilder` para MENOS: reusa `evento_gameplay` e
`planejar_callouts` deste mesmo modulo. Nada e copiado — ha teste cobrando
que o duelo nao tem timeline propria de gameplay.

Escopo: build, estreia e torneio NAO mudam. O duelo e publicado ao lado
deles e a comparacao decide qual vence (Onda 15E).
"""
from __future__ import annotations

import random

from ..content.caption_generator import CaptionGenerator
from .timeline import evento_gameplay


class DueloTimelineBuilder:
    """Monta o `edit_plan.json` do duelo: um unico evento de gameplay."""

    def __init__(self, editing_config: dict, captions: CaptionGenerator):
        self.config = editing_config
        self.captions = captions

    @property
    def _cfg(self) -> dict:
        return self.config.get("duelo") or {}

    def build(self, rng: random.Random, fight: dict) -> dict:
        # O duelo e sempre UMA luta. Numa serie, o round que fechou — mas a
        # politica do formato e `melhor_de=1`, entao na pratica e a unica.
        rounds = list(fight.get("lutas") or [fight["luta"]])
        luta = rounds[-1]

        evento = evento_gameplay(rng, luta, self.config, self.captions)
        if evento is None:
            raise ValueError(
                "duelo sem clipe gravado: o formato E a luta, entao nao ha "
                "o que montar sem ela (o build, esse sim, cai para roleta)")

        duracao = max(float(c["duracao"]) for c in (luta.get("clipes") or {}).values())
        evento["start"] = 0.0
        evento["duration"] = round(duracao, 3)
        evento["identidade"] = self._identidade(luta, duracao)
        evento["veredito"] = self._veredito(luta, duracao)
        # Sem `caption`: legenda de cena e coisa de cena, e aqui nao ha cena.
        # O que o espectador le esta desenhado sobre o jogo.
        evento["caption"] = ""

        return {
            "generation_id": fight.get("duelo_id", fight.get("fight_id", "duelo")),
            "seed": fight["seed"],
            "kind": "duelo",
            "total_duration": round(duracao, 3),
            "events": [evento],
        }

    # ------------------------------------------------------------ overlays
    def _identidade(self, luta: dict, duracao: float) -> dict:
        """Quem e quem, nos primeiros segundos, SEM parar a luta.

        A referencia do genero resolve identidade em meio segundo porque a
        bola E a identidade ("a vermelha da espada"). Aqui o equivalente
        barato e cor + nome + arma sobre o proprio jogo. O ledger (cartel,
        revanche, titulo) entra nesta mesma caixa na 15D.
        """
        ate = float(self._cfg.get("identidade_s", 1.5))
        return {
            "ate": round(min(ate, duracao * 0.25), 3),
            "p1": self._lado(luta, "p1"),
            "p2": self._lado(luta, "p2"),
        }

    def _veredito(self, luta: dict, duracao: float) -> dict:
        """O desfecho sobre o ultimo frame — nunca um cartao depois dele.

        Um cartao de resultado e uma cena parada no exato momento em que o
        espectador ja decidiu ficar ate o fim: e onde o formato antigo
        gastava 2,5 s para dizer o que a tela ja mostrou.
        """
        dur = float(self._cfg.get("veredito_s", 1.2))
        dur = min(dur, max(0.4, duracao * 0.2))
        return {
            "de": round(max(0.0, duracao - dur), 3),
            "vencedor": luta.get("vencedor") or "",
            "ko_type": luta.get("ko_type") or "",
        }

    @staticmethod
    def _lado(luta: dict, slot: str) -> dict:
        """O que da para dizer de um lutador em meio segundo de leitura.

        A ficha da luta tem `nome_arma` (o nome proprio, "Iskimantr") mas
        NAO o tipo ("Reta", "Arco"). Identidade por TIPO de arma — que e o
        que a referencia do genero usa, com glifo — depende do glifo por
        tipo que a 15C traz; ate la o nome da arma e o que existe.
        """
        ficha = luta.get(f"{slot}_ficha") or {}
        return {
            "nome": luta.get(slot) or "",
            "arma": ficha.get("nome_arma") or "",
            "classe": ficha.get("classe") or "",
        }
