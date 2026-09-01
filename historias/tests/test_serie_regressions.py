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
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

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


if __name__ == "__main__":
    unittest.main()
