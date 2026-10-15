# -*- coding: utf-8 -*-
"""Contratos do painel novo. Sem abrir janela onde da para evitar.

Rode da raiz:
    python -m unittest painel.test_painel -v
"""
from __future__ import annotations

import gc
import os
import pathlib
import tkinter as tk
import unittest
from unittest.mock import patch

from painel import estilo
from painel.processos import Periodico, Supervisor
from painel.widgets import Oficina


PANORAMA_VAZIO = {"saude": {}, "desempenho": {}, "inventario": {},
                  "qualidade": {}, "confiabilidade": {}}


def _resumo_vazio(*_args, **_kwargs):
    """Impede que as Cascas leiam metricas, ledger ou diario reais."""
    return {chave: dict(valor) for chave, valor in PANORAMA_VAZIO.items()}


def setUpModule():
    global _dubles, _pasta_processos, _env_antes
    import tempfile
    # `Casca._pedir_resumo()` importa panorama dentro da thread de fundo.
    # Dublar esta porta cobre todas as paginas que abrem uma Casca aqui.
    # O Fluxo (`ao_mostrar`) le `snapshot` e o freio le `controle.estado`:
    # sem dubles, os testes liam a maquina de verdade (PNL-19).
    _dubles = [
        patch("panorama.resumo", side_effect=_resumo_vazio),
        patch("builds.pipeline.fluxo.snapshot",
              return_value={"geracoes": []}),
        patch("builds.identity.controle.estado",
              return_value={"situacao": "rodando", "pausas": {},
                            "parada": None, "resumo": "rodando normalmente"}),
    ]
    for duble in _dubles:
        duble.start()
    # As fichas de "ja esta rodando" das janelas (PNL-1) ficam numa pasta
    # descartavel, nunca no runtime de verdade.
    _pasta_processos = tempfile.mkdtemp(prefix="nf-painel-processos-")
    _env_antes = os.environ.get("NF_PAINEL_PROCESSOS")
    os.environ["NF_PAINEL_PROCESSOS"] = _pasta_processos


def tearDownModule():
    for duble in _dubles:
        duble.stop()
    if _env_antes is None:
        os.environ.pop("NF_PAINEL_PROCESSOS", None)
    else:
        os.environ["NF_PAINEL_PROCESSOS"] = _env_antes


class PanoramaDubladoTests(unittest.TestCase):
    def test_o_resumo_das_cascas_nao_toca_os_dados_reais(self):
        import panorama

        dados = panorama.resumo()
        self.assertEqual(PANORAMA_VAZIO, dados)
        dados["saude"]["fila"] = "alterado"
        self.assertEqual({}, panorama.resumo()["saude"])

    def test_snapshot_e_controle_dublados(self):
        from unittest.mock import MagicMock

        from builds.identity import controle
        from painel.paginas import fluxo
        self.assertIsInstance(fluxo.regra.snapshot, MagicMock)
        self.assertIsInstance(controle.estado, MagicMock)


class TemaTests(unittest.TestCase):
    def test_as_duas_caras_tem_as_MESMAS_chaves(self):
        """Se uma tem uma cor que a outra nao tem, a pagina quebra ao trocar."""
        self.assertEqual(set(estilo.OFICINA.cores()),
                         set(estilo.VILA.cores()))

    def test_os_papeis_de_texto_batem(self):
        self.assertEqual(set(estilo.OFICINA._texto), set(estilo.VILA._texto))

    def test_cor_com_nome_de_metodo_e_recusada_na_montagem(self):
        """`__getattr__` so roda quando a busca normal falha.

        Uma cor chamada "letra" nunca seria devolvida -- o Tk receberia o
        objeto do metodo virado texto e diria "unknown color name". Aconteceu
        com a cor `texto` contra o metodo `texto()`, e o erro so aparecia ao
        montar a tela.
        """
        with self.assertRaises(ValueError) as caso:
            estilo.Tema(nome="ruim", fonte="Segoe UI", densidade=20,
                        escala_texto={"corpo": 10},
                        cores={"letra": "#ffffff"})
        self.assertIn("letra", str(caso.exception))

    def test_cor_inexistente_diz_quais_existem(self):
        with self.assertRaises(AttributeError) as caso:
            estilo.OFICINA.roxo_bonito                       # noqa: B018
        self.assertIn("acento", str(caso.exception))

    def test_a_vila_nao_usa_o_roxo_da_oficina(self):
        """As caras precisam ser distinguiveis, senao nao sao duas caras."""
        self.assertNotEqual(estilo.OFICINA.acento, estilo.VILA.acento)


class TabelaTests(unittest.TestCase):
    def setUp(self):
        self.raiz = tk.Tk()
        self.raiz.withdraw()
        self.addCleanup(self.raiz.destroy)
        self.o = Oficina(estilo.OFICINA)

    def test_id_repetido_e_recusado_na_cara(self):
        """O Tk aceita e depois desalinha o cabecalho em silencio."""
        colunas = [("build", "GERAÇÃO", 100, "w"),
                   ("nome", "PERSONAGEM", 100, "w"),
                   ("build", "BUILD", 60, "center")]
        with self.assertRaises(ValueError) as caso:
            self.o.tabela(self.raiz, colunas)
        self.assertIn("build", str(caso.exception))

    def test_ids_distintos_montam(self):
        colunas = [("id", "GERAÇÃO", 100, "w"), ("nome", "NOME", 100, "w")]
        tabela = self.o.tabela(self.raiz, colunas)
        self.assertEqual(("id", "nome"), tabela["columns"])

    def test_largura_cabe_e_verificavel(self):
        colunas = [("a", "A", 600, "w"), ("b", "B", 600, "w")]
        self.assertFalse(self.o.largura_cabe(colunas, 1116))
        self.assertTrue(self.o.largura_cabe(colunas[:1], 1116))


class GavetaTests(unittest.TestCase):
    """O console em gaveta e o que devolveu ~100px ao conteudo."""

    def setUp(self):
        from painel.app import Casca
        from painel.paginas import fluxo
        self.app = Casca.criar([fluxo.Pagina])
        self.app.geometry("1366x740")
        self.app.update()
        self.addCleanup(self._fechar)

    def _fechar(self):
        self.app.encerrar()
        # As leituras de fundo seguram a janela: se acabarem depois do
        # destroy, o Tk e finalizado fora da thread principal e o processo
        # aborta. Espera, destroi e coleta AQUI.
        self.app.supervisor.aguardar(60)
        self.app.destroy()
        gc.collect()

    def test_fechada_ocupa_uma_faixa_fina(self):
        altura = self.app._gaveta.winfo_height()
        self.assertLessEqual(altura, 40,
                             "o console fixo antigo comia 130px do conteudo")
        self.assertGreater(altura, 10, "a faixa precisa ser visivel")

    def test_abre_e_fecha(self):
        fechada = self.app._gaveta.winfo_height()
        self.app._abrir_console()
        self.app.update()
        self.assertGreater(self.app._gaveta.winfo_height(), fechada + 60)
        self.app._fechar_console()
        self.app.update()
        self.assertEqual(fechada, self.app._gaveta.winfo_height())

    def test_um_comando_abre_a_gaveta_sozinho(self):
        self.app._fechar_console()
        self.app._registrar(">>> alguma coisa", "cmd")
        self.assertTrue(self.app._console_aberto)

    def test_a_gaveta_fica_no_pe_da_janela(self):
        gaveta = self.app._gaveta
        base = gaveta.winfo_y() + gaveta.winfo_height()
        self.assertEqual(self.app.winfo_height(), base,
                         "a gaveta tem que encostar na base")


