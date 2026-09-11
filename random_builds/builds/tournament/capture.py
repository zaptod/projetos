"""Grava as lutas do torneio em video, uma por subprocesso.

Por que a gravacao e a FONTE DA VERDADE
---------------------------------------
Seria natural simular a luta em headless (rapido) e depois grava-la de novo
para o video. Sao, porem, dois caminhos de codigo diferentes: o headless pula
VFX, nunca chama `desenhar()` (que drena `arena.limpar_colisoes()`) e nao passa
por `avancar_relogio`. Qualquer divergencia produziria um video que **contradiz
o placar** mostrado logo depois.

Entao a luta e simulada UMA vez, desenhando: o resultado sai da propria
gravacao. Alem de eliminar a divergencia, corta metade do trabalho.

Um subprocesso por luta e obrigatorio — o `Simulador` tem trava de instancia
unica por processo (`simulacao.py:95-96`) e `close()` chama `pygame.quit()`.
Como sao processos separados, varias lutas gravam em paralelo.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
RAIZ_PROJETOS = Path(__file__).resolve().parents[3]


def gravar_uma(*, p1: str, p2: str, seed: int, saida: Path, cenario: str,
               portrait: bool = False, camera_modo: str | None = None,
               fps: int = 30, max_duracao: float = 120.0,
               timeout: float = 600.0, resolucao: tuple[int, int] | None = None,
               sem_hud: bool = False,
               camera_largura_min: float | None = None,
               camera_espera_zoom: float | None = None) -> dict:
    """Roda o gravador oficial num subprocesso e devolve o resultado da luta.

    `resolucao` grava em tamanho nativo (1080x1920 para o celular) — sem o
    upscale 2x que borrava o gameplay. `sem_hud` tira as barras do jogo: o
    HUD do video e desenhado pelo renderer a partir da `serie_hp`.
    """
    saida = Path(saida)
    comando = [
        sys.executable, "-X", "utf8",
        "-m", "neural_fights.recording.fight_recorder",
        "--p1", p1, "--p2", p2, "--seed", str(seed),
        "--saida", str(saida), "--cenario", cenario,
        "--fps", str(fps), "--max-duracao", str(max_duracao),
    ]
    if resolucao:
        comando += ["--resolucao", f"{int(resolucao[0])}x{int(resolucao[1])}"]
    elif portrait:
        comando.append("--portrait")
    if camera_modo:
        comando += ["--camera", camera_modo]
    if camera_largura_min:
        comando += ["--camera-largura-min", str(float(camera_largura_min))]
    if camera_espera_zoom:
        comando += ["--camera-espera-zoom", str(float(camera_espera_zoom))]
    if sem_hud:
        comando.append("--sem-hud")

    ambiente = dict(os.environ)
    ambiente.setdefault("SDL_VIDEODRIVER", "dummy")
    ambiente.setdefault("SDL_AUDIODRIVER", "dummy")
    ambiente.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    try:
        processo = subprocess.run(
            comando, cwd=str(RAIZ_PROJETOS), env=ambiente, timeout=timeout,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        return {"sucesso": False, "erro": f"gravacao passou de {timeout}s",
                "p1": p1, "p2": p2, "seed": seed}

    # O gravador imprime uma linha JSON; o pygame polui o stdout com o banner,
    # entao lemos a ultima linha que se parece com um objeto.
    for linha in reversed((processo.stdout or "").splitlines()):
        linha = linha.strip()
        if linha.startswith("{") and linha.endswith("}"):
            try:
                return json.loads(linha)
            except ValueError:
                continue
    return {"sucesso": False, "p1": p1, "p2": p2, "seed": seed,
            "erro": (processo.stderr or "gravador nao devolveu resultado")[-400:]}


def gravar_em_paralelo(tarefas: list[dict], *, trabalhadores: int = 3,
                       progresso=None) -> list[dict]:
    """Grava varias lutas ao mesmo tempo, preservando a ordem das tarefas.

    Cada tarefa e um dict com os argumentos de `gravar_uma`. O paralelismo e
    limitado porque cada subprocesso roda um motor de jogo inteiro.
    """
    if not tarefas:
        return []
    trabalhadores = max(1, min(trabalhadores, len(tarefas)))
    resultados: list[dict | None] = [None] * len(tarefas)
    feitas = 0

    with ThreadPoolExecutor(max_workers=trabalhadores) as executor:
        futuros = {executor.submit(gravar_uma, **tarefa): indice
                   for indice, tarefa in enumerate(tarefas)}
        for futuro, indice in futuros.items():
            try:
                resultados[indice] = futuro.result()
            except Exception as erro:
                resultados[indice] = {"sucesso": False, "erro": str(erro)}
            feitas += 1
            if progresso:
                progresso(feitas, len(tarefas), resultados[indice])
    return [r or {"sucesso": False, "erro": "sem resultado"} for r in resultados]
