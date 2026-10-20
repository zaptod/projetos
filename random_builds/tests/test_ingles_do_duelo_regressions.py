# -*- coding: utf-8 -*-
"""O duelo fala INGLES com o publico (decisao geral/canal-em-ingles, 20/10/2026).

A traducao e um mapa explicito (`builds/publicar/ingles.py`), nao um LLM. Estes
testes FALHAM ALTO quando aparece algo sem traducao:

- estilo de arma, classe, elemento (catalogo do motor) e rotulo do plano da IA;
- callout do `editing.json` (mesma quantidade de modelos, mesma ordem);
- o banco vivo, quando da para le-lo (arma ou classe nova que a roleta criou);
- e o que a edicao do duelo manda desenhar: nenhum texto em portugues na tela,
  fora os nomes proprios.

Tambem: o texto que o JOGO desenha no clipe (plano sob o lutador, "CRÍTICO!")
vai trocado pelo gravador so no duelo.
"""
from __future__ import annotations

import inspect
import json
import os
import random
import re
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from builds.content.caption_generator import CaptionGenerator  # noqa: E402
from builds.generation.session_generator import load_config  # noqa: E402
from builds.publicar import catalogo, confronto, ingles  # noqa: E402
from builds.tournament.duelo import DueloTimelineBuilder  # noqa: E402

ACENTOS = set("áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ")
# Palavras portuguesas que ja apareceram na tela do duelo: nenhuma pode voltar.
PALAVRAS_PT = ("PRESSÃO", "PRESSAO", "NOCAUTE", "ACABOU", "VIROU", "ESQUIVOU",
               "SEGUIDAS", "REVANCHE", "TITULO EM JOGO", "Decisao", "Necromante",
               "Feiticeiro", "Guerreiro", "QUEBRAR", "PAREDE", "PRIMEIRO")


def _em_ingles(texto: str) -> bool:
    return not (set(str(texto)) & ACENTOS) and not any(
        p.casefold() in str(texto).casefold() for p in PALAVRAS_PT)


class MapaCompletoTests(unittest.TestCase):

    def test_toda_arma_do_catalogo_tem_traducao(self):
        from neural_fights.models.constants import TIPOS_ARMA
        estilos = [e for t in TIPOS_ARMA.values() for e in t.get("estilos", [])]
        self.assertGreater(len(estilos), 40)
        faltam = [e for e in estilos if e not in ingles.ARMAS]
        self.assertEqual([], faltam, "estilo de arma sem traducao em ingles.ARMAS")

    def test_toda_classe_do_catalogo_tem_traducao(self):
        from neural_fights.models.constants import CLASSES_DATA
        faltam = [c for c in CLASSES_DATA if c.split("(")[0].strip() not in ingles.CLASSES]
        self.assertEqual([], faltam, "classe sem traducao em ingles.CLASSES")

    def test_todo_elemento_de_arma_tem_traducao(self):
        from neural_fights.models.constants import ENCANTAMENTOS
        self.assertEqual([], [e for e in ENCANTAMENTOS if e not in ingles.ELEMENTOS])

    def test_todo_rotulo_de_plano_tem_traducao(self):
        from neural_fights.ai.plano_de_luta import DEFINICOES
        rotulos = {d.rotulo for d in DEFINICOES.values()}
        self.assertGreater(len(rotulos), 8)
        self.assertEqual(set(), rotulos - set(ingles.PLANOS))

    def test_todo_callout_do_config_tem_o_par_em_ingles(self):
        textos = (load_config("editing.json").get("fight_callouts") or {}).get("textos") or {}
        self.assertTrue(textos)
        for tipo, modelos in textos.items():
            with self.subTest(tipo=tipo):
                self.assertIn(tipo, ingles.CALLOUTS)
                self.assertEqual(len(modelos), len(ingles.CALLOUTS[tipo]))
                for pt, en in zip(modelos, ingles.CALLOUTS[tipo]):
                    # os marcadores andam juntos
                    self.assertEqual("{N}" in pt, "{N}" in en, (pt, en))
                    self.assertEqual("{ROTULO}" in pt, "{ROTULO}" in en, (pt, en))

    def test_toda_traducao_e_ingles(self):
        for mapa in (ingles.ARMAS, ingles.CLASSES, ingles.ELEMENTOS, ingles.PLANOS,
                     ingles.KO, ingles.TELA_DO_JOGO):
            for pt, en in mapa.items():
                with self.subTest(pt=pt):
                    self.assertTrue(en and _em_ingles(en), en)
        for lista in ingles.CALLOUTS.values():
            for en in lista:
                self.assertTrue(_em_ingles(en), en)

    def test_o_banco_vivo_tambem_traduz(self):
        """Arma ou classe NOVA que a roleta pos no banco: sem traducao, o
        titulo sairia com a classe no lugar da arma (ou em portugues)."""
        try:
            from builds.nf_bridge import loader as nf
            armas, personagens = nf.database.carregar_database()
        except Exception as erro:                              # noqa: BLE001
            self.skipTest(f"banco ilegivel aqui: {erro}")
        if not armas or not personagens:
            self.skipTest("banco vazio (runtime descartavel)")
        self.assertEqual(set(), {a.get("estilo") for a in armas} - set(ingles.ARMAS))
        self.assertEqual(set(), {a.get("afinidade_elemento") for a in armas
                                 if a.get("afinidade_elemento")} - set(ingles.ELEMENTOS))
        self.assertEqual(set(), {str(p.get("classe")).split("(")[0].strip()
                                 for p in personagens} - set(ingles.CLASSES))


