# -*- coding: utf-8 -*-
"""O texto entra no campo sem apostar na velocidade da maquina.

MEDIDO EM 27/09/2026. Desde 20/09: 12 `Locator.type: Timeout 30000ms` no
YouTube (titulo e descricao) e 22 "a legenda nao entrou (TimeoutError)" no
TikTok. O campo EXISTIA ("locator resolved to <div id="textbox" ...>") e o
clique passava; o que vencia era o prazo de 30 s do `type`, que vale para o
texto INTEIRO, uma ida e volta a pagina por letra. Com o League of Legends
aberto e a CPU em 100%: 126 ms por caractere numa pagina vazia — 300
caracteres em 37,9 s. A descricao da `historia_00032:celular:p04` tem 238.
13 das 17 falhas de 25 a 27/09 cairam dentro de uma partida.

`insert_text` entrega o trecho num evento so: 1500 caracteres em 0,05 s na
mesma CPU. Continuam TECLA a quebra de linha (Enter) e as hashtags (o site
abre sugestao no `#` e fecha no espaco): 46 teclas em vez de 238.

MEDIDO EM PRODUCAO, 28/09/2026 00:37: no YouTube a colagem saiu identica
(titulo e descricao conferidos pela API, duas publicacoes); no TikTok uma das
duas legendas coladas perdeu dois paragrafos (85 de 230 caracteres) e o
criterio antigo de leitura a aprovou. Por isso o TikTok digita primeiro e so
cola na segunda tentativa, e a leitura passou a exigir cada linha.

Os dubles aqui SAO o relogio e o teclado: o custo de cada tecla e o numero
medido, e o teste antigo (tudo tecla, prazo de 30 s) estoura no mesmo
relogio — sem isso, o verde nao provaria nada.
"""
import inspect
import tempfile
import unittest
from pathlib import Path

from builds.publicar import escrita, tiktok, youtube_web

# O texto exato da parte que ficou fora do YouTube em 27/09/2026, 18:07.
DESCRICAO_H32_P04 = (
    "A Filha que Ficou\n\nParte 4 de 6 — as outras estão no canal, na ordem."
    "\n\nEu escrevo e conto essas histórias aqui. Os personagens e os nomes "
    "são invenção minha.\n\nO que você faria no lugar dele?\n\n#historias "
    "#relatos #reddit #storytime #shorts")
MS_POR_TECLA_MEDIDO = 126


class _Relogio:
    def __init__(self):
        self.agora = 0.0

    def __call__(self):
        return self.agora


class _Campo:
    """Contenteditable falso. `aceita_colagem=False` e o site que ignora
    `insert_text`; `guarda=False`, o campo que nao aceita nada."""

    def __init__(self, *, aceita_colagem=True, guarda=True, falhas=0):
        self.aceita_colagem, self.guarda = aceita_colagem, guarda
        self.falhas = falhas
        self.texto = ""
        self.cliques = 0

    def click(self, **_k):
        self.cliques += 1

    def inner_text(self):
        return self.texto

    def receber(self, trecho, *, colado=False):
        if self.falhas > 0:
            self.falhas -= 1
            raise TimeoutError("o campo nao respondeu")
        if not self.guarda or (colado and not self.aceita_colagem):
            return
        self.texto += trecho


class _Teclado:
    def __init__(self, campo, relogio, ms_por_tecla):
        self.campo, self.relogio, self.custo = campo, relogio, ms_por_tecla / 1000
        self.selecionou = False
        self.teclas = 0
        self.colagens = 0

    def press(self, tecla):
        self.relogio.agora += self.custo
        if tecla == "Control+A":
            self.selecionou = True
        elif tecla == "Delete" and self.selecionou:
            self.campo.texto = ""
            self.selecionou = False
        elif tecla == "Enter":
            self.teclas += 1
            self.campo.receber("\n")

    def type(self, texto, delay=0):
        for letra in texto:
            self.relogio.agora += self.custo
            self.teclas += 1
            self.campo.receber(letra)

    def insert_text(self, texto):
        self.colagens += 1
        self.campo.receber(texto, colado=True)


class _Pagina:
    def __init__(self, campo, *, ms_por_tecla=MS_POR_TECLA_MEDIDO):
        self.relogio = _Relogio()
        self.campo = campo
        self.keyboard = _Teclado(campo, self.relogio, ms_por_tecla)
        self.fotos = []

    def screenshot(self, path, timeout=0):
        self.fotos.append(path)
        Path(path).write_bytes(b"png")


