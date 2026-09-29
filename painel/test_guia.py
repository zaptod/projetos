# -*- coding: utf-8 -*-
"""Contratos da janela do guia das IAs (`painel/flutuante/guia/`).

1. DETECTAR. HTML, seletor (CSS/XPath) e texto livre — inclusive a frase
   com aspas que parecia seletor.
2. PREVIA. Uma linha enxuta: tag, id, aria, texto visivel, "+N dentro".
3. SELETOR ROBUSTO. data-testid > id estavel > aria-label > ... > texto; a
   classe gerada e o id do radix NUNCA viram ancora; o botao vence o div
   com o mesmo texto; sem ancora, so a tag com aviso para editar.
4. O JSONL. Append de uma linha inteira; lixo e meia-linha pulados; apagar
   e LAPIDE (o agente do guia le por contagem de linhas — o arquivo nunca
   encolhe); `seletor_sugerido` e o nome que `ias/guia.py` le.
5. CASO ZERO. Sem `_atual.json` a janela monta, cai na primeira IA e diz
   que o agente ainda nao falou; sem `colado.jsonl` a lista diz "nada".
6. A JANELA. Cabe em 1366x768 com todo botao dentro; Ctrl+V cai na caixa
   (com a area de transferencia dublada — nunca a de verdade); gravar
   escreve no `<ia>/guia/colado.jsonl` da IA da vez; o seletor editado
   vence a sugestao; proximo com mensagem grava as duas linhas; apagar
   pede dois cliques; recolher nunca usa iconify/withdraw.
7. A VILA tem o botao que abre o guia.

Rode da raiz:  python -m pytest painel/test_guia.py -q
"""
from __future__ import annotations

import ast
import gc
import json
import tempfile
import tkinter as tk
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from painel.flutuante.caminhos import Caminhos
from painel.flutuante.guia import colado
from painel.flutuante.guia import janela as guia_janela

TEXTAREA_GROK = ('<textarea class="w-full px-2 prose !max-w-none leading-7 '
                 'bg-transparent" aria-label="Pergunte ao Grok qualquer '
                 'coisa" dir="auto" style="height: 28px;"></textarea>')
BOTAO_HASH = ('<button class="css-1x2y3z4 sc-bdVaJa" type="submit" '
              'aria-label="Enviar"><svg><path d="M1 2"/></svg></button>')
DIV_RADIX = ('<div id="radix-:r5:" class="flex"><button class="px-3">'
             'Grok 4</button></div>')
BOTAO_TESTID = ('<button data-testid="composer-plus-btn" class="x8f2Kq" '
                'id="btn-9f8e7d6c"><span>+</span></button>')
DIV_SO_CLASSE = ('<div class="Message_bubble__x8f2K">Você atingiu o limite. '
                 'Tente novamente em 2 horas, ou faça upgrade para o '
                 'SuperGrok agora mesmo.</div>')
EDITAVEL = ('<p contenteditable="true" class="ProseMirror" '
            'id="prompt-textarea" data-placeholder="Pergunte"></p>')
GEMINI = ('<div class="ql-editor ql-blank textarea new-input-ui" '
          'contenteditable="true" role="textbox" aria-multiline="true" '
          'aria-label="Insira um comando para o Gemini" '
          'data-placeholder="Peça ao Gemini"><p><br></p></div>')


class Detectar(unittest.TestCase):
    def test_html_seletor_texto_e_vazio(self):
        self.assertEqual(colado.detectar(TEXTAREA_GROK), "html")
        self.assertEqual(colado.detectar("  <div>\n</div>"), "html")
        self.assertEqual(colado.detectar("button[aria-label='Enviar']"),
                         "seletor")
        self.assertEqual(colado.detectar("#prompt-textarea"), "seletor")
        self.assertEqual(colado.detectar("div > button:has-text(\"Grok 4\")"),
                         "seletor")
        self.assertEqual(colado.detectar('//button[@type="submit"]'),
                         "seletor")
        self.assertEqual(colado.detectar("textarea"), "seletor")
        self.assertEqual(colado.detectar("Não achei o botão"), "texto")
        self.assertEqual(colado.detectar("Enviar"), "texto")
        self.assertEqual(colado.detectar(
            'Deu erro: "Você atingiu o limite diário. Faça upgrade."'),
            "texto")
        self.assertEqual(colado.detectar("Você atingiu o limite: tente "
                                         "de novo"), "texto")
        self.assertEqual(colado.detectar("   "), "")
        self.assertEqual(colado.detectar(None), "")