EPITETO_PT = r" (o|a|do|da|das|dos|de) \S.*$"


class EpitetosTests(unittest.TestCase):
    """"Helga o Protetor" -> "Helga the Protector", so na exibicao."""

    def test_todo_titulo_do_gerador_tem_traducao(self):
        from neural_fights.tools.gerador_database import TITULOS
        faltam = [t for t in TITULOS if t and t not in ingles.EPITETOS]
        self.assertEqual([], faltam, "epiteto do gerador sem traducao em ingles.EPITETOS")

    def test_todo_nome_do_banco_vivo_sai_sem_epiteto_portugues(self):
        import re
        try:
            from builds.nf_bridge import loader as nf
            _, personagens = nf.database.carregar_database()
        except Exception as erro:                              # noqa: BLE001
            self.skipTest(f"banco ilegivel aqui: {erro}")
        if not personagens:
            self.skipTest("banco vazio (runtime descartavel)")
        sobrou = [p["nome"] for p in personagens
                  if re.search(EPITETO_PT, ingles.nome(p["nome"]))]
        self.assertEqual([], sobrou, "nome do banco com epiteto sem traducao")

    def test_o_nome_proprio_fica_e_o_desempate_sobrevive(self):
        self.assertEqual("Helga the Protector", ingles.nome("Helga o Protetor"))
        self.assertEqual("Elara the Legendary", ingles.nome("Elara o Lendário"))
        self.assertEqual("Maximus the Just", ingles.nome("Maximus a Justa"))
        self.assertEqual("Beatrix of the Shadows", ingles.nome("Beatrix das Sombras"))
        self.assertEqual("Helga the Protector #2", ingles.nome("Helga o Protetor #2"))
        self.assertEqual("Kuro #2", ingles.nome("Kuro #2"))
        self.assertEqual("Vitinho Da Massa", ingles.nome("Vitinho Da Massa"))
        # caso zero: sem o mapa o epiteto portugues seria pego pela guarda
        import re
        self.assertTrue(re.search(EPITETO_PT, "Helga o Protetor"))

    def test_a_descricao_usa_o_nome_em_ingles(self):
        config = catalogo.carregar_config()
        campos = catalogo.campos_do_confronto(
            {"p1": "Helga o Protetor", "p2": "Maximus a Justa",
             "confronto": {"p1": "Shuriken", "p2": "Sentinels"}})
        texto = catalogo._formatar(config["descricoes"][catalogo.DUELO], campos)
        self.assertIn("Helga the Protector vs Maximus the Just", texto)
        self.assertNotIn("Protetor", texto)

    def test_o_mapa_do_jogo_leva_os_nomes_do_duelo(self):
        mapa = ingles.tela_do_jogo("Helga o Protetor", "Kuro #2")
        self.assertEqual("Helga the Protector", mapa["Helga o Protetor"])
        self.assertNotIn("Kuro #2", mapa)
        self.assertEqual("PRESSURE", mapa["PRESSÃO"])

    def test_o_nome_sobre_o_lutador_traduzido_nao_e_cortado(self):
        from neural_fights.simulation.simulacao import Simulador
        lutador = SimpleNamespace(dados=SimpleNamespace(nome="Celeste a Impiedosa"))
        com = SimpleNamespace(match_config={
            "textos_da_tela": ingles.tela_do_jogo("Celeste a Impiedosa")})
        self.assertEqual("Celeste the Merciless", Simulador._nome_na_tela(com, lutador))
        # caso zero: sem o mapa, o nome de sempre e o corte de sempre (18)
        sem = SimpleNamespace(match_config={})
        self.assertEqual("Celeste a Impiedos", Simulador._nome_na_tela(sem, lutador))
        # no duelo (com mapa) o nome sem epiteto tambem vai a 24 ("Nyxaris
        # Cinzamorda" era o corte em 18; conferente, 20/10)
        nyx = SimpleNamespace(dados=SimpleNamespace(nome="Nyxaris Cinzamordaca"))
        self.assertEqual("Nyxaris Cinzamordaca", Simulador._nome_na_tela(com, nyx))

    def test_o_duelo_grava_com_os_nomes_traduzidos(self):
        from builds.tournament import runner
        self.assertEqual("Helga the Protector",
                         runner._textos_da_tela("duelo", "Helga o Protetor", "X")
                         ["Helga o Protetor"])
        self.assertIn("_textos_da_tela(origem, p1, p2)", inspect.getsource(runner))


