"""Fila de jobs de identidade em disco.

A unidade da fila e o SLOT, nao a geracao: cada geracao rende tres videos
(personagem, arma, personagem+arma), entao a chave e `generation_id#slot`
(`src/identity/slots.py`). Jobs gravados no formato antigo, sem slot, sao lidos
como o slot de personagem — a fila que ja estava no disco continua valendo.

A roleta enfileira e termina; o worker drena depois. Sao processos diferentes
(a UI dispara `generate-video`, o worker roda a parte), entao a fila precisa de
lock inter-processo e escrita atomica — mesmo padrao provado em
`neural_fights/data/database.py:80-134`, com arquivo de lock proprio para nao
serializar a fila contra as gravacoes do banco do jogo.
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from . import artefato, config, slots
from .config import settings

ARQUIVO_FILA = config.IDENTITY_DIR / "queue.json"
LOCK = Path(tempfile.gettempdir()) / "random-builds.identity.lock"
LOCK_TIMEOUT = 30.0

# Lock de INSTANCIA do worker, diferente do lock da fila: aquele protege uma
# escrita (milissegundos), este e segurado pela rodada inteira (minutos).
LOCK_WORKER = Path(tempfile.gettempdir()) / "random-builds.identity.worker.lock"

PENDENTE, RODANDO, PRONTO, FALHOU = "pending", "running", "done", "failed"


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextlib.contextmanager
def _bloqueio():
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    arquivo = open(LOCK, "a+b")
    adquirido = False
    try:
        arquivo.seek(0, os.SEEK_END)
        if arquivo.tell() == 0:
            arquivo.write(b"\0")
            arquivo.flush()
        arquivo.seek(0)
        if os.name == "nt":
            import msvcrt
            limite = time.monotonic() + LOCK_TIMEOUT
            while True:
                try:
                    msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
                    adquirido = True
                    break
                except OSError as exc:
                    if time.monotonic() >= limite:
                        raise TimeoutError(
                            "tempo esgotado aguardando o lock da fila") from exc
                    time.sleep(0.01)
        else:
            import fcntl
            fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX)
            adquirido = True
        yield
    finally:
        if adquirido:
            arquivo.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
        arquivo.close()


@contextlib.contextmanager
def instancia_unica():
    """Garante UM worker por vez. Cede sem bloquear se ja houver outro.

    Nao e preciosismo: dois workers se sabotam. `reabrir()` devolve a fila
    qualquer job em `running`, presumindo worker morto — mas com dois vivos, um
    considera orfao o job que o OUTRO esta processando e o rouba. Foi assim que
    `generation_00014` acabou baixado duas vezes e concluido duas vezes.

    Com instancia unica, `running` volta a significar de fato "worker morreu".
    """
    LOCK_WORKER.parent.mkdir(parents=True, exist_ok=True)
    arquivo = open(LOCK_WORKER, "a+b")
    adquirido = False
    try:
        arquivo.seek(0, os.SEEK_END)
        if arquivo.tell() == 0:
            arquivo.write(b"\0")
            arquivo.flush()
        arquivo.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            adquirido = True
        except OSError:
            adquirido = False
        yield adquirido
    finally:
        if adquirido:
            arquivo.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
        arquivo.close()


def _ler() -> list[dict]:
    if not ARQUIVO_FILA.is_file():
        return []
    try:
        with open(ARQUIVO_FILA, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    except (json.JSONDecodeError, OSError):
        # Fila ilegivel nao pode derrubar a roleta nem o worker: recomeca vazia
        # e preserva o arquivo velho para inspecao.
        with contextlib.suppress(OSError):
            ARQUIVO_FILA.replace(ARQUIVO_FILA.with_suffix(".corrompida.json"))
        return []
    return _normalizar(dados) if isinstance(dados, list) else []


def _normalizar(jobs: list[dict]) -> list[dict]:
    """Job do formato antigo ganha slot e job_id ao ser lido.

    Migracao preguicosa de proposito: nao existe passo de upgrade para rodar,
    e uma fila gravada pela versao anterior continua sendo processada.
    """
    for job in jobs:
        job.setdefault("slot", slots.CHARACTER)
        job.setdefault("job_id", slots.job_id(job["generation_id"], job["slot"]))
        # Provedor e dependencia nasceram depois; um job gravado antes disso
        # ganha o padrao do proprio slot na leitura. Sem passo de upgrade: a
        # fila que ja esta no disco continua sendo processada.
        job.setdefault("provider", slots.provedor(job["slot"]))
        job.setdefault("depends_on",
                       [slots.job_id(job["generation_id"], dependencia)
                        for dependencia in slots.depende_de(job["slot"])])
        job.setdefault("aguardar_ate", None)
        # O que foi de fato anexado ao prompt (preenchido no envio).
        job.setdefault("referencias", None)
        # No formato antigo so existia um clipe por espaco, entao ter
        # `space_url` gravado JA significava "o prompt foi enviado".
        job.setdefault("enviado", bool(job.get("space_url")))
        job.setdefault("videos_antes", None)
        # Quando o prompt foi enviado: a prova de origem compara com a data
        # do card, e uma retomada precisa saber isso sem o client.
        job.setdefault("enviado_em", None)
    return jobs


def _gravar(jobs: list[dict]) -> None:
    ARQUIVO_FILA.parent.mkdir(parents=True, exist_ok=True)
    temporario = ARQUIVO_FILA.with_suffix(".tmp")
    with open(temporario, "w", encoding="utf-8") as fh:
        json.dump(jobs, fh, ensure_ascii=False, indent=2)
    os.replace(temporario, ARQUIVO_FILA)


def _atualizar(job_id: str, mudancas: dict) -> dict | None:
    with _bloqueio():
        jobs = _ler()
        for job in jobs:
            if job["job_id"] == job_id:
                job.update(mudancas)
                _gravar(jobs)
                return job
    return None


# ------------------------------------------------------------------ publico
def listar() -> list[dict]:
    with _bloqueio():
        return _ler()


def enqueue(generation_id: str, prompt: str, aspect: str = "9:16",
            slot: str = slots.CHARACTER, aguardar_ate: str | None = None) -> dict:
    """Enfileira (ou reenfileira) UM slot. Idempotente por (geracao, slot).

    Provedor e dependencia nao sao parametro: eles sao propriedade do SLOT
    (`slots.PROVEDOR`, `slots.DEPENDE_DE`). Quem enfileira nao pode escolher
    errado, e `identity run` de um slot solto sai com o mesmo grafo.
    """
    identificador = slots.job_id(generation_id, slot)
    grafo = {
        "provider": slots.provedor(slot),
        "depends_on": [slots.job_id(generation_id, dependencia)
                       for dependencia in slots.depende_de(slot)],
        "aguardar_ate": aguardar_ate,
    }
    with _bloqueio():
        jobs = _ler()
        # Um `pending` com as tentativas no teto NAO esta em andamento: esta
        # travado, e `claim` nunca mais vai pega-lo. Devolve-lo intacto por
        # "idempotencia" deixava o unico comando capaz de destravar sem efeito
        # nenhum — reenfileirar dizia OK e nada mudava.
        maximo = int(settings().get("max_attempts", 3))
        for job in jobs:
            if job["job_id"] == identificador:
                em_andamento = job["status"] == RODANDO or (
                    job["status"] == PENDENTE
                    and job.get("attempts", 0) < maximo)
                if em_andamento:
                    return job
                # O grafo e reescrito TAMBEM aqui: sem isto um job ressuscitado
                # por `identity run` voltaria sem dependencia e o payoff seria
                # gerado antes das imagens existirem.
                #
                # E `enviado` e ZERADO: reenfileirar um job ja concluido quer
                # dizer "faca de novo". Sem zerar, o worker via o `space_url`
                # antigo, tomava o caminho de RETOMADA e rebaixava exatamente o
                # mesmo video — silenciosamente, sem gerar nada. Foi o que
                # aconteceu ao tentar refazer um payoff: byte por byte igual.
                # `attempts` ZERADO junto: reenfileirar quer dizer "tente de
                # novo do zero". Sem isso um job que falhou tres vezes voltava
                # como `pending` com as tentativas no teto — `claim` nunca mais
                # o pegava e ele ficava na fila sem rodar e sem aparecer como
                # falha, que e o pior estado possivel (o mesmo que `reabrir`
                # existe para evitar).
                job.update({"status": PENDENTE, "prompt": prompt,
                            "aspect": aspect, "error": None, "attempts": 0,
                            "enviado": False, "videos_antes": None,
                            "referencias": None,
                            "updated_at": _agora(), **grafo})
                _gravar(jobs)
                return job
        job = {
            "job_id": identificador,
            "generation_id": generation_id,
            "slot": slot,
            **grafo,
            "status": PENDENTE,
            "prompt": prompt,
            "aspect": aspect,
            # Espaco do Digen desta BUILD. Os tres clipes da geracao nascem
            # no mesmo, entao ele e compartilhado entre os slots.
            "space_url": None,
            # `enviado` e o que distingue "o espaco existe porque outro slot o
            # criou" de "eu ja mandei o meu prompt e o video esta em voo". Sem
            # essa separacao, o slot da arma abriria o espaco do personagem e
            # esperaria para sempre por um video que nunca foi pedido.
            "enviado": False,
            # Foto dos cards que ja existiam no espaco na hora do envio: e ela
            # que identifica o video novo quando a retomada perde o contexto.
            "videos_antes": None,
            "attempts": 0,
            "error": None,
            "created_at": _agora(),
            "updated_at": _agora(),
        }
        jobs.append(job)
        _gravar(jobs)
        return job


def _dependencias_satisfeitas(job: dict, jobs: list[dict], agora: str) -> bool:
    """O job pode sair da fila, ou ainda esta esperando alguem?

    SATISFEITA nao e o mesmo que PRONTA. Sao cinco caminhos, e cada um fecha um
    buraco concreto:

      1. artefato no DISCO       `identity queue --limpar` apaga as linhas
                                 `done`; se a prova fosse a linha, uma limpeza
                                 de rotina deixaria o payoff pendente para
                                 sempre.
      2. linha ausente da fila   `identity run --slot character_weapon` sozinho
                                 declara dependencia que ninguem enfileirou.
      3. linha `done`            o caminho obvio.
      4. linha `failed`          nao se espera defunto. E de proposito que
                                 falha NAO se propaga para o dependente: o
                                 payoff sabe rodar sem referencia, e mata-lo
                                 junto tiraria o unico video que restou.
      5. prazo vencido           rede contra qualquer estado nao previsto. O
                                 prazo e ABSOLUTO (gravado no enqueue) e nunca
                                 renovado, senao rodadas mortas o empurrariam
                                 para frente para sempre.

    Roda dentro do lock que o `claim` ja segura, sobre a lista em memoria: sem
    I/O de fila e sem reentrar em `_bloqueio()`.
    """
    dependencias = job.get("depends_on") or []
    if not dependencias:
        return True
    por_id = {j["job_id"]: j for j in jobs}
    faltam = []
    for dependencia in dependencias:
        gid, slot = slots.partes(dependencia)
        if artefato.utilizavel(gid, slot):
            continue
        linha = por_id.get(dependencia)
        if linha is None or linha["status"] in (PRONTO, FALHOU):
            continue
        faltam.append(dependencia)
    if not faltam:
        return True
    prazo = job.get("aguardar_ate")
    return bool(prazo) and agora >= prazo


def _reivindicavel(job: dict, jobs: list[dict], max_attempts: int,
                   provedor: str | None, agora: str) -> bool:
    return (job["status"] == PENDENTE
            and job.get("attempts", 0) < max_attempts
            and (provedor is None or job.get("provider") == provedor)
            and _dependencias_satisfeitas(job, jobs, agora))


def tem_reivindicavel(max_attempts: int = 3) -> bool:
    """Ha job que o worker CONSEGUE pegar agora?

    Usa o MESMO predicado do claim de proposito. O modo `--watch` decide o
    recuo comparando "havia trabalho" com "algo saiu"; se um payoff bloqueado
    contasse como trabalho, toda rodada seria improdutiva, o backoff subiria
    ate o teto e o Chrome ficaria abrindo e fechando a toa.
    """
    agora = _agora()
    with _bloqueio():
        jobs = _ler()
        return any(_reivindicavel(j, jobs, max_attempts, None, agora)
                   for j in jobs)


def claim(max_attempts: int = 3, ignorar: set[str] | None = None,
          provedor: str | None = None) -> dict | None:
    """Pega o proximo job pendente e ja o marca como rodando.

    Marcar dentro do mesmo lock e o que impede dois workers de pegarem o mesmo
    job. Jobs `running` orfaos (worker morto) sao retomados por `reabrir`.

    `ignorar` sao os jobs ja adiados NESTA rodada. Sem isso um job que voltou
    para `pending` por ainda estar gerando e repescado em seguida, e a rodada
    vira ping-pong: o mesmo job a cada ~50 s, sem nunca dar tempo do Digen
    terminar.
    """
    ignorar = ignorar or set()
    agora = _agora()
    with _bloqueio():
        jobs = _ler()
        for job in jobs:
            if job["job_id"] in ignorar:
                continue
            if _reivindicavel(job, jobs, max_attempts, provedor, agora):
                job.update({"status": RODANDO,
                            "attempts": job.get("attempts", 0) + 1,
                            "updated_at": _agora()})
                _gravar(jobs)
                return dict(job)
    return None


def registrar_espaco(job_id: str, url: str) -> dict | None:
    """Grava o espaco do Digen onde o video esta sendo gerado.

    Gravado logo apos o envio, antes da espera: se o worker morrer (ou a espera
    estourar), a proxima tentativa RETOMA esse video em vez de gastar outra
    geracao pedindo o mesmo clipe de novo.
    """
    return _atualizar(job_id, {"space_url": url, "updated_at": _agora()})


def concluir(job_id: str, arquivo: str) -> dict | None:
    return _atualizar(job_id, {"status": PRONTO, "arquivo": arquivo,
                                      "error": None, "updated_at": _agora()})


def registrar_envio(job_id: str, url: str | None,
                    videos_antes: list | None,
                    enviado_em: str | None = None) -> dict | None:
    """Marca que o prompt DESTE slot foi enviado, e guarda o contexto.

    Gravado logo apos o envio, antes da espera: se o worker morrer (ou a espera
    estourar), a proxima tentativa RETOMA aquele video em vez de gastar outra
    geracao pedindo o mesmo clipe.
    """
    mudancas = {"enviado": True, "videos_antes": list(videos_antes or []),
                "enviado_em": enviado_em or _agora(), "updated_at": _agora()}
    if url:
        mudancas["space_url"] = url
    return _atualizar(job_id, mudancas)


def esquecer_envio(job_id: str) -> dict | None:
    """Descarta o video em voo: a proxima tentativa manda o prompt de novo.

    Usado quando aquele render falhou de verdade — sem isso o job ficaria
    preso retomando algo que nunca vai terminar. O ESPACO continua gravado: ele
    e da build, nao daquela tentativa, e os outros dois clipes ainda vao para
    dentro dele.
    """
    return _atualizar(job_id, {"enviado": False, "videos_antes": None,
                               "enviado_em": None, "updated_at": _agora()})


def espaco_da_geracao(generation_id: str) -> str | None:
    """O espaco que algum slot desta geracao ja criou, se houver.

    E o que faz personagem, arma e os dois juntos nascerem no mesmo espaco.
    """
    for job in listar():
        if job["generation_id"] != generation_id:
            continue
        url = job.get("space_url")
        if url and "/space/" in url:
            return url
    return None


def falhar(job_id: str, erro: str, max_attempts: int = 3) -> dict | None:
    """Volta para `pending` enquanto houver tentativa; depois congela em `failed`."""
    with _bloqueio():
        jobs = _ler()
        for job in jobs:
            if job["job_id"] == job_id:
                esgotou = job.get("attempts", 0) >= max_attempts
                job.update({"status": FALHOU if esgotou else PENDENTE,
                            "error": str(erro)[:500], "updated_at": _agora()})
                _gravar(jobs)
                return dict(job)
    return None


def reagendar(job_id: str, motivo: str) -> dict | None:
    """Volta para `pending` SEM gastar tentativa.

    Para o caso em que o video ainda esta na fila do Digen: nao houve falha,
    so demora. Descontar a tentativa aqui faria um render lento queimar as tres
    e o job morrer esperando algo que ia chegar.
    """
    with _bloqueio():
        jobs = _ler()
        for job in jobs:
            if job["job_id"] == job_id:
                job.update({"status": PENDENTE,
                            "attempts": max(job.get("attempts", 1) - 1, 0),
                            "error": str(motivo)[:500], "updated_at": _agora()})
                _gravar(jobs)
                return dict(job)
    return None


def reabrir() -> int:
    """Devolve jobs `running` orfaos para a fila (worker morto no meio).

    Devolve tambem a TENTATIVA. `claim` incrementa ao pegar o job; se o worker
    morre antes de concluir, essa tentativa nao produziu nada. Sem devolver, um
    job morto tres vezes chega a `attempts == max_attempts` e `claim` nunca
    mais o pega — ele fica `pending` para sempre, sem nunca ser processado e
    sem aparecer como falha.
    """
    with _bloqueio():
        jobs = _ler()
        reabertos = 0
        for job in jobs:
            if job["status"] == RODANDO:
                job.update({"status": PENDENTE,
                            "attempts": max(job.get("attempts", 1) - 1, 0),
                            "updated_at": _agora()})
                reabertos += 1
        if reabertos:
            _gravar(jobs)
        return reabertos


def limpar_concluidos() -> int:
    with _bloqueio():
        jobs = _ler()
        restantes = [j for j in jobs if j["status"] != PRONTO]
        removidos = len(jobs) - len(restantes)
        if removidos:
            _gravar(restantes)
        return removidos


def em_aberto_da_geracao(generation_id: str, ignorar_job: str | None = None) -> list[dict]:
    """Jobs daquela geracao que ainda podem produzir clipe.

    O worker usa para decidir QUANDO re-renderizar: refazer o video a cada um
    dos tres clipes custa tres renders completos (dois perfis cada) para
    entregar o mesmo resultado do ultimo. Com esta consulta, so o ultimo slot
    que fecha paga o render.
    """
    return [job for job in listar()
            if job["generation_id"] == generation_id
            and job["job_id"] != ignorar_job
            and job["status"] in (PENDENTE, RODANDO)]


def registrar_prompt(job_id: str, prompt: str,
                     referencias: list | None = None) -> dict | None:
    """Grava o texto que sera REALMENTE enviado, antes de enviar.

    O prompt do payoff depende de quantas imagens deram para anexar, e isso so
    se sabe na hora do envio. Gravar antes mantem a propriedade que a retomada
    depende: o que esta na fila e o que foi enviado — senao uma retomada
    mandaria um texto diferente do que gerou o video que esta em voo.
    """
    return _atualizar(job_id, {"prompt": prompt,
                               "referencias": referencias,
                               "updated_at": _agora()})
