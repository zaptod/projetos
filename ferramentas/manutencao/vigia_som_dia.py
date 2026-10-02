"""Re-renderiza duelos com som real de dia, respeitando a grade e trocando copias."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
PY = sys.executable
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ARQUIVOS = ["final_celular.mp4", "final_normal.mp4", "fight.json", "edit_plan.json"]
PASTAS = ["_segments_celular", "_segments_normal"]


def argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=RAIZ / "random_builds", help="raiz de random_builds")
    p.add_argument("--alvos", nargs="+", default=[f"duelo_{n:05d}" for n in range(17, 24)], help="duelos candidatos")
    p.add_argument("--temp", type=Path, default=Path(os.environ.get("LOCALAPPDATA", ".")) / "neural_fights/som_dia",
                   help="pasta de copias e temporarios")
    p.add_argument("--fim", default="20:00", help="hora limite HH:MM (padrao: 20:00)")
    return p.parse_args()


def horarios_grade(repo: Path) -> list[datetime]:
    sys.path.insert(0, str(repo))
    from builds import grade
    agora = datetime.now().replace(second=0, microsecond=0)
    return [(agora + timedelta(days=dia)).replace(hour=h, minute=grade.minuto(h))
            for dia in (-1, 0, 1) for h in grade.HORAS]


def proibido(posts: list[datetime], instante: datetime | None = None) -> bool:
    instante = instante or datetime.now()
    return 25 <= instante.minute < 55 or any(post - timedelta(minutes=12) <= instante < post + timedelta(minutes=18)
                                               for post in posts)


def esperar_livre(posts: list[datetime], fim: datetime, minutos: int = 7) -> bool:
    while datetime.now() < fim:
        agora = datetime.now()
        livre = not proibido(posts, agora) and not any(proibido(posts, agora + timedelta(minutes=i)) for i in range(minutos))
        if livre:
            return True
        time.sleep(20)
    return False


def trocar(origem: Path, nova: Path, backup: Path) -> None:
    """Troca arquivos e pastas publicaveis; em falha, restaura o que ja mudou."""
    backup.mkdir(parents=True, exist_ok=True)
    feitos: list[tuple[str, str]] = []
    try:
        for nome in ARQUIVOS:
            shutil.copy2(origem / nome, backup / nome)
            os.replace(nova / nome, origem / nome)
            feitos.append(("arquivo", nome))
        for nome in PASTAS:
            os.rename(origem / nome, backup / nome)
            feitos.append(("fora", nome))
            os.rename(nova / nome, origem / nome)
            feitos.append(("dentro", nome))
    except OSError:
        for tipo, nome in reversed(feitos):
            if tipo == "arquivo":
                shutil.copy2(backup / nome, origem / nome)
            elif tipo == "dentro":
                os.rename(origem / nome, nova / nome)
            else:
                os.rename(backup / nome, origem / nome)
        raise


def renderizar(repo: Path, alvo: str, copia: Path, temp: Path) -> int:
    destino = copia / alvo
    if destino.exists():
        shutil.rmtree(destino)
    temp.mkdir(parents=True, exist_ok=True)
    ambiente = dict(os.environ, TEMP=str(temp), TMP=str(temp), PYTHONUTF8="1")
    return subprocess.run([PY, "-u", "-X", "utf8", "main.py", "som-da-luta", alvo, "--destino", str(destino)],
                          cwd=repo, env=ambiente, creationflags=NO_WINDOW).returncode


def principal() -> int:
    a = argumentos()
    hora, minuto = map(int, a.fim.split(":"))
    fim = datetime.now().replace(hour=hora, minute=minuto, second=0, microsecond=0)
    posts = horarios_grade(a.repo)
    copia, antes = a.temp / "copia", a.temp / "antes"
    for alvo in a.alvos:
        if not esperar_livre(posts, fim):
            return 2
        if renderizar(a.repo, alvo, copia, a.temp / "temp"):
            return 2
        while proibido(posts):
            time.sleep(20)
        trocar(a.repo / "outputs" / alvo, copia / alvo, antes / f"{alvo}_{datetime.now():%H%M%S}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
