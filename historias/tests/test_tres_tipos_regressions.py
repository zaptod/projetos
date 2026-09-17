# -*- coding: utf-8 -*-
"""Tres tipos de historia por dia: favela, normal e babaca (17/09/2026).

Decisoes do Adrian, e o que este arquivo trava:

1. O TIPO fica acima do molde: favela = quebrada; normal = reddit,
   confissao e vinganca em rodizio; babaca = o post "Eu sou o babaca?".
   A quebrada SAIU do rodizio geral.
2. O babaca tem numero de partes SORTEADO ("vai ser aleatoria").
3. A criacao escolhe o tipo com MENOS estoque aprovado.
4. A postagem alterna os tipos em RODIZIO, sem quebrar a ordem das partes.
5. O julgamento do babaca e em PORTUGUES — nunca NTA/YTA/ESH.

Rode de dentro de historias/:
    python -m unittest tests.test_tres_tipos_regressions -v
"""
from __future__ import annotations

import contextlib
import json
import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from contos.pipeline import agenda                                 # noqa: E402
from contos.publicar import tipos as T                             # noqa: E402
from contos.roteiro import gerar as G                              # noqa: E402
from contos.roteiro import roteiro as R                            # noqa: E402
from contos.roteiro import serie as S                              # noqa: E402
from contos.roteiro.modelo import carregar_config                  # noqa: E402

CONFIG = carregar_config()
# O modo GUIADO (moldes, abertura e fechamento prescritos) continua existindo
# para quem desligar o `modo: livre`; os testes dele usam esta copia.
CONFIG_GUIADO = json.loads(json.dumps(CONFIG))
for _ficha in CONFIG_GUIADO["tipos"].values():
    _ficha.pop("modo", None)


class OsTiposNoConfig(unittest.TestCase):

    def test_os_tres_tipos_e_seus_moldes(self):
        tipos = S.tipos(CONFIG)
        self.assertEqual(["favela", "normal", "babaca"], list(tipos))
        self.assertEqual(["quebrada"], tipos["favela"]["moldes"])
        self.assertEqual(["reddit", "confissao", "vinganca"],
                         tipos["normal"]["moldes"])
        self.assertEqual(["babaca"], tipos["babaca"]["moldes"])

    def test_molde_de_tipo_que_nao_existe_e_ignorado(self):
        config = dict(CONFIG, tipos={"x": {"moldes": ["nao_existe"]},
                                     "_comment": "texto"})
        self.assertEqual({}, S.tipos(config))

    def test_rodizio_fica_dentro_do_tipo(self):
        # A quebrada saiu do rodizio geral: o normal nunca a escolhe.
        usadas = ["reddit", "confissao", "vinganca"]
        for _ in range(6):
            molde = S.proxima_estrutura(usadas, CONFIG, tipo="normal")
            self.assertIn(molde, ("reddit", "confissao", "vinganca"))
            usadas.insert(0, molde)
        self.assertEqual("quebrada",
                         S.proxima_estrutura(usadas, CONFIG, tipo="favela"))
        self.assertEqual("babaca",
                         S.proxima_estrutura(usadas, CONFIG, tipo="babaca"))

    def test_historia_antiga_ganha_tipo_pelo_molde(self):
        self.assertEqual("favela", S.tipo_da_historia(
            {"estrutura": "quebrada"}, CONFIG))
        self.assertEqual("normal", S.tipo_da_historia(
            {"estrutura": "confissao"}, CONFIG))
        self.assertEqual("babaca", S.tipo_da_historia(
            {"estrutura": "reddit", "tipo": "babaca"}, CONFIG))
        self.assertEqual("", S.tipo_da_historia({}, CONFIG))


