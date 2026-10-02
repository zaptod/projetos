"""Validador de animacao, perfis da esteira e inventario da Vila.

As folhas sao desenhadas por codigo (nenhuma IA): um bonequinho de contorno
escuro em 4 linhas de 4 quadros, com o braco subindo e descendo. Cada teste
estraga UMA coisa e confere que o portao reprova com o numero medido.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from esteira_sprites import animacao, config, ficha, prompt

portao = importlib.import_module("esteira_sprites.portao")
juiz = importlib.import_module("esteira_sprites.juiz")
pedir = importlib.import_module("esteira_sprites.pedir")
limpar = importlib.import_module("esteira_sprites.limpar")
cli = importlib.import_module("esteira_sprites.__main__")

CELULA = (96, 128)                 # largura, altura
CONTORNO = (20, 20, 26, 255)
BRACO_BOM = (0, 8, 16, 8)          # sobe e volta: o ultimo emenda no primeiro
BRACO_SEM_VOLTA = (0, 8, 16, 24)   # so sobe: o ultimo fica longe do primeiro


def _ciclos(fps=8, loop=True):
    return [{"nome": n, "quadros": [j * 4 + k for k in range(4)], "fps": fps, "loop": loop}
            for j, n in enumerate(("frente", "esquerda", "direita", "costas"))]


ITEM = {"id": "hab_teste", "nome_arquivo": "habitantes/teste/andar.png", "descricao": "habitante teste",
        "tipo": "folha", "quadros": 16, "prioridade": "P1", "ordem": 1, "bloqueio": "", "opcional": False,
        "chroma": "#FF00FF", "contorno": True, "fundo": "magenta #FF00FF",
        "animacao": {"ciclo": True, "grade": [4, 4], "ancora": "pes", "escala": True, "ciclos": _ciclos()}}


def boneco(braco=0, dx=0, altura=1.0, corpo=(70, 120, 220, 255), contorno=True, perna=0):
    """Um quadro: cabeca, corpo, braco e pernas, pes em y=118."""
    img = Image.new("RGBA", CELULA, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    borda = CONTORNO if contorno else None
    w = 2 if contorno else 0
    pe = 118
    alto = int(round(96 * altura))
    topo = pe - alto
    cx = 48 + dx

    def y(f):                       # posicao relativa na altura do boneco
        return int(round(topo + f * alto))

    d.ellipse([cx - 16, y(0), cx + 16, y(0.34)], fill=(255, 220, 190, 255), outline=borda, width=w)
    d.rectangle([cx - 14, y(0.34), cx + 14, y(0.78)], fill=corpo, outline=borda, width=w)
    d.rectangle([cx + 14, y(0.36) + braco, cx + 24, y(0.36) + braco + 26], fill=corpo, outline=borda, width=w)
    d.rectangle([cx - 12 + perna, y(0.78), cx - 2 + perna, pe], fill=(60, 50, 70, 255), outline=borda, width=w)
    d.rectangle([cx + 2 - perna, y(0.78), cx + 12 - perna, pe], fill=(60, 50, 70, 255), outline=borda, width=w)
    return np.asarray(img)


def folha(quadro=None, linhas=4):
    """Folha 4xN; `quadro(linha, coluna)` devolve o array de cada celula."""
    quadro = quadro or (lambda j, k: boneco(braco=BRACO_BOM[k], perna=(-2, 0, 2, 0)[k]))
    w, h = CELULA
    arr = np.zeros((h * linhas, w * 4, 4), np.uint8)
    for j in range(linhas):
        for k in range(4):
            q = quadro(j, k)
            if q is not None:
                arr[j * h:(j + 1) * h, k * w:(k + 1) * w] = q
    return arr


def salvar(arr, caminho):
    Image.fromarray(arr, "RGBA").save(caminho)
    return caminho


@pytest.fixture
def perfil_limpo(tmp_path, monkeypatch):
    """Isola o perfil global e a pasta da esteira em tmp."""
    monkeypatch.setattr(config, "PERFIL", "palco")
    monkeypatch.setattr(config, "INVENTARIO", config.PERFIS["palco"].inventario)
    monkeypatch.setattr(config, "PAGINA", None)
    monkeypatch.setattr(config, "RAIZ", tmp_path / "esteira")
    return tmp_path


# ------------------------------------------------------------------ validador
def test_ciclo_bom_passa(tmp_path):
    resultado = portao.validar(ITEM, salvar(folha(), tmp_path / "bom.png"))
    assert resultado["aprovado"], resultado["erros"]
    ciclos = resultado["medidas"]["animacao"]["ciclos"]
    assert set(ciclos) == {"frente", "esquerda", "direita", "costas"}
    assert ciclos["frente"]["deriva_chao_px"] == 0 and ciclos["frente"]["trocas_repetidas"] == 0


@pytest.mark.parametrize(("nome", "quadro", "trecho"), [
    ("ancora", lambda j, k: boneco(braco=BRACO_BOM[k], dx=(0, 6, 12, 18)[k] if j == 0 else 0),
     "frente: os pes derivam"),
    ("escala", lambda j, k: boneco(braco=BRACO_BOM[k], altura=0.7 if (j, k) == (1, 2) else 1.0),
     "esquerda: a altura pula"),
    ("paleta", lambda j, k: boneco(braco=BRACO_BOM[k],
                                   corpo=(230, 60, 40, 255) if (j, k) == (2, 1) else (70, 120, 220, 255)),
     "direita: a paleta do quadro 10 diverge"),
    ("loop", lambda j, k: boneco(braco=(BRACO_SEM_VOLTA if j == 3 else BRACO_BOM)[k]),
     "costas: o loop quebra"),
    ("congelado", lambda j, k: boneco(braco=0 if j == 0 else BRACO_BOM[k]),
     "frente: 4 de 4 trocas de quadro sem mudanca"),
    ("vazio", lambda j, k: None if (j, k) == (3, 3) else boneco(braco=BRACO_BOM[k]),
     "animacao com 15 quadros nao-vazios (esperados 16)"),
    ("contorno", lambda j, k: boneco(braco=BRACO_BOM[k], contorno=(j, k) != (0, 2)),
     "contorno escuro falta"),
])
def test_animacao_estragada_reprova_com_o_numero(tmp_path, nome, quadro, trecho):
    resultado = portao.validar(ITEM, salvar(folha(quadro), tmp_path / f"{nome}.png"))
    erros = " | ".join(resultado["erros"])
    assert not resultado["aprovado"] and trecho in erros, erros
    # uma reprovacao por defeito: o resto da folha esta bom
    assert len(resultado["erros"]) == 1, erros


def test_numeros_medidos_vao_na_mensagem(tmp_path):
    arr = folha(lambda j, k: boneco(braco=BRACO_BOM[k], dx=(0, 6, 12, 18)[k] if j == 0 else 0))
    erros, valores = animacao.validar(arr, ITEM)
    assert valores["ciclos"]["frente"]["deriva_pes_px"] == pytest.approx(18, abs=1)
    assert "18.0 px" in erros[0] and "limite 7.8" in erros[0]


def test_folha_sem_marca_de_ciclo_nao_passa_pelo_validador(tmp_path):
    impacto = {**ITEM, "animacao": None}
    assert prompt.animacao(impacto) is None
    assert animacao.validar(folha(), impacto) == ([], {})


def test_previa_gif_toca_os_ciclos_lado_a_lado(tmp_path):
    saida = animacao.previa(folha(), ITEM, tmp_path / "previa")
    with Image.open(saida["gif"]) as gif:
        assert gif.n_frames == 4 and gif.size == (4 * 120, 160)
        assert gif.info["duration"] in (120, 130)   # o GIF guarda centesimos
    if saida["webp"]:
        assert Path(saida["webp"]).is_file()


def test_passar_grava_a_previa_e_o_juiz_recebe_o_gif(perfil_limpo, monkeypatch):
    limpo = salvar(folha(), perfil_limpo / "limpo.png")
    dados = ficha.nova(ITEM)
    dados["estado"] = "limpo"
    dados["tentativas"] = [{"caminhos": {"limpo": str(limpo)}}]
    ficha.gravar(dados)
    assert portao.passar("hab_teste")
    dados = ficha.ler("hab_teste")
    assert dados["estado"] == "medido"
    gif = dados["tentativas"][-1]["caminhos"]["previa_gif"]
    assert Path(gif).is_file()
    enviados = []
    monkeypatch.setattr(juiz, "_controle", lambda _d: False)
    monkeypatch.setattr(juiz.correio, "enviar", lambda *a, **k: enviados.append((a, k)) or {"id": "g1"})
    assert juiz.perguntar("hab_teste")
    texto, anexos = enviados[0][0][1], enviados[0][1]["anexos"]
    assert "julgue a ANIMAÇÃO" in texto and "base deslizando" in texto
    assert gif in anexos


def test_limpar_de_animacao_alinha_pelos_pes_e_mantem_vazias():
    r = limpar._receita(ITEM)
    assert (r.colunas, r.linhas, r.ancora, r.ignorar_vazias) == (4, 4, "pe", False)
    peca = limpar._receita({"id": "p", "tipo": "peca"})
    assert (peca.colunas, peca.linhas, peca.ancora, peca.ignorar_vazias) == (0, 0, "massa", True)


def test_textura_opaca_mede_a_emenda(tmp_path):
    item = {"id": "chao", "tipo": "peca", "fundo": "opaco (textura que emenda)"}
    x = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    onda = (120 + 40 * np.sin(x)[None, :] + 40 * np.cos(x)[:, None]).astype(np.uint8)
    boa = np.dstack([onda, onda, onda, np.full_like(onda, 255)])
    assert portao.validar(item, salvar(boa, tmp_path / "boa.png"))["aprovado"]
    rampa = np.tile(np.linspace(0, 250, 64).astype(np.uint8), (64, 1))
    ruim = np.dstack([rampa, rampa, rampa, np.full_like(rampa, 255)])
    resultado = portao.validar(item, salvar(ruim, tmp_path / "ruim.png"))
    assert not resultado["aprovado"] and "nao emenda" in resultado["erros"][0]


# -------------------------------------------------------------------- perfis
def _inventario_vila(caminho: Path, mestra_externa=True) -> Path:
    itens = [dict(ITEM)]
    if mestra_externa:
        itens.insert(0, {"id": "imagem_mestra", "tipo": "peca", "prioridade": "P1", "ordem": 0,
                         "externo": "palco:imagem_mestra", "nome_arquivo": "_mestra/aprovada.png"})
    caminho.write_text(json.dumps({"itens": itens}), encoding="utf-8")
    return caminho


def test_perfil_vila_usa_a_biblia_e_a_pasta_da_vila(perfil_limpo, monkeypatch):
    inventario = _inventario_vila(perfil_limpo / "inv_vila.json")
    pedidos = []
    monkeypatch.setattr(pedir.correio, "pedir_imagem",
                        lambda caixa, texto, **k: pedidos.append(texto) or {"id": "img1"})
    assert cli.main(["--perfil", "vila", "--inventario", str(inventario), "pedir", "hab_teste"]) == 0
    assert config.PERFIL == "vila" and config.INVENTARIO == inventario
    assert "MESMO estilo dos lutadores do Neural Fights" in pedidos[0]
    assert "Estilo anime cel-shading" in pedidos[0]
    assert "Linha 1: frente (4 quadros, em laço" in pedidos[0]
    ficha_vila = config.RAIZ / "vila" / "hab_teste" / "ficha.json"
    assert ficha_vila.is_file() and json.loads(ficha_vila.read_text(encoding="utf-8"))["perfil"] == "vila"
    # a mestra e a MESMA do palco, fora da subpasta da Vila
    assert config.mestra() == config.RAIZ / "_mestra" / "aprovada.png"


def test_perfil_padrao_continua_o_palco(perfil_limpo, monkeypatch):
    inventario = _inventario_vila(perfil_limpo / "inv.json")
    pedidos = []
    monkeypatch.setattr(pedir.correio, "pedir_imagem",
                        lambda caixa, texto, **k: pedidos.append(texto) or {"id": "img1"})
    monkeypatch.setattr(pedir, "marcar", lambda *_: None)
    assert cli.main(["--inventario", str(inventario), "pedir", "hab_teste"]) == 0
    assert config.PERFIL == "palco" and "Arte 2D para Neural Fights" in pedidos[0]
    assert (config.RAIZ / "hab_teste" / "ficha.json").is_file()
    assert not (config.RAIZ / "vila").exists()


def test_lote_da_vila_espera_a_mestra_e_pula_a_externa(perfil_limpo, monkeypatch):
    monkeypatch.setattr(cli, "FOLHAS_POR_IA", True)       # o item de teste e uma folha
    config.usar("vila", _inventario_vila(perfil_limpo / "inv_vila.json"))
    pedidos = []
    monkeypatch.setattr(cli, "pedir", lambda item: pedidos.append(item))
    assert cli.lote("P1", 5) == [] and pedidos == []
    config.mestra().parent.mkdir(parents=True)
    salvar(boneco(), config.mestra())
    assert cli.lote("P1", 5) == ["hab_teste"]
    with pytest.raises(ValueError, match="mestra do Neural"):
        cli.mestra()
    with pytest.raises(ValueError, match="vem de fora"):
        pedir.pedir("imagem_mestra")


def test_lote_pula_a_mestra_e_espera_a_decisao_do_grupo(perfil_limpo, monkeypatch):
    itens = [{"id": "imagem_mestra", "tipo": "peca", "prioridade": "P1", "ordem": 0},
             {"id": "hab_a", "grupo": "habitantes", "tipo": "peca", "prioridade": "P1", "ordem": 1},
             {"id": "casa", "grupo": "predios", "tipo": "peca", "prioridade": "P1", "ordem": 2}]
    inventario = perfil_limpo / "inv.json"
    inventario.write_text(json.dumps({"itens": itens}), encoding="utf-8")
    config.usar("palco", inventario)
    config.mestra().parent.mkdir(parents=True)
    salvar(boneco(), config.mestra())
    decisoes = perfil_limpo / "decisoes"
    (decisoes / "painel-e-vila").mkdir(parents=True)
    arquivo = decisoes / "painel-e-vila" / "vila-habitante-forma.json"
    arquivo.write_text('{"situacao": "pendente"}', encoding="utf-8")
    monkeypatch.setattr(cli, "DECISOES", decisoes)
    pedidos = []
    monkeypatch.setattr(cli, "pedir", lambda item: pedidos.append(item))
    # a mestra ja aprovada nunca vira pedido; habitante espera a forma
    assert cli.lote("P1", 5) == ["casa"]
    arquivo.write_text('{"situacao": "decidida"}', encoding="utf-8")
    monkeypatch.setattr(cli.ficha, "ler", lambda _id: None)
    assert cli.lote("P1", 5) == ["hab_a", "casa"]


def test_aprovar_da_vila_copia_a_folha_com_metadados(perfil_limpo):
    aprovar = importlib.import_module("esteira_sprites.aprovar")
    config.usar("vila", _inventario_vila(perfil_limpo / "inv_vila.json"))
    limpo = salvar(folha(), perfil_limpo / "limpo.png")
    prova = perfil_limpo / "prova.json"
    prova.write_text('{"conversa": "x"}', encoding="utf-8")
    dados = ficha.nova(ITEM)
    dados["estado"] = "a_conferir"
    dados["tentativas"] = [{"caminhos": {"limpo": str(limpo), "prova": str(prova)}, "medidas": {}}]
    ficha.gravar(dados)
    saida = aprovar.aprovar("hab_teste", perfil_limpo / "arte_vila")
    assert Path(saida["folha"]) == perfil_limpo / "arte_vila" / "habitantes" / "teste" / "andar.png"
    meta = json.loads(Path(saida["metadados"]).read_text(encoding="utf-8"))
    assert meta["grade"] == [4, 4] and meta["animacao"]["ciclos"][0]["fps"] == 8
    assert meta["prova_conteudo"] == {"conversa": "x"}
    dados = ficha.ler("hab_teste")
    dados["estado"] = "a_conferir"
    ficha.gravar(dados)
    with pytest.raises(FileExistsError):
        aprovar.aprovar("hab_teste", perfil_limpo / "arte_vila")


# --------------------------------------------------------- inventario da Vila
INVENTARIO_VILA = config.PERFIS["vila"].inventario


@pytest.fixture(scope="module")
def vila():
    return json.loads(INVENTARIO_VILA.read_text(encoding="utf-8"))


def test_inventario_vila_ids_unicos_p1_com_arquivo_folhas_com_quadros(vila):
    itens = vila["itens"]
    ids = [i["id"] for i in itens]
    assert len(ids) == len(set(ids))
    assert [i["ordem"] for i in itens] == list(range(1, len(itens) + 1))
    for i in itens:
        if i["prioridade"] == "P1":
            assert i["nome_arquivo"], i["id"]
        if i["tipo"] == "folha":
            anim = i["animacao"]
            colunas, linhas = anim["grade"]
            indices = [q for c in anim["ciclos"] for q in c["quadros"]]
            assert i["quadros"] == len(indices) > 0, i["id"]
            assert max(indices) < colunas * linhas and len(indices) == len(set(indices)), i["id"]
            assert all(c["fps"] > 0 and isinstance(c["loop"], bool) for c in anim["ciclos"]), i["id"]


def test_inventario_vila_cobre_a_vila_de_hoje(vila):
    from painel.flutuante import arte, dados
    ids = {i["id"] for i in vila["itens"]}
    for nome in list(arte.LOTES) + ["casa"]:
        assert f"predio_{nome}" in ids
    for nome in dados.PREDIOS:
        for acao in ("parado", "andar", "trabalhar", "conversar", "triste", "comemorar", "sentado"):
            assert f"habitante_{nome}_{acao}" in ids
    for nome in arte.DECORACOES:
        assert f"enfeite_{nome}" in ids
    primeiro = vila["itens"][0]
    assert primeiro["id"] == "imagem_mestra" and primeiro["externo"] == "palco:imagem_mestra"
    p1 = {i["id"] for i in vila["itens"] if i["prioridade"] == "P1"}
    assert {"chao_grama", "caminho_terra", "habitante_grok_andar", "predio_grok"} <= p1


def test_inventario_vila_cabe_no_prompt_e_tem_fundo_valido(vila):
    for i in vila["itens"]:
        if i.get("externo"):
            continue
        texto = prompt.montar(i, defeitos="x" * 400, perfil="vila")
        assert len(texto) < 5000, i["id"]
        if prompt.opaco(i):
            assert "OPACA" in texto and "#FF00FF" not in texto, i["id"]
        else:
            assert i["chroma"] in ("#FF00FF", "#00FF00") and prompt.fundo_do(i) == i["chroma"], i["id"]
