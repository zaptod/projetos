"""Publicar so depois de processar — mas nunca perder o video por esperar.

Medido em `outputs/postar.txt` (16/09/2026), com a medicao que entrou no dia
anterior: seis publicacoes sairam com a barra do Studio dizendo "subindo",
tres dizendo "processando (N minutos restantes)" e duas em "sd". O botao
`#done-button` habilita quando o ARQUIVO TERMINA DE SUBIR, e nao quando o
YouTube termina de processar — entao "botao habilitado" nunca foi prova de
pronto. O video ia ao ar antes de existir nem em SD, justamente na primeira
hora, que e quando o algoritmo mede o Short.

E metade dos "Publicar mesmo assim" coincidia com isso.

O QUE CADA ESTAGIO SIGNIFICA decide o desfecho, e o proprio `FASES` ja
dizia: "processando ate SD" quer dizer que NAO HA NADA PRONTO ainda;
"processando ate HD" quer dizer que o SD ja existe. Tratar os dois como a
mesma coisa era o que escondia o problema — e dar a eles o mesmo DESFECHO
seria repetir o erro do outro lado.

O contrato:

1. `hd` -> clica na hora. Esperar por nada atrasa a grade.
2. `subindo`/`processando` -> espera; no estouro do teto NAO publica. O
   arquivo nao chegou inteiro, ou nada e assistivel: publicar ali e o
   rascunho quebrado. Vira atrasado e sai depois inteiro.
3. `sd` -> espera; no estouro do teto PUBLICA. Ja existe video de verdade, que
   melhora sozinho. Um Short em SD na primeira hora rende mais que um Short
   perfeito que nao saiu.
4. `desconhecida` -> espera COMO SE FOSSE `processando`, relendo a tela. "Nao
   consegui ler" nao e "pronto": e o mesmo erro do botao habilitado e do
   `None` que virava `False` (login-do-llm-tres-estados). No estouro publica
   — uma troca de layout do Studio nao pode derrubar todas as postagens —
   mas grava ERRO no diario, para a apuracao pegar na primeira vez.
5. O teto sai da GRADE (`min(5 min, ate o proximo horario - margem)`), com
   piso de 30 s para a rodada que comeca atrasada. "Uma rodada, um horario"
   continua valendo por construcao.
6. Qualquer excecao na espera cai direto no clique. O codigo novo nao pode
   ser um jeito novo de perder postagem.
7. A medida de quando o botao habilitou continua gravada. Foi ela que provou
   o problema; troca-la pela medida do fim apagaria a evidencia.
"""
import unittest
from unittest.mock import patch

from builds.publicar import youtube_web


class _Passos(list):
    def __call__(self, texto):
        self.append(texto)


def _estagio(qualidade, falta="", reconhecido=True):
    return {"qualidade": qualidade, "falta": falta, "texto": "",
            "reconhecido": reconhecido, "escopo": "dialogo"}


class _Relogio:
    """Relogio falso: so anda quando o codigo dorme.

    Sem ele um teto de 30 s ou faria o teste demorar 30 s de verdade, ou (com
    `sleep` anulado) giraria milhoes de vezes ate o relogio real chegar la.
    """

    def __init__(self):
        self.agora = 1000.0

    def monotonic(self):
        return self.agora

    def sleep(self, s):
        self.agora += s


