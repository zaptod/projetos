"""O aviso de falta de variedade compara com o RESTO do dia, nao com o dia.

MEDIDO EM 28/09/2026: o log do `postar.py` tinha 164 avisos "so N serie(s)
elegivel(is) hoje, e o dia precisa de 5" (82 com N=3, 59 com N=4, 21 com
N=2, 2 com N=1). A conta era sempre contra os 10 horarios do dia inteiro,
a qualquer hora: as 21:37, com tres horarios pela frente (21:37, 22:37,
23:37), quatro series que entregam duas partes cada cobrem 8 — e o aviso
dizia que faltava. E sem nenhuma fonte cheia ele nem era avaliado.

Conta de mao do caso da noite (o do log): as 21:37 venceram 8 horarios e
nada saiu no de 21:37 ainda, entao restam 2 + 1 = 3; quatro series livres
com duas partes aprovadas cada entregam 4 x 2 = 8 >= 3 -> SEM aviso.
De manha (06:37), tres series de duas partes: restam 10 - 2 + 1 = 9 e
cobrem 6 -> COM aviso "cobrem 6 dos 9".
"""
import importlib.util
import unittest
from datetime import datetime
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_variedade", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


postar = _postar()
postar._linha = lambda *_a, **_k: None
DIA = "2026-09-28"


class _V:
    def __init__(self, fonte, parte):
        self.fonte_id, self.parte = fonte, parte
        self.id = f"{fonte}:celular:p{parte:02d}"
        self.perfil, self.titulo = "celular", self.id


def _saiu(fonte, parte, hora, plataforma="youtube", dia=DIA):
    return {"video_id": f"{fonte}:celular:p{parte:02d}",
            "plataforma": plataforma, "quando": f"{dia}T{hora}:00",
            "titulo": f"{fonte} p{parte}", "url": "https://youtu.be/x",
            "publicado": True, "estado": "publicado"}


def _em(hora, minuto):
    return datetime(2026, 9, 28, hora, minuto)


def _series(*fontes, partes=(3, 4)):
    return [_V(f, p) for f in fontes for p in partes]


def _no_ar(*fontes, ate=2):
    """As partes 1..ate de cada fonte, em dias anteriores."""
    return [_saiu(f, p, "10:00", dia="2026-09-20")
            for f in fontes for p in range(1, ate + 1)]


class HorariosQueRestamTests(unittest.TestCase):
    def test_2137_sem_nada_no_horario_restam_tres(self):
        self.assertEqual(3, postar._horarios_que_restam([], _em(21, 37)))

    def test_2137_ja_publicado_restam_dois(self):
        feito = [_saiu("historia_00031", 3, "21:39")]
        self.assertEqual(2, postar._horarios_que_restam(feito, _em(21, 50)))

    def test_o_disparo_que_cruza_a_hora_conta_no_proprio_horario(self):
        """17:57 publica as 18:01: `grade.slot` diz 17, e o horario esta
        feito — a hora do relogio (18) diria que nao."""
        feito = [_saiu("historia_00031", 3, "18:01")]
        self.assertEqual(4, postar._horarios_que_restam(feito, _em(18, 30)))
        self.assertEqual(5, postar._horarios_que_restam([], _em(18, 30)))

    def test_fim_do_dia_depois_do_ultimo_post_nao_resta_nada(self):
        feito = [_saiu("historia_00031", 3, "23:39")]
        self.assertEqual(0, postar._horarios_que_restam(feito, _em(23, 50)))

    def test_antes_do_primeiro_horario_o_dia_inteiro(self):
        self.assertEqual(10, postar._horarios_que_restam([], _em(0, 10)))

    def test_publicacao_que_nao_saiu_nao_fecha_o_horario(self):
        falha = dict(_saiu("historia_00031", 3, "21:39"), publicado=False,
                     url="", estado="nao_subiu")
        self.assertEqual(3, postar._horarios_que_restam([falha], _em(21, 50)))


class AvisoDeVariedadeTests(unittest.TestCase):
    FONTES = ("historia_00031", "historia_00033", "historia_00034",
              "historia_00035")

    def test_noite_quatro_series_tres_horarios_SEM_aviso(self):
        """O caso do log: 'so 4 ... precisa de 5' as 21:37 era falso."""
        fila = _series(*self.FONTES)
        publicados = _no_ar(*self.FONTES)
        self.assertEqual("", postar._avisar_variedade(
            "historias", fila, publicados, _em(21, 37)))

    def test_manha_tres_series_nove_horarios_COM_aviso(self):
        fontes = self.FONTES[:3]
        frase = postar._avisar_variedade(
            "historias", _series(*fontes), _no_ar(*fontes), _em(6, 37))
        self.assertIn("cobrem 6 dos 9", frase)
        self.assertIn("so 3 serie(s)", frase)

    def test_ultimo_horario_uma_serie_basta(self):
        fila = [_V("historia_00031", 3)]
        self.assertEqual("", postar._avisar_variedade(
            "historias", fila, _no_ar("historia_00031"), _em(23, 37)))

    def test_fim_do_dia_ja_servido_nao_avisa_nem_com_zero(self):
        feito = [_saiu("historia_00031", 3, "23:39")]
        self.assertEqual("", postar._avisar_variedade(
            "historias", [], feito, _em(23, 50)))

    def test_ZERO_series_com_horario_pela_frente_AVISA(self):
        """O aviso antigo exigia `fontes` nao vazio: com todas as series
        cheias ele se calava justamente quando a falta era total."""
        frase = postar._avisar_variedade("historias", [], [], _em(21, 37))
        self.assertIn("cobrem 0 dos 3", frase)

    def test_serie_que_ja_saiu_hoje_entrega_so_mais_uma(self):
        """21:37, tres horarios; duas series, cada uma ja saiu 1x hoje:
        entregam 1 + 1 = 2 < 3."""
        fontes = self.FONTES[:2]
        publicados = _no_ar(*fontes) + [
            _saiu(f, 3, "12:09") for f in fontes]
        fila = _series(*fontes, partes=(4, 5))
        frase = postar._avisar_variedade("historias", fila, publicados,
                                         _em(21, 37))
        self.assertIn("cobrem 2 dos 3", frase)

    def test_conta_o_destino_mais_cheio(self):
        """Saiu 1x no TikTok e 0x no YouTube: o teto do TikTok manda."""
        fonte = self.FONTES[0]
        publicados = _no_ar(fonte) + [_saiu(fonte, 3, "12:09", "tiktok")]
        cap = postar._capacidade_de_hoje(_series(fonte, partes=(3, 4)),
                                         publicados, _em(21, 37))
        # A p03 conta como no ar (qualquer destino); a p04 e a unica que
        # falta, e o TikTok ja levou uma hoje: entrega 1.
        self.assertEqual(1, cap["capacidade"])

    def test_parte_que_falta_segura_a_serie(self):
        """Proxima parte (p03) fora da fila: a serie nao entrega nada."""
        fila = [_V("historia_00031", 4), _V("historia_00031", 5)]
        cap = postar._capacidade_de_hoje(fila, _no_ar("historia_00031"),
                                         _em(21, 37))
        self.assertEqual(0, cap["capacidade"])

    def test_builds_nao_sei_contar_nao_avisa(self):
        class _B:
            id, fonte_id, parte = "generation_00083:build:celular", "generation_00083", 0
        self.assertIsNone(postar._capacidade_de_hoje([_B()], [], _em(9, 37)))
        self.assertEqual("", postar._avisar_variedade("builds", [_B()], [],
                                                      _em(9, 37)))


if __name__ == "__main__":
    unittest.main()
