# -*- coding: utf-8 -*-
"""A historia inteira mais rapida: voz, plano e legenda no mesmo relogio.

Pedido dele (14/09/2026): "acelere o video em 1.7 na velocidade, isso inclui a
narracao e tudo mais, sinto que ele fala de forma muito lenta".

POR QUE DEPOIS DO PLANO, E NAO NA SINTESE. Pedir 1,7x ao motor de voz (a
`taxa` do edge-tts) derruba a propria voz: o `voz.py` compartilhado com o canal
de builds le mais de 4 palavras por segundo como AUDIO CORTADO e troca pela voz
do Windows, e as pausas redistribuidas pelo `respirar` sao segundos fixos, que
nao encolheriam. Acelerar so o mp4 pronto e o erro do outro lado: o
`edit_plan.json` ficaria no relogio antigo, e quem le dele (as janelas de cena
do parecer, a folha de contato, os cortes de Shorts, a metrica por cena, o
reparo) passaria a apontar a cena errada.

Entao a voz e o plano nascem exatamente como sempre, e so no fim tudo e
dividido pelo mesmo fator. A musica fica de fora de proposito: ela entra
depois, no `_mix_final`, no andamento dela.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import wave
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# OUVIDO, NAO SUPOSTO. A aposta era o `rubberband`, que costuma borrar menos a
# fala. Em 14/09/2026 o Gemini ouviu a mesma narracao acelerada 1,7x por quatro
# metodos e deu 7/10 ao `atempo` contra 3 a 5 a tres ajustes do rubberband
# (metalico, robotico e tremulo, eco constante). O rubberband fica de reserva.
FILTRO_PADRAO = "atempo={fator}"
RESERVA_PADRAO = ("rubberband=tempo={fator}:transients=smooth:detector=soft:"
                  "window=short")
# Quanto o audio esticado pode ficar abaixo do esperado antes de ser recusado.
TOLERANCIA = 0.02
# O que conta como "a fala comecou" ao medir o atraso do filtro.
LIMIAR_DB = -40.0
# Folga no fim da entrada: filtro de esticar segura as ultimas amostras, e
# sem enchimento a ultima palavra sairia cortada.
ENCHIMENTO_S = 0.4


def _ler(caminho: Path):
    """`(amostras int16 [n, canais], taxa)`."""
    import numpy as np

    with wave.open(str(caminho), "rb") as fh:
        canais = fh.getnchannels()
        taxa = fh.getframerate()
        largura = fh.getsampwidth()
        bruto = fh.readframes(fh.getnframes())
    if largura != 2:
        raise ValueError(f"{Path(caminho).name}: so wav de 16 bits "
                         f"(veio {largura * 8})")
    amostras = np.frombuffer(bruto, dtype=np.int16).reshape(-1, canais)
    return amostras, taxa


def _gravar(caminho: Path, amostras, taxa: int) -> None:
    with wave.open(str(caminho), "wb") as fh:
        fh.setnchannels(int(amostras.shape[1]))
        fh.setsampwidth(2)
        fh.setframerate(int(taxa))
        fh.writeframes(amostras.astype("<i2").tobytes())


def inicio_da_fala(amostras, taxa: int, limiar_db: float = LIMIAR_DB,
                   janela_s: float = 0.01) -> float | None:
    """O segundo em que o som passa do limiar pela primeira vez."""
    import numpy as np

    mono = np.abs(amostras.astype(np.float32)).max(axis=1) / 32768.0
    passo = max(1, int(taxa * janela_s))
    limiar = 10 ** (limiar_db / 20.0)
    for inicio in range(0, len(mono), passo):
        janela = mono[inicio:inicio + passo]
        if len(janela) and float(np.sqrt(np.mean(janela ** 2))) > limiar:
            return inicio / float(taxa)
    return None


def _esticar(origem: Path, destino: Path, filtro: str, taxa: int) -> str | None:
    """None se o ffmpeg escreveu; senao o motivo."""
    comando = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(origem),
               "-af", f"apad=pad_dur={ENCHIMENTO_S},{filtro},aresample={taxa}",
               "-ar", str(taxa), "-c:a", "pcm_s16le", str(destino)]
    try:
        r = subprocess.run(comando, capture_output=True, text=True,
                           timeout=600, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as erro:
        return f"{type(erro).__name__}: {erro}"
    if r.returncode != 0 or not destino.is_file():
        return (r.stderr or "")[-300:] or f"codigo {r.returncode}"
    return None


def _uma_tentativa(wav: Path, fator: float, filtro: str) -> str | None:
    """Estica `wav` no lugar. None quando deu certo; senao o motivo."""
    import numpy as np

    entrada, taxa = _ler(wav)
    esperado = int(round(len(entrada) / fator))
    temporario = wav.with_name(wav.stem + ".acelerando.wav")
    try:
        erro = _esticar(wav, temporario, filtro.format(fator=f"{fator:g}"), taxa)
        if erro:
            return erro
        saida, taxa_saida = _ler(temporario)
        if taxa_saida != taxa or saida.shape[1] != entrada.shape[1]:
            saida = saida[:, :entrada.shape[1]]
        # O ATRASO DO FILTRO. O rubberband do ffmpeg roda em modo tempo real
        # e entrega as primeiras amostras atrasadas; sem cortar isso, a voz
        # inteira ficaria deslocada das palavras e a legenda acenderia antes.
        # Medido, e nao suposto: onde a fala comeca antes e depois.
        antes = inicio_da_fala(entrada, taxa)
        depois = inicio_da_fala(saida, taxa)
        atraso = 0
        if antes is not None and depois is not None:
            atraso = max(0, int(round((depois - antes / fator) * taxa)))
        util = saida[atraso:]
        if len(util) < esperado * (1.0 - TOLERANCIA):
            return (f"o filtro entregou {len(util) / taxa:.2f}s de "
                    f"{esperado / taxa:.2f}s esperados")
        if len(util) >= esperado:
            final = util[:esperado]
        else:
            falta = np.zeros((esperado - len(util), util.shape[1]),
                             dtype=util.dtype)
            final = np.concatenate([util, falta])
        _gravar(temporario, final, taxa)
        os.replace(temporario, wav)
        return None
    finally:
        temporario.unlink(missing_ok=True)


def acelerar_voz(wav: Path, fator: float, *, filtro: str = FILTRO_PADRAO,
                 reserva: str = RESERVA_PADRAO, log=print) -> dict | None:
    """Estica `voz.wav` no lugar. `{fator, filtro}` ou None (ficou 1x).

    None nunca derruba o render: a parte sai na velocidade normal, com o
    aviso, e o plano fica coerente com o audio que ficou.
    """
    wav = Path(wav)
    fator = float(fator or 1.0)
    if abs(fator - 1.0) < 1e-6:
        return {"fator": 1.0, "filtro": ""}
    if not wav.is_file():
        log(f"[velocidade] {wav.name} nao existe; nada a acelerar.")
        return None
    motivos = []
    for nome in (filtro, reserva):
        if not nome:
            continue
        try:
            erro = _uma_tentativa(wav, fator, nome)
        except Exception as exc:                               # noqa: BLE001
            erro = f"{type(exc).__name__}: {exc}"
        if erro is None:
            log(f"[velocidade] voz acelerada {fator:g}x "
                f"({nome.split('=')[0]}).")
            return {"fator": fator, "filtro": nome.split("=")[0]}
        motivos.append(f"{nome.split('=')[0]}: {erro[:160]}")
    log("[velocidade] nao consegui acelerar a voz ("
        + "; ".join(motivos) + "); a parte sai na velocidade normal.")
    return None


def escalar_palavras(caminho: Path, fator: float) -> int:
    """Divide `t0/t1` de `voz_palavras.json` pelo fator. Devolve quantas."""
    caminho = Path(caminho)
    fator = float(fator or 1.0)
    if abs(fator - 1.0) < 1e-6 or not caminho.is_file():
        return 0
    with open(caminho, encoding="utf-8") as fh:
        palavras = json.load(fh)
    for palavra in palavras:
        for chave in ("t0", "t1"):
            if chave in palavra:
                palavra[chave] = round(float(palavra[chave]) / fator, 3)
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(palavras, fh, ensure_ascii=False)
    return len(palavras)


def escalar_plano(plano: dict, fator: float,
                  titulo_minimo_s: float = 1.4) -> dict:
    """O plano no relogio do video acelerado. Nao mexe no original.

    O ENCADEAMENTO SOBREVIVE AO ARREDONDAMENTO: cada inicio e cada FIM sao
    divididos a partir dos valores de antes, e a duracao sai da diferenca.
    Dividir inicio e duracao separadamente abriria frestas de milissegundos
    entre as cenas, e o teste da linha do tempo contaria cada uma.
    """
    fator = float(fator or 1.0)
    novo = copy.deepcopy(plano)
    if abs(fator - 1.0) < 1e-6:
        return novo
    for evento in novo.get("events") or []:
        inicio = float(evento.get("start") or 0.0)
        fim = inicio + float(evento.get("duration") or 0.0)
        evento["start"] = round(inicio / fator, 3)
        evento["duration"] = round(round(fim / fator, 3) - evento["start"], 3)
        if evento.get("fala_medida"):
            evento["fala_medida"] = round(float(evento["fala_medida"]) / fator, 3)
        if evento.get("titulo_duracao"):
            # O titulo tambem acelera, mas precisa de tempo de LEITURA: a 1,7x
            # os 2,2 s virariam 1,3 s. E nunca passa do proprio plano.
            titulo = max(float(evento["titulo_duracao"]) / fator,
                         float(titulo_minimo_s))
            evento["titulo_duracao"] = round(min(titulo, evento["duration"]), 3)
    if "total_duration" in novo:
        novo["total_duration"] = round(float(novo["total_duration"]) / fator, 3)
    return novo


__all__ = ["FILTRO_PADRAO", "RESERVA_PADRAO", "acelerar_voz",
           "escalar_palavras", "escalar_plano", "inicio_da_fala"]
