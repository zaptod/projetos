# -*- coding: utf-8 -*-
"""A janela "Blue Lock — versoes": escolher a versao do jogo e abrir.

O que o atalho da Area de Trabalho abre (pythonw, sem console). Lista a main,
os ramos do GitHub dele (com o veredito do vigia de ramos, a data e o CI) e
as versoes ja preparadas; aceita um commit colado. "Rodar" prepara a versao
(pasta + npm ci se o lock for novo + build) mostrando o progresso e abre o
jogo numa janela VISIVEL do Chrome (perfil proprio do lancador).

A cara e a das janelas de trabalho do painel (`painel.estilo.OFICINA`):
sobria e densa, borda em vez de bloco de cor, acento so no que e clicavel.

A TELA DELE (medida pelo conferente, 19/10): 1920x1080 a 150% = 1280x720
logicos, ~680 uteis com a barra de tarefas. Tudo aqui cabe nisso: a lista
ROLA (barra empacotada antes da tabela), o veredito da lista e CURTO (a frase
inteira fica no detalhe) e o comando de merge tem linha propria logo abaixo
do veredito — antes ele era a ultima linha de um texto de 4 linhas e sumia.

O trabalho pesado roda numa thread e fala com a tela por uma FILA lida pelo
`after` da thread da interface — `after()` chamado de outra thread quebra o
Tk (memoria random-builds-reacoes-e-fluxo).
"""
from __future__ import annotations

import os
import queue
import re
import threading
import tkinter as tk
import tkinter.font as tkfont
from contextlib import ExitStack
from datetime import datetime
from tkinter import messagebox, ttk

from .ramos import VigiaDeRamos, link_de_pr
from .versoes import MANTER, ErroDeVersao, Versoes, matar_arvore

ICONE_DO_TIPO = {"vale": "✅", "espere": "⏳", "nao_vale": "❌", "olho": "⚠", "na_main": "✔"}
# (id, titulo, exemplo que tem de caber). A "versao" e a unica que estica:
# ela absorve a sobra e encolhe quando falta, sem empurrar a barra de rolagem
# para fora (19/10: 1115 px de colunas num quadro de 1106 deixavam a barra com 0).
COLUNAS = [("versao", "Versão", "fix/bachira-air-contact"), ("commit", "Commit", "face59dc"),
           ("data", "Data", "19/10 21:57"), ("veredito", "Veredito", "⏳ espere (contido no isagi-off-ba…)"),
           ("ci", "CI", "vermelho"), ("testes", "Testes aqui", "falhou 1770/1770"), ("pronta", "Pronta", "★ servidor")]
VEREDITO_MAX = 36           # caracteres do veredito da lista
ALTURA_UTIL = 680           # a tela dele, em pixels logicos uteis


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
    if ci.get("indisponivel"):
        return "?"                          # sem rede: NAO e "sem CI"
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


def apelido(ramo: str) -> str:
    """`fix/isagi-off-ball-20261020` -> `isagi-off-ball` (para caber na lista)."""
    curto = re.sub(r"^(feat|fix|chore|docs|refactor|test)/", "", ramo)
    curto = re.sub(r"-\d{8}$", "", curto)
    return curto if len(curto) <= 16 else curto[:15] + "…"


def veredito_curto(a: dict | None) -> str:
    """O veredito da LISTA: no maximo `VEREDITO_MAX` caracteres. A frase
    inteira (com o porque) fica no detalhe."""
    if not a:
        return "⏳ o vigia ainda não olhou"
    v = a.get("veredito") or {}
    codigo, tipo = v.get("codigo"), v.get("tipo") or "espere"
    icone = ICONE_DO_TIPO.get(tipo, "•")
    pontas = a.get("pontas") or []
    texto = {
        "vale": "vale o merge",
        "na_main": "já na main",
        "contido": f"espere (contido no {apelido(pontas[0])})" if pontas else "espere (contido)",
        "ci_rodando": "espere (CI rodando)",
        "ci_ilegivel": "espere (CI ilegível agora)",
        "sem_teste": "espere (teste na fila)",
        "ci_vermelho": "não vale (CI vermelho)",
        "teste_vermelho": "não vale (testes quebram)",
        "npm_ci": "não vale (npm ci falha)",
        "nao_ff": "precisa de olho (não é ff)",
        "conflito": "precisa de olho (conflito)",
        "ci_estranho": "precisa de olho (CI)",
    }.get(codigo, (v.get("texto") or "").replace("`", ""))
    frase = f"{icone} {texto}"
    return frase if len(frase) <= VEREDITO_MAX else frase[:VEREDITO_MAX - 1] + "…"


