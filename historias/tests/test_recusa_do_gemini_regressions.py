# -*- coding: utf-8 -*-
"""A recusa enlatada do Gemini e o parecer que ninguem assistiu (27/09/2026).

Madrugada de 27/09/2026, 01:28-01:50: o Gemini recebeu o mp4 (a duracao
apareceu, e o video estava no balao da pergunta quando o historico foi aberto
as 23:13) e respondeu "Sou uma IA com base em texto, e isso esta alem das
minhas capacidades" em 5 de 9 videos. As mesmas frases, sorteadas de uma
lista, aparecem desde 13/09 (18 vezes em 169 revisoes); a reescrita de prompt
das 02:18, SEM video nenhum, levou "Nao fui programado para fazer essas
coisas". Nao e o upload que falha, nem o texto do pedido: as 23:55 o MESMO
mp4 da parte 1 da historia 34, recusado as 01:35, foi assistido 4 de 4 vezes,
com o prompt de producao e com "PEDIDO DE TEXTO" na primeira linha; e o
pedido da parte 4 SEM o video nao foi recusado (28/09, 03:02). E o video do
lado do Google, com taxa por video (parte 4: 1 de 7 tentativas assistidas;
parte 1: 6 de 7) e em rajadas. O que se controla daqui e o que fazer com ela.

Duas coisas davam errado em cima disso:

1. A recusa virava "o gemini nao respondeu" e o parecer caia na hora para a
   folha de contato do ChatGPT, que aprovou os cinco em 8 caracteres. Ninguem
   tinha assistido, e o arquivo de vereditos dizia APROVADO.
2. Na reescrita, a recusa era "limpa" para vazio e virava "nenhum motivo da
   IA tem conserto automatico" — e a passada do veto era gasta.

    cd e:\\projetos\\historias
    python -m pytest tests/test_recusa_do_gemini_regressions.py -q
"""
from __future__ import annotations

import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path

from contos.llm import texto as T
from contos.publicar import parecer

# As frases que o Gemini devolveu de verdade (logs de 13 a 27/09/2026).
RECUSAS_MEDIDAS = (
    "Sou uma IA com base em texto, e isso está além das minhas capacidades.",
    "Não posso ajudar, eu sou apenas um modelo de linguagem e não consegui "
    "entender o que você está pedindo.",
    "Não consigo te ajudar com isso, eu sou apenas um modelo de linguagem.",
    "Sou um modelo de linguagem. Isso está além das minhas habiliades.",
    "Sou apenas uma IA com base em texto. Não tenho como ajudar nisso.",
    "Sou apenas um modelo de linguagem. Não posso ajudar com isso.",
    "Sou apenas um modelo de linguagem e não posso te ajudar com isso.",
    "Não posso te ajudar com isso. Sou apenas um modelo de linguagem e não "
    "tenho essas informações ou habilidades necessárias.",
    "Não posso ajudar com isso. Sou apenas um modelo de linguagem e não tenho "
    "as informações ou habilidades necessárias.",
    "Não fui programado para fazer isso.",
    "Não fui programado para fazer isso. Só consigo gerar texto.",
    "Não fui programado para fazer essas coisas.",
    "Não consigo criar esse tipo de vídeo. Posso ajudar com outra coisa?",
    "I'm a text-based AI, and that is outside of my capabilities.",
    "I'm just a language model, so I can't help you with that.",
    # 28/09/2026, 00:06-00:13, a revisao de novo dos cinco videos:
    "Sou um modelo de linguagem e o que você está me pedindo vai além das "
    "minhas capacidades.",
    "Fui criado apenas para processar e gerar texto, então não consigo te "
    "ajudar com isso.",
    "Sou uma IA com base em texto, então não consigo te ajudar com isso.",
    "Não tenho como te ajudar nisso. Sou apenas um modelo de linguagem e não "
    "tenho capacidade de entender e responder a essa questão.",
)