class EsperarProcessarTests(unittest.TestCase):
    def _rodar(self, estagios, limite=300.0, canal="builds"):
        """`estagios` e o que a barra mostra em cada leitura, em ordem."""
        restantes = list(estagios)
        lidas = []
        relogio = _Relogio()

        def ler(_page):
            e = restantes.pop(0) if len(restantes) > 1 else restantes[0]
            lidas.append(e["qualidade"])
            return e

        passo, laudo, diario = _Passos(), {}, []
        with patch.object(youtube_web, "_qualidade_agora", ler), \
             patch.object(youtube_web.time, "sleep", relogio.sleep), \
             patch.object(youtube_web.time, "monotonic", relogio.monotonic), \
             patch.object(youtube_web.atividade, "registrar",
                          lambda *a, **k: diario.append((a, k))):
            fim = youtube_web._esperar_qualidade(
                None, passo, laudo, canal=canal, limite_s=limite)
        return fim, laudo, passo, lidas, diario

    # -------------------------------------------------- 1 e 2: o caso feliz
    def test_espera_subindo_ate_ficar_hd(self):
        fim, laudo, passo, lidas, _ = self._rodar([
            _estagio("subindo", "10 minutos restantes"),
            _estagio("processando", "3 minutos restantes"),
            _estagio("hd"),
        ])
        self.assertEqual("hd", fim["qualidade"])
        self.assertEqual(["subindo", "processando", "hd"], lidas)
        self.assertEqual("subindo", laudo["qualidade_ao_habilitar"],
                         "a medida que provou o problema nao pode sumir")
        self.assertEqual("hd", laudo["qualidade_no_clique"])
        self.assertFalse(laudo.get("estourou_a_espera"))
        self.assertTrue(any("esper" in p.lower() for p in passo))
        self.assertFalse(youtube_web._nao_publicar_ainda(fim))

    def test_sd_tambem_e_esperado_enquanto_da(self):
        """`sd` espera o HD, mas ja pode sair — sao coisas diferentes."""
        fim, _, _, lidas, _ = self._rodar([_estagio("sd"), _estagio("hd")])
        self.assertEqual("hd", fim["qualidade"])
        self.assertEqual(["sd"], lidas[:1])

    def test_ja_em_hd_nao_espera(self):
        fim, laudo, _, lidas, _ = self._rodar([_estagio("hd")])
        self.assertEqual("hd", fim["qualidade"])
        self.assertEqual(1, len(lidas), "esperar por nada atrasa a grade")
        self.assertEqual(0.0, laudo["esperou_s"])

    # ------------------------------------ 2: estouro em subindo/processando
    def test_estouro_em_processando_NAO_publica(self):
        fim, laudo, _, _, _ = self._rodar(
            [_estagio("processando", "40 minutos restantes")], limite=30.0)
        self.assertEqual("processando", fim["qualidade"],
                         "devolve o estagio real, sem maquiar")
        self.assertTrue(laudo["estourou_a_espera"])
        self.assertTrue(
            youtube_web._nao_publicar_ainda(fim),
            "nada assistivel existe: publicar aqui e o rascunho quebrado")

    def test_estouro_em_subindo_NAO_publica(self):
        fim, _, _, _, _ = self._rodar(
            [_estagio("subindo", "40 minutos restantes")], limite=30.0)
        self.assertTrue(youtube_web._nao_publicar_ainda(fim),
                        "o arquivo nem chegou inteiro")

    # ------------------------------------------------- 3: estouro em sd
    def test_estouro_em_sd_PUBLICA(self):
        """Um Short em SD na primeira hora rende mais que um que nao saiu."""
        fim, laudo, _, _, _ = self._rodar(
            [_estagio("sd", "20 minutos restantes")], limite=30.0)
        self.assertEqual("sd", fim["qualidade"])
        self.assertTrue(laudo["estourou_a_espera"])
        self.assertFalse(youtube_web._nao_publicar_ainda(fim))

    # ------------------------------------------- 4: "nao sei" nao e "pronto"
    def test_desconhecida_ESPERA(self):
        """Foi o erro do botao habilitado e o do `None` que virava `False`."""
        fim, _, _, lidas, _ = self._rodar([
            _estagio("desconhecida", reconhecido=False),
            _estagio("desconhecida", reconhecido=False),
            _estagio("hd"),
        ])
        self.assertEqual("hd", fim["qualidade"])
        self.assertEqual(3, len(lidas), "tinha de reler a tela")

    def test_desconhecida_ate_o_fim_publica_MAS_grava_ERRO(self):
        fim, laudo, _, _, diario = self._rodar(
            [_estagio("desconhecida", reconhecido=False)], limite=30.0)
        self.assertEqual("desconhecida", fim["qualidade"])
        self.assertFalse(
            youtube_web._nao_publicar_ainda(fim),
            "uma troca de layout do Studio nao pode derrubar as postagens")
        self.assertTrue(laudo["estourou_a_espera"])
        self.assertTrue(diario, "sem ERRO ninguem descobre a troca de layout")
        self.assertEqual(youtube_web.atividade.ERRO, diario[0][0][1])

    def test_o_ERRO_vai_para_o_canal_certo(self):
        _, _, _, _, diario = self._rodar(
            [_estagio("desconhecida", reconhecido=False)], limite=30.0,
            canal="historias")
        self.assertIn("historias", diario[0][0])

    def test_hd_nao_grava_erro(self):
        _, _, _, _, diario = self._rodar([_estagio("hd")])
        self.assertEqual([], diario)

    # --------------------------------------------------- 5: o teto e a grade
    def test_o_teto_sai_da_grade_e_respeita_o_piso(self):
        teto = youtube_web._teto_da_espera()
        self.assertGreaterEqual(teto, youtube_web.PISO_DA_ESPERA_S)
        self.assertLessEqual(teto, youtube_web.ESPERA_QUALIDADE_S)

    def test_o_teto_e_DERIVADO_e_nao_um_numero_escrito(self):
        """Um teto fixo cabe na grade de hoje e deixa de caber no dia em que
        alguem mexer nos horarios, em silencio."""
        import inspect
        fonte = inspect.getsource(youtube_web._teto_da_espera)
        self.assertIn("grade", fonte)

    def test_grade_quebrada_nao_derruba_a_espera(self):
        with patch.object(youtube_web, "ESPERA_QUALIDADE_S", 300.0):
            with patch.dict("sys.modules", {"builds.grade": None}):
                self.assertGreaterEqual(youtube_web._teto_da_espera(),
                                        youtube_web.PISO_DA_ESPERA_S)

    # ------------------------------------------ 6: nao virar um jeito de perder
    def test_erro_na_leitura_cai_no_clique(self):
        """O codigo novo nao pode ser um jeito novo de perder postagem."""
        def explode(_page):
            raise RuntimeError("o dialogo sumiu")

        passo, laudo = _Passos(), {}
        with patch.object(youtube_web, "_qualidade_agora", explode), \
             patch.object(youtube_web.time, "sleep", lambda _s: None), \
             patch.object(youtube_web.atividade, "registrar",
                          lambda *a, **k: None):
            fim = youtube_web._esperar_qualidade(
                None, passo, laudo, limite_s=0.0)
        self.assertEqual("desconhecida", fim["qualidade"])
        self.assertFalse(youtube_web._nao_publicar_ainda(fim))
        self.assertIn("qualidade_no_clique", laudo)


