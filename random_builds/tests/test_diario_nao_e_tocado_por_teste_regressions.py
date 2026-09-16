"""Nenhum teste pode escrever no `atividade.jsonl` de PRODUCAO.

16/09/2026, custou tempo de duas sessoes. Um teste meu chamava
`recuperar_no_tiktok` com dubles para o catalogo, para o publicador e para o
arquivo do contador — mas NAO para o diario. Entao
`_anotar_falha_no_tiktok` gravou de verdade:

    desisti do TikTok para trava:build:celular depois de 3 tentativas

`trava:build:celular` e um id de duble, que nao existe em lugar nenhum. O
apurador automatico le o diario, viu um ERRO de producao, disparou um
`claude -p` de diagnostico e saiu EDITANDO O REPOSITORIO as 19:12 por causa
de um vídeo que nunca existiu. A outra sessao teve de desligar o conserto
automatico no `remoto.json` para conter.

A licao nao e "lembre de dublar o diario": e que **desviar um caminho de
escrita nao cobre os outros**. O contador foi para o tmp e o diario continuou
apontando para producao, no mesmo `_anotar_falha_no_tiktok`.

Este arquivo e a rede que nao depende de ninguem lembrar: se a suite inteira
terminar e o diario de producao tiver crescido, ele acusa e diz quem.
"""
import os
import unittest
from pathlib import Path

from builds import atividade


class DiarioDeProducaoTests(unittest.TestCase):
    """NAO compara tamanho de arquivo.

    A primeira versao desta trava media o `atividade.jsonl` antes e depois e
    falhava se ele tivesse crescido. Daria VERMELHO FALSO num horario
    qualquer: a producao escreve no mesmo arquivo enquanto a suite roda —
    postagem de :37, bot, madrugada, conferencia. Um teste que quebra por
    causa do relogio ensina a ignorar teste vermelho.

    A trava que nao depende do relogio: durante o teste, o caminho resolvido
    NAO pode ser o de producao. Quem escrever sem dublar escreve no tmp.
    """

    def test_o_diario_resolvido_nao_e_o_de_producao(self):
        resolvido = atividade._arquivo().resolve()
        producao = (Path(os.environ.get("LOCALAPPDATA") or Path.home())
                    / "neural-fights" / "atividade.jsonl").resolve()
        self.assertNotEqual(
            producao, resolvido,
            "o diario esta apontando para PRODUCAO durante os testes. "
            "O `conftest.py` da pasta de testes desvia o "
            "`NEURAL_FIGHTS_RUNTIME_DIR` justamente para isto — se ele sumiu, "
            "ou se este teste rodou fora dele, um teste que registre atividade "
            "vai gravar falha inventada no diario real e o apurador "
            "automatico vai agir sobre ela.")

    def test_escrever_de_verdade_cai_no_desvio(self):
        """Nao basta o caminho estar certo: a escrita tem de seguir por ele."""
        alvo = atividade._arquivo()
        antes = alvo.stat().st_size if alvo.is_file() else 0
        atividade.registrar("publicacao", atividade.LOG,
                            "prova do desvio do diario", "builds")
        self.assertTrue(alvo.is_file())
        self.assertGreater(alvo.stat().st_size, antes)


class ORegistrarEDublavelTests(unittest.TestCase):
    """A rede acima so funciona se der para dublar. Trava a forma."""

    def test_registrar_e_um_atributo_do_modulo(self):
        original = atividade.registrar
        try:
            chamadas = []
            atividade.registrar = lambda *a, **k: chamadas.append((a, k))
            atividade.registrar("x", atividade.LOG, "y", "builds")
            self.assertEqual(1, len(chamadas))
        finally:
            atividade.registrar = original

    def test_o_caminho_do_diario_tem_uma_funcao_so(self):
        """Um ponto unico para desviar. Se virarem dois, dublar um deixa o
        outro escrevendo em producao — que foi exatamente o defeito."""
        self.assertTrue(callable(atividade._arquivo))
        self.assertEqual("atividade.jsonl", atividade._arquivo().name)


if __name__ == "__main__":
    unittest.main()