class FreioDaPipelineTests(unittest.TestCase):
    """O freio de mao da pipeline SUMIU na reescrita em 3 janelas (01/09).

    As contas do PicassoIA/Digen sao compartilhadas: quando alguem mais
    precisa da ferramenta, a pipeline tem que parar sem ninguem digitar
    comando, e sem matar o worker no meio de um job. Depois do split so a
    CLI ficou com `pausar/retomar/parar` — o painel nao tinha nenhum
    caminho, e nada apontou isso.
    """

    def setUp(self):
        from painel.app import Casca
        from painel.paginas import fluxo
        self.app = Casca.criar([fluxo.Pagina], pipeline=True)
        self.app.geometry("1366x740")
        self.app.update()
        self.addCleanup(self._fechar)

    def _fechar(self):
        self.app.encerrar()
        # As leituras de fundo seguram a janela: se acabarem depois do
        # destroy, o Tk e finalizado fora da thread principal e o processo
        # aborta. Espera, destroi e coleta AQUI.
        self.app.supervisor.aguardar(60)
        self.app.destroy()
        gc.collect()

    def test_a_faixa_existe_na_janela_de_criacao(self):
        from painel.app import ALVOS_DO_FREIO
        self.assertTrue(hasattr(self.app, "_pipeline_estado"))
        self.assertEqual(ALVOS_DO_FREIO,
                         tuple(self.app._pipeline_alvo.cget("values")))

    def test_combo_tem_os_alvos_da_cli(self):
        """PNL-23: o combo nao oferecia "correio", que a CLI aceita."""
        escolhas = ComandosDaUITests._choices_do_provedor()
        self.assertTrue(escolhas, "nao li os choices do argparse")
        for sub in ("pausar", "retomar", "identity pausar",
                    "identity retomar"):
            self.assertEqual(set(escolhas[sub]),
                             set(self.app._pipeline_alvo.cget("values")),
                             sub)

    def test_a_faixa_mostra_o_estado_lido_do_disco(self):
        self.app._entregar_pipeline(
            {"situacao": "pausado", "resumo": "pausado: tudo (emprestada)"})
        texto = self.app._pipeline_estado.cget("text")
        self.assertIn("pausado", texto)
        self.assertIn("⏸", texto)

    def test_estado_ilegivel_nao_derruba_a_faixa(self):
        self.app._entregar_pipeline(None)
        self.app._entregar_pipeline("qualquer coisa")

    def test_leitura_que_falha_nao_vira_rodando(self):
        """FALHA: o `controle` estourou. Antes: "● rodando" em verde."""
        self.app._entregar_pipeline({"erro": "OSError: trancado"})
        texto = self.app._pipeline_estado.cget("text")
        self.assertNotIn("rodando", texto)
        self.assertNotIn("●", texto)
        self.assertIn("ilegível", texto)
        self.assertIn("trancado", texto)
        self.assertEqual(self.app.tema.erro,
                         self.app._pipeline_estado.cget("fg"))
        self.app._entregar_pipeline({})
        self.assertIn("ilegível", self.app._pipeline_estado.cget("text"))

    def test_rodando_de_verdade_continua_verde(self):
        """O caso normal: `situacao` lida = o que a faixa mostra."""
        self.app._entregar_pipeline({"situacao": "rodando",
                                     "resumo": "rodando normalmente"})
        self.assertIn("● rodando", self.app._pipeline_estado.cget("text"))
        self.assertEqual(self.app.tema.ok,
                         self.app._pipeline_estado.cget("fg"))

    def test_encerrar_desliga_o_pulso_da_pipeline(self):
        """PNL-17: o pulso do freio seguia agendado depois de fechar."""
        pulso = self.app._pulso_pipeline
        self.assertTrue(pulso._ligado)
        self.app.encerrar()
        self.assertFalse(pulso._ligado)
        self.assertIsNone(pulso._agendado)

    # NAO criar uma segunda Casca aqui para testar a janela sem freio: dois
    # interpretadores Tk no MESMO processo deixam a thread da janela anterior
    # tocando um interpretador morto ("async handler deleted by the wrong
    # thread") e a suite morre sem imprimir. Quem cobre isso e o contrato de
    # `JANELAS` abaixo, que e onde a ligacao mora.

    def test_a_janela_de_criacao_pede_o_freio(self):
        """A ligacao mora em `janelas.py`; sem ela a faixa existe e nao aparece."""
        from painel.janelas import JANELAS
        self.assertTrue(JANELAS["criacao"].get("pipeline"))
        self.assertFalse(JANELAS["vila"].get("pipeline"))
        self.assertFalse(JANELAS["jogo"].get("pipeline"))


class EstadoSemDonoTests(unittest.TestCase):
    """Atributo que a pagina LE e nenhuma tela ESCREVE = funcao morta.

    Foi assim que `Videos.escolhas` passou despercebido: nasceu `{}` no
    `__init__`, era lido em `_bandeiras()` para montar `--fixar`/`--genero`,
    e o dialogo que o preenchia ficou para tras na reescrita em 3 janelas.
    O painel continuou montando, os testes continuaram verdes, e escolher
    atributo simplesmente deixou de existir.
    """

    MUTADORES = ("append", "extend", "update", "clear", "pop", "setdefault",
                 "add", "remove", "insert", "sort", "discard")

    @staticmethod
    def _self_attr(no):
        """`self.x` -> "x"; qualquer outra coisa -> None."""
        import ast
        if isinstance(no, ast.Attribute) and isinstance(no.value, ast.Name)                 and no.value.id == "self":
            return no.attr
        return None

    def _escritos(self, corpo) -> set:
        """Tudo que MUDA o atributo: atribuir, indexar ou mutar no lugar."""
        import ast
        nomes = set()
        for no in ast.walk(corpo):
            if isinstance(no, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                alvos = (no.targets if isinstance(no, ast.Assign)
                         else [no.target])
                for alvo in alvos:
                    direto = self._self_attr(alvo)
                    if direto:
                        nomes.add(direto)
                    # `self.x[k] = v` e escrita em `x`, nao leitura
                    if isinstance(alvo, ast.Subscript):
                        indexado = self._self_attr(alvo.value)
                        if indexado:
                            nomes.add(indexado)
            elif isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)                     and no.func.attr in self.MUTADORES:
                dono = self._self_attr(no.func.value)
                if dono:
                    nomes.add(dono)
        return nomes

    def test_todo_estado_vazio_do_init_tem_quem_escreva(self):
        import ast
        import pathlib

        vazios = (ast.Dict, ast.List, ast.Set)
        orfaos = []
        for arquivo in sorted(pathlib.Path("painel/paginas").glob("*.py")):
            if arquivo.name == "__init__.py":
                continue
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            for classe in [n for n in ast.walk(arvore)
                           if isinstance(n, ast.ClassDef)]:
                inits = [n for n in classe.body if isinstance(n, ast.FunctionDef)
                         and n.name == "__init__"]
                outros = [n for n in classe.body if isinstance(n, ast.FunctionDef)
                          and n.name != "__init__"]
                nascidos = set()
                for init in inits:
                    for no in ast.walk(init):
                        if not isinstance(no, (ast.Assign, ast.AnnAssign)):
                            continue
                        alvo = (no.targets[0] if isinstance(no, ast.Assign)
                                and len(no.targets) == 1 else
                                getattr(no, "target", None))
                        nome = self._self_attr(alvo) if alvo is not None else None
                        valor = no.value
                        if nome and isinstance(valor, vazios)                                 and not getattr(valor, "elts", None)                                 and not getattr(valor, "keys", None):
                            nascidos.add(nome)
                if not nascidos:
                    continue
                lidos = set()
                for metodo in outros:
                    for no in ast.walk(metodo):
                        nome = self._self_attr(no)
                        if nome and isinstance(no.ctx, ast.Load):
                            lidos.add(nome)
                escritos = set()
                for metodo in outros:
                    escritos |= self._escritos(metodo)
                for nome in sorted(nascidos & lidos):
                    if nome not in escritos:
                        orfaos.append(f"{arquivo.name}:{classe.name}.{nome}")
        self.assertEqual([], orfaos,
                         "estado lido que nenhuma tela escreve (funcao perdida "
                         "na reescrita?): " + ", ".join(orfaos))


class WidgetSemTelaTests(unittest.TestCase):
    """Widget criado e nunca colocado na tela = tela que monta e nao mostra.

    `Oficina.tabela` CRIA o Treeview e devolve; quem monta e que empacota.
    A pagina Espelho nasceu (02/09/2026) sem o `.pack()`: ela subia inteira,
    com os quatro grupos de botoes, e a lista de canais simplesmente nao
    existia. Nenhum teste viu — o smoke prova que a pagina MONTA, nao que os
    widgets estao visiveis, e foi preciso alguem abrir o painel para notar.

    O mesmo vale para `grid` e `place`: o que se cobra e que o widget tenha
    UM gerenciador de geometria, nao qual.
    """

    COLOCAM = ("pack", "grid", "place")
    # Fabricas da Oficina que devolvem o widget sem coloca-lo.
    SOLTAS = ("tabela",)

    @staticmethod
    def _self_attr(no):
        import ast
        if isinstance(no, ast.Attribute) and isinstance(no.value, ast.Name) \
                and no.value.id == "self":
            return no.attr
        return None

    @classmethod
    def _fabricados(cls, corpo) -> dict:
        """{atributo: linha} dos `self.x = self.o.<fabrica>(...)`."""
        import ast
        achados = {}
        for no in ast.walk(corpo):
            if not isinstance(no, ast.Assign) or not isinstance(no.value, ast.Call):
                continue
            chamada = no.value.func
            if not isinstance(chamada, ast.Attribute) \
                    or chamada.attr not in cls.SOLTAS:
                continue
            for alvo in no.targets:
                nome = cls._self_attr(alvo)
                if nome:
                    achados[nome] = no.lineno
        return achados

    @classmethod
    def _colocados(cls, corpo) -> set:
        """Os `self.x.pack(...)` / `.grid(...)` / `.place(...)`."""
        import ast
        postos = set()
        for no in ast.walk(corpo):
            if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Attribute):
                continue
            if no.func.attr not in cls.COLOCAM:
                continue
            nome = cls._self_attr(no.func.value)
            if nome:
                postos.add(nome)
        return postos

    def test_toda_tabela_criada_e_colocada_na_tela(self):
        import ast

        orfas = []
        for arquivo in sorted(pathlib.Path("painel/paginas").glob("*.py")):
            if arquivo.name == "__init__.py":
                continue
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            for classe in [n for n in ast.walk(arvore)
                           if isinstance(n, ast.ClassDef)]:
                fabricados = self._fabricados(classe)
                if not fabricados:
                    continue
                postos = self._colocados(classe)
                for nome, linha in sorted(fabricados.items()):
                    if nome not in postos:
                        orfas.append(f"{arquivo.name}:{linha} "
                                     f"{classe.name}.{nome}")
        self.assertEqual([], orfas,
                         "tabela criada e nunca empacotada (a pagina monta e "
                         "a lista nao aparece): " + ", ".join(orfas))

    @classmethod
    def _textos_de_tag(cls, no) -> set:
        """Os nomes de tag de `tags=...`, sem varrer a expressao inteira.

        Um `ast.walk` cru aqui da FALSO POSITIVO: em
        `tags=("ok" if linha["logado"] else "falta",)` ele acha tres textos e
        acusa `logado`, que e chave de dicionario, nao tag. So contam as
        posicoes onde um nome de tag pode mesmo estar.
        """
        import ast
        if isinstance(no, ast.Constant):
            return {no.value} if isinstance(no.value, str) else set()
        if isinstance(no, (ast.Tuple, ast.List, ast.Set)):
            return set().union(*(cls._textos_de_tag(e) for e in no.elts)) \
                if no.elts else set()
        if isinstance(no, ast.IfExp):          # o teste do ternario nao conta
            return cls._textos_de_tag(no.body) | cls._textos_de_tag(no.orelse)
        return set()

    def test_as_tags_que_a_pagina_usa_foram_configuradas(self):
        """Tag aplicada e nunca configurada nao pinta nada — some em silencio."""
        import ast

        problemas = []
        for arquivo in sorted(pathlib.Path("painel/paginas").glob("*.py")):
            if arquivo.name == "__init__.py":
                continue
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            usadas, configuradas = set(), set()
            for no in ast.walk(arvore):
                if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Attribute):
                    continue
                if no.func.attr == "tag_configure" and no.args:
                    if isinstance(no.args[0], ast.Constant):
                        configuradas.add(no.args[0].value)
                if no.func.attr == "insert":
                    for chave in no.keywords:
                        if chave.arg == "tags":
                            usadas |= self._textos_de_tag(chave.value)
            for tag in sorted(usadas - configuradas):
                problemas.append(f"{arquivo.name}: tag '{tag}'")
        self.assertEqual([], problemas,
                         "tag usada na tabela e nunca configurada: "
                         + ", ".join(problemas))


