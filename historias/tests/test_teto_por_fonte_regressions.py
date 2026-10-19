"""Uma historia nao ocupa o perfil inteiro: teto por fonte e rodizio.

17/09/2026, decisao do Adrian depois de ver o perfil. Em 16/09 sairam 16
posts no TikTok e DUAS historias ocuparam onze deles — a h3 com as partes 1 a
6 e a h16 com 1 a 5, alternando a cada rodada.

NENHUMA parte foi repetida: conferido contra a lista do Studio, 50 itens e 50
combinacoes (historia, parte) distintas. O que aconteceu foi pior de explicar
e igual de ver: a recuperacao andava "uma por rodada" e a fila estava
ordenada por data, entao ela despejou uma serie inteira em seis horas. Como
as partes de uma serie compartilham o COMECO da legenda — so diferem no
"Parte N de M" no meio do texto — o perfil ficou com seis blocos de texto
quase identico.

O comentario original da recuperacao dizia "os 14 de uma vez virariam
enxurrada no perfil". Eu evitei os 14 de uma vez e produzi 6 em seis horas.

Duas travas, e elas atacam coisas diferentes:

- **Teto por fonte no dia** limita o VOLUME: no maximo 2 por historia,
  contando tudo que sai no TikTok naquele dia (rodada normal + recuperacao),
  porque os dois caminhos publicam no mesmo perfil.
- **Rodizio** conserta a ORDEM: alterna entre fontes em vez de esgotar uma.

A ordem das partes DENTRO de cada historia continua sagrada: quem viu a parte
2 e nunca recebe a 3 e o pior resultado possivel, pior que qualquer atraso.
"""
import importlib.util
import unittest
from datetime import datetime
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_teto", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


postar = _postar()
# UM DIA FIXO, e nao `datetime.now()`: desde 29/09/2026 o teto conta pelo DIA
# DE GRADE (06:37 -> 00:37). Com "hoje" do relogio, a suite rodada as 03:00
# poria as linhas das 10:00 num dia de grade que ainda nem abriu.
HOJE = "2026-09-29"
AGORA = datetime(2026, 9, 29, 15, 40)


class _V:
    def __init__(self, vid):
        self.id, self.perfil = vid, "celular"
        self.titulo = vid


def _tiktok(vid, quando):
    return {"video_id": vid, "plataforma": "tiktok", "quando": quando,
            "titulo": vid, "url": "http://x"}


class TetoPorFonteTests(unittest.TestCase):
    def test_duas_partes_no_dia_fecham_a_fonte(self):
        linhas = [_tiktok("h3:celular:p01", f"{HOJE}T10:00"),
                  _tiktok("h3:celular:p02", f"{HOJE}T12:00")]
        self.assertEqual({"h3"}, postar._fontes_cheias_hoje(linhas, agora=AGORA))

    def test_uma_parte_no_dia_nao_fecha(self):
        linhas = [_tiktok("h3:celular:p01", f"{HOJE}T10:00")]
        self.assertEqual(set(), postar._fontes_cheias_hoje(linhas, agora=AGORA))

    def test_ontem_nao_conta(self):
        """O teto e por DIA: amanha a mesma historia pode andar de novo."""
        linhas = [_tiktok("h3:celular:p01", "2026-09-16T10:00"),
                  _tiktok("h3:celular:p02", "2026-09-16T12:00")]
        self.assertEqual(set(), postar._fontes_cheias_hoje(linhas, agora=AGORA))

    def test_o_youtube_nao_conta_para_o_teto_do_tiktok(self):
        linhas = [{"video_id": "h3:celular:p01", "plataforma": "youtube",
                   "quando": f"{HOJE}T10:00", "titulo": "x", "url": "u"},
                  {"video_id": "h3:celular:p02", "plataforma": "youtube",
                   "quando": f"{HOJE}T12:00", "titulo": "y", "url": "u"}]
        self.assertEqual(set(), postar._fontes_cheias_hoje(linhas, agora=AGORA))

    def test_conta_os_DOIS_caminhos_juntos(self):
        """Rodada normal e recuperacao publicam no mesmo perfil: o teto e
        sobre o que o perfil recebeu, venha de onde vier."""
        linhas = [_tiktok("h3:celular:p01", f"{HOJE}T10:00"),   # normal
                  _tiktok("h3:celular:p05", f"{HOJE}T12:00")]   # recuperacao
        self.assertEqual({"h3"}, postar._fontes_cheias_hoje(linhas, agora=AGORA))


