# -*- coding: utf-8 -*-
"""O que impede uma parte de ir ao ar — conferido no ARQUIVO, nao no plano.

"Publicar com um clique" so e seguro se algo olhar o mp4 antes. Um roteiro
perfeito nao garante video bom: a imagem pode ter faltado, a voz pode nao ter
sido sintetizada (sem rede), o render pode ter saido mudo, e nada disso
levanta excecao — o arquivo existe do mesmo jeito.

Entao cada parte passa por uma vistoria antes do upload:

    ERRO    nao publica. Video sem audio, sem imagem nenhuma, curto demais.
    AVISO   publica, mas voce fica sabendo. Cena sem imagem, audio baixo.

Tudo medido com ffprobe/ffmpeg, que ja sao dependencia do render.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Faixas de um vertical publicavel. Fora disto nao e "estilo": e defeito.
DURACAO_MINIMA = 8.0
DURACAO_MAXIMA = 180.0
# As plataformas normalizam para perto de -14 LUFS; abaixo de -30 dB de media
# o video esta praticamente mudo no celular (foi o diagnostico do outro canal).
MEDIA_MINIMA_DB = -30.0
BYTES_MINIMOS = 100_000
# Fala humana em pt-BR fica entre ~1,5 e ~4,0 palavras/s (medido nas partes boas:
# 1,99 a 2,87). Contar as palavras do ROTEIRO contra a duracao do VIDEO responde
# a pergunta que nenhuma medida do arquivo sozinha responde: a narracao chegou
# inteira? A parte 1 da historia 8 dava 19,1 palavras/s e passava em tudo mais.
PALAVRAS_POR_S_MIN = 1.5
PALAVRAS_POR_S_MAX = 4.0
# Silencio no fim = a voz acabou antes das imagens. Um respiro de ~0,6 s e de
# proposito (o CTA precisa de tempo de leitura); tres segundos ja e defeito.
SILENCIO_FINAL_MAXIMO = 3.0
# Parte que destoa das irmas: a p01 tinha 35,7 s contra ~145 s das outras cinco.
FRACAO_MINIMA_DA_MEDIANA = 0.5


def _ffprobe(caminho: Path) -> dict:
    try:
        saida = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration,size:stream=codec_type,codec_name",
             "-of", "json", str(caminho)],
            capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)
        return json.loads(saida.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}


def _audio(caminho: Path, duracao: float) -> tuple:
    """(media em dB, segundos calados no fim) numa DECODIFICACAO SO.

    Os dois filtros vao no mesmo `-af`: decodificar um video de 150 s duas
    vezes custava o dobro para responder duas perguntas sobre as mesmas
    amostras, e a vistoria de uma serie de 6 partes fazia isso 12 vezes.
    """
    try:
        saida = subprocess.run(
            ["ffmpeg", "-v", "info", "-i", str(caminho), "-af",
             "volumedetect,silencedetect=n=-40dB:d=1.0", "-f", "null", "-"],
            capture_output=True, text=True, timeout=300, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None, 0.0
    media, inicios, fins = None, [], []
    for linha in (saida.stderr or "").splitlines():
        try:
            if "mean_volume:" in linha:
                media = float(linha.split("mean_volume:")[1].split("dB")[0].strip())
            elif "silence_start:" in linha:
                inicios.append(float(linha.split("silence_start:")[1].split()[0]))
            elif "silence_end:" in linha:
                fins.append(float(linha.split("silence_end:")[1].split()[0]))
        except (ValueError, IndexError):
            continue
    if not inicios or duracao <= 0:
        return media, 0.0
    comeco = inicios[-1]
    # O ffmpeg fecha o ultimo bloco no fim do arquivo, entao "tem silence_end"
    # NAO quer dizer "o silencio acabou antes do video": e preciso olhar ONDE
    # ele fecha. So conta o que vai ate o fim — pausa longa no meio e respiro.
    fim = fins[-1] if fins and fins[-1] > comeco else duracao
    if fim < duracao - 0.3:
        return media, 0.0
    return media, max(0.0, duracao - comeco)


def vistoriar_arquivo(caminho: Path) -> dict:
    """O que o mp4 tem de fato: duracao, faixas e nivel de audio."""
    caminho = Path(caminho)
    if not caminho.is_file():
        return {"existe": False, "erros": [f"{caminho.name} nao existe"],
                "avisos": []}
    dados = _ffprobe(caminho)
    fluxos = dados.get("streams") or []
    duracao = float((dados.get("format") or {}).get("duration") or 0.0)
    tem_video = any(f.get("codec_type") == "video" for f in fluxos)
    tem_audio = any(f.get("codec_type") == "audio" for f in fluxos)
    tamanho = caminho.stat().st_size

    erros, avisos = [], []
    if tamanho < BYTES_MINIMOS:
        erros.append(f"arquivo de {tamanho / 1000:.0f} KB: render interrompido")
    if not tem_video:
        erros.append("sem faixa de video")
    if not tem_audio:
        erros.append("sem faixa de audio: o video vai ao ar mudo")
    if duracao < DURACAO_MINIMA:
        erros.append(f"{duracao:.1f}s e curto demais para uma historia")
    elif duracao > DURACAO_MAXIMA:
        avisos.append(f"{duracao:.0f}s: longo para um Short/Reel")

    media, calado = _audio(caminho, duracao) if tem_audio else (None, 0.0)
    if media is not None and media < MEDIA_MINIMA_DB:
        erros.append(f"audio a {media:.1f} dB de media: praticamente mudo")

    if calado > SILENCIO_FINAL_MAXIMO:
        erros.append(f"os ultimos {calado:.1f}s sao mudos: a narracao acabou "
                     "antes das imagens")

    return {"existe": True, "duracao": round(duracao, 2), "bytes": tamanho,
            "audio": tem_audio, "video": tem_video, "media_db": media,
            "silencio_final": round(calado, 2),
            "erros": erros, "avisos": avisos}


def vistoriar_parte(historia_id: str, parte: int, caminho: Path,
                    roteiro: dict | None = None) -> dict:
    """A vistoria do arquivo MAIS o que so o roteiro sabe dizer."""
    from ..imagens import fila
    from ..roteiro import roteiro as R
    from ..video.timeline import cenas_da_parte

    roteiro = roteiro or R.carregar(historia_id)
    laudo = vistoriar_arquivo(caminho)

    # A NARRACAO CHEGOU INTEIRA? Nenhuma medida do arquivo sozinha responde
    # isso: um video com 85% da fala faltando tem audio, tem imagem, tem
    # duracao e passa em tudo. O roteiro sabe quantas palavras deviam ser
    # ditas; o arquivo sabe em quantos segundos. O resto e divisao.
    palavras = sum(len(str(c.get("narracao") or "").split())
                   for c in cenas_da_parte(roteiro, parte))
    laudo["palavras"] = palavras
    laudo["palavras_por_s"] = None
    if palavras and laudo.get("duracao"):
        taxa = palavras / float(laudo["duracao"])
        laudo["palavras_por_s"] = round(taxa, 2)
        if taxa > PALAVRAS_POR_S_MAX:
            laudo["erros"].append(
                f"{palavras} palavras em {laudo['duracao']:.0f}s "
                f"({taxa:.1f} palavras/s): a narracao nao cabe no video — "
                "o audio veio incompleto")
        elif taxa < PALAVRAS_POR_S_MIN:
            laudo["avisos"].append(
                f"{taxa:.1f} palavras/s: o video esta arrastado para o texto")

    imagens = fila.resumo(historia_id, roteiro, parte)
    if imagens["total"] and imagens["prontas"] == 0:
        laudo["erros"].append(
            "nenhuma cena tem imagem: o video inteiro e cartao de texto")
    elif imagens["faltam"]:
        laudo["avisos"].append(
            f"{imagens['faltam']} de {imagens['total']} cena(s) sem imagem")

    # O mp4 mais velho que a ultima imagem = a imagem nova nao entrou nele.
    novas = [l["arquivo"] for l in fila.estado(historia_id, roteiro, parte)
             if l["pronta"]]
    if novas and laudo.get("existe"):
        mais_nova = max(a.stat().st_mtime for a in novas)
        if Path(caminho).stat().st_mtime + 5 < mais_nova:
            laudo["erros"].append(
                "imagem mais nova que o video: re-renderize antes de publicar")

    laudo.update({"parte": parte, "imagens": imagens,
                  "titulo": R.titulo_da_parte(roteiro, parte),
                  "ok": not laudo["erros"]})
    return laudo


def vistoriar_serie(historia_id: str, videos: list) -> dict:
    """Vistoria de todas as partes prontas. `videos` sao os do catalogo."""
    from ..roteiro import roteiro as R
    roteiro = R.carregar(historia_id)
    partes = [vistoriar_parte(historia_id, v.parte, v.caminho, roteiro)
              for v in videos]
    # UMA PARTE FORA DA CURVA. As partes de uma serie sao escritas com o mesmo
    # numero de cenas, entao duram quase o mesmo; a que destoa nao e estilo, e
    # defeito. A p01 da historia 8 tinha 35,7 s contra ~145 s das cinco irmas —
    # visivel de longe para quem olha a tabela, invisivel para quem olha um mp4.
    duracoes = sorted(float(p.get("duracao") or 0.0) for p in partes
                      if p.get("existe"))
    if len(duracoes) >= 3:
        mediana = duracoes[len(duracoes) // 2]
        for laudo in partes:
            atual = float(laudo.get("duracao") or 0.0)
            if laudo.get("existe") and atual < mediana * FRACAO_MINIMA_DA_MEDIANA:
                laudo["avisos"].append(
                    f"{atual:.0f}s contra {mediana:.0f}s das outras partes: "
                    "esta parte esta pela metade")
    if str(roteiro.get("provedor") or "").lower() == "fake":
        for laudo in partes:
            laudo["erros"].append(
                "historia de TESTE (provedor 'fake'): as imagens sao cartoes "
                "de placeholder, isto nao vai ao ar")
    for laudo in partes:
        laudo["ok"] = not laudo["erros"]
    esperadas = len(roteiro["partes"])
    faltando = sorted({p["n"] for p in roteiro["partes"]}
                      - {v.parte for v in videos})
    resumo = {
        "historia_id": historia_id, "titulo": roteiro.get("titulo", ""),
        "partes": partes, "esperadas": esperadas,
        "prontas": len(videos), "faltando": faltando,
        "erros": [f"parte {p['parte']}: {e}" for p in partes for e in p["erros"]],
        "avisos": [f"parte {p['parte']}: {a}" for p in partes for a in p["avisos"]],
    }
    if faltando:
        resumo["erros"].insert(
            0, f"faltam os videos da(s) parte(s) {', '.join(map(str, faltando))}")
    resumo["ok"] = not resumo["erros"]
    return resumo
