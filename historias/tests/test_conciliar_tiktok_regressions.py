"""Casar o ledger com o TikTok: por (gancho, parte), e nunca por titulo.

17/09/2026. A recuperacao de atrasados republicou uma serie inteira porque o
ledger e cego para o passado do TikTok — publicacao feita a mao e a grade
propria de 13-15/09 nunca ganharam linha. A cura importa essas linhas; este
arquivo trava o criterio de casamento, que eu errei DUAS vezes antes de
acertar.

**Primeira tentativa: por titulo. Achou zero, com confianca.**
O titulo do catalogo e o da PARTE e a legenda do TikTok e o gancho da
HISTORIA — textos diferentes, vindos de campos diferentes:

    catalogo:  "O plano que ela nunca contou (Parte 7/10)"
    TikTok:    "Eu encontrei meu quarto de infancia... Parte 7 de 10."

**Segunda tentativa: pelo gancho truncado. Pior que a primeira.**
Todas as partes da mesma historia colidem: a `h10 p02` e a `p04` casaram com
o MESMO post. Um falso "ja esta la" e pior que um falso "falta", porque
deixa um video de fora para sempre e ninguem procura.

**Terceira, que e esta: (gancho, parte).** A parte fica no MEIO da descricao
("...17 anos.\\n\\nParte 7 de 10 — as outras estao no canal"), nao no fim,
entao ela e extraida de onde estiver.

E UM POST PERTENCE A UM VIDEO SO: as variantes A e B tem descricao identica.
Importar as duas gravaria "publicado" sobre um video que nao foi, com o id do
irmao — o post fica com a principal.
"""
import importlib.util
import unittest
from pathlib import Path

FERRAMENTA = (Path(__file__).resolve().parents[2] / "ferramentas"
              / "conciliar_tiktok.py")