class ComandosDaUITests(unittest.TestCase):
    """Todo botao que dispara CLI tem que passar pelo argparse de verdade.

    Os botoes Recategorizar e Remover da pagina Reacoes mandavam
    `main.py reactions --recategorizar/--remover` para um subcomando que nao
    aceitava bandeira NENHUMA, e o importador mandava `--mover` para um
    parser que so conhecia `--move`. Clicar nao fazia nada e nada avisava:
    o argparse recusa no subprocesso, e o erro morria no console.
    """

    # Qual `main.py` cada pagina dispara. Ate 02/09/2026 as paginas que
    # falavam com outra CLI eram ISENTAS deste teste — e isento e nao
    # testado: uma bandeira errada nelas continuaria morrendo no console,
    # que e exatamente o defeito que este teste existe para pegar.
    CLI_DA_PAGINA = {"historias.py": "historias", "mimetizar.py": "mimetizar"}
    CLI_PADRAO = "random_builds"

    @classmethod
    def _choices_do_provedor(cls) -> dict:
        """{subcomando: choices de --provedor} do `random_builds/main.py`."""
        import argparse
        parser = cls._parser_do_cli("random_builds")
        if parser is None:
            return {}
        saida = {}

        def andar(p, prefixo):
            for acao in p._actions:
                if isinstance(acao, argparse._SubParsersAction):
                    for nome, sub in acao.choices.items():
                        andar(sub, f"{prefixo} {nome}".strip())
                elif "--provedor" in acao.option_strings and acao.choices:
                    saida[prefixo] = tuple(acao.choices)
        andar(parser, "")
        return saida

    @staticmethod
    def _flags_do_cli(projeto: str = "random_builds") -> dict:
        """{subcomando: {bandeiras aceitas}} lendo o argparse REAL."""
        import argparse
        parser = ComandosDaUITests._parser_do_cli(projeto)
        if parser is None:
            return {}
        mapa = {}
        for acao in parser._actions:
            if not isinstance(acao, argparse._SubParsersAction):
                continue
            for nome, sub in acao.choices.items():
                flags = {o for a in sub._actions for o in a.option_strings}
                aninhados = [a for a in sub._actions
                             if isinstance(a, argparse._SubParsersAction)]
                for a in aninhados:
                    for filho, spf in a.choices.items():
                        mapa[f"{nome} {filho}"] = {
                            o for ac in spf._actions for o in ac.option_strings}
                mapa[nome] = flags
        return mapa

    @staticmethod
    def _parser_do_cli(projeto: str = "random_builds"):
        """O `ArgumentParser` REAL do `main.py` do projeto (ou None)."""
        import argparse
        import runpy
        import sys

        capturado = {}
        original = argparse.ArgumentParser.parse_args

        def espiao(self, *a, **k):
            capturado["parser"] = self
            raise SystemExit(0)

        raiz = pathlib.Path(__file__).resolve().parents[1] / projeto
        if not (raiz / "main.py").is_file():
            return None
        argv, cwd = sys.argv, os.getcwd()
        argparse.ArgumentParser.parse_args = espiao
        sys.argv = ["main.py", "--help"]
        os.chdir(raiz)
        try:
            runpy.run_path(str(raiz / "main.py"), run_name="__main__")
        except SystemExit:
            pass
        finally:
            argparse.ArgumentParser.parse_args = original
            sys.argv, _ = argv, os.chdir(cwd)

        return capturado.get("parser")

    DISPAROS = ("rodar", "_rb", "rb", "_rodar")

    @classmethod
    def _resolver(cls, no, locais: dict):
        """Reduz uma expressao a uma lista de textos, quando da.

        Precisa existir porque quase nenhum comando do painel e um literal
        no ponto da chamada: o normal e `argumentos = [...]`, um `append`
        condicional, e `self.rb(argumentos + entrada)`. Olhando so o
        literal, o disparo do importador era INVISIVEL — foi assim que
        `--mover` contra um CLI que so aceitava `--move` passou batido.
        """
        import ast
        if isinstance(no, ast.Constant):
            return [str(no.value)]
        if isinstance(no, (ast.List, ast.Tuple)):
            saida = []
            for elemento in no.elts:
                saida.extend(cls._resolver(elemento, locais) or ["?"])
            return saida
        if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
            return ((cls._resolver(no.left, locais) or ["?"])
                    + (cls._resolver(no.right, locais) or ["?"]))
        if isinstance(no, ast.Name):
            return list(locais.get(no.id, ["?"]))
        if isinstance(no, ast.IfExp):
            return cls._resolver(no.body, locais) or ["?"]
        return ["?"]

    @classmethod
    def _comandos_da_funcao(cls, func) -> list:
        import ast
        locais: dict = {}
        for no in ast.walk(func):
            if isinstance(no, ast.Assign) and len(no.targets) == 1                     and isinstance(no.targets[0], ast.Name):
                locais[no.targets[0].id] = cls._resolver(no.value, locais)
            elif isinstance(no, ast.AugAssign) and isinstance(no.target, ast.Name)                     and isinstance(no.op, ast.Add):
                locais.setdefault(no.target.id, []).extend(
                    cls._resolver(no.value, locais))
            elif isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)                     and no.func.attr in ("append", "extend")                     and isinstance(no.func.value, ast.Name) and no.args:
                locais.setdefault(no.func.value.id, []).extend(
                    cls._resolver(no.args[0], locais))
        saida = []
        for no in ast.walk(func):
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)                     and no.func.attr in cls.DISPAROS and no.args:
                saida.append(cls._resolver(no.args[0], locais))
        return saida

    def _comandos_do_painel(self):
        """(arquivo, subcomandos, bandeiras) de cada disparo com `main.py`."""
        import ast

        saida = []
        for arquivo in sorted(pathlib.Path("painel/paginas").glob("*.py")):
            if arquivo.name == "__init__.py":
                continue
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            for func in [n for n in ast.walk(arvore)
                         if isinstance(n, ast.FunctionDef)]:
                for textos in self._comandos_da_funcao(func):
                    if "main.py" not in textos:
                        continue
                    resto = textos[textos.index("main.py") + 1:]
                    partes = [t for t in resto
                              if not t.startswith("-") and t != "?"]
                    flags = [t for t in resto if t.startswith("--")]
                    if not partes:
                        continue
                    saida.append((arquivo.name, partes[:2], flags))
        return saida

    def test_toda_bandeira_que_a_ui_manda_e_aceita_pelo_cli(self):
        clis = {}
        problemas = []
        for arquivo, partes, flags in self._comandos_do_painel():
            projeto = self.CLI_DA_PAGINA.get(arquivo, self.CLI_PADRAO)
            if projeto not in clis:
                clis[projeto] = self._flags_do_cli(projeto)
            cli = clis[projeto]
            if not cli:
                problemas.append(f"{arquivo}: nao consegui ler o argparse "
                                 f"de {projeto}/main.py")
                continue
            sub = " ".join(partes)
            aceitas = cli.get(sub)
            if aceitas is None and partes:
                sub = partes[0]
                aceitas = cli.get(sub)
            if aceitas is None:
                problemas.append(f"{arquivo}: subcomando inexistente '{sub}'")
                continue
            for flag in flags:
                if flag not in aceitas:
                    problemas.append(f"{arquivo}: `{sub}` nao aceita {flag}")
        self.assertEqual([], problemas, "; ".join(problemas))


