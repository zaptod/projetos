# -*- coding: utf-8 -*-
"""Os tres buracos entre DETECTAR e CONSERTAR (11/09/2026).

A pipeline ficou boa em detectar: colagem, texto de outra historia, render
defasado, cena sem imagem, veto da IA. Nada disso consertava nada, e as tres
falhas abaixo so aparecem juntas — o sintoma final e um canal mudo, sem um
alerta sequer.

1. O FREIO CONTAVA ARQUIVO, NAO VIDEO PUBLICAVEL. A criacao para quando ha
   "um dia de estoque no disco", e essa conta nao passava pela vistoria. Cinco
   videos barrados enchiam o estoque, o freio fechava, e a grade chegava no
   horario sem nada aprovado. A pipeline conseguia se matar de fome achando
   que estava abastecida.
2. VIDEO BARRADO FICAVA BARRADO PARA SEMPRE. A imagem em colagem existe no
   disco, entao o worker nao a refazia; o comando que apaga era manual.
3. O PARECER DESISTIA NA PRIMEIRA CONTA OCUPADA. A geracao segura o Gemini
   pela historia INTEIRA, horas — esperar nao resolve, trocar de provedor
   resolve.

    cd e:\\projetos\\historias
    python -m pytest tests/test_autossuficiencia_regressions.py -q
"""
from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from contos.pipeline import agenda, reparo


class FreioContaAprovadosTests(unittest.TestCase):

    def test_o_freio_passa_pela_vistoria(self):
        """Sem isto a conta e de arquivo no disco, e barrado vira estoque."""
        import inspect
        fonte = inspect.getsource(agenda.aprovados_no_estoque)
        # A vistoria agora vem de `qualidade.liberado`, que soma a mecanica e
        # o veto lembrado da IA numa resposta so.
        self.assertIn("qualidade.liberado", fonte)
        self.assertIn('veredito.get("ok")', fonte)

    def test_o_numero_do_freio_sai_dos_aprovados(self):
        import inspect
        self.assertIn("aprovados_no_estoque()",
                      inspect.getsource(agenda.dias_de_estoque_novo))

    def test_vistoria_que_explode_conta_como_estoque(self):
        """Errar para o lado de NAO criar: um ffprobe travado nao pode virar
        geracao sem parar."""
        import inspect
        fonte = inspect.getsource(agenda.aprovados_no_estoque)
        # `rindex`: ha dois `except Exception` na funcao, e o primeiro e o do
        # ledger de publicados. O que interessa e o da VISTORIA, o ultimo.
        trecho = fonte[fonte.rindex("except Exception"):]
        self.assertIn("aprovados.append(video)", trecho[:400])

    def test_barrados_usa_a_mesma_vistoria_da_grade(self):
        """Se o reparo olhasse por conta propria, ele consertaria o que a
        grade nao reclama e deixaria passar o que ela barra."""
        import inspect
        self.assertIn("qualidade.liberado",
                      inspect.getsource(agenda.barrados_no_estoque))


class ReparoTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._antes = reparo.REGISTRO
        reparo.REGISTRO = Path(self._tmp.name) / "_reparos.json"
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        reparo.REGISTRO = self._antes
        self._tmp.cleanup()

    def test_acha_a_cena_da_colagem_pela_mensagem(self):
        erros = ["cena 11: parece colagem: 2 calha(s) atravessando a imagem",
                 "cena 3: parece colagem: 1 calha(s)"]
        self.assertEqual([3, 11], reparo.cenas_com_colagem(erros))

    def test_erro_que_nao_e_colagem_nao_vira_cena(self):
        self.assertEqual([], reparo.cenas_com_colagem(
            ["cena 4: sem imagem", "imagem mais nova que o video"]))

    def test_o_teto_de_tentativas_existe_e_e_pequeno(self):
        """A conta do PicassoIA e compartilhada: uma cena que o modelo
        insiste em desenhar em painel consumiria geracao para sempre.

        Desde 15/09/2026 ("diminua para apenas uma passada no gemini e
        pronto") o VETO tem uma passada so (`UMA_PASSADA`), e as tentativas de
        maquina seguem com teto proprio."""
        self.assertLessEqual(reparo.TETO_DE_TENTATIVAS, 4)
        self.assertGreaterEqual(reparo.TETO_DE_TENTATIVAS, 2)
        self.assertTrue(reparo.UMA_PASSADA)
        self.assertFalse(reparo.CONFIRMAR_COM_A_IA)

    def test_depois_do_teto_para_de_tentar(self):
        alvo = "historia_00005:celular:p05"
        for _ in range(reparo.TETO_DE_TENTATIVAS):
            reparo._anotar(alvo, "colagem", "refiz")
        self.assertTrue(reparo.insistente(alvo))

    def test_video_que_passou_zera_a_conta(self):
        """Sem isto, um video consertado na terceira tentativa entraria na
        quarta ja marcado como insistente."""
        alvo = "historia_00005:celular:p05"
        reparo._anotar(alvo, "colagem", "refiz")
        self.assertEqual(1, reparo.tentativas(alvo))
        reparo.esquecer(alvo)
        self.assertEqual(0, reparo.tentativas(alvo))

    def test_insistente_nao_e_tentado_de_novo(self):
        class _V:
            id = "historia_00005:celular:p05"
            fonte_id = "historia_00005"
            parte = 5
        for _ in range(reparo.TETO_DE_TENTATIVAS):
            reparo._anotar(_V.id, "colagem", "refiz")
        saida = reparo.reparar(_V(), ["cena 11: parece colagem: x"])
        self.assertEqual("nada", saida["acao"])
        self.assertIn("parei", saida["detalhe"])

    def test_texto_de_outra_historia_nao_e_conserto_de_imagem(self):
        """Isso e reescrita de parte, e quem faz e a retomada."""
        class _V:
            id = "historia_00005:celular:p03"
            fonte_id = "historia_00005"
            parte = 3
        saida = reparo.reparar(
            _V(), ["roteiro: so 0% dos prompts de imagem estao em ingles"])
        self.assertEqual("nada", saida["acao"])
        self.assertIn("nao e conserto de imagem", saida["detalhe"])

    def test_conta_ocupada_NAO_gasta_tentativa(self):
        """Nao foi o video que falhou, foi a maquina que estava ocupada.
        Gastar tentativa ali queimaria o teto sem tentar nada — e a imagem
        guardada tem de voltar para o lugar."""
        from contos.imagens.worker import NaoRodou

        cena = Path(self._tmp.name) / "p05_cena_11.png"
        cena.write_bytes(b"a velha, em colagem")

        class _V:
            id = "historia_00005:celular:p05"
            fonte_id = "historia_00005"
            parte = 5

        class _Pipeline:
            def imagens(self, *_a, **_k):
                raise NaoRodou("a conta do PicassoIA esta em uso")

        from contos.imagens import fila
        antes = fila.caminho_da_cena
        fila.caminho_da_cena = lambda *_a, **_k: cena
        try:
            saida = reparo.reparar(_V(), ["cena 11: parece colagem: x"],
                                   pipeline=_Pipeline(), log=lambda _t: None)
        finally:
            fila.caminho_da_cena = antes
        self.assertEqual("adiado", saida["acao"])
        self.assertEqual(0, reparo.tentativas(_V.id))
        self.assertIn(b"velha", cena.read_bytes(),
                      "a imagem guardada nao voltou para o lugar")

    def test_conserto_bem_sucedido_re_renderiza(self):
        """Refazer a imagem sem re-renderizar deixa o mp4 com a colagem
        antiga — e a vistoria barraria de novo, agora por render defasado."""
        chamadas = []
        cena = Path(self._tmp.name) / "p05_cena_11.png"
        cena.write_bytes(b"a velha, em colagem")

        class _V:
            id = "historia_00005:celular:p05"
            fonte_id = "historia_00005"
            parte = 5

        class _Pipeline:
            def imagens(self, *_a, **_k):
                chamadas.append("imagens")
                cena.write_bytes(b"uma cena limpa")

            def render(self, *_a, **_k):
                chamadas.append("render")

        from contos.imagens import composicao, fila
        antes = (fila.caminho_da_cena, composicao.e_colagem)
        fila.caminho_da_cena = lambda *_a, **_k: cena
        composicao.e_colagem = lambda c: b"colagem" in Path(c).read_bytes()
        try:
            saida = reparo.reparar(_V(), ["cena 11: parece colagem: x"],
                                   pipeline=_Pipeline(), log=lambda _t: None)
        finally:
            fila.caminho_da_cena, composicao.e_colagem = antes
        self.assertTrue(saida["ok"], saida)
        self.assertEqual(["imagens", "render"], chamadas)

    def test_render_defasado_so_re_renderiza(self):
        chamadas = []

        class _V:
            id = "historia_00004:celular:p02"
            fonte_id = "historia_00004"
            parte = 2

        class _Pipeline:
            def imagens(self, *_a, **_k):
                chamadas.append("imagens")

            def render(self, *_a, **_k):
                chamadas.append("render")

        saida = reparo.reparar(
            _V(), ["imagem mais nova que o video: re-renderize antes de publicar"],
            pipeline=_Pipeline(), log=lambda _t: None)
        self.assertTrue(saida["ok"])
        self.assertEqual(["render"], chamadas,
                         "gerar imagem aqui gastaria a conta a toa")

    def test_o_reparo_roda_ANTES_de_criar(self):
        """Recuperar um video ja pago (roteiro, imagens, render) e mais
        barato do que fabricar outro do zero — e, com o freio contando
        aprovados, deixar barrado faz a maquina produzir sem parar."""
        import inspect
        fonte = inspect.getsource(agenda._trabalhar)
        self.assertLess(fonte.index("reparo.rodada"),
                        fonte.index("teto_de_estoque(config)"))