def _carregar():
    spec = importlib.util.spec_from_file_location("conciliar", FERRAMENTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


conciliar = _carregar()

GANCHO = ("Eu encontrei meu quarto de infância intacto num leilão — ele "
          "queimou há 17 anos.")


class _V:
    def __init__(self, vid, descricao, titulo="t", fonte=None, parte=None):
        self.id, self.descricao_completa, self.titulo = vid, descricao, titulo
        self.fonte_id, self.parte, self.partes = fonte, parte, None


def _post(tid, legenda, quando=1757000000):
    return {"tiktok_id": tid, "legenda": legenda, "post_time": quando}


class MarcaTests(unittest.TestCase):
    def test_a_parte_no_MEIO_do_texto_e_encontrada(self):
        d = f"{GANCHO}\n\nParte 7 de 10 — as outras estão no canal, na ordem."
        self.assertEqual((7, 10), conciliar.marca(d)[1])

    def test_partes_diferentes_dao_marcas_diferentes(self):
        a = conciliar.marca(f"{GANCHO}\n\nParte 2 de 10 — as outras...")
        b = conciliar.marca(f"{GANCHO}\n\nParte 4 de 10 — as outras...")
        self.assertNotEqual(a, b, "foi assim que h10 p02 e p04 colidiram")

    def test_as_duas_grafias_dao_a_mesma_marca(self):
        self.assertEqual(conciliar.marca("Gancho. Parte 3 de 6 — x"),
                         conciliar.marca("Gancho. (Parte 3/6)"))

    def test_acento_e_caixa_nao_separam(self):
        self.assertEqual(conciliar.marca("Ação É Isso. Parte 1 de 2"),
                         conciliar.marca("acao e isso. parte 1 de 2"))

    def test_sem_parte_a_marca_e_so_o_gancho(self):
        self.assertIsNone(conciliar.marca("Um build qualquer")[1])


class LinhasAImportarTests(unittest.TestCase):
    def test_casa_a_parte_certa(self):
        studio = [_post("111", f"{GANCHO} Parte 7 de 10."),
                  _post("222", f"{GANCHO} Parte 8 de 10.")]
        v = _V("h3:celular:p07", f"{GANCHO}\n\nParte 7 de 10 — as outras...")
        novas = conciliar.linhas_a_importar(studio, [v], set())
        self.assertEqual(1, len(novas))
        self.assertEqual("111", novas[0]["tiktok_id"])
        self.assertTrue(novas[0]["publicado"])

    def test_NAO_casa_por_titulo(self):
        """O teste que a primeira tentativa teria passado e nao devia."""
        studio = [_post("111", f"{GANCHO} Parte 7 de 10.")]
        v = _V("h3:celular:p07", f"{GANCHO}\n\nParte 7 de 10 — x",
               titulo="O plano que ela nunca contou (Parte 7/10)")
        novas = conciliar.linhas_a_importar(studio, [v], set())
        self.assertEqual("111", novas[0]["tiktok_id"],
                         "casa pela descricao, nao pelo titulo")

    def test_parte_ausente_do_studio_NAO_e_importada(self):
        studio = [_post("111", f"{GANCHO} Parte 7 de 10.")]
        v = _V("h3:celular:p04", f"{GANCHO}\n\nParte 4 de 10 — x")
        self.assertEqual([], conciliar.linhas_a_importar(studio, [v], set()))

    def test_um_post_para_UM_video_so(self):
        """A e B tem descricao identica; o post fica com a principal."""
        studio = [_post("111", "Erik, Guerreiro — build 87/100")]
        a = _V("g67:build:celular", "Erik, Guerreiro — build 87/100")
        b = _V("g67:build:celular:B", "Erik, Guerreiro — build 87/100")
        for ordem in ([a, b], [b, a]):
            with self.subTest(ordem=[v.id for v in ordem]):
                novas = conciliar.linhas_a_importar(studio, ordem, set())
                self.assertEqual(["g67:build:celular"],
                                 [n["video_id"] for n in novas])

    def test_quem_ja_esta_no_ledger_nao_entra_de_novo(self):
        studio = [_post("111", f"{GANCHO} Parte 7 de 10.")]
        v = _V("h3:celular:p07", f"{GANCHO}\n\nParte 7 de 10 — x")
        self.assertEqual([], conciliar.linhas_a_importar(
            studio, [v], {"h3:celular:p07"}))

    def test_nenhum_tiktok_id_e_usado_duas_vezes(self):
        studio = [_post("111", f"{GANCHO} Parte 1 de 3."),
                  _post("222", f"{GANCHO} Parte 2 de 3.")]
        vs = [_V(f"h3:celular:p0{n}", f"{GANCHO}\n\nParte {n} de 3 — x")
              for n in (1, 2)]
        ids = [n["tiktok_id"] for n in conciliar.linhas_a_importar(
            studio, vs, set())]
        self.assertEqual(len(ids), len(set(ids)))

    def test_a_linha_gravada_diz_de_onde_veio(self):
        studio = [_post("111", f"{GANCHO} Parte 7 de 10.")]
        v = _V("h3:celular:p07", f"{GANCHO}\n\nParte 7 de 10 — x")
        linha = conciliar.linhas_a_importar(studio, [v], set())[0]
        self.assertEqual("ja_estava_no_tiktok", linha["estado"])
        self.assertEqual("conciliar_tiktok.py", linha["por"])
        self.assertIn("111", linha["url"])

    def test_rodar_DUAS_vezes_nao_inventa_publicacao(self):
        """A idempotencia pagou sozinha: rodando de novo depois de gravar, a
        principal ja estava no ledger, a `:B` ficava sozinha na chave e
        HERDAVA o post do irmao — "publicado" sobre um video que nunca saiu.
        """
        studio = [_post("111", "Erik, Guerreiro — build 87/100")]
        a = _V("g67:build:celular", "Erik, Guerreiro — build 87/100")
        b = _V("g67:build:celular:B", "Erik, Guerreiro — build 87/100")
        # 1a passada: o post vai para a principal.
        primeira = conciliar.linhas_a_importar(studio, [a, b], set(), set())
        self.assertEqual(["g67:build:celular"],
                         [n["video_id"] for n in primeira])
        # 2a passada, com o estado que a 1a deixou.
        segunda = conciliar.linhas_a_importar(
            studio, [a, b], {"g67:build:celular"}, {"111"})
        self.assertEqual([], segunda, "a :B nao pode herdar o post do irmao")

    def test_variante_com_post_PROPRIO_entra(self):
        """Quando A e B foram MESMO publicadas separadas, sao duas linhas."""
        studio = [_post("111", "Erik, Guerreiro — build 87/100"),
                  _post("222", "Erik, Guerreiro — build 87/100")]
        b = _V("g67:build:celular:B", "Erik, Guerreiro — build 87/100")
        novas = conciliar.linhas_a_importar(
            studio, [b], {"g67:build:celular"}, {"111"})
        self.assertEqual(["222"], [n["tiktok_id"] for n in novas])

    def test_post_com_linha_REAL_por_perto_ja_tem_dono(self):
        """As seis linhas falsas de 17/09 vieram daqui.

        A primeira versao so marcava como usado o post que tinha `tiktok_id`,
        e as linhas do caminho normal NAO tem esse campo. Entao a principal
        saia dos candidatos (ja tinha linha) e a `:B` ficava sozinha na chave
        e herdava o post dela. Dois posts nao acontecem no mesmo segundo: se
        ha linha de TikTok a menos de 120 s, o post ja tem dono.
        """
        quando = 1757000000
        studio = [_post("111", "Erik — build 87/100", quando)]
        b = _V("g67:build:celular:B", "Erik — build 87/100")
        novas = conciliar.linhas_a_importar(
            studio, [b], {"g67:build:celular"},
            set(),                       # a linha real nao tem tiktok_id...
            [quando + 2])                # ...mas tem hora, e ela basta
        self.assertEqual([], novas, "a :B herdou o post da principal")

    def test_post_longe_no_tempo_continua_importavel(self):
        quando = 1757000000
        studio = [_post("111", "Erik — build 87/100", quando)]
        b = _V("g67:build:celular:B", "Erik — build 87/100")
        novas = conciliar.linhas_a_importar(
            studio, [b], {"g67:build:celular"}, set(), [quando + 9999])
        self.assertEqual(["111"], [n["tiktok_id"] for n in novas])

    def test_marca_de_DUAS_GERACOES_nao_se_importa(self):
        """Nos builds a legenda nao tem "Parte", e geracoes diferentes
        compartilham os 70 primeiros caracteres: 118 videos para 90 marcas.
        Foi assim que o generation_00027 recebeu um post do 00024."""
        studio = [_post("111", "Aventura sem fim no coliseu de pedra")]
        a = _V("g24:build:celular", "Aventura sem fim no coliseu de pedra")
        b = _V("g27:build:celular", "Aventura sem fim no coliseu de pedra")
        self.assertEqual([], conciliar.linhas_a_importar(studio, [a, b], set()),
                         "nao da para saber de quem e; nenhum recebe")

    def test_variantes_da_MESMA_geracao_nao_sao_ambiguidade(self):
        """O par A/B e resolvido de proposito: fica a principal."""
        studio = [_post("111", "Erik — build 87/100")]
        a = _V("g67:build:celular", "Erik — build 87/100")
        b = _V("g67:build:celular:B", "Erik — build 87/100")
        novas = conciliar.linhas_a_importar(studio, [a, b], set())
        self.assertEqual(["g67:build:celular"],
                         [n["video_id"] for n in novas])

    def test_studio_vazio_nao_importa_nada(self):
        v = _V("h3:celular:p07", f"{GANCHO}\n\nParte 7 de 10 — x")
        self.assertEqual([], conciliar.linhas_a_importar([], [v], set()))


if __name__ == "__main__":
    unittest.main()