def acao_de_merge(linha: dict | None) -> dict:
    """O que a linha do merge mostra e se o botao copia: {texto, copiar, rotulo}.

    So o "vale" copia o comando e so o "precisa de olho" copia o link do PR;
    no "espere (contido)" o botao fica desligado e a linha diz de quem e o
    merge (antes copiava o link do PR do ramo de baixo)."""
    a = (linha or {}).get("analise") or {}
    if not linha or linha.get("tipo") == "main":
        return {"texto": "a main é a versão oficial: nada a juntar", "copiar": None, "rotulo": "Copiar"}
    if not a:
        return {"texto": "sem análise do vigia para esta versão", "copiar": None, "rotulo": "Copiar"}
    v = a.get("veredito") or {}
    if a.get("comando"):
        return {"texto": a["comando"], "copiar": a["comando"], "rotulo": "Copiar comando"}
    if v.get("codigo") == "contido" and a.get("pontas"):
        return {"texto": f"dê o merge do {a['pontas'][0]} (ele contém este)", "copiar": None,
                "rotulo": "Copiar comando"}
    if v.get("tipo") == "olho" and a.get("a_frente"):
        pr = link_de_pr(linha["ref"])
        return {"texto": f"abrir PR: {pr}", "copiar": pr, "rotulo": "Copiar link do PR"}
    if v.get("tipo") == "na_main":
        return {"texto": "já está na main: nada a fazer", "copiar": None, "rotulo": "Copiar"}
    return {"texto": "sem merge agora: " + (v.get("texto") or "").replace("`", ""), "copiar": None,
            "rotulo": "Copiar"}


def linhas(ramos_clone: list[dict], tabela: dict | None, registro: dict) -> list[dict]:
    """As linhas da tabela, na ordem: main, commits colados que estao
    preparados, ramos com coisa a decidir e ramos ja na main. Pura (o teste
    chama sem Tk)."""
    tabela = tabela or {}
    analise = {r["ramo"]: r for r in tabela.get("ramos") or []}
    versoes = registro.get("versoes") or {}

    def pronta(sha: str) -> str:
        ficha = versoes.get(sha) or {}
        marca = "★ " if ficha.get("fixada") else ""
        if ficha.get("modo") == "html":
            return marca + "sim"
        if ficha.get("modo") == "servidor":
            return marca + "servidor"
        return marca + ("pasta" if ficha else "")

    saida, vistos = [], set()
    for r in ramos_clone:
        sha, nome = r["sha"], r["ramo"]
        vistos.add(sha)
        a = analise.get(nome) if (analise.get(nome) or {}).get("sha") == sha else None
        if nome == "main":
            saida.append({"id": "ramo:main", "ref": "main", "sha": sha, "tipo": "main", "ordem": 0,
                          "valores": ("main", sha[:7], _hora(r.get("data")), "★ a versão oficial", "", "",
                                      pronta(sha)), "analise": None, "assunto": r.get("assunto", "")})
            continue
        tipo = ((a or {}).get("veredito") or {}).get("tipo") or "espere"
        ci, testes = (_ci(a), _testes(a)) if a else ("", "")
        saida.append({"id": f"ramo:{nome}", "ref": nome, "sha": sha, "tipo": tipo,
                      "ordem": 3 if tipo == "na_main" else 2,
                      "valores": (nome, sha[:7], _hora(r.get("data")), veredito_curto(a), ci, testes, pronta(sha)),
                      "analise": a, "assunto": r.get("assunto", "")})
    for sha, ficha in sorted(versoes.items(), key=lambda par: par[1].get("usada_em") or "", reverse=True):
        if sha in vistos:
            continue
        saida.append({"id": f"commit:{sha}", "ref": sha, "sha": sha, "tipo": "commit", "ordem": 1,
                      "valores": (f"commit {sha[:7]}", sha[:7], _hora(ficha.get("data")), "colado",
                                  "", "", pronta(sha)), "analise": None,
                      "assunto": f"{ficha.get('assunto', '')} (era {ficha.get('ref', '?')})"})
    saida.sort(key=lambda linha: linha["ordem"])
    return saida


