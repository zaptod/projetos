"""CharacterVisualizer: personagem (contrato NF) -> character.png.

Silhueta tintada com a cor oficial do personagem (cor_r/g/b), altura segue
o tamanho rolado, largura segue a forca. Dados SEMPRE antes da imagem.
"""
from __future__ import annotations

from pathlib import Path

from PIL import ImageDraw

from .draw_common import gradient, load_font, fit_font, stat_bar


def render_character_card(personagem: dict, out_path: Path, fonts: dict,
                          size: tuple[int, int] = (1080, 1350)) -> Path:
    width, height = size
    img = gradient(width, height, "#181430", "#241d45")
    draw = ImageDraw.Draw(img)

    tint = (personagem.get("cor_r", 200), personagem.get("cor_g", 120),
            personagem.get("cor_b", 220))
    _silhouette(draw, width * 0.30, height * 0.40,
                personagem.get("tamanho", 1.75), personagem.get("forca", 5.0), tint)

    nome = personagem.get("nome", "???")
    name_font = fit_font(nome, fonts["black"], int(width * 0.52), 76)
    draw.text((width * 0.30, height * 0.76), nome, font=name_font,
              fill=(245, 242, 255), anchor="mm", stroke_width=3,
              stroke_fill=(20, 16, 40))
    sub = f"{personagem.get('tamanho', '?')}m  |  {personagem.get('personalidade', '?')}"
    draw.text((width * 0.30, height * 0.82), sub,
              font=load_font(fonts["regular"], 38), fill=(154, 147, 184), anchor="mm")

    x = int(width * 0.60)
    y = int(height * 0.14)
    label_font = load_font(fonts["bold"], 40)
    draw.text((x, y), "CLASSE", font=label_font, fill=tint, anchor="lm")
    classe_font = fit_font(personagem.get("classe", "?"), fonts["bold"], int(width * 0.36), 44)
    draw.text((x, y + 52), personagem.get("classe", "?"), font=classe_font,
              fill=(245, 242, 255), anchor="lm")

    y += 150
    for key, label, escala in (("forca", "FORCA", 10), ("mana", "MANA", 10)):
        valor = personagem.get(key, 0)
        draw.text((x, y), label, font=label_font, fill=(200, 195, 230), anchor="lm")
        stat_bar(draw, x, y + 28, int(width * 0.30), 24, round(valor * escala),
                 "#%02x%02x%02x" % tint)
        draw.text((x + int(width * 0.30) + 18, y + 40), str(valor),
                  font=label_font, fill=(245, 242, 255), anchor="lm")
        y += 128

    draw.text((x, y + 6), "ARMA", font=label_font, fill=tint, anchor="lm")
    arma_font = fit_font(personagem.get("nome_arma", "?"), fonts["bold"], int(width * 0.36), 40)
    draw.text((x, y + 56), personagem.get("nome_arma", "?"), font=arma_font,
              fill=(245, 242, 255), anchor="lm")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def _silhouette(draw: ImageDraw.ImageDraw, cx: float, cy: float,
                tamanho_m: float, forca: float, tint) -> None:
    scale = 0.7 + (max(1.4, min(2.2, tamanho_m)) - 1.4) / 0.8 * 0.8   # 0.7..1.5
    width_mult = 0.65 + max(0.0, min(1.0, (forca - 3.0) / 6.0)) * 0.8  # 0.65..1.45
    unit = 60 * scale
    torso_w = unit * 1.4 * width_mult

    draw.ellipse([cx - torso_w * 1.6, cy - unit * 3.5, cx + torso_w * 1.6, cy + unit * 3.7],
                 outline=tint, width=6)
    head_r = unit * 0.55
    draw.ellipse([cx - head_r, cy - unit * 3.0, cx + head_r, cy - unit * 3.0 + head_r * 2],
                 fill=tint)
    draw.rounded_rectangle([cx - torso_w / 2, cy - unit * 1.8, cx + torso_w / 2, cy + unit * 0.6],
                           radius=int(unit * 0.4), fill=tint)
    arm_w = unit * 0.38 * width_mult
    for side in (-1, 1):
        x0 = cx + side * (torso_w / 2 + arm_w * 0.2)
        box = sorted([x0, x0 + side * arm_w])
        draw.rounded_rectangle([box[0], cy - unit * 1.7, box[1], cy + unit * 0.5],
                               radius=int(arm_w / 2), fill=tint)
    leg_w = unit * 0.5 * width_mult
    for side in (-1, 1):
        x0 = cx + side * torso_w * 0.22
        draw.rounded_rectangle([x0 - leg_w / 2, cy + unit * 0.6, x0 + leg_w / 2, cy + unit * 2.9],
                               radius=int(leg_w / 2), fill=tint)
