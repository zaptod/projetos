"""04/10/2026: rodando de historias/ (como o `main.py auto`), o worker nao achava o
pacote `ias` e toda passada de imagens morria. O pytest roda da raiz e nao via."""
import subprocess
import sys
from pathlib import Path

HISTORIAS = Path(__file__).resolve().parents[1]


def test_worker_importa_ias_rodando_de_historias():
    feito = subprocess.run(
        [sys.executable, "-c", "from contos.imagens import worker; from ias import imagem, correio; "
                               "print(callable(worker._ordem_de_geradores))"],
        cwd=str(HISTORIAS), capture_output=True, text=True, timeout=120)
    assert feito.returncode == 0, feito.stderr[-800:]
    assert feito.stdout.strip().endswith("True")
