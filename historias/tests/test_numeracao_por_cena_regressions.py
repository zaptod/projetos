# -*- coding: utf-8 -*-
"""O numero que a IA da aponta CENA, e o reparador so age com ele (13/09/2026).

Ate aqui o parecer pedia "o numero do quadro" sem dizer o que era um quadro.
Na folha de contato era a sexta de doze miniaturas espacadas no tempo, numa
parte de 13 ou 14 cenas; no video, era a contagem do proprio Gemini. O
reparador lia esse numero como cena e podia refazer a imagem boa e deixar a
ruim.

E dois defeitos que o reparador nao sabia consertar: imagem que nao mostra a
narracao da cena, e protagonista trocando de rosto entre as cenas.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from contos.pipeline import conserto_de_cena as C
from contos.publicar import parecer
from contos.roteiro import roteiro as R
from contos.video import plano


class PlanoTests(unittest.TestCase):

    def test_a_cena_dividida_em_planos_volta_a_ser_uma(self):
        with tempfile.TemporaryDirectory() as tmp:
            arquivo = Path(tmp) / "edit_plan.json"
            arquivo.write_text(json.dumps({"events": [
                {"type": "titulo", "start": 0, "duration": 2},
                {"type": "cena", "n": 1, "start": 0.0, "duration": 5.0,
                 "narracao": "um"},
                {"type": "cena", "n": 2, "start": 5.0, "duration": 3.0,
                 "narracao": "dois"},
                {"type": "cena", "n": 2, "start": 8.0, "duration": 4.0,
                 "narracao": "dois"}]}), encoding="utf-8")
            cenas = plano.cenas_do_plano(arquivo)
        self.assertEqual([1, 2], [c["n"] for c in cenas])
        self.assertEqual((5.0, 12.0), (cenas[1]["inicio"], cenas[1]["fim"]))

    def test_sem_plano_estima_pelo_tempo_do_roteiro(self):
        roteiro = {"partes": [{"n": 1, "cenas": [
            {"n": 1, "tempo": 4, "narracao": "a"},
            {"n": 2, "tempo": 6, "narracao": "b"}]}]}
        cenas = plano.cenas_do_roteiro(roteiro, 1)
        self.assertEqual([(0.0, 4.0), (4.0, 10.0)],
                         [(c["inicio"], c["fim"]) for c in cenas])


class _Video:
    titulo = "A mola frouxa (Parte 1/2)"
    caminho = "x.mp4"


class PromptNumeradoTests(unittest.TestCase):

    ROTEIRO = {"partes": [{"n": 1, "cenas": [
        {"n": 1, "tempo": 5, "imagem": "x",
         "narracao": "Ela desceu a rua arrastando a cadeira."},
        {"n": 2, "tempo": 5, "imagem": "y",
         "narracao": "O vizinho abriu a janela."}]}]}

    def _texto(self, **kw):
        return parecer.prompt(_Video(), self.ROTEIRO, 1, {}, **kw)

    def test_cada_cena_vai_com_o_trecho_dela(self):
        texto = self._texto()
        self.assertIn("CENA 1 (0s a 5s)", texto)
        self.assertIn("CENA 2 (5s a 10s)", texto)

    def test_pede_numero_de_cena_e_nao_de_quadro(self):
        texto = self._texto()
        self.assertIn("'cena 7: ...'", texto)
        self.assertNotIn("'quadro 7: ...'", texto)

    def test_a_folha_por_cena_diz_que_quadro_e_cena(self):
        self.assertIn("O quadro 1 e a CENA 1", self._texto(pela_folha=True))

    def test_a_folha_no_tempo_nao_promete_quadro_por_cena(self):
        texto = self._texto(pela_folha=True, por_cena=False)
        self.assertNotIn("O quadro 1 e a CENA 1", texto)

    def test_pede_a_descricao_do_protagonista(self):
        self.assertIn("PROTAGONISTA:", self._texto())

    def test_a_imagem_tem_de_mostrar_a_narracao_daquela_cena(self):
        self.assertIn("narracao DAQUELA cena", self._texto())


class LeituraDoVereditoTests(unittest.TestCase):

    def test_a_linha_do_protagonista_nao_vira_motivo(self):
        lido = parecer.ler_veredito(
            "REPROVADO\ncena 4: o protagonista muda de rosto\n"
            "PROTAGONISTA: East Asian man, early 30s, short black hair, "
            "thin scar on the left eyebrow, gray shirt")
        self.assertEqual(["cena 4: o protagonista muda de rosto"],
                         lido["motivos"])
        self.assertIn("East Asian", lido["protagonista"])

    def test_aprovado_tem_protagonista_vazio(self):
        self.assertEqual("", parecer.ler_veredito("APROVADO")["protagonista"])


class LembreteNumeradoTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        pasta = Path(self._tmp.name)
        antes = parecer.LEMBRETES
        parecer.LEMBRETES = pasta / "_pareceres.json"
        self.addCleanup(lambda: setattr(parecer, "LEMBRETES", antes))
        mp4 = pasta / "final_celular_p02.mp4"
        mp4.write_bytes(b"um video")

        class _V:
            id = "historia_00004:celular:p02"
        self.video = _V()
        self.video.caminho = mp4

    def test_guarda_a_numeracao_e_o_protagonista(self):
        parecer.lembrar(self.video, {
            "aprovado": False, "motivos": ["cena 4: muda de rosto"],
            "vista": "video inteiro (2:03)", "numeracao": "cena",
            "protagonista": "East Asian man"})
        ficha = parecer.lembrado(self.video)
        self.assertEqual("cena", ficha["numeracao"])
        self.assertEqual("East Asian man", ficha["protagonista"])

    def test_folha_por_cena_substitui_video_sem_numeracao(self):
        """O video viu mais, mas o numero dele nao aponta cena nenhuma."""
        parecer.lembrar(self.video, {
            "aprovado": False, "motivos": ["quadro 6: tela dividida"],
            "vista": "video inteiro (2:03)"})
        parecer.lembrar(self.video, {
            "aprovado": False, "motivos": ["cena 6: tela dividida"],
            "vista": "folha de contato", "numeracao": "cena"})
        self.assertEqual("cena", parecer.lembrado(self.video)["numeracao"])

    def test_folha_nao_substitui_video_que_ja_numerava_cena(self):
        parecer.lembrar(self.video, {
            "aprovado": False, "motivos": ["cena 6: tela dividida"],
            "vista": "video inteiro (2:03)", "numeracao": "cena"})
        parecer.lembrar(self.video, {
            "aprovado": True, "motivos": [],
            "vista": "folha de contato", "numeracao": "cena"})
        ficha = parecer.lembrado(self.video)
        self.assertFalse(ficha["aprovado"])
        self.assertEqual("video inteiro (2:03)", ficha["vista"])


class ClassificacaoTests(unittest.TestCase):

    def test_os_motivos_reais_de_12_de_setembro(self):
        """Os textos do Gemini daquela noite, agora com numero de cena."""
        motivos = [
            "cena 3: a imagem mostra um corredor completamente vazio, "
            "enquanto a narração descreve pessoas sentadas em poltronas",
            "cena 5: a protagonista aparece entrando pela porta ao lado de "
            "Marcus, contrariando a narração",
            "cena 10: o protagonista muda de rosto, parecendo outra pessoa",
            "cena 14: a imagem é uma grade de painéis com a tela dividida",
            "cena 4: a imagem tem uma grade de linhas brancas sobreposta "
            "pelo gerador (marca d'água de grade)",
        ]
        classes = C.classificar(motivos)
        self.assertEqual([3, 5], classes["narracao"])
        self.assertEqual([10], classes["rosto"])
        self.assertEqual([4, 14], classes["imagem"])

    def test_frase_unica_separada_por_ponto_e_virgula(self):
        junto = ("cena 2: a imagem tem tela dividida.; cena 8: o protagonista "
                 "muda para um homem branco de cabelo escuro")
        classes = C.classificar([junto])
        self.assertEqual([2], classes["imagem"])
        self.assertEqual([8], classes["rosto"])

    def test_rosto_escrito_de_outro_jeito_ainda_e_rosto(self):
        """O texto real da primeira rodada, que a lista literal deixou passar."""
        classes = C.classificar([
            "cena 13: o protagonista muda completamente de aparência "
            "(etnia, rosto e cabelo) e de roupa"])
        self.assertEqual([13], classes["rosto"])

    def test_mesmo_rosto_citado_nao_vira_troca_de_rosto(self):
        """"com o mesmo rosto" contradiz a narracao; nao e troca de rosto."""
        classes = C.classificar([
            "cena 8: a mulher que sorri e a propria protagonista (com o mesmo "
            "rosto e casaco), o que contradiz a narracao"])
        self.assertEqual([], classes["rosto"])
        self.assertEqual([8], classes["narracao"])

    def test_so_confia_em_numeracao_por_cena(self):
        self.assertFalse(C.confiavel(None))
        self.assertFalse(C.confiavel({"numeracao": ""}))
        self.assertFalse(C.confiavel({"numeracao": "quadro"}))
        self.assertTrue(C.confiavel({"numeracao": "cena"}))


class ProtagonistaTests(unittest.TestCase):

    def test_troca_dentro_dos_prompts_e_nao_so_na_ficha(self):
        """Os prompts ja trazem a descricao antiga por extenso: trocar so a
        ficha nao mudaria imagem nenhuma."""
        roteiro = {"protagonista": "30s man, short dark hair, tired eyes",
                   "partes": [{"n": 1, "cenas": [
                       {"n": 1, "imagem": "Vertical shot, a 30s man, short "
                                          "dark hair, tired eyes, standing"},
                       {"n": 2, "imagem": "a payment machine on a counter"}]}]}
        nova = ("East Asian man, early 30s, short black hair, thin scar on "
                "the left eyebrow")
        self.assertEqual(1, C.fixar_protagonista(roteiro, nova))
        cena = roteiro["partes"][0]["cenas"][0]["imagem"]
        self.assertIn("thin scar", cena)
        self.assertNotIn("tired eyes", cena)
        self.assertEqual(nova, roteiro["protagonista"])

    def test_descricao_vazia_nao_mexe_em_nada(self):
        roteiro = {"protagonista": "x", "partes": []}
        self.assertEqual(0, C.fixar_protagonista(roteiro, ""))
        self.assertEqual("x", roteiro["protagonista"])


class ReescritaPelaNarracaoTests(unittest.TestCase):

    def test_reescreve_so_as_cenas_apontadas_e_manda_a_narracao(self):
        roteiro = {"protagonista": "p", "partes": [{"n": 2, "cenas": [
            {"n": 3, "narracao": "A sala de espera estava cheia de "
                                 "engravatados.",
             "imagem": "an empty corridor, dim light, vertical"},
            {"n": 4, "narracao": "Ele sorriu.",
             "imagem": "a man smiling, office, vertical"}]}]}
        pedidos = []

        def perguntar(texto):
            pedidos.append(texto)
            return ("a crowded waiting room, men in suits seated in "
                    "armchairs, vertical cinematic shot")

        novos = C.reescrever_prompts(roteiro, 2, [3],
                                     ["cena 3: corredor vazio"],
                                     perguntar=perguntar)
        self.assertEqual([3], list(novos))
        self.assertIn("engravatados", pedidos[0])
        cenas = roteiro["partes"][0]["cenas"]
        self.assertIn("crowded waiting room", cenas[0]["imagem"])
        self.assertEqual("a man smiling, office, vertical", cenas[1]["imagem"])


class GravarRoteiroTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        antes = R.OUTPUTS
        R.OUTPUTS = Path(self._tmp.name)
        self.addCleanup(lambda: setattr(R, "OUTPUTS", antes))
        pasta = R.OUTPUTS / "historia_x"
        pasta.mkdir()
        self.arquivo = pasta / "roteiro.json"
        self.arquivo.write_text(json.dumps(
            {"protagonista": "a", "partes": [], "biblia": {}}),
            encoding="utf-8")

    def test_nunca_grava_um_roteiro_que_perdeu_chave(self):
        """O gravador do roteiro avulso apagaria partes, biblia e
        protagonista de uma serie."""
        with self.assertRaises(ValueError):
            C.gravar_roteiro("historia_x", {"partes": []})
        self.assertIn("biblia", json.loads(self.arquivo.read_text("utf-8")))

    def test_guarda_copia_do_original_uma_vez(self):
        C.gravar_roteiro("historia_x",
                         {"protagonista": "b", "partes": [], "biblia": {}})
        C.gravar_roteiro("historia_x",
                         {"protagonista": "c", "partes": [], "biblia": {}})
        copia = self.arquivo.with_name("roteiro.antes_do_reparo.json")
        self.assertEqual("a", json.loads(copia.read_text("utf-8"))
                         ["protagonista"])
        self.assertEqual("c", json.loads(self.arquivo.read_text("utf-8"))
                         ["protagonista"])


class _Pipeline:

    def __init__(self):
        self.renders = []

    def render(self, historia_id, parte=None, log=print):
        self.renders.append(parte)

    def imagens(self, *_a, **_k):
        return None


class ReparadorSoConfiaEmCenaTests(unittest.TestCase):
    """Dubla tudo que abre navegador ou gera imagem."""

    def setUp(self):
        from contos.pipeline import reparo
        self.reparo = reparo
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        originais = {
            (reparo, "REGISTRO"): reparo.REGISTRO,
            (reparo, "_confirmar_com_a_ia"): reparo._confirmar_com_a_ia,
            (reparo, "_refazer_cenas"): reparo._refazer_cenas,
            (parecer, "lembrado"): parecer.lembrado,
            (R, "carregar"): R.carregar,
        }
        for (modulo, nome), valor in originais.items():
            self.addCleanup(setattr, modulo, nome, valor)
        reparo.REGISTRO = Path(self._tmp.name) / "_reparos.json"
        R.carregar = lambda _hid: {"partes": []}

        class _V:
            id = "historia_00004:celular:p02"
            fonte_id = "historia_00004"
            parte = 2
            caminho = "x.mp4"
        self.video = _V()

    def test_veto_sem_numeracao_e_perguntado_de_novo_antes_de_refazer(self):
        parecer.lembrado = lambda _v: {
            "aprovado": False, "motivos": ["quadro 6: tela dividida"],
            "vista": "video inteiro (2:03)"}
        perguntas = []

        def olhar(*_a, **_k):
            perguntas.append(1)
            return {"aprovado": True, "motivos": [], "numeracao": "cena"}
        self.reparo._confirmar_com_a_ia = olhar

        def nao_pode(*_a, **_k):
            raise AssertionError("refez cena com numero nao confiavel")
        self.reparo._refazer_cenas = nao_pode

        pipeline = _Pipeline()
        saida = self.reparo.reparar(
            self.video, ["a IA reprovou: quadro 6: tela dividida"],
            pipeline=pipeline, log=lambda *_a: None)
        self.assertEqual(1, len(perguntas))
        self.assertEqual("reolhado", saida["acao"])
        self.assertEqual([], pipeline.renders)

    def test_veto_numerado_refaz_a_cena_que_ele_aponta(self):
        parecer.lembrado = lambda _v: {
            "aprovado": False, "vista": "video inteiro (2:03)",
            "numeracao": "cena",
            "motivos": ["cena 6: a imagem e uma tela dividida"]}
        refeitas = []

        def refazer(_pipeline, _hid, _parte, cenas, **_k):
            refeitas.extend(cenas)
            return list(cenas), []
        self.reparo._refazer_cenas = refazer
        self.reparo._confirmar_com_a_ia = lambda *_a, **_k: {
            "aprovado": True, "motivos": []}

        pipeline = _Pipeline()
        saida = self.reparo.reparar(
            self.video, ["a IA reprovou: cena 6: a imagem e uma tela dividida"],
            pipeline=pipeline, log=lambda *_a: None)
        self.assertEqual([6], refeitas)
        self.assertTrue(saida["ok"])
        self.assertEqual([2], pipeline.renders)

    def test_sem_parecer_adia_e_nao_esquece_o_veto(self):
        """Esquecer o veto liberaria o video para a grade sem parecer."""
        parecer.lembrado = lambda _v: {
            "aprovado": False, "motivos": ["quadro 6: x"],
            "vista": "video inteiro (2:03)"}
        self.reparo._confirmar_com_a_ia = lambda *_a, **_k: None
        saida = self.reparo.reparar(
            self.video, ["a IA reprovou: quadro 6: x"],
            pipeline=_Pipeline(), log=lambda *_a: None)
        self.assertEqual("adiado", saida["acao"])


if __name__ == "__main__":
    unittest.main()
