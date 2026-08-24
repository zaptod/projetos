"""Drena a fila de identidade: prompt -> Digen -> mp4 -> re-render do video.

A unidade de trabalho e o SLOT (personagem, arma, personagem+arma), nao a
geracao. Os tres clipes de uma mesma build sao tres jobs independentes: o
payoff final pode falhar sem levar junto o clipe de personagem que ja tinha
dado certo.

Um job por vez e com intervalo entre eles. Nao e so furtividade: e nao
martelar um servico gratuito. O browser abre UMA vez e serve todos os jobs da
rodada — reabrir o Chrome a cada job e lento e chama atencao.
"""
from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from . import artefato, config, history, queue, slots
from .browser import contexto_persistente, pagina, pausa_humana
from .client import BrowserMorreu, DigenClient, EsperaEstourou, GeracaoFalhou
from .selectors import SeletorNaoEncontrado
from .session import ensure_logged_in


def _duracao(caminho: Path) -> float | None:
    from ..assets.importer import _probe_duration
    return _probe_duration(caminho)


def _rerender(generation_id: str, preview: bool = False) -> None:
    """Reconstroi o video da roleta agora que o clipe existe.

    `rerender` nunca re-rola a roleta: reusa o generation.json gravado. Com
    `refazer_edicao` a timeline e remontada de `RandomEngine(seed)` — sai
    identica, mais o evento `identity`.
    """
    from ..pipeline.controller import PipelineController
    print(f"[identity] re-renderizando {generation_id} com o clipe...")
    PipelineController().rerender(generation_id, preview=preview,
                                  refazer_edicao=True)


def preset_do_slot(ajustes: dict, chave: str, slot: str):
    """Preferencia daquele slot, com queda para a global.

    Cada clipe tem uma janela propria na montagem (5 s de personagem, 4 s de
    arma, 6 s do payoff), entao pedir "max" para os tres faz o Digen gerar
    material que a edicao joga fora — e demorar mais para entregar.
    """
    por_slot = ajustes.get(f"{chave}_por_slot") or {}
    return por_slot.get(slot, ajustes.get(chave))


def _falta_algum_slot(generation_id: str, job_id: str) -> bool:
    """Ainda ha outro clipe desta geracao a caminho?

    Refazer o video a cada um dos tres clipes custa tres renders completos
    (dois perfis cada) para chegar no mesmo resultado do ultimo. Entao so o
    ultimo slot que fecha paga o render; os anteriores so gravam o arquivo.
    """
    try:
        return bool(queue.em_aberto_da_geracao(generation_id, ignorar_job=job_id))
    except Exception:
        # Fila ilegivel nao pode impedir o render: melhor renderizar a mais.
        return False


