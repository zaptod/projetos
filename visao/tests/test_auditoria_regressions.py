# -*- coding: utf-8 -*-
"""Os quatro controles e a grade unica (11/09/2026).

Pedido dele depois de um dia em que tres coisas foram ao ar erradas sem que
nada avisasse: "preciso de controle de qualidade, controle de metas, controle
de producao e controle de recursos".

O que este arquivo trava:

1. A GRADE E UMA SO. A tupla (6,7,8,10,12,15,17,20) estava escrita em
   `ferramentas/postar.py` e em `remoto/relatorios.py`. Duas copias bastam
   para o relatorio dizer "bateu a meta" enquanto a postagem trabalha com
   outro horario, e quem le as duas telas nao sabe qual esta certa.
2. SO O HORARIO VENCIDO E COBRADO. Comparar com os oito o dia inteiro faria
   o relatorio das 09:00 acusar seis horarios perdidos que nem chegaram.
3. A AUDITORIA NAO TEM OPINIAO PROPRIA: a coluna de qualidade e a MESMA
   funcao que o `postar.py` consulta. Duas opinioes sobre "pode publicar?"
   e nenhuma.
4. NADA AQUI LEVANTA. Uma tela de resumo que estoura por causa de um arquivo
   e pior do que uma tela incompleta — a regra do pacote inteiro.

    cd e:\\projetos
    python -m pytest visao/tests/test_auditoria_regressions.py -q
"""
from __future__ import annotations

import unittest
from datetime import datetime

from builds import grade
from panorama import auditoria, recursos


class GradeUnicaTests(unittest.TestCase):

    def test_a_postagem_e_o_relatorio_leem_a_mesma_grade(self):
        import importlib.util
        from pathlib import Path

        from remoto import relatorios
        caminho = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"
        spec = importlib.util.spec_from_file_location("postar_aud", caminho)
        postar = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(postar)
        self.assertEqual(tuple(grade.HORAS), tuple(postar.HORAS_PADRAO))
        self.assertEqual(tuple(grade.HORAS),
                         tuple(relatorios.HORARIOS_DA_GRADE))
        self.assertEqual(grade.MINUTO, postar.MINUTO_PADRAO)

    def test_a_meta_do_canal_e_um_por_horario(self):
        self.assertEqual(len(grade.HORAS), grade.META_DIARIA_POR_CANAL)

    def test_a_grade_e_das_horas_vagas(self):
        """15/09/2026, pedido dele: indo pro trabalho, cafe, almoco, lanche,
        ida embora e a noite ociosa ate quase de madrugada."""
        self.assertEqual(["00:37", "06:37", "09:37", "12:07", "15:37", "17:57",
                          "20:37", "21:37", "22:37", "23:37"], grade.horarios())
        self.assertEqual(10, grade.META_DIARIA_POR_CANAL)

    def test_a_meta_total_conta_os_dois_lugares(self):
        """Dez horarios, duas plataformas, dois canais: 10 x 2 x 2 = 40."""
        self.assertEqual(40, grade.META_DIARIA_TOTAL)

    def test_o_tiktok_posta_em_todos_os_horarios(self):
        """Decisao dele em 15/09/2026 ("tapar esses buracos"): de 13 a 15/09 o
        TikTok pulava 7h e 8h e a parte desses horarios nunca chegava la."""
        self.assertEqual(grade.HORAS, grade.horas_da_plataforma("tiktok"))
        self.assertEqual(grade.HORAS, grade.horas_da_plataforma("youtube"))
        for h in grade.HORAS:
            self.assertTrue(grade.publica_em("tiktok", h))
        self.assertFalse(grade.publica_em("tiktok", 8))

    def test_o_tiktok_so_usa_horario_que_existe_na_grade(self):
        """Quem posta no TikTok e a rodada da grade: hora fora dela nunca roda."""
        for plataforma in grade.PLATAFORMAS:
            self.assertTrue(set(grade.horas_da_plataforma(plataforma))
                            <= set(grade.HORAS))

    def test_so_conta_o_horario_que_ja_venceu(self):
        cedo = datetime(2026, 9, 11, 9, 0)
        self.assertEqual([0, 6], grade.vencidos(cedo))
        self.assertEqual([0, 6], grade.vencidos(cedo, "tiktok"))

    def test_antes_do_primeiro_horario_nao_ha_divida(self):
        self.assertEqual([], grade.vencidos(datetime(2026, 9, 11, 0, 36)))

    def test_o_minuto_conta_na_borda_e_e_de_cada_hora(self):
        """06:37 e a hora; 06:36 ainda nao. E o almoco e 12:07, nao 12:37."""
        self.assertEqual([0], grade.vencidos(datetime(2026, 9, 11, 6, 36)))
        self.assertEqual([0, 6], grade.vencidos(datetime(2026, 9, 11, 6, 37)))
        self.assertEqual([0, 6, 9], grade.vencidos(datetime(2026, 9, 11, 12, 6)))
        self.assertEqual([0, 6, 9, 12], grade.vencidos(datetime(2026, 9, 11, 12, 7)))

    def test_o_proximo_vira_o_dia(self):
        self.assertEqual("00:37", grade.proximo(datetime(2026, 9, 11, 23, 50))[:5])
        self.assertIn("amanha", grade.proximo(datetime(2026, 9, 11, 23, 50)))
        self.assertEqual("12:07", grade.proximo(datetime(2026, 9, 11, 10, 30)))
        self.assertEqual("06:37", grade.proximo(datetime(2026, 9, 11, 0, 37)))


