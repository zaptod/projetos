# -*- coding: utf-8 -*-
"""O pacote de evidencia que sobe no chat: um dossie por video.

Nem o ChatGPT nem o Gemini engolem um mp4 de 12 minutos pelo navegador. E o
dossie e melhor que o video cru para esta tarefa, nao um consolo:

  o video   obriga o modelo a estimar no olho ("o corte parece agil")
  o dossie  entrega medido ("4,2 cortes/min, plano medio de 2,4s") e sobra
            atencao dele para o que so ele sabe fazer — ler intencao, tom,
            a quem aquilo esta falando

Sao quatro camadas, nesta ordem: ficha tecnica, numeros medidos, mapa de
cortes e a transcricao com tempos. Mais o mosaico de frames, que vai como
anexo — sem ele, enquadramento e cor viram chute.

Video longo entra com a transcricao RECORTADA (comeco, meio e fim), e o
dossie diz que foi recortada. Um dossie que estoura o limite do chat no meio
de um acervo custa a noite inteira; um que avisa o recorte custa nada.
"""
from __future__ import annotations

from pathlib import Path

from . import canal as _canal
from . import config, medidas, transcrever


def _mmss(segundos: float) -> str:
    segundos = max(0.0, float(segundos or 0))
    return f"{int(segundos // 60):d}:{int(segundos % 60):02d}"


def _numeros(medida: dict) -> list:
    """As linhas de "medido" — so o que tem numero atras."""
    if not medida:
        return ["  (este video ainda nao foi medido: rode `medir`)"]
    audio = medida.get("audio") or {}
    cor = medida.get("cor") or {}
    linhas = [
        f"  duracao ................ {_mmss(medida.get('duracao_s', 0))}",
        f"  formato ................ {medida.get('largura')}x"
        f"{medida.get('altura')} @ {medida.get('fps')}fps"
        f"{' (vertical)' if medida.get('vertical') else ''}",
        f"  cortes ................. {medida.get('cortes', 0)} "
        f"({medida.get('cortes_por_min', 0)} por minuto)",
        f"  plano medio ............ {medida.get('plano_medio_s', 0)}s",
    ]
    if audio.get("lufs") is not None:
        linhas.append(f"  loudness ............... {audio['lufs']} LUFS "
                      f"(faixa {audio.get('faixa_lu')} LU)")
    if medida.get("fala_pct") is not None:
        linhas.append(f"  fala x silencio ........ {medida['fala_pct']}% de "
                      f"fala, {audio.get('pausas', 0)} pausa(s)")
    if cor.get("rgb_medio"):
        clima = "escura" if cor.get("escuro") else "clara"
        quente = "quente" if (cor.get("temperatura") or 0) > 0.02 else (
            "fria" if (cor.get("temperatura") or 0) < -0.02 else "neutra")
        linhas.append(f"  imagem ................. media {clima} e {quente} "
                      f"(brilho {cor.get('brilho')}, "
                      f"saturacao {cor.get('saturacao')})")
    if medida.get("amostra_parcial"):
        linhas.append(f"  ! medido so os primeiros "
                      f"{_mmss(medida.get('analisado_s', 0))}")
    return linhas


def _mapa_de_cortes(medida: dict, quantos: int = 24) -> list:
    instantes = (medida or {}).get("instantes_de_corte") or []
    if not instantes:
        return []
    marcas = " ".join(_mmss(t) for t in instantes[:quantos])
    sobra = f"  (+{len(instantes) - quantos})" if len(instantes) > quantos else ""
    return [f"  troca de plano em: {marcas}{sobra}"]


