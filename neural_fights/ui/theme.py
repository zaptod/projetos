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

CORES_CLASSE = {k: rgb_to_hex(v) for k, v in _CORES_CLASSE_RGB.items()}

# ============================================================================
# CORES DAS CLASSES POR CATEGORIA
# ============================================================================


# Cores específicas para a tela de luta
COR_P1 = "#3498db"
COR_P2 = "#e94560"


class FilaDaThread:
    """Leva o desfecho de uma thread de trabalho para a thread do Tk.

    MOT-117 (auditoria de 11/10/2026): as threads de render chamavam
    ``self.after`` direto; com a janela ja destruida isso dava RuntimeError
    na thread. Aqui a thread so poe uma funcao na fila (``enviar``); quem a
    chama e a thread do Tk, num ``after`` que para sozinho quando o widget
    some.
    """

    INTERVALO_MS = 100

    def __init__(self, widget: tk.Misc):
        import queue

        self._widget = widget
        self._fila = queue.SimpleQueue()
        self._agendado = False

    def enviar(self, funcao) -> None:
        """Chamado de QUALQUER thread; nunca toca no Tk."""
        self._fila.put(funcao)

    def vigiar(self) -> None:
        """Chamado da thread do Tk ao disparar o trabalho."""
        if not self._agendado:
            self._agendado = True
            self._widget.after(self.INTERVALO_MS, self._drenar)

    def _drenar(self) -> None:
        self._agendado = False
        try:
            if not self._widget.winfo_exists():
                return
        except tk.TclError:
            return
        while True:
            try:
                funcao = self._fila.get_nowait()
            except Exception:
                break
            funcao()
        try:
            self._widget.after(self.INTERVALO_MS, self._drenar)
            self._agendado = True
        except (tk.TclError, RuntimeError):
            pass


def registrar_rolagem(alvo: tk.Misc, ao_rolar) -> None:
    """Liga a roda do mouse a ``alvo`` so quando o ponteiro esta sobre ele.

    MOT-113 (auditoria de 11/10/2026): cada tela fazia o proprio
    ``bind_all("<MouseWheel>")`` e o ultimo vencia (a TelaSons, a ultima
    construida): o wizard de personagens nao rolava e a roda mexia o canvas
    escondido dos Sons. Agora ha um despachante unico por janela: ele acha o
    widget sob o ponteiro (``winfo_containing``), sobe pelos pais ate um alvo
    registrado e chama o ``ao_rolar`` dele.
    """
    raiz = alvo.winfo_toplevel()
    registro = getattr(raiz, "_rolagem_registro", None)
    if registro is None:
        registro = {}
        raiz._rolagem_registro = registro

        def despachar(evento):
            try:
                widget = raiz.winfo_containing(evento.x_root, evento.y_root)
            except (tk.TclError, KeyError):
                widget = None
            while widget is not None:
                funcao = registro.get(str(widget))
                if funcao is not None:
                    try:
                        if widget.winfo_ismapped():
                            return funcao(evento)
                    except tk.TclError:
                        return None
                    return None
                widget = getattr(widget, "master", None)
            return None

        raiz.bind_all("<MouseWheel>", despachar)
    registro[str(alvo)] = ao_rolar
    alvo.bind("<Destroy>", lambda _e, nome=str(alvo): registro.pop(nome, None), add="+")


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
    """Mostra somente arte do Atelie ou os marcadores neutros do palco."""
    from neural_fights.ui import arte_atelie
    if personagem is None:
        canvas.delete("all")
        return
    largura = max(canvas.winfo_width(), int(canvas.cget("width") or 200))
    altura = max(canvas.winfo_height(), int(canvas.cget("height") or 200))
    cx, cy = centro or (largura // 2, altura // 2 - 4)
    corpo = max(50, int(min(largura, altura) * .55 * escala))
    arte_corpo = arte_atelie.carregar_quadros(arte_atelie.peca_lutador(personagem), corpo=corpo)
    arte_arma = arte_atelie.carregar_quadros(arte_atelie.peca_arma(arma), corpo=corpo) if arma else None
    canvas.delete("all")

    def quadro(indice=0):
        # a arma fica na mao (lado direito), sem rosto ou silhueta sintetica.
        canvas.delete("arte")
        arte_atelie.desenhar(canvas, arte_corpo, cx, cy, indice=indice, limpar=False)
        if arte_arma:
            arte_atelie.desenhar(canvas, arte_arma, cx + corpo // 3, cy, indice=indice, limpar=False)
    quadro(0)
    if hasattr(canvas, "after"):
        arte_atelie.animar(canvas, arte_corpo, cx, cy, ao_desenhar=quadro)

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
