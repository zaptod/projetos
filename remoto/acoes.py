# -*- coding: utf-8 -*-
"""As acoes que o app do celular pode pedir. Tabela FECHADA, com guardas.

Fase 2 do app. Cada acao e uma das funcoes que o bot ja usa (`controle`,
`comandos`, `main.py publicar`), nunca texto executado. O que este modulo
acrescenta e o que um botao no bolso exige a mais que um comando digitado:

  DOIS PASSOS no que nao se desfaz (parar, gerar, publicar). `preparar` NAO
  executa: devolve o texto que a tela mostra. So a confirmacao executa — e
  ela chama `preparar` DE NOVO, dentro da `trava_de_acoes`, porque em 60
  segundos a grade pode ter publicado o mesmo video, e duas confirmacoes
  simultaneas nao podem passar juntas pelas guardas.

  GUARDAS DE PUBLICACAO (a noite de 16 para 17/09 foi limpando repostagem):
    - o video ja saiu naquele destino (`metricas.publicado`);
    - OUTRO video ja pos o mesmo titulo no ar ali (`titulos`);
    - a outra variante (A/B) da mesma geracao ja saiu ali;
    - o TikTok marcou o video "a conferir";
    - postagem da grade perto (relogio), `postar.py` vivo, ou o perfil de
      Chrome daquele destino ocupado;
    - QUALQUER publicacao do app naquele destino ainda sem desfecho limpo;
    - o video tem pendencia ou nao e do perfil celular.
  Tudo que nao se consegue ler RECUSA: um botao manual nao tem pressa.

  PUBLICO. O padrao do `publicacao.json` e `private`; o app diz `public`
  na linha de comando e no texto da confirmacao, como a grade.

  O CAMINHO DE UMA PUBLICACAO, e por que cada passo esta onde esta:
    1. a marca "a conferir" de cada destino e gravada ANTES do clique, sob
       a trava comum da lista (`desfecho.nome_da_trava`), e relida.
       Se o servidor, o PC ou o filho morrerem no meio, a recuperacao da
       grade — que le essa lista e nao le o app — nao reposta. A marca e
       escrita aqui, no arquivo e sob a trava da grade, e nao pela
       `desfecho.marcar_para_conferir`: aquela grava um ERRO no diario
       ("cliquei e nao veio confirmacao"), que antes do clique seria mentira
       e dispararia a apuracao automatica. Depois do clique, o proprio
       publicador chama a dela, que ve a marca do app e nao duplica.
    2. o "em voo" (arquivo) recebe a publicacao.
    3. `publicacao_filha` sobe DESLIGADA do servidor e manda a saida do
       `main.py` para um arquivo (um PIPE mataria o filho junto com o
       servidor).
    4. o desfecho e lido com `youtube_web.confirmado` e `tiktok.confirmado`
       (o prefixo "YouTube:" nao basta: o Studio devolve "cliquei em
       publicar, mas... RASCUNHO" com codigo 0).
    5. SO o sucesso limpo tira a marca do app e o "em voo". Qualquer outra
       coisa deixa os dois de pe, com o motivo, ate a conferencia humana e
       `--liberar`. O servidor que sobe concilia o que ficou pela metade.

  LIMITES E RASTRO: gerar + publicar e pausar + retomar tem teto por hora e
  por aparelho, contado por TEMPO no `app_celular_acoes.jsonl` (com
  rotacao). Rastro que nao grava bloqueia gerar/publicar ate voltar. Cada
  acao vira um aviso no Telegram, por uma fila de uma thread so.
"""
from __future__ import annotations

import contextlib
import json
import os
import queue
import re
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from .config import runtime_dir

MINUTOS_MIN, MINUTOS_MAX = 15, 24 * 60
LIMITE_POR_HORA = 6                      # gerar + publicar
LIMITE_LEVES_POR_HORA = 30               # pausar + retomar
CONFIRMAR_VALE_S = 60
# Folga ANTES de cada horario da grade, pelo pior caso de upload medido nos
# proprios modulos: Studio espera ate 900 s pelo upload (~17 min com os
# dialogos); TikTok, pagina + processamento + botao + confirmacao (~10 min).
# Depois do horario, a rodada da grade vai ate :55 de um disparo em :37.
JANELA_ANTES_MIN = {"youtube": 25, "tiktok": 20, "ambos": 40}
JANELA_DEPOIS_MIN = 18
ESPERA_MAX_S = 6 * 3600                  # depois disso: a conferir, sem matar
VIGIA_S = 5.0
ROTACAO_BYTES = 512 * 1024
DESTINOS = {"youtube": ("youtube",), "tiktok": ("tiktok",),
            "ambos": ("youtube", "tiktok")}
NOME_DESTINO = {"youtube": "YouTube", "tiktok": "TikTok"}
PESADAS = ("gerar", "publicar")
LEVES = ("pausar", "retomar")
# As do catalogo (remoto/comandos_app.py) entram no mesmo teto por hora: o
# que pesa e gastar conta compartilhada, cota e tempo de maquina.


def _pesadas() -> tuple:
    from .comandos_app import PESADAS as outras
    return PESADAS + tuple(outras)