class SupervisorTests(unittest.TestCase):
    """Uma fila so, e so ela toca em `after`."""

    def setUp(self):
        self.raiz = tk.Tk()
        self.raiz.withdraw()
        self.linhas = []
        self.sup = Supervisor(self.raiz,
                              ao_registrar=lambda t, _c: self.linhas.append(t))
        self.addCleanup(self._fechar)

    def _fechar(self):
        self.sup.encerrar()
        self.raiz.destroy()

    def test_a_tarefa_entrega_na_thread_da_interface(self):
        import threading
        daqui = threading.get_ident()
        visto = {}

        def pronto(valor):
            visto["thread"] = threading.get_ident()
            visto["valor"] = valor

        self.sup.tarefa(lambda: 42, pronto)
        for _ in range(60):
            self.raiz.update()
            if "valor" in visto:
                break
            import time
            time.sleep(0.05)
        self.assertEqual(42, visto.get("valor"))
        self.assertEqual(daqui, visto.get("thread"),
                         "o callback rodou fora da thread da interface")

    def test_tarefa_que_estoura_vira_dicionario_de_erro(self):
        visto = {}

        def explode():
            raise RuntimeError("pegou fogo")

        self.sup.tarefa(explode, lambda v: visto.update(valor=v))
        for _ in range(60):
            self.raiz.update()
            if "valor" in visto:
                break
            import time
            time.sleep(0.05)
        self.assertIn("pegou fogo", str(visto.get("valor")))

    def test_callback_que_estoura_nao_derruba_o_laco(self):
        self.sup.tarefa(lambda: 1, lambda _v: 1 / 0)
        for _ in range(40):
            self.raiz.update()
            import time
            time.sleep(0.03)
        self.assertTrue(any("ZeroDivisionError" in l for l in self.linhas))


# Um filho inofensivo: so dorme. Nenhum teste daqui dispara comando do
# projeto (publicar, gerar, login) -- o que se prova e o supervisor.
DORME = ["-c", "import time; time.sleep({s})"]


class UmPorRotuloTests(unittest.TestCase):
    """PNL-1: o duplo clique em PUBLICAR abria DOIS processos.

    `main.py publicar` nao olha se ja publicou; o mesmo video podia subir
    duas vezes. Um rotulo vivo (nesta janela OU em outra do painel) recusa
    o segundo disparo, e o botao fica desligado enquanto o processo roda.
    """

    @classmethod
    def setUpClass(cls):
        # UM Tk para a classe: cada `tk.Tk()` a mais e mais uma chance de o
        # Tcl desta maquina falhar ao carregar (ver `conftest.py`).
        cls.raiz = tk.Tk()
        cls.raiz.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.raiz.destroy()

    def setUp(self):
        import sys
        import tempfile
        from painel.processos import Registro
        self.py = sys.executable
        self.pasta = tempfile.mkdtemp(prefix="nf-registro-")
        self.linhas = []
        self.sups = []
        self.botoes = []
        self.sup = self._supervisor(Registro(self.pasta))
        self.addCleanup(self._fechar)

    def _supervisor(self, registro):
        sup = Supervisor(self.raiz, registro=registro,
                         ao_registrar=lambda t, _c: self.linhas.append(t))
        self.sups.append(sup)
        return sup

    def _fechar(self):
        for sup in self.sups:
            sup.parar_tudo()
            sup.encerrar()
        for botao in self.botoes:
            botao.destroy()

    def _ate(self, condicao, limite=15.0):
        import time
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            self.raiz.update()
            if condicao():
                return True
            time.sleep(0.03)
        return False

    def _dorme(self, segundos):
        return [self.py] + [a.format(s=segundos) for a in DORME]

    def test_rotulo_vivo_nao_dispara_de_novo(self):
        self.assertTrue(self.sup.rodar(self._dorme(3), rotulo="x"))
        self.assertFalse(self.sup.rodar(self._dorme(3), rotulo="x"))
        self.assertEqual(1, self.sup.ativos)
        self.assertTrue(any("já está rodando" in l and "x" in l
                            for l in self.linhas), self.linhas)

    def test_outra_janela_tambem_recusa(self):
        """Duas janelas = dois supervisores; o que os une e a pasta."""
        from painel.processos import Registro
        outra = self._supervisor(Registro(self.pasta))
        self.assertTrue(self.sup.rodar(self._dorme(3), rotulo="publicar g1"))
        self.assertFalse(outra.rodar(self._dorme(3), rotulo="publicar g1"))
        self.assertEqual(0, outra.ativos)
        self.assertTrue(any("outra janela" in l for l in self.linhas))

    def test_rotulo_diferente_roda_junto(self):
        self.assertTrue(self.sup.rodar(self._dorme(3), rotulo="publicar g1"))
        self.assertTrue(self.sup.rodar(self._dorme(3), rotulo="publicar g2"))
        self.assertEqual(2, self.sup.ativos)

    def test_depois_de_acabar_pode_de_novo(self):
        self.assertTrue(self.sup.rodar(self._dorme(0), rotulo="x"))
        self.assertTrue(self._ate(lambda: any("terminou" in l
                                              for l in self.linhas)))
        self.assertFalse(self.sup.rodando("x"))
        self.assertTrue(self.sup.rodar(self._dorme(0), rotulo="x"))

    def test_ficha_de_processo_morto_nao_trava(self):
        """Painel que caiu deixa ficha; PID morto nao pode travar o botao."""
        import json
        import subprocess
        from painel.processos import Registro
        morto = subprocess.Popen(self._dorme(0))
        morto.wait()
        registro = Registro(self.pasta)
        registro.reservar("x")
        registro.gravar("x", morto.pid)
        arquivo = registro._arquivo("x")
        self.assertEqual(morto.pid,
                         json.loads(arquivo.read_text("utf-8"))["pid"])
        self.assertIsNone(registro.ocupado("x"))
        self.assertTrue(self.sup.rodar(self._dorme(0), rotulo="x"))

    def test_botao_fica_desligado_ate_o_fim(self):
        o = Oficina(estilo.OFICINA)
        botao = o.botao(self.raiz, "PUBLICAR",
                        lambda: self.sup.rodar(self._dorme(1),
                                               rotulo="publicar g1"))
        self.botoes.append(botao)
        botao.invoke()
        self.assertEqual("disabled", str(botao.cget("state")))
        self.assertTrue(self.sup.segura(botao))
        # Clicar de novo (o duplo clique) nao abre outro processo.
        botao.invoke()
        self.assertEqual(1, self.sup.ativos)
        self.assertTrue(self._ate(lambda: str(botao.cget("state"))
                                  == "normal"))
        self.assertFalse(self.sup.segura(botao))

    def test_botao_explicito_e_o_que_desliga(self):
        o = Oficina(estilo.OFICINA)
        alvo = o.botao(self.raiz, "alvo")
        self.botoes.append(alvo)
        self.sup.rodar(self._dorme(1), rotulo="y", botao=alvo)
        self.assertEqual("disabled", str(alvo.cget("state")))
        self.assertTrue(self._ate(lambda: str(alvo.cget("state"))
                                  == "normal"))

    def test_parar_mata_os_netos(self):
        """PNL-6: `kill()` deixava Chrome/ffmpeg orfaos."""
        import os as _os
        import subprocess
        import tempfile
        from painel.processos import processo_vivo
        arquivo = _os.path.join(tempfile.mkdtemp(), "neto.pid")
        codigo = (
            "import subprocess, sys, time\n"
            "neto = subprocess.Popen([sys.executable, '-c', "
            "'import time; time.sleep(60)'])\n"
            f"open({arquivo!r}, 'w').write(str(neto.pid))\n"
            "time.sleep(60)\n")
        self.sup.rodar([self.py, "-c", codigo], rotulo="pai")
        self.assertTrue(self._ate(lambda: _os.path.exists(arquivo)
                                  and open(arquivo).read().strip()))
        neto = int(open(arquivo).read())
        self.assertTrue(processo_vivo(neto))
        self.assertEqual(1, self.sup.parar_tudo())
        self.assertTrue(self._ate(lambda: not processo_vivo(neto), 10))
        if _os.name == "nt":
            lista = subprocess.run(
                ["tasklist", "/FI", f"PID eq {neto}", "/NH"],
                # `errors`: em pt-BR o tasklist responde em cp850
                # ("INFORMAÇÕES"), e com o PYTHONUTF8 do testar.py a leitura
                # quebrava e o stdout vinha None.
                capture_output=True, text=True, errors="replace").stdout
            self.assertNotIn(str(neto), lista)
        self.assertTrue(any("encerrei a árvore" in l for l in self.linhas))


class PeriodicoTests(unittest.TestCase):
    """O painel antigo tinha dois temporizadores que nunca paravam."""

    def setUp(self):
        self.raiz = tk.Tk()
        self.raiz.withdraw()
        self.addCleanup(self.raiz.destroy)

    def test_desligar_para_de_verdade(self):
        import time
        batidas = []
        p = Periodico(self.raiz, 10, lambda: batidas.append(1))
        p.ligar()
        for _ in range(20):
            self.raiz.update()
            time.sleep(0.01)
        quantas = len(batidas)
        self.assertGreater(quantas, 1)

        p.desligar()
        for _ in range(20):
            self.raiz.update()
            time.sleep(0.01)
        self.assertEqual(quantas, len(batidas), "continuou batendo depois de "
                                                "desligado")


