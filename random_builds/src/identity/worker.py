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

from . import artefato, config, history, provedores, proveniencia, queue, slots
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


def _generation(generation_id: str) -> dict | None:
    """O generation.json daquela build, ou None se sumiu."""
    caminho = config.build_dir(generation_id) / "generation.json"
    if not caminho.is_file():
        return None
    try:
        with open(caminho, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _preparar_juncao(client, job: dict):
    """Abre o Editor Pro e sobe as DUAS imagens que serao compostas.

    O editor aceita as duas no mesmo campo, uma apos a outra (medido no DOM
    em 27/08/2026: ficam 'Remover imagem 1' e 'Remover imagem 2'). O que
    fazia parecer que a segunda substituia a primeira era o detector de
    anexo, que procurava miniatura `blob:` e nunca a encontrava — o worker
    desistia depois da primeira.

    Mandar as duas SEPARADAS e melhor que uma folha colada: o modelo recebe
    personagem e arma limpos, em vez de uma imagem com um painel no canto que
    o prompt ainda precisa pedir para remover.

    O prompt ja esta na fila (e o de juncao); o que muda aqui e a PAGINA e as
    imagens de entrada. Sem as duas no disco a juncao nao tem o que fazer.
    """
    from . import picasso_selectors, referencias
    gid = job["generation_id"]
    antes = client.preparar_espaco(picasso_selectors.URL_EDITOR)
    entradas = referencias.entradas_do_editor(gid)
    if len(entradas) < 2:
        raise GeracaoFalhou(
            f"a juncao precisa das duas imagens e achei {len(entradas)} "
            f"em {gid}.")
    anexadas = client.anexar_referencias(entradas)
    if len(anexadas) < 2:
        raise GeracaoFalhou(
            f"o editor confirmou {len(anexadas)} de 2 imagens; sem as duas a "
            "juncao sairia sem uma das identidades. Nada foi enviado.")
    return antes


def _texto_com_referencias(client, job: dict, ajustes: dict,
                           espaco: str | None) -> tuple[str, list, str | None]:
    """Prepara o espaco, ANEXA as imagens e so entao decide o texto.

    Esta e a ordem que importa. O prompt do payoff depende de quantas imagens
    deram para anexar, e isso so se sabe depois de tentar; decidir antes seria
    chutar. E o texto e gravado na fila ANTES do envio, para manter a
    propriedade de que a retomada reusa exatamente o que foi enviado — senao
    ela mandaria outro texto para o video que ja esta em voo.
    """
    from . import prompt as prompt_mod
    from . import referencias

    gid, job_id = job["generation_id"], job["job_id"]
    # ESPACO NOVO quando ha referencia a anexar, mesmo com o space da build
    # disponivel: o composer GUARDA o anexo entre envios (visto na tela em
    # 24/08), e uma miniatura sobrando de uma tentativa anterior condicionaria
    # o video na imagem errada sem nada acusar. Perder a companhia dos outros
    # clipes no mesmo space e barato; gerar o payoff a partir da imagem de
    # outra build nao e.
    from . import referencias as _ref
    tem_referencia = bool(_ref.disponiveis(
        gid, (ajustes.get("referencias") or {}).get("ordem")))
    antes = client.preparar_espaco(None if tem_referencia else espaco)

    generation = _generation(gid)
    if generation is None:
        # Sem o generation.json nao da para montar variante nenhuma: vai o
        # texto que ja estava na fila, que e o completo.
        return job["prompt"], antes, None

    ajustes_ref = ajustes.get("referencias") or {}
    ordem = ajustes_ref.get("ordem")

    # UMA folha com as duas identidades, porque o composer aceita uma imagem
    # e a segunda substitui a primeira. Sem as duas no disco, vai a que ha.
    folha = (referencias.folha_de_referencia(gid, ordem)
             if ajustes_ref.get("folha_unica", True) else None)
    if folha is not None:
        anexadas = client.anexar_referencias([folha])
        com_referencia = ([slots.CHARACTER, slots.WEAPON] if anexadas else [])
    else:
        anexadas = client.anexar_referencias(referencias.disponiveis(gid, ordem))
        com_referencia = [referencias.slot_do_arquivo(a) for a in anexadas]

    texto = prompt_mod.para_payoff(generation, ajustes, com_referencia)
    queue.registrar_prompt(job_id, texto, [str(a) for a in anexadas])
    reconhecidos = [s for s in com_referencia if s]
    print(f"[identity] payoff com {len(anexadas)} referencia(s) "
          f"[{', '.join(reconhecidos) or 'nenhuma reconhecida'}] "
          f"({len(texto)} chars de prompt)")
    # O MODELO muda junto com o texto, e pelo mesmo motivo: os dois dependem
    # de ter entrado imagem. Real Motion e text-to-video e ignora a referencia
    # — com ele o anexo "funciona" e o video sai com outro personagem, que foi
    # exatamente o que aconteceu em generation_00021.
    modelo = ajustes_ref.get("modelo") if anexadas else None
    if modelo:
        print(f"[identity] payoff com referencia -> modelo {modelo}")

    if len(reconhecidos) != len(anexadas):
        # Anexou e nao soube de qual slot era: o texto cai numa variante mais
        # longa do que precisava. Nao e fatal, mas e sintoma de nome de arquivo
        # fora do padrao — e ficar mudo aqui foi o que escondeu o bug.
        print("[identity] AVISO: nem toda referencia anexada foi reconhecida; "
              "o prompt usou a variante mais conservadora.")
    return texto, antes, modelo


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
              job_id: str | None = None, presets: dict | None = None,
              origem: dict | None = None) -> Path:
    """Grava os metadados do clipe e refaz o video da roleta com ele dentro.

    Separado de `processar` para poder ser chamado sobre um mp4 que ja esta no
    disco (download manual, retomada depois de queda) sem gerar de novo.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    meta_dir = config.identity_dir(generation_id)
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / f"{slot}.prompt.txt").write_text(prompt, encoding="utf-8")
    anterior = artefato.metadados(generation_id, slot) or {}
    registro = {
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
    }
    # A prova de origem e do DOWNLOAD, nao deste registro: um re-registro
    # feito do disco (retomada, resolucao sem browser) carrega a que ja
    # existia em vez de apaga-la.
    if origem is not None:
        registro["origem"] = origem
    else:
        for chave in ("origem", "quarentena"):
            if anterior.get(chave):
                registro[chave] = anterior[chave]
    with open(meta_dir / f"{slot}.json", "w", encoding="utf-8") as fh:
        json.dump(registro, fh, ensure_ascii=False, indent=2)

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
    # Space compartilhado e conceito do Digen: no PicassoIA cada geracao e uma
    # pagina so, e herdar a URL de um job irmao mandaria o editor para a tela
    # do criador.
    junto = (bool(ajustes.get("espaco_por_geracao", True))
             and slots.provedor(slot) == slots.DIGEN)
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
        texto = job["prompt"]
        enviado_em = _de_iso(job.get("enviado_em"))
        history.registrar(generation_id, history.RETOMADO, slot=slot,
                          space_url=espaco, tentativa=job.get("attempts"))
    else:
        print(f"[identity] {job_id}: gerando {slots.rotulo(slot)} ({aspecto})")
        texto, preparado, modelo = job["prompt"], None, None
        if slot == slots.REFERENCIA:
            preparado = _preparar_juncao(client, job)
        elif slot == slots.CHARACTER_WEAPON:
            texto, preparado, modelo = _texto_com_referencias(
                client, job, ajustes, espaco if junto else None)
        enviado_em = datetime.now(timezone.utc)
        antes = client.submit_prompt(
            texto, aspecto, modelo=modelo,
            duracao=preset_do_slot(ajustes, "duracao", slot),
            resolucao=preset_do_slot(ajustes, "resolucao", slot),
            espaco=espaco if junto else None, antes=preparado)
        # O texto que vale e o que ENTROU no campo (o aprimorador do
        # PicassoIA pode reescrever): e ele que o historico vai mostrar.
        texto = getattr(client, "prompt_enviado", None) or texto
        enviado_em = getattr(client, "enviado_em", None) or enviado_em
        queue.registrar_envio(job_id, client.url_do_espaco, antes,
                              enviado_em=enviado_em.isoformat(timespec="seconds"))
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

    # PROVA DE ORIGEM, antes de baixar qualquer byte. As contas sao
    # compartilhadas com outras pessoas: "apareceu depois do meu clique" nao
    # quer dizer "e meu" (generation_00044 gravou como referencia a foto de
    # outra pessoa, que entrou no historico 0,1 s depois do envio). Sem prova
    # nada e gravado; a tentativa conta como falha e a proxima gera de novo.
    prova = proveniencia.comprovar(client, generation_id, slot, texto,
                                   enviado_em, video, ajustes)
    if not prova.get("comprovada"):
        if proveniencia.exigida(ajustes):
            queue.esquecer_envio(job_id)
            history.registrar(generation_id, history.ORIGEM_RECUSADA, slot=slot,
                              motivo=str(prova.get("motivo"))[:200],
                              candidato=str(prova.get("candidato"))[:160])
            raise GeracaoFalhou(
                f"sem prova de origem para {slots.rotulo(slot)}: "
                f"{prova.get('motivo')}. Nada foi baixado; a proxima tentativa "
                "gera de novo.")
        print(f"[identity] AVISO: sem prova de origem ({prova.get('motivo')}); "
              "seguindo porque proveniencia.exigir=false.")
    alvo = prova.get("alvo") if prova.get("comprovada") else video
    if alvo is None:
        alvo = video
    if prova.get("candidato_descartado"):
        print(f"[identity] {job_id}: o resultado que apareceu primeiro nao era "
              "o nosso; baixando o que o historico atribui ao nosso prompt.")

    client.download(alvo, destino)

    # Guarda final: o provedor pode ter devolvido o artefato de OUTRO slot.
    # Falhar aqui e barato (a proxima tentativa gera de novo); aceitar seria
    # gravar a arma como copia do personagem e levar o erro para a juncao e
    # para o video.
    gemeo = artefato.duplicado_de(destino, generation_id, slot)
    if gemeo:
        destino.unlink(missing_ok=True)
        raise GeracaoFalhou(
            f"o arquivo baixado para {slot} e identico ao de {gemeo}: o site "
            "devolveu a imagem errada. Descartado.")

    if slot == slots.REFERENCIA:
        # O Editor Pro carimba texto no rodape mesmo proibido no prompt, e
        # essa imagem vira video: o carimbo iria junto.
        from . import referencias as _ref
        _ref.aparar_rodape(destino)

    proveniencia.reivindicar(prova, generation_id, slot)
    history.registrar(generation_id, history.BAIXADO, slot=slot,
                      bytes=destino.stat().st_size if destino.is_file() else 0,
                      origem=prova.get("forca"))

    caminho = registrar(generation_id, slot, destino, job["prompt"], aspecto,
                        rerender=rerender, preview=preview, job_id=job_id,
                        presets=client.presets_aplicados, origem=prova)
    history.registrar(generation_id, history.CONCLUIDO, slot=slot,
                      rerender=rerender, duracao_s=_duracao(destino))
    return caminho


def _de_iso(texto) -> datetime | None:
    """ISO gravado na fila -> datetime aware, ou None."""
    if not texto:
        return None
    try:
        quando = datetime.fromisoformat(str(texto))
    except ValueError:
        return None
    return quando if quando.tzinfo else quando.replace(tzinfo=timezone.utc)


class DeployDoDigen(RuntimeError):
    """Um seletor parou de casar: a rodada inteira e inutil ate ajustar."""


def _alertar_seletor(provedor: str = "digen") -> None:
    arquivo = ("src/identity/selectors.py" if provedor == "digen"
               else "src/identity/picasso_selectors.py")
    print("")
    print("=" * 66)
    print(f"  O SITE MUDOU ({provedor}): um seletor parou de casar.")
    print("  Nada vai andar ate isso ser ajustado. Rode, nesta ordem:")
    print("     python main.py identity doctor --online   (mostra qual quebrou)")
    print(f"     python main.py identity probe --provedor {provedor}")
    print(f"  e atualize a lista em {arquivo}.")
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


def _resolver_no_disco(rerender: bool, preview: bool) -> int:
    """Fecha, SEM abrir browser, todo job cujo trabalho ja esta no disco.

    Roda ANTES das passadas: marcar um job como feito nao precisa de browser, e
    abrir um so para descobrir isso e o que fazia a janela piscar. E e tambem o
    que LIBERA o payoff na mesma rodada — as duas imagens fecham aqui, e a
    passada do Digen ja encontra a dependencia satisfeita.

    Nao reivindica nada de proposito: reivindicar marcaria `running` um job que
    talvez nao fosse processado, e devolver depois custaria uma tentativa.
    Rodamos sob `instancia_unica`, entao ler e fechar em duas etapas e seguro.
    """
    from . import status

    resolvidos = 0
    for job in queue.listar():
        if job["status"] != queue.PENDENTE:
            continue
        gid = job["generation_id"]
        slot = job.get("slot", slots.CHARACTER)
        job_id = job.get("job_id") or slots.job_id(gid, slot)
        if status.esta_completo(gid, slot):
            print(f"[identity] {job_id}: ja completo no disco; so fechando.")
            queue.concluir(job_id, str(artefato.caminho(gid, slot)))
            resolvidos += 1
        elif status.clipe_utilizavel(gid, slot):
            print(f"[identity] {job_id}: artefato ja baixado; refazendo o "
                  "video sem abrir o browser.")
            destino = registrar(gid, slot, artefato.caminho(gid, slot),
                                job["prompt"], job.get("aspect") or "9:16",
                                rerender=rerender, preview=preview,
                                job_id=job_id)
            queue.concluir(job_id, str(destino))
            resolvidos += 1
    return resolvidos


def _drenar(headless: bool, rerender: bool, preview: bool,
            limite: int | None) -> int:
    """Uma rodada: pre-passe no disco e depois UMA passada por provedor.

    As passadas sao SEQUENCIAIS e irmas, nunca aninhadas: `contexto_persistente`
    abre o proprio `sync_playwright` por dentro, e dois no mesmo thread
    levantam "Playwright Sync API inside the asyncio loop". Sequencial tambem
    da de graca a ordem do grafo — quando a passada do Digen comeca, as imagens
    do PicassoIA ja estao no disco e o payoff passa no portao da fila.
    """
    reabertos = queue.reabrir()
    if reabertos:
        print(f"[identity] {reabertos} job(s) orfao(s) devolvido(s) a fila.")

    resolvidos = _resolver_no_disco(rerender, preview)
    if resolvidos:
        print(f"[identity] {resolvidos} job(s) fechado(s) pelo disco, "
              "sem abrir o browser.")

    concluidos = resolvidos
    quebrou: Exception | None = None
    for provedor in provedores.TODOS:
        if limite is not None and concluidos >= limite:
            break
        restante = None if limite is None else limite - concluidos
        try:
            feitos, erro = _passada(provedor, headless, rerender, preview,
                                    restante)
        except Exception as exc:
            # Falha de UM provedor nao leva o outro junto: a imagem pode ter
            # dado certo e o video ainda valer a tentativa, e vice-versa.
            print(f"[identity] passada de {provedores.rotulo(provedor)} "
                  f"falhou: {type(exc).__name__} {str(exc)[:160]}")
            continue
        concluidos += feitos
        quebrou = quebrou or erro

    if not concluidos:
        # Sair calado com job parado na fila e como nao ter rodado: quem olha
        # nao sabe se nao havia trabalho, se as tentativas acabaram ou se uma
        # dependencia esta segurando. Cada caso pede uma acao diferente.
        _explicar_parada()
    if quebrou is not None:
        raise DeployDoDigen(str(quebrou))
    return concluidos


def _explicar_parada() -> None:
    """Diz POR QUE a rodada nao produziu nada."""
    jobs = queue.listar()
    if not jobs:
        print("[identity] fila vazia.")
        return
    pendentes = [j for j in jobs if j["status"] == queue.PENDENTE]
    if not pendentes:
        estados = {}
        for job in jobs:
            estados[job["status"]] = estados.get(job["status"], 0) + 1
        print("[identity] nada pendente ("
              + ", ".join(f"{v} {k}" for k, v in sorted(estados.items())) + ").")
        return

    maximo = int(config.settings().get("max_attempts", 3))
    esgotados = [j for j in pendentes if j.get("attempts", 0) >= maximo]
    esperando = [j for j in pendentes if j.get("depends_on")
                 and j.get("attempts", 0) < maximo]
    print(f"[identity] {len(pendentes)} job(s) pendente(s) e nenhum "
          "reivindicavel agora.")
    for job in esgotados:
        print(f"[identity]   {job['job_id']}: tentativas esgotadas "
              f"({job['attempts']}/{maximo}) - reenfileire com "
              f"`identity run {job['generation_id']}` para zerar.")
    for job in esperando:
        faltam = [d for d in job["depends_on"]
                  if not artefato.utilizavel(*slots.partes(d))]
        if faltam:
            print(f"[identity]   {job['job_id']}: esperando "
                  + ", ".join(slots.partes(d)[1] for d in faltam)
                  + f" (prazo ate {job.get('aguardar_ate')})")


def _passada(provedor: str, headless: bool, rerender: bool, preview: bool,
             limite: int | None) -> tuple[int, Exception | None]:
    """Um browser, um perfil, um login: todos os jobs daquele provedor."""
    sel = provedores.seletores(provedor)
    ajustes = config.settings(provedor)
    max_attempts = int(ajustes.get("max_attempts", 3))
    min_interval = float(ajustes.get("min_interval", 45))
    rng = random.Random()

    # Jobs adiados NESTA passada: voltaram para `pending` porque a geracao
    # ainda esta em voo, e repesca-los agora so gastaria a rodada em ping-pong.
    adiados: set[str] = set()

    job = queue.claim(max_attempts, provedor=provedor)
    if job is None:
        return 0, None

    concluidos = 0
    quebrou: Exception | None = None
    print(f"[identity] --- passada: {provedores.rotulo(provedor)} ---")
    with contexto_persistente(headless=headless,
                              profile=config.profile_dir(provedor)) as ctx:
        page = pagina(ctx)
        ensure_logged_in(page, ajustes, rng, sel=sel, provedor=provedor)

        # O browser abre uma vez e serve todos os jobs da passada, entao o
        # client nao sabe de qual job e o espaco que acabou de aparecer: o loop
        # mantem essa informacao aqui e o callback so consulta.
        atual: dict[str, str | None] = {"job_id": None}

        def _guardar_espaco(url: str) -> None:
            if atual["job_id"]:
                queue.registrar_espaco(atual["job_id"], url)

        client = provedores.cliente(provedor, ctx, page, ajustes, rng,
                                    ao_descobrir_espaco=_guardar_espaco)

        saldo = client.creditos()
        if saldo is not None:
            print(f"[identity] creditos em {provedor}: {saldo}")
            if saldo <= 0:
                queue.falhar(job["job_id"],
                             f"conta sem creditos em {provedor}", max_attempts=0)
                print(f"[identity] {provedor} sem creditos: os jobs seguem na "
                      "fila para quando houver saldo.")
                return 0, None

        while job is not None:
            atual["job_id"] = job["job_id"]
            try:
                destino = processar(client, job, ajustes, rerender, preview)
                queue.concluir(job["job_id"], str(destino))
                concluidos += 1
                print(f"[identity] {job['job_id']}: OK -> {destino}")
            except BrowserMorreu as exc:
                # A aba morreu: o `page` que o client guarda esta morto para
                # SEMPRE, e todo job seguinte falharia em segundos contra ele.
                # Encerrar a passada faz o `with` fechar tudo; a proxima abre um
                # browser limpo e retoma de onde parou.
                queue.reagendar(job["job_id"], str(exc))
                print(f"[identity] {job['job_id']}: {exc}")
                print("[identity] encerrando a passada para abrir um browser "
                      "novo; a geracao continua acontecendo no site.")
                break
            except EsperaEstourou as exc:
                # Nao conta como falha: a geracao segue na fila do site e a
                # proxima passada retoma.
                queue.reagendar(job["job_id"], str(exc))
                adiados.add(job["job_id"])
                print(f"[identity] {job['job_id']}: ainda gerando; "
                      "retomo na proxima passada.")
            except Exception as exc:
                atualizado = queue.falhar(job["job_id"], str(exc), max_attempts)
                estado = (atualizado or {}).get("status", "?")
                history.registrar(job["generation_id"], history.FALHOU,
                                  slot=job.get("slot"), provedor=provedor,
                                  erro=str(exc)[:200], estado=estado,
                                  tipo=type(exc).__name__)
                print(f"[identity] {job['job_id']}: FALHOU ({estado}) {exc}")
                if isinstance(exc, SeletorNaoEncontrado):
                    # Assinatura de deploy do site. Em --watch isso se
                    # repetiria em silencio para sempre; melhor parar a passada
                    # e dizer o que fazer do que queimar a fila inteira.
                    _alertar_seletor(provedor)
                    quebrou = exc
                    break

            if limite is not None and concluidos >= limite:
                break
            job = queue.claim(max_attempts, adiados, provedor=provedor)
            if job is not None:
                espera = min_interval + rng.uniform(0, min_interval * 0.3)
                print(f"[identity] proximo job em {espera:.0f}s...")
                time.sleep(espera)
                pausa_humana(rng)

    return concluidos, quebrou


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
