# -*- coding: utf-8 -*-
"""A serie do Blue Lock na rodada do postar (26/10/2026).

Pedido do Adrian: um episodio por dia, nas contas do antigo zombie
(`zombie_survivores` no YouTube, `zombie_surviv0rs` no TikTok), so o que o
conferente aprovou. Escolha medida: 20:37 (a unica noite da grade que os
duelos nao usam: duelos 06:37 09:37 12:07 15:37 17:57 21:37 22:37 23:37 desde
27/10; 21:37 ate 26/10), nos dois destinos (o TikTok tem 20:37 na grade dele).

Contas de mao (o que cada teste prova):
  - 20:37 e subconjunto da grade de cada plataforma e NAO esta em nenhuma das
    tabelas dos duelos (26/10, 27/10, 01/11) — nenhum duelo divide o horario;
  - fora das 20:37 a ficha e calada (`fora_da_grade`) e NAO le fila nem ledger;
  - sem episodio aprovado (caso ZERO) as 20:37: ficha calada, nunca alarme;
  - com o ep1 aprovado: 1 linha no YouTube e 1 no TikTok no ledger PROPRIO
    (`outputs/_serie_bluelock`), e a segunda rodada no mesmo horario nao
    publica nada (um por horario);
  - YouTube que clicou mas nao disse PUBLICO: nenhuma linha "publicada" e o
    episodio vai para "a conferir" (nunca sobe de novo);
  - ledger ou lista "a conferir" ilegiveis: nao publica (falha fechada).

Rode de dentro de historias/:
    python -m unittest tests.test_serie_bluelock_postar_regressions -v
"""
from __future__ import annotations

import importlib.util
import json
import os
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from builds import grade
from builds.publicar import desfecho, metricas
from builds.publicar import serie_bluelock as serie

GRADE_DAS_HISTORIAS_REAL = True   # ver o conftest.py da raiz

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"

TITULO = "Esse jogador parou. Ninguém mandou. 🤔 | Como eu criei um Blue Lock #1"
DESCRICAO = ("Ninguém controla os jogadores do meu simulador de Blue Lock: "
             "cada um decide sozinho, só com o que vê. Episódio 1 da série "
             "sobre como eu criei o jogo. Segue pra ver o episódio 2: o replay.")
TAGS = ["#bluelock", "#futebol", "#simulador", "#anime", "#isagi", "#bachira"]


