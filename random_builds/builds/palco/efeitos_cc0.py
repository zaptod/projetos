"""Efeitos por (TIPO x ELEMENTO) com a arte CC0: traz as texturas e gera as cenas.

    python main.py palco efeitos-cc0                    # texturas + cenas + LICENCAS.md
    python main.py palco efeitos-cc0 --so-cenas

A escolha de cada par vem do `E:\\ferramentas\\arte_cc0\\catalogo_candidatos.md`
(secao 1.5, "Os 12 elementos x 3 formas"). Tudo e mascara BRANCA com alfa: o
palco pinta com a paleta do elemento (UtilPalco.PALETAS), entao uma textura
serve varios elementos.

A biblioteca procura, nesta ordem (nucleo/biblioteca.gd):
  efeitos/skills/<skill>.tscn            sobrescrita de UMA skill
  efeitos/objetos/<tipo>/<elemento>.tscn o par tipo x elemento (gerado aqui)
  efeitos/objetos/<tipo>/_padrao.tscn    o padrao do tipo (gerado aqui)
  efeitos/objetos/_padrao.tscn           o desenho procedural da 16D

As cenas geradas so apontam o script `objeto_cc0.gd` e as texturas: abra uma
no editor e troque a textura no inspetor (grupo "Arte (CC0)"). Gerar de novo
SOBRESCREVE as cenas geradas; uma cena feita a mao para outro par nao e tocada
(so os pares da TABELA sao escritos).
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import config

PALCO = config.RAIZ_PROJETOS / "palco"
BIB = PALCO / "biblioteca"
TEX = BIB / "efeitos" / "texturas"
OBJ = BIB / "efeitos" / "objetos"
A = Path(r"E:/ferramentas/arte_cc0")
KP = A / "kenney/kenney_particle-pack/PNG (Transparent)"
KL = A / "kenney/kenney_light-masks/Transparent"
SPLAT = A / "kenney/kenney_splat-pack/PNG/Double (512px)"
CIRC = A / "opengameart/4-summoning-circles"
PROVA_KP = "`License.txt` do zip; kenney.nl/assets/particle-pack"
PROVA_KL = "`License.txt` do zip; kenney.nl/assets/light-masks"

# nome no palco: (origem, lado, receita, autor, pacote, prova)
#   receita: "mascara" = alfa x luminancia; "linhas" = traco preto em fundo
#   claro vira alfa; "+circulo" recorta num disco suave; "+girar" poe o feixe
#   (vertical no pacote) deitado em +x; "+faixa" zera o alfa nas bordas de
#   cima e de baixo (o feixe repetido nao desenha um retangulo em volta)
TEXTURAS = {
    "fogo": (KP / "fire_01.png", 512, "mascara", "Kenney", "Particle Pack v1.1, `fire_01.png`", PROVA_KP),
    "estrela_4": (KP / "star_07.png", 256, "mascara", "Kenney", "Particle Pack v1.1, `star_07.png`", PROVA_KP),
    "bola": (KP / "circle_05.png", 512, "mascara", "Kenney", "Particle Pack v1.1, `circle_05.png`", PROVA_KP),
    "raio": (KP / "spark_01.png", 512, "mascara", "Kenney", "Particle Pack v1.1, `spark_01.png`", PROVA_KP),
    "magia_estrela": (KP / "magic_05.png", 256, "mascara", "Kenney", "Particle Pack v1.1, `magic_05.png`", PROVA_KP),
    "magia_anel": (KP / "magic_03.png", 256, "mascara", "Kenney", "Particle Pack v1.1, `magic_03.png`", PROVA_KP),
    "magia_pontos": (KP / "magic_02.png", 512, "mascara", "Kenney", "Particle Pack v1.1, `magic_02.png`", PROVA_KP),
    "terra": (KP / "dirt_01.png", 256, "mascara", "Kenney", "Particle Pack v1.1, `dirt_01.png`", PROVA_KP),
    "giro_1": (KP / "twirl_01.png", 512, "mascara", "Kenney", "Particle Pack v1.1, `twirl_01.png`", PROVA_KP),
    "giro_2": (KP / "twirl_02.png", 512, "mascara", "Kenney", "Particle Pack v1.1, `twirl_02.png`", PROVA_KP),
    "giro_3": (KP / "twirl_03.png", 512, "mascara", "Kenney", "Particle Pack v1.1, `twirl_03.png`", PROVA_KP),
    "arranhao": (KP / "scratch_01.png", 256, "mascara", "Kenney", "Particle Pack v1.1, `scratch_01.png`", PROVA_KP),
    "aro": (KP / "circle_04.png", 256, "mascara", "Kenney", "Particle Pack v1.1, `circle_04.png`", PROVA_KP),
    "estrelinha": (KP / "star_04.png", 256, "mascara", "Kenney", "Particle Pack v1.1, `star_04.png`", PROVA_KP),
    "luz_aneis": (KP / "light_03.png", 512, "mascara", "Kenney", "Particle Pack v1.1, `light_03.png`", PROVA_KP),
    "fumaca_anel": (KP / "smoke_10.png", 512, "mascara", "Kenney", "Particle Pack v1.1, `smoke_10.png`", PROVA_KP),
    "raio_linha": (KP / "spark_07.png", 512, "mascara+faixa", "Kenney", "Particle Pack v1.1, `spark_07.png`", PROVA_KP),
    "flor": (KL / "shape_g.png", 256, "mascara", "Kenney", "Light Masks v1.0, `shape_g.png`", PROVA_KL),
    "aneis_a": (KL / "circle_rings_a.png", 512, "mascara", "Kenney", "Light Masks v1.0, `circle_rings_a.png`", PROVA_KL),
    "aneis_c": (KL / "circle_rings_c.png", 256, "mascara", "Kenney", "Light Masks v1.0, `circle_rings_c.png`", PROVA_KL),
    "aneis_d": (KL / "circle_rings_d.png", 512, "mascara", "Kenney", "Light Masks v1.0, `circle_rings_d.png`", PROVA_KL),
    "gelo_rachado": (KL / "water_caustics_b.png", 512, "mascara+circulo", "Kenney",
                     "Light Masks v1.0, `water_caustics_b.png` (recortado num disco)", PROVA_KL),
    "aro_fino": (KL / "ring_a.png", 512, "mascara", "Kenney", "Light Masks v1.0, `ring_a.png`", PROVA_KL),
    "aro_duplo": (KL / "ring_b.png", 512, "mascara", "Kenney", "Light Masks v1.0, `ring_b.png`", PROVA_KL),
    "folhagem": (KL / "foliage_canopy_d.png", 512, "mascara+circulo", "Kenney",
                 "Light Masks v1.0, `foliage_canopy_d.png` (recortado num disco)", PROVA_KL),
    "feixe_a": (KL / "streaks_composed_a.png", 512, "mascara+girar+faixa", "Kenney",
                "Light Masks v1.0, `streaks_composed_a.png` (deitado em +x)", PROVA_KL),
    "feixe_d": (KL / "streaks_composed_d.png", 512, "mascara+girar+faixa", "Kenney",
                "Light Masks v1.0, `streaks_composed_d.png` (deitado em +x)", PROVA_KL),
    "circulo_arcano": (CIRC / "circle6.png", 512, "linhas", "Luke.RUSTLTD",
                       "4 Summoning Circles, `circle6.png` (1000 -> 512, traco preto -> mascara)",
                       "opengameart.org/content/4-summoning-circles"),
    "circulo_tempo": (CIRC / "circle4.png", 512, "linhas", "Luke.RUSTLTD",
                      "4 Summoning Circles, `circle4.png` (1000 -> 512, traco preto -> mascara)",
                      "opengameart.org/content/4-summoning-circles"),
    "mancha": (SPLAT / "splat03.png", 512, "mascara", "Kenney", "Splat Pack v1.0, `splat03.png`",
               "`License.txt` do zip; kenney.nl/assets/splat-pack"),
}

# As texturas que ja estavam na biblioteca (16D) tambem entram na tabela.
JA_EXISTEM = {"brilho", "chama", "estrela", "estrela_larga", "anel", "faisca", "fumaca", "onda", "rastro"}

# Os pares. Campos = os @export de objeto_cc0.gd. Cor: chave da paleta do
# elemento (core, mid, outer, spark, glow).
_P = "projetil"
_A = "area"
_B = "beam"
TABELA: dict[tuple[str, str], dict] = {
    # ---------------- projetil: nucleo girando + halo + rastro
    (_P, "_padrao"): {"nucleo": "estrela", "halo": "brilho", "giro": 3.0},
    (_P, "fogo"): {"nucleo": "fogo", "halo": "chama", "giro": 4.0, "nucleo_escala": 3.0},
    (_P, "gelo"): {"nucleo": "estrela_4", "halo": "bola", "giro": 1.2},
    (_P, "raio"): {"nucleo": "raio", "halo": "brilho", "giro": 11.0, "nucleo_escala": 3.4},
    (_P, "trevas"): {"nucleo": "fumaca", "halo": "chama", "giro": 2.0, "aditivo": False, "cor_nucleo": "mid"},
    (_P, "luz"): {"nucleo": "magia_estrela", "halo": "brilho", "giro": 1.5},
    (_P, "natureza"): {"nucleo": "flor", "halo": "terra", "giro": 2.5},
    (_P, "arcano"): {"nucleo": "magia_anel", "halo": "chama", "giro": 2.2},
    (_P, "caos"): {"nucleo": "giro_2", "halo": "estrela_larga", "giro": 6.0, "duas_cores": True},
    (_P, "sangue"): {"nucleo": "arranhao", "halo": "bola", "giro": 5.0, "aditivo": False, "cor_nucleo": "mid"},
    (_P, "void"): {"nucleo": "aro", "halo": "giro_3", "giro": -3.0, "aditivo": False, "nucleo_escuro": True},
    (_P, "tempo"): {"nucleo": "aneis_c", "halo": "estrelinha", "giro": 0.8, "ponteiros": True},
    (_P, "gravitacao"): {"nucleo": "giro_1", "halo": "giro_3", "giro": 4.0, "halo_giro": -3.0},
    # ---------------- area: preenchimento girando + anel
    (_A, "_padrao"): {"preenchimento": "bola", "anel": "onda", "giro": 0.6},
    (_A, "fogo"): {"preenchimento": "fogo", "anel": "onda", "giro": 0.9},
    (_A, "gelo"): {"preenchimento": "gelo_rachado", "anel": "aro_duplo", "giro": 0.15},
    (_A, "raio"): {"preenchimento": "raio", "anel": "onda", "giro": 7.0},
    (_A, "trevas"): {"preenchimento": "fumaca_anel", "anel": "giro_3", "giro": 0.8, "aditivo": False},
    (_A, "luz"): {"preenchimento": "luz_aneis", "anel": "aneis_d", "giro": 0.4},
    (_A, "natureza"): {"preenchimento": "folhagem", "anel": "aro_fino", "giro": 0.25},
    (_A, "arcano"): {"preenchimento": "circulo_arcano", "anel": "magia_pontos", "giro": 0.5},
    (_A, "caos"): {"preenchimento": "giro_2", "anel": "estrela_larga", "giro": 3.0, "duas_cores": True},
    (_A, "sangue"): {"preenchimento": "mancha", "anel": "bola", "giro": 0.1, "aditivo": False},
    (_A, "void"): {"preenchimento": "giro_3", "anel": "fumaca_anel", "giro": -2.0, "aditivo": False,
                   "nucleo_escuro": True},
    (_A, "tempo"): {"preenchimento": "circulo_tempo", "anel": "aneis_c", "giro": 0.35, "ponteiros": True},
    (_A, "gravitacao"): {"preenchimento": "giro_3", "anel": "aneis_a", "giro": 2.0, "encolhe": True},
    # ---------------- beam: corpo correndo ao longo do feixe + ponta
    (_B, "_padrao"): {"corpo": "feixe_a", "ponta": "brilho"},
    (_B, "fogo"): {"corpo": "feixe_a", "ponta": "fogo"},
    (_B, "gelo"): {"corpo": "feixe_d", "ponta": "estrela_4"},
    (_B, "raio"): {"corpo": "raio_linha", "ponta": "raio"},
    (_B, "trevas"): {"corpo": "feixe_d", "ponta": "fumaca", "aditivo": False},
    (_B, "luz"): {"corpo": "feixe_a", "ponta": "magia_estrela"},
    (_B, "natureza"): {"corpo": "feixe_a", "ponta": "flor"},
    (_B, "arcano"): {"corpo": "feixe_a", "ponta": "magia_anel"},
    (_B, "caos"): {"corpo": "raio_linha", "ponta": "estrela_larga", "duas_cores": True},
    (_B, "sangue"): {"corpo": "feixe_d", "ponta": "arranhao", "aditivo": False},
    (_B, "void"): {"corpo": "feixe_d", "ponta": "aro", "aditivo": False, "nucleo_escuro": True},
    (_B, "tempo"): {"corpo": "feixe_a", "ponta": "estrelinha", "ponteiros": True},
    (_B, "gravitacao"): {"corpo": "feixe_d", "ponta": "giro_1"},
}
CAMPOS_TEXTURA = ("nucleo", "halo", "preenchimento", "anel", "corpo", "ponta")


def _mascara(origem: Path, receita: str, lado: int) -> Image.Image:
    im = Image.open(origem).convert("RGBA")
    if receita.startswith("linhas"):
        # traco preto sobre fundo claro (opaco): alfa = escuridao
        alfa = ImageChops.invert(im.convert("L"))
        alfa = ImageChops.multiply(alfa, im.getchannel("A"))
    else:
        alfa = ImageChops.multiply(im.getchannel("A"), im.convert("L"))
    if "+girar" in receita:
        alfa = alfa.rotate(90, expand=True)
    alfa = alfa.resize((lado, lado), Image.LANCZOS)
    if "+circulo" in receita:
        disco = Image.new("L", (lado, lado), 0)
        ImageDraw.Draw(disco).ellipse((lado * 0.06, lado * 0.06, lado * 0.94, lado * 0.94), fill=255)
        disco = disco.filter(ImageFilter.GaussianBlur(lado * 0.04))
        alfa = ImageChops.multiply(alfa, disco)
    if "+faixa" in receita:
        perfil = Image.new("L", (1, lado), 0)
        for y in range(lado):
            d = abs(2.0 * (y + 0.5) / lado - 1.0)          # 0 no meio, 1 na borda
            perfil.putpixel((0, y), int(255 * max(0.0, 1.0 - d) ** 0.7))
        alfa = ImageChops.multiply(alfa, perfil.resize((lado, lado)))
    branco = Image.new("RGBA", (lado, lado), (255, 255, 255, 255))
    branco.putalpha(alfa)
    return branco


def trazer_texturas() -> list[str]:
    usadas = {v for par in TABELA.values() for k, v in par.items() if k in CAMPOS_TEXTURA}
    faltam = usadas - set(TEXTURAS) - JA_EXISTEM
    if faltam:
        raise SystemExit(f"textura sem origem na tabela: {sorted(faltam)}")
    linhas = []
    for nome, (origem, lado, receita, autor, pacote, prova) in TEXTURAS.items():
        if nome not in usadas:
            continue
        _mascara(origem, receita, lado).save(TEX / f"{nome}.png", optimize=True)
        linhas.append(f"| `efeitos/texturas/{nome}.png` | {pacote} ({lado} px) | {autor} | CC0 | {prova} |")
        print(f"textura {nome:16s} <- {origem.name} ({lado})")
    return linhas


def _cena(tipo: str, elemento: str, campos: dict) -> str:
    externos = [("Script", "res://biblioteca/efeitos/objetos/objeto_cc0.gd")]
    for campo in CAMPOS_TEXTURA:
        if campo in campos:
            externos.append(("Texture2D", f"res://biblioteca/efeitos/texturas/{campos[campo]}.png"))
    ids = {caminho: f"{k + 1}_x" for k, (_t, caminho) in enumerate(externos)}
    nome = "".join(p.capitalize() for p in f"{tipo}_{elemento}".split("_") if p) or "Objeto"
    saida = [f"[gd_scene load_steps={len(externos) + 1} format=3]", ""]
    for tipo_ext, caminho in externos:
        saida.append(f'[ext_resource type="{tipo_ext}" path="{caminho}" id="{ids[caminho]}"]')
    saida += ["", f'[node name="{nome}" type="Node2D"]',
              f'script = ExtResource("{ids[externos[0][1]]}")']
    for campo, valor in campos.items():
        if campo in CAMPOS_TEXTURA:
            saida.append(f'{campo} = ExtResource("{ids[f"res://biblioteca/efeitos/texturas/{valor}.png"]}")')
        elif isinstance(valor, bool):
            saida.append(f"{campo} = {'true' if valor else 'false'}")
        elif isinstance(valor, str):
            saida.append(f'{campo} = "{valor}"')
        else:
            saida.append(f"{campo} = {float(valor)}")
    return "\n".join(saida) + "\n"


def gerar_cenas() -> int:
    n = 0
    for (tipo, elemento), campos in TABELA.items():
        destino = OBJ / tipo / f"{elemento}.tscn"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(_cena(tipo, elemento, campos), encoding="utf-8", newline="\n")
        n += 1
    print(f"{n} cenas em {OBJ}")
    return n


INICIO = "<!-- efeitos_cc0:inicio (gerado por main.py palco efeitos-cc0) -->"
FIM = "<!-- efeitos_cc0:fim -->"


def escrever_licencas(linhas: list[str]) -> None:
    arquivo = BIB / "LICENCAS.md"
    texto = arquivo.read_text(encoding="utf-8")
    bloco = "\n".join([INICIO, "", "Efeitos por tipo x elemento (16E):", "",
                       "| arquivo no palco | origem | autor | licença | prova |",
                       "|---|---|---|---|---|", *linhas, "", FIM])
    if INICIO in texto:
        texto = re.sub(re.escape(INICIO) + r".*?" + re.escape(FIM), lambda _m: bloco, texto, flags=re.S)
    else:
        texto = texto.rstrip("\n") + "\n\n" + bloco + "\n"
    arquivo.write_text(texto, encoding="utf-8", newline="\n")


def gerar(*, so_cenas: bool = False) -> int:
    if not so_cenas:
        escrever_licencas(trazer_texturas())
    return gerar_cenas()
