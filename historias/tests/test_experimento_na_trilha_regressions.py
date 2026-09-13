# -*- coding: utf-8 -*-
"""O experimento chega ate a trilha da historia (11/09/2026).

A pergunta que originou isto foi concreta: canais parecidos poem um
instrumental por baixo da narracao, e ninguem sabe se aquilo segura ou
atrapalha. Para responder era preciso que a producao soubesse rodar os dois
lados e que cada video lembrasse de qual lado veio.

O que este arquivo trava:

1. `_musica` obedece `audio.trilha_arquivo`. Antes a escolha era
   `existentes[0]`: com dois arquivos na pasta, qual tocava dependia da
   ordem do sistema de arquivos — e um experimento de trilha com trilha
   indefinida nao mede nada.
2. Arquivo nomeado que nao existe AVISA e cai na trilha de sempre, em vez de
   derrubar o render de madrugada.
3. O id gravado na atribuicao e o mesmo que o catalogo monta — inclusive a
   parte que nao leva sufixo. Errar isso deixaria o braco com zero medidos e
   nenhum erro no caminho.

    cd e:\\projetos\\historias
    python -m pytest tests/test_experimento_na_trilha_regressions.py -q
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from contos.pipeline import controller


class TrilhaEscolhidaTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._antes = controller.ASSETS
        controller.ASSETS = Path(self._tmp.name)
        (controller.ASSETS / "music").mkdir(parents=True)
        self.addCleanup(self._restaurar)
        self.pipeline = controller.Pipeline()
        self.avisos = []

    def _restaurar(self):
        controller.ASSETS = self._antes
        self._tmp.cleanup()

    def _por_no_disco(self, *nomes):
        for nome in nomes:
            (controller.ASSETS / "music" / nome).write_bytes(b"RIFF")

    def _log(self, texto):
        self.avisos.append(str(texto))

    def test_o_arquivo_nomeado_ganha_do_primeiro_da_pasta(self):
        self._por_no_disco("aaa_procedural.wav", "itaraca.mp3")
        escolhido = self.pipeline._musica(
            self._log, {"audio": {"trilha_arquivo": "itaraca.mp3"}})
        self.assertEqual("itaraca.mp3", Path(escolhido).name)

    def test_sem_nome_cai_no_primeiro_em_ordem_estavel(self):
        """Ordem do disco nao e ordem: sem `sorted`, dois arquivos na pasta
        davam trilhas diferentes em maquinas diferentes."""
        self._por_no_disco("zzz.mp3", "aaa.mp3")
        escolhido = self.pipeline._musica(self._log, {"audio": {}})
        self.assertEqual("aaa.mp3", Path(escolhido).name)

    def test_arquivo_que_nao_existe_avisa_e_nao_derruba(self):
        self._por_no_disco("trilha_historias.wav")
        escolhido = self.pipeline._musica(
            self._log, {"audio": {"trilha_arquivo": "nao_existe.mp3"}})
        self.assertEqual("trilha_historias.wav", Path(escolhido).name)
        self.assertTrue(any("nao_existe.mp3" in a for a in self.avisos),
                        "o render seguiu com OUTRA trilha e nao avisou — o "
                        "experimento mediria os dois bracos com o mesmo som")

    def test_trilha_desligada_continua_desligando(self):
        self._por_no_disco("itaraca.mp3")
        self.assertIsNone(self.pipeline._musica(
            self._log, {"audio": {"trilha_procedural": False,
                                  "trilha_arquivo": "itaraca.mp3"}}))

    def test_sem_config_usa_o_do_proprio_pipeline(self):
        """A assinatura antiga (`_musica(log)`) continua valendo: ela e
        chamada assim em codigo que nao sabe de experimento."""
        self._por_no_disco("trilha_historias.wav")
        self.assertIsNotNone(self.pipeline._musica(self._log))


class IdDaAtribuicaoTests(unittest.TestCase):
    """A chave que liga o video renderizado a metrica dele."""

    def setUp(self):
        self.pipeline = controller.Pipeline()

    def test_serie_leva_o_sufixo_da_parte(self):
        roteiro = {"serie": True, "partes": [{"n": 1}, {"n": 2}, {"n": 3}]}
        self.assertEqual(
            "historia_00007:celular:p04",
            self.pipeline.id_do_catalogo(roteiro, "historia_00007", "celular", 4))

    def test_uma_parte_so_NAO_leva_sufixo(self):
        """O catalogo so poe `:pNN` quando ha mais de uma parte. Gravar o
        sufixo sempre apontaria para um id que nao existe no ledger."""
        roteiro = {"partes": [{"n": 1}]}
        self.assertEqual(
            "historia_00009:celular",
            self.pipeline.id_do_catalogo(roteiro, "historia_00009", "celular", 1))

    def test_bate_com_o_que_o_catalogo_monta(self):
        """Nao e so formato parecido: e a mesma string, ou a juncao falha."""
        from contos.publicar import catalogo
        fonte = Path(catalogo.__file__).read_text(encoding="utf-8")
        self.assertIn('f":p{parte:02d}" if total_partes > 1 else ""', fonte,
                      "a regra do sufixo mudou no catalogo e a copia do "
                      "controller ficou para tras")


if __name__ == "__main__":
    unittest.main()
