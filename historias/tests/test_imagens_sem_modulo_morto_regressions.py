# -*- coding: utf-8 -*-
"""HIS-13: `contos/imagens/referencia.py` era codigo morto que prometia uma guarda.

Auditoria profunda (11/10/2026): nenhum modulo de producao importava o
arquivo (so o proprio teste). A "ancora visual", o "estilo congelado" e o
"dividir por parte" descritos nele nao aconteciam. Decisao
`historias/imagem-de-referencia` (14/10/2026): apagar o modulo morto.

A guarda: todo modulo de `contos/imagens/` tem quem o importe em producao.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

HISTORIAS = Path(__file__).resolve().parents[1]
IMAGENS = HISTORIAS / "contos" / "imagens"


class SemModuloMortoTests(unittest.TestCase):
    def test_todo_modulo_de_imagens_e_importado_em_producao(self):
        fontes = [p for p in (HISTORIAS / "contos").rglob("*.py")]
        fontes.append(HISTORIAS / "main.py")
        textos = {p: p.read_text(encoding="utf-8", errors="replace")
                  for p in fontes}
        mortos = []
        for modulo in sorted(IMAGENS.glob("*.py")):
            nome = modulo.stem
            if nome == "__init__":
                continue
            padrao = re.compile(
                rf"(from\s+\.+\s+import\s+[^\n]*\b{nome}\b"
                rf"|from\s+\.+{nome}\s+import"
                rf"|from\s+\.+imagens\s+import\s+[^\n]*\b{nome}\b"
                rf"|imagens\.{nome}\b"
                rf"|import\s+{nome}\b)")
            if not any(padrao.search(texto) for p, texto in textos.items()
                       if p != modulo):
                mortos.append(nome)
        self.assertEqual([], mortos)

    def test_referencia_saiu(self):
        self.assertFalse((IMAGENS / "referencia.py").exists())


if __name__ == "__main__":
    unittest.main()
