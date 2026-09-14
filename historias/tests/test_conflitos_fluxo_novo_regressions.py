# -*- coding: utf-8 -*-
"""Guardas contra os conflitos do fluxo novo (14/09/2026).

Antes de criar e publicar a primeira historia no formato novo (1,7x e tela
dividida), uma varredura com verificadores independentes confirmou conflitos
entre a criacao, a postagem e o reparo. Cada classe aqui trava um deles.

Rode de dentro de historias/:
    python -m unittest tests.test_conflitos_fluxo_novo_regressions -v
"""
from __future__ import annotations

import importlib.util
import inspect
import tempfile
import unittest
from pathlib import Path

from contos.pipeline import reparo
from contos.roteiro import gerar

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_conflitos", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class ContaDoLLMTests(unittest.TestCase):

    def test_criacao_espera_a_postagem_liberar_o_gemini(self):
        """A postagem das :07 segura o Gemini por ate ~30 min no parecer."""
        self.assertGreaterEqual(gerar.ESPERA_DA_CONTA_S, 1500)
        fonte = inspect.getsource(gerar)
        self.assertEqual(2, fonte.count("esperar=ESPERA_DA_CONTA_S"))


class MetadeDeBaixoTests(unittest.TestCase):

    def test_marca_na_metade_de_baixo_vista_no_video_e_o_formato(self):
        self.assertTrue(reparo._motivo_e_do_formato(
            ["cena 6: logotipo visivel na metade de baixo"], 6,
            "video inteiro (1:30)"))

    def test_na_folha_recortada_a_mesma_frase_ainda_refaz(self):
        self.assertFalse(reparo._motivo_e_do_formato(
            ["cena 6: logotipo visivel na metade de baixo"], 6,
            "folha de contato"))

    def test_colagem_de_verdade_vence_ate_no_video(self):
        self.assertFalse(reparo._motivo_e_do_formato(
            ["cena 6: a imagem é uma tela dividida com dois quadros "
             "empilhados, e maquiagem na metade de baixo"], 6,
            "video inteiro (1:30)"))

    def test_mulher_se_maquiando_e_o_fundo(self):
        self.assertTrue(reparo._motivo_e_do_formato(
            ["cena 4: aparece outra mulher se maquiando que nao e a "
             "protagonista"], 4, "video inteiro (1:30)"))

    def test_o_filtro_vale_para_rosto_e_narracao_antes_de_mexer_no_roteiro(self):
        fonte = inspect.getsource(reparo._plano_pelo_veto_da_ia)
        laco = 'for classe in ("imagem", "rosto", "narracao")'
        self.assertIn(laco, fonte)
        self.assertLess(fonte.index(laco), fonte.index("C.fixar_protagonista("))
        self.assertLess(fonte.index(laco), fonte.index("C.reescrever_prompts("))


class PublicacaoManualRegistraTikTokTests(unittest.TestCase):

    def test_main_publicar_confere_e_grava_o_tiktok_como_a_grade(self):
        """Sem registro, a postagem das :07 subiria o mesmo video de novo."""
        fonte = (Path(__file__).resolve().parents[1] / "main.py").read_text(
            encoding="utf-8")
        corpo = fonte[fonte.index("def cmd_publicar("):]
        corpo = corpo[:corpo.index("\ndef ")]
        trecho = corpo[corpo.index("if args.tiktok:"):]
        self.assertLess(trecho.index('ja_publicado(alvo.id, "tiktok")'),
                        trecho.index("catalogo.publicar_tiktok("))
        self.assertLess(trecho.index("_tk.confirmado(estado)"),
                        trecho.index('_serie.registrar(alvo, estado, "tiktok"'))


class SerieSemBuracoTests(unittest.TestCase):

    def _fila(self, partes, publicados):
        postar = _postar()
        from contos.publicar import catalogo, serie

        def _video(h, p):
            return type("V", (), {"id": f"{h}:celular:p{p:02d}",
                                  "fonte_id": h, "perfil": "celular",
                                  "parte": p})()

        videos = [_video(h, p) for h, p in partes]
        self.addCleanup(setattr, catalogo, "listar", catalogo.listar)
        self.addCleanup(setattr, serie, "publicados", serie.publicados)
        catalogo.listar = lambda: videos
        serie.publicados = lambda: publicados
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        postar.PRIORIDADE = Path(tmp.name) / "prioridade.json"
        return [v.id for v in postar.fila_de_historias()]

    def test_parte_cuja_anterior_nao_existe_nao_entra(self):
        fila = self._fila([("historia_00012", 2), ("historia_00012", 3),
                           ("historia_00011", 1)], [])
        self.assertEqual(["historia_00011:celular:p01"], fila)

    def test_anterior_ja_publicada_sem_mp4_nao_bloqueia(self):
        fila = self._fila([("historia_00012", 2)], [
            {"video_id": "historia_00012:celular:p01",
             "fonte_id": "historia_00012", "parte": 1, "url": "x"}])
        self.assertEqual(["historia_00012:celular:p02"], fila)

    def test_serie_inteira_continua_igual(self):
        fila = self._fila([("historia_00012", 1), ("historia_00012", 2)], [])
        self.assertEqual(["historia_00012:celular:p01",
                          "historia_00012:celular:p02"], fila)


if __name__ == "__main__":
    unittest.main()
