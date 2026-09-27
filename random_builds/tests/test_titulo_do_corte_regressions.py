"""A chave de titulo passa a enxergar a parte que virou dois Shorts.

MEDIDO EM 17/09/2026, casando o ledger com o canal de historias: a
`historia_00003` tem SEIS conteudos publicados em DUPLICATA — as partes 1 a
3 com o video inteiro E os dois pedacos no ar, e as partes 4 a 6 com dois
pares de pedacos, de rodadas de upload diferentes. 96 videos no canal para
79 conteudos distintos.

A chave nao enxergava nada disso: o ledger guarda "(Parte 4)" e o canal
guarda "(Parte 4) (1 de 2)". Chaves diferentes, comparacao sempre negativa —
e foi por esse falso negativo que eu reportei cinco videos PUBLICOS como
"publicacoes fantasma", duas vezes, antes de olhar a lista do canal.

POR QUE TIRAR O SUFIXO E SEGURO PARA AS GUARDAS: nenhuma delas roda por
pedaco. `publicar_youtube` percorre `cortes.preparar` dentro de UMA
publicacao (dois uploads, uma linha de ledger, `prova` em lista), e o titulo
repetido e o rodizio decidem sobre o item do CATALOGO, que e sempre inteiro.
Medido antes de mexer, e nao suposto.

E ONDE ELE NAO E SEGURO, que e o motivo de `corte` existir: ao escolher
videos PRIVADOS para voltar ao ar, "(1 de 2)" e "(2 de 2)" sao dois arquivos
e os dois precisam sair. Deduplicar por conteudo ali escolheria um so e
deixaria metade da parte privada para sempre — quebrando a parte ao meio no
canal, que e pior que o problema original.
"""
import unittest

from builds.publicar import titulos


class ChaveTests(unittest.TestCase):
    def test_o_pedaco_casa_com_a_parte_inteira(self):
        """O caso que produziu o falso negativo."""
        self.assertEqual(
            titulos.chave("A historia oficial nao fecha (Parte 4)"),
            titulos.chave("A historia oficial nao fecha (Parte 4) (1 de 2)"))

    def test_os_dois_pedacos_casam_entre_si(self):
        self.assertEqual(
            titulos.chave("A frase que minha irma lembrou (Parte 5) (1 de 2)"),
            titulos.chave("A frase que minha irma lembrou (Parte 5) (2 de 2)"))

    def test_a_PARTE_continua_distinguindo(self):
        """O sufixo do corte sai; o da parte fica. Se os dois saissem, uma
        serie inteira viraria uma chave so e pararia na parte 1."""
        self.assertNotEqual(
            titulos.chave("Mesma historia (Parte 4) (1 de 2)"),
            titulos.chave("Mesma historia (Parte 5) (1 de 2)"))

    def test_o_corte_sai_e_a_parte_FICA(self):
        """A parte e a unica coisa que distingue dois videos da mesma serie;
        o corte nao pode leva-la junto."""
        self.assertIn("parte 4", titulos.chave("Um titulo (Parte 4) (1 de 2)"))

    def test_o_corte_sai_antes_do_sufixo_de_parte_com_total(self):
        """No formato "(Parte 3/6)" a parte vira SUFIXO da chave, e ela so e
        reconhecida se estiver no fim — ou seja, depois de o corte sair."""
        k = titulos.chave("Um titulo (Parte 3/6) (1 de 2)")
        self.assertTrue(k.endswith("parte 3 de 6"), k)

    def test_titulo_sem_corte_nao_muda(self):
        self.assertEqual(titulos.chave("Build 60/100 BUILD FORTE"),
                         titulos.chave("Build 60/100 BUILD FORTE"))
        self.assertNotIn(" de ", titulos.chave("Build 60/100 BUILD FORTE"))

    def test_nao_come_numero_que_faz_parte_do_titulo(self):
        """"3 de 4" no MEIO do titulo nao e sufixo de corte."""
        k = titulos.chave("Ele pagou 3 de 4 parcelas e sumiu")
        self.assertIn("3 de 4", k)

    def test_vazio_continua_vazio(self):
        self.assertEqual("", titulos.chave(""))
        self.assertEqual("", titulos.chave("   "))


class CorteTests(unittest.TestCase):
    def test_reconhece_o_pedaco(self):
        self.assertEqual((1, 2), titulos.corte("Um titulo (1 de 2)"))
        self.assertEqual((2, 2), titulos.corte("Um titulo (2 de 2)"))

    def test_titulo_inteiro_nao_tem_corte(self):
        self.assertIsNone(titulos.corte("Um titulo (Parte 4)"))
        self.assertIsNone(titulos.corte("Um titulo"))
        self.assertIsNone(titulos.corte(""))

    def test_nao_confunde_parte_com_corte(self):
        """"(Parte 3 de 6)" e parte, nao pedaco."""
        self.assertIsNone(titulos.corte("Um titulo (Parte 3 de 6)"))