class ReparoNaoPioraTests(unittest.TestCase):
    """Aprendido em campo, 11/09/2026 as 20:33, na PRIMEIRA rodada
    automatica: o reparo apagou a imagem em colagem, a geracao estourou a
    espera, a cena ficou sem imagem nenhuma e o render seguiu em frente com
    um cartao de texto no lugar. O conserto piorou o defeito — colagem e
    ruim, cartao de texto no meio da historia e pior."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)
        self._antes = reparo.REGISTRO
        reparo.REGISTRO = self.pasta / "_reparos.json"
        self.addCleanup(self._restaurar)
        self.cena = self.pasta / "p05_cena_11.png"
        self.cena.write_bytes(b"a imagem velha, em colagem")

    def _restaurar(self):
        reparo.REGISTRO = self._antes
        self._tmp.cleanup()

    def _com_cena(self, gerar):
        """Aponta a fila para a cena de teste e dubla a geracao."""
        from contos.imagens import composicao, fila
        antes = (fila.caminho_da_cena, composicao.e_colagem)
        fila.caminho_da_cena = lambda *_a, **_k: self.cena
        composicao.e_colagem = lambda caminho: (
            b"colagem" in Path(caminho).read_bytes())
        self.addCleanup(lambda: (
            setattr(fila, "caminho_da_cena", antes[0]),
            setattr(composicao, "e_colagem", antes[1])))

        class _Pipeline:
            renderizou = False

            def imagens(self, *_a, **_k):
                gerar(self)

            def render(self, *_a, **_k):
                self.renderizou = True

        return _Pipeline()

    def test_geracao_que_falha_devolve_a_imagem_antiga(self):
        pipeline = self._com_cena(lambda _p: None)   # nao gera nada
        trocadas, restauradas = reparo._refazer_cenas(
            pipeline, "historia_00005", 5, [11], log=lambda _t: None)
        self.assertEqual([], trocadas)
        self.assertEqual([11], restauradas)
        self.assertTrue(self.cena.is_file(), "a cena sumiu do disco")
        self.assertIn(b"velha", self.cena.read_bytes())

    def test_nao_re_renderiza_quando_a_imagem_nao_veio(self):
        """Este e o passo que produziu o cartao de texto."""
        class _V:
            id = "historia_00005:celular:p05"
            fonte_id = "historia_00005"
            parte = 5
        pipeline = self._com_cena(lambda _p: None)
        saida = reparo.reparar(_V(), ["cena 11: parece colagem: x"],
                               pipeline=pipeline, log=lambda _t: None)
        self.assertEqual("adiado", saida["acao"])
        self.assertFalse(pipeline.renderizou)

    def test_imagem_nova_que_e_colagem_DE_NOVO_tambem_desfaz(self):
        """Trocar uma colagem por outra nao e conserto."""
        def gerar(_p):
            self.cena.write_bytes(b"a nova, tambem colagem")
        pipeline = self._com_cena(gerar)
        trocadas, restauradas = reparo._refazer_cenas(
            pipeline, "historia_00005", 5, [11], log=lambda _t: None)
        self.assertEqual([11], restauradas)
        self.assertIn(b"velha", self.cena.read_bytes())

    def test_imagem_boa_substitui_e_a_reserva_some(self):
        def gerar(_p):
            self.cena.write_bytes(b"uma cena limpa")
        pipeline = self._com_cena(gerar)
        trocadas, restauradas = reparo._refazer_cenas(
            pipeline, "historia_00005", 5, [11], log=lambda _t: None)
        self.assertEqual([11], trocadas)
        self.assertEqual([], restauradas)
        self.assertIn(b"limpa", self.cena.read_bytes())
        self.assertFalse(list(self.pasta.glob("*.colagem")),
                         "a reserva ficou para tras")

    def test_a_prova_e_o_arquivo_e_nao_o_retorno(self):
        """`pipeline.imagens` NAO levanta quando o site falha: ele devolve o
        resultado com os erros dentro. Confiar no retorno foi o erro."""
        import inspect
        fonte = inspect.getsource(reparo._refazer_cenas)
        self.assertIn("arquivo.is_file()", fonte)


class ConfirmarComQuemViuTests(unittest.TestCase):
    """O reparo fecha no MESMO crivo do publicador, e nao no dele proprio.

    O detector de colagem olha pixel: sabe dizer que nao ha mais faixa
    dividindo a imagem, nao sabe dizer que a cena nova continua sem ter nada
    a ver com a narracao. Confirmar conserto por pixel e conferir a parte
    facil e chamar de pronto.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._antes = reparo.REGISTRO
        reparo.REGISTRO = Path(self._tmp.name) / "_reparos.json"
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        reparo.REGISTRO = self._antes
        self._tmp.cleanup()

    def test_o_reparo_pergunta_a_quem_assistiu(self):
        import inspect
        fonte = inspect.getsource(reparo._confirmar_com_a_ia)
        self.assertIn("parecer.pedir", fonte)

    def test_a_vistoria_mecanica_vem_antes_de_gastar_navegador(self):
        import inspect
        fonte = inspect.getsource(reparo._confirmar_com_a_ia)
        self.assertLess(fonte.index("vistoriar_parte"),
                        fonte.index("parecer.pedir"))

    def test_sem_parecer_NAO_e_reprovacao(self):
        """`None` deixa o publicador perguntar de novo no horario; virar
        reprovacao aqui condenaria o video por causa de conta ocupada."""
        import inspect
        fonte = inspect.getsource(reparo._confirmar_com_a_ia)
        self.assertIn("return None", fonte)

    def test_reprovado_pela_IA_nao_conta_como_consertado(self):
        class _V:
            id = "historia_00004:celular:p02"
            fonte_id = "historia_00004"
            parte = 2
            caminho = "x.mp4"

        class _Pipeline:
            def render(self, *_a, **_k):
                pass

        antes = reparo._confirmar_com_a_ia
        reparo._confirmar_com_a_ia = lambda *_a, **_k: {
            "aprovado": False, "motivos": ["quadro 3: contradiz a narracao"]}
        try:
            saida = reparo.reparar(
                _V(), ["imagem mais nova que o video: re-renderize"],
                pipeline=_Pipeline(), log=lambda _t: None)
        finally:
            reparo._confirmar_com_a_ia = antes
        self.assertFalse(saida["ok"])
        self.assertIn("ainda reprova", saida["detalhe"])
        self.assertEqual(1, reparo.tentativas(_V.id),
                         "reprovado pela IA tem de gastar tentativa")