class Previa(unittest.TestCase):
    def test_html_resume_tag_aria_e_texto(self):
        info = colado.previa(TEXTAREA_GROK)
        self.assertEqual(info["tipo"], "html")
        self.assertEqual(info["tag"], "textarea")
        self.assertEqual(info["aria-label"], "Pergunte ao Grok qualquer coisa")
        self.assertIn("textarea", info["resumo"])
        self.assertIn("«Pergunte ao Grok qualquer coisa»", info["resumo"])
        self.assertNotIn("w-full", info["resumo"])       # classe nao aparece

    def test_html_conta_o_que_tem_dentro_e_o_texto_visivel(self):
        info = colado.previa(DIV_RADIX)
        self.assertEqual(info["elementos"], 2)
        self.assertEqual(info["texto"], "Grok 4")
        self.assertIn("+1 dentro", info["resumo"])
        self.assertIn("#radix-:r5:", info["resumo"])

    def test_script_e_svg_nao_viram_texto_visivel(self):
        html = ('<button><svg><title>icone</title></svg><script>x=1'
                '</script>Enviar</button>')
        self.assertEqual(colado.previa(html)["texto"], "Enviar")

    def test_texto_e_seletor(self):
        longo = "x" * 500
        info = colado.previa(longo)
        self.assertEqual(info["tipo"], "texto")
        self.assertEqual(len(info["resumo"]), colado.LIMITE_PREVIA)
        self.assertTrue(info["resumo"].endswith("…"))
        self.assertTrue(colado.previa("#a").get("resumo").startswith("CSS:"))
        self.assertTrue(colado.previa("//a").get("resumo").startswith("XPath:"))

    def test_html_quebrado_nao_levanta(self):
        info = colado.previa("<div <span aria-label='x'")
        self.assertEqual(info["tipo"], "html")
        self.assertIsInstance(info["resumo"], str)


class SeletorRobusto(unittest.TestCase):
    def test_aria_label_vence_a_classe_tailwind(self):
        seletor, motivo = colado.seletor_robusto(TEXTAREA_GROK)
        self.assertEqual(seletor,
                         "textarea[aria-label='Pergunte ao Grok qualquer coisa']")
        self.assertEqual(motivo, "por aria-label")

    def test_data_testid_vence_tudo_e_o_id_com_hash_e_ignorado(self):
        seletor, motivo = colado.seletor_robusto(BOTAO_TESTID)
        self.assertEqual(seletor, "button[data-testid='composer-plus-btn']")
        self.assertEqual(motivo, "por data-testid")

    def test_id_estavel_vence_o_aria(self):
        seletor, motivo = colado.seletor_robusto(EDITAVEL)
        self.assertEqual(seletor, "#prompt-textarea")
        self.assertEqual(motivo, "por id estável")

    def test_classe_gerada_nunca_e_ancora(self):
        seletor, _ = colado.seletor_robusto(BOTAO_HASH)
        self.assertEqual(seletor, "button[aria-label='Enviar']")
        for html in (BOTAO_HASH, DIV_SO_CLASSE, BOTAO_TESTID, TEXTAREA_GROK):
            seletor, _ = colado.seletor_robusto(html)
            self.assertNotIn("css-", seletor)
            self.assertNotIn("x8f2K", seletor)
            self.assertNotIn(".", seletor.split("[")[0].split(":")[0])

    def test_id_do_radix_e_ignorado_e_o_botao_vence_o_div(self):
        seletor, motivo = colado.seletor_robusto(DIV_RADIX)
        self.assertEqual(seletor, "button:has-text('Grok 4')")
        self.assertEqual(motivo, "pelo texto visível")

    def test_sem_ancora_devolve_a_tag_e_pede_edicao(self):
        seletor, motivo = colado.seletor_robusto(DIV_SO_CLASSE)
        self.assertEqual(seletor, "div")
        self.assertIn("edite", motivo)
        self.assertEqual(colado.seletor_robusto("")[0], "")

    def test_gemini_editavel_por_aria(self):
        seletor, _ = colado.seletor_robusto(GEMINI)
        self.assertEqual(
            seletor, "div[aria-label='Insira um comando para o Gemini']")

    def test_aspas_no_valor_sao_escapadas(self):
        seletor, _ = colado.seletor_robusto(
            "<button aria-label=\"Dave's\">x</button>")
        self.assertEqual(seletor, "button[aria-label='Dave\\'s']")

    def test_parece_gerado(self):
        for nome in ("prompt-textarea", "sendButton", "__next",
                     "composer-plus-btn", "grok-content-area", "email"):
            self.assertFalse(colado.parece_gerado(nome), nome)
        for nome in ("radix-:r5:", ":r1:", "css-1abc", "x8f2Kq",
                     "Message_bubble__x8f2K", "Ab12Cd34", "message-12345",
                     "headlessui-menu-button-:r2:", "", "a9f8e7d6c"):
            self.assertTrue(colado.parece_gerado(nome), nome)