class MetasTests(unittest.TestCase):

    def test_a_divida_e_contra_o_que_venceu(self):
        cedo = auditoria.metas(datetime(2026, 9, 11, 9, 0))
        self.assertEqual(2, cedo["horarios_vencidos"])
        self.assertEqual(len(grade.HORAS), cedo["horarios_do_dia"])

    def test_todo_canal_e_toda_plataforma_entram_na_conta(self):
        dados = auditoria.metas()
        for canal in grade.CANAIS:
            self.assertIn(canal, dados["canais"])
            for plataforma in grade.PLATAFORMAS:
                self.assertIn(plataforma, dados["canais"][canal])

    def test_faltando_e_a_soma_e_em_dia_concorda_com_ela(self):
        dados = auditoria.metas()
        soma = sum(p["faltando"] for c in dados["canais"].values()
                   for p in c.values())
        self.assertEqual(soma, dados["faltando"])
        self.assertEqual(dados["faltando"] == 0, dados["em_dia"])

    def test_nunca_conta_divida_negativa(self):
        """Publicar duas vezes no mesmo horario nao cria credito."""
        dados = auditoria.metas()
        for canal in dados["canais"].values():
            for plataforma in canal.values():
                self.assertGreaterEqual(plataforma["faltando"], 0)


class VereditoTests(unittest.TestCase):

    @staticmethod
    def _dados(**extra):
        base = {"qualidade": {"liberados": 5, "barrados": 0, "fila": []},
                "metas": {"faltando": 0},
                "recursos": {"alertas": []}}
        base.update(extra)
        return base

    def test_tudo_em_dia_e_verde(self):
        self.assertEqual("ok", auditoria.veredito(self._dados())["cor"])

    def test_video_barrado_e_aviso_e_nao_erro(self):
        """Barrado e o sistema funcionando: ele impediu algo ruim de sair."""
        dados = self._dados(qualidade={"liberados": 3, "barrados": 2,
                                       "fila": []})
        self.assertEqual("aviso", auditoria.veredito(dados)["cor"])

    def test_fila_vazia_e_erro(self):
        """Zero liberados significa que o proximo horario NAO vai sair."""
        dados = self._dados(qualidade={"liberados": 0, "barrados": 4,
                                       "fila": []})
        self.assertEqual("erro", auditoria.veredito(dados)["cor"])

    def test_pipeline_pausada_e_erro(self):
        dados = self._dados(
            recursos={"alertas": ["a pipeline esta PAUSADA (tudo)"]})
        self.assertEqual("erro", auditoria.veredito(dados)["cor"])

    def test_disco_critico_e_erro(self):
        dados = self._dados(
            recursos={"alertas": ["disco em 1.2 GB livres: critico"]})
        self.assertEqual("erro", auditoria.veredito(dados)["cor"])

    def test_a_frase_e_o_primeiro_problema(self):
        dados = self._dados(metas={"faltando": 3})
        self.assertIn("3 publicacao", auditoria.veredito(dados)["frase"])


class RecursosTests(unittest.TestCase):

    def test_o_barato_nao_chama_rede_nem_subprocesso(self):
        """`leves()` entra no resumo de 4 s do painel. Um `schtasks` ali
        viraria dezenas de subprocessos por minuto."""
        dados = recursos.leves()
        self.assertNotIn("agendador", dados)
        self.assertNotIn("oauth", dados)

    def test_o_caro_traz_agendador_e_oauth(self):
        import inspect
        fonte = inspect.getsource(recursos.completo)
        self.assertIn("_agendador()", fonte)
        self.assertIn("_oauth_vivo()", fonte)

    def test_o_disco_vira_situacao_e_nao_so_numero(self):
        disco = recursos.situacao()["disco"]
        self.assertIn(disco.get("situacao"), ("ok", "baixo", "critico"))

    def test_trava_conhecida_nao_e_trava_ocupada(self):
        """`travas.estado()` lista TODOS os perfis com um campo `ocupada`. A
        primeira versao daqui mostrou os sete como se estivessem presos."""
        travas = recursos.situacao()["travas"]
        self.assertIn("ocupadas", travas)
        self.assertLessEqual(travas["quantas"], travas["conhecidas"])

    def test_alertas_sao_frases_e_nao_codigos(self):
        for alerta in recursos.situacao()["alertas"]:
            self.assertGreater(len(alerta), 12)


class NuncaLevantaTests(unittest.TestCase):
    """A regra do pacote: uma familia que falha nao leva as outras junto."""

    def test_qualidade_devolve_erro_em_vez_de_estourar(self):
        import panorama.auditoria as modulo
        antes = modulo.__dict__.get("_publicados_hoje")
        try:
            modulo._publicados_hoje = lambda agora=None: (_ for _ in ()).throw(
                RuntimeError("disco fora"))
            dados = modulo.metas()
            self.assertIn("erro", dados)
        finally:
            modulo._publicados_hoje = antes

    def test_completa_devolve_as_quatro_familias(self):
        dados = auditoria.completa(limite=1)
        for familia in ("qualidade", "metas", "producao", "recursos"):
            self.assertIn(familia, dados)

    def test_o_veredito_aguenta_familia_com_erro(self):
        dados = {"qualidade": {"erro": "x"}, "metas": {"erro": "y"},
                 "recursos": {"erro": "z"}}
        self.assertIn(auditoria.veredito(dados)["cor"], ("ok", "aviso", "erro"))


if __name__ == "__main__":
    unittest.main()