def _corpo(funcao) -> str:
    """O fonte da funcao SEM o docstring.

    Varrer o fonte inteiro faz o teste tropecar na propria explicacao: o
    docstring de `liberado` diz "e nunca `parecer.pedir`", e a busca por
    `parecer.pedir` acha essa frase. Ja aconteceu tres vezes neste
    repositorio com scanners de fonte.
    """
    import inspect
    fonte = inspect.getsource(funcao)
    doc = inspect.getdoc(funcao)
    if not doc:
        return fonte
    corte = fonte.find('"""')
    fim = fonte.find('"""', corte + 3)
    return fonte[:corte] + fonte[fim + 3:] if corte >= 0 and fim > corte else fonte


class UmaFonteUmaRespostaTests(unittest.TestCase):
    """Tres donos da pergunta "pode sair?", e eram duas respostas.

    Medido em 11/09/2026: a auditoria mostrava "0 barrados" enquanto o freio
    de estoque contava um video reprovado pela IA. A auditoria chamava so
    `vistoriar_parte`; o freio somava `parecer.lembrado`. Nao havia como
    saber qual das duas telas estava certa.
    """

    def test_existe_uma_funcao_so_que_decide(self):
        from contos.publicar import qualidade
        self.assertTrue(callable(qualidade.liberado))

    def test_o_freio_pergunta_a_ela(self):
        import inspect
        from contos.pipeline import agenda
        for funcao in (agenda.aprovados_no_estoque, agenda.barrados_no_estoque):
            self.assertIn("qualidade.liberado", inspect.getsource(funcao),
                          funcao.__name__)

    def test_a_auditoria_pergunta_a_ela(self):
        import inspect
        from panorama import auditoria
        self.assertIn("vistoria.liberado",
                      inspect.getsource(auditoria.qualidade))

    def test_ela_soma_o_veto_da_IA_a_vistoria(self):
        import inspect
        from contos.publicar import qualidade
        fonte = inspect.getsource(qualidade.liberado)
        self.assertIn("vistoriar_parte", fonte)
        self.assertIn("parecer.lembrado", fonte)

    def test_ela_NUNCA_abre_navegador(self):
        """O `panorama` tem regra escrita de so ler. `pedir` abre o Gemini e
        custa 100 s; quem PERGUNTA e o publicador, uma vez, no horario."""
        from contos.publicar import qualidade
        self.assertNotIn("parecer.pedir", _corpo(qualidade.liberado))

    def test_o_veto_da_IA_so_e_consultado_se_a_vistoria_passou(self):
        """Decodificar mp4 e barato perto de nada; ler o lembrete e de graca.
        A ordem existe para o motivo mecanico aparecer primeiro no relatorio,
        que e o que da para consertar sozinho."""
        import inspect
        from contos.publicar import qualidade
        fonte = inspect.getsource(qualidade.liberado)
        self.assertLess(fonte.index("vistoriar_parte"),
                        fonte.index("parecer.lembrado"))
        self.assertIn("if not erros:", fonte)


