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
HOJE = datetime.now().strftime("%Y-%m-%d")


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
        self.assertEqual({"h3"}, postar._fontes_cheias_hoje(linhas))

    def test_uma_parte_no_dia_nao_fecha(self):
        linhas = [_tiktok("h3:celular:p01", f"{HOJE}T10:00")]
        self.assertEqual(set(), postar._fontes_cheias_hoje(linhas))

    def test_ontem_nao_conta(self):
        """O teto e por DIA: amanha a mesma historia pode andar de novo."""
        linhas = [_tiktok("h3:celular:p01", "2026-09-16T10:00"),
                  _tiktok("h3:celular:p02", "2026-09-16T12:00")]
        self.assertEqual(set(), postar._fontes_cheias_hoje(linhas))

    def test_o_youtube_nao_conta_para_o_teto_do_tiktok(self):
        linhas = [{"video_id": "h3:celular:p01", "plataforma": "youtube",
                   "quando": f"{HOJE}T10:00", "titulo": "x", "url": "u"},
                  {"video_id": "h3:celular:p02", "plataforma": "youtube",
                   "quando": f"{HOJE}T12:00", "titulo": "y", "url": "u"}]
        self.assertEqual(set(), postar._fontes_cheias_hoje(linhas))

    def test_conta_os_DOIS_caminhos_juntos(self):
        """Rodada normal e recuperacao publicam no mesmo perfil: o teto e
        sobre o que o perfil recebeu, venha de onde vier."""
        linhas = [_tiktok("h3:celular:p01", f"{HOJE}T10:00"),   # normal
                  _tiktok("h3:celular:p05", f"{HOJE}T12:00")]   # recuperacao
        self.assertEqual({"h3"}, postar._fontes_cheias_hoje(linhas))


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


if __name__ == "__main__":
    unittest.main()
