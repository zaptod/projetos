"""Grava uma luta do Neural Fights em mp4 — sem abrir janela.

Por que NAO usamos ``headless=True``
------------------------------------
O modo headless do ``Simulador`` nao e apenas "sem janela": ele DEGRADA o
visual. Sob ele o motor pula a aura das transformacoes (``simulacao.py:593``),
o clima da arena e o feedback de defesa (``:619-621``), a trilha dramatica dos
projeteis de skill (``:1298``), o beam sustentado (``:1689``) e o telegraph de
golpe pesado (``core/entities.py:2535``); e, por chamar apenas
``pygame.font.init()``, deixa ``pygame.time.get_ticks()`` cravado em zero,
congelando toda animacao pulsada.

Gravamos entao com ``headless=False`` + ``SDL_VIDEODRIVER=dummy``: o
``set_mode`` devolve uma superficie offscreen, nenhuma janela aparece e todo o
VFX continua vivo. Medido nesta maquina: 242 fps para
``update`` + ``desenhar`` + extrair o frame em 540x960 — cerca de 4x o tempo
real.

Uso:
    python -m neural_fights.recording.fight_recorder \\
        --p1 "Nome" --p2 "Outro" --seed 7 --saida luta.mp4 [--portrait]

Imprime o resultado da luta como JSON no stdout (uma linha), no mesmo espirito
de ``cli/headless.py``.
"""
from __future__ import annotations

import os

# O driver de video precisa ser escolhido ANTES de o pygame inicializar. Mesmo
# par ja usado por tools/qualidade_luta.py:35 e pela suite de testes.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import argparse  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import pygame  # noqa: E402

from neural_fights.utils.config import FPS  # noqa: E402

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Sobra gravada depois do KO: o slow-motion dura 2 s (simulacao.py:3455) e o
# letterbox cinematografico 1,6 s (:3290). Sem isso o video corta no meio da
# comemoracao.
CAUDA_POS_KO = 3.5


class SondaDeDano:
    """Coleta ``(t_video, slot, dano, categoria)`` de cada golpe.

    Segue o mesmo contrato de hooks da ``FightQualityProbe``
    (``simulation/probes.py:94`` e ``:111``) e o mesmo mecanismo: o proprio
    ``Lutador`` anota em ``registro_eventos_dano`` (``core/entities.py:2767``)
    e a sonda drena a lista a cada frame.

    Diferenca deliberada: o tempo registrado e o **tempo do video**, nao o
    tempo do jogo. Durante o slow-motion do KO os dois divergem, e quem vai
    cortar os melhores momentos precisa de timestamps que existam no mp4.
    """

    def __init__(self) -> None:
        self.eventos: list[tuple[float, str, float, str]] = []
        self._registros: dict[str, list[tuple[float, str]]] = {}

    def on_inicio(self, sim) -> None:
        for slot in ("p1", "p2"):
            lista: list[tuple[float, str]] = []
            getattr(sim, slot).registro_eventos_dano = lista
            self._registros[slot] = lista

    def on_frame(self, sim, t_video: float) -> None:
        for slot in ("p1", "p2"):
            lista = self._registros.get(slot)
            if not lista:
                continue
            for dano, categoria in lista:
                self.eventos.append((round(t_video, 3), slot, float(dano), str(categoria)))
            lista.clear()


