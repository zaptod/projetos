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
    monkeypatch.setattr(config, "PERFIL", "palco")
    monkeypatch.setenv("NF_IAS_PASTA", str(tmp_path / "correio"))   # nunca o correio de verdade
    monkeypatch.setattr(config, "RAIZ", tmp_path / "esteira")
    monkeypatch.setattr(config, "INVENTARIO", inventario)
    # o Atelie e a biblioteca de verdade nunca entram no teste
    monkeypatch.setattr(config, "ATELIE", tmp_path / "atelie")
    monkeypatch.setattr(config, "BIBLIOTECA_PALCO", tmp_path / "biblioteca_palco")
    monkeypatch.setattr(pedir, "marcar", lambda *_: None)
    # 14/10/2026: todo pedido anexa a imagem-mestra; sem ela nada e pedido
    config.mestra().parent.mkdir(parents=True, exist_ok=True)
    imagem(config.mestra())
    return tmp_path


def base_aprovado_pelo_juiz(item_id: str, limpo: Path, **extra) -> dict:
    """A ficha do sprite-base como o juiz deixa quando aprova (fluxo de 14/10)."""
    from esteira_sprites import base
    dados = ficha.nova(config.item(item_id))
    dados["estado"] = "a_conferir"
    dados["tentativas"] = [{"fluxo": base.FLUXO, "caixa": "chatgpt", "caminhos": {"limpo": str(limpo)},
                            "veredito": {"defeitos": [{"o_que": "x", "gravidade": "leve"}], "notas": {}},
                            **extra}]
    return ficha.gravar(dados)


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
    # a mestra nao e mais citada no corpo: vai ANEXADA, e o cabecalho diz o que e
    texto = prompt.com_anexos(prompt.montar(config.item("fogo_teste")), [prompt.ANEXO_ESTILO])
    assert texto.startswith("ANEXOS") and "imagem 1: a referência de ESTILO" in texto


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
    assert enviados[0][0][0] == "chatgpt"  # Grok e Gemini julgavam mal (02/10)
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


@pytest.mark.parametrize("perfil", ["palco", "vila"])
def test_o_chatgpt_gera_tudo_peca_e_folha_nos_dois_perfis(ambiente, monkeypatch, perfil):
    """14/10/2026: o Adrian mandou voltar ao ChatGPT para TODOS os sprites."""
    monkeypatch.setattr(config, "PERFIL", perfil)
    monkeypatch.setattr(config, "PAGINA", None)
    caixas = []
    monkeypatch.setattr(pedir.correio, "pedir_imagem",
                        lambda caixa, texto, **k: caixas.append(caixa) or {"id": f"m{len(caixas)}"})
    base_aprovado_pelo_juiz("folha_teste_base", imagem(ambiente / "base.png"))
    for item_id in ("fogo_teste", "folha_teste"):          # uma peca e uma folha
        assert config.item(item_id)["tipo"] in ("peca", "folha")
        dados = pedir.pedir(item_id)
        assert dados["tentativas"][-1]["caixa"] == "chatgpt"
    assert caixas == ["chatgpt", "chatgpt"]
    assert pedir.gerador_do({"tipo": "folha"}) == pedir.gerador_do({"tipo": "peca"}) == "chatgpt"
    # e nao ha mais como mandar a outra IA: o parametro `caixa` saiu
    with pytest.raises(TypeError):
        pedir.pedir("fogo_teste", caixa="gemini")


def test_juiz_e_sempre_o_chatgpt():
    assert juiz.JUIZ == "chatgpt"                              # a constante nao engana mais
    assert juiz.juiz_do({"caixa": "gemini"}) == "chatgpt"
    assert juiz.juiz_do({"caixa": "chatgpt"}) == "chatgpt"   # o Gemini julgava mal (02/10)


def test_a_pergunta_ao_juiz_diz_o_tamanho_real():
    """Memoria pergunta-diz-o-que-e-e-pra-que-serve: o QUE e, PARA QUE serve e o TAMANHO real."""
    vila = juiz._pergunta({"id": "casa", "descricao": "casa", "perfil": "vila",
                           "tamanho": "1024x1024; no mundo 72x64 (x3 no celular)"}, ["o desenho"])
    assert "TAMANHO REAL NA TELA: aparece com 216x192 px na tela do celular" in vila
    palco = juiz._pergunta({"id": "fogo", "descricao": "fogo", "perfil": "palco",
                            "tamanho": "512x512, objeto com ~400 px"}, ["o desenho"])
    assert "TAMANHO REAL NA TELA:" in palco and "~144 px na tela do celular" in palco
    assert "512x512, objeto com ~400 px" in palco
    icone = juiz.tamanho_real_txt({"tamanho": "512x512 (aparece com ~30 px no celular)"}, "vila")
    assert icone.startswith("aparece com ~30 px na tela do celular")
    for texto in (vila, palco):
        assert "O QUE É ESTE DESENHO" in texto and "PARA QUE SERVE A SUA RESPOSTA" in texto


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
    # 14/10: pecas E folhas voltaram (ordem do Adrian); a folha espera o sprite-base,
    # que vem PRIMEIRO
    assert cli.FOLHAS_POR_IA is True
    assert cli.lote("P1", 5) == ["folha_teste_base", "fogo_teste", "trevas_teste"]
    assert "bloqueado" not in pedidos and "opcional" not in pedidos
    # a chave continua funcionando, se um dia ele desligar as folhas de novo
    monkeypatch.setattr(cli, "FOLHAS_POR_IA", False)
    assert cli.lote("P1", 5) == ["fogo_teste", "trevas_teste"]


