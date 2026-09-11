# -*- coding: utf-8 -*-
"""A voz nao pode SUMIR no meio da fala.

Em 10/09/2026 ele disse: "o audio fica pipocando... e na voz, eu tenho
certeza, e e em todos os videos". Estava certo nas tres coisas, e a medicao
achou o numero: na parte 1 da `historia_00006`, **333 buracos de zero exato
entre 5 e 120 ms DENTRO da fala continua** — uns 2,6 por segundo. O ouvido
nao escuta "silencio": escuta o audio sumindo e voltando.

A causa estava no `respirar`, que existe para variar o tamanho das pausas. Ele
fatiava a narracao palavra a palavra e remontava assim:

    pedacos.append(pcm[t0:t1])                    # a palavra
    pedacos.append(np.zeros(silencio * taxa))     # o "entre"

O `entre` das palavras NAO E SILENCIO: e respiracao, ar da sala e a ligacao
entre um som e o outro. Troca-lo por zero absoluto e o que se ouvia.

QUATRO HIPOTESES FORAM TESTADAS E REJEITADAS antes desta, e vale registrar
para ninguem refazer o caminho: emenda dos segmentos de video (as bordas de
cena sao MAIS quietas que o resto, 241 contra 3560), degrau na emenda do
respiro (real, mas so 54->52 estalos), defeito daquela historia (ela era a
MAIS limpa das tres medidas) e buraco/bombeamento da musica (o unico silencio
estava no rabo do video).

O que este arquivo trava:

1. O AUDIO ENTRE AS PALAVRAS E PRESERVADO quando a pausa nao muda de tamanho.
2. QUANDO A PAUSA CRESCE, o zero entra no MIOLO — as bordas continuam sendo o
   audio de verdade, e a fala nunca encosta em zero absoluto.
3. QUANDO ENCOLHE, corta-se pelo miolo pelo mesmo motivo.
4. A RAMPA de 3 ms nas bordas que encostam em silencio, que derruba o degrau
   de 4000 para 31 (42 dB) sem a orelha perceber corte de fala.
"""
from __future__ import annotations

import unittest

import numpy as np

from builds.content import voz


class PausaComArTests(unittest.TestCase):
    def _entre(self, n=400, valor=50):
        return np.ones(n, dtype=np.int16) * valor

    def test_a_pausa_que_CRESCE_mantem_as_bordas_reais(self):
        p = voz._pausa_com_ar(self._entre(), 0.02, 44100, np.int16)
        self.assertEqual(882, len(p))
        self.assertEqual(50, int(p[0]), "a borda inicial virou zero")
        self.assertEqual(50, int(p[-1]), "a borda final virou zero")
        self.assertEqual(0, int(p[len(p) // 2]), "o miolo devia ser silencio")

    def test_a_pausa_que_ENCOLHE_corta_pelo_miolo(self):
        p = voz._pausa_com_ar(self._entre(), 0.005, 44100, np.int16)
        self.assertEqual(220, len(p))
        self.assertEqual(50, int(p[0]))
        self.assertEqual(50, int(p[-1]))

    def test_sem_material_sobra_o_silencio(self):
        """Nao ha o que preservar: e o unico caso em que zero e a resposta."""
        p = voz._pausa_com_ar(np.array([], dtype=np.int16), 0.01, 44100,
                              np.int16)
        self.assertEqual(441, len(p))
        self.assertFalse(bool(np.any(p)))


class TransicaoPreservadaTests(unittest.TestCase):
    """A transicao curta entre palavras da mesma frase nao se inventa."""

    def test_o_entre_das_palavras_NAO_vira_zero(self):
        taxa = 1000
        # duas palavras de 100 ms com 20 ms de "ar" entre elas (valor 7)
        pcm = np.concatenate([
            np.ones(100, dtype=np.int16) * 900,
            np.ones(20, dtype=np.int16) * 7,
            np.ones(100, dtype=np.int16) * 900,
        ])
        palavras = [{"t0": 0.0, "t1": 0.1, "texto": "um"},
                    {"t0": 0.12, "t1": 0.22, "texto": "dois"}]
        novo, _ = voz.respirar(pcm, palavras, taxa)
        # o trecho do "entre" tem que continuar existindo, e nao ser zero
        miolo = novo[100:120]
        self.assertTrue(bool(np.any(miolo)),
                        "o ar entre as palavras virou silencio digital")

    def test_a_fonte_nao_usa_mais_zeros_para_o_entre_curto(self):
        import inspect
        fonte = inspect.getsource(voz.respirar)
        trecho = fonte[fonte.index("natural < PAUSA_MINIMA_S"):]
        # o ramo da transicao curta preserva `entre`, nao fabrica silencio
        curto = trecho[:trecho.index("else:")]
        self.assertIn("pedacos.append(entre)", curto)
        self.assertNotIn("np.zeros", curto)


class RampaTests(unittest.TestCase):
    def test_o_degrau_vira_rampa(self):
        fala = np.ones(2000, dtype=np.int16) * -4000
        silencio = np.zeros(1000, dtype=np.int16)
        pedacos = [fala.copy(), silencio.copy()]
        antes = np.concatenate(pedacos)
        pico_antes = max(abs(int(antes[i]) - int(antes[i - 1]))
                         for i in range(1, len(antes)))
        voz._tirar_o_estalo(pedacos, 44100)
        depois = np.concatenate(pedacos)
        pico_depois = max(abs(int(depois[i]) - int(depois[i - 1]))
                          for i in range(1, len(depois)))
        self.assertEqual(4000, pico_antes)
        self.assertLess(pico_depois, 100, "o degrau continua audivel")

    def test_a_fala_CONTIGUA_nao_e_tocada(self):
        """Rampa no meio da frase viraria um afundamento."""
        a = np.ones(2000, dtype=np.int16) * 1000
        b = np.ones(2000, dtype=np.int16) * 1000
        pedacos = [a.copy(), b.copy()]
        voz._tirar_o_estalo(pedacos, 44100)
        self.assertTrue(bool(np.all(pedacos[0] == 1000)))
        self.assertTrue(bool(np.all(pedacos[1] == 1000)))

    def test_a_rampa_e_curta_o_bastante_para_nao_se_ouvir(self):
        self.assertLessEqual(voz.RAMPA_S, 0.005)
        self.assertGreater(voz.RAMPA_S, 0.001)


if __name__ == "__main__":
    unittest.main()
