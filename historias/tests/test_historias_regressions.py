# -*- coding: utf-8 -*-
"""Contratos do canal de historias.

O que este arquivo trava, e por que cada um existe:

1. PARSER TOLERANTE. O LLM enfeita a resposta (markdown, acento, JSON,
   "5 segundos"). Se o parser quebrar com isso, voce edita texto a mao — que
   e o trabalho que este projeto existe para tirar.
2. PARSER RIGOROSO NO QUE IMPORTA. Cena sem narracao ou sem prompt de imagem
   e erro, nao aviso: sem isso nao existe video.
3. A CENA ESPERA A FALA. A duracao final e a fala medida mais margem, nunca
   o tempo sugerido pelo roteiro. Foi o bug mais caro do outro projeto.
4. PROMPT-MESTRE. Modelo proprio troca a ESTRUTURA, nunca as regras de
   retencao nem o contrato de saida - sao eles que fazem o roteiro virar video.
5. IMAGEM. O estilo entra em toda cena (as 12 imagens tem que parecer do
   mesmo filme) e o prompt respeita o teto do site.
6. O titulo aparece SOBRE a primeira cena, curto - nunca como cartao antes
   dela, que e o que faz rolar o feed.

Rode de dentro de historias/:
    python -m unittest discover -s tests -p "test_*.py"
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from contos.imagens import fila                                   # noqa: E402
from contos.roteiro import modelo                                  # noqa: E402
from contos.roteiro import roteiro as R                            # noqa: E402
from contos.video import timeline                                  # noqa: E402

CONFIG = modelo.carregar_config()
RENDER = timeline.carregar_config("render.json")


def _roteiro(cenas: int = 5, tempo: float = 4.0) -> dict:
    return {"titulo": "Um titulo qualquer", "cta": "E voce?",
            "cenas": [{"n": i, "imagem": f"a man in a room, scene {i}, night light",
                       "tempo": tempo, "narracao": f"Fala da cena {i}."}
                      for i in range(1, cenas + 1)]}


# --------------------------------------------------------------- 1. parser
class ParserTests(unittest.TestCase):
    SUJO = """Claro! Aqui esta:

**TITULO:** Meu vizinho pagou meu aluguel

## CENA 1
**IMAGEM:** a man in his forties standing frozen in a small kitchen at night
**TEMPO:** 4
**NARRACAO:** Descobri ontem que ele pagava.
Ha tres anos.

CENA 2
- IMAGEM: same man sitting on the hallway floor with a phone
- TEMPO: 5 segundos
- NARRAÇÃO: A imobiliaria ligou pra confirmar.

