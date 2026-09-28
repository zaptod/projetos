"""Contratos da timeline v1 (Onda 16C): o palco desenha SO a partir dela.

A timeline so pode substituir o desenho do pygame se duas coisas forem
verdade, e estes testes travam as duas:

1. A sonda NAO muda a luta. O teste antigo do gravador compara o fim (vencedor,
   duracao, HP); aqui a comparacao e um HASH DE ESTADO POR PASSO — corpo,
   timers, status, contadores, o RNG de cada lutador, o mundo, a camera e o
   ``random`` global — com e sem a sonda. Uma sonda que consumisse um unico
   numero aleatorio, ou esvaziasse uma lista, apareceria no passo exato.
2. A timeline diz a verdade: o schema valida, o golpe segue o relogio do motor,
   a ponta da arma cai no alcance da hitbox, o KO e o HP batem com o resultado.
"""

from __future__ import annotations

import hashlib
import os
import random
import shutil
import struct
import subprocess
import tempfile
import unittest
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from neural_fights.data.database import carregar_personagens  # noqa: E402
from neural_fights.recording import timeline, timeline_arquivo  # noqa: E402
from neural_fights.simulation.headless import run_headless_match  # noqa: E402

SEED = 20260821
CENARIO = "Arena Pequena"
RESOLUCAO = (540, 960)
# Desenhar cada passo custa ~4x o motor: o caminho do gravador fica atras do
# mesmo gate dos testes pesados de gravacao.
GATE_PESADO = os.environ.get("NF_RECORDING_GATE") != "1"
# O Godot nao e dependencia da suite: o teste que abre o container nele e
# opcional. NF_GODOT = caminho do executavel de console.
GODOT = os.environ.get("NF_GODOT")


@lru_cache(maxsize=1)
def _lutadores() -> tuple[str, str]:
    personagens = carregar_personagens()
    return personagens[0].nome, personagens[1].nome


def _parametros(**extra) -> dict:
    p1, p2 = _lutadores()
    return {"p1": p1, "p2": p2, "seed": SEED, "cenario": CENARIO,
            "resolucao": RESOLUCAO, "camera_modo": "DIRETOR", **extra}


@lru_cache(maxsize=None)
def _luta(sonda: bool, headless: bool = True, desenhar: bool = False) -> dict:
    return timeline.gravar_timeline(**_parametros(headless=headless, desenhar=desenhar),
                                    sonda=sonda, hashes=True)


def _primeira_divergencia(sem: list, com: list):
    for i, (a, b) in enumerate(zip(sem, com)):
        if a != b:
            return i, a, b
    return None