class TituloQueFalhaAltoTests(unittest.TestCase):
    """Campo sumido do modelo daria o MESMO titulo a todo par: a guarda de
    titulo repetido fecharia a fila sem erro nenhum."""

    def test_o_rodizio_levanta_com_campo_que_nao_existe(self):
        from builds.arena import rodizio
        with self.assertRaises(catalogo.TituloIncompleto):
            rodizio.titulo_do_par("A", "B", {"titulos": {"duelo": "{lado1} VS {lado3}"}})
        # caso zero: o modelo de verdade monta sem erro
        self.assertEqual("A VS B — who wins?",
                         rodizio.titulo_do_par("A", "B", catalogo.carregar_config()))

    def test_o_catalogo_segura_o_duelo_com_titulo_incompleto(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(catalogo, "OUTPUTS", Path(tmp)):
            pasta = Path(tmp) / "duelo_00001"
            pasta.mkdir()
            (pasta / "fight.json").write_text(json.dumps({"luta": {
                "p1": "A", "p2": "B", "confronto": {"p1": "Katana", "p2": "Sai"}}}),
                encoding="utf-8")
            (pasta / "edit_plan.json").write_text(json.dumps({"total_duration": 30.0}),
                                                  encoding="utf-8")
            (pasta / "final_celular.mp4").write_bytes(b"\0" * (catalogo.BYTES_MINIMOS + 1))
            config = dict(catalogo.carregar_config(), pasta_export=str(Path(tmp) / "_p"))
            config["titulos"] = dict(config["titulos"], duelo="{lado1} VS {lado3}")
            video = next(v for v in catalogo.listar(config) if v.origem == catalogo.DUELO)
            self.assertFalse(video.pronto)
            self.assertIn("lado3", video.pendencias[0])
            with self.assertRaises(catalogo.TituloIncompleto):
                catalogo.titulo_do_duelo({"p1": "A", "p2": "B"}, config)

    def test_todo_campo_do_titulo_do_duelo_existe(self):
        modelo = catalogo.modelo_do_titulo_do_duelo()
        campos = catalogo.campos_do_confronto({"p1": "A", "p2": "B"})
        self.assertEqual([], catalogo.campos_faltando(modelo, campos))


class TraducoesTests(unittest.TestCase):

    def test_callout_volta_pelo_modelo_de_mesmo_indice(self):
        textos = load_config("editing.json")["fight_callouts"]["textos"]
        self.assertEqual("COMBO x4", ingles.callout("COMBO x4", "combo", textos["combo"], n=4))
        self.assertEqual("4 HITS", ingles.callout("4 HITS", "combo", textos["combo"], n=4))
        self.assertEqual("IT'S OVER!", ingles.callout("ACABOU", "ko", textos["ko"]))
        self.assertEqual("SLAMMED INTO THE WALL",
                         ingles.callout("COMEU PAREDE", "wall_splat", textos["wall_splat"]))
        self.assertEqual("PLAN: GUARD BREAK", ingles.callout(
            "PLANO: QUEBRAR GUARDA", "plano", textos["plano"], rotulo_pt="QUEBRAR GUARDA"))
        # caso zero: texto que nenhum modelo gerou volta como veio
        self.assertEqual("ALGO NOVO", ingles.callout("ALGO NOVO", "ko", textos["ko"]))

    def test_o_cartao_final_concorda_com_o_rotulo(self):
        self.assertEqual("SHURIKEN WINS!", ingles.vence("Shuriken"))
        self.assertEqual("SENTINELS WIN!", ingles.vence("Sentinels"))
        self.assertEqual("TACTICAL KNIVES WIN!", ingles.vence("Tactical Knives"))
        self.assertEqual("LONGSWORD NINJA WINS!", ingles.vence("Longsword Ninja"))
        self.assertEqual("ALDRIC'S LONGSWORD WINS!", ingles.vence("Aldric's Longsword"))
        # todo estilo traduzido sai com um dos dois finais
        for en in ingles.ARMAS.values():
            self.assertRegex(ingles.vence(en), r" WINS?!$")

    def test_cartel_selo_ko_e_classe(self):
        self.assertEqual("12W-3L", ingles.cartel("12V-3D"))
        self.assertEqual("REMATCH", ingles.selo("REVANCHE"))
        self.assertEqual("TITLE ON THE LINE", ingles.selo("TITULO EM JOGO"))
        self.assertEqual("Kuro IS ON A 4-WIN STREAK",
                         ingles.selo("Kuro VEM DE 4 SEGUIDAS", "Kuro", 4))
        self.assertEqual("HP DECISION", ingles.ko("Decisao por HP"))
        self.assertEqual("Necromancer", ingles.classe("Necromante (Trevas)"))

    def test_arma_sem_traducao_cai_na_classe_em_ingles(self):
        confronto.esquecer_armas()
        with mock.patch.object(confronto, "_carregar_armas", return_value={
                "X": {"nome": "X", "estilo": "Arma Que Nao Existe"}}):
            l1, _ = confronto.rotulos({"nome_arma": "X", "classe": "Monge (Chi)"},
                                      {"nome_arma": "X", "classe": "Mago (Arcano)"})
        confronto.esquecer_armas()
        self.assertEqual("Monk", l1)


class TelaDoDueloEmInglesTests(unittest.TestCase):
    """O que a edicao manda desenhar, de uma luta com tudo em portugues."""

    def _fight(self):
        luta = {"p1": "Aldric o Lendário", "p2": "Elowen a Impiedosa",
                "vencedor": "Elowen a Impiedosa", "ko_type": "Decisao por HP",
                "p1_ficha": {"nome": "Aldric o Lendário", "nome_arma": "A1",
                             "classe": "Necromante (Trevas)"},
                "p2_ficha": {"nome": "Elowen a Impiedosa", "nome_arma": "A2",
                             "classe": "Feiticeiro (Caos)"},
                "p1_cartel": "4V-2D", "p2_cartel": "4V-0D",
                "p2_recorde": {"vitorias": 4, "derrotas": 0, "sequencia": 4},
                "serie_hp": [[0.0, 100.0, 100.0], [5.0, 40.0, 70.0]],
                "serie_plano": [[0.0, "PRESSÃO", 0.2, "QUEBRAR GUARDA", 0.5],
                                [3.0, "TROCAÇÃO", 0.1, "PRA PAREDE", 0.3]],
                "eventos_narrativos": [
                    {"t": 0.4, "tipo": "primeiro_sangue", "slot": "p1"},
                    {"t": 2.0, "tipo": "combo", "slot": "p2", "n": 4},
                    {"t": 4.0, "tipo": "wall_splat", "slot": "p1"},
                    {"t": 6.0, "tipo": "virada", "slot": "p2"},
                    {"t": 9.0, "tipo": "ko", "slot": "p2"}],
                "clipes": {"celular": {"path": "x.mp4", "duracao": 12.0}},
                "duracao": 10.0}
        return {"seed": 7, "luta": luta, "lutas": [json.loads(json.dumps(luta))]}

    def test_nenhum_texto_portugues_na_tela(self):
        confronto.esquecer_armas()
        with mock.patch.object(confronto, "_carregar_armas", return_value={
                "A1": {"nome": "A1", "estilo": "Facas Táticas"},
                "A2": {"nome": "A2", "estilo": "Espada Longa"}}):
            editing = load_config("editing.json")
            captions = CaptionGenerator(load_config("captions.json"), load_config("frases.json"))
            fight = self._fight()
            evento = DueloTimelineBuilder(editing, captions).build(
                random.Random(3), fight)["events"][0]
        confronto.esquecer_armas()
        nomes = {"Aldric", "Elowen"}   # so o nome proprio fica
        ident = evento["identidade"]
        na_tela = [evento["confronto"]["p1"], evento["confronto"]["p2"],
                   ident["pergunta"], ident.get("selo", "")]
        for slot in ("p1", "p2"):
            na_tela += [ident[slot]["classe"], ident[slot]["cartel"]]
        na_tela += [ident["p1"]["nome"], ident["p2"]["nome"], evento["veredito"]["vencedor"]]
        na_tela += [evento["veredito"]["ko_type"], evento["veredito"]["cartel_apos"]]
        na_tela += [c["texto"] for c in evento.get("callouts") or []]
        for amostra in evento["hud"]["serie_plano"]:
            na_tela += [amostra[1], amostra[3]]
        self.assertGreater(len(evento.get("callouts") or []), 0)
        for texto in na_tela:
            limpo = texto
            for nome in nomes:
                limpo = limpo.replace(nome, "")
            with self.subTest(texto=texto):
                self.assertTrue(_em_ingles(limpo), texto)
                self.assertIsNone(re.search(EPITETO_PT, texto), texto)
        self.assertEqual("Aldric the Legendary", ident["p1"]["nome"])
        self.assertEqual("Elowen the Merciless", evento["veredito"]["vencedor"])
        self.assertIn("Elowen the Merciless", ident.get("selo", ""))
        self.assertEqual("Aldric o Lendário", fight["luta"]["p1"])
        self.assertEqual("WHO WINS?", ident["pergunta"])
        self.assertEqual(("Tactical Knives", "Longsword"),
                         (evento["confronto"]["p1"], evento["confronto"]["p2"]))
        # o fight.json (portugues, para o motor) nao foi tocado
        self.assertEqual("PRESSÃO", fight["luta"]["serie_plano"][0][1])
        self.assertEqual("en", evento["idioma"])

    def test_titulo_descricao_e_hashtags_do_duelo_em_ingles(self):
        config = catalogo.carregar_config()
        for bloco in ("titulos", "descricoes"):
            with self.subTest(bloco=bloco):
                self.assertTrue(_em_ingles(config[bloco][catalogo.DUELO]))
        for tag in config["hashtags"][catalogo.DUELO]:
            self.assertTrue(_em_ingles(tag), tag)
        self.assertIn("#shorts", config["hashtags"][catalogo.DUELO])
        self.assertNotIn("#luta", config["hashtags"][catalogo.DUELO])


# Funcoes do Simulador que NAO vao ao video do duelo: o gravador desliga o HUD
# do jogo (--sem-hud), roda em modo_live (sem o cartaz de vitoria nem o
# placar de serie), sem debug, sem analise e sem pausa.
NAO_VAI_AO_VIDEO = {"desenhar_hitbox_debug", "desenhar_painel_debug", "desenhar_barras",
                    "_renderizar_texto_ajustado", "desenhar_placar_serie",
                    "desenhar_controles", "desenhar_analise", "desenhar_pause",
                    "desenhar_vitoria"}
# Revisados a mao: nao sao palavras.
REVISADOS = {"vis['glifo']": "simbolo de status (☠ ▽ ✹ ≈), core/status_runtime.py"}
_GANCHOS = ("_texto_da_tela", "_nome_na_tela")


def _sem_letras(no) -> bool:
    import ast
    if isinstance(no, ast.Constant) and isinstance(no.value, str):
        return not any(c.isalpha() for c in no.value)
    if isinstance(no, ast.JoinedStr):
        return all(not any(c.isalpha() and c != "x" for c in str(p.value))
                   for p in no.values if isinstance(p, ast.Constant))
    return False


def _pelo_mapa(no) -> bool:
    import ast
    return any(isinstance(n, ast.Call) and
               (getattr(n.func, "attr", None) or getattr(n.func, "id", None)) in _GANCHOS
               for n in ast.walk(no))


def _renders_sem_mapa(fonte: str) -> list[str]:
    """Cada `.render(` de funcao que vai ao video cujo texto nao passa pelo
    mapa de exibicao: 'linha N: expressao'."""
    import ast
    arvore = ast.parse(fonte)
    problemas = []
    for funcao in ast.walk(arvore):
        if not isinstance(funcao, ast.FunctionDef) or funcao.name in NAO_VAI_AO_VIDEO:
            continue
        atribuicoes = {}
        for no in ast.walk(funcao):
            if isinstance(no, ast.Assign):
                for alvo in no.targets:
                    if isinstance(alvo, ast.Name):
                        atribuicoes.setdefault(alvo.id, []).append(no)
        for no in ast.walk(funcao):
            if not (isinstance(no, ast.Call) and getattr(no.func, "attr", None) == "render"
                    and no.args):
                continue
            arg = no.args[0]
            while (isinstance(arg, ast.Call) and getattr(arg.func, "id", None) == "str"
                   and arg.args):
                arg = arg.args[0]
            texto = ast.unparse(arg)
            ok = _pelo_mapa(arg) or _sem_letras(arg) or texto in REVISADOS
            if not ok and isinstance(arg, ast.Name):
                antes = [a for a in atribuicoes.get(arg.id, []) if a.lineno < no.lineno]
                ok = bool(antes) and (_pelo_mapa(antes[-1].value) or _sem_letras(antes[-1].value))
            if not ok:
                problemas.append(f"linha {no.lineno} ({funcao.name}): {texto}")
    return problemas


class SkillsForaDaTelaTests(unittest.TestCase):
    """Nome de skill (portugues no banco: "Fúria Giratória") nao aparece no
    duelo. Se um dia aparecer, estes testes acusam."""

    KIT = ["Repulsão", "Fúria Giratória", "Velocidade Arcana", "Determinação"]

    def test_todo_texto_que_o_jogo_desenha_e_ingles_ou_tem_traducao(self):
        """Varre o fonte do Simulador: cada texto LITERAL que vai para a tela
        pelo `_push_texto` e ingles ou esta no `TELA_DO_JOGO`."""
        import re
        from pathlib import Path
        fonte = (Path(__file__).resolve().parents[2] / "neural_fights" / "simulation"
                 / "simulacao.py").read_text(encoding="utf-8")
        literais = set(re.findall(r'_push_texto\([^()]*?,\s*[^,()]*?,\s*"([^"]+)"', fonte))
        literais |= set(re.findall(r'_push_texto\(\s*\n?[^"]*?\n\s*"([^"]+)",', fonte))
        literais |= set(re.findall(r'texto = "([^"]+)"', fonte))
        self.assertIn("CRÍTICO!", literais)              # a varredura enxerga o caso
        faltam = [t for t in literais if not _em_ingles(t) and t not in ingles.TELA_DO_JOGO]
        self.assertEqual([], faltam, "texto do jogo em portugues sem traducao")

    def test_todo_render_do_jogo_que_vai_ao_video_passa_pelo_mapa(self):
        """Conferente, 20/10 (2a rodada): o agarrao ("ARREMESSO!",
        "JOELHADA", "REVERSÃO!") e o nome da invocacao ("Fênix") iam direto
        ao `.render(` e a varredura antiga, que so olhava o `_push_texto`,
        deixou passar. Agora: TODO `.render(` das funcoes de desenho que vao
        ao video recebe texto pelo mapa (`_texto_da_tela`/`_nome_na_tela`),
        ou sem letras, ou um item revisado de `REVISADOS`."""
        from pathlib import Path
        fonte = (Path(__file__).resolve().parents[2] / "neural_fights" / "simulation"
                 / "simulacao.py").read_text(encoding="utf-8")
        problemas = _renders_sem_mapa(fonte)
        self.assertEqual([], problemas, "texto desenhado pelo jogo fora do mapa de exibicao")
        # caso zero: o desenho antigo do agarrao seria pego
        antigo = ("class Simulador:\n"
                  "    def _desenhar_tell(self, modo):\n"
                  "        rotulo = {'JOELHADA': 'JOELHADA'}.get(modo, modo)\n"
                  "        surf = get_fonte(20).render(rotulo, True, (1, 1, 1))\n"
                  "        nome = getattr(self, 'nome', '')\n"
                  "        outra = get_fonte(14).render(nome, True, (1, 1, 1))\n")
        self.assertEqual(2, len(_renders_sem_mapa(antigo)))

    def test_agarrao_e_invocacoes_tem_traducao(self):
        import re
        from pathlib import Path
        from neural_fights.core.skills import SKILL_DB
        invocacoes = [k for k, v in SKILL_DB.items()
                      if str(v.get("tipo", "")).upper() == "SUMMON"]
        self.assertGreaterEqual(len(invocacoes), 4)
        self.assertEqual([], [n for n in invocacoes if n not in ingles.TELA_DO_JOGO])
        fonte = (Path(__file__).resolve().parents[2] / "neural_fights" / "simulation"
                 / "simulacao.py").read_text(encoding="utf-8")
        bloco = re.search(r'"ARREMESSO": "ARREMESSO!".*?\}', fonte, re.S).group(0)
        rotulos = re.findall(r':\s*"([^"]+)"', bloco) + ["REVERSÃO!"]
        self.assertEqual(5, len(rotulos))
        self.assertEqual([], [r for r in rotulos if r not in ingles.TELA_DO_JOGO])

    def test_nome_de_skill_nao_entra_no_texto_do_duelo(self):
        confronto.esquecer_armas()
        with mock.patch.object(confronto, "_carregar_armas", return_value={}):
            editing = load_config("editing.json")
            captions = CaptionGenerator(load_config("captions.json"), load_config("frases.json"))
            luta = TelaDoDueloEmInglesTests()._fight()["luta"]
            for slot in ("p1_ficha", "p2_ficha"):
                luta[slot]["kit"] = [{"nome": n} for n in self.KIT]
                luta[slot]["kit_skills"] = list(self.KIT)
            fight = {"seed": 7, "luta": luta, "lutas": [json.loads(json.dumps(luta))]}
            evento = DueloTimelineBuilder(editing, captions).build(
                random.Random(3), fight)["events"][0]
            config = catalogo.carregar_config()
            campos = catalogo.campos_do_confronto(fight["luta"])
        confronto.esquecer_armas()
        visto = json.dumps({k: evento.get(k) for k in
                            ("confronto", "identidade", "veredito", "callouts")},
                           ensure_ascii=False)
        visto += catalogo._formatar(config["titulos"]["duelo"], campos)
        visto += catalogo._formatar(config["descricoes"]["duelo"], campos)
        for skill in self.KIT:
            self.assertNotIn(skill, visto)


class TextoDoJogoNoClipeTests(unittest.TestCase):

    def test_o_simulador_troca_o_texto_desenhado_pelo_mapa(self):
        from neural_fights.simulation.simulacao import Simulador
        com = SimpleNamespace(match_config={"textos_da_tela": dict(ingles.TELA_DO_JOGO)})
        self.assertEqual("PRESSURE", Simulador._texto_da_tela(com, "PRESSÃO"))
        self.assertEqual("CRIT!", Simulador._texto_da_tela(com, "CRÍTICO!"))
        self.assertEqual(12, Simulador._texto_da_tela(com, 12))
        # caso zero: sem mapa (build, estreia, o jogo), o texto de sempre
        sem = SimpleNamespace(match_config={})
        self.assertEqual("PRESSÃO", Simulador._texto_da_tela(sem, "PRESSÃO"))

    def test_o_desenho_do_plano_e_os_textos_flutuantes_passam_pelo_mapa(self):
        from neural_fights.simulation.simulacao import Simulador
        self.assertIn("self._texto_da_tela(rotulo_plano)",
                      inspect.getsource(Simulador._desenhar_rotulo_do_plano))
        self.assertIn("Simulador._texto_da_tela(self, conteudo)",
                      inspect.getsource(Simulador._push_texto))

    def test_o_gravador_aceita_o_mapa(self):
        from neural_fights.recording import fight_recorder
        args = fight_recorder.build_parser().parse_args(
            ["--p1", "A", "--p2", "B", "--sem-video",
             "--textos-da-tela", json.dumps({"PRESSÃO": "PRESSURE"}, ensure_ascii=False)])
        self.assertEqual({"PRESSÃO": "PRESSURE"}, args.textos_da_tela)
        self.assertIn('match_config["textos_da_tela"]',
                      inspect.getsource(fight_recorder.gravar_luta))

    def test_so_o_duelo_grava_com_o_mapa(self):
        from builds.tournament import capture, runner
        self.assertEqual(ingles.TELA_DO_JOGO, runner._textos_da_tela("duelo"))
        for origem in ("estreia", "luta", "torneio"):
            self.assertIsNone(runner._textos_da_tela(origem))
        visto = {}

        def falso_run(comando, **_):
            visto["comando"] = comando
            return SimpleNamespace(stdout='{"sucesso": true}', stderr="")

        with mock.patch.object(capture.subprocess, "run", falso_run):
            capture.gravar_uma(p1="A", p2="B", seed=1, saida=None, cenario="Arena",
                               textos_da_tela={"PRESSÃO": "PRESSURE"})
        indice = visto["comando"].index("--textos-da-tela")
        self.assertEqual({"PRESSÃO": "PRESSURE"}, json.loads(visto["comando"][indice + 1]))
        with mock.patch.object(capture.subprocess, "run", falso_run):
            capture.gravar_uma(p1="A", p2="B", seed=1, saida=None, cenario="Arena")
        self.assertNotIn("--textos-da-tela", visto["comando"])

    def test_a_reserva_do_letreiro_mede_o_ko_em_ingles(self):
        from builds.tournament import runner
        self.assertIn("ingles.CALLOUTS", inspect.getsource(runner.reserva_do_letreiro))


class VozDoGanchoTests(unittest.TestCase):
    """A voz do quadro 0 ("X versus Y, who will win?"), so pelo edge-tts."""

    def _mp3_falso(self, pasta):
        import subprocess
        caminho = os.path.join(pasta, "fala.mp3")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=1.8", "-ac", "1", caminho],
                       check=True)
        return caminho

    def test_a_frase_e_o_confronto_e_a_pergunta(self):
        from builds.content import voz_do_duelo
        self.assertEqual("Tactical Knives versus Kusarigama, who will win?",
                         voz_do_duelo.frase("Tactical Knives", "Kusarigama"))
        self.assertTrue(voz_do_duelo.VOZ_PADRAO.startswith("en-US-"))

    def test_a_voz_comeca_no_quadro_0(self):
        import tempfile
        import wave
        from pathlib import Path
        from builds.content import voz_do_duelo
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(self._mp3_falso(tmp))
            with mock.patch.object(voz_do_duelo, "_sintetizar_edge", return_value=mp3):
                wav = voz_do_duelo.gerar(Path(tmp), "Katana", "Sai", log=lambda *_: None)
            self.assertIsNotNone(wav)
            with wave.open(str(wav)) as fh:
                quadros = fh.readframes(fh.getnframes())
                taxa = fh.getframerate()
            # som ja nos primeiros 50 ms
            import array
            amostras = array.array("h", quadros)
            primeiros = amostras[: int(0.05 * taxa) * 2]
            self.assertGreater(max(abs(a) for a in primeiros), 1000)
            registro = json.loads((Path(tmp) / voz_do_duelo.REGISTRO).read_text(encoding="utf-8"))
            self.assertEqual("Katana versus Sai, who will win?", registro["texto"])
            self.assertEqual(0.0, registro["inicio_s"])

    def test_sem_edge_sai_sem_voz_e_nunca_pelo_sapi(self):
        import tempfile
        from pathlib import Path
        from builds.content import voz, voz_do_duelo
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(voz, "_edge", side_effect=voz.VozIndisponivel("403")), \
                mock.patch.object(voz, "_sapi") as sapi:
            wav = voz_do_duelo.gerar(Path(tmp), "Katana", "Sai", cache=Path(tmp) / "c",
                                     log=lambda *_: None)
        self.assertIsNone(wav)
        sapi.assert_not_called()

    def test_a_frase_inglesa_nao_passa_pelo_falavel_pt_br(self):
        """`voz.falavel` e pt-BR ("KO" -> "nocaute", "IA" -> "inteligencia
        artificial"): a frase em ingles vai ao edge-tts como esta."""
        import tempfile
        from pathlib import Path
        from builds.content import voz, voz_do_duelo
        enviados = []

        def edge_falso(texto, destino, cfg):
            enviados.append((texto, cfg["voz"]))
            raise voz.VozIndisponivel("so registrando")

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(voz, "_edge", edge_falso), \
                mock.patch.object(voz, "falavel", side_effect=AssertionError("falavel pt-BR")):
            voz_do_duelo.gerar(Path(tmp), "KO Blade", "IA Bow", cache=Path(tmp) / "c",
                               log=lambda *_: None)
        self.assertEqual([("KO Blade versus IA Bow, who will win?", "en-US-GuyNeural")],
                         enviados)
        # caso zero: o falavel pt-BR estragaria a frase
        self.assertIn("nocaute", voz.falavel("KO Blade versus IA Bow, who will win?"))

    def test_o_duelo_passa_a_voz_para_o_render(self):
        from builds.pipeline.controller import PipelineController
        fonte = inspect.getsource(PipelineController._entregar_duelo)
        self.assertIn('"voz": voz_gancho, "voz_sobre_o_jogo": True', fonte)
        self.assertIn("voz_do_duelo.gerar", inspect.getsource(PipelineController._voz_do_duelo))

    def test_voz_curta_sobre_o_jogo_nao_corta_o_audio(self):
        """duelo_00001 (20/10): o sidechaincompress acabava junto com a voz
        de 2,4 s e o video de 5,9 s ficava mudo dali em diante."""
        import subprocess
        import tempfile
        from pathlib import Path
        from builds.video.renderer import VideoRenderer
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            video, voz_wav, musica = tmp / "v.mp4", tmp / "voz.wav", tmp / "m.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "color=c=black:s=64x64:d=4", "-f", "lavfi", "-i",
                            "sine=frequency=300:duration=4", "-shortest", "-c:v",
                            "libx264", "-c:a", "aac", str(video)], check=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "sine=frequency=800:duration=1", str(voz_wav)], check=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "sine=frequency=500:duration=2", str(musica)], check=True)
            r = VideoRenderer(load_config("render.json"), "celular")
            r._voz_sobre_o_jogo = True
            saida = tmp / "final.mp4"
            r._mix_final(video, musica, voz_wav, saida)
            dur = float(subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                 "stream=duration", "-of", "csv=p=0", str(saida)],
                capture_output=True, text=True).stdout.strip())
        self.assertGreater(dur, 3.8)

    def test_plano_antigo_sem_confronto_nao_ganha_voz(self):
        from builds.pipeline.controller import PipelineController
        falso = SimpleNamespace(editing_config={}, render_config={})
        self.assertIsNone(PipelineController._voz_do_duelo(
            falso, "x", {"events": [{"type": "gameplay"}]}))


if __name__ == "__main__":
    unittest.main()