class PartesSorteadas(unittest.TestCase):

    def test_babaca_sorteia_dentro_da_faixa(self):
        rng = random.Random(7)
        vistos = {S.partes_do_tipo("babaca", 6, CONFIG, rng=rng)
                  for _ in range(200)}
        # "aleatorio de 2 a 6" (Adrian, 17/09/2026).
        self.assertEqual({2, 3, 4, 5, 6}, vistos)

    def test_tipo_sem_faixa_usa_a_agenda(self):
        self.assertEqual(6, S.partes_do_tipo("normal", 6, CONFIG))
        self.assertEqual(6, S.partes_do_tipo("favela", 6, CONFIG))

    def test_faixa_torta_usa_a_agenda(self):
        for faixa in ("3-6", [0, 4], ["x", 2], None):
            config = dict(CONFIG, tipos={"babaca": {"moldes": ["babaca"],
                                                    "partes": faixa}})
            self.assertEqual(6, S.partes_do_tipo("babaca", 6, config))

    def test_agenda_usa_o_sorteio_so_no_tipo_que_pede(self):
        self.assertEqual(6, agenda.partes_da_proxima("", {"partes": 6}))
        self.assertEqual(6, agenda.partes_da_proxima("normal", {"partes": 6}))
        self.assertIn(agenda.partes_da_proxima(
            "babaca", {"partes": 6}, rng=random.Random(1)), range(2, 7))


