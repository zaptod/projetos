"""Regressoes visuais e de integracao do launcher."""

from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

import pytest

from neural_fights.ui import view_luta
from neural_fights.ui.theme import _renderizar_preview_lutador, desenhar_lutador


class CanvasGravador:
    """Duble do Canvas suficiente para conferir as pecas do preview."""

    def __init__(self):
        self.chamadas = []

    def cget(self, nome):
        return "200" if nome in {"width", "height"} else ""

    def winfo_width(self):
        return 200

    def winfo_height(self):
        return 200

    def delete(self, *args):
        self.chamadas.append(("delete", args, {}))

    def create_oval(self, *args, **kwargs):
        self.chamadas.append(("oval", args, kwargs))

    def create_line(self, *args, **kwargs):
        self.chamadas.append(("line", args, kwargs))


def test_preview_dupla_desenha_duas_laminas():
    canvas = CanvasGravador()
    personagem = SimpleNamespace(cor_r=200, cor_g=50, cor_b=50, tamanho=1.7)
    arma = SimpleNamespace(tipo="Dupla", r=80, g=160, b=255, comp_lamina=70)

    desenhar_lutador(canvas, personagem, arma)

    laminas = [chamada for chamada in canvas.chamadas if chamada[2].get("tags") == "lamina"]
    assert len(laminas) == 4  # contorno e cor para cada uma das duas laminas


def test_preview_rasteriza_os_oito_tipos_de_arma_em_quatro_vezes():
    personagem = SimpleNamespace(classe="Piromante (Fogo)", tamanho=1.8)
    imagens = []
    for tipo in ("Reta", "Dupla", "Corrente", "Arco", "Arremesso", "Orbital", "Mágica", "Transformável"):
        arma = SimpleNamespace(tipo=tipo, r=80, g=160, b=255, comp_lamina=70)
        imagem = _renderizar_preview_lutador(personagem, arma, "#ff6600", 42)
        imagens.append(imagem.tobytes())
        assert imagem.size == (336, 336)
        assert imagem.getbbox() is not None

    assert len(set(imagens)) == 8


def test_exportar_palco_selecao_chama_manual_e_render(monkeypatch, tmp_path):
    chamadas = []
    palco = ModuleType("random_builds.builds.palco")
    palco.config = SimpleNamespace(SAIDAS=tmp_path)
    palco.godot = SimpleNamespace(
        abrir_previa=lambda caminho: chamadas.append(("previa", caminho)),
        abrir_arquivo=lambda caminho: chamadas.append(("arquivo", caminho)),
    )
    palco.render = SimpleNamespace(
        renderizar=lambda entrada, saida: chamadas.append(("render", entrada, saida)),
    )
    monkeypatch.setitem(sys.modules, "random_builds.builds.palco", palco)
    manual = SimpleNamespace(main=lambda argumentos: chamadas.append(("manual", argumentos)) or 0)
    import neural_fights.simulation as simulation
    monkeypatch.setattr(simulation, "manual", manual, raising=False)

    saida = view_luta.exportar_palco_selecao("P1", "P2", "Arena", "mp4")

    assert saida == Path(tmp_path, "launcher", "P1_vs_P2.mp4")
    argumentos = next(item[1] for item in chamadas if item[0] == "manual")
    assert argumentos[:5] == ["--exportar-palco", "--p1", "P1", "--p2", "P2"]
    assert "--cenario" in argumentos
    assert any(item[0] == "render" for item in chamadas)
    assert any(item[0] == "arquivo" for item in chamadas)


def test_sistema_app_constroi_telas_e_navega_sem_janela(monkeypatch, tmp_path):
    tk = pytest.importorskip("tkinter")
    import neural_fights.ui.view_sons as view_sons
    from neural_fights.ui.main import SistemaApp

    monkeypatch.setattr(view_sons, "get_runtime_sound_dir", lambda: tmp_path / "sons")
    monkeypatch.setattr(view_sons, "get_runtime_config_path", lambda: tmp_path / "sons.json")
    try:
        app = SistemaApp()
    except tk.TclError as erro:
        pytest.skip(f"Tk indisponivel: {erro}")
    app.withdraw()
    try:
        for nome in app.frames:
            app.show_frame(nome)
            app.update_idletasks()
    finally:
        app.destroy()


def _descendentes(widget):
    for filho in widget.winfo_children():
        yield filho
        yield from _descendentes(filho)


@pytest.mark.parametrize("largura,altura", [(1366, 728), (1000, 750)])
def test_textos_e_acoes_cabem_na_area_util(monkeypatch, tmp_path, largura, altura):
    """Evita regressao de texto e rodape fora da area de trabalho."""
    tk = pytest.importorskip("tkinter")
    import neural_fights.ui.view_sons as view_sons
    from neural_fights.ui.main import SistemaApp

    monkeypatch.setattr(view_sons, "get_runtime_sound_dir", lambda: tmp_path / "sons")
    monkeypatch.setattr(view_sons, "get_runtime_config_path", lambda: tmp_path / "sons.json")
    try:
        app = SistemaApp()
    except tk.TclError as erro:
        pytest.skip(f"Tk indisponivel: {erro}")
    try:
        app.geometry(f"{largura}x{altura}+0+0")
        app.deiconify()
        app.update()
        for nome, tela in app.frames.items():
            app.show_frame(nome)
            app.update_idletasks()
            for widget in _descendentes(tela):
                if isinstance(widget, (tk.Label, tk.Button)) and widget.winfo_ismapped():
                    pai = widget.nametowidget(widget.winfo_parent())
                    assert widget.winfo_reqwidth() <= pai.winfo_width(), widget.cget("text")
        luta = app.frames["TelaLuta"]
        personagens = app.frames["TelaPersonagens"]
        for acao in (luta.btn_iniciar, luta.btn_palco, luta.btn_mp4,
                     personagens.btn_anterior, personagens.btn_proximo):
            assert acao.winfo_rooty() + acao.winfo_height() <= app.winfo_rooty() + app.winfo_height()
    finally:
        app.destroy()
