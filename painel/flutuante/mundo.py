# -*- coding: utf-8 -*-
"""A Vila da janela flutuante: um mapa COMPACTO e os bots andando nele.

O mapa grande do painel (44x26 tiles, 2x) nao cabe numa janela de 720 px
com dez predios. Este e outro recorte do MESMO mundo — mesmo motor, mesma
folha, mesmos papeis —, montado em codigo: duas fileiras de predios, duas
ruas, a casa dos bots no meio. Nada disso vai para o `config.json`: a
Oficina continua dona do mapa grande.

FALLBACK EM TRES DEGRAUS, porque a Oficina salva config pela metade e uma
fabrica nova (o DeepSeek) pode chegar antes da arte:

  1. o papel `predio.<nome>` do config (sprite de verdade);
  2. `vila.gerar_base.predio_procedural` (o mesmo desenho, feito na hora);
  3. um retangulo com telhado na cor do predio (sem Pillow nao ha Vila,
     mas sem `vila/` instalado ainda ha janela).

Predio nunca some da tela: sumir e o jeito mais silencioso de mentir.
"""
from __future__ import annotations

import math
import random
import time
import tkinter as tk

from . import dados

TILE = 16
LARG, ALT = 44, 15
LARGURA_PX, ALTURA_PX = LARG * TILE, ALT * TILE
ESCALA_BOT = 2

# (x, y) em tiles do canto de cada predio 4x3.
LOTES = {
    "deepseek": (1, 1), "chatgpt": (10, 1), "gemini": (19, 1),
    "picasso": (28, 1), "digen": (37, 1),
    "estudio": (1, 9), "arena": (7, 9), "youtube": (27, 9),
    "tiktok": (32, 9), "bot": (37, 9),
}
CASA = (20, 9)
RUAS = (5, 13)
TRAVESSAS = (17, 25)

CORES = {
    "deepseek": "#4d6bfe", "chatgpt": "#10a37f", "gemini": "#4e8cf7",
    "picasso": "#c05be3", "digen": "#e35b8f", "estudio": "#e0a63b",
    "arena": "#d9483b", "youtube": "#d4201a", "tiktok": "#26242e",
    "bot": "#6d5fd8", "casa": "#b5502e",
}


def mapa_compacto() -> dict:
    """O mapa no formato do motor (paleta + chao + decor), deterministico."""
    rnd = random.Random(11)
    paleta = ["chao.grama", "chao.flor", "chao.caminho", "chao.agua"]
    chao = [[1 if rnd.random() < 0.06 else 0 for _ in range(LARG)]
            for _ in range(ALT)]
    for y in RUAS:
        for x in range(LARG):
            chao[y][x] = 2
    for x in TRAVESSAS:
        for y in range(RUAS[0], RUAS[1] + 1):
            chao[y][x] = 2
    for nome, (x, y) in list(LOTES.items()) + [("casa", CASA)]:
        chao[y + 3][x + 2] = 2                    # a calcada da porta
    for y in range(9, 12):                        # a lagoa entre arena e rua
        for x in range(12, 16):
            if ((x - 13.5) ** 2) / 4.5 + ((y - 10) ** 2) / 1.6 <= 1:
                chao[y][x] = 3

    decor = [{"x": x, "y": 1, "papel": p} for x, p in (
        (6, "decor.arvore"), (15, "decor.arvore2"), (24, "decor.arvore"),
        (33, "decor.arvore2"), (42, "decor.arvore"))]
    decor += [{"x": 42, "y": 9, "papel": "decor.arvore2"},
              {"x": 42, "y": 11, "papel": "decor.arvore"}]
    ocupado = set()
    for nome, (x, y) in list(LOTES.items()) + [("casa", CASA)]:
        ocupado |= {(x + dx, y + dy) for dx in range(4) for dy in range(4)}
    for item in decor:
        ocupado |= {(item["x"] + dx, item["y"] + dy)
                    for dx in range(2) for dy in range(2)}
    for _ in range(40):
        x, y = rnd.randrange(LARG), rnd.randrange(ALT)
        if (x, y) in ocupado or chao[y][x] not in (0, 1):
            continue
        if y not in (0, 6, 7, 8, 14) and not (x == 36 and y == 11):
            continue
        decor.append({"x": x, "y": y, "papel": rnd.choice(
            ["decor.arbusto", "decor.arbusto", "decor.pedra"])})
        ocupado.add((x, y))
    return {"larg": LARG, "alt": ALT, "paleta": paleta, "chao": chao,
            "decor": decor, "predios": {}, "casa": None}


