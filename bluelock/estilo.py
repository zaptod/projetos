# -*- coding: utf-8 -*-
"""A cara da janela "Blue Lock — versoes": verde-campo com acento lima.

Identidade do JOGO (o "BL" do logo e lima sobre campo escuro), no mesmo
molde das janelas de trabalho do painel: escalas fechadas (espaco 4/8/12/16/
24/32, texto por PAPEL, cor por SIGNIFICADO) e acento so no que e clicavel
ou esta ativo. Sem Tk neste arquivo, exceto os dois widgets (`Pilula`,
`Logo`): os nomes amigaveis e as datas relativas sao puros e o teste chama
sem tela.
"""
from __future__ import annotations

import re
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime, timezone

CORES = {
    "fundo": "#0f1512", "superficie": "#161f1a", "superficie_alta": "#1d2923",
    "borda": "#26352d", "borda_forte": "#35493e",
    "texto": "#e8efe9", "texto_fraco": "#9fb0a5", "texto_apagado": "#6b7d72",
    "acento": "#c4f16b", "acento_forte": "#d6f78f", "acento_fundo": "#1f3326", "sobre_acento": "#0f1512",
    "ok": "#4ade80", "aviso": "#f5c451", "erro": "#ff7a7a", "erro_fundo": "#2b1618",
    "aviso_fundo": "#2a2413",
}
ESPACO = {"pouco": 4, "meio": 8, "normal": 12, "muito": 16, "secao": 24, "pagina": 32}
FONTE = "Segoe UI"
# papel -> (tamanho, peso)
TEXTO = {"titulo": (20, "bold"), "destaque": (15, "bold"), "secao": (12, "bold"), "nome": (11, "bold"), "corpo": (10, "normal"),
         "legenda": (9, "normal"), "selo": (8, "bold"), "mono": (9, "normal")}


def letra(papel: str, peso: str | None = None) -> tuple:
    tamanho, peso_padrao = TEXTO[papel]
    familia = "Consolas" if papel == "mono" else FONTE
    return (familia, tamanho, peso or peso_padrao)


# ------------------------------------------------------------------ nomes
JOGADORES = {"bachira", "isagi", "rin", "barou", "nagi", "chigiri", "kunigami", "reo", "kaiser", "shidou",
             "otoya", "aryu", "gagamaru", "ness", "yukimiya", "karasu", "hiori", "raichi", "niko", "ego"}
TIPOS = {"feat": "melhoria", "fix": "correção", "audit": "auditoria", "docs": "documentação", "design": "design",
         "chore": "ajuste", "refactor": "reorganização", "test": "testes"}


def nome_amigavel(ref: str) -> tuple[str, str]:
    """`feat/bachira-roulette-choreography-20261024` -> ("Bachira · roulette
    choreography", "melhoria"). O slug cru nao vai para a tela principal."""
    if ref == "main":
        return "Versão principal", ""
    if re.fullmatch(r"[0-9a-f]{7,40}", ref):
        return f"Commit {ref[:7]}", ""
    tipo = ""
    if "/" in ref:
        prefixo, ref = ref.split("/", 1)
        tipo = TIPOS.get(prefixo, prefixo)
    ref = re.sub(r"-\d{8}$", "", ref)
    palavras = [p for p in ref.split("-") if p]
    if not palavras:
        return ref, tipo
    if palavras[0].lower() in JOGADORES and len(palavras) > 1:
        return f"{palavras[0].capitalize()} · {' '.join(palavras[1:])}", tipo
    texto = " ".join(palavras)
    return texto[:1].upper() + texto[1:], tipo