def test_lote_seco_nao_pede_nem_grava(ambiente, monkeypatch):
    from esteira_sprites import __main__ as cli
    monkeypatch.setattr(cli, "pedir", lambda *a, **k: pytest.fail("seco nao pede"))
    assert cli.lote("P1", 2, seco=True) == ["folha_teste_base", "fogo_teste"]
    assert not config.RAIZ.exists() or not list(config.RAIZ.rglob("ficha.json"))


def test_descarte_da_parada_volta_e_o_do_adrian_fica_fora(ambiente, monkeypatch):
    """02/10 a parada descartou tudo o que estava em voo; daqui em diante o descarte e dele."""
    from esteira_sprites import __main__ as cli
    for item_id, quando in (("fogo_teste", "2026-10-02T16:42:38"), ("trevas_teste", "2026-10-14T18:00:00")):
        d = ficha.nova(config.item(item_id))
        d["tentativas"] = [{"caixa": "gemini", "caminhos": {}}] * 6
        d["contar_desde"] = 3
        d["estado"] = "descartado"
        d["historico"] = [{"tipo": "descartado", "em": quando}]
        ficha.gravar(d)
    pedidos = []
    monkeypatch.setattr(cli, "pedir", lambda item: pedidos.append(item))
    monkeypatch.setattr(cli, "FOLHAS_POR_IA", False)
    assert cli.lote("P1", 5) == ["fogo_teste"] and pedidos == ["fogo_teste"]
    volta = ficha.ler("fogo_teste")
    assert juiz.tentativas_contadas(volta) == 0 and volta["historico"][-1]["tipo"] == "volta_a_fila"


def _folha_no_atelie(peca: str, estado: str, animacao: str = "parado", historico: bool = False) -> Path:
    pasta = config.ATELIE / peca / estado / animacao
    if historico:
        pasta = pasta / "historico" / "20261008T000000Z"
    pasta.mkdir(parents=True, exist_ok=True)
    return imagem(pasta / "folha.png")


def test_item_que_o_adrian_fez_no_atelie_nao_e_pedido(ambiente, monkeypatch):
    """14/10/2026: a esteira nunca pede o que ele ja subiu pelo Atelie."""
    from esteira_sprites import __main__ as cli, ja_feito
    itens = [
        {"id": "arma_cristais", "nome_arquivo": "armas/estilos/cristais_flutuantes.png", "tipo": "peca",
         "prioridade": "P1", "ordem": 1},
        {"id": "arma_katana", "nome_arquivo": "armas/estilos/katana.png", "tipo": "peca",
         "prioridade": "P1", "ordem": 2},
        {"id": "pilar", "nome_arquivo": "efeitos/folhas/skills/pilar_de_fogo_erupcao.png", "tipo": "folha",
         "prioridade": "P1", "ordem": 3},
        {"id": "projetil_fogo", "nome_arquivo": "efeitos/folhas/11239_removebg_preview_1.png",
         "tipo": "folha", "prioridade": "P1", "ordem": 4},
        {"id": "acerto", "nome_arquivo": "efeitos/folhas/acerto.png", "tipo": "folha",
         "prioridade": "P1", "ordem": 5},
        {"id": "livre", "nome_arquivo": "efeitos/pecas/skills/livre.png", "tipo": "peca",
         "prioridade": "P1", "ordem": 6},
    ]
    config.INVENTARIO.write_text(json.dumps({"itens": itens}), encoding="utf-8")
    monkeypatch.setattr(cli, "pedir", lambda *a, **k: pytest.fail("seco"))
    # sem nada feito: os sprites-base das 3 folhas primeiro; as folhas esperam por eles
    assert cli.lote("P1", 9, seco=True) == ["pilar_base", "projetil_fogo_base", "acerto_base",
                                            "arma_cristais", "arma_katana", "livre"]
    # a folha dele no Atelie (a pasta de peca/estado/animacao que o app grava)
    _folha_no_atelie("arma.estilo.cristais_flutuantes", "orbitando", "orbitar")
    _folha_no_atelie("skill.pilar_de_fogo", "efeito", "efeito")
    # versao velha no historico nao conta como feito
    _folha_no_atelie("arma.estilo.katana", "parado", historico=True)
    # a folha dele direto na biblioteca (o fogo do piriri) e o destino do `aprovar` ocupado
    (config.BIBLIOTECA_PALCO / "efeitos" / "folhas").mkdir(parents=True)
    imagem(config.BIBLIOTECA_PALCO / "efeitos" / "folhas" / "11239_removebg_preview_1.png")
    imagem(config.BIBLIOTECA_PALCO / "efeitos" / "folhas" / "acerto.png")
    assert cli.lote("P1", 9, seco=True) == ["arma_katana", "livre"]
    assert "Atelie" in ja_feito.motivo(itens[0]) and "biblioteca" in ja_feito.motivo(itens[3])


