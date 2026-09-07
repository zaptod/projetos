# -*- coding: utf-8 -*-
"""Contratos do painel novo. Sem abrir janela onde da para evitar.

Rode da raiz:
    python -m unittest painel.test_painel -v
"""
from __future__ import annotations

import os
import pathlib
import tkinter as tk
import unittest

from painel import estilo
from painel.processos import Periodico, Supervisor
from painel.widgets import Oficina


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
        self.app.destroy()

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
        self.app.destroy()

    def test_a_faixa_existe_na_janela_de_criacao(self):
        self.assertTrue(hasattr(self.app, "_pipeline_estado"))
        self.assertEqual(("tudo", "picasso", "digen"),
                         self.app._pipeline_alvo.cget("values"))

    def test_a_faixa_mostra_o_estado_lido_do_disco(self):
        self.app._entregar_pipeline(
            {"situacao": "pausado", "resumo": "pausado: tudo (emprestada)"})
        texto = self.app._pipeline_estado.cget("text")
        self.assertIn("pausado", texto)
        self.assertIn("⏸", texto)

    def test_estado_ilegivel_nao_derruba_a_faixa(self):
        self.app._entregar_pipeline(None)
        self.app._entregar_pipeline("qualquer coisa")

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

    @staticmethod
    def _flags_do_cli(projeto: str = "random_builds") -> dict:
        """{subcomando: {bandeiras aceitas}} lendo o argparse REAL."""
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
            return {}
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

        parser = capturado.get("parser")
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


if __name__ == "__main__":
    unittest.main()
