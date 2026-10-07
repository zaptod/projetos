# -*- coding: utf-8 -*-
"""Parte em pedacos: o pedaco 1 no ar e o 2 caido NAO repoem (06/10/2026).

Achado do conferente no commit c431c6e. A parte que passa do Shorts sobe
pedaco a pedaco (`contos.publicar.catalogo.publicar_youtube` percorre
`cortes.preparar`), e a linha do ledger so e gravada DEPOIS do ultimo
(`serie.registrar`, no `postar_historia`). Se o pedaco 2 cai com
"infraestrutura:" (a pagina lenta das 00:37), a ficha leva a marca de rede,
`_derrubados_pela_rede` devolve ["youtube"], `_publicar_canal` roda o canal
de novo, `publicou_neste_horario` nao acha linha nenhuma, a fila escolhe a
MESMA parte — e o pedaco 1 sobe de novo, PUBLICO.

Conta de mao, com o TikTok caindo junto (senao a parte ja conta como
publicada pelo TikTok e a fila leva a seguinte): pedaco 1 enviado
1 + `TENTATIVAS_POR_REDE` (2) = 3 vezes, duas duplicatas publicas. Depois do
conserto: 1 vez, e a parte vai a lista "a conferir" do YouTube — a rodada
seguinte tambem nao a repete (repetir e pior que nao postar, 17/09).

Hoje 0 de 59 partes passam de 182 s (corte ligado em 180 s): o defeito e
latente, nao medido no canal.

Rode de dentro de historias/:
    python -m unittest tests.test_pedaco_no_ar_nao_repoe_regressions -v
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_pedaco_no_ar",
                                                  POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


ALVO = type("V", (), {"id": "historia_00054:celular:p02",
                      "fonte_id": "historia_00054", "parte": 2, "partes": 6,
                      "caminho": "x.mp4",
                      "titulo": "A Conta Dividida (Parte 2/6)"})()

QUEDA_DO_PEDACO_2 = ("infraestrutura: nao consegui abrir o envio de video "
                     "(o clique no Criar nao passou (TimeoutError)). A "
                     "pagina levou 126 s para abrir (o normal e 8-30 s).")


class PedacoNoArTests(unittest.TestCase):
    def setUp(self):
        from builds.publicar import desfecho, tiktok
        from contos.publicar import catalogo, serie
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.m._dormir = lambda _s: None
        self.m.esperar_a_rede = lambda **k: True
        self.m._ainda_no_horario = lambda comeco, slot, **k: True
        self.m.publicou_neste_horario = lambda *a, **k: None
        self.m._tiktok_neste_horario = lambda agora=None: True
        self.m.titulo_repetido = lambda *a, **k: False
        self.m._registrar_valvula = lambda ficha: None
        self.m._valvula_da_parte = lambda ficha, alvo: ""
        # A fila: nada foi registrado, entao ela escolhe a MESMA parte.
        self.m.proxima_historia = lambda **k: (ALVO, [])
        # Sem divida do YouTube: ela vem antes da fila e leria o ledger REAL.
        self.m._divida_do_youtube = lambda: (None, "", [])
        self.marcas = {}
        _trocar(self, desfecho, "marcar_para_conferir",
                lambda canal, vid, estado, plataforma="tiktok", **k:
                self.marcas.setdefault(plataforma, {}).update({vid: estado})
                or True)
        self.registros = []
        _trocar(self, serie, "registrar",
                lambda *a, **k: self.registros.append(a) or {})
        _trocar(self, tiktok, "confirmado",
                lambda estado: estado == "publicado no TikTok")
        self.envios_do_pedaco_1 = 0

        def publicar_youtube(alvo, visibilidade=None, *, provas=None, **_k):
            # O laco de `catalogo.publicar_youtube`: o laudo de cada pedaco
            # entra na lista DEPOIS que o pedaco sobe.
            self.envios_do_pedaco_1 += 1
            provas.append({"youtube_id": f"PEDACO1_{self.envios_do_pedaco_1}",
                           "estado": "publicado"})
            raise RuntimeError(QUEDA_DO_PEDACO_2)
        _trocar(self, catalogo, "publicar_youtube", publicar_youtube)

        def tiktok_caido(alvo, falha=None):
            falha.update(tipo="TikTokFalhou",
                         mensagem="infraestrutura: a pagina do TikTok nao "
                                  "abriu (Timeout 90000ms)")
            return ""
        self.m._tiktok_das_historias = tiktok_caido

    def _rodada(self):
        return self.m._publicar_canal("historias", self.m.postar_historia,
                                      so_ver=False, comeco=0.0, slot=0)

    def test_pedaco_1_sobe_uma_vez_so(self):
        """Antes: 3 envios do pedaco 1 (1 + 2 reposicoes). Agora: 1."""
        fichas = self._rodada()
        self.assertEqual(1, self.envios_do_pedaco_1)
        self.assertEqual(1, len(fichas))
        self.assertTrue(fichas[0]["youtube_meio_no_ar"])

    def test_a_falha_seguinte_nao_leva_a_marca_de_rede(self):
        ficha = self.m.postar_historia()
        self.assertTrue(ficha["youtube_falhou"])
        self.assertFalse(self.m._e_de_rede(ficha["motivo"]), ficha["motivo"])
        self.assertNotIn("youtube", self.m._derrubados_pela_rede(ficha))
        # O erro de verdade fica na ficha, para quem le o relatorio.
        self.assertIn("126 s", ficha["youtube_erro"])
        self.assertIn("PEDACO1_1", ficha["motivo"])

    def test_tiktok_caido_por_rede_continua_contando_para_a_recuperacao(self):
        """O TikTok desta ficha caiu por rede de verdade: `main` usa isso para
        nao chamar a recuperacao/reserva do TikTok logo atras. So o REPOR o
        canal fica proibido (repor roda o YouTube de novo)."""
        ficha = self.m.postar_historia()
        self.assertEqual(["tiktok"], self.m._derrubados_pela_rede(ficha))

    def test_parte_vai_a_lista_a_conferir_do_youtube(self):
        """E a rodada SEGUINTE nao a escolhe: `_sem_a_conferir` le a marca."""
        self.m.postar_historia()
        marca = self.marcas["youtube"][ALVO.id]
        self.assertTrue(marca.startswith(self.m.PREFIXO_DO_PEDACO), marca)
        self.assertIn("PEDACO1_1", marca)
        self.m.a_conferir_no_tiktok = (
            lambda canal="historias", plataforma="tiktok":
            set(self.marcas.get(plataforma, {})))
        self.assertEqual([], self.m._sem_a_conferir([ALVO], "historias"))
        self.assertEqual([], self.registros, "nenhuma linha de meia parte")

    def test_caso_zero_nenhum_pedaco_no_ar_continua_repondo(self):
        """O pedaco 1 e quem cai: nenhum arquivo entregue, repetir nao
        duplica — a reposicao de c431c6e segue valendo."""
        from contos.publicar import catalogo

        def cai_no_primeiro(alvo, visibilidade=None, *, provas=None, **_k):
            self.envios_do_pedaco_1 += 1
            raise RuntimeError(QUEDA_DO_PEDACO_2)
        _trocar(self, catalogo, "publicar_youtube", cai_no_primeiro)
        fichas = self._rodada()
        self.assertEqual(1 + self.m.TENTATIVAS_POR_REDE,
                         self.envios_do_pedaco_1)
        self.assertNotIn("youtube_meio_no_ar", fichas[0])
        self.assertEqual({}, self.marcas)

    def test_marca_que_nao_gravou_ainda_segura_a_reposicao(self):
        """A marca falhou (trava ocupada): o horario continua sem repor."""
        from builds.publicar import desfecho

        def nao_marca(*a, **k):
            raise desfecho.NaoConsegviMarcar("a trava esta ocupada")
        _trocar(self, desfecho, "marcar_para_conferir", nao_marca)
        self._rodada()
        self.assertEqual(1, self.envios_do_pedaco_1)


    def test_marca_de_meio_no_ar_vence_a_frase_de_rede(self):
        """Duas travas, de proposito: mesmo que a frase volte a carregar
        "infraestrutura" (alguem junta o erro original nela), a ficha com
        pedaco no ar nao entrega o YouTube a reposicao."""
        ficha = {"canal": "historias", "feito": False, "youtube_falhou": True,
                 "youtube_meio_no_ar": True, "tiktok": "",
                 "motivo": "YouTube falhou: " + QUEDA_DO_PEDACO_2}
        self.assertEqual([], self.m._derrubados_pela_rede(ficha))

    def test_a_porta_levanta_meio_no_ar_com_os_ids(self):
        provas: list = []
        with self.assertRaises(self.m.ParteMeioNoAr) as caso:
            self.m._subir_parte_no_youtube(ALVO, "public", provas)
        self.assertEqual(["PEDACO1_1"], caso.exception.ids)
        self.assertIn("126 s", caso.exception.erro)
        self.assertFalse(self.m._e_de_rede(str(caso.exception)))


class EscoarEAvulsoTests(unittest.TestCase):
    """Os outros dois caminhos do postar que sobem parte de historia
    (`--tudo` e `--so-youtube`) passam pela mesma porta."""

    def test_os_tres_caminhos_usam_a_porta(self):
        fonte = POSTAR.read_text(encoding="utf-8")
        self.assertEqual(1, fonte.count("catalogo.publicar_youtube("),
                         "so a porta (_subir_parte_no_youtube) chama o "
                         "catalogo direto")
        self.assertEqual(3, fonte.count("url = _subir_parte_no_youtube(alvo"))


if __name__ == "__main__":
    unittest.main()
