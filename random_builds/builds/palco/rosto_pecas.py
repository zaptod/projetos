"""Recorta as PECAS DO ROSTO do Kenney Shape Characters (CC0) em mascaras
brancas nitidas, com nome, para a biblioteca do palco.

    python main.py palco pecas-do-rosto                 # grava em palco/biblioteca/lutadores/rosto/
    python main.py palco pecas-do-rosto --folha F.png

De onde: `E:\\ferramentas\\arte_cc0\\kenney\\kenney_shape-characters\\Vector\\overview.svg`
(licenca em palco/biblioteca/LICENCAS.md). O SVG e rasterizado pelo proprio
Godot (ferramentas/rasterizar_svg.gd) SO na regiao dos rostos, a 1x (para
achar as pecas) e a 12x (para recortar): o olho sai com 144 px e, na bolinha
de 408 px da tela, o maior uso de qualquer peca (a boca aberta do euforico,
1,5x o olho) pede 122 px: a peca sempre DIMINUI (nitida). A 4x (16D) o olho
tinha 64 px e a 8x a boca aberta ainda crescia 1,27x (medido no teste
test_pecas_do_rosto_nitidas_a_408_px).

As pecas saem BRANCAS com alfa: o palco pinta com a cor do traco do estilo
(#14141A), como as mascaras do Kenney dos efeitos. Os nomes sao os do
pacote (PNG/Default/facial_part_*.png), achados pela posicao no overview:

  linha 1: eye_open, eyebrow_a (reta), eyebrow_b (inclinada), eyebrow_c
           (curva curta), eyebrow_d (grossa)
  linha 2: eye_half_top, eye_half_top_wing, mouth_happy, mouth_sad, mouth_smirk
  linha 3: eye_half_bottom, eye_closed_down, eye_closed_up
  e o olho em X do rosto pronto face_j (eye_x).
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import config, godot

PALCO = config.RAIZ_PROJETOS / "palco"
SVG = Path(r"E:\ferramentas\arte_cc0\kenney\kenney_shape-characters\Vector\overview.svg")
DESTINO = PALCO / "biblioteca" / "lutadores" / "rosto"
ESCALA = 12
# regiao dos rostos no overview (unidades do SVG = px a 1x)
REGIAO = (0, 375, 360, 305)
LINHAS = [
    ((0, 30), ["eye_open", "eyebrow_a", "eyebrow_b", "eyebrow_c", "eyebrow_d"]),
    ((45, 72), ["eye_half_top", "eye_half_top_wing", "mouth_happy", "mouth_sad", "mouth_smirk"]),
    ((76, 100), ["eye_half_bottom", "eye_closed_down", "eye_closed_up"]),
]
# o X do face_j: sem dilatar (cada X ja e um componente so)
CAIXA_X = (110, 255, 180, 290)
MARGEM = 6  # px em volta da peca no png (o filtro linear precisa de borda)


def _dilatar(m, it):
    for _ in range(it):
        p = np.pad(m, 1)
        m = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return m


def _componentes(m):
    """Caixas (y0, x0, y1, x1) dos componentes 4-conexos."""
    rot = np.zeros(m.shape, dtype=int)
    caixas = []
    for y in range(m.shape[0]):
        for x in range(m.shape[1]):
            if m[y, x] and not rot[y, x]:
                n = len(caixas) + 1
                pilha = [(y, x)]
                rot[y, x] = n
                ys, xs = [y], [x]
                while pilha:
                    cy, cx = pilha.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < m.shape[0] and 0 <= nx < m.shape[1] and m[ny, nx] and not rot[ny, nx]:
                            rot[ny, nx] = n
                            pilha.append((ny, nx))
                            ys.append(ny)
                            xs.append(nx)
                caixas.append((min(ys), min(xs), max(ys) + 1, max(xs) + 1))
    return caixas


def _rasterizar(svg_regiao: Path, png: Path, escala: int) -> Image.Image:
    rc, saida = godot.rodar_script("res://ferramentas/rasterizar_svg.gd",
                                   [f"--svg={svg_regiao}", f"--png={png}", f"--escala={escala}"])
    if rc != 0 or not png.is_file():
        raise SystemExit(f"rasterizar_svg falhou ({rc}): {saida[-600:]}")
    return Image.open(png).convert("RGBA")


def _svg_da_regiao(destino: Path) -> Path:
    texto = SVG.read_text(encoding="utf-8")
    cab = re.search(r"<svg[^>]*>", texto).group(0)
    x, y, w, h = REGIAO
    novo = re.sub(r'width="[^"]*"', f'width="{w}px"', cab)
    novo = re.sub(r'height="[^"]*"', f'height="{h}px"', novo)
    novo = re.sub(r'viewBox="[^"]*"', f'viewBox="{x} {y} {w} {h}"', novo)
    destino.write_text(texto.replace(cab, novo, 1), encoding="utf-8")
    return destino


def _escuro(img: np.ndarray) -> np.ndarray:
    return (img[..., 3] > 40) & (img[..., :3].mean(axis=2) < 140)


def achar_pecas(um: np.ndarray) -> dict[str, tuple[int, int, int, int]]:
    """{nome: caixa a 1x (y0, x0, y1, x1)} pela posicao no overview."""
    escuro = _escuro(um)
    faixa = escuro[:100, :260]
    caixas = _componentes(_dilatar(faixa, 2))
    pecas = {}
    for (ya, yb), nomes in LINHAS:
        da_linha = sorted((c for c in caixas if ya <= (c[0] + c[2]) / 2 < yb), key=lambda c: c[1])
        if len(da_linha) != len(nomes):
            raise SystemExit(f"linha {ya}-{yb}: achei {len(da_linha)} pecas, esperava {len(nomes)}")
        for nome, (y0, x0, y1, x1) in zip(nomes, da_linha):
            # a caixa foi dilatada 2 px: volta ao tamanho real
            pecas[nome] = (y0 + 2, x0 + 2, y1 - 2, x1 - 2)
    x0, y0, x1, y1 = CAIXA_X
    xs = sorted((c for c in _componentes(escuro[y0:y1, x0:x1]) if 10 <= c[2] - c[0] <= 30 and 10 <= c[3] - c[1] <= 30),
                key=lambda c: c[1])
    if len(xs) != 2:
        raise SystemExit(f"olho em X do face_j: achei {len(xs)} componentes, esperava 2")
    c = xs[0]
    pecas["eye_x"] = (c[0] + y0, c[1] + x0, c[2] + y0, c[3] + x0)
    return pecas


def recortar(oito: Image.Image, caixa: tuple[int, int, int, int]) -> Image.Image:
    y0, x0, y1, x1 = caixa
    folga = 2  # px a 1x: pega a borda antisserrilhada inteira
    bruto = oito.crop(((x0 - folga) * ESCALA, (y0 - folga) * ESCALA, (x1 + folga) * ESCALA, (y1 + folga) * ESCALA))
    a = np.array(bruto)
    # so o traco escuro (o branco do fundo nao existe: o SVG e transparente;
    # a guarda e para nao levar a borda de outra peca junto)
    alfa = np.where(a[..., :3].mean(axis=2) < 160, a[..., 3], 0).astype(np.uint8)
    ys, xs = np.nonzero(alfa > 8)
    alfa = alfa[max(0, ys.min() - MARGEM):ys.max() + 1 + MARGEM, max(0, xs.min() - MARGEM):xs.max() + 1 + MARGEM]
    branco = np.full(alfa.shape + (4,), 255, dtype=np.uint8)
    branco[..., 3] = alfa
    return Image.fromarray(branco, "RGBA")


IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[params]

compress/mode=0
mipmaps/generate=true
mipmaps/limit=-1
process/fix_alpha_border=true
process/premult_alpha=false
process/size_limit=0
detect_3d/compress_to=0
"""


