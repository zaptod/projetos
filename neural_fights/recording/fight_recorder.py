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

Onda 16A (o som real do jogo)
-----------------------------
O driver de audio continua ``dummy``, mas o ``AudioManager`` da partida e um
``AnotadorDeAudio`` (``effects/audio_anotador.py``): cada som que o jogo
tocaria vira uma linha de ``sons`` (instante no relogio do video, chave,
volume, pitch). A mesma lista e misturada com os wav reais
(``effects/mixagem.py``) e entra no mp4 no lugar da trilha ``anullsrc`` — o
bruto ja sai com o som da luta. A luta nao muda com isso (ver o anotador).

Onda 16C (a timeline do palco)
------------------------------
Com ``timeline=CAMINHO`` (``--timeline``), a ``SondaTimeline``
(``recording/timeline.py``) amostra TODO passo, logo depois do ``update`` e
antes do ``desenhar``, e a luta sai tambem como timeline v1: o arquivo de que
o palco em Godot desenha a luta (docs/palco/timeline.md), com os ``sons``
acima na secao propria. A sonda so le: o teste compara um hash de estado por
passo com e sem ela.

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
import sys  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

import pygame  # noqa: E402

from neural_fights.utils.config import FPS, PPM  # noqa: E402

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Sobra gravada depois do KO: o slow-motion dura 1,2 s (``ativar_slow_motion``)
# e, quando ele acaba, toca a fanfarra de vitoria (``avancar_relogio``). Desde
# 14/10/2026 a cauda vai ate a fanfarra ACABAR (``cauda_pos_ko_de``): com 3,5 s
# fixos sobravam ~0,9 s de silencio depois dela (medido na seed 4242, Arena).
# CAUDA_POS_KO e so o que se usa quando o arquivo da fanfarra nao e achado.
CAUDA_POS_KO = 3.5
# Nunca menos que o slow-mo (1,2 s) + o letterbox do golpe letal.
CAUDA_MIN_POS_KO = 1.5
# Folga depois do ultimo sample da fanfarra (o arquivo ja termina no rabo dela).
FOLGA_POS_FANFARRA = 0.1
SOM_DA_VITORIA = "arena_victory"
SOM_FIM_DO_SLOWMO = "slowmo_end"

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


def duracao_do_som(id_som: str) -> float | None:
    """Segundos do arquivo que o jogo tocaria para ``id_som`` (None se nao ha).

    Mesma cadeia da mistura (``arquivos_de_som``: runtime > pacote >
    fallbacks): trocar a fanfarra pelo wav do Adrian muda a cauda junto.
    """
    try:
        from neural_fights.effects.audio_anotador import arquivos_de_som
        arquivo = arquivos_de_som().get(id_som)
    except Exception:
        return None
    if arquivo is None:
        return None
    arquivo = Path(arquivo)
    if arquivo.suffix.lower() == ".wav":
        import wave
        try:
            with wave.open(str(arquivo), "rb") as leitor:
                taxa = leitor.getframerate()
                if taxa > 0:
                    return leitor.getnframes() / float(taxa)
        except (wave.Error, OSError, EOFError):
            pass   # wav que o modulo wave nao le (float, extensivel): ffmpeg
    try:
        from neural_fights.effects import mixagem
        amostras = mixagem.decodificar(arquivo)
    except Exception:
        return None
    if amostras is None or not len(amostras):
        return None
    return len(amostras) / float(mixagem.TAXA)


def cauda_pos_ko_de(sim, *, padrao: float = CAUDA_POS_KO) -> float:
    """Quanto gravar depois do K.O.: ate a fanfarra de vitoria acabar.

    Chamada no quadro do K.O., quando o slow-mo acabou de ser armado: a
    fanfarra toca quando ``slow_mo_timer`` zera (relogio de parede, o mesmo
    do video). Sem o arquivo dela, ``padrao`` (os 3,5 s de sempre).
    O gravador e a timeline do palco usam esta MESMA conta: o palco confere
    que a imagem dele tem a duracao do clipe do pygame.
    """
    fanfarra = duracao_do_som(SOM_DA_VITORIA)
    if fanfarra is None:
        return float(padrao)
    # O ``slowmo_end`` toca no mesmo quadro: a cauda cobre o mais longo.
    fanfarra = max(fanfarra, duracao_do_som(SOM_FIM_DO_SLOWMO) or 0.0)
    espera = max(0.0, float(getattr(sim, "slow_mo_timer", 0.0) or 0.0))
    return round(max(CAUDA_MIN_POS_KO, espera + fanfarra + FOLGA_POS_FANFARRA), 3)