class VeredictoLembradoTests(unittest.TestCase):
    """O que a IA disse fica gravado, com a data do mp4 junto.

    Sem isso, o freio de estoque e o reparo teriam de perguntar de novo (100 s
    e um navegador por video) ou ignorar a IA. Em 11/09/2026 eles ignoraram: o
    freio contou 9 aprovados com um deles reprovado pela IA, e o contador de
    tentativas zerava a cada rodada — reparo eterno, sem nunca desistir.

    A data do arquivo e a chave: re-renderizou, a memoria morre sozinha.
    """

    def setUp(self):
        from contos.publicar import parecer
        self.parecer = parecer
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)
        self._antes = parecer.LEMBRETES
        parecer.LEMBRETES = self.pasta / "_pareceres.json"
        self.addCleanup(self._restaurar)
        self.mp4 = self.pasta / "final_celular_p05.mp4"
        self.mp4.write_bytes(b"um video")

        class _V:
            id = "historia_00005:celular:p05"
        self.video = _V()
        self.video.caminho = self.mp4

    def _restaurar(self):
        self.parecer.LEMBRETES = self._antes
        self._tmp.cleanup()

    def test_o_veredito_volta_para_quem_perguntar(self):
        self.parecer.lembrar(self.video, {"aprovado": False,
                                          "motivos": ["quadro 2: dividida"]})
        ficha = self.parecer.lembrado(self.video)
        self.assertFalse(ficha["aprovado"])
        self.assertIn("quadro 2", ficha["motivos"][0])

    def test_video_re_renderizado_apaga_a_memoria(self):
        """O parecer era sobre AQUELE arquivo. Outro arquivo, outra pergunta."""
        import os
        import time
        self.parecer.lembrar(self.video, {"aprovado": False, "motivos": ["x"]})
        agora = time.time() + 600
        os.utime(self.mp4, (agora, agora))
        self.assertIsNone(self.parecer.lembrado(self.video))

    def test_video_que_nunca_foi_visto_nao_inventa_veredito(self):
        self.assertIsNone(self.parecer.lembrado(self.video))

    def test_chave_que_nao_e_id_de_video_e_recusada(self):
        """A porta. Em 11/09/2026 tres chaves `<object object at 0x...>`
        entraram no arquivo de PRODUCAO, escritas por um teste que dublava
        `_pedir_em` mas nao isolava `LEMBRETES` — mesma familia das 322 de 358
        linhas de lixo que o ledger de publicados levou em setembro."""
        for ruim in ("<object object at 0x0000019E2B013A10>", "", "sem dois pontos",
                     "com espaco: aqui"):
            with self.assertRaises(ValueError, msg=ruim):
                self.parecer._lembrar(ruim, {"aprovado": True})

    def test_id_de_verdade_passa(self):
        for bom in ("historia_00008:celular:p01", "historia_00009:celular",
                    "generation_00055:estreia:celular"):
            self.assertTrue(self.parecer._e_id_de_video(bom), bom)

    def test_lembrar_engole_a_recusa_em_vez_de_derrubar_o_parecer(self):
        """A memoria e conveniencia; o veredito e o produto. Uma chave ruim
        nao pode perder um parecer que custou 100 s de navegador."""
        self.parecer.lembrar(object(), {"aprovado": True})   # nao levanta
        self.assertEqual({}, self.parecer._lembretes())

    def test_o_freio_desconta_o_que_a_IA_reprovou(self):
        from contos.publicar import qualidade
        self.assertIn("parecer.lembrado", _corpo(qualidade.liberado))

    def test_o_reparo_ve_o_veto_da_IA_como_barrado(self):
        """Vistoria mecanica passando nao basta: se quem assistiu reprovou,
        continua sendo um video que nao pode sair."""
        from contos.publicar import qualidade
        corpo = _corpo(qualidade.liberado)
        self.assertIn("parecer.lembrado", corpo)
        self.assertIn("a IA reprovou", corpo)

    def test_esquecer_so_vale_para_quem_saiu_da_lista(self):
        import inspect
        from contos.pipeline import reparo as modulo
        fonte = inspect.getsource(modulo.rodada)
        self.assertIn("ainda_barrados", fonte)


