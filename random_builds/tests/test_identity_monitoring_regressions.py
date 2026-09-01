"""Contratos do monitoramento da geracao de identidade.

O que este arquivo trava:

1. O historico NUNCA derruba o worker. Monitoramento que quebra a producao e
   pior que monitoramento nenhum.
2. A espera do Digen e medida por pareamento (abertura -> `pronto`), nao por
   contagem — senao uma tentativa que estourou entraria na mediana como se
   tivesse dado certo.
3. `status` detecta as inconsistencias que NAO levantam erro em lugar nenhum:
   clipe baixado fora do edit_plan, e mp4 final mais velho que o clipe.
4. `doctor` roda inteiro sem browser e sem levantar, mesmo com a fila zoada.

Rode de dentro de random_builds/:
    python -m unittest discover -s tests -p "test_*.py"
"""
from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from builds.identity import browser                     # noqa: E402
from builds.identity import config as identity_config   # noqa: E402
from builds.identity import health                      # noqa: E402
from builds.identity import history                     # noqa: E402
from builds.identity import queue as identity_queue     # noqa: E402
from builds.identity import status                      # noqa: E402


class HistoricoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original = history.ARQUIVO
        history.ARQUIVO = Path(self._tmp.name) / "history.jsonl"

    def tearDown(self):
        history.ARQUIVO = self._original
        self._tmp.cleanup()

    def test_registrar_nunca_levanta(self):
        """Monitoramento que quebra a producao e pior que nenhum."""
        history.ARQUIVO = Path(self._tmp.name) / "nao" / "existe" / "x.jsonl"
        history.registrar("generation_00001", history.ENVIADO)   # cria a pasta
        history.ARQUIVO = Path(self._tmp.name)                   # e um diretorio
        history.registrar("generation_00001", history.FALHOU)    # nao pode explodir

    def test_linha_corrompida_nao_leva_o_arquivo_junto(self):
        history.registrar("generation_00001", history.ENVIADO)
        with open(history.ARQUIVO, "a", encoding="utf-8") as fh:
            fh.write("{isso nao e json\n")
        history.registrar("generation_00001", history.CONCLUIDO)
        eventos = history.ler()
        self.assertEqual([history.ENVIADO, history.CONCLUIDO],
                         [e["evento"] for e in eventos])

    def test_espera_e_pareada_com_a_abertura(self):
        history.registrar("g1", history.ENVIADO)
        time.sleep(1.05)                       # ts tem resolucao de segundo
        history.registrar("g1", history.PRONTO)
        esperas = history.esperas()
        self.assertEqual(1, len(esperas))
        self.assertGreaterEqual(esperas[0], 1.0)

    def test_tentativa_sem_pronto_fica_fora_da_mediana(self):
        """A mediana e "quanto demora quando da certo".

        Uma abertura que estourou nao tem `pronto`; conta-la como zero (ou como
        o tempo ate a falha) mascararia a lentidao real do Digen.
        """
        history.registrar("g1", history.ENVIADO)
        history.registrar("g1", history.ESTOUROU)
        self.assertEqual([], history.esperas())

    def test_resumo_calcula_taxa_de_sucesso(self):
        for gid, fecho in (("g1", history.CONCLUIDO), ("g2", history.FALHOU),
                           ("g3", history.CONCLUIDO), ("g4", history.CONCLUIDO)):
            history.registrar(gid, history.ENVIADO)
            history.registrar(gid, fecho)
        resumo = history.resumo()
        self.assertEqual(4, resumo["tentativas_fechadas"])
        self.assertEqual(3, resumo["concluidos"])
        self.assertEqual(0.75, resumo["taxa_sucesso"])

    def test_resumo_vazio_nao_divide_por_zero(self):
        resumo = history.resumo()
        self.assertEqual(0, resumo["eventos"])
        self.assertIsNone(resumo["taxa_sucesso"])
        self.assertIsNone(resumo["espera_mediana_s"])