def test_habitante_da_vila_feito_no_atelie_nao_e_pedido(ambiente, monkeypatch):
    from esteira_sprites import __main__ as cli, ja_feito
    from neural_fights.tools import catalogo_vila
    itens = [{"id": "hab_bot_andar", "grupo": "habitantes", "subgrupo": "bot",
              "nome_arquivo": "habitantes/bot/andar.png", "tipo": "folha", "prioridade": "P1", "ordem": 1},
             {"id": "hab_bot_parado", "grupo": "habitantes", "subgrupo": "bot",
              "nome_arquivo": "habitantes/bot/parado.png", "tipo": "folha", "prioridade": "P1", "ordem": 2},
             {"id": "predio_casa", "grupo": "predios", "nome_arquivo": "predios/casa.png",
              "tipo": "peca", "prioridade": "P1", "ordem": 3}]
    config.INVENTARIO.write_text(json.dumps({"itens": itens}), encoding="utf-8")
    biblioteca = ambiente / "arte_vila"
    monkeypatch.setattr(config, "PERFIL", "vila")
    monkeypatch.setitem(config.PERFIS, "vila", config.Perfil(
        "vila", config.INVENTARIO, "vila", biblioteca, None, exige_mestra=True))
    # a mestra ja vem do `ambiente` (14/10/2026: sem ela nada e pedido)
    assert config.mestra().is_file()
    # a mesma chave que o Atelie e a Vila usam
    peca, estado = catalogo_vila.chave_do_item(itens[0])
    assert (peca, estado) == ("vila.habitantes.bot", "andar")
    _folha_no_atelie(peca, estado, "direita")
    (biblioteca / "predios").mkdir(parents=True)
    imagem(biblioteca / "predios" / "casa.png")              # arte da Vila ja aprovada
    assert cli.lote("P1", 9, seco=True) == ["hab_bot_parado"]
    assert "Atelie" in ja_feito.motivo(itens[0]) and "biblioteca" in ja_feito.motivo(itens[2])


def test_chatgpt_ocupado_a_ficha_espera_e_nao_vai_ao_gemini(ambiente, monkeypatch):
    """14/10/2026: acabou a cobertura pelo Gemini (decisao folhas-chatgpt-ocupado)."""
    cli = importlib.import_module("esteira_sprites.__main__")
    assert not hasattr(cli, "_cobrir_chatgpt_ocupado")
    from esteira_sprites import base
    dados = ficha.nova(dict(config.item("folha_teste")))
    dados["estado"] = "pedido"
    dados["tentativas"] = [{"caixa": "chatgpt", "correio_id": "c1", "prompt": "P" * 90, "motivo": "",
                            "caminhos": {}, "fluxo": base.FLUXO}]
    ficha.gravar(dados)
    # pendente ha 6 horas: as historias seguram a conta do ChatGPT
    monkeypatch.setattr(cli.correio, "uma", lambda caixa, mid: {"situacao": "pendente",
                                                                "em": "2026-10-14T03:00:00"})
    monkeypatch.setattr(colher_mod.correio, "uma", lambda caixa, mid: {"situacao": "pendente",
                                                                       "em": "2026-10-14T03:00:00"})
    monkeypatch.setattr(cli.correio, "atualizar", lambda *a, **k: pytest.fail("nao cancela"))
    monkeypatch.setattr(cli, "pedir", lambda *a, **k: pytest.fail("nao pede de novo"))
    for _ in range(3):
        assert cli.avancar() == 0
    depois = ficha.ler("folha_teste")
    assert depois["estado"] == "pedido" and [t["caixa"] for t in depois["tentativas"]] == ["chatgpt"]


def test_ficha_do_gemini_volta_ao_chatgpt_dentro_do_teto(ambiente, monkeypatch):
    """As fichas que o Gemini comecou antes de 14/10 sao refeitas no ChatGPT, sem gastar o teto."""
    cli = importlib.import_module("esteira_sprites.__main__")
    monkeypatch.setattr(cli, "ESTEIRA_LIGADA", True)
    limpo = imagem(ambiente / "limpo.png")
    for item_id in ("fogo_teste", "trevas_teste", "folha_teste"):
        d = ficha.nova(config.item(item_id))
        d["estado"] = "limpo"
        d["tentativas"] = [{"caixa": "gemini", "correio_id": f"g-{item_id}", "prompt": "velho",
                            "motivo": "", "caminhos": {"limpo": str(limpo)}}]
        ficha.registrar(d, "pedido", correio_id=f"g-{item_id}", motivo="sem franja", caixa="gemini")
        ficha.gravar(d)
    respondidas = {"situacao": "respondida"}
    monkeypatch.setattr(cli.correio, "uma", lambda caixa, mid: respondidas)
    monkeypatch.setattr(cli.correio, "atualizar", lambda *a, **k: pytest.fail("nada pendente"))
    monkeypatch.setattr(cli, "passar", lambda *_: pytest.fail("imagem do Gemini nao anda"))
    assert cli.avancar() == 0
    caixas = []
    monkeypatch.setattr(pedir.correio, "pedir_imagem",
                        lambda caixa, texto, **k: caixas.append((caixa, texto)) or {"id": f"c{len(caixas)}"})
    monkeypatch.setattr(cli, "pedir", pedir.pedir)
    saida = cli.ciclo()
    assert cli.ALVO_EM_VOO == 2 and saida["novos"] == ["fogo_teste", "trevas_teste"]
    assert [c for c, _ in caixas] == ["chatgpt", "chatgpt"] and "sem franja" in caixas[0][1]
    fogo = ficha.ler("fogo_teste")
    assert [t["caixa"] for t in fogo["tentativas"]] == ["gemini", "chatgpt"]
    assert juiz.tentativas_contadas(fogo) == 1 and fogo["tentativas"][0]["trocado_para"] == "chatgpt"
    assert ficha.ler("folha_teste")["estado"] == "limpo"        # espera a vaga


def test_ficha_do_gemini_com_pedido_pendente_e_cancelada(ambiente, monkeypatch):
    cli = importlib.import_module("esteira_sprites.__main__")
    d = ficha.nova(config.item("fogo_teste"))
    d["estado"] = "pedido"
    d["tentativas"] = [{"caixa": "gemini", "correio_id": "g1", "prompt": "p", "caminhos": {}}]
    ficha.gravar(d)
    monkeypatch.setattr(cli.correio, "uma", lambda caixa, mid: {"situacao": "pendente"})
    cancelados = []
    monkeypatch.setattr(cli.correio, "atualizar", lambda caixa, mid, **k: cancelados.append((caixa, mid, k)))
    assert cli.avancar() == 1
    assert cancelados[0][:2] == ("gemini", "g1") and cancelados[0][2]["situacao"] == "falhou"


