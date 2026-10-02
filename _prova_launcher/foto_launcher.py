"""Captura cada tela principal do launcher nos dois tamanhos de referencia.

Execute em uma sessao Windows com area de trabalho disponivel:
    python _prova_launcher/foto_launcher.py
"""

from pathlib import Path
import time

from PIL import ImageGrab

from neural_fights.ui.main import SistemaApp
import neural_fights.ui.view_sons as view_sons


TAMANHOS = ((1366, 768), (1000, 750))


def capturar():
    destino = Path(__file__).parent
    view_sons.get_runtime_sound_dir = lambda: destino / "sons_runtime"
    view_sons.get_runtime_config_path = lambda: destino / "sons_runtime.json"
    app = SistemaApp()
    app.update_idletasks()
    torneio = None
    try:
        from neural_fights.ui.view_torneio import TournamentWindow
        torneio = TournamentWindow(app)
        torneio.withdraw()
    except (ImportError, RuntimeError):
        pass
    try:
        for largura, altura in TAMANHOS:
            app.state("normal")
            app.geometry(f"{largura}x{altura}+0+0")
            for nome in app.frames:
                app.show_frame(nome)
                app.update()
                time.sleep(.2)
                x, y = app.winfo_rootx(), app.winfo_rooty()
                try:
                    imagem = ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height()))
                except OSError as erro:
                    raise SystemExit(f"Captura de tela indisponivel: {erro}") from erro
                imagem.save(destino / f"{nome}_{largura}x{altura}.png")
            if torneio is not None:
                torneio.geometry(f"{largura}x{altura}+0+0")
                torneio.deiconify()
                torneio.update()
                time.sleep(.2)
                x, y = torneio.winfo_rootx(), torneio.winfo_rooty()
                try:
                    imagem = ImageGrab.grab(
                        bbox=(x, y, x + torneio.winfo_width(), y + torneio.winfo_height())
                    )
                except OSError as erro:
                    raise SystemExit(f"Captura de tela indisponivel: {erro}") from erro
                imagem.save(destino / f"Torneio_{largura}x{altura}.png")
                torneio.withdraw()
    finally:
        if torneio is not None:
            torneio.destroy()
        app.destroy()


if __name__ == "__main__":
    capturar()
