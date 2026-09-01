# -*- coding: utf-8 -*-
"""Contratos das CONTAS e da publicacao em um clique.

O que este arquivo trava:

1. CONTAS. Cada servico tem varias contas e uma ATIVA por canal. A conta
   `principal` continua nos caminhos ANTIGOS (perfil de Chrome, arquivo de
   credencial) — se isso quebrar, todo login ja feito se perde. Conta nova
   ganha caminho proprio: publicar a historia no canal de builds e
   irreversivel.
2. VISTORIA. Video mudo, curto demais ou sem imagem nenhuma NAO sobe. Um
   roteiro perfeito nao garante mp4 bom, e nada disso levanta excecao no
   render: o arquivo existe do mesmo jeito.
3. AGENDAMENTO. As partes saem espacadas e na ordem; a primeira nunca no
   passado (o YouTube recusa). Soltar oito partes no mesmo minuto mata a
   serie.
4. NAO PUBLICAR DUAS VEZES. O registro de publicados e consultado antes de
   subir.

Rode de dentro de historias/:
    python -m unittest tests.test_contas_publicacao_regressions -v
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from contos import compartilhado                                   # noqa: E402
from contos.publicar import qualidade, serie                       # noqa: E402

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TEM_FFMPEG = bool(shutil.which("ffmpeg"))


def _mp4(destino: Path, *, segundos: float = 12.0, com_audio: bool = True,
         volume: float = 0.5) -> Path:
    """Um mp4 de verdade, pequeno, para a vistoria ter o que medir."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    entradas = ["-f", "lavfi", "-i",
                f"testsrc=duration={segundos}:size=180x320:rate=12"]
    if com_audio:
        entradas += ["-f", "lavfi", "-i",
                     f"sine=frequency=300:duration={segundos}"]
    saida = ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    if com_audio:
        saida += ["-af", f"volume={volume}", "-c:a", "aac", "-shortest"]
    else:
        saida += ["-an"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *entradas, *saida,
                    str(destino)], check=True, creationflags=NO_WINDOW)
    return destino


# --------------------------------------------------------------- 1. contas
class ContasTests(unittest.TestCase):
    def setUp(self):
        self.contas = compartilhado.modulo("contas")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._registro = self.contas.ARQUIVO
        self._runtime = self.contas.runtime_dir
        self.contas.ARQUIVO = Path(self._tmp.name) / "contas.json"
        self.contas.runtime_dir = lambda: Path(self._tmp.name)

        def restaurar():
            self.contas.ARQUIVO = self._registro
            self.contas.runtime_dir = self._runtime
        self.addCleanup(restaurar)

    def test_toda_conta_comeca_em_principal(self):
        for servico in self.contas.SERVICOS:
            self.assertEqual([self.contas.PADRAO], self.contas.contas(servico))
            self.assertEqual(self.contas.PADRAO,
                             self.contas.ativa(servico, "historias"))

    def test_conta_por_canal_e_independente(self):
        self.contas.adicionar("youtube", "Canal de Histórias!")
        self.contas.escolher("youtube", "historias", "canal_de_historias")
        self.assertEqual("canal_de_historias",
                         self.contas.ativa("youtube", "historias"))
        # o outro canal nao muda: e o ponto inteiro da separacao
        self.assertEqual(self.contas.PADRAO, self.contas.ativa("youtube", "builds"))

    def test_nome_de_conta_vira_nome_de_pasta(self):
        self.assertEqual("canal_2_historias",
                         self.contas.adicionar("tiktok", "Canal 2 — Histórias"))

    def test_credencial_do_youtube_por_conta(self):
        principal = self.contas.credencial_youtube("builds")
        self.assertEqual("youtube_credentials.json", principal.name)
        self.contas.adicionar("youtube", "historias")
        self.contas.escolher("youtube", "historias", "historias")
        outra = self.contas.credencial_youtube("historias")
        self.assertEqual("youtube_credentials_historias.json", outra.name)
        self.assertNotEqual(principal, outra)

    def test_perfil_da_principal_e_o_caminho_antigo(self):
        """Se isto quebrar, os logins de Digen/Picasso/TikTok se perdem."""
        for servico in ("tiktok", "picasso", "digen"):
            legado = self.contas.SERVICOS[servico].get("legado")
            self.assertIsNotNone(legado, servico)
            self.assertEqual(Path(legado),
                             self.contas.perfil(servico, "builds"))

    def test_conta_nova_ganha_perfil_proprio(self):
        self.contas.adicionar("tiktok", "historias")
        self.contas.escolher("tiktok", "historias", "historias")
        novo = self.contas.perfil("tiktok", "historias")
        self.assertNotEqual(Path(self.contas.SERVICOS["tiktok"]["legado"]), novo)
        self.assertIn("tiktok__historias", str(novo))
        self.assertTrue(novo.is_dir())

    def test_esquecer_conta_devolve_o_canal_para_principal(self):
        self.contas.adicionar("gemini", "secundaria")
        self.contas.escolher("gemini", "historias", "secundaria")
        self.assertTrue(self.contas.remover("gemini", "secundaria"))
        self.assertEqual(self.contas.PADRAO,
                         self.contas.ativa("gemini", "historias"))
        self.assertFalse(self.contas.remover("gemini", self.contas.PADRAO))

    def test_conta_apagada_do_registro_nao_deixa_canal_orfao(self):
        self.contas.escolher("youtube", "historias", "some_dai")
        dados = self.contas.estado()
        dados["servicos"]["youtube"]["contas"].remove("some_dai")
        self.contas._gravar(dados)
        self.assertEqual(self.contas.PADRAO,
                         self.contas.ativa("youtube", "historias"))

    def test_resumo_tem_uma_linha_por_servico_e_canal(self):
        linhas = self.contas.resumo()
        self.assertEqual(len(self.contas.SERVICOS) * 2, len(linhas))
        chaves = {(l["servico"], l["canal"]) for l in linhas}
        self.assertIn(("youtube", "historias"), chaves)
        self.assertIn(("chatgpt", "builds"), chaves)
        for linha in linhas:
            self.assertIn("onde", linha)
            self.assertIn(linha["conta"], linha["contas"])


