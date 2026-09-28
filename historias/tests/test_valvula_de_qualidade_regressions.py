# -*- coding: utf-8 -*-
"""A valvula de qualidade: parte duvidosa so sai se o horario fosse ficar vazio.

Decisao do Adrian no plano de 27/09/2026 (S2, item 4): "retido = 'a IA
reprovou' ou 'parecer so pela folha'; retido so sai quando nao houver outro
candidato para o horario; quando sair, fica marcado na lista 'a conferir'".

MEDIDO NA FILA DE 28/09/2026, 03:05 (19 partes): 10 com o veto da IA vencido
(as rodadas de conserto acabaram), 7 com o veto ainda de pe, 1 so pela folha
(`nao_assistido`) e 1 aprovada — atras de uma parte vetada da mesma serie.
Ate aqui o veto vencido saia na hora, com "a IA reprovou, mas as rodadas de
conserto acabaram; sai assim": era o que ia sair as 06:37 (h32 p05).

Com a valvula, nesta fila, NENHUMA parte limpa sobra: o ultimo recurso leva a
mesma h32 p05 — mas marcada na lista "a conferir" e com a marca no aviso.
A diferenca aparece no dia em que houver parte limpa: ela passa na frente.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_valvula_q", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _video(h, p):
    return type("V", (), {"id": f"{h}:celular:p{p:02d}", "fonte_id": h,
                          "parte": p, "partes": 6, "caminho": "x.mp4",
                          "titulo": f"{h} parte {p}"})()


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


class _Fila(unittest.TestCase):
    """`proxima_historia` de verdade; a qualidade de cada parte e dublada."""

    def setUp(self):
        from builds import travas
        from contos.publicar import qualidade
        from contos.roteiro import roteiro as R
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.vencidas, self.folha, self.vetadas, self.quebradas = (
            set(), set(), set(), set())
        self.vistoriadas = []
        self.m._veto_lembrado = (
            lambda alvo: f"{alvo.id}: veto" if alvo.id in self.vetadas else "")
        self.m._veto_vencido = lambda alvo: alvo.id in self.vencidas
        self.m._parecer_da_ia = lambda *_a, **_k: ""
        self.m._situacao_do_parecer = lambda alvo: (
            "reprovado" if alvo.id in self.vencidas | self.vetadas
            else "nao_assistido" if alvo.id in self.folha else "aprovado")

        _trocar(self, qualidade, "vistoriar_parte",
                lambda h, p, caminho, r: (
                    self.vistoriadas.append(f"{h}:celular:p{p:02d}") or
                    {"ok": f"{h}:celular:p{p:02d}" not in self.quebradas,
                     "erros": ["quebrado"]}))
        _trocar(self, R, "carregar", lambda _hid: {})
        _trocar(self, travas, "ocupada", lambda _nome: False)

    def _escolha(self, fila):
        self.m.fila_de_historias = lambda: fila
        alvo, recusados = self.m.proxima_historia()
        self.recusados = recusados
        return alvo.id if alvo else None


class RetidoSoSaiSemOutroTests(_Fila):
    def test_veto_vencido_cede_a_vez_a_parte_limpa(self):
        """Ate 28/09 a h32 p05 (vencida) saia na frente de qualquer outra."""
        fila = [_video("historia_00032", 5), _video("historia_00040", 1)]
        self.vencidas.add("historia_00032:celular:p05")
        self.assertEqual("historia_00040:celular:p01", self._escolha(fila))
        self.assertTrue(any("retida" in r for r in self.recusados))

    def test_parecer_so_pela_folha_cede_a_vez(self):
        fila = [_video("historia_00034", 4), _video("historia_00040", 1)]
        self.folha.add("historia_00034:celular:p04")
        self.assertEqual("historia_00040:celular:p01", self._escolha(fila))

    def test_sem_outro_candidato_o_retido_sai(self):
        """'Nao ficar sem video' continua valendo: a fila de 28/09."""
        fila = [_video("historia_00032", 5)]
        self.vencidas.add("historia_00032:celular:p05")
        self.assertEqual("historia_00032:celular:p05", self._escolha(fila))

    def test_a_serie_espera_a_parte_retida(self):
        """A parte seguinte da mesma serie nao passa na frente: ordem e
        sagrada, e fora de ordem continua sendo o ULTIMO recurso."""
        fila = [_video("historia_00032", 5), _video("historia_00032", 6)]
        self.vencidas.add("historia_00032:celular:p05")
        self.assertEqual("historia_00032:celular:p05", self._escolha(fila))

    def test_vencida_antes_da_vetada_no_ultimo_recurso(self):
        """O veto vencido ja gastou o conserto; o de pe ainda pode ser
        consertado — publica-lo agora queimaria o conserto."""
        fila = [_video("historia_00034", 1), _video("historia_00032", 5)]
        self.vetadas.add("historia_00034:celular:p01")
        self.vencidas.add("historia_00032:celular:p05")
        self.assertEqual("historia_00032:celular:p05", self._escolha(fila))

    def test_reter_nao_gasta_tentativa(self):
        """Sete retidas na frente e a limpa em oitavo: `TENTATIVAS` (6) nao
        pode acabar nelas, senao a limpa nunca e vista e a retida sai."""
        fila = [_video(f"historia_{n:05d}", 1) for n in range(20, 27)]
        self.vencidas.update(v.id for v in fila)
        fila.append(_video("historia_00040", 1))
        self.assertEqual("historia_00040:celular:p01", self._escolha(fila))
        self.assertEqual(["historia_00040:celular:p01"], self.vistoriadas)

    def test_retido_com_arquivo_quebrado_nao_sai_nem_assim(self):
        fila = [_video("historia_00032", 5)]
        self.vencidas.add("historia_00032:celular:p05")
        self.quebradas.add("historia_00032:celular:p05")
        self.assertIsNone(self._escolha(fila))


class RetencaoTests(unittest.TestCase):
    """A regra, pura: duas causas, lidas de arquivo."""

    def setUp(self):
        self.m = _postar()
        self.alvo = _video("historia_00032", 5)

    def test_vencido_so_conta_com_o_parecer_reprovado(self):
        self.m._veto_vencido = lambda _a: True
        self.m._situacao_do_parecer = lambda _a: "reprovado"
        self.assertIn("rodadas de conserto", self.m._retencao(self.alvo))
        self.m._situacao_do_parecer = lambda _a: "aprovado"
        self.assertEqual("", self.m._retencao(self.alvo),
                         "consertado e aprovado assistindo nao e retido")

    def test_veto_de_pe_tambem_e_retido(self):
        self.m._veto_vencido = lambda _a: False
        self.m._situacao_do_parecer = lambda _a: "reprovado"
        retencao = self.m._retencao(self.alvo)
        self.assertIn("a IA reprovou", retencao)
        self.assertNotIn("rodadas", retencao)

    def test_folha_e_retida(self):
        self.m._veto_vencido = lambda _a: False
        self.m._situacao_do_parecer = lambda _a: "nao_assistido"
        self.assertIn("folha", self.m._retencao(self.alvo))

    def test_aprovado_assistindo_nao_e(self):
        self.m._veto_vencido = lambda _a: False
        self.m._situacao_do_parecer = lambda _a: "aprovado"
        self.assertEqual("", self.m._retencao(self.alvo))

    def test_sem_parecer_nao_e(self):
        """Sem ninguem ter olhado nao e "so a folha": a postagem nao pergunta
        ao Gemini (PEDIR_PARECER_NA_POSTAGEM), e reter tudo que nao tem ficha
        pararia o canal."""
        self.m._veto_vencido = lambda _a: False
        self.m._situacao_do_parecer = lambda _a: ""
        self.assertEqual("", self.m._retencao(self.alvo))


class QuandoSaiFicaMarcadoTests(unittest.TestCase):
    """`postar_historia` de verdade: retido que sai vai para a lista."""

    def setUp(self):
        from builds.publicar import desfecho, tiktok
        from contos.publicar import catalogo, serie
        self.m = _postar()
        self.m._linha = lambda *_a, **_k: None
        self.m.publicou_neste_horario = lambda *a, **k: None
        self.m._tiktok_neste_horario = lambda agora=None: True
        self.m.titulo_repetido = lambda *a, **k: False
        self.m._veto_vencido = lambda _a: True
        self.m._veto_lembrado = lambda _a: ""
        self.m._registrar_valvula = lambda ficha: None
        self.alvo = _video("historia_00032", 5)
        self.m.proxima_historia = lambda **k: (self.alvo, [])
        self.marcas = []
        _trocar(self, desfecho, "marcar_para_conferir",
                lambda canal, vid, estado, plataforma="tiktok", **k:
                self.marcas.append((canal, vid, plataforma, estado, k)) or True)
        _trocar(self, serie, "registrar", lambda *a, **k: {})
        _trocar(self, tiktok, "confirmado",
                lambda estado: estado == "publicado no TikTok")
        self.catalogo = catalogo

    def _rodar(self, *, url, tiktok, retencao):
        _trocar(self, self.catalogo, "publicar_youtube",
                lambda *a, **k: url)
        self.m._tiktok_das_historias = lambda alvo, falha=None: tiktok
        self.m._retencao = lambda _a: retencao
        return self.m.postar_historia()

    def test_retido_que_sai_fica_marcado_nos_dois_destinos(self):
        ficha = self._rodar(url="publicado no YouTube",
                            tiktok="publicado no TikTok",
                            retencao="historia_00032:celular:p05: a IA reprovou")
        self.assertEqual(["youtube", "tiktok"], [m[2] for m in self.marcas])
        self.assertTrue(all(m[3].startswith("[qualidade] ") for m in self.marcas))
        self.assertTrue(all(m[4].get("erro") is False for m in self.marcas))
        self.assertIn("a IA reprovou", ficha["retido"])

    def test_saiu_em_um_destino_marca_os_dois(self):
        """A recuperacao do TikTok levaria depois, como extra, a parte que so
        saiu no YouTube: extra nunca e "o horario ia ficar vazio"."""
        self._rodar(url="publicado no YouTube", tiktok="",
                    retencao="x: a IA reprovou")
        self.assertEqual(["youtube", "tiktok"], [m[2] for m in self.marcas])

    def test_nao_saiu_nao_marca(self):
        """Marcar antes de sair tiraria a parte da fila para sempre."""
        self._rodar(url="", tiktok="", retencao="x: a IA reprovou")
        self.assertEqual([], self.marcas)

    def test_parte_limpa_nao_marca(self):
        self._rodar(url="publicado no YouTube", tiktok="publicado no TikTok",
                    retencao="")
        self.assertEqual([], self.marcas)


if __name__ == "__main__":
    unittest.main()
