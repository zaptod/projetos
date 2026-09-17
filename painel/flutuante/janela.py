# -*- coding: utf-8 -*-
"""A janela flutuante: sem borda do Windows, por cima de tudo, arrastavel.

PEDIDO DO ADRIAN (17/09/2026): "uma interface grafica flutuante para
substituir esse terminal aberto, fica feio. Quero que utilize aquela ideia da
vila, e que fique bem claro tudo o que esta acontecendo."

Quatro tamanhos, e cada um responde uma pergunta:

  ICONE    (56x56)   "esta tudo bem?" — a borda muda de cor, o selo conta
                     os erros. O "fechar" vem para ca: janela sem borda nao
                     tem barra de tarefas, e fechar de verdade esconderia os
                     alertas. Sem `pystray` (nao esta instalado), o icone
                     flutuante faz o papel da bandeja.
  MINI     (340x64)  "o que esta rodando e quando sai o proximo?"
  MEDIO    (720x520) a Vila + quem esta vivo + abas (diario, postagem,
                     erros, terminal).
  GRANDE   (ate 1180x700) tudo lado a lado, com o terminal em gaveta.

A REGRA DE THREAD, que e a unica que derruba o Tk: so esta classe chama
`after`, e so na thread da interface. O `Coletor` publica numa fila.
"""
from __future__ import annotations

import queue
import tkinter as tk
from datetime import datetime

from .. import estilo
from ..estilo import ESPACO
from . import dados, preferencias
from .caminhos import Caminhos
from .coletor import Coletor
from .mundo import CenaVila

ANIMACAO_MS = 70
FILA_MS = 250
TIQUE_MS = 1000
# Cor que o Windows torna transparente no modo icone (o circulo fica redondo).
CHAVE_TRANSPARENTE = "#010203"

ABAS = (("diario", "Diário"), ("postagem", "Postagem"), ("erros", "Erros"),
        ("terminal", "Terminal"))


def _cortar(texto: str, limite: int) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


def _hora(momento) -> str:
    return momento.strftime("%H:%M") if momento else "—"


# ====================================================================
# Paineis: cada um sabe se montar e se atualizar a partir do ESTADO.
# ====================================================================
class _Painel:
    def __init__(self, app):
        self.app = app
        self.t = app.t
        self._assinatura = None

    def mudou(self, *partes) -> bool:
        assinatura = repr(partes)
        if assinatura == self._assinatura:
            return False
        self._assinatura = assinatura
        return True

    def tique(self, agora: datetime) -> None:
        pass


def _texto(pai, tema, altura: int = 6, mono: bool = True) -> tk.Text:
    caixa = tk.Text(pai, height=altura, bg=tema.console_fundo,
                    fg=tema.console_texto,
                    font=tema.letra("mono" if mono else "legenda"),
                    relief="flat", bd=0, wrap="none", state="disabled",
                    padx=ESPACO["meio"], pady=ESPACO["pouco"],
                    highlightthickness=1, highlightbackground=tema.borda,
                    cursor="arrow", insertwidth=0)
    for marca, cor in (("erro", tema.erro), ("ok", tema.ok),
                       ("aviso", tema.aviso), ("inicio", tema.acento_forte),
                       ("fraco", tema.texto_apagado), ("cmd", tema.info),
                       ("acento", tema.acento), ("titulo", tema.texto_fraco),
                       ("forte", tema.texto)):
        caixa.tag_configure(marca, foreground=cor)
    caixa.tag_configure("titulo", font=tema.letra("legenda", "bold"),
                        spacing1=6)
    caixa.tag_configure("forte", font=tema.letra("mono", "bold"))
    return caixa


def _reescrever(caixa: tk.Text, pedacos: list, rolar_fim: bool = False) -> None:
    """Troca o conteudo sem perder a rolagem de quem esta lendo."""
    topo = caixa.yview()
    no_fim = topo[1] >= 0.999
    caixa.configure(state="normal")
    caixa.delete("1.0", "end")
    for texto, marcas in pedacos:
        caixa.insert("end", texto, marcas)
    caixa.configure(state="disabled")
    if rolar_fim and no_fim:
        caixa.see("end")
        # Recem-montada, a caixa ainda nao tem altura e o `see` erra: o fim
        # so fica certo depois do desenho. (Estamos na thread do Tk.)
        caixa.after_idle(caixa.yview_moveto, 1.0)
    elif not rolar_fim:
        caixa.yview_moveto(topo[0])


class PainelProxima(_Painel):
    """Uma linha: quando sai o proximo, e o que sai."""

    def __init__(self, app, pai, curto: bool = False):
        super().__init__(app)
        self.curto = curto
        self.quadro = tk.Frame(pai, bg=self.t.fundo)
        self.lbl_tempo = tk.Label(self.quadro, bg=self.t.fundo,
                                  fg=self.t.acento,
                                  font=self.t.letra("corpo", "bold"))
        self.lbl_tempo.pack(side="left")
        self.lbl_oque = tk.Label(self.quadro, bg=self.t.fundo,
                                 fg=self.t.texto_fraco, anchor="w",
                                 font=self.t.letra("legenda"))
        self.lbl_oque.pack(side="left", padx=(ESPACO["meio"], 0), fill="x")

    def atualizar(self, estado: dict) -> None:
        self.lbl_oque.configure(text=_cortar(
            texto_da_fila(estado), 70 if self.curto else 110))

    def tique(self, agora: datetime) -> None:
        self.lbl_tempo.configure(text=texto_do_proximo(self.app.estado, agora))


def texto_do_proximo(estado: dict, agora: datetime) -> str:
    alvo = estado.get("proximo") or dados.proximo_horario(agora)
    if alvo <= agora:
        alvo = dados.proximo_horario(agora)
    return (f"⏭ {alvo.strftime('%H:%M')} · "
            f"{dados.contagem((alvo - agora).total_seconds())}")


def texto_da_fila(estado: dict) -> str:
    previsao = estado.get("previsao") or {}
    if not previsao:
        return ("YouTube + TikTok · prevendo o que sai…"
                if estado.get("previsao_rodando") else
                "YouTube + TikTok · previsão ainda não lida")
    if previsao.get("falhou"):
        return f"previsão falhou: {previsao['falhou']}"
    partes = ["YT + TT"]
    for canal, icone in (("historias", "📚"), ("builds", "🧱")):
        video = previsao.get(canal)
        partes.append(f"{icone} {dados.ref_legivel(video['id'])}" if video
                      else f"{icone} nada pronto")
    return " · ".join(partes)


