"""Publicar no TikTok sem legenda queima o video — entao nao publica.

16/09/2026, medido no `outputs/postar.txt`: 73 uploads, **69 legendas
escritas**. Quatro videos subiram ao TikTok sem titulo, sem hashtag e sem
descoberta. A falha registrava so `"nao consegui escrever a legenda
(TimeoutError); da para colar na mao"` e o fluxo seguia e publicava — um
aviso simpatico num log que ninguem le as 3 da manha.

Publicar assim e PIOR que adiar. O video fica marcado como publicado, rende
nada e nunca mais e tentado; adiado, ele volta pela recuperacao de atrasados
(um por rodada) e sai inteiro depois. E nao fere a regra do Adrian de nao
ficar sem video: ha dezenas no estoque para o horario, e o que falta e um
video BOM.

O contrato:
1. Falha na primeira tentativa, sucesso na segunda: publica normal.
2. Falha nas duas: NAO publica, e o motivo aparece na mensagem do erro
   (e dela que o diario conta por que o TikTok falhou).
3. `type()` sem erro NAO e prova: campo lido de volta vazio conta como falha.
   E a mesma confusao do "botao habilitado" que este arquivo ja combate.
4. Sem legenda para escrever (descricao vazia) nao ha o que cobrar.
5. Fora do modo `postar` (janela para conferir na mao) nada e barrado: tem
   gente na frente da tela.
6. O TikTok reformata a legenda enquanto ela e digitada (hashtag vira `span`,
   emoji vira imagem). A conferencia NAO pode exigir texto identico, ou
   adiaria video bom.
"""
import unittest

from builds.publicar import tiktok


class _Campo:
    """Contenteditable falso: aceita (ou nao) o que o TECLADO manda, e devolve
    o que tem.

    Desde 27/09/2026 a legenda nao entra mais por `campo.type` (ver
    `builds/publicar/escrita.py`): ela chega pelo teclado da pagina — colada,
    com Enter e hashtag como tecla. Uma TENTATIVA e um clique, que e como
    `escrita.escrever` comeca cada escrita.
    """

    def __init__(self, *, falhas=0, guarda=True, texto_lido=None, ler_erro=False):
        self.falhas_restantes = falhas
        self.guarda = guarda            # o campo guarda o que foi digitado?
        self.texto_lido = texto_lido    # forca o que `inner_text` devolve
        self.ler_erro = ler_erro
        self.conteudo = ""
        self.tentativas = 0

    def click(self):
        self.tentativas += 1

    def receber(self, trecho):
        if self.falhas_restantes > 0:
            self.falhas_restantes -= 1
            raise TimeoutError("o campo nao respondeu")
        if self.guarda:
            self.conteudo += trecho

    def type(self, texto, delay=0):
        """So para os testes de `_estado_da_legenda`, que enchem o campo."""
        self.conteudo = texto

    def inner_text(self):
        if self.ler_erro:
            raise RuntimeError("elemento saiu da tela")
        return self.texto_lido if self.texto_lido is not None else self.conteudo


LEGENDA = "Ylva Brumalok, Berserker — build 56/100 #build #rpg"


