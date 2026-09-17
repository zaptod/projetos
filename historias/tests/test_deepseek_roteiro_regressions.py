# -*- coding: utf-8 -*-
"""DeepSeek ESCREVE, Gemini e ChatGPT ANALISAM (decisao de 16/09/2026).

O que este arquivo trava:

1. PAPEIS. O nome do provedor mora no `config/llm.json`; config ausente ou
   torto volta ao comportamento de antes.
2. QUEDA. Se o DeepSeek falha, o Gemini assume — COMECANDO se nada foi
   criado, RETOMANDO se ja ha partes. Cada parte guarda quem a escreveu, e
   cada queda fica no roteiro e no diario.
3. TEXTO. O raciocinio do DeepThink nunca vira narracao, e o markdown
   carregado do DeepSeek passa pelo mesmo parser tolerante.

Nenhum navegador abre aqui: todo cliente e duble.

Rode de dentro de historias/:
    python -m unittest tests.test_deepseek_roteiro_regressions -v
"""
from __future__ import annotations

import contextlib
import json
import tempfile
import unittest
from pathlib import Path

from contos.llm import cliente as llm_cliente                      # noqa: E402
from contos.llm import papeis                                      # noqa: E402
from contos.llm import seletores                                   # noqa: E402
from contos.llm.texto import limpar_resposta                       # noqa: E402
from contos.roteiro import gerar as G                              # noqa: E402
from contos.roteiro import roteiro as R                            # noqa: E402
from contos.roteiro import serie as S                              # noqa: E402


def _escrever_json(pasta: Path, dados) -> Path:
    caminho = pasta / "llm.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


class Papeis(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)

    def test_sem_arquivo_vale_o_comportamento_de_antes(self):
        dados = papeis.carregar(self.pasta / "nao_existe.json")
        self.assertEqual(["gemini"], dados[papeis.ROTEIRO])
        self.assertEqual(["gemini", "chatgpt"], dados[papeis.QUALIDADE])

    def test_arquivo_ilegivel_vale_o_padrao(self):
        caminho = self.pasta / "llm.json"
        caminho.write_text("{quebrado", encoding="utf-8")
        self.assertEqual(papeis.PADRAO, papeis.carregar(caminho))

    def test_nome_desconhecido_e_repetido_saem(self):
        caminho = _escrever_json(self.pasta, {"papeis": {
            "roteiro": ["DeepSeek", "grok", "deepseek", " gemini "]}})
        self.assertEqual(["deepseek", "gemini"],
                         papeis.carregar(caminho)[papeis.ROTEIRO])

    def test_lista_vazia_nao_apaga_o_papel(self):
        caminho = _escrever_json(self.pasta, {"papeis": {"roteiro": ["x"]}})
        self.assertEqual(["gemini"], papeis.carregar(caminho)[papeis.ROTEIRO])

    def test_preferido_vem_primeiro_sem_repetir(self):
        self.assertEqual(["gemini", "deepseek"],
                         papeis.com_preferido("gemini", ["deepseek", "gemini"]))
        self.assertEqual(["deepseek", "gemini"],
                         papeis.com_preferido(None, ["deepseek", "gemini"]))
        self.assertEqual(["deepseek", "gemini"],
                         papeis.com_preferido("fake", ["deepseek", "gemini"]))

    def test_o_config_de_verdade_segue_a_decisao(self):
        dados = papeis.carregar()
        self.assertEqual("deepseek", dados[papeis.ROTEIRO][0])
        self.assertIn("gemini", dados[papeis.ROTEIRO],
                      "sem o Gemini nao ha para onde cair")
        self.assertNotIn("deepseek", dados[papeis.QUALIDADE],
                         "quem escreve nao julga")
        self.assertIn("deepthink", papeis.ajustes("deepseek"))

    def test_ajustes_de_provedor_sem_bloco(self):
        self.assertEqual({}, papeis.ajustes("chatgpt",
                                            self.pasta / "nao_existe.json"))


