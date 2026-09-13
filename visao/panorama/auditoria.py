# -*- coding: utf-8 -*-
"""Os quatro controles, numa resposta so — e a TRAVA antes de publicar.

Pedido dele em 11/09/2026, depois de um dia em que tres coisas diferentes
foram ao ar erradas: "preciso de controle de qualidade, controle de metas,
controle de producao e controle de recursos".

As quatro perguntas, e por que separadas:

    QUALIDADE   o que esta PRESTES a sair pode sair? E a unica que tem poder
                de veto. As outras tres informam; esta impede.
    METAS       o combinado esta sendo cumprido HOJE? Nao "nos ultimos sete
                dias": o dia de hoje ainda da para consertar.
    PRODUCAO    o que esta em pe de fabrica, e ha quanto tempo? E onde se ve
                o travamento, que e sempre silencioso.
    RECURSOS    com o que a maquina esta contando? Disco, conta, credencial,
                trava, freio de mao.

POR QUE ISTO NAO E MAIS UM RELATORIO. O relatorio do Telegram conta o que
ACONTECEU; este modulo responde o que VAI acontecer no proximo horario, e a
parte de qualidade dele e a mesma funcao que o `postar.py` consulta antes de
subir. Ler a auditoria e ver exatamente o que a grade vai ver.

CUSTO. `qualidade()` decodifica cada mp4 pendente com ffprobe — segundos, nao
milissegundos. Por isso ela NAO entra no `resumo()` de 4 s do painel: quem a
chama chama de proposito, e a tela mostra quando foi a ultima vez.
"""
from __future__ import annotations

from datetime import datetime

from . import recursos as _recursos


def _publicados_hoje(agora: datetime | None = None) -> dict:
    """`{canal: {plataforma: [horas]}}` do dia, dos dois ledgers."""
    agora = agora or datetime.now()
    hoje = agora.strftime("%Y-%m-%d")
    saida = {}
    try:
        from builds.publicar import metricas
    except Exception:                                          # noqa: BLE001
        return saida
    for canal in ("historias", "builds"):
        por_plataforma = {}
        try:
            linhas = metricas.publicados(canal)
        except Exception:                                      # noqa: BLE001
            linhas = []
        for linha in linhas:
            quando = str(linha.get("quando") or "")
            if not quando.startswith(hoje) or not linha.get("url"):
                continue
            plataforma = linha.get("plataforma") or "youtube"
            por_plataforma.setdefault(plataforma, []).append(quando[11:16])
        saida[canal] = por_plataforma
    return saida


def metas(agora: datetime | None = None) -> dict:
    """O dia de HOJE contra a grade. So o que ja venceu conta como devido."""
    # TUDO dentro do `try`, e nao so o import. A regra do pacote e que uma
    # familia que falha nao leva as outras junto, e ler dois ledgers de disco
    # tem mais motivo para falhar do que importar um modulo.
    try:
        from builds import grade
        agora = agora or datetime.now()
        vencidos = grade.vencidos(agora)
        feitos = _publicados_hoje(agora)
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}
    canais = {}
    for canal in grade.CANAIS:
        por_plataforma = feitos.get(canal) or {}
        ficha = {}
        for plataforma in grade.PLATAFORMAS:
            saiu = len(por_plataforma.get(plataforma) or [])
            # O devido e o da grade DAQUELA plataforma: desde 13/09/2026 o
            # TikTok pula 7h e 8h, e cobrar dele os oito horarios acusaria
            # dois "faltando" todo dia por uma decisao, nao por uma falha.
            devido = len(grade.vencidos(agora, plataforma))
            ficha[plataforma] = {"saiu": saiu, "devido": devido,
                                 "faltando": max(0, devido - saiu)}
        canais[canal] = ficha
    faltando = sum(p["faltando"] for c in canais.values() for p in c.values())
    return {"horarios_vencidos": len(vencidos),
            "horarios_do_dia": len(grade.HORAS),
            "proximo": grade.proximo(agora),
            "canais": canais, "faltando": faltando,
            "em_dia": faltando == 0}


