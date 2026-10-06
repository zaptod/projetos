from __future__ import annotations

import json

from PIL import Image

from neural_fights.tools import manifesto_sprites
from neural_fights.tools.manifesto_sprites import arquivo_do_destino, importar_antigas


def test_manifesto_commitado_e_igual_ao_gerado():
    gerado = manifesto_sprites.gerar()
    atual = json.loads(manifesto_sprites.PADRAO.read_text(encoding="utf-8"))
    assert atual == gerado


def test_gerar_nao_depende_do_banco_de_personagens(monkeypatch, tmp_path):
    """A contagem de personagens mudava a cada um que nascia (106 x 107) e
    quebrava a comparacao acima; o manifesto so sai da engine."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "sem_banco"))
    manifesto = manifesto_sprites.gerar()
    assert "personagens_no_banco" not in manifesto["resumo"]
    assert manifesto == json.loads(manifesto_sprites.PADRAO.read_text(encoding="utf-8"))
    fonte = manifesto_sprites.PROTOCOLO.read_text(encoding="utf-8")
    assert "personagens.json" not in fonte


def test_toda_lista_da_engine_tem_um_lugar_no_manifesto():
    manifesto = manifesto_sprites.gerar()
    resumo = manifesto["resumo"]
    slots = manifesto["slots"]
    assert len(slots) == resumo["total_slots"] == 1867
    assert {s["grupo"] for s in slots} == {"lutador", "camada_estado", "arma", "skill", "efeito", "arena", "hud"}
    assert len({s["id"] for s in slots}) == len(slots)
    contagens = resumo["contagens_engine"]
    assert contagens["classes"] == 16
    assert contagens["expressoes"] == 24
    assert contagens["skills"] == 118
    assert contagens["tipos_arma"] == 8
    assert contagens["status"] == 29
    assert contagens["arenas"] == 20


def _capacete_falso(tamanho=(512, 533), centro=(257, 278), raio=253, arco=9):
    """Parecido com o classe_berserker.png: chifres e testeira em cima, miolo
    transparente, e embaixo so o arco fino do corpo fechando o miolo."""
    from PIL import ImageDraw
    imagem = Image.new("RGBA", tamanho, (0, 0, 0, 0))
    caneta = ImageDraw.Draw(imagem)
    cx, cy = centro
    caixa = (cx - raio, cy - raio, cx + raio, cy + raio)
    caneta.ellipse(caixa, outline=(20, 20, 26, 255), width=arco)          # o corpo
    caneta.pieslice(caixa, 180, 360, fill=(120, 40, 40, 255))              # o capacete
    caneta.ellipse((cx - raio + 70, cy - raio + 110, cx + raio - 70, cy + raio - 30), fill=(0, 0, 0, 0))
    caneta.polygon(((cx - 200, cy - 120), (cx - 250, cy - 270), (cx - 150, cy - 150)), fill=(160, 30, 30, 255))
    caneta.polygon(((cx + 200, cy - 120), (cx + 250, cy - 270), (cx + 150, cy - 150)), fill=(160, 30, 30, 255))
    return imagem


def _distancia_ao_corpo(imagem):
    """Raio e centro do circulo achado no PNG ja encaixado."""
    from neural_fights.tools.manifesto_sprites import circulo_do_miolo
    return circulo_do_miolo(imagem)


def test_importar_artes_antigas_copia_centrada_e_guarda_a_versao(tmp_path):
    from neural_fights.tools.manifesto_sprites import versoes
    origem = tmp_path / "folhas"
    origem.mkdir()
    Image.new("RGBA", (512, 512), (255, 0, 0, 255)).save(origem / "corpo_bolinha.png")
    _capacete_falso().save(origem / "classe_berserker.png")
    biblioteca = tmp_path / "biblioteca"
    destino = arquivo_do_destino(biblioteca, "palco/biblioteca/partes/lutador/pele/comum/_/base.png")
    destino.parent.mkdir(parents=True)
    Image.new("RGBA", (1024, 1024), (0, 255, 0, 255)).save(destino)

    copiados = importar_antigas(biblioteca, origem)

    assert len(copiados) == 2
    assert Image.open(destino).getpixel((512, 512))[:3] == (255, 0, 0)
    anteriores = versoes(destino)
    assert len(anteriores) == 1 and len(anteriores[0].name) == 24       # o mesmo carimbo da API
    assert Image.open(anteriores[0]).getpixel((512, 512))[:3] == (0, 255, 0)
    assert Image.open(origem / "corpo_bolinha.png").getpixel((0, 0))[:3] == (255, 0, 0)
    # O capacete e ACESSORIO DE CABECA do Berserker, nao a pele da classe.
    capacete = biblioteca / "partes/lutador/acessorio_cabeca/classe/berserker_furia/base.png"
    assert copiados[1] == capacete.resolve()
    assert not (biblioteca / "partes/lutador/pele/classe/berserker_furia/base.png").exists()
    # O arco do capacete cai em cima do circulo de 512 do gabarito (06/10:
    # pela ancora o centro saia em 524,544.5 e o arco passava ~40 px longe).
    cx, cy, raio = _distancia_ao_corpo(Image.open(capacete))
    assert abs(cx - 512) <= 3 and abs(cy - 512) <= 3 and abs(raio - 256) <= 3


def test_encaixe_de_anel_com_miolo_transparente():
    """Um anel grosso simples (sem arco fino) tambem cai em cima do corpo."""
    from PIL import ImageDraw
    from neural_fights.tools.manifesto_sprites import encaixar_no_corpo
    anel = Image.new("RGBA", (400, 420), (0, 0, 0, 0))
    caneta = ImageDraw.Draw(anel)
    caneta.ellipse((40, 60, 360, 380), fill=(200, 200, 0, 255))
    caneta.ellipse((90, 110, 310, 330), fill=(0, 0, 0, 0))      # miolo de raio 110 em (200,220)
    quadro = encaixar_no_corpo(anel, (200, 220))
    cx, cy, raio = _distancia_ao_corpo(quadro)
    assert abs(cx - 512) <= 3 and abs(cy - 512) <= 3 and abs(raio - 256) <= 3
    assert quadro.getpixel((512, 512))[3] == 0          # o miolo continua vazio


def test_peca_sem_miolo_usa_a_ancora():
    from neural_fights.tools.manifesto_sprites import encaixar_no_corpo
    quadro = encaixar_no_corpo(Image.new("RGBA", (100, 100), (1, 2, 3, 255)), (50, 50))
    assert quadro.getbbox() == (462, 462, 562, 562)


def test_regra_do_rosto_e_a_mesma_do_palco():
    """FAMILIA, EXPRESSOES e NIVEIS em Python sao copia do partes_lutador.gd."""
    import re
    from neural_fights.tools import manifesto_sprites as m
    gd = (manifesto_sprites.RAIZ / "palco" / "nucleo" / "partes_lutador.gd").read_text(encoding="utf-8")
    familia = dict(re.findall(r'"(\w+)": "(\w+)"', gd.split("const FAMILIA := {")[1].split("}")[0]))
    assert familia == m.FAMILIA
    expressoes = re.findall(r'"(\w+)"', gd.split("const EXPRESSOES := [")[1].split("]")[0])
    assert tuple(expressoes) == m.EXPRESSOES
    niveis_gd = gd.split("const NIVEIS := {")[1].split("}")[0]
    for parte, niveis in m.NIVEIS.items():
        assert re.search(rf'"{parte}": \[{", ".join(chr(34) + n + chr(34) for n in niveis)}\]', niveis_gd), parte
    existe = {("olhos", "classe", "berserker_furia", "neutro"), ("olhos", "comum", "_", "dor")}
    achado = m.resolver_parte("olhos", "berserker_furia", "tonto", lambda *k: k in existe)
    # A classe e dona dos olhos: cai no neutro DELA, nunca no 'dor' comum.
    assert achado == {"nivel": "classe", "alvo": "berserker_furia", "estado": "neutro"}


def test_gabarito_aparece_em_fundo_claro_e_escuro():
    import io
    from neural_fights.tools.manifesto_sprites import gabarito_lutador
    imagem = Image.open(io.BytesIO(gabarito_lutador("olhos"))).convert("RGBA")
    assert imagem.size == (1024, 1024) and imagem.getpixel((0, 0))[3] == 0
    for fundo_cor in ((255, 255, 255, 255), (0, 0, 0, 255), (60, 140, 60, 255)):
        fundo = Image.new("RGBA", imagem.size, fundo_cor)
        fundo.alpha_composite(imagem)
        # Em cima do circulo do corpo ha pixel bem diferente do fundo.
        faixa = [fundo.getpixel((512, y))[:3] for y in range(248, 266)]
        assert max(sum(abs(a - b) for a, b in zip(px, fundo_cor[:3])) for px in faixa) > 300
    # Legenda escrita no PNG (canto de cima) e zona dos olhos marcada.
    assert imagem.crop((20, 20, 600, 80)).getbbox() is not None
