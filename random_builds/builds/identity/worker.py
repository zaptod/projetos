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
import os
import random
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import (artefato, config, controle, history, provedores, proveniencia,
               queue, slots)
from .browser import contexto_persistente, pagina, pausa_humana
from .client import BrowserMorreu, DigenClient, EsperaEstourou, GeracaoFalhou
from .selectors import SeletorNaoEncontrado
from .session import ensure_logged_in


def _duracao(caminho: Path) -> float | None:
    from ..assets.importer import _probe_duration
    return _probe_duration(caminho)


def modelo_em_uso(ajustes: dict) -> str:
    """O modelo que o payoff vai pedir: o de referencia quando configurado,
    senao o de texto."""
    referencias = ajustes.get("referencias") or {}
    return str(referencias.get("modelo") or ajustes.get("modelo") or "")


def credito_bloqueia(ajustes: dict, provedor: str = "digen") -> bool:
    """Saldo zero impede de gerar? So quando o modelo em uso e PAGO.

    O contador do Digen mostra 0 para o plano Free, mas o Real Motion (a
    lista branca `modelos_permitidos`) e incluso no plano e continua
    gerando — o payoff nao custa credito. Abortar a passada por "sem
    creditos" deixava 27 de 64 builds sem payoff a toa. Um modelo fora da
    lista branca (Kling, Runway...) e cobrado por geracao: ai o saldo
    manda. `creditos_obrigatorios: true` na config forca o bloqueio antigo.
    """
    if ajustes.get("creditos_obrigatorios"):
        return True
    if provedor != "digen":
        return False
    permitidos = {str(m) for m in (ajustes.get("modelos_permitidos") or [])}
    modelo = modelo_em_uso(ajustes)
    return bool(permitidos) and modelo not in permitidos


