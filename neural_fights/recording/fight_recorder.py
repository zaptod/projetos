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

Onda 9 (a luta como video)
--------------------------
Alem do mp4, a gravacao devolve o material que a EDICAO precisa para tratar
a luta como elemento dominante, tudo em tempo de VIDEO:

- ``eventos_dano``        cada golpe (t, slot atingido, dano, categoria);
- ``serie_hp``            HP dos dois a cada 0,25 s (o HUD do video e
                          desenhado pelo renderer, na tipografia do canal);
- ``eventos_narrativos``  o que a Onda 8 tornou legivel — tells (instinto,
                          desvio, punicao, parry, clinch), combos, primeiro
                          sangue, viradas de lideranca e o nocaute — para
                          virar legenda sincronizada;
- ``metricas_video``      quanto da luta cabe na tela (Onda 9: alvos V7).

Uso:
    python -m neural_fights.recording.fight_recorder \\
        --p1 "Nome" --p2 "Outro" --seed 7 --saida luta.mp4 \\
        [--camera DIRETOR --resolucao 1080x1920 --sem-hud]

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
import math  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

import pygame  # noqa: E402

from neural_fights.utils.config import FPS, PPM  # noqa: E402

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Sobra gravada depois do KO: o slow-motion dura 1,2 s (simulacao.py:3739) e o
# letterbox cinematografico 0,9 s (:3584). Sem isso o video corta no meio da
# comemoracao.
CAUDA_POS_KO = 3.5

# Passo da serie de HP, em segundos de video. Mesmo passo da sonda de
# qualidade (probes.PASSO_HP): o drama acontece em escala de segundos.
PASSO_SERIE_HP = 0.25

# Lideranca so conta depois da aproximacao e com histerese (probes.py).
IGNORAR_LIDERANCA_ATE = 3.0
HISTERESE_LIDERANCA = 0.05

# Tells que viram evento narrativo. "hesitacao" fica de fora: e sinal
# interno da IA, nao momento que o espectador comemora. Onda 10A: agarrao,
# wall-splat e iniciativa sao momentos de arena (o callout le "modo").
TELLS_NARRATIVOS = frozenset({
    "instinto", "desvio", "punicao", "parry", "clinch",
    "agarrao", "wall_splat", "iniciativa",
    # Onda 10C: o plano de luta e sinal PUBLICO (rotulo sob o lutador); a
    # troca vira evento com throttle por lutador (PLANO_GAP_MIN_S).
    "plano",
    # Onda 10D: obstaculo destruido por skill/arremesso.
    "obstaculo",
})

# Onda 10C: intervalo minimo entre dois eventos "plano" do mesmo lutador.
PLANO_GAP_MIN_S = 4.0

CAMERAS = ("ARENA", "AUTO", "DIRETOR", "P1", "P2")


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


