from __future__ import annotations

import json
import importlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from esteira_sprites import config, ficha, prompt
colher_mod = importlib.import_module("esteira_sprites.colher")
juiz = importlib.import_module("esteira_sprites.juiz")
limpar = importlib.import_module("esteira_sprites.limpar")
pedir = importlib.import_module("esteira_sprites.pedir")
portao = importlib.import_module("esteira_sprites.portao")


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    itens = [
        {"id": "fogo_teste", "nome_arquivo": "skills/fogo.png", "descricao": "projetil de fogo", "tipo": "peca", "prioridade": "P1", "ordem": 1, "bloqueio": "", "opcional": False},
        {"id": "trevas_teste", "nome_arquivo": "skills/trevas.png", "descricao": "orbe roxo", "tipo": "peca", "prioridade": "P1", "ordem": 2, "bloqueio": "", "opcional": False},
        {"id": "folha_teste", "nome_arquivo": "impacto.png", "descricao": "impacto", "tipo": "folha", "prioridade": "P1", "ordem": 3, "bloqueio": "", "opcional": False},
        {"id": "bloqueado", "nome_arquivo": "x.png", "descricao": "x", "tipo": "peca", "prioridade": "P1", "ordem": 4, "bloqueio": "aguarda", "opcional": False},
        {"id": "opcional", "nome_arquivo": "x.png", "descricao": "x", "tipo": "peca", "prioridade": "P1", "ordem": 5, "bloqueio": "", "opcional": True},
    ]
    inventario = tmp_path / "inventario.json"
    inventario.write_text(json.dumps({"itens": itens}), encoding="utf-8")
    monkeypatch.setattr(config, "RAIZ", tmp_path / "esteira")
    monkeypatch.setattr(config, "INVENTARIO", inventario)
    monkeypatch.setattr(pedir, "marcar", lambda *_: None)
    return tmp_path


def imagem(caminho: Path, folha=False, borda=False, grade=False, vazios=0):
    arr = np.zeros((80, 80, 4), dtype=np.uint8)
    if folha:
        for y in range(4):
            for x in range(4):
                if y * 4 + x >= 16 - vazios:
                    continue
                arr[y * 20 + 5:y * 20 + 15, x * 20 + 5:x * 20 + 15] = (10, 100, 200, 255)
    else:
        arr[20:60, 20:60] = (10, 100, 200, 255)
    if borda:
        arr[0, 10:30] = (10, 100, 200, 255)
    if grade:
        arr[40:42, :] = (10, 100, 200, 255)
    Image.fromarray(arr, "RGBA").save(caminho)
    return caminho


def test_prompt_tem_fundo_verde_e_mestra(ambiente):
    assert "#FF00FF" in prompt.montar(config.item("fogo_teste"))
    assert "#00FF00" in prompt.montar(config.item("trevas_teste"))
    config.mestra().parent.mkdir(parents=True)
    imagem(config.mestra())
    assert "imagem-mestra aprovada" in prompt.montar(config.item("fogo_teste"))


def test_pedir_grava_ficha_e_marca(ambiente, monkeypatch):
    marcas, mensagens = [], []
    monkeypatch.setattr(pedir, "marcar", lambda item, estado: marcas.append((item, estado)))
    monkeypatch.setattr(pedir.correio, "pedir_imagem", lambda *a, **k: mensagens.append((a, k)) or {"id": "img1"})
    dados = pedir.pedir("fogo_teste")
    assert dados["estado"] == "pedido" and dados["tentativas"][0]["correio_id"] == "img1"
    assert marcas == [("fogo_teste", "esteira")] and mensagens[0][1]["proporcao"] == "1:1"


def test_colher_pega_imagem(ambiente, monkeypatch):
    origem = imagem(ambiente / "resposta.png")
    dados = ficha.nova(config.item("fogo_teste"))
    dados["tentativas"] = [{"correio_id": "i", "caixa": "chatgpt", "caminhos": {}}]
    ficha.gravar(dados)
    monkeypatch.setattr(colher_mod.correio, "uma", lambda *_: {"situacao": "respondida", "imagem": {"caminho": str(origem)}})
    assert colher_mod.colher("fogo_teste")
    assert Path(ficha.ler("fogo_teste")["tentativas"][-1]["caminhos"]["gerada"]).is_file()


