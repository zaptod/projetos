# -*- coding: utf-8 -*-
"""Pagina VILA: o mundo, e o que esta acontecendo nele AGORA.

E o painel principal por escolha dele. Aqui a cara e quente e o pixel art e
o protagonista -- a moldura recua para o mundo saltar.

O QUE MUDOU EM RELACAO A VERSAO ANTIGA, e nao e enfeite:

  A VILA MENTIA. `publicar/tiktok.py` e `publicar/youtube_web.py` nao
  escreviam no diario, entao a fabrica "publicacao" ficava OCIOSA durante
  quase todo upload real. Corrigido na etapa 2; aqui a consequencia aparece.

  O PLACAR ERA CONTAGEM DE LINHA. "32 publicados" saia de contar as linhas
  de dois arquivos, o que conta tambem o que falhou. Agora vem do
  `panorama`, o MESMO dicionario que as outras telas leem.

  HAVIA UM SEGUNDO MAPA. O painel guardava um desenho vetorial proprio, com
  as sete fabricas em coordenadas de pixel, que NAO vinha do
  `vila/config.json`. Ele servia de reserva quando faltava Pillow -- e
  mostrava um mundo DIFERENTE do real. Reserva que mostra outro mundo
  contradiz a unica coisa que a Vila promete. Foi apagado: sem cenario,
  aparece um convite explicito para gerar um.

  OS EFEITOS EXISTIAM E NAO ERAM USADOS. `fx.trabalho` e `fx.erro` estavam
  definidos e documentados no motor desde o inicio, sem nenhum chamador.
"""
from __future__ import annotations

import math
import sys
import time
import tkinter as tk
from pathlib import Path

from builds import atividade

from .. import estilo
from ..processos import Periodico

RAIZ = Path(__file__).resolve().parents[2]
PY = sys.executable

# De quanto em quanto os bots redesenham. 60 ms e o que da caminhada fluida
# sem pesar; so roda com a pagina VISIVEL.
PASSO_MS = 60
LEITURA_MS = 3500


