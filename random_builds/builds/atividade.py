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
  - O arquivo e podado por IDADE e PRIORIDADE quando passa de ~6 MB (ver
    `_podar`): fica tudo das ultimas 72 h (com teto de linhas, cortando o
    `log` mais velho primeiro) e todo `erro` dos ultimos 7 dias.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

# As fabricas que a Vila conhece. Quem registrar uma desconhecida nao quebra
# nada — ela so aparece na lista de logs, sem predio proprio.
FABRICAS = {
    "chatgpt": {"rotulo": "ChatGPT", "emoji": "🤖", "faz": "roteiros"},
    "gemini": {"rotulo": "Gemini", "emoji": "✨", "faz": "analise e video"},
    "deepseek": {"rotulo": "DeepSeek", "emoji": "🐋", "faz": "roteiros"},
    "picasso": {"rotulo": "PicassoIA", "emoji": "🎨", "faz": "imagens"},
    "digen": {"rotulo": "Digen", "emoji": "🎥", "faz": "video do payoff"},
    "estudio": {"rotulo": "Estúdio", "emoji": "🎬", "faz": "render dos vídeos"},
    "arena": {"rotulo": "Arena", "emoji": "⚔️", "faz": "lutas gravadas"},
    "publicacao": {"rotulo": "Publicação", "emoji": "📤", "faz": "YouTube/TikTok"},
    "mimetizar": {"rotulo": "Espelho", "emoji": "🪞",
                  "faz": "estudo de canal alheio"},
}

TRABALHANDO, OK, ERRO, LOG = "inicio", "ok", "erro", "log"

# A PODA. Ate 05/10/2026 ela cortava por NUMERO de linhas (passou de 4000,
# ficavam as 2000 novas): com a vistoria escrevendo 74% das linhas, o diario
# cobria ~23,6 h e caia para ~12 h depois de cada poda — o relatorio "24 h"
# lia 8,6 h, e um erro da madrugada sumia antes de alguem olhar.
# Agora a poda e por idade e prioridade:
#   - so dispara com o arquivo acima de `_LIMITE_BYTES` (leitura cara, rara);
#   - todo evento das ultimas `_JANELA_S` fica, ate `_TETO_LINHAS`; passou
#     do teto, sai primeiro o `log` mais velho, depois o resto mais velho;
#   - todo `erro` dos ultimos `_ERRO_GUARDA_S` fica, fora do teto (ate
#     `_TETO_ERROS`): e o que a apuracao e o bot procuram dias depois;
#   - linha ilegivel ou sem data sai.
_LIMITE_BYTES = 6_000_000
_JANELA_S = 72 * 3600.0
_ERRO_GUARDA_S = 7 * 24 * 3600.0
_TETO_LINHAS = 12_000
_TETO_ERROS = 3_000
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
              canal: str = "builds", *, etapa: str = "", ref: str = "",
              dur_s: float | None = None) -> None:
    """Anota o evento. Nunca levanta — ver o cabecalho.

    `etapa`, `ref` e `dur_s` sao OPCIONAIS e so aparecem na linha quando tem
    valor: linha sem eles sai byte a byte igual a de antes de 16/09/2026, e
    todo leitor antigo continua valendo.

    Por que os tres, e nao so a duracao: a pergunta e "quanto tempo leva
    cada etapa E O QUE PIOROU". `fabrica` e grossa demais — `estudio` cobre
    render, concat e mix no mesmo rotulo. E sem `ref` (a QUAL coisa o tempo
    pertence) um pico e indistinguivel de uma historia grande.
    """
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
        if etapa:
            linha["etapa"] = str(etapa)[:60]
        if ref:
            linha["ref"] = str(ref)[:80]
        if dur_s is not None:
            linha["dur_s"] = round(float(dur_s), 1)
        caminho = _arquivo()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
        _podar(caminho)
    except Exception:
        pass


def _podar(caminho: Path, agora: datetime | None = None) -> None:
    try:
        if caminho.stat().st_size < _LIMITE_BYTES:
            return
        linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
        mantidas = _o_que_fica(linhas, agora or datetime.now(timezone.utc))
        if len(mantidas) < len(linhas):
            caminho.write_text("".join(linha + "\n" for linha in mantidas),
                               encoding="utf-8")
    except OSError:
        pass


