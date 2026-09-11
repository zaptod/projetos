# -*- coding: utf-8 -*-
"""Contratos da historia LONGA em partes e da geracao automatica.

O que este arquivo trava:

1. BIBLIA. A etapa 1 pede (e o parser le) o que a etapa 2 precisa: titulo,
   descricao FISICA do protagonista e o arco de cada parte. Sem a descricao
   fisica, 80 imagens saem de 80 pessoas diferentes.
2. PARTE. O prompt da parte 1 abre com o choque; o das partes seguintes
   recapitula em uma frase; o da ultima fecha a pergunta central. E todos
   carregam a descricao do protagonista.
3. PARTES NA PIPELINE. Uma parte = um video. As cenas nao colidem entre
   partes (p03_cena_07 nao sobrescreve p01_cena_07), o plano e por parte e o
   catalogo lista um video por parte, em ORDEM.
4. RESPOSTA CORTADA. Os sites cortam mensagem longa: quando vem menos cena
   do que se pediu, o proximo turno e "continue da cena N" - nunca uma
   tentativa nova do zero.
5. CLIENTE DE LLM. As duas provas que a automacao exige: envio so e envio
   quando o campo esvazia (ou o botao de parar aparece), e resposta so e
   resposta quando o texto PARA de crescer.

Rode de dentro de historias/:
    python -m unittest tests.test_serie_regressions -v
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from contos.imagens import fila                                    # noqa: E402
from contos.llm import cliente as llm_cliente                      # noqa: E402
from contos.publicar import catalogo                               # noqa: E402
from contos.roteiro import gerar                                   # noqa: E402
from contos.roteiro import roteiro as R                            # noqa: E402
from contos.roteiro import serie as S                              # noqa: E402
from contos.roteiro.modelo import carregar_config                  # noqa: E402
from contos.video import timeline                                  # noqa: E402

CONFIG = carregar_config()

BIBLIA_CRUA = """TITULO DA SERIE: Eu descobri o que meu pai escondia na garagem
PREMISSA: Um homem herda a casa do pai e acha uma porta que nao existia na planta. A pergunta e o que o pai guardava ali por trinta anos.
PROTAGONISTA: Tiago | a man in his late thirties, shaved head, thin scar on the chin, worn denim jacket
ELENCO: Dona Irene | an elderly woman in her eighties, silver bun, floral cardigan; Marcos | a heavyset man in his fifties, moustache, mechanic overalls
CENARIO: a narrow two-story house and its garage in a small coastal town, humid and overcast
VIRADA CENTRAL: a porta leva a um comodo com fichas de desaparecidos, e sai na parte 4

PARTE 1
TITULO: A porta que nao estava na planta
RESUMO: Tiago encontra a porta atras de uma estante. A fechadura e nova.
GANCHO: A planta da casa nao tem essa porta.
CLIFFHANGER: Do outro lado tem luz acesa.

PARTE 2
TITULO: A chave que a vizinha tinha
RESUMO: Dona Irene entrega uma chave e diz que prometeu nao contar.
GANCHO: A vizinha me deu a chave antes de eu perguntar.
CLIFFHANGER: Ela sabia o meu nome do meio.

