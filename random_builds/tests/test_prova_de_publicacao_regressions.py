# -*- coding: utf-8 -*-
"""O laudo da publicacao: o que de fato deu para provar.

Por que existe (15/09/2026): entre 10 e 15 de setembro, 29 videos entraram no
ledger como publicados e estavam como RASCUNHO no canal. O ledger nao mentiu
por descuido — ele registrava a unica coisa que sabia, que era "a funcao de
publicar nao levantou excecao". Isso nunca foi prova.

Aqui ficam as tres pecas que tornam a afirmacao conferivel por fora:

  `_qualidade_agora`  em que pe o arquivo estava NO INSTANTE do clique;
  `_id_do_video`      o id devolvido pelo Studio, que a API pode desmentir;
  `prova_ok`          a regra que separa "provado" de "nao sei".

Nenhum teste aqui toca a rede nem abre navegador: a pagina e um duble.
"""
import unittest

from builds.publicar import metricas, youtube, youtube_web as Y


class PaginaFalsa:
    """So o que `_qualidade_agora` usa: `evaluate` devolvendo innerText."""

    def __init__(self, texto: str = "", estoura: bool = False):
        self.texto, self.estoura = texto, estoura

    def evaluate(self, _script):
        if self.estoura:
            raise RuntimeError("a pagina fechou no meio")
        return self.texto


class QualidadeNoClique(unittest.TestCase):

    def test_processando_ate_sd_e_nada_pronto(self):
        # A FRASE MEDIDA NA TELA em 15/09/2026, no instante do clique.
        page = PaginaFalsa("Processando até SD ... 3 minutos restantes")
        achado = Y._qualidade_agora(page)
        self.assertEqual(achado["qualidade"], "processando")
        self.assertEqual(achado["falta"], "3 minutos restantes")
        self.assertTrue(achado["reconhecido"])

    def test_processando_ate_hd_quer_dizer_que_o_sd_ja_existe(self):
        # A distincao que o codigo antigo nao fazia: "ate HD" e um estagio
        # ADIANTE de "ate SD" — o video ja existe, so nao na melhor forma.
        page = PaginaFalsa("Processando até HD")
        self.assertEqual(Y._qualidade_agora(page)["qualidade"], "sd")

    def test_envio_concluido_ainda_e_subindo(self):
        page = PaginaFalsa(
            "Envio concluído ... O processamento vai começar em breve")
        self.assertEqual(Y._qualidade_agora(page)["qualidade"], "subindo")

    def test_tela_de_sucesso_conta_como_hd_e_reconhecida(self):
        page = PaginaFalsa("Vídeo publicado — link do vídeo")
        achado = Y._qualidade_agora(page)
        self.assertEqual(achado["qualidade"], "hd")
        self.assertTrue(achado["reconhecido"])

    def test_tela_estranha_diz_hd_mas_avisa_que_nao_entendeu(self):
        # O DIA EM QUE O STUDIO TROCAR AS PALAVRAS. Sem `reconhecido`, a
        # medicao viraria "hd" para tudo e a serie inteira seria uma mentira
        # silenciosa — o mesmo defeito que este arquivo existe para impedir.
        achado = Y._qualidade_agora(PaginaFalsa("bem-vindo ao novo studio"))
        self.assertEqual(achado["qualidade"], "hd")
        self.assertFalse(achado["reconhecido"])

    def test_pagina_morta_nao_levanta(self):
        achado = Y._qualidade_agora(PaginaFalsa(estoura=True))
        self.assertEqual(achado["qualidade"], "desconhecida")
        self.assertFalse(achado["reconhecido"])

    def test_pagina_em_branco_nao_vira_hd(self):
        # Texto vazio e ausencia de informacao, nao aprovacao.
        self.assertEqual(
            Y._qualidade_agora(PaginaFalsa("   "))["qualidade"],
            "desconhecida")

    def test_o_vocabulario_medido_continua_na_lista(self):
        # PROCESSANDO passou a ser DERIVADA de FASES. Se alguem reescrever
        # FASES e perder uma frase, a medicao para de enxergar aquele estagio
        # sem nenhum erro aparecer.
        for frase in ("processando ate sd", "processando ate hd",
                      "processamento vai comecar", "uploading"):
            self.assertIn(frase, Y.PROCESSANDO)


class IdDoVideo(unittest.TestCase):

    def test_reconhece_as_tres_formas_que_o_studio_devolve(self):
        for url, esperado in (
            ("https://youtu.be/bZIDPJr_yzs", "bZIDPJr_yzs"),
            ("https://www.youtube.com/watch?v=bZIDPJr_yzs", "bZIDPJr_yzs"),
            ("https://youtube.com/shorts/bZIDPJr_yzs", "bZIDPJr_yzs"),
        ):
            self.assertEqual(Y._id_do_video(url), esperado)

    def test_sem_id_devolve_vazio_e_nao_levanta(self):
        for url in ("", None, "publicado no YouTube", "https://youtu.be/"):
            self.assertEqual(Y._id_do_video(url), "")