class PainelAgora(_Painel):
    """Uma linha por processo vivo: quem, o que, desde quando."""

    def __init__(self, app, pai, maximo: int, chars: int,
                 com_contas: bool = True):
        super().__init__(app)
        self.maximo, self.chars = maximo, chars
        # No MEDIO a linha das contas sai: a bandeira ja esta no predio, e
        # cada linha aqui e uma linha a menos na aba (terminal, diario).
        self.com_contas = com_contas
        self.quadro = tk.Frame(pai, bg=self.t.fundo)

    def atualizar(self, estado: dict) -> None:
        vivos = estado.get("vivos") or []
        travas = [t for t in estado.get("travas") or []
                  if t["predio"] not in ("casa", "bot")
                  and not t["texto"].startswith("render ")]
        conhecidos = estado.get("processos_conhecidos")
        chave = [(v["emoji"], v["quem"], v["oque"], v["desde"], v["ha"],
                  v["ativo"]) for v in vivos]
        if not self.mudou(chave, [t["texto"] for t in travas], conhecidos):
            return
        for filho in self.quadro.winfo_children():
            filho.destroy()
        linhas = vivos[:self.maximo]
        if not linhas:
            self._linha("…" if not conhecidos else "💤",
                        "lendo quem está rodando…" if not conhecidos
                        else "nenhum processo do sistema rodando agora",
                        "", False)
        for v in linhas:
            self._linha(v["emoji"], f"{v['quem']} — {v['oque']}",
                        f"desde {v['desde']} · {v['ha']}", v["ativo"])
        if len(vivos) > self.maximo:
            self._linha("", f"… e mais {len(vivos) - self.maximo} "
                            "(o GRANDE mostra todos)", "", False)
        if travas and self.com_contas:
            contas = ", ".join(
                f"{dados.rotulo(t['predio']) if t['predio'] else '?'} "
                f"({t['conta']})" for t in travas)
            self._linha("⚑", f"contas de navegador em uso: {contas}", "",
                        False, cor=self.t.acento_forte)

    def _linha(self, icone: str, texto: str, direita: str, ativo: bool,
               cor: str | None = None) -> None:
        linha = tk.Frame(self.quadro, bg=self.t.fundo)
        linha.pack(fill="x")
        frente = cor or (self.t.texto if ativo else self.t.texto_fraco)
        tk.Label(linha, text=f"{icone} {_cortar(texto, self.chars)}",
                 bg=self.t.fundo, fg=frente, anchor="w",
                 font=self.t.letra("legenda", "bold" if ativo else "normal")
                 ).pack(side="left", fill="x")
        if direita:
            tk.Label(linha, text=direita, bg=self.t.fundo,
                     fg=self.t.texto_apagado, font=self.t.letra("legenda")
                     ).pack(side="right")


class PainelDiario(_Painel):
    def __init__(self, app, pai, altura: int = 6):
        super().__init__(app)
        self.caixa = _texto(pai, self.t, altura)
        self.quadro = self.caixa

    def atualizar(self, estado: dict) -> None:
        feed = estado.get("feed") or []
        if not self.mudou(feed[-40:], estado.get("diario_ok")):
            return
        if not feed:
            texto = ("o diário ainda não tem eventos" if estado.get("diario_ok")
                     else "não achei o atividade.jsonl")
            _reescrever(self.caixa, [(texto, ("fraco",))])
            return
        _reescrever(self.caixa, [(f"{t}\n", (m,)) for t, m in reversed(feed)])


class PainelPostagem(_Painel):
    """Proxima postagem por canal, gordura, ultimos publicados e o bot."""

    def __init__(self, app, pai, altura: int = 10, com_relogio: bool = True):
        super().__init__(app)
        self.quadro = tk.Frame(pai, bg=self.t.fundo)
        # No MEDIO a linha do proximo horario ja esta logo acima das abas;
        # repetir o relogio ali so come as linhas que a aba tem.
        self.lbl_tempo = tk.Label(self.quadro, bg=self.t.fundo,
                                  fg=self.t.acento, anchor="w",
                                  font=self.t.letra("corpo", "bold"))
        if com_relogio:
            self.lbl_tempo.pack(fill="x")
        self.caixa = _texto(self.quadro, self.t, altura)
        # Titulo inteiro, quebrado com recuo, em vez de cortado na borda.
        self.caixa.configure(wrap="word")
        self.caixa.tag_configure("recuo", lmargin2=36)
        self.caixa.pack(fill="both", expand=True, pady=(ESPACO["pouco"], 0))
        self.caixa.tag_configure("link", foreground=self.t.acento,
                                 underline=True)
        self.caixa.tag_bind("link", "<Button-1>",
                            lambda _e: self.app.prever_agora())
        self.caixa.tag_bind("link", "<Enter>",
                            lambda _e: self.caixa.configure(cursor="hand2"))
        self.caixa.tag_bind("link", "<Leave>",
                            lambda _e: self.caixa.configure(cursor="arrow"))

    def tique(self, agora: datetime) -> None:
        self.lbl_tempo.configure(
            text=f"{texto_do_proximo(self.app.estado, agora)}  ·  "
                 "YouTube + TikTok, os dois canais")

    def atualizar(self, estado: dict) -> None:
        previsao = estado.get("previsao") or {}
        bot = estado.get("bot") or {}
        publicados = estado.get("publicados") or []
        if not self.mudou(previsao, publicados, bot,
                          estado.get("previsao_rodando"),
                          estado.get("previsao_em"), estado.get("tarefas")):
            return
        _reescrever(self.caixa, [(texto, tuple(marcas) + ("recuo",))
                                 for texto, marcas in
                                 pedacos_da_postagem(estado)])


def pedacos_da_postagem(estado: dict) -> list:
    """O conteudo do painel de postagem, como (texto, marcas). Sem Tk."""
    p: list = []
    previsao = estado.get("previsao") or {}
    p.append(("O QUE SAI\n", ("titulo",)))
    if previsao.get("falhou"):
        p.append((f"  previsão falhou: {previsao['falhou']}\n", ("erro",)))
    elif not previsao:
        p.append(("  prevendo…\n" if estado.get("previsao_rodando")
                  else "  ainda sem previsão\n", ("fraco",)))
    for canal, icone, nome in (("historias", "📚", "histórias"),
                               ("builds", "🧱", "builds")):
        if not previsao or previsao.get("falhou"):
            break
        video = previsao.get(canal)
        if video:
            p.append((f"  {icone} {nome:<9} ", ("forte",)))
            p.append((f"{dados.ref_legivel(video['id'])}  ", ("acento",)))
            p.append((f"{_cortar(video.get('titulo'), 90)}\n", ()))
        else:
            p.append((f"  {icone} {nome:<9} ", ("forte",)))
            p.append(("nada pronto para sair neste canal\n", ("erro",)))
        if canal == "historias" and previsao.get("fila_historias"):
            depois = ", ".join(dados.ref_legivel(v["id"])
                               for v in previsao["fila_historias"])
            p.append((f"      depois: {depois}\n", ("fraco",)))
    atrasados = previsao.get("atrasados_tiktok") or {}
    if any(atrasados.values()):
        p.append(("  atrasados no TikTok: " + " · ".join(
            f"{c} {n}" for c, n in atrasados.items()) + "\n", ("aviso",)))
    if previsao.get("avisos"):
        for aviso in previsao["avisos"][-3:]:
            aviso = aviso.replace("[postar] ", "").split(":")[0]
            p.append((f"  · {_cortar(aviso, 58)}\n", ("fraco",)))
    quando = estado.get("previsao_em")
    p.append((f"  lida às {_hora(quando)} · " if quando else "  ", ("fraco",)))
    p.append(("prever agora", ("link",)))
    p.append(("  (vistoria e parecer só na hora do post)\n", ("fraco",)))

    gordura = previsao.get("gordura") or {}
    if gordura:
        p.append(("GORDURA\n", ("titulo",)))
        for canal, icone in (("historias", "📚"), ("builds", "🧱")):
            dias = gordura.get(canal)
            if dias is None:
                continue
            if dias < 0:
                p.append((f"  {icone} {canal}: não consegui contar\n",
                          ("erro",)))
            elif dias < 1:
                p.append((f"  {icone} {canal}: {dias} dia(s)  ⚠ abaixo do "
                          "piso\n", ("erro",)))
            else:
                p.append((f"  {icone} {canal}: {dias} dia(s)\n", ("ok",)))

    # O BOT VEM ANTES DOS PUBLICADOS: se ele caiu, os avisos do celular
    # pararam — e isso e mais urgente que a lista do que ja foi.
    _secao_do_bot(p, estado.get("bot") or {})
    _secao_de_publicados(p, estado.get("publicados") or [])
    _secao_do_agendador(p, estado.get("tarefas"))
    return p


