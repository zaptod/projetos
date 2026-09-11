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
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"
CONFIG = RAIZ / "config" / "agenda.json"

# Uma so rodada automatica por vez, em qualquer processo desta maquina.
TRAVA = "historias__auto"
# Horas aceitas no config: hora cheia, 0 a 23.
HORAS_VALIDAS = range(24)


def carregar(caminho: Path | None = None) -> dict:
    with open(caminho or CONFIG, encoding="utf-8-sig") as fh:
        dados = json.load(fh)
    horas = sorted({int(h) for h in (dados.get("horas") or [])
                    if int(h) in HORAS_VALIDAS})
    dados["horas"] = horas
    return dados


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
                      "estoque cheio"):
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
    """Quantos videos novos podem esperar na fila: UM DIA de grade.

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
    horas = config.get("horas") or []
    return len(horas) or 8


def dias_de_estoque_novo() -> int:
    """Dias de video pronto feitos com a ABORDAGEM ATUAL.

    E este o numero que decide se vale criar mais, e nao o estoque total. O
    estoque velho (Gemini Flash, sem molde, sem revisao, sem alavancas) e
    RESERVA: serve para o canal nao ficar mudo se a criacao parar, mas nao e
    motivo para deixar de produzir o que esta melhor. Em 08/09/2026 eram 38
    dias de video antigo — contra um teto de 45, sobrariam sete dias de folga
    para o jeito novo, e as melhorias apareceriam a conta-gotas.

    A marca e `modelo_llm` no roteiro, gravada desde que o modelo passou a ser
    escolhido de proposito. Historia sem a marca e do tempo antigo.
    """
    from ..publicar import catalogo, serie
    from ..roteiro import roteiro as R

    try:
        ja = {linha.get("video_id") for linha in serie.publicados()
              if linha.get("url")}
    except Exception:                                          # noqa: BLE001
        ja = set()
    novas = set()
    for resumo in R.listar():
        if (resumo.get("modelo_llm") or "").strip():
            novas.add(resumo["historia_id"])
    return len([v for v in catalogo.listar()
                if v.id not in ja and v.perfil == "celular"
                and v.fonte_id in novas])


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
              if linha.get("url")}
    except Exception:                                          # noqa: BLE001
        ja = set()
    return len([v for v in catalogo.listar()
                if v.id not in ja and v.perfil == "celular"])


def rodar(*, config: dict | None = None, headless: bool = False,
          tela=print) -> dict:
    """Uma rodada. Devolve o que aconteceu — nunca levanta por conta da tarefa.

    O Agendador nao le excecao: o que ele ve e o codigo de saida. Entao aqui
    tudo vira dicionario e log, e quem decide o codigo de saida e o `main.py`.
    """
    from builds import travas
    from builds.identity import controle

    config = config or carregar()
    agora = datetime.now()
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
                resultado = _trabalhar(config, headless, print)
            except Exception as exc:                           # noqa: BLE001
                # A rodada nao pode morrer calada: o unico jeito de descobrir
                # seria abrir o log, e quem abre o log ja desconfiou de algo.
                print(f"[auto] a rodada quebrou: {type(exc).__name__}: {exc}")
                resultado = {"feito": "nada", "motivo": "a rodada quebrou",
                             "erro": f"{type(exc).__name__}: {exc}"}
                if config.get("avisar_telegram", True):
                    avisar(mensagem(resultado, time.monotonic() - comeco))
                raise
            if resultado.get("erros") or resultado.get("motivo") not in (
                    None, "", "ja rodando", "pausado", "agenda desligada",
                    "estoque cheio"):
                # TODO ERRO NO MESMO LUGAR. `atividade.jsonl` e o ledger de
                # onde o bot tira os alertas e onde a apuracao automatica
                # procura o que investigar. As etapas ja registravam (imagens,
                # LLM); a rodada em si nao, entao uma falha DELA nao chegava
                # nem no Telegram nem no Claude.
                _registrar_erro(resultado)
            if config.get("avisar_telegram", True):
                texto = mensagem(resultado, time.monotonic() - comeco)
                if texto:
                    avisar(texto)
            return resultado
        finally:
            sys.stdout, sys.stderr = anterior_out, anterior_err


def _trabalhar(config: dict, headless: bool, log) -> dict:
    from .controller import Pipeline

    pipeline = Pipeline()

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
                                  headless, log)
        if pendentes:
            alvo = pendentes[0]
            log(f"[auto] terminando {alvo['historia_id']} antes de criar "
                f"outra: {alvo['imagens_faltando']} imagem(ns) e "
                f"{len(alvo['partes_sem_video'])} video(s) pendentes.")
            return _terminar(pipeline, alvo["historia_id"], headless, log,
                             criada=False)

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
    teto = teto_de_estoque(config)
    if teto:
        estoque = dias_de_estoque_novo()
        if estoque >= teto:
            log(f"[auto] ja ha {estoque} video(s) novo(s) na fila "
                f"(teto: {teto} = um dia de grade). Nao crio mais ate baixar.")
            return {"feito": "nada", "motivo": "estoque cheio",
                    "estoque": estoque}

    log(f"[auto] criando historia nova via {config.get('provedor')} "
        f"({config.get('partes')} partes de {config.get('cenas_por_parte')} "
        "cenas)...")
    try:
        criada = pipeline.gerar(
            provedor=str(config.get("provedor") or "gemini"),
            partes=int(config.get("partes") or 6),
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
    return _terminar(pipeline, historia_id, headless, log, criada=True)


def _retomar_texto(pipeline, historia_id: str, faltam: list,
                   headless: bool, log) -> dict:
    """Escreve as partes que faltam e so entao segue para imagem e video."""
    from ..roteiro import gerar as G
    from ..roteiro import roteiro as R

    config = carregar()
    try:
        G.retomar_serie(historia_id, provedor=str(config.get("provedor")
                                                  or "gemini"),
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
    return _terminar(pipeline, historia_id, headless, log, criada=False)


def _terminar(pipeline, historia_id: str, headless: bool, log,
              *, criada: bool) -> dict:
    """Imagens que faltam e depois os videos. Cada etapa reporta o que deu."""
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
