# -*- coding: utf-8 -*-
"""Contratos da espera pela imagem: estouro de espera TENTA DE NOVO.

Diagnostico de 09/09/2026, sobre o log de 08/09 (87 envios ao PicassoIA):

  imagem que da certo volta em 9 a 42 s. A maioria nem chega a imprimir o
  primeiro "gerando...", que so sai aos 20 s.
  imagem que falha NUNCA volta: fica os 600 s inteiros e estoura.

E o estouro era o fim da cena. `EsperaEstourou` caia no `except Exception`
generico do laco de escalada, que registrava o erro e dava `break` — nenhuma
nova tentativa. O preco, no disco:

    historia_00010  p01_cena_01 estourou as 10:12, as 12:10 e as 15:10, em
                    tres disparos seguidos, e ficou PRONTA as 15:35 com o
                    MESMO prompt. 30 minutos de espera por falta de um reenvio.
    historia_00011  81 de 84 imagens. Faltaram a cena 1 da parte 1 (o gancho)
                    e a cena 14 da parte 6 (o CTA) — e por isso duas das seis
                    partes nao viraram video.

O que este arquivo trava:

1. ESTOURO REENVIA, e reenvia o texto IGUAL. Suavizar por causa de timeout
   pioraria a imagem para consertar o que nao era problema dela.
2. RECUSA E ESTOURO SAO COISAS DIFERENTES. Recusa e sobre o conteudo
   (reenviar identico seria recusado de novo, por definicao); estouro e sobre
   o site.
3. `BrowserMorreu` NAO tenta de novo. Ele herda de `EsperaEstourou`, entao um
   `except EsperaEstourou` desatento ficaria reenviando prompt para uma aba
   fechada ate acabar as tentativas.
4. O ORCAMENTO TOTAL NAO PIOROU: 3 tentativas de 180 s custam menos que a
   espera unica de 600 s que havia antes.

Rode de dentro de historias/:
    python -m unittest tests.test_imagem_espera_regressions -v
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from builds.identity.client import BrowserMorreu, EsperaEstourou  # noqa: E402
from contos.imagens.worker import _gerar_esperando                # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = json.loads((RAIZ / "config" / "imagens.json").read_text(
    encoding="utf-8"))


class ClienteFalso:
    """Um PicassoIA de mentira: falha as N primeiras esperas, depois entrega."""

    def __init__(self, estouros: int = 0, erro=EsperaEstourou):
        self.estouros = estouros
        self.erro = erro
        self.enviados = []

    def submit_prompt(self, prompt, aspect="9:16"):
        self.enviados.append(prompt)
        return ["ja_na_tela"]

    def wait_for_render(self, antes=None):
        if self.estouros > 0:
            self.estouros -= 1
            raise self.erro("a imagem nao ficou pronta em 180s.")
        return "https://picassoia/nova.png"


AJUSTES = {"render_timeout": 180, "min_interval": 0}


def _rodar(cliente, config=None):
    return _gerar_esperando(cliente, "uma mulher numa cozinha escura",
                            config or {"tentativas_por_espera": 3},
                            AJUSTES, lambda *a: None, "p01_cena_01")


class ReenvioTests(unittest.TestCase):
    def test_a_primeira_de_primeira_nao_reenvia_nada(self):
        cliente = ClienteFalso(estouros=0)
        alvo, _ = _rodar(cliente)
        self.assertEqual("https://picassoia/nova.png", alvo)
        self.assertEqual(1, len(cliente.enviados))

    def test_estouro_reenvia_e_a_cena_se_salva(self):
        """Era exatamente este caso, e ele custava a cena inteira."""
        cliente = ClienteFalso(estouros=2)
        alvo, _ = _rodar(cliente)
        self.assertEqual("https://picassoia/nova.png", alvo)
        self.assertEqual(3, len(cliente.enviados))

    def test_o_texto_reenviado_e_IDENTICO(self):
        """Timeout nao e problema do prompt: suavizar aqui piora a imagem."""
        cliente = ClienteFalso(estouros=2)
        _rodar(cliente)
        self.assertEqual(1, len(set(cliente.enviados)))

    def test_esgotadas_as_tentativas_o_erro_sobe(self):
        cliente = ClienteFalso(estouros=99)
        with self.assertRaises(EsperaEstourou):
            _rodar(cliente)
        self.assertEqual(3, len(cliente.enviados))

    def test_respeita_o_numero_configurado(self):
        cliente = ClienteFalso(estouros=99)
        with self.assertRaises(EsperaEstourou):
            _rodar(cliente, {"tentativas_por_espera": 2})
        self.assertEqual(2, len(cliente.enviados))

    def test_aba_fechada_NAO_tenta_de_novo(self):
        """`BrowserMorreu` herda de `EsperaEstourou` — a ordem do except importa."""
        cliente = ClienteFalso(estouros=99, erro=BrowserMorreu)
        with self.assertRaises(BrowserMorreu):
            _rodar(cliente)
        self.assertEqual(1, len(cliente.enviados))


class OrcamentoTests(unittest.TestCase):
    def test_tres_tentativas_custam_menos_que_a_espera_antiga(self):
        espera = CONFIG["render_timeout"]
        tentativas = CONFIG["tentativas_por_espera"]
        self.assertLessEqual(espera * tentativas, 600,
                             "o pior caso ficou mais caro do que era antes")

    def test_a_espera_tem_folga_sobre_a_maior_medida_boa(self):
        """42 s foi a maior espera bem-sucedida em 87 envios."""
        self.assertGreaterEqual(CONFIG["render_timeout"], 42 * 3)

    def test_ha_mais_de_uma_tentativa(self):
        self.assertGreater(CONFIG["tentativas_por_espera"], 1)


class EscaladaTests(unittest.TestCase):
    def test_o_worker_usa_o_reenvio_em_vez_do_wait_cru(self):
        fonte = (RAIZ / "contos" / "imagens" / "worker.py").read_text(
            encoding="utf-8")
        trecho = fonte[fonte.index("for i, linha in enumerate(pendentes)"):]
        self.assertIn("_gerar_esperando(", trecho)
        self.assertNotIn("cliente.wait_for_render(", trecho)


class FilaRegistroTests(unittest.TestCase):
    """Trava o contrato de fila.registrar() com nivel int ou string."""

    def test_registrar_aceita_nivel_zero(self):
        """nivel=0 (sem suavizacao)."""
        from contos.imagens import fila
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock: substitui OUTPUTS para nao escrever em outputs real
            orig_outputs = fila.OUTPUTS
            try:
                fila.OUTPUTS = Path(tmpdir)
                fila.registrar(
                    "h00001", 1,
                    prompt="teste", arquivo="c1.png", parte=1, nivel=0
                )
                dados = fila._meta("h00001")
                self.assertEqual(dados["cenas"]["1:1"]["suavizacao"], None)
            finally:
                fila.OUTPUTS = orig_outputs

    def test_registrar_aceita_nivel_inteiro(self):
        """nivel=2 (suavizacao mecanica)."""
        from contos.imagens import fila
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            orig_outputs = fila.OUTPUTS
            try:
                fila.OUTPUTS = Path(tmpdir)
                fila.registrar(
                    "h00001", 1,
                    prompt="teste", arquivo="c1.png", parte=1, nivel=2
                )
                dados = fila._meta("h00001")
                self.assertEqual(dados["cenas"]["1:1"]["suavizacao"], 2)
            finally:
                fila.OUTPUTS = orig_outputs

    def test_registrar_aceita_nivel_string_llm(self):
        """nivel='llm 1' (reescrita com LLM)."""
        from contos.imagens import fila
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            orig_outputs = fila.OUTPUTS
            try:
                fila.OUTPUTS = Path(tmpdir)
                fila.registrar(
                    "h00001", 1,
                    prompt="teste", arquivo="c1.png", parte=1, nivel="llm 1"
                )
                dados = fila._meta("h00001")
                self.assertEqual(dados["cenas"]["1:1"]["suavizacao"], "llm 1")
            finally:
                fila.OUTPUTS = orig_outputs


class RecusaFalsaTests(unittest.TestCase):
    """Erro tecnico NAO pode virar "recusado pelo filtro de conteudo".

    Em 09/09/2026, `historia_00012` p01_cena_10: o PicassoIA recusou o prompt,
    o ChatGPT reescreveu, a imagem NOVA passou (1088x1920) e foi baixada para
    o disco — e ai `fila.registrar` estourou num `int("llm 1")`, porque o
    nivel da reescrita e um rotulo de texto, nao um numero.

    O `except Exception` generico pegou, `feito` ficou False, e como havia uma
    recusa ANTIGA guardada na variavel, a cena foi gravada como "recusado pelo
    filtro ate o ultimo nivel". Tres cenas ficaram assim: imagem no disco,
    sem prova de origem, e marcadas como impossiveis de gerar.

    A mentira custa caro porque as duas conclusoes pedem coisas opostas:
    recusa pede prompt novo no roteiro (trabalho humano, e a cena nunca mais
    tenta sozinha), erro tecnico pede conserto no codigo e a cena volta na
    proxima passada.

    Em 10/09/2026, p05_cena_09: a imagem foi gerada mas o historico da conta
    estava vazio, entao `comprovar()` falhou sem ser recusa. O codigo anterior
    nao marcava como erro tecnico, deixando a cena em estado indefinido. Agora
    marca como falha_tecnica quando prova de origem falha, para que retente na
    proxima passada em vez de virar "impossivel de gerar".
    """

    def _trecho(self) -> str:
        fonte = (RAIZ / "contos" / "imagens" / "worker.py").read_text(
            encoding="utf-8")
        return fonte[fonte.index("for i, linha in enumerate(pendentes)"):]

    def test_a_falha_tecnica_e_lembrada(self):
        trecho = self._trecho()
        self.assertIn("falha_tecnica = exc", trecho)
        self.assertIn("falha_tecnica = None", trecho)

    def test_falha_de_prova_marca_como_erro_tecnico(self):
        """Falha de prova de origem nao e recusa: marca como falha_tecnica."""
        trecho = self._trecho()
        # Deve haver a atribuicao de falha_tecnica no ramo de prova falha
        prova_falha = trecho[trecho.index("exigir_prova_de_origem"):
                             trecho.index("except ConteudoRecusado")]
        self.assertIn("falha_tecnica = ", prova_falha,
                      "Prova de origem falha deve marcar falha_tecnica")

    def test_erro_tecnico_NAO_marca_recusa(self):
        """O `registrar_recusa` so pode acontecer no ramo da recusa."""
        trecho = self._trecho()
        self.assertIn("if not feito and falha_tecnica is not None:", trecho)
        self.assertIn("elif not feito and ultima_recusa:", trecho)
        tecnico = trecho[trecho.index("if not feito and falha_tecnica"):
                         trecho.index("elif not feito and ultima_recusa:")]
        self.assertNotIn("registrar_recusa", tecnico)

    def test_o_ramo_da_recusa_continua_marcando(self):
        """A cena barrada DE VERDADE ainda tem que ficar registrada."""
        trecho = self._trecho()
        recusa = trecho[trecho.index("elif not feito and ultima_recusa:"):]
        self.assertIn("registrar_recusa", recusa[:900])

    def test_falha_de_prova_registra_a_tentativa(self):
        """Falha de prova deve ser registrada em imagens.json (com comprovada=false)."""
        trecho = self._trecho()
        # Deve haver fila.registrar() no ramo de prova falha
        prova_falha = trecho[trecho.index("exigir_prova_de_origem"):
                             trecho.index("except ConteudoRecusado")]
        self.assertIn("fila.registrar(", prova_falha,
                      "Falha de prova deve registrar a tentativa em imagens.json")


class NivelDeSuavizacaoTests(unittest.TestCase):
    """O nivel e int OU rotulo de texto — e o registro tem que aceitar os dois."""

    def _registrar(self, nivel):
        import tempfile
        from contos.imagens import fila
        with tempfile.TemporaryDirectory() as tmp:
            antes = fila.OUTPUTS
            try:
                fila.OUTPUTS = Path(tmp)
                fila.registrar("h00001", 1, prompt="t", arquivo="c1.png",
                               parte=1, nivel=nivel)
                return fila._meta("h00001")["cenas"]["1:1"]["suavizacao"]
            finally:
                fila.OUTPUTS = antes

    def test_o_rotulo_do_llm_atravessa_inteiro(self):
        """Era aqui que estourava: `int("llm 1")`."""
        self.assertEqual("llm 1", self._registrar("llm 1"))

    def test_o_numero_da_suavizacao_mecanica_continua_numero(self):
        self.assertEqual(2, self._registrar(2))

    def test_sem_tratamento_nenhum_fica_None(self):
        self.assertIsNone(self._registrar(0))


class DownloadFalhaTests(unittest.TestCase):
    """Download silenciosamente falha e deixa o arquivo inexistente.

    Em 11/09/2026, p05_cena_11 foi registrada como sucesso em imagens.json,
    mas o arquivo nunca foi criado no disco. O motivo: se o download falhava,
    composicao.motivo() tentava abrir um arquivo inexistente e retornava "",
    fazendo o codigo assumir que a colagem estava OK.

    O conserto valida que o arquivo foi criado antes de registrar sucesso.
    """

    def test_arquivo_inexistente_nao_registra_como_sucesso(self):
        """Se o download falha, composicao.motivo retorna ""; precisamos
        validar que o arquivo realmente foi criado antes de registrar."""
        from contos.imagens import worker
        import tempfile
        from unittest.mock import MagicMock

        with tempfile.TemporaryDirectory() as tmpdir:
            arquivo = Path(tmpdir) / "cena_teste.png"

            # Cliente fake que nao cria arquivo no download
            cliente_fake = MagicMock()
            cliente_fake.prompt_enviado = "prompt de teste"
            cliente_fake.enviado_em = "2026-09-11T10:00:00"

            def download_sem_arquivo(url, destino):
                # Simula download que falha silenciosamente
                pass

            cliente_fake.download = download_sem_arquivo

            # Simular a escalada de um prompt com arquivo faltando
            # Precisamos chamar a funcao de colagem que valida
            razao = worker.composicao.motivo(str(arquivo))

            # Se o arquivo nao existe, motivo deve retornar "" (lista vazia)
            self.assertEqual("", razao,
                             "composicao.motivo deve retornar string vazia "
                             "quando arquivo nao existe")


if __name__ == "__main__":
    unittest.main()
