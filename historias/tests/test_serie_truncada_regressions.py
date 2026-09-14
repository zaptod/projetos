# -*- coding: utf-8 -*-
"""Serie pela metade nao vira video, nao vai ao ar: ela se RETOMA.

Em 10/09/2026 as 06:15 o Gemini bateu no limite de uso no meio da parte 3 e a
`historia_00005` ficou com **2 partes de 6**. O roteiro nao guardava quantas
partes tinham sido planejadas, entao ela parecia inteira — so menor.

O que aconteceria sem este arquivo: `incompletas()` olha as partes que
EXISTEM, veria duas sem video, mandaria gerar 28 imagens e dois videos, e o
catalogo publicaria a serie. Quem assistisse a parte 2 nunca receberia a 3.

**E o pior resultado possivel do canal** — pior que atraso e pior que video
fraco, porque quem ficou esperando nao volta. E o proprio `postar.py` ja diz
isso na regra 1 da fila ("TERMINA O QUE COMECOU"); faltava a geracao saber.

O que este arquivo trava:

1. O ROTEIRO SABE que esta pela metade (`partes_esperadas` gravado).
2. TEXTO FALTANDO VEM ANTES de imagem e video, e nao passa por `_terminar`.
3. O CATALOGO RECUSA a serie truncada — a porta do upload para aqui.
4. ROTEIRO ANTIGO, sem o campo, NAO e acusado: inventar falta faria a
   pipeline reprocessar historia que esta boa.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from contos.roteiro import gerar
from contos.roteiro import roteiro as R

RAIZ = Path(__file__).resolve().parents[1]


class PartesQueFaltamTests(unittest.TestCase):
    def _roteiro(self, esperadas, tem):
        return {"partes_esperadas": esperadas,
                "partes": [{"n": n, "cenas": []} for n in tem]}

    def test_serie_completa_nao_falta_nada(self):
        self.assertEqual([], R.partes_que_faltam(self._roteiro(6, [1, 2, 3, 4, 5, 6])))

    def test_a_historia_00005_o_caso_real(self):
        """2 de 6: o Gemini parou no meio da parte 3."""
        self.assertEqual([3, 4, 5, 6],
                         R.partes_que_faltam(self._roteiro(6, [1, 2])))

    def test_buraco_no_meio_tambem_conta(self):
        self.assertEqual([3], R.partes_que_faltam(self._roteiro(4, [1, 2, 4])))

    def test_roteiro_ANTIGO_sem_o_campo_nao_e_acusado(self):
        """Inventar falta faria reprocessar historia que esta boa."""
        self.assertEqual([], R.partes_que_faltam({"partes": [{"n": 1}]}))
        self.assertEqual([], R.partes_que_faltam(
            {"partes_esperadas": 0, "partes": [{"n": 1}]}))

    def test_o_numero_planejado_e_gravado(self):
        with tempfile.TemporaryDirectory() as tmp:
            antes = R.OUTPUTS
            try:
                R.OUTPUTS = Path(tmp)
                biblia = {"titulo": "t", "protagonista": "p",
                          "partes_esperadas": 6,
                          "partes": [{"n": n} for n in range(1, 7)]}
                caminho = R.salvar_serie(
                    biblia,
                    [{"n": 1, "titulo": "t", "cta": "",
                      "cenas": [{"n": 1, "imagem": "x", "tempo": 4,
                                 "narracao": "y"}]}],
                    "historia_00099", provedor="gemini")
                dados = json.loads(Path(caminho).read_text(encoding="utf-8-sig"))
                self.assertEqual(6, dados["partes_esperadas"])
                self.assertEqual([2, 3, 4, 5, 6], R.partes_que_faltam(dados))
            finally:
                R.OUTPUTS = antes


class OndeAGuardaVaeTests(unittest.TestCase):
    def _fonte(self, *partes) -> str:
        return (RAIZ.joinpath(*partes)).read_text(encoding="utf-8")

    def test_texto_faltando_vem_ANTES_de_imagem_e_video(self):
        corpo = self._fonte("contos", "pipeline", "agenda.py")
        trecho = corpo[corpo.index("pendentes = incompletas()"):]
        self.assertLess(trecho.index("partes_sem_texto"),
                        trecho.index("_terminar(pipeline"))

    def test_a_truncada_NAO_passa_por_terminar(self):
        """`_terminar` gera imagem e video — e o que nao pode acontecer."""
        corpo = self._fonte("contos", "pipeline", "agenda.py")
        trecho = corpo[corpo.index("truncadas = ["):]
        alvo = trecho[:trecho.index("if pendentes:")]
        self.assertIn("_retomar_texto(", alvo)
        self.assertNotIn("_terminar(", alvo)

    def test_incompletas_marca_a_truncada_e_para_ali(self):
        corpo = self._fonte("contos", "pipeline", "agenda.py")
        trecho = corpo[corpo.index("def incompletas("):]
        alvo = trecho[trecho.index("faltam_partes ="):]
        self.assertIn("partes_sem_texto", alvo[:400])
        self.assertIn("continue", alvo[:500])

    def test_o_catalogo_recusa_a_truncada(self):
        """A porta do upload para aqui, como ja para a historia de teste."""
        corpo = self._fonte("contos", "publicar", "catalogo.py")
        trecho = corpo[corpo.index("def listar("):]
        self.assertIn("partes_que_faltam(dados)", trecho)
        self.assertLess(trecho.index("partes_que_faltam(dados)"),
                        trecho.index("videos.append") if "videos.append"
                        in trecho else len(trecho))


class RetomadaTests(unittest.TestCase):
    def test_a_retomada_escreve_SO_o_que_falta(self):
        from contos.roteiro import gerar
        fonte = Path(gerar.__file__).read_text(encoding="utf-8")
        trecho = fonte[fonte.index("def retomar_serie("):
                       fonte.index("def gerar_serie(")]
        self.assertIn("partes_que_faltam", trecho)
        self.assertIn("for numero in faltam:", trecho)
        # a biblia salva e o que torna a retomada possivel
        self.assertIn("biblia.json", trecho)
        # e ela preserva a identidade da historia para o rodizio
        self.assertIn("ganchos=roteiro.get", trecho)

    def test_a_retomada_que_falha_NAO_derruba_a_rodada(self):
        """Ela falha pelo mesmo motivo que a escrita falhou (limite, rede)."""
        corpo = (RAIZ / "contos" / "pipeline" / "agenda.py").read_text(
            encoding="utf-8")
        trecho = corpo[corpo.index("def _retomar_texto("):]
        self.assertIn("except Exception", trecho[:1200])
        self.assertIn("_registrar_erro(", trecho[:1400])

    def test_roteiro_com_partes_vazias_e_salvo_apos_biblia(self):
        """Apos a BIBLIA ser parseada, o roteiro e salvo com partes vazias.

        Isso permite que se a geracao falhar antes de completar alguma parte,
        a proxima rodada a detecte como incompleta e retome automaticamente
        (evitando deixar a historia orfã e gerando diagnóstico).
        """
        fonte = Path(gerar.__file__).read_text(encoding="utf-8")
        trecho = fonte[fonte.index("_gravar(pasta / \"biblia.json\""):]
        # Deve salvar o roteiro apos gravar a biblia
        self.assertLess(trecho.index("_gravar(pasta / \"biblia.json\""),
                        trecho.index("R.salvar_serie(biblia, []"))
        # Com partes vazias, para que incompletas() a detecte
        self.assertIn("R.salvar_serie(biblia, []", trecho[:700])
        # E ANTES de comeco da etapa 2, nao depois
        self.assertLess(trecho.index("R.salvar_serie(biblia, []"),
                        trecho.index("# --- etapa 2:"))


if __name__ == "__main__":
    unittest.main()
