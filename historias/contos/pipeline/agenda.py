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


# A JANELA DO TRABALHO PESADO. Pedido dele em 13/09/2026: "fazer o trabalho
# pesado de madrugada e deixar os ajustes e deliverys para o dia". Pesado e o
# que abre navegador e segura a maquina por horas: roteiro, imagem, render,
# parecer do Gemini, conserto, metrica do TikTok. De dia a maquina so publica
# e avisa.
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
    """
    from datetime import timedelta

    if janela and int(agora.hour) < int(janela["fim"]) % 24:
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


def modo_dia(config: dict, agora) -> dict | None:
    """O que a rodada faz fora da janela. `None` quando nao ha nada a fazer.

    Conserta sempre que ha video barrado: esperar a madrugada deixava a fila
    parada o dia inteiro. Cria historia so se faltar video para o dia.
    Metrica e revisao do estoque continuam so de madrugada.
    """
    barrados = len(barrados_no_estoque())
    aprovados = len(aprovados_no_estoque())
    urgente = falta_video(aprovados, agora,
                          int(config.get("piso_de_estoque") or 1))
    if not barrados and not urgente:
        return None
    motivos = []
    if barrados:
        motivos.append(f"{barrados} video(s) barrado(s)")
    if urgente:
        motivos.append(f"so {aprovados} aprovado(s) para "
                       f"{horarios_restantes(agora)} horario(s) de hoje")
    return {"por_que": " e ".join(motivos),
            "config": {**config, "janela_pesada": None,
                       "revisar_estoque_a_noite": False,
                       "retomar_incompletas": urgente,
                       "reparos_por_rodada":
                           int(config.get("reparos_de_dia") or 2),
                       "so_consertar": not urgente}}


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
        if motivo in ("ja rodando", "pausado", "agenda desligada", "fora da janela",
                    "sem tempo na janela", "so consertar",
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
    # Da GRADE DE PUBLICACAO, e nao dos disparos de criacao. Eram a mesma
    # lista ate 13/09/2026; com a criacao so de madrugada (7 disparos), contar
    # os disparos daria teto 7 para uma grade que consome 8 por dia.
    from builds import grade
    return len(grade.HORAS) or 8


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
    return len(aprovados_no_estoque())


def aprovados_no_estoque() -> list:
    """Os videos PRONTOS E PUBLICAVEIS feitos com a abordagem atual."""
    from ..publicar import catalogo, qualidade, serie
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
    return aprovados


def barrados_no_estoque() -> list:
    """`[(video, motivos)]` do que esta pronto mas a vistoria nao deixa sair.

    E a lista que o reparador consome. Sai daqui, e nao de uma varredura
    propria, para o reparo olhar exatamente o que a grade olha.
    """
    from ..publicar import catalogo, qualidade, serie
    from ..roteiro import roteiro as R

    try:
        ja = {linha.get("video_id") for linha in serie.publicados()
              if linha.get("url")}
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

    janela = config.get("janela_pesada")
    if not na_janela(agora.hour, janela):
        # DE DIA SO O QUE EVITA FICAR SEM VIDEO. Pedido dele em 13/09/2026,
        # logo depois de montar a rotina de madrugada: "esse tipo de problema
        # eu quero que seja resolvido a qualquer momento, a prioridade e nao
        # ficar sem video". Fora da janela a rodada nao coleta metrica nem
        # revisa o estoque: ela conserta o que esta barrado e, se o estoque
        # aprovado nao cobre o resto do dia, cria historia tambem.
        dia = modo_dia(config, agora)
        if not dia:
            log(f"[auto] fora da janela do trabalho pesado "
                f"({int(janela['inicio']):02d}h as {int(janela['fim']):02d}h),"
                " sem video barrado e com estoque para o dia. Saindo.")
            return {"feito": "nada", "motivo": "fora da janela"}
        log(f"[auto] fora da janela, mas {dia['por_que']}: sigo em modo dia.")
        config = dia["config"]

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
                    None, "", "ja rodando", "pausado", "agenda desligada", "fora da janela",
                    "sem tempo na janela", "so consertar",
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


def _servico_da_noite(config: dict, headless: bool, log) -> None:
    """O que so a madrugada faz. Nunca derruba a rodada: e servico.

    1. METRICA do YouTube e do TikTok, uma vez por noite. Estava na primeira
       postagem do dia, as 06:07, e a coleta do TikTok segura o Studio por
       ate 12 minutos: era trabalho pesado caindo na hora em que o dia comeca.
    2. PARECER DO GEMINI em todo video pendente sem veredito numerado por
       cena. De dia a postagem so LE o que a madrugada decidiu.
    """
    from datetime import datetime as _relogio

    janela = config.get("janela_pesada")
    try:
        from builds.publicar import metricas
        chave = f"noite-{chave_da_noite(_relogio.now(), janela)}"
        if metricas.atualizar_uma_vez_por_dia(log=log, chave=chave):
            log("[auto] metricas da noite atualizadas.")
    except Exception as exc:                                   # noqa: BLE001
        log(f"[auto] a metrica da noite falhou: {type(exc).__name__}: {exc}")
    if config.get("revisar_estoque_a_noite", True):
        try:
            revisar_estoque(config, headless=headless, log=log)
        except Exception as exc:                               # noqa: BLE001
            log(f"[auto] a revisao do estoque falhou: "
                f"{type(exc).__name__}: {exc}")


def revisar_estoque(config: dict, *, headless: bool = False,
                    log=print) -> dict:
    """Parecer do Gemini para cada video pendente sem veredito numerado.

    Para quando a janela aperta. Video que ja tem veredito por cena e pulado,
    aprovado ou nao: o aprovado esta pronto e o reprovado e do reparador.
    """
    from datetime import datetime as _relogio

    from ..publicar import catalogo, parecer, qualidade, serie
    from ..roteiro import roteiro as R
    from . import conserto_de_cena as C

    janela = config.get("janela_pesada")
    margem = float(config.get("minutos_minimos") or 90)
    ja = {l.get("video_id") for l in serie.publicados() if l.get("url")}
    pendentes = [v for v in catalogo.listar()
                 if v.perfil == "celular" and v.id not in ja]
    revisados = aprovados = pulados = 0
    for video in pendentes:
        if minutos_ate_fechar(_relogio.now(), janela) < margem:
            log("[auto] a janela esta fechando; paro a revisao do estoque.")
            break
        # ATUAL, e nao so numerado: veto dado com o criterio velho do parecer
        # e perguntado de novo aqui, com a regua de hoje.
        if C.atual(parecer.lembrado(video)):
            pulados += 1
            continue
        # UMA PASSADA SO NO GEMINI (15/09/2026): video que ja foi olhado uma
        # vez nao volta, nem depois de consertado (o mp4 novo zera o
        # `lembrado`, mas a passada dele ja foi gasta).
        if parecer.ja_olhado(video):
            pulados += 1
            continue
        roteiro = R.carregar(video.fonte_id)
        laudo = qualidade.vistoriar_parte(video.fonte_id, video.parte,
                                          video.caminho, roteiro)
        if not laudo.get("ok"):
            pulados += 1
            continue
        try:
            veredito = parecer.pedir(video, roteiro, video.parte, laudo=laudo,
                                     headless=headless, log=log)
        except parecer.SemParecer as exc:
            log(f"[auto] {video.id}: sem parecer agora ({exc}).")
            continue
        revisados += 1
        aprovados += 1 if veredito.get("aprovado") else 0
    if revisados:
        log(f"[auto] revisei {revisados} video(s) do estoque de madrugada; "
            f"{aprovados} aprovado(s).")
    return {"revisados": revisados, "aprovados": aprovados,
            "pulados": pulados}


def _trabalhar(config: dict, headless: bool, log) -> dict:
    from .controller import Pipeline

    pipeline = Pipeline()
    janela = config.get("janela_pesada")
    if janela:
        sobra = minutos_ate_fechar(datetime.now(), janela)
        if sobra < float(config.get("minutos_minimos") or 90):
            log(f"[auto] faltam {sobra:.0f} min para a janela fechar. Nao "
                "comeco trabalho pesado: ele invadiria o dia.")
            return {"feito": "nada", "motivo": "sem tempo na janela"}
        _servico_da_noite(config, headless, log)

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
            log(f"[auto] ja ha {estoque} video(s) novo(s) na fila "
                f"(teto: {teto} = um dia de grade). Nao crio mais ate baixar.")
            return {"feito": "nada", "motivo": "estoque cheio",
                    "estoque": estoque}

    if janela:
        sobra = minutos_ate_fechar(datetime.now(), janela)
        precisa = float(config.get("minutos_por_historia") or 240)
        if sobra < precisa:
            log(f"[auto] faltam {sobra:.0f} min para a janela fechar e uma "
                f"historia leva ~{precisa:.0f}. Nao comeco outra: ela "
                "invadiria o dia.")
            return {"feito": "nada", "motivo": "sem tempo na janela"}
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
