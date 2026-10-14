# -*- coding: utf-8 -*-
"""HIS-1 (critico, auditoria de 11/10/2026): `roteiro.json` e `biblia.json`
nunca mais ficam pela metade no disco.

Eram gravados com `open(..., "w")` + `json.dump` direto no arquivo final, e o
`roteiro.json` e regravado a CADA parte. Um corte no meio deixava o JSON
truncado: `listar()` pulava a pasta calado, `carregar` levantava e a queda de
provedor (`gerar._situacao`) respondia "nova" — e o proximo provedor escrevia
OUTRA biblia na mesma pasta, por cima das cenas da antiga.

O que estes testes travam (nenhum abre navegador nem LLM; OUTPUTS e o diario
sao desviados para temporarios):

  (a) uma gravacao que morre no meio deixa o arquivo ANTERIOR intacto, em
      todos os gravadores (`salvar_serie`, `salvar`, `registrar_queda`,
      `gerar._gravar`, `conserto_de_cena.gravar_roteiro`), e nao sobra .tmp;
  (b) roteiro truncado = "ilegivel", e `escrever_serie` levanta SEM chamar
      `gerar_serie`/`retomar_serie` (nenhum provedor escreve por cima);
  (c) `listar()` com um roteiro truncado registra UM aviso no diario
      (etapa `roteiro.ilegivel`), uma vez por pasta e por dia.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from contos.pipeline import conserto_de_cena as C
from contos.roteiro import gerar as G
from contos.roteiro import roteiro as R


def _biblia(partes: int = 2) -> dict:
    return {"titulo": "A Casa", "serie_nome": "A Casa", "premissa": "p",
            "protagonista": "a woman", "partes_esperadas": partes,
            "partes": [{"n": n, "titulo": f"t{n}", "cliffhanger": ""}
                       for n in range(1, partes + 1)]}


def _parte(n: int) -> dict:
    return {"n": n, "titulo": f"Parte {n}", "cta": "", "provedor": "deepseek",
            "cenas": [{"n": 1, "narracao": "Era uma vez.", "imagem": "x",
                       "tempo": 4.0}]}


def _dump_que_morre(dados, fh, **_kw):
    """Escreve METADE do JSON e morre, como um processo cortado no meio."""
    texto = json.dumps(dados, ensure_ascii=False, indent=2)
    fh.write(texto[: len(texto) // 2])
    fh.flush()
    raise OSError("o processo morreu no meio da gravacao")


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pasta = Path(tmp.name)
        for modulo in (R, G):
            self.addCleanup(setattr, modulo, "OUTPUTS", modulo.OUTPUTS)
            modulo.OUTPUTS = self.pasta
        # o diario de producao nunca e tocado
        self.diario = []
        import builds.atividade as atividade
        patcher = mock.patch.object(
            atividade, "registrar",
            lambda *a, **k: self.diario.append((a, k)))
        patcher.start()
        self.addCleanup(patcher.stop)
        R._ILEGIVEIS_AVISADOS.clear()
        self.addCleanup(R._ILEGIVEIS_AVISADOS.clear)

    def _serie(self, historia_id: str = "historia_00001") -> Path:
        R.salvar_serie(_biblia(2), [_parte(1)], historia_id, provedor="deepseek")
        return self.pasta / historia_id / "roteiro.json"

    def _sem_tmp(self, pasta: Path) -> None:
        self.assertEqual([], [p.name for p in pasta.iterdir()
                              if p.name.endswith(".tmp")])


class GravacaoQueMorreNoMeio(_Base):
    def test_salvar_serie_que_morre_deixa_o_roteiro_anterior_inteiro(self):
        caminho = self._serie()
        antes = caminho.read_bytes()
        with mock.patch.object(R.json, "dump", _dump_que_morre):
            with self.assertRaises(OSError):
                R.salvar_serie(_biblia(2), [_parte(1), _parte(2)],
                               "historia_00001", provedor="deepseek")
        self.assertEqual(antes, caminho.read_bytes())
        self.assertEqual(1, len(R.carregar("historia_00001")["partes"]))
        self._sem_tmp(caminho.parent)

    def test_salvar_avulso_que_morre_deixa_o_anterior(self):
        R.salvar({"titulo": "um", "cenas": []}, "historia_00002")
        caminho = self.pasta / "historia_00002" / "roteiro.json"
        antes = caminho.read_bytes()
        with mock.patch.object(R.json, "dump", _dump_que_morre):
            with self.assertRaises(OSError):
                R.salvar({"titulo": "dois", "cenas": []}, "historia_00002")
        self.assertEqual(antes, caminho.read_bytes())
        self._sem_tmp(caminho.parent)

    def test_registrar_queda_que_morre_nao_levanta_e_nao_trunca(self):
        caminho = self._serie()
        antes = caminho.read_bytes()
        with mock.patch.object(R.json, "dump", _dump_que_morre):
            R.registrar_queda("historia_00001", {"provedor": "gemini"})
        self.assertEqual(antes, caminho.read_bytes())
        self._sem_tmp(caminho.parent)

    def test_biblia_que_morre_deixa_a_anterior(self):
        caminho = self.pasta / "historia_00003" / "biblia.json"
        G._gravar(caminho, _biblia(2))
        antes = caminho.read_bytes()
        with mock.patch.object(R.json, "dump", _dump_que_morre):
            with self.assertRaises(OSError):
                G._gravar(caminho, _biblia(6))
        self.assertEqual(antes, caminho.read_bytes())
        self._sem_tmp(caminho.parent)

    def test_conserto_de_cena_que_morre_deixa_o_roteiro(self):
        caminho = self._serie()
        antes = caminho.read_bytes()
        roteiro = json.loads(antes.decode("utf-8"))
        roteiro["titulo"] = "Outro"
        with mock.patch.object(R.json, "dump", _dump_que_morre):
            with self.assertRaises(OSError):
                C.gravar_roteiro("historia_00001", roteiro)
        self.assertEqual(antes, caminho.read_bytes())

    def test_arquivo_trancado_tenta_de_novo_e_depois_desiste_inteiro(self):
        """`PermissionError` na troca (leitor aberto no Windows): 3 tentativas;
        a 2a pega. E se todas falham, o arquivo de antes continua la."""
        caminho = self._serie()
        antes = caminho.read_bytes()
        real = R.os.replace
        vezes = {"n": 0}

        def trancado_uma_vez(origem, destino):
            vezes["n"] += 1
            if vezes["n"] == 1:
                raise PermissionError("o painel esta lendo")
            return real(origem, destino)

        with mock.patch.object(R.os, "replace", trancado_uma_vez), \
                mock.patch.object(R.time, "sleep", lambda _s: None):
            R.salvar_serie(_biblia(2), [_parte(1), _parte(2)],
                           "historia_00001", provedor="deepseek")
        self.assertEqual(2, vezes["n"])
        self.assertEqual(2, len(R.carregar("historia_00001")["partes"]))

        antes = caminho.read_bytes()

        def sempre_trancado(_o, _d):
            raise PermissionError("trancado")

        with mock.patch.object(R.os, "replace", sempre_trancado), \
                mock.patch.object(R.time, "sleep", lambda _s: None):
            with self.assertRaises(PermissionError):
                R.salvar_serie(_biblia(2), [_parte(1)], "historia_00001",
                               provedor="deepseek")
        self.assertEqual(antes, caminho.read_bytes())
        self._sem_tmp(caminho.parent)


class RoteiroTruncadoNaoViraNova(_Base):
    def _truncar(self, historia_id: str = "historia_00001") -> Path:
        caminho = self._serie(historia_id)
        texto = caminho.read_text(encoding="utf-8")
        caminho.write_text(texto[: len(texto) // 2], encoding="utf-8")
        return caminho

    def test_situacao_e_ilegivel_e_nao_nova(self):
        self._truncar()
        self.assertEqual("ilegivel", G._situacao("historia_00001"))
        # pasta sem roteiro continua "nova"; id vazio tambem
        self.assertEqual("nova", G._situacao("historia_00099"))
        self.assertEqual("nova", G._situacao(None))

    def test_escrever_serie_levanta_sem_chamar_nenhum_provedor(self):
        self._truncar()
        chamados = []
        for nome in ("gerar_serie", "retomar_serie"):
            self.addCleanup(setattr, G, nome, getattr(G, nome))
            setattr(G, nome, lambda *a, _n=nome, **k: chamados.append(_n))
        with self.assertRaises(G.GeracaoFalhou) as caso:
            G.escrever_serie(["deepseek", "gemini"],
                             historia_id="historia_00001",
                             log=lambda *_a: None)
        self.assertIn("nao le", str(caso.exception))
        self.assertEqual([], chamados)

    def test_listar_avisa_uma_vez_no_diario(self):
        self._truncar("historia_00001")
        self._serie("historia_00002")
        ids = [d["historia_id"] for d in R.listar()]
        self.assertEqual(["historia_00002"], ids)
        R.listar()                       # segunda leitura: nao repete o aviso
        R._ILEGIVEIS_AVISADOS.clear()    # outro processo, mesmo dia
        R.listar()
        avisos = [k for (_a, k) in self.diario
                  if k.get("etapa") == "roteiro.ilegivel"]
        self.assertEqual(1, len(avisos))
        self.assertEqual("historia_00001", avisos[0]["ref"])
        status = [a[1] for (a, k) in self.diario
                  if k.get("etapa") == "roteiro.ilegivel"]
        self.assertEqual(["aviso"], status)


if __name__ == "__main__":
    unittest.main()
