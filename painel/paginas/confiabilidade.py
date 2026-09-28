# -*- coding: utf-8 -*-
"""Pagina CONFIABILIDADE: o que foi afirmado hoje, e o que da para provar.

Toda a regra mora em `panorama.confiabilidade` — esta pagina so desenha. E o
mesmo dicionario que o `/confiabilidade` do Telegram formata; se os dois
mostrarem numeros diferentes para o mesmo dia, o defeito esta na fonte, e so
la se conserta.

Por que existe (16/09/2026): 29 videos passaram cinco dias contados como
publicados e estavam como RASCUNHO no canal. Toda tela lia o mesmo ledger
que estava errado. Esta separa as duas perguntas:

    PROVADO      o sistema disse que publicou E tem com que provar
    SEM PROVA    o sistema disse que publicou e nao consegue provar
    VALVULA      saiu mesmo assim, porque nao havia outro video
    CONFERENCIA  o canal, perguntado de fora, concorda com o ledger?

Ao contrario da Auditoria, esta pagina CABE no pulso: a fonte so le ledger,
diario e um json — nenhum mp4 e decodificado. O unico botao que toca a rede
e o de conferir o canal, e ele roda no supervisor, fora da interface.
"""
from __future__ import annotations

import tkinter as tk

from .. import estilo

MARCAS = {True: "✓", False: "✕", None: "·"}
ETIQUETAS = {True: "provado", False: "sem_prova", None: "sem_laudo"}


class Pagina:
    chave = "confiabilidade"
    rotulo = "Confiabilidade"
    icone = "🔒"

    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema
        self._dia = ""

    # ------------------------------------------------------------ montar
    def construir(self, pai) -> None:
        self.o.titulo(pai, "Confiabilidade — o que saiu, e o que dá para provar")

        self.faixa = self.o.rotulo(pai, "lendo…", papel="secao", peso="bold")
        self.faixa.pack(anchor="w", padx=estilo.ESPACO["secao"])
        self.carimbo = self.o.legenda(pai, "")
        self.carimbo.pack(anchor="w", padx=estilo.ESPACO["secao"])

        cartoes = tk.Frame(pai, bg=self.t.fundo)
        cartoes.pack(fill="x", padx=estilo.ESPACO["secao"],
                     pady=(estilo.ESPACO["normal"], 0))
        self._cartoes = {}
        for chave, titulo in (("provado", "PROVADO"),
                              ("sem_prova", "SEM PROVA"),
                              ("valvula", "VÁLVULA"),
                              ("conferencia", "CONFERÊNCIA")):
            cartao = self.o.cartao(cartoes, titulo)
            cartao.pack(side="left", fill="both", expand=True,
                        padx=(0, estilo.ESPACO["meio"]))
            self._cartoes[chave] = self.o.rotulo(
                cartao.corpo, "—", cor="texto_fraco", bg=self.t.superficie,
                justify="left")
            self._cartoes[chave].pack(anchor="w")

        self.o.secao(pai, "O que olhar").pack(
            anchor="w", padx=estilo.ESPACO["secao"],
            pady=(estilo.ESPACO["normal"], estilo.ESPACO["pouco"]))
        self.alertas = self.o.rotulo(pai, "—", cor="texto_fraco",
                                     justify="left")
        self.alertas.pack(anchor="w", padx=estilo.ESPACO["secao"])

        # OS BOTOES SAO EMPACOTADOS ANTES DA TABELA, presos ao rodape. A
        # pagina tem altura fixa (sem rolagem) e o `pack` corta primeiro o
        # que entrou por ultimo: com a tabela antes, numa tela de 1366x768 os
        # botoes seriam os primeiros a sumir — o defeito de 27/08/2026. Assim
        # quem encolhe e a tabela.
        acoes = tk.Frame(pai, bg=self.t.fundo)
        acoes.pack(side="bottom", fill="x", padx=estilo.ESPACO["secao"],
                   pady=estilo.ESPACO["normal"])
        self.o.botao(acoes, "↻  Ler de novo", self.recarregar,
                     tipo="primario").pack(side="left")
        self.o.botao(acoes, "🌐  Conferir o canal agora",
                     self.conferir).pack(side="right")

        self.o.secao(pai, "Publicações de hoje").pack(
            anchor="w", padx=estilo.ESPACO["secao"],
            pady=(estilo.ESPACO["normal"], estilo.ESPACO["pouco"]))
        # Altura 7: a tela dele e 1366x768, e a pagina ainda tem cartoes e
        # alertas acima da tabela.
        colunas = [("prova", "", 36, "center"),
                   ("hora", "HORA", 56, "center"),
                   ("canal", "CANAL", 90, "w"),
                   ("destino", "DESTINO", 80, "w"),
                   ("qualidade", "NO CLIQUE", 110, "w"),
                   ("video", "VÍDEO", 420, "w")]
        self.tabela = self.o.tabela(pai, colunas, altura=7, estica="video")
        self.tabela.pack(fill="both", expand=True,
                         padx=estilo.ESPACO["secao"])
        self.tabela.tag_configure("provado", foreground=self.t.ok)
        self.tabela.tag_configure("sem_prova", foreground=self.t.erro)
        self.tabela.tag_configure("sem_laudo", foreground=self.t.texto_fraco)
        self._acoes = acoes

    # -------------------------------------------------------------- dados
    def ao_mostrar(self) -> None:
        self.recarregar()

    def ao_esconder(self) -> None:
        """Nada a desligar: a pagina nao tem animacao nem laco proprio."""

    def atualizar(self, resumo: dict) -> None:
        """Vem do pulso: a fonte so le disco leve, entao cabe nele."""
        self._desenhar((resumo or {}).get("confiabilidade"))

    def recarregar(self) -> None:
        self.faixa.configure(text="lendo…", fg=self.t.texto_fraco)
        self.casca.supervisor.tarefa(_ler, self._desenhar,
                                     rotulo="confiabilidade")

    def conferir(self) -> None:
        """Pergunta ao YouTube. Rede: roda no supervisor, nunca na tela."""
        self.faixa.configure(text="conferindo o canal…",
                             fg=self.t.texto_fraco)
        self.casca.supervisor.tarefa(_conferir, lambda _r: self.recarregar(),
                                     rotulo="conferencia")

    def _desenhar(self, dados) -> None:
        if not isinstance(dados, dict) or dados.get("erro"):
            self.faixa.configure(
                text=f"não consegui ler: {(dados or {}).get('erro', '?')}",
                fg=self.t.erro)
            return
        self._dia = str(dados.get("dia") or "")
        alertas = dados.get("alertas") or []
        prometido = dados.get("prometido", 0)
        provado = dados.get("provado", 0)
        if alertas:
            self.faixa.configure(
                text=f"⚠ {provado}/{prometido} com prova — "
                     f"{len(alertas)} coisa(s) para olhar", fg=self.t.aviso)
        else:
            self.faixa.configure(
                text=f"✓ {provado}/{prometido} com prova — nada fora do lugar",
                fg=self.t.ok)
        self.carimbo.configure(
            text=f"dia {self._dia}  ·  lido às "
                 f"{str(dados.get('quando'))[11:19]}")

        # As falhas ficam neste cartao, e nao no de SEM PROVA: falha nao e
        # publicacao — o video nao saiu, entao nao ha o que provar.
        self._cartoes["provado"].configure(
            text=f"{provado} de {prometido}\n"
                 f"{dados.get('sem_campo', 0)} sem laudo (não sei)\n"
                 f"falhou: TikTok {dados.get('falhas_tiktok', 0)} · "
                 f"YouTube {dados.get('falhas_youtube', 0)}")
        self._cartoes["sem_prova"].configure(
            text=f"{dados.get('sem_prova', 0)} sem prova\n"
                 f"{dados.get('fora_de_hd', 0)} antes do processamento\n"
                 f"{dados.get('barra_nao_entendida', 0)} barra não entendida")
        valvula = dados.get("valvula") or []
        self._cartoes["valvula"].configure(
            text=f"abriu {len(valvula)} vez(es)\n"
                 + "\n".join(f"{v.get('hora', '')} {v.get('marca', '')}"
                             for v in valvula[:2]))
        self._cartoes["conferencia"].configure(
            text="\n".join(_linha_da_conferencia(canal, conf)
                           for canal, conf in
                           (dados.get("conferencia") or {}).items()) or "—")

        self.alertas.configure(
            text="\n".join(f"•  {a}" for a in alertas) or "nada",
            fg=self.t.aviso if alertas else self.t.texto_fraco)

        self.tabela.delete(*self.tabela.get_children())
        for n, pub in enumerate(dados.get("publicacoes") or []):
            prova = pub.get("prova_ok") if pub.get("tem_laudo") else None
            self.tabela.insert(
                "", "end", iid=f"p{n}",
                values=[MARCAS.get(prova, "·"), pub.get("hora", ""),
                        pub.get("canal", ""), pub.get("plataforma", ""),
                        pub.get("qualidade") or "—",
                        str(pub.get("video_id") or "")],
                tags=(ETIQUETAS.get(prova, "sem_laudo"),))


