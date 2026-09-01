"""Auditoria de origem: que artefato ja gravado tem prova de que e nosso?

A prova de origem (proveniencia.py) so existe para o que o worker baixa de
agora em diante. O que ja esta no disco foi aceito pela regra antiga ("novo na
tela depois do clique"), e numa conta compartilhada isso deixou passar imagem
alheia - generation_00044 e o caso conhecido. Este modulo responde, build a
build e slot a slot:

  ok          `origem.comprovada` no metadado do slot (forte/media/fraca).
  suspeito    sem prova E o historico diz que o resultado "ficou pronto" rapido
              demais para ter sido gerado (0,1 s no Editor Pro nao e geracao,
              e imagem de outra pessoa que ja estava chegando).
  sem_prova   anterior a prova de origem, sem sinal de alarme. Nao da para
              afirmar nada: quem decide e quem olha a imagem.
  quarentena  o artefato foi tirado da build (identity/quarentena/).

Quarentenar NUNCA apaga: move o arquivo (e a copia de upload) para
identity/quarentena/, anota o motivo, e reenfileira o slot para gerar de
novo - agora com prova.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import artefato, config, history, queue, slots

OK, SEM_PROVA, SUSPEITO, QUARENTENA = "ok", "sem_prova", "suspeito", "quarentena"

# Prova que nenhum site da: alguem abriu a imagem e conferiu. Fica registrada
# como origem `manual` para a auditoria parar de acusar o slot.
METODO_MANUAL, FORCA_MANUAL = "verificacao_humana", "manual"

# Abaixo disto o provedor nao gerou nada: so mostrou algo que ja existia.
# Picasso: a geracao mais rapida medida foi ~4,6 s (chip do card); o Editor
# Pro leva 11-14 s. Digen: nunca abaixo de dezenas de segundos.
SUSPEITA_ESPERA_S = {slots.PICASSO: 6.0, slots.DIGEN: 20.0}


def _prompt_gravado(generation_id: str, slot: str) -> str | None:
    arquivo = config.identity_dir(generation_id) / f"{slot}.prompt.txt"
    if arquivo.is_file():
        try:
            texto = arquivo.read_text(encoding="utf-8-sig").strip()
            if texto:
                return texto
        except OSError:
            pass
    meta = artefato.metadados(generation_id, slot) or {}
    return meta.get("prompt") or None


def classificar(generation_id: str | None = None) -> list[dict]:
    """Uma linha por (build, slot) que tem artefato - ou teve, se quarentenado."""
    esperas = history.ultima_espera_por_slot()
    linhas = []
    for out_dir in sorted(config.OUTPUTS.glob("generation_*")):
        gid = out_dir.name
        if generation_id and gid != generation_id:
            continue
        for slot in slots.JOBS:
            caminho = artefato.caminho(gid, slot)
            meta = artefato.metadados(gid, slot) or {}
            linha = {"generation_id": gid, "slot": slot,
                     "arquivo": caminho.name, "forca": None, "detalhe": ""}
            if not caminho.is_file():
                if meta.get("quarentena"):
                    linha.update(
                        estado=QUARENTENA,
                        detalhe=str(meta["quarentena"].get("motivo", ""))[:80])
                    linhas.append(linha)
                continue
            origem = meta.get("origem") or {}
            if origem.get("comprovada"):
                linha.update(estado=OK, forca=origem.get("forca"),
                             detalhe=f"{origem.get('metodo')} ({origem.get('forca')})")
                linhas.append(linha)
                continue
            espera = esperas.get((gid, slot))
            limiar = SUSPEITA_ESPERA_S.get(slots.provedor(slot), 0.0)
            if origem and origem.get("motivo"):
                linha.update(estado=SEM_PROVA,
                             detalhe=f"origem nao comprovada: {origem['motivo']}"[:80])
            elif espera is not None and espera < limiar:
                linha.update(
                    estado=SUSPEITO,
                    detalhe=f"'pronto' em {espera:.1f}s (< {limiar:.0f}s): nao "
                            "houve geracao, so algo que ja estava la")
            else:
                sufixo = f" ('pronto' em {espera:.0f}s)" if espera is not None else ""
                linha.update(estado=SEM_PROVA,
                             detalhe="anterior a prova de origem" + sufixo)
            linhas.append(linha)
    return linhas


def resumo(linhas: list[dict]) -> dict:
    contagem = {OK: 0, SEM_PROVA: 0, SUSPEITO: 0, QUARENTENA: 0}
    for linha in linhas:
        contagem[linha["estado"]] = contagem.get(linha["estado"], 0) + 1
    return contagem


def imprimir(linhas: list[dict]) -> int:
    """Relatorio. Devolve quantos artefatos estao SUSPEITOS."""
    print("\nORIGEM DOS ARTEFATOS (as contas do PicassoIA e do Digen sao compartilhadas)")
    print("-" * 78)
    if not linhas:
        print("  nenhum artefato de identidade no disco")
    marca = {OK: "ok ", SEM_PROVA: "?  ", SUSPEITO: "!! ", QUARENTENA: "q  "}
    for linha in linhas:
        print(f"  {marca[linha['estado']]}{linha['generation_id']:<18} "
              f"{linha['slot']:<21} {linha['detalhe']}")
    contagem = resumo(linhas)
    print(f"\n  comprovados: {contagem[OK]} | sem prova (anteriores): "
          f"{contagem[SEM_PROVA]} | SUSPEITOS: {contagem[SUSPEITO]} | "
          f"em quarentena: {contagem[QUARENTENA]}")
    if contagem[SUSPEITO]:
        print("  !! suspeito = o site 'ficou pronto' rapido demais para ter gerado. "
              "Abra a imagem; se for alheia:")
        print("     python main.py identity quarentenar <geracao> <slot>   "
              "(ou: identity auditar --quarentenar-suspeitos)")
    if contagem[SEM_PROVA]:
        print("  ?  sem prova = anterior ao portao de origem; nada acusa, mas "
              "nada prova. Confira as imagens das builds que voce vai publicar.")
    return contagem[SUSPEITO]


def quarentenar(generation_id: str, slot: str, motivo: str,
                reenfileirar: bool = True, rerender: bool = True,
                preview: bool = False) -> list[Path]:
    """Tira o artefato da build e (opcionalmente) manda gerar de novo."""
    slot = slots.valido(slot)
    movidos = artefato.quarentenar(generation_id, slot, motivo)
    if not movidos:
        print(f"[auditoria] {generation_id}/{slot}: nao ha artefato para quarentenar.")
        return []
    for caminho in movidos:
        print(f"[auditoria] {generation_id}/{slot}: -> {caminho}")
    history.registrar(generation_id, history.QUARENTENA, slot=slot,
                      motivo=str(motivo)[:200],
                      arquivos=[p.name for p in movidos])

    if slot == slots.REFERENCIA and artefato.utilizavel(generation_id,
                                                        slots.CHARACTER_WEAPON):
        print(f"[auditoria] atencao: o payoff de {generation_id} foi gerado com "
              "esta referencia anexada. Para refaze-lo (gasta credito do Digen):")
        print(f"           python main.py identity quarentenar {generation_id} "
              f"{slots.CHARACTER_WEAPON}")

    if reenfileirar:
        prompt = _prompt_gravado(generation_id, slot)
        if prompt:
            queue.enqueue(generation_id, prompt, slot=slot)
            print(f"[auditoria] {generation_id}/{slot} reenfileirado; o proximo "
                  "`identity worker` gera de novo, com prova de origem.")
        else:
            print(f"[auditoria] {generation_id}/{slot}: sem prompt gravado para "
                  f"reenfileirar; rode `identity run {generation_id} --slot {slot}`.")

    if rerender and slot in slots.SLOTS:
        # Esse slot aparece no video: sem re-render o mp4 final continua
        # mostrando a imagem que acabou de sair da build.
        from .worker import _rerender
        _rerender(generation_id, preview=preview)
    return movidos


def aprovar(generation_id: str, slot: str, motivo: str) -> bool:
    """Registra que um humano conferiu o artefato e ele e nosso.

    E o par de `quarentenar`: a auditoria aponta o suspeito, alguem abre a
    imagem, e o veredito vai para o metadado — senao o mesmo slot acusaria
    para sempre. Nao se aprova o que nao esta no disco.
    """
    slot = slots.valido(slot)
    if not artefato.utilizavel(generation_id, slot):
        print(f"[auditoria] {generation_id}/{slot}: nao ha artefato para aprovar.")
        return False
    meta = artefato.metadados(generation_id, slot) or {
        "generation_id": generation_id, "slot": slot}
    meta["origem"] = {
        "comprovada": True,
        "forca": FORCA_MANUAL,
        "metodo": METODO_MANUAL,
        "provedor": slots.provedor(slot),
        "alvo": None, "url": None, "candidato": None,
        "candidato_descartado": False,
        "prompt_sha256": None,
        "enviado_em": None,
        "verificado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "card": None,
        "motivo": str(motivo),
    }
    meta.pop("quarentena", None)
    pasta = config.identity_dir(generation_id)
    pasta.mkdir(parents=True, exist_ok=True)
    with open(pasta / f"{slot}.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    history.registrar(generation_id, history.APROVADO, slot=slot,
                      motivo=str(motivo)[:200])
    print(f"[auditoria] {generation_id}/{slot}: aprovado ({motivo}).")
    return True
