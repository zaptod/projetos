# -*- coding: utf-8 -*-
"""Pagina PUBLICAR: tudo que esta pronto, e PARA ONDE cada coisa vai.

Junta as duas fontes numa lista so (builds e historias), diz por linha se ja
subiu para cada plataforma, e mostra a conta de destino ANTES do clique --
porque publicar no canal errado nao tem desfazer.

O cartao ONDE POSTAR ficava ABAIXO DA DOBRA no painel antigo: o console
comia 130px fixos e a escolha de destino -- justamente a parte que ele pediu
-- so aparecia rolando a pagina. Com o console em gaveta, cabe.
"""
from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from builds import contas as contas_reg
from builds.publicar import catalogo as catalogo_builds
from builds.publicar import youtube as youtube_reg

from .. import estilo

RAIZ = Path(__file__).resolve().parents[2]
RANDOM_BUILDS = RAIZ / "random_builds"
HISTORIAS = RAIZ / "historias"
PY = sys.executable

ORIGENS = {
    "build": ("🎮", "build"), "historia": ("📖", "história"),
    "estreia": ("⚔", "estreia"), "torneio": ("🏆", "torneio"),
}


class Pagina:
    chave = "publicar"
    rotulo = "Publicar"
    icone = "📤"

    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema
        self._itens: dict = {}
        self._ja_publicados: dict = {}

    # ------------------------------------------------------------ montar
    def construir(self, pai) -> None:
        self.o.titulo(pai, "Publicar — tudo que está pronto, e para onde vai")

        filtros = tk.Frame(pai, bg=self.t.fundo)
        filtros.pack(fill="x", padx=estilo.ESPACO["secao"])
        self.o.rotulo(filtros, "Mostrar:", cor="texto_fraco").pack(
            side="left", padx=(0, estilo.ESPACO["meio"]))
        self.combo_origem = self.o.combo(
            filtros, ["tudo", "🎮 builds", "📖 histórias", "⚔ estreias",
                      "🏆 torneios"], "tudo", largura=15)
        self.combo_origem.pack(side="left", padx=(0, estilo.ESPACO["meio"]))
        self.combo_formato = self.o.combo(
            filtros, ["todos os formatos", "celular (9:16)", "normal (16:9)"],
            "celular (9:16)", largura=16)
        self.combo_formato.pack(side="left")
        caixa, self.var_pendentes = self.o.marcador(
            filtros, "só o que ainda não publiquei")
        caixa.configure(command=self.recarregar)
        caixa.pack(side="left", padx=estilo.ESPACO["normal"])
        for combo in (self.combo_origem, self.combo_formato):
            combo.bind("<<ComboboxSelected>>", lambda _e: self.recarregar())
        self.o.botao(filtros, "↻  Atualizar", self.recarregar).pack(
            side="right")
        self.o.botao(filtros, "📂  Pasta de exportação",
                     self.abrir_export).pack(side="right",
                                             padx=estilo.ESPACO["meio"])

        corpo = tk.Frame(pai, bg=self.t.fundo)
        corpo.pack(fill="both", expand=True, padx=estilo.ESPACO["secao"],
                   pady=(estilo.ESPACO["normal"], 0))

        esquerda = tk.Frame(corpo, bg=self.t.fundo)
        esquerda.pack(side="left", fill="both", expand=True)
        self.tabela = self.o.tabela(esquerda, [
            ("onde", "O QUE É", 92, "w"),
            ("titulo", "VÍDEO", 320, "w"),
            ("formato", "FORMATO", 74, "center"),
            ("yt", "YOUTUBE", 86, "center"),
            ("tt", "TIKTOK", 78, "center"),
        ], altura=11, estica="titulo")
        self.tabela.tag_configure("publicado", foreground=self.t.ok)
        self.tabela.tag_configure("pendente", foreground=self.t.aviso)
        self.tabela.pack(fill="both", expand=True)
        self.tabela.bind("<<TreeviewSelect>>", lambda _e: self.mostrar_texto())
        self.tabela.bind("<Double-1>", lambda _e: self.no_arquivo("assistir"))
        self.lbl_conta = self.o.legenda(esquerda, "")
        self.lbl_conta.pack(fill="x", pady=(estilo.ESPACO["pouco"], 0))

        direita = self.o.cartao(corpo)
        direita.pack(side="left", fill="both",
                     padx=(estilo.ESPACO["normal"], 0))
        self.o.secao(direita.corpo, "Título").pack(anchor="w")
        self.txt_titulo = self._caixa(direita.corpo, altura=2)
        self.txt_titulo.pack(fill="x", pady=(estilo.ESPACO["pouco"],
                                             estilo.ESPACO["normal"]))
        self.o.secao(direita.corpo, "Descrição (com as hashtags)").pack(
            anchor="w")
        self.txt_descricao = self._caixa(direita.corpo, altura=8)
        self.txt_descricao.pack(fill="both", expand=True,
                                pady=(estilo.ESPACO["pouco"],
                                      estilo.ESPACO["meio"]))
        linha = tk.Frame(direita.corpo, bg=self.t.superficie)
        linha.pack(fill="x")
        self.o.botao(linha, "💾  Salvar texto", self.salvar_texto).pack(
            side="left")
        self.o.botao(linha, "📋  Copiar", self.copiar_texto).pack(
            side="left", padx=estilo.ESPACO["meio"])
        self.lbl_texto = self.o.legenda(direita.corpo, "",
                                        cor="texto_apagado")
        self.lbl_texto.configure(wraplength=290, justify="left",
                                 bg=self.t.superficie)
        self.lbl_texto.pack(anchor="w", pady=(estilo.ESPACO["meio"], 0))

        self._onde_postar(pai)
        self._rodape(pai)

    def _caixa(self, pai, altura: int):
        return tk.Text(pai, height=altura, width=38,
                       bg=self.t.superficie_alta, fg=self.t.texto,
                       insertbackground=self.t.texto, relief="flat", bd=0,
                       font=self.t.letra("corpo"), wrap="word",
                       highlightthickness=1,
                       highlightbackground=self.t.borda,
                       highlightcolor=self.t.acento)

    def _onde_postar(self, pai) -> None:
        cartao = self.o.cartao(pai, "Onde postar")
        cartao.pack(fill="x", padx=estilo.ESPACO["secao"],
                    pady=(estilo.ESPACO["normal"], estilo.ESPACO["meio"]))
        grade = cartao.corpo

        caixa, self.var_yt = self.o.marcador(grade, "YouTube")
        self.var_yt.set(True)
        caixa.configure(command=self.pintar_botao,
                        font=self.t.letra("corpo", "bold"))
        caixa.grid(row=0, column=0, sticky="w", pady=2)
        self.o.rotulo(grade, "conta:", cor="texto_fraco",
                      bg=self.t.superficie).grid(row=0, column=1, sticky="e",
                                                 padx=(estilo.ESPACO["meio"], 2))
        self.combo_conta_yt = self.o.combo(grade, [], largura=16)
        self.combo_conta_yt.grid(row=0, column=2, sticky="w")
        self.combo_conta_yt.bind("<<ComboboxSelected>>",
                                 lambda _e: self.trocar_conta("youtube"))
        self.o.rotulo(grade, "visibilidade:", cor="texto_fraco",
                      bg=self.t.superficie).grid(row=0, column=3, sticky="e",
                                                 padx=(estilo.ESPACO["normal"], 2))
        atual = (catalogo_builds.carregar_config().get("youtube") or {})
        self.combo_visibilidade = self.o.combo(
            grade, ["public", "unlisted", "private"],
            atual.get("visibilidade", "private"), largura=10)
        self.combo_visibilidade.grid(row=0, column=4, sticky="w")

        caixa, self.var_tt = self.o.marcador(grade, "TikTok")
        caixa.configure(command=self.pintar_botao,
                        font=self.t.letra("corpo", "bold"))
        caixa.grid(row=1, column=0, sticky="w", pady=2)
        self.o.rotulo(grade, "conta:", cor="texto_fraco",
                      bg=self.t.superficie).grid(row=1, column=1, sticky="e",
                                                 padx=(estilo.ESPACO["meio"], 2))
        self.combo_conta_tt = self.o.combo(grade, [], largura=16)
        self.combo_conta_tt.grid(row=1, column=2, sticky="w")
        self.combo_conta_tt.bind("<<ComboboxSelected>>",
                                 lambda _e: self.trocar_conta("tiktok"))
        self.o.legenda(grade, "o TikTok posta de verdade, sem confirmação",
                       cor="texto_apagado").grid(row=1, column=3,
                                                 columnspan=2, sticky="w",
                                                 padx=(estilo.ESPACO["normal"], 0))

        self.btn_enviar = self.o.botao(grade, "🚀  PUBLICAR", self.enviar,
                                       tipo="primario")
        # Sem `weight`: com ele o botao engolia metade da largura da janela.
        # Um botao primario grande demais nao fica mais visivel -- fica
        # desproporcional, e rouba a atencao das contas ao lado, que sao o
        # que precisa ser lido ANTES de clicar.
        self.btn_enviar.grid(row=0, column=5, rowspan=2, sticky="ns",
                             padx=(estilo.ESPACO["secao"], 0))

    def _rodape(self, pai) -> None:
        rodape = tk.Frame(pai, bg=self.t.fundo)
        rodape.pack(fill="x", padx=estilo.ESPACO["secao"],
                    pady=(0, estilo.ESPACO["normal"]))

        arquivo = tk.Frame(rodape, bg=self.t.fundo)
        arquivo.pack(side="left")
        for texto, qual in (("▶  Assistir", "assistir"), ("📁  Pasta", "pasta"),
                            ("📤  Exportar", "exportar")):
            self.o.botao(arquivo, texto,
                         lambda q=qual: self.no_arquivo(q)).pack(
                side="left", padx=(0, estilo.ESPACO["meio"]))

        config = tk.Frame(rodape, bg=self.t.fundo)
        config.pack(side="right")
        self.btn_login_yt = self.o.botao(config, "🔑  Login YouTube Studio",
                                         self.login_youtube_web)
        self.btn_login_yt.pack(side="left", padx=(0, estilo.ESPACO["meio"]))
        self.btn_login_tt = self.o.botao(config, "🔑  Login TikTok",
                                         self.login_tiktok)
        self.btn_login_tt.pack(side="left", padx=(0, estilo.ESPACO["meio"]))
        self.o.botao(config, "🎯  Canais do YouTube", self.canais).pack(
            side="left", padx=(0, estilo.ESPACO["meio"]))
        self.o.botao(config, "📊  Métricas", self.metricas).pack(side="left")

    # ------------------------------------------------------------ dados
    def ao_mostrar(self) -> None:
        self.recarregar()

    def recarregar(self) -> None:
        self.casca.supervisor.tarefa(self._ler, self._desenhar,
                                     rotulo="publicar")

    def _ler(self) -> dict:
        """FORA da thread da interface: toca disco nos dois projetos."""
        builds = [{"id": v.id, "fonte": "builds", "origem": v.origem,
                   "titulo": v.titulo, "perfil": v.perfil, "quando": v.quando,
                   "caminho": str(v.caminho),
                   "descricao": v.descricao_completa,
                   "pendencias": list(v.pendencias or []),
                   "parte": 1, "partes": 1}
                  for v in catalogo_builds.listar()]
        try:
            from contos.publicar import catalogo as catalogo_contos
            historias = [{**h, "fonte": "historias", "pendencias": []}
                         for h in (catalogo_contos.resumo() or [])]
        except Exception:
            historias = []
        return {"itens": builds + historias,
                "publicados": self._publicados()}

    @staticmethod
    def _publicados() -> dict:
        """{(video_id, plataforma): linha} dos DOIS registros.

        Continuam separados de proposito -- sao canais diferentes, com
        analytics diferente. O que faltava era UM caminho de codigo lendo os
        dois.
        """
        mapa = {}
        for caminho in (RANDOM_BUILDS / "outputs/_publicar/publicados.jsonl",
                        HISTORIAS / "outputs/_publicar/publicados.jsonl"):
            try:
                bruto = caminho.read_text(encoding="utf-8")
            except OSError:
                continue
            for linha in bruto.splitlines():
                if not linha.strip():
                    continue
                try:
                    dado = json.loads(linha)
                except ValueError:
                    continue
                if dado.get("url"):
                    mapa[(dado.get("video_id"),
                          dado.get("plataforma") or "youtube")] = dado
        return mapa

    def _desenhar(self, dados: dict) -> None:
        if dados.get("erro"):
            self.casca._registrar(f"[publicar] não li a lista: "
                                  f"{dados['erro']}", "erro")
            return
        self._ja_publicados = dados["publicados"]
        alvo = self.combo_origem.get()
        formato = self.combo_formato.get()
        so_pendentes = self.var_pendentes.get()

        def cabe(item) -> bool:
            origem = item.get("origem") or ""
            for palavra, esperado in (("builds", "build"),
                                      ("histórias", "historia"),
                                      ("estreias", "estreia"),
                                      ("torneios", "torneio")):
                if palavra in alvo and origem != esperado:
                    return False
            if not formato.startswith("todos") \
                    and item.get("perfil") != formato.split()[0]:
                return False
            if so_pendentes and (self._estado(item, "youtube")
                                 or self._estado(item, "tiktok")):
                return False
            return True

        escolhido = self.tabela.selection()
        visiveis = sorted([i for i in dados["itens"] if cabe(i)],
                          key=lambda i: (i.get("quando") or 0), reverse=True)
        self._itens = {i["id"]: i for i in visiveis}
        self.tabela.delete(*self.tabela.get_children())
        for item in visiveis:
            emoji, rotulo = ORIGENS.get(item.get("origem"),
                                        ("•", item.get("origem", "?")))
            titulo = item["titulo"]
            if item.get("partes", 1) > 1:
                titulo = f"{titulo}  ·  parte {item['parte']}/{item['partes']}"
            if item.get("pendencias"):
                titulo = "⚠ " + titulo
            yt, tt = self._marca(item, "youtube"), self._marca(item, "tiktok")
            marcas = ("publicado",) if (yt != "—" and tt != "—") else (
                ("pendente",) if item.get("pendencias") else ())
            self.tabela.insert(
                "", "end", iid=item["id"],
                values=(f"{emoji} {rotulo}", titulo,
                        "9:16" if item.get("perfil") == "celular" else "16:9",
                        yt, tt), tags=marcas)
        if escolhido and self.tabela.exists(escolhido[0]):
            self.tabela.selection_set(escolhido)
        elif visiveis:
            self.tabela.selection_set(visiveis[0]["id"])
        else:
            self.mostrar_texto()

    def _estado(self, item, plataforma):
        return self._ja_publicados.get((item["id"], plataforma))

    def _marca(self, item, plataforma) -> str:
        linha = self._estado(item, plataforma)
        if not linha:
            return "—"
        quando = str(linha.get("quando") or "")
        return f"✓ {quando[8:10]}/{quando[5:7]}" if len(quando) >= 10 else "✓"

    # ---------------------------------------------------------- selecao
    def selecionado(self):
        iid = (self.tabela.selection() or [None])[0]
        if iid is None:
            messagebox.showinfo("Publicar", "Selecione um vídeo na lista.")
            return None
        return self._itens.get(iid)

    def _canal(self, item) -> str:
        return "historias" if item.get("fonte") == "historias" else "builds"

    def canal_atual(self) -> str:
        item = self._itens.get((self.tabela.selection() or [None])[0])
        return self._canal(item) if item else "builds"

    def servico_youtube(self) -> str:
        """Qual login vale HOJE: o perfil do navegador ou o OAuth da API.

        Cobrar o OAuth no modo navegador bloquearia justamente o caminho que
        nao precisa dele.
        """
        try:
            return "youtube" if youtube_reg.modo() == "api" else "youtube_web"
        except Exception:
            return "youtube_web"

    def mostrar_texto(self) -> None:
        item = self._itens.get((self.tabela.selection() or [None])[0])
        for caixa in (self.txt_titulo, self.txt_descricao):
            caixa.configure(state="normal")
            caixa.delete("1.0", "end")
        if item is None:
            self.lbl_texto.configure(text="")
            self.lbl_conta.configure(text="")
            self.pintar_botao()
            return
        for pendencia in item.get("pendencias") or []:
            self.casca._registrar(f"[publicar] {item['id']}: {pendencia}",
                                  "erro")
        self.txt_titulo.insert("1.0", item["titulo"])
        self.txt_descricao.insert("1.0", item.get("descricao") or "")
        de_historia = item.get("fonte") == "historias"
        for caixa in (self.txt_titulo, self.txt_descricao):
            caixa.configure(state="disabled" if de_historia else "normal")
        self.lbl_texto.configure(
            text=("o texto da história vem do roteiro — para mudar, edite o "
                  "roteiro e gere o vídeo de novo."
                  if de_historia else "o texto salvo vale nos dois envios"))
        self.pintar_contas(item)
        self.pintar_botao()

    def pintar_contas(self, item) -> None:
        canal = self._canal(item)
        servico_yt = self.servico_youtube()
        partes = []
        for servico, combo in ((servico_yt, self.combo_conta_yt),
                               ("tiktok", self.combo_conta_tt)):
            combo.configure(values=contas_reg.contas(servico))
            destino = contas_reg.destino(servico, canal)
            combo.set(destino["conta"])
            marca = "✓" if destino["tem_login"] else "✗ sem login"
            herdada = "" if destino["explicita"] else " (herdada)"
            # O NOME DA CONTA nao diz para onde o video vai. O canal, sim --
            # e e o canal que nao tem desfazer.
            quem = destino.get("identidade") or ""
            nome = "youtube" if servico.startswith("youtube") else servico
            partes.append(f"{nome}: {destino['conta']}{herdada} → "
                          f"{quem or 'canal ?'} {marca}")
        repetidos = contas_reg.destinos_repetidos(servico_yt)
        aviso = ""
        if repetidos:
            juntos = "; ".join(" e ".join(c) for c in repetidos.values())
            aviso = f"   ⚠ {juntos} publicam NO MESMO canal"
        self.lbl_conta.configure(text=f"canal {canal}  ·  "
                                      + "   ·   ".join(partes) + aviso)
        self.btn_login_yt.configure(text=f"🔑  Login YouTube Studio ({canal})")
        self.btn_login_tt.configure(text=f"🔑  Login TikTok ({canal})")

    def trocar_conta(self, servico: str) -> None:
        item = self.selecionado()
        if item is None:
            return
        if servico == "youtube":
            servico = self.servico_youtube()
        combo = (self.combo_conta_tt if servico == "tiktok"
                 else self.combo_conta_yt)
        canal = self._canal(item)
        contas_reg.escolher(servico, canal, combo.get())
        self.casca._registrar(f"[contas] {servico} do canal {canal}: "
                              f"{combo.get()}", "fim")
        self.pintar_contas(item)

    def pintar_botao(self) -> None:
        alvos = []
        if self.var_yt.get():
            alvos.append("YOUTUBE")
        if self.var_tt.get():
            alvos.append("TIKTOK")
        self.btn_enviar.configure(
            text="🚀  PUBLICAR NO " + " + ".join(alvos) if alvos
            else "escolha YouTube e/ou TikTok",
            state="normal" if alvos else "disabled")

    # ------------------------------------------------------------ acoes
    def _rb(self, argumentos: list, rotulo: str, cwd=None) -> None:
        self.casca.supervisor.rodar([PY, "-u", "-X", "utf8"] + argumentos,
                                    cwd=cwd or RANDOM_BUILDS, rotulo=rotulo,
                                    depois=self.recarregar)

    def enviar(self) -> None:
        item = self.selecionado()
        if item is None:
            return
        alvos = []
        if self.var_yt.get():
            alvos.append("--youtube")
        if self.var_tt.get():
            alvos.append("--tiktok")
        if not alvos:
            return
        if item.get("fonte") == "historias":
            self._rb(["main.py", "publicar", item["id"]] + alvos
                     + ["--visibilidade", self.combo_visibilidade.get()],
                     f"publicar {item['id']}", cwd=HISTORIAS)
        else:
            self._rb(["main.py", "publicar", item["id"]] + alvos
                     + ["--visibilidade", self.combo_visibilidade.get()],
                     f"publicar {item['id']}")

    def no_arquivo(self, qual: str) -> None:
        item = self.selecionado()
        if item is None:
            return
        caminho = Path(item.get("caminho") or "")
        if qual == "assistir" and caminho.is_file():
            os.startfile(caminho)                            # noqa: S606
        elif qual == "pasta" and caminho.parent.is_dir():
            os.startfile(caminho.parent)                     # noqa: S606
        elif qual == "exportar":
            self._rb(["main.py", "publicar", item["id"], "--exportar"],
                     f"exportar {item['id']}",
                     cwd=HISTORIAS if item.get("fonte") == "historias"
                     else RANDOM_BUILDS)

    def abrir_export(self) -> None:
        try:
            pasta = catalogo_builds.pasta_export()
            if Path(pasta).is_dir():
                os.startfile(pasta)                          # noqa: S606
        except Exception as erro:                            # noqa: BLE001
            self.casca._registrar(f"[publicar] {erro}", "erro")

    def salvar_texto(self) -> None:
        item = self.selecionado()
        if item is None or item.get("fonte") == "historias":
            return
        try:
            catalogo_builds.salvar_texto(
                item["id"], self.txt_titulo.get("1.0", "end").strip(),
                self.txt_descricao.get("1.0", "end").strip())
            self.casca._registrar(f"[publicar] texto de {item['id']} salvo.",
                                  "fim")
        except Exception as erro:                            # noqa: BLE001
            self.casca._registrar(f"[publicar] não salvei: {erro}", "erro")

    def copiar_texto(self) -> None:
        texto = (self.txt_titulo.get("1.0", "end").strip() + "\n\n"
                 + self.txt_descricao.get("1.0", "end").strip())
        self.casca.clipboard_clear()
        self.casca.clipboard_append(texto)
        self.casca._registrar("[publicar] título e descrição copiados.", "fim")

    def login_youtube_web(self) -> None:
        self._rb(["-m", "builds.publicar.youtube_web", "--login",
                  "--canal", self.canal_atual()],
                 f"login no YouTube Studio ({self.canal_atual()})")

    def login_tiktok(self) -> None:
        self._rb(["-m", "builds.publicar.tiktok", "--login",
                  "--canal", self.canal_atual()],
                 f"login no TikTok ({self.canal_atual()})")

    def canais(self) -> None:
        self._rb(["-m", "builds.publicar.youtube_web", "--canais"],
                 "canais do YouTube")

    def metricas(self) -> None:
        self._rb(["main.py", "metricas"], "métricas")


__all__ = ["Pagina"]