class SondaNarrativa:
    """Momentos legiveis da luta, em tempo de video.

    Le apenas estado que o motor JA expõe para o renderer (``brain.tell_atual``,
    ``Lutador.combo_contra``, vida) — a mesma doutrina da sonda de qualidade:
    passiva, nunca altera combate. Cada evento e um dict::

        {"t": 12.4, "tipo": "parry", "slot": "p2"}
        {"t": 20.1, "tipo": "combo", "slot": "p1", "n": 4}     # p1 SOFRE o combo
        {"t": 23.0, "tipo": "virada", "slot": "p2"}            # p2 assume a lideranca
        {"t": 31.2, "tipo": "ko", "slot": "p1"}                # p1 vence

    ``slot`` e sempre o lutador a quem o momento pertence; quem monta a
    legenda decide como falar dele.
    """

    def __init__(self) -> None:
        self.eventos: list[dict] = []
        self._ultimo_tell: dict[str, tuple] = {"p1": (), "p2": ()}
        self._ultimo_plano_t: dict[str, float] = {"p1": -99.0, "p2": -99.0}
        self._combo_max: dict[str, int] = {"p1": 0, "p2": 0}
        self._lider: str | None = None
        self._primeiro_sangue = False
        self._ko = False
        self._proxima_amostra = 0.0

    def on_frame(self, sim, t_video: float, t_jogo: float,
                 golpes_no_frame: list[tuple[float, str, float, str]] | None = None) -> None:
        t = round(t_video, 3)
        if golpes_no_frame and not self._primeiro_sangue:
            self._primeiro_sangue = True
            atingido = golpes_no_frame[0][1]
            self.eventos.append({"t": t, "tipo": "primeiro_sangue",
                                 "slot": "p2" if atingido == "p1" else "p1"})

        for slot in ("p1", "p2"):
            lutador = getattr(sim, slot, None)
            if lutador is None:
                continue
            brain = getattr(lutador, "brain", None)
            tell = getattr(brain, "tell_atual", None) if brain is not None else None
            if isinstance(tell, dict):
                tipo = str(tell.get("tipo", ""))
                chave = (tipo, tell.get("ate"))
                ativo = getattr(brain, "tempo_combate", 0.0) < float(tell.get("ate", 0.0) or 0.0)
                if ativo and tipo in TELLS_NARRATIVOS and chave != self._ultimo_tell[slot]:
                    self._ultimo_tell[slot] = chave
                    evento = {"t": t, "tipo": tipo, "slot": slot}
                    emitir = True
                    # Onda 10A: o agarrao tem dois tells (lock e desfecho);
                    # so o desfecho (com "modo") vira evento.
                    if tipo == "agarrao":
                        if tell.get("modo"):
                            evento["modo"] = str(tell.get("modo"))
                            evento["papel"] = str(tell.get("papel", ""))
                        else:
                            emitir = False
                    # Onda 10C: troca de plano leva o rotulo; no maximo uma a
                    # cada PLANO_GAP_MIN_S por lutador (o callout nao vira spam).
                    elif tipo == "plano":
                        if t - self._ultimo_plano_t[slot] < PLANO_GAP_MIN_S:
                            emitir = False
                        else:
                            self._ultimo_plano_t[slot] = t
                            evento["plano"] = str(tell.get("plano", ""))
                            evento["rotulo"] = str(tell.get("rotulo", "") or "")
                            evento["adaptativo"] = bool(tell.get("adaptativo", False))
                    if emitir:
                        self.eventos.append(evento)

            n = int(getattr(lutador, "combo_contra", 0) or 0)
            timer = float(getattr(lutador, "combo_contra_timer", 0.0) or 0.0)
            if n >= 2 and timer > 0.0:
                if n > self._combo_max[slot]:
                    self._combo_max[slot] = n
                    self.eventos.append({"t": t, "tipo": "combo", "slot": slot, "n": n})
            elif timer <= 0.0 or n < 2:
                self._combo_max[slot] = 0

        if t_jogo >= self._proxima_amostra:
            self._proxima_amostra = t_jogo + PASSO_SERIE_HP
            self._amostrar_lideranca(sim, t, t_jogo)

        if not self._ko and getattr(sim, "round_finalizado", False):
            self._ko = True
            lado = getattr(sim, "vencedor_round_side", None)
            self.eventos.append({"t": t, "tipo": "ko", "slot": lado})

    def _amostrar_lideranca(self, sim, t: float, t_jogo: float) -> None:
        if t_jogo < IGNORAR_LIDERANCA_ATE:
            return
        try:
            r1 = max(0.0, float(sim.p1.vida)) / max(1e-9, float(sim.p1.vida_max))
            r2 = max(0.0, float(sim.p2.vida)) / max(1e-9, float(sim.p2.vida_max))
        except AttributeError:
            return
        diff = r1 - r2
        if diff > HISTERESE_LIDERANCA:
            candidato = "p1"
        elif diff < -HISTERESE_LIDERANCA:
            candidato = "p2"
        else:
            return
        if self._lider is not None and candidato != self._lider:
            self.eventos.append({"t": t, "tipo": "virada", "slot": candidato})
        self._lider = candidato


