"""Tema visual compartilhado do launcher Neural Fights."""

import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

# ============================================================================
# CORES DO TEMA PRINCIPAL
# ============================================================================
COR_BG = "#10111d"
COR_BG_SECUNDARIO = "#1b1d31"
COR_HEADER = "#24233d"
COR_ACCENT = "#ff4568"
COR_SUCCESS = "#35d9ff"
COR_TEXTO = "#ffffff"
COR_TEXTO_DIM = "#a9acc6"
COR_WARNING = "#ffbd3d"
COR_DANGER = "#ff526c"
COR_BORDA = "#080911"
COR_CARD = "#20233b"
FONTE_TITULO = ("Bahnschrift SemiBold", 20)
FONTE_DESTAQUE = ("Segoe UI Semibold", 11)

# ============================================================================
# CORES DAS RARIDADES
# ============================================================================
# Passe 2 (arte): fonte única em RGB vive em utils/palette.py; o tema
# Tkinter consome a MESMA verdade convertida para hex.
from neural_fights.utils.palette import (
    CORES_CLASSE as _CORES_CLASSE_RGB,
    CORES_RARIDADE as _CORES_RARIDADE_RGB,
    rgb_to_hex,
)

CORES_RARIDADE = {k: rgb_to_hex(v) for k, v in _CORES_RARIDADE_RGB.items()}

# ============================================================================
# CORES DAS CLASSES POR CATEGORIA
# ============================================================================
CORES_CLASSE = {k: rgb_to_hex(v) for k, v in _CORES_CLASSE_RGB.items()}


# Cores específicas para a tela de luta
COR_P1 = "#3498db"
COR_P2 = "#e94560"


