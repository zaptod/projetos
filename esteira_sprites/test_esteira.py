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
    config.mestra().parent.mkdir(parents=True)
    imagem(config.mestra())
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
