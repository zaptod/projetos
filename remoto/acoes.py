# -*- coding: utf-8 -*-
"""As acoes que o app do celular pode pedir. Tabela FECHADA, com guardas.

Fase 2 do app. Cada acao e uma das funcoes que o bot ja usa (`controle`,
`comandos`), nunca texto executado. O que este modulo acrescenta e o que um
botao no bolso exige a mais que um comando digitado:

  DOIS PASSOS no que nao se desfaz (parar, gerar, publicar). `preparar` NAO
  executa: devolve o texto que a tela mostra ("Publicar «titulo» no
  TikTok?"). So a confirmacao executa — e ela chama `preparar` DE NOVO,
  porque em 60 segundos a grade pode ter publicado o mesmo video.

  GUARDAS DE PUBLICACAO. O Adrian passou a noite de 16 para 17/09 limpando
  repostagem; publicar pelo app nao pode ser o oitavo caminho que fura as
  guardas do `postar.py`. Aqui se aplicam as mesmas leituras:
    - o video ja saiu naquele destino (`metricas.publicado`);
    - OUTRO video ja pos o mesmo titulo no ar ali (`titulos`);
    - a outra variante (A/B) da mesma geracao ja saiu ali;
    - o TikTok marcou o video "a conferir" (clique sem confirmacao);
    - ha uma postagem da grade em curso (mesmo perfil de Chrome);
    - o video tem pendencia ou nao e do perfil celular.

  ID EXATO. `comandos.publicar` acha o video pelo COMECO do id, e
  `generation_00023:build:normal:` e comeco de `...:B` — o botao publicaria a
  variante errada. Aqui o id e comparado inteiro e a linha de comando e
  montada com ele (o mesmo `main.py publicar` que o bot dispara).

  LIMITE: gerar + publicar, no maximo `LIMITE_POR_HORA` por aparelho.

  RASTRO: toda acao executada vai para `app_celular_acoes.jsonl` e vira um
  aviso no Telegram. O `atividade.jsonl` nao e tocado.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from .config import runtime_dir

MINUTOS_MIN, MINUTOS_MAX = 15, 24 * 60
LIMITE_POR_HORA = 6
CONFIRMAR_VALE_S = 60
# A postagem da grade que dispara em :37 roda ate :55. Antes dela, a folga
# e maior que a da suite (:25): um upload manual leva uns 5 minutos, e o que
# comecar as :24 ainda estaria no Chrome quando a grade abrir o mesmo perfil.
# A mesma folga vale para os horarios de minuto proprio (12:07, 17:57).
JANELA_ANTES_MIN, JANELA_DEPOIS_MIN = 20, 18
# Uma publicacao pedida pelo app so entra no ledger quando o upload termina.
# Ate la, a mesma geracao (ou o mesmo video) nao pode ser pedida de novo.
EM_VOO_MIN = 45
DESTINOS = {"youtube": ("youtube",), "tiktok": ("tiktok",),
            "ambos": ("youtube", "tiktok")}
NOME_DESTINO = {"youtube": "YouTube", "tiktok": "TikTok"}
CONTAM_NO_LIMITE = ("gerar", "publicar")
TRAVA_HISTORIAS = "historias__auto"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

ARQUIVO_RASTRO = None                     # os testes apontam para outro lugar


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


def alvos_de_pausa() -> list[str]:
    try:
        from builds.identity import config
        provedores = sorted(config.PROVEDORES)
    except Exception:                                        # noqa: BLE001
        provedores = []
    return [_controle().TUDO] + provedores


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


def gerando_builds() -> bool | None:
    """Ha um `main.py generate-video` rodando? None = nao sei.

    A geracao de builds nao tem trava propria (as travas sao por perfil),
    entao a pergunta vai para a lista de processos.
    """
    script = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe' or "
              "Name='pythonw.exe'\" | ForEach-Object { $_.CommandLine }")
    try:
        saida = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, creationflags=NO_WINDOW).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return None
    return any("generate-video" in linha and "main.py" in linha
               for linha in saida.splitlines())


def postagem_em_curso(agora: datetime | None = None) -> str | None:
    """O horario da grade cuja postagem esta rodando agora, ou None."""
    agora = agora or _agora()
    for texto in _grade().horarios():
        hora, minuto = (int(x) for x in texto.split(":"))
        for dias in (-1, 0, 1):
            slot = (agora.replace(hour=hora, minute=minuto, second=0,
                                  microsecond=0) + timedelta(days=dias))
            if (slot - timedelta(minutes=JANELA_ANTES_MIN) <= agora
                    <= slot + timedelta(minutes=JANELA_DEPOIS_MIN)):
                return texto
    return None


# ------------------------------------------------------------------ rastro
def caminho_rastro() -> Path:
    return Path(ARQUIVO_RASTRO) if ARQUIVO_RASTRO else \
        runtime_dir() / "app_celular_acoes.jsonl"


def registrar(aparelho: str, acao: str, args: dict, resultado: str,
              ok: bool = True) -> dict:
    from .api_http import trava_arquivo
    linha = {"quando": _agora().isoformat(timespec="seconds"),
             "aparelho": aparelho, "acao": acao, "args": args,
             "ok": ok, "resultado": str(resultado)[:300]}
    alvo = caminho_rastro()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    with trava_arquivo(alvo.with_suffix(".lock")):
        with open(alvo, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return linha


def usadas_na_ultima_hora(aparelho: str, agora: datetime | None = None) -> int:
    agora = agora or _agora()
    limite = agora - timedelta(hours=1)
    total = 0
    try:
        with open(caminho_rastro(), encoding="utf-8") as fh:
            linhas = fh.readlines()[-500:]
    except OSError:
        return 0
    for bruta in linhas:
        try:
            linha = json.loads(bruta)
            quando = datetime.fromisoformat(linha["quando"])
        except (ValueError, KeyError, TypeError):
            continue
        if (linha.get("aparelho") == aparelho and linha.get("ok")
                and linha.get("acao") in CONTAM_NO_LIMITE and quando >= limite):
            total += 1
    return total


def publicacoes_em_voo(agora: datetime | None = None) -> list[dict]:
    """Publicacoes que o app disparou ha pouco (qualquer aparelho).

    O ledger ainda nao as tem: o `main.py publicar` grava so no fim. Sem
    esta lista, publicar a variante A e logo depois a B passaria pelas
    duas guardas.
    """
    agora = agora or _agora()
    limite = agora - timedelta(minutes=EM_VOO_MIN)
    saida = []
    try:
        with open(caminho_rastro(), encoding="utf-8") as fh:
            linhas = fh.readlines()[-500:]
    except OSError:
        return []
    for bruta in linhas:
        try:
            linha = json.loads(bruta)
            quando = datetime.fromisoformat(linha["quando"])
        except (ValueError, KeyError, TypeError):
            continue
        if (linha.get("acao") == "publicar" and linha.get("ok")
                and quando >= limite and isinstance(linha.get("args"), dict)):
            saida.append(linha["args"])
    return saida


def _escapar_markdown(texto: str) -> str:
    for sinal in ("\\", "_", "*", "`", "["):
        texto = texto.replace(sinal, "\\" + sinal)
    return texto


def avisar_telegram(aparelho: str, acao: str, resultado: str) -> None:
    """Em segundo plano: o Telegram lento nao segura a resposta do app."""
    texto = _escapar_markdown(
        f"📱 pelo app ({aparelho}): {acao} — {str(resultado)[:300]}")

    def enviar():
        try:
            from .__main__ import avisar
            avisar(texto)
        except Exception:                                    # noqa: BLE001
            pass

    threading.Thread(target=enviar, daemon=True).start()


# ---------------------------------------------------------------- guardas
def _destinos_do_ledger(linha: dict) -> str:
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
    except Exception:                                        # noqa: BLE001
        return set()


def video_para_publicar(video_id: str, onde: str, agora: datetime | None = None):
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

    em_curso = postagem_em_curso(agora)
    if em_curso:
        raise Recusa(f"a postagem das {em_curso} está em curso (usa o mesmo "
                     "Chrome); tente de novo depois")

    metricas = _metricas()
    titulos = _titulos()
    try:
        linhas = [l for l in metricas.publicados("builds") if isinstance(l, dict)]
    except Exception as exc:                                 # noqa: BLE001
        # Sem ledger nao da para saber o que ja saiu. O postar deixa passar
        # ("nao sei" nao barra a grade); um botao manual nao tem essa pressa.
        raise Recusa("não consegui ler o registro de publicações "
                     f"({type(exc).__name__})") from exc

    fonte = getattr(video, "fonte_id", "") or ""
    conferir = _a_conferir_no_tiktok()
    em_voo = publicacoes_em_voo(agora)
    for destino in DESTINOS[onde]:
        nome = NOME_DESTINO[destino]
        for pedido in em_voo:
            if destino not in DESTINOS.get(pedido.get("onde"), ()):
                continue
            if pedido.get("id") == video.id:
                raise Recusa(f"esse vídeo já foi mandado ao {nome} pelo app há "
                             "pouco; espere o envio terminar")
            if fonte and pedido.get("fonte") == fonte:
                raise Recusa(f"a outra variante de {fonte} foi mandada ao {nome} "
                             "pelo app há pouco")
        saidas = [l for l in linhas if _destinos_do_ledger(l) == destino
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


def _limite(aparelho: str) -> None:
    usadas = usadas_na_ultima_hora(aparelho)
    if usadas >= LIMITE_POR_HORA:
        raise Recusa(f"limite de {LIMITE_POR_HORA} gerações/publicações por "
                     "hora pelo app; tente mais tarde")


def preparar(acao: str, args, aparelho: str) -> dict:
    """{acao, args, dois_passos, texto}. Valida tudo; nao executa nada."""
    if not isinstance(args, dict):
        raise Recusa("argumentos inválidos")
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
        return {"acao": acao, "args": {}, "dois_passos": True,
                "texto": ("Parar a produção? O worker das imagens e vídeos dos "
                          "builds termina o job atual, fecha o navegador e "
                          "encerra. As imagens das histórias também ficam "
                          "paradas até você tocar em Retomar. A postagem da "
                          "grade NÃO para. Para voltar: Retomar, aqui no app.")}
    if acao == "gerar":
        _limite(aparelho)
        if trava_ocupada(TRAVA_HISTORIAS):
            raise Recusa("já está gerando: a rodada automática de histórias "
                         "está rodando")
        gerando = gerando_builds()
        if gerando:
            raise Recusa("já está gerando: há uma build sendo feita agora")
        aviso = ("" if gerando is False else
                 " (não consegui conferir se já há uma build rodando)")
        return {"acao": acao, "args": {}, "dois_passos": True,
                "texto": ("Gerar uma build nova (roleta + vídeo)? Usa as contas "
                          f"compartilhadas e leva alguns minutos.{aviso}")}
    if acao == "publicar":
        _limite(aparelho)
        video_id = str(args.get("id") or "")
        onde = str(args.get("onde") or "")
        video = video_para_publicar(video_id, onde)
        destinos = " e no ".join(NOME_DESTINO[d] for d in DESTINOS[onde])
        return {"acao": acao,
                "args": {"id": video.id, "onde": onde,
                         "fonte": getattr(video, "fonte_id", "") or ""},
                "dois_passos": True,
                "texto": f"Publicar «{video.titulo}» no {destinos}? "
                         "Não dá para desfazer pelo app."}
    raise Recusa(f"ação desconhecida: {acao}")


def executar(acao: str, args: dict) -> str:
    """Faz de verdade. So e chamada com `args` que sairam de `preparar`."""
    controle = _controle()
    if acao == "pausar":
        return controle.pausar(args["alvo"], "pelo app",
                               args.get("minutos")).get("resumo", "pausado")
    if acao == "retomar":
        return controle.retomar(args.get("alvo")).get("resumo", "retomado")
    if acao == "parar":
        return controle.pedir_parada("pelo app").get("resumo", "parada pedida")
    comandos = _comandos()
    if acao == "gerar":
        return comandos.gerar()
    if acao == "publicar":
        onde = args["onde"]
        comando = [comandos.PY, "main.py", "publicar", args["id"]]
        if "youtube" in DESTINOS[onde]:
            comando += ["--youtube"]
        if "tiktok" in DESTINOS[onde]:
            comando += ["--tiktok", "--postar"]
        return comandos._rodar(comando, comandos.RANDOM_BUILDS,
                               f"publicar {args['id']} em {onde}")
    raise Recusa(f"ação desconhecida: {acao}")


# ---------------------------------------------------------- confirmacoes
class Pendentes:
    """Pedidos de dois passos esperando o "sim". Em memoria, de uso unico."""

    def __init__(self):
        self._trava = threading.Lock()
        self._itens: dict[str, dict] = {}

    def guardar(self, pedido: dict, dono: str) -> str:
        import secrets
        agora = time.time()
        codigo = secrets.token_urlsafe(16)
        with self._trava:
            self._itens = {k: v for k, v in self._itens.items()
                           if v["expira"] > agora}
            self._itens[codigo] = dict(pedido, dono=dono,
                                       expira=agora + CONFIRMAR_VALE_S)
        return codigo

    def tirar(self, codigo: str, dono: str) -> dict | None:
        """O pedido, se o codigo existe, e do mesmo aparelho e nao venceu.

        O codigo sai da lista em qualquer caso em que existia: um "sim" que
        falhou nao pode ser repetido.
        """
        with self._trava:
            pedido = self._itens.get(str(codigo or ""))
            if pedido is None or pedido["dono"] != dono:
                return None
            del self._itens[str(codigo)]
        if pedido["expira"] < time.time():
            return None
        return pedido


__all__ = ["CONFIRMAR_VALE_S", "LIMITE_POR_HORA", "Pendentes", "Recusa",
           "alvos_de_pausa", "avisar_telegram", "executar", "preparar",
           "registrar", "usadas_na_ultima_hora", "video_para_publicar"]


if __name__ == "__main__":                                   # pragma: no cover
    sys.exit("use pelo servidor: python -m remoto.api_http")
