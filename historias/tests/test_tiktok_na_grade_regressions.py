# -*- coding: utf-8 -*-
"""O TikTok tambem e destino: 49 publicacoes, todas YouTube, zero TikTok.

Em 10/09/2026 ele avisou: "ambos os tiktoks estao sem videos novos". Estava
certo — o `ferramentas/postar.py`, que eu escrevi em 08/09 e que virou a grade
de oito horarios, nao tinha UMA LINHA de TikTok. O contador nao deixa duvida:

    publicacoes por plataforma:  youtube 49   tiktok 0

E a maquina toda ja existia: `tiktok.publicar(video, postar=, canal=)`,
`catalogo.publicar_tiktok` para as historias, duas contas configuradas e
separadas (`builds -> principal`, `historias -> historinhas`). So ninguem
chamava.

DOIS DEFEITOS que o conserto teve que resolver junto, e nenhum dos dois e
obvio:

1. A GUARDA ERA CEGA AO DESTINO. `publicou_neste_horario(canal)` olhava so a
   hora: a postagem do YouTube passaria a bloquear a do TikTok no mesmo
   horario, e o segundo destino nunca sairia.
2. HISTORIA NO TIKTOK NAO FICAVA REGISTRADA. `tiktok.publicar` grava por
   `metricas.registrar_publicado(canal=...)`, e essa funcao DESCARTA tudo que
   nao e do canal `builds` (a guarda existe para o upload de historia nao
   sujar o ledger de builds). Sem registro, a guarda nunca veria a postagem
   e ela poderia repetir a cada disparo.
"""
from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
POSTAR = RAIZ.parent / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_tiktok", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class GuardaPorDestinoTests(unittest.TestCase):
    def setUp(self):
        self.postar = _postar()
        self.quando = datetime(2026, 9, 10, 10, 30)

    def _ledger(self, linhas):
        self.postar._publicados_do_canal = lambda _c: list(linhas)

    def test_youtube_postado_NAO_bloqueia_o_tiktok(self):
        """Era isto que faria o segundo destino nunca sair."""
        self._ledger([{"quando": "2026-09-10T10:10:09", "video_id": "x",
                       "plataforma": "youtube"}])
        self.assertIsNotNone(self.postar.publicou_neste_horario(
            "historias", "youtube", self.quando))
        self.assertIsNone(self.postar.publicou_neste_horario(
            "historias", "tiktok", self.quando))

    def test_tiktok_postado_nao_bloqueia_o_youtube(self):
        self._ledger([{"quando": "2026-09-10T10:10:09", "video_id": "x",
                       "plataforma": "tiktok"}])
        self.assertIsNone(self.postar.publicou_neste_horario(
            "historias", "youtube", self.quando))

    def test_cada_destino_ainda_nao_repete_em_si(self):
        self._ledger([{"quando": "2026-09-10T10:10:09", "video_id": "x",
                       "plataforma": "tiktok"}])
        self.assertIsNotNone(self.postar.publicou_neste_horario(
            "historias", "tiktok", self.quando))

    def test_linha_ANTIGA_sem_plataforma_conta_como_youtube(self):
        """Era o unico destino que existia quando ela foi gravada."""
        self._ledger([{"quando": "2026-09-10T10:10:09", "video_id": "x"}])
        self.assertIsNotNone(self.postar.publicou_neste_horario(
            "historias", "youtube", self.quando))
        self.assertIsNone(self.postar.publicou_neste_horario(
            "historias", "tiktok", self.quando))


