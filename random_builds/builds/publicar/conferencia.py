# -*- coding: utf-8 -*-
"""O ledger contra o canal — a unica pergunta que ninguem fazia.

Por que existe: entre 10 e 15/09/2026, 29 videos entraram no
`publicados.jsonl` como publicados e estavam como RASCUNHO no canal. Cinco
dias, um por postagem, e nenhum alarme disparou — porque auditoria, gordura
e meta leem o MESMO ledger que estava errado. `auditoria.metas()` compara
ledger contra grade, o que e o ledger contra si mesmo. Quem descobriu foi o
Adrian, olhando o canal com os proprios olhos.

O que ja existia e nao resolvia:

  `metricas.reconciliar` baixa os uploads reais do canal e casa por titulo,
  mas so PREENCHE id faltante — nunca denuncia linha sem video nem video sem
  linha. E mutirao de completar, nao auditoria.

  `tiktok_metricas.casar` casa a hora da postagem com o ledger e apenas LOGA
  a taxa. O numero passava na tela toda noite sem ninguem somar.

A regra desta casa: `conferir` e PURA quando as duas listas sao injetadas.
So `buscar_no_canal` toca a rede, e ela e chamada em um lugar so. E o que
permite testar a deteccao do caso de 15/09 sem pedir nada ao YouTube.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from . import metricas, titulos

# Janela curta de proposito. O acervo antigo nao tem laudo nem id, e uma
# conferencia que acende para tudo no primeiro dia e uma conferencia que
# ninguem olha no segundo.
DIAS_PADRAO = 3


def pasta(canal: str = "builds") -> Path:
    return metricas.pasta_do_canal(canal).parent / "_conferencia"


def _recente(quando: str, desde: date) -> bool:
    try:
        return datetime.fromisoformat(str(quando)).date() >= desde
    except (TypeError, ValueError):
        return False


def conferir(canal: str = "builds", plataforma: str = "youtube", *,
             dias: int = DIAS_PADRAO, publicados=None, no_canal=None,
             hoje: date | None = None) -> dict:
    """O que o ledger afirma contra o que o canal tem de fato.

    `publicados` sao as linhas do ledger; `no_canal` e o que a plataforma
    devolveu. Injetando as duas, nada aqui toca a rede.
    """
    hoje = hoje or date.today()
    desde = hoje - timedelta(days=max(0, int(dias)))
    if publicados is None:
        publicados = metricas.publicados(canal)
    if no_canal is None:
        no_canal = buscar_no_canal(canal, plataforma)

    linhas = [l for l in (publicados or ())
              if isinstance(l, dict) and l.get("plataforma") == plataforma
              and _recente(l.get("quando"), desde)]
    do_canal = [v for v in (no_canal or ()) if isinstance(v, dict)]

    por_id = {str(v.get("id")): v for v in do_canal if v.get("id")}
    por_titulo = {}
    for v in do_canal:
        chave = titulos.chave(v.get("titulo"))
        if chave:
            por_titulo.setdefault(chave, v)

    fantasmas, casados, rascunhos, so_sd = [], [], [], []
    vistos = set()
    for linha in linhas:
        alvo = por_id.get(str(linha.get("youtube_id") or "")) \
            or por_titulo.get(titulos.chave(linha.get("titulo")))
        ficha = {"video_id": linha.get("video_id"),
                 "titulo": linha.get("titulo"),
                 "quando": linha.get("quando"),
                 "prova_ok": linha.get("prova_ok")}
        if alvo is None:
            # O LEDGER AFIRMA E O CANAL NAO TEM. E o nome exato do defeito.
            fantasmas.append(ficha)
            continue
        vistos.add(id(alvo))
        casados.append(ficha)
        if str(alvo.get("privacidade") or "").lower() in ("private", "privado"):
            # A ASSINATURA DO RASCUNHO DE 15/09/2026.
            rascunhos.append({**ficha, "youtube_id": alvo.get("id"),
                              "privacidade": alvo.get("privacidade"),
                              "upload": alvo.get("upload")})
        if str(alvo.get("definicao") or "").lower() == "sd":
            so_sd.append({**ficha, "youtube_id": alvo.get("id")})

    orfaos = [{"youtube_id": v.get("id"), "titulo": v.get("titulo"),
               "publicado_em": v.get("publicado_em")}
              for v in do_canal if id(v) not in vistos]

    contagem = {}
    for v in do_canal:
        chave = titulos.chave(v.get("titulo"))
        if chave:
            contagem.setdefault(chave, []).append(v.get("id"))
    duplicados = [{"chave": k, "ids": ids}
                  for k, ids in contagem.items() if len(ids) > 1]

    sujo = bool(fantasmas or rascunhos)
    return {
        "canal": canal, "plataforma": plataforma,
        "dia": hoje.isoformat(), "janela_dias": int(dias),
        "no_ledger": len(linhas), "no_canal": len(do_canal),
        "casados": len(casados),
        "fantasmas": fantasmas, "orfaos": orfaos,
        "rascunhos": rascunhos, "so_sd": so_sd, "duplicados": duplicados,
        "taxa": round(len(casados) / len(linhas), 3) if linhas else 1.0,
        "veredito": "sujo" if sujo else "limpo",
        "quando": datetime.now().isoformat(timespec="seconds"),
    }


def buscar_no_canal(canal: str = "builds",
                    plataforma: str = "youtube") -> list:
    """A UNICA funcao com rede. Devolve o que a plataforma diz ter."""
    if plataforma != "youtube":
        raise ValueError(
            "so o YouTube tem consulta direta. O TikTok nao expoe a lista "
            "por API: a conferencia dele passa pelo Studio, em "
            "`tiktok_metricas.coletar`.")
    # `_token` devolve (token, credenciais). Ate 16/09/2026 a TUPLA inteira
    # ia para o cabecalho `Authorization`, o Google respondia 401, e o 401
    # virava "token invalido ou revogado" — um diagnostico falso que chegou
    # a ser repassado ao Adrian como "os tres tokens estao revogados".
    token, _ = metricas._token(canal)
    enviados = metricas.enviados(token)
    ids = [v.get("youtube_id") or v.get("id") for v in enviados]
    ids = [i for i in ids if i]
    detalhes = metricas.estatisticas(ids, token) if ids else {}
    saida = []
    for v in enviados:
        vid = v.get("youtube_id") or v.get("id")
        saida.append({**(detalhes.get(vid) or {}),
                      "id": vid, "titulo": v.get("titulo")})
    return saida


def salvar(ficha: dict) -> Path:
    destino = pasta(ficha.get("canal", "builds"))
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{ficha.get('dia', 'hoje')}.json"
    caminho.write_text(json.dumps(ficha, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    return caminho


def ultima(canal: str = "builds") -> dict:
    """A conferencia mais recente daquele canal, ou `{}`."""
    try:
        arquivos = sorted(pasta(canal).glob("*.json"))
        return json.loads(arquivos[-1].read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, IndexError):
        return {}


def conferir_tudo(canais=("builds", "historias"), *, dias: int = DIAS_PADRAO,
                  log=print) -> dict:
    """Confere cada canal, grava e ACENDE o alarme quando esta sujo.

    O alarme nao tem uma linha de Telegram: uma linha de erro no diario ja
    vira aviso no celular (`bot._alertar`) e ja convoca a apuracao automatica
    do Claude. Escrever um segundo caminho de aviso seria criar a proxima
    divergencia.
    """
    from .. import atividade

    fichas = {}
    for canal in canais:
        try:
            ficha = conferir(canal, dias=dias)
        except Exception as exc:                               # noqa: BLE001
            # Servico da noite NAO derruba rodada. E o OAuth de um canal pode
            # estar morto sem que o outro esteja.
            log(f"[conferencia] {canal}: {type(exc).__name__}: {exc}")
            fichas[canal] = {"canal": canal, "dia": date.today().isoformat(),
                             "erro": f"{type(exc).__name__}: {exc}"}
            # A FALHA TAMBEM VAI PARA DISCO. Sem isto a pagina via "nunca
            # rodou" — medido em 16/09/2026, com os tres tokens revogados — e
            # "nunca rodou" e "rodou e o token morreu" pedem acoes diferentes.
            try:
                salvar(fichas[canal])
            except OSError:
                pass
            continue
        salvar(ficha)
        fichas[canal] = ficha
        log(f"[conferencia] {canal}: {ficha['casados']}/{ficha['no_ledger']} "
            f"casados, {len(ficha['fantasmas'])} fantasma(s), "
            f"{len(ficha['rascunhos'])} rascunho(s) — {ficha['veredito']}")
        if ficha["veredito"] == "sujo":
            atividade.registrar(
                "publicacao", atividade.ERRO,
                f"conferencia {canal}/{ficha['plataforma']}: "
                f"{len(ficha['fantasmas'])} no ledger sem video no canal, "
                f"{len(ficha['rascunhos'])} rascunho(s), "
                f"{len(ficha['orfaos'])} orfao(s) em {ficha['janela_dias']} "
                "dia(s)", canal=canal)
    return fichas


def main(argv=None) -> int:
    """`python -m builds.publicar.conferencia --canal builds --dias 1`."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="conferencia",
        description="o ledger contra o que o canal realmente tem")
    parser.add_argument("--canal", default="", help="builds, historias, ou "
                                                    "vazio para os dois")
    parser.add_argument("--dias", type=int, default=DIAS_PADRAO)
    args = parser.parse_args(argv)

    canais = (args.canal,) if args.canal else ("builds", "historias")
    fichas = conferir_tudo(canais, dias=args.dias)
    sujo = False
    for canal, ficha in fichas.items():
        if ficha.get("erro"):
            print(f"[{canal}] NAO DEU PARA CONFERIR: {ficha['erro']}")
            continue
        sujo = sujo or ficha.get("veredito") == "sujo"
        for nome in ("fantasmas", "rascunhos", "orfaos", "so_sd"):
            for item in (ficha.get(nome) or [])[:6]:
                print(f"   {nome[:-1]:10} {item.get('titulo') or item.get('youtube_id')}")
    return 1 if sujo else 0


__all__ = ["DIAS_PADRAO", "buscar_no_canal", "conferir", "conferir_tudo",
           "main", "pasta", "salvar", "ultima"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
