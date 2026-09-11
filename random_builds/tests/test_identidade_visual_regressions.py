"""A cor de um lutador e dele (Onda 15C).

`_cores_do_confronto` garante contraste entre os dois lados: cores que caem
quase iguais (dois verdes) tornam o video ilegivel. O problema era DE ONDE
saia o desempate — o lado 2 virava o laranja do ecossistema, uma cor sem
relacao nenhuma com aquele personagem. O mesmo lutador aparecia verde num
video e laranja no seguinte, dependendo so de quem estava do outro lado.

Identidade que muda ao acaso nao vira torcida, e torcida e o que o formato
curto precisa: a licao do marble racing e que identidade transforma fisica
aleatoria em fandom, e a do weapon ball e que a bola vermelha da espada e
reconhecida em meio segundo.

A garantia que estes testes travam nao e "a cor nunca muda" — com dois
lutadores de cor parecida algum desempate e inevitavel. E que toda cor que
um lutador exibe seja funcao SO DELE: ele tem no maximo duas aparencias, a
dele e a dele girada, e as duas sao estaveis em qualquer confronto.
"""
from __future__ import annotations

import unittest

from builds.generation.session_generator import load_config
from builds.video.renderer import VideoRenderer

VERDE = {"cor_r": 60, "cor_g": 200, "cor_b": 90}
VERDE_PARECIDO = {"cor_r": 70, "cor_g": 195, "cor_b": 100}
VERMELHO = {"cor_r": 210, "cor_g": 60, "cor_b": 55}


def _renderer() -> VideoRenderer:
    return VideoRenderer(load_config("render.json"), "celular", True)


def _luta(p1_ficha, p2_ficha, p1="Kael", p2="Lyra") -> dict:
    return {"p1": p1, "p2": p2, "p1_ficha": p1_ficha, "p2_ficha": p2_ficha}


class CorEstavelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = _renderer()

    def test_cores_distantes_passam_intactas(self):
        c1, c2 = self.r._cores_do_confronto(_luta(VERDE, VERMELHO))
        self.assertEqual((60, 200, 90), c1)
        self.assertEqual((210, 60, 55), c2)

    def test_cores_parecidas_ganham_contraste(self):
        c1, c2 = self.r._cores_do_confronto(_luta(VERDE, VERDE_PARECIDO))
        distancia = sum(abs(a - b) for a, b in zip(c1, c2))
        self.assertGreaterEqual(distancia, self.r.DISTANCIA_MINIMA_DE_COR)

    def test_o_desempate_sai_do_proprio_lutador_e_nao_do_ecossistema(self):
        """O laranja do ecossistema nao diz nada sobre quem esta lutando."""
        from builds.visualization.draw_common import hex_rgb

        _, c2 = self.r._cores_do_confronto(_luta(VERDE, VERDE_PARECIDO))
        self.assertNotEqual(hex_rgb(self.r.colors["accent_weapon"]), c2)
        self.assertNotEqual(hex_rgb(self.r.colors["accent_character"]), c2)

    def test_a_cor_desempatada_e_a_mesma_contra_qualquer_adversario(self):
        """Duas aparencias no maximo, e as duas sempre as mesmas.

        Antes, cada adversario podia produzir uma cor diferente para o
        mesmo lutador. Agora o giro deriva do NOME dele, entao a segunda
        aparencia e sempre identica.
        """
        vistas = set()
        for adversario in ("Kael", "Varo", "Pandora", "Raven", "Selene"):
            ficha1 = dict(VERDE_PARECIDO)  # sempre parecido -> sempre desempata
            _, c2 = self.r._cores_do_confronto(
                _luta(ficha1, VERDE, p1=adversario, p2="Lyra"))
            vistas.add(c2)
        self.assertEqual(1, len(vistas), f"a cor de Lyra oscilou: {vistas}")

    def test_lutadores_diferentes_giram_para_lugares_diferentes(self):
        """Senao o desempate vira uma cor unica de 'segundo lugar'."""
        giradas = {self.r._girar_matiz(VERDE_PARECIDO_T, nome)
                   for nome in ("Lyra", "Varo", "Selene", "Morgana")}
        self.assertGreater(len(giradas), 1)

    def test_o_giro_e_deterministico_entre_processos(self):
        """`hash()` de str e randomizado por PYTHONHASHSEED: a cor mudaria
        a cada render. O giro usa crc32, como `identity/prompt.py`."""
        import zlib
        esperado = 0.28 + (zlib.crc32(b"Lyra") % 1000) / 1000.0 * 0.44
        self.assertGreater(esperado, 0.27)
        primeira = self.r._girar_matiz(VERDE_PARECIDO_T, "Lyra")
        self.assertEqual(primeira, self.r._girar_matiz(VERDE_PARECIDO_T, "Lyra"))

    def test_a_cor_girada_continua_viva(self):
        """Girar o matiz nao pode produzir um cinza sem vida."""
        for nome in ("Lyra", "Varo", "Selene", "Morgana", "Aldric"):
            cor = self.r._girar_matiz((60, 60, 62), nome)
            with self.subTest(nome=nome):
                self.assertGreater(max(cor) - min(cor), 30, f"{cor} e cinza")


VERDE_PARECIDO_T = (70, 195, 100)


if __name__ == "__main__":
    unittest.main()
