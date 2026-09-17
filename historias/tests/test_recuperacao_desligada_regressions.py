"""O interruptor da recuperacao do TikTok, e as quatro condicoes dele.

16/09/2026, a noite. A recuperacao de atrasados republicou no ar: a
`historia_00003` saiu da p01 a p06 e o Adrian viu o perfil cheio de blocos de
texto quase identico. A causa era de metodo: `atrasados_no_tiktok` pergunta
ao LEDGER quem ja foi ao TikTok, e o ledger NAO TEM as publicacoes antigas de
la — as feitas a mao, as da grade propria de 13-15/09. A fila leu "nunca foi"
sobre partes que estavam no ar havia dias.

As tres (recuperacao dos dois canais e reserva de builds) foram desligadas
juntas, e nao so a que foi pega: enquanto o ledger fosse cego, QUALQUER coisa
que dependesse dele para dizer "nunca foi" ia repetir.

RELIGADAS EM 17/09, depois de as quatro condicoes existirem:

  1. o ledger enxerga o passado (`conciliar_tiktok.py` importou o que faltava);
  2. teto de 2 por historia/geracao por dia, no perfil inteiro;
  3. rodizio entre fontes, para a fila nao esgotar uma serie;
  4. desfecho classificado: clique sem confirmacao sai da fila e espera
     conferencia, em vez de voltar e ser reenviado.

Este arquivo NAO trava o estado do interruptor — trava que ele FUNCIONA nas
duas posicoes, e que desligar significa parar de publicar sem parar de saber.
Travar o estado obrigaria a mexer no teste a cada virada, e um teste que se
edita junto com a mudanca nao protege de nada.
"""
import importlib.util
import unittest
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_interruptor", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class InterruptorTests(unittest.TestCase):
    def setUp(self):
        self.postar = _postar()
        self.postar._linha = lambda *_a, **_k: None

    def _desligar(self):
        self.postar.RECUPERACAO_LIGADA = False
        self.postar.RESERVA_LIGADA = False

    def test_desligada_nao_leva_ninguem_nos_dois_canais(self):
        self._desligar()
        for canal in ("historias", "builds"):
            with self.subTest(canal=canal):
                r = self.postar.recuperar_no_tiktok(canal=canal)
                self.assertFalse(r["feito"])
                self.assertEqual(0, r["fila"])
                self.assertIn("desligada", r.get("motivo", ""))

    def test_desligada_nem_monta_a_fila(self):
        """Nao e "monta e nao publica": e nao monta. Se a fila fosse montada,
        um erro dentro dela ainda apareceria com a chave em off."""
        self._desligar()
        chamou = []
        self.postar.atrasados_no_tiktok = lambda **_k: chamou.append(1) or []
        self.postar.recuperar_no_tiktok(canal="builds")
        self.assertEqual([], chamou)

    def test_reserva_desligada_nao_leva_ninguem(self):
        self._desligar()
        r = self.postar.publicar_da_reserva()
        self.assertFalse(r["feito"])
        self.assertEqual(0, r["reserva"])
        self.assertIn("desligada", r.get("motivo", ""))

    def test_so_ver_respeita_o_interruptor(self):
        """O `--ver` nao pode prometer o que a rodada nao vai fazer."""
        self._desligar()
        self.assertEqual(0, self.postar.recuperar_no_tiktok(so_ver=True)["fila"])
        self.assertEqual(0, self.postar.publicar_da_reserva(so_ver=True)["reserva"])

    def test_desligar_NAO_apaga_o_calculo_da_fila(self):
        """Desligar e parar de PUBLICAR, nao parar de saber. E dessas listas
        que sai o levantamento de quantos atrasados ja estao no TikTok — o
        trabalho que precisa ser feito justamente enquanto esta desligado."""
        self._desligar()
        self.assertIsInstance(
            self.postar.atrasados_no_tiktok(canal="builds"), list)
        self.assertIsInstance(self.postar.reserva_do_tiktok(), list)

    def test_ligada_volta_a_montar_a_fila(self):
        self.postar.RECUPERACAO_LIGADA = True
        chamou = []

        def fila(**_k):
            chamou.append(1)
            return []
        self.postar.atrasados_no_tiktok = fila
        self.postar.recuperar_no_tiktok(canal="builds")
        self.assertEqual([1], chamou)

    def test_as_duas_chaves_sao_independentes(self):
        """Desligar a reserva nao pode desligar a recuperacao, e vice-versa:
        elas foram desligadas juntas por precaucao, nao por acoplamento."""
        self.postar.RECUPERACAO_LIGADA = True
        self.postar.RESERVA_LIGADA = False
        self.assertIn("desligada",
                      self.postar.publicar_da_reserva().get("motivo", ""))
        self.postar.atrasados_no_tiktok = lambda **_k: []
        self.assertNotIn(
            "desligada",
            self.postar.recuperar_no_tiktok(canal="builds").get("motivo", ""))


if __name__ == "__main__":
    unittest.main()