class BotaoCanvas(tk.Canvas):
    """Botao leve com borda grossa e hover, sem depender de imagens."""

    def __init__(self, parent, text, command=None, cor=COR_ACCENT,
                 width=210, height=42, font=FONTE_DESTAQUE, **kwargs):
        super().__init__(parent, width=width, height=height, bg=kwargs.pop("bg", COR_BG),
                         highlightthickness=0, bd=0, cursor="hand2", **kwargs)
        self._text = text
        self._command = command
        self._cor = cor
        self._ativo = True
        self._font = font
        self.bind("<Configure>", lambda _event: self._desenhar())
        self.bind("<Enter>", lambda _event: self._desenhar(hover=True))
        self.bind("<Leave>", lambda _event: self._desenhar())
        self.bind("<Button-1>", self._clicar)
        self.after_idle(self._desenhar)

    def _desenhar(self, hover=False):
        self.delete("all")
        largura, altura = max(self.winfo_width(), 2), max(self.winfo_height(), 2)
        cor = self._cor if self._ativo else COR_TEXTO_DIM
        if hover and self._ativo:
            cor = COR_SUCCESS
        raio = min(12, altura // 2)
        pontos = (raio, 1, largura - raio, 1, largura - 1, raio,
                  largura - 1, altura - raio, largura - raio, altura - 1,
                  raio, altura - 1, 1, altura - raio, 1, raio)
        self.create_polygon(pontos, fill=cor, outline=COR_BORDA, width=3, smooth=True)
        self.create_text(largura // 2, altura // 2, text=self._text, font=self._font,
                         fill=COR_TEXTO if self._ativo else COR_BORDA)

    def _clicar(self, _event):
        if self._ativo and self._command:
            self._command()

    def configurar(self, *, ativo=None, texto=None, cor=None):
        if ativo is not None:
            self._ativo = ativo
            self.configure(cursor="hand2" if ativo else "arrow")
        if texto is not None:
            self._text = texto
        if cor is not None:
            self._cor = cor
        self._desenhar()


class CartaoMenu(tk.Canvas):
    """Cartao grande rasterizado em 2x para o menu nao ficar serrilhado."""

    def __init__(self, parent, icone, titulo, descricao, command, cor=COR_ACCENT):
        super().__init__(parent, height=112, bg=COR_BG, highlightthickness=0, bd=0,
                         cursor="hand2")
        self._icone, self._titulo, self._descricao = icone, titulo, descricao
        self._command, self._cor, self._foto = command, cor, None
        self.bind("<Configure>", lambda _event: self._desenhar())
        self.bind("<Enter>", lambda _event: self._desenhar(hover=True))
        self.bind("<Leave>", lambda _event: self._desenhar())
        self.bind("<Button-1>", lambda _event: self._command())
        self.after_idle(self._desenhar)

    def _desenhar(self, hover=False):
        largura, altura = max(self.winfo_width(), 80), max(self.winfo_height(), 80)
        escala = 2
        imagem = Image.new("RGBA", (largura * escala, altura * escala), (0, 0, 0, 0))
        desenho = ImageDraw.Draw(imagem)
        cor = COR_SUCCESS if hover else self._cor
        caixa = (4 * escala, 4 * escala, (largura - 4) * escala, (altura - 4) * escala)
        desenho.rounded_rectangle(caixa, radius=18 * escala, fill=cor, outline=COR_BORDA,
                                  width=4 * escala)
        imagem = imagem.resize((largura, altura), Image.Resampling.LANCZOS)
        self._foto = ImageTk.PhotoImage(imagem)
        self.delete("all")
        self.create_image(0, 0, image=self._foto, anchor="nw")
        self.create_text(37, altura // 2, text=self._icone, font=("Segoe UI Emoji", 24),
                         fill=COR_TEXTO)
        self.create_text(70, altura // 2 - 16, text=self._titulo,
                         font=("Bahnschrift SemiBold", 15), fill=COR_TEXTO, anchor="w")
        self.create_text(70, altura // 2 + 16, text=self._descricao,
                         font=("Segoe UI", 9), fill=COR_BORDA, anchor="w")


def criar_titulo(canvas, texto, largura=None):
    """Titulo cel-shading com sombra e contorno, usado no menu principal."""
    largura = largura or max(canvas.winfo_width(), 400)
    centro = largura // 2
    fonte = ("Bahnschrift SemiBold", 39)
    canvas.create_text(centro + 6, 46, text=texto, font=fonte, fill="#05050a")
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2)):
        canvas.create_text(centro + dx, 40 + dy, text=texto, font=fonte, fill=COR_BORDA)
    canvas.create_text(centro, 40, text=texto, font=fonte, fill=COR_ACCENT)
    canvas.create_text(centro, 38, text=texto, font=fonte, fill="#ff6682")


