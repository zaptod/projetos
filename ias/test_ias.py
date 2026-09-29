# -*- coding: utf-8 -*-
"""Contratos do pacote `ias`: o schema (caso ZERO incluido), o catalogo de
textos com dublês, a tabela e o protocolo de arquivos da sessao guiada.

Nenhum teste abre navegador nem toca a rede: as funcoes sao puras ou
recebem pastas temporarias (no TEMP da maquina, que o `testar.py` aponta
para o E:).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ias import IAS, catalogo, ficha, guia


class FichaVaziaEhValida(unittest.TestCase):
    """O caso ZERO: uma IA sobre a qual nada foi medido ainda."""

    def test_vazia_passa_na_validacao_para_todas(self):
        for ia in IAS:
            self.assertEqual(ficha.validar(ficha.vazia(ia)), [], ia)

    def test_vazia_nao_supoe_nada(self):
        f = ficha.vazia("gemini")
        self.assertIsNone(f["texto"]["gera"])
        self.assertIsNone(f["imagem"]["gera"])
        self.assertIsNone(f["video"]["assiste"])
        self.assertEqual(f["login"]["estado"], "nao_medido")
        self.assertEqual(f["catalogo_textos"], [])

    def test_tabela_com_fichas_vazias_imprime_tracos(self):
        texto = ficha.tabela([ficha.vazia(ia) for ia in IAS])
        linhas = texto.splitlines()
        self.assertEqual(len(linhas), 2 + len(IAS))
        for linha in linhas[2:]:
            celulas = [c.strip() for c in linha.strip("|").split("|")]
            self.assertTrue(all(c == "—" for c in celulas[1:]), linha)

    def test_carregar_inexistente_devolve_vazia(self):
        with tempfile.TemporaryDirectory() as pasta:
            f = ficha.carregar("grok", Path(pasta))
        self.assertEqual(f["ia"], "grok")
        self.assertEqual(ficha.validar(f), [])

    def test_ficha_sem_ia_e_invalida(self):
        f = ficha.vazia("")
        self.assertTrue(any("de que IA" in p for p in ficha.validar(f)))

    def test_login_fora_dos_estados_e_invalido(self):
        f = ficha.vazia("gemini")
        f["login"]["estado"] = "talvez"
        self.assertTrue(any("login.estado" in p for p in ficha.validar(f)))

    def test_salvar_e_carregar_vao_e_voltam(self):
        f = ficha.vazia("chatgpt")
        f["texto"]["gera"] = True
        f["texto"]["tempo_ok_s"] = 3.2
        f["login"] = {"estado": "logado", "detalhe": "x", "prova": None}
        with tempfile.TemporaryDirectory() as pasta:
            caminho = ficha.salvar(f, Path(pasta))
            self.assertTrue(caminho.is_file())
            lida = ficha.carregar("chatgpt", Path(pasta))
        self.assertEqual(lida["texto"]["tempo_ok_s"], 3.2)
        self.assertEqual(lida["login"]["estado"], "logado")

    def test_salvar_recusa_ficha_torta(self):
        f = ficha.vazia("digen")
        f["catalogo_textos"] = [{"categoria": "inventada", "texto": "x"}]
        with tempfile.TemporaryDirectory() as pasta:
            with self.assertRaises(ficha.FichaInvalida):
                ficha.salvar(f, Path(pasta))

    def test_ficha_antiga_ganha_chaves_novas_ao_carregar(self):
        with tempfile.TemporaryDirectory() as pasta:
            alvo = Path(pasta) / "gemini.json"
            alvo.write_text(json.dumps({"ia": "gemini", "texto": {"gera": True}}),
                            encoding="utf-8")
            f = ficha.carregar("gemini", Path(pasta))
        self.assertTrue(f["texto"]["gera"])
        self.assertIn("catalogo_textos", f)
        self.assertEqual(ficha.validar(f), [])


class TabelaComMedidas(unittest.TestCase):
    def test_colunas_lem_os_campos_certos(self):
        f = ficha.vazia("gemini")
        f["login"]["estado"] = "logado"
        f["texto"].update({"gera": True, "tempo_ok_s": 4.6, "chars_aceitos_no_campo": 120000})
        f["modelos"].update({"ativo": "2.5 Pro", "disponiveis": ["2.5 Pro", "2.5 Flash"]})
        f["anexos"].update({"imagem": True, "video": True, "arquivo": False})
        f["imagem"].update({"gera": True, "resolucao": [1024, 1024], "alfa": False})
        f["video"].update({"assiste": True})
        f["catalogo_textos"] = [catalogo.item("limite", "Você atingiu o limite")]
        f["cota"].update({"plano": "gratuito"})
        linha = ficha.linhas([f])[1]
        self.assertEqual(linha[1], "logado")
        self.assertEqual(linha[2], "5s")
        self.assertEqual(linha[3], "2.5 Pro (+1)")
        self.assertEqual(linha[4], "img, vid, sem arq")
        self.assertEqual(linha[5], "sim 1024x1024")
        self.assertEqual(linha[6], "assiste")
        self.assertEqual(linha[7], "120000 chars")
        self.assertEqual(linha[8], "limite 1")

    def test_tabela_png_grava_arquivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            alvo = ficha.tabela_png([ficha.vazia("grok")], Path(pasta) / "t.png", "teste")
            self.assertTrue(alvo.is_file())
            self.assertGreater(alvo.stat().st_size, 500)


class CatalogoDeTextos(unittest.TestCase):
    """Os dublês: frases reais (dos logs e das memorias) e frases que NAO
    sao aviso. Cada categoria com pelo menos um exemplo nas duas linguas."""

    def test_classifica_as_frases_conhecidas(self):
        casos = {
            "Sou uma IA com base em texto, e isso está além das minhas capacidades": "recusa_enlatada",
            "Não fui programado para fazer isso": "recusa_enlatada",
            "I'm a text-based AI and can't help with that": "recusa_enlatada",
            "Você atingiu o limite de uso do 2.5 Pro. Tente novamente em 4 horas": "limite",
            "You've reached your message limit. Try again after 3:00 PM": "limite",
            "Not enough credits": "limite",
            "Faça upgrade para o Google AI Pro": "upgrade",
            "Upgrade to ChatGPT Plus": "upgrade",
            "Assine para Gerar": "upgrade",
            "Just a moment...": "cloudflare",
            "Um momento…": "cloudflare",
            "Algo deu errado (1155)": "erro_site",
            "Something went wrong": "erro_site",
            "Generation failed": "erro_site",
            "Modelo temporariamente indisponível": "indisponivel",
            "We're experiencing high demand. Try again later": "indisponivel",
            "Confira se você tem os direitos sobre os conteúdos que enviar": "consentimento",
            "This request violates our content policy": "conteudo",
            "Entrar com Google": "login",
        }
        for frase, esperado in casos.items():
            self.assertEqual(catalogo.classificar(frase), esperado, frase)

    def test_nao_classifica_resposta_normal(self):
        for frase in ("OK", "Claro! Aqui está a história que você pediu.",
                      "O círculo é vermelho.", "Bate-papo", "Imagine",
                      "O que devemos explorar?"):
            self.assertIsNone(catalogo.classificar(frase), frase)

    def test_paragrafo_longo_que_cita_language_model_nao_e_recusa(self):
        texto = ("As a language model I can certainly write this story for you. " * 8)
        self.assertGreater(len(texto), catalogo.LINHA_MAXIMA)
        self.assertIsNone(catalogo.classificar(texto))

    def test_varrer_texto_visivel_devolve_so_avisos_sem_repetir(self):
        tela = ("Bate-papo\nImagine\nFaça upgrade para o Google AI Pro\n"
                "O que devemos explorar?\nFaça upgrade para o Google AI Pro\n"
                "Você atingiu o limite de uso\n")
        itens = catalogo.varrer(tela, visto_em="2026-09-29T01:00:00")
        self.assertEqual([i["categoria"] for i in itens], ["upgrade", "limite"])
        self.assertTrue(all(i["fonte"] == "sonda" for i in itens))

    def test_varrer_tela_vazia(self):
        self.assertEqual(catalogo.varrer(""), [])
        self.assertEqual(catalogo.varrer(None), [])

    def test_juntar_nao_repete_e_preserva_o_antigo(self):
        antigos = [catalogo.item("limite", "Você atingiu o limite", fonte="logs")]
        novos = [catalogo.item("limite", "VOCÊ ATINGIU O LIMITE", fonte="sonda"),
                 catalogo.item("upgrade", "Assine", fonte="sonda")]
        juntos = catalogo.juntar(antigos, novos)
        self.assertEqual(len(juntos), 2)
        self.assertEqual(juntos[0]["fonte"], "logs")

    def test_conhecidos_de_cada_ia_passam_no_schema(self):
        for ia in IAS:
            f = ficha.vazia(ia)
            f["catalogo_textos"] = catalogo.conhecidos(ia)
            self.assertEqual(ficha.validar(f), [], ia)

    def test_conhecidos_do_gemini_incluem_a_recusa_enlatada_com_seletor(self):
        itens = catalogo.conhecidos("gemini")
        recusas = [i for i in itens if i["categoria"] == "recusa_enlatada"]
        self.assertGreaterEqual(len(recusas), 3)
        self.assertTrue(all(i["seletor"] for i in recusas))


class SessaoGuiada(unittest.TestCase):
    """O protocolo por arquivos com a janela flutuante do painel."""

    def test_colado_le_so_as_linhas_novas_e_ignora_lixo(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "colado.jsonl"
            arquivo.write_text('{"papel": "campo_texto", "tipo": "html", "conteudo": "<x>"}\n'
                               'lixo\n\n{"papel": "proximo"}\n', encoding="utf-8")
            novas, lidas = guia.ler_colado(arquivo, 0)
            self.assertEqual([n["papel"] for n in novas], ["campo_texto", "proximo"])
            self.assertEqual(lidas, 4)
            novas2, lidas2 = guia.ler_colado(arquivo, lidas)
            self.assertEqual(novas2, [])
            self.assertEqual(lidas2, 4)

    def test_colado_inexistente(self):
        self.assertEqual(guia.ler_colado(Path("nao/existe.jsonl"), 0), ([], 0))

    def test_atual_json_tem_ia_passo_e_desde(self):
        original = guia.ATUAL
        with tempfile.TemporaryDirectory() as pasta:
            guia.ATUAL = Path(pasta) / "_atual.json"
            try:
                guia.escrever_atual("grok", guia.PASSOS[0])
                dados = json.loads(guia.ATUAL.read_text(encoding="utf-8"))
            finally:
                guia.ATUAL = original
        self.assertEqual(dados["ia"], "grok")
        self.assertEqual(dados["passo"], "onde escreve")
        self.assertRegex(dados["desde"], r"^\d{4}-\d{2}-\d{2}T")

    def test_mensagem_de_abertura_pede_os_sete_passos(self):
        texto = guia.mensagem_de_abertura("grok")
        for n in range(1, 8):
            self.assertIn(f"({n})", texto)
        self.assertIn("próximo", texto)

    def test_sete_passos_na_ordem_pedida(self):
        self.assertEqual(guia.PASSOS, ("onde escreve", "como manda", "onde a resposta aparece",
                                       "onde troca de modelo", "como anexa imagem",
                                       "onde gera imagem", "o que aparece quando a cota acaba"))


if __name__ == "__main__":
    unittest.main()