class InconsistenciaTests(unittest.TestCase):
    """Os estados que nao levantam erro em lugar nenhum."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        self._outputs = identity_config.OUTPUTS
        self._fila = identity_queue.ARQUIVO_FILA
        identity_config.OUTPUTS = self.raiz
        status.config.OUTPUTS = self.raiz
        identity_queue.ARQUIVO_FILA = self.raiz / "_identity" / "queue.json"

    def tearDown(self):
        identity_config.OUTPUTS = self._outputs
        status.config.OUTPUTS = self._outputs
        identity_queue.ARQUIVO_FILA = self._fila
        self._tmp.cleanup()

    def _gerar(self, gid, *, clipe_bytes=None, no_plano=None,
               finais=True, final_velho=False):
        d = self.raiz / gid
        d.mkdir(parents=True, exist_ok=True)
        if no_plano is not None:
            eventos = [{"type": "final"}, {"type": "outro"}]
            if no_plano:
                eventos.insert(1, {"type": "identity"})
            (d / "edit_plan.json").write_text(
                json.dumps({"events": eventos}), encoding="utf-8")
        if finais:
            for perfil in ("celular", "normal"):
                (d / f"final_{perfil}.mp4").write_bytes(b"x")
        if clipe_bytes is not None:
            (d / "identity").mkdir(exist_ok=True)
            clipe = d / "identity" / "digen.mp4"
            clipe.write_bytes(b"x" * clipe_bytes)
            if final_velho:
                # final gravado ANTES do clipe = re-render nao rodou
                antigo = clipe.stat().st_mtime - 600
                for perfil in ("celular", "normal"):
                    import os
                    os.utime(d / f"final_{perfil}.mp4", (antigo, antigo))
        return d

    def test_clipe_fora_do_plano_e_apontado(self):
        self._gerar("generation_00001", clipe_bytes=50_000, no_plano=False)
        problemas = status.inconsistencias()
        self.assertTrue(any("fora do edit_plan" in p for p in problemas), problemas)

    def test_final_mais_velho_que_o_clipe_e_apontado(self):
        """O caso mais traicoeiro: o video existe, parece pronto, e esta errado."""
        self._gerar("generation_00001", clipe_bytes=50_000, no_plano=True,
                    final_velho=True)
        problemas = status.inconsistencias()
        self.assertTrue(any("mais velho que o clipe" in p for p in problemas),
                        problemas)

    def test_clipe_truncado_e_apontado(self):
        self._gerar("generation_00001", clipe_bytes=200, no_plano=True)
        problemas = status.inconsistencias()
        self.assertTrue(any("truncado" in p for p in problemas), problemas)

    def test_geracao_antiga_sem_clipe_nao_e_problema(self):
        """Tudo que veio antes desta feature nao tem clipe — e esta certo."""
        self._gerar("generation_00001", no_plano=False)
        self.assertEqual([], status.inconsistencias())

    def test_caminho_feliz_nao_reporta_nada(self):
        self._gerar("generation_00001", clipe_bytes=50_000, no_plano=True)
        self.assertEqual([], status.inconsistencias())

    def test_trabalho_ja_feito_e_reconhecido(self):
        """O disco manda mais que a fila.

        Um job pode ficar `pending` com tudo pronto (worker morto depois do
        download, fila reescrita por outro processo). Regerar ai desperdicaria
        uma geracao e sobrescreveria um clipe que estava certo — foi o que
        aconteceu com `generation_00014`, baixado duas vezes.
        """
        self._gerar("generation_00001", clipe_bytes=50_000, no_plano=True)
        self.assertTrue(status.clipe_utilizavel("generation_00001"))
        self.assertTrue(status.esta_completo("generation_00001"))

    def test_clipe_truncado_nao_conta_como_pronto(self):
        """Senao o guard aceitaria um download pela metade como trabalho feito."""
        self._gerar("generation_00001", clipe_bytes=200, no_plano=True)
        self.assertFalse(status.clipe_utilizavel("generation_00001"))
        self.assertFalse(status.esta_completo("generation_00001"))

    def test_clipe_sem_render_nao_conta_como_completo(self):
        """Ha clipe, mas o video final ainda nao tem: falta refazer o render."""
        self._gerar("generation_00001", clipe_bytes=50_000, no_plano=False)
        self.assertTrue(status.clipe_utilizavel("generation_00001"))
        self.assertFalse(status.esta_completo("generation_00001"))

    def test_geracao_inexistente_nao_e_completa(self):
        self.assertFalse(status.esta_completo("generation_99999"))
        self.assertFalse(status.clipe_utilizavel("generation_99999"))

    def test_job_pronto_e_fechado_sem_abrir_o_browser(self):
        """Marcar um job como feito nao precisa de Chrome.

        Abrir o browser so para descobrir que o trabalho ja estava no disco era
        o que fazia a janela piscar em `--watch`: abre, fecha, espera, repete.
        O pre-passe resolve isso antes de qualquer navegador subir.
        """
        from builds.identity import worker

        self._gerar("generation_00001", clipe_bytes=50_000, no_plano=True)
        identity_queue.enqueue("generation_00001", "prompt")

        resolvidos = worker._resolver_no_disco(rerender=False, preview=True)

        self.assertEqual(1, resolvidos)
        self.assertEqual(identity_queue.PRONTO,
                         identity_queue.listar()[0]["status"])

    def test_job_que_precisa_gerar_sobrevive_ao_pre_passe(self):
        """O pre-passe nao pode engolir trabalho de verdade.

        Ele nao reivindica nada: um job que ainda precisa ser gerado tem que
        sair de la intacto e `pending`, para a passada do provedor pega-lo.
        """
        from builds.identity import worker

        self._gerar("generation_00001", no_plano=False)   # sem artefato
        identity_queue.enqueue("generation_00001", "prompt")

        self.assertEqual(0, worker._resolver_no_disco(rerender=False,
                                                      preview=True))
        restante = identity_queue.listar()[0]
        self.assertEqual(identity_queue.PENDENTE, restante["status"])
        self.assertEqual(0, restante["attempts"],
                         "o pre-passe gastou uma tentativa sem gerar nada")

    def test_diferenca_de_milissegundos_nao_e_alarme(self):
        """Alarme falso e o que faz monitoramento ser ignorado.

        Na ordem real o clipe cai e o re-render escreve os finais logo depois,
        entao os mtimes ficam a segundos um do outro. Comparar sem tolerancia
        acusava granularidade de filesystem como "final desatualizado".
        """
        import os
        d = self._gerar("generation_00001", clipe_bytes=50_000, no_plano=True)
        clipe = d / "identity" / "digen.mp4"
        quase = clipe.stat().st_mtime - (status.TOLERANCIA_MTIME - 1)
        for perfil in ("celular", "normal"):
            os.utime(d / f"final_{perfil}.mp4", (quase, quase))
        self.assertEqual([], status.inconsistencias())

    def test_plano_ilegivel_nao_derruba_o_inventario(self):
        d = self._gerar("generation_00001", clipe_bytes=50_000)
        (d / "edit_plan.json").write_text("{quebrado", encoding="utf-8")
        linhas = status.inventario()
        self.assertIsNone(linhas[0]["no_plano"])


class DoctorTests(unittest.TestCase):
    """O diagnostico local roda sem browser e sem levantar."""

    def test_checar_local_devolve_checks_validos(self):
        checks = health.checar_local()
        self.assertTrue(checks)
        for check in checks:
            self.assertIn(check["estado"], (health.OK, health.AVISO, health.ERRO))
            self.assertTrue(check["nome"])
            self.assertIn(check["estado"], health.SIMBOLO)

    def test_pior_estado_escolhe_a_gravidade_certa(self):
        self.assertEqual(health.OK, health.pior_estado(
            [{"estado": health.OK}]))
        self.assertEqual(health.AVISO, health.pior_estado(
            [{"estado": health.OK}, {"estado": health.AVISO}]))
        self.assertEqual(health.ERRO, health.pior_estado(
            [{"estado": health.AVISO}, {"estado": health.ERRO}]))

    def test_espaco_e_persistido_assim_que_aparece(self):
        """O video em voo precisa sobreviver ate a um kill -9.

        A navegacao para /en/space/<id> costuma acontecer DEPOIS do envio, ja
        durante a espera. Se so gravassemos no fim, um worker morto no meio
        perderia o espaco e mandaria gerar outro video do mesmo personagem.
        """
        from builds.identity.client import DigenClient

        class FakePage:
            url = "https://digen.ai/en/space"

        page = FakePage()
        vistos = []
        client = DigenClient(None, page, {}, None,
                             ao_descobrir_espaco=vistos.append)

        client._anotar_espaco()
        self.assertEqual([], vistos, "avisou sem ter id de espaco")

        page.url = "https://digen.ai/en/space/999"
        client._anotar_espaco()
        self.assertEqual(["https://digen.ai/en/space/999"], vistos)

        client._anotar_espaco()
        self.assertEqual(1, len(vistos), "avisou duas vezes pelo mesmo espaco")

    def test_callback_quebrado_nao_derruba_a_geracao(self):
        """Persistir o espaco e conveniencia; o video e o que importa."""
        from builds.identity.client import DigenClient

        class FakePage:
            url = "https://digen.ai/en/space/999"

        def explode(_):
            raise RuntimeError("disco cheio")

        client = DigenClient(None, FakePage(), {}, None,
                             ao_descobrir_espaco=explode)
        client._anotar_espaco()
        self.assertEqual("https://digen.ai/en/space/999", client.url_do_espaco)

    def test_hidratacao_nao_exige_pagina_sem_spinner(self):
        """A pagina de Spaces mantem spinners permanentes (3, medidos).

        Exigir zero spinners fazia `esperar_hidratacao` queimar o limite
        inteiro em toda navegacao e devolver False mesmo com a pagina pronta —
        e o worker concluia que a sessao tinha caido, parando por 180 s
        esperando um login que nao era necessario.
        """
        from builds.identity import browser

        pedidos = []

        class FakeLocator:
            def __init__(self, quantos): self._quantos = quantos
            def count(self): return self._quantos

        class FakePage:
            def locator(self, seletor):
                pedidos.append(seletor)
                return FakeLocator(1)      # ha conteudo na tela

        self.assertTrue(browser.esperar_hidratacao(FakePage(), limite=2))
        self.assertTrue(pedidos, "nao consultou a pagina")
        for seletor in pedidos:
            self.assertNotIn("animate-spin", seletor,
                             "voltou a depender de spinner")

    def test_hidratacao_devolve_false_sem_conteudo(self):
        class FakeLocator:
            def count(self): return 0

        class FakePage:
            def locator(self, _): return FakeLocator()

        self.assertFalse(browser.esperar_hidratacao(FakePage(), limite=1))

    def test_erro_transitorio_nao_conta_como_browser_morto(self):
        """Numa SPA, `evaluate` falha o tempo todo por motivos passageiros.

        "Execution context was destroyed" acontece a cada re-render/navegacao
        do Digen. Tratar isso como browser morto derrubava a rodada logo depois
        de `abrir_espaco`, e o `--watch` virava um ciclo de abrir e fechar o
        Chrome a cada ~50 s — exatamente o sintoma reportado.
        """
        from builds.identity.client import BrowserMorreu, DigenClient, _e_alvo_fechado

        transitorios = [
            "Execution context was destroyed, most likely because of a navigation",
            "Element is not attached to the DOM",
            "Timeout 5000ms exceeded",
        ]
        fatais = [
            "Target page, context or browser has been closed",
            "Protocol error: Connection closed",
        ]
        for msg in transitorios:
            self.assertFalse(_e_alvo_fechado(Exception(msg)), msg)
        for msg in fatais:
            self.assertTrue(_e_alvo_fechado(Exception(msg)), msg)

        class FakePage:
            url = "https://digen.ai/en/space/9"

            def __init__(self, erro): self.erro = erro
            def is_closed(self): return False
            def evaluate(self, _): raise RuntimeError(self.erro)

        # transitorio: segue esperando
        DigenClient(None, FakePage(transitorios[0]), {})._checar_vivo()
        # fatal: aborta
        with self.assertRaises(BrowserMorreu):
            DigenClient(None, FakePage(fatais[0]), {})._checar_vivo()

    def test_watch_recua_quando_a_rodada_nao_progride(self):
        """Sem recuo, um job travado abre e fecha o Chrome para sempre.

        O recuo vale so para rodada improdutiva (havia trabalho e nada saiu);
        fila vazia mantem o intervalo normal, senao um job novo demoraria
        minutos para ser notado.
        """
        import inspect
        from builds.identity import worker

        corpo = inspect.getsource(worker.observar)
        self.assertIn("improdutivas", corpo)
        self.assertIn("not havia", corpo, "fila vazia nao deveria acionar recuo")
        self.assertIn("watch_backoff_max", corpo)

    def test_aba_morta_encerra_a_rodada_antes_do_estouro_generico(self):
        """`BrowserMorreu` herda de `EsperaEstourou`: a ORDEM do except manda.

        Se `except EsperaEstourou` viesse primeiro, ele engoliria tambem a aba
        morta e o worker seguiria usando um `page` morto — foi o loop de 50 em
        50 s visto em 22/08, falhando instantaneamente em todo job seguinte.
        """
        import inspect
        from builds.identity.client import BrowserMorreu, EsperaEstourou
        from builds.identity import worker

        self.assertTrue(issubclass(BrowserMorreu, EsperaEstourou))
        # O laco de jobs vive em `_passada` (uma por provedor); `_drenar` so
        # orquestra as passadas.
        corpo = inspect.getsource(worker._passada)
        self.assertLess(corpo.index("except BrowserMorreu"),
                        corpo.index("except EsperaEstourou"),
                        "BrowserMorreu precisa ser capturado ANTES do pai")

    def test_seletor_quebrado_aborta_a_rodada(self):
        """Deploy de qualquer um dos dois sites nao pode virar falha em looping.

        Sem abortar, `--watch` repetiria a mesma falha a cada 30 s e queimaria
        as tentativas de TODOS os jobs da fila em silencio — o pior desfecho
        possivel, porque some com o trabalho e nao avisa. O contrato: quebra de
        seletor para a rodada e sobe `DeployDoDigen`, que o watch trata saindo.
        """
        import inspect
        from builds.identity import worker

        # Quem detecta a quebra e a passada; quem sobe o erro e a rodada.
        self.assertIn("SeletorNaoEncontrado", inspect.getsource(worker._passada))
        self.assertIn("raise DeployDoDigen", inspect.getsource(worker._drenar))
        self.assertIn("DeployDoDigen", inspect.getsource(worker.observar))
        self.assertTrue(issubclass(worker.DeployDoDigen, RuntimeError))

    def test_saida_e_ascii(self):
        """Console cp1252 no Windows transforma travessao em '?'.

        Ferramenta de monitoramento ilegivel no terminal padrao do usuario nao
        cumpre o proposito.
        """
        for modulo in (health, status, history):
            texto = Path(modulo.__file__).read_text(encoding="utf-8")
            fora = sorted({c for c in texto if ord(c) > 127})
            self.assertEqual([], fora, f"{modulo.__name__}: {fora}")


if __name__ == "__main__":
    unittest.main()