CTA: Voce teria aceitado?
"""

    def test_le_markdown_acento_e_continuacao(self):
        r = R.parse(self.SUJO)
        self.assertEqual("Meu vizinho pagou meu aluguel", r["titulo"])
        self.assertEqual("Voce teria aceitado?", r["cta"])
        self.assertEqual(2, len(r["cenas"]))
        # linha quebrada vira uma narracao so
        self.assertEqual("Descobri ontem que ele pagava. Ha tres anos.",
                         r["cenas"][0]["narracao"])
        # "5 segundos" vira 5.0
        self.assertEqual(5.0, r["cenas"][1]["tempo"])
        # o enfeite de markdown nao entra no conteudo
        for cena in r["cenas"]:
            self.assertNotIn("*", cena["narracao"])
            self.assertTrue(cena["imagem"].startswith(("a man", "same man")))

    def test_le_json_com_chaves_em_ingles(self):
        bruto = json.dumps({"title": "T", "scenes": [
            {"image": "a cat on a roof at dusk", "time": 3, "narration": "oi"},
            {"image": "the same cat running", "time": 4, "narration": "tchau"}]})
        r = R.parse(bruto)
        self.assertEqual("T", r["titulo"])
        self.assertEqual(["oi", "tchau"], [c["narracao"] for c in r["cenas"]])
        self.assertEqual([1, 2], [c["n"] for c in r["cenas"]])

    def test_numera_em_sequencia_mesmo_com_numero_errado(self):
        r = R.parse("CENA 3\nIMAGEM: uma sala escura com uma janela aberta\n"
                    "TEMPO: 4\nNARRACAO: a\n\n"
                    "CENA 7\nIMAGEM: a mesma sala de manha com sol\n"
                    "TEMPO: 4\nNARRACAO: b\n")
        self.assertEqual([1, 2], [c["n"] for c in r["cenas"]])

    def test_tempo_ausente_tem_padrao(self):
        r = R.parse("CENA 1\nIMAGEM: a long empty road at sunrise, wide shot\n"
                    "NARRACAO: sem tempo\n")
        self.assertEqual(4.0, r["cenas"][0]["tempo"])


class ValidacaoTests(unittest.TestCase):
    def test_poucas_cenas_e_erro(self):
        problemas, erros = R.validar(_roteiro(cenas=2), CONFIG)
        self.assertTrue(any("minimo" in e for e in erros))
        del problemas

    def test_cena_sem_narracao_ou_sem_imagem_e_erro(self):
        r = _roteiro(cenas=5)
        r["cenas"][0]["narracao"] = ""
        r["cenas"][1]["imagem"] = ""
        _, erros = R.validar(r, CONFIG)
        self.assertTrue(any("cena 1" in e and "NARRACAO" in e for e in erros))
        self.assertTrue(any("cena 2" in e and "IMAGEM" in e for e in erros))

    def test_roteiro_bom_passa_limpo(self):
        problemas, erros = R.validar(_roteiro(), CONFIG)
        self.assertEqual([], erros)
        self.assertEqual([], problemas)

    def test_prompt_de_imagem_curto_e_so_aviso(self):
        r = _roteiro()
        r["cenas"][0]["imagem"] = "a man"
        problemas, erros = R.validar(r, CONFIG)
        self.assertEqual([], erros)
        self.assertTrue(any("curto" in p for p in problemas))


# ------------------------------------------------------- 2. prompt-mestre
class PromptMestreTests(unittest.TestCase):
    def test_carrega_regras_estrutura_e_contrato(self):
        dados = modelo.prompt_mestre("reddit", config=CONFIG)
        texto = dados["prompt"]
        for regra in CONFIG["regras"]["narracao"]:
            self.assertIn(regra, texto)
        for regra in CONFIG["regras"]["imagem"]:
            self.assertIn(regra, texto)
        for bloco in CONFIG["modelos"]["reddit"]["estrutura"]:
            self.assertIn(bloco, texto)
        # o contrato precisa estar la, senao o parser nao le a resposta
        for rotulo in ("TITULO:", "CENA 1", "IMAGEM:", "TEMPO:", "NARRACAO:"):
            self.assertIn(rotulo, texto)

    def test_modelo_proprio_troca_a_estrutura_e_mantem_as_regras(self):
        with tempfile.TemporaryDirectory() as tmp:
            meu = Path(tmp) / "meu.txt"
            meu.write_text("ABERTURA: uma frase\nMEIO: outra\nFIM: mais uma\n",
                           encoding="utf-8")
            texto = modelo.prompt_mestre(arquivo=meu, config=CONFIG)["prompt"]
        self.assertIn("ABERTURA: uma frase", texto)
        self.assertNotIn(CONFIG["modelos"]["reddit"]["estrutura"][0], texto)
        self.assertIn(CONFIG["regras"]["narracao"][0], texto)
        self.assertIn("NARRACAO:", texto)

    def test_sem_tema_o_llm_inventa(self):
        self.assertIn("voce escolhe",
                      modelo.prompt_mestre("reddit", config=CONFIG)["prompt"])
        com = modelo.prompt_mestre("reddit", tema="um casamento", config=CONFIG)
        self.assertIn("um casamento", com["prompt"])

    def test_modelo_desconhecido_diz_quais_existem(self):
        with self.assertRaises(KeyError) as ctx:
            modelo.prompt_mestre("nao_existe", config=CONFIG)
        self.assertIn("reddit", str(ctx.exception))


# ------------------------------------------- 3. a cena espera a fala
class TimelineTests(unittest.TestCase):
    def test_a_cena_cresce_ate_a_fala_caber(self):
        roteiro = _roteiro(cenas=4, tempo=3.0)
        medidas = {0: 6.4, 1: 1.0, 2: 3.2, 3: 2.0}
        margem = CONFIG["narracao"]["margem"]
        plano = timeline.montar(roteiro, medidas, config_roteiro=CONFIG,
                                config_render=RENDER)
        eventos = plano["events"]
        # fala longa manda: 6,4 + margem
        self.assertAlmostEqual(6.4 + margem, eventos[0]["duration"], places=2)
        # fala curta nao encolhe a cena abaixo do tempo sugerido
        self.assertAlmostEqual(3.0, eventos[1]["duration"], places=2)
        for evento, indice in zip(eventos, range(4)):
            falado = medidas[indice]
            self.assertGreaterEqual(evento["duration"] + 1e-6, falado + margem
                                    if falado + margem > 3.0 else falado)

    def test_nenhuma_cena_termina_antes_da_fala(self):
        roteiro = _roteiro(cenas=6, tempo=2.0)
        medidas = {i: 2.0 + i for i in range(6)}
        plano = timeline.montar(roteiro, medidas, config_roteiro=CONFIG,
                                config_render=RENDER)
        for indice, evento in enumerate(plano["events"]):
            self.assertGreaterEqual(evento["duration"], medidas[indice],
                                    f"cena {evento['n']} corta a fala")

    def test_o_teto_vale_para_cena_SEM_fala(self):
        limites = CONFIG["narracao"]
        plano = timeline.montar(_roteiro(cenas=2, tempo=90.0), {},
                                config_roteiro=CONFIG, config_render=RENDER)
        self.assertAlmostEqual(limites["maximo_cena"],
                               plano["events"][0]["duration"], places=2)

    def test_o_teto_NAO_corta_a_fala_medida(self):
        """Medido em 31/08/2026: o teto de 14 s cortava 9 das 14 falas.

        `voz.py` trunca o audio no espaco que a cena der — entao um teto
        abaixo da fala nao "aperta o video", ele decepa a frase no meio da
        palavra. Cena longa e ruim; frase cortada e pior.
        """
        limites = CONFIG["narracao"]
        falado = limites["maximo_cena"] + 3.0
        plano = timeline.montar(_roteiro(cenas=2, tempo=0.5),
                                {0: falado, 1: 0.1},
                                config_roteiro=CONFIG, config_render=RENDER)
        self.assertGreaterEqual(plano["events"][0]["duration"], falado,
                                "a cena tem que esperar a fala terminar")

    def test_o_piso_vale(self):
        limites = CONFIG["narracao"]
        plano = timeline.montar(_roteiro(cenas=2, tempo=0.5), {0: 0.1, 1: 0.1},
                                config_roteiro=CONFIG, config_render=RENDER)
        self.assertGreaterEqual(plano["events"][1]["duration"],
                                limites["minimo_cena"])

    def test_sem_medidas_usa_o_tempo_sugerido(self):
        plano = timeline.montar(_roteiro(cenas=3, tempo=4.0), {},
                                config_roteiro=CONFIG, config_render=RENDER)
        self.assertAlmostEqual(4.0, plano["events"][0]["duration"], places=2)

    def test_titulo_so_na_primeira_cena_e_curto(self):
        plano = timeline.montar(_roteiro(), {}, config_roteiro=CONFIG,
                                config_render=RENDER)
        self.assertIn("titulo", plano["events"][0])
        self.assertLessEqual(plano["events"][0]["titulo_duracao"], 3.0)
        for evento in plano["events"][1:]:
            self.assertNotIn("titulo", evento)

    def test_camera_alterna_entre_cenas(self):
        plano = timeline.montar(_roteiro(cenas=4), {}, config_roteiro=CONFIG,
                                config_render=RENDER)
        zooms = [e["camera"]["zoom"] for e in plano["events"]]
        self.assertNotEqual(zooms[0], zooms[1], "duas cenas com o mesmo movimento")
        self.assertEqual(zooms[0], zooms[2])

    def test_starts_em_cadeia_e_total_fecha(self):
        plano = timeline.montar(_roteiro(cenas=5), {i: 2.0 for i in range(5)},
                                config_roteiro=CONFIG, config_render=RENDER)
        cursor = 0.0
        for evento in plano["events"]:
            self.assertAlmostEqual(cursor, evento["start"], places=2)
            cursor += evento["duration"]
        self.assertAlmostEqual(cursor, plano["total_duration"], places=2)

    def test_linhas_do_plano_seguem_o_plano(self):
        plano = timeline.montar(_roteiro(cenas=3), {0: 5.0}, config_roteiro=CONFIG,
                                config_render=RENDER)
        linhas = timeline.linhas_do_plano(plano)
        self.assertEqual(3, len(linhas))
        for linha, evento in zip(linhas, plano["events"]):
            self.assertEqual(evento["start"], linha["start"])
            self.assertEqual(evento["narracao"], linha["text"])


# ------------------------------------------------------------- 4. imagens
class ImagemTests(unittest.TestCase):
    def test_estilo_entra_em_toda_cena(self):
        config = fila.carregar_config()
        cena = {"imagem": "a man opening a door at night"}
        prompt = fila.prompt_da_cena(cena, config)
        self.assertIn("a man opening a door at night", prompt)
        self.assertIn(config["estilo"].split(",")[0], prompt)
        self.assertIn("no text", prompt)

    def test_respeita_o_teto_de_caracteres(self):
        config = dict(fila.carregar_config(), prompt_max_chars=120)
        prompt = fila.prompt_da_cena({"imagem": "x " * 300}, config)
        self.assertLessEqual(len(prompt), 120)

    def test_protagonista_reforca_so_quando_falta(self):
        config = fila.carregar_config()
        com = fila.prompt_da_cena({"imagem": "a door opening"}, config,
                                  "a man with a red scarf")
        self.assertIn("a man with a red scarf", com)
        ja_tem = fila.prompt_da_cena(
            {"imagem": "a man with a red scarf opening a door"}, config,
            "a man with a red scarf")
        self.assertEqual(1, ja_tem.lower().count("a man with a red scarf"))

    def test_estado_vem_do_disco(self):
        with tempfile.TemporaryDirectory() as tmp:
            antes = fila.OUTPUTS
            fila.OUTPUTS = Path(tmp)
            try:
                roteiro = _roteiro(cenas=3)
                resumo = fila.resumo("historia_00099", roteiro)
                self.assertEqual({"total": 3, "prontas": 0, "faltam": 3,
                                  "completa": False}, resumo)
                alvo = fila.caminho_da_cena("historia_00099", 2)
                alvo.parent.mkdir(parents=True, exist_ok=True)
                alvo.write_bytes(b"0" * (fila.BYTES_MINIMOS + 1))
                self.assertEqual(2, len(fila.pendentes("historia_00099", roteiro)))
                self.assertEqual([1, 3],
                                 [p["n"] for p in fila.pendentes("historia_00099",
                                                                 roteiro)])
                # arquivo truncado nao conta como pronto
                alvo.write_bytes(b"0" * 10)
                self.assertEqual(3, len(fila.pendentes("historia_00099", roteiro)))
            finally:
                fila.OUTPUTS = antes


# -------------------------------------------------------------- 5. ponte
class PonteTests(unittest.TestCase):
    def test_a_ponte_carrega_narrador_e_trilha(self):
        from contos import compartilhado
        if not compartilhado.disponivel():
            self.skipTest("random_builds nao esta ao lado")
        voz = compartilhado.voz()
        self.assertEqual("Isto e um teste.", voz.falavel("ISTO E UM TESTE"))
        self.assertTrue(hasattr(compartilhado.trilha(), "trilha"))
        # o `src` deste projeto nao pode ter sido substituido pelo de la
        import contos.roteiro.roteiro as meu
        self.assertIn("historias", str(Path(meu.__file__)))


if __name__ == "__main__":
    unittest.main()