def _o_que_fica(linhas: list[str], agora: datetime) -> list[str]:
    """As linhas que sobrevivem a poda, na ordem original (ver `_LIMITE_BYTES`)."""
    erros: list[int] = []
    comuns: list[tuple[int, bool]] = []          # (indice, e_log)
    for indice, bruta in enumerate(linhas):
        if not bruta.strip():
            continue
        try:
            evento = json.loads(bruta)
            quando = datetime.fromisoformat(str(evento["ts"]))
        except (ValueError, KeyError, TypeError):
            continue
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=timezone.utc)
        idade = (agora - quando).total_seconds()
        if evento.get("status") == ERRO and idade <= _ERRO_GUARDA_S:
            erros.append(indice)
        elif idade <= _JANELA_S:
            comuns.append((indice, evento.get("status") == LOG))
    erros = erros[-_TETO_ERROS:]
    excesso = len(comuns) - _TETO_LINHAS
    if excesso > 0:
        # Os mais velhos primeiro, `log` antes de qualquer outro.
        fora = {i for i, _ in sorted(comuns, key=lambda c: (not c[1], c[0]))[:excesso]}
        comuns = [c for c in comuns if c[0] not in fora]
    ficam = sorted(erros + [i for i, _ in comuns])
    return [linhas[i] for i in ficam]


def _linhas_do_fim(caminho: Path, bloco: int = 65536):
    """As linhas do arquivo, da ultima para a primeira, lendo em blocos.

    `recentes(n)` precisa ir tao fundo quanto o `n` pedido (com filtro de
    fabrica, bem mais fundo que n linhas) sem ler o arquivo inteiro a cada
    chamada — a Vila e o painel perguntam o tempo todo.
    """
    with open(caminho, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        posicao = fh.tell()
        resto = b""
        while posicao > 0:
            passo = min(bloco, posicao)
            posicao -= passo
            fh.seek(posicao)
            pedaco = fh.read(passo) + resto
            partes = pedaco.split(b"\n")
            resto = partes[0]
            for parte in reversed(partes[1:]):
                yield parte.decode("utf-8", errors="replace")
        if resto:
            yield resto.decode("utf-8", errors="replace")


def recentes(n: int = 60, fabrica: str | None = None) -> list:
    """Os ultimos `n` eventos (da `fabrica`, se pedida), do mais novo para o
    mais velho.

    Ate 05/10/2026 so olhava as ultimas 1200 linhas: `recentes(1200,
    fabrica="picasso")` devolvia so os eventos do PicassoIA que cabiam
    nelas, e quem pedia "as ultimas 24 h" recebia ~8,6 h. Agora vai ate
    juntar `n` ou acabar o arquivo.
    """
    if n <= 0:
        return []
    saida = []
    try:
        for bruta in _linhas_do_fim(_arquivo()):
            bruta = bruta.strip()
            if not bruta:
                continue
            try:
                evento = json.loads(bruta)
            except ValueError:
                continue
            if not isinstance(evento, dict):
                continue
            if fabrica and evento.get("fabrica") != fabrica:
                continue
            saida.append(evento)
            if len(saida) >= n:
                break
    except OSError:
        return saida
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

    def __init__(self, nome: str, detalhe: str = "", canal: str = "builds",
                 *, etapa: str = "", ref: str = ""):
        self.nome, self.detalhe, self.canal = nome, detalhe, canal
        self.etapa, self.ref = etapa, ref
        self._comeco = None

    def __enter__(self):
        self._comeco = time.monotonic()
        registrar(self.nome, TRABALHANDO, self.detalhe, self.canal,
                  etapa=self.etapa, ref=self.ref)
        return self

    def anotar(self, detalhe: str) -> None:
        registrar(self.nome, LOG, detalhe, self.canal,
                  etapa=self.etapa, ref=self.ref)

    def marco(self, etapa: str, dur_s: float, detalhe: str = "") -> None:
        """Um sub-tempo dentro da mesma fabrica, sem abrir outro `inicio`.

        Serve para o que acontece em laco (uma cena, um segmento): abrir e
        fechar uma fabrica por item encheria o diario e a poda comeria o
        dia inteiro em poucas horas.
        """
        registrar(self.nome, LOG, detalhe or etapa, self.canal,
                  etapa=etapa, ref=self.ref, dur_s=dur_s)

    def _gasto(self) -> float | None:
        if self._comeco is None:
            return None
        return time.monotonic() - self._comeco

    def __exit__(self, tipo, valor, tb):
        # A DURACAO SAI TAMBEM NO ERRO. Etapa que estoura e justamente a que
        # se quer medir: sem isto, o tempo perdido numa falha some do total
        # do dia e a conta fecha errado para menos.
        if tipo is None:
            registrar(self.nome, OK, self.detalhe, self.canal,
                      etapa=self.etapa, ref=self.ref, dur_s=self._gasto())
        else:
            registrar(self.nome, ERRO, f"{tipo.__name__}: {str(valor)[:200]}",
                      self.canal, etapa=self.etapa, ref=self.ref,
                      dur_s=self._gasto())
        return False


__all__ = ["ERRO", "FABRICAS", "LOG", "OK", "TRABALHANDO",
           "estado_das_fabricas", "estado_por_canal", "fabrica", "recentes",
           "registrar"]
