"""Nem toda falha do TikTok e a mesma coisa — e tratar como se fosse custa video.

Ate 16/09/2026 a recuperacao so perguntava "confirmou?". Tudo que nao fosse
sucesso virava "falha do video": contava para a desistencia e voltava para a
fila. Isso junta tres desfechos que pedem reacoes opostas.

**1. Clique sem confirmacao — o pior, e o motivo deste arquivo.**
`tiktok.py` devolve "cliquei em publicar, mas o TikTok nao confirmou" quando o
clique SAIU e o aviso de sucesso nao apareceu. O post pode estar no ar. Antes
do conserto de hoje o video simplesmente saia da fila; com a recuperacao que
eu escrevi, ele volta e e reenviado **ate tres vezes** — e cada reenvio e uma
DUPLICATA no perfil, que o publico ve. Troquei uma falha silenciosa por uma
visivel. Desfecho certo: fica FORA da fila, com ERRO no diario, esperando
conferencia humana. Nunca reenviar sozinho.

**2. Falha de infraestrutura — nao e culpa do video.**
Aconteceu de verdade as 20:47 de 16/09: `nao consegui abrir o Chrome no perfil
.browser_profile\\youtube_web`, e a rodada de historias perdeu o video. Se
isso pegar a cabeca de uma fila de recuperacao tres vezes — TikTok fora do ar,
login vencido, perfil ocupado — um video sem defeito nenhum e abandonado para
sempre. Desfecho certo: nao conta nada, tenta de novo na proxima rodada.

**3. Falha do video — a unica que conta para desistir.**
Legenda que nao fica, arquivo que o TikTok recusa. E dela que o contador de
tres tentativas fala.

O contrato aqui e a CLASSIFICACAO. Quem reage a cada classe e testado onde a
reacao mora.
"""
import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_desfecho", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


postar = _postar()

SUCESSO = "publicado no TikTok (com a confirmacao extra)"
CLICOU_1 = ("cliquei em publicar, mas o TikTok nao confirmou. A janela ficou "
            "aberta: confira se o video subiu.")
CLICOU_2 = ("cliquei em publicar e na confirmacao, mas o TikTok nao mostrou o "
            "aviso de sucesso. Confira o perfil antes de publicar de novo.")


class ClassificacaoTests(unittest.TestCase):
    def test_sucesso(self):
        self.assertEqual("publicado", postar.desfecho_do_tiktok(SUCESSO))

    def test_as_duas_frases_de_clique_sem_confirmacao(self):
        for estado in (CLICOU_1, CLICOU_2):
            with self.subTest(estado=estado[:30]):
                self.assertEqual("sem_confirmacao",
                                 postar.desfecho_do_tiktok(estado))

    def test_vazio_sem_motivo_e_falha_do_video(self):
        """Sem informacao nenhuma, o conservador e contar — senao um video
        que o TikTok recusa em silencio nunca seria abandonado."""
        self.assertEqual("falha", postar.desfecho_do_tiktok(""))

    def test_chrome_que_nao_abre_e_infraestrutura(self):
        falha = {"tipo": "RuntimeError",
                 "mensagem": "nao consegui abrir o Chrome no perfil "
                             r"E:\projetos\random_builds\.browser_profile"
                             r"\youtube_web. Se houver uma janela aberta..."}
        self.assertEqual("infraestrutura",
                         postar.desfecho_do_tiktok("", falha))

    def test_perfil_ocupado_e_infraestrutura(self):
        self.assertEqual("infraestrutura", postar.desfecho_do_tiktok(
            "", {"tipo": "PerfilOcupado", "mensagem": "o perfil esta em uso"}))

    def test_login_vencido_e_infraestrutura(self):
        self.assertEqual("infraestrutura", postar.desfecho_do_tiktok(
            "", {"tipo": "TikTokFalhou",
                 "mensagem": "o TikTok pediu login. Rode o login uma vez"}))

    def test_rede_fora_e_infraestrutura(self):
        self.assertEqual("infraestrutura", postar.desfecho_do_tiktok(
            "", {"tipo": "Error",
                 "mensagem": "net::ERR_NAME_NOT_RESOLVED at https://..."}))

    def test_legenda_que_nao_entrou_e_falha_do_video(self):
        self.assertEqual("falha", postar.desfecho_do_tiktok(
            "", {"tipo": "TikTokFalhou",
                 "mensagem": "a legenda nao entrou (ficou vazia) e publicar "
                             "sem ela queima o video"}))

    def test_arquivo_sumido_e_falha_do_video(self):
        self.assertEqual("falha", postar.desfecho_do_tiktok(
            "", {"tipo": "TikTokFalhou", "mensagem": "arquivo sumiu: x.mp4"}))

    def test_clique_sem_confirmacao_vence_a_excecao(self):
        """Se o clique saiu, o que aconteceu depois nao muda o risco: pode
        estar no ar, e reenviar duplica."""
        self.assertEqual("sem_confirmacao", postar.desfecho_do_tiktok(
            CLICOU_1, {"tipo": "RuntimeError",
                       "mensagem": "nao consegui abrir o Chrome"}))

    def test_a_marca_do_laudo_sobrevive_a_excecao(self):
        """O caso que o codigo real produz, e que o teste acima NAO cobria.

        Quando algo levanta depois do clique (o ledger preso, o Chrome
        fechando), a frase de retorno se perde e sobra `""`. Sem a marca
        `clicou` gravada no laudo, isso viraria "falha" — tres reenvios sobre
        um post que pode estar no ar.
        """
        self.assertEqual("sem_confirmacao", postar.desfecho_do_tiktok(
            "", {"tipo": "RuntimeError", "mensagem": "ledger ocupado"},
            {"clicou": True}))

    def test_acento_nao_impede_a_marca_de_casar(self):
        """"nao achei o campo de arquivo" nunca casava: o tiktok.py escreve
        "nao" COM acento. Marca que nunca casa e pior que marca ausente."""
        self.assertEqual("infraestrutura", postar.desfecho_do_tiktok(
            "", {"tipo": "TikTokFalhou",
                 "mensagem": "não achei o campo de arquivo na página"}))