def test_limpar_magenta_deixa_alfa(ambiente):
    arr = np.full((80, 80, 4), (255, 0, 255, 255), dtype=np.uint8)
    arr[20:60, 20:60] = (0, 80, 220, 255)
    origem = ambiente / "magenta.png"
    Image.fromarray(arr, "RGBA").save(origem)
    dados = ficha.nova(config.item("fogo_teste"))
    dados["estado"] = "gerado"
    dados["tentativas"] = [{"caminhos": {"gerada": str(origem)}}]
    ficha.gravar(dados)
    assert limpar.limpar("fogo_teste")
    assert np.asarray(Image.open(ficha.ler("fogo_teste")["tentativas"][-1]["caminhos"]["limpo"]))[..., 3].min() == 0


@pytest.mark.parametrize(("nome", "item_id", "kw", "trecho"), [
    ("sem_alfa", "fogo_teste", {}, "transparencia"),
    ("borda", "fogo_teste", {"borda": True}, "borda"),
    ("grade", "fogo_teste", {"grade": True}, "grade"),
    ("folha15", "folha_teste", {"folha": True, "vazios": 1}, "15 quadros"),
])
def test_portao_reprova_defeitos(ambiente, nome, item_id, kw, trecho):
    caminho = ambiente / f"{nome}.png"
    if nome == "sem_alfa":
        Image.new("RGBA", (80, 80), (10, 100, 200, 255)).save(caminho)
    else:
        imagem(caminho, **kw)
    resultado = portao.validar(config.item(item_id), caminho)
    assert not resultado["aprovado"] and trecho in " ".join(resultado["erros"])


def test_portao_aprova_sprite_limpo(ambiente):
    resultado = portao.validar(config.item("fogo_teste"), imagem(ambiente / "limpo.png"))
    assert resultado["aprovado"]


def test_juiz_pergunta_defeitos_e_le_json(ambiente, monkeypatch):
    limpo = imagem(ambiente / "limpo.png")
    dados = ficha.nova(config.item("fogo_teste"))
    dados["estado"] = "medido"
    dados["tentativas"] = [{"caminhos": {"limpo": str(limpo)}}]
    ficha.gravar(dados)
    enviados = []
    monkeypatch.setattr(juiz.correio, "enviar", lambda *a, **k: enviados.append((a, k)) or {"id": "g1"})
    monkeypatch.setattr(juiz, "_controle", lambda _d: False)
    assert juiz.perguntar("fogo_teste")
    texto = enviados[0][0][1]
    assert enviados[0][0][0] == "gemini"  # o Grok respondia mal (02/10)
    # o juiz sabe O QUE e o desenho, PARA QUE serve e o que cada anexo e (02/10)
    item = config.item("fogo_teste")
    assert "O JOGO:" in texto and "PARA QUE SERVE A SUA RESPOSTA" in texto
    assert str(item.get("descricao") or item["id"]).strip() in texto
    assert "ANEXOS: 1)" in texto and "está errado PARA ESSE USO" in texto


def test_controle_do_juiz_e_cego(ambiente, monkeypatch):
    limpo = imagem(ambiente / "limpo.png")
    dados = ficha.nova(config.item("fogo_teste"))
    dados["estado"] = "medido"
    dados["tentativas"] = [{"caminhos": {"limpo": str(limpo)}}]
    ficha.gravar(dados)
    enviados = []
    monkeypatch.setattr(juiz, "_controle", lambda _d: True)
    monkeypatch.setattr(juiz.correio, "enviar", lambda *a, **k: enviados.append((a, k)) or {"id": "g1"})
    assert juiz.perguntar("fogo_teste")
    # avisar que e controle entregava a resposta ao juiz
    assert "controle" not in enviados[0][0][1].lower() and "estragad" not in enviados[0][0][1].lower()
    assert ficha.ler("fogo_teste")["tentativas"][-1]["controle"] is True


def test_tamanho_real_vem_do_inventario():
    assert juiz._tamanho_real({"tamanho": "folha 1024; no mundo 26x32 (x3 no celular)"}) == (78, 96)
    assert juiz._tamanho_real({"tamanho": "1024x1024"}) is None
    assert juiz.ler_json("lixo {\"defeitos\":[],\"notas\":{}} fim")["defeitos"] == []