class Jsonl(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.arquivo = self.pasta / "grok" / "guia" / "colado.jsonl"

    def test_item_novo_tem_as_chaves_do_contrato(self):
        agora = datetime(2026, 9, 29, 2, 0, tzinfo=timezone(timedelta(hours=-3)))
        item = colado.item_novo("Grok", "campo_texto", TEXTAREA_GROK,
                                passo="onde escreve",
                                seletor=" textarea[aria-label='x'] ",
                                agora=agora)
        self.assertEqual(item["ia"], "grok")
        self.assertEqual(item["papel"], "campo_texto")
        self.assertEqual(item["tipo"], "html")
        self.assertEqual(item["em"], "2026-09-29T02:00:00-03:00")
        self.assertEqual(item["passo"], "onde escreve")
        self.assertEqual(item["seletor_sugerido"], "textarea[aria-label='x']")
        self.assertNotIn("seletor", item)
        self.assertTrue(item["previa"].startswith("textarea"))
        self.assertTrue(item["id"].startswith("20260929020000-"))
        self.assertNotIn("cortado", item)
        marcador = colado.item_novo("grok", "proximo", "", agora=agora)
        self.assertEqual(marcador["conteudo"], "")
        self.assertEqual(marcador["tipo"], "")
        self.assertNotIn("passo", marcador)

    def test_conteudo_gigante_e_cortado_e_marcado(self):
        item = colado.item_novo("grok", "observacao",
                                "a" * (colado.LIMITE_CONTEUDO + 10))
        self.assertEqual(len(item["conteudo"]), colado.LIMITE_CONTEUDO)
        self.assertTrue(item["cortado"])

    def test_gravar_faz_append_de_uma_linha_por_item(self):
        a = colado.item_novo("grok", "campo_texto", TEXTAREA_GROK)
        b = colado.item_novo("grok", "proximo", "")
        self.assertTrue(colado.gravar_item(self.arquivo, a))
        self.assertTrue(colado.gravar_item(self.arquivo, b))
        linhas = self.arquivo.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(linhas), 2)
        self.assertEqual(json.loads(linhas[0])["papel"], "campo_texto")
        self.assertEqual(json.loads(linhas[1])["papel"], "proximo")
        self.assertEqual([i["id"] for i in colado.ler_itens(self.arquivo)],
                         [a["id"], b["id"]])

    def test_leitura_tolera_lixo_e_meia_linha(self):
        self.arquivo.parent.mkdir(parents=True)
        bom = json.dumps(colado.item_novo("grok", "enviar", "<b>x</b>"))
        self.arquivo.write_text(bom + "\nlixo\n{\"papel\": \n" + bom[:20],
                                encoding="utf-8")
        self.assertEqual(len(colado.ler_itens(self.arquivo)), 1)
        self.assertEqual(colado.ler_itens(self.pasta / "nao.jsonl"), [])

    def test_apagar_e_lapide_e_o_arquivo_nunca_encolhe(self):
        a = colado.item_novo("grok", "campo_texto", TEXTAREA_GROK)
        b = colado.item_novo("grok", "enviar", BOTAO_HASH)
        colado.gravar_item(self.arquivo, a)
        colado.gravar_item(self.arquivo, b)
        self.assertTrue(colado.apagar_item(self.arquivo, a["id"]))
        linhas = colado.ler_linhas(self.arquivo)
        self.assertEqual(len(linhas), 3)             # nada foi reescrito
        self.assertEqual(linhas[2]["papel"], colado.PAPEL_APAGADO)
        self.assertEqual(linhas[2]["alvo"], a["id"])
        self.assertEqual([i["id"] for i in colado.ler_itens(self.arquivo)],
                         [b["id"]])
        self.assertFalse(colado.apagar_item(self.arquivo, a["id"]))
        self.assertFalse(colado.apagar_item(self.arquivo, "nao-existe"))
        # O agente le por contagem de linhas: um item novo depois da lapide
        # cai num indice que ele ainda nao passou.
        c = colado.item_novo("grok", "proximo", "")
        colado.gravar_item(self.arquivo, c)
        self.assertEqual(len(self.arquivo.read_text(
            encoding="utf-8").splitlines()), 4)


