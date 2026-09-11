# -*- coding: utf-8 -*-
"""Roteiro + narracao medida -> plano de edicao.

A regra que manda aqui e a licao mais cara do outro projeto: A CENA ESPERA A
FALA. O `TEMPO` que o roteiro sugere e uma DICA de ritmo; a duracao real da
cena e o maior entre a sugestao e a fala medida mais a margem. Cronometrar a
cena primeiro e espremer a voz depois foi o que cortava a frase no meio.

O plano e uma lista plana de eventos com tempo, no mesmo espirito do outro
projeto: o renderer executa, nunca decide.

    {"type": "cena", "n": 1, "imagem": "...png", "duration": 5.2,
     "narracao": "...", "titulo": "..." (so na primeira), "camera": {...}}
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


class NarracaoNaoCobre(RuntimeError):
    """A voz sintetizada e curta demais para as cenas desta parte."""


def carregar_config(nome: str) -> dict:
    with open(RAIZ / "config" / nome, encoding="utf-8-sig") as fh:
        return json.load(fh)


def cenas_da_parte(roteiro: dict, parte: int = 1) -> list:
    for bloco in roteiro.get("partes") or []:
        if int(bloco["n"]) == int(parte):
            return bloco["cenas"]
    return roteiro.get("cenas") or []


def linhas_de_narracao(roteiro: dict, parte: int = 1) -> list[dict]:
    """Uma linha por cena da PARTE, na ordem. `start`/`duration` sao
    provisorios ate o plano existir: `medir` so olha o texto."""
    linhas = []
    cursor = 0.0
    for cena in cenas_da_parte(roteiro, parte):
        texto = str(cena.get("narracao") or "").strip()
        duracao = float(cena.get("tempo") or 4.0)
        linhas.append({"start": round(cursor, 3), "duration": duracao,
                       "text": texto, "cena": cena["n"]})
        cursor += duracao
    return linhas


def _camera(indice: int, config: dict) -> dict:
    """Push-in e pull-back alternados: dois cortes seguidos com o mesmo
    movimento fazem a sequencia parecer um slideshow."""
    camera = config.get("camera") or {}
    zoom = list(camera.get("zoom") or [1.0, 1.12])
    if camera.get("alternar", True) and indice % 2:
        zoom = [zoom[1], zoom[0]]
    # O centro tambem alterna de lado, de leve: movimento identico em todas as
    # cenas cansa tanto quanto imagem parada.
    lado = 0.46 if indice % 2 else 0.54
    return {"zoom": zoom, "centro": [[0.5, 0.46], [lado, 0.52]]}


def montar(roteiro: dict, medidas: dict | None = None, *, marcos=None,
           duracao_audio: float | None = None,
           config_roteiro: dict | None = None,
           config_render: dict | None = None,
           pasta: Path | None = None, parte: int = 1) -> dict:
    """O plano com as duracoes finais.

    `medidas` e {indice da linha -> segundos de fala}, como `voz.medir`
    devolve. Sem medidas (voz desligada ou sem rede), a cena usa o TEMPO
    sugerido pelo roteiro — o video sai, so sem a garantia de caber.
    """
    config_roteiro = config_roteiro or carregar_config("roteiro.json")
    config_render = config_render or carregar_config("render.json")
    ajustes = config_roteiro.get("narracao") or {}
    margem = float(ajustes.get("margem", 0.35))
    minimo = float(ajustes.get("minimo_cena", 2.5))
    maximo = float(ajustes.get("maximo_cena", 14.0))
    respiro = float(ajustes.get("respiro_final", 0.6))
    medidas = medidas or {}

    cenas = cenas_da_parte(roteiro, parte)
    serie = bool(roteiro.get("serie"))
    estourou: list = []
    # LEITURA CONTINUA: `marcos[i]` diz em que segundo a fala da cena `i`
    # comeca dentro de uma narracao unica. Quando eles chegam, a cena deixa
    # de ser uma PREVISAO da fala e passa a ser o recorte dela — sem folga
    # inventada, sem reinicio de entonacao, sem 0,3 s de vazio entre cenas.
    marcos = list(marcos or [])
    if len(marcos) != len(cenas):
        marcos = []
    eventos = []
    cursor = 0.0
    for indice, cena in enumerate(cenas):
        sugerido = float(cena.get("tempo") or 4.0)
        falado = float(medidas.get(indice, 0.0))
        if marcos:
            # A ultima cena vai ate o fim do audio (mais o respiro, que o
            # bloco abaixo acrescenta).
            fim = (marcos[indice + 1] if indice + 1 < len(marcos)
                   else float(duracao_audio or marcos[-1] + sugerido))
            duracao = max(minimo, fim - marcos[indice])
            falado = duracao
        else:
            duracao = max(sugerido, falado + margem if falado else 0.0)
        # O teto (`maximo_cena`) vale para a cena SEM fala. Com fala medida
        # ele nao pode cortar a voz: `voz.py` trunca o audio no espaco que a
        # cena der, e uma frase cortada no meio da palavra e pior do que uma
        # cena longa. Medido em 31/08/2026: 9 das 14 falas de uma parte
        # saiam cortadas porque o teto era 14 s e a narracao pedia ate 16,4 s.
        if marcos:
            teto = duracao          # o audio manda: nada a limitar
        else:
            teto = max(maximo, falado + margem) if falado else maximo
        duracao = max(minimo, min(teto, duracao))
        if falado and duracao > maximo + 0.01:
            estourou.append((cena.get("n"), round(duracao, 1)))
        if indice == len(cenas) - 1:
            # A ultima cena segura o CTA: cortar em cima da ultima palavra
            # tira o tempo de ler a pergunta e de tocar em "seguir".
            duracao += respiro
        evento = {
            "type": "cena",
            "n": cena["n"],
            "start": round(cursor, 3),
            "duration": round(duracao, 3),
            "narracao": str(cena.get("narracao") or ""),
            "imagem": str(cena.get("imagem") or ""),
            "camera": _camera(indice, config_render),
            "fala_medida": round(falado, 3) if falado else None,
        }
        evento["parte"] = parte
        if pasta is not None:
            from ..imagens import fila
            arquivo = fila.caminho_da_cena(Path(pasta).name, cena["n"],
                                           parte if serie else None)
            if fila.utilizavel(arquivo):
                evento["arquivo"] = str(arquivo)
        if indice == 0 and roteiro.get("titulo"):
            # O titulo entra SOBRE a primeira imagem, nunca num cartao antes
            # dela: cartao de texto no segundo zero e o que faz rolar o feed.
            from ..roteiro.roteiro import titulo_da_parte
            evento["titulo"] = titulo_da_parte(roteiro, parte)
            evento["titulo_duracao"] = float(
                (config_render.get("titulo") or {}).get("duracao", 2.2))
        eventos.append(evento)
        cursor += duracao

    from ..roteiro.roteiro import titulo_da_parte
    # A NARRACAO TEM QUE COBRIR AS CENAS. Com `marcos`, cada cena e um recorte
    # do audio — entao a soma delas so pode passar muito do audio se o piso
    # `minimo_cena` estiver segurando cena que nao tem fala nenhuma, ou seja,
    # se a voz acabou antes do roteiro. Foi o que aconteceu na parte 1 da
    # historia 8: 21,8 s de audio para 14 cenas, todas no piso, 35,6 s de plano
    # e 14 s de imagem muda no fim. Renderizar isso e pior do que nao renderizar.
    if marcos and duracao_audio and cursor > float(duracao_audio) * 1.3:
        raise NarracaoNaoCobre(
            f"parte {parte}: a narracao tem {float(duracao_audio):.1f}s mas as "
            f"{len(cenas)} cenas pedem {cursor:.1f}s. O audio veio incompleto — "
            "o video sairia com a voz parando no meio. Rode "
            "`python main.py conferir --consertar` e renderize de novo.")
    eventos = dividir_planos(eventos, config_render)
    if estourou:
        print(f"[timeline] {len(estourou)} cena(s) passaram de {maximo:.0f}s "
              f"para a fala caber: "
              + ", ".join(f"cena {n} -> {d}s" for n, d in estourou[:6])
              + ". Narracao mais curta no roteiro deixa o video mais rapido.",
              flush=True)
    return {
        "historia_id": roteiro.get("historia_id", ""),
        "parte": parte,
        "partes": len(roteiro.get("partes") or [1]),
        "titulo": titulo_da_parte(roteiro, parte),
        "total_duration": round(cursor, 3),
        "events": eventos,
    }


def linhas_do_plano(plano: dict) -> list[dict]:
    """As falas ja no relogio do plano — e isto que a voz monta."""
    return [{"start": e["start"], "duration": e["duration"],
             "text": e["narracao"], "cena": e["n"]}
            for e in plano["events"]
            if e.get("narracao") and not e.get("continuacao")]


def dividir_planos(eventos: list, config_render: dict | None = None) -> list:
    """Cena comprida vira DOIS planos da mesma imagem: aberto e fechado.

    O motivo e medido (01/09/2026): a historia trocava de imagem a cada
    14,7 s, enquanto o video de build corta a cada 2,5 s. Uma foto parada
    com zoom lento por quinze segundos e um slideshow — o texto pode ser
    otimo, mas nao ha o que olhar, e a pessoa rola o feed.

    Nada de imagem nova (que custaria geracao): o segundo plano e a MESMA
    imagem num enquadramento diferente — o olho reengata na troca, como num
    corte de wide para close. A fala nao e tocada; ela ja e continua.
    """
    camera = (config_render or {}).get("camera") or {}
    limite = float(camera.get("corte_visual_s", 8.0))
    if limite <= 0:
        return eventos
    minimo = float(camera.get("plano_minimo_s", 3.0))

    saida = []
    for evento in eventos:
        duracao = float(evento.get("duration") or 0.0)
        # So vale para cena com imagem: um cartao de texto partido ao meio
        # nao ganha nada.
        if duracao < limite * 1.5 or not evento.get("arquivo"):
            saida.append(evento)
            continue
        quantos = min(3, max(2, int(duracao // limite)))
        while quantos > 1 and duracao / quantos < minimo:
            quantos -= 1
        if quantos < 2:
            saida.append(evento)
            continue

        fatia = duracao / quantos
        for i in range(quantos):
            plano = dict(evento)
            plano["start"] = round(float(evento["start"]) + fatia * i, 3)
            plano["duration"] = round(fatia, 3)
            plano["camera"] = _enquadramento(i, quantos, camera)
            if i:
                # O texto (titulo, narracao, legenda) pertence ao PRIMEIRO
                # plano da cena; os outros sao continuacao visual dela.
                plano["continuacao"] = True
                plano.pop("titulo", None)
                plano.pop("titulo_duracao", None)
            saida.append(plano)
    return saida


def _enquadramento(i: int, total: int, camera: dict) -> dict:
    """Um plano da mesma imagem: o zoom CONTINUA, o enquadramento muda.

    Medido em 01/09/2026, a primeira versao disto tinha um defeito visivel:
    o plano terminava em zoom 1.12 e o seguinte COMECAVA em 1.37, na mesma
    imagem e quase no mesmo centro. Isso nao le como corte — le como falha
    de reproducao, e acontecia 21 vezes por parte (o detector de corte
    acusou 34 mudancas contra 13 do video antigo).

    O conserto tem duas metades, e as duas importam:

      ZOOM ENCADEADO. O plano seguinte comeca exatamente onde o anterior
      parou. Nao ha salto de escala em lugar nenhum.

      CENTRO BEM DIFERENTE. Se a escala e continua, o que faz o corte ser
      lido como corte e olhar outra PARTE da imagem — 0,06 de deslocamento
      passava por defeito; 0,20 le como reenquadramento.
    """
    zoom = list(camera.get("zoom") or [1.0, 1.12])
    largo, fechado = float(zoom[0]), float(zoom[1])
    total = max(1, int(total))
    # O empurrao total da cena e repartido entre os planos: cada um continua
    # o anterior, e o ultimo termina no zoom maximo previsto.
    passo = (fechado - largo) / total
    inicio = largo + passo * i
    # Regioes distintas da imagem. O rosto costuma ficar no terco superior,
    # entao o primeiro plano olha para cima e os outros vao para os lados.
    regioes = [
        [[0.50, 0.42], [0.50, 0.48]],
        [[0.36, 0.52], [0.44, 0.46]],
        [[0.64, 0.46], [0.56, 0.52]],
    ]
    return {"zoom": [round(inicio, 4), round(inicio + passo, 4)],
            "centro": regioes[i % len(regioes)]}


def legenda_srt(plano: dict) -> str:
    """Legenda por CENA (a karaoke e desenhada no quadro; isto e o arquivo
    para quem quiser subir legenda separada na plataforma)."""
    def tempo(segundos: float) -> str:
        total = max(0.0, float(segundos))
        h, resto = divmod(total, 3600)
        m, s = divmod(resto, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"

    partes = []
    principais = [e for e in plano["events"] if not e.get("continuacao")]
    total = float(plano.get("total_duration") or 0.0)
    for i, evento in enumerate(principais, 1):
        if not evento.get("narracao"):
            continue
        # A CENA PODE TER VIRADO VARIOS PLANOS. `dividir_planos` corta cena
        # longa em 2-3 enquadramentos da mesma imagem, e so o PRIMEIRO fica
        # sem `continuacao` — entao `evento["duration"]` e a duracao do
        # primeiro plano, nao a da cena. Usar ela encurtava a legenda:
        # medido em 08/09/2026 na historia 9, a fala final durava 15,1 s e a
        # legenda sumia aos 5,2 s, deixando o CTA sem texto na tela.
        #
        # As cenas ladrilham a linha do tempo, entao o fim de uma e o comeco
        # da seguinte — e a ultima vai ate o fim do video.
        proximo = principais[i] if i < len(principais) else None
        fim = (float(proximo["start"]) if proximo is not None
               else (total or evento["start"] + evento["duration"]))
        partes.append(f"{i}\n{tempo(evento['start'])} --> {tempo(fim)}\n"
                      f"{evento['narracao']}\n")
    return "\n".join(partes)
