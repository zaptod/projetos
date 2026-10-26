# -*- coding: utf-8 -*-
"""A serie do Blue Lock no relatorio diario (26/10/2026).

O `metas` das 21:00 passou a trazer UMA linha por episodio e plataforma e os
comentarios novos da serie (so leitura). Os casos vazios contam: sem episodio
e sem leitura de comentario o relatorio NAO pode soar como "tudo bem".

Nada aqui vai a rede: `agora` explicito = so disco, sem marcar nada.
"""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from remoto import comandos, config, relatorios

from builds.publicar import metricas


class _SerieNumaPasta(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = mock.patch.object(metricas, "OUTPUTS", Path(self.tmp.name))
        patch.start()
        self.addCleanup(patch.stop)
        (Path(self.tmp.name) / "_serie_bluelock").mkdir()


class AsLinhasDaSerie(_SerieNumaPasta):
    AGORA = datetime(2026, 10, 27, 21, 0)

    def test_sem_episodio_o_bloco_nao_soa_a_nota_boa(self):
        texto = "\n".join(relatorios._serie(self.AGORA))
        self.assertIn("Série Blue Lock", texto)
        self.assertIn("nenhum episódio publicado", texto)

    def test_sem_leitura_de_comentario_o_bloco_avisa(self):
        texto = "\n".join(relatorios._comentarios_da_serie(self.AGORA))
        self.assertIn("nenhuma leitura", texto)
        self.assertNotIn("nenhum comentário novo", texto)

    def test_o_episodio_do_ledger_aparece_com_as_duas_plataformas(self):
        ledger = Path(self.tmp.name) / "_serie_bluelock" / "publicados.jsonl"
        ledger.write_text("\n".join(json.dumps(l) for l in (
            {"quando": "2026-10-26T10:22:49", "plataforma": "youtube",
             "youtube_id": "8RFvQp9VogE", "episodio": 1, "publicado": True},
            {"quando": "2026-10-26T11:00:34", "plataforma": "tiktok",
             "episodio": 1, "publicado": True})) + "\n", encoding="utf-8")
        texto = "\n".join(relatorios._serie(self.AGORA))
        self.assertIn("Ep. 1", texto)
        self.assertIn("YouTube", texto)
        self.assertIn("TikTok", texto)

    def test_o_bloco_que_quebra_nao_derruba_as_metas(self):
        with mock.patch("builds.publicar.serie_metricas.linhas_do_relatorio",
                        side_effect=RuntimeError("boom")):
            texto = "\n".join(relatorios._serie(self.AGORA))
        self.assertIn("falhou", texto)

    def test_com_agora_explicito_nao_marca_comentario_como_avisado(self):
        from builds.publicar import serie_comentarios as C
        dado = C.carregar()
        C.guardar(dado, "youtube", "v", [{"id": "c1", "texto": "oi"}], self.AGORA)
        C.gravar(dado)
        relatorios._comentarios_da_serie(self.AGORA)
        self.assertIsNone(C.carregar()["comentarios"]["youtube:c1"]["avisado_em"])


class OsComandos(unittest.TestCase):

    def test_comentarios_e_comando_mas_nao_e_relatorio_automatico(self):
        self.assertIs(comandos.TABELA["comentarios"], comandos.comentarios)
        self.assertIn("comentarios", relatorios.RELATORIOS)
        # Relatorio automatico novo e decisao do Adrian: vai DENTRO do metas.
        self.assertNotIn("comentarios", config.PADRAO["relatorios"])


if __name__ == "__main__":
    unittest.main()
