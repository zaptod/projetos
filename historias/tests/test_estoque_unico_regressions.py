# -*- coding: utf-8 -*-
"""A agenda e a publicacao contam o estoque com UM numero so (30/09/2026).

As 11:02 a agenda contou 29 "aprovados" (>= piso 20) e entrou em "so
consertar"; as 11:21 o `postar.py --ver` contou 8 videos (0,8 dia). Medido as
11:25: dos 27 da agenda, 20 eram RETIDOS (18 com o veto da IA, 2 so pela
folha), que a publicacao so solta quando o horario ia ficar vazio. A agenda
nao criava e o canal secaria em menos de um dia.

Agora `agenda.estoque_publicavel()` E `postar.pendentes_por_canal()`
["historias"]. Os testes trocam o `postar` carregado por um de mentira (ou
dublam as funcoes dele) e congelam o resto: nada abre navegador.
"""
from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from contos.pipeline import agenda

QUINTA = datetime(2026, 10, 8, 10, 2)        # reposicao, piso 20
SEGUNDA = datetime(2026, 10, 5, 10, 2)       # lote


def _video(serie: int, parte: int):
    fonte = f"historia_{serie:05d}"
    return type("V", (), {"id": f"{fonte}:celular:p{parte:02d}",
                          "fonte_id": fonte, "parte": parte,
                          "perfil": "celular", "titulo": ""})()


class _PostarDeMentira:
    def __init__(self, historias):
        self.historias = historias
        self.chamadas = 0

    def pendentes_por_canal(self):
        self.chamadas += 1
        if isinstance(self.historias, Exception):
            raise self.historias
        return {"historias": self.historias, "builds": 17}


class _Base(unittest.TestCase):

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self._trocar(agenda, "OUTPUTS", Path(tmp.name))
        # 29 "aprovados" da vistoria mecanica: o que a agenda via as 11:02.
        self.aprovados = [_video(34000 + s, p) for s in range(5)
                          for p in range(1, 7)][:29]
        self._trocar(agenda, "aprovados_no_estoque",
                     lambda: list(self.aprovados))
        self._trocar(agenda, "barrados_no_estoque", lambda: [])
        self._trocar(agenda, "incompletas", lambda: [])
        self._trocar(agenda, "servico_pendente", lambda agora: False)
        self._trocar(agenda, "_livre_gb", lambda _c: 100.0)
        from contos.imagens import cota
        self._trocar(cota, "motivo", lambda *a, **k: None)
        self.config = {**agenda.carregar(), "avisar_telegram": False}

    def _trocar(self, alvo, nome, valor):
        self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
        setattr(alvo, nome, valor)

    def _publicacao(self, historias):
        falso = _PostarDeMentira(historias)
        self._trocar(agenda, "_POSTAR_CARREGADO", falso)
        return falso


class AgendaEPublicacaoDiscordandoTests(_Base):
    """O caso de 30/09: a agenda via 29, a publicacao 8."""

    def test_29_aprovados_e_8_publicaveis_a_reposicao_cria(self):
        self._publicacao(8)
        plano = agenda.planejar(self.config, QUINTA)
        self.assertEqual("reposicao", plano["modo"])
        self.assertEqual(8, plano["aprovados"])
        self.assertTrue(plano["criar"], plano["por_que"])
        self.assertTrue(plano["fazer"])
        self.assertFalse(plano["config"]["so_consertar"])
        self.assertIn("8 publicavel(is), piso 20", plano["por_que"])

    def test_o_lote_conta_o_mesmo_numero(self):
        self._publicacao(8)
        plano = agenda.planejar(self.config, SEGUNDA)
        self.assertEqual("lote", plano["modo"])
        self.assertEqual(8, plano["aprovados"])
        self.assertTrue(plano["criar"])

    def test_publicacao_com_estoque_de_verdade_nao_cria(self):
        self._publicacao(25)
        self.aprovados = self.aprovados[:3]
        plano = agenda.planejar(self.config, QUINTA)
        self.assertFalse(plano["criar"])
        self.assertEqual("estoque cheio", plano["motivo"])

    def test_o_freio_de_trabalhar_conta_o_mesmo_numero(self):
        """O plano manda criar e `_trabalhar` nao pode dizer "cheio"."""
        self._publicacao(8)
        self.assertEqual(8, agenda.dias_de_estoque_novo())
        fonte = Path(agenda.__file__).read_text(encoding="utf-8")
        trabalhar = fonte[fonte.index("def _trabalhar("):]
        corpo = trabalhar[trabalhar.index("teto = teto_de_estoque(config)"):]
        self.assertIn("dias_de_estoque_novo()", corpo[:400])

    def test_lista_passada_por_quem_chama_vale(self):
        publicacao = self._publicacao(8)
        plano = agenda.planejar(self.config, QUINTA,
                                aprovados=[_video(1, 1)] * 30)
        self.assertEqual(30, plano["aprovados"])
        self.assertEqual(0, publicacao.chamadas)


class NaoSeiContarTests(_Base):
    """Sem o numero da publicacao, conta a mais (cria de menos)."""

    def test_menos_um_cai_nos_aprovados(self):
        self._publicacao(-1)
        self.assertEqual(29, agenda.estoque_publicavel())

    def test_excecao_cai_nos_aprovados(self):
        self._publicacao(RuntimeError("ledger ilegivel"))
        self.assertEqual(29, agenda.estoque_publicavel())

    def test_zero_e_zero_e_nao_cai(self):
        """Zero publicavel NAO e "nao sei": e o caso mais urgente."""
        self._publicacao(0)
        self.assertEqual(0, agenda.estoque_publicavel())


class MesmaFuncaoDaPublicacaoTests(unittest.TestCase):
    """O `postar.py` DE VERDADE, com a fila dublada: os dois numeros batem."""

    def setUp(self):
        self.postar = agenda._postar()

    def _trocar(self, alvo, nome, valor):
        self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
        setattr(alvo, nome, valor)

    def test_carrega_o_postar_do_repositorio(self):
        self.assertTrue(agenda.POSTAR.is_file())
        self.assertTrue(callable(self.postar.pendentes_por_canal))

    def test_retida_fica_fora_nos_dois(self):
        fila = [_video(41, 1), _video(41, 2), _video(36, 3)]
        retidas = {fila[2].id}
        self._trocar(self.postar, "fila_de_historias", lambda: list(fila))
        self._trocar(self.postar, "_retencao",
                     lambda v: "a IA reprovou" if v.id in retidas else "")
        self._trocar(self.postar, "_builds_prontos", lambda *a, **k: [])
        self.assertEqual(2, self.postar.pendentes_por_canal()["historias"])
        self.assertEqual(2, agenda.estoque_publicavel())

    def test_o_codigo_nao_duplica_o_criterio(self):
        import inspect
        fonte = inspect.getsource(agenda.estoque_publicavel)
        self.assertIn("pendentes_por_canal()", fonte)
        self.assertNotIn("_retencao", fonte)
        self.assertIn("estoque_publicavel()",
                      inspect.getsource(agenda.dias_de_estoque_novo))


if __name__ == "__main__":
    unittest.main()