PARTE 3
TITULO: O que estava do outro lado
RESUMO: O comodo esta organizado e limpo demais.
GANCHO: Tinha cafe quente na mesa.
CLIFFHANGER: FINAL - o pai guardava as fichas dos desaparecidos que ele procurava.
"""


def _biblia() -> dict:
    return S.parse_biblia(BIBLIA_CRUA, 3)


def _cenas(quantidade: int, prefixo: str = "fala") -> list:
    return [{"n": i, "imagem": f"a man in a dim room, moment {i}, night",
             "tempo": 4.0, "narracao": f"{prefixo} {i}."}
            for i in range(1, quantidade + 1)]


def _serie(partes: int = 3, cenas: int = 5) -> dict:
    dados = {
        "historia_id": "historia_00099", "titulo": "A serie",
        "protagonista": "a man in his thirties, shaved head",
        "partes": [{"n": k, "titulo": f"Parte {k} - titulo",
                    "cliffhanger": "e ai?", "cenas": _cenas(cenas, f"p{k}")}
                   for k in range(1, partes + 1)],
    }
    return R.normalizar(dados)


# -------------------------------------------------------------- 1. biblia
class BibliaTests(unittest.TestCase):
    def test_o_prompt_pede_o_que_a_etapa_2_precisa(self):
        texto = S.prompt_biblia(partes=4, cenas_por_parte=12, config=CONFIG)
        self.assertIn("ETAPA 1", texto)
        self.assertIn("nao escreva narracao", texto.lower())
        for rotulo in ("TITULO DA SERIE:", "PROTAGONISTA:", "VIRADA CENTRAL:",
                       "GANCHO:", "CLIFFHANGER:"):
            self.assertIn(rotulo, texto)
        # o arco tem que ser pedido parte a parte
        for k in range(1, 5):
            self.assertIn(f"PARTE {k}", texto)
        # e a consistencia visual e obrigatoria, senao as imagens divergem
        self.assertIn("ingles", texto.lower())
        self.assertIn("4 PARTES de 12 cenas", texto)

    def test_le_a_biblia_inteira(self):
        biblia = _biblia()
        self.assertEqual("Eu descobri o que meu pai escondia na garagem",
                         biblia["titulo"])
        self.assertEqual("Tiago", biblia["protagonista_nome"])
        self.assertIn("shaved head", biblia["protagonista"])
        self.assertIn("Dona Irene", biblia["elenco"])
        self.assertEqual(3, len(biblia["partes"]))
        self.assertEqual("A porta que nao estava na planta",
                         biblia["partes"][0]["titulo"])
        self.assertEqual("Do outro lado tem luz acesa.",
                         biblia["partes"][0]["cliffhanger"])
        self.assertTrue(biblia["partes"][2]["cliffhanger"].startswith("FINAL"))

    def test_biblia_incompleta_e_acusada(self):
        self.assertEqual([], S.problemas_da_biblia(_biblia()))
        capenga = S.parse_biblia("PREMISSA: so isso", 3)
        problemas = " ".join(S.problemas_da_biblia(capenga))
        self.assertIn("TITULO", problemas)
        self.assertIn("protagonista", problemas)
        self.assertIn("PARTE", problemas)

    def test_biblia_com_menos_partes_do_que_o_pedido(self):
        problemas = S.problemas_da_biblia(S.parse_biblia(BIBLIA_CRUA, 8))
        self.assertTrue(any("3 parte(s) planejadas de 8" in p for p in problemas))


# --------------------------------------------------------------- 2. parte
class PromptDaParteTests(unittest.TestCase):
    def test_parte_1_abre_com_o_choque(self):
        texto = S.prompt_parte(_biblia(), 1, cenas=12, config=CONFIG)
        self.assertIn("HISTORIA INTEIRA", texto)
        self.assertIn("Escreva exatamente 12 cenas", texto)
        self.assertNotIn("recapitula", texto)

    def test_parte_do_meio_recapitula_e_termina_em_cliffhanger(self):
        texto = S.prompt_parte(_biblia(), 2, config=CONFIG)
        self.assertIn("recapitula", texto)
        # o recap tem que ser um gancho NOVO: "no episodio anterior" entra no
        # prompt como PROIBICAO, nunca como sugestao de abertura
        self.assertIn("nunca 'no episodio anterior'", texto)
        self.assertIn("gancho novo", texto)
        self.assertIn("cliffhanger", texto.lower())
        # A continuacao e PROMETIDA pela pergunta final, nunca anunciada:
        # medido em 01/09/2026, 9 de 10 partes de uma serie terminavam com a
        # frase literal "a historia continua na proxima parte" — a ultima
        # coisa que a pessoa ouvia, dez vezes igual.
        self.assertIn("NUNCA escreva", texto)
        self.assertIn("se PROMETE pela pergunta", texto)

    def test_ultima_parte_fecha_a_pergunta(self):
        texto = S.prompt_parte(_biblia(), 3, config=CONFIG)
        self.assertIn("responda a pergunta central", texto)
        self.assertIn("pergunta direta para quem assiste", texto)
        self.assertNotIn("cliffhanger e a ULTIMA FRASE", texto)

    def test_toda_parte_carrega_a_descricao_do_protagonista(self):
        for numero in (1, 2, 3):
            texto = S.prompt_parte(_biblia(), numero, config=CONFIG)
            self.assertIn("shaved head", texto, f"parte {numero}")
            self.assertIn("CENA 1", texto)
            self.assertIn("NARRACAO:", texto)

    def test_o_plano_da_parte_entra_no_prompt(self):
        texto = S.prompt_parte(_biblia(), 2, config=CONFIG)
        self.assertIn("Dona Irene entrega uma chave", texto)
        self.assertIn("Ela sabia o meu nome do meio.", texto)


# ------------------------------------------------- 3. partes na pipeline
class PartesNaPipelineTests(unittest.TestCase):
    def test_historia_antiga_vira_serie_de_uma_parte(self):
        antiga = {"titulo": "T", "cenas": _cenas(4)}
        dados = R.normalizar(dict(antiga))
        self.assertFalse(dados["serie"])
        self.assertEqual(1, len(dados["partes"]))
        self.assertEqual(4, dados["total_cenas"])
        self.assertEqual("T", R.titulo_da_parte(dados, 1))

    def test_serie_numera_as_cenas_dentro_de_cada_parte(self):
        dados = _serie(partes=3, cenas=5)
        self.assertTrue(dados["serie"])
        self.assertEqual(15, dados["total_cenas"])
        for parte in dados["partes"]:
            self.assertEqual([1, 2, 3, 4, 5], [c["n"] for c in parte["cenas"]])

    def test_imagem_de_partes_diferentes_nao_colide(self):
        p1 = fila.caminho_da_cena("historia_00099", 7, 1)
        p3 = fila.caminho_da_cena("historia_00099", 7, 3)
        self.assertNotEqual(p1, p3)
        self.assertIn("p03_cena_07", p3.name)
        # historia de uma parte so mantem o nome curto (as que ja existiam)
        self.assertEqual("cena_07.png",
                         fila.caminho_da_cena("historia_00099", 7, None).name)

    def test_plano_e_por_parte_e_leva_o_titulo_da_parte(self):
        dados = _serie(partes=3, cenas=5)
        plano = timeline.montar(dados, {}, config_roteiro=CONFIG,
                                config_render=timeline.carregar_config("render.json"),
                                parte=2)
        self.assertEqual(2, plano["parte"])
        self.assertEqual(3, plano["partes"])
        self.assertEqual(5, len(plano["events"]))
        self.assertEqual("Parte 2 - titulo", plano["titulo"])
        self.assertEqual("Parte 2 - titulo", plano["events"][0]["titulo"])
        self.assertEqual(["p2 1.", "p2 2.", "p2 3.", "p2 4.", "p2 5."],
                         [e["narracao"] for e in plano["events"]])

    def test_salvar_e_carregar_a_serie(self):
        with tempfile.TemporaryDirectory() as tmp:
            antes = R.OUTPUTS
            R.OUTPUTS = Path(tmp)
            try:
                biblia = _biblia()
                partes = [{"n": k, "titulo": f"P{k}", "cliffhanger": "x",
                           "cta": "", "cenas": _cenas(6)} for k in (1, 2, 3)]
                caminho = R.salvar_serie(biblia, partes, "historia_00042",
                                         tema="teste", provedor="chatgpt")
                self.assertTrue(caminho.is_file())
                lido = R.carregar("historia_00042")
                self.assertTrue(lido["serie"])
                self.assertEqual(3, len(lido["partes"]))
                self.assertEqual(18, lido["total_cenas"])
                self.assertIn("shaved head", lido["protagonista"])
                self.assertEqual("Eu descobri o que meu pai escondia na garagem",
                                 lido["titulo"])
            finally:
                R.OUTPUTS = antes

    def test_catalogo_lista_um_video_por_parte_em_ordem(self):
        with tempfile.TemporaryDirectory() as tmp:
            antes = catalogo.OUTPUTS
            catalogo.OUTPUTS = Path(tmp)
            try:
                pasta = Path(tmp) / "historia_00050"
                pasta.mkdir(parents=True)
                dados = _serie(partes=3, cenas=4)
                dados["historia_id"] = "historia_00050"
                (pasta / "roteiro.json").write_text(
                    json.dumps(dados, ensure_ascii=False), encoding="utf-8")
                for k in (1, 2, 3):
                    (pasta / f"final_celular_p{k:02d}.mp4").write_bytes(
                        b"0" * (catalogo.BYTES_MINIMOS + 1))
                videos = catalogo.listar()
                self.assertEqual([1, 2, 3], [v.parte for v in videos])
                self.assertTrue(all(v.partes == 3 for v in videos))
                self.assertEqual("celular", videos[0].perfil)
                self.assertTrue(videos[2].id.endswith(":p03"))
                self.assertIn("_p02_", videos[1].nome_export)
                self.assertIn("Parte 2", videos[1].descricao)
            finally:
                catalogo.OUTPUTS = antes


# ----------------------------------------------------- 4. resposta cortada
class ClienteFalso:
    """Um LLM de mentira: devolve as respostas na ordem em que foram postas."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.perguntas = []

    def perguntar(self, prompt, timeout=None):
        self.perguntas.append(prompt)
        return self.respostas.pop(0) if self.respostas else ""


def _bloco(inicio: int, fim: int) -> str:
    partes = []
    for i in range(inicio, fim + 1):
        partes.append(f"CENA {i}\nIMAGEM: a dim room with an open window, {i}\n"
                      f"TEMPO: 4\nNARRACAO: fala numero {i}.")
    return "\n\n".join(partes)


