# -*- coding: utf-8 -*-
"""A cena FOFA: desenha a `vida.Vida` num Canvas, com a arte do `arte.py`.

A unica cena da janela desde 28/09/2026 (a classica em pixel, `mundo.py`,
foi aposentada por decisao do Adrian). A interface que a janela usa:
`canvas`, `aplicar(predios)`, `passo()`, `predio_em(x, y)` e
`aplicar_estado(estado, colecao)` (noite, publicacoes, placar e enfeites).

O QUE NAO PODE SE PERDER no meio da graca: placa de cada predio com a cor
do estado, bandeira de conta em uso, o balao do que esta sendo feito embaixo
do habitante que trabalha, e o ❗ no predio com erro.
"""
from __future__ import annotations

import math
import random
import time
import tkinter as tk
from datetime import datetime

from . import arte, dados
from .vida import Vida

LARGURA, ALTURA = arte.LARGURA, arte.ALTURA
TILE = arte.TILE


def e_noite(momento: datetime) -> bool:
    return momento.hour >= 19 or momento.hour < 6


class CenaFofa:
    def __init__(self, pai, tema, ao_clicar=None, cache: dict | None = None,
                 relogio=time.monotonic, hora=None):
        self.t = tema
        self.ao_clicar = ao_clicar
        self.relogio = relogio
        self.hora = hora                     # int fixo (provas) ou None
        self.canvas = tk.Canvas(pai, width=LARGURA, height=ALTURA,
                                bg=tema.superficie, highlightthickness=1,
                                highlightbackground=tema.borda, bd=0)
        self._cache = cache if cache is not None else {}
        self._fotos: dict = {}
        self._imagem_atual: dict = {}
        self._posicoes: dict = {}
        self._configs: dict = {}
        self._info_aberto = True
        self._quadro_ambiente = 0
        self.origens = {n: "fofa" for n in arte.LOTES}
        self.vida = self._cache.get("vida") or Vida(list(dados.PREDIOS))
        self._cache["vida"] = self.vida
        self._rnd = random.Random(11)
        self._ultimo = self.relogio()
        self._noite = None
        self._particulas: list = []
        self._visitante = None
        self._proximo_visitante = self._ultimo + self._rnd.uniform(15, 40)
        self._ultima_publicacao = self._cache.get("ultima_publicacao")
        self._colecao = -1
        self._predios: dict = {}
        self._montar()
        self.canvas.bind("<Button-1>", self._clique)

    # ------------------------------------------------------------ imagens
    def _foto(self, chave, fabricar):
        foto = self._fotos.get(chave)
        if foto is None:
            from PIL import ImageTk
            foto = ImageTk.PhotoImage(fabricar())
            self._fotos[chave] = foto
        return foto

    def _mundo(self, noite: bool):
        chave = ("mundo", noite)
        if chave not in self._cache:
            # RGB, e nao RGBA: o fundo e opaco, e com canal alfa o Tk mistura
            # pixel a pixel a cada redesenho — era o grosso da CPU.
            self._cache[chave] = arte.compor_mundo(noite).convert("RGB")
        return self._foto(chave, lambda: self._cache[chave])

    def _personagem(self, nome, pose, olhos, direcao):
        chave = ("p", nome, pose, olhos, direcao)
        if chave not in self._cache:
            self._cache[chave] = arte.desenhar_personagem(nome, pose, olhos,
                                                          direcao)
        return self._foto(chave, lambda: self._cache[chave])

    def _generica(self, chave, fabricar):
        if chave not in self._cache:
            self._cache[chave] = fabricar()
        return self._foto(chave, lambda: self._cache[chave])

    def _trocar_imagem(self, item, foto) -> None:
        """So fala com o Tk quando a imagem MUDOU (e o que segura a CPU)."""
        if self._imagem_atual.get(item) is not foto:
            self.canvas.itemconfigure(item, image=foto)
            self._imagem_atual[item] = foto

    def _mover(self, item, *coords) -> bool:
        """`coords` so quando o PIXEL muda. Devolve se moveu."""
        arred = tuple(int(round(v)) for v in coords)
        if self._posicoes.get(item) == arred:
            return False
        self.canvas.coords(item, *arred)
        self._posicoes[item] = arred
        return True

    def _config(self, item, **opcoes) -> bool:
        """`itemconfigure` so do que mudou. Devolve se mudou algo."""
        atual = self._configs.setdefault(item, {})
        novo = {k: v for k, v in opcoes.items() if atual.get(k) != v}
        if not novo:
            return False
        self.canvas.itemconfigure(item, **novo)
        atual.update(novo)
        return True

    # ------------------------------------------------------------ montar
    def _montar(self) -> None:
        c = self.canvas
        self._fundo = c.create_image(0, 0, anchor="nw")
        self._decoracoes = [c.create_image(x, y, anchor="s", state="hidden")
                            for nome, (x, y) in
                            arte.LUGAR_DAS_DECORACOES.items()]
        cx, cy = arte.LAGO
        self._patos = [c.create_image(cx, cy, anchor="center")
                       for _ in range(2)]
        self._fonte = c.create_image(arte.FONTE[0] - 20, arte.FONTE[1] - 16,
                                     anchor="nw")
        fonte_texto = self.t.letra("legenda")
        self._rotulos = {}
        for nome, (lx, ly) in arte.LOTES.items():
            x = (lx + 2) * TILE
            y = ly * TILE - 15
            fundo = c.create_rectangle(0, 0, 0, 0, fill=self.t.fundo,
                                       outline=self.t.borda, width=1)
            texto = c.create_text(x, y, anchor="n", font=fonte_texto,
                                  fill=self.t.texto_fraco,
                                  text=dados.rotulo(nome))
            bandeira = c.create_text((lx + 4) * TILE + 2, ly * TILE - 2,
                                     anchor="ne", text="",
                                     font=self.t.letra("legenda", "bold"),
                                     fill=self.t.acento_forte)
            alerta = c.create_image((lx + 4) * TILE, ly * TILE + 2,
                                    anchor="s", state="hidden")
            self._rotulos[nome] = (fundo, texto, bandeira, alerta)
            self._ajustar(fundo, texto, 4, 1)

        self._itens = {}
        for nome in self.vida.habitantes:
            corpo = c.create_image(0, 0, anchor="s")
            emote = c.create_image(0, 0, anchor="s", state="hidden")
            balao_fundo = c.create_rectangle(0, 0, 0, 0,
                                             fill=self.t.superficie_alta,
                                             outline=self.t.acento,
                                             state="hidden")
            balao = c.create_text(0, 0, anchor="n", font=fonte_texto,
                                  fill=self.t.texto, text="")
            self._itens[nome] = {"corpo": corpo,
                                 "emote": emote, "balao": balao,
                                 "balao_fundo": balao_fundo}
        # baloes e emotes por cima de todos os corpos
        for itens in self._itens.values():
            for chave in ("balao_fundo", "balao", "emote"):
                c.tag_raise(itens[chave])
        self._vagalumes = [c.create_image(0, 0, state="hidden")
                           for _ in range(12)]
        self._visitante_item = c.create_image(-50, -50, anchor="s")
        self._info_fundo = c.create_rectangle(0, 0, 0, 0, fill="#fffaf2",
                                              outline=self.t.acento,
                                              state="hidden")
        self._info = c.create_text(0, 0, anchor="s", font=fonte_texto,
                                   fill="#3b2a2a", text="")
        self._placar_fundo = c.create_rectangle(0, 0, 0, 0,
                                                fill=self.t.fundo,
                                                outline=self.t.borda)
        self._placar = c.create_text(LARGURA - 6, ALTURA - 4, anchor="se",
                                     font=fonte_texto, fill=self.t.texto,
                                     text="")
        self._atualizar_noite(forcar=True)

    def _ajustar(self, fundo, texto, fx, fy) -> None:
        caixa = self.canvas.bbox(texto)
        if not caixa or not self.canvas.itemcget(texto, "text"):
            self.canvas.itemconfigure(fundo, state="hidden")
            return
        x0, y0, x1, y1 = caixa
        self.canvas.coords(fundo, x0 - fx, y0 - fy, x1 + fx, y1 + fy)
        self.canvas.itemconfigure(fundo, state="normal")

    def _agora_de_parede(self) -> datetime:
        agora = datetime.now()
        if self.hora is not None:
            agora = agora.replace(hour=int(self.hora) % 24)
        return agora

    def _atualizar_noite(self, forcar: bool = False) -> None:
        noite = e_noite(self._agora_de_parede())
        if noite == self._noite and not forcar:
            return
        self._noite = noite
        self.canvas.itemconfigure(self._fundo, image=self._mundo(noite))
        estado = "normal" if noite else "hidden"
        foto = self._generica("vagalume", arte.desenhar_vagalume)
        for item in self._vagalumes:
            self.canvas.itemconfigure(item, image=foto, state=estado)

    # ------------------------------------------------------------ estado
    def aplicar(self, predios: dict) -> None:
        self._predios = predios or {}
        self.vida.aplicar(self._predios, self.relogio())
        for nome, (fundo, texto, bandeira, alerta) in self._rotulos.items():
            info = self._predios.get(nome) or {}
            status = info.get("status", "ocioso")
            cor = {"trabalhando": self.t.acento, "recente": self.t.acento,
                   "aviso": self.t.aviso, "no_ar": self.t.ok,
                   "erro": self.t.erro}.get(status, self.t.borda)
            self.canvas.itemconfigure(fundo, outline=cor,
                                      width=2 if status != "ocioso" else 1)
            self.canvas.itemconfigure(
                texto, fill=self.t.texto if status != "ocioso"
                else self.t.texto_fraco)
            contas = info.get("contas") or []
            self.canvas.itemconfigure(bandeira, text="⚑" if contas else "")
            if status == "erro":
                self.canvas.itemconfigure(
                    alerta, state="normal",
                    image=self._generica(("emote", "❗"),
                                         lambda: arte.emote("❗", 20)))
            else:
                self.canvas.itemconfigure(alerta, state="hidden")

    def aplicar_estado(self, estado: dict, colecao: int = 0,
                       hoje: int = 0) -> None:
        publicados = estado.get("publicados") or []
        mais_nova = publicados[0]["quando"] if publicados else None
        if mais_nova is not None:
            if self._ultima_publicacao is not None \
                    and mais_nova > self._ultima_publicacao:
                self.festa()
            self._ultima_publicacao = mais_nova
            self._cache["ultima_publicacao"] = mais_nova
        self._mostrar_colecao(colecao)
        self.canvas.itemconfigure(
            self._placar,
            text=f"📤 {hoje} hoje · 🎀 {colecao}/{len(arte.DECORACOES)}")
        self._ajustar(self._placar_fundo, self._placar, 4, 1)

    def _mostrar_colecao(self, nivel: int) -> None:
        if nivel == self._colecao:
            return
        self._colecao = nivel
        for i, (item, nome) in enumerate(zip(self._decoracoes,
                                             arte.DECORACOES)):
            if i < nivel:
                foto = self._generica(("decor", nome),
                                      lambda n=nome: arte.desenhar_decoracao(n))
                self.canvas.itemconfigure(item, image=foto, state="normal")
            else:
                self.canvas.itemconfigure(item, state="hidden")

    def festa(self) -> None:
        """Saiu uma publicacao: confete na praca e todo mundo comemora."""
        agora = self.relogio()
        self.vida.publicou(agora)
        cores = ["#ff6b81", "#ffd56b", "#6fd6a8", "#6fb7ff", "#c9a7ff"]
        x0, y0 = arte.FONTE[0], arte.FONTE[1] - 20
        for _ in range(36):
            angulo = self._rnd.uniform(-math.pi * .9, -math.pi * .1)
            vel = self._rnd.uniform(60, 140)
            item = self.canvas.create_rectangle(
                x0, y0, x0 + 3, y0 + 2, width=0,
                fill=self._rnd.choice(cores))
            self._particulas.append({
                "item": item, "x": x0, "y": y0,
                "vx": math.cos(angulo) * vel, "vy": math.sin(angulo) * vel,
                "fim": agora + self._rnd.uniform(1.6, 2.6)})

    # ------------------------------------------------------------ animar
    def passo(self) -> None:
        agora = self.relogio()
        dt = min(.25, agora - self._ultimo)
        self._ultimo = agora
        self.vida.tick(dt, agora)
        c = self.canvas
        for nome, h in self.vida.habitantes.items():
            itens = self._itens[nome]
            pose, olhos, direcao, pulo = self.vida.pose(h, agora)
            x, y = self.vida.posicao_de_desenho(h)
            # Balanco so andando: parado, o boneco fica quieto e o Tk nao
            # recebe nada (e isso que deixa a CPU baixa com a vila calma).
            balanco = math.sin(h.passo_t * 12) * 1.2 if h.andando else 0.0
            self._trocar_imagem(itens["corpo"],
                                self._personagem(nome, pose, olhos, direcao))
            topo = y - pulo + balanco
            self._mover(itens["corpo"], x, topo)
            # emote em cima da cabeca
            if h.emote and h.emote_desde <= agora < h.emote_ate:
                foto = self._generica(("emote", h.emote),
                                      lambda s=h.emote: arte.emote(s))
                self._trocar_imagem(itens["emote"], foto)
                flutua = math.sin((agora - h.emote_desde) * 4) * 1.5
                self._mover(itens["emote"], x + 9, topo - 26 + flutua)
                self._config(itens["emote"], state="normal")
            else:
                self._config(itens["emote"], state="hidden")
            # o balao do TRABALHO (o estado real): embaixo do habitante
            texto = h.balao if h.modo in ("trabalho", "erro") else ""
            aviso = texto.startswith("⚠")
            cor_balao = (self.t.erro if h.modo == "erro"
                         else self.t.aviso if aviso else self.t.acento)
            mudou = self._config(
                itens["balao"], text=texto,
                fill=self.t.erro if h.modo == "erro"
                else self.t.aviso if aviso else self.t.texto)
            if texto:
                mudou = self._mover(itens["balao"], x, y + 2) or mudou
                if mudou:
                    caixa = c.bbox(itens["balao"])
                    desvio = 0
                    if caixa and caixa[0] < 4:
                        desvio = 4 - caixa[0]
                    elif caixa and caixa[2] > LARGURA - 4:
                        desvio = LARGURA - 4 - caixa[2]
                    if desvio:
                        c.move(itens["balao"], desvio, 0)
                        self._posicoes.pop(itens["balao"], None)
                    self._ajustar(itens["balao_fundo"], itens["balao"], 4, 1)
                    self._configs.pop(itens["balao_fundo"], None)
                self._config(itens["balao_fundo"], outline=cor_balao)
            elif mudou:
                c.itemconfigure(itens["balao_fundo"], state="hidden")
        self._animar_ambiente(agora, dt)

    def _animar_ambiente(self, agora: float, dt: float) -> None:
        # O cenario anda a ~7 quadros por segundo: patos e fonte nao precisam
        # de mais, e cada redesenho do Tk custa CPU.
        self._quadro_ambiente = (self._quadro_ambiente + 1) % 3
        if self._quadro_ambiente:
            self._animar_particulas(agora, dt)
            return
        dt = dt * 3
        cx, cy = arte.LAGO
        for i, item in enumerate(self._patos):
            a = agora * .35 + i * math.pi
            x = cx + math.cos(a) * 18
            y = cy + math.sin(a) * 7 - 2
            frente = "dir" if math.sin(a) < 0 else "esq"
            foto = self._generica(("pato", frente, int(agora * 2 + i) % 2),
                                  lambda f=frente, q=int(agora * 2 + i) % 2:
                                  _virar(arte.desenhar_pato(q), f))
            self._trocar_imagem(item, foto)
            self._mover(item, x, y)
        quadro = int(agora * 3) % 3
        self._trocar_imagem(self._fonte, self._generica(
            ("fonte", quadro), lambda q=quadro: arte.desenhar_fonte(q)))
        if int(agora) % 30 == 0:
            self._atualizar_noite()
        if self._noite:
            for i, item in enumerate(self._vagalumes):
                base_x = (i * 61 + 23) % LARGURA
                base_y = 100 + (i * 37) % 120
                x = base_x + math.sin(agora * .7 + i) * 14
                y = base_y + math.cos(agora * .9 + i * 1.3) * 8
                self._mover(item, x, y)
                ligado = math.sin(agora * 2.2 + i * 1.7) > -.3
                self._config(item, state="normal" if ligado else "hidden")
        self._animar_visitante(agora, dt)
        self._animar_particulas(agora, dt / 3)
        self._animar_info(agora)

    def _animar_particulas(self, agora: float, dt: float) -> None:
        c = self.canvas
        vivas = []
        for p in self._particulas:
            if agora >= p["fim"]:
                c.delete(p["item"])
                continue
            p["vy"] += 160 * dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            c.coords(p["item"], p["x"], p["y"], p["x"] + 3, p["y"] + 2)
            vivas.append(p)
        self._particulas = vivas

    def _animar_info(self, agora: float) -> None:
        c = self.canvas
        h = next((h for h in self.vida.habitantes.values()
                  if h.info and h.info_ate > agora), None)
        if h is not None:
            x, y = self.vida.posicao_de_desenho(h)
            c.itemconfigure(self._info, text=h.info)
            c.coords(self._info, x, y - 36)
            caixa = c.bbox(self._info)
            if caixa and caixa[0] < 4:
                c.move(self._info, 4 - caixa[0], 0)
            elif caixa and caixa[2] > LARGURA - 4:
                c.move(self._info, LARGURA - 4 - caixa[2], 0)
            if caixa and caixa[1] < 2:
                c.move(self._info, 0, 2 - caixa[1])
            self._ajustar(self._info_fundo, self._info, 5, 2)
            c.tag_raise(self._info_fundo)
            c.tag_raise(self._info)
        elif self._info_aberto:
            c.itemconfigure(self._info, text="")
            c.itemconfigure(self._info_fundo, state="hidden")
        self._info_aberto = h is not None

    def _animar_visitante(self, agora: float, dt: float) -> None:
        """De vez em quando um gatinho passa pela rua, ou um passaro voa."""
        c = self.canvas
        if self._visitante is None:
            if agora < self._proximo_visitante:
                return
            tipo = self._rnd.choice(("gato", "passaro"))
            indo = self._rnd.choice((1, -1))
            self._visitante = {
                "tipo": tipo, "dir": indo,
                "x": -20 if indo > 0 else LARGURA + 20,
                "y": arte.RUA_Y[1] + 14 if tipo == "gato"
                else self._rnd.uniform(18, 60),
                "vel": 30 if tipo == "gato" else 70}
        v = self._visitante
        v["x"] += v["dir"] * v["vel"] * dt
        quadro = int(agora * (6 if v["tipo"] == "passaro" else 4)) % 2
        frente = "dir" if v["dir"] > 0 else "esq"
        fabricar = (arte.desenhar_gato if v["tipo"] == "gato"
                    else arte.desenhar_passaro)
        foto = self._generica((v["tipo"], frente, quadro),
                              lambda: _virar(fabricar(quadro), frente))
        self._trocar_imagem(self._visitante_item, foto)
        y = v["y"] + (math.sin(agora * 5) * 3 if v["tipo"] == "passaro"
                      else 0)
        c.coords(self._visitante_item, v["x"], y)
        if not -30 <= v["x"] <= LARGURA + 30:
            self._visitante = None
            self._proximo_visitante = agora + self._rnd.uniform(35, 90)
            c.coords(self._visitante_item, -50, -50)

    # ------------------------------------------------------------ clique
    def personagem_em(self, x: float, y: float) -> str | None:
        melhor, distancia = None, 15.0
        for nome, h in self.vida.habitantes.items():
            hx, hy = self.vida.posicao_de_desenho(h)
            d = math.hypot(x - hx, y - (hy - 14))
            if d < distancia:
                melhor, distancia = nome, d
        return melhor

    def predio_em(self, x: float, y: float) -> str | None:
        tx, ty = x / TILE, y / TILE
        for nome, (lx, ly) in arte.LOTES.items():
            if lx <= tx < lx + 4 and ly - 1 <= ty < ly + 3:
                return nome
        return None

    def _clique(self, evento) -> None:
        nome = self.personagem_em(evento.x, evento.y)
        if nome:
            self.vida.clique(nome, self.relogio())
            return
        predio = self.predio_em(evento.x, evento.y)
        if predio and self.ao_clicar:
            self.ao_clicar(predio)


def _virar(img, frente: str):
    from PIL import Image
    return img if frente == "dir" else img.transpose(Image.FLIP_LEFT_RIGHT)


__all__ = ["CenaFofa", "e_noite"]