def test_ciclo_ligado_anda_e_enche_ate_o_alvo(ambiente, monkeypatch):
    """A esteira esta LIGADA (14/10/2026): o ciclo anda as fichas e pede ate ALVO_EM_VOO."""
    cli = importlib.import_module("esteira_sprites.__main__")
    # o interruptor de producao pode estar pausado; o teste prova o ciclo LIGADO
    monkeypatch.setattr(cli, "ESTEIRA_LIGADA", True)
    origem = imagem(ambiente / "resposta.png")
    pedidas = []
    monkeypatch.setattr(pedir.correio, "pedir_imagem",
                        lambda caixa, texto, **k: pedidas.append(caixa) or {"id": f"c{len(pedidas)}"})
    monkeypatch.setattr(cli, "pedir", pedir.pedir)
    primeira = cli.ciclo()
    # o sprite-base da folha vem primeiro (14/10/2026)
    assert primeira == {"perfil": "palco", "andou": 0, "em_voo": 2,
                        "novos": ["folha_teste_base", "fogo_teste"]}
    assert pedidas == ["chatgpt", "chatgpt"]
    # o ChatGPT entrega a primeira: a ficha anda e o ciclo nao passa do alvo
    monkeypatch.setattr(colher_mod.correio, "uma", lambda caixa, mid: (
        {"situacao": "respondida", "imagem": {"caminho": str(origem)}} if mid == "c1" else {"situacao": "pendente"}))
    segunda = cli.ciclo()
    assert segunda["andou"] == 1 and segunda["novos"] == [] and segunda["em_voo"] == 2
    assert ficha.ler("folha_teste_base")["estado"] == "gerado"


def test_ciclo_desligado_nao_faz_nada(ambiente, monkeypatch):
    cli = importlib.import_module("esteira_sprites.__main__")
    monkeypatch.setattr(cli, "ESTEIRA_LIGADA", False)
    monkeypatch.setattr(cli, "avancar", lambda: pytest.fail("desligada"))
    assert cli.ciclo()["desligada"]


def test_avancar_sem_resposta_e_idempotente(ambiente):
    from esteira_sprites import __main__ as cli, base
    dados = ficha.nova(config.item("fogo_teste"))
    dados["tentativas"] = [{"correio_id": "nao_chegou", "caixa": "chatgpt", "caminhos": {},
                            "fluxo": base.FLUXO}]
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


# ------------------------------------------------- fluxo sprite-base -> folhas
# 14/10/2026, o Adrian: "um sprite base para pegar o estilo certo e a partir
# desse sprite base fazer as variacoes em sprite sheet das animacoes".

def _correio_de_imagem(monkeypatch) -> list[dict]:
    """O que a esteira deixaria na caixa do gerador (nenhum carteiro le isto)."""
    pedidos: list[dict] = []

    def pedir_imagem(caixa, texto, **k):
        pedidos.append({"caixa": caixa, "texto": texto, **k})
        return {"id": f"m{len(pedidos)}"}
    monkeypatch.setattr(pedir.correio, "pedir_imagem", pedir_imagem)
    return pedidos


def test_folha_sem_base_pronto_nao_e_pedida(ambiente, monkeypatch):
    from esteira_sprites import __main__ as cli, base
    pedidos = _correio_de_imagem(monkeypatch)
    assert base.id_do_base(config.item("folha_teste"), config.itens()) == "folha_teste_base"
    assert config.item("folha_teste_base")["derivado"] is True
    with pytest.raises(base.BaseFaltando):
        pedir.pedir("folha_teste")
    assert pedidos == [] and ficha.ler("folha_teste") is None
    # o seco cheio (--n 1) ainda conta a folha que espera (antes dizia 0)
    assert cli.lote("P1", 1, seco=True) == ["folha_teste_base"] and cli.ESPERAM_BASE == ["folha_teste"]
    # o lote pede o base e deixa a folha esperando por ele
    monkeypatch.setattr(cli, "pedir", lambda item: pedidos.append({"item": item}))
    assert cli.lote("P1", 9) == ["folha_teste_base", "fogo_teste", "trevas_teste"]
    assert cli.ESPERAM_BASE == ["folha_teste"]
    assert "folha_teste" not in [p.get("item") for p in pedidos]
    # o base em producao (pedido, ainda sem juiz) tambem nao libera a folha
    dados = ficha.nova(config.item("folha_teste_base"))
    dados["tentativas"] = [{"fluxo": base.FLUXO, "caixa": "chatgpt", "correio_id": "m1", "caminhos": {}}]
    ficha.gravar(dados)
    assert "folha_teste" not in cli.lote("P1", 9, seco=True)
    # e o `refazer` de uma folha sem base espera, sem pedir nem quebrar o avancar
    folha = ficha.nova(config.item("folha_teste"))
    folha["estado"] = "refazer"
    folha["tentativas"] = [{"fluxo": base.FLUXO, "caixa": "chatgpt", "caminhos": {}, "erro": "x"}]
    ficha.gravar(folha)
    monkeypatch.setattr(cli, "pedir", pedir.pedir)
    monkeypatch.setattr(cli, "colher", lambda *_: False)
    assert cli.avancar() == 0 and ficha.ler("folha_teste")["estado"] == "refazer"
    assert len(pedidos) == 3                                  # so os do lote acima


