# -*- coding: utf-8 -*-
"""Camada de broadcast da live (Passe 3 do programa de arte).

Antes deste módulo, ``neural_fights/live`` não desenhava um pixel: o
ranking morria no SQLite, o ``ResultadoComando`` virava bool, quem pagava
``!meteoro`` via um efeito idêntico ao de uma skill da IA, e os 6 segundos
entre partidas eram um véu preto com "Pressione R" vazando ao vivo.

O ``BroadcastOverlay`` é desenhado por ``LiveSession.passo()`` DEPOIS de
``sim.desenhar()`` e antes do flip — o motor continua sem saber que está
numa transmissão. Todo elemento consome o :class:`LayoutSpec` (16:9 e
9:16 desde o início) e as fontes/paleta centrais do Passe 2. Um overlay
que quebre nunca derruba o show (a sessão engole a exceção e loga).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pygame

from neural_fights.simulation.layout import LayoutSpec, obter_layout
from neural_fights.utils.fonts import get_fonte, get_fonte_impact
from neural_fights.utils.palette import CORES_RARIDADE  # noqa: F401 (passes futuros)

if TYPE_CHECKING:  # pragma: no cover
    from neural_fights.live.commands import ResultadoComando
    from neural_fights.live.events import ViewerEvent

logger = logging.getLogger(__name__)

# Timeline da pausa entre partidas (a pausa padrão é 6s)
FIM_VITORIA_S = 3.0
FIM_VS_S = 5.0

DURACAO_LOWER_THIRD_S = 4.0
MAX_LOWER_THIRDS = 3
DURACAO_TOAST_RECUSA_S = 2.5
POLL_RANKING_S = 10.0
DURACAO_FIGHT_FLASH_S = 0.9

COR_PAINEL = (10, 10, 18, 210)
COR_ACENTO = (0, 217, 255)      # ciano neon (COR_SUCCESS do tema)
COR_ACENTO_2 = (233, 69, 96)    # magenta-vermelho (COR_ACCENT do tema)
COR_OURO = (255, 215, 0)
COR_TEXTO = (240, 240, 245)
COR_TEXTO_DIM = (150, 156, 176)


def _texto_curto(texto: str, limite: int = 18) -> str:
    texto = str(texto or "").strip()
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


class BroadcastOverlay:
    """Compositor de show: lower-thirds, ticker, VS screen, countdown."""

    def __init__(self, sessao, registry=None):
        self.sessao = sessao
        self.registry = registry
        self._lower_thirds: list[dict] = []
        self._toast_recusa: dict | None = None
        self._ranking: list[dict] = []
        self._proximo_poll_ranking = 0.0
        self._ticker_scroll = 0.0
        self._ultimo_desenho = None
        self._em_pausa_antes = False
        self._fight_flash_ate = 0.0
        self._inicio_luta = None
        self._duracao_ultima_luta = 0.0

    # ------------------------------------------------------------- comandos

    def notificar_comando(self, resultado: "ResultadoComando", evento: "ViewerEvent") -> None:
        """Recebe o ResultadoComando COMPLETO (o hook do Passe 3).

        Aplicado → lower-third "Fulano usou !verbo". Recusado com gift →
        toast discreto: quem pagou merece saber que não entrou.
        """
        agora = self.sessao._relogio()
        nome = _texto_curto(getattr(evento, "viewer_name", "") or "Alguém", 16)
        verbo = (getattr(evento, "texto", "") or "").strip().split(" ")[0]
        if not verbo.startswith("!"):
            verbo = "!?"

        if resultado.aplicado:
            self._lower_thirds.append(
                {"nome": nome, "verbo": verbo, "ate": agora + DURACAO_LOWER_THIRD_S}
            )
            if len(self._lower_thirds) > MAX_LOWER_THIRDS:
                del self._lower_thirds[0]
        elif getattr(evento, "value_units", 0) > 0:
            detalhe = _texto_curto(resultado.detalhe, 34)
            self._toast_recusa = {
                "texto": f"{nome}: {verbo} — {detalhe or resultado.status.lower()}",
                "ate": agora + DURACAO_TOAST_RECUSA_S,
            }

    # -------------------------------------------------------------- desenho

    def desenhar(self, tela: pygame.Surface) -> None:
        layout = obter_layout(tela.get_width(), tela.get_height())
        agora = self.sessao._relogio()
        pausa = self.sessao.tempo_na_pausa

        # Transições de fase (o overlay só observa o relógio da sessão)
        if pausa is None and self._em_pausa_antes:
            self._fight_flash_ate = agora + DURACAO_FIGHT_FLASH_S
            self._inicio_luta = agora
        if pausa is not None and not self._em_pausa_antes and self._inicio_luta:
            self._duracao_ultima_luta = agora - self._inicio_luta
        self._em_pausa_antes = pausa is not None

        self._lower_thirds = [lt for lt in self._lower_thirds if lt["ate"] > agora]
        if self._toast_recusa and self._toast_recusa["ate"] <= agora:
            self._toast_recusa = None

        if pausa is None:
            self._desenhar_em_luta(tela, layout, agora)
        else:
            self._desenhar_pausa(tela, layout, pausa)

    # ------------------------------------------------------------- em luta

    def _desenhar_em_luta(self, tela, layout: LayoutSpec, agora: float) -> None:
        self._desenhar_placar_contexto(tela, layout)
        self._desenhar_lower_thirds(tela, layout)
        self._desenhar_toast(tela, layout)
        self._desenhar_ticker(tela, layout, agora)
        if agora < self._fight_flash_ate:
            restante = (self._fight_flash_ate - agora) / DURACAO_FIGHT_FLASH_S
            fonte = get_fonte_impact(int(layout.fonte_titulo * 2.2))
            surf = fonte.render("LUTEM!", True, COR_OURO)
            surf.set_alpha(int(255 * min(1.0, restante * 2)))
            tela.blit(
                surf,
                (layout.centro_x - surf.get_width() // 2,
                 layout.centro_y - surf.get_height() // 2),
            )

    def _desenhar_placar_contexto(self, tela, layout: LayoutSpec) -> None:
        """"PARTIDA #N • Arena" — no lugar do placar de série que era uma
        string eternamente constante na live."""
        sim = self.sessao.sim
        arena = str(sim.match_config.get("cenario") or "Arena")
        numero = self.sessao.stats.partidas + 1
        texto = f"PARTIDA #{numero}  •  {arena}"
        fonte = get_fonte(layout.fonte_media, negrito=True)
        surf = fonte.render(texto, True, COR_OURO)
        x = layout.centro_x - surf.get_width() // 2
        fundo = pygame.Surface((surf.get_width() + 24, surf.get_height() + 8), pygame.SRCALPHA)
        fundo.fill(COR_PAINEL)
        tela.blit(fundo, (x - 12, layout.placar_y - 4))
        tela.blit(surf, (x, layout.placar_y))

    def _desenhar_lower_thirds(self, tela, layout: LayoutSpec) -> None:
        x, y_base = layout.lower_third_pos
        fonte_nome = get_fonte(layout.fonte_media, negrito=True)
        fonte_verbo = get_fonte(layout.fonte_media)
        altura = fonte_nome.get_height() + 12
        for i, lt in enumerate(reversed(self._lower_thirds)):
            y = y_base - i * (altura + 6)
            painel = pygame.Surface((layout.lower_third_largura, altura), pygame.SRCALPHA)
            painel.fill(COR_PAINEL)
            pygame.draw.rect(painel, COR_ACENTO, (0, 0, 4, altura))
            tela.blit(painel, (x, y))
            s_nome = fonte_nome.render(lt["nome"], True, COR_ACENTO)
            s_meio = fonte_verbo.render(" usou ", True, COR_TEXTO_DIM)
            s_verbo = fonte_nome.render(lt["verbo"], True, COR_OURO)
            cx = x + 12
            for surf in (s_nome, s_meio, s_verbo):
                tela.blit(surf, (cx, y + 6))
                cx += surf.get_width()

    def _desenhar_toast(self, tela, layout: LayoutSpec) -> None:
        if not self._toast_recusa:
            return
        fonte = get_fonte(layout.fonte_pequena)
        surf = fonte.render(self._toast_recusa["texto"], True, COR_TEXTO_DIM)
        x, y_base = layout.lower_third_pos
        y = y_base + 34
        painel = pygame.Surface((surf.get_width() + 16, surf.get_height() + 8), pygame.SRCALPHA)
        painel.fill((10, 10, 18, 160))
        tela.blit(painel, (x, y))
        tela.blit(surf, (x + 8, y + 4))

    def _desenhar_ticker(self, tela, layout: LayoutSpec, agora: float) -> None:
        if self.registry is None:
            return
        if agora >= self._proximo_poll_ranking:
            self._proximo_poll_ranking = agora + POLL_RANKING_S
            try:
                self._ranking = list(self.registry.classificacao(limite=5))
            except Exception:
                logger.exception("classificacao() falhou; ticker mantém cache")
        if not self._ranking:
            return
        partes = ["RANKING"]
        for i, linha in enumerate(self._ranking):
            partes.append(
                f"#{i + 1} {_texto_curto(linha.get('display_name', '?'), 14)} "
                f"{linha.get('wins', 0)}V"
            )
        texto = "   •   ".join(partes) + "   •   digite !entrar para lutar"
        fonte = get_fonte(layout.fonte_pequena, negrito=True)
        surf = fonte.render(texto, True, COR_TEXTO)
        faixa = pygame.Surface((layout.largura, layout.ticker_altura), pygame.SRCALPHA)
        faixa.fill((8, 8, 14, 200))
        pygame.draw.line(faixa, COR_ACENTO, (0, 0), (layout.largura, 0), 2)
        tela.blit(faixa, (0, layout.ticker_y))
        # scroll contínuo baseado no relógio (o overlay não recebe dt)
        periodo = surf.get_width() + layout.largura
        desloc = int((agora * 60) % periodo)
        tela.blit(surf, (layout.largura - desloc,
                         layout.ticker_y + (layout.ticker_altura - surf.get_height()) // 2))

    # --------------------------------------------------------------- pausa

    def _desenhar_pausa(self, tela, layout: LayoutSpec, pausa: float) -> None:
        veu = pygame.Surface((layout.largura, layout.altura), pygame.SRCALPHA)
        veu.fill((5, 5, 12, 170))
        tela.blit(veu, (0, 0))

        total = max(0.1, self.sessao.pausa_entre_partidas)
        # timeline proporcional: vitória → VS → countdown
        t_vitoria = FIM_VITORIA_S * total / 6.0
        t_vs = FIM_VS_S * total / 6.0

        if pausa < t_vitoria:
            self._desenhar_cartaz_vitoria(tela, layout)
        elif pausa < t_vs:
            self._desenhar_vs(tela, layout)
        else:
            restante = max(0.0, total - pausa)
            numero = max(1, int(restante / max(0.001, (total - t_vs)) * 3) + 0)
            fonte = get_fonte_impact(int(layout.fonte_titulo * 3))
            surf = fonte.render(str(min(3, numero)), True, COR_ACENTO)
            tela.blit(
                surf,
                (layout.centro_x - surf.get_width() // 2,
                 layout.centro_y - surf.get_height() // 2),
            )

    def _nome_exibicao(self, nome_motor: str) -> str:
        mapa = self.sessao.sim.match_config.get("nomes_exibicao") or {}
        return _texto_curto(mapa.get(nome_motor, nome_motor), 20)

    def _desenhar_cartaz_vitoria(self, tela, layout: LayoutSpec) -> None:
        sim = self.sessao.sim
        vencedor = getattr(sim, "vencedor", None)
        nome_motor = getattr(getattr(vencedor, "dados", None), "nome", None)
        empate = nome_motor is None
        nome = "EMPATE" if empate else self._nome_exibicao(nome_motor)
        fonte_tit = get_fonte_impact(int(layout.fonte_titulo * 1.6))
        fonte_sub = get_fonte(layout.fonte_media, negrito=True)
        s_rot = get_fonte(layout.fonte_pequena, negrito=True).render(
            "RESULTADO" if empate else "VENCEDOR", True, COR_TEXTO_DIM
        )
        s_nome = fonte_tit.render(nome, True, COR_OURO)
        detalhes = ""
        if not empate:
            vitorias_dia = self.sessao.stats.vitorias_por_lutador.get(nome_motor, 0)
            detalhes = f"{vitorias_dia} vitória(s) hoje"
        if self._duracao_ultima_luta > 0:
            sep = "  •  " if detalhes else ""
            detalhes += f"{sep}{self._duracao_ultima_luta:.0f}s de luta"
        s_det = fonte_sub.render(detalhes or " ", True, COR_TEXTO)
        y = layout.centro_y - s_nome.get_height()
        for surf, dy in ((s_rot, -30), (s_nome, 0), (s_det, s_nome.get_height() + 14)):
            tela.blit(surf, (layout.centro_x - surf.get_width() // 2, y + dy))

    def _desenhar_vs(self, tela, layout: LayoutSpec) -> None:
        confronto = self.sessao.proximo_confronto
        if not confronto:
            return
        p1, p2, cenario = confronto
        fonte_nome = get_fonte_impact(int(layout.fonte_titulo * 1.3))
        fonte_vs = get_fonte_impact(int(layout.fonte_titulo * 1.8))
        fonte_arena = get_fonte(layout.fonte_media, negrito=True)
        s1 = fonte_nome.render(self._nome_exibicao(p1), True, COR_ACENTO)
        s2 = fonte_nome.render(self._nome_exibicao(p2), True, COR_ACENTO_2)
        s_vs = fonte_vs.render("VS", True, COR_TEXTO)
        s_arena = fonte_arena.render(str(cenario), True, COR_OURO)
        if layout.portrait:
            # em coluna
            y = layout.centro_y - 120
            for surf, dy in ((s1, 0), (s_vs, 70), (s2, 140), (s_arena, 220)):
                tela.blit(surf, (layout.centro_x - surf.get_width() // 2, y + dy))
        else:
            y = layout.centro_y - s_vs.get_height() // 2
            tela.blit(s_vs, (layout.centro_x - s_vs.get_width() // 2, y))
            tela.blit(s1, (layout.centro_x - s_vs.get_width() // 2 - 40 - s1.get_width(), y + 8))
            tela.blit(s2, (layout.centro_x + s_vs.get_width() // 2 + 40, y + 8))
            tela.blit(
                s_arena,
                (layout.centro_x - s_arena.get_width() // 2, y + s_vs.get_height() + 24),
            )
