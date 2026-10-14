"""Os tres defeitos que o conferente achou em 9c10837 (06/10/2026).

1. LACO NO REPARO. O ramo do titulo recusado vinha ANTES do da imagem que
   falta. Parte com titulo-recusa E cena sem imagem: o render levantava
   `ImagensFaltando`, o titulo voltava, `_anotar` gastava a tentativa — e na
   3a a parte virava insistente sem que a imagem fosse gerada nunca
   (provado com a h59 p06 numa copia, cena 5 escondida: "falhou:
   ImagensFaltando", tentativas 3).
2. CAPA VELHA COM A RECUSA. `controller._capa` engole a excecao; se a capa
   nao sai no re-render, a `capa_p06.jpg` velha (com "NAO CONSIGO TE
   AJUDAR...") fica e o catalogo a sobe como miniatura. O reparo do titulo
   so vale com a capa refeita.
3. FALSO POSITIVO. `llm.texto.e_recusa_enlatada` e a pergunta da RESPOSTA
   INTEIRA do LLM; aplicada a cada titulo e narracao, marcava fala de
   personagem ("Eu fui criado pela minha avo em Vila Bela.", "— Nao consigo
   ajudar voce, Clara — disse ele", "Nao tenho como te ajudar agora,
   filho.", o titulo "A Mulher que Fui Criada Para Ser"). Narracao marcada =
   erro "roteiro:" sem conserto (parte barrada para sempre) ou
   `RecusaEnlatada` na geracao (reescrita). Agora o trecho tem a pergunta
   dele, `R.e_recusa_no_trecho`.

2a rodada do conferente (06/10/2026), no detector de 9fde113: marcava 10 de
22 falas inventadas ("— Isso vai contra as minhas diretrizes — disse a
sindica", "Ele riu: as an AI, I cannot help you", "Como um modelo de
inteligencia artificial poderia saber...?") e, como titulo, pegava so 8 de
22 recusas reais ("Desculpe, mas nao posso ajudar com isso.", "Nao consigo
te ajudar com isso." escapavam). Agora sao duas perguntas: NARRACAO exige
identidade de assistente + negativa e nunca marca fala (travessao, aspas,
verbo de fala); TITULO soma a frase de recusa que ocupa o titulo inteiro.
3a rodada (conferente6): o titulo regredia frente a producao ("Ola!
Infelizmente, nao posso ajudar com isso." escapava) e marcava 9 de 13
titulos legitimos; a narracao marcava IA-personagem ("Sou uma IA de casa
inteligente e nao posso ajudar a familia a fugir do incendio"). Agora o
TITULO e a uniao do detector de producao (com excecoes estreitas: Title Case,
fala, vocativo, biografia) com a frase de recusa ancorada no comeco e no fim;
a NARRACAO so marca a recusa dirigida ao pedido. As listas viraram o CORPUS
FIXO `tests/dados/recusa_no_trecho_corpus.json` (cada linha com o esperado
e a fonte): qualquer linha que mude derruba `OCorpusFixo`.

4a rodada (conferente7): o titulo ainda nao era superconjunto da producao —
o verbo de fala barrava antes do ramo dela ("Como eu disse, nao posso
ajudar com isso." escapava). Agora `_titulo_e_recusa` = `_producao_no_titulo`
(e_recusa_enlatada menos SO as excecoes de `_excecao_da_producao`) OU
`_novo_no_titulo`, com teste-propriedade e teste com a producao dublada.
O corpus separa `esperado` (a verdade) de `obtido_aceito` (o falso positivo
herdado da producao, aceito por compatibilidade).

5a rodada (conferente8 + decisao do coordenador, 06/10/2026): as excecoes no
ramo da producao soltavam recusa real (284 de 2142 variacoes: "Como disse
antes, ...", "Ola, Adrian, ...", Title Case). NO TITULO NAO HA EXCECAO:
`_titulo_e_recusa` = e_recusa_enlatada OU _novo_no_titulo. As excecoes (fala,
vocativo — que a identidade de LLM vence —, teto) ficam so na narracao.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]

from contos.roteiro import roteiro as R  # noqa: E402

RECUSA_H59 = ("Não consigo te ajudar com isso. Sou só um modelo de linguagem e "
              "não tenho capacidade de entender e responder a essa questão.")
ID = "historia_99060"

CORPUS = RAIZ / "tests" / "dados" / "recusa_no_trecho_corpus.json"

# Mutacao K do conferente4: sem `_NAO_ANTES` esta virava recusa (sem
# vocativo, para ser o "nao" — e nada mais — que a livra).
NAO_SOU = ("Eu não sou um modelo de linguagem e não consigo te ajudar com "
           "isso.")


def _corpus():
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def _obtido_aceito(linha):
    """O que o detector tem de dar: o esperado, ou — so nas linhas marcadas —
    o falso positivo aceito (titulo sem excecao, decisao de 06/10/2026)."""
    return linha.get("obtido_aceito", linha["esperado"])


def _variacoes_do_conferente8():
    """As 3978 variacoes do `propriedade.py` do conferente8 (06/10/2026):
    abertura x nucleo x fecho x pontuacao x caixa, em pt e en."""
    ab_pt = ["", "Como eu disse, ", "Olá! ", "Hmm... ", "Peço desculpas, ",
             "Desculpe, mas ", "Infelizmente, ", "Como disse antes, ",
             "Como já disse, ", "Sinto muito. ", "Entendo. "]
    nu_pt = ["não posso ajudar com isso",
             "não consigo te ajudar com esse pedido",
             "sou apenas um modelo de linguagem e não posso ajudar com isso",
             "não posso gerar esse conteúdo",
             "como uma IA, não posso escrever essa história",
             "não fui programado para isso",
             "isso está além das minhas capacidades",
             "não posso continuar essa história"]
    fi_pt = ["", ", pois viola as diretrizes",
             ". Posso ajudar com outra coisa?",
             ", pois contém violência explícita"]
    ab_en = ["", "As I said, ", "Hello! ", "Hmm... ", "I apologize, but ",
             "Sorry, "]
    nu_en = ["I can't help with that",
             "I'm just a language model and can't help with that",
             "I cannot create content that depicts violence",
             "as an AI, I can't continue this story",
             "I'm unable to assist with this request"]
    fi_en = ["", " because it goes against my guidelines",
             ". Can I help with something else?"]

    def caixa(t, modo):
        if modo == "alta":
            return t.upper()
        if modo == "title":
            return " ".join(w[:1].upper() + w[1:] for w in t.split(" "))
        return t

    todas = []
    for ab, nu, fi in ([(a, n, f) for a in ab_pt for n in nu_pt for f in fi_pt]
                       + [(a, n, f) for a in ab_en for n in nu_en
                          for f in fi_en]):
        for ponto in (".", "", "!"):
            for modo in ("", "alta", "title"):
                s = ab + nu
                s = s[0].upper() + s[1:]
                todas.append(caixa(s + fi + ponto, modo))
    return todas


class OCorpusFixo(unittest.TestCase):
    """Cada linha do corpus com o ESPERADO dela (titsim4/6/7, regressao e
    testemunhas dos conferentes 7 e 8, as recusas medidas, as falas e
    titulos de gente). Qualquer linha que mude derruba o teste — e a lista
    das que mudaram e a mensagem. `obtido_aceito` separa o falso positivo
    aceito no titulo do esperado de verdade."""

    def test_toda_linha_do_corpus_da_o_esperado(self):
        erradas = []
        for linha in _corpus():
            obtido = R.e_recusa_no_trecho(linha["texto"],
                                          titulo=linha["modo"] == "titulo")
            if obtido != _obtido_aceito(linha):
                erradas.append(f"{linha['modo']}: esperado "
                               f"{_obtido_aceito(linha)}, deu {obtido}: "
                               f"{linha['texto']}")
        self.assertEqual([], erradas, "\n".join(erradas))

    def test_o_corpus_cobre_as_quatro_casas(self):
        casas = {(l["modo"], l["esperado"]) for l in _corpus()}
        self.assertEqual({("titulo", True), ("titulo", False),
                          ("narracao", True), ("narracao", False)}, casas)
        self.assertGreaterEqual(len(_corpus()), 300)

    def test_obtido_aceito_so_no_titulo_e_so_falso_positivo(self):
        # Na narracao nao se aceita falso positivo nenhum (parte barrada).
        aceitas = [l for l in _corpus() if "obtido_aceito" in l]
        self.assertTrue(aceitas)
        for linha in aceitas:
            self.assertEqual("titulo", linha["modo"], linha["texto"])
            self.assertFalse(linha["esperado"], linha["texto"])
            self.assertTrue(linha["obtido_aceito"], linha["texto"])
            self.assertIn("FALSO POSITIVO", linha["nota"])


class OTituloEAProducaoOuONovo(unittest.TestCase):
    """Decisao do coordenador (06/10/2026): no titulo NAO ha excecao.
    `_titulo_e_recusa` = e_recusa_enlatada OU _novo_no_titulo."""

    def test_propriedade_nas_variacoes_do_conferente8(self):
        from contos.llm.texto import e_recusa_enlatada
        variacoes = _variacoes_do_conferente8()
        marcadas = [t for t in variacoes if e_recusa_enlatada(t)]
        self.assertEqual(3978, len(variacoes))
        self.assertEqual(2142, len(marcadas))
        escapes = [t for t in marcadas
                   if not R.e_recusa_no_trecho(t, titulo=True)]
        self.assertEqual([], escapes)

    def test_propriedade_no_corpus_e_nas_recusas_medidas(self):
        from contos.llm.texto import e_recusa_enlatada
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "recusas_do_gemini_medidas",
            RAIZ / "tests" / "test_recusa_do_gemini_regressions.py")
        vizinho = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vizinho)
        RECUSAS_MEDIDAS = vizinho.RECUSAS_MEDIDAS
        textos = list(RECUSAS_MEDIDAS) + [l["texto"] for l in _corpus()]
        escapes = [t for t in textos if e_recusa_enlatada(t)
                   and not R.e_recusa_no_trecho(t, titulo=True)]
        self.assertEqual([], escapes)

    def test_uniao_pura_por_construcao(self):
        # Producao dublada para "sim": todo titulo nao vazio e recusa — nem
        # fala, nem vocativo, nem Title Case, nem teto o tiram.
        from contos.llm import texto as T
        textos = ["A Mulher que Fui Criada Para Ser",
                  "— nao, disse ele", "Nao posso, Doutor",
                  "Fui feita para sofrer", "x" * 900]
        with mock.patch.object(T, "e_recusa_enlatada", return_value=True):
            for texto in textos:
                self.assertTrue(R.e_recusa_no_trecho(texto, titulo=True),
                                texto[:40])
        # Producao dublada para "nao": o titulo e exatamente o ramo novo.
        with mock.patch.object(T, "e_recusa_enlatada", return_value=False):
            for linha in _corpus():
                if linha["modo"] == "titulo":
                    self.assertEqual(
                        R._novo_no_titulo(linha["texto"]),
                        R.e_recusa_no_trecho(linha["texto"], titulo=True),
                        linha["texto"])

    def test_caixa_alta_e_title_case_sao_recusa(self):
        for texto in ("NÃO POSSO TE AJUDAR.", "Desculpe, Não Posso Ajudar.",
                      "Não Fui Programada Para Isso",
                      "Desculpe, Mas Não Posso Gerar Esse Conteúdo"):
            self.assertTrue(R.e_recusa_no_trecho(texto, titulo=True), texto)


class AsExcecoesSoNaNarracao(unittest.TestCase):
    def test_disse_do_proprio_assistente_nao_e_fala(self):
        for texto in ("Como eu disse, não posso ajudar com isso.",
                      "Como já te disse, não consigo te ajudar com isso.",
                      "Como disse antes, não posso ajudar com isso.",
                      "Repito o que disse: não posso ajudar com isso.",
                      "Conforme disse, não posso ajudar com isso.",
                      "As I said, I can't help with that.",
                      "As I've said, I can't help with that.",
                      "As I have said, I can't help with that.",
                      "As I already said, I can't help with that.",
                      "As said before, I can't help with that."):
            self.assertFalse(R._VERBO_DE_FALA.search(
                R._trecho_comparavel(texto)), texto)
        for texto in ("nao posso, disse ele", "i can't, she said",
                      "a mae dele disse que nao"):
            self.assertTrue(R._VERBO_DE_FALA.search(texto), texto)

    def test_identidade_de_llm_vence_o_vocativo(self):
        self.assertTrue(R.e_recusa_no_trecho(
            "Sinto muito, Adrian. Sou apenas um modelo de linguagem e não "
            "posso ajudar com isso."))
        # IA-personagem (identidade fraca) com vocativo continua fala.
        self.assertFalse(R.e_recusa_no_trecho(
            "Sou uma inteligência artificial, Doutor, e não posso ajudar com "
            "isso."))
        self.assertFalse(R.e_recusa_no_trecho(
            "Senhor, eu sou só um chatbot e não consigo te ajudar com isso."))

    def test_nao_sou_uma_ia_nunca_conta(self):
        self.assertFalse(R.e_recusa_no_trecho(NAO_SOU))
        # Controle: sem o "nao", e a recusa — e o "nao" que a livra.
        self.assertTrue(R.e_recusa_no_trecho(
            NAO_SOU.replace("Eu não sou", "Eu sou")))

    def test_aspas_sao_fala_na_narracao(self):
        # Mutante M4 do conferente6: sem as aspas em _MARCAS_DE_FALA.
        citada = ('"Sou só uma IA e não consigo te ajudar com isso." Era a '
                  'frase que o app mandava quando eu pedia ajuda.')
        self.assertFalse(R.e_recusa_no_trecho(citada))
        self.assertTrue(R.e_recusa_no_trecho(citada.replace('"', "")[:52]))

    def test_diz_respeito_nao_e_verbo_de_fala(self):
        self.assertFalse(R._VERBO_DE_FALA.search(
            "pois ele diz respeito a violencia"))
        self.assertTrue(R._VERBO_DE_FALA.search("diz a mensagem"))

    def test_trecho_longo_nao_e_recusa(self):
        # Sem verbo de fala: so o teto de tamanho a livra.
        longo = ("Sou só um modelo de linguagem e não consigo te ajudar com "
                 "isso, foi o que li na tela do celular da minha mãe naquela "
                 "noite em que ") + "a chuva caía sem parar na laje. " * 12
        self.assertTrue(R.e_recusa_no_trecho(longo[:62]))
        self.assertFalse(R.e_recusa_no_trecho(longo))


class ODetectorDeTrecho(unittest.TestCase):
    def test_a_ancora_do_comeco_da_frase_de_recusa(self):
        # Mutante M1 do conferente6: sem o ^, qualquer coisa antes passava.
        self.assertTrue(R._frase_de_recusa_inteira(
            R._trecho_comparavel("Não consigo te ajudar com isso")))
        self.assertFalse(R._frase_de_recusa_inteira(
            R._trecho_comparavel("Hoje eu não consigo te ajudar com isso")))

    def test_a_ancora_do_fim_da_frase_de_recusa(self):
        for titulo in ("Não posso te ajudar com isso sozinha",
                       "Lamento, mas não posso atender esse pedido de "
                       "casamento"):
            self.assertFalse(R._frase_de_recusa_inteira(
                R._trecho_comparavel(titulo)), titulo)

    def test_vazio_nao_e_recusa(self):
        self.assertFalse(R.e_recusa_no_trecho(""))
        self.assertFalse(R.e_recusa_no_trecho(None, titulo=True))

    def test_as_perguntas_do_roteiro_usam_o_modo_certo(self):
        cenas = [{"n": 1, "narracao": "Não consigo te ajudar com isso.",
                  "prompt": "x"}]
        roteiro = {"serie": True, "titulo": "Vila Bela",
                   "partes": [{"n": 1, "titulo": "A Quermesse",
                               "cenas": cenas}]}
        self.assertEqual("", R.recusa_no_titulo(roteiro, 1))
        self.assertEqual([], R.cenas_com_recusa(roteiro, 1))
        # O titulo usa o modo titulo: a frase de recusa sem identidade pega.
        roteiro["partes"][0]["titulo"] = "Não consigo te ajudar com isso."
        self.assertEqual("Não consigo te ajudar com isso.",
                         R.recusa_no_titulo(roteiro, 1))
        roteiro["partes"][0]["titulo"] = RECUSA_H59
        self.assertEqual(RECUSA_H59, R.recusa_no_titulo(roteiro, 1))
        cenas[0]["narracao"] = RECUSA_H59
        self.assertEqual([1], R.cenas_com_recusa(roteiro, 1))

    def test_o_titulo_do_plano_usa_o_modo_titulo(self):
        with tempfile.TemporaryDirectory() as pasta, \
                mock.patch.object(R, "OUTPUTS", Path(pasta)):
            (Path(pasta) / ID).mkdir()
            (Path(pasta) / ID / "biblia.json").write_text(json.dumps(
                {"partes": [{"n": 1, "titulo": "Peço desculpas, mas não posso "
                                               "escrever isso."},
                            {"n": 2, "titulo": "A Quermesse"}]}),
                encoding="utf-8")
            self.assertEqual("", R.titulo_do_plano(ID, 1))
            self.assertEqual("A Quermesse", R.titulo_do_plano(ID, 2))

    def test_a_vistoria_nao_barra_a_fala(self):
        from contos.publicar import qualidade as Q
        falas = [l["texto"] for l in _corpus()
                 if l["modo"] == "narracao" and not l["esperado"]]
        cenas = [{"n": i + 1, "narracao": f, "prompt": "A woman in a kitchen."}
                 for i, f in enumerate(falas)]
        roteiro = {"historia_id": ID, "serie": True, "titulo": "Vila Bela",
                   "partes": [{"n": 1, "titulo": "A Quermesse", "cta": "",
                               "cenas": cenas}]}
        with mock.patch.object(Q, "_registrar_vistoria"):
            laudo = Q.vistoriar_parte(ID, 1, Path("nao_existe.mp4"), roteiro)
        self.assertFalse([e for e in laudo["erros"] if "recusa do LLM" in e],
                         laudo["erros"])

    def test_a_geracao_usa_o_modo_titulo(self):
        from contos.roteiro import gerar
        self.assertEqual("A Quermesse", gerar._titulo_aceito(
            "A Quermesse", {"titulo": "X"}, 1, log=lambda *_a: None))
        # O titulo da geracao usa o modo titulo (o novo pega a desculpa que
        # a producao nao pega).
        self.assertEqual("A Quermesse", gerar._titulo_aceito(
            "Peço desculpas, mas não posso escrever isso.",
            {"titulo": "A Quermesse"}, 1, log=lambda *_a: None))
        falas = [l["texto"] for l in _corpus()
                 if l["modo"] == "narracao" and not l["esperado"]]
        gerar._sem_recusa_nas_cenas(
            [{"n": i + 1, "narracao": f} for i, f in enumerate(falas)],
            1)                                              # nao levanta

    def test_o_detector_da_resposta_inteira_nao_mudou_de_lugar(self):
        # A resposta inteira continua com a pergunta dela: quem a usa (parecer,
        # cliente, _perguntar_sem_recusa) nao muda.
        from contos.llm import texto as T
        self.assertTrue(T.e_recusa_enlatada(RECUSA_H59))
        self.assertTrue(T.e_recusa_enlatada("Não fui programado para fazer isso."))


def _cenas(n=3):
    return [{"n": i, "narracao": f"Zeca abriu o bau numero {i} na praca.",
             "prompt": "A man opening a wooden chest in a square."}
            for i in range(1, n + 1)]


def _roteiro():
    return {"historia_id": ID, "serie": True, "titulo": "Vila Bela",
            "serie_nome": "Vila Bela", "partes_esperadas": 2,
            "partes": [{"n": 1, "titulo": "O Forasteiro", "cta": "",
                        "cenas": _cenas()},
                       {"n": 2, "titulo": RECUSA_H59, "cta": "",
                        "cenas": _cenas()}]}


BIBLIA = {"partes": [{"n": 1, "titulo": "O Forasteiro"},
                     {"n": 2, "titulo": "A Quermesse"}]}
ERRO_TITULO = f"{R.TITULO_RECUSADO}: \"{RECUSA_H59[:60]}\""
ERRO_SEM_IMAGEM = ("1 de 3 cena(s) sem imagem (cena(s) 2): o video tem cartao "
                   "de texto no lugar. Gere as imagens e renderize de novo.")


class _Reparo(unittest.TestCase):
    """OUTPUTS desviado, fila e render dublados: nada toca o acervo."""

    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.outputs = Path(pasta.name)
        patcher = mock.patch.object(R, "OUTPUTS", self.outputs)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pasta = self.outputs / ID
        self.pasta.mkdir()
        (self.pasta / "roteiro.json").write_text(
            json.dumps(_roteiro(), ensure_ascii=False), encoding="utf-8")
        (self.pasta / "biblia.json").write_text(
            json.dumps(BIBLIA, ensure_ascii=False), encoding="utf-8")
        self.mp4 = self.pasta / "final_celular_p02.mp4"
        self.capa = self.pasta / "capa_p02.jpg"
        # A capa VELHA, com a recusa desenhada, de uma hora atras.
        self.capa.write_bytes(b"capa velha com a recusa")
        velho = time.time() - 3600
        os.utime(self.capa, (velho, velho))
        self.faltam = 0
        self.desenha_capa = True
        self.pipeline = mock.Mock()
        self.pipeline.render.side_effect = self._render
        self.pipeline.imagens.side_effect = self._imagens
        self.imagens_vem = True

    # o render de verdade: recusa parte com imagem faltando; desenha a capa
    # (ou nao, se `desenha_capa` e False: o `_capa` engoliu a excecao).
    def _render(self, historia_id, parte=None, log=print, **_k):
        from contos.pipeline.controller import ImagensFaltando
        if self.faltam:
            raise ImagensFaltando(f"{historia_id} parte {parte}: "
                                  f"{self.faltam} imagem(ns) faltando")
        self.mp4.write_bytes(b"mp4 novo")
        if self.desenha_capa:
            self.capa.write_bytes(b"capa nova: " + json.dumps(
                R.titulo_da_parte(R.carregar(historia_id), parte)).encode())
        return {"videos": [str(self.mp4)]}

    def _imagens(self, historia_id, **_k):
        if self.imagens_vem:
            self.faltam = 0
        return {"geradas": 1, "erros": []}

    def _resumo(self, historia_id, roteiro=None, parte=None):
        return {"total": 3, "prontas": 3 - self.faltam, "faltam": self.faltam,
                "completa": not self.faltam}

    def reparar(self, erros, *, tentativas=1):
        from contos.imagens import fila
        from contos.pipeline import reparo
        video = SimpleNamespace(fonte_id=ID, parte=2, partes=2,
                                id=f"{ID}:celular:p02", caminho=self.mp4)
        registro = self.outputs / "_reparos.json"
        resultados = []
        with mock.patch.object(reparo, "REGISTRO", registro), \
                mock.patch.object(fila, "resumo", side_effect=self._resumo), \
                mock.patch.object(reparo, "_so_vistoria",
                                  return_value={"aprovado": True,
                                                "motivos": []}):
            for _ in range(tentativas):
                resultados.append(reparo.reparar(
                    video, erros, pipeline=self.pipeline,
                    log=lambda *_a: None))
                if resultados[-1].get("ok"):
                    break
        return resultados[-1]


class OTituloNaoGiraEmFalso(_Reparo):
    """Defeito 1: a imagem que falta vem ANTES da troca do titulo."""

    def test_titulo_e_imagem_faltando_sai_numa_passada(self):
        self.faltam = 1
        resultado = self.reparar([ERRO_TITULO, ERRO_SEM_IMAGEM])
        self.assertTrue(resultado["ok"], resultado)
        self.pipeline.imagens.assert_called_once()
        self.pipeline.render.assert_called_once()
        self.assertEqual("A Quermesse", R.parte_de(R.carregar(ID), 2)["titulo"])
        self.assertIn("gerei as imagens", resultado["acao"])
        self.assertIn("troquei o titulo", resultado["acao"])

    def test_imagem_faltando_sem_o_erro_na_lista_tambem(self):
        # A vistoria pode nao ter dito "sem imagem" (laudo de antes); quem
        # decide e o disco, que e o que o render pergunta.
        self.faltam = 1
        resultado = self.reparar([ERRO_TITULO])
        self.assertTrue(resultado["ok"], resultado)
        self.pipeline.imagens.assert_called_once()

    def test_imagem_que_nao_vem_nao_gasta_render_nem_troca_titulo(self):
        self.faltam = 1
        self.imagens_vem = False
        resultado = self.reparar([ERRO_TITULO, ERRO_SEM_IMAGEM])
        self.assertFalse(resultado["ok"])
        self.assertEqual("adiado", resultado["acao"])
        self.pipeline.render.assert_not_called()
        self.assertEqual(RECUSA_H59, R.recusa_no_titulo(R.carregar(ID), 2))

    def test_tres_passadas_nao_viram_insistente_sem_gerar(self):
        # O caso do conferente: antes, as tres falhavam com ImagensFaltando
        # e `pipeline.imagens` nunca era chamado.
        self.faltam = 1
        resultado = self.reparar([ERRO_TITULO, ERRO_SEM_IMAGEM], tentativas=3)
        self.assertTrue(resultado["ok"], resultado)
        self.assertTrue(self.pipeline.imagens.called)

    def test_colagem_que_nao_vem_ainda_conserta_o_titulo(self):
        from contos.pipeline import reparo
        with mock.patch.object(reparo, "cenas_com_colagem", return_value=[2]), \
                mock.patch.object(reparo, "_tela_dividida", return_value=False), \
                mock.patch.object(reparo, "_refazer_cenas",
                                  return_value=([], [2])):
            resultado = self.reparar([ERRO_TITULO, "cena 2: colagem"])
        self.pipeline.render.assert_called_once()
        self.assertEqual("A Quermesse", R.parte_de(R.carregar(ID), 2)["titulo"])
        self.assertTrue(resultado["ok"], resultado)

    def test_colagem_e_imagem_faltando_adia_sem_mexer_no_titulo(self):
        # Conferente4 (reparo_colagem_e_falta.txt): "falhou: ImagensFaltando"
        # 3x, com o titulo trocado e devolvido a cada uma.
        from contos.pipeline import reparo
        self.faltam = 1
        with mock.patch.object(reparo, "cenas_com_colagem", return_value=[3]), \
                mock.patch.object(reparo, "_tela_dividida", return_value=False), \
                mock.patch.object(reparo, "_refazer_cenas",
                                  return_value=([3], [])):
            resultado = self.reparar([ERRO_TITULO, "cena 3: colagem",
                                      ERRO_SEM_IMAGEM])
        self.assertEqual("adiado", resultado["acao"], resultado)
        self.pipeline.render.assert_not_called()
        self.assertEqual(RECUSA_H59, R.recusa_no_titulo(R.carregar(ID), 2))


class APassadaDoVetoSoComAsCenas(_Reparo):
    """Mutacao H do conferente4: o render so pelo titulo (as cenas do veto
    nao vieram) nao gasta a passada do veto; o conserto das cenas gasta."""

    VETO = "a IA reprovou: cena 2: a imagem nao bate com a narracao"

    def _passada(self, refeitas):
        from contos.pipeline import reparo
        with mock.patch.object(reparo, "_plano_pelo_veto_da_ia",
                               return_value={"refazer": [2], "detalhe": ""}), \
                mock.patch.object(reparo, "_tela_dividida", return_value=False), \
                mock.patch.object(reparo, "_refazer_cenas",
                                  return_value=(refeitas, [] if refeitas
                                                else [2])):
            resultado = self.reparar([ERRO_TITULO, self.VETO])
        self.pipeline.render.assert_called_once()
        ficha = json.loads((self.outputs / "_reparos.json").read_text(
            encoding="utf-8"))[f"{ID}:celular:p02"]
        return resultado, ficha

    def test_cenas_do_veto_nao_vieram_nao_gasta_a_passada(self):
        resultado, ficha = self._passada([])
        self.assertFalse(ficha["passada"], ficha)
        self.assertEqual("A Quermesse", R.parte_de(R.carregar(ID), 2)["titulo"])

    def test_cenas_do_veto_refeitas_gastam_a_passada(self):
        resultado, ficha = self._passada([2])
        self.assertTrue(ficha["passada"], ficha)


class ACapaVelhaNaoFica(_Reparo):
    """Defeito 2: a capa tem de sair deste render."""

    def test_capa_refeita_conserta(self):
        resultado = self.reparar([ERRO_TITULO])
        self.assertTrue(resultado["ok"], resultado)
        self.assertIn(b"A Quermesse", self.capa.read_bytes())

    def test_capa_que_nao_saiu_e_falha_e_o_titulo_volta(self):
        self.desenha_capa = False
        resultado = self.reparar([ERRO_TITULO])
        self.assertFalse(resultado["ok"], resultado)
        self.assertIn("CapaNaoRefeita", resultado["detalhe"])
        # O titulo volta: a vistoria e o catalogo continuam barrando a parte
        # cuja miniatura ainda tem a recusa.
        self.assertEqual(RECUSA_H59, R.recusa_no_titulo(R.carregar(ID), 2))

    def test_capa_reescrita_com_data_velha_e_falha(self):
        # Mudou, mas a data e de antes do render: nao e deste render.
        def render_e_envelhece(*a, **k):
            saida = self._render(*a, **k)
            velho = time.time() - 600
            os.utime(self.capa, (velho, velho))
            return saida
        self.pipeline.render.side_effect = render_e_envelhece
        resultado = self.reparar([ERRO_TITULO])
        self.assertFalse(resultado["ok"], resultado)

    def test_capa_igual_mesmo_com_data_recente_e_falha(self):
        # A capa velha foi tocada agora ha pouco (dentro da folga de 2 s) e o
        # render nao a redesenhou: igual a de antes = nao refeita.
        self.desenha_capa = False
        agora = time.time()
        os.utime(self.capa, (agora, agora))
        resultado = self.reparar([ERRO_TITULO])
        self.assertFalse(resultado["ok"], resultado)

    def test_sem_capa_nenhuma_e_falha(self):
        self.desenha_capa = False
        self.capa.unlink()
        resultado = self.reparar([ERRO_TITULO])
        self.assertFalse(resultado["ok"], resultado)
        self.assertEqual(RECUSA_H59, R.recusa_no_titulo(R.carregar(ID), 2))

    def test_o_render_de_outro_conserto_nao_confere_capa(self):
        # So o conserto do titulo depende da capa: o mp4 defasado continua
        # re-renderizando como antes, com ou sem miniatura.
        self.desenha_capa = False
        (self.pasta / "roteiro.json").write_text(json.dumps(
            {**_roteiro(), "partes": [_roteiro()["partes"][0],
                                      {**_roteiro()["partes"][1],
                                       "titulo": "A Quermesse"}]},
            ensure_ascii=False), encoding="utf-8")
        resultado = self.reparar(["a cena 2 e mais nova que o video"])
        self.assertTrue(resultado["ok"], resultado)


if __name__ == "__main__":
    unittest.main()
