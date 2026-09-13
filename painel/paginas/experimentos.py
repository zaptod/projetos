# -*- coding: utf-8 -*-
"""Pagina EXPERIMENTOS: a pergunta, o braco e o numero que decide.

Toda a regra mora em `builds.experimentos` — esta pagina so desenha e
pergunta. E de proposito que ela nao calcula nada: o mesmo resultado precisa
sair igual aqui, no relatorio do Telegram e na linha de comando, e tres
lugares fazendo a propria conta e como tres telas mostrarem numeros
diferentes do mesmo estoque (foi o que ja aconteceu com o `panorama`).

O que a tela precisa deixar obvio, porque e onde a analise costuma mentir:

    n         quantos videos ENTRARAM no braco
    medidos   quantos desses ja tem metrica — sempre menor, as vezes zero
    confianca o que estes numeros permitem dizer, em portugues

Sem a coluna `medidos` do lado de `n`, um braco com 20 videos e 2 medidos
parece forte e nao e. Essa e a diferenca entre a tela ajudar e a tela
enganar.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import builds.experimentos as X

from .. import estilo

RAIZ = Path(__file__).resolve().parents[2]
RANDOM_BUILDS = RAIZ / "random_builds"

METRICAS = (("retencao", "retenção média (%)"),
            ("views_por_dia", "views por dia (mediana)"))

CORES_DA_CONFIANCA = {"claro": "ok", "indicio": "aviso", "empate": "texto_fraco",
                      "insuficiente": "texto_fraco", "sem dados": "texto_fraco"}

EXEMPLO_BRACOS = (
    "com trilha  | audio.trilha_procedural=true\n"
    "sem trilha  | audio.trilha_procedural=false")


def interpretar(texto: str):
    """`true`/`12`/`0.5` viram o tipo certo; o resto fica string.

    O ajuste entra num config JSON que a pipeline le: gravar a string
    `"false"` onde o codigo espera `False` liga a trilha em vez de desligar,
    e o experimento mediria o oposto do que diz medir — em silencio.
    """
    cru = str(texto).strip()
    baixo = cru.lower()
    if baixo in ("true", "sim", "verdadeiro"):
        return True
    if baixo in ("false", "nao", "não", "falso"):
        return False
    if baixo in ("null", "none", "vazio"):
        return None
    try:
        return int(cru)
    except ValueError:
        pass
    try:
        return float(cru)
    except ValueError:
        return cru


def ler_bracos(texto: str) -> list:
    """Uma linha por braco: `nome | chave.pontilhada=valor, outra=valor`."""
    bracos = []
    for linha in str(texto or "").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        nome, _, resto = linha.partition("|")
        ajuste = {}
        for pedaco in resto.split(","):
            chave, igual, valor = pedaco.partition("=")
            if not igual:
                continue
            ajuste[chave.strip()] = interpretar(valor)
        bracos.append({"nome": nome.strip(), "ajuste": ajuste})
    return bracos


class Pagina:
    chave = "experimentos"
    rotulo = "Experimentos"
    icone = "🔬"

    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema
        self._resultado = None

    # ------------------------------------------------------------ montar
    def construir(self, pai) -> None:
        self.o.titulo(pai, "Experimentos — o que muda o número, medido")

        topo = tk.Frame(pai, bg=self.t.fundo)
        topo.pack(fill="x", padx=estilo.ESPACO["secao"])
        self.o.rotulo(topo, "métrica que decide:", cor="texto_fraco").pack(
            side="left", padx=(0, estilo.ESPACO["meio"]))
        self.metrica = self.o.combo(topo, [r for _c, r in METRICAS],
                                    METRICAS[0][1], largura=24)
        self.metrica.pack(side="left")
        self.metrica.bind("<<ComboboxSelected>>",
                          lambda _e: self._desenhar_resultado())
        self.o.botao(topo, "＋  Novo experimento", self.novo,
                     tipo="primario").pack(side="right")
        self.o.botao(topo, "↻  Atualizar métricas", self.atualizar_metricas
                     ).pack(side="right", padx=(0, estilo.ESPACO["meio"]))

        self.o.secao(pai, "Experimentos").pack(
            anchor="w", padx=estilo.ESPACO["secao"],
            pady=(estilo.ESPACO["normal"], estilo.ESPACO["pouco"]))
        colunas = [("id", "ID", 82, "w"), ("nome", "NOME", 260, "w"),
                   ("canal", "CANAL", 88, "w"), ("tipo", "TIPO", 108, "w"),
                   ("estado", "ESTADO", 92, "w"),
                   ("bracos", "BRAÇOS", 70, "center"),
                   ("videos", "VÍDEOS", 70, "center"),
                   ("pergunta", "PERGUNTA", 300, "w")]
        self.lista = self.o.tabela(pai, colunas, altura=6, estica="pergunta")
        self.lista.pack(fill="x", padx=estilo.ESPACO["secao"])
        self.lista.tag_configure("rodando", foreground=self.t.ok)
        self.lista.tag_configure("rascunho", foreground=self.t.texto_fraco)
        self.lista.tag_configure("encerrado", foreground=self.t.texto)
        self.lista.bind("<<TreeviewSelect>>",
                        lambda _e: self._desenhar_resultado())

        self.o.secao(pai, "Resultado").pack(
            anchor="w", padx=estilo.ESPACO["secao"],
            pady=(estilo.ESPACO["normal"], estilo.ESPACO["pouco"]))
        colunas = [("braco", "BRAÇO", 240, "w"),
                   ("videos", "VÍDEOS", 74, "center"),
                   ("medidos", "MEDIDOS", 80, "center"),
                   ("views", "VIEWS", 80, "center"),
                   ("dia", "VIEWS/DIA", 96, "center"),
                   ("ret", "RETENÇÃO", 96, "center"),
                   ("nota", "", 380, "w")]
        self.placar = self.o.tabela(pai, colunas, altura=5, estica="nota")
        self.placar.pack(fill="x", padx=estilo.ESPACO["secao"])
        self.placar.tag_configure("topo", foreground=self.t.ok)

        self.leitura = self.o.rotulo(pai, "", cor="texto_fraco",
                                     wraplength=1080, justify="left")
        self.leitura.pack(anchor="w", padx=estilo.ESPACO["secao"],
                          pady=(estilo.ESPACO["meio"], 0))

        acoes = tk.Frame(pai, bg=self.t.fundo)
        acoes.pack(fill="x", padx=estilo.ESPACO["secao"],
                   pady=estilo.ESPACO["normal"])
        for texto, alvo in (("▶  Ativar", "ativar"),
                            ("■  Encerrar", "encerrar"),
                            ("🏷  Marcar vídeos", "marcar"),
                            ("🗑  Apagar", "apagar")):
            self.o.botao(acoes, texto, lambda a=alvo: self.acao(a)).pack(
                side="left", padx=(0, estilo.ESPACO["meio"]))
        self.o.legenda(
            acoes, "um experimento de ajuste por canal — dois ao mesmo tempo "
                   "se confundem").pack(side="right")

    # -------------------------------------------------------------- dados
    def ao_mostrar(self) -> None:
        self.recarregar()

    def atualizar(self, resumo: dict) -> None:
        """Nada daqui vem do panorama: a metrica e cara e tem botao proprio."""

    def recarregar(self) -> None:
        escolhido = self.lista.selection()
        self.lista.delete(*self.lista.get_children())
        contagem = {}
        for linha in X.atribuicoes():
            chave = linha.get("experimento")
            contagem[chave] = contagem.get(chave, 0) + 1
        for exp in X.listar():
            tipo = exp.get("tipo", "ajuste")
            rotulo = ("observacional" if tipo == "observacional" else "ajuste")
            if tipo == "observacional" and exp.get("campo"):
                rotulo = f"por {exp['campo']}"
            self.lista.insert(
                "", "end", iid=exp["id"],
                values=[exp["id"], exp.get("nome", ""), exp.get("canal", ""),
                        rotulo, exp.get("estado", ""),
                        len(exp.get("bracos") or []) or "—",
                        contagem.get(exp["id"], 0) or "—",
                        exp.get("pergunta", "")],
                tags=(exp.get("estado", "rascunho"),))
        for iid in escolhido:
            if self.lista.exists(iid):
                self.lista.selection_set(iid)
        self._desenhar_resultado()

    def _chave_da_metrica(self) -> str:
        escolhido = self.metrica.get()
        for chave, rotulo in METRICAS:
            if rotulo == escolhido:
                return chave
        return METRICAS[0][0]

    def _desenhar_resultado(self) -> None:
        self.placar.delete(*self.placar.get_children())
        escolha = self.lista.selection()
        if not escolha:
            self.leitura.configure(text="escolha um experimento na lista.",
                                   fg=self.t.texto_fraco)
            return
        try:
            dados = X.resultado(escolha[0], self._chave_da_metrica())
        except Exception as exc:                              # noqa: BLE001
            self.leitura.configure(text=f"não consegui ler: {exc}",
                                   fg=self.t.erro)
            return
        self._resultado = dados
        for posicao, braco in enumerate(dados["bracos"]):
            self.placar.insert(
                "", "end", iid=braco["nome"],
                values=[braco["nome"], braco["videos"], braco["medidos"],
                        braco["views"], _numero(braco["views_por_dia"]),
                        _numero(braco["retencao"], "%"),
                        _nota(braco)],
                tags=("topo",) if posicao == 0 and braco["medidos"] else ())
        cor = CORES_DA_CONFIANCA.get(dados["confianca"], "texto_fraco")
        self.leitura.configure(
            text=f"{dados['confianca'].upper()} — {dados['leitura']}"
                 + (f"\nveredito: {dados['veredito']}"
                    if dados.get("veredito") else ""),
            fg=getattr(self.t, cor))

    # -------------------------------------------------------------- acoes
    def acao(self, qual: str) -> None:
        iid = self.o.selecionado(self.lista, "Escolha um experimento.")
        if iid is None:
            return
        try:
            if qual == "ativar":
                X.ativar(iid)
            elif qual == "encerrar":
                veredito = _perguntar(self.casca, "Encerrar experimento",
                                      "O que ficou decidido? (fica gravado)")
                if veredito is None:
                    return
                X.encerrar(iid, veredito)
            elif qual == "apagar":
                if not messagebox.askyesno(
                        "Apagar", f"Apagar {iid}? Só funciona em experimento "
                                  "que ainda não produziu vídeo."):
                    return
                X.apagar(iid)
            elif qual == "marcar":
                self.marcar(iid)
                return
        except X.ExperimentoInvalido as exc:
            messagebox.showwarning("Não dá", str(exc))
        except Exception as exc:                              # noqa: BLE001
            messagebox.showerror("Falhou", str(exc))
        self.recarregar()

    def marcar(self, exp_id: str) -> None:
        """Rotula videos JA publicados — a pergunta feita depois do fato."""
        exp = X.carregar().get(exp_id) or {}
        if exp.get("tipo", "ajuste") == "observacional":
            messagebox.showinfo(
                "Não precisa",
                "Um experimento observacional já agrupa sozinho pelo campo "
                "escolhido. Marcar à mão só faz sentido em experimento de "
                "ajuste.")
            return
        nomes = [b["nome"] for b in exp.get("bracos") or []]
        if not nomes:
            return
        janela = Dialogo(self.casca, "Marcar vídeos já publicados")
        braco = janela.combo("Braço", nomes)
        ids = janela.texto("IDs dos vídeos (um por linha)", 7,
                           "ex.: historia_00007:celular:p04")
        if not janela.esperar():
            return
        lista = [L.strip() for L in ids.get("1.0", "end").splitlines()
                 if L.strip()]
        try:
            quantos = X.marcar_a_mao(exp_id, braco.get(), lista)
        except X.ExperimentoInvalido as exc:
            messagebox.showwarning("Não dá", str(exc))
            return
        self.casca._registrar(
            f"{quantos} vídeo(s) marcados como {braco.get()!r}.", "ok")
        self.recarregar()

    def novo(self) -> None:
        janela = Dialogo(self.casca, "Novo experimento")
        nome = janela.entrada("Nome", "Trilha instrumental nas histórias")
        pergunta = janela.entrada(
            "Pergunta", "O instrumental de fundo muda a retenção?")
        canal = janela.combo("Canal", list(X.CANAIS))
        tipo = janela.combo("Tipo", list(X.TIPOS))
        campo = janela.combo("Campo (só observacional)",
                             sorted(X.CAMPOS_OBSERVAVEIS))
        janela.explicar(
            "ajuste — muda a produção e sorteia qual vídeo recebe qual braço. "
            "É o único jeito de responder sobre algo que ainda não existe em "
            "vídeo nenhum.\n"
            "observacional — não muda nada: agrupa o que já foi medido por um "
            "campo que já varia. Responde hoje.")
        bracos = janela.texto("Braços (um por linha)", 6, EXEMPLO_BRACOS)
        if not janela.esperar():
            return
        try:
            criado = X.criar(
                nome.get(), pergunta.get(), canal.get(),
                ler_bracos(bracos.get("1.0", "end")),
                tipo=tipo.get(), campo=campo.get())
        except X.ExperimentoInvalido as exc:
            messagebox.showwarning("Não dá", str(exc))
            return
        self.casca._registrar(
            f"{criado['id']} criado em rascunho — use Ativar para valer.",
            "ok")
        self.recarregar()

    def atualizar_metricas(self) -> None:
        """Reconcilia o id do YouTube e busca views/retenção dos dois canais."""
        import sys
        self.casca.supervisor.rodar(
            [sys.executable, "-u", "-X", "utf8", "-c",
             "from builds.publicar import metricas; metricas.atualizar_tudo()"],
            cwd=RANDOM_BUILDS, rotulo="métricas dos dois canais",
            depois=self.recarregar)


# ------------------------------------------------------------------ apoio
def _numero(valor, sufixo: str = "") -> str:
    if valor is None:
        return "—"
    return f"{valor:.1f}{sufixo}" if valor < 100 else f"{valor:.0f}{sufixo}"


def _nota(braco: dict) -> str:
    """A ressalva que a linha precisa carregar, e nao a tela inteira."""
    if not braco["videos"]:
        return "nenhum vídeo entrou neste braço ainda"
    if not braco["medidos"]:
        return "nenhum vídeo medido ainda — atualize as métricas"
    if braco["medidos"] < braco["videos"]:
        faltam = braco["videos"] - braco["medidos"]
        return f"{faltam} vídeo(s) ainda sem métrica"
    return ""


def _perguntar(casca, titulo: str, pergunta: str):
    from tkinter import simpledialog
    return simpledialog.askstring(titulo, pergunta, parent=casca)


class Dialogo(tk.Toplevel):
    """Um formulario modal montado por linhas, sem uma classe por caixa."""

    def __init__(self, casca, titulo: str):
        super().__init__(casca)
        self.o, self.t = casca.oficina, casca.tema
        self.title(titulo)
        self.configure(bg=self.t.fundo)
        self.transient(casca)
        self.resizable(False, False)
        self._ok = False
        self.corpo = tk.Frame(self, bg=self.t.fundo)
        self.corpo.pack(fill="both", expand=True, padx=estilo.ESPACO["secao"],
                        pady=estilo.ESPACO["normal"])

    def _linha(self, rotulo: str):
        linha = tk.Frame(self.corpo, bg=self.t.fundo)
        linha.pack(fill="x", pady=estilo.ESPACO["pouco"])
        self.o.rotulo(linha, rotulo, cor="texto_fraco").pack(
            anchor="w")
        return linha

    def entrada(self, rotulo: str, exemplo: str = ""):
        linha = self._linha(rotulo)
        variavel = tk.StringVar()
        tk.Entry(linha, textvariable=variavel, width=58,
                 bg=self.t.superficie_alta, fg=self.t.texto,
                 insertbackground=self.t.texto, relief="flat",
                 font=self.t.letra("corpo"), highlightthickness=1,
                 highlightbackground=self.t.borda).pack(fill="x", ipady=3)
        if exemplo:
            self.o.legenda(linha, f"ex.: {exemplo}").pack(anchor="w")
        return variavel

    def combo(self, rotulo: str, valores: list):
        linha = self._linha(rotulo)
        alvo = self.o.combo(linha, valores, valores[0] if valores else "",
                            largura=30)
        alvo.pack(anchor="w")
        return alvo

    def texto(self, rotulo: str, alturas: int, exemplo: str = ""):
        linha = self._linha(rotulo)
        caixa = tk.Text(linha, height=alturas, width=58, wrap="none",
                        bg=self.t.superficie_alta, fg=self.t.texto,
                        insertbackground=self.t.texto, relief="flat",
                        font=self.t.letra("corpo"), highlightthickness=1,
                        highlightbackground=self.t.borda)
        caixa.pack(fill="x")
        if exemplo:
            caixa.insert("1.0", exemplo)
        return caixa

    def explicar(self, texto: str):
        self.o.rotulo(self.corpo, texto, cor="texto_fraco", wraplength=520,
                      justify="left").pack(anchor="w",
                                           pady=estilo.ESPACO["pouco"])

    def esperar(self) -> bool:
        pe = tk.Frame(self.corpo, bg=self.t.fundo)
        pe.pack(fill="x", pady=(estilo.ESPACO["normal"], 0))
        self.o.botao(pe, "Cancelar", self._cancelar).pack(side="right")
        self.o.botao(pe, "Gravar", self._gravar, tipo="primario").pack(
            side="right", padx=(0, estilo.ESPACO["meio"]))
        self.grab_set()
        self.wait_window(self)
        return self._ok

    def _gravar(self) -> None:
        self._ok = True
        self.destroy()

    def _cancelar(self) -> None:
        self._ok = False
        self.destroy()


__all__ = ["Pagina", "interpretar", "ler_bracos"]