def registrar(generation_id: str, slot: str, destino: Path, prompt: str,
              aspecto: str, rerender: bool = True, preview: bool = False,
              job_id: str | None = None, presets: dict | None = None) -> Path:
    """Grava os metadados do clipe e refaz o video da roleta com ele dentro.

    Separado de `processar` para poder ser chamado sobre um mp4 que ja esta no
    disco (download manual, retomada depois de queda) sem gerar de novo.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    meta_dir = config.identity_dir(generation_id)
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / f"{slot}.prompt.txt").write_text(prompt, encoding="utf-8")
    with open(meta_dir / f"{slot}.json", "w", encoding="utf-8") as fh:
        json.dump({
            "generation_id": generation_id,
            "slot": slot,
            "arquivo": destino.name,
            "aspecto": aspecto,
            "duracao": _duracao(destino),
            # O que os controles do Digen MOSTRAVAM no envio. Sem registro,
            # "esse clipe saiu com 3 s" vira discussao em vez de consulta.
            "presets": presets or {},
            "prompt": prompt,
            "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, fh, ensure_ascii=False, indent=2)

    if rerender:
        if _falta_algum_slot(generation_id,
                             job_id or slots.job_id(generation_id, slot)):
            print(f"[identity] {generation_id}: {slots.rotulo(slot)} pronto; "
                  "render fica para quando o ultimo clipe chegar.")
        else:
            _rerender(generation_id, preview=preview)
    return destino


def processar(client: DigenClient, job: dict, ajustes: dict,
              rerender: bool = True, preview: bool = False) -> Path:
    from . import status

    generation_id = job["generation_id"]
    slot = job.get("slot", slots.CHARACTER)
    job_id = job.get("job_id") or slots.job_id(generation_id, slot)
    destino = artefato.caminho(generation_id, slot)
    aspecto = job.get("aspect") or ajustes.get("aspect", "9:16")
    espaco = job.get("space_url")
    junto = bool(ajustes.get("espaco_por_geracao", True))
    if junto and not espaco:
        # Os tres clipes da build no MESMO espaco: o slot que chega depois
        # entra no espaco que o primeiro criou.
        espaco = queue.espaco_da_geracao(generation_id)

    # O disco manda mais que a fila. Um job pode estar `pending` com o trabalho
    # ja feito (worker morto depois do download, fila reescrita por outro
    # processo); regerar nesse caso desperdicia uma geracao e sobrescreve um
    # clipe que estava certo.
    if status.esta_completo(generation_id, slot):
        print(f"[identity] {job_id}: ja completo no disco; so fechando.")
        return destino
    if status.clipe_utilizavel(generation_id, slot):
        print(f"[identity] {job_id}: clipe ja baixado; "
              "pulando a geracao e refazendo o video.")
        return registrar(generation_id, slot, destino, job["prompt"], aspecto,
                         rerender=rerender, preview=preview, job_id=job_id)

    if job.get("enviado") and espaco and "/space/" in espaco:
        # Retomada: o video daquele espaco pode so estar demorando na fila.
        # Reenviar o prompt criaria um SEGUNDO video do mesmo personagem.
        # `enviado` (e nao a mera existencia do espaco) e o que marca isso: o
        # espaco pode existir so porque OUTRO slot da mesma build o criou.
        client.abrir_espaco(espaco)
        antes = job.get("videos_antes") or []
        history.registrar(generation_id, history.RETOMADO, slot=slot,
                          space_url=espaco, tentativa=job.get("attempts"))
    else:
        print(f"[identity] {job_id}: gerando {slots.rotulo(slot)} ({aspecto})")
        antes = client.submit_prompt(
            job["prompt"], aspecto,
            duracao=preset_do_slot(ajustes, "duracao", slot),
            resolucao=preset_do_slot(ajustes, "resolucao", slot),
            espaco=espaco if junto else None)
        queue.registrar_envio(job_id, client.url_do_espaco, antes)
        history.registrar(generation_id, history.ENVIADO, slot=slot, aspecto=aspecto,
                          space_url=client.url_do_espaco,
                          prompt_chars=len(job["prompt"]),
                          presets=client.presets_aplicados,
                          tentativa=job.get("attempts"))

    inicio = time.monotonic()
    try:
        video = client.wait_for_render(antes=antes)
        history.registrar(generation_id, history.PRONTO, slot=slot,
                          espera_s=round(time.monotonic() - inicio, 1))
    except EsperaEstourou:
        # A URL pode ter aparecido so durante a espera: guardar agora e o que
        # permite a proxima tentativa retomar em vez de regerar.
        if client.url_do_espaco and "/space/" in client.url_do_espaco:
            queue.registrar_espaco(job_id, client.url_do_espaco)
        history.registrar(generation_id, history.ESTOUROU, slot=slot,
                          espera_s=round(time.monotonic() - inicio, 1),
                          space_url=client.url_do_espaco)
        raise
    except GeracaoFalhou as exc:
        # Falha de verdade (sem credito, modelo recusou): aquele espaco nao vai
        # produzir nada, entao a proxima tentativa precisa gerar de novo.
        queue.esquecer_envio(job_id)
        history.registrar(generation_id, history.FALHOU, slot=slot,
                          erro=str(exc)[:200],
                          espera_s=round(time.monotonic() - inicio, 1))
        raise

    client.download(video, destino)
    history.registrar(generation_id, history.BAIXADO, slot=slot,
                      bytes=destino.stat().st_size if destino.is_file() else 0)

    caminho = registrar(generation_id, slot, destino, job["prompt"], aspecto,
                        rerender=rerender, preview=preview, job_id=job_id,
                        presets=client.presets_aplicados)
    history.registrar(generation_id, history.CONCLUIDO, slot=slot,
                      rerender=rerender, duracao_s=_duracao(destino))
    return caminho


class DeployDoDigen(RuntimeError):
    """Um seletor parou de casar: a rodada inteira e inutil ate ajustar."""


def _alertar_seletor() -> None:
    print("")
    print("=" * 66)
    print("  O DIGEN MUDOU: um seletor parou de casar com a pagina.")
    print("  Nada vai andar ate isso ser ajustado. Rode, nesta ordem:")
    print("     python main.py identity doctor --online   (mostra qual quebrou)")
    print("     python main.py identity probe             (despeja o DOM novo)")
    print("  e atualize a lista em src/identity/selectors.py.")
    print("=" * 66)
    print("")


def drenar(headless: bool = False, rerender: bool = True,
           preview: bool = False, limite: int | None = None) -> int:
    """Processa os pendentes e retorna quantos concluiram.

    Roda como INSTANCIA UNICA: se ja houver worker, esta chamada nao faz nada.
    Dois workers se sabotam: o `reabrir` de um rouba o job que o outro esta
    processando, e o mesmo video acaba baixado duas vezes.
    """
    with queue.instancia_unica() as sozinho:
        if not sozinho:
            print("[identity] outro worker ja esta rodando; nada a fazer.")
            return 0
        return _drenar(headless, rerender, preview, limite)


def _resolver_no_disco(max_attempts: int, rerender: bool,
                       preview: bool) -> tuple[int, dict | None]:
    """Fecha os jobs cujo trabalho ja existe e devolve o primeiro que falta.

    Roda ANTES de abrir o Chrome: marcar um job como feito nao precisa de
    browser, e abrir um so para descobrir isso e o que fazia a janela piscar.
    """
    from . import status

    resolvidos = 0
    while True:
        job = queue.claim(max_attempts)
        if job is None:
            return resolvidos, None
        gid = job["generation_id"]
        slot = job.get("slot", slots.CHARACTER)
        job_id = job.get("job_id") or slots.job_id(gid, slot)
        if status.esta_completo(gid, slot):
            print(f"[identity] {job_id}: ja completo no disco; so fechando.")
            queue.concluir(job_id, str(artefato.caminho(gid, slot)))
            resolvidos += 1
            continue
        if status.clipe_utilizavel(gid, slot):
            print(f"[identity] {job_id}: clipe ja baixado; refazendo o video "
                  "sem abrir o browser.")
            destino = registrar(gid, slot, artefato.caminho(gid, slot),
                                job["prompt"], job.get("aspect") or "9:16",
                                rerender=rerender, preview=preview, job_id=job_id)
            queue.concluir(job_id, str(destino))
            resolvidos += 1
            continue
        return resolvidos, job


def _drenar(headless: bool, rerender: bool, preview: bool,
            limite: int | None) -> int:
    ajustes = config.settings()
    max_attempts = int(ajustes.get("max_attempts", 3))
    min_interval = float(ajustes.get("min_interval", 45))
    rng = random.Random()

    reabertos = queue.reabrir()
    if reabertos:
        print(f"[identity] {reabertos} job(s) orfao(s) devolvido(s) a fila.")

    # Jobs adiados nesta rodada: voltaram para `pending` porque o video ainda
    # esta sendo gerado, e repesca-los agora so gastaria a rodada em ping-pong.
    adiados: set[str] = set()

    # PRE-PASSE SEM BROWSER: resolve tudo que ja esta pronto no disco antes de
    # abrir o Chrome. Sem isso, um job que so precisava ser marcado como feito
    # abria e fechava o browser a toa — em `--watch` isso vira um ciclo visivel
    # de janelas piscando.
    resolvidos, job = _resolver_no_disco(max_attempts, rerender, preview)
    if job is None:
        if resolvidos:
            print(f"[identity] {resolvidos} job(s) fechado(s) pelo disco, "
                  "sem abrir o browser.")
        else:
            print("[identity] fila vazia.")
        return resolvidos

    concluidos = resolvidos
    quebrou: Exception | None = None
    with contexto_persistente(headless=headless) as ctx:
        page = pagina(ctx)
        ensure_logged_in(page, ajustes, rng)

        # O browser abre uma vez e serve todos os jobs, entao o client nao sabe
        # de qual geracao e o espaco que acabou de aparecer: o loop mantem essa
        # informacao aqui e o callback so consulta.
        atual: dict[str, str | None] = {"job_id": None}

        def _guardar_espaco(url: str) -> None:
            if atual["job_id"]:
                queue.registrar_espaco(atual["job_id"], url)

        client = DigenClient(ctx, page, ajustes, rng,
                             ao_descobrir_espaco=_guardar_espaco)

        saldo = client.creditos()
        if saldo is not None:
            print(f"[identity] creditos disponiveis: {saldo}")
            if saldo <= 0:
                queue.falhar(job["job_id"],
                             "conta sem creditos no Digen", max_attempts=0)
                print("[identity] sem creditos: nada a fazer. Os jobs seguem "
                      "na fila para quando houver saldo.")
                return 0

        while job is not None:
            atual["job_id"] = job["job_id"]
            try:
                destino = processar(client, job, ajustes, rerender, preview)
                queue.concluir(job["job_id"], str(destino))
                concluidos += 1
                print(f"[identity] {job['job_id']}: OK -> {destino}")
            except BrowserMorreu as exc:
                # A aba morreu: o `page` que o client guarda esta morto para
                # SEMPRE, e todo job seguinte falharia em segundos contra ele
                # (visto em 22/08: loop de 50 em 50 s sem sair do lugar).
                # Encerrar a rodada faz o `with` fechar tudo; a proxima abre um
                # browser limpo e retoma o mesmo espaco.
                queue.reagendar(job["job_id"], str(exc))
                print(f"[identity] {job['job_id']}: {exc}")
                print("[identity] encerrando a rodada para abrir um browser "
                      "novo; o video continua sendo gerado no Digen.")
                break
            except EsperaEstourou as exc:
                # Nao conta como falha: o video segue na fila do Digen e a
                # proxima passada retoma o mesmo espaco.
                queue.reagendar(job["job_id"], str(exc))
                adiados.add(job["job_id"])
                print(f"[identity] {job['job_id']}: ainda gerando; "
                      "retomo na proxima passada.")
            except Exception as exc:
                atualizado = queue.falhar(job["job_id"], str(exc), max_attempts)
                estado = (atualizado or {}).get("status", "?")
                history.registrar(job["generation_id"], history.FALHOU,
                                  slot=job.get("slot"), erro=str(exc)[:200],
                                  estado=estado, tipo=type(exc).__name__)
                print(f"[identity] {job['job_id']}: FALHOU ({estado}) {exc}")
                if isinstance(exc, SeletorNaoEncontrado):
                    # Assinatura de deploy do Digen. Em --watch isso se
                    # repetiria em silencio para sempre; melhor parar a rodada
                    # e dizer o que fazer do que queimar a fila inteira.
                    _alertar_seletor()
                    quebrou = exc
                    break

            if limite is not None and concluidos >= limite:
                break
            job = queue.claim(max_attempts, adiados)
            if job is not None:
                espera = min_interval + rng.uniform(0, min_interval * 0.3)
                print(f"[identity] proximo job em {espera:.0f}s...")
                time.sleep(espera)
                pausa_humana(rng)

    if quebrou is not None:
        raise DeployDoDigen(str(quebrou))
    return concluidos


def _tem_pendente() -> bool:
    """Ha job que o worker CONSEGUE pegar? (nao so `pending` no papel)

    Delega para o MESMO predicado do claim. Um payoff esperando as imagens
    fica `pending` e nao e reivindicavel; se ele contasse como trabalho, toda
    rodada seria "havia trabalho e nada saiu", o recuo do `--watch` subiria ate
    o teto e o Chrome ficaria abrindo e fechando a esmo.
    """
    maximo = int(config.settings().get("max_attempts", 3))
    return queue.tem_reivindicavel(maximo)


def observar(headless: bool = False, rerender: bool = True,
             preview: bool = False) -> None:
    """Fica em pe drenando a fila; Ctrl+C para sair.

    Recua quando a rodada abre o browser e nao conclui nada. Sem isso um job
    que nao consegue avancar vira um ciclo de abrir e fechar o Chrome a cada
    poucos segundos, para sempre — barulhento, inutil e alarmante de assistir.

    O recuo so vale para rodada IMPRODUTIVA (havia trabalho e nada saiu). Fila
    vazia mantem o intervalo normal, senao um job novo demoraria minutos para
    ser notado.
    """
    ajustes = config.settings()
    intervalo = float(ajustes.get("watch_interval", 30))
    teto = float(ajustes.get("watch_backoff_max", 600))
    improdutivas = 0
    print(f"[identity] modo watch (poll a cada {intervalo:.0f}s). Ctrl+C para sair.")
    try:
        while True:
            havia = _tem_pendente()
            feitos = drenar(headless=headless, rerender=rerender, preview=preview)
            if feitos or not havia:
                improdutivas = 0
                espera = intervalo
            else:
                improdutivas += 1
                espera = min(intervalo * 2 ** min(improdutivas, 5), teto)
                print(f"[identity] rodada sem progresso ({improdutivas}); "
                      f"proxima em {espera:.0f}s.")
            time.sleep(espera)
    except DeployDoDigen:
        # Insistir de 30 em 30 s com o seletor quebrado so enche o log e gasta
        # as tentativas de todo job da fila.
        print("[identity] watch encerrado: conserte os seletores e rode de novo.")
    except KeyboardInterrupt:
        print("\n[identity] encerrado.")
