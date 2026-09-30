# -*- coding: utf-8 -*-
"""O lote semanal na publicacao: frescor, piso e o aviso de quarta.

Decisoes do Adrian em 30/09/2026 (Grimorio `geral/lote-*`): historias de
seg a qua, builds de seg a ter, video de ate 6 dias (`lote-frescor`), piso de
reposicao de 2 dias = 20 videos (`lote-piso-de-reposicao`), 1o lote seg 05/10.

MEDIDO ANTES DO CONSERTO (30/09, 11:05):

- Estoque real de historias: nenhum video com mais de 6 dias (o mais velho, a
  h34, nasceu 26/09 10:08: 4,0 dias). A fila nova sai IGUAL a velha, parte
  por parte (31 partes): a h34 vira "vencendo", mas o rodizio de tipo ja a
  punha na frente da h41. O conserto e para a semana do lote, nao para hoje.
- Builds: 7 variantes B (generation_00030..00041) com 13,0 dias de mp4; o
  build ja sai do mais velho para o mais novo dentro do formato
  (`proximo_build`), entao elas saem primeiro — nao ha o que reordenar.
- Simulacao de 4 semanas de lote (semanas 2 a 4, 210 publicacoes), o que sai
  com mais de 6 dias: "a mais nova primeiro" 24 (pior 14,8 dias); vencendo
  sem folga 15 (pior 7,1); vencendo com 1 dia de folga 2 (pior 6,1); FIFO 2
  (pior 6,1). Os 2 restantes sao do volume do lote, e nao da ordem.
- `PISO_DE_ALERTA` era 1 DIA (10 videos) desde 10/09; o piso decidido e 20.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_lote", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    modulo._linha = lambda *_a, **_k: None
    return modulo


class _P:
    def __init__(self, fonte, parte, quando=0.0):
        self.fonte_id = fonte
        self.parte = parte
        self.id = f"{fonte}:celular:p{parte:02d}"
        self.perfil = "celular"
        self.titulo = f"{fonte} (Parte {parte}/6)"
        self.quando = quando


def _serie(fonte, partes=range(1, 7)):
    return [_P(fonte, p) for p in partes]


SEG = datetime(2026, 10, 5, 10, 0)          # 1o lote
QUA_22 = datetime(2026, 10, 7, 22, 0)


# ------------------------------------------------------------------ frescor
class VencendoTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()

    def test_conta_de_mao_seis_partes_vence_na_quarta_as_10(self):
        """Nascida seg 10:00, 6 partes (3 dias de grade) + 1 de folga: vence
        quando a idade chega a 2 dias, qua 10:00."""
        criado = {"h": SEG}
        pend = _serie("h")
        antes = SEG + timedelta(days=2) - timedelta(minutes=1)
        self.assertEqual(set(), self.m._series_vencendo(pend, criado, antes))
        self.assertEqual({"h"}, self.m._series_vencendo(
            pend, criado, SEG + timedelta(days=2)))

    def test_menos_partes_vence_mais_tarde(self):
        """2 partes saem num dia: vence com 4 dias (4 + 1 + 1 = 6)."""
        criado = {"h": SEG}
        pend = _serie("h", (5, 6))
        self.assertEqual(set(), self.m._series_vencendo(
            pend, criado, SEG + timedelta(days=3, hours=23)))
        self.assertEqual({"h"}, self.m._series_vencendo(
            pend, criado, SEG + timedelta(days=4)))

    def test_ZERO_nada_pendente_nada_vence(self):
        self.assertEqual(set(), self.m._series_vencendo([], {}, SEG))

    def test_sem_data_de_nascimento_nao_reordena(self):
        """"Nao sei" nunca reordena a fila."""
        self.assertEqual(set(), self.m._series_vencendo(
            _serie("h"), {"h": None}, SEG + timedelta(days=30)))


class OrdemPelaSerieTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()

    def _ordem(self, pend, comecadas, criado, agora):
        return [v.id for v in
                self.m._ordenar_pela_serie(pend, comecadas, criado, agora)]

    def test_na_quinta_do_lote_a_de_segunda_vem_antes_da_de_quarta(self):
        """O defeito: "a mais nova primeiro" deixava a historia de segunda
        para depois das de terca e quarta, a semana inteira."""
        agora = datetime(2026, 10, 8, 10, 0)            # quinta
        criado = {"historia_00010": SEG,                 # 3 dias: vence
                  "historia_00011": SEG + timedelta(days=1),   # 2: vence
                  "historia_00012": SEG + timedelta(days=2)}   # 1: nao
        pend = (_serie("historia_00012") + _serie("historia_00010")
                + _serie("historia_00011"))
        ordem = self._ordem(pend, set(), criado, agora)
        fontes = list(dict.fromkeys(i.split(":")[0] for i in ordem))
        self.assertEqual(["historia_00010", "historia_00011",
                          "historia_00012"], fontes)

    def test_sem_nada_vencendo_a_mais_nova_continua_primeiro(self):
        """A regra de 08/09 continua para o que esta fresco."""
        criado = {f: SEG for f in ("historia_00004", "historia_00008",
                                   "historia_00010")}
        pend = [_P("historia_00004", 1), _P("historia_00010", 1),
                _P("historia_00008", 1)]
        ordem = self._ordem(pend, set(), criado, SEG + timedelta(hours=1))
        self.assertEqual(["historia_00010", "historia_00008",
                          "historia_00004"],
                         [i.split(":")[0] for i in ordem])

    def test_a_COMECADA_continua_na_frente_da_vencendo(self):
        """Termina o que comecou: a vencendo passa as novas, nunca a
        comecada."""
        agora = SEG + timedelta(days=5)
        criado = {"historia_00020": SEG + timedelta(days=4),
                  "historia_00010": SEG}
        pend = _serie("historia_00010") + _serie("historia_00020", (3, 4))
        ordem = self._ordem(pend, {"historia_00020"}, criado, agora)
        self.assertEqual("historia_00020:celular:p03", ordem[0])

    def test_a_ordem_das_PARTES_sobrevive(self):
        agora = SEG + timedelta(days=4)
        criado = {"historia_00010": SEG}
        pend = [_P("historia_00010", p) for p in (4, 2, 6, 3, 5)]
        ordem = self._ordem(pend, set(), criado, agora)
        self.assertEqual([2, 3, 4, 5, 6], [int(i[-2:]) for i in ordem])

    def test_ZERO_fila_vazia(self):
        self.assertEqual([], self._ordem([], set(), {}, SEG))


class CriadoDaFonteTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()
        from contos.roteiro import roteiro as R
        self.R = R
        self.addCleanup(setattr, R, "carregar", R.carregar)

    def test_vale_o_criado_em_do_roteiro_e_nao_o_mp4(self):
        """O reparo re-renderiza: a h34 nasceu 26/09 e a p01 foi regravada
        em 29/09. O mtime faria a historia velha parecer nova."""
        self.R.carregar = lambda f: {"criado_em": "2026-09-26T10:08:30"}
        parte = _P("h", 1, quando=datetime(2026, 9, 29, 21, 19).timestamp())
        self.assertEqual(datetime(2026, 9, 26, 10, 8, 30),
                         self.m._criado_da_fonte("h", [parte]))

    def test_sem_roteiro_vale_o_mp4_mais_velho(self):
        def explode(_f):
            raise FileNotFoundError("sem roteiro")
        self.R.carregar = explode
        partes = [_P("h", 1, quando=datetime(2026, 9, 29).timestamp()),
                  _P("h", 2, quando=datetime(2026, 9, 26).timestamp())]
        self.assertEqual(datetime(2026, 9, 26),
                         self.m._criado_da_fonte("h", partes))

    def test_ZERO_sem_roteiro_e_sem_mp4_e_None(self):
        def explode(_f):
            raise FileNotFoundError("sem roteiro")
        self.R.carregar = explode
        self.assertIsNone(self.m._criado_da_fonte("h", [_P("h", 1)]))


class NaFilaDeVerdadeTests(unittest.TestCase):
    """A LIGACAO na `fila_de_historias`, com catalogo e ledger de mentira."""

    def setUp(self):
        from contos.publicar import catalogo, serie
        self.m = _postar()
        self.addCleanup(setattr, catalogo, "listar", catalogo.listar)
        self.addCleanup(setattr, serie, "publicados", serie.publicados)
        self.catalogo, self.serie = catalogo, serie
        self.m._tipo_da_fonte = lambda f: "favela"       # um tipo so
        self.m._prioridades = lambda: []

    def test_a_velha_que_vence_sai_antes_da_nova(self):
        agora = datetime.now()
        criado = {"historia_00010": agora - timedelta(days=4),
                  "historia_00012": agora - timedelta(hours=2)}
        self.m._criado_da_fonte = lambda f, partes=(): criado[f]
        self.catalogo.listar = lambda: (_serie("historia_00010")
                                        + _serie("historia_00012"))
        self.serie.publicados = lambda: []
        fila = self.m.fila_de_historias()
        self.assertEqual("historia_00010:celular:p01", fila[0].id)

    def test_a_fila_chama_a_ordem_de_frescor(self):
        fonte = inspect.getsource(self.m.fila_de_historias)
        sem_comentario = "\n".join(
            l for l in fonte.splitlines() if not l.strip().startswith("#"))
        self.assertIn("_ordenar_pela_serie(", sem_comentario)
        self.assertLess(fonte.find("_ordenar_pela_serie("),
                        fonte.find("_sem_fonte_cheia("),
                        "o teto por fonte continua valendo depois da ordem")


# --------------------------------------------------------------------- piso
class PisoTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()
        from contos.pipeline import agenda
        from builds.pipeline import noite
        self.agenda, self.noite = agenda, noite
        self.addCleanup(setattr, agenda, "carregar", agenda.carregar)
        self.addCleanup(setattr, noite, "carregar", noite.carregar)

    def test_nao_ha_mais_numero_magico(self):
        self.assertFalse(hasattr(self.m, "PISO_DE_ALERTA"),
                         "o piso era 1 dia fixo no codigo")

    def test_o_piso_vivo_e_o_do_config_de_quem_cria(self):
        """Mesma fonte da agenda: o alerta e a criacao concordam."""
        esperado = self.agenda.piso_de_reposicao(self.agenda.carregar())
        self.assertEqual(esperado, self.m.piso_de_alerta("historias"))

    def test_segue_o_config(self):
        self.agenda.carregar = lambda: {"piso_de_reposicao": 30}
        self.noite.carregar = lambda: {}
        self.assertEqual(30, self.m.piso_de_alerta("historias"))
        self.assertEqual(30, self.m.piso_de_alerta("builds"),
                         "a decisao e geral: sem piso proprio, o mesmo")
        self.noite.carregar = lambda: {"piso_de_reposicao": 15}
        self.assertEqual(15, self.m.piso_de_alerta("builds"))

    def test_config_ilegivel_da_os_2_dias_da_decisao(self):
        def explode():
            raise OSError("sem config")
        self.agenda.carregar = explode
        self.assertEqual(2 * len(self.m.HORAS_PADRAO),
                         self.m.piso_de_alerta("historias"))


class EstoqueDoLoteTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()
        self.m.piso_de_alerta = lambda canal: 20

    def test_quarta_22h_o_alvo_e_o_da_agenda(self):
        """44 horarios ate seg 12/10 07h + 20 = 64 (conta da agenda)."""
        from contos.pipeline import agenda
        lote = self.m.estoque_do_lote(QUA_22, {"historias": 25})
        f = lote["historias"]
        self.assertEqual(44, f["horarios"])
        self.assertEqual(agenda.alvo_do_lote(agenda.carregar(), QUA_22),
                         f["alvo"])
        self.assertEqual(64, f["alvo"])
        self.assertEqual(39, f["faltam"])
        self.assertEqual(datetime(2026, 10, 12, 7, 0), f["fim"])
        self.assertAlmostEqual(2.5, f["dias"])
        self.assertFalse(f["magro"])

    def test_ZERO_e_magro_e_falta_tudo(self):
        f = self.m.estoque_do_lote(QUA_22, {"builds": 0})["builds"]
        self.assertTrue(f["magro"])
        self.assertEqual(64, f["faltam"])

    def test_abaixo_de_20_e_magro_mesmo_com_um_dia(self):
        """Com o piso velho (1 dia), 12 videos NAO avisavam."""
        f = self.m.estoque_do_lote(QUA_22, {"historias": 12})["historias"]
        self.assertTrue(f["magro"])

    def test_nao_contou_nao_e_magro_nem_falta(self):
        f = self.m.estoque_do_lote(QUA_22, {"historias": -1})["historias"]
        self.assertFalse(f["magro"])
        self.assertIsNone(f["faltam"])
        self.assertEqual(64, f["alvo"])

    def test_as_linhas_do_ver(self):
        lote = self.m.estoque_do_lote(QUA_22, {"historias": 12, "builds": 70})
        texto = "\n".join(self.m.linhas_do_estoque(lote))
        self.assertIn("12 video(s) = 1,2 dia(s)", texto)
        self.assertIn("<<< ABAIXO DO PISO (20 videos)", texto)
        self.assertIn("ate seg 12/10 07h: 44 horario(s) = 4,4 dia(s)", texto)
        self.assertIn("alvo 64 -> faltam 52", texto)
        self.assertIn("alvo 64 -> cobre", texto)

    def test_o_ver_imprime_as_linhas_e_o_frescor(self):
        fonte = inspect.getsource(self.m.main)
        self.assertIn("linhas_do_estoque(estoque_do_lote())", fonte)
        self.assertIn("frescor_do_estoque()", fonte)


class AvisoDoEstoqueTests(unittest.TestCase):
    """O aviso de toda rodada fala do piso decidido, em videos."""

    def _texto(self, pendentes):
        import subprocess
        m = _postar()
        m.pendentes_por_canal = lambda: dict(pendentes)
        m.retidos_por_canal = lambda: {}
        m.estoque_por_formato = lambda por_dia=None: {}
        m.piso_de_alerta = lambda canal: 20
        m._conta_do_destino = lambda servico, canal: "conta"
        enviado = []
        original = subprocess.run

        def run(args, *a, **k):
            if "--avisar" in list(args):
                enviado.append(args[-1])
            return type("R", (), {"returncode": 0})()
        subprocess.run = run
        try:
            m.avisar([])
        finally:
            subprocess.run = original
        return enviado[0]

    def test_ZERO_avisa(self):
        texto = self._texto({"historias": 0, "builds": 25})
        self.assertIn("abaixo do piso de reposição", texto)
        self.assertIn("histórias (0 de 20)", texto)
        self.assertNotIn("builds (25", texto)

    def test_folgado_nao_avisa(self):
        texto = self._texto({"historias": 30, "builds": 25})
        self.assertNotIn("abaixo do piso", texto)
        self.assertIn("30 vídeo(s), 3,0 dia(s)", texto)


# ------------------------------------------------------ "o lote nao fechou"
def _config():
    from contos.pipeline import agenda
    return agenda.carregar()


class FechamentoTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()
        self.c = _config()

    def test_a_noite_de_quarta(self):
        f = self.m._fechamento_do_lote
        self.assertIsNone(f(self.c, datetime(2026, 10, 7, 21, 59)))
        for agora in (datetime(2026, 10, 7, 22, 0),
                      datetime(2026, 10, 7, 22, 37),
                      datetime(2026, 10, 8, 0, 37),
                      datetime(2026, 10, 8, 6, 37)):
            self.assertEqual(QUA_22, f(self.c, agora), agora)
        self.assertIsNone(f(self.c, datetime(2026, 10, 8, 7, 0)))
        self.assertIsNone(f(self.c, datetime(2026, 10, 6, 22, 37)),
                          "terca nao e o ultimo dia de lote")

    def test_antes_do_primeiro_lote_nao_ha_o_que_fechar(self):
        """Hoje (qua 30/09) e antes de `lote_a_partir_de` (05/10)."""
        self.assertIsNone(self.m._fechamento_do_lote(
            self.c, datetime(2026, 9, 30, 22, 37)))


class LoteNaoFechouTests(unittest.TestCase):
    def setUp(self):
        self.m = _postar()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        pasta = Path(self.tmp.name)
        self.m._arquivo_do_aviso_do_lote = (
            lambda canal: pasta / canal / "_lote_avisado.json")
        self.enviados = []
        self.aceita = True

        def mandar(texto):
            self.enviados.append(texto)
            return self.aceita
        self.m._mandar_no_telegram = mandar
        self.c = _config()

    def _lote(self, historias, builds):
        self.m.piso_de_alerta = lambda canal: 20
        return self.m.estoque_do_lote(QUA_22, {"historias": historias,
                                               "builds": builds})

    def _rodar(self, agora, lote):
        return self.m.avisar_lote_nao_fechou(agora, lote=lote, config=self.c)

    def test_ZERO_avisa_os_dois_canais(self):
        feitos = self._rodar(datetime(2026, 10, 7, 22, 37), self._lote(0, 0))
        self.assertEqual(["historias", "builds"], feitos)
        self.assertIn("O lote da semana não fechou", self.enviados[0])
        self.assertIn("0 vídeo(s) prontos; o alvo era 64", self.enviados[0])
        self.assertIn("Faltam 64", self.enviados[0])

    def test_uma_vez_por_semana_por_canal(self):
        self._rodar(datetime(2026, 10, 7, 22, 37), self._lote(40, 70))
        self.assertEqual(1, len(self.enviados))
        self.assertNotIn("builds", self.enviados[0].split("\n", 2)[2]
                         .split("De quinta")[0])
        # 23:37 e 00:37 da mesma noite: nada de novo
        self._rodar(datetime(2026, 10, 7, 23, 37), self._lote(40, 70))
        self._rodar(datetime(2026, 10, 8, 0, 37), self._lote(40, 70))
        self.assertEqual(1, len(self.enviados))
        # o builds cai abaixo do alvo na mesma noite: ele ainda nao foi avisado
        self._rodar(datetime(2026, 10, 8, 0, 37), self._lote(40, 10))
        self.assertEqual(2, len(self.enviados))
        self.assertIn("builds", self.enviados[1])
        self.assertNotIn("histórias", self.enviados[1])
        # a semana seguinte avisa de novo
        feitos = self._rodar(datetime(2026, 10, 14, 22, 37),
                             self._lote(40, 70))
        self.assertEqual(["historias"], feitos)

    def test_bateu_o_alvo_nao_avisa(self):
        self.assertEqual([], self._rodar(datetime(2026, 10, 7, 22, 37),
                                         self._lote(64, 90)))
        self.assertEqual([], self.enviados)

    def test_telegram_que_falhou_tenta_na_proxima_rodada(self):
        self.aceita = False
        self.assertEqual([], self._rodar(datetime(2026, 10, 7, 22, 37),
                                         self._lote(0, 90)))
        self.aceita = True
        self.assertEqual(["historias"], self._rodar(
            datetime(2026, 10, 7, 23, 37), self._lote(0, 90)))

    def test_nao_contou_avisa_dizendo_isso(self):
        """Silencio nao pode parecer "fechou"."""
        feitos = self._rodar(datetime(2026, 10, 7, 22, 37),
                             self._lote(-1, 90))
        self.assertEqual(["historias"], feitos)
        self.assertIn("não deu para contar", self.enviados[0])

    def test_fora_da_noite_de_quarta_nem_conta_o_estoque(self):
        """O relogio vem antes: contar o estoque decodifica mp4."""
        def nao_era_para_contar(*_a, **_k):
            raise AssertionError("contou o estoque fora da noite de quarta")
        self.m.estoque_do_lote = nao_era_para_contar
        for agora in (datetime(2026, 10, 7, 20, 37),
                      datetime(2026, 10, 8, 9, 37),
                      datetime(2026, 9, 30, 22, 37)):
            self.assertEqual([], self.m.avisar_lote_nao_fechou(
                agora, config=self.c))
        self.assertEqual([], self.enviados)

    def test_a_marca_mora_ao_lado_do_ledger(self):
        m = _postar()
        from builds.publicar import metricas
        self.assertEqual(metricas.registro_do_canal("historias").parent,
                         m._arquivo_do_aviso_do_lote("historias").parent)

    def test_so_a_rodada_de_verdade_avisa(self):
        fonte = inspect.getsource(self.m.main)
        trecho = fonte[fonte.index("if not args.ver:\n        avisar("):]
        self.assertIn("avisar_lote_nao_fechou()", trecho[:600])


if __name__ == "__main__":
    unittest.main()
