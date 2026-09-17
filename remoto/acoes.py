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

  GUARDAS DE PUBLICACAO. O Adrian passou a noite de 16 para 17/09 limpando
  repostagem; publicar pelo app nao pode ser o oitavo caminho que fura as
  guardas do `postar.py`. As mesmas leituras, e mais as de um botao:
    - o video ja saiu naquele destino (`metricas.publicado`);
    - OUTRO video ja pos o mesmo titulo no ar ali (`titulos`);
    - a outra variante (A/B) da mesma geracao ja saiu ali;
    - o TikTok marcou o video "a conferir";
    - postagem da grade perto (relogio), `postar.py` vivo, ou o perfil de
      Chrome daquele destino ocupado;
    - o proprio app ja mandou o video (ou a outra variante) e o desfecho
      ainda nao voltou — o "em voo";
    - o video tem pendencia ou nao e do perfil celular.
  Tudo que nao se consegue ler RECUSA: um botao manual nao tem pressa.

  PUBLICO. O padrao do `publicacao.json` e `private`, e o que sobe privado
  vira "publicado" no ledger e fica queimado. A grade publica `public`;
  o app tambem, dito na linha de comando e no texto da confirmacao.

  DESFECHO DO TIKTOK. `main.py publicar --tiktok` so grava no ledger quando
  o post confirma. Clique sem confirmacao (ou saida que nao seja sucesso
  limpo) nao deixava marca nenhuma, e a recuperacao da grade repostaria.
  O app acompanha o processo ate o fim e, nesse caso, marca "a conferir"
  com a MESMA funcao do `postar.py`. Enquanto o desfecho nao volta, o video
  fica no "em voo" (arquivo, nao memoria: servidor que cai no meio deixa o
  bloqueio de pe, e `--liberar` o tira depois da conferencia).

  LIMITES E RASTRO: gerar + publicar e pausar + retomar tem teto por hora e
  por aparelho, contado por TEMPO no `app_celular_acoes.jsonl` (com
  rotacao). Rastro que nao grava bloqueia gerar/publicar ate voltar. Cada
  acao vira um aviso no Telegram, por uma fila de uma thread so.
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import queue
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
PUBLICAR_TIMEOUT_S = 60 * 60
ROTACAO_BYTES = 512 * 1024
DESTINOS = {"youtube": ("youtube",), "tiktok": ("tiktok",),
            "ambos": ("youtube", "tiktok")}
NOME_DESTINO = {"youtube": "YouTube", "tiktok": "TikTok"}
SERVICO_DO_DESTINO = {"youtube": "youtube_web", "tiktok": "tiktok"}
PESADAS = ("gerar", "publicar")
LEVES = ("pausar", "retomar")
TRAVA_HISTORIAS = "historias__auto"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
RAIZ = Path(__file__).resolve().parents[1]

ARQUIVO_RASTRO = None                     # os testes apontam para outro lugar
ARQUIVO_EM_VOO = None


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


_POSTAR = None


