# -*- coding: utf-8 -*-
"""Contratos da revisao de retencao (29/08/2026).

O diagnostico que motivou tudo isto: video de 73 s de media, 14 roletas
identicas de 3,3 s, praticamente mudo (assets/music e sfx vazios, narracao
com tts:null), gancho de texto sobre fundo liso, payoff aos 62 s e 40 de 64
videos sem nenhuma reacao real. O que este arquivo trava:

1. Tempo de tela proporcional ao PESO: atributo numerico com rolagem NORMAL
   vira roleta-relampago; tudo que e noticia (classe fora de NORMAL, atributo
   escolhido, reacao) gira cheio e ganha a legenda de tensao durante o giro.
2. O gancho abre com a IMAGEM do personagem quando ela existe (e continua
   sendo o evento `hook`, curto); sem imagem, abre pela rolagem absurda ou
   pelo texto. O gancho B e sempre de outro tipo que o A.
3. Com a imagem no disco, o personagem aparece logo depois de CLASSE e
   PERSONALIDADE, e a placa NAO entrega a altura ainda nao sorteada.
4. Com a estreia gravada, o round decisivo entra no fim do build: trecho
   terminando apos o KO, HUD e callouts no relogio do trecho, stinger antes
   e CTA convidando para a estreia completa.
5. A narracao tem pergunta durante o giro e comentario no instante em que a
   roda para; a roleta rapida so fala o valor; as falas nunca se atropelam.
6. Voz: texto de tela vira texto falavel; a montagem coloca cada fala no
   tempo e corta antes da proxima.
7. Trilha e efeitos nascem por sintese, deterministicos por seed, e cada
   tipo de evento tem o seu som.
8. Publicar: build sem payoff/estreia/mp4 atualizado aparece com pendencia.
9. Metricas: a curva de retencao aponta o EVENTO da timeline onde a queda
   acontece; o registro de publicados liga o mp4 ao id da plataforma.

Rode de dentro de random_builds/:
    python -m unittest tests.test_retencao_regressions -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builds.assets.catalog import AssetCatalog                             # noqa: E402
from builds.assets.selector import AssetSelector                            # noqa: E402
from builds.content import voz                                              # noqa: E402
from builds.content.caption_generator import CaptionGenerator               # noqa: E402
from builds.content.narration_generator import NarrationGenerator           # noqa: E402
from builds.editing.timeline_builder import TimelineBuilder                 # noqa: E402
from builds.generation.random_engine import RandomEngine                    # noqa: E402
from builds.generation.session_generator import SessionGenerator, load_config  # noqa: E402
from builds.publicar import catalogo, metricas                              # noqa: E402
from builds.video import trilha                                             # noqa: E402

EDICAO = load_config("editing.json")
CAPTIONS = load_config("captions.json")
FRASES = load_config("frases.json")
SEEDS = (20260822, 4242, 77)


def _gerar(seed: int) -> dict:
    return SessionGenerator().generate(seed=seed, generation_id=f"generation_{seed}")


def _plano(generation: dict, out_dir=None, config: dict | None = None) -> dict:
    builder = TimelineBuilder(config or EDICAO,
                              CaptionGenerator(CAPTIONS, FRASES),
                              AssetSelector(AssetCatalog(ROOT / "assets")))
    return builder.build(RandomEngine(generation["seed"]).fork("editing"),
                         generation, out_dir)


def _png(caminho: Path, tamanho=(64, 96)) -> Path:
    from PIL import Image
    Image.new("RGB", tamanho, (120, 60, 200)).save(caminho)
    return caminho


def _estreia_falsa(pasta: Path, duracao_clipe: float = 24.0, ko: float = 20.0) -> Path:
    """Uma estreia gravada de mentira: fight.json + clipes vazios no disco."""
    gameplay = pasta / "estreia" / "gameplay"
    gameplay.mkdir(parents=True)
    clipes = {}
    for perfil in ("celular", "normal"):
        arquivo = gameplay / f"luta_01_{perfil}.mp4"
        arquivo.write_bytes(b"\x00" * 2048)
        clipes[perfil] = {"path": str(arquivo), "duracao": duracao_clipe,
                          "trechos": [[0.0, duracao_clipe]], "crop": None}
    passos = int(duracao_clipe * 4)
    luta = {
        "match_id": 0, "rodada": 0, "rodada_nome": "ROUND 2", "origem": "estreia",
        "p1": "Heroi", "p2": "Vilao", "vencedor": "Heroi", "perdedor": "Vilao",
        "duracao": ko, "ko_type": "KO", "hp_vencedor": 40, "tier": "GOOD",
        "clipes": clipes, "ko_em_clipe": ko, "duracao_clipe": duracao_clipe,
        "serie_hp": [(t * 0.25, 100 - t, 100 - t * 1.6) for t in range(passos)],
        "serie_plano": [(t * 0.5, "PRESSAO", 0.3, "RECUAR", 0.2) for t in range(int(duracao_clipe * 2))],
        "eventos_dano": [(t * 0.5, "p1" if t % 2 else "p2", 6.0) for t in range(2, passos // 2)],
        "eventos_narrativos": [{"t": 3.0, "tipo": "primeiro_sangue"},
                               {"t": ko - 0.2, "tipo": "ko"}],
        "score": 70, "surpresa": 20, "sentiment": "positive", "intensity": 0.6,
        "round": 2, "melhor_de": 3, "placar": [2, 0], "marcas": [],
    }
    fight = {"seed": 7, "kind": "fight", "origem": "estreia", "estreia_de": "Heroi",
             "p1": "Heroi", "p2": "Vilao", "cenario": "x", "melhor_de": 3,
             "placar": [2, 0], "lutas": [dict(luta, round=1), luta], "luta": luta,
             "vencedor": "Heroi", "vencedor_gerado": True}
    with open(pasta / "estreia" / "fight.json", "w", encoding="utf-8") as fh:
        json.dump(fight, fh)
    return pasta


# ------------------------------------------------------------------ 1. ritmo
def _peso(evento: dict) -> float:
    """Peso editorial da rolagem daquele evento (0 quando o plano nao traz)."""
    return float((evento.get("roll") or {}).get("weight")
                 or evento.get("weight") or 0)


class RitmoPorPesoTests(unittest.TestCase):
    def test_o_giro_cheio_e_um_orcamento(self):
        """Relampago e o PADRAO; o giro cheio e caro e tem teto.

        A regra antiga era o contrario ("relampago so para numero de peso
        baixo") e so 16% das roletas passavam rapido: sobravam 11,8 giros
        cheios = 40,4 s da MESMA roda roxa por video, 55% do tempo de tela.
        Medido em 31/08/2026 sobre 33 planos.
        """
        teto = EDICAO["roletas_cheias_max"]
        d = EDICAO["durations"]
        for seed in SEEDS:
            with self.subTest(seed=seed):
                eventos = [e for e in _plano(_gerar(seed))["events"]
                           if e["type"] == "roulette"]
                cheias = [e for e in eventos if not e["rapida"]]
                self.assertTrue(any(e["rapida"] for e in eventos),
                                "nenhuma roleta rapida")
                self.assertTrue(cheias, "todas relampago: o video perde o ritmo")
                self.assertLessEqual(
                    len(cheias), teto + 2,
                    f"{len(cheias)} giros cheios: a roda volta a dominar a tela")
                self.assertLess(len(cheias), len(eventos) / 2,
                                "o giro cheio tem que ser a excecao")
                for e in eventos:
                    if e["rapida"]:
                        self.assertAlmostEqual(d["roulette_spin_fast"],
                                               e["spin_duration"])
                        self.assertNotIn("caption_spin", e)
                    else:
                        self.assertAlmostEqual(d["roulette_spin"],
                                               e["spin_duration"])
                        self.assertTrue(e["caption_spin"],
                                        "roleta cheia sem tensao no giro")

    def test_o_giro_cheio_vai_para_a_maior_noticia(self):
        """O orcamento e gasto no que TEM noticia, nunca no que sobrou.

        Nao da mais para exigir giro cheio de TODA rolagem pesada (o teto
        pode ser menor que o numero delas), mas a ordem tem que valer:
        nenhuma relampago pode pesar mais que uma cheia.
        """
        for seed in SEEDS:
            with self.subTest(seed=seed):
                eventos = [e for e in _plano(_gerar(seed))["events"]
                           if e["type"] == "roulette"]
                # `escolhido`/com reacao sao obrigatorias e nao entram na ordem
                def opcional(e):
                    return not e["roll"].get("escolhido")
                pesos_cheios = [_peso(e) for e in eventos
                                if not e["rapida"] and opcional(e)]
                pesos_rapidos = [_peso(e) for e in eventos if e["rapida"]]
                if pesos_cheios and pesos_rapidos:
                    self.assertGreaterEqual(
                        min(pesos_cheios), max(pesos_rapidos),
                        "uma rolagem mais fraca ficou com o giro caro")

    def test_a_roda_nao_domina_mais_a_tela(self):
        """O sintoma que originou a onda 13, em SEGUNDOS.

        Medido em 31/08/2026 sobre 33 planos reais: 11,8 giros cheios =
        40,4 s de roda por video. Aqui o plano e seco (sem imagem, reacao
        nem luta), entao a roleta e quase todo o conteudo e a PROPORCAO nao
        diz nada — o que importa e o tempo absoluto que ela ocupa.
        """
        for seed in SEEDS:
            with self.subTest(seed=seed):
                plano = _plano(_gerar(seed))
                roleta = sum(e["duration"] for e in plano["events"]
                             if e["type"] == "roulette")
                self.assertLess(roleta, 26,
                                f"{roleta:.1f}s de roleta (antes eram 40,4s)")

    def test_o_video_encolheu(self):
        """Sem clipes, o plano fica bem abaixo dos 73 s de media de antes."""
        for seed in SEEDS:
            total = _plano(_gerar(seed))["total_duration"]
            self.assertLess(total, 50, f"seed {seed}: {total}s")
            self.assertGreater(total, 25)

    def test_tensao_existe_para_toda_roleta(self):
        for roleta in FRASES["por_roleta"]:
            self.assertTrue(FRASES["stakes"].get(roleta), roleta)


class LikeECtaTests(unittest.TestCase):
    """O CTA: ate 31/08/2026 NENHUMA copy pedia like (grep em src/ e config/).

    Os 10 CTAs pediam comentario ou follow, e o cartao final era texto branco
    sobre fundo quase preto — a ultima coisa do video era uma tela morta, e e
    exatamente nela que a decisao de curtir acontece.
    """

    def test_todo_cta_pede_like(self):
        for banco in ("outro", "outro_com_estreia"):
            frases = CAPTIONS[banco]
            self.assertTrue(frases, banco)
            for frase in frases:
                self.assertIn("LIKE", frase.upper(), f"{banco}: {frase}")

    def test_o_cta_tem_imagem_atras_quando_ela_existe(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            _png(pasta / "character_weapon_reference.png")
            _png(pasta / "character_image.png")
            plano = _plano(_gerar(SEEDS[0]), pasta)
            outro = [e for e in plano["events"] if e["type"] == "outro"][0]
            self.assertEqual("imagem", (outro.get("asset") or {}).get("media"),
                             "o CTA voltou a ser cartao de texto no vazio")

    def test_sem_imagem_o_cta_nao_quebra(self):
        outro = [e for e in _plano(_gerar(SEEDS[0]))["events"]
                 if e["type"] == "outro"][0]
        self.assertNotIn("asset", outro)
        self.assertTrue(outro["caption"])

    def test_o_gancho_tem_variedade_suficiente(self):
        """5 frases repetiam entre videos consecutivos (medido em 20 planos)."""
        self.assertGreaterEqual(len(CAPTIONS["hook_payoff"]), 9)


class TextoDuplicadoTests(unittest.TestCase):
    """O karaoke escrevia a MESMA frase que o cartao ja mostrava.

    Nestes eventos a narracao E o `caption` (veja `build_script`), entao a
    legenda karaoke repetia palavra por palavra o texto grande logo acima —
    ocupava tela, nao acrescentava nada e fazia o video parecer amador.
    Visto nos frames de gen_00080/76/82 em 31/08/2026.
    """

    def test_eventos_cuja_fala_e_a_legenda_nao_tem_karaoke(self):
        from builds.video.renderer import VideoRenderer
        for tipo in ("hook", "stinger", "outro", "final", "nameplate"):
            self.assertIsNone(VideoRenderer.KARAOKE_Y.get(tipo, "faltando"),
                              f"{tipo} voltou a escrever duas vezes")

    def test_a_roleta_mantem_o_karaoke(self):
        """Na roleta a fala e a pergunta/comentario, nao o cartao: nao duplica."""
        from builds.video.renderer import VideoRenderer
        self.assertIsNotNone(VideoRenderer.KARAOKE_Y["roulette"])


# ---------------------------------------------------------------- 2. gancho
class GanchoTests(unittest.TestCase):
    def test_sem_imagem_o_gancho_e_texto_ou_absurdo(self):
        plano = _plano(_gerar(SEEDS[0]))
        gancho = plano["events"][0]
        self.assertEqual("hook", gancho["type"])
        self.assertIn(gancho["variante"], ("texto", "absurdo"))
        self.assertLessEqual(gancho["duration"], 2.0)
        self.assertNotIn("asset", gancho)

    def test_com_imagem_o_gancho_e_o_payoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            _png(pasta / "character_weapon_reference.png")
            _png(pasta / "character_image.png")
            plano = _plano(_gerar(SEEDS[0]), pasta)
            gancho = plano["events"][0]
            self.assertEqual("hook", gancho["type"])
            self.assertEqual("payoff", gancho["variante"])
            self.assertEqual("imagem", gancho["asset"]["media"])
            # sem o video do Digen a referencia vira o PAYOFF, entao o gancho
            # abre pelo personagem (a mesma imagem nao abre E fecha o video)
            self.assertTrue(gancho["asset"]["path"].endswith("character_image.png"))
            self.assertIn(gancho["caption"], CAPTIONS["hook_payoff"])
            # B existe e e de OUTRO tipo
            self.assertIn("gancho_b", plano)
            self.assertNotEqual(plano["gancho_b"]["variante"], "payoff")
            self.assertEqual(plano["gancho_b"]["duration"], gancho["duration"])

    def test_gancho_b_pode_ser_desligado(self):
        config = json.loads(json.dumps(EDICAO))
        config["gancho"]["ab"] = False
        self.assertNotIn("gancho_b", _plano(_gerar(SEEDS[0]), None, config))


# -------------------------------------------------------- 3. revelacao cedo
class RevelacaoCedoTests(unittest.TestCase):
    def test_personagem_aparece_depois_de_classe_e_personalidade(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            _png(pasta / "character_image.png")
            eventos = _plano(_gerar(SEEDS[1]), pasta)["events"]
            tipos = [e["type"] for e in eventos]
            ident = tipos.index("identity")
            self.assertEqual(["roulette", "roulette"], tipos[ident - 2:ident])
            ids = [eventos[ident - 2]["roll"]["roulette_id"], eventos[ident - 1]["roll"]["roulette_id"]]
            self.assertEqual(["classe", "personalidade"], ids)
            self.assertEqual("character", eventos[ident]["slot"])
            # a placa nao entrega a altura que a roleta de TAMANHO ainda vai sortear
            self.assertNotIn(" m", eventos[ident]["nameplate"]["subtitulo"])
            # e as roletas de atributo continuam DEPOIS da revelacao
            restantes = [e["roll"]["roulette_id"] for e in eventos[ident + 1:]
                         if e["type"] == "roulette" and e["roll"]["entity"] == "character"]
            self.assertEqual({"tamanho", "forca", "mana"}, set(restantes))

    def test_sem_imagem_o_nameplate_fica_no_fim_da_secao(self):
        eventos = _plano(_gerar(SEEDS[1]))["events"]
        tipos = [e["type"] for e in eventos]
        placa = tipos.index("nameplate")
        anteriores = [e["roll"]["roulette_id"] for e in eventos[:placa] if e["type"] == "roulette"]
        self.assertEqual({"classe", "personalidade", "tamanho", "forca", "mana"}, set(anteriores))
        self.assertIn(" m", eventos[placa]["nameplate"]["subtitulo"])


# ------------------------------------------------------------ 4. luta no fim
class LutaNoBuildTests(unittest.TestCase):
    def test_round_decisivo_entra_antes_da_nota(self):
        cfg = EDICAO["luta_no_build"]
        with tempfile.TemporaryDirectory() as tmp:
            plano = _plano(_gerar(SEEDS[2]), _estreia_falsa(Path(tmp)))
            eventos = plano["events"]
            tipos = [e["type"] for e in eventos]
            self.assertIn("gameplay", tipos)
            g = tipos.index("gameplay")
            self.assertEqual("stinger", tipos[g - 1])
            self.assertIn(eventos[g - 1]["caption"], CAPTIONS["stinger"]["luta"])
            self.assertEqual("final", tipos[g + 1])
            luta = eventos[g]
            self.assertLessEqual(luta["duration"], cfg["segundos"] + 0.01)
            self.assertAlmostEqual(luta["start_offset"] + luta["duration"],
                                   20.0 + cfg["depois_do_ko"], places=1)
            self.assertEqual("contain", luta["fit"])
            self.assertTrue(luta["narracao"])
            # HUD e callouts no relogio do TRECHO
            tempos = [a[0] for a in luta["hud"]["serie_hp"]]
            self.assertEqual(0.0, tempos[0])
            self.assertLessEqual(max(tempos), luta["duration"] + 1e-6)
            for c in luta.get("callouts") or []:
                self.assertGreaterEqual(c["t"], 0.0)
                self.assertLessEqual(c["t"], luta["duration"])
            self.assertIn(eventos[-1]["caption"], CAPTIONS["outro_com_estreia"])

    def test_sem_estreia_nada_entra(self):
        eventos = _plano(_gerar(SEEDS[2]))["events"]
        self.assertNotIn("gameplay", [e["type"] for e in eventos])
        self.assertIn(eventos[-1]["caption"], CAPTIONS["outro"])

    def test_pode_ser_desligada(self):
        config = json.loads(json.dumps(EDICAO))
        config["luta_no_build"]["ativa"] = False
        with tempfile.TemporaryDirectory() as tmp:
            eventos = _plano(_gerar(SEEDS[2]), _estreia_falsa(Path(tmp)), config)["events"]
            self.assertNotIn("gameplay", [e["type"] for e in eventos])


# ---------------------------------------------------------------- 5. narracao
class NarracaoTests(unittest.TestCase):
    def test_pergunta_no_giro_e_comentario_no_resultado(self):
        generation = _gerar(SEEDS[0])
        plano = _plano(generation)
        script = NarrationGenerator().build_script(
            RandomEngine(generation["seed"]).fork("narration"), plano, generation)
        self.assertNotEqual(None, script["tts"])
        linhas = script["lines"]
        por_inicio = {round(l["start"], 3): l for l in linhas}
        for e in plano["events"]:
            if e["type"] != "roulette":
                continue
            resultado = por_inicio.get(round(e["start"] + e["spin_duration"], 3))
            if e["rapida"]:
                # relampago e MUDA: ler "seis virgula tres" leva mais que a cena
                self.assertNotIn(round(e["start"], 3), por_inicio, "roleta rapida com pergunta")
                self.assertIsNone(resultado, "roleta rapida com comentario")
            else:
                self.assertIsNotNone(resultado, "sem comentario no resultado")
                self.assertIn(round(e["start"], 3), por_inicio, "roleta cheia sem pergunta")
                # o parentese da tela nao e falado
                self.assertNotIn("(", resultado["text"])
        # nunca duas falas comecando no mesmo instante, e sempre em ordem
        inicios = [l["start"] for l in linhas]
        self.assertEqual(inicios, sorted(inicios))
        self.assertEqual(len(inicios), len(set(round(i, 3) for i in inicios)))


# --------------------------------------------------------------------- 6. voz
class VozTests(unittest.TestCase):
    def test_texto_de_tela_vira_texto_falavel(self):
        self.assertEqual("Esse cara saiu 100% da roleta.", voz.falavel("ESSE CARA SAIU 100% DA ROLETA"))
        self.assertEqual("mede 2 metros e 1.", voz.falavel("mede 2,01m"))
        self.assertEqual("1 e 97.", voz.falavel("1,97m"))
        self.assertEqual("2 metros.", voz.falavel("2,00m"))
        self.assertEqual("Duelista. Serve.", voz.falavel("Duelista (Precisão). Serve."))
        self.assertEqual("3 vírgula 6 quilos. isso ajuda.", voz.falavel("3,6kg. isso ajuda 🔥"))
        self.assertEqual("", voz.falavel(""))

    def test_montagem_coloca_cada_fala_no_tempo_e_corta_antes_da_proxima(self):
        if not trilha.disponivel():
            self.skipTest("numpy ausente")
        import numpy as np
        taxa = 44100

        def falsa(texto, cfg, cache, log=None):
            # "fala" de 1,5 s: mais longa que o espaco da segunda linha
            destino = Path(cache) / f"{abs(hash(texto))}.wav"
            t = np.arange(int(1.5 * taxa)) / taxa
            trilha.gravar_wav(destino, 0.5 * np.sin(2 * np.pi * 440 * t), taxa)
            return destino

        original = voz.sintetizar
        voz.sintetizar = falsa
        try:
            with tempfile.TemporaryDirectory() as tmp:
                linhas = [{"start": 0.0, "duration": 2.0, "text": "Primeira."},
                          {"start": 2.0, "duration": 0.6, "text": "Segunda."},
                          {"start": 2.7, "duration": 1.0, "text": "Terceira."}]
                saida = voz.montar(linhas, Path(tmp) / "voz.wav", voz.config({}),
                                   taxa=taxa, cache=Path(tmp))
                self.assertIsNotNone(saida)
                with wave.open(str(saida)) as w:
                    quadros = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")[::2]
                    seg = w.getframerate()
                self.assertAlmostEqual(len(quadros) / seg, 3.7 + 1.0, places=1)
                energia = lambda a, b: float(np.abs(quadros[int(a * seg):int(b * seg)]).mean())  # noqa: E731
                self.assertGreater(energia(0.1, 1.0), 100)          # primeira fala esta la
                self.assertGreater(energia(2.1, 2.5), 100)          # segunda tambem
                self.assertLess(energia(2.66, 2.74), energia(2.1, 2.5) * 0.5)  # cortada antes da terceira
                self.assertGreater(energia(2.8, 3.5), 100)
        finally:
            voz.sintetizar = original


# ------------------------------------------------------------------ 7. trilha
class TrilhaTests(unittest.TestCase):
    def setUp(self):
        if not trilha.disponivel():
            self.skipTest("numpy ausente")

    def test_trilha_e_deterministica_e_estereo(self):
        a = trilha.trilha(seed=3, compassos=2)
        b = trilha.trilha(seed=3, compassos=2)
        self.assertEqual(a.shape[1], 2)
        self.assertEqual(a.shape, b.shape)
        self.assertTrue((a == b).all())
        self.assertAlmostEqual(a.shape[0] / trilha.TAXA, 2 * 4 * 60 / 142, places=1)
        self.assertLessEqual(float(abs(a).max()), 0.98)

    def test_cada_evento_tem_o_seu_som(self):
        def camadas(**evento):
            return trilha.sfx_do_evento({"duration": 1.6, **evento})
        self.assertEqual(2, len(camadas(type="hook")))
        self.assertEqual(1, len(camadas(type="stinger")))
        self.assertEqual(2, len(camadas(type="final")))
        self.assertEqual([], camadas(type="reaction"))
        insano = camadas(type="roulette", spin_duration=1.5, effects=["bass_hit", "flash"])
        ruim = camadas(type="roulette", spin_duration=1.5, effects=["sad_sfx"])
        normal = camadas(type="roulette", spin_duration=0.7, effects=[])
        self.assertEqual(1.5, insano[0][0])
        self.assertGreater(len(insano[0][1]), len(normal[0][1]))
        self.assertNotEqual(len(ruim[0][1]), len(normal[0][1]))

    def test_garantir_trilha_nao_pisa_em_musica_do_usuario(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            (pasta / "minha.mp3").write_bytes(b"x" * 10)
            self.assertEqual(pasta / "minha.mp3", trilha.garantir_trilha(pasta))
            self.assertFalse((pasta / trilha.NOME_TRILHA).exists())


# --------------------------------------------------------------- 8. publicar
class PendenciasTests(unittest.TestCase):
    """Contratos com o video do Digen LIGADO (a config real pode estar com
    ele desligado — ver PayoffImagemTests para esse caso)."""

    def setUp(self):
        from unittest.mock import patch
        from builds.identity import config as icfg
        ligado = patch.object(icfg, "payoff_video_ativo", lambda ajustes=None: True)
        ligado.start()
        self.addCleanup(ligado.stop)

    def test_build_incompleta_tem_pendencias(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            (pasta / "final_celular.mp4").write_bytes(b"\x00" * 10)
            lista = catalogo.pendencias_da_build(pasta, "celular")
            self.assertEqual(3, len(lista))
            self.assertTrue(any("payoff" in p for p in lista))
            self.assertTrue(any("estreia" in p for p in lista))

    def test_build_completa_nao_tem_pendencias(self):
        import os
        import time
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            (pasta / "character_weapon_video.mp4").write_bytes(b"\x00")
            (pasta / "character_image.png").write_bytes(b"\x00")
            (pasta / "estreia").mkdir()
            (pasta / "estreia" / "fight.json").write_text("{}")
            (pasta / "final_celular.mp4").write_bytes(b"\x00" * 10)
            self.assertEqual([], catalogo.pendencias_da_build(pasta, "celular"))
            # mp4 mais velho que o payoff: precisa de re-render
            velho = time.time() - 600
            os.utime(pasta / "final_celular.mp4", (velho, velho))
            lista = catalogo.pendencias_da_build(pasta, "celular")
            self.assertEqual(1, len(lista))
            self.assertIn("mais velho", lista[0])


# ---------------------------------------------------------------- 9. metricas
class MetricasTests(unittest.TestCase):
    def test_a_queda_aponta_o_evento_da_timeline(self):
        eventos = [{"type": "hook", "start": 0.0, "duration": 1.6},
                   {"type": "roulette", "category": "CLASSE", "start": 1.6, "duration": 2.7},
                   {"type": "roulette", "category": "PESO", "start": 4.3, "duration": 2.7},
                   {"type": "final", "start": 7.0, "duration": 1.8}]
        curva = [(i / 10, 1.0 - 0.02 * i) for i in range(11)]
        curva[6] = (0.6, curva[5][1] - 0.4)          # tombo aos 60% (~5,3 s)
        dado = {"curva": curva, "duracao": 8.8}
        quedas = metricas.quedas(dado, eventos, quantas=1)
        self.assertEqual(1, len(quedas))
        self.assertEqual("roleta PESO", quedas[0]["evento"])
        self.assertAlmostEqual(0.4, quedas[0]["queda"], places=6)
        self.assertEqual(len(metricas.sparkline(curva, 5)), 5)

    def test_registro_liga_o_mp4_ao_id_da_plataforma(self):
        original = metricas.REGISTRO
        with tempfile.TemporaryDirectory() as tmp:
            metricas.REGISTRO = Path(tmp) / "publicados.jsonl"
            try:
                video = catalogo.Video(id="generation_00001:build:celular:B", origem="build",
                                       perfil="celular", caminho=Path("x.mp4"), titulo="t",
                                       descricao="", fonte_id="generation_00001", variante="B")
                linha = metricas.registrar_publicacao(video, "https://youtu.be/abc123XYZ")
                self.assertEqual("abc123XYZ", linha["youtube_id"])
                self.assertEqual("B", linha["variante"])
                self.assertEqual(1, len(metricas.publicados()))
            finally:
                metricas.REGISTRO = original

    def test_catalogo_lista_o_gancho_b_como_video_proprio(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            for nome in ("final_celular.mp4", "final_celular_ganchoB.mp4"):
                (pasta / nome).write_bytes(b"\x00" * (catalogo.BYTES_MINIMOS + 1))
            videos = catalogo._videos_de(pasta, catalogo.BUILD, "generation_x", {},
                                         {"titulos": {"build": "T"}}, "rotulo")
            self.assertEqual(["A", "B"], [v.variante for v in videos])
            self.assertTrue(videos[1].id.endswith(":B"))
            self.assertIn("gancho B", videos[1].rotulo)
            self.assertTrue(all(v.pendencias for v in videos))


# ------------------------------------------------------------------ 10. fluxo
class FluxoRetencaoTests(unittest.TestCase):
    """O painel e o `fluxo` mostram voz, luta no video e gancho A/B por build,
    e acusam a estreia gravada que ficou FORA do video publicavel."""

    def _pasta(self, tmp: str, com_luta: bool, com_estreia: bool) -> Path:
        pasta = Path(tmp)
        eventos = [{"type": "hook", "variante": "payoff", "start": 0.0, "duration": 1.6}]
        if com_luta:
            eventos.append({"type": "gameplay", "start": 30.0, "duration": 6.5})
        (pasta / "edit_plan.json").write_text(
            json.dumps({"events": eventos, "total_duration": 41.2}), encoding="utf-8")
        (pasta / "voz.wav").write_bytes(b"\x00" * 20_000)
        (pasta / "final_celular_ganchoB.mp4").write_bytes(b"\x00" * 20_000)
        if com_estreia:
            (pasta / "estreia").mkdir()
            (pasta / "estreia" / "fight.json").write_text("{}", encoding="utf-8")
        return pasta

    def test_le_voz_luta_e_gancho(self):
        from builds.pipeline import fluxo
        with tempfile.TemporaryDirectory() as tmp:
            ret = fluxo.retencao_de(self._pasta(tmp, com_luta=True, com_estreia=True))
            self.assertTrue(ret["voz"])
            self.assertTrue(ret["luta"])
            self.assertTrue(ret["gancho_b"])
            self.assertEqual("payoff", ret["gancho"])
            self.assertAlmostEqual(41.2, ret["duracao"])
            self.assertFalse(ret["estreia_fora_do_video"])

    def test_estreia_gravada_fora_do_video_vira_proximo_passo(self):
        from builds.pipeline import fluxo
        with tempfile.TemporaryDirectory() as tmp:
            ret = fluxo.retencao_de(self._pasta(tmp, com_luta=False, com_estreia=True))
            self.assertTrue(ret["estreia_fora_do_video"])
            etapas = {"build": {"estado": fluxo.OK},
                      "estreia": {"estado": fluxo.OK}}
            for chave, _r, slot in fluxo.ETAPAS:
                if slot is not None:
                    etapas[chave] = {"estado": fluxo.OK, "detalhe": ""}
            passo = fluxo._proximo_passo("generation_00001", etapas, ret)
            self.assertIn("--refazer-edicao", passo)
            self.assertIn("estreia", passo)


# ------------------------------------------------------------ 11. remessa 2
class Remessa2Tests(unittest.TestCase):
    """Avatar persistente, etiqueta da reacao e palavras no relogio do video."""

    def test_avatar_acompanha_as_roletas_depois_da_revelacao(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            _png(pasta / "character_image.png")
            _png(pasta / "weapon_image.png")
            eventos = _plano(_gerar(SEEDS[1]), pasta)["events"]
            tipos = [e["type"] for e in eventos]
            ident = tipos.index("identity")
            for e in eventos[:ident]:
                self.assertNotIn("avatares", e)
            depois = [e for e in eventos[ident + 1:] if e["type"] == "roulette"]
            self.assertTrue(depois)
            for e in depois:
                self.assertIn("character", e["avatares"])
                self.assertTrue(e["avatares"]["character"]["nome"])
            # a arma so entra no avatar DEPOIS da revelacao dela
            arma = [i for i, e in enumerate(eventos)
                    if e["type"] == "identity" and e.get("slot") == "weapon"][0]
            antes_da_arma = [e for e in eventos[ident + 1:arma] if e.get("avatares")]
            self.assertTrue(all("weapon" not in e["avatares"] for e in antes_da_arma))
            depois_da_arma = [e for e in eventos[arma + 1:] if e.get("avatares")]
            self.assertTrue(any("weapon" in e["avatares"] for e in depois_da_arma))

    def test_sem_imagem_nao_ha_avatar(self):
        for e in _plano(_gerar(SEEDS[1]))["events"]:
            self.assertNotIn("avatares", e)

    def test_etiqueta_da_reacao_explica_a_classe(self):
        badge = TimelineBuilder._badge_da_reacao
        self.assertEqual("RARO · 5% de chance",
                         badge({"classification": "RARE", "reason": "probabilidade 0.05"}))
        self.assertEqual("ABSURDO · 97 de 100",
                         badge({"classification": "ABSURD",
                                "reason": "score 97 no extremo da escala"}))
        self.assertEqual("CONTRADITÓRIO · briga com o resto da build",
                         badge({"classification": "CONTRADICTORY",
                                "reason": "resultado briga com o que ja foi sorteado"}))
        self.assertEqual("", badge({"classification": "NORMAL", "reason": ""}))
        for seed in SEEDS:
            for e in _plano(_gerar(seed))["events"]:
                if e["type"] == "reaction":
                    self.assertIn("badge", e)

    def test_palavras_ficam_no_relogio_do_video(self):
        if not trilha.disponivel():
            self.skipTest("numpy ausente")
        import numpy as np
        taxa = 44100

        def falsa(texto, cfg, cache, log=None):
            destino = Path(cache) / f"{abs(hash(texto))}.wav"
            t = np.arange(int(1.0 * taxa)) / taxa
            trilha.gravar_wav(destino, 0.5 * np.sin(2 * np.pi * 440 * t), taxa)
            return destino

        original = voz.sintetizar
        voz.sintetizar = falsa
        try:
            with tempfile.TemporaryDirectory() as tmp:
                linhas = [{"start": 3.0, "duration": 2.0, "text": "Classe? Duelista agora."},
                          {"start": 6.0, "duration": 1.0, "text": "Seis vírgula três."}]
                saida = voz.montar(linhas, Path(tmp) / "voz.wav", voz.config({}),
                                   taxa=taxa, cache=Path(tmp))
                self.assertIsNotNone(saida)
                palavras = json.loads(voz.caminho_palavras(saida).read_text(encoding="utf-8"))
                self.assertEqual(["Classe?", "Duelista", "agora.", "Seis", "vírgula", "três."],
                                 [p["texto"] for p in palavras])
                primeira = [p for p in palavras if p["linha"] == 0]
                self.assertGreaterEqual(primeira[0]["t0"], 3.0)
                self.assertLessEqual(primeira[-1]["t1"], 3.0 + 1.0 + 0.11)
                for a, b in zip(palavras, palavras[1:]):
                    self.assertLessEqual(a["t0"], b["t0"])
        finally:
            voz.sintetizar = original

    def test_frase_do_motor_vira_palavras(self):
        limites = [{"t0": 0.0, "t1": 1.0, "texto": "Na média.", "tipo": "SentenceBoundary"},
                   {"t0": 1.0, "t1": 1.4, "texto": "Bom", "tipo": "WordBoundary"}]
        palavras = voz._em_palavras(limites)
        self.assertEqual(["Na", "média.", "Bom"], [p["texto"] for p in palavras])
        self.assertAlmostEqual(1.0, palavras[1]["t1"], places=3)
        self.assertLess(palavras[0]["t1"], palavras[1]["t1"])


# ---------------------------------------------------------- 12. sem credito
class CreditoTests(unittest.TestCase):
    """Saldo 0 no Digen NAO impede o payoff quando o modelo e o Real Motion
    (incluso no plano). So um modelo pago (fora da lista branca) bloqueia."""

    def test_modelo_incluso_segue_sem_credito(self):
        from builds.identity import worker
        ajustes = {"modelo": "Real Motion 3.5", "referencias": {"modelo": None},
                   "modelos_permitidos": ["Real Motion 3.5", "Real Motion 3.2"]}
        self.assertFalse(worker.credito_bloqueia(ajustes, "digen"))
        self.assertEqual("Real Motion 3.5", worker.modelo_em_uso(ajustes))

    def test_modelo_pago_bloqueia(self):
        from builds.identity import worker
        ajustes = {"modelo": "Real Motion 3.5", "referencias": {"modelo": "Kling 3.0"},
                   "modelos_permitidos": ["Real Motion 3.5"]}
        self.assertTrue(worker.credito_bloqueia(ajustes, "digen"))
        self.assertEqual("Kling 3.0", worker.modelo_em_uso(ajustes))

    def test_config_pode_forcar_o_bloqueio(self):
        from builds.identity import worker
        ajustes = {"modelo": "Real Motion 3.5", "modelos_permitidos": ["Real Motion 3.5"],
                   "creditos_obrigatorios": True}
        self.assertTrue(worker.credito_bloqueia(ajustes, "digen"))

    def test_a_config_real_nao_bloqueia(self):
        from builds.identity import config as icfg
        from builds.identity import worker
        self.assertFalse(worker.credito_bloqueia(icfg.settings(), "digen"))


# ------------------------------------------------- 13. payoff sem o Digen
class PayoffImagemTests(unittest.TestCase):
    """O gerador de video quebrou: desligado, o video sai so com as imagens."""

    def test_sem_video_o_payoff_e_a_imagem_personagem_com_arma(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            _png(pasta / "character_image.png")
            _png(pasta / "character_weapon_reference.png")
            eventos = _plano(_gerar(SEEDS[0]), pasta)["events"]
            payoff = [e for e in eventos
                      if e["type"] == "identity" and e.get("slot") == "character_weapon"]
            self.assertEqual(1, len(payoff))
            self.assertEqual("imagem", payoff[0]["asset"]["media"])
            self.assertTrue(payoff[0]["asset"]["path"].endswith("character_weapon_reference.png"))
            self.assertAlmostEqual(EDICAO["identity_slots"]["character_weapon"]["still"],
                                   payoff[0]["duration"])
            self.assertNotIn("nameplate", [e["type"] for e in eventos
                                           if e.get("slot") == "character_weapon"])
            self.assertTrue(eventos[0]["asset"]["path"].endswith("character_image.png"))

    def test_com_video_o_gancho_volta_a_usar_a_referencia(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            _png(pasta / "character_image.png")
            _png(pasta / "character_weapon_reference.png")
            (pasta / "character_weapon_video.mp4").write_bytes(b"0" * 20_000)
            eventos = _plano(_gerar(SEEDS[0]), pasta)["events"]
            self.assertTrue(eventos[0]["asset"]["path"].endswith("character_weapon_reference.png"))
            payoff = [e for e in eventos
                      if e["type"] == "identity" and e.get("slot") == "character_weapon"][0]
            self.assertEqual("video", payoff["asset"]["media"])

    def test_config_desliga_o_job_do_digen(self):
        from builds.identity import config as icfg
        from builds.identity import slots
        self.assertNotIn(slots.CHARACTER_WEAPON, icfg.jobs_ativos({"payoff_video": False}))
        self.assertIn(slots.REFERENCIA, icfg.jobs_ativos({"payoff_video": False}))
        self.assertIn(slots.CHARACTER_WEAPON, icfg.jobs_ativos({"payoff_video": True}))
        self.assertIn(slots.CHARACTER_WEAPON, icfg.jobs_ativos({}))
        self.assertNotIn(slots.CHARACTER_WEAPON, icfg.slots_ativos({"payoff_video": False}))

    def test_pendencia_com_video_desligado_pede_a_imagem(self):
        from unittest.mock import patch
        from builds.identity import config as icfg
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            (pasta / "final_celular.mp4").write_bytes(b"0" * 10)
            (pasta / "character_image.png").write_bytes(b"0")
            (pasta / "estreia").mkdir()
            (pasta / "estreia" / "fight.json").write_text("{}")
            with patch.object(icfg, "payoff_video_ativo", lambda ajustes=None: False):
                lista = catalogo.pendencias_da_build(pasta, "celular")
                self.assertEqual(1, len(lista))
                self.assertIn("imagem personagem+arma", lista[0])
                (pasta / "character_weapon_reference.png").write_bytes(b"0")
                self.assertEqual([], catalogo.pendencias_da_build(pasta, "celular"))
            with patch.object(icfg, "payoff_video_ativo", lambda ajustes=None: True):
                lista = catalogo.pendencias_da_build(pasta, "celular")
                self.assertTrue(any("Digen" in p for p in lista))


# ------------------------------------------------------- 14. roteiro solido
class RoteiroSolidoTests(unittest.TestCase):
    """A cena espera a fala: medido em 29/08, ~29 de 33 falas por video nao
    cabiam nem acelerando. Agora cada evento cresce ate a narracao terminar."""

    def _plano_e_linhas(self, seed=SEEDS[0]):
        generation = _gerar(seed)
        plano = _plano(generation)
        linhas = NarrationGenerator().build_script(
            RandomEngine(generation["seed"]).fork("narration"), plano, generation)["lines"]
        return generation, plano, linhas

    def test_evento_cresce_ate_a_fala_caber(self):
        from builds.editing.timeline_builder import ajustar_ao_roteiro
        generation, plano, linhas = self._plano_e_linhas()
        antes = json.loads(json.dumps(plano))
        # toda fala dura 2,5 s: bem mais que qualquer slot de resultado
        medidas = {i: 2.5 for i in range(len(linhas))}
        ajustado = ajustar_ao_roteiro(plano, linhas, medidas, EDICAO)
        margem = EDICAO["narracao"]["margem"]
        # as linhas voltam a ser geradas a partir do plano ajustado
        novas = NarrationGenerator().build_script(
            RandomEngine(generation["seed"]).fork("narration"), ajustado, generation)["lines"]
        self.assertEqual([l["text"] for l in linhas], [l["text"] for l in novas])
        novas = sorted(novas, key=lambda l: l["start"])
        for i, linha in enumerate(novas):
            espaco = linha["duration"]
            if i + 1 < len(novas):
                espaco = min(espaco + 5, novas[i + 1]["start"] - linha["start"])
            self.assertGreaterEqual(espaco + 1e-6, 2.5 + min(margem, 0.15) - 1e-6,
                                    f"fala {i} ({linha['text']!r}) nao cabe: {espaco}s")
        self.assertGreater(ajustado["total_duration"], antes["total_duration"])
        # os starts continuam em cadeia, sem buraco nem sobreposicao
        cursor = 0.0
        for e in ajustado["events"]:
            self.assertAlmostEqual(cursor, e["start"], places=2)
            cursor += e["duration"]
        self.assertAlmostEqual(cursor, ajustado["total_duration"], places=2)

    def test_roleta_estica_giro_para_a_pergunta_e_resultado_para_o_comentario(self):
        from builds.editing.timeline_builder import ajustar_ao_roteiro
        generation, plano, linhas = self._plano_e_linhas()
        cheia = next(i for i, e in enumerate(plano["events"])
                     if e["type"] == "roulette" and not e["rapida"])
        evento = plano["events"][cheia]
        spin_antes, dur_antes = evento["spin_duration"], evento["duration"]
        pergunta = next(i for i, l in enumerate(linhas)
                        if abs(l["start"] - evento["start"]) < 1e-6)
        comentario = next(i for i, l in enumerate(linhas)
                          if abs(l["start"] - evento["start"] - spin_antes) < 1e-6)
        ajustado = ajustar_ao_roteiro(plano, linhas, {pergunta: 3.0, comentario: 4.0}, EDICAO)
        e = ajustado["events"][cheia]
        self.assertGreaterEqual(e["spin_duration"], 3.0 + EDICAO["narracao"]["margem_giro"] - 1e-6)
        self.assertGreaterEqual(e["duration"] - e["spin_duration"],
                                4.0 + EDICAO["narracao"]["margem"] - 1e-6)
        self.assertGreater(e["duration"], dur_antes)

    def test_fala_curta_nao_muda_nada(self):
        from builds.editing.timeline_builder import ajustar_ao_roteiro
        generation, plano, linhas = self._plano_e_linhas()
        antes = json.loads(json.dumps(plano))
        ajustado = ajustar_ao_roteiro(plano, linhas, {i: 0.2 for i in range(len(linhas))}, EDICAO)
        self.assertEqual([e["duration"] for e in antes["events"]],
                         [e["duration"] for e in ajustado["events"]])

    def test_clipe_de_video_nao_estica(self):
        from builds.editing.timeline_builder import ajustar_ao_roteiro
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            _png(pasta / "character_image.png")
            (pasta / "character_weapon_video.mp4").write_bytes(b"0" * 20_000)
            generation = _gerar(SEEDS[0])
            plano = _plano(generation, pasta)
            linhas = NarrationGenerator().build_script(
                RandomEngine(generation["seed"]).fork("narration"), plano, generation)["lines"]
            payoff = next(i for i, e in enumerate(plano["events"])
                          if e["type"] == "identity" and e.get("slot") == "character_weapon")
            dur = plano["events"][payoff]["duration"]
            linha = next(i for i, l in enumerate(linhas)
                         if abs(l["start"] - plano["events"][payoff]["start"]) < 1e-6)
            ajustado = ajustar_ao_roteiro(plano, linhas, {linha: 30.0}, EDICAO)
            self.assertEqual(dur, ajustado["events"][payoff]["duration"])


# --------------------------------------------------- 15. pausa nao decapita
class PausaNaFalaTests(unittest.TestCase):
    """`silenceremove=stop_periods=1` cortava a fala na PRIMEIRA pausa:
    "Guerreiro. Na media." virava so "Guerreiro". O decodificador tem que
    manter as pausas do meio e tirar so o silencio do fim."""

    def test_pausa_no_meio_e_mantida_e_silencio_do_fim_sai(self):
        if not trilha.disponivel():
            self.skipTest("numpy ausente")
        import numpy as np
        taxa = 44100
        t = np.arange(int(0.5 * taxa)) / taxa
        tom = 0.5 * np.sin(2 * np.pi * 440 * t)
        pausa = np.zeros(int(0.8 * taxa))         # pausa entre "frases"
        fim = np.zeros(int(1.2 * taxa))           # silencio do fim (sai)
        sinal = np.concatenate([tom, pausa, tom, fim])
        with tempfile.TemporaryDirectory() as tmp:
            arquivo = trilha.gravar_wav(Path(tmp) / "fala.wav", sinal, taxa)
            pcm = voz._pcm(arquivo, taxa)
            self.assertAlmostEqual(0.5 + 0.8 + 0.5, len(pcm) / taxa, delta=0.06)
            # e a medicao usa o MESMO corte
            def falsa(texto, cfg, cache, log=None):
                return arquivo
            original = voz.sintetizar
            voz.sintetizar = falsa
            try:
                medidas = voz.medir([{"text": "Guerreiro. Na média."}], voz.config({}), taxa=taxa,
                                    cache=Path(tmp))
            finally:
                voz.sintetizar = original
            self.assertAlmostEqual(1.8, medidas[0], delta=0.06)


# ------------------------------------------------ 16. modal de login Picasso
class _LocatorModal:
    def __init__(self, pagina, seletor):
        self.pagina, self.seletor = pagina, seletor

    def count(self):
        if "auth-card-email" in self.seletor or "role='dialog'" in self.seletor:
            return 1 if self.pagina.modal_aberto else 0
        if "lucide-x" in self.seletor:
            return 1 if self.pagina.modal_aberto else 0
        return 0

    @property
    def first(self):
        return self

    def is_visible(self):
        return self.pagina.modal_aberto

    def click(self, timeout=None):
        self.pagina.cliques.append(self.seletor)
        if "lucide-x" in self.seletor:
            self.pagina.modal_aberto = False


class _PaginaPicassoFake:
    def __init__(self, modal_aberto=True):
        self.modal_aberto = modal_aberto
        self.cliques = []
        self.url = "https://picassoia.com/create"

    def locator(self, seletor):
        return _LocatorModal(self, seletor)


class PicassoModalTests(unittest.TestCase):
    """Desde 29/08 o Picasso abre um modal de login com a sessao VALIDA: e so
    aviso, fecha pelo X (icone lucide-x). Tentar logar por ele quebrava."""

    def _cliente(self, pagina):
        import random
        from builds.identity.picasso_client import PicassoClient
        return PicassoClient(None, pagina, {"navigation_timeout": 1}, random.Random(1))

    def test_fecha_pelo_x_sem_credenciais(self):
        from unittest.mock import patch
        from builds.identity import picasso_client
        pagina = _PaginaPicassoFake(modal_aberto=True)
        cliente = self._cliente(pagina)
        with patch.object(picasso_client, "pausa_humana", lambda *a, **k: None), \
             patch.object(picasso_client.time, "sleep", lambda *_: None):
            self.assertTrue(cliente._fechar_modal_de_login())
        self.assertFalse(pagina.modal_aberto)
        self.assertTrue(any("lucide-x" in c for c in pagina.cliques))
        self.assertEqual(1, cliente._modal_fechado)

    def test_sem_modal_nao_clica_em_nada(self):
        pagina = _PaginaPicassoFake(modal_aberto=False)
        self.assertFalse(self._cliente(pagina)._fechar_modal_de_login())
        self.assertEqual([], pagina.cliques)

    def test_resolver_dialogo_prefere_o_x_ao_login(self):
        from unittest.mock import patch
        from builds.identity import picasso_client
        pagina = _PaginaPicassoFake(modal_aberto=True)
        cliente = self._cliente(pagina)
        with patch.object(picasso_client, "pausa_humana", lambda *a, **k: None), \
             patch.object(picasso_client.time, "sleep", lambda *_: None), \
             patch.object(picasso_client.iconfig, "load_credentials",
                          lambda *_: self.fail("nao devia tentar logar")):
            self.assertTrue(cliente._resolver_dialogo_de_auth())
        self.assertFalse(pagina.modal_aberto)

    def test_modal_que_volta_depois_de_fechado_vai_para_o_login(self):
        from unittest.mock import patch
        from builds.identity import picasso_client
        pagina = _PaginaPicassoFake(modal_aberto=True)
        cliente = self._cliente(pagina)
        cliente._modal_fechado = 1          # ja foi fechado uma vez nesta pagina
        chamado = []
        with patch.object(picasso_client, "pausa_humana", lambda *a, **k: None), \
             patch.object(picasso_client.time, "sleep", lambda *_: None), \
             patch.object(picasso_client.iconfig, "load_credentials",
                          lambda *_: chamado.append(1) or None):
            with self.assertRaises(picasso_client.GeracaoFalhou):
                cliente._resolver_dialogo_de_auth()
        self.assertEqual([1], chamado)


# ------------------------------------------------------ 17. um worker so
class WorkerUnicoTests(unittest.TestCase):
    """Cinco `identity worker --watch` vivos ao mesmo tempo (29/08/2026): a
    trava impedia o estrago, mas os extras ficavam em loop eterno cedendo a
    trava — memoria a toa e imprevisibilidade sobre QUAL processo assume
    quando o dono morre. Agora o extra sai."""

    def test_ha_worker_ve_a_trava_sem_segurar(self):
        from unittest.mock import patch
        from builds.identity import queue
        # Lock proprio: a maquina pode ter um worker de verdade de pe.
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(queue, "LOCK_WORKER", Path(tmp) / "worker.lock"):
                self.assertFalse(queue.ha_worker())      # ninguem segurando
                with queue.instancia_unica() as sozinho:
                    self.assertTrue(sozinho)
                    self.assertTrue(queue.ha_worker())   # agora ha
                self.assertFalse(queue.ha_worker())      # e soltou

    def _sem_pausa(self):
        """Controle isolado: a maquina pode estar com a pipeline pausada de
        verdade, e ai `observar` entraria no loop de espera para sempre."""
        from unittest.mock import patch
        from builds.identity import controle
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        alvo = patch.object(controle, "ARQUIVO", Path(tmp.name) / "controle.json")
        alvo.start()
        self.addCleanup(alvo.stop)

    def test_watch_extra_sai_em_vez_de_ficar_em_loop(self):
        from unittest.mock import patch
        from builds.identity import worker
        self._sem_pausa()
        chamadas = []
        with patch.object(worker.queue, "ha_worker", lambda: True), \
             patch.object(worker, "drenar", lambda **k: chamadas.append(1)):
            worker.observar()
        self.assertEqual([], chamadas, "o watch extra nao pode drenar")

    def test_watch_sozinho_roda_normalmente(self):
        from unittest.mock import patch
        from builds.identity import worker
        self._sem_pausa()
        chamadas = []

        def _drenar(**kwargs):
            chamadas.append(1)
            raise KeyboardInterrupt        # sai do loop como o Ctrl+C faria

        with patch.object(worker.queue, "ha_worker", lambda: False), \
             patch.object(worker, "_tem_pendente", lambda: True), \
             patch.object(worker, "drenar", _drenar):
            worker.observar()
        self.assertEqual([1], chamadas)

    def test_watch_pausado_espera_sem_drenar(self):
        """Pausado, o watch NAO chama drenar — e nao infla o backoff."""
        from unittest.mock import patch
        from builds.identity import controle, worker
        self._sem_pausa()
        controle.pausar(motivo="conta emprestada")
        chamadas, dormidas = [], []

        def _sleep(segundos):
            dormidas.append(segundos)
            raise KeyboardInterrupt        # um ciclo basta para o contrato

        with patch.object(worker.queue, "ha_worker", lambda: False), \
             patch.object(worker, "drenar", lambda **k: chamadas.append(1)), \
             patch.object(worker.time, "sleep", _sleep):
            worker.observar()
        self.assertEqual([], chamadas, "pausado nao pode drenar")
        self.assertEqual(1, len(dormidas))


# ------------------------------------------------- 18. controle da pipeline
class ControleTests(unittest.TestCase):
    """A ferramenta de video e conta COMPARTILHADA: quando outra pessoa esta
    usando, a pipeline tem que parar de pegar trabalho — sem matar processo
    no meio de um job (foi assim que a generation_00075 ficou pela metade)."""

    def setUp(self):
        from unittest.mock import patch
        from builds.identity import controle
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        alvo = patch.object(controle, "ARQUIVO", Path(self._tmp.name) / "controle.json")
        alvo.start()
        self.addCleanup(alvo.stop)
        self.controle = controle

    def test_comeca_rodando(self):
        estado = self.controle.estado()
        self.assertEqual(self.controle.RODANDO, estado["situacao"])
        self.assertFalse(self.controle.pausado_para("digen"))

    def test_pausar_tudo_bloqueia_todos_os_provedores(self):
        estado = self.controle.pausar(motivo="conta emprestada")
        self.assertEqual(self.controle.PAUSADO, estado["situacao"])
        self.assertIn("conta emprestada", estado["resumo"])
        self.assertTrue(self.controle.pausado_para("digen"))
        self.assertTrue(self.controle.pausado_para("picasso"))

    def test_pausar_so_um_provedor_deixa_o_outro_trabalhando(self):
        self.controle.pausar("digen", motivo="video em uso")
        self.assertTrue(self.controle.pausado_para("digen"))
        self.assertFalse(self.controle.pausado_para("picasso"))

    def test_retomar_libera(self):
        self.controle.pausar("digen")
        self.controle.retomar("digen")
        self.assertFalse(self.controle.pausado_para("digen"))
        self.assertEqual(self.controle.RODANDO, self.controle.estado()["situacao"])

    def test_pausa_com_prazo_vence_sozinha(self):
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch
        self.controle.pausar("digen", "emprestada", minutos=60)
        self.assertTrue(self.controle.pausado_para("digen"))
        depois = datetime.now(timezone.utc) + timedelta(minutes=61)
        with patch.object(self.controle, "_agora", lambda: depois):
            self.assertFalse(self.controle.pausado_para("digen"))
            self.assertEqual(self.controle.RODANDO,
                             self.controle.estado()["situacao"])

    def test_parada_limpa_bloqueia_e_e_consumida(self):
        estado = self.controle.pedir_parada("fim do dia")
        self.assertEqual(self.controle.PARANDO, estado["situacao"])
        self.assertTrue(self.controle.parada_pedida())
        self.assertTrue(self.controle.pausado_para("picasso"))
        self.controle.limpar_parada()
        self.assertFalse(self.controle.parada_pedida())

    def test_a_fila_obedece_a_pausa(self):
        from unittest.mock import patch
        from builds.identity import queue
        job = {"job_id": "g#character", "generation_id": "g", "slot": "character",
               "status": queue.PENDENTE, "attempts": 0, "provider": "picasso",
               "prompt": "x", "depends_on": []}
        # copia a cada leitura: `claim` MUTA o job (pending -> running), e sem
        # ela a segunda chamada nao acharia mais nada pendente.
        with patch.object(queue, "_ler", lambda: [dict(job)]), \
             patch.object(queue, "_gravar", lambda _: None):
            self.assertIsNotNone(queue.claim(3))          # rodando: pega
            self.controle.pausar(motivo="ocupada")
            self.assertIsNone(queue.claim(3))             # pausado: nao pega
            self.assertFalse(queue.tem_reivindicavel(3))
            self.controle.retomar()
            self.assertIsNotNone(queue.claim(3))          # retomado: volta


if __name__ == "__main__":
    unittest.main()
