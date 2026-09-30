# -*- coding: utf-8 -*-
"""A vistoria mede no pixel se a imagem da historia ficou preta.

17/09/2026: o 09003 p1 saiu com as cenas 12 a 14 com a metade de cima preta
(11 de 14 imagens; a aba fechou no meio da geracao). Audio, duracao e ritmo
estavam certos; so o Gemini viu. O teste com video de verdade gera um mp4
minusculo com o ffmpeg e PULA se ele nao estiver instalado.
"""
from __future__ import annotations

import inspect
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from contos.publicar import qualidade as Q

SAIDA_DO_FFMPEG = """\
[Parsed_blackdetect_3 @ 000001] black_start:1 black_end:2.25 black_duration:1.25
frame=   12 fps=0.0 q=-0.0 size=N/A time=00:00:03.00
[Parsed_blackdetect_3 @ 000001] black_start:x black_end:y black_duration:z
[Parsed_blackdetect_3 @ 000001] black_start:5.5 black_end:6.25 black_duration:0.75
"""


class LeituraDoFiltro(unittest.TestCase):

    def test_le_os_intervalos_e_ignora_linha_quebrada(self):
        self.assertEqual([(1.0, 2.25), (5.5, 6.25)],
                         Q._intervalos_pretos(SAIDA_DO_FFMPEG))

    def test_sem_nada_preto(self):
        self.assertEqual([], Q._intervalos_pretos("frame= 10\n"))

    def test_dividido_olha_so_a_metade_de_cima(self):
        visto = {}

        def _rodar(cmd, **_kw):
            visto["filtro"] = cmd[cmd.index("-vf") + 1]
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(Q.subprocess, "run", side_effect=_rodar):
            Q.trechos_pretos(Path("x.mp4"), "dividido")
            self.assertIn("crop=iw:ih/2:0:0", visto["filtro"])
            Q.trechos_pretos(Path("x.mp4"), "vertical")
            self.assertNotIn("crop=", visto["filtro"])
        self.assertIn(f"pic_th={Q.PRETO_AREA}", visto["filtro"])
        self.assertIn(f"d={Q.PRETO_MIN_S}", visto["filtro"])

    def test_ffmpeg_ausente_nao_barra(self):
        with mock.patch.object(Q.subprocess, "run",
                               side_effect=FileNotFoundError("ffmpeg")):
            self.assertIsNone(Q.trechos_pretos(Path("x.mp4"), "vertical"))


class LaudoDoPreto(unittest.TestCase):

    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.mp4 = Path(pasta.name) / "final_celular_p01.mp4"
        self.mp4.write_bytes(b"x" * 10)
        Q._PRETOS_MEDIDOS.clear()
        self.addCleanup(Q._PRETOS_MEDIDOS.clear)

    def test_trecho_preto_vira_erro(self):
        with mock.patch.object(Q, "trechos_pretos",
                               return_value=[(12.0, 14.5)]):
            laudo = Q.erros_de_preto(self.mp4, "dividido")
        self.assertEqual(1, len(laudo["erros"]))
        self.assertIn("metade de cima", laudo["erros"][0])
        self.assertIn("12.0-14.5s", laudo["erros"][0])

    def test_sem_medida_e_aviso_e_nao_erro(self):
        with mock.patch.object(Q, "trechos_pretos", return_value=None):
            laudo = Q.erros_de_preto(self.mp4, "vertical")
        self.assertEqual([], laudo["erros"])
        self.assertEqual(1, len(laudo["avisos"]))

    def test_mede_uma_vez_por_arquivo_e_de_novo_se_ele_mudar(self):
        with mock.patch.object(Q, "trechos_pretos",
                               return_value=[]) as medir:
            Q.erros_de_preto(self.mp4, "dividido")
            Q.erros_de_preto(self.mp4, "dividido")
            self.assertEqual(1, medir.call_count)
            # O reparo re-renderiza NO MESMO CAMINHO.
            self.mp4.write_bytes(b"y" * 20)
            Q.erros_de_preto(self.mp4, "dividido")
            self.assertEqual(2, medir.call_count)

    def test_a_vistoria_da_parte_usa_o_layout_feito(self):
        fonte = inspect.getsource(Q.vistoriar_parte)
        self.assertIn('erros_de_preto(caminho, str(feito.get("layout")',
                      fonte)

    def test_fora_de_outputs_nunca_escreve_o_memo(self):
        with mock.patch.object(Q, "trechos_pretos", return_value=[]), \
                mock.patch.object(Q, "_gravar_memo") as gravar:
            Q.erros_de_preto(self.mp4, "dividido")
        gravar.assert_not_called()


