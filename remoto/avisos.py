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

import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

JANELA_S = 24 * 3600
ARQUIVO = None              # os testes apontam para outro lugar
REGISTRO = None
_GUARDA_DIAS = 3
_REGISTRO_MAX = 2000

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


def normalizar(texto: str) -> str:
    """O texto sem o que muda a cada envio (hora, data, idade, pid)."""
    limpo = str(texto or "").lower()
    for padrao in _VOLATEIS:
        limpo = padrao.sub("#", limpo)
    return " ".join(limpo.split())


def _assinatura(texto: str) -> str:
    return hashlib.sha1(normalizar(texto).encode("utf-8")).hexdigest()[:16]


def _ler() -> dict:
    try:
        dados = json.loads(_arquivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar(dados: dict) -> None:
    destino = _arquivo()
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(f".{destino.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, destino)


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
    chave = str(chave or ("texto:" + estado))
    try:
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
                        "texto": " ".join(str(texto).split())[:160]}
        _gravar(_podar(dados, agora))
    except Exception:                                          # noqa: BLE001
        return True
    _anotar(texto, chave, origem, agora)
    return True


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
