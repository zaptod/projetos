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

PADRAO = {
    "ativo": True,
    "janela_pesada": {"inicio": 1, "fim": 6},
    "grade_proibida": {"de": 25, "ate": 55},
    "horas": [1, 2, 3, 4, 5],
    "minuto": 2,
    "dias_de_gordura": 2,
    "minutos_por_duelo": 5,
    "minutos_por_imagem": 8,
    "minutos_por_payoff": 18,
    "maximo_de_duelos_por_rodada": 6,
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


def cabe(agora: datetime, minutos: float, config: dict) -> bool:
    """Um trabalho de `minutos` comecando AGORA termina sem encostar em nada?

    Confere minuto a minuto (o trabalho mais longo e de 8 min): cada instante
    tem de estar na janela pesada e fora da janela da grade. O ultimo
    instante conta — terminar as :25 em ponto ja e encostar.
    """
    janela = config.get("janela_pesada")
    proibida = config.get("grade_proibida")
    passos = max(1, int(math.ceil(float(minutos))))
    for i in range(passos + 1):
        instante = agora + timedelta(minutes=min(float(minutos), i))
        if not na_janela(instante.hour, janela):
            return False
        if na_grade(instante.minute, proibida):
            return False
    return True


def quantos_cabem(agora: datetime, minutos: float, config: dict,
                  maximo: int = 50) -> int:
    """Quantos trabalhos de `minutos`, um atras do outro, cabem a partir de
    AGORA."""
    n = 0
    while n < maximo and cabe(agora + timedelta(minutes=n * float(minutos)),
                              minutos, config):
        n += 1
    return n


def fim_da_folga(agora: datetime, config: dict,
                 horizonte_min: int = 24 * 60) -> datetime:
    """O primeiro minuto, a partir de AGORA, em que nada pode estar rodando
    (janela da grade ou fim da janela pesada). E dele que sai o prazo que o
    worker recebe: prazo = fim da folga - quanto um job leva."""
    janela = config.get("janela_pesada")
    proibida = config.get("grade_proibida")
    base = agora.replace(second=0, microsecond=0)
    for i in range(horizonte_min + 1):
        instante = base + timedelta(minutes=i)
        if instante < agora:
            continue
        if (not na_janela(instante.hour, janela)
                or na_grade(instante.minute, proibida)):
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


# ------------------------------------------------------------------ estoque
def cota(config_publicacao: dict | None = None) -> dict:
    if config_publicacao is None:
        from ..publicar import catalogo
        config_publicacao = catalogo.carregar_config()
    bruta = ((config_publicacao or {}).get("grade") or {}).get("mistura")
    if not isinstance(bruta, dict) or not bruta:
        return dict(COTA_DE_QUEDA)
    return {str(k): max(0, int(v)) for k, v in bruta.items()}


def duelos_por_dia(config_publicacao: dict | None = None,
                   horarios: int | None = None) -> float:
    """Quantos horarios do dia a cota da ao duelo (4/8 de 10 = 5)."""
    if horarios is None:
        from .. import grade
        horarios = len(grade.HORAS)
    pesos = cota(config_publicacao)
    total = sum(pesos.values())
    if total <= 0:
        return 0.0
    return horarios * pesos.get("duelo", 0) / total


def teto_de_duelos(config: dict, config_publicacao: dict | None = None,
                   horarios: int | None = None) -> int:
    dias = max(0.0, float(config.get("dias_de_gordura", 0)))
    return int(math.ceil(dias * duelos_por_dia(config_publicacao, horarios)))


def estoque_de_duelos(videos=None, publicados=None) -> list:
    """Os duelos que a publicacao ESCOLHERIA, do mais antigo ao mais novo.

    O mesmo funil de `postar.proximo_build`, com as mesmas funcoes: saiu =
    `metricas.publicado`, titulo = `titulos.chave`. Fica de fora o que ja
    foi ao ar (em qualquer destino), o que tem pendencia e o que tem titulo
    ja publicado. Dois duelos pendentes com o MESMO titulo contam como um:
    o segundo so sairia repetindo o primeiro.
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
        if getattr(video, "origem", "") != catalogo.DUELO:
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
    return [j for j in queue.listar()
            if j.get("status") == queue.PENDENTE
            and int(j.get("attempts", 0)) < maximo]


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


def _worker_de_verdade(so_provedor: str | None = None,
                       prazo: float | None = None) -> int:
    from ..identity import worker
    return worker.drenar(headless=False, rerender=True, preview=False,
                         so_provedor=so_provedor, prazo=prazo)


def rodar(*, config: dict | None = None, ensaio: bool = False,
          duelos: int | None = None, sem_worker: bool = False,
          relogio=None, gerar_duelo=None, drenar_worker=None,
          jobs=None, estoque=None, proximo=None, tela=None) -> dict:
    """Uma rodada. Devolve o que aconteceu; nunca levanta por conta da tarefa.

    `ensaio`: faz TODAS as conferencias e diz o que faria, sem gerar nada e
    sem escrever no diario compartilhado. E o duble do teste de ponta a
    ponta (tarefa -> .cmd -> python -> trava -> diario) antes de registrar.

    `duelos`: quantos gerar, ignorando o teto (a rodada manual). O relogio
    continua mandando: o que nao couber antes de :25 fica para a proxima.

    Os parametros `relogio`, `gerar_duelo`, `drenar_worker`, `jobs` e
    `estoque` existem para os testes trocarem o mundo por dubles.
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
                       travas=travas, controle=controle)
    finally:
        try:
            sys.stdout.flush()
        except Exception:                                      # noqa: BLE001
            pass
        sys.stdout, sys.stderr = anterior_out, anterior_err


