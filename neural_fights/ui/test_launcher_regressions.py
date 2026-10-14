"""Regressoes visuais e de integracao do launcher."""

from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

import pytest

from neural_fights.ui import view_luta
from neural_fights.ui.theme import desenhar_lutador


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


def test_preview_sem_arte_usa_marcadores_neutros():
    canvas = CanvasGravador()
    personagem = SimpleNamespace(cor_r=200, cor_g=50, cor_b=50, tamanho=1.7)
    arma = SimpleNamespace(tipo="Dupla", r=80, g=160, b=255, comp_lamina=70)

    desenhar_lutador(canvas, personagem, arma)

    assert any(chamada[0] == "oval" and chamada[2].get("tags") == "arte"
               for chamada in canvas.chamadas)
    assert any(chamada[0] == "line" and chamada[2].get("tags") == "arte"
               for chamada in canvas.chamadas)


def test_preview_sem_arte_nao_desenha_rosto_nem_tracejado():
    canvas = CanvasGravador()
    personagem = SimpleNamespace(cor_r=200, cor_g=50, cor_b=50, tamanho=1.7)

    desenhar_lutador(canvas, personagem)

    corpo = next(chamada for chamada in canvas.chamadas if chamada[2].get("tags") == "arte")
    assert corpo[2]["fill"] == "#8b8d96"
    assert not any(chamada[2].get("dash") for chamada in canvas.chamadas)


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
    # sem --seed a exportacao quebrava em int(None) e o Godot nunca abria (02/10)
    assert "--seed" in argumentos and int(argumentos[argumentos.index("--seed") + 1]) > 0
    assert any(item[0] == "render" for item in chamadas)
    assert any(item[0] == "arquivo" for item in chamadas)


def test_arena_do_launcher_nao_oferece_simulador_pygame():
    import inspect

    fonte = inspect.getsource(view_luta)

    assert "INICIAR " + "BATALHA" not in fonte
    assert "simulacao." + "S" + "imulador" not in fonte


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
        for acao in (luta.btn_palco, luta.btn_mp4,
                     personagens.btn_anterior, personagens.btn_proximo):
            assert acao.winfo_rooty() + acao.winfo_height() <= app.winfo_rooty() + app.winfo_height()
    finally:
        app.destroy()


# ---------------------------------------------------------------------------
# Auditoria profunda de 11/10/2026, metade B do motor (launcher)
# ---------------------------------------------------------------------------
def _app(monkeypatch, tmp_path, visivel=False):
    tk = pytest.importorskip("tkinter")
    import neural_fights.ui.view_sons as view_sons
    from neural_fights.ui.main import SistemaApp

    monkeypatch.setattr(view_sons, "get_runtime_sound_dir", lambda: tmp_path / "sons")
    monkeypatch.setattr(view_sons, "get_runtime_config_path", lambda: tmp_path / "sons.json")
    try:
        app = SistemaApp()
    except tk.TclError as erro:
        pytest.skip(f"Tk indisponivel: {erro}")
    if not visivel:
        app.withdraw()
    return app


def test_passo3_da_forja_nao_arredonda_dano(monkeypatch, tmp_path):
    """MOT-107: so visitar o passo 3 virava 12,5 em 13,0."""
    app = _app(monkeypatch, tmp_path, visivel=True)
    try:
        app.show_frame("TelaArmas")
        tela = app.frames["TelaArmas"]
        tela.dados_arma["dano"] = 12.5
        tela.mostrar_passo(3)
        for _ in range(5):
            app.update()
        assert tela.dados_arma["dano"] == 12.5
    finally:
        app.destroy()


def test_roda_do_mouse_rola_o_wizard(monkeypatch, tmp_path):
    """MOT-113: o bind_all da TelaSons roubava a roda do wizard."""
    app = _app(monkeypatch, tmp_path, visivel=True)
    try:
        app.geometry("1280x700+0+0")
        app.show_frame("TelaPersonagens")
        tela = app.frames["TelaPersonagens"]
        tela.mostrar_passo(2)
        for _ in range(3):
            app.update()
        canvas = tela.canvas_wizard
        sons = app.frames["TelaSons"].canvas_sons
        antes_sons = sons.yview()[0]
        x = canvas.winfo_rootx() + canvas.winfo_width() // 2
        y = canvas.winfo_rooty() + canvas.winfo_height() // 2
        antes = canvas.yview()[0]
        alvo = app.winfo_containing(x, y)
        assert alvo is not None
        alvo.event_generate("<MouseWheel>", delta=-120, rootx=x, rooty=y, x=1, y=1)
        app.update()
        assert canvas.yview()[0] > antes
        assert sons.yview()[0] == antes_sons
    finally:
        app.destroy()


def test_corpo_e_arma_coexistem():
    """MOT-114: a PhotoImage da arma soltava a do corpo."""
    tk = pytest.importorskip("tkinter")
    import gc

    from PIL import Image

    from neural_fights.ui import arte_atelie

    try:
        raiz = tk.Tk()
    except tk.TclError as erro:
        pytest.skip(f"Tk indisponivel: {erro}")
    raiz.withdraw()
    try:
        canvas = tk.Canvas(raiz, width=100, height=100)
        corpo = SimpleNamespace(quadros=[Image.new("RGBA", (10, 10), "red")], marcador="corpo")
        arma = SimpleNamespace(quadros=[Image.new("RGBA", (10, 10), "blue")], marcador="arma")
        arte_atelie.desenhar(canvas, corpo, 50, 50, limpar=False)
        arte_atelie.desenhar(canvas, arma, 60, 50, limpar=False)
        gc.collect()
        nomes = set(str(n) for n in raiz.tk.call("image", "names"))
        imagens = [canvas.itemcget(item, "image") for item in canvas.find_withtag("arte")]
        assert len(imagens) == 2
        assert all(nome in nomes for nome in imagens)
    finally:
        raiz.destroy()