def test_pedido_de_base_e_de_peca_anexa_so_a_mestra(ambiente, monkeypatch):
    from esteira_sprites import base
    pedidos = _correio_de_imagem(monkeypatch)
    for item_id in ("folha_teste_base", "fogo_teste"):
        dados = pedir.pedir(item_id)
        t = dados["tentativas"][-1]
        assert t["fluxo"] == base.FLUXO and t["base"] is None
        assert t["anexos"] == [str(config.mestra())]
    for p in pedidos:
        assert p["caixa"] == "chatgpt" and p["anexos"] == [str(config.mestra())]
        cabecalho, corpo = p["texto"].split("\n\n", 1)
        assert cabecalho == f"ANEXOS (leia antes de desenhar):\nimagem 1: {prompt.ANEXO_ESTILO}."
        assert "imagem 2" not in p["texto"] and corpo.strip()
    # o pedido do base diz que e o desenho parado de referencia das folhas
    assert "SPRITE-BASE de: impacto" in pedidos[0]["texto"]


def test_pedido_de_folha_anexa_mestra_e_base_com_cabecalho(ambiente, monkeypatch):
    from PIL import ImageColor

    from esteira_sprites import base
    pedidos = _correio_de_imagem(monkeypatch)
    base_aprovado_pelo_juiz("folha_teste_base", imagem(ambiente / "base.png"))
    dados = pedir.pedir("folha_teste")
    t = dados["tentativas"][-1]
    sprite_base = t["base"]
    assert sprite_base["origem"] == "juiz" and sprite_base["base_id"] == "folha_teste_base"
    assert Path(sprite_base["caminho"]).is_file() and Path(sprite_base["anexo"]).is_file()
    assert pedidos[0]["anexos"] == [str(config.mestra()), sprite_base["anexo"]] == t["anexos"]
    # o anexo do gerador e o base sobre o chroma da folha (o fundo que a limpeza tira)
    with Image.open(sprite_base["anexo"]) as anexo:
        assert anexo.mode == "RGB"
        assert anexo.getpixel((0, 0)) == ImageColor.getrgb(prompt.fundo_do(config.item("folha_teste")))
    linhas = pedidos[0]["texto"].split("\n\n", 1)[0].splitlines()
    assert linhas == ["ANEXOS (leia antes de desenhar):", f"imagem 1: {prompt.ANEXO_ESTILO}.",
                      f"imagem 2: {prompt.ANEXO_BASE}."]
    # o mesmo prompt de novo (falha do gerador) troca o cabecalho, nao empilha
    pedir.pedir("folha_teste", "estourou", prompt_pronto=pedidos[0]["texto"])
    assert pedidos[1]["texto"].count("ANEXOS (") == 1
    assert pedidos[1]["texto"].split("\n\n", 1)[1] == pedidos[0]["texto"].split("\n\n", 1)[1]
    assert ficha.ler("folha_teste")["tentativas"][-1]["base"]["anexo"].endswith("base_2_chroma.png")
    assert t["fluxo"] == base.FLUXO


def test_juiz_da_folha_recebe_o_base_e_pergunta_se_e_o_mesmo(ambiente, monkeypatch):
    from esteira_sprites import base
    _correio_de_imagem(monkeypatch)
    base_aprovado_pelo_juiz("folha_teste_base", imagem(ambiente / "base.png"))
    dados = pedir.pedir("folha_teste")
    dados["estado"] = "medido"
    dados["tentativas"][-1]["caminhos"] = {"limpo": str(imagem(ambiente / "folha.png", folha=True))}
    ficha.gravar(dados)
    enviados = []
    monkeypatch.setattr(juiz, "_controle", lambda _d: False)
    monkeypatch.setattr(juiz.correio, "enviar", lambda *a, **k: enviados.append((a, k)) or {"id": "j1"})
    assert juiz.perguntar("folha_teste")
    texto, anexos = enviados[0][0][1], enviados[0][1]["anexos"]
    pasta = ficha.caminho("folha_teste").parent
    assert str(pasta / "base_para_juiz.png") in anexos and (pasta / "base_para_juiz.png").is_file()
    assert juiz.PERGUNTA_DO_BASE in texto and '"mesmo_do_base":0-3' in texto
    assert "o SPRITE-BASE aprovado do personagem" in texto
    # a peca (sem base) nao leva a pergunta nem o anexo
    peca = ficha.nova(config.item("fogo_teste"))
    peca["estado"] = "medido"
    peca["tentativas"] = [{"fluxo": base.FLUXO, "caminhos": {"limpo": str(imagem(ambiente / "p.png"))}}]
    ficha.gravar(peca)
    assert juiz.perguntar("fogo_teste")
    assert juiz.PERGUNTA_DO_BASE not in enviados[1][0][1] and "mesmo_do_base" not in enviados[1][0][1]


