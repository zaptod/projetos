"""Vigia das RODADAS LONGAS penduradas (SCR-7 da auditoria profunda, 14/10/2026).

A rodada de criacao de historias das 07:02 de 12/10 (pid 4332) parou no
Gemini as 13:09:33, nao escreveu mais uma linha e segurou a trava
`historias__auto` por 31 h, ate o PC cair: os 12 disparos seguintes do dia
sairam "ja tem uma rodada em andamento" e nada matou o Python. As 49 tarefas
tinham `ExecutionTimeLimit` de 72 h, e mesmo no limite o Agendador mata so o
`wscript` (medido em 06/10).

Cada rodada longa (`main.py auto` das historias, `main.py noite` dos builds)
deixa uma ficha em `<runtime>/rodadas/<pid>.json` enquanto segura a trava, e
cada linha do diario dela renova o pulso (`builds.rodada_viva`). Este vigia,
a cada `INTERVALO_S`, olha as fichas:

- pid morto (ou reaproveitado por outro processo): a ficha e lixo e sai;
- pulso parado ha `LIMITE_SEM_PULSO_MIN` ou mais com o MESMO processo vivo:
  mata a arvore dele (`taskkill /T /F`: o Python e o Chrome que ele abriu),
  confere que morreu, apaga a ficha e avisa no Telegram com o pid, a faixa e
  a hora do ultimo pulso. A trava de arquivo solta com o processo; o proximo
  disparo do Agendador recomeca.

Rodada lenta que fala nao morre, por mais longa que seja. Caso ZERO: sem
ficha nenhuma, nada acontece e nada e avisado.
"""
from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime

INTERVALO_S = 60
# Segundos entre a epoca do FILETIME (1601) e a do Unix (1970).
_FILETIME_PARA_UNIX = 11644473600.0
# O processo nasce ANTES de pegar a trava; uma folga para relogio grosso.
_FOLGA_DE_IDENTIDADE_S = 5.0


def _limite_min() -> float:
    from builds.rodada_viva import LIMITE_SEM_PULSO_MIN
    return float(LIMITE_SEM_PULSO_MIN)


def criado_em(pid) -> float | None:
    """Quando o processo nasceu, em epoch Unix; None = morto ou sem acesso."""
    try:
        from remoto.orquestrador import hora_de_criacao
        bruto = hora_de_criacao(pid)
    except Exception:                                         # noqa: BLE001
        return None
    if bruto is None:
        return None
    return float(bruto) - (_FILETIME_PARA_UNIX if os.name == "nt" else 0.0)


def matar_arvore(pid: int) -> None:
    subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                   capture_output=True, check=False,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def situacao(ficha: dict, agora: float, criado, limite_min: float) -> str:
    """'viva', 'pendurada', 'morta' ou 'ilegivel'. Pura (o `criado` e dublavel)."""
    if ficha.get("ilegivel"):
        return "ilegivel"
    try:
        pid = int(ficha["pid"])
        inicio = float(ficha["inicio"])
        pulso = float(ficha.get("pulso") or inicio)
    except (KeyError, TypeError, ValueError):
        return "ilegivel"
    nasceu = criado(pid)
    if nasceu is None or nasceu > inicio + _FOLGA_DE_IDENTIDADE_S:
        # sem processo, ou o pid ja e de OUTRO processo (nasceu depois da
        # ficha): a rodada dona dela morreu
        return "morta"
    if agora - pulso >= limite_min * 60.0:
        return "pendurada"
    return "viva"


class VigiaRodadas:
    def __init__(self, *, avisar=None, evento=None, log=print, relogio=time.time,
                 criado=criado_em, matar=matar_arvore, fichas=None, apagar=None,
                 limite_min=None, dormir=time.sleep):
        self.avisar = avisar or (lambda texto: False)
        self.evento = evento or (lambda tipo, texto: None)
        self.log = log
        self.relogio = relogio
        self.criado = criado
        self.matar = matar
        self._fichas = fichas
        self._apagar = apagar
        self._limite = limite_min
        self.dormir = dormir
        self.ultimo = None
        self.falhou = set()           # (pid, inicio) que nao morreu: avisado 1x

    def fichas(self):
        if self._fichas is not None:
            return self._fichas()
        from builds import rodada_viva
        return rodada_viva.fichas()

    def apagar(self, ficha):
        if self._apagar is not None:
            return self._apagar(ficha)
        try:
            os.remove(ficha["_arquivo"])
        except (KeyError, OSError):
            pass

    def passo(self, *, forcar=False) -> list[dict]:
        """Uma olhada. Devolve o que fez (para o retrato e os testes)."""
        agora = self.relogio()
        if not forcar and self.ultimo is not None and agora - self.ultimo < INTERVALO_S:
            return []
        self.ultimo = agora
        limite = float(self._limite if self._limite is not None else _limite_min())
        feito = []
        for ficha in self.fichas():
            estado = situacao(ficha, agora, self.criado, limite)
            if estado == "morta":
                self.apagar(ficha)
                feito.append({"pid": ficha.get("pid"), "acao": "faxina"})
            elif estado == "pendurada":
                feito.append(self._encerrar(ficha, agora))
        return feito

    def _encerrar(self, ficha: dict, agora: float) -> dict:
        pid, inicio = int(ficha["pid"]), float(ficha["inicio"])
        pulso = float(ficha.get("pulso") or inicio)
        calada_min = int((agora - pulso) // 60)
        rotulo = str(ficha.get("rotulo") or ficha.get("trava") or "rodada")
        trava = str(ficha.get("trava") or "?")
        quando = datetime.fromtimestamp(pulso).strftime("%d/%m %H:%M")
        try:
            self.matar(pid)
        except Exception as exc:                              # noqa: BLE001
            self.log(f"[vigia-rodadas] taskkill {pid} falhou: {exc}")
        # confere que morreu (ate ~10 s) antes de dizer que a trava soltou
        morta = False
        for _ in range(5):
            if situacao(ficha, agora, self.criado, 0.0) == "morta":
                morta = True
                break
            self.dormir(2)
        if morta:
            self.apagar(ficha)
            texto = (f"Encerrei a rodada de {rotulo} (pid {pid}): calada ha "
                     f"{calada_min} min, ultimo sinal {quando}. A trava {trava} "
                     f"ficou livre; o proximo disparo recomeca.")
            self.evento("rodada_encerrada", texto)
            self.avisar(texto)
            return {"pid": pid, "acao": "encerrada", "calada_min": calada_min}
        chave = (pid, inicio)
        if chave not in self.falhou:
            self.falhou.add(chave)
            texto = (f"A rodada de {rotulo} (pid {pid}) esta calada ha "
                     f"{calada_min} min e NAO consegui encerra-la; a trava "
                     f"{trava} continua presa. Feche o processo {pid} na mao.")
            self.evento("rodada_presa", texto)
            self.avisar(texto)
        return {"pid": pid, "acao": "nao_morreu", "calada_min": calada_min}