class ExperimentosTests(unittest.TestCase):
    """A pagina de experimentos (11/09/2026).

    O que ela nao pode fazer e mentir: um braco com 20 videos e 2 medidos
    parece forte e nao e. Por isso `videos` e `medidos` sao colunas
    separadas, e nenhuma conta acontece aqui — tudo vem de
    `builds.experimentos`, para o numero da tela, o do Telegram e o da linha
    de comando serem o mesmo.
    """

    def setUp(self):
        import tempfile
        from pathlib import Path

        import builds.experimentos as X

        from painel.app import Casca
        from painel.paginas import experimentos

        self.X = X
        self._tmp = tempfile.TemporaryDirectory()
        raiz = Path(self._tmp.name)
        self._antes = (X.PASTA, X.REGISTRO, X.ATRIBUICOES)
        X.PASTA, X.REGISTRO = raiz, raiz / "experimentos.json"
        X.ATRIBUICOES = raiz / "atribuicoes.jsonl"

        self.app = Casca.criar([experimentos.Pagina])
        self.app.geometry("1366x740")
        self.app.update()
        self.pagina = self.app.paginas["experimentos"]
        self.addCleanup(self._fechar)

    def _fechar(self):
        self.X.PASTA, self.X.REGISTRO, self.X.ATRIBUICOES = self._antes
        self.app.encerrar()
        # As leituras de fundo seguram a janela: se acabarem depois do
        # destroy, o Tk e finalizado fora da thread principal e o processo
        # aborta. Espera, destroi e coleta AQUI.
        self.app.supervisor.aguardar(60)
        self.app.destroy()
        gc.collect()
        self._tmp.cleanup()

    def test_as_colunas_cabem_na_tela_dele(self):
        """1366 de largura menos a barra lateral. A tabela do Fluxo ja
        estourou isso uma vez, sem erro nenhum."""
        colunas = [("id", "ID", 82, "w"), ("nome", "NOME", 260, "w"),
                   ("canal", "CANAL", 88, "w"), ("tipo", "TIPO", 108, "w"),
                   ("estado", "ESTADO", 92, "w"),
                   ("bracos", "BRAÇOS", 70, "center"),
                   ("videos", "VÍDEOS", 70, "center"),
                   ("pergunta", "PERGUNTA", 300, "w")]
        self.assertTrue(self.pagina.o.largura_cabe(colunas, 1116))

    def test_o_placar_separa_quantos_entraram_de_quantos_foram_medidos(self):
        self.assertIn("videos", self.pagina.placar["columns"])
        self.assertIn("medidos", self.pagina.placar["columns"])

    def test_experimento_novo_aparece_na_lista(self):
        self.X.criar("Trilha", "muda?", "historias", [
            {"nome": "com", "ajuste": {"audio.trilha_procedural": True}},
            {"nome": "sem", "ajuste": {"audio.trilha_procedural": False}}])
        self.pagina.recarregar()
        self.app.update()
        linhas = self.pagina.lista.get_children()
        self.assertEqual(1, len(linhas))
        valores = self.pagina.lista.item(linhas[0])["values"]
        self.assertIn("Trilha", valores)
        self.assertIn("rascunho", valores)

    def test_sem_selecao_a_leitura_nao_inventa_numero(self):
        self.pagina.recarregar()
        self.app.update()
        self.assertIn("escolha", self.pagina.leitura.cget("text").lower())

    def test_braco_sem_metrica_diz_que_nao_tem_metrica(self):
        """O caso perigoso: o video foi produzido, entrou no braco, e a
        metrica ainda nao existe. Sem a nota a linha parece um zero medido."""
        from painel.paginas import experimentos as E
        nota = E._nota({"videos": 4, "medidos": 0})
        self.assertIn("nenhum vídeo medido", nota)
        parcial = E._nota({"videos": 4, "medidos": 1})
        self.assertIn("3 vídeo(s) ainda sem métrica", parcial)

    def test_valor_do_ajuste_vira_o_tipo_certo(self):
        """Gravar a string "false" onde o config espera False LIGA a trilha
        em vez de desligar, e o experimento mediria o oposto do que diz."""
        from painel.paginas import experimentos as E
        self.assertIs(False, E.interpretar("false"))
        self.assertIs(True, E.interpretar("TRUE"))
        self.assertEqual(12, E.interpretar("12"))
        self.assertEqual(0.26, E.interpretar("0.26"))
        self.assertEqual("itaraca.mp3", E.interpretar(" itaraca.mp3 "))

    def test_uma_linha_por_braco_com_chave_pontilhada(self):
        from painel.paginas import experimentos as E
        bracos = E.ler_bracos(
            "com trilha | audio.trilha_arquivo=itaraca.mp3, "
            "audio.music_volume=0.3\n"
            "# comentario\n"
            "sem trilha | audio.trilha_procedural=false\n")
        self.assertEqual(["com trilha", "sem trilha"],
                         [b["nome"] for b in bracos])
        self.assertEqual({"audio.trilha_arquivo": "itaraca.mp3",
                          "audio.music_volume": 0.3}, bracos[0]["ajuste"])
        self.assertIs(False, bracos[1]["ajuste"]["audio.trilha_procedural"])


