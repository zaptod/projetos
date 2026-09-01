# -*- coding: utf-8 -*-
"""O diario das FABRICAS: quem esta trabalhando, no que, e o que deu errado.

E a fonte de verdade da Vila (a pagina gamificada do painel): cada etapa da
pipeline — dos dois projetos — anota aqui quando comeca, termina ou falha em
uma fabrica. O painel le e desenha os bots indo trabalhar; um erro vira um
log na tela em vez de uma excecao perdida num console.

Uma linha JSONL por evento, em `%LOCALAPPDATA%/neural-fights/atividade.jsonl`
(fora do repo, compartilhado pelos dois projetos):

    {"ts": ..., "fabrica": "picasso", "canal": "historias",
     "status": "inicio|ok|erro|log", "detalhe": "..."}

Regras de sobrevivencia:
  - `registrar` NUNCA levanta: o diario e observabilidade, e observabilidade
    que derruba a pipeline e pior que nenhuma.
  - O arquivo e podado quando passa de ~4000 linhas (ficam as 2000 novas).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# As fabricas que a Vila conhece. Quem registrar uma desconhecida nao quebra
# nada — ela so aparece na lista de logs, sem predio proprio.
FABRICAS = {
    "chatgpt": {"rotulo": "ChatGPT", "emoji": "🤖", "faz": "roteiros"},
    "gemini": {"rotulo": "Gemini", "emoji": "✨", "faz": "roteiros"},
    "picasso": {"rotulo": "PicassoIA", "emoji": "🎨", "faz": "imagens"},
    "digen": {"rotulo": "Digen", "emoji": "🎥", "faz": "video do payoff"},
    "estudio": {"rotulo": "Estúdio", "emoji": "🎬", "faz": "render dos vídeos"},
    "arena": {"rotulo": "Arena", "emoji": "⚔️", "faz": "lutas gravadas"},
    "publicacao": {"rotulo": "Publicação", "emoji": "📤", "faz": "YouTube/TikTok"},
}

TRABALHANDO, OK, ERRO, LOG = "inicio", "ok", "erro", "log"
_LIMITE_LINHAS = 4000
_PODA_PARA = 2000
# Sem um "ok" nem "erro" depois disto, o inicio e considerado morto (processo
# derrubado no meio): a fabrica nao pode ficar "trabalhando" para sempre.
INICIO_VELHO_S = 2 * 3600.0


def _vivo(pid) -> bool | None:
    """O processo ainda existe? None quando nao da para saber.

    None e diferente de False de proposito: evento antigo (gravado antes de
    haver `pid`) ou PID de outra maquina nao podem ser tratados como morte,
    senao a Vila apagaria trabalho de verdade.
    """
    try:
        numero = int(pid)
    except (TypeError, ValueError):
        return None
    if numero <= 0:
        return None
    try:
        if os.name == "nt":
            import ctypes
            # 0x0400 = PROCESS_QUERY_INFORMATION; sem direito de abrir, o
            # processo existe e e de outro usuario -- ainda e "vivo".
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, numero)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return ctypes.windll.kernel32.GetLastError() != 87   # 87 = sumiu
        os.kill(numero, 0)
        return True
    except PermissionError:
        return True
    except (OSError, AttributeError):
        return False


def _arquivo() -> Path:
    try:
        from .contas import runtime_dir
        return runtime_dir() / "atividade.jsonl"
    except Exception:
        return Path(__file__).resolve().parents[1] / "outputs" / "atividade.jsonl"


def registrar(fabrica: str, status: str, detalhe: str = "",
              canal: str = "builds") -> None:
    """Anota o evento. Nunca levanta — ver o cabecalho."""
    try:
        linha = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            # QUEM esta rodando. Sem isto, "trabalhando" so podia ser
            # desmentido pelo relogio: um `inicio` sem `ok` era considerado
            # morto depois de 2 h, o que dava as duas respostas erradas --
            # job legitimo de 3 h aparecia ocioso, e processo derrubado
            # ficava trabalhando na tela por duas horas.
            "pid": os.getpid(),
            "fabrica": str(fabrica), "canal": str(canal),
            "status": str(status), "detalhe": str(detalhe)[:300],
        }
        caminho = _arquivo()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
        _podar(caminho)
    except Exception:
        pass


def _podar(caminho: Path) -> None:
    try:
        if caminho.stat().st_size < _LIMITE_LINHAS * 120:
            return
        linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(linhas) > _LIMITE_LINHAS:
            caminho.write_text("\n".join(linhas[-_PODA_PARA:]) + "\n",
                               encoding="utf-8")
    except OSError:
        pass


def recentes(n: int = 60, fabrica: str | None = None) -> list:
    """Os ultimos eventos, do mais novo para o mais velho."""
    try:
        with open(_arquivo(), encoding="utf-8", errors="replace") as fh:
            linhas = fh.readlines()[-1200:]
    except OSError:
        return []
    saida = []
    for bruta in reversed(linhas):
        bruta = bruta.strip()
        if not bruta:
            continue
        try:
            evento = json.loads(bruta)
        except ValueError:
            continue
        if fabrica and evento.get("fabrica") != fabrica:
            continue
        saida.append(evento)
        if len(saida) >= n:
            break
    return saida


def _idade_s(ts: str) -> float:
    try:
        quando = datetime.fromisoformat(str(ts))
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - quando).total_seconds()
    except ValueError:
        return float("inf")


def estado_das_fabricas() -> dict:
    """{fabrica: {"status": trabalhando|erro|ocioso, "detalhe", "canal", "ha_s"}}.

    O ultimo evento de cada fabrica manda: um `inicio` recente sem `ok`/`erro`
    depois = trabalhando; `erro` = com problema (ate a proxima atividade);
    o resto = ociosa. Um `inicio` de horas atras e processo morto, nao
    trabalho — vira ocioso para o bot nao morar na fabrica.
    """
    ultimo: dict[str, dict] = {}
    for evento in recentes(600):
        chave = evento.get("fabrica")
        if not chave or chave in ultimo:
            continue
        if evento.get("status") == LOG:
            continue
        ultimo[chave] = evento
        if len(ultimo) >= len(FABRICAS) + 4:
            break

    saida = {}
    for fabrica in FABRICAS:
        evento = ultimo.get(fabrica)
        if evento is None:
            saida[fabrica] = {"status": "ocioso", "detalhe": "", "canal": "",
                              "ha_s": None}
            continue
        idade = _idade_s(evento.get("ts", ""))
        status = evento.get("status")
        if status == TRABALHANDO and _trabalhando_de_verdade(evento, idade):
            situacao = "trabalhando"
        elif status == ERRO:
            situacao = "erro"
        else:
            situacao = "ocioso"
        saida[fabrica] = {"status": situacao,
                          "detalhe": evento.get("detalhe", ""),
                          "canal": evento.get("canal", ""),
                          "ha_s": round(idade, 1)}
    return saida


def _trabalhando_de_verdade(evento: dict, idade: float) -> bool:
    """Um `inicio` sem `ok`/`erro` depois: ainda esta acontecendo?

    O PID manda quando ele diz alguma coisa: processo vivo continua
    trabalhando por mais tempo que passe, e processo morto para de trabalhar
    na hora. So quando o PID nao responde (evento velho, de antes de existir
    `pid`, ou de outra maquina) e que o relogio decide, como antes.
    """
    vivo = _vivo(evento.get("pid"))
    if vivo is True:
        return True
    if vivo is False:
        return False
    return idade <= INICIO_VELHO_S


def estado_por_canal() -> dict:
    """{(fabrica, canal): {status, detalhe, ha_s}} — dois canais, dois bots.

    `estado_das_fabricas` guarda so o evento mais novo POR FABRICA, entao
    builds e historias trabalhando no mesmo provedor viravam um so: o mais
    recente apagava o outro. Para a Vila mostrar o mundo como ele e, a chave
    precisa incluir o canal.
    """
    ultimo: dict[tuple, dict] = {}
    for evento in recentes(600):
        fabrica_nome = evento.get("fabrica")
        if not fabrica_nome or evento.get("status") == LOG:
            continue
        chave = (fabrica_nome, evento.get("canal") or "")
        if chave in ultimo:
            continue
        ultimo[chave] = evento

    saida = {}
    for chave, evento in ultimo.items():
        idade = _idade_s(evento.get("ts", ""))
        status = evento.get("status")
        if status == TRABALHANDO and _trabalhando_de_verdade(evento, idade):
            situacao = "trabalhando"
        elif status == ERRO:
            situacao = "erro"
        else:
            situacao = "ocioso"
        saida[chave] = {"status": situacao,
                        "detalhe": evento.get("detalhe", ""),
                        "ha_s": round(idade, 1),
                        "pid": evento.get("pid")}
    return saida


class fabrica:
    """`with atividade.fabrica("picasso", "3 cenas", canal="historias"):`

    Anota inicio na entrada; `ok` na saida limpa, `erro` (com o tipo e a
    mensagem) quando estourar — e re-levanta: o diario observa, nao engole.
    """

    def __init__(self, nome: str, detalhe: str = "", canal: str = "builds"):
        self.nome, self.detalhe, self.canal = nome, detalhe, canal

    def __enter__(self):
        registrar(self.nome, TRABALHANDO, self.detalhe, self.canal)
        return self

    def anotar(self, detalhe: str) -> None:
        registrar(self.nome, LOG, detalhe, self.canal)

    def __exit__(self, tipo, valor, tb):
        if tipo is None:
            registrar(self.nome, OK, self.detalhe, self.canal)
        else:
            registrar(self.nome, ERRO, f"{tipo.__name__}: {str(valor)[:200]}",
                      self.canal)
        return False


__all__ = ["ERRO", "FABRICAS", "LOG", "OK", "TRABALHANDO",
           "estado_das_fabricas", "estado_por_canal", "fabrica", "recentes",
           "registrar"]