def test_base_so_vira_aceito_com_o_juiz_aprovando(ambiente, monkeypatch):
    from esteira_sprites import base
    limpo = str(imagem(ambiente / "base.png"))
    folha = config.item("folha_teste")

    def com(estado="a_conferir", **t):
        tentativa = {"fluxo": base.FLUXO, "caminhos": {"limpo": limpo},
                     "veredito": {"defeitos": [{"o_que": "x", "gravidade": "leve"}]}}
        tentativa.update(t)
        return {"estado": estado, "tentativas": [tentativa]}
    grave = {"defeitos": [{"o_que": "outro bicho", "gravidade": "grave"}]}
    assert base.juiz_aprovou(com()) is True
    for nao in (com(estado="julgado"), com(estado="medido"),
                com(veredito=grave),                 # tentativas esgotadas: a_conferir com grave
                com(veredito=None),                  # o juiz falhou 3x: a_conferir sem veredito
                com(portao_reprovou=["grade: 3"]),
                com(controle=True),                  # o controle estragado nao e o base
                com(fluxo=None),                     # pedido sem a mestra anexada
                com(caminhos={}), None, {"estado": "a_conferir", "tentativas": []}):
        assert base.juiz_aprovou(nao) is False, nao
    # pelo caminho real: o juiz responde sem grave e so entao a folha tem base
    dados = ficha.nova(config.item("folha_teste_base"))
    dados["estado"] = "julgado"
    dados["tentativas"] = [{"fluxo": base.FLUXO, "caixa": "chatgpt", "juiz_id": "j1",
                            "juiz_caixa": "chatgpt", "caminhos": {"limpo": limpo}}]
    ficha.gravar(dados)
    assert base.referencia(folha) is None
    monkeypatch.setattr(juiz.correio, "uma", lambda *_: {"situacao": "respondida",
                                                          "resposta": json.dumps(grave)})
    monkeypatch.setattr(pedir, "pedir", lambda *a, **k: None)
    assert juiz.colher("folha_teste_base") and base.referencia(folha) is None   # grave: refaz
    d = ficha.ler("folha_teste_base")
    d["estado"] = "julgado"
    ficha.gravar(d)
    monkeypatch.setattr(juiz.correio, "uma", lambda *_: {"situacao": "respondida",
                                                          "resposta": '{"defeitos":[],"notas":{}}'})
    assert juiz.colher("folha_teste_base") and ficha.ler("folha_teste_base")["estado"] == "a_conferir"
    assert base.referencia(folha)["origem"] == "juiz"


def test_o_que_o_adrian_fez_ou_aprovou_vale_mais_que_o_juiz(ambiente):
    from esteira_sprites import base
    folha = config.item("folha_teste")
    base_aprovado_pelo_juiz("folha_teste_base", imagem(ambiente / "juiz.png"))
    assert base.referencia(folha)["origem"] == "juiz"
    d = ficha.ler("folha_teste_base")
    d["estado"] = "na_biblioteca"
    ficha.gravar(d)
    assert base.referencia(folha)["origem"] == "aprovado_pelo_adrian"
    # a peca do objeto ja na biblioteca, sem ficha, tambem serve (senao a folha esperava sempre)
    ficha.caminho("folha_teste_base").unlink()
    alvo = config.BIBLIOTECA_PALCO / config.item("folha_teste_base")["nome_arquivo"]
    alvo.parent.mkdir(parents=True, exist_ok=True)
    imagem(alvo)
    ref = base.referencia(folha)
    assert ref["origem"] == "biblioteca" and ref["fonte"] == str(alvo)


def test_folha_do_fluxo_antigo_sem_base_faz_o_base_ser_pedido(ambiente, monkeypatch):
    """Sem isto o base nunca tinha demanda (a folha ja tem ficha) e ela esperava para sempre."""
    from esteira_sprites import __main__ as cli
    d = ficha.nova(config.item("folha_teste"))
    d["estado"] = "pedido"
    d["tentativas"] = [{"caixa": "chatgpt", "correio_id": "velho", "caminhos": {}}]   # sem `fluxo`
    ficha.gravar(d)
    assert cli._fora_do_fluxo(d) == "sem_anexo"
    monkeypatch.setattr(cli, "pedir", lambda *a, **k: pytest.fail("seco"))
    assert cli.lote("P1", 9, seco=True)[0] == "folha_teste_base"


def test_caso_zero_nada_a_pedir_nao_finge_sucesso(ambiente, monkeypatch, capsys):
    """Memoria relatorio-verde-que-mente: o caso ZERO."""
    from esteira_sprites import __main__ as cli, base
    pedidos = _correio_de_imagem(monkeypatch)
    monkeypatch.setattr(cli, "pedir", pedir.pedir)
    monkeypatch.setattr(cli, "ESTEIRA_LIGADA", True)
    # 1. inventario vazio: nenhuma ficha, nenhum base, nada pedido
    config.INVENTARIO.write_text(json.dumps({"itens": []}), encoding="utf-8")
    assert config.itens() == [] and base.derivar([]) == [] and base.mapa([]) == {}
    assert cli.lote("P1", 9) == [] and cli.lote("P1", 9, seco=True) == []
    assert cli.ciclo() == {"perfil": "palco", "andou": 0, "em_voo": 0, "novos": []}
    assert cli.main(["--inventario", str(config.INVENTARIO), "lote", "--prioridade", "P1", "--seco"]) == 0
    saida = capsys.readouterr().out.splitlines()
    assert saida == ["# fora do fluxo (o ciclo refaz PRIMEIRO, sem gastar tentativa): nenhuma",
                     "# folhas P1 que esperam o sprite-base: 0"]
    assert pedidos == [] and not list(config.RAIZ.rglob("ficha.json"))
    # 2. so folhas, e o base delas ainda no juiz: a folha nao e pedida e o ciclo nao conta ela
    config.INVENTARIO.write_text(json.dumps({"itens": [
        {"id": "so_folha", "nome_arquivo": "efeitos/folhas/so.png", "descricao": "faisca",
         "tipo": "folha", "prioridade": "P1", "ordem": 1}]}), encoding="utf-8")
    d = ficha.nova(config.item("so_folha_base"))
    d["estado"] = "julgado"
    d["tentativas"] = [{"fluxo": base.FLUXO, "caixa": "chatgpt", "juiz_id": "j", "caminhos": {}}]
    ficha.gravar(d)
    monkeypatch.setattr(cli, "colher_juiz", lambda *_: False)
    assert cli.lote("P1", 9) == [] and cli.ESPERAM_BASE == ["so_folha"]
    assert cli.ciclo()["novos"] == [] and pedidos == [] and ficha.ler("so_folha") is None
    # 3. sem a imagem-mestra: nada e pedido, nem pelo `pedir` direto
    config.mestra().unlink()
    ficha.caminho("so_folha_base").unlink()
    assert cli.lote("P1", 9) == []
    with pytest.raises(pedir.SemMestra):
        pedir.pedir("so_folha_base")
    assert pedidos == []