class Pagina:
    chave = "vila"
    rotulo = "Vila"
    icone = "🏘"

    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema
        self._bots: dict = {}
        self._fotos: dict = {}
        self._filtro: str | None = None
        self._visivel = False
        self._escala: int | None = None
        self._motor = None
        self._animacao = None
        self._leitura = None

    # ------------------------------------------------------------ montar
    def construir(self, pai) -> None:
        topo = tk.Frame(pai, bg=self.t.fundo)
        topo.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=(estilo.ESPACO["muito"], estilo.ESPACO["meio"]))
        self.lbl_placar = self.o.rotulo(topo, "…", papel="secao",
                                        peso="bold")
        self.lbl_placar.pack(side="left")
        for texto, acao in (("↻", self.recarregar),
                            ("➕", lambda: self.zoom(1)),
                            ("➖", lambda: self.zoom(-1))):
            self.o.botao(topo, texto, acao, compacto=True).pack(
                side="right", padx=(estilo.ESPACO["pouco"], 0))
        self.o.botao(topo, "🎨  Oficina", self.oficina).pack(
            side="right", padx=(estilo.ESPACO["normal"], 0))
        self.o.botao(topo, "🤖  Bot do celular", self.bot).pack(side="right")

        self.canvas = tk.Canvas(pai, height=300, bg=self.t.superficie,
                                highlightthickness=1,
                                highlightbackground=self.t.borda)
        self.canvas.pack(fill="x", padx=estilo.ESPACO["secao"])

        # --- diario
        rodape = tk.Frame(pai, bg=self.t.fundo)
        rodape.pack(fill="both", expand=True, padx=estilo.ESPACO["secao"],
                    pady=(estilo.ESPACO["normal"], 0))
        cabeca = tk.Frame(rodape, bg=self.t.fundo)
        cabeca.pack(fill="x")
        self.lbl_filtro = self.o.secao(cabeca, "Diário")
        self.lbl_filtro.pack(side="left")
        self.o.legenda(cabeca, "clique num prédio para filtrar").pack(
            side="left", padx=estilo.ESPACO["meio"])
        self.o.botao(cabeca, "todas", self.sem_filtro, compacto=True).pack(
            side="right")
        self.texto = tk.Text(rodape, height=6, bg=self.t.console_fundo,
                             fg=self.t.console_texto, font=self.t.letra("mono"),
                             relief="flat", bd=0, state="disabled",
                             wrap="none", padx=estilo.ESPACO["meio"],
                             pady=estilo.ESPACO["pouco"])
        self.texto.pack(fill="both", expand=True,
                        pady=(estilo.ESPACO["meio"], 0))
        for marca, cor in (("erro", self.t.erro), ("ok", self.t.ok),
                           ("inicio", self.t.aviso)):
            self.texto.tag_configure(marca, foreground=cor)

        self._paralelismo(pai)
        self.montar_cenario()

    def _paralelismo(self, pai) -> None:
        """Quem divide pasta com quem — a serializacao que ninguem ve.

        Uma trava usada por DOIS canais e um lugar onde o paralelismo
        prometido nao acontece. Isso e CONFIGURACAO, nao codigo: o valor de
        mostrar aqui e poder agir.
        """
        area = tk.Frame(pai, bg=self.t.fundo)
        area.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=(estilo.ESPACO["normal"], estilo.ESPACO["normal"]))
        cabeca = tk.Frame(area, bg=self.t.fundo)
        cabeca.pack(fill="x")
        self.o.secao(cabeca, "Paralelismo").pack(side="left")
        self.o.legenda(cabeca, "uma pasta de perfil = uma fila").pack(
            side="left", padx=estilo.ESPACO["meio"])
        self.lbl_paralelo = self.o.legenda(cabeca, "")
        self.lbl_paralelo.pack(side="right")
        self.tabela = self.o.tabela(area, [
            ("servico", "SERVIÇO", 110, "w"),
            ("canais", "USADA POR", 170, "w"),
            ("estado", "AGORA", 90, "w"),
            ("perfil", "PASTA DO PERFIL", 380, "w"),
        ], altura=4, estica="perfil")
        self.tabela.tag_configure("ocupada", foreground=self.t.aviso)
        self.tabela.tag_configure("dividida", foreground=self.t.erro)
        self.tabela.pack(fill="x", pady=(estilo.ESPACO["meio"], 0))

    # ---------------------------------------------------------- cenario
    def montar_cenario(self) -> None:
        self.canvas.delete("all")
        self._bots.clear()
        self._fotos.clear()
        if not self._montar_sprites():
            self._sem_cenario()

    def _sem_cenario(self) -> None:
        """Estado vazio EXPLICITO, no lugar do segundo mapa divergente."""
        self.canvas.create_text(
            440, 130, text="A vila ainda não tem cenário.",
            font=self.t.letra("titulo", "bold"), fill=self.t.texto)
        self.canvas.create_text(
            440, 165,
            text="Gere um mundo base com  python -m vila.gerar_base\n"
                 "ou monte o seu na 🎨 Oficina.",
            font=self.t.letra("corpo"), fill=self.t.texto_fraco,
            justify="center")

    def _montar_sprites(self) -> bool:
        try:
            from PIL import ImageTk

            from vila import motor
        except Exception:
            return False
        try:
            cfg = motor.carregar()
            if not motor.pronto(cfg):
                return False
            if self._escala is None:
                self._escala = int(cfg.get("escala", 2))
            atlas = motor.Atlas(cfg)
            mundo = motor.compor_mundo(cfg, atlas, self._escala)
        except Exception as erro:                            # noqa: BLE001
            self.casca._registrar(f"[vila] o cenário quebrou: {erro}", "erro")
            return False

        self._motor = (motor, cfg, atlas, ImageTk)
        self._fotos["mundo"] = ImageTk.PhotoImage(mundo)
        self.canvas.create_image(0, 0, anchor="nw", image=self._fotos["mundo"])
        self.canvas.configure(scrollregion=(0, 0, mundo.width, mundo.height))

        lado = int(cfg["tile"]) * self._escala
        self._lado = lado
        mapa = cfg["mapa"]
        casa = mapa.get("casa") or {"x": mapa["larg"] // 2,
                                    "y": mapa["alt"] // 2}
        larg_casa, alt_casa = motor.tamanho(cfg, "predio.casa")
        porta = ((casa["x"] + larg_casa / 2) * lado,
                 (casa["y"] + alt_casa) * lado + 4)

        for i, nome in enumerate(motor.FABRICAS):
            pos = (mapa.get("predios") or {}).get(nome)
            base = [porta[0] + (i - 3) * lado * 0.9, porta[1] + lado * 0.6]
            if pos:
                larg, alt = motor.tamanho(cfg, f"predio.{nome}")
                trabalho = [(pos["x"] + larg / 2) * lado,
                            (pos["y"] + alt) * lado + 4]
                # O EFEITO em cima do predio: `fx.trabalho` e `fx.erro`
                # existiam no motor desde o inicio e nenhum chamador os
                # usava. Sao exatamente o sinal visual do estado.
                self.canvas.create_image(trabalho[0], pos["y"] * lado,
                                         anchor="s", tags=(f"fx_{nome}",))
                self.canvas.create_text(trabalho[0], trabalho[1] + 12, text="",
                                        font=self.t.letra("legenda"),
                                        fill=self.t.acento_forte,
                                        tags=(f"legenda_{nome}",))
            else:
                trabalho = list(base)
            item = self.canvas.create_image(base[0], base[1], anchor="s")
            foto = self._foto_bot(nome, "baixo", 0)
            if foto is not None:
                self.canvas.itemconfigure(item, image=foto)
            balao = self.canvas.create_text(base[0], base[1] - lado * 1.5,
                                            text="",
                                            font=self.t.letra("corpo"))
            self._bots[nome] = {"itens": (item, balao), "pos": list(base),
                                "alvo": list(base), "casa": list(base),
                                "trabalho": trabalho, "direcao": "baixo",
                                "fase": i * 1.3, "balao": ""}

        self.canvas.bind("<Button-1>", self._clique)
        self.canvas.bind("<ButtonPress-3>",
                         lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind("<B3-Motion>",
                         lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        return True

    def _foto(self, papel: str, quadro: int = 0, fabrica=None):
        if self._motor is None:
            return None
        _motor, _cfg, atlas, ImageTk = self._motor
        chave = (papel, fabrica, int(quadro), self._escala)
        if chave in self._fotos:
            return self._fotos[chave]
        try:
            foto = ImageTk.PhotoImage(
                atlas.sprite(papel, int(quadro), self._escala,
                             fabrica=fabrica))
        except Exception:                                    # noqa: BLE001
            foto = None
        self._fotos[chave] = foto
        return foto

    def _foto_bot(self, fabrica: str, direcao: str, quadro: int):
        return self._foto(f"bot.{direcao}", quadro, fabrica=fabrica)

    def _clique(self, evento) -> None:
        if self._motor is None:
            return
        motor, cfg, _atlas, _ = self._motor
        tx = int(self.canvas.canvasx(evento.x) // self._lado)
        ty = int(self.canvas.canvasy(evento.y) // self._lado)
        for nome, pos in (cfg["mapa"].get("predios") or {}).items():
            larg, alt = motor.tamanho(cfg, f"predio.{nome}")
            if pos["x"] <= tx < pos["x"] + larg \
                    and pos["y"] <= ty < pos["y"] + alt:
                self.filtrar(nome)
                return

    def zoom(self, passo: int) -> None:
        if self._motor is None:
            self.casca._registrar(
                "[vila] o zoom é do cenário em sprites — gere um com "
                "python -m vila.gerar_base.", "erro")
            return
        novo = max(1, min(4, (self._escala or 2) + passo))
        if novo != self._escala:
            self._escala = novo
            self.montar_cenario()

    # ------------------------------------------------------------ estado
    def ao_mostrar(self) -> None:
        self._visivel = True
        if self._animacao is None:
            self._animacao = Periodico(self.casca, PASSO_MS, self._passo)
            self._leitura = Periodico(self.casca, LEITURA_MS, self.recarregar)
        self._animacao.ligar()
        self._leitura.ligar()
        self.recarregar()

    def ao_esconder(self) -> None:
        """Desliga a animacao DE VERDADE.

        No painel antigo o temporizador continuava marcado e so a funcao
        desistia; aqui o `Periodico` cancela o agendamento. Sessenta
        milissegundos desenhando o que ninguem ve custa bateria e nada mais.
        """
        self._visivel = False
        for pulso in (self._animacao, self._leitura):
            if pulso is not None:
                pulso.desligar()

    def recarregar(self) -> None:
        self.casca.supervisor.tarefa(self._ler, self._aplicar, rotulo="vila")

    def _ler(self) -> dict:
        return {"por_canal": atividade.estado_por_canal(),
                "fabricas": atividade.estado_das_fabricas(),
                "eventos": atividade.recentes(40, self._filtro)}

    def _aplicar(self, dados: dict) -> None:
        if dados.get("erro"):
            return
        self._diario(dados.get("eventos") or [])
        for nome, info in (dados.get("fabricas") or {}).items():
            bot = self._bots.get(nome)
            if not bot:
                continue
            trabalhando = info["status"] in ("trabalhando", "erro")
            bot["alvo"] = list(bot["trabalho"] if trabalhando else bot["casa"])
            bot["balao"] = ("⚙" if info["status"] == "trabalhando"
                            else "❗" if info["status"] == "erro" else "")
            efeito = ("fx.erro" if info["status"] == "erro"
                      else "fx.trabalho" if info["status"] == "trabalhando"
                      else None)
            foto = self._foto(efeito) if efeito else None
            self.canvas.itemconfigure(f"fx_{nome}", image=foto or "")
            self.canvas.itemconfigure(
                f"legenda_{nome}",
                text=(info.get("detalhe") or "")[:22]
                if info["status"] != "ocioso" else "")

    def atualizar(self, resumo: dict) -> None:
        """O placar vem do agregador, e nao de contagem de linha de arquivo."""
        saude = resumo.get("saude") or {}
        desempenho = resumo.get("desempenho") or {}
        inventario = resumo.get("inventario") or {}
        qualidade = resumo.get("qualidade") or {}

        prontos = (inventario.get("videos_prontos") or {}).get("total", 0)
        trabalhando = len(saude.get("trabalhando") or [])
        problemas = qualidade.get("total_erros", 0)
        self.lbl_placar.configure(
            text=f"📤 {desempenho.get('total', 0)} publicados   ·   "
                 f"🎬 {prontos} prontos   ·   "
                 f"⚙ {trabalhando} trabalhando   ·   "
                 f"⚠ {problemas} problema(s)")

        paralelo = saude.get("paralelismo") or {}
        self.tabela.delete(*self.tabela.get_children())
        for linha in paralelo.get("travas") or []:
            canais = linha.get("canais") or []
            marca = ("dividida" if len(canais) > 1
                     else "ocupada" if linha.get("ocupada") else "")
            self.tabela.insert(
                "", "end",
                values=(linha.get("servico", ""), " + ".join(canais),
                        "em uso" if linha.get("ocupada") else "livre",
                        linha.get("perfil", "")),
                tags=(marca,) if marca else ())
        divididas = len(paralelo.get("divididas") or [])
        self.lbl_paralelo.configure(
            text=f"{paralelo.get('ocupadas', 0)} em uso · {divididas} pasta(s) "
                 "usada(s) por DOIS canais (essas não rodam juntas)",
            fg=self.t.erro if divididas else self.t.texto_fraco)

    def _diario(self, eventos: list) -> None:
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        for evento in eventos:
            hora = str(evento.get("ts", ""))[11:19]
            fabrica = atividade.FABRICAS.get(evento.get("fabrica"), {})
            rotulo = fabrica.get("rotulo", evento.get("fabrica", "?"))
            estado = evento.get("status", "")
            self.texto.insert(
                "end",
                f"{hora}  {rotulo:<11} {evento.get('canal', ''):<10} "
                f"{estado:<7} {evento.get('detalhe', '')}\n",
                estado if estado in ("erro", "ok", "inicio") else "")
        self.texto.configure(state="disabled")

    def _passo(self) -> None:
        """Os bots andam. So com a pagina visivel."""
        if not self._visivel or not self._bots:
            return
        agora = time.monotonic()
        for nome, bot in self._bots.items():
            px, py = bot["pos"]
            ax, ay = bot["alvo"]
            dx, dy = ax - px, ay - py
            distancia = (dx * dx + dy * dy) ** 0.5
            andando = distancia > 2
            if andando:
                passo = min(3.2, distancia)
                px += dx / distancia * passo
                py += dy / distancia * passo
                bot["direcao"] = (("dir" if dx > 0 else "esq")
                                  if abs(dx) > abs(dy)
                                  else ("baixo" if dy > 0 else "cima"))
            bob = math.sin(agora * 6 + bot["fase"]) * (2 if andando else 0.8)
            bot["pos"] = [px, py]
            foto = self._foto_bot(nome, bot["direcao"],
                                  int(agora * 6) % 2 if andando else 0)
            item, balao = bot["itens"]
            if foto is not None:
                self.canvas.itemconfigure(item, image=foto)
            self.canvas.coords(item, px, py + bob)
            self.canvas.coords(balao, px, py - self._lado * 1.5 + bob)
            self.canvas.itemconfigure(balao, text=bot.get("balao", ""))

    # ------------------------------------------------------------ acoes
    def filtrar(self, fabrica: str) -> None:
        self._filtro = fabrica
        rotulo = atividade.FABRICAS.get(fabrica, {}).get("rotulo", fabrica)
        self.lbl_filtro.configure(text=f"DIÁRIO — {rotulo.upper()}")
        self.recarregar()

    def sem_filtro(self) -> None:
        self._filtro = None
        self.lbl_filtro.configure(text="DIÁRIO")
        self.recarregar()

    def oficina(self) -> None:
        self.casca.supervisor.rodar([PY, "-X", "utf8", "-m", "vila.editor"],
                                    cwd=RAIZ, rotulo="Oficina de sprites",
                                    depois=self.montar_cenario)

    def bot(self) -> None:
        self.casca.supervisor.rodar([PY, "-u", "-X", "utf8", "-m", "remoto"],
                                    cwd=RAIZ, rotulo="bot do Telegram")


__all__ = ["Pagina"]
