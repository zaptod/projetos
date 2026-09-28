# -*- coding: utf-8 -*-
"""Descarte reversivel: video tirado de circulacao de proposito, com motivo.

Por que existe (28/09/2026, decisao 5 da rota de 27/09): a estreia da
`generation_00066` fica calada em 114,7 s de 120,8 s (95%). Ela so nao ia ao
ar porque a guarda de audio da publicacao a media e barrava a cada horario —
e continuava contando como "a unica estreia em estoque". Descartar e decisao
de gente: fica em `config/publicacao.json -> descartados`, com o motivo, e
nada e apagado (o ledger e as metricas referenciam o id; o mp4 fica).

O que este arquivo trava:
1. Descartado sai da lista, da fila e de `por_id` (por onde se publica na mao),
   nos dois perfis e nas duas variantes; o resto da mesma pasta fica.
2. Tirar a linha do config devolve o video: e reversivel.
3. O config real descarta a estreia muda da 00066, com o motivo escrito.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from builds.publicar import catalogo

CONTEUDO = b"v" * (catalogo.BYTES_MINIMOS + 1)
BASE = {"titulos": {"build": "{personagem} — build",
                    "estreia": "{personagem} estreia"}}
DESCARTE = {**BASE, "descartados": {
    "_comentario": "linha com _ e comentario, nao chave",
    "generation_00066:estreia": {"motivo": "audio mudo (95% de silencio)"}}}


class DescarteReversivel(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.outputs = Path(tmp.name) / "outputs"
        pasta = self.outputs / "generation_00066"
        (pasta / "estreia").mkdir(parents=True)
        (pasta / "character.json").write_text(json.dumps({"nome": "Cassian"}),
                                              encoding="utf-8")
        for alvo in (pasta, pasta / "estreia"):
            for perfil in catalogo.PERFIS:
                (alvo / f"final_{perfil}.mp4").write_bytes(CONTEUDO)
                (alvo / f"final_{perfil}_ganchoB.mp4").write_bytes(CONTEUDO)
        self.estreia = pasta / "estreia" / "final_celular.mp4"
        export = Path(tmp.name) / "publicar"
        for alvo, valor in (("OUTPUTS", self.outputs),
                            ("pasta_export", lambda config=None: export),
                            ("pendencias_da_build", lambda pasta, perfil: [])):
            p = patch.object(catalogo, alvo, valor)
            p.start()
            self.addCleanup(p.stop)

    def test_descartado_sai_da_lista_e_de_por_id(self):
        videos = catalogo.listar(DESCARTE)
        self.assertEqual({catalogo.BUILD}, {v.origem for v in videos})
        self.assertEqual(4, len(videos))          # build: 2 perfis x 2 variantes
        for vid in ("generation_00066:estreia:celular",
                    "generation_00066:estreia:normal:B"):
            self.assertIsNone(catalogo.por_id(vid, DESCARTE))
        # Nada foi apagado.
        self.assertTrue(self.estreia.is_file())

    def test_sem_a_linha_ele_volta(self):
        videos = catalogo.listar(BASE)
        estreias = [v for v in videos if v.origem == catalogo.ESTREIA]
        self.assertEqual(4, len(estreias))

    def test_motivo_e_chave(self):
        self.assertEqual({"generation_00066:estreia":
                          "audio mudo (95% de silencio)"},
                         catalogo.descartados(DESCARTE))
        self.assertEqual({}, catalogo.descartados(BASE))
        video = catalogo.listar(BASE)[0]
        self.assertEqual(f"{video.fonte_id}:{video.origem}",
                         catalogo.chave_de_descarte(video))

    def test_o_config_real_descarta_a_estreia_muda_da_00066(self):
        motivo = catalogo.descartados(catalogo.carregar_config()).get(
            "generation_00066:estreia", "")
        self.assertIn("mudo", motivo)
        self.assertIn("95%", motivo)

    def test_o_config_real_descarta_a_00077_inteira(self):
        # Decisao `generation-00077` do Adrian (28/09/2026): "Descartar, como
        # a 00066". Medido pela regua da publicacao: a luta da build (seg_022,
        # A e B) E a da estreia (seg_007) a -91 dB, e os dois lutadores sairam
        # do banco em 02/09 (som real impossivel). As duas chaves saem.
        descartados = catalogo.descartados(catalogo.carregar_config())
        for chave in ("generation_00077:build", "generation_00077:estreia"):
            motivo = descartados.get(chave, "")
            self.assertIn("luta muda", motivo, chave)
            self.assertIn("fora do banco", motivo, chave)


class FilaDeIdentidadePulaDescartada(unittest.TestCase):
    """A `generation_00077` foi descartada com o payoff do Digen `pending`: a
    rodada noturna gastaria 12-15 min de Digen num video que nao vai ao ar.
    O job fica na fila (reversivel), mas ninguem o reivindica."""

    def setUp(self):
        from builds.identity import queue as fila
        self.fila = fila
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = patch.object(fila, "ARQUIVO_FILA", Path(tmp.name) / "queue.json")
        p.start()
        self.addCleanup(p.stop)
        for gid in ("generation_00077", "generation_00090"):
            fila.enqueue(gid, "prompt", slot="character")

    def _descartar(self, config):
        p = patch.object(catalogo, "carregar_config", lambda: config)
        p.start()
        self.addCleanup(p.stop)

    def test_build_descartada_nao_e_reivindicada(self):
        self._descartar({"descartados": {
            "generation_00077:build": {"motivo": "luta muda"}}})
        self.assertEqual({"generation_00077"}, self.fila.geracoes_descartadas())
        job = self.fila.claim(3)
        self.assertEqual("generation_00090", job["generation_id"])
        self.assertIsNone(self.fila.claim(3))
        self.assertFalse(self.fila.tem_reivindicavel(3))
        # Nada saiu da fila: continua `pending`, pronta para voltar.
        linha = [j for j in self.fila.listar()
                 if j["generation_id"] == "generation_00077"]
        self.assertEqual("pending", linha[0]["status"])

    def test_so_a_estreia_descartada_nao_para_o_payoff(self):
        # 00066: so a estreia saiu; a build (e o payoff dela) seguem.
        self._descartar({"descartados": {
            "generation_00077:estreia": {"motivo": "muda"}}})
        self.assertEqual(set(), self.fila.geracoes_descartadas())
        self.assertIsNotNone(self.fila.claim(3))
        self.assertIsNotNone(self.fila.claim(3))

    def test_sem_a_linha_o_job_volta(self):
        self._descartar({})
        self.assertTrue(self.fila.tem_reivindicavel(3))


if __name__ == "__main__":
    unittest.main()
