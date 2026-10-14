# -*- coding: utf-8 -*-
"""SCR-PT (14/10/2026): chaves de config sem leitor ou com padrao diferente.

Mudar uma chave sem leitor nao muda nada; um padrao no codigo diferente do
arquivo faz o comportamento mudar muito so quando a chave some. A tabela da
auditoria (`panorama-configs.md`) tinha 24; aqui ficam as que sairam e os
padroes que passaram a ser os do arquivo. Ficaram de proposito, com leitor
de teste ou de humano: `agenda.json` `piso_de_estoque` (teste do teto),
`identity.json` `blocos_identidade` (teste de cobertura do prompt),
`capacidades.json` `faz` (texto para quem le) e `servicos.json` `saude`.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _json(caminho: str) -> dict:
    return json.loads((RAIZ / caminho).read_text(encoding="utf-8-sig"))


class ChavesSemLeitorTests(unittest.TestCase):
    def test_as_que_sairam(self):
        render_h = _json("historias/config/render.json")
        self.assertNotIn("accent_alt", render_h["colors"])
        self.assertNotIn("text_dim", render_h["colors"])
        self.assertNotIn("corte_aperto", render_h["camera"])
        self.assertNotIn("text_dim", _json("random_builds/config/render.json")["colors"])
        self.assertNotIn("reveal", _json("random_builds/config/editing.json")["durations"])
        presets = _json("random_builds/config/probability.json")["presets"]
        self.assertNotIn("stat_generous", presets)
        self.assertNotIn("body_normal", presets)
        self.assertNotIn("tiktok", _json("historias/config/publicacao.json")["um_clique"])
        self.assertNotIn("postar_automatico",
                         _json("random_builds/config/publicacao.json")["tiktok"])
        self.assertNotIn("tentativas_por_secao", _json("mimetizar/config/biblia.json"))
        coleta = _json("mimetizar/config/coleta.json")
        self.assertNotIn("cookies_do_perfil", coleta)
        self.assertNotIn("timeout_por_video_s", coleta)


class PadraoIgualAoArquivoTests(unittest.TestCase):
    def test_agenda(self):
        from contos.pipeline import agenda
        config = _json("historias/config/agenda.json")
        self.assertEqual(config["reparos_por_rodada"], agenda.PADRAO_REPAROS_POR_RODADA)
        self.assertEqual(config["minutos_minimos"], agenda.PADRAO_MINUTOS_MINIMOS)
        self.assertEqual(config["minutos_por_historia"],
                         agenda.PADRAO_MINUTOS_POR_HISTORIA)
        self.assertEqual(config["passos_por_rodada"], agenda.PADRAO_PASSOS_POR_RODADA)

    def test_voz(self):
        from builds.content import voz
        arquivo = _json("random_builds/config/render.json")["audio"]["voz"]
        for chave in ("taxa", "max_atempo", "folga"):
            self.assertEqual(arquivo[chave], voz.PADRAO[chave], chave)

    def test_rodizio_de_imagem(self):
        fonte = (RAIZ / "ias" / "imagem.py").read_text(encoding="utf-8")
        self.assertNotIn('"picasso"]', fonte.split("def rodizio_ordem")[1][:600])


if __name__ == "__main__":
    unittest.main()
