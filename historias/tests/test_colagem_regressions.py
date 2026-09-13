# -*- coding: utf-8 -*-
"""A imagem e UMA cena, ou virou colagem? (11/09/2026)

O prompt negativo diz "no collage, no split screen" em toda cena, e o modelo
ignora. Varridas as 440 imagens do disco, 44 eram colagem: painel de cima e
de baixo, grade 2x2, tela dividida ao meio com pessoas diferentes em cada
lado. Num video vertical cada painel fica com menos de metade da altura, e a
cena seguinte volta a ser inteira — a historia pisca entre dois formatos.

DUAS TENTATIVAS FALHARAM ANTES, e por isso este arquivo existe:

  1. Descontinuidade entre linhas vizinhas. Nao separa: uma colagem de dois
     paineis marcou 7,3 e uma foto boa marcou 8,4. Foto de interior e cheia
     de borda horizontal forte (batente, mesa, horizonte).
  2. Fracao de COLUNAS que saltam na mesma linha. Tambem nao separa: o
     caixilho de uma janela atravessa a imagem inteira e marcou 0,67, o mesmo
     que uma colagem de verdade.

O que separa e a CALHA — a faixa fina, lisa e destoante que o gerador desenha
ENTRE os paineis. Os numeros aqui vieram das imagens reais, e sao eles que
este arquivo protege.

    cd e:\\projetos\\historias
    python -m pytest tests/test_colagem_regressions.py -q
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from contos.imagens import composicao


class TelaSintetica:
    """Imagens montadas a mao: o teste nao pode depender do acervo, que muda."""

    @staticmethod
    def _ruido(tamanho, base):
        """Fundo com variacao HORIZONTAL, como uma foto de verdade.

        A primeira versao era cor chapada mais ruido: cada linha saia com
        desvio ~2 depois da reducao, e o detector via a imagem INTEIRA como
        uma faixa lisa so — larga demais para ser calha, entao nada era
        acusado, nem a calha de verdade que estava no meio. Foto real tem
        desvio de dezenas por linha, e e contra esse fundo que a calha se
        destaca.
        """
        largura, altura = tamanho
        # Manchas grandes, e nao gradiente: o gradiente varia em UM eixo so,
        # entao as linhas ficavam com desvio 11 (abaixo do limiar) e as
        # vizinhas da calha entravam na mesma faixa lisa, alargando-a ate ela
        # deixar de parecer calha. Foto tem estrutura nos dois eixos.
        manchas = Image.effect_noise((largura // 16, altura // 16), 90)
        manchas = manchas.resize(tamanho, Image.BICUBIC).convert("RGB")
        return Image.blend(manchas,
                           Image.effect_noise(tamanho, 40).convert("RGB"), 0.3)

    @classmethod
    def cena_unica(cls, tamanho=(1088, 1920)):
        return cls._ruido(tamanho, (90, 110, 130))

    # 22 px em 1088 de largura. As calhas reais medem de 1 a 6 px na escala
    # reduzida de 192 px, ou seja ~6 a 34 px no original — uma faixa de 6 px
    # no original vira menos de um pixel depois do downscale e se mistura ao
    # ruido, o que fez a primeira versao deste teste medir uma calha que nao
    # existia mais na imagem analisada.
    @classmethod
    def com_calha_horizontal(cls, largura=22, tamanho=(1088, 1920)):
        img = cls.cena_unica(tamanho)
        meio = tamanho[1] // 2
        faixa = Image.new("RGB", (tamanho[0], largura), (250, 250, 248))
        img.paste(faixa, (0, meio))
        return img

    @classmethod
    def com_calha_vertical(cls, largura=22, tamanho=(1088, 1920)):
        img = cls.cena_unica(tamanho)
        meio = tamanho[0] // 2
        faixa = Image.new("RGB", (largura, tamanho[1]), (250, 250, 248))
        img.paste(faixa, (meio, 0))
        return img

    @classmethod
    def com_parede_grossa(cls, tamanho=(1088, 1920)):
        """Um elemento LARGO e liso no meio (uma parede, um movel claro).
        Nao e calha: calha e fina."""
        img = cls.cena_unica(tamanho)
        faixa = Image.new("RGB", (tamanho[0], 260), (250, 250, 248))
        img.paste(faixa, (0, tamanho[1] // 2))
        return img

    @classmethod
    def com_faixa_na_borda(cls, tamanho=(1088, 1920)):
        """Divisoria de vidro rente a borda. Ela existe nas fotos boas e o
        'painel' que criaria teria 5% da tela — isso e moldura, nao colagem."""
        img = cls.cena_unica(tamanho)
        faixa = Image.new("RGB", (22, tamanho[1]), (250, 250, 248))
        img.paste(faixa, (int(tamanho[0] * 0.05), 0))
        return img


class DeteccaoTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _salvar(self, imagem, nome="cena.png") -> Path:
        alvo = self.pasta / nome
        imagem.save(alvo)
        return alvo

    def test_a_cena_unica_passa(self):
        self.assertFalse(composicao.e_colagem(
            self._salvar(TelaSintetica.cena_unica())))

    def test_calha_horizontal_e_colagem(self):
        self.assertTrue(composicao.e_colagem(
            self._salvar(TelaSintetica.com_calha_horizontal())))

    def test_calha_vertical_e_colagem(self):
        self.assertTrue(composicao.e_colagem(
            self._salvar(TelaSintetica.com_calha_vertical())))

    def test_faixa_larga_nao_e_calha(self):
        """Parede clara no meio da cena e cena, nao divisao."""
        self.assertFalse(composicao.e_colagem(
            self._salvar(TelaSintetica.com_parede_grossa())))

    def test_faixa_rente_a_borda_nao_e_calha(self):
        """Medido: uma divisoria de vidro a 94% da largura acusava colagem
        numa foto boa. O 'painel' teria 6% da tela."""
        self.assertFalse(composicao.e_colagem(
            self._salvar(TelaSintetica.com_faixa_na_borda())))

    def test_o_motivo_diz_onde_esta_a_calha(self):
        """A frase vai para o log e para a tela: 'parece colagem' sozinho
        obriga a abrir a imagem para saber do que se trata."""
        razao = composicao.motivo(
            self._salvar(TelaSintetica.com_calha_horizontal()))
        self.assertIn("colagem", razao)
        self.assertIn("linha", razao)
        self.assertIn("%", razao)

    def test_cena_boa_nao_tem_motivo(self):
        self.assertEqual("", composicao.motivo(
            self._salvar(TelaSintetica.cena_unica())))

    def test_arquivo_ilegivel_nao_vira_colagem(self):
        """Quem recusa arquivo quebrado e `fila.utilizavel`, pelo tamanho.
        Acusar colagem aqui esconderia a causa real."""
        quebrado = self.pasta / "quebrado.png"
        quebrado.write_bytes(b"nao sou png")
        self.assertFalse(composicao.e_colagem(quebrado))

    def test_arquivo_que_nao_existe_nao_explode(self):
        self.assertFalse(composicao.e_colagem(self.pasta / "sumiu.png"))


class LimiaresTests(unittest.TestCase):
    """Os numeros vieram das imagens reais; mexer neles sem medir e chute."""

    def test_a_calha_e_fina_por_definicao(self):
        self.assertLessEqual(composicao.CALHA_MAXIMA, 8,
                             "faixa mais grossa que isto e elemento da cena")

    def test_so_o_miolo_conta(self):
        comeco, fim = composicao.MIOLO
        self.assertGreaterEqual(comeco, 0.10)
        self.assertLessEqual(fim, 0.90)


class RefazerTests(unittest.TestCase):
    """Colagem se refaz com o MESMO prompt, e nao se suaviza."""

    def setUp(self):
        from contos.imagens import worker
        self.fonte = Path(worker.__file__).read_text(encoding="utf-8")

    def test_o_worker_confere_a_composicao_antes_de_registrar(self):
        registrar = self.fonte.index("fila.registrar(historia_id, n,\n"
                                     "                                       "
                                     "prompt=cliente.prompt_enviado")
        antes = self.fonte[:registrar]
        self.assertIn("composicao.motivo(destino)", antes,
                      "a colagem precisa ser vista ANTES de a cena virar "
                      "pronta, senao o worker nunca a refaz")

    def test_o_reenvio_usa_o_mesmo_prompt(self):
        trecho = self.fonte[self.fonte.index("composicao.motivo(destino)"):]
        trecho = trecho[:900]
        self.assertIn("cliente, tentativa, config", trecho,
                      "suavizar por causa de colagem pioraria a cena para "
                      "consertar o que nao era problema dela")

    def test_o_orcamento_de_refeitas_e_pequeno(self):
        from contos.imagens import worker
        self.assertLessEqual(worker.TENTATIVAS_DE_COMPOSICAO, 4,
                             "a conta do PicassoIA e compartilhada")
        self.assertGreaterEqual(worker.TENTATIVAS_DE_COMPOSICAO, 2)


if __name__ == "__main__":
    unittest.main()