class SondaCamera:
    """Quanto da luta cabe na tela (Onda 9, alvos V7).

    Amostrada a cada frame CAPTURADO (o que o espectador ve), nunca por frame
    de jogo. ``pan`` e medido em larguras de tela por segundo — independe da
    resolucao, entao 540p e 1080p sao comparaveis.
    """

    def __init__(self) -> None:
        self.frames = 0
        self.visiveis = 0
        self.diametros: list[float] = []
        self.pans: list[float] = []
        self.zoom_trocas = 0
        self._ultimo: tuple[float, float, float] | None = None
        self._direcao_zoom = 0

    def on_frame(self, sim, dt_video: float) -> None:
        cam = getattr(sim, "cam", None)
        if cam is None:
            return
        self.frames += 1
        largura = max(1, int(getattr(cam, "screen_width", 1)))
        p1, p2 = getattr(sim, "p1", None), getattr(sim, "p2", None)
        try:
            if cam._lutador_visivel(p1) and cam._lutador_visivel(p2):
                self.visiveis += 1
            for lutador in (p1, p2):
                # O DIAMETRO que o espectador ve. `desenhar_lutador` pinta o
                # corpo com raio `dados.tamanho / 2` (simulacao.py), enquanto
                # `raio_fisico` e `tamanho / 4` — metade disso. Ate 10/09/2026
                # esta sonda media `2 * raio_fisico`, que e o RAIO desenhado, e
                # reportava o corpo pela METADE: o alvo V7 de 0.08 valia na
                # pratica 0.16, e o comentario do runner citava "8-10%" quando
                # o corpo ocupava 16-20%. Ler `dados.tamanho` tira a
                # indirecao que causou o engano.
                diametro = float(lutador.dados.tamanho) * PPM * cam.zoom
                self.diametros.append(diametro / largura)
        except Exception:
            pass
        atual = (float(cam.x), float(cam.y), float(cam.zoom))
        if self._ultimo is not None and dt_video > 0:
            dx = (atual[0] - self._ultimo[0]) * atual[2]
            dy = (atual[1] - self._ultimo[1]) * atual[2]
            self.pans.append(math.hypot(dx, dy) / largura / dt_video)
            dz = atual[2] - self._ultimo[2]
            if abs(dz) > 1e-4:
                direcao = 1 if dz > 0 else -1
                if self._direcao_zoom and direcao != self._direcao_zoom:
                    self.zoom_trocas += 1
                self._direcao_zoom = direcao
        self._ultimo = atual

    def resumo(self, duracao_video: float) -> dict:
        def _percentil(valores: list[float], p: float) -> float | None:
            if not valores:
                return None
            ordenados = sorted(valores)
            indice = min(len(ordenados) - 1, max(0, int(round(p * (len(ordenados) - 1)))))
            return ordenados[indice]

        minutos = max(1e-9, duracao_video / 60.0)
        d50 = _percentil(self.diametros, 0.5)
        d10 = _percentil(self.diametros, 0.1)
        return {
            "frames": self.frames,
            "pct_frames_visiveis": (self.visiveis / self.frames) if self.frames else None,
            "diametro_lutador_p50": d50,
            "diametro_lutador_p10": d10,
            # Aliases obsoletos (10/09/2026): sao o RAIO desenhado, que e o que
            # as chaves antigas sempre entregaram apesar do nome. Ficam uma
            # onda para nao quebrar leitor externo em silencio; saem na 16.
            "tamanho_lutador_p50": None if d50 is None else d50 / 2.0,
            "tamanho_lutador_p10": None if d10 is None else d10 / 2.0,
            "pan_p50_larguras_s": _percentil(self.pans, 0.5),
            "pan_p90_larguras_s": _percentil(self.pans, 0.9),
            "zoom_trocas_por_min": self.zoom_trocas / minutos,
        }


def _recorte_util(sim, largura: int, altura: int) -> list[int] | None:
    """Onde a arena (mais o HUD) fica no quadro, em pixels.

    So faz sentido com a camera TRAVADA na arena (modo ARENA): a arena ocupa
    exatamente o mesmo retangulo em todos os frames. Em 9:16 ela deixa faixas
    vazias enormes em cima e embaixo, e quem monta o video pode aparar esse
    excedente sem mexer na camera nem cortar nada da luta. Com camera movel
    (AUTO/DIRETOR) nao ha retangulo fixo — devolve None.

    Devolve [x, y, largura, altura] ou None se nao der para calcular.
    """
    camera = getattr(sim, "cam", None)
    arena = getattr(sim, "arena", None)
    if camera is None or arena is None or getattr(camera, "arena_centro", None) is None:
        return None
    if str(getattr(camera, "modo", "ARENA")).upper() != "ARENA":
        return None
    try:
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

    Mesmo formato de `random_builds/builds/video/renderer.py::_encode_frames`,
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


def parse_resolucao(valor) -> tuple[int, int] | None:
    """"1080x1920" | [1080, 1920] -> (1080, 1920); None se invalido."""
    if not valor:
        return None
    try:
        if isinstance(valor, str):
            partes = valor.lower().replace("x", " ").split()
        else:
            partes = list(valor)
        largura, altura = int(partes[0]), int(partes[1])
    except (TypeError, ValueError, IndexError):
        return None
    if largura < 64 or altura < 64:
        return None
    return largura // 2 * 2, altura // 2 * 2


