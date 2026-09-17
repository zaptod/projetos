"""A marca de "a conferir" E o bloqueio, entao perde-la reposta video.

Tres defeitos achados pela revisao do app, todos na fronteira em que o bot e
o botao do painel usam as mesmas funcoes da grade.

**1. Arquivo cortado apagava as marcas antigas.**
A primeira versao lia o JSON e, com o arquivo ilegivel, caia em `{}` e
regravava a lista **so com o item novo**. Todos os videos que estavam
bloqueados voltavam para a fila e a recuperacao os repostava — o modo de
falha era exatamente o defeito que a marca existe para impedir, e chegava em
silencio. Agora o arquivo ilegivel e RENOMEADO (nunca sobrescrito: ele e a
unica lista de quem estava bloqueado) e a gravacao vai por `.tmp` +
`os.replace`, que troca o arquivo inteiro ou nenhum.

**2. Nao conseguir gravar passava por "nao havia o que gravar".**
`except: pass` transformava "nao consegui bloquear" em silencio. Agora
levanta `NaoConsegviMarcar`, com ERRO no diario antes.

**3. "A conferir" saia como sucesso no `main.py publicar`.**
Ele imprimia `YouTube: <estado>` e devolvia 0 para qualquer retorno,
inclusive "cliquei em publicar, mas o Studio nao mostrou a confirmacao...
RASCUNHO". Quem automatiza lia zero e dava por publicado. Agora imprime
"A CONFERIR" e sai com codigo 3 — nem 0 (publicou) nem 1 (falhou).
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from builds.publicar import desfecho

CLICOU = ("cliquei em publicar, mas o TikTok nao confirmou. A janela ficou "
          "aberta: confira se o video subiu.")


class MarcaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.arq = Path(self.tmp.name) / "_tiktok_a_conferir.json"
        self.addCleanup(setattr, desfecho, "arquivo_a_conferir",
                        desfecho.arquivo_a_conferir)
        desfecho.arquivo_a_conferir = lambda _c, _p="tiktok": self.arq
        from builds import atividade
        self.addCleanup(setattr, atividade, "registrar", atividade.registrar)
        self.diario = []
        atividade.registrar = lambda *a, **k: self.diario.append(a)

    # ------------------------------------------------ 1: o que se perdia
    def test_arquivo_cortado_NAO_apaga_as_marcas_antigas(self):
        self.arq.write_text('{"velho:build:celular": {"quando": "x"}',  # sem }
                            encoding="utf-8")
        with self.assertRaises(desfecho.NaoConsegviMarcar):
            desfecho.marcar_para_conferir("builds", "novo:build:celular",
                                          CLICOU)
        guardados = list(self.arq.parent.glob("*.corrompido-*"))
        self.assertTrue(guardados, "o ilegivel tem de ser GUARDADO, nao sumir")
        self.assertIn("velho:build:celular",
                      guardados[0].read_text(encoding="utf-8"),
                      "e ele e a unica lista de quem estava bloqueado")

    def test_o_ilegivel_FICA_no_lugar_e_nada_e_gravado(self):
        """Renomear sozinho ja era o estrago.

        Sem arquivo, `a_conferir` devolve `set()` — "ninguem bloqueado" —,
        que e uma AFIRMACAO. A falha fechada da leitura viraria falha aberta
        na chamada seguinte, pela porta dos fundos, e a recuperacao
        repostaria todo mundo que estava marcado.
        """
        self.arq.write_text('{"velho:build:celular": {"quando": "x"}',
                            encoding="utf-8")
        with self.assertRaises(desfecho.NaoConsegviMarcar):
            desfecho.marcar_para_conferir("builds", "novo:build:celular",
                                          CLICOU)
        self.assertTrue(self.arq.exists(), "o ilegivel nao pode sumir")
        self.assertNotIn("novo:build:celular",
                         self.arq.read_text(encoding="utf-8"),
                         "gravar por cima do ilegivel apaga a lista")
        with self.assertRaises(desfecho.NaoConsegviLer):
            desfecho.a_conferir("builds")

    def test_avisa_que_ninguem_esta_bloqueado(self):
        self.arq.write_text("{quebrado", encoding="utf-8")
        with self.assertRaises(desfecho.NaoConsegviMarcar):
            desfecho.marcar_para_conferir("builds", "novo:build:celular",
                                          CLICOU)
        texto = " ".join(str(a) for a in self.diario)
        self.assertIn("ilegivel", texto)
        self.assertIn("NAO esta bloqueado", texto)

    def test_marca_normal_preserva_as_anteriores(self):
        desfecho.marcar_para_conferir("builds", "a:build:celular", CLICOU)
        desfecho.marcar_para_conferir("builds", "b:build:celular", CLICOU)
        self.assertEqual({"a:build:celular", "b:build:celular"},
                         desfecho.a_conferir("builds"))

    def test_nao_repete_o_aviso_do_mesmo_video(self):
        desfecho.marcar_para_conferir("builds", "a:build:celular", CLICOU)
        antes = len(self.diario)
        desfecho.marcar_para_conferir("builds", "a:build:celular", CLICOU)
        self.assertEqual(antes, len(self.diario))

    def test_nao_deixa_o_tmp_para_tras(self):
        desfecho.marcar_para_conferir("builds", "a:build:celular", CLICOU)
        self.assertEqual([], list(self.arq.parent.glob("*.tmp")))

    # ------------------------------------------------ 2: falha ruidosa
    def test_nao_conseguir_gravar_LEVANTA(self):
        """"Nao consegui bloquear" nao pode virar "nao havia o que bloquear"."""
        desfecho.arquivo_a_conferir = (
            lambda _c, _p="tiktok": Path("Z:/nao/existe/x.json"))
        with self.assertRaises(desfecho.NaoConsegviMarcar):
            desfecho.marcar_para_conferir("builds", "a:build:celular", CLICOU)
        texto = " ".join(str(a) for a in self.diario)
        self.assertIn("NAO esta bloqueado", texto)

    def test_video_id_vazio_nao_marca_nem_levanta(self):
        self.assertFalse(desfecho.marcar_para_conferir("builds", "", CLICOU))


class ErroPassageiroNaoEcorrupcaoTests(unittest.TestCase):
    """A protecao contra corrupcao virava a CAUSA da perda.

    No Windows, ler enquanto outro processo faz `os.replace` devolve erro de
    compartilhamento. A versao anterior tratava isso como arquivo quebrado,
    renomeava a lista e recomecava VAZIA — e o app, o bot e a grade escrevem
    no mesmo arquivo. `OSError` tenta de novo; so JSON invalido conta como
    corrupcao.
    """

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.arq = Path(self.tmp.name) / "_tiktok_a_conferir.json"
        self.addCleanup(setattr, desfecho, "arquivo_a_conferir",
                        desfecho.arquivo_a_conferir)
        desfecho.arquivo_a_conferir = lambda _c, _p="tiktok": self.arq

    def test_OSError_passageiro_e_tentado_de_novo(self):
        self.arq.write_text('{"a:build:celular": {"quando": "x"}}',
                            encoding="utf-8")
        chamadas = []
        original = Path.read_text

        def instavel(self_, *a, **k):
            chamadas.append(1)
            if len(chamadas) == 1:
                raise OSError("o arquivo esta em uso por outro processo")
            return original(self_, *a, **k)

        self.addCleanup(setattr, Path, "read_text", original)
        Path.read_text = instavel
        self.assertEqual({"a:build:celular"}, desfecho.a_conferir("builds"))
        self.assertGreaterEqual(len(chamadas), 2, "tinha de tentar de novo")

    def test_json_invalido_SIM_e_corrupcao(self):
        self.arq.write_text("{isto nao e json", encoding="utf-8")
        with self.assertRaises(desfecho.NaoConsegviLer):
            desfecho.a_conferir("builds")


class FalhaFechadaTests(unittest.TestCase):
    """`set()` e uma afirmacao ("ninguem bloqueado"), nao um "nao sei".

    A versao anterior devolvia conjunto vazio em qualquer erro, e quem chama
    entendia que nada estava bloqueado — repostando todos os marcados.
    """

    def setUp(self):
        self.addCleanup(setattr, desfecho, "arquivo_a_conferir",
                        desfecho.arquivo_a_conferir)

    def test_nao_conseguir_ler_LEVANTA(self):
        ruim = Path("Z:/nao/existe/x.json")
        desfecho.arquivo_a_conferir = lambda _c, _p="tiktok": ruim
        # Arquivo inexistente nao e erro: e "ninguem marcado".
        self.assertEqual(set(), desfecho.a_conferir("builds"))

    def test_arquivo_ilegivel_LEVANTA_em_vez_de_dizer_vazio(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        arq = Path(tmp.name) / "x.json"
        arq.write_text("{quebrado", encoding="utf-8")
        desfecho.arquivo_a_conferir = lambda _c, _p="tiktok": arq
        with self.assertRaises(desfecho.NaoConsegviLer):
            desfecho.a_conferir("builds")


class PorDestinoTests(unittest.TestCase):
    """Um arquivo POR DESTINO: sem confirmacao no YouTube nao bloqueia o
    TikTok, onde o video talvez ainda precise sair."""

    def test_os_arquivos_sao_diferentes(self):
        a = desfecho.arquivo_a_conferir("builds", "tiktok")
        b = desfecho.arquivo_a_conferir("builds", "youtube")
        self.assertNotEqual(a, b)
        self.assertIn("tiktok", a.name)
        self.assertIn("youtube", b.name)

    def test_a_trava_e_por_destino(self):
        self.assertNotEqual(desfecho.nome_da_trava("tiktok"),
                            desfecho.nome_da_trava("youtube"))


class ConfirmadoTests(unittest.TestCase):
    def test_sem_o_modulo_a_resposta_e_NAO(self):
        """`bool(estado)` fazia QUALQUER texto virar "publicado", inclusive
        "cliquei mas nao confirmou" — o caso em que nada se deve afirmar."""
        import importlib.util
        raiz = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location(
            "postar_conf", raiz / "ferramentas" / "postar.py")
        postar = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(postar)
        import builds.publicar.tiktok as T
        original = T.confirmado
        try:
            def explode(_e):
                raise ImportError("tiktok indisponivel")
            T.confirmado = explode
            self.assertFalse(postar._tiktok_confirmado(CLICOU))
            self.assertFalse(postar._tiktok_confirmado("qualquer texto"))
        finally:
            T.confirmado = original


class SaidaDoMainTests(unittest.TestCase):
    """O `main.py publicar` precisa distinguir tres coisas, nao duas."""

    def setUp(self):
        import importlib.util
        raiz = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "rb_main", raiz / "main.py")
        self.main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.main)

    def test_reconhece_a_conferir(self):
        self.assertTrue(self.main._a_conferir(CLICOU))

    def test_sucesso_nao_e_a_conferir(self):
        self.assertFalse(self.main._a_conferir("publicado no TikTok"))
        self.assertFalse(self.main._a_conferir("https://youtu.be/abc"))

    def test_usa_a_MESMA_classificacao_da_grade(self):
        """Dois criterios de "publicou" foi o defeito que fez rascunho contar
        como publicacao por semanas."""
        import inspect
        self.assertIn("desfecho", inspect.getsource(self.main._a_conferir))

    def test_o_codigo_de_saida_3_existe_no_caminho(self):
        import inspect
        fonte = inspect.getsource(self.main._publicar)
        self.assertIn("A CONFERIR", fonte)
        self.assertIn("return 3", fonte)


if __name__ == "__main__":
    unittest.main()
