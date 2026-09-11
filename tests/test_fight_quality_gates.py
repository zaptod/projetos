"""Gate de qualidade de luta (corpus smoke).

Roda as 48 lutas espelhadas do corpus smoke com a sonda e cobra os alvos da
onda atual. E deliberadamente pesado (~25s), entao fica atras de
``NF_QUALITY_GATE=1`` — o CI liga a variavel num step proprio e a suite
principal continua rapida.

O que este gate protege HOJE (onda 0):

* o harness em si — toda luta do corpus precisa executar sem erro;
* o vies de lado (B4): espelhos exatos com winrate de p1 fora de 30-70% no
  smoke denunciam bug de spawn/medicao, nao de balance;
* o contrato do relatorio — as chaves que as ondas seguintes vao cobrar ja
  existem e sao numericas quando ha amostra.
"""

from __future__ import annotations

import os
import unittest

GATE_LIGADO = os.environ.get("NF_QUALITY_GATE") == "1"

# A onda atual do programa "lutas vivas". Sobe junto com cada onda entregue —
# e o unico lugar do repositorio que declara em que onda estamos.
ONDA_ATUAL = 11


@unittest.skipUnless(GATE_LIGADO, "gate pesado; ligue com NF_QUALITY_GATE=1")
class FightQualityGateTests(unittest.TestCase):
    resumo = None
    avaliacoes = None

    @classmethod
    def setUpClass(cls) -> None:
        from neural_fights.tools import qualidade_luta as ql

        fonte = ql.FonteDeDados("engine")
        lutas = ql.rodar_corpus(ql.corpus_smoke(fonte), fonte)
        cls.lutas = lutas
        cls.resumo = ql.agregar(lutas)
        cls.avaliacoes = ql.avaliar(cls.resumo, ql.carregar_alvos(), ONDA_ATUAL)

    def test_toda_luta_do_corpus_executa(self) -> None:
        falhas = [
            (luta["spec"], luta["error"])
            for luta in self.lutas
            if not luta["success"]
        ]
        self.assertEqual(falhas, [])

    def test_nenhum_alvo_habilitado_esta_violado(self) -> None:
        violados = [
            f"{item['alvo']}: {item['valor']} fora de {item['faixa']}"
            for item in self.avaliacoes
            if item["status"] == "violado"
        ]
        self.assertEqual(violados, [])

    def test_vies_de_lado_dentro_da_faixa_do_smoke(self) -> None:
        """B4: espelhos exatos; fora de 30-70% e bug de harness/spawn."""
        winrate = self.resumo["winrate_p1"]
        self.assertIsNotNone(winrate)
        self.assertGreaterEqual(winrate, 0.30)
        self.assertLessEqual(winrate, 0.70)

    def test_contrato_do_relatorio(self) -> None:
        """As chaves que as proximas ondas cobram ja existem e sao numericas."""
        obrigatorias = (
            "duracao_p50",
            "pct_sob_5s",
            "taxa_critico_global",
            "taxa_anulacao_iframes_media",
            "share_dano_basico",
            "share_dano_skill",
            "share_dano_dot",
            "skills_por_luta_p50",
            "taxa_pilha_media",
            "acao_mediana_ms_p50",
            "pct_com_lead_change",
            "pct_vencedor_acima_80",
            "winrate_p1",
        )
        for chave in obrigatorias:
            with self.subTest(chave=chave):
                self.assertIn(chave, self.resumo)
                self.assertIsInstance(self.resumo[chave], (int, float))

    def test_baseline_dos_bugs_conhecidos_ainda_reproduz(self) -> None:
        """Enquanto a onda 1 nao entra, o corpus PROVA que mede os bugs.

        Estes asserts sao o inverso dos alvos: fixam que o harness enxerga o
        estado quebrado atual. Quando a onda correspondente corrigir o bug,
        este teste e ONDA_ATUAL sobem juntos no mesmo PR.
        """
        # Ondas 1-3 entregues: critico raro, DoT existe. Os bugs de "vida"
        # (pilha em 0,04%, flicker de 33ms) seguem reproduzidos ate a O5.
        self.assertLess(self.resumo["taxa_critico_global"], 0.25)
        # Re-pino Onda 5A/5B: a pilha rodava em 0,04-0,9% das decisoes e a
        # acao mediana era 16,7ms (tremor). Com proposta+pipeline e o
        # escritor unico com min-hold, os pinos viram na direcao consertada.
        self.assertGreater(self.resumo["taxa_pilha_media"], 0.9)
        self.assertGreater(self.resumo["acao_mediana_ms_p50"], 250.0)
        self.assertGreater(self.resumo["share_dano_dot"], 0.0)


class HarnessDeVideoTests(unittest.TestCase):
    """Contratos baratos do passe --video. Fora do gate pesado de proposito.

    O gate acima nao roda `medir_video` (ele custa 4 gravacoes), entao os
    alvos V7 ficam `sem_dados` no CI e nada aqui os cobra automaticamente.
    O que DA para cobrar sem gravar nada e que o harness aponte para o palco
    certo — e era exatamente isso que estava errado.
    """

    def test_o_harness_mede_as_arenas_que_a_producao_publica(self) -> None:
        """O passe --video precisa medir o palco que vai ao ar.

        Ate 10/09/2026 `ARENAS_DE_VIDEO` era ("Arena Pequena", "Ringue",
        "Dojo", "Cyberpunk") enquanto os videos eram gravados em
        Duto/Poco/Torre: os alvos V7 nunca mediram o que o espectador ve.
        Medido na troca (fixture congelada, 4 lutas): diametro p50 de 0,190
        para 0,207, frames visiveis de 0,985 para 0,993, pan p90 de 0,625
        para 0,566 — o estouro do V7_pan_calmo era artefato do palco errado.
        """
        from neural_fights.core.arena import ARENAS, ARENAS_VERTICAIS
        from neural_fights.tools import qualidade_luta as ql

        self.assertEqual(tuple(ARENAS_VERTICAIS), tuple(ql.ARENAS_DE_VIDEO))
        for nome in ql.ARENAS_DE_VIDEO:
            with self.subTest(arena=nome):
                self.assertIn(nome, ARENAS)

    def test_o_alvo_de_tamanho_fala_da_mesma_chave_que_a_sonda_emite(self) -> None:
        """Alvo e sonda tem que concordar na METRICA, nao so no numero.

        Na 15A a sonda passou a emitir o diametro desenhado (antes emitia o
        raio com nome de diametro) e os alvos V7 foram renomeados junto. Se
        um lado mudar sozinho, o alvo vira `sem_dados` em silencio — que e o
        pior modo de falha possivel num harness de qualidade.
        """
        from neural_fights.tools import qualidade_luta as ql

        alvos = ql.carregar_alvos()
        metricas = {a["metrica"] for a in alvos.values()
                    if str(a["metrica"]).startswith("video_")}
        self.assertIn("video_diametro_lutador_p50", metricas)
        self.assertNotIn("video_tamanho_lutador_p50", metricas)


if __name__ == "__main__":
    unittest.main()
