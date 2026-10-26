# -*- coding: utf-8 -*-
"""26/10/2026: a serie de videos do Blue Lock (canal `bluelock`).

Pedido do Adrian: publicar a serie sobre a criacao do simulador dele, um
episodio por dia, nas contas do antigo zombie. A fonte e uma pasta de JSON com
a marca de aprovado pelo conferente, amarrada ao arquivo por sha256.

Caso medido: o episodio 1 (`EP01_v6.mp4`, 69,5 s, 18 490 576 bytes, sha256
81559b22...) com o titulo e a descricao aprovados. Contas de mao:
  - sem JSON nenhum (caso ZERO): fila vazia, sem erro e sem alarme;
  - ep1 aprovado e ledger vazio: o proximo e o ep1;
  - ep1 ja publicado no YouTube e nao no TikTok: o YouTube espera o ep2 (que
    nao existe: horario vazio) e o TikTok leva o ep1;
  - ep2 aprovado sem o ep1 publicado: o ep2 NAO sai (a ordem manda).
"""
from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from builds.publicar import serie_bluelock as S

TITULO = "Esse jogador parou. Ninguém mandou. 🤔 | Como eu criei um Blue Lock #1"
DESCRICAO = ("Ninguém controla os jogadores do meu simulador de Blue Lock: "
             "cada um decide sozinho, só com o que vê. Episódio 1 da série "
             "sobre como eu criei o jogo. Segue pra ver o episódio 2: o replay.")


def _titulo(numero: int) -> str:
    """Cada episodio tem o SEU gancho: `titulos.chave` corta o titulo em 60
    letras e nao enxerga o `#N` do fim (medido: o gancho do ep1 com `#2` da a
    MESMA chave) — titulo que so troca o numero e repeticao, e barra."""
    if numero == 1:
        return TITULO
    return f"Gancho do episodio {numero} | Como eu criei um Blue Lock #{numero}"


TAGS = ["#bluelock", "#futebol", "#simulador", "#anime", "#isagi", "#bachira"]


def _ficha(pasta: Path, numero: int = 1, **mudar) -> Path:
    mp4 = pasta / f"EP{numero:02d}.mp4"
    if not mp4.exists():
        mp4.write_bytes(b"video aprovado " + bytes([numero]))
    dados = {"episodio": numero, "arquivo": str(mp4),
             "sha256": S.sha256_de(mp4),
             "titulo": _titulo(numero),
             "descricao": DESCRICAO, "tags": TAGS, "idioma": "pt",
             "aprovado_por_conferente": True}
    dados.update(mudar)
    destino = pasta / f"ep{numero:02d}.json"
    destino.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return destino


def _linha(numero: int, plataforma: str, quando: str, **mais) -> dict:
    linha = {"quando": quando, "plataforma": plataforma,
             "url": "publicado no YouTube", "video_id": f"bluelock_ep{numero:02d}",
             "titulo": _titulo(numero), "publicado": True}
    linha.update(mais)
    return linha


class FonteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)

    def test_pasta_que_nao_existe_e_fila_vazia_sem_erro(self):
        """O caso ZERO: nada aprovado nao e erro nem alarme."""
        aprovados, fora = S.episodios(self.pasta / "nao_existe")
        self.assertEqual((aprovados, fora), ([], []))
        ep, motivo = S.escolher("youtube", [], [], set(), date(2026, 10, 26))
        self.assertIsNone(ep)
        self.assertIn("episodio 1", motivo)

    def test_so_entra_o_aprovado_e_amarrado_ao_arquivo(self):
        _ficha(self.pasta, 1)
        _ficha(self.pasta, 2, aprovado_por_conferente=False)
        ficha3 = _ficha(self.pasta, 3)
        (self.pasta / "EP03.mp4").write_bytes(b"re-render com o mesmo nome")
        aprovados, fora = S.episodios(self.pasta)
        self.assertEqual([e.numero for e in aprovados], [1])
        self.assertEqual(len(fora), 2)
        self.assertTrue(any("sem a marca" in m for m in fora))
        self.assertTrue(any("mudou depois da aprovacao" in m for m in fora),
                        ficha3.name)

    def test_regras_do_adrian_para_o_texto(self):
        """Nada de ferramenta de IA, de codigo, de GitHub nem do local."""
        for ruim in ("Feito com o Claude", "no GitHub", "cada commit",
                     "meu codigo", "em E:\\projetos", "um bug estranho"):
            self.assertTrue(S.texto_proibido(ruim), ruim)
        self.assertEqual(S.texto_proibido(TITULO, DESCRICAO, *TAGS), "")
        _ficha(self.pasta, 1, descricao=DESCRICAO + " Feito com Claude.")
        aprovados, fora = S.episodios(self.pasta)
        self.assertEqual(aprovados, [])
        self.assertIn("claude", fora[0])

    def test_idioma_e_titulo_longo_barram(self):
        _ficha(self.pasta, 1, idioma="en")
        _ficha(self.pasta, 2, titulo="x" * 101)
        aprovados, fora = S.episodios(self.pasta)
        self.assertEqual(aprovados, [])
        self.assertEqual(len(fora), 2)

    def test_dois_json_do_mesmo_numero_nao_entram(self):
        _ficha(self.pasta, 1)
        copia = json.loads((self.pasta / "ep01.json").read_text("utf-8"))
        (self.pasta / "ep01_outro.json").write_text(json.dumps(copia),
                                                     encoding="utf-8")
        aprovados, fora = S.episodios(self.pasta)
        self.assertEqual(aprovados, [])
        self.assertTrue(any("mesmo numero" in m for m in fora))

    def test_video_carrega_titulo_e_descricao_inteira(self):
        _ficha(self.pasta, 1)
        ep = S.episodios(self.pasta)[0][0]
        video = ep.como_video()
        self.assertEqual(video.id, "bluelock_ep01")
        self.assertEqual(video.titulo, TITULO)
        self.assertEqual(video.descricao_completa,
                         DESCRICAO + "\n\n" + " ".join(TAGS))
        self.assertTrue(video.vertical)


class EscolherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)
        _ficha(self.pasta, 1)
        _ficha(self.pasta, 2)
        self.aprovados = S.episodios(self.pasta)[0]
        self.hoje = date(2026, 10, 26)

    def test_ledger_vazio_o_proximo_e_o_ep1(self):
        ep, _ = S.escolher("youtube", self.aprovados, [], set(), self.hoje)
        self.assertEqual(ep.numero, 1)

    def test_cada_destino_segue_a_sua_ordem(self):
        linhas = [_linha(1, "youtube", "2026-10-26T20:41:00")]
        yt, motivo = S.escolher("youtube", self.aprovados, linhas, set(),
                                date(2026, 10, 27))
        tk, _ = S.escolher("tiktok", self.aprovados, linhas, set(),
                           date(2026, 10, 27))
        self.assertEqual(yt.numero, 2, motivo)
        self.assertEqual(tk.numero, 1)

    def test_um_por_dia_por_destino(self):
        linhas = [_linha(1, "youtube", "2026-10-26T09:10:00")]
        ep, motivo = S.escolher("youtube", self.aprovados, linhas, set(),
                                self.hoje)
        self.assertIsNone(ep)
        self.assertIn("ja saiu 1 episodio hoje", motivo)
        outro, _ = S.escolher("youtube", self.aprovados, linhas, set(),
                              date(2026, 10, 27))
        self.assertEqual(outro.numero, 2)

    def test_a_ordem_nunca_pula_o_que_nao_esta_aprovado(self):
        so_o_2 = [e for e in self.aprovados if e.numero == 2]
        ep, motivo = S.escolher("youtube", so_o_2, [], set(), self.hoje)
        self.assertIsNone(ep)
        self.assertIn("episodio 1", motivo)

    def test_titulo_repetido_barra_pela_chave_e_nao_pelo_texto(self):
        outro = [_linha(9, "youtube", "2026-10-20T20:41:00",
                        titulo=TITULO.upper().replace("🤔", ""))]
        ep, motivo = S.escolher("youtube", self.aprovados, outro, set(),
                                self.hoje)
        self.assertIsNone(ep)
        self.assertIn("ja esta no ar", motivo)

    def test_lista_a_conferir_barra(self):
        ep, motivo = S.escolher("youtube", self.aprovados, [],
                                {"bluelock_ep01"}, self.hoje)
        self.assertIsNone(ep)
        self.assertIn("a conferir", motivo)

    def test_rascunho_e_apagado_nao_contam_como_no_ar(self):
        rascunho = _linha(1, "youtube", "2026-10-25T20:41:00",
                          publicado=False, estado="rascunho")
        ep, _ = S.escolher("youtube", self.aprovados, [rascunho], set(),
                           self.hoje)
        self.assertEqual(ep.numero, 1)
        apagado = _linha(1, "youtube", "2026-10-25T20:41:00",
                         publicado=False, estado="apagado_do_canal")
        ep, _ = S.escolher("youtube", self.aprovados, [apagado], set(),
                           self.hoje)
        self.assertEqual(ep.numero, 2)


if __name__ == "__main__":
    unittest.main()