class ConfiabilidadeTests(unittest.TestCase):
    """A pagina DESENHA o que `panorama.confiabilidade` entrega — e so."""

    FICHA = {
        "dia": "2026-09-16", "quando": "2026-09-16T16:41:25",
        "prometido": 3, "provado": 1, "sem_prova": 1, "sem_campo": 1,
        "fora_de_hd": 1, "barra_nao_entendida": 0,
        "valvula": [{"hora": "12:10", "marca": "titulo_repetido",
                     "alvo": "g1:build:celular:B", "motivo": "x"}],
        "conferencia": {"builds": {"estado": "falhou", "erro": "token"},
                        "historias": {"estado": "limpo", "casados": 4,
                                      "no_ledger": 4}},
        "alertas": ["1 publicação(ões) sem prova hoje"],
        "veredito": "atencao",
        "publicacoes": [
            {"hora": "09:40", "canal": "builds", "plataforma": "youtube",
             "video_id": "g1", "tem_laudo": True, "prova_ok": True,
             "qualidade": "processando"},
            {"hora": "09:38", "canal": "historias", "plataforma": "youtube",
             "video_id": "h12:p2", "tem_laudo": True, "prova_ok": False,
             "qualidade": "desconhecida"},
            {"hora": "06:37", "canal": "builds", "plataforma": "tiktok",
             "video_id": "g0", "tem_laudo": False, "prova_ok": None,
             "qualidade": ""},
        ],
    }

    def setUp(self):
        from painel.app import Casca
        from painel.paginas import confiabilidade

        self.app = Casca.criar([confiabilidade.Pagina])
        self.app.geometry("1366x740")
        self.app.update()
        # O pulso de 4 s le o panorama REAL e chama `atualizar`, que redesenha
        # por cima da FICHA: no CI (maquina lenta) ele caia no meio do teste
        # (alertas com 1 linha em vez de 2). Os testes do pulso chamam
        # `atualizar` direto; aqui ele fica desligado. A leitura de abertura
        # (`ao_mostrar`) termina e e entregue antes do teste comecar.
        self.app._pulso.desligar()
        if self.app._pulso_pipeline is not None:
            self.app._pulso_pipeline.desligar()
        self.app.supervisor.aguardar(60)
        self.app.update()
        self.pagina = self.app.paginas["confiabilidade"]
        self.addCleanup(self._fechar)

    def _fechar(self):
        self.app.encerrar()
        # As leituras de fundo seguram a janela: se acabarem depois do
        # destroy, o Tk e finalizado fora da thread principal e o processo
        # aborta. Espera, destroi e coleta AQUI.
        self.app.supervisor.aguardar(60)
        self.app.destroy()
        gc.collect()

    def test_desenha_a_ficha_inteira(self):
        self.pagina._desenhar(self.FICHA)
        self.assertIn("1/3", self.pagina.faixa.cget("text"))
        self.assertIn("⚠", self.pagina.faixa.cget("text"))
        linhas = self.pagina.tabela.get_children()
        self.assertEqual(3, len(linhas))
        etiquetas = [self.pagina.tabela.item(i, "tags")[0] for i in linhas]
        # O TERCEIRO ESTADO tem cor propria: sem laudo nao e reprovado.
        self.assertEqual(["provado", "sem_prova", "sem_laudo"], etiquetas)
        self.assertIn("não rodou",
                      self.pagina._cartoes["conferencia"].cget("text"))
        self.assertIn("abriu 1",
                      self.pagina._cartoes["valvula"].cget("text"))

    def test_mostra_as_falhas_das_duas_plataformas(self):
        self.pagina._desenhar(dict(self.FICHA, falhas_tiktok=2,
                                   falhas_youtube=1))
        texto = self.pagina._cartoes["provado"].cget("text")
        self.assertIn("TikTok 2", texto)
        self.assertIn("YouTube 1", texto)

    def test_ficha_sem_as_falhas_mostra_zero(self):
        # Ficha anterior a 3b07c4e nao tinha `falhas_youtube`.
        self.pagina._desenhar(self.FICHA)
        self.assertIn("YouTube 0",
                      self.pagina._cartoes["provado"].cget("text"))

    def test_desenhar_de_novo_nao_duplica_linhas(self):
        self.pagina._desenhar(self.FICHA)
        self.pagina._desenhar(self.FICHA)
        self.assertEqual(3, len(self.pagina.tabela.get_children()))

    def test_dia_limpo_diz_que_nada_esta_fora(self):
        limpo = dict(self.FICHA, alertas=[], veredito="ok")
        self.pagina._desenhar(limpo)
        self.assertIn("✓", self.pagina.faixa.cget("text"))

    def test_fonte_quebrada_vira_frase_e_nao_excecao(self):
        self.pagina._desenhar({"erro": "OSError: ledger ilegivel"})
        self.assertIn("não consegui ler", self.pagina.faixa.cget("text"))
        self.pagina._desenhar(None)
        self.pagina.atualizar({})

    def test_a_tabela_cabe_na_tela_dele(self):
        # A tela dele e 1366 de largura. A coluna VIDEO estica para ocupar o
        # que sobra, entao somar larguras mede o espaco OCUPADO, nao estouro:
        # o que importa e a borda direita da tabela nao passar da janela.
        self.pagina._desenhar(self.FICHA)
        self.app.update()
        tabela = self.pagina.tabela
        direita = tabela.winfo_rootx() + tabela.winfo_width()
        janela = self.app.winfo_rootx() + self.app.winfo_width()
        self.assertLessEqual(direita, janela)

    def test_os_botoes_ficam_na_tela_dele_mesmo_com_muito_alerta(self):
        # A pagina tem altura fixa e nao rola. Em 27/08/2026 botoes sumiram
        # abaixo da borda numa tela de 1366x768 sem erro nenhum.
        cheia = dict(self.FICHA, alertas=[f"alerta {n}" for n in range(8)])
        self.pagina._desenhar(cheia)
        self.app.update()
        acoes = self.pagina._acoes
        base = acoes.winfo_rooty() + acoes.winfo_height()
        janela = self.app.winfo_rooty() + self.app.winfo_height()
        self.assertTrue(acoes.winfo_ismapped())
        self.assertLessEqual(base, janela)

    def test_vem_logo_depois_da_auditoria(self):
        from painel import janelas
        from painel.paginas import auditoria, confiabilidade

        paginas = janelas._paginas_de_criacao()
        self.assertEqual([auditoria.Pagina, confiabilidade.Pagina],
                         paginas[:2])

    # --- PNL-3 e PNL-7: leitura que falha nao e dia calmo -----------------
    def test_ficha_vazia_nao_e_nada_fora_do_lugar(self):
        """ZERO: nada publicado hoje. Nao e verde, e nao e erro."""
        self.pagina._desenhar({})
        texto = self.pagina.faixa.cget("text")
        self.assertNotIn("nada fora do lugar", texto)
        self.assertNotIn("✓", texto)
        self.assertNotEqual(self.app.tema.ok, self.pagina.faixa.cget("fg"))

    def test_familia_ausente_e_falha_de_leitura(self):
        """FALHA: o panorama veio sem a familia. Antes: `{}` -> "✓ 0/0"."""
        from painel.paginas import confiabilidade
        with patch("panorama.resumo", return_value={"saude": {}}):
            self.assertIn("erro", confiabilidade._ler())
        self.pagina.atualizar({"saude": {}})
        self.assertIn("não consegui ler", self.pagina.faixa.cget("text"))
        self.assertEqual(self.app.tema.erro, self.pagina.faixa.cget("fg"))

    def test_panorama_ilegivel_chega_a_pagina(self):
        self.app._entregar_resumo({"erro": "OSError: X"})
        self.assertIn("não consegui ler", self.pagina.faixa.cget("text"))
        self.assertIn("ilegível", self.app._texto.get("1.0", "end"))

    def test_leitura_que_falha_diz_que_a_tela_e_velha(self):
        """Os cartoes ficam com a leitura anterior: o carimbo tem de dizer."""
        self.pagina._desenhar(self.FICHA)
        self.assertIn("16:41:25", self.pagina.carimbo.cget("text"))
        self.app._entregar_resumo({"erro": "OSError: X"})
        carimbo = self.pagina.carimbo.cget("text")
        self.assertIn("ANTERIOR", carimbo)
        self.assertIn("16:41:25", carimbo)
        self.assertEqual(self.app.tema.erro, self.pagina.carimbo.cget("fg"))
        self.pagina._desenhar(self.FICHA)                  # voltou a ler
        self.assertNotIn("ANTERIOR", self.pagina.carimbo.cget("text"))
        self.assertEqual(self.app.tema.texto_fraco,
                         self.pagina.carimbo.cget("fg"))

    def test_poucos_alertas_sem_barra(self):
        self.pagina._desenhar(dict(self.FICHA, alertas=["um", "dois"]))
        self.app.update()
        self.assertEqual(2, int(self.pagina.alertas.cget("height")))
        self.assertFalse(self.pagina._barra_alertas.winfo_ismapped())
        self.assertIn("dois", self.pagina.alertas.get("1.0", "end"))

    def test_conferencia_com_erro_aparece(self):
        """PNL-7: o erro da conferencia era jogado fora pelo callback."""
        def tarefa(_funcao, ao_pronto, rotulo=""):
            ao_pronto({"erro": "HttpError: token expirado"})
        with patch.object(self.app.supervisor, "tarefa", side_effect=tarefa):
            self.pagina.conferir()
        self.assertIn("token expirado", self.pagina.faixa.cget("text"))
        self.assertEqual(self.app.tema.erro, self.pagina.faixa.cget("fg"))
        self.assertIn("token expirado", self.app._texto.get("1.0", "end"))

    def test_conferencia_que_deu_certo_recarrega(self):
        chamadas = []

        def tarefa(_funcao, ao_pronto, rotulo=""):
            chamadas.append(rotulo)
            if rotulo == "conferencia":
                ao_pronto({"builds": {"estado": "limpo"}})
        with patch.object(self.app.supervisor, "tarefa", side_effect=tarefa):
            self.pagina.conferir()
        self.assertEqual(["conferencia", "confiabilidade"], chamadas)


class _CascaDe(unittest.TestCase):
    """Uma Casca com UMA pagina, fechada do jeito seguro."""

    MODULO = ""
    TAMANHO = "1366x740"

    def setUp(self):
        import importlib
        from painel.app import Casca
        modulo = importlib.import_module(f"painel.paginas.{self.MODULO}")
        self.app = Casca.criar([modulo.Pagina])
        self.app.geometry(self.TAMANHO)
        self.app.update()
        # A leitura de fundo do `ao_mostrar` chega DEPOIS e reescreve a
        # tela: espera ela assentar antes de o teste comecar a desenhar.
        import time
        self.app.supervisor.aguardar(30)
        fim = time.monotonic() + 10
        while not self.app.supervisor._fila.empty() \
                and time.monotonic() < fim:
            self.app.update()
            time.sleep(0.03)
        self.app.update()
        self.pagina = next(iter(self.app.paginas.values()))
        self.addCleanup(self._fechar)

    def _fechar(self):
        self.app.encerrar()
        self.app.supervisor.aguardar(60)
        self.app.destroy()
        gc.collect()

    def gaveta(self) -> str:
        return self.app._texto.get("1.0", "end")


class PlacarComErroTests(_CascaDe):
    """PNL-3: o `{"erro": ...}` do panorama virava "0 problema(s)" calmo."""

    MODULO = "vila"

    def test_panorama_ilegivel_nao_vira_placar_zero(self):
        """FALHA: a leitura inteira estourou."""
        self.app._entregar_resumo({"erro": "OSError: disco ocupado"})
        placar = self.pagina.lbl_placar.cget("text")
        self.assertNotIn("0 problema(s)", placar)
        self.assertNotIn("0 publicados", placar)
        self.assertIn("não consegui ler", placar)
        self.assertIn("disco ocupado", placar)
        self.assertEqual(self.app.tema.erro, self.pagina.lbl_placar.cget("fg"))
        self.assertIn("ilegível", self.gaveta())

    def test_o_mesmo_erro_nao_enche_a_gaveta(self):
        for _ in range(3):
            self.app._entregar_resumo({"erro": "OSError: disco ocupado"})
        self.assertEqual(1, self.gaveta().count("ilegível"))

    def test_dia_zerado_de_verdade_mostra_zero(self):
        """ZERO: tudo lido, nada aconteceu. Isso e 0, sem cor de erro."""
        self.app._entregar_resumo(_resumo_vazio())
        placar = self.pagina.lbl_placar.cget("text")
        self.assertIn("📤 0 publicados", placar)
        self.assertIn("0 problema(s)", placar)
        self.assertNotIn("não li", placar)
        self.assertEqual(self.app.tema.texto, self.pagina.lbl_placar.cget("fg"))

    def test_familia_que_falha_vira_interrogacao(self):
        """FALHA de uma familia so: as outras seguem, a dela vira "?"."""
        resumo = _resumo_vazio()
        resumo["desempenho"] = {"erro": "OSError: ledger trancado"}
        self.app._entregar_resumo(resumo)
        placar = self.pagina.lbl_placar.cget("text")
        self.assertIn("📤 ? publicados", placar)
        self.assertIn("0 problema(s)", placar)       # a qualidade foi lida
        self.assertIn("não li: desempenho", placar)
        self.assertEqual(self.app.tema.erro, self.pagina.lbl_placar.cget("fg"))

    def test_volta_ao_normal_depois_do_erro(self):
        self.app._entregar_resumo({"erro": "OSError: X"})
        self.app._entregar_resumo(_resumo_vazio())
        self.assertIn("0 publicados", self.pagina.lbl_placar.cget("text"))
        self.assertEqual(self.app.tema.texto, self.pagina.lbl_placar.cget("fg"))


