"""Devolver ao ar o que ficou privado por defeito nosso, sem duplicar nada.

MEDIDO EM 17/09/2026, canal de builds: 134 videos na playlist de envios, 51
privados. 29 tem gemeo publico com o mesmo titulo (os rascunhos da fabrica
que fechou em 811cf5a) e publica-los DUPLICARIA o canal; 16 sao conteudo
distinto que nunca foi ao ar, todos inteiros, o mais velho esperando desde
31/08; 2 sao envios de teste sem descricao; 4 sao dois pares principal/
variante que repetem titulo entre si.

Entao a recuperacao nao e "tornar publico o que esta privado" — e escolher,
e cada crivo aqui veio de um caso que existe no canal agora.

Os dois defeitos que estes testes travam, e o primeiro ja aconteceu no
desenho desta mesma tarde:

1. `ESCOPO in credencial.escopo` da POSITIVO para quem so le. O escopo de
   edicao (".../auth/youtube") e substring de ".../auth/youtube.readonly" e
   de ".../auth/youtube.upload". Escrito com `in`, a guarda passaria com a
   credencial de hoje e o 403 chegaria no meio do lote, com metade dos
   videos recuperados e nenhuma mensagem util.

2. `videos.update` SUBSTITUI a parte que se manda. Mandar so
   `{"privacyStatus": "public"}` apaga `selfDeclaredMadeForKids` — o video
   volta ao ar com a declaracao de publico infantil zerada, que e questao
   legal e nao detalhe.

E a conferencia depois: "a API respondeu 200" e a mesma classe de prova que
"o botao estava habilitado" — diz que o pedido foi aceito, nao que o estado
mudou.
"""
import unittest
from unittest.mock import patch

from builds.publicar import recuperar
from builds.publicar.youtube import Credenciais, PublicacaoFalhou


def _video(vid, titulo, privacidade="private", upload="processed",
           descricao="uma descricao de verdade", quando="2026-09-10T10:00:00"):
    return {"id": vid, "titulo": titulo, "descricao": descricao,
            "quando": quando, "privacidade": privacidade, "upload": upload,
            "duracao": "PT1M19S"}


class EscopoTests(unittest.TestCase):
    SO_LEITURA = ("https://www.googleapis.com/auth/youtube.readonly "
                  "https://www.googleapis.com/auth/youtube.upload "
                  "https://www.googleapis.com/auth/yt-analytics.readonly")

    def _cred(self, escopo):
        return Credenciais("id", "segredo", "refresh", escopo)

    def test_o_escopo_de_HOJE_nao_pode_editar(self):
        """Era o escopo real da conta em 17/09/2026, e `in` dizia que sim."""
        self.assertFalse(recuperar.pode_editar(self._cred(self.SO_LEITURA)))

    def test_o_escopo_de_edicao_pode(self):
        cred = self._cred(self.SO_LEITURA + " " + recuperar.ESCOPO_EDICAO)
        self.assertTrue(recuperar.pode_editar(cred))

    def test_credencial_antiga_sem_campo_nao_pode(self):
        self.assertFalse(recuperar.pode_editar(self._cred("")))
        self.assertFalse(recuperar.pode_editar(None))

    def test_a_mensagem_diz_o_comando_exato(self):
        with patch.object(recuperar, "carregar_credenciais",
                          lambda *a, **k: self._cred(self.SO_LEITURA)):
            with self.assertRaises(recuperar.FaltaEscopo) as caso:
                recuperar._token("builds")
        texto = str(caso.exception)
        self.assertIn("youtube_oauth", texto)
        self.assertIn("--com-edicao", texto)
        self.assertNotIn("Studio", texto.replace(
            "NAO tento pelo Studio", ""), "nao existe plano B pelo navegador")

    def test_falta_de_escopo_NAO_e_erro_de_tentar_de_novo(self):
        """Erro proprio: a resposta e uma autorizacao no navegador, do dono
        da conta, uma vez — e nao uma nova tentativa."""
        self.assertTrue(issubclass(recuperar.FaltaEscopo, PublicacaoFalhou))