class AtualEPrefs(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())

    def test_caso_zero_sem_atual_json(self):
        self.assertIsNone(colado.ler_atual(self.pasta / "_atual.json"))
        (self.pasta / "_atual.json").write_text("{lixo", encoding="utf-8")
        self.assertIsNone(colado.ler_atual(self.pasta / "_atual.json"))
        (self.pasta / "_atual.json").write_text('{"passo": "x"}',
                                                encoding="utf-8")
        self.assertIsNone(colado.ler_atual(self.pasta / "_atual.json"))

    def test_atual_lido_e_normalizado(self):
        (self.pasta / "_atual.json").write_text(json.dumps(
            {"ia": "Gemini", "passo": "onde escreve",
             "desde": "2026-09-29T02:01:19"}), encoding="utf-8")
        atual = colado.ler_atual(self.pasta / "_atual.json")
        self.assertEqual(atual, {"ia": "gemini", "passo": "onde escreve",
                                 "desde": "2026-09-29T02:01:19"})
        agora = datetime(2026, 9, 29, 2, 8, 19)
        self.assertEqual(colado.ha_quanto(atual["desde"], agora), "há 7 min")
        self.assertEqual(colado.ha_quanto("lixo"), "")
        self.assertEqual(colado.hora_curta(atual["desde"]), "02:01")

    def test_prefs_padrao_minimo_e_ida_e_volta(self):
        caminho = self.pasta / "guia.json"
        prefs = colado.ler_prefs(caminho)
        self.assertEqual((prefs["largura"], prefs["altura"]), (400, 660))
        self.assertTrue(prefs["topo"])
        self.assertIsNone(prefs["ia_manual"])
        prefs.update({"largura": 10, "altura": 10, "ia_manual": "xpto",
                      "x": 5, "y": 6, "recolhida": True})
        self.assertTrue(colado.gravar_prefs(caminho, prefs))
        lido = colado.ler_prefs(caminho)
        self.assertEqual((lido["largura"], lido["altura"]),
                         colado.TAMANHO_MINIMO)
        self.assertIsNone(lido["ia_manual"])
        self.assertEqual((lido["x"], lido["y"], lido["recolhida"]),
                         (5, 6, True))


# ====================================================================
class _ComJanela(unittest.TestCase):
    ATUAL: dict | None = None
    IA: str | None = None

    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp())
        self.runtime = Path(tempfile.mkdtemp())
        self.caminhos = Caminhos(raiz=self.raiz, rt=self.runtime)
        if self.ATUAL is not None:
            atual = colado.caminho_atual(self.caminhos.ias)
            atual.parent.mkdir(parents=True, exist_ok=True)
            atual.write_text(json.dumps(self.ATUAL), encoding="utf-8")
        self.app = guia_janela.JanelaGuia(caminhos=self.caminhos, ia=self.IA,
                                          topo=False, persistir=False)
        self.app.update()
        self.addCleanup(gc.collect)
        self.addCleanup(self.__dict__.pop, "app", None)
        self.addCleanup(self._fechar)

    def _fechar(self):
        try:
            self.app.sair()
        except tk.TclError:
            pass

    def colado_de(self, ia: str) -> Path:
        return colado.caminho_colado(self.caminhos.ias, ia)