class EstadoDaLegendaTests(unittest.TestCase):
    def test_campo_vazio_e_vazio(self):
        self.assertEqual("ficou vazia",
                         tiktok._estado_da_legenda(_Campo(texto_lido=""),
                                                   LEGENDA))

    def test_campo_com_o_texto_e_escrita(self):
        campo = _Campo()
        campo.type(LEGENDA)
        self.assertEqual("escrita", tiktok._estado_da_legenda(campo, LEGENDA))

    def test_hashtag_reformatada_ainda_e_escrita(self):
        """O TikTok mexe no fim da legenda; o comeco e o titulo e fica."""
        campo = _Campo(texto_lido="Ylva Brumalok, Berserker — build 56/100 ")
        self.assertEqual("escrita", tiktok._estado_da_legenda(campo, LEGENDA),
                         "exigir texto identico adiaria video bom")

    def test_meia_duzia_de_letras_e_INCOMPLETA_nao_vazia(self):
        """Vazia e incompleta tem causas diferentes e conserto diferente:
        campo que nao aceitou nada contra digitacao interrompida no meio."""
        self.assertEqual("ficou incompleta",
                         tiktok._estado_da_legenda(_Campo(texto_lido="Ylv"),
                                                   LEGENDA))

    def test_nao_dar_para_ler_nao_inventa_falha(self):
        self.assertEqual("escrita",
                         tiktok._estado_da_legenda(_Campo(ler_erro=True),
                                                   LEGENDA))

    def test_emoji_no_comeco_nao_vira_falso_alarme(self):
        """`inner_text` nao ve emoji (o TikTok troca por `<img>`). Sem tirar
        dos DOIS lados, legenda que comeca com emoji seria dada como falha e
        o contador acabaria DESISTINDO de um video que estava certo."""
        texto = "🔥 Ylva Brumalok, Berserker — build 56/100 #build"
        campo = _Campo(texto_lido=" Ylva Brumalok, Berserker — build 56/100 ")
        self.assertEqual("escrita", tiktok._estado_da_legenda(campo, texto))


class DeveBarrarTests(unittest.TestCase):
    """A decisao real, chamada direto — nao uma copia dela no teste."""

    def test_barra_quando_a_legenda_nao_entrou(self):
        self.assertTrue(tiktok._deve_barrar(True, LEGENDA,
                                            {"legenda": "ficou vazia"}))

    def test_nao_barra_com_a_legenda_escrita(self):
        self.assertFalse(tiktok._deve_barrar(True, LEGENDA,
                                             {"legenda": "escrita"}))

    def test_conferir_na_mao_NUNCA_barra(self):
        """`postar=False` e o modo do painel: a janela fica aberta para ele
        conferir. Levantar ali tiraria dele a chance de colar na mao."""
        for estado in ("ficou vazia", "ficou incompleta",
                       "campo não encontrado", "falhou: TimeoutError"):
            with self.subTest(estado=estado):
                self.assertFalse(
                    tiktok._deve_barrar(False, LEGENDA, {"legenda": estado}))

    def test_sem_texto_nao_ha_o_que_cobrar(self):
        self.assertFalse(tiktok._deve_barrar(True, "", {"legenda": "ficou vazia"}))

    def test_laudo_sem_a_chave_barra(self):
        """Ausencia nao e sucesso: se ninguem escreveu o laudo, a legenda nao
        foi escrita."""
        self.assertTrue(tiktok._deve_barrar(True, LEGENDA, {}))


class _Passos(list):
    def __call__(self, texto):
        self.append(texto)


class _Teclado:
    """Escreve no campo da pagina, como o de verdade escreve no que tem foco."""

    def __init__(self, campo):
        self.campo = campo

    def press(self, tecla):
        if tecla == "Delete":
            self.campo.conteudo = ""
        elif tecla == "Enter":
            self.campo.receber("\n")

    def insert_text(self, texto):
        self.campo.receber(texto)

    def type(self, texto, delay=0):
        self.campo.receber(texto)


class _Pagina:
    """Pagina falsa que sempre devolve o mesmo campo (ou nenhum)."""

    def __init__(self, campo):
        self.campo = campo
        self.keyboard = _Teclado(campo)


