# -*- coding: utf-8 -*-
"""Pagina ESPELHO: absorver um canal alheio e devolver a biblia dele.

Projeto separado (pasta `mimetizar/`, pacote `espelho`), controlado daqui.
E o unico dos seis que ESTUDA em vez de produzir: aponta para um canal que
ja funciona, mede o que ele faz, poe o ChatGPT e o Gemini para lerem cada
video, e escreve o manual mais um preset que o `historias/` consome.

Duas coisas nao sao um clique so, de proposito:

  BAIXAR   o acervo de um canal grande passa de dezenas de GB. O botao
           manda `--limite`, e o teto de espaco continua valendo na CLI.
  PRESET   sai na pasta do canal, e a copia para `historias/config/` e um
           ato humano. Sobrescrever o formato de um canal que ja funciona
           sem alguem olhar seria trocar uma coisa que da certo por outra,
           em silencio.

A lista vem de `espelho.status` por IMPORT DIRETO — o modulo so le disco e
nao arrasta patchright nem yt-dlp junto (eles sao importados tarde, dentro
dos comandos). O trabalho pesado vai por subprocesso, como no resto do
painel: quem trabalha publica na fila, quem desenha le a fila.
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from .. import estilo

RAIZ = Path(__file__).resolve().parents[2]
MIMETIZAR = RAIZ / "mimetizar"
PY = sys.executable


class Pagina:
    chave = "mimetizar"
    rotulo = "Espelho"
    icone = "🪞"

    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema

    # ------------------------------------------------------------ montar
    def construir(self, pai) -> None:
        self.o.titulo(pai, "Espelho — absorver um canal e escrever a bíblia dele")
        if not MIMETIZAR.is_dir():
            self.o.rotulo(pai, "A pasta mimetizar/ não existe ao lado do painel.",
                          cor="erro", peso="bold").pack(
                anchor="w", padx=estilo.ESPACO["secao"])
            return

        novo = self.o.cartao(
            pai, "1. Catalogar — lê o acervo do canal sem baixar nada")
        novo.pack(fill="x", padx=estilo.ESPACO["secao"])
        linha = tk.Frame(novo.corpo, bg=self.t.superficie)
        linha.pack(anchor="w", fill="x")
        moldura, self.var_url = self.o.campo(
            linha, "URL do canal:", 42)
        moldura.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        self.o.botao(linha, "🔎  Catalogar", self.catalogar,
                     tipo="primario").pack(side="left")
        self.o.legenda(
            novo.corpo,
            "https://www.youtube.com/@nome — ou só @nome. Sai a contagem de "
            "vídeos e a estimativa de espaço antes de baixar qualquer coisa."
        ).pack(anchor="w", pady=(estilo.ESPACO["pouco"], 0))

        pipeline = self.o.cartao(
            pai, "2. Absorver — baixa, as duas IAs leem ao mesmo tempo, "
                 "e o vídeo é apagado")
        pipeline.pack(fill="x", padx=estilo.ESPACO["secao"],
                      pady=(estilo.ESPACO["meio"], 0))
        acoes = tk.Frame(pipeline.corpo, bg=self.t.superficie)
        acoes.pack(anchor="w", fill="x")
        self.o.rotulo(acoes, "Vídeos:", cor="texto_fraco",
                      bg=self.t.superficie).pack(
            side="left", padx=(0, estilo.ESPACO["pouco"]))
        moldura_limite, self.var_limite = self.o.campo(acoes, "", 5)
        moldura_limite.pack(side="left", padx=(0, estilo.ESPACO["meio"]))
        self.var_limite.set("30")
        self.o.rotulo(acoes, "Em disco por vez:", cor="texto_fraco",
                      bg=self.t.superficie).pack(
            side="left", padx=(0, estilo.ESPACO["pouco"]))
        moldura_lote, self.var_lote = self.o.campo(acoes, "", 4)
        moldura_lote.pack(side="left", padx=(0, estilo.ESPACO["meio"]))
        self.var_lote.set("4")
        self.o.rotulo(acoes, "IA:", cor="texto_fraco",
                      bg=self.t.superficie).pack(
            side="left", padx=(0, estilo.ESPACO["pouco"]))
        self.combo_provedor = self.o.combo(
            acoes, ["ambos", "chatgpt", "gemini"], "ambos", largura=8)
        self.combo_provedor.pack(side="left",
                                 padx=(0, estilo.ESPACO["normal"]))
        self.o.botao(acoes, "🌀  Absorver", self.absorver,
                     tipo="primario").pack(side="left")
        self.o.legenda(
            pipeline.corpo,
            "O disco fica plano: só o lote atual existe em vídeo, e cada um "
            "é apagado assim que as duas IAs terminam com ele. O que fica é "
            "medida, transcrição, mosaico e ficha — quilobytes por vídeo. "
            "Vídeos: quantos do canal no total (os mais vistos primeiro)."
        ).pack(anchor="w", pady=(estilo.ESPACO["pouco"], 0))

        segunda = tk.Frame(pipeline.corpo, bg=self.t.superficie)
        segunda.pack(anchor="w", fill="x", pady=(estilo.ESPACO["meio"], 0))
        self.o.botao(segunda, "📕  Escrever a bíblia", self.biblia).pack(
            side="left")
        self.o.botao(segunda, "🧩  Gerar preset", self.gerar_preset).pack(
            side="left", padx=(estilo.ESPACO["pouco"], 0))
        self.o.botao(segunda, "🧹  Apagar os vídeos baixados",
                     self.limpar).pack(
            side="left", padx=(estilo.ESPACO["normal"], 0))

        abrir = tk.Frame(pipeline.corpo, bg=self.t.superficie)
        abrir.pack(anchor="w", fill="x", pady=(estilo.ESPACO["meio"], 0))
        self.o.botao(abrir, "📂  Abrir a pasta do canal", self.abrir_pasta).pack(
            side="left")
        self.o.botao(abrir, "📖  Abrir a bíblia", self.abrir_biblia).pack(
            side="left", padx=(estilo.ESPACO["pouco"], 0))
        self.o.botao(abrir, "🔑  Login no LLM", self.login).pack(
            side="left", padx=(estilo.ESPACO["pouco"], 0))

        self.tabela = self.o.tabela(pai, [
            ("canal", "CANAL", 106, "w"),
            ("nome", "NOME", 170, "w"),
            ("videos", "VÍDEOS", 62, "e"),
            ("prontos", "PRONTOS", 70, "e"),
            ("fichas", "FICHAS", 62, "e"),
            ("disco", "EM DISCO", 82, "e"),
            ("proximo", "PRÓXIMO PASSO", 250, "w"),
        ], altura=10, estica="proximo")
        # `o.tabela` CRIA o Treeview e nao o coloca na tela — quem monta
        # empacota. Sem estas duas linhas a pagina sobe inteira, com todos os
        # botoes, e a lista simplesmente nao existe: o smoke so prova que a
        # pagina MONTA, nao que os widgets estao visiveis.
        self.tabela.tag_configure("pronta", foreground=self.t.ok)
        self.tabela.tag_configure("faltando", foreground=self.t.aviso)
        self.tabela.pack(fill="both", expand=True,
                         padx=estilo.ESPACO["secao"])
        self.tabela.bind("<Double-1>", lambda _e: self.abrir_pasta())

    def ao_mostrar(self) -> None:
        self.recarregar()

    def atualizar(self, resumo) -> None:
        """O pulso do painel nao recarrega esta pagina.

        Contar arquivo em disco de um acervo de centenas de videos a cada 4
        segundos custaria mais que a informacao vale. Recarrega ao entrar na
        pagina e ao fim de cada comando, que e quando muda.
        """

    # ------------------------------------------------------------- ler
    def recarregar(self) -> None:
        self.casca.supervisor.tarefa(self._ler, self._desenhar,
                                     rotulo="espelho")

    @staticmethod
    def _ler() -> list:
        from espelho import status
        return status.todos()

    def _desenhar(self, linhas) -> None:
        if isinstance(linhas, dict):
            self.casca._registrar(f"[espelho] {linhas.get('erro')}", "erro")
            return
        escolhido = self.tabela.selection()
        self.tabela.delete(*self.tabela.get_children())
        for dado in linhas or []:
            pronto = dado["preset"] and dado["biblia"]
            disco = dado["em_disco"]
            ocupado = (f"{disco['videos']} · {disco['mb']:.0f}MB"
                       if disco["videos"] else "—")
            self.tabela.insert(
                "", "end", iid=dado["canal_id"],
                tags=("pronta" if pronto else "faltando",),
                values=(dado["canal_id"], dado["nome"][:40], dado["n_videos"],
                        dado["completos"], dado["fichas_total"], ocupado,
                        dado["proximo_passo"]))
        if escolhido and self.tabela.exists(escolhido[0]):
            self.tabela.selection_set(escolhido)

    # ---------------------------------------------------------- acoes
    def cli(self, argumentos: list, rotulo: str) -> None:
        self.casca.supervisor.rodar(
            [PY, "-u", "-X", "utf8", "main.py"] + argumentos, cwd=MIMETIZAR,
            rotulo=rotulo, depois=self.recarregar)

    def selecionado(self):
        return self.o.selecionado(self.tabela, "Escolha um canal na lista.")

    def _limite(self) -> list:
        bruto = (self.var_limite.get() or "").strip()
        if not bruto:
            return []
        try:
            valor = int(bruto)
        except ValueError:
            messagebox.showinfo("Espelho", "O limite precisa ser um número.")
            return []
        return ["--limite", str(valor)] if valor > 0 else []

    def catalogar(self) -> None:
        url = (self.var_url.get() or "").strip()
        if not url:
            messagebox.showinfo("Espelho", "Cole a URL do canal primeiro.")
            return
        self.cli(["canal", url], "catalogar canal")

    def absorver(self) -> None:
        canal_id = self.selecionado()
        if canal_id is None:
            return
        provedor = self.combo_provedor.get()
        lote = (self.var_lote.get() or "4").strip()
        if not lote.isdigit() or int(lote) < 1:
            messagebox.showinfo("Espelho",
                                "Quantos ficam em disco por vez precisa ser "
                                "um número maior que zero.")
            return
        self.casca._registrar(
            f"[espelho] absorvendo com {provedor} — o Chrome abre "
            f"{'duas janelas' if provedor == 'ambos' else 'uma janela'} e "
            "cada vídeo é apagado assim que as fichas saem. Leva horas num "
            "acervo grande, e retoma de onde parar.")
        self.cli(["absorver", canal_id, "--provedor", provedor,
                  "--lote", lote] + self._limite(), f"absorver ({provedor})")

    def limpar(self) -> None:
        """Apaga os videos que sobraram, sem tocar no derivado."""
        canal_id = self.selecionado()
        if canal_id is None:
            return
        from espelho import absorver as modulo
        try:
            disco = modulo.em_disco(canal_id)
        except Exception as erro:                              # noqa: BLE001
            messagebox.showinfo("Espelho", f"Não consegui olhar o disco: {erro}")
            return
        if not disco["videos_em_disco"]:
            messagebox.showinfo("Espelho",
                                "Não há vídeo ocupando disco neste canal.")
            return
        if not messagebox.askyesno(
                "Apagar os vídeos baixados",
                f"Apagar {disco['videos_em_disco']} arquivo(s) de vídeo "
                f"({disco['mb']:.0f} MB) deste canal?\n\n"
                "As medidas, transcrições, mosaicos e fichas FICAM — só o "
                "mp4 sai. Um vídeo apagado volta a ser baixado se você pedir "
                "para analisá-lo de novo."):
            return
        self.casca.supervisor.tarefa(
            lambda: self._apagar(canal_id), self._apagou, rotulo="limpar")

    @staticmethod
    def _apagar(canal_id: str) -> dict:
        from espelho import baixar, config
        pasta = config.pasta_do_canal(canal_id)
        liberados = sum(baixar.apagar_midia(pasta, item.name)
                        for item in (pasta / "midia").iterdir()
                        if item.is_dir())
        return {"mb": liberados / 1e6}

    def _apagou(self, resultado) -> None:
        if isinstance(resultado, dict) and resultado.get("erro"):
            self.casca._registrar(f"[espelho] {resultado['erro']}", "erro")
            return
        self.casca._registrar(
            f"[espelho] {resultado['mb']:.0f} MB de vídeo apagados; "
            "o derivado ficou.")
        self.recarregar()

    def biblia(self) -> None:
        canal_id = self.selecionado()
        if canal_id is None:
            return
        provedor = self.combo_provedor.get()
        if provedor == "ambos":
            provedor = "chatgpt"
        self.cli(["biblia", canal_id, "--provedor", provedor],
                 "escrever a bíblia")

    def gerar_preset(self) -> None:
        canal_id = self.selecionado()
        if canal_id is None:
            return
        provedor = self.combo_provedor.get()
        if provedor == "ambos":
            provedor = "chatgpt"
        self.cli(["preset", canal_id, "--provedor", provedor], "gerar preset")

    def login(self) -> None:
        provedor = self.combo_provedor.get()
        if provedor == "ambos":
            provedor = "chatgpt"
        messagebox.showinfo(
            "Login no LLM",
            f"Vou abrir o {provedor} numa janela do Chrome.\n\nEntre na sua "
            "conta. O login fica salvo no perfil e vale para as Histórias "
            "também — é o mesmo registro de contas.")
        self.cli(["llm", "login", "--provedor", provedor],
                 f"login no {provedor}")

    def abrir_pasta(self) -> None:
        canal_id = self.selecionado()
        if canal_id is None:
            return
        pasta = MIMETIZAR / "outputs" / canal_id
        if not pasta.is_dir():
            messagebox.showinfo("Espelho", f"A pasta {pasta} não existe.")
            return
        os.startfile(str(pasta))                               # noqa: S606

    def abrir_biblia(self) -> None:
        canal_id = self.selecionado()
        if canal_id is None:
            return
        arquivo = MIMETIZAR / "outputs" / canal_id / "biblia.md"
        if not arquivo.is_file():
            messagebox.showinfo(
                "Espelho",
                "Este canal ainda não tem bíblia.\n\nO caminho é: baixar, "
                "medir, transcrever, analisar — e então escrever a bíblia.")
            return
        os.startfile(str(arquivo))                             # noqa: S606