def _transcricao(falas: list, cfg: dict) -> tuple:
    """Blocos de N segundos com o instante na frente. (linhas, recortada?)."""
    if not falas:
        return ["  (sem transcricao — o video nao tinha legenda)"], False
    bloco_s = float(cfg.get("bloco_de_transcricao_s") or 15)
    blocos, atual, abertura = [], [], falas[0]["inicio"]
    for fala in falas:
        if fala["inicio"] - abertura >= bloco_s and atual:
            blocos.append((abertura, " ".join(atual)))
            atual, abertura = [], fala["inicio"]
        atual.append(fala["texto"])
    if atual:
        blocos.append((abertura, " ".join(atual)))

    teto = int(cfg.get("transcricao_max_palavras") or 1800)
    palavras = sum(len(texto.split()) for _t, texto in blocos)
    recortada = palavras > teto
    if recortada:
        # Comeco, meio e fim: o gancho, o miolo e o desfecho/CTA. Cortar so
        # o fim perderia justamente o que o canal pede ao espectador.
        fatia = max(1, len(blocos) * teto // (palavras * 3))
        meio = len(blocos) // 2
        blocos = (blocos[:fatia]
                  + [(-1.0, "[...]")]
                  + blocos[meio:meio + fatia]
                  + [(-1.0, "[...]")]
                  + blocos[-fatia:])
    linhas = [f"  [{_mmss(t)}] {texto}" if t >= 0 else f"  {texto}"
              for t, texto in blocos]
    return linhas, recortada


def montar(pasta: Path, video: dict, *, cfg: dict | None = None) -> str:
    """O dossie de um video, em texto."""
    cfg = cfg or config.carregar("analise")
    video_id = video["id"]
    medida = medidas.carregar(pasta, video_id)
    falas = transcrever.carregar(pasta, video_id)
    stats = transcrever.stats_de(pasta, video_id)

    linhas = [f"VIDEO {video_id} — {video.get('titulo', '')}", ""]
    linhas.append("FICHA")
    linhas.append(f"  publicado em ........... {video.get('data') or '?'}"
                  f"{' (aproximado)' if video.get('data_aproximada') else ''}")
    linhas.append(f"  visualizacoes .......... {video.get('views', 0):,}"
                  .replace(",", "."))
    linhas.append(f"  aba do canal ........... {video.get('aba', 'videos')}")
    if stats.get("wpm"):
        linhas.append(f"  ritmo de fala .......... {stats['wpm']:.0f} palavras "
                      f"por minuto falado ({stats.get('palavras', 0)} palavras)")
    linhas.append("")

    linhas.append("MEDIDO (ffmpeg — estes numeros nao sao estimativa)")
    linhas += _numeros(medida)
    mapa = _mapa_de_cortes(medida)
    if mapa:
        linhas.append("")
        linhas.append("MAPA DE CORTES")
        linhas += mapa
    linhas.append("")

    corpo, recortada = _transcricao(falas, cfg)
    linhas.append("TRANSCRICAO" + (" (RECORTADA: comeco, meio e fim)"
                                   if recortada else ""))
    linhas += corpo
    return "\n".join(linhas)


def gravar(pasta: Path, video: dict, *, cfg: dict | None = None) -> Path:
    """Grava `dossies/<id>.md` e devolve o caminho."""
    destino = Path(pasta) / "dossies"
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{video['id']}.md"
    caminho.write_text(montar(pasta, video, cfg=cfg), encoding="utf-8")
    return caminho


def contato_de(pasta: Path, video_id: str) -> Path | None:
    """O mosaico de frames daquele video, se foi gerado."""
    caminho = Path(pasta) / "contatos" / f"{video_id}.jpg"
    return caminho if caminho.is_file() else None


def cabecalho_do_canal(pasta: Path) -> str:
    """O contexto do canal, reenviado uma vez por chat.

    Compacto de proposito: e o mesmo texto em todo lote, e o que interessa e
    o modelo saber DE QUE canal se trata e o que ja se sabe dele em numeros —
    nao ler o catalogo inteiro.
    """
    cabecalho = _canal.cabecalho(pasta)
    videos = _canal.videos(pasta)
    todas = medidas.todas(pasta)

    linhas = [f"CANAL: {cabecalho.get('nome') or cabecalho.get('url')}",
              f"  {cabecalho.get('n_videos', len(videos))} videos publicos"]
    if cabecalho.get("inscritos"):
        linhas.append(f"  {cabecalho['inscritos']:,} inscritos"
                      .replace(",", "."))
    datas = sorted(v.get("data") for v in videos if v.get("data"))
    if datas:
        linhas.append(f"  do primeiro catalogado ({datas[0]}) ao mais "
                      f"recente ({datas[-1]})")
    if todas:
        linhas += _distribuicoes(todas)
    if cabecalho.get("descricao"):
        linhas.append(f"  descricao do canal: "
                      f"{cabecalho['descricao'][:300]}")
    return "\n".join(linhas)


def _distribuicoes(todas: list) -> list:
    """As medianas do acervo — o pano de fundo de cada video individual."""
    def mediana(valores):
        limpos = sorted(v for v in valores if v is not None)
        if not limpos:
            return None
        meio = len(limpos) // 2
        if len(limpos) % 2:
            return limpos[meio]
        return (limpos[meio - 1] + limpos[meio]) / 2.0

    duracao = mediana([m.get("duracao_s") for m in todas])
    cortes = mediana([m.get("cortes_por_min") for m in todas])
    lufs = mediana([(m.get("audio") or {}).get("lufs") for m in todas])
    fala = mediana([m.get("fala_pct") for m in todas])
    verticais = sum(1 for m in todas if m.get("vertical"))

    linhas = [f"  MEDIDO no acervo ({len(todas)} videos ja medidos):"]
    if duracao:
        linhas.append(f"    duracao mediana ...... {_mmss(duracao)}")
    if cortes is not None:
        linhas.append(f"    cortes por minuto .... {cortes:.1f} (mediana)")
    if lufs is not None:
        linhas.append(f"    loudness ............. {lufs:.1f} LUFS (mediana)")
    if fala is not None:
        linhas.append(f"    proporcao de fala .... {fala:.0f}% (mediana)")
    linhas.append(f"    formato .............. {verticais} vertical(is), "
                  f"{len(todas) - verticais} horizontal(is)")
    return linhas
