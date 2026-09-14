# -*- coding: utf-8 -*-
"""Uma pergunta so: tem alguma coisa errada com o que ja esta no disco?

Existe porque o defeito da historia 8 foi encontrado por acaso. A parte 1
tinha 21,8 s de narracao onde deviam existir 150, o video saiu com 14 s de
imagem muda, e o painel dizia "pronta: 6 video(s) para publicar" — nada
mentia, e ninguem tinha como perguntar.

Sao tres varreduras, todas baratas:

    CACHE DE VOZ   mp3 sem os limites de palavra ao lado (sintese que nao
                   terminou) e mp3 cujas marcas passam do fim do audio
                   (audio cortado). `--consertar` apaga; a proxima
                   renderizacao re-sintetiza sozinha.
    VIDEOS         palavras do roteiro contra a duracao do mp4, parte por
                   parte. Fala humana fica em ~2,0-2,9 palavras/s; 19 e
                   audio faltando.
    NUMEROS        o que a narracao cita e a ficha de FATOS nao fixou.

Nao renderiza, nao apaga video, nao publica nada.
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"
CACHE_VOZ = OUTPUTS / "_voz_cache"

# O edge-tts entrega mp3 CBR de 48 kbps: 6000 bytes por segundo, aferido no
# arquivo do defeito (131.040 bytes = 21,84 s exatos). Serve para varrer
# centenas de arquivos sem pagar um ffprobe por arquivo.
BYTES_POR_SEGUNDO = 6000.0


def cache_de_voz(cache: Path | None = None) -> list[dict]:
    """As entradas do cache que nao servem, com o motivo."""
    cache = Path(cache or CACHE_VOZ)
    if not cache.is_dir():
        return []
    ruins = []
    for mp3 in sorted(cache.glob("*.mp3")):
        duracao = mp3.stat().st_size / BYTES_POR_SEGUNDO
        sidecar = mp3.with_suffix(".words.json")
        if not sidecar.is_file():
            ruins.append({"arquivo": mp3, "duracao": duracao,
                          "motivo": "sem os limites de palavra: a sintese "
                                    "nao chegou ao fim"})
            continue
        try:
            with open(sidecar, encoding="utf-8") as fh:
                palavras = json.load(fh)
        except (OSError, ValueError):
            ruins.append({"arquivo": mp3, "duracao": duracao,
                          "motivo": "limites de palavra ilegiveis"})
            continue
        if not palavras:
            ruins.append({"arquivo": mp3, "duracao": duracao,
                          "motivo": "limites de palavra vazios"})
            continue
        fim = float(palavras[-1].get("t1") or 0.0)
        if fim > duracao + 1.0:
            ruins.append({"arquivo": mp3, "duracao": duracao,
                          "motivo": f"as marcas vao ate {fim:.1f}s mas o audio "
                                    f"tem {duracao:.1f}s: veio cortado"})
    return ruins


def limpar_cache(ruins: list[dict]) -> int:
    """Apaga as entradas ruins. A proxima renderizacao re-sintetiza."""
    apagados = 0
    for item in ruins:
        mp3 = Path(item["arquivo"])
        mp3.with_suffix(".words.json").unlink(missing_ok=True)
        if mp3.exists():
            mp3.unlink()
            apagados += 1
    return apagados


def partes_da_historia(historia_id: str) -> list[dict]:
    """Uma linha por parte: palavras, duracao, palavras/s e o que esta errado.

    De proposito SO com ffprobe (le o cabecalho, nao decodifica). A vistoria
    de publicar mede nivel e silencio, o que exige decodificar o video
    inteiro: 12 passagens numa serie de 6 partes, minutos de espera. Aqui a
    pergunta e outra — "tem alguma coisa obviamente errada?" — e a divisao
    palavras/segundo responde de graca. O que ela nao pega, `main.py publicar
    <id> --vistoriar` pega antes do upload.
    """
    from ..publicar import qualidade
    from ..roteiro import roteiro as R
    from ..video.timeline import cenas_da_parte

    roteiro = R.carregar(historia_id)
    pasta = OUTPUTS / historia_id
    serie = bool(roteiro.get("serie")) and len(roteiro.get("partes") or []) > 1
    linhas = []
    for parte in roteiro.get("partes") or []:
        n = int(parte["n"])
        nome = f"final_celular_p{n:02d}.mp4" if serie else "final_celular.mp4"
        video = pasta / nome
        palavras = sum(len(str(c.get("narracao") or "").split())
                       for c in cenas_da_parte(roteiro, n))
        linha = {"parte": n, "palavras": palavras, "video": video,
                 "duracao": 0.0, "palavras_por_s": None, "erros": [],
                 "avisos": []}
        if not video.is_file():
            linha["avisos"].append("ainda sem video")
            linhas.append(linha)
            continue
        dados = qualidade._ffprobe(video)
        duracao = float((dados.get("format") or {}).get("duration") or 0.0)
        linha["duracao"] = round(duracao, 2)
        # A MESMA regra da vistoria de publicar, e nao uma copia dela: desde
        # 14/09/2026 o video pode estar acelerado, e duas contas diferentes
        # dariam duas respostas para a mesma parte.
        feito = qualidade.formato_de(dados, historia_id, n)
        ritmo = qualidade.avaliar_ritmo(palavras, duracao, feito["velocidade"])
        linha["palavras_por_s"] = ritmo["palavras_por_s"]
        linha["palavras_por_s_natural"] = ritmo["palavras_por_s_natural"]
        linha["formato"] = feito
        linha["erros"].extend(ritmo["erros"])
        linha["avisos"].extend(ritmo["avisos"])
        linhas.append(linha)

    # A parte que destoa das irmas. Precisa das outras para existir, entao so
    # da para perguntar aqui, depois de medir todas.
    medidas = sorted(l["duracao"] for l in linhas if l["duracao"])
    if len(medidas) >= 3:
        mediana = medidas[len(medidas) // 2]
        for linha in linhas:
            if 0 < linha["duracao"] < mediana * qualidade.FRACAO_MINIMA_DA_MEDIANA:
                linha["avisos"].append(
                    f"{linha['duracao']:.0f}s contra {mediana:.0f}s das outras "
                    "partes: esta parte esta pela metade")
    return linhas


def conferir_historia(historia_id: str) -> dict:
    from ..roteiro import coerencia
    from ..roteiro import roteiro as R

    roteiro = R.carregar(historia_id)
    return {"historia_id": historia_id,
            "titulo": roteiro.get("titulo") or "",
            "teste": str(roteiro.get("provedor") or "").lower() == "fake",
            "partes": partes_da_historia(historia_id),
            "numeros": coerencia.conferir(roteiro)}