# ------------------------------------------- base rejeitado DEPOIS das folhas
# Decisao builds/base-rejeitado-depois (14/10/2026) = "refazer": as folhas que
# o Adrian nao aprovou voltam a refazer e esperam o base novo; as aprovadas ficam.

FOLHAS_DO_BONECO = ("andar", "pular", "cair", "soco", "chute", "giro", "queda")


def _boneco(ambiente) -> None:
    """Um lutador parado (o base) e 7 folhas dele, no inventario do teste."""
    itens = [{"id": "boneco", "nome_arquivo": "lutadores/boneco.png", "descricao": "lutador boneco",
              "tipo": "peca", "prioridade": "P1", "ordem": 1}]
    itens += [{"id": f"boneco_{n}", "nome_arquivo": f"lutadores/boneco_{n}.png",
               "descricao": f"boneco: {n}", "tipo": "folha", "prioridade": "P1", "ordem": 2 + k}
              for k, n in enumerate(FOLHAS_DO_BONECO)]
    config.INVENTARIO.write_text(json.dumps({"itens": itens}), encoding="utf-8")


def _juiz_aprova_o_base(item_id: str, limpo: Path) -> dict:
    """A ultima tentativa do base passa no juiz (veredito sem grave, portao limpo)."""
    from esteira_sprites import base
    d = ficha.ler(item_id)
    t = d["tentativas"][-1]
    t.update({"fluxo": base.FLUXO, "caminhos": {"limpo": str(limpo)},
              "veredito": {"defeitos": [{"o_que": "x", "gravidade": "leve"}], "notas": {}}})
    d["estado"] = "a_conferir"
    return ficha.gravar(d)


def test_base_refeito_manda_as_folhas_nao_aprovadas_esperarem_o_base_novo(ambiente, monkeypatch):
    from esteira_sprites import __main__ as cli, aprovar, base
    _boneco(ambiente)
    pedidos = _correio_de_imagem(monkeypatch)
    base_aprovado_pelo_juiz("boneco", imagem(ambiente / "base_v1.png"))
    for n in FOLHAS_DO_BONECO:
        pedir.pedir(f"boneco_{n}")
    # a folha guarda QUAL versao do base usou
    assert {ficha.ler(f"boneco_{n}")["tentativas"][-1]["base"]["versao"] for n in FOLHAS_DO_BONECO} == {1}
    # cada folha num ponto da esteira
    limpo = str(imagem(ambiente / "folha.png", folha=True))

    def por(n, estado, **t):
        d = ficha.ler(f"boneco_{n}")
        d["estado"] = estado
        d["tentativas"][-1]["caminhos"] = {"limpo": limpo}
        d["tentativas"][-1].update(t)
        return ficha.gravar(d)
    por("pular", "julgado", juiz_id="j-pular", juiz_caixa="chatgpt")       # no juiz
    por("cair", "a_conferir")                                               # esperando o Adrian
    aprovar.refazer("boneco_soco", "braço maior")                           # o Adrian pediu mudanca
    por("chute", "aprovado")                                                # aprovada pelo Adrian
    por("giro", "na_biblioteca")                                            # aprovada e exportada
    aprovar.descartar("boneco_queda")                                       # descartada por ele
    ficas = {n: ficha.ler(f"boneco_{n}") for n in ("chute", "giro", "queda")}
    # com a folha irma aprovada pelo Adrian, a referencia vem dela (o 1º quadro)
    assert base.referencia(config.item("boneco_andar"))["origem"] == "folha_aprovada_pelo_adrian"
    pendentes = {"m1", "j-pular"}
    monkeypatch.setattr(cli.correio, "uma", lambda caixa, mid: {"situacao": "pendente" if mid in pendentes
                                                                else "respondida"})
    cancelados = []
    monkeypatch.setattr(cli.correio, "atualizar", lambda caixa, mid, **k: cancelados.append((mid, k)))
    antes = len(pedidos)
    # o Adrian manda refazer o BASE depois que as folhas sairam dele
    dados_base = aprovar.refazer("boneco", "o rosto esta errado")
    assert dados_base["estado"] == "refazer" and dados_base["versao_rejeitada"] == 1
    voltaram = [e for e in dados_base["historico"] if e["tipo"] == "base_rejeitado"][-1]["folhas"]
    assert voltaram == ["boneco_andar", "boneco_pular", "boneco_cair", "boneco_soco"]
    for n in ("andar", "pular", "cair", "soco"):
        d = ficha.ler(f"boneco_{n}")
        assert d["estado"] == "refazer" and d["espera_base"]["base_id"] == "boneco"
        assert d["espera_base"]["versao_velha"] == 1 and d["tentativas"][-1]["base_velho"] is True
        # nao gasta tentativa: nenhuma tentativa nova e o teto recomeca com o base novo
        assert len(d["tentativas"]) == 1 and juiz.tentativas_contadas(d) == 0
    assert ficha.ler("boneco_andar")["tentativas"][-1]["motivo"] == base.MOTIVO_BASE_NOVO
    assert ficha.ler("boneco_soco")["tentativas"][-1]["motivo"] == "braço maior"   # o do Adrian fica
    # o que estava pendente no correio (gerar a folha em voo, julgar a do juiz) foi cancelado
    assert {mid for mid, _ in cancelados} == {"m1", "j-pular"}
    assert all(k["situacao"] == "falhou" and k["categoria"] == "interrompida" for _, k in cancelados)
    # as aprovadas pelo Adrian e a descartada nao mudam nada
    for n, d in ficas.items():
        assert ficha.ler(f"boneco_{n}") == d, n
    assert len(pedidos) == antes                                            # nada pedido ainda
    # nenhuma folha e pedida ate o base NOVO passar no juiz: nem pela folha irma
    # aprovada (o desenho velho), nem reaproveitando o base anterior
    assert base.referencia(config.item("boneco_andar")) is None
    with pytest.raises(base.BaseFaltando, match="sprite-base NOVO"):
        pedir.pedir("boneco_andar")
    monkeypatch.setattr(cli, "colher", lambda *_: False)
    monkeypatch.setattr(cli, "colher_juiz", lambda *_: False)
    cli.avancar()                                                           # repede so o base
    assert [p["anexos"] for p in pedidos[antes:]] == [[str(config.mestra())]]
    assert ficha.ler("boneco")["estado"] == "pedido" and len(ficha.ler("boneco")["tentativas"]) == 2
    for _ in range(2):
        cli.avancar()                                                       # base em voo: folhas esperam
    assert len(pedidos) == antes + 1 and ficha.ler("boneco_andar")["estado"] == "refazer"
    assert "boneco_andar" not in cli.lote("P1", 99, seco=True)
    # o juiz aprova o base novo: as folhas sao pedidas com ele (versao 2)
    _juiz_aprova_o_base("boneco", imagem(ambiente / "base_v2.png"))
    cli.avancar()
    assert len(pedidos) == antes + 1 + 4
    for n in ("andar", "pular", "cair", "soco"):
        d = ficha.ler(f"boneco_{n}")
        t = d["tentativas"][-1]
        assert d["estado"] == "pedido" and "espera_base" not in d
        assert t["base"]["origem"] == "juiz" and t["base"]["versao"] == 2 and not base.velho(t["base"])
        assert juiz.tentativas_contadas(d) == 1
        assert any(e["tipo"] == "base_novo" for e in d["historico"])
    assert "braço maior" in ficha.ler("boneco_soco")["tentativas"][-1]["prompt"]
    for n, d in ficas.items():
        assert ficha.ler(f"boneco_{n}")["estado"] == d["estado"], n


