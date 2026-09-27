# -*- coding: utf-8 -*-
"""A vida dos habitantes da Vila. Logica PURA: sem Tk, testavel.

PEDIDO DO ADRIAN (17/09/2026): "de mais vida aos personagens, faca eles
andarem de um lado pro outro e crie interacoezinhas; quero que seja um
passatempo legalzinho".

A REGRA QUE NAO SE DOBRA: a animacao enfeita, o ESTADO REAL manda. Um
servico trabalhando leva o seu habitante ao predio, com o balao do que esta
sendo feito, nao importa se ele estava sentado no banco ou conversando.
Erro fica visivel no predio. So quem esta de folga passeia.

COMO ANDAM: por um GRAFO de caminhos (as duas ruas, as duas travessas e as
calcadas ate cada porta e cada ponto de interesse). Ninguem atravessa casa:
o teste confere cada segmento contra cada lote.
"""
from __future__ import annotations

import heapq
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field

from . import arte

TOPO_Y, BASE_Y = arte.RUA_Y
INF = float("inf")

# ponto de interesse: (posicao, rua de acesso, atividade, emotes possiveis)
PONTOS = {
    "banco": ((arte.BANCO[0], 110), "T", "sentado", ("☕", "😌", "")),
    "fonte": ((arte.FONTE[0], 104), "T", "olhar", ("✨", "😊", "")),
    "canteiro": ((arte.CANTEIRO[0], 104), "T", "regar", ("🌷", "💐")),
    "lago": ((arte.LAGO[0], 196), "B", "patos", ("🦆", "🍞")),
    "arvore": ((112, 76), "T", "olhar", ("🍃", "🍎", "")),
    "casa": ((arte.portas()["casa"][0], 204), "B", "descansar",
             ("💤", "📖", "")),
}
ATIVIDADES_DE_PASSEIO = tuple(PONTOS)
PAPO = ("👋", "💬", "☕", "😄")


class Grafo:
    def __init__(self):
        self.nos: dict[str, tuple] = {}
        self.adj: dict[str, set] = defaultdict(set)

    def no(self, nome: str, x: float, y: float) -> str:
        self.nos[nome] = (float(x), float(y))
        return nome

    def ligar(self, a: str, b: str) -> None:
        self.adj[a].add(b)
        self.adj[b].add(a)

    def distancia(self, a: str, b: str) -> float:
        (x0, y0), (x1, y1) = self.nos[a], self.nos[b]
        return math.hypot(x1 - x0, y1 - y0)

    def segmentos(self) -> list:
        vistos = set()
        saida = []
        for a, vizinhos in self.adj.items():
            for b in vizinhos:
                chave = tuple(sorted((a, b)))
                if chave not in vistos:
                    vistos.add(chave)
                    saida.append((self.nos[a], self.nos[b]))
        return saida

    def caminho(self, de: str, para: str) -> list[str]:
        """Os nos DEPOIS de `de` ate `para` (Dijkstra). [] se ja esta la."""
        if de == para:
            return []
        dist = {de: 0.0}
        veio: dict[str, str] = {}
        fila = [(0.0, de)]
        while fila:
            d, atual = heapq.heappop(fila)
            if atual == para:
                break
            if d > dist.get(atual, INF):
                continue
            for viz in sorted(self.adj[atual]):
                nd = d + self.distancia(atual, viz)
                if nd < dist.get(viz, INF):
                    dist[viz] = nd
                    veio[viz] = atual
                    heapq.heappush(fila, (nd, viz))
        if para not in veio:
            return []
        rota = [para]
        while rota[-1] != de:
            rota.append(veio[rota[-1]])
        rota.reverse()
        return rota[1:]


def montar_grafo() -> Grafo:
    g = Grafo()
    portas = arte.portas()
    xs = {"T": {8, 692, *arte.TRAVESSAS_X}, "B": {8, 692, *arte.TRAVESSAS_X}}
    for nome, (px, py) in portas.items():
        xs["T" if py < 120 else "B"].add(px)
    for _nome, ((x, _y), rua, _a, _e) in PONTOS.items():
        xs[rua].add(x)
    for rua, y in (("T", TOPO_Y), ("B", BASE_Y)):
        ordem = sorted(xs[rua])
        for x in ordem:
            g.no(f"{rua}:{x}", x, y)
        for a, b in zip(ordem, ordem[1:]):
            g.ligar(f"{rua}:{a}", f"{rua}:{b}")
    for x in arte.TRAVESSAS_X:
        g.ligar(f"T:{x}", f"B:{x}")
    for nome, (px, py) in portas.items():
        rua, y = ("T", py + 12) if py < 120 else ("B", py + 12)
        g.no(f"porta:{nome}", px, y)
        g.ligar(f"porta:{nome}", f"{rua}:{px}")
    for nome, ((x, y), rua, _a, _e) in PONTOS.items():
        if nome == "casa":
            continue                       # a casa ja e a porta:casa
        g.no(f"poi:{nome}", x, y)
        g.ligar(f"poi:{nome}", f"{rua}:{x}")
    return g