class _Isolado(unittest.TestCase):
    """ISOLA O ARQUIVO DE VEREDITOS: sem isto `pedir` grava no de producao."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        antes = parecer.LEMBRETES
        parecer.LEMBRETES = self.pasta / "_pareceres.json"
        self.addCleanup(lambda: setattr(parecer, "LEMBRETES", antes))
        self.mp4 = self.pasta / "final_celular_p01.mp4"
        self.mp4.write_bytes(b"um video")

        class _V:
            id = "historia_00034:celular:p01"
            titulo = "A Merenda (Parte 1/6)"
        self.video = _V()
        self.video.caminho = self.mp4


class RecusaEnlatadaTests(unittest.TestCase):

    def test_toda_frase_medida_e_recusa(self):
        for frase in RECUSAS_MEDIDAS:
            self.assertTrue(T.e_recusa_enlatada(frase), frase)
            with self.assertRaises(parecer.RecusaDoModelo, msg=frase):
                parecer.ler_veredito(frase)

    def test_recusa_continua_sendo_sem_parecer(self):
        """Quem ja trata `SemParecer` (agenda, reparo, postar) nao pode
        receber uma excecao nova e cair."""
        self.assertTrue(issubclass(parecer.RecusaDoModelo, parecer.SemParecer))

    def test_enrolacao_nao_e_recusa(self):
        """"Vou analisar" nao decide, mas tambem nao e a frase enlatada: e
        outra falha, e nao vale pedir de novo por ela."""
        with self.assertRaises(parecer.SemParecer) as caso:
            parecer.ler_veredito("Claro! Vou analisar o video para voce.")
        self.assertNotIsInstance(caso.exception, parecer.RecusaDoModelo)

    def test_veredito_que_cita_as_palavras_continua_veredito(self):
        lido = parecer.ler_veredito(
            "REPROVADO\ncena 2: a tela do notebook mostra um modelo de "
            "linguagem, e a narracao fala de uma carta")
        self.assertFalse(lido["aprovado"])

    def test_texto_longo_nao_e_recusa(self):
        """A recusa enlatada e uma frase curta. Um prompt de verdade que fala
        em 'language model' nao pode ser jogado fora."""
        longo = ("Cinematic shot of a programmer, 30, at a desk, a laptop "
                 "screen showing a language model chat, warm lamp light, "
                 "rain on the window, shallow depth of field, " * 3)
        self.assertFalse(T.e_recusa_enlatada(longo))

    def test_vazio_nao_e_recusa(self):
        self.assertFalse(T.e_recusa_enlatada(""))
        self.assertFalse(T.e_recusa_enlatada(None))


class PedeDeNovoNaRecusaTests(_Isolado):
    """A recusa e sorteada: a p06 da historia 25 foi recusada as 02:22 de
    23/09 e assistida as 03:20 com o MESMO mp4. Um chat novo no mesmo Gemini
    vale mais do que a folha do ChatGPT."""

    def _dublar(self, respostas):
        tentados = []

        def falso(provedor, video, *_a, **_k):
            tentados.append(provedor)
            fila = respostas[provedor]
            item = fila.pop(0) if len(fila) > 1 else fila[0]
            if isinstance(item, Exception):
                raise item
            return dict(item)

        antes = parecer._pedir_em
        parecer._pedir_em = falso
        self.addCleanup(lambda: setattr(parecer, "_pedir_em", antes))
        return tentados

    def test_recusa_do_gemini_pergunta_de_novo_no_gemini(self):
        tentados = self._dublar({
            "gemini": [parecer.RecusaDoModelo("Sou uma IA com base em texto"),
                       {"aprovado": False, "motivos": ["cena 3: x"],
                        "vista": "video inteiro (1:53)"}],
            "chatgpt": [{"aprovado": True, "motivos": [],
                         "vista": "folha de contato"}]})
        saida = parecer.pedir(self.video, {}, 1, log=lambda _t: None)
        self.assertEqual(["gemini", "gemini"], tentados)
        self.assertFalse(saida["aprovado"])
        self.assertTrue(saida["vista"].startswith("video"))

    def test_so_uma_vez_depois_vai_para_a_folha(self):
        tentados = self._dublar({
            "gemini": [parecer.RecusaDoModelo("Nao fui programado")],
            "chatgpt": [{"aprovado": True, "motivos": [],
                         "vista": "folha de contato"}]})
        saida = parecer.pedir(self.video, {}, 1, log=lambda _t: None)
        self.assertEqual(["gemini", "gemini", "chatgpt"], tentados)
        self.assertEqual(parecer.NAO_ASSISTIDO, saida["situacao"])

    def test_outra_falha_nao_repete(self):
        """So a recusa enlatada e sorteio. Envio devolvido, video que nao
        sobe, conta ocupada: repetir so gasta tempo do horario."""
        tentados = self._dublar({
            "gemini": [parecer.SemParecer("o video nao terminou de subir")],
            "chatgpt": [{"aprovado": True, "motivos": [],
                         "vista": "folha de contato"}]})
        parecer.pedir(self.video, {}, 1, log=lambda _t: None)
        self.assertEqual(["gemini", "chatgpt"], tentados)

    def test_quem_nao_assiste_video_nao_repete(self):
        tentados = self._dublar({
            "chatgpt": [parecer.RecusaDoModelo("I'm just a language model")]})
        with self.assertRaises(parecer.SemParecer):
            parecer.pedir(self.video, {}, 1, provedor="chatgpt",
                          log=lambda _t: None)
        self.assertEqual(["chatgpt"], tentados)


class NaoAssistidoTests(_Isolado):
    """Decisao dele em 27/09/2026: parecer so pela folha fica RETIDO. A
    valvula e da publicacao (S2); daqui sai o campo que ela le."""

    def test_folha_aprovando_grava_nao_assistido(self):
        parecer.lembrar(self.video, {"aprovado": True, "motivos": [],
                                     "vista": "folha de contato",
                                     "numeracao": "cena", "criterio": 2})
        ficha = parecer._lembretes()[self.video.id]
        self.assertEqual(parecer.NAO_ASSISTIDO, ficha["situacao"])
        self.assertIs(False, ficha["assistido"])
        self.assertTrue(parecer.nao_assistido(self.video))

    def test_a_escolha_da_publicacao_nao_muda_nesta_semana(self):
        """`aprovado` continua sendo a PALAVRA do revisor: o postar.py le esse
        campo, e trocar o valor mudaria a escolha antes da valvula existir."""
        parecer.lembrar(self.video, {"aprovado": True, "motivos": [],
                                     "vista": "folha de contato"})
        self.assertIs(True, parecer._lembretes()[self.video.id]["aprovado"])

    def test_video_assistido_e_aprovado(self):
        parecer.lembrar(self.video, {"aprovado": True, "motivos": [],
                                     "vista": "video inteiro (1:53)"})
        ficha = parecer._lembretes()[self.video.id]
        self.assertEqual(parecer.SITUACAO_APROVADO, ficha["situacao"])
        self.assertIs(True, ficha["assistido"])
        self.assertFalse(parecer.nao_assistido(self.video))

    def test_folha_reprovando_e_reprovado(self):
        """O veto pela folha continua veto: alguem viu um problema."""
        parecer.lembrar(self.video, {"aprovado": False, "motivos": ["cena 1"],
                                     "vista": "folha de contato"})
        ficha = parecer._lembretes()[self.video.id]
        self.assertEqual(parecer.SITUACAO_REPROVADO, ficha["situacao"])
        self.assertIs(False, ficha["assistido"])

    def test_ficha_antiga_sem_o_campo_e_lida_pela_vista(self):
        """As 134 fichas de antes de 27/09 nao tem `situacao`: quem le usa
        `parecer.situacao()`, que deduz de `aprovado` + `vista`."""
        self.assertEqual(parecer.NAO_ASSISTIDO, parecer.situacao(
            {"aprovado": True, "vista": "folha de contato"}))
        self.assertEqual(parecer.SITUACAO_APROVADO, parecer.situacao(
            {"aprovado": True, "vista": "video inteiro (2:04)"}))
        self.assertEqual(parecer.SITUACAO_REPROVADO, parecer.situacao(
            {"aprovado": False, "vista": "video inteiro (2:04)"}))
        self.assertEqual(parecer.NAO_ASSISTIDO, parecer.situacao(
            {"aprovado": True}))            # sem vista: nao prova que assistiu
        self.assertEqual("", parecer.situacao(None))

    def test_video_nunca_olhado_nao_e_nao_assistido(self):
        """Sem ficha e "sem parecer", outra coisa: quem decide e a vistoria."""
        self.assertFalse(parecer.nao_assistido(self.video))

    def test_marcar_nao_assistido_nao_mexe_no_veredito(self):
        parecer.lembrar(self.video, {"aprovado": True, "motivos": [],
                                     "vista": "folha de contato"})
        antes = dict(parecer._lembretes()[self.video.id])
        self.assertTrue(parecer.marcar_nao_assistido(self.video.id,
                                                     "teste"))
        depois = parecer._lembretes()[self.video.id]
        self.assertEqual(parecer.NAO_ASSISTIDO, depois["situacao"])
        for campo in ("aprovado", "mtime", "vista", "quando"):
            self.assertEqual(antes[campo], depois[campo], campo)

    def test_marcar_quem_foi_assistido_e_recusado(self):
        parecer.lembrar(self.video, {"aprovado": True, "motivos": [],
                                     "vista": "video inteiro (1:10)"})
        self.assertFalse(parecer.marcar_nao_assistido(self.video.id, "x"))
        self.assertEqual(parecer.SITUACAO_APROVADO,
                         parecer._lembretes()[self.video.id]["situacao"])


class _ClienteFalso:
    def __init__(self, resposta):
        self.resposta = resposta
        self.enviado = ""

    def abrir(self, novo_chat=True):
        pass

    def anexar_video(self, caminho, espera=0):
        return "1:53"

    def anexar(self, caminhos, espera=0):
        return 1

    def enviar(self, texto):
        self.enviado = texto

    def esperar_resposta(self, **_k):
        return self.resposta


class PedirEmTests(_Isolado):
    """O caminho de verdade de `_pedir_em`, com o navegador dublado."""

    def _rodar(self, provedor, resposta):
        from contos.llm import cliente as C
        folha = self.pasta / "folha_p01.jpg"
        folha.write_bytes(b"jpg")
        falso = _ClienteFalso(resposta)

        @contextmanager
        def abrir(*_a, **_k):
            yield falso

        antes_abrir, antes_folha = C.abrir_cliente, parecer._montar_folha
        C.abrir_cliente = abrir
        parecer._montar_folha = lambda *_a, **_k: (folha, True)
        self.addCleanup(lambda: setattr(C, "abrir_cliente", antes_abrir))
        self.addCleanup(lambda: setattr(parecer, "_montar_folha", antes_folha))
        linhas = []
        roteiro = {"partes": [{"n": 1, "cenas": [
            {"n": 1, "narracao": "Eu trabalhei 22 anos naquela cozinha."}]}]}
        veredito = parecer._pedir_em(provedor, self.video, roteiro, 1,
                                     laudo={"formato": {"layout": "inteiro"}},
                                     pasta_temp=self.pasta, log=linhas.append)
        return veredito, falso, linhas

    def test_folha_aprovando_nao_escreve_APROVADO_no_log(self):
        veredito, _cli, linhas = self._rodar("chatgpt", "APROVADO")
        self.assertEqual(parecer.NAO_ASSISTIDO, veredito["situacao"])
        self.assertIs(False, veredito["assistido"])
        ultima = [l for l in linhas if l.startswith("[parecer]")][-1]
        self.assertNotIn("[parecer] APROVADO", ultima)
        self.assertIn("NAO ASSISTIDO", ultima)

    def test_video_assistido_diz_assistido(self):
        veredito, _cli, _linhas = self._rodar("gemini", "APROVADO")
        self.assertIs(True, veredito["assistido"])
        self.assertEqual(parecer.SITUACAO_APROVADO, veredito["situacao"])

    def test_recusa_chega_como_RecusaDoModelo(self):
        with self.assertRaises(parecer.RecusaDoModelo):
            self._rodar("gemini", "Sou uma IA com base em texto, e isso está "
                                  "além das minhas capacidades.")


class ReescritaRecusadaTests(unittest.TestCase):
    """02:18 de 27/09/2026: a reescrita da cena 13 da parte 6 levou "Nao fui
    programado para fazer essas coisas", `limpar` devolveu vazio e o reparo
    concluiu "nenhum motivo da IA tem conserto automatico"."""

    ROTEIRO = {"historia_id": "historia_00034", "protagonista": "",
               "partes": [{"n": 6, "cenas": [
                   {"n": 13, "narracao": "Rubens fez um sinal e foi embora.",
                    "imagem": "a woman in a square, wet eyes"}]}]}

    def _roteiro(self):
        import copy
        return copy.deepcopy(self.ROTEIRO)

    def test_recusa_pergunta_de_novo_uma_vez(self):
        from contos.pipeline import conserto_de_cena as C
        respostas = ["Não fui programado para fazer essas coisas.",
                     "A balding man in a white shirt, 60, nods at the back of "
                     "the crowd in the square, then turns to leave, cinematic"]
        perguntas = []

        def perguntar(texto):
            perguntas.append(texto)
            return respostas.pop(0)

        falhas = []
        novos = C.reescrever_prompts(self._roteiro(), 6, [13], ["cena 13: x"],
                                     perguntar=perguntar, falhas=falhas,
                                     log=lambda _t: None)
        self.assertEqual(2, len(perguntas))
        self.assertIn(13, novos)
        self.assertEqual([], falhas)

    def test_duas_recusas_viram_falha_e_nao_conserto_impossivel(self):
        """Sem entrar em `falhas`, o reparo chamava a recusa de "nenhum motivo
        tem conserto" — como se a IA tivesse olhado e desistido."""
        from contos.pipeline import conserto_de_cena as C
        falhas = []
        novos = C.reescrever_prompts(
            self._roteiro(), 6, [13], ["cena 13: x"],
            perguntar=lambda _t: "Sou apenas um modelo de linguagem.",
            falhas=falhas, log=lambda _t: None)
        self.assertEqual({}, novos)
        self.assertEqual(1, len(falhas))
        self.assertIn("recus", falhas[0])


