# -*- coding: utf-8 -*-
"""O Aprimorador de Prompt do PicassoIA, e o que ele joga fora (11/09/2026).

O site tem um aprimorador NATIVO, e ele vale mais que o nosso reescritor por
um motivo simples: foi feito para aquele gerador. O nosso e um LLM generico
adivinhando o que o PicassoIA gosta.

MEDIDO, com um prompt real do canal de historias — 701 chars entrando, 4093
saindo:

    manteve   a descricao do protagonista (45-year-old, curly black hair,
              floral sundress) e o estilo (cartoon), e ainda detalhou
    APAGOU    `no collage`, `no split screen`

Ou seja: ele apaga exatamente as duas linhas que existem para impedir o
defeito mais comum do canal — 44 das 440 imagens do disco eram colagem.
Ligar o aprimorador sem devolver isso seria trocar um prompt melhor por
imagens piores.

E ele multiplica o tamanho por seis, muito acima do `prompt_max_chars`.
Cortar no teto ANTES de recolocar as proibicoes jogaria fora justamente
elas — por isso a ordem e recolocar, depois cortar.

    cd e:\\projetos\\random_builds
    python -m pytest tests/test_aprimorador_regressions.py -q
"""
from __future__ import annotations

import unittest

from builds.identity.picasso_client import PicassoClient

NEGATIVO = ("no text, no letters, no collage, no split screen, "
            "not landscape, single frame only")


def _cliente(**ajustes):
    cliente = PicassoClient.__new__(PicassoClient)
    cliente.ajustes = {"negativo": NEGATIVO, "prompt_max_chars": 900,
                       **ajustes}
    return cliente


class ProibicoesVoltamTests(unittest.TestCase):

    def test_o_que_o_aprimorador_apagou_volta(self):
        aprimorado = ("A 45-year-old Latina woman with voluminous curly hair "
                      "dragging a neon beach chair, cinematic lighting")
        saida = _cliente()._reforcar_proibicoes(aprimorado)
        self.assertIn("no collage", saida)
        self.assertIn("no split screen", saida)

    def test_o_texto_aprimorado_e_preservado(self):
        aprimorado = "A 45-year-old Latina woman with voluminous curly hair"
        saida = _cliente()._reforcar_proibicoes(aprimorado)
        self.assertIn("voluminous curly hair", saida)

    def test_nao_duplica_quando_ja_esta_la(self):
        ja = f"uma cena qualquer, {NEGATIVO}"
        saida = _cliente()._reforcar_proibicoes(ja)
        self.assertEqual(1, saida.count("no collage"))

    def test_o_teto_e_respeitado(self):
        gigante = "A woman with voluminous curly hair. " * 200
        saida = _cliente()._reforcar_proibicoes(gigante)
        self.assertLessEqual(len(saida), 905)

    def test_no_corte_as_proibicoes_SOBREVIVEM(self):
        """Cortar antes de recolocar jogaria fora justamente elas — e o
        prompt sairia sem a unica linha que impede a colagem."""
        gigante = "A woman with voluminous curly hair. " * 200
        saida = _cliente()._reforcar_proibicoes(gigante)
        self.assertTrue(saida.endswith(NEGATIVO), saida[-80:])

    def test_o_corte_cai_numa_virgula_e_nao_no_meio_da_palavra(self):
        gigante = ("A woman with hair, a chair on the asphalt, "
                   "golden light everywhere, ") * 40
        saida = _cliente()._reforcar_proibicoes(gigante)
        corpo = saida[:-len(NEGATIVO)].rstrip(" ,")
        self.assertFalse(corpo.endswith(" "), saida[:120])
        self.assertNotIn("  ", saida)

    def test_sem_negativo_configurado_nao_inventa_nada(self):
        saida = _cliente(negativo="")._reforcar_proibicoes("uma cena")
        self.assertEqual("uma cena", saida)

    def test_espaco_repetido_e_normalizado(self):
        """O painel do site devolve o texto com quebras de linha; o campo de
        prompt e uma linha so."""
        bruto = "uma    cena" + chr(10) + chr(10) + "com quebras"
        self.assertIn("uma cena com quebras",
                      _cliente()._reforcar_proibicoes(bruto))


class LigadoNoFluxoTests(unittest.TestCase):

    def test_o_aprimorador_roda_antes_de_gerar(self):
        """Ele tem de mexer no prompt ANTES do clique em gerar; depois seria
        aprimorar para nada."""
        import inspect
        fonte = inspect.getsource(PicassoClient.submit_prompt)
        self.assertLess(fonte.index("self._aprimorar("),
                        fonte.index("_esperar_estabilizar"))

    def test_falha_do_aprimorador_nao_derruba_o_job(self):
        """Aprimorar e otimizacao. Uma cena sem imagem custa mais do que uma
        cena com prompt cru."""
        import inspect
        fonte = inspect.getsource(PicassoClient._aprimorar)
        self.assertIn("return original", fonte)

    def test_ele_e_desligavel(self):
        import inspect
        self.assertIn('ajustes.get("aprimorar_prompt"',
                      inspect.getsource(PicassoClient._aprimorar))

    def test_o_canal_de_historias_esta_com_ele_desligado(self):
        """Desligado em 14/09/2026 23:55: na historia_00012 ele trocou a ACAO
        de 18 de 21 cenas por um retrato do personagem, e numa cena reescrita
        depois de recusa escreveu um retrato sexualizado que saiu em diptico.
        Religar exige uma guarda que confira se a acao do roteiro sobreviveu —
        e o comentario no imagens.json tem que continuar explicando por que."""
        import json
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[2]
        config = json.loads(
            (raiz / "historias" / "config" / "imagens.json")
            .read_text(encoding="utf-8-sig"))
        self.assertFalse(config.get("aprimorar_prompt"))
        self.assertIn("DESLIGADO", config.get("_comment_aprimorador_desligado", ""))
        self.assertTrue(config.get("negativo"),
                        "sem `negativo` o prompt cru perde as proibicoes")


if __name__ == "__main__":
    unittest.main()