def test_controle_juiz_fraco_fica_registrado(ambiente, monkeypatch):
    dados = ficha.nova(config.item("fogo_teste"))
    dados["estado"] = "julgado"
    dados["tentativas"] = [{"juiz_id": "g1", "controle": True, "caminhos": {}}]
    ficha.gravar(dados)
    monkeypatch.setattr(juiz.correio, "uma", lambda *_: {"situacao": "respondida", "resposta": "{\"defeitos\":[],\"notas\":{}}"})
    assert juiz.colher("fogo_teste")
    assert ficha.ler("fogo_teste")["tentativas"][-1]["juiz_fraco"]


def test_grave_refaz_com_o_prompt_do_juiz_e_depois_confere(ambiente, monkeypatch):
    dados = ficha.nova(config.item("fogo_teste"))
    dados["estado"] = "julgado"
    dados["tentativas"] = [{"juiz_id": "g1", "caminhos": {}, "prompt": "p0"}]
    ficha.gravar(dados)
    corrigido = "Arte 2D para Neural Fights. " + "Bola de fogo inteira, sem partículas soltas. " * 3
    resposta = {"defeitos": [{"o_que": "corte", "gravidade": "grave"}],
                "prompt_corrigido": corrigido, "notas": {}}
    monkeypatch.setattr(juiz.correio, "uma", lambda *_: {"situacao": "respondida",
                                                          "resposta": "ok " + json.dumps(resposta)})
    refeitos = []
    monkeypatch.setattr(pedir, "pedir", lambda item, motivo, prompt_pronto="": refeitos.append(
        (item, motivo, prompt_pronto)))
    # o prompt reescrito pelo juiz vai DIRETO ao gerador (02/10/2026)
    assert juiz.colher("fogo_teste") and refeitos == [("fogo_teste", "corte", corrigido.strip())]
    dados = ficha.ler("fogo_teste")
    dados["estado"] = "julgado"
    dados["tentativas"] *= juiz.MAX_TENTATIVAS
    dados["tentativas"][-1]["juiz_id"] = "g1"
    ficha.gravar(dados)
    assert juiz.colher("fogo_teste") and ficha.ler("fogo_teste")["estado"] == "a_conferir"


def test_medida_reprovada_vai_ao_juiz_e_conta_como_grave(ambiente, monkeypatch):
    dados = ficha.nova(config.item("fogo_teste"))
    dados["estado"] = "julgado"
    dados["tentativas"] = [{"juiz_id": "g1", "caminhos": {}, "portao_reprovou": ["pontinhos soltos: 3"]}]
    ficha.gravar(dados)
    monkeypatch.setattr(juiz.correio, "uma", lambda *_: {"situacao": "respondida",
                                                          "resposta": '{"defeitos":[],"notas":{}}'})
    refeitos = []
    monkeypatch.setattr(pedir, "pedir", lambda item, motivo, prompt_pronto="": refeitos.append(motivo))
    assert juiz.colher("fogo_teste") and refeitos == ["pontinhos soltos: 3"]


def test_gerador_e_juiz_cruzados():
    assert pedir.gerador_do({"tipo": "folha"}) == "chatgpt"
    assert pedir.gerador_do({"tipo": "peca"}) == "gemini"
    assert juiz.juiz_do({"caixa": "gemini"}) == "chatgpt"
    assert juiz.juiz_do({"caixa": "chatgpt"}) == "gemini"


def test_a_pergunta_leva_o_prompt_usado_e_as_medidas():
    texto = juiz._pergunta({"id": "x", "descricao": "fogo"}, ["o desenho"], "PROMPT ORIGINAL", ["grade: 3"])
    assert "<<<\nPROMPT ORIGINAL\n>>>" in texto and "grade: 3" in texto and "prompt_corrigido" in texto


def test_aprovar_exporta_com_prova_e_recusa_sem_ela(ambiente, monkeypatch):
    aprovar_mod = importlib.import_module("esteira_sprites.aprovar")
    monkeypatch.setattr(aprovar_mod, "marcar", lambda *_: None)
    limpo = imagem(ambiente / "limpo.png")
    prova = ambiente / "prova.json"
    prova.write_text("{}", encoding="utf-8")
    dados = ficha.nova(config.item("fogo_teste"))
    dados["estado"] = "a_conferir"
    dados["tentativas"] = [{"caminhos": {"limpo": str(limpo), "prova": str(prova)}, "medidas": {}}]
    ficha.gravar(dados)
    saida = aprovar_mod.aprovar("fogo_teste", ambiente / "biblioteca")
    assert Path(saida["folha"]).is_file() and ficha.ler("fogo_teste")["estado"] == "na_biblioteca"
    dados["tentativas"][0]["caminhos"]["prova"] = ""
    ficha.gravar(dados)
    with pytest.raises(ValueError, match="sem prova"):
        aprovar_mod.aprovar("fogo_teste", ambiente / "outra")


