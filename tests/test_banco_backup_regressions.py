"""Gravar o banco nunca mais apaga personagem sem deixar copia.

02/09/2026, descoberto em 16/09. `gerador_database.py` grava com
`substituir=True`: o banco inteiro e trocado, sem aviso e sem volta. Naquele
dia isso levou junto todos os personagens gerados em agosto — e com eles 20
videos de build prontos e nao publicados, porque sem ficha no banco nao ha
estreia para gravar e sem estreia a build nunca entra na fila. Duas semanas
sem ninguem notar, porque o dano nao aparece aqui: aparece no publicador,
como uma pendencia que parece tarefa.

O contrato que fica:
1. Gravacao que REMOVE personagem copia o estado anterior antes.
2. Gravacao que so ACRESCENTA nao copia nada — a roleta insere um personagem
   por rodada e um backup por rodada seria deposito, nao rede.
3. A copia leva armas E personagens: eles so valem como par coerente.
4. Falhar ao copiar NUNCA impede a gravacao. Isto e rede, nao portao.
5. So as ultimas `COPIAS_GUARDADAS` ficam.
"""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from neural_fights.data import database


def _personagem(nome: str) -> dict:
    return {"nome": nome, "classe": "Guerreiro", "hp": 100, "ataque": 10,
            "defesa": 10, "velocidade": 10, "personalidade": "Bruto",
            "nome_arma": "Espada"}


def _arma(nome: str) -> dict:
    return {"nome": nome, "tipo": "Espada", "raridade": "Comum", "dano": 10}


class BackupDoBancoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.armas = str(self.dir / "armas.json")
        self.chars = str(self.dir / "personagens.json")

    def _gravar(self, nomes_chars, nomes_armas=("Espada",)):
        # `validar_database` e assunto de outros testes; aqui o que importa e
        # a copia, entao o caminho de validacao sai da frente.
        with patch.object(database, "validar_database", return_value=None):
            database.salvar_database(
                [_arma(n) for n in nomes_armas],
                [_personagem(n) for n in nomes_chars],
                arquivo_armas=self.armas,
                arquivo_personagens=self.chars,
            )

    def _copias(self):
        return sorted(d for d in os.listdir(self.dir)
                      if d.startswith("_backup-"))

    def test_remover_personagem_deixa_copia(self):
        self._gravar(["Silas o Sombrio", "Ylva Brumalok"])
        self.assertEqual([], self._copias(), "primeira gravacao nao perde nada")

        self._gravar(["Ylva Brumalok"])
        copias = self._copias()
        self.assertEqual(1, len(copias), "a perda de Silas tinha de copiar")

        salvos = json.loads(
            (self.dir / copias[0] / "personagens.json").read_text("utf-8"))
        self.assertEqual({"Silas o Sombrio", "Ylva Brumalok"},
                         {p["nome"] for p in salvos})

    def test_so_acrescentar_nao_copia(self):
        self._gravar(["Ylva Brumalok"])
        self._gravar(["Ylva Brumalok", "Silas o Sombrio"])
        self._gravar(["Ylva Brumalok", "Silas o Sombrio", "Emi Ossarhamar"])
        self.assertEqual([], self._copias(),
                         "insercao da roleta nao pode gerar backup")

    def test_a_copia_leva_as_armas_junto(self):
        self._gravar(["Silas o Sombrio"], nomes_armas=("Machado",))
        self._gravar(["Ylva Brumalok"], nomes_armas=("Espada",))
        copia = self.dir / self._copias()[0]
        armas = json.loads((copia / "armas.json").read_text("utf-8"))
        self.assertEqual(["Machado"], [a["nome"] for a in armas],
                         "armas e personagens so valem como par coerente")

    def test_copia_que_falha_nao_derruba_a_gravacao(self):
        self._gravar(["Silas o Sombrio"])
        with patch("shutil.copy2", side_effect=OSError("disco cheio")):
            self._gravar(["Ylva Brumalok"])
        gravado = json.loads(Path(self.chars).read_text("utf-8"))
        self.assertEqual(["Ylva Brumalok"], [p["nome"] for p in gravado],
                         "a rede de seguranca nunca vira portao")

    def test_guarda_so_as_ultimas(self):
        self._gravar(["a", "b", "c", "d", "e", "f", "g", "h"])
        for nome in ("b", "c", "d", "e", "f", "g", "h"):
            self._gravar([nome])
        self.assertLessEqual(len(self._copias()), database.COPIAS_GUARDADAS)

    def test_banco_novo_nao_copia(self):
        """Sem arquivo anterior nao ha o que perder."""
        self._gravar(["Ylva Brumalok"])
        self.assertEqual([], self._copias())

    # ---- BLD-3 (auditoria profunda, 14/10/2026) ----

    def test_remover_arma_deixa_copia(self):
        """O "Deletar" da aba Armas apagava sem copia nenhuma."""
        self._gravar(["Ylva Brumalok"], nomes_armas=("Espada", "Arma Sem Dono"))
        with patch.object(database, "validar_database", return_value=None):
            database.remover_arma(
                "Arma Sem Dono",
                arquivo_armas=self.armas,
                arquivo_personagens=self.chars,
            )
        copias = self._copias()
        self.assertEqual(1, len(copias), "a arma apagada tinha de copiar")
        salvas = json.loads(
            (self.dir / copias[0] / "armas.json").read_text("utf-8"))
        self.assertIn("Arma Sem Dono", {a["nome"] for a in salvas})
        atuais = json.loads(Path(self.armas).read_text("utf-8"))
        self.assertNotIn("Arma Sem Dono", {a["nome"] for a in atuais})

    def test_duas_perdas_no_mesmo_instante_nao_se_sobrescrevem(self):
        """Carimbo de segundo + exist_ok: a 2a copia apagava a 1a."""
        self._gravar(["a", "b", "c"])
        with patch.object(database, "_carimbo_da_copia",
                          return_value="20261014-101010-000000"):
            self._gravar(["b", "c"])
            self._gravar(["c"])
        copias = self._copias()
        self.assertEqual(["_backup-20261014-101010-000000",
                          "_backup-20261014-101010-000000-2"], copias)
        primeira = json.loads(
            (self.dir / copias[0] / "personagens.json").read_text("utf-8"))
        segunda = json.loads(
            (self.dir / copias[1] / "personagens.json").read_text("utf-8"))
        self.assertEqual({"a", "b", "c"}, {p["nome"] for p in primeira})
        self.assertEqual({"b", "c"}, {p["nome"] for p in segunda})

    def test_duas_perdas_seguidas_de_verdade_deixam_duas_copias(self):
        self._gravar(["a", "b", "c"])
        self._gravar(["b", "c"])
        self._gravar(["c"])
        self.assertEqual(2, len(self._copias()))

    def test_copia_manual_nao_ocupa_vaga_nem_e_podada(self):
        manual = self.dir / "_backup-manual-x"
        manual.mkdir()
        nomes = ["a", "b", "c", "d", "e", "f", "g"]
        self._gravar(nomes)
        for i in range(1, 7):  # 6 perdas
            self._gravar(nomes[i:])
        copias = self._copias()
        self.assertIn("_backup-manual-x", copias)
        automaticas = [c for c in copias if not c.startswith("_backup-manual-")]
        self.assertEqual(database.COPIAS_GUARDADAS, len(automaticas))


if __name__ == "__main__":
    unittest.main()