def _rodada(*, config, ensaio, duelos, sem_worker, relogio, gerar_duelo,
            drenar_worker, jobs, estoque, proximo, travas, controle) -> dict:
    agora = relogio()
    rotulo = " (ENSAIO: nada e gerado)" if ensaio else ""
    print(f"[noite] disparo das {agora:%H:%M}{rotulo}")

    if not config.get("ativo", True):
        print("[noite] a geracao esta desligada (`ativo: false`). Nada a fazer.")
        return {"feito": "nada", "motivo": "desligada"}
    if controle.pausado_para():
        print("[noite] a pipeline esta PAUSADA (pagina Vila). Saindo.")
        return {"feito": "nada", "motivo": "pausado"}

    janela = config.get("janela_pesada")
    if not na_janela(agora.hour, janela):
        texto = (f"[noite] fora da janela do trabalho pesado "
                 f"({int(janela['inicio']):02d}h as {int(janela['fim']):02d}h).")
        if not ensaio:
            print(texto + " Saindo.")
            return {"feito": "nada", "motivo": "fora da janela"}
        print(texto + " Numa rodada real eu sairia aqui; o ensaio segue.")

    with travas.trava(TRAVA, esperar=0.0) as minha:
        if not minha:
            print("[noite] ja tem uma rodada de geracao em andamento. Saindo.")
            return {"feito": "nada", "motivo": "ja rodando"}
        comeco = time.monotonic()
        resultado = _trabalhar(config=config, ensaio=ensaio, duelos=duelos,
                               sem_worker=sem_worker, relogio=relogio,
                               gerar_duelo=gerar_duelo,
                               drenar_worker=drenar_worker, jobs=jobs,
                               estoque=estoque, proximo=proximo)
        gasto = time.monotonic() - comeco
        resultado["segundos"] = round(gasto, 1)
        feitos = resultado.get("duelos") or []
        print(f"[noite] fim: {len(feitos)} duelo(s) novo(s), "
              f"{resultado.get('jobs_do_worker', 0)} job(s) do worker, "
              f"{len(resultado.get('erros') or [])} erro(s), "
              f"{gasto / 60:.1f} min.")
        if not ensaio:
            if resultado.get("erros"):
                _registrar("erro", "geracao noturna: "
                           + "; ".join(resultado["erros"])[:280],
                           etapa="noite")
            if feitos or resultado.get("jobs_do_worker"):
                _registrar("ok", f"geracao noturna: {len(feitos)} duelo(s) "
                           f"({', '.join(feitos)})"[:300], etapa="noite",
                           dur_s=gasto)
        return resultado


