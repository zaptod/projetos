# -*- coding: utf-8 -*-
"""Os dois relatorios que chegam sozinhos no Telegram.

Pedido do Adrian em 09/09/2026: "um relatorio e de funcionamento, como
metricas tempo e td mais, e o outro de metas — quantos videos postei, em
quais horarios e em quais canais".

SAO DOIS PORQUE RESPONDEM A PERGUNTAS DIFERENTES, e misturar as duas e o que
faz ninguem ler nenhuma:

    METAS          o canal cumpriu o combinado? Um video por canal por dia,
                   publico. E olhar para FORA: o que o mundo viu.
    FUNCIONAMENTO  a maquina esta saudavel? Quanto tempo cada etapa levou,
                   o que falhou, se as tarefas vao mesmo disparar. E olhar
                   para DENTRO: o que pode quebrar amanha.

Metas se le em 5 segundos e quase sempre e "✓". Funcionamento so interessa
quando algo esta estranho — mas ele tem que chegar TODO dia, porque a graca
e comparar com ontem.

TUDO SAI DE FATO GRAVADO, nada de estimativa: os dois `publicados.jsonl`
(quem publicou o que, quando, com que visibilidade), o `atividade.jsonl`
(inicio/ok/erro por fabrica, que emparelhado vira DURACAO) e o proprio
Agendador do Windows. Relatorio que chuta e pior do que relatorio nenhum.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from builds import atividade, grade

RAIZ = Path(__file__).resolve().parents[1]

# UM VIDEO EM CADA HORARIO DA GRADE, e nao um por dia — correcao dele em
# 09/09/2026. A meta do dia so esta batida quando todos os horarios sairam
# (dez desde 15/09, em cada plataforma); contar "pelo menos um" esconderia
# nove disparos perdidos. Fonte unica: `builds.grade`. Antes esta tupla era
# uma copia da de `ferramentas/postar.py`, e nada garantia que as duas
# contassem o mesmo dia.
HORARIOS_DA_GRADE = grade.HORAS
META_DIARIA_POR_CANAL = grade.META_DIARIA_POR_CANAL
CANAIS = {
    "historias": {"emoji": "📖", "rotulo": "histórias"},
    "builds": {"emoji": "⚔️", "rotulo": "builds"},
}
# UM DIA, o mesmo alvo do `ferramentas/postar.py`. Era 14 ate 10/09/2026:
# com a meta de estoque em um dia, alertar a partir de duas semanas seria
# alertar sempre.
PISO_DE_ESTOQUE = 1


# --------------------------------------------------------- o dia de grade
# A META E DO DIA DE GRADE, e nao do dia do calendario (28/09/2026). A grade
# vai das 06:37 ate as 00:37 do dia SEGUINTE, e a recuperacao das 23:37 as
# vezes so sai depois da meia-noite. Contado pelo calendario, o dia perdia o
# horario das 00:37 e a recuperacao, e o seguinte ganhava dois que nao eram
# dele: um dia cheio aparecia como 9 + 1 e nunca batia a meta.
#
# A regra e a da conferencia da madrugada (fc17986), e nao uma copia dela:
# quem decide a que dia de grade um instante pertence e `conferencia.py`, a
# partir de `builds.grade`. Se a grade mudar, os dois mudam juntos. As funcoes
# sao internas de la; o acesso fica todo AQUI, num lugar so.
def _conferencia():
    from builds.publicar import conferencia
    return conferencia


def _instante(quando):
    """O `quando` do ledger (hora local, sem fuso) como datetime, ou None.

    `None` nao vira zero nem palpite: registro sem data legivel nao paga
    horario nenhum, e e assim que ele aparece no placar (em falta).
    """
    try:
        return datetime.fromisoformat(str(quando)[:19])
    except (TypeError, ValueError):
        return None


def _dia_de_grade(instante: datetime, plataforma: str = "youtube") -> tuple:
    """(dia de grade, hora da grade) a que o instante pertence.

    00:10 de 28/09 e o horario das 23:37 de 27/09 (a recuperacao atrasada);
    00:39 e o das 00:37, que fecha o dia de grade de 27/09; 06:40 ja e 28/09.
    """
    conferencia = _conferencia()
    dia, hora = conferencia._horario_da_grade(instante, plataforma)
    return conferencia._dia_de_grade(dia, hora, plataforma), hora


def _janela_da_grade(plataforma: str = "youtube") -> str:
    """"06:37 → 00:37": onde o dia de grade abre e onde fecha."""
    abertura, fechamento = _conferencia()._abertura_e_fechamento(plataforma)
    return f"{grade.horario(abertura)} → {grade.horario(fechamento)}"


def _horarios_servidos(itens: list[dict]) -> dict:
    """`{(canal, plataforma): quantos HORARIOS da grade sairam}`.

    Conta SLOT DISTINTO, nao linha. Duas publicacoes no mesmo horario (a
    normal e a recuperacao que anda junto) sao um horario cumprido, e nao
    dois — a grade promete um video por horario, nao dois.
    """
    slots = {}
    for item in itens:
        if item["slot"] is None or not item["plataforma"]:
            continue
        slots.setdefault((item["canal"], item["plataforma"]),
                         set()).add(item["slot"])
    return {chave: len(vistos) for chave, vistos in slots.items()}


def _bateu_o_dia(servidos: dict) -> bool:
    """O dia so esta completo quando TODO canal cumpriu TODA plataforma."""
    return all(servidos.get((canal, plataforma), 0)
               >= grade.META_DIARIA_POR_PLATAFORMA[plataforma]
               for canal in CANAIS for plataforma in grade.PLATAFORMAS)


def _publicacoes() -> list[dict]:
    """Toda publicacao dos dois canais, com canal e hora local resolvidos.

    Os dois ledgers tem formatos proprios (um sabe `origem`/`perfil`, o outro
    sabe `parte`/`partes`), e nenhum guarda o canal — cada um E um canal. Aqui
    eles viram uma lista so, que e o que a pergunta "quantos videos postei"
    precisa.
    """
    saida = []
    for canal, carregar in (("historias", _historias), ("builds", _builds)):
        for linha in carregar():
            quando = str(linha.get("quando") or "")
            if not quando:
                continue
            # A PLATAFORMA E O QUE FALTAVA AQUI, e a falta dava meta batida
            # que nao foi: o placar somava YouTube e TikTok e comparava com o
            # alvo de UMA plataforma. Em 27/09/2026 ele imprimiu "✓ histórias:
            # 11/10 horários" com 5 no YouTube e 6 no TikTok — os dois
            # destinos em falta, e um tique verde.
            plataforma = str(linha.get("plataforma") or "").lower()
            instante = _instante(quando)
            # O HORARIO DA GRADE a que a publicacao pertence, e nao a hora do
            # relogio: a rodada das 17:57 termina as 18:01, e a tarefa
            # recuperada as 19:30 ainda e aquele disparo. Contar por slot
            # tambem impede que dois videos no mesmo horario (a recuperacao e
            # um extra) paguem dois horarios. Linha sem plataforma entra no
            # dia pela regra do YouTube, mas nao paga horario.
            dia, slot = ((None, None) if instante is None
                         else _dia_de_grade(instante, plataforma or "youtube"))
            saida.append({
                "canal": canal,
                "quando": quando,
                "instante": instante,
                # O DIA DE GRADE. Sem data legivel, o do calendario — para a
                # linha ainda aparecer (como "sem data legivel"), e nao sumir.
                "dia": dia.isoformat() if dia else quando[:10],
                "hora": quando[11:16],
                "plataforma": plataforma,
                "slot": slot,
                "video_id": linha.get("video_id"),
                "titulo": linha.get("titulo") or "",
                # `None` aqui e uma linha antiga, de antes de o registro
                # guardar visibilidade. Nao vira "public" por otimismo.
                "visibilidade": linha.get("visibilidade"),
            })
    saida.sort(key=lambda d: d["quando"])
    return saida


def _historias() -> list[dict]:
    try:
        from contos.publicar import serie
        return serie.publicados()
    except Exception:                                          # noqa: BLE001
        return []


def _builds() -> list[dict]:
    try:
        from builds.publicar import metricas
        return metricas.publicados()
    except Exception:                                          # noqa: BLE001
        return []


def _estoque() -> dict:
    """Quantos dias de video pronto cada canal tem. `{}` se nao der para ver."""
    try:
        import importlib.util
        caminho = RAIZ / "ferramentas" / "postar.py"
        spec = importlib.util.spec_from_file_location("postar_rel", caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo.estoque() or {}
    except Exception:                                          # noqa: BLE001
        return {}


# ------------------------------------------------------------------ metas
def metas(agora: datetime | None = None, *, dias: int = 7) -> str:
    """Quantos videos, em que horario, em que canal. E se bateu a meta.

    "Hoje" e o DIA DE GRADE em curso (06:37 ate 00:37 do dia seguinte), e a
    serie conta dias de grade. Pedido a meia-noite e meia, "hoje" ainda e o
    dia de grade que esta fechando — e e ele que a recuperacao das 23:37 paga.
    """
    agora = agora or datetime.now()
    hoje, _ = _dia_de_grade(agora)
    # O dia de grade que ainda nao fechou fica "em andamento" na serie, e nao
    # reprovado: as 21h ainda faltam tres horarios, e um ✗ ali e mentira.
    fechado = _conferencia().dia_de_grade_fechado(agora)
    # So o que ja existia em `agora`: o relatorio de uma hora passada nao
    # conta o que saiu depois dela.
    tudo = [i for i in _publicacoes()
            if i["instante"] is None or i["instante"] <= agora]
    por_dia = {}
    for item in tudo:
        por_dia.setdefault(item["dia"], []).append(item)

    linhas = [f"🎯 *Metas* — {hoje:%d/%m} (dia de grade, "
              f"{_janela_da_grade()})", ""]

    # --- hoje, com hora e canal, que e literalmente o que ele pediu
    de_hoje = por_dia.get(hoje.isoformat()) or []
    if de_hoje:
        linhas.append("*Hoje*")
        for item in de_hoje:
            ficha = CANAIS.get(item["canal"], {})
            visto = item["visibilidade"]
            marca = {"public": "público", "private": "PRIVADO",
                     "unlisted": "não listado"}.get(visto, visto or "?")
            # A hora do relogio e a do horario que ela pagou so aparecem as
            # duas quando diferem: a recuperacao das 00:10 pagou o das 23:37.
            pagou = ""
            if item["slot"] is not None and item["hora"][:2] != f"{item['slot']:02d}":
                pagou = f" · horário das {grade.horario(item['slot'])}"
            linhas.append(f"  {ficha.get('emoji', '•')} {item['hora']}  "
                          f"{ficha.get('rotulo', item['canal'])} · {marca}{pagou}")
    else:
        linhas.append("*Hoje* — nada publicado ainda")

    # A meta e por HORARIO E POR PLATAFORMA, entao o placar tem de ser as
    # duas coisas. Contar linha e somar os destinos foi o defeito de
    # 27/09/2026: "✓ histórias: 11/10 horários" com 5 no YouTube e 6 no
    # TikTok — 11 linhas contra o alvo de uma plataforma so, tique verde num
    # dia em que os dois destinos ficaram em falta. Quem ja contava certo era
    # a conferencia da madrugada (`conferencia.conferir`: `horarios_cumpridos`
    # e `deficit` do dia de grade que fechou, fc17986); agora aqui tambem, e
    # pela mesma regra do dia de grade.
    linhas.append("")
    servidos_hoje = _horarios_servidos(de_hoje)
    for canal, ficha in CANAIS.items():
        placar = []
        completo = True
        for plataforma in grade.PLATAFORMAS:
            saiu = servidos_hoje.get((canal, plataforma), 0)
            alvo = grade.META_DIARIA_POR_PLATAFORMA[plataforma]
            completo = completo and saiu >= alvo
            placar.append(f"{plataforma} {saiu}/{alvo}")
        marca = "✓" if completo else "⏳"
        linhas.append(f"  {marca} {ficha['emoji']} {ficha['rotulo']}: "
                      + " · ".join(placar))

    # LINHA QUE NAO PAGA HORARIO TEM DE APARECER. Sem plataforma ou sem data
    # legivel, o registro fica fora do placar — e um placar menor sem explicar
    # por que e exatamente o tipo de silencio que fez este relatorio mentir.
    mudas = [i for i in de_hoje if not i["plataforma"] or i["slot"] is None]
    if mudas:
        linhas.append(f"  ⚠ {len(mudas)} registro(s) sem plataforma ou sem "
                      f"data legível: não pagam horário")

    # --- a serie, que e onde se ve se e habito ou sorte
    linhas += ["", f"*Últimos {dias} dias de grade*"]
    completos = 0
    for recuo in range(dias - 1, -1, -1):
        dia = hoje - timedelta(days=recuo)
        itens = por_dia.get(dia.isoformat()) or []
        servidos = _horarios_servidos(itens)
        bateu = _bateu_o_dia(servidos)
        completos += 1 if bateu else 0
        # Um numero por canal, mas com o DENOMINADOR CHEIO (os horarios das
        # duas plataformas somados) — senao "11" ao lado de uma meta de 10
        # continua parecendo dia completo.
        alvo_do_canal = sum(grade.META_DIARIA_POR_PLATAFORMA[p]
                            for p in grade.PLATAFORMAS)
        corpo = " ".join(
            f"{CANAIS[c]['emoji']}"
            f"{sum(servidos.get((c, p), 0) for p in grade.PLATAFORMAS)}"
            f"/{alvo_do_canal}" for c in CANAIS)
        marca = "✓" if bateu else ("⏳" if dia > fechado else "✗")
        linhas.append(f"  {dia:%d/%m}  {corpo}  {marca}")
    desde = (hoje - timedelta(days=dias - 1)).isoformat()
    total = {c: sum(1 for i in tudo if i["canal"] == c and i["dia"] >= desde)
             for c in CANAIS}
    linhas.append("  " + " · ".join(
        f"{CANAIS[c]['rotulo']}: {total[c]}" for c in CANAIS))
    linhas.append(f"  dias completos: {completos}/{dias}")

    # --- privado e uma meta furada com cara de meta batida
    privados = [i for i in tudo
                if i["visibilidade"] and i["visibilidade"] != "public"]
    if privados:
        mostrar = privados[-3:]
        linhas += ["", f"⚠ {len(privados)} vídeo(s) NÃO público(s):"]
        for item in mostrar:
            # A data em que ELE saiu (calendario), e nao o dia de grade.
            linhas.append(f"  {item['quando'][8:10]}/{item['quando'][5:7]} "
                          f"{item['video_id']} ({item['visibilidade']})")
        if len(privados) > len(mostrar):
            linhas.append(f"  … e mais {len(privados) - len(mostrar)}")

    # --- estoque: a meta de amanha se decide hoje
    dias_de_estoque = _estoque()
    if dias_de_estoque:
        linhas += ["", "*Estoque*"]
        for canal, ficha in CANAIS.items():
            valor = dias_de_estoque.get(canal)
            if valor is None:
                continue
            alerta = " ⚠ abaixo do piso" if valor < PISO_DE_ESTOQUE else ""
            linhas.append(f"  {ficha['emoji']} {ficha['rotulo']}: "
                          f"{valor} dia(s){alerta}")
    return "\n".join(linhas)


# ---------------------------------------------------------- funcionamento
def _duracoes(eventos: list[dict]) -> dict:
    """Emparelha `inicio` com o `ok`/`erro` do MESMO pid e mede o tempo.

    O pid e o que torna isso confiavel: duas fabricas rodando ao mesmo tempo
    (ou dois disparos da mesma) intercalam eventos no diario, e casar por
    ordem de chegada mediria o intervalo errado.
    """
    def _ordem(evento):
        # O FIM VEM ANTES DO COMECO quando o segundo e o mesmo. O diario grava
        # com resolucao de segundo e o Estudio comeca a proxima parte no
        # mesmo segundo em que fecha a anterior:
        #
        #     ok     12:32:26   (parte 2 terminou)
        #     inicio 12:32:26   (parte 3 comecou)
        #
        # Ordenando so por `ts`, o `inicio` podia ser processado primeiro,
        # sobrescrever o comeco que estava aberto e casar com o `ok` do mesmo
        # segundo — medindo ZERO. Era a "mediana 0s" do Estudio, que na
        # verdade leva ~7 min por parte.
        terminal = evento.get("status") in (atividade.OK, atividade.ERRO)
        return (str(evento.get("ts") or ""), 0 if terminal else 1)

    abertos, medidas = {}, {}
    for evento in sorted(eventos, key=_ordem):
        fabrica = evento.get("fabrica")
        chave = (fabrica, evento.get("pid"))
        situacao = evento.get("status")
        quando = _hora(evento.get("ts"))
        if quando is None:
            continue
        if situacao == atividade.TRABALHANDO:
            # Um `inicio` sem fim (processo derrubado) nao pode apagar o
            # comeco anterior: fica o mais ANTIGO, que e o que ainda espera
            # resposta.
            abertos.setdefault(chave, quando)
        elif situacao in (atividade.OK, atividade.ERRO):
            inicio = abertos.pop(chave, None)
            if inicio is not None:
                medidas.setdefault(fabrica, []).append(
                    (quando - inicio).total_seconds())
    return medidas


def _hora(ts) -> datetime | None:
    try:
        marca = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    return marca if marca.tzinfo else marca.replace(tzinfo=timezone.utc)


def _hora_local(ts) -> str:
    """"HH:MM" no fuso DA CASA, nao em UTC.

    O `atividade.jsonl` grava em UTC (certo: fuso explicito nunca ambiguo) e
    os dois `publicados.jsonl` gravam hora local. Fatiar as duas strings do
    mesmo jeito colocava "20:11" ao lado de "17:12" para coisas que
    aconteceram no mesmo minuto — e o relatorio existe justamente para
    responder EM QUE HORARIO. Um relatorio com fuso trocado mente com cara de
    precisao.
    """
    marca = _hora(ts)
    if marca is None:
        return "--:--"
    return marca.astimezone().strftime("%H:%M")


def _mediana(valores: list) -> float:
    ordenados = sorted(valores)
    meio = len(ordenados) // 2
    if not ordenados:
        return 0.0
    if len(ordenados) % 2:
        return ordenados[meio]
    return (ordenados[meio - 1] + ordenados[meio]) / 2


def _tempo(segundos: float) -> str:
    if segundos < 90:
        return f"{segundos:.0f}s"
    if segundos < 5400:
        return f"{segundos / 60:.0f}min"
    return f"{segundos / 3600:.1f}h"


def funcionamento(agora: datetime | None = None, *, horas: int = 24) -> str:
    """Como a maquina passou: o que rodou, quanto demorou, o que falhou."""
    agora = agora or datetime.now()
    corte = datetime.now(timezone.utc) - timedelta(hours=horas)
    eventos = [e for e in atividade.recentes(4000)
               if (_hora(e.get("ts")) or corte) >= corte]

    linhas = [f"🩺 *Funcionamento* — últimas {horas}h", ""]

    # --- fabricas: quantas passadas, quantas falharam, quanto demoram
    duracoes = _duracoes(eventos)
    contagem = {}
    for evento in eventos:
        fabrica = evento.get("fabrica")
        situacao = evento.get("status")
        if situacao in (atividade.OK, atividade.ERRO):
            ficha = contagem.setdefault(fabrica, {"ok": 0, "erro": 0})
            ficha["ok" if situacao == atividade.OK else "erro"] += 1
    if contagem:
        linhas.append("*Fábricas*")
        for fabrica, ficha in sorted(
                contagem.items(), key=lambda p: -(p[1]["ok"] + p[1]["erro"])):
            dados = atividade.FABRICAS.get(fabrica, {})
            tempos = [t for t in (duracoes.get(fabrica) or []) if t >= 1]
            # Sem medida NENHUMA e melhor do que "mediana 0s": zero aqui
            # significa que nao deu para emparelhar, nao que foi instantaneo.
            medida = (f" · mediana {_tempo(_mediana(tempos))}"
                      if tempos else "")
            falhas = f" · {ficha['erro']} erro" if ficha["erro"] else ""
            linhas.append(f"  {dados.get('emoji', '•')} "
                          f"{dados.get('rotulo', fabrica)}: "
                          f"{ficha['ok']} ok{falhas}{medida}")
    else:
        linhas.append("*Fábricas* — nada rodou nesta janela")

    # --- erros, com a hora, porque "3 erros" sozinho nao ajuda ninguem
    falhas = [e for e in eventos if e.get("status") == atividade.ERRO]
    if falhas:
        linhas += ["", f"*Erros* ({len(falhas)})"]
        for evento in falhas[-5:]:
            dados = atividade.FABRICAS.get(evento.get("fabrica"), {})
            detalhe = " ".join((evento.get("detalhe") or "").split())[:90]
            linhas.append(f"  {_hora_local(evento.get('ts'))} "
                          f"{dados.get('emoji', '•')} {detalhe}")
    else:
        linhas += ["", "*Erros* — nenhum ✓"]

    # --- o agendamento, que e o que decide se AMANHA acontece
    linhas += ["", "*Agendamento*"] + _linhas_do_agendador()
    linhas += ["", "*Credenciais*"] + _linhas_das_credenciais()
    return "\n".join(linhas)


def _linhas_das_credenciais() -> list[str]:
    """O OAuth de cada canal ainda funciona?

    Entra aqui porque um refresh_token morto nao faz barulho: a publicacao
    continua (ela vai pelo navegador), so a MEDICAO para. Medido em
    11/09/2026, o canal de historias estava assim desde 31/08 e a pasta de
    metricas dele nunca chegou a existir — onze dias sem um numero, sem uma
    linha de erro em lugar nenhum.

    `oauth_vivo` usa rede de proposito: `tem_login` so olha o arquivo, e foi
    exatamente isso que ja mentiu antes (08/09/2026).
    """
    try:
        from builds import contas
    except Exception:                                          # noqa: BLE001
        return ["  (não consegui consultar as contas)"]
    saida = []
    for canal in ("builds", "historias"):
        try:
            ficha = contas.oauth_vivo(canal)
        except Exception as exc:                               # noqa: BLE001
            saida.append(f"  ⚠ {canal}: não deu para conferir ({exc})"[:120])
            continue
        if ficha.get("ok") and not ficha.get("motivo"):
            continue
        marca = "⚠" if ficha.get("ok") else "❗"
        saida.append(f"  {marca} {canal}: {ficha.get('motivo')}")
        if not ficha.get("ok"):
            try:
                from builds.publicar import metricas
                saida.append(f"     `{metricas.comando_oauth(canal)}`")
            except Exception:                                  # noqa: BLE001
                pass
    return saida or ["  ✓ os dois canais medem normalmente"]


def _linhas_do_agendador() -> list[str]:
    """As tarefas disparam mesmo? Uma linha, e o detalhe so quando ha problema.

    Isto entra no relatorio porque em 09/09/2026 as dez tarefas estavam
    recusando iniciar na bateria e nunca recuperavam horario perdido — e
    nada, em lugar nenhum, dizia isso.
    """
    try:
        from builds import tarefas_windows
    except Exception:                                          # noqa: BLE001
        return ["  (não consegui consultar o Agendador)"]
    # AS OITO DE POSTAGEM, e nao a antiga `NeuralFights_postar`. Aquela tarefa
    # foi APAGADA de proposito quando a grade virou uma por horario
    # (`postar.instalar_grade` a deleta antes de criar as novas), e a lista
    # aqui nunca acompanhou. Resultado medido em 11/09/2026: o relatorio
    # dizia "1 tarefa nao existe" TODO DIA — e, pior, nunca conferia nenhuma
    # das oito que de fato publicam. Alerta que sempre acende e alerta que
    # ninguem le, e um instrumento cego achando que esta olhando.
    #
    # A postagem vem de `grade.HORAS`, a fonte unica dos horarios de publicar.
    # A CRIACAO vem do config da agenda: desde 13/09/2026 ela roda de
    # madrugada, e conferir os oito horarios do dia acusaria oito tarefas
    # sumidas todo dia.
    #
    # A GERACAO NOTURNA DE DUELOS (`NeuralFights_gerar_HH`, bdfa125) entrou
    # em 28/09/2026: cinco tarefas de madrugada que ninguem conferia, e das
    # quais depende o estoque do canal de builds. As horas vem do config dela
    # (`geracao.json`) e o nome, de quem cria a tarefa; desligada (`ativo`
    # falso), ela nao e cobrada. O app do celular entra junto: ele tambem
    # vive de uma tarefa que o relatorio nao olhava.
    #
    # LISTA QUE NAO SE LE NAO SOME EM SILENCIO. Sem ela o monitor conferia
    # menos tarefas e dizia "✓" do mesmo jeito.
    ilegiveis = []
    try:
        from contos.pipeline import agenda
        horas_de_criacao = list(agenda.carregar()["horas"])
    except Exception:                                          # noqa: BLE001
        horas_de_criacao = []
        ilegiveis.append("da criação das histórias")
    try:
        from builds.pipeline import noite, tarefas_noite
        geracao = noite.carregar()
        tarefas_da_geracao = ([tarefas_noite.nome_da_tarefa(h)
                               for h in geracao["horas"]]
                              if geracao.get("ativo", True) else [])
    except Exception:                                          # noqa: BLE001
        tarefas_da_geracao = []
        ilegiveis.append("da geração noturna")
    nomes = ([f"Historias_auto_{h:02d}" for h in horas_de_criacao]
             + [f"NeuralFights_postar_{h:02d}" for h in grade.HORAS]
             + tarefas_da_geracao
             + ["NeuralFights_bot_telegram", "NeuralFights_app_celular"])
    fracas, sumidas = [], []
    for nome in nomes:
        ficha = tarefas_windows.conferir(nome)
        if not ficha:
            sumidas.append(nome)
        elif not ficha.get("confiavel"):
            fracas.append(nome)
    saida = []
    if sumidas:
        saida.append(f"  ❗ {len(sumidas)} tarefa(s) não existem: "
                     + ", ".join(sumidas[:3]))
    if fracas:
        saida.append(f"  ⚠ {len(fracas)} tarefa(s) somem na bateria ou "
                     "perdem horário: " + ", ".join(fracas[:3]))
    if not saida:
        saida.append(f"  ✓ {len(nomes)} tarefas ativas e confiáveis")
    for qual in ilegiveis:
        saida.append(f"  ⚠ não consegui ler as tarefas {qual}")
    return saida


# ------------------------------------------------------- quando cada um vai
def _estado_caminho() -> Path:
    """Ao lado do `remoto.json`, de proposito.

    Vem de `config.caminho().parent` e nao de `runtime_dir()` porque os testes
    apontam `config.ARQUIVO` para uma pasta temporaria — e um "ja mandei o
    relatorio de hoje" gravado pela suite no arquivo de verdade calaria o
    relatorio real daquele dia.
    """
    from . import config
    return config.caminho().parent / "relatorios.json"


def enviados() -> dict:
    """{nome: 'YYYY-MM-DD'} do ultimo envio de cada relatorio."""
    alvo = _estado_caminho()
    if not alvo.is_file():
        return {}
    try:
        with open(alvo, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def marcar(nome: str, dia: str) -> None:
    dados = enviados()
    dados[str(nome)] = str(dia)
    alvo = _estado_caminho()
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with open(alvo, "w", encoding="utf-8") as fh:
            json.dump(dados, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def devidos(horarios: dict, agora: datetime | None = None,
            ja_enviados: dict | None = None) -> list[str]:
    """Quais relatorios estao vencidos AGORA.

    A regra e "passou da hora e ainda nao foi hoje", e nao "e exatamente a
    hora": o bot reinicia, a maquina dorme, e um relatorio que so sai se
    alguem estiver olhando o relogio no minuto certo e um relatorio que nao
    sai. Mesma licao do `StartWhenAvailable` das tarefas do Windows.

    O que ele NAO faz e mandar o de ontem: se a maquina passou o dia inteiro
    desligada, aquele dia nao tem relatorio — inventar um depois seria pior
    do que a falta.
    """
    agora = agora or datetime.now()
    hoje = agora.strftime("%Y-%m-%d")
    ja_enviados = enviados() if ja_enviados is None else ja_enviados
    vencidos = []
    for nome, hora in (horarios or {}).items():
        if nome not in RELATORIOS:
            continue
        marca = _minutos(hora)
        if marca is None:
            continue
        if ja_enviados.get(nome) == hoje:
            continue
        if agora.hour * 60 + agora.minute >= marca:
            vencidos.append(nome)
    return vencidos


def _minutos(hora) -> int | None:
    """"21:00" -> 1260. Hora invalida vira None (o relatorio nao sai)."""
    try:
        h, _, m = str(hora).partition(":")
        total = int(h) * 60 + int(m or 0)
    except (TypeError, ValueError):
        return None
    return total if 0 <= total < 24 * 60 else None


def auditoria(agora: datetime | None = None) -> str:
    """Os quatro controles em texto — o mesmo veredito que a tela mostra.

    E o relatorio que responde "o proximo horario vai sair?", e nao "o que ja
    saiu". Ele existe porque em 11/09/2026 tres videos foram ao ar errados e
    nenhum dos dois relatorios de entao tinha como saber: metas contava
    publicacao e funcionamento contava erro, e um video ruim que publica sem
    erro nao aparece em nenhum dos dois.

    Chama a vistoria de verdade, que decodifica mp4 — segundos, nao
    milissegundos. Por isso ele nao entra no ritmo dos outros dois: e pedido.
    """
    try:
        from panorama import auditoria as motor
    except Exception as exc:                                   # noqa: BLE001
        return f"a auditoria não está disponível: {exc}"
    dados = motor.completa(com_rede=True)
    veredito = motor.veredito(dados)
    marca = {"ok": "✅", "aviso": "⚠️", "erro": "🚨"}.get(veredito["cor"], "•")
    linhas = [f"{marca} *Auditoria* — {veredito['frase']}", ""]

    qual = dados.get("qualidade") or {}
    linhas.append("*Qualidade* (o que a grade vai pegar)")
    linhas.append(f"  {qual.get('liberados', 0)} liberado(s) · "
                  f"{qual.get('barrados', 0)} barrado(s) · "
                  f"{qual.get('pendentes', 0)} na fila")
    for item in (qual.get("fila") or []):
        if item.get("ok"):
            continue
        motivo = (item.get("erros") or ["?"])[0]
        linhas.append(f"  ✕ {item['id']}: {motivo[:110]}")

    alvo = dados.get("metas") or {}
    linhas += ["", "*Metas de hoje*",
               f"  {alvo.get('horarios_vencidos', 0)} de "
               f"{alvo.get('horarios_do_dia', 0)} horários já venceram · "
               f"próximo {alvo.get('proximo', '—')}"]
    for canal, ficha in (alvo.get("canais") or {}).items():
        corpo = " · ".join(f"{p} {x['saiu']}/{x['devido']}"
                           for p, x in ficha.items())
        marca = "✓" if all(x["faltando"] == 0 for x in ficha.values()) else "⏳"
        linhas.append(f"  {marca} {canal}: {corpo}")

    prod = dados.get("producao") or {}
    travadas = prod.get("historias_incompletas")
    if isinstance(travadas, list) and travadas:
        linhas += ["", "*Produção* — parou no meio"]
        for item in travadas[:4]:
            faltas = []
            if item.get("partes_sem_texto"):
                faltas.append(f"texto das partes {item['partes_sem_texto']}")
            if item.get("imagens_faltando"):
                faltas.append(f"{item['imagens_faltando']} imagem(ns)")
            if item.get("partes_sem_video"):
                faltas.append(f"{item['partes_sem_video']} vídeo(s)")
            linhas.append(f"  {item.get('id')}: " + ", ".join(faltas or ["?"]))

    alertas = (dados.get("recursos") or {}).get("alertas") or []
    linhas += ["", "*Recursos*"]
    if alertas:
        linhas += [f"  ⚠ {a}" for a in alertas[:6]]
    else:
        disco = (dados.get("recursos") or {}).get("disco") or {}
        linhas.append(f"  ✓ disco {disco.get('livre_gb', '—')} GB, contas e "
                      "tarefas em ordem")
    return "\n".join(linhas)


def confiabilidade(agora: datetime | None = None, *, ficha=None) -> str:
    """O que foi afirmado hoje, e o que da para provar.

    FORMATA E NAO CALCULA. O numero mora em `panorama.confiabilidade`, que e
    o mesmo que a pagina do painel le: se os dois mostrarem coisas
    diferentes para o mesmo dia, o defeito esta la, e so la se conserta.

    Quase sempre e uma linha. So cresce quando ha o que olhar.
    """
    if ficha is None:
        from panorama import confiabilidade as fonte
        dia = (agora or datetime.now()).strftime("%Y-%m-%d")
        ficha = fonte.hoje(dia)
    dia = datetime.strptime(ficha["dia"], "%Y-%m-%d").strftime("%d/%m")
    prometido, provado = ficha.get("prometido", 0), ficha.get("provado", 0)
    marca = "✓" if ficha.get("veredito") == "ok" else "⚠"
    linhas = [f"🔒 *Confiabilidade* — {dia}",
              f"{marca} {provado}/{prometido} publicação(ões) com prova"]
    if ficha.get("sem_campo"):
        linhas.append(f"   {ficha['sem_campo']} sem laudo (não sei, não é falha)")
    if not ficha.get("alertas"):
        return "\n".join(linhas)

    linhas.append("")
    for alerta in ficha["alertas"]:
        linhas.append(f"• {alerta}")
    for v in (ficha.get("valvula") or [])[:4]:
        linhas.append(f"   ↳ {v.get('hora', '')} {v.get('alvo', '')}: "
                      f"{v.get('motivo', '')}")
    for canal, ids in (ficha.get("num_destino_so") or {}).items():
        if ids:
            amostra = ", ".join(f"`{i}`" for i in ids[:3])
            linhas.append(f"   ↳ {canal}: {amostra}"
                          f"{' …' if len(ids) > 3 else ''}")
    falhas = [f"{nome} {ficha[campo]}x" for nome, campo in
              (("TikTok", "falhas_tiktok"), ("YouTube", "falhas_youtube"))
              if ficha.get(campo)]
    if falhas:
        linhas.append(f"   (falhas ao publicar hoje: {', '.join(falhas)} — "
                      "o número que importa é o de destino só)")
    ignoradas = ficha.get("falhas_ignoradas") or []
    if ignoradas:
        refs = ", ".join(sorted({f"`{i.get('ref')}`" for i in ignoradas}))
        linhas.append(f"   ({len(ignoradas)} falha(s) de teste fora da conta: "
                      f"{refs})")
    return "\n".join(linhas)


RELATORIOS = {"metas": metas, "funcionamento": funcionamento,
              "auditoria": auditoria, "confiabilidade": confiabilidade}


def montar(nome: str, agora: datetime | None = None) -> str:
    """O texto daquele relatorio. Nunca levanta: relatorio que quebra o bot
    seria pior do que relatorio nenhum."""
    funcao = RELATORIOS.get(str(nome))
    if funcao is None:
        return f"não conheço o relatório {nome!r}."
    try:
        return funcao(agora)
    except Exception as exc:                                   # noqa: BLE001
        return (f"o relatório de {nome} falhou: "
                f"{type(exc).__name__}: {exc}")
