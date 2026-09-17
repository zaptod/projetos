# -*- coding: utf-8 -*-
"""O que o app do celular le. Dicionarios prontos para JSON, SO LEITURA.

O bot (`comandos.py`) responde em texto para o Telegram; o app precisa dos
mesmos fatos em estrutura, para desenhar a tela. Em vez de fazer o bot e o app
discordarem, este modulo chama as MESMAS fontes que o bot chama:
`atividade`, `controle`, `grade`, os dois catalogos e `relatorios`.

Nada aqui publica, gera, pega trava ou escreve no diario. A unica escrita
indireta e a de `controle.estado()`, que apaga do disco uma pausa ja vencida
— o bot faz a mesma chamada ha semanas.

A PREVISAO do proximo horario (qual historia, qual build, quanta gordura) e
da Vila flutuante: `python -m painel.flutuante.previsao`. Ela roda em
SUBPROCESSO porque o `postar.py` puxa meio projeto na importacao, e NUNCA com
`postar.py --ver`, que grava uma vistoria no diario a cada chamada. Enquanto
aquele modulo nao existir nesta arvore, o campo vem `None` e a tela so nao
mostra o bloco.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

RELATORIOS = ("metas", "funcionamento", "confiabilidade", "auditoria")
MAX_EVENTOS = 200
PREVISAO_VALE_S = 120.0
PREVISAO_TIMEOUT_S = 180


# --------------------------------------------------------------- fontes
# Funcoes pequenas para os testes trocarem sem tocar o disco de verdade.
def _atividade():
    from builds import atividade
    return atividade


def _controle():
    from builds.identity import controle
    return controle


def _grade():
    from builds import grade
    return grade


def _catalogos() -> dict:
    """{canal: modulo de catalogo}. O canal e a chave que o app usa."""
    saida = {}
    try:
        from builds.publicar import catalogo as builds
        saida["builds"] = builds
    except Exception:                                        # noqa: BLE001
        pass
    try:
        from contos.publicar import catalogo as historias
        saida["historias"] = historias
    except Exception:                                        # noqa: BLE001
        pass
    return saida


# --------------------------------------------------------------- estado
def fabricas() -> list[dict]:
    atividade = _atividade()
    estado = atividade.estado_das_fabricas()
    saida = []
    for nome, dados in atividade.FABRICAS.items():
        info = estado.get(nome) or {}
        saida.append({"nome": nome,
                      "rotulo": dados.get("rotulo", nome),
                      "emoji": dados.get("emoji", ""),
                      "faz": dados.get("faz", ""),
                      "status": info.get("status", "ocioso"),
                      "detalhe": info.get("detalhe") or "",
                      "canal": info.get("canal") or "",
                      "ha_s": info.get("ha_s")})
    return saida


def pausa() -> dict:
    estado = _controle().estado()
    return {"situacao": estado.get("situacao", ""),
            "resumo": estado.get("resumo", ""),
            "alvos": sorted((estado.get("pausas") or {}).keys())}


def proxima_postagem() -> dict:
    grade = _grade()
    return {"horario": grade.proximo(), "grade": grade.horarios()}


def estado() -> dict:
    """A tela "Agora" inteira numa chamada."""
    saida: dict = {"agora": datetime.now().isoformat(timespec="seconds"),
                   "erros_de_leitura": []}
    for chave, funcao in (("fabricas", fabricas), ("pausa", pausa),
                          ("proxima", proxima_postagem)):
        try:
            saida[chave] = funcao()
        except Exception as exc:                             # noqa: BLE001
            saida[chave] = None
            saida["erros_de_leitura"].append(f"{chave}: {type(exc).__name__}")
    saida["previsao"] = PREVISAO.ler()
    return saida


# ---------------------------------------------------------------- diario
def _evento(evento: dict) -> dict:
    fabrica = _atividade().FABRICAS.get(evento.get("fabrica"), {})
    return {"ts": str(evento.get("ts", "")),
            "fabrica": str(evento.get("fabrica", "")),
            "emoji": fabrica.get("emoji", ""),
            "status": str(evento.get("status", "")),
            "canal": str(evento.get("canal", "")),
            "etapa": str(evento.get("etapa", "")),
            "detalhe": str(evento.get("detalhe", ""))[:300],
            "dur_s": evento.get("dur_s")}


def diario(desde: str = "", n: int = 60) -> list[dict]:
    """Eventos mais novos que `desde`, do MAIS VELHO para o mais novo.

    Nessa ordem o app so acrescenta no fim da lista. `desde` e o `ts` do
    ultimo evento que o app ja tem; a comparacao e de texto, que para ISO
    no mesmo fuso e a mesma coisa que comparar datas.
    """
    n = max(1, min(int(n), MAX_EVENTOS))
    eventos = _atividade().recentes(n)
    if desde:
        eventos = [e for e in eventos if str(e.get("ts", "")) > desde]
    return [_evento(e) for e in reversed(eventos)]


def erros(n: int = 10) -> list[dict]:
    n = max(1, min(int(n), MAX_EVENTOS))
    eventos = [e for e in _atividade().recentes(MAX_EVENTOS)
               if e.get("status") == "erro"]
    return [_evento(e) for e in eventos[:n]]


# ---------------------------------------------------------------- videos
def _video(canal: str, video) -> dict:
    return {"canal": canal,
            "id": str(video.id),
            "titulo": str(getattr(video, "titulo", "") or ""),
            "perfil": str(getattr(video, "perfil", "") or ""),
            "origem": str(getattr(video, "origem", "") or ""),
            "parte": getattr(video, "parte", None),
            "partes": getattr(video, "partes", None),
            "bytes": int(getattr(video, "bytes", 0) or 0),
            "quando": float(getattr(video, "quando", 0.0) or 0.0),
            "pendencias": list(getattr(video, "pendencias", []) or [])}


def videos(quantos: int = 40) -> list[dict]:
    saida = []
    for canal, catalogo in _catalogos().items():
        try:
            lista = catalogo.listar()
        except Exception:                                    # noqa: BLE001
            continue
        saida.extend(_video(canal, v) for v in lista)
    saida.sort(key=lambda v: v["quando"], reverse=True)
    return saida[:max(1, min(int(quantos), 200))]


def arquivo_do_video(canal: str, video_id: str) -> Path | None:
    """O mp4 daquele id, e SO se ele morar na pasta de saida do catalogo.

    O caminho vem do catalogo, nunca da URL; o id so escolhe entre os que o
    catalogo listou. A conferencia de pasta e a segunda tranca: um catalogo
    que um dia devolva um caminho estranho (link, `..` num json) nao vira
    leitura de arquivo qualquer.
    """
    catalogo = _catalogos().get(canal)
    if catalogo is None or not video_id:
        return None
    try:
        lista = catalogo.listar()
    except Exception:                                        # noqa: BLE001
        return None
    for video in lista:
        if str(video.id) != video_id:
            continue
        try:
            caminho = Path(video.caminho).resolve()
            raiz = Path(catalogo.OUTPUTS).resolve()
        except (OSError, TypeError, AttributeError):
            return None
        if caminho.suffix.lower() != ".mp4" or not caminho.is_file():
            return None
        if not caminho.is_relative_to(raiz):
            return None
        return caminho
    return None


# ------------------------------------------------------------ relatorios
def relatorio(nome: str) -> str | None:
    if nome not in RELATORIOS:
        return None
    from . import relatorios
    return relatorios.montar(nome)


# -------------------------------------------------------------- previsao
class _Previsao:
    """Resultado da previsao guardado por um tempo, recalculado em segundo plano.

    O subprocesso leva de segundos a minutos (mede o audio do build
    escolhido). A tela nao pode esperar isso: ela recebe o ultimo resultado,
    com a idade, e um recalculo e disparado se ele venceu.
    """

    def __init__(self):
        self._trava = threading.Lock()
        self._valor: dict | None = None
        self._quando = 0.0
        self._rodando = False

    @staticmethod
    def disponivel() -> bool:
        try:
            return importlib.util.find_spec("painel.flutuante.previsao") is not None
        except (ImportError, ValueError):
            return False

    def _calcular(self) -> None:
        try:
            saida = subprocess.run(
                [sys.executable, "-X", "utf8", "-m", "painel.flutuante.previsao",
                 "--raiz", str(RAIZ)],
                cwd=str(RAIZ), capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=PREVISAO_TIMEOUT_S,
                creationflags=NO_WINDOW).stdout or ""
            linhas = [l for l in saida.splitlines() if l.strip()]
            valor = json.loads(linhas[-1]) if linhas else {"falhou": "sem saida"}
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            valor = {"falhou": f"{type(exc).__name__}"}
        with self._trava:
            self._valor, self._quando, self._rodando = valor, time.time(), False

    def ler(self) -> dict | None:
        if not self.disponivel():
            return None
        with self._trava:
            vencida = time.time() - self._quando > PREVISAO_VALE_S
            if vencida and not self._rodando:
                self._rodando = True
                threading.Thread(target=self._calcular, daemon=True).start()
            if self._valor is None:
                return {"calculando": True}
            return dict(self._valor, idade_s=round(time.time() - self._quando))


PREVISAO = _Previsao()
