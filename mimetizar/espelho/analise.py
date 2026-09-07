# -*- coding: utf-8 -*-
"""Etapa 3: o laco que faz o ChatGPT e o Gemini lerem o acervo.

Um video por TURNO, varios turnos por CHAT. As duas escolhas tem motivo:

  um video por turno   pedir cinco fichas numa resposta so devolve cinco
                       fichas rasas, e a quinta costuma vir cortada.
  varios por chat      o cabecalho do canal (o que ja se sabe dele, medido)
                       vale para todos; reenviar a cada video seria pagar o
                       mesmo contexto 177 vezes.

O chat e trocado a cada `lote` videos porque conversa longa comeca a
responder pela ficha anterior em vez de pela atual — o modelo "aprende" o
formato e para de olhar o dossie.

Retomada: a ficha e um arquivo. Existe = pulado. Um acervo grande leva
horas, o navegador cai, a conta bate limite de uso — e nada disso pode
custar o que ja foi analisado.

O texto CRU e gravado antes de qualquer parse. Quando o formato do site ou
do modelo mudar, a resposta original esta em `conversa/`, e a diferenca
aparece la em vez de virar "ficha vazia" sem explicacao.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import canal as _canal
from . import config, dossie, estado, ficha

PROVEDORES = ("chatgpt", "gemini")


class NaoAnalisou(RuntimeError):
    """Erro humano: o que se tentou, e o que fazer."""


def _diario(status: str, detalhe: str, canal_id: str = "") -> None:
    """Anota no diario da Vila. Nunca levanta — observabilidade nao derruba."""
    try:
        import builds.atividade as atividade
        atividade.registrar("mimetizar", status, detalhe, canal=canal_id)
    except Exception:                                          # noqa: BLE001
        pass


def analisavel(pasta: Path, video_id: str) -> bool:
    """Da para montar um dossie deste video?

    O que sobe no chat e o DOSSIE, nunca o mp4 — entao a pergunta certa e se
    ha medida (ou um dossie ja montado), nao se o video ainda esta em disco.
    A diferenca importa desde que o `absorver` passou a apagar o video assim
    que os dois provedores terminam: exigir o mp4 faria a segunda passada
    achar que nao ha nada para analisar.
    """
    pasta = Path(pasta)
    return ((pasta / "medidas" / f"{video_id}.json").is_file()
            or (pasta / "dossies" / f"{video_id}.md").is_file())


def pendentes(pasta: Path, provedor: str, *, limite: int = 0,
              refazer: bool = False, so_estes=None) -> list:
    """Os videos que ainda nao tem ficha daquele provedor."""
    destino = pasta / "fichas" / provedor
    filtro = set(so_estes) if so_estes else None
    alvos = []
    for video in _canal.videos(pasta):
        if filtro is not None and video["id"] not in filtro:
            continue
        if not analisavel(pasta, video["id"]):
            continue
        if not refazer and (destino / f"{video['id']}.json").is_file():
            continue
        alvos.append(video)
    return alvos[:limite] if limite and limite > 0 else alvos


def _lotes(itens: list, tamanho: int) -> list:
    tamanho = max(1, int(tamanho))
    return [itens[i:i + tamanho] for i in range(0, len(itens), tamanho)]


def _guardar_conversa(pasta: Path, provedor: str, nome: str, texto: str) -> None:
    destino = pasta / "conversa" / provedor
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"{nome}.txt").write_text(texto, encoding="utf-8")


def _uma_ficha(cliente, pasta: Path, video: dict, *, ordem: int, total: int,
               cfg: dict, provedor: str, log) -> dict:
    """Um turno: manda o dossie, le a ficha, conserta uma vez se precisar."""
    texto_dossie = dossie.montar(pasta, video, cfg=cfg)
    dossie.gravar(pasta, video, cfg=cfg)
    anexos = []
    if cfg.get("anexar_contato", True):
        folha = dossie.contato_de(pasta, video["id"])
        if folha is not None:
            anexos = [folha]

    pergunta = ficha.prompt_ficha(video, texto_dossie, ordem=ordem, total=total)
    timeout = float(cfg.get("resposta_timeout_s") or 600)
    resposta = cliente.perguntar(pergunta, timeout=timeout, anexos=anexos)
    _guardar_conversa(pasta, provedor, video["id"], resposta)

    lida = ficha.parse_ficha(resposta)
    problemas = ficha.problemas_da_ficha(lida, cfg=cfg)
    tentativas = max(1, int(cfg.get("tentativas_por_video") or 2))
    volta = 1
    while problemas and volta < tentativas:
        log(f"           ficha incompleta ({problemas[0]}); repergunto.")
        resposta = cliente.perguntar(ficha.prompt_conserto(problemas),
                                     timeout=timeout)
        _guardar_conversa(pasta, provedor, f"{video['id']}_conserto{volta}",
                          resposta)
        candidata = ficha.parse_ficha(resposta)
        if not candidata.get("_ilegivel"):
            lida = candidata
        problemas = ficha.problemas_da_ficha(lida, cfg=cfg)
        volta += 1

    lida["video_id"] = video["id"]
    lida["titulo"] = video.get("titulo", "")
    lida["provedor"] = provedor
    lida["problemas"] = problemas
    return lida


def _gravar_ficha(pasta: Path, provedor: str, lida: dict) -> Path:
    destino = pasta / "fichas" / provedor
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{lida['video_id']}.json"
    # O bruto ja esta em `conversa/`; repeti-lo aqui triplicaria a pasta de
    # fichas sem servir a ninguem.
    magro = {k: v for k, v in lida.items() if k != "bruto"}
    caminho.write_text(json.dumps(magro, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return caminho


def analisar_provedor(canal_id: str, provedor: str, *, limite: int = 0,
                      refazer: bool = False, headless: bool = False,
                      so_estes=None, log=print) -> dict:
    """Roda um provedor sobre os videos pendentes."""
    from contos.llm.cliente import LLMFalhou, abrir_cliente

    pasta = config.pasta_do_canal(canal_id)
    cfg = config.carregar("analise")
    alvos = pendentes(pasta, provedor, limite=limite, refazer=refazer,
                      so_estes=so_estes)
    if not alvos:
        log(f"[{provedor}] nada pendente — todas as fichas ja existem.")
        return {"provedor": provedor, "fichas": 0, "incompletas": 0,
                "falharam": 0, "pendentes": 0}

    cabecalho = dossie.cabecalho_do_canal(pasta)
    lotes = _lotes(alvos, int(cfg.get("lote") or 6))
    log(f"[{provedor}] {len(alvos)} video(s) em {len(lotes)} chat(s).")
    _diario("inicio", f"{provedor}: {len(alvos)} videos de {canal_id}",
            canal_id)

    feitas, incompletas, falharam = 0, 0, []
    try:
        with abrir_cliente(provedor, headless=headless, log=log) as cliente:
            for numero, lote in enumerate(lotes, 1):
                log(f"\n[{provedor}] chat {numero}/{len(lotes)} "
                    f"({len(lote)} videos)")
                cliente.abrir(novo_chat=True)
                abertura = ficha.prompt_abertura(cabecalho, total=len(lote),
                                                 cfg=cfg)
                resposta = cliente.perguntar(abertura, timeout=180)
                _guardar_conversa(pasta, provedor, f"abertura_lote{numero:03d}",
                                  abertura + "\n\n--- resposta ---\n" + resposta)

                for ordem, video in enumerate(lote, 1):
                    titulo = video.get("titulo", "")[:52]
                    log(f"[{provedor}] {video['id']}  {titulo}")
                    try:
                        lida = _uma_ficha(cliente, pasta, video, ordem=ordem,
                                          total=len(lote), cfg=cfg,
                                          provedor=provedor, log=log)
                    except LLMFalhou as exc:
                        log(f"           ! {exc}")
                        falharam.append((video["id"], str(exc)))
                        continue
                    _gravar_ficha(pasta, provedor, lida)
                    feitas += 1
                    if lida["problemas"]:
                        incompletas += 1
                        log(f"           gravada COM PENDENCIA: "
                            f"{lida['problemas'][0]}")
                    else:
                        log(f"           {ficha.resumo_da_ficha(lida)}")
    except LLMFalhou as exc:
        _diario("erro", f"{provedor}: {exc}", canal_id)
        raise NaoAnalisou(str(exc)) from exc
    except KeyboardInterrupt:
        log(f"\n[{provedor}] interrompido. {feitas} ficha(s) ficaram em disco.")
        _diario("erro", f"{provedor}: interrompido em {canal_id}", canal_id)
        raise

    sobrando = len(pendentes(pasta, provedor, so_estes=so_estes))
    estado.marcar(pasta, f"analisar_{provedor}", fichas=feitas,
                  incompletas=incompletas, falharam=len(falharam))
    _diario("ok", f"{provedor}: {feitas} fichas de {canal_id}", canal_id)
    if falharam:
        log(f"\n[{provedor}] {len(falharam)} falharam:")
        for video_id, motivo in falharam[:6]:
            log(f"    {video_id}: {motivo[:110]}")
    return {"provedor": provedor, "fichas": feitas,
            "incompletas": incompletas, "falharam": len(falharam),
            "pendentes": sobrando}


def analisar(canal_id: str, *, provedor: str = "ambos", limite: int = 0,
             refazer: bool = False, headless: bool = False, so_estes=None,
             log=print) -> dict:
    """Roda um provedor, ou os dois em sequencia.

    Aqui em sequencia porque os dois dividem o mesmo console. Para os dois
    AO MESMO TEMPO, use `absorver`: ele levanta um processo por provedor, e
    as travas de `builds.travas` sao por pasta de perfil do Chrome, entao
    ChatGPT e Gemini nao disputam nada.
    """
    escolhidos = (list(PROVEDORES) if provedor == "ambos"
                  else [str(provedor).lower()])
    for nome in escolhidos:
        if nome not in PROVEDORES:
            raise NaoAnalisou(
                f"provedor desconhecido: {nome!r}. "
                f"Use {', '.join(PROVEDORES)} ou 'ambos'.")

    resultados = []
    for nome in escolhidos:
        resultados.append(analisar_provedor(
            canal_id, nome, limite=limite, refazer=refazer,
            headless=headless, so_estes=so_estes, log=log))
    return {
        "provedores": resultados,
        "fichas": sum(r["fichas"] for r in resultados),
        "incompletas": sum(r["incompletas"] for r in resultados),
        "falharam": sum(r["falharam"] for r in resultados),
        "pendentes": sum(r["pendentes"] for r in resultados),
    }


def carregar_fichas(pasta: Path, provedor: str) -> list:
    """As fichas gravadas daquele provedor, na ordem do catalogo."""
    destino = Path(pasta) / "fichas" / provedor
    if not destino.is_dir():
        return []
    encontradas = []
    for video in _canal.videos(pasta):
        caminho = destino / f"{video['id']}.json"
        if not caminho.is_file():
            continue
        try:
            encontradas.append(json.loads(
                caminho.read_text(encoding="utf-8-sig")))
        except (OSError, ValueError):
            continue
    return encontradas