def test_janela_cabe_na_area_util(monkeypatch, tmp_path):
    """MOT-116: cliente de 720 + barra de titulo passava da area util."""
    from neural_fights.ui.main import area_util_tela

    app = _app(monkeypatch, tmp_path, visivel=True)
    try:
        app.update()
        _esq, topo, _larg, altura = area_util_tela(app)
        assert app.winfo_rooty() + app.winfo_height() <= topo + altura
    finally:
        app.destroy()


def test_fechar_durante_render_nao_quebra_thread(monkeypatch, tmp_path):
    """MOT-117: a thread chamava self.after com a janela destruida."""
    import threading
    import time

    erros = []
    monkeypatch.setattr(threading, "excepthook", lambda args: erros.append(args))
    monkeypatch.setattr(view_luta, "exportar_palco_selecao",
                        lambda *a, **k: time.sleep(0.5) or tmp_path / "x.mp4")
    app = _app(monkeypatch, tmp_path)
    tela = app.frames["TelaLuta"]
    tela.personagem_p1 = SimpleNamespace(nome="A")
    tela.personagem_p2 = SimpleNamespace(nome="B")
    tela._palco_em_andamento = False
    tela._iniciar_palco("mp4")
    app._fechar()
    tela._thread_palco.join(3)
    assert not tela._thread_palco.is_alive()
    assert erros == []


def test_godot_registrado_e_encerrado():
    """MOT-117: encerrar_todos mata o Godot que sobrou."""
    from random_builds.builds.palco import godot

    class Processo:
        def __init__(self):
            self.morto = False

        def poll(self):
            return 0 if self.morto else None

        def kill(self):
            self.morto = True

    vivo = Processo()
    godot._registrar(vivo)
    assert godot.encerrar_todos() == 1
    assert vivo.morto


def test_resumo_do_wizard_bate_com_o_modelo(monkeypatch, tmp_path):
    """MOT-118: as formulas locais nao eram as do motor."""
    from neural_fights.models import Personagem

    app = _app(monkeypatch, tmp_path)
    try:
        tela = app.frames["TelaPersonagens"]
        tela.dados_char.update({"nome": "Teste", "tamanho": 1.70, "forca": 5,
                                "classe": "Guerreiro (Força Bruta)", "arma": ""})
        tela.criar_resumo_stats()
        textos = [w.cget("text") for w in _descendentes(tela.frame_stats) if "text" in w.keys()]
        modelo = Personagem("Teste", 1.70, 5, tela.dados_char["mana"], "", 0,
                            classe="Guerreiro (Força Bruta)")
        assert any(f"{modelo.velocidade:.1f}" in t for t in textos), textos
        assert any(f"{modelo.resistencia:.1f}" == t for t in textos), textos
    finally:
        app.destroy()


def test_passo6_recarrega_armas(monkeypatch, tmp_path):
    """MOT-119: voltar da Forja reconstruia o passo 5, nao o 6."""
    app = _app(monkeypatch, tmp_path)
    try:
        tela = app.frames["TelaPersonagens"]
        tela.mostrar_passo(6)
        nova = SimpleNamespace(nome="Arma Nova da Forja", r=10, g=20, b=30, tipo="Reta",
                               dano=5.0, raridade="Comum", peso=2.0)
        app.lista_armas = list(app.lista_armas) + [nova]
        tela.atualizar_dados()
        textos = [w.cget("text") for w in _descendentes(tela.frame_armas_inner) if "text" in w.keys()]
        assert "Arma Nova da Forja" in textos
    finally:
        app.destroy()


def test_sugestao_usa_personagem(monkeypatch, tmp_path):
    """MOT-120: lia controller.lista_chars (inexistente) e nunca via personagem."""
    import neural_fights.ui.view_armas as view_armas

    vistos = []
    monkeypatch.setattr(view_armas, "sugerir_tamanho_arma",
                        lambda personagem, tipo: vistos.append(personagem) or {})
    monkeypatch.setattr(view_armas.messagebox, "showinfo", lambda *a, **k: None)
    app = _app(monkeypatch, tmp_path)
    try:
        app.frames["TelaPersonagens"].dados_char.update({"nome": "Em Edicao", "tamanho": 1.9})
        tela = app.frames["TelaArmas"]
        tela.sliders_geometria = {}
        tela.aplicar_sugestao_geometria()
        assert vistos and vistos[0] is not None
        assert vistos[0].tamanho == 1.9
    finally:
        app.destroy()


def test_sugerir_tamanho_usa_altura_em_metros():
    from neural_fights.models import sugerir_tamanho_arma

    padrao = sugerir_tamanho_arma(None, "Reta")
    medio = sugerir_tamanho_arma(SimpleNamespace(tamanho=1.70), "Reta")
    alto = sugerir_tamanho_arma(SimpleNamespace(tamanho=2.10), "Reta")
    assert medio == padrao
    assert alto["comp_lamina"] > medio["comp_lamina"]