def titulo_do_detalhe(linha: dict | None) -> tuple[str, str]:
    """(primeira linha, veredito por extenso) do cartao de baixo."""
    if not linha:
        return "Escolha uma versão na lista (ou cole um commit) e clique em Rodar.", ""
    topo = f"{linha['valores'][0]}  ·  {linha['sha'][:10]}  ·  {linha.get('assunto', '')}"
    a = linha.get("analise")
    if linha.get("tipo") == "main":
        return topo, "A versão oficial dele (origin/main)."
    if not a:
        return topo, "Sem análise do vigia de ramos para esta cabeça (clique em Atualizar lista)."
    v = a.get("veredito") or {}
    return topo, f"{ICONE_DO_TIPO.get(v.get('tipo'), '•')} {(v.get('texto') or '').replace('`', '')}"


def detalhe(linha: dict | None) -> str:
    """O resto do cartao (rola): relacao com a main, areas e commits."""
    if not linha:
        return ""
    a = linha.get("analise")
    if not a:
        return ""
    partes = [f"Relação com a main: +{a.get('a_frente', 0)} à frente, -{a.get('atras', 0)} atrás"
              + (", fast-forward" if a.get("ff") and a.get("a_frente") else "")]
    if a.get("contem"):
        partes.append("Contém os ramos: " + ", ".join(a["contem"]))
    if a.get("areas"):
        partes.append(f"Mexe em {a.get('arquivos', 0)} arquivo(s): "
                      + ", ".join(f"{k} {n}" for k, n in a["areas"].items()))
    if a.get("commits"):
        partes.append("Commits:")
        partes += [f"  • {c.get('hash')} {c.get('assunto', '')[:100]}" for c in a["commits"][:30]]
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
        self.abertas: set[str] = set()          # shas abertos nesta janela: a limpeza nao toca
        self._seguras = ExitStack()             # e a trava de cada um, contra o vigia de outro processo
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
        largura = min(1180, r.winfo_screenwidth() - 40)
        # ALTURA_UTIL menos a barra de titulo do Windows (~32) e uma folga.
        altura = min(ALTURA_UTIL - 50, r.winfo_screenheight() - 90)
        r.geometry(f"{largura}x{altura}+20+4")
        r.minsize(900, 480)
        o.aplicar_ttk(r)
        r.protocol("WM_DELETE_WINDOW", self.fechar)
        try:
            from .versoes import caminho_do_icone
            if caminho_do_icone().is_file():
                r.iconbitmap(default=str(caminho_do_icone()))
        except (tk.TclError, OSError):
            pass
        self.letra = tkfont.Font(root=r, font=t.letra("corpo"))

        topo = tk.Frame(r, bg=t.fundo)
        topo.pack(fill="x")
        titulo = o.rotulo(topo, "Blue Lock — versões", papel="titulo", peso="bold")
        titulo.pack(anchor="w", padx=E["secao"], pady=(E["normal"], 0))
        self.resumo = o.legenda(topo, "")
        self.resumo.pack(anchor="w", padx=E["secao"], pady=(0, E["meio"]))

        # O RODAPE SE EMPACOTA ANTES DA TABELA, por baixo: empacotado depois,
        # o cartao com `expand` comia a altura e os botoes sumiam.
        rodape = tk.Frame(r, bg=t.fundo)
        rodape.pack(side="bottom", fill="x", padx=E["secao"], pady=(0, E["normal"]))
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
        moldura, self.commit = o.campo(botoes, "Colar um commit ou ramo:", largura=24)
        moldura.pack(side="left", padx=(E["muito"], 0))
        o.botao(botoes, "Rodar este", self.rodar_colado).pack(side="left", padx=(E["meio"], 0))
        self.b_limpar = o.botao(botoes, "Apagar versões velhas", self.limpar, tipo="perigo")
        self.b_limpar.pack(side="right")
        o.botao(botoes, "Abrir pasta", self.abrir_pasta).pack(side="right", padx=(0, E["meio"]))

        # O detalhe (tambem por baixo, antes da lista).
        cartao_det = o.cartao(r)
        cartao_det.pack(side="bottom", fill="x", padx=E["secao"], pady=(0, E["meio"]))
        corpo = cartao_det.corpo
        fundo = t.superficie
        self.det_topo = o.rotulo(corpo, "", cor="texto", bg=fundo, peso="bold")
        self.det_topo.pack(fill="x")
        self.det_veredito = o.rotulo(corpo, "", cor="texto", bg=fundo, justify="left", wraplength=1080)
        self.det_veredito.pack(fill="x", pady=(E["pouco"], 0))
        linha_merge = tk.Frame(corpo, bg=fundo)
        linha_merge.pack(fill="x", pady=(E["meio"], E["meio"]))
        o.rotulo(linha_merge, "Merge:", cor="texto_fraco", bg=fundo).pack(side="left", padx=(0, E["meio"]))
        self.b_comando = o.botao(linha_merge, "Copiar comando", self.copiar_comando, compacto=True)
        self.b_comando.pack(side="right")
        self.merge = tk.StringVar()
        self.campo_merge = tk.Entry(linha_merge, textvariable=self.merge, state="readonly",
                                    readonlybackground=t.console_fundo, fg=t.acento_forte,
                                    font=t.letra("mono", "bold"), relief="flat", highlightthickness=1,
                                    highlightbackground=t.borda)
        self.campo_merge.pack(side="left", fill="x", expand=True, ipady=3, padx=(0, E["meio"]))
        quadro_texto = tk.Frame(corpo, bg=fundo)
        quadro_texto.pack(fill="x")
        barra_texto = ttk.Scrollbar(quadro_texto, orient="vertical")
        barra_texto.pack(side="right", fill="y")
        self.texto = tk.Text(quadro_texto, height=3, bg=fundo, fg=t.texto_fraco, relief="flat",
                             font=t.letra("legenda"), wrap="word", highlightthickness=0, bd=0,
                             yscrollcommand=barra_texto.set)
        barra_texto.configure(command=self.texto.yview)
        self.texto.pack(side="left", fill="x", expand=True)

        cartao = o.cartao(r)
        cartao.pack(fill="both", expand=True, padx=E["secao"], pady=(0, E["meio"]))
        quadro = tk.Frame(cartao.corpo, bg=t.superficie)
        quadro.pack(fill="both", expand=True)
        ttk.Style(r).configure("Treeview", rowheight=self.letra.metrics("linespace") + 6)
        # A BARRA PRIMEIRO, a direita: empacotada depois da tabela, ela ficava
        # com 0 px quando as colunas pediam mais que o quadro.
        self.rolagem = ttk.Scrollbar(quadro, orient="vertical")
        self.rolagem.pack(side="right", fill="y")
        colunas = [(c, titulo_, self.letra.measure(exemplo) + 18 if c != "versao" else 160, "w")
                   for c, titulo_, exemplo in COLUNAS]
        self.tabela = o.tabela(quadro, colunas, altura=8, estica="versao")
        self.tabela.column("versao", minwidth=120)
        self.tabela.configure(yscrollcommand=self.rolagem.set)
        self.rolagem.configure(command=self.tabela.yview)
        self.tabela.pack(side="left", fill="both", expand=True)
        self.tabela.tag_configure("na_main", foreground=t.texto_apagado)
        self.tabela.tag_configure("vale", foreground=t.ok)
        self.tabela.tag_configure("nao_vale", foreground=t.erro)
        self.tabela.tag_configure("olho", foreground=t.aviso)
        self.tabela.tag_configure("main", foreground=t.acento_forte)
        self.tabela.bind("<<TreeviewSelect>>", lambda _e: self._escolheu())
        self.tabela.bind("<Double-1>", lambda _e: self.rodar())
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
        self._escrever_detalhe(self._linha_escolhida())
        main = (tabela or {}).get("main") or {}
        abertos = [r for r in (tabela or {}).get("ramos") or [] if r.get("a_frente")]
        texto = (f"{len(self.linhas)} versões · {len(abertos)} ramo(s) fora da main · "
                 f"vigia olhou {_hora((tabela or {}).get('olhado_em')) or 'nunca'}")
        if main.get("sha"):
            texto = f"main {main['sha'][:7]} · " + texto
        self.resumo.configure(text=texto)

    def _linha_escolhida(self):
        escolha = self.tabela.selection()
        if not escolha:
            return None
        return next((linha for linha in self.linhas if linha["id"] == escolha[0]), None)

    def _escolheu(self):
        self._escrever_detalhe(self._linha_escolhida())

    def _escrever_detalhe(self, linha):
        topo, veredito = titulo_do_detalhe(linha)
        self.det_topo.configure(text=topo)
        self.det_veredito.configure(text=veredito)
        merge = acao_de_merge(linha)
        self.merge.set(merge["texto"])
        self.b_comando.configure(text=merge["rotulo"], state="normal" if merge["copiar"] else "disabled")
        # So o que se COLA tem cara de comando; a dica ("de o merge do X") e apagada.
        t = self.tema
        self.campo_merge.configure(fg=t.acento_forte if merge["copiar"] else t.texto_fraco,
                                   font=t.letra("mono", "bold") if merge["copiar"] else t.letra("corpo"))
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
            self._proteger(dados.get("sha"))
            self.estado.configure(text=f"aberto: {dados['url']}", fg=self.tema.ok)
            self._mostrar(self.versoes.ramos(), self._ultima or self.vigia.ler())
        elif acao == "limpou":
            self.estado.configure(text=f"apaguei {len(dados['apagadas'])} versão(ões) velha(s)",
                                  fg=self.tema.texto_fraco)
            self._mostrar(self.versoes.ramos(), self._ultima or self.vigia.ler())

    def _proteger(self, sha: str | None) -> None:
        """A versao aberta nao sai do disco enquanto a janela vive: entra nos
        `protegidos` da limpeza daqui e segura a trava dela (a limpeza do
        vigia, em outro processo, pula versao com trava ocupada)."""
        if not sha or sha in self.abertas:
            return
        self.abertas.add(sha)
        try:
            self._seguras.enter_context(self.versoes.trava(f"bluelock_versao_{sha[:12]}"))
        except Exception:                                       # noqa: BLE001
            pass

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
            return "rodou", dict(aberto, sha=ficha["sha"])
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
        merge = acao_de_merge(self._linha_escolhida())
        if not merge["copiar"]:
            self.estado.configure(text=merge["texto"], fg=self.tema.texto_fraco)
            return
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append(merge["copiar"])
        self.estado.configure(text=f"copiado: {merge['copiar']}", fg=self.tema.texto_fraco)

    def limpar(self):
        fixadas = sum(1 for f in self.versoes.ler()["versoes"].values() if f.get("fixada"))
        if not messagebox.askyesno("Apagar versões velhas",
                                   f"Mantenho as {MANTER} usadas por último, as {fixadas} fixada(s) e as "
                                   f"{len(self.abertas)} aberta(s) agora; o resto (pasta, node_modules sem "
                                   "dono e HTML) sai do disco. Nada no GitHub muda. Continuar?"):
            return
        protegidos = set(self.abertas)
        self._em_thread("apagando versões velhas…",
                        lambda: ("limpou", self.versoes.limpar(MANTER, protegidos=protegidos)))

    def abrir_pasta(self):
        self.versoes.raiz.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self.versoes.raiz))                    # noqa: S606

    def fechar(self):
        for servidor in self.servidores:
            if servidor.poll() is None:
                matar_arvore(servidor.pid)
        self._seguras.close()
        self.raiz.destroy()


def abrir_janela() -> int:
    raiz = tk.Tk()
    Janela(raiz)
    raiz.mainloop()
    return 0
