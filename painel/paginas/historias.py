# -*- coding: utf-8 -*-
"""Pagina HISTORIAS: roteiro por IA, imagens, narracao e video.

Projeto separado (pasta `historias/`, pacote `contos`), controlado daqui.
Ha um passo que NAO e automatico de proposito: o roteiro nasce no LLM. O
caminho automatico abre o Chrome e conduz a conversa; o manual monta o
prompt para voce colar onde quiser.

A lista vem do `Pipeline().listar()` por IMPORT DIRETO. Ate 01/09/2026 isto
era um `subprocess` com codigo Python dentro de uma string e ate 120 s de
espera, porque os dois projetos tinham um pacote chamado `src` e este
processo so enxergava um deles. Agora leva 0,3 s.
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from builds import contas as contas_reg

from .. import estilo

RAIZ = Path(__file__).resolve().parents[2]
HISTORIAS = RAIZ / "historias"
PY = sys.executable


class Pagina:
    chave = "historias"
    rotulo = "Histórias"
    icone = "📖"

    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema

    # ------------------------------------------------------------ montar
    def construir(self, pai) -> None:
        self.o.titulo(pai, "Histórias por IA — roteiro, imagens, narração e vídeo")
        if not HISTORIAS.is_dir():
            self.o.rotulo(pai, "A pasta historias/ não existe ao lado do painel.",
                          cor="erro", peso="bold").pack(
                anchor="w", padx=estilo.ESPACO["secao"])
            return

        auto = self.o.cartao(
            pai, "1. Roteiro automático — o browser abre o LLM, planeja a "
                 "série e escreve cada parte")
        auto.pack(fill="x", padx=estilo.ESPACO["secao"])
        linha = tk.Frame(auto.corpo, bg=self.t.superficie)
        linha.pack(anchor="w", fill="x")
        self.o.rotulo(linha, "LLM:", cor="texto_fraco",
                      bg=self.t.superficie).pack(side="left",
                                                 padx=(0, estilo.ESPACO["pouco"]))
        self.combo_llm = self.o.combo(linha, ["chatgpt", "gemini"], "chatgpt",
                                      largura=9)
        self.combo_llm.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        self.var_partes = self._contador(linha, "Partes:", "6", 1, 30)
        self.var_cenas = self._contador(linha, "Cenas/parte:", "14", 4, 40)
        moldura, self.var_tema = self.o.campo(linha, "Tema (opcional):", 24)
        moldura.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        self.o.botao(linha, "🤖  Gerar história", self.gerar,
                     tipo="primario").pack(side="left")
        self.o.botao(linha, "🔑  Login no LLM", self.login).pack(
            side="left", padx=(estilo.ESPACO["meio"], 0))
        self.o.legenda(
            auto.corpo,
            "Cada parte vira um vídeo. Uma janela do Chrome abre e conduz a "
            "conversa: primeiro a bíblia da história, depois cada parte. "
            "Faça o login uma vez por LLM.").pack(
            anchor="w", pady=(estilo.ESPACO["meio"], 0))

        manual = self.o.cartao(
            pai, "1b. Roteiro manual — monte o prompt, cole no LLM que "
                 "quiser, traga a resposta")
        manual.pack(fill="x", padx=estilo.ESPACO["secao"],
                    pady=estilo.ESPACO["meio"])
        linha = tk.Frame(manual.corpo, bg=self.t.superficie)
        linha.pack(anchor="w", fill="x")
        self.o.rotulo(linha, "Modelo:", cor="texto_fraco",
                      bg=self.t.superficie).pack(
            side="left", padx=(0, estilo.ESPACO["meio"]))
        self.combo_modelo = self.o.combo(linha, self._modelos(), largura=14)
        self.combo_modelo.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        self.o.botao(linha, "📋  Gerar prompt e copiar",
                     lambda: self.cli(["prompt", "--copiar"],
                                      "prompt da história")).pack(side="left")
        self.o.botao(linha, "📥  Importar resposta (clipboard)",
                     lambda: self.cli(["roteiro", "--colar"],
                                      "importar roteiro")).pack(
            side="left", padx=(estilo.ESPACO["meio"], 0))

        topo = tk.Frame(pai, bg=self.t.fundo)
        topo.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=(estilo.ESPACO["normal"], estilo.ESPACO["meio"]))
        self.o.secao(topo, "2. Histórias").pack(side="left")
        self.o.legenda(topo, "duplo-clique assiste").pack(
            side="left", padx=estilo.ESPACO["meio"])
        self.o.botao(topo, "↻  Atualizar", self.recarregar).pack(side="right")

        self.tabela = self.o.tabela(pai, [
            ("id", "HISTÓRIA", 128, "w"), ("titulo", "TÍTULO", 300, "w"),
            ("partes", "PARTES", 58, "center"), ("cenas", "CENAS", 54, "center"),
            ("imagens", "IMAGENS", 74, "center"),
            ("videos", "VÍDEOS", 58, "center"),
            ("passo", "PRÓXIMO PASSO", 260, "w"),
        ], altura=8, estica="passo")
        self.tabela.tag_configure("pronta", foreground=self.t.ok)
        self.tabela.tag_configure("faltando", foreground=self.t.aviso)
        self.tabela.pack(fill="both", expand=True, padx=estilo.ESPACO["secao"])
        self.tabela.bind("<Double-1>", lambda _e: self.acao("assistir"))

        acoes = tk.Frame(pai, bg=self.t.fundo)
        acoes.pack(fill="x", padx=estilo.ESPACO["secao"],
                   pady=estilo.ESPACO["normal"])
        self.o.botao(acoes, "▶  Gerar tudo", lambda: self.acao("tudo"),
                     tipo="primario").pack(side="left")
        for texto, qual in (("🖼  Só imagens", "imagens"),
                            ("🎬  Só vídeo", "video"),
                            ("▶  Assistir", "assistir"),
                            ("📁  Pasta", "pasta")):
            self.o.botao(acoes, texto, lambda q=qual: self.acao(q)).pack(
                side="left", padx=(estilo.ESPACO["meio"], 0))
        self.o.botao(acoes, "🚀  Publicar série", self.publicar_serie,
                     tipo="primario").pack(side="right")
        for texto, qual in (("🩺  Vistoriar", "vistoriar"),
                            ("📤  Exportar", "exportar")):
            self.o.botao(acoes, texto, lambda q=qual: self.acao(q)).pack(
                side="right", padx=(0, estilo.ESPACO["meio"]))

    def _contador(self, pai, rotulo: str, inicial: str, minimo: int,
                  maximo: int):
        self.o.rotulo(pai, rotulo, cor="texto_fraco",
                      bg=self.t.superficie).pack(
            side="left", padx=(0, estilo.ESPACO["pouco"]))
        variavel = tk.StringVar(value=inicial)
        tk.Spinbox(pai, from_=minimo, to=maximo, width=4,
                   textvariable=variavel, bg=self.t.superficie_alta,
                   fg=self.t.texto, buttonbackground=self.t.superficie,
                   relief="flat", font=self.t.letra("corpo"),
                   highlightthickness=1,
                   highlightbackground=self.t.borda).pack(
            side="left", padx=(0, estilo.ESPACO["normal"]))
        return variavel

    @staticmethod
    def _modelos() -> list:
        try:
            import json
            config = json.loads(
                (HISTORIAS / "config/roteiro.json").read_text(
                    encoding="utf-8-sig"))
            return sorted(config.get("modelos") or {}) or ["reddit"]
        except Exception:                                    # noqa: BLE001
            return ["reddit"]

    # ------------------------------------------------------------ dados
    def ao_mostrar(self) -> None:
        self.recarregar()

    def recarregar(self) -> None:
        self.casca.supervisor.tarefa(self._ler, self._desenhar,
                                     rotulo="historias")

    @staticmethod
    def _ler():
        from contos.pipeline.controller import Pipeline
        return Pipeline().listar()

    def _desenhar(self, dados) -> None:
        if isinstance(dados, dict) and dados.get("erro"):
            self.casca._registrar(f"[histórias] {dados['erro']}", "erro")
            return
        escolhido = self.tabela.selection()
        self.tabela.delete(*self.tabela.get_children())
        for linha in dados or []:
            imagens = linha.get("imagens") or {}
            faltam = int(imagens.get("faltam") or 0)
            self.tabela.insert(
                "", "end", iid=linha["historia_id"],
                tags=("faltando" if faltam else "pronta",),
                values=(linha["historia_id"], linha.get("titulo", "")[:70],
                        linha.get("n_partes", 1), linha.get("cenas", 0),
                        f"{imagens.get('prontas', 0)}/"
                        f"{imagens.get('total', 0)}",
                        linha.get("videos_prontos", 0),
                        linha.get("proximo_passo", "")))
        if escolhido and self.tabela.exists(escolhido[0]):
            self.tabela.selection_set(escolhido)

    # ------------------------------------------------------------ acoes
    def cli(self, argumentos: list, rotulo: str) -> None:
        self.casca.supervisor.rodar(
            [PY, "-u", "-X", "utf8", "main.py"] + argumentos, cwd=HISTORIAS,
            rotulo=rotulo, depois=self.recarregar)

    def selecionada(self):
        return self.o.selecionado(self.tabela, "Escolha uma história na lista.")

    def gerar(self) -> None:
        try:
            partes = max(1, int(self.var_partes.get() or 6))
            cenas = max(4, int(self.var_cenas.get() or 14))
        except ValueError:
            messagebox.showinfo("Histórias",
                                "Partes e cenas precisam ser números.")
            return
        # Sem dialogo de confirmacao (decisao dele, 31/08: um clique). O aviso
        # vai para o console; a trava por PASTA DE PERFIL impede duas geracoes
        # no mesmo Chrome.
        self.casca._registrar(
            f"[histórias] abrindo o {self.combo_llm.get()} para escrever "
            f"{partes} parte(s) de {cenas} cenas — leva vários minutos; não "
            "mexa na janela do Chrome.")
        argumentos = ["gerar", "--provedor", self.combo_llm.get(),
                      "--partes", str(partes), "--cenas", str(cenas)]
        if self.var_tema.get().strip():
            argumentos += ["--tema", self.var_tema.get().strip()]
        self.cli(argumentos, f"gerar história ({self.combo_llm.get()})")

    def login(self) -> None:
        provedor = self.combo_llm.get()
        messagebox.showinfo(
            "Login no LLM",
            f"Vou abrir o {provedor} numa janela do Chrome.\n\nEntre na sua "
            "conta. Quando o chat aparecer, o login fica salvo no perfil e a "
            "geração automática passa a funcionar.")
        self.cli(["llm", "login", "--provedor", provedor],
                 f"login no {provedor}")

    def acao(self, qual: str) -> None:
        historia = self.selecionada()
        if historia is None:
            return
        pasta = HISTORIAS / "outputs" / historia
        if qual == "pasta":
            if pasta.is_dir():
                os.startfile(pasta)                          # noqa: S606
            return
        if qual == "assistir":
            for nome in ("final_celular.mp4", "final_normal.mp4"):
                if (pasta / nome).is_file():
                    os.startfile(pasta / nome)               # noqa: S606
                    return
            messagebox.showinfo("Assistir",
                                "Esta história ainda não tem vídeo.")
            return
        if qual in ("exportar", "vistoriar"):
            self.cli(["publicar", historia, f"--{qual}"], f"{qual} {historia}")
            return
        self.cli([qual, historia], f"{qual} {historia}")

    def publicar_serie(self) -> None:
        """Um clique: vistoria, sobe as partes na ordem e agenda a sequência.

        A trava olha o login CERTO: no modo navegador o que vale e o perfil
        (`youtube_web`), nao o token da API. Cobrar o OAuth aqui bloquearia
        justamente o caminho que nao precisa dele.
        """
        historia = self.selecionada()
        if historia is None:
            return
        servico = self._servico_youtube()
        if not contas_reg.tem_login(servico, "historias"):
            conta = contas_reg.ativa(servico, "historias")
            messagebox.showinfo(
                "Publicar série",
                f"O YouTube do canal Histórias ('{conta}') ainda não tem "
                "login neste computador.\n\nVá na página Contas e clique em "
                "Entrar / Autorizar.")
            self.casca.mostrar("contas")
            return

        destino = contas_reg.destino(servico, "historias")
        if not destino["explicita"]:
            # Sem conta propria, o registro cai na conta de builds -- e um
            # video de historia no canal de builds e IRREVERSIVEL.
            self.casca._registrar(
                f"[histórias] PAREI: o canal historias não tem conta própria "
                f"de YouTube — subiria em '{destino['conta']}', a de builds. "
                "Escolha em 🔑 Contas.", "erro")
            self.casca.mostrar("contas")
            return

        argumentos = ["publicar", historia, "--serie"]
        tiktok = contas_reg.destino("tiktok", "historias")
        if tiktok["explicita"] and tiktok["tem_login"]:
            argumentos.append("--tiktok")
        else:
            self.casca._registrar(
                "[histórias] TikTok sem conta própria com login no canal "
                "historias — só YouTube desta vez.", "erro")
        self.casca._registrar(
            f"[histórias] publicando {historia}: YouTube agendado de 24 em "
            "24 h" + (" + TikTok" if "--tiktok" in argumentos else "") + ".")
        self.cli(argumentos, f"publicar série {historia}")

    @staticmethod
    def _servico_youtube() -> str:
        try:
            from builds.publicar import youtube
            return "youtube" if youtube.modo() == "api" else "youtube_web"
        except Exception:                                    # noqa: BLE001
            return "youtube_web"


__all__ = ["Pagina"]
