# -*- coding: utf-8 -*-
"""A variante B com titulo PROPRIO volta para a fila; sem ele, fica fora.

Por que existe (27/09/2026): 25 builds estavam fora da fila por "titulo ja
publicado" — 21 variantes "gancho B" (id com sufixo `:B`, mesmo titulo do A)
e 4 re-execucoes de seed fixa. Com o canal em 0 dia de gordura, o Adrian
decidiu: cada variante B ganha titulo proprio. O titulo mora no texto
editado (`catalogo.salvar_texto`), que ja vale sobre o gerado para o painel
e para a grade — nenhum caminho novo de publicacao.

O que este arquivo trava:
1. Sem texto proprio, o B herda o titulo do A e a guarda o barra.
2. Com texto proprio, SO o B muda: o A continua com o titulo que foi ao ar,
   e o do outro perfil tambem nao e tocado.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from builds.publicar import catalogo, titulos

CONFIG = {"titulos": {"build": "{personagem}, {classe} — build {nota}/100"},
          "descricoes": {"build": "Arma: {arma}"},
          "hashtags": {"build": ["#shorts"]}}
CONTEUDO = b"v" * (catalogo.BYTES_MINIMOS + 1)


class VarianteBComTituloProprio(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.outputs = Path(tmp.name) / "outputs"
        pasta = self.outputs / "generation_00040"
        pasta.mkdir(parents=True)
        (pasta / "character.json").write_text(json.dumps(
            {"nome": "Suki Acijaggur", "classe": "Monge (Chi)"}),
            encoding="utf-8")
        (pasta / "build.json").write_text(json.dumps({"final_score": 55}),
                                          encoding="utf-8")
        for perfil in catalogo.PERFIS:
            (pasta / f"final_{perfil}.mp4").write_bytes(CONTEUDO)
            (pasta / f"final_{perfil}_ganchoB.mp4").write_bytes(CONTEUDO)
        self.export = Path(tmp.name) / "publicar"
        for alvo, valor in (("OUTPUTS", self.outputs),
                            ("pasta_export", lambda config=None: self.export)):
            p = patch.object(catalogo, alvo, valor)
            p.start()
            self.addCleanup(p.stop)
        # Pendencias de build (payoff, estreia) nao sao o assunto aqui.
        p = patch.object(catalogo, "pendencias_da_build",
                         lambda pasta, perfil: [])
        p.start()
        self.addCleanup(p.stop)

    def _por_id(self):
        return {v.id: v for v in catalogo.listar(CONFIG)}

    def test_sem_texto_proprio_o_b_repete_o_a_e_fica_fora(self):
        videos = self._por_id()
        a = videos["generation_00040:build:celular"]
        b = videos["generation_00040:build:celular:B"]
        no_ar = titulos.ja_publicados([{"titulo": a.titulo, "publicado": True}])
        self.assertTrue(titulos.repetido(b.titulo, no_ar))

    def test_com_texto_proprio_so_o_b_muda_e_volta_a_fila(self):
        antes = self._por_id()
        a = antes["generation_00040:build:celular"]
        b = antes["generation_00040:build:celular:B"]
        novo = "Suki Acijaggur: monge com Bomba Relógio? A roleta surtou"
        catalogo.salvar_texto(b.id, novo, b.descricao, list(b.hashtags))

        depois = self._por_id()
        self.assertEqual(novo, depois[b.id].titulo)
        self.assertEqual(a.titulo, depois[a.id].titulo)
        self.assertEqual(
            antes["generation_00040:build:normal:B"].titulo,
            depois["generation_00040:build:normal:B"].titulo)
        self.assertEqual(b.descricao, depois[b.id].descricao)
        no_ar = titulos.ja_publicados([{"titulo": a.titulo, "publicado": True}])
        self.assertFalse(titulos.repetido(depois[b.id].titulo, no_ar))


if __name__ == "__main__":
    unittest.main()
