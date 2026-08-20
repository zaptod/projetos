#!/usr/bin/env python3
"""CLI da sessao de live.

Abre **uma** janela e roda partidas encadeadas nela ate ser interrompido. A
janela e o que o OBS captura, entao ela e criada uma vez e nunca recriada.

Nesta fase so existe a fonte ``replay``, que le eventos gravados de um arquivo
JSON Lines. Isso permite desenvolver e ensaiar o show inteiro sem estar ao vivo
e sem credencial de plataforma.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from neural_fights.data import database
from neural_fights.live.commands import criar_handler, criar_preparador
from neural_fights.live.registry import LiveRegistry, caminho_padrao
from neural_fights.live.roster import LiveRoster
from neural_fights.live.session import LiveSession, Matchmaker
from neural_fights.live.standings import RankedMatchmaker, criar_registrador
from neural_fights.live.sources.replay import RecordingSource, ReplayEventSource
from neural_fights.utils.console import SafeArgumentParser, safe_print

logger = logging.getLogger(__name__)


def _roster(limite: int | None) -> list[str]:
    nomes = [personagem.nome for personagem in database.carregar_personagens()]
    if len(nomes) < 2:
        raise RuntimeError("sao necessarios ao menos dois personagens para uma live")
    return nomes[:limite] if limite else nomes


def _montar_config(nomes: list[str], cenario: str, sem_hud: bool, portrait: bool = False) -> dict[str, Any]:
    return {
        "p1_nome": nomes[0],
        "p2_nome": nomes[1],
        "cenario": cenario,
        "modo_live": True,
        # A serie e sempre de um round: o formato do show e contado pela sessao,
        # porque ``best_of`` so e lido na construcao do Simulador.
        "best_of": 1,
        # Passe 7: 9:16 pleno — era hardcoded False; o LayoutSpec
        # (Passe 3) ja faz todo elemento de HUD nascer nas duas proporcoes.
        "portrait_mode": bool(portrait),
        "overlays": {"hud": not sem_hud, "analise": False, "hitbox_debug": False},
    }


def build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(description="Neural Fights - sessao de live interativa")
    parser.add_argument(
        "--source",
        choices=("replay", "youtube", "nenhuma"),
        default="nenhuma",
        help="fonte de eventos (padrao: nenhuma, so o show rodando)",
    )
    parser.add_argument(
        "--video-id",
        help="id do video da transmissao; sem ele a conta e consultada",
    )
    parser.add_argument(
        "--credenciais",
        help="arquivo JSON de credenciais do YouTube (padrao: no diretorio de runtime)",
    )
    parser.add_argument(
        "--gravar-eventos",
        help="grava tudo que chegar num .jsonl, para repetir a sessao offline",
    )
    parser.add_argument("--events", help="arquivo JSON Lines de eventos para --source replay")
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="fator de velocidade do replay; 0 publica tudo de uma vez",
    )
    parser.add_argument("--loop-events", action="store_true", help="repete o replay ao terminar")
    parser.add_argument("--cenario", default="Arena", help="arena da primeira partida")
    parser.add_argument(
        "--portrait",
        action="store_true",
        help="janela 9:16 (Shorts/TikTok); HUD e broadcast usam o layout vertical",
    )
    parser.add_argument(
        "--rotacao-arenas",
        default="Arena,Labirinto,Arena Pequena",
        help=(
            "rodizio de arenas entre partidas, separado por virgula "
            "(Labirinto: +60%% de duracao e 27%% de vencedores diferentes "
            "na medicao da F3 — variedade gratis; vazio desliga)"
        ),
    )
    parser.add_argument("--roster", type=int, help="limita quantos lutadores entram no rodizio")
    parser.add_argument("--max-partidas", type=int, help="encerra apos N partidas")
    parser.add_argument(
        "--pausa",
        type=float,
        default=6.0,
        help="segundos de resultado na tela antes da proxima partida",
    )
    parser.add_argument("--sem-hud", action="store_true", help="esconde o HUD do motor")
    parser.add_argument(
        "--registry",
        help=f"arquivo do registro de espectadores (padrao: {caminho_padrao()})",
    )
    parser.add_argument(
        "--sem-registry",
        action="store_true",
        help="nao registra espectadores; o chat vira apenas ambientacao",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)

    if args.source == "replay" and not args.events:
        safe_print("Erro: --source replay exige --events", file=sys.stderr)
        return 2

    # Importado aqui para que `--help` nao precise inicializar o pygame.
    from neural_fights.simulation.simulacao import Simulador

    try:
        nomes = _roster(args.roster)
    except (RuntimeError, OSError, ValueError) as exc:
        safe_print(f"Erro: {exc}", file=sys.stderr)
        return 1

    fontes = []
    fonte = None
    if args.source == "replay":
        try:
            fonte = ReplayEventSource.de_arquivo(
                args.events,
                velocidade=max(0.0, args.speed),
                repetir=args.loop_events,
            )
        except (OSError, ValueError) as exc:
            safe_print(f"Erro ao carregar eventos: {exc}", file=sys.stderr)
            return 1
    elif args.source == "youtube":
        # Importado aqui para que o caminho offline nunca pague o modulo de rede.
        from neural_fights.live.sources.youtube import ErroDeAutenticacao, criar_fonte

        try:
            fonte = criar_fonte(
                caminho_credenciais_json=args.credenciais,
                video_id=args.video_id or "",
            )
        except ErroDeAutenticacao as exc:
            safe_print(f"Erro de credencial: {exc}", file=sys.stderr)
            return 1

    if fonte is not None:
        if args.gravar_eventos:
            fonte = RecordingSource(fonte, args.gravar_eventos)
        fontes.append(fonte)

    registry = None
    handler = None
    preparador = None
    registrador = None
    if not args.sem_registry:
        try:
            registry = LiveRegistry(args.registry)
        except Exception as exc:
            safe_print(f"Erro ao abrir o registro: {exc}", file=sys.stderr)
            return 1
        # handler e preparador nascem DEPOIS do overlay (que recebe os
        # comandos via ao_aplicar) — ver bloco da sessao abaixo.
        registrador = criar_registrador(registry)

    # Um roster com cache: sem ele, cada troca de partida revarre o catalogo
    # inteiro, e lutadores de espectador nem seriam encontrados.
    roster = LiveRoster(registry)
    cenarios = tuple(
        c.strip() for c in (args.rotacao_arenas or "").split(",") if c.strip()
    ) or (args.cenario,)
    matchmaker = (
        # Onda 6: rotacao de arenas — o Matchmaker sempre soube rotacionar
        # (cenarios e um rodizio), so nunca recebeu mais de uma arena.
        RankedMatchmaker(roster, cenarios=cenarios)
        if registry is not None
        else Matchmaker(nomes, cenarios)
    )
    simulador = Simulador(
        match_config=_montar_config(nomes, args.cenario, args.sem_hud, args.portrait),
        roster_provider=roster,
    )
    try:
        sessao = LiveSession(
            simulador,
            matchmaker,
            fontes=fontes,
            aplicar_evento=None,  # ligado abaixo, junto do overlay
            preparar_partida=preparador,
            ao_terminar_partida=registrador,
            pausa_entre_partidas=max(0.0, args.pausa),
            max_partidas=args.max_partidas,
        )
        # Passe 3 (arte): a camada de broadcast — lower-thirds de comando,
        # ticker de ranking, VS screen e countdown na pausa.
        from neural_fights.live.broadcast import BroadcastOverlay

        overlay = BroadcastOverlay(sessao, registry=registry)
        sessao.overlay = overlay
        if registry is not None:
            handler = criar_handler(registry, ao_aplicar=overlay.notificar_comando)
            preparador_real = criar_preparador(handler.router)
            sessao._aplicar_evento = handler
            sessao._preparar_partida = preparador_real
        stats = sessao.run()
    except KeyboardInterrupt:
        safe_print("Sessao interrompida pelo operador.")
        return 0
    finally:
        # Só aqui a janela e destruida: pygame.quit() vive dentro de close().
        try:
            simulador.close()
        except Exception:
            logger.exception("falha ao encerrar o simulador")
        if registry is not None:
            try:
                registry.close()
            except Exception:
                logger.exception("falha ao fechar o registro")

    safe_print(
        f"Sessao encerrada: {stats.partidas} partidas, {stats.frames} frames, "
        f"{stats.eventos_aplicados}/{stats.eventos_recebidos} eventos aplicados."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
