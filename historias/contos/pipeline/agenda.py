# -*- coding: utf-8 -*-
"""Criacao automatica: um disparo, uma historia inteira.

O Agendador do Windows chama `main.py auto` nas horas de `config/agenda.json`.
Cada chamada faz o caminho todo — roteiro no LLM, imagens no PicassoIA, um mp4
por parte — e escreve tudo em `outputs/_logs/auto_<data>.txt`.

TRES CUIDADOS, cada um vindo de uma coisa medida:

  UMA DE CADA VEZ. Uma historia leva ~4h (medido na 8: 5 min de roteiro, 3h13
  de imagens, 53 min de video). Oito disparos num dia nao cabem, e dois ao
  mesmo tempo brigariam pelo MESMO perfil de Chrome do LLM e pela MESMA conta
  do PicassoIA — que ainda por cima e dividida com o canal de builds. O
  disparo que encontra rodada em andamento sai na hora e diz isso no log; nao
  espera, porque esperar so empurraria a fila para cima do disparo seguinte.

  TERMINA ANTES DE COMECAR. Se a rodada anterior morreu no meio (PC
  reiniciado, PicassoIA fora do ar), existe uma historia sem imagem ou sem
  video. Comecar outra por cima deixaria as duas pela metade. Entao a rodada
  primeiro procura incompleta e termina; so cria historia nova quando nao ha
  nada pendente.

  RESPEITA A PAUSA. O mesmo interruptor que segura os workers (a pagina Vila,
  `identity/controle`) segura a rodada automatica. Pausar a pipeline e a
  primeira coisa que se faz quando algo esta errado; uma tarefa agendada que
  ignorasse isso seria a pior parte do sistema.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from builds.publicar.metricas import publicado as _publicado

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"
CONFIG = RAIZ / "config" / "agenda.json"

# Uma so rodada automatica por vez, em qualquer processo desta maquina.
TRAVA = "historias__auto"
# Horas aceitas no config: hora cheia, 0 a 23.
HORAS_VALIDAS = range(24)


# O RELOGIO E O SONO PASSAM POR AQUI, e nao por `datetime.now()`/`time.sleep`
# espalhados: os testes do lote (30/09/2026) congelam o relogio numa segunda
# 07:02 ou numa quinta 00:02 e trocam o sono por um que so avanca o relogio.
def _relogio() -> datetime:
    return datetime.now()


def _dormir(segundos: float) -> None:
    time.sleep(max(0.0, float(segundos)))


# A JANELA DO TRABALHO PESADO. Era a madrugada (13/09/2026: "fazer o trabalho
# pesado de madrugada e deixar os ajustes e deliverys para o dia"); desde
# 30/09/2026 e o DIA, 07h-22h, porque de madrugada o PC faz barulho (Grimorio
# `geral/fila-pesada-de-dia` e `geral/lote-janela-de-dia`). Pesado e o que
# abre navegador e segura a maquina por horas: roteiro, imagem, render,
# parecer do Gemini, conserto, metrica do TikTok. Ver `planejar`.
#
# Config sem `janela_pesada` roda a qualquer hora, como antes: e o que os
# testes e quem roda na mao esperam.
def na_janela(hora: int, janela: dict | None) -> bool:
    """A hora cheia `hora` esta dentro da janela? Atravessa a meia-noite."""
    if not janela:
        return True
    inicio, fim = int(janela["inicio"]) % 24, int(janela["fim"]) % 24
    if inicio == fim:
        return True
    if inicio < fim:
        return inicio <= int(hora) < fim
    return int(hora) >= inicio or int(hora) < fim


def minutos_ate_fechar(agora, janela: dict | None) -> float:
    """Quanto falta para a janela fechar. Sem janela, tempo de sobra."""
    from datetime import timedelta

    if not janela:
        return float("inf")
    fim = int(janela["fim"]) % 24
    fechamento = agora.replace(hour=fim, minute=0, second=0, microsecond=0)
    if fechamento <= agora:
        fechamento += timedelta(days=1)
    return (fechamento - agora).total_seconds() / 60.0


def chave_da_noite(agora, janela: dict | None) -> str:
    """A data em que a noite COMECOU.

    23h do dia 12 e 3h do dia 13 sao a mesma noite, "2026-09-12". Pela data
    do calendario seriam duas, e o que e "uma vez por noite" rodaria duas.

    Janela que NAO atravessa a meia-noite (a de dia, 07h-22h) e a data do
    calendario: sem esta guarda, as 10h de 30/09 dariam "2026-09-29".
    """
    atravessa = (janela and int(janela["inicio"]) % 24
                 > int(janela["fim"]) % 24)
    if atravessa and int(agora.hour) < int(janela["fim"]) % 24:
        return (agora - timedelta(days=1)).strftime("%Y-%m-%d")
    return agora.strftime("%Y-%m-%d")


# O minuto do disparo quando a hora vem sem ele: depois da postagem, nunca
# antes (a criacao abre os mesmos navegadores).
MINUTO_PADRAO = 20


def carregar(caminho: Path | None = None) -> dict:
    """O config, com `horas` (ints) e `minutos` ({hora: minuto}) normalizados.

    Cada disparo pode vir como hora cheia (`3`, dispara em :20) ou como
    `"HH:MM"` (desde 15/09/2026, para a rodada de dia cair 25 min depois de
    cada publicacao, que tem minuto proprio por horario).
    """
    with open(caminho or CONFIG, encoding="utf-8-sig") as fh:
        dados = json.load(fh)
    minutos = {}
    for item in dados.get("horas") or []:
        texto = str(item).strip()
        if ":" in texto:
            hora, minuto = texto.split(":", 1)
            hora, minuto = int(hora), int(minuto)
        else:
            hora, minuto = int(texto), MINUTO_PADRAO
        if hora in HORAS_VALIDAS:
            minutos[hora] = minuto
    dados["horas"] = sorted(minutos)
    dados["minutos"] = minutos
    return dados


def horario_do_disparo(config: dict, hora: int) -> str:
    """`'07:02'` — quando a agenda dispara naquela hora."""
    return f"{int(hora):02d}:{int((config.get('minutos') or {}).get(int(hora), MINUTO_PADRAO)):02d}"


def horarios_restantes(agora) -> int:
    """Quantos horarios da grade de publicacao ainda faltam hoje."""
    from builds import grade

    minuto = agora.hour * 60 + agora.minute
    return len([h for h in grade.HORAS if h * 60 + grade.minuto(h) > minuto])


def falta_video(aprovados: int, agora, piso: int = 1) -> bool:
    """O estoque aprovado NAO cobre o resto do dia com folga de `piso`?"""
    return int(aprovados) < horarios_restantes(agora) + int(piso)


# ------------------------------------------------------------------ o lote
#
# DECISOES DO ADRIAN, 30/09/2026 (Grimorio `geral/lote-*`), e cada uma vira
# uma chave de `config/agenda.json`, nunca um numero no codigo:
#
#   janela_pesada        07h-22h: trabalho pesado so de dia (barulho a noite)
#   dias_de_lote         seg-qua: as historias da semana saem em lote
#   alvo_do_lote         o lote cobre ate segunda 07h + o piso de reposicao
#   piso_de_reposicao    qui-dom so consertam; criam so abaixo de 20 (2 dias)
#   estoque zero         de madrugada, sem video para o proximo horario,
#                        LIBERA TUDO: o canal nao pode parar
#   lote_a_partir_de     o 1o lote e seg 05/10; antes disso, dia de lote se
#                        comporta como dia de reposicao
#   madrugada_na_transicao  o esquema antigo (01h-06h) continua ate o de dia
#                        rodar validado um dia inteiro; tirar a chave desliga
#   folga_da_grade       passo novo nao comeca na meia hora em volta de cada
#                        horario da grade (inclusive 12:07 e 17:57)


def dias_de_lote(config: dict) -> set:
    """Os dias da semana do lote (0 = segunda)."""
    return {int(d) % 7 for d in (config.get("dias_de_lote") or [])}


def lote_valendo(config: dict, agora) -> bool:
    """Hoje e dia de lote? Antes de `lote_a_partir_de`, nao.

    Data torta no config NAO liga o lote: o erro barato e cair na reposicao,
    que ainda cria abaixo do piso.
    """
    desde = config.get("lote_a_partir_de")
    if desde:
        try:
            if agora.date() < datetime.strptime(str(desde),
                                                "%Y-%m-%d").date():
                return False
        except ValueError:
            return False
    return agora.weekday() in dias_de_lote(config)


def postagens_entre(inicio, fim) -> int:
    """Quantos horarios da grade caem em (inicio, fim]. Da GRADE, com minuto."""
    from builds import grade

    total, dia = 0, inicio.date()
    while dia <= fim.date():
        for hora, minuto in grade.GRADE:
            momento = datetime(dia.year, dia.month, dia.day, hora, minuto)
            if inicio < momento <= fim:
                total += 1
        dia += timedelta(days=1)
    return total


def fim_da_cobertura(config: dict, agora):
    """Ate quando o lote precisa cobrir: a PROXIMA segunda 07h (config).

    "Proxima" e estritamente depois de agora: na segunda 07:02 e a segunda
    seguinte — o lote daquela segunda produz a semana inteira. Na terca e na
    quarta e a mesma segunda, entao a meta NAO recomeca: se a segunda nao
    produziu (PC desligado), a terca e a quarta herdam a diferenca sozinhas.
    """
    alvo = config.get("alvo_do_lote") or {}
    padrao_dia = min(dias_de_lote(config) or {0})
    dia = int(alvo.get("cobrir_ate_o_dia", padrao_dia)) % 7
    padrao_hora = (config.get("janela_pesada") or {}).get("inicio", 0)
    hora = int(alvo.get("cobrir_ate_a_hora", padrao_hora)) % 24
    base = agora.replace(hour=hora, minute=0, second=0, microsecond=0)
    base += timedelta(days=(dia - agora.weekday()) % 7)
    if base <= agora:
        base += timedelta(days=7)
    return base


def piso_de_reposicao(config: dict) -> int:
    """Abaixo disto, qui-dom criam. Sem a chave, o teto de sempre (2 dias)."""
    valor = config.get("piso_de_reposicao")
    if valor is None:
        return teto_de_estoque(config)
    return max(0, int(valor))


def alvo_do_lote(config: dict, agora) -> int:
    """Videos aprovados que a fila precisa ter AGORA num dia de lote.

    Os horarios da grade de agora ate `fim_da_cobertura` (segunda 07h), mais
    o piso de reposicao (`alvo_do_lote.mais_o_piso`). Medido com a grade de
    10 horarios: segunda 07:02 = 70 + 20 = 90; quarta 22:00 = 44 + 20 = 64.
    """
    alvo = config.get("alvo_do_lote") or {}
    total = postagens_entre(agora, fim_da_cobertura(config, agora))
    if alvo.get("mais_o_piso", True):
        total += piso_de_reposicao(config)
    return total


def postagem_perto(config: dict, agora):
    """O horario da grade (datetime) a menos de `folga_da_grade` de agora.

    `None` quando nao ha postagem perto (ou o config nao tem folga). Olha a
    grade de ontem, hoje e amanha, para as 23:50 enxergarem o 00:37.
    """
    folga = config.get("folga_da_grade")
    if not folga:
        return None
    from builds import grade

    antes = timedelta(minutes=int(folga.get("antes", 15)))
    depois = timedelta(minutes=int(folga.get("depois", 15)))
    for delta in (-1, 0, 1):
        dia = (agora + timedelta(days=delta)).date()
        for hora, minuto in grade.GRADE:
            post = datetime(dia.year, dia.month, dia.day, hora, minuto)
            if post - antes <= agora <= post + depois:
                return post
    return None


def esperar_a_grade(config: dict, log=print) -> bool:
    """Segura o PROXIMO passo enquanto uma postagem esta perto.

    O passo que ja esta rodando termina (quem decide isso e quem chama: esta
    funcao so roda ENTRE passos). Devolve False quando a janela fechou
    enquanto esperava — ai nao se comeca nada.
    """
    folga = config.get("folga_da_grade") or {}
    depois = timedelta(minutes=int(folga.get("depois", 15)), seconds=5)
    avisou = False
    for _ in range(6):
        agora = _relogio()
        post = postagem_perto(config, agora)
        if post is None:
            break
        fim = post + depois
        if not avisou:
            log(f"[auto] postagem das {post:%H:%M} perto: nao comeco passo "
                f"novo ate {fim:%H:%M}.")
            avisou = True
        _dormir(max(1.0, (fim - agora).total_seconds()))
    return na_janela(_relogio().hour, config.get("janela_pesada"))


def estoque_zero(aprovados, config: dict | None = None) -> bool:
    """Nao ha video para o PROXIMO horario?

    Zero aprovado e zero. Com aprovados, olha as series: se nenhuma tem a
    PROXIMA parte aprovada (a ordem e sagrada), nada sai no proximo horario
    mesmo com video no disco. Nao saber contar NAO e zero: o erro barato de
    madrugada e nao fazer barulho.
    """
    aprovados = list(aprovados or ())
    if not aprovados:
        return True
    try:
        conta = series_elegiveis(aprovados, None,
                                 teto_por_historia(config or {}))
    except Exception:                                          # noqa: BLE001
        return False
    return bool(conta) and conta.get("elegiveis", 1) == 0


def _livre_gb(caminho: str) -> float:
    import shutil
    return shutil.disk_usage(caminho).free / (1024 ** 3)


def disco_apertado(config: dict) -> str | None:
    """Texto quando o disco vigiado tem menos que o minimo; senao None.

    Plano do lote (30/09/2026): C: estava com 13 GB e o lote nao comeca com
    menos de `disco_livre_minimo_gb`. Nao conseguir medir nao para nada.
    """
    try:
        minimo = float(config.get("disco_livre_minimo_gb") or 0)
    except (TypeError, ValueError):
        return None
    if minimo <= 0:
        return None
    alvo = str(config.get("disco_a_vigiar") or "C:/")
    try:
        livre = _livre_gb(alvo)
    except OSError:
        return None
    if livre >= minimo:
        return None
    return f"so {livre:.1f} GB livres em {alvo} (minimo {minimo:g} GB)"


def _impedimento_de_criar(config: dict) -> str | None:
    """O que impede criar AGORA, mesmo com falta de video. Nunca levanta."""
    try:
        from ..imagens import cota
        texto = cota.motivo()
    except Exception:                                          # noqa: BLE001
        texto = None
    return texto or disco_apertado(config)


def _marca_do_servico() -> Path:
    return OUTPUTS / "_servico_do_dia.json"


def servico_pendente(agora) -> bool:
    """O servico do dia (metrica, tempos, conferencia) ainda nao rodou hoje?"""
    try:
        with open(_marca_do_servico(), encoding="utf-8") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return True
    return (dados or {}).get("data") != agora.strftime("%Y-%m-%d")


def _marcar_servico(agora) -> None:
    try:
        destino = _marca_do_servico()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({"data": agora.strftime("%Y-%m-%d"),
                                       "em": agora.isoformat(
                                           timespec="seconds")}),
                           encoding="utf-8")
    except OSError:
        pass


def modo_da_hora(config: dict, agora) -> str:
    """'livre' | 'lote' | 'reposicao' | 'madrugada' | 'noite'."""
    janela = config.get("janela_pesada")
    if not janela:
        return "livre"
    if na_janela(agora.hour, janela):
        return "lote" if lote_valendo(config, agora) else "reposicao"
    transicao = config.get("madrugada_na_transicao")
    if transicao and na_janela(agora.hour, transicao):
        return "madrugada"
    return "noite"


def planejar(config: dict, agora, *, aprovados=None, barrados=None,
             pendentes=None) -> dict:
    """O que a rodada faz agora. Nunca abre navegador.

    Devolve `{modo, fazer, criar, emendar, meta, aprovados, barrados,
    por_que, motivo, config}`. `config` e o config EFETIVO que `_trabalhar`
    recebe (teto, so_consertar, retomar, servico do dia). `motivo` e o do
    dicionario da rodada quando `fazer` e False.

    livre      config sem janela: roda como sempre rodou (testes, mao)
    lote       seg-qua 07h-22h: cria ate `alvo_do_lote`, emendando
    reposicao  qui-dom 07h-22h: conserta; cria so abaixo do piso
    madrugada  transicao: o esquema antigo das 01h-06h, uma historia por
               disparo, ate o teto de sempre
    noite      fora de tudo: nada, a nao ser o estoque zero (libera tudo)
    """
    modo = modo_da_hora(config, agora)
    if modo == "livre":
        return {"modo": modo, "fazer": True, "criar": True, "emendar": False,
                "por_que": "config sem janela", "config": config}
    if modo == "madrugada":
        return {"modo": modo, "fazer": True, "criar": True, "emendar": False,
                "por_que": "madrugada da transicao (o esquema antigo roda "
                           "ate o de dia ser validado)",
                "config": {**config,
                           "janela_pesada": config["madrugada_na_transicao"],
                           "servico_do_dia": False}}
    if modo == "noite":
        # A NOITE PERGUNTA OUTRA COISA: "sai algo no PROXIMO horario?". A
        # retida sai quando o horario ia ficar vazio, entao aqui ela conta.
        lista = (aprovados_no_estoque() if aprovados is None
                 else list(aprovados))
        n = len(lista)
        if not (config.get("estoque_zero_libera_a_noite", True)
                and estoque_zero(lista, config)):
            janela = config["janela_pesada"]
            return {"modo": modo, "fazer": False, "criar": False,
                    "emendar": False, "aprovados": n,
                    "motivo": "fora da janela",
                    "por_que": (f"fora da janela do trabalho pesado "
                                f"({int(janela['inicio']):02d}h as "
                                f"{int(janela['fim']):02d}h) e com video "
                                f"para o proximo horario ({n} aprovado(s))"),
                    "config": config}
        impedido = _impedimento_de_criar(config)
        piso = max(1, piso_de_reposicao(config))
        return {"modo": "zero", "fazer": not impedido,
                "criar": not impedido, "emendar": True, "aprovados": n,
                "meta": piso, "motivo": "impedido" if impedido else "",
                "impedimento": impedido,
                "por_que": ("ESTOQUE ZERO de madrugada: nenhum video para o "
                            "proximo horario; libera tudo (decisao de "
                            "30/09/2026)")
                           + (f", mas {impedido}" if impedido else ""),
                "config": {**config, "janela_pesada": None,
                           "teto_de_estoque": piso, "so_consertar": False,
                           "retomar_incompletas": True,
                           "revisar_estoque_a_noite": False,
                           "servico_do_dia": False,
                           "reparos_por_rodada":
                               int(config.get("reparos_de_dia") or 2)}}

    lista_barrados = barrados_no_estoque() if barrados is None else barrados
    nb = len(lista_barrados or ())
    # HISTORIA PELA METADE E CONSERTO, nao criacao: ja foi paga (roteiro,
    # imagens) e o lote de quarta pode fechar as 22h no meio de uma. Sem
    # isto ela esperaria ate segunda, envelhecendo.
    ni = len(incompletas() if pendentes is None else pendentes)
    servico = servico_pendente(agora)
    # O NUMERO DA PUBLICACAO (30/09/2026): `estoque_publicavel`, o mesmo do
    # `postar.py --ver`. Lista passada por quem chama (teste, mao) vale.
    n = (estoque_publicavel() if aprovados is None
         else len(list(aprovados)))
    if modo == "lote":
        meta = alvo_do_lote(config, agora)
        reparos = int(config.get("reparos_por_rodada") or 6)
        rotulo = f"lote: {n} publicavel(is) para um alvo de {meta}"
    else:
        meta = piso_de_reposicao(config)
        reparos = int(config.get("reparos_de_dia") or 2)
        rotulo = f"reposicao: {n} publicavel(is), piso {meta}"
    criar = n < meta
    impedido = _impedimento_de_criar(config) if criar else None
    if impedido:
        criar = False
    motivos = [rotulo]
    if nb:
        motivos.append(f"{nb} barrado(s)")
    if ni:
        motivos.append(f"{ni} historia(s) pela metade")
    if servico:
        motivos.append("servico do dia pendente")
    if impedido:
        motivos.append(f"NAO crio: {impedido}")
    retomar = bool(ni) and not _impedimento_de_criar(config)
    fazer = bool(criar or nb or servico or retomar)
    if fazer:
        motivo = ""
    elif impedido:
        motivo = "impedido"
    else:
        motivo = "estoque cheio"
    return {"modo": modo, "fazer": fazer, "criar": criar, "emendar": True,
            "meta": meta, "aprovados": n, "barrados": nb, "motivo": motivo,
            "impedimento": impedido, "por_que": "; ".join(motivos),
            "config": {**config,
                       "teto_de_estoque": max(1, meta),
                       "so_consertar": not criar,
                       "retomar_incompletas": bool(criar or retomar),
                       "reparos_por_rodada": reparos,
                       "servico_do_dia": servico}}


def _diario(destino: Path, tela=print):
    """Escreve na tela E no arquivo — a tarefa agendada nao tem tela."""
    destino.parent.mkdir(parents=True, exist_ok=True)

    def log(texto: str) -> None:
        if tela:
            try:
                tela(texto)
            except Exception:                                  # noqa: BLE001
                pass
        try:
            with open(destino, "a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now():%H:%M:%S} {texto}\n")
        except OSError:
            pass
    return log


class _SaidaNoDiario:
    """`sys.stdout` que grava no diario em vez de num console.

    DOIS PROBLEMAS, UMA SOLUCAO. O primeiro e que a rodada TRAVAVA: em
    08/09/2026 o py-spy achou o processo parado ha 13 minutos em
    `session.py:77`, um `print()`. Escrever num console que ninguem esvazia
    bloqueia para sempre — e a rodada morre em pe, de janela aberta, segurando
    a trava do PicassoIA (que o canal de builds tambem usa).

    O segundo e que quase tudo que a geracao de imagem conta sobre si mesma
    ("[picasso] gerando... 21s", "origem comprovada", "prompt recusado") sai
    por `print`, nao pelo `log` — entao o diario de uma rodada de 4h tinha tres
    linhas e nenhuma delas dizia se as coisas estavam andando.

    Mandando `print` para o arquivo, ele nao pode bloquear e passa a contar a
    historia. A tela so recebe copia quando existe tela DE VERDADE (terminal
    interativo); a do Agendador nao conta, e e exatamente ela que trava.
    """

    def __init__(self, destino: Path, original=None):
        self.destino = Path(destino)
        self.eco = original if _e_terminal(original) else None
        self._resto = ""

    def write(self, texto: str) -> int:
        if self.eco is not None:
            try:
                self.eco.write(texto)
            except Exception:                                  # noqa: BLE001
                self.eco = None
        self._resto += texto
        linhas = self._resto.split("\n")
        self._resto = linhas.pop()
        if linhas:
            try:
                with open(self.destino, "a", encoding="utf-8") as fh:
                    for linha in linhas:
                        fh.write(f"{datetime.now():%H:%M:%S} {linha}\n")
            except OSError:
                pass
        return len(texto)

    def flush(self) -> None:
        if self.eco is not None:
            try:
                self.eco.flush()
            except Exception:                                  # noqa: BLE001
                self.eco = None

    def isatty(self) -> bool:
        return False


def avisar(texto: str, log=print) -> bool:
    """Manda uma mensagem no Telegram. NUNCA derruba a rodada.

    Por subprocesso, e nao por `import remoto`, por dois motivos. O primeiro e
    que `remoto` nao esta instalado no workspace — ele so e importavel com a
    RAIZ do monorepo como cwd, e a rodada roda de dentro de `historias/`. O
    segundo e que ja existe esse caminho: a pagina Vila do painel liga o bot
    exatamente assim, com `python -m remoto`.

    Um aviso que falha nao pode custar a historia: quatro horas de trabalho
    nao se perdem porque o Telegram estava fora do ar.
    """
    import subprocess
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "remoto", "--avisar", texto],
            cwd=str(RAIZ.parent), capture_output=True, text=True, timeout=90,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:                                   # noqa: BLE001
        log(f"[auto] nao consegui avisar no Telegram ({exc}).")
        return False
    if proc.returncode != 0:
        motivo = (proc.stdout or proc.stderr or "").strip()[:200]
        log(f"[auto] o aviso do Telegram nao saiu: {motivo}")
        return False
    return True


def _registrar_erro(resultado: dict) -> None:
    """Poe a falha da rodada no ledger compartilhado. Nunca levanta."""
    try:
        from builds import atividade
        detalhe = "; ".join(str(e) for e in (resultado.get("erros") or []))
        if not detalhe:
            detalhe = f"{resultado.get('motivo', '')} {resultado.get('erro', '')}"
        alvo = resultado.get("historia_id") or "criacao automatica"
        atividade.registrar("estudio", "erro", f"{alvo}: {detalhe[:400]}",
                            "historias")
    except Exception:                                          # noqa: BLE001
        pass


def _cronometrar(resultado: dict, gasto: float) -> None:
    """Grava quanto a rodada levou. Nunca levanta.

    Rodada que nao fez nada (`ja rodando`, `estoque cheio`, `pausado`) fica
    de fora: ela mede o custo de conferir, nao o de produzir, e misturar as
    duas faria a mediana do dia despencar sem nada ter melhorado.
    """
    try:
        if resultado.get("motivo") in ("ja rodando", "pausado",
                                       "agenda desligada", "fora da janela",
                                       "sem tempo na janela", "estoque cheio",
                                       "impedido"):
            return
        from builds import atividade
        atividade.registrar(
            "estudio", atividade.LOG,
            f"rodada: {resultado.get('feito', '?')}", "historias",
            etapa="rodada",
            ref=str(resultado.get("historia_id") or ""), dur_s=gasto)
    except Exception:                                          # noqa: BLE001
        pass


def _duracao(segundos: float) -> str:
    horas, resto = divmod(int(segundos), 3600)
    minutos = resto // 60
    return f"{horas}h{minutos:02d}" if horas else f"{minutos} min"


def mensagem(resultado: dict, segundos: float) -> str | None:
    """O texto do aviso — ou None quando nao ha o que contar.

    Disparo que sai sem fazer nada (trava ocupada, pausa) NAO avisa: sao 4 a 6
    por dia dizendo a mesma coisa, e aviso que se repete a toa e aviso que se
    aprende a ignorar.
    """
    if resultado.get("feito") != "historia":
        motivo = resultado.get("motivo") or ""
        if motivo in ("ja rodando", "pausado", "agenda desligada",
                      "fora da janela", "sem tempo na janela",
                      "so consertar", "estoque cheio", "impedido"):
            return None
        return (f"❌ *a criacao automatica falhou*\n{motivo}\n"
                f"{(resultado.get('erro') or '')[:300]}")

    historia_id = resultado.get("historia_id", "?")
    titulo = (resultado.get("titulo") or "")[:120]
    partes = resultado.get("partes") or "?"
    cenas = resultado.get("cenas") or "?"
    erros = resultado.get("erros") or []
    cabeca = ("✅" if not erros else "⚠️")
    linhas = [f"{cabeca} *{historia_id}* "
              + ("pronta" if not erros
                 else f"terminou com {len(erros)} problema(s)")]
    if titulo:
        linhas.append(titulo)
    linhas.append(f"{partes} partes · {cenas} cenas · {_duracao(segundos)}")
    for erro in erros[:3]:
        linhas.append(f"• {str(erro)[:200]}")
    return "\n".join(linhas)


def _e_terminal(fluxo) -> bool:
    try:
        return bool(fluxo is not None and fluxo.isatty())
    except Exception:                                          # noqa: BLE001
        return False


def incompletas() -> list[dict]:
    """Historias que existem mas nao terminaram: falta imagem ou falta video.

    E o que a rodada termina antes de criar outra. Historia de TESTE
    (`provedor: fake`) nao entra: as imagens dela sao cartoes de placeholder e
    tentar "terminar" isso geraria as 16 cenas de novo, de verdade, a toa.
    """
    from ..roteiro import roteiro as R
    from ..imagens import fila

    pendentes = []
    for resumo in R.listar():
        historia_id = resumo["historia_id"]
        try:
            roteiro = R.carregar(historia_id)
        except (OSError, ValueError):
            continue
        if str(roteiro.get("provedor") or "").lower() == "fake":
            continue
        # ROTEIRO PELA METADE NAO SE "TERMINA", SE RETOMA. Gerar imagem e
        # video para as partes que existem produziria uma serie truncada — e
        # publicar a parte 2 de uma historia que nao tem parte 3 e o pior
        # resultado possivel do canal, pior que atraso e pior que video fraco.
        # Aconteceu em 10/09/2026 as 06:15: o Gemini bateu no limite de uso no
        # meio da parte 3 e a `historia_00005` ficou com 2 de 6.
        faltam_partes = R.partes_que_faltam(roteiro)
        if faltam_partes:
            pendentes.append({"historia_id": historia_id,
                              "partes_sem_texto": faltam_partes,
                              "imagens_faltando": 0,
                              "partes_sem_video": []})
            continue
        imagens = fila.resumo(historia_id, roteiro)
        partes = roteiro.get("partes") or []
        serie = bool(roteiro.get("serie")) and len(partes) > 1
        faltam_videos = []
        for parte in partes:
            n = int(parte["n"])
            nome = f"final_celular_p{n:02d}.mp4" if serie else "final_celular.mp4"
            if not (OUTPUTS / historia_id / nome).is_file():
                faltam_videos.append(n)
        if imagens["faltam"] or faltam_videos:
            pendentes.append({"historia_id": historia_id,
                              "imagens_faltando": imagens["faltam"],
                              "partes_sem_video": faltam_videos})
    return pendentes


def teto_de_estoque(config: dict | None = None) -> int:
    """Quantos videos novos podem esperar na fila: `dias_de_gordura` de grade.

    DERIVADO da grade, e nao um numero solto no config. Se um dia a grade for
    de 8 para 12 horarios, o teto acompanha sozinho — um numero fixo ao lado
    de uma grade que muda vira mentira na primeira mudanca.

    TRES ESTADOS no config, e a diferenca entre dois deles ja se perdeu uma
    vez hoje: `teto_de_estoque` AUSENTE (ou `null`) = derivar da grade, que e
    o padrao novo; `0` = FREIO DESLIGADO, que e a valvula de escape que ja
    existia e quase morreu quando eu fiz `0` significar "derive"; qualquer
    numero = esse numero.
    """
    config = config if config is not None else carregar()
    if "teto_de_estoque" in config and config["teto_de_estoque"] is not None:
        return int(config["teto_de_estoque"])
    # Da GRADE DE PUBLICACAO, e nao dos disparos de criacao. Eram a mesma
    # lista ate 13/09/2026; com a criacao so de madrugada (7 disparos), contar
    # os disparos daria teto 7 para uma grade que consome 8 por dia.
    from builds import grade
    return (len(grade.HORAS) or 8) * dias_de_gordura(config)


def dias_de_gordura(config: dict | None = None) -> int:
    """Quantos DIAS de grade o teto guarda. Dois desde 15/09/2026.

    Era um dia fixo desde 10/09 ("quero sempre ter a gordura de apenas um dia
    em tudo, mas quero que essa gordura seja totalmente nova"), e o motivo
    continua valendo: estoque grande e feito com o molde de hoje e vai ao ar
    semanas depois, quando o molde ja mudou.

    Dois dias nao briga com isso — 20 videos saem em 48 h — e e o minimo para
    a grade nova parar de pe. Com teto de um dia, o freio fecha em 10 e a
    producao da madrugada (6) fica abaixo do consumo (10): a fila so e
    reabastecida quando ja esta raspando, e qualquer noite que falhe deixa o
    dia seguinte sem video. Com dois, a rodada de dia tem margem para encher
    nos buracos entre as publicacoes antes de virar emergencia.
    """
    config = config if config is not None else carregar()
    return max(1, int(config.get("dias_de_gordura") or 2))


# O `ferramentas/postar.py`, carregado pelo caminho como o painel e o bot o
# carregam (`painel/flutuante/previsao.py`, `remoto/relatorios.py`).
POSTAR = RAIZ.parent / "ferramentas" / "postar.py"
_POSTAR_CARREGADO = None


def _postar():
    global _POSTAR_CARREGADO
    if _POSTAR_CARREGADO is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_postar_da_agenda",
                                                      POSTAR)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        _POSTAR_CARREGADO = modulo
    return _POSTAR_CARREGADO


def estoque_publicavel() -> int:
    """Quantas partes de historia a PUBLICACAO tem para os proximos horarios.

    UMA CONTAGEM SO (30/09/2026). As 11:02 a agenda contou 29 "aprovados" e
    entrou em "so consertar" (piso 20); as 11:21 o `postar.py --ver` contou
    8 (0,8 dia). Medido as 11:25: dos 27 da agenda, 20 eram partes RETIDAS
    (18 com o veto da IA, 2 so pela folha) — a vistoria mecanica deixa passar
    o veto vencido, e a publicacao so solta a retida quando o horario ia
    ficar vazio (decisao `reprovado-ou-nao-assistido`). Os 8 da publicacao
    sao os 7 que sobram mais a h41 p01, que a vistoria barrava. O freio
    contava como estoque o que a escolha nao usa, e o canal secaria em menos
    de um dia sem ninguem criar.

    Agora o numero que decide criar E o de `postar.pendentes_por_canal()` —
    o mesmo que o `--ver` mostra e que a gordura/alerta usam: a fila da
    escolha (`fila_de_historias`) sem as retidas. Nenhum criterio duplicado:
    se a publicacao mudar o que conta, a agenda muda junto.

    Nao deu para contar (`-1` ou excecao): cai no `aprovados_no_estoque`,
    que conta a mais — o erro barato e criar de menos, nao sem parar.
    """
    try:
        n = int(_postar().pendentes_por_canal().get("historias", -1))
    except Exception:                                          # noqa: BLE001
        n = -1
    if n >= 0:
        return n
    return len(aprovados_no_estoque())


def dias_de_estoque_novo() -> int:
    """O estoque que decide criar: `estoque_publicavel()` (30/09/2026).

    O nome ficou (o freio de `_trabalhar` e os testes o chamam); a conta e a
    da publicacao. O texto abaixo e a historia de antes, e o porque de ela
    ter passado a olhar so o que a vistoria aprova.

    Dias de video pronto feitos com a ABORDAGEM ATUAL.

    E este o numero que decide se vale criar mais, e nao o estoque total. O
    estoque velho (Gemini Flash, sem molde, sem revisao, sem alavancas) e
    RESERVA: serve para o canal nao ficar mudo se a criacao parar, mas nao e
    motivo para deixar de produzir o que esta melhor. Em 08/09/2026 eram 38
    dias de video antigo — contra um teto de 45, sobrariam sete dias de folga
    para o jeito novo, e as melhorias apareceriam a conta-gotas.

    A marca e `modelo_llm` no roteiro, gravada desde que o modelo passou a ser
    escolhido de proposito. Historia sem a marca e do tempo antigo.

    CONTA SO O QUE A VISTORIA APROVA, e essa e a correcao de 11/09/2026. Antes
    a conta era de ARQUIVO NO DISCO, e isso deixava a pipeline se matar de
    fome achando que estava abastecida: video barrado por colagem, por texto
    de outra historia ou pela IA continua no disco, continua contando como
    estoque, e o freio se fecha. A grade entao pede um video que a vistoria
    nao deixa sair, e nada cria mais nenhum. Nenhum alerta dispara, porque do
    ponto de vista do freio esta tudo cheio.

    Custa uma decodificacao por video (ffprobe), medido em 1 s cada, 8 s para
    a fila inteira. O freio roda oito vezes por dia: o custo e irrelevante
    perto de descobrir tarde que o canal ficou sem o que publicar.
    """
    return estoque_publicavel()


def aprovados_no_estoque() -> list:
    """Os videos PRONTOS E PUBLICAVEIS feitos com a abordagem atual."""
    from ..publicar import catalogo, qualidade, serie
    from ..roteiro import roteiro as R

    try:
        ja = {linha.get("video_id") for linha in serie.publicados()
              if _publicado(linha)}
    except Exception:                                          # noqa: BLE001
        ja = set()
    novas = set()
    for resumo in R.listar():
        if (resumo.get("modelo_llm") or "").strip():
            novas.add(resumo["historia_id"])

    aprovados, roteiros = [], {}
    for video in catalogo.listar():
        if video.id in ja or video.perfil != "celular":
            continue
        if video.fonte_id not in novas:
            continue
        try:
            if video.fonte_id not in roteiros:
                roteiros[video.fonte_id] = R.carregar(video.fonte_id)
            veredito = qualidade.liberado(video, roteiros[video.fonte_id])
        except Exception:                                      # noqa: BLE001
            # Nao deu para vistoriar: conta como estoque. Errar para o lado de
            # nao criar e melhor do que gerar sem parar por causa de um
            # ffprobe que travou.
            aprovados.append(video)
            continue
        if veredito.get("ok"):
            aprovados.append(video)
    return _sem_titulo_barrado(aprovados)


def _sem_titulo_barrado(aprovados: list) -> list:
    """Tira do ESTOQUE o que a guarda de titulo nunca vai deixar sair.

    Desde 17/09/2026 a valvula de titulo repetido FECHA: parte cujo titulo ja
    esta no ar nao sai — nunca, nao "sai depois". Mas ela continuava contando
    aqui, e o estoque alimenta o freio da producao.

    O resultado seria fome silenciosa: com 20 aprovados, tres deles com
    titulo repetido, o freio ve 20 (teto 20) e nao cria nada; a fila entrega
    17 e esvazia; o freio continua vendo 3 e continua sem criar. Horarios
    vazios ate alguem olhar — e nada acusa, porque o numero parece saudavel.

    Estoque quer dizer "video que vai sair". O que nao vai sair e outra
    coisa, e somar os dois faz o painel prometer o que nao tem.

    Falhar ao ler os titulos NAO tira ninguem do estoque: nesse caso o certo
    e contar a mais e criar de menos, nao o contrario — criar sem parar por
    causa de um ledger ilegivel seria trocar fome por enchente.
    """
    try:
        from builds.publicar import titulos
        from ..publicar import catalogo as _cat
        from ..publicar import serie
        # O INTERRUPTOR DA GRADE REABRE A VALVULA. Com ele ligado o titulo
        # repetido volta a sair, entao esses videos voltam a ser estoque — e
        # descontar aqui faria a producao passar do ponto.
        if (_cat.carregar_config() or {}).get("repetir_titulo"):
            return aprovados
        ja = titulos.ja_publicados(serie.publicados())
    except Exception:                                          # noqa: BLE001
        return aprovados
    if not ja:
        return aprovados
    return [v for v in aprovados
            if not titulos.repetido(getattr(v, "titulo", ""), ja)]


def barrados_no_estoque() -> list:
    """`[(video, motivos)]` do que esta pronto mas a vistoria nao deixa sair.

    E a lista que o reparador consome. Sai daqui, e nao de uma varredura
    propria, para o reparo olhar exatamente o que a grade olha.
    """
    from ..publicar import catalogo, qualidade, serie
    from ..roteiro import roteiro as R

    try:
        ja = {linha.get("video_id") for linha in serie.publicados()
              if _publicado(linha)}
    except Exception:                                          # noqa: BLE001
        ja = set()
    saida, roteiros = [], {}
    for video in catalogo.listar():
        if video.id in ja or video.perfil != "celular":
            continue
        try:
            if video.fonte_id not in roteiros:
                roteiros[video.fonte_id] = R.carregar(video.fonte_id)
            veredito = qualidade.liberado(video, roteiros[video.fonte_id])
        except Exception:                                      # noqa: BLE001
            continue
        if not veredito.get("ok"):
            saida.append((video, list(veredito.get("erros") or [])))
    return saida


def dias_de_estoque() -> int:
    """Quantos dias de postagem ja estao PRONTOS no disco.

    A unidade e o dia porque a postagem e de UM video por dia (decisao dele em
    08/09/2026). Antes isto contava HISTORIAS nao publicadas, e a conta ficou
    errada no dia em que a postagem passou a ser parte por parte: uma historia
    com a parte 1 no ar e cinco partes pendentes contava como "publicada" e
    sumia do estoque.

    E o numero que responde as duas perguntas que importam: tem gordura para
    postar amanha? e vale a pena continuar criando?
    """
    from ..publicar import catalogo, serie
    try:
        ja = {linha.get("video_id") for linha in serie.publicados()
              if _publicado(linha)}
    except Exception:                                          # noqa: BLE001
        ja = set()
    return len([v for v in catalogo.listar()
                if v.id not in ja and v.perfil == "celular"])


def rodar(*, config: dict | None = None, headless: bool = False,
          tela=print) -> dict:
    """Uma rodada. Devolve o que aconteceu — nunca levanta por conta da tarefa.

    O Agendador nao le excecao: o que ele ve e o codigo de saida. Entao aqui
    tudo vira dicionario e log, e quem decide o codigo de saida e o `main.py`.

    Desde o lote de 30/09/2026 a rodada EMENDA passos: num dia de lote ela
    cria historia atras de historia ate o alvo, a janela fechar ou um passo
    falhar. Os disparos seguintes do dia encontram a trava ocupada e saem; se
    a rodada morrer, o proximo disparo recomeca de onde ela parou.
    """
    from builds import travas
    from builds.identity import controle

    config = config or carregar()
    agora = _relogio()
    destino = OUTPUTS / "_logs" / f"auto_{agora:%Y%m%d}.txt"
    log = _diario(destino, tela)
    log(f"[auto] disparo das {agora:%H:%M}")

    if not config.get("ativo", True):
        log("[auto] a agenda esta desligada (`ativo: false`). Nada a fazer.")
        return {"feito": "nada", "motivo": "agenda desligada"}

    if controle.pausado_para():
        log("[auto] a pipeline esta PAUSADA (pagina Vila). Saindo sem criar "
            "nada; o proximo disparo tenta de novo.")
        return {"feito": "nada", "motivo": "pausado"}

    # O PLANO VEM ANTES DA TRAVA: o disparo que nao tem nada a fazer (noite
    # com video, reposicao com estoque cheio) sai sem disputar nada. A tarefa
    # perdida que roda quando o PC volta de manha tambem cai aqui.
    plano = planejar(config, agora)
    if not plano.get("fazer"):
        log(f"[auto] {plano.get('por_que')}. Saindo.")
        if (plano.get("motivo") == "impedido"
                and config.get("avisar_telegram", True)):
            _avisar_uma_vez_por_dia(
                "impedido-" + ("picasso" if "PicassoIA" in str(
                    plano.get("impedimento")) else "disco"),
                f"⚠️ *historias: nao crio agora*\n{plano.get('impedimento')}",
                agora, log)
        return {"feito": "nada", "motivo": plano.get("motivo") or
                "fora da janela", "modo": plano.get("modo")}
    if plano.get("modo") != "livre":
        log(f"[auto] modo {plano['modo']}: {plano.get('por_que')}.")

    with travas.trava(TRAVA, esperar=0.0) as minha:
        if not minha:
            log("[auto] ja tem uma rodada em andamento. Saindo — uma historia "
                "leva ~4h e duas ao mesmo tempo brigariam pelo mesmo "
                "navegador e pela mesma conta do PicassoIA.")
            return {"feito": "nada", "motivo": "ja rodando"}
        # Daqui para baixo mora o trabalho de verdade, e e onde o `print` das
        # bibliotecas de navegador aparece. Ele vai para o diario: num console
        # do Agendador ele TRAVA o processo, e no diario ele vira o unico
        # sinal de que a rodada esta andando.
        anterior_out, anterior_err = sys.stdout, sys.stderr
        sys.stdout = _SaidaNoDiario(destino, anterior_out)
        sys.stderr = _SaidaNoDiario(destino, anterior_err)
        try:
            # UM escritor so. Com o stdout ja indo para o diario, um `log` que
            # tambem escrevesse no arquivo gravaria a mesma linha duas vezes —
            # foi o que aconteceu na corrida das 08:21 de 08/09/2026, com o log
            # inteiro em dobro. Aqui `print` E o log: o `_SaidaNoDiario` carimba
            # a hora e ecoa na tela quando existe tela de verdade.
            comeco = time.monotonic()
            try:
                return _emendar(config, plano, headless, print)
            except Exception as exc:                           # noqa: BLE001
                # A rodada nao pode morrer calada: o unico jeito de descobrir
                # seria abrir o log, e quem abre o log ja desconfiou de algo.
                print(f"[auto] a rodada quebrou: {type(exc).__name__}: {exc}")
                resultado = {"feito": "nada", "motivo": "a rodada quebrou",
                             "erro": f"{type(exc).__name__}: {exc}"}
                if config.get("avisar_telegram", True):
                    avisar(mensagem(resultado, time.monotonic() - comeco))
                raise
        finally:
            sys.stdout, sys.stderr = anterior_out, anterior_err


def _emendar(config: dict, plano: dict, headless: bool, log) -> dict:
    """Os passos da rodada, um atras do outro. Devolve o ULTIMO resultado.

    So emenda quando o plano manda (`emendar`) e o passo anterior CRIOU ou
    TERMINOU uma historia sem erro: passo que nao andou (so conserto, estoque
    cheio, imagem faltando, teto do PicassoIA) encerra a rodada, e o proximo
    disparo tenta de novo. Isso impede o laco de insistir no mesmo defeito.

    Entre um passo e outro: a folga da grade (nao comeca nada perto de uma
    postagem), a janela (22h fecha) e um plano NOVO, com o estoque de agora.
    """
    efetivo = plano["config"]
    emendar = bool(plano.get("emendar"))
    limite = (max(1, int(config.get("passos_por_rodada") or 1))
              if emendar else 1)
    passos, historias, resultado = 0, [], None
    while True:
        if emendar and not esperar_a_grade(efetivo, log):
            log("[auto] a janela do trabalho pesado fechou; nao comeco passo "
                "novo.")
            break
        comeco = time.monotonic()
        resultado = _trabalhar(efetivo, headless, log)
        passos += 1
        _fechar_passo(resultado, time.monotonic() - comeco, config)
        if resultado.get("feito") == "historia" and resultado.get(
                "historia_id"):
            historias.append(resultado["historia_id"])
        if passos >= limite:
            if emendar:
                log(f"[auto] {passos} passo(s) nesta rodada (teto "
                    "`passos_por_rodada`); o proximo disparo continua.")
            break
        if (resultado.get("feito") not in ("historia", "texto")
                or resultado.get("erros")):
            break
        plano = planejar(config, _relogio())
        if not plano.get("criar"):
            log(f"[auto] paro de emendar: {plano.get('por_que')}.")
            break
        efetivo = plano["config"]
        log(f"[auto] emendo o passo {passos + 1} ({plano['modo']}): "
            f"{plano.get('por_que')}.")
    if resultado is None:
        return {"feito": "nada", "motivo": "sem tempo na janela", "passos": 0}
    saida = {**resultado, "passos": passos}
    if len(historias) > 1:
        saida["historias"] = historias
    return saida


def _fechar_passo(resultado: dict, gasto: float, config: dict) -> None:
    """Erro no diario, duracao no disco e aviso no Telegram — por PASSO.

    Era o fim da rodada; com a rodada emendando historias o dia inteiro, o
    aviso de cada historia pronta sairia so no fim do dia (ou nunca, se a
    ultima falhasse).
    """
    if resultado.get("erros") or resultado.get("motivo") not in (
            None, "", "ja rodando", "pausado", "agenda desligada",
            "fora da janela", "sem tempo na janela", "so consertar",
            "estoque cheio", "impedido"):
        # TODO ERRO NO MESMO LUGAR. `atividade.jsonl` e o ledger de
        # onde o bot tira os alertas e onde a apuracao automatica
        # procura o que investigar. As etapas ja registravam (imagens,
        # LLM); a rodada em si nao, entao uma falha DELA nao chegava
        # nem no Telegram nem no Claude.
        _registrar_erro(resultado)
    # A DURACAO DA RODADA VAI PARA O DISCO. Ela ja era medida aqui desde
    # sempre, e ia so para o TEXTO do Telegram — lida uma vez, nunca somada.
    _cronometrar(resultado, gasto)
    if config.get("avisar_telegram", True):
        texto = mensagem(resultado, gasto)
        if texto:
            avisar(texto)


def _avisar_uma_vez_por_dia(chave: str, texto: str, agora, log=print) -> bool:
    """Aviso que se repetiria a cada disparo sai UMA vez por dia."""
    marca = OUTPUTS / "_avisos_do_dia.json"
    hoje = agora.strftime("%Y-%m-%d")
    try:
        with open(marca, encoding="utf-8") as fh:
            dados = json.load(fh)
        if not isinstance(dados, dict):
            dados = {}
    except (OSError, ValueError):
        dados = {}
    if dados.get(chave) == hoje:
        return False
    dados = {k: v for k, v in dados.items() if v == hoje}
    dados[chave] = hoje
    try:
        marca.parent.mkdir(parents=True, exist_ok=True)
        marca.write_text(json.dumps(dados), encoding="utf-8")
    except OSError:
        pass
    return avisar(texto, log=log)


def _servico_do_dia(config: dict, headless: bool, log) -> None:
    """O servico do 1o disparo do dia. Nunca derruba a rodada: e servico.

    Era da madrugada (`_servico_da_noite`, 13 a 29/09/2026); com o pesado de
    dia (30/09) a metrica passou para o primeiro disparo da janela, as 07:02.
    Roda uma vez por dia (`outputs/_servico_do_dia.json`).

    1. METRICA do YouTube e do TikTok. A coleta do TikTok segura o Studio
       por ate 12 minutos.
    2. FECHAR O DIA DE ONTEM em tempos por etapa. O diario e podado acima de
       4000 linhas, entao a medicao fina dura menos de um dia nele: sem esta
       consolidacao, a serie que diz "o que piorou" nunca existiria.
    3. CONFERENCIA do canal.

    O parecer do Gemini no estoque (`revisar_estoque`) NAO mora aqui: ele
    roda a cada passo da janela, para a historia feita as 10h ser assistida
    no passo seguinte, e nao no dia seguinte.
    """
    agora = _relogio()
    try:
        from builds.publicar import metricas
        chave = f"dia-{agora:%Y-%m-%d}"
        if metricas.atualizar_uma_vez_por_dia(log=log, chave=chave):
            log("[auto] metricas do dia atualizadas.")
    except Exception as exc:                                   # noqa: BLE001
        log(f"[auto] a metrica do dia falhou: {type(exc).__name__}: {exc}")
    try:
        from builds import tempos
        destino = tempos.consolidar()
        log(f"[auto] tempos do dia fechados em {destino.name}.")
    except Exception as exc:                                   # noqa: BLE001
        log(f"[auto] a consolidacao dos tempos falhou: "
            f"{type(exc).__name__}: {exc}")
    try:
        from builds.publicar import conferencia
        conferencia.conferir_tudo(log=log)
    except Exception as exc:                                   # noqa: BLE001
        log(f"[auto] a conferencia do canal falhou: "
            f"{type(exc).__name__}: {exc}")
    _marcar_servico(agora)


def revisar_estoque(config: dict, *, headless: bool = False,
                    log=print) -> dict:
    """Parecer do Gemini para cada video pendente sem veredito numerado.

    Para quando a janela aperta. Video que ja tem veredito por cena e pulado,
    aprovado ou nao: o aprovado esta pronto e o reprovado e do reparador.
    """
    from ..publicar import catalogo, parecer, qualidade, serie
    from ..roteiro import roteiro as R
    from . import conserto_de_cena as C

    janela = config.get("janela_pesada")
    margem = float(config.get("minutos_minimos") or 90)
    ja = {l.get("video_id") for l in serie.publicados() if _publicado(l)}
    pendentes = [v for v in catalogo.listar()
                 if v.perfil == "celular" and v.id not in ja]
    revisados = aprovados = pulados = nao_assistidos = 0
    # Quem assiste: so ele pode tirar um video de "nao assistido". A folha
    # daquele video ja foi olhada, e olhar de novo nao muda nada.
    quem_assiste = (list(parecer.ASSISTEM_VIDEO) or ["gemini"])[0]
    segunda_chance = []
    for video in pendentes:
        if minutos_ate_fechar(_relogio(), janela) < margem:
            log("[auto] a janela esta fechando; paro a revisao do estoque.")
            break
        # NAO ASSISTIDO VOLTA AO GEMINI (27/09/2026). A passada dele nao foi
        # gasta: quem "olhou" foi a folha, depois de o Gemini recusar o mp4
        # com a frase enlatada. Sem isto o video ficaria retido para sempre.
        sem_assistir = parecer.nao_assistido(video)
        # ATUAL, e nao so numerado: veto dado com o criterio velho do parecer
        # e perguntado de novo aqui, com a regua de hoje.
        if not sem_assistir and C.atual(parecer.lembrado(video)):
            pulados += 1
            continue
        # UMA PASSADA SO NO GEMINI (15/09/2026): video que ja foi olhado uma
        # vez nao volta, nem depois de consertado (o mp4 novo zera o
        # `lembrado`, mas a passada dele ja foi gasta).
        if not sem_assistir and parecer.ja_olhado(video):
            pulados += 1
            continue
        roteiro = R.carregar(video.fonte_id)
        laudo = qualidade.vistoriar_parte(video.fonte_id, video.parte,
                                          video.caminho, roteiro)
        if not laudo.get("ok"):
            pulados += 1
            continue
        try:
            veredito = parecer.pedir(
                video, roteiro, video.parte, laudo=laudo, headless=headless,
                provedor=quem_assiste if sem_assistir else None, log=log)
        except parecer.SemParecer as exc:
            log(f"[auto] {video.id}: sem parecer agora ({exc})"
                + ("; continua NAO ASSISTIDO." if sem_assistir else "."))
            continue
        revisados += 1
        # SO CONTA COMO APROVADO QUEM ASSISTIU (27/09/2026): "revisei 9;
        # 5 aprovado(s)" daquela madrugada eram 5 folhas do ChatGPT depois de
        # o Gemini recusar o mp4 — nenhum dos cinco tinha sido assistido.
        situacao = parecer.situacao(veredito)
        if situacao == parecer.NAO_ASSISTIDO:
            nao_assistidos += 1
            segunda_chance.append((video, roteiro, laudo))
        elif situacao == parecer.SITUACAO_APROVADO:
            aprovados += 1
    # A SEGUNDA CHANCE VEM NO FIM, minutos depois, e nao na hora: a recusa
    # vem em rajadas. Em 27/09/2026 quatro chats novos seguidos foram
    # recusados entre 01:32 e 01:43, e os dois seguintes foram assistidos; o
    # mesmo mp4 da parte 1 da historia 34, recusado as 01:35, foi assistido
    # 4 de 4 vezes as 23:55.
    for video, roteiro, laudo in segunda_chance:
        if minutos_ate_fechar(_relogio(), janela) < margem:
            break
        try:
            veredito = parecer.pedir(video, roteiro, video.parte, laudo=laudo,
                                     headless=headless, provedor=quem_assiste,
                                     log=log)
        except parecer.SemParecer as exc:
            log(f"[auto] {video.id}: o {quem_assiste} nao assistiu de novo "
                f"({exc}); fica NAO ASSISTIDO.")
            continue
        situacao = parecer.situacao(veredito)
        if situacao != parecer.NAO_ASSISTIDO:
            nao_assistidos -= 1
            aprovados += 1 if situacao == parecer.SITUACAO_APROVADO else 0
    if revisados:
        log(f"[auto] revisei {revisados} video(s) do estoque de madrugada; "
            f"{aprovados} aprovado(s) assistindo"
            + (f", {nao_assistidos} so pela folha (NAO ASSISTIDOS)"
               if nao_assistidos else "") + ".")
    return {"revisados": revisados, "aprovados": aprovados,
            "nao_assistidos": nao_assistidos, "pulados": pulados}


def _trabalhar(config: dict, headless: bool, log) -> dict:
    from .controller import Pipeline

    pipeline = Pipeline()
    janela = config.get("janela_pesada")
    if janela:
        sobra = minutos_ate_fechar(_relogio(), janela)
        if sobra < float(config.get("minutos_minimos") or 90):
            log(f"[auto] faltam {sobra:.0f} min para a janela fechar. Nao "
                "comeco trabalho pesado: ele invadiria a hora do silencio.")
            return {"feito": "nada", "motivo": "sem tempo na janela"}
    if config.get("servico_do_dia"):
        _servico_do_dia(config, headless, log)
    if janela and config.get("revisar_estoque_a_noite", True):
        # A chave guarda o nome antigo (era so de madrugada); hoje vale para
        # qualquer janela pesada: parecer do Gemini no que ainda nao foi
        # olhado, antes de consertar e de criar.
        try:
            revisar_estoque(config, headless=headless, log=log)
        except Exception as exc:                               # noqa: BLE001
            log(f"[auto] a revisao do estoque falhou: "
                f"{type(exc).__name__}: {exc}")

    if config.get("retomar_incompletas", True):
        pendentes = incompletas()
        # ROTEIRO PELA METADE VEM PRIMEIRO, e nao vai para `_terminar`: ele
        # gera imagem e video, e fazer isso numa serie truncada seria fabricar
        # exatamente o que nao pode ir ao ar. Ela precisa das PARTES QUE
        # FALTAM antes de qualquer outra coisa.
        truncadas = [p for p in pendentes if p.get("partes_sem_texto")]
        if truncadas:
            alvo = truncadas[0]
            faltam = alvo["partes_sem_texto"]
            log(f"[auto] {alvo['historia_id']} esta pela METADE: falta o "
                f"texto das partes {faltam}. Retomo antes de qualquer imagem "
                "— serie truncada nao pode virar video.")
            return _retomar_texto(pipeline, alvo["historia_id"], faltam,
                                  headless, log,
                                  guarda=_guarda_da_grade(config, log))
        if pendentes:
            alvo = pendentes[0]
            log(f"[auto] terminando {alvo['historia_id']} antes de criar "
                f"outra: {alvo['imagens_faltando']} imagem(ns) e "
                f"{len(alvo['partes_sem_video'])} video(s) pendentes.")
            return _terminar(pipeline, alvo["historia_id"], headless, log,
                             criada=False, guarda=_guarda_da_grade(config, log))

    # CONSERTAR VEM ANTES DE CRIAR, e a ordem e a coisa toda. Um video
    # barrado ja custou roteiro, imagens e render; recuperar ele e mais
    # barato do que fabricar outro do zero. E, sem isto, o freio abaixo
    # nunca mais fecharia: ele agora conta APROVADOS, entao um barrado que
    # ninguem conserta faz a maquina produzir sem parar para cobrir um
    # buraco que continua ali.
    from . import reparo
    conserto = reparo.rodada(limite=int(config.get("reparos_por_rodada") or 2),
                             headless=headless, log=log)
    if conserto["barrados"]:
        log(f"[auto] {conserto['consertados']} de {conserto['barrados']} "
            "video(s) barrado(s) consertados.")
        if conserto["insistentes"]:
            log(f"[auto] desisti de {len(conserto['insistentes'])}: "
                + ", ".join(conserto["insistentes"][:3]))

    # O FREIO, e ele aperta MUITO mais desde 10/09/2026. Antes o teto era 45
    # videos (uns 5 dias e meio) e a ideia era ter reserva. O pedido dele
    # mudou a doutrina: "quero sempre ter a gordura de apenas UM DIA em tudo,
    # mas quero que essa gordura seja totalmente NOVA".
    #
    # E a leitura certa. Estoque grande parece seguranca e e o contrario: ele
    # e feito com o molde de HOJE e sai no ar semanas depois, quando o molde
    # ja mudou — foi assim que 38 dias de video do Gemini Flash seguraram as
    # melhorias de 08/09 na fila. Gordura de um dia significa que o que sai
    # amanha foi feito com o que se aprendeu hoje.
    if config.get("so_consertar"):
        # Modo dia sem falta de video: consertar e tudo o que se faz.
        return {"feito": "nada", "motivo": "so consertar",
                "consertados": conserto.get("consertados", 0)}
    teto = teto_de_estoque(config)
    if teto:
        estoque = dias_de_estoque_novo()
        if estoque >= teto:
            # A lista so e aberta abaixo do TETO DURO: acima dele a resposta
            # ja e "nao cria", e abrir o catalogo a toa custa um ffprobe por
            # video.
            falta = (falta_serie(config, aprovados_no_estoque())
                     if estoque < teto_duro(config) else None)
            if not falta:
                # "teto: 20 = um dia de grade" ficou errado em 15/09/2026,
                # quando a gordura passou a dois dias (`dias_de_gordura`).
                log(f"[auto] ja ha {estoque} video(s) novo(s) na fila "
                    f"(teto: {teto}). Nao crio mais ate baixar.")
                return {"feito": "nada", "motivo": "estoque cheio",
                        "estoque": estoque}
            # A RODADA CRIA UMA HISTORIA SO, entao este gatilho nunca da mais
            # de uma criacao extra por rodada.
            log(f"[auto] estoque cheio em PARTES ({estoque}/{teto}), mas "
                f"{falta['motivo']}: crio mais uma.")
            _registrar_gatilho_de_serie(falta)

    # A HISTORIA NOVA E UM PASSO NOVO: nao comeca perto de uma postagem
    # (a postagem abre os mesmos navegadores e disputa a maquina).
    guarda = _guarda_da_grade(config, log)
    if guarda is not None and not guarda():
        return {"feito": "nada", "motivo": "sem tempo na janela"}
    if janela:
        sobra = minutos_ate_fechar(_relogio(), janela)
        precisa = float(config.get("minutos_por_historia") or 240)
        if sobra < precisa:
            log(f"[auto] faltam {sobra:.0f} min para a janela fechar e uma "
                f"historia leva ~{precisa:.0f}. Nao comeco outra: ela "
                "invadiria a hora do silencio.")
            return {"feito": "nada", "motivo": "sem tempo na janela"}
    escritores = provedores_do_roteiro(config)
    tipo = tipo_mais_magro()
    partes = partes_da_proxima(tipo, config)
    log("[auto] criando historia nova"
        + (f" do tipo {tipo}" if tipo else "")
        + f" via {' -> '.join(escritores)} "
        f"({partes} partes de {config.get('cenas_por_parte')} cenas)...")
    try:
        criada = pipeline.gerar(
            provedor=escritores[0], provedores=escritores, tipo=tipo or None,
            partes=partes,
            cenas_por_parte=int(config.get("cenas_por_parte") or 14),
            tema=(config.get("tema") or None),
            headless=headless, log=log)
    except Exception as exc:                                   # noqa: BLE001
        log(f"[auto] o roteiro FALHOU: {type(exc).__name__}: {exc}")
        return {"feito": "nada", "motivo": "roteiro falhou", "erro": str(exc)}

    historia_id = criada["historia_id"]
    log(f"[auto] {historia_id}: {criada['partes']} parte(s), "
        f"{criada['cenas']} cenas — {criada.get('titulo', '')}")

    # A CONFERENCIA DE LINGUAGEM VEM ANTES DAS IMAGENS, que e onde o dinheiro
    # e o tempo vao (84 imagens, ~40 min de PicassoIA, depois ~1h de render).
    # Descobrir na hora de publicar que a historia nao pode ir ao ar seria
    # pagar tudo isso para nada.
    from ..roteiro import linguagem
    from ..roteiro import roteiro as R
    achados = linguagem.conferir(R.carregar(historia_id))
    for linha in linguagem.resumo(achados):
        log(f"[linguagem] {linha}")
    if achados["pare"]:
        log(f"[auto] {historia_id}: NAO vou gerar imagem. O assunto derruba o "
            "video pelo que ele e, nao pela palavra — e um strike custa o "
            "canal, nao um video.")
        return {"feito": "nada", "motivo": "historia impublicavel",
                "historia_id": historia_id,
                "erro": "; ".join(linguagem.resumo(achados))[:300]}
    return _terminar(pipeline, historia_id, headless, log, criada=True,
                     guarda=guarda)


def estoque_por_tipo(aprovados=None) -> dict:
    """`{tipo: partes aprovadas na fila}` para os tipos do config.

    Tipo sem nada na fila aparece com 0 — e e justamente o que a criacao
    precisa ver. Historia de antes dos tipos entra pelo molde (quebrada ->
    favela). Nunca levanta.
    """
    from ..roteiro import roteiro as R
    from ..roteiro import serie as S

    try:
        config = S.carregar_config()
        saida = {nome: 0 for nome in S.tipos(config)}
    except Exception:                                          # noqa: BLE001
        return {}
    if aprovados is None:
        try:
            aprovados = aprovados_no_estoque()
        except Exception:                                      # noqa: BLE001
            return saida
    roteiros: dict = {}
    for video in aprovados:
        fonte = getattr(video, "fonte_id", "")
        if fonte not in roteiros:
            try:
                roteiros[fonte] = R.carregar(fonte)
            except Exception:                                  # noqa: BLE001
                roteiros[fonte] = {}
        tipo = S.tipo_da_historia(roteiros[fonte], config)
        if tipo in saida:
            saida[tipo] += 1
    return saida


def tipo_mais_magro(estoque: dict | None = None) -> str:
    """O tipo com MENOS partes aprovadas na fila; `""` sem tipos no config.

    Empate: a ordem do config decide (favela, normal, babaca), para a
    escolha ser previsivel e testavel.
    """
    estoque = estoque_por_tipo() if estoque is None else estoque
    if not estoque:
        return ""
    return min(estoque, key=lambda nome: (estoque[nome],
                                          list(estoque).index(nome)))


def partes_da_proxima(tipo: str, config: dict, rng=None) -> int:
    """Partes da proxima historia: sorteadas no tipo que pede, senao a agenda."""
    padrao = int(config.get("partes") or 6)
    if not tipo:
        return padrao
    from ..roteiro import serie as S
    try:
        return S.partes_do_tipo(tipo, padrao, rng=rng)
    except Exception:                                          # noqa: BLE001
        return padrao


def teto_por_historia(config: dict | None = None) -> int:
    """Partes da MESMA historia por dia no perfil (decisao do Adrian,
    17/09/2026, valendo para tudo). O publicador aplica; aqui ele so entra
    na conta de quantas series precisam estar prontas."""
    config = config if config is not None else carregar()
    return max(1, int(config.get("teto_por_historia_no_dia") or 2))


def series_minimas(config: dict | None = None) -> int:
    """Quantas SERIES distintas a grade precisa por dia: horarios / teto."""
    import math
    from builds import grade
    return math.ceil((len(grade.HORAS) or 8) / teto_por_historia(config))


_PARTE_NO_ID = re.compile(r":p(\d+)$")


def _parte_do_video(video) -> int | None:
    """O numero da parte: `video.parte`, ou o `pNN` no fim do id."""
    try:
        parte = int(getattr(video, "parte", 0) or 0)
    except (TypeError, ValueError):
        parte = 0
    if parte > 0:
        return parte
    achado = _PARTE_NO_ID.search(str(getattr(video, "id", "") or ""))
    return int(achado.group(1)) if achado else None


def partes_publicadas(publicados=None) -> dict:
    """`{historia_id: {partes no ar}}`, em QUALQUER destino — como a fila.

    `publicados` sao linhas do ledger; sem elas, le o ledger (so leitura).
    Conta so o que `builds.publicar.metricas.publicado` aceita. Nunca levanta:
    ledger ilegivel vira "nada publicado".
    """
    if publicados is None:
        try:
            from ..publicar import serie
            publicados = serie.publicados()
        except Exception:                                      # noqa: BLE001
            publicados = []
    saida: dict = {}
    for linha in publicados or ():
        try:
            if not _publicado(linha):
                continue
            vid = str(linha.get("video_id") or "")
        except Exception:                                      # noqa: BLE001
            continue
        achado = _PARTE_NO_ID.search(vid)
        if vid.startswith("historia_") and achado:
            saida.setdefault(vid.split(":")[0], set()).add(
                int(achado.group(1)))
    return saida


def series_elegiveis(aprovados: list, publicados=None,
                     teto_no_dia: int = 2) -> dict | None:
    """O que as series aprovadas entregam num DIA. `None` = nao sei contar.

    `{"elegiveis", "capacidade", "distintas", "por_serie"}`. Uma serie so
    entrega se a PROXIMA parte dela (a menor que ainda nao foi ao ar) esta
    aprovada: a ordem das partes e sagrada, e a parte barrada segura as
    seguintes (`postar.proxima_historia`). E entrega no maximo `teto_no_dia`
    partes, as que vem EM SEGUIDA aprovadas.

    POR QUE (27/09/2026): o gatilho contava series DISTINTAS com parte
    aprovada. Havia 6 e o `postar.py` avisou 150 vezes no dia "so 4 serie(s)
    elegivel(is) hoje, e o dia precisa de 5": serie com a proxima parte
    barrada tem partes na fila e nao entrega nenhuma.
    """
    teto_no_dia = max(1, int(teto_no_dia or 1))
    aprovadas: dict = {}
    for video in aprovados or ():
        fonte = str(getattr(video, "fonte_id", "") or
                    str(getattr(video, "id", "")).split(":")[0])
        parte = _parte_do_video(video)
        if not fonte.startswith("historia_") or not parte:
            # NAO SEI CONTAR: sem a fonte e a parte de todos, "poucas series"
            # seria chute — e o erro barato aqui e nao criar.
            return None
        aprovadas.setdefault(fonte, set()).add(parte)
    no_ar = partes_publicadas(publicados)
    por_serie, capacidade, elegiveis = {}, 0, 0
    for fonte in sorted(aprovadas):
        feitas = no_ar.get(fonte, set())
        proxima = 1
        while proxima in feitas:
            proxima += 1
        corrida, n = 0, proxima
        while corrida < teto_no_dia:
            if n in feitas:
                n += 1
            elif n in aprovadas[fonte]:
                corrida += 1
                n += 1
            else:
                break
        por_serie[fonte] = {"proxima": proxima, "entrega": corrida}
        capacidade += corrida
        elegiveis += 1 if corrida else 0
    return {"elegiveis": elegiveis, "capacidade": capacidade,
            "distintas": len(aprovadas), "por_serie": por_serie}


def falta_serie(config: dict, aprovados: list,
                publicados=None) -> dict | None:
    """`{motivo, series, minimo, teto_duro, ...}` quando faltam SERIES; senao
    None.

    O freio conta PARTES, e com o teto por historia isso nao basta: 20 partes
    de 3 series enchem o teto (20) e so alimentam 6 horarios por dia. A
    criacao e liberada quando as series ELEGIVEIS nao enchem o dia (ver
    `series_elegiveis`: proxima parte aprovada, teto de 2 por dia, ordem das
    partes), com um TETO DURO de partes (o teto de sempre + uma serie
    inteira), para series longas nao virarem producao sem fim.

    `publicados` sao linhas do ledger; sem elas, le o ledger.
    """
    teto = teto_de_estoque(config)
    if not teto:
        return None
    aprovados = list(aprovados or ())
    duro = teto_duro(config)
    if len(aprovados) < teto or len(aprovados) >= duro:
        # Abaixo do teto o freio de partes ja cria; acima do duro, nada cria.
        return None
    por_dia = teto_por_historia(config)
    conta = series_elegiveis(aprovados, publicados, por_dia)
    if conta is None:
        return None
    minimo = series_minimas(config)
    horarios = minimo * por_dia
    try:
        from builds import grade
        horarios = len(grade.HORAS) or horarios
    except Exception:                                          # noqa: BLE001
        pass
    if conta["capacidade"] >= horarios:
        return None
    return {"motivo": (f"so {conta['elegiveis']} serie(s) elegivel(is) de "
                       f"{conta['distintas']} com parte aprovada: elas cobrem "
                       f"{conta['capacidade']} de {horarios} horario(s) do "
                       f"dia (teto de {por_dia} por serie), a grade precisa "
                       f"de {minimo}"),
            "series": conta["elegiveis"], "distintas": conta["distintas"],
            "capacidade": conta["capacidade"], "horarios": horarios,
            "minimo": minimo, "teto_duro": duro}


def teto_duro(config: dict) -> int:
    """O teto de partes + uma serie inteira: o limite do gatilho de series."""
    return teto_de_estoque(config) + int(config.get("partes") or 6)


def _registrar_gatilho_de_serie(falta: dict) -> None:
    """No diario, para o relatorio saber POR QUE a historia nasceu."""
    try:
        from builds import atividade
        atividade.registrar(
            "estudio", atividade.LOG,
            f"series < {falta['minimo']}: {falta['motivo']}; criacao extra "
            f"(teto duro {falta['teto_duro']} partes)",
            "historias", etapa="criacao.series")
    except Exception:                                          # noqa: BLE001
        pass


def provedores_do_roteiro(config: dict) -> list:
    """A ordem de queda de quem escreve (`config/llm.json`, papel roteiro).

    Sem o arquivo, vale o `provedor` da agenda, como era antes da troca.
    """
    from ..llm import papeis

    lista = papeis.provedores(papeis.ROTEIRO)
    if not (papeis.ARQUIVO.is_file() and lista):
        lista = [str(config.get("provedor") or "gemini")]
    return lista


def _retomar_texto(pipeline, historia_id: str, faltam: list,
                   headless: bool, log, *, guarda=None) -> dict:
    """Escreve as partes que faltam e so entao segue para imagem e video."""
    from ..roteiro import gerar as G
    from ..roteiro import roteiro as R

    from ..llm import papeis

    config = carregar()
    # A historia continua com QUEM a comecou (o estilo e dele); se ele falhar,
    # a mesma ordem de queda da criacao assume.
    try:
        gravado = R.carregar(historia_id).get("provedor")
    except Exception:                                          # noqa: BLE001
        gravado = None
    ordem = papeis.com_preferido(gravado, provedores_do_roteiro(config))
    try:
        G.escrever_serie(ordem, historia_id=historia_id,
                         headless=headless, log=log)
    except Exception as exc:                                   # noqa: BLE001
        # A retomada falha pelo mesmo motivo que a escrita falhou (limite de
        # uso, rede). Ela nao pode derrubar a rodada: a proxima tenta de novo,
        # e ate la a historia continua fora da fila de publicacao.
        log(f"[auto] a retomada de {historia_id} nao foi ({exc}).")
        _registrar_erro(f"retomada de {historia_id}: {exc}")
        return {"feito": "nada", "motivo": f"retomada falhou: {exc}"[:200],
                "historia_id": historia_id, "erro": str(exc)[:300]}
    if R.partes_que_faltam(R.carregar(historia_id)):
        return {"feito": "texto", "historia_id": historia_id,
                "motivo": "retomada parcial; o proximo disparo continua"}
    return _terminar(pipeline, historia_id, headless, log, criada=False,
                     guarda=guarda)


def _guarda_da_grade(config: dict, log):
    """A pergunta "posso comecar o proximo passo?" para quem so tem um log.

    `None` quando o config nao tem `folga_da_grade` (testes, quem roda na
    mao): ai nao se espera nada, como sempre foi.
    """
    if not config.get("folga_da_grade"):
        return None
    return lambda: esperar_a_grade(config, log)


def _terminar(pipeline, historia_id: str, headless: bool, log,
              *, criada: bool, guarda=None) -> dict:
    """Imagens que faltam e depois os videos. Cada etapa reporta o que deu.

    `guarda()` roda antes de cada render de parte (cada uma e um passo de
    ~6 min de CPU): espera a postagem que estiver perto e devolve False se a
    janela fechou — ai as partes que faltam ficam para o proximo disparo.
    """
    from ..imagens import fila
    from ..roteiro import roteiro as R

    roteiro_agora = R.carregar(historia_id)
    resultado = {"feito": "historia", "historia_id": historia_id,
                 "criada": criada, "erros": [],
                 # O aviso do Telegram precisa contar o que saiu, nao so que
                 # saiu: titulo e contagem sao o que faz a mensagem valer a
                 # notificacao no celular.
                 "titulo": roteiro_agora.get("titulo") or "",
                 "partes": len(roteiro_agora.get("partes") or []),
                 "cenas": roteiro_agora.get("total_cenas") or 0}

    faltam = fila.resumo(historia_id)["faltam"]
    if faltam:
        log(f"[auto] {historia_id}: gerando {faltam} imagem(ns)...")
        try:
            imagens = pipeline.imagens(historia_id, headless=headless, log=log)
            resultado["imagens"] = imagens
            for erro in imagens.get("erros") or []:
                resultado["erros"].append(f"imagem: {erro}")
        except Exception as exc:                               # noqa: BLE001
            log(f"[auto] as imagens FALHARAM: {type(exc).__name__}: {exc}")
            resultado["erros"].append(f"imagens: {exc}")
            # Sem imagem nao ha video que preste: para aqui e deixa o proximo
            # disparo retomar de onde parou.
            return resultado

    roteiro = R.carregar(historia_id)
    partes = [int(p["n"]) for p in (roteiro.get("partes") or [])]
    serie = bool(roteiro.get("serie")) and len(partes) > 1
    # PARTE COM IMAGEM FALTANDO NAO RENDERIZA. O render nao se recusa a rodar
    # sem imagem: ele desenha um cartao tipografico no lugar e entrega um mp4
    # que parece pronto. Medido em 08/09/2026, na historia 10: a cena 1 da
    # parte 1 — o GANCHO — estourou os 600 s do PicassoIA, e o video sairia
    # com um cartao de texto no primeiro segundo, que e onde a pessoa decide
    # ficar. Deixar para a rodada seguinte custa horas; publicar assim custa o
    # video. A `historia_00005` ja tinha passado por isso sem ninguem ver.
    faltando = {int(p["parte"]): p["faltam"]
                for p in fila.resumo_por_parte(historia_id, roteiro)
                if p["faltam"]}
    for n in partes:
        nome = f"final_celular_p{n:02d}.mp4" if serie else "final_celular.mp4"
        if (OUTPUTS / historia_id / nome).is_file():
            continue
        if n in faltando:
            log(f"[auto] parte {n}: {faltando[n]} imagem(ns) faltando; nao "
                "renderizo agora — o proximo disparo tenta as imagens de novo.")
            resultado["erros"].append(
                f"parte {n}: {faltando[n]} imagem(ns) faltando, video adiado")
            continue
        if guarda is not None and not guarda():
            log(f"[auto] parte {n}: a janela do trabalho pesado fechou; o "
                "render fica para o proximo disparo.")
            resultado["erros"].append(
                f"parte {n}: render adiado, a janela fechou")
            continue
        log(f"[auto] {historia_id}: renderizando a parte {n}...")
        try:
            pipeline.render(historia_id, parte=n, log=log)
        except Exception as exc:                               # noqa: BLE001
            log(f"[auto] a parte {n} FALHOU: {type(exc).__name__}: {exc}")
            resultado["erros"].append(f"parte {n}: {exc}")

    from . import conferir as C
    for linha in C.partes_da_historia(historia_id):
        for erro in linha["erros"]:
            log(f"[auto] CONFERIR parte {linha['parte']}: {erro}")
            resultado["erros"].append(f"conferir parte {linha['parte']}: {erro}")
    log(f"[auto] {historia_id}: rodada encerrada"
        + (f" com {len(resultado['erros'])} problema(s)."
           if resultado["erros"] else " sem problema."))
    return resultado