def no_do_ponto(nome: str) -> str:
    return "porta:casa" if nome == "casa" else f"poi:{nome}"


def lotes_px() -> list[tuple]:
    """(x0, y0, x1, y1) de cada predio e da casa, em pixels."""
    saida = []
    for lx, ly in list(arte.LOTES.values()) + [arte.CASA]:
        saida.append((lx * arte.TILE, ly * arte.TILE,
                      (lx + 4) * arte.TILE, (ly + 3) * arte.TILE))
    return saida


@dataclass
class Habitante:
    nome: str
    pos: list
    no: str
    desvio: float = 0.0
    modo: str = "passeio"
    rota: list = field(default_factory=list)
    atividade: str = ""
    ate: float = 0.0
    pausa_ate: float = 0.0
    direcao: str = "dir"
    emote: str = ""
    emote_ate: float = 0.0
    pulo_ini: float = -10.0
    info: str = ""
    info_ate: float = 0.0
    balao: str = ""
    alvo: str = ""
    replanejar: bool = False
    ultimo_ponto: str = ""
    destino_ponto: str = ""
    emote_desde: float = 0.0
    conversa_livre: float = 0.0
    fase: float = 0.0
    andando: bool = False
    passo_t: float = 0.0


class Vida:
    VEL_PASSEIO = 34.0
    VEL_TRABALHO = 70.0
    RAIO_DE_ENCONTRO = 16.0
    PAUSA_DE_PAPO = 2.4
    INTERVALO_DE_PAPO = 25.0

    def __init__(self, nomes, semente: int = 7, grafo: Grafo | None = None):
        self.g = grafo or montar_grafo()
        self.rnd = random.Random(semente)
        self.habitantes: dict[str, Habitante] = {}
        partida = sorted(n for n in self.g.nos if n.startswith(("T:", "B:")))
        for i, nome in enumerate(nomes):
            no = self.rnd.choice(partida)
            self.habitantes[nome] = Habitante(
                nome=nome, pos=list(self.g.nos[no]), no=no,
                desvio=(i % 5 - 2) * 4.0, fase=i * 1.37,
                conversa_livre=self.rnd.uniform(3, 12))
        self._status: dict[str, str] = {n: "ocioso" for n in nomes}

    # --------------------------------------------------------- estado real
    def aplicar(self, predios: dict, agora: float) -> list:
        """O estado real entra aqui. Devolve eventos (para testes e efeitos)."""
        eventos = []
        novos_erros = []
        for nome, h in self.habitantes.items():
            info = predios.get(nome) or {}
            status = info.get("status", "ocioso")
            antes = self._status.get(nome, "ocioso")
            self._status[nome] = status
            if status in ("trabalhando", "recente", "no_ar", "aviso"):
                novo = "trabalho"
            elif status == "erro":
                novo = "erro"
                if antes != "erro":
                    novos_erros.append(nome)
            else:
                if h.modo == "trabalho":
                    novo = "comemorar"
                    eventos.append(("terminou", nome))
                elif h.modo == "erro":
                    novo = "passeio"
                else:
                    novo = h.modo
            h.balao = (info.get("balao") or "") if novo in (
                "trabalho", "erro") else ""
            if novo != h.modo:
                self._mudar(h, novo, agora)
        for nome in novos_erros:
            amigo = self._mais_perto_de_folga(nome)
            if amigo is not None:
                amigo.alvo = nome
                self._mudar(amigo, "consolar", agora)
                eventos.append(("consolar", amigo.nome, nome))
        return eventos

    def _mudar(self, h: Habitante, modo: str, agora: float) -> None:
        h.modo = modo
        h.replanejar = True
        if modo in ("trabalho", "erro"):
            h.pausa_ate = 0.0          # trabalho nao espera fim de papo

    def _mais_perto_de_folga(self, nome: str) -> Habitante | None:
        destino = self.g.nos[f"porta:{nome}"]
        candidatos = [h for h in self.habitantes.values()
                      if h.nome != nome and h.modo == "passeio"]
        if not candidatos:
            return None
        return min(candidatos, key=lambda h: (
            math.hypot(h.pos[0] - destino[0], h.pos[1] - destino[1]),
            h.nome))

    # ------------------------------------------------------------ o tempo
    def tick(self, dt: float, agora: float) -> list:
        eventos = []
        dt = max(0.0, min(dt, 0.25))
        for h in self.habitantes.values():
            eventos += self._andar(h, dt, agora)
        eventos += self._encontros(agora)
        return eventos

    def _parado_num_no(self, h: Habitante) -> bool:
        return not h.rota

    def _andar(self, h: Habitante, dt: float, agora: float) -> list:
        eventos = []
        if h.replanejar and self._parado_num_no(h):
            h.replanejar = False
            h.atividade, h.ate, h.destino_ponto = "", 0.0, ""
            if h.emote == "💧" and h.modo != "erro":
                h.emote_ate = 0.0
            h.rota = []
        if h.pausa_ate > agora:
            h.andando = False
            return eventos
        if not h.rota:
            if h.atividade and h.ate > agora:
                h.andando = False
                return eventos
            eventos += self._decidir(h, agora)
        if not h.rota:
            h.andando = False
            return eventos
        alvo = self.g.nos[h.rota[0]]
        dx, dy = alvo[0] - h.pos[0], alvo[1] - h.pos[1]
        dist = math.hypot(dx, dy)
        vel = (self.VEL_TRABALHO if h.modo in ("trabalho", "erro", "consolar")
               else self.VEL_PASSEIO)
        passo = vel * dt
        h.andando = True
        h.passo_t += dt
        if abs(dx) > 0.5:
            h.direcao = "dir" if dx > 0 else "esq"
        if dist <= passo:
            h.pos = [alvo[0], alvo[1]]
            h.no = h.rota.pop(0)
            if h.replanejar:
                h.rota = []
            if not h.rota:
                h.andando = False
                eventos.append(("chegou", h.nome, h.no))
        else:
            h.pos[0] += dx / dist * passo
            h.pos[1] += dy / dist * passo
        return eventos

    def _ir(self, h: Habitante, destino: str) -> None:
        h.rota = self.g.caminho(h.no, destino)

    def _decidir(self, h: Habitante, agora: float) -> list:
        eventos = []
        if h.modo in ("trabalho", "erro"):
            porta = f"porta:{h.nome}"
            if h.no != porta:
                h.atividade = ""
                self._ir(h, porta)
            else:
                h.atividade = "trabalhar" if h.modo == "trabalho" else "triste"
                h.ate = INF
                h.direcao = "dir"
                if h.modo == "erro":
                    self.emocionar(h, "💧", agora, 999999)
            return eventos
        if h.modo == "comemorar":
            if h.atividade == "comemorar":         # ja comemorou
                h.modo, h.atividade = "passeio", ""
                return eventos
            if h.no != "poi:fonte":
                self._ir(h, "poi:fonte")
            else:
                h.atividade, h.ate = "comemorar", agora + 3.0
                self.emocionar(h, "✨", agora, 3.0)
                self.pular(h, agora)
                eventos.append(("comemorou", h.nome))
            return eventos
        if h.modo == "consolar":
            if h.atividade == "consolar":
                h.modo, h.atividade, h.alvo = "passeio", "", ""
                return eventos
            porta = f"porta:{h.alvo}"
            if h.alvo not in self.habitantes or \
                    self._status.get(h.alvo) != "erro":
                h.modo, h.alvo = "passeio", ""
                return eventos
            if h.no != porta:
                self._ir(h, porta)
            else:
                h.atividade, h.ate = "consolar", agora + 5.0
                self.emocionar(h, "🤗", agora, 5.0)
                eventos.append(("consolou", h.nome, h.alvo))
            return eventos
        # PASSEIO. Chegou ao ponto escolhido: faz a coisa de la.
        if h.destino_ponto and h.no == no_do_ponto(h.destino_ponto):
            ponto, h.destino_ponto = h.destino_ponto, ""
            _pos, _rua, atividade, emotes = PONTOS[ponto]
            h.atividade = atividade
            h.ate = agora + self.rnd.uniform(8.0, 18.0)
            h.ultimo_ponto = ponto
            emoji = self.rnd.choice(emotes)
            if emoji:
                self.emocionar(h, emoji, agora + self.rnd.uniform(.3, 1.5),
                               2.5)
            if atividade == "olhar":
                h.direcao = self.rnd.choice(("dir", "esq"))
            eventos.append(("atividade", h.nome, atividade))
            return eventos
        if h.atividade:                     # acabou a atividade: respira
            h.atividade = ""
            return eventos
        opcoes = [p for p in ATIVIDADES_DE_PASSEIO if p != h.ultimo_ponto]
        h.destino_ponto = self.rnd.choice(opcoes)
        self._ir(h, no_do_ponto(h.destino_ponto))
        return eventos

    def _encontros(self, agora: float) -> list:
        eventos = []
        livres = [h for h in self.habitantes.values()
                  if h.modo == "passeio" and h.andando
                  and h.conversa_livre <= agora and h.pausa_ate <= agora]
        usados = set()
        for i, a in enumerate(livres):
            if a.nome in usados:
                continue
            for b in livres[i + 1:]:
                if b.nome in usados:
                    continue
                if math.hypot(a.pos[0] - b.pos[0],
                              a.pos[1] - b.pos[1]) > self.RAIO_DE_ENCONTRO:
                    continue
                for h, outro in ((a, b), (b, a)):
                    h.pausa_ate = agora + self.PAUSA_DE_PAPO
                    h.conversa_livre = agora + self.INTERVALO_DE_PAPO
                    h.direcao = "dir" if outro.pos[0] >= h.pos[0] else "esq"
                    self.emocionar(h, self.rnd.choice(PAPO), agora,
                                   self.PAUSA_DE_PAPO)
                usados |= {a.nome, b.nome}
                eventos.append(("encontro", a.nome, b.nome))
                break
        return eventos

    # ------------------------------------------------------------- toques
    def emocionar(self, h: Habitante, simbolo: str, desde: float,
                  duracao: float) -> None:
        h.emote = simbolo
        h.emote_desde = desde
        h.emote_ate = desde + duracao

    def pular(self, h: Habitante, agora: float) -> None:
        h.pulo_ini = agora

    def clique(self, nome: str, agora: float) -> str:
        """O personagem pula e diz o que esta fazendo."""
        h = self.habitantes[nome]
        self.pular(h, agora)
        rotulo = arte_rotulo(nome)
        if h.modo == "trabalho":
            texto = f"{rotulo}: {h.balao or 'trabalhando'}"
        elif h.modo == "erro":
            texto = f"{rotulo}: deu erro — {h.balao or 'veja o prédio'}"
        elif h.modo == "consolar":
            texto = f"{rotulo}: indo animar o {arte_rotulo(h.alvo)}"
        elif h.modo == "comemorar":
            texto = f"{rotulo}: acabou um trabalho!"
        else:
            texto = f"{rotulo}: de folga — {DESCRICAO.get(h.atividade, 'passeando')}"
        h.info, h.info_ate = texto, agora + 3.5
        return texto

    def publicou(self, agora: float) -> list:
        """Saiu uma publicacao: quem esta de folga comemora."""
        nomes = []
        for h in self.habitantes.values():
            if h.modo == "passeio":
                self.emocionar(h, "🎉", agora, 3.0)
                self.pular(h, agora + self.rnd.uniform(0, .6))
                nomes.append(h.nome)
        return nomes

    # ------------------------------------------------------------- desenho
    def pose(self, h: Habitante, agora: float) -> tuple:
        """(pose, olhos, direcao, altura_do_pulo) para a cena desenhar."""
        if h.andando and h.pausa_ate <= agora:
            pose = "passo1" if int(h.passo_t / .16) % 2 == 0 else "passo2"
        else:
            pose = {"sentado": "sentado", "regar": "trabalhar",
                    "patos": "acenar", "trabalhar": "trabalhar",
                    "triste": "triste", "comemorar": "feliz",
                    "consolar": "acenar"}.get(h.atividade, "parado")
            if h.pausa_ate > agora:
                pose = "acenar"
        # piscar: 0,14 s a cada ~3,7 s, defasado por habitante
        ciclo = (agora + h.fase) % 3.7
        olhos = "fechados" if ciclo < .14 and pose != "feliz" else "abertos"
        direcao = h.direcao
        if h.atividade == "olhar" and not h.andando:
            direcao = "dir" if int((agora + h.fase) / 1.6) % 2 else "esq"
        dt = agora - h.pulo_ini
        pulo = 12 * math.sin(math.pi * dt / .5) if 0 <= dt < .5 else 0.0
        if h.atividade == "comemorar" and 0 <= (agora % .8) < .4:
            pulo = max(pulo, 6 * math.sin(math.pi * (agora % .8) / .4))
        return pose, olhos, direcao, pulo

    def posicao_de_desenho(self, h: Habitante) -> tuple:
        x, y = h.pos
        if not h.andando and h.modo not in ("trabalho", "erro"):
            x += h.desvio
        if h.modo == "consolar" and not h.andando:
            x += 14
        return x, y


DESCRICAO = {
    "sentado": "sentado no banco", "olhar": "olhando a vila",
    "regar": "regando as flores", "patos": "dando comida aos patos",
    "descansar": "descansando em casa", "": "passeando",
    "comemorar": "comemorando", "consolar": "animando um amigo",
}


def arte_rotulo(nome: str) -> str:
    from .dados import rotulo
    return rotulo(nome)


__all__ = ["DESCRICAO", "Grafo", "Habitante", "PONTOS", "Vida",
           "lotes_px", "montar_grafo", "no_do_ponto"]
