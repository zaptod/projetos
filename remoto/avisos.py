# -*- coding: utf-8 -*-
"""O porteiro dos avisos: a mesma mensagem nao sai duas vezes no mesmo dia.

Pedido do Adrian (02/10 e 04/10/2026): "essa notificacao infinita da trilha
sonora e do rerender ta me deixando bravo". Medido em 04/10, nas ultimas
48 h: o "🛰 Andamento" do coordenador saiu 14 vezes, 9 delas terminando em
"Fila: ...; primeiro: [builds] Som real nas 15 builds de estoque ainda com
som sintetizado" (um item parado na fila desde 30/09) e 3 sem NENHUMA
novidade; o bot mandou 22 vezes "❗ PicassoIA (historias) No module named
'ias'" (o mesmo erro, um por tentativa do reparo) e 24 vezes "🤖 bot no ar"
(um por religamento do coordenador).

Cada fonte tinha (ou nao) a sua propria regra. Aqui fica uma so, e todo
aviso que sai sem alguem pedir passa por ela:

  * CHAVE e o assunto + o item ("bot.erro|picasso|historias|imagens|...",
    "tailnet"). Sem chave, a chave e o proprio texto normalizado.
  * ESTADO e o texto normalizado: sem hora, data, "ha N min", pid. Duas
    mensagens que so diferem no relogio sao a mesma mensagem.
  * Sai quando a chave e nova, quando o ESTADO mudou ou quando a ultima
    vez foi ha mais de um dia. Senao, conta como calado.

O que foi calado nao some: `calados(horas)` devolve as contagens, e o
relatorio de funcionamento (uma vez por dia) diz quantos e quais. E todo
aviso que SAI vai para `avisos_enviados.jsonl` — ate hoje nao havia registro
nenhum do que chegava ao celular, e "quantas vezes ele recebeu isso?" so se
respondia por deducao.

Nunca levanta: um porteiro quebrado deixa passar (melhor um aviso repetido
do que um aviso perdido).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

JANELA_S = 24 * 3600
ARQUIVO = None              # os testes apontam para outro lugar
REGISTRO = None
PENDENTES = None
_GUARDA_DIAS = 3
_REGISTRO_MAX = 2000

# A TRAVA (APP-12, 14/10). Bot, carteiro, coordenador e cada `remoto
# --avisar` leem, mudam e regravam o estado e a fila INTEIROS. Sem trava,
# medido: de 300 `liberar()` em dois processos sobravam 116 fichas, e o que
# outro processo enfileirava durante uma entrega do bot sumia. A trava e um
# byte de `avisos.lock` (ao lado do estado: cada teste tem a sua), entre
# processos, e reentrante na mesma thread.
TRAVA_PRAZO_S = 10.0
_TRAVA_THREADS = threading.RLock()
_TRAVA_LOCAL = threading.local()

_VOLATEIS = (
    re.compile(r"\d{4}-\d{2}-\d{2}[t ]\d{2}:\d{2}(:\d{2})?(\.\d+)?([+-]\d{2}:\d{2}|z)?"),
    # dd/mm com DOIS digitos: "parte 1/4" e "2/4" sao estados diferentes
    re.compile(r"\b\d{2}/\d{2}(/\d{2,4})?\b"),
    re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b"),
    re.compile(r"\bh[aá] \d+(\.\d+)?\s*(s|min|h|dias?)\b"),
    re.compile(r"\bpid \d+\b"),
)


def _pasta() -> Path:
    # O mesmo runtime do diario: o conftest da raiz aponta este para uma pasta
    # descartavel, e um teste nunca cala (nem registra) aviso de verdade.
    proprio = os.environ.get("NEURAL_FIGHTS_RUNTIME_DIR")
    if proprio:
        return Path(proprio)
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "neural-fights"


def _arquivo() -> Path:
    return Path(ARQUIVO) if ARQUIVO else _pasta() / "avisos_estado.json"


def _registro() -> Path:
    return Path(REGISTRO) if REGISTRO else _pasta() / "avisos_enviados.jsonl"


def _pendentes() -> Path:
    return Path(PENDENTES) if PENDENTES else _pasta() / "avisos_pendentes.jsonl"


def normalizar(texto: str) -> str:
    """O texto sem o que muda a cada envio (hora, data, idade, pid)."""
    limpo = str(texto or "").lower()
    for padrao in _VOLATEIS:
        limpo = padrao.sub("#", limpo)
    return " ".join(limpo.split())


def _assinatura(texto: str) -> str:
    return hashlib.sha1(normalizar(texto).encode("utf-8")).hexdigest()[:16]


def chave_de(texto: str, chave: str | None = None) -> str:
    return str(chave or ("texto:" + _assinatura(texto)))


@contextlib.contextmanager
def _travado():
    """Segura `avisos.lock` (entre processos) durante ler-mudar-gravar.

    Nunca levanta e nunca prende para sempre: passado `TRAVA_PRAZO_S` sem
    conseguir, segue sem trava (o porteiro deixa passar, como sempre).
    """
    if not _TRAVA_THREADS.acquire(timeout=TRAVA_PRAZO_S):
        yield
        return
    try:
        profundidade = getattr(_TRAVA_LOCAL, "n", 0)
        _TRAVA_LOCAL.n = profundidade + 1
        try:
            if profundidade:
                yield
                return
            with _trava_de_arquivo():
                yield
        finally:
            _TRAVA_LOCAL.n = profundidade
    finally:
        _TRAVA_THREADS.release()


@contextlib.contextmanager
def _trava_de_arquivo():
    fh = None
    pegou = False
    try:
        alvo = _arquivo().with_name("avisos.lock")
        alvo.parent.mkdir(parents=True, exist_ok=True)
        fh = open(alvo, "a+b")
        limite = time.monotonic() + TRAVA_PRAZO_S
        while True:
            fh.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:                                        # pragma: no cover
                    import fcntl
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                pegou = True
                break
            except OSError:
                if time.monotonic() >= limite:
                    break
                time.sleep(0.01)
    except OSError:
        pass
    try:
        yield
    finally:
        if fh is not None:
            if pegou:
                with contextlib.suppress(OSError):
                    fh.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                    else:                                    # pragma: no cover
                        import fcntl
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            fh.close()


def _ler_texto(caminho: Path) -> str | None:
    """O texto do arquivo; None se nao existe. PermissionError (o `os.replace`
    de outro processo no meio) tenta de novo antes de desistir."""
    for tentativa in range(5):
        try:
            return caminho.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError:
            if tentativa == 4:
                raise
            time.sleep(0.02)
    return None                                              # pragma: no cover


def _trocar(tmp: Path, destino: Path) -> None:
    for tentativa in range(10):
        try:
            os.replace(tmp, destino)
            return
        except PermissionError:
            if tentativa == 9:
                with contextlib.suppress(OSError):
                    tmp.unlink()
                raise
            time.sleep(0.02)


def _ler() -> dict:
    try:
        texto = _ler_texto(_arquivo())
        dados = json.loads(texto) if texto else {}
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar(dados: dict) -> None:
    destino = _arquivo()
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(f".{destino.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    _trocar(tmp, destino)


def _data(iso) -> datetime | None:
    try:
        return datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return None


def liberar(texto: str, *, chave: str | None = None, origem: str = "",
            agora: datetime | None = None, janela_s: float = JANELA_S) -> bool:
    """True = pode mandar (e fica anotado como enviado). False = calar.

    `chave` e o assunto + item; o ESTADO e o texto normalizado. Mesma chave e
    mesmo estado dentro da janela: cala. Estado novo ou janela vencida: sai.
    """
    agora = agora or datetime.now()
    estado = _assinatura(texto)
    chave = chave_de(texto, chave)
    try:
        with _travado():
            dados = _ler()
            ficha = dados.get(chave) if isinstance(dados.get(chave), dict) else None
            ultimo = _data((ficha or {}).get("em"))
            if (ficha and ficha.get("estado") == estado and ultimo is not None
                    and (agora - ultimo).total_seconds() < janela_s):
                ficha["calados"] = int(ficha.get("calados") or 0) + 1
                ficha["calado_em"] = agora.isoformat(timespec="seconds")
                dados[chave] = ficha
                _gravar(_podar(dados, agora))
                return False
            dados[chave] = {"estado": estado, "em": agora.isoformat(timespec="seconds"),
                            "calados": 0, "origem": origem,
                            "texto": " ".join(str(texto).split())[:160],
                            "_antes": ficha}
            _gravar(_podar(dados, agora))
    except Exception:                                          # noqa: BLE001
        return True
    return True


def confirmar(texto: str, *, chave: str | None = None, origem: str = "",
              agora: datetime | None = None) -> None:
    """Confirma que o aviso saiu e so entao o registra como enviado."""
    agora = agora or datetime.now()
    chave = chave_de(texto, chave)
    try:
        with _travado():
            dados = _ler()
            ficha = dados.get(chave)
            if isinstance(ficha, dict):
                ficha.pop("_antes", None)
                dados[chave] = ficha
                _gravar(_podar(dados, agora))
    except Exception:                                          # noqa: BLE001
        pass
    _anotar(texto, chave, origem, agora)


def desfazer(texto: str, *, chave: str | None = None) -> None:
    """Desfaz a reserva de um aviso que nao conseguiu sair."""
    chave = chave_de(texto, chave)
    try:
        with _travado():
            dados = _ler()
            ficha = dados.get(chave)
            if not isinstance(ficha, dict):
                return
            antes = ficha.get("_antes")
            if antes is None:
                dados.pop(chave, None)
            else:
                dados[chave] = antes
            _gravar(dados)
    except Exception:                                          # noqa: BLE001
        pass


ULTIMA_LEITURA_RUIM = {"linhas": 0}


def pendentes() -> list[dict]:
    """Avisos aguardando rede, na ordem em que falharam.

    Linha a linha (APP-13, 14/10): ate entao UMA linha invalida fazia a lista
    inteira virar `[]`, e o proximo `enfileirar` regravava o arquivo so com o
    item novo — a fila sumia. A linha ruim e pulada e contada.
    """
    try:
        texto = _ler_texto(_pendentes())
    except OSError:
        return []
    itens, ruins = [], 0
    for linha in (texto or "").splitlines():
        if not linha.strip():
            continue
        try:
            item = json.loads(linha)
        except ValueError:
            ruins += 1
            continue
        if isinstance(item, dict):
            itens.append(item)
        else:
            ruins += 1
    ULTIMA_LEITURA_RUIM["linhas"] = ruins
    return itens


def guardar_pendentes(itens: list[dict]) -> None:
    try:
        with _travado():
            destino = _pendentes()
            destino.parent.mkdir(parents=True, exist_ok=True)
            tmp = destino.with_name(f".{destino.name}.{os.getpid()}.tmp")
            tmp.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n"
                                   for item in itens), encoding="utf-8")
            _trocar(tmp, destino)
    except Exception:                                          # noqa: BLE001
        pass


def _mesmo_item(a: dict, b: dict) -> bool:
    return (a.get("chave"), a.get("em"), a.get("texto")) == (
        b.get("chave"), b.get("em"), b.get("texto"))


def retirar_pendentes(saidos: list[dict]) -> None:
    """Tira da fila SO os itens dados (entregues ou descartados), relendo-a
    dentro da trava: o que outro processo enfileirou no meio fica."""
    if not saidos:
        return
    try:
        with _travado():
            atuais = pendentes()
            sobra = [i for i in atuais if not any(_mesmo_item(i, s) for s in saidos)]
            if len(sobra) != len(atuais):
                guardar_pendentes(sobra)
    except Exception:                                          # noqa: BLE001
        pass


def enfileirar(texto: str, *, chave: str | None = None, origem: str = "",
              agora: datetime | None = None) -> None:
    # ACRESCENTA uma linha (nao relê e regrava a fila): uma leitura que falhe
    # nunca vira "fila vazia + o item novo".
    linha = json.dumps({"texto": str(texto), "chave": chave_de(texto, chave),
                        "origem": origem, "em": (agora or datetime.now()).isoformat(
                            timespec="seconds")}, ensure_ascii=False)
    try:
        with _travado():
            destino = _pendentes()
            destino.parent.mkdir(parents=True, exist_ok=True)
            with destino.open("ab") as fh:
                fh.seek(0, os.SEEK_END)
                inicio = b""
                if fh.tell() > 0:
                    with destino.open("rb") as leitura:
                        leitura.seek(-1, os.SEEK_END)
                        if leitura.read(1) != b"\n":
                            inicio = b"\n"
                fh.write(inicio + linha.encode("utf-8") + b"\n")
    except Exception:                                          # noqa: BLE001
        pass


def _podar(dados: dict, agora: datetime) -> dict:
    corte = agora - timedelta(days=_GUARDA_DIAS)
    return {k: v for k, v in dados.items()
            if isinstance(v, dict) and (_data(v.get("calado_em") or v.get("em")) or agora) >= corte}


def _anotar(texto: str, chave: str, origem: str, agora: datetime) -> None:
    """Uma linha por aviso que SAIU. Podado para as ultimas `_REGISTRO_MAX`."""
    try:
        destino = _registro()
        destino.parent.mkdir(parents=True, exist_ok=True)
        linha = json.dumps({"em": agora.isoformat(timespec="seconds"), "origem": origem,
                            "chave": chave, "texto": str(texto)[:500]}, ensure_ascii=False)
        with destino.open("a", encoding="utf-8") as fh:
            fh.write(linha + "\n")
        if destino.stat().st_size > 1_500_000:
            linhas = destino.read_text(encoding="utf-8").splitlines()[-_REGISTRO_MAX:]
            destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    except Exception:                                          # noqa: BLE001
        pass


def calados(horas: int = 24, agora: datetime | None = None) -> list[dict]:
    """[{chave, texto, calados}] do que foi calado nas ultimas `horas`."""
    agora = agora or datetime.now()
    corte = agora - timedelta(hours=horas)
    saida = []
    for chave, ficha in _ler().items():
        if not isinstance(ficha, dict) or not ficha.get("calados"):
            continue
        quando = _data(ficha.get("calado_em"))
        if quando is None or quando < corte:
            continue
        saida.append({"chave": chave, "texto": ficha.get("texto", ""),
                      "calados": int(ficha["calados"])})
    return sorted(saida, key=lambda f: -f["calados"])