class CenaNoturnaNaoETelaPreta(unittest.TestCase):
    """30/09/2026: a h41 p01 barrada 3x por "preta 85,0-91,8 s". Era a cena
    14, cemiterio a noite, com a propria imagem 85% abaixo do limiar."""

    def setUp(self):
        import json

        from contos.roteiro import roteiro as R
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.outputs = Path(pasta.name)
        patcher = mock.patch.object(R, "OUTPUTS", self.outputs)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cenas = self.outputs / "historia_teste" / "cenas"
        self.cenas.mkdir(parents=True)
        self.json = json

    def _imagem(self, nome: str, escura: float) -> Path:
        """Imagem com `escura` da area em luma 8 e o resto em 200."""
        from PIL import Image
        im = Image.new("L", (100, 100), 200)
        linhas = int(round(100 * escura))
        if linhas:
            im.paste(8, (0, 0, 100, linhas))
        destino = self.cenas / nome
        im.convert("RGB").save(destino)
        return destino

    def _plano(self, eventos, total=20.0):
        pasta = self.outputs / "historia_teste" / "partes" / "p01"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "edit_plan.json").write_text(self.json.dumps(
            {"total_duration": total, "events": eventos}), encoding="utf-8")

    @staticmethod
    def _cena(n, inicio, duracao, arquivo):
        return {"type": "cena", "n": n, "start": inicio,
                "duration": duracao, "arquivo": str(arquivo)}

    def test_fracao_escura_da_imagem(self):
        self.assertAlmostEqual(0.85, Q.fracao_escura(
            self._imagem("a.png", 0.85)), places=2)
        self.assertIsNone(Q.fracao_escura(self.cenas / "nao_existe.png"))

    def test_imagem_noturna_explica_o_trecho(self):
        noite = self._imagem("p01_cena_02.png", 0.85)
        dia = self._imagem("p01_cena_01.png", 0.30)
        self._plano([self._cena(1, 0.0, 10.0, dia),
                     self._cena(2, 10.0, 5.0, noite),
                     self._cena(2, 15.0, 5.0, noite)])
        explicados = Q.trechos_de_imagem_escura("historia_teste", 1,
                                                [(10.1, 19.8)], 20.0)
        self.assertEqual([(10.1, 19.8)], list(explicados))
        self.assertIn("cena 2", explicados[(10.1, 19.8)])

    def test_imagem_clara_que_saiu_preta_continua_erro(self):
        dia = self._imagem("p01_cena_01.png", 0.30)
        self._plano([self._cena(1, 0.0, 20.0, dia)])
        self.assertEqual({}, Q.trechos_de_imagem_escura(
            "historia_teste", 1, [(3.0, 6.0)], 20.0))

    def test_cena_sem_arquivo_o_cartao_continua_erro(self):
        self._plano([self._cena(1, 0.0, 20.0,
                                self.cenas / "p01_cena_01.png")])
        self.assertEqual({}, Q.trechos_de_imagem_escura(
            "historia_teste", 1, [(3.0, 6.0)], 20.0))

    def test_trecho_que_pega_cena_clara_nao_e_explicado(self):
        noite = self._imagem("p01_cena_02.png", 0.85)
        dia = self._imagem("p01_cena_01.png", 0.30)
        self._plano([self._cena(1, 0.0, 10.0, dia),
                     self._cena(2, 10.0, 10.0, noite)])
        self.assertEqual({}, Q.trechos_de_imagem_escura(
            "historia_teste", 1, [(8.0, 14.0)], 20.0))

    def test_plano_de_outro_render_nao_explica(self):
        noite = self._imagem("p01_cena_01.png", 0.85)
        self._plano([self._cena(1, 0.0, 20.0, noite)], total=20.0)
        self.assertEqual({}, Q.trechos_de_imagem_escura(
            "historia_teste", 1, [(3.0, 6.0)], 35.0))

    def test_sem_plano_nao_explica(self):
        self.assertEqual({}, Q.trechos_de_imagem_escura(
            "historia_teste", 1, [(3.0, 6.0)], 20.0))

    def test_no_laudo_o_explicado_vira_aviso_e_o_resto_erro(self):
        mp4 = self.outputs / "x.mp4"
        mp4.write_bytes(b"x" * 10)
        Q._PRETOS_MEDIDOS.clear()
        self.addCleanup(Q._PRETOS_MEDIDOS.clear)
        with mock.patch.object(Q, "trechos_pretos",
                               return_value=[(2.0, 3.0), (85.0, 91.75)]):
            laudo = Q.erros_de_preto(
                mp4, "dividido",
                explicar=lambda t: {(85.0, 91.75): "cena 14 (85% escura)"})
        self.assertEqual(1, len(laudo["erros"]))
        self.assertIn("2.0-3.0s", laudo["erros"][0])
        self.assertNotIn("85.0", laudo["erros"][0])
        self.assertTrue(any("cena 14" in a for a in laudo["avisos"]))
        # o memo guarda o que foi MEDIDO, nunca a explicacao
        self.assertEqual([(2.0, 3.0), (85.0, 91.75)], laudo["trechos"])

    def test_explicacao_que_quebra_mantem_o_erro(self):
        mp4 = self.outputs / "y.mp4"
        mp4.write_bytes(b"y" * 10)
        Q._PRETOS_MEDIDOS.clear()
        self.addCleanup(Q._PRETOS_MEDIDOS.clear)

        def _quebra(_t):
            raise RuntimeError("plano ilegivel")

        with mock.patch.object(Q, "trechos_pretos",
                               return_value=[(2.0, 3.0)]):
            laudo = Q.erros_de_preto(mp4, "dividido", explicar=_quebra)
        self.assertEqual(1, len(laudo["erros"]))

    def test_a_vistoria_da_parte_pede_a_explicacao(self):
        fonte = inspect.getsource(Q.vistoriar_parte)
        self.assertIn("trechos_de_imagem_escura(", fonte)