class _PastaDeTelas(unittest.TestCase):
    """As fotos de falha vao para uma pasta descartavel, nunca para outputs/."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        original = escrita.PASTA_DAS_TELAS
        escrita.PASTA_DAS_TELAS = Path(self._tmp.name)
        self.addCleanup(setattr, escrita, "PASTA_DAS_TELAS", original)


class PedacosTests(unittest.TestCase):
    def test_so_hashtag_e_quebra_de_linha_sao_tecla(self):
        pedacos = escrita.pedacos(DESCRICAO_H32_P04)
        digitado = sum(len(t) for m, t in pedacos if m == "digitar")
        enters = sum(1 for m, _ in pedacos if m == "tecla")
        self.assertEqual(238, len(DESCRICAO_H32_P04))
        self.assertEqual(46, digitado, "so as cinco hashtags e seus espacos")
        self.assertEqual(8, enters)
        self.assertTrue(all(t == "Enter" for m, t in pedacos if m == "tecla"))

    def test_hashtag_leva_o_espaco_que_a_fecha(self):
        """O site abre sugestao no `#` e fecha no espaco. O espaco colado
        seria um evento que o jeito antigo nunca mandou."""
        digitados = [t for m, t in escrita.pedacos("a #um #dois b")
                     if m == "digitar"]
        self.assertEqual(["#um ", "#dois "], digitados)

    def test_sem_colar_e_o_jeito_antigo_tecla_a_tecla(self):
        pedacos = escrita.pedacos(DESCRICAO_H32_P04, colar=False)
        self.assertNotIn("colar", {m for m, _ in pedacos})
        self.assertEqual(DESCRICAO_H32_P04,
                         "".join("\n" if m == "tecla" else t
                                 for m, t in pedacos))

    def test_reconstroi_o_texto_exato(self):
        """Nada se perde nem se duplica na divisao — nem emoji, nem espaco
        duplo, nem hashtag no meio da frase, nem linha vazia nas pontas."""
        for texto in (DESCRICAO_H32_P04, "\nabc\n", "🔥 um  dois #tres\t#q",
                      "#so", "", "fim com espaco ", "a\n\n\nb"):
            for colar in (True, False):
                with self.subTest(texto=texto, colar=colar):
                    pedacos = escrita.pedacos(texto, colar=colar)
                    self.assertEqual(texto, "".join(
                        "\n" if m == "tecla" else t for m, t in pedacos))


class EscreverNoRelogioMedidoTests(unittest.TestCase):
    def test_a_descricao_cabe_com_a_maquina_ocupada(self):
        """126 ms por tecla: 46 teclas e 8 Enter = ~7 s, e nao 30."""
        campo = _Campo()
        pagina = _Pagina(campo)
        laudo = escrita.escrever(pagina, campo, DESCRICAO_H32_P04,
                                 prazo_s=30, relogio=pagina.relogio)
        self.assertEqual(DESCRICAO_H32_P04, campo.texto)
        self.assertLess(pagina.relogio.agora, 10)
        self.assertEqual("colado", laudo["modo"])
        self.assertEqual(46 + 8, laudo["teclas"])

    def test_o_jeito_antigo_passa_dos_30s_no_mesmo_relogio(self):
        """A prova de que o duble reproduz o defeito: tudo tecla, a 126 ms,
        passa dos 30 s que o `Locator.type` dava para o texto inteiro."""
        campo = _Campo()
        pagina = _Pagina(campo)
        escrita.escrever(pagina, campo, DESCRICAO_H32_P04, colar=False,
                         prazo_s=1e9, relogio=pagina.relogio)
        self.assertEqual(DESCRICAO_H32_P04, campo.texto)
        self.assertGreater(pagina.relogio.agora, 30.0)

    def test_prazo_e_conferido_no_meio_e_nao_so_no_fim(self):
        campo = _Campo()
        pagina = _Pagina(campo, ms_por_tecla=2000)
        with self.assertRaises(escrita.EscritaLenta):
            escrita.escrever(pagina, campo, "uma frase bem comprida " * 20,
                             colar=False, prazo_s=10, relogio=pagina.relogio)
        self.assertLess(pagina.relogio.agora, 40,
                        "parou perto do prazo, nao depois de digitar tudo")

    def test_limpa_o_que_o_site_preencheu(self):
        """O Studio e o TikTok poem o NOME DO ARQUIVO no campo."""
        campo = _Campo()
        campo.texto = "final_celular_p04"
        escrita.escrever(_Pagina(campo), campo, "Titulo novo")
        self.assertEqual("Titulo novo", campo.texto)


class FotografarTests(_PastaDeTelas):
    def test_foto_que_falha_nao_derruba(self):
        class _Quebrada:
            def screenshot(self, **_k):
                raise RuntimeError("pagina fechou")
        self.assertEqual("", escrita.fotografar(_Quebrada(), "x"))

    def test_guarda_so_as_mais_novas(self):
        pasta = escrita.PASTA_DAS_TELAS
        for i in range(escrita.TELAS_GUARDADAS + 5):
            (pasta / f"20260101_0000{i:02d}_velha.png").write_bytes(b"x")
        caminho = escrita.fotografar(_Pagina(_Campo()), "youtube_titulo")
        self.assertTrue(Path(caminho).is_file())
        self.assertEqual(escrita.TELAS_GUARDADAS,
                         len(list(pasta.glob("*.png"))))


class YouTubeEscreverTests(_PastaDeTelas):
    """`youtube_web._escrever` de verdade, com a pagina dublada."""

    def test_cola_confere_e_segue(self):
        campo = _Campo()
        laudo = youtube_web._escrever(_Pagina(campo), campo,
                                      DESCRICAO_H32_P04, rotulo="descricao")
        self.assertEqual(DESCRICAO_H32_P04, campo.texto)
        self.assertEqual("colado", laudo["modo"])

    def test_colagem_que_nao_pega_cai_na_tecla(self):
        """Se o Studio ignorar o `insert_text`, o jeito antigo assume — sem
        o prazo de 30 s que era o defeito."""
        campo = _Campo(aceita_colagem=False)
        pagina = _Pagina(campo)
        laudo = youtube_web._escrever(pagina, campo, "Wren Telgyll x Otavio",
                                      rotulo="titulo")
        self.assertEqual("Wren Telgyll x Otavio", campo.texto)
        self.assertEqual("digitado", laudo["modo"])

    def test_campo_que_nao_aceita_nada_levanta_com_foto(self):
        campo = _Campo(guarda=False)
        pagina = _Pagina(campo)
        with self.assertRaises(youtube_web.YouTubeWebFalhou) as caso:
            youtube_web._escrever(pagina, campo, "Titulo", rotulo="titulo")
        self.assertIn("ficou vazia", str(caso.exception))
        self.assertEqual(1, len(pagina.fotos), "a tela da falha fica guardada")

    def test_excecao_no_meio_tambem_fotografa(self):
        """A mensagem guarda o NOME da excecao original: e por ele que o
        diario e a apuracao contam as falhas de escrita."""
        campo = _Campo(falhas=99)
        pagina = _Pagina(campo)
        with self.assertRaises(youtube_web.YouTubeWebFalhou) as caso:
            youtube_web._escrever(pagina, campo, "Titulo", rotulo="titulo")
        self.assertIn("TimeoutError", str(caso.exception))
        self.assertIsInstance(caso.exception.__cause__, TimeoutError)
        self.assertEqual(1, len(pagina.fotos))


class TikTokLegendaTests(_PastaDeTelas):
    """`tiktok._escrever_legenda` de verdade: 1a tecla a tecla, 2a cola."""

    def _rodar(self, campo, *, ms_por_tecla=MS_POR_TECLA_MEDIDO):
        pagina = _Pagina(campo, ms_por_tecla=ms_por_tecla)
        original = tiktok._primeiro
        tiktok._primeiro = lambda page, sel, timeout=0: page.campo
        self.addCleanup(setattr, tiktok, "_primeiro", original)
        # O prazo de `escrita` corre no relogio do teclado dublado.
        relogio = escrita.RELOGIO
        escrita.RELOGIO = pagina.relogio
        self.addCleanup(setattr, escrita, "RELOGIO", relogio)
        laudo, passos = {}, []
        ok = tiktok._escrever_legenda(pagina, DESCRICAO_H32_P04,
                                      passos.append, laudo)
        return ok, laudo, pagina

    def test_digita_na_primeira_sem_o_teto_de_30s(self):
        """238 letras a 126 ms = 30,2 s: o `type` antigo estourava aqui. O
        prazo agora e o de `escrita`, conferido entre palavras."""
        ok, laudo, pagina = self._rodar(_Campo())
        self.assertTrue(ok)
        self.assertEqual("digitada", laudo["legenda_modo"])
        self.assertEqual(0, pagina.keyboard.colagens,
                         "a colagem comeu paragrafos no TikTok em 28/09")
        self.assertGreater(pagina.relogio.agora, 30.0)

    def test_maquina_lenta_demais_cai_na_colagem(self):
        """A 2 s por tecla o prazo de 180 s vence; a colagem salva o post."""
        ok, laudo, pagina = self._rodar(_Campo(), ms_por_tecla=2000)
        self.assertTrue(ok)
        self.assertEqual("colada", laudo["legenda_modo"])
        self.assertEqual(DESCRICAO_H32_P04, pagina.campo.texto)
        self.assertEqual(1, len(pagina.fotos),
                         "a primeira tentativa que estourou deixa a tela")

    def test_nada_entra_e_nao_publica(self):
        ok, laudo, pagina = self._rodar(_Campo(guarda=False))
        self.assertFalse(ok)
        self.assertTrue(tiktok._deve_barrar(True, DESCRICAO_H32_P04, laudo))
        self.assertEqual(2, len(pagina.fotos))


class LeituraExigeCadaLinhaTests(unittest.TestCase):
    """Os dois casos que o criterio antigo (20 primeiros caracteres, ou metade
    do volume) aprovava."""

    class _Lido:
        def __init__(self, texto):
            self.texto = texto

        def inner_text(self):
            return self.texto

    LEGENDA_H31_P06 = (
        "A Casa 42\n\nParte 6 de 6 — as outras estão no canal, na ordem.\n\n"
        "Eu escrevo e conto essas histórias aqui. Os personagens e os nomes "
        "são invenção minha.\n\nO que você faria no lugar dele?\n\n#historias "
        "#relatos #reddit #storytime #shorts")

    def test_paragrafos_comidos_na_colagem_sao_incompleta(self):
        """O que a tela do TikTok mostrou as 00:42 de 28/09/2026."""
        lido = ("A Casa 42\n\nParte 6 de 6 — as outras estão no canal, na "
                "ordem.\n\n\n\n#historias #relatos #reddit #storytime #shorts")
        self.assertEqual("ficou incompleta",
                         escrita.estado(self._Lido(lido), self.LEGENDA_H31_P06))

    def test_titulo_cortado_e_incompleto(self):
        """O rascunho `YqbQUrY1nuE`, 27/09 18:05: 32 de 71 letras."""
        titulo = "A Filha que Ficou — O grupo da família se virou contra mim."
        self.assertEqual("ficou incompleta", escrita.estado(
            self._Lido("A Filha que Ficou — O grupo da f"), titulo))

    def test_hashtag_e_emoji_reformatados_nao_contam(self):
        """O site troca hashtag por `span` (ou a perde no fim) e emoji por
        imagem; exigir isso adiaria video bom."""
        lido = ("A Casa 42\nParte 6 de 6 — as outras estão no canal, na "
                "ordem.\nEu escrevo e conto essas histórias aqui. Os "
                "personagens e os nomes são invenção minha.\nO que você "
                "faria no lugar dele?\n#historias")
        self.assertEqual("escrita",
                         escrita.estado(self._Lido(lido), self.LEGENDA_H31_P06))

    def test_texto_inteiro_e_escrita(self):
        self.assertEqual("escrita", escrita.estado(
            self._Lido(self.LEGENDA_H31_P06), self.LEGENDA_H31_P06))


class NenhumPublicadorDigitaTextoLongoTests(unittest.TestCase):
    """A guarda e no FUNIL: todo caminho de publicacao (grade, recuperacao,
    reserva, escoar, `main.py publicar`, bot, app) termina em
    `youtube_web.publicar` ou `tiktok.publicar`. Se um deles voltar a chamar
    `Locator.type` com o texto do video, o defeito volta — em silencio, so
    nos dias de maquina ocupada."""

    @staticmethod
    def _codigo(modulo):
        return "\n".join(l for l in inspect.getsource(modulo).splitlines()
                         if not l.strip().startswith("#"))

    def test_so_o_agendamento_digita_com_type(self):
        """`_agendar` digita data (10 letras) e hora (5): mesmo a 400 ms por
        tecla sao 6 s. O resto passa por `escrita`.

        Pela ARVORE do codigo, e nao pelo texto: o proprio comentario que
        conta o defeito cita `alvo.type(...)`, e uma busca por texto acusaria
        a explicacao em vez do codigo."""
        import ast
        for modulo in (youtube_web, tiktok):
            arvore = ast.parse(inspect.getsource(modulo))
            chamadas = []
            for funcao in ast.walk(arvore):
                if not isinstance(funcao, ast.FunctionDef):
                    continue
                for no in ast.walk(funcao):
                    if (isinstance(no, ast.Call)
                            and isinstance(no.func, ast.Attribute)
                            and no.func.attr == "type"):
                        chamadas.append(funcao.name)
            with self.subTest(modulo=modulo.__name__):
                self.assertEqual(set(), set(chamadas) - {"_agendar"},
                                 "texto de video digitado com `type` de novo")

    def test_os_dois_publicadores_escrevem_pelo_modulo(self):
        self.assertIn("escrita.escrever(", self._codigo(youtube_web._escrever))
        self.assertIn("escrita.escrever(", self._codigo(tiktok._escrever_legenda))


if __name__ == "__main__":
    unittest.main()