def _secao_do_agendador(p: list, agendador: dict | None) -> None:
    p.append(("AGENDADOR\n", ("titulo",)))
    if not agendador:
        p.append(("  lendo as tarefas…\n", ("fraco",)))
        return
    marca = {True: "ok", False: "erro"}.get(agendador.get("ok"), "fraco")
    p.append((f"  {agendador.get('selo')}\n", (marca,)))
    for item in (agendador.get("problemas") or [])[:6]:
        p.append((f"  ⚠ {item['nome']}: {item['motivo']}\n", ("aviso",)))


def _secao_de_publicados(p: list, publicados: list) -> None:
    p.append(("ÚLTIMOS PUBLICADOS\n", ("titulo",)))
    if not publicados:
        p.append(("  nenhum no ledger\n", ("fraco",)))
    for item in publicados:
        marca = "✓" if item["prova"] else "⚠"
        plataforma = {"youtube": "YT", "tiktok": "TT"}.get(
            item["plataforma"], item["plataforma"][:2].upper())
        canal = {"historias": "hist", "builds": "build"}.get(item["canal"],
                                                            item["canal"])
        p.append((f"  {marca} ", ("ok" if item["prova"] else "aviso",)))
        p.append((f"{item['quando'].strftime('%d/%m %H:%M')} {plataforma} "
                  f"{canal:<5} ", ("fraco",)))
        p.append((f"{_cortar(item['titulo'], 90)}", ()))
        p.append(("\n" if item["prova"] else "  (sem prova)\n",
                  () if item["prova"] else ("aviso",)))


def _secao_do_bot(p: list, bot: dict) -> None:
    p.append(("BOT DO TELEGRAM\n", ("titulo",)))
    if bot.get("vivo"):
        desde = bot.get("desde")
        p.append(("  ● no ar", ("ok",)))
        if desde:
            p.append((f" desde {desde.strftime('%d/%m %H:%M')}", ("fraco",)))
        p.append(("\n", ()))
    else:
        p.append(("  ● FORA DO AR — os avisos do celular pararam\n",
                  ("erro",)))
    relatorios = bot.get("relatorios") or {}
    if relatorios:
        p.append(("  relatórios: " + " · ".join(
            f"{k} {str(v)[8:10]}/{str(v)[5:7]}"
            for k, v in relatorios.items()) + "\n", ("fraco",)))
    if bot.get("ultima_linha"):
        p.append((f"  último: {_cortar(bot['ultima_linha'], 70)} "
                  f"({_hora(bot.get('mexeu'))})\n", ("fraco",)))


class PainelErros(_Painel):
    def __init__(self, app, pai, altura: int = 6):
        super().__init__(app)
        self.quadro = tk.Frame(pai, bg=self.t.fundo)
        self.lbl = tk.Label(self.quadro, bg=self.t.fundo, anchor="w",
                            fg=self.t.texto_fraco,
                            font=self.t.letra("legenda", "bold"))
        self.lbl.pack(fill="x")
        self.caixa = _texto(self.quadro, self.t, altura)
        self.caixa.pack(fill="both", expand=True, pady=(ESPACO["pouco"], 0))

    def atualizar(self, estado: dict) -> None:
        erros = estado.get("erros") or []
        chave = [(e.get("ts"), e.get("detalhe")) for e in erros]
        if not self.mudou(chave):
            return
        self.lbl.configure(
            text=f"ERROS NAS ÚLTIMAS 2 H · {len(erros)}"
                 + ("  (clique para ver o detalhe)" if erros else ""),
            fg=self.t.erro if erros else self.t.texto_fraco)
        for marca in self.caixa.tag_names():
            if marca.startswith("e_"):
                self.caixa.tag_delete(marca)
        if not erros:
            _reescrever(self.caixa,
                        [("✓ nenhum erro nas últimas 2 horas\n", ("ok",))])
            return
        pedacos = []
        for i, erro in enumerate(erros):
            marca = f"e_{i}"
            self.caixa.tag_configure(marca)
            self.caixa.tag_bind(marca, "<Button-1>",
                                lambda _e, x=erro: self.app.detalhe_erro(x))
            self.caixa.tag_bind(
                marca, "<Enter>",
                lambda _e: self.caixa.configure(cursor="hand2"))
            self.caixa.tag_bind(
                marca, "<Leave>",
                lambda _e: self.caixa.configure(cursor="arrow"))
            pedacos.append((f"✗ {_hora(erro.get('quando'))} "
                            f"{dados.rotulo(erro['predio']):<9.9} ",
                            ("erro", marca)))
            pedacos.append((f"{_cortar(erro.get('detalhe'), 90)}\n",
                            (marca,)))
        _reescrever(self.caixa, pedacos)


class PainelTerminal(_Painel):
    """Os consoles pretos, aqui dentro, com cor por tipo de linha."""

    def __init__(self, app, pai, altura: int = 8):
        super().__init__(app)
        self.quadro = tk.Frame(pai, bg=self.t.fundo)
        topo = tk.Frame(self.quadro, bg=self.t.fundo)
        topo.pack(fill="x")
        self.botoes = {}
        for nome in app.caminhos.terminais:
            botao = tk.Label(topo, text=nome, bg=self.t.fundo,
                             font=self.t.letra("legenda", "bold"),
                             padx=ESPACO["meio"], cursor="hand2")
            botao.pack(side="left")
            botao.bind("<Button-1>", lambda _e, n=nome: self.escolher(n))
            self.botoes[nome] = botao
        self.lbl = tk.Label(topo, bg=self.t.fundo, fg=self.t.texto_apagado,
                            font=self.t.letra("legenda"), anchor="e")
        self.lbl.pack(side="right")
        self.caixa = _texto(self.quadro, self.t, altura)
        self.caixa.pack(fill="both", expand=True, pady=(ESPACO["pouco"], 0))
        # SEGUIR O FIM como um console: so enquanto quem le esta no fim. A
        # rolagem feita antes de a caixa ter tamanho parava 2-3 linhas antes
        # (medido); o `<Configure>` chega quando o tamanho e o de verdade.
        self._seguir = True
        self.caixa.bind("<Configure>", lambda _e: self._ao_fim())
        self._pintar_botoes()

    def _ao_fim(self) -> None:
        if self._seguir:
            self.caixa.see("end")
            self.caixa.yview_moveto(1.0)

    def escolher(self, nome: str) -> None:
        self.app.prefs["terminal"] = nome
        self.app.guardar()
        self._assinatura = None
        self._pintar_botoes()
        self.atualizar(self.app.estado, rolar=True)

    def _pintar_botoes(self) -> None:
        atual = self.app.prefs.get("terminal")
        for nome, botao in self.botoes.items():
            botao.configure(fg=self.t.acento if nome == atual
                            else self.t.texto_fraco)

    def atualizar(self, estado: dict, rolar: bool = False) -> None:
        nome = self.app.prefs.get("terminal")
        if nome not in self.app.caminhos.terminais:
            nome = next(iter(self.app.caminhos.terminais))
        linhas = (estado.get("terminais") or {}).get(nome) or []
        if not self.mudou(nome, linhas[-3:], len(linhas)):
            return
        caminho = self.app.caminhos.terminais[nome]
        try:
            mexeu = datetime.fromtimestamp(caminho.stat().st_mtime)
            info = f"{caminho.name} · mudou às {mexeu.strftime('%d/%m %H:%M')}"
        except OSError:
            info = f"{caminho.name} · ainda não existe"
        self.lbl.configure(text=info)
        if not linhas:
            _reescrever(self.caixa, [("(vazio)", ("fraco",))])
            return
        self._seguir = rolar or self.caixa.yview()[1] >= 0.999
        pedacos = [(f"{t}\n", (m,) if m else ()) for t, m in linhas]
        texto, marcas = pedacos[-1]
        pedacos[-1] = (texto.rstrip("\n"), marcas)
        _reescrever(self.caixa, pedacos, rolar_fim=True)
        self._ao_fim()


