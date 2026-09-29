# -*- coding: utf-8 -*-
"""(e) CONFIABILIDADE: o que foi afirmado hoje, e o que da para provar.

Por que existe (16/09/2026): entre 10 e 15/09, 29 videos entraram no ledger
como publicados e estavam como RASCUNHO no canal. Nenhum painel pegou,
porque todos liam o mesmo ledger que estava errado — o ledger conferido
contra si mesmo. Esta familia separa as duas coisas: o que o sistema
AFIRMOU e o que ele consegue PROVAR.

UMA FONTE, DOIS LEITORES. O resumo do Telegram (`/confiabilidade`) e a
pagina do painel leem ESTE dicionario e nao calculam nada. Se os dois
mostrarem numeros diferentes para o mesmo dia, o defeito e aqui — e e so
aqui que se conserta.

As regras da casa valem inteiras: SO LE (nenhum subprocesso, nenhuma rede,
nenhum ffprobe — o pulso do painel e de 3 s) e NAO LEVANTA.

Estado ganha de evento. "O TikTok falhou 3 vezes hoje" e ruido; "12 videos
estao num destino so" e sintoma — se esse numero parar de cair, alguma
coisa quebrou. Por isso as duas coisas aparecem, mas so o estado dispara
alerta sozinho.

Nao ha NOTA de 0 a 100 de proposito: uma nota exigiria inventar pesos, e
um "86" nao diz o que olhar. O que sai e a lista de alertas, cada um com o
seu motivo.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from .auditoria import _publicado

# Quantos dias para tras contam para o ESTADO "num destino so". Curto o
# bastante para o acervo de antes do TikTok entrar na grade nao inflar o
# numero; longo o bastante para a fila de atrasados aparecer inteira.
JANELA_DESTINO_DIAS = 7
# Conferencia mais velha que isto e conferencia que parou de rodar. Ficou
# para quem ja lia o numero; a regra agora e a da NOITE (`sinais`): a de
# 21/09/2026 faltou e, com a regra dos dois dias, ninguem teria sabido.
CONFERENCIA_VELHA_DIAS = 2
FORA_DE_HD = ("processando", "subindo", "sd")
# Metrica que nao se renova ha mais que isto parou de ser coletada. A coleta
# e uma por noite: uma noite e um dia de folga, e nada mais.
METRICA_VELHA_H = 30
ROTULO_DA_PARTE = {"builds": "do YouTube de builds",
                   "historias": "do YouTube de historias",
                   "builds_tiktok": "do TikTok de builds",
                   "historias_tiktok": "do TikTok de historias"}


def _ledger(modulo_nome: str) -> list:
    try:
        if modulo_nome == "builds":
            from builds.publicar import metricas
            return list(metricas.publicados() or [])
        from contos.publicar import serie
        return list(serie.publicados() or [])
    except Exception:
        return []


def _diario() -> list | None:
    """O diario INTEIRO. `None` = nao consegui ler (e nao "nada aconteceu").

    Era `atividade.recentes(4000)`, que so le as ultimas 1200 linhas: num dia
    de historias (1103 eventos em 27/09) a janela de 24 h saia cortada.
    """
    try:
        from builds.publicar import sinais
        eventos = sinais.ler_diario()
    except Exception:
        return None
    # Do mais novo para o mais velho, como `recentes()` entregava: a pagina
    # e o relatorio mostram as primeiras aberturas da valvula da lista.
    return None if eventos is None else list(reversed(eventos))


def _marca_das_metricas() -> dict | None:
    try:
        from builds.publicar import metricas
        return metricas.ler_marca()
    except Exception:
        return None


def _conferencias() -> dict:
    saida = {}
    for canal in ("builds", "historias"):
        try:
            from builds.publicar import conferencia
            saida[canal] = conferencia.ultima(canal) or {}
        except Exception:
            saida[canal] = {}
    return saida


def _dia_local(ts) -> str:
    """O dia LOCAL de um carimbo. O ledger grava local; o diario, UTC."""
    try:
        quando = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return ""
    if quando.tzinfo is not None:
        quando = quando.astimezone()
    return quando.date().isoformat()


def _laudo(linha: dict) -> dict:
    prova = linha.get("prova")
    if isinstance(prova, list):
        return prova[0] if prova and isinstance(prova[0], dict) else {}
    return prova if isinstance(prova, dict) else {}


def _publicacoes(linhas_por_canal: dict, dia: str) -> list:
    saida = []
    for canal, linhas in linhas_por_canal.items():
        for linha in linhas:
            if not isinstance(linha, dict) or not _publicado(linha):
                continue
            if _dia_local(linha.get("quando")) != dia:
                continue
            laudo = _laudo(linha)
            saida.append({
                "canal": canal,
                "plataforma": linha.get("plataforma") or "youtube",
                "hora": str(linha.get("quando") or "")[11:16],
                "video_id": linha.get("video_id"),
                "titulo": linha.get("titulo"),
                # `in linha` e nao `.get`: ausente e o TERCEIRO estado ("nao
                # sei"), e precisa continuar distinguivel de `None` gravado.
                "tem_laudo": "prova_ok" in linha,
                "prova_ok": linha.get("prova_ok"),
                "qualidade": laudo.get("qualidade_no_clique") or "",
                "reconhecido": laudo.get("reconhecido"),
            })
    return sorted(saida, key=lambda p: (p["hora"], p["canal"], p["plataforma"]))


def _num_destino_so(linhas_por_canal: dict, hoje: date) -> dict:
    """ESTADO: videos que foram a uma plataforma e nao a outra."""
    desde = hoje - timedelta(days=JANELA_DESTINO_DIAS)
    saida = {}
    for canal, linhas in linhas_por_canal.items():
        onde: dict = {}
        for linha in linhas:
            if not isinstance(linha, dict) or not _publicado(linha):
                continue
            dia = _dia_local(linha.get("quando"))
            if not dia or dia < desde.isoformat():
                continue
            onde.setdefault(linha.get("video_id"), set()).add(
                linha.get("plataforma") or "youtube")
        saida[canal] = sorted(
            vid for vid, plataformas in onde.items()
            if vid and len(plataformas) == 1)
    return saida


# A etapa que cada publicador grava no diario. E o criterio CERTO: ela diz
# de onde veio a falha, independente do texto da excecao.
ETAPA_POR_DESTINO = {"publicar.tiktok": "tiktok",
                     "publicar.youtube": "youtube"}
# Os erros que so o publicador do YouTube levanta. Casar por "youtube" solto
# contaria tambem a conferencia, que grava `fabrica="publicacao"` com
# "conferencia builds/youtube: ..." no detalhe — e isso nao e falha de
# publicar.
ERROS_DO_YOUTUBE = ("YouTubeWebFalhou", "LimiteDiarioDoYouTube")


def _destino_da_falha(ev: dict) -> str:
    """De que publicador veio esta falha? `""` se nao e falha de publicar.

    Evento COM etapa e julgado so pela etapa. Evento SEM etapa cai no
    criterio antigo, e isso e transicao, nao descuido: ate o publicador
    passar a gravar a etapa, zerar a contagem esconderia justamente as
    falhas que se quer ver. O antigo do TikTok e o de 16/09/2026 ("tiktok"
    no texto, que pega o nome da classe `TikTokFalhou`); o do YouTube casa so
    o nome das classes dele.
    """
    if ev.get("fabrica") != "publicacao" or ev.get("status") != "erro":
        return ""
    etapa = str(ev.get("etapa") or "")
    if etapa:
        return ETAPA_POR_DESTINO.get(etapa, "")
    detalhe = str(ev.get("detalhe") or "")
    if "tiktok" in detalhe.lower():
        return "tiktok"
    if detalhe.startswith(ERROS_DO_YOUTUBE):
        return "youtube"
    return ""


# A forma de um id de video DE VERDADE. Um `ref` fora dela veio de dublê de
# teste: em 16/09/2026 dois testes escreveram no diario de producao falhas
# de "trava:build:celular", e elas contavam como falhas reais do TikTok.
# Canal novo com outro formato de id (o zombie, por exemplo) precisa entrar
# aqui — ha teste que lista os formatos aceitos.
ID_DE_VIDEO = re.compile(r"^(?:generation|historia|duelo|tournament)_\d+")


def _ref_de_teste(ev: dict) -> bool:
    """O evento aponta para um video que nao pode existir?

    Evento SEM ref nao e julgado: a maioria do diario antigo e assim, e
    descartar tudo o que nao tem ref apagaria falhas verdadeiras.
    """
    ref = str(ev.get("ref") or "")
    return bool(ref) and not ID_DE_VIDEO.match(ref)


def _do_diario(eventos: list, dia: str) -> tuple:
    valvula, ignoradas = [], []
    falhas = {"tiktok": 0, "youtube": 0}
    for ev in eventos:
        if not isinstance(ev, dict) or _dia_local(ev.get("ts")) != dia:
            continue
        if ev.get("etapa") == "valvula":
            alvo, _, marca = str(ev.get("ref") or "").partition("|")
            valvula.append({"canal": ev.get("canal"), "alvo": alvo,
                            "marca": marca, "motivo": ev.get("detalhe"),
                            "hora": _hora_local(ev.get("ts"))})
            continue
        destino = _destino_da_falha(ev)
        if not destino:
            continue
        if _ref_de_teste(ev):
            # Fica na ficha, e nao some: quem le precisa saber que houve
            # linha descartada, e por que.
            ignoradas.append({"hora": _hora_local(ev.get("ts")),
                              "destino": destino, "ref": ev.get("ref"),
                              "pid": ev.get("pid"),
                              "motivo": "ref nao e id de video (dublê de teste)"})
            continue
        falhas[destino] += 1
    return valvula, falhas, ignoradas


def _hora_local(ts) -> str:
    try:
        quando = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return ""
    if quando.tzinfo is not None:
        quando = quando.astimezone()
    return quando.strftime("%H:%M")


def _resumo_conferencia(ficha: dict, hoje: date) -> dict:
    if not ficha:
        return {"estado": "nunca rodou"}
    if ficha.get("erro"):
        return {"estado": "falhou", "erro": ficha["erro"]}
    dia = str(ficha.get("dia") or "")
    try:
        idade = (hoje - date.fromisoformat(dia)).days
    except ValueError:
        idade = None
    return {
        "estado": ficha.get("veredito") or "?",
        "dia": dia, "idade_dias": idade,
        "casados": ficha.get("casados", 0),
        "no_ledger": ficha.get("no_ledger", 0),
        "fantasmas": len(ficha.get("fantasmas") or []),
        "rascunhos": len(ficha.get("rascunhos") or []),
        "privados_fora": len(ficha.get("orfaos_privados") or []),
        "orfaos": len(ficha.get("orfaos") or []),
        "so_sd": len(ficha.get("so_sd") or []),
        # A GRADE, e nao so o veredito. Ate 28/09/2026 esta pagina mostrava
        # "✓ 5/5" para um canal com 5 de 10 horarios cumpridos: ledger
        # coerente e grade cumprida sao perguntas diferentes. `None` = ficha
        # de antes de 27/09, que nao sabia a grade.
        "grade": ficha.get("grade"),
        "dia_de_grade": ficha.get("dia_de_grade"),
        "horarios_cumpridos": ficha.get("horarios_cumpridos"),
        "slots_da_grade": ficha.get("slots_da_grade"),
        "horarios_em_falta": list(ficha.get("horarios_em_falta") or []),
        # A LISTA DO CANAL (28/09/2026): `None` e ficha de antes, ou lista
        # que nao veio do canal. Incompleta = o veredito do ledger parou.
        "lista": ficha.get("lista"),
    }


def _metricas(marca, agora: datetime) -> dict:
    """`{parte: {estado, ultimo_ok, idade_h, velha, erro}}` da marca do dia.

    `None` na entrada e "nao consegui ler a marca": fica `{"_ilegivel": ...}`
    e vira alerta, em vez de sumir.
    """
    if marca is None:
        return {"_ilegivel": True}
    try:
        from builds.publicar import metricas
        partes = metricas.partes_da_marca(marca)
        nomes = [metricas.nome_da_parte(c, p) for c, p in metricas.partes()]
    except Exception:
        partes, nomes = {}, list(ROTULO_DA_PARTE)
    saida = {}
    for nome in nomes:
        ficha = partes.get(nome) if isinstance(partes.get(nome), dict) else {}
        ultimo = str(ficha.get("ultimo_ok") or "")
        try:
            idade = (agora - datetime.fromisoformat(ultimo)).total_seconds() \
                / 3600 if ultimo else None
        except ValueError:
            idade = None
        saida[nome] = {
            "estado": ficha.get("estado"),
            "ultimo_ok": ultimo or None,
            "idade_h": None if idade is None else round(idade, 1),
            # NUNCA TEVE COLETA BOA tambem e velha: ausencia nao e frescor.
            "velha": idade is None or idade > METRICA_VELHA_H,
            "erro": ficha.get("erro"),
            "videos": ficha.get("videos_no_ultimo_ok"),
            "lista": ficha.get("lista"),
            "casados": ficha.get("casados"),
            "envios": ficha.get("envios"),
        }
    return saida


def _sinais(linhas: dict, eventos, conferencias: dict,
            agora: datetime) -> dict:
    """Os tres sinais de ausencia, pelas mesmas contas da conferencia."""
    try:
        from builds.publicar import sinais
    except Exception:
        return {}
    contagem = (sinais.eventos_por_canal(eventos, agora, canais=tuple(linhas))
                if eventos is not None else None)
    saida = {}
    for canal, do_canal in linhas.items():
        ficha = (conferencias or {}).get(canal)
        saida[canal] = {
            "noite": sinais.noites_sem_conferencia(
                ficha if isinstance(ficha, dict) else {}, agora),
            "eventos_24h": None if contagem is None else contagem.get(canal),
            "cobertura_ids": sinais.cobertura_de_ids(do_canal, agora),
        }
    return saida


def _alertas(ficha: dict) -> list:
    alertas = []
    if ficha["sem_prova"]:
        alertas.append(f"{ficha['sem_prova']} publicação(ões) sem prova hoje")
    if ficha["fora_de_hd"]:
        alertas.append(f"{ficha['fora_de_hd']} no YouTube foram ao ar antes "
                       "de terminar o processamento")
    if ficha["barra_nao_entendida"]:
        # O ALARME PROMETIDO na Etapa 1: se a leitura da barra do Studio
        # para de reconhecer o texto, a medida inteira vira palpite.
        alertas.append(f"{ficha['barra_nao_entendida']} leitura(s) da barra "
                       "do Studio não reconhecida(s) — o texto pode ter mudado")
    if ficha["valvula"]:
        alertas.append(f"a válvula abriu {len(ficha['valvula'])} vez(es)")
    for canal, ids in ficha["num_destino_so"].items():
        if ids:
            alertas.append(f"{len(ids)} vídeo(s) de {canal} em um destino só "
                           f"(últimos {JANELA_DESTINO_DIAS} dias)")
    for canal, conf in ficha["conferencia"].items():
        estado = conf.get("estado")
        if estado == "sujo":
            partes = [f"{conf.get(chave, 0)} {nome}"
                      for chave, nome in (("fantasmas", "fantasma(s)"),
                                          ("rascunhos", "rascunho(s)"),
                                          ("privados_fora",
                                           "privado(s) fora do ledger"))
                      if conf.get(chave)]
            alertas.append(f"conferência de {canal}: "
                           + (", ".join(partes) or "suja"))
        elif estado == "falhou":
            alertas.append(f"conferência de {canal} não rodou: "
                           f"{str(conf.get('erro'))[:80]}")
        elif estado == "nunca rodou":
            alertas.append(f"conferência de {canal} nunca rodou")
        lista = conf.get("lista") or {}
        if lista and not lista.get("completa"):
            # LISTA CURTA NAO E "LIMPO". A conferencia que nao viu o canal
            # inteiro nao da veredito do ledger, e isso tem de aparecer.
            declarados = lista.get("declarados")
            alertas.append(
                f"conferência de {canal} sem veredito do ledger: "
                + (f"a lista do canal trouxe {lista.get('publicos', '?')} "
                   f"públicos e o canal declara {declarados}"
                   if isinstance(declarados, int) and declarados >= 0 else
                   "o canal não disse quantos vídeos públicos tem"))
        if conf.get("grade") == "em falta":
            # A GRADE FURADA APARECE AQUI TAMBEM, e nao so no diario: a
            # pagina dizia "✓" para o canal que cumpriu 5 de 10 horarios.
            falta = ", ".join(conf.get("horarios_em_falta") or [])
            alertas.append(
                f"grade de {canal} em falta no dia "
                f"{_dia_curto(conf.get('dia_de_grade'))}: "
                f"{conf.get('horarios_cumpridos', 0)} de "
                f"{conf.get('slots_da_grade', 0)} horários com vídeo público"
                + (f" (faltaram {falta})" if falta else ""))
    for canal, sinal in (ficha.get("sinais") or {}).items():
        noite = sinal.get("noite")
        estado = (ficha["conferencia"].get(canal) or {}).get("estado")
        if noite and estado != "nunca rodou":
            # A NOITE QUE FALTOU. A de 21/09/2026 passou sem conferencia, e
            # a regra antiga (dois dias) nunca teria dito nada.
            esperada = _dia_curto(noite.get("esperada"))
            if not noite.get("ultima"):
                alertas.append(f"conferência de {canal} nunca rodou")
            elif noite["ultima"] < str(noite.get("esperada") or ""):
                alertas.append(
                    f"conferência de {canal} parada desde "
                    f"{_dia_curto(noite.get('ultima'))}: a noite de "
                    f"{esperada} não rodou")
            else:
                alertas.append(
                    f"conferência de {canal}: a noite de {esperada} não rodou "
                    "(só houve conferência feita à mão)")
        eventos = sinal.get("eventos_24h") or {}
        if eventos.get("poucos"):
            alertas.append(
                f"{canal}: {eventos.get('eventos', 0)} evento(s) de trabalho "
                f"em {eventos.get('horas_cobertas', 0):.0f} h no diário, menos "
                f"que os {eventos.get('minimo', 0)} horário(s) da grade — o "
                "canal parou?")
        cobertura = sinal.get("cobertura_ids") or {}
        if cobertura.get("baixa"):
            alertas.append(
                f"{canal}: só {cobertura.get('com_id', 0)} de "
                f"{cobertura.get('linhas', 0)} publicação(ões) recentes do "
                f"YouTube têm youtube_id "
                f"({100 * (cobertura.get('cobertura') or 0):.0f}%) — sem id "
                "não há métrica")
    alertas.extend(_alertas_de_metrica(ficha.get("metricas") or {}))
    return alertas


def _dia_curto(texto) -> str:
    texto = str(texto or "")
    return f"{texto[8:10]}/{texto[5:7]}" if len(texto) >= 10 else "?"


def _alertas_de_metrica(metricas: dict) -> list:
    """Metrica velha acende AQUI, que e o relatorio das 22:30.

    Onze noites sem metrica do YouTube (17 a 28/09/2026) e a pagina lia o
    disco velho sem avisar. Estado, e nao evento: enquanto a ultima coleta
    boa de uma parte for de mais de `METRICA_VELHA_H` horas, o alerta fica.
    """
    if metricas.get("_ilegivel"):
        return ["não consegui ler a marca das métricas (_atualizado_em.json)"]
    alertas = []
    for nome, parte in metricas.items():
        rotulo = ROTULO_DA_PARTE.get(nome, nome)
        if parte.get("estado") == "erro":
            # A marca de antes de 28/09/2026 so guardava o numero: "0" sem
            # o motivo. O motivo novo vem da excecao.
            motivo = (str(parte["erro"])[:70] if parte.get("erro")
                      else "a marca diz 0 vídeos, sem o motivo")
            alertas.append(f"métrica {rotulo}: a coleta desta noite falhou "
                           f"({motivo})")
        elif parte.get("velha"):
            if parte.get("ultimo_ok"):
                alertas.append(
                    f"métrica {rotulo} velha: a última coleta boa é de "
                    f"{_dia_curto(parte['ultimo_ok'])} "
                    f"{str(parte['ultimo_ok'])[11:16]} "
                    f"({parte.get('idade_h', 0):.0f} h)")
            else:
                alertas.append(f"métrica {rotulo}: nenhuma coleta boa "
                               "registrada")
        if parte.get("lista") in ("parada", "tempo"):
            alertas.append(
                f"métrica {rotulo}: a lista do Studio veio incompleta "
                f"({parte.get('casados')} de {parte.get('envios')} envios "
                "casados)")
    return alertas


def hoje(dia: str | None = None, *, builds=None, historias=None,
         eventos=None, conferencias=None, marca=None,
         agora: datetime | None = None) -> dict:
    """O retrato do dia. Tudo injetavel — e assim que se testa sem disco.

    `marca` e a marca do dia das metricas (`{}` = nunca coletou; ausente =
    le do disco). `agora` e o relogio dos sinais; sem ele, o de agora se o
    dia e hoje, e o fim do dia se e um dia passado.
    """
    referencia = date.fromisoformat(dia) if dia else date.today()
    dia = referencia.isoformat()
    if agora is None:
        agora = (datetime.now() if referencia >= date.today()
                 else datetime.combine(referencia, datetime.max.time()))
    linhas = {
        "builds": _ledger("builds") if builds is None else list(builds),
        "historias": (_ledger("historias") if historias is None
                      else list(historias)),
    }
    lidos = _diario() if eventos is None else list(eventos)
    eventos = lidos or []
    conferencias = _conferencias() if conferencias is None else conferencias
    marca = _marca_das_metricas() if marca is None else marca

    publicacoes = _publicacoes(linhas, dia)
    valvula, falhas, ignoradas = _do_diario(eventos, dia)
    ficha = {
        "dia": dia,
        "publicacoes": publicacoes,
        "prometido": len(publicacoes),
        "provado": sum(1 for p in publicacoes if p["prova_ok"] is True),
        "sem_prova": sum(1 for p in publicacoes if p["prova_ok"] is False),
        # Linha anterior a 16/09/2026, ou gravada por caminho sem laudo.
        "sem_campo": sum(1 for p in publicacoes
                         if not p["tem_laudo"] or p["prova_ok"] is None),
        "fora_de_hd": sum(1 for p in publicacoes
                          if p["plataforma"] == "youtube"
                          and p["qualidade"] in FORA_DE_HD),
        "barra_nao_entendida": sum(
            1 for p in publicacoes
            if p["plataforma"] == "youtube" and p["tem_laudo"]
            and p["reconhecido"] is False),
        "num_destino_so": _num_destino_so(linhas, referencia),
        "valvula": valvula,
        # O nome antigo continua: o Telegram e a pagina ja leem este campo.
        "falhas_tiktok": falhas["tiktok"],
        "falhas_youtube": falhas["youtube"],
        "falhas_ignoradas": ignoradas,
        "conferencia": {canal: _resumo_conferencia(f or {}, referencia)
                        for canal, f in (conferencias or {}).items()},
        # O QUE FALTA, e nao so o que aconteceu errado: noite sem
        # conferencia, canal que parou de trabalhar, linha sem id.
        "sinais": _sinais(linhas, lidos, conferencias or {}, agora),
        "metricas": _metricas(marca, agora),
        "quando": datetime.now().isoformat(timespec="seconds"),
    }
    ficha["alertas"] = _alertas(ficha)
    ficha["veredito"] = "atencao" if ficha["alertas"] else "ok"
    return ficha


__all__ = ["CONFERENCIA_VELHA_DIAS", "FORA_DE_HD", "JANELA_DESTINO_DIAS",
           "hoje"]