def _recorte_util(sim, largura: int, altura: int) -> list[int] | None:
    """Onde a arena (mais o HUD) fica no quadro, em pixels.

    So faz sentido porque a camera padrao e TRAVADA na arena: a arena ocupa
    exatamente o mesmo retangulo em todos os frames. Em 9:16 ela deixa faixas
    vazias enormes em cima e embaixo, e quem monta o video pode aparar esse
    excedente sem mexer na camera nem cortar nada da luta.

    Devolve [x, y, largura, altura] ou None se nao der para calcular.
    """
    camera = getattr(sim, "cam", None)
    arena = getattr(sim, "arena", None)
    if camera is None or arena is None or getattr(camera, "arena_centro", None) is None:
        return None
    try:
        from neural_fights.utils.config import PPM
        meia_l = arena.largura * PPM / 2
        meia_a = arena.altura * PPM / 2
        centro_x = arena.centro_x * PPM
        centro_y = arena.centro_y * PPM
        esquerda, topo = camera.converter(centro_x - meia_l, centro_y - meia_a)
        direita, base = camera.converter(centro_x + meia_l, centro_y + meia_a)
    except Exception:
        return None

    # A largura fica INTEIRA: o HUD (barras de vida) ocupa a linha toda, e
    # apara-lo pelas laterais cortaria os nomes. So a sobra vertical sai.
    folga = round(min(largura, altura) * 0.04)
    x0, x1 = 0, largura
    # O topo vai ate 0 de proposito: e onde moram as barras de vida.
    y0 = 0
    y1 = min(altura, max(topo, base) + folga)
    if y1 - y0 < 32 or y1 >= altura - 8:
        return None  # nada relevante a aparar
    # Dimensoes pares: exigencia do yuv420p.
    return [int(x0), int(y0), int((x1 - x0) // 2 * 2), int((y1 - y0) // 2 * 2)]


def _abrir_ffmpeg(saida: Path, largura: int, altura: int, fps: int,
                  crf: int, preset: str) -> subprocess.Popen:
    """Pipe de frames crus para o ffmpeg.

    Mesmo formato de `random_builds/src/video/renderer.py::_encode_frames`,
    inclusive a trilha silenciosa: manter os segmentos com video E audio e o
    que permite o `concat -c copy` do renderer funcionar depois.
    """
    saida.parent.mkdir(parents=True, exist_ok=True)
    comando = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{largura}x{altura}", "-r", str(fps), "-i", "pipe:",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-shortest",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        str(saida),
    ]
    return subprocess.Popen(comando, stdin=subprocess.PIPE, creationflags=NO_WINDOW)


def gravar_luta(
    *,
    p1: str,
    p2: str,
    saida: str | Path,
    seed: int = 0,
    cenario: str = "Arena Pequena",
    portrait: bool = False,
    fps_saida: int = 30,
    max_duracao: float = 120.0,
    cauda_pos_ko: float = CAUDA_POS_KO,
    hud: bool = True,
    crf: int = 20,
    preset: str = "veryfast",
    camera_modo: str | None = None,
    nomes_exibicao: dict | None = None,
) -> dict:
    """Roda a luta desenhando cada frame e devolve o resultado + timestamps.

    A luta e deterministica pela seed: gravar a mesma seed duas vezes (uma por
    formato) produz exatamente a mesma luta enquadrada de dois jeitos.
    """
    # Import tardio: o Simulador puxa pygame, e o driver precisa ja estar
    # escolhido (feito no topo do modulo).
    from neural_fights.simulation.simulacao import Simulador

    saida = Path(saida)
    match_config = {
        "p1_nome": p1,
        "p2_nome": p2,
        "cenario": cenario,
        "best_of": 1,
        "portrait_mode": bool(portrait),
        # Suprime o placar de serie e o cartaz "Pressione R" — sao para quem
        # joga, nao para quem assiste ao video (simulacao.py:3971 e :3983).
        "modo_live": True,
        # analise=True QUEBRA: desenhar_analise monta pygame.Surface com uma
        # tupla de 3 elementos (simulacao.py:5434).
        "overlays": {"hud": bool(hud), "analise": False, "hitbox_debug": False},
    }
    # Em 9:16 a camera ARENA (padrao) deixa os lutadores minusculos: a arena
    # inteira ocupa menos da metade do quadro. "AUTO" enquadra os lutadores.
    # Medido: nao muda o resultado da luta, so o que aparece na tela.
    if camera_modo:
        match_config["camera_modo"] = camera_modo
    if nomes_exibicao:
        match_config["nomes_exibicao"] = dict(nomes_exibicao)

    sim = Simulador(match_config=match_config, headless=False, seed=seed)
    sonda = SondaDeDano()
    ffmpeg = None
    try:
        largura, altura = sim.tela.get_size()
        recorte = _recorte_util(sim, largura, altura)
        ffmpeg = _abrir_ffmpeg(saida, largura, altura, fps_saida, crf, preset)
        sonda.on_inicio(sim)

        passo = 1.0 / FPS                       # o motor pensa a 60 Hz
        a_cada = max(1, round(FPS / fps_saida))  # 2 quadros de jogo por frame de video
        indice = 0
        capturados = 0
        t_jogo = 0.0
        t_ko_video: float | None = None
        # Duracao DA LUTA = tempo de jogo ate o nocaute. A cauda gravada
        # depois dele (slow-mo + letterbox) e do video, nao da luta; incluir
        # a faria divergir do que o motor headless reporta.
        duracao_luta: float | None = None

        while True:
            t_video = capturados / fps_saida
            if t_video >= max_duracao:
                break

            pygame.event.pump()
            # avancar_relogio aplica o time_scale (simulacao.py:5513): durante
            # o slow-mo do KO o jogo anda menos por frame, e e assim que o
            # slow-mo aparece no video.
            dt = sim.avancar_relogio(passo)
            sim.update(dt)
            sim.desenhar()   # 1:1 com update: desenhar() drena arena.limpar_colisoes()
            t_jogo += dt
            sonda.on_frame(sim, t_video)

            if indice % a_cada == 0:
                ffmpeg.stdin.write(pygame.image.tobytes(sim.tela, "RGB"))
                capturados += 1
            indice += 1

            # Nada seta rodando=False no KO (simulacao.py:467 e o unico sinal).
            if sim.round_finalizado:
                if t_ko_video is None:
                    t_ko_video = t_video
                    duracao_luta = t_jogo
                elif t_video - t_ko_video >= cauda_pos_ko:
                    break

        vencedor = getattr(sim, "vencedor", None)
        empate = vencedor in (None, "", "EMPATE")
        perdedor = None
        if not empate:
            perdedor = p2 if vencedor == p1 else p1

        def _razao(lutador) -> float:
            maximo = max(1e-9, float(lutador.vida_max))
            return max(0.0, float(lutador.vida)) / maximo

        hp = {"p1": round(_razao(sim.p1) * 100, 1), "p2": round(_razao(sim.p2) * 100, 1)}
        resultado = {
            "sucesso": True,
            "p1": p1,
            "p2": p2,
            "vencedor": None if empate else vencedor,
            "perdedor": perdedor,
            "empate": empate,
            "motivo": "knockout" if t_ko_video is not None else "time_limit",
            "duracao_jogo": round(duracao_luta if duracao_luta is not None else t_jogo, 2),
            "duracao_video": round(capturados / fps_saida, 2),
            "ko_em_video": round(t_ko_video, 2) if t_ko_video is not None else None,
            "hp_final": hp,
            "hp_vencedor": None if empate else hp["p1" if vencedor == p1 else "p2"],
            "seed": seed,
            "cenario": cenario,
            "portrait": bool(portrait),
            "resolucao": [largura, altura],
            "recorte_util": recorte,
            "fps": fps_saida,
            "arquivo": str(saida),
            "eventos_dano": sonda.eventos,
        }
        return resultado
    finally:
        if ffmpeg is not None:
            try:
                ffmpeg.stdin.close()
            except (OSError, ValueError):
                pass
            ffmpeg.wait()
        sim.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Grava uma luta do Neural Fights em mp4, sem abrir janela")
    parser.add_argument("--p1", required=True)
    parser.add_argument("--p2", required=True)
    parser.add_argument("--saida", required=True, help="arquivo .mp4 de saida")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--cenario", default="Arena Pequena")
    parser.add_argument("--portrait", action="store_true",
                        help="540x960 (9:16) em vez de 1200x800; a camera enquadra "
                             "a arena inteira, entao em 9:16 sobra muita margem — "
                             "prefira gravar em paisagem e encaixar no video")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--max-duracao", type=float, default=120.0)
    parser.add_argument("--sem-hud", action="store_true")
    parser.add_argument("--crf", type=int, default=20)
    parser.add_argument("--preset", default="veryfast")
    parser.add_argument("--camera", default=None,
                        choices=["ARENA", "AUTO", "P1", "P2"],
                        help="enquadramento; ausente = ARENA (arena inteira). "
                             "Use AUTO no vertical, onde a arena inteira "
                             "deixaria os lutadores pequenos demais")
    parser.add_argument("--resultado", default=None,
                        help="grava o resultado tambem neste arquivo JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        resultado = gravar_luta(
            p1=args.p1, p2=args.p2, saida=args.saida, seed=args.seed,
            cenario=args.cenario, portrait=args.portrait, fps_saida=args.fps,
            max_duracao=args.max_duracao, hud=not args.sem_hud,
            crf=args.crf, preset=args.preset, camera_modo=args.camera,
        )
    except Exception as erro:  # o chamador precisa do motivo, nao de um traceback
        resultado = {"sucesso": False, "erro": f"{type(erro).__name__}: {erro}",
                     "p1": args.p1, "p2": args.p2, "seed": args.seed}
    if args.resultado:
        Path(args.resultado).parent.mkdir(parents=True, exist_ok=True)
        Path(args.resultado).write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False))
    return 0 if resultado.get("sucesso") else 1


if __name__ == "__main__":
    raise SystemExit(main())
