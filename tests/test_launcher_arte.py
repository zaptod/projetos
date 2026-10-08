"""Contrato da previa do launcher com a biblioteca do Atelie."""
import io
import json

from PIL import Image
import pytest

from neural_fights.tools import atelie_animacoes as atelie
from neural_fights.ui import arte_atelie


def _catalogo():
    animacao = {"id": "ociosa", "gatilho": "ocioso", "tamanho_padrao": "1,0 do corpo"}
    estado = {"id": "parada", "rotulo": "Parada", "animacoes": [animacao]}
    return {"pecas": [
        {"id": "classe.teste", "grupo": "lutador", "heranca": [], "estados": [estado]},
        {"id": "lutador.corpo", "grupo": "lutador", "heranca": ["lutador.generico"], "estados": [estado]},
        {"id": "lutador.generico", "grupo": "lutador", "heranca": [], "estados": [estado]},
        {"id": "arma.estilo.teste", "grupo": "arma", "heranca": ["arma.tipo.teste", "arma.generica"], "estados": [estado]},
        {"id": "arma.tipo.teste", "grupo": "arma", "heranca": ["arma.generica"], "estados": [estado]},
        {"id": "arma.generica", "grupo": "arma", "heranca": [], "estados": [estado]},
    ]}


def _folha_4x2():
    imagem = Image.new("RGBA", (40, 20), "#ff00ff")
    bruto = io.BytesIO(); imagem.save(bruto, "PNG")
    return bruto.getvalue()


def _contrato():
    return {"quadros": [{"x": x * 10, "y": y * 10, "w": 10, "h": 10}
                         for y in range(2) for x in range(4)], "fps": 12,
            "loop": True, "ancora": {"x": .5, "y": .5}, "escala": 1}


def test_resolve_heranca_e_recorta_folha_no_tamanho_do_corpo(tmp_path, monkeypatch):
    catalogo = _catalogo(); arquivo = tmp_path / "catalogo.json"
    arquivo.write_text(json.dumps(catalogo), encoding="utf-8")
    monkeypatch.setattr(atelie, "CATALOGO", arquivo)
    monkeypatch.setattr(atelie, "ANIMACOES", tmp_path / "animacoes")
    atelie.salvar("lutador.corpo", "parada", "ociosa", _folha_4x2(), _contrato())
    atelie.salvar("arma.tipo.teste", "parada", "ociosa", _folha_4x2(), _contrato())

    corpo = arte_atelie.carregar_quadros("classe.teste", corpo=80)
    arma = arte_atelie.carregar_quadros("arma.estilo.teste", corpo=80)

    assert corpo.fonte == "lutador.corpo"
    assert arma.fonte == "arma.tipo.teste"
    assert len(corpo.quadros) == 8
    assert {quadro.size for quadro in corpo.quadros} == {(80, 80)}


def test_marcador_quando_heranca_nao_tem_folha(tmp_path, monkeypatch):
    arquivo = tmp_path / "catalogo.json"
    arquivo.write_text(json.dumps(_catalogo()), encoding="utf-8")
    monkeypatch.setattr(atelie, "CATALOGO", arquivo)
    monkeypatch.setattr(atelie, "ANIMACOES", tmp_path / "animacoes")

    arte = arte_atelie.carregar_quadros("arma.estilo.teste")

    assert arte.fonte is None
    assert arte.quadros == []
    assert arte.marcador == "arma"


def test_peca_sem_ocioso_usa_a_primeira_animacao(tmp_path, monkeypatch):
    catalogo = _catalogo()
    peca = next(p for p in catalogo["pecas"] if p["id"] == "arma.tipo.teste")
    peca["estados"][0]["animacoes"][0].update({"id": "orbitar", "gatilho": "orbital"})
    arquivo = tmp_path / "catalogo.json"
    arquivo.write_text(json.dumps(catalogo), encoding="utf-8")
    monkeypatch.setattr(atelie, "CATALOGO", arquivo)
    monkeypatch.setattr(atelie, "ANIMACOES", tmp_path / "animacoes")
    atelie.salvar("arma.tipo.teste", "parada", "orbitar", _folha_4x2(), _contrato())

    arte = arte_atelie.carregar_quadros("arma.tipo.teste")

    assert arte.fonte == "arma.tipo.teste"
    assert len(arte.quadros) == 8


def test_heranca_aceita_primeira_animacao_com_nome_diferente(tmp_path, monkeypatch):
    catalogo = _catalogo()
    classe = next(p for p in catalogo["pecas"] if p["id"] == "classe.teste")
    classe["estados"] = [{"id": "base", "animacoes": [{"id": "ociosa", "gatilho": "ocioso"}]}]
    corpo = next(p for p in catalogo["pecas"] if p["id"] == "lutador.corpo")
    corpo["estados"] = [{"id": "parado", "animacoes": [{"id": "parado", "gatilho": "ocioso"}]}]
    arquivo = tmp_path / "catalogo.json"
    arquivo.write_text(json.dumps(catalogo), encoding="utf-8")
    monkeypatch.setattr(atelie, "CATALOGO", arquivo)
    monkeypatch.setattr(atelie, "ANIMACOES", tmp_path / "animacoes")
    atelie.salvar("lutador.corpo", "parado", "parado", _folha_4x2(), _contrato())

    arte = arte_atelie.carregar_quadros("classe.teste")

    assert arte.fonte == "lutador.corpo"
    assert len(arte.quadros) == 8


def test_forja_desenha_arte_apos_canvas_receber_tamanho(tmp_path, monkeypatch):
    tk = __import__("tkinter")
    try:
        raiz = tk.Tk()
        raiz.geometry("400x300+0+0")
    except tk.TclError as erro:
        pytest.skip(f"Tk indisponivel: {erro}")
    from neural_fights.ui.view_armas import TelaArmas
    try:
        arquivo = tmp_path / "catalogo.json"
        arquivo.write_text(json.dumps(_catalogo()), encoding="utf-8")
        monkeypatch.setattr(atelie, "CATALOGO", arquivo)
        monkeypatch.setattr(atelie, "ANIMACOES", tmp_path / "animacoes")
        atelie.salvar("arma.tipo.teste", "parada", "ociosa", _folha_4x2(), _contrato())
        tela = TelaArmas.__new__(TelaArmas)
        tela.canvas_preview = tk.Canvas(raiz, width=300, height=180)
        tela.canvas_preview.pack()
        tela.lbl_arte = tk.Label(raiz)
        tela.dados_arma = {"tipo": "Teste", "estilo": "", "geometria": {"comp_lamina": 70}}
        raiz.update()
        tela.atualizar_preview()
        assert tela.canvas_preview.find_withtag("arte")
        assert "Armas › Teste" in tela.lbl_arte.cget("text")
    finally:
        raiz.destroy()


def test_preview_de_lutador_pede_a_arte_da_arma(monkeypatch):
    from neural_fights.ui.theme import desenhar_lutador

    class Canvas:
        def cget(self, _nome): return "200"
        def winfo_width(self): return 200
        def winfo_height(self): return 200
        def delete(self, *_args): pass
        def create_oval(self, *_args, **_kwargs): pass
        def create_line(self, *_args, **_kwargs): pass

    pedidos = []
    marcador = arte_atelie.QuadrosArte("", None, {}, [], "arma")
    monkeypatch.setattr(arte_atelie, "carregar_quadros",
                        lambda ident, **_kwargs: pedidos.append(ident) or marcador)
    desenhar_lutador(Canvas(), type("P", (), {"classe": "Teste"})(),
                     type("A", (), {"tipo": "Teste", "estilo": ""})())

    assert "arma.tipo.teste" in pedidos
