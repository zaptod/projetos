# -*- coding: utf-8 -*-
"""Cura do ledger de publicacoes — passo 2 do contrato do campo `url`.

    python ferramentas/curar_ledger.py                 # A SECO: so relata
    python ferramentas/curar_ledger.py --gravar        # aplica (com copia)

Por que existe (16/09/2026): o `url` do ledger guardava tres coisas — o
link, a frase de estado e, no TikTok, sempre a frase —, e a frase contava
como "saiu". Com isso, 40 linhas do Neural Fights diziam "publicado" para
videos privados (20 deles nunca foram ao ar, e a fila os pula para sempre),
12 linhas de YouTube tinham frase no lugar do link, e cinco ids apareciam em
mais de uma linha. O passo 1 (`metricas.publicado`) fez os leitores
perguntarem a mesma coisa; este passo corrige as RESPOSTAS gravadas.

A SECO E O PADRAO, e nao por timidez: as curas mudam o que a fila considera
publicado — video volta a ser elegivel, video some da conta. Isso e decisao
do Adrian. Sem `--gravar` nada no ledger muda; o relatorio diz, linha por
linha, o que MUDARIA (antes -> depois), com o grau de certeza.

Com `--gravar`: copia o ledger ao lado (`.antes-cura-<carimbo>`) e so entao
reescreve. Cura "a conferir" NUNCA e aplicada; ela so aparece no relatorio.

O nucleo (`calcular_curas`) e puro: recebe as linhas e a lista do canal e
devolve as curas. So `buscar_canal` toca a rede.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "outputs" / "_cura"

from builds.publicar import metricas, titulos                  # noqa: E402

ALTA, MEDIA, A_CONFERIR = "alta", "media", "a_conferir"
FOLGA_ALTA = timedelta(minutes=2)
PEDACO = re.compile(r"\s*\((\d+) de (\d+)\)\s*$")
PRIVADO = ("private", "privado")


def _linha(texto: str = "") -> None:
    sys.stdout.buffer.write((texto + "\n").encode("utf-8", "replace"))


# --------------------------------------------------------------- nucleo puro
def _link(youtube_id: str) -> str:
    return f"https://youtu.be/{youtube_id}"


def _e_link(url) -> bool:
    return str(url or "").startswith("http")


def _referencia(linha: dict):
    return (metricas._instante(linha.get("agendado_para"))
            or metricas._instante(linha.get("quando")))


def _distancia(linha: dict, video: dict):
    ref, no_ar = _referencia(linha), metricas._instante(video.get("publicado_em"))
    if ref is None or no_ar is None:
        return None
    return abs(no_ar - ref)


def _cura(indice, linha, tipo, certeza, depois, motivo) -> dict:
    campos = sorted(set(depois))
    return {"linha": indice, "tipo": tipo, "certeza": certeza,
            "video_id": linha.get("video_id"), "quando": linha.get("quando"),
            "plataforma": linha.get("plataforma") or "youtube",
            "antes": {c: linha.get(c) for c in campos},
            "depois": depois, "motivo": motivo}


def calcular_curas(linhas: list, videos: list, canal: str = "builds") -> list:
    """As curas de UM canal. Uma linha recebe no maximo uma cura de conteudo.

    Ordem das regras, e ela importa:
      1. ID REPETIDO: dono e a linha mais proxima da hora do video; as outras
         perdem o id (o caso A/B de generation_00081).
      2. VIDEO PRIVADO: com gemeo publico de mesmo titulo, a linha passa a
         apontar para ele; sem gemeo, a linha deixa de contar como publicada.
      3. FRASE NO URL: um video (titulo e hora) ou dois pedacos
         "(1 de 2)"/"(2 de 2)" viram link.
      4. FORMATO: toda linha que sobrar ganha `publicado` explicito, e a
         frase sai do `url` para `estado_texto` (inclui o TikTok, que nunca
         teve link).
    """
    # UM video por id. A lista de uploads do canal traz o mesmo video mais de
    # uma vez (medido em 16/09/2026: `U7n1dgQCidA` duas vezes), e sem isto um
    # gemeo unico virava "dois gemeos" e a cura caia em "a conferir".
    unicos: dict = {}
    for v in videos or ():
        if isinstance(v, dict) and v.get("youtube_id"):
            unicos.setdefault(v["youtube_id"], v)
    videos = list(unicos.values())
    por_id = unicos
    curas: list = []
    tocadas: set = set()
    donos = {str(L.get("youtube_id")) for L in linhas
             if isinstance(L, dict) and L.get("youtube_id")}

    def youtube(L):
        return isinstance(L, dict) and (L.get("plataforma") or "youtube") == "youtube"

    # 1. id repetido
    grupos: dict = {}
    for i, L in enumerate(linhas):
        if youtube(L) and L.get("youtube_id"):
            grupos.setdefault(L["youtube_id"], []).append(i)
    for vid, indices in grupos.items():
        if len(indices) < 2:
            continue
        video = por_id.get(vid)
        def chave_de_dono(i, video=video):
            d = _distancia(linhas[i], video) if video else None
            return d if d is not None else timedelta.max
        dono = min(indices, key=chave_de_dono)
        for i in indices:
            if i == dono:
                continue
            curas.append(_cura(
                i, linhas[i], "id_repetido", MEDIA,
                {"youtube_id": None, "url": "", "publicado_em": None,
                 "publicado": False, "estado": "nao_confirmado"},
                f"o id {vid} pertence a linha {dono} (mais proxima da hora "
                "do video); esta linha nao tem video proprio no canal"))
            tocadas.add(i)

    # 2. video privado
    publicos = [v for v in videos
                if str(v.get("privacidade") or "").lower() == "public"]
    for i, L in enumerate(linhas):
        if i in tocadas or not youtube(L):
            continue
        video = por_id.get(str(L.get("youtube_id") or ""))
        if not video or str(video.get("privacidade") or "").lower() not in PRIVADO:
            continue
        chave = titulos.chave(video.get("titulo"))
        gemeos = [v for v in publicos if titulos.chave(v.get("titulo")) == chave
                  and v["youtube_id"] not in donos]
        if canal == "historias" and not gemeos:
            curas.append(_cura(
                i, L, "historia_privada", A_CONFERIR, {},
                f"{video['youtube_id']} esta privado e nao ha publico de mesmo "
                "titulo; pode ter sido privado de proposito"))
        elif not gemeos:
            curas.append(_cura(
                i, L, "rascunho_sem_gemeo", MEDIA,
                {"publicado": False, "estado": "rascunho",
                 "rascunho_id": video["youtube_id"]},
                f"{video['youtube_id']} esta privado e nenhum video publico "
                "tem o mesmo titulo: este video nunca foi ao ar"))
        elif len(gemeos) > 1:
            curas.append(_cura(
                i, L, "rascunho_gemeo_ambiguo", A_CONFERIR, {},
                f"{video['youtube_id']} esta privado e ha {len(gemeos)} "
                "publicos com o mesmo titulo: "
                + ", ".join(g["youtube_id"] for g in gemeos)))
        else:
            gemeo = gemeos[0]
            donos.add(gemeo["youtube_id"])
            curas.append(_cura(
                i, L, "rascunho_com_gemeo", MEDIA,
                {"youtube_id": gemeo["youtube_id"],
                 "url": _link(gemeo["youtube_id"]),
                 "publicado_em": gemeo.get("publicado_em"),
                 "publicado": True, "estado": "publicado",
                 "rascunho_id": video["youtube_id"]},
                f"{video['youtube_id']} esta privado; o publico de mesmo "
                f"titulo e {gemeo['youtube_id']}"))
        tocadas.add(i)

    # 3. frase no url
    pares = dict(metricas.casar_ids(linhas, videos))
    for i, L in enumerate(linhas):
        if i in tocadas or not youtube(L) or _e_link(L.get("url")):
            continue
        if not L.get("url") or L.get("youtube_id"):
            continue
        video = pares.get(i)
        if video is not None and video["youtube_id"] in donos:
            # `casar_ids` nao sabe dos gemeos atribuidos na regra 2.
            video = None
        if video is not None:
            d = _distancia(L, video)
            curas.append(_cura(
                i, L, "link_de_frase",
                ALTA if d is not None and d <= FOLGA_ALTA else MEDIA,
                {"youtube_id": video["youtube_id"],
                 "url": _link(video["youtube_id"]),
                 "publicado_em": video.get("publicado_em"),
                 "publicado": True, "estado": "publicado",
                 "estado_texto": L.get("url")},
                f"titulo igual, no ar a {int(d.total_seconds()) if d else '?'} s "
                "da linha"))
            donos.add(video["youtube_id"])
            tocadas.add(i)
            continue
        pedacos = _pedacos(L, videos, donos)
        if pedacos:
            ids = [v["youtube_id"] for v in pedacos]
            donos.update(ids)
            curas.append(_cura(
                i, L, "link_de_pedacos", ALTA,
                {"youtube_id": ids[0], "youtube_ids": ids,
                 "url": _link(ids[0]),
                 "publicado_em": pedacos[0].get("publicado_em"),
                 "publicado": True, "estado": "publicado",
                 "estado_texto": L.get("url")},
                f"{len(ids)} pedacos \"(k de {len(ids)})\" com o titulo da "
                "parte, no ar a menos de 2 min da linha"))
            tocadas.add(i)

    # 4. formato
    for i, L in enumerate(linhas):
        if i in tocadas or not isinstance(L, dict) or "publicado" in L:
            continue
        url = L.get("url")
        depois = {"publicado": bool(url), "estado":
                  "publicado" if url else "nao_subiu"}
        if url and not _e_link(url):
            depois["url"] = ""
            depois["estado_texto"] = url
        curas.append(_cura(i, L, "formato", ALTA, depois,
                           "campo `publicado` explicito; frase fora do `url`"))
    return curas


def _pedacos(linha: dict, videos: list, donos: set) -> list:
    """Os pedacos "(1 de N)".."(N de N)" desta parte, ou `[]`.

    So vale com TODOS os N pedacos achados, cada um a menos de 2 min da
    linha: meia parte nao e publicacao.
    """
    base = titulos.chave(linha.get("titulo"))
    if not base:
        return []
    achados: dict = {}
    total = None
    for v in videos:
        m = PEDACO.search(str(v.get("titulo") or ""))
        if not m or v["youtube_id"] in donos:
            continue
        if titulos.chave(PEDACO.sub("", v["titulo"])) != base:
            continue
        d = _distancia(linha, v)
        if d is None or d > FOLGA_ALTA:
            continue
        k, n = int(m.group(1)), int(m.group(2))
        total = total or n
        if n == total:
            achados.setdefault(k, v)
    if not total or sorted(achados) != list(range(1, total + 1)):
        return []
    return [achados[k] for k in range(1, total + 1)]


def aplicar(linhas: list, curas: list) -> list:
    """As linhas depois das curas aplicaveis. Nunca aplica "a conferir"."""
    novas = [dict(L) if isinstance(L, dict) else L for L in linhas]
    for cura in curas:
        if cura["certeza"] == A_CONFERIR:
            continue
        alvo = novas[cura["linha"]]
        alvo.update(cura["depois"])
        if cura["tipo"] != "formato":
            alvo.setdefault("cura", []).append(
                {"tipo": cura["tipo"], "certeza": cura["certeza"],
                 "antes": cura["antes"],
                 "quando": datetime.now().isoformat(timespec="seconds")})
    return novas


def resumo(curas: list) -> dict:
    contagem: dict = {}
    for c in curas:
        chave = f"{c['tipo']} ({c['certeza']})"
        contagem[chave] = contagem.get(chave, 0) + 1
    return dict(sorted(contagem.items()))


# ------------------------------------------------------------------- casca
def buscar_canal(canal: str) -> list:
    """A UNICA funcao com rede: uploads do canal com privacidade e data."""
    token, _ = metricas._token(canal)
    enviados = metricas.enviados(token)
    detalhes = metricas.estatisticas([v["youtube_id"] for v in enviados], token)
    return [{**v, **detalhes.get(v["youtube_id"], {})} for v in enviados]


def ler(caminho: Path) -> list:
    linhas = []
    for bruta in caminho.read_text(encoding="utf-8").splitlines():
        if bruta.strip():
            linhas.append(json.loads(bruta))
    return linhas


def gravar(caminho: Path, linhas: list, carimbo: str) -> Path:
    copia = caminho.with_name(f"{caminho.name}.antes-cura-{carimbo}")
    shutil.copy2(caminho, copia)
    with open(caminho, "w", encoding="utf-8") as fh:
        for linha in linhas:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return copia


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="curar_ledger",
        description="cura do ledger de publicacoes (a seco por padrao)")
    parser.add_argument("--canal", choices=("builds", "historias"),
                        action="append", help="padrao: os dois")
    parser.add_argument("--gravar", action="store_true",
                        help="APLICA as curas (alta e media), com copia antes")
    args = parser.parse_args(argv)

    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta = SAIDA / carimbo
    pasta.mkdir(parents=True, exist_ok=True)
    geral = {}
    for canal in args.canal or ("builds", "historias"):
        caminho = metricas.registro_do_canal(canal)
        linhas = ler(caminho)
        curas = calcular_curas(linhas, buscar_canal(canal), canal)
        (pasta / f"{canal}.json").write_text(
            json.dumps(curas, ensure_ascii=False, indent=1), encoding="utf-8")
        geral[canal] = resumo(curas)
        _linha(f"[{canal}] {len(linhas)} linhas, {len(curas)} cura(s):")
        for chave, n in geral[canal].items():
            _linha(f"   {n:4d}  {chave}")
        if args.gravar:
            copia = gravar(caminho, aplicar(linhas, curas), carimbo)
            _linha(f"[{canal}] GRAVADO. Copia do antes: {copia}")
    (pasta / "resumo.json").write_text(
        json.dumps({"gravado": bool(args.gravar), "canais": geral},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    _linha(f"relatorio: {pasta}"
           + ("" if args.gravar else "  (A SECO: nada no ledger mudou)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
