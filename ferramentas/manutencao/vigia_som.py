"""Re-renderiza duelos com som real em janelas noturnas, vigiando o filho."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
PY = sys.executable
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=RAIZ / "random_builds", help="raiz de random_builds")
    p.add_argument("--alvos", nargs="+", default=[f"duelo_{n:05d}" for n in range(17, 24)],
                   help="ids dos duelos a renderizar")
    p.add_argument("--janelas", nargs="+", default=["01:55", "02:55", "03:55", "04:55"],
                   help="horarios HH:MM para disparar cada rodada")
    p.add_argument("--temp", type=Path, default=Path(os.environ.get("LOCALAPPDATA", ".")) / "neural_fights/som",
                   help="pasta temporaria do render")
    p.add_argument("--log", type=Path, help="arquivo de log (padrao: outputs/_logs)")
    return p.parse_args()


def tem_sons(pasta: Path) -> bool:
    try:
        luta = json.loads((pasta / "fight.json").read_text(encoding="utf-8-sig")).get("luta") or {}
    except (OSError, ValueError):
        return False
    return isinstance(luta.get("sons"), list) and bool(luta["sons"])


def esperar_ate(hora: int, minuto: int) -> bool:
    alvo = datetime.now().replace(hour=hora, minute=minuto, second=30, microsecond=0)
    if alvo < datetime.now() - timedelta(minutes=20):
        return False
    while datetime.now() < alvo:
        time.sleep(min(20, max(.5, (alvo - datetime.now()).total_seconds())))
    return True


def parar(proc: subprocess.Popen, motivo: str) -> None:
    print(f"PARANDO ({motivo}) pid {proc.pid}", flush=True)
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True,
                   creationflags=NO_WINDOW)


def vigiar(proc: subprocess.Popen, log_render: Path) -> str:
    inicio = time.time()
    while proc.poll() is None:
        time.sleep(10)
        agora = datetime.now()
        motivo = ""
        if 27 <= agora.minute < 55:
            motivo = f"passou de :27 ({agora:%H:%M})"
        elif log_render.exists() and time.time() - log_render.stat().st_mtime > 12 * 60 and time.time() - inicio > 12 * 60:
            motivo = "log parado ha mais de 12 min"
        elif shutil.disk_usage("C:\\").free < 1500 * 1024 * 1024:
            motivo = "C: com menos de 1500 MB livres"
        if motivo:
            parar(proc, motivo)
            return motivo
    return ""


def rodada(repo: Path, alvos: list[str], temp: Path, log_render: Path) -> list[str]:
    sys.path.insert(0, str(repo))
    from builds import travas
    with travas.trava("builds__gerar", esperar=300.0) as minha:
        if not minha:
            print("trava builds__gerar ocupada; pulo esta janela")
            return alvos
        temp.mkdir(parents=True, exist_ok=True)
        ambiente = dict(os.environ, TEMP=str(temp), TMP=str(temp), PYTHONUTF8="1")
        inicio = time.time()
        comando = [PY, "-u", "-X", "utf8", "main.py", "som-da-luta", *alvos]
        log_render.parent.mkdir(parents=True, exist_ok=True)
        with log_render.open("a", encoding="utf-8") as fh:
            proc = subprocess.Popen(comando, cwd=repo, env=ambiente, stdin=subprocess.DEVNULL,
                                    stdout=fh, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
            motivo = vigiar(proc, log_render)
        faltam = [alvo for alvo in alvos if not (tem_sons(repo / "outputs" / alvo) and
                   all((repo / "outputs" / alvo / f"final_{perfil}.mp4").is_file() and
                       (repo / "outputs" / alvo / f"final_{perfil}.mp4").stat().st_mtime > inicio
                       for perfil in ("celular", "normal")))]
        print(f"render terminou: codigo {proc.returncode}; faltam {faltam}; {motivo}")
        return faltam


def principal() -> int:
    a = argumentos()
    log_render = a.log or a.repo / "outputs/_logs" / f"som_da_luta_{datetime.now():%Y%m%d}.txt"
    faltam = list(a.alvos)
    for janela in a.janelas:
        try:
            hora, minuto = map(int, janela.split(":"))
        except ValueError:
            raise SystemExit(f"janela invalida: {janela} (use HH:MM)")
        if esperar_ate(hora, minuto) and faltam:
            faltam = rodada(a.repo, faltam, a.temp, log_render)
    return 0 if not faltam else 2


if __name__ == "__main__":
    raise SystemExit(principal())