def anunciar_fim_da_festa(sim, cauda: float) -> None:
    """Diz ao desenho quanto a festa da vitoria vai durar no video.

    Chamada no quadro do K.O., junto com a conta da cauda: a festa comeca
    quando o slow-mo acaba e o video termina ``cauda`` s depois do K.O. O
    desenho usa isto para nao soltar uma rajada de confete recem-nascida no
    ultimo quadro (``Simulador._rajadas_vivas``). So desenho: nada da luta le.
    """
    espera = max(0.0, float(getattr(sim, "slow_mo_timer", 0.0) or 0.0))
    try:
        sim._festa_dura_s = max(0.0, float(cauda) - espera)
    except (AttributeError, TypeError, ValueError):
        pass


def validar_fps_e_duracao(fps: int, max_duracao: float) -> None:
    """Recusa o que gravaria errado (MOT-121, auditoria de 11/10/2026).

    O motor pensa a 60 Hz e o gravador captura um quadro a cada ``60 / fps``
    passos: so os divisores de 60 saem em tempo real (24 saia a 0,8x, 50 a
    0,83x, acima de 60 acelerava). ``fps < 1`` era laco infinito e
    ``max_duracao <= 0`` devolvia "sucesso" com 0 s.
    """
    if isinstance(fps, bool) or not isinstance(fps, int) or fps < 1 or FPS % fps:
        raise ValueError(f"fps precisa dividir {FPS} (10, 12, 15, 20, 30, 60): {fps!r}")
    if not (float(max_duracao) > 0):
        raise ValueError(f"max_duracao precisa ser maior que zero: {max_duracao!r}")


def tipo_fps(texto: str) -> int:
    """``type=`` do argparse para ``--fps``: so divisores de 60."""
    try:
        valor = int(texto)
        validar_fps_e_duracao(valor, 1.0)
    except ValueError as erro:
        raise argparse.ArgumentTypeError(str(erro)) from None
    return valor


def tipo_duracao(texto: str) -> float:
    """``type=`` do argparse para ``--max-duracao``: maior que zero."""
    try:
        valor = float(texto)
        validar_fps_e_duracao(FPS, valor)
    except ValueError as erro:
        raise argparse.ArgumentTypeError(str(erro)) from None
    return valor


