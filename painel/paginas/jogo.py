# -*- coding: utf-8 -*-
"""Paginas do JOGO: simulacao, banco de dados e live.

As tres tem a mesma forma -- cartoes com botoes que rodam uma ferramenta do
`neural_fights` por linha de comando. No painel antigo cada uma montava o seu
argv na mao (`[PY, "-m", "neural_fights..."]` aparecia doze vezes); aqui a
lista de acoes e DADO, e quem executa e um so.
"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from .. import estilo

RAIZ = Path(__file__).resolve().parents[2]
PY = sys.executable


class _Base:
    """O que as tres compartilham: rodar um modulo do jogo."""

    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema

    def rodar(self, argumentos: list, rotulo: str = "") -> None:
        self.casca.supervisor.rodar([PY, "-u", "-X", "utf8"] + argumentos,
                                    cwd=RAIZ, rotulo=rotulo)

    def _linha(self, pai):
        linha = tk.Frame(pai, bg=pai.cget("bg"))
        linha.pack(anchor="w")
        return linha


class Simulacao(_Base):
    chave = "simulacao"
    rotulo = "Simulação"
    icone = "⚔"

    ABRIR = (
        ("🕹  Launcher", ["-m", "neural_fights.cli.main"]),
        ("🤖  IA vs IA", ["-m", "neural_fights.cli.main", "--sim"]),
        ("🎮  Teste manual", ["-m", "neural_fights.cli.main", "--test"]),
        ("🏆  Torneio", ["-m", "neural_fights.cli.tournament"]),
    )

    def construir(self, pai) -> None:
        self.o.titulo(pai, "Simulação")

        cartao = self.o.cartao(pai, "Abrir — cada um em janela própria do jogo")
        cartao.pack(fill="x", padx=estilo.ESPACO["secao"],
                    pady=estilo.ESPACO["meio"])
        linha = self._linha(cartao.corpo)
        for texto, argumentos in self.ABRIR:
            self.o.botao(linha, texto,
                         lambda a=argumentos, t=texto: self.rodar(a, t)).pack(
                side="left", padx=(0, estilo.ESPACO["meio"]))

        sem_janela = self.o.cartao(
            pai, "Headless — sem janela, relatório no console")
        sem_janela.pack(fill="x", padx=estilo.ESPACO["secao"],
                        pady=estilo.ESPACO["meio"])
        linha = self._linha(sem_janela.corpo)
        self.o.rotulo(linha, "Modo:", cor="texto_fraco",
                      bg=self.t.superficie).pack(side="left",
                                                 padx=(0, estilo.ESPACO["meio"]))
        self.combo = self.o.combo(linha, ["rapido", "stress", "all"],
                                  "rapido", largura=8)
        self.combo.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        for nome, largura, atributo in (("Seed:", 10, "seed"),
                                        ("P1:", 16, "p1"), ("P2:", 16, "p2")):
            moldura, variavel = self.o.campo(linha, nome, largura)
            moldura.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
            setattr(self, f"var_{atributo}", variavel)
        self.o.botao(sem_janela.corpo, "▶  Rodar headless", self.headless,
                     tipo="primario").pack(anchor="w",
                                           pady=(estilo.ESPACO["normal"], 0))

    def headless(self) -> None:
        extras = ["--mode", self.combo.get()]
        for bandeira, variavel in (("--seed", self.var_seed),
                                   ("--p1", self.var_p1), ("--p2", self.var_p2)):
            valor = variavel.get().strip()
            if valor:
                extras += [bandeira, valor]
        self.rodar(["-m", "neural_fights.cli.headless"] + extras,
                   "simulação headless")


class Database(_Base):
    chave = "database"
    rotulo = "Database"
    icone = "🗃"

    def construir(self, pai) -> None:
        self.o.titulo(pai, "Database do Neural Fights")

        ver = self.o.cartao(pai, "Consultar")
        ver.pack(fill="x", padx=estilo.ESPACO["secao"],
                 pady=estilo.ESPACO["meio"])
        linha = self._linha(ver.corpo)
        self.o.botao(linha, "📋  Ver banco atual",
                     lambda: self.rodar(
                         ["-m", "neural_fights.tools.resumo_banco"],
                         "resumo do banco"), tipo="primario").pack(side="left")
        for texto, modulo in (("🗡  Análise das armas",
                               "neural_fights.tools.analise_armas"),
                              ("🥊  Qualidade de luta",
                               "neural_fights.tools.qualidade_luta")):
            self.o.botao(linha, texto,
                         lambda m=modulo, t=texto: self.rodar(["-m", m], t)
                         ).pack(side="left", padx=(estilo.ESPACO["meio"], 0))

        roster = self.o.cartao(pai, "Roster")
        roster.pack(fill="x", padx=estilo.ESPACO["secao"],
                    pady=estilo.ESPACO["meio"])
        linha = self._linha(roster.corpo)
        self.o.rotulo(linha, "Modo:", cor="texto_fraco",
                      bg=self.t.superficie).pack(
            side="left", padx=(0, estilo.ESPACO["meio"]))
        self.combo = self.o.combo(linha, ["completo", "64", "16"], "64",
                                  largura=10)
        self.combo.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        moldura, self.var_seed = self.o.campo(linha, "Seed:", 10)
        moldura.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        self.o.botao(linha, "Gerar roster", self.roster).pack(side="left")

        perigo = self.o.zona_de_perigo(
            pai, "Regenerar APAGA o banco atual — os personagens que os "
                 "vídeos de build criaram são perdidos, e não tem volta.")
        perigo.pack(fill="x", padx=estilo.ESPACO["secao"],
                    pady=estilo.ESPACO["secao"])
        self.o.botao(perigo.corpo, "⚠  REGENERAR DATABASE INTEIRA",
                     self.regenerar, tipo="perigo").pack(anchor="w")

    def roster(self) -> None:
        extras = ["--modo", self.combo.get()]
        if self.var_seed.get().strip():
            extras += ["--seed", self.var_seed.get().strip()]
        self.rodar(["-m", "neural_fights.cli.roster"] + extras, "roster")

    def regenerar(self) -> None:
        # Duas perguntas de proposito: a primeira explica, a segunda confirma.
        # Apagar o banco perde trabalho que levou dias para existir.
        if not messagebox.askyesno(
                "Regenerar database",
                "Isso APAGA o banco atual e gera um novo do zero.\n"
                "Os personagens inseridos pelos vídeos serão perdidos.\n\n"
                "Continuar?"):
            return
        if not messagebox.askyesno("Regenerar database",
                                   "Certeza MESMO? Não tem volta."):
            return
        self.rodar(["-m", "neural_fights.tools.gerador_database"],
                   "regenerar database")


class Live(_Base):
    chave = "live"
    rotulo = "Live / YouTube"
    icone = "🔴"

    def construir(self, pai) -> None:
        self.o.titulo(pai, "Live / YouTube")

        show = self.o.cartao(pai, "Iniciar live")
        show.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=estilo.ESPACO["meio"])
        linha = self._linha(show.corpo)
        moldura, self.var_video = self.o.campo(
            linha, "ID do vídeo (vazio = consultar a conta):", 20)
        moldura.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        caixa, self.var_vertical = self.o.marcador(linha, "vertical (9:16)")
        caixa.pack(side="left", padx=(0, estilo.ESPACO["meio"]))
        caixa, self.var_gravar = self.o.marcador(linha,
                                                 "gravar eventos (.jsonl)")
        caixa.pack(side="left")

        botoes = tk.Frame(show.corpo, bg=self.t.superficie)
        botoes.pack(anchor="w", pady=(estilo.ESPACO["normal"], 0))
        self.o.botao(botoes, "🔴  LIVE COM CHAT DO YOUTUBE", self.com_chat,
                     tipo="primario").pack(side="left")
        self.o.botao(botoes, "▶  Só o show (sem chat)", self.so_show).pack(
            side="left", padx=(estilo.ESPACO["normal"], 0))

        replay = self.o.cartao(pai, "Replay de eventos gravados")
        replay.pack(fill="x", padx=estilo.ESPACO["secao"],
                    pady=estilo.ESPACO["meio"])
        linha = self._linha(replay.corpo)
        self.var_arquivo = tk.StringVar()
        tk.Entry(linha, textvariable=self.var_arquivo, width=46,
                 bg=self.t.superficie_alta, fg=self.t.texto, relief="flat",
                 insertbackground=self.t.texto, font=self.t.letra("corpo"),
                 highlightthickness=1, highlightbackground=self.t.borda,
                 highlightcolor=self.t.acento).pack(side="left", ipady=3)
        self.o.botao(linha, "Escolher .jsonl…", self.escolher).pack(
            side="left", padx=estilo.ESPACO["meio"])
        caixa, self.var_loop = self.o.marcador(linha, "loop")
        caixa.pack(side="left")
        self.o.botao(linha, "▶  Replay", self.replay).pack(
            side="left", padx=estilo.ESPACO["meio"])

        oauth = self.o.cartao(
            pai, "Credenciais do YouTube — uma vez só, do Google Cloud Console")
        oauth.pack(fill="x", padx=estilo.ESPACO["secao"],
                   pady=estilo.ESPACO["meio"])
        linha = self._linha(oauth.corpo)
        moldura, self.var_id = self.o.campo(linha, "client-id:", 28)
        moldura.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        moldura, self.var_segredo = self.o.campo(linha, "client-secret:", 22)
        moldura.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        self.o.botao(linha, "Configurar OAuth", self.oauth).pack(side="left")

    def _extras(self) -> list:
        return ["--portrait"] if self.var_vertical.get() else []

    def so_show(self) -> None:
        self.rodar(["-m", "neural_fights.cli.live", "--source", "nenhuma"]
                   + self._extras(), "live sem chat")

    def com_chat(self) -> None:
        extras = ["--source", "youtube"] + self._extras()
        if self.var_video.get().strip():
            extras += ["--video-id", self.var_video.get().strip()]
        if self.var_gravar.get():
            extras += ["--gravar-eventos", "live_eventos.jsonl"]
        self.rodar(["-m", "neural_fights.cli.live"] + extras, "live com chat")

    def escolher(self) -> None:
        from tkinter import filedialog
        arquivo = filedialog.askopenfilename(
            title="Arquivo de eventos",
            filetypes=[("JSON Lines", "*.jsonl"), ("Todos", "*.*")])
        if arquivo:
            self.var_arquivo.set(arquivo)

    def replay(self) -> None:
        caminho = self.var_arquivo.get().strip()
        if not caminho:
            messagebox.showwarning("Replay", "Escolha o arquivo .jsonl "
                                             "primeiro.")
            return
        extras = ["--source", "replay", "--events", caminho]
        if self.var_loop.get():
            extras.append("--loop-events")
        self.rodar(["-m", "neural_fights.cli.live"] + extras, "replay")

    def oauth(self) -> None:
        identificador = self.var_id.get().strip()
        segredo = self.var_segredo.get().strip()
        if not identificador or not segredo:
            messagebox.showwarning("OAuth",
                                   "Preencha client-id e client-secret.")
            return
        # O rotulo NAO leva as credenciais: ele vai para o console, que fica
        # na tela e pode acabar numa captura.
        self.casca.supervisor.rodar(
            [PY, "-u", "-X", "utf8", "-m", "neural_fights.tools.youtube_oauth",
             "--client-id", identificador, "--client-secret", segredo],
            cwd=RAIZ, rotulo="youtube_oauth (credenciais ocultas)")


__all__ = ["Database", "Live", "Simulacao"]