def _quando(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.astimezone()
    return d.astimezone()


def data_relativa(iso: str | None, agora: datetime | None = None) -> str:
    """`há 2 h`, `ontem`, `há 3 dias`; passado de uma semana vira `14/10`."""
    d = _quando(iso)
    if d is None:
        return ""
    agora = (agora or datetime.now(timezone.utc)).astimezone()
    seg = (agora - d).total_seconds()
    if seg < 90:
        return "agora há pouco"
    if seg < 3600:
        return f"há {int(seg // 60)} min"
    if seg < 86400 and d.date() == agora.date():
        return f"há {int(seg // 3600)} h"
    dias = (agora.date() - d.date()).days
    if dias <= 1:
        return "ontem"
    if dias < 7:
        return f"há {dias} dias"
    return d.strftime("%d/%m")


def e_de_hoje(iso: str | None, agora: datetime | None = None) -> bool:
    d = _quando(iso)
    agora = (agora or datetime.now(timezone.utc)).astimezone()
    return bool(d) and d.date() == agora.date()


# ---------------------------------------------------------------- widgets
def retangulo_redondo(canvas: tk.Canvas, x0, y0, x1, y1, raio, **opcoes):
    r = max(1, min(raio, (x1 - x0) // 2, (y1 - y0) // 2))
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
           x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return canvas.create_polygon(pts, smooth=True, **opcoes)


class Pilula(tk.Canvas):
    """Botao de cantos redondos. tipo: primario | normal | fantasma | perigo | chip.

    Aceita `state`/`text` em `configure`/`cget` como um botao comum. O fundo do
    Canvas tem de ser o do PAI (os cantos mostram o que esta atras)."""

    def __init__(self, pai, texto: str, acao=None, *, tipo: str = "normal", papel: str = "corpo",
                 bg: str | None = None, padx: int = 16, pady: int = 8, peso: str | None = None):
        c = CORES
        self.fonte = tkfont.Font(root=pai, font=letra(papel, peso or ("bold" if tipo == "primario" else None)))
        self._texto, self._acao, self._tipo = texto, acao, tipo
        self._padx = padx
        self._estado, self._sobre, self._ativo = "normal", False, False
        super().__init__(pai, bg=bg or c["fundo"], highlightthickness=0, bd=0, cursor="hand2",
                         height=self.fonte.metrics("linespace") + 2 * pady,
                         width=self.fonte.measure(texto) + 2 * padx)
        self.bind("<Configure>", lambda _e: self._desenhar())
        self.bind("<Enter>", lambda _e: self._passou(True))
        self.bind("<Leave>", lambda _e: self._passou(False))
        self.bind("<ButtonRelease-1>", self._soltou)

    def _paleta(self) -> tuple[str, str, str]:
        c, t = CORES, self._tipo
        if self._estado == "disabled":
            return c["superficie"], c["texto_apagado"], c["borda"]
        if t == "primario":
            return (c["acento_forte"] if self._sobre else c["acento"]), c["sobre_acento"], c["acento"]
        if t == "perigo":
            return (c["erro_fundo"] if self._sobre else self["bg"]), c["erro"], c["erro"]
        if t == "chip":
            if self._ativo:
                return c["acento_fundo"], c["acento"], c["acento"]
            return (c["superficie_alta"] if self._sobre else self["bg"]), c["texto_fraco"], c["borda_forte"]
        if t == "fantasma":
            return (c["superficie_alta"] if self._sobre else self["bg"]), c["texto_fraco"], c["borda"]
        return (c["borda"] if self._sobre else c["superficie_alta"]), c["texto"], c["borda_forte"]

    def _desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        fundo, frente, borda = self._paleta()
        retangulo_redondo(self, 1, 1, w - 1, h - 1, 10, fill=fundo, outline=borda)
        self.create_text(w // 2, h // 2, text=self._texto, fill=frente, font=self.fonte)

    def _passou(self, sim: bool):
        self._sobre = sim
        self._desenhar()

    def _soltou(self, evento):
        if self._estado == "disabled" or not (0 <= evento.x <= self.winfo_width() and 0 <= evento.y <= self.winfo_height()):
            return
        if self._acao:
            self._acao()

    def marcar(self, ativo: bool):
        self._ativo = ativo
        self._desenhar()

    def configure(self, cnf=None, **opcoes):                    # noqa: D102
        redesenhar = False
        if "state" in opcoes:
            self._estado = str(opcoes.pop("state"))
            super().configure(cursor="arrow" if self._estado == "disabled" else "hand2")
            redesenhar = True
        if "text" in opcoes:
            self._texto = opcoes.pop("text")
            super().configure(width=max(int(self["width"]), self.fonte.measure(self._texto) + 2 * self._padx))
            redesenhar = True
        if opcoes or cnf:
            super().configure(cnf, **opcoes)
        if redesenhar:
            self._desenhar()
    config = configure

    def cget(self, chave):                                      # noqa: D102
        if chave == "state":
            return self._estado
        if chave == "text":
            return self._texto
        return super().cget(chave)


class Logo(tk.Canvas):
    """O "BL" lima sobre o campo: quadrado de cantos redondos."""

    def __init__(self, pai, lado: int = 44, bg: str | None = None):
        super().__init__(pai, width=lado, height=lado, bg=bg or CORES["fundo"], highlightthickness=0, bd=0)
        retangulo_redondo(self, 1, 1, lado - 1, lado - 1, lado // 4, fill=CORES["acento"], outline="")
        self.create_text(lado // 2, lado // 2, text="BL", fill=CORES["sobre_acento"],
                         font=(FONTE, max(10, lado // 3), "bold"))


def selo(pai, texto: str, tipo: str = "neutro", bg: str | None = None) -> tk.Label:
    """Etiqueta curta e MAIUSCULA: NOVA, VERSAO PRINCIPAL, PREPARADA."""
    c = CORES
    fundo, frente = {"destaque": (c["acento"], c["sobre_acento"]), "ok": (c["acento_fundo"], c["ok"]),
                     "aviso": (c["aviso_fundo"], c["aviso"]), "erro": (c["erro_fundo"], c["erro"]),
                     "neutro": (c["superficie_alta"], c["texto_fraco"])}[tipo]
    return tk.Label(pai, text=texto.upper(), bg=fundo, fg=frente, font=letra("selo"), padx=6, pady=1)


class Rolagem(tk.Frame):
    """Quadro que rola: o conteudo vai em `.corpo`; a roda do mouse funciona
    quando o ponteiro esta em cima (nao rouba a roda das outras areas)."""

    def __init__(self, pai, bg: str):
        super().__init__(pai, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.barra = ttk_barra(self, self.canvas.yview)
        self.barra.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=self.barra.set)
        self.corpo = tk.Frame(self.canvas, bg=bg)
        self._janela = self.canvas.create_window(0, 0, window=self.corpo, anchor="nw")
        self.corpo.bind("<Configure>", lambda _e: self._ajustar())
        self.canvas.bind("<Configure>", self._largura)
        for w in (self.canvas, self.corpo):
            w.bind("<Enter>", self._entrou)
            w.bind("<Leave>", self._saiu)

    def _largura(self, evento):
        self.canvas.itemconfigure(self._janela, width=evento.width)
        self._ajustar()

    def _ajustar(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all") or (0, 0, 0, 0))
        # sem o que rolar, a barra some (nao ocupa espaco nem engana)
        alto = self.corpo.winfo_reqheight() > self.canvas.winfo_height() > 1
        if alto and not self.barra.winfo_ismapped():
            self.barra.pack(side="right", fill="y", before=self.canvas)
        elif not alto and self.barra.winfo_ismapped():
            self.barra.pack_forget()
            self.canvas.yview_moveto(0)

    def _entrou(self, _e):
        self.bind_all("<MouseWheel>", self._roda)

    def _saiu(self, evento):
        dentro = self.winfo_containing(evento.x_root, evento.y_root)
        if dentro is not None and str(dentro).startswith(str(self)):
            return
        self.unbind_all("<MouseWheel>")

    def _roda(self, evento):
        if self.corpo.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-1 if evento.delta > 0 else 1, "units")

    def ver(self, widget):
        """Rola ate o widget ficar inteiro dentro da area visivel."""
        self.update_idletasks()
        topo = widget.winfo_y()
        base = topo + widget.winfo_height()
        total = max(1, self.corpo.winfo_reqheight())
        y0 = self.canvas.canvasy(0)
        y1 = y0 + self.canvas.winfo_height()
        if topo < y0:
            self.canvas.yview_moveto(topo / total)
        elif base > y1 and self.canvas.winfo_height() > 1:
            self.canvas.yview_moveto((base - self.canvas.winfo_height()) / total)


class Barra(tk.Canvas):
    """Barra de progresso fina (6 px) lima. Fala como a `ttk.Progressbar`
    (`value`, `maximum`, `start`/`stop`) para o resto do codigo nao mudar."""

    def __init__(self, pai, bg: str | None = None):
        super().__init__(pai, height=6, bg=bg or CORES["fundo"], highlightthickness=0, bd=0)
        self._v, self._max, self._modo, self._anda, self._fase = 0.0, 5.0, "determinate", None, 0.0
        self.bind("<Configure>", lambda _e: self._desenhar())

    def _desenhar(self):
        self.delete("all")
        w = self.winfo_width()
        retangulo_redondo(self, 0, 0, w, 6, 3, fill=CORES["superficie_alta"], outline="")
        if self._modo == "indeterminate":
            largura = max(40, w // 5)
            x = int((w + largura) * self._fase) - largura
            self.create_rectangle(max(0, x), 0, min(w, x + largura), 6, fill=CORES["acento"], outline="")
        elif self._v > 0:
            retangulo_redondo(self, 0, 0, max(6, int(w * min(1.0, self._v / (self._max or 1)))), 6, 3,
                              fill=CORES["acento"], outline="")

    def configure(self, cnf=None, **opcoes):                    # noqa: D102
        for chave, atributo in (("value", "_v"), ("maximum", "_max"), ("mode", "_modo")):
            if chave in opcoes:
                setattr(self, atributo, opcoes.pop(chave))
        if opcoes or cnf:
            super().configure(cnf, **opcoes)
        self._desenhar()
    config = configure

    def cget(self, chave):                                      # noqa: D102
        return {"value": self._v, "maximum": self._max, "mode": self._modo}.get(chave) or super().cget(chave)

    def start(self, _intervalo=None):
        self._modo = "indeterminate"
        self.stop(manter_modo=True)
        self._passo()

    def _passo(self):
        self._fase = (self._fase + 0.02) % 1.0
        self._desenhar()
        self._anda = self.after(30, self._passo)

    def stop(self, manter_modo: bool = False):
        if self._anda:
            self.after_cancel(self._anda)
            self._anda = None
        if not manter_modo:
            self._modo = "determinate"
            self._desenhar()


def ttk_barra(pai, comando):
    from tkinter import ttk
    return ttk.Scrollbar(pai, orient="vertical", command=comando, style="BL.Vertical.TScrollbar")


def aplicar_ttk(raiz) -> None:
    from tkinter import ttk
    c = CORES
    e = ttk.Style(raiz)
    try:
        e.theme_use("clam")
    except tk.TclError:
        pass
    e.configure("BL.Vertical.TScrollbar", background=c["borda_forte"], troughcolor=c["fundo"],
                bordercolor=c["fundo"], lightcolor=c["borda_forte"], darkcolor=c["borda_forte"],
                arrowcolor=c["fundo"], gripcount=0, width=10)
    e.map("BL.Vertical.TScrollbar", background=[("active", c["texto_apagado"])])
    e.layout("BL.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
        ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
