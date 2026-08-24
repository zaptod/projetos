"""WeaponVisualizer: arma (contrato NF) -> weapon.png.

Glifo vetorial por TIPO oficial (Reta, Dupla, Corrente, Arremesso, Arco,
Orbital, Magica, Transformavel), tintado com a cor de raridade que o proprio
gerador do NF atribuiu (r/g/b do registro).
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import ImageDraw

from .draw_common import gradient, load_font, fit_font, stat_bar

RARIDADE_COR = {
    "Comum": "#9a9a9a", "Incomum": "#50c850", "Raro": "#4682e6",
    "Épico": "#a03cdc", "Lendário": "#ff9632", "Mítico": "#ff3296",
}


def render_weapon_card(arma: dict, out_path: Path, fonts: dict,
                       size: tuple[int, int] = (1080, 1350)) -> Path:
    width, height = size
    img = gradient(width, height, "#1f1408", "#332012")
    draw = ImageDraw.Draw(img)

    tint = (arma.get("r", 180), arma.get("g", 180), arma.get("b", 180))
    raridade = arma.get("raridade", "Comum")
    raridade_cor = RARIDADE_COR.get(raridade, "#9a9a9a")

    _glyph(draw, arma.get("tipo", "Reta"), width * 0.30, height * 0.40,
           340.0, tint)

    draw.text((width * 0.30, height * 0.10), raridade.upper(),
              font=load_font(fonts["black"], 52), fill=raridade_cor, anchor="mm",
              stroke_width=2, stroke_fill=(30, 18, 8))

    nome = arma.get("nome", "???")
    name_font = fit_font(nome, fonts["black"], int(width * 0.9), 62)
    draw.text((width / 2, height * 0.76), nome, font=name_font,
              fill=(255, 248, 235), anchor="mm", stroke_width=3, stroke_fill=(30, 18, 8))
    sub = f"{arma.get('tipo', '?')}  |  {arma.get('estilo', '?')}  |  {arma.get('peso', '?')}kg"
    draw.text((width / 2, height * 0.82), sub,
              font=load_font(fonts["regular"], 38), fill=(190, 165, 135), anchor="mm")

    x = int(width * 0.58)
    y = int(height * 0.16)
    label_font = load_font(fonts["bold"], 38)
    barras = (
        ("dano", "DANO", arma.get("dano", 0), 34.0),
        ("critico", "CRITICO", arma.get("critico", 0), 7.0),
        ("velocidade_ataque", "VELOCIDADE", arma.get("velocidade_ataque", 0), 1.2),
    )
    for _, label, valor, maximo in barras:
        draw.text((x, y), label, font=label_font, fill=(230, 215, 190), anchor="lm")
        stat_bar(draw, x, y + 26, int(width * 0.28), 22,
                 round(valor / maximo * 100), raridade_cor)
        draw.text((x + int(width * 0.28) + 16, y + 36), str(valor),
                  font=label_font, fill=(255, 248, 235), anchor="lm")
        y += 116

    enc = (arma.get("encantamentos") or ["Nenhum"])[0]
    draw.text((x, y + 4), "ENCANTAMENTO", font=load_font(fonts["bold"], 34),
              fill=raridade_cor, anchor="lm")
    draw.text((x, y + 48), enc, font=load_font(fonts["bold"], 40),
              fill=(255, 248, 235), anchor="lm")
    y += 110
    draw.text((x, y), "HABILIDADE", font=load_font(fonts["bold"], 34),
              fill=raridade_cor, anchor="lm")
    hab_font = fit_font(arma.get("habilidade", "Nenhuma"), fonts["bold"], int(width * 0.38), 40)
    draw.text((x, y + 44), arma.get("habilidade", "Nenhuma"), font=hab_font,
              fill=(255, 248, 235), anchor="lm")

    passiva = (arma.get("passiva") or {}).get("nome")
    rodape = f"PASSIVA: {passiva}" if passiva else "SEM PASSIVA"
    draw.text((width / 2, height * 0.93), rodape,
              font=load_font(fonts["regular"], 36), fill=(255, 190, 140), anchor="mm")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def _glyph(draw: ImageDraw.ImageDraw, tipo: str, cx: float, cy: float,
           unit: float, tint) -> None:
    handle = (90, 62, 40)
    draw.ellipse([cx - unit * 0.75, cy - unit * 0.75, cx + unit * 0.75, cy + unit * 0.75],
                 outline=tint, width=8)

    if tipo == "Reta":
        blade_w = unit * 0.13
        draw.polygon([(cx - blade_w, cy + unit * 0.15), (cx - blade_w, cy - unit * 0.55),
                      (cx, cy - unit * 0.75), (cx + blade_w, cy - unit * 0.55),
                      (cx + blade_w, cy + unit * 0.15)], fill=tint)
        draw.rectangle([cx - unit * 0.22, cy + unit * 0.15, cx + unit * 0.22, cy + unit * 0.21],
                       fill=handle)
        draw.rectangle([cx - unit * 0.045, cy + unit * 0.21, cx + unit * 0.045, cy + unit * 0.55],
                       fill=handle)
    elif tipo == "Dupla":
        for side in (-1, 1):
            bx = cx + side * unit * 0.28
            blade_w = unit * 0.09
            draw.polygon([(bx - blade_w, cy + unit * 0.1), (bx - blade_w, cy - unit * 0.35),
                          (bx, cy - unit * 0.55), (bx + blade_w, cy - unit * 0.35),
                          (bx + blade_w, cy + unit * 0.1)], fill=tint)
            draw.rectangle([bx - unit * 0.03, cy + unit * 0.1, bx + unit * 0.03, cy + unit * 0.4],
                           fill=handle)
    elif tipo == "Corrente":
        points = []
        for i in range(9):
            t = i / 8
            points.append((cx - unit * 0.5 + t * unit, cy + math.sin(t * math.pi * 2) * unit * 0.22))
        draw.line(points, fill=tint, width=int(unit * 0.06), joint="curve")
        draw.ellipse([points[-1][0] - unit * 0.14, points[-1][1] - unit * 0.14,
                      points[-1][0] + unit * 0.14, points[-1][1] + unit * 0.14], fill=tint)
    elif tipo == "Arremesso":
        for k in range(4):
            ang = math.radians(90 * k + 45)
            tip = (cx + math.cos(ang) * unit * 0.5, cy + math.sin(ang) * unit * 0.5)
            base1 = (cx + math.cos(ang + 0.5) * unit * 0.12, cy + math.sin(ang + 0.5) * unit * 0.12)
            base2 = (cx + math.cos(ang - 0.5) * unit * 0.12, cy + math.sin(ang - 0.5) * unit * 0.12)
            draw.polygon([tip, base1, base2], fill=tint)
        draw.ellipse([cx - unit * 0.1, cy - unit * 0.1, cx + unit * 0.1, cy + unit * 0.1],
                     fill=handle)
    elif tipo == "Arco":
        draw.arc([cx - unit * 0.45, cy - unit * 0.7, cx + unit * 0.5, cy + unit * 0.7],
                 start=285, end=75, fill=tint, width=int(unit * 0.06))
        draw.line([cx + unit * 0.07, cy - unit * 0.67, cx + unit * 0.07, cy + unit * 0.67],
                  fill=(220, 220, 220), width=4)
        draw.line([cx - unit * 0.45, cy, cx + unit * 0.35, cy], fill=handle, width=6)
    elif tipo == "Orbital":
        for k in range(4):
            ang = math.radians(90 * k)
            ox = cx + math.cos(ang) * unit * 0.45
            oy = cy + math.sin(ang) * unit * 0.45
            draw.ellipse([ox - unit * 0.12, oy - unit * 0.12, ox + unit * 0.12, oy + unit * 0.12],
                         fill=tint)
        draw.ellipse([cx - unit * 0.16, cy - unit * 0.16, cx + unit * 0.16, cy + unit * 0.16],
                     outline=tint, width=6)
    elif tipo == "Mágica":
        draw.rectangle([cx - unit * 0.035, cy - unit * 0.5, cx + unit * 0.035, cy + unit * 0.6],
                       fill=handle)
        draw.ellipse([cx - unit * 0.16, cy - unit * 0.8, cx + unit * 0.16, cy - unit * 0.48],
                     fill=tint)
        for k in range(3):
            ang = math.radians(120 * k - 90)
            sx = cx + math.cos(ang) * unit * 0.32
            sy = cy - unit * 0.62 + math.sin(ang) * unit * 0.28
            draw.ellipse([sx - unit * 0.05, sy - unit * 0.05, sx + unit * 0.05, sy + unit * 0.05],
                         fill=tint)
    elif tipo == "Transformável":
        blade_w = unit * 0.11
        draw.polygon([(cx - unit * 0.5, cy + unit * 0.45), (cx - unit * 0.5 - blade_w, cy + unit * 0.2),
                      (cx - unit * 0.15, cy - unit * 0.45), (cx, cy - unit * 0.3)], fill=tint)
        draw.polygon([(cx + unit * 0.5, cy + unit * 0.45), (cx + unit * 0.5 + blade_w, cy + unit * 0.2),
                      (cx + unit * 0.15, cy - unit * 0.45), (cx, cy - unit * 0.3)], fill=tint)
        draw.ellipse([cx - unit * 0.1, cy + unit * 0.3, cx + unit * 0.1, cy + unit * 0.5],
                     fill=handle)
    else:
        draw.ellipse([cx - unit * 0.3, cy - unit * 0.3, cx + unit * 0.3, cy + unit * 0.3],
                     fill=tint)