def qualidade(limite: int = 12) -> dict:
    """Os proximos videos da fila, cada um com o veredito da vistoria.

    A MESMA funcao que o `postar.py` chama antes de subir. Se aqui diz que
    barra, a grade tambem vai barrar — e e esse o ponto: a auditoria nao tem
    opiniao propria, ela mostra a decisao que ja esta tomada.
    """
    try:
        import json
        from pathlib import Path

        from contos.publicar import catalogo
        from contos.publicar import qualidade as vistoria
        from contos.publicar import serie as serie_pub
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}

    try:
        registro = Path(serie_pub.REGISTRO)
        ja = set()
        if registro.is_file():
            for linha in registro.read_text(encoding="utf-8").splitlines():
                try:
                    dado = json.loads(linha)
                except ValueError:
                    continue
                if dado.get("url"):
                    ja.add(dado.get("video_id"))
        pendentes = [v for v in catalogo.listar() if v.id not in ja]
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}

    pendentes.sort(key=lambda v: (v.fonte_id, v.parte))
    fila, barrados = [], 0
    for video in pendentes[:limite]:
        try:
            # `liberado`, e nao `vistoriar_parte`: e a MESMA funcao que o
            # freio de estoque e o publicador consultam. Ate 11/09/2026 esta
            # tela chamava so a vistoria mecanica e ignorava o veto ja
            # lembrado da IA — mostrava "0 barrados" enquanto o freio contava
            # um video reprovado. Duas telas discordando sobre "pode sair?" e
            # o mesmo que nenhuma.
            laudo = vistoria.liberado(video)
        except Exception as erro:                              # noqa: BLE001
            laudo = {"ok": False, "erros": [f"{type(erro).__name__}: {erro}"],
                     "avisos": []}
        if not laudo.get("ok"):
            barrados += 1
        fila.append({"id": video.id, "titulo": video.titulo,
                     "canal": "historias", "ok": bool(laudo.get("ok")),
                     "erros": list(laudo.get("erros") or []),
                     "avisos": list(laudo.get("avisos") or []),
                     "capa": bool(getattr(video, "capa", None))})
    liberados = len(fila) - barrados
    return {"fila": fila, "barrados": barrados, "liberados": liberados,
            "pendentes": len(pendentes),
            # A conta que importa: com quantos horarios ainda da para cumprir
            # a grade se nada mudar.
            "cobre_horarios": liberados}


def producao() -> dict:
    """O que esta em pe de fabrica, e o que travou no meio."""
    saida = {}
    try:
        from contos.pipeline.agenda import incompletas
        saida["historias_incompletas"] = [
            {"id": i.get("historia_id"),
             "partes_sem_texto": i.get("partes_sem_texto") or [],
             "imagens_faltando": i.get("imagens_faltando") or 0,
             "partes_sem_video": len(i.get("partes_sem_video") or [])}
            for i in (incompletas() or [])]
    except Exception as erro:                                  # noqa: BLE001
        saida["historias_incompletas"] = {"erro": str(erro)}
    try:
        from . import inventario
        saida["estoque"] = inventario.estoque()
    except Exception as erro:                                  # noqa: BLE001
        saida["estoque"] = {"erro": str(erro)}
    try:
        from . import saude
        saida["agora"] = saude.agora()
    except Exception as erro:                                  # noqa: BLE001
        saida["agora"] = {"erro": str(erro)}
    return saida


def completa(*, com_rede: bool = False, limite: int = 12) -> dict:
    """Os quatro controles. `com_rede` liga o que custa subprocesso e rede."""
    return {
        "quando": datetime.now().isoformat(timespec="seconds"),
        "qualidade": qualidade(limite=limite),
        "metas": metas(),
        "producao": producao(),
        "recursos": (_recursos.completo() if com_rede
                     else _recursos.situacao()),
    }


def veredito(dados: dict | None = None) -> dict:
    """Uma frase e uma cor. E o que cabe no alto de uma tela e no Telegram."""
    dados = dados or completa()
    problemas = []

    qual = dados.get("qualidade") or {}
    if qual.get("barrados"):
        problemas.append(f"{qual['barrados']} video(s) barrado(s) na vistoria")
    if not qual.get("erro") and qual.get("liberados", 0) == 0:
        problemas.append("nenhum video liberado para o proximo horario")

    alvo = dados.get("metas") or {}
    if alvo.get("faltando"):
        problemas.append(f"{alvo['faltando']} publicacao(oes) faltando hoje")

    for alerta in (dados.get("recursos") or {}).get("alertas") or []:
        problemas.append(alerta)

    if not problemas:
        return {"cor": "ok", "frase": "tudo em dia", "problemas": []}
    grave = any(p.startswith("nenhum video") or "critico" in p
                or "PAUSADA" in p for p in problemas)
    return {"cor": "erro" if grave else "aviso",
            "frase": problemas[0], "problemas": problemas}


__all__ = ["completa", "qualidade", "metas", "producao", "veredito"]