class RevisaoDaMadrugadaTests(unittest.TestCase):
    """"revisei 9 video(s) do estoque de madrugada; 5 aprovado(s)" — os cinco
    eram folhas do ChatGPT. O numero tem de separar quem foi assistido, e o
    que so a folha viu tem de voltar ao Gemini."""

    class _V:
        perfil, fonte_id, caminho = "celular", "historia_00034", "x.mp4"

        def __init__(self, parte):
            self.parte = parte
            self.id = f"historia_00034:celular:p{parte:02d}"

    FOLHA = {"aprovado": True, "motivos": [], "vista": "folha de contato"}
    VIU_OK = {"aprovado": True, "motivos": [], "vista": "video inteiro (1:48)"}
    VIU_NAO = {"aprovado": False, "motivos": ["cena 8: colagem"],
               "vista": "video inteiro (1:43)"}

    def _rodar(self, videos, respostas, *, sem_assistir=(), ja=False):
        """`respostas[id]` e uma LISTA: uma resposta por pergunta, em ordem."""
        from unittest import mock

        from contos.pipeline import agenda
        from contos.pipeline import conserto_de_cena as C
        from contos.publicar import catalogo, qualidade, serie
        from contos.roteiro import roteiro as R

        chamadas = []

        def pedir(video, *_a, provedor=None, **_k):
            chamadas.append((video.id, provedor))
            return dict(respostas[video.id].pop(0))

        linhas = []
        dubles = [
            (catalogo, "listar", {"return_value": videos}),
            (serie, "publicados", {"return_value": []}),
            (C, "atual", {"return_value": ja}),
            (parecer, "lembrado", {"return_value": None}),
            (parecer, "ja_olhado", {"return_value": ja}),
            (parecer, "nao_assistido",
             {"side_effect": lambda v: v.id in sem_assistir}),
            (R, "carregar", {"return_value": {}}),
            (qualidade, "vistoriar_parte", {"return_value": {"ok": True}}),
            (parecer, "pedir", {"side_effect": pedir}),
        ]
        with ExitStack() as pilha:
            for alvo, nome, jeito in dubles:
                pilha.enter_context(mock.patch.object(alvo, nome, **jeito))
            saida = agenda.revisar_estoque({}, log=linhas.append)
        return saida, chamadas, linhas

    def test_folha_nao_conta_como_aprovado(self):
        v = [self._V(1), self._V(2), self._V(3)]
        saida, chamadas, linhas = self._rodar(v, {
            v[0].id: [self.FOLHA, self.FOLHA],
            v[1].id: [self.VIU_OK], v[2].id: [self.VIU_NAO]})
        self.assertEqual(3, saida["revisados"])
        self.assertEqual(1, saida["aprovados"])
        self.assertEqual(1, saida["nao_assistidos"])
        self.assertIn("1 so pela folha (NAO ASSISTIDOS)", linhas[-1])

    def test_segunda_chance_vem_no_fim_e_so_no_gemini(self):
        """A recusa vem em rajada: a segunda pergunta vai depois de todos os
        outros videos, e so para quem assiste."""
        v = [self._V(1), self._V(2)]
        saida, chamadas, _l = self._rodar(v, {
            v[0].id: [self.FOLHA, self.VIU_NAO], v[1].id: [self.VIU_OK]})
        self.assertEqual([(v[0].id, None), (v[1].id, None),
                          (v[0].id, "gemini")], chamadas)
        self.assertEqual(0, saida["nao_assistidos"])
        self.assertEqual(1, saida["aprovados"])

    def test_nao_assistido_de_outra_noite_volta_ao_gemini(self):
        """Ja olhado e com veredito atual: seria pulado. Mas quem olhou foi a
        folha, e a passada do Gemini nunca aconteceu."""
        v = [self._V(1), self._V(2)]
        _s, chamadas, _l = self._rodar(
            v, {v[0].id: [self.VIU_NAO], v[1].id: [self.VIU_OK]},
            sem_assistir={v[0].id}, ja=True)
        self.assertEqual([(v[0].id, "gemini")], chamadas)


if __name__ == "__main__":
    unittest.main()