def gravar_luta(
    *,
    p1: str,
    p2: str,
    saida: str | Path | None,
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
    camera_largura_min_m: float | None = None,
    camera_espera_zoom_in: float | None = None,
    nomes_exibicao: dict | None = None,
    resolucao: tuple[int, int] | list[int] | str | None = None,
    roster_provider=None,
) -> dict:
    """Roda a luta desenhando cada frame e devolve o resultado + timestamps.

    A luta e deterministica pela seed: gravar a mesma seed duas vezes (uma por
    formato) produz exatamente a mesma luta enquadrada de dois jeitos.

    ``saida=None`` desenha tudo e mede tudo, mas nao codifica video — e o
    modo que o harness de qualidade usa para medir a camera (alvos V7) sem
    pagar o ffmpeg.
    """
    # Import tardio: o Simulador puxa pygame, e o driver precisa ja estar
    # escolhido (feito no topo do modulo).
    from neural_fights.simulation.simulacao import Simulador

    saida = Path(saida) if saida is not None else None
    resolucao = parse_resolucao(resolucao)
    match_config = {
        "p1_nome": p1,
        "p2_nome": p2,
        "cenario": cenario,
        "best_of": 1,
        "portrait_mode": bool(portrait) if resolucao is None else resolucao[1] > resolucao[0],
        # Suprime o placar de serie e o cartaz "Pressione R" — sao para quem
        # joga, nao para quem assiste ao video (simulacao.py:3971 e :3983).
        "modo_live": True,
        # analise=True QUEBRA: desenhar_analise monta pygame.Surface com uma
        # tupla de 3 elementos (simulacao.py:5434).
        "overlays": {"hud": bool(hud), "analise": False, "hitbox_debug": False},
    }
    if resolucao is not None:
        match_config["resolucao"] = list(resolucao)
    # ARENA (padrao) trava a arena inteira; DIRETOR e a camera de video (Onda
    # 9); AUTO e a camera de jogo. Medido: nenhum modo muda o resultado da
    # luta, so o que aparece na tela.
    if camera_modo:
        match_config["camera_modo"] = str(camera_modo).upper()
    # Onda 15C: so o DUELO fecha mais que o default de 7,0 m da classe
    # Camera. Passar por match_config (e nao mexer no default) e o que
    # mantem estreia e torneio com o enquadramento que ja foi medido.
    if camera_largura_min_m:
        match_config["camera_largura_min_m"] = float(camera_largura_min_m)
    if camera_espera_zoom_in:
        match_config["camera_espera_zoom_in"] = float(camera_espera_zoom_in)
    if nomes_exibicao:
        match_config["nomes_exibicao"] = dict(nomes_exibicao)

    extras = {}
    if roster_provider is not None:
        extras["roster_provider"] = roster_provider
    sim = Simulador(match_config=match_config, headless=False, seed=seed, **extras)
    sonda = SondaDeDano()
    narrativa = SondaNarrativa()
    camera = SondaCamera()
    ffmpeg = None
    try:
        largura, altura = sim.tela.get_size()
        recorte = _recorte_util(sim, largura, altura)
        if saida is not None:
            ffmpeg = _abrir_ffmpeg(saida, largura, altura, fps_saida, crf, preset)
        sonda.on_inicio(sim)

        passo = 1.0 / FPS                       # o motor pensa a 60 Hz
        a_cada = max(1, round(FPS / fps_saida))  # 2 quadros de jogo por frame de video
        dt_video = 1.0 / fps_saida
        indice = 0
        capturados = 0
        t_jogo = 0.0
        t_ko_video: float | None = None
        # Duracao DA LUTA = tempo de jogo ate o nocaute. A cauda gravada
        # depois dele (slow-mo + letterbox) e do video, nao da luta; incluir
        # a faria divergir do que o motor headless reporta.
        duracao_luta: float | None = None
        serie_hp: list[tuple[float, float, float]] = []
        # Onda 10C: rotulo e progresso do plano de cada lado, na mesma
        # cadencia da serie de HP — o HUD do video mostra o plano vivo.
        serie_plano: list[tuple] = []
        proxima_amostra_hp = 0.0

        def _plano(lutador):
            brain = getattr(lutador, "brain", None)
            plano = getattr(brain, "plano", None) if brain is not None else None
            if plano is None:
                return "", 0.0
            rotulo = str(getattr(plano, "rotulo", "") or "")
            try:
                progresso = round(float(getattr(plano, "progresso", 0.0) or 0.0), 2)
            except (TypeError, ValueError):
                progresso = 0.0
            return rotulo, progresso

        def _razao(lutador) -> float:
            maximo = max(1e-9, float(lutador.vida_max))
            return max(0.0, float(lutador.vida)) / maximo

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
            antes = len(sonda.eventos)
            sonda.on_frame(sim, t_video)
            narrativa.on_frame(sim, t_video, t_jogo, sonda.eventos[antes:] or None)

            if indice % a_cada == 0:
                if ffmpeg is not None:
                    ffmpeg.stdin.write(pygame.image.tobytes(sim.tela, "RGB"))
                camera.on_frame(sim, dt_video)
                if t_video >= proxima_amostra_hp:
                    proxima_amostra_hp = t_video + PASSO_SERIE_HP
                    serie_hp.append((round(t_video, 3),
                                     round(_razao(sim.p1) * 100, 1),
                                     round(_razao(sim.p2) * 100, 1)))
                    r1, g1 = _plano(sim.p1)
                    r2, g2 = _plano(sim.p2)
                    serie_plano.append((round(t_video, 3), r1, g1, r2, g2))
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

        hp = {"p1": round(_razao(sim.p1) * 100, 1), "p2": round(_razao(sim.p2) * 100, 1)}
        duracao_video = round(capturados / fps_saida, 2)
        # A ultima amostra fecha a serie no HP final: o HUD do video termina
        # exatamente onde o placar diz que terminou.
        if not serie_hp or serie_hp[-1][0] < duracao_video:
            serie_hp.append((duracao_video, hp["p1"], hp["p2"]))
        resultado = {
            "sucesso": True,
            "p1": p1,
            "p2": p2,
            "vencedor": None if empate else vencedor,
            "perdedor": perdedor,
            "empate": empate,
            "motivo": "knockout" if t_ko_video is not None else "time_limit",
            "duracao_jogo": round(duracao_luta if duracao_luta is not None else t_jogo, 2),
            "duracao_video": duracao_video,
            "ko_em_video": round(t_ko_video, 2) if t_ko_video is not None else None,
            "hp_final": hp,
            "hp_vencedor": None if empate else hp["p1" if vencedor == p1 else "p2"],
            "seed": seed,
            "cenario": cenario,
            "portrait": bool(match_config["portrait_mode"]),
            "resolucao": [largura, altura],
            "camera_modo": str(getattr(sim.cam, "modo", "ARENA")),
            "hud": bool(hud),
            "recorte_util": recorte,
            "fps": fps_saida,
            "arquivo": str(saida) if saida is not None else None,
            "eventos_dano": sonda.eventos,
            "serie_hp": serie_hp,
            "serie_plano": serie_plano,
            "eventos_narrativos": narrativa.eventos,
            "metricas_video": camera.resumo(duracao_video),
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
                        help="540x960 (9:16) em vez de 1200x800; prefira "
                             "--resolucao 1080x1920 --camera DIRETOR para video")
    parser.add_argument("--resolucao", default=None, metavar="LxA",
                        help="resolucao nativa da gravacao, ex. 1080x1920 "
                             "(a proporcao decide retrato/paisagem)")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--max-duracao", type=float, default=120.0)
    parser.add_argument("--sem-hud", action="store_true",
                        help="sem as barras do jogo (o video desenha as suas)")
    parser.add_argument("--crf", type=int, default=20)
    parser.add_argument("--preset", default="veryfast")
    parser.add_argument("--camera-largura-min", type=float, default=None,
                        metavar="METROS",
                        help="quao fechado o DIRETOR pode chegar, em metros "
                             "de largura visivel (padrao da classe: 7.0)")
    parser.add_argument("--camera-espera-zoom", type=float, default=None,
                        metavar="SEGUNDOS",
                        help="estabilidade exigida antes de FECHAR o quadro "
                             "(padrao da classe: 1.5). Quadro mais fechado "
                             "precisa de mais, senao vira sanfona")
    parser.add_argument("--camera", default=None, choices=CAMERAS,
                        help="enquadramento; ausente = ARENA (arena inteira). "
                             "DIRETOR = camera de transmissao para video")
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
            camera_largura_min_m=args.camera_largura_min,
            camera_espera_zoom_in=args.camera_espera_zoom,
            resolucao=args.resolucao,
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