def test_exportar_vila_reduz_png_e_guarda_tamanho_original(ambiente):
    aprovar_mod = importlib.import_module("esteira_sprites.aprovar")
    limpo = ambiente / "grande.png"
    Image.new("RGBA", (1600, 900), (10, 100, 200, 255)).save(limpo)
    prova = ambiente / "prova.json"
    prova.write_text("{}", encoding="utf-8")
    dados = {"item": {"id": "casa", "nome_arquivo": "predios/casa.png", "tipo": "peca"},
             "tentativas": [{"caminhos": {"limpo": str(limpo)}, "medidas": {}}]}
    saida = aprovar_mod._exportar_vila(dados, str(prova), ambiente / "biblioteca")
    with Image.open(saida["folha"]) as exportada:
        assert exportada.size == (512, 288)
    meta = json.loads(Path(saida["metadados"]).read_text(encoding="utf-8"))
    assert meta["tamanho_original"] == [1600, 900]


def test_lote_pula_bloqueado_e_opcional(ambiente, monkeypatch):
    from esteira_sprites import __main__ as cli
    pedidos = []
    monkeypatch.setattr(cli, "pedir", lambda item: pedidos.append(item))
    assert cli.lote("P1", 5) == ["fogo_teste", "trevas_teste", "folha_teste"]
    assert "bloqueado" not in pedidos and "opcional" not in pedidos


def test_avancar_sem_resposta_e_idempotente(ambiente):
    from esteira_sprites import __main__ as cli
    dados = ficha.nova(config.item("fogo_teste"))
    dados["tentativas"] = [{"correio_id": "nao_chegou", "caixa": "chatgpt", "caminhos": {}}]
    ficha.gravar(dados)
    assert cli.avancar() == 0
    assert cli.avancar() == 0 and ficha.ler("fogo_teste")["estado"] == "pedido"


def test_juiz_que_falha_nao_gasta_tentativa(ambiente, monkeypatch):
    dados = ficha.nova(config.item("fogo_teste"))
    dados["estado"] = "julgado"
    dados["tentativas"] = [{"juiz_id": "g1", "caminhos": {}, "juiz_caixa": "gemini"}]
    ficha.gravar(dados)
    monkeypatch.setattr(juiz.correio, "uma", lambda *_: {"situacao": "falhou", "erro": "ERR_NAME_NOT_RESOLVED"})
    refeitos = []
    monkeypatch.setattr(pedir, "pedir", lambda *a, **k: refeitos.append(a))
    # rede fora no juiz: pergunta de novo, sem pedir outra imagem (02/10/2026)
    for _ in range(juiz.JUIZ_FALHAS_MAX - 1):
        assert juiz.colher("fogo_teste") and ficha.ler("fogo_teste")["estado"] == "medido"
        d = ficha.ler("fogo_teste")
        d["estado"] = "julgado"
        ficha.gravar(d)
    assert juiz.colher("fogo_teste") and ficha.ler("fogo_teste")["estado"] == "a_conferir"
    assert refeitos == [] and len(ficha.ler("fogo_teste")["tentativas"]) == 1


def test_contar_desde_reabre_as_tentativas():
    assert juiz.tentativas_contadas({"tentativas": [{}] * 6, "contar_desde": 5}) == 1
    assert juiz.tentativas_contadas({"tentativas": [{}] * 4}) == 4


def test_pedir_atualiza_o_item_da_ficha(ambiente, monkeypatch):
    velho = dict(config.item("fogo_teste"), descricao="desenho de antes")
    dados = ficha.nova(velho)
    ficha.gravar(dados)
    monkeypatch.setattr(pedir.correio, "pedir_imagem", lambda *a, **k: {"id": "m1"})
    monkeypatch.setattr(pedir, "marcar", lambda *_: None)
    pedir.pedir("fogo_teste")
    assert ficha.ler("fogo_teste")["item"] == config.item("fogo_teste")