def _postar():
    """O `ferramentas/postar.py`, carregado uma vez. E dele a marca "a conferir".

    Nao e copia: `desfecho_do_tiktok` e `_marcar_para_conferir` sao as
    funcoes da grade, e o que mudar la vale aqui.
    """
    global _POSTAR
    if _POSTAR is None:
        caminho = RAIZ / "ferramentas" / "postar.py"
        spec = importlib.util.spec_from_file_location("_postar_app_celular", caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        _POSTAR = modulo
    return _POSTAR


def _abrir_processo(comando: list, cwd) -> subprocess.Popen:
    ambiente = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.Popen(comando, cwd=str(cwd), creationflags=NO_WINDOW,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", env=ambiente)


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

    Entre threads E entre processos, e reentrante na mesma thread (o
    `registrar` de dentro pega a mesma trava sem se bloquear).
    """
    from .api_http import trava_arquivo
    return trava_arquivo(caminho_rastro().with_name("app_celular_acoes.lock"))


# -------------------------------------------------------- travas e processos
def trava_ocupada(nome: str) -> bool | None:
    """Sonda a trava SEM pegar (a regra da Vila flutuante).

    `travas.ocupada()` responde pegando a trava por um instante, e nesse
    instante o dono de verdade ouviria "ocupado" e desistiria da rodada.
    Aqui so se tenta LER o byte que o dono tranca: no Windows, byte trancado
    por outro processo nao le. None = nao sei.
    """
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
    _RASTRO_FALHOU.clear()
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


def usadas_na_ultima_hora(aparelho: str, acoes: tuple = PESADAS,
                          agora: datetime | None = None) -> int:
    agora = agora or _agora()
    return sum(1 for l in _ler_rastro(agora - timedelta(hours=1))
               if l.get("aparelho") == aparelho and l.get("ok")
               and l.get("acao") in acoes)


# ------------------------------------------------------------------ em voo
def caminho_em_voo() -> Path:
    return Path(ARQUIVO_EM_VOO) if ARQUIVO_EM_VOO else \
        runtime_dir() / "app_celular_em_voo.json"


def em_voo() -> dict:
    """{chave: {id, onde, fonte, desde, aparelho}}. Ilegivel = Recusa."""
    try:
        texto = caminho_em_voo().read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise Recusa("não consegui ler as publicações em andamento") from exc
    try:
        dados = json.loads(texto) if texto.strip() else {}
    except ValueError as exc:
        raise Recusa("o arquivo de publicações em andamento está ilegível") from exc
    if not isinstance(dados, dict):
        raise Recusa("o arquivo de publicações em andamento está ilegível")
    return dados


def _gravar_em_voo(dados: dict) -> None:
    alvo = caminho_em_voo()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    temporario = alvo.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    os.replace(temporario, alvo)


def _por_em_voo(chave: str, item: dict) -> None:
    with trava_de_acoes():
        dados = em_voo()
        dados[chave] = item
        _gravar_em_voo(dados)


def _tirar_do_voo(chave: str) -> None:
    with trava_de_acoes():
        dados = em_voo()
        if dados.pop(chave, None) is not None:
            _gravar_em_voo(dados)


def liberar(video_id: str) -> int:
    """Tira do "em voo" as publicacoes daquele video (depois de conferir)."""
    with trava_de_acoes():
        dados = em_voo()
        fora = [k for k, v in dados.items() if v.get("id") == video_id]
        for chave in fora:
            del dados[chave]
        if fora:
            _gravar_em_voo(dados)
    return len(fora)


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


def _a_conferir_no_tiktok() -> set:
    try:
        caminho = (_metricas().registro_do_canal("builds").parent
                   / "_tiktok_a_conferir.json")
        if not caminho.is_file():
            return set()
        return set(json.loads(caminho.read_text(encoding="utf-8")))
    except Exception as exc:                                 # noqa: BLE001
        raise Recusa("não consegui ler a lista “a conferir” do TikTok") from exc


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
    conferir = _a_conferir_no_tiktok()
    voando = list(em_voo().values())
    for destino in DESTINOS[onde]:
        nome = NOME_DESTINO[destino]
        for pedido in voando:
            if destino not in DESTINOS.get(pedido.get("onde"), ()):
                continue
            if pedido.get("id") == video.id:
                raise Recusa(f"esse vídeo já foi mandado ao {nome} pelo app e o "
                             "resultado ainda não voltou")
            if fonte and pedido.get("fonte") == fonte:
                raise Recusa(f"a outra variante de {fonte} foi mandada ao {nome} "
                             "pelo app e o resultado ainda não voltou")
        saidas = [l for l in linhas if _destino_da_linha(l) == destino
                  and metricas.publicado(l)]
        if any(l.get("video_id") == video.id for l in saidas):
            raise Recusa(f"esse vídeo já saiu no {nome}")
        if fonte and any(l.get("fonte_id") == fonte and l.get("video_id") != video.id
                         for l in saidas):
            raise Recusa(f"a outra variante de {fonte} já saiu no {nome}")
        outros = [l for l in saidas if l.get("video_id") != video.id]
        if not _repetir_titulo() and titulos.repetido(
                video.titulo, titulos.ja_publicados(outros)):
            raise Recusa(f"outro vídeo já pôs esse título no ar no {nome}")
        if destino == "tiktok" and video.id in conferir:
            raise Recusa("o TikTok deste vídeo está “a conferir” (o clique "
                         "saiu sem confirmação); confira no perfil antes")
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
    if acao in PESADAS:
        _rastro_ok()
        _limite(aparelho, PESADAS, LIMITE_POR_HORA, "gerações/publicações")
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
                         "fonte": getattr(video, "fonte_id", "") or ""},
                "dois_passos": True,
                "texto": f"Publicar «{video.titulo}»{gancho} no {destinos}"
                         f"{publico}? Não dá para desfazer pelo app."}
    raise Recusa(f"ação desconhecida: {acao}")


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
        chave = secrets.token_hex(8)
        # Primeiro o bloqueio, depois o processo: se o arquivo nao grava,
        # nada sobe.
        _por_em_voo(chave, {"id": args["id"], "onde": args["onde"],
                            "fonte": args.get("fonte", ""), "aparelho": aparelho,
                            "desde": _agora().isoformat(timespec="seconds")})
        try:
            processo = _abrir_processo(comando_de_publicar(args),
                                       _comandos().RANDOM_BUILDS)
        except OSError as exc:
            _tirar_do_voo(chave)
            raise Recusa(f"não consegui iniciar a publicação: {exc}") from exc
        threading.Thread(target=_acompanhar, args=(processo, chave, args, aparelho),
                         daemon=True, name=f"publicar-{chave}").start()
        publico = " (público no YouTube)" if "youtube" in DESTINOS[args["onde"]] else ""
        return (f"comecei: publicar {args['id']} em {args['onde']}{publico}. "
                "Aviso quando terminar.")
    raise Recusa(f"ação desconhecida: {acao}")


# ---------------------------------------------------------------- desfecho
def desfechos(saida: str | None, codigo: int | None, onde: str) -> dict:
    """{destino: "publicado" | "nao_tentado" | desfecho do postar}.

    Le a saida do `main.py publicar`: "YouTube: <url>" ou "YouTube FALHOU:",
    "TikTok: <estado>" ou "TikTok FALHOU: <motivo>". Sem saida (tempo
    esgotado) ou sem a linha do TikTok, o clique PODE ter saido: vale
    "sem_confirmacao". A excecao e o YouTube ter falhado antes, porque o
    `main.py` sai ali sem tentar o TikTok.
    """
    resultado: dict = {}
    linhas = (saida or "").splitlines()
    # Cota esgotada sai como "YouTube: <motivo>" com codigo 2 — e falha.
    yt_falhou = (any(l.startswith("YouTube FALHOU") for l in linhas)
                 or (codigo == 2 and "youtube" in DESTINOS[onde]))
    if "youtube" in DESTINOS[onde]:
        yt_linha = any(l.startswith("YouTube: ") for l in linhas)
        resultado["youtube"] = "publicado" if yt_linha and not yt_falhou else "falha"
    if "tiktok" in DESTINOS[onde]:
        estado = next((l[len("TikTok: "):] for l in linhas
                       if l.startswith("TikTok: ")), None)
        falha = next((l[len("TikTok FALHOU: "):] for l in linhas
                      if l.startswith("TikTok FALHOU: ")), None)
        if saida is None:
            resultado["tiktok"] = "sem_confirmacao"
        elif estado is None and falha is None:
            resultado["tiktok"] = ("nao_tentado" if yt_falhou and onde == "ambos"
                                   else "sem_confirmacao")
        else:
            desfecho = _postar().desfecho_do_tiktok(
                estado or "", {"erro": falha} if falha else None)
            # So o sucesso limpo solta o video. Qualquer outra coisa pode ter
            # clicado: vai para a conferencia humana.
            if desfecho == "publicado" and codigo != 0:
                desfecho = "sem_confirmacao"
            resultado["tiktok"] = desfecho
    return resultado


def concluir_publicacao(chave: str, args: dict, aparelho: str,
                        saida: str | None, codigo: int | None) -> dict:
    """Marca o que precisa de conferencia, anota, avisa e solta o "em voo"."""
    resultado = desfechos(saida, codigo, args["onde"])
    soltar = True
    tiktok = resultado.get("tiktok")
    if tiktok not in (None, "publicado", "nao_tentado"):
        ultima = next((l for l in reversed((saida or "").splitlines())
                       if l.startswith("TikTok")), "")
        motivo = (ultima or ("tempo esgotado" if saida is None else
                             f"saída {codigo} sem linha do TikTok"))[:200]
        try:
            _postar()._marcar_para_conferir("builds", args["id"],
                                            f"pelo app: {tiktok}: {motivo}")
        except Exception:                                    # noqa: BLE001
            # Sem a marca, o "em voo" e a unica coisa que segura o video.
            soltar = False
    texto = ", ".join(f"{NOME_DESTINO[d]}: {r}" for d, r in resultado.items())
    if not soltar:
        texto += " (não consegui marcar “a conferir”; o vídeo segue bloqueado no app)"
    ok = all(r == "publicado" for r in resultado.values())
    try:
        registrar(aparelho, "desfecho", {"id": args["id"], "onde": args["onde"]},
                  texto, ok=ok)
    except Exception:                                        # noqa: BLE001
        pass
    avisar_telegram(aparelho, f"publicar {args['id']}", texto)
    if soltar:
        _tirar_do_voo(chave)
    return resultado


def _acompanhar(processo, chave: str, args: dict, aparelho: str) -> None:
    try:
        saida, _ = processo.communicate(timeout=PUBLICAR_TIMEOUT_S)
        codigo = processo.returncode
    except subprocess.TimeoutExpired:
        # Nao mata: pode estar no meio do upload. Vai para a conferencia.
        saida, codigo = None, None
    except Exception:                                        # noqa: BLE001
        saida, codigo = None, None
    try:
        concluir_publicacao(chave, args, aparelho, saida, codigo)
    except Exception:                                        # noqa: BLE001
        pass          # o "em voo" fica: bloqueado e visivel em --em-voo


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
           "alvos_de_pausa", "avisar_telegram", "concluir_publicacao",
           "desfechos", "em_voo", "executar", "liberar", "preparar",
           "registrar", "trava_de_acoes", "usadas_na_ultima_hora",
           "video_para_publicar"]


if __name__ == "__main__":                                   # pragma: no cover
    sys.exit("use pelo servidor: python -m remoto.api_http")
