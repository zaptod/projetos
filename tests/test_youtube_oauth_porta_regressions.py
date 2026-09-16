# -*- coding: utf-8 -*-
"""O login do YouTube nao pode entregar o codigo a outro programa.

16/09/2026: um `python -m http.server 8765` esquecido segurava `[::]:8765`,
a ferramenta escutava `127.0.0.1:8765`, o redirect ia para "localhost", o
Chrome resolvia para `::1` — e o `?code=` foi parar no servidor esquecido,
que respondeu 200 com uma listagem de diretorio. Na tela, o login do Adrian
"tinha funcionado".

Nenhum caso abre socket de verdade nem navegador: `socket.socket`,
`webbrowser.open` e o servidor sao dublados.
"""
import socket
import unittest

from neural_fights.tools import youtube_oauth as Y


class _SocketFalso:
    """Imita so o que `porta_ocupada` usa."""

    ocupados_bind: set = set()
    atendendo: set = set()
    sem_familia: set = set()

    def __init__(self, familia, _tipo):
        if familia in self.sem_familia:
            raise OSError("familia indisponivel")
        self.familia = familia

    def settimeout(self, _s):
        pass

    def setsockopt(self, *_a):
        pass

    def connect_ex(self, alvo):
        return 0 if alvo[0] in self.atendendo else 10061

    def bind(self, alvo):
        if alvo[0] in self.ocupados_bind:
            raise OSError(10048, "endereco em uso")

    def close(self):
        pass


class PortaOcupada(unittest.TestCase):

    def _com(self, *, bind=(), atendendo=(), sem_familia=()):
        _SocketFalso.ocupados_bind = set(bind)
        _SocketFalso.atendendo = set(atendendo)
        _SocketFalso.sem_familia = set(sem_familia)
        real = Y.socket.socket
        Y.socket.socket = _SocketFalso
        self.addCleanup(lambda: setattr(Y.socket, "socket", real))
        return Y.porta_ocupada(8765)

    def test_porta_livre(self):
        self.assertEqual("", self._com())

    def test_o_caso_de_16_09_atendendo_no_ipv6(self):
        motivo = self._com(atendendo={"::1"})
        self.assertIn("::1:8765", motivo)

    def test_atendendo_no_ipv4(self):
        self.assertIn("127.0.0.1", self._com(atendendo={"127.0.0.1"}))

    def test_coringa_ipv6_reservado_e_pego_pelo_bind(self):
        # No Windows um bind em ::1 pode passar com [::] tomado: por isso o
        # coringa entra na lista.
        self.assertIn("::", self._com(bind={"::"}))

    def test_coringa_ipv4_reservado(self):
        self.assertIn("0.0.0.0", self._com(bind={"0.0.0.0"}))

    def test_maquina_sem_ipv6_nao_acusa_nada(self):
        self.assertEqual("", self._com(sem_familia={socket.AF_INET6}))


class OMainNaoAbreONavegador(unittest.TestCase):

    def setUp(self):
        self.abertos = []
        reais = (Y.webbrowser.open, Y.porta_ocupada, Y._receber_codigo,
                 Y.credenciais_do_app)
        Y.webbrowser.open = self.abertos.append
        Y.credenciais_do_app = lambda _destino: ("id", "segredo")

        def restaurar():
            (Y.webbrowser.open, Y.porta_ocupada, Y._receber_codigo,
             Y.credenciais_do_app) = reais

        self.addCleanup(restaurar)

    def test_porta_tomada_para_antes_do_consentimento(self):
        Y.porta_ocupada = lambda _p: "ja tem alguem atendendo em ::1:8765"
        codigo = Y.main(["--conta", "teste", "--out", "nao_grava.json"])
        self.assertEqual(3, codigo)
        self.assertEqual([], self.abertos,
                         "abrir o consentimento aqui entregaria o codigo "
                         "a outro programa")

    def test_o_retorno_vai_para_o_ip_e_nao_para_localhost(self):
        class Parou(Exception):
            pass

        def parar(_porta):
            raise Parou

        Y.porta_ocupada = lambda _p: ""
        Y._receber_codigo = parar
        with self.assertRaises(Parou):
            Y.main(["--conta", "teste", "--out", "nao_grava.json"])
        (url,) = self.abertos
        self.assertIn("redirect_uri=http%3A%2F%2F127.0.0.1%3A8765", url)
        self.assertNotIn("localhost", url)

    def test_host_configuravel_para_voltar_atras(self):
        self.assertEqual("http://localhost:9000",
                         Y.redirect_uri("localhost", 9000))
        args = Y.build_parser().parse_args(["--host", "localhost"])
        self.assertEqual("localhost", args.host)


if __name__ == "__main__":
    unittest.main()
