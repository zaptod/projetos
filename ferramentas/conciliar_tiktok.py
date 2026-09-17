# -*- coding: utf-8 -*-
"""Importa para o ledger o que ja esta no TikTok e ele nao sabe.

O ledger e CEGO PARA O PASSADO do TikTok. Publicacao feita a mao, a grade
propria de 13-15/09, os pedacos antigos: nada disso ganhou linha. Em
16/09/2026 a recuperacao de atrasados leu "nunca foi" sobre partes que
estavam no ar havia dias e republicou uma serie inteira. O Adrian viu.

Consertar so a recuperacao nao bastaria: enquanto o ledger for cego, QUALQUER
leitor que pergunte "ja foi?" recebe a resposta errada. A cura e aqui, uma
vez por vez que alguem publicar por fora — e nao uma conferencia ao vivo a
cada rodada, que abriria o Chrome em toda postagem (duas coisas no mesmo
perfil ja custaram uma rodada em 16/09).

CASAR POR (GANCHO, PARTE) — NUNCA POR TITULO
--------------------------------------------
Descoberto medindo, depois de duas tentativas erradas:

    catalogo (titulo da PARTE):  "O plano que ela nunca contou (Parte 7/10)"
    TikTok   (legenda = gancho): "Eu encontrei meu quarto de infancia...
                                  Parte 7 de 10."

Sao textos DIFERENTES: a legenda vem de `descricao_completa`, o titulo vem de
`titulo`. Casar por titulo acha zero — foi o que a primeira tentativa
reportou, com confianca.

E casar so pelo gancho e pior: todas as partes da mesma historia colidem, e a
segunda tentativa deu duas partes apontando para o mesmo post. A parte fica
no MEIO da descricao, nao no fim, entao ela e extraida de onde estiver.

UM POST PERTENCE A UM VIDEO SO
------------------------------
As variantes A e B de uma geracao tem descricao identica e casam com o mesmo
`tiktok_id`. Importar as duas gravaria "publicado" sobre um video que nao
foi, com o id do irmao. O post fica com a variante principal; a `:B` continua
barrada pela guarda de titulo, que e o que ja impede a duplicata.

    python ferramentas/conciliar_tiktok.py            # a seco (padrao)
    python ferramentas/conciliar_tiktok.py --gravar
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CAPTURA_PADRAO = RAIZ / "outputs" / "_tiktok" / "captura.json"


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip()


def marca(texto: str) -> tuple:
    """`(gancho, (parte, total))` — a identidade comparavel de um post.

    Funcao pura, e e ela que os testes cobrem: todo o resto deste arquivo e
    leitura de disco em volta desta decisao.
    """
    n = _norm(texto)
    achado = re.search(r"parte\s*(\d+)\s*(?:de|/)\s*(\d+)", n)
    parte = (int(achado.group(1)), int(achado.group(2))) if achado else None
    gancho = n[:achado.start()] if achado else n
    gancho = "".join(c for c in gancho if c.isalnum() or c.isspace())
    return (re.sub(r"\s+", " ", gancho).strip()[:70], parte)


def _principal(a, b):
    """Entre dois videos que casam com o MESMO post, fica o principal."""
    if a is None:
        return b
    return b if str(a.id).endswith(":B") and not str(b.id).endswith(":B") else a


JANELA_S = 120


def _posts_ja_com_dono(linhas_do_ledger: list) -> tuple:
    """(tiktok_ids ja atribuidos, instantes de post ja ocupados).

    O SEGUNDO CONJUNTO E O QUE FALTAVA, e ele custou seis linhas falsas no
    ledger. A primeira versao so marcava como usado o post que tinha
    `tiktok_id` — mas as linhas do caminho normal NAO tem esse campo. Entao a
    principal saia dos candidatos (ja tinha linha) e a variante `:B` ficava
    sozinha na chave e HERDAVA o post dela.

    Dois posts distintos nao acontecem no mesmo segundo. Se ja existe linha
    de TikTok a menos de 120 s daquele instante, o post ja tem dono — mesmo
    que ninguem tenha anotado o id.
    """
    ids, quandos = set(), []
    for l in linhas_do_ledger or ():
        if l.get("plataforma") != "tiktok":
            continue
        if l.get("tiktok_id"):
            ids.add(l["tiktok_id"])
        try:
            quandos.append(datetime.fromisoformat(l["quando"]).timestamp())
        except Exception:                                      # noqa: BLE001
            continue
    return ids, quandos


def _tem_dono(item: dict, ids: set, quandos: list) -> bool:
    if item.get("tiktok_id") in ids:
        return True
    try:
        t = float(item.get("post_time") or 0)
    except (TypeError, ValueError):
        return False
    return any(abs(q - t) <= JANELA_S for q in quandos)


def _fonte_de(video) -> str:
    """A geracao/historia, sem a variante: `g67:build:celular:B` -> `g67`."""
    return str(getattr(video, "id", "")).split(":")[0]


def linhas_a_importar(itens_do_studio: list, videos: list,
                      ja_no_tiktok: set, ids_ja_usados: set | None = None,
                      quandos_ja_usados: list | None = None) -> list:
    """O que falta no ledger. Sem tocar em disco — e por isso e testavel.

    `ids_ja_usados` sao os `tiktok_id` que JA pertencem a alguem no ledger, e
    sem eles a ferramenta nao e idempotente. Rodando duas vezes: na primeira
    o post vai para a variante principal; na segunda a principal ja esta no
    ledger e some dos candidatos, a `:B` fica sozinha na chave e HERDA o post
    do irmao — gravando "publicado" sobre um video que nunca saiu.

    Descoberto rodando a ferramenta duas vezes de proposito, depois de a
    primeira ter gravado. A conferencia de idempotencia pagou sozinha.
    """
    usados = set(ids_ja_usados or ())
    quandos = list(quandos_ja_usados or ())
    indice = {}
    for item in itens_do_studio or ():
        if _tem_dono(item, usados, quandos):
            continue
        indice.setdefault(marca(item.get("legenda")), item)

    # MARCA AMBIGUA NAO SE IMPORTA. Nos builds a legenda nao tem "Parte", e
    # geracoes DIFERENTES compartilham os 70 primeiros caracteres: medido em
    # 17/09, 118 videos para 90 marcas, com grupos como 00025/26/28/29 e
    # 00024/27. O `escolhidos[chave]` entregava o post ao primeiro do
    # catalogo, e foi assim que o 00027 recebeu um post do 00024.
    #
    # Variante da MESMA geracao nao e ambiguidade: e o par A/B, e ali o
    # criterio (fica a principal) e deliberado.
    candidatos: dict = {}
    for v in videos or ():
        if v.id in ja_no_tiktok:
            continue
        chave = marca(getattr(v, "descricao_completa", "") or
                      getattr(v, "titulo", ""))
        if chave not in indice:
            continue
        candidatos.setdefault(chave, []).append(v)

    escolhidos: dict = {}
    for chave, lista in candidatos.items():
        if len({_fonte_de(v) for v in lista}) > 1:
            continue                    # fontes diferentes: nao da para saber
        escolhido = None
        for v in lista:
            escolhido = _principal(escolhido, v)
        escolhidos[chave] = escolhido

    novas = []
    for chave, v in escolhidos.items():
        item = indice[chave]
        try:
            quando = datetime.fromtimestamp(
                float(item.get("post_time") or 0)).isoformat(timespec="seconds")
        except Exception:                                      # noqa: BLE001
            quando = ""
        novas.append({
            "quando": quando,
            "plataforma": "tiktok",
            "url": f"https://www.tiktok.com/@/video/{item.get('tiktok_id')}",
            "publicado": True,
            "tiktok_id": item.get("tiktok_id"),
            "video_id": v.id,
            "fonte_id": getattr(v, "fonte_id", None),
            "parte": getattr(v, "parte", None),
            "partes": getattr(v, "partes", None),
            "titulo": getattr(v, "titulo", ""),
            "agendado_para": None,
            "por": "conciliar_tiktok.py",
            "visibilidade": "public",
            "estado": "ja_estava_no_tiktok",
        })
    return sorted(novas, key=lambda n: n["quando"])


def _catalogo(canal: str) -> list:
    if canal == "builds":
        from builds.publicar import catalogo as C
    else:
        from contos.publicar import catalogo as C
    return [v for v in C.listar() if getattr(v, "perfil", "") == "celular"]


def _ledger_lido(caminho: Path) -> tuple:
    """(linhas, video_ids com linha de TikTok)."""
    linhas, videos = [], set()
    for bruta in caminho.read_text(encoding="utf-8").splitlines():
        if not bruta.strip():
            continue
        try:
            linha = json.loads(bruta)
        except ValueError:
            continue
        linhas.append(linha)
        if linha.get("plataforma") == "tiktok" and linha.get("video_id"):
            videos.add(linha["video_id"])
    return linhas, videos


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--captura", default=str(CAPTURA_PADRAO),
                   help="JSON {canal: [itens do Studio]}")
    p.add_argument("--gravar", action="store_true",
                   help="grava de verdade (sem isto, so mostra)")
    p.add_argument("--so", action="append", default=None, metavar="VIDEO_ID",
                   help="grava APENAS estes video_id (repetivel). A "
                        "ferramenta propoe; quem revisou escolhe. Existe "
                        "porque nem toda proposta e decidivel: quando A e B "
                        "da mesma geracao disputam um post sem dono, nao da "
                        "para saber de quem e, e chutar marca como publicado "
                        "um video que ninguem viu.")
    args = p.parse_args(argv)

    captura = json.loads(Path(args.captura).read_text(encoding="utf-8"))
    from builds import travas
    from builds.publicar import metricas

    total = 0
    for canal in ("historias", "builds"):
        itens = captura.get(canal) or []
        if not itens:
            print(f"--- {canal}: sem captura, pulei.")
            continue
        caminho = metricas.registro_do_canal(canal)
        do_ledger, vistos = _ledger_lido(caminho)
        usados, quandos = _posts_ja_com_dono(do_ledger)
        novas = linhas_a_importar(itens, _catalogo(canal), vistos,
                                  usados, quandos)
        propostas = novas
        if args.so:
            novas = [n for n in novas if n["video_id"] in set(args.so)]
        print(f"--- {canal}: {len(itens)} no Studio, "
              f"{len(propostas)} proposta(s)"
              + (f", {len(novas)} selecionada(s)" if args.so else ""))
        for n in propostas:
            marca_sel = "  <<< GRAVA" if n in novas else ""
            print(f"      {n['quando'][:16]}  {n['video_id']:34} "
                  f"{n['tiktok_id']}{marca_sel}")
        total += len(novas)
        if not args.gravar or not novas:
            continue
        # A TRAVA E A MESMA DE TODO ESCRITOR DO LEDGER, e a copia vem antes de
        # qualquer escrita: importar errado e pior que nao importar, porque
        # marca como publicado um video que ninguem viu.
        # A TRAVA DEVOLVE BOOL, e ignorar isso e escrever por cima de quem
        # esta reescrevendo o ledger. Esta ferramenta pode esperar: abortar e
        # sempre melhor que um append no meio de uma reescrita.
        with travas.trava(metricas.nome_da_trava(canal), esperar=60.0) as peguei:
            if peguei is False:
                print(f"      NAO peguei a trava de {canal}; abortei "
                      f"(rode de novo depois).")
                continue
            carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
            copia = caminho.with_suffix(f".jsonl.antes-{carimbo}")
            shutil.copy2(caminho, copia)
            with open(caminho, "a", encoding="utf-8") as fh:
                for n in novas:
                    fh.write(json.dumps(n, ensure_ascii=False) + "\n")
            print(f"      copia em {copia.name}; {len(novas)} gravadas.")

    print(f"\ntotal: {total}")
    if not args.gravar:
        print("(a seco: nada gravado. Use --gravar.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