class TrocaDeProvedorTests(unittest.TestCase):

    def setUp(self):
        """ISOLA O ARQUIVO DE VEREDITOS. Sem isto, `parecer.pedir` grava no
        `outputs/_pareceres.json` DE PRODUCAO — e gravou: tres chaves
        `<object object at 0x...>` foram parar la, escritas por
        `test_conta_ocupada_no_primeiro_tenta_o_segundo`. E a mesma falha que
        encheu o ledger de publicados com 322 linhas de teste em setembro."""
        from contos.publicar import parecer
        self._tmp_lembretes = tempfile.TemporaryDirectory()
        self._lembretes_antes = parecer.LEMBRETES
        parecer.LEMBRETES = Path(self._tmp_lembretes.name) / "_pareceres.json"
        self.addCleanup(self._devolver_lembretes)

    def _devolver_lembretes(self):
        from contos.publicar import parecer
        parecer.LEMBRETES = self._lembretes_antes
        self._tmp_lembretes.cleanup()

    def test_conta_ocupada_e_um_erro_PROPRIO(self):
        """Sem tipo proprio, "conta em uso" e "o site quebrou" chegam iguais
        em quem chama, e a unica reacao possivel e desistir."""
        from contos.llm.cliente import ContaOcupada, LLMFalhou
        self.assertTrue(issubclass(ContaOcupada, LLMFalhou))

    def test_ha_um_segundo_provedor(self):
        from contos.publicar import parecer
        self.assertGreaterEqual(len(parecer.PROVEDORES), 2)
        self.assertEqual("gemini", parecer.PROVEDORES[0])

    def test_so_o_gemini_recebe_o_mp4(self):
        """O ChatGPT desta maquina e free: 33 MB de upload para ele tratar o
        arquivo como opaco e a folha entrar mesmo assim."""
        from contos.publicar import parecer
        self.assertEqual(("gemini",), parecer.ASSISTEM_VIDEO)

    def test_a_espera_pela_conta_e_curta(self):
        """A geracao segura a conta por horas: esperar nao resolve, trocar
        de provedor resolve."""
        from contos.publicar import parecer
        self.assertLessEqual(parecer.ESPERA_DA_CONTA_S, 120)

    def test_conta_ocupada_no_primeiro_tenta_o_segundo(self):
        from contos.publicar import parecer
        from contos.llm.cliente import ContaOcupada
        tentados = []

        def falso(provedor, *_a, **_k):
            tentados.append(provedor)
            if provedor == "gemini":
                raise ContaOcupada("em uso")
            return {"aprovado": True, "motivos": [], "texto": "APROVADO"}

        antes = parecer._pedir_em
        parecer._pedir_em = falso
        try:
            saida = parecer.pedir(object(), {}, 1, log=lambda _t: None)
        finally:
            parecer._pedir_em = antes
        self.assertEqual(["gemini", "chatgpt"], tentados)
        self.assertTrue(saida["aprovado"])

    def test_os_dois_falhando_vira_SemParecer(self):
        from contos.publicar import parecer
        antes = parecer._pedir_em
        parecer._pedir_em = lambda *_a, **_k: (_ for _ in ()).throw(
            parecer.SemParecer("nada"))
        try:
            with self.assertRaises(parecer.SemParecer):
                parecer.pedir(object(), {}, 1, log=lambda _t: None)
        finally:
            parecer._pedir_em = antes