class CriacaoPeloTipoMaisMagro(unittest.TestCase):

    def test_o_tipo_com_menos_estoque_vai_primeiro(self):
        self.assertEqual("babaca", agenda.tipo_mais_magro(
            {"favela": 4, "normal": 2, "babaca": 0}))
        self.assertEqual("normal", agenda.tipo_mais_magro(
            {"favela": 4, "normal": 2, "babaca": 3}))

    def test_empate_segue_a_ordem_do_config(self):
        self.assertEqual("favela", agenda.tipo_mais_magro(
            {"favela": 1, "normal": 1, "babaca": 1}))

    def test_sem_tipos_nao_escolhe(self):
        self.assertEqual("", agenda.tipo_mais_magro({}))

    def test_estoque_conta_por_tipo_e_zero_aparece(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(setattr, R, "OUTPUTS", R.OUTPUTS)
        R.OUTPUTS = Path(tmp.name)
        biblia = {"titulo": "x", "partes": [{"n": 1}]}
        R.salvar_serie(biblia, [], "historia_00001", estrutura="quebrada")
        R.salvar_serie(biblia, [], "historia_00002", estrutura="reddit",
                       tipo="normal")
        videos = [SimpleNamespace(fonte_id="historia_00001"),
                  SimpleNamespace(fonte_id="historia_00001"),
                  SimpleNamespace(fonte_id="historia_00002"),
                  SimpleNamespace(fonte_id="historia_09999")]
        self.assertEqual({"favela": 2, "normal": 1, "babaca": 0},
                         agenda.estoque_por_tipo(videos))


class OTipoViajaComAHistoria(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for modulo in (R, G):
            self.addCleanup(setattr, modulo, "OUTPUTS", modulo.OUTPUTS)
            modulo.OUTPUTS = Path(tmp.name)

    def test_salvar_grava_o_tipo(self):
        R.salvar_serie({"titulo": "x", "partes": [{"n": 1}]}, [],
                       "historia_00003", estrutura="babaca", tipo="babaca")
        self.assertEqual("babaca", R.carregar("historia_00003")["tipo"])

    def test_tipo_vem_da_biblia_quando_nao_passado(self):
        R.salvar_serie({"titulo": "x", "tipo": "favela",
                        "partes": [{"n": 1}]}, [], "historia_00004")
        self.assertEqual("favela", R.carregar("historia_00004")["tipo"])

    def test_escrever_serie_repassa_o_tipo(self):
        vistos = []
        self.addCleanup(setattr, G, "gerar_serie", G.gerar_serie)
        G.gerar_serie = lambda **k: vistos.append(k.get("tipo")) or {
            "historia_id": "h", "partes": 1, "cenas": 1}
        G.escrever_serie(["gemini"], tipo="babaca", log=lambda *_a: None)
        self.assertEqual(["babaca"], vistos)


class OPromptDoBabacaGuiado(unittest.TestCase):

    def _biblia(self, partes=4):
        return {"titulo": "Eu sou o babaca?", "estrutura": "babaca",
                "tipo": "babaca",
                "partes": [{"n": k, "titulo": f"P{k}", "resumo": "r"}
                           for k in range(1, partes + 1)]}

    def test_parte_1_abre_com_a_pergunta_do_post(self):
        texto = S.prompt_parte(self._biblia(), 1, config=CONFIG_GUIADO)
        self.assertIn("Eu sou o babaca por", texto)
        self.assertNotIn("ABERTURA (parte 1): a primeira cena e o momento "
                         "mais chocante", texto)
        # A regra geral de narracao ("a primeira frase e o momento mais
        # chocante") continua no prompt: a abertura do molde diz que manda.
        self.assertIn("vale sobre qualquer regra geral", texto)

    def test_parte_do_meio_abre_com_edicao_e_fecha_em_fato_novo(self):
        texto = S.prompt_parte(self._biblia(), 2, config=CONFIG_GUIADO)
        self.assertIn("ABERTURA (parte 2)", texto)
        self.assertIn("'Edicao:'", texto)
        self.assertIn("proxima 'Edicao'", texto)

    def test_ultima_parte_pede_julgamento_em_portugues(self):
        texto = S.prompt_parte(self._biblia(), 4, config=CONFIG_GUIADO)
        self.assertIn("Resumindo:", texto)
        self.assertIn("eu errei, ela errou, ou todo mundo errou?", texto)
        self.assertIn("Nunca use NTA", texto)

    def test_as_regras_do_molde_chegam_a_retomada(self):
        # Chat novo: sem as regras aqui, o post viraria roteiro com dialogo.
        texto = S.prompt_parte(self._biblia(), 3, config=CONFIG_GUIADO)
        self.assertIn("PROSA", texto)
        self.assertIn("NOME DA SERIE e curto", texto)

    def test_babaca_de_duas_partes_tem_gancho_so_na_primeira(self):
        # Parte 1: a pergunta e o fato que a Edicao vai explicar.
        # Parte 2: abre com a Edicao e fecha com resumo e julgamento.
        biblia = self._biblia(partes=2)
        primeira = S.prompt_parte(biblia, 1, config=CONFIG_GUIADO)
        segunda = S.prompt_parte(biblia, 2, config=CONFIG_GUIADO)
        self.assertIn("PARTE 1 de 2", primeira)
        self.assertIn("'Eu sou o babaca por ...?'", primeira)
        self.assertIn("proxima 'Edicao'", primeira)
        self.assertNotIn("Resumindo:", primeira.split("ABERTURA (parte 1)")[1]
                         .split("CONSISTENCIA VISUAL")[0])
        self.assertIn("PARTE 2 de 2", segunda)
        self.assertIn("ABERTURA (parte 2)", segunda)
        self.assertIn("'Edicao:'", segunda)
        self.assertIn("Resumindo:", segunda)
        self.assertIn("eu errei, ela errou, ou todo mundo errou?", segunda)
        self.assertNotIn("proxima 'Edicao'", segunda)

    def test_o_normal_continua_com_a_abertura_de_sempre(self):
        biblia = dict(self._biblia(), estrutura="confissao", tipo="normal")
        self.assertIn("momento mais chocante",
                      S.prompt_parte(biblia, 1, config=CONFIG_GUIADO))

    def test_biblia_sem_molde_nao_quebra(self):
        biblia = {"titulo": "x", "partes": [{"n": 1}, {"n": 2}]}
        self.assertIn("ETAPA 2", S.prompt_parte(biblia, 2, config=CONFIG_GUIADO))

    def test_o_julgamento_em_portugues_passa_na_linguagem(self):
        from contos.roteiro import linguagem
        roteiro = R.normalizar({"titulo": "Eu sou o babaca?", "partes": [
            {"n": 1, "cenas": [{"n": 1, "imagem": "x", "tempo": 4,
                                "narracao": "Eu sou o babaca por nao "
                                            "emprestar o vestido?"},
                               {"n": 2, "imagem": "x", "tempo": 4,
                                "narracao": "Entao me fala: eu errei, ela "
                                            "errou, ou todo mundo errou?"}]}]})
        self.assertEqual([], linguagem.conferir(roteiro)["pare"])


class OModoLivre(unittest.TestCase):
    """Pedido do Adrian (17/09/2026): assunto base e tamanho, e a IA com
    autoridade para criar. O que fica e so o que nao se negocia."""

    def _biblia(self, partes=3):
        return {"titulo": "T", "tipo": "babaca", "estrutura": "babaca",
                "protagonista": "a Brazilian woman in her thirties",
                "fatos": "idade = 34",
                "partes": [{"n": k, "resumo": f"r{k}", "gancho": f"g{k}",
                            "cliffhanger": f"c{k}"}
                           for k in range(1, partes + 1)]}

    def test_os_tres_tipos_estao_livres_e_tem_assunto(self):
        for tipo in ("favela", "normal", "babaca"):
            self.assertTrue(S.livre(tipo, CONFIG), tipo)
            self.assertTrue(S.assunto_do_tipo(tipo, CONFIG), tipo)
        self.assertFalse(S.livre("babaca", CONFIG_GUIADO))

    def test_biblia_livre_da_assunto_tamanho_e_autoridade(self):
        texto = S.prompt_biblia(partes=4, cenas_por_parte=12, config=CONFIG,
                                tipo="babaca", estrutura="babaca",
                                ganchos=["TRAICAO"], narrador="mulher",
                                evitar=["historia velha"])
        self.assertIn(S.assunto_do_tipo("babaca", CONFIG), texto)
        self.assertIn("4 parte(s), cada uma com 12 cenas", texto)
        self.assertIn("AUTORIDADE CRIATIVA", texto)
        self.assertIn("historia velha", texto)
        self.assertIn("menor de 18", texto)
        for rotulo in ("TITULO DA SERIE:", "NOME DA SERIE:", "PROTAGONISTA:",
                       "NARRADOR:", "FATOS:", "PARTE 4", "GANCHO:"):
            self.assertIn(rotulo, texto)
        for engessado in ("MOLDE DESTA HISTORIA", "ALAVANCAS", "TRAICAO",
                          "QUEM CONTA", "Eu sou o babaca por"):
            self.assertNotIn(engessado, texto)

    def test_parte_livre_so_traz_o_necessario(self):
        texto = S.prompt_parte(self._biblia(), 2, config=CONFIG)
        self.assertIn("PARTE 2 de 3", texto)
        self.assertIn("exatamente 14 cenas", texto)
        self.assertIn("a Brazilian woman in her thirties", texto)
        self.assertIn("idade = 34", texto)
        self.assertIn("COMO DIZER O QUE E PESADO", texto)
        self.assertIn("CENA 1", texto)
        for engessado in ("ABERTURA (parte", "FECHAMENTO (parte",
                          "COMO ESCREVER A NARRACAO", "Edicao",
                          "AS REGRAS DO MOLDE"):
            self.assertNotIn(engessado, texto)

    def test_ultima_parte_livre_so_avisa_que_termina(self):
        texto = S.prompt_parte(self._biblia(), 3, config=CONFIG)
        self.assertIn("E a ultima parte", texto)
        self.assertNotIn("Resumindo", texto)

    def test_revisao_livre_e_curta_e_aceita_devolver_igual(self):
        livre = S.prompt_revisao(2, 14, config=CONFIG, biblia=self._biblia())
        guiada = S.prompt_revisao(2, 14, config=CONFIG)
        self.assertIn("devolva igual", livre)
        self.assertLess(len(livre), len(guiada) / 2)

    def test_biblia_livre_leva_uma_linha_do_que_evitar(self):
        texto = S.prompt_biblia(partes=2, config=CONFIG, tipo="favela",
                                recentes=["mulher; a sogra; o carro",
                                          "homem; o chefe; a demissao"])
        linha = [l for l in texto.splitlines() if "Evite repetir" in l]
        self.assertEqual(1, len(linha))
        self.assertIn("a sogra; o carro / homem; o chefe", linha[0])
        self.assertIn("VIRADA CENTRAL:", texto)
        sem = S.prompt_biblia(partes=2, config=CONFIG, tipo="favela")
        self.assertNotIn("Evite repetir", sem)

    def test_o_resumo_das_ultimas_vem_do_disco(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(setattr, R, "OUTPUTS", R.OUTPUTS)
        R.OUTPUTS = Path(tmp.name)
        for n, (narrador, premissa, virada) in enumerate((
                ("mulher", "p1", "v1"), ("homem", "p2", "v2"),
                ("mulher", "p3", "v3"), ("homem", "p4", "v4")), 1):
            R.salvar_serie({"titulo": "x", "premissa": premissa,
                            "virada": virada, "partes": [{"n": 1}]}, [],
                           f"historia_0000{n}", narrador=narrador)
        self.assertEqual(["homem; p4; v4", "mulher; p3; v3", "homem; p2; v2"],
                         R.resumos_recentes(3))

    def test_corte_automatico_fica_no_diario(self):
        from builds import atividade
        from builds.publicar import cortes
        registros = []
        reais = (atividade.registrar, cortes.precisa, cortes.pedacos,
                 cortes.fronteiras, cortes.ganchos, cortes.cortar,
                 cortes._copia)
        atividade.registrar = lambda *a, **k: registros.append((a, k))
        cortes.precisa = lambda video, limite: (250.0, True)
        cortes.pedacos = lambda *a, **k: [(0, 125), (125, 250)]
        cortes.fronteiras = lambda caminho: []
        cortes.ganchos = lambda caminho: {}
        cortes.cortar = lambda caminho, fatias, log=print: ["a", "b"]
        cortes._copia = lambda video, arquivo, i, total: arquivo

        def restaurar():
            (atividade.registrar, cortes.precisa, cortes.pedacos,
             cortes.fronteiras, cortes.ganchos, cortes.cortar,
             cortes._copia) = reais

        self.addCleanup(restaurar)
        video = SimpleNamespace(caminho="x/h_p01.mp4", id="h:celular:p01",
                                canal="historias")
        self.assertEqual(["a", "b"],
                         cortes.preparar(video, limite=180, log=lambda *_a: None))
        ((args, kwargs),) = registros
        self.assertEqual(("publicacao", atividade.LOG), args[:2])
        self.assertIn("250s passou de 180s", args[2])
        self.assertEqual("publicar.corte", kwargs["etapa"])
        self.assertEqual("h:celular:p01", kwargs["ref"])

    def test_gerar_serie_livre_grava_o_narrador_que_a_ia_escolheu(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for modulo in (R, G):
            self.addCleanup(setattr, modulo, "OUTPUTS", modulo.OUTPUTS)
            modulo.OUTPUTS = Path(tmp.name)
        biblia = ("TITULO DA SERIE: O vestido\nNOME DA SERIE: O Vestido\n"
                  "PREMISSA: a irma pegou o vestido. Quem errou?\n"
                  "PROTAGONISTA: Joao | a Brazilian man in his forties, bald\n"
                  "NARRADOR: Homem, 41 anos\n"
                  "CENARIO: a small apartment in Sao Paulo\n"
                  "FATOS: idade = 41\n\nPARTE 1\nTITULO: O vestido\n"
                  "RESUMO: r\nGANCHO: g\nCLIFFHANGER: c\n")
        parte = "TITULO: O vestido (Parte 1)\n\n" + "\n\n".join(
            f"CENA {i}\nIMAGEM: a bald Brazilian man in a small kitchen, "
            f"moment {i}\nTEMPO: 4\nNARRACAO: Eu nunca achei que ia contar "
            f"isso, parte {i}." for i in (1, 2))
        perguntas = []

        class Cliente:
            modelo_atual, modelo_confirmado = "DeepSeek (site)", True

            def abrir(self, novo_chat=True):
                pass

            def perguntar(self, prompt, timeout=None):
                perguntas.append(prompt)
                return biblia if len(perguntas) == 1 else parte

        from contos.llm import cliente as llm_cliente
        self.addCleanup(setattr, llm_cliente, "abrir_cliente",
                        llm_cliente.abrir_cliente)
        llm_cliente.abrir_cliente = (
            lambda *a, **k: contextlib.nullcontext(Cliente()))
        feito = G.gerar_serie(provedor="deepseek", partes=1,
                              cenas_por_parte=2, tipo="babaca",
                              historia_id="historia_00005",
                              log=lambda *_a: None)
        roteiro = R.carregar(feito["historia_id"])
        self.assertEqual("homem", roteiro["narrador"])
        self.assertEqual([], roteiro["ganchos"])
        self.assertEqual("babaca", roteiro["tipo"])
        self.assertIn("AUTORIDADE CRIATIVA", perguntas[0])
        self.assertNotIn("ABERTURA (parte", perguntas[1])


class RodizioNaFila(unittest.TestCase):

    @staticmethod
    def _v(vid, tipo):
        return SimpleNamespace(id=vid, tipo=tipo)

    def _ordem(self, fila, ultimos):
        return [v.id for v in T.ordenar_por_tipo(
            fila, ultimos, lambda v: v.tipo)]

    def test_quem_esta_ha_mais_tempo_sem_sair_vai_primeiro(self):
        fila = [self._v("f1", "favela"), self._v("n1", "normal"),
                self._v("b1", "babaca")]
        self.assertEqual(["b1", "f1", "n1"],
                         self._ordem(fila, ["normal", "favela", "babaca"]))

    def test_tipo_nunca_publicado_vai_antes_de_todos(self):
        fila = [self._v("f1", "favela"), self._v("b1", "babaca")]
        self.assertEqual(["b1", "f1"], self._ordem(fila, ["favela"]))

    def test_intercala_e_preserva_a_ordem_das_partes(self):
        fila = [self._v("f:p2", "favela"), self._v("f:p3", "favela"),
                self._v("n:p5", "normal"), self._v("b:p1", "babaca"),
                self._v("b:p2", "babaca")]
        ordem = self._ordem(fila, ["favela", "babaca", "normal"])
        self.assertEqual(["n:p5", "b:p1", "f:p2", "b:p2", "f:p3"], ordem)
        self.assertLess(ordem.index("f:p2"), ordem.index("f:p3"))
        self.assertLess(ordem.index("b:p1"), ordem.index("b:p2"))

    def test_nao_tira_nem_poe_ninguem(self):
        fila = [self._v("x", ""), self._v("f1", "favela"),
                self._v("n1", "normal")]
        ordem = self._ordem(fila, [])
        self.assertEqual(sorted(v.id for v in fila), sorted(ordem))
        self.assertEqual("x", ordem[-1], "sem tipo vai para o fim")

    def test_fila_com_um_tipo_so_fica_como_veio(self):
        # Ate existir estoque dos tres tipos, a fila so tem um: o rodizio
        # nao pode mudar nada nem esvaziar horario.
        fila = [self._v("n:p2", "normal"), self._v("n:p3", "normal"),
                self._v("m:p1", "normal")]
        for ultimos in ([], ["normal"], ["favela", "babaca"]):
            self.assertEqual(["n:p2", "n:p3", "m:p1"],
                             self._ordem(fila, ultimos))

    def test_fila_so_de_historias_antigas_sem_tipo_fica_como_veio(self):
        fila = [self._v("a", ""), self._v("b", "")]
        self.assertEqual(["a", "b"], self._ordem(fila, ["favela"]))

    def test_fila_vazia(self):
        self.assertEqual([], T.ordenar_por_tipo([], ["favela"], str))

    def test_tipos_das_ultimas_do_ledger(self):
        linhas = [
            {"quando": "2026-09-17T06:37", "plataforma": "youtube",
             "video_id": "historia_00001:celular:p01", "url": "u"},
            {"quando": "2026-09-17T09:37", "plataforma": "youtube",
             "video_id": "historia_00002:celular:p01", "url": "u"},
            {"quando": "2026-09-17T09:38", "plataforma": "tiktok",
             "video_id": "historia_00003:celular:p01", "url": "u"},
            {"quando": "2026-09-17T12:07", "plataforma": "youtube",
             "video_id": "historia_00003:celular:p01", "url": ""},
        ]
        tipo = {"historia_00001": "favela", "historia_00002": "babaca",
                "historia_00003": "normal"}.get
        self.assertEqual(["babaca", "favela"],
                         T.tipos_das_ultimas(linhas, tipo))


if __name__ == "__main__":
    unittest.main()
