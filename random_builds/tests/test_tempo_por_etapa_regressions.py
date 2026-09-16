# -*- coding: utf-8 -*-
"""Tempo por etapa: o campo que nao existia.

Ate 16/09/2026 nao havia UM campo de duracao por etapa em todo o
repositorio. O unico cronometro era o da rodada inteira, e ia para o texto
do Telegram, nunca para disco. Os numeros que o projeto repetia ("2h12 por
historia") eram comentarios escritos a mao no config.

O risco desta mudanca nao e medir errado — e quebrar o diario, que e o que
a Vila, o bot e os relatorios leem. Por isso metade destes casos prova que
NADA mudou para quem ja lia.
"""
import json

import tempfile
import unittest
from pathlib import Path

from builds import atividade, tempos


class _Relogio:
    """Monotonico falso: o teste nao pode depender do relogio de verdade."""

    def __init__(self, passos):
        self.passos, self.i = list(passos), 0

    def __call__(self):
        valor = self.passos[min(self.i, len(self.passos) - 1)]
        self.i += 1
        return valor


class _TempoFalso:
    """Substitui a REFERENCIA `atividade.time`, nunca o modulo `time`.

    Escrever `atividade.time.monotonic = ...` mexeria no modulo `time` de
    verdade, para o processo inteiro — inclusive para as outras 3000 provas
    desta suite. Trocar a referencia isola o estrago em um modulo so.
    """

    def __init__(self, passos):
        self.monotonic = _Relogio(passos)


class _Diario(unittest.TestCase):
    """Cada caso escreve num runtime descartavel."""

    def setUp(self):
        # `NEURAL_FIGHTS_RUNTIME_DIR` e lido no IMPORT de
        # `neural_fights.data.database`, entao trocar a variavel agora nao
        # moveria nada — o diario de verdade e que receberia os eventos de
        # teste. Trocar `_arquivo` e a unica isolacao que funciona aqui.
        self.pasta = Path(tempfile.mkdtemp(prefix="tempos-"))
        self.diario = self.pasta / "atividade.jsonl"
        real = atividade._arquivo
        atividade._arquivo = lambda: self.diario
        self.addCleanup(lambda: setattr(atividade, "_arquivo", real))

    def linhas(self):
        if not self.diario.exists():
            return []
        return [json.loads(l) for l in
                self.diario.read_text(encoding="utf-8").splitlines()
                if l.strip()]


class OContratoAntigoVale(_Diario):

    def test_linha_sem_os_campos_novos_sai_como_antes(self):
        # A REGRESSAO QUE PROTEGE TUDO: chave nova que aparece vazia mudaria
        # o formato para todo leitor, inclusive os que nao sao meus.
        atividade.registrar("estudio", atividade.OK, "oi", "historias")
        linha = self.linhas()[-1]
        self.assertEqual(set(linha),
                         {"ts", "pid", "fabrica", "canal", "status", "detalhe"})

    def test_os_leitores_antigos_engolem_os_campos_novos(self):
        atividade.registrar("estudio", atividade.OK, "oi", "historias",
                            etapa="render.mix", ref="h12:p3", dur_s=9.5)
        self.assertTrue(atividade.recentes(5))
        self.assertIsInstance(atividade.estado_das_fabricas(), dict)
        self.assertIsInstance(atividade.estado_por_canal(), dict)

    def test_registrar_continua_nunca_levantando(self):
        # Um objeto que estoura ao virar texto nao pode derrubar a rodada.
        class Ruim:
            def __str__(self):
                raise ValueError("nao sou texto")

        atividade.registrar("estudio", atividade.OK, Ruim(), "historias")


class ACronometragem(_Diario):

    def _congelar(self, passos):
        real = atividade.time
        atividade.time = _TempoFalso(passos)
        self.addCleanup(lambda: setattr(atividade, "time", real))

    def test_o_ok_carrega_a_duracao(self):
        self._congelar([100.0, 142.4])
        with atividade.fabrica("estudio", "render", "historias",
                               etapa="render.segmento", ref="h12:p3"):
            pass
        linha = self.linhas()[-1]
        self.assertEqual(linha["status"], atividade.OK)
        self.assertEqual(linha["dur_s"], 42.4)
        self.assertEqual(linha["etapa"], "render.segmento")
        self.assertEqual(linha["ref"], "h12:p3")

    def test_o_erro_TAMBEM_carrega_a_duracao_e_re_levanta(self):
        # Etapa que estoura e justamente a que se quer medir: sem isto o
        # tempo perdido numa falha some do total do dia e a conta fecha
        # errado PARA MENOS.
        self._congelar([10.0, 25.0])
        with self.assertRaises(ValueError):
            with atividade.fabrica("picasso", "cena", "historias",
                                   etapa="imagem"):
                raise ValueError("a conta caiu")
        linha = self.linhas()[-1]
        self.assertEqual(linha["status"], atividade.ERRO)
        self.assertEqual(linha["dur_s"], 15.0)

    def test_marco_nao_abre_outro_inicio(self):
        # Abrir e fechar uma fabrica por cena encheria o diario, e a poda
        # (4000 -> 2000 linhas) comeria o dia em poucas horas.
        with atividade.fabrica("picasso", "84 cenas", "historias") as diario:
            diario.marco("imagem", 12.1, "cena 3")
            diario.marco("imagem.espera", 8.0, "cena 3")
        inicios = [l for l in self.linhas()
                   if l["status"] == atividade.TRABALHANDO]
        self.assertEqual(len(inicios), 1)
        marcos = [l for l in self.linhas() if l.get("etapa", "").startswith(
            "imagem")]
        self.assertEqual(len(marcos), 2)
        self.assertEqual(marcos[0]["dur_s"], 12.1)


