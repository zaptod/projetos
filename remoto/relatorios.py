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

from builds import atividade

RAIZ = Path(__file__).resolve().parents[1]

# UM VIDEO EM CADA HORARIO DA GRADE (6, 7, 8, 10, 12, 15, 17, 20), e nao um
# por dia — correcao dele em 09/09/2026. A meta do dia so esta batida quando
# os oito sairam; contar "pelo menos um" esconderia sete disparos perdidos.
HORARIOS_DA_GRADE = (6, 7, 8, 10, 12, 15, 17, 20)
META_DIARIA_POR_CANAL = len(HORARIOS_DA_GRADE)
CANAIS = {
    "historias": {"emoji": "📖", "rotulo": "histórias"},
    "builds": {"emoji": "⚔️", "rotulo": "builds"},
}
# UM DIA, o mesmo alvo do `ferramentas/postar.py`. Era 14 ate 10/09/2026:
# com a meta de estoque em um dia, alertar a partir de duas semanas seria
# alertar sempre.
PISO_DE_ESTOQUE = 1


# ----------------------------------------------------------------- coleta
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
            saida.append({
                "canal": canal,
                "quando": quando,
                "dia": quando[:10],
                "hora": quando[11:16],
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
    """Quantos videos, em que horario, em que canal. E se bateu a meta."""
    agora = agora or datetime.now()
    hoje = agora.strftime("%Y-%m-%d")
    tudo = _publicacoes()
    por_dia = {}
    for item in tudo:
        por_dia.setdefault(item["dia"], []).append(item)

    linhas = [f"🎯 *Metas* — {agora.strftime('%d/%m')}", ""]

    # --- hoje, com hora e canal, que e literalmente o que ele pediu
    de_hoje = por_dia.get(hoje) or []
    if de_hoje:
        linhas.append("*Hoje*")
        for item in de_hoje:
            ficha = CANAIS.get(item["canal"], {})
            visto = item["visibilidade"]
            marca = {"public": "público", "private": "PRIVADO",
                     "unlisted": "não listado"}.get(visto, visto or "?")
            linhas.append(f"  {ficha.get('emoji', '•')} {item['hora']}  "
                          f"{ficha.get('rotulo', item['canal'])} · {marca}")
    else:
        linhas.append("*Hoje* — nada publicado ainda")

    # A meta e por HORARIO, entao o placar tem que ser por horario — dizer
    # "os dois canais publicaram" com um post de oito seria dar por batida uma
    # meta que faltou 7/8.
    linhas.append("")
    for canal, ficha in CANAIS.items():
        saiu = sum(1 for i in de_hoje if i["canal"] == canal)
        alvo = META_DIARIA_POR_CANAL
        marca = "✓" if saiu >= alvo else "⏳"
        linhas.append(f"  {marca} {ficha['emoji']} {ficha['rotulo']}: "
                      f"{saiu}/{alvo} horários")

    # --- a serie, que e onde se ve se e habito ou sorte
    linhas += ["", f"*Últimos {dias} dias*"]
    completos = 0
    for recuo in range(dias - 1, -1, -1):
        dia = (agora - timedelta(days=recuo)).strftime("%Y-%m-%d")
        itens = por_dia.get(dia) or []
        contagem = {c: 0 for c in CANAIS}
        for item in itens:
            if item["canal"] in contagem:
                contagem[item["canal"]] += 1
        bateu = all(v >= META_DIARIA_POR_CANAL for v in contagem.values())
        completos += 1 if bateu else 0
        corpo = " ".join(f"{CANAIS[c]['emoji']}{contagem[c]}" for c in CANAIS)
        linhas.append(f"  {dia[8:10]}/{dia[5:7]}  {corpo}  "
                      f"{'✓' if bateu else '✗'}")
    total = {c: sum(1 for i in tudo
                    if i["canal"] == c
                    and i["dia"] >= (agora - timedelta(days=dias - 1)
                                     ).strftime("%Y-%m-%d"))
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
            linhas.append(f"  {item['dia'][8:10]}/{item['dia'][5:7]} "
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
    return "\n".join(linhas)


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
    nomes = ([f"Historias_auto_{h:02d}" for h in (6, 7, 8, 10, 12, 15, 17, 20)]
             + ["NeuralFights_postar", "NeuralFights_bot_telegram"])
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


RELATORIOS = {"metas": metas, "funcionamento": funcionamento}


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
