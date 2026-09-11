"""Contratos da Onda 15B: o DUELO, a luta inteira sem cena parada.

Por que o formato existe, em numeros (11/09/2026, primeira coleta de
retencao real do canal): o build tem 28,1% de retencao media e a estreia
3,4% com MEDIANA ZERO; a curva do unico video com amostra cai de 86% aos
8,5 s para 18,6% aos 50,9 s, que e quando a luta comeca. O publico entrega
~20 s a este canal.

O que este arquivo trava:

1. O duelo e UM evento de gameplay. Nenhuma cena parada, nunca — e a
   afirmacao estrutural do formato, e o que o distingue da estreia.
2. Identidade e veredito sao SOBREPOSICAO no clipe, nao eventos com tempo
   proprio: apresentar e concluir nao podem custar segundo de tela.
3. O duelo respeita o orcamento de gravacao proprio e nao estoura a janela
   do formato.
4. O duelo NAO mudou build, estreia nem torneio — a decisao de fazer o
   formato novo em paralelo, cobrada no codigo e nao so na intencao.
5. Determinismo por seed, como todo o resto do pipeline.

Rode de dentro de random_builds/:
    python -m unittest discover -s tests -p "test_*.py"
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from builds.content.caption_generator import CaptionGenerator            # noqa: E402
from builds.generation.random_engine import RandomEngine                 # noqa: E402
from builds.generation.session_generator import load_config              # noqa: E402
from builds.tournament import highlights                                 # noqa: E402
from builds.tournament.duelo import DueloTimelineBuilder                 # noqa: E402
from builds.tournament.runner import (GAMEPLAY_PADRAO, camera_do_perfil,  # noqa: E402
                                      config_gameplay)

EDICAO = load_config("editing.json")
CAPTIONS = CaptionGenerator(load_config("captions.json"),
                            load_config("frases.json"))

# A janela do formato. O teto e o que importa: o piso existe porque uma
# luta muito curta ainda precisa ser um video, e nao um piscar.
JANELA_MIN, JANELA_MAX = 8.0, 35.0


def _fight(seed: int = 7, duracao_clipe: float = 24.0) -> dict:
    ficha1 = {"nome": "Kael", "classe": "Guerreiro (Combate)", "forca": 7.0,
              "mana": 4.0, "nome_arma": "Vurdak",
              "cor_r": 50, "cor_g": 200, "cor_b": 255}
    ficha2 = {"nome": "Lyra", "classe": "Maga (Arcano)", "forca": 4.0,
              "mana": 8.0, "nome_arma": "Iskimantr",
              "cor_r": 255, "cor_g": 90, "cor_b": 60}
    luta = {
        "match_id": 0, "rodada": 0, "rodada_nome": "LUTA", "origem": "duelo",
        "p1": "Kael", "p2": "Lyra", "p1_ficha": ficha1, "p2_ficha": ficha2,
        "vencedor": "Kael", "perdedor": "Lyra", "vencedor_gerado": True,
        "duracao": 21.0, "motivo": "knockout", "ko_type": "KO",
        "hp_vencedor": 22, "seed": seed, "cenario": "Duto",
        "clipes": {"celular": {"path": "x_celular.mp4", "duracao": duracao_clipe},
                   "normal": {"path": "x_normal.mp4", "duracao": duracao_clipe}},
        "serie_hp": [(t * 0.25, 100 - t, 100 - t * 1.5)
                     for t in range(int(duracao_clipe * 4))],
        "eventos_narrativos": [{"t": 2.0, "tipo": "primeiro_sangue", "slot": "p1"},
                               {"t": 9.0, "tipo": "parry", "slot": "p2"},
                               {"t": 15.0, "tipo": "combo", "slot": "p2", "n": 4},
                               {"t": 20.5, "tipo": "ko", "slot": "p1"}],
        "score": 68, "marcas": [], "zebra": False, "favorito": "Kael",
        "surpresa": 29, "tier": "GOOD", "tier_label": "BOM",
        "sentiment": "positive", "intensity": 0.4, "tier_color": "#7ed957",
    }
    return {"seed": seed, "kind": "duelo", "origem": "duelo", "luta": luta,
            "duelo_id": f"duelo_{seed}"}


def _plano(fight: dict) -> dict:
    builder = DueloTimelineBuilder(EDICAO, CAPTIONS)
    return builder.build(RandomEngine(fight["seed"]).fork("duelo:edicao"), fight)


class FormatoTests(unittest.TestCase):
    def test_o_duelo_e_um_segmento_so(self):
        """Nenhuma cena parada. E a definicao do formato.

        A estreia tem hook, card, round_title, round_result, reacao e outro;
        o build tem roleta e ficha. O duelo tem a luta. Se um tipo novo
        aparecer aqui, o formato deixou de ser o que ele existe para ser.
        """
        for seed in (7, 11, 23):
            with self.subTest(seed=seed):
                plano = _plano(_fight(seed=seed))
                self.assertEqual(["gameplay"], [e["type"] for e in plano["events"]])
                self.assertEqual("duelo", plano["kind"])

    def test_a_luta_comeca_no_primeiro_frame(self):
        """Zero segundo de espera. A curva de 11/09/2026 mostrou 81% da
        audiencia indo embora ANTES da luta comecar no formato antigo."""
        plano = _plano(_fight())
        self.assertEqual(0.0, plano["events"][0]["start"])

    def test_o_duelo_nao_estoura_a_janela_do_formato(self):
        for clipe in (9.0, 14.0, 22.0, 28.0):
            with self.subTest(clipe=clipe):
                plano = _plano(_fight(duracao_clipe=clipe))
                self.assertLessEqual(plano["total_duration"], JANELA_MAX)
                self.assertGreaterEqual(plano["total_duration"], JANELA_MIN)
                self.assertAlmostEqual(clipe, plano["total_duration"], places=2)

    def test_sem_clipe_o_duelo_falha_em_vez_de_virar_cartao(self):
        """O build sem gravacao cai para roleta; o duelo NAO tem para onde
        cair — o formato E a luta. Falhar alto e melhor que publicar um
        video de texto com nome de duelo."""
        fight = _fight()
        fight["luta"]["clipes"] = {}
        with self.assertRaises(ValueError):
            _plano(fight)

    def test_deterministico_por_seed(self):
        self.assertEqual(_plano(_fight(seed=31)), _plano(_fight(seed=31)))


class SobreposicaoTests(unittest.TestCase):
    """Apresentar e concluir nao podem custar segundo de tela."""

    def test_identidade_e_veredito_nao_sao_eventos(self):
        evento = _plano(_fight())["events"][0]
        for chave in ("identidade", "veredito"):
            with self.subTest(chave=chave):
                self.assertIn(chave, evento)
                self.assertNotIn("start", evento[chave])
                self.assertNotIn("duration", evento[chave])

    def test_a_identidade_esta_na_abertura_e_o_veredito_no_fim(self):
        plano = _plano(_fight(duracao_clipe=24.0))
        evento = plano["events"][0]
        total = plano["total_duration"]
        self.assertLessEqual(evento["identidade"]["ate"], 2.0)
        self.assertGreaterEqual(evento["veredito"]["de"], total - 2.0)
        self.assertLess(evento["veredito"]["de"], total)

    def test_clipe_curto_encolhe_as_sobreposicoes_em_vez_de_cobrir_a_luta(self):
        """Numa luta de 5 s, 1,5 s de identidade seriam 30% da tela."""
        evento = _plano(_fight(duracao_clipe=5.0))["events"][0]
        self.assertLessEqual(evento["identidade"]["ate"], 5.0 * 0.25 + 1e-6)
        self.assertGreaterEqual(evento["veredito"]["de"], 5.0 * 0.8 - 1e-6)

    def test_a_identidade_diz_quem_e_quem(self):
        ident = _plano(_fight())["events"][0]["identidade"]
        self.assertEqual("Kael", ident["p1"]["nome"])
        self.assertEqual("Iskimantr", ident["p2"]["arma"])
        self.assertTrue(ident["p1"]["classe"])

    def test_o_veredito_nomeia_o_vencedor(self):
        ver = _plano(_fight())["events"][0]["veredito"]
        self.assertEqual("Kael", ver["vencedor"])
        self.assertEqual("KO", ver["ko_type"])

    def test_todo_tipo_emitido_tem_ramo_no_renderer(self):
        """O `_frames_for` devolve um CARTAO DE TEXTO para tipo desconhecido.

        E o pior modo de falha possivel: o video sai, com duracao certa, e
        so quem assiste descobre que a luta virou uma placa. Este teste
        casa os tipos que o duelo emite com os que o renderer trata.
        """
        from builds.video.renderer import VideoRenderer

        tipos = {e["type"] for e in _plano(_fight())["events"]}
        fonte = Path(VideoRenderer.__module__.replace(".", "/") + ".py")
        codigo = (ROOT / fonte).read_text(encoding="utf-8")
        for tipo in tipos:
            with self.subTest(tipo=tipo):
                self.assertIn(f'"{tipo}"', codigo)


class EscopoPorOrigemTests(unittest.TestCase):
    """A decisao 1 da Onda 15: o formato novo e PARALELO, nao substitui."""

    def test_o_duelo_nao_mudou_a_gravacao_dos_outros_formatos(self):
        sem_origem = config_gameplay(EDICAO)
        for origem in ("build", "estreia", "torneio", "luta"):
            with self.subTest(origem=origem):
                self.assertEqual(sem_origem, config_gameplay(EDICAO, origem))

    def test_a_estreia_continua_com_a_camera_presa_no_celular(self):
        cfg = config_gameplay(EDICAO, "estreia")
        self.assertEqual("ARENA", camera_do_perfil(cfg, "estreia", "celular"))
        self.assertEqual("DIRETOR", camera_do_perfil(cfg, "estreia", "normal"))

    def test_o_duelo_usa_a_camera_que_segue_os_lutadores(self):
        cfg = config_gameplay(EDICAO, "duelo")
        for perfil in ("celular", "normal"):
            with self.subTest(perfil=perfil):
                self.assertEqual("DIRETOR", camera_do_perfil(cfg, "duelo", perfil))

    def test_o_orcamento_do_duelo_e_mais_apertado_que_o_padrao(self):
        padrao = config_gameplay(EDICAO)
        duelo = config_gameplay(EDICAO, "duelo")
        self.assertLess(duelo["max_total"], padrao["max_total"])
        self.assertLess(duelo["seca"], padrao["seca"],
                        "e a `seca` que transforma 45 s de luta em 25 s de pancada")

    def test_o_teto_do_duelo_cabe_na_janela_do_formato(self):
        self.assertLessEqual(config_gameplay(EDICAO, "duelo")["max_total"], JANELA_MAX)

    def test_origem_desconhecida_cai_no_padrao(self):
        self.assertEqual(config_gameplay(EDICAO),
                         config_gameplay(EDICAO, "formato_que_nao_existe"))

    def test_sem_config_os_padroes_do_modulo_bastam(self):
        """`config_gameplay(None)` e usado por teste e por quem so gera dados."""
        self.assertEqual(GAMEPLAY_PADRAO["max_total"],
                         config_gameplay(None)["max_total"])
        self.assertEqual(28.0, config_gameplay(None, "duelo")["max_total"])


class PublicacaoDoDueloTests(unittest.TestCase):
    """Roda contra o `config/publicacao.json` REAL, como os outros."""

    @classmethod
    def setUpClass(cls):
        from builds.publicar import catalogo
        cls.config = catalogo.carregar_config()
        cls.catalogo = catalogo

    def test_o_duelo_tem_titulo_descricao_e_hashtags(self):
        for bloco in ("titulos", "descricoes", "hashtags"):
            with self.subTest(bloco=bloco):
                self.assertIn(self.catalogo.DUELO, self.config.get(bloco, {}))

    def test_o_titulo_do_duelo_nao_entrega_o_final_nem_anuncia_mediocridade(self):
        """O da estreia dizia "venceu por 2 x 0"; o do build, "BUILD MEDIANA".
        Um spoila, o outro promete que o video e mediano."""
        modelo = self.config["titulos"][self.catalogo.DUELO]
        for proibido in ("{desfecho}", "{placar}", "{nota}", "{veredito}",
                         "{vencedor}"):
            with self.subTest(campo=proibido):
                self.assertNotIn(proibido, modelo)

    def test_o_titulo_nomeia_os_dois_lutadores(self):
        modelo = self.config["titulos"][self.catalogo.DUELO]
        self.assertIn("{p1}", modelo)
        self.assertIn("{p2}", modelo)

    def test_nenhum_placeholder_sobra_no_texto_montado(self):
        campos = {"p1": "Kael", "p2": "Lyra", "arena": "Duto", "duracao": 21}
        for bloco in ("titulos", "descricoes"):
            texto = self.catalogo._formatar(
                self.config[bloco][self.catalogo.DUELO], campos)
            with self.subTest(bloco=bloco):
                self.assertNotIn("{", texto)
                self.assertNotIn("}", texto)


class CorteDoDueloTests(unittest.TestCase):
    def _gravacao(self, duracao: float, ko: float | None,
                  hits: tuple[float, ...]) -> dict:
        return {"duracao_video": duracao, "ko_em_video": ko,
                "eventos_dano": [(t, "p1", 8.0, "ataque") for t in hits],
                "serie_hp": [], "eventos_narrativos": []}

    def test_o_minimo_para_cortar_virou_knob(self):
        """Com o valor fixo em 12 s, uma luta de 11 s passava inteira e uma
        de 13 s era cortada. Num video de 25 s esse degrau aparece."""
        gravacao = self._gravacao(11.0, 9.0, (1.0, 8.5))
        inteiro = highlights.planejar_corte_tedio(gravacao, minimo_para_cortar=12.0)
        self.assertEqual([(0.0, 11.0)], inteiro)
        cortado = highlights.planejar_corte_tedio(
            gravacao, minimo_para_cortar=8.0, seca_min=2.0, contexto=0.5,
            protecao_ko=6.0, abertura=0.4)
        self.assertLess(highlights.duracao_total(cortado), 11.0)

    def test_o_orcamento_do_duelo_encurta_uma_luta_longa(self):
        gravacao = self._gravacao(70.0, 66.0, tuple(float(t) for t in range(2, 66, 7)))
        duelo = config_gameplay(EDICAO, "duelo")
        trechos = highlights.planejar_corte_tedio(
            gravacao, max_total=duelo["max_total"], seca_min=duelo["seca"],
            contexto=duelo["contexto"], protecao_ko=duelo["protecao_ko"],
            abertura=duelo["abertura"],
            minimo_para_cortar=duelo["minimo_para_cortar"])
        self.assertLessEqual(highlights.duracao_total(trechos),
                             duelo["max_total"] + 1e-6)


if __name__ == "__main__":
    unittest.main()
