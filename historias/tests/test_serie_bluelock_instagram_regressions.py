# -*- coding: utf-8 -*-
"""O Instagram na rodada da serie do Blue Lock (26/10/2026).

Contas de mao:
  - SEM CONTA (caso ZERO): a rodada das 20:37 publica YouTube e TikTok como
    sempre e a ficha NAO tem a chave `instagram` (nenhum alarme, nenhuma linha
    no ledger, o funil do Instagram nem e chamado);
  - COM CONTA (login conferido): 3 linhas no ledger PROPRIO (youtube, tiktok,
    instagram), o Instagram por ULTIMO, `feito` verdadeiro, url do Reel na
    linha; a 2a rodada no mesmo horario nao publica nada;
  - Instagram que FALHA: YouTube e TikTok ja saidos, ficha com
    `instagram_falha`, nenhuma linha de instagram no ledger, e o episodio
    continua sendo o proximo do Instagram (nao pula);
  - o clique saiu e nao houve confirmacao: o Instagram nao vira "publicado";
  (a ficha de voo com destino instagram e testada em random_builds:
  `ContratoDoPostarTests`)

Rode de dentro de historias/:
    python -m unittest tests.test_serie_bluelock_instagram_regressions -v
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from builds import contas
from builds.publicar import metricas
from builds.publicar import serie_bluelock as serie
from tests import test_serie_bluelock_postar_regressions as base

GRADE_DAS_HISTORIAS_REAL = True


class RodadaComInstagramTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        raiz = Path(self.tmp.name)
        self.fonte = raiz / "publicar"
        self.fonte.mkdir()
        antes = os.environ.get("NF_SERIE_BLUELOCK")
        os.environ["NF_SERIE_BLUELOCK"] = str(self.fonte)
        self.addCleanup(lambda: os.environ.pop("NF_SERIE_BLUELOCK", None)
                        if antes is None
                        else os.environ.__setitem__("NF_SERIE_BLUELOCK", antes))
        self._trocar(metricas, "OUTPUTS", raiz / "outputs")
        self._trocar(contas, "ARQUIVO", str(raiz / "contas.json"))
        self._trocar(contas, "runtime_dir", lambda: raiz)
        self.m = base._postar()
        self.m._linha = lambda *_a, **_k: None
        self._trocar(self.m.grade, "slot", lambda agora=None: 20)
        self.chamadas = []
        mp4 = self.fonte / "EP01.mp4"
        mp4.write_bytes(b"episodio aprovado")
        (self.fonte / "ep01.json").write_text(json.dumps({
            "episodio": 1, "arquivo": str(mp4), "sha256": serie.sha256_de(mp4),
            "titulo": base.TITULO, "descricao": base.DESCRICAO,
            "tags": base.TAGS, "idioma": "pt",
            "aprovado_por_conferente": True}, ensure_ascii=False),
            encoding="utf-8")
        self._dubles()

    def _trocar(self, objeto, nome, valor):
        original = getattr(objeto, nome)
        setattr(objeto, nome, valor)
        self.addCleanup(setattr, objeto, nome, original)

    def _dubles(self, instagram="publicado no Instagram", url="", levanta=None):
        def yt(alvo, laudo=None):
            self.chamadas.append("youtube")
            laudo.update({"clicou": True, "visibilidade": "public",
                          "estado": "publicado", "youtube_id": "abc123XYZ_-",
                          "confirmado": True})
            return "publicado no YouTube"

        def tk(alvo, falha=None):
            self.chamadas.append("tiktok")
            serie.registrar(alvo, "publicado no TikTok", "tiktok",
                            {"publicado": True, "estado": "publicado"})
            return "publicado no TikTok"

        def ig(alvo, falha=None):
            self.chamadas.append("instagram")
            if levanta:
                falha.update({"tipo": "ContaErrada", "mensagem": levanta})
                return ""
            if instagram.startswith("publicado"):
                extra = {"publicado": True, "estado": "publicado"}
                if url:
                    extra["url"] = url
                serie.registrar(alvo, instagram, "instagram", extra)
            return instagram
        self._trocar(self.m, "_youtube_da_serie", yt)
        self._trocar(self.m, "_tiktok_da_serie", tk)
        self._trocar(self.m, "_instagram_da_serie", ig)
        self._trocar(self.m, "_garantir_marca", lambda *a, **k: True)

    def _ligar(self):
        contas.escolher("instagram", "bluelock", "egoistsoccer")
        contas.identificar("instagram", "egoistsoccer", rotulo="@egoistsoccer",
                           identificador="egoistsoccer")

    def _plataformas(self):
        return sorted(l["plataforma"] for l in metricas.publicados("bluelock"))

    def test_sem_conta_o_instagram_nem_aparece(self):
        ficha = self.m.postar_bluelock()
        self.assertTrue(ficha["feito"])
        self.assertEqual(self.chamadas, ["youtube", "tiktok"])
        self.assertNotIn("instagram", ficha)
        self.assertNotIn("instagram_falha", ficha)
        self.assertEqual(self._plataformas(), ["tiktok", "youtube"])

    def test_com_conta_sai_por_ultimo_e_uma_vez_por_horario(self):
        self._ligar()
        self._dubles(url="https://www.instagram.com/reel/NOVO123/")
        ficha = self.m.postar_bluelock()
        self.assertTrue(ficha["feito"], ficha)
        self.assertEqual(self.chamadas, ["youtube", "tiktok", "instagram"])
        self.assertEqual(self._plataformas(),
                         ["instagram", "tiktok", "youtube"])
        ig = next(l for l in metricas.publicados("bluelock")
                  if l["plataforma"] == "instagram")
        self.assertEqual(ig["url"], "https://www.instagram.com/reel/NOVO123/")
        self.assertTrue(metricas.publicado(ig))
        self.chamadas.clear()
        segunda = self.m.postar_bluelock()
        self.assertTrue(segunda["fora_da_grade"], segunda)
        self.assertEqual(self.chamadas, [])

    def test_instagram_que_falha_nao_derruba_os_outros_nem_pula_o_episodio(self):
        self._ligar()
        self._dubles(levanta="o Instagram esta logado como @pessoal")
        ficha = self.m.postar_bluelock()
        self.assertTrue(ficha["feito"])                  # YouTube e TikTok
        self.assertIn("@pessoal", ficha["instagram_falha"])
        self.assertEqual(ficha["instagram"], "")
        self.assertEqual(self._plataformas(), ["tiktok", "youtube"])
        # o proximo do Instagram continua sendo o ep1
        aprovados, _ = serie.episodios()
        ep, _ = serie.escolher("instagram", aprovados,
                               metricas.publicados("bluelock"), set())
        self.assertEqual(ep.id, "bluelock_ep01")

    def test_clique_sem_confirmacao_nao_vira_publicado(self):
        self._ligar()
        self._dubles(instagram="cliquei em publicar, mas o Instagram nao "
                               "confirmou.")
        ficha = self.m.postar_bluelock()
        self.assertEqual(self._plataformas(), ["tiktok", "youtube"])
        self.assertTrue(ficha["feito"])                  # pelos outros dois


if __name__ == "__main__":
    unittest.main()
