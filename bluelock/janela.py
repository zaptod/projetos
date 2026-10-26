# -*- coding: utf-8 -*-
"""A janela "Blue Lock — versoes": escolher a versao do jogo e jogar.

O que o atalho da Area de Trabalho abre (pythonw, sem console). Lista a main,
os ramos do GitHub dele (com o veredito do vigia de ramos, a data e o CI) e
as versoes ja preparadas; aceita um commit colado. "Jogar" prepara a versao
(pasta + npm ci se o lock for novo + build) mostrando o progresso e abre o
jogo numa janela VISIVEL do Chrome (perfil proprio do lancador).

A CARA (26/10): identidade do jogo — verde-campo com acento lima, o do "BL"
(`bluelock/estilo.py`) — e nao mais a tabela de 7 colunas. Cada versao e um
cartao com nome amigavel ("Bachira · roulette choreography"), data relativa
e selos (VERSAO PRINCIPAL, NOVA, PREPARADA, FIXADA); a da direita mostra a
escolhida com o botao grande "Jogar". Veredito do vigia, comando de merge e
commits ficam em "Detalhes tecnicos" (recolhido), o log tecnico na gaveta do
rodape. O que sobra de jargao e o hash curto, discreto.

A TELA DELE (medida pelo conferente, 19/10): 1920x1080 a 150% = 1280x720
logicos, ~680 uteis com a barra de tarefas. Tudo aqui cabe nisso: a lista
ROLA (quadro com barra propria), o painel da direita rola nos detalhes e o
rodape e empacotado ANTES do corpo, senao o `pack` corta em silencio.

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
from contextlib import ExitStack
from datetime import datetime
from tkinter import messagebox

from . import estilo
from .estilo import CORES, Barra, ESPACO, Logo, Pilula, Rolagem, data_relativa, e_de_hoje, letra, nome_amigavel, selo
from .ramos import VigiaDeRamos, link_de_pr
from .versoes import MANTER, ErroDeVersao, Versoes, matar_arvore

ICONE_DO_TIPO = {"vale": "✅", "espere": "⏳", "nao_vale": "❌", "olho": "⚠", "na_main": "✔"}
VEREDITO_MAX = 36           # caracteres do veredito curto (o da linha do vigia)
ALTURA_UTIL = 680           # a tela dele, em pixels logicos uteis
LARGURA_PAINEL = 368        # o painel da direita (a escolhida + Jogar)
BUSCA_DICA = "Buscar por nome, personagem ou commit…"
FILTROS = [("todas", "Todas"), ("novas", "Novas"), ("preparadas", "Preparadas"), ("fixadas", "Fixadas")]
# tipo do veredito -> (frase de gente, cor). So o que pede acao aparece no cartao.
ETIQUETA_DO_TIPO = {"vale": ("pronta para juntar", "ok"), "nao_vale": ("com problema", "erro"),
                    "olho": ("precisa de olho", "aviso"), "na_main": ("já na principal", "texto_apagado")}


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

# --- o que a TELA mostra (puro: o teste chama sem Tk) -----------------
def preparada(linha: dict) -> bool:
    return bool(linha["valores"][6].replace("★", "").strip())


def fixada(linha: dict) -> bool:
    return "★" in linha["valores"][6]


def e_nova(linha: dict, iso: dict, agora: datetime | None = None) -> bool:
    return linha["tipo"] not in ("main", "commit", "na_main") and e_de_hoje(iso.get(linha["sha"]), agora)


def filtrar(todas: list[dict], filtro: str = "todas", busca: str = "", iso: dict | None = None,
            agora: datetime | None = None) -> list[dict]:
    """As linhas que o filtro (chip) e a busca deixam passar. A busca acha pelo
    nome amigavel, pelo ramo, pelo commit e pelo assunto."""
    iso = iso or {}
    palavras = busca.lower().split()
    saida = []
    for linha in todas:
        if filtro == "novas" and not e_nova(linha, iso, agora):
            continue
        if filtro == "preparadas" and not preparada(linha):
            continue
        if filtro == "fixadas" and not fixada(linha):
            continue
        palheiro = " ".join([nome_amigavel(linha["ref"])[0], linha["ref"], linha["sha"], linha.get("assunto", "")]).lower()
        if all(p in palheiro for p in palavras):
            saida.append(linha)
    return saida


def curto(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + "…"


class Janela:
    def __init__(self, raiz, *, versoes: Versoes | None = None, vigia: VigiaDeRamos | None = None,
                 atualizar_ao_abrir: bool = True):
        self.raiz = raiz
        self.fila: queue.Queue = queue.Queue()
        self.versoes = versoes or Versoes(log=lambda texto: self.fila.put(("log", texto)))
        if versoes is not None:
            versoes.log = lambda texto: self.fila.put(("log", texto))
        self.vigia = vigia or VigiaDeRamos(self.versoes, log=lambda texto: self.fila.put(("log", texto)))
        self.servidores = []
        self.abertas: set[str] = set()          # shas abertos nesta janela: a limpeza nao toca
        self._seguras = ExitStack()             # e a trava de cada um, contra o vigia de outro processo
        self._ultima: dict | None = None        # a ultima analise dos ramos (Atualizar)
        self.linhas: list[dict] = []            # todas
        self.visiveis: list[dict] = []          # as que o filtro e a busca deixam
        self._iso: dict[str, str] = {}          # sha -> data ISO (a coluna "Data" virou "ha 2 h")
        self._registro: dict = {}
        self._tabela: dict = {}
        self._cartoes: dict[str, dict] = {}
        self._sel: str | None = None
        self._filtro = "todas"
        self._dica_ligada = False
        self.ocupado = False
        self._op = ""
        self._montar()
        self._mostrar(self.versoes.ramos() if self.versoes.tem_clone() else [], self.vigia.ler())
        self.raiz.after(100, self._drenar)
        if atualizar_ao_abrir:
            self.atualizar()

    # --- montagem ---------------------------------------------------
    def _montar(self):
        r, c, E = self.raiz, CORES, ESPACO
        r.title("Blue Lock — versões")
        r.configure(bg=c["fundo"])
        largura = min(1180, r.winfo_screenwidth() - 40)
        # ALTURA_UTIL menos a barra de titulo do Windows (~32) e uma folga.
        altura = min(ALTURA_UTIL - 50, r.winfo_screenheight() - 90)
        r.geometry(f"{largura}x{altura}+20+4")
        r.minsize(820, 480)
        estilo.aplicar_ttk(r)
        r.protocol("WM_DELETE_WINDOW", self.fechar)
        try:
            from .versoes import caminho_do_icone
            if caminho_do_icone().is_file():
                r.iconbitmap(default=str(caminho_do_icone()))
        except (tk.TclError, OSError):
            pass
        self.letra = tk_font(r, "corpo")

        # ---- cabecalho
        topo = tk.Frame(r, bg=c["fundo"])
        topo.pack(fill="x", padx=E["secao"], pady=(E["muito"], E["normal"]))
        Logo(topo, 44).pack(side="left")
        nome = tk.Frame(topo, bg=c["fundo"])
        nome.pack(side="left", padx=(E["normal"], 0))
        tk.Label(nome, text="Blue Lock", bg=c["fundo"], fg=c["texto"], font=letra("titulo")).pack(anchor="w")
        self.resumo = tk.Label(nome, text="", bg=c["fundo"], fg=c["texto_fraco"], font=letra("legenda"))
        self.resumo.pack(anchor="w")
        self.b_atualizar = Pilula(topo, "↻  Atualizar", self.atualizar, bg=c["fundo"])
        self.b_atualizar.pack(side="right")

        # ---- aviso (vazio = altura 0): sem rede, erro...
        self.zona_aviso = tk.Frame(r, bg=c["fundo"])
        self.zona_aviso.pack(fill="x", padx=E["secao"])

        # ---- rodape: EMPACOTADO ANTES do corpo, por baixo (o corpo expande)
        rodape = tk.Frame(r, bg=c["fundo"])
        rodape.pack(side="bottom", fill="x", padx=E["secao"], pady=(0, E["normal"]))
        self.gaveta = tk.Frame(rodape, bg=c["fundo"])           # o log tecnico, recolhido
        self.console = tk.Text(self.gaveta, height=5, bg=c["superficie"], fg=c["texto_fraco"], relief="flat",
                               font=letra("mono"), wrap="none", highlightthickness=1,
                               highlightbackground=c["borda"], bd=0)
        self.console.pack(fill="x", pady=(0, E["meio"]))
        self._gaveta_aberta = False
        self.barra = _barra(rodape)
        self.barra.pack(side="bottom", fill="x", pady=(E["meio"], 0))
        linha_baixo = tk.Frame(rodape, bg=c["fundo"])
        linha_baixo.pack(side="bottom", fill="x")
        self.estado = tk.Label(linha_baixo, text="pronto", bg=c["fundo"], fg=c["texto_fraco"], font=letra("corpo"),
                               anchor="w")
        self.estado.pack(side="left")
        self.b_limpar = Pilula(linha_baixo, "Apagar versões velhas", self.limpar, tipo="perigo", papel="legenda",
                               padx=12, pady=4)
        self.b_limpar.pack(side="right")
        Pilula(linha_baixo, "Abrir pasta", self.abrir_pasta, tipo="fantasma", papel="legenda", padx=12,
               pady=4).pack(side="right", padx=(0, E["meio"]))
        self.b_log = Pilula(linha_baixo, "Log técnico ▸", self.alternar_console, tipo="fantasma", papel="legenda",
                            padx=12, pady=4)
        self.b_log.pack(side="right", padx=(0, E["meio"]))
        self._linha_baixo = linha_baixo

        # ---- barra de busca e filtros
        ferramentas = tk.Frame(r, bg=c["fundo"])
        ferramentas.pack(fill="x", padx=E["secao"], pady=(0, E["meio"]))
        moldura = tk.Frame(ferramentas, bg=c["superficie"], highlightthickness=1, highlightbackground=c["borda_forte"],
                           highlightcolor=c["acento"])
        moldura.pack(side="left")
        self.busca = tk.StringVar()
        self.campo_busca = tk.Entry(moldura, textvariable=self.busca, width=36, bg=c["superficie"], fg=c["texto"],
                                    insertbackground=c["acento"], relief="flat", font=letra("corpo"),
                                    highlightthickness=0)
        self.campo_busca.pack(padx=E["meio"], pady=E["meio"])
        self.campo_busca.bind("<FocusIn>", lambda _e: self._dica(False))
        self.campo_busca.bind("<FocusOut>", lambda _e: self._dica(True))
        self.busca.trace_add("write", lambda *_a: hasattr(self, "lista") and self._redesenhar())
        self._dica(True)
        self.chips = {}
        for chave, texto in FILTROS:
            chip = Pilula(ferramentas, texto, lambda k=chave: self.filtrar_por(k), tipo="chip", papel="legenda",
                          padx=12, pady=6)
            chip.pack(side="left", padx=(E["meio"], 0))
            self.chips[chave] = chip
        self.chips["todas"].marcar(True)
        self.contagem = tk.Label(ferramentas, text="", bg=c["fundo"], fg=c["texto_apagado"], font=letra("legenda"))
        self.contagem.pack(side="right")

        # ---- corpo: a lista (rola) e o painel da escolhida
        corpo = tk.Frame(r, bg=c["fundo"])
        corpo.pack(fill="both", expand=True, padx=E["secao"], pady=(0, E["normal"]))
        self._montar_painel(corpo)
        self.lista = Rolagem(corpo, c["fundo"])
        self.lista.pack(side="left", fill="both", expand=True)
        self._escrever_detalhe(None)

    def _montar_painel(self, pai):
        c, E = CORES, ESPACO
        painel = tk.Frame(pai, bg=c["superficie"], width=LARGURA_PAINEL, highlightthickness=1,
                          highlightbackground=c["borda"])
        painel.pack(side="right", fill="y", padx=(E["muito"], 0))
        painel.pack_propagate(False)
        # O painel INTEIRO rola: com os detalhes e o log abertos ele nao cabe e o
        # `pack` cortaria em silencio o que viesse por ultimo (Fixar, Detalhes).
        self.rolagem_painel = Rolagem(painel, c["superficie"])
        self.rolagem_painel.pack(fill="both", expand=True)
        p = tk.Frame(self.rolagem_painel.corpo, bg=c["superficie"])
        p.pack(fill="both", expand=True, padx=E["muito"], pady=E["muito"])
        fundo = c["superficie"]
        self._painel = p
        self._largura_texto = LARGURA_PAINEL - 2 * E["muito"] - 24

        # em cima: quem e a escolhida
        self.det_selos = tk.Frame(p, bg=fundo)
        self.det_selos.pack(fill="x", anchor="w", pady=(0, E["meio"]))
        self.det_topo = tk.Label(p, text="", bg=fundo, fg=c["texto"], font=letra("destaque"), anchor="w",
                                 justify="left", wraplength=self._largura_texto)
        self.det_topo.pack(fill="x")
        self.det_meta = tk.Label(p, text="", bg=fundo, fg=c["texto_fraco"], font=letra("legenda"), anchor="w")
        self.det_meta.pack(fill="x", pady=(E["pouco"], 0))
        self.det_assunto = tk.Label(p, text="", bg=fundo, fg=c["texto_fraco"], font=letra("corpo"), anchor="w",
                                    justify="left", wraplength=self._largura_texto)
        self.det_assunto.pack(fill="x", pady=(E["meio"], E["normal"]))
        self.b_rodar = Pilula(p, "▶  Jogar", self.rodar, tipo="primario", papel="secao", bg=fundo, pady=12)
        self.b_rodar.pack(fill="x")
        self.det_estado = tk.Label(p, text="", bg=fundo, fg=c["texto_fraco"], font=letra("legenda"), anchor="w",
                                   justify="left", wraplength=self._largura_texto)
        self.det_estado.pack(fill="x", pady=(E["meio"], E["meio"]))
        self.b_fixar = Pilula(p, "☆  Fixar esta versão", self.fixar, tipo="fantasma", papel="legenda", bg=fundo,
                              pady=6)
        self.b_fixar.pack(fill="x")

        # os detalhes tecnicos: recolhidos (o merge, o veredito do vigia, os commits)
        self.b_detalhes = tk.Label(p, text="Detalhes técnicos ▸", bg=fundo, fg=c["acento"], font=letra("legenda"),
                                   anchor="w", cursor="hand2")
        self.b_detalhes.pack(fill="x", pady=(E["normal"], 0))
        self.b_detalhes.bind("<Button-1>", lambda _e: self.alternar_detalhes())
        self.zona_det = tk.Frame(p, bg=fundo)
        d = self.zona_det
        self.det_veredito = tk.Label(d, text="", bg=fundo, fg=c["texto"], font=letra("corpo"), anchor="w",
                                     justify="left", wraplength=self._largura_texto)
        self.det_veredito.pack(fill="x", pady=(E["meio"], 0))
        linha_merge = tk.Frame(d, bg=fundo)
        linha_merge.pack(fill="x", pady=(E["meio"], E["meio"]))
        tk.Label(linha_merge, text="Merge", bg=fundo, fg=c["texto_apagado"], font=letra("legenda")).pack(anchor="w")
        self.merge = tk.StringVar()
        self.campo_merge = tk.Entry(linha_merge, textvariable=self.merge, state="readonly", width=10,
                                    readonlybackground=c["fundo"], fg=c["acento"], font=letra("mono", "bold"),
                                    relief="flat", highlightthickness=1, highlightbackground=c["borda"])
        self.campo_merge.pack(fill="x", ipady=3, pady=(E["pouco"], E["pouco"]))
        self.b_comando = Pilula(linha_merge, "Copiar comando", self.copiar_comando, bg=fundo, papel="legenda",
                                padx=12, pady=5)
        self.b_comando.pack(anchor="e")
        self.texto = tk.Text(d, height=3, bg=fundo, fg=c["texto_fraco"], relief="flat", font=letra("legenda"),
                             wrap="word", highlightthickness=0, bd=0, width=10)
        self.texto.pack(fill="x")
        self._detalhes_abertos = False

        # o commit colado, por ultimo
        colar = tk.Frame(p, bg=fundo)
        colar.pack(fill="x", pady=(E["muito"], 0))
        tk.Label(colar, text="Outro commit ou ramo", bg=fundo, fg=c["texto_fraco"], font=letra("legenda")
                 ).pack(anchor="w", pady=(0, E["pouco"]))
        linha_colar = tk.Frame(colar, bg=fundo)
        linha_colar.pack(fill="x")
        moldura = tk.Frame(linha_colar, bg=c["fundo"], highlightthickness=1, highlightbackground=c["borda_forte"],
                           highlightcolor=c["acento"])
        moldura.pack(side="left", fill="x", expand=True)
        self.commit = tk.Entry(moldura, width=12, bg=c["fundo"], fg=c["texto"], insertbackground=c["acento"],
                               relief="flat", font=letra("mono"), highlightthickness=0)
        self.commit.pack(fill="x", padx=E["meio"], pady=E["meio"])
        self.b_colado = Pilula(linha_colar, "Jogar este", self.rodar_colado, bg=fundo, papel="legenda", padx=12,
                               pady=7)
        self.b_colado.pack(side="right", padx=(E["meio"], 0))

    # --- pequenos ---------------------------------------------------
    def _dica(self, ligar: bool):
        """O texto-dica da busca (some ao focar; volta se ficar vazia)."""
        if ligar and not self.busca.get():
            self._dica_ligada = True
            self.busca.set(BUSCA_DICA)
            self.campo_busca.configure(fg=CORES["texto_apagado"])
        elif not ligar and self._dica_ligada:
            self._dica_ligada = False
            self.busca.set("")
            self.campo_busca.configure(fg=CORES["texto"])

    def _termo(self) -> str:
        return "" if self._dica_ligada else self.busca.get().strip()

    def alternar_console(self):
        self._gaveta_aberta = not self._gaveta_aberta
        if self._gaveta_aberta:
            self.gaveta.pack(side="bottom", fill="x", after=self._linha_baixo)
        else:
            self.gaveta.pack_forget()
        self.b_log.configure(text="Log técnico ▾" if self._gaveta_aberta else "Log técnico ▸")

    def alternar_detalhes(self, abrir: bool | None = None):
        self._detalhes_abertos = (not self._detalhes_abertos) if abrir is None else abrir
        if self._detalhes_abertos:
            self.zona_det.pack(fill="x", pady=(ESPACO["meio"], 0), after=self.b_detalhes)
        else:
            self.zona_det.pack_forget()
        self.b_detalhes.configure(text="Detalhes técnicos ▾" if self._detalhes_abertos else "Detalhes técnicos ▸")

    def filtrar_por(self, chave: str):
        self._filtro = chave
        for k, chip in self.chips.items():
            chip.marcar(k == chave)
        self._redesenhar()

    # --- aviso (sem rede, erro) -------------------------------------
    def _aviso(self, texto: str, nivel: str = "aviso"):
        c, E = CORES, ESPACO
        self._sem_aviso()
        fundo = c["erro_fundo"] if nivel == "erro" else c["aviso_fundo"]
        cor = c["erro"] if nivel == "erro" else c["aviso"]
        faixa = tk.Frame(self.zona_aviso, bg=fundo, highlightthickness=1, highlightbackground=cor)
        faixa.pack(fill="x", pady=(0, E["meio"]))
        self.aviso_texto = tk.Label(faixa, text=texto, bg=fundo, fg=cor, font=letra("corpo"), anchor="w",
                                    justify="left", wraplength=900)
        self.aviso_texto.pack(side="left", padx=E["normal"], pady=E["meio"])
        ver = tk.Label(faixa, text="ver o log", bg=fundo, fg=cor, font=letra("legenda", "bold"), cursor="hand2")
        ver.pack(side="right", padx=E["normal"])
        ver.bind("<Button-1>", lambda _e: self._abrir_log())

    def _sem_aviso(self):
        for w in self.zona_aviso.winfo_children():
            w.destroy()

    def _abrir_log(self):
        if not self._gaveta_aberta:
            self.alternar_console()

    # --- lista ------------------------------------------------------
    def _mostrar(self, ramos_clone, tabela):
        escolhido = self._linha_escolhida()
        self._registro = self.versoes.ler()
        self._tabela = tabela or {}
        self.linhas = linhas(ramos_clone, tabela, self._registro)
        self._iso = {f["sha"]: f.get("data") for f in (self._registro.get("versoes") or {}).values() if f.get("data")}
        self._iso.update({r["sha"]: r.get("data") for r in ramos_clone if r.get("data")})
        if escolhido and any(linha["id"] == escolhido["id"] for linha in self.linhas):
            self._sel = escolhido["id"]
        else:
            self._sel = self.linhas[0]["id"] if self.linhas else None
        main = self._tabela.get("main") or {}
        novas = sum(1 for linha in self.linhas if e_nova(linha, self._iso))
        partes = []
        if main.get("sha"):
            partes.append(f"principal {main['sha'][:7]}")
        partes.append(f"{novas} nova{'s' if novas != 1 else ''} hoje" if novas else "nada novo hoje")
        olhado = data_relativa(self._tabela.get("olhado_em"))
        partes.append(f"ramos conferidos {olhado}" if olhado else "ramos ainda não conferidos")
        self.resumo.configure(text=" · ".join(partes))
        self._redesenhar()

    def _redesenhar(self):
        self.visiveis = filtrar(self.linhas, self._filtro, self._termo(), self._iso)
        corpo = self.lista.corpo
        for w in corpo.winfo_children():
            w.destroy()
        self._cartoes = {}
        if not self.visiveis:
            self._vazio(corpo)
        for linha in self.visiveis:
            self._cartao(corpo, linha)
        n, total = len(self.visiveis), len(self.linhas)
        self.contagem.configure(text=f"{n} de {total} versões" if n != total else f"{total} versões")
        if self.visiveis and (self._sel not in self._cartoes):
            self._sel = self.visiveis[0]["id"]
        self._pintar()
        self._escrever_detalhe(self._linha_escolhida())
        self.lista.canvas.yview_moveto(0)
        if self._sel in self._cartoes:
            self.raiz.after(60, self._ver_escolhida)

    def _ver_escolhida(self):
        try:
            if self._sel in self._cartoes:
                self.lista.ver(self._cartoes[self._sel]["quadro"])
        except tk.TclError:
            pass

    def _vazio(self, pai):
        """Lista vazia: sem o jogo baixado, ou o filtro nao achou nada."""
        c, E = CORES, ESPACO
        caixa = tk.Frame(pai, bg=c["fundo"])
        caixa.pack(fill="x", pady=E["pagina"])
        sem_clone = not self.linhas
        tk.Label(caixa, text="Ainda não tenho as versões do jogo" if sem_clone else "Nenhuma versão encontrada",
                 bg=c["fundo"], fg=c["texto"], font=letra("secao")).pack()
        tk.Label(caixa, text=("Clique em Atualizar para buscar as versões no GitHub." if sem_clone else
                              "Tente outra palavra, ou mostre todas."),
                 bg=c["fundo"], fg=c["texto_fraco"], font=letra("corpo")).pack(pady=(E["pouco"], E["muito"]))
        if sem_clone:
            Pilula(caixa, "↻  Atualizar", self.atualizar, tipo="primario", bg=c["fundo"]).pack()
        else:
            Pilula(caixa, "Limpar busca e filtros", self._limpar_busca, bg=c["fundo"]).pack()

    def _limpar_busca(self):
        self._dica_ligada = False
        self.busca.set("")
        self._dica(True)
        self.filtrar_por("todas")

    def _cartao(self, pai, linha: dict):
        c, E = CORES, ESPACO
        iid = linha["id"]
        nome, tipo_ramo = nome_amigavel(linha["ref"])
        quadro = tk.Frame(pai, bg=c["superficie"], highlightthickness=1, highlightbackground=c["borda"], cursor="hand2")
        quadro.pack(fill="x", pady=(0, E["pouco"]), padx=(0, E["meio"]))
        marca = tk.Frame(quadro, bg=c["superficie"], width=4)
        marca.pack(side="left", fill="y")
        miolo = tk.Frame(quadro, bg=c["superficie"])
        miolo.pack(side="left", fill="both", expand=True, padx=E["normal"], pady=E["meio"])
        miolo.columnconfigure(0, weight=1)
        apagada = linha["tipo"] == "na_main"
        n = tk.Label(miolo, text=curto(nome, 38), bg=c["superficie"], fg=c["texto_apagado"] if apagada else c["texto"],
                     font=letra("nome"), anchor="w")
        n.grid(row=0, column=0, sticky="w")
        selos = tk.Frame(miolo, bg=c["superficie"])
        selos.grid(row=0, column=1, sticky="e", padx=(E["meio"], 0))
        for texto, tipo in self._selos(linha):
            selo(selos, texto, tipo).pack(side="left", padx=(E["pouco"], 0))
        detalhe_ = tk.Frame(miolo, bg=c["superficie"])
        detalhe_.grid(row=1, column=0, sticky="w")
        quando = data_relativa(self._iso.get(linha["sha"]))
        extra = tipo_ramo
        if linha["tipo"] == "commit":
            extra = "colado · " + curto(re.sub(r" \(era .*\)$", "", linha.get("assunto", "")), 34)
        meta = " · ".join(p for p in (quando, extra) if p)
        m = tk.Label(detalhe_, text=meta, bg=c["superficie"], fg=c["texto_fraco"], font=letra("legenda"))
        m.pack(side="left")
        tag = ETIQUETA_DO_TIPO.get(linha["tipo"])
        if tag and linha["tipo"] != "na_main":
            t = tk.Label(detalhe_, text="·  " + tag[0], bg=c["superficie"], fg=c[tag[1]], font=letra("legenda"))
            t.pack(side="left", padx=(E["meio"], 0))
        elif tag:
            tk.Label(detalhe_, text="·  " + tag[0], bg=c["superficie"], fg=c["texto_apagado"],
                     font=letra("legenda")).pack(side="left", padx=(E["meio"], 0))
        if preparada(linha):
            tk.Label(miolo, text="✓ preparada", bg=c["superficie"], fg=c["ok"], font=letra("legenda")
                     ).grid(row=1, column=1, sticky="e", padx=(E["meio"], 0))
        self._cartoes[iid] = {"quadro": quadro, "fundo": [quadro, marca, miolo, n, selos, detalhe_, m,
                                                           *[w for w in detalhe_.winfo_children() if w is not m],
                                                           *[w for w in miolo.grid_slaves(row=1, column=1)]],
                              "marca": marca}
        self._ligar(quadro, iid)
        return quadro

    def _selos(self, linha: dict) -> list[tuple[str, str]]:
        saida = []
        if linha["tipo"] == "main":
            saida.append(("versão principal", "destaque"))
        elif e_nova(linha, self._iso):
            saida.append(("nova", "destaque"))
        if fixada(linha):
            saida.append(("fixada", "aviso"))
        return saida

    def _ligar(self, widget, iid):
        widget.bind("<Button-1>", lambda _e: self.selecionar(iid), add="+")
        widget.bind("<Double-1>", lambda _e: self.rodar(), add="+")
        widget.bind("<Enter>", lambda _e: self._pintar(iid), add="+")
        widget.bind("<Leave>", lambda _e: self._pintar(), add="+")
        for filho in widget.winfo_children():
            self._ligar(filho, iid)

    def _pintar(self, sobre: str | None = None):
        """Cor de cada cartao: escolhido (lima) > com o mouse em cima > normal."""
        c = CORES
        for iid, cartao in self._cartoes.items():
            escolhido = iid == self._sel
            fundo = c["acento_fundo"] if escolhido else (c["superficie_alta"] if iid == sobre else c["superficie"])
            for w in cartao["fundo"]:
                try:
                    w.configure(bg=fundo)
                except tk.TclError:
                    pass
            cartao["marca"].configure(bg=c["acento"] if escolhido else fundo)
            cartao["quadro"].configure(highlightbackground=c["acento"] if escolhido else c["borda"])

    def selecionar(self, iid: str):
        if iid not in self._cartoes:
            return
        self._sel = iid
        self._pintar()
        self._escolheu()

    def _linha_escolhida(self):
        return next((linha for linha in self.linhas if linha["id"] == self._sel), None)

    def _escolheu(self):
        self._escrever_detalhe(self._linha_escolhida())

    def _escrever_detalhe(self, linha):
        c, E = CORES, ESPACO
        for w in self.det_selos.winfo_children():
            w.destroy()
        merge = acao_de_merge(linha)
        self.merge.set(merge["texto"])
        self.b_comando.configure(text=merge["rotulo"], state="normal" if merge["copiar"] else "disabled")
        # So o que se COLA tem cara de comando; a dica ("de o merge do X") e apagada.
        self.campo_merge.configure(fg=c["acento"] if merge["copiar"] else c["texto_fraco"],
                                   font=letra("mono", "bold") if merge["copiar"] else letra("corpo", "normal"))
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        corpo = detalhe(linha)
        self.texto.insert("1.0", corpo)
        self.texto.configure(state="disabled", height=min(40, max(2, corpo.count("\n") + 1)))
        if not linha:
            self.det_topo.configure(text="Escolha uma versão")
            self.det_meta.configure(text="")
            self.det_assunto.configure(text="Clique num cartão da lista (ou cole um commit) e depois em Jogar.")
            self.det_estado.configure(text="")
            self.det_veredito.configure(text="")
            self.b_fixar.configure(state="disabled")
            self.b_rodar.configure(state="disabled")
            return
        nome, tipo_ramo = nome_amigavel(linha["ref"])
        self.det_topo.configure(text=nome)
        quando = data_relativa(self._iso.get(linha["sha"]))
        self.det_meta.configure(text="  ·  ".join(p for p in (quando, tipo_ramo, linha["sha"][:7]) if p))
        self.det_assunto.configure(text=curto(linha.get("assunto", ""), 160))
        self.det_estado.configure(
            text="Preparada: abre em poucos segundos." if preparada(linha)
            else "Ainda não preparada: a primeira vez leva alguns minutos.",
            fg=c["ok"] if preparada(linha) else c["texto_fraco"])
        for texto, tipo in self._selos(linha):
            selo(self.det_selos, texto, tipo).pack(side="left", padx=(0, E["pouco"]))
        if preparada(linha):
            selo(self.det_selos, "preparada", "ok").pack(side="left", padx=(0, E["pouco"]))
        tag = ETIQUETA_DO_TIPO.get(linha["tipo"])
        if tag:
            selo(self.det_selos, tag[0], {"ok": "ok", "erro": "erro", "aviso": "aviso"}.get(tag[1], "neutro")
                 ).pack(side="left")
        _topo, veredito = titulo_do_detalhe(linha)
        self.det_veredito.configure(text=veredito)
        fixa = fixada(linha)
        self.b_fixar.configure(text="★  Fixada — clique para soltar" if fixa else "☆  Fixar esta versão",
                               state="disabled" if self.ocupado else "normal")
        self.b_rodar.configure(state="disabled" if self.ocupado else "normal")

    # --- trabalho em thread -----------------------------------------
    def _botoes(self, ligados: bool):
        estado = "normal" if ligados else "disabled"
        for b in (self.b_rodar, self.b_atualizar, self.b_limpar, self.b_fixar, self.b_colado):
            b.configure(state=estado)

    def _em_thread(self, rotulo: str, trabalho, op: str = ""):
        if self.ocupado:
            messagebox.showinfo("Espere", "Ainda estou terminando a tarefa anterior.")
            return
        self.ocupado = True
        self._op = op
        self._sem_aviso()
        self._botoes(False)
        self.b_rodar.configure(text="Preparando…" if op == "jogar" else "▶  Jogar")
        self.estado.configure(text=rotulo, fg=CORES["texto"])
        self.barra.configure(value=0, mode="determinate")
        if op != "jogar":
            self.barra.configure(mode="indeterminate")
            self.barra.start(14)

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
                    self.estado.configure(text=f"Passo {n} de {total} · {curto(str(texto), 70)}")
                elif tipo in ("fim", "erro"):
                    self._terminou(tipo, resto[0])
        except queue.Empty:
            pass
        try:
            self.raiz.after(100, self._drenar)
        except tk.TclError:
            pass

    def _terminou(self, tipo, carga):
        c = CORES
        op, self._op = self._op, ""
        self.ocupado = False
        self.barra.stop()
        self.barra.configure(mode="determinate")
        self.b_rodar.configure(text="▶  Jogar")
        self._botoes(True)
        self._escolheu()                                    # religa Jogar/Fixar conforme a escolha
        if tipo == "erro":
            self.barra.configure(value=0)
            self._log(f"erro: {carga}")
            if op == "atualizar":
                self.estado.configure(text="sem conexão com o GitHub", fg=c["aviso"])
                self._aviso("Não consegui falar com o GitHub (sem internet?). Mostro a última lista que guardei.",
                            "aviso")
            else:
                self.estado.configure(text="não deu certo", fg=c["erro"])
                self._aviso(("Não consegui preparar esta versão. " if op == "jogar" else "Algo deu errado. ")
                            + curto(str(carga).splitlines()[0] if str(carga) else "", 160), "erro")
            return
        acao, dados = carga
        if acao == "lista":
            self._mostrar(*dados)
            self.barra.configure(value=0)
            self.estado.configure(text="lista atualizada", fg=c["texto_fraco"])
        elif acao == "rodou":
            self.barra.configure(value=self.barra.cget("maximum"))
            if dados.get("servidor"):
                self.servidores.append(dados["servidor"])
            self._proteger(dados.get("sha"))
            self.estado.configure(text="Jogo aberto no Chrome. Bom jogo!", fg=c["ok"])
            self._log(f"aberto: {dados.get('url')}")
            self._mostrar(self.versoes.ramos(), self._ultima or self.vigia.ler())
        elif acao == "limpou":
            self.barra.configure(value=0)
            self.estado.configure(text=f"apaguei {len(dados['apagadas'])} versão(ões) velha(s)",
                                  fg=c["texto_fraco"])
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
        self._em_thread("Buscando as versões no GitHub…", trabalho, "atualizar")

    def _preparar_e_abrir(self, ref: str, rotulo: str):
        def passo(n, total, texto):
            self.fila.put(("progresso", n, total, texto))

        def trabalho():
            ficha = self.versoes.preparar(ref, progresso=passo, rotulo=rotulo)
            self.fila.put(("log", f"abrindo {ficha['sha'][:7]} ({ficha.get('modo')})…"))
            aberto = self.versoes.abrir(ficha["sha"])
            return "rodou", dict(aberto, sha=ficha["sha"])
        self._em_thread(f"Preparando {nome_amigavel(ref)[0]}…", trabalho, "jogar")

    def rodar(self):
        linha = self._linha_escolhida()
        if not linha:
            messagebox.showinfo("Escolha uma versão", "Escolha uma versão da lista (ou cole um commit).")
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
            self.estado.configure(text=merge["texto"], fg=CORES["texto_fraco"])
            return
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append(merge["copiar"])
        self.estado.configure(text=f"copiado: {merge['copiar']}", fg=CORES["texto_fraco"])

    def limpar(self):
        fixadas = sum(1 for f in self.versoes.ler()["versoes"].values() if f.get("fixada"))
        if not messagebox.askyesno("Apagar versões velhas",
                                   f"Mantenho as {MANTER} usadas por último, as {fixadas} fixada(s) e as "
                                   f"{len(self.abertas)} aberta(s) agora; o resto (pasta, node_modules sem "
                                   "dono e HTML) sai do disco. Nada no GitHub muda. Continuar?"):
            return
        protegidos = set(self.abertas)
        self._em_thread("Apagando versões velhas…",
                        lambda: ("limpou", self.versoes.limpar(MANTER, protegidos=protegidos)), "limpar")

    def abrir_pasta(self):
        self.versoes.raiz.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self.versoes.raiz))                    # noqa: S606

    def fechar(self):
        for servidor in self.servidores:
            if servidor.poll() is None:
                matar_arvore(servidor.pid)
        self._seguras.close()
        self.raiz.destroy()


def tk_font(raiz, papel):
    import tkinter.font as tkfont
    return tkfont.Font(root=raiz, font=letra(papel))


def _barra(pai):
    return Barra(pai, CORES["fundo"])


def abrir_janela() -> int:
    raiz = tk.Tk()
    Janela(raiz)
    raiz.mainloop()
    return 0