def test_base_descartado_depois_e_pedido_de_novo_so_se_folhas_esperam(ambiente, monkeypatch):
    from esteira_sprites import __main__ as cli, aprovar, base
    _correio_de_imagem(monkeypatch)
    base_aprovado_pelo_juiz("folha_teste_base", imagem(ambiente / "base.png"))
    pedir.pedir("folha_teste")
    d = ficha.ler("folha_teste")
    d["estado"] = "a_conferir"
    ficha.gravar(d)
    aprovar.descartar("folha_teste_base")
    folha = ficha.ler("folha_teste")
    assert folha["estado"] == "refazer" and folha["espera_base"]["acao"] == "descartar"
    assert cli.esperam_base_novo("folha_teste_base") == ["folha_teste"]
    # o descarte do Adrian fica fora, MENOS o do base com folhas esperando o novo
    assert cli.lote("P1", 9, seco=True)[0] == "folha_teste_base"
    assert base.referencia(config.item("folha_teste")) is None
    # o Adrian descarta a folha tambem: ninguem espera, o base fica fora
    aprovar.descartar("folha_teste")
    assert cli.esperam_base_novo("folha_teste_base") == []
    assert "folha_teste_base" not in cli.lote("P1", 9, seco=True)


def test_base_rejeitado_caso_zero(ambiente, monkeypatch, capsys):
    """Memoria relatorio-verde-que-mente: base sem folhas, peca comum, base sem tentativa."""
    from esteira_sprites import __main__ as cli, aprovar, base
    monkeypatch.setattr(cli.correio, "atualizar", lambda *a, **k: pytest.fail("nada a cancelar"))
    # 1. base aprovado pelo juiz, nenhuma folha dele com ficha
    base_aprovado_pelo_juiz("folha_teste_base", imagem(ambiente / "base.png"))
    dados = aprovar.refazer("folha_teste_base", "outro rosto")
    assert dados["estado"] == "refazer" and dados["versao_rejeitada"] == 1
    assert [e["folhas"] for e in dados["historico"] if e["tipo"] == "base_rejeitado"] == [[]]
    assert ficha.ler("folha_teste") is None and cli.esperam_base_novo("folha_teste_base") == []
    # 2. peca que nao e base de ninguem: nada muda alem do refazer de sempre
    peca = ficha.nova(config.item("fogo_teste"))
    peca["estado"] = "a_conferir"
    peca["tentativas"] = [{"fluxo": base.FLUXO, "caminhos": {}}]
    ficha.gravar(peca)
    assert "versao_rejeitada" not in aprovar.refazer("fogo_teste", "maior")
    assert "versao_rejeitada" not in aprovar.descartar("fogo_teste")
    # 3. base sem tentativa nenhuma e inventario vazio nao quebram
    assert base.rejeitar({"item_id": "folha_teste_base", "tentativas": []}, "refazer") == []
    assert base.rejeitar({"item_id": "x", "tentativas": [{}]}, "refazer", itens=[]) == []
    assert base.velho(None) is False and base.velho({"origem": "atelie", "base_id": "x"}) is False
    # 4. o seco nao ganha linha nova quando ninguem espera o base novo
    assert cli.main(["--inventario", str(config.INVENTARIO), "lote", "--prioridade", "P1", "--seco"]) == 0
    assert "NOVO" not in capsys.readouterr().out