class AConsolidacao(unittest.TestCase):
    """`resumir` e pura: lista na mao, sem disco e sem relogio."""

    EVENTOS = [
        {"canal": "historias", "fabrica": "estudio", "etapa": "render.segmento",
         "status": atividade.OK, "dur_s": 10.0, "ref": "h12:p1"},
        {"canal": "historias", "fabrica": "estudio", "etapa": "render.segmento",
         "status": atividade.OK, "dur_s": 20.0, "ref": "h12:p2"},
        {"canal": "historias", "fabrica": "estudio", "etapa": "render.segmento",
         "status": atividade.ERRO, "dur_s": 90.0, "ref": "h12:p2"},
        {"canal": "historias", "fabrica": "picasso", "etapa": "imagem",
         "status": atividade.OK, "dur_s": 5.0},
        # Sem duracao: e a maioria do diario e nao pode entrar na conta.
        {"canal": "historias", "fabrica": "estudio", "status": atividade.OK},
    ]

    def test_conta_n_ok_erro_e_o_total(self):
        etapas = tempos.resumir(self.EVENTOS)
        ficha = etapas["historias/estudio/render.segmento"]
        self.assertEqual((ficha["n"], ficha["ok"], ficha["erro"]), (3, 2, 1))
        self.assertEqual(ficha["total_s"], 120.0)
        self.assertEqual(ficha["max"], 90.0)
        self.assertEqual(ficha["p50"], 20.0)

    def test_evento_sem_duracao_fica_de_fora(self):
        etapas = tempos.resumir(self.EVENTOS)
        self.assertNotIn("historias/estudio/", etapas)

    def test_conta_a_quantas_coisas_diferentes_o_tempo_pertence(self):
        # Sem `refs`, um pico e indistinguivel de uma historia grande.
        ficha = tempos.resumir(self.EVENTOS)[
            "historias/estudio/render.segmento"]
        self.assertEqual(ficha["refs"], 2)

    def test_lista_torta_nao_levanta(self):
        for entrada in (None, [], [None], ["texto"], [{}]):
            self.assertEqual(tempos.resumir(entrada), {})

    def test_o_erro_entra_no_total_do_dia(self):
        # O caso que justifica medir o erro: 90 s perdidos numa falha sao 90
        # s do dia. Somar so o que deu certo responderia a pergunta errada.
        ficha = tempos.resumir(self.EVENTOS)[
            "historias/estudio/render.segmento"]
        self.assertGreater(ficha["total_s"], 30.0)


class OArquivoDoDia(_Diario):

    def setUp(self):
        super().setUp()
        # Sem isto o teste escreveria na pasta de tempos DE VERDADE e
        # plantaria dias falsos na serie do Adrian.
        real = tempos.pasta
        tempos.pasta = lambda: self.pasta / "tempos"
        self.addCleanup(lambda: setattr(tempos, "pasta", real))

    def test_consolidar_duas_vezes_da_o_mesmo(self):
        eventos = AConsolidacao.EVENTOS
        a = tempos.consolidar("2026-09-15", eventos=eventos)
        primeiro = json.loads(a.read_text(encoding="utf-8"))
        tempos.consolidar("2026-09-15", eventos=eventos)
        segundo = tempos.carregar("2026-09-15")
        self.assertEqual(primeiro["etapas"], segundo["etapas"])

    def test_dia_sem_arquivo_devolve_vazio(self):
        self.assertEqual(tempos.carregar("1999-01-01"), {})

    def test_a_serie_guarda_o_buraco(self):
        # Dia sem medida entra como None: buraco e informacao (maquina
        # desligada, rodada que nao correu). Fechar o buraco faria duas
        # semanas parecerem continuas quando nao foram.
        linha = tempos.series(dias=3)
        for valores in linha.values():
            self.assertEqual(len(valores), 3)


if __name__ == "__main__":
    unittest.main()