class ContinuacaoTests(unittest.TestCase):
    def test_pede_continuacao_quando_a_resposta_vem_cortada(self):
        with tempfile.TemporaryDirectory() as tmp:
            cliente = ClienteFalso([_bloco(9, 14)])
            parcial = gerar._completar_parte(cliente, _bloco(1, 8), 3, 14,
                                             Path(tmp), lambda *a: None)
            self.assertEqual(14, len(parcial["cenas"]))
            self.assertEqual(list(range(1, 15)),
                             [c["n"] for c in parcial["cenas"]])
            self.assertEqual(1, len(cliente.perguntas))
            self.assertIn("CENA 9", cliente.perguntas[0])
            self.assertIn("nao repita", cliente.perguntas[0].lower())

    def test_desiste_depois_de_tres_tentativas(self):
        with tempfile.TemporaryDirectory() as tmp:
            cliente = ClienteFalso(["", "", ""])
            parcial = gerar._completar_parte(cliente, _bloco(1, 4), 1, 14,
                                             Path(tmp), lambda *a: None)
            self.assertEqual(4, len(parcial["cenas"]))
            self.assertLessEqual(len(cliente.perguntas), 3)

    def test_resposta_completa_nao_pede_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            cliente = ClienteFalso([])
            parcial = gerar._completar_parte(cliente, _bloco(1, 14), 1, 14,
                                             Path(tmp), lambda *a: None)
            self.assertEqual(14, len(parcial["cenas"]))
            self.assertEqual([], cliente.perguntas)


# ------------------------------------------------------- 5. cliente de LLM
class PaginaFalsa:
    """DOM de mentira: o suficiente para exercitar as provas de envio e de
    resposta sem abrir browser nenhum."""

    def __init__(self, respostas=("",), escrevendo=False):
        self.respostas = list(respostas)
        self.escrevendo = escrevendo
        self.campo_texto = "prompt aqui"

    # a interface que o cliente usa
    def locator(self, seletor):
        raise RuntimeError("PaginaFalsa nao usa locator")


class ClienteLLMTests(unittest.TestCase):
    def _cliente(self):
        return llm_cliente.ClienteLLM("chatgpt", None, PaginaFalsa(),
                                      {"resposta_timeout": 3}, log=lambda *a: None)

    def test_envio_so_e_envio_com_prova(self):
        cliente = self._cliente()
        estado = {"texto": "ainda com o prompt inteiro aqui dentro"}

        class Campo:
            def input_value(self):
                return estado["texto"]

        # sem botao de parar e com o campo cheio: NAO houve envio
        cliente._parada_visivel = lambda: False
        from contos.llm import seletores
        original = seletores.encontrar
        seletores.encontrar = lambda page, cand, timeout=0: None
        try:
            self.assertFalse(cliente._confirmou_envio(Campo(), espera=0.6))
            estado["texto"] = ""          # o campo esvaziou: prova de envio
            self.assertTrue(cliente._confirmou_envio(Campo(), espera=0.6))
        finally:
            seletores.encontrar = original

    def test_resposta_so_e_lida_quando_para_de_crescer(self):
        cliente = self._cliente()
        passos = ["Era uma", "Era uma vez", "Era uma vez um", "Era uma vez um homem"]
        estado = {"i": 0}

        def texto_atual():
            i = min(estado["i"], len(passos) - 1)
            estado["i"] += 1
            return passos[i]

        cliente._resposta_atual = texto_atual
        from contos.llm import seletores
        original = seletores.encontrar
        # "escrevendo" enquanto o texto cresce; depois o botao de parar some
        seletores.encontrar = lambda page, cand, timeout=0: (
            object() if estado["i"] < len(passos) else None)
        try:
            texto = cliente.esperar_resposta(timeout=20, estabilidade=0.2)
        finally:
            seletores.encontrar = original
        self.assertEqual("Era uma vez um homem", texto)

    def test_resposta_em_multiplos_turnos_nao_e_anterior(self):
        """Em chat com multiplos turnos, _.nth(total-1) pega a resposta nova,
        nao a anterior ainda renderizada na tela. Isso era o problema de h00005
        parte 3 que ficava retornando 6332 chars da parte 2 (gemini-resposta-
        anterior-multiplasturnos).
        """
        cliente = self._cliente()
        # Simula um chat com 3 turnos: parte 1, parte 2, parte 3
        turnos = {
            1: ["Parte 1", "Parte 1 completa"],
            2: ["Parte 2", "Parte 2 completa"],
            3: ["Parte 3", "Parte 3 completa"],
        }
        estado = {"turno": 1, "passo": 0}

        from contos.llm import seletores
        original_encontrar = seletores.encontrar

        def texto_atual():
            # Retorna a resposta do turno atual; cresce progressivamente
            turno = estado["turno"]
            passo = estado["passo"]
            respostas = turnos[turno]
            passo = min(passo, len(respostas) - 1)
            estado["passo"] += 1
            return respostas[passo]

        def avancar_turno():
            # Simula o usuario enviando a proxima pergunta
            if estado["turno"] < 3:
                estado["turno"] += 1
                estado["passo"] = 0

        cliente._resposta_atual = texto_atual
        # "escrevendo" enquanto o texto cresce; depois some
        seletores.encontrar = lambda page, cand, timeout=0: (
            object() if estado["passo"] < len(turnos[estado["turno"]]) else None)

        try:
            # Turno 1: parte 1
            resp1 = cliente.esperar_resposta(timeout=20, estabilidade=0.2)
            avancar_turno()

            # Turno 2: parte 2
            resp2 = cliente.esperar_resposta(timeout=20, estabilidade=0.2)
            avancar_turno()

            # Turno 3: parte 3 (esse era o que ficava com resposta anterior)
            resp3 = cliente.esperar_resposta(timeout=20, estabilidade=0.2)
        finally:
            seletores.encontrar = original_encontrar

        # Cada resposta deve ser diferente e nao pode ser a anterior
        self.assertEqual("Parte 1 completa", resp1)
        self.assertEqual("Parte 2 completa", resp2)
        self.assertEqual("Parte 3 completa", resp3)
        # Validar que nao pegou resposta anterior
        self.assertNotEqual(resp3, resp2)
        self.assertNotEqual(resp3, resp1)

    def test_perfil_por_provedor_e_separado(self):
        self.assertNotEqual(llm_cliente.perfil_de("chatgpt"),
                            llm_cliente.perfil_de("gemini"))
        self.assertTrue(llm_cliente.perfil_de("chatgpt").is_dir())

    def test_provedor_desconhecido_diz_quais_existem(self):
        from contos.llm import seletores
        with self.assertRaises(ValueError) as ctx:
            seletores.do_provedor("copilot")
        self.assertIn("chatgpt", str(ctx.exception))
        self.assertIn("gemini", str(ctx.exception))

    def test_os_dois_provedores_tem_todos_os_alvos(self):
        from contos.llm import seletores
        for provedor in seletores.PROVEDORES:
            alvo = seletores.do_provedor(provedor)
            for chave in ("url", "campo", "enviar", "parar", "resposta",
                          "logado", "login"):
                self.assertIn(chave, alvo, provedor)
                self.assertTrue(alvo[chave], f"{provedor}.{chave} vazio")


