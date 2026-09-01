# -*- coding: utf-8 -*-
"""O diario que a Vila le tem que dizer a verdade sobre o que esta rodando.

Tres mentiras medidas em 01/09/2026, todas com o mesmo efeito: a Vila
mostrava um mundo que nao era o mundo.

1. PUBLICAR NAO APARECIA. `publicar/tiktok.py` e `publicar/youtube_web.py`
   nao escreviam nada no diario. Como publicar virou navegador por padrao
   (`youtube.modo()` devolve "navegador"), a fabrica `publicacao` ficava
   OCIOSA durante quase todo upload real -- so o caminho da API, hoje
   secundario, reportava.

2. DOIS CANAIS VIRAVAM UM. `estado_das_fabricas()` guardava so o evento mais
   novo por fabrica, entao builds e historias trabalhando no mesmo provedor
   eram indistinguiveis: o mais recente apagava o outro.

3. NAO HAVIA SINAL DE VIDA. Sem pulso e sem PID, a unica guarda era
   `INICIO_VELHO_S = 2h`: um job legitimo de tres horas lia como ocioso, e um
   processo derrubado deixava um bot trabalhando na tela por duas horas.

Rode de dentro de random_builds/:
    python -m unittest tests.test_diario_verdadeiro_regressions -v
"""
from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from builds import atividade


class DiarioTemporario(unittest.TestCase):
    """Cada teste com o seu proprio jsonl — o diario real fica quieto."""

    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.arquivo = Path(pasta.name) / "atividade.jsonl"
        original = atividade._arquivo
        atividade._arquivo = lambda: self.arquivo
        self.addCleanup(lambda: setattr(atividade, "_arquivo", original))

    def linhas(self) -> list:
        if not self.arquivo.is_file():
            return []
        return [json.loads(l) for l in
                self.arquivo.read_text(encoding="utf-8").splitlines() if l.strip()]


class PublicarApareceTests(unittest.TestCase):
    """Os 7 lugares que abrem navegador para publicar tem que reportar."""

    def _fonte(self, caminho: str) -> str:
        raiz = Path(__file__).resolve().parents[1] / "builds"
        return (raiz / caminho).read_text(encoding="utf-8")

    CHAMADA = 'atividade.fabrica("publicacao"'

    def test_tiktok_registra_no_diario(self):
        self.assertIn(self.CHAMADA, self._fonte("publicar/tiktok.py"))

    def test_youtube_web_registra_no_diario(self):
        self.assertIn(self.CHAMADA, self._fonte("publicar/youtube_web.py"))

    def test_o_canal_vai_junto(self):
        """Sem o canal, nao da para saber de QUEM e o upload."""
        for caminho in ("publicar/tiktok.py", "publicar/youtube_web.py"):
            fonte = self._fonte(caminho)
            i = fonte.index(self.CHAMADA)
            self.assertIn("canal=canal", fonte[i:i + 300], caminho)

    def test_e_dentro_do_publicar_e_nao_do_login(self):
        """Login e sondagem nao sao producao; publicar e."""
        for caminho in ("publicar/tiktok.py", "publicar/youtube_web.py"):
            fonte = self._fonte(caminho)
            i = fonte.index(self.CHAMADA)
            antes = fonte[:i]
            ultima_def = antes.rfind(chr(10) + "def ")
            self.assertIn("def publicar(", antes[ultima_def:ultima_def + 40],
                          caminho)


class CanalSeparaTests(DiarioTemporario):
    """Dois canais no mesmo provedor sao dois trabalhos, nao um."""

    def test_builds_e_historias_no_picasso_aparecem_os_dois(self):
        atividade.registrar("picasso", atividade.TRABALHANDO, "cena 1",
                            canal="historias")
        atividade.registrar("picasso", atividade.TRABALHANDO, "build 42",
                            canal="builds")

        por_canal = atividade.estado_por_canal()
        chaves = {(f, c) for (f, c) in por_canal}
        self.assertIn(("picasso", "historias"), chaves)
        self.assertIn(("picasso", "builds"), chaves)
        self.assertEqual("trabalhando", por_canal[("picasso", "builds")]["status"])
        self.assertEqual("trabalhando",
                         por_canal[("picasso", "historias")]["status"])

    def test_o_resumo_por_fabrica_continua_existindo(self):
        """A visao antiga nao pode sumir: o bot da Vila ainda usa."""
        atividade.registrar("digen", atividade.TRABALHANDO, "x")
        estado = atividade.estado_das_fabricas()
        self.assertEqual("trabalhando", estado["digen"]["status"])

    def test_um_canal_com_erro_nao_apaga_o_outro_trabalhando(self):
        atividade.registrar("picasso", atividade.ERRO, "recusado",
                            canal="historias")
        atividade.registrar("picasso", atividade.TRABALHANDO, "build 42",
                            canal="builds")
        por_canal = atividade.estado_por_canal()
        self.assertEqual("erro", por_canal[("picasso", "historias")]["status"])
        self.assertEqual("trabalhando", por_canal[("picasso", "builds")]["status"])


class SinalDeVidaTests(DiarioTemporario):
    """Sem pulso, "trabalhando" nao quer dizer nada."""

    def test_o_evento_guarda_quem_esta_rodando(self):
        atividade.registrar("estudio", atividade.TRABALHANDO, "render")
        evento = self.linhas()[-1]
        self.assertIn("pid", evento)
        self.assertIsInstance(evento["pid"], int)

    def test_processo_morto_nao_conta_como_trabalhando(self):
        """PID que nao existe mais = processo derrubado, nao trabalho."""
        atividade.registrar("estudio", atividade.TRABALHANDO, "render")
        linhas = self.arquivo.read_text(encoding="utf-8").splitlines()
        evento = json.loads(linhas[-1])
        evento["pid"] = 999_999_999          # nao existe
        linhas[-1] = json.dumps(evento, ensure_ascii=False)
        self.arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")

        estado = atividade.estado_das_fabricas()
        self.assertEqual("ocioso", estado["estudio"]["status"],
                         "processo morto continuou 'trabalhando'")

    def test_processo_vivo_continua_trabalhando_depois_de_duas_horas(self):
        """Um job legitimo e longo lia como ocioso; com PID vivo, nao mais."""
        atividade.registrar("estudio", atividade.TRABALHANDO, "render longo")
        linhas = self.arquivo.read_text(encoding="utf-8").splitlines()
        evento = json.loads(linhas[-1])
        antigo = time.time() - (3 * 3600)
        from datetime import datetime, timezone
        evento["ts"] = datetime.fromtimestamp(
            antigo, timezone.utc).isoformat(timespec="seconds")
        linhas[-1] = json.dumps(evento, ensure_ascii=False)
        self.arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")

        estado = atividade.estado_das_fabricas()
        self.assertEqual("trabalhando", estado["estudio"]["status"],
                         "processo VIVO de 3h foi dado como ocioso")


if __name__ == "__main__":
    unittest.main()
