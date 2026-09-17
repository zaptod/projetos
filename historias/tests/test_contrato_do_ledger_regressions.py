"""O publicador pergunta "saiu?" de UM jeito so, e a cura depende disso.

Ate 16/09/2026 cada leitor respondia com `bool(linha["url"])`. Mas o `url`
guardava TRES coisas: o link, a frase de estado ("publicado no YouTube (com a
confirmacao extra)") e, no TikTok, SEMPRE a frase. Entao rascunho e
publicacao de verdade ficavam identicos para todo filtro do projeto — foi
assim que 30 rascunhos contaram como publicados.

A cura do ledger (d2) tira a frase do `url` das linhas de TikTok e marca cada
linha com `publicado`. Enquanto o publicador ler `url`, gravar essa cura
apagaria a guarda de "ja esta no TikTok" de 46 builds e 51 historias — e eles
voltariam a ser postados. **A migracao vem ANTES da cura, nunca depois**, e e
por isso que o `curar_ledger` recusa gravar enquanto `CONTRATO_DO_LEDGER` nao
for 2.

O que fica travado aqui:
1. O contrato declarado, que e o que a cura confere.
2. Nenhum ponto do publicador decide "saiu?" pelo `url` — a varredura da cura
   procura exatamente esse padrao no fonte.
3. O comportamento NAO muda hoje: nenhuma linha tem o campo `publicado`,
   entao `publicado()` cai no criterio antigo. Migrar nao pode mexer no que
   sai enquanto o ledger nao for curado.
4. E o caso que a cura VAI criar: `url` vazia com `publicado: True` conta
   como publicado. Se isso falhar, a cura devolve videos para a fila.
"""
import importlib.util
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
POSTAR = RAIZ / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_contrato", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


postar = _postar()

# O MESMO padrao que a varredura da cura usa (`curar_ledger.LEITURA_POR_URL`).
# Copiado de proposito: se ele mudar la e nao aqui, este teste para de
# proteger — e e melhor descobrir por divergencia do que por reposta em massa.
LEITURA_POR_URL = re.compile(
    r"(?:\bif|\band|\bor|\bnot)\s+(?:l|linha)\.get\(\"url\"\)")


class ContratoTests(unittest.TestCase):
    def test_o_contrato_esta_declarado(self):
        self.assertGreaterEqual(postar.CONTRATO_DO_LEDGER, 2)

    def test_nenhum_ponto_decide_saiu_pelo_url(self):
        """SEM os comentarios.

        A primeira versao deste teste acusou uma ocorrencia que estava dentro
        do comentario que explica por que ela nao existe. E a mesma armadilha
        de teste-que-le-fonte que ja mordeu tres vezes aqui — e ela mostra que
        a varredura da propria cura tambem pode ser enganada por um
        comentario, em qualquer arquivo. Avisado a d2.
        """
        codigo = "\n".join(
            l for l in POSTAR.read_text(encoding="utf-8").splitlines()
            if not l.strip().startswith("#"))
        self.assertEqual([], LEITURA_POR_URL.findall(codigo),
                         "a cura recusa gravar enquanto houver leitura por url")

    def test_a_cura_libera_a_gravacao(self):
        """O portao de verdade, e nao a nossa leitura dele."""
        caminho = RAIZ / "ferramentas" / "curar_ledger.py"
        if not caminho.is_file():
            self.skipTest("curar_ledger.py ainda nao existe")
        spec = importlib.util.spec_from_file_location("curar_teste", caminho)
        curar = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(curar)
        self.assertEqual("", curar.postar_migrado())


class SaiuTests(unittest.TestCase):
    def test_link_de_verdade(self):
        self.assertTrue(postar._saiu({"url": "https://youtu.be/abc"}))

    def test_frase_de_estado_ainda_conta_HOJE(self):
        """Linha antiga, sem o campo: cai no criterio de antes. Migrar nao
        pode mudar o que sai enquanto o ledger nao for curado."""
        self.assertTrue(postar._saiu({"url": "publicado no TikTok"}))

    def test_publicado_FALSE_vence_o_url(self):
        """O rascunho curado: tem frase no url e nao saiu."""
        self.assertFalse(
            postar._saiu({"url": "publicado no TikTok", "publicado": False}))

    def test_publicado_TRUE_sem_url_conta(self):
        """O que a cura vai gravar. Se isto falhar, ela devolve video para a
        fila e o canal reposta."""
        self.assertTrue(postar._saiu({"url": "", "publicado": True}))

    def test_linha_vazia_e_lixo_nao_contam(self):
        for ruim in ({}, {"url": ""}, None, "texto", []):
            with self.subTest(ruim=ruim):
                self.assertFalse(postar._saiu(ruim))


if __name__ == "__main__":
    unittest.main()