def desenhar_lutador(canvas, personagem, arma=None, cor_borda=COR_BORDA,
                     centro=None, escala=1.0):
    """Preview cel-shaded em alta resolucao, reduzido para o Canvas."""
    canvas.delete("all")
    largura = max(canvas.winfo_width(), int(canvas.cget("width") or 200))
    altura = max(canvas.winfo_height(), int(canvas.cget("height") or 200))
    cx, cy = centro or (largura // 2, altura // 2 - 4)
    if personagem is None:
        return
    r = max(0, min(255, int(getattr(personagem, "cor_r", 180))))
    g = max(0, min(255, int(getattr(personagem, "cor_g", 80))))
    b = max(0, min(255, int(getattr(personagem, "cor_b", 80))))
    classe = str(getattr(personagem, "classe", ""))
    corpo = CORES_CLASSE.get(classe)
    if corpo is None:
        corpo = next((cor for nome, cor in CORES_CLASSE.items()
                      if classe and nome.startswith(classe.split(" ")[0])), None)
    corpo = corpo or f"#{r:02x}{g:02x}{b:02x}"
    raio = max(24, min(52, int((getattr(personagem, "tamanho", 1.7) * 23) * escala)))
    if not hasattr(canvas, "tk"):
        return _desenhar_lutador_teste(canvas, personagem, arma, cor_borda, cx, cy, raio, corpo)
    fator = 2
    tamanho = int((raio * 2 + 74) * fator)
    imagem = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    meio = tamanho // 2
    raio_px = raio * fator
    def cor_escura(valor, proporcao=.62):
        valor = valor.lstrip("#")
        return tuple(int(int(valor[i:i + 2], 16) * proporcao) for i in (0, 2, 4))
    corpo_rgb = tuple(int(corpo[i:i + 2], 16) for i in (1, 3, 5))
    caixa = (meio - raio_px, meio - raio_px, meio + raio_px, meio + raio_px)
    desenho.ellipse((caixa[0] - 6, caixa[1] - 6, caixa[2] + 6, caixa[3] + 6), fill=COR_BORDA)
    desenho.ellipse(caixa, fill=corpo_rgb)
    mascara = Image.new("L", (tamanho, tamanho), 0)
    ImageDraw.Draw(mascara).ellipse(caixa, fill=255)
    sombra = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).ellipse((caixa[0], meio - raio_px // 8, caixa[2], caixa[3] + raio_px // 2),
                                   fill=cor_escura(corpo) + (190,))
    imagem.alpha_composite(Image.composite(sombra, Image.new("RGBA", (tamanho, tamanho)), mascara))
    desenho = ImageDraw.Draw(imagem)
    desenho.ellipse((meio - raio_px * .58, meio - raio_px * .7,
                     meio - raio_px * .05, meio - raio_px * .18), fill=(255, 255, 255, 95))
    olho_x, olho_y, olho_r = meio + raio_px * .23, meio - raio_px * .18, max(8, raio_px * .15)
    for deslocamento in (-raio_px * .24, raio_px * .24):
        caixa_olho = (olho_x - olho_r, olho_y + deslocamento - olho_r,
                      olho_x + olho_r, olho_y + deslocamento + olho_r)
        desenho.ellipse(caixa_olho, fill=COR_TEXTO, outline=COR_BORDA, width=3)
        desenho.ellipse((olho_x, olho_y + deslocamento - olho_r * .5,
                         olho_x + olho_r, olho_y + deslocamento + olho_r * .5), fill=COR_BORDA)
    desenho.line((olho_x - olho_r, olho_y - raio_px * .36, olho_x + olho_r,
                  olho_y - raio_px * .43), fill=COR_BORDA, width=3)
    if arma is not None:
        _pintar_arma(desenho, arma, meio, meio, raio_px)
    imagem = imagem.resize((tamanho // fator, tamanho // fator), Image.Resampling.LANCZOS)
    foto = ImageTk.PhotoImage(imagem)
    canvas._foto_lutador = foto
    canvas.create_image(cx, cy, image=foto, tags="lutador")


def _pintar_arma(desenho, arma, meio, meio_y, raio):
    """Pinta cabo e laminas com contorno em escala alta."""
    ar, ag, ab = (int(getattr(arma, chave, 180)) for chave in ("r", "g", "b"))
    cor = (ar, ag, ab, 255)
    comprimento = max(58, min(120, int(getattr(arma, "comp_lamina", 70) * 1.1)))
    def lamina(sinal=1, deslocamento=0):
        inicio = (meio + sinal * (raio - 7), meio_y + deslocamento)
        fim = (inicio[0] + sinal * comprimento, inicio[1] - 30)
        cabo = (inicio[0] - sinal * 38, inicio[1] + 17)
        desenho.line((cabo, inicio), fill=COR_BORDA, width=15)
        desenho.line((cabo, inicio), fill=(117, 66, 29, 255), width=7)
        desenho.line((inicio, fim), fill=COR_BORDA, width=19)
        desenho.line((inicio, fim), fill=cor, width=11)
        desenho.line((inicio, fim), fill=(255, 255, 255, 130), width=2)
    if "Dupla" in str(getattr(arma, "tipo", "Reta")):
        lamina(1, -raio * .32)
        lamina(-1, raio * .32)
    else:
        lamina()


def _desenhar_lutador_teste(canvas, personagem, arma, cor_borda, cx, cy, raio, corpo):
    """Fallback sem Tk para os dublês de Canvas nos testes."""
    canvas.create_oval(cx - raio - 8, cy - raio - 8, cx + raio + 8, cy + raio + 8,
                       outline=COR_SUCCESS, width=2, dash=(4, 3))
    canvas.create_oval(cx - raio, cy - raio, cx + raio, cy + raio,
                       fill=corpo, outline=cor_borda, width=5, tags="corpo")
    # Olhos apontados para a direita, como a pose neutra do palco.
    olho_x, olho_y, olho_r = cx + raio * .25, cy - raio * .18, max(4, raio * .14)
    for dy in (-raio * .24, raio * .24):
        canvas.create_oval(olho_x - olho_r, olho_y + dy - olho_r,
                           olho_x + olho_r, olho_y + dy + olho_r,
                           fill=COR_TEXTO, outline=cor_borda, width=1, tags="rosto")
        canvas.create_oval(olho_x, olho_y + dy - olho_r / 2,
                           olho_x + olho_r, olho_y + dy + olho_r / 2,
                           fill=COR_BORDA, outline="", tags="rosto")
    if arma is None:
        return
    ar, ag, ab = (int(getattr(arma, chave, 180)) for chave in ("r", "g", "b"))
    cor_arma = f"#{ar:02x}{ag:02x}{ab:02x}"
    tipo = str(getattr(arma, "tipo", "Reta"))
    comprimento = max(26, min(58, int(getattr(arma, "comp_lamina", 70) * .55)))

    def lamina(sinal=1, y=0):
        inicio_x, inicio_y = cx + sinal * (raio - 4), cy + y
        fim_x, fim_y = inicio_x + sinal * comprimento, inicio_y - 15
        cabo_x, cabo_y = inicio_x - sinal * 18, inicio_y + 8
        canvas.create_line(cabo_x, cabo_y, inicio_x, inicio_y, fill=COR_BORDA, width=7, tags="arma")
        canvas.create_line(cabo_x, cabo_y, inicio_x, inicio_y, fill="#75421d", width=3, tags="arma")
        canvas.create_line(inicio_x, inicio_y, fim_x, fim_y, fill=COR_BORDA, width=9, tags="lamina")
        canvas.create_line(inicio_x, inicio_y, fim_x, fim_y, fill=cor_arma, width=5, tags="lamina")

    if "Dupla" in tipo:
        lamina(1, -raio * .32)
        lamina(-1, raio * .32)
    else:
        lamina()

# ============================================================================
# CATEGORIAS DE CLASSES
# ============================================================================
CATEGORIAS_CLASSE = {
    "⚔️ Físicos": ["Guerreiro (Força Bruta)", "Berserker (Fúria)", "Gladiador (Combate)", "Cavaleiro (Defesa)"],
    "🗡️ Ágeis": ["Assassino (Crítico)", "Ladino (Evasão)", "Ninja (Velocidade)", "Duelista (Precisão)"],
    "✨ Mágicos": ["Mago (Arcano)", "Piromante (Fogo)", "Criomante (Gelo)", "Necromante (Trevas)"],
    "⚡ Híbridos": ["Paladino (Sagrado)", "Druida (Natureza)", "Feiticeiro (Caos)", "Monge (Chi)"],
}

__all__ = [
    'COR_BG', 'COR_BG_SECUNDARIO', 'COR_HEADER', 'COR_ACCENT',
    'COR_SUCCESS', 'COR_TEXTO', 'COR_TEXTO_DIM', 'COR_WARNING', 'COR_DANGER',
    'COR_BORDA', 'COR_CARD', 'FONTE_TITULO', 'FONTE_DESTAQUE', 'BotaoCanvas', 'CartaoMenu',
    'criar_titulo', 'desenhar_lutador', 'CORES_RARIDADE', 'CORES_CLASSE',
    'COR_P1', 'COR_P2', 'CATEGORIAS_CLASSE',
]