class ProvaOk(unittest.TestCase):

    def test_linha_antiga_sem_laudo_e_nao_sei_e_nao_falso(self):
        # O TERCEIRO ESTADO. As 219 linhas ja no disco nao tem laudo; se
        # ausencia valesse `False`, o alarme acenderia para o acervo inteiro
        # no primeiro dia e ninguem olharia o alarme de novo.
        self.assertIsNone(metricas.prova_ok(None))
        self.assertIsNone(metricas.prova_ok({}))

    def test_sem_confirmacao_e_falso(self):
        self.assertIs(
            metricas.prova_ok({"estado": "sem_confirmacao",
                               "youtube_id": ""}), False)

    def test_publicado_com_id_e_verdadeiro(self):
        self.assertIs(
            metricas.prova_ok({"estado": "publicado",
                               "youtube_id": "bZIDPJr_yzs"}), True)

    def test_publicado_sem_nenhum_vestigio_nao_conta_como_provado(self):
        # "A funcao nao levantou excecao" e exatamente o que os 29 rascunhos
        # devolveram. Nao pode contar como prova.
        self.assertIs(
            metricas.prova_ok({"estado": "publicado", "youtube_id": "",
                               "url": ""}), False)


class LaudoChegaNoLedger(unittest.TestCase):
    """De nada adianta medir se a medida nao chega ao registro.

    Estes casos existem porque a ligacao entre o navegador e a linha do
    ledger passa por tres funcoes; quebrar um elo deixaria a Etapa 1 verde e
    o ledger exatamente tao cego quanto antes.
    """

    def _publicar_dublado(self, estado: str, laudo_do_navegador: dict):
        """Roda `publicar_como_configurado` com o navegador dublado."""
        registrado = {}

        def falso_publicar(video, **kw):
            kw["prova"].update(laudo_do_navegador)
            return estado

        def falso_registrar(video, url, plataforma, *, canal, extra=None):
            registrado.update(extra or {})
            return extra

        original_web, original_reg = Y.publicar, metricas.registrar_publicado
        Y.publicar = falso_publicar
        metricas.registrar_publicado = falso_registrar
        self.addCleanup(lambda: setattr(Y, "publicar", original_web))
        self.addCleanup(
            lambda: setattr(metricas, "registrar_publicado", original_reg))

        youtube.publicar_como_configurado(
            "video.mp4", config={"youtube": {"modo": "navegador"}},
            canal="builds")
        return registrado

    def test_a_linha_do_ledger_carrega_o_laudo_e_o_veredito(self):
        registrado = self._publicar_dublado(
            "https://youtu.be/bZIDPJr_yzs",
            {"estado": "publicado", "youtube_id": "bZIDPJr_yzs",
             "qualidade_no_clique": "sd"})
        self.assertIs(registrado["prova_ok"], True)
        self.assertEqual(len(registrado["prova"]), 1)
        self.assertEqual(registrado["prova"][0]["qualidade_no_clique"], "sd")

    def test_publicacao_sem_prova_entra_como_nao_provada(self):
        # O CASO DOS RASCUNHOS: o Studio nao confirmou, mas a funcao devolveu
        # texto. Antes disso virava uma linha indistinguivel de sucesso.
        registrado = self._publicar_dublado(
            "publicado no YouTube",
            {"estado": "sem_confirmacao", "youtube_id": "", "url": ""})
        self.assertIs(registrado["prova_ok"], False)

    def test_o_campo_prova_e_sempre_lista(self):
        # Uma parte longa de historia vira DOIS Shorts. Dois formatos de
        # campo no mesmo ledger seria a proxima pergunta sem resposta unica.
        registrado = self._publicar_dublado(
            "https://youtu.be/bZIDPJr_yzs",
            {"estado": "publicado", "youtube_id": "bZIDPJr_yzs"})
        self.assertIsInstance(registrado["prova"], list)


class ProvaDeVariosPedacos(unittest.TestCase):

    def test_dois_pedacos_provados_valem_publicacao(self):
        laudos = [{"estado": "publicado", "youtube_id": "aaaaaaaaaaa"},
                  {"estado": "publicado", "youtube_id": "bbbbbbbbbbb"}]
        self.assertIs(metricas.prova_ok(laudos), True)

    def test_meia_publicacao_nao_e_publicacao(self):
        # A parte 2/2 nao subiu: quem assistir a primeira metade fica sem o
        # resto. Contar isso como publicado seria a mesma mentira de antes,
        # com outro rosto.
        laudos = [{"estado": "publicado", "youtube_id": "aaaaaaaaaaa"},
                  {"estado": "sem_confirmacao", "youtube_id": ""}]
        self.assertIs(metricas.prova_ok(laudos), False)

    def test_lista_vazia_e_nao_sei(self):
        self.assertIsNone(metricas.prova_ok([]))


class ContratoAntigo(unittest.TestCase):

    def test_publicar_continua_aceitando_ser_chamada_sem_prova(self):
        # A regressao que protege a operacao: `prova` e OPCIONAL e o retorno
        # nao mudou. `postar.py` chama esta funcao em todo horario da grade.
        import inspect

        assinatura = inspect.signature(Y.publicar)
        self.assertIn("prova", assinatura.parameters)
        self.assertIs(assinatura.parameters["prova"].default, None)
        self.assertEqual(assinatura.parameters["prova"].kind,
                         inspect.Parameter.KEYWORD_ONLY)

    def test_confirmado_nao_mudou_de_porta(self):
        self.assertTrue(Y.confirmado("https://youtu.be/bZIDPJr_yzs"))
        self.assertTrue(Y.confirmado(Y.SUCESSO + " (com a confirmacao extra)"))
        self.assertFalse(Y.confirmado("cliquei em publicar, mas o Studio"))


if __name__ == "__main__":
    unittest.main()
