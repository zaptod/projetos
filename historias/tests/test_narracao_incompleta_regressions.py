# -*- coding: utf-8 -*-
"""A narração incompleta que virou vídeo — e as cinco camadas que deixaram (02/09/2026).

O defeito: a parte 1 da `historia_00008` foi ao disco com **21,8 s de voz para
uma narração de 150 s**. As 417 palavras estavam todas lá, espremidas numa
faixa impossível de 19 palavras por segundo; o vídeo saiu com 35,7 s, cada uma
das 14 cenas no piso de 2,5 s, e os últimos 13,9 s completamente mudos.

A causa foi UM arquivo: `outputs/_voz_cache/7b754cf4….mp3`, 131.040 bytes,
o único dos 265 mp3 do cache sem o `.words.json` ao lado. O `_edge()` grava o
mp3 aos pedaços dentro do `async for` e só escreve os limites de palavra
DEPOIS; quando a síntese não chega ao fim, sobra o áudio pela metade — e o
`except` não roda para apagá-lo. Como o cache aceitava qualquer arquivo com
mais de 200 bytes, esse pedaço foi servido em toda re-renderização seguinte.
Re-renderizar não adiantava: a resposta errada já estava guardada.

O que estes testes travam, camada por camada:

    motor      áudio inacabado não vira arquivo de cache (grava em .parcial)
    plausível  417 palavras em 21,8 s é recusado; 2,8 palavras/s passa
    cache      entrada sem os limites, ou implausível, é descartada e refeita
    plano      `montar()` levanta quando a voz não cobre as cenas
    vistoria   o mp4 não passa se a narração não couber, nem com silêncio no fim

Rode de dentro de historias/:
    python -m unittest tests.test_narracao_incompleta_regressions -v
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from contos.pipeline import conferir as C                          # noqa: E402
from contos.publicar import qualidade                              # noqa: E402
from contos.video import timeline                                  # noqa: E402

from builds.content import voz                                     # noqa: E402

# O texto real da parte 1 tinha 417 palavras e devia durar ~150 s.
PALAVRAS = 417
TEXTO = " ".join(f"palavra{i}" for i in range(PALAVRAS))
DURACAO_BOA = 149.0
DURACAO_DEFEITO = 21.84


class PlausibilidadeTests(unittest.TestCase):
    """Palavra contra segundo: a única pergunta que separa leitura de pedaço."""

    def test_a_leitura_inteira_passa(self):
        self.assertEqual(voz.implausivel(TEXTO, DURACAO_BOA), "")

    def test_o_audio_do_defeito_e_recusado(self):
        motivo = voz.implausivel(TEXTO, DURACAO_DEFEITO)
        self.assertTrue(motivo)
        self.assertIn("cortado", motivo)
        # A mensagem precisa dizer o número, senão não explica nada.
        self.assertIn("19.1", motivo)

    def test_audio_longo_demais_para_o_texto_tambem_e_recusado(self):
        self.assertTrue(voz.implausivel(TEXTO, 900.0))

    def test_texto_curto_nao_e_julgado(self):
        # "Guerreiro." em 1 s dá 1 palavra/s e está certo: a medida só
        # significa alguma coisa com texto suficiente.
        self.assertEqual(voz.implausivel("Guerreiro. Na media.", 1.0), "")

    def test_a_faixa_cobre_a_fala_real_medida(self):
        # As 30 partes boas mediram de 1,99 a 2,87 palavras/s.
        for taxa in (2.0, 2.5, 2.87):
            self.assertEqual(voz.implausivel(TEXTO, PALAVRAS / taxa), "")


class CacheDeVozTests(unittest.TestCase):
    """O cache não serve o que não presta — e se cura sozinho."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cache = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _entrada(self, nome="a.mp3", segundos=DURACAO_BOA, com_sidecar=True):
        mp3 = self.cache / nome
        # O edge entrega 48 kbps CBR: 6000 bytes por segundo.
        mp3.write_bytes(b"\x00" * int(segundos * 6000))
        if com_sidecar:
            voz.palavras_de(mp3).write_text(
                json.dumps([{"t0": 0.0, "t1": segundos, "texto": "oi"}]),
                encoding="utf-8")
        return mp3

    def test_mp3_sem_limites_de_palavra_nao_e_servido(self):
        mp3 = self._entrada(com_sidecar=False)
        motivo = voz.motivo_do_cache_ruim(mp3, TEXTO, "edge")
        self.assertIn("interrompida", motivo)

    def test_o_wav_do_sapi_nao_precisa_de_limites(self):
        # O SAPI nunca informou limites; exigi-los inutilizaria a reserva.
        wav = self._entrada("a.wav", com_sidecar=False)
        self.assertEqual(voz.motivo_do_cache_ruim(wav, TEXTO, "sapi"), "")

    def test_arquivo_vazio_nao_e_servido(self):
        vazio = self.cache / "v.mp3"
        vazio.write_bytes(b"\x00" * 10)
        self.assertEqual(voz.motivo_do_cache_ruim(vazio, TEXTO, "edge"),
                         "arquivo vazio")

    def test_entrada_ruim_e_apagada_e_re_sintetizada(self):
        """O ponto todo: re-renderizar tem que consertar, não repetir."""
        cfg = voz.config({"motor": "edge"})
        chave = voz._chave("edge", cfg["voz"], cfg["taxa"], cfg["tom"], TEXTO)
        envenenada = self.cache / f"{chave}.mp3"
        envenenada.write_bytes(b"\x00" * 131_040)      # o tamanho real do defeito

        chamou = []

        def _falso_edge(texto, destino, cfg):
            chamou.append(destino)
            raise voz.VozIndisponivel("sem rede no teste")

        original = voz._edge
        voz._edge = _falso_edge
        self.addCleanup(setattr, voz, "_edge", original)
        with self.assertRaises(voz.VozIndisponivel):
            voz.sintetizar(TEXTO, cfg, self.cache)
        self.assertFalse(envenenada.exists(),
                         "a entrada envenenada tinha que ter sido apagada")
        self.assertTrue(chamou, "devia ter tentado sintetizar de novo")