class FichaDeFatosTests(unittest.TestCase):
    """Os NUMEROS tambem precisam de consistencia entre partes (02/09/2026).

    A descricao fisica do protagonista ja era repetida em toda cena, e por
    isso 84 imagens pareciam a mesma pessoa. Nada fazia o mesmo pelos numeros:
    na historia 8 o aluguel era "tres mil e oitocentos" nas partes 1 e 6 e
    "cinco mil" na 2. A ficha de FATOS e o gemeo factual daquela frase.
    """

    def setUp(self):
        from contos.roteiro import serie
        self.serie = serie
        self.biblia = serie.parse_biblia("\n".join([
            "TITULO DA SERIE: T",
            "PREMISSA: P",
            "PROTAGONISTA: Ana | a 30-year-old woman",
            "FATOS: aluguel = R$ 3.800 por mes; se conheceram = 2020",
            "PARTE 1",
            "TITULO: A",
            "RESUMO: R",
            "GANCHO: G",
        ]), 1)

    def test_a_biblia_pede_a_ficha(self):
        prompt = self.serie.prompt_biblia(partes=2, cenas_por_parte=4)
        self.assertIn("FATOS:", prompt)
        self.assertIn("CONSISTENCIA DE FATOS", prompt)

    def test_a_ficha_e_lida_da_resposta(self):
        self.assertIn("aluguel = R$ 3.800", self.biblia["fatos"])

    def test_a_ficha_entra_em_TODA_parte(self):
        # O modelo nao lembra na parte 6 do numero que escreveu na parte 1;
        # e por isso que ela vai junto em cada pergunta, nao so na primeira.
        for numero in (1, 2, 6):
            prompt = self.serie.prompt_parte(self.biblia, numero, cenas=4)
            self.assertIn("aluguel = R$ 3.800 por mes", prompt, f"parte {numero}")
            self.assertIn("se conheceram = 2020", prompt, f"parte {numero}")

    def test_sem_ficha_o_prompt_nao_inventa_secao_vazia(self):
        biblia = dict(self.biblia, fatos="")
        self.assertNotIn("FATOS DA HISTORIA",
                         self.serie.prompt_parte(biblia, 1, cenas=4))

    def test_a_ficha_sobrevive_ao_salvar(self):
        from contos.roteiro import roteiro as R
        with tempfile.TemporaryDirectory() as tmp:
            antigo, R.OUTPUTS = R.OUTPUTS, Path(tmp)
            try:
                caminho = R.salvar_serie(
                    self.biblia,
                    [{"n": 1, "titulo": "A", "cta": "", "cenas": [
                        {"n": 1, "imagem": "x" * 30, "tempo": 4,
                         "narracao": "oi"}]}],
                    "historia_00099")
                with open(caminho, encoding="utf-8-sig") as fh:
                    self.assertIn("3.800", json.load(fh)["fatos"])
            finally:
                R.OUTPUTS = antigo


class CoerenciaDeNumerosTests(unittest.TestCase):
    """Numero por extenso e numero em digito sao o mesmo numero."""

    def setUp(self):
        from contos.roteiro import coerencia
        self.C = coerencia

    def test_le_valor_por_extenso(self):
        self.assertEqual(self.C._por_extenso("Tres mil e oitocentos reais."),
                         [3800])

    def test_conto_e_mil(self):
        self.assertEqual(self.C._por_extenso("me tirava quase quatro contos"),
                         [4000])

    def test_digito_e_extenso_dao_o_mesmo(self):
        self.assertEqual(self.C._dinheiro("um rombo de cinco mil reais"),
                         self.C._dinheiro("um rombo de 5.000 reais"))

    def _historia(self, narracao, fatos="aluguel = R$ 3.800 por mes"):
        return {"fatos": fatos, "partes": [
            {"n": 1, "cenas": [{"n": 1, "narracao": narracao}]}]}

    def test_valor_fora_da_ficha_e_apontado_com_a_cena(self):
        avisos = self.C.conferir(self._historia(
            "ver um rombo de cinco mil reais todo dia dez"))
        self.assertEqual(len(avisos), 1)
        self.assertIn("5000", avisos[0])
        self.assertIn("p01c01", avisos[0])

    def test_valor_da_ficha_nao_acusa_nada(self):
        self.assertEqual(
            self.C.conferir(self._historia("Tres mil e oitocentos reais.")), [])

    def test_sem_ficha_avisa_uma_vez_so(self):
        avisos = self.C.conferir(self._historia("Tres mil reais.", fatos=""))
        self.assertEqual(len(avisos), 1)
        self.assertIn("FATOS", avisos[0])


class TituloQueCabeTests(unittest.TestCase):
    """Titulo grande demais e ERRO: o YouTube corta em 100 caracteres."""

    def _roteiro(self, titulo):
        return {"titulo": titulo, "cenas": [
            {"n": i, "imagem": "a photo of something", "tempo": 4,
             "narracao": "oi"} for i in range(1, 6)]}

    def test_titulo_de_130_chars_e_erro(self):
        from contos.roteiro import roteiro as R
        _problemas, erros = R.validar(self._roteiro("M" * 130))
        self.assertTrue(any("titulo" in e for e in erros),
                        "as historias 4 (136) e 8 (130) passaram com aviso")

    def test_titulo_no_limite_passa(self):
        from contos.roteiro import roteiro as R
        _problemas, erros = R.validar(self._roteiro("M" * 100))
        self.assertEqual(erros, [])


