"""Tema visual compartilhado do launcher Neural Fights."""

import math
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
    """Cartao grande rasterizado com cor propria para o menu."""

    def __init__(self, parent, icone, titulo, descricao, command, cor=COR_ACCENT,
                 destaque=False):
        super().__init__(parent, height=112, bg=COR_BG, highlightthickness=0, bd=0,
                         cursor="hand2")
        self._icone, self._titulo, self._descricao = icone, titulo, descricao
        self._command, self._cor, self._destaque, self._foto = command, cor, destaque, None
        self.bind("<Configure>", lambda _event: self._desenhar())
        self.bind("<Enter>", lambda _event: self._desenhar(hover=True))
        self.bind("<Leave>", lambda _event: self._desenhar())
        self.bind("<Button-1>", lambda _event: self._command())
        self.after_idle(self._desenhar)

    def _desenhar(self, hover=False):
        largura, altura = max(self.winfo_width(), 80), max(self.winfo_height(), 80)
        escala = 4
        imagem = Image.new("RGBA", (largura * escala, altura * escala), (0, 0, 0, 0))
        desenho = ImageDraw.Draw(imagem)
        cor = COR_SUCCESS if hover else self._cor
        caixa = (4 * escala, 4 * escala, (largura - 4) * escala, (altura - 4) * escala)
        rgb = tuple(int(cor[indice:indice + 2], 16) for indice in (1, 3, 5))
        escura = tuple(max(0, int(componente * .25)) for componente in rgb)
        raio = 18 * escala
        for y in range(caixa[1], caixa[3] + 1):
            fracao = (y - caixa[1]) / max(1, caixa[3] - caixa[1])
            faixa = tuple(int(escura[i] * (1 - fracao) + rgb[i] * fracao)
                          for i in range(3))
            distancia = min(y - caixa[1], caixa[3] - y)
            recuo = 0 if distancia >= raio else raio - int((raio ** 2 - (raio - distancia) ** 2) ** .5)
            desenho.line((caixa[0] + recuo, y, caixa[2] - recuo, y), fill=faixa)
        borda = "#f6c95b" if self._destaque else COR_BORDA
        desenho.rounded_rectangle(caixa, radius=raio, outline=borda,
                                  width=(5 if self._destaque else 4) * escala)
        imagem = imagem.resize((largura, altura), Image.Resampling.LANCZOS)
        self._foto = ImageTk.PhotoImage(imagem)
        self.delete("all")
        self.create_image(0, 0, image=self._foto, anchor="nw")
        self.create_text(39, altura // 2, text=self._icone, font=("Segoe UI Emoji", 31),
                         fill=COR_TEXTO)
        self.create_text(70, altura // 2 - 16, text=self._titulo,
                         font=("Bahnschrift SemiBold", 15), fill=COR_TEXTO, anchor="w")
        self.create_text(70, altura // 2 + 16, text=self._descricao,
                         font=("Segoe UI", 9), fill="#eef0ff", anchor="w")


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
    """Preview do lutador na mesma linguagem visual do palco Godot."""
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
    tamanho_personagem = float(getattr(personagem, "tamanho", 1.7))
    ajuste_tamanho = max(-.03, min(.03, (tamanho_personagem - 1.7) * .02))
    raio = max(24, int(min(largura, altura) * (.30 + ajuste_tamanho) * escala))
    if not hasattr(canvas, "tk"):
        return _desenhar_lutador_teste(canvas, personagem, arma, cor_borda, cx, cy, raio, corpo)
    imagem = _renderizar_preview_lutador(personagem, arma, corpo, raio)
    foto = ImageTk.PhotoImage(imagem)
    canvas._foto_lutador = foto
    canvas.create_image(cx, cy, image=foto, tags="lutador")