class NoiteDeDozeDeSetembroTests(unittest.TestCase):
    """Os tres defeitos que deixaram o canal publicar 1 de 8 em 12/09/2026.

    A noite em que a mensagem "nao foi possivel postar uma historia" chegou no
    Telegram. A falta de estoque era so o sintoma; embaixo dela havia tres
    coisas quebradas, e cada uma sozinha ja bastava para um video reprovado ir
    ao ar ou para o reparador nunca consertar nada.
    """

    def setUp(self):
        from contos.publicar import parecer
        self.parecer = parecer
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        self._antes = parecer.LEMBRETES
        parecer.LEMBRETES = self.pasta / "_pareceres.json"
        self.addCleanup(lambda: setattr(parecer, "LEMBRETES", self._antes))
        self.mp4 = self.pasta / "final_celular_p01.mp4"
        self.mp4.write_bytes(b"um video")

        class _V:
            id = "historia_00004:celular:p01"
        self.video = _V()
        self.video.caminho = self.mp4

    # ---- 1. a folha de contato nao derruba quem assistiu ao video
    def test_a_folha_nao_sobrescreve_o_veredito_de_quem_assistiu(self):
        """O ChatGPT viu 12 miniaturas; o Gemini viu 2:23 de video.

        Em 12/09/2026 o Gemini reprovou a parte 1 da historia 4 as 06:14 depois
        de assistir ao arquivo inteiro, e as 20:25 o ChatGPT devolveu
        "APROVADO" em oito caracteres olhando so a folha de contato. O arquivo
        de vereditos trocou a reprovacao pela aprovacao e o video voltou a
        ficar liberado para a grade.
        """
        self.parecer.lembrar(self.video, {
            "aprovado": False, "motivos": ["quadro 6: tela dividida"],
            "vista": "video inteiro (2:23)"})
        self.parecer.lembrar(self.video, {
            "aprovado": True, "motivos": [], "vista": "folha de contato"})

        ficha = self.parecer.lembrado(self.video)
        self.assertFalse(ficha["aprovado"], "a folha derrubou quem assistiu")
        self.assertEqual("video inteiro (2:23)", ficha["vista"])

    def test_mas_a_folha_entra_quando_nao_ha_nada(self):
        """Ela e reserva, nao veto: sem veredito anterior, vale o que ela diz."""
        self.parecer.lembrar(self.video, {
            "aprovado": False, "motivos": ["quadro 3: colagem"],
            "vista": "folha de contato"})
        self.assertFalse(self.parecer.lembrado(self.video)["aprovado"])

    def test_e_quem_assistiu_de_novo_manda(self):
        """Re-assistir SUBSTITUI. So a folha e que nao derruba o video."""
        self.parecer.lembrar(self.video, {
            "aprovado": False, "motivos": ["x"], "vista": "video inteiro (2:23)"})
        self.parecer.lembrar(self.video, {
            "aprovado": True, "motivos": [], "vista": "video inteiro (2:23)"})
        self.assertTrue(self.parecer.lembrado(self.video)["aprovado"])

    # ---- 2. o publicador le o veto que ja esta em disco
    def test_o_publicador_consulta_o_veredito_antes_de_perguntar(self):
        """Era o terceiro dono da pergunta "pode sair?", e o unico sem consulta.

        `qualidade.liberado` unificou a auditoria e o freio; o publicador
        continuou perguntando de novo toda vez. Resultado medido: a parte 3 da
        historia 4, reprovada as 06:14 com o video inteiro assistido, foi ao
        YouTube e ao TikTok as 15:34 do mesmo dia.
        """
        fonte = (Path(__file__).resolve().parents[2] / "ferramentas"
                 / "postar.py").read_text(encoding="utf-8")
        inicio = fonte.index("def _parecer_da_ia")
        corpo = fonte[inicio:fonte.index("def ", inicio + 10)]
        self.assertIn("parecer.lembrado", corpo)
        # e o veto tem de sair ANTES do pedido, senao nao evita nada
        self.assertLess(corpo.index("parecer.lembrado"),
                        corpo.index("parecer.pedir"))

    # ---- 3. o reparador entende o vocabulario da IA
    def test_quem_chama__trabalhar_num_teste_dubla_o_reparador(self):
        """`_trabalhar` chama `reparo.rodada()`, e a rodada abre o PicassoIA.

        O teste do teto de estoque dublava `Pipeline.gerar` mas nao o
        reparador, e passava mesmo assim porque `cenas_com_colagem` estava
        cega ao vocabulario da IA. Consertada a cegueira, ele achou 14 cenas
        de verdade e a suite deixou de terminar.

        Esta guarda varre o ARQUIVO DE TESTE, nao o codigo: quem exercitar
        `_trabalhar` de verdade tem de neutralizar as duas saidas da maquina.
        """
        alvo = Path(__file__).with_name("test_agenda_automatica_regressions.py")
        fonte = alvo.read_text(encoding="utf-8")
        chamadas = fonte.count("agenda._trabalhar(")
        if not chamadas:
            self.skipTest("ninguem mais chama `_trabalhar` ali")
        self.assertIn("reparo.rodada = ", fonte,
                      "o teste chama `_trabalhar` sem dublar o reparador: "
                      "ele vai abrir o navegador e gerar imagem de verdade")


    def test_a_ficha_do_protagonista_exige_etnia_e_um_traco(self):
        """Repetir uma descricao VAGA nao fixa pessoa nenhuma.

        A frase era "a 30s man, short dark hair, tired eyes, wearing a simple
        gray button-down shirt". Ela ia em TODAS as imagens, e ainda assim o
        Gemini reprovou tres videos em 12/09/2026 porque o protagonista
        trocava de rosto entre as cenas: aquela descricao serve tanto a um
        homem asiatico quanto a um branco, e o modelo escolhia um diferente a
        cada imagem. O reparador nao alcanca isto — refazer a cena sozinha nao
        devolve continuidade — entao a guarda tem de estar na escrita.
        """
        from contos.roteiro import serie
        fonte = inspect.getsource(serie)
        alvo = fonte[fonte.index("CONSISTENCIA VISUAL"):]
        alvo = alvo[:alvo.index("add(\"\")")]
        self.assertIn("etnia", alvo)
        self.assertIn("traco marcante", alvo)
        # e o contra-exemplo, para nao voltar o adjetivo que nao descreve
        self.assertIn("tired eyes", alvo)


    def test_o_reparo_entende_quadro_e_nao_so_cena(self):
        """"cena" e a palavra do nosso codigo; "quadro" e a do Gemini.

        O reparador registrou "0 de 8 video(s) barrado(s) consertados" oito
        vezes seguidas porque `cenas_com_colagem` devolvia lista vazia para
        tudo o que a IA escreveu.
        """
        from contos.pipeline import reparo
        self.assertEqual([2], reparo.cenas_com_colagem(
            ["quadro 2: a imagem tem tela dividida."]))
        self.assertEqual([3], reparo.cenas_com_colagem(
            ["cena 3: colagem detectada"]))

    def test_o_reparo_entende_os_tres_nomes_do_mesmo_defeito(self):
        """Exigir a palavra literal "colagem" perdia dois tercos dos motivos."""
        from contos.pipeline import reparo
        self.assertEqual([4], reparo.cenas_com_colagem(
            ["quadro 4: a imagem e uma grade de paineis."]))
        self.assertEqual([7], reparo.cenas_com_colagem(
            ["quadro 7: a imagem tem tela dividida."]))

    def test_o_reparo_nao_contamina_a_frase_inteira(self):
        """Os motivos chegam numa string so, separados por `;`.

        Sem partir antes de olhar, um unico "colagem" na frase faria TODO
        numero dela virar colagem — e o reparador refaria cenas que estavam
        boas, gastando geracao de imagem a toa.
        """
        from contos.pipeline import reparo
        junto = ("a IA reprovou: quadro 2: a imagem tem tela dividida.; "
                 "quadro 5: o protagonista muda de rosto.; "
                 "quadro 9: a imagem e uma grade de paineis.")
        self.assertEqual([2, 9], reparo.cenas_com_colagem([junto]))

    def test_trocar_de_rosto_nao_e_conserto_de_imagem(self):
        """A IA reprova por continuidade tambem, e isso o reparo NAO resolve.

        Refazer a cena sozinha nao faz o protagonista voltar a ter o mesmo
        rosto das irmas. Marcar como colagem seria gastar geracao para nada.
        """
        from contos.pipeline import reparo
        self.assertEqual([], reparo.cenas_com_colagem(
            ["quadro 4: o protagonista muda de rosto a ponto de parecer outra "
             "pessoa."]))



if __name__ == "__main__":
    unittest.main()