def _rerender(generation_id: str, preview: bool = False) -> None:
    """Reconstroi o video da roleta agora que o clipe existe.

    `rerender` nunca re-rola a roleta: reusa o generation.json gravado. Com
    `refazer_edicao` a timeline e remontada de `RandomEngine(seed)` — sai
    identica, mais o evento `identity`.

    Roda em SUBPROCESSO, nao neste processo, por dois motivos medidos em
    29/08: (1) o worker em `--watch` fica dias de pe e um render em memoria
    usa o codigo de quando ele subiu — depois de uma atualizacao ele
    misturava modulos novos e velhos e entregava um plano antigo; (2) um
    render que estoura nao pode derrubar o worker nem travar a fila. O
    subprocesso le o codigo do disco e falha sozinho.
    """
    import subprocess
    import sys
    raiz = Path(__file__).resolve().parents[2]
    comando = [sys.executable, "-u", "-X", "utf8", "main.py", "generate-video",
               "--rerender", generation_id, "--refazer-edicao"]
    if preview:
        comando.append("--preview")
    print(f"[identity] re-renderizando {generation_id} com o clipe...", flush=True)
    try:
        resultado = subprocess.run(comando, cwd=str(raiz), timeout=3600,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[identity] re-render de {generation_id} nao rodou: {exc}", flush=True)
        return
    if resultado.returncode != 0:
        print(f"[identity] re-render de {generation_id} terminou com codigo "
              f"{resultado.returncode} (veja as linhas acima).", flush=True)


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


class EntradasFaltando(GeracaoFalhou):
    """A juncao foi pega sem as duas imagens no disco.

    Nao e falha do job: e cedo. O worker devolve o job para a fila SEM gastar
    tentativa (`queue.reagendar`) — em 04/10/2026 as juncoes da 00078, 00090,
    00095 e 00098 queimaram as tres tentativas assim e ficaram `failed` com a
    imagem que faltava chegando depois.
    """


# Assinatura da parede gravada no `error` da fila (ver `ParedeDePlanos`): as
# falhas antigas, de antes deste conserto, sao reconhecidas pelo texto.
_PAREDE_NO_ERRO = queue.PAREDE_NO_ERRO
# E a da juncao que foi pega sem as duas imagens (a mensagem de
# `EntradasFaltando`, igual a da falha antiga).
_FALTA_DE_ENTRADA_NO_ERRO = queue.FALTA_DE_ENTRADA_NO_ERRO

# Quanto tempo o provedor fica pausado depois da parede de planos. A conta
# volta sozinha (17/09/2026: reabrir o perfil resolveu) e a rodada seguinte
# tenta de novo; `pausa_na_parede_min` na config muda.
PAUSA_NA_PAREDE_MIN = 45.0

# As falhas da ultima `drenar` deste processo, uma linha por job. Quem le e a
# rodada de geracao (`pipeline/noite.py`), que dizia "fim: 0 erro(s)" com seis
# tentativas queimadas pela parede de planos no meio (04/10/2026 01:16).
_FALHAS: list[str] = []


def falhas_da_ultima_rodada() -> list[str]:
    """Copia das falhas registradas na ultima `drenar` deste processo."""
    return list(_FALHAS)


def _anotar_falha(job_id: str, exc: BaseException) -> None:
    _FALHAS.append(f"{job_id}: {type(exc).__name__}: {str(exc)[:140]}")


def _e_parede_de_planos(exc: BaseException) -> bool:
    try:
        from .picasso_client import ParedeDePlanos
    except Exception:                                   # noqa: BLE001
        return False
    return isinstance(exc, ParedeDePlanos)


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
    imagens de entrada. Sem as duas no disco a juncao nao tem o que fazer —
    e isso e conferido ANTES de mexer na pagina, e sai como `EntradasFaltando`
    (adiamento, nao falha).
    """
    from . import picasso_selectors, referencias
    gid = job["generation_id"]
    entradas = referencias.entradas_do_editor(gid)
    if len(entradas) < 2:
        raise EntradasFaltando(
            f"a juncao precisa das duas imagens e achei {len(entradas)} "
            f"em {gid}.")
    antes = client.preparar_espaco(picasso_selectors.URL_EDITOR)
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
        # Job de um slot DESLIGADO (payoff_video=false) nao segura o render:
        # ele nunca vai fechar.
        ativos = set(config.jobs_ativos())
        return any(job.get("slot") in ativos
                   for job in queue.em_aberto_da_geracao(generation_id,
                                                         ignorar_job=job_id))
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


class CorreioOcupado(GeracaoFalhou):
    """As contas do rodizio estao com outra pipeline (ou fora de cota): nao
    houve tentativa, so espera. O job volta SEM gastar tentativa e a passada
    para (sem isto tres noites de historias ocupando o Gemini e o ChatGPT
    matavam o job de imagem sem ele ter sido pedido uma vez)."""


class CorreioSemAmbiente(RuntimeError):
    """O pacote `ias` (correio, carteiro) nao importa neste processo. E o
    AMBIENTE, nao o job: nao gasta tentativa nem marca failed; a passada para
    e a falha vai ao resumo da rodada. Conferencia de 07/10/2026: rodando de
    `random_builds/` (como o gerar.cmd), "No module named 'ias'" era engolido
    pelo `except Exception` da passada e 35 de 51 jobs queimaram 3/3 em
    segundos."""


# Falha do correio que e espera, e nao tentativa (`Carteiro._falhar`).
_CATEGORIAS_DE_ESPERA = ("conta_ocupada", "rodizio")

# De quanto em quanto tempo o worker volta a olhar as contas do rodizio.
PASSO_CONTA_S = 20.0
_dormir = time.sleep

# Folga da proporcao pedida. O Gemini entrega 1536x2752 (0,558) para 9:16
# (0,5625): 0,8% fora. Acima de 3% e outro formato (1:1, 3:4, 16:9).
FOLGA_PROPORCAO = 0.03

_RAIZ_DO_REPO = Path(__file__).resolve().parents[3]
# Ja no import do worker, como em `historias/contos/imagens/worker.py`: quem
# importa o worker (o gerar.cmd, de dentro de random_builds/) acha o `ias`.
if str(_RAIZ_DO_REPO) not in sys.path:
    sys.path.append(str(_RAIZ_DO_REPO))


def _importar_ias():
    """(correio, carteiro, imagem) do pacote `ias`, que mora na RAIZ do
    repositorio e nao e instalado. Rodando de `random_builds/` a raiz nao esta
    no sys.path: o mesmo conserto de `historias/contos/imagens/worker.py`
    (04/10/2026). Se ainda assim nao importar: `CorreioSemAmbiente`."""
    raiz = str(_RAIZ_DO_REPO)
    if raiz not in sys.path:
        sys.path.append(raiz)
    try:
        from ias import carteiro, correio, imagem
    except Exception as exc:                                   # noqa: BLE001
        raise CorreioSemAmbiente(
            f"o pacote ias nao importa ({type(exc).__name__}: {exc}); "
            f"raiz do repositorio {raiz}") from exc
    return correio, carteiro, imagem


def _tempo_legivel(segundos: float) -> str:
    segundos = max(0.0, float(segundos))
    if segundos < 90:
        return f"{segundos:.0f} s"
    if segundos < 5400:
        return f"{segundos / 60:.0f} min"
    return f"{segundos / 3600:.1f} h".replace(".0 h", " h").replace(".", ",")


def _pedido_reaproveitavel(mensagem: dict, correio) -> bool:
    """O pedido gravado no job ainda pode dar a imagem desta tentativa?

    Respondido: sim (a imagem esta no correio; a retomada so copia). Pendente
    e livre para mim: sim (o carteiro entrega o MESMO pedido). Falhou, ou
    entregue por um processo que morreu no meio: nao — reusar o id so
    devolveria a mesma falha a cada tentativa ate o job morrer sem ter pedido
    de novo. Entregue por um processo VIVO: `CorreioOcupado` (outro esta
    gerando agora; pedir de novo geraria duas vezes)."""
    situacao = mensagem.get("situacao")
    if situacao == "respondida":
        return True
    if situacao == "pendente":
        return not correio.reservado_por_outro(mensagem)
    if situacao == "entregue":
        quem = correio._entregador(mensagem)
        if quem and quem != os.getpid() and correio._pid_vivo(quem) is not False:
            raise CorreioOcupado(
                f"o pedido {mensagem.get('id')} esta sendo entregue pelo processo {quem}")
        return False
    return False


def _geradores_em_condicao(aspecto: str, correio, carteiro, imagem) -> tuple[list, list]:
    """Os geradores do rodizio que podem gerar ESTA imagem agora, do que gerou
    ha mais tempo ao mais recente, e os motivos dos que ficaram de fora. So
    gerador de chat: e o que recebe as referencias da juncao e o que da a
    prova da casa (o turno que e nosso)."""
    horas = float(carteiro.config().get("cota_pausa_h", 6))
    candidatos, motivos = [], []
    for g in imagem.rodizio_ordem():
        info = imagem.gerador(g)
        rotulo = info.get("rotulo") or g
        if g not in correio.CHATS:
            motivos.append(f"{rotulo}: nao gera pelo chat")
            continue
        if not info.get("disponivel"):
            motivos.append(f"{rotulo}: {str(info.get('motivo') or '')[:90]}")
            continue
        if aspecto not in (info.get("proporcoes") or ()):
            motivos.append(f"{rotulo}: nao faz {aspecto}")
            continue
        fora = imagem.fora_de_cota(g, horas)
        if fora:
            motivos.append(f"{rotulo}: {fora}")
            continue
        candidatos.append(g)
    return candidatos, motivos


@contextmanager
def _conta_do_rodizio(aspecto: str, espera_s: float, correio, carteiro, imagem):
    """Segura a trava da CONTA de um gerador do rodizio antes de o pedido
    existir e devolve o gerador.

    A espera pela conta acontece AQUI, e nao dentro do correio: la ela virava
    `falhou` na caixa livre do app, `erro` no diario e alerta no Telegram
    ("ocupadas por 0 h", conferencia de 07/10/2026). A trava e reentrante
    por thread, entao o Carteiro, no mesmo thread, a pega na hora. Ninguem
    livre ate `espera_s`, ou ninguem em condicao: `CorreioOcupado`, sem
    pedido criado."""
    import builds.travas as travas

    inicio = time.monotonic()
    while True:
        candidatos, motivos = _geradores_em_condicao(aspecto, correio, carteiro, imagem)
        if not candidatos:
            raise CorreioOcupado("nenhum gerador do rodizio pode gerar agora: "
                                 + ("; ".join(motivos) or "rodizio vazio")[:400])
        for g in candidatos:
            with travas.trava(travas.do_perfil(g, "geral"), esperar=0.0) as minha:
                if minha:
                    yield g
                    return
        if time.monotonic() - inicio >= espera_s:
            raise CorreioOcupado(
                f"as contas do rodizio ({', '.join(candidatos)}) seguiram com outra "
                f"pipeline por {_tempo_legivel(time.monotonic() - inicio)}; "
                "o job volta para a fila")
        _dormir(PASSO_CONTA_S)


def _proporcao(aspecto: str) -> float | None:
    try:
        largura, altura = (float(x) for x in str(aspecto).split(":"))
        return largura / altura if largura > 0 and altura > 0 else None
    except (TypeError, ValueError):
        return None


def _gravar_como_png(origem: Path, destino: Path, aspecto: str) -> None:
    """Grava a imagem do correio no destino como PNG DE VERDADE e confere a
    forma. O Gemini baixa JPEG (`.jfif`) e a build guarda `*.png`: a copia
    crua deixava um JPEG com nome de PNG (conferencia de 07/10/2026).
    Forma fora de `aspecto` (com `FOLGA_PROPORCAO`) levanta `GeracaoFalhou`
    sem gravar nada."""
    from PIL import Image

    with Image.open(origem) as aberta:
        aberta.load()
        largura, altura = aberta.size
        alvo = _proporcao(aspecto)
        if alvo and altura:
            desvio = abs((largura / altura) / alvo - 1.0)
            if desvio > FOLGA_PROPORCAO:
                raise GeracaoFalhou(
                    f"a imagem do correio veio {largura}x{altura}, fora de {aspecto} "
                    f"({desvio * 100:.0f}% de desvio). Descartada.")
        modo = "RGBA" if aberta.mode in ("RGBA", "LA", "P") else "RGB"
        convertida = aberta.convert(modo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".parcial")
    convertida.save(temporario, format="PNG")
    os.replace(temporario, destino)


def _motivo_de_colagem(caminho: Path) -> str:
    """O detector de colagem das historias (`composicao.motivo`: calha
    atravessando a imagem). Medido em 07/10/2026 nas 202 imagens de
    identidade das builds: nenhuma marcada. Sem o detector: "" (avisa)."""
    try:
        from contos.imagens import composicao
    except Exception as exc:                                   # noqa: BLE001
        print(f"[identity] AVISO: sem o detector de colagem ({type(exc).__name__}); "
              "so a proporcao foi conferida.")
        return ""
    try:
        return composicao.motivo(caminho)
    except Exception:                                          # noqa: BLE001
        return ""


def processar_correio(job: dict, ajustes: dict, rerender: bool = True,
                      preview: bool = False, prazo: float | None = None) -> Path:
    """Pede imagem pelo correio e aceita somente o arquivo provado da casa.

    O id do pedido fica no job ANTES de o pedido existir: a retomada (worker
    morto no meio) consulta o MESMO pedido em vez de gerar outra imagem. Um
    pedido que falhou (ou cujo entregador morreu) nao e reaproveitado: a
    proxima tentativa nasce com id novo. Reenfileirar zera o id
    (`queue.enqueue`): "faca de novo" nunca devolve a imagem antiga."""
    correio, carteiro, imagem = _importar_ias()
    from . import referencias, status

    generation_id = job["generation_id"]
    slot = job.get("slot", slots.CHARACTER)
    job_id = job.get("job_id") or slots.job_id(generation_id, slot)
    destino = artefato.caminho(generation_id, slot)
    aspecto = job.get("aspect") or ajustes.get("aspect", "9:16")
    if status.esta_completo(generation_id, slot):
        return destino
    if status.clipe_utilizavel(generation_id, slot):
        return registrar(generation_id, slot, destino, job["prompt"], aspecto,
                         rerender=rerender, preview=preview, job_id=job_id)

    anexos = []
    if slot == slots.REFERENCIA:
        entradas = referencias.entradas_do_editor(generation_id)
        if len(entradas) != 2:
            raise EntradasFaltando(
                f"a juncao precisa das duas imagens e achei {len(entradas)} em {generation_id}.")
        # Dentro do teto de anexo do correio (8 MB): a imagem do Gemini em PNG
        # passa de 6 MB; acima de 1536 px ela sobe reduzida, em JPEG.
        pasta = config.identity_dir(generation_id) / "anexos_correio"
        anexos = [referencias.para_upload(e, pasta) for e in entradas]

    mensagem_id = str(job.get("correio_id") or "")
    pedido = correio.uma(correio.LIVRE, mensagem_id) if mensagem_id else None
    if pedido is not None and not _pedido_reaproveitavel(pedido, correio):
        print(f"[identity] {job_id}: pedido {mensagem_id} ficou "
              f"{pedido.get('situacao')}; peco de novo com outro id.")
        pedido, mensagem_id = None, ""
    if pedido is not None and pedido.get("situacao") == "respondida":
        atual = pedido                                  # retomada: so copiar
    else:
        # Espera pela conta (as historias usam as mesmas): limitada e, com
        # prazo, nunca alem dele. Estourar e `CorreioOcupado`, sem tentativa.
        espera_conta = float(ajustes.get("espera_conta_correio_s", 1800))
        if prazo is not None:
            espera_conta = min(espera_conta, max(60.0, float(prazo) - time.time()))
        with _conta_do_rodizio(aspecto, espera_conta, correio, carteiro,
                               imagem) as gerador:
            if pedido is None:
                mensagem_id = mensagem_id or correio.novo_id()
                queue.registrar_correio(job_id, mensagem_id)
                pedido = correio.pedir_imagem(
                    correio.LIVRE, job["prompt"], proporcao=aspecto, de="random_builds",
                    dono=os.getpid(), anexos=anexos, mensagem_id=mensagem_id)
            print(f"[identity] {job_id}: pedido {mensagem_id} ao {gerador} "
                  f"({len(anexos)} anexo(s))")
            resposta = carteiro.Carteiro(
                ajustes={"resposta_timeout_s": float(ajustes.get("espera_correio_s", 420)),
                         "janela_conversa_s": 0, "rodizio_imagem": [gerador],
                         "espera_conta_max_s": 60.0},
                avisar=lambda _texto: False,
                avisar_arquivo=lambda _caminho, _legenda: False).entregar(pedido)
        atual = correio.uma(correio.LIVRE, mensagem_id) or resposta or {}
    if (atual.get("situacao") == "falhou"
            and atual.get("categoria") in _CATEGORIAS_DE_ESPERA):
        raise CorreioOcupado(str(atual.get("erro") or "as contas do rodizio estao ocupadas"))
    resumo = atual.get("imagem") if isinstance(atual.get("imagem"), dict) else {}
    origem = correio.arquivo_da_imagem(correio.LIVRE, mensagem_id)
    if (atual.get("situacao") != "respondida" or not resumo.get("prova")
            or origem is None or not origem.is_file()):
        if atual.get("situacao") == "respondida":
            queue.registrar_correio(job_id, "")      # resposta inutil: a proxima pede de novo
        raise GeracaoFalhou(str(atual.get("erro") or "o correio nao entregou imagem com prova"))
    try:
        registro = json.loads(origem.with_suffix(".prova.json").read_text(encoding="utf-8"))
        prova = registro.get("prova") if isinstance(registro, dict) else None
    except (OSError, ValueError):
        prova = None
    if not isinstance(prova, dict) or not prova.get("comprovada"):
        queue.registrar_correio(job_id, "")
        raise GeracaoFalhou("imagem do correio sem prova de origem")
    try:
        _gravar_como_png(origem, destino, aspecto)
    except GeracaoFalhou:
        queue.registrar_correio(job_id, "")
        raise
    except Exception as exc:                                   # noqa: BLE001
        queue.registrar_correio(job_id, "")
        raise GeracaoFalhou(f"a imagem do correio nao abre ({type(exc).__name__}: "
                            f"{str(exc)[:120]})") from exc
    colagem = _motivo_de_colagem(destino)
    if colagem:
        destino.unlink(missing_ok=True)
        queue.registrar_correio(job_id, "")
        raise GeracaoFalhou(f"{slots.rotulo(slot)}: {colagem} Descartada.")
    gemeo = artefato.duplicado_de(destino, generation_id, slot)
    if gemeo:
        destino.unlink(missing_ok=True)
        queue.registrar_correio(job_id, "")
        raise GeracaoFalhou(
            f"o arquivo baixado para {slot} e identico ao de {gemeo}: "
            "o correio devolveu a imagem errada. Descartado.")
    gerador = str(atual.get("gerador") or "correio")
    history.registrar(generation_id, history.PRONTO, slot=slot,
                      provedor=gerador, pedido=mensagem_id)
    # A prova da casa + QUAL pedido do correio e QUAL gerador: a auditoria
    # liga a imagem da build a mensagem que a trouxe.
    origem_da_build = dict(prova, pedido_correio=mensagem_id, gerador=gerador)
    caminho = registrar(generation_id, slot, destino, job["prompt"], aspecto,
                        rerender=rerender, preview=preview, job_id=job_id,
                        origem=origem_da_build)
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
           preview: bool = False, limite: int | None = None, *,
           so_provedor: str | None = None,
           prazo: float | None = None) -> int:
    """Processa os pendentes e retorna quantos concluiram.

    Roda como INSTANCIA UNICA: se ja houver worker, esta chamada nao faz nada.
    Dois workers se sabotam: o `reabrir` de um rouba o job que o outro esta
    processando, e o mesmo video acaba baixado duas vezes.

    `so_provedor`: so a passada daquele provedor (quem chama sabe quanto tempo
    um job DELE leva: imagem do PicassoIA ~3-6 min, payoff do Digen 12-15 min).
    `prazo` (epoch, `time.time()`): depois dele nenhum job NOVO comeca — nem
    uma nova tentativa do mesmo. O job em andamento termina. Sem os dois, o
    worker de sempre.
    """
    # Limpa ANTES da trava: com outro worker de pe esta chamada volta 0, e a
    # rodada da noite (uma `drenar` por provedor no mesmo processo) contaria
    # de novo as falhas da chamada anterior.
    _FALHAS.clear()
    with queue.instancia_unica() as sozinho:
        if not sozinho:
            print("[identity] outro worker ja esta rodando; nada a fazer.")
            return 0
        return _drenar(headless, rerender, preview, limite,
                       so_provedor=so_provedor, prazo=prazo)


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

    _reabrir_falhas_superadas()
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


def _reabrir_falhas_superadas() -> int:
    """Devolve a fila o job `failed` cuja causa ja nao existe.

    Dois casos, os dois medidos em 05/10/2026 (`queue.json`):

    - JUNCAO com as duas imagens no disco. `generation_00078`, `00090` e
      `00095` morreram com "achei 1 imagem" e a imagem que faltava chegou
      depois; `failed` era terminal e as builds ficavam sem a imagem do
      personagem com a arma para sempre (00090 e 00095: fora da fila de
      publicacao por pendencia).
    - PAREDE DE PLANOS. `generation_00098` personagem e arma "falharam" 3
      vezes cada em 22 s (04/10 01:16) — a conta, nao o job. Desde este
      conserto a parede e pausa (`_passada`), e as falhas antigas com essa
      assinatura voltam como se tivessem sido pausa.

    So reabre o que ainda falta: juncao cujo arquivo ja existe fica como esta.
    Nunca levanta (roda antes de toda passada).

    O criterio e `queue.motivo_para_reabrir` — o MESMO que `noite` usa para
    decidir se chama o worker (`queue.reabriveis`). Build descartada ou ja
    publicada fica de fora (`queue.fora_da_reabertura`): a 00078 esta no ar e
    reabrir a juncao dela gastaria uma imagem e um re-render a toa.
    """
    reabertos = 0
    try:
        candidatos = queue.reabriveis()
    except Exception:                                   # noqa: BLE001
        return 0
    for job in candidatos:
        gid = job.get("generation_id", "")
        slot = job.get("slot", slots.CHARACTER)
        job_id = job.get("job_id") or slots.job_id(gid, slot)
        motivo = queue.motivo_para_reabrir(job) or "causa superada"
        try:
            queue.reabrir_falha(job_id, motivo)
        except Exception:                               # noqa: BLE001
            continue
        reabertos += 1
        print(f"[identity] {job_id}: reaberto ({motivo}).")
    return reabertos


def _drenar(headless: bool, rerender: bool, preview: bool,
            limite: int | None, *, so_provedor: str | None = None,
            prazo: float | None = None) -> int:
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
        if so_provedor is not None and provedor != so_provedor:
            continue
        if limite is not None and concluidos >= limite:
            break
        if _prazo_vencido(prazo):
            print("[identity] prazo da rodada: nenhuma passada nova.")
            break
        restante = None if limite is None else limite - concluidos
        try:
            feitos, erro = _passada(provedor, headless, rerender, preview,
                                    restante, prazo=prazo)
        except Exception as exc:
            # Falha de UM provedor nao leva o outro junto: a imagem pode ter
            # dado certo e o video ainda valer a tentativa, e vice-versa.
            print(f"[identity] passada de {provedores.rotulo(provedor)} "
                  f"falhou: {type(exc).__name__} {str(exc)[:160]}")
            _anotar_falha(f"passada de {provedores.rotulo(provedor)}", exc)
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


def _prazo_vencido(prazo: float | None) -> bool:
    """Passou da hora de COMECAR trabalho novo? Sem prazo, nunca."""
    return prazo is not None and time.time() >= float(prazo)


def _passada(provedor: str, headless: bool, rerender: bool, preview: bool,
             limite: int | None,
             prazo: float | None = None) -> tuple[int, Exception | None]:
    """Um browser, um perfil, um login: todos os jobs daquele provedor.

    Com `prazo`, nenhum job (nem nova tentativa) comeca depois dele. Existe
    pela rodada noturna (27/09/2026): um job que falha volta para a fila e e
    reivindicado de novo NA MESMA passada, entao `limite=1` nao limitava o
    tempo — tres tentativas de uma imagem cabem em 15 min, e depois delas a
    passada ainda pegava o proximo job.
    """
    if _prazo_vencido(prazo):
        return 0, None
    if provedor == slots.CORREIO:
        return _passada_correio(rerender, preview, limite, prazo=prazo)
    sel = provedores.seletores(provedor)
    ajustes = config.settings(provedor)
    if controle.pausado_para(provedor):
        # Pausado: nem abre o browser. A conta do site pode estar em uso por
        # outra pessoa — o pior que a pipeline pode fazer e entrar no meio.
        print(f"[identity] {provedor} PAUSADO ({controle.estado()['resumo']}); "
              "nenhum job novo sera pego.", flush=True)
        return 0, None
    if provedor == "digen" and not config.payoff_video_ativo(ajustes):
        print("[identity] payoff em video DESLIGADO (payoff_video=false em "
              "config/identity.json): o Digen nao e aberto; a montagem usa a "
              "imagem personagem+arma.", flush=True)
        return 0, None
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
    parede: Exception | None = None
    print(f"[identity] --- passada: {provedores.rotulo(provedor)} ---")
    from contextlib import ExitStack

    from .. import atividade, travas
    nome_trava = travas.do_perfil(provedor, "builds")
    pilha = ExitStack()
    if not pilha.enter_context(travas.trava(nome_trava, esperar=15.0)):
        pilha.close()
        queue.reagendar(job["job_id"], f"perfil {nome_trava} em uso")
        print(f"[identity] {provedores.rotulo(provedor)}: o perfil "
              f"({nome_trava}) esta em uso por outro processo; esta passada "
              "fica para a proxima rodada.")
        return 0, None
    pilha.enter_context(atividade.fabrica(
        provedor, f"fila de {provedores.rotulo(provedor)}"))
    with pilha, contexto_persistente(headless=headless,
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
            if saldo <= 0 and credito_bloqueia(ajustes, provedor):
                queue.falhar(job["job_id"],
                             f"conta sem creditos em {provedor}", max_attempts=0)
                _anotar_falha(job["job_id"], RuntimeError(
                    f"conta sem creditos em {provedor}"))
                print(f"[identity] {provedor} sem creditos: os jobs seguem na "
                      "fila para quando houver saldo.")
                return 0, None
            if saldo <= 0:
                print(f"[identity] {provedor} com saldo 0, mas o modelo em uso e "
                      "incluso no plano: segue gerando (se o site recusar, o job "
                      "falha sozinho).")

        while job is not None:
            if controle.parada_pedida():
                print("[identity] parada pedida: encerrando depois deste job.",
                      flush=True)
                queue.reagendar(job["job_id"], "parada pedida pelo operador")
                break
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
            except EntradasFaltando as exc:
                # Cedo, nao falha: a imagem que falta ainda pode chegar.
                queue.reagendar(job["job_id"], str(exc))
                adiados.add(job["job_id"])
                print(f"[identity] {job['job_id']}: {exc} Volta para a fila "
                      "sem gastar tentativa.")
            except Exception as exc:
                if _e_parede_de_planos(exc):
                    # A CONTA, nao o job: o proximo job bateria na mesma
                    # parede (04/10/2026 01:16: seis tentativas em 22 s).
                    # Pausa o provedor com prazo, como falta de credito, e o
                    # job volta para a fila sem gastar tentativa.
                    _parar_na_parede(provedor, job, exc, ajustes)
                    parede = exc
                    break
                atualizado = queue.falhar(job["job_id"], str(exc), max_attempts)
                estado = (atualizado or {}).get("status", "?")
                _anotar_falha(job["job_id"], exc)
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
            if _prazo_vencido(prazo):
                print("[identity] prazo da rodada: nenhum job novo nesta "
                      "passada; o resto fica para a proxima.", flush=True)
                break
            job = queue.claim(max_attempts, adiados, provedor=provedor)
            if job is not None:
                espera = min_interval + rng.uniform(0, min_interval * 0.3)
                print(f"[identity] proximo job em {espera:.0f}s...")
                time.sleep(espera)
                pausa_humana(rng)

    if parede is not None:
        # DEPOIS do `with`: a fabrica anota `ok` ao sair limpa, e o ultimo
        # evento do provedor tem de ser o erro (a Vila e a apuracao leem o
        # ultimo). Sem `ref`: a parede e da conta, nao conserto de codigo.
        atividade.registrar(provedor, atividade.ERRO,
                            f"{type(parede).__name__}: {str(parede)[:200]}",
                            etapa="identity.parede_de_planos")
    return concluidos, quebrou


def _passada_correio(rerender: bool, preview: bool, limite: int | None,
                     prazo: float | None = None) -> tuple[int, Exception | None]:
    """Drena as imagens sem abrir o navegador dos provedores antigos."""
    if controle.pausado_para(slots.CORREIO):
        print(f"[identity] correio PAUSADO ({controle.estado()['resumo']}); "
              "nenhum job novo sera pego.", flush=True)
        return 0, None
    try:
        # ANTES de pegar job: sem o pacote `ias` nenhum job anda, e nao e
        # culpa de nenhum deles (nao gasta tentativa, nao marca failed).
        _importar_ias()
    except CorreioSemAmbiente as exc:
        print(f"[identity] passada do correio NAO rodou: {exc}", flush=True)
        _anotar_falha("passada do correio (ambiente)", exc)
        return 0, None
    ajustes = config.settings()
    max_attempts = int(ajustes.get("max_attempts", 3))
    concluidos = 0
    adiados: set[str] = set()
    job = queue.claim(max_attempts, provedor=slots.CORREIO)
    while job is not None:
        if controle.parada_pedida():
            queue.reagendar(job["job_id"], "parada pedida pelo operador")
            break
        try:
            destino = processar_correio(job, ajustes, rerender, preview, prazo=prazo)
            queue.concluir(job["job_id"], str(destino))
            concluidos += 1
            print(f"[identity] {job['job_id']}: OK pelo correio -> {destino}")
        except CorreioOcupado as exc:
            # Espera, nao falha: devolve sem gastar tentativa e encerra a
            # passada (os proximos jobs esbarrariam nas mesmas contas).
            queue.reagendar(job["job_id"], str(exc))
            print(f"[identity] {job['job_id']}: correio ocupado ({exc}); fica para "
                  "a proxima rodada.")
            break
        except (CorreioSemAmbiente, ImportError) as exc:
            # Ambiente quebrado no meio (modulo que nao importa): o job nao
            # tem culpa. Volta sem gastar tentativa, a passada para e avisa.
            queue.reagendar(job["job_id"], f"ambiente: {exc}")
            _anotar_falha(f"{job['job_id']} (ambiente)", exc)
            print(f"[identity] {job['job_id']}: ambiente quebrado ({type(exc).__name__}: "
                  f"{exc}); a passada do correio para.", flush=True)
            break
        except EntradasFaltando as exc:
            queue.reagendar(job["job_id"], str(exc))
            adiados.add(job["job_id"])
        except Exception as exc:
            atualizado = queue.falhar(job["job_id"], str(exc), max_attempts)
            _anotar_falha(job["job_id"], exc)
            history.registrar(job["generation_id"], history.FALHOU,
                              slot=job.get("slot"), provedor=slots.CORREIO,
                              erro=str(exc)[:200],
                              estado=(atualizado or {}).get("status", "?"),
                              tipo=type(exc).__name__)
            print(f"[identity] {job['job_id']}: FALHOU pelo correio ({exc})")
        if limite is not None and concluidos >= limite:
            break
        if _prazo_vencido(prazo):
            break
        job = queue.claim(max_attempts, adiados, provedor=slots.CORREIO)
    return concluidos, None


def _parar_na_parede(provedor: str, job: dict, exc: BaseException,
                     ajustes: dict) -> None:
    """Parede de planos: pausa o provedor com prazo e devolve o job intacto."""
    job_id = job["job_id"]
    minutos = float(ajustes.get("pausa_na_parede_min", PAUSA_NA_PAREDE_MIN)
                    or PAUSA_NA_PAREDE_MIN)
    queue.reagendar(job_id, f"pausado: {exc}")
    _anotar_falha(job_id, exc)
    try:
        controle.pausar(provedor, motivo=f"parede de planos em "
                        f"{provedores.rotulo(provedor)} (conta sem plano?)",
                        minutos=minutos)
    except Exception:                                   # noqa: BLE001
        pass
    history.registrar(job["generation_id"], history.FALHOU,
                      slot=job.get("slot"), provedor=provedor,
                      erro=str(exc)[:200], estado="pausado",
                      tipo=type(exc).__name__)
    print(f"[identity] {job_id}: {exc}")
    print(f"[identity] {provedores.rotulo(provedor)} pausado por "
          f"{minutos:.0f} min; o job volta para a fila sem gastar tentativa "
          "e nenhum outro job deste provedor comeca agora.", flush=True)


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
    if queue.ha_worker():
        # Sair, e nao ficar em loop cedendo a trava: o processo ocioso nao
        # ajuda em nada e ainda esconde qual worker esta realmente de pe.
        print("[identity] JA existe um worker de pe; este nao vai subir. "
              "(Para trocar de worker, pare o outro primeiro.)")
        return
    ajustes = config.settings()
    intervalo = float(ajustes.get("watch_interval", 30))
    teto = float(ajustes.get("watch_backoff_max", 600))
    improdutivas = 0
    print(f"[identity] modo watch (poll a cada {intervalo:.0f}s). Ctrl+C para sair.")
    atual = controle.estado()
    if atual["situacao"] != controle.RODANDO:
        print(f"[identity] atencao: a pipeline esta {atual['resumo']}.")
    try:
        anunciado = None
        while True:
            if controle.parada_pedida():
                print("[identity] parada pedida: o watch vai encerrar.")
                controle.limpar_parada()
                break
            situacao = controle.estado()
            if situacao["situacao"] == controle.PAUSADO:
                # Pausado nao e rodada improdutiva: nao infla o recuo, so
                # espera o intervalo normal e avisa UMA vez por mudanca.
                if situacao["resumo"] != anunciado:
                    print(f"[identity] {situacao['resumo']} — esperando.")
                    anunciado = situacao["resumo"]
                time.sleep(intervalo)
                continue
            anunciado = None
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