def _renderizar_preview_lutador(personagem, arma, corpo, raio):
    """Rasteriza em 4x para manter contorno, cel e arma nitidos."""
    fator = 4
    raio *= fator
    tamanho = int(raio * 8)
    meio = tamanho // 2
    imagem = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    corpo_rgb = tuple(int(corpo[i:i + 2], 16) for i in (1, 3, 5))
    sombra = tuple(int(valor * .72) for valor in corpo_rgb)
    contorno = max(3, int(raio * .08))
    caixa = (meio - raio, meio - raio, meio + raio, meio + raio)
    desenho.ellipse((caixa[0] - contorno, caixa[1] - contorno,
                     caixa[2] + contorno, caixa[3] + contorno), fill=COR_BORDA)
    desenho.ellipse(caixa, fill=sombra)
    mascara = Image.new("L", (tamanho, tamanho), 0)
    mascara_desenho = ImageDraw.Draw(mascara)
    mascara_desenho.ellipse(caixa, fill=255)
    mascara_desenho.rectangle((0, meio + 1, tamanho, tamanho), fill=0)
    base = Image.new("RGBA", (tamanho, tamanho), corpo_rgb + (255,))
    base.putalpha(mascara)
    imagem.alpha_composite(base)
    desenho = ImageDraw.Draw(imagem)
    desenho.ellipse((meio - raio * .58, meio - raio * .70, meio - raio * .27,
                     meio - raio * .39), fill=(255, 255, 255, 175))
    _pintar_rosto(desenho, personagem, meio, raio)
    if arma is not None:
        _pintar_arma(desenho, arma, meio, meio, raio)
    return imagem.resize((tamanho // fator, tamanho // fator), Image.Resampling.LANCZOS)


def _pintar_rosto(desenho, personagem, meio, raio):
    """Olhos e expressoes neutras do rosto do palco, voltados para a arma."""
    classe = str(getattr(personagem, "classe", ""))
    expressao = next((nome for chave, nome in {
        "Berserker": "furia", "Gladiador": "determinado", "Cavaleiro": "firmeza",
        "Assassino": "focado", "Ladino": "confiante", "Ninja": "concentrado",
        "Duelista": "animado", "Mago": "alerta", "Piromante": "furia",
        "Criomante": "glacial", "Necromante": "tedio", "Paladino": "determinado",
        "Druida": "animado", "Feiticeiro": "extase", "Monge": "firmeza",
    }.items() if chave in classe), "neutro")
    olho_r = max(6, int(raio * .19))
    olho_x = meio + int(raio * .20)
    olhos = [(olho_x, meio - int(raio * .35)), (olho_x, meio + int(raio * .35))]
    for x, y in olhos:
        desenho.ellipse((x - olho_r - 2, y - olho_r - 2, x + olho_r + 2, y + olho_r + 2),
                        fill=COR_BORDA)
        desenho.ellipse((x - olho_r, y - olho_r, x + olho_r, y + olho_r), fill=(250, 250, 252))
        pupila = int(olho_r * .48)
        desenho.ellipse((x + int(olho_r * .22) - pupila, y - pupila,
                         x + int(olho_r * .22) + pupila, y + pupila), fill=COR_BORDA)
    espessura = max(3, int(raio * .075))
    if expressao in {"furia", "determinado", "focado", "firmeza"}:
        desenho.line((olho_x - olho_r, olhos[0][1] - olho_r * 1.25,
                      olho_x + olho_r, olhos[0][1] - olho_r * .65), fill=COR_BORDA,
                     width=espessura)
        desenho.line((olho_x - olho_r, olhos[1][1] - olho_r * .65,
                      olho_x + olho_r, olhos[1][1] - olho_r * 1.25), fill=COR_BORDA,
                     width=espessura)
    elif expressao in {"confiante", "glacial", "tedio", "concentrado"}:
        desenho.line((olho_x - olho_r, olhos[0][1] - olho_r * .65,
                      olho_x + olho_r, olhos[0][1] - olho_r * .65), fill=COR_BORDA,
                     width=espessura)
    boca_x = meio + int(raio * .57)
    if expressao in {"animado", "confiante", "berserk"}:
        desenho.arc((boca_x - olho_r, meio - olho_r, boca_x + olho_r, meio + olho_r),
                    25, 135, fill=COR_BORDA, width=espessura)
    else:
        desenho.line((boca_x - olho_r * .65, meio, boca_x + olho_r * .65, meio),
                     fill=COR_BORDA, width=espessura)


def _pintar_arma(desenho, arma, meio, meio_y, raio):
    """Pinta a silhueta dos oito tipos de arma da peca padrao do palco."""
    ar, ag, ab = (int(getattr(arma, chave, 180)) for chave in ("r", "g", "b"))
    cor = (ar, ag, ab, 255)
    metal = tuple(int(200 * .7 + valor * .3) for valor in cor[:3]) + (255,)
    largura = max(6, int(raio * .10))
    comprimento = int(raio * .55)
    tipo = str(getattr(arma, "tipo", "Reta")).lower()

    def poligono(pontos, preenchimento):
        desenho.polygon(pontos, fill=preenchimento)
        desenho.line(pontos + [pontos[0]], fill=COR_BORDA, width=max(3, largura // 2), joint="curve")

    def lamina(sinal=1, deslocamento=0, curta=False):
        inicio = (meio + sinal * int(raio * .88), meio_y + int(deslocamento))
        fim = (inicio[0] + sinal * (int(comprimento * (.62 if curta else 1))),
               inicio[1] - int(raio * .32))
        cabo = (inicio[0] - sinal * int(raio * .55), inicio[1] + int(raio * .18))
        desenho.line((cabo, inicio), fill=COR_BORDA, width=largura * 2)
        desenho.line((cabo, inicio), fill=(112, 80, 46, 255), width=largura)
        desenho.line((inicio[0], inicio[1] - largura * 1.5, inicio[0], inicio[1] + largura * 1.5),
                     fill=COR_BORDA, width=largura * 2)
        desenho.line((inicio[0], inicio[1] - largura * 1.5, inicio[0], inicio[1] + largura * 1.5),
                     fill=cor, width=max(3, largura))
        perpendicular = largura * .85
        poligono([(inicio[0], inicio[1] - perpendicular),
                  (fim[0] - sinal * largura * 2, fim[1] - perpendicular), fim,
                  (fim[0] - sinal * largura * 2, fim[1] + perpendicular),
                  (inicio[0], inicio[1] + perpendicular)], metal)
        desenho.line((inicio, fim), fill=(255, 255, 255, 180), width=max(2, largura // 4))

    if "dupla" in tipo:
        lamina(1, -raio * .31)
        lamina(-1, raio * .31)
    elif "corrente" in tipo:
        cabo = (meio + int(raio * .48), meio_y + int(raio * .16))
        inicio = (meio + int(raio * .9), meio_y)
        fim = (inicio[0] + comprimento, inicio[1] - int(raio * .18))
        desenho.line((cabo, inicio), fill=COR_BORDA, width=largura * 2)
        desenho.line((cabo, inicio), fill=(112, 80, 46, 255), width=largura)
        desenho.line((inicio, fim), fill=COR_BORDA, width=max(3, largura // 2))
        for indice in range(5):
            x = int(inicio[0] + (fim[0] - inicio[0]) * (indice + .5) / 5)
            y = int(inicio[1] + (fim[1] - inicio[1]) * (indice + .5) / 5)
            desenho.ellipse((x - largura, y - largura, x + largura, y + largura),
                            outline=COR_BORDA, width=max(2, largura // 3))
        desenho.ellipse((fim[0] - largura * 2, fim[1] - largura * 2,
                         fim[0] + largura * 2, fim[1] + largura * 2), fill=metal,
                        outline=COR_BORDA, width=max(3, largura // 2))
    elif "arco" in tipo:
        cabo = (meio + int(raio * .48), meio_y)
        x = meio + int(raio * .92)
        desenho.line((cabo, (x, meio_y)), fill=COR_BORDA, width=largura * 2)
        desenho.line((cabo, (x, meio_y)), fill=(112, 80, 46, 255), width=largura)
        caixa = (x, meio_y - int(raio * .95), x + comprimento, meio_y + int(raio * .95))
        desenho.arc(caixa, 105, 255, fill=COR_BORDA, width=largura * 2)
        desenho.arc(caixa, 105, 255, fill=(112, 80, 46, 255), width=largura)
        corda_x = x + int(comprimento * .16)
        desenho.line((corda_x, meio_y - int(raio * .88), corda_x, meio_y + int(raio * .88)),
                     fill=(235, 235, 242), width=2)
        desenho.line((corda_x, meio_y, x + comprimento + largura, meio_y), fill=COR_BORDA, width=largura)
        desenho.line((corda_x, meio_y, x + comprimento + largura, meio_y), fill=metal, width=max(2, largura // 2))
    elif "arremesso" in tipo:
        lamina(curta=True)
    elif "orbital" in tipo:
        cabo = (meio + int(raio * .48), meio_y)
        base = (meio + int(raio * .92), meio_y)
        desenho.line((cabo, base), fill=COR_BORDA, width=largura * 2)
        desenho.line((cabo, base), fill=(112, 80, 46, 255), width=largura)
        for angulo in (-.65, 0, .65):
            x = base[0] + int(comprimento * .38 * math.cos(angulo))
            y = base[1] + int(comprimento * .38 * math.sin(angulo))
            desenho.line((base, (x, y)), fill=COR_BORDA, width=max(3, largura // 2))
            desenho.ellipse((x - largura * 2, y - largura * 2, x + largura * 2, y + largura * 2),
                            fill=metal, outline=COR_BORDA, width=max(3, largura // 2))
    elif "mágica" in tipo or "magica" in tipo:
        cabo = (meio + int(raio * .48), meio_y)
        x, y = meio + int(raio * 1.12), meio_y
        desenho.line((cabo, (x, y)), fill=COR_BORDA, width=largura * 2)
        desenho.line((cabo, (x, y)), fill=(112, 80, 46, 255), width=largura)
        poligono([(x, y - largura * 3), (x + largura * 2, y), (x, y + largura * 3),
                  (x - largura * 2, y)], cor)
    elif "transform" in tipo:
        x = meio + int(raio * .8)
        desenho.line((meio + int(raio * .3), meio_y, x + comprimento, meio_y),
                     fill=COR_BORDA, width=largura * 2)
        desenho.line((meio + int(raio * .3), meio_y, x + comprimento, meio_y),
                     fill=(112, 80, 46, 255), width=largura)
        poligono([(x + comprimento - largura * 3, meio_y - largura * 4),
                  (x + comprimento + largura, meio_y - largura * 3),
                  (x + comprimento, meio_y + largura * 2),
                  (x + comprimento - largura * 4, meio_y + largura)], metal)
    else:
        lamina()


def _desenhar_lutador_teste(canvas, personagem, arma, cor_borda, cx, cy, raio, corpo):
    """Fallback sem Tk para os dublês de Canvas nos testes."""
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