class CasoZero(_ComJanela):
    """Sem `_atual.json`, sem `colado.jsonl`, sem preferencias."""

    def test_monta_na_primeira_ia_e_diz_que_o_agente_nao_falou(self):
        self.assertIsNone(self.app.atual)
        self.assertEqual(self.app.ia, colado.IAS[0])
        self.assertEqual(self.app.passo, "")
        self.assertIn("sem _atual.json", self.app._lbl_origem.cget("text"))
        self.assertIn("nada colado ainda",
                      self.app.lista.get("1.0", "end"))
        self.assertEqual(self.app._itens, [])

    def test_cabe_em_1366x768_com_todo_botao_dentro(self):
        self.app.update()
        largura, altura = self.app.winfo_width(), self.app.winfo_height()
        self.assertEqual((largura, altura), (400, 660))
        self.assertLessEqual(altura, 768 - 48)
        esperados = {p for p, _ in colado.PAPEIS} | {
            "proximo", "enviar_mensagem", "fechar", "recolher", "topo"}
        self.assertTrue(esperados <= set(self.app._botoes))
        for nome in esperados:
            w = self.app._botoes[nome]
            self.assertTrue(w.winfo_ismapped(), nome)
            x = w.winfo_rootx() - self.app.winfo_rootx()
            y = w.winfo_rooty() - self.app.winfo_rooty()
            self.assertGreaterEqual(x, 0, nome)
            self.assertGreaterEqual(y, 0, nome)
            self.assertLessEqual(x + w.winfo_width(), largura, nome)
            self.assertLessEqual(y + w.winfo_height(), altura, nome)
        # e a lista ainda tem espaco de verdade
        self.assertGreater(self.app.lista.winfo_height(), 80)

    def test_gravar_sem_nada_na_caixa_nao_escreve(self):
        self.assertIsNone(self.app.gravar("campo_texto"))
        self.assertFalse(self.colado_de("grok").exists())
        self.assertIn("cole algo", self.app._lbl_dica.cget("text"))

    def test_ctrl_v_cai_na_caixa_sem_tocar_a_area_de_verdade(self):
        # Tecla gerada nao chega a uma janela sem foco (a prova tem alfa
        # zero e nunca o tem), entao o que se testa e a LIGACAO existir e o
        # que ela chama — com a area de transferencia dublada, nunca a de
        # verdade (o Adrian pode estar copiando um HTML neste instante).
        for alvo in (self.app, self.app.caixa):
            self.assertTrue(alvo.bind_all("<Control-v>") if alvo is self.app
                            else alvo.bind("<Control-v>"))
        with mock.patch.object(self.app, "clipboard_get",
                               return_value=TEXTAREA_GROK):
            self.assertEqual(self.app._colar_atalho(None), "break")
        self.assertEqual(self.app.conteudo(), TEXTAREA_GROK)
        self.assertEqual(self.app._lbl_tipo.cget("text"), "HTML")
        self.assertEqual(self.app.entrada_seletor.get(),
                         "textarea[aria-label='Pergunte ao Grok qualquer coisa']")
        # colar de novo TROCA, nao emenda
        with mock.patch.object(self.app, "clipboard_get",
                               return_value=BOTAO_HASH):
            self.assertEqual(self.app._colar_na_caixa(None), "break")
        self.assertEqual(self.app.conteudo(), BOTAO_HASH)
        # area de transferencia sem texto: avisa e nao quebra
        with mock.patch.object(self.app, "clipboard_get",
                               side_effect=tk.TclError("vazia")):
            self.assertEqual(self.app._colar_na_caixa(None), "break")
        self.assertIn("não tem texto", self.app._lbl_dica.cget("text"))

    def test_colar_e_gravar_escreve_no_jsonl_da_ia(self):
        self.app.colar(TEXTAREA_GROK)
        item = self.app.gravar("campo_texto")
        self.assertIsNotNone(item)
        linhas = colado.ler_itens(self.colado_de("grok"))
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["papel"], "campo_texto")
        self.assertEqual(linhas[0]["tipo"], "html")
        self.assertEqual(linhas[0]["seletor_sugerido"],
                         "textarea[aria-label='Pergunte ao Grok qualquer coisa']")
        self.assertNotIn("passo", linhas[0])
        self.assertEqual(self.app.conteudo(), "")            # caixa limpa
        self.assertEqual(self.app.entrada_seletor.get(), "")
        self.assertIn("(1)", self.app._lbl_lista.cget("text"))
        self.assertIn("É o campo de texto", self.app.lista.get("1.0", "end"))

    def test_seletor_editado_vence_a_sugestao(self):
        self.app.colar(DIV_SO_CLASSE)
        self.assertEqual(self.app.entrada_seletor.get(), "div")
        self.app.entrada_seletor.delete(0, "end")
        self.app.entrada_seletor.insert(0, "div[role='alert']")
        item = self.app.gravar("erro_cota")
        self.assertEqual(item["seletor_sugerido"], "div[role='alert']")
        # e uma colada nova nao apaga o que ele editou
        self.app.entrada_seletor.insert(0, "main ")
        self.app.colar(TEXTAREA_GROK)
        self.assertTrue(self.app.entrada_seletor.get().startswith("main "))

    def test_texto_livre_e_observacao(self):
        self.app.colar("o botão só aparece depois de escrever algo")
        self.assertEqual(self.app._lbl_tipo.cget("text"), "TEXTO")
        self.assertEqual(self.app.entrada_seletor.get(), "")
        item = self.app.gravar("observacao")
        self.assertEqual(item["tipo"], "texto")
        self.assertNotIn("seletor_sugerido", item)

    def test_proximo_com_mensagem_grava_as_duas_linhas(self):
        self.app._focou_mensagem()
        self.app.entrada_mensagem.insert(0, "não achei o botão")
        self.assertIsNotNone(self.app.proximo())
        linhas = colado.ler_itens(self.colado_de("grok"))
        self.assertEqual([l["papel"] for l in linhas],
                         ["mensagem", "proximo"])
        self.assertEqual(linhas[0]["conteudo"], "não achei o botão")
        self.assertEqual(self.app.texto_da_mensagem(), "")
        self.assertIsNone(self.app.enviar_mensagem())        # vazia: nada

    def test_apagar_pede_dois_cliques(self):
        self.app.colar(TEXTAREA_GROK)
        item = self.app.gravar("campo_texto")
        self.assertFalse(self.app.apagar(item["id"]))
        self.assertIn("apagar?", self.app.lista.get("1.0", "end"))
        self.assertEqual(len(colado.ler_itens(self.colado_de("grok"))), 1)
        self.assertTrue(self.app.apagar(item["id"]))
        self.assertEqual(colado.ler_itens(self.colado_de("grok")), [])
        self.assertEqual(len(colado.ler_linhas(self.colado_de("grok"))), 2)
        self.assertIn("(0)", self.app._lbl_lista.cget("text"))

    def test_recolher_vira_faixa_e_volta(self):
        self.app.recolher()
        self.app.update()
        self.assertTrue(self.app.prefs["recolhida"])
        self.assertEqual(self.app.winfo_height(), colado.ALTURA_RECOLHIDA)
        self.assertFalse(self.app.corpo.winfo_ismapped())
        self.assertIn("Grok", self.app._lbl_dica.cget("text"))
        self.app.recolher()
        self.app.update()
        self.assertEqual(self.app.winfo_height(), 660)
        self.assertTrue(self.app.corpo.winfo_ismapped())

    def test_nunca_some_de_vez(self):
        arvore = ast.parse(Path(guia_janela.__file__).read_text(
            encoding="utf-8"))
        chamadas = {getattr(n.func, "attr", "") for n in ast.walk(arvore)
                    if isinstance(n, ast.Call)}
        self.assertFalse(chamadas & {"iconify", "withdraw", "wm_iconify",
                                     "wm_withdraw"})

    def test_prova_nao_escreve_preferencias(self):
        self.app.guardar()
        self.assertFalse(self.caminhos.guia_preferencias.exists())

    def test_escolher_ia_a_mao_e_o_agente_aparecendo_depois(self):
        self.app.escolher_ia("deepseek")
        self.assertEqual(self.app.ia, "deepseek")
        self.app.colar(BOTAO_HASH)
        self.app.gravar("enviar")
        self.assertTrue(self.colado_de("deepseek").exists())
        # o agente comeca a escrever o _atual.json: quem escolheu a mao
        # continua na dele, mas a origem diz onde o agente esta
        atual = colado.caminho_atual(self.caminhos.ias)
        atual.write_text(json.dumps({"ia": "gemini", "passo": "como manda",
                                     "desde": "2026-09-29T02:00:00"}),
                         encoding="utf-8")
        self.app._tique()
        self.assertEqual(self.app.ia, "deepseek")
        self.assertIn("Gemini", self.app._lbl_origem.cget("text"))
        self.app.escolher_ia(None)
        self.assertEqual(self.app.ia, "gemini")
        self.assertEqual(self.app.passo, "como manda")