class EscritaAtomicaTests(unittest.TestCase):
    """Nada chega ao nome de cache antes de a síntese inteira terminar.

    Lido do fonte de propósito. O estado que causou o defeito é um processo
    MORTO no meio do `async for` — nenhum `except` roda ali, então não há como
    provocá-lo de dentro de um teste. O que dá para travar é a forma: se o
    stream voltar a escrever direto no arquivo de cache, o defeito volta com
    ele, e este teste é o que avisa.
    """

    def setUp(self):
        self.fonte = Path(voz.__file__).read_text(encoding="utf-8")
        inicio = self.fonte.index("def _edge(")
        self.edge = self.fonte[inicio:self.fonte.index("\ndef ", inicio + 10)]

    def test_o_stream_grava_no_parcial_e_nao_no_destino(self):
        self.assertIn('open(parcial, "wb")', self.edge)
        self.assertNotIn('open(destino, "wb")', self.edge)

    def test_o_destino_so_aparece_no_rename_final(self):
        self.assertIn("parcial.replace(destino)", self.edge)
        # E as palavras entram ANTES do áudio: morrer entre os dois renames
        # tem que deixar um sidecar órfão (cache erra e refaz), nunca um
        # áudio sem alinhamento, que é o que fabricava tempos falsos.
        self.assertLess(self.edge.index("parcial_palavras.replace("),
                        self.edge.index("parcial.replace(destino)"))

    def test_a_plausibilidade_e_conferida_antes_de_publicar_no_cache(self):
        self.assertLess(self.edge.index("implausivel("),
                        self.edge.index("parcial.replace(destino)"))

    def test_o_sapi_tambem_grava_em_parcial(self):
        inicio = self.fonte.index("def _sapi(")
        sapi = self.fonte[inicio:self.fonte.index("\ndef ", inicio + 10)]
        self.assertIn("parcial.replace(destino)", sapi)


