# -*- coding: utf-8 -*-
"""Contratos do painel novo. Sem abrir janela onde da para evitar.

Rode da raiz:
    python -m unittest painel.test_painel -v
"""
from __future__ import annotations

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
