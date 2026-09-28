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


if __name__ == "__main__":
    unittest.main()