class TetoNaRodadaNORMALTests(unittest.TestCase):
    """O teto vale para o PERFIL INTEIRO (decisao do Adrian, 17/09).

    Ele so valia em `_fila_do_tiktok`, ou seja, na recuperacao e na reserva.
    A rodada NORMAL — que leva a parte do horario aos dois destinos — nao
    passava por ele, e a fila de historias prefere "terminar a serie
    comecada": sozinha, uma historia ocupava ate seis horarios num dia. Foi
    parte do que ele viu em 16/09, e nao so a recuperacao.
    """

    def setUp(self):
        self.addCleanup(setattr, postar, "_publicados_do_canal",
                        postar._publicados_do_canal)
        self.addCleanup(setattr, postar, "_linha", postar._linha)
        postar._linha = lambda *_a, **_k: None

    def _fila(self, ids, ledger):
        postar._publicados_do_canal = lambda _c: ledger
        return [v.id for v in postar._sem_fonte_cheia(
            [_V(i) for i in ids], "historias", agora=AGORA)]

    def test_historia_que_ja_saiu_duas_vezes_hoje_sai_da_fila(self):
        ledger = [_tiktok("h3:celular:p01", f"{HOJE}T10:00"),
                  _tiktok("h3:celular:p02", f"{HOJE}T12:00")]
        self.assertEqual(["h4:celular:p01"],
                         self._fila(["h3:celular:p03", "h4:celular:p01"],
                                    ledger))

    def test_o_teto_conta_o_YOUTUBE_tambem(self):
        """Basta um destino cheio: publicar so no outro deixaria a serie meio
        publicada, com a parte N num lugar e nao no outro."""
        ledger = [{"video_id": "h3:celular:p01", "plataforma": "youtube",
                   "quando": f"{HOJE}T10:00", "titulo": "x", "url": "u"},
                  {"video_id": "h3:celular:p02", "plataforma": "youtube",
                   "quando": f"{HOJE}T12:00", "titulo": "y", "url": "u"}]
        self.assertEqual([], self._fila(["h3:celular:p03"], ledger))

    def test_uma_saida_hoje_nao_barra(self):
        ledger = [_tiktok("h3:celular:p01", f"{HOJE}T10:00")]
        self.assertEqual(["h3:celular:p02"],
                         self._fila(["h3:celular:p02"], ledger))

    def test_TODAS_cheias_devolve_vazio(self):
        """Horario sem post e melhor que empilhar a mesma serie."""
        ledger = [_tiktok("h3:celular:p01", f"{HOJE}T10:00"),
                  _tiktok("h3:celular:p02", f"{HOJE}T12:00")]
        self.assertEqual([], self._fila(["h3:celular:p03"], ledger))

    def test_ledger_ilegivel_NAO_barra_a_rodada(self):
        def explode(_c):
            raise OSError("ledger ilegivel")
        postar._publicados_do_canal = explode
        self.assertEqual(
            ["h3:celular:p01"],
            [v.id for v in postar._sem_fonte_cheia(
                [_V("h3:celular:p01")], "historias")])


class SoContaOQueSaiuTests(unittest.TestCase):
    def test_linha_nao_publicada_nao_fecha_a_fonte(self):
        """Tentativa que falhou nao ocupa lugar no perfil."""
        linhas = [{"video_id": "h3:celular:p01", "plataforma": "tiktok",
                   "quando": f"{HOJE}T10:00", "titulo": "x",
                   "url": "", "publicado": False},
                  {"video_id": "h3:celular:p02", "plataforma": "tiktok",
                   "quando": f"{HOJE}T12:00", "titulo": "y",
                   "url": "", "publicado": False}]
        self.assertEqual(set(), postar._fontes_cheias_hoje(linhas, agora=AGORA))


class RodizioTests(unittest.TestCase):
    def test_alterna_entre_historias(self):
        fila = [_V("h3:p01"), _V("h3:p02"), _V("h3:p03"),
                _V("h4:p01"), _V("h4:p02")]
        self.assertEqual(
            ["h3:p01", "h4:p01", "h3:p02", "h4:p02", "h3:p03"],
            [v.id for v in postar._em_rodizio(fila)])

    def test_a_ordem_das_partes_DENTRO_da_historia_e_preservada(self):
        """A regra sagrada: quem viu a 2 tem de receber a 3."""
        fila = [_V("h3:p01"), _V("h3:p02"), _V("h3:p03"), _V("h4:p01")]
        saida = [v.id for v in postar._em_rodizio(fila)]
        so_h3 = [v for v in saida if v.startswith("h3")]
        self.assertEqual(["h3:p01", "h3:p02", "h3:p03"], so_h3)

    def test_uma_fonte_so_nao_muda_nada(self):
        fila = [_V("h3:p01"), _V("h3:p02")]
        self.assertEqual(["h3:p01", "h3:p02"],
                         [v.id for v in postar._em_rodizio(fila)])

    def test_fila_vazia(self):
        self.assertEqual([], postar._em_rodizio([]))

    def test_nenhum_video_se_perde(self):
        fila = [_V(f"h{n}:p{p:02d}") for n in (3, 4, 5) for p in (1, 2, 3)]
        self.assertEqual({v.id for v in fila},
                         {v.id for v in postar._em_rodizio(fila)})


