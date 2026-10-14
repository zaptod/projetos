"""Aviso "o PC religou" (SCR-1; decisao `geral/pc-religado`, 14/10/2026).

Depois de uma queda de energia, de um Windows Update ou de uma tela azul,
nada do projeto sobe ate alguem entrar no Windows: as 61 tarefas sao "somente
com o usuario conectado" (o Chrome precisa da sessao grafica) e o bot, que
avisaria, e uma das coisas que nao sobem. Em 13/10 o PC religou as 22:43 e
nao ficou rastro de quanto tempo ficou parado.

A decisao foi o MINIMO: so um aviso quando ele entrar. Nao guarda senha e nao
liga logon automatico. O coordenador sobe no logon (`LogonTrigger` da tarefa
`NeuralFights_coordenador`); na primeira subida depois de um boot novo ele
manda, uma vez:

    O PC religou as 22:43 (13/10); a sessao abriu as 23:31 (48 min depois).
    Ultimo sinal do coordenador antes disso: 13/10 22:17 (1 h 14 min sem nada
    rodando).

O "ultimo sinal" e o `pulso_em` que o coordenador anterior deixou no
`estado.json` (gravado a cada 5 s). Uma vez por boot: a marca
`boot_<epoch>.marca` e criada com O_EXCL antes do aviso, entao duas subidas
juntas (o gatilho de logon e o de repeticao) nao avisam duas vezes. A
primeira subida depois de instalar este codigo so grava a marca (sem marca
anterior nao da para afirmar que houve boot novo desde a ultima vez).
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

# Dois boots com menos que isto de diferenca sao o mesmo (o calculo pelo
# tempo ligado varia alguns segundos entre leituras).
MESMO_BOOT_S = 120.0


def boot_em() -> float | None:
    """Quando o Windows ligou, em epoch (agora - tempo ligado)."""
    if os.name != "nt":                                     # pragma: no cover
        return None
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.GetTickCount64.restype = ctypes.c_ulonglong
        return time.time() - k.GetTickCount64() / 1000.0
    except Exception:                                         # noqa: BLE001
        return None


def _marcas(pasta: Path) -> list[float]:
    saida = []
    for arquivo in pasta.glob("boot_*.marca"):
        try:
            saida.append(float(arquivo.stem.split("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    return saida


def _duracao(segundos: float) -> str:
    minutos = max(0, int(segundos // 60))
    if minutos < 60:
        return f"{minutos} min"
    return f"{minutos // 60} h {minutos % 60:02d} min"


def verificar(pasta: Path, *, anterior: dict | None, agora: float | None = None,
              boot=...) -> str | None:
    """O texto do aviso se ESTA e a primeira subida depois de um boot novo.

    `boot` omitido = o do Windows (`boot_em`); `None` = nao sei (nao avisa).
    """
    agora = time.time() if agora is None else float(agora)
    boot = boot_em() if boot is ... else boot
    if boot is None:
        return None
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    conhecidas = _marcas(pasta)
    if any(abs(b - boot) < MESMO_BOOT_S for b in conhecidas):
        return None
    try:
        fd = os.open(pasta / f"boot_{int(boot)}.marca",
                     os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except OSError:
        return None                    # outra subida ja e dona deste boot
    for velho in sorted(conhecidas)[:-3]:     # guarda so as ultimas
        try:
            (pasta / f"boot_{int(velho)}.marca").unlink()
        except OSError:
            pass
    if not conhecidas:
        return None                    # primeira vez: nada a comparar
    ligou = datetime.fromtimestamp(boot)
    texto = (f"O PC religou as {ligou:%H:%M} ({ligou:%d/%m}); a sessao abriu "
             f"as {datetime.fromtimestamp(agora):%H:%M} "
             f"({_duracao(agora - boot)} depois).")
    pulso = (anterior or {}).get("pulso_em")
    try:
        ultimo = datetime.fromisoformat(str(pulso)).timestamp() if pulso else None
    except ValueError:
        ultimo = None
    if ultimo is not None and ultimo < boot:
        texto += (f" Ultimo sinal do coordenador antes disso: "
                  f"{datetime.fromtimestamp(ultimo):%d/%m %H:%M} "
                  f"({_duracao(agora - ultimo)} sem nada rodando).")
    return texto