def _cor(texto: str) -> tuple:
    texto = texto.lstrip("#")
    return tuple(int(texto[i:i + 2], 16) for i in (0, 2, 4))


def predio_vetorial(nome: str):
    """O ultimo degrau: parede, telhado e porta, sem folha nenhuma."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (TILE * 4, TILE * 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    tom = _cor(CORES.get(nome, "#8a7f72"))
    d.rectangle([4, 16, 59, 47], fill=(230, 215, 180, 255))
    d.polygon([0, 18, 63, 18, 55, 2, 8, 2], fill=tom + (255,))
    d.rectangle([28, 36, 35, 47], fill=(91, 61, 36, 255))
    return img


def sprite_do_predio(nome: str, atlas=None) -> tuple:
    """(imagem 64x48, origem) com origem em sprite|procedural|vetorial."""
    papel = f"predio.{nome}"
    if atlas is not None:
        try:
            img = atlas.sprite(papel, 0, 1)
            if img.size != (TILE * 4, TILE * 3):
                from PIL import Image
                img = img.resize((TILE * 4, TILE * 3), Image.NEAREST)
            return img, "sprite"
        except Exception:                                    # noqa: BLE001
            pass
    try:
        from vila.gerar_base import predio_procedural
        return predio_procedural(nome, CORES.get(nome)), "procedural"
    except Exception:                                        # noqa: BLE001
        return predio_vetorial(nome), "vetorial"


def _atlas_e_cfg():
    try:
        from vila import motor
        cfg = motor.carregar()
        if not motor.pronto(cfg):
            return None, None, None
        cfg = dict(cfg)
        cfg["mapa"] = mapa_compacto()
        return motor, cfg, motor.Atlas(cfg)
    except Exception:                                        # noqa: BLE001
        return None, None, None


def compor(atlas_e_cfg=None):
    """(imagem do mundo, {predio: origem do sprite}, atlas)."""
    from PIL import Image, ImageDraw
    motor, cfg, atlas = atlas_e_cfg or _atlas_e_cfg()
    mundo = None
    if motor is not None:
        try:
            mundo = motor.compor_mundo(cfg, atlas, 1)
        except Exception:                                    # noqa: BLE001
            mundo = None
    if mundo is None:
        # Sem folha: chao liso com as ruas, para os predios terem onde ficar.
        mundo = Image.new("RGBA", (LARGURA_PX, ALTURA_PX), (62, 122, 58, 255))
        d = ImageDraw.Draw(mundo)
        for y in RUAS:
            d.rectangle([0, y * TILE, LARGURA_PX, (y + 1) * TILE - 1],
                        fill=(201, 169, 105, 255))
        for x in TRAVESSAS:
            d.rectangle([x * TILE, RUAS[0] * TILE, (x + 1) * TILE - 1,
                         (RUAS[1] + 1) * TILE - 1], fill=(201, 169, 105, 255))
    origens = {}
    for nome, (x, y) in list(LOTES.items()) + [("casa", CASA)]:
        img, origem = sprite_do_predio(nome, atlas)
        mundo.alpha_composite(img, (x * TILE, y * TILE))
        origens[nome] = origem
    return mundo, origens, atlas


def porta(nome: str) -> tuple:
    """Onde o bot fica em pe para trabalhar (base do sprite, em px)."""
    x, y = LOTES.get(nome, CASA)
    return ((x + 2) * TILE, (y + 3) * TILE + 12)


def lar(indice: int) -> tuple:
    """A vaga do bot na frente da casa quando nao ha trabalho."""
    cx = (CASA[0] + 2) * TILE
    return (cx + (indice - 4.5) * 17, ALTURA_PX - 1)


class CenaVila:
    """O Canvas. So desenha: o estado chega pronto em `aplicar`."""

    PASSO_PX = 2.6

    def __init__(self, pai, tema, ao_clicar=None, cache: dict | None = None):
        self.t = tema
        self.ao_clicar = ao_clicar
        self.canvas = tk.Canvas(pai, width=LARGURA_PX, height=ALTURA_PX,
                                bg=tema.superficie, highlightthickness=1,
                                highlightbackground=tema.borda, bd=0)
        # O cache vive na JANELA: trocar de tamanho recria a cena, e recompor
        # o mundo a cada troca seria meio segundo de Pillow a toa.
        self._cache = cache if cache is not None else {}
        self._fotos: dict = {}
        self._bots: dict = {}
        self._fx: dict = {}
        self.origens: dict = {}
        self._montar()
        self.canvas.bind("<Button-1>", self._clique)

    # ------------------------------------------------------------ montar
    def _montar(self) -> None:
        try:
            from PIL import ImageTk
        except Exception:                                    # noqa: BLE001
            self.canvas.create_text(
                LARGURA_PX // 2, ALTURA_PX // 2, fill=self.t.texto_fraco,
                text="A Vila precisa do Pillow (pip install pillow).")
            return
        if "mundo" not in self._cache:
            self._cache["mundo"] = compor()
        mundo, self.origens, self._atlas = self._cache["mundo"]
        self._ImageTk = ImageTk
        self._fotos["mundo"] = ImageTk.PhotoImage(mundo)
        self.canvas.create_image(0, 0, anchor="nw",
                                 image=self._fotos["mundo"])

        fonte = self.t.letra("legenda")
        for i, nome in enumerate(dados.PREDIOS):
            x, y = LOTES[nome]
            cx = (x + 2) * TILE
            topo = y * TILE
            fundo = self.canvas.create_rectangle(0, 0, 0, 0,
                                                 fill=self.t.fundo,
                                                 outline=self.t.borda)
            texto = self.canvas.create_text(
                cx, topo + 1, anchor="n", font=fonte, fill=self.t.texto,
                text=f"{dados.emoji(nome)} {dados.rotulo(nome)}")
            self._ajustar_fundo(fundo, texto, 3, 0)
            # A BANDEIRA e so o sinal (conta de navegador em uso aqui); QUAL
            # conta aparece na linha "contas em uso" e no clique no predio.
            # Com o nome escrito no telhado, ela brigava com o balao.
            bandeira_fundo = self.canvas.create_rectangle(
                0, 0, 0, 0, fill=self.t.acento_fundo,
                outline=self.t.acento, state="hidden")
            bandeira = self.canvas.create_text(
                (x + 4) * TILE - 3, topo + 19, anchor="ne",
                font=self.t.letra("legenda", "bold"),
                fill=self.t.acento_forte, text="", state="hidden")
            fx = self.canvas.create_image((x + 4) * TILE - 4, topo + 36,
                                          anchor="center")
            casa = lar(i)
            item = self.canvas.create_image(casa[0], casa[1], anchor="s")
            balao_fundo = self.canvas.create_rectangle(
                0, 0, 0, 0, fill=self.t.superficie_alta,
                outline=self.t.borda_forte, state="hidden")
            balao = self.canvas.create_text(casa[0], casa[1] + 3,
                                            anchor="n", font=fonte,
                                            fill=self.t.texto, text="")
            self._bots[nome] = {
                "item": item, "balao": balao, "balao_fundo": balao_fundo,
                "rotulo": texto, "rotulo_fundo": fundo,
                "bandeira": bandeira, "bandeira_fundo": bandeira_fundo,
                "fx": fx, "pos": list(casa), "alvo": list(casa),
                "casa": list(casa), "direcao": "baixo", "fase": i * 1.7,
                "texto": "", "status": "ocioso"}
        # Os ociosos nao ganham balao cada um (dez "💤" empilhados viram
        # ruido): uma placa so, ao lado da turma na frente da casa.
        inicio_da_turma = lar(0)
        self._ociosos_fundo = self.canvas.create_rectangle(
            0, 0, 0, 0, fill=self.t.fundo, outline=self.t.borda,
            state="hidden")
        self._ociosos = self.canvas.create_text(
            inicio_da_turma[0] - 22, ALTURA_PX - 6, anchor="se", font=fonte,
            fill=self.t.texto_fraco, text="")
        for bot in self._bots.values():
            self.canvas.tag_raise(bot["balao_fundo"])
            self.canvas.tag_raise(bot["balao"])

    def _ajustar_fundo(self, fundo, texto, folga_x: int, folga_y: int) -> None:
        caixa = self.canvas.bbox(texto)
        if not caixa or not self.canvas.itemcget(texto, "text"):
            self.canvas.itemconfigure(fundo, state="hidden")
            return
        x0, y0, x1, y1 = caixa
        self.canvas.coords(fundo, x0 - folga_x, y0 - folga_y,
                           x1 + folga_x, y1 + folga_y)
        self.canvas.itemconfigure(fundo, state="normal")

    def _foto(self, papel: str, quadro: int, escala: int, fabrica=None):
        chave = (papel, fabrica, quadro, escala)
        if chave in self._fotos:
            return self._fotos[chave]
        foto = None
        if self._atlas is not None:
            try:
                foto = self._ImageTk.PhotoImage(self._atlas.sprite(
                    papel, quadro, escala, fabrica=fabrica))
            except Exception:                                # noqa: BLE001
                foto = None
        if foto is None and papel.startswith("bot."):
            foto = self._ImageTk.PhotoImage(_bot_vetorial(escala))
        self._fotos[chave] = foto
        return foto

    # ------------------------------------------------------------ estado
    def aplicar(self, predios: dict) -> None:
        if not self._bots:
            return
        for nome, bot in self._bots.items():
            info = predios.get(nome) or {"status": "ocioso", "balao": "💤",
                                         "contas": []}
            status = info["status"]
            bot["status"] = status
            # `recente` (evento solto ha poucos minutos) tambem e trabalho:
            # o Estudio vistoria e renderiza registrando so `log`/`ok`.
            vai = status in ("trabalhando", "no_ar", "recente")
            bot["alvo"] = list(porta(nome) if vai else bot["casa"])
            bot["texto"] = info.get("balao") or ""
            cor = {"trabalhando": self.t.acento, "recente": self.t.acento,
                   "no_ar": self.t.ok,
                   "erro": self.t.erro}.get(status, self.t.borda)
            self.canvas.itemconfigure(bot["rotulo_fundo"], outline=cor)
            self.canvas.itemconfigure(
                bot["rotulo"],
                fill=self.t.texto if status != "ocioso" else self.t.texto_fraco)
            contas = info.get("contas") or []
            self.canvas.itemconfigure(
                bot["bandeira"],
                text=(f"⚑{len(contas)}" if len(contas) > 1 else "⚑")
                if contas else "",
                state="normal" if contas else "hidden")
            self._ajustar_fundo(bot["bandeira_fundo"], bot["bandeira"], 2, 0)
            bot["efeito"] = {"trabalhando": "fx.trabalho",
                             "recente": "fx.trabalho",
                             "erro": "fx.erro"}.get(status)
        ociosos = sum(1 for b in self._bots.values() if b["status"] == "ocioso")
        self.canvas.itemconfigure(
            self._ociosos,
            text=f"💤 {ociosos} à toa" if ociosos else "")
        self._ajustar_fundo(self._ociosos_fundo, self._ociosos, 3, 0)

    def passo(self) -> None:
        """Um quadro: os bots andam, os baloes seguem, os efeitos piscam."""
        if not self._bots:
            return
        agora = time.monotonic()
        for nome, bot in self._bots.items():
            px, py = bot["pos"]
            ax, ay = bot["alvo"]
            dx, dy = ax - px, ay - py
            distancia = math.hypot(dx, dy)
            andando = distancia > 1.5
            if andando:
                passo = min(self.PASSO_PX, distancia)
                px += dx / distancia * passo
                py += dy / distancia * passo
                bot["direcao"] = (("dir" if dx > 0 else "esq")
                                  if abs(dx) > abs(dy)
                                  else ("baixo" if dy > 0 else "cima"))
            elif bot["direcao"] != "baixo" and bot["status"] == "ocioso":
                bot["direcao"] = "baixo"
            elif bot["status"] != "ocioso" and not andando:
                bot["direcao"] = "cima"         # de frente para a porta
            bot["pos"] = [px, py]
            quadro = int(agora * 6) % 2 if andando else 0
            foto = self._foto(f"bot.{bot['direcao']}", quadro, ESCALA_BOT,
                              fabrica=nome)
            balanco = math.sin(agora * 5 + bot["fase"]) * (1.5 if andando
                                                           else 0.6)
            if foto is not None:
                self.canvas.itemconfigure(bot["item"], image=foto)
            self.canvas.coords(bot["item"], px, py + balanco)

            ocioso = bot["status"] == "ocioso"
            self.canvas.itemconfigure(
                bot["balao"], text="" if ocioso else bot["texto"],
                fill=self.t.erro if bot["status"] == "erro" else self.t.texto)
            # O balao vai POR BAIXO do bot: na rua de cima cai no gramado
            # vazio entre as ruas, na de baixo cai na rua. Por cima, ele
            # tapava a placa do predio — justamente o que diz onde ele esta.
            self.canvas.coords(bot["balao"], px, py + 3 + balanco)
            # Balao de predio na beirada nao pode sair cortado do mapa.
            caixa = self.canvas.bbox(bot["balao"])
            if caixa:
                if caixa[0] < 6:
                    self.canvas.move(bot["balao"], 6 - caixa[0], 0)
                elif caixa[2] > LARGURA_PX - 6:
                    self.canvas.move(bot["balao"],
                                     LARGURA_PX - 6 - caixa[2], 0)
            if ocioso:
                self.canvas.itemconfigure(bot["balao_fundo"], state="hidden")
            else:
                self._ajustar_fundo(bot["balao_fundo"], bot["balao"], 4, 1)

            efeito = bot.get("efeito")
            foto_fx = (self._foto(efeito, int(agora * 3) % 2, 1)
                       if efeito else None)
            self.canvas.itemconfigure(bot["fx"], image=foto_fx or "")

    # ------------------------------------------------------------ clique
    def predio_em(self, x: float, y: float) -> str | None:
        tx, ty = int(x // TILE), int(y // TILE)
        for nome, (lx, ly) in LOTES.items():
            if lx <= tx < lx + 4 and ly <= ty < ly + 3:
                return nome
        return None

    def _clique(self, evento) -> None:
        nome = self.predio_em(evento.x, evento.y)
        if nome and self.ao_clicar:
            self.ao_clicar(nome)


def _bot_vetorial(escala: int):
    """Um bonequinho quando a folha nao tem `bot.*`."""
    from PIL import Image, ImageDraw
    lado = TILE * escala
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = escala
    d.ellipse([5 * u, 1 * u, 11 * u, 7 * u], fill=(240, 196, 154, 255))
    d.rectangle([4 * u, 7 * u, 11 * u, 12 * u], fill=(59, 110, 165, 255))
    d.rectangle([5 * u, 12 * u, 6 * u, 15 * u], fill=(44, 44, 52, 255))
    d.rectangle([9 * u, 12 * u, 10 * u, 15 * u], fill=(44, 44, 52, 255))
    return img


__all__ = ["CenaVila", "LOTES", "compor", "mapa_compacto", "porta",
           "sprite_do_predio"]