class NaEscolhaDosPrivadosTests(unittest.TestCase):
    """Os dois pedacos de uma parte privada tem de voltar ao ar, os DOIS."""

    def test_os_dois_pedacos_sobrevivem_a_deduplicacao(self):
        from unittest.mock import patch
        from builds.publicar import recuperar

        def _v(vid, titulo, quando):
            return {"id": vid, "titulo": titulo, "descricao": "uma descricao",
                    "quando": quando, "privacidade": "private",
                    "upload": "processed", "duracao": "PT1M30S"}

        canal = [_v("a", "A parte longa (Parte 4) (1 de 2)",
                    "2026-09-10T10:00:00Z"),
                 _v("b", "A parte longa (Parte 4) (2 de 2)",
                    "2026-09-10T10:01:00Z")]
        with patch.object(recuperar, "videos_do_canal",
                          lambda _c=None, _t=None: canal):
            fora = recuperar.recuperaveis("historias", token="x")
        self.assertEqual({"a", "b"}, {v["id"] for v in fora},
                         "deduplicar por conteudo deixaria metade da parte "
                         "privada para sempre")

    def test_a_MESMA_metade_repetida_ainda_deduplica(self):
        from unittest.mock import patch
        from builds.publicar import recuperar

        def _v(vid, titulo, quando):
            return {"id": vid, "titulo": titulo, "descricao": "uma descricao",
                    "quando": quando, "privacidade": "private",
                    "upload": "processed", "duracao": "PT1M30S"}

        canal = [_v("a", "A parte longa (Parte 4) (1 de 2)",
                    "2026-09-10T10:00:00Z"),
                 _v("a2", "A parte longa (Parte 4) (1 de 2)",
                    "2026-09-11T10:00:00Z")]
        with patch.object(recuperar, "videos_do_canal",
                          lambda _c=None, _t=None: canal):
            fora = recuperar.recuperaveis("historias", token="x")
        self.assertEqual(1, len(fora), "o mesmo pedaco duas vezes e duplicata")

    def test_metade_publica_NAO_derruba_a_outra_metade(self):
        """O crivo do irmao publico tambem partia a parte ao meio.

        Medido em 27/09/2026: com `titulos.chave` ignorando o "(N de M)", a
        metade "(1 de 2)" publica passou a ter a MESMA chave da "(2 de 2)"
        privada, e o crivo 4 ("titulo que ja tem irmao publico sai") apagava
        a segunda antes de qualquer deduplicacao. A parte ficava partida no
        canal para sempre — o defeito que o resto deste trabalho conserta.
        """
        from unittest.mock import patch
        from builds.publicar import recuperar

        canal = [_video("a", "A parte longa (Parte 4) (1 de 2)",
                        "2026-09-10T10:00:00Z", "public"),
                 _video("b", "A parte longa (Parte 4) (2 de 2)",
                        "2026-09-10T10:01:00Z", "private")]
        with patch.object(recuperar, "videos_do_canal",
                          lambda _c=None, _t=None: canal):
            fora = recuperar.recuperaveis("historias", token="x")
        self.assertEqual(["b"], [v["id"] for v in fora])

    def test_video_inteiro_publico_barra_o_pedaco_privado(self):
        """O outro lado: cobrir o conteudo e o que o crivo 4 existe para ver.

        E o caso `historia_00003` (17/09/2026), em que o video inteiro E os
        dois pedacos foram para o ar. Recuperar o pedaco aqui duplicaria de
        novo o conteudo que ja esta publico.
        """
        from unittest.mock import patch
        from builds.publicar import recuperar

        canal = [_video("w", "A parte longa (Parte 4)",
                        "2026-09-10T10:00:00Z", "public"),
                 _video("b", "A parte longa (Parte 4) (2 de 2)",
                        "2026-09-10T10:01:00Z", "private")]
        with patch.object(recuperar, "videos_do_canal",
                          lambda _c=None, _t=None: canal):
            fora = recuperar.recuperaveis("historias", token="x")
        self.assertEqual([], fora)

    def test_pedaco_publico_barra_o_video_inteiro_privado(self):
        """Metade no ar ja e conteudo no ar: o inteiro privado nao sai.

        Publicar o inteiro por cima de um pedaco publico e exatamente como a
        `historia_00003` virou seis duplicatas no canal.
        """
        from unittest.mock import patch
        from builds.publicar import recuperar

        canal = [_video("a", "A parte longa (Parte 4) (1 de 2)",
                        "2026-09-10T10:00:00Z", "public"),
                 _video("w", "A parte longa (Parte 4)",
                        "2026-09-10T10:01:00Z", "private")]
        with patch.object(recuperar, "videos_do_canal",
                          lambda _c=None, _t=None: canal):
            fora = recuperar.recuperaveis("historias", token="x")
        self.assertEqual([], fora)

    def test_titulo_igual_sem_corte_continua_barrado_pelo_publico(self):
        """O crivo 4 original (os rascunhos gemeos) nao pode ter afrouxado."""
        from unittest.mock import patch
        from builds.publicar import recuperar

        canal = [_video("a", "Um build qualquer", "2026-09-10T10:00:00Z",
                        "public"),
                 _video("b", "Um build qualquer", "2026-09-10T10:01:00Z",
                        "private")]
        with patch.object(recuperar, "videos_do_canal",
                          lambda _c=None, _t=None: canal):
            fora = recuperar.recuperaveis("historias", token="x")
        self.assertEqual([], fora)


def _video(vid: str, titulo: str, quando: str, privacidade: str) -> dict:
    """Video do canal como `videos_do_canal` o devolve, com privacidade a mao."""
    return {"id": vid, "titulo": titulo, "descricao": "uma descricao",
            "quando": quando, "privacidade": privacidade,
            "upload": "processed", "duracao": "PT1M30S"}


if __name__ == "__main__":
    unittest.main()
