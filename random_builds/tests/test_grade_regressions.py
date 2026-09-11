"""A grade escolhe FORMATO, nao so o mais antigo (Onda 15E).

`ferramentas/postar.py::proximo_build` filtrava por perfil celular, tirava
os ja publicados e devolvia o mais antigo. FIFO cego: `catalogo.listar()`
devolve build, estreia, duelo e torneio no mesmo indice. Com 8 disparos por
dia e um backlog desequilibrado, uma semana inteira podia sair de um
formato so — e a comparacao que a Onda 15 existe para fazer simplesmente
nao aconteceria.

A garantia que importava antes ("nada sai duas vezes, o mais antigo sai
primeiro") continua valendo DENTRO de cada formato. A ordem ENTRE formatos
nunca foi uma garantia: era efeito colateral de nao haver formatos.
"""
from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

# Carregado por caminho, e nao por import: `ferramentas` nao e pacote
# instalado no workspace, e mexer em `sys.path` estoura a catraca de
# arquitetura (teto de 2 no repo inteiro). Mesmo padrao de
# historias/tests/test_um_por_dia_regressions.py.
POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_grade", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_GRADE = _postar()
COTA_PADRAO = _GRADE.COTA_PADRAO
cota_da_grade = _GRADE.cota_da_grade
escolher_por_cota = _GRADE.escolher_por_cota


def _pendentes(quantos_por_origem: dict) -> list:
    """Do mais ANTIGO para o mais novo, como `proximo_build` entrega."""
    saida = []
    relogio = 0.0
    for indice in range(max(quantos_por_origem.values(), default=0)):
        for origem, quantos in quantos_por_origem.items():
            if indice < quantos:
                relogio += 1.0
                saida.append(SimpleNamespace(
                    id=f"{origem}_{indice}", origem=origem, quando=relogio))
    return sorted(saida, key=lambda v: v.quando)


def _rodar(pendentes: list, voltas: int, cota: dict) -> list:
    servidos: dict[str, int] = {}
    sequencia = []
    restantes = list(pendentes)
    for _ in range(voltas):
        escolhido = escolher_por_cota(restantes, servidos, cota)
        if escolhido is None:
            break
        sequencia.append(escolhido.origem)
        servidos[escolhido.origem] = servidos.get(escolhido.origem, 0) + 1
        restantes.remove(escolhido)
    return sequencia


class MisturaTests(unittest.TestCase):
    def test_a_grade_alterna_entre_formatos(self):
        """Em 16 disparos, cada formato sai o dobro da cota dele."""
        pendentes = _pendentes({"duelo": 20, "build": 20,
                                "estreia": 20, "torneio": 20})
        sequencia = _rodar(pendentes, 16, COTA_PADRAO)
        for origem, peso in COTA_PADRAO.items():
            with self.subTest(origem=origem):
                self.assertLessEqual(abs(sequencia.count(origem) - peso * 2), 1)

    def test_um_formato_sem_estoque_nao_trava_a_grade(self):
        """Sem duelo pendente, os slots dele vao para quem tem — nunca
        viram 'nao ha video pendente'."""
        sequencia = _rodar(_pendentes({"build": 10, "estreia": 10}), 8,
                           COTA_PADRAO)
        self.assertEqual(8, len(sequencia))
        self.assertNotIn("duelo", sequencia)

    def test_cota_zero_e_ultimo_recurso_e_nao_proibicao(self):
        """Torneio tem cota 0: sai quando nao ha mais nada, nao nunca."""
        so_torneio = _rodar(_pendentes({"torneio": 3}), 3, COTA_PADRAO)
        self.assertEqual(["torneio"] * 3, so_torneio)
        com_outros = _rodar(_pendentes({"torneio": 5, "duelo": 5}), 4,
                            COTA_PADRAO)
        self.assertNotIn("torneio", com_outros)

    def test_sem_cota_configurada_a_grade_volta_a_ser_fifo(self):
        """Compatibilidade com o `publicacao.json` de antes da 15E."""
        pendentes = _pendentes({"build": 3, "duelo": 3})
        self.assertEqual(pendentes[0], escolher_por_cota(pendentes, {}, {}))

    def test_dentro_do_formato_o_mais_antigo_sai_primeiro(self):
        """A garantia que sempre valeu, agora escopada por formato."""
        pendentes = _pendentes({"duelo": 3})
        escolhido = escolher_por_cota(pendentes, {}, COTA_PADRAO)
        self.assertEqual(min(v.quando for v in pendentes), escolhido.quando)

    def test_sem_pendente_devolve_nada_em_vez_de_explodir(self):
        self.assertIsNone(escolher_por_cota([], {}, COTA_PADRAO))

    def test_a_escolha_nao_depende_de_disco_nem_de_rede(self):
        """A regra e pura: da para simular a grade inteira num teste."""
        self.assertIsNotNone(escolher_por_cota(
            _pendentes({"duelo": 1}), {"duelo": 99}, COTA_PADRAO))

    def test_a_cota_real_do_config_cobre_os_formatos_publicaveis(self):
        cota = cota_da_grade()
        for origem in ("duelo", "build", "estreia"):
            with self.subTest(origem=origem):
                self.assertIn(origem, cota)
        self.assertGreater(cota.get("duelo", 0), 0,
                           "o formato em teste precisa de slots para ser testado")


class VereditoTests(unittest.TestCase):
    """O numero que decide a Onda 15 — e o que ele se recusa a inventar."""

    AGORA = datetime(2026, 9, 11, 12, 0, 0)

    def _video(self, origem, views, dias, retencao=None, likes=0, duracao=60):
        dado = {"origem": origem, "views": views, "likes": likes,
                "duracao": duracao,
                "publicado_em": (self.AGORA - timedelta(days=dias)).isoformat()}
        if retencao is not None:
            dado["media_percentual"] = retencao
        return dado

    def test_a_comparacao_separa_por_origem_e_ordena_por_retencao(self):
        from builds.publicar import metricas

        dados = [self._video("build", 100, 10, retencao=28.0),
                 self._video("duelo", 10, 2, retencao=61.0)]
        formatos = metricas.comparar_formatos(dados, self.AGORA)
        self.assertEqual("duelo", formatos[0]["origem"],
                         "retencao decide, nao views — views e muito ruidosa")

    def test_nao_inventa_retencao_quando_a_analytics_calou(self):
        """Video sem linha da API nao entra na media como 0%.

        E a mesma doutrina de `retencao()`, que se recusa a gravar zero
        quando a Analytics nao devolve nada. Aqui o erro seria pior: o
        formato NOVO, que tem menos views, teria mais videos suprimidos e
        perderia a comparacao por um artefato da coleta.
        """
        from builds.publicar import metricas

        dados = [self._video("duelo", 10, 2, retencao=60.0),
                 self._video("duelo", 1, 1)]          # sem media_percentual
        formato = metricas.comparar_formatos(dados, self.AGORA)[0]
        self.assertEqual(2, formato["videos"])
        self.assertEqual(1, formato["com_retencao"])
        self.assertAlmostEqual(60.0, formato["retencao_media"])

    def test_formato_sem_nenhuma_retencao_nao_derruba_a_tabela(self):
        from builds.publicar import metricas

        dados = [self._video("duelo", 10, 2), self._video("build", 5, 3)]
        for formato in metricas.comparar_formatos(dados, self.AGORA):
            with self.subTest(origem=formato["origem"]):
                self.assertIsNone(formato["retencao_media"])
                self.assertEqual(0, formato["com_retencao"])


if __name__ == "__main__":
    unittest.main()