class _Base(unittest.TestCase):
    """OUTPUTS num temporario e as duas etapas do gerador dubladas."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        for modulo in (R, G):
            self.addCleanup(setattr, modulo, "OUTPUTS", modulo.OUTPUTS)
            modulo.OUTPUTS = self.pasta
        self.chamadas = []
        self.falhas = {}
        for nome in ("gerar_serie", "retomar_serie"):
            self.addCleanup(setattr, G, nome, getattr(G, nome))
        G.gerar_serie = self._gerar
        G.retomar_serie = self._retomar

    def _salvar(self, historia_id, partes_escritas, provedor, total=3):
        biblia = {"titulo": "A serie", "partes_esperadas": total,
                  "partes": [{"n": k} for k in range(1, total + 1)]}
        partes = [{"n": k, "titulo": f"P{k}", "cliffhanger": "", "cta": "",
                   "cenas": [{"n": 1, "imagem": "x", "tempo": 4,
                              "narracao": "fala"}],
                   "provedor": provedor}
                  for k in range(1, partes_escritas + 1)]
        R.salvar_serie(biblia, partes, historia_id, provedor=provedor)

    def _gerar(self, *, provedor, historia_id=None, **_k):
        self.chamadas.append(("gerar", provedor, historia_id))
        falha = self.falhas.get(provedor)
        if falha:
            exc = RuntimeError(f"{provedor} caiu")
            if falha == "no_meio":
                self._salvar("historia_00077", 1, provedor)
                exc.historia_id = "historia_00077"
            elif falha == "no_fim":
                self._salvar("historia_00077", 3, provedor)
                exc.historia_id = "historia_00077"
            raise exc
        self._salvar("historia_00077", 3, provedor)
        return {"historia_id": "historia_00077", "partes": 3, "cenas": 3,
                "titulo": "A serie"}

    def _retomar(self, historia_id, *, provedor, **_k):
        self.chamadas.append(("retomar", provedor, historia_id))
        if self.falhas.get(provedor):
            raise RuntimeError(f"{provedor} caiu na retomada")
        roteiro = R.carregar(historia_id)
        partes = list(roteiro["partes"])
        for k in R.partes_que_faltam(roteiro):
            partes.append({"n": k, "titulo": f"P{k}", "cliffhanger": "",
                           "cta": "", "cenas": [{"n": 1, "imagem": "x",
                                                 "tempo": 4,
                                                 "narracao": "fala"}],
                           "provedor": provedor})
        biblia = {"titulo": "A serie", "partes_esperadas": 3,
                  "partes": [{"n": k} for k in range(1, 4)]}
        R.salvar_serie(biblia, partes, historia_id, provedor=provedor)
        return {"historia_id": historia_id, "faltam": []}

    def _escrever(self, **k):
        return G.escrever_serie(["deepseek", "gemini"], log=lambda *_a: None,
                                **k)


class QuedaDeProvedor(_Base):

    def test_deepseek_que_escreve_nao_chama_ninguem_mais(self):
        feito = self._escrever()
        self.assertEqual([("gerar", "deepseek", None)], self.chamadas)
        self.assertEqual("historia_00077", feito["historia_id"])
        self.assertEqual([], R.carregar("historia_00077").get("quedas"))

    def test_falha_antes_da_biblia_faz_o_gemini_comecar(self):
        self.falhas["deepseek"] = "antes"
        avisos = []
        self._escrever(ao_falhar=lambda p, e, prox: avisos.append((p, prox)))
        self.assertEqual([("gerar", "deepseek", None),
                          ("gerar", "gemini", None)], self.chamadas)
        self.assertEqual([("deepseek", "gemini")], avisos)

    def test_falha_no_meio_faz_o_gemini_RETOMAR_e_nao_comecar_outra(self):
        self.falhas["deepseek"] = "no_meio"
        feito = self._escrever()
        self.assertEqual(("retomar", "gemini", "historia_00077"),
                         self.chamadas[-1])
        self.assertEqual(3, feito["partes"])
        roteiro = R.carregar("historia_00077")
        self.assertEqual(["deepseek", "gemini", "gemini"],
                         [p["provedor"] for p in roteiro["partes"]])
        (queda,) = roteiro["quedas"]
        self.assertEqual("deepseek", queda["provedor"])
        self.assertEqual("gemini", queda["proximo"])
        self.assertIn("deepseek caiu", queda["erro"])

    def test_falha_depois_da_ultima_parte_nao_reescreve(self):
        self.falhas["deepseek"] = "no_fim"
        feito = self._escrever()
        self.assertEqual([("gerar", "deepseek", None)], self.chamadas)
        self.assertEqual(3, feito["partes"])

    def test_todos_falham_levanta_o_ultimo_erro(self):
        self.falhas.update(deepseek="no_meio", gemini=True)
        with self.assertRaises(RuntimeError) as erro:
            self._escrever()
        self.assertIn("gemini", str(erro.exception))
        quedas = R.carregar("historia_00077")["quedas"]
        self.assertEqual(["deepseek", "gemini"],
                         [q["provedor"] for q in quedas])
        self.assertIsNone(quedas[-1]["proximo"])

    def test_retomada_comeca_por_quem_escreveu(self):
        self._salvar("historia_00077", 1, "deepseek")
        G.escrever_serie(papeis.com_preferido("deepseek", ["gemini"]),
                         historia_id="historia_00077", log=lambda *_a: None)
        self.assertEqual([("retomar", "deepseek", "historia_00077")],
                         self.chamadas)

    def test_so_o_ultimo_espera_a_conta_pelo_prazo_cheio(self):
        # Conta ocupada passa ao PROXIMO LIVRE (17/09/2026).
        esperas = []
        real = self._gerar

        def espia(**k):
            esperas.append((k["provedor"], k.get("espera_da_conta")))
            return real(**k)

        G.gerar_serie = espia
        self.falhas.update(deepseek="antes", chatgpt="antes")
        G.escrever_serie(["deepseek", "chatgpt", "gemini"],
                         log=lambda *_a: None)
        self.assertEqual([("deepseek", G.ESPERA_CURTA_S),
                          ("chatgpt", G.ESPERA_CURTA_S),
                          ("gemini", G.ESPERA_DA_CONTA_S)], esperas)
        self.assertLess(G.ESPERA_CURTA_S, 60)

    def test_sem_provedor_e_erro_claro(self):
        with self.assertRaises(G.GeracaoFalhou):
            G.escrever_serie([], log=lambda *_a: None)

    def test_regravar_a_parte_nao_apaga_as_quedas(self):
        self._salvar("historia_00077", 1, "deepseek")
        R.registrar_queda("historia_00077", {"provedor": "deepseek"})
        self._salvar("historia_00077", 2, "gemini")
        self.assertEqual([{"provedor": "deepseek"}],
                         R.carregar("historia_00077")["quedas"])


class OGeradorDeVerdadeDizOndeParou(unittest.TestCase):

    def test_falha_ao_abrir_leva_historia_id_vazio(self):
        # Sem biblia nao ha historia: a queda tem de COMECAR.
        real = llm_cliente.abrir_cliente

        @contextlib.contextmanager
        def quebrado(*_a, **_k):
            raise llm_cliente.LLMFalhou("sem login")
            yield

        llm_cliente.abrir_cliente = quebrado
        self.addCleanup(setattr, llm_cliente, "abrir_cliente", real)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(setattr, G, "OUTPUTS", G.OUTPUTS)
        G.OUTPUTS = Path(tmp.name)
        with self.assertRaises(llm_cliente.LLMFalhou) as erro:
            G.gerar_serie(provedor="deepseek", partes=3, log=lambda *_a: None)
        self.assertIsNone(erro.exception.historia_id)


class ODiarioDaQueda(_Base):

    def test_queda_e_erro_de_quem_caiu_e_ok_de_quem_escreveu(self):
        from contos.pipeline import controller
        registros = []
        atividade = controller._rb_atividade
        self.addCleanup(setattr, atividade, "registrar", atividade.registrar)
        atividade.registrar = lambda *a, **k: registros.append((a, k))
        self.falhas["deepseek"] = "antes"
        pipeline = controller.Pipeline.__new__(controller.Pipeline)
        pipeline.roteiro_config = {}
        pipeline.gerar(provedores=["deepseek", "gemini"], partes=3,
                       log=lambda *_a: None)
        resumo = [(a[0], a[1], k.get("etapa")) for a, k in registros]
        self.assertEqual([("deepseek", "inicio", "roteiro"),
                          ("deepseek", "erro", "roteiro.queda"),
                          ("gemini", "inicio", "roteiro"),
                          ("gemini", "ok", "roteiro")], resumo)
        self.assertIn("gemini assume", registros[1][0][2])

    def test_sem_lista_o_provedor_unico_continua_valendo(self):
        from contos.pipeline import controller
        registros = []
        atividade = controller._rb_atividade
        self.addCleanup(setattr, atividade, "registrar", atividade.registrar)
        atividade.registrar = lambda *a, **k: registros.append(a[:2])
        pipeline = controller.Pipeline.__new__(controller.Pipeline)
        pipeline.roteiro_config = {}
        pipeline.gerar(provedor="chatgpt", partes=3, log=lambda *_a: None)
        self.assertEqual([("gerar", "chatgpt", None)], self.chamadas)
        self.assertEqual([("chatgpt", "inicio"), ("chatgpt", "ok")],
                         registros)


class QuemAnalisa(unittest.TestCase):

    def test_parecer_usa_o_papel_de_qualidade(self):
        from contos.publicar import parecer
        # Quem ASSISTE primeiro (papel video), depois a folha (qualidade).
        self.assertEqual(["gemini", "chatgpt"],
                         parecer.provedores_da_analise())
        self.assertEqual(["chatgpt", "gemini"],
                         papeis.provedores(papeis.QUALIDADE))
        self.assertNotIn("deepseek", parecer.provedores_da_analise())
        self.assertIn(parecer.provedores_da_analise()[0],
                      parecer.ASSISTEM_VIDEO)

    def test_agenda_escreve_com_o_papel_de_roteiro(self):
        from contos.pipeline import agenda
        self.assertEqual(papeis.provedores(papeis.ROTEIRO),
                         agenda.provedores_do_roteiro({"provedor": "chatgpt"}))

    def test_agenda_sem_llm_json_usa_o_provedor_de_antes(self):
        from contos.pipeline import agenda
        self.addCleanup(setattr, papeis, "ARQUIVO", papeis.ARQUIVO)
        papeis.ARQUIVO = Path(tempfile.gettempdir()) / "nao_existe_llm.json"
        self.assertEqual(["chatgpt"],
                         agenda.provedores_do_roteiro({"provedor": "chatgpt"}))

    def test_conserto_de_cena_reescreve_com_quem_analisa(self):
        from contos.pipeline import conserto_de_cena
        usados = []
        real = llm_cliente.abrir_cliente

        @contextlib.contextmanager
        def espiao(provedor, **_k):
            usados.append(provedor)
            raise llm_cliente.LLMFalhou("duble")
            yield

        llm_cliente.abrir_cliente = espiao
        self.addCleanup(setattr, llm_cliente, "abrir_cliente", real)
        conserto_de_cena.reescrever_prompts(
            {"partes": []}, 1, [1], [], log=lambda *_a: None)
        self.assertEqual([papeis.provedores(papeis.QUALIDADE)[0]], usados)


# ------------------------------------------------------------------ texto
# Respostas no ESTILO do DeepSeek (markdown carregado). As respostas REAIS
# entram em `tests/dados/deepseek/` depois do primeiro teste de ponta a
# ponta, conferidas para nao levar dado pessoal.
PARTE_EM_MARKDOWN = """Claro! Aqui está a parte 1:

