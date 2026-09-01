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
HISTORIAS = RAIZ / "historias"
PY = sys.executable
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

sys.path.insert(0, str(RANDOM_BUILDS))
from builds import atividade as atividade_reg  # noqa: E402
from builds import travas as travas_reg  # noqa: E402
from builds import contas as contas_reg  # noqa: E402
from builds.assets import importer as reacoes_importer  # noqa: E402
from builds.identity import controle as pipeline_controle  # noqa: E402
from builds.assets.catalog import CATEGORIES  # noqa: E402
from builds.assets.reaction_cli import CATEGORY_DESC  # noqa: E402
from builds.assets.triagem import SessaoTriagem  # noqa: E402
from builds.pipeline import fluxo  # noqa: E402
from builds.publicar import catalogo as publicar_catalogo  # noqa: E402
from builds.publicar import youtube as youtube_reg  # noqa: E402

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
        self._pipeline_estado()
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

        # --- FREIO DE MAO: controle da pipeline, visivel de qualquer pagina.
        # A conta dos sites de video e COMPARTILHADA: quando outra pessoa esta
        # usando, tem que dar para parar sem caçar processo nem digitar comando.
        controle_frame = tk.Frame(conteudo, bg=CARD_HL)
        controle_frame.pack(side="bottom", fill="x")
        faixa = tk.Frame(controle_frame, bg=CARD_HL)
        faixa.pack(fill="x", padx=10, pady=6)
        tk.Label(faixa, text="PIPELINE", bg=CARD_HL, fg=DIM,
                 font=FONT_B).pack(side="left")
        self.lbl_pipeline = tk.Label(faixa, text="lendo...", bg=CARD_HL, fg=TEXT,
                                     font=FONT_B, anchor="w")
        self.lbl_pipeline.pack(side="left", padx=10)
        self._botao(faixa, "▶  Retomar", self._pipeline_retomar,
                    cor=OK).pack(side="right", padx=3)
        self._botao(faixa, "⏹  Parar worker", self._pipeline_parar,
                    cor=RED).pack(side="right", padx=3)
        self._botao(faixa, "⏸  Pausar 1h",
                    lambda: self._pipeline_pausar(minutos=60)).pack(side="right", padx=3)
        self._botao(faixa, "⏸  Pausar tudo",
                    lambda: self._pipeline_pausar()).pack(side="right", padx=3)
        self.combo_pausa_alvo = ttk.Combobox(
            faixa, values=("tudo", "digen", "picasso"), width=9, state="readonly")
        self.combo_pausa_alvo.set("tudo")
        self.combo_pausa_alvo.pack(side="right", padx=(12, 3))
        tk.Label(faixa, text="alvo:", bg=CARD_HL, fg=DIM,
                 font=FONT).pack(side="right")

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
            ("vila", "🏭  Vila", self._pagina_vila),
            ("fluxo", "🧭  Fluxo", self._pagina_fluxo),
            ("publicar", "📤  Publicar", self._pagina_publicar),
            ("videos", "🎬  Vídeos de Build", self._pagina_videos),
            ("historias", "📖  Histórias", self._pagina_historias),
            ("contas", "🔑  Contas", self._pagina_contas),
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
        if chave == "historias":
            self._atualizar_historias()
        if chave == "contas":
            self._atualizar_contas()
        self._vila_visivel = chave == "vila"
        if self._vila_visivel:
            self._vila_dados()
            self._vila_tick()
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

    def _rodar(self, args, cwd=RAIZ, rotulo=None, ao_terminar=None):
        """`ao_terminar` roda NO THREAD DA UI, quando o processo acaba.

        Ele existe porque a thread do processo nao pode tocar em widget nem
        chamar `after()` — isso derruba o Tkinter. A volta e pela fila, que
        `_drenar_fila` ja consome no lugar certo.
        """
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
                         args=(proc, mostrado, ao_terminar),
                         daemon=True).start()

    def _ler_processo(self, proc, rotulo, ao_terminar=None):
        for linha in proc.stdout:
            self._fila.put(("linha", linha.rstrip()))
        codigo = proc.wait()
        self._fila.put(("fim", f"({rotulo}) terminou com codigo {codigo}",
                        codigo, ao_terminar))

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
                    depois = item[3] if len(item) > 3 else None
                    if depois is not None:
                        try:
                            depois()
                        except Exception as erro:
                            self._log(f"[painel] {erro}", "erro")
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

    # ------------------------------------------------ controle da pipeline
    def _pipeline_estado(self):
        """Le o interruptor e pinta a faixa. Roda sozinho a cada 3 s."""
        if not hasattr(self, "lbl_pipeline"):
            return
        try:
            estado = pipeline_controle.estado()
        except Exception as erro:
            self.lbl_pipeline.configure(text=f"não li o controle: {erro}", fg=RED)
            self.after(5000, self._pipeline_estado)
            return
        cor = {pipeline_controle.RODANDO: OK,
               pipeline_controle.PAUSADO: ORANGE,
               pipeline_controle.PARANDO: RED}[estado["situacao"]]
        simbolo = {pipeline_controle.RODANDO: "●",
                   pipeline_controle.PAUSADO: "⏸",
                   pipeline_controle.PARANDO: "⏹"}[estado["situacao"]]
        self.lbl_pipeline.configure(text=f"{simbolo}  {estado['resumo']}", fg=cor)
        self.after(3000, self._pipeline_estado)

    def _pipeline_pausar(self, minutos=None):
        alvo = self.combo_pausa_alvo.get() or pipeline_controle.TUDO
        motivo = ("ferramenta em uso por outra pessoa" if minutos is None
                  else f"pausa de {minutos:.0f} min pelo painel")
        estado = pipeline_controle.pausar(alvo, motivo, minutos)
        self._log(f"[pipeline] {estado['resumo']}", "fim")
        self._log("[pipeline] o job em andamento termina; nenhum novo começa.")
        self._pipeline_estado()

    def _pipeline_retomar(self):
        estado = pipeline_controle.retomar()
        self._log(f"[pipeline] {estado['resumo']}", "fim")
        self._pipeline_estado()

    def _pipeline_parar(self):
        """Parada LIMPA: o worker termina o job atual, fecha o browser e sai."""
        if not messagebox.askyesno(
                "Parar worker",
                "Parar a pipeline de forma limpa?\n\n"
                "O job que está em andamento TERMINA (nada é perdido) e o "
                "worker encerra em seguida. Nenhum job novo é pego.\n\n"
                "Para voltar depois: ▶ Retomar."):
            return
        estado = pipeline_controle.pedir_parada("parado pelo painel")
        self._log(f"[pipeline] {estado['resumo']}", "erro")
        self._pipeline_estado()

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
        `builds.pipeline.fluxo`, o mesmo do `main.py fluxo`) e, para cada build,
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
            chave for chave, _r, _s in fluxo.ETAPAS) + tuple(
            f"ret_{chave}" for chave, _r in fluxo.RETENCAO) + ("dur", "passo")
        self.tabela_fluxo = ttk.Treeview(pai, columns=colunas, show="headings",
                                         height=11)
        cabecalhos = {"build": ("BUILD", 120), "personagem": ("PERSONAGEM", 150),
                      "dur": ("DUR", 52), "passo": ("PRÓXIMO PASSO", 420)}
        # Revisao de retencao (29/08): voz narrada, luta no video, gancho A/B.
        for chave, rotulo in fluxo.RETENCAO:
            cabecalhos[f"ret_{chave}"] = (rotulo, 50)
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
                 "        VOZ = narração no vídeo · LUTA = round da estreia no fim "
                 "· A/B = gancho alternativo renderizado")
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
            ret = geracao.get("retencao") or {}
            extras = ["✓" if ret.get(chave) else "·" for chave, _r in fluxo.RETENCAO]
            dur = f"{ret['duracao']:.0f}s" if ret.get("duracao") else ""
            self.tabela_fluxo.insert(
                "", "end", iid=geracao["generation_id"], tags=(tag,),
                values=(geracao["generation_id"], geracao["personagem"],
                        *simbolos, *extras, dur, geracao["proximo_passo"]))
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
    # Emoji + rotulo por origem: a primeira coluna responde "o que e isto?"
    # antes de o titulo ser lido. Era a duvida do Adrian em 31/08 — a lista
    # misturava build, estreia e torneio sem dizer qual era qual, e as
    # historias nem apareciam.
    PUB_ORIGENS = {
        "build": ("\U0001f3ae", "build"),
        "estreia": ("\u2694", "estreia"),
        "torneio": ("\U0001f3c6", "torneio"),
        "historia": ("\U0001f4d6", "história"),
    }

    def _pagina_publicar(self, pai):
        """TUDO que esta pronto para ir ao ar, e para onde cada coisa vai.

        Antes esta pagina so mostrava os mp4 do random_builds, e as historias
        tinham um botao proprio em outra pagina — nao dava para ver num lugar
        so o que existe nem escolher o destino. Agora a lista junta as duas
        fontes, cada linha diz se JA foi para o YouTube e para o TikTok, e a
        caixa ONDE POSTAR mostra a conta de destino antes do clique.
        """
        self._titulo(pai, "Publicar — tudo que está pronto, e para onde vai")

        # ---------------------------------------------------------- filtros
        filtros = tk.Frame(pai, bg=BG)
        filtros.pack(fill="x", padx=20)
        tk.Label(filtros, text="Mostrar:", bg=BG, fg=DIM,
                 font=FONT).pack(side="left")
        self.combo_pub_origem = ttk.Combobox(
            filtros, width=16, state="readonly",
            values=("tudo", "\U0001f3ae builds", "\U0001f4d6 histórias",
                    "\u2694 estreias", "\U0001f3c6 torneios"))
        self.combo_pub_origem.set("tudo")
        self.combo_pub_origem.pack(side="left", padx=6)
        self.combo_pub_perfil = ttk.Combobox(
            filtros, width=16, state="readonly",
            values=("todos os formatos", "celular (9:16)", "normal (16:9)"))
        self.combo_pub_perfil.set("celular (9:16)")
        self.combo_pub_perfil.pack(side="left")
        self.var_pub_pendentes = tk.BooleanVar(value=False)
        tk.Checkbutton(filtros, text="só o que ainda não publiquei",
                       variable=self.var_pub_pendentes, bg=BG, fg=TEXT,
                       selectcolor=CARD, activebackground=BG, font=FONT,
                       command=self._atualizar_publicar).pack(side="left",
                                                              padx=(10, 0))
        for combo in (self.combo_pub_origem, self.combo_pub_perfil):
            combo.bind("<<ComboboxSelected>>",
                       lambda e: self._atualizar_publicar())
        self._botao(filtros, "\u21bb  Atualizar",
                    self._atualizar_publicar).pack(side="right")
        self._botao(filtros, "\U0001f4c2  Pasta de exportação",
                    self._abrir_pasta_export).pack(side="right", padx=6)

        corpo = tk.Frame(pai, bg=BG)
        corpo.pack(fill="both", expand=True, padx=20, pady=(8, 0))

        # ------------------------------------------------------------ lista
        esquerda = tk.Frame(corpo, bg=BG)
        esquerda.pack(side="left", fill="both", expand=True)
        self.tabela_pub = ttk.Treeview(
            esquerda, columns=("onde", "titulo", "formato", "yt", "tt"),
            show="headings", height=12)
        for coluna, titulo, largura, ancora in (
                ("onde", "O QUE É", 92, "w"),
                ("titulo", "VÍDEO", 300, "w"),
                ("formato", "FORMATO", 72, "center"),
                ("yt", "YOUTUBE", 88, "center"),
                ("tt", "TIKTOK", 80, "center")):
            self.tabela_pub.heading(coluna, text=titulo)
            self.tabela_pub.column(coluna, width=largura, anchor=ancora,
                                   stretch=coluna == "titulo")
        self.tabela_pub.tag_configure("publicado", foreground=OK)
        self.tabela_pub.tag_configure("pendente", foreground=ORANGE)
        self.tabela_pub.pack(fill="both", expand=True)
        self.tabela_pub.bind("<<TreeviewSelect>>",
                             lambda e: self._mostrar_texto_publicar())
        self.tabela_pub.bind("<Double-1>",
                             lambda e: self._publicar_arquivo("assistir"))
        self.lbl_pub_conta = tk.Label(esquerda, text="", bg=BG, fg=DIM,
                                      font=("Segoe UI", 8), anchor="w")
        self.lbl_pub_conta.pack(fill="x", pady=(3, 0))

        # ------------------------------------------------------- texto
        direita = tk.Frame(corpo, bg=CARD, padx=12, pady=10)
        direita.pack(side="left", fill="both", padx=(10, 0))
        tk.Label(direita, text="TÍTULO", bg=CARD, fg=ACCENT,
                 font=FONT_B).pack(anchor="w")
        self.texto_pub_titulo = tk.Text(direita, height=2, width=40, bg=CARD_HL,
                                        fg=TEXT, insertbackground=TEXT, bd=0,
                                        font=FONT, wrap="word")
        self.texto_pub_titulo.pack(fill="x", pady=(2, 8))
        tk.Label(direita, text="DESCRIÇÃO (com as hashtags)", bg=CARD, fg=ACCENT,
                 font=FONT_B).pack(anchor="w")
        self.texto_pub_desc = tk.Text(direita, height=9, width=40, bg=CARD_HL,
                                      fg=TEXT, insertbackground=TEXT, bd=0,
                                      font=FONT, wrap="word")
        self.texto_pub_desc.pack(fill="both", expand=True, pady=(2, 6))
        linha_texto = tk.Frame(direita, bg=CARD)
        linha_texto.pack(fill="x")
        self._botao(linha_texto, "\U0001f4be  Salvar texto",
                    self._salvar_texto_publicar).pack(side="left")
        self._botao(linha_texto, "\U0001f4cb  Copiar",
                    self._copiar_texto_publicar).pack(side="left", padx=6)
        self.lbl_pub_texto = tk.Label(direita, text="", bg=CARD, fg=DIM,
                                      font=("Segoe UI", 8), wraplength=300,
                                      justify="left")
        self.lbl_pub_texto.pack(anchor="w", pady=(6, 0))

        # ------------------------------------------------- ONDE POSTAR
        destino = tk.Frame(pai, bg=CARD, padx=12, pady=8)
        destino.pack(fill="x", padx=20, pady=(10, 4))
        tk.Label(destino, text="ONDE POSTAR", bg=CARD, fg=ACCENT,
                 font=FONT_B).grid(row=0, column=0, columnspan=6, sticky="w")

        self.var_pub_yt = tk.BooleanVar(value=True)
        tk.Checkbutton(destino, text="YouTube", variable=self.var_pub_yt,
                       bg=CARD, fg=TEXT, selectcolor=CARD_HL,
                       activebackground=CARD, font=FONT_B,
                       command=self._pub_atualizar_botao).grid(
                           row=1, column=0, sticky="w", pady=2)
        tk.Label(destino, text="conta:", bg=CARD, fg=DIM,
                 font=FONT).grid(row=1, column=1, sticky="e", padx=(10, 2))
        self.combo_pub_conta_yt = ttk.Combobox(destino, width=16,
                                               state="readonly")
        self.combo_pub_conta_yt.grid(row=1, column=2, sticky="w")
        self.combo_pub_conta_yt.bind(
            "<<ComboboxSelected>>", lambda e: self._pub_trocar_conta("youtube"))
        tk.Label(destino, text="visibilidade:", bg=CARD, fg=DIM,
                 font=FONT).grid(row=1, column=3, sticky="e", padx=(12, 2))
        self.combo_pub_vis = ttk.Combobox(
            destino, width=10, state="readonly",
            values=("public", "unlisted", "private"))
        self.combo_pub_vis.set(
            (publicar_catalogo.carregar_config().get("youtube") or {})
            .get("visibilidade", "private"))
        self.combo_pub_vis.grid(row=1, column=4, sticky="w")

        self.var_pub_tt = tk.BooleanVar(value=False)
        tk.Checkbutton(destino, text="TikTok", variable=self.var_pub_tt,
                       bg=CARD, fg=TEXT, selectcolor=CARD_HL,
                       activebackground=CARD, font=FONT_B,
                       command=self._pub_atualizar_botao).grid(
                           row=2, column=0, sticky="w", pady=2)
        tk.Label(destino, text="conta:", bg=CARD, fg=DIM,
                 font=FONT).grid(row=2, column=1, sticky="e", padx=(10, 2))
        self.combo_pub_conta_tt = ttk.Combobox(destino, width=16,
                                               state="readonly")
        self.combo_pub_conta_tt.grid(row=2, column=2, sticky="w")
        self.combo_pub_conta_tt.bind(
            "<<ComboboxSelected>>", lambda e: self._pub_trocar_conta("tiktok"))
        tk.Label(destino, text="o TikTok posta de verdade (sem confirmação)",
                 bg=CARD, fg=DIM,
                 font=("Segoe UI", 8)).grid(row=2, column=3, columnspan=2,
                                            sticky="w", padx=(12, 0))

        self.btn_pub_enviar = self._botao_primario(
            destino, "\U0001f680  PUBLICAR", self._publicar_enviar)
        self.btn_pub_enviar.grid(row=1, column=5, rowspan=2, padx=(18, 0),
                                 sticky="nsew")
        destino.columnconfigure(5, weight=1)

        # ------------------------------------- arquivo x configuracao
        rodape = tk.Frame(pai, bg=BG)
        rodape.pack(fill="x", padx=20, pady=(2, 10))
        arquivo = tk.Frame(rodape, bg=BG)
        arquivo.pack(side="left")
        tk.Label(arquivo, text="ARQUIVO", bg=BG, fg=DIM,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        linha_arq = tk.Frame(arquivo, bg=BG)
        linha_arq.pack()
        self._botao(linha_arq, "\u25b6  Assistir",
                    lambda: self._publicar_arquivo("assistir")).pack(side="left")
        self._botao(linha_arq, "\U0001f4c1  Pasta",
                    lambda: self._publicar_arquivo("pasta")).pack(side="left",
                                                                  padx=6)
        self._botao(linha_arq, "\U0001f4e4  Exportar",
                    lambda: self._publicar_arquivo("exportar")).pack(side="left")

        config = tk.Frame(rodape, bg=BG)
        config.pack(side="right")
        tk.Label(config, text="CONFIGURAÇÃO (uma vez só)", bg=BG, fg=DIM,
                 font=("Segoe UI", 8, "bold")).pack(anchor="e")
        linha_cfg = tk.Frame(config, bg=BG)
        linha_cfg.pack()
        # O rotulo carrega o CANAL: autorizar "o YouTube" sem dizer qual
        # conta era metade da confusao — o login ia sempre para o de builds,
        # mesmo com uma historia selecionada.
        self.btn_pub_oauth = self._botao(
            linha_cfg, "\U0001f511  Autorizar YouTube",
            self._pub_autorizar_youtube)
        self.btn_pub_oauth.pack(side="left")
        self.btn_pub_tiktok = self._botao(
            linha_cfg, "\U0001f511  Login TikTok", self._pub_login_tiktok)
        self.btn_pub_tiktok.pack(side="left", padx=6)
        # Desde 01/09 o YouTube tambem sobe por navegador, entao ele precisa
        # do MESMO login manual que o TikTok — e o botao ao lado deixa isso
        # obvio. "Autorizar YouTube" (OAuth) continua ali, mas hoje serve so
        # para LER metricas.
        self.btn_pub_yt_web = self._botao(
            linha_cfg, "\U0001f511  Login YouTube Studio",
            self._pub_login_youtube_web)
        self.btn_pub_yt_web.pack(side="left", padx=(0, 6))
        self._botao(linha_cfg, "\U0001f3af  Canais do YouTube",
                    self._pub_canais_youtube).pack(side="left", padx=(0, 6))
        self._botao(linha_cfg, "\U0001f9f9  Reparar perfil",
                    self._pub_reparar_perfil).pack(side="left")
        self._botao(linha_cfg, "♻  Recomeçar perfil",
                    self._pub_recomecar_perfil).pack(side="left", padx=(6, 0))
        self._botao(linha_cfg, "\U0001f4ca  Métricas",
                    lambda: self._metricas(False)).pack(side="left", padx=(6, 0))

        self._pub_itens = {}
        self._pub_lendo = False

    # ------------------------------------------------------- dados da lista
    def _pub_publicados(self) -> dict:
        """{(video_id, plataforma): linha} dos DOIS registros.

        E o que faz a lista dizer "ja subiu" sem abrir o navegador: cada
        upload deixa uma linha em `outputs/_publicar/publicados.jsonl`.
        """
        import json as _json
        mapa = {}
        for caminho in (RANDOM_BUILDS / "outputs" / "_publicar" / "publicados.jsonl",
                        HISTORIAS / "outputs" / "_publicar" / "publicados.jsonl"):
            try:
                bruto = caminho.read_text(encoding="utf-8")
            except OSError:
                continue
            for linha in bruto.splitlines():
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    dado = _json.loads(linha)
                except ValueError:
                    continue
                chave = (dado.get("video_id"),
                         dado.get("plataforma") or "youtube")
                if dado.get("url"):
                    mapa[chave] = dado
        return mapa

    def _pub_historias(self) -> list:
        """Os videos de historia, lidos por um python DE DENTRO daquele projeto.

        Importar aqui nao da: os dois projetos tem um pacote chamado `src`.
        """
        import json as _json
        import subprocess as sp
        try:
            saida = sp.run(
                [PY, "-X", "utf8", "-c",
                 "import sys, json; sys.path.insert(0, '.');"
                 "from contos.publicar import catalogo;"
                 "print(json.dumps(catalogo.resumo()))"],
                cwd=str(HISTORIAS), capture_output=True, text=True,
                encoding="utf-8", timeout=90, creationflags=NO_WINDOW)
            return _json.loads((saida.stdout or "[]").strip().splitlines()[-1])
        except Exception:
            return []

    def _atualizar_publicar(self):
        """Le as duas fontes FORA da thread da UI (uma delas e subprocesso)."""
        if not hasattr(self, "tabela_pub") or getattr(self, "_pub_lendo", False):
            return
        self._pub_lendo = True
        self._pub_fila = getattr(self, "_pub_fila", queue.Queue())

        def trabalho():
            try:
                builds = [{"id": v.id, "fonte": "builds", "origem": v.origem,
                           "titulo": v.titulo, "perfil": v.perfil,
                           "bytes": v.bytes, "quando": v.quando,
                           "caminho": str(v.caminho),
                           "descricao": v.descricao_completa,
                           "pendencias": list(v.pendencias or []),
                           "parte": 1, "partes": 1}
                          for v in publicar_catalogo.listar()]
                historias = [{**h, "fonte": "historias", "pendencias": []}
                             for h in self._pub_historias()]
                dados = {"itens": builds + historias,
                         "publicados": self._pub_publicados()}
            except Exception as erro:
                dados = {"erro": f"{type(erro).__name__}: {erro}"}
            self._pub_fila.put(dados)

        threading.Thread(target=trabalho, daemon=True).start()
        self.after(200, self._colher_publicar)

    def _colher_publicar(self):
        try:
            dados = self._pub_fila.get_nowait()
        except queue.Empty:
            if self._pub_lendo:
                self.after(200, self._colher_publicar)
            return
        self._pub_lendo = False
        if dados.get("erro"):
            self._log(f"[publicar] não li a lista: {dados['erro']}", "erro")
            return
        self._pub_pub = dados["publicados"]
        self._pub_render(dados["itens"])

    def _pub_render(self, itens):
        import datetime
        alvo = self.combo_pub_origem.get()
        formato = self.combo_pub_perfil.get()
        so_pendentes = self.var_pub_pendentes.get()

        def cabe(item):
            origem = item.get("origem") or ""
            if alvo != "tudo":
                if "builds" in alvo and origem != "build":
                    return False
                if "histórias" in alvo and origem != "historia":
                    return False
                if "estreias" in alvo and origem != "estreia":
                    return False
                if "torneios" in alvo and origem != "torneio":
                    return False
            if not formato.startswith("todos"):
                if item.get("perfil") != formato.split()[0]:
                    return False
            if so_pendentes and (self._pub_estado(item, "youtube")
                                 or self._pub_estado(item, "tiktok")):
                return False
            return True

        selecionado = self.tabela_pub.selection()
        visiveis = [i for i in itens if cabe(i)]
        visiveis.sort(key=lambda i: (i.get("quando") or 0), reverse=True)
        self._pub_itens = {i["id"]: i for i in visiveis}
        self.tabela_pub.delete(*self.tabela_pub.get_children())
        for item in visiveis:
            emoji, rotulo = self.PUB_ORIGENS.get(item.get("origem"),
                                                 ("\u2022", item.get("origem", "?")))
            titulo = item["titulo"]
            if item.get("partes", 1) > 1:
                titulo = f"{titulo}  ·  parte {item['parte']}/{item['partes']}"
            if item.get("pendencias"):
                titulo = "\u26a0 " + titulo
            yt = self._pub_marca(item, "youtube")
            tt = self._pub_marca(item, "tiktok")
            tags = ("publicado",) if (yt != "\u2014" and tt != "\u2014") else (
                ("pendente",) if item.get("pendencias") else ())
            self.tabela_pub.insert(
                "", "end", iid=item["id"],
                values=(f"{emoji} {rotulo}", titulo,
                        "9:16" if item.get("perfil") == "celular" else "16:9",
                        yt, tt), tags=tags)
        if selecionado and self.tabela_pub.exists(selecionado[0]):
            self.tabela_pub.selection_set(selecionado)
        elif visiveis:
            self.tabela_pub.selection_set(visiveis[0]["id"])
        else:
            self._mostrar_texto_publicar()

    def _pub_estado(self, item, plataforma):
        return getattr(self, "_pub_pub", {}).get((item["id"], plataforma))

    def _pub_marca(self, item, plataforma) -> str:
        linha = self._pub_estado(item, plataforma)
        if not linha:
            return "\u2014"
        quando = str(linha.get("quando") or "")[:10]
        try:
            dia = f"{quando[8:10]}/{quando[5:7]}"
        except Exception:
            dia = "sim"
        return f"\u2713 {dia}"

    # ------------------------------------------------------------ selecao
    def _publicar_selecionado(self):
        selecionado = self.tabela_pub.selection()
        if not selecionado:
            messagebox.showwarning("Publicar", "Selecione um vídeo na lista.")
            return None
        return getattr(self, "_pub_itens", {}).get(selecionado[0])

    def _pub_canal(self, item) -> str:
        return "historias" if item.get("fonte") == "historias" else "builds"

    def _mostrar_texto_publicar(self):
        item = getattr(self, "_pub_itens", {}).get(
            (self.tabela_pub.selection() or [None])[0])
        self.texto_pub_titulo.delete("1.0", "end")
        self.texto_pub_desc.delete("1.0", "end")
        if item is None:
            self.lbl_pub_texto.configure(text="")
            self.lbl_pub_conta.configure(text="")
            self._pub_atualizar_botao()
            return
        for pendencia in item.get("pendencias") or []:
            self._log(f"[publicar] {item['id']}: {pendencia}", "erro")
        self.texto_pub_titulo.insert("1.0", item["titulo"])
        self.texto_pub_desc.insert("1.0", item.get("descricao") or "")
        de_historia = item.get("fonte") == "historias"
        estado = "disabled" if de_historia else "normal"
        self.texto_pub_titulo.configure(state=estado)
        self.texto_pub_desc.configure(state=estado)
        self.lbl_pub_texto.configure(
            text=("o texto da história vem do roteiro — para mudar, edite o "
                  "roteiro e gere o vídeo de novo.\n\nAqui você publica UMA "
                  "parte. Para subir a série inteira já agendada de 24 em "
                  "24 h, use 🚀 Publicar série na página Histórias."
                  if de_historia else "o texto salvo vale nos dois envios"))
        self._pub_contas(item)
        self._pub_atualizar_botao()

    def _pub_contas(self, item):
        """Mostra (e deixa trocar) a conta de destino DAQUELE canal."""
        canal = self._pub_canal(item)
        partes = []
        # O servico do YouTube depende do MODO: no navegador o que vale e o
        # perfil (`youtube_web`), nao o token da API.
        servico_yt = self._servico_youtube()
        for servico, combo in ((servico_yt, self.combo_pub_conta_yt),
                               ("tiktok", self.combo_pub_conta_tt)):
            contas = contas_reg.contas(servico)
            combo.configure(values=contas)
            destino = contas_reg.destino(servico, canal)
            combo.set(destino["conta"])
            marca = "\u2713" if destino["tem_login"] else "\u2717 sem login"
            proprio = "" if destino["explicita"] else " (herdada)"
            # O NOME DA CONTA nao diz para onde o video vai. O canal, sim —
            # e e o canal que nao tem desfazer.
            quem = destino.get("identidade") or ""
            onde = f" \u2192 {quem}" if quem else " \u2192 canal ?"
            rotulo = "youtube" if servico.startswith("youtube") else servico
            partes.append(
                f"{rotulo}: {destino['conta']}{proprio}{onde} {marca}")
        aviso = ""
        repetidos = contas_reg.destinos_repetidos(servico_yt)
        if repetidos:
            juntos = "; ".join(" e ".join(c) for c in repetidos.values())
            aviso = f"   \u26a0 {juntos} publicam NO MESMO canal"
        self.lbl_pub_conta.configure(
            text=f"canal {canal}  ·  " + "   ·   ".join(partes)
                 + aviso)
        if hasattr(self, "btn_pub_oauth"):
            self.btn_pub_oauth.configure(
                text=f"\U0001f511  Autorizar YouTube ({canal})")
            self.btn_pub_tiktok.configure(
                text=f"\U0001f511  Login TikTok ({canal})")

    def _pub_trocar_conta(self, servico: str):
        item = self._publicar_selecionado()
        if item is None:
            return
        if servico == "youtube":
            servico = self._servico_youtube()
        combo = (self.combo_pub_conta_tt if servico == "tiktok"
                 else self.combo_pub_conta_yt)
        canal = self._pub_canal(item)
        contas_reg.escolher(servico, canal, combo.get())
        self._log(f"[contas] {servico} do canal {canal}: {combo.get()}", "fim")
        self._pub_contas(item)

    def _pub_atualizar_botao(self):
        alvos = []
        if getattr(self, "var_pub_yt", None) and self.var_pub_yt.get():
            alvos.append("YOUTUBE")
        if getattr(self, "var_pub_tt", None) and self.var_pub_tt.get():
            alvos.append("TIKTOK")
        texto = ("\U0001f680  PUBLICAR NO " + " + ".join(alvos) if alvos
                 else "escolha YouTube e/ou TikTok")
        self.btn_pub_enviar.configure(text=texto,
                                      state="normal" if alvos else "disabled")

    # ------------------------------------------------- configuracao do canal
    def _pub_canal_atual(self) -> str:
        item = getattr(self, "_pub_itens", {}).get(
            (self.tabela_pub.selection() or [None])[0])
        return self._pub_canal(item) if item else "builds"

    def _pub_autorizar_youtube(self):
        """Autoriza a conta DAQUELE canal, no arquivo DAQUELE canal.

        Sem o `--out`, o token do canal de historias sobrescreveria o de
        builds — os dois moram em arquivos diferentes justamente para nao
        publicar no canal errado.
        """
        canal = self._pub_canal_atual()
        cliente, segredo = self._credenciais_youtube()
        if not (cliente and segredo):
            messagebox.showinfo(
                "Autorizar YouTube",
                "Não achei o client-id/client-secret do YouTube.\n\n"
                "Preencha os dois na página Live / YouTube (card CREDENCIAIS "
                "DO YOUTUBE) e clique aqui de novo.")
            self._mostrar("live")
            return
        conta = contas_reg.ativa("youtube", canal)
        destino = contas_reg.credencial_youtube(canal)
        messagebox.showinfo(
            "Autorizar YouTube",
            f"Vou abrir o navegador no login do Google.\n\n"
            f"Canal: {canal}   ·   conta: {conta}\n\n"
            "IMPORTANTE: entre com a conta do Google DESTE canal — é ela que "
            "vai receber os vídeos. Marque as permissões de enviar vídeo e de "
            "estatísticas.")
        self._rodar([PY, "-m", "neural_fights.tools.youtube_oauth",
                     "--client-id", cliente, "--client-secret", segredo,
                     "--com-upload", "--com-analytics",
                     "--out", str(destino)],
                    rotulo=f"autorizar YouTube {canal}/{conta} "
                           "(credenciais ocultas)")

    def _pub_reparar_perfil(self):
        """Limpa o cache do perfil de Chrome daquele canal (mantém o login).

        O sintoma que isto resolve não parece cache: a página do site abre
        BRANCA, só o esqueleto cinza, como se estivesse bloqueada. Medido em
        31/08/2026 — o perfil do TikTok tinha 1,1 GB acumulados.
        """
        from builds.identity.browser import limpar_cache
        canal = self._pub_canal_atual()
        achou = False
        for servico in ("tiktok", "picasso", "digen"):
            try:
                perfil = contas_reg.perfil(servico, canal)
            except Exception:
                continue
            pastas, mb = limpar_cache(perfil)
            if pastas:
                achou = True
                self._log(f"[perfil] {servico}/{canal}: {len(pastas)} pasta(s) "
                          f"de cache, {mb} MB liberados (login preservado).",
                          "fim")
        if not achou:
            self._log("[perfil] nada de cache para limpar (ou o Chrome está "
                      "aberto segurando os arquivos — feche e tente de novo).")
        self._log("[perfil] se a página do site AINDA abrir em branco, o "
                  "estrago está no storage do perfil: use ♻ Recomeçar perfil "
                  "(aí o login precisa ser refeito).")

    def _pub_recomecar_perfil(self):
        """Guarda o perfil quebrado de lado e começa um novo.

        Isto CUSTA o login — por isso pergunta antes, ao contrário do resto
        da página. A pasta antiga não é apagada: vira `.quebrado-<data>`.
        """
        from builds.identity.browser import resetar_perfil
        canal = self._pub_canal_atual()
        conta = contas_reg.ativa("tiktok", canal)
        if not messagebox.askyesno(
                "Recomeçar perfil",
                f"Começar um perfil de Chrome NOVO para o TikTok do canal "
                f"'{canal}' (conta {conta})?\n\n"
                "Use quando a página do TikTok abre em branco mesmo depois de "
                "limpar o cache.\n\n"
                "O login DESSA conta terá que ser refeito. A pasta antiga não "
                "é apagada — fica ao lado como '.quebrado-<data>'."):
            return
        perfil = contas_reg.perfil("tiktok", canal)
        guardado = resetar_perfil(perfil)
        if guardado is None:
            self._log("[perfil] não havia perfil para recomeçar.", "erro")
            return
        self._log(f"[perfil] perfil novo em {perfil}; o antigo ficou em "
                  f"{guardado.name}. Agora clique em 🔑 Login TikTok.", "fim")

    def _servico_youtube(self) -> str:
        """Qual login vale HOJE: o perfil do navegador ou o OAuth da API.

        Depende do modo de publicacao. Cobrar o OAuth no modo navegador
        bloquearia justamente o caminho que nao precisa dele.
        """
        try:
            return ("youtube" if youtube_reg.modo() == "api"
                    else "youtube_web")
        except Exception:
            return "youtube_web"

    def _pub_canais_youtube(self):
        """Lista os canais que o login enxerga e cadastra cada um.

        Depois disso o combo de conta vira o seletor de CANAL: os canais
        aparecem la pelo nome de verdade, e escolher um muda para onde este
        canal do projeto publica.
        """
        self._log("[canais] abrindo o YouTube para ver os canais desta "
                  "sessao — leva uns 30 s.")
        self._rodar([PY, "-m", "builds.publicar.youtube_web", "--canais"],
                    cwd=RANDOM_BUILDS, rotulo="canais do YouTube",
                    ao_terminar=self._pub_recarregar_contas)

    def _pub_recarregar_contas(self):
        """Redesenha a linha de contas depois que a lista mudou."""
        item = self._publicar_selecionado()
        if item is not None:
            self._pub_contas(item)

    def _pub_login_youtube_web(self):
        canal = self._pub_canal_atual()
        self._rodar([PY, "-m", "builds.publicar.youtube_web", "--login",
                     "--canal", canal],
                    cwd=RANDOM_BUILDS,
                    rotulo=f"login no YouTube Studio ({canal})")

    def _pub_login_tiktok(self):
        canal = self._pub_canal_atual()
        self._rodar([PY, "-m", "builds.publicar.tiktok", "--login",
                     "--canal", canal],
                    cwd=RANDOM_BUILDS,
                    rotulo=f"login no TikTok ({canal})")

    # ------------------------------------------------------------- acoes
    def _publicar_arquivo(self, acao: str):
        item = self._publicar_selecionado()
        if item is None:
            return
        caminho = Path(item["caminho"])
        if acao == "assistir":
            os.startfile(caminho)
        elif acao == "pasta":
            os.startfile(caminho.parent)
        elif acao == "exportar":
            if item.get("fonte") == "historias":
                self._historias_cli(["publicar", item["id"], "--exportar"],
                                    f"exportar {item['titulo'][:30]}")
                return
            if self._salvar_texto_publicar(silencioso=True) is None:
                return
            destino = publicar_catalogo.exportar(
                publicar_catalogo.por_id(item["id"]))
            self._log(f"[exportar] {destino}\n", "fim")
            os.startfile(destino.parent)

    def _publicar_enviar(self):
        """UM clique, com o destino que esta na tela."""
        item = self._publicar_selecionado()
        if item is None:
            return
        quer_yt, quer_tt = self.var_pub_yt.get(), self.var_pub_tt.get()
        if not (quer_yt or quer_tt):
            return
        canal = self._pub_canal(item)
        for servico, quer in (("youtube", quer_yt), ("tiktok", quer_tt)):
            if quer and not contas_reg.tem_login(servico, canal):
                self._log(f"[publicar] {servico} do canal {canal} sem login — "
                          "use CONFIGURAÇÃO aqui embaixo.", "erro")
                return
        ja = [p for p in ("youtube", "tiktok")
              if self._pub_estado(item, p) and
              (quer_yt if p == "youtube" else quer_tt)]
        if ja:
            self._log(f"[publicar] atenção: já subiu em {', '.join(ja)} — "
                      "vai virar um segundo vídeo lá.", "erro")

        if item.get("fonte") == "historias":
            args = ["publicar", item["id"]]
            if quer_yt:
                args += ["--youtube", "--visibilidade", self.combo_pub_vis.get()]
            if quer_tt:
                args.append("--tiktok")
            self._historias_cli(args, f"publicar {item['titulo'][:34]}")
        else:
            if self._salvar_texto_publicar(silencioso=True) is None:
                return
            args = [PY, "main.py", "publicar", item["id"]]
            if quer_yt:
                args += ["--youtube", "--visibilidade", self.combo_pub_vis.get()]
            if quer_tt:
                args += ["--tiktok", "--postar"]
            self._rodar(args, cwd=RANDOM_BUILDS,
                        rotulo=f"publicar {item['titulo'][:34]}")
        if quer_yt and self.combo_pub_vis.get() == "private":
            self._log("[publicar] visibilidade 'private': o vídeo sobe mas NÃO "
                      "fica visível.", "erro")
        self.after(4000, self._atualizar_publicar)

    # ------------------------------------------------------------- texto
    def _texto_editado(self) -> tuple[str, str]:
        return (self.texto_pub_titulo.get("1.0", "end").strip(),
                self.texto_pub_desc.get("1.0", "end").strip())

    def _salvar_texto_publicar(self, silencioso: bool = False):
        """Grava o texto da tela como o texto DAQUELE vídeo.

        Salvar antes de enviar é o que faz o envio usar o que está na tela —
        o subprocesso lê do catálogo, não da janela.
        """
        item = self._publicar_selecionado()
        if item is None:
            return None
        if item.get("fonte") == "historias":
            if not silencioso:
                messagebox.showinfo(
                    "Texto da história",
                    "O título e a descrição de uma história vêm do roteiro.\n\n"
                    "Para mudar, edite o roteiro e gere o vídeo de novo.")
            return item["id"]
        titulo, descricao = self._texto_editado()
        if not titulo:
            messagebox.showwarning("Publicar", "O título não pode ficar vazio.")
            return None
        publicar_catalogo.salvar_texto(item["id"], titulo, descricao)
        if not silencioso:
            self._log(f"[texto] salvo para {item['id']}\n", "fim")
            self._atualizar_publicar()
        return item["id"]

    def _copiar_texto_publicar(self):
        titulo, descricao = self._texto_editado()
        self.clipboard_clear()
        self.clipboard_append(f"{titulo}\n\n{descricao}")
        self._log("[texto] copiado para a área de transferência\n", "fim")

    def _abrir_pasta_export(self):
        pasta = publicar_catalogo.pasta_export()
        pasta.mkdir(parents=True, exist_ok=True)
        os.startfile(pasta)

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
            from builds.publicar.youtube import carregar_credenciais
            salvas = carregar_credenciais()
        except Exception:
            salvas = None
        if salvas is None:
            return atual
        return salvas.client_id, salvas.client_secret

    def _oauth_upload(self, com_analytics: bool = False):
        """Re-autoriza o YouTube pedindo TAMBÉM o escopo de upload (e, com
        `com_analytics`, o do YouTube Analytics — a curva de retenção)."""
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
        extras = ["--com-analytics"] if com_analytics else []
        self._rodar([PY, "-m", "neural_fights.tools.youtube_oauth",
                     "--client-id", cliente, "--client-secret", segredo,
                     "--com-upload", *extras],
                    rotulo="youtube_oauth --com-upload"
                           + (" --com-analytics" if com_analytics else "")
                           + " (credenciais ocultas)")

    def _tiktok_login(self):
        self._rodar([PY, "-m", "builds.publicar.tiktok", "--login"],
                    cwd=RANDOM_BUILDS, rotulo="login no TikTok")

    def _tiktok_sondar(self):
        self._rodar([PY, "-m", "builds.publicar.tiktok", "--sondar"],
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

        self._card_retencao(pai)

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
        cols = ("geracao", "nota", "duracao", "formatos", "retencao")
        self.tabela_videos = ttk.Treeview(corpo, columns=cols, show="headings",
                                          selectmode="browse")
        for coluna, texto, largura in (("geracao", "Geração", 170),
                                       ("nota", "Nota final", 210),
                                       ("duracao", "Duração", 90),
                                       ("formatos", "Formatos prontos", 200),
                                       ("retencao", "Voz · luta · A/B", 150)):
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
        from builds.generation import escolhas as mod_escolhas

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

    # ------------------------------------------------- retencao (29/08/2026)
    _VOZES = ("pt-BR-AntonioNeural", "pt-BR-FranciscaNeural",
              "pt-BR-ThalitaMultilingualNeural")

    def _card_retencao(self, pai):
        """Os ajustes da revisao de retencao, editaveis sem abrir JSON.

        Cada caixa e uma chave de config/editing.json ou config/render.json;
        `Salvar ajustes` grava os dois arquivos preservando o formato. O que
        muda de verdade o video e o proximo render — por isso o card fica ao
        lado de GERAR e RE-RENDERIZAR, nao numa tela de configuracao.
        """
        card = self._card(pai, "RETENÇÃO — som, gancho, luta no fim, métricas")
        card.pack(fill="x", padx=20, pady=(8, 0))
        self.lbl_retencao = tk.Label(card, text="lendo...", bg=CARD, fg=DIM,
                                     font=FONT, justify="left", anchor="w")
        self.lbl_retencao.pack(anchor="w")

        linha1 = tk.Frame(card, bg=CARD)
        linha1.pack(anchor="w", pady=(6, 0))
        self.var_ret: dict[str, tk.BooleanVar] = {}
        for chave, rotulo in (("gancho_payoff", "Gancho com a imagem do personagem"),
                              ("gancho_ab", "Gancho B (A/B)"),
                              ("revelacao_cedo", "Personagem cedo"),
                              ("luta", "Luta no fim")):
            caixa, var = self._check(linha1, rotulo)
            caixa.pack(side="left", padx=(0, 8))
            self.var_ret[chave] = var
        linha2 = tk.Frame(card, bg=CARD)
        linha2.pack(anchor="w", pady=(2, 0))
        for chave, rotulo in (("voz", "Voz narrada"),
                              ("trilha", "Trilha sintetizada"),
                              ("ducking", "Abaixar música sob a fala"),
                              ("payoff_video", "Vídeo do payoff (Digen)")):
            caixa, var = self._check(linha2, rotulo)
            caixa.pack(side="left", padx=(0, 8))
            self.var_ret[chave] = var
        tk.Label(linha2, text="voz:", bg=CARD, fg=DIM, font=FONT).pack(side="left")
        self.combo_voz = ttk.Combobox(linha2, width=30, state="readonly",
                                      values=self._VOZES + ("sapi (voz do Windows)",))
        self.combo_voz.pack(side="left", padx=4)

        linha3 = tk.Frame(card, bg=CARD)
        linha3.pack(anchor="w", pady=(8, 2))
        self._botao_primario(linha3, "💾  Salvar ajustes",
                             self._salvar_ajustes_retencao).pack(side="left")
        self._botao(linha3, "🎵  Gerar trilha", self._gerar_trilha).pack(side="left", padx=8)
        self._botao(linha3, "🔈  Testar voz", self._testar_voz).pack(side="left")
        self._botao(linha3, "📊  Atualizar métricas",
                    lambda: self._metricas(True)).pack(side="left", padx=8)
        self._botao(linha3, "📈  Ver métricas",
                    lambda: self._metricas(False)).pack(side="left")
        self._dica(linha3, "As métricas vêm da API do YouTube; a curva de retenção "
                           "exige 'Autorizar analytics' na página Publicar")
        self._carregar_ajustes_retencao()

    @staticmethod
    def _ler_config_rb(nome: str) -> tuple[dict, bool]:
        import json
        bruto = (RANDOM_BUILDS / "config" / nome).read_bytes()
        return json.loads(bruto.decode("utf-8-sig")), b"\r\n" in bruto

    @staticmethod
    def _gravar_config_rb(nome: str, dados: dict, crlf: bool) -> None:
        import json
        texto = json.dumps(dados, ensure_ascii=False, indent=4) + "\n"
        if crlf:
            texto = texto.replace("\n", "\r\n")
        (RANDOM_BUILDS / "config" / nome).write_bytes(texto.encode("utf-8"))

    def _carregar_ajustes_retencao(self):
        try:
            edicao, _ = self._ler_config_rb("editing.json")
            render, _ = self._ler_config_rb("render.json")
            identidade, _ = self._ler_config_rb("identity.json")
        except (OSError, ValueError) as erro:
            self.lbl_retencao.configure(text=f"não li a config: {erro}", fg=RED)
            return
        self.var_ret["payoff_video"].set(bool(identidade.get("payoff_video", True)))
        gancho = edicao.get("gancho") or {}
        audio = render.get("audio") or {}
        voz = audio.get("voz") or {}
        self.var_ret["gancho_payoff"].set(bool(gancho.get("payoff", True)))
        self.var_ret["gancho_ab"].set(bool(gancho.get("ab", True)))
        self.var_ret["revelacao_cedo"].set(bool(edicao.get("revelacao_cedo", True)))
        self.var_ret["luta"].set(bool((edicao.get("luta_no_build") or {}).get("ativa", True)))
        self.var_ret["voz"].set(bool(voz.get("ativa", True)))
        self.var_ret["trilha"].set(bool(audio.get("trilha_procedural", True)))
        self.var_ret["ducking"].set(bool(audio.get("ducking", True)))
        if voz.get("motor") == "sapi":
            self.combo_voz.set("sapi (voz do Windows)")
        else:
            self.combo_voz.set(voz.get("voz") or self._VOZES[0])

        musicas = [p.name for p in (RANDOM_BUILDS / "assets" / "music").glob("*")
                   if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".m4a", ".flac")]
        cache = RANDOM_BUILDS / "outputs" / "_voz_cache"
        falas = len(list(cache.glob("*"))) if cache.is_dir() else 0
        payoff = ("vídeo (Digen)" if identidade.get("payoff_video", True)
                  else "imagem personagem+arma (Digen desligado)")
        self.lbl_retencao.configure(
            fg=DIM,
            text=(f"payoff: {payoff}   ·   "
                  f"trilha: {', '.join(musicas) if musicas else 'nenhuma (clique Gerar trilha)'}"
                  f"   ·   voz: {voz.get('motor', 'edge')} / {voz.get('voz', '')}"
                  f" ({falas} fala(s) em cache)   ·   loudness alvo {audio.get('loudnorm', -14)} LUFS"))

    def _salvar_ajustes_retencao(self):
        try:
            edicao, crlf_e = self._ler_config_rb("editing.json")
            render, crlf_r = self._ler_config_rb("render.json")
            edicao.setdefault("gancho", {})["payoff"] = self.var_ret["gancho_payoff"].get()
            edicao["gancho"]["ab"] = self.var_ret["gancho_ab"].get()
            edicao["revelacao_cedo"] = self.var_ret["revelacao_cedo"].get()
            edicao.setdefault("luta_no_build", {})["ativa"] = self.var_ret["luta"].get()
            audio = render.setdefault("audio", {})
            voz = audio.setdefault("voz", {})
            voz["ativa"] = self.var_ret["voz"].get()
            escolha = self.combo_voz.get()
            if escolha.startswith("sapi"):
                voz["motor"] = "sapi"
            else:
                voz["motor"] = "edge"
                voz["voz"] = escolha
            audio["trilha_procedural"] = self.var_ret["trilha"].get()
            audio["ducking"] = self.var_ret["ducking"].get()
            identidade, crlf_i = self._ler_config_rb("identity.json")
            identidade["payoff_video"] = self.var_ret["payoff_video"].get()
            self._gravar_config_rb("editing.json", edicao, crlf_e)
            self._gravar_config_rb("render.json", render, crlf_r)
            self._gravar_config_rb("identity.json", identidade, crlf_i)
        except (OSError, ValueError) as erro:
            messagebox.showerror("Retenção", f"não consegui salvar: {erro}")
            return
        self._log("[retenção] ajustes salvos em config/editing.json, render.json e "
                  "identity.json — valem a partir do próximo render; o worker de "
                  "identidade precisa ser reiniciado para ver o payoff ligado/desligado.",
                  "fim")
        self._carregar_ajustes_retencao()

    def _gerar_trilha(self):
        self._rodar([PY, "-u", "-X", "utf8", "main.py", "trilha"], RANDOM_BUILDS,
                    rotulo="gerar trilha sintetizada")
        self.after(4000, self._carregar_ajustes_retencao)

    def _testar_voz(self):
        """Sintetiza uma fala com a voz configurada e toca no player padrão."""
        def tarefa():
            try:
                from builds.content import voz as voz_mod
                render, _ = self._ler_config_rb("render.json")
                cfg = voz_mod.config((render.get("audio") or {}).get("voz"))
                caminho = voz_mod.sintetizar(
                    "Vamos criar um personagem completamente aleatório. Classe? "
                    "Berserker. Agora sim.", cfg,
                    log=lambda t: self._fila.put(("linha", t)))
                os.startfile(str(caminho))
                self._fila.put(("fim", f"voz ok: {cfg['motor']} ({caminho.name})", 0))
            except Exception as erro:
                self._fila.put(("fim", f"teste de voz falhou: {erro}", 1))
        self._log(">>> testar voz", "cmd")
        threading.Thread(target=tarefa, daemon=True).start()

    def _metricas(self, atualizar: bool):
        args = [PY, "-u", "-X", "utf8", "main.py", "metricas"]
        if atualizar:
            args.append("--atualizar")
        self._rodar(args, RANDOM_BUILDS,
                    rotulo="métricas" + (" --atualizar" if atualizar else ""))

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
            ret = fluxo.retencao_de(pasta)
            marcas = " · ".join(
                ("voz" if ret["voz"] else "sem voz",
                 "luta" if ret["luta"] else "sem luta",
                 "A/B" if ret["gancho_b"] else "só A"))
            self.tabela_videos.insert(
                "", "end", iid=nome,
                values=(nome, nota, duracao,
                        " + ".join(formatos) if formatos else "(sem video)",
                        marcas if formatos else ""))
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
        # Um worker por vez: subir outro so cria processo ocioso (a fila tem
        # trava de instancia unica) e confunde quem esta de fato trabalhando.
        try:
            import sys as _sys
            if str(RANDOM_BUILDS) not in _sys.path:
                _sys.path.insert(0, str(RANDOM_BUILDS))
            from builds.identity import queue as identity_queue
            if identity_queue.ha_worker():
                self._log("[identity] já existe um worker de pé — use "
                          "'Parar processos' antes de subir outro.", "erro")
                messagebox.showinfo(
                    "Processar fila",
                    "Já existe um worker de identidade rodando.\n\n"
                    "Ele continua drenando a fila sozinho. Para reiniciá-lo "
                    "(por exemplo, depois de mudar o código), clique em "
                    "'Parar processos' e depois aqui de novo.")
                return
        except Exception as erro:      # a checagem nunca impede o worker
            self._log(f"[identity] não consegui checar worker existente: {erro}")
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

    # -------------------------------------------------------- pagina: vila
    # A fabrica de conteudo como um jogo: cada bot e um "criador" que anda da
    # casa ate a fabrica quando aquela etapa esta trabalhando de verdade. O
    # dado vem do diario de atividade (src/atividade.py), que TODAS as etapas
    # das duas pipelines alimentam — o que aparece aqui aconteceu mesmo.
    VILA_PREDIOS = {
        "chatgpt": (90, 70, "#10a37f"),
        "gemini": (240, 52, "#4e8cf7"),
        "picasso": (420, 60, "#c05be3"),
        "digen": (600, 52, "#e35b8f"),
        "arena": (760, 90, "#d9483b"),
        "estudio": (150, 210, "#e0a63b"),
        "publicacao": (700, 215, "#3ba55d"),
    }
    VILA_CASA = (430, 250)

    def _pagina_vila(self, pai):
        self._titulo(pai, "Vila — os bots trabalhando nas fábricas, ao vivo")

        topo = tk.Frame(pai, bg=BG)
        topo.pack(fill="x", padx=20)
        self.lbl_vila_placar = tk.Label(topo, text="…", bg=BG, fg=TEXT,
                                        font=FONT_B)
        self.lbl_vila_placar.pack(side="left")
        self._botao(topo, "↻", self._vila_dados).pack(side="right")
        self._botao(topo, "➕", lambda: self._vila_zoom(1)).pack(
            side="right", padx=(0, 6))
        self._botao(topo, "➖", lambda: self._vila_zoom(-1)).pack(side="right")
        self._botao(topo, "🎨 Oficina", self._vila_oficina).pack(
            side="right", padx=(0, 10))
        self._botao(topo, "🤖 Bot do celular", self._vila_bot).pack(
            side="right", padx=(0, 6))

        self.canvas_vila = tk.Canvas(pai, width=880, height=330,
                                     bg="#17251a", highlightthickness=0)
        self.canvas_vila.pack(padx=20, pady=(8, 4))

        rodape = tk.Frame(pai, bg=BG)
        rodape.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        cab = tk.Frame(rodape, bg=BG)
        cab.pack(fill="x")
        self.lbl_vila_filtro = tk.Label(cab, text="DIÁRIO  (clique numa fábrica "
                                        "para filtrar)", bg=BG, fg=DIM, font=FONT_B)
        self.lbl_vila_filtro.pack(side="left")
        self._botao(cab, "todas", self._vila_sem_filtro).pack(side="right")
        self.texto_vila = tk.Text(rodape, height=7, bg="#0e0c18", fg=TEXT,
                                  font=FONT_MONO, bd=0, state="disabled",
                                  wrap="word")
        self.texto_vila.pack(fill="both", expand=True, pady=(4, 0))
        self.texto_vila.tag_configure("erro", foreground=RED)
        self.texto_vila.tag_configure("ok", foreground=OK)
        self.texto_vila.tag_configure("inicio", foreground=ORANGE)

        # PARALELISMO: duas coisas so rodam juntas se usarem CONTAS
        # diferentes — a trava e por conta, nao por tarefa. Sem esta tabela,
        # descobrir que dois canais compartilham a mesma conta do PicassoIA
        # exigia ler codigo; o unico sintoma era um "em uso" no meio de uma
        # geracao, horas depois.
        paralelo = tk.Frame(pai, bg=BG)
        paralelo.pack(fill="x", padx=20, pady=(6, 0))
        cabeca = tk.Frame(paralelo, bg=BG)
        cabeca.pack(fill="x")
        tk.Label(cabeca, text="PARALELISMO  (uma conta = uma fila)", bg=BG,
                 fg=DIM, font=("Segoe UI", 8, "bold")).pack(side="left")
        self.lbl_paralelo = tk.Label(cabeca, text="", bg=BG, fg=DIM,
                                     font=("Segoe UI", 8))
        self.lbl_paralelo.pack(side="right")
        self.tabela_paralelo = ttk.Treeview(
            paralelo, columns=("conta", "servico", "canais", "estado"),
            show="headings", height=4)
        for coluna, titulo, largura in (("conta", "CONTA (trava)", 210),
                                        ("servico", "SERVIÇO", 100),
                                        ("canais", "USADA POR", 150),
                                        ("estado", "AGORA", 90)):
            self.tabela_paralelo.heading(coluna, text=titulo)
            self.tabela_paralelo.column(coluna, width=largura, anchor="w")
        self.tabela_paralelo.tag_configure("ocupada", foreground=ORANGE)
        self.tabela_paralelo.tag_configure("dividida", foreground=RED)
        self.tabela_paralelo.pack(fill="x", pady=(3, 0))

        self._vila_filtro = None
        self._vila_estado = {}
        self._vila_bots = {}
        self._vila_visivel = False
        self._vila_lendo = False
        self._vila_modo = "vetor"
        self._vila_fotos = {}
        self._vila_escala = None
        self._vila_montar_cenario()
        self.after(3500, self._vila_auto)

    # -------------------------------------------------- cenario (sprites)
    # A Vila bonita: o mundo vem de vila/config.json (folhas de sprites +
    # mapa montados na Oficina). O mundo ESTATICO vira UMA imagem so — e o
    # que faz um mapa grande rodar liso num canvas Tk; so bots e efeitos
    # sao itens animados por cima. Sem config (ou sem Pillow), cai no
    # desenho vetorial de sempre: a Vila nunca fica em branco.
    def _vila_montar_cenario(self):
        c = self.canvas_vila
        c.delete("all")
        self._vila_bots = {}
        self._vila_fotos = {}
        if self._vila_sprites_iniciar():
            self._vila_modo = "sprites"
        else:
            self._vila_modo = "vetor"
            c.configure(scrollregion=(0, 0, 880, 330))
            self._vila_desenhar_mapa()
        if self._vila_estado:
            self._vila_aplicar_estado()

    def _vila_sprites_iniciar(self) -> bool:
        try:
            from PIL import ImageTk
            from vila import motor
        except Exception:
            return False
        try:
            cfg = motor.carregar()
            if not motor.pronto(cfg):
                return False
            if self._vila_escala is None:
                self._vila_escala = int(cfg.get("escala", 2))
            atlas = motor.Atlas(cfg)
            mundo = motor.compor_mundo(cfg, atlas, self._vila_escala)
        except Exception as erro:
            self._log(f"[vila] cenário em sprites quebrou ({erro}); "
                      "usando o desenho simples.", "erro")
            return False
        self._vila_motor = (motor, cfg, atlas, ImageTk)
        c = self.canvas_vila
        self._vila_fotos["mundo"] = ImageTk.PhotoImage(mundo)
        c.create_image(0, 0, anchor="nw", image=self._vila_fotos["mundo"])
        c.configure(scrollregion=(0, 0, mundo.width, mundo.height))
        ts = int(cfg["tile"]) * self._vila_escala
        self._vila_ts = ts
        mapa = cfg["mapa"]
        casa = mapa.get("casa") or {"x": mapa["larg"] // 2,
                                    "y": mapa["alt"] // 2}
        larg_casa, alt_casa = motor.tamanho(cfg, "predio.casa")
        porta = ((casa["x"] + larg_casa / 2) * ts,
                 (casa["y"] + alt_casa) * ts + 4)

        for i, nome in enumerate(motor.FABRICAS):
            pos = (mapa.get("predios") or {}).get(nome)
            base = [porta[0] + (i - 3) * ts * 0.9, porta[1] + ts * 0.6]
            if pos:
                larg, alt = motor.tamanho(cfg, f"predio.{nome}")
                trabalho = [(pos["x"] + larg / 2) * ts,
                            (pos["y"] + alt) * ts + 4]
                c.create_text(trabalho[0], pos["y"] * ts - 10, text="",
                              font=("Segoe UI", 11, "bold"), fill=RED,
                              tags=(f"alerta_{nome}",))
                c.create_text(trabalho[0], trabalho[1] + 12, text="",
                              font=("Segoe UI", 8), fill="#ffe9a8",
                              tags=(f"legenda_{nome}",))
            else:
                trabalho = list(base)
            item = c.create_image(base[0], base[1], anchor="s")
            foto = self._vila_foto_bot(nome, "baixo", 0)
            if foto is not None:
                c.itemconfigure(item, image=foto)
            balao = c.create_text(base[0], base[1] - ts * 1.5, text="",
                                  font=("Segoe UI", 10))
            self._vila_bots[nome] = {"tipo": "sprite", "itens": (item, balao),
                                     "pos": list(base), "alvo": list(base),
                                     "casa": list(base), "trabalho": trabalho,
                                     "direcao": "baixo", "fase": i * 1.3}
        c.bind("<Button-1>", self._vila_clique_sprites)
        c.bind("<ButtonPress-3>", lambda e: c.scan_mark(e.x, e.y))
        c.bind("<B3-Motion>", lambda e: c.scan_dragto(e.x, e.y, gain=1))
        c.bind("<MouseWheel>",
               lambda e: c.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Shift-MouseWheel>",
               lambda e: c.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        return True

    def _vila_foto(self, papel, quadro=0, fabrica=None):
        """PhotoImage cacheada de um papel (None se nao atribuido)."""
        if not hasattr(self, "_vila_motor"):
            return None
        _motor, _cfg, atlas, ImageTk = self._vila_motor
        chave = (papel, fabrica, int(quadro), self._vila_escala)
        if chave in self._vila_fotos:
            return self._vila_fotos[chave]
        try:
            img = atlas.sprite(papel, int(quadro), self._vila_escala,
                               fabrica=fabrica)
            foto = ImageTk.PhotoImage(img)
        except Exception:
            foto = None
        self._vila_fotos[chave] = foto
        return foto

    def _vila_foto_bot(self, fabrica, direcao, quadro):
        return self._vila_foto(f"bot.{direcao}", quadro, fabrica=fabrica)

    def _vila_clique_sprites(self, evento):
        """Clique no predio filtra o diario (mapa em coordenadas de tile)."""
        if self._vila_modo != "sprites":
            return
        motor, cfg, _atlas, _ = self._vila_motor
        c = self.canvas_vila
        tx = int(c.canvasx(evento.x) // self._vila_ts)
        ty = int(c.canvasy(evento.y) // self._vila_ts)
        for nome, pos in (cfg["mapa"].get("predios") or {}).items():
            larg, alt = motor.tamanho(cfg, f"predio.{nome}")
            if pos["x"] <= tx < pos["x"] + larg                     and pos["y"] <= ty < pos["y"] + alt:
                self._vila_filtrar(nome)
                return

    def _vila_zoom(self, passo):
        if self._vila_modo != "sprites":
            self._log("[vila] o zoom é do cenário em sprites — gere um com "
                      "python -m vila.gerar_base ou monte o seu na 🎨 Oficina.")
            return
        novo = max(1, min(4, (self._vila_escala or 2) + passo))
        if novo != self._vila_escala:
            self._vila_escala = novo
            self._vila_montar_cenario()

    def _vila_bot(self):
        """Liga o bot de Telegram, que é o painel no bolso.

        Sobe como processo separado de propósito: se o painel fechar, o bot
        continua avisando — e é justamente quando você não está na frente do
        PC que um erro precisa chegar até você.
        """
        self._log("[remoto] ligando o bot… o código de emparelhamento aparece "
                  "aqui embaixo (mande-o para o seu bot no Telegram).")
        self._rodar([PY, "-u", "-X", "utf8", "-m", "remoto"], RAIZ,
                    rotulo="bot do Telegram")

    def _vila_oficina(self):
        """A ferramenta de atribuir tudo: folhas, papeis e o mapa."""
        try:
            from vila import editor as vila_editor
        except Exception as erro:
            messagebox.showerror("Oficina", f"não abriu: {erro}")
            return
        vila_editor.Oficina(self, ao_salvar=self._vila_montar_cenario)

    # ------------------------------------------------------------- desenho
    def _vila_desenhar_mapa(self):
        c = self.canvas_vila
        c.delete("all")
        # gramado quadriculado + caminhos de terra ate a casa
        for x in range(0, 880, 40):
            for y in range(0, 330, 40):
                if (x + y) % 80 == 0:
                    c.create_rectangle(x, y, x + 40, y + 40, fill="#1b2b1e",
                                       outline="")
        cx, cy = self.VILA_CASA
        for nome, (x, y, _cor) in self.VILA_PREDIOS.items():
            c.create_line(x + 40, y + 46, cx + 30, cy + 20, fill="#4a3f2c",
                          width=7, capstyle="round")
        # a casa (estudio central, onde os bots moram)
        c.create_rectangle(cx, cy, cx + 62, cy + 44, fill="#6b4a2f",
                           outline="#2c1f13", width=2)
        c.create_polygon(cx - 6, cy, cx + 68, cy, cx + 31, cy - 24,
                         fill="#8a5a36", outline="#2c1f13", width=2)
        c.create_rectangle(cx + 24, cy + 18, cx + 38, cy + 44, fill="#2c1f13",
                           outline="")
        c.create_text(cx + 31, cy + 56, text="🏠 base", fill="#cfc7b8",
                      font=("Segoe UI", 8, "bold"))
        # as fabricas
        for nome, (x, y, cor) in self.VILA_PREDIOS.items():
            dados = atividade_reg.FABRICAS.get(nome, {})
            tag = f"predio_{nome}"
            c.create_rectangle(x, y, x + 80, y + 46, fill=cor, outline="#101010",
                               width=2, tags=(tag,))
            c.create_polygon(x - 5, y, x + 85, y, x + 40, y - 20, fill=cor,
                             outline="#101010", width=2, tags=(tag,))
            c.create_text(x + 40, y + 16,
                          text=f"{dados.get('emoji', '?')} {dados.get('rotulo', nome)}",
                          fill="#0e0e0e", font=("Segoe UI", 8, "bold"), tags=(tag,))
            c.create_text(x + 40, y + 33, text="", fill="#0e0e0e",
                          font=("Segoe UI", 7), tags=(tag, f"legenda_{nome}"))
            c.create_text(x + 40, y - 30, text="", font=("Segoe UI", 12, "bold"),
                          fill="#ff5c5c", tags=(f"alerta_{nome}",))
            c.tag_bind(tag, "<Button-1>",
                       lambda e, alvo=nome: self._vila_filtrar(alvo))
        # um bot por fabrica, morando na base
        for i, (nome, (_x, _y, cor)) in enumerate(self.VILA_PREDIOS.items()):
            bx = cx + 31 + (i - 3) * 14
            by = cy + 52
            corpo = c.create_oval(bx - 7, by - 7, bx + 7, by + 7, fill=cor,
                                  outline="#101010", width=2)
            olho1 = c.create_oval(bx - 4, by - 3, bx - 1, by, fill="#101010",
                                  outline="")
            olho2 = c.create_oval(bx + 1, by - 3, bx + 4, by, fill="#101010",
                                  outline="")
            balao = c.create_text(bx, by - 15, text="", font=("Segoe UI", 9))
            px, py, _cor = self.VILA_PREDIOS[nome]
            self._vila_bots[nome] = {"tipo": "vetor",
                                     "itens": (corpo, olho1, olho2, balao),
                                     "pos": [bx, by], "alvo": [bx, by],
                                     "casa": [bx, by],
                                     "trabalho": [px + 40, py + 58],
                                     "fase": i * 1.3}

    # --------------------------------------------------------------- dados
    def _vila_dados(self):
        """Le o diario FORA da thread da UI (mexe em disco)."""
        if getattr(self, "_vila_lendo", False) or not hasattr(self, "canvas_vila"):
            return
        self._vila_lendo = True
        self._vila_fila = getattr(self, "_vila_fila", queue.Queue())

        def trabalho():
            try:
                estado = atividade_reg.estado_das_fabricas()
                eventos = atividade_reg.recentes(40, self._vila_filtro)
                publicados = 0
                for caminho in (RANDOM_BUILDS / "outputs" / "_publicar" / "publicados.jsonl",
                                HISTORIAS / "outputs" / "_publicar" / "publicados.jsonl"):
                    try:
                        publicados += sum(1 for l in
                                          caminho.read_text(encoding="utf-8").splitlines()
                                          if l.strip())
                    except OSError:
                        pass
                dados = {"estado": estado, "eventos": eventos,
                         "publicados": publicados}
            except Exception as erro:
                dados = {"erro": f"{type(erro).__name__}: {erro}"}
            self._vila_fila.put(dados)

        threading.Thread(target=trabalho, daemon=True).start()
        self.after(200, self._vila_colher)

    def _vila_colher(self):
        try:
            dados = self._vila_fila.get_nowait()
        except queue.Empty:
            if self._vila_lendo:
                self.after(200, self._vila_colher)
            return
        self._vila_lendo = False
        if dados.get("erro"):
            self.lbl_vila_placar.configure(text=f"não li o diário: {dados['erro']}")
            return
        self._vila_estado = dados["estado"]
        ativos = sum(1 for e in dados["estado"].values()
                     if e["status"] == "trabalhando")
        erros = sum(1 for e in dados["estado"].values() if e["status"] == "erro")
        self.lbl_vila_placar.configure(
            text=f"📤 {dados['publicados']} publicados   ·   "
                 f"⚙ {ativos} fábrica(s) trabalhando   ·   "
                 f"{'⚠ ' + str(erros) + ' com problema' if erros else '✓ sem problemas'}")
        self._vila_aplicar_estado()
        self._vila_paralelo()
        self._vila_log(dados["eventos"])

    def _vila_paralelo(self):
        """Quem divide conta com quem — e o que esta preso agora."""
        if not hasattr(self, "tabela_paralelo"):
            return
        try:
            linhas = travas_reg.estado()
        except Exception as erro:
            self.lbl_paralelo.configure(text=f"não li as travas: {erro}")
            return
        self.tabela_paralelo.delete(*self.tabela_paralelo.get_children())
        dividindo = 0
        for linha in linhas:
            compartilhada = len(linha["canais"]) > 1
            dividindo += compartilhada
            tags = ("ocupada",) if linha["ocupada"] else (
                ("dividida",) if compartilhada else ())
            self.tabela_paralelo.insert(
                "", "end", iid=linha["trava"],
                values=(linha["trava"], linha["servico"],
                        " + ".join(linha["canais"]),
                        "⚙ em uso" if linha["ocupada"] else "livre"),
                tags=tags)
        ocupadas = sum(1 for linha in linhas if linha["ocupada"])
        self.lbl_paralelo.configure(
            text=(f"{ocupadas} em uso   ·   {dividindo} conta(s) usada(s) por "
                  "DOIS canais (essas não rodam juntas)"))

    def _vila_aplicar_estado(self):
        c = self.canvas_vila
        for nome, info in self._vila_estado.items():
            bot = self._vila_bots.get(nome)
            if not bot:
                continue
            bot["status"] = info["status"]
            if info["status"] in ("trabalhando", "erro"):
                bot["alvo"] = list(bot["trabalho"])
                bot["balao"] = "⚙" if info["status"] == "trabalhando" else "❗"
            else:
                bot["alvo"] = list(bot["casa"])
                bot["balao"] = ""
            c.itemconfigure(f"alerta_{nome}",
                            text="❗" if info["status"] == "erro" else "")
            detalhe = (info.get("detalhe") or "")[:20]
            c.itemconfigure(f"legenda_{nome}",
                            text=detalhe if info["status"] != "ocioso" else "")

    def _vila_tick(self):
        """Animacao: os bots andam. So roda com a pagina visivel."""
        if not getattr(self, "_vila_visivel", False):
            return
        import math as _math
        import time as _time
        c = self.canvas_vila
        agora = _time.monotonic()
        for nome, bot in self._vila_bots.items():
            px, py = bot["pos"]
            ax, ay = bot["alvo"]
            dx, dy = ax - px, ay - py
            distancia = (dx * dx + dy * dy) ** 0.5
            andando = distancia > 2
            if andando:
                passo = min(3.2, distancia)
                px += dx / distancia * passo
                py += dy / distancia * passo
            # respiracao/caminhada: um balancinho vivo
            bob = _math.sin(agora * 6 + bot["fase"]) * (2 if andando else 0.8)
            bot["pos"] = [px, py]
            if bot["tipo"] == "vetor":
                corpo, olho1, olho2, balao = bot["itens"]
                c.coords(corpo, px - 7, py - 7 + bob, px + 7, py + 7 + bob)
                c.coords(olho1, px - 4, py - 3 + bob, px - 1, py + bob)
                c.coords(olho2, px + 1, py - 3 + bob, px + 4, py + bob)
                c.coords(balao, px, py - 15 + bob)
                c.itemconfigure(balao, text=bot.get("balao", ""))
                continue
            # sprite: direcao pelo eixo dominante + caminhada de 2 quadros
            if andando:
                bot["direcao"] = (("dir" if dx > 0 else "esq")
                                  if abs(dx) > abs(dy)
                                  else ("baixo" if dy > 0 else "cima"))
            quadro = int(agora * 6) % 2 if andando else 0
            foto = self._vila_foto_bot(nome, bot["direcao"], quadro)
            item, balao = bot["itens"]
            if foto is not None:
                c.itemconfigure(item, image=foto)
            c.coords(item, px, py + bob)
            c.coords(balao, px, py - self._vila_ts * 1.5 + bob)
            c.itemconfigure(balao, text=bot.get("balao", ""))
        self.after(60, self._vila_tick)

    def _vila_auto(self):
        """Recarrega o diario sozinho enquanto a pagina esta aberta."""
        if getattr(self, "_vila_visivel", False):
            self._vila_dados()
        self.after(3500, self._vila_auto)

    # ----------------------------------------------------------------- log
    def _vila_filtrar(self, fabrica: str):
        self._vila_filtro = fabrica
        rotulo = atividade_reg.FABRICAS.get(fabrica, {}).get("rotulo", fabrica)
        self.lbl_vila_filtro.configure(text=f"DIÁRIO — {rotulo}")
        self._vila_dados()

    def _vila_sem_filtro(self):
        self._vila_filtro = None
        self.lbl_vila_filtro.configure(text="DIÁRIO  (clique numa fábrica "
                                            "para filtrar)")
        self._vila_dados()

    def _vila_log(self, eventos):
        self.texto_vila.configure(state="normal")
        self.texto_vila.delete("1.0", "end")
        for evento in eventos:
            hora = str(evento.get("ts", ""))[11:19]
            fabrica = atividade_reg.FABRICAS.get(evento.get("fabrica"), {})
            rotulo = fabrica.get("rotulo", evento.get("fabrica", "?"))
            status = evento.get("status", "")
            linha = (f"{hora}  {rotulo:<11} {evento.get('canal', ''):<10} "
                     f"{status:<7} {evento.get('detalhe', '')}\n")
            self.texto_vila.insert("end", linha,
                                   status if status in ("erro", "ok", "inicio")
                                   else ())
        if not eventos:
            self.texto_vila.insert("end", "nada registrado ainda — rode qualquer "
                                          "geração e os bots aparecem aqui.\n")
        self.texto_vila.configure(state="disabled")

    # ------------------------------------------------------ pagina: contas
    def _pagina_contas(self, pai):
        """Todos os logins do ecossistema num lugar só, por CANAL.

        Existe porque os dois canais deixaram de compartilhar conta: publicar
        a história no canal de builds é irreversível. Cada serviço tem uma
        lista de contas e uma conta ATIVA por canal; quem precisa de perfil
        ou credencial pergunta ao registro, nunca monta o caminho na mão.
        """
        self._titulo(pai, "Contas — quem publica o quê, e onde cada login mora")

        cred = self._card(pai, "CREDENCIAIS DO YOUTUBE  (do Google Cloud Console; "
                               "as mesmas para todas as contas)")
        cred.pack(fill="x", padx=20, pady=(6, 0))
        linha = tk.Frame(cred, bg=CARD)
        linha.pack(anchor="w")
        campo_ci, self.var_contas_ci = self._campo(linha, "client-id:", 30)
        campo_ci.pack(side="left")
        campo_cs, self.var_contas_cs = self._campo(linha, "client-secret:", 22)
        campo_cs.pack(side="left", padx=8)
        tk.Label(cred, bg=CARD, fg=DIM, font=("Segoe UI", 8), justify="left",
                 text="O client-id/secret é do PROJETO no Google Cloud e vale para "
                      "qualquer canal; o que muda por conta é o token, criado no "
                      "Autorizar.").pack(anchor="w", pady=(4, 0))

        topo = tk.Frame(pai, bg=BG)
        topo.pack(fill="x", padx=20, pady=(12, 2))
        tk.Label(topo, text="SERVIÇOS  ·  uma linha por canal", bg=BG, fg=DIM,
                 font=FONT_B).pack(side="left")
        self._botao(topo, "↻  Atualizar", self._atualizar_contas).pack(side="right")

        colunas = ("servico", "canal", "conta", "login", "onde")
        self.tabela_contas = ttk.Treeview(pai, columns=colunas, show="headings",
                                          height=12)
        for coluna, texto, largura in (("servico", "SERVIÇO", 110),
                                       ("canal", "CANAL", 100),
                                       ("conta", "CONTA ATIVA", 150),
                                       ("login", "LOGIN", 70),
                                       ("onde", "ONDE FICA", 420)):
            self.tabela_contas.heading(coluna, text=texto)
            self.tabela_contas.column(coluna, width=largura,
                                      anchor="w" if largura > 90 else "center",
                                      stretch=coluna == "onde")
        self.tabela_contas.pack(fill="both", expand=True, padx=20, pady=(0, 6))
        self.tabela_contas.tag_configure("ok", foreground=OK)
        self.tabela_contas.tag_configure("falta", foreground=ORANGE)
        self.tabela_contas.bind("<<TreeviewSelect>>",
                                lambda e: self._contas_selecao())

        acoes = tk.Frame(pai, bg=BG)
        acoes.pack(fill="x", padx=20, pady=(0, 6))
        tk.Label(acoes, text="Conta:", bg=BG, fg=DIM, font=FONT).pack(side="left")
        self.combo_conta = ttk.Combobox(acoes, width=18, state="readonly")
        self.combo_conta.pack(side="left", padx=6)
        self._botao(acoes, "✓  Usar esta conta",
                    self._contas_usar).pack(side="left")
        self._botao(acoes, "➕  Nova conta",
                    self._contas_nova).pack(side="left", padx=6)
        self._botao_primario(acoes, "🔑  Entrar / Autorizar",
                             self._contas_entrar).pack(side="left", padx=6)
        self._botao(acoes, "🗑  Esquecer", self._contas_esquecer,
                    cor=RED).pack(side="right")

        self.lbl_contas = tk.Label(pai, bg=BG, fg=DIM, font=("Segoe UI", 8),
                                   justify="left", anchor="w", wraplength=900)
        self.lbl_contas.pack(fill="x", padx=20, pady=(0, 10))

    def _contas_linha(self):
        selecao = self.tabela_contas.selection()
        if not selecao:
            messagebox.showwarning("Contas", "Selecione um serviço na lista.")
            return None
        servico, canal = selecao[0].split("|", 1)
        return servico, canal

    def _contas_selecao(self):
        selecao = self.tabela_contas.selection()
        if not selecao:
            return
        servico, canal = selecao[0].split("|", 1)
        self.combo_conta["values"] = contas_reg.contas(servico)
        self.combo_conta.set(contas_reg.ativa(servico, canal))
        dados = contas_reg.SERVICOS.get(servico, {})
        self.lbl_contas.configure(
            text=f"{dados.get('rotulo', servico)} · canal {canal}: "
                 f"{dados.get('ajuda', '')}")

    def _contas_usar(self):
        alvo = self._contas_linha()
        if alvo is None:
            return
        servico, canal = alvo
        conta = self.combo_conta.get()
        if not conta:
            return
        contas_reg.escolher(servico, canal, conta)
        self._log(f"[contas] {servico} do canal {canal}: agora usa '{conta}'.", "fim")
        self._atualizar_contas()

    def _contas_nova(self):
        alvo = self._contas_linha()
        if alvo is None:
            return
        servico, canal = alvo
        from tkinter import simpledialog
        nome = simpledialog.askstring(
            "Nova conta",
            f"Nome da nova conta de {contas_reg.SERVICOS[servico]['rotulo']}\n"
            f"(só para você identificar: 'historias', 'canal2'...)", parent=self)
        if not nome:
            return
        limpo = contas_reg.adicionar(servico, nome)
        contas_reg.escolher(servico, canal, limpo)
        self._log(f"[contas] conta '{limpo}' criada em {servico} e ativada no "
                  f"canal {canal}. Clique em Entrar/Autorizar para fazer o login.",
                  "fim")
        self._atualizar_contas()

    def _contas_esquecer(self):
        alvo = self._contas_linha()
        if alvo is None:
            return
        servico, _canal = alvo
        conta = self.combo_conta.get()
        if conta == contas_reg.PADRAO:
            messagebox.showinfo("Contas", "A conta 'principal' não pode ser removida.")
            return
        if not messagebox.askyesno(
                "Esquecer conta",
                f"Tirar '{conta}' da lista de {servico}?\n\n"
                "O login em disco NÃO é apagado — dá para readicionar depois."):
            return
        contas_reg.remover(servico, conta)
        self._atualizar_contas()

    def _contas_entrar(self):
        """Dispara o login certo para o serviço e a conta selecionados."""
        alvo = self._contas_linha()
        if alvo is None:
            return
        servico, canal = alvo
        conta = self.combo_conta.get() or contas_reg.ativa(servico, canal)
        if conta != contas_reg.ativa(servico, canal):
            contas_reg.escolher(servico, canal, conta)

        if servico == "youtube":
            cliente = self.var_contas_ci.get().strip()
            segredo = self.var_contas_cs.get().strip()
            if not (cliente and segredo):
                cliente, segredo = self._credenciais_youtube()
            if not (cliente and segredo):
                messagebox.showinfo(
                    "Autorizar YouTube",
                    "Preencha o client-id e o client-secret no card de cima "
                    "(são os dados do seu projeto no Google Cloud Console).")
                return
            destino = contas_reg.credencial_youtube(canal, conta)
            messagebox.showinfo(
                "Autorizar YouTube",
                f"Vou abrir o navegador para autorizar a conta '{conta}'.\n\n"
                "IMPORTANTE: entre com a conta do Google DESTE canal — é ela "
                "que vai receber os vídeos.\n\n"
                "Marque as permissões de enviar vídeo e de estatísticas.")
            self._rodar([PY, "-m", "neural_fights.tools.youtube_oauth",
                         "--client-id", cliente, "--client-secret", segredo,
                         "--com-upload", "--com-analytics",
                         "--out", str(destino)],
                        rotulo=f"autorizar YouTube ({conta}) (credenciais ocultas)")
        elif servico in ("chatgpt", "gemini"):
            if not HISTORIAS.is_dir():
                messagebox.showinfo("Contas", "A pasta historias/ não existe.")
                return
            messagebox.showinfo(
                "Login no LLM",
                f"Vou abrir o {servico} numa janela do Chrome.\n\n"
                "Entre na sua conta. Quando o chat aparecer, o login fica "
                "salvo e vale para qualquer parte do projeto que use esse LLM.")
            self._rodar([PY, "-u", "-X", "utf8", "main.py", "llm", "login",
                         "--provedor", servico], HISTORIAS,
                        rotulo=f"login no {servico} ({conta})")
        elif servico == "tiktok":
            messagebox.showinfo(
                "Login no TikTok",
                f"Vou abrir o TikTok numa janela do Chrome para a conta "
                f"'{conta}' do canal {canal}.\n\nEntre na conta CERTA: é ela "
                "que vai receber os vídeos desse canal.")
            self._rodar([PY, "-u", "-X", "utf8", "-m", "builds.publicar.tiktok",
                         "--login", "--canal", canal], RANDOM_BUILDS,
                        rotulo=f"login no TikTok ({conta}/{canal})")
        else:  # picasso, digen
            self._rodar([PY, "-u", "-X", "utf8", "main.py", "identity", "login",
                         "--provedor", servico, "--canal", canal], RANDOM_BUILDS,
                        rotulo=f"login no {servico} ({conta}/{canal})")
        self.after(4000, self._atualizar_contas)

    def _atualizar_contas(self):
        if not hasattr(self, "tabela_contas"):
            return
        if not self.var_contas_ci.get().strip():
            cliente, segredo = self._credenciais_youtube()
            if cliente:
                self.var_contas_ci.set(cliente)
            if segredo:
                self.var_contas_cs.set(segredo)
        selecionado = self.tabela_contas.selection()
        self.tabela_contas.delete(*self.tabela_contas.get_children())
        for linha in contas_reg.resumo():
            iid = f"{linha['servico']}|{linha['canal']}"
            marca = "sim" if linha["logado"] else "FALTA"
            self.tabela_contas.insert(
                "", "end", iid=iid,
                tags=("ok" if linha["logado"] else "falta",),
                values=(linha["rotulo"], linha["canal"], linha["conta"],
                        marca, linha["onde"]))
        if selecionado and self.tabela_contas.exists(selecionado[0]):
            self.tabela_contas.selection_set(selecionado)
        self._contas_selecao()

    # ---------------------------------------------------- pagina: historias
    def _pagina_historias(self, pai):
        """O canal de historias por IA: roteiro -> imagens -> video.

        Projeto separado (pasta `historias/`), controlado daqui. O fluxo tem
        um passo que NAO e automatico de proposito: o roteiro nasce no LLM
        que voce usa. O painel monta o prompt, voce cola la, copia a resposta
        e clica em importar - o resto (imagens, narracao, video) e um botao.
        """
        self._titulo(pai, "Histórias por IA — roteiro, imagens, narração e vídeo")

        if not HISTORIAS.is_dir():
            tk.Label(pai, text="A pasta historias/ não existe ao lado do painel.",
                     bg=BG, fg=RED, font=FONT_B).pack(anchor="w", padx=20)
            return

        # --- 1) geracao automatica: o browser conversa com o LLM sozinho
        card = self._card(pai, "1. ROTEIRO AUTOMÁTICO  —  o browser abre o LLM, "
                               "planeja a série e escreve cada parte")
        card.pack(fill="x", padx=20, pady=(6, 0))
        linha = tk.Frame(card, bg=CARD)
        linha.pack(anchor="w", fill="x")
        tk.Label(linha, text="LLM:", bg=CARD, fg=DIM, font=FONT).pack(side="left")
        self.combo_hllm = ttk.Combobox(linha, width=9, state="readonly",
                                       values=("chatgpt", "gemini"))
        self.combo_hllm.current(0)
        self.combo_hllm.pack(side="left", padx=(4, 10))
        tk.Label(linha, text="Partes:", bg=CARD, fg=DIM, font=FONT).pack(side="left")
        self.var_hpartes = tk.StringVar(value="6")
        tk.Spinbox(linha, from_=1, to=30, width=4, textvariable=self.var_hpartes,
                   bg=CARD_HL, fg=TEXT, buttonbackground=CARD, relief="flat",
                   font=FONT).pack(side="left", padx=(4, 10))
        tk.Label(linha, text="Cenas/parte:", bg=CARD, fg=DIM,
                 font=FONT).pack(side="left")
        self.var_hcenas = tk.StringVar(value="14")
        tk.Spinbox(linha, from_=4, to=40, width=4, textvariable=self.var_hcenas,
                   bg=CARD_HL, fg=TEXT, buttonbackground=CARD, relief="flat",
                   font=FONT).pack(side="left", padx=(4, 10))
        tk.Label(linha, text="Tema (opcional):", bg=CARD, fg=DIM,
                 font=FONT).pack(side="left")
        self.var_htema = tk.StringVar()
        tk.Entry(linha, textvariable=self.var_htema, width=26, bg=CARD_HL,
                 fg=TEXT, insertbackground=TEXT, relief="flat",
                 font=FONT).pack(side="left", padx=4)
        self._botao_primario(linha, "🤖  Gerar história",
                             self._historias_gerar).pack(side="left", padx=8)
        self._botao(linha, "🔑  Login no LLM",
                    self._historias_login).pack(side="left")
        self.lbl_hauto = tk.Label(
            card, bg=CARD, fg=DIM, font=("Segoe UI", 8), justify="left",
            text="Cada parte vira um vídeo. Uma janela do Chrome abre e conduz a "
                 "conversa: primeiro a bíblia da história, depois cada parte. "
                 "Faça o login uma vez por LLM.")
        self.lbl_hauto.pack(anchor="w", pady=(4, 0))

        # --- 1b) o caminho manual, para quando quiser escolher o LLM na mao
        card2 = self._card(pai, "1b. ROTEIRO MANUAL  —  monte o prompt, cole no "
                                "LLM que quiser, traga a resposta")
        card2.pack(fill="x", padx=20, pady=(8, 0))
        linha2 = tk.Frame(card2, bg=CARD)
        linha2.pack(anchor="w", fill="x")
        tk.Label(linha2, text="Modelo:", bg=CARD, fg=DIM, font=FONT).pack(side="left")
        self.combo_hmodelo = ttk.Combobox(linha2, width=14, state="readonly",
                                          values=self._historias_modelos())
        if self.combo_hmodelo["values"]:
            self.combo_hmodelo.current(0)
        self.combo_hmodelo.pack(side="left", padx=6)
        self._botao(linha2, "📋  Gerar prompt e copiar",
                    self._historias_prompt).pack(side="left", padx=10)
        self._botao(linha2, "📥  Importar resposta (clipboard)",
                    self._historias_importar).pack(side="left")
        tk.Label(card2, bg=CARD, fg=DIM, font=("Segoe UI", 8), justify="left",
                 text="O modelo dita só a ESTRUTURA; a ideia é do LLM. Modelo próprio: "
                      "um .txt em historias/modelos/.").pack(anchor="w", pady=(4, 0))

        # --- 2) as historias
        topo = tk.Frame(pai, bg=BG)
        topo.pack(fill="x", padx=20, pady=(12, 2))
        tk.Label(topo, text="2. HISTÓRIAS  (duplo-clique assiste)", bg=BG, fg=DIM,
                 font=FONT_B).pack(side="left")
        self._botao(topo, "↻  Atualizar", self._atualizar_historias).pack(side="right")

        colunas = ("id", "titulo", "partes", "cenas", "imagens", "videos",
                   "dur", "passo")
        self.tabela_hist = ttk.Treeview(pai, columns=colunas, show="headings",
                                        height=9)
        for coluna, texto, largura in (
                ("id", "HISTÓRIA", 130), ("titulo", "TÍTULO", 300),
                ("partes", "PARTES", 60), ("cenas", "CENAS", 55),
                ("imagens", "IMAGENS", 75), ("videos", "VÍDEOS", 60),
                ("dur", "DUR", 50), ("passo", "PRÓXIMO PASSO", 300)):
            self.tabela_hist.heading(coluna, text=texto)
            self.tabela_hist.column(coluna, width=largura,
                                    anchor="w" if largura > 100 else "center",
                                    stretch=coluna == "passo")
        self.tabela_hist.pack(fill="both", expand=True, padx=20, pady=(0, 6))
        self.tabela_hist.tag_configure("pronta", foreground=OK)
        self.tabela_hist.tag_configure("faltando", foreground=ORANGE)
        self.tabela_hist.bind("<Double-1>", lambda e: self._historias_acao("assistir"))

        acoes = tk.Frame(pai, bg=BG)
        acoes.pack(fill="x", padx=20, pady=(0, 12))
        self._botao_primario(acoes, "▶  Gerar tudo (imagens + vídeo)",
                             lambda: self._historias_acao("tudo")).pack(side="left")
        self._botao(acoes, "🖼  Só imagens",
                    lambda: self._historias_acao("imagens")).pack(side="left", padx=6)
        self._botao(acoes, "🎬  Só vídeo",
                    lambda: self._historias_acao("video")).pack(side="left")
        self._botao(acoes, "▶  Assistir",
                    lambda: self._historias_acao("assistir")).pack(side="left", padx=6)
        self._botao(acoes, "📁  Pasta",
                    lambda: self._historias_acao("pasta")).pack(side="left")
        self._botao_primario(acoes, "🚀  Publicar série",
                             self._historias_publicar).pack(side="right", padx=6)
        self._botao(acoes, "🩺  Vistoriar",
                    lambda: self._historias_acao("vistoriar")).pack(side="right")
        self._botao(acoes, "📤  Exportar",
                    lambda: self._historias_acao("exportar")).pack(side="right", padx=6)
        self._botao(acoes, "🩺  Probe LLM",
                    self._historias_probe).pack(side="right", padx=6)
        tk.Label(pai, bg=BG, fg=DIM, font=("Segoe UI", 8), justify="left",
                 text="As imagens usam a MESMA conta do PicassoIA da outra pipeline: "
                      "os dois workers nunca rodam juntos (a trava é compartilhada). "
                      "Se estiver pausado na faixa PIPELINE, retome antes."
                 ).pack(anchor="w", padx=20, pady=(0, 8))

    @staticmethod
    def _historias_modelos():
        try:
            import json
            with open(HISTORIAS / "config" / "roteiro.json", encoding="utf-8-sig") as fh:
                config = json.load(fh)
            nomes = list(config["modelos"])
            proprios = sorted(p.stem for p in (HISTORIAS / "modelos").glob("*.txt")) \
                if (HISTORIAS / "modelos").is_dir() else []
            return nomes + proprios
        except (OSError, ValueError, KeyError):
            return ["reddit"]

    def _historias_cli(self, args, rotulo):
        self._rodar([PY, "-u", "-X", "utf8", "main.py", *args], HISTORIAS,
                    rotulo=rotulo)

    def _historias_gerar(self):
        """Dispara a serie inteira: biblia + cada parte, no browser."""
        try:
            partes = max(1, int(self.var_hpartes.get() or 6))
            cenas = max(4, int(self.var_hcenas.get() or 14))
        except ValueError:
            messagebox.showwarning("Histórias", "Partes e cenas precisam ser números.")
            return
        # Sem dialogo (decisao do Adrian, 31/08: um clique). O aviso vai
        # para o log; a trava por conta impede duas geracoes na mesma conta.
        self._log(f"[histórias] abrindo o {self.combo_hllm.get()} para escrever "
                  f"{partes} parte(s) de {cenas} cenas — leva vários minutos; "
                  "não mexa na janela do Chrome.")
        args = ["gerar", "--provedor", self.combo_hllm.get(),
                "--partes", str(partes), "--cenas", str(cenas)]
        tema = self.var_htema.get().strip()
        if tema:
            args += ["--tema", tema]
        self._historias_cli(args, f"gerar história ({self.combo_hllm.get()})")
        self.after(8000, self._atualizar_historias)

    def _historias_login(self):
        provedor = self.combo_hllm.get()
        messagebox.showinfo(
            "Login no LLM",
            f"Vou abrir o {provedor} numa janela do Chrome.\n\n"
            "Entre na sua conta normalmente. Quando o chat aparecer, o login "
            "fica salvo no perfil e a geração automática passa a funcionar.")
        self._historias_cli(["llm", "login", "--provedor", provedor],
                            f"login no {provedor}")

    def _historias_probe(self):
        self._historias_cli(["llm", "probe", "--provedor", self.combo_hllm.get()],
                            f"probe do {self.combo_hllm.get()}")

    def _historias_prompt(self):
        args = ["prompt", self.combo_hmodelo.get() or "reddit", "--copiar"]
        tema = self.var_htema.get().strip()
        if tema:
            args += ["--tema", tema]
        self._historias_cli(args, "montar prompt-mestre")
        self._log("[histórias] o prompt vai para o clipboard: cole no seu LLM, "
                  "copie a resposta e clique em 'Importar resposta'.", "fim")

    def _historias_importar(self):
        self._historias_cli(["roteiro", "--colar", "--modelo",
                             self.combo_hmodelo.get() or "reddit"],
                            "importar roteiro do clipboard")
        self.after(2500, self._atualizar_historias)

    def _historias_selecionada(self):
        selecao = self.tabela_hist.selection()
        if not selecao:
            messagebox.showwarning("Histórias", "Selecione uma história na lista.")
            return None
        return selecao[0]

    def _historias_acao(self, acao: str):
        historia = self._historias_selecionada()
        if historia is None:
            return
        pasta = HISTORIAS / "outputs" / historia
        if acao == "pasta":
            os.startfile(str(pasta))
            return
        if acao == "assistir":
            for nome in ("final_celular.mp4", "final_normal.mp4"):
                if (pasta / nome).is_file():
                    os.startfile(str(pasta / nome))
                    return
            messagebox.showinfo("Assistir", "Esta história ainda não tem vídeo.")
            return
        if acao == "exportar":
            self._historias_cli(["publicar", historia, "--exportar"],
                                f"exportar {historia}")
            return
        if acao == "vistoriar":
            self._historias_cli(["publicar", historia, "--vistoriar"],
                                f"vistoriar {historia}")
            return
        comandos = {"tudo": ["tudo", historia], "imagens": ["imagens", historia],
                    "video": ["video", historia]}
        self._historias_cli(comandos[acao], f"{acao} {historia}")
        self.after(3000, self._atualizar_historias)

    def _historias_publicar(self):
        """Um clique: vistoria, sobe as partes na ordem e agenda a sequência."""
        historia = self._historias_selecionada()
        if historia is None:
            return
        # QUAL login importa depende de por onde se publica. Desde 01/09 o
        # padrao e navegador: cobrar o OAuth aqui bloquearia justamente o
        # caminho que nao precisa dele — e liberar por ele deixaria o erro
        # aparecer so la na frente, com o Chrome ja aberto.
        servico = self._servico_youtube()
        conta = contas_reg.ativa(servico, "historias")
        if not contas_reg.tem_login(servico, "historias"):
            if servico == "youtube_web":
                messagebox.showinfo(
                    "Publicar série",
                    f"O YouTube Studio do canal Histórias ('{conta}') ainda "
                    "não tem login neste computador.\n\nVá na "
                    "página Publicar e clique em Login YouTube Studio — é "
                    "uma vez só, igual ao TikTok.")
                self._mostrar("publicar")
            else:
                messagebox.showinfo(
                    "Publicar série",
                    f"A conta de YouTube do canal Histórias ('{conta}') ainda "
                    "não foi autorizada.\n\nVá na página Contas, "
                    "selecione YouTube / historias e clique em Entrar / "
                    "Autorizar.")
                self._mostrar("contas")
            return
        # UM clique, sem dialogo (decisao do Adrian, 31/08): a vistoria e o
        # freio — parte com problema nao sobe. YouTube agendado; TikTok posta
        # a proxima parte pendente quando a conta do canal tem login.
        # Destino ANTES de subir: sem conta própria, o registro cai na conta
        # `principal` — que é a de builds. Um vídeo de história no canal de
        # builds é irreversível, e nada avisaria.
        args = ["publicar", historia, "--serie"]
        yt = contas_reg.destino(servico, "historias")
        if not yt["explicita"]:
            self._log(
                f"[histórias] PAREI: o canal historias não tem conta de "
                f"YouTube própria — subiria em '{yt['conta']}', a de builds. "
                "Vá em 🔑 Contas → youtube → historias e escolha (ou "
                "cadastre) a conta certa. Se for pra usar a mesma mesmo, "
                "clique 'Usar esta conta' lá que eu paro de reclamar.", "erro")
            self._mostrar("contas")
            return
        tt = contas_reg.destino("tiktok", "historias")
        if tt["explicita"] and tt["tem_login"]:
            args.append("--tiktok")
        elif not tt["explicita"]:
            self._log("[histórias] TikTok: canal historias sem conta própria "
                      "(usaria a de builds) — só YouTube desta vez. Escolha a "
                      "conta em 🔑 Contas.", "erro")
        else:
            self._log("[histórias] TikTok sem login no canal historias: só "
                      "YouTube desta vez (página Contas → Entrar).", "erro")
        self._log(f"[histórias] publicando {historia}: YouTube agendado de 24 "
                  "em 24 h" + (" + TikTok (posta a próxima parte)"
                               if "--tiktok" in args else "") + ".")
        self._historias_cli(args, f"publicar série {historia}")

    def _atualizar_historias(self):
        """Le o estado das historias FORA da thread da UI (toca disco)."""
        if not hasattr(self, "tabela_hist"):
            return
        if getattr(self, "_hist_lendo", False):
            return
        self._hist_lendo = True
        self._hist_fila = getattr(self, "_hist_fila", queue.Queue())

        def trabalho():
            try:
                import subprocess as sp
                saida = sp.run([PY, "-X", "utf8", "-c",
                                "import sys, json; sys.path.insert(0, '.');"
                                "from contos.pipeline.controller import Pipeline;"
                                "print(json.dumps(Pipeline().listar()))"],
                               cwd=str(HISTORIAS), capture_output=True, text=True,
                               encoding="utf-8", timeout=120,
                               creationflags=NO_WINDOW)
                import json as _json
                dados = _json.loads((saida.stdout or "[]").strip().splitlines()[-1])
            except Exception as erro:
                dados = {"erro": f"{type(erro).__name__}: {erro}"}
            self._hist_fila.put(dados)

        threading.Thread(target=trabalho, daemon=True).start()
        self.after(200, self._colher_historias)

    def _colher_historias(self):
        try:
            dados = self._hist_fila.get_nowait()
        except queue.Empty:
            if getattr(self, "_hist_lendo", False):
                self.after(200, self._colher_historias)
            return
        self._hist_lendo = False
        if not hasattr(self, "tabela_hist"):
            return
        if isinstance(dados, dict):
            self._log(f"[histórias] não consegui ler: {dados.get('erro')}", "erro")
            return
        selecionado = self.tabela_hist.selection()
        self.tabela_hist.delete(*self.tabela_hist.get_children())
        for status in dados:
            imagens = f"{status['imagens']['prontas']}/{status['imagens']['total']}"
            videos = f"{status['videos_prontos']}/{status['n_partes']}"
            completa = (status["imagens"]["completa"]
                        and status["videos_prontos"] == status["n_partes"])
            self.tabela_hist.insert(
                "", "end", iid=status["historia_id"],
                tags=("pronta" if completa else "faltando",),
                values=(status["historia_id"], status["titulo"],
                        status["n_partes"], status["cenas"], imagens, videos,
                        f"{status['duracao']:.0f}s" if status["duracao"] else "-",
                        status["proximo_passo"]))
        if selecionado and self.tabela_hist.exists(selecionado[0]):
            self.tabela_hist.selection_set(selecionado)
        elif dados:
            self.tabela_hist.selection_set(dados[0]["historia_id"])

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
    vivem em SessaoTriagem (random_builds/builds/assets/triagem.py).
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