class NaoPublicaSemLegendaTests(unittest.TestCase):
    """Chama `_escrever_legenda` DE VERDADE, sem abrir o Chrome.

    O laco nao e reproduzido aqui de proposito: um teste que reimplementasse
    a logica passaria com a producao quebrada, que e justamente o que ele
    deveria pegar.
    """

    def _rodar(self, campo, *, postar=True, texto=LEGENDA):
        laudo, passo = {}, _Passos()
        pagina = _Pagina(campo)
        original = tiktok._primeiro
        tiktok._primeiro = lambda page, sel, timeout=0: page.campo
        try:
            tiktok._escrever_legenda(pagina, texto, passo, laudo)
        finally:
            tiktok._primeiro = original
        # A mesma condicao que `publicar` aplica logo depois de chamar.
        # A MESMA funcao que `publicar` chama, nao uma copia da regra.
        barrou = tiktok._deve_barrar(postar, texto, laudo)
        return laudo, passo, barrou

    def test_falha_uma_vez_e_passa_na_segunda(self):
        campo = _Campo(falhas=1)
        laudo, _, barrou = self._rodar(campo)
        self.assertEqual("escrita", laudo["legenda"])
        self.assertFalse(barrou, "lentidao passageira nao pode custar o video")
        self.assertEqual(2, campo.tentativas)

    def test_falha_sempre_e_nao_publica(self):
        laudo, _, barrou = self._rodar(_Campo(falhas=9))
        self.assertTrue(barrou, "publicar sem legenda queima o video")
        self.assertIn("TimeoutError", laudo["legenda"])

    def test_type_sem_erro_mas_campo_vazio_nao_publica(self):
        """O caso que o codigo antigo dava como sucesso."""
        campo = _Campo(guarda=False)
        laudo, _, barrou = self._rodar(campo)
        self.assertEqual("ficou vazia", laudo["legenda"])
        self.assertTrue(barrou)
        self.assertEqual(2, campo.tentativas, "tinha de tentar de novo")

    def test_campo_ausente_nao_publica(self):
        laudo, _, barrou = self._rodar(None)
        self.assertEqual("campo não encontrado", laudo["legenda"])
        self.assertTrue(barrou)

    def test_sem_texto_nao_ha_o_que_cobrar(self):
        _, _, barrou = self._rodar(_Campo(falhas=9), texto="")
        self.assertFalse(barrou)

    def test_modo_conferir_na_mao_nao_barra(self):
        _, _, barrou = self._rodar(_Campo(falhas=9), postar=False)
        self.assertFalse(barrou, "tem gente na frente da tela")


class AGuardaEstaNoCaminhoRealTests(unittest.TestCase):
    """`_escrever_legenda` sozinho nao prova nada: `publicar` tem de barrar.

    Sem isto, alguem poderia tirar a guarda de `publicar` e os testes acima
    continuariam verdes — a funcao devolve `False` e ninguem olha.
    """

    def test_publicar_chama_as_duas_funcoes_testadas(self):
        """Duas chamadas, nao a regra escrita de novo.

        Ficou mais simples depois que a condicao virou `_deve_barrar`: antes
        este teste procurava o TEXTO da condicao no fonte e quebraria numa
        reformatacao. Agora procura o nome de duas funcoes, que so mudam se
        alguem realmente trocar o desenho.
        """
        import inspect
        fonte = inspect.getsource(tiktok.publicar)
        sem_comentario = "\n".join(
            l for l in fonte.splitlines() if not l.strip().startswith("#"))
        self.assertIn("_escrever_legenda(", sem_comentario,
                      "publicar tem de usar a funcao testada, nao uma copia")
        self.assertIn("_deve_barrar(", sem_comentario,
                      "e tem de decidir pela funcao testada, nao por uma copia")
        self.assertIn("raise TikTokFalhou", sem_comentario)

    def test_a_etiqueta_de_legenda_saiu_da_mensagem_do_botao(self):
        """Item F: `[legenda: ...]` era para separar duas falhas no diario.
        Legenda que nao entra levanta ANTES agora, com mensagem propria, e
        nunca chega la — a etiqueta so dizia "escrita" e ocupava espaco.

        Confere o CODIGO sem os comentarios: o proprio comentario que explica
        a remocao cita a etiqueta, e sem tirar os comentarios este teste
        acusaria a si mesmo. E a armadilha que ja mordeu duas vezes aqui.
        """
        import inspect
        codigo = "\n".join(
            l for l in inspect.getsource(tiktok.publicar).splitlines()
            if not l.strip().startswith("#"))
        self.assertNotIn("[legenda:", codigo)


if __name__ == "__main__":
    unittest.main()