def _postar():
    spec = importlib.util.spec_from_file_location("postar_serie_bluelock",
                                                  POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class GradeDaSerieTests(unittest.TestCase):
    def test_20_37_nos_dois_destinos_e_dentro_da_grade(self):
        self.assertEqual(grade.horas_da_serie("youtube"), (20,))
        self.assertEqual(grade.horas_da_serie("tiktok"), (20,))
        self.assertTrue(set(grade.horas_da_serie("youtube"))
                        <= set(grade.horas_da_plataforma("youtube")))
        self.assertTrue(set(grade.horas_da_serie("tiktok"))
                        <= set(grade.horas_da_plataforma("tiktok")))
        self.assertTrue(grade.publica_a_serie("youtube", 20))
        self.assertFalse(grade.publica_a_serie("youtube", 21))
        self.assertEqual(grade.horario(20), "20:37")

    def test_nenhum_duelo_divide_o_horario_da_serie(self):
        for dia in (date(2026, 10, 26), date(2026, 10, 27),
                    date(2026, 11, 1), date(2026, 11, 20)):
            for plataforma in ("youtube", "tiktok"):
                with self.subTest(dia=dia, plataforma=plataforma):
                    duelos = grade.horas_do_canal("builds", plataforma, dia)
                    self.assertFalse(
                        set(duelos) & set(grade.horas_da_serie(plataforma)),
                        f"{dia} {plataforma}: {duelos}")

    def test_as_tabelas_dos_outros_canais_nao_mudaram(self):
        """A serie e uma constante a parte: 8 duelos e 10 historias intactos."""
        self.assertEqual(grade.horas_do_canal("builds", "youtube",
                                              date(2026, 10, 27)),
                         (6, 9, 12, 15, 17, 21, 22, 23))
        self.assertEqual(grade.horas_do_canal("builds", "tiktok",
                                              date(2026, 10, 27)), (21,))
        # historias: dez e seis ate 26/10; tres e um desde 27/10
        self.assertEqual(len(grade.horas_do_canal(
            "historias", "youtube", date(2026, 10, 26))), 10)
        self.assertEqual(len(grade.horas_do_canal(
            "historias", "tiktok", date(2026, 10, 26))), 6)
        self.assertEqual(grade.CANAIS, ("historias", "builds"))


class RodadaDaSerieTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        raiz = Path(self.tmp.name)
        self.fonte = raiz / "publicar"
        self.fonte.mkdir()
        antes = os.environ.get("NF_SERIE_BLUELOCK")
        os.environ["NF_SERIE_BLUELOCK"] = str(self.fonte)
        self.addCleanup(lambda: os.environ.pop("NF_SERIE_BLUELOCK", None)
                        if antes is None
                        else os.environ.__setitem__("NF_SERIE_BLUELOCK", antes))
        self._trocar(metricas, "OUTPUTS", raiz / "outputs")
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.chamadas = []
        self._trocar(self.m.grade, "slot", lambda agora=None: 20)

    def _trocar(self, objeto, nome, valor):
        original = getattr(objeto, nome)
        setattr(objeto, nome, valor)
        self.addCleanup(setattr, objeto, nome, original)

    def _aprovar(self, numero=1):
        mp4 = self.fonte / f"EP{numero:02d}.mp4"
        mp4.write_bytes(b"episodio aprovado " + bytes([numero]))
        (self.fonte / f"ep{numero:02d}.json").write_text(json.dumps({
            "episodio": numero, "arquivo": str(mp4),
            "sha256": serie.sha256_de(mp4),
            "titulo": TITULO if numero == 1 else
            f"Gancho {numero} | Como eu criei um Blue Lock #{numero}",
            "descricao": DESCRICAO, "tags": TAGS, "idioma": "pt",
            "aprovado_por_conferente": True}, ensure_ascii=False),
            encoding="utf-8")

    def _dubles(self, *, visibilidade="public", youtube="publicado no YouTube",
                tiktok="publicado no TikTok"):
        def yt(alvo, laudo=None):
            self.chamadas.append(("youtube", alvo.id))
            laudo.update({"clicou": True, "visibilidade": visibilidade,
                          "estado": "publicado", "youtube_id": "abc123XYZ_-",
                          "confirmado": True})
            return youtube

        def tk(alvo, falha=None):
            self.chamadas.append(("tiktok", alvo.id))
            if tiktok:
                serie.registrar(alvo, tiktok, "tiktok",
                                {"publicado": True, "estado": "publicado"})
            return tiktok
        self._trocar(self.m, "_youtube_da_serie", yt)
        self._trocar(self.m, "_tiktok_da_serie", tk)
        self.marcas = []
        self._trocar(self.m, "_garantir_marca",
                     lambda *a, **k: self.marcas.append(a) or True)

    def test_fora_do_horario_a_ficha_e_calada_e_nao_le_nada(self):
        self._trocar(self.m.grade, "slot", lambda agora=None: 21)

        def nao_le(*_a, **_k):
            raise AssertionError("leu a fila fora do horario da serie")
        self._trocar(serie, "episodios", nao_le)
        ficha = self.m.postar_bluelock()
        self.assertTrue(ficha["fora_da_grade"])
        self.assertFalse(ficha["feito"])
        self.assertIn("20:37", ficha["motivo"])

    def test_sem_episodio_aprovado_o_horario_fica_vazio_sem_alarme(self):
        """O caso ZERO: pasta vazia ou inexistente nao e erro."""
        for fonte in (self.fonte, self.fonte / "nao_existe"):
            os.environ["NF_SERIE_BLUELOCK"] = str(fonte)
            ficha = self.m.postar_bluelock()
            self.assertTrue(ficha["fora_da_grade"], fonte)
            self.assertFalse(ficha["feito"])
            self.assertNotIn("excecao", ficha)

    def test_ep1_sai_nos_dois_destinos_e_uma_vez_so_por_horario(self):
        self._aprovar(1)
        self._dubles()
        ficha = self.m.postar_bluelock()
        self.assertTrue(ficha["feito"], ficha)
        self.assertEqual(ficha["alvo"], "bluelock_ep01")
        self.assertEqual(ficha["visibilidade"], "public")
        self.assertEqual(self.chamadas, [("youtube", "bluelock_ep01"),
                                         ("tiktok", "bluelock_ep01")])
        linhas = metricas.publicados("bluelock")
        self.assertEqual(sorted((l["plataforma"], l["video_id"])
                                for l in linhas),
                         [("tiktok", "bluelock_ep01"),
                          ("youtube", "bluelock_ep01")])
        yt = next(l for l in linhas if l["plataforma"] == "youtube")
        self.assertTrue(metricas.publicado(yt))
        self.assertEqual(yt["visibilidade"], "public")
        self.assertEqual(yt["youtube_id"], "abc123XYZ_-")
        self.assertEqual(yt["titulo"], TITULO)
        # o ledger de builds nao foi tocado
        self.assertFalse(metricas.registro_do_canal("builds").is_relative_to(
            metricas.registro_do_canal("bluelock").parent))
        # a SEGUNDA rodada no mesmo horario: nada, calada
        self.chamadas.clear()
        segunda = self.m.postar_bluelock()
        self.assertTrue(segunda["fora_da_grade"], segunda)
        self.assertEqual(self.chamadas, [])

    def test_o_ep2_so_sai_depois_do_ep1_e_so_no_dia_seguinte(self):
        self._aprovar(1)
        self._aprovar(2)
        self._dubles()
        self.m.postar_bluelock()
        self.chamadas.clear()
        # mesmo dia, outro horario da serie (simulado): o teto de 1 por dia
        self._trocar(self.m, "publicou_neste_horario", lambda *a, **k: None)
        ficha = self.m.postar_bluelock()
        self.assertEqual(self.chamadas, [])
        self.assertIn("ja saiu 1 episodio hoje", ficha["motivo"])

    def test_youtube_sem_confirmacao_de_publico_vai_para_a_conferir(self):
        self._aprovar(1)
        self._dubles(visibilidade="private")
        ficha = self.m.postar_bluelock()
        self.assertFalse(ficha["feito"] and not ficha.get("tiktok"))
        youtube = [l for l in metricas.publicados("bluelock")
                   if l["plataforma"] == "youtube"]
        self.assertEqual(youtube, [], "privado nao pode virar 'publicado'")
        self.assertTrue(ficha["youtube_falhou"])
        self.assertEqual([(m[0], m[1], m[2]) for m in self.marcas],
                         [("bluelock", "bluelock_ep01", "youtube")])

    def test_ledger_ilegivel_nao_publica(self):
        self._aprovar(1)
        self._dubles()

        def ilegivel(canal):
            raise self.m.LedgerIlegivel("disco")
        self._trocar(self.m, "_publicados_do_canal", ilegivel)
        ficha = self.m.postar_bluelock()
        self.assertTrue(ficha["ledger_ilegivel"])
        self.assertFalse(ficha["feito"])
        self.assertEqual(self.chamadas, [])

    def test_lista_a_conferir_ilegivel_nao_publica(self):
        self._aprovar(1)
        self._dubles()

        def nao_li(canal, plataforma="tiktok"):
            raise desfecho.NaoConsegviLer("trava ocupada")
        self._trocar(desfecho, "a_conferir", nao_li)
        ficha = self.m.postar_bluelock()
        self.assertFalse(ficha["feito"])
        self.assertNotIn("fora_da_grade", ficha)
        self.assertIn("a conferir", ficha["motivo"])
        self.assertEqual(self.chamadas, [])

    def test_so_ver_nao_publica_nem_grava(self):
        self._aprovar(1)
        self._dubles()
        ficha = self.m.postar_bluelock(so_ver=True)
        self.assertIn("bluelock_ep01", ficha["veria"])
        self.assertEqual(self.chamadas, [])
        self.assertEqual(metricas.publicados("bluelock"), [])

    def test_agora_leva_o_episodio_fora_do_horario_com_as_outras_guardas(self):
        self._aprovar(1)
        self._dubles()
        self._trocar(self.m.grade, "slot", lambda agora=None: 9)
        self.assertTrue(self.m.postar_bluelock()["fora_da_grade"])
        ficha = self.m.postar_bluelock(agora=True)
        self.assertTrue(ficha["feito"], ficha)
        self.assertEqual(len(self.chamadas), 2)
        # de novo, agora: o teto de um por dia segura
        self.chamadas.clear()
        de_novo = self.m.postar_bluelock(agora=True)
        self.assertEqual(self.chamadas, [])
        self.assertTrue(de_novo.get("fora_da_grade"), de_novo)

    def test_reposicao_do_youtube_depois_que_o_tiktok_ja_saiu(self):
        """A rede derrubou o YouTube e o TikTok foi: a segunda passada leva so
        o YouTube e a ficha diz `so_youtube` (e o que `_juntar_reposicao` usa
        para juntar as duas)."""
        self._aprovar(1)
        self._dubles()
        ep = serie.episodios()[0][0]
        serie.registrar(ep.como_video(), "publicado no TikTok", "tiktok",
                        {"publicado": True, "estado": "publicado"})
        ficha = self.m.postar_bluelock()
        self.assertEqual(self.chamadas, [("youtube", "bluelock_ep01")])
        self.assertTrue(ficha["feito"])
        self.assertTrue(ficha["so_youtube"])
        self.assertEqual(ficha["tiktok"], "")

    def test_agora_so_com_so_bluelock(self):
        with self.assertRaises(SystemExit):
            self.m.main(["--ver", "--agora"])


class FichaDaTravaTests(unittest.TestCase):
    """O voo do bluelock precisa ser aceito pela ficha da trava: um canal
    fora dessa lista perderia o clique numa queda de energia."""

    def test_voo_do_bluelock_e_valido(self):
        m = _postar()
        self.assertIn("bluelock", m.CANAIS_DA_FICHA)
        voo = {"canal": "bluelock", "alvo": "bluelock_ep01",
               "destino": "youtube", "etapa": "clicou", "desde": 1.0}
        dados = {"horario": "2026-10-26T20:37:00", "em_voo": voo,
                 "pid": 4242, "criado": 1.0, "inicio": 1.0,
                 "tipo": next(iter(m.DESCRICAO_DA_DONA))}
        ficha, erro = m._ficha_valida(dados)
        self.assertIsNone(erro)
        self.assertEqual(ficha["em_voo"]["canal"], "bluelock")
        voo["canal"] = "outro"      # o que NAO esta na lista continua barrado
        self.assertIsNotNone(m._ficha_valida(dict(dados, em_voo=voo))[1])


if __name__ == "__main__":
    unittest.main()
