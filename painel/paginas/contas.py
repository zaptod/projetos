# -*- coding: utf-8 -*-
"""Pagina CONTAS: quem publica o que, e onde cada login mora.

Existe porque os dois canais deixaram de compartilhar conta -- publicar a
historia no canal de builds e irreversivel. Cada servico tem uma lista de
contas e uma conta ATIVA por canal; quem precisa de perfil ou credencial
pergunta ao registro, nunca monta o caminho na mao.

E a pagina onde se AGE sobre o paralelismo: a Vila mostra que sete pastas de
perfil sao usadas pelos dois canais ao mesmo tempo (e por isso as duas
coisas nunca rodam juntas); e aqui que se cria a segunda conta que separa
uma da outra.
"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog

from builds import contas as contas_reg

from .. import estilo

RAIZ = Path(__file__).resolve().parents[2]
RANDOM_BUILDS = RAIZ / "random_builds"
HISTORIAS = RAIZ / "historias"
PY = sys.executable


class Pagina:
    chave = "contas"
    rotulo = "Contas"
    icone = "🔑"

    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema

    # ------------------------------------------------------------ montar
    def construir(self, pai) -> None:
        self.o.titulo(pai, "Contas — quem publica o quê, e onde o login mora")

        cred = self.o.cartao(
            pai, "Credenciais do YouTube — do Google Cloud Console, as "
                 "mesmas para todas as contas")
        cred.pack(fill="x", padx=estilo.ESPACO["secao"])
        linha = tk.Frame(cred.corpo, bg=self.t.superficie)
        linha.pack(anchor="w")
        moldura, self.var_cliente = self.o.campo(linha, "client-id:", 30)
        moldura.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        moldura, self.var_segredo = self.o.campo(linha, "client-secret:", 22)
        moldura.pack(side="left")
        self.o.legenda(
            cred.corpo,
            "O client-id/secret é do PROJETO no Google Cloud e vale para "
            "qualquer canal; o que muda por conta é o token, criado no "
            "Autorizar.").pack(anchor="w", pady=(estilo.ESPACO["meio"], 0))

        topo = tk.Frame(pai, bg=self.t.fundo)
        topo.pack(fill="x", padx=estilo.ESPACO["secao"],
                  pady=(estilo.ESPACO["muito"], estilo.ESPACO["meio"]))
        self.o.secao(topo, "Serviços").pack(side="left")
        self.o.legenda(topo, "uma linha por canal").pack(
            side="left", padx=estilo.ESPACO["meio"])
        self.o.botao(topo, "↻  Atualizar", self.recarregar).pack(side="right")

        self.tabela = self.o.tabela(pai, [
            ("servico", "SERVIÇO", 118, "w"),
            ("canal", "CANAL", 96, "w"),
            ("conta", "CONTA ATIVA", 150, "w"),
            ("login", "LOGIN", 70, "center"),
            ("onde", "ONDE FICA", 380, "w"),
        ], altura=11, estica="onde")
        self.tabela.tag_configure("ok", foreground=self.t.ok)
        self.tabela.tag_configure("falta", foreground=self.t.aviso)
        self.tabela.pack(fill="both", expand=True,
                         padx=estilo.ESPACO["secao"])
        self.tabela.bind("<<TreeviewSelect>>", lambda _e: self.selecionou())

        acoes = tk.Frame(pai, bg=self.t.fundo)
        acoes.pack(fill="x", padx=estilo.ESPACO["secao"],
                   pady=estilo.ESPACO["normal"])
        self.o.rotulo(acoes, "Conta:", cor="texto_fraco").pack(
            side="left", padx=(0, estilo.ESPACO["meio"]))
        self.combo = self.o.combo(acoes, [], largura=18)
        self.combo.pack(side="left", padx=(0, estilo.ESPACO["normal"]))
        self.o.botao(acoes, "✓  Usar esta conta", self.usar).pack(side="left")
        self.o.botao(acoes, "➕  Nova conta", self.nova).pack(
            side="left", padx=estilo.ESPACO["meio"])
        self.o.botao(acoes, "🔑  Entrar / Autorizar", self.entrar,
                     tipo="primario").pack(side="left")
        self.o.botao(acoes, "🗑  Esquecer", self.esquecer,
                     tipo="perigo").pack(side="right")

        self.lbl_ajuda = self.o.legenda(pai, "")
        self.lbl_ajuda.pack(fill="x", padx=estilo.ESPACO["secao"],
                            pady=(0, estilo.ESPACO["normal"]))

    # ------------------------------------------------------------ dados
    def ao_mostrar(self) -> None:
        self.recarregar()

    def recarregar(self) -> None:
        if not self.var_cliente.get().strip():
            cliente, segredo = self._credenciais()
            if cliente:
                self.var_cliente.set(cliente)
            if segredo:
                self.var_segredo.set(segredo)
        escolhido = self.tabela.selection()
        self.tabela.delete(*self.tabela.get_children())
        for linha in contas_reg.resumo():
            self.tabela.insert(
                "", "end", iid=f"{linha['servico']}|{linha['canal']}",
                tags=("ok" if linha["logado"] else "falta",),
                values=(linha["rotulo"], linha["canal"], linha["conta"],
                        "sim" if linha["logado"] else "FALTA", linha["onde"]))
        if escolhido and self.tabela.exists(escolhido[0]):
            self.tabela.selection_set(escolhido)
        self.selecionou()

    @staticmethod
    def _credenciais() -> tuple:
        try:
            from builds.publicar.youtube import carregar_credenciais
            salvas = carregar_credenciais()
            return (salvas.client_id, salvas.client_secret) if salvas \
                else ("", "")
        except Exception:                                    # noqa: BLE001
            return "", ""

    def _linha(self):
        escolhido = self.tabela.selection()
        if not escolhido:
            messagebox.showinfo("Contas", "Selecione um serviço na lista.")
            return None
        return escolhido[0].split("|", 1)

    def selecionou(self) -> None:
        escolhido = self.tabela.selection()
        if not escolhido:
            return
        servico, canal = escolhido[0].split("|", 1)
        self.combo.configure(values=contas_reg.contas(servico))
        self.combo.set(contas_reg.ativa(servico, canal))
        dados = contas_reg.SERVICOS.get(servico, {})
        self.lbl_ajuda.configure(
            text=f"{dados.get('rotulo', servico)} · canal {canal}: "
                 f"{dados.get('ajuda', '')}")

    # ------------------------------------------------------------ acoes
    def usar(self) -> None:
        alvo = self._linha()
        if alvo is None:
            return
        servico, canal = alvo
        conta = self.combo.get()
        if not conta:
            return
        contas_reg.escolher(servico, canal, conta)
        self.casca._registrar(f"[contas] {servico} do canal {canal}: agora "
                              f"usa '{conta}'.", "fim")
        self.recarregar()

    def nova(self) -> None:
        alvo = self._linha()
        if alvo is None:
            return
        servico, canal = alvo
        nome = simpledialog.askstring(
            "Nova conta",
            f"Nome da nova conta de "
            f"{contas_reg.SERVICOS[servico]['rotulo']}\n"
            "(só para você identificar: 'historias', 'canal2'...)",
            parent=self.casca)
        if not nome:
            return
        limpo = contas_reg.adicionar(servico, nome)
        contas_reg.escolher(servico, canal, limpo)
        self.casca._registrar(
            f"[contas] conta '{limpo}' criada em {servico} e ativada no canal "
            f"{canal}. Clique em Entrar/Autorizar para fazer o login.", "fim")
        self.recarregar()

    def esquecer(self) -> None:
        alvo = self._linha()
        if alvo is None:
            return
        servico, _canal = alvo
        conta = self.combo.get()
        if conta == contas_reg.PADRAO:
            messagebox.showinfo("Contas",
                                "A conta 'principal' não pode ser removida.")
            return
        if not messagebox.askyesno(
                "Esquecer conta",
                f"Tirar '{conta}' da lista de {servico}?\n\n"
                "O login em disco NÃO é apagado — dá para readicionar depois."):
            return
        contas_reg.remover(servico, conta)
        self.recarregar()

    def entrar(self) -> None:
        """Dispara o login CERTO para o servico e a conta selecionados."""
        alvo = self._linha()
        if alvo is None:
            return
        servico, canal = alvo
        conta = self.combo.get() or contas_reg.ativa(servico, canal)
        if conta != contas_reg.ativa(servico, canal):
            contas_reg.escolher(servico, canal, conta)

        if servico == "youtube":
            self._oauth(canal, conta)
        elif servico == "youtube_web":
            self._abrir(["-m", "builds.publicar.youtube_web", "--login",
                         "--canal", canal], RANDOM_BUILDS,
                        f"login no YouTube Studio ({conta}/{canal})",
                        f"Vou abrir o YouTube Studio para a conta '{conta}' do "
                        f"canal {canal}.\n\nUm login do Google cobre os três "
                        "canais; o que separa um do outro é o id, escolhido "
                        "em 🎯 Canais do YouTube.")
        elif servico in ("chatgpt", "gemini"):
            if not HISTORIAS.is_dir():
                messagebox.showinfo("Contas", "A pasta historias/ não existe.")
                return
            self._abrir(["main.py", "llm", "login", "--provedor", servico],
                        HISTORIAS, f"login no {servico} ({conta})",
                        f"Vou abrir o {servico} numa janela do Chrome.\n\n"
                        "Entre na sua conta. Quando o chat aparecer, o login "
                        "fica salvo e vale para o projeto inteiro.")
        elif servico == "tiktok":
            self._abrir(["-m", "builds.publicar.tiktok", "--login",
                         "--canal", canal], RANDOM_BUILDS,
                        f"login no TikTok ({conta}/{canal})",
                        f"Vou abrir o TikTok para a conta '{conta}' do canal "
                        f"{canal}.\n\nEntre na conta CERTA: é ela que vai "
                        "receber os vídeos desse canal.")
        else:                                    # picasso, digen, dreamface
            self._abrir(["main.py", "identity", "login", "--provedor", servico,
                         "--canal", canal], RANDOM_BUILDS,
                        f"login no {servico} ({conta}/{canal})", "")

    def _abrir(self, argumentos: list, cwd, rotulo: str, aviso: str) -> None:
        if aviso:
            messagebox.showinfo("Login", aviso)
        self.casca.supervisor.rodar([PY, "-u", "-X", "utf8"] + argumentos,
                                    cwd=cwd, rotulo=rotulo,
                                    depois=self.recarregar)

    def _oauth(self, canal: str, conta: str) -> None:
        cliente = self.var_cliente.get().strip()
        segredo = self.var_segredo.get().strip()
        if not (cliente and segredo):
            cliente, segredo = self._credenciais()
        if not (cliente and segredo):
            messagebox.showinfo(
                "Autorizar YouTube",
                "Preencha o client-id e o client-secret no card de cima "
                "(são os dados do seu projeto no Google Cloud Console).")
            return
        # `--out` por conta: sem ele o token do canal de historias
        # SOBRESCREVERIA o de builds, e os dois moram em arquivos diferentes
        # justamente para nao publicar no canal errado.
        destino = contas_reg.credencial_youtube(canal, conta)
        messagebox.showinfo(
            "Autorizar YouTube",
            f"Vou abrir o navegador para autorizar a conta '{conta}'.\n\n"
            "IMPORTANTE: entre com a conta do Google DESTE canal — é ela que "
            "vai receber os vídeos.\n\nMarque as permissões de enviar vídeo e "
            "de estatísticas.")
        # O rotulo NAO leva as credenciais: ele vai para o console, que fica
        # na tela e pode acabar numa captura.
        self.casca.supervisor.rodar(
            [PY, "-u", "-X", "utf8", "-m", "neural_fights.tools.youtube_oauth",
             "--client-id", cliente, "--client-secret", segredo,
             "--com-upload", "--com-analytics", "--out", str(destino)],
            cwd=RAIZ, rotulo=f"autorizar YouTube ({conta}) — credenciais "
                             "ocultas", depois=self.recarregar)


__all__ = ["Pagina"]
