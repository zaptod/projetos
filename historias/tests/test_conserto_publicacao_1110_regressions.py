# -*- coding: utf-8 -*-
"""Conserto da auditoria profunda de 11/10/2026 — publicacao (lado historias
e o `postar.py`).

Cada classe e um item da tarefa `conserto_publicacao.md`, com o numero medido
na prova da auditoria no docstring. Nada toca o estado real: `_pareceres`,
ledger, lancador e diario vao para pasta temporaria ou para listas.

Rode de dentro de historias/:
    python -m pytest tests/test_conserto_publicacao_1110_regressions.py -q
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

RAIZ_HISTORIAS = Path(__file__).resolve().parents[1]
RAIZ = RAIZ_HISTORIAS.parent
POSTAR = RAIZ / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_conserto_1110", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


class _V:
    def __init__(self, fonte, parte, partes=6):
        self.fonte_id = fonte
        self.parte = parte
        self.partes = partes
        self.id = f"{fonte}:celular:p{parte:02d}"
        self.caminho = Path(f"{self.id}.mp4")
        self.titulo = f"T {self.id}"


# ------------------------------------------------------------ item 1: parecer
class PareceresTests(unittest.TestCase):
    """`_pareceres.json`: leitura que falha virava `{}` e `lembrar` gravava
    por cima. Prova p2 da auditoria: com o JSON pela metade, depois de
    `lembrar(novo)` o arquivo tinha SO a ficha nova; `veto_por_id(vetado)`
    virou None e a parte reprovada saia. Corrida de 3 processos x 40
    `lembrar`: 6 fichas de 122."""

    def setUp(self):
        from contos.publicar import parecer
        from builds import atividade
        self.parecer = parecer
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        _trocar(self, parecer, "LEMBRETES", self.pasta / "_pareceres.json")
        self.diario = []
        _trocar(self, atividade, "registrar",
                lambda *a, **k: self.diario.append(a))
        mp4 = self.pasta / "v.mp4"
        mp4.write_bytes(b"x" * 10)
        self.vetado = type("V", (), {"id": "historia_00050:celular:p01",
                                     "caminho": mp4})()
        self.novo = type("V", (), {"id": "historia_00051:celular:p01",
                                   "caminho": mp4})()
        parecer.lembrar(self.vetado, {"aprovado": False, "motivos": ["cena 3"],
                                      "vista": "video inteiro (2:10)",
                                      "criterio": 2})
        self.bom = parecer.LEMBRETES.read_text(encoding="utf-8")

    def _partir(self):
        partido = self.bom[: len(self.bom) // 2]
        self.parecer.LEMBRETES.write_text(partido, encoding="utf-8")
        return partido

    def test_json_partido_levanta_e_guarda_copia(self):
        partido = self._partir()
        with self.assertRaises(ValueError):
            self.parecer._lembretes()
        copia = self.parecer.LEMBRETES.with_suffix(".json.corrompido")
        self.assertEqual(partido, copia.read_text(encoding="utf-8"))

    def test_lembrar_sobre_json_partido_nao_grava_por_cima_e_avisa(self):
        partido = self._partir()
        self.parecer.lembrar(self.novo, {"aprovado": True, "motivos": [],
                                         "vista": "video inteiro (1:50)",
                                         "criterio": 2})      # nao levanta
        self.assertEqual(partido, self.parecer.LEMBRETES.read_text(encoding="utf-8"),
                         "nada foi gravado por cima do arquivo partido")
        self.assertEqual([], list(self.pasta.glob("*.tmp")))
        (aviso,) = self.diario
        self.assertEqual(("parecer", "erro"), aviso[:2])
        self.assertIn("nao gravei", aviso[2])

    def test_arquivo_trancado_tenta_de_novo(self):
        import builtins
        contagem = {"n": 0}

        def trancado(*a, **k):
            if contagem["n"] < 2:
                contagem["n"] += 1
                raise PermissionError("em uso")
            return builtins.open(*a, **k)
        self.parecer.open = trancado
        self.addCleanup(lambda: delattr(self.parecer, "open"))
        self.assertIn(self.vetado.id, self.parecer._lembretes())
        self.assertEqual(2, contagem["n"])

    def test_gravacao_sob_trava_por_temporario(self):
        from builds import travas
        usadas = []
        original = travas.trava

        @contextlib.contextmanager
        def espia(nome, esperar=0.0):
            usadas.append(nome)
            with original(nome, esperar=esperar) as minha:
                yield minha
        _trocar(self, travas, "trava", espia)
        self.parecer.lembrar(self.novo, {"aprovado": True, "motivos": [],
                                         "vista": "video inteiro (1:50)",
                                         "criterio": 2})
        self.assertIn("pareceres_json", usadas)
        self.assertEqual([], list(self.pasta.glob("*.tmp")))
        fichas = json.loads(self.parecer.LEMBRETES.read_text(encoding="utf-8"))
        self.assertEqual({self.vetado.id, self.novo.id}, set(fichas))
        self.assertTrue(self.parecer.veto_por_id(self.vetado))


# ---------------------------------------------- item 4: pedacos e horarios
class PublicacaoParcialTests(unittest.TestCase):
    """Prova p4 da auditoria: parte em 2 Shorts, o 2o falha -> rodada 1
    `enviados = []`, ledger 0 linhas; rodada 2 sobe o pedaco 1 DE NOVO
    (`uploads = [p01#1, p01#1, p01#2]`). Agora: o que subiu e registrado e a
    rodada 2 pula a parte (pedaco 1 subiu 1 vez)."""

    def setUp(self):
        from contos.publicar import catalogo, qualidade, serie
        from builds import atividade
        self.catalogo, self.serie = catalogo, serie
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        pasta = Path(self._tmp.name)
        _trocar(self, serie, "REGISTRO", pasta / "publicados.jsonl")
        _trocar(self, atividade, "registrar", lambda *a, **k: None)
        mp4 = pasta / "p4.mp4"
        mp4.write_bytes(b"x" * 200_000)
        self.video = catalogo.Video(id="historia_00777:celular:p01", perfil="celular",
                                    caminho=mp4, titulo="T", descricao="D",
                                    parte=1, partes=2, fonte_id="historia_00777")
        _trocar(self, serie, "videos_da_serie", lambda hid, perfil="celular": [self.video])
        _trocar(self, qualidade, "vistoriar_serie",
                lambda hid, vs: {"erros": [], "avisos": [], "partes": []})
        _trocar(self, catalogo, "barrar_pausa", lambda: None)
        _trocar(self, catalogo, "barrar_recusa", lambda v: None)
        _trocar(self, catalogo, "carregar_config", lambda: {})
        _trocar(self, catalogo._rb_publicar_youtube, "modo", lambda config=None: "navegador")
        self.uploads = []
        self.falhar_no_2 = True

        def preparar(v, *, limite, log=print):
            return [catalogo.Video(**{**v.__dict__, "id": v.id + "#1"}),
                    catalogo.Video(**{**v.__dict__, "id": v.id + "#2"})]

        def publicar(pedaco, **kw):
            if pedaco.id.endswith("#2") and self.falhar_no_2:
                self.falhar_no_2 = False
                raise RuntimeError("Studio caiu no 2o pedaco (TargetClosed)")
            self.uploads.append(pedaco.id)
            kw["prova"].update({"estado": "publicado", "youtube_id": f"ID{len(self.uploads)}"})
            return f"https://youtu.be/ID{len(self.uploads)}"
        _trocar(self, catalogo._rb_publicar_cortes, "preparar", preparar)
        _trocar(self, catalogo._rb_publicar_cortes, "limite", lambda config: 180)
        _trocar(self, catalogo._rb_publicar_youtube, "publicar_como_configurado", publicar)

    def test_a_excecao_carrega_o_que_ja_subiu(self):
        provas = []
        with self.assertRaises(self.catalogo.PublicacaoParcial) as caso:
            self.catalogo.publicar_youtube(self.video, "public", provas=provas)
        exc = caso.exception
        self.assertEqual(["https://youtu.be/ID1"], exc.urls)
        self.assertEqual([{"estado": "publicado", "youtube_id": "ID1"}], exc.provas)
        self.assertEqual(exc.provas, provas)
        self.assertIn("TargetClosed", str(exc))
        self.assertIn("1 pedaco(s)", str(exc))

    def test_caso_zero_pedaco_1_que_cai_levanta_o_erro_original(self):
        def cai_no_primeiro(pedaco, **kw):
            raise RuntimeError("caiu no 1o")
        _trocar(self, self.catalogo._rb_publicar_youtube, "publicar_como_configurado",
                cai_no_primeiro)
        with self.assertRaises(RuntimeError) as caso:
            self.catalogo.publicar_youtube(self.video, "public", provas=[])
        self.assertNotIsInstance(caso.exception, self.catalogo.PublicacaoParcial)

    def test_serie_registra_o_pedaco_que_subiu_e_nao_o_sobe_de_novo(self):
        r1 = self.serie.publicar("historia_00777", agendar=False, log=lambda *_: None)
        self.assertEqual(1, len(r1["enviados"]))
        self.assertEqual(1, len(r1["erros"]))
        linhas = self.serie.publicados()
        self.assertEqual(1, len(linhas))
        self.assertEqual("https://youtu.be/ID1", linhas[0]["url"])
        self.assertTrue(linhas[0]["parcial"])
        self.assertEqual(["ID1"], [p["youtube_id"] for p in linhas[0]["prova"]])
        r2 = self.serie.publicar("historia_00777", agendar=False, log=lambda *_: None)
        self.assertEqual(1, len(r2["pulados"]))
        self.assertEqual(1, self.uploads.count("historia_00777:celular:p01#1"),
                         "antes: 2 envios do pedaco 1")


class HorariosTests(unittest.TestCase):
    """Prova p5a: `horarios(1, comecar_em=datetime(2026,10,20,18,0))[0]` dava
    `18:00:00Z` — 15:00 na hora da maquina (-03:00)."""

    def test_hora_local_sem_fuso_vira_o_mesmo_instante_em_utc(self):
        from contos.publicar import serie
        local = datetime(2099, 10, 20, 18, 0)
        if local.astimezone().utcoffset().total_seconds() == 0:
            self.skipTest("maquina em UTC: os dois caminhos dao o mesmo")
        (saida,) = serie.horarios(1, comecar_em=local)
        esperado = (local.astimezone(timezone.utc).isoformat(timespec="seconds")
                    .replace("+00:00", "Z"))
        self.assertEqual(esperado, saida)
        self.assertNotEqual("2099-10-20T18:00:00Z", saida)

    def test_hora_com_fuso_segue_igual(self):
        from contos.publicar import serie
        utc = datetime(2099, 10, 20, 18, 0, tzinfo=timezone.utc)
        self.assertEqual(["2099-10-20T18:00:00Z"], serie.horarios(1, comecar_em=utc))


# -------------------------------------------------------- item 5: postar.py
class AdiadasRespeitamORenderTests(unittest.TestCase):
    """Prova `prova_adiadas_render.py`: fila com p03 e p04 da MESMA serie em
    render -> `escolhida: historia_00050:celular:p04`, `vistoriou:
    [('historia_00050', 4)]` — o mp4 lido enquanto o render escreve, fora de
    ordem. Agora: nenhuma escolhida, nada vistoriado."""

    def setUp(self):
        from builds import travas
        from contos.publicar import qualidade
        from contos.roteiro import roteiro as R
        self.m = _postar()
        self.m._linha = lambda *a, **k: None
        self.m._pulsar = lambda: None
        self.m._veto_lembrado = lambda alvo: ""
        self.m._retencao = lambda alvo: ""
        self.m._parecer_da_ia = lambda alvo, roteiro, laudo: ""
        self.vistoriadas = []
        _trocar(self, qualidade, "vistoriar_parte",
                lambda fonte, parte, caminho, roteiro=None:
                self.vistoriadas.append((fonte, parte)) or {"ok": True, "erros": [], "avisos": []})
        _trocar(self, R, "carregar", lambda fonte: {})
        self.travas = travas

    def test_serie_em_render_nao_sai_nem_no_ultimo_recurso(self):
        self.m.fila_de_historias = lambda: [_V("historia_00050", 3), _V("historia_00050", 4)]
        _trocar(self, self.travas, "ocupada",
                lambda nome: nome == "historias__render__historia_00050")
        alvo, recusados = self.m.proxima_historia()
        self.assertIsNone(alvo)
        self.assertEqual([], self.vistoriadas)
        self.assertEqual(2, sum("sendo renderizada" in r for r in recusados), recusados)

    def test_caso_zero_sem_render_o_ultimo_recurso_continua_valendo(self):
        self.m.fila_de_historias = lambda: [_V("historia_00050", 3), _V("historia_00050", 4)]
        _trocar(self, self.travas, "ocupada", lambda nome: False)
        self.m._veto_lembrado = (lambda alvo: "a IA REPROVOU" if alvo.parte == 3 else "")
        qualidade_ok = {"ok": True, "erros": [], "avisos": []}
        from contos.publicar import qualidade
        _trocar(self, qualidade, "vistoriar_parte",
                lambda fonte, parte, caminho, roteiro=None:
                dict(qualidade_ok, ok=parte == 4))
        alvo, _ = self.m.proxima_historia()
        self.assertEqual("historia_00050:celular:p04", getattr(alvo, "id", None))


class EscoarPelaPortaDaRodadaTests(unittest.TestCase):
    """Prova `prova_escoar.py`: `--tudo` subiu a p03 VETADA, `vistoriou
    antes? []`, `marcou 'a conferir'? []`, e a linha ia sem `prova`. Agora
    passa por `proxima_historia`, grava prova/ids e marca a retida."""

    def setUp(self):
        from contos.publicar import serie
        self.m = _postar()
        self.m._linha = lambda *a, **k: None
        self.m._visibilidade_das_historias = lambda: "public"
        self.m._registrar_valvula = lambda ficha: None
        self.m._tiktok_das_historias = lambda alvo, falha=None: "publicado no TikTok"
        self.fila = [_V("historia_00050", 3), _V("historia_00050", 4), _V("historia_00051", 1)]
        self.m.fila_de_historias = lambda: list(self.fila)
        self.restantes = list(self.fila)
        self.pedidas = 0

        def proxima(*, vistoriar=True):
            self.pedidas += 1
            return (self.restantes.pop(0), []) if self.restantes else (None, [])
        self.m.proxima_historia = proxima
        self.subidos = []

        def subir(alvo, visibilidade, provas):
            self.subidos.append(alvo.id)
            provas.append({"estado": "publicado", "youtube_id": f"ID{len(self.subidos)}"})
            return f"https://youtu.be/ID{len(self.subidos)}"
        self.m._subir_parte_no_youtube = subir
        self.registros = []
        _trocar(self, serie, "registrar",
                lambda alvo, url, plat, quando, extra=None:
                self.registros.append((alvo.id, extra)) or {})
        self.marcados = []
        self.m._marcar_retido = lambda alvo, retencao, destinos=None: \
            self.marcados.append((alvo.id, retencao, destinos))
        self.m._valvula_da_parte = (
            lambda ficha, alvo: "a IA reprovou" if alvo.fonte_id == "historia_00050" else "")

    def test_escoa_pela_porta_e_grava_prova_e_marca(self):
        r = self.m.escoar_historias()
        self.assertEqual([v.id for v in self.fila], self.subidos)
        self.assertEqual(3, len(r["postados"]))
        _id, extra = self.registros[0]
        self.assertEqual("postar.py --tudo", extra["por"])
        self.assertEqual("ID1", extra["youtube_id"])
        self.assertIs(True, extra["prova_ok"])
        self.assertEqual(1, len(extra["prova"]))
        self.assertEqual([("historia_00050:celular:p03", "a IA reprovou", ("youtube",)),
                          ("historia_00050:celular:p04", "a IA reprovou", ("youtube",))],
                         self.marcados)

    def test_limite_1_sobe_exatamente_uma(self):
        """A 1a versao do conserto fazia `range(1, limite)`: com `--limite 1`
        nao subia nada, e sem limite subia N-1."""
        self.m.escoar_historias(limite=1)
        self.assertEqual(["historia_00050:celular:p03"], self.subidos)

    def test_fila_que_seca_para_sem_insistir(self):
        self.restantes = []
        r = self.m.escoar_historias()
        self.assertEqual([], self.subidos)
        self.assertEqual([], r["postados"])
        self.assertEqual(1, self.pedidas)

    def test_so_ver_nao_sobe_nada(self):
        r = self.m.escoar_historias(so_ver=True)
        self.assertEqual(3, r["total"])
        self.assertEqual([], self.subidos)
        self.assertEqual(0, self.pedidas)


class FichasDeBuildsTests(unittest.TestCase):
    """Prova `_derrubados_pela_rede` da ficha `{"feito": True, "so_tiktok":
    True, "tiktok": "", "tiktok_falha": "PerfilOcupado: ..."}` -> `[]`,
    `_publicou_sem_queda -> True`, codigo de saida 0: a passada nao publicou
    nada e saia [POSTADO]. E `prova_aviso_ja_tk.py`: o Telegram dizia
    "TikTok nao subiu" para um build cujo TikTok ja tinha saido."""

    def setUp(self):
        self.m = _postar()
        self.m._linha = lambda *a, **k: None
        self.m._registrar_valvula = lambda ficha: None
        self.m.titulo_repetido = lambda *a, **k: False
        self.m._tiktok_neste_horario = lambda agora=None: True
        self.alvo = type("B", (), {"id": "generation_00102:duelo:celular",
                                   "titulo": "Duelo"})()
        self.m._build_por_id = lambda vid: self.alvo
        self.m.proximo_build = lambda marcar=True: self.alvo

    def _horario(self, youtube=None, tiktok=None):
        self.m.publicou_neste_horario = (
            lambda canal, plataforma: youtube if plataforma == "youtube" else tiktok)

    def test_youtube_ja_saiu_e_tiktok_falha_NAO_e_feito(self):
        self._horario(youtube={"video_id": self.alvo.id, "url": "https://youtu.be/x"})

        def tiktok_cai(alvo, falha=None):
            falha.update(tipo="PerfilOcupado", mensagem="o perfil esta em uso")
            return ""
        self.m._tiktok_dos_builds = tiktok_cai
        ficha = self.m.postar_build()
        self.assertFalse(ficha["feito"])
        self.assertTrue(ficha["so_tiktok"])
        self.assertIn("PerfilOcupado", ficha["tiktok_falha"])
        self.assertFalse(self.m._publicou_sem_queda(ficha))
        self.assertEqual([], self.m._derrubados_pela_rede(ficha))

    def test_youtube_ja_saiu_e_tiktok_confirma_e_feito(self):
        self._horario(youtube={"video_id": self.alvo.id, "url": "https://youtu.be/x"})
        self.m._tiktok_dos_builds = lambda alvo, falha=None: "publicado no TikTok"
        ficha = self.m.postar_build()
        self.assertTrue(ficha["feito"])
        self.assertTrue(self.m._publicou_sem_queda(ficha))

    def test_tiktok_ja_saiu_leva_so_youtube_na_ficha(self):
        self._horario(tiktok={"video_id": self.alvo.id})
        self.m._youtube_dos_builds = lambda alvo, laudo=None: "https://youtu.be/x"
        self.m._tiktok_dos_builds = lambda alvo, falha=None: self.fail("o TikTok nao roda")
        ficha = self.m.postar_build()
        self.assertTrue(ficha["so_youtube"])
        self.assertTrue(ficha["feito"])
        self.assertEqual("", ficha["tiktok"])
        self.assertNotIn("tiktok_falha", ficha)

    def test_excecao_depois_do_clique_no_youtube_nao_repoe(self):
        """Item 3: a marca `clicou` do laudo chega a ficha; a frase de rede
        da excecao nao devolve o YouTube a reposicao (subiria de novo)."""
        self._horario()
        self.m._tiktok_dos_builds = lambda alvo, falha=None: ""

        def clicou_e_caiu(alvo, laudo=None):
            laudo["clicou"] = True
            raise RuntimeError("infraestrutura: net::ERR_TIMED_OUT depois do clique")
        self.m._youtube_dos_builds = clicou_e_caiu
        ficha = self.m.postar_build()
        self.assertTrue(ficha["youtube_falhou"])
        self.assertTrue(ficha["youtube_clicou"])
        self.assertNotIn("youtube", self.m._derrubados_pela_rede(ficha))

    def test_caso_zero_queda_antes_do_clique_continua_repondo(self):
        self._horario()
        self.m._tiktok_dos_builds = lambda alvo, falha=None: ""

        def caiu_antes(alvo, laudo=None):
            raise RuntimeError("infraestrutura: net::ERR_TIMED_OUT")
        self.m._youtube_dos_builds = caiu_antes
        ficha = self.m.postar_build()
        self.assertNotIn("youtube_clicou", ficha)
        self.assertIn("youtube", self.m._derrubados_pela_rede(ficha))


class SaidaDatadaTests(unittest.TestCase):
    """Maquina.md item 18: 4 dias com horario vazio sem causa porque o
    `postar.txt` nao data as linhas."""
    CARIMBO = r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] "

    def setUp(self):
        self.m = _postar()
        self.arquivo = io.StringIO()
        self.saida = self.m._SaidaDatada(self.arquivo)

    def test_cada_linha_ganha_data_e_hora(self):
        self.saida.write("primeira\nsegunda\n")
        self.saida.write("terceira em ")
        self.saida.write("dois pedacos\n")
        linhas = self.arquivo.getvalue().splitlines()
        self.assertEqual(3, len(linhas))
        for linha in linhas:
            self.assertRegex(linha, self.CARIMBO)
        self.assertTrue(linhas[2].endswith("terceira em dois pedacos"))

    def test_a_linha_do_postar_tambem_e_datada(self):
        """`_linha` escreve em `sys.stdout.buffer` quando ele existe; a saida
        datada nao pode expor o do arquivo, senao a linha sai sem data."""
        self.assertIsNone(self.saida.buffer)
        original = sys.stdout
        sys.stdout = self.saida
        try:
            self.m._linha("[postar] builds: nao ha video pendente")
        finally:
            sys.stdout = original
        (linha,) = self.arquivo.getvalue().splitlines()
        self.assertRegex(linha, self.CARIMBO + r"\[postar\] builds")

    def test_o_main_abre_a_saida_pelo_python_e_data(self):
        fonte = POSTAR.read_text(encoding="utf-8")
        bloco = fonte[fonte.index('if __name__ == "__main__":'):]
        self.assertIn('"--saida"', bloco)
        self.assertIn("_SaidaDatada(saida)", bloco)
        self.assertIn('open(argumentos[i + 1], "a"', bloco)


class LancadorTests(unittest.TestCase):
    """Auditoria `postar.md` item 1 (gravidade alta): as 10 tarefas rodam o
    MESMO `postar.cmd` com `>>`, e o cmd do horario seguinte morria com
    "O arquivo ja esta sendo usado por outro processo" ANTES de o python
    nascer, com codigo 0 — a trava da rodada, a dona pendurada e o "em voo"
    nunca chegavam a rodar (prova: `b_rodou.txt existe: False`)."""

    def test_o_lancador_nao_usa_o_redirecionamento_do_cmd(self):
        m = _postar()
        with tempfile.TemporaryDirectory() as tmp:
            m.RAIZ = Path(tmp)
            texto = m.escrever_lancador().read_text(encoding="utf-8")
        self.assertNotIn(">>", texto)
        self.assertIn("--saida", texto)
        self.assertIn("postar.txt", texto)
        self.assertIn("> NUL 2>&1", texto)
        self.assertIn("ferramentas\\postar.py", texto)


# ------------------------------------------------------- item 8: agenda
class AgendaAchaORemotoTests(unittest.TestCase):
    """Maquina.md item 6: `[parecer] nao consegui avisar no Telegram: No
    module named 'remoto'` 24x — o parecer roda com cwd `historias/`, e
    `remoto` mora na raiz do repositorio."""

    def test_com_cwd_em_historias_o_remoto_e_encontrado(self):
        codigo = ("import importlib.util as u, sys\n"
                  "import contos.pipeline.agenda as a\n"
                  "s = u.find_spec('remoto')\n"
                  "print(s.origin if s else 'NAO')\n")
        ambiente = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        saida = subprocess.run([sys.executable, "-c", codigo], cwd=str(RAIZ_HISTORIAS),
                               capture_output=True, text=True, timeout=120,
                               env=ambiente)
        self.assertEqual(0, saida.returncode, saida.stderr)
        origem = saida.stdout.strip()
        self.assertNotEqual("NAO", origem, "sem a raiz no sys.path o aviso nao sai")
        self.assertTrue(Path(origem).resolve().is_relative_to(RAIZ.resolve()),
                        f"{origem} nao e o remoto desta arvore")

    def test_a_raiz_do_repositorio_esta_no_sys_path(self):
        from contos.pipeline import agenda
        raiz = str(agenda.RAIZ_DO_REPOSITORIO)
        self.assertEqual(RAIZ.resolve(), Path(raiz).resolve())
        self.assertIn(raiz, sys.path)


if __name__ == "__main__":
    unittest.main()
