"""PAINEL DE CONTROLE (interface grafica) - Neural Fights + Random Builds.

Janela unica com tudo: videos de build, biblioteca de reacoes, simulacao,
lives com chat do YouTube e database — botoes e formularios em vez de
comandos. Cada acao roda a CLI oficial da ferramenta em processo proprio;
a saida aparece ao vivo no console embutido.

Uso:  python painel_ui.py   (ou dois cliques em painel.bat)
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

RAIZ = Path(__file__).resolve().parent
RANDOM_BUILDS = RAIZ / "random_builds"
PY = sys.executable

sys.path.insert(0, str(RANDOM_BUILDS))
from src.assets import importer as reacoes_importer  # noqa: E402
from src.assets.catalog import CATEGORIES  # noqa: E402

# ------------------------------------------------------------------ tema
BG = "#14121f"
PANEL = "#1b1830"
CARD = "#232040"
CARD_HL = "#2b2750"
ACCENT = "#9b59ff"
ACCENT_DARK = "#7a3fe0"
ORANGE = "#ff8c42"
TEXT = "#f0edfa"
DIM = "#9a93b8"
OK = "#3ddc84"
RED = "#ff5c5c"

FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 15, "bold")
FONT_MONO = ("Consolas", 9)

RESUMO_BANCO = """
from neural_fights.data import database
armas, personagens = database.carregar_database()
print(f'{len(personagens)} personagens | {len(armas)} armas')
print()
print('Ultimos 5 personagens:')
for p in personagens[-5:]:
    print(f"  - {p['nome']} ({p['classe']}, forca {p['forca']}, arma: {p['nome_arma']})")
print()
print('Ultimas 5 armas:')
for a in armas[-5:]:
    print(f"  - {a['nome']} ({a['tipo']}/{a['estilo']}, {a['raridade']}, dano {a['dano']})")