class SeguindoOAgente(_ComJanela):
    ATUAL = {"ia": "gemini", "passo": "onde escreve",
             "desde": "2026-09-29T02:01:19"}

    def test_cabecalho_e_pasta_sao_da_ia_do_agente(self):
        self.assertEqual(self.app.ia, "gemini")
        self.assertEqual(self.app._lbl_ia.cget("text"), "Gemini ▾")
        self.assertEqual(self.app._lbl_passo.cget("text"), "onde escreve")
        self.assertIn("seguindo o agente", self.app._lbl_origem.cget("text"))
        self.app.colar(GEMINI)
        item = self.app.gravar("campo_texto")
        self.assertEqual(item["ia"], "gemini")
        self.assertEqual(item["passo"], "onde escreve")
        self.assertTrue(self.colado_de("gemini").exists())
        self.assertFalse(self.colado_de("grok").exists())
        marcador = self.app.proximo()
        self.assertEqual(marcador["papel"], "proximo")
        self.assertEqual(marcador["passo"], "onde escreve")

    def test_passo_novo_do_agente_aparece_no_tique(self):
        atual = colado.caminho_atual(self.caminhos.ias)
        atual.write_text(json.dumps({"ia": "gemini", "passo": "como manda",
                                     "desde": "2026-09-29T02:05:00"}),
                         encoding="utf-8")
        self.app._mtime_atual = None                 # forca a releitura
        self.app._tique()
        self.assertEqual(self.app._lbl_passo.cget("text"), "como manda")

    def test_lista_mostra_so_o_que_vale_para_esta_ia(self):
        outro = colado.item_novo("grok", "enviar", BOTAO_HASH)
        colado.gravar_item(self.colado_de("grok"), outro)
        self.app.colar(GEMINI)
        self.app.gravar("resposta")
        self.app._ler_itens(forcar=True)
        self.assertEqual([i["papel"] for i in self.app._itens], ["resposta"])


class IaPelaLinhaDeComando(_ComJanela):
    ATUAL = {"ia": "gemini", "passo": "onde escreve", "desde": None}
    IA = "chatgpt"

    def test_a_ia_pedida_vence_o_agente(self):
        self.assertEqual(self.app.ia, "chatgpt")
        self.assertIn("escolhida a mão", self.app._lbl_origem.cget("text"))


class BotaoNaVila(unittest.TestCase):
    def test_a_vila_tem_o_botao_e_o_item_de_menu(self):
        fonte = Path(guia_janela.__file__).parent.parent / "janela.py"
        codigo = fonte.read_text(encoding="utf-8")
        self.assertIn('"guia", self.abrir_guia', codigo)
        self.assertIn("Abrir o guia das IAs", codigo)
        from painel import janelas
        self.assertTrue(callable(janelas.abrir_guia))


if __name__ == "__main__":
    unittest.main()
