# -*- coding: utf-8 -*-
"""A janela "Blue Lock — versoes": escolher a versao do jogo e abrir.

O que o atalho da Area de Trabalho abre (pythonw, sem console). Lista a main,
os ramos do GitHub dele (com o veredito do vigia de ramos, a data e o CI) e
as versoes ja preparadas; aceita um commit colado. "Rodar" prepara a versao
(pasta + npm ci se o lock for novo + build) mostrando o progresso e abre o
jogo numa janela VISIVEL do Chrome (perfil proprio do lancador).

A cara e a das janelas de trabalho do painel (`painel.estilo.OFICINA`):
sobria e densa, borda em vez de bloco de cor, acento so no que e clicavel.

O trabalho pesado roda numa thread e fala com a tela por uma FILA lida pelo
`after` da thread da interface — `after()` chamado de outra thread quebra o
Tk (memoria random-builds-reacoes-e-fluxo).
"""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from tkinter import messagebox, ttk

from .ramos import VigiaDeRamos, link_de_pr
from .versoes import MANTER, ErroDeVersao, Versoes, matar_arvore

ICONE_DO_TIPO = {"vale": "✅", "espere": "⏸", "nao_vale": "❌", "olho": "👀", "na_main": "✔"}
COLUNAS = [("versao", "Versão", 330, "w"), ("commit", "Commit", 70, "w"), ("data", "Data", 92, "w"),
           ("veredito", "Veredito do vigia", 380, "w"), ("ci", "CI", 78, "w"),
           ("testes", "Testes aqui", 92, "w"), ("pronta", "Pronta", 70, "w")]