class MemoEmDisco(unittest.TestCase):
    """Revisao de 17/09/2026: cada rodada da agenda e um processo novo e
    media a fila inteira de novo (3-5 min por rodada)."""

    def setUp(self):
        from contos.pipeline import controller
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.outputs = Path(pasta.name)
        patcher = mock.patch.object(controller, "OUTPUTS", self.outputs)
        patcher.start()
        self.addCleanup(patcher.stop)
        historia = self.outputs / "historia_teste"
        historia.mkdir()
        self.mp4 = historia / "final_celular_p01.mp4"
        self.mp4.write_bytes(b"x" * 10)
        Q._PRETOS_MEDIDOS.clear()
        self.addCleanup(Q._PRETOS_MEDIDOS.clear)

    def _novo_processo(self):
        Q._PRETOS_MEDIDOS.clear()

    def test_outro_processo_le_do_disco_e_nao_mede(self):
        with mock.patch.object(Q, "trechos_pretos",
                               return_value=[(3.0, 4.5)]) as medir:
            Q.erros_de_preto(self.mp4, "dividido")
            self._novo_processo()
            laudo = Q.erros_de_preto(self.mp4, "dividido")
        self.assertEqual(1, medir.call_count)
        self.assertEqual([(3.0, 4.5)], laudo["trechos"])
        self.assertEqual(1, len(laudo["erros"]))
        self.assertTrue((self.outputs / Q.MEMO_PRETOS_NOME).is_file())

    def test_video_refeito_e_medido_de_novo(self):
        with mock.patch.object(Q, "trechos_pretos", return_value=[]) as medir:
            Q.erros_de_preto(self.mp4, "dividido")
            self.mp4.write_bytes(b"y" * 20)
            self._novo_processo()
            Q.erros_de_preto(self.mp4, "dividido")
        self.assertEqual(2, medir.call_count)

    def test_sem_medida_nao_vai_ao_disco(self):
        with mock.patch.object(Q, "trechos_pretos",
                               return_value=None) as medir:
            Q.erros_de_preto(self.mp4, "vertical")
            self._novo_processo()
            Q.erros_de_preto(self.mp4, "vertical")
        self.assertEqual(2, medir.call_count)

    def test_memo_quebrado_so_faz_medir(self):
        (self.outputs / Q.MEMO_PRETOS_NOME).write_text("{", encoding="utf-8")
        with mock.patch.object(Q, "trechos_pretos", return_value=[]):
            self.assertEqual([], Q.erros_de_preto(self.mp4,
                                                  "dividido")["erros"])

    def test_arquivo_apagado_sai_do_memo(self):
        import json
        outro = self.mp4.with_name("final_celular_p02.mp4")
        outro.write_bytes(b"z" * 5)
        with mock.patch.object(Q, "trechos_pretos", return_value=[]):
            Q.erros_de_preto(outro, "dividido")
            outro.unlink()
            Q.erros_de_preto(self.mp4, "dividido")
        memo = json.loads((self.outputs / Q.MEMO_PRETOS_NOME)
                          .read_text(encoding="utf-8"))
        self.assertEqual(1, len(memo))
        self.assertIn("final_celular_p01.mp4", next(iter(memo)))