TRAVA_HISTORIAS = "historias__auto"
MARCA_DO_APP = "pelo app"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DESLIGADO = (getattr(subprocess, "DETACHED_PROCESS", 0)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
FORA_DO_JOB = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
RAIZ = Path(__file__).resolve().parents[1]

ARQUIVO_RASTRO = None                     # os testes apontam para outro lugar
ARQUIVO_EM_VOO = None
PASTA_PUBLICACOES = None
PASTA_A_CONFERIR = None


class Recusa(Exception):
    """A acao nao vai acontecer; a mensagem e para a tela."""


# ------------------------------------------------------------------ fontes
# Pequenas, para os testes trocarem.
def _controle():
    from builds.identity import controle
    return controle


def _comandos():
    from . import comandos
    return comandos


def _catalogo():
    from builds.publicar import catalogo
    return catalogo


def _metricas():
    from builds.publicar import metricas
    return metricas


def _titulos():
    from builds.publicar import titulos
    return titulos


def _grade():
    from builds import grade
    return grade


def _agora() -> datetime:
    return datetime.now()


def confirmado(destino: str, estado: str) -> bool:
    """A porta de cada publicador. Levanta se nao der para carregar."""
    if destino == "tiktok":
        from builds.publicar.tiktok import confirmado as porta
    else:
        from builds.publicar.youtube_web import confirmado as porta
    return bool(porta(estado))


def _vivo(pid) -> bool | None:
    try:
        from builds.atividade import _vivo as sonda
    except Exception:                                        # noqa: BLE001
        return None
    return sonda(pid)


def _criado_em(pid) -> float | None:
    from .publicacao_filha import criado_em
    return criado_em(pid)


def vivo_de_verdade(pid, criado) -> bool | None:
    """O processo daquele PID, nascido naquela hora, ainda existe?

    Depois de um reboot o Windows reaproveita PIDs: "o 4312 esta vivo" pode
    ser outro programa. Com a hora de nascimento guardada, PID igual e hora
    diferente e morte.
    """
    vivo = _vivo(pid)
    if vivo is not True or not criado:
        return vivo
    agora = _criado_em(pid)
    if agora is None:
        return None
    return abs(float(agora) - float(criado)) <= 2.0


def _iniciar_filha(pasta: Path, comando: list, cwd) -> int:
    """Sobe a `publicacao_filha` fora do servidor. Devolve o PID."""
    chamada = [sys.executable, "-X", "utf8", "-m", "remoto.publicacao_filha",
               "--pasta", str(pasta), "--cwd", str(cwd), "--"] + list(comando)
    comum = dict(cwd=str(RAIZ), stdin=subprocess.DEVNULL,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                 close_fds=True)
    try:
        # Fora do job do servidor, quando o Windows deixa: um servidor que
        # roda dentro de um job com "mata ao fechar" levaria a filha junto.
        processo = subprocess.Popen(chamada, creationflags=DESLIGADO | FORA_DO_JOB,
                                    **comum)
    except OSError:
        processo = subprocess.Popen(chamada, creationflags=DESLIGADO, **comum)
    return processo.pid


def alvos_de_pausa() -> list[str]:
    try:
        from builds.identity import config
        provedores = sorted(config.PROVEDORES)
    except Exception:                                        # noqa: BLE001
        provedores = []
    return [_controle().TUDO] + provedores


# ------------------------------------------------------------------ trava
def trava_de_acoes():
    """Uma acao por vez: preparar de novo -> executar -> registrar.

    Entre threads E entre processos, reentrante na mesma thread, e com prazo
    (quem nao consegue levanta OSError; o servidor responde 503).
    """
    from .api_http import trava_arquivo
    return trava_arquivo(caminho_rastro().with_name("app_celular_acoes.lock"))


# -------------------------------------------------------- travas e processos
def trava_ocupada(nome: str) -> bool | None:
    """Sonda a trava SEM pegar (a regra da Vila flutuante). None = nao sei."""
    try:
        from builds import travas
        caminho = travas._pasta() / f"{travas._nome_seguro(nome)}.lock"
    except Exception:                                        # noqa: BLE001
        return None
    if not caminho.is_file():
        return False
    try:
        with open(caminho, "rb") as fh:
            fh.read(1)
    except PermissionError:
        return True
    except OSError:
        return None
    return False


def perfil_ocupado(destino: str) -> bool | None:
    """O Chrome daquele destino (canal builds) esta aberto por alguem?"""
    try:
        from builds import travas
        if destino == "tiktok":
            from builds.publicar.tiktok import perfil_da_conta
        else:
            from builds.publicar.youtube_web import perfil_da_conta
        nome = travas.do_caminho(perfil_da_conta("builds"))
    except Exception:                                        # noqa: BLE001
        return None
    return trava_ocupada(nome)


def processos() -> list[str] | None:
    """As linhas de comando dos Pythons vivos. None = nao sei."""
    script = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe' or "
              "Name='pythonw.exe'\" | ForEach-Object { $_.CommandLine }")
    try:
        feito = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    if feito.returncode != 0:
        return None
    return [linha for linha in (feito.stdout or "").splitlines() if linha.strip()]


def gerando_builds(vivos: list[str] | None) -> bool | None:
    if vivos is None:
        return None
    return any("generate-video" in l and "main.py" in l for l in vivos)


def postando(vivos: list[str] | None) -> bool | None:
    if vivos is None:
        return None
    return any("postar.py" in l for l in vivos)


def postagem_em_curso(agora: datetime | None = None,
                      onde: str = "youtube") -> str | None:
    """O horario da grade perto demais para este destino, ou None."""
    agora = agora or _agora()
    antes = timedelta(minutes=JANELA_ANTES_MIN.get(onde, max(JANELA_ANTES_MIN.values())))
    depois = timedelta(minutes=JANELA_DEPOIS_MIN)
    for texto in _grade().horarios():
        hora, minuto = (int(x) for x in texto.split(":"))
        for dias in (-1, 0, 1):
            slot = (agora.replace(hour=hora, minute=minuto, second=0,
                                  microsecond=0) + timedelta(days=dias))
            if slot - antes <= agora <= slot + depois:
                return texto
    return None


# ------------------------------------------------------------------ rastro
def caminho_rastro() -> Path:
    return Path(ARQUIVO_RASTRO) if ARQUIVO_RASTRO else \
        runtime_dir() / "app_celular_acoes.jsonl"


_RASTRO_FALHOU = threading.Event()


def _ler_rastro(desde: datetime) -> list[dict]:
    """As linhas desde `desde`, do arquivo atual e do rodado. Falha = Recusa."""
    atual = caminho_rastro()
    saida = []
    for caminho in (atual.with_name(atual.name + ".1"), atual):
        try:
            with open(caminho, encoding="utf-8") as fh:
                brutas = fh.readlines()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise Recusa(f"não consegui ler o rastro do app ({type(exc).__name__})") from exc
        for bruta in brutas:
            try:
                linha = json.loads(bruta)
                quando = datetime.fromisoformat(linha["quando"])
            except (ValueError, KeyError, TypeError):
                continue
            if quando >= desde:
                saida.append(linha)
    return saida


def _rastro_gravavel() -> bool:
    alvo = caminho_rastro()
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with open(alvo, "a", encoding="utf-8"):
            pass
    except OSError:
        return False
    return True


