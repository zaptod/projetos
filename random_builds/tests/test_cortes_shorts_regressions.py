# -*- coding: utf-8 -*-
"""Contratos do corte para Shorts.

O YouTube só trata vídeo vertical como Short até 3 min. Passou disso, ele
vira vídeo normal e sai da esteira de Shorts — sem aviso nenhum. Medido em
31/08/2026: as três partes prontas da `historia_00003` tinham 206 s, 191 s e
189 s, todas fora do formato.

O que este arquivo trava:

1. CORTE NA CENA, NUNCA NO RELÓGIO. Um corte em 180 s cravado cai no meio de
   uma palavra. Com o plano de edição em mãos, o corte vai para a troca de
   cena mais próxima do ponto ideal.
2. PEDAÇOS EQUILIBRADOS. 206 s viram 100 s + 106 s, não 180 s + 26 s — um
   rabinho de 26 segundos não segura ninguém.
3. NENHUM PEDAÇO ACIMA DO LIMITE. É o ponto inteiro do exercício.
4. O QUE CABE NÃO É TOCADO, e um 16:9 nunca é cortado (não seria Short de
   qualquer jeito).

Rode de dentro de random_builds/:
    python -m unittest tests.test_cortes_shorts_regressions -v
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from builds.publicar import cortes                                # noqa: E402

# As fronteiras reais da parte 1 da historia_00003 (14 cenas).
CENAS = [0.0, 11.8, 26.7, 40.5, 54.8, 71.6, 85.3, 100.0,
         113.5, 128.1, 143.2, 157.8, 174.4, 190.9]
LIMITE = 180.0


class PontosDeCorteTests(unittest.TestCase):
    def test_o_que_cabe_nao_e_cortado(self):
        for duracao in (57.9, 120.0, 179.0):
            self.assertEqual([(0.0, duracao)],
                             cortes.pedacos(duracao, LIMITE, CENAS))

    def test_corta_na_troca_de_cena(self):
        fatias = cortes.pedacos(206.19, LIMITE, CENAS)
        self.assertEqual(2, len(fatias))
        corte = fatias[0][1]
        self.assertIn(corte, CENAS, "cortou fora de uma troca de cena")
        self.assertAlmostEqual(100.0, corte, places=1)

    def test_pedacos_equilibrados_e_nao_180_mais_o_resto(self):
        fatias = cortes.pedacos(206.19, LIMITE, CENAS)
        duracoes = [fim - ini for ini, fim in fatias]
        self.assertLess(max(duracoes) - min(duracoes), 60,
                        f"pedaços muito desiguais: {duracoes}")

    def test_nenhum_pedaco_passa_do_limite(self):
        for duracao in (181.0, 206.19, 400.0, 900.0):
            for ini, fim in cortes.pedacos(duracao, LIMITE, CENAS):
                self.assertLessEqual(fim - ini, LIMITE + cortes.MARGEM_S,
                                     f"{duracao}s deixou pedaço de {fim - ini}s")

    def test_as_fatias_cobrem_o_video_inteiro_sem_buraco(self):
        fatias = cortes.pedacos(206.19, LIMITE, CENAS)
        self.assertEqual(0.0, fatias[0][0])
        self.assertAlmostEqual(206.19, fatias[-1][1], places=2)
        for (_, fim), (ini, _) in zip(fatias, fatias[1:]):
            self.assertEqual(fim, ini, "sobrou (ou repetiu) um trecho")

    def test_sem_plano_ainda_corta(self):
        """Vídeo sem `edit_plan.json` não pode ficar sem publicar."""
        fatias = cortes.pedacos(206.19, LIMITE, [])
        self.assertEqual(2, len(fatias))
        for ini, fim in fatias:
            self.assertLessEqual(fim - ini, LIMITE + cortes.MARGEM_S)

    def test_nenhum_pedaco_minusculo(self):
        for duracao in (182.0, 190.0, 206.19, 361.0):
            for ini, fim in cortes.pedacos(duracao, LIMITE, CENAS):
                self.assertGreaterEqual(fim - ini, cortes.MINIMO_S,
                                        f"{duracao}s gerou um caco")

    def test_video_muito_longo_vira_varios(self):
        fatias = cortes.pedacos(900.0, LIMITE, CENAS)
        self.assertGreaterEqual(len(fatias), 6)


class GanchoDoSegundoPedacoTests(unittest.TestCase):
    """O 2o Short comeca no MEIO da historia — ele precisa abrir bem.

    Sem isto, o corte cai onde o relogio mandar e a pessoa entra numa frase
    pela metade, sem titulo e sem contexto. Como as fronteiras candidatas
    sao inicios de CENA — e toda cena comeca com uma frase escrita para
    prender — da para escolher a que abre melhor, e nao so a mais proxima.
    """

    def test_pergunta_vale_mais_que_frase_comum(self):
        self.assertGreater(cortes.forca_do_gancho("Quem levou?"),
                           cortes.forca_do_gancho(
                               "Eu continuo andando pela sala devagar."))

    def test_frase_curta_e_detalhe_concreto_pontuam(self):
        curta = cortes.forca_do_gancho("A assinatura nao e do meu pai.")
        longa = cortes.forca_do_gancho(
            "A assinatura que estava no contrato guardado na gaveta nao "
            "pertencia ao meu pai como todos sempre acreditaram.")
        self.assertGreater(curta, longa)
        self.assertGreater(
            cortes.forca_do_gancho("Eram 3 da manha de 17 de setembro."),
            cortes.forca_do_gancho("Era de manha cedo naquele dia."))

    def test_texto_vazio_nao_quebra(self):
        for texto in ("", None, "   "):
            self.assertEqual(0.0, cortes.forca_do_gancho(texto))

    def test_o_corte_anda_ate_a_cena_que_abre_melhor(self):
        """Trocar alguns segundos de equilibrio por uma pergunta compensa."""
        pontos = [0.0, 90.0, 100.0, 110.0, 190.0]
        notas = {90.0: 0.0, 100.0: 0.0, 110.0: 3.0, 190.0: 0.0}
        sem = cortes.pedacos(210.0, LIMITE, pontos)
        com = cortes.pedacos(210.0, LIMITE, pontos, notas=notas)
        self.assertNotEqual(sem[0][1], com[0][1],
                            "o gancho forte nao mudou o corte")
        self.assertEqual(110.0, com[0][1],
                         "o corte tinha que ir para a cena que abre com "
                         "pergunta")

    def test_gancho_longe_demais_nao_desequilibra_o_video(self):
        """Uma pergunta a 40 s do ponto ideal nao vale um pedaco torto."""
        pontos = [0.0, 20.0, 105.0, 190.0]
        notas = {20.0: 3.0, 105.0: 0.0, 190.0: 0.0}
        fatias = cortes.pedacos(210.0, LIMITE, pontos, notas=notas)
        self.assertEqual(105.0, fatias[0][1])

    def test_sem_notas_o_comportamento_e_o_de_antes(self):
        pontos = [0.0, 90.0, 100.0, 110.0]
        self.assertEqual(cortes.pedacos(210.0, LIMITE, pontos),
                         cortes.pedacos(210.0, LIMITE, pontos, notas={}))

    def test_le_os_ganchos_do_plano(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            video = pasta / "final_celular_p01.mp4"
            video.write_bytes(b"x")
            plano = pasta / "partes" / "p01" / "edit_plan.json"
            plano.parent.mkdir(parents=True)
            plano.write_text(json.dumps({"events": [
                {"start": 0.0, "narracao": "Comeco normal aqui."},
                {"start": 10.0, "narracao": "Quem levou?"},
                {"start": 15.0, "narracao": "outro plano", "continuacao": True},
            ]}), encoding="utf-8")
            notas = cortes.ganchos(video)
        self.assertEqual({0.0, 10.0}, set(notas),
                         "a continuacao nao abre cena nenhuma")
        self.assertGreater(notas[10.0], notas[0.0])


class FronteirasTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)

    def _plano(self, destino: Path, comecos):
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(
            {"events": [{"start": c} for c in comecos]}), encoding="utf-8")

    def test_acha_o_plano_ao_lado_do_mp4(self):
        video = self.pasta / "final_celular.mp4"
        video.write_bytes(b"x")
        self._plano(self.pasta / "edit_plan.json", [0.0, 10.0, 20.0])
        self.assertEqual([0.0, 10.0, 20.0], cortes.fronteiras(video))

    def test_acha_o_plano_da_PARTE_nas_historias(self):
        """`final_celular_p01.mp4` -> `partes/p01/edit_plan.json`."""
        video = self.pasta / "final_celular_p01.mp4"
        video.write_bytes(b"x")
        self._plano(self.pasta / "partes" / "p01" / "edit_plan.json",
                    [0.0, 11.8, 26.7])
        self.assertEqual([0.0, 11.8, 26.7], cortes.fronteiras(video))

    def test_sem_plano_devolve_vazio_sem_levantar(self):
        video = self.pasta / "final_celular.mp4"
        video.write_bytes(b"x")
        self.assertEqual([], cortes.fronteiras(video))

    def test_plano_corrompido_nao_derruba(self):
        video = self.pasta / "final_celular.mp4"
        video.write_bytes(b"x")
        (self.pasta / "edit_plan.json").write_text("{nao e json",
                                                   encoding="utf-8")
        self.assertEqual([], cortes.fronteiras(video))


class VideoFalso:
    def __init__(self, caminho, vertical=True, titulo="Um título", id="x"):
        self.caminho = caminho
        self.vertical = vertical
        self.titulo = titulo
        self.id = id
        self.bytes = 0


class PortaTests(unittest.TestCase):
    """`preparar` é a porta: quem publica só percorre a lista que ela devolve."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        self._duracao = cortes.medidas.duracao

    def _fingir_duracao(self, valor):
        cortes.medidas.duracao = lambda _c: valor
        self.addCleanup(lambda: setattr(cortes.medidas, "duracao",
                                        self._duracao))

    def test_video_curto_passa_intocado(self):
        self._fingir_duracao(58.0)
        video = VideoFalso(self.pasta / "v.mp4")
        self.assertEqual([video], cortes.preparar(video, limite=LIMITE))

    def test_horizontal_nunca_e_cortado(self):
        """16:9 não seria Short de qualquer forma — cortar não resolveria."""
        self._fingir_duracao(400.0)
        video = VideoFalso(self.pasta / "v.mp4", vertical=False)
        self.assertEqual([video], cortes.preparar(video, limite=LIMITE))

    def test_limite_zero_desliga(self):
        self._fingir_duracao(400.0)
        video = VideoFalso(self.pasta / "v.mp4")
        self.assertEqual([video], cortes.preparar(video, limite=0))

    def test_falha_ao_cortar_publica_inteiro(self):
        """Não conseguir cortar não pode impedir a publicação."""
        self._fingir_duracao(400.0)
        video = VideoFalso(self.pasta / "nao_existe.mp4")
        original = cortes.cortar

        def explodir(*_a, **_k):
            raise RuntimeError("ffmpeg sumiu")

        cortes.cortar = explodir
        self.addCleanup(lambda: setattr(cortes, "cortar", original))
        self.assertEqual([video],
                         cortes.preparar(video, limite=LIMITE,
                                         log=lambda *_a: None))

    def test_os_pedacos_dizem_a_ordem_no_titulo(self):
        self._fingir_duracao(400.0)
        video = VideoFalso(self.pasta / "v.mp4", titulo="Minha história")
        cortes.cortar = lambda _c, fatias, log=None: [
            self.pasta / f"v_corte{i:02d}.mp4" for i in range(1, len(fatias) + 1)]
        self.addCleanup(lambda: setattr(cortes, "cortar", cortes.cortar))
        for arquivo in self.pasta.glob("*"):
            arquivo.unlink()
        pedacos = cortes.preparar(video, limite=LIMITE, log=lambda *_a: None)
        self.assertGreater(len(pedacos), 1)
        self.assertIn("(1 de", pedacos[0].titulo)
        self.assertIn("Minha história", pedacos[0].titulo)
        self.assertNotEqual(pedacos[0].id, pedacos[1].id,
                            "dois pedaços com o mesmo id viram registro errado")


class ConfigTests(unittest.TestCase):
    def test_limite_padrao_e_o_do_shorts(self):
        self.assertEqual(180.0, cortes.LIMITE_PADRAO_S)

    def test_desligar_no_config_devolve_zero(self):
        self.assertEqual(
            0.0, cortes.limite({"youtube": {"cortar_para_shorts": False}}))

    def test_config_manda_no_limite(self):
        self.assertEqual(
            60.0, cortes.limite({"youtube": {"shorts_max_s": 60}}))


if __name__ == "__main__":
    unittest.main()
