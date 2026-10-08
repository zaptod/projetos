"""Abre cada tela do launcher e guarda capturas para a conferencia manual.

Uso: ``python -m neural_fights.ui.prova_launcher``. Requer uma sessao grafica
do Windows; as imagens vao para ``palco/_saida/launcher``.
"""
from __future__ import annotations

from pathlib import Path
import time

from PIL import ImageGrab

from neural_fights.ui.main import SistemaApp


def main() -> int:
    destino = Path(__file__).resolve().parents[2] / "palco" / "_saida" / "launcher"
    destino.mkdir(parents=True, exist_ok=True)
    app = SistemaApp()
    app.geometry("1200x760+20+20")
    app.deiconify()
    try:
        for nome in ("TelaArmas", "TelaPersonagens", "TelaLuta"):
            app.show_frame(nome)
            app.update()
            time.sleep(.3)
            x, y = app.winfo_rootx(), app.winfo_rooty()
            imagem = ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height()))
            imagem.save(destino / f"{nome}.png")
            print(destino / f"{nome}.png")
    except OSError as erro:
        # Ambientes sem desktop ainda validam a abertura; os testes de Tk
        # cobrem a previa sem depender de captura do monitor.
        print(f"captura indisponivel: {erro}")
    finally:
        app.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
