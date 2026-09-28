"""`main.py som-da-luta`: o som REAL do jogo em video ja gravado (Onda 16A).

Tres usos:

    python main.py som-da-luta --listar
        o estoque NAO publicado cuja luta esta muda (a regua da LUTA da guarda
        da publicacao: media do trecho abaixo de -60 dB, ou trecho sem faixa
        de audio — silencio entre golpes nao conta), com o clipe cru de cada
        um e o comando de re-render;

    python main.py som-da-luta duelo_00012 generation_00083 ...
        anota o som da luta sem regravar o video (a luta e deterministica pela
        seed; `tournament/som_real.py` confere que a re-simulacao e a MESMA
        luta do clipe) e re-renderiza NO LUGAR: o mp4 publicavel e trocado;

    python main.py som-da-luta duelo_00012 --destino outputs/_ouvir/x --perfis celular
        o mesmo numa COPIA: o original nao muda (e como os pares de ouvir
        foram feitos, e como se confere um re-render antes de aprovar).

Alvos: `duelo_*`, `fight_*`, `tournament_*` e `generation_*` (ou
`generation_*/estreia`). Numa geracao, a luta da estreia entra em DOIS videos
— a estreia e o fim do video de build — e os dois sao re-renderizados juntos:
o catalogo compara o mp4 da build com o `estreia/fight.json`, e deixar um so
para tras tiraria a build da fila como "mp4 mais velho que os clipes".

O relogio manda: nenhum alvo comeca se nao termina antes de :25 (a janela em
que a grade publica), a mesma regra da geracao noturna. `--agora` ignora.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from ..generation.random_engine import RandomEngine

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# A regua da LUTA da guarda da publicacao (`publicar/audio.py`, dona:
# publicacao, desde 6f09b80): so a media do trecho e a faixa ausente. A
# fracao calada NAO conta no trecho de luta — silencio entre golpes e normal
# (com ela, 00014, 00016 e 00017 sairiam da fila com golpes a -19/-21 dB).
# Usada aqui so para LISTAR o estoque; quem barra e ela. O limiar e importado
# para as duas listas nunca discordarem.
try:
    from ..publicar.audio import LIMIAR_MUDO_DB
except ImportError:  # pragma: no cover - guarda ainda nao instalada
    LIMIAR_MUDO_DB = -60.0

# Minutos por alvo (re-simular a luta sem video + render dos dois perfis),
# medidos na maquina do Adrian em 28/09/2026; a geracao usa 5 por duelo.
MINUTOS = {"duelo": 4, "luta": 6, "build": 12, "torneio": 15}


# ------------------------------------------------------------------ alvos
def resolver(alvo: str, outputs: Path) -> dict:
    """Pasta, tipo e arquivos de um alvo (id em `outputs/`, ou caminho de pasta)."""
    caminho = Path(str(alvo).strip())
    if caminho.is_absolute():
        # Pasta dada por inteiro (outra arvore, uma copia): o tipo sai do nome.
        if caminho.name == "estreia":
            caminho = caminho.parent
        base, pasta = caminho.name, caminho
    else:
        nome = str(alvo).strip().strip("/\\").replace("\\", "/")
        base = nome.split("/")[0]
        pasta = Path(outputs) / base
    if base.startswith("generation_"):
        return {"alvo": base, "tipo": "build", "pasta": pasta,
                "fonte": pasta / "estreia" / "fight.json",
                "planos": [pasta / "estreia" / "edit_plan.json",
                           pasta / "edit_plan.json"]}
    if base.startswith("tournament_"):
        return {"alvo": base, "tipo": "torneio", "pasta": pasta,
                "fonte": pasta / "tournament.json",
                "planos": [pasta / "edit_plan.json"]}
    tipo = "duelo" if base.startswith("duelo_") else "luta"
    return {"alvo": base, "tipo": tipo, "pasta": pasta,
            "fonte": pasta / "fight.json", "planos": [pasta / "edit_plan.json"]}


def _ler(caminho: Path) -> dict:
    with open(caminho, encoding="utf-8-sig") as fh:
        return json.load(fh)


def _gravar(caminho: Path, dados: dict, *, manter_data: bool = False) -> None:
    """Grava o JSON inteiro de uma vez (temporario + replace): nada pela metade."""
    caminho = Path(caminho)
    antes = caminho.stat() if manter_data and caminho.is_file() else None
    temporario = caminho.with_name(caminho.name + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    temporario.replace(caminho)
    if antes is not None:
        # So a lista de sons mudou; o video continua o mesmo ate o render. Sem
        # isto a build ganharia a pendencia "mp4 mais velho que os clipes" e
        # sairia da fila sem nada ter piorado nela.
        os.utime(caminho, ns=(antes.st_atime_ns, antes.st_mtime_ns))


# ------------------------------------------------------------------ relogio
def cabe_agora(minutos: float, agora: datetime | None = None) -> bool:
    """Um trabalho de `minutos` comecando agora termina antes de :25?"""
    from . import noite
    proibida = noite.carregar().get("grade_proibida")
    agora = agora or datetime.now()
    passos = max(1, int(minutos) + 1)
    for i in range(passos + 1):
        instante = agora.timestamp() + 60 * min(float(minutos), i)
        if noite.na_grade(datetime.fromtimestamp(instante).minute, proibida):
            return False
    return True


# ----------------------------------------------------------------- o trabalho
def sonorizar(controller, alvo: str, *, destino: Path | None = None,
              perfis: tuple[str, ...] | None = None, renderizar: bool = True,
              forcar: bool = False, preview: bool = False, log=print) -> dict:
    """Anota o som real de um alvo e (por padrao) re-renderiza. Relatorio."""
    from ..tournament import som_real
    from ..tournament.runner import config_gameplay
    from ..video.som_da_luta import resumo
    from .controller import OUTPUTS

    info = resolver(alvo, OUTPUTS)
    if not info["fonte"].is_file():
        raise FileNotFoundError(f"{info['alvo']}: nao achei {info['fonte']}")
    dados = _ler(info["fonte"])
    origem = "torneio" if info["tipo"] == "torneio" else str(
        dados.get("origem") or ("duelo" if info["tipo"] == "duelo" else "luta"))
    gameplay = config_gameplay(controller.editing_config, origem)

    def _progresso(luta: dict) -> None:
        log(f"[som] {info['alvo']} round {luta.get('match_id', 0)}: "
            f"{len(luta.get('sons') or [])} sons anotados")

    anotados = som_real.anotar_fight(dados, gameplay, origem, forcar=forcar,
                                     progresso=_progresso)
    sons = som_real.sons_por_round(dados)
    cfg_som = controller.editing_config.get("som_da_luta")
    rodadas = [resumo(s) for s in sons.values()]
    relatorio = {"alvo": info["alvo"], "tipo": info["tipo"], "anotados": anotados,
                 "rounds": rodadas, "renderizados": []}

    # Onde escrever: no lugar, ou numa copia (o original fica intocado).
    if destino is not None:
        if info["tipo"] == "build" and renderizar:
            raise ValueError("--destino so renderiza duelo, luta e torneio: o "
                             "video de build depende da voz e das imagens da "
                             "pasta (com --so-anotar vale para todos)")
        destino = Path(destino)
        # Caminho relativo preservado: a build tem DOIS planos (o dela e o da
        # estreia) e um nome so apagaria o outro.
        fonte_escrita = destino / info["fonte"].relative_to(info["pasta"])
        planos = [(p, destino / p.relative_to(info["pasta"]))
                  for p in info["planos"] if p.is_file()]
        for caminho in [fonte_escrita, *(alvo for _p, alvo in planos)]:
            caminho.parent.mkdir(parents=True, exist_ok=True)
    else:
        fonte_escrita = info["fonte"]
        planos = [(p, p) for p in info["planos"] if p.is_file()]
    _gravar(fonte_escrita, dados, manter_data=not renderizar and destino is None)
    planos_escritos = []
    for origem_plano, alvo_plano in planos:
        plano = _ler(origem_plano)
        remendou = som_real.aplicar_no_plano(plano, sons, cfg_som)
        # Na copia o plano vai sempre (o render le de la); no lugar, so se mudou.
        if remendou or destino is not None:
            _gravar(alvo_plano, plano, manter_data=not renderizar and destino is None)
            planos_escritos.append(alvo_plano)
    relatorio["planos"] = [str(p) for p in planos_escritos]
    if not renderizar:
        return relatorio

    perfis = tuple(perfis or controller.perfis)
    if destino is not None:
        relatorio["renderizados"] = _renderizar_copia(
            controller, dados, destino, perfis, preview, log)
        return relatorio
    relatorio["renderizados"] = _renderizar_no_lugar(
        controller, info, dados, preview, log)
    return relatorio


def _renderizar_copia(controller, dados: dict, destino: Path,
                      perfis: tuple[str, ...], preview: bool, log) -> list[str]:
    from ..video.renderer import VideoRenderer
    plano = _ler(destino / "edit_plan.json")
    music = controller._musica(RandomEngine(dados["seed"]))
    feitos = []
    for perfil in perfis:
        renderer = VideoRenderer(controller.render_config, perfil, preview)
        final = renderer.render(plano, dados, destino, music)
        log(f"[render:{perfil}] {final}")
        feitos.append(str(final))
    return feitos


def _renderizar_no_lugar(controller, info: dict, dados: dict, preview: bool,
                         log) -> list[str]:
    pasta = info["pasta"]
    if info["tipo"] == "duelo":
        controller._entregar_duelo(pasta, dados, preview, remontar=False)
        return [str(pasta / f"final_{p}.mp4") for p in controller.perfis]
    if info["tipo"] == "luta":
        controller._entregar_luta(pasta, dados, preview, remontar=False)
        return [str(pasta / f"final_{p}.mp4") for p in controller.perfis]
    if info["tipo"] == "torneio":
        controller.rerender_torneio(info["alvo"], preview=preview)
        return [str(pasta / f"final_{p}.mp4") for p in controller.perfis]
    # build: a estreia (video proprio) e o video de build (a luta no fim)
    feitos = []
    estreia = pasta / "estreia"
    if (estreia / "edit_plan.json").is_file():
        controller._entregar_luta(estreia, dados, preview, remontar=False)
        feitos += [str(estreia / f"final_{p}.mp4") for p in controller.perfis]
    if (pasta / "edit_plan.json").is_file():
        controller.rerender(info["alvo"], preview=preview)
        feitos += [str(pasta / f"final_{p}.mp4") for p in controller.perfis]
    return feitos


def rodar(controller, alvos: list[str], *, destino: Path | None = None,
          perfis: tuple[str, ...] | None = None, renderizar: bool = True,
          forcar: bool = False, preview: bool = False, agora: bool = False,
          log=print) -> int:
    """Os alvos em ordem; para ANTES de um alvo que encostaria em :25."""
    from ..tournament.som_real import LutaDiferente
    falhas = 0
    for alvo in alvos:
        info = resolver(alvo, Path("."))
        minutos = MINUTOS.get(info["tipo"], 6) if renderizar else 2
        if not agora and not cabe_agora(minutos):
            log(f"[som] parei antes de {alvo}: nao termina antes de :25 (a "
                f"grade publica entre :25 e :55). Rode de novo depois de :55; "
                f"quem ja saiu esta pronto.")
            return 4
        alvo_destino = None
        if destino is not None:
            alvo_destino = Path(destino) / info["alvo"] if len(alvos) > 1 else Path(destino)
        try:
            relatorio = sonorizar(controller, alvo, destino=alvo_destino,
                                  perfis=perfis, renderizar=renderizar,
                                  forcar=forcar, preview=preview, log=log)
        except LutaDiferente as erro:
            falhas += 1
            log(f"[som] {alvo}: NAO sonorizado — a luta re-simulada nao e a do "
                f"clipe ({erro}). So regravando a luta inteira.")
            continue
        except Exception as erro:                              # noqa: BLE001
            falhas += 1
            log(f"[som] {alvo}: falhou ({type(erro).__name__}: {erro})")
            continue
        for rodada in relatorio["rounds"]:
            log(f"[som] {relatorio['alvo']}: {rodada['sons']} sons, "
                f"{len(rodada['ids'])} ids, {len(rodada['arquivos'])} arquivos "
                f"distintos ({', '.join(rodada['arquivos'])})")
    return 1 if falhas else 0


# ------------------------------------------------------------------ estoque
def medir_trecho(caminho: Path) -> dict | None:
    """Media (dB) e fracao calada (-50 dB por 0,5 s) de um arquivo; None se nao mediu."""
    caminho = Path(caminho)
    if not caminho.is_file():
        return None
    try:
        saida = subprocess.run(
            ["ffmpeg", "-v", "info", "-i", str(caminho), "-vn", "-af",
             "silencedetect=n=-50dB:d=0.5,volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    texto = saida.stderr or ""
    media = re.search(r"mean_volume: (-?[\d.]+) dB", texto)
    duracao = re.search(r"Duration: (\d+):(\d+):([\d.]+)", texto)
    if media is None:
        # sem faixa de audio o volumedetect nao imprime nada: e mudo
        if "Stream #" in texto and "Audio:" not in texto:
            return {"media_db": -91.0, "calado": 1.0, "sem_faixa": True}
        return None
    total = 0.0
    if duracao:
        h, m, s = duracao.groups()
        total = int(h) * 3600 + int(m) * 60 + float(s)
    calado = sum(float(x) for x in re.findall(r"silence_duration: ([\d.]+)", texto))
    inicios = re.findall(r"silence_start: (-?[\d.]+)", texto)
    if len(inicios) > len(re.findall(r"silence_end:", texto)) and total:
        calado += max(0.0, total - float(inicios[-1]))
    fracao = min(1.0, calado / total) if total else 0.0
    return {"media_db": float(media.group(1)), "calado": round(fracao, 3)}


def _mudo(medida: dict | None) -> bool:
    """A regua da luta: media abaixo do limiar ou faixa ausente (-91 dB)."""
    return bool(medida) and (medida["media_db"] < LIMIAR_MUDO_DB
                             or bool(medida.get("sem_faixa")))


def _alvo_do_video(video) -> str:
    fonte = str(getattr(video, "fonte_id", "") or "")
    return fonte


def _nomes_no_banco() -> set | None:
    """Quem tem ficha no banco vivo (None se nao deu para ler).

    Re-anotar e re-simular: sem os dois lutadores no banco nao ha luta — e o
    caso das builds de agosto, cujo elenco saiu quando o banco foi refeito.
    """
    try:
        from ..nf_bridge import loader as nf
        _, personagens = nf.database.carregar_database()
        return {p["nome"] for p in personagens}
    except Exception:                                          # noqa: BLE001
        return None


def _rerender_sintetizado(video) -> str:
    """O comando que re-renderiza SEM som real (a luta ganha o sintetizado)."""
    fonte = str(getattr(video, "fonte_id", "") or "")
    if getattr(video, "origem", "") == "estreia":
        return f"python main.py fight --rerender {fonte}/estreia"
    if getattr(video, "origem", "") == "duelo":
        return f"python main.py duelo --rerender {fonte}"
    return f"python main.py generate-video --rerender {fonte}"


def estoque(*, medir=medir_trecho, videos=None, publicados=None,
            nomes=...) -> list[dict]:
    """O estoque NAO publicado (perfil celular), com o som da luta de cada um."""
    from ..publicar import catalogo, metricas
    if videos is None:
        videos = catalogo.listar()
    if publicados is None:
        publicados = metricas.publicados()
    if nomes is ...:
        nomes = _nomes_no_banco()
    ja = {linha.get("video_id") for linha in publicados if metricas.publicado(linha)}
    saida = []
    for video in videos:
        if video.id in ja or getattr(video, "perfil", "") != "celular":
            continue
        caminho = Path(video.caminho)
        try:
            eventos = _ler(caminho.parent / "edit_plan.json").get("events") or []
        except (OSError, ValueError):
            continue
        trechos = [(i, e) for i, e in enumerate(eventos)
                   if isinstance(e, dict) and e.get("type") == "gameplay"]
        if not trechos:
            continue
        pasta_seg = caminho.parent / "_segments_celular"
        medidas, clipes, com_sons, fora = [], [], True, set()
        for indice, evento in trechos:
            medidas.append(medir(pasta_seg / f"seg_{indice:03d}.mp4"))
            asset = evento.get("asset") or {}
            for perfil in ("celular", "normal"):
                clipe = asset.get(f"path_{perfil}")
                if clipe:
                    clipes.append({"perfil": perfil, "path": clipe,
                                   "existe": Path(clipe).is_file()})
            luta = evento.get("luta") or {}
            com_sons = com_sons and isinstance(luta.get("sons"), list)
            if nomes is not None:
                fora |= {luta.get(lado) for lado in ("p1", "p2")
                         if luta.get(lado) and luta.get(lado) not in nomes}
        saida.append({
            "video": video.id, "origem": video.origem, "alvo": _alvo_do_video(video),
            "pendencias": list(getattr(video, "pendencias", []) or []),
            "trechos": [{"seg": f"seg_{i:03d}", "medida": m}
                        for (i, _e), m in zip(trechos, medidas)],
            "muda": any(_mudo(m) for m in medidas),
            "nao_medido": any(m is None for m in medidas),
            "som_real": com_sons,
            # Lutador fora do banco: a luta nao re-simula, o som real e
            # impossivel sem regravar tudo; sobra o re-render com o sintetizado.
            "fora_do_banco": sorted(fora),
            "rerender_sintetizado": _rerender_sintetizado(video),
            "clipes": clipes,
        })
    return saida


def comando(alvos: list[str]) -> str:
    unicos = list(dict.fromkeys(a for a in alvos if a))
    return "python main.py som-da-luta " + " ".join(unicos)


def listar(log=print, **kwargs) -> int:
    itens = estoque(**kwargs)
    mudos = [i for i in itens if i["muda"]]
    sinteticos = [i for i in itens if not i["muda"] and not i["som_real"]]
    log(f"estoque nao publicado com luta: {len(itens)} video(s); "
        f"{len(mudos)} com a luta MUDA, {len(sinteticos)} so com o som "
        f"sintetizado, {sum(1 for i in itens if i['som_real'])} com o som real")
    for item in mudos:
        medidas = "; ".join(
            f"{t['seg']} {t['medida']['media_db']:.1f} dB, {t['medida']['calado']:.0%} calado"
            if t["medida"] else f"{t['seg']} nao medido" for t in item["trechos"])
        log(f"  MUDA  {item['video']}  ({medidas})")
        for pendencia in item["pendencias"]:
            log(f"        ! {pendencia}")
        if item["fora_do_banco"]:
            log(f"        som real impossivel: {', '.join(item['fora_do_banco'])} "
                f"fora do banco (a luta nao re-simula). So o sintetizado: "
                f"{item['rerender_sintetizado']}")
        for clipe in item["clipes"]:
            marca = "" if clipe["existe"] else "  (FALTA)"
            log(f"        clipe cru {clipe['perfil']}: {clipe['path']}{marca}")
    possiveis = [i["alvo"] for i in mudos if not i["fora_do_banco"]]
    if possiveis:
        log("re-render com o som real (depois da aprovacao do som, de madrugada):")
        log("  " + comando(possiveis))
    return 0