# ------------------------------------------------------------ 2. vistoria
@unittest.skipUnless(TEM_FFMPEG, "ffmpeg ausente")
class VistoriaTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)

    def test_video_bom_passa(self):
        laudo = qualidade.vistoriar_arquivo(_mp4(self.pasta / "ok.mp4"))
        self.assertEqual([], laudo["erros"])
        self.assertTrue(laudo["audio"])
        self.assertGreater(laudo["duracao"], 10)

    def test_video_mudo_nao_passa(self):
        laudo = qualidade.vistoriar_arquivo(
            _mp4(self.pasta / "mudo.mp4", com_audio=False))
        self.assertTrue(any("sem faixa de audio" in e for e in laudo["erros"]))

    def test_video_curto_nao_passa(self):
        laudo = qualidade.vistoriar_arquivo(
            _mp4(self.pasta / "curto.mp4", segundos=3))
        self.assertTrue(any("curto demais" in e for e in laudo["erros"]))

    def test_audio_quase_inaudivel_nao_passa(self):
        laudo = qualidade.vistoriar_arquivo(
            _mp4(self.pasta / "baixo.mp4", volume=0.0005))
        self.assertTrue(any("mudo" in e for e in laudo["erros"]), laudo)

    def test_arquivo_que_nao_existe(self):
        laudo = qualidade.vistoriar_arquivo(self.pasta / "nada.mp4")
        self.assertFalse(laudo["existe"])
        self.assertTrue(laudo["erros"])


# ---------------------------------------------------------- 3. agendamento
class AgendamentoTests(unittest.TestCase):
    def test_uma_parte_por_dia_na_ordem(self):
        marcados = serie.horarios(4, intervalo_h=24)
        self.assertEqual(4, len(marcados))
        tempos = [datetime.fromisoformat(m.replace("Z", "+00:00"))
                  for m in marcados]
        self.assertEqual(tempos, sorted(tempos))
        for antes, depois in zip(tempos, tempos[1:]):
            self.assertAlmostEqual(24.0,
                                   (depois - antes).total_seconds() / 3600, places=3)

    def test_a_primeira_nunca_fica_no_passado(self):
        passado = datetime.now(timezone.utc) - timedelta(days=2)
        primeiro = datetime.fromisoformat(
            serie.horarios(2, comecar_em=passado)[0].replace("Z", "+00:00"))
        self.assertGreater(primeiro, datetime.now(timezone.utc))

    def test_horario_escolhido_e_respeitado(self):
        futuro = datetime.now(timezone.utc) + timedelta(days=3)
        marcados = serie.horarios(3, comecar_em=futuro, intervalo_h=12)
        primeiro = datetime.fromisoformat(marcados[0].replace("Z", "+00:00"))
        # ate 1 s de diferenca: o ISO e gravado com precisao de segundo
        self.assertLess(abs((primeiro - futuro).total_seconds()), 1.5)
        self.assertTrue(marcados[0].endswith("Z"))


# -------------------------------------------------- 4. nao publicar 2 vezes
class RegistroDePublicadosTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._antes = serie.REGISTRO
        serie.REGISTRO = Path(self._tmp.name) / "publicados.jsonl"
        self.addCleanup(lambda: setattr(serie, "REGISTRO", self._antes))

    def test_registra_e_reconhece(self):
        from contos.publicar.catalogo import Video
        video = Video(id="historia_00009:celular:p02", perfil="celular",
                      caminho=Path("x.mp4"), titulo="T", descricao="",
                      parte=2, partes=5, fonte_id="historia_00009")
        self.assertIsNone(serie.ja_publicado(video.id))
        serie.registrar(video, "https://youtu.be/abc", "youtube",
                        "2026-09-01T18:00:00Z")
        achado = serie.ja_publicado(video.id)
        self.assertEqual("https://youtu.be/abc", achado["url"])
        self.assertEqual(2, achado["parte"])
        self.assertEqual("2026-09-01T18:00:00Z", achado["agendado_para"])
        # linha sem url nao conta como publicado
        serie.REGISTRO.write_text(
            json.dumps({"video_id": video.id, "url": ""}) + "\n", encoding="utf-8")
        self.assertIsNone(serie.ja_publicado(video.id))


if __name__ == "__main__":
    unittest.main()