class EscolhaTests(unittest.TestCase):
    """Cada crivo veio de um caso que existe no canal agora."""

    def _recuperaveis(self, todos, conhecidos=None):
        with patch.object(recuperar, "videos_do_canal",
                          lambda _c=None, _t=None: todos):
            return recuperar.recuperaveis("builds", token="x",
                                          conhecidos=conhecidos)

    def test_o_desempate_prefere_quem_o_LEDGER_conhece(self):
        """Dos dois pares no canal, um tem a variante no ledger e o
        principal fora dele. Escolhendo pela data, a recuperacao pegaria o
        video de que nao da para escrever linha coerente — e ficaria sem
        registro do que fez."""
        fora = self._recuperaveis([
            _video("fora", "Erik build 87/100", quando="2026-09-15T10:08:00"),
            _video("dentro", "Erik build 87/100",
                   quando="2026-09-15T11:08:00"),
        ], conhecidos={"dentro"})
        self.assertEqual(["dentro"], [v["id"] for v in fora])

    def test_sem_lista_de_conhecidos_vale_o_mais_antigo(self):
        fora = self._recuperaveis([
            _video("novo", "Erik build 87/100", quando="2026-09-15T11:08:00"),
            _video("velho", "Erik build 87/100",
                   quando="2026-09-15T10:08:00"),
        ])
        self.assertEqual(["velho"], [v["id"] for v in fora])

    def test_o_privado_sozinho_volta(self):
        fora = self._recuperaveis([_video("a", "Brutus build 69/100")])
        self.assertEqual(["a"], [v["id"] for v in fora])

    def test_o_GEMEO_de_um_publico_NAO_volta(self):
        """Sao 29 no canal. Publicar duplicaria — o oposto do conserto."""
        fora = self._recuperaveis([
            _video("pub", "Elara build 56/100", privacidade="public"),
            _video("rascunho", "Elara build 56/100"),
        ])
        self.assertEqual([], fora)

    def test_titulo_repetido_ENTRE_privados_manda_o_mais_antigo(self):
        """Principal e variante do mesmo build. A variante existe para
        assumir quando o principal cai, e aqui ele nao caiu."""
        fora = self._recuperaveis([
            _video("b", "Cassia build 39/100", quando="2026-09-15T18:38:00"),
            _video("a", "Cassia build 39/100", quando="2026-09-15T15:09:00"),
        ])
        self.assertEqual(["a"], [v["id"] for v in fora])

    def test_sem_descricao_NAO_volta(self):
        """Os dois casos no canal eram envios de teste meus."""
        self.assertEqual([], self._recuperaveis(
            [_video("t", "final celular", descricao="")]))

    def test_ainda_processando_NAO_volta(self):
        """Publicar o que ainda processa foi o defeito de ontem (98e3737);
        repeti-lo aqui seria comico."""
        self.assertEqual([], self._recuperaveis(
            [_video("p", "Yuki build 61/100", upload="uploaded")]))

    def test_nao_listado_NAO_volta(self):
        """`unlisted` foi escolha de alguem, nao defeito nosso."""
        self.assertEqual([], self._recuperaveis(
            [_video("u", "Circe build 28/100", privacidade="unlisted")]))

    def test_o_publico_nunca_entra_na_lista(self):
        self.assertEqual([], self._recuperaveis(
            [_video("p", "Selene build 82/100", privacidade="public")]))

    def test_sai_na_ordem_do_envio(self):
        """O mais velho primeiro: ele esta esperando ha mais tempo."""
        fora = self._recuperaveis([
            _video("novo", "B", quando="2026-09-15T10:00:00"),
            _video("velho", "A", quando="2026-08-31T14:14:00"),
        ])
        self.assertEqual(["velho", "novo"], [v["id"] for v in fora])


