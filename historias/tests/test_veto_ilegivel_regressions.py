# -*- coding: utf-8 -*-
"""O veto da IA nao falha ABERTO quando `_pareceres.json` nao se le.

Achado da verificacao de 14/10/2026 (fora da contagem da auditoria): desde
11/10 `parecer._lembretes` levanta com o arquivo ilegivel ou trancado, mas
todo leitor da PUBLICACAO engolia a excecao e respondia "sem parecer". Medido
contra o HEAD d6aedb45, com `_lembretes` levantando:

  - `_retencao(parte)` -> "" (nao retida) e `_veto_lembrado` -> "";
  - no ultimo recurso fora de ordem (`adiadas`), a parte seguinte de uma
    serie parada saia LIMPA, sem marca nenhuma (`proxima_historia` devolvia
    a p02);
  - a parte que passava pela vistoria chegava a `_parecer_da_ia`, cujo
    `parecer.lembrado` levantava e derrubava o canal inteiro na rodada.

Agora "nao sei ler os pareceres" e RETIDA (a classe do "ninguem
assistiu"): so sai se o horario ficaria vazio e sai marcada `[qualidade]`;
nas `adiadas` nao sai; `_parecer_da_ia` barra em vez de levantar. O aviso vai
ao diario uma vez por rodada.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_veto_ilegivel",
                                                  POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _trocar(teste, objeto, nome, valor):
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    teste.addCleanup(setattr, objeto, nome, original)


class _Parte:
    def __init__(self, fonte, parte):
        self.fonte_id = fonte
        self.parte = parte
        self.partes = 6
        self.id = f"{fonte}:celular:p{parte:02d}"
        self.titulo = f"{fonte} parte {parte}"
        self.caminho = Path("nao_existe.mp4")


class VetoIlegivelTests(unittest.TestCase):
    def setUp(self):
        from builds import atividade, travas
        from contos.publicar import parecer, qualidade
        from contos.roteiro import roteiro as R
        self.ilegivel = True

        def lembretes():
            if self.ilegivel:
                raise PermissionError("_pareceres.json trancado")
            return {}
        _trocar(self, parecer, "_lembretes", lembretes)
        self.diario = []
        _trocar(self, atividade, "registrar",
                lambda *a, **k: self.diario.append(a))
        # A p01 da serie 91 e reprovada pela vistoria: a serie para nela e a
        # p02 vira "adiada" (o ultimo recurso fora de ordem). Sem render: as
        # `adiadas` reconferem a trava de render, e com ela a p02 nem chegaria
        # a pergunta do veto.
        _trocar(self, qualidade, "vistoriar_parte",
                lambda fonte, parte, *a, **k: (
                    {"ok": True, "erros": [], "avisos": []} if parte != 1
                    or fonte != "historia_00091"
                    else {"ok": False, "erros": ["cena sem imagem"],
                          "avisos": []}))
        _trocar(self, R, "carregar", lambda fonte: {})
        _trocar(self, travas, "ocupada", lambda nome: False)
        self.m = m = _postar()
        m._linha = lambda *a, **k: None
        m._consertado = lambda alvo: False
        self.p1 = _Parte("historia_00091", 1)
        self.p2 = _Parte("historia_00091", 2)

    def test_parte_com_pareceres_ilegiveis_e_retida(self):
        self.assertIn("pareceres", self.m._retencao(self.p1))

    def test_adiada_nao_sai_limpa(self):
        """O caminho que falhava aberto: no HEAD devolvia a p02, sem marca."""
        self.m.fila_de_historias = lambda: [self.p1, self.p2]
        alvo, recusados = self.m.proxima_historia()
        self.assertIsNone(alvo)

    def test_ultimo_recurso_sai_RETIDA_e_marcada(self):
        """Sem nenhuma parte limpa, a retida sai (nao ficar sem video) — e a
        valvula a marca `[qualidade]`, como qualquer retida."""
        outra = _Parte("historia_00092", 1)
        self.m.fila_de_historias = lambda: [outra]
        alvo, recusados = self.m.proxima_historia()
        self.assertIs(outra, alvo)
        self.assertTrue(any("retida" in r for r in recusados))
        ficha = {}
        self.assertIn("pareceres", self.m._valvula_da_parte(ficha, outra))
        self.assertIn("pareceres", ficha["retido"])

    def test_parecer_da_ia_barra_em_vez_de_derrubar_a_rodada(self):
        veto = self.m._parecer_da_ia(self.p1, {}, {})
        self.assertIn("nao consegui ler os pareceres", veto)

    def test_o_diario_ouve_uma_vez_por_rodada(self):
        for _ in range(3):
            self.m._retencao(self.p1)
        erros = [a for a in self.diario if "pareceres" in str(a)]
        self.assertEqual(1, len(erros))

    def test_caso_zero_arquivo_que_se_le_sem_parecer_nao_retem(self):
        """Arquivo legivel e vazio: "sem parecer" NAO e retido (a postagem
        nao pergunta ao Gemini; reter tudo pararia o canal)."""
        self.ilegivel = False
        self.assertEqual("", self.m._retencao(self.p1))
        self.m.fila_de_historias = lambda: [_Parte("historia_00092", 1)]
        alvo, _r = self.m.proxima_historia()
        self.assertEqual("historia_00092:celular:p01", alvo.id)
        self.assertEqual([], self.diario)


if __name__ == "__main__":
    unittest.main()