---

### **TÍTULO:** A porta que não estava na planta

#### CENA 1
- **IMAGEM:** a man in his late thirties opening a narrow door behind a bookshelf, dim light
- **TEMPO:** 4
- **NARRAÇÃO:** Eu achei uma porta que não existia na planta da casa do meu pai.

#### CENA 2
> **IMAGEM:** close-up of a brand new lock on an old wooden door
> **TEMPO:** 3,5
> **NARRAÇÃO:** *A fechadura era nova. Nova demais.*

---
**CTA:** Comenta se você abriria essa porta.
"""

BIBLIA_EM_MARKDOWN = """## **TÍTULO DA SÉRIE:** Eu descobri o que meu pai escondia
**PREMISSA:** Um homem herda a casa do pai e acha uma porta.
**PROTAGONISTA:** Tiago | a man in his late thirties, shaved head

---

### PARTE 1
- **TÍTULO:** A porta
- **RESUMO:** Tiago encontra a porta.
- **GANCHO:** A planta não tem essa porta.
- **CLIFFHANGER:** Tem luz acesa.

### PARTE 2
- **TÍTULO:** A chave
- **RESUMO:** A vizinha entrega a chave.
- **GANCHO:** Ela sabia.
- **CLIFFHANGER:** FINAL - ela sabia o meu nome.
"""


class TextoDoDeepSeek(unittest.TestCase):

    def test_raciocinio_nunca_entra(self):
        texto = ("<think>vou pensar na protagonista</think>\n"
                 "Thought for 12 seconds\n"
                 "Pensou por 8 segundos\n"
                 "TITULO: A porta")
        self.assertEqual("TITULO: A porta", limpar_resposta(texto))

    def test_raciocinio_cortado_no_meio_some_inteiro(self):
        self.assertEqual("TITULO: A porta",
                         limpar_resposta("TITULO: A porta\n<think>e se ela"))

    def test_narracao_que_comeca_com_pensando_fica(self):
        texto = "Pensando bem, eu devia ter desconfiado da minha sogra."
        self.assertEqual(texto, limpar_resposta(texto))

    def test_parte_em_markdown_vira_cenas_com_acento(self):
        roteiro = R.parse(limpar_resposta(PARTE_EM_MARKDOWN))
        self.assertEqual(2, len(roteiro["cenas"]))
        self.assertEqual("Eu achei uma porta que não existia na planta da "
                         "casa do meu pai.", roteiro["cenas"][0]["narracao"])
        self.assertEqual("A fechadura era nova. Nova demais.",
                         roteiro["cenas"][1]["narracao"])
        self.assertEqual(3.5, roteiro["cenas"][1]["tempo"])
        self.assertIn("brand new lock", roteiro["cenas"][1]["imagem"])
        self.assertIn("porta", roteiro["titulo"])

    def test_biblia_em_markdown_vira_partes(self):
        biblia = S.parse_biblia(limpar_resposta(BIBLIA_EM_MARKDOWN), 2)
        self.assertEqual([1, 2], [p["n"] for p in biblia["partes"]])
        self.assertEqual("A chave", biblia["partes"][1]["titulo"])
        self.assertIn("meu pai", biblia["titulo"])

    def test_o_verificador_de_linguagem_ve_o_texto_limpo(self):
        from contos.roteiro import linguagem
        roteiro = R.normalizar({"titulo": "x", "partes": [
            {"n": 1, "cenas": R.parse(limpar_resposta(
                PARTE_EM_MARKDOWN))["cenas"]}]})
        achados = linguagem.conferir(roteiro)
        self.assertEqual([], achados["pare"])


class ClienteDoDeepSeek(unittest.TestCase):

    def _cliente(self):
        return llm_cliente.ClienteLLM("deepseek", None, None,
                                      log=lambda *_a: None)

    def _responder(self, cliente, texto):
        self.addCleanup(setattr, llm_cliente, "_pausa", llm_cliente._pausa)
        llm_cliente._pausa = lambda *a, **k: None
        cliente.enviar = lambda _prompt: None
        cliente.esperar_resposta = lambda _timeout=None: texto

    def test_seletores_tem_o_que_o_cliente_usa(self):
        bloco = seletores.do_provedor("deepseek")
        for chave in ("url", "url_novo_chat", "campo", "enviar", "parar",
                      "resposta", "raciocinio", "logado", "login"):
            self.assertTrue(bloco.get(chave), chave)
        self.assertIn("deepseek", seletores.PROVEDORES)

    def test_a_resposta_passa_pela_limpeza(self):
        cliente = self._cliente()
        self._responder(cliente, "<think>x</think>\n### TITULO: A")
        self.assertEqual("TITULO: A", cliente.perguntar("oi"))

    def test_gemini_nao_passa_pela_limpeza(self):
        cliente = llm_cliente.ClienteLLM("gemini", None, None,
                                         log=lambda *_a: None)
        self._responder(cliente, "### TITULO: A")
        self.assertEqual("### TITULO: A", cliente.perguntar("oi"))

    def test_modelo_fixo_confirmado_e_com_o_raciocinio_no_nome(self):
        cliente = self._cliente()
        cliente._ajustar_raciocinio = lambda: True
        self.assertEqual("DeepSeek (site) + DeepThink",
                         cliente.escolher_modelo())
        self.assertTrue(cliente.modelo_confirmado)
        cliente._ajustar_raciocinio = lambda: None
        self.assertEqual("DeepSeek (site)", cliente.escolher_modelo())
        self.assertFalse(cliente.modelo_confirmado)

    def test_resposta_ignora_o_bloco_de_raciocinio(self):
        vistos = {}

        class Pagina:
            def evaluate(self, script, argumento=None):
                if argumento is not None:
                    vistos["argumento"] = argumento
                    return "a resposta"
                return None

        cliente = self._cliente()
        cliente.page = Pagina()
        self.assertEqual("a resposta", cliente._resposta_atual())
        respostas, pensamentos = vistos["argumento"]
        self.assertIn("ds-assistant-message-main-content", respostas[0])
        self.assertEqual(["div.ds-think-content"], pensamentos)

    def test_deepthink_em_estado_desconhecido_nao_e_clicado(self):
        cliques = []

        class Botao:
            def evaluate(self, _script):
                return None

            def click(self, **_k):
                cliques.append(1)

        cliente = self._cliente()
        self.addCleanup(setattr, seletores, "encontrar", seletores.encontrar)
        seletores.encontrar = lambda *a, **k: Botao()
        self.addCleanup(setattr, papeis, "ajustes", papeis.ajustes)
        papeis.ajustes = lambda _p: {"deepthink": True}
        self.assertIsNone(cliente._ajustar_raciocinio())
        self.assertEqual([], cliques)

    def test_deepthink_null_nao_toca_no_botao(self):
        cliente = self._cliente()
        self.addCleanup(setattr, seletores, "encontrar", seletores.encontrar)
        seletores.encontrar = lambda *a, **k: self.fail("nao devia procurar")
        self.addCleanup(setattr, papeis, "ajustes", papeis.ajustes)
        papeis.ajustes = lambda _p: {"deepthink": None}
        self.assertEqual(cliente.RACIOCINIO_DA_CONTA,
                         cliente._ajustar_raciocinio())
        self.assertTrue(cliente.escolher_modelo().startswith("DeepSeek"))
        self.assertTrue(cliente.modelo_confirmado)

    def test_a_resposta_de_verdade_do_site_so_traz_a_parte_final(self):
        # Trecho real mandado pelo Adrian em 17/09/2026 (um "ola" de teste,
        # sem dado pessoal): raciocinio em ingles num bloco, resposta no outro.
        html = (
            '<div class="ds-message"><span>Pensou por 1 segundo</span>'
            '<div class="e1675d8b ds-think-content"><div class="ds-markdown">'
            '<p>We need answer in Portuguese likely.</p></div></div>'
            '<div class="ds-markdown ds-assistant-message-main-content">'
            '<p>Olá! Como posso ajudar você hoje?</p></div></div>')
        bloco = seletores.do_provedor("deepseek")
        self.assertIn("ds-assistant-message-main-content", bloco["resposta"][0])
        self.assertIn("div.ds-think-content", bloco["raciocinio"])
        self.assertIn("ds-think-content", html)

    def test_deepthink_ligado_sem_querer_e_desligado(self):
        cliques = []

        class Botao:
            def evaluate(self, _script):
                return True

            def click(self, **_k):
                cliques.append(1)

        cliente = self._cliente()
        self.addCleanup(setattr, seletores, "encontrar", seletores.encontrar)
        seletores.encontrar = lambda *a, **k: Botao()
        self.addCleanup(setattr, papeis, "ajustes", papeis.ajustes)
        papeis.ajustes = lambda _p: {"deepthink": False}
        self.assertIs(False, cliente._ajustar_raciocinio())
        self.assertEqual([1], cliques)

    def test_conta_registrada(self):
        import builds.contas as contas
        self.assertIn("deepseek", contas.SERVICOS)
        self.assertEqual("perfil", contas.SERVICOS["deepseek"]["tipo"])


if __name__ == "__main__":
    unittest.main()