class FluxoTests(_CascaDe):
    MODULO = "fluxo"

    def test_erro_sobrevive_ao_pulso(self):
        """PNL-16: o pulso de 4 s apagava o erro de leitura da tabela."""
        self.pagina._desenhar_tabela({"erro": "OSError: X"})
        self.pagina.atualizar(_resumo_vazio())
        self.app.update()
        self.assertIn("X", self.pagina._erro_leitura.cget("text"))
        self.assertTrue(self.pagina._erro_leitura.winfo_ismapped())
        # e o alerta seguinte nao herda a cor de erro
        resumo = _resumo_vazio()
        resumo["saude"] = {"alertas": ["fila parada"]}
        self.pagina.atualizar(resumo)
        self.assertEqual(self.app.tema.aviso, self.pagina._alerta.cget("fg"))

    def test_leitura_boa_limpa_o_erro(self):
        self.pagina._desenhar_tabela({"erro": "OSError: X"})
        self.pagina._desenhar_tabela({"geracoes": []})
        self.app.update()
        self.assertEqual("", self.pagina._erro_leitura.cget("text"))
        self.assertFalse(self.pagina._erro_leitura.winfo_ismapped())

    def test_cartao_zero_e_cartao_ilegivel(self):
        """ZERO = "0 na fila"; FALHA = "não consegui ler", nunca zero."""
        self.pagina.atualizar(_resumo_vazio())
        self.assertIn("0 na fila", self.pagina._cartoes["fila"].cget("text"))
        resumo = _resumo_vazio()
        resumo["saude"] = {"erro": "OSError: fila trancada"}
        self.pagina.atualizar(resumo)
        texto = self.pagina._cartoes["fila"].cget("text")
        self.assertNotIn("0 na fila", texto)
        self.assertIn("fila trancada", texto)
        self.app._entregar_resumo({"erro": "OSError: tudo"})
        self.assertIn("não consegui ler",
                      self.pagina._cartoes["arena"].cget("text"))


class PublicarTests(_CascaDe):
    MODULO = "publicar"

    def setUp(self):
        from painel.paginas import publicar
        # Sem ler o catalogo de verdade ao abrir a pagina.
        duble = patch.object(publicar.Pagina, "ao_mostrar", lambda _s: None)
        duble.start()
        self.addCleanup(duble.stop)
        super().setUp()

    def _escolher(self, fonte="builds"):
        item = {"id": "generation_00999:build:celular:A", "fonte": fonte,
                "origem": "build", "titulo": "t", "perfil": "celular",
                "caminho": "", "descricao": "", "pendencias": []}
        self.pagina._itens = {item["id"]: item}
        self.pagina.tabela.insert("", "end", iid=item["id"],
                                  values=("", "t", "9:16", "—", "—"))
        self.pagina.tabela.selection_set(item["id"])
        return item

    def _enviar(self, yt: bool, tt: bool, fonte="builds"):
        item = self._escolher(fonte)
        self.pagina.var_yt.set(yt)
        self.pagina.var_tt.set(tt)
        with patch.object(self.app.supervisor, "rodar",
                          return_value=True) as rodar:
            self.pagina.enviar()
        self.assertEqual(1, rodar.call_count)
        return item, rodar.call_args

    def test_tiktok_marcado_manda_postar(self):
        """PNL-2: a legenda diz que posta; o comando tem que dizer tambem."""
        item, chamada = self._enviar(yt=False, tt=True)
        argumentos = chamada.args[0]
        self.assertIn("--tiktok", argumentos)
        self.assertIn("--postar", argumentos)
        self.assertIn("posta de verdade",
                      " ".join(w.cget("text") for w in _rotulos(
                          self.pagina.btn_enviar.master)))
        self.assertEqual(f"publicar {item['id']}", chamada.kwargs["rotulo"])
        self.assertIs(self.pagina.btn_enviar, chamada.kwargs["botao"])

    def test_so_youtube_nao_manda_postar(self):
        _item, chamada = self._enviar(yt=True, tt=False)
        self.assertNotIn("--postar", chamada.args[0])

    def test_historia_nao_recebe_postar(self):
        """`historias/main.py publicar` ja posta e nao conhece `--postar`."""
        _item, chamada = self._enviar(yt=False, tt=True, fonte="historias")
        self.assertIn("--tiktok", chamada.args[0])
        self.assertNotIn("--postar", chamada.args[0])

    def test_postar_e_aceito_pelo_cli_de_builds(self):
        flags = ComandosDaUITests._flags_do_cli("random_builds")
        self.assertIn("--postar", flags.get("publicar", set()))

    def test_botao_preso_nao_volta_ao_trocar_a_selecao(self):
        """PNL-1: `pintar_botao` religava o PUBLICAR no meio do upload."""
        self._escolher()
        with patch.object(self.app.supervisor, "segura", return_value=True):
            self.pagina.pintar_botao()
        self.assertEqual("disabled", str(self.pagina.btn_enviar.cget("state")))
        self.pagina.pintar_botao()
        self.assertEqual("normal", str(self.pagina.btn_enviar.cget("state")))

    def test_publicando_tem_texto_e_cor_de_desligado(self):
        self._escolher()
        botao = self.pagina.btn_enviar
        with patch.object(self.app.supervisor, "segura", return_value=True):
            self.pagina.pintar_botao()
        self.assertIn("publicando", botao.cget("text"))
        self.assertEqual("disabled", str(botao.cget("state")))
        self.assertEqual(self.app.tema.superficie_alta, botao.cget("bg"))
        self.assertEqual(self.app.tema.texto_apagado,
                         botao.cget("disabledforeground"))
        self.pagina.pintar_botao()                         # acabou
        self.assertIn("PUBLICAR", botao.cget("text"))
        self.assertEqual(self.app.tema.acento, botao.cget("bg"))

    def test_historias_quebradas_avisam(self):
        """PNL-8: as historias sumiam da lista sem nenhuma linha de erro."""
        from painel.paginas import publicar
        with patch.object(publicar.catalogo_builds, "listar", return_value=[]), \
                patch("contos.publicar.catalogo.resumo",
                      side_effect=RuntimeError("catalogo x quebrado")), \
                patch.object(publicar.Pagina, "_publicados",
                             return_value={}):
            dados = self.pagina._ler()
        self.assertIn("avisos", dados)
        self.assertTrue(any("catalogo x quebrado" in a
                            for a in dados["avisos"]))
        self.pagina._desenhar(dados)
        self.app.update()
        self.assertIn("catalogo x quebrado",
                      self.pagina.lbl_aviso.cget("text"))
        self.assertTrue(self.pagina.lbl_aviso.winfo_ismapped())
        self.assertIn("histórias não carregaram", self.gaveta())

    def test_sem_aviso_o_rotulo_some(self):
        self.pagina._desenhar({"itens": [], "publicados": {}, "avisos": []})
        self.app.update()
        self.assertFalse(self.pagina.lbl_aviso.winfo_ismapped())


def _rotulos(pai):
    """Todos os Label dentro de `pai` (recursivo)."""
    saida = []
    for filho in pai.winfo_children():
        if filho.winfo_class() == "Label":
            saida.append(filho)
        saida.extend(_rotulos(filho))
    return saida


def _descendentes(pai):
    for filho in pai.winfo_children():
        yield filho
        yield from _descendentes(filho)


def _assentar(app, segundos: float) -> None:
    import time
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        app.update()
        time.sleep(0.03)


class CaminhoDoCliqueTests(unittest.TestCase):
    """PNL-5 pelo CAMINHO REAL (reprovado pelo conferente em 14/10/2026).

    A janela abre na Auditoria, ASSENTA, e so entao a pagina rolavel e
    mostrada -- como no clique do menu. Mostrar a pagina antes de a janela
    assentar (o que o teste antigo fazia) dava verde falso: a pagina
    montada cedo pedia 338 px, a janela do canvas ficava presa em 639 e a
    barra nunca aparecia quando ela crescia para 971.
    """

    TAMANHO = "1366x705"         # a Criacao maximizada na tela dele

    def _abrir(self, modulo_nome):
        import importlib
        from painel.app import Casca
        from painel.paginas import auditoria, publicar
        modulo = importlib.import_module(f"painel.paginas.{modulo_nome}")
        for classe in (auditoria.Pagina, publicar.Pagina):
            duble = patch.object(classe, "ao_mostrar", lambda _s: None)
            duble.start()
            self.addCleanup(duble.stop)
        app = Casca.criar([auditoria.Pagina, modulo.Pagina])
        app.geometry(self.TAMANHO)
        self.addCleanup(self._fechar, app)
        _assentar(app, 1.0)                   # a janela assenta na Auditoria
        self.assertEqual("auditoria", app._atual)
        app.mostrar(modulo.Pagina.chave)      # o mesmo que o clique faz
        _assentar(app, 1.5)
        return app, app.paginas[modulo.Pagina.chave]

    @staticmethod
    def _fechar(app):
        app.encerrar()
        app.supervisor.aguardar(60)
        app.destroy()
        gc.collect()

    def _conferir_rolagem(self, app, pagina, *, precisa_rolar: bool):
        corpo = pagina.corpo
        tela = corpo.tela
        pedida, altura = corpo.winfo_reqheight(), tela.winfo_height()
        if precisa_rolar:
            self.assertGreater(pedida, altura,
                               "a pagina nao precisava rolar? (layout mudou)")
        regiao = [int(float(v)) for v in str(tela.cget("scrollregion")).split()]
        self.assertGreaterEqual(regiao[3], pedida, "scrollregion velha")
        barras = [w for w in tela.master.winfo_children()
                  if w.winfo_class() == "TScrollbar"]
        self.assertEqual(pedida > altura, bool(barras[0].winfo_ismapped()))
        if pedida <= altura:
            return
        # a RODA DO MOUSE sobre um rotulo da pagina rola ate o fim
        rotulo = next(w for w in _descendentes(corpo)
                      if w.winfo_class() == "Label")
        for _ in range(80):
            if tela.yview()[1] >= 0.999:
                break
            rotulo.event_generate("<MouseWheel>", delta=-120, when="now")
            app.update()
        self.assertGreaterEqual(tela.yview()[1], 0.999, tela.yview())
        app.update()
        base = tela.winfo_rooty() + altura
        for tabela in (w for w in _descendentes(corpo)
                       if w.winfo_class() == "Treeview"):
            self.assertEqual(1, tabela.winfo_ismapped())
            self.assertGreater(tabela.winfo_height(), 60)
            self.assertLessEqual(tabela.winfo_rooty() + tabela.winfo_height(),
                                 base + 1)

    def test_videos_rola_pelo_clique(self):
        app, pagina = self._abrir("videos")
        self._conferir_rolagem(app, pagina, precisa_rolar=True)

    def test_publicar_pelo_clique(self):
        app, pagina = self._abrir("publicar")
        self._conferir_rolagem(app, pagina, precisa_rolar=False)
        # com a gaveta do console aberta, a mesma pagina tem de rolar
        app._abrir_console()
        _assentar(app, 0.8)
        self._conferir_rolagem(app, pagina, precisa_rolar=True)

    def test_historias_pelo_clique(self):
        app, pagina = self._abrir("historias")
        self._conferir_rolagem(app, pagina, precisa_rolar=False)
        app._abrir_console()
        _assentar(app, 0.8)
        self._conferir_rolagem(app, pagina, precisa_rolar=True)

    def test_confiabilidade_com_14_alertas_mantem_a_tabela(self):
        """Com os dados de 14/10 (14 alertas) a tabela ia a 4 px."""
        app, pagina = self._abrir("confiabilidade")
        ficha = dict(ConfiabilidadeTests.FICHA,
                     alertas=[f"alerta numero {n} com um texto de tamanho "
                              "parecido com o de verdade" for n in range(14)])
        pagina._desenhar(ficha)
        _assentar(app, 0.8)
        tabela = pagina.tabela
        self.assertEqual(1, tabela.winfo_ismapped())
        self.assertGreaterEqual(tabela.winfo_height(),
                                tabela.winfo_reqheight() - 2)
        from painel.paginas.confiabilidade import ALERTAS_VISIVEIS
        self.assertEqual(ALERTAS_VISIVEIS,
                         int(pagina.alertas.cget("height")))
        self.assertTrue(pagina._barra_alertas.winfo_ismapped())
        # e a tabela inteira cabe na tela, sem rolar
        tela = pagina.corpo.tela
        self.assertLessEqual(tabela.winfo_rooty() + tabela.winfo_height(),
                             tela.winfo_rooty() + tela.winfo_height() + 1)
        self._conferir_rolagem(app, pagina, precisa_rolar=False)



