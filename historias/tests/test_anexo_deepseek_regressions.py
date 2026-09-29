# -*- coding: utf-8 -*-
"""O ANEXO NO DEEPSEEK (29/09/2026, tarefa dc176b96 da Vila das IAs).

Ate aqui `DEEPSEEK["anexo_prova"]` era vazio e o carteiro recusava na hora
qualquer mensagem do Adrian com imagem para o DeepSeek. O site ACEITA anexo:
clipe a esquerda do enviar, `input[type=file]` com `multiple` e `accept` de
imagens, PDF, texto/codigo e Office (medido na sessao guiada das 02:21 e de
novo as 14:32, `random_builds/outputs/_ias/deepseek/anexo/`).

O que foi medido, e o que este arquivo trava:

1. A MINIATURA de imagem e um `div[role=button]` com `<img src="blob:...">`
   (alt = nome do arquivo); arquivo que nao e imagem vira um CHIP com o nome
   e "TXT 59B". Nenhum dos dois tem aria-label, e as classes sao hashes do
   build (`d5fa3d1b`, `_9f130b7`): os seletores nao podem depender delas.
2. A MINIATURA NAO PROVA QUE SUBIU. Ela aparece em 0,07 s; um PNG de 3,2 MB
   so terminou de subir em 2,8 s — ate la o spinner gira e o botao de enviar
   fica `ds-button--disabled`. Mandar o prompt nesse intervalo e clicar num
   botao morto. `anexo_subindo` e a espera por isso.

Nenhum navegador abre aqui: a pagina e um duble com relogio falso.

Rode de dentro de historias/:
    python -m unittest tests.test_anexo_deepseek_regressions -v
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from contos.llm import cliente as llm_cliente                      # noqa: E402
from contos.llm import seletores                                   # noqa: E402

# Classe gerada no build do site: 6-8 hex, com ou sem "_" na frente.
CLASSE_DE_HASH = re.compile(r"\.(_?[0-9a-f]{6,8})\b")


class _Relogio:
    """Substitui o modulo `time` do cliente: dormir so anda o ponteiro."""

    def __init__(self):
        self.agora = 1000.0

    def monotonic(self):
        return self.agora

    def sleep(self, s):
        self.agora += float(s)


class _Alvo:
    def __init__(self, pagina, seletor):
        self.pagina, self.seletor = pagina, seletor

    def count(self):
        return self.pagina.contar(self.seletor)

    @property
    def first(self):
        return self

    def nth(self, _i):
        return self

    def is_visible(self):
        return True

    def set_input_files(self, arquivos):
        self.pagina.receber(arquivos)


class _PaginaDoDeepSeek:
    """O compositor medido: a miniatura sai na hora; o botao de enviar fica
    desabilitado por `sobe_em_s` segundos (None = nunca termina)."""

    def __init__(self, relogio, sel, sobe_em_s=2.8, miniatura=True):
        self.relogio, self.sel = relogio, sel
        self.sobe_em_s, self.miniatura = sobe_em_s, miniatura
        self.arquivos = 0
        self.enviado_em = None

    def locator(self, seletor):
        return _Alvo(self, seletor)

    def receber(self, arquivos):
        self.arquivos += len(arquivos) if isinstance(arquivos, list) else 1
        self.enviado_em = self.relogio.monotonic()

    def subindo(self):
        if self.enviado_em is None:
            return False
        if self.sobe_em_s is None:
            return True
        return self.relogio.monotonic() - self.enviado_em < self.sobe_em_s

    def contar(self, seletor):
        if seletor in self.sel.get("anexo_input", []):
            return 1
        if seletor in (self.sel.get("anexo_prova") or []):
            return self.arquivos if self.miniatura else 0
        if seletor in (self.sel.get("anexo_subindo") or []):
            return 1 if self.subindo() else 0
        return 0


class SeletoresDoAnexo(unittest.TestCase):

    def test_o_deepseek_tem_prova_de_anexo(self):
        # Vazio, o carteiro recusava toda imagem ("mande sem anexo").
        self.assertTrue(seletores.DEEPSEEK["anexo_prova"])
        self.assertTrue(seletores.DEEPSEEK["anexo_input"])

    def test_nenhum_seletor_de_anexo_depende_de_classe_de_hash(self):
        for chave in ("anexo_prova", "anexo_subindo", "anexo_input"):
            for seletor in seletores.DEEPSEEK.get(chave) or []:
                self.assertIsNone(
                    CLASSE_DE_HASH.search(seletor),
                    f"{chave}: {seletor!r} usa classe gerada no build")

    def test_a_prova_conta_imagem_e_arquivo_num_seletor_so(self):
        # `_provas_de_anexo` pega o MAIOR numero entre os seletores: imagem e
        # chip em seletores separados contariam 1 para dois anexos. A lista
        # CSS com virgula soma (conferido no HTML medido: 0 / 1 / 2).
        primeiro = seletores.DEEPSEEK["anexo_prova"][0]
        self.assertIn("img[src^='blob:']", primeiro)
        self.assertIn("text-matches", primeiro)
        self.assertIn(",", primeiro)

    def test_subindo_e_o_botao_de_enviar_desabilitado(self):
        subindo = seletores.DEEPSEEK["anexo_subindo"]
        self.assertTrue(any("ds-button--disabled" in s for s in subindo))
        # e e o MESMO botao que `enviar` clica, nao outro
        base = seletores.DEEPSEEK["enviar"][0]
        self.assertTrue(any(s.startswith(base) for s in subindo))

    def test_so_o_deepseek_ganhou_a_espera_de_upload(self):
        for nome in ("chatgpt", "gemini", "grok"):
            self.assertFalse(seletores.do_provedor(nome).get("anexo_subindo"),
                             nome)


class EsperaDoUpload(unittest.TestCase):

    def setUp(self):
        self.relogio = _Relogio()
        self.addCleanup(setattr, llm_cliente, "time", llm_cliente.time)
        llm_cliente.time = self.relogio
        pasta = tempfile.TemporaryDirectory(dir=_temp_no_e())
        self.addCleanup(pasta.cleanup)
        self.png = Path(pasta.name) / "circulo.png"
        self.png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 64)

    def _cliente(self, provedor, pagina):
        cli = llm_cliente.ClienteLLM(provedor, None, pagina,
                                     log=lambda *_a: None)
        pagina.sel = cli.sel
        return cli

    def test_so_devolve_quando_o_botao_de_enviar_volta(self):
        pagina = _PaginaDoDeepSeek(self.relogio, {}, sobe_em_s=2.8)
        cli = self._cliente("deepseek", pagina)
        self.assertEqual(1, cli.anexar([self.png], espera=120.0))
        # a miniatura saiu na hora; quem segurou foi o upload
        self.assertGreaterEqual(self.relogio.agora - pagina.enviado_em, 2.8)
        self.assertFalse(pagina.subindo())

    def test_upload_que_nunca_termina_falha_com_motivo(self):
        pagina = _PaginaDoDeepSeek(self.relogio, {}, sobe_em_s=None)
        cli = self._cliente("deepseek", pagina)
        with self.assertRaises(llm_cliente.LLMFalhou) as erro:
            cli.anexar([self.png], espera=30.0)
        self.assertIn("nao terminou de subir", str(erro.exception))

    def test_sem_miniatura_continua_falhando_como_antes(self):
        pagina = _PaginaDoDeepSeek(self.relogio, {}, miniatura=False)
        cli = self._cliente("deepseek", pagina)
        with self.assertRaises(llm_cliente.LLMFalhou) as erro:
            cli.anexar([self.png], espera=10.0)
        self.assertIn("nenhuma miniatura", str(erro.exception))

    def test_provedor_sem_anexo_subindo_nao_espera_nada(self):
        # Grok/ChatGPT/Gemini: a miniatura (o "Remover") continua sendo a
        # prova, como antes — a espera nova nao pode mudar o tempo deles.
        pagina = _PaginaDoDeepSeek(self.relogio, {}, sobe_em_s=None)
        cli = self._cliente("grok", pagina)
        comeco = self.relogio.agora
        self.assertEqual(1, cli.anexar([self.png], espera=30.0))
        self.assertLess(self.relogio.agora - comeco, 1.0)


def _temp_no_e():
    """TEMP no E: (o C: vive quase cheio); cai no padrao se nao houver E:."""
    candidato = Path("E:/projetos-wt/_tmp_testes")
    try:
        candidato.mkdir(parents=True, exist_ok=True)
        return str(candidato)
    except OSError:
        return None


if __name__ == "__main__":
    unittest.main()