class CanalCertoTests(unittest.TestCase):
    """O login e refeito por uma PESSOA, numa tela que lista todos os canais
    dela. Escolher o errado ali e um clique, e aconteceu em 17/09/2026.

    Depois disso a credencial funciona perfeitamente — autentica, lista,
    pagina — so que lista OUTRO canal. E a recuperacao, que so olha "privado
    sem gemeo publico", acharia dezenas de candidatos no canal pessoal dele e
    os tornaria publicos.
    """

    CERTO = "UCA3Y1SaahhDsMj4JKGLbQ-Q"

    def _com_identidade(self, gravado):
        import builds.contas as C
        self.addCleanup(setattr, C, "identidade", C.identidade)
        self.addCleanup(setattr, C, "ativa", C.ativa)
        C.ativa = lambda _s, _c="geral": "neural_fights"
        C.identidade = lambda _s, _conta: ({"id": gravado} if gravado else {})

    def test_o_canal_esperado_passa(self):
        self._com_identidade(self.CERTO)
        self.assertEqual(self.CERTO, recuperar.conferir_o_canal(
            "builds", {"id": self.CERTO, "snippet": {"title": "Neural"}}))

    def test_outro_canal_PARA_tudo(self):
        self._com_identidade(self.CERTO)
        with self.assertRaises(recuperar.CanalErrado) as caso:
            recuperar.conferir_o_canal("builds", {
                "id": "UC1IrqhQZJhaiYGT_0bQJcFA",
                "snippet": {"title": "Adrian Oliveira (pessoal)"}})
        texto = str(caso.exception)
        self.assertIn("Adrian Oliveira", texto, "diga QUAL canal ele abriu")
        self.assertIn(self.CERTO, texto, "e qual era o esperado")
        self.assertIn("youtube_oauth", texto, "e como refazer")

    def test_sem_identidade_gravada_PARA(self):
        """"Nao sei em que canal estou" nao pode virar "deve ser o certo"."""
        self._com_identidade("")
        with self.assertRaises(recuperar.CanalErrado):
            recuperar.conferir_o_canal("builds", {"id": self.CERTO})

    def test_a_listagem_confere_antes_de_listar(self):
        self._com_identidade(self.CERTO)
        chamou = []

        def get(_t, caminho, **_k):
            chamou.append(caminho)
            if caminho == "channels":
                return {"items": [{"id": "OUTRO", "snippet": {"title": "x"},
                                   "contentDetails": {"relatedPlaylists":
                                                      {"uploads": "UU"}}}]}
            raise AssertionError("nao pode chegar aqui")

        with patch.object(recuperar, "_get", get), \
             patch.object(recuperar, "_token", lambda _c, editar=True: "t"):
            with self.assertRaises(recuperar.CanalErrado):
                recuperar.videos_do_canal("builds")
        self.assertEqual(["channels"], chamou)


class _Resposta:
    def __init__(self, status=200, texto="{}"):
        self.status_code = status
        self.text = texto
        self.ok = 200 <= status < 300


class TornarPublicoTests(unittest.TestCase):
    STATUS = {"privacyStatus": "private", "selfDeclaredMadeForKids": False,
              "license": "youtube", "embeddable": True,
              "publicStatsViewable": True, "uploadStatus": "processed"}

    CANAL = "UCA3Y1SaahhDsMj4JKGLbQ-Q"

    def setUp(self):
        import builds.contas as C
        self.addCleanup(setattr, C, "identidade", C.identidade)
        self.addCleanup(setattr, C, "ativa", C.ativa)
        C.ativa = lambda _s, _c="geral": "neural_fights"
        C.identidade = lambda _s, _conta: {"id": self.CANAL}

    def _rodar(self, depois="public", status_put=200):
        self.enviado = {}
        leituras = [
            {"items": [{"status": dict(self.STATUS)}]},
            {"items": [{"status": {"privacyStatus": depois}}]},
        ]

        def get(_t, caminho, **_k):
            if caminho == "channels":
                return {"items": [{"id": self.CANAL,
                                   "snippet": {"title": "Neural fights"}}]}
            return leituras.pop(0)

        def put(_url, **kw):
            import json as _j
            self.enviado = _j.loads(kw["data"].decode("utf-8"))
            return _Resposta(status_put, "recusado")

        import builds.publicar.recuperar as R
        with patch.object(R, "_get", get), \
             patch.object(R, "_token", lambda _c: "tok"), \
             patch("requests.put", put):
            return R.tornar_publico("vid1", "builds")

    def test_muda_e_confere_no_canal(self):
        fora = self._rodar()
        self.assertTrue(fora["mudou"])
        self.assertEqual("private", fora["antes"])
        self.assertEqual("public", fora["depois"])

    def test_a_declaracao_de_publico_infantil_SOBREVIVE(self):
        """`videos.update` substitui a parte inteira. Mandar so o
        `privacyStatus` zeraria `selfDeclaredMadeForKids` — questao legal,
        nao detalhe."""
        self._rodar()
        status = self.enviado["status"]
        self.assertEqual("public", status["privacyStatus"])
        self.assertIn("selfDeclaredMadeForKids", status)
        self.assertEqual("youtube", status["license"])
        self.assertTrue(status["embeddable"])

    def test_nao_devolve_campos_que_o_PUT_recusa(self):
        self._rodar()
        self.assertNotIn("uploadStatus", self.enviado["status"])

    def test_200_NAO_e_prova_de_que_mudou(self):
        """Mesma classe de prova que "o botao estava habilitado"."""
        fora = self._rodar(depois="private")
        self.assertFalse(fora["mudou"])
        self.assertIn("private", fora["motivo"])

    def test_403_vira_FaltaEscopo_com_o_comando(self):
        with self.assertRaises(recuperar.FaltaEscopo) as caso:
            self._rodar(status_put=403)
        self.assertIn("--com-edicao", str(caso.exception))


if __name__ == "__main__":
    unittest.main()
