# -*- coding: utf-8 -*-
"""Pagina VIDEOS DE BUILD: gerar, re-renderizar, e os botoes de retencao.

O card de RETENCAO grava direto em `config/{editing,render,identity}.json`.
Preservar BOM e CRLF ao regravar nao e frescura: o arquivo e versionado, e
um diff inteiro por causa de fim de linha esconde a mudanca de verdade.
"""
from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from .. import estilo

RAIZ = Path(__file__).resolve().parents[2]
RANDOM_BUILDS = RAIZ / "random_builds"
PY = sys.executable

IMAGENS = [("Imagem", "*.png *.jpg *.jpeg *.webp"), ("Todos", "*.*")]

# As unicas vozes pt-BR do edge-tts. A lista e curta porque e o que existe.
VOZES = ("pt-BR-AntonioNeural", "pt-BR-FranciscaNeural",
         "pt-BR-ThalitaMultilingualNeural", "sapi (voz do Windows)")


class Pagina:
    chave = "videos"
    rotulo = "Vídeos de Build"
    icone = "🎬"

    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema
        self.escolhas: dict = {}

    # ------------------------------------------------------------ montar
    def construir(self, pai) -> None:
        self.o.titulo(pai, "Vídeos de Build — roletas e edição automática")

        colunas = tk.Frame(pai, bg=self.t.fundo)
        colunas.pack(fill="x", padx=estilo.ESPACO["secao"])
        self._card_gerar(colunas)
        self._card_rerender(colunas)
        self._card_identidade(pai)
        self._card_retencao(pai)
        self._galeria(pai)

    def _card_gerar(self, pai) -> None:
        card = self.o.cartao(pai, "Gerar novo vídeo — sai em 9:16 e 16:9")
        card.pack(side="left", fill="both", expand=True,
                  padx=(0, estilo.ESPACO["meio"]))
        linha = tk.Frame(card.corpo, bg=self.t.superficie)
        linha.pack(anchor="w")
        moldura, self.var_seed = self.o.campo(linha, "Seed:", 10)
        moldura.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        self.marcas = {}
        for chave, texto, ligado in (("preview", "Preview", False),
                                     ("inserir", "Inserir no banco", True),
                                     ("identidade", "Identidade", True),
                                     ("estreia", "Estreia", True)):
            caixa, variavel = self.o.marcador(linha, texto)
            variavel.set(ligado)
            caixa.pack(side="left", padx=(0, estilo.ESPACO["meio"]))
            self.marcas[chave] = variavel

        pedido = tk.Frame(card.corpo, bg=self.t.superficie)
        pedido.pack(anchor="w", pady=(estilo.ESPACO["normal"], 0))
        self.o.rotulo(pedido, "Pedido de comentário:", peso="bold",
                      bg=self.t.superficie).pack(
            side="left", padx=(0, estilo.ESPACO["meio"]))
        moldura, self.var_nome = self.o.campo(pedido, "Nome:", 14)
        moldura.pack(side="left", padx=(0, estilo.ESPACO["meio"]))
        moldura, self.var_autor = self.o.campo(pedido, "de:", 12)
        moldura.pack(side="left")

        linha = tk.Frame(card.corpo, bg=self.t.superficie)
        linha.pack(anchor="w", pady=(estilo.ESPACO["meio"], 0))
        self.var_print = tk.StringVar()
        self.o.botao(linha, "🖼  Print do comentário…", self.escolher_print).pack(
            side="left")
        self.lbl_print = self.o.legenda(linha, "nenhum print escolhido")
        self.lbl_print.configure(bg=self.t.superficie)
        self.lbl_print.pack(side="left", padx=estilo.ESPACO["meio"])
        self.o.botao(linha, "limpar", self.limpar_print, compacto=True).pack(
            side="left")

        linha = tk.Frame(card.corpo, bg=self.t.superficie)
        linha.pack(anchor="w", pady=(estilo.ESPACO["normal"], 0))
        self.o.botao(linha, "🎬  GERAR VÍDEO", self.gerar,
                     tipo="primario").pack(side="left")
        self.o.botao(linha, "Só dados", self.gerar_dados).pack(
            side="left", padx=estilo.ESPACO["meio"])
        moldura, self.var_lote = self.o.campo(linha, "Lote:", 6)
        self.var_lote.set("100")
        moldura.pack(side="left", padx=(estilo.ESPACO["normal"], 0))
        self.o.botao(linha, "Rodar lote", self.lote).pack(
            side="left", padx=estilo.ESPACO["meio"])

    def _card_rerender(self, pai) -> None:
        card = self.o.cartao(pai, "Re-renderizar — não rola nada de novo")
        card.pack(side="left", fill="both", expand=True)
        linha = tk.Frame(card.corpo, bg=self.t.superficie)
        linha.pack(anchor="w")
        self.combo_geracao = self.o.combo(linha, [], largura=20)
        self.combo_geracao.pack(side="left")
        caixa, self.var_preview2 = self.o.marcador(linha, "Preview")
        caixa.pack(side="left", padx=estilo.ESPACO["meio"])
        # Linha PROPRIA, e nao ao lado: lado a lado a linha passava da
        # largura do card e o `pack` recortava o botao sem avisar.
        linha = tk.Frame(card.corpo, bg=self.t.superficie)
        linha.pack(anchor="w", pady=(estilo.ESPACO["normal"], 0))
        self.o.botao(linha, "Re-renderizar", self.rerender).pack(side="left")
        self.o.botao(linha, "+ print do comentário",
                     self.rerender_com_print).pack(
            side="left", padx=estilo.ESPACO["meio"])

    def _card_identidade(self, pai) -> None:
        card = self.o.cartao(
            pai, "Identidade visual (PicassoIA + Digen) — 2 imagens e 1 vídeo")
        card.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=estilo.ESPACO["meio"])
        self.o.legenda(
            card.corpo,
            "A roleta só ENFILEIRA e termina na hora. O worker gera as imagens "
            "no PicassoIA, anexa as duas no Digen e refaz o vídeo com tudo "
            "dentro. Cada site tem seu login: faça uma vez em cada.").pack(
            anchor="w")
        linha = tk.Frame(card.corpo, bg=self.t.superficie)
        linha.pack(anchor="w", pady=(estilo.ESPACO["normal"], 0))
        for texto, provedor in (("🔑  Login no PicassoIA", "picasso"),
                                ("🔑  Login no Digen", "digen")):
            self.o.botao(linha, texto,
                         lambda p=provedor: self.rb(
                             ["main.py", "identity", "login", "--provedor", p],
                             f"login no {p}")).pack(
                side="left", padx=(0, estilo.ESPACO["meio"]))
        self.o.botao(linha, "⬇  Processar fila",
                     lambda: self.rb(["main.py", "identity", "worker"],
                                     "worker de identidade"),
                     tipo="primario").pack(side="left",
                                           padx=(estilo.ESPACO["normal"], 0))
        for texto, comando in (("Ver fila", ["identity", "queue"]),
                               ("🧪  Diagnóstico", ["identity", "doctor"]),
                               ("📊  Status", ["identity", "status"]),
                               ("🔎  Auditar origem", ["identity", "auditar"])):
            self.o.botao(linha, texto,
                         lambda c=comando, t=texto: self.rb(
                             ["main.py"] + c, t)).pack(
                side="left", padx=(estilo.ESPACO["meio"], 0))

    def _card_retencao(self, pai) -> None:
        card = self.o.cartao(pai, "Retenção — o que entra no vídeo")
        card.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=estilo.ESPACO["meio"])
        self.lbl_retencao = self.o.legenda(card.corpo, "lendo…")
        self.lbl_retencao.configure(bg=self.t.superficie, justify="left")
        self.lbl_retencao.pack(anchor="w")

        self.var_ret: dict = {}
        for grupo in (
                (("gancho_payoff", "Gancho com a imagem"),
                 ("gancho_ab", "Gancho B (A/B)"),
                 ("revelacao_cedo", "Personagem cedo"),
                 ("luta", "Luta no fim")),
                (("voz", "Voz narrada"), ("trilha", "Trilha sintetizada"),
                 ("ducking", "Abaixar música sob a fala"),
                 ("payoff_video", "Vídeo do payoff (Digen)"))):
            linha = tk.Frame(card.corpo, bg=self.t.superficie)
            linha.pack(anchor="w", pady=(estilo.ESPACO["meio"], 0))
            for chave, texto in grupo:
                caixa, variavel = self.o.marcador(linha, texto)
                caixa.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
                self.var_ret[chave] = variavel

        linha = tk.Frame(card.corpo, bg=self.t.superficie)
        linha.pack(anchor="w", pady=(estilo.ESPACO["normal"], 0))
        self.o.rotulo(linha, "Voz:", cor="texto_fraco",
                      bg=self.t.superficie).pack(
            side="left", padx=(0, estilo.ESPACO["meio"]))
        self.combo_voz = self.o.combo(linha, list(VOZES), VOZES[0], largura=32)
        self.combo_voz.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        self.o.botao(linha, "💾  Salvar ajustes", self.salvar_retencao,
                     tipo="primario").pack(side="left")
        self.o.botao(linha, "🎵  Gerar trilha",
                     lambda: self.rb(["main.py", "trilha"],
                                     "gerar trilha")).pack(
            side="left", padx=estilo.ESPACO["meio"])

    def _galeria(self, pai) -> None:
        topo = tk.Frame(pai, bg=self.t.fundo)
        topo.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=(estilo.ESPACO["normal"], estilo.ESPACO["meio"]))
        self.o.secao(topo, "Vídeos prontos").pack(side="left")
        self.o.legenda(topo, "duplo-clique assiste").pack(
            side="left", padx=estilo.ESPACO["meio"])
        for texto, acao in (("↻", self.recarregar),
                            ("📂  Pasta", lambda: self.assistir("pasta")),
                            ("▶  Normal", lambda: self.assistir("normal")),
                            ("▶  Celular", lambda: self.assistir("celular"))):
            self.o.botao(topo, texto, acao).pack(
                side="right", padx=(estilo.ESPACO["pouco"], 0))

        self.tabela = self.o.tabela(pai, [
            ("geracao", "GERAÇÃO", 160, "w"),
            ("nota", "NOTA FINAL", 200, "w"),
            ("duracao", "DURAÇÃO", 84, "center"),
            ("formatos", "FORMATOS PRONTOS", 180, "w"),
            ("retencao", "VOZ · LUTA · A/B", 140, "center"),
        ], altura=8, estica="nota")
        self.tabela.pack(fill="both", expand=True,
                         padx=estilo.ESPACO["secao"],
                         pady=(0, estilo.ESPACO["normal"]))
        self.tabela.bind("<Double-1>", lambda _e: self.assistir("celular"))

    # ------------------------------------------------------------ config
    @staticmethod
    def _ler_config(nome: str):
        """Devolve (dados, tinha_crlf). O BOM e tratado pelo utf-8-sig."""
        bruto = (RANDOM_BUILDS / "config" / nome).read_bytes()
        texto = bruto.decode("utf-8-sig")
        return json.loads(texto), ("\r\n" in texto)

    @staticmethod
    def _gravar_config(nome: str, dados: dict, crlf: bool) -> None:
        texto = json.dumps(dados, ensure_ascii=False, indent=4) + "\n"
        if crlf:
            texto = texto.replace("\n", "\r\n")
        (RANDOM_BUILDS / "config" / nome).write_bytes(texto.encode("utf-8"))

    def carregar_retencao(self) -> None:
        try:
            edicao, _ = self._ler_config("editing.json")
            render, _ = self._ler_config("render.json")
            identidade, _ = self._ler_config("identity.json")
        except (OSError, ValueError) as erro:
            self.lbl_retencao.configure(text=f"não li a config: {erro}",
                                        fg=self.t.erro)
            return
        gancho = edicao.get("gancho") or {}
        audio = render.get("audio") or {}
        voz = audio.get("voz") or {}
        for chave, valor in (
                ("gancho_payoff", gancho.get("payoff", True)),
                ("gancho_ab", gancho.get("ab", True)),
                ("revelacao_cedo", edicao.get("revelacao_cedo", True)),
                ("luta", (edicao.get("luta_no_build") or {}).get("ativa", True)),
                ("voz", voz.get("ativa", True)),
                ("trilha", audio.get("trilha_procedural", True)),
                ("ducking", audio.get("ducking", True)),
                ("payoff_video", identidade.get("payoff_video", True))):
            self.var_ret[chave].set(bool(valor))
        self.combo_voz.set("sapi (voz do Windows)" if voz.get("motor") == "sapi"
                           else (voz.get("voz") or VOZES[0]))

        musicas = [p.name for p in (RANDOM_BUILDS / "assets/music").glob("*")
                   if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".m4a")]
        cache = RANDOM_BUILDS / "outputs/_voz_cache"
        falas = len(list(cache.glob("*"))) if cache.is_dir() else 0
        self.lbl_retencao.configure(
            fg=self.t.texto_fraco,
            text=f"trilha: {', '.join(musicas) or 'nenhuma'}   ·   "
                 f"voz: {voz.get('motor', 'edge')} ({falas} fala(s) em cache)"
                 f"   ·   loudness alvo {audio.get('loudnorm', -14)} LUFS")

    def salvar_retencao(self) -> None:
        try:
            edicao, crlf_e = self._ler_config("editing.json")
            render, crlf_r = self._ler_config("render.json")
            identidade, crlf_i = self._ler_config("identity.json")
            edicao.setdefault("gancho", {})["payoff"] = \
                self.var_ret["gancho_payoff"].get()
            edicao["gancho"]["ab"] = self.var_ret["gancho_ab"].get()
            edicao["revelacao_cedo"] = self.var_ret["revelacao_cedo"].get()
            edicao.setdefault("luta_no_build", {})["ativa"] = \
                self.var_ret["luta"].get()
            audio = render.setdefault("audio", {})
            voz = audio.setdefault("voz", {})
            voz["ativa"] = self.var_ret["voz"].get()
            escolha = self.combo_voz.get()
            if escolha.startswith("sapi"):
                voz["motor"] = "sapi"
            else:
                voz["motor"], voz["voz"] = "edge", escolha
            audio["trilha_procedural"] = self.var_ret["trilha"].get()
            audio["ducking"] = self.var_ret["ducking"].get()
            identidade["payoff_video"] = self.var_ret["payoff_video"].get()
            self._gravar_config("editing.json", edicao, crlf_e)
            self._gravar_config("render.json", render, crlf_r)
            self._gravar_config("identity.json", identidade, crlf_i)
        except (OSError, ValueError) as erro:
            messagebox.showerror("Retenção", f"não consegui salvar: {erro}")
            return
        self.casca._registrar(
            "[retenção] ajustes salvos — valem a partir do próximo render; o "
            "worker de identidade precisa ser reiniciado para ver o payoff "
            "ligado/desligado.", "fim")
        self.carregar_retencao()

    # ------------------------------------------------------------ dados
    def ao_mostrar(self) -> None:
        self.carregar_retencao()
        self.recarregar()

    def recarregar(self) -> None:
        self.casca.supervisor.tarefa(self._ler, self._desenhar,
                                     rotulo="galeria")

    @staticmethod
    def _ler() -> list:
        from builds.pipeline import fluxo
        saida = []
        pasta = RANDOM_BUILDS / "outputs"
        for geracao in sorted(pasta.glob("generation_*"), reverse=True)[:40]:
            build = geracao / "build.json"
            nota = duracao = ""
            if build.is_file():
                try:
                    dados = json.loads(build.read_text(encoding="utf-8-sig"))
                    nota = str(dados.get("nota_final") or dados.get("tier") or "")
                except (OSError, ValueError):
                    pass
            formatos = [n.replace("final_", "").replace(".mp4", "")
                        for n in ("final_celular.mp4", "final_normal.mp4")
                        if (geracao / n).is_file()]
            retencao = fluxo.retencao_de(geracao) or {}
            if retencao.get("duracao"):
                duracao = f"{retencao['duracao']:.0f}s"
            marcas = " · ".join("✓" if retencao.get(c) else "·"
                                for c in ("voz", "luta", "gancho_b"))
            saida.append((geracao.name, nota, duracao,
                          ", ".join(formatos) or "—", marcas))
        return saida

    def _desenhar(self, linhas) -> None:
        if isinstance(linhas, dict):
            return
        self.tabela.delete(*self.tabela.get_children())
        for linha in linhas:
            self.tabela.insert("", "end", iid=linha[0], values=linha)
        self.combo_geracao.configure(values=[l[0] for l in linhas])
        if linhas and not self.combo_geracao.get():
            self.combo_geracao.set(linhas[0][0])

    # ------------------------------------------------------------ acoes
    def rb(self, argumentos: list, rotulo: str) -> None:
        self.casca.supervisor.rodar([PY, "-u", "-X", "utf8"] + argumentos,
                                    cwd=RANDOM_BUILDS, rotulo=rotulo,
                                    depois=self.recarregar)

    def _bandeiras(self) -> list:
        extras = []
        if self.var_seed.get().strip():
            extras += ["--seed", self.var_seed.get().strip()]
        if self.marcas["preview"].get():
            extras.append("--preview")
        if not self.marcas["inserir"].get():
            extras.append("--no-insert")
        if not self.marcas["identidade"].get():
            extras.append("--no-identity")
        if not self.marcas["estreia"].get():
            extras.append("--no-estreia")
        # Campo vazio NAO vira bandeira: `--nome-pedido ""` faria o pipeline
        # tratar como pedido recusado em vez de "nao houve pedido".
        for bandeira, variavel in (("--nome-pedido", self.var_nome),
                                   ("--autor-pedido", self.var_autor),
                                   ("--print-pedido", self.var_print)):
            if variavel.get().strip():
                extras += [bandeira, variavel.get().strip()]
        for chave, valor in (self.escolhas or {}).items():
            extras += (["--genero", valor] if chave == "genero"
                       else ["--fixar", f"{chave}={valor}"])
        return extras

    def gerar(self) -> None:
        self.rb(["main.py", "generate-video"] + self._bandeiras(),
                "gerar vídeo")

    def gerar_dados(self) -> None:
        extras = [a for a in self._bandeiras() if a != "--preview"]
        self.rb(["main.py", "generate-video", "--generation-only"] + extras,
                "gerar só os dados")

    def lote(self) -> None:
        self.rb(["main.py", "generate-video", "--generation-only", "--count",
                 self.var_lote.get().strip() or "100"], "lote de gerações")

    def rerender(self, print_novo: str = "") -> None:
        geracao = self.combo_geracao.get()
        if not geracao:
            messagebox.showinfo("Re-renderizar", "Escolha uma geração.")
            return
        extras = ["--preview"] if self.var_preview2.get() else []
        if print_novo:
            extras += ["--print-pedido", print_novo]
        self.rb(["main.py", "generate-video", "--rerender", geracao] + extras,
                f"re-renderizar {geracao}")

    def rerender_com_print(self) -> None:
        caminho = filedialog.askopenfilename(title="Print do comentário",
                                             filetypes=IMAGENS)
        if caminho:
            self.rerender(caminho)

    def escolher_print(self) -> None:
        caminho = filedialog.askopenfilename(title="Print do comentário",
                                             filetypes=IMAGENS)
        if caminho:
            self.var_print.set(caminho)
            self.lbl_print.configure(text=Path(caminho).name, fg=self.t.texto)

    def limpar_print(self) -> None:
        self.var_print.set("")
        self.lbl_print.configure(text="nenhum print escolhido",
                                 fg=self.t.texto_fraco)

    def assistir(self, qual: str) -> None:
        iid = self.o.selecionado(self.tabela, "Escolha uma geração na lista.")
        if iid is None:
            return
        pasta = RANDOM_BUILDS / "outputs" / iid
        if qual == "pasta":
            if pasta.is_dir():
                os.startfile(pasta)                          # noqa: S606
            return
        alvo = pasta / f"final_{qual}.mp4"
        if alvo.is_file():
            os.startfile(alvo)                               # noqa: S606
        else:
            self.casca._registrar(f"{iid}: não tem o formato {qual}.", "erro")


__all__ = ["Pagina"]