class CorridaQueMorreTests(unittest.TestCase):
    """Tentativa que falha nao queima id nem deixa pasta vazia (02/09/2026).

    `historia_00006` e `historia_00007` sao duas pastas VAZIAS, criadas em
    01/09 as 18:00 e 18:01: duas corridas que morreram antes da biblia. O id
    e a pasta eram tirados ANTES de abrir o navegador, e nenhum registro
    sobrava para dizer por que elas falharam.
    """

    def test_o_id_so_e_alocado_depois_da_biblia(self):
        from contos.roteiro import gerar
        fonte = Path(gerar.__file__).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def gerar_serie("):]
        self.assertLess(corpo.index("S.parse_biblia("), corpo.index("R.proximo_id()"),
                        "o id nao pode ser tirado antes de a biblia existir")

    def test_a_falha_deixa_o_motivo_escrito(self):
        from contos.roteiro import gerar
        fonte = Path(gerar.__file__).read_text(encoding="utf-8")
        self.assertIn("[serie] FALHOU:", fonte)
        self.assertIn("_logs", fonte)

    def test_o_diario_escreve_na_tela_e_no_arquivo(self):
        from contos.roteiro import gerar
        with tempfile.TemporaryDirectory() as tmp:
            tela = []
            diario = gerar._Diario(tela.append, Path(tmp) / "log.txt")
            diario("primeira linha")
            self.assertEqual(tela, ["primeira linha"])
            self.assertIn("primeira linha",
                          diario.destino.read_text(encoding="utf-8"))

    def test_o_log_de_antes_do_id_vai_junto_para_a_pasta_da_historia(self):
        from contos.roteiro import gerar
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            diario = gerar._Diario(lambda _: None, raiz / "_logs" / "x.txt")
            diario("antes de existir id")
            provisorio = diario.destino
            diario.mudar_de_casa(raiz / "historia_00099" / "log.txt")
            diario("depois do id")
            texto = diario.destino.read_text(encoding="utf-8")
            self.assertIn("antes de existir id", texto)
            self.assertIn("depois do id", texto)
            self.assertFalse(provisorio.exists(),
                             "o log provisorio nao pode ficar para tras")


class NaoRepetirHistoriaTests(unittest.TestCase):
    """O canal nao pode contar a mesma historia duas vezes (08/09/2026).

    Com `tema` vazio o modelo escolhe o assunto, e o chat e NOVO a cada
    rodada — entao o mesmo prompt converge para a mesma ideia. Duas rodadas
    seguidas da agenda automatica deram:

        historia_00009  "conta de luz paga no meu CPF em um endereco
                         onde nunca pisei na vida"
        historia_00010  "conta de luz paga no meu nome numa casa
                         onde nunca pisei na vida"

    A virada de cada uma era diferente, mas o gancho era o mesmo. Num canal
    que publica 4 a 6 por dia, isso vira um assunto so, repetido.
    """

    def test_a_lista_do_que_ja_existe_entra_no_prompt(self):
        prompt = S.prompt_biblia(partes=2, cenas_por_parte=4,
                                 evitar=["Achei uma conta de luz no meu nome",
                                         "Meu vizinho pagou meu aluguel"])
        self.assertIn("Nao repita", prompt)
        self.assertIn("Achei uma conta de luz no meu nome", prompt)
        self.assertIn("Meu vizinho pagou meu aluguel", prompt)

    def test_sem_lista_o_prompt_nao_ganha_secao_vazia(self):
        self.assertNotIn("O CANAL JA TEM",
                         S.prompt_biblia(partes=2, cenas_por_parte=4))

    def test_a_geracao_automatica_passa_a_lista(self):
        # Sem esta ligacao a lista existiria e nunca seria usada.
        fonte = Path(gerar.__file__).read_text(encoding="utf-8")
        self.assertIn("evitar=R.titulos_recentes()", fonte)

    def test_titulos_recentes_vem_do_mais_novo_e_ignora_teste(self):
        with tempfile.TemporaryDirectory() as tmp:
            antigo, R.OUTPUTS = R.OUTPUTS, Path(tmp)
            try:
                for numero, titulo, provedor in (
                        (1, "A primeira", "gemini"),
                        (2, "A de teste", "fake"),
                        (3, "A mais nova", "chatgpt")):
                    pasta = Path(tmp) / f"historia_{numero:05d}"
                    pasta.mkdir(parents=True)
                    (pasta / "roteiro.json").write_text(json.dumps({
                        "historia_id": f"historia_{numero:05d}",
                        "titulo": titulo, "provedor": provedor,
                        "cenas": [{"n": 1, "imagem": "x", "tempo": 4,
                                   "narracao": "oi"}]}), encoding="utf-8")
                recentes = R.titulos_recentes()
            finally:
                R.OUTPUTS = antigo
        self.assertEqual(recentes, ["A mais nova", "A primeira"])

    def test_titulos_recentes_respeita_o_limite(self):
        self.assertLessEqual(len(R.titulos_recentes(quantos=3)), 3)


class ModeloDoLLMTests(unittest.TestCase):
    """O chat abre no modelo mais FORTE, nao no que sobrou (08/09/2026).

    A URL do Gemini nao carrega modelo nenhum: ela abre com o que estiver
    marcado na conta. Em 08/09/2026 estava em "3.6 Flash" — o rapido — e as
    historias 3 a 10 inteiras sairam dele. Escrever historia e trabalho de
    raciocinio; deixar isso na sorte do que ficou selecionado da ultima vez e
    deixar a qualidade na sorte.
    """

    def test_o_gemini_prefere_pro_antes_de_flash(self):
        from contos.llm import seletores
        alvo = seletores.do_provedor("gemini")
        self.assertEqual(alvo["modelo_preferido"][0], "pro")
        self.assertIn("flash", alvo["modelo_preferido"])

    def test_ha_seletor_para_abrir_e_para_escolher(self):
        from contos.llm import seletores
        alvo = seletores.do_provedor("gemini")
        self.assertTrue(alvo["modelo_botao"])
        self.assertTrue(alvo["modelo_opcao"])

    def test_escolher_modelo_NUNCA_derruba_a_geracao(self):
        """Seletor que mudou nao pode impedir a historia de sair.

        Ela sai no modelo que estiver, e o log conta que nao deu para trocar —
        o contrario seria a noite inteira sem nenhuma historia por causa de um
        botao que o Google renomeou.
        """
        from contos.llm import cliente as C

        class _PaginaQuebrada:
            def locator(self, *_a, **_k):
                raise RuntimeError("o Google mudou tudo")

        falso = C.ClienteLLM.__new__(C.ClienteLLM)
        falso.page = _PaginaQuebrada()
        falso.provedor = "gemini"
        falso.sel = {"modelo_botao": ["x"], "modelo_opcao": ["y"],
                     "modelo_preferido": ["pro"]}
        falso.log = lambda *_a: None
        import random
        falso.rng = random.Random(1)
        self.assertEqual(falso.escolher_modelo(), "")   # nao levanta

    def test_a_escolha_acontece_ao_abrir_o_chat(self):
        """Depois de mandar o prompt ja seria tarde."""
        fonte = Path(llm_cliente.__file__).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def abrir("):fonte.index("def escolher_modelo(")]
        self.assertIn("self.escolher_modelo()", corpo)


class AbordagemDeQualidadeTests(unittest.TestCase):
    """As quatro alavancas de qualidade que ele pediu (08/09/2026).

    Ele disse "sinto que essa abordagem diminui muito a qualidade" e apontou
    quatro coisas: as historias se parecem, o texto soa raso, o gancho nao
    segura e o meio arrasta. A causa de fundo era o modelo (Gemini FLASH, nao
    Pro), mas havia uma falha estrutural junto: **a serie nunca usou os moldes**
    de `roteiro.json` — `reddit`, `confissao` e `vinganca` so valiam no fluxo
    manual, e o automatico deixava a forma por conta do modelo, que escolhe
    sempre a mesma.
    """

    # ------------------------------------------------- as historias se parecem
    def test_o_molde_entra_no_prompt_da_biblia(self):
        texto = S.prompt_biblia(partes=2, cenas_por_parte=4, config=CONFIG,
                                estrutura="vinganca")
        self.assertIn("MOLDE DESTA HISTORIA", texto)
        self.assertIn("malicious compliance", texto.lower())

    def test_o_rodizio_pega_o_que_faltou(self):
        usadas = ["reddit", "reddit", "confissao"]
        self.assertEqual(S.proxima_estrutura(usadas, CONFIG), "vinganca")

    def test_com_todos_usados_volta_para_o_mais_antigo(self):
        # lida do mais NOVO para o mais velho: `reddit` e o mais antigo aqui
        usadas = ["vinganca", "confissao", "reddit"]
        self.assertEqual(S.proxima_estrutura(usadas, CONFIG), "reddit")

    def test_a_estrutura_e_guardada_para_o_rodizio_ter_memoria(self):
        with tempfile.TemporaryDirectory() as tmp:
            antigo, R.OUTPUTS = R.OUTPUTS, Path(tmp)
            try:
                caminho = R.salvar_serie(
                    _biblia(),
                    [{"n": 1, "titulo": "A", "cta": "", "cenas": [
                        {"n": 1, "imagem": "x" * 30, "tempo": 4,
                         "narracao": "oi"}]}],
                    "historia_00099", estrutura="confissao")
                with open(caminho, encoding="utf-8-sig") as fh:
                    self.assertEqual(json.load(fh)["estrutura"], "confissao")
            finally:
                R.OUTPUTS = antigo

    # ------------------------------------------------------ texto soa raso
    def test_existe_uma_etapa_de_REVISAO(self):
        texto = S.prompt_revisao(2, 14, config=CONFIG)
        self.assertIn("RELEIA", texto)
        for caca in ("Frase de efeito", "informacao NOVA", "mesmo tamanho"):
            self.assertIn(caca, texto)
        self.assertIn("INTEIRA reescrita", texto)

    def test_a_revisao_e_descartada_se_vier_menor(self):
        """Parte pela metade e pior do que parte mediana."""
        fonte = Path(gerar.__file__).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def _revisar_parte("):]
        self.assertIn("< len(parcial[", corpo)
        self.assertIn("fico com a primeira versao", corpo)

    def test_a_revisao_acontece_antes_de_salvar(self):
        fonte = Path(gerar.__file__).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("for numero in range(1, total + 1):"):]
        self.assertLess(corpo.index("_revisar_parte("),
                        corpo.index("R.salvar_serie("))

    # ---------------------------------------------------- o gancho nao segura
    def test_a_parte_1_escolhe_entre_TRES_aberturas(self):
        texto = S.prompt_parte(_biblia(), 1, cenas=12, config=CONFIG)
        self.assertIn("TRES aberturas", texto)
        self.assertIn("PRECISAR saber", texto)

    def test_so_a_parte_1_pede_isso(self):
        self.assertNotIn("TRES aberturas",
                         S.prompt_parte(_biblia(), 2, config=CONFIG))

    # ------------------------------------------------------ o meio arrasta
    def test_cada_parte_precisa_de_fato_novo(self):
        texto = S.prompt_biblia(partes=6, cenas_por_parte=14, config=CONFIG)
        self.assertIn("FATO NOVO", texto)
        self.assertIn("pode ser resumida sem", texto)

    # ------------------------------------------- ganchos psicologicos
    def test_so_as_DUAS_escolhidas_entram_no_prompt(self):
        """Este teste era o contrario, e o contrario era o proprio defeito.

        Ele exigia que TRAICAO, MEDO, ORGULHO FERIDO e VINGANCA estivessem
        TODAS no prompt — ou seja, travava o despejo do catalogo inteiro com
        um "escolha DUAS" no fim. Com escolha livre o modelo converge: as
        cinco historias geradas com alavancas (11 a 15) escolheram TODAS o
        mesmo par, e seis das nove alavancas nunca sairam uma vez.

        Listar e convidar. Agora quem escolhe e o rodizio, e a alavanca que
        NAO foi escolhida nao pode aparecer — cada uma visivel e uma porta
        para o modelo voltar ao par de sempre.
        """
        escolhidas = ["SER_SUBSTITUIDA", "VINGANCA_ELEGANTE"]
        texto = S.prompt_biblia(partes=2, cenas_por_parte=4, config=CONFIG,
                                narrador="mulher", ganchos=escolhidas)
        for nome in escolhidas:
            self.assertIn(nome.replace("_", " "), texto)
        # o campo que impede "ela tinha medo de ter escolhido errado"
        self.assertIn("como isso APARECE", texto)
        # e uma terceira do mesmo catalogo NAO pode estar la
        self.assertNotIn("A ULTIMA A SABER", texto)

    def test_alavanca_de_mulher_nao_sai_com_narrador_homem(self):
        """O gancho e de genero: "marido que nao cresce" so funciona na boca dela."""
        catalogo = S.catalogo_de_ganchos("homem", CONFIG)
        self.assertNotIn("MARIDO_QUE_NAO_CRESCE", catalogo)
        self.assertIn("NAO_PODER_PROVER", catalogo)
        # as universais valem para os dois
        self.assertIn("CULPA", catalogo)
        self.assertIn("CULPA", S.catalogo_de_ganchos("mulher", CONFIG))

    def test_o_par_traz_um_medo_e_uma_fantasia(self):
        """Duas do mesmo lado dao video que so aperta (cansa) ou so afaga."""
        for narrador in ("mulher", "homem"):
            par = S.proximos_ganchos([], narrador, CONFIG)
            self.assertEqual(2, len(par), narrador)
            catalogo = S.catalogo_de_ganchos(narrador, CONFIG)
            registros = sorted(catalogo[n]["registro"] for n in par)
            self.assertEqual(["fantasia", "medo"], registros, narrador)

    def test_o_rodizio_nao_repete_o_que_acabou_de_sair(self):
        """As 11 a 15 sairam com o MESMO par. Aqui isso e impossivel."""
        usadas, pares = [], []
        for _ in range(6):
            par = S.proximos_ganchos(usadas, "mulher", CONFIG)
            pares.append(tuple(sorted(par)))
            usadas = par + usadas          # a mais nova na frente, como no disco
        self.assertEqual(len(pares), len(set(pares)), f"par repetido: {pares}")
        nomes = [n for p in pares for n in p]
        self.assertEqual(len(nomes), len(set(nomes)), "alavanca repetida cedo")

    def test_o_LIMITE_de_idade_vale_MESMO_sem_alavanca(self):
        """Ele morava dentro do `if ganchos:` — catalogo vazio levava o
        guarda-corpo junto, em silencio. Nasceu de incidente real em 08/09."""
        texto = S.prompt_biblia(partes=2, cenas_por_parte=4, config=CONFIG,
                                ganchos=[])
        self.assertIn("menor de 18", texto)
        self.assertIn("nao se negocia", texto)

    def test_o_narrador_ja_decidido_vai_no_prompt(self):
        """Ele derivava: as historias 12 a 15 sairam todas com narrador homem."""
        texto = S.prompt_biblia(partes=2, cenas_por_parte=4, config=CONFIG,
                                narrador="mulher")
        self.assertIn("QUEM CONTA: mulher", texto)

    def test_o_narrador_alterna(self):
        self.assertEqual("mulher", S.proximo_narrador(["homem", "homem"]))
        self.assertEqual("homem", S.proximo_narrador(["mulher", "mulher"]))

    def test_o_catalogo_esta_no_formato(self):
        """O revisor de quem escreve 35 entradas a mao.

        E o guarda-corpo que importa: se um pool de narrador ficar sem uma das
        familias, a regra "uma de medo e uma de fantasia" para de valer em
        silencio e o par sai sempre do mesmo lado.
        """
        catalogo = CONFIG["ganchos"]
        self.assertEqual({"mulher", "homem", "qualquer"}, set(catalogo))
        vistos = set()
        for quem, itens in catalogo.items():
            registros = set()
            for nome, ficha in itens.items():
                self.assertRegex(nome, r"^[A-Z][A-Z0-9_]*$", nome)
                self.assertNotIn(nome, vistos, f"{nome} duplicado")
                vistos.add(nome)
                self.assertEqual({"registro", "mexe", "cena"}, set(ficha), nome)
                self.assertIn(ficha["registro"], ("medo", "fantasia"), nome)
                for campo in ("mexe", "cena"):
                    self.assertTrue(ficha[campo].strip(), f"{nome}.{campo}")
                registros.add(ficha["registro"])
            if quem != "qualquer":
                self.assertEqual({"medo", "fantasia"}, registros,
                                 f"o pool '{quem}' precisa das duas familias")

    def test_os_ganchos_e_o_narrador_sao_guardados_para_o_rodizio_ter_memoria(self):
        """Sem isto o rodizio nao tem de onde ler: ate 09/09/2026 as alavancas
        so existiam em `biblia.json`, que `listar()` nao abre — e o resultado
        foram cinco historias seguidas com o mesmo par."""
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            antes = R.OUTPUTS
            try:
                R.OUTPUTS = Path(tmp)
                caminho = R.salvar_serie(
                    _biblia(), [{"n": 1, "titulo": "t", "cta": "",
                                 "cenas": _cenas(2)}],
                    "historia_00099", provedor="gemini",
                    ganchos=["SER_SUBSTITUIDA", "VINGANCA_ELEGANTE"],
                    narrador="mulher")
                dados = json.loads(Path(caminho).read_text(encoding="utf-8-sig"))
                self.assertEqual(["SER_SUBSTITUIDA", "VINGANCA_ELEGANTE"],
                                 dados["ganchos"])
                self.assertEqual("mulher", dados["narrador"])
                self.assertEqual(["SER_SUBSTITUIDA", "VINGANCA_ELEGANTE"],
                                 R.ganchos_recentes())
                self.assertEqual(["mulher"], R.narradores_recentes())
            finally:
                R.OUTPUTS = antes

    def test_a_geracao_automatica_escolhe_antes_do_primeiro_turno(self):
        """Escolher depois de perguntar seria escolher para nada."""
        from pathlib import Path
        from contos.roteiro import gerar
        fonte = Path(gerar.__file__).read_text(encoding="utf-8")
        trecho = fonte[fonte.index("def gerar_serie("):]
        self.assertLess(trecho.index("proximos_ganchos("),
                        trecho.index("cliente.perguntar("))
        self.assertIn("ganchos=ganchos, narrador=narrador", trecho)
        # AS DUAS chamadas de `salvar_serie` tem que levar a escolha: uma
        # corrida que morra na parte 3 grava pela primeira, e memoria vazia
        # ali faria o rodizio esquecer a historia inteira.
        chamadas = [p for p in trecho.split("R.salvar_serie(")[1:]]
        self.assertEqual(2, len(chamadas), "mudou o numero de gravacoes")
        for corpo in chamadas:
            self.assertIn("ganchos=ganchos", corpo[:corpo.index(")")])

    def test_o_menos_usado_pega_o_mais_esquecido_e_nao_o_ultimo_da_lista(self):
        """A sequencia REAL dos moldes das historias 11 a 15.

        Na escolha da 00015 a janela era esta e `reversed(usadas)` devolvia o
        `reddit` da 00011 — o mais antigo da LISTA, nao o menos recentemente
        usado. E `reddit` tinha acabado de sair na 00014.
        """
        usadas = ["reddit", "vinganca", "confissao", "reddit"]
        self.assertEqual("confissao", S.proxima_estrutura(usadas, CONFIG))

    def test_a_biblia_declara_quais_duas_escolheu(self):
        self.assertIn("ALAVANCAS:", S.prompt_biblia(partes=2, cenas_por_parte=4,
                                                    config=CONFIG))

    def test_as_alavancas_escolhidas_vao_em_TODA_parte(self):
        """Sem repetir, a parte 4 conta bem uma historia que nao mexe em nada."""
        biblia = dict(_biblia(), alavancas="TRAICAO e VERGONHA | o que ela "
                                           "esconde do proprio filho")
        for numero in (1, 2, 3):
            texto = S.prompt_parte(biblia, numero, config=CONFIG)
            self.assertIn("ALAVANCAS DESTA HISTORIA", texto, f"parte {numero}")
            self.assertIn("TRAICAO e VERGONHA", texto)

    def test_a_tensao_e_no_que_se_SENTE_nao_no_que_a_camera_mostra(self):
        """Nao e pudor: o filtro do PicassoIA recusa e a plataforma derruba.

        Sugerir tambem prende mais — o que a pessoa imagina e sempre pior do
        que o que se mostra.
        """
        texto = S.prompt_biblia(partes=2, cenas_por_parte=4, config=CONFIG)
        self.assertIn("SENTE", texto)
        self.assertIn("filtro de conteudo", texto)


class LinguagemQuePassaTests(unittest.TestCase):
    """Dizer o duro sem perder o video (08/09/2026).

    Ele pediu: "preciso que voce substitua isso de uma forma que o youtube nao
    pegue mas a pessoa saiba... nao podemos deixar isso parar o projeto".

    O YouTube nao le a historia: ele pega PALAVRA e IMAGEM. Boa historia
    perder monetizacao por um substantivo e desperdicio, e o prejuizo nem
    aparece — o video sobe, fica no ar e so nao entrega.

    DUAS FAIXAS, e a diferenca e o ponto todo: `risco` some reescrevendo a
    frase (a cena fica igual); `pare` e assunto que a plataforma derruba pelo
    que ELE E, e ai trocar a palavra so esconde de quem le, nao de quem
    revisa — e o preco e o canal, nao o video.
    """

    def test_o_guia_de_linguagem_entra_no_prompt(self):
        texto = S.prompt_parte(_biblia(), 2, config=CONFIG)
        self.assertIn("COMO DIZER O QUE E PESADO", texto)
        self.assertIn("MORTE:", texto)
        self.assertIn("pare na porta", texto.lower())

    def test_a_revisao_tambem_caca_termo_que_derruba(self):
        texto = S.prompt_revisao(2, 14, config=CONFIG)
        self.assertIn("TERMO QUE DERRUBA O VIDEO", texto)

    def test_termo_cru_e_marcado_como_risco(self):
        from contos.roteiro import linguagem
        laudo = linguagem.conferir_texto(
            "Ele matou o cachorro na minha frente, porra")
        self.assertIn("morte", laudo["risco"])
        self.assertIn("palavrao", laudo["risco"])
        self.assertEqual(laudo["pare"], [])

    def test_a_versao_sugerida_passa_limpa(self):
        """E o ponto: a cena continua, so a palavra sai."""
        from contos.roteiro import linguagem
        laudo = linguagem.conferir_texto(
            "A gente nao dormiu. De manha a camisa dele estava na "
            "minha cadeira.")
        self.assertEqual(laudo["risco"], {})
        self.assertEqual(laudo["pare"], [])

    def test_menor_em_contexto_sexual_e_PARE(self):
        from contos.roteiro import linguagem
        laudo = linguagem.conferir_texto(
            "o homem que comprou a minha virgindade aos dezessete anos")
        self.assertTrue(laudo["pare"])

    def test_idade_de_menor_SEM_contexto_sexual_nao_alarma(self):
        """Alarme demais vira alarme ignorado.

        "Minha filha de 14 anos chorou" e frase normal de desabafo.
        """
        from contos.roteiro import linguagem
        laudo = linguagem.conferir_texto(
            "Minha filha de 14 anos chorou a noite inteira depois "
            "que o pai foi embora")
        self.assertEqual(laudo["pare"], [])

    def test_a_conferencia_vem_ANTES_das_imagens(self):
        """Sao 84 imagens e ~2h antes de alguem notar."""
        fonte = Path(gerar.__file__).read_text(encoding="utf-8")
        del fonte
        from contos.pipeline import agenda
        corpo = Path(agenda.__file__).read_text(encoding="utf-8")
        trecho = corpo[corpo.index("def _trabalhar("):]
        self.assertLess(trecho.index("linguagem.conferir("),
                        trecho.index("_terminar(pipeline, historia_id"))

    def test_historia_impublicavel_nao_gasta_picasso(self):
        from contos.pipeline import agenda
        corpo = Path(agenda.__file__).read_text(encoding="utf-8")
        self.assertIn("historia impublicavel", corpo)
        trecho = corpo[corpo.index('if achados["pare"]:'):]
        self.assertIn("return", trecho[:400])


BIBLIA_PROIBIDA = BIBLIA_CRUA.replace(
    "PREMISSA: Um homem herda a casa do pai e acha uma porta que nao existia "
    "na planta.",
    "PREMISSA: Ela descobre que o chefe e o homem que comprou a virgindade "
    "dela na cama aos dezessete anos.")


class TrocarPremissaTests(unittest.TestCase):
    """A premissa impublicavel se conserta na biblia, nao vira historia morta.

    Descartar aqui custava a historia inteira e deixava a agenda parada.
    Trocar a PALAVRA nao resolve — a revisao olha do que a historia trata. O
    que resolve e trocar de onde vem a PRESSAO, mantendo molde e alavancas.
    """

    def test_a_biblia_impublicavel_e_detectada_antes_de_qualquer_cena(self):
        from contos.roteiro import linguagem
        achados = linguagem.conferir_biblia(S.parse_biblia(BIBLIA_PROIBIDA, 3))
        self.assertTrue(achados["pare"])
        self.assertIn("virgindade", linguagem.termos_de_pare(achados))

    def test_a_biblia_boa_passa_limpa(self):
        from contos.roteiro import linguagem
        self.assertEqual([], linguagem.conferir_biblia(_biblia())["pare"])

    def test_o_pedido_de_troca_guarda_o_que_prendia(self):
        pedido = S.prompt_trocar_premissa(["virgindade"], 3)
        baixo = pedido.lower()
        for alavanca in ("divida", "poder", "vergonha", "chefe"):
            self.assertIn(alavanca, baixo)
        self.assertIn("alavancas", baixo)
        self.assertIn("molde", baixo)

    def test_o_pedido_proibe_resolver_trocando_a_palavra(self):
        """O disfarce e que e o problema: quem revisa le o ASSUNTO."""
        baixo = S.prompt_trocar_premissa(["virgem"], 3).lower()
        self.assertIn("nao tente resolver trocando o termo", baixo)
        self.assertIn("censurando", baixo)

    def test_a_troca_acontece_e_a_historia_continua(self):
        with tempfile.TemporaryDirectory() as tmp:
            cliente = ClienteFalso([BIBLIA_CRUA])
            biblia = gerar._trocar_premissa_se_precisar(
                cliente, S.parse_biblia(BIBLIA_PROIBIDA, 3), 3,
                Path(tmp), lambda *a: None)
            self.assertEqual(1, len(cliente.perguntas))
            self.assertIn("PARE", cliente.perguntas[0])
            self.assertNotIn("virgindade", biblia["premissa"].lower())
            self.assertEqual(3, len(biblia["partes"]))

    def test_a_biblia_limpa_nao_gasta_turno_nenhum(self):
        with tempfile.TemporaryDirectory() as tmp:
            cliente = ClienteFalso([])
            gerar._trocar_premissa_se_precisar(cliente, _biblia(), 3,
                                               Path(tmp), lambda *a: None)
            self.assertEqual([], cliente.perguntas)

    def test_modelo_que_insiste_falha_ANTES_de_escrever_as_partes(self):
        with tempfile.TemporaryDirectory() as tmp:
            cliente = ClienteFalso([BIBLIA_PROIBIDA, BIBLIA_PROIBIDA])
            with self.assertRaises(gerar.GeracaoFalhou) as caso:
                gerar._trocar_premissa_se_precisar(
                    cliente, S.parse_biblia(BIBLIA_PROIBIDA, 3), 3,
                    Path(tmp), lambda *a: None)
            self.assertIn("Nenhuma", str(caso.exception))
            self.assertEqual(gerar.TENTATIVAS_DE_TROCA, len(cliente.perguntas))

    def test_a_troca_vem_antes_da_etapa_2(self):
        """Se vier depois, ja se pagou seis turnos de escrita por nada."""
        corpo = Path(gerar.__file__).read_text(encoding="utf-8")
        trecho = corpo[corpo.index("def gerar_serie("):]
        self.assertLess(trecho.index("_trocar_premissa_se_precisar("),
                        trecho.index("etapa 2"))

    def test_o_que_e_salvo_em_disco_e_a_biblia_ja_trocada(self):
        corpo = Path(gerar.__file__).read_text(encoding="utf-8")
        trecho = corpo[corpo.index("def gerar_serie("):]
        self.assertLess(trecho.index("_trocar_premissa_se_precisar("),
                        trecho.index('_gravar(pasta / "biblia.json"'))


if __name__ == "__main__":
    unittest.main()