def gerar(destino: Path | str = DESTINO, folha: Path | str | None = None) -> dict:
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(PALCO / "_saida")) as tmp:
        tmp = Path(tmp)
        svg = _svg_da_regiao(tmp / "rosto.svg")
        um = np.array(_rasterizar(svg, tmp / "um.png", 1))
        oito = _rasterizar(svg, tmp / "oito.png", ESCALA)
    pecas = achar_pecas(um)
    medidas = {}
    for nome, caixa in pecas.items():
        img = recortar(oito, caixa)
        img.save(destino / f"{nome}.png")
        imp = destino / f"{nome}.png.import"
        if not imp.is_file():
            # mipmaps: a mesma peca vai de ~20 px (bolinha de 88) a ~130 px
            imp.write_text(IMPORT, encoding="utf-8", newline="\n")
        medidas[nome] = {"px": list(img.size), "caixa_1x": [caixa[3] - caixa[1], caixa[2] - caixa[0]]}
        print(f"{nome:18s} {img.size}")
    (destino / "pecas.json").write_text(json.dumps({
        "_comentario": "gerado por main.py palco pecas-do-rosto (builds/palco/rosto_pecas.py); px = tamanho do png (com margem de "
                       f"{MARGEM} px), caixa_1x = a peca no overview.svg sem margem",
        "escala": ESCALA, "margem": MARGEM, "pecas": medidas}, indent=1), encoding="utf-8", newline="\n")
    if folha:
        nomes = list(pecas)
        imagem = Image.new("RGBA", (5 * 300, ((len(nomes) + 4) // 5) * 260), (70, 110, 200, 255))
        d = ImageDraw.Draw(imagem)
        for k, nome in enumerate(nomes):
            img = Image.open(destino / f"{nome}.png")
            escuro = Image.new("RGBA", img.size, (20, 20, 26, 255))
            escuro.putalpha(img.getchannel("A"))
            x, y = (k % 5) * 300 + 20, (k // 5) * 260 + 40
            imagem.paste(escuro, (x, y), escuro)
            d.text((x, y - 28), f"{nome} {img.size}", fill=(255, 255, 255, 255))
        imagem.save(folha)
    return medidas