class AjustesDaRevisao(unittest.TestCase):
    """Revisao independente da feat/deepseek-roteiro (17/09/2026)."""

    def test_conserto_de_cena_vai_para_quem_viu_o_video(self):
        from contos.pipeline import conserto_de_cena
        fonte = inspect.getsource(conserto_de_cena)
        self.assertIn("papeis.provedores(papeis.VIDEO)", fonte)
        self.assertNotIn("papeis.provedores(papeis.QUALIDADE)", fonte)

    def test_fabricas_de_llm_nao_disparam_apuracao(self):
        # Pelo fonte: a suite de historias roda sem a raiz no sys.path, e
        # `import remoto` so passava com o PYTHONPATH da worktree.
        import ast
        raiz = Path(Q.__file__).resolve().parents[3]
        arvore = ast.parse((raiz / "remoto" / "apurador.py").read_text(
            encoding="utf-8"))
        valor = next(no.value for no in arvore.body
                     if isinstance(no, ast.Assign)
                     and getattr(no.targets[0], "id", "")
                     == "FABRICAS_SEM_APURACAO")
        nomes = ast.literal_eval(valor.args[0])
        for fabrica in ("deepseek", "chatgpt", "gemini"):
            self.assertIn(fabrica, nomes)

    def test_painel_manda_o_login_do_deepseek_para_o_llm(self):
        raiz = Path(Q.__file__).resolve().parents[3]
        fonte = (raiz / "painel" / "paginas" / "contas.py").read_text(
            encoding="utf-8")
        self.assertIn('elif servico in ("chatgpt", "gemini", "deepseek"):',
                      fonte)


@unittest.skipUnless(shutil.which("ffmpeg"),
                     "ffmpeg ausente: o video sintetico nao pode ser gerado")
class VideoSintetico(unittest.TestCase):
    """90x160, 3 s: cinza, com uma faixa na cor do cartao de 1 a 2,2 s."""

    def _gerar(self, regiao: str) -> Path:
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        destino = Path(pasta.name) / "sintetico.mp4"
        y, h = {"cima": ("0", "ih/2"), "baixo": ("ih/2", "ih/2"),
                "tudo": ("0", "ih")}[regiao]
        caixa = (f"drawbox=x=0:y={y}:w=iw:h={h}:color=0x141019:t=fill:"
                 "enable='between(t,1,2.2)'")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "color=c=0x808080:s=90x160:r=10:d=3", "-vf", caixa,
             "-pix_fmt", "yuv420p", str(destino)],
            check=True, capture_output=True, timeout=60,
            creationflags=Q.NO_WINDOW)
        return destino

    def test_metade_de_cima_preta_no_dividido(self):
        trechos = Q.trechos_pretos(self._gerar("cima"), "dividido")
        self.assertEqual(1, len(trechos))
        inicio, fim = trechos[0]
        self.assertAlmostEqual(1.0, inicio, delta=0.3)
        self.assertAlmostEqual(2.2, fim, delta=0.3)

    def test_metade_de_baixo_e_o_fundo_e_nao_conta_no_dividido(self):
        self.assertEqual([], Q.trechos_pretos(self._gerar("baixo"),
                                              "dividido"))

    def test_no_vertical_meia_tela_escura_nao_basta(self):
        # Cena noturna com laterais escuras chega a ~62% da area.
        self.assertEqual([], Q.trechos_pretos(self._gerar("cima"),
                                              "vertical"))

    def test_o_cartao_de_cena_sem_imagem_do_renderer_e_pego(self):
        """O defeito de verdade: o painel de cima vira o cartao tipografico."""
        import json

        from contos.video.renderer import VideoRenderer
        raiz = Path(Q.__file__).resolve().parents[2]
        cfg = json.loads((raiz / "config" / "render.json")
                         .read_text(encoding="utf-8-sig"))
        r = VideoRenderer(cfg, "celular", formato={"layout": "dividido",
                                                   "velocidade": 1.5})
        texto = ("Ela abriu a fatura na minha frente e perguntou quem tinha "
                 "gasto seis mil reais no cartao, e eu fiquei calado.")
        quadro = list(r._cena_sem_imagem({"narracao": texto, "start": 0.0},
                                         3))[-1]
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        png = Path(pasta.name) / "cartao.png"
        quadro.resize((quadro.width // 6, quadro.height // 6)).save(png)
        destino = Path(pasta.name) / "cartao.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-r", "10", "-t",
             "1.5", "-i", str(png), "-vf",
             "pad=iw:ih*2:0:0:color=0x808080,scale=trunc(iw/2)*2:"
             "trunc(ih/2)*2", "-pix_fmt", "yuv420p", str(destino)],
            check=True, capture_output=True, timeout=60,
            creationflags=Q.NO_WINDOW)
        self.assertEqual(1, len(Q.trechos_pretos(destino, "dividido")))

    def test_no_vertical_a_tela_inteira_preta_conta(self):
        self.assertEqual(1, len(Q.trechos_pretos(self._gerar("tudo"),
                                                 "vertical")))


if __name__ == "__main__":
    unittest.main()