class RolavelTests(unittest.TestCase):
    """`Oficina.rolavel`: rola so quando nao cabe, e estica quando cabe."""

    @classmethod
    def setUpClass(cls):
        cls.janela = tk.Tk()
        cls.janela.geometry("600x400")

    @classmethod
    def tearDownClass(cls):
        cls.janela.destroy()

    def setUp(self):
        self.raiz = tk.Frame(self.janela)
        self.raiz.pack(fill="both", expand=True)
        self.addCleanup(self.raiz.destroy)
        self.o = Oficina(estilo.OFICINA)

    def test_com_espaco_sobrando_nao_rola_e_estica(self):
        corpo = self.o.rolavel(self.raiz)
        caixa = tk.Frame(corpo, height=50, bg="red")
        caixa.pack(fill="both", expand=True)
        self.raiz.update()
        self.assertEqual((0.0, 1.0), tuple(corpo.tela.yview()))
        # `expand` continua valendo: a caixa ocupa a altura toda
        self.assertGreater(caixa.winfo_height(), 300)

    def test_conteudo_que_cresce_depois_ganha_a_barra(self):
        """O defeito do caminho real: assentou pequeno, cresceu depois, e
        nenhum <Configure> chegava (a janela do canvas tem altura fixa)."""
        corpo = self.o.rolavel(self.raiz)
        tk.Label(corpo, text="pouco").pack()
        _assentar(self.janela, 0.5)
        self.assertEqual((0.0, 1.0), tuple(corpo.tela.yview()))
        for _ in range(30):
            tk.Label(corpo, text="linha que chegou depois").pack()
        _assentar(self.janela, 0.6)
        regiao = [int(float(v)) for v in
                  str(corpo.tela.cget("scrollregion")).split()]
        self.assertGreaterEqual(regiao[3], corpo.winfo_reqheight())
        self.assertLess(corpo.tela.yview()[1], 1.0)

    def test_sem_espaco_rola_ate_o_fim(self):
        corpo = self.o.rolavel(self.raiz)
        for _ in range(30):
            tk.Label(corpo, text="linha").pack()
        fim = tk.Label(corpo, text="FIM")
        fim.pack()
        self.raiz.update()
        self.assertLess(corpo.tela.yview()[1], 1.0)
        corpo.tela.yview_moveto(1.0)
        self.raiz.update()
        base = corpo.tela.winfo_rooty() + corpo.tela.winfo_height()
        self.assertLessEqual(fim.winfo_rooty() + fim.winfo_height(), base + 1)


class TamanhoInicialTests(unittest.TestCase):
    """PNL-4: a janela nascia no `minsize` (1000x600) e cortava botoes."""

    def test_abre_do_tamanho_da_tela(self):
        from painel import janelas
        from painel.paginas import auditoria
        with patch.object(auditoria.Pagina, "ao_mostrar", lambda _s: None):
            app = janelas.montar("criacao")
        try:
            app.update()
            self.assertTrue(app.state() == "zoomed"
                            or app.winfo_width() >= 1300,
                            f"{app.winfo_width()}x{app.winfo_height()} "
                            f"({app.state()})")
            # Quem pede tamanho (a --prova, os testes) ganha o que pediu.
            # `maxsize` da tela dele: no Windows o Tk limita a janela ao
            # tamanho da tela, e no runner do GitHub (1024x768) o pedido de
            # 1200 virava 1024 (CI 38625290567).
            app.maxsize(1366, 768)
            app.geometry("1200x650")
            app.update()
            self.assertEqual("normal", app.state())
            self.assertEqual(1200, app.winfo_width())
        finally:
            app.encerrar()
            app.supervisor.aguardar(60)
            app.destroy()
            gc.collect()


class ReacoesTests(unittest.TestCase):
    def test_lista_le_o_catalogo_da_pasta_de_assets(self):
        """`list_reactions` exige a pasta desde 53155b1; sem ela, TypeError."""
        import json
        import tempfile
        from painel.paginas import extras
        raiz = pathlib.Path(tempfile.mkdtemp(prefix="nf-reacoes-"))
        pasta = raiz / "assets" / "reactions"
        pasta.mkdir(parents=True)
        (pasta / "catalog.json").write_text(json.dumps({
            "next_id": 2, "reactions": [
                {"id": "r1", "category": "good", "duration": 2.5,
                 "source": "x.mp4"}]}), encoding="utf-8")
        with patch.object(extras, "RANDOM_BUILDS", raiz):
            linhas = extras.Reacoes._ler()
        self.assertEqual([("r1", "good", "2.5s", "x.mp4")], linhas)

    def test_pasta_sem_catalogo_e_lista_vazia(self):
        import tempfile
        from painel.paginas import extras
        with patch.object(extras, "RANDOM_BUILDS",
                          pathlib.Path(tempfile.mkdtemp())):
            self.assertEqual([], extras.Reacoes._ler())


class ContasTests(unittest.TestCase):
    def _entrar(self, servico):
        from unittest.mock import MagicMock

        from painel.paginas import contas
        pagina = contas.Pagina.__new__(contas.Pagina)
        pagina.tabela = MagicMock()
        pagina.tabela.selection.return_value = [f"{servico}|historias"]
        pagina.combo = MagicMock()
        pagina.combo.get.return_value = "principal"
        with patch.object(contas.contas_reg, "ativa",
                          return_value="principal"), \
                patch.object(contas.Pagina, "_abrir") as abrir, \
                patch.object(contas.messagebox, "showinfo") as aviso:
            pagina.entrar()
        return abrir, aviso

    def test_grok_vai_para_llm_login(self):
        """PNL-15: o grok caia no `identity login`, que o recusa."""
        from painel.paginas import contas
        abrir, _aviso = self._entrar("grok")
        self.assertEqual(1, abrir.call_count)
        argumentos, cwd = abrir.call_args.args[0], abrir.call_args.args[1]
        self.assertEqual(["main.py", "llm", "login", "--provedor", "grok"],
                         argumentos)
        self.assertEqual(contas.HISTORIAS, cwd)

    def test_os_logins_do_llm_sao_os_do_cli(self):
        from painel.paginas import contas
        parser = ComandosDaUITests._parser_do_cli("historias")
        self.assertIsNotNone(parser)
        import argparse
        escolhas = None
        for acao in parser._actions:
            if isinstance(acao, argparse._SubParsersAction):
                llm = acao.choices.get("llm")
                for sub in llm._actions:
                    if "--provedor" in sub.option_strings:
                        escolhas = tuple(sub.choices)
        self.assertEqual(set(escolhas), set(contas.LOGIN_PELO_LLM))

    def test_servico_sem_login_avisa_em_vez_de_disparar(self):
        abrir, aviso = self._entrar("servico_inventado")
        self.assertEqual(0, abrir.call_count)
        self.assertEqual(1, aviso.call_count)

    def test_identity_continua_indo_para_identity(self):
        abrir, _aviso = self._entrar("digen")
        self.assertEqual(["main.py", "identity", "login", "--provedor",
                          "digen", "--canal", "historias"],
                         abrir.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