caminhos = database.resolver_database_paths(para_escrita=False)
print()
print(f'Arquivos: {caminhos[0]}')
print(f'          {caminhos[1]}')
"""


class Painel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Painel de Controle - Neural Fights")
        self.geometry("1180x760")
        self.minsize(980, 640)
        self.configure(bg=BG)
        self._fila: queue.Queue = queue.Queue()
        self._processos: list[subprocess.Popen] = []

        self._estilo_ttk()
        self._montar_layout()
        self.after(100, self._drenar_fila)

    # ------------------------------------------------------------ estrutura
    def _estilo_ttk(self):
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.configure("TCombobox", fieldbackground=CARD_HL, background=CARD,
                         foreground=TEXT, arrowcolor=TEXT, bordercolor=CARD,
                         lightcolor=CARD, darkcolor=CARD)
        estilo.map("TCombobox", fieldbackground=[("readonly", CARD_HL)])
        estilo.configure("Treeview", background=CARD, fieldbackground=CARD,
                         foreground=TEXT, bordercolor=PANEL, rowheight=24,
                         font=FONT)
        estilo.configure("Treeview.Heading", background=PANEL, foreground=DIM,
                         font=FONT_B, relief="flat")
        estilo.map("Treeview", background=[("selected", ACCENT_DARK)])
        estilo.configure("Vertical.TScrollbar", background=PANEL,
                         troughcolor=BG, arrowcolor=DIM)
        estilo.configure("Horizontal.TProgressbar", background=ACCENT,
                         troughcolor=CARD_HL, bordercolor=CARD,
                         lightcolor=ACCENT, darkcolor=ACCENT)

    def _montar_layout(self):
        # barra lateral
        self.sidebar = tk.Frame(self, bg=PANEL, width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="NEURAL\nFIGHTS", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 17, "bold"), justify="left").pack(
            anchor="w", padx=18, pady=(20, 18))

        self.paginas: dict[str, tk.Frame] = {}
        self.botoes_menu: dict[str, tk.Button] = {}
        conteudo = tk.Frame(self, bg=BG)
        conteudo.pack(side="right", fill="both", expand=True)

        # console embutido (parte de baixo)
        console_frame = tk.Frame(conteudo, bg=PANEL)
        console_frame.pack(side="bottom", fill="x")
        barra = tk.Frame(console_frame, bg=PANEL)
        barra.pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(barra, text="CONSOLE", bg=PANEL, fg=DIM, font=FONT_B).pack(side="left")
        self.status = tk.Label(barra, text="pronto", bg=PANEL, fg=OK, font=FONT)
        self.status.pack(side="left", padx=14)
        self._botao(barra, "Limpar", self._limpar_console).pack(side="right", padx=4)
        self._botao(barra, "Parar processos", self._parar_processos,
                    cor=RED).pack(side="right", padx=4)
        # progresso global (render de video, lutas de torneio) — visivel de
        # qualquer pagina, alimentado pelas linhas [progresso] dos processos
        self.barra_video = ttk.Progressbar(barra, length=260, maximum=100)
        self.barra_video.pack(side="right", padx=12)
        self.label_progresso = tk.Label(barra, text="", bg=PANEL, fg=DIM, font=FONT)
        self.label_progresso.pack(side="right")
        self.console = tk.Text(console_frame, height=11, bg="#0e0c18", fg=TEXT,
                               insertbackground=TEXT, font=FONT_MONO, bd=0,
                               state="disabled", wrap="word")
        self.console.pack(fill="x", padx=10, pady=8)
        self.console.tag_configure("cmd", foreground=ACCENT)
        self.console.tag_configure("fim", foreground=OK)
        self.console.tag_configure("erro", foreground=RED)

        # area principal (paginas)
        self.area = tk.Frame(conteudo, bg=BG)
        self.area.pack(side="top", fill="both", expand=True)

        paginas = [
            ("videos", "🎬  Vídeos de Build", self._pagina_videos),
            ("reacoes", "😂  Reações", self._pagina_reacoes),
            ("torneio", "🏆  Torneio", self._pagina_torneio),
            ("simulacao", "⚔️  Simulação", self._pagina_simulacao),
            ("live", "🔴  Live / YouTube", self._pagina_live),
            ("database", "🗃️  Database", self._pagina_database),
            ("audio", "🔊  Áudio", self._pagina_audio),
        ]
        for chave, rotulo, construtor in paginas:
            frame = tk.Frame(self.area, bg=BG)
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            construtor(frame)
            self.paginas[chave] = frame
            botao = tk.Button(
                self.sidebar, text=rotulo, anchor="w", bd=0, font=FONT_B,
                bg=PANEL, fg=TEXT, activebackground=CARD_HL,
                activeforeground=TEXT, padx=18, pady=10, cursor="hand2",
                command=lambda c=chave: self._mostrar(c))
            botao.pack(fill="x")
            self.botoes_menu[chave] = botao

        tk.Label(self.sidebar, text="cada botao roda a CLI\noficial da ferramenta",
                 bg=PANEL, fg=DIM, font=("Segoe UI", 8), justify="left").pack(
            side="bottom", anchor="w", padx=18, pady=14)
        self._mostrar("videos")

    def _mostrar(self, chave: str):
        self.paginas[chave].tkraise()
        for nome, botao in self.botoes_menu.items():
            botao.configure(bg=CARD_HL if nome == chave else PANEL,
                            fg=ACCENT if nome == chave else TEXT)
        if chave == "videos":
            self._atualizar_geracoes()
        if chave == "reacoes":
            self._atualizar_reacoes()
        if chave == "audio":
            self._atualizar_audio()
        if chave == "torneio":
            self._atualizar_torneios()

    # -------------------------------------------------------------- widgets
    def _botao(self, pai, texto, comando, cor=None, grande=False):
        base = cor or CARD_HL
        botao = tk.Button(pai, text=texto, command=comando, bd=0,
                          bg=base, fg=TEXT, activebackground=ACCENT_DARK,
                          activeforeground=TEXT, cursor="hand2",
                          font=FONT_B if not grande else ("Segoe UI", 11, "bold"),
                          padx=14, pady=8 if grande else 5)
        if cor is None:
            botao.bind("<Enter>", lambda e: botao.configure(bg=ACCENT_DARK))
            botao.bind("<Leave>", lambda e: botao.configure(bg=base))
        return botao

    def _botao_primario(self, pai, texto, comando):
        botao = self._botao(pai, texto, comando, cor=ACCENT, grande=True)
        botao.bind("<Enter>", lambda e: botao.configure(bg=ACCENT_DARK))
        botao.bind("<Leave>", lambda e: botao.configure(bg=ACCENT))
        return botao

    def _card(self, pai, titulo_texto):
        card = tk.Frame(pai, bg=CARD, padx=16, pady=12)
        tk.Label(card, text=titulo_texto, bg=CARD, fg=ACCENT,
                 font=FONT_B).pack(anchor="w", pady=(0, 8))
        return card

    def _titulo(self, pai, texto):
        tk.Label(pai, text=texto, bg=BG, fg=TEXT, font=FONT_TITLE).pack(
            anchor="w", padx=20, pady=(16, 10))

    def _campo(self, pai, rotulo, largura=14):
        linha = tk.Frame(pai, bg=CARD)
        tk.Label(linha, text=rotulo, bg=CARD, fg=DIM, font=FONT).pack(side="left")
        var = tk.StringVar()
        tk.Entry(linha, textvariable=var, width=largura, bg=CARD_HL, fg=TEXT,
                 insertbackground=TEXT, bd=0, font=FONT).pack(side="left", padx=6, ipady=3)
        return linha, var

    def _check(self, pai, rotulo, ligado=False):
        var = tk.BooleanVar(value=ligado)
        caixa = tk.Checkbutton(pai, text=rotulo, variable=var, bg=CARD, fg=TEXT,
                               selectcolor=CARD_HL, activebackground=CARD,
                               activeforeground=TEXT, font=FONT)
        return caixa, var

    # -------------------------------------------------------- processos/log
    def _log(self, texto, tag=None):
        self.console.configure(state="normal")
        self.console.insert("end", texto + "\n", tag)
        self.console.see("end")
        self.console.configure(state="disabled")

    def _limpar_console(self):
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")

    def _rodar(self, args, cwd=RAIZ, rotulo=None):
        mostrado = rotulo or " ".join(str(a) for a in args)
        self._log(f">>> {mostrado}", "cmd")
        try:
            proc = subprocess.Popen(
                [str(a) for a in args], cwd=str(cwd),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as erro:
            self._log(f"erro ao iniciar: {erro}", "erro")
            return
        self._processos.append(proc)
        self._atualizar_status()
        threading.Thread(target=self._ler_processo,
                         args=(proc, mostrado), daemon=True).start()

    def _ler_processo(self, proc, rotulo):
        for linha in proc.stdout:
            self._fila.put(("linha", linha.rstrip()))
        codigo = proc.wait()
        self._fila.put(("fim", f"({rotulo}) terminou com codigo {codigo}", codigo))

    def _drenar_fila(self):
        try:
            while True:
                item = self._fila.get_nowait()
                if item[0] == "linha":
                    if item[1].startswith("[progresso] "):
                        self._progresso_video(item[1])
                        continue
                    self._log(item[1])
                else:
                    self._log(item[1], "fim" if item[2] == 0 else "erro")
                    self._processos = [p for p in self._processos
                                       if p.poll() is None]
                    self._atualizar_status()
                    self._atualizar_geracoes()
                    self._atualizar_torneios()
        except queue.Empty:
            pass
        self.after(120, self._drenar_fila)

    def _progresso_video(self, linha: str):
        """Interpreta '[progresso] celular 12/40' (render) ou
        '[progresso] lutas 3/7' (torneio)."""
        try:
            _, etapa, frac = linha.split()
            atual, total = (int(n) for n in frac.split("/"))
        except ValueError:
            return
        self.barra_video.configure(maximum=total, value=atual)
        if etapa == "lutas":
            texto = f"lutando: {atual}/{total}"
        else:
            texto = f"renderizando {etapa}: {atual}/{total}"
        if atual >= total:
            texto = f"{etapa} ✔"
        self.label_progresso.configure(text=texto,
                                       fg=OK if atual >= total else ORANGE)

    def _atualizar_status(self):
        ativos = len([p for p in self._processos if p.poll() is None])
        if ativos:
            self.status.configure(text=f"{ativos} processo(s) rodando", fg=ORANGE)
        else:
            self.status.configure(text="pronto", fg=OK)
            if hasattr(self, "barra_video"):
                self.barra_video.configure(value=0)
                self.label_progresso.configure(text="", fg=DIM)

    def _parar_processos(self):
        ativos = [p for p in self._processos if p.poll() is None]
        for proc in ativos:
            proc.kill()
        if ativos:
            self._log(f"{len(ativos)} processo(s) finalizado(s) a força.", "erro")

    # ------------------------------------------------------- pagina: videos
    def _pagina_videos(self, pai):
        self._titulo(pai, "Vídeos de Build (roletas + edição automática)")

        colunas = tk.Frame(pai, bg=BG)
        colunas.pack(fill="x", padx=20)

        gerar = self._card(colunas, "GERAR NOVO VÍDEO (sai em celular 9:16 + normal 16:9)")
        gerar.pack(side="left", fill="both", expand=True, padx=(0, 6))
        linha = tk.Frame(gerar, bg=CARD)
        linha.pack(anchor="w", pady=2)
        campo_seed, self.var_seed = self._campo(linha, "Seed:", 10)
        campo_seed.pack(side="left")
        caixa_preview, self.var_preview = self._check(linha, "Preview")
        caixa_preview.pack(side="left", padx=8)
        caixa_inserir, self.var_inserir = self._check(
            linha, "Inserir no banco", ligado=True)
        caixa_inserir.pack(side="left")
        caixa_ident, self.var_identidade = self._check(
            linha, "Identidade (Digen)", ligado=True)
        caixa_ident.pack(side="left", padx=8)
        linha2 = tk.Frame(gerar, bg=CARD)
        linha2.pack(anchor="w", pady=(8, 2))
        self._botao_primario(linha2, "🎬  GERAR VÍDEO",
                             self._gerar_video).pack(side="left")
        self._botao(linha2, "Só dados", self._gerar_dados).pack(side="left", padx=8)
        campo_count, self.var_count = self._campo(linha2, "Lote:", 6)
        campo_count.pack(side="left", padx=(12, 0))
        self.var_count.set("100")
        self._botao(linha2, "Rodar lote", self._rodar_lote).pack(side="left", padx=6)

        rerender = self._card(colunas, "RE-RENDERIZAR (não rola nada de novo)")
        rerender.pack(side="left", fill="both", expand=True, padx=(6, 0))
        linha = tk.Frame(rerender, bg=CARD)
        linha.pack(anchor="w")
        self.combo_geracao = ttk.Combobox(linha, width=20, state="readonly")
        self.combo_geracao.pack(side="left")
        caixa_prev2, self.var_preview2 = self._check(linha, "Preview")
        caixa_prev2.pack(side="left", padx=6)
        linha2 = tk.Frame(rerender, bg=CARD)
        linha2.pack(anchor="w", pady=(8, 2))
        self._botao(linha2, "Re-renderizar", self._rerender).pack(side="left")

        identidade = self._card(
            pai, "IDENTIDADE VISUAL (Digen) — clipe real do personagem no fim do video")
        identidade.pack(fill="x", padx=20, pady=(8, 0))
        tk.Label(identidade,
                 text="A roleta so ENFILEIRA o clipe e termina na hora. O worker "
                      "baixa depois e refaz o video com ele dentro.",
                 bg=CARD, fg=DIM, font=FONT, justify="left").pack(anchor="w")
        linha_ident = tk.Frame(identidade, bg=CARD)
        linha_ident.pack(anchor="w", pady=(8, 2))
        self._botao(linha_ident, "🔑  Login no Digen",
                    self._digen_login).pack(side="left")
        self._botao_primario(linha_ident, "⬇  Processar fila",
                             self._digen_worker).pack(side="left", padx=8)
        self._botao(linha_ident, "Ver fila", self._digen_fila).pack(side="left")
        self._botao(linha_ident, "🧪  Diagnostico",
                    self._digen_doctor).pack(side="left", padx=8)
        self._botao(linha_ident, "📊  Status",
                    self._digen_status).pack(side="left")
        caixa_watch, self.var_digen_watch = self._check(linha_ident, "Ficar em pe")
        caixa_watch.pack(side="left", padx=8)

        # galeria de videos prontos
        galeria_topo = tk.Frame(pai, bg=BG)
        galeria_topo.pack(fill="x", padx=20, pady=(10, 2))
        tk.Label(galeria_topo, text="VÍDEOS PRONTOS  (duplo-clique assiste)",
                 bg=BG, fg=ACCENT, font=FONT_B).pack(side="left")
        self._botao(galeria_topo, "▶ Celular",
                    lambda: self._assistir("celular")).pack(side="right", padx=3)
        self._botao(galeria_topo, "▶ Normal",
                    lambda: self._assistir("normal")).pack(side="right", padx=3)
        self._botao(galeria_topo, "📂 Pasta",
                    self._abrir_pasta_geracao).pack(side="right", padx=3)
        self._botao(galeria_topo, "🔄", self._atualizar_geracoes).pack(side="right", padx=3)

        corpo = tk.Frame(pai, bg=BG)
        corpo.pack(fill="both", expand=True, padx=20, pady=(2, 10))
        cols = ("geracao", "nota", "duracao", "formatos")
        self.tabela_videos = ttk.Treeview(corpo, columns=cols, show="headings",
                                          selectmode="browse")
        for coluna, texto, largura in (("geracao", "Geração", 170),
                                       ("nota", "Nota final", 210),
                                       ("duracao", "Duração", 90),
                                       ("formatos", "Formatos prontos", 200)):
            self.tabela_videos.heading(coluna, text=texto)
            self.tabela_videos.column(coluna, width=largura, anchor="w")
        self.tabela_videos.pack(side="left", fill="both", expand=True)
        rolagem = ttk.Scrollbar(corpo, orient="vertical",
                                command=self.tabela_videos.yview)
        rolagem.pack(side="left", fill="y")
        self.tabela_videos.configure(yscrollcommand=rolagem.set)
        self.tabela_videos.bind("<Double-1>", lambda e: self._assistir("celular"))

    def _flags_video(self):
        extras = []
        if self.var_seed.get().strip():
            extras += ["--seed", self.var_seed.get().strip()]
        if self.var_preview.get():
            extras.append("--preview")
        if not self.var_inserir.get():
            extras.append("--no-insert")
        if not self.var_identidade.get():
            extras.append("--no-identity")
        return extras

    def _gerar_video(self):
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "generate-video"]
                    + self._flags_video(), RANDOM_BUILDS)

    def _gerar_dados(self):
        extras = [a for a in self._flags_video() if a != "--preview"]
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "generate-video",
                     "--generation-only"] + extras, RANDOM_BUILDS)

    def _rodar_lote(self):
        quantidade = self.var_count.get().strip() or "100"
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "generate-video",
                     "--generation-only", "--count", quantidade], RANDOM_BUILDS)

    def _atualizar_geracoes(self):
        if not hasattr(self, "combo_geracao"):
            return
        saidas = sorted(p.name for p in (RANDOM_BUILDS / "outputs").glob("generation_*"))
        self.combo_geracao["values"] = saidas
        if saidas and not self.combo_geracao.get():
            self.combo_geracao.set(saidas[-1])
        self._atualizar_galeria(saidas)

    def _atualizar_galeria(self, saidas=None):
        if not hasattr(self, "tabela_videos"):
            return
        import json
        if saidas is None:
            saidas = sorted(p.name for p in (RANDOM_BUILDS / "outputs").glob("generation_*"))
        selecionado = self.tabela_videos.selection()
        self.tabela_videos.delete(*self.tabela_videos.get_children())
        for nome in reversed(saidas):  # mais recente primeiro
            pasta = RANDOM_BUILDS / "outputs" / nome
            nota = "?"
            try:
                build = json.loads((pasta / "build.json").read_text(encoding="utf-8"))
                nota = f"{build['final_score']} - {build['verdict_label']}"
            except (OSError, ValueError, KeyError):
                pass
            duracao = ""
            try:
                plan = json.loads((pasta / "edit_plan.json").read_text(encoding="utf-8"))
                duracao = f"{round(plan['total_duration'])}s"
            except (OSError, ValueError, KeyError):
                pass
            formatos = []
            if (pasta / "final_celular.mp4").exists():
                formatos.append("celular")
            if (pasta / "final_normal.mp4").exists():
                formatos.append("normal")
            self.tabela_videos.insert(
                "", "end", iid=nome,
                values=(nome, nota, duracao,
                        " + ".join(formatos) if formatos else "(sem video)"))
        if selecionado and self.tabela_videos.exists(selecionado[0]):
            self.tabela_videos.selection_set(selecionado)

    def _geracao_selecionada(self) -> Path | None:
        selecionado = self.tabela_videos.selection()
        if not selecionado:
            messagebox.showwarning("Vídeos", "Selecione uma geração na lista.")
            return None
        return RANDOM_BUILDS / "outputs" / selecionado[0]

    def _assistir(self, profile: str):
        pasta = self._geracao_selecionada()
        if pasta is None:
            return
        video = pasta / f"final_{profile}.mp4"
        if not video.exists():
            outro = "normal" if profile == "celular" else "celular"
            alternativa = pasta / f"final_{outro}.mp4"
            if alternativa.exists():
                video = alternativa
            else:
                messagebox.showwarning("Assistir",
                                       f"{pasta.name} ainda não tem vídeo renderizado.")
                return
        os.startfile(video)

    def _abrir_pasta_geracao(self):
        pasta = self._geracao_selecionada()
        if pasta is not None:
            os.startfile(pasta)

    def _rerender(self):
        escolha = self.combo_geracao.get()
        if not escolha:
            messagebox.showwarning("Re-render", "Nenhuma geração selecionada.")
            return
        extras = ["--preview"] if self.var_preview2.get() else []
        # --refazer-edicao: remonta a timeline, e so assim que um clipe de
        # identidade que chegou depois entra no video.
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "generate-video",
                     "--rerender", escolha, "--refazer-edicao"] + extras,
                    RANDOM_BUILDS)

    # -------------------------------------------------- identidade (Digen)
    def _digen_login(self):
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "identity", "login"],
                    RANDOM_BUILDS, rotulo="digen login")

    def _digen_worker(self):
        extras = ["--watch"] if self.var_digen_watch.get() else []
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "identity", "worker"] + extras,
                    RANDOM_BUILDS, rotulo="digen worker")

    def _digen_fila(self):
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "identity", "queue"],
                    RANDOM_BUILDS, rotulo="digen fila")

    def _digen_doctor(self):
        # --online abre o Chrome: e o unico jeito de saber se um deploy do
        # Digen quebrou algum seletor antes de a fila travar.
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "identity", "doctor",
                     "--online"], RANDOM_BUILDS, rotulo="digen diagnostico")

    def _digen_status(self):
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "identity", "status"],
                    RANDOM_BUILDS, rotulo="digen status")

    # ------------------------------------------------------ pagina: reacoes
    def _pagina_reacoes(self, pai):
        self._titulo(pai, "Biblioteca de vídeos de reação")

        topo = tk.Frame(pai, bg=BG)
        topo.pack(fill="x", padx=20)
        tk.Label(topo, text="Categoria para importar:", bg=BG, fg=DIM,
                 font=FONT).pack(side="left")
        self.combo_categoria = ttk.Combobox(topo, values=CATEGORIES, width=12,
                                            state="readonly")
        self.combo_categoria.set("insane")
        self.combo_categoria.pack(side="left", padx=6)
        caixa_mover, self.var_mover = self._check(topo, "mover em vez de copiar")
        caixa_mover.configure(bg=BG, activebackground=BG)
        caixa_mover.pack(side="left", padx=8)
        self._botao_primario(topo, "＋ Importar vídeos…",
                             self._importar_arquivos).pack(side="left", padx=8)
        self._botao(topo, "＋ Importar pasta inteira…",
                    self._importar_pasta).pack(side="left")

        corpo = tk.Frame(pai, bg=BG)
        corpo.pack(fill="both", expand=True, padx=20, pady=10)
        colunas = ("id", "categoria", "duracao", "origem")
        self.tabela = ttk.Treeview(corpo, columns=colunas, show="headings",
                                   selectmode="extended", height=10)
        for coluna, texto, largura in (("id", "ID", 70), ("categoria", "Categoria", 110),
                                       ("duracao", "Duração", 90), ("origem", "Arquivo original", 420)):
            self.tabela.heading(coluna, text=texto)
            self.tabela.column(coluna, width=largura, anchor="w")
        self.tabela.pack(side="left", fill="both", expand=True)
        rolagem = ttk.Scrollbar(corpo, orient="vertical", command=self.tabela.yview)
        rolagem.pack(side="left", fill="y")
        self.tabela.configure(yscrollcommand=rolagem.set)

        rodape = tk.Frame(pai, bg=BG)
        rodape.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(rodape, text="Selecionados:", bg=BG, fg=DIM, font=FONT).pack(side="left")
        self.combo_recat = ttk.Combobox(rodape, values=CATEGORIES, width=12,
                                        state="readonly")
        self.combo_recat.set("good")
        self.combo_recat.pack(side="left", padx=6)
        self._botao(rodape, "Recategorizar", self._recategorizar).pack(side="left", padx=4)
        self._botao(rodape, "Remover", self._remover_reacoes, cor=RED).pack(side="left", padx=4)
        self._botao(rodape, "🔄 Atualizar lista", self._atualizar_reacoes).pack(side="right")

    def _atualizar_reacoes(self):
        if not hasattr(self, "tabela"):
            return
        self.tabela.delete(*self.tabela.get_children())
        for entrada in reacoes_importer.list_reactions(RANDOM_BUILDS / "assets"):
            duracao = f"{entrada['duration']}s" if entrada.get("duration") else "?"
            self.tabela.insert("", "end", iid=entrada["id"],
                               values=(entrada["id"], entrada["category"],
                                       duracao, entrada.get("source", "")))

    def _importar_em_thread(self, alvo):
        def tarefa():
            try:
                importados = reacoes_importer.import_reactions(
                    alvo, self.combo_categoria.get(),
                    RANDOM_BUILDS / "assets", move=self.var_mover.get())
                for entrada in importados:
                    self._fila.put(("linha",
                                    f"[import] ID {entrada['id']} <- {entrada['source']} "
                                    f"({entrada['category']}, {entrada['duration']}s)"))
                self._fila.put(("fim", f"{len(importados)} vídeo(s) importado(s)", 0))
            except (OSError, ValueError, FileNotFoundError) as erro:
                self._fila.put(("fim", f"importação falhou: {erro}", 1))
            self.after(200, self._atualizar_reacoes)
        threading.Thread(target=tarefa, daemon=True).start()

    def _importar_arquivos(self):
        arquivos = filedialog.askopenfilenames(
            title="Escolha os vídeos de reação",
            filetypes=[("Vídeos", "*.mp4 *.mov *.webm *.mkv *.gif"), ("Todos", "*.*")])
        for arquivo in arquivos:
            self._importar_em_thread(Path(arquivo))

    def _importar_pasta(self):
        pasta = filedialog.askdirectory(title="Escolha a pasta com os vídeos")
        if pasta:
            self._importar_em_thread(Path(pasta))

    def _recategorizar(self):
        selecionados = self.tabela.selection()
        if not selecionados:
            messagebox.showwarning("Recategorizar", "Selecione ao menos um vídeo na lista.")
            return
        for asset_id in selecionados:
            reacoes_importer.recategorize_reaction(
                asset_id, self.combo_recat.get(), RANDOM_BUILDS / "assets")
        self._log(f"{len(selecionados)} vídeo(s) recategorizado(s) "
                  f"para '{self.combo_recat.get()}'.", "fim")
        self._atualizar_reacoes()

    def _remover_reacoes(self):
        selecionados = self.tabela.selection()
        if not selecionados:
            messagebox.showwarning("Remover", "Selecione ao menos um vídeo na lista.")
            return
        if not messagebox.askyesno("Remover",
                                   f"Remover {len(selecionados)} vídeo(s) da biblioteca?\n"
                                   "O arquivo também será apagado."):
            return
        for asset_id in selecionados:
            reacoes_importer.remove_reaction(asset_id, RANDOM_BUILDS / "assets")
        self._log(f"{len(selecionados)} vídeo(s) removido(s).", "fim")
        self._atualizar_reacoes()

    # ------------------------------------------------------ pagina: torneio
    def _pagina_torneio(self, pai):
        self._titulo(pai, "Torneio (mata-mata dos personagens → vídeo)")

        card = self._card(pai, "NOVO TORNEIO  —  lutas reais no motor do jogo, "
                               "vídeo nos 2 formatos")
        card.pack(fill="x", padx=20, pady=6)
        linha = tk.Frame(card, bg=CARD)
        linha.pack(anchor="w", pady=2)
        tk.Label(linha, text="Quem luta:", bg=CARD, fg=DIM, font=FONT).pack(side="left")
        self.combo_fonte = ttk.Combobox(
            linha, width=9, state="readonly",
            values=["misto", "gerados", "banco"])
        self.combo_fonte.set("misto")
        self.combo_fonte.pack(side="left", padx=6)
        tk.Label(linha, text="Participantes:", bg=CARD, fg=DIM,
                 font=FONT).pack(side="left", padx=(10, 0))
        self.combo_participantes = ttk.Combobox(
            linha, width=5, state="readonly", values=["4", "8", "16", "32"])
        self.combo_participantes.set("8")
        self.combo_participantes.pack(side="left", padx=6)
        campo_seed, self.var_seed_torneio = self._campo(linha, "Seed:", 10)
        campo_seed.pack(side="left", padx=(10, 0))
        caixa_prev, self.var_preview_torneio = self._check(linha, "Preview")
        caixa_prev.pack(side="left", padx=8)

        linha2 = tk.Frame(card, bg=CARD)
        linha2.pack(anchor="w", pady=(8, 2))
        self._botao_primario(linha2, "🏆  RODAR TORNEIO",
                             self._rodar_torneio).pack(side="left")
        self._botao(linha2, "Só as lutas (sem vídeo)",
                    lambda: self._rodar_torneio(so_dados=True)).pack(side="left", padx=8)
        tk.Label(linha2,
                 text="as lutas são gravadas de verdade e entram no vídeo",
                 bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack(side="left", padx=12)

        topo = tk.Frame(pai, bg=BG)
        topo.pack(fill="x", padx=20, pady=(10, 2))
        tk.Label(topo, text="TORNEIOS  (duplo-clique assiste)", bg=BG, fg=ACCENT,
                 font=FONT_B).pack(side="left")
        self._botao(topo, "▶ Celular",
                    lambda: self._assistir_torneio("celular")).pack(side="right", padx=3)
        self._botao(topo, "▶ Normal",
                    lambda: self._assistir_torneio("normal")).pack(side="right", padx=3)
        self._botao(topo, "📂 Pasta",
                    self._abrir_pasta_torneio).pack(side="right", padx=3)
        self._botao(topo, "♻ Re-renderizar",
                    self._rerender_torneio).pack(side="right", padx=3)
        self._botao(topo, "🔄", self._atualizar_torneios).pack(side="right", padx=3)

        corpo = tk.Frame(pai, bg=BG)
        corpo.pack(fill="both", expand=True, padx=20, pady=(2, 10))
        cols = ("torneio", "campeao", "lutas", "destaque", "formatos")
        self.tabela_torneios = ttk.Treeview(corpo, columns=cols, show="headings",
                                            selectmode="browse")
        for coluna, texto, largura in (("torneio", "Torneio", 140),
                                       ("campeao", "Campeão", 190),
                                       ("lutas", "Lutas", 60),
                                       ("destaque", "Destaques", 220),
                                       ("formatos", "Vídeos", 130)):
            self.tabela_torneios.heading(coluna, text=texto)
            self.tabela_torneios.column(coluna, width=largura, anchor="w")
        self.tabela_torneios.pack(side="left", fill="both", expand=True)
        rolagem = ttk.Scrollbar(corpo, orient="vertical",
                                command=self.tabela_torneios.yview)
        rolagem.pack(side="left", fill="y")
        self.tabela_torneios.configure(yscrollcommand=rolagem.set)
        self.tabela_torneios.bind("<Double-1>",
                                  lambda e: self._assistir_torneio("celular"))

    def _rodar_torneio(self, so_dados: bool = False):
        args = [PY, "-u", "-X", "utf8", "main.py", "tournament",
                "--fonte", self.combo_fonte.get(),
                "--participantes", self.combo_participantes.get()]
        if self.var_seed_torneio.get().strip():
            args += ["--seed", self.var_seed_torneio.get().strip()]
        if so_dados:
            args.append("--generation-only")
        elif self.var_preview_torneio.get():
            args.append("--preview")
        self._rodar(args, RANDOM_BUILDS)

    def _rerender_torneio(self):
        pasta = self._torneio_selecionado()
        if pasta is None:
            return
        refazer = messagebox.askyesno(
            "Re-renderizar",
            "Remontar também a edição (legendas e reações novas)?\n\n"
            "As lutas gravadas são reaproveitadas nos dois casos — elas são a "
            "parte cara.")
        args = [PY, "-u", "-X", "utf8", "main.py", "tournament",
                "--rerender", pasta.name]
        if refazer:
            args.append("--refazer-edicao")
        if self.var_preview_torneio.get():
            args.append("--preview")
        self._rodar(args, RANDOM_BUILDS)

    def _atualizar_torneios(self):
        if not hasattr(self, "tabela_torneios"):
            return
        import json
        self.tabela_torneios.delete(*self.tabela_torneios.get_children())
        pastas = sorted((RANDOM_BUILDS / "outputs").glob("tournament_*"))
        for pasta in reversed(pastas):
            campeao, lutas, destaque = "?", "", ""
            try:
                dados = json.loads((pasta / "tournament.json").read_text(encoding="utf-8"))
                campeao = str(dados.get("campeao", "?"))
                if dados.get("campeao_gerado"):
                    campeao += "  ⭐"
                stats = dados.get("estatisticas", {})
                lutas = str(stats.get("total_lutas", ""))
                partes = []
                if stats.get("zebras"):
                    partes.append(f"{stats['zebras']} zebra(s)")
                melhor = stats.get("melhor_luta", {})
                if melhor.get("marcas"):
                    partes.append(", ".join(melhor["marcas"][:2]))
                gravadas = len(list((pasta / "gameplay").glob("luta_*_celular.mp4")))
                if gravadas:
                    partes.insert(0, f"🎥 {gravadas} luta(s)")
                destaque = " • ".join(partes)
            except (OSError, ValueError, KeyError):
                pass
            formatos = [nome for nome, arquivo in
                        (("celular", "final_celular.mp4"), ("normal", "final_normal.mp4"))
                        if (pasta / arquivo).exists()]
            self.tabela_torneios.insert(
                "", "end", iid=pasta.name,
                values=(pasta.name, campeao, lutas, destaque,
                        " + ".join(formatos) if formatos else "(sem video)"))

    def _torneio_selecionado(self) -> Path | None:
        selecionado = self.tabela_torneios.selection()
        if not selecionado:
            messagebox.showwarning("Torneio", "Selecione um torneio na lista.")
            return None
        return RANDOM_BUILDS / "outputs" / selecionado[0]

    def _assistir_torneio(self, profile: str):
        pasta = self._torneio_selecionado()
        if pasta is None:
            return
        video = pasta / f"final_{profile}.mp4"
        if not video.exists():
            outro = "normal" if profile == "celular" else "celular"
            alternativa = pasta / f"final_{outro}.mp4"
            if not alternativa.exists():
                messagebox.showwarning("Assistir",
                                       f"{pasta.name} ainda não tem vídeo renderizado.")
                return
            video = alternativa
        os.startfile(video)

    def _abrir_pasta_torneio(self):
        pasta = self._torneio_selecionado()
        if pasta is not None:
            os.startfile(pasta)

    # ---------------------------------------------------- pagina: simulacao
    def _pagina_simulacao(self, pai):
        self._titulo(pai, "Simulação")

        janelas = self._card(pai, "ABRIR (cada um em janela própria do jogo)")
        janelas.pack(fill="x", padx=20, pady=6)
        linha = tk.Frame(janelas, bg=CARD)
        linha.pack(anchor="w")
        for texto, args in (
                ("🕹️ Launcher (UI)", ["-m", "neural_fights.cli.main"]),
                ("🤖 IA vs IA", ["-m", "neural_fights.cli.main", "--sim"]),
                ("🎮 Teste manual", ["-m", "neural_fights.cli.main", "--test"]),
                ("🏆 Torneio", ["-m", "neural_fights.cli.tournament"]),
                ("🐞 Debug arena", ["debug_simulation.py"])):
            self._botao(linha, texto,
                        lambda a=args: self._rodar([PY] + a)).pack(side="left", padx=4)

        headless = self._card(pai, "SIMULAÇÃO HEADLESS (sem janela, relatório no console)")
        headless.pack(fill="x", padx=20, pady=6)
        linha = tk.Frame(headless, bg=CARD)
        linha.pack(anchor="w")
        tk.Label(linha, text="Modo:", bg=CARD, fg=DIM, font=FONT).pack(side="left")
        self.combo_headless = ttk.Combobox(linha, values=["rapido", "stress", "all"],
                                           width=8, state="readonly")
        self.combo_headless.set("rapido")
        self.combo_headless.pack(side="left", padx=6)
        campo_seed, self.var_seed_headless = self._campo(linha, "Seed:", 10)
        campo_seed.pack(side="left", padx=6)
        campo_p1, self.var_p1 = self._campo(linha, "P1:", 16)
        campo_p1.pack(side="left", padx=6)
        campo_p2, self.var_p2 = self._campo(linha, "P2:", 16)
        campo_p2.pack(side="left", padx=6)
        self._botao_primario(headless, "▶ Rodar headless",
                             self._rodar_headless).pack(anchor="w", pady=(8, 0))

    def _rodar_headless(self):
        extras = ["--mode", self.combo_headless.get()]
        if self.var_seed_headless.get().strip():
            extras += ["--seed", self.var_seed_headless.get().strip()]
        if self.var_p1.get().strip():
            extras += ["--p1", self.var_p1.get().strip()]
        if self.var_p2.get().strip():
            extras += ["--p2", self.var_p2.get().strip()]
        self._rodar([PY, "-m", "neural_fights.cli.headless"] + extras)

    # --------------------------------------------------------- pagina: live
    def _pagina_live(self, pai):
        self._titulo(pai, "Live / YouTube")

        show = self._card(pai, "INICIAR LIVE")
        show.pack(fill="x", padx=20, pady=6)
        linha = tk.Frame(show, bg=CARD)
        linha.pack(anchor="w")
        campo_video, self.var_video_id = self._campo(
            linha, "ID do vídeo (vazio = consultar a conta):", 20)
        campo_video.pack(side="left")
        caixa_portrait, self.var_portrait = self._check(linha, "vertical (9:16)")
        caixa_portrait.pack(side="left", padx=10)
        caixa_gravar, self.var_gravar = self._check(linha, "gravar eventos (.jsonl)")
        caixa_gravar.pack(side="left")
        linha2 = tk.Frame(show, bg=CARD)
        linha2.pack(anchor="w", pady=(8, 0))
        self._botao_primario(linha2, "🔴  LIVE COM CHAT DO YOUTUBE",
                             self._live_chat).pack(side="left")
        self._botao(linha2, "▶ Só o show (sem chat)",
                    self._live_show).pack(side="left", padx=10)

        replay = self._card(pai, "REPLAY DE EVENTOS GRAVADOS")
        replay.pack(fill="x", padx=20, pady=6)
        linha = tk.Frame(replay, bg=CARD)
        linha.pack(anchor="w")
        self.var_replay = tk.StringVar()
        tk.Entry(linha, textvariable=self.var_replay, width=48, bg=CARD_HL,
                 fg=TEXT, insertbackground=TEXT, bd=0, font=FONT).pack(
            side="left", ipady=3)
        self._botao(linha, "Escolher .jsonl…", self._escolher_replay).pack(side="left", padx=6)
        caixa_loop, self.var_loop = self._check(linha, "loop")
        caixa_loop.pack(side="left", padx=4)
        self._botao(linha, "▶ Replay", self._live_replay).pack(side="left", padx=6)

        oauth = self._card(pai, "CREDENCIAIS DO YOUTUBE (uma vez só; do Google Cloud Console)")
        oauth.pack(fill="x", padx=20, pady=6)
        linha = tk.Frame(oauth, bg=CARD)
        linha.pack(anchor="w")
        campo_ci, self.var_client_id = self._campo(linha, "client-id:", 28)
        campo_ci.pack(side="left")
        campo_cs, self.var_client_secret = self._campo(linha, "client-secret:", 22)
        campo_cs.pack(side="left", padx=8)
        self._botao(linha, "Configurar OAuth", self._oauth).pack(side="left", padx=6)

    def _extras_live(self):
        extras = []
        if self.var_portrait.get():
            extras.append("--portrait")
        return extras

    def _live_show(self):
        self._rodar([PY, "-m", "neural_fights.cli.live", "--source", "nenhuma"]
                    + self._extras_live())

    def _live_chat(self):
        extras = ["--source", "youtube"] + self._extras_live()
        if self.var_video_id.get().strip():
            extras += ["--video-id", self.var_video_id.get().strip()]
        if self.var_gravar.get():
            extras += ["--gravar-eventos", "live_eventos.jsonl"]
        self._rodar([PY, "-m", "neural_fights.cli.live"] + extras)

    def _escolher_replay(self):
        arquivo = filedialog.askopenfilename(
            title="Arquivo de eventos", filetypes=[("JSON Lines", "*.jsonl"), ("Todos", "*.*")])
        if arquivo:
            self.var_replay.set(arquivo)

    def _live_replay(self):
        if not self.var_replay.get().strip():
            messagebox.showwarning("Replay", "Escolha o arquivo .jsonl primeiro.")
            return
        extras = ["--source", "replay", "--events", self.var_replay.get().strip()]
        if self.var_loop.get():
            extras.append("--loop-events")
        self._rodar([PY, "-m", "neural_fights.cli.live"] + extras)

    def _oauth(self):
        client_id = self.var_client_id.get().strip()
        client_secret = self.var_client_secret.get().strip()
        if not client_id or not client_secret:
            messagebox.showwarning("OAuth", "Preencha client-id e client-secret.")
            return
        self._rodar([PY, "-m", "neural_fights.tools.youtube_oauth",
                     "--client-id", client_id, "--client-secret", client_secret],
                    rotulo="youtube_oauth (credenciais ocultas)")

    # ----------------------------------------------------- pagina: database
    def _pagina_database(self, pai):
        self._titulo(pai, "Database do Neural Fights")

        ver = self._card(pai, "CONSULTAR")
        ver.pack(fill="x", padx=20, pady=6)
        linha = tk.Frame(ver, bg=CARD)
        linha.pack(anchor="w")
        self._botao_primario(linha, "📋 Ver banco atual",
                             lambda: self._rodar(
                                 [PY, "-u", "-X", "utf8", "-c", RESUMO_BANCO],
                                 rotulo="resumo do banco")).pack(side="left")
        self._botao(linha, "🗡️ Análise das armas",
                    lambda: self._rodar([PY, "-m", "neural_fights.tools.analise_armas"])
                    ).pack(side="left", padx=8)
        self._botao(linha, "🥊 Qualidade de luta",
                    lambda: self._rodar([PY, "-m", "neural_fights.tools.qualidade_luta"])
                    ).pack(side="left")

        roster = self._card(pai, "ROSTER")
        roster.pack(fill="x", padx=20, pady=6)
        linha = tk.Frame(roster, bg=CARD)
        linha.pack(anchor="w")
        tk.Label(linha, text="Modo:", bg=CARD, fg=DIM, font=FONT).pack(side="left")
        self.combo_roster = ttk.Combobox(linha, values=["completo", "64", "16"],
                                         width=10, state="readonly")
        self.combo_roster.set("64")
        self.combo_roster.pack(side="left", padx=6)
        campo_seed, self.var_seed_roster = self._campo(linha, "Seed:", 10)
        campo_seed.pack(side="left", padx=6)
        self._botao(linha, "Gerar roster", self._gerar_roster).pack(side="left", padx=8)

        perigo = tk.Frame(pai, bg="#3a1d24", padx=16, pady=12)
        perigo.pack(fill="x", padx=20, pady=6)
        tk.Label(perigo, text="ZONA DE PERIGO", bg="#3a1d24", fg=RED,
                 font=FONT_B).pack(anchor="w")
        tk.Label(perigo,
                 text="Regenerar apaga o banco atual — personagens criados pelos vídeos de build serão perdidos.",
                 bg="#3a1d24", fg=DIM, font=FONT).pack(anchor="w", pady=(2, 8))
        self._botao(perigo, "⚠ REGENERAR DATABASE INTEIRA",
                    self._regenerar_db, cor=RED).pack(anchor="w")

    def _gerar_roster(self):
        extras = ["--modo", self.combo_roster.get()]
        if self.var_seed_roster.get().strip():
            extras += ["--seed", self.var_seed_roster.get().strip()]
        self._rodar([PY, "-m", "neural_fights.cli.roster"] + extras)

    def _regenerar_db(self):
        if not messagebox.askyesno("Regenerar database",
                                   "Isso APAGA o banco atual e gera um novo do zero.\n"
                                   "Personagens inseridos pelos vídeos serão perdidos.\n\nContinuar?"):
            return
        if not messagebox.askyesno("Regenerar database", "Certeza MESMO? Não tem volta."):
            return
        self._rodar([PY, "-m", "neural_fights.tools.gerador_database"])


    # ------------------------------------------------------- pagina: audio
    def _pagina_audio(self, pai):
        self._titulo(pai, "Sons do jogo (46 eventos de combate/UI)")

        topo = tk.Frame(pai, bg=BG)
        topo.pack(fill="x", padx=20)
        self._botao_primario(topo, "📁 Importar pasta de áudios…",
                             self._audio_importar).pack(side="left")
        tk.Label(topo, text="(arquivos nomeados pelo evento: slash_light.mp3, ko_impact.wav...)",
                 bg=BG, fg=DIM, font=("Segoe UI", 9)).pack(side="left", padx=8)
        self._botao(topo, "📋 Copiar lista de eventos",
                    self._audio_copiar_eventos).pack(side="right")

        corpo = tk.Frame(pai, bg=BG)
        corpo.pack(fill="both", expand=True, padx=20, pady=8)
        colunas = ("evento", "arquivo", "origem")
        self.tabela_audio = ttk.Treeview(corpo, columns=colunas, show="headings",
                                         selectmode="browse", height=9)
        for coluna, texto, largura in (("evento", "Evento", 200),
                                       ("arquivo", "Arquivo configurado", 260),
                                       ("origem", "Tocando de", 280)):
            self.tabela_audio.heading(coluna, text=texto)
            self.tabela_audio.column(coluna, width=largura, anchor="w")
        self.tabela_audio.pack(side="left", fill="both", expand=True)
        rolagem = ttk.Scrollbar(corpo, orient="vertical",
                                command=self.tabela_audio.yview)
        rolagem.pack(side="left", fill="y")
        self.tabela_audio.configure(yscrollcommand=rolagem.set)
        self.tabela_audio.bind("<Double-1>", lambda e: self._audio_tocar())

        rodape = tk.Frame(pai, bg=BG)
        rodape.pack(fill="x", padx=20, pady=(0, 4))
        self._botao(rodape, "▶ Tocar", self._audio_tocar).pack(side="left", padx=4)
        self.botao_pausa = self._botao(rodape, "⏸ Pausar", self._audio_pausar)
        self.botao_pausa.pack(side="left", padx=4)
        self._botao(rodape, "⏹ Parar", self._audio_parar).pack(side="left", padx=4)
        self._botao(rodape, "🗑 Remover som selecionado",
                    self._audio_remover, cor=RED).pack(side="left", padx=10)
        self._botao(rodape, "🔄 Atualizar", self._atualizar_audio).pack(side="right", padx=4)

        rodape2 = tk.Frame(pai, bg=BG)
        rodape2.pack(fill="x", padx=20, pady=(0, 10))
        self._botao(rodape2, "📂 Pasta de overrides",
                    lambda: self._abrir_pasta(self._audio_runtime_dir())).pack(side="left", padx=4)
        self._botao(rodape2, "📂 Pasta do pacote",
                    lambda: self._abrir_pasta(self._audio_pacote_dir())).pack(side="left", padx=4)
        self._botao(rodape2, "♻ Restaurar sons originais (git)",
                    self._audio_restaurar_git).pack(side="right", padx=4)
        self._botao(rodape2, "🧹 Limpar TODOS os overrides",
                    self._audio_limpar_overrides, cor=RED).pack(side="right", padx=4)

    # helpers de audio (imports tardios para nao pesar a abertura do painel)
    def _audio_api(self):
        from neural_fights.effects import audio_paths
        return audio_paths

    def _audio_runtime_dir(self) -> Path:
        return self._audio_api().get_runtime_sound_dir()

    def _audio_runtime_seguro(self) -> bool:
        """Garante que a pasta de overrides NAO e a pasta do pacote.

        Se NEURAL_FIGHTS_RUNTIME_DIR apontar para dentro do repositorio, a
        pasta de overrides vira a propria neural_fights/sounds e qualquer
        'limpar override' apagaria os assets originais do jogo.
        """
        runtime = Path(self._audio_runtime_dir()).resolve()
        pacote = Path(self._audio_pacote_dir()).resolve()
        if runtime == pacote or pacote in runtime.parents or runtime in pacote.parents:
            messagebox.showerror(
                "Operação bloqueada",
                "A pasta de overrides está resolvendo para a pasta do PACOTE:\n\n"
                f"{runtime}\n\n"
                "Apagar overrides aí destruiria os sons originais do jogo.\n"
                "Isso costuma acontecer quando a variável de ambiente\n"
                "NEURAL_FIGHTS_RUNTIME_DIR aponta para o repositório.")
            self._log(f"BLOQUEADO: pasta de overrides = pasta do pacote ({runtime})",
                      "erro")
            return False
        return True

    def _audio_pacote_dir(self) -> Path:
        return self._audio_api().PACKAGE_SOUND_DIR

    def _audio_eventos(self) -> dict:
        api = self._audio_api()
        config = api.load_sound_config()
        return {k: v for k, v in config.items() if not k.startswith("_")}

    def _abrir_pasta(self, pasta: Path):
        Path(pasta).mkdir(parents=True, exist_ok=True)
        os.startfile(pasta)

    def _atualizar_audio(self):
        if not hasattr(self, "tabela_audio"):
            return
        api = self._audio_api()
        runtime = self._audio_runtime_dir()
        self.tabela_audio.delete(*self.tabela_audio.get_children())
        for evento, arquivo in sorted(self._audio_eventos().items()):
            resolvido = api.resolve_sound_file(arquivo)
            if resolvido is None:
                origem = "⚠ MUDO (arquivo nao encontrado)"
            elif resolvido.parent == runtime:
                origem = "override local"
            else:
                origem = "pacote (padrao)"
            self.tabela_audio.insert("", "end", iid=evento,
                                     values=(evento, arquivo, origem))

    def _audio_copiar_eventos(self):
        eventos = "\n".join(sorted(self._audio_eventos()))
        self.clipboard_clear()
        self.clipboard_append(eventos)
        self._log("Lista de eventos de audio copiada para a area de transferencia.", "fim")

    def _audio_tocar(self):
        selecionado = self.tabela_audio.selection()
        if not selecionado:
            messagebox.showwarning("Tocar", "Selecione um evento na lista.")
            return
        evento = selecionado[0]
        api = self._audio_api()
        resolvido = api.resolve_sound_file(self._audio_eventos().get(evento))
        if resolvido is None:
            self._log(f"{evento}: sem arquivo para tocar.", "erro")
            return
        try:
            import pygame
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            pygame.mixer.stop()  # um som por vez: o novo substitui o anterior
            pygame.mixer.Sound(str(resolvido)).play()
            self._audio_pausado = False
            self.botao_pausa.configure(text="⏸ Pausar")
            self._log(f"tocando {evento} <- {resolvido.name}", "fim")
        except Exception as erro:
            self._log(f"nao consegui tocar {evento}: {erro}", "erro")

    def _audio_pausar(self):
        import pygame
        if pygame.mixer.get_init() is None:
            return
        if getattr(self, "_audio_pausado", False):
            pygame.mixer.unpause()
            self._audio_pausado = False
            self.botao_pausa.configure(text="⏸ Pausar")
        else:
            pygame.mixer.pause()
            self._audio_pausado = True
            self.botao_pausa.configure(text="▶ Retomar")

    def _audio_parar(self):
        import pygame
        if pygame.mixer.get_init() is not None:
            pygame.mixer.stop()
        self._audio_pausado = False
        self.botao_pausa.configure(text="⏸ Pausar")

    def _audio_remover(self):
        selecionado = self.tabela_audio.selection()
        if not selecionado:
            messagebox.showwarning("Remover", "Selecione um evento na lista.")
            return
        evento = selecionado[0]
        api = self._audio_api()
        self._audio_parar()
        config = self._audio_eventos()
        resolvido = api.resolve_sound_file(config.get(evento))
        if resolvido is None:
            self._log(f"{evento}: ja esta mudo, nada para remover.", "erro")
            return

        if resolvido.parent == self._audio_runtime_dir():
            if not self._audio_runtime_seguro():
                return
            if not messagebox.askyesno(
                    "Remover override",
                    f"Remover o som LOCAL de '{evento}'?\n"
                    "O evento volta a usar o som do pacote."):
                return
            api.remove_runtime_sound_overrides(evento)
            # devolve a entrada do config local para o padrao do pacote
            import json
            pacote_cfg = json.loads(
                api.get_package_config_path().read_text(encoding="utf-8"))
            runtime_cfg = api.load_sound_config()
            if evento in pacote_cfg:
                runtime_cfg[evento] = pacote_cfg[evento]
            else:
                runtime_cfg.pop(evento, None)
            api.save_sound_config(runtime_cfg)
            self._log(f"override de '{evento}' removido; voltou ao pacote.", "fim")
        else:
            if not messagebox.askyesno(
                    "Apagar do pacote",
                    f"Apagar '{resolvido.name}' do PACOTE?\n"
                    "O evento fica mudo (ou usa fallback) ate voce importar outro som.\n"
                    "Da para restaurar depois com 'Restaurar sons originais (git)'."):
                return
            resolvido.unlink()
            self._log(f"'{resolvido.name}' apagado do pacote "
                      f"(restauravel via git).", "fim")
        self._atualizar_audio()

    def _audio_importar(self):
        pasta = filedialog.askdirectory(title="Pasta com os novos audios (nomes = eventos)")
        if not pasta:
            return
        api = self._audio_api()
        extensoes = api.SUPPORTED_SOUND_EXTENSIONS
        eventos = self._audio_eventos()
        candidatos = {}
        for arquivo in sorted(Path(pasta).iterdir()):
            if arquivo.suffix.lower() in extensoes and arquivo.stem.lower() in eventos:
                candidatos[arquivo.stem.lower()] = arquivo
        ignorados = [f.name for f in Path(pasta).iterdir()
                     if f.suffix.lower() in extensoes
                     and f.stem.lower() not in eventos]
        if not candidatos:
            messagebox.showwarning(
                "Importar áudios",
                "Nenhum arquivo casou com os eventos.\nNomeie os arquivos como os "
                "eventos (use o botao 'Copiar lista de eventos').")
            return

        destino_pacote = messagebox.askyesno(
            "Importar áudios",
            f"{len(candidatos)} audio(s) casaram com eventos.\n\n"
            "SIM  = substituir os sons do PACOTE (neural_fights/sounds) — "
            "vale para o jogo inteiro e pode ser commitado.\n"
            "NAO = instalar como overrides locais (%LOCALAPPDATA%), "
            "sem tocar no pacote.")
        import shutil
        if destino_pacote:
            destino = self._audio_pacote_dir()
            config_path = api.get_package_config_path()
            import json
            config = json.loads(config_path.read_text(encoding="utf-8"))
            for evento, arquivo in candidatos.items():
                novo_nome = f"{evento}{arquivo.suffix.lower()}"
                antigo = config.get(evento)
                shutil.copy2(arquivo, destino / novo_nome)
                if antigo and antigo != novo_nome and (destino / antigo).exists():
                    (destino / antigo).unlink()
                config[evento] = novo_nome
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
            self._log(f"{len(candidatos)} som(ns) SUBSTITUIDOS no pacote.", "fim")
        else:
            destino = self._audio_runtime_dir()
            destino.mkdir(parents=True, exist_ok=True)
            config = api.load_sound_config()
            for evento, arquivo in candidatos.items():
                api.remove_runtime_sound_overrides(evento)
                novo_nome = f"{evento}{arquivo.suffix.lower()}"
                shutil.copy2(arquivo, destino / novo_nome)
                config[evento] = novo_nome
            api.save_sound_config(config)
            self._log(f"{len(candidatos)} override(s) locais instalados.", "fim")
        if ignorados:
            self._log("ignorados (nome nao é um evento): " + ", ".join(ignorados), "erro")
        self._atualizar_audio()

    def _audio_restaurar_git(self):
        if not messagebox.askyesno(
                "Restaurar sons",
                "Restaurar TODOS os sons originais do pacote a partir do git?\n"
                "(git restore -- neural_fights/sounds)"):
            return
        self._rodar(["git", "restore", "--", "neural_fights/sounds"],
                    rotulo="git restore neural_fights/sounds")
        self.after(1500, self._atualizar_audio)

    def _audio_limpar_overrides(self):
        if not self._audio_runtime_seguro():
            return
        if not messagebox.askyesno(
                "Limpar overrides",
                "Remover TODOS os overrides locais de som?\n"
                "O jogo volta a usar so os sons do pacote.\n"
                "(volumes salvos tambem voltam ao padrao)"):
            return
        api = self._audio_api()
        removidos = 0
        for evento in self._audio_eventos():
            removidos += api.remove_runtime_sound_overrides(evento)
        config_runtime = api.get_runtime_config_path()
        if config_runtime.is_file():
            config_runtime.unlink()
        self._log(f"{removidos} arquivo(s) de override removidos; "
                  "configuracao local resetada.", "fim")
        self._atualizar_audio()


def main():
    app = Painel()
    if "--smoke" in sys.argv:
        app.update()
        for chave in app.paginas:
            app._mostrar(chave)
            app.update()
        print("smoke ok:", ", ".join(app.paginas))
        app.destroy()
        return
    app.mainloop()


if __name__ == "__main__":
    main()
