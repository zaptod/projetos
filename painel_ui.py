"""PAINEL DE CONTROLE (interface grafica) - Neural Fights + Random Builds.

Janela unica com tudo: videos de build, biblioteca de reacoes, simulacao,
lives com chat do YouTube e database — botoes e formularios em vez de
comandos. Cada acao roda a CLI oficial da ferramenta em processo proprio;
a saida aparece ao vivo no console embutido.

Uso:  python painel_ui.py   (ou dois cliques em painel.bat)
"""
from __future__ import annotations

import ctypes
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

RAIZ = Path(__file__).resolve().parent
RANDOM_BUILDS = RAIZ / "random_builds"
PY = sys.executable
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

sys.path.insert(0, str(RANDOM_BUILDS))
from src.assets import importer as reacoes_importer  # noqa: E402
from src.assets.catalog import CATEGORIES  # noqa: E402
from src.assets.reaction_cli import CATEGORY_DESC  # noqa: E402
from src.assets.triagem import SessaoTriagem  # noqa: E402
from src.pipeline import fluxo  # noqa: E402
from src.publicar import catalogo as publicar_catalogo  # noqa: E402

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

# Os três jeitos de usar o painel (Ctrl+1/2/3; F11 alterna a tela cheia).
MODOS = ("janela", "cheia", "canto")

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
        self.configure(bg=BG)
        self._fila: queue.Queue = queue.Queue()
        self._processos: list[subprocess.Popen] = []
        # A janela tem que caber no monitor DESTE computador. O tamanho fixo
        # de 1180x760 estourava telas menores (e telas com escala do Windows,
        # onde o espaço lógico é menor que o físico): o rodapé ficava fora da
        # tela e os botões de baixo simplesmente não existiam para quem usa.
        self.minsize(420, 420)
        self._modo = self._layout_salvo().get("modo", "janela")
        self._sidebar_compacta = False
        self._console_visivel = True
        self._canvas_paginas: dict[str, tk.Canvas] = {}

        self._estilo_ttk()
        self._montar_layout()
        self._aplicar_modo(self._modo, salvar=False)
        self.bind("<Configure>", self._ao_redimensionar)
        self.bind("<F11>", lambda e: self._alternar_cheia())
        self.bind("<Escape>", lambda e: (self._aplicar_modo("janela")
                                         if self._modo == "cheia" else None))
        for indice, modo in enumerate(MODOS, start=1):
            self.bind(f"<Control-Key-{indice}>",
                      lambda e, m=modo: self._aplicar_modo(m))
        self.after(100, self._drenar_fila)

    # ------------------------------------------------------ janela e layout
    def _arquivo_layout(self) -> Path:
        try:
            from neural_fights.data.database import RUNTIME_DIR
            return Path(RUNTIME_DIR) / "painel_layout.json"
        except Exception:
            return RAIZ / ".painel_layout.json"

    def _layout_salvo(self) -> dict:
        import json
        try:
            with open(self._arquivo_layout(), encoding="utf-8-sig") as fh:
                dados = json.load(fh)
            return dados if isinstance(dados, dict) else {}
        except (OSError, ValueError):
            return {}

    def _salvar_layout(self):
        import json
        try:
            caminho = self._arquivo_layout()
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text(json.dumps({"modo": self._modo}, indent=2),
                               encoding="utf-8")
        except OSError:
            pass

    def _aplicar_modo(self, modo: str, salvar: bool = True):
        """janela | cheia | canto — os três jeitos de usar o painel.

        `canto` é o modo de acompanhar: janela estreita encostada na direita,
        sempre por cima, sem console — para deixar o Fluxo à vista enquanto
        você trabalha em outra coisa.
        """
        if modo not in MODOS:
            modo = "janela"
        self._modo = modo
        largura_tela = self.winfo_screenwidth()
        altura_tela = self.winfo_screenheight()
        self.attributes("-fullscreen", False)
        self.attributes("-topmost", modo == "canto")

        if modo == "cheia":
            self.attributes("-fullscreen", True)
        elif modo == "canto":
            self.state("normal")
            largura = max(420, min(560, int(largura_tela * 0.30)))
            altura = int(altura_tela * 0.90)
            self.geometry(f"{largura}x{altura}"
                          f"+{largura_tela - largura - 16}+16")
        else:
            self.state("normal")
            # Nunca maior que a tela: 40 px de folga para a barra de tarefas
            # e para a borda da janela.
            largura = min(1180, largura_tela - 40)
            altura = min(760, altura_tela - 80)
            self.geometry(f"{largura}x{altura}"
                          f"+{max(0, (largura_tela - largura) // 2)}"
                          f"+{max(0, (altura_tela - altura) // 2 - 20)}")
        # Trocar de modo é um recomeço: a escolha manual do console valia para
        # o modo anterior.
        self._console_manual = False
        if salvar:
            self._salvar_layout()
        self.after(60, self._reagir_ao_tamanho)
        if hasattr(self, "botoes_modo"):
            for chave, botao in self.botoes_modo.items():
                botao.configure(bg=ACCENT_DARK if chave == modo else PANEL,
                                fg=TEXT if chave == modo else DIM)

    def _alternar_cheia(self):
        self._aplicar_modo("janela" if self._modo == "cheia" else "cheia")

    def _ao_redimensionar(self, evento):
        """Reage ao tamanho REAL da janela, com debounce.

        `<Configure>` dispara dezenas de vezes ao arrastar a borda; refazer o
        layout em cada uma trava a janela.
        """
        if evento.widget is not self:
            return
        if getattr(self, "_debounce_tamanho", None):
            self.after_cancel(self._debounce_tamanho)
        self._debounce_tamanho = self.after(120, self._reagir_ao_tamanho)

    def _reagir_ao_tamanho(self):
        self._debounce_tamanho = None
        if not self.winfo_exists():
            return
        largura, altura = self.winfo_width(), self.winfo_height()
        # Janela estreita: o menu vira coluna de ícones em vez de sumir com o
        # conteúdo. 210 px de menu em 460 px de janela é metade da tela.
        compacta = largura < 900
        if compacta != self._sidebar_compacta:
            self._sidebar_compacta = compacta
            self._aplicar_sidebar()
        # Janela baixa (ou modo canto): o console de 11 linhas come o espaço
        # dos botões. Ele encolhe primeiro; o conteúdo é o que importa. Mas se
        # VOCÊ abriu o console na mão, ele fica: a decisão automática não pode
        # desfazer a sua a cada pixel de resize.
        if not getattr(self, "_console_manual", False):
            deve_mostrar = altura >= 620 and self._modo != "canto"
            if deve_mostrar != self._console_visivel:
                self._console_visivel = deve_mostrar
                self._aplicar_console()
        if self._console_visivel:
            self.console.configure(height=6 if altura < 780 else 11)
        for canvas in self._canvas_paginas.values():
            self._ajustar_rolagem(canvas)

    def _aplicar_sidebar(self):
        compacta = self._sidebar_compacta
        self.sidebar.configure(width=58 if compacta else 210)
        self.logo.configure(
            text="NF" if compacta else "NEURAL\nFIGHTS",
            font=("Segoe UI", 15 if compacta else 17, "bold"))
        for chave, botao in self.botoes_menu.items():
            rotulo = self._rotulos_menu[chave]
            botao.configure(text=rotulo.split()[0] if compacta else rotulo,
                            padx=6 if compacta else 18,
                            anchor="center" if compacta else "w")
        self.rodape_sidebar.pack_forget() if compacta else self.rodape_sidebar.pack(
            side="bottom", anchor="w", padx=18, pady=14)

    def _aplicar_console(self):
        if self._console_visivel:
            self.console_frame.pack(side="bottom", fill="x")
        else:
            self.console_frame.pack_forget()
        if hasattr(self, "botao_console"):
            self.botao_console.configure(
                text="▾ console" if self._console_visivel else "▴ console")

    def _alternar_console(self):
        self._console_visivel = not self._console_visivel
        self._console_manual = True
        self._aplicar_console()

    # -------------------------------------------------------- rolagem geral
    def _pagina_rolavel(self, pai):
        """Devolve o frame onde a página é montada, já com rolagem vertical.

        É a garantia de que NENHUM botão some: quando a janela encolhe, o
        conteúdo continua inteiro e ganha barra de rolagem, em vez de ser
        cortado pelo `pack` sem aviso.
        """
        canvas = tk.Canvas(pai, bg=BG, highlightthickness=0, bd=0)
        barra = ttk.Scrollbar(pai, orient="vertical", command=canvas.yview)
        interno = tk.Frame(canvas, bg=BG)
        janela = canvas.create_window((0, 0), window=interno, anchor="nw")
        canvas.configure(yscrollcommand=barra.set)
        canvas.pack(side="left", fill="both", expand=True)
        canvas._barra = barra          # noqa: SLF001 - guardado para o ajuste
        canvas._janela = janela        # noqa: SLF001
        canvas._interno = interno      # noqa: SLF001

        interno.bind("<Configure>", lambda e: self._ajustar_rolagem(canvas))
        canvas.bind("<Configure>", lambda e: self._ajustar_rolagem(canvas))
        # A roda só rola a página que está sob o mouse.
        canvas.bind("<Enter>", lambda e: canvas.bind_all(
            "<MouseWheel>",
            lambda ev: canvas.yview_scroll(int(-ev.delta / 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        return interno, canvas

    def _ajustar_rolagem(self, canvas):
        if not canvas.winfo_exists():
            return
        interno = canvas._interno          # noqa: SLF001
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfigure(canvas._janela,  # noqa: SLF001
                             width=max(1, canvas.winfo_width()))
        # Barra só quando ela é necessária: uma barra sempre visível numa
        # página curta é ruído.
        precisa = interno.winfo_reqheight() > canvas.winfo_height() + 2
        barra = canvas._barra              # noqa: SLF001
        if precisa and not barra.winfo_ismapped():
            barra.pack(side="right", fill="y")
        elif not precisa and barra.winfo_ismapped():
            barra.pack_forget()

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
        self.logo = tk.Label(self.sidebar, text="NEURAL\nFIGHTS", bg=PANEL,
                             fg=ACCENT, font=("Segoe UI", 17, "bold"),
                             justify="left")
        self.logo.pack(anchor="w", padx=18, pady=(20, 18))

        self.paginas: dict[str, tk.Frame] = {}
        self.botoes_menu: dict[str, tk.Button] = {}
        self._rotulos_menu: dict[str, str] = {}
        conteudo = tk.Frame(self, bg=BG)
        conteudo.pack(side="right", fill="both", expand=True)

        # console embutido (parte de baixo)
        console_frame = tk.Frame(conteudo, bg=PANEL)
        self.console_frame = console_frame
        console_frame.pack(side="bottom", fill="x")
        barra = tk.Frame(console_frame, bg=PANEL)
        barra.pack(fill="x", padx=10, pady=(8, 0))
        self.botao_console = tk.Button(
            barra, text="▾ console", bd=0, font=FONT_B, bg=PANEL, fg=DIM,
            activebackground=PANEL, activeforeground=TEXT, cursor="hand2",
            command=self._alternar_console)
        self.botao_console.pack(side="left")
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
            ("fluxo", "🧭  Fluxo", self._pagina_fluxo),
            ("publicar", "📤  Publicar", self._pagina_publicar),
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
            # Cada página vive dentro de um container rolável: se a janela for
            # menor que o conteúdo, ele rola — nunca desaparece.
            interno, canvas = self._pagina_rolavel(frame)
            construtor(interno)
            self.paginas[chave] = frame
            self._canvas_paginas[chave] = canvas
            self._rotulos_menu[chave] = rotulo
            botao = tk.Button(
                self.sidebar, text=rotulo, anchor="w", bd=0, font=FONT_B,
                bg=PANEL, fg=TEXT, activebackground=CARD_HL,
                activeforeground=TEXT, padx=18, pady=10, cursor="hand2",
                command=lambda c=chave: self._mostrar(c))
            botao.pack(fill="x")
            # No menu compacto sobra só o ícone; a dica é o que diz o nome.
            self._dica(botao, rotulo.strip())
            self.botoes_menu[chave] = botao

        # modos de janela: janela / tela cheia / canto da tela
        modos = tk.Frame(self.sidebar, bg=PANEL)
        modos.pack(side="bottom", fill="x", pady=(6, 10))
        self.botoes_modo: dict[str, tk.Button] = {}
        for chave, icone, dica in (("janela", "🗖", "Janela (Ctrl+1)"),
                                   ("cheia", "⛶", "Tela cheia (F11 / Ctrl+2)"),
                                   ("canto", "📌", "Canto da tela (Ctrl+3)")):
            botao = tk.Button(modos, text=icone, bd=0, font=("Segoe UI", 12),
                              bg=PANEL, fg=DIM, activebackground=ACCENT_DARK,
                              activeforeground=TEXT, cursor="hand2", padx=6,
                              command=lambda c=chave: self._aplicar_modo(c))
            botao.pack(side="left", expand=True)
            self._dica(botao, dica)
            self.botoes_modo[chave] = botao

        self.rodape_sidebar = tk.Label(
            self.sidebar, text="cada botao roda a CLI\noficial da ferramenta",
            bg=PANEL, fg=DIM, font=("Segoe UI", 8), justify="left")
        self.rodape_sidebar.pack(side="bottom", anchor="w", padx=18, pady=14)
        self._mostrar("fluxo")

    def _dica(self, widget, texto: str):
        """Tooltip simples: no menu de ícones, o rótulo some e a dica fica."""
        def mostrar(_evento=None):
            if getattr(widget, "_dica_janela", None):
                return
            janela = tk.Toplevel(self)
            janela.wm_overrideredirect(True)
            janela.configure(bg=CARD_HL)
            tk.Label(janela, text=texto, bg=CARD_HL, fg=TEXT, font=("Segoe UI", 8),
                     padx=8, pady=4).pack()
            janela.geometry(f"+{widget.winfo_rootx() + 10}"
                            f"+{widget.winfo_rooty() - 28}")
            widget._dica_janela = janela  # noqa: SLF001

        def esconder(_evento=None):
            janela = getattr(widget, "_dica_janela", None)
            if janela is not None:
                janela.destroy()
                widget._dica_janela = None  # noqa: SLF001

        widget.bind("<Enter>", mostrar, add="+")
        widget.bind("<Leave>", esconder, add="+")

    def _mostrar(self, chave: str):
        self.paginas[chave].tkraise()
        for nome, botao in self.botoes_menu.items():
            botao.configure(bg=CARD_HL if nome == chave else PANEL,
                            fg=ACCENT if nome == chave else TEXT)
        if chave == "fluxo":
            self._atualizar_fluxo()
        if chave == "publicar":
            self._atualizar_publicar()
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
    # =====================================================================
    # PAGINA: FLUXO — onde cada build esta e o que fazer agora
    # =====================================================================
    def _pagina_fluxo(self, pai):
        """A pipeline inteira numa tela: build -> identidade -> estreia -> torneio.

        As outras paginas sao FERRAMENTAS (cada uma faz uma coisa); esta e o
        MAPA. Ela nao roda nada por conta propria: le o disco e a fila (via
        `src.pipeline.fluxo`, o mesmo do `main.py fluxo`) e, para cada build,
        mostra o proximo passo com o botao que o executa.
        """
        self._titulo(pai, "Fluxo da pipeline — o que já saiu e o que falta")

        # --- faixa de resumo (fila, arena, chaves do torneio)
        resumo = tk.Frame(pai, bg=BG)
        resumo.pack(fill="x", padx=20)
        self.fluxo_resumo: dict[str, tk.Label] = {}
        for chave, titulo in (("fila", "FILA DE IDENTIDADE"),
                              ("torneio", "PREPARAÇÃO DO TORNEIO"),
                              ("arena", "ARENA")):
            card = self._card(resumo, titulo)
            card.pack(side="left", fill="both", expand=True,
                      padx=(0, 8) if chave != "arena" else 0)
            rotulo = tk.Label(card, text="lendo...", bg=CARD, fg=TEXT,
                              font=FONT, justify="left", anchor="w")
            rotulo.pack(anchor="w", fill="x")
            self.fluxo_resumo[chave] = rotulo

        # --- alertas: o que exige acao agora
        self.fluxo_alertas = tk.Label(
            pai, text="", bg=BG, fg=ORANGE, font=FONT_B, justify="left",
            anchor="w", wraplength=900)
        self.fluxo_alertas.pack(fill="x", padx=20, pady=(8, 0))

        # --- tabela das builds
        topo = tk.Frame(pai, bg=BG)
        topo.pack(fill="x", padx=20, pady=(10, 2))
        tk.Label(topo, text="BUILDS  (duplo-clique abre a pasta)", bg=BG,
                 fg=DIM, font=FONT_B).pack(side="left")
        self._botao(topo, "↻  Atualizar", self._atualizar_fluxo).pack(side="right")
        caixa_auto, self.var_fluxo_auto = self._check(topo, "Atualizar sozinho")
        caixa_auto.configure(bg=BG, activebackground=BG)
        caixa_auto.pack(side="right", padx=8)

        colunas = ("build", "personagem") + tuple(
            chave for chave, _r, _s in fluxo.ETAPAS) + ("passo",)
        self.tabela_fluxo = ttk.Treeview(pai, columns=colunas, show="headings",
                                         height=11)
        cabecalhos = {"build": ("BUILD", 120), "personagem": ("PERSONAGEM", 150),
                      "passo": ("PRÓXIMO PASSO", 420)}
        for coluna in colunas:
            titulo, largura = cabecalhos.get(
                coluna, (fluxo.CURTOS.get(coluna, coluna.upper()), 62))
            self.tabela_fluxo.heading(coluna, text=titulo)
            self.tabela_fluxo.column(
                coluna, width=largura, anchor="w" if largura > 100 else "center",
                stretch=coluna == "passo")
        self.tabela_fluxo.pack(fill="both", expand=True, padx=20, pady=(0, 6))
        self.tabela_fluxo.tag_configure("completa", foreground=OK)
        self.tabela_fluxo.tag_configure("andando", foreground=ORANGE)
        self.tabela_fluxo.tag_configure("parada", foreground=RED)
        self.tabela_fluxo.tag_configure("neutra", foreground=TEXT)
        self.tabela_fluxo.bind(
            "<Double-1>", lambda e: self._fluxo_acao("pasta"))

        # --- acoes sobre a build selecionada
        acoes = tk.Frame(pai, bg=BG)
        acoes.pack(fill="x", padx=20, pady=(0, 10))
        self._botao(acoes, "▶  Assistir", lambda: self._fluxo_acao("assistir")
                    ).pack(side="left")
        self._botao(acoes, "📁  Pasta", lambda: self._fluxo_acao("pasta")
                    ).pack(side="left", padx=6)
        self._botao(acoes, "🔁  Re-renderizar",
                    lambda: self._fluxo_acao("rerender")).pack(side="left")
        self._botao(acoes, "🧩  Enfileirar identidade",
                    lambda: self._fluxo_acao("identidade")).pack(side="left", padx=6)
        self._botao(acoes, "⚔️  Gerar estreia",
                    lambda: self._fluxo_acao("estreia")).pack(side="left")
        tk.Frame(acoes, bg=BG, width=18).pack(side="left")
        self._botao_primario(acoes, "⬇  Processar fila",
                             self._digen_worker).pack(side="left")
        self._botao(acoes, "🏆  Rodar torneio",
                    lambda: self._mostrar("torneio")).pack(side="left", padx=6)

        self.fluxo_legenda = tk.Label(
            pai, bg=BG, fg=DIM, font=("Segoe UI", 8), justify="left", anchor="w",
            text="✓ pronto    ▶ gerando agora    … na fila    ✕ falhou    · não começou"
                 "        (as etapas seguem a ordem em que acontecem)")
        self.fluxo_legenda.pack(fill="x", padx=20, pady=(0, 8))

    _FLUXO_SIMBOLO = {"ok": "✓", "rodando": "▶", "fila": "…",
                      "falhou": "✕", "ausente": "·"}

    def _atualizar_fluxo(self):
        """Le o snapshot FORA da thread da UI (ele toca disco e banco).

        O resultado volta por FILA e quem mexe no Tk e sempre a thread
        principal: `after()` chamado de dentro da thread estoura
        "main thread is not in main loop" — o Tkinter nao e thread-safe.
        """
        if not hasattr(self, "tabela_fluxo"):
            return
        if getattr(self, "_fluxo_lendo", False):
            return
        self._fluxo_lendo = True
        self._fluxo_fila: queue.Queue = getattr(self, "_fluxo_fila", queue.Queue())

        def trabalho():
            try:
                dados = fluxo.snapshot(limite=15)
            except Exception as exc:  # a tela nunca cai por causa do status
                dados = {"erro": f"{type(exc).__name__}: {exc}"}
            self._fluxo_fila.put(dados)

        threading.Thread(target=trabalho, daemon=True).start()
        self.after(150, self._colher_fluxo)

    def _colher_fluxo(self):
        """Na thread da UI: pega o snapshot pronto ou volta a esperar."""
        try:
            dados = self._fluxo_fila.get_nowait()
        except queue.Empty:
            if getattr(self, "_fluxo_lendo", False):
                self.after(150, self._colher_fluxo)
            return
        self._aplicar_fluxo(dados)

    def _aplicar_fluxo(self, dados: dict):
        self._fluxo_lendo = False
        if not hasattr(self, "tabela_fluxo"):
            return
        if dados.get("erro"):
            self.fluxo_alertas.configure(
                text=f"não consegui ler o fluxo: {dados['erro']}", fg=RED)
            return

        self._fluxo_dados = {g["generation_id"]: g for g in dados["geracoes"]}
        selecionado = self.tabela_fluxo.selection()
        self.tabela_fluxo.delete(*self.tabela_fluxo.get_children())
        for geracao in dados["geracoes"]:
            estados = [geracao["etapas"][chave]["estado"]
                       for chave, _r, _s in fluxo.ETAPAS]
            simbolos = [self._FLUXO_SIMBOLO.get(e, "?") for e in estados]
            if geracao["completa"]:
                tag = "completa"
            elif "falhou" in estados:
                tag = "parada"
            elif "rodando" in estados or "fila" in estados:
                tag = "andando"
            else:
                tag = "neutra"
            self.tabela_fluxo.insert(
                "", "end", iid=geracao["generation_id"], tags=(tag,),
                values=(geracao["generation_id"], geracao["personagem"],
                        *simbolos, geracao["proximo_passo"]))
        if selecionado and self.tabela_fluxo.exists(selecionado[0]):
            self.tabela_fluxo.selection_set(selecionado)

        fila = dados["fila"]
        self.fluxo_resumo["fila"].configure(
            text=(f"{fila.get('pending', 0)} na fila · "
                  f"{fila.get('running', 0)} gerando · "
                  f"{fila.get('failed', 0)} com falha\n"
                  f"última atividade há {fluxo.idade(dados['ultima_atividade'])}"))
        chaves = dados["chaves"]
        if chaves["chave_gerados"]:
            linha = f"dá para uma chave de {chaves['chave_gerados']} gerados"
        else:
            linha = (f"faltam {chaves['faltam_para_proxima']} build(s) "
                     "para a chave de 4")
        self.fluxo_resumo["torneio"].configure(
            text=(f"{chaves['prontos']} build(s) com vídeo pronto — {linha}\n"
                  f"banco: {chaves['no_banco']} personagens "
                  f"(chave de {chaves['chave_banco']})"))
        arena = dados["arena"]
        campeao = arena.get("campeao") or "ninguém ainda"
        self.fluxo_resumo["arena"].configure(
            text=(f"{arena.get('lutas', 0)} luta(s) registradas\n"
                  f"campeão: {campeao}"))

        alertas = dados["alertas"]
        self.fluxo_alertas.configure(
            text=("⚠  " + "\n⚠  ".join(alertas)) if alertas else "",
            fg=ORANGE)

        if getattr(self, "var_fluxo_auto", None) and self.var_fluxo_auto.get():
            self.after(20000, self._atualizar_fluxo)

    def _fluxo_selecionada(self) -> str | None:
        selecionado = self.tabela_fluxo.selection()
        if not selecionado:
            messagebox.showwarning("Fluxo", "Selecione uma build na lista.")
            return None
        return selecionado[0]

    def _fluxo_acao(self, acao: str):
        gid = self._fluxo_selecionada()
        if gid is None:
            return
        pasta = RANDOM_BUILDS / "outputs" / gid
        if acao == "pasta":
            if pasta.is_dir():
                os.startfile(pasta)
            return
        if acao == "assistir":
            for nome in ("final_celular.mp4", "final_normal.mp4"):
                if (pasta / nome).is_file():
                    os.startfile(pasta / nome)
                    return
            messagebox.showwarning("Fluxo", f"{gid} ainda não tem vídeo.")
            return
        if acao == "rerender":
            self._rodar([PY, "main.py", "generate-video", "--rerender", gid,
                         "--refazer-edicao"], cwd=RANDOM_BUILDS,
                        rotulo=f"re-render {gid}")
            return
        if acao == "identidade":
            self._rodar([PY, "main.py", "identity", "run", gid],
                        cwd=RANDOM_BUILDS, rotulo=f"identidade {gid}")
            return
        if acao == "estreia":
            dados = getattr(self, "_fluxo_dados", {}).get(gid) or {}
            personagem = dados.get("personagem")
            if not personagem or personagem == "?":
                messagebox.showwarning(
                    "Fluxo", f"não achei o personagem de {gid}.")
                return
            self._rodar([PY, "main.py", "fight", "--p1", personagem],
                        cwd=RANDOM_BUILDS, rotulo=f"estreia de {personagem}")

    # =====================================================================
    # PAGINA: PUBLICAR — todos os videos num lugar, um clique para enviar
    # =====================================================================
    def _pagina_publicar(self, pai):
        """Todo mp4 pronto (build, estreia, torneio) com texto e envio.

        O atrito nunca foi o render: era achar o arquivo. Os mp4 nascem em
        tres lugares diferentes, todos com o mesmo nome (`final_celular.mp4`)
        e nada dizendo de quem sao. Aqui eles aparecem juntos, com titulo e
        descricao ja escritos a partir dos dados da build — da para exportar
        com nome legivel ou mandar direto para o YouTube/TikTok.
        """
        self._titulo(pai, "Publicar — todos os vídeos prontos")

        filtros = tk.Frame(pai, bg=BG)
        filtros.pack(fill="x", padx=20)
        tk.Label(filtros, text="Mostrar:", bg=BG, fg=DIM, font=FONT).pack(side="left")
        self.combo_pub_origem = ttk.Combobox(
            filtros, width=12, state="readonly",
            values=("todos", "build", "estreia", "torneio"))
        self.combo_pub_origem.set("todos")
        self.combo_pub_origem.pack(side="left", padx=6)
        self.combo_pub_perfil = ttk.Combobox(
            filtros, width=14, state="readonly",
            values=("todos", "celular (9:16)", "normal (16:9)"))
        self.combo_pub_perfil.set("celular (9:16)")
        self.combo_pub_perfil.pack(side="left")
        for combo in (self.combo_pub_origem, self.combo_pub_perfil):
            combo.bind("<<ComboboxSelected>>",
                       lambda e: self._atualizar_publicar())
        self._botao(filtros, "↻  Atualizar", self._atualizar_publicar).pack(side="right")
        self._botao(filtros, "📂  Pasta de exportação",
                    self._abrir_pasta_export).pack(side="right", padx=6)

        corpo = tk.Frame(pai, bg=BG)
        corpo.pack(fill="both", expand=True, padx=20, pady=(8, 0))

        # lista dos videos
        esquerda = tk.Frame(corpo, bg=BG)
        esquerda.pack(side="left", fill="both", expand=True)
        self.tabela_pub = ttk.Treeview(
            esquerda, columns=("titulo", "origem", "tamanho", "quando"),
            show="headings", height=12)
        for coluna, titulo, largura in (("titulo", "VÍDEO", 330),
                                        ("origem", "TIPO", 70),
                                        ("tamanho", "MB", 55),
                                        ("quando", "QUANDO", 80)):
            self.tabela_pub.heading(coluna, text=titulo)
            self.tabela_pub.column(coluna, width=largura,
                                   anchor="w" if largura > 100 else "center",
                                   stretch=coluna == "titulo")
        self.tabela_pub.pack(fill="both", expand=True)
        self.tabela_pub.bind("<<TreeviewSelect>>",
                             lambda e: self._mostrar_texto_publicar())
        self.tabela_pub.bind("<Double-1>", lambda e: self._publicar_acao("assistir"))

        # texto que vai junto com o video
        direita = tk.Frame(corpo, bg=CARD, padx=12, pady=10)
        direita.pack(side="left", fill="both", padx=(10, 0))
        tk.Label(direita, text="TÍTULO", bg=CARD, fg=ACCENT,
                 font=FONT_B).pack(anchor="w")
        self.texto_pub_titulo = tk.Text(direita, height=2, width=44, bg=CARD_HL,
                                        fg=TEXT, insertbackground=TEXT, bd=0,
                                        font=FONT, wrap="word")
        self.texto_pub_titulo.pack(fill="x", pady=(2, 8))
        tk.Label(direita, text="DESCRIÇÃO (com as hashtags)", bg=CARD, fg=ACCENT,
                 font=FONT_B).pack(anchor="w")
        self.texto_pub_desc = tk.Text(direita, height=11, width=44, bg=CARD_HL,
                                      fg=TEXT, insertbackground=TEXT, bd=0,
                                      font=FONT, wrap="word")
        self.texto_pub_desc.pack(fill="both", expand=True, pady=(2, 6))
        linha_texto = tk.Frame(direita, bg=CARD)
        linha_texto.pack(fill="x")
        self._botao(linha_texto, "💾  Salvar texto",
                    self._salvar_texto_publicar).pack(side="left")
        self._botao(linha_texto, "📋  Copiar",
                    self._copiar_texto_publicar).pack(side="left", padx=6)
        tk.Label(direita, text="o texto salvo vale nos dois envios",
                 bg=CARD, fg=DIM, font=("Segoe UI", 8)).pack(anchor="w", pady=(6, 0))

        # acoes
        acoes = tk.Frame(pai, bg=BG)
        acoes.pack(fill="x", padx=20, pady=(10, 4))
        self._botao(acoes, "▶  Assistir",
                    lambda: self._publicar_acao("assistir")).pack(side="left")
        self._botao(acoes, "📁  Pasta",
                    lambda: self._publicar_acao("pasta")).pack(side="left", padx=6)
        self._botao_primario(acoes, "📤  EXPORTAR",
                             lambda: self._publicar_acao("exportar")).pack(side="left")
        tk.Frame(acoes, bg=BG, width=20).pack(side="left")
        self._botao(acoes, "▶  Enviar ao YouTube",
                    lambda: self._publicar_acao("youtube"),
                    cor="#c4302b").pack(side="left")
        tk.Label(acoes, text="visibilidade:", bg=BG, fg=DIM,
                 font=FONT).pack(side="left", padx=(8, 2))
        self.combo_pub_vis = ttk.Combobox(
            acoes, width=11, state="readonly",
            values=("private", "unlisted", "public"))
        self.combo_pub_vis.set(
            (publicar_catalogo.carregar_config().get("youtube") or {})
            .get("visibilidade", "private"))
        self.combo_pub_vis.pack(side="left")
        self._botao(acoes, "▶  Enviar ao TikTok",
                    lambda: self._publicar_acao("tiktok"),
                    cor="#25252d").pack(side="left", padx=8)

        setup = tk.Frame(pai, bg=BG)
        setup.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(setup, text="uma vez só:", bg=BG, fg=DIM, font=FONT).pack(side="left")
        self._botao(setup, "🔑  Autorizar upload no YouTube",
                    self._oauth_upload).pack(side="left", padx=6)
        self._botao(setup, "🔑  Login no TikTok",
                    self._tiktok_login).pack(side="left")
        self._botao(setup, "🧪  Sondar tela do TikTok",
                    self._tiktok_sondar).pack(side="left", padx=6)
        tk.Label(pai, bg=BG, fg=DIM, font=("Segoe UI", 8), justify="left",
                 text="O YouTube usa a API oficial (o vídeo sobe como PRIVADO por padrão — "
                      "você publica no Studio). O TikTok não tem API aberta: o painel abre o "
                      "navegador na SUA conta, sobe o arquivo, escreve a legenda e PARA antes "
                      "de publicar.").pack(anchor="w", padx=20, pady=(0, 8))

    def _publicar_filtrados(self) -> list:
        origem = self.combo_pub_origem.get()
        perfil = self.combo_pub_perfil.get().split()[0]
        videos = publicar_catalogo.listar()
        if origem != "todos":
            videos = [v for v in videos if v.origem == origem]
        if perfil != "todos":
            videos = [v for v in videos if v.perfil == perfil]
        return videos

    def _atualizar_publicar(self):
        if not hasattr(self, "tabela_pub"):
            return
        import datetime
        selecionado = self.tabela_pub.selection()
        self._pub_videos = {v.id: v for v in self._publicar_filtrados()}
        self.tabela_pub.delete(*self.tabela_pub.get_children())
        for video in self._pub_videos.values():
            quando = datetime.datetime.fromtimestamp(video.quando)
            self.tabela_pub.insert(
                "", "end", iid=video.id,
                values=(video.titulo, video.origem,
                        f"{video.bytes / 1e6:.0f}", quando.strftime("%d/%m %H:%M")))
        if selecionado and self.tabela_pub.exists(selecionado[0]):
            self.tabela_pub.selection_set(selecionado)
        elif self._pub_videos:
            primeiro = next(iter(self._pub_videos))
            self.tabela_pub.selection_set(primeiro)

    def _publicar_selecionado(self):
        selecionado = self.tabela_pub.selection()
        if not selecionado:
            messagebox.showwarning("Publicar", "Selecione um vídeo na lista.")
            return None
        return getattr(self, "_pub_videos", {}).get(selecionado[0])

    def _mostrar_texto_publicar(self):
        video = getattr(self, "_pub_videos", {}).get(
            (self.tabela_pub.selection() or [None])[0])
        if video is None:
            return
        self.texto_pub_titulo.delete("1.0", "end")
        self.texto_pub_titulo.insert("1.0", video.titulo)
        self.texto_pub_desc.delete("1.0", "end")
        self.texto_pub_desc.insert("1.0", video.descricao_completa)

    def _texto_editado(self) -> tuple[str, str]:
        return (self.texto_pub_titulo.get("1.0", "end").strip(),
                self.texto_pub_desc.get("1.0", "end").strip())

    def _salvar_texto_publicar(self, silencioso: bool = False):
        """Grava o texto da tela como o texto DAQUELE vídeo.

        Salvar antes de enviar é o que faz o envio usar o que está na tela —
        o subprocesso lê do catálogo, não da janela.
        """
        video = self._publicar_selecionado()
        if video is None:
            return None
        titulo, descricao = self._texto_editado()
        if not titulo:
            messagebox.showwarning("Publicar", "O título não pode ficar vazio.")
            return None
        publicar_catalogo.salvar_texto(video.id, titulo, descricao)
        self._atualizar_publicar()
        if not silencioso:
            self._log(f"[texto] salvo para {video.id}\n", "fim")
        return video.id

    def _copiar_texto_publicar(self):
        titulo, descricao = self._texto_editado()
        self.clipboard_clear()
        self.clipboard_append(f"{titulo}\n\n{descricao}")
        self._log("[texto] copiado para a área de transferência\n", "fim")

    def _abrir_pasta_export(self):
        pasta = publicar_catalogo.pasta_export()
        pasta.mkdir(parents=True, exist_ok=True)
        os.startfile(pasta)

    def _publicar_acao(self, acao: str):
        video = self._publicar_selecionado()
        if video is None:
            return
        if acao == "assistir":
            os.startfile(video.caminho)
            return
        if acao == "pasta":
            os.startfile(video.caminho.parent)
            return

        # Qualquer coisa que ESCREVA usa o texto que está na tela.
        if self._salvar_texto_publicar(silencioso=True) is None:
            return

        if acao == "exportar":
            destino = publicar_catalogo.exportar(
                publicar_catalogo.por_id(video.id) or video)
            self._log(f"[exportar] {destino}\n", "fim")
            os.startfile(destino.parent)
            return
        if acao == "youtube":
            visibilidade = self.combo_pub_vis.get()
            if visibilidade == "public" and not messagebox.askyesno(
                    "Publicar no YouTube",
                    f"Enviar '{video.titulo}' como PÚBLICO?\n\n"
                    "Ele fica visível para todo mundo assim que terminar de "
                    "processar. Cancelar manda como privado."):
                return
            self._rodar([PY, "main.py", "publicar", video.id, "--youtube",
                         "--visibilidade", visibilidade],
                        cwd=RANDOM_BUILDS, rotulo=f"YouTube: {video.titulo[:40]}")
            return
        if acao == "tiktok":
            if not video.vertical and not messagebox.askyesno(
                    "TikTok", "Este é o corte 16:9 (normal). O TikTok espera "
                              "o 9:16 (celular).\n\nEnviar assim mesmo?"):
                return
            self._rodar([PY, "main.py", "publicar", video.id, "--tiktok"],
                        cwd=RANDOM_BUILDS, rotulo=f"TikTok: {video.titulo[:40]}")

    def _credenciais_youtube(self) -> tuple[str, str]:
        """client-id/secret: dos campos da tela ou do arquivo que a live já usa.

        Quem configurou a live UMA vez não tem por que voltar ao Google Cloud
        Console para autorizar o upload — os dois campos já estão gravados em
        `youtube_credentials.json`; o que falta é só o escopo novo.
        """
        cliente = getattr(self, "var_client_id", None)
        segredo = getattr(self, "var_client_secret", None)
        atual = (cliente.get().strip() if cliente else "",
                 segredo.get().strip() if segredo else "")
        if all(atual):
            return atual
        try:
            from src.publicar.youtube import carregar_credenciais
            salvas = carregar_credenciais()
        except Exception:
            salvas = None
        if salvas is None:
            return atual
        return salvas.client_id, salvas.client_secret

    def _oauth_upload(self):
        """Re-autoriza o YouTube pedindo TAMBÉM o escopo de upload."""
        cliente, segredo = self._credenciais_youtube()
        if not (cliente and segredo):
            messagebox.showinfo(
                "Autorizar upload",
                "Não achei o client-id/client-secret do YouTube.\n\n"
                "Preencha os dois na página Live / YouTube (card CREDENCIAIS "
                "DO YOUTUBE) e clique aqui de novo — são os dados do projeto "
                "no Google Cloud Console.")
            self._mostrar("live")
            return
        messagebox.showinfo(
            "Autorizar upload",
            "Vou abrir o navegador no login do Google.\n\n"
            "1. entre com a conta DO CANAL\n"
            "2. se aparecer 'app não verificado', clique em Avançado → "
            "Acessar (o app é seu)\n"
            "3. marque a permissão de gerenciar/enviar vídeos\n\n"
            "A janela avisa quando terminar; o console mostra o resultado.")
        self._rodar([PY, "-m", "neural_fights.tools.youtube_oauth",
                     "--client-id", cliente, "--client-secret", segredo,
                     "--com-upload"],
                    rotulo="youtube_oauth --com-upload (credenciais ocultas)")

    def _tiktok_login(self):
        self._rodar([PY, "-m", "src.publicar.tiktok", "--login"],
                    cwd=RANDOM_BUILDS, rotulo="login no TikTok")

    def _tiktok_sondar(self):
        self._rodar([PY, "-m", "src.publicar.tiktok", "--sondar"],
                    cwd=RANDOM_BUILDS, rotulo="sondar TikTok")

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
            linha, "Identidade (imagens + video)", ligado=True)
        caixa_ident.pack(side="left", padx=8)
        caixa_estreia, self.var_estreia = self._check(
            linha, "Estreia (grava a 1ª luta)", ligado=True)
        caixa_estreia.pack(side="left")
        # Pedido de comentário: nome, quem pediu e o print como prova. Fica
        # junto do botão de gerar porque é decisão da MESMA rodada — separar
        # em outro card faria esquecer de preencher antes de clicar.
        linha_pedido = tk.Frame(gerar, bg=CARD)
        linha_pedido.pack(anchor="w", pady=(8, 0))
        tk.Label(linha_pedido, text="Pedido de comentário:", bg=CARD, fg=ACCENT,
                 font=FONT_B).pack(side="left", padx=(0, 8))
        campo_nome, self.var_nome_pedido = self._campo(linha_pedido, "Nome:", 16)
        campo_nome.pack(side="left")
        campo_autor, self.var_autor_pedido = self._campo(linha_pedido, "de:", 14)
        campo_autor.pack(side="left", padx=(6, 0))

        linha_print = tk.Frame(gerar, bg=CARD)
        linha_print.pack(anchor="w", pady=(4, 0))
        self.var_print_pedido = tk.StringVar()
        botao_print = self._botao(linha_print, "🖼  Print do comentário…",
                                  self._escolher_print)
        botao_print.pack(side="left")
        self._dica(botao_print, "A imagem entra como tela logo depois do gancho")
        self.lbl_print = tk.Label(linha_print, text="nenhum print escolhido",
                                  bg=CARD, fg=DIM, font=FONT)
        self.lbl_print.pack(side="left", padx=8)
        self._botao(linha_print, "limpar", self._limpar_print).pack(side="left")

        # Escolher em vez de sortear. Linha própria e rótulo dizendo o padrão:
        # a premissa do canal é a roleta decidir, então escolher é exceção e
        # precisa ficar visível que foi feito.
        linha_escolhas = tk.Frame(gerar, bg=CARD)
        linha_escolhas.pack(anchor="w", pady=(8, 0))
        self.escolhas_fixas: dict[str, str] = {}
        botao_escolher = self._botao(linha_escolhas, "🎛  Escolher atributos…",
                                     self._abrir_escolhas)
        botao_escolher.pack(side="left")
        self._dica(botao_escolher,
                   "Gênero, classe, altura… o que você não escolher, a roleta sorteia")
        self.lbl_escolhas = tk.Label(linha_escolhas, text="tudo sorteado",
                                     bg=CARD, fg=DIM, font=FONT)
        self.lbl_escolhas.pack(side="left", padx=8)

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
        # Linha própria, e não ao lado do botão acima: lado a lado, a linha
        # passava da largura do card e o `pack` recortava ESTE botão sem
        # avisar — o mesmo jeito que a UI já escondeu botão antes.
        linha3 = tk.Frame(rerender, bg=CARD)
        linha3.pack(anchor="w", pady=(2, 2))
        botao = self._botao(linha3, "+ print do comentário",
                            self._rerender_com_print)
        botao.pack(side="left")
        self._dica(botao, "Escolhe o print e re-renderiza esta geração com ele")

        identidade = self._card(
            pai, "IDENTIDADE VISUAL (PicassoIA + Digen) — 2 imagens e 1 video")
        identidade.pack(fill="x", padx=20, pady=(8, 0))
        tk.Label(identidade,
                 text="A roleta so ENFILEIRA e termina na hora. O worker gera as "
                      "imagens do personagem e da arma no PicassoIA, anexa as duas "
                      "no Digen para o video final e refaz o video com tudo dentro. "
                      "Cada site tem seu proprio login: faca uma vez em cada.",
                 bg=CARD, fg=DIM, font=FONT, justify="left").pack(anchor="w")
        linha_login = tk.Frame(identidade, bg=CARD)
        linha_login.pack(anchor="w", pady=(8, 2))
        self._botao(linha_login, "🔑  Login no PicassoIA",
                    self._picasso_login).pack(side="left")
        self._botao(linha_login, "🔑  Login no Digen",
                    self._digen_login).pack(side="left", padx=8)
        linha_ident = tk.Frame(identidade, bg=CARD)
        linha_ident.pack(anchor="w", pady=(2, 2))
        self._botao_primario(linha_ident, "⬇  Processar fila",
                             self._digen_worker).pack(side="left", padx=8)
        self._botao(linha_ident, "Ver fila", self._digen_fila).pack(side="left")
        self._botao(linha_ident, "🧪  Diagnostico",
                    self._digen_doctor).pack(side="left", padx=8)
        self._botao(linha_ident, "📊  Status",
                    self._digen_status).pack(side="left")
        # As contas dos sites sao compartilhadas: o que "ficou pronto" rapido
        # demais nao foi gerado, ja estava la — e era de outra pessoa.
        self._botao(linha_ident, "🔎  Auditar origem",
                    self._digen_auditar).pack(side="left", padx=8)
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

    IMAGENS = [("Imagem", "*.png *.jpg *.jpeg *.webp"), ("Todos", "*.*")]

    def _escolher_print(self):
        caminho = filedialog.askopenfilename(title="Print do comentário",
                                             filetypes=self.IMAGENS)
        if caminho:
            self.var_print_pedido.set(caminho)
            self.lbl_print.configure(text=Path(caminho).name, fg=TEXT)

    def _limpar_print(self):
        self.var_print_pedido.set("")
        self.lbl_print.configure(text="nenhum print escolhido", fg=DIM)

    ALEATORIO = "— sortear —"

    def _abrir_escolhas(self):
        """Janela de escolha, montada a partir do catálogo de roletas.

        Nada de lista escrita aqui: classe nova no neural_fights aparece
        sozinha, do mesmo jeito que aparece na roleta. Cada atributo começa em
        "sortear" — é o padrão do formato, e sair dele é decisão consciente.
        """
        from src.generation import escolhas as mod_escolhas

        try:
            catalogo = mod_escolhas.catalogo()
        except Exception as erro:                       # catálogo do NF fora do ar
            messagebox.showerror("Escolher atributos", str(erro))
            return

        janela = tk.Toplevel(self)
        janela.title("Escolher atributos")
        janela.configure(bg=BG)
        janela.transient(self)
        # Cabe na tela dele: alta o bastante para os 15 atributos, e rolável.
        altura = min(int(self.winfo_screenheight() * 0.8), 40 * len(catalogo) + 150)
        janela.geometry(f"560x{altura}")

        corpo, _canvas = self._pagina_rolavel(janela)
        tk.Label(corpo, text="O que você NÃO escolher aqui, a roleta sorteia.",
                 bg=BG, fg=DIM, font=FONT, wraplength=500,
                 justify="left").pack(anchor="w", padx=16, pady=(12, 8))

        campos: dict[str, tk.StringVar] = {}
        for chave, entrada in catalogo.items():
            linha = tk.Frame(corpo, bg=BG)
            linha.pack(fill="x", padx=16, pady=3)
            tk.Label(linha, text=entrada["rotulo"], bg=BG, fg=TEXT, font=FONT,
                     width=18, anchor="w").pack(side="left")
            var = tk.StringVar(value=self.escolhas_fixas.get(chave, self.ALEATORIO))
            campos[chave] = var
            if entrada["tipo"] == "categorical":
                combo = ttk.Combobox(linha, textvariable=var, width=30,
                                     state="readonly",
                                     values=[self.ALEATORIO] + list(entrada["opcoes"]))
                combo.pack(side="left")
            else:
                tk.Entry(linha, textvariable=var, width=12, bg=CARD_HL, fg=TEXT,
                         insertbackground=TEXT, bd=0,
                         font=FONT).pack(side="left", ipady=3)
                unidade = f" {entrada['unidade']}" if entrada.get("unidade") else ""
                tk.Label(linha, bg=BG, fg=DIM, font=FONT,
                         text=f"{entrada['minimo']:g} a {entrada['maximo']:g}"
                              f"{unidade}").pack(side="left", padx=8)

        rodape = tk.Frame(corpo, bg=BG)
        rodape.pack(fill="x", padx=16, pady=12)

        def aplicar():
            escolhido = {chave: var.get().strip()
                         for chave, var in campos.items()
                         if var.get().strip() not in ("", self.ALEATORIO)}
            try:
                # Valida AQUI: descobrir um valor fora da faixa só na geração
                # gastaria a rodada inteira para nada.
                mod_escolhas.interpretar([f"{k}={v}" for k, v in escolhido.items()])
            except ValueError as erro:
                messagebox.showerror("Escolher atributos", str(erro), parent=janela)
                return
            self.escolhas_fixas = escolhido
            self._mostrar_escolhas()
            janela.destroy()

        def limpar():
            for var in campos.values():
                var.set(self.ALEATORIO)

        self._botao(rodape, "Aplicar", aplicar, cor=ACCENT).pack(side="left")
        self._botao(rodape, "Sortear tudo", limpar).pack(side="left", padx=8)
        self._botao(rodape, "Cancelar", janela.destroy).pack(side="left")

    def _mostrar_escolhas(self):
        if not self.escolhas_fixas:
            self.lbl_escolhas.configure(text="tudo sorteado", fg=DIM)
            return
        resumo = ", ".join(f"{k}={v}" for k, v in self.escolhas_fixas.items())
        self.lbl_escolhas.configure(text=resumo[:60], fg=ACCENT)

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
        if not self.var_estreia.get():
            extras.append("--no-estreia")
        return extras + self._flags_pedido()

    def _flags_pedido(self):
        """Nome, autor e print do comentário — só o que estiver preenchido.

        Campo vazio não vira flag: `--nome-pedido ""` faria o pipeline tratar
        como pedido recusado em vez de "não houve pedido".
        """
        extras = []
        for flag, var in (("--nome-pedido", self.var_nome_pedido),
                          ("--autor-pedido", self.var_autor_pedido),
                          ("--print-pedido", self.var_print_pedido)):
            valor = var.get().strip()
            if valor:
                extras += [flag, valor]
        for chave, valor in (getattr(self, "escolhas_fixas", None) or {}).items():
            # `genero` tem flag própria na CLI; o resto vai por --fixar.
            if chave == "genero":
                extras += ["--genero", valor]
            else:
                extras += ["--fixar", f"{chave}={valor}"]
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

    def _rerender_com_print(self):
        """Põe o print numa geração que já virou vídeo, e re-renderiza."""
        escolha = self.combo_geracao.get()
        if not escolha:
            messagebox.showwarning("Print do comentário",
                                   "Nenhuma geração selecionada.")
            return
        caminho = filedialog.askopenfilename(
            title=f"Print do comentário — {escolha}", filetypes=self.IMAGENS)
        if not caminho:
            return
        extras = ["--preview"] if self.var_preview2.get() else []
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "generate-video",
                     "--rerender", escolha, "--refazer-edicao",
                     "--print-pedido", caminho] + extras, RANDOM_BUILDS)

    # -------------------------------------------------- identidade (Digen)
    def _digen_login(self):
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "identity", "login",
                     "--provedor", "digen"],
                    RANDOM_BUILDS, rotulo="digen login")

    def _picasso_login(self):
        """Login separado de proposito: cada site tem seu perfil de Chrome.

        Nao e so cookie — o Chrome trava o diretorio de perfil, e o projeto
        encerra processos filtrando por ele. Com perfil unico, abrir um site
        derrubaria o browser que esta esperando geracao no outro.
        """
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "identity", "login",
                     "--provedor", "picasso"],
                    RANDOM_BUILDS, rotulo="picasso login")

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

    def _digen_auditar(self):
        """Prova de origem de cada artefato (ver README, 'Contas compartilhadas')."""
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "identity", "auditar"],
                    RANDOM_BUILDS, rotulo="auditoria de origem")

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
        self._botao(topo, "🎬 Categorizar assistindo…",
                    self._categorizar_assistindo).pack(side="left", padx=8)

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

    def _categorizar_assistindo(self):
        janela = getattr(self, "_janela_triagem", None)
        if janela is not None and janela.winfo_exists():
            janela.lift()
            janela.focus_force()
            return
        self._janela_triagem = JanelaTriagem(self)

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

        luta = self._card(pai, "LUTA ÚNICA  —  uma luta, um vídeo (a luta é o "
                               "elemento dominante; entra quase inteira)")
        luta.pack(fill="x", padx=20, pady=6)
        linha = tk.Frame(luta, bg=CARD)
        linha.pack(anchor="w", pady=2)
        campo_p1, self.var_luta_p1 = self._campo(linha, "P1:", 18)
        campo_p1.pack(side="left")
        campo_p2, self.var_luta_p2 = self._campo(linha, "P2:", 18)
        campo_p2.pack(side="left", padx=(8, 0))
        tk.Label(linha, text="Arena:", bg=CARD, fg=DIM, font=FONT).pack(
            side="left", padx=(10, 0))
        self.combo_arena_luta = ttk.Combobox(
            linha, width=13, state="readonly",
            values=["(sorteio)", "Arena Pequena", "Ringue", "Cyberpunk", "Dojo", "Templo"])
        self.combo_arena_luta.set("(sorteio)")
        self.combo_arena_luta.pack(side="left", padx=6)
        campo_seed_luta, self.var_seed_luta = self._campo(linha, "Seed:", 10)
        campo_seed_luta.pack(side="left", padx=(8, 0))
        linha2 = tk.Frame(luta, bg=CARD)
        linha2.pack(anchor="w", pady=(8, 2))
        self._botao_primario(linha2, "🥊  GRAVAR LUTA", self._rodar_luta).pack(side="left")
        self._botao(linha2, "Só dados", lambda: self._rodar_luta(so_dados=True)).pack(
            side="left", padx=8)
        self._botao(linha2, "🏅 Ranking da arena", self._ranking_arena).pack(
            side="left", padx=8)
        tk.Label(linha2,
                 text="P1 vazio = último criado na roleta; P2 vazio = adversário "
                      "por continuidade/poder. Toda luta conta no cartel.",
                 bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack(side="left", padx=12)

        topo = tk.Frame(pai, bg=BG)
        topo.pack(fill="x", padx=20, pady=(10, 2))
        tk.Label(topo, text="TORNEIOS E LUTAS  (duplo-clique assiste)", bg=BG, fg=ACCENT,
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

    def _rodar_luta(self, so_dados: bool = False):
        args = [PY, "-u", "-X", "utf8", "main.py", "fight"]
        if self.var_luta_p1.get().strip():
            args += ["--p1", self.var_luta_p1.get().strip()]
        if self.var_luta_p2.get().strip():
            args += ["--p2", self.var_luta_p2.get().strip()]
        arena = self.combo_arena_luta.get()
        if arena and not arena.startswith("("):
            args += ["--arena", arena]
        if self.var_seed_luta.get().strip():
            args += ["--seed", self.var_seed_luta.get().strip()]
        if so_dados:
            args.append("--generation-only")
        elif self.var_preview_torneio.get():
            args.append("--preview")
        self._rodar(args, RANDOM_BUILDS)

    def _ranking_arena(self):
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "arena", "ranking"],
                    RANDOM_BUILDS)

    def _rerender_torneio(self):
        pasta = self._torneio_selecionado()
        if pasta is None:
            return
        refazer = messagebox.askyesno(
            "Re-renderizar",
            "Remontar também a edição (legendas e reações novas)?\n\n"
            "As lutas gravadas são reaproveitadas nos dois casos — elas são a "
            "parte cara.")
        comando = "fight" if pasta.name.startswith("fight_") else "tournament"
        args = [PY, "-u", "-X", "utf8", "main.py", comando,
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
        saidas = RANDOM_BUILDS / "outputs"
        pastas = sorted(list(saidas.glob("tournament_*")) + list(saidas.glob("fight_*"))
                        + list(saidas.glob("generation_*/estreia")),
                        key=lambda p: p.stat().st_mtime)
        for pasta in reversed(pastas):
            campeao, lutas, destaque = "?", "", ""
            try:
                if (pasta / "fight.json").exists():
                    dados = json.loads((pasta / "fight.json").read_text(encoding="utf-8"))
                    luta_dados = dados.get("luta", {})
                    campeao = str(luta_dados.get("vencedor", "?"))
                    if luta_dados.get("vencedor_gerado"):
                        campeao += "  ⭐"
                    lutas = "1"
                    partes = [f"{luta_dados.get('p1', '?')} x {luta_dados.get('p2', '?')}"]
                    if dados.get("origem") == "estreia":
                        partes.insert(0, "🐣 estreia")
                    if luta_dados.get("marcas"):
                        partes.append(", ".join(luta_dados["marcas"][:2]))
                    destaque = " • ".join(partes)
                else:
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
            rotulo = (f"{pasta.parent.name}/estreia" if pasta.name == "estreia"
                      else pasta.name)
            self.tabela_torneios.insert(
                "", "end", iid=rotulo,
                values=(rotulo, campeao, lutas, destaque,
                        " + ".join(formatos) if formatos else "(sem video)"))

    def _torneio_selecionado(self) -> Path | None:
        selecionado = self.tabela_torneios.selection()
        if not selecionado:
            messagebox.showwarning("Torneio", "Selecione um torneio ou luta na lista.")
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


class JanelaTriagem(tk.Toplevel):
    """Categorizar assistindo: os videos do pack tocam um a um DENTRO da
    janela, e um clique (ou tecla 1-9) importa na categoria clicada.

    O ffplay abre com um titulo unico, a janela dele e adotada como filha do
    frame preto (SetParent) e o input dela e desligado — os atalhos ficam
    sempre com o painel; espaco e as setas sao repassados ao player via
    PostMessage. Sem ffplay no PATH, cada video abre no player padrao do
    sistema e os botoes continuam valendo. A fila, a importacao e o desfazer
    vivem em SessaoTriagem (random_builds/src/assets/triagem.py).
    """

    GWL_STYLE = -16
    WS_CHILD = 0x40000000
    WS_VISIBLE = 0x10000000
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    VK_SPACE = 0x20
    VK_LEFT = 0x25
    VK_RIGHT = 0x27

    def __init__(self, painel: Painel):
        super().__init__(painel)
        self.painel = painel
        self.title("Categorizar assistindo — biblioteca de reações")
        self.geometry("1080x800")
        self.minsize(900, 660)
        self.configure(bg=BG)
        self.sessao = SessaoTriagem(RANDOM_BUILDS / "assets")
        self.fila: list[str] = []
        self.idx = 0
        self.importados_sessao = 0
        self._player: subprocess.Popen | None = None
        self._hwnd = 0
        self._geracao = 0     # invalida callbacks (embed/sonda) de video antigo
        self._dims = None     # (largura, altura) do video atual, para o letterbox
        self._ocupado = False
        self._ffplay = shutil.which("ffplay")
        self._montar()
        self._atalhos()
        self.protocol("WM_DELETE_WINDOW", self._fechar)
        if not self._ffplay:
            self.painel._log("[triagem] ffplay não encontrado no PATH — os "
                             "vídeos vão abrir no player padrão do sistema.", "erro")

    # ------------------------------------------------------------ interface
    def _montar(self):
        topo = tk.Frame(self, bg=BG)
        topo.pack(fill="x", padx=14, pady=(12, 6))
        self.painel._botao_primario(topo, "📂 Escolher pasta do pack…",
                                    self._escolher_pasta).pack(side="left")
        self.var_mover = tk.BooleanVar(value=False)
        tk.Checkbutton(topo, text="mover em vez de copiar",
                       variable=self.var_mover, bg=BG, fg=DIM,
                       selectcolor=CARD_HL, activebackground=BG,
                       activeforeground=TEXT, font=FONT,
                       takefocus=0).pack(side="left", padx=12)
        self.lbl_contador = tk.Label(topo, text="", bg=BG, fg=DIM, font=FONT_B)
        self.lbl_contador.pack(side="right")

        self.lbl_pasta = tk.Label(self, text="", bg=BG, fg=DIM, font=FONT,
                                  anchor="w")
        self.lbl_pasta.pack(fill="x", padx=16)

        self.frame_video = tk.Frame(self, bg="#000000")
        self.frame_video.pack(fill="both", expand=True, padx=14, pady=8)
        self.frame_video.bind("<Configure>", lambda e: self._ajustar_video())
        self.lbl_msg = tk.Label(self.frame_video,
                                text="Escolha a pasta do pack para começar.",
                                bg="#000000", fg=DIM, font=FONT_TITLE)
        self.lbl_msg.place(relx=0.5, rely=0.5, anchor="center")

        info = tk.Frame(self, bg=BG)
        info.pack(fill="x", padx=16)
        self.lbl_nome = tk.Label(info, text="", bg=BG, fg=TEXT, font=FONT_B,
                                 anchor="w")
        self.lbl_nome.pack(side="left")
        self.lbl_detalhes = tk.Label(info, text="", bg=BG, fg=DIM, font=FONT)
        self.lbl_detalhes.pack(side="right")

        grade = tk.Frame(self, bg=BG)
        grade.pack(fill="x", padx=14, pady=6)
        self.botoes_categoria: dict[str, tk.Button] = {}
        contagens = self.sessao.contagens()
        for i, cat in enumerate(CATEGORIES):
            botao = tk.Button(
                grade, text=self._texto_botao(i, cat, contagens[cat]),
                command=lambda c=cat: self._categorizar(c), bd=0, bg=PANEL,
                fg=TEXT, activebackground=ACCENT_DARK, activeforeground=TEXT,
                font=FONT, justify="left", anchor="w", padx=12, pady=8,
                cursor="hand2", takefocus=0)
            botao.grid(row=i // 3, column=i % 3, sticky="nsew", padx=3, pady=3)
            self.botoes_categoria[cat] = botao
        for coluna in range(3):
            grade.grid_columnconfigure(coluna, weight=1)

        rodape = tk.Frame(self, bg=BG)
        rodape.pack(fill="x", padx=14, pady=(0, 12))
        self.painel._botao(rodape, "Pular  (S)", self._pular).pack(side="left", padx=3)
        self.painel._botao(rodape, "Desfazer último  (Z)",
                           self._desfazer_ultimo).pack(side="left", padx=3)
        self.painel._botao(rodape, "⏯ Pausar  (Espaço)",
                           self._pausar).pack(side="left", padx=3)
        self.painel._botao(rodape, "Abrir no player do sistema",
                           self._abrir_externo).pack(side="right", padx=3)
        tk.Label(rodape, text="1–9 categoriza · ←/→ ±10s", bg=BG, fg=DIM,
                 font=("Segoe UI", 8)).pack(side="right", padx=10)

    def _texto_botao(self, indice: int, categoria: str, contagem: int) -> str:
        return (f"{indice + 1}  {categoria}  ·  {contagem} na biblioteca\n"
                f"{CATEGORY_DESC[categoria]}")

    def _atualizar_contagens(self, contagens: dict):
        for i, cat in enumerate(CATEGORIES):
            self.botoes_categoria[cat].configure(
                text=self._texto_botao(i, cat, contagens[cat]))

    def _atalhos(self):
        for i in range(1, 10):
            self.bind(str(i), lambda e, n=i: self._categoria_por_numero(n))
        self.bind("<s>", lambda e: self._pular())
        self.bind("<S>", lambda e: self._pular())
        self.bind("<z>", lambda e: self._desfazer_ultimo())
        self.bind("<Z>", lambda e: self._desfazer_ultimo())
        self.bind("<space>", lambda e: self._pausar())
        self.bind("<Left>", lambda e: self._seek(self.VK_LEFT))
        self.bind("<Right>", lambda e: self._seek(self.VK_RIGHT))

    def _categoria_por_numero(self, numero: int):
        if numero <= len(CATEGORIES):
            self._categorizar(CATEGORIES[numero - 1])

    # ----------------------------------------------------------------- fila
    def _atual(self) -> str | None:
        return self.fila[self.idx] if self.fila else None

    def _escolher_pasta(self):
        inicial = self.sessao.ultima_pasta() or str(RAIZ)
        pasta = filedialog.askdirectory(title="Pasta com o pack de vídeos",
                                        initialdir=inicial, parent=self)
        if not pasta:
            return
        try:
            resultado = self.sessao.carregar_pasta(pasta)
        except (OSError, ValueError) as erro:
            messagebox.showerror("Carregar pasta", str(erro), parent=self)
            return
        self.fila = resultado["fila"]
        self.idx = 0
        self.importados_sessao = 0
        self.lbl_pasta.configure(text=resultado["raiz"])
        aviso = (f" ({resultado['ja_importados']} já estavam na biblioteca)"
                 if resultado["ja_importados"] else "")
        self.painel._log(f"[triagem] {len(self.fila)} vídeo(s) na fila{aviso}")
        if not self.fila:
            messagebox.showinfo(
                "Carregar pasta",
                "Nenhum vídeo novo nessa pasta." +
                (aviso and f"\n{resultado['ja_importados']} já estava(m) "
                           "na biblioteca."), parent=self)
        self._mostrar_atual()

    def _mostrar_atual(self):
        self._parar_player()
        nome = self._atual()
        if nome is None:
            self.lbl_nome.configure(text="")
            self.lbl_detalhes.configure(text="")
            self.lbl_contador.configure(text="")
            if self.importados_sessao:
                self.lbl_msg.configure(
                    text=f"✔ Pack concluído — {self.importados_sessao} "
                         "importado(s) nesta sessão.", fg=OK)
            self.focus_set()
            return
        self.lbl_msg.configure(text="")
        self.lbl_nome.configure(text=nome)
        self.lbl_detalhes.configure(text="…")
        self.lbl_contador.configure(
            text=f"{self.idx + 1} de {len(self.fila)} restantes")
        caminho = self.sessao.resolver(nome)
        self._dims = None
        self._tocar(caminho)
        geracao = self._geracao
        threading.Thread(target=self._sondar, args=(caminho, geracao),
                         daemon=True).start()
        self.focus_set()

    def _sondar(self, caminho: Path, geracao: int):
        info = reacoes_importer.probe_info(caminho)
        self.after(0, lambda: self._aplicar_sonda(info, geracao))

    def _aplicar_sonda(self, info: dict, geracao: int):
        if geracao != self._geracao or not self.winfo_exists():
            return
        duracao = f"{info['duration']}s" if info["duration"] else "?s"
        resolucao = (f"{info['width']}x{info['height']}"
                     if info["width"] else "resolução desconhecida")
        self.lbl_detalhes.configure(text=f"{duracao} · {resolucao}")
        if info["width"] and info["height"]:
            self._dims = (info["width"], info["height"])
            self._ajustar_video()

    # --------------------------------------------------------------- player
    def _tocar(self, caminho: Path):
        self._geracao += 1
        if not self._ffplay:
            os.startfile(str(caminho))
            self.lbl_msg.configure(
                text="Tocando no player do sistema…", fg=DIM)
            return
        titulo = f"nf_triagem_{os.getpid()}_{self._geracao}"
        self._player = subprocess.Popen(
            [self._ffplay, "-loop", "0", "-v", "error", "-nostats",
             "-volume", "85", "-window_title", titulo, str(caminho)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW)
        self.after(120, lambda: self._embutir(titulo, self._geracao, 0))

    def _embutir(self, titulo: str, geracao: int, tentativa: int):
        if geracao != self._geracao or not self.winfo_exists():
            return
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, titulo)
        if not hwnd:
            if self._player is None or self._player.poll() is not None:
                # ffplay morreu sem abrir janela: formato que ele nao le
                self.lbl_msg.configure(
                    text="⚠ Não consegui tocar este vídeo.\n"
                         "Use “Abrir no player do sistema” — os botões "
                         "de categoria continuam valendo.", fg=RED)
                return
            if tentativa >= 50:
                self.painel._log("[triagem] não consegui embutir o player; "
                                 "ele segue em janela separada.", "erro")
                return
            self.after(100, lambda: self._embutir(titulo, geracao,
                                                  tentativa + 1))
            return
        user32.SetWindowLongW(hwnd, self.GWL_STYLE,
                              self.WS_CHILD | self.WS_VISIBLE)
        user32.SetParent(hwnd, self.frame_video.winfo_id())
        user32.EnableWindow(hwnd, False)
        self._hwnd = hwnd
        self._ajustar_video()

    def _ajustar_video(self):
        if not self._hwnd:
            return
        larg = self.frame_video.winfo_width()
        alt = self.frame_video.winfo_height()
        w, h = larg, alt
        if self._dims:
            aspecto = self._dims[0] / self._dims[1]
            if larg / max(alt, 1) > aspecto:
                w, h = int(alt * aspecto), alt
            else:
                w, h = larg, int(larg / aspecto)
        ctypes.windll.user32.MoveWindow(
            self._hwnd, (larg - w) // 2, (alt - h) // 2, w, h, True)

    def _parar_player(self):
        self._geracao += 1
        self._hwnd = 0
        if self._player is not None and self._player.poll() is None:
            self._player.kill()
            try:
                self._player.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
        self._player = None

    def _tecla_para_player(self, vk: int):
        if not self._hwnd:
            return
        user32 = ctypes.windll.user32
        user32.PostMessageW(self._hwnd, self.WM_KEYDOWN, vk, 0)
        user32.PostMessageW(self._hwnd, self.WM_KEYUP, vk, 0)

    def _pausar(self):
        self._tecla_para_player(self.VK_SPACE)

    def _seek(self, vk: int):
        self._tecla_para_player(vk)

    # ---------------------------------------------------------------- acoes
    def _categorizar(self, categoria: str):
        nome = self._atual()
        if nome is None or self._ocupado:
            return
        self._ocupado = True
        self._parar_player()  # solta o arquivo antes de copiar/mover
        try:
            resultado = self.sessao.categorizar(nome, categoria,
                                                self.var_mover.get())
        except (OSError, ValueError) as erro:
            self._ocupado = False
            messagebox.showerror("Categorizar", str(erro), parent=self)
            self._mostrar_atual()
            return
        self._ocupado = False
        entrada = resultado["entrada"]
        self.importados_sessao += 1
        del self.fila[self.idx]
        self._atualizar_contagens(resultado["contagens"])
        self.painel._log(f"[triagem] ID {entrada['id']} <- "
                         f"{entrada['source']} ({categoria})")
        self.painel._atualizar_reacoes()
        self._mostrar_atual()

    def _pular(self):
        if self.fila:
            self.idx = (self.idx + 1) % len(self.fila)
            self._mostrar_atual()

    def _desfazer_ultimo(self):
        if self._ocupado:
            return
        try:
            resultado = self.sessao.desfazer()
        except (OSError, ValueError) as erro:
            messagebox.showinfo("Desfazer", str(erro), parent=self)
            return
        self.fila.insert(self.idx, resultado["arquivo"])
        self.importados_sessao = max(0, self.importados_sessao - 1)
        self._atualizar_contagens(resultado["contagens"])
        self.painel._log(f"[triagem] desfeito: {resultado['arquivo']}")
        self.painel._atualizar_reacoes()
        self._mostrar_atual()

    def _abrir_externo(self):
        nome = self._atual()
        if nome is not None:
            os.startfile(str(self.sessao.resolver(nome)))

    def _fechar(self):
        self._parar_player()
        self.destroy()


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