class OsDoisDestinosTests(unittest.TestCase):
    def _corpo(self, nome: str) -> str:
        fonte = POSTAR.read_text(encoding="utf-8")
        inicio = fonte.index(f"def {nome}(")
        fim = fonte.find("\ndef ", inicio + 10)
        return fonte[inicio:fim if fim > 0 else len(fonte)]

    def test_os_dois_canais_vao_para_o_tiktok(self):
        self.assertIn("_tiktok_das_historias(", self._corpo("postar_historia"))
        self.assertIn("_tiktok_dos_builds(", self._corpo("postar_build"))

    def test_o_youtube_ja_postado_leva_o_MESMO_video_ao_tiktok(self):
        """Os dois canais tem que mostrar a mesma coisa — e assim o TikTok
        recupera o atraso sozinho, sem furar a fila."""
        for nome, buscador in (("postar_historia", "_video_por_id("),
                               ("postar_build", "_build_por_id(")):
            corpo = self._corpo(nome)
            self.assertIn("if ja_yt:", corpo, nome)
            self.assertIn(buscador, corpo, nome)
            self.assertIn("so_tiktok", corpo, nome)

    def test_o_tiktok_que_falha_NAO_derruba_o_youtube(self):
        """O YouTube ja subiu: deixar o TikTok derrubar faria parecer falha."""
        for nome in ("_tiktok_das_historias", "_tiktok_dos_builds"):
            corpo = self._corpo(nome)
            self.assertIn("except Exception", corpo, nome)
            self.assertIn("NAO subiu", corpo, nome)

    def test_a_grade_automatica_manda_postar_de_verdade(self):
        """`postar_automatico: false` e o certo para o BOTAO do painel, onde a
        ultima palavra e dele. A grade nao tem quem clique."""
        self.assertIn("postar=True", self._corpo("_tiktok_dos_builds"))
        self.assertIn("postar=True", self._corpo("_tiktok_das_historias"))

    def test_historia_no_tiktok_e_registrada_NO_LEDGER_DAS_HISTORIAS(self):
        """`registrar_publicado` descarta o que nao e do canal `builds`, entao
        sem isto a postagem sumia e a guarda nunca a via."""
        corpo = self._corpo("_tiktok_das_historias")
        self.assertIn('serie.registrar(alvo, estado, "tiktok"', corpo)
        self.assertIn("confirmado(estado)", corpo)

    def test_build_no_tiktok_NAO_e_registrado_duas_vezes(self):
        """La dentro `tiktok.publicar` ja grava para o canal `builds`.

        Olha SO O CODIGO: a docstring da funcao cita `registrar_publicado`
        justamente para explicar por que ela nao o chama, e cobrar o texto
        faria a explicacao da regra violar a regra.
        """
        corpo = self._corpo("_tiktok_dos_builds")
        depois_do_doc = corpo[corpo.index('"""', corpo.index('"""') + 3):]
        codigo = "\n".join(l for l in depois_do_doc.splitlines()
                           if not l.lstrip().startswith("#"))
        self.assertNotIn("registrar", codigo)

    def test_o_relatorio_mostra_o_tiktok_mesmo_quando_falha(self):
        """Destino que some do relatorio e destino que fica 49 posts vazio."""
        fonte = POSTAR.read_text(encoding="utf-8")
        self.assertIn("NAO SUBIU", fonte)
        self.assertIn("tiktok:", fonte)



