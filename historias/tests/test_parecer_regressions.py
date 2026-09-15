# -*- coding: utf-8 -*-
"""Uma IA assiste ao video antes de ele sair (11/09/2026).

Pedido dele: "passar o video no gemini antes de postar para saber o que ele
acha, e postar apenas se ele der um comando correto; caso ele de um comando
negativo o texto vem pra esse chat".

O CAMINHO ATE FUNCIONAR, porque cada tropeco virou uma regra aqui:

1. Li o atributo `accept` do input do Gemini, nao vi extensao de video e
   concluí que ele nao aceitava mp4. Errado: `accept` e filtro do seletor de
   arquivos do sistema, e `set_input_files` passa por cima. Ele aceita.
2. O botao de anexo nao era mais "Adicionar arquivos": e "Envio e
   ferramentas". Sem ele, o input nem existe no DOM.
3. A miniatura aparece em ~10 s e a duracao (`1:47`) em ~30 s. So a duracao
   prova que o arquivo subiu inteiro; perguntar antes faz o modelo responder
   sobre um video que nao recebeu, e a resposta parece boa.
4. O dialogo de direitos autorais abre DEPOIS do clique em enviar, nao ao
   anexar. Com ele aberto o botao reporta `disabled: false` e o clique nao
   faz nada — quatro tentativas morreram em "cliquei em enviar mas nada
   mudou na tela".

Medido funcionando: 33 MB, 100 s do inicio ao veredito, e o parecer apontou
duas cenas cuja imagem contradiz a narracao.

    cd e:\\projetos\\historias
    python -m pytest tests/test_parecer_regressions.py -q
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from contos.publicar import parecer


class VereditoTests(unittest.TestCase):
    """A leitura da resposta e MECANICA: o veto nao pode depender de
    interpretar prosa."""

    def test_aprovado_e_aprovado(self):
        self.assertTrue(parecer.ler_veredito("APROVADO")["aprovado"])

    def test_reprovado_traz_os_motivos_um_por_linha(self):
        lido = parecer.ler_veredito(
            "REPROVADO\nquadro 6: a imagem contradiz a narracao\n"
            "quadro 8: a personagem muda de rosto")
        self.assertFalse(lido["aprovado"])
        self.assertEqual(2, len(lido["motivos"]))
        self.assertIn("quadro 6", lido["motivos"][0])

    def test_so_a_primeira_linha_decide(self):
        """'APROVADO, mas cuidado com o ritmo' aprovou. Ler o texto inteiro
        atras da palavra faria qualquer ressalva virar veto."""
        self.assertTrue(parecer.ler_veredito(
            "APROVADO\n\nObservacao: o ritmo podia ser mais rapido."
        )["aprovado"])

    def test_reprovado_sem_motivo_ainda_e_reprovado(self):
        lido = parecer.ler_veredito("REPROVADO")
        self.assertFalse(lido["aprovado"])
        self.assertEqual(["sem motivo dado"], lido["motivos"])

    def test_resposta_que_nao_decide_NAO_e_reprovacao(self):
        """A diferenca que mais importa: 'nao consegui perguntar' e
        'a IA reprovou' pedem acoes opostas. Confundir as duas para o canal
        toda vez que o navegador tossir."""
        with self.assertRaises(parecer.SemParecer):
            parecer.ler_veredito("Claro! Vou analisar o video para voce.")

    def test_resposta_vazia_nao_e_reprovacao(self):
        with self.assertRaises(parecer.SemParecer):
            parecer.ler_veredito("   ")

    def test_marcacao_em_volta_da_palavra_nao_atrapalha(self):
        self.assertFalse(parecer.ler_veredito("**REPROVADO**\nquadro 1: x"
                                              )["aprovado"])


class PromptTests(unittest.TestCase):

    ROTEIRO = {"partes": [{"n": 1, "cenas": [
        {"n": 1, "narracao": "Ela desceu a rua arrastando a cadeira.",
         "imagem": "a woman dragging a chair"}]}]}

    class _Video:
        titulo = "A mola frouxa (Parte 1/2)"
        caminho = "x.mp4"

    def _texto(self, **kw):
        return parecer.prompt(self._Video(), self.ROTEIRO, 1,
                              {"duracao": 107, "media_db": -16.2,
                               "palavras_por_s": 2.4}, **kw)

    def test_pede_a_palavra_fechada(self):
        texto = self._texto()
        self.assertIn("APROVADO", texto)
        self.assertIn("REPROVADO", texto)
        self.assertIn("Primeira linha", texto)

    def test_manda_assistir_quando_e_o_video(self):
        self.assertIn("Assista ao video", self._texto())

    def test_explica_a_folha_quando_e_a_folha(self):
        self.assertIn("FOLHA DE CONTATO", self._texto(pela_folha=True))

    def test_a_legenda_do_canal_nao_pode_reprovar(self):
        """A legenda amarela entra em TODO video de proposito. Na primeira
        versao o prompt dizia so 'nao pode ter texto', e a IA reprovou um
        video bom por causa de um papel escrito dentro da cena."""
        texto = self._texto()
        self.assertIn("legenda amarela", texto)
        self.assertIn("faz parte da CENA", texto)

    def test_nao_reprova_por_gosto(self):
        self.assertIn("gosto pessoal", self._texto())

    def test_a_narracao_vai_junto(self):
        self.assertIn("arrastando a cadeira", self._texto())

    def test_as_medidas_ja_feitas_nao_sao_repedidas(self):
        self.assertIn("nao precisa julgar de novo", self._texto())


class FolhaTests(unittest.TestCase):

    def test_a_folha_e_reserva_e_nao_o_caminho_principal(self):
        """O video inteiro vai primeiro; a folha so entra quando ele nao
        sobe. Trocar essa ordem tira o audio e o movimento do parecer."""
        fonte = Path(parecer.__file__).read_text(encoding="utf-8")
        trecho = fonte[fonte.index("with abrir_cliente"):]
        self.assertLess(trecho.index("anexar_video"),
                        trecho.index("anexar([folha]"),
                        "a folha nao pode ser tentada antes do video")

    def test_o_mosaico_cobre_o_video_inteiro(self):
        """`fps` fracionario e o que espaca os quadros. Pegar os N primeiros
        daria doze imagens do mesmo primeiro segundo."""
        fonte = Path(parecer.__file__).read_text(encoding="utf-8")
        self.assertIn("quadros / duracao", fonte)

    def test_video_ilegivel_vira_SemParecer_e_nao_reprovacao(self):
        with tempfile.TemporaryDirectory() as tmp:
            falso = Path(tmp) / "nao_e_video.mp4"
            falso.write_bytes(b"nada")
            with self.assertRaises(parecer.SemParecer):
                parecer.folha_de_contato(falso, Path(tmp) / "f.jpg")


class GateTests(unittest.TestCase):
    """A ligacao com a postagem: quem reprova impede, quem cala nao."""

    def setUp(self):
        import importlib.util
        caminho = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"
        spec = importlib.util.spec_from_file_location("postar_parecer", caminho)
        self.postar = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.postar)
        # Estes testes cobrem a pergunta AO VIVO, que continua atras da chave.
        # O padrao desde 15/09/2026 e a postagem nao perguntar.
        self.postar.PEDIR_PARECER_NA_POSTAGEM = True

    def test_por_padrao_a_postagem_nao_pergunta_ao_gemini(self):
        """15/09/2026: 'amanha nos horarios certos seja postar'."""
        import importlib.util
        caminho = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"
        spec = importlib.util.spec_from_file_location("postar_parecer_padrao", caminho)
        postar = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(postar)
        self.assertFalse(postar.PEDIR_PARECER_NA_POSTAGEM)

        def nao_pergunta(*_a, **_k):
            raise AssertionError("a postagem perguntou ao Gemini")
        self._com_parecer({"aprovado": False, "motivos": [], "texto": ""})
        from contos.publicar import parecer as modulo
        modulo.pedir = nao_pergunta
        postar._veto_vencido = lambda _alvo: False
        antes = modulo.lembrado
        self.addCleanup(setattr, modulo, "lembrado", antes)
        modulo.lembrado = lambda _v: None
        self.assertEqual("", postar._parecer_da_ia(self._Alvo(), {}, {}))

    class _Alvo:
        id = "historia_00008:celular:p01"
        fonte_id = "historia_00008"
        parte = 1
        titulo = "A mola frouxa"

    def _com_parecer(self, resultado):
        from contos.publicar import parecer as modulo
        antes = modulo.pedir

        def falso(*_a, **_k):
            if isinstance(resultado, Exception):
                raise resultado
            return resultado

        modulo.pedir = falso
        self.addCleanup(lambda: setattr(modulo, "pedir", antes))

    def test_aprovado_libera(self):
        self._com_parecer({"aprovado": True, "motivos": [], "texto": "APROVADO"})
        self.assertEqual("", self.postar._parecer_da_ia(self._Alvo(), {}, {}))

    def test_reprovado_impede_e_diz_por_que(self):
        self._com_parecer({"aprovado": False, "motivos": ["quadro 6: contradiz"],
                           "texto": "REPROVADO\nquadro 6: contradiz"})
        self.postar.avisar_reprovacao = lambda *_a, **_k: None
        veto = self.postar._parecer_da_ia(self._Alvo(), {}, {})
        self.assertIn("REPROVOU", veto)
        self.assertIn("quadro 6", veto)

    def test_sem_parecer_publica_por_padrao(self):
        """Conta ocupada por uma geracao de 4 h nao pode parar o canal: as
        oito checagens mecanicas ja passaram neste ponto."""
        from contos.publicar import parecer as modulo
        self._com_parecer(modulo.SemParecer("a conta esta em uso"))
        self.assertTrue(self.postar.PUBLICAR_SEM_PARECER)
        self.assertEqual("", self.postar._parecer_da_ia(self._Alvo(), {}, {}))

    def test_com_a_trava_ligada_sem_parecer_impede(self):
        from contos.publicar import parecer as modulo
        self._com_parecer(modulo.SemParecer("a conta esta em uso"))
        self.postar.PUBLICAR_SEM_PARECER = False
        veto = self.postar._parecer_da_ia(self._Alvo(), {}, {})
        self.assertIn("nao deu para pedir", veto)


if __name__ == "__main__":
    unittest.main()
