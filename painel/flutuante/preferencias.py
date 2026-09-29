# -*- coding: utf-8 -*-
"""Onde a janela estava, de que tamanho e se fica por cima — e como ela
terminou da ultima vez (a caixa-preta, la embaixo).

E o UNICO arquivo que a janela escreve (`flutuante.json` no runtime), e ele
e dela: nao e estado do sistema.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

MODOS = ("mini", "medio", "grande", "icone")

# A tela dele e 1366x768 com a barra do Windows de ~40 px. O MEDIO nao passa
# de 720x520 (pedido explicito); o GRANDE cresce ate caber.
TAMANHOS = {"mini": (340, 64), "medio": (720, 520), "icone": (56, 56)}
GRANDE_MAX = (1180, 700)
BARRA_DO_WINDOWS = 48

PADRAO = {"modo": "medio", "anterior": "medio", "topo": True,
          "x": None, "y": None, "aba": "diario", "terminal": "postar",
          "gaveta": False, "arte": "fofa", "colecao": None,
          # a caixa-preta (ver `abrir_vida`)
          "vida": None, "quedas": None, "fechar_pedido": None}
# So a fofa: a classica em pixel foi aposentada (28/09/2026). Quem tinha
# "classico" guardado volta para a fofa pelo `ler`.
ARTES = ("fofa",)
# Um enfeite novo na Vila a cada N publicacoes do dia (o "passatempo").
PUBLICACOES_POR_ENFEITE = 3
ENFEITES = 6


def atualizar_colecao(prefs: dict, publicados_hoje: int, dia: str) -> int:
    """O nivel de enfeites de hoje. Guarda o dia e o recorde em `prefs`.

    Nunca desce no mesmo dia (um ledger relido pela metade nao pode tirar
    enfeite da tela); vira o dia, recomeca do zero. Devolve o nivel.
    """
    nivel = min(ENFEITES, max(0, int(publicados_hoje)) //
                PUBLICACOES_POR_ENFEITE)
    atual = prefs.get("colecao") if isinstance(prefs.get("colecao"),
                                               dict) else {}
    if atual.get("dia") == dia:
        nivel = max(nivel, int(atual.get("nivel") or 0))
    recorde = max(nivel, int(atual.get("recorde") or 0))
    prefs["colecao"] = {"dia": dia, "nivel": nivel, "recorde": recorde}
    return nivel


def tamanho(modo: str, tela: tuple) -> tuple:
    if modo == "grande":
        return (min(GRANDE_MAX[0], tela[0] - 24),
                min(GRANDE_MAX[1], tela[1] - BARRA_DO_WINDOWS - 12))
    return TAMANHOS.get(modo, TAMANHOS["medio"])


def encaixar(x, y, largura: int, altura: int, tela: tuple) -> tuple:
    """A posicao dentro da tela. Sem posicao salva: canto superior direito.

    Salvo com outro monitor (ou antes de trocar de tamanho), a janela podia
    nascer fora da tela — e uma janela sem borda fora da tela nao tem como
    ser puxada de volta.
    """
    livre_x = max(0, tela[0] - largura)
    livre_y = max(0, tela[1] - BARRA_DO_WINDOWS - altura)
    if x is None or y is None:
        return livre_x - 16 if livre_x >= 16 else livre_x, min(16, livre_y)
    return (min(max(0, int(x)), livre_x), min(max(0, int(y)), livre_y))


def ler(caminho: Path) -> dict:
    dados = dict(PADRAO)
    try:
        with open(caminho, encoding="utf-8") as fh:
            salvo = json.load(fh)
        if isinstance(salvo, dict):
            dados.update({k: v for k, v in salvo.items() if k in PADRAO})
    except (OSError, ValueError):
        pass
    if dados["modo"] not in MODOS:
        dados["modo"] = "medio"
    if dados["anterior"] not in MODOS or dados["anterior"] == "icone":
        dados["anterior"] = "medio"
    if dados["arte"] not in ARTES:
        dados["arte"] = "fofa"
    return dados


def gravar(caminho: Path, dados: dict) -> bool:
    """Grava de um jeito que nao deixa arquivo pela metade. Nunca levanta."""
    try:
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = caminho.with_suffix(".tmp")
        temporario.write_text(json.dumps(
            {k: dados.get(k) for k in PADRAO}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        os.replace(temporario, caminho)
        return True
    except OSError:
        return False


# ------------------------------------------------------------ caixa-preta
# Em 27/09/2026 a Vila morreu TRES vezes num dia (a de antes das 18:50, a
# 17020 e a 18316) e nao deu para saber de que: pythonw nao tem console, e a
# janela nao deixava rastro nenhum de como terminava. O unico sinal era o
# PID trocado. Daqui em diante ela anota, neste mesmo arquivo:
#
#   vida           quem esta no ar (pid), desde quando, e o ultimo "estou
#                  viva" (a cada VIVO_S). E o "visto" que diz A HORA da
#                  queda — sem ele, so se sabe que foi em algum momento do
#                  dia;
#   quedas         as ultimas QUEDAS_GUARDADAS vidas que acabaram SEM passar
#                  pelo "Fechar de verdade": morte de fora (TerminateProcess,
#                  "Finalizar tarefa" do Gerenciador) ou queda do processo.
#                  Queda nativa ainda aparece no Visualizador de Eventos
#                  (Aplicativo, pythonw.exe, 1000/1001); morte de fora, so
#                  aqui. Se o Windows ligou depois do ultimo sinal, a queda
#                  diz `windows_reiniciou`;
#   fechar_pedido  quantas vezes o SISTEMA pediu para fechar (WM_CLOSE). Ate
#                  28/09 isso DESTRUIA a janela calada; hoje vira o icone, e
#                  a conta mostra se isso acontece na pratica.
VIVO_S = 300
QUEDAS_GUARDADAS = 10


def _agora(agora: datetime | None = None) -> datetime:
    return agora or datetime.now().astimezone()


def _iso(momento: datetime) -> str:
    return momento.isoformat(timespec="seconds")


def _ler_iso(texto) -> datetime | None:
    try:
        return datetime.fromisoformat(str(texto))
    except (TypeError, ValueError):
        return None


def inicio_do_windows(agora: datetime | None = None) -> datetime | None:
    """Quando o Windows ligou (conta o tempo dormindo), ou None fora dele."""
    try:
        import ctypes
        contador = ctypes.windll.kernel32.GetTickCount64
        contador.restype = ctypes.c_ulonglong
        return _agora(agora) - timedelta(milliseconds=contador())
    except (AttributeError, OSError):
        return None


def abrir_vida(prefs: dict, pid: int, agora: datetime | None = None,
               ligado_em: datetime | None = None) -> dict | None:
    """Anota que ESTA janela nasceu. Devolve a queda da anterior, se houve.

    A anterior caiu quando deixou uma `vida` de outro PID sem `saiu` — o
    `sair()` (menu "Fechar de verdade") marca `saiu` antes de gravar.
    """
    agora = _agora(agora)
    anterior = prefs.get("vida") if isinstance(prefs.get("vida"), dict) \
        else None
    queda = None
    if anterior and anterior.get("pid") != pid and not anterior.get("saiu"):
        queda = {"pid": anterior.get("pid"), "desde": anterior.get("desde"),
                 "visto": anterior.get("visto"), "notada": _iso(agora)}
        visto = _ler_iso(anterior.get("visto"))
        if ligado_em is not None and visto is not None:
            try:
                if ligado_em > visto:
                    queda["windows_reiniciou"] = True
            except TypeError:                   # um com fuso, outro sem
                pass
        quedas = [q for q in (prefs.get("quedas") or [])
                  if isinstance(q, dict)]
        prefs["quedas"] = (quedas + [queda])[-QUEDAS_GUARDADAS:]
    prefs["vida"] = {"pid": pid, "desde": _iso(agora), "visto": _iso(agora),
                     "saiu": None}
    return queda


def marcar_visto(prefs: dict, agora: datetime | None = None) -> None:
    vida = prefs.get("vida")
    if isinstance(vida, dict):
        vida["visto"] = _iso(_agora(agora))


def marcar_saida(prefs: dict, como: str,
                 agora: datetime | None = None) -> None:
    vida = prefs.get("vida")
    if isinstance(vida, dict):
        vida["saiu"] = como
        vida["visto"] = _iso(_agora(agora))


def anotar_pedido_de_fechar(prefs: dict,
                            agora: datetime | None = None) -> int:
    atual = prefs.get("fechar_pedido")
    try:
        antes = int(atual.get("vezes") or 0) if isinstance(atual, dict) else 0
    except (TypeError, ValueError):
        antes = 0
    vezes = antes + 1
    prefs["fechar_pedido"] = {"vezes": vezes, "ultimo": _iso(_agora(agora))}
    return vezes


__all__ = ["MODOS", "PADRAO", "QUEDAS_GUARDADAS", "TAMANHOS", "VIVO_S",
           "abrir_vida", "anotar_pedido_de_fechar", "encaixar", "gravar",
           "inicio_do_windows", "ler", "marcar_saida", "marcar_visto",
           "tamanho"]