class LimiteDiarioTests(unittest.TestCase):
    """A cota do YouTube tem nome proprio, sai cedo, e avisa no Telegram.

    Em 10/09/2026 o Adrian achou a frase na tela: "O limite diário de envios
    foi alcançado". Ate entao ela chegava disfarçada — o Studio mostra o aviso
    e o formulario simplesmente nao completa, entao a falha vinha como
    `TimeoutError` no botao "feito para criancas", que e o botao ERRADO.
    Foram dois videos e um minuto de espera cada para descobrir uma coisa que
    estava escrita na tela desde o primeiro segundo.

    Pedido dele junto: "quando isso ocorrer no youtube me avise que resolvo
    remotamente com o anydesk, pode me avisar por telegram mesmo". E o tipo de
    coisa que so uma pessoa resolve: nao ha retry, nao ha conserto de codigo.

    E os DOIS CANAIS TEM COTAS SEPARADAS. Eu testei no builds, ele passou, e
    eu conclui que a cota tinha liberado — errado: `neural_fights` e
    `historinhas` sao canais diferentes na mesma conta Google, e o limite do
    YouTube e por CANAL. O teste do canal errado nao prova nada sobre o outro.
    """

    def _postar(self):
        return _postar()

    def test_a_cota_tem_classe_propria(self):
        from builds.publicar.youtube_web import (LimiteDiarioDoYouTube,
                                                 YouTubeWebFalhou)
        self.assertTrue(issubclass(LimiteDiarioDoYouTube, YouTubeWebFalhou))

    def test_reconhece_pela_classe_e_pelo_texto(self):
        from builds.publicar.youtube_web import LimiteDiarioDoYouTube
        m = self._postar()
        self.assertTrue(m._e_limite_diario(LimiteDiarioDoYouTube("x")))
        self.assertTrue(m._e_limite_diario(
            RuntimeError("O limite diário de envios foi alcançado")))
        self.assertTrue(m._e_limite_diario(
            RuntimeError("you have reached the daily upload limit")))

    def test_NAO_confunde_com_outra_falha(self):
        m = self._postar()
        self.assertFalse(m._e_limite_diario(RuntimeError("Timeout 30000ms")))
        self.assertFalse(m._e_limite_diario(RuntimeError("net::ERR_FAILED")))

    def test_a_cota_e_perguntada_LOGO_DEPOIS_do_envio(self):
        """Detectar no fim custava cinco sintomas confusos e um rascunho."""
        from pathlib import Path
        from builds.publicar import youtube_web
        fonte = Path(youtube_web.__file__).read_text(encoding="utf-8")
        trecho = fonte[fonte.index("entrada.set_input_files"):]
        self.assertLess(trecho.index("_bateu_o_limite(page)"),
                        trecho.index("CAMPO_TITULO"))

    def test_o_escoamento_PARA_na_cota_em_vez_de_insistir(self):
        fonte = POSTAR.read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def escoar_historias("):]
        corpo = corpo[:corpo.index("\ndef ")]
        self.assertIn("_e_limite_diario(exc)", corpo)
        alvo = corpo[corpo.index("_e_limite_diario(exc)"):]
        self.assertIn("break", alvo[:600])
        self.assertIn("avisar_limite_diario(", alvo[:600])

    def test_o_caminho_NORMAL_tambem_avisa(self):
        """Quem roda sozinho nos oito horarios e ele, nao o escoamento."""
        fonte = POSTAR.read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def main("):]
        self.assertIn("_e_limite_diario(exc)", corpo)
        self.assertIn("avisar_limite_diario(", corpo)
class AvisoDoTelegramTests(unittest.TestCase):
    """O aviso diz QUANDO, ONDE e EM QUAIS plataformas.

    Pedido dele em 10/09/2026: "discrimine bem no telegram quando foi, em
    quais plataformas e outras infos quando o video for postado, hj so diz
    que foi postado no youtube". Estava certo em tudo:

      - o TikTok nao era mencionado, mesmo depois de entrar na grade no
        mesmo dia;
      - o "link" era o `url` CRU, que quase sempre e a frase de estado
        repetida ("publicado no YouTube | publicado no YouTube") porque o
        Studio nem sempre devolve link e uma parte longa vira dois Shorts;
      - nao dizia a hora, a parte, a visibilidade nem para qual CONTA foi —
        e o nome da conta e o destino: "para que canal isso foi" era pergunta
        que so se respondia abrindo o navegador.
    """

    def _avisar(self, resultados):
        import subprocess
        m = _postar()
        enviado = []
        original = subprocess.run
        subprocess.run = (lambda *a, **k: enviado.append(a[0][-1])
                          or type("R", (), {"returncode": 0})())
        try:
            m.avisar(resultados)
        finally:
            subprocess.run = original
        return enviado[0] if enviado else ""

    def _historia(self, **extra):
        base = {"canal": "historias", "feito": True,
                "alvo": "historia_00007:celular:p02",
                "titulo": "Proibido de entrar", "parte": 2, "partes": 6,
                "url": "publicado no YouTube | publicado no YouTube",
                "visibilidade": "public", "tiktok": "publicado no TikTok"}
        base.update(extra)
        return base

    def test_diz_QUANDO(self):
        from datetime import datetime
        texto = self._avisar([self._historia()])
        self.assertIn(datetime.now().strftime("%d/%m"), texto)
        self.assertIn(datetime.now().strftime("%H:"), texto)

    def test_diz_AS_DUAS_PLATAFORMAS(self):
        texto = self._avisar([self._historia()])
        self.assertIn("YouTube", texto)
        self.assertIn("TikTok", texto)

    def test_o_tiktok_que_NAO_subiu_aparece_mesmo_assim(self):
        """Destino que some do aviso e destino que fica vazio sem ninguem ver."""
        texto = self._avisar([self._historia(tiktok="")])
        self.assertIn("TikTok", texto)
        self.assertIn("não subiu", texto)

    def test_nao_despeja_a_frase_de_estado_repetida(self):
        texto = self._avisar([self._historia()])
        self.assertNotIn("publicado no YouTube | publicado no YouTube", texto)
        self.assertIn("2 pedaços", texto)

    def test_link_de_verdade_aparece_inteiro(self):
        texto = self._avisar([self._historia(url="https://youtu.be/abc123")])
        self.assertIn("https://youtu.be/abc123", texto)

    def test_diz_a_parte_e_a_visibilidade(self):
        texto = self._avisar([self._historia()])
        self.assertIn("parte 2/6", texto)
        self.assertIn("public", texto)

    def test_diz_para_QUAL_CONTA_foi(self):
        """O nome da conta e o destino, e sem ele "para que canal isso foi?"
        so se responde abrindo o navegador.

        O nome REAL nao entra na asserção: `testar.py` roda a suite com
        `NEURAL_FIGHTS_RUNTIME_DIR` isolado, entao o registro de contas da
        maquina nao existe la e `historinhas` viraria `principal`. Um teste
        que so passa NESTA maquina nao e um teste — cobra-se a chamada.
        """
        m = _postar()
        original = m._conta_do_destino
        m._conta_do_destino = lambda servico, canal: f"conta-{servico}"
        try:
            import subprocess
            enviado = []
            roda = subprocess.run
            subprocess.run = (lambda *a, **k: enviado.append(a[0][-1])
                              or type("R", (), {"returncode": 0})())
            try:
                m.avisar([self._historia()])
            finally:
                subprocess.run = roda
        finally:
            m._conta_do_destino = original
        self.assertIn("conta-youtube_web", enviado[0])
        self.assertIn("conta-tiktok", enviado[0])

    def test_a_cota_do_youtube_aparece_como_cota(self):
        texto = self._avisar([self._historia(url="", cota_youtube=True)])
        self.assertIn("limite diário", texto)

    def test_e_diz_o_proximo_horario(self):
        texto = self._avisar([self._historia()])
        self.assertIn("Próximo horário", texto)
        m = _postar()
        self.assertIn(f":{m.MINUTO_PADRAO:02d}", texto)



class QuedaDeEnergiaTests(unittest.TestCase):
    """A noite de 11/09/2026: tres horarios perdidos, e silencio total.

    A queda de energia derrubou o PC. Ele voltou as 03:34; as tarefas das
    06:07, 07:07 e 08:07 dispararam em dia e as tres morreram em
    `net::ERR_NAME_NOT_RESOLVED` — a rede nao tinha voltado junto. As 10:00 o
    DNS resolvia normalmente: era espera, nao defeito.

    TRES DEFEITOS SE SOMARAM, e nenhum sozinho teria feito o estrago:

    1. `return 0` fixo — o Agendador registrou SUCESSO nas tres rodadas que
       publicaram zero. O historico do Windows era a ultima coisa que ainda
       podia denunciar, e ele mentia.
    2. Erro de rede nao esperava nem tentava de novo.
    3. `avisar()` so disparava com `any(feito)` — rodada que nao publica NADA
       nao mandava Telegram nenhum. Falha calada e pior que falha.
    """

    def test_espera_a_rede_antes_de_gastar_navegador(self):
        m = _postar()
        self.assertTrue(m.esperar_a_rede(limite=5))

    def test_desiste_e_devolve_False_quando_a_rede_nao_volta(self):
        m = _postar()
        m.ALVOS_DE_REDE = ("nao.existe.invalido.teste",)
        self.assertFalse(m.esperar_a_rede(limite=1, log=lambda _s: None))

    def test_a_espera_cobre_religar_o_roteador(self):
        """Curta demais nao cobre o boot; longa demais engole o horario."""
        m = _postar()
        self.assertGreaterEqual(m.ESPERA_DE_REDE_S, 120)
        self.assertLessEqual(m.ESPERA_DE_REDE_S, 900)

    def test_o_codigo_de_saida_diz_a_VERDADE(self):
        fonte = POSTAR.read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def main("):]
        self.assertIn("if tentou and not any(", corpo)
        self.assertIn("return 1", corpo)

    def test_avisa_SEMPRE_e_nao_so_quando_deu_certo(self):
        """Era `if any(feito)`, e por isso a noite inteira passou calada."""
        fonte = POSTAR.read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def main("):]
        self.assertIn("if not args.ver:\n        avisar(resultados)", corpo)
        self.assertNotIn("any(r.get(\"feito\") for r in resultados):\n"
                         "        avisar(", corpo)

    def test_a_checagem_de_rede_vem_ANTES_de_publicar(self):
        fonte = POSTAR.read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def main("):]
        self.assertLess(corpo.index("esperar_a_rede()"),
                        corpo.index("resultados = []"))
if __name__ == "__main__":
    unittest.main()