def _abrir_ffmpeg(saida: Path, largura: int, altura: int, fps: int,
                  crf: int, preset: str) -> subprocess.Popen:
    """Pipe de frames crus para o ffmpeg.

    Mesmo formato de `random_builds/builds/video/renderer.py::_encode_frames`,
    inclusive a trilha silenciosa: manter os segmentos com video E audio e o
    que permite o `concat -c copy` do renderer funcionar depois.

    O stderr vai para um arquivo temporario (MOT-109): um pipe encheria e
    travaria o ffmpeg, e sem ele a falha (disco cheio, arquivo trancado) era
    engolida e o gravador dizia sucesso com um mp4 sem ``moov``.
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
    erros = tempfile.TemporaryFile()
    try:
        processo = subprocess.Popen(comando, stdin=subprocess.PIPE, stderr=erros,
                                    creationflags=NO_WINDOW)
    except Exception:
        erros.close()
        raise
    processo.arquivo_de_erros = erros
    return processo


def _stderr_do_ffmpeg(processo) -> str:
    """Os ultimos 800 caracteres do que o ffmpeg escreveu no stderr."""
    arquivo = getattr(processo, "arquivo_de_erros", None)
    if arquivo is None:
        fluxo = getattr(processo, "stderr", None)
        try:
            dados = fluxo.read() if fluxo is not None else b""
        except Exception:
            dados = b""
    else:
        try:
            arquivo.seek(0)
            dados = arquivo.read()
        except Exception:
            dados = b""
    if isinstance(dados, bytes):
        dados = dados.decode("utf-8", errors="replace")
    return str(dados or "").strip()[-800:]


def _escrever_quadro(processo, dados: bytes) -> None:
    """Escreve um quadro; pipe quebrado vira RuntimeError com o motivo do ffmpeg."""
    try:
        processo.stdin.write(dados)
    except (BrokenPipeError, OSError) as erro:
        try:
            processo.stdin.close()
        except (OSError, ValueError):
            pass
        try:
            processo.wait(timeout=30)
        except Exception:
            pass
        raise RuntimeError(f"ffmpeg falhou: {_stderr_do_ffmpeg(processo) or erro}") from erro


def _fechar_ffmpeg(processo, saida: Path | None) -> str | None:
    """Fecha o ffmpeg e devolve o erro (``None`` se o mp4 saiu inteiro)."""
    try:
        processo.stdin.close()
    except (OSError, ValueError):
        pass
    try:
        codigo = processo.wait(timeout=120)
    except subprocess.TimeoutExpired:
        processo.kill()
        processo.wait()
        codigo = "timeout"
    erro = None
    if codigo != 0:
        erro = f"ffmpeg saiu com {codigo}: {_stderr_do_ffmpeg(processo)}"
    elif saida is not None and (not Path(saida).exists() or Path(saida).stat().st_size == 0):
        erro = f"ffmpeg saiu com 0 mas o arquivo nao existe ou esta vazio: {saida}"
    arquivo = getattr(processo, "arquivo_de_erros", None)
    if arquivo is not None:
        try:
            arquivo.close()
        except Exception:
            pass
    return erro


def _embutir_som(saida: Path, sons: list, duracao: float) -> dict:
    """Troca a trilha silenciosa do mp4 pelo som anotado da luta.

    Nunca derruba a gravacao: sem numpy, sem som anotado ou com o ffmpeg
    falhando, o mp4 fica como estava (com ``anullsrc``) e a resposta diz
    ``som_no_video: False`` com o motivo. Quem renderiza continua tendo a
    lista ``sons`` para misturar na hora.
    """
    wav = saida.with_name(saida.stem + ".som.wav")
    tentativas: list[Path] = []
    try:
        from neural_fights.effects import mixagem
        if not mixagem.disponivel():
            return {"som_no_video": False, "erro_som": "numpy ausente"}
        if not sons:
            return {"som_no_video": False, "erro_som": "a luta nao pediu som nenhum"}
        estado: dict = {}

        def codificar(pico_db: float, nivel_db: float, indice: int):
            relatorio = mixagem.trilha_da_luta(
                sons, duracao, wav, teto=mixagem.TETO * 10 ** (pico_db / 20.0),
                alvo_db=mixagem.ALVO_DB + nivel_db)
            if relatorio is None:
                estado["erro"] = "nenhum som tinha arquivo"
                return None
            estado["relatorio"] = relatorio
            destino = saida.with_name(f"{saida.stem}.com_som{indice}{saida.suffix}")
            tentativas.append(destino)
            comando = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(saida),
                       "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                       "-c:a", "aac", "-b:a", "160k", "-shortest", str(destino)]
            proc = subprocess.run(comando, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  creationflags=NO_WINDOW)
            if proc.returncode != 0 or not destino.is_file():
                estado["erro"] = (proc.stderr or "ffmpeg falhou")[-300:]
                return None
            estado.setdefault("arquivos", len(relatorio.get("arquivos") or []))
            return destino

        # Teto de pico verdadeiro (14/10/2026): o aac passa do pico do wav
        # (-1,2 dBTP na seed 4242 da Arena). Mede o mp4 e refaz com o
        # limitador mais baixo, sem deixar o integrado cair.
        escolhida, historico = mixagem.com_teto_de_pico(codificar)
        if escolhida is None:
            return {"som_no_video": False, "erro_som": estado.get("erro") or "ffmpeg falhou"}
        Path(escolhida["caminho"]).replace(saida)
        return {"som_no_video": True,
                "sons_distintos": estado.get("arquivos", 0),
                "pico_verdadeiro_dbtp": escolhida.get("tp"),
                "lufs": escolhida.get("lufs"),
                "tentativas_de_pico": len(historico)}
    except Exception as erro:  # o video sem som ainda e um video
        return {"som_no_video": False, "erro_som": f"{type(erro).__name__}: {erro}"}
    finally:
        wav.unlink(missing_ok=True)
        for caminho in tentativas:
            caminho.unlink(missing_ok=True)


def _salvar_timeline(sonda_timeline, caminho, resumo: dict, sons) -> dict:
    """Fecha a timeline v1 (Onda 16C) e grava; nunca levanta."""
    try:
        from neural_fights.effects.audio_anotador import VERSAO_SONS
        from neural_fights.recording import timeline_arquivo

        if sons is not None:
            sonda_timeline.anexar_sons(sons, VERSAO_SONS)
        documento = sonda_timeline.documento(resultado=resumo)
        caminho = Path(caminho)
        compressao = "zstd" if caminho.suffix.lower() == ".gcpf" else None
        tamanho = timeline_arquivo.salvar(documento, caminho, compressao=compressao)
        return {"timeline": str(caminho), "timeline_bytes": tamanho,
                "timeline_passos": documento["n"]}
    except Exception as erro:
        return {"timeline": None, "erro_timeline": f"{type(erro).__name__}: {erro}"}


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
    cauda_pos_ko: float | None = None,
    hud: bool = True,
    crf: int = 20,
    preset: str = "veryfast",
    camera_modo: str | None = None,
    camera_largura_min_m: float | None = None,
    camera_espera_zoom_in: float | None = None,
    nomes_exibicao: dict | None = None,
    resolucao: tuple[int, int] | list[int] | str | None = None,
    roster_provider=None,
    anotar_som: bool = True,
    som_no_video: bool = True,
    timeline: str | Path | None = None,
    corrente_v2: bool | None = None,
    reserva_pos_ko: dict | None = None,
) -> dict:
    """Roda a luta desenhando cada frame e devolve o resultado + timestamps.

    A luta e deterministica pela seed: gravar a mesma seed duas vezes (uma por
    formato) produz exatamente a mesma luta enquadrada de dois jeitos.

    ``saida=None`` desenha tudo e mede tudo, mas nao codifica video — e o
    modo que o harness de qualidade usa para medir a camera (alvos V7) sem
    pagar o ffmpeg, e o que re-anota o som de uma luta ja gravada.

    ``anotar_som`` (Onda 16A) poe o ``AnotadorDeAudio`` no lugar do
    ``AudioManager`` e devolve ``sons``; ``som_no_video`` mistura essa lista
    com os wav reais e troca a trilha muda do mp4 por ela.

    ``timeline`` (Onda 16C) grava tambem a timeline v1 da luta nesse caminho:
    o contrato do palco (docs/palco/timeline.md), com a secao ``sons``
    preenchida pelo anotador. ``.gcpf`` sai no container comprimido que o
    Godot abre nativo (zstd); outro sufixo, JSON. O resultado leva o CAMINHO,
    nunca o documento (~1 MB). A timeline nunca derruba a gravacao: falha vira
    ``erro_timeline`` no resultado.

    ``corrente_v2`` carimba a chave da corrente nova (bola fisica + enlace)
    no match_config; ``None`` nao carimba e a luta usa a corrente antiga.

    ``cauda_pos_ko``: segundos gravados depois do K.O.; ``None`` (padrao) =
    ate a fanfarra de vitoria acabar (``cauda_pos_ko_de()``).
    """
    # Import tardio: o Simulador puxa pygame, e o driver precisa ja estar
    # escolhido (feito no topo do modulo).
    from neural_fights.simulation.simulacao import Simulador
    from neural_fights.effects.audio_anotador import VERSAO_SONS, AnotadorDeAudio

    validar_fps_e_duracao(fps_saida, max_duracao)
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
    # Corrente nova (core/corrente.py): so entra quando quem grava pede.
    # Ausente = a corrente antiga — e o que toda luta gravada antes usa, entao
    # a regeracao de uma luta antiga continua a mesma.
    if corrente_v2 is not None:
        match_config["corrente_v2"] = bool(corrente_v2)

    extras = {}
    if roster_provider is not None:
        extras["roster_provider"] = roster_provider
    # A seed da luta semeia o PITCH dos sons (Random proprio do anotador): a
    # mesma luta gravada de novo sai com o mesmo som.
    anotador = AnotadorDeAudio(seed=seed) if anotar_som else None
    if anotador is not None:
        anotador.passo = 0   # Onda 16C: o som tambem leva o passo exato (``i``)
        extras["audio"] = anotador
    sim = Simulador(match_config=match_config, headless=False, seed=seed, **extras)
    if reserva_pos_ko and getattr(sim, "cam", None) is not None:
        # so a camera da cauda le (Camera._topo_do_letreiro); nada da luta
        sim.cam.reserva_pos_ko = dict(reserva_pos_ko)
    sonda = SondaDeDano()
    narrativa = SondaNarrativa()
    camera = SondaCamera()
    sonda_timeline = None
    erro_timeline = None
    if timeline is not None:
        from neural_fights.recording.timeline import SondaTimeline
        sonda_timeline = SondaTimeline()
    ffmpeg = None
    try:
        largura, altura = sim.tela.get_size()
        recorte = _recorte_util(sim, largura, altura)
        if saida is not None:
            ffmpeg = _abrir_ffmpeg(saida, largura, altura, fps_saida, crf, preset)
        sonda.on_inicio(sim)
        if sonda_timeline is not None:
            sonda_timeline.on_inicio(sim, seed=seed, p1=p1, p2=p2, cenario=cenario)

        passo = 1.0 / FPS                       # o motor pensa a 60 Hz
        a_cada = max(1, round(FPS / fps_saida))  # 2 quadros de jogo por frame de video
        dt_video = 1.0 / fps_saida
        indice = 0
        capturados = 0
        t_jogo = 0.0
        t_ko_video: float | None = None
        cauda: float | None = None
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
            # Depois do K.O. nao ha plano: o HUD do video mostrava "ACABAR"
            # sob as barras a cauda inteira (conferente, 14/10/2026).
            if getattr(sim, "round_finalizado", False):
                return "", 0.0
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
            if anotador is not None:
                # O som pedido neste passo de jogo aparece no quadro que o
                # captura: o mesmo relogio de `eventos_dano`.
                anotador.t_video = t_video
                anotador.passo = indice

            pygame.event.pump()
            # avancar_relogio aplica o time_scale (simulacao.py:5513): durante
            # o slow-mo do KO o jogo anda menos por frame, e e assim que o
            # slow-mo aparece no video.
            dt = sim.avancar_relogio(passo)
            sim.update(dt)
            t_jogo += dt
            if sonda_timeline is not None:
                # Onda 16C: ANTES do desenhar(), que esvazia os impactos de
                # parede (arena.colisoes_recentes). A sonda so le.
                try:
                    sonda_timeline.on_frame(sim, t_video, t_jogo=t_jogo)
                except Exception as erro:  # a timeline nunca derruba o video
                    erro_timeline = f"{type(erro).__name__}: {erro}"
                    sonda_timeline = None
            sim.desenhar()   # 1:1 com update: desenhar() drena arena.limpar_colisoes()
            antes = len(sonda.eventos)
            sonda.on_frame(sim, t_video)
            narrativa.on_frame(sim, t_video, t_jogo, sonda.eventos[antes:] or None)

            if indice % a_cada == 0:
                if ffmpeg is not None:
                    _escrever_quadro(ffmpeg, pygame.image.tobytes(sim.tela, "RGB"))
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
                    cauda = (cauda_pos_ko_de(sim) if cauda_pos_ko is None
                             else float(cauda_pos_ko))
                    anunciar_fim_da_festa(sim, cauda)
                    # o plano some do HUD no quadro do K.O., nao na proxima
                    # amostra da serie
                    if serie_plano:
                        serie_plano.append((round(t_video, 3), "", 0.0, "", 0.0))
                elif t_video - t_ko_video >= cauda:
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
            # A chave da corrente que ESTA luta usou (carimbo ou padrao do
            # motor): quem grava o fight.json a guarda para re-simular igual.
            "corrente_v2": bool(getattr(sim, "corrente_v2", False)),
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
        if anotador is not None:
            resultado["sons"] = list(anotador.sons)
            resultado["versao_sons"] = VERSAO_SONS
        if timeline is not None:
            if sonda_timeline is None:
                resultado.update({"timeline": None, "erro_timeline": erro_timeline})
            else:
                resumo = {
                    "vencedor": resultado["vencedor"],
                    "vencedor_slot": getattr(sim, "vencedor_round_side", None),
                    "empate": empate,
                    "motivo": resultado["motivo"],
                    "duracao_jogo": resultado["duracao_jogo"],
                    "duracao_video": duracao_video,
                    "ko_em_video": resultado["ko_em_video"],
                    "passos": indice,
                    "quadros_video": capturados,
                    "passos_por_quadro": a_cada,
                    "hp_final": hp,
                    "seed": seed,
                }
                resultado.update(_salvar_timeline(
                    sonda_timeline, timeline, resumo,
                    resultado.get("sons") if anotador is not None else None))
        if ffmpeg is not None:
            # Fecha o video ANTES de trocar a trilha: o mp4 so existe inteiro
            # depois que o ffmpeg termina.
            processo, ffmpeg = ffmpeg, None
            erro_ffmpeg = _fechar_ffmpeg(processo, saida)
            if erro_ffmpeg is not None:
                # MOT-109: o codigo de saida era ignorado e um mp4 sem
                # ``moov`` (trailer que nao gravou) saia como sucesso.
                resultado["sucesso"] = False
                resultado["erro"] = erro_ffmpeg
                return resultado
            if anotador is not None and som_no_video:
                resultado.update(_embutir_som(saida, resultado["sons"], duracao_video))
        return resultado
    finally:
        if ffmpeg is not None:
            _fechar_ffmpeg(ffmpeg, None)
        sim.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Grava uma luta do Neural Fights em mp4, sem abrir janela")
    parser.add_argument("--p1", required=True)
    parser.add_argument("--p2", required=True)
    parser.add_argument("--saida", default=None,
                        help="arquivo .mp4 de saida (obrigatorio sem --sem-video)")
    parser.add_argument("--sem-video", action="store_true",
                        help="roda e desenha a luta sem codificar mp4: devolve "
                             "o resultado, os eventos e os sons anotados (e "
                             "assim que se anota o som de uma luta ja gravada)")
    parser.add_argument("--sem-som", action="store_true",
                        help="nao anota o som (o AudioManager de sempre) e "
                             "deixa a trilha muda no mp4")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--cenario", default="Arena Pequena")
    parser.add_argument("--portrait", action="store_true",
                        help="540x960 (9:16) em vez de 1200x800; prefira "
                             "--resolucao 1080x1920 --camera DIRETOR para video")
    parser.add_argument("--resolucao", default=None, metavar="LxA",
                        help="resolucao nativa da gravacao, ex. 1080x1920 "
                             "(a proporcao decide retrato/paisagem)")
    parser.add_argument("--fps", type=tipo_fps, default=30,
                        help="quadros por segundo; precisa dividir 60")
    parser.add_argument("--max-duracao", type=tipo_duracao, default=120.0)
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
    parser.add_argument("--timeline", default=None, metavar="CAMINHO",
                        help="grava tambem a timeline v1 do palco (Onda 16C); "
                             ".gcpf = container zstd que o Godot abre, senao JSON")
    # Chave da corrente nova (core/corrente.py). Nenhuma das duas = nao
    # carimba (vale o padrao do motor). Quem re-simula uma luta gravada passa
    # o que o fight.json guardou; luta antiga sem o campo = --sem-corrente-v2.
    chave = parser.add_mutually_exclusive_group()
    chave.add_argument("--corrente-v2", dest="corrente_v2", action="store_const", const=True,
                       default=None, help="carimba corrente_v2=True no match_config")
    chave.add_argument("--sem-corrente-v2", dest="corrente_v2", action="store_const", const=False,
                       help="carimba corrente_v2=False (a corrente antiga)")
    parser.add_argument("--reserva-pos-ko", type=tipo_reserva_pos_ko, default=None,
                        metavar="TOPO,SEGUNDOS[,HUD]",
                        help="letreiro do K.O. do video: borda de baixo (fracao da "
                             "altura) e quanto ele fica na tela depois do K.O.; a "
                             "camera DIRETOR da cauda poe o vencedor abaixo dele. "
                             "HUD (opcional): borda de baixo do HUD do video, que "
                             "fica a cauda inteira; o vencedor fica abaixo dele")
    return parser


def tipo_reserva_pos_ko(texto: str) -> dict:
    """``"0.27,0.9"`` -> ``{"topo": 0.27, "ate_s": 0.9}`` e
    ``"0.27,0.9,0.17"`` -> ``{..., "hud": 0.17}`` (argparse)."""
    try:
        valores = [float(v) for v in str(texto).split(",")]
    except ValueError:
        valores = []
    if len(valores) not in (2, 3):
        raise argparse.ArgumentTypeError(
            f"use TOPO,SEGUNDOS[,HUD] (ex. 0.27,0.9,0.17): {texto}") from None
    topo, ate = valores[0], valores[1]
    if not (0.0 <= topo < 1.0) or ate < 0:
        raise argparse.ArgumentTypeError(f"fora da faixa: {texto}")
    reserva = {"topo": topo, "ate_s": ate}
    if len(valores) == 3:
        if not (0.0 <= valores[2] < 1.0):
            raise argparse.ArgumentTypeError(f"HUD fora da faixa: {texto}")
        reserva["hud"] = valores[2]
    return reserva


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.sem_video and not args.saida:
        parser.error("--saida e obrigatorio (ou use --sem-video)")
    if args.resolucao and parse_resolucao(args.resolucao) is None:
        # MOT-122: "--resolucao 1080" virava a resolucao padrao em silencio
        parser.error(f"--resolucao invalida (use LxA, ex. 1080x1920): {args.resolucao}")
    try:
        resultado = gravar_luta(
            p1=args.p1, p2=args.p2,
            saida=None if args.sem_video else args.saida, seed=args.seed,
            cenario=args.cenario, portrait=args.portrait, fps_saida=args.fps,
            max_duracao=args.max_duracao, hud=not args.sem_hud,
            crf=args.crf, preset=args.preset, camera_modo=args.camera,
            camera_largura_min_m=args.camera_largura_min,
            camera_espera_zoom_in=args.camera_espera_zoom,
            resolucao=args.resolucao,
            anotar_som=not args.sem_som,
            timeline=args.timeline,
            corrente_v2=args.corrente_v2,
            reserva_pos_ko=args.reserva_pos_ko,
        )
    except Exception as erro:  # o chamador precisa do motivo, nao de um traceback
        resultado = {"sucesso": False, "erro": f"{type(erro).__name__}: {erro}",
                     "p1": args.p1, "p2": args.p2, "seed": args.seed}
    if args.resultado:
        Path(args.resultado).parent.mkdir(parents=True, exist_ok=True)
        Path(args.resultado).write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False))
    if not resultado.get("sucesso"):
        return 1
    # MOT-123: a timeline ou o som PEDIDOS que nao sairam davam exit 0.
    falta = resultado.get("erro_timeline") if args.timeline else None
    if not falta and args.timeline and resultado.get("timeline") is None:
        falta = "timeline pedida nao foi gravada"
    if not falta and not args.sem_som and not args.sem_video and resultado.get("som_no_video") is False:
        falta = f"som pedido nao entrou no video: {resultado.get('erro_som', '')}".strip()
    if falta:
        print(falta, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