class SondaNaoMudaALutaTests(unittest.TestCase):
    def test_hash_de_estado_igual_em_todo_passo(self) -> None:
        sem, com = _luta(False)["hashes"], _luta(True)["hashes"]
        self.assertGreater(len(sem), 600, "a luta curta demais nao prova nada")
        self.assertEqual(len(sem), len(com), "a sonda mudou o numero de passos")
        divergencia = _primeira_divergencia(sem, com)
        self.assertIsNone(divergencia, f"a sonda mudou o estado: (passo, sem, com) = {divergencia}")

    def test_vencedor_duracao_e_hp_iguais_ao_motor(self) -> None:
        sem, com = _luta(False)["resultado"], _luta(True)["resultado"]
        chaves = ("vencedor", "duracao_jogo", "duracao_video", "ko_em_video", "passos", "hp_final")
        self.assertEqual({k: sem[k] for k in chaves}, {k: com[k] for k in chaves})
        # E o laco da timeline e o MESMO motor do placar: o runner headless
        # oficial (sem hash e sem sonda) chega no mesmo lugar.
        p1, p2 = _lutadores()
        oficial = run_headless_match(
            {"p1_nome": p1, "p2_nome": p2, "cenario": CENARIO, "best_of": 1,
             "portrait_mode": True, "resolucao": list(RESOLUCAO), "camera_modo": "DIRETOR"},
            fixed_dt=1 / 60, max_duration=120.0, seed=SEED)
        self.assertTrue(oficial.success, oficial.error)
        self.assertEqual(oficial.winner, com["vencedor"])
        self.assertAlmostEqual(oficial.duration, com["duracao_jogo"], delta=1e-3)
        self.assertAlmostEqual(oficial.p1_hp_ratio * 100, com["hp_final"]["p1"], delta=0.01)
        self.assertAlmostEqual(oficial.p2_hp_ratio * 100, com["hp_final"]["p2"], delta=0.01)

    def test_mesma_seed_mesma_timeline(self) -> None:
        de_novo = timeline.gravar_timeline(**_parametros(headless=True), sonda=True)
        self.assertEqual(_luta(True)["timeline"], de_novo["timeline"])

    def test_o_hash_enxerga_o_que_uma_sonda_poderia_estragar(self) -> None:
        """Um hash cego passaria qualquer sonda: ele precisa acusar um
        numero aleatorio consumido e um lutador movido."""
        from neural_fights.simulation.simulacao import Simulador

        p1, p2 = _lutadores()
        timeline._zerar_animador_de_arma()
        sim = Simulador(match_config={"p1_nome": p1, "p2_nome": p2, "cenario": CENARIO,
                                      "best_of": 1, "portrait_mode": True,
                                      "resolucao": list(RESOLUCAO), "camera_modo": "DIRETOR"},
                        headless=True, seed=SEED)
        try:
            for _ in range(30):
                sim.update(1 / 60)
            base = timeline.hash_estado(sim)
            self.assertEqual(base, timeline.hash_estado(sim), "o hash nao e estavel")
            random.random()
            luta, tudo = timeline.hash_estado(sim)
            self.assertEqual(base[0], luta, "o random global nao e estado da LUTA")
            self.assertNotEqual(base[1], tudo, "o hash completo nao viu o random global")
            sim.p1.rng_runtime.random()
            self.assertNotEqual(luta, timeline.hash_estado(sim)[0],
                                "o hash nao viu o RNG do lutador")
            sim.p1.pos[0] += 1e-9
            depois = timeline.hash_estado(sim)[0]
            sim.p1.pos[0] -= 1e-9
            self.assertNotEqual(timeline.hash_estado(sim)[0], depois,
                                "o hash nao viu o lutador mexer 1 nanometro")
        finally:
            sim.close()

    @unittest.skipIf(GATE_PESADO, "gate pesado; ligue com NF_RECORDING_GATE=1")
    def test_no_laco_do_gravador_tambem(self) -> None:
        """O caminho do video: desenhar() a cada passo, a sonda ANTES dele."""
        sem = _luta(False, headless=False, desenhar=True)
        com = _luta(True, headless=False, desenhar=True)
        self.assertEqual(len(sem["hashes"]), len(com["hashes"]))
        self.assertIsNone(_primeira_divergencia(sem["hashes"], com["hashes"]))
        self.assertEqual(sem["resultado"], com["resultado"])


def _gravar_no_gravador(caminho_timeline, max_duracao: float) -> tuple[dict, list]:
    """O gravador DE VERDADE (desenha cada passo, anota o som), com um hash de
    estado por passo tirado logo depois de cada ``update``. O embrulho existe
    so no teste e e o mesmo nos dois lados da comparacao."""
    from unittest import mock

    from neural_fights.recording.fight_recorder import gravar_luta
    from neural_fights.simulation.simulacao import Simulador

    hashes: list = []
    original = Simulador.update

    def update_com_hash(sim, dt):
        original(sim, dt)
        hashes.append(timeline.hash_estado(sim))

    p1, p2 = _lutadores()
    timeline._zerar_animador_de_arma()
    with mock.patch.object(Simulador, "update", update_com_hash):
        resultado = gravar_luta(p1=p1, p2=p2, saida=None, seed=SEED, cenario=CENARIO,
                                resolucao=RESOLUCAO, camera_modo="DIRETOR", hud=False,
                                max_duracao=max_duracao, timeline=caminho_timeline)
    return resultado, hashes


