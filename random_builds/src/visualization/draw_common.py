"""Shared PIL drawing helpers (fonts, gradients, bars, text)."""
from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont, ImageFilter


def hex_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore


@lru_cache(maxsize=64)
def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except OSError:
            return ImageFont.load_default(size)


def gradient(width: int, height: int, top: str, bottom: str) -> Image.Image:
    top_rgb, bottom_rgb = hex_rgb(top), hex_rgb(bottom)
    base = Image.new("RGB", (1, height))
    px = base.load()
    for y in range(height):
        t = y / max(1, height - 1)
        px[0, y] = tuple(round(a + (b - a) * t) for a, b in zip(top_rgb, bottom_rgb))
    return base.resize((width, height))


def draw_text_center(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str,
                     font: ImageFont.FreeTypeFont, fill, stroke: int = 0,
                     stroke_fill=(0, 0, 0)) -> None:
    draw.text(xy, text, font=font, fill=fill, anchor="mm",
              stroke_width=stroke, stroke_fill=stroke_fill)


def fit_font(text: str, font_path: str, max_width: int, start_size: int) -> ImageFont.FreeTypeFont:
    size = start_size
    while size > 14:
        font = load_font(font_path, size)
        if font.getlength(text) <= max_width:
            return font
        size -= 4
    return load_font(font_path, 14)


def fit_font_wrap(text: str, font_path: str, max_width: int, start_size: int,
                  max_lines: int = 2, min_size: int = 18) -> ImageFont.FreeTypeFont:
    """Como `fit_font`, mas contando com a quebra de linha.

    `fit_font` encolhe ate a frase INTEIRA caber numa linha so, e uma frase de
    seis palavras vira corpo 20 no meio de uma tela 1080x1920. Aqui basta a
    maior PALAVRA caber: quem quebra o resto e o desenho.
    """
    palavras = text.split() or [text]
    maior = max(palavras, key=len)
    size = start_size
    while size > min_size:
        font = load_font(font_path, size)
        if (font.getlength(maior) <= max_width
                and font.getlength(text) <= max_width * max_lines):
            return font
        size -= 3
    return load_font(font_path, min_size)


def stat_bar(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int,
             value: int, color: str, bg=(50, 46, 75)) -> None:
    draw.rounded_rectangle([x, y, x + width, y + height], radius=height // 2, fill=bg)
    filled = max(height, round(width * min(100, max(0, value)) / 100))
    draw.rounded_rectangle([x, y, x + filled, y + height], radius=height // 2,
                           fill=hex_rgb(color))


def glow(image: Image.Image, radius: int = 6) -> Image.Image:
    return image.filter(ImageFilter.GaussianBlur(radius))
