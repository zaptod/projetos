# -*- coding: utf-8 -*-
"""O código-fonte não pode ter byte de controle escondido.

Existe por um bug real e silencioso (01/09/2026): uma regex escrita como
`r"_p(\\d{2})\\b"` chegou ao arquivo com o `\\b` convertido num byte de
BACKSPACE de verdade (0x08). O Python leu aquilo como um caractere literal,
a regex nunca casou, e a função devolveu vazio **sem erro nenhum** — o
recurso simplesmente não funcionava, e o arquivo parecia correto em toda
leitura (o terminal não desenha o 0x08).

O caminho de entrada é sempre o mesmo: texto com `\\` passando por um
heredoc de shell antes de virar arquivo. A defesa é olhar os BYTES, não o
texto renderizado.

Só tabulação (9), quebra de linha (10) e retorno de carro (13) são
aceitáveis. Qualquer outro byte abaixo de 32 é corrupção.

Rode de dentro de random_builds/:
    python -m unittest tests.test_fonte_integra_regressions -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
# Os três projetos vivem lado a lado e compartilham este risco.
PROJETOS = (RAIZ, RAIZ.parent / "historias", RAIZ.parent / "remoto")
PERMITIDOS = {9, 10, 13}
IGNORAR = ("__pycache__", ".git", "node_modules", ".browser_profile")


def _fontes():
    for projeto in PROJETOS:
        if not projeto.is_dir():
            continue
        for arquivo in projeto.rglob("*.py"):
            if any(parte in str(arquivo) for parte in IGNORAR):
                continue
            yield arquivo


class FonteIntegraTests(unittest.TestCase):
    def test_nenhum_byte_de_controle_no_codigo(self):
        sujos = []
        for arquivo in _fontes():
            bruto = arquivo.read_bytes()
            maus = {b for b in bruto if b < 32 and b not in PERMITIDOS}
            if maus:
                # a posição ajuda a achar a linha na hora de consertar
                primeiro = next(i for i, b in enumerate(bruto)
                                if b < 32 and b not in PERMITIDOS)
                linha = bruto[:primeiro].count(b"\n") + 1
                sujos.append(f"{arquivo.name}:{linha} "
                             f"bytes {sorted(hex(b) for b in maus)}")
        self.assertEqual([], sujos,
                         "byte de controle no fonte (heredoc comeu um '\\\\'?)")

    def test_o_json_de_config_tambem(self):
        """Config corrompido quebra em silêncio do mesmo jeito."""
        sujos = []
        for projeto in PROJETOS:
            for arquivo in (projeto / "config").glob("*.json") \
                    if (projeto / "config").is_dir() else []:
                bruto = arquivo.read_bytes()
                if any(b < 32 and b not in PERMITIDOS for b in bruto):
                    sujos.append(arquivo.name)
        self.assertEqual([], sujos)

    def test_a_varredura_realmente_pega_o_caso(self):
        """Sem isto, o teste poderia estar passando por não olhar nada."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "ruim.py"
            # 0x08 DE VERDADE (um byte), que é o que o heredoc produziu no
            # lugar de `\b`. Escrever "\\x08" aqui gravaria os quatro
            # caracteres e o teste passaria sem testar nada.
            alvo.write_bytes(b'x = re.search("_p" + chr(8), s)\n'
                             .replace(b'chr(8)', b'\x08'))
            bruto = alvo.read_bytes()
            self.assertIn(8, bruto, "o caso de teste não tem o byte ruim")
            self.assertTrue(any(b < 32 and b not in PERMITIDOS for b in bruto))

    def test_a_varredura_encontra_arquivos(self):
        """Uma lista vazia faria todos os testes acima passarem à toa."""
        self.assertGreater(len(list(_fontes())), 40)


if __name__ == "__main__":
    unittest.main()
