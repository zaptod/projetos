"""A pendencia da estreia precisa dizer se ainda da para resolver.

16/09/2026. Vinte das trinta builds fora da fila de publicacao paravam na
mesma linha: "sem luta no fim (estreia nao gravada)". A frase se le como uma
tarefa — grave a luta e ela sai. Nenhuma das vinte era gravavel: o banco do
neural_fights foi refeito em 02/09 e os personagens criados em agosto sairam
junto. Sem ficha no banco, `_gravar_estreia` desiste na primeira linha
("nao esta no banco; estreia pulada") e devolve None.

Entao a lista de pendencias contava vinte tarefas todo dia, nenhuma delas
executavel, e ninguem descobria sem ir ler o banco. E o mesmo defeito do
ledger que chamava rascunho de publicado: verdadeiro sobre o que mediu,
enganoso sobre o que parece dizer.

O que fica travado por contrato:
1. Personagem fora do banco: a mensagem diz IMPOSSIVEL e nomeia quem falta.
2. Personagem no banco: a mensagem antiga continua, porque ali gravar resolve.
3. Banco ilegivel NAO inventa lapide: volta para a mensagem antiga. Errar para
   "tente gravar" custa uma tentativa; errar para "perdido" abandona estoque
   bom para sempre.
4. A estreia gravada nao gera pendencia nenhuma, com banco ou sem.
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from builds.publicar import catalogo


def _build(raiz: Path, nome: str, *, com_estreia: bool) -> Path:
    """Uma build completa, faltando (ou nao) so a estreia."""
    pasta = raiz / "generation_00023"
    (pasta / "estreia").mkdir(parents=True, exist_ok=True)
    (pasta / "character.json").write_text(
        json.dumps({"nome": nome}), encoding="utf-8")
    for arquivo in ("character_weapon_video.mp4",
                    "character_weapon_reference.png",
                    "character_image.png", "final_celular.mp4"):
        (pasta / arquivo).write_bytes(b"x")
    if com_estreia:
        (pasta / "estreia" / "fight.json").write_text("{}", encoding="utf-8")
    return pasta


class EstreiaImpossivelTests(unittest.TestCase):
    def setUp(self):
        # O cache existe para nao reler o banco por build; entre testes ele
        # mentiria.
        catalogo._nomes_no_banco.cache_clear()
        self.addCleanup(catalogo._nomes_no_banco.cache_clear)

    def _pendencias(self, nome, banco, *, com_estreia=False):
        with TemporaryDirectory() as tmp:
            pasta = _build(Path(tmp), nome, com_estreia=com_estreia)
            with patch.object(catalogo, "_nomes_no_banco", return_value=banco):
                return catalogo.pendencias_da_build(pasta, "celular")

    def test_fora_do_banco_diz_impossivel_e_nomeia(self):
        pend = self._pendencias("Silas o Sombrio", frozenset({"Ylva Brumalok"}))
        self.assertEqual(1, len(pend), pend)
        self.assertIn("impossivel", pend[0])
        self.assertIn("Silas o Sombrio", pend[0])
        # Nao pode continuar parecendo tarefa.
        self.assertNotIn("estreia nao gravada", pend[0])

    def test_no_banco_continua_pedindo_para_gravar(self):
        pend = self._pendencias("Ylva Brumalok", frozenset({"Ylva Brumalok"}))
        self.assertEqual(["sem luta no fim (estreia nao gravada)"], pend)

    def test_banco_ilegivel_nao_inventa_lapide(self):
        pend = self._pendencias("Silas o Sombrio", None)
        self.assertEqual(["sem luta no fim (estreia nao gravada)"], pend)

    def test_estreia_gravada_nao_tem_pendencia(self):
        for banco in (None, frozenset(), frozenset({"Silas o Sombrio"})):
            with self.subTest(banco=banco):
                pend = self._pendencias("Silas o Sombrio", banco,
                                        com_estreia=True)
                self.assertEqual([], pend)

    def test_sem_character_json_volta_para_a_mensagem_antiga(self):
        """Sem nome nao da para afirmar que esta perdido."""
        with TemporaryDirectory() as tmp:
            pasta = _build(Path(tmp), "Silas o Sombrio", com_estreia=False)
            (pasta / "character.json").unlink()
            with patch.object(catalogo, "_nomes_no_banco",
                              return_value=frozenset({"Outro"})):
                pend = catalogo.pendencias_da_build(pasta, "celular")
        self.assertEqual(["sem luta no fim (estreia nao gravada)"], pend)

    def test_banco_e_lido_uma_vez_so(self):
        """`pendencias_da_build` roda por build; reler o banco em cada uma
        custaria caro num catalogo de 90."""
        from builds.nf_bridge import loader as nf
        with patch.object(nf.database, "carregar_database",
                          return_value=([], [{"nome": "Ylva Brumalok"}])) as carregar:
            for _ in range(5):
                catalogo._nomes_no_banco()
        self.assertEqual(1, carregar.call_count)


if __name__ == "__main__":
    unittest.main()
