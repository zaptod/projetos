# -*- coding: utf-8 -*-
"""Conserto da auditoria profunda de 11/10/2026 — publicacao (lado builds).

Dois arquivos de estado que, lidos com falha, viravam `{}` e eram gravados
por cima na chamada seguinte; e a marca "a conferir" que nao subia de nivel.

1. `contas.json` (`builds.contas`): `_ler` devolvia `{}` para QUALQUER
   `OSError`/`ValueError` e `_gravar` escrevia com `open("w")`, sem
   temporario, sem `os.replace`, sem trava. Prova p1 da auditoria: com o JSON
   pela metade, um `identificar()` deixava o arquivo so com `['identidades']`
   — a conta de cada canal sumia e o Studio publicava "onde abrir". Com o
   arquivo trancado por outro handle, `escolher()` levantava e o registro
   ficava com 0 bytes (tinha 1484). Agora: ausente = vazio; trancado = tenta
   de novo; JSON partido = copia `.corrompido` e LEVANTA (nada e gravado por
   cima); gravacao por temporario + `os.replace`, sob a trava `contas_json`.

2. `marcar_para_conferir` devolvia True sem tocar no arquivo quando o id ja
   estava la — a marca `[audio]` (que a maquina solta sozinha) nunca virava a
   de clique (que so pessoa tira). Prova prova1: `revisar_marcas` soltava a
   marca e o video com clique dado voltava a fila (duplicata).

Nada toca o estado real: registro e lista "a conferir" em pasta temporaria.
"""
from __future__ import annotations

import contextlib
import json
import tempfile
import unittest
from pathlib import Path

from builds import atividade, contas, travas
from builds.publicar import desfecho

REGISTRO_BOM = {
    "servicos": {
        "tiktok": {"contas": ["principal", "historinhas"],
                   "ativa": {"historias": "historinhas"}},
        "youtube_web": {"contas": ["principal", "neural_fights", "historinhas"],
                        "ativa": {"builds": "neural_fights",
                                  "historias": "historinhas"}},
    },
    "identidades": {"youtube_web": {"historinhas": {"id": "UC_hist",
                                                    "rotulo": "historinhas"}}},
}