class ReacaoAoDesfechoTests(unittest.TestCase):
    """Classificar sem reagir nao conserta nada."""

    def setUp(self):
        # A recuperacao esta DESLIGADA em producao desde 16/09/2026 (ela
        # repostou no ar). Estes testes descrevem o contrato de QUANDO ela
        # estiver ligada, entao ligam a chave e a devolvem no fim.
        for _chave in ("RECUPERACAO_LIGADA", "RESERVA_LIGADA"):
            self.addCleanup(setattr, postar, _chave, getattr(postar, _chave))
            setattr(postar, _chave, True)
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        for nome in ("_arquivo_de_desistencias", "_arquivo_a_conferir",
                     "_fontes_de_atraso", "_tiktok_dos_builds", "_linha"):
            self.addCleanup(setattr, postar, nome, getattr(postar, nome))
        postar._arquivo_de_desistencias = lambda _c: base / "desist.json"
        postar._arquivo_a_conferir = lambda _c: base / "conferir.json"
        postar._linha = lambda *_a, **_k: None
        self.diario = []
        from builds import atividade
        self.addCleanup(setattr, atividade, "registrar", atividade.registrar)
        atividade.registrar = lambda *a, **k: self.diario.append((a, k))

        class _V:
            def __init__(self, vid, titulo):
                self.id, self.titulo, self.perfil = vid, titulo, "celular"

        self.videos = [_V("a:build:celular", "A"), _V("b:build:celular", "B")]
        linhas = [{"video_id": "a:build:celular", "plataforma": "youtube",
                   "quando": "2026-09-14T10:00", "titulo": "A", "url": "u"},
                  {"video_id": "b:build:celular", "plataforma": "youtube",
                   "quando": "2026-09-14T11:00", "titulo": "B", "url": "u"}]
        postar._fontes_de_atraso = lambda _c: (
            linhas, {v.id: v for v in self.videos})

    def _publicador_que_clica_sem_confirmar(self):
        """Dubla `tiktok.publicar`, e NAO `_tiktok_dos_builds`.

        A reacao mora dentro do publicador desde o segundo conserto — dublar
        o publicador inteiro pularia justamente o que se quer testar.
        """
        import sys
        modulo = sys.modules.get("builds.publicar.tiktok")
        self.addCleanup(setattr, modulo, "publicar", modulo.publicar)

        def publicar(alvo, postar=True, canal="builds", progresso=None,
                     prova=None):
            if prova is not None:
                prova["clicou"] = True
            return CLICOU_1
        modulo.publicar = publicar
        self.addCleanup(setattr, postar, "_build_ja_no_tiktok",
                        postar._build_ja_no_tiktok)
        postar._build_ja_no_tiktok = lambda _v: False

    def test_sem_confirmacao_sai_da_fila_e_NAO_conta_falha(self):
        self._publicador_que_clica_sem_confirmar()
        postar.recuperar_no_tiktok(canal="builds")
        self.assertEqual(set(), postar.desistencias_do_tiktok("builds"),
                         "clique sem confirmacao nao e falha do video")
        self.assertIn("a:build:celular", postar.a_conferir_no_tiktok("builds"))
        # e some da fila, para nunca ser reenviado sozinho
        fila = [v.id for v in postar.atrasados_no_tiktok(canal="builds")]
        self.assertNotIn("a:build:celular", fila)
        self.assertIn("b:build:celular", fila)

    def test_sem_confirmacao_vira_ERRO_no_diario(self):
        self._publicador_que_clica_sem_confirmar()
        postar.recuperar_no_tiktok(canal="builds")
        from builds import atividade
        erros = [a for a, _k in self.diario if a[1] == atividade.ERRO]
        self.assertTrue(erros, "ninguem le log; isto tem de ser contado")
        self.assertIn("confer", " ".join(str(e) for e in erros).lower())

    def test_infraestrutura_nao_conta_e_NAO_sai_da_fila(self):
        def publicar(alvo, falha=None):
            if falha is not None:
                falha.update({"tipo": "RuntimeError",
                              "mensagem": "nao consegui abrir o Chrome"})
            return ""
        postar._tiktok_dos_builds = publicar
        for _ in range(postar.FALHAS_ATE_DESISTIR + 2):
            postar.recuperar_no_tiktok(canal="builds")
        self.assertEqual(set(), postar.desistencias_do_tiktok("builds"),
                         "o TikTok fora do ar nao pode abandonar video bom")
        self.assertIn("a:build:celular",
                      [v.id for v in postar.atrasados_no_tiktok(canal="builds")])

    def test_TODO_caminho_marca_a_conferir_nao_so_a_recuperacao(self):
        """O buraco que sobrou do primeiro conserto, e ele era da MESMA rodada.

        A rodada normal recebia "cliquei mas nao confirmou", nada ia para o
        ledger, e a recuperacao — chamada logo depois, no mesmo `main` — via
        um video com YouTube e sem TikTok e o postava DE NOVO. Marcar so
        dentro da recuperacao nao cobria nenhum dos cinco outros caminhos.
        """
        chamados = []

        class _Fake:
            id = "a:build:celular"
            titulo = "A"

        def publicar(alvo, postar=True, canal="builds", progresso=None,
                     prova=None):
            chamados.append(alvo.id)
            if prova is not None:
                prova["clicou"] = True          # o clique saiu
            return CLICOU_1

        import sys
        modulo = sys.modules.get("builds.publicar.tiktok")
        original = modulo.publicar
        self.addCleanup(setattr, modulo, "publicar", original)
        modulo.publicar = publicar
        self.addCleanup(setattr, postar, "_build_ja_no_tiktok",
                        postar._build_ja_no_tiktok)
        postar._build_ja_no_tiktok = lambda _v: False

        postar._tiktok_dos_builds(_Fake())
        self.assertEqual(["a:build:celular"], chamados)
        self.assertIn("a:build:celular", postar.a_conferir_no_tiktok("builds"),
                      "o caminho NORMAL tem de marcar, nao so a recuperacao")
        fila = [v.id for v in postar.atrasados_no_tiktok(canal="builds")]
        self.assertNotIn("a:build:celular", fila,
                         "e por isso a recuperacao da MESMA rodada nao o pega")

    def test_falha_do_video_continua_contando(self):
        def publicar(alvo, falha=None):
            if falha is not None:
                falha.update({"tipo": "TikTokFalhou",
                              "mensagem": "a legenda nao entrou (ficou vazia)"})
            return ""
        postar._tiktok_dos_builds = publicar
        for _ in range(postar.FALHAS_ATE_DESISTIR):
            postar.recuperar_no_tiktok(canal="builds")
        self.assertIn("a:build:celular",
                      postar.desistencias_do_tiktok("builds"))


if __name__ == "__main__":
    unittest.main()
