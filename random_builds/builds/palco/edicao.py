"""16G, a primeira metade: a EDICAO do duelo por cima do clipe do palco.

O duelo publicado e um evento so (`tournament/duelo.py`): o clipe da luta com
HUD, identidade, callouts, veredito, o som da luta (16A) e a musica, montado
pelo `VideoRenderer`. Para o Adrian aprovar a troca, o lado B tem de ser o
MESMO video com so o desenho da luta trocado. Entao aqui nada e remontado:

1. a luta e re-simulada pela seed do `fight.json` (e tem de dar o mesmo
   vencedor e a mesma duracao, senao e erro — o banco mudou?);
2. o palco desenha essa timeline com o MESMO corte de tedio do duelo, SEM o
   HUD dele (o HUD e o da edicao, como no A);
3. o `edit_plan.json` do duelo e copiado e so muda o que tem hora: o hitstop
   do render (ligado pela decisao `hitstop`) para a imagem por 1-4 quadros em
   cada acerto forte, e tudo o que vem depois anda o mesmo tanto — barras de
   vida, plano, callouts, sons da luta, veredito;
4. o `VideoRenderer` de sempre monta o B com a musica escolhida pela mesma
   seed. O A e o `final_<perfil>.mp4` do duelo, intocado.

Nada disto publica nem entra no catalogo: sai em outputs/_palco/g16_<duelo>/.
A troca do duelo de producao so vem depois da decisao do Adrian.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import subprocess
import sys
from pathlib import Path

from . import ab, checagens, config, fonte, plano, render
from .config import ErroPalco

FPS = 30


class Relogio:
    """Instante do clipe SEM hitstop -> instante do video do palco."""

    def __init__(self, paradas: dict[int, int] | None = None, fps: int = FPS):
        self.paradas = {int(b): int(q) for b, q in (paradas or {}).items() if int(q) > 0}
        self.fps = fps

    @property
    def extra_s(self) -> float:
        return sum(self.paradas.values()) / self.fps

    def __call__(self, t) -> float:
        return round(float(t) + plano.atraso_de_hitstop(self.paradas, float(t), self.fps), 3)


def _serie(serie, relogio: Relogio) -> list:
    return [[relogio(a[0]), *list(a[1:])] for a in serie or [] if isinstance(a, (list, tuple)) and a]


def luta_no_relogio_do_palco(luta: dict, relogio: Relogio, *, perfil: str, clipe: Path,
                             duracao: float) -> dict:
    """A luta com o clipe do palco no perfil e as horas levadas ao relogio dele.

    So o perfil pedido fica em `clipes`: o duelo usa a duracao do MAIOR clipe,
    e o do outro perfil ainda e o do pygame."""
    nova = copy.deepcopy(luta)
    velho = (luta.get("clipes") or {}).get(perfil)
    if not velho:
        raise ErroPalco(f"a luta nao tem clipe do perfil {perfil}")
    nova["clipes"] = {perfil: {**velho, "path": str(clipe), "duracao": round(float(duracao), 3),
                               "palco": True}}
    for chave in ("serie_hp", "serie_plano", "eventos_dano"):
        if isinstance(nova.get(chave), list):
            nova[chave] = _serie(nova[chave], relogio)
    for chave in ("sons", "eventos_narrativos"):
        if isinstance(nova.get(chave), list):
            nova[chave] = [{**item, "t": relogio(item.get("t", 0.0))} if isinstance(item, dict) else item
                           for item in nova[chave]]
    if nova.get("ko_em_clipe") is not None:
        nova["ko_em_clipe"] = relogio(nova["ko_em_clipe"])
    if nova.get("duracao_clipe") is not None:
        nova["duracao_clipe"] = round(float(duracao), 3)
    return nova


def edicao_sobre_o_palco(edit_plan: dict, fight: dict, *, clipe: Path, duracao: float,
                         relogio: Relogio, perfil: str = "celular") -> tuple[dict, dict]:
    """(plano B, fight B): a edicao do A, com o clipe do palco e o relogio dele."""
    eventos = edit_plan.get("events") or []
    if len(eventos) != 1 or eventos[0].get("type") != "gameplay":
        raise ErroPalco("a edicao sobre o palco e a do DUELO: um evento so, de gameplay")
    plano_b = copy.deepcopy(edit_plan)
    ev = plano_b["events"][0]
    dur_a = float(ev["duration"])
    duracao = round(float(duracao), 3)
    ev["asset"] = {**ev["asset"], "path": str(clipe), f"path_{perfil}": str(clipe)}
    for outro in [k for k in ev["asset"] if k.startswith("path_") and k != f"path_{perfil}"]:
        ev["asset"].pop(outro)
    for chave in [k for k in ev if k.startswith("crop")]:
        ev.pop(chave)                      # o palco ja sai no quadro do perfil
    ev["duration"] = duracao
    plano_b["total_duration"] = duracao
    hud = ev.get("hud")
    if isinstance(hud, dict):
        for chave in ("serie_hp", "serie_plano"):
            if isinstance(hud.get(chave), list):
                hud[chave] = _serie(hud[chave], relogio)
    for callout in ev.get("callouts") or []:
        callout["t"] = relogio(callout.get("t", 0.0))
    ver = ev.get("veredito")
    if isinstance(ver, dict) and ver.get("de") is not None:
        # o veredito fica o MESMO tanto antes do fim (e o ultimo quadro que muda)
        ver["de"] = round(max(0.0, duracao - (dur_a - float(ver["de"]))), 3)
    ev["luta"] = luta_no_relogio_do_palco(ev["luta"], relogio, perfil=perfil, clipe=clipe, duracao=duracao)
    ev["palco"] = {"hitstop_quadros": sum(relogio.paradas.values()), "duracao_a": dur_a}

    fight_b = copy.deepcopy(fight)
    fight_b["luta"] = ev["luta"]
    if fight_b.get("lutas"):
        fight_b["lutas"] = [*fight_b["lutas"][:-1], ev["luta"]]
    return plano_b, fight_b


# ------------------------------------------------------------------ medidas
def _executar(comando: list, timeout: float = 600) -> str:
    feito = subprocess.run([str(c) for c in comando], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, creationflags=checagens.SEM_JANELA)
    return feito.stderr or ""


def imagem_parada_ou_preta(mp4: Path, *, congelado_s: float = 0.5) -> dict:
    """Trechos pretos (blackdetect) e congelados (freezedetect) do video."""
    texto = _executar(["ffmpeg", "-v", "info", "-nostats", "-i", mp4, "-an", "-vf",
                       f"blackdetect=d=0.1:pix_th=0.10,freezedetect=n=0.003:d={congelado_s}",
                       "-f", "null", "-"])
    pretos = [[float(a), float(b)] for a, b in
              re.findall(r"black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)", texto)]
    inicios = [float(x) for x in re.findall(r"freeze_start:\s*([\d.]+)", texto)]
    fins = [float(x) for x in re.findall(r"freeze_end:\s*([\d.]+)", texto)]
    congelados = [[a, fins[k] if k < len(fins) else None] for k, a in enumerate(inicios)]
    return {"pretos": pretos, "congelados": congelados}


def medir_video(mp4: Path) -> dict:
    from ..pipeline import sonorizar
    info = checagens.sonda(mp4)
    video = next((s for s in info.get("streams") or [] if s.get("codec_type") == "video"), {})
    audio = next((s for s in info.get("streams") or [] if s.get("codec_type") == "audio"), None)
    nivel = checagens.loudness(mp4) if audio else {}
    trecho = sonorizar.medir_trecho(mp4) or {}
    return {"arquivo": str(mp4), "resolucao": [video.get("width"), video.get("height")],
            "quadros": int(video.get("nb_frames") or 0),
            "duracao": round(float((info.get("format") or {}).get("duration") or 0.0), 3),
            "audio": audio is not None, "lufs": nivel.get("lufs"), "pico_dbfs": nivel.get("pico_dbfs"),
            "media_db": trecho.get("media_db"), "calado": trecho.get("calado"),
            **imagem_parada_ou_preta(mp4)}


def comparar_eventos(fight: dict, doc: dict, remap) -> dict:
    """Os golpes e o K.O. do A (clipe do pygame) contra os da timeline no
    relogio-base do palco (antes do hitstop). Diferenca em segundos."""
    luta = fight["luta"]
    duracao = int(doc["n"]) / int(doc["hz"])
    # Por MOMENTO (instante, alvo), e nao por golpe: o gravador anota cada
    # projetil de uma rajada que acerta no mesmo passo (3 linhas iguais), a
    # timeline um evento por passo. Medido no duelo_00031: 131 x 113 linhas,
    # e todo momento da timeline existe no A.
    momentos_b = set()
    for t_grav, alvo, *_ in fonte.eventos_de_dano(doc):
        q = plano.mapear(t_grav, duracao, remap)
        if q >= 0:
            momentos_b.add((round(q / FPS, 3), alvo))
    momentos_a = {(round(float(e[0]), 3), e[1]) for e in luta.get("eventos_dano") or []}

    def mais_perto(t, alvo, outros):
        return min((abs(t - u) for u, quem in outros if quem == alvo), default=None)

    tolerancia = 1.0 / FPS + 1e-6
    dif_a = [mais_perto(t, alvo, momentos_b) for t, alvo in momentos_a]
    dif_b = [mais_perto(t, alvo, momentos_a) for t, alvo in momentos_b]
    diffs = [d for d in dif_a + dif_b if d is not None]
    res = doc.get("resultado") or {}
    ko_b = None
    if res.get("ko_em_video") is not None:
        q = plano.mapear(float(res["ko_em_video"]), duracao, remap)
        ko_b = None if q < 0 else round(q / FPS, 3)
    return {"linhas_a": len(luta.get("eventos_dano") or []), "momentos_a": len(momentos_a),
            "momentos_b": len(momentos_b),
            "so_no_a": sum(1 for d in dif_a if d is None or d > tolerancia),
            "so_no_b": sum(1 for d in dif_b if d is None or d > tolerancia),
            "maior_diferenca_s": round(max(diffs), 3) if diffs else None,
            "ko_a": luta.get("ko_em_clipe"), "ko_b": ko_b}


class _Espelho(io.TextIOBase):
    """stdout duplicado: mostra E guarda (para pegar o 'composto falhou')."""

    def __init__(self, destino):
        self.destino, self.texto = destino, []

    def write(self, s):
        self.texto.append(s)
        return self.destino.write(s)

    def flush(self):
        self.destino.flush()


def ab_com_edicao(duelo_id: str, *, pasta: Path | None = None, perfil: str = "celular") -> dict:
    """A (o duelo como esta) x B (palco + a mesma edicao): mp4s, lado a lado e medidas."""
    if perfil != "celular":
        raise ErroPalco("o palco so desenha 9:16 (viewport 1080x1920); o 16:9 e da segunda metade da 16G")
    from ..generation.random_engine import RandomEngine
    from ..pipeline.controller import PipelineController
    from ..video.renderer import VideoRenderer

    cfg = config.carregar()
    pasta_duelo = config.OUTPUTS / duelo_id
    fight = json.loads((pasta_duelo / "fight.json").read_text(encoding="utf-8"))
    edit_plan = json.loads((pasta_duelo / "edit_plan.json").read_text(encoding="utf-8"))
    luta = fight["luta"]
    final_a = pasta_duelo / f"final_{perfil}.mp4"
    if not final_a.is_file():
        raise ErroPalco(f"{duelo_id} nao tem final_{perfil}.mp4")
    if not isinstance(luta.get("sons"), list):
        raise ErroPalco(f"{duelo_id} e de antes do som real (sem luta.sons): o A nao teria o som de hoje")
    trechos = [[float(a), float(b), 1.0] for a, b in (luta.get("clipes") or {}).get(perfil, {}).get("trechos") or []]
    duelo_cfg = cfg.get("duelo") or {}
    print(f"[16G] {duelo_id}: {luta['p1']} x {luta['p2']} | seed {luta['seed']} | {luta['cenario']}", flush=True)
    doc, _ = fonte.timeline_da_luta(p1=luta["p1"], p2=luta["p2"], seed=int(luta["seed"]), cenario=luta["cenario"],
                                    tentativas=1, camera_largura_min_m=duelo_cfg.get("camera_largura_min_m"),
                                    camera_espera_zoom_in=duelo_cfg.get("camera_espera_zoom_in"))
    res = doc.get("resultado") or {}
    if res.get("vencedor") != luta.get("vencedor") or \
            abs(float(res.get("duracao_jogo") or 0) - float(luta.get("duracao") or 0)) > 0.1:
        raise ErroPalco(f"a luta re-simulada nao bate com o fight.json ({res.get('vencedor')}, "
                        f"{res.get('duracao_jogo')} s x {luta.get('vencedor')}, {luta.get('duracao')} s)")
    remap = {"relogio": "gravacao", "trechos": trechos} if trechos else None
    if remap:
        doc["remapeamento"] = remap
    pasta = Path(pasta) if pasta else config.SAIDAS / f"g16_{duelo_id}"
    pasta.mkdir(parents=True, exist_ok=True)
    from .cli import _salvar_timeline
    arquivo = _salvar_timeline(doc, pasta / "timeline.gcpf")

    # 1. o palco, SEM o HUD dele: o HUD e o da edicao, como no A
    clipe = pasta / f"palco_{perfil}.mp4"
    resumo = render.renderizar(arquivo, clipe, hud=False)
    paradas = plano.paradas_de_hitstop(doc, plano.hitstop_do_estilo(config.projeto(cfg)), remap)
    relogio = Relogio(paradas)
    if sum(paradas.values()) != int((resumo.get("hitstop") or {}).get("quadros") or 0):
        raise ErroPalco("o hitstop das paradas nao bate com o do render")

    # 2. a edicao do A sobre o clipe do palco
    duracao_b = float(resumo["quadros"]) / FPS
    plano_b, fight_b = edicao_sobre_o_palco(edit_plan, fight, clipe=clipe, duracao=duracao_b,
                                            relogio=relogio, perfil=perfil)
    (pasta / "edit_plan.json").write_text(json.dumps(plano_b, ensure_ascii=False, indent=1), encoding="utf-8")
    controller = PipelineController()
    musica = controller._musica(RandomEngine(fight["seed"]))
    espelho = _Espelho(sys.stdout)
    with contextlib.redirect_stdout(espelho):
        final_b = VideoRenderer(controller.render_config, perfil, False).render(plano_b, fight_b, pasta, musica)
    if "composto falhou" in "".join(espelho.texto):
        raise ErroPalco("o gameplay composto (HUD/callouts) falhou no B e caiu no transcode simples")

    # 3. o lado a lado (1a passada com o som do A, 2a com o do B)
    lado = ab.lado_a_lado(final_a, final_b, pasta / f"ab_{perfil}.mp4", rotulos=("A HOJE", "B PALCO"))

    # 4. medidas
    seg_a = pasta_duelo / f"_segments_{perfil}" / "seg_000.mp4"
    seg_b = pasta / f"_segments_{perfil}" / "seg_000.mp4"
    clipe_a = Path(str((luta.get("clipes") or {}).get(perfil, {}).get("path") or ""))
    quadros_clipe_a = int(next((s.get("nb_frames") for s in checagens.sonda(clipe_a).get("streams") or []
                                if s.get("codec_type") == "video"), 0) or 0) if clipe_a.is_file() else None
    medidas = {
        "duelo": duelo_id, "seed": luta["seed"], "p1": luta["p1"], "p2": luta["p2"], "cenario": luta["cenario"],
        "vencedor": luta["vencedor"], "trechos": trechos,
        "musica": (musica or {}).get("path"),
        "a": {"final": medir_video(final_a), "luta": medir_video(seg_a) if seg_a.is_file() else None,
              "quadros_do_clipe": quadros_clipe_a},
        "b": {"final": medir_video(final_b), "luta": medir_video(seg_b),
              "quadros_do_palco": resumo.get("quadros"),
              "hitstop_quadros": sum(paradas.values()), "hitstop_s": round(relogio.extra_s, 3),
              "sons_do_palco": resumo.get("sons"), "tempo_palco": resumo.get("tempo")},
        "eventos": comparar_eventos(fight, doc, remap),
        "sons_no_plano": {"a": len(luta.get("sons") or []), "b": len(fight_b["luta"].get("sons") or [])},
        "lado_a_lado": str(lado),
    }
    # O clipe do pygame pode ter MENOS quadros que a duracao que declara (o
    # renderer repete o ultimo): medido no duelo_00031, 726 para 24,33 s.
    base = (medidas["b"]["quadros_do_palco"] or 0) - medidas["b"]["hitstop_quadros"]
    medidas["quadros_da_luta"] = {"clipe_a": quadros_clipe_a, "palco_sem_hitstop": base,
                                  "pedido_pelo_corte": plano.quadros(int(doc["n"]) / int(doc["hz"]), remap)}
    (pasta / "medidas.json").write_text(json.dumps(medidas, ensure_ascii=False, indent=1, default=str),
                                        encoding="utf-8")
    ab.quadro(lado, pasta / "ab_quadro.png", min(duracao_b * 0.4, duracao_b - 0.5))
    return medidas
