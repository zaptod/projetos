# -*- coding: utf-8 -*-
"""A rodada noturna do canal de builds: duelos ate o teto, depois o worker.

POR QUE EXISTE (27/09/2026). O canal de builds publicou ~20 videos por dia
ate 20/09 e depois ZERO em 22, 23, 25 e 26/09. Nao era a publicacao: era o
estoque. No Agendador havia 14 tarefas `Historias_auto_*` e 10
`NeuralFights_postar_*` — e nenhuma que GERASSE build ou duelo. Criar video
de builds dependia de alguem lembrar de rodar o comando.

O formato que a rodada produz e o DUELO, porque e o que o dado manda: medido
em 27/09/2026, duelo 51,5% assistido e 78 views medianas, contra build
25,4%/37 e estreia 10,7%/25 — e e o mais barato (~4,3 min ponta a ponta,
nenhuma chamada de IA). A cota da grade (4 de 8) tambem e dele.

QUATRO CUIDADOS, cada um vindo de uma coisa que ja quebrou:

  O ESTOQUE PASSA PELO MESMO FUNIL DA ESCOLHA. Contador que nao passa por ele
  ja anunciou "2 dias de gordura" com a fila vazia. Aqui um duelo so conta se
  a publicacao o escolheria: nao publicado, sem pendencia e com titulo livre
  (a guarda de titulo repetido fecha desde 17/09).

  NADA PESADO ENTRE :25 E :55. E a janela em que a grade publica. Um duelo so
  comeca se cabe inteiro antes de :25 (e antes de a janela pesada fechar).

  UMA RODADA POR VEZ, ENTRE PROCESSOS. Cada hora e uma tarefa, cada tarefa e
  um processo, e a trava e um arquivo. `travas.trava` e REENTRANTE no mesmo
  processo (de proposito) — por isso o teste da trava usa subprocesso de
  verdade, e nunca "segura a trava e chama rodar() no mesmo processo".

  O `print` NAO VAI PARA CONSOLE. No console que o Agendador da e ninguem
  esvazia, escrever trava o processo (08/09/2026). Toda a saida da rodada vai
  para o diario do dia, com hora.

O p1 sai do RODIZIO (`arena/rodizio.py`), nao do "ultimo criado": 5 dos 8
duelos de 27/09 eram do mesmo personagem.

O LOTE SEMANAL DE DIA (decisoes do Adrian em 30/09/2026, Grimorio
`geral/lote-*`). O trabalho pesado saiu da madrugada por causa do barulho:
janela 07h-22h; SEG-QUA (`dias_de_lote`; a quarta desde 01/10/2026, no
`builds/lote-builds-quarta`: fecha o lote se a terca nao der) a rodada produz
ate cobrir a proxima segunda 07h mais o piso; QUI-DOM so repoem abaixo do
piso de 20 videos (2 dias); ESTOQUE ZERO de madrugada libera tudo (o canal
nao para); a madrugada antiga continua (`madrugada_na_transicao`) ate o
esquema de dia rodar validado um dia; o 1o lote e seg 05/10. A janela da
grade deixou de ser ":25 a :55 de toda hora" e virou a meia hora em volta de
cada um dos 10 horarios (`folga_da_grade`, inclusive 12:07 e 17:57). Quem
decide o que a rodada faz e `planejar`, ANTES da trava — o mesmo desenho de
`contos.pipeline.agenda.planejar`.

O ESTOQUE QUE DECIDE E O DA PUBLICACAO (`contar_estoque`): o funil de
`postar._builds_prontos`, que e literalmente `pendentes_por_canal()["builds"]`.
As historias erraram isso no mesmo dia (a agenda contou 27, o `--ver` 8).
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"
CONFIG = RAIZ / "config" / "geracao.json"
LOGS = OUTPUTS / "_logs"

TRAVA = "builds__gerar"

# O PADRAO E O ESQUEMA ANTIGO (madrugada 01h-06h, :25 a :55 proibido): e o
# que vale se `geracao.json` sumir ou ficar ilegivel — nada pesado de dia sem
# config que o diga. Sem `dias_de_lote` o modo e "livre" (ver `modo_da_hora`).
PADRAO = {
    "ativo": True,
    "janela_pesada": {"inicio": 1, "fim": 6},
    "grade_proibida": {"de": 25, "ate": 55},
    "horas": [1, 2, 3, 4, 5],
    "minuto": 2,
    "dias_de_gordura": 2,
    "minutos_por_duelo": 5,
    "minutos_por_build": 15,
    "minutos_por_imagem": 8,
    "minutos_por_payoff": 18,
    "maximo_de_duelos_por_rodada": 6,
    "maximo_de_builds_por_rodada": 1,
    "builds": True,
    "worker": True,
}

# A cota de queda, igual a `COTA_PADRAO` da publicacao. Duplicada de
# proposito: `builds` nao importa `ferramentas/`, e o valor vivo vem do
# `publicacao.json` (que e meu) — esta so vale se o bloco sumir.
COTA_DE_QUEDA = {"duelo": 4, "build": 3, "estreia": 1, "torneio": 0}

# Duas falhas seguidas de duelo param a rodada: a terceira quase sempre
# falharia pelo mesmo motivo, e cada uma custa minutos de janela.
FALHAS_SEGUIDAS = 2


def carregar(caminho: Path | None = None) -> dict:
    """O config com os padroes por baixo. Chave `_...` e comentario."""
    config = dict(PADRAO)
    try:
        with open(caminho or CONFIG, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
        if isinstance(dados, dict):
            config.update({k: v for k, v in dados.items()
                           if not str(k).startswith("_")})
    except (OSError, ValueError):
        pass
    return config


# ------------------------------------------------------------------ relogio
def na_janela(hora: int, janela: dict | None) -> bool:
    """A hora cheia esta dentro da janela pesada? Atravessa a meia-noite."""
    if not janela:
        return True
    inicio, fim = int(janela["inicio"]) % 24, int(janela["fim"]) % 24
    if inicio == fim:
        return True
    if inicio < fim:
        return inicio <= int(hora) < fim
    return int(hora) >= inicio or int(hora) < fim


def na_grade(minuto: int, proibida: dict | None) -> bool:
    """Este minuto cai na janela em que a grade publica (:25 a :55)?"""
    if not proibida:
        return False
    de, ate = int(proibida["de"]) % 60, int(proibida["ate"]) % 60
    if de <= ate:
        return de <= int(minuto) < ate
    return int(minuto) >= de or int(minuto) < ate


def perto_da_grade(instante: datetime, folga: dict | None):
    """O horario da grade (datetime) a menos de `folga_da_grade` do instante.

    `None` quando nao ha postagem perto (ou nao ha folga no config). Olha a
    grade de ontem, hoje e amanha, para as 23:50 enxergarem o 00:37. Os
    horarios vem de `builds.grade.GRADE`, com o minuto de cada um: 12:07 e
    17:57 nao sao :37, e a regra velha (":25 a :55") nao os protegia.
    Intervalo fechado dos dois lados, como em `agenda.postagem_perto`.
    """
    if not folga:
        return None
    from .. import grade

    antes = timedelta(minutes=int(folga.get("antes", 15)))
    depois = timedelta(minutes=int(folga.get("depois", 15)))
    for delta in (-1, 0, 1):
        dia = (instante + timedelta(days=delta)).date()
        for hora, minuto in grade.GRADE:
            post = datetime(dia.year, dia.month, dia.day, hora, minuto)
            if post - antes <= instante <= post + depois:
                return post
    return None


def fora_da_grade(instante: datetime, config: dict) -> bool:
    """Este instante esta livre das postagens? As duas regras, se houver:
    a velha (`grade_proibida`, minuto :25 a :55 de toda hora) e a do lote
    (`folga_da_grade`, a meia hora em volta de cada horario)."""
    if na_grade(instante.minute, config.get("grade_proibida")):
        return False
    return perto_da_grade(instante, config.get("folga_da_grade")) is None


def cabe(agora: datetime, minutos: float, config: dict,
         limite: datetime | None = None) -> bool:
    """Um trabalho de `minutos` comecando AGORA termina sem encostar em nada?

    Confere minuto a minuto (o trabalho mais longo e de 18 min): cada instante
    tem de estar na janela pesada, fora da grade e antes do `limite` da
    rodada (se houver). O ultimo instante conta — terminar em cima da borda
    ja e encostar.
    """
    janela = config.get("janela_pesada")
    passos = max(1, int(math.ceil(float(minutos))))
    for i in range(passos + 1):
        instante = agora + timedelta(minutes=min(float(minutos), i))
        if not na_janela(instante.hour, janela):
            return False
        if not fora_da_grade(instante, config):
            return False
        if limite is not None and instante >= limite:
            return False
    return True


def quantos_cabem(agora: datetime, minutos: float, config: dict,
                  maximo: int = 50, limite: datetime | None = None) -> int:
    """Quantos trabalhos de `minutos`, um atras do outro, cabem a partir de
    AGORA."""
    n = 0
    while n < maximo and cabe(agora + timedelta(minutes=n * float(minutos)),
                              minutos, config, limite):
        n += 1
    return n


def fim_da_folga(agora: datetime, config: dict,
                 horizonte_min: int = 24 * 60,
                 limite: datetime | None = None) -> datetime:
    """O primeiro minuto, a partir de AGORA, em que nada pode estar rodando
    (postagem perto, fim da janela pesada ou fim da rodada). E dele que sai o
    prazo que o worker recebe: prazo = fim da folga - quanto um job leva."""
    janela = config.get("janela_pesada")
    base = agora.replace(second=0, microsecond=0)
    for i in range(horizonte_min + 1):
        instante = base + timedelta(minutes=i)
        if instante < agora:
            continue
        if (not na_janela(instante.hour, janela)
                or not fora_da_grade(instante, config)
                or (limite is not None and instante >= limite)):
            return instante
    return base + timedelta(minutes=horizonte_min)


def minutos_do_job(provedor: str, config: dict) -> float:
    """Quanto um job DAQUELE provedor leva, medido.

    Imagem do PicassoIA: 3,3 / 4,5 / 6 min na madrugada de 28/09/2026 (a de
    6 teve duas tentativas falhas dentro). Payoff do Digen, do envio ao fim
    (inclui o re-render da build, que acontece no ultimo clipe): 12, 15 e
    12,5 min nas generation_00082/83/84. Um orcamento so (8 min) deixava o
    payoff comecar as :16 e terminar depois de :25.
    """
    if provedor == "digen":
        return float(config.get("minutos_por_payoff", 18))
    return float(config.get("minutos_por_imagem",
                            config.get("minutos_por_job_do_worker", 8)))


# ------------------------------------------------------------------ o lote
#
# DECISOES DO ADRIAN, 30/09/2026 (Grimorio `geral/lote-*`), cada uma uma
# chave de `config/geracao.json`, nunca um numero no codigo:
#
#   janela_pesada          07h-22h: trabalho pesado so de dia
#   dias_de_lote           seg-qua: as builds da semana saem em lote (a
#                          quarta desde 01/10, `builds/lote-builds-quarta`)
#   alvo_do_lote           o lote cobre ate segunda 07h + o piso
#   piso_de_reposicao      qui-dom so repoem abaixo de 20 (2 dias); a
#                          publicacao le o mesmo numero (`postar.piso_de_alerta`)
#   estoque_zero_libera_a_noite   sem video nenhum, a noite gera: o canal
#                          nao para, mesmo com barulho
#   lote_a_partir_de       o 1o lote e seg 05/10; antes disso dia de lote
#                          se comporta como reposicao
#   madrugada_na_transicao o esquema antigo (01h-06h) continua ate o de dia
#                          rodar validado um dia inteiro; apagar desliga
#   folga_da_grade         nada roda na meia hora em volta de cada horario
#   rodada_de_dia          quanto uma rodada dura (o disparo seguinte
#                          continua) e quanto dela fica para o worker
#   disco_livre_minimo_gb  abaixo disso em `disco_a_vigiar`, nada e gerado
#
# As contas de calendario (`fim_da_cobertura`, `postagens_entre`) sao as da
# agenda das historias, reescritas aqui porque `builds` nao importa `contos`;
# o `postar.estoque_do_lote` usa as de la, e com os mesmos numeros no config
# (segunda, 07h) as duas dao o mesmo alvo.

def dias_de_lote(config: dict) -> set:
    """Os dias da semana do lote (0 = segunda)."""
    return {int(d) % 7 for d in (config.get("dias_de_lote") or [])}


def lote_valendo(config: dict, agora: datetime) -> bool:
    """Hoje e dia de lote? Antes de `lote_a_partir_de`, nao. Data torta NAO
    liga o lote: o erro barato e cair na reposicao, que ainda cria abaixo do
    piso."""
    desde = config.get("lote_a_partir_de")
    if desde:
        try:
            if agora.date() < datetime.strptime(str(desde),
                                                "%Y-%m-%d").date():
                return False
        except ValueError:
            return False
    return agora.weekday() in dias_de_lote(config)


def postagens_entre(inicio: datetime, fim: datetime) -> int:
    """Quantos horarios da grade caem em (inicio, fim]."""
    from .. import grade

    total, dia = 0, inicio.date()
    while dia <= fim.date():
        for hora, minuto in grade.GRADE:
            momento = datetime(dia.year, dia.month, dia.day, hora, minuto)
            if inicio < momento <= fim:
                total += 1
        dia += timedelta(days=1)
    return total


def fim_da_cobertura(config: dict, agora: datetime) -> datetime:
    """Ate quando o lote cobre: a PROXIMA segunda 07h (estritamente depois de
    agora). Na terca e a mesma segunda: se a segunda nao produziu (PC
    desligado), a terca herda a diferenca sozinha."""
    alvo = config.get("alvo_do_lote") or {}
    dia = int(alvo.get("cobrir_ate_o_dia", min(dias_de_lote(config) or {0})))
    hora = int(alvo.get("cobrir_ate_a_hora",
                        (config.get("janela_pesada") or {}).get("inicio", 0)))
    base = agora.replace(hour=hora % 24, minute=0, second=0, microsecond=0)
    base += timedelta(days=(dia % 7 - agora.weekday()) % 7)
    if base <= agora:
        base += timedelta(days=7)
    return base


def piso_de_reposicao(config: dict) -> int:
    """Abaixo disto a reposicao cria. Sem a chave: `dias_de_gordura` x
    horarios da grade (os mesmos 2 dias = 20)."""
    valor = config.get("piso_de_reposicao")
    if valor is None:
        from .. import grade
        return int(max(0.0, float(config.get("dias_de_gordura", 2)))
                   * len(grade.HORAS))
    return max(0, int(valor))


def alvo_do_lote(config: dict, agora: datetime) -> int:
    """Videos que o canal precisa ter AGORA num dia de lote: os horarios da
    grade ate `fim_da_cobertura` mais o piso. Medido com a grade de 10
    horarios: segunda 07:02 = 70 + 20 = 90; terca 07:02 = 80."""
    alvo = config.get("alvo_do_lote") or {}
    total = postagens_entre(agora, fim_da_cobertura(config, agora))
    if alvo.get("mais_o_piso", True):
        total += piso_de_reposicao(config)
    return total


def metas_por_formato(meta: int, config_publicacao: dict | None = None
                      ) -> dict:
    """A meta do canal dividida pela COTA da grade (a mesma que escolhe):
    `ceil(meta x peso / soma)`. Com duelo 4, build 3, estreia 1 e meta 90:
    45, 34 e 12. Formato de cota zero (torneio) nao tem meta."""
    pesos = cota(config_publicacao)
    total = sum(pesos.values())
    if total <= 0 or meta <= 0:
        return {f: 0 for f in ("duelo", "build", "estreia")}
    saida = {}
    for formato in ("duelo", "build", "estreia"):
        saida[formato] = int(math.ceil(meta * pesos.get(formato, 0) / total
                                       - 1e-9))
    return saida


def _livre_gb(caminho: str) -> float:
    import shutil
    return shutil.disk_usage(caminho).free / (1024 ** 3)


def disco_apertado(config: dict) -> str | None:
    """Texto quando o disco vigiado tem menos que o minimo; senao None.
    Plano do lote (30/09/2026): o lote nao comeca com menos de 5 GB no C:.
    Nao conseguir medir nao para nada."""
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


def modo_da_hora(config: dict, agora: datetime) -> str:
    """'livre' | 'lote' | 'reposicao' | 'madrugada' | 'noite'.

    `livre` e o config sem `dias_de_lote` (o PADRAO, os testes antigos, a
    mao): a rodada como era antes do lote — janela, grade e teto de gordura.
    """
    if "dias_de_lote" not in config:
        return "livre"
    janela = config.get("janela_pesada")
    if not janela or na_janela(agora.hour, janela):
        return "lote" if lote_valendo(config, agora) else "reposicao"
    transicao = config.get("madrugada_na_transicao")
    if transicao and na_janela(agora.hour, transicao):
        return "madrugada"
    return "noite"


def _config_de_dia(config: dict) -> dict:
    """Os maximos por rodada de dia (`rodada_de_dia`) no lugar dos da noite."""
    dia = config.get("rodada_de_dia") or {}
    efetivo = dict(config)
    for chave, destino in (("maximo_de_duelos", "maximo_de_duelos_por_rodada"),
                           ("maximo_de_builds", "maximo_de_builds_por_rodada")):
        if dia.get(chave) is not None:
            efetivo[destino] = int(dia[chave])
    return efetivo


def planejar(config: dict, agora: datetime, *, contagem: dict | None = None,
             config_publicacao: dict | None = None) -> dict:
    """O que a rodada faz agora. Nunca gera nada. Roda ANTES da trava.

    Devolve `{modo, fazer, criar, meta, metas, total, por_que, motivo,
    impedimento, limite_min, config}`. `metas` e a meta de cada formato
    (`None` = o teto de gordura de sempre); `config` e o EFETIVO que
    `_trabalhar` recebe; `limite_min` e quanto a rodada dura (`None` = so o
    relogio da janela e da grade manda).

    livre      config sem `dias_de_lote`: a rodada de antes do lote
    lote       seg-qua 07h-22h (`dias_de_lote`; a partir de `lote_a_partir_de`): ate o alvo
    reposicao  os outros dias 07h-22h: cria so abaixo do piso
    madrugada  transicao: o esquema antigo, ate o teto de gordura
    zero       fora da janela com estoque ZERO: libera tudo, ate o piso
    noite      fora de tudo com estoque: nada
    """
    modo = modo_da_hora(config, agora)
    minutos = (config.get("rodada_de_dia") or {}).get("minutos")
    limite_min = float(minutos) if minutos else None
    if modo == "livre":
        return {"modo": modo, "fazer": True, "criar": True, "metas": None,
                "por_que": "config sem lote (o esquema de antes)",
                "motivo": "", "impedimento": None, "limite_min": None,
                "config": config}
    if modo == "madrugada":
        return {"modo": modo, "fazer": True, "criar": True, "metas": None,
                "por_que": "madrugada da transicao (o esquema antigo roda ate "
                           "o de dia ser validado)",
                "motivo": "", "impedimento": None, "limite_min": limite_min,
                "config": {**config,
                           "janela_pesada": config["madrugada_na_transicao"]}}

    if contagem is None:
        contagem = contar_estoque()
    total = int(contagem.get("total", 0))
    piso = piso_de_reposicao(config)

    if modo == "noite":
        janela = config.get("janela_pesada") or {}
        if not (config.get("estoque_zero_libera_a_noite", True)
                and total <= 0):
            return {"modo": modo, "fazer": False, "criar": False,
                    "metas": None, "total": total, "motivo": "fora da janela",
                    "impedimento": None, "limite_min": limite_min,
                    "por_que": (f"fora da janela do trabalho pesado "
                                f"({int(janela.get('inicio', 0)):02d}h as "
                                f"{int(janela.get('fim', 0)):02d}h) e com "
                                f"{total} video(s) no estoque"),
                    "config": config}
        impedido = disco_apertado(config)
        meta = max(1, piso)
        return {"modo": "zero", "fazer": not impedido,
                "criar": not impedido, "meta": meta,
                "metas": metas_por_formato(meta, config_publicacao),
                "total": total, "motivo": "impedido" if impedido else "",
                "impedimento": impedido, "limite_min": limite_min,
                "por_que": ("ESTOQUE ZERO fora da janela: nenhum video para o "
                            "proximo horario; libera tudo (decisao de "
                            "30/09/2026)")
                           + (f", mas {impedido}" if impedido else ""),
                "config": {**_config_de_dia(config), "janela_pesada": None}}

    if modo == "lote":
        meta = alvo_do_lote(config, agora)
        rotulo = f"lote: {total} video(s) para um alvo de {meta}"
    else:
        meta = piso
        rotulo = f"reposicao: {total} video(s), piso {meta}"
    criar = total < meta
    impedido = disco_apertado(config) if criar else None
    if impedido:
        criar = False
    motivos = [rotulo]
    if impedido:
        motivos.append(f"NAO gero: {impedido}")
    elif not criar:
        motivos.append("so o worker")
    return {"modo": modo, "fazer": True, "criar": criar, "meta": meta,
            "metas": (metas_por_formato(meta, config_publicacao) if criar
                      else {"duelo": 0, "build": 0, "estreia": 0}),
            "total": total, "motivo": "impedido" if impedido else "",
            "impedimento": impedido, "limite_min": limite_min,
            "por_que": "; ".join(motivos),
            "config": _config_de_dia(config)}


# ------------------------------------------------------------------ estoque
def cota(config_publicacao: dict | None = None) -> dict:
    if config_publicacao is None:
        from ..publicar import catalogo
        config_publicacao = catalogo.carregar_config()
    bruta = ((config_publicacao or {}).get("grade") or {}).get("mistura")
    if not isinstance(bruta, dict) or not bruta:
        return dict(COTA_DE_QUEDA)
    return {str(k): max(0, int(v)) for k, v in bruta.items()}


def por_dia(formato: str, config_publicacao: dict | None = None,
            horarios: int | None = None) -> float:
    """Quantos horarios do dia a cota da ao formato (duelo 4/8 de 10 = 5,
    build 3/8 de 10 = 3,75)."""
    if horarios is None:
        from .. import grade
        horarios = len(grade.HORAS)
    pesos = cota(config_publicacao)
    total = sum(pesos.values())
    if total <= 0:
        return 0.0
    return horarios * pesos.get(formato, 0) / total


def duelos_por_dia(config_publicacao: dict | None = None,
                   horarios: int | None = None) -> float:
    return por_dia("duelo", config_publicacao, horarios)


def builds_por_dia(config_publicacao: dict | None = None,
                   horarios: int | None = None) -> float:
    return por_dia("build", config_publicacao, horarios)


def teto_de_duelos(config: dict, config_publicacao: dict | None = None,
                   horarios: int | None = None) -> int:
    dias = max(0.0, float(config.get("dias_de_gordura", 0)))
    return int(math.ceil(dias * duelos_por_dia(config_publicacao, horarios)))


def teto_de_builds(config: dict, config_publicacao: dict | None = None,
                   horarios: int | None = None) -> int:
    dias = max(0.0, float(config.get("dias_de_gordura", 0)))
    return int(math.ceil(dias * builds_por_dia(config_publicacao, horarios)))


# O `ferramentas/postar.py`, carregado pelo caminho como a agenda das
# historias o carrega (`contos.pipeline.agenda._postar`): `builds` nao importa
# `ferramentas`, e o numero que decide gerar tem de ser o da publicacao.
POSTAR = RAIZ.parent / "ferramentas" / "postar.py"
_POSTAR_CARREGADO = None


def _postar():
    global _POSTAR_CARREGADO
    if _POSTAR_CARREGADO is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_postar_da_geracao",
                                                      POSTAR)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        _POSTAR_CARREGADO = modulo
    return _POSTAR_CARREGADO


def contar_estoque() -> dict:
    """`{"total", "duelo", "build", "estreia", "torneio", "fonte"}`: o que a
    PUBLICACAO tem para os proximos horarios.

    UMA CONTAGEM SO (30/09/2026). `postar.pendentes_por_canal()["builds"]` e
    `len(postar._builds_prontos())` — o funil da escolha (nao publicado em
    nenhum destino, celular, sem pendencia, titulo livre, som). Aqui a MESMA
    lista, agrupada por formato numa passada so (medir o som custa 0,3-0,65 s
    por video). O `--ver`, o alerta de piso e o `estoque_do_lote` usam esse
    numero; decidir gerar por outro seria o erro das historias em 30/09
    (a agenda contou 27 "aprovados", a publicacao tinha 8).

    Nao deu para carregar a publicacao: cai no funil daqui
    (`estoque_do_formato`, sem a medida de som), e `fonte` diz isso.
    """
    try:
        prontos = list(_postar()._builds_prontos())
        fonte = "publicacao"
    except Exception as exc:                                   # noqa: BLE001
        from ..publicar import catalogo
        prontos = []
        for origem in (catalogo.DUELO, catalogo.BUILD, "estreia", "torneio"):
            prontos.extend(estoque_do_formato(origem))
        fonte = f"geracao (publicacao ilegivel: {type(exc).__name__})"
    saida = {"total": len(prontos), "duelo": 0, "build": 0, "estreia": 0,
             "torneio": 0, "fonte": fonte}
    for video in prontos:
        origem = str(getattr(video, "origem", "") or "")
        saida[origem] = saida.get(origem, 0) + 1
    return saida


def estoque_de_duelos(videos=None, publicados=None) -> list:
    """Os duelos que a publicacao ESCOLHERIA, do mais antigo ao mais novo."""
    from ..publicar import catalogo
    return estoque_do_formato(catalogo.DUELO, videos, publicados)


def estoque_de_builds(videos=None, publicados=None) -> list:
    """Os builds (A e B com titulo proprio) que a publicacao ESCOLHERIA."""
    from ..publicar import catalogo
    return estoque_do_formato(catalogo.BUILD, videos, publicados)


# Pendencia que o WORKER resolve sozinho: imagem, payoff, re-render. Build
# com qualquer outra (estreia impossivel, estreia nao gravada) nao esta "a
# caminho" — e nao pode segurar a geracao de outra.
_PENDENCIA_DO_WORKER = ("identity worker", "(PicassoIA)", "mp4 mais velho")


def builds_em_preparo(videos=None, publicados=None, jobs=None) -> list[str]:
    """As generation_* que VAO entrar no estoque sem ninguem mexer.

    Build nova nasce com pendencia (sem imagem, sem payoff) e so entra na
    fila quando o worker termina — o que pode levar mais de uma rodada,
    porque o PicassoIA e dividido com as historias. Sem contar essas, a
    rodada seguinte veria o estoque igual e geraria OUTRA roleta por hora.
    So conta quem tem job VIVO na fila (pendente, com tentativa sobrando):
    job esgotado nao anda sozinho, e contar ele seria um cemiterio de novo.
    """
    from ..publicar import catalogo, metricas
    if publicados is None:
        publicados = metricas.publicados()
    if videos is None:
        videos = catalogo.listar()
    if jobs is None:
        jobs = jobs_do_worker()
    vivos = {j.get("generation_id") for j in jobs or ()}
    saiu = {linha.get("video_id") for linha in publicados
            if metricas.publicado(linha)}
    preparo = []
    for video in videos:
        if (getattr(video, "origem", "") != catalogo.BUILD
                or getattr(video, "perfil", "") != "celular"
                or getattr(video, "variante", "A") != "A"
                or video.id in saiu):
            continue
        pendencias = list(getattr(video, "pendencias", None) or ())
        if not pendencias or video.fonte_id not in vivos:
            continue
        if all(any(m in p for m in _PENDENCIA_DO_WORKER) for p in pendencias):
            preparo.append(video.fonte_id)
    return sorted(set(preparo))


def estoque_do_formato(origem: str, videos=None, publicados=None) -> list:
    """O que a publicacao ESCOLHERIA daquele formato, do mais antigo ao mais
    novo.

    O mesmo funil de `postar.proximo_build`, com as mesmas funcoes: saiu =
    `metricas.publicado`, titulo = `titulos.chave`. Fica de fora o que ja
    foi ao ar (em qualquer destino), o que tem pendencia e o que tem titulo
    ja publicado. Dois pendentes com o MESMO titulo contam como um: o
    segundo so sairia repetindo o primeiro.
    """
    from ..publicar import catalogo, metricas, titulos
    if publicados is None:
        publicados = metricas.publicados()
    if videos is None:
        videos = catalogo.listar()
    saiu = {linha.get("video_id") for linha in publicados
            if metricas.publicado(linha)}
    no_ar = titulos.ja_publicados(publicados)
    fila, vistos = [], set()
    for video in sorted(videos, key=lambda v: getattr(v, "quando", 0.0)):
        if getattr(video, "origem", "") != origem:
            continue
        if getattr(video, "perfil", "") != "celular":
            continue
        if video.id in saiu or getattr(video, "pendencias", None):
            continue
        chave = titulos.chave(getattr(video, "titulo", ""))
        if titulos.repetido(video.titulo, no_ar) or (chave and chave in vistos):
            continue
        vistos.add(chave)
        fila.append(video)
    return fila


def proximo_do_worker(excluir=()) -> str | None:
    """O provedor do proximo job que o worker CONSEGUE pegar, na ordem dele
    (PicassoIA antes do Digen), pulando `excluir`. Usa o predicado do `claim`
    (`queue.tem_reivindicavel`): payoff esperando imagem nao conta."""
    from ..identity import config as icfg
    from ..identity import provedores, queue
    maximo = int(icfg.settings().get("max_attempts", 3))
    for provedor in provedores.TODOS:
        if provedor in excluir:
            continue
        if queue.tem_reivindicavel(maximo, provedor=provedor):
            return provedor
    return None


def jobs_do_worker() -> list[dict]:
    """Os jobs de identidade que um worker ainda pode fazer andar."""
    from ..identity import config as icfg
    from ..identity import queue
    maximo = int(icfg.settings().get("max_attempts", 3))
    # Build descartada (config/publicacao.json) nao anda: o claim a pula, e
    # conta-la aqui a faria parecer "em preparo" para sempre.
    descartadas = queue.geracoes_descartadas()
    return [j for j in queue.listar()
            if j.get("status") == queue.PENDENTE
            and int(j.get("attempts", 0)) < maximo
            and j.get("generation_id") not in descartadas]


# ------------------------------------------------------------------- diario
class _Diario:
    """`sys.stdout` que grava no diario do dia, com hora, e nunca no console.

    O mesmo remedio das historias (`contos.pipeline.agenda._SaidaNoDiario`),
    escrito aqui porque `builds` nao importa `contos`. O console do Agendador
    nao e esvaziado por ninguem, e o `print` que escreve nele trava para
    sempre; no arquivo ele nunca trava e vira o unico sinal de que a rodada
    esta andando — que e o que o vigia le.
    """

    def __init__(self, destino: Path, eco=None):
        self.destino = Path(destino)
        self.destino.parent.mkdir(parents=True, exist_ok=True)
        self.eco = eco if _e_terminal(eco) else None
        self._resto = ""

    def write(self, texto: str) -> int:
        texto = str(texto)
        if self.eco is not None:
            try:
                self.eco.write(texto)
            except Exception:                                  # noqa: BLE001
                self.eco = None
        # "\r" de barra de progresso vira quebra: senao uma linha acumula o
        # render inteiro e o diario fica ilegivel.
        self._resto += texto.replace("\r", "\n")
        linhas = self._resto.split("\n")
        self._resto = linhas.pop()
        linhas = [l for l in linhas if l.strip()]
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


def _e_terminal(fluxo) -> bool:
    try:
        return bool(fluxo is not None and fluxo.isatty())
    except Exception:                                          # noqa: BLE001
        return False


def diario_do_dia(agora: datetime | None = None) -> Path:
    return LOGS / f"gerar_{(agora or datetime.now()):%Y%m%d}.txt"


def _registrar(status: str, detalhe: str, **extra) -> None:
    """Diario compartilhado (`atividade.jsonl`). Nunca levanta."""
    try:
        from .. import atividade
        atividade.registrar("arena", status, detalhe, "builds", **extra)
    except Exception:                                          # noqa: BLE001
        pass


# ------------------------------------------------------------------ rodada
def _duelo_de_verdade():
    """O gerador real: um `PipelineController` para a rodada inteira."""
    from .controller import PipelineController
    controlador = PipelineController()

    def gerar() -> Path:
        # p1 e p2 ficam para o rodizio de `controller.duelo`.
        return controlador.duelo()
    return gerar


def _build_de_verdade():
    """A roleta inteira (`generate-video`): build, insercao no banco, estreia,
    render e a fila de identidade. O controller e criado so aqui: a rodada
    que nao gera build nao paga o carregamento dele."""
    from .controller import PipelineController
    controlador = {}

    def gerar() -> Path:
        if "c" not in controlador:
            controlador["c"] = PipelineController()
        return controlador["c"].generate()
    return gerar


def _worker_de_verdade(so_provedor: str | None = None,
                       prazo: float | None = None) -> int:
    from ..identity import worker
    return worker.drenar(headless=False, rerender=True, preview=False,
                         so_provedor=so_provedor, prazo=prazo)


def rodar(*, config: dict | None = None, ensaio: bool = False,
          duelos: int | None = None, sem_worker: bool = False,
          relogio=None, gerar_duelo=None, drenar_worker=None,
          jobs=None, estoque=None, proximo=None, tela=None,
          builds: int | None = None, gerar_build=None,
          estoque_builds=None, contagem=None) -> dict:
    """Uma rodada. Devolve o que aconteceu; nunca levanta por conta da tarefa.

    `ensaio`: faz TODAS as conferencias e diz o que faria, sem gerar nada e
    sem escrever no diario compartilhado. E o duble do teste de ponta a
    ponta (tarefa -> .cmd -> python -> trava -> diario) antes de registrar.

    `duelos`: quantos gerar, ignorando o teto (a rodada manual). O relogio
    continua mandando: o que nao couber antes da proxima postagem fica para
    a proxima.

    Os parametros `relogio`, `gerar_duelo`, `drenar_worker`, `jobs`,
    `estoque`, `estoque_builds` e `contagem` (o estoque da publicacao por
    formato, ver `contar_estoque`) existem para os testes trocarem o mundo
    por dubles.
    """
    from .. import travas
    from ..identity import controle

    config = carregar() if config is None else config
    relogio = relogio or datetime.now
    agora = relogio()
    destino = diario_do_dia(agora)
    anterior_out, anterior_err = sys.stdout, sys.stderr
    sys.stdout = _Diario(destino, tela if tela is not None else anterior_out)
    sys.stderr = _Diario(destino, None)
    try:
        return _rodada(config=config, ensaio=ensaio, duelos=duelos,
                       sem_worker=sem_worker, relogio=relogio,
                       gerar_duelo=gerar_duelo, drenar_worker=drenar_worker,
                       jobs=jobs, estoque=estoque, proximo=proximo,
                       travas=travas, controle=controle, builds=builds,
                       gerar_build=gerar_build, estoque_builds=estoque_builds,
                       contagem=contagem)
    finally:
        try:
            sys.stdout.flush()
        except Exception:                                      # noqa: BLE001
            pass
        sys.stdout, sys.stderr = anterior_out, anterior_err


def _contagem_para_o_plano(contagem, estoque, estoque_builds):
    """O estoque que `planejar` recebe. Duble de teste vale; senao a
    publicacao (`contar_estoque`)."""
    if callable(contagem):
        return contagem()
    if contagem is not None:
        return dict(contagem)
    if estoque is not None or estoque_builds is not None:
        # Testes antigos so dublavam as listas por formato.
        duelos = len(estoque()) if estoque else 0
        roletas = len(estoque_builds()) if estoque_builds else 0
        return {"total": duelos + roletas, "duelo": duelos, "build": roletas,
                "estreia": 0, "fonte": "duble"}
    return None


def _rodada(*, config, ensaio, duelos, sem_worker, relogio, gerar_duelo,
            drenar_worker, jobs, estoque, proximo, travas, controle,
            builds=None, gerar_build=None, estoque_builds=None,
            contagem=None) -> dict:
    agora = relogio()
    rotulo = " (ENSAIO: nada e gerado)" if ensaio else ""
    print(f"[noite] disparo das {agora:%H:%M}{rotulo}")

    if not config.get("ativo", True):
        print("[noite] a geracao esta desligada (`ativo: false`). Nada a fazer.")
        return {"feito": "nada", "motivo": "desligada"}
    if controle.pausado_para():
        print("[noite] a pipeline esta PAUSADA (pagina Vila). Saindo.")
        return {"feito": "nada", "motivo": "pausado"}

    # ---- o plano, ANTES da trava (o mesmo desenho da agenda das historias)
    modo = modo_da_hora(config, agora)
    contado = _contagem_para_o_plano(contagem, estoque, estoque_builds)
    if contado is None:
        try:
            contado = contar_estoque()
            print(f"[noite] estoque da publicacao: {contado['total']} "
                  f"video(s) ({contado['duelo']} duelo(s), "
                  f"{contado['build']} build(s), {contado['estreia']} "
                  f"estreia(s); fonte: {contado['fonte']}).")
        except Exception as exc:                               # noqa: BLE001
            print(f"[noite] nao deu para contar o estoque: "
                  f"{type(exc).__name__}: {exc}")
    try:
        plano = planejar(config, agora, contagem=contado)
    except Exception as exc:                                   # noqa: BLE001
        # Nao saber contar NAO libera a noite nem para o dia: cai no esquema
        # de antes do lote, que tem teto proprio.
        print(f"[noite] o plano falhou ({type(exc).__name__}: {exc}); "
              f"sigo pelo teto de gordura.")
        plano = {"modo": modo, "fazer": modo != "noite", "criar": True,
                 "metas": None, "motivo": "fora da janela",
                 "por_que": "plano ilegivel", "impedimento": None,
                 "limite_min": None, "config": config}
    modo = plano["modo"]
    efetivo = plano["config"]
    if modo != "livre":
        print(f"[noite] modo {modo}: {plano['por_que']}.")

    if modo == "livre":
        janela = config.get("janela_pesada")
        if not na_janela(agora.hour, janela):
            texto = (f"[noite] fora da janela do trabalho pesado "
                     f"({int(janela['inicio']):02d}h as "
                     f"{int(janela['fim']):02d}h).")
            if not ensaio:
                print(texto + " Saindo.")
                return {"feito": "nada", "motivo": "fora da janela",
                        "modo": modo}
            print(texto + " Numa rodada real eu sairia aqui; o ensaio segue.")
    elif not plano["fazer"]:
        if not ensaio:
            print("[noite] nada a fazer agora. Saindo.")
            return {"feito": "nada", "motivo": plano.get("motivo") or "nada",
                    "modo": modo, "plano": plano}
        print("[noite] numa rodada real eu sairia aqui; o ensaio segue com a "
              "regra do dia.")
        efetivo = _config_de_dia(config)

    limite = None
    if plano.get("limite_min") and duelos is None and builds is None:
        limite = agora + timedelta(minutes=float(plano["limite_min"]))

    with travas.trava(TRAVA, esperar=0.0) as minha:
        if not minha:
            print("[noite] ja tem uma rodada de geracao em andamento. Saindo.")
            return {"feito": "nada", "motivo": "ja rodando", "modo": modo}
        comeco = time.monotonic()
        resultado = _trabalhar(config=efetivo, ensaio=ensaio, duelos=duelos,
                               sem_worker=sem_worker, relogio=relogio,
                               gerar_duelo=gerar_duelo,
                               drenar_worker=drenar_worker, jobs=jobs,
                               estoque=estoque, proximo=proximo,
                               builds=builds, gerar_build=gerar_build,
                               estoque_builds=estoque_builds,
                               metas=plano.get("metas"), contagem=contado,
                               limite=limite)
        resultado["modo"] = modo
        resultado["plano"] = plano
        if (plano.get("impedimento") and not resultado.get("duelos")
                and not resultado.get("builds")):
            resultado["motivo"] = "impedido"
        gasto = time.monotonic() - comeco
        resultado["segundos"] = round(gasto, 1)
        feitos = resultado.get("duelos") or []
        roletas = resultado.get("builds") or []
        print(f"[noite] fim: {len(feitos)} duelo(s) novo(s), "
              f"{len(roletas)} build(s) nova(s), "
              f"{resultado.get('jobs_do_worker', 0)} job(s) do worker, "
              f"{len(resultado.get('erros') or [])} erro(s), "
              f"{gasto / 60:.1f} min.")
        if not ensaio:
            if resultado.get("erros"):
                _registrar("erro", f"geracao ({modo}): "
                           + "; ".join(resultado["erros"])[:280],
                           etapa="noite")
            if feitos or roletas or resultado.get("jobs_do_worker"):
                _registrar("ok", f"geracao ({modo}): {len(feitos)} duelo(s), "
                           f"{len(roletas)} build(s) "
                           f"({', '.join(feitos + roletas)})"[:300],
                           etapa="noite", dur_s=gasto)
        return resultado


def planos(config: dict, *, duelos=None, builds=None, estoque=None,
           estoque_builds=None, metas=None, contagem=None) -> list[dict]:
    """O que gerar nesta rodada, e em que ordem: a NECESSIDADE manda.

    Decisao do Adrian em 28/09/2026: a roleta entra na geracao automatica
    junto com o duelo, e quem tem MENOS DIAS de estoque vai primeiro — o
    tempo da rodada nao da para os dois quando os dois estao baixos, e o
    formato que acaba antes e o que deixa horario vazio.

    Dias = estoque / horarios que a cota da ao formato por dia. Estoque de
    build conta tambem as builds em preparo (o worker ainda termina).
    Empate: duelo primeiro (mais barato, e o que o dado mais quer).

    `metas` (do `planejar`): a meta de cada formato no lote, na reposicao e
    no estoque zero; sem ela, o teto de gordura de sempre. A roleta tambem
    atende a meta da ESTREIA — ela so nasce dentro do `generate-video`.
    `contagem`: o estoque da publicacao por formato (`contar_estoque`).

    Pedido manual (`--duelos`/`--builds`): so o que foi pedido, ignorando o
    teto; formato nao pedido fica de fora.
    """
    manual = duelos is not None or builds is not None
    saida = []

    if estoque:
        na_fila = len(estoque())
    elif contagem is not None:
        na_fila = int(contagem.get("duelo", 0))
    else:
        na_fila = len(estoque_de_duelos())
    saida.append({
        "formato": "duelo", "na_fila": na_fila,
        "teto": (int(metas.get("duelo", 0)) if metas is not None
                 else teto_de_duelos(config)),
        "por_dia": duelos_por_dia(),
        "pedido": duelos, "maximo": int(config.get(
            "maximo_de_duelos_por_rodada", 6)),
        "minutos": float(config.get("minutos_por_duelo", 5)),
        "ligado": True})

    preparo = 0
    if estoque_builds:
        na_fila_b = len(estoque_builds())
    else:
        preparo = len(builds_em_preparo())
        base = (int(contagem.get("build", 0)) if contagem is not None
                else len(estoque_de_builds()))
        na_fila_b = base + preparo
    plano_b = {
        "formato": "build", "na_fila": na_fila_b,
        "teto": (int(metas.get("build", 0)) if metas is not None
                 else teto_de_builds(config)),
        "por_dia": builds_por_dia(),
        "pedido": builds, "maximo": int(config.get(
            "maximo_de_builds_por_rodada", 1)),
        "minutos": float(config.get("minutos_por_build", 15)),
        "ligado": bool(config.get("builds", True))}
    if metas is not None and contagem is not None and metas.get("estreia"):
        plano_b["estreias"] = int(contagem.get("estreia", 0)) + preparo
        plano_b["meta_estreia"] = int(metas["estreia"])
    saida.append(plano_b)

    for plano in saida:
        if manual:
            plano["alvo"] = max(0, int(plano["pedido"] or 0))
        elif not plano["ligado"]:
            plano["alvo"] = 0
        else:
            falta = plano["teto"] - plano["na_fila"]
            if "meta_estreia" in plano:
                falta = max(falta, plano["meta_estreia"] - plano["estreias"])
            plano["alvo"] = min(max(0, falta), plano["maximo"])
        plano["dias"] = (plano["na_fila"] / plano["por_dia"]
                         if plano["por_dia"] > 0 else float("inf"))
    ordem = {"duelo": 0, "build": 1}
    saida.sort(key=lambda p: (p["dias"], ordem[p["formato"]]))
    return saida


def _limite_da_geracao(config, limite, pendentes_no_comeco: bool,
                       sem_worker: bool):
    """Ate quando a GERACAO pode comecar passo: o fim da rodada menos a
    reserva do worker (`rodada_de_dia.reserva_do_worker`), so quando ha job
    esperando — sem job, a rodada inteira e da geracao."""
    if limite is None:
        return None
    reserva = float((config.get("rodada_de_dia") or {})
                    .get("reserva_do_worker") or 0)
    if (reserva <= 0 or sem_worker or not config.get("worker", True)
            or not pendentes_no_comeco):
        return limite
    return limite - timedelta(minutes=reserva)


def _trabalhar(*, config, ensaio, duelos, sem_worker, relogio, gerar_duelo,
               drenar_worker, jobs, estoque, proximo=None, builds=None,
               gerar_build=None, estoque_builds=None, metas=None,
               contagem=None, limite=None) -> dict:
    erros: list[str] = []
    feitos: list[str] = []
    roletas: list[str] = []
    parou = ""
    listar_jobs = jobs or jobs_do_worker

    # ---- 1. duelos e builds ate a meta, quem tem menos dias primeiro
    fila_de_planos = planos(config, duelos=duelos, builds=builds,
                            estoque=estoque, estoque_builds=estoque_builds,
                            metas=metas, contagem=contagem)
    for plano in fila_de_planos:
        rotulo = "duelos" if plano["formato"] == "duelo" else "builds"
        origem = ("pedido manual" if plano["pedido"] is not None
                  else "desligado no config" if not plano["ligado"]
                  else f"meta {plano['teto']}" if metas is not None
                  else f"teto {plano['teto']}")
        extra = ""
        if "meta_estreia" in plano:
            extra = (f"; estreias {plano['estreias']}, meta "
                     f"{plano['meta_estreia']}")
        print(f"[noite] {rotulo} no estoque que a grade escolheria: "
              f"{plano['na_fila']} ({plano['dias']:.1f} dia(s); {origem}"
              f"{extra}). Vou gerar {plano['alvo']}.")

    pendentes_no_comeco = False
    if limite is not None and any(p["alvo"] for p in fila_de_planos):
        try:
            pendentes_no_comeco = bool(listar_jobs())
        except Exception:                                      # noqa: BLE001
            pendentes_no_comeco = False
    limite_geracao = _limite_da_geracao(config, limite, pendentes_no_comeco,
                                        sem_worker)
    if limite is not None:
        print(f"[noite] rodada ate {limite:%H:%M}; passo novo de geracao so "
              f"se termina ate {limite_geracao:%H:%M}.")

    geradores = {
        "duelo": gerar_duelo or (_duelo_ensaiado() if ensaio
                                 else _duelo_de_verdade()),
        "build": gerar_build or (_build_ensaiado() if ensaio
                                 else _build_de_verdade()),
    }
    for plano in fila_de_planos:
        formato, minutos = plano["formato"], plano["minutos"]
        destino = feitos if formato == "duelo" else roletas
        falhas = 0
        for _ in range(plano["alvo"]):
            if not cabe(relogio(), minutos, config, limite_geracao):
                parou = "janela"
                print(f"[noite] outro {formato} ({minutos:.0f} min) nao cabe "
                      f"antes da proxima postagem, do fim da janela ou do "
                      f"fim da rodada. Fica para a proxima.")
                if not ensaio:
                    break
            try:
                pasta = geradores[formato]()
            except Exception as exc:                           # noqa: BLE001
                falhas += 1
                erros.append(f"{formato}: {type(exc).__name__}: "
                             f"{str(exc)[:160]}")
                print(f"[noite] o {formato} falhou: {type(exc).__name__}: "
                      f"{exc}")
                if falhas >= FALHAS_SEGUIDAS:
                    print(f"[noite] duas falhas seguidas; paro os {formato}s.")
                    break
                continue
            falhas = 0
            destino.append(Path(str(pasta)).name)

    # ---- 2. worker de identidade (capa e payoff das builds)
    feitos_worker = 0
    if config.get("worker", True) and not sem_worker:
        try:
            pendentes = listar_jobs()
        except Exception as exc:                               # noqa: BLE001
            pendentes = []
            erros.append(f"fila do worker ilegivel: {type(exc).__name__}")
        if pendentes:
            gids = sorted({j.get("generation_id", "?") for j in pendentes})
            print(f"[noite] worker: {len(pendentes)} job(s) pendente(s) "
                  f"({', '.join(gids)}).")
        drenar = drenar_worker or (_worker_ensaiado if ensaio
                                   else _worker_de_verdade)
        qual = proximo or (_proximo_ensaiado(pendentes) if ensaio
                           else proximo_do_worker)
        # Provedor que nao andou nesta rodada (perfil ocupado por outra
        # fabrica, dependencia, tentativas no teto) nao e chamado de novo — e
        # NAO encerra o worker. Medido as 03:03 de 28/09/2026: a rodada de
        # historias segurava o PicassoIA, a passada de imagem voltou vazia e
        # o payoff do Digen (outro perfil, livre) ficou parado atras dela.
        tentados: set = set()
        while pendentes:
            # UM PROVEDOR POR CHAMADA, COM PRAZO. O tempo de um job depende de
            # quem faz: imagem ~3-6 min, payoff do Digen 12-15 min (medido).
            # O prazo vai para dentro do worker, que nao comeca job nem
            # tentativa nova depois dele — `limite` nao bastava, porque um
            # job que falha e repescado na mesma passada.
            try:
                provedor = qual(excluir=frozenset(tentados))
            except Exception as exc:                           # noqa: BLE001
                erros.append(f"fila do worker ilegivel: {type(exc).__name__}")
                break
            if not provedor:
                print("[noite] worker: nada que ele consiga pegar agora "
                      "(dependencia esperando ou tentativas esgotadas).")
                break
            minutos_job = minutos_do_job(provedor, config)
            agora = relogio()
            if not cabe(agora, minutos_job, config, limite):
                print(f"[noite] worker: um job de {provedor} "
                      f"({minutos_job:.0f} min) nao cabe antes da proxima "
                      f"postagem ou do fim da rodada. Fica para a proxima.")
                parou = parou or "janela"
                break
            prazo = (fim_da_folga(agora, config, limite=limite)
                     - timedelta(minutes=minutos_job))
            print(f"[noite] worker: {provedor}, jobs novos ate "
                  f"{prazo:%H:%M} ({minutos_job:.0f} min cada).")
            try:
                feitos_agora = int(drenar(so_provedor=provedor,
                                          prazo=prazo.timestamp()) or 0)
            except Exception as exc:                           # noqa: BLE001
                erros.append(f"worker: {type(exc).__name__}: {str(exc)[:160]}")
                print(f"[noite] o worker falhou: {type(exc).__name__}: {exc}")
                break
            if feitos_agora <= 0:
                tentados.add(provedor)
                print(f"[noite] worker: {provedor} nao andou (perfil "
                      f"ocupado, dependencia ou tentativas esgotadas); sigo "
                      f"para o proximo provedor, se houver.")
                continue
            feitos_worker += feitos_agora
            if ensaio:
                break
            pendentes = listar_jobs()

    duelo = next(p for p in fila_de_planos if p["formato"] == "duelo")
    alvos = sum(p["alvo"] for p in fila_de_planos)
    feito = ("duelos" if feitos else "builds" if roletas
             else "worker" if feitos_worker else "nada")
    return {"feito": feito, "duelos": feitos, "builds": roletas,
            "jobs_do_worker": feitos_worker,
            "estoque_antes": duelo["na_fila"], "teto": duelo["teto"],
            "alvo": duelo["alvo"], "planos": fila_de_planos,
            "parou": parou, "erros": erros,
            "motivo": "" if (feitos or roletas or feitos_worker or erros)
            else ("estoque cheio" if alvos == 0 else parou or "nada feito")}


# ---------------------------------------------------------------- ensaio
def _duelo_ensaiado():
    """Duble do gerador: escolhe o par pelo rodizio de verdade e para.

    Nao simula, nao grava, nao renderiza. Os pares escolhidos entram numa
    lista local, para o segundo duelo do ensaio ver o primeiro — senao o
    ensaio mostraria o mesmo par N vezes e esconderia justamente o que ele
    existe para mostrar.
    """
    from ..arena import rodizio
    from ..arena.ledger import Ledger
    from ..generation.random_engine import RandomEngine
    from ..publicar import catalogo, titulos
    from ..tournament.runner import fichas_do_banco, personagens_gerados

    fichas = fichas_do_banco()
    gerados = personagens_gerados()
    config = catalogo.carregar_config()
    pares = rodizio.duelos_recentes(n=None)
    ocupados = rodizio.titulos_ocupados(pares, config=config)
    ledger = Ledger()
    contador = {"n": 0}

    def gerar() -> Path:
        contador["n"] += 1
        rng = RandomEngine(RandomEngine.new_seed()).fork("duelo:participantes")
        p1, p2 = rodizio.escolher_par(fichas, gerados, rng, pares=pares,
                                      ledger=ledger, ocupados=ocupados,
                                      config=config)
        if not (p1 and p2):
            raise ValueError("nao ha par com titulo livre no banco")
        pares.append((p1, p2))
        ocupados.add(titulos.chave(rodizio.titulo_do_par(p1, p2, config)))
        print(f"[ensaio] duelo {contador['n']}: {p1} x {p2} (nada gravado)")
        return Path(f"ensaio_{contador['n']:02d}")
    return gerar


def _build_ensaiado():
    """Duble da roleta: diz que geraria e para. Nada e sorteado nem gravado."""
    contador = {"n": 0}

    def gerar() -> Path:
        contador["n"] += 1
        print(f"[ensaio] build {contador['n']}: generate-video (nada gerado)")
        return Path(f"ensaio_build_{contador['n']:02d}")
    return gerar


def _worker_ensaiado(so_provedor: str | None = None,
                     prazo: float | None = None) -> int:
    quando = (datetime.fromtimestamp(prazo).strftime("%H:%M")
              if prazo is not None else "sem prazo")
    print(f"[ensaio] worker: drenaria {so_provedor or 'tudo'} com jobs novos "
          f"ate {quando} (nada aberto)")
    return 1


def _proximo_ensaiado(pendentes):
    """No ensaio o provedor sai da lista de pendentes, sem tocar na fila."""
    def qual(excluir=()):
        provedores = [j.get("provider") for j in pendentes
                      if j.get("provider") and j.get("provider") not in excluir]
        if "picasso" in provedores:
            return "picasso"
        return provedores[0] if provedores else None
    return qual


# ---------------------------------------------------------------- saida
def codigo_de_saida(resultado: dict) -> int:
    """0 = fez o que devia (inclusive nada); 1 = houve erro."""
    return 1 if resultado.get("erros") else 0


__all__ = ["CONFIG", "TRAVA", "alvo_do_lote", "contar_estoque",
           "disco_apertado", "fim_da_cobertura", "fora_da_grade",
           "lote_valendo", "metas_por_formato", "modo_da_hora",
           "perto_da_grade", "piso_de_reposicao", "planejar",
           "postagens_entre",
           "builds_em_preparo", "builds_por_dia", "cabe",
           "carregar", "codigo_de_saida", "diario_do_dia", "duelos_por_dia",
           "estoque_de_builds", "estoque_de_duelos", "estoque_do_formato",
           "planos", "por_dia", "teto_de_builds",
           "fim_da_folga", "jobs_do_worker", "minutos_do_job", "na_grade",
           "na_janela", "proximo_do_worker", "quantos_cabem", "rodar",
           "teto_de_duelos"]