def registrar(aparelho: str, acao: str, args: dict, resultado: str,
              ok: bool = True) -> dict:
    """Uma linha no rastro. Falhou: gerar/publicar ficam bloqueados."""
    linha = {"quando": _agora().isoformat(timespec="seconds"),
             "aparelho": aparelho, "acao": acao, "args": args,
             "ok": ok, "resultado": str(resultado)[:300]}
    alvo = caminho_rastro()
    try:
        with trava_de_acoes():
            alvo.parent.mkdir(parents=True, exist_ok=True)
            with contextlib.suppress(OSError):
                if alvo.stat().st_size > ROTACAO_BYTES:
                    os.replace(alvo, alvo.with_name(alvo.name + ".1"))
            with open(alvo, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except Exception:
        _RASTRO_FALHOU.set()
        raise
    return linha


def usadas_na_ultima_hora(aparelho: str, acoes: tuple | None = None,
                          agora: datetime | None = None) -> int:
    agora = agora or _agora()
    acoes = _pesadas() if acoes is None else acoes
    return sum(1 for l in _ler_rastro(agora - timedelta(hours=1))
               if l.get("aparelho") == aparelho and l.get("ok")
               and l.get("acao") in acoes)


# ------------------------------------------------------------------ em voo
def caminho_em_voo() -> Path:
    return Path(ARQUIVO_EM_VOO) if ARQUIVO_EM_VOO else \
        runtime_dir() / "app_celular_em_voo.json"


def pasta_publicacoes() -> Path:
    return Path(PASTA_PUBLICACOES) if PASTA_PUBLICACOES else \
        runtime_dir() / "app_celular_publicacoes"


def _ler_json(caminho: Path, tentativas: int = 3):
    """O JSON do arquivo (None se nao existe). Ilegivel apos tentar: ValueError.

    Tenta de novo por um instante: quem le no meio de um `os.replace` do
    outro lado pode pegar o arquivo sendo trocado.
    """
    for vez in range(tentativas):
        try:
            texto = caminho.read_text(encoding="utf-8")
            return json.loads(texto) if texto.strip() else {}
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            if vez == tentativas - 1:
                raise ValueError(f"{caminho.name} ilegível") from None
            time.sleep(0.2)
    return None


def _gravar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(f"{caminho.name}.{os.getpid()}.tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    os.replace(temporario, caminho)


def em_voo() -> dict:
    """{chave: item}. Ilegivel = Recusa."""
    try:
        dados = _ler_json(caminho_em_voo())
    except ValueError as exc:
        raise Recusa("o arquivo de publicações do app está ilegível") from exc
    if dados is None:
        return {}
    if not isinstance(dados, dict):
        raise Recusa("o arquivo de publicações do app está ilegível")
    return dados


def _mexer_no_voo(chave: str, item: dict | None = None, **campos) -> None:
    """Poe (item), atualiza (campos) ou tira (nenhum dos dois) uma entrada."""
    with trava_de_acoes():
        dados = em_voo()
        if item is not None:
            dados[chave] = item
        elif campos:
            if chave not in dados:
                return
            dados[chave].update(campos)
        else:
            if dados.pop(chave, None) is None:
                return
        _gravar_json(caminho_em_voo(), dados)


# -------------------------------------------------- a conferir (os dois destinos)
# A lista e da grade (`builds.publicar.desfecho`): um arquivo por destino, uma
# trava comum (`desfecho.nome_da_trava`) para QUEM LE E QUEM ESCREVE. O app
# le e escreve sob ela, com a leitura dela (`desfecho._ler`: nova tentativa em
# OSError, ValueError = corrupcao). O que o app nao usa e a `marcar_para_
# conferir` para a marca PREVIA: ela grava ERRO no diario ("cliquei e nao veio
# confirmacao"), que antes do clique seria falso — e como e idempotente, a
# marca do app, posta antes, faz a do publicador virar no-op sem perder o
# bloqueio.
def _desfecho():
    from builds.publicar import desfecho
    return desfecho


# O video longo sobe ao YouTube em partes, e cada parte ganha o id
# `X:corte01` (`cortes._copia`) — no ledger e na marca do publicador. Para
# qualquer guarda, `X` e `X:corteNN` sao o MESMO video.
_CORTE = re.compile(r":corte\d+$")


def id_base(video_id) -> str:
    return _CORTE.sub("", str(video_id or ""))


def mesmo_video(a, b) -> bool:
    return bool(a) and bool(b) and id_base(a) == id_base(b)


def _diario(texto: str, video_id: str) -> None:
    """Uma linha de ERRO no diario, para a apuracao ver.

    Com a marca previa do app, a `marcar_para_conferir` do publicador ve o
    video ja marcado e nao escreve nada — quem avisa passa a ser o app.
    """
    try:
        from builds import atividade
        atividade.registrar("publicacao", atividade.ERRO, texto, "builds",
                            etapa="app.a_conferir", ref=video_id)
    except Exception:                                        # noqa: BLE001
        pass


def caminho_a_conferir(plataforma: str = "tiktok") -> Path:
    if PASTA_A_CONFERIR:
        return Path(PASTA_A_CONFERIR) / f"_{plataforma}_a_conferir.json"
    return Path(_desfecho().arquivo_a_conferir("builds", plataforma))


@contextlib.contextmanager
def _trava_da_marca(plataforma: str):
    """A trava comum da lista daquele destino. Nao veio = Recusa."""
    from builds import travas
    desfecho = _desfecho()
    with travas.trava(desfecho.nome_da_trava(plataforma),
                      esperar=desfecho.ESPERA_DA_TRAVA_S) as minha:
        if minha is False:
            raise Recusa(f"a lista “a conferir” do {NOME_DESTINO[plataforma]} "
                         "está ocupada; tente de novo")
        yield


def _ler_marcas(plataforma: str) -> dict:
    """Le a lista (quem chama segura a trava). Ilegivel = Recusa, NUNCA {}.

    Conjunto vazio e uma afirmacao ("ninguem bloqueado"); nao saber e outra
    coisa, e tratar um como o outro republica os marcados.
    """
    nome = NOME_DESTINO[plataforma]
    try:
        dados = _desfecho()._ler(caminho_a_conferir(plataforma))
    except ValueError as exc:
        raise Recusa(f"a lista “a conferir” do {nome} está ilegível; "
                     "confira o arquivo antes de publicar") from exc
    except OSError as exc:
        raise Recusa(f"não consegui ler a lista “a conferir” do {nome}") from exc
    if not isinstance(dados, dict):
        raise Recusa(f"a lista “a conferir” do {nome} está ilegível")
    return dados


def _ler_a_conferir(plataforma: str = "tiktok") -> dict:
    """{video_id: {...}} daquele destino, lido sob a trava comum."""
    with _trava_da_marca(plataforma):
        return _ler_marcas(plataforma)


def _marcar_do_app(video_id: str, chave: str, estado: str,
                   plataforma: str = "tiktok") -> None:
    """Grava (ou atualiza) a marca do app e RELE. Nao conseguiu = Recusa."""
    nome = NOME_DESTINO[plataforma]
    with _trava_da_marca(plataforma):
        dados = _ler_marcas(plataforma)
        atual = dados.get(video_id)
        if atual is not None and (atual or {}).get("app") != chave:
            raise Recusa(f"esse vídeo já está “a conferir” no {nome}")
        dados[video_id] = {"quando": _agora().isoformat(timespec="seconds"),
                           "estado": f"{MARCA_DO_APP}: {estado}"[:200],
                           "plataforma": plataforma, "app": chave}
        try:
            _gravar_json(caminho_a_conferir(plataforma), dados)
        except OSError as exc:
            raise Recusa(f"não consegui gravar a marca “a conferir” do {nome}") from exc
        if (_ler_marcas(plataforma).get(video_id) or {}).get("app") != chave:
            raise Recusa(f"a marca “a conferir” do {nome} não ficou gravada")


def _retirar_marca_do_app(video_id: str, chave: str,
                          plataforma: str = "tiktok") -> bool:
    """Tira SO a marca que este app pos para esta publicacao. True se saiu."""
    try:
        with _trava_da_marca(plataforma):
            dados = _ler_marcas(plataforma)
            nossas = [k for k, v in dados.items()
                      if mesmo_video(k, video_id) and (v or {}).get("app") == chave]
            if not nossas:
                return video_id not in dados
            for k in nossas:
                del dados[k]
            _gravar_json(caminho_a_conferir(plataforma), dados)
            depois = _ler_marcas(plataforma)
            return not any(k in depois for k in nossas) and video_id not in depois
    except (Recusa, OSError):
        return False


def _adotar_partes(video_id: str, chave: str, desde: str,
                   plataforma: str) -> int:
    """As marcas `X:corteNN` que o publicador pos DURANTE esta publicacao
    passam a ser do app, para sairem junto depois da conferencia."""
    with _trava_da_marca(plataforma):
        dados = _ler_marcas(plataforma)
        adotadas = 0
        for k, v in dados.items():
            v = v if isinstance(v, dict) else {}
            if (k != video_id and mesmo_video(k, video_id) and not v.get("app")
                    and str(v.get("quando", "")) >= str(desde or "")):
                v["app"] = chave
                dados[k] = v
                adotadas += 1
        if adotadas:
            _gravar_json(caminho_a_conferir(plataforma), dados)
        return adotadas


# ------------------------------------------------------------------ avisos
_FILA_AVISOS: queue.Queue = queue.Queue(maxsize=50)
_CARTEIRO: threading.Thread | None = None
_CARTEIRO_TRAVA = threading.Lock()


def _escapar_markdown(texto: str) -> str:
    for sinal in ("\\", "_", "*", "`", "["):
        texto = texto.replace(sinal, "\\" + sinal)
    return texto


def _entregar(texto: str) -> None:
    from .__main__ import avisar
    avisar(texto)


def _carteiro() -> None:
    while True:
        texto = _FILA_AVISOS.get()
        try:
            _entregar(texto)
        except Exception:                                    # noqa: BLE001
            pass
        finally:
            _FILA_AVISOS.task_done()


def avisar_telegram(aparelho: str, acao: str, resultado: str) -> None:
    """Enfileira. UMA thread entrega, na ordem; fila cheia descarta."""
    global _CARTEIRO
    texto = _escapar_markdown(
        f"📱 pelo app ({aparelho}): {acao} — {str(resultado)[:300]}")
    with _CARTEIRO_TRAVA:
        if _CARTEIRO is None or not _CARTEIRO.is_alive():
            _CARTEIRO = threading.Thread(target=_carteiro, daemon=True,
                                         name="avisos-app")
            _CARTEIRO.start()
    with contextlib.suppress(queue.Full):
        _FILA_AVISOS.put_nowait(texto)


# ---------------------------------------------------------------- guardas
def _destino_da_linha(linha: dict) -> str:
    # Linha antiga sem `plataforma` e do YouTube (a mesma regra do postar).
    return str(linha.get("plataforma") or "youtube")


def _repetir_titulo() -> bool:
    try:
        config = _catalogo().carregar_config()
    except Exception:                                        # noqa: BLE001
        config = {}
    return bool(((config or {}).get("grade") or {}).get("repetir_titulo"))


def video_para_publicar(video_id: str, onde: str, agora: datetime | None = None,
                        vivos: list[str] | None = None):
    """O video do catalogo, se TODAS as guardas deixarem. Senao, `Recusa`."""
    if onde not in DESTINOS:
        raise Recusa("destino inválido: youtube, tiktok ou ambos")
    video = next((v for v in _catalogo().listar() if str(v.id) == video_id), None)
    if video is None:
        raise Recusa("esse vídeo não está no catálogo de builds")
    if getattr(video, "perfil", "") != "celular":
        raise Recusa("só o formato celular vai para a grade")
    if getattr(video, "pendencias", None):
        raise Recusa("o vídeo tem pendência: " + "; ".join(video.pendencias))

    # O app, primeiro: uma publicacao dele sem desfecho limpo no mesmo
    # destino barra tudo ali (o perfil so tranca quando o Chrome abre).
    for item in em_voo().values():
        comum = set(DESTINOS[onde]) & set(DESTINOS.get(item.get("onde"), ()))
        if not comum:
            continue
        nome = " e ".join(NOME_DESTINO[d] for d in sorted(comum))
        situacao = ("ainda está em andamento" if item.get("estado") == "em_andamento"
                    else "está “a conferir”")
        if item.get("id") == video.id:
            raise Recusa(f"esse vídeo já foi mandado ao {nome} pelo app e {situacao}")
        raise Recusa(f"outra publicação do app no {nome} ({item.get('id')}) "
                     f"{situacao}; confira e libere antes")

    perto = postagem_em_curso(agora, onde)
    if perto:
        raise Recusa(f"a postagem das {perto} está perto demais (usa o mesmo "
                     "Chrome); tente de novo depois")
    rodando = postando(vivos)
    if rodando is None:
        raise Recusa("não consegui conferir se a postagem da grade está rodando")
    if rodando:
        raise Recusa("a postagem da grade está rodando agora; tente depois")
    for destino in DESTINOS[onde]:
        ocupado = perfil_ocupado(destino)
        if ocupado is None:
            raise Recusa(f"não consegui conferir o Chrome do {NOME_DESTINO[destino]}")
        if ocupado:
            raise Recusa(f"o Chrome do {NOME_DESTINO[destino]} está em uso agora")

    metricas = _metricas()
    titulos = _titulos()
    try:
        linhas = [l for l in metricas.publicados("builds") if isinstance(l, dict)]
    except Exception as exc:                                 # noqa: BLE001
        raise Recusa("não consegui ler o registro de publicações "
                     f"({type(exc).__name__})") from exc

    fonte = getattr(video, "fonte_id", "") or ""
    for destino in DESTINOS[onde]:
        nome = NOME_DESTINO[destino]
        if any(mesmo_video(k, video.id) for k in _ler_a_conferir(destino)):
            raise Recusa(f"o {nome} deste vídeo está “a conferir” (o clique "
                         "pode ter saído); confira antes")
        saidas = [l for l in linhas if _destino_da_linha(l) == destino
                  and metricas.publicado(l)]
        if any(mesmo_video(l.get("video_id"), video.id) for l in saidas):
            raise Recusa(f"esse vídeo (ou uma parte dele) já saiu no {nome}")
        if fonte and any(l.get("fonte_id") == fonte
                         and not mesmo_video(l.get("video_id"), video.id)
                         for l in saidas):
            raise Recusa(f"a outra variante de {fonte} já saiu no {nome}")
        outros = [l for l in saidas if not mesmo_video(l.get("video_id"), video.id)]
        if not _repetir_titulo() and titulos.repetido(
                video.titulo, titulos.ja_publicados(outros)):
            raise Recusa(f"outro vídeo já pôs esse título no ar no {nome}")
    return video


# --------------------------------------------------------------- a tabela
def _alvo(args: dict, obrigatorio: bool) -> str | None:
    alvo = args.get("alvo")
    if alvo in (None, "") and not obrigatorio:
        return None
    alvo = str(alvo or _controle().TUDO)
    if alvo not in alvos_de_pausa():
        raise Recusa(f"alvo desconhecido: {alvo}")
    return alvo


def _minutos(args: dict) -> int | None:
    bruto = args.get("minutos")
    if bruto in (None, "", 0):
        return None
    try:
        minutos = int(bruto)
    except (TypeError, ValueError) as exc:
        raise Recusa("minutos inválidos") from exc
    if not MINUTOS_MIN <= minutos <= MINUTOS_MAX:
        raise Recusa(f"a pausa vai de {MINUTOS_MIN} a {MINUTOS_MAX} minutos")
    return minutos


def _limite(aparelho: str, acoes: tuple, teto: int, nome: str) -> None:
    if usadas_na_ultima_hora(aparelho, acoes) >= teto:
        raise Recusa(f"limite de {teto} {nome} por hora pelo app; tente mais tarde")


def _rastro_ok() -> None:
    """Bloqueia gerar/publicar enquanto o rastro nao grava.

    `_RASTRO_FALHOU` marca a falha de uma gravacao de verdade. Com ela
    acesa, so uma gravacao de verdade a apaga (abrir o arquivo nao prova
    que a trava tambem voltou).
    """
    if _RASTRO_FALHOU.is_set():
        try:
            registrar("servidor", "verificacao", {}, "o rastro voltou a gravar")
        except Exception as exc:                             # noqa: BLE001
            raise Recusa("o rastro do app não está gravando; gerar e publicar "
                         "ficam bloqueados até ele voltar") from exc
        _RASTRO_FALHOU.clear()
        return
    if not _rastro_gravavel():
        raise Recusa("o rastro do app não está gravando; gerar e publicar "
                     "ficam bloqueados até ele voltar")


TEXTO_PARAR = (
    "Parar o worker dos builds (imagens e vídeos do Digen/PicassoIA)? Ele "
    "termina o job atual, fecha o navegador e encerra — e, ao sair, a parada "
    "se apaga sozinha. Até ele sair, as imagens das histórias esperam. A "
    "rodada automática das histórias e a postagem da grade continuam. O "
    "worker só volta quando for iniciado de novo. Mudou de ideia antes de ele "
    "sair? Toque em Retomar.")


def preparar(acao: str, args, aparelho: str) -> dict:
    """{acao, args, dois_passos, texto}. Valida tudo; nao executa nada."""
    if not isinstance(args, dict):
        raise Recusa("argumentos inválidos")
    if acao in LEVES:
        _limite(aparelho, LEVES, LIMITE_LEVES_POR_HORA, "pausas/retomadas")
    if acao == "pausar":
        alvo = _alvo(args, obrigatorio=True)
        minutos = _minutos(args)
        prazo = f" por {minutos} min" if minutos else " sem prazo"
        return {"acao": acao, "args": {"alvo": alvo, "minutos": minutos},
                "dois_passos": False,
                "texto": f"Pausar {alvo}{prazo}. O job em andamento termina."}
    if acao == "retomar":
        alvo = _alvo(args, obrigatorio=False)
        return {"acao": acao, "args": {"alvo": alvo}, "dois_passos": False,
                "texto": f"Retomar {alvo or 'tudo'}."}
    if acao == "parar":
        return {"acao": acao, "args": {}, "dois_passos": True, "texto": TEXTO_PARAR}
    if acao in _pesadas():
        _rastro_ok()
        _limite(aparelho, _pesadas(), LIMITE_POR_HORA, "gerações/publicações")
    if acao == "gerar":
        avisos = []
        historias = trava_ocupada(TRAVA_HISTORIAS)
        if historias:
            raise Recusa("já está gerando: a rodada automática de histórias "
                         "está rodando")
        if historias is None:
            avisos.append("a rodada das histórias")
        gerando = gerando_builds(processos())
        if gerando:
            raise Recusa("já está gerando: há uma build sendo feita agora")
        if gerando is None:
            avisos.append("se já há uma build rodando")
        aviso = (f" (não consegui conferir {' nem '.join(avisos)})"
                 if avisos else "")
        return {"acao": acao, "args": {}, "dois_passos": True,
                "texto": ("Gerar uma build nova (roleta + vídeo)? Usa as contas "
                          f"compartilhadas e leva alguns minutos.{aviso}")}
    if acao == "publicar":
        video_id = str(args.get("id") or "")
        onde = str(args.get("onde") or "")
        video = video_para_publicar(video_id, onde, vivos=processos())
        destinos = " e no ".join(NOME_DESTINO[d] for d in DESTINOS[onde])
        publico = " como PÚBLICO" if "youtube" in DESTINOS[onde] else ""
        # A e B tem o MESMO titulo: sem isto, a confirmacao nao diz qual sai.
        variante = str(getattr(video, "variante", "A") or "A")
        gancho = "" if variante == "A" else f" (gancho {variante})"
        return {"acao": acao,
                "args": {"id": video.id, "onde": onde,
                         "fonte": getattr(video, "fonte_id", "") or "",
                         "titulo": str(getattr(video, "titulo", "") or "")[:120]},
                "dois_passos": True,
                "texto": f"Publicar «{video.titulo}»{gancho} no {destinos}"
                         f"{publico}? Não dá para desfazer pelo app."}
    return _preparar_do_catalogo(acao, args, aparelho)


def _preparar_do_catalogo(acao: str, args: dict, aparelho: str) -> dict:
    """As acoes declaradas em `comandos_app`: valida, guarda, e pede o "sim".

    A validacao vem ANTES das guardas de propósito: "falta preencher o
    campo" e uma resposta melhor do que "o perfil esta ocupado" para quem
    nem terminou de preencher.
    """
    from . import comandos_app
    ficha = comandos_app.FICHAS.get(acao)
    if ficha is None:
        raise Recusa(f"ação desconhecida: {acao}")
    limpos = comandos_app.validar(acao, args)
    comandos_app.guardar(acao, limpos)
    return {"acao": acao, "args": limpos,
            "dois_passos": bool(ficha.get("dois_passos")),
            "perigosa": comandos_app.e_perigosa(acao, limpos),
            "texto": comandos_app.texto(acao, limpos)}


def comando_de_publicar(args: dict) -> list:
    comandos = _comandos()
    comando = [comandos.PY, "-X", "utf8", "main.py", "publicar", args["id"]]
    if "youtube" in DESTINOS[args["onde"]]:
        comando += ["--youtube", "--visibilidade", "public"]
    if "tiktok" in DESTINOS[args["onde"]]:
        comando += ["--tiktok", "--postar"]
    return comando


def executar(acao: str, args: dict, aparelho: str = "") -> str:
    """Faz de verdade. So e chamada com `args` que sairam de `preparar`."""
    controle = _controle()
    if acao == "pausar":
        return controle.pausar(args["alvo"], "pelo app",
                               args.get("minutos")).get("resumo", "pausado")
    if acao == "retomar":
        return controle.retomar(args.get("alvo")).get("resumo", "retomado")
    if acao == "parar":
        return controle.pedir_parada("pelo app").get("resumo", "parada pedida")
    if acao == "gerar":
        return _comandos().gerar()
    if acao == "publicar":
        return _disparar_publicacao(args, aparelho)
    from . import comandos_app
    if acao in comandos_app.FICHAS:
        return comandos_app.executar(acao, args, aparelho)
    raise Recusa(f"ação desconhecida: {acao}")


def _disparar_publicacao(args: dict, aparelho: str) -> str:
    chave = secrets.token_hex(8)
    pasta = pasta_publicacoes() / chave
    destinos = DESTINOS[args["onde"]]
    with trava_de_acoes():
        marcados = []
        try:
            for destino in destinos:
                _marcar_do_app(args["id"], chave,
                               f"publicação em andamento ({chave})", destino)
                marcados.append(destino)
            pasta.mkdir(parents=True, exist_ok=True)
            _mexer_no_voo(chave, {
                "id": args["id"], "onde": args["onde"],
                "fonte": args.get("fonte", ""), "titulo": args.get("titulo", ""),
                "aparelho": aparelho, "pasta": str(pasta), "pid": None,
                "estado": "em_andamento", "motivo": "",
                "desde": _agora().isoformat(timespec="seconds")})
            pid = _iniciar_filha(pasta, comando_de_publicar(args),
                                 _comandos().RANDOM_BUILDS)
        except Exception as exc:
            # Nada subiu: desfaz o que foi preparado.
            with contextlib.suppress(Exception):
                _mexer_no_voo(chave)
            for destino in marcados:
                _retirar_marca_do_app(args["id"], chave, destino)
            if isinstance(exc, Recusa):
                raise
            raise Recusa(f"não consegui iniciar a publicação: {exc}") from exc
        _mexer_no_voo(chave, pid=pid, criado=_criado_em(pid))
    vigiar(chave)
    publico = " (público no YouTube)" if "youtube" in destinos else ""
    return (f"comecei: publicar {args['id']} em {args['onde']}{publico}. "
            "Aviso quando terminar.")


# ---------------------------------------------------------------- desfecho
def desfechos(saida: str | None, codigo: int | None, onde: str) -> dict:
    """{destino: "publicado" | "a_conferir" | "falha_limpa" | "nao_tentado"}.

    Le a saida do `main.py publicar`. "publicado" so com a porta do
    publicador dizendo que confirmou, em TODAS as partes (o video longo vira
    "(1 de 2)", "(2 de 2)"), e o processo saindo com 0. "falha_limpa" so
    existe para a cota do YouTube (codigo 2) antes de qualquer parte
    confirmada: nada foi clicado. "nao_tentado": o `main.py` saiu no YouTube
    e nunca chegou ao TikTok. Todo o resto — incluindo o que nao deu para
    ler — e "a_conferir".
    """
    resultado: dict = {}
    linhas = (saida or "").splitlines()
    sem_fim = saida is None or codigo is None
    cota = codigo == 2
    yt = [l[len("YouTube: "):] for l in linhas if l.startswith("YouTube: ")]
    yt_falhou = any(l.startswith("YouTube FALHOU") for l in linhas)
    yt_a_conferir = any(l.startswith("YouTube A CONFERIR") for l in linhas)
    tk = next((l[len("TikTok: "):] for l in linhas if l.startswith("TikTok: ")), None)
    tk_falhou = any(l.startswith("TikTok FALHOU") for l in linhas)

    def confirma(destino, estados) -> bool | None:
        try:
            return all(confirmado(destino, e) for e in estados)
        except Exception:                                    # noqa: BLE001
            return None        # nao deu para carregar a porta: nao sei

    if "youtube" in DESTINOS[onde]:
        if sem_fim or yt_falhou:
            resultado["youtube"] = "a_conferir"
        elif cota:
            # A linha da cota e a ultima "YouTube:". Qualquer linha antes
            # dela e uma parte que foi tentada (publicada ou rascunho).
            # "A CONFERIR" antes da cota tambem e parte tentada.
            limpa = len(yt) <= 1 and not yt_a_conferir
            resultado["youtube"] = "falha_limpa" if limpa else "a_conferir"
        elif yt and confirma("youtube", yt) is True and codigo == 0:
            resultado["youtube"] = "publicado"
        else:
            resultado["youtube"] = "a_conferir"
    if "tiktok" in DESTINOS[onde]:
        saiu_no_youtube = (onde == "ambos" and not sem_fim and tk is None
                           and not tk_falhou and codigo in (1, 2)
                           and resultado.get("youtube") in ("falha_limpa", "a_conferir")
                           and (yt_falhou or cota))
        if saiu_no_youtube:
            resultado["tiktok"] = "nao_tentado"
        elif (not sem_fim and tk is not None and not tk_falhou and codigo == 0
              and confirma("tiktok", [tk]) is True):
            resultado["tiktok"] = "publicado"
        else:
            resultado["tiktok"] = "a_conferir"
    return resultado


def _limpo(resultado: dict) -> bool:
    return all(r in ("publicado", "falha_limpa", "nao_tentado")
               for r in resultado.values())


def concluir_publicacao(chave: str) -> dict | None:
    """Le a saida da filha, marca/solta, anota e avisa. Devolve o resultado."""
    item = em_voo().get(chave)
    if item is None:
        return None
    pasta = Path(item.get("pasta") or pasta_publicacoes() / chave)
    try:
        saida = (pasta / "saida.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        saida = None
    try:
        fim = _ler_json(pasta / "fim.json")
    except ValueError:
        fim = None
    codigo = (fim or {}).get("codigo")
    if fim is None:
        saida = None                        # sem fim, a saida esta incompleta
    resultado = desfechos(saida, codigo, item["onde"])
    video_id = item["id"]
    avisos = []

    with trava_de_acoes():
        # De novo, dentro da trava: duas vigias (esta e a de um servidor que
        # acabou de subir) nao concluem a mesma publicacao duas vezes.
        atual = em_voo().get(chave)
        if atual is None or atual.get("estado") != "em_andamento":
            return None
        for destino, desfecho in resultado.items():
            nome = NOME_DESTINO[destino]
            if desfecho == "a_conferir":
                ultima = next((l for l in reversed((saida or "").splitlines())
                               if l.startswith(nome)), "")
                motivo = ultima or ("sem desfecho" if fim is None
                                    else f"saída {codigo} sem linha do {nome}")
                adotadas = 0
                try:
                    _marcar_do_app(video_id, chave, f"a conferir: {motivo}", destino)
                    adotadas = _adotar_partes(video_id, chave, item.get("desde", ""),
                                              destino)
                except Recusa as exc:
                    avisos.append(f"marca do {nome} não atualizada ({exc})")
                # Parte cortada: o publicador marcou `X:corteNN` (que nao tinha
                # marca previa) e ja escreveu o ERRO no diario. So o app avisa
                # quando o publicador ficou calado.
                if not adotadas:
                    _diario(f"{video_id}: publicado pelo app sem confirmação no "
                            f"{nome} ({motivo[:120]}). Pode estar no ar — "
                            "bloqueado até conferência (--em-voo / --liberar).",
                            video_id)
            elif not _retirar_marca_do_app(video_id, chave, destino):
                avisos.append(f"não consegui tirar a marca “a conferir” do app "
                              f"no {nome}")
        if _limpo(resultado):
            _mexer_no_voo(chave)
        else:
            pendentes = [NOME_DESTINO[d] for d, r in resultado.items()
                         if r == "a_conferir"]
            _mexer_no_voo(chave, estado="a_conferir",
                          motivo="confira no " + " e no ".join(pendentes),
                          resultado=resultado)

    texto = ", ".join(f"{NOME_DESTINO[d]}: {r}" for d, r in resultado.items())
    if not _limpo(resultado):
        texto += " — bloqueado no app até conferir (--em-voo / --liberar)"
    if avisos:
        texto += " (" + "; ".join(avisos) + ")"
    with contextlib.suppress(Exception):
        registrar(item.get("aparelho", ""), "desfecho",
                  {"id": video_id, "onde": item["onde"]}, texto,
                  ok=_limpo(resultado) and not avisos)
    avisar_telegram(item.get("aparelho", ""), f"publicar {video_id}", texto)
    return resultado


def situacao_da_filha(item: dict) -> dict:
    """{terminou, filha, filho}: o fim existe? e os dois processos vivem?

    `filho` e o `main.py` que a filha abriu (ele pode sobreviver a ela).
    Cada vivo e True/False/None, com a hora de nascimento conferida.
    """
    pasta = Path(item.get("pasta") or "")
    terminou = bool(item.get("pasta")) and (pasta / "fim.json").is_file()
    filha = vivo_de_verdade(item.get("pid"), item.get("criado"))
    # O filho.json e escrito logo depois do main.py nascer. Ausente COM fim:
    # o main.py nem chegou a nascer (o fim traz o erro). Ausente SEM fim, ou
    # ilegivel: nao sei — e "nao sei" nao solta.
    filho = None
    if item.get("pasta"):
        try:
            filho_json = _ler_json(pasta / "filho.json")
        except ValueError:
            filho_json = {}
        if filho_json is None:
            filho = False if terminou else None
        elif isinstance(filho_json, dict) and filho_json.get("pid"):
            filho = vivo_de_verdade(filho_json.get("pid"), filho_json.get("criado"))
    return {"terminou": terminou, "filha": filha, "filho": filho}


ESPERA_ERRO_MAX_S = 300.0


def _vigia(chave: str) -> None:
    """Espera o fim e conclui. Erro (trava estourada, disco) NAO encerra.

    Ate 17/09 um erro no concluir saia da vigia para sempre, e o item ficava
    "em_andamento" ate alguem reiniciar o servidor. Agora ela tenta de novo,
    com espera crescente, ate o item sair de "em_andamento".
    """
    comeco = time.monotonic()
    espera_erro = VIGIA_S
    while True:
        try:
            item = em_voo().get(chave)
        except Recusa:
            item = {}                      # arquivo ilegivel agora: tenta depois
        if item is None or (item and item.get("estado") != "em_andamento"):
            return
        if item:
            estado = situacao_da_filha(item)
            sumiu = (not estado["terminou"] and estado["filha"] is False
                     and estado["filho"] is False)
            estourou = time.monotonic() - comeco > ESPERA_MAX_S
            if estado["terminou"] or sumiu or estourou:
                try:
                    concluir_publicacao(chave)
                    espera_erro = VIGIA_S
                except Exception:                            # noqa: BLE001
                    time.sleep(espera_erro)
                    espera_erro = min(espera_erro * 2, ESPERA_ERRO_MAX_S)
                continue                   # rele: so sai quando concluiu
        time.sleep(VIGIA_S)


def vigiar(chave: str) -> threading.Thread:
    fio = threading.Thread(target=_vigia, args=(chave,), daemon=True,
                           name=f"publicar-{chave}")
    fio.start()
    return fio


def conciliar() -> list[str]:
    """Na subida do servidor: volta a vigiar o que ficou em andamento."""
    try:
        voando = em_voo()
    except Recusa:
        return []
    chaves = [k for k, v in voando.items() if v.get("estado") == "em_andamento"]
    for chave in chaves:
        vigiar(chave)
    return chaves


def _pode_soltar(item: dict) -> str:
    """"" se o item pode sair do em-voo; senao, o motivo.

    Enquanto a publicacao PODE estar rodando, soltar libera um segundo
    publicar do mesmo video (no YouTube em rascunho, uma duplicata).
    Pode estar rodando = sem fim.json e com a filha ou o main.py vivos (ou
    sem dar para saber), ou com fim.json mas o main.py ainda vivo.
    """
    estado = situacao_da_filha(item)
    if estado["filho"] is not False:
        return "o main.py dessa publicação ainda pode estar rodando"
    if not estado["terminou"] and estado["filha"] is not False:
        return "essa publicação ainda não terminou"
    return ""


def liberar(video_id: str) -> int:
    """Tira do "em voo" as publicacoes daquele video. A marca do TikTok fica.

    Recusa (levanta `Recusa`) se alguma delas ainda puder estar rodando.
    """
    with trava_de_acoes():
        dados = em_voo()
        fora = [k for k, v in dados.items() if mesmo_video(v.get("id"), video_id)]
        for chave in fora:
            motivo = _pode_soltar(dados[chave])
            if motivo:
                raise Recusa(f"não solto {video_id}: {motivo}")
        for chave in fora:
            del dados[chave]
        if fora:
            _gravar_json(caminho_em_voo(), dados)
    return len(fora)


def soltar_marca(video_id: str) -> bool:
    """Tira a marca "a conferir" que o APP pos, depois da conferencia humana.

    So a marca do app (a que tem "app"), e so sem publicacao do app ainda no
    em-voo para aquele video. Marca da grade nao sai por aqui.
    """
    with trava_de_acoes():
        if any(mesmo_video(v.get("id"), video_id) for v in em_voo().values()):
            raise Recusa("o vídeo ainda está no em-voo do app; libere-o antes")
        do_app = []
        for destino in NOME_DESTINO:
            for k, marca in _ler_a_conferir(destino).items():
                if not mesmo_video(k, video_id):
                    continue
                chave = (marca or {}).get("app")
                if not chave:
                    raise Recusa(f"a marca de {k} no {NOME_DESTINO[destino]} não é "
                                 "do app (é da grade); não mexo nela")
                do_app.append((destino, k, chave))
        for destino, k, chave in do_app:
            if not _retirar_marca_do_app(k, chave, destino):
                raise Recusa(f"não consegui tirar a marca de {k} no "
                             f"{NOME_DESTINO[destino]}")
    return bool(do_app)


def relatorio_do_video(video_id: str) -> list[str]:
    """O que se sabe do video antes de liberar: em voo, ledger, a conferir."""
    linhas = []
    try:
        for item in em_voo().values():
            if mesmo_video(item.get("id"), video_id):
                linhas.append(f"em voo: {item.get('onde')} {item.get('estado')} "
                              f"desde {item.get('desde')} — {item.get('motivo', '')}")
    except Recusa as exc:
        linhas.append(f"em voo: {exc}")
    try:
        for l in _metricas().publicados("builds"):
            if isinstance(l, dict) and mesmo_video(l.get("video_id"), video_id):
                linhas.append(f"ledger: {l.get('video_id')} {_destino_da_linha(l)} "
                              f"{l.get('quando')} "
                              f"publicado={_metricas().publicado(l)}")
    except Exception as exc:                                 # noqa: BLE001
        linhas.append(f"ledger: ilegível ({type(exc).__name__})")
    for destino, nome in NOME_DESTINO.items():
        try:
            for k, marca in _ler_a_conferir(destino).items():
                if not mesmo_video(k, video_id):
                    continue
                dono = "do app" if (marca or {}).get("app") else "da grade"
                parte = "" if k == video_id else f" {k}"
                linhas.append(f"a conferir ({nome}, {dono}){parte}: "
                              f"{(marca or {}).get('estado', '')}")
        except Recusa as exc:
            linhas.append(f"a conferir ({nome}): {exc}")
    return linhas


# ---------------------------------------------------------- confirmacoes
class Pendentes:
    """Pedidos de dois passos esperando o "sim". Em memoria, de uso unico."""

    LEMBRAR_S = 600

    def __init__(self):
        self._trava = threading.Lock()
        self._itens: dict[str, dict] = {}
        # Codigos que existiram (usados ou vencidos) -> (dono, ate quando
        # lembrar). O toque duplo e o "sim" atrasado do proprio aparelho
        # nao sao chute.
        self._encerrados: dict[str, tuple] = {}

    def _podar(self, agora: float) -> None:
        for codigo, item in list(self._itens.items()):
            if item["expira"] <= agora:
                del self._itens[codigo]
                self._encerrados[codigo] = (item["dono"], agora + self.LEMBRAR_S)
        self._encerrados = {k: v for k, v in self._encerrados.items()
                            if v[1] > agora}

    def guardar(self, pedido: dict, dono: str) -> str:
        agora = time.time()
        codigo = secrets.token_urlsafe(16)
        with self._trava:
            self._podar(agora)
            self._itens[codigo] = dict(pedido, dono=dono,
                                       expira=agora + CONFIRMAR_VALE_S)
        return codigo

    def tirar(self, codigo: str, dono: str) -> tuple:
        """(pedido, motivo): "ok", "encerrado" (do mesmo aparelho) ou "chute"."""
        codigo = str(codigo or "")
        agora = time.time()
        with self._trava:
            self._podar(agora)
            pedido = self._itens.get(codigo)
            if pedido is None:
                antigo = self._encerrados.get(codigo)
                if antigo and antigo[0] == dono:
                    return (None, "encerrado")
                return (None, "chute")
            if pedido["dono"] != dono:
                return (None, "chute")
            del self._itens[codigo]
            self._encerrados[codigo] = (dono, agora + self.LEMBRAR_S)
        return (pedido, "ok")


__all__ = ["CONFIRMAR_VALE_S", "LIMITE_POR_HORA", "Pendentes", "Recusa",
           "alvos_de_pausa", "avisar_telegram", "conciliar", "concluir_publicacao",
           "desfechos", "em_voo", "executar", "liberar", "preparar", "registrar",
           "relatorio_do_video", "situacao_da_filha", "soltar_marca",
           "trava_de_acoes", "usadas_na_ultima_hora", "video_para_publicar",
           "vivo_de_verdade"]


if __name__ == "__main__":                                   # pragma: no cover
    sys.exit("use pelo servidor: python -m remoto.api_http")