def _linha_da_conferencia(canal: str, conf: dict) -> str:
    """Uma linha por canal: o ledger contra o canal E a grade do dia.

    Ate 28/09/2026 a linha era so o veredito do ledger, e o canal que cumpriu
    5 de 10 horarios aparecia como "✓ 5/5" — ledger coerente com a grade
    furada. O ✓ agora exige as duas coisas.
    """
    conf = conf or {}
    estado = conf.get("estado", "?")
    grade = conf.get("grade")
    placar = (f"grade {conf.get('horarios_cumpridos', 0)}/"
              f"{conf.get('slots_da_grade', 0)}" if grade else "")
    if estado == "sujo":
        return (f"{canal}: ✕ {conf.get('fantasmas', 0)} fant., "
                f"{conf.get('rascunhos', 0)} rasc."
                + (f" · {placar}" if placar else ""))
    if estado == "limpo":
        ledger = f"{conf.get('casados', 0)}/{conf.get('no_ledger', 0)}"
        if grade == "em falta":
            return f"{canal}: ✕ {placar} · ledger ✓ {ledger}"
        return f"{canal}: ✓ {ledger}" + (f" · {placar}" if placar else "")
    if estado == "falhou":
        return f"{canal}: não rodou"
    return f"{canal}: {estado}"


def _ler() -> dict:
    import panorama
    return panorama.resumo(forcar=True).get("confiabilidade") or {}


def _conferir():
    from builds.publicar import conferencia
    return conferencia.conferir_tudo(log=lambda _texto: None)