# ====================================================================
# A janela
# ====================================================================
class Janela(tk.Tk):
    def __init__(self, caminhos: Caminhos | None = None,
                 modo: str | None = None, topo: bool | None = None,
                 coletor: Coletor | None = None, iniciar: bool = True,
                 persistir: bool = True):
        super().__init__()
        self.persistir = persistir
        self.t = estilo.VILA
        self.caminhos = caminhos or Caminhos()
        self.prefs = preferencias.ler(self.caminhos.preferencias)
        if modo in preferencias.MODOS:
            self.prefs["modo"] = modo
        if topo is not None:
            self.prefs["topo"] = bool(topo)
        self.coletor = coletor or Coletor(self.caminhos, queue.Queue())
        self.fila = self.coletor.fila
        self.estado: dict = {}
        self.modo = None
        self._cache_mundo: dict = {}
        self._paineis: list = []
        self._cena: CenaVila | None = None
        self._animacao = None
        self._arrasto = None
        self._abas: dict = {}
        self._dica_padrao = ""
        self._vivo = True
        self._botoes: list = []
        self._dica_flutuante = None
        self._escuta = None

        self.title("Vila — Neural Fights")
        self.configure(bg=self.t.borda_forte)
        self.overrideredirect(True)
        self._aplicar_topo()
        self._menu = self._montar_menu()
        self.trocar(self.prefs["modo"], inicial=True)
        self.after(FILA_MS, self._drenar)
        self.after(TIQUE_MS, self._tique)
        if iniciar:
            self.coletor.iniciar()
        if persistir:
            self.escutar()

    # -------------------------------------------------------- utilidades
    def guardar(self) -> None:
        if not self.persistir:
            return
        if self.modo and self.winfo_exists():
            self.prefs["x"], self.prefs["y"] = self.winfo_x(), self.winfo_y()
        preferencias.gravar(self.caminhos.preferencias, self.prefs)

    def _aplicar_topo(self) -> None:
        self.attributes("-topmost", bool(self.prefs["topo"]))

    def alternar_topo(self) -> None:
        self.prefs["topo"] = not self.prefs["topo"]
        self._aplicar_topo()
        self._topo_var.set(self.prefs["topo"])
        if getattr(self, "_btn_topo", None) is not None:
            cor = self.t.acento if self.prefs["topo"] else self.t.texto_fraco
            self._btn_topo.botao.cor_normal = cor
            self._btn_topo.botao.configure(fg=cor)
        self.guardar()

    def _montar_menu(self) -> tk.Menu:
        menu = tk.Menu(self, tearoff=False, bg=self.t.superficie_alta,
                       fg=self.t.texto, activebackground=self.t.acento_fundo,
                       activeforeground=self.t.acento_forte,
                       font=self.t.letra("corpo"), bd=0)
        menu.add_command(label="Faixa (mini)", command=lambda: self.trocar("mini"))
        menu.add_command(label="Médio", command=lambda: self.trocar("medio"))
        menu.add_command(label="Grande", command=lambda: self.trocar("grande"))
        menu.add_command(label="Ícone", command=lambda: self.trocar("icone"))
        menu.add_separator()
        self._topo_var = tk.BooleanVar(value=bool(self.prefs["topo"]))
        menu.add_checkbutton(label="Sempre por cima",
                             variable=self._topo_var,
                             command=self.alternar_topo)
        menu.add_command(label="Prever a próxima postagem agora",
                         command=self.prever_agora)
        menu.add_command(label="Abrir o painel completo",
                         command=self.abrir_painel)
        menu.add_separator()
        # O unico jeito de FECHAR de verdade: o ✕ e o − viram o icone, que
        # continua visivel e traz a janela de volta com um clique.
        menu.add_command(label="Fechar de verdade", command=self.sair)
        return menu

    def _abrir_menu(self, evento) -> None:
        try:
            self._menu.tk_popup(evento.x_root, evento.y_root)
        finally:
            self._menu.grab_release()

    def _arrastavel(self, *widgets, ao_clicar=None) -> None:
        for w in widgets:
            w.bind("<ButtonPress-1>", self._agarrar, add="+")
            w.bind("<B1-Motion>", self._arrastar, add="+")
            w.bind("<ButtonRelease-1>",
                   lambda e, f=ao_clicar: self._soltar(e, f), add="+")
            w.bind("<Button-3>", self._abrir_menu, add="+")

    def _agarrar(self, evento) -> None:
        self._arrasto = (evento.x_root - self.winfo_x(),
                         evento.y_root - self.winfo_y(),
                         evento.x_root, evento.y_root, False)

    def _arrastar(self, evento) -> None:
        if not self._arrasto:
            return
        dx, dy, x0, y0, _moveu = self._arrasto
        moveu = abs(evento.x_root - x0) + abs(evento.y_root - y0) > 3
        if moveu or _moveu:
            self._arrasto = (dx, dy, x0, y0, True)
            self.geometry(f"+{evento.x_root - dx}+{evento.y_root - dy}")

    def _soltar(self, _evento, ao_clicar) -> None:
        moveu = bool(self._arrasto and self._arrasto[4])
        self._arrasto = None
        if moveu:
            self._reencaixar()
            self.guardar()
        elif ao_clicar is not None:
            ao_clicar()

    def _reencaixar(self) -> None:
        tela = (self.winfo_screenwidth(), self.winfo_screenheight())
        x, y = preferencias.encaixar(self.winfo_x(), self.winfo_y(),
                                     self.winfo_width(), self.winfo_height(),
                                     tela)
        self.geometry(f"+{x}+{y}")

    LADO_BOTAO = 26

    def _botao(self, pai, texto: str, acao, dica: str,
               ativo: bool = False, nome: str = "") -> tk.Label:
        """Um botao com AREA DE CLIQUE PROPRIA, de tamanho fixo.

        Bug de 17/09/2026: os botoes eram Labels soltos empacotados DEPOIS
        de um texto com `expand`; com o texto comprido o Tk os espremia e o
        clique no ✕ caia no vizinho. Agora cada um mora num quadro de
        26x26 que nao encolhe, e a barra empacota os botoes PRIMEIRO.
        """
        fundo = pai.cget("bg")
        cor = self.t.acento if ativo else self.t.texto_fraco
        from tkinter import font as tkfont
        largura = max(self.LADO_BOTAO, tkfont.Font(
            font=self.t.letra("corpo")).measure(texto) + 12)
        caixa = tk.Frame(pai, bg=fundo, width=largura,
                         height=self.LADO_BOTAO, cursor="hand2")
        caixa.pack_propagate(False)
        botao = tk.Label(caixa, text=texto, bg=fundo, fg=cor, cursor="hand2",
                         font=self.t.letra("corpo"), bd=0, padx=0, pady=0)
        botao.pack(fill="both", expand=True)

        def entrar(_e):
            for w in (caixa, botao):
                w.configure(bg=self.t.superficie_alta)
            botao.configure(fg=self.t.acento_forte)
            self._dica(dica)
            self._mostrar_dica_flutuante(caixa, dica)

        def sair(_e):
            for w in (caixa, botao):
                w.configure(bg=fundo)
            botao.configure(fg=botao.cor_normal)
            self._dica(None)
            self._esconder_dica_flutuante()

        def clicar(_e):
            self._esconder_dica_flutuante()
            acao()
            return "break"

        botao.cor_normal = cor
        botao.caixa = caixa
        botao.dica = dica
        for w in (caixa, botao):
            w.bind("<Enter>", entrar)
            w.bind("<Leave>", sair)
            w.bind("<ButtonRelease-1>", clicar)
        caixa.botao = botao
        self._botoes.append((nome or texto, caixa))
        return caixa

    def _mostrar_dica_flutuante(self, alvo, texto: str) -> None:
        self._esconder_dica_flutuante()
        if not texto or not self.persistir:
            return
        dica = tk.Toplevel(self)
        dica.overrideredirect(True)
        dica.attributes("-topmost", True)
        tk.Label(dica, text=texto, bg=self.t.superficie_alta,
                 fg=self.t.texto, font=self.t.letra("legenda"),
                 padx=ESPACO["meio"], pady=2, bd=1, relief="solid"
                 ).pack()
        dica.update_idletasks()
        x = alvo.winfo_rootx() + alvo.winfo_width() - dica.winfo_width()
        y = alvo.winfo_rooty() + alvo.winfo_height() + 4
        dica.geometry(f"+{max(0, x)}+{y}")
        self._dica_flutuante = dica

    def _esconder_dica_flutuante(self) -> None:
        dica = getattr(self, "_dica_flutuante", None)
        if dica is not None:
            try:
                dica.destroy()
            except tk.TclError:
                pass
            self._dica_flutuante = None

    def botoes_visiveis(self) -> list:
        """[(nome, x, y, largura, altura)] relativos a janela — para teste."""
        self.update()
        saida = []
        for nome, caixa in self._botoes:
            if not caixa.winfo_exists() or not caixa.winfo_ismapped():
                continue
            saida.append((nome, caixa.winfo_rootx() - self.winfo_rootx(),
                          caixa.winfo_rooty() - self.winfo_rooty(),
                          caixa.winfo_width(), caixa.winfo_height()))
        return saida

    def _dica(self, texto) -> None:
        alvo = getattr(self, "_lbl_dica", None)
        if alvo is None or not alvo.winfo_exists():
            return
        alvo.configure(text=texto if texto else self._dica_padrao,
                       fg=self.t.acento_forte if texto else self.t.texto_fraco)

    # ------------------------------------------------------------ modos
    def trocar(self, modo: str, inicial: bool = False) -> None:
        if modo not in preferencias.MODOS:
            modo = "medio"
        antigo = None
        if not inicial and self.modo:
            antigo = (self.winfo_x(), self.winfo_y(), self.winfo_width())
            if modo == "icone" and self.modo != "icone":
                self.prefs["anterior"] = self.modo
        self._parar_animacao()
        for filho in self.winfo_children():
            # O menu e as janelas de detalhe sobrevivem a troca de tamanho.
            if not isinstance(filho, (tk.Menu, tk.Toplevel)):
                filho.destroy()
        self._paineis, self._cena, self._abas = [], None, {}
        self._btn_topo = None
        self._lbl_dica = None
        self._lbl_tarefas = None
        self._botoes = []
        self._esconder_dica_flutuante()
        self.modo = modo
        self.prefs["modo"] = modo

        tela = (self.winfo_screenwidth(), self.winfo_screenheight())
        largura, altura = preferencias.tamanho(modo, tela)
        if antigo is not None:
            # A BORDA DIREITA FICA PARADA: a janela mora no canto direito, e
            # encolher para a esquerda a tiraria de onde o olho procura.
            x, y = antigo[0] + antigo[2] - largura, antigo[1]
        else:
            x, y = self.prefs.get("x"), self.prefs.get("y")
        x, y = preferencias.encaixar(x, y, largura, altura, tela)
        if not self.persistir:
            # A PROVA NAO APARECE NA TELA DE NINGUEM: janela invisivel
            # (alfa zero), que o PrintWindow desenha do mesmo jeito. Fora do
            # monitor nao serve — la o Tk nao pinta e a foto sai preta.
            self.attributes("-alpha", 0.0)
        self.geometry(f"{largura}x{altura}+{x}+{y}")
        try:
            self.attributes("-transparentcolor",
                            CHAVE_TRANSPARENTE if modo == "icone" else "")
        except tk.TclError:
            pass
        self.configure(bg=CHAVE_TRANSPARENTE if modo == "icone"
                       else self.t.borda_forte)
        getattr(self, f"_montar_{modo}")()
        self.coletor.ritmo(escondido=modo == "icone")
        self.coletor.agora()
        if self.estado:
            self._desenhar()
        self._tique(reagendar=False)
        if modo in ("medio", "grande"):
            self._ligar_animacao()
        self.guardar()

    def restaurar(self) -> None:
        anterior = self.prefs.get("anterior") or "medio"
        self.trocar(anterior if anterior != "icone" else "medio")

    def _moldura(self) -> tk.Frame:
        moldura = tk.Frame(self, bg=self.t.fundo)
        moldura.pack(fill="both", expand=True, padx=1, pady=1)
        self._moldura_atual = moldura
        return moldura

    def _barra_titulo(self, pai) -> None:
        barra = tk.Frame(pai, bg=self.t.fundo, height=30)
        barra.pack(fill="x")
        barra.pack_propagate(False)
        # OS BOTOES ENTRAM PRIMEIRO: no `pack`, quem chega antes reserva o
        # espaco. O texto com `expand` fica com o que sobrar, nunca o
        # contrario (era isso que sobrepunha o ✕ ao vizinho).
        botoes = [
            ("✕", "fechar", lambda: self.trocar("icone"),
             "fechar: vira o ícone flutuante (sair de vez: botão direito "
             "no ícone → Fechar de verdade)"),
            ("−", "recolher", lambda: self.trocar("icone"),
             "recolher para o ícone flutuante (clique nele para voltar)"),
            ("▬", "faixa", lambda: self.trocar("mini"),
             "encolher para a faixa"),
            ("⤡" if self.modo == "grande" else "⤢", "tamanho",
             lambda: self.trocar("medio" if self.modo == "grande"
                                 else "grande"),
             "tamanho médio" if self.modo == "grande" else "tamanho grande"),
            ("⟳", "prever", self.prever_agora,
             "prever agora o que sai no próximo horário"),
        ]
        for texto, nome, acao, dica in botoes:
            self._botao(barra, texto, acao, dica, nome=nome).pack(
                side="right", padx=(2, 0), pady=2)
        self._btn_topo = self._botao(barra, "📌", self.alternar_topo,
                                     "sempre por cima (liga/desliga)",
                                     ativo=bool(self.prefs["topo"]),
                                     nome="topo")
        self._btn_topo.pack(side="right", padx=(2, 0), pady=2)
        marca = tk.Label(barra, text="🏘 Vila", bg=self.t.fundo,
                         fg=self.t.texto, font=self.t.letra("secao", "bold"),
                         padx=ESPACO["meio"])
        marca.pack(side="left")
        # O SELO DO AGENDADOR: as tarefas ainda abririam janela preta? Fica
        # na barra porque e a promessa desta janela — o console nao volta.
        self._lbl_tarefas = tk.Label(barra, text="tarefas: …", bg=self.t.fundo,
                                     fg=self.t.texto_apagado, cursor="hand2",
                                     font=self.t.letra("legenda"),
                                     padx=ESPACO["meio"])
        self._lbl_tarefas.pack(side="right")
        self._lbl_tarefas.bind("<Button-1>", lambda _e: self.detalhe_tarefas())
        # `width=1`: o texto nao PEDE espaco, so ocupa o que sobrou.
        self._lbl_dica = tk.Label(barra, text="", bg=self.t.fundo, width=1,
                                  fg=self.t.texto_fraco, anchor="w",
                                  font=self.t.letra("legenda"))
        self._lbl_dica.pack(side="left", fill="x", expand=True)
        self._arrastavel(barra, marca, self._lbl_dica)
        tk.Frame(pai, bg=self.t.borda, height=1).pack(fill="x")

    def _montar_icone(self) -> None:
        tela = tk.Canvas(self, width=56, height=56, bg=CHAVE_TRANSPARENTE,
                         highlightthickness=0, bd=0, cursor="hand2")
        tela.pack(fill="both", expand=True)
        self._icone = {
            "tela": tela,
            "anel": tela.create_oval(3, 3, 53, 53, fill=self.t.superficie_alta,
                                     outline=self.t.borda_forte, width=3),
            "desenho": tela.create_text(28, 29, text="🏘",
                                        font=(self.t.fonte, 20)),
            "selo": tela.create_oval(36, 2, 54, 20, fill=self.t.erro,
                                     outline=self.t.fundo, state="hidden"),
            "numero": tela.create_text(45, 11, text="", fill="#1a0f0f",
                                       font=(self.t.fonte, 8, "bold"),
                                       state="hidden"),
        }
        self._arrastavel(tela, ao_clicar=self.restaurar)

    def _montar_mini(self) -> None:
        moldura = self._moldura()
        linha1 = tk.Frame(moldura, bg=self.t.fundo)
        linha1.pack(fill="x", padx=(ESPACO["meio"], 0), pady=(ESPACO["pouco"], 0))
        self._ponto = tk.Canvas(linha1, width=12, height=12, bg=self.t.fundo,
                                highlightthickness=0)
        self._ponto_item = self._ponto.create_oval(1, 1, 11, 11,
                                                   fill=self.t.texto_apagado,
                                                   outline="")
        self._ponto.pack(side="left")
        # Botoes primeiro (ver `_barra_titulo`), depois o texto com width=1.
        self._botao(linha1, "✕", lambda: self.trocar("icone"),
                    "fechar: vira o ícone flutuante", nome="fechar").pack(
            side="right", padx=(2, 2))
        self._botao(linha1, "−", lambda: self.trocar("icone"),
                    "recolher para o ícone", nome="recolher").pack(
            side="right", padx=(2, 0))
        self._botao(linha1, "⤢", lambda: self.trocar("medio"),
                    "abrir a Vila (tamanho médio)", nome="tamanho").pack(
            side="right", padx=(2, 0))
        self._mini_frase = tk.Label(linha1, text="lendo…", bg=self.t.fundo,
                                    fg=self.t.texto, anchor="w", width=1,
                                    font=self.t.letra("corpo", "bold"))
        self._mini_frase.pack(side="left", fill="x", expand=True,
                              padx=(ESPACO["pouco"], 0))
        linha2 = tk.Frame(moldura, bg=self.t.fundo)
        linha2.pack(fill="x", padx=ESPACO["meio"])
        self._mini_tempo = tk.Label(linha2, bg=self.t.fundo, fg=self.t.acento,
                                    font=self.t.letra("legenda", "bold"))
        self._mini_tempo.pack(side="left")
        self._mini_alerta = tk.Label(linha2, bg=self.t.fundo, anchor="w",
                                     fg=self.t.texto_fraco, width=1,
                                     font=self.t.letra("legenda"))
        self._mini_alerta.pack(side="left", fill="x", expand=True,
                               padx=(ESPACO["meio"], 0))
        self._arrastavel(moldura, linha1, linha2, self._mini_frase,
                         self._mini_tempo, self._mini_alerta, self._ponto)
        # Duplo clique na faixa abre a Vila: o alvo grande e o texto.
        for w in (self._mini_frase, self._mini_alerta):
            w.bind("<Double-Button-1>", lambda _e: self.trocar("medio"))

    def _montar_medio(self) -> None:
        moldura = self._moldura()
        self._barra_titulo(moldura)
        corpo = tk.Frame(moldura, bg=self.t.fundo)
        corpo.pack(fill="both", expand=True, padx=6, pady=(ESPACO["pouco"], 4))
        self._cena = CenaVila(corpo, self.t, self.detalhe_predio,
                              self._cache_mundo)
        self._cena.canvas.pack()
        proxima = PainelProxima(self, corpo, curto=True)
        proxima.quadro.pack(fill="x", pady=(ESPACO["pouco"], 0))
        agora = PainelAgora(self, corpo, maximo=2, chars=92, com_contas=False)
        agora.quadro.pack(fill="x")
        self._paineis += [proxima, agora]

        abas = tk.Frame(corpo, bg=self.t.fundo)
        abas.pack(fill="x", pady=(ESPACO["pouco"], 0))
        conteudo = tk.Frame(corpo, bg=self.t.fundo)
        conteudo.pack(fill="both", expand=True)
        # ALTURA MINIMA de proposito: a caixa cresce com `expand` ate o fim da
        # janela. Pedindo 5-6 linhas ela passava do que sobra, e o Tk cortava
        # o fundo — justamente as ultimas linhas do terminal.
        paineis = {
            "diario": PainelDiario(self, conteudo, 2),
            "postagem": PainelPostagem(self, conteudo, 2, com_relogio=False),
            "erros": PainelErros(self, conteudo, 2),
            "terminal": PainelTerminal(self, conteudo, 2),
        }
        self._paineis += list(paineis.values())
        for chave, rotulo in ABAS:
            botao = tk.Label(abas, text=rotulo, bg=self.t.fundo,
                             font=self.t.letra("legenda", "bold"),
                             padx=ESPACO["meio"], pady=2, cursor="hand2")
            botao.pack(side="left")
            botao.bind("<Button-1>", lambda _e, c=chave: self.aba(c))
            self._abas[chave] = (botao, paineis[chave])
        self.aba(self.prefs.get("aba") or "diario")

    def aba(self, chave: str) -> None:
        if chave not in self._abas:
            chave = "diario"
        self.prefs["aba"] = chave
        for nome, (botao, painel) in self._abas.items():
            ativo = nome == chave
            botao.configure(fg=self.t.acento if ativo else self.t.texto_fraco,
                            bg=self.t.acento_fundo if ativo else self.t.fundo)
            if ativo:
                painel.quadro.pack(fill="both", expand=True)
                # Preenchido enquanto estava escondido, o terminal nao sabia
                # a propria altura: ao aparecer, vai para as ultimas linhas.
                if isinstance(painel, PainelTerminal):
                    painel._seguir = True
                    painel.caixa.after_idle(painel._ao_fim)
            else:
                painel.quadro.pack_forget()
        self._rotular_abas()

    def _rotular_abas(self) -> None:
        if "erros" in self._abas:
            n = len(self.estado.get("erros") or [])
            botao = self._abas["erros"][0]
            botao.configure(text=f"Erros ({n})" if n else "Erros")
            if n and self.prefs.get("aba") != "erros":
                botao.configure(fg=self.t.erro)

    def _montar_grande(self) -> None:
        moldura = self._moldura()
        self._barra_titulo(moldura)
        # A GAVETA ENTRA ANTES DO CORPO: no `pack`, quem chega primeiro
        # reserva espaco. Empacotada depois de um `expand=True`, ela some.
        gaveta = tk.Frame(moldura, bg=self.t.fundo)
        gaveta.pack(side="bottom", fill="x", padx=6, pady=(0, 6))
        puxador = tk.Frame(gaveta, bg=self.t.fundo)
        puxador.pack(fill="x")
        aberta = bool(self.prefs.get("gaveta"))
        self._botao(puxador, ("▾ " if aberta else "▸ ") + "Terminal",
                    self.alternar_gaveta,
                    "mostra/esconde as saídas do bot, da postagem e das "
                    "histórias").pack(side="left")
        tk.Label(puxador, text="o que antes ficava nas janelas pretas",
                 bg=self.t.fundo, fg=self.t.texto_apagado,
                 font=self.t.letra("legenda")).pack(side="left")
        if aberta:
            terminal = PainelTerminal(self, gaveta, 7)
            terminal.quadro.pack(fill="x")
            self._paineis.append(terminal)

        corpo = tk.Frame(moldura, bg=self.t.fundo)
        corpo.pack(fill="both", expand=True, padx=6, pady=(ESPACO["pouco"], 0))
        esquerda = tk.Frame(corpo, bg=self.t.fundo, width=708)
        esquerda.pack(side="left", fill="y")
        esquerda.pack_propagate(False)
        direita = tk.Frame(corpo, bg=self.t.fundo)
        direita.pack(side="left", fill="both", expand=True,
                     padx=(ESPACO["normal"], 0))

        self._cena = CenaVila(esquerda, self.t, self.detalhe_predio,
                              self._cache_mundo)
        self._cena.canvas.pack(anchor="w")
        proxima = PainelProxima(self, esquerda)
        proxima.quadro.pack(fill="x", pady=(ESPACO["pouco"], 0))
        tk.Label(esquerda, text="AGORA", bg=self.t.fundo,
                 fg=self.t.texto_fraco, anchor="w",
                 font=self.t.letra("legenda", "bold")).pack(
            fill="x", pady=(ESPACO["meio"], 0))
        agora = PainelAgora(self, esquerda, maximo=6, chars=96)
        agora.quadro.pack(fill="x")
        tk.Label(esquerda, text="DIÁRIO (mais novo em cima)",
                 bg=self.t.fundo, fg=self.t.texto_fraco, anchor="w",
                 font=self.t.letra("legenda", "bold")).pack(
            fill="x", pady=(ESPACO["meio"], 0))
        diario = PainelDiario(self, esquerda, 4)
        diario.quadro.pack(fill="both", expand=True, pady=(0, ESPACO["pouco"]))

        postagem = PainelPostagem(self, direita, 4)
        postagem.quadro.pack(fill="both", expand=True)
        erros = PainelErros(self, direita, 5)
        erros.quadro.pack(fill="x", pady=(ESPACO["meio"], ESPACO["pouco"]))
        self._paineis += [proxima, agora, diario, postagem, erros]

    def alternar_gaveta(self) -> None:
        self.prefs["gaveta"] = not self.prefs.get("gaveta")
        self.trocar("grande")

    # ---------------------------------------------------------- animacao
    def _ligar_animacao(self) -> None:
        self._parar_animacao()
        self._animacao = self.after(ANIMACAO_MS, self._animar)

    def _parar_animacao(self) -> None:
        if self._animacao is not None:
            try:
                self.after_cancel(self._animacao)
            except tk.TclError:
                pass
            self._animacao = None

    def _animar(self) -> None:
        self._animacao = None
        if self._cena is None or not self._vivo:
            return
        # So anima o que se ve: janela recolhida pelo Windows nao desenha.
        if self.state() == "normal" and self.winfo_viewable():
            try:
                self._cena.passo()
            except tk.TclError:
                return
        self._animacao = self.after(ANIMACAO_MS, self._animar)

    # ------------------------------------------------------------- dados
    def _drenar(self) -> None:
        if not self._vivo:
            return
        ultimo = None
        mostrar = False
        try:
            while True:
                tipo, valor = self.fila.get_nowait()
                if tipo == "estado":
                    ultimo = valor
                elif tipo == "mostrar":
                    mostrar = True
        except queue.Empty:
            pass
        if mostrar:
            self.mostrar()
        if ultimo is not None:
            self.estado = ultimo
            try:
                self._desenhar()
            except tk.TclError:
                pass
        self.after(FILA_MS, self._drenar)

    def _desenhar(self) -> None:
        estado = self.estado
        resumo = estado.get("resumo") or {}
        nivel = resumo.get("nivel", "calmo")
        cor_nivel = {"erro": self.t.erro, "trabalhando": self.t.acento,
                     "calmo": self.t.ok}.get(nivel, self.t.borda_forte)
        if self.modo != "icone":
            self.configure(bg=self.t.erro if nivel == "erro"
                           else self.t.borda_forte)
        self._dica_padrao = _cortar(resumo.get("frase", ""), 70)
        self._dica(None)
        if self._lbl_tarefas is not None:
            agendador = estado.get("tarefas") or {}
            cor = {True: self.t.ok, False: self.t.erro}.get(
                agendador.get("ok"), self.t.texto_apagado)
            self._lbl_tarefas.configure(
                text=agendador.get("selo") or "tarefas: …", fg=cor)
        if self._cena is not None:
            self._cena.aplicar(estado.get("predios") or {})
        for painel in self._paineis:
            painel.atualizar(estado)
        self._rotular_abas()
        if self.modo == "mini":
            self._ponto.itemconfigure(self._ponto_item, fill=cor_nivel)
            self._mini_frase.configure(text=_cortar(resumo.get("frase"), 36))
            if resumo.get("alerta"):
                self._mini_alerta.configure(
                    text="❗ " + _cortar(resumo["alerta"], 34),
                    fg=self.t.erro)
            else:
                self._mini_alerta.configure(
                    text=_cortar(texto_da_fila(estado), 36),
                    fg=self.t.texto_fraco)
        if self.modo == "icone":
            icone = self._icone
            erros = len(estado.get("erros") or [])
            icone["tela"].itemconfigure(icone["anel"], outline=cor_nivel)
            estado_selo = "normal" if erros else "hidden"
            icone["tela"].itemconfigure(icone["selo"], state=estado_selo)
            icone["tela"].itemconfigure(icone["numero"], state=estado_selo,
                                        text=str(min(erros, 99)))

    def _tique(self, reagendar: bool = True) -> None:
        if not self._vivo:
            return
        agora = datetime.now()
        try:
            for painel in self._paineis:
                painel.tique(agora)
            if self.modo == "mini":
                self._mini_tempo.configure(
                    text=texto_do_proximo(self.estado, agora))
        except tk.TclError:
            pass
        if reagendar:
            self.after(TIQUE_MS, self._tique)

    # ------------------------------------------------------------- acoes
    def prever_agora(self) -> None:
        self.coletor.pedir_previsao()
        self._dica("prevendo o próximo horário (leva uns segundos)…")

    def abrir_painel(self) -> None:
        try:
            from .. import janelas
            janelas.abrir("vila")
        except Exception:                                    # noqa: BLE001
            self._dica("não consegui abrir o painel")

    def detalhe_predio(self, nome: str) -> None:
        info = (self.estado.get("predios") or {}).get(nome) or {}
        linhas = [(f"{dados.emoji(nome)} {dados.rotulo(nome)} — "
                   f"{dados.PREDIOS[nome]['faz']}\n", "forte")]
        status = {"trabalhando": "trabalhando", "erro": "com erro recente",
                  "recente": "com atividade nos últimos minutos",
                  "no_ar": "no ar", "ocioso": "ocioso"}.get(
            info.get("status"), "sem leitura ainda")
        linhas.append((f"estado: {status}\n", ""))
        recente = info.get("recente")
        if recente and not info.get("trabalhos"):
            evento = recente["evento"]
            linhas.append((f"\n· {recente['texto']}  "
                           f"({evento.get('canal') or 'sem canal'})\n",
                           "inicio"))
            linhas.append((f"  há {dados.duracao(recente['ha_s'])} · "
                           f"{evento.get('status', '')} · pid "
                           f"{evento.get('pid', '?')}\n", "fraco"))
        for t in info.get("trabalhos") or []:
            desde = t.get("desde")
            linhas.append((f"\n▶ {t['texto']}  ({t['canal'] or 'sem canal'})\n",
                           "inicio"))
            linhas.append((f"  desde {_hora(desde)} · "
                           f"{dados.duracao(t.get('ha_s'))} · pid {t['pid']}\n",
                           "fraco"))
            if t.get("detalhe"):
                linhas.append((f"  {t['detalhe']}\n", ""))
        if info.get("contas"):
            linhas.append((f"\n⚑ contas em uso: {', '.join(info['contas'])}\n",
                           "acento"))
        erro = info.get("erro")
        if erro:
            linhas.append((f"\n✗ último erro ({_hora(erro.get('quando'))}):\n",
                           "erro"))
            linhas.append((f"  {erro.get('detalhe', '')}\n", ""))
        if len(linhas) == 2:
            linhas.append(("\nnada acontecendo aqui agora.\n", "fraco"))
        self.mostrar_detalhe(dados.rotulo(nome), linhas)

    def detalhe_tarefas(self) -> None:
        from . import tarefas
        agendador = self.estado.get("tarefas")
        if not agendador:
            self._dica("ainda lendo o Agendador…")
            return
        marca = {True: "ok", False: "erro"}.get(agendador.get("ok"), "fraco")
        linhas = [(f"{agendador.get('selo')}\n\n", marca)]
        for linha in tarefas.descrever(agendador).splitlines()[:-2]:
            cor = ("erro" if linha.startswith(("[CONSOLE]", "[QUEBRADA]"))
                   else "ok" if linha.startswith("[ok]") else "")
            linhas.append((linha + "\n", cor))
        linhas.append(("\nSó leitura. Para conferir no terminal: "
                       "python ferramentas/ocultar_consoles.py\n", "fraco"))
        self.mostrar_detalhe("Tarefas do Agendador", linhas)

    def detalhe_erro(self, erro: dict) -> None:
        linhas = [(f"✗ {dados.rotulo(erro['predio'])} — "
                   f"{erro.get('canal') or 'sem canal'}\n", "erro")]
        momento = erro.get("quando")
        linhas.append((f"quando: {momento.strftime('%d/%m %H:%M:%S') if momento else '?'}"
                       f" (há {dados.duracao(erro.get('ha_s'))})\n", "fraco"))
        for chave in ("fabrica", "etapa", "ref", "pid", "dur_s"):
            if erro.get(chave) not in (None, ""):
                linhas.append((f"{chave}: {erro[chave]}\n", "fraco"))
        linhas.append(("\n", ""))
        linhas.append((f"{erro.get('detalhe', '')}\n", ""))
        self.mostrar_detalhe("Erro", linhas)

    def mostrar_detalhe(self, titulo: str, linhas: list) -> None:
        janela = tk.Toplevel(self)
        janela.title(f"{titulo} — Vila")
        janela.configure(bg=self.t.fundo)
        janela.attributes("-topmost", True)
        caixa = _texto(janela, self.t, 12, mono=False)
        caixa.configure(wrap="word", width=64,
                        font=self.t.letra("corpo"), cursor="xterm")
        caixa.pack(fill="both", expand=True, padx=ESPACO["meio"],
                   pady=(ESPACO["meio"], 0))
        caixa.configure(state="normal")
        for texto, marca in linhas:
            caixa.insert("end", texto, (marca,) if marca else ())
        # Selecionavel (para copiar o erro), mas nao editavel.
        caixa.bind("<Key>", lambda e: None if e.state & 0x4 else "break")
        rodape = tk.Frame(janela, bg=self.t.fundo)
        rodape.pack(fill="x", padx=ESPACO["meio"], pady=ESPACO["meio"])
        tk.Button(rodape, text="Fechar", command=janela.destroy,
                  bg=self.t.superficie_alta, fg=self.t.texto, relief="flat",
                  activebackground=self.t.borda_forte, padx=ESPACO["normal"],
                  cursor="hand2").pack(side="right")
        janela.update_idletasks()
        x = max(0, self.winfo_x() - janela.winfo_width() - 8)
        janela.geometry(f"+{x}+{self.winfo_y()}")
        janela.bind("<Escape>", lambda _e: janela.destroy())

    def escutar(self) -> None:
        """Deixa um segundo lancamento trazer ESTA janela de volta."""
        from . import sinal
        try:
            self._escuta = sinal.Escuta(
                self.caminhos.sinal,
                lambda: self.fila.put(("mostrar", None))).iniciar()
        except OSError:
            self._escuta = None

    def mostrar(self) -> None:
        """Volta a janela: sai do icone/faixa e vem para a frente."""
        if self.modo in ("icone", "mini"):
            anterior = self.prefs.get("anterior")
            self.trocar(anterior if anterior in ("medio", "grande")
                        else "medio")
        self.deiconify()
        self.lift()
        # Por cima por um instante, mesmo com "sempre por cima" desligado.
        self.attributes("-topmost", True)
        self.after(1500, self._aplicar_topo)
        try:
            self.focus_force()
        except tk.TclError:
            pass

    def sair(self) -> None:
        self._vivo = False
        self._esconder_dica_flutuante()
        if self._escuta is not None:
            self._escuta.parar()
        self.guardar()
        self.coletor.parar()
        self._parar_animacao()
        self.destroy()


__all__ = ["Janela", "pedacos_da_postagem", "texto_da_fila",
           "texto_do_proximo"]
