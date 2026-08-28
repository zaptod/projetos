# -*- coding: utf-8 -*-
"""Regressões do painel de fluxo (src/pipeline/fluxo.py).

O que este arquivo protege é a pergunta que o painel responde: "e agora, o
que eu faço?". Cada teste fixa uma resposta que o operador precisa ver certa:

1. O DISCO manda sobre a fila — artefato pronto é etapa concluída, mesmo com
   job velho parado em `pending` (senão o painel manda gerar de novo o que já
   existe, que foi como generation_00014 acabou baixado duas vezes).
2. Job falhado vira próximo passo ACIONÁVEL, com o comando na frase.
3. Dependência não satisfeita se explica ("esperando a arma"), em vez de
   aparecer como um "na fila" mudo que não diz por que não anda.
4. Clipe baixado que não entrou no vídeo publicável vira ALERTA — é o caso
   que nenhuma ferramenta reporta sozinha.
5. Chave de torneio conta as duas fontes (builds prontas e banco).
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.identity import queue, slots                       # noqa: E402
from src.pipeline import fluxo                              # noqa: E402

CONTEUDO = b"x" * (fluxo.BYTES_MINIMOS + 1)


def _job(gid: str, slot: str, status: str, **extra) -> dict:
    job = {"generation_id": gid, "slot": slot, "status": status,
           "job_id": f"{gid}#{slot}", "attempts": 1}
    job.update(extra)
    return job


class FluxoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.outputs = Path(self._tmp.name)
        self.gid = "generation_00099"
        self.build = self.outputs / self.gid
        self.build.mkdir(parents=True)
        (self.build / "character.json").write_text(
            json.dumps({"nome": "Cobaia", "classe": "Ninja (Velocidade)",
                        "nome_arma": "Katana"}), encoding="utf-8")
        self.addCleanup(self._tmp.cleanup)

    # ------------------------------------------------------------ utilidades
    def _arquivo(self, nome: str, dentro: Path | None = None):
        destino = (dentro or self.build) / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(CONTEUDO)
        return destino

    def _build_completa(self):
        for perfil in ("celular", "normal"):
            self._arquivo(f"final_{perfil}.mp4")

    def _snapshot(self, jobs=()):
        with patch.object(fluxo.config, "OUTPUTS", self.outputs), \
             patch.object(fluxo.queue, "listar", lambda: list(jobs)), \
             patch.object(fluxo, "_arena", lambda: {"lutas": 0, "campeao": None,
                                                    "ranking": []}), \
             patch.object(fluxo, "_torneios", lambda: []):
            return fluxo.snapshot()

    def _geracao(self, jobs=()):
        return self._snapshot(jobs)["geracoes"][0]

    # ---------------------------------------------------------------- testes
    def test_disco_manda_sobre_a_fila(self):
        """Artefato no disco é etapa PRONTA, mesmo com job pendente na fila."""
        self._build_completa()
        self._arquivo(slots.ARQUIVO[slots.CHARACTER])
        geracao = self._geracao([_job(self.gid, slots.CHARACTER, queue.PENDENTE)])
        self.assertEqual(fluxo.OK, geracao["etapas"]["personagem"]["estado"])
        self.assertNotIn("identity run", geracao["proximo_passo"].split("falta")[0])

    def test_falha_vira_proximo_passo_com_o_comando(self):
        self._build_completa()
        geracao = self._geracao([
            _job(self.gid, slots.CHARACTER, queue.FALHOU, error="sem creditos"),
        ])
        self.assertEqual(fluxo.FALHOU, geracao["etapas"]["personagem"]["estado"])
        self.assertIn("identity run generation_00099", geracao["proximo_passo"])
        self.assertIn("sem creditos", geracao["etapas"]["personagem"]["detalhe"])

    def test_dependencia_pendente_se_explica(self):
        """O payoff parado por causa da junção diz ISSO, não só 'na fila'."""
        self._build_completa()
        self._arquivo(slots.ARQUIVO[slots.CHARACTER])
        self._arquivo(slots.ARQUIVO[slots.WEAPON])
        geracao = self._geracao([
            _job(self.gid, slots.REFERENCIA, queue.RODANDO),
            _job(self.gid, slots.CHARACTER_WEAPON, queue.PENDENTE,
                 depends_on=[f"{self.gid}#{slots.REFERENCIA}"]),
        ])
        self.assertEqual(fluxo.RODANDO, geracao["etapas"]["juncao"]["estado"])
        detalhe = geracao["etapas"]["payoff"]["detalhe"]
        self.assertIn("esperando", detalhe)
        self.assertIn(slots.rotulo(slots.REFERENCIA), detalhe)

    def test_sem_video_da_build_o_passo_e_renderizar(self):
        geracao = self._geracao()
        self.assertEqual(fluxo.AUSENTE, geracao["etapas"]["build"]["estado"])
        self.assertIn("--rerender generation_00099", geracao["proximo_passo"])

    def test_clipe_fora_do_video_publicavel_vira_alerta(self):
        """mp4 final mais VELHO que o clipe: o vídeo no disco não tem o clipe."""
        self._build_completa()
        clipe = self._arquivo(slots.ARQUIVO[slots.CHARACTER_WEAPON])
        import os
        agora = clipe.stat().st_mtime
        for perfil in ("celular", "normal"):
            antigo = self.build / f"final_{perfil}.mp4"
            os.utime(antigo, (agora - 3600, agora - 3600))

        dados = self._snapshot()
        geracao = dados["geracoes"][0]
        self.assertTrue(geracao["etapas"]["build"]["desatualizado"])
        self.assertTrue(any("não tem o clipe" in a for a in dados["alertas"]))

    def test_tudo_pronto_menos_a_estreia(self):
        self._build_completa()
        for slot in slots.JOBS:
            self._arquivo(slots.ARQUIVO[slot])
        geracao = self._geracao()
        self.assertIn("estreia", geracao["proximo_passo"])
        self.assertFalse(geracao["completa"])

        for perfil in ("celular", "normal"):
            self._arquivo(f"final_{perfil}.mp4", dentro=self.build / "estreia")
        geracao = self._geracao()
        self.assertTrue(geracao["completa"])
        self.assertIn("completa", geracao["proximo_passo"])

    def test_chave_do_torneio_conta_as_duas_fontes(self):
        self._build_completa()
        for slot in slots.JOBS:
            self._arquivo(slots.ARQUIVO[slot])
        with patch.object(fluxo, "_chaves", wraps=fluxo._chaves):
            dados = self._snapshot()
        chaves = dados["chaves"]
        self.assertEqual(1, chaves["prontos"])
        self.assertEqual(0, chaves["chave_gerados"])
        self.assertEqual(3, chaves["faltam_para_proxima"])
        # o banco é a outra fonte e continua respondendo por si
        self.assertGreaterEqual(chaves["chave_banco"], 0)

    def test_worker_parado_com_fila_cheia_vira_alerta(self):
        self._build_completa()
        dados = self._snapshot([
            _job(self.gid, slots.CHARACTER, queue.PENDENTE,
                 updated_at="2020-01-01T00:00:00+00:00"),
        ])
        self.assertTrue(any("worker" in a for a in dados["alertas"]), dados["alertas"])


if __name__ == "__main__":
    unittest.main()