class GravadorComTimelineTests(unittest.TestCase):
    """A sonda LIGADA no ``fight_recorder.gravar_luta`` (Onda 16C), com o
    anotador de som da 16A: 8 s de video bastam para o hash por passo."""

    SEGUNDOS = 8.0

    @classmethod
    def setUpClass(cls) -> None:
        cls._pasta = tempfile.TemporaryDirectory()
        cls.caminho = Path(cls._pasta.name) / "luta.timeline.gcpf"
        cls.com, cls.hashes_com = _gravar_no_gravador(cls.caminho, cls.SEGUNDOS)
        cls.sem, cls.hashes_sem = _gravar_no_gravador(None, cls.SEGUNDOS)
        cls.doc = timeline_arquivo.carregar(cls.caminho)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._pasta.cleanup()

    def test_mesma_luta_com_e_sem_timeline(self) -> None:
        self.assertGreater(len(self.hashes_sem), 400)
        self.assertEqual(len(self.hashes_sem), len(self.hashes_com))
        self.assertIsNone(_primeira_divergencia(self.hashes_sem, self.hashes_com))
        # o som depende do random GLOBAL (variante do grupo): uma sonda que
        # consumisse um numero mudaria esta lista
        for chave in ("eventos_dano", "serie_hp", "serie_plano", "eventos_narrativos",
                      "sons", "metricas_video", "hp_final", "duracao_video"):
            self.assertEqual(self.sem[chave], self.com[chave], chave)
        self.assertNotIn("timeline", self.sem)

    def test_a_timeline_do_gravador_e_valida_e_traz_o_som(self) -> None:
        self.assertEqual(self.com["timeline"], str(self.caminho))
        self.assertNotIn("erro_timeline", self.com)
        self.assertEqual(timeline_arquivo.validar(self.doc), [])
        self.assertEqual(self.doc["n"], len(self.hashes_com))
        self.assertEqual(self.com["timeline_passos"], self.doc["n"])
        self.assertTrue(self.com["sons"], "a luta nao pediu som nenhum")
        self.assertEqual(self.doc["sons"],
                         {"versao": self.com["versao_sons"], "relogio": "video",
                          "itens": self.com["sons"]})

    def test_o_palco_sem_desenhar_ve_a_mesma_luta_e_o_mesmo_som(self) -> None:
        """O palco simula SEM desenhar (4x mais barato): canais, eventos e
        sons precisam ser os do gravador, que desenha."""
        palco = timeline.gravar_timeline(**_parametros(), max_duracao=self.SEGUNDOS)["timeline"]
        self.assertEqual(palco["n"], self.doc["n"])
        self.assertEqual(palco["trilhas"], self.doc["trilhas"])
        self.assertEqual(palco["eventos"], self.doc["eventos"])
        self.assertEqual(palco["sons"], self.doc["sons"])

    @unittest.skipIf(GATE_PESADO, "gate pesado; ligue com NF_RECORDING_GATE=1")
    def test_luta_inteira_no_gravador(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            com, hashes_com = _gravar_no_gravador(Path(pasta) / "t.json", 120.0)
        sem, hashes_sem = _gravar_no_gravador(None, 120.0)
        self.assertEqual(com["motivo"], "knockout")
        self.assertEqual(len(hashes_sem), len(hashes_com))
        self.assertIsNone(_primeira_divergencia(hashes_sem, hashes_com))
        self.assertEqual(sem["sons"], com["sons"])
        self.assertEqual(sem["eventos_dano"], com["eventos_dano"])


class SondaSoLeTests(unittest.TestCase):
    def test_nao_consome_rng_nem_muda_estado_no_proprio_passo(self) -> None:
        """Mesma luta, mesmo passo: chamar on_frame cinco vezes seguidas nao
        pode mexer em nada (nem no random global, nem no RNG do lutador)."""
        from neural_fights.simulation.simulacao import Simulador

        p1, p2 = _lutadores()
        timeline._zerar_animador_de_arma()
        sim = Simulador(match_config={"p1_nome": p1, "p2_nome": p2, "cenario": CENARIO,
                                      "best_of": 1, "portrait_mode": True,
                                      "resolucao": list(RESOLUCAO), "camera_modo": "DIRETOR"},
                        headless=True, seed=SEED)
        try:
            sonda = timeline.SondaTimeline()
            sonda.on_inicio(sim)
            for _ in range(240):
                sim.update(1 / 60)
            colisoes = sim.arena.colisoes_recentes
            conteudo = list(colisoes)
            antes = (timeline.hash_estado(sim), random.getstate(),
                     sim.p1.rng_runtime.getstate(), sim.p2.rng_runtime.getstate())
            for _ in range(5):
                sonda.on_frame(sim)
            depois = (timeline.hash_estado(sim), random.getstate(),
                      sim.p1.rng_runtime.getstate(), sim.p2.rng_runtime.getstate())
            self.assertEqual(antes, depois)
            self.assertIs(colisoes, sim.arena.colisoes_recentes)
            self.assertEqual(conteudo, list(colisoes), "a sonda mexeu em colisoes_recentes")
        finally:
            sim.close()

    def test_nao_desenha_e_tolera_fakes_de_contrato(self) -> None:
        """Simulador e lutadores de mentira: sem metade dos atributos, com
        desenhar() e limpar_colisoes() que explodem se forem chamados."""
        from neural_fights.ai.brain import AIBrain
        from neural_fights.core.entities import Lutador

        def proibido(*_a, **_k):
            raise AssertionError("a sonda chamou um metodo que MUDA o estado")

        cerebro = object.__new__(AIBrain)   # sem __init__: sem motor emocional
        lutador_vazio = object.__new__(Lutador)
        lutador_vazio.brain = cerebro
        colisoes = [(1.0, 2.0, 5.0)]
        arena = SimpleNamespace(colisoes_recentes=colisoes, limpar_colisoes=proibido,
                                obstaculos=[], largura=10.0, altura=10.0)
        lutador_min = SimpleNamespace(pos=[3.0, 4.0], vida=50.0, vida_max=100.0,
                                      dados=SimpleNamespace(nome="Fake", tamanho=1.6))
        sim = SimpleNamespace(p1=lutador_vazio, p2=lutador_min, arena=arena,
                              desenhar=proibido, match_config={})
        sonda = timeline.SondaTimeline()
        sonda.on_inicio(sim)
        for _ in range(3):
            sonda.on_frame(sim)
        doc = sonda.documento()
        self.assertEqual(timeline_arquivo.validar(doc), [])
        self.assertEqual(doc["n"], 3)
        self.assertNotIn("emocoes", vars(cerebro),
                         "a sonda criou o motor emocional lendo brain.humor")
        self.assertEqual(colisoes, [(1.0, 2.0, 5.0)])
        self.assertEqual([e["tipo"] for e in doc["eventos"]], ["parede"],
                         "a colisao vista no passo 0 vira UM evento, nao tres")


class TimelineDizAVerdadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        saida = _luta(True)
        cls.doc = saida["timeline"]
        cls.resultado = saida["resultado"]

    def test_schema_valido_e_um_valor_por_passo(self) -> None:
        self.assertEqual(timeline_arquivo.validar(self.doc), [])
        self.assertEqual(self.doc["versao"], timeline.VERSAO)
        self.assertEqual(self.doc["n"], self.resultado["passos"])
        self.assertAlmostEqual(self.doc["duracao"], self.doc["n"] / 60, places=4)
        # o quadro k do video de 30 fps e o passo 2k: a timeline cobre o video
        self.assertEqual(self.resultado["passos_por_quadro"], 2)
        self.assertGreaterEqual(self.doc["n"], 2 * (self.resultado["quadros_video"] - 1) + 1)

    def test_ko_e_hp_batem_com_o_resultado(self) -> None:
        kos = [e for e in self.doc["eventos"] if e["tipo"] == "ko"]
        self.assertEqual(len(kos), 1)
        fim = self.doc["trilhas"]["global"]["fim"]
        self.assertEqual(kos[0]["i"], fim.index(1), "o KO nao e o primeiro passo com fim=1")
        self.assertEqual(kos[0]["vencedor"], self.resultado["vencedor_slot"])
        for slot in ("p1", "p2"):
            self.assertAlmostEqual(self.doc["trilhas"]["lutadores"][slot]["hp"][-1] * 100,
                                   self.resultado["hp_final"][slot], delta=0.1)

    def test_acertos_derrubam_o_hp_de_quem_apanha(self) -> None:
        lutadores = self.doc["trilhas"]["lutadores"]
        acertos = [e for e in self.doc["eventos"] if e["tipo"] == "acerto"]
        self.assertTrue(acertos, "nenhum acerto numa luta inteira")
        for evento in acertos:
            hp = lutadores[evento["alvo"]]["hp"]
            i = evento["i"]
            # O canal tem 3 casas: golpe menor que 0,1% da vida nao aparece
            # nele, entao a regra e "nao sobe" + o dano do evento positivo.
            self.assertLessEqual(hp[i], hp[i - 1] if i else 1.0, evento)
            self.assertGreater(evento["dano"], 0.0, evento)
            if evento["dano_pct"] > 0.0011:
                self.assertLess(hp[i], hp[i - 1] if i else 1.0, evento)
            self.assertIn(evento["tier"], timeline.TIERS)
            self.assertNotEqual(evento["alvo"], evento["autor"])
        self.assertEqual(sum(1 for e in self.doc["eventos"] if e["tipo"] == "primeiro_sangue"), 1)

    def test_fases_do_golpe_seguem_o_relogio_do_motor(self) -> None:
        cabecalhos = {c["slot"]: c for c in self.doc["lutadores"]}
        fases = timeline.FASES
        golpes = 0
        for slot, canais in self.doc["trilhas"]["lutadores"].items():
            perfil = (cabecalhos[slot].get("arma") or {}).get("perfil_golpe") or {}
            ultimo = {}
            for i, fase in enumerate(canais["golpe_fase"]):
                if not fase:
                    continue
                golpes += 1
                self.assertAlmostEqual(canais["golpe_d"][i], perfil[fases[fase]], places=3)
                self.assertTrue(0.0 <= canais["golpe_p"][i] <= 1.0)
                ident = canais["golpe_id"][i]
                self.assertGreaterEqual(fase, ultimo.get(ident, 0),
                                        f"{slot} passo {i}: a fase voltou dentro do golpe {ident}")
                ultimo[ident] = fase
        self.assertGreater(golpes, 0, "ninguem golpeou a luta inteira")

    def test_ponta_da_arma_no_alcance_da_hitbox(self) -> None:
        """Geometria honesta na timeline real: sem lunge, a ponta de uma arma
        de lamina fica a ``alcance_m`` do centro (o alcance que a hitbox usa)."""
        lamina = {"Reta", "Dupla", "Transformável", "Transformavel"}
        conferidos = 0
        for cabecalho in self.doc["lutadores"]:
            arma = cabecalho.get("arma") or {}
            if arma.get("tipo") not in lamina:
                continue
            canais = self.doc["trilhas"]["lutadores"][cabecalho["slot"]]
            for i in range(self.doc["n"]):
                if canais["arma_lunge"][i] != 0.0 or canais["flags"][i] & 2:
                    continue
                dx = canais["arma_px"][i] - canais["x"][i]
                dy = canais["arma_py"][i] - canais["y"][i]
                self.assertAlmostEqual((dx * dx + dy * dy) ** 0.5, arma["alcance_m"], delta=3e-3)
                conferidos += 1
        if not conferidos:
            self.skipTest("nenhum dos dois lutadores desta luta usa arma de lamina")


class GeometriaEConstantesTests(unittest.TestCase):
    def test_ponta_igual_ao_alcance_da_hitbox_por_tipo(self) -> None:
        from neural_fights.core.hitbox import PPM, get_hitbox_profile, sistema_hitbox
        from neural_fights.simulation.simulacao import Simulador

        for tipo in ("Reta", "Dupla", "Transformável"):
            with self.subTest(tipo=tipo):
                arma = SimpleNamespace(tipo=tipo, comp_cabo=20, comp_lamina=40,
                                       largura=30, forma_atual=1)
                lutador = SimpleNamespace(
                    pos=[5.0, 6.0], angulo_arma_visual=33.0, angulo_olhar=33.0,
                    atacando=False, fator_escala=1.0,
                    dados=SimpleNamespace(nome="x", tamanho=1.7, arma_obj=arma))
                hitbox = sistema_hitbox.calcular_hitbox_arma(lutador)
                gx, gy, px, py, _l = timeline.geometria_da_arma(
                    5.0, 6.0, 33.0, 1.7 / 2, tipo, Simulador.GRIP_PROFILES,
                    get_hitbox_profile(tipo)["range_mult"])
                alcance = ((px - 5.0) ** 2 + (py - 6.0) ** 2) ** 0.5
                self.assertAlmostEqual(alcance, hitbox.alcance / PPM, places=6)
                # a ponta esta NA linha da hitbox parada (mesma direcao)
                self.assertAlmostEqual(px * PPM, hitbox.pontos[1][0], places=4)
                self.assertAlmostEqual(py * PPM, hitbox.pontos[1][1], places=4)

    def test_constantes_espelham_o_motor(self) -> None:
        from neural_fights.effects.character_flair import EXPRESSOES
        from neural_fights.effects.weapon_animations import AttackPhase
        from neural_fights.recording import fight_recorder
        from neural_fights.simulation.simulacao import Simulador
        from neural_fights.utils import config

        self.assertEqual(timeline.EXPRESSOES, tuple(EXPRESSOES))
        self.assertEqual(len(timeline.EXPRESSOES), 24)
        self.assertEqual(timeline.FASES[1:], tuple(fase.value for fase in AttackPhase))
        self.assertEqual(timeline.GRIP_PROFILES_PADRAO, Simulador.GRIP_PROFILES)
        self.assertEqual(timeline.HZ, config.FPS)
        self.assertEqual(timeline.PPM, config.PPM)
        self.assertEqual(timeline.IGNORAR_LIDERANCA_ATE, fight_recorder.IGNORAR_LIDERANCA_ATE)
        self.assertEqual(timeline.HISTERESE_LIDERANCA, fight_recorder.HISTERESE_LIDERANCA)
        self.assertEqual(timeline.PASSO_LIDERANCA, fight_recorder.PASSO_SERIE_HP)

    def test_fase_no_tempo_e_a_conta_do_animador(self) -> None:
        from neural_fights.effects.weapon_animations import WEAPON_PROFILES, WeaponAnimator

        animador = WeaponAnimator()
        for perfil in WEAPON_PROFILES.values():
            for passo in range(0, 80):
                t = passo * 0.0125
                estado = SimpleNamespace(attack_timer=t)
                fase, progresso = animador._get_phase(estado, perfil)
                indice, meu_progresso, _d = timeline.fase_no_tempo(t, perfil)
                self.assertEqual(timeline.FASES[indice], fase.value)
                self.assertAlmostEqual(meu_progresso, min(1.0, progresso), places=9)


class ArquivoTests(unittest.TestCase):
    DOC = {"formato": timeline.FORMATO, "versao": 1, "nome": "Sábia", "x": [1.5, 2.25] * 700}

    def test_gcpf_ida_e_volta_nos_tres_modos(self) -> None:
        dados = timeline_arquivo.para_bytes(self.DOC)
        for modo in ("zstd", "deflate", "gzip"):
            with self.subTest(modo=modo):
                arquivo = timeline_arquivo.escrever_gcpf(dados, modo, bloco=1000)
                self.assertEqual(arquivo[:4], b"GCPF")
                self.assertEqual(arquivo[-4:], b"GCPF")
                modo_id, bloco, total = struct.unpack_from("<III", arquivo, 4)
                self.assertEqual((modo_id, bloco, total),
                                 (timeline_arquivo.MODOS[modo], 1000, len(dados)))
                self.assertEqual(timeline_arquivo.ler_gcpf(arquivo), dados)

    def test_gcpf_com_total_multiplo_do_bloco(self) -> None:
        """A conta do Godot e ``total // bloco + 1`` blocos: com o total
        multiplo do bloco o ultimo existe e e VAZIO, e a tabela o declara."""
        dados = b"x" * 2048
        arquivo = timeline_arquivo.escrever_gcpf(dados, "deflate", bloco=1024)
        tamanhos = struct.unpack_from("<3I", arquivo, 16)
        self.assertEqual(len(tamanhos), 3)
        self.assertEqual(16 + 12 + sum(tamanhos) + 4, len(arquivo))
        self.assertEqual(timeline_arquivo.ler_gcpf(arquivo), dados)

    def test_salvar_e_carregar(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            for compressao in (None, "zstd", "gzip"):
                caminho = Path(pasta) / f"t_{compressao}.timeline"
                timeline_arquivo.salvar(self.DOC, caminho, compressao=compressao)
                self.assertEqual(timeline_arquivo.carregar(caminho), self.DOC)

    def test_remapeamento_e_o_corte_de_tedio(self) -> None:
        sonda = timeline.SondaTimeline()
        sonda.definir_remapeamento([(0.0, 5.6), (7.3, 13.77), (21.07, 2.0, 0.5)])
        remap = sonda.remapeamento
        mapa = timeline_arquivo.tempo_no_clipe
        volta = timeline_arquivo.tempo_na_gravacao
        self.assertEqual(remap["trechos"][0], [0.0, 5.6, 1.0])
        self.assertAlmostEqual(mapa(remap, 3.0), 3.0)
        self.assertIsNone(mapa(remap, 6.0), "o que caiu no corte nao aparece")
        self.assertAlmostEqual(mapa(remap, 7.3), 5.6)
        self.assertAlmostEqual(mapa(remap, 22.07), 5.6 + 13.77 + 2.0, places=6)
        self.assertAlmostEqual(timeline_arquivo.duracao_do_clipe(remap, 0.0),
                               5.6 + 13.77 + 4.0, places=6)
        for t_clipe in (0.0, 2.5, 5.6, 9.0, 19.37, 20.0, 23.37):
            t = volta(remap, t_clipe)
            self.assertAlmostEqual(mapa(remap, t), t_clipe, places=6)

    @unittest.skipUnless(GODOT and Path(GODOT).is_file(), "defina NF_GODOT com o Godot de console")
    def test_godot_abre_o_container_nativo(self) -> None:
        """O ``FileAccess.open_compressed`` do Godot le o que escrevemos."""
        leitor = (
            "extends SceneTree\n"
            "func _init():\n"
            "\tvar a = OS.get_cmdline_user_args()\n"
            "\tvar f = FileAccess.open_compressed(a[0], FileAccess.READ, int(a[1]))\n"
            "\tif f == null:\n"
            "\t\tprint('ERRO ', FileAccess.get_open_error())\n"
            "\t\tquit(2)\n"
            "\t\treturn\n"
            "\tvar texto = f.get_as_text()\n"
            "\tvar doc = JSON.parse_string(texto)\n"
            "\tprint('MD5=', texto.md5_text(), ' NOME=', doc['nome'])\n"
            "\tquit(0)\n"
        )
        dados = timeline_arquivo.para_bytes(self.DOC)
        esperado = hashlib.md5(dados).hexdigest()
        with tempfile.TemporaryDirectory() as pasta:
            projeto = Path(pasta)
            (projeto / "project.godot").write_text("config_version=5\n", encoding="utf-8")
            (projeto / "ler.gd").write_text(leitor, encoding="utf-8")
            for modo in ("zstd", "deflate", "gzip"):
                with self.subTest(modo=modo):
                    arquivo = projeto / f"t.{modo}.gcpf"
                    timeline_arquivo.salvar(self.DOC, arquivo, compressao=modo)
                    processo = subprocess.run(
                        [GODOT, "--headless", "--path", str(projeto), "--script", "res://ler.gd",
                         "--", str(arquivo), str(timeline_arquivo.MODOS[modo])],
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        timeout=120)
                    self.assertIn(f"MD5={esperado}", processo.stdout, processo.stdout + processo.stderr)
                    self.assertIn("NOME=Sábia", processo.stdout)
            shutil.rmtree(projeto / ".godot", ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
