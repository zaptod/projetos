import io
import json

from PIL import Image, ImageDraw

from neural_fights.tools import atelie_animacoes as atelie


def folha():
    imagem = Image.new("RGBA", (50, 30))
    caneta = ImageDraw.Draw(imagem)
    for y in range(2):
        for x in range(4):
            caneta.rectangle((2 + x * 12, 2 + y * 14, 9 + x * 12, 9 + y * 14), fill="white")
    bruto = io.BytesIO(); imagem.save(bruto, "PNG")
    return bruto.getvalue()


def contrato(quadros):
    return {"quadros": quadros, "fps": 12, "loop": True, "ida_e_volta": False,
            "ancora": {"x": .5, "y": 1}, "escala": 1, "rotacao": 0,
            "espelho": False, "gatilho": "ocioso", "versao": 1}


def test_fatiar_4x2_por_vaos_e_grade():
    bruto = folha()
    assert len(atelie.fatiar_automatico(bruto)) == 8
    assert len(atelie.fatiar_grade(50, 30, 2, 4, margem=2, espaco=4)) == 8


def test_salvar_desfazer_e_folha_intacta(tmp_path, monkeypatch):
    monkeypatch.setattr(atelie, "ANIMACOES", tmp_path / "animacoes")
    bruto = folha(); quadros = atelie.fatiar_automatico(bruto)
    salvo = atelie.salvar("olhos", "medo", "chorar", bruto, contrato(quadros))
    assert atelie.ler("olhos", "medo", "chorar") == salvo
    assert (atelie.caminho("olhos", "medo", "chorar") / "folha.png").read_bytes() == bruto
    novo = contrato(quadros); novo["fps"] = 7
    atelie.salvar("olhos", "medo", "chorar", bruto, novo)
    assert atelie.desfazer("olhos", "medo", "chorar")["fps"] == 12


def test_ajustes_sobrevivem_catalogo_e_heranca(tmp_path, monkeypatch):
    monkeypatch.setattr(atelie, "AJUSTES", tmp_path / "ajustes.json")
    monkeypatch.setattr(atelie, "ANIMACOES", tmp_path / "animacoes")
    catalogo = {"pecas": [{"id": "tipo.x", "grupo": "Olhos", "rotulo": "tipo X", "heranca": [], "estados": [{"id": "medo", "animacoes": [{"id": "piscar", "gatilho": "ocioso", "loop": True}]}]}, {"id": "estilo.y", "grupo": "Olhos", "rotulo": "estilo Y", "heranca": ["tipo.x"], "estados": [{"id": "medo", "animacoes": [{"id": "piscar", "gatilho": "ocioso", "loop": True}]}]}]}
    arquivo = tmp_path / "catalogo.json"; arquivo.write_text(json.dumps(catalogo), encoding="utf-8")
    monkeypatch.setattr(atelie, "CATALOGO", arquivo)
    atelie.salvar("tipo.x", "medo", "piscar", folha(), contrato(atelie.fatiar_automatico(folha())))
    atelie.criar_animacao("estilo.y", "medo", {"id": "chorar", "rotulo": "chorar", "gatilho": "dano", "loop": False})
    arvore = atelie.arvore(); pecas = {p["id"]: p for g in arvore for p in g["pecas"]}
    assert any(a["id"] == "chorar" for a in pecas["estilo.y"]["estados"][0]["animacoes"])
    assert pecas["estilo.y"]["estados"][0]["animacoes"][0]["usa_a_de"] == "tipo.x"
    arquivo.write_text(json.dumps(catalogo), encoding="utf-8")
    assert any(a["id"] == "chorar" for g in atelie.arvore() for p in g["pecas"] for e in p["estados"] for a in e["animacoes"])


def test_folha_real_com_veu_e_ultima_linha_incompleta():
    """08/10/2026: a folha do Adrian (6x5, 26 desenhos) tem um veu de alfa
    baixo que sobra da remocao de fundo; o corte antigo (alfa > 0) devolvia
    UM quadro do tamanho da folha. Celulas iguais, sem as vazias do fim."""
    folha = Image.new("RGBA", (600, 250), (0, 0, 0, 5))          # veu quase invisivel
    caneta = ImageDraw.Draw(folha)
    for i in range(26):
        lin, col = divmod(i, 6)
        caneta.ellipse((col * 100 + 20, lin * 50 + 10, col * 100 + 80, lin * 50 + 40), fill=(90, 200, 40, 255))
    quadros = atelie.fatiar_automatico(folha)
    assert len(quadros) == 26
    assert {(q["w"], q["h"]) for q in quadros} == {(100, 50)}
    assert quadros[0] == {"x": 0, "y": 0, "w": 100, "h": 50}
    assert quadros[-1] == {"x": 100, "y": 200, "w": 100, "h": 50}


def test_esconder_tem_volta(tmp_path, monkeypatch):
    monkeypatch.setattr(atelie, "AJUSTES", tmp_path / "ajustes.json")
    atelie.esconder_animacao("peca.x", "base", "ociosa")
    assert atelie.ajustes()["escondidas"] == ["peca.x/base/ociosa"]
    atelie.mostrar_animacao("peca.x", "base", "ociosa")
    assert atelie.ajustes()["escondidas"] == []