class AGuardaEstaNoCaminhoRealTests(unittest.TestCase):
    """Uma funcao certa que ninguem chama conserta zero videos."""

    def _fonte_sem_comentario(self):
        import inspect
        fonte = inspect.getsource(youtube_web.publicar)
        return "\n".join(l for l in fonte.splitlines()
                         if not l.strip().startswith("#"))

    def test_publicar_espera_antes_de_clicar(self):
        fonte = self._fonte_sem_comentario()
        i_espera = fonte.find("_esperar_qualidade(")
        i_clique = fonte.find("pronto.click()")
        self.assertNotEqual(-1, i_espera, "publicar tem de usar a espera")
        self.assertNotEqual(-1, i_clique)
        self.assertLess(i_espera, i_clique,
                        "esperar DEPOIS de clicar nao conserta nada")

    def test_a_guarda_fica_entre_a_espera_e_o_clique(self):
        fonte = self._fonte_sem_comentario()
        i_guarda = fonte.find("_nao_publicar_ainda(")
        self.assertNotEqual(-1, i_guarda, "medir sem segurar foi o passo 1")
        self.assertLess(fonte.find("_esperar_qualidade("), i_guarda)
        self.assertLess(i_guarda, fonte.find("pronto.click()"))

    def test_a_espera_quebrada_nao_cancela_a_postagem(self):
        """A espera e ganho de qualidade; ficar sem video e o pior desfecho."""
        fonte = self._fonte_sem_comentario()
        trecho = fonte[fonte.find("_esperar_qualidade("):
                       fonte.find("pronto.click()")]
        self.assertIn("except", trecho)


class FasesTests(unittest.TestCase):
    def test_salvando_conta_como_subindo(self):
        """Na prova da `historia_00016:celular:p02` a barra dizia
        "salvando..." com 10 minutos pela frente e nenhuma frase casava: a
        medicao ficava cega no momento que ela existe para medir."""
        frases = dict(youtube_web.FASES)["subindo"]
        self.assertIn("salvando", frases)
        self.assertIn("saving", frases)


if __name__ == "__main__":
    unittest.main()
