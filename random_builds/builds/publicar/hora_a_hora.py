# -*- coding: utf-8 -*-
"""Views dos videos NOVOS do YouTube, de hora em hora (21/10/2026).

Por que existe. A medida da semana do PLANO compara os duelos da mudanca com
os de antes — e o video de ontem nao se compara com o de semana passada pelo
total de hoje: o mais velho teve mais horas no ar. A coleta do dia (07:02)
fotografa cada video UMA vez por dia; para saber quantas views um video
tinha com 6, 12, 24 ou 48 horas de vida e preciso ler mais vezes enquanto
ele e novo, que e quando o numero anda.

O que faz. Uma chamada `videos.list` (Data API, `part=statistics,status`,
**1 unidade** de cota das 10.000 do dia) para ate 50 videos do canal
publicados nas ultimas 48 h, lidos do ledger. Grava UMA linha por leitura em
`outputs/_metricas_hora/<AAAA-MM-DD>.jsonl`, com a hora da leitura e, por
video, views/likes/comentarios e a IDADE em horas. Pasta propria: o
`carregar_salvas` le todo `.json` de `_metricas/` como video.

Quem chama. O disparo de hora em hora da geracao de builds
(`main.py noite`, tarefas `NeuralFights_gerar_HH`, 00-05 e 07-23 h, no
minuto :02), ANTES de qualquer saida dele — gerar ou nao gerar, a leitura
acontece. Nenhuma tarefa nova no Agendador.

As tres perguntas da lei:

- ZERO: sem video novo, a linha e gravada com `estado: vazio` e
  `pedidos: 0` — ausencia de video e um evento com numero, e nenhuma cota e
  gasta. Video pedido que a API nao devolve vai para `nao_devolvidos`; se
  NENHUM volta, e `erro`, nunca "0 views".
- DENOMINADOR: idade = hora da leitura - `quando` do ledger (local). Linha
  sem `youtube_id` nao e lida e e CONTADA (`sem_id`).
- EXCECAO: token, rede ou recusa do Google viram linha `estado: erro` com o
  motivo e UMA linha de erro `metricas` no diario por dia e tipo de erro (que
  chega ao Telegram). Nunca levanta para quem chama.

    python -m builds.publicar.hora_a_hora --ver     o que leria agora (sem rede)
    python -m builds.publicar.hora_a_hora           le e grava (1 unidade)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from . import metricas

HORAS = 48
MAXIMO_POR_CHAMADA = 50
# Duas leituras boas a menos disto nao acrescentam nada (a tarefa que roda de
# novo, a mao no meio): a segunda sai sem gastar cota.
INTERVALO_MINIMO_MIN = 30
DIAS_GUARDADOS = 60

# Os testes apontam para um tmpdir; `None` = `<outputs de builds>/_metricas_hora`.
PASTA = None


def pasta() -> Path:
    return Path(PASTA) if PASTA else Path(metricas.OUTPUTS) / "_metricas_hora"


def arquivo_do_dia(dia: date) -> Path:
    return pasta() / f"{dia.isoformat()}.jsonl"


def _instante(texto) -> datetime | None:
    try:
        return datetime.fromisoformat(str(texto)[:19])
    except (TypeError, ValueError):
        return None


def recentes(linhas: list, agora: datetime, horas: float = HORAS) -> tuple:
    """`([(youtube_id, quando)], sem_id)` das publicacoes do YouTube com
    menos de `horas`. O mesmo id em duas linhas conta uma vez (a mais velha:
    e a hora em que o video nasceu)."""
    corte = agora - timedelta(hours=horas)
    vistos: dict = {}
    sem_id = 0
    for linha in linhas or []:
        if not isinstance(linha, dict) or not metricas.publicado(linha):
            continue
        if str(linha.get("plataforma") or "youtube") != "youtube":
            continue
        quando = _instante(linha.get("quando"))
        if quando is None or not (corte <= quando <= agora):
            continue
        yid = linha.get("youtube_id")
        if not yid:
            sem_id += 1
            continue
        if yid not in vistos or quando < vistos[yid]:
            vistos[yid] = quando
    ordem = sorted(vistos.items(), key=lambda par: par[1], reverse=True)
    return ordem, sem_id


def ler(canal: str = "builds", agora: datetime | None = None, *,
        linhas: list | None = None, token: str | None = None) -> dict:
    """UMA leitura. Levanta se a API falhar (quem chama decide o aviso).

    `linhas` (o ledger) e `token` existem para os testes; o padrao e o
    ledger do canal e o OAuth dele. A rede passa por `metricas._get`, que
    conta a chamada e tenta de novo UMA vez se a conexao cair.
    """
    agora = agora or datetime.now()
    if linhas is None:
        linhas = metricas.publicados(canal)
    ids, sem_id = recentes(linhas, agora)
    leitura = {"quando": agora.isoformat(timespec="seconds"), "canal": canal,
               "horas": HORAS, "pedidos": len(ids), "sem_id": sem_id,
               "chamadas": 0, "videos": {}, "nao_devolvidos": []}
    if len(ids) > MAXIMO_POR_CHAMADA:
        # Com a grade de hoje (3/dia) nao passa de ~6; se passar, o MAIS NOVO
        # fica (e o que mais muda) e o corte e dito.
        leitura["fora_do_teto"] = len(ids) - MAXIMO_POR_CHAMADA
        ids = ids[:MAXIMO_POR_CHAMADA]
    if not ids:
        leitura["estado"] = "vazio"
        return leitura
    token = token or metricas._token(canal)[0]
    resposta = metricas._get(
        "data", metricas.API_VIDEOS, timeout=30,
        params={"part": "statistics,status",
                "id": ",".join(yid for yid, _q in ids),
                "maxResults": MAXIMO_POR_CHAMADA},
        headers={"Authorization": f"Bearer {token}"})
    leitura["chamadas"] = 1
    if not resposta.ok:
        raise metricas.RecusaDaAPI(resposta, api="data")
    lida_em = agora
    itens ={item.get("id"): item for item in (resposta.json() or {}).get("items") or []
             if isinstance(item, dict)}
    for yid, quando in ids:
        item = itens.get(yid)
        if item is None:
            leitura["nao_devolvidos"].append(yid)
            continue
        st = item.get("statistics") or {}

        def inteiro(chave):
            try:
                return int(st[chave])
            except (KeyError, TypeError, ValueError):
                return None          # o campo escondido nao e zero
        leitura["videos"][yid] = {
            "views": inteiro("viewCount"), "likes": inteiro("likeCount"),
            "comentarios": inteiro("commentCount"),
            "privacidade": (item.get("status") or {}).get("privacyStatus"),
            "publicado": quando.isoformat(timespec="seconds"),
            "idade_h": round((lida_em - quando).total_seconds() / 3600.0, 2)}
    if not leitura["videos"]:
        leitura["estado"] = "erro"
        leitura["erro"] = (f"NadaDevolvido: a API nao devolveu nenhum dos "
                           f"{len(ids)} video(s) pedidos (privados? apagados? "
                           "token de outro canal?)")
    else:
        leitura["estado"] = "ok"
    return leitura


def carregar(dias: int = 16, hoje: date | None = None,
             pasta_das_leituras: Path | None = None) -> list:
    """Todas as leituras dos ultimos `dias`, na ordem do arquivo. Linha
    ilegivel e pulada."""
    hoje = hoje or date.today()
    base = Path(pasta_das_leituras) if pasta_das_leituras else pasta()
    saida = []
    for i in range(dias - 1, -1, -1):
        caminho = base / f"{(hoje - timedelta(days=i)).isoformat()}.jsonl"
        try:
            texto = caminho.read_text(encoding="utf-8")
        except OSError:
            continue
        for linha in texto.splitlines():
            try:
                dado = json.loads(linha)
            except ValueError:
                continue
            if isinstance(dado, dict):
                saida.append(dado)
    return saida


def _gravar(leitura: dict, agora: datetime) -> Path:
    destino = arquivo_do_dia(agora.date())
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(leitura, ensure_ascii=False) + "\n")
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except OSError:
            pass
    return destino


def _podar(agora: datetime) -> None:
    try:
        corte = (agora.date() - timedelta(days=DIAS_GUARDADOS)).isoformat()
        for arquivo in pasta().glob("*.jsonl"):
            if arquivo.stem < corte:
                arquivo.unlink()
    except OSError:
        pass


def _ja_lida(agora: datetime) -> bool:
    """Ja houve leitura BOA (ou vazia) ha menos de `INTERVALO_MINIMO_MIN`?"""
    limite = agora - timedelta(minutes=INTERVALO_MINIMO_MIN)
    for leitura in carregar(dias=2, hoje=agora.date()):
        quando = _instante(leitura.get("quando"))
        if (quando and limite < quando <= agora
                and leitura.get("estado") in ("ok", "vazio")):
            return True
    return False


def _ja_avisado(agora: datetime, tipo: str) -> bool:
    for leitura in carregar(dias=1, hoje=agora.date()):
        if leitura.get("estado") == "erro" and leitura.get("avisado") == tipo:
            return True
    return False


def disparo(canal: str = "builds", agora: datetime | None = None, *,
            log=print, **dubles) -> dict:
    """O passo de hora em hora. NUNCA levanta. Devolve a leitura gravada
    (ou `{"estado": "pulada"}` quando ja houve uma ha menos de 30 min)."""
    agora = agora or datetime.now()
    try:
        if _ja_lida(agora):
            log(f"[hora-a-hora] {canal}: ja lido ha menos de "
                f"{INTERVALO_MINIMO_MIN} min; nao gasto cota de novo.")
            return {"estado": "pulada"}
    except Exception:                                          # noqa: BLE001
        pass          # sem saber, le de novo: repetir e o erro barato
    try:
        leitura = ler(canal, agora, **dubles)
    except Exception as exc:                                   # noqa: BLE001
        # O TIPO agrupa o aviso (um por dia e tipo). Recusa da API leva o
        # codigo e o motivo ("403 quotaExceeded"), nao o nome da excecao: com
        # o nome, toda recusa era "RuntimeError" e so a 1a do dia avisava.
        leitura = {"quando": agora.isoformat(timespec="seconds"),
                   "canal": canal, "estado": "erro", "videos": {},
                   "erro": f"{type(exc).__name__}: {exc}"[:300],
                   "tipo_do_erro": str(getattr(exc, "tipo", "") or type(exc).__name__)}
    if leitura.get("estado") == "erro":
        tipo = str(leitura.get("tipo_do_erro")
                   or str(leitura.get("erro") or "").split(":")[0])
        try:
            avisado = _ja_avisado(agora, tipo)
        except Exception:                                      # noqa: BLE001
            avisado = False
        if not avisado:
            try:
                from .. import atividade
                atividade.registrar(
                    "metricas", atividade.ERRO,
                    f"[hora a hora] leitura das views dos videos novos de "
                    f"{canal} falhou: {leitura.get('erro')}"[:300],
                    canal=canal, etapa="metricas.hora_a_hora")
            except Exception:                                  # noqa: BLE001
                pass
        leitura["avisado"] = tipo
    try:
        _gravar(leitura, agora)
        _podar(agora)
    except Exception as exc:                                   # noqa: BLE001
        log(f"[hora-a-hora] {canal}: nao consegui gravar a leitura: "
            f"{type(exc).__name__}: {exc}")
    log(f"[hora-a-hora] {canal}: {texto(leitura)}")
    return leitura


def texto(leitura: dict) -> str:
    estado = leitura.get("estado")
    if estado == "vazio":
        return (f"nenhum video do YouTube com menos de {HORAS} h no ledger"
                + (f" ({leitura['sem_id']} sem youtube_id)" if leitura.get("sem_id") else "")
                + "; nenhuma cota gasta.")
    if estado == "erro":
        return f"FALHOU: {leitura.get('erro')}"
    partes = [f"{yid} {v.get('views')} views aos {v.get('idade_h')} h"
              for yid, v in (leitura.get("videos") or {}).items()]
    extra = ""
    if leitura.get("nao_devolvidos"):
        extra += f"; a API nao devolveu {', '.join(leitura['nao_devolvidos'])}"
    if leitura.get("sem_id"):
        extra += f"; {leitura['sem_id']} linha(s) sem youtube_id"
    return (f"{len(partes)} video(s), {leitura.get('chamadas', 0)} chamada(s): "
            + "; ".join(partes) + extra)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--canal", default="builds")
    parser.add_argument("--ver", action="store_true",
                        help="so diz o que leria (sem rede, sem gravar)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    agora = datetime.now()
    if args.ver:
        ids, sem_id = recentes(metricas.publicados(args.canal), agora)
        print(f"{len(ids)} video(s) com menos de {HORAS} h ({sem_id} sem id):")
        for yid, quando in ids:
            print(f"  {yid}  {quando:%d/%m %H:%M}  "
                  f"{(agora - quando).total_seconds() / 3600:.1f} h")
        return 0 if ids else 1
    leitura = disparo(args.canal, agora)
    return 0 if leitura.get("estado") in ("ok", "vazio", "pulada") else 1


if __name__ == "__main__":
    raise SystemExit(main())
