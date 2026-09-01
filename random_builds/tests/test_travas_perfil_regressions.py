# -*- coding: utf-8 -*-
"""A trava tem que proteger o RECURSO de verdade: a pasta do Chrome.

O invariante real, que a propria docstring de `travas.py` declara, e "um
Chrome por `user_data_dir`". Ate 01/09/2026 a trava era nomeada
`servico__conta` — o que valia enquanto conta e pasta andavam juntas.

Elas deixaram de andar. O servico `youtube_web` ganhou `sessao_unica: True`
(um login do Google cobre os tres canais dele, entao `contas.perfil()` forca
a conta para `principal`), mas `travas.do_perfil` continuou chavando pela
conta ATIVA. Resultado medido:

    canal      trava                        perfil
    builds     youtube_web__neural_fights   youtube_web
    historias  youtube_web__historinhas     youtube_web

Duas travas, uma pasta. Dois Chrome no mesmo `user_data_dir` corrompem o
perfil — e o sintoma seria "meu login sumiu", dias depois, sem causa
aparente.

Pior: publicar nao pegava trava NENHUMA. Das 16 chamadas de
`contexto_persistente` no repositorio, so 3 estavam guardadas; as 7 dos
publicadores abriam Chrome com o perfil livre.

Rode de dentro de random_builds/:
    python -m unittest tests.test_travas_perfil_regressions -v
"""
from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from builds import contas, travas


class RegistroTemporario(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        anterior = contas.ARQUIVO
        contas.ARQUIVO = str(Path(pasta.name) / "contas.json")
        self.addCleanup(lambda: setattr(contas, "ARQUIVO", anterior))


class TravaSegueAPastaTests(RegistroTemporario):
    """O nome da trava tem que sair do CAMINHO, nao do nome da conta."""

    def test_sessao_unica_da_a_MESMA_trava_nos_dois_canais(self):
        """O bug medido: duas travas para a mesma pasta."""
        contas.escolher("youtube_web", "builds", "neural_fights")
        contas.escolher("youtube_web", "historias", "historinhas")

        # Premissa: a pasta e a mesma (e o que `sessao_unica` faz).
        self.assertEqual(contas.perfil("youtube_web", "builds"),
                         contas.perfil("youtube_web", "historias"))
        # Entao a trava tambem tem que ser.
        self.assertEqual(travas.do_perfil("youtube_web", "builds"),
                         travas.do_perfil("youtube_web", "historias"))

    def test_pastas_diferentes_continuam_com_travas_diferentes(self):
        """Separar conta continua servindo para rodar em paralelo."""
        contas.escolher("picasso", "builds", "principal")
        contas.escolher("picasso", "historias", "segunda")
        self.assertNotEqual(contas.perfil("picasso", "builds"),
                            contas.perfil("picasso", "historias"))
        self.assertNotEqual(travas.do_perfil("picasso", "builds"),
                            travas.do_perfil("picasso", "historias"))

    def test_a_mesma_conta_nos_dois_canais_e_uma_trava_so(self):
        """O caso comum hoje: tudo caindo em `principal`."""
        self.assertEqual(travas.do_perfil("picasso", "builds"),
                         travas.do_perfil("picasso", "historias"))

    def test_o_estado_mostra_a_pasta_para_o_humano_entender(self):
        """Sem o caminho, "essas duas dividem a trava" e uma afirmacao cega."""
        contas.escolher("youtube_web", "builds", "neural_fights")
        contas.escolher("youtube_web", "historias", "historinhas")
        linhas = travas.estado()
        do_yt = [linha for linha in linhas if linha["servico"] == "youtube_web"]
        self.assertTrue(do_yt, "youtube_web sumiu do estado")
        self.assertIn("perfil", do_yt[0])
        for linha in do_yt:
            self.assertTrue(str(linha["perfil"]), "perfil vazio")

    def test_youtube_web_aparece_uma_vez_so_no_estado(self):
        """Uma pasta, uma linha — senao o painel mostra paralelismo que nao ha."""
        contas.escolher("youtube_web", "builds", "neural_fights")
        contas.escolher("youtube_web", "historias", "historinhas")
        do_yt = [linha for linha in travas.estado()
                 if linha["servico"] == "youtube_web"]
        self.assertEqual(1, len(do_yt), do_yt)
        self.assertEqual({"builds", "historias"}, set(do_yt[0]["canais"]))


class ReentranciaTests(unittest.TestCase):
    """Segurar a mesma trava duas vezes no MESMO processo nao pode travar.

    Isto nao e luxo: a guarda vai passar para dentro de
    `contexto_persistente`, e ha tres lugares que JA pegam a trava antes de
    chamar. Sem reentrancia eles travariam contra si mesmos, e o sintoma
    seria a pipeline inteira parada parecendo disco lento.
    """

    def test_a_mesma_trava_duas_vezes_na_mesma_thread(self):
        nome = "teste_reentrante_abc"
        with travas.trava(nome) as primeira:
            self.assertTrue(primeira)
            with travas.trava(nome) as segunda:
                self.assertTrue(segunda, "travou contra si mesma")

    def test_liberar_a_de_dentro_nao_solta_a_de_fora(self):
        nome = "teste_reentrante_def"
        resultado = {}

        with travas.trava(nome) as externa:
            self.assertTrue(externa)
            with travas.trava(nome):
                pass

            # Depois do bloco interno, a trava ainda tem que ser minha.
            def outra_thread():
                # `ocupada` adquire para testar; de outra thread deve dar True.
                resultado["ocupada"] = travas.ocupada(nome)

            t = threading.Thread(target=outra_thread)
            t.start()
            t.join(timeout=10)
        self.assertTrue(resultado.get("ocupada"),
                        "a trava de fora foi solta pela de dentro")

    def test_depois_de_sair_de_tudo_a_trava_esta_livre(self):
        nome = "teste_reentrante_ghi"
        with travas.trava(nome):
            with travas.trava(nome):
                pass
        self.assertFalse(travas.ocupada(nome))


class PublicarPegaTravaTests(unittest.TestCase):
    """Publicar abria Chrome sem guarda nenhuma."""

    def test_contexto_persistente_pede_a_trava_do_perfil(self):
        fonte = (Path(__file__).resolve().parents[1] / "builds" / "identity"
                 / "browser.py").read_text(encoding="utf-8")
        i = fonte.index("def contexto_persistente")
        trecho = fonte[i:i + 3000]
        self.assertIn("travas", trecho)
        self.assertIn("PerfilOcupado", trecho)

    def test_existe_um_erro_com_nome_para_perfil_ocupado(self):
        from builds.identity import browser
        self.assertTrue(issubclass(browser.PerfilOcupado, Exception))


if __name__ == "__main__":
    unittest.main()