class VarreduraDoCacheTests(unittest.TestCase):
    """`main.py conferir` acha o arquivo que ninguém tinha como procurar."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cache = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _mp3(self, nome, segundos, marcas_ate=None):
        mp3 = self.cache / nome
        mp3.write_bytes(b"\x00" * int(segundos * C.BYTES_POR_SEGUNDO))
        if marcas_ate is not None:
            voz.palavras_de(mp3).write_text(
                json.dumps([{"t0": 0.0, "t1": marcas_ate, "texto": "oi"}]),
                encoding="utf-8")
        return mp3

    def test_acha_o_mp3_sem_sidecar(self):
        self._mp3("bom.mp3", 100.0, marcas_ate=99.5)
        orfao = self._mp3("orfao.mp3", 21.84)
        ruins = C.cache_de_voz(self.cache)
        self.assertEqual([r["arquivo"] for r in ruins], [orfao])
        self.assertAlmostEqual(ruins[0]["duracao"], 21.84, places=2)

    def test_acha_o_audio_cortado_com_marcas_alem_do_fim(self):
        self._mp3("cortado.mp3", 21.84, marcas_ate=150.0)
        ruins = C.cache_de_voz(self.cache)
        self.assertEqual(len(ruins), 1)
        self.assertIn("cortado", ruins[0]["motivo"])

    def test_cache_saudavel_nao_acusa_nada(self):
        self._mp3("bom.mp3", 150.0, marcas_ate=149.8)
        self.assertEqual(C.cache_de_voz(self.cache), [])

    def test_consertar_apaga_os_dois_arquivos(self):
        self._mp3("cortado.mp3", 21.84, marcas_ate=150.0)
        ruins = C.cache_de_voz(self.cache)
        self.assertEqual(C.limpar_cache(ruins), 1)
        self.assertEqual(list(self.cache.iterdir()), [])


class PlanoDeEdicaoTests(unittest.TestCase):
    """O plano recusa o áudio que não cobre as cenas, em vez de render mudo."""

    def _roteiro(self, cenas=14):
        return {
            "titulo": "T", "serie": True,
            "partes": [{"n": 1, "titulo": "P1", "cenas": [
                {"n": i, "imagem": "a photo", "tempo": 10,
                 "narracao": f"frase {i}"} for i in range(1, cenas + 1)]}],
        }

    def test_marcos_espremidos_levantam(self):
        # É exatamente o caso da p01: 14 cenas, marcos dentro de 21,8 s.
        marcos = [i * 1.55 for i in range(14)]
        with self.assertRaises(timeline.NarracaoNaoCobre) as ctx:
            timeline.montar(self._roteiro(), marcos=marcos,
                            duracao_audio=21.84, parte=1)
        self.assertIn("21.8", str(ctx.exception))

    def test_narracao_inteira_monta_normalmente(self):
        marcos = [i * 10.5 for i in range(14)]
        plano = timeline.montar(self._roteiro(), marcos=marcos,
                                duracao_audio=148.0, parte=1)
        self.assertGreater(plano["total_duration"], 140)

    def test_sem_marcos_nada_muda(self):
        """Sem leitura contínua não há o que conferir: o caminho antigo segue."""
        plano = timeline.montar(self._roteiro(cenas=6), parte=1)
        self.assertEqual(len([e for e in plano["events"]
                              if e["type"] == "cena" and not e.get("continuacao")]), 6)


class VistoriaTests(unittest.TestCase):
    """A vistoria compara o vídeo com o ROTEIRO, não só consigo mesmo."""

    def test_o_teto_e_o_mesmo_nas_duas_casas(self):
        # O teto é o cheque que pega áudio faltando, e as duas casas julgam a
        # mesma coisa: divergir deixaria uma delas passar o que a outra barra.
        self.assertEqual(qualidade.PALAVRAS_POR_S_MAX, voz.PALAVRAS_POR_S_MAX)

    def test_o_piso_do_motor_e_mais_folgado_que_o_da_vistoria(self):
        """Os pisos divergem de propósito, e a diferença tem consequência.

        No motor, reprovar significa cair no SAPI — a história inteira sairia
        com voz robótica por causa de uma leitura só um pouco mais lenta. Na
        vistoria é só um aviso na tela. Por isso o motor é folgado e a vistoria
        pode ser exigente; trocar os dois de lugar seria o erro.
        """
        self.assertLess(voz.PALAVRAS_POR_S_MIN, qualidade.PALAVRAS_POR_S_MIN)
        # E o piso do motor fica abaixo da entrada mais lenta que existe no
        # cache hoje (1,54), com folga para palavra escrita virar várias faladas.
        self.assertLessEqual(voz.PALAVRAS_POR_S_MIN, 1.2)

    def test_silencio_no_fim_e_erro_e_respiro_nao_e(self):
        self.assertGreater(qualidade.SILENCIO_FINAL_MAXIMO, 0.6,
                           "o respiro final do CTA nao pode virar defeito")
        self.assertLess(qualidade.SILENCIO_FINAL_MAXIMO, 13.9,
                        "os 13,9 s mudos da p01 tinham que reprovar")


if __name__ == "__main__":
    unittest.main()