def _parte(n, quando):
    return _tiktok(f"historia_00037:celular:p{n:02d}", quando)


class DiaDeGradeTests(unittest.TestCase):
    """O teto de 2 por serie conta pelo DIA DE GRADE, o mesmo da guarda de um
    por horario (decisao do Adrian `teto-por-fonte-dia-de-grade`, 29/09/2026).

    Medido no ledger de historias: a `historia_00037` saiu TRES vezes no dia
    de grade de 28/09 — p01 as 09:43, p02 as 12:10 (28/09) e p03 as 00:38
    (29/09), nos dois destinos. A rodada das 00:37 contava pelo calendario:
    29/09 so tinha comecado, a h37 tinha zero saidas "hoje", e a terceira
    parte do dia foi ao ar. O dia de grade vai das 06:37 as 00:37 do dia
    seguinte (`conferencia.chave_do_horario`): o post das 00:37 FECHA o dia
    anterior e nao abre o seguinte.
    """

    def test_o_caso_medido_a_rodada_das_00h37_ve_a_serie_cheia(self):
        linhas = [_parte(1, "2026-09-28T09:43:10"),
                  _parte(2, "2026-09-28T12:10:05")]
        agora = datetime(2026, 9, 29, 0, 37, 20)
        self.assertEqual({"historia_00037"},
                         postar._fontes_cheias_hoje(linhas, agora=agora))
        no_youtube = [dict(l, plataforma="youtube") for l in linhas]
        self.assertEqual({"historia_00037"}, postar._fontes_cheias_hoje(
            no_youtube, "youtube", agora=agora))

    def test_a_parte_das_00h37_conta_para_o_dia_ANTERIOR(self):
        """p03 as 00:38 de 29/09 e p04 as 09:40 de 29/09: no calendario sao
        duas "hoje" e a serie fecharia ao meio-dia; no dia de grade, a das
        00:38 e do dia 28 e o dia 29 so tem uma."""
        linhas = [_parte(3, "2026-09-29T00:38:40"),
                  _parte(4, "2026-09-29T09:40:00")]
        agora = datetime(2026, 9, 29, 12, 7, 30)
        self.assertEqual(set(),
                         postar._fontes_cheias_hoje(linhas, agora=agora))
        self.assertEqual({"historia_00037": 1},
                         dict(postar._saidas_hoje(linhas, "tiktok", agora)))

    def test_a_madrugada_ainda_e_o_dia_de_grade_anterior(self):
        """Recuperacao atrasada as 03:00 paga o dia que ainda nao abriu o
        seguinte (o proximo abre as 06:37)."""
        linhas = [_parte(1, "2026-09-28T20:40:00"),
                  _parte(2, "2026-09-29T03:00:00")]
        self.assertEqual({"historia_00037"}, postar._fontes_cheias_hoje(
            linhas, agora=datetime(2026, 9, 29, 5, 0)))
        self.assertEqual(set(), postar._fontes_cheias_hoje(
            linhas, agora=datetime(2026, 9, 29, 6, 37, 30)))

    def test_ZERO_ledger_vazio_nao_fecha_nada(self):
        self.assertEqual(set(), postar._fontes_cheias_hoje([], agora=AGORA))
        self.assertEqual({}, dict(postar._saidas_hoje([], "tiktok", AGORA)))
        self.assertEqual(set(), postar._fontes_cheias_hoje(None, agora=AGORA))

    def test_ZERO_nada_no_dia_de_grade_corrente(self):
        """Ledger cheio de ontem e hoje vazio: nenhuma serie esta cheia."""
        linhas = [_parte(1, "2026-09-28T09:43:10"),
                  _parte(2, "2026-09-28T12:10:05"),
                  _parte(3, "2026-09-29T00:38:40")]
        self.assertEqual(set(), postar._fontes_cheias_hoje(
            linhas, agora=datetime(2026, 9, 29, 6, 40)))

    def test_linha_sem_data_legivel_nao_conta_nem_derruba(self):
        linhas = [_parte(1, ""), _parte(2, "ontem, acho"),
                  _parte(3, f"{HOJE}T10:00")]
        self.assertEqual({"historia_00037": 1},
                         dict(postar._saidas_hoje(linhas, "tiktok", AGORA)))

    def test_sem_agora_conta_pelo_dia_de_grade_do_relogio(self):
        """Os chamadores de verdade nao passam `agora`: vale o relogio."""
        from builds.publicar import conferencia
        dia = conferencia.chave_do_horario(datetime.now(), "tiktok")[0]
        linhas = [_parte(1, f"{dia:%Y-%m-%d}T09:40:00"),
                  _parte(2, f"{dia:%Y-%m-%d}T12:10:00")]
        self.assertEqual({"historia_00037"}, postar._fontes_cheias_hoje(linhas))


if __name__ == "__main__":
    unittest.main()
