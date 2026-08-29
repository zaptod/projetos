# -*- coding: utf-8 -*-
"""O FLUXO da pipeline numa leitura só: onde cada build está e o que falta.

A pipeline tem quatro trilhos que acontecem em tempos diferentes — a build
(roleta), as imagens/vídeo de identidade (dois sites, fila assíncrona), a
estreia (a luta do personagem novo) e o torneio (que consome quem já está
pronto). Cada trilho tem sua própria ferramenta de status, e é por isso que
dá para se perder: nenhuma delas responde "e agora, o que eu faço?".

Este módulo responde. Ele é PURO leitura (disco + fila, nunca escreve, nunca
abre browser) e devolve, por geração, o estado de cada etapa e UM próximo
passo — o comando exato que destrava aquela build.

Consumido pelo painel (`painel_ui.py`, página Fluxo) e pela CLI
(`python main.py fluxo`). A regra de estado mora aqui, não na tela: assim ela
é testável sem abrir janela.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ..identity import artefato, config, queue, slots

# Estados de uma etapa, do fim para o começo.
OK, RODANDO, FILA, FALHOU, AUSENTE = "ok", "rodando", "fila", "falhou", "ausente"

# Abaixo disto o arquivo não é entrega de verdade (download truncado, página
# de erro salva como imagem). Mesmo piso do `identity.status`.
BYTES_MINIMOS = 10_000

# Sem atividade por mais que isto, com trabalho pendente na fila, o worker
# provavelmente não está de pé — é a pergunta que o painel precisa responder
# sem precisar caçar processo.
SILENCIO_SUSPEITO_S = 15 * 60

# As etapas na ORDEM em que acontecem. `slot` liga a etapa à fila de
# identidade; None = etapa que não é trabalho do worker.
ETAPAS = (
    ("build", "Vídeo da build", None),
    ("personagem", "Imagem do personagem", slots.CHARACTER),
    ("arma", "Imagem da arma", slots.WEAPON),
    ("juncao", "Personagem com a arma", slots.REFERENCIA),
    ("payoff", "Vídeo do personagem", slots.CHARACTER_WEAPON),
    ("estreia", "Estreia (a luta)", None),
)
ROTULOS = {chave: rotulo for chave, rotulo, _ in ETAPAS}

# Cabeçalho de coluna: curto e DISTINTO (dois "Vídeo" e dois "Imagem" numa
# tabela de seis colunas não dizem nada).
CURTOS = {"build": "BUILD", "personagem": "PERSON.", "arma": "ARMA",
          "juncao": "JUNÇÃO", "payoff": "VÍDEO", "estreia": "ESTREIA"}

# O que a revisão de retenção (29/08/2026) entrega em cada build, além das
# etapas: a voz narrada entrou? o round decisivo da estreia está NO vídeo?
# saiu o gancho alternativo para medir? Colunas do painel e do `fluxo`.
RETENCAO = (("voz", "VOZ"), ("luta", "LUTA"), ("gancho_b", "A/B"))


def retencao_de(out_dir: Path) -> dict:
    """Leitura pura da pasta da build: voz, luta no vídeo, gancho A/B.

    `estreia_fora_do_video` é o caso que ninguém reporta sozinho: a estreia
    foi gravada (fight.json existe) mas o plano do vídeo publicável não tem o
    evento `gameplay` — o vídeo foi montado antes da luta existir e precisa
    de `--rerender --refazer-edicao`.
    """
    out_dir = Path(out_dir)
    plano = _ler_json(out_dir / "edit_plan.json") or {}
    eventos = plano.get("events") or []
    tem_luta = any(e.get("type") == "gameplay" for e in eventos)
    gancho = None
    if eventos:
        gancho = eventos[0].get("variante") or "texto"
    return {
        "voz": _arquivo_util(out_dir / "voz.wav"),
        "luta": tem_luta,
        "gancho_b": _arquivo_util(out_dir / "final_celular_ganchoB.mp4"),
        "gancho": gancho,
        "duracao": float(plano.get("total_duration") or 0.0),
        "estreia_fora_do_video": bool(
            (out_dir / "estreia" / "fight.json").is_file() and eventos and not tem_luta),
    }


def _ler_json(caminho: Path):
    try:
        with open(caminho, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _arquivo_util(caminho: Path | None) -> bool:
    return bool(caminho and caminho.is_file()
                and caminho.stat().st_size >= BYTES_MINIMOS)


def idade(iso_ou_ts) -> str:
    """"há 3min" legível, a partir de ISO ou timestamp."""
    if not iso_ou_ts:
        return "-"
    if isinstance(iso_ou_ts, (int, float)):
        segundos = max(0.0, time.time() - float(iso_ou_ts))
    else:
        try:
            quando = datetime.fromisoformat(str(iso_ou_ts))
        except ValueError:
            return "-"
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=timezone.utc)
        segundos = max(0.0, (datetime.now(timezone.utc) - quando).total_seconds())
    if segundos < 90:
        return f"{segundos:.0f}s"
    if segundos < 5400:
        return f"{segundos / 60:.0f}min"
    if segundos < 172800:
        return f"{segundos / 3600:.0f}h"
    return f"{segundos / 86400:.0f}d"


def _estado_do_slot(gid: str, slot: str, jobs: dict) -> dict:
    """O disco manda: artefato pronto é `ok` mesmo com job velho na fila."""
    caminho = artefato.caminho(gid, slot)
    if _arquivo_util(caminho):
        return {"estado": OK, "detalhe": caminho.name}
    job = jobs.get(slot)
    if job is None:
        return {"estado": AUSENTE, "detalhe": "não enfileirado"}
    estado = {queue.RODANDO: RODANDO, queue.PENDENTE: FILA,
              queue.FALHOU: FALHOU, queue.PRONTO: AUSENTE}.get(job["status"], AUSENTE)
    detalhe = {RODANDO: "gerando agora", FILA: "na fila",
               FALHOU: str(job.get("error") or "falhou")[:60],
               AUSENTE: "fila diz pronto, disco não tem"}[estado]
    if estado == FILA and job.get("depends_on"):
        pendentes = [slots.partes(d)[1] for d in job["depends_on"]
                     if not _arquivo_util(artefato.caminho(*slots.partes(d)))]
        if pendentes:
            detalhe = "esperando " + ", ".join(slots.rotulo(s) for s in pendentes)
    return {"estado": estado, "detalhe": detalhe}


def _proximo_passo(gid: str, etapas: dict, retencao: dict | None = None) -> str:
    """UMA frase: o que destrava esta build agora."""
    retencao = retencao or {}
    if etapas["build"]["estado"] != OK:
        return f"vídeo da build não saiu — rode: generate-video --rerender {gid}"

    for chave, _rotulo, slot in ETAPAS:
        if slot is None:
            continue
        estado = etapas[chave]["estado"]
        if estado == FALHOU:
            return (f"{ROTULOS[chave].lower()} falhou — re-enfileire: "
                    f"identity run {gid}")
        if estado == AUSENTE:
            return (f"falta {ROTULOS[chave].lower()} — enfileire: "
                    f"identity run {gid}")
        if estado in (FILA, RODANDO):
            return f"{ROTULOS[chave].lower()}: {etapas[chave]['detalhe']}"

    if etapas["build"].get("desatualizado"):
        return (f"clipe novo fora do vídeo — rode: generate-video --rerender "
                f"{gid} --refazer-edicao")
    if retencao.get("estreia_fora_do_video"):
        return (f"estreia gravada mas fora do vídeo — rode: generate-video "
                f"--rerender {gid} --refazer-edicao")
    if etapas["estreia"]["estado"] != OK:
        return "identidade completa — falta a estreia (a primeira luta)"
    return "completa: build, identidade e estreia prontas"


def _geracao(out_dir: Path, jobs_por_gid: dict) -> dict:
    gid = out_dir.name
    jobs = jobs_por_gid.get(gid, {})
    etapas: dict[str, dict] = {}

    # --- build: os dois mp4 finais da roleta
    finais = {perfil: out_dir / f"final_{perfil}.mp4"
              for perfil in ("celular", "normal")}
    prontos = [p for p, caminho in finais.items() if _arquivo_util(caminho)]
    etapas["build"] = {
        "estado": OK if len(prontos) == len(finais) else AUSENTE,
        "detalhe": (f"{', '.join(prontos)}" if prontos else "sem mp4 final"),
    }

    # --- identidade: um estado por slot da fila
    for chave, _rotulo, slot in ETAPAS:
        if slot is not None:
            etapas[chave] = _estado_do_slot(gid, slot, jobs)
    if not config.payoff_video_ativo():
        # Video do Digen desligado: a etapa "payoff" e cumprida pela IMAGEM
        # personagem+arma, que e o que a montagem usa no lugar do clipe.
        referencia = artefato.caminho(gid, slots.REFERENCIA)
        if _arquivo_util(referencia):
            etapas["payoff"] = {"estado": OK, "detalhe": "imagem (vídeo desligado)"}
        else:
            etapas["payoff"] = {"estado": AUSENTE,
                                "detalhe": "vídeo desligado; falta a imagem da junção"}

    # O vídeo publicável está mais VELHO que o último clipe? Então o clipe
    # existe mas não entrou no vídeo — o caso que ninguém reporta sozinho.
    mais_novo = max((artefato.caminho(gid, s).stat().st_mtime
                     for s in slots.SLOTS
                     if _arquivo_util(artefato.caminho(gid, s))), default=0.0)
    if mais_novo and prontos:
        atraso = mais_novo - min(finais[p].stat().st_mtime for p in prontos)
        etapas["build"]["desatualizado"] = atraso > 5.0
        if etapas["build"]["desatualizado"]:
            etapas["build"]["detalhe"] = "mp4 mais velho que o clipe"

    # --- estreia: a primeira luta do personagem
    estreia_dir = out_dir / "estreia"
    estreia_ok = all(_arquivo_util(estreia_dir / f"final_{p}.mp4")
                     for p in ("celular", "normal"))
    resumo = _ler_json(out_dir / "estreia.json") or {}
    if estreia_ok:
        vencedor = resumo.get("vencedor")
        adversario = resumo.get("adversario")
        placar = resumo.get("placar") or []
        if adversario and vencedor:
            detalhe = f"vs {adversario} — venceu {vencedor}"
            if len(placar) == 2:
                detalhe += f" ({placar[0]} x {placar[1]})"
        else:
            detalhe = "gravada"
    else:
        detalhe = "não gravada"
    etapas["estreia"] = {"estado": OK if estreia_ok else AUSENTE,
                         "detalhe": detalhe}

    personagem = _ler_json(out_dir / "character.json") or {}
    feitas = sum(1 for chave in ROTULOS if etapas[chave]["estado"] == OK)
    retencao = retencao_de(out_dir)
    return {
        "generation_id": gid,
        "personagem": personagem.get("nome") or "?",
        "classe": personagem.get("classe") or "",
        "arma": personagem.get("nome_arma") or "",
        "etapas": etapas,
        "retencao": retencao,
        "feitas": feitas,
        "total": len(ETAPAS),
        "completa": feitas == len(ETAPAS),
        "proximo_passo": _proximo_passo(gid, etapas, retencao),
        "quando": out_dir.stat().st_mtime,
    }


def _torneios() -> list[dict]:
    saida = []
    for pasta in sorted(config.OUTPUTS.glob("tournament_*"), reverse=True):
        dados = _ler_json(pasta / "tournament.json") or {}
        campeao = dados.get("campeao") or dados.get("champion")
        participantes = dados.get("participantes") or dados.get("players") or []
        saida.append({
            "id": pasta.name,
            "campeao": campeao if isinstance(campeao, str) else "?",
            "participantes": len(participantes),
            "video": all(_arquivo_util(pasta / f"final_{p}.mp4")
                         for p in ("celular", "normal")),
            "quando": pasta.stat().st_mtime,
        })
    return saida


def _arena() -> dict:
    try:
        from ..arena.ledger import Ledger
        ledger = Ledger()
        return {"lutas": len(ledger.lutas),
                "campeao": ledger.campeao_atual(),
                "ranking": ledger.ranking(5)}
    except Exception as exc:
        return {"lutas": 0, "campeao": None, "ranking": [],
                "erro": f"{type(exc).__name__}: {str(exc)[:60]}"}


# Tamanhos de chave que o torneio aceita (potências de 2).
CHAVES = (16, 8, 4)


def _maior_chave(quantos: int) -> int:
    return next((tamanho for tamanho in CHAVES if quantos >= tamanho), 0)


def _chaves(geracoes: list[dict]) -> dict:
    """Preparação do torneio: quem já pode entrar numa chave, por FONTE.

    São duas fontes e elas dão respostas diferentes — o torneio pode ser só
    de personagens GERADOS (os que já têm o vídeo do personagem pronto) ou
    sair do banco inteiro. Reportar só uma das duas fazia "chave possível:
    nenhuma" aparecer com 67 lutadores disponíveis no banco.
    """
    prontos = [g for g in geracoes if g["etapas"]["payoff"]["estado"] == OK]
    try:
        from ..nf_bridge import loader as nf
        _, personagens = nf.database.carregar_database()
        no_banco = len(personagens)
    except Exception:
        no_banco = 0
    chave_gerados = _maior_chave(len(prontos))
    faltam = 0
    if chave_gerados < CHAVES[0]:
        alvo = next(t for t in reversed(CHAVES) if t > len(prontos))
        faltam = alvo - len(prontos)
    return {
        "prontos": len(prontos),
        "no_banco": no_banco,
        "chave_gerados": chave_gerados,
        "chave_banco": _maior_chave(no_banco),
        "faltam_para_proxima": faltam,
    }


def snapshot(limite: int | None = 12) -> dict:
    """Uma leitura completa do fluxo. `limite` = quantas builds mais novas."""
    jobs_por_gid: dict[str, dict] = {}
    contagem = {queue.PENDENTE: 0, queue.RODANDO: 0,
                queue.FALHOU: 0, queue.PRONTO: 0}
    ultima_atividade = None
    try:
        for job in queue.listar():
            jobs_por_gid.setdefault(job["generation_id"], {})[job["slot"]] = job
            if job["status"] in contagem:
                contagem[job["status"]] += 1
            quando = job.get("updated_at")
            if quando and (ultima_atividade is None or quando > ultima_atividade):
                ultima_atividade = quando
    except Exception:
        pass

    pastas = sorted(config.OUTPUTS.glob("generation_*"),
                    key=lambda p: p.name, reverse=True)
    if limite:
        pastas = pastas[:limite]
    geracoes = [_geracao(pasta, jobs_por_gid) for pasta in pastas]

    # "O worker está de pé?" sem caçar processo: com trabalho reivindicável e
    # silêncio longo, ele não está — e é isso que trava a fila inteira.
    pendente = contagem[queue.PENDENTE] + contagem[queue.RODANDO]
    silencio = None
    if ultima_atividade:
        try:
            quando = datetime.fromisoformat(str(ultima_atividade))
            if quando.tzinfo is None:
                quando = quando.replace(tzinfo=timezone.utc)
            silencio = (datetime.now(timezone.utc) - quando).total_seconds()
        except ValueError:
            silencio = None

    alertas = []
    if pendente and (silencio is None or silencio > SILENCIO_SUSPEITO_S):
        alertas.append(
            f"{pendente} job(s) esperando e nenhuma atividade há "
            f"{idade(ultima_atividade)} — o worker provavelmente está parado.")
    if contagem[queue.FALHOU]:
        alertas.append(f"{contagem[queue.FALHOU]} job(s) com tentativas "
                       "esgotadas — re-enfileire pela linha da build.")
    for geracao in geracoes:
        if geracao["etapas"]["build"].get("desatualizado"):
            alertas.append(f"{geracao['generation_id']}: o vídeo publicável "
                           "não tem o clipe que já foi baixado.")
        if geracao.get("retencao", {}).get("estreia_fora_do_video"):
            alertas.append(f"{geracao['generation_id']}: a estreia foi gravada "
                           "mas a luta não está no vídeo — re-renderize com "
                           "--refazer-edicao.")

    return {
        "geracoes": geracoes,
        "fila": contagem,
        "ultima_atividade": ultima_atividade,
        "silencio_s": silencio,
        "arena": _arena(),
        "torneios": _torneios(),
        "chaves": _chaves(geracoes),
        "alertas": alertas,
    }


# --------------------------------------------------------------------- texto
_SIMBOLO = {OK: "OK ", RODANDO: ">> ", FILA: "...", FALHOU: "ERR",
            AUSENTE: " - "}


def imprimir(dados: dict | None = None) -> int:
    """Relatório de terminal. Devolve quantos alertas encontrou."""
    dados = snapshot() if dados is None else dados
    largura = 78
    print("\nFLUXO DA PIPELINE")
    print("=" * largura)
    cabecalho = f"  {'build':<17}" + "".join(
        f"{CURTOS[chave]:<10}" for chave, _r, _s in ETAPAS) + "".join(
        f"{rotulo:<6}" for _c, rotulo in RETENCAO) + "DUR"
    print(cabecalho)
    print("-" * largura)
    for geracao in dados["geracoes"]:
        colunas = "".join(f"{_SIMBOLO[geracao['etapas'][c]['estado']]:<10}"
                          for c, _r, _s in ETAPAS)
        ret = geracao.get("retencao", {})
        extras = "".join(f"{('OK ' if ret.get(c) else ' - '):<6}"
                         for c, _r in RETENCAO)
        dur = f"{ret['duracao']:.0f}s" if ret.get("duracao") else ""
        print(f"  {geracao['generation_id']:<17}{colunas}{extras}{dur}")
        print(f"    {geracao['personagem']} — {geracao['proximo_passo']}")
    fila = dados["fila"]
    print(f"\nFILA: {fila[queue.PENDENTE]} na fila | {fila[queue.RODANDO]} "
          f"rodando | {fila[queue.FALHOU]} falhas | última atividade há "
          f"{idade(dados['ultima_atividade'])}")
    chaves = dados["chaves"]
    com_gerados = (f"chave de {chaves['chave_gerados']}"
                   if chaves["chave_gerados"]
                   else f"faltam {chaves['faltam_para_proxima']} para a de 4")
    print(f"TORNEIO: {chaves['prontos']} build(s) com vídeo pronto ({com_gerados})"
          f" | banco: {chaves['no_banco']} personagens "
          f"(chave de {chaves['chave_banco']})")
    arena = dados["arena"]
    print(f"ARENA: {arena['lutas']} luta(s) | campeão: "
          f"{arena['campeao'] or '-'}")
    if dados["alertas"]:
        print("\nALERTAS")
        for alerta in dados["alertas"]:
            print(f"  ! {alerta}")
    return len(dados["alertas"])


__all__ = ["CURTOS", "ETAPAS", "ROTULOS", "OK", "RODANDO", "FILA", "FALHOU",
           "AUSENTE", "idade", "imprimir", "snapshot"]
