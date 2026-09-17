"""O publicador pergunta "saiu?" de UM jeito so, e a cura depende disso.

Ate 16/09/2026 cada leitor respondia com `bool(linha["url"])`. Mas o `url`
guardava TRES coisas: o link, a frase de estado ("publicado no YouTube (com a
confirmacao extra)") e, no TikTok, SEMPRE a frase. Entao rascunho e
publicacao de verdade ficavam identicos para todo filtro do projeto — foi
assim que 30 rascunhos contaram como publicados.

A cura do ledger (d2) tira a frase do `url` das linhas de TikTok e marca cada
linha com `publicado`. Enquanto o publicador ler `url`, gravar essa cura
apagaria a guarda de "ja esta no TikTok" de 46 builds e 51 historias — e eles
voltariam a ser postados. **A migracao vem ANTES da cura, nunca depois**, e e
por isso que o `curar_ledger` recusa gravar enquanto `CONTRATO_DO_LEDGER` nao
for 2.

O que fica travado aqui:
1. O contrato declarado, que e o que a cura confere.
2. Nenhum ponto do publicador decide "saiu?" pelo `url` — a varredura da cura
   procura exatamente esse padrao no fonte.
3. O comportamento NAO muda hoje: nenhuma linha tem o campo `publicado`,
   entao `publicado()` cai no criterio antigo. Migrar nao pode mexer no que
   sai enquanto o ledger nao for curado.
4. E o caso que a cura VAI criar: `url` vazia com `publicado: True` conta
   como publicado. Se isso falhar, a cura devolve videos para a fila.
"""
import importlib.util
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
POSTAR = RAIZ / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_contrato", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


postar = _postar()

def _leituras_por_url(fonte: str):
    """A varredura DA PROPRIA CURA, e nao uma copia dela.

    A primeira versao deste teste copiava a regex antiga do `curar_ledger`.
    Copia diverge: desde `db55cae` a varredura le a ARVORE do codigo (ast), e
    a regex que eu tinha copiado nem via leitura atribuida a uma variavel.
    Um teste que confere um criterio diferente do portao nao protege do
    portao — protege de uma lembranca dele.
    """
    import importlib.util
    caminho = RAIZ / "ferramentas" / "curar_ledger.py"
    spec = importlib.util.spec_from_file_location("curar_varredura", caminho)
    curar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(curar)
    return curar.leituras_por_url(fonte)


class ContratoTests(unittest.TestCase):
    def test_o_contrato_esta_declarado(self):
        self.assertGreaterEqual(postar.CONTRATO_DO_LEDGER, 2)

    def test_nenhum_ponto_decide_saiu_pelo_url(self):
        """Pela varredura da cura, que le a arvore e ignora comentario."""
        fonte = POSTAR.read_text(encoding="utf-8")
        self.assertEqual([], _leituras_por_url(fonte),
                         "a cura recusa gravar enquanto houver leitura por url")

    def test_comentario_nao_conta_como_leitura(self):
        """Eu acusei, no meu proprio teste, uma leitura que estava dentro do
        comentario que explicava por que ela nao existia."""
        self.assertEqual(
            [], _leituras_por_url('# if linha.get("url")\nx = 1\n'))

    def test_a_cura_libera_a_gravacao(self):
        """O portao de verdade, e nao a nossa leitura dele."""
        caminho = RAIZ / "ferramentas" / "curar_ledger.py"
        if not caminho.is_file():
            self.skipTest("curar_ledger.py ainda nao existe")
        spec = importlib.util.spec_from_file_location("curar_teste", caminho)
        curar = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(curar)
        self.assertEqual("", curar.postar_migrado())


class SaiuTests(unittest.TestCase):
    def test_link_de_verdade(self):
        self.assertTrue(postar._saiu({"url": "https://youtu.be/abc"}))

    def test_frase_de_estado_ainda_conta_HOJE(self):
        """Linha antiga, sem o campo: cai no criterio de antes. Migrar nao
        pode mudar o que sai enquanto o ledger nao for curado."""
        self.assertTrue(postar._saiu({"url": "publicado no TikTok"}))

    def test_publicado_FALSE_vence_o_url(self):
        """O rascunho curado: tem frase no url e nao saiu."""
        self.assertFalse(
            postar._saiu({"url": "publicado no TikTok", "publicado": False}))

    def test_publicado_TRUE_sem_url_conta(self):
        """O que a cura vai gravar. Se isto falhar, ela devolve video para a
        fila e o canal reposta."""
        self.assertTrue(postar._saiu({"url": "", "publicado": True}))

    def test_linha_vazia_e_lixo_nao_contam(self):
        for ruim in ({}, {"url": ""}, None, "texto", []):
            with self.subTest(ruim=ruim):
                self.assertFalse(postar._saiu(ruim))


class SemQuedaLocalTests(unittest.TestCase):
    """`_saiu` NAO tem queda local, e a ausencia dela e deliberada.

    Eu escrevi uma, e a varredura da cura a recusou — com razao. Qualquer
    queda ou volta ao criterio antigo (e ai, depois da cura, diz "nao saiu"
    para 46 builds e 51 historias, e a recuperacao reposta os noventa e
    sete), ou olha so o campo `publicado` (e ai diz "nao saiu" para toda
    linha anterior a cura). As duas erram feio, em silencio, num caminho
    raro.

    E ela nao protegeria nada: todo chamador de `_saiu` acabou de chamar
    `publicados()` na linha de cima. Se `metricas` nao importa, a rodada ja
    esta morta — adivinhar so troca falha visivel por decisao errada calada.
    """

    def setUp(self):
        import builds.publicar.metricas as M
        self.addCleanup(setattr, M, "publicado", M.publicado)

        def explode(_l):
            raise ImportError("metricas indisponivel")
        M.publicado = explode
        from builds import atividade
        self.addCleanup(setattr, atividade, "registrar", atividade.registrar)
        self.diario = []
        atividade.registrar = lambda *a, **k: self.diario.append(a)

    def test_sem_metricas_ele_LEVANTA_em_vez_de_adivinhar(self):
        with self.assertRaises(ImportError):
            postar._saiu({"url": "", "publicado": True})

    def test_e_registra_ERRO_antes_de_levantar(self):
        """Defeito de ambiente que ninguem veria de outro jeito."""
        with self.assertRaises(ImportError):
            postar._saiu({"url": "x"})
        self.assertTrue(self.diario, "a falha tem de ser contada")
        from builds import atividade
        self.assertEqual(atividade.ERRO, self.diario[0][1])


if __name__ == "__main__":
    unittest.main()