def _hora(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m %H:%M")
    except ValueError:
        return iso[:16]


def _ci(r: dict) -> str:
    ci = r.get("ci") or {}
    if not r.get("a_frente"):
        return "—"
    return {"success": "verde", "failure": "vermelho"}.get(ci.get("conclusao") or "", "") or \
        ({"in_progress": "rodando", "queued": "na fila"}.get(ci.get("estado") or "", "") or "sem CI")


def _testes(r: dict) -> str:
    t = r.get("testes") or {}
    if not t.get("rodou"):
        return "—"
    contas = t.get("testes") or {}
    if contas:
        return f"{'ok' if t.get('ok') else 'falhou'} {contas.get('passou', '?')}/{contas.get('total', '?')}"
    return "ok" if t.get("ok") else "falhou"


def linhas(ramos_clone: list[dict], tabela: dict | None, registro: dict) -> list[dict]:
    """As linhas da tabela, na ordem: main, ramos com coisa a decidir, ramos
    ja na main, e por fim os commits colados que estao preparados. Pura (o
    teste chama sem Tk)."""
    tabela = tabela or {}
    analise = {r["ramo"]: r for r in tabela.get("ramos") or []}
    versoes = registro.get("versoes") or {}

    def pronta(sha: str) -> str:
        ficha = versoes.get(sha) or {}
        marca = "★ " if ficha.get("fixada") else ""
        if ficha.get("modo") == "html":
            return marca + "sim"
        if ficha.get("modo") == "servidor":
            return marca + "sim (servidor)"
        return marca + ("pasta" if ficha else "")

    saida, vistos = [], set()
    for r in ramos_clone:
        sha, nome = r["sha"], r["ramo"]
        vistos.add(sha)
        a = analise.get(nome) if (analise.get(nome) or {}).get("sha") == sha else None
        if nome == "main":
            saida.append({"id": "ramo:main", "ref": "main", "sha": sha, "tipo": "main", "ordem": 0,
                          "valores": ("main — a versão oficial", sha[:7], _hora(r.get("data")),
                                      r.get("assunto", "")[:70], "", "", pronta(sha)), "analise": None,
                          "assunto": r.get("assunto", "")})
            continue
        if a:
            v = a.get("veredito") or {}
            tipo = v.get("tipo") or "espere"
            texto = f"{ICONE_DO_TIPO.get(tipo, '•')} {v.get('texto', '')}".replace("`", "")
            ci, testes = _ci(a), _testes(a)
        else:
            tipo, texto, ci, testes = "espere", "⏸ o vigia ainda não olhou esta cabeça", "", ""
        ordem = 2 if tipo == "na_main" else 1
        saida.append({"id": f"ramo:{nome}", "ref": nome, "sha": sha, "tipo": tipo, "ordem": ordem,
                      "valores": (nome, sha[:7], _hora(r.get("data")), texto, ci, testes, pronta(sha)),
                      "analise": a, "assunto": r.get("assunto", "")})
    for sha, ficha in sorted(versoes.items(), key=lambda par: par[1].get("usada_em") or "", reverse=True):
        if sha in vistos:
            continue
        rotulo = f"commit {sha[:7]} — {ficha.get('assunto', '')}"[:80]
        saida.append({"id": f"commit:{sha}", "ref": sha, "sha": sha, "tipo": "commit", "ordem": 3,
                      "valores": (rotulo, sha[:7], _hora(ficha.get("data")), f"(colado; era {ficha.get('ref', '?')})",
                                  "", "", pronta(sha)), "analise": None, "assunto": ficha.get("assunto", "")})
    saida.sort(key=lambda linha: linha["ordem"])
    return saida


def detalhe(linha: dict | None) -> str:
    """O texto do cartao de baixo para a linha escolhida."""
    if not linha:
        return "Escolha uma versão na lista (ou cole um commit) e clique em Rodar."
    a = linha.get("analise")
    partes = [f"{linha['valores'][0]}  ·  {linha['sha'][:10]}  ·  {linha.get('assunto', '')}"]
    if a:
        v = a.get("veredito") or {}
        partes.append(f"Veredito: {v.get('texto', '').replace('`', '')}")
        partes.append(f"Relação com a main: +{a.get('a_frente', 0)} à frente, -{a.get('atras', 0)} atrás"
                      + (", fast-forward" if a.get("ff") and a.get("a_frente") else ""))
        if a.get("contem"):
            partes.append("Contém os ramos: " + ", ".join(a["contem"]))
        if a.get("areas"):
            partes.append(f"Mexe em {a.get('arquivos', 0)} arquivo(s): "
                          + ", ".join(f"{k} {n}" for k, n in a["areas"].items()))
        for commit in (a.get("commits") or [])[:6]:
            partes.append(f"  • {commit.get('hash')} {commit.get('assunto', '')[:90]}")
        if a.get("comando"):
            partes.append(f"Para dar merge (no seu clone, depois de git fetch):  {a['comando']}")
        elif a.get("a_frente"):
            partes.append(f"PR: {link_de_pr(linha['ref'])}")
    return "\n".join(partes)


class Janela:
    def __init__(self, raiz, *, versoes: Versoes | None = None, vigia: VigiaDeRamos | None = None,
                 atualizar_ao_abrir: bool = True):
        from painel.estilo import ESPACO, OFICINA
        from painel.widgets import Oficina
        self.raiz = raiz
        self.tema = OFICINA
        self.o = Oficina(OFICINA)
        self.E = ESPACO
        self.fila: queue.Queue = queue.Queue()
        self.versoes = versoes or Versoes(log=lambda texto: self.fila.put(("log", texto)))
        if versoes is not None:
            versoes.log = lambda texto: self.fila.put(("log", texto))
        self.vigia = vigia or VigiaDeRamos(self.versoes, log=lambda texto: self.fila.put(("log", texto)))
        self.servidores = []
        self._ultima: dict | None = None        # a ultima analise dos ramos (Atualizar)
        self.linhas: list[dict] = []
        self.ocupado = False
        self._montar()
        self._mostrar(self.versoes.ramos() if self.versoes.tem_clone() else [], self.vigia.ler())
        self.raiz.after(100, self._drenar)
        if atualizar_ao_abrir:
            self.atualizar()

    # --- montagem ---------------------------------------------------
    def _montar(self):
        r, t, o, E = self.raiz, self.tema, self.o, self.E
        r.title("Blue Lock — versões")
        r.configure(bg=t.fundo)
        # A tela dele e 1366x768 (memoria painel-ui-reativo): cabe com a barra
        # de tarefas.
        largura = min(1180, r.winfo_screenwidth() - 40)
        altura = min(680, r.winfo_screenheight() - 90)
        r.geometry(f"{largura}x{altura}+20+10")
        r.minsize(900, 520)
        o.aplicar_ttk(r)
        r.protocol("WM_DELETE_WINDOW", self.fechar)
        try:
            from .versoes import caminho_do_icone
            if caminho_do_icone().is_file():
                r.iconbitmap(default=str(caminho_do_icone()))
        except (tk.TclError, OSError):
            pass

        topo = tk.Frame(r, bg=t.fundo)
        topo.pack(fill="x")
        o.titulo(topo, "Blue Lock — versões")
        self.resumo = o.legenda(topo, "")
        self.resumo.pack(anchor="w", padx=E["secao"], pady=(0, E["meio"]))

        # O RODAPE SE EMPACOTA ANTES DA TABELA, por baixo. Empacotado depois,
        # o cartao com `expand` comia a altura e os botoes, o commit colado e
        # o progresso sumiam para fora da janela (captura de 19/10, 21:23).
        rodape = tk.Frame(r, bg=t.fundo)
        rodape.pack(side="bottom", fill="x", padx=E["secao"], pady=(0, E["muito"]))
        self.estado = o.rotulo(rodape, "pronto", cor="texto_fraco")
        self.estado.pack(anchor="w")
        self.barra = ttk.Progressbar(rodape, mode="determinate", maximum=5)
        self.barra.pack(fill="x", pady=(E["pouco"], E["pouco"]))
        self.console = tk.Text(rodape, height=2, bg=t.console_fundo, fg=t.console_texto, relief="flat",
                               font=t.letra("mono"), wrap="none", highlightthickness=0, bd=0)
        self.console.pack(fill="x")

        botoes = tk.Frame(r, bg=t.fundo)
        botoes.pack(side="bottom", fill="x", padx=E["secao"], pady=(0, E["meio"]))
        self.b_rodar = o.botao(botoes, "▶  Rodar", self.rodar, tipo="primario")
        self.b_rodar.pack(side="left")
        self.b_atualizar = o.botao(botoes, "Atualizar lista", self.atualizar)
        self.b_atualizar.pack(side="left", padx=(E["meio"], 0))
        self.b_fixar = o.botao(botoes, "Fixar / soltar", self.fixar)
        self.b_fixar.pack(side="left", padx=(E["meio"], 0))
        self.b_comando = o.botao(botoes, "Copiar comando de merge", self.copiar_comando)
        self.b_comando.pack(side="left", padx=(E["meio"], 0))
        self.b_limpar = o.botao(botoes, "Apagar versões velhas", self.limpar, tipo="perigo")
        self.b_limpar.pack(side="right")
        o.botao(botoes, "Abrir pasta", self.abrir_pasta).pack(side="right", padx=(0, E["meio"]))

        linha_commit = tk.Frame(r, bg=t.fundo)
        linha_commit.pack(side="bottom", fill="x", padx=E["secao"], pady=(0, E["meio"]))
        moldura, self.commit = o.campo(linha_commit, "Colar um commit (ou nome de ramo):", largura=44)
        moldura.pack(side="left")
        o.botao(linha_commit, "Rodar este commit", self.rodar_colado).pack(side="left", padx=E["meio"])

        cartao = o.cartao(r, "Versões do jogo")
        cartao.pack(fill="both", expand=True, padx=E["secao"], pady=(0, E["meio"]))
        quadro = tk.Frame(cartao.corpo, bg=t.superficie)
        quadro.pack(fill="both", expand=True)
        # Altura da linha e largura das colunas pela FONTE medida: com a
        # escala de DPI o `rowheight` fixo de 22 px sobrepunha as linhas e o
        # sha de 7 letras nao cabia em 70 px.
        letra = tkfont.Font(root=r, font=t.letra("corpo"))
        ttk.Style(r).configure("Treeview", rowheight=letra.metrics("linespace") + 6)
        exemplo = {"versao": "feat/pressured-reception-continuation", "commit": "face59dc",
                   "data": "19/10 17:18", "ci": "vermelho", "testes": "ok 1684/1684", "pronta": "★ sim"}
        colunas = [(c, titulo, max(largura, letra.measure(exemplo.get(c, titulo)) + 16,
                                   letra.measure(titulo) + 16) if c != "veredito" else largura, alinha)
                   for c, titulo, largura, alinha in COLUNAS]
        self.tabela = o.tabela(quadro, colunas, altura=10, estica="veredito")
        barra = ttk.Scrollbar(quadro, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=barra.set)
        self.tabela.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.tabela.tag_configure("na_main", foreground=t.texto_apagado)
        self.tabela.tag_configure("vale", foreground=t.ok)
        self.tabela.tag_configure("nao_vale", foreground=t.erro)
        self.tabela.tag_configure("olho", foreground=t.aviso)
        self.tabela.tag_configure("main", foreground=t.acento_forte)
        self.tabela.bind("<<TreeviewSelect>>", lambda _e: self._escolheu())
        self.tabela.bind("<Double-1>", lambda _e: self.rodar())

        self.texto = tk.Text(cartao.corpo, height=4, bg=t.superficie, fg=t.texto_fraco, relief="flat",
                             font=t.letra("corpo"), wrap="word", highlightthickness=0, bd=0)
        self.texto.pack(side="bottom", fill="x", pady=(E["meio"], 0), before=quadro)
        self._escrever_detalhe(None)

    # --- tabela -----------------------------------------------------
    def _mostrar(self, ramos_clone, tabela):
        escolhido = self._linha_escolhida()
        self.linhas = linhas(ramos_clone, tabela, self.versoes.ler())
        self.tabela.delete(*self.tabela.get_children())
        for linha in self.linhas:
            self.tabela.insert("", "end", iid=linha["id"], values=linha["valores"], tags=(linha["tipo"],))
        if escolhido and self.tabela.exists(escolhido["id"]):
            self.tabela.selection_set(escolhido["id"])
        elif self.linhas:
            self.tabela.selection_set(self.linhas[0]["id"])
        main = (tabela or {}).get("main") or {}
        abertos = [r for r in (tabela or {}).get("ramos") or [] if r.get("a_frente")]
        texto = (f"{len(self.linhas)} versões · {len(abertos)} ramo(s) fora da main · "
                 f"vigia olhou {_hora((tabela or {}).get('olhado_em')) or 'nunca'}")
        if main.get("sha"):
            texto = f"main {main['sha'][:7]} · " + texto
        if (tabela or {}).get("pesado"):
            texto += f" · testes adiados: {tabela['pesado']}"
        self.resumo.configure(text=texto)

    def _linha_escolhida(self):
        escolha = self.tabela.selection()
        if not escolha:
            return None
        return next((linha for linha in self.linhas if linha["id"] == escolha[0]), None)

    def _escolheu(self):
        self._escrever_detalhe(self._linha_escolhida())

    def _escrever_detalhe(self, linha):
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.insert("1.0", detalhe(linha))
        self.texto.configure(state="disabled")

    # --- trabalho em thread -----------------------------------------
    def _em_thread(self, rotulo: str, trabalho):
        if self.ocupado:
            messagebox.showinfo("Espere", "Ainda estou terminando a tarefa anterior.")
            return
        self.ocupado = True
        for b in (self.b_rodar, self.b_atualizar, self.b_limpar, self.b_fixar):
            b.configure(state="disabled")
        self.estado.configure(text=rotulo, fg=self.tema.texto)
        self.barra.configure(value=0)

        def correr():
            try:
                self.fila.put(("fim", trabalho()))
            except ErroDeVersao as exc:
                self.fila.put(("erro", str(exc)))
            except Exception as exc:                            # noqa: BLE001
                self.fila.put(("erro", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=correr, daemon=True).start()

    def _drenar(self):
        try:
            while True:
                tipo, *resto = self.fila.get_nowait()
                if tipo == "log":
                    self._log(resto[0])
                elif tipo == "progresso":
                    n, total, texto = resto
                    self.barra.configure(maximum=total, value=n)
                    self.estado.configure(text=f"[{n}/{total}] {texto}")
                elif tipo in ("fim", "erro"):
                    self._terminou(tipo, resto[0])
        except queue.Empty:
            pass
        try:
            self.raiz.after(100, self._drenar)
        except tk.TclError:
            pass

    def _terminou(self, tipo, carga):
        self.ocupado = False
        for b in (self.b_rodar, self.b_atualizar, self.b_limpar, self.b_fixar):
            b.configure(state="normal")
        if tipo == "erro":
            self.estado.configure(text=f"erro: {carga}", fg=self.tema.erro)
            self._log(f"erro: {carga}")
            return
        acao, dados = carga
        if acao == "lista":
            self._mostrar(*dados)
            self.estado.configure(text="lista atualizada", fg=self.tema.texto_fraco)
        elif acao == "rodou":
            self.barra.configure(value=self.barra.cget("maximum"))
            if dados.get("servidor"):
                self.servidores.append(dados["servidor"])
            self.estado.configure(text=f"aberto: {dados['url']}", fg=self.tema.ok)
            self._mostrar(self.versoes.ramos(), self._ultima or self.vigia.ler())
        elif acao == "limpou":
            self.estado.configure(text=f"apaguei {len(dados['apagadas'])} versão(ões) velha(s)",
                                  fg=self.tema.texto_fraco)
            self._mostrar(self.versoes.ramos(), self._ultima or self.vigia.ler())

    def _log(self, texto):
        self.console.configure(state="normal")
        self.console.insert("end", str(texto).rstrip() + "\n")
        linhas_ = int(self.console.index("end-1c").split(".")[0])
        if linhas_ > 400:
            self.console.delete("1.0", f"{linhas_ - 400}.0")
        self.console.see("end")
        self.console.configure(state="disabled")

    # --- botoes -----------------------------------------------------
    def atualizar(self):
        def trabalho():
            resultado = self.vigia.olhar(testar=False, avisar=False, gravar=False, buscar=True)
            tabela = resultado.get("tabela")
            if tabela is None:
                if resultado.get("acao") == "ocupado":
                    tabela = self.vigia.ler()
                else:
                    raise ErroDeVersao(resultado.get("erro") or resultado.get("motivo") or "sem rede?")
            self._ultima = tabela
            return "lista", (self.versoes.ramos(), tabela)
        self._em_thread("buscando os ramos no GitHub…", trabalho)

    def _preparar_e_abrir(self, ref: str, rotulo: str):
        def passo(n, total, texto):
            self.fila.put(("progresso", n, total, texto))

        def trabalho():
            ficha = self.versoes.preparar(ref, progresso=passo, rotulo=rotulo)
            self.fila.put(("log", f"abrindo {ficha['sha'][:7]} ({ficha.get('modo')})…"))
            aberto = self.versoes.abrir(ficha["sha"])
            return "rodou", aberto
        self._em_thread(f"preparando {rotulo}…", trabalho)

    def rodar(self):
        linha = self._linha_escolhida()
        if not linha:
            messagebox.showinfo("Escolha uma versão", "Escolha uma linha da lista (ou cole um commit).")
            return
        self._preparar_e_abrir(linha["ref"], linha["valores"][0] if linha["tipo"] != "commit" else linha["ref"])

    def rodar_colado(self):
        ref = self.commit.get().strip()
        if not ref:
            messagebox.showinfo("Cole um commit", "Cole o hash de um commit (ou o nome de um ramo).")
            return
        self._preparar_e_abrir(ref, ref)

    def fixar(self):
        linha = self._linha_escolhida()
        if not linha:
            return
        ficha = (self.versoes.ler()["versoes"].get(linha["sha"]) or {})
        self.versoes.fixar(linha["sha"], not ficha.get("fixada"))
        self._mostrar(self.versoes.ramos(), self._ultima or self.vigia.ler())

    def copiar_comando(self):
        linha = self._linha_escolhida()
        a = (linha or {}).get("analise") or {}
        texto = a.get("comando") or (link_de_pr(linha["ref"]) if a.get("a_frente") else "")
        if not texto:
            messagebox.showinfo("Sem comando", "Esta versão não tem merge a fazer.")
            return
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append(texto)
        self.estado.configure(text=f"copiado: {texto}", fg=self.tema.texto_fraco)

    def limpar(self):
        fixadas = sum(1 for f in self.versoes.ler()["versoes"].values() if f.get("fixada"))
        if not messagebox.askyesno("Apagar versões velhas",
                                   f"Mantenho as {MANTER} usadas por último e as {fixadas} fixada(s); "
                                   "o resto (pasta, node_modules sem dono e HTML) sai do disco. "
                                   "Nada no GitHub muda. Continuar?"):
            return
        self._em_thread("apagando versões velhas…", lambda: ("limpou", self.versoes.limpar(MANTER)))

    def abrir_pasta(self):
        self.versoes.raiz.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self.versoes.raiz))                    # noqa: S606

    def fechar(self):
        for servidor in self.servidores:
            if servidor.poll() is None:
                matar_arvore(servidor.pid)
        self.raiz.destroy()


def abrir_janela() -> int:
    raiz = tk.Tk()
    Janela(raiz)
    raiz.mainloop()
    return 0