class _ComRegistro(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        self.registro = self.pasta / "contas.json"
        antes = (contas.ARQUIVO, contas.runtime_dir)
        contas.ARQUIVO = self.registro
        contas.runtime_dir = lambda: self.pasta
        self.addCleanup(lambda: setattr(contas, "ARQUIVO", antes[0]))
        self.addCleanup(lambda: setattr(contas, "runtime_dir", antes[1]))
        self.diario = []
        real = atividade.registrar
        atividade.registrar = lambda *a, **k: self.diario.append(a)
        self.addCleanup(lambda: setattr(atividade, "registrar", real))

    def _gravar_bom(self):
        self.registro.write_text(json.dumps(REGISTRO_BOM, ensure_ascii=False,
                                            indent=2), encoding="utf-8")

    def _trancar_open(self, falhas: int):
        """`open` do modulo falha `falhas` vezes com PermissionError (outro
        processo com o arquivo), depois volta ao normal."""
        import builtins
        contagem = {"n": 0}

        def trancado(*a, **k):
            if contagem["n"] < falhas:
                contagem["n"] += 1
                raise PermissionError("[WinError 32] arquivo em uso")
            return builtins.open(*a, **k)
        contas.open = trancado
        self.addCleanup(lambda: delattr(contas, "open"))
        return contagem


class LeituraQueFalha(_ComRegistro):

    def test_arquivo_ausente_e_vazio(self):
        self.assertEqual({}, contas._ler())

    def test_json_partido_levanta_e_guarda_copia(self):
        self._gravar_bom()
        partido = self.registro.read_text(encoding="utf-8")[:150]
        self.registro.write_text(partido, encoding="utf-8")
        with self.assertRaises(ValueError):
            contas._ler()
        copia = self.registro.with_suffix(".json.corrompido")
        self.assertTrue(copia.is_file())
        self.assertEqual(partido, copia.read_text(encoding="utf-8"))

    def test_a_gravacao_seguinte_NAO_apaga_o_registro_partido(self):
        """O caso da prova p1: `identificar()` sobre a leitura que falhou
        deixava o arquivo so com `['identidades']`."""
        self._gravar_bom()
        partido = self.registro.read_text(encoding="utf-8")[:150]
        self.registro.write_text(partido, encoding="utf-8")
        with self.assertRaises(ValueError):
            contas.identificar("youtube_web", "historinhas", identificador="UC_x")
        with self.assertRaises(ValueError):
            contas.escolher("tiktok", "builds", "outra")
        self.assertEqual(partido, self.registro.read_text(encoding="utf-8"),
                         "o arquivo partido fica como esta, para olho humano")
        self.assertEqual([], list(self.pasta.glob("*.tmp")))

    def test_arquivo_trancado_tenta_de_novo(self):
        self._gravar_bom()
        contagem = self._trancar_open(falhas=2)
        self.assertEqual("historinhas", contas.ativa("tiktok", "historias"))
        self.assertEqual(2, contagem["n"])

    def test_trancado_ate_o_fim_levanta_em_vez_de_devolver_vazio(self):
        self._gravar_bom()
        self._trancar_open(falhas=99)
        with self.assertRaises(OSError):
            contas._ler()
        # e `ativa` nao responde "principal" por cima de um registro que
        # existe: o Studio publicaria no canal errado.
        with self.assertRaises(OSError):
            contas.ativa("youtube_web", "historias")


class GravacaoAtomica(_ComRegistro):

    def test_grava_por_temporario_e_replace_sob_a_trava(self):
        usadas = []
        original = travas.trava

        @contextlib.contextmanager
        def espia(nome, esperar=0.0):
            usadas.append(nome)
            with original(nome, esperar=esperar) as minha:
                yield minha
        travas.trava = espia
        self.addCleanup(lambda: setattr(travas, "trava", original))
        self.assertEqual("canal_x", contas.adicionar("tiktok", "Canal X"))
        self.assertIn("contas_json", usadas)
        self.assertEqual([], list(self.pasta.glob("*.tmp")))
        dados = json.loads(self.registro.read_text(encoding="utf-8"))
        self.assertIn("canal_x", dados["servicos"]["tiktok"]["contas"])

    def test_trava_ocupada_por_outro_processo_nao_trunca_o_arquivo(self):
        self._gravar_bom()
        antes = self.registro.read_text(encoding="utf-8")
        original = travas.trava

        @contextlib.contextmanager
        def ocupada(nome, esperar=0.0):
            yield False
        travas.trava = ocupada
        self.addCleanup(lambda: setattr(travas, "trava", original))
        with self.assertRaises(TimeoutError):
            contas.escolher("tiktok", "builds", "historinhas")
        self.assertEqual(antes, self.registro.read_text(encoding="utf-8"))

    def test_escolher_limpa_o_nome_como_adicionar(self):
        contas.escolher("tiktok", "historias", "Canal Histórias")
        self.assertEqual("canal_historias", contas.ativa("tiktok", "historias"))
        self.assertEqual(["principal", "canal_historias"], contas.contas("tiktok"))
        self.assertEqual("canal_historias", contas.adicionar("tiktok", "Canal Histórias"))
        self.assertEqual(["principal", "canal_historias"], contas.contas("tiktok"),
                         "um destino, um nome")

    def test_renomear_grava_o_registro_ANTES_de_mover_a_pasta(self):
        """Prova p1 (5d): a pasta ja se chamava `<novo>` e o registro ainda
        dizia `<antigo>` — `tem_login` virava False no meio da fila."""
        contas.adicionar("tiktok", "velha")
        contas.escolher("tiktok", "historias", "velha")
        perfil = self.pasta / "browser_profiles" / "tiktok__velha"
        perfil.mkdir(parents=True)
        (perfil / "Cookies").write_bytes(b"login")
        real = contas._gravar

        def recusa(_dados):
            raise PermissionError("registro trancado")
        contas._gravar = recusa
        self.addCleanup(lambda: setattr(contas, "_gravar", real))
        with self.assertRaises(PermissionError):
            contas.renomear("tiktok", "velha", "nova")
        self.assertTrue(perfil.is_dir(), "a pasta NAO foi movida")
        self.assertFalse((self.pasta / "browser_profiles" / "tiktok__nova").exists())
        contas._gravar = real
        self.assertEqual("velha", contas.ativa("tiktok", "historias"))

    def test_renomear_que_da_certo_move_a_pasta_junto(self):
        contas.adicionar("tiktok", "velha")
        perfil = self.pasta / "browser_profiles" / "tiktok__velha"
        perfil.mkdir(parents=True)
        r = contas.renomear("tiktok", "velha", "nova")
        self.assertTrue((self.pasta / "browser_profiles" / "tiktok__nova").is_dir())
        self.assertEqual(1, len(r["movidos"]))
        self.assertIn("nova", contas.contas("tiktok"))


class MarcaQueSobeDeNivel(unittest.TestCase):
    CLIQUE = ("cliquei em publicar, mas o TikTok nao confirmou. A janela "
              "ficou aberta: confira se o video subiu.")
    AUDIO = "[audio] a luta esta muda (seg_021 a -91 dB)"
    VIDEO = "generation_00099:build:celular"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.arq = Path(self.tmp.name) / "_tiktok_a_conferir.json"
        self.addCleanup(setattr, desfecho, "arquivo_a_conferir",
                        desfecho.arquivo_a_conferir)
        desfecho.arquivo_a_conferir = lambda _c, _p="tiktok": self.arq
        self.addCleanup(setattr, atividade, "registrar", atividade.registrar)
        self.diario = []
        atividade.registrar = lambda *a, **k: self.diario.append(a)

    def _estado(self):
        return json.loads(self.arq.read_text(encoding="utf-8"))[self.VIDEO]["estado"]

    def test_marca_de_audio_e_promovida_a_marca_de_clique(self):
        desfecho.marcar_para_conferir("builds", self.VIDEO, self.AUDIO)
        self.assertTrue(desfecho.marcar_para_conferir("builds", self.VIDEO, self.CLIQUE))
        self.assertEqual(self.CLIQUE, self._estado())
        # e o som voltando NAO solta mais o video (a prova1 da auditoria):
        self.assertFalse(desfecho.soltar_marca("builds", self.VIDEO, "tiktok",
                                               prefixo="[audio] "))
        self.assertEqual({self.VIDEO}, desfecho.a_conferir("builds", "tiktok"))

    def test_marca_de_clique_nao_desce_para_audio(self):
        desfecho.marcar_para_conferir("builds", self.VIDEO, self.CLIQUE)
        self.assertTrue(desfecho.marcar_para_conferir("builds", self.VIDEO, self.AUDIO))
        self.assertEqual(self.CLIQUE, self._estado())

    def test_a_mesma_marca_duas_vezes_nao_repete_o_diario(self):
        desfecho.marcar_para_conferir("builds", self.VIDEO, self.AUDIO)
        quantos = len(self.diario)
        texto = self.arq.read_text(encoding="utf-8")
        self.assertTrue(desfecho.marcar_para_conferir("builds", self.VIDEO,
                                                      "[audio] outra frase"))
        self.assertEqual(texto, self.arq.read_text(encoding="utf-8"))
        self.assertEqual(quantos, len(self.diario))


if __name__ == "__main__":
    unittest.main()