def _trabalhar(*, config, ensaio, duelos, sem_worker, relogio, gerar_duelo,
               drenar_worker, jobs, estoque, proximo=None) -> dict:
    erros: list[str] = []
    feitos: list[str] = []
    parou = ""

    # ---- 1. duelos ate o teto
    na_fila = len(estoque() if estoque else estoque_de_duelos())
    teto = teto_de_duelos(config)
    if duelos is not None:
        alvo = max(0, int(duelos))
        print(f"[noite] duelos no estoque que a grade escolheria: {na_fila} "
              f"(teto {teto}). Pedido manual: {alvo}.")
    else:
        alvo = max(0, teto - na_fila)
        alvo = min(alvo, int(config.get("maximo_de_duelos_por_rodada", 6)))
        print(f"[noite] duelos no estoque que a grade escolheria: {na_fila} "
              f"(teto {teto}). Vou gerar {alvo}.")

    if gerar_duelo is None:
        gerar_duelo = _duelo_ensaiado() if ensaio else _duelo_de_verdade()
    minutos_duelo = float(config.get("minutos_por_duelo", 5))
    falhas = 0
    for _ in range(alvo):
        if not cabe(relogio(), minutos_duelo, config):
            parou = "janela"
            print(f"[noite] outro duelo ({minutos_duelo:.0f} min) nao cabe "
                  f"antes de :{int(config['grade_proibida']['de']):02d} ou do "
                  f"fim da janela. Fica para a proxima rodada.")
            if not ensaio:
                break
        try:
            pasta = gerar_duelo()
        except Exception as exc:                               # noqa: BLE001
            falhas += 1
            erros.append(f"duelo: {type(exc).__name__}: {str(exc)[:160]}")
            print(f"[noite] o duelo falhou: {type(exc).__name__}: {exc}")
            if falhas >= FALHAS_SEGUIDAS:
                print("[noite] duas falhas seguidas; paro os duelos.")
                break
            continue
        falhas = 0
        feitos.append(Path(str(pasta)).name)

    # ---- 2. worker de identidade (capa e payoff das builds)
    feitos_worker = 0
    if config.get("worker", True) and not sem_worker:
        listar_jobs = jobs or jobs_do_worker
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
            if not cabe(agora, minutos_job, config):
                print(f"[noite] worker: um job de {provedor} "
                      f"({minutos_job:.0f} min) nao cabe antes da janela da "
                      f"grade. Fica para a proxima.")
                parou = parou or "janela"
                break
            prazo = fim_da_folga(agora, config) - timedelta(minutes=minutos_job)
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

    feito = "duelos" if feitos else ("worker" if feitos_worker else "nada")
    return {"feito": feito, "duelos": feitos, "jobs_do_worker": feitos_worker,
            "estoque_antes": na_fila, "teto": teto, "alvo": alvo,
            "parou": parou, "erros": erros,
            "motivo": "" if (feitos or feitos_worker or erros)
            else ("estoque cheio" if alvo == 0 else parou or "nada feito")}


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


__all__ = ["CONFIG", "TRAVA", "cabe", "carregar", "codigo_de_saida",
           "diario_do_dia", "duelos_por_dia", "estoque_de_duelos",
           "fim_da_folga", "jobs_do_worker", "minutos_do_job", "na_grade",
           "na_janela", "proximo_do_worker", "quantos_cabem", "rodar",
           "teto_de_duelos"]
