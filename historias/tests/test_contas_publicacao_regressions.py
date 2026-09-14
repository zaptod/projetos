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
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

import builds.contas as _rb_contas
from contos.publicar import catalogo, qualidade, serie             # noqa: E402

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
        self.contas = _rb_contas
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


class HistoriaDeTesteTests(unittest.TestCase):
    """A historia de TESTE nao pode aparecer como publicavel (02/09/2026).

    A `historia_00002` tem `provedor: "fake"`, `tema: "teste"` e imagens que
    sao cartoes roxos escritos "P1 / 1" (14-22 KB cada, contra 230 KB-1,9 MB
    das reais). Mesmo assim o status dizia "pronta: 3 video(s) para publicar",
    e uma parte dela ja tinha sido exportada para `outputs/_publicar/`.
    """

    def test_o_status_diz_que_e_teste_em_vez_de_pronta(self):
        from contos.pipeline.controller import Pipeline
        passo = Pipeline._proximo_passo(
            {"faltam": 0}, [{"parte": 1, "videos": {"celular": True}}],
            True, {"provedor": "fake"})
        self.assertIn("TESTE", passo)
        self.assertNotIn("publicar", passo.replace("nao publicar", ""))

    def test_historia_de_verdade_continua_pronta(self):
        from contos.pipeline.controller import Pipeline
        passo = Pipeline._proximo_passo(
            {"faltam": 0}, [{"parte": 1, "videos": {"celular": True}}],
            True, {"provedor": "gemini"})
        self.assertIn("publicar", passo)

    def test_o_catalogo_e_a_porta_do_upload_e_ele_barra(self):
        # O status e texto na tela; o catalogo e por onde o video sobe.
        fonte = Path(catalogo.__file__).read_text(encoding="utf-8")
        self.assertIn('"fake"', fonte)


class NarracaoCobreOVideoTests(unittest.TestCase):
    """Vistoria: a narracao chegou inteira? (02/09/2026)

    A parte 1 da historia 8 tinha audio, tinha imagem, tinha 35,7 s e mais de
    100 KB — passava em todos os cinco cheques que existiam. O que faltava era
    comparar o video com o ROTEIRO: 417 palavras nao cabem em 36 segundos.
    """

    def test_a_faixa_esta_onde_a_fala_real_ficou(self):
        # Medido nas 30 partes boas: 1,99 a 2,87 palavras/s.
        self.assertLessEqual(qualidade.PALAVRAS_POR_S_MIN, 1.99)
        self.assertGreaterEqual(qualidade.PALAVRAS_POR_S_MAX, 2.87)

    def test_o_defeito_da_p01_fica_fora_da_faixa(self):
        self.assertGreater(417 / 35.7, qualidade.PALAVRAS_POR_S_MAX)

    def test_uma_parte_pela_metade_destoa_da_mediana(self):
        # 35,7 s contra ~145 s das cinco irmas.
        self.assertLess(35.7, 145.0 * qualidade.FRACAO_MINIMA_DA_MEDIANA)

    def test_o_silencio_do_fim_e_medido_ate_o_fim_do_arquivo(self):
        # O ffmpeg fecha o ultimo bloco no EOF: tratar "tem silence_end" como
        # "acabou antes" zerava a medida (foi o primeiro jeito, e dava 0,0).
        fonte = Path(qualidade.__file__).read_text(encoding="utf-8")
        self.assertIn("duracao - 0.3", fonte)

    def test_nivel_e_silencio_saem_de_UMA_decodificacao(self):
        fonte = Path(qualidade.__file__).read_text(encoding="utf-8")
        self.assertIn("volumedetect,silencedetect", fonte)


class PadraoDeNomesTests(unittest.TestCase):
    """O nome da conta e o DESTINO (08/09/2026).

    Ele pediu: "confira cada caminho e em qual canal vai, com base nisso mude
    o nome e crie o padrao". O que a auditoria achou no registro:

        `principal`            significava TRES destinos conforme o servico —
                               o canal pessoal, o historinhas e a conta de
                               builds do TikTok
        `bem_facil_d_verdade`  e `historinhas` eram o MESMO canal
        `canal2`               nao dizia nada

    Com nomes assim, "para onde isso vai?" so se responde abrindo o navegador,
    e publicar no canal errado nao tem desfazer.
    """

    def setUp(self):
        self.contas = _rb_contas
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._registro, self._runtime = self.contas.ARQUIVO, self.contas.runtime_dir
        self.contas.ARQUIVO = Path(self._tmp.name) / "contas.json"
        self.contas.runtime_dir = lambda: Path(self._tmp.name)

        def restaurar():
            self.contas.ARQUIVO = self._registro
            self.contas.runtime_dir = self._runtime
        self.addCleanup(restaurar)

    # ------------------------------------------------------------ renomear
    def test_renomear_leva_o_perfil_do_chrome_junto(self):
        """Renomear so o registro deixaria a conta sem login.

        O nome E a pasta. Trocar o registro e deixar a pasta para tras faria
        o proximo upload pedir login de novo, no meio de uma fila agendada.
        """
        self.contas.adicionar("tiktok", "canal2")
        pasta = self.contas.perfil("tiktok", "historias", "canal2")
        (pasta / "marca.txt").write_text("sessao", encoding="utf-8")

        self.contas.renomear("tiktok", "canal2", "historinhas")
        nova = Path(self._tmp.name) / "browser_profiles" / "tiktok__historinhas"
        self.assertTrue((nova / "marca.txt").is_file(), "o login ficou para tras")
        self.assertIn("historinhas", self.contas.contas("tiktok"))
        self.assertNotIn("canal2", self.contas.contas("tiktok"))

    def test_renomear_leva_a_credencial_do_youtube_junto(self):
        self.contas.adicionar("youtube", "bem_facil_d_verdade")
        cred = self.contas.credencial_youtube("historias", "bem_facil_d_verdade")
        cred.write_text('{"refresh_token": "x"}', encoding="utf-8")

        self.contas.renomear("youtube", "bem_facil_d_verdade", "historinhas")
        self.assertTrue(
            (Path(self._tmp.name) / "youtube_credentials_historinhas.json").is_file())

    def test_renomear_carrega_a_escolha_e_a_identidade(self):
        self.contas.adicionar("youtube_web", "antiga")
        self.contas.escolher("youtube_web", "builds", "antiga")
        self.contas.identificar("youtube_web", "antiga",
                                rotulo="Neural fights", identificador="UCA3Y")

        self.contas.renomear("youtube_web", "antiga", "neural_fights")
        self.assertEqual(self.contas.ativa("youtube_web", "builds"),
                         "neural_fights")
        self.assertEqual(
            self.contas.identidade("youtube_web", "neural_fights")["id"], "UCA3Y")

    def test_principal_NAO_se_renomeia(self):
        """Ela mora nos caminhos antigos; mover perderia os logins de todos.

        Ha teste irmao (`test_perfil_da_principal_e_o_caminho_antigo`) travando
        esse caminho — este garante que nem por engano se mexa nele.
        """
        with self.assertRaises(ValueError) as ctx:
            self.contas.renomear("tiktok", "principal", "neural_fights")
        self.assertIn("legado", str(ctx.exception))

    def test_nenhuma_conta_pode_virar_principal(self):
        self.contas.adicionar("tiktok", "outra")
        with self.assertRaises(ValueError):
            self.contas.renomear("tiktok", "outra", "principal")

    def test_nao_atropela_uma_conta_que_ja_existe(self):
        self.contas.adicionar("tiktok", "uma")
        self.contas.adicionar("tiktok", "outra")
        with self.assertRaises(ValueError):
            self.contas.renomear("tiktok", "uma", "outra")

    # -------------------------------------------------------- conformidade
    def _identificar(self, servico, conta, rotulo, ident):
        self.contas.adicionar(servico, conta)
        self.contas.identificar(servico, conta, rotulo=rotulo,
                                identificador=ident)

    def test_dois_nomes_para_o_mesmo_destino_e_acusado(self):
        for nome in ("historinhas", "bem_facil_d_verdade"):
            self._identificar("youtube_web", nome, "historinhas", "UC2S8")
        self.contas.escolher("youtube_web", "historias", "historinhas")
        self.contas.escolher("youtube_web", "builds", "bem_facil_d_verdade")
        tipos = [a["tipo"] for a in self.contas.conformidade()]
        self.assertIn("dois nomes para um destino", tipos)

    def test_dois_canais_no_mesmo_lugar_e_acusado(self):
        self._identificar("youtube_web", "historinhas", "historinhas", "UC2S8")
        for canal in ("builds", "historias"):
            self.contas.escolher("youtube_web", canal, "historinhas")
        tipos = [a["tipo"] for a in self.contas.conformidade()]
        self.assertIn("canais no mesmo destino", tipos)

    def test_canal_sem_escolha_e_acusado(self):
        # Registro virgem: builds e historias caem em `principal`.
        tipos = [a["tipo"] for a in self.contas.conformidade()]
        self.assertIn("canal sem conta propria", tipos)

    def test_nome_sem_sentido_e_sem_identidade_e_acusado(self):
        self.contas.adicionar("tiktok", "canal2")
        self.contas.escolher("tiktok", "historias", "canal2")
        achados = [a for a in self.contas.conformidade()
                   if a["tipo"] == "destino desconhecido"]
        self.assertTrue(achados)
        self.assertIn("canal2", achados[0]["detalhe"])

    def test_nome_ruim_COM_identidade_gravada_passa(self):
        """A regra e 'da para saber para onde vai', nao 'o nome e bonito'.

        `principal` do TikTok e o login legado e nao pode ser renomeada — mas
        se a identidade dela estiver registrada, a pergunta tem resposta.
        """
        self.contas.escolher("tiktok", "builds", "principal")
        self.contas.identificar("tiktok", "principal",
                                rotulo="Neural fights", identificador="@nf")
        tipos = [a["tipo"] for a in self.contas.conformidade()
                 if a["servico"] == "tiktok"]
        self.assertNotIn("destino desconhecido", tipos)

    def test_geral_nao_conta_como_canal_repetido(self):
        """`geral` nao e canal: e a queda de quem nao escolheu.

        Contando ele, a regra 2 acusava "historias e geral publicam no mesmo
        lugar" — que e a definicao de queda padrao, nao um defeito. O alerta
        certo para isso e a regra 3, e ele some sozinho quando o canal escolhe.
        """
        self._identificar("youtube_web", "historinhas", "historinhas", "UC2S8")
        self._identificar("youtube_web", "neural_fights", "Neural fights", "UCA3Y")
        self.contas.escolher("youtube_web", "historias", "historinhas")
        self.contas.escolher("youtube_web", "builds", "neural_fights")
        tipos = [a["tipo"] for a in self.contas.conformidade()
                 if a["servico"] == "youtube_web"]
        self.assertNotIn("canais no mesmo destino", tipos)

    def test_principal_nao_conta_como_nome_duplicado(self):
        """Ela nao pode ser renomeada: acusar seria alerta que nunca apaga."""
        self._identificar("youtube", "historinhas", "historinhas", "UC2S8")
        self.contas.identificar("youtube", "principal", rotulo="historinhas",
                                identificador="UC2S8")
        self.contas.escolher("youtube", "historias", "historinhas")
        tipos = [a["tipo"] for a in self.contas.conformidade()]
        self.assertNotIn("dois nomes para um destino", tipos)

    def test_oauth_sem_arquivo_e_reportado_como_morto(self):
        estado = self.contas.oauth_vivo("builds", "nao_existe")
        self.assertFalse(estado["ok"])
        self.assertIn("credencial", estado["motivo"])

    def test_oauth_com_arquivo_incompleto_nao_diz_que_esta_vivo(self):
        """`tem_login` so ve campos; isto tem que ver se serve.

        Em 08/09/2026 a auditoria dizia "login ok" para uma credencial que o
        Google recusava com `invalid_grant` — e as metricas estavam paradas
        havia seis dias sem nada avisar.
        """
        caminho = self.contas.credencial_youtube("builds", "capenga")
        caminho.write_text('{"client_id": "x"}', encoding="utf-8")
        estado = self.contas.oauth_vivo("builds", "capenga")
        self.assertFalse(estado["ok"])

    def test_login_sem_destino_nao_entra_na_conformidade(self):
        """PicassoIA e ChatGPT nao publicam: nao ha canal para nomear."""
        servicos = {a["servico"] for a in self.contas.conformidade()}
        for so_login in ("picasso", "chatgpt", "gemini", "digen", "dreamface"):
            self.assertNotIn(so_login, servicos)


class CenaSemImagemNaoPublicaTests(unittest.TestCase):
    """Cena sem imagem e ERRO, nao aviso (08/09/2026).

    O render nao se recusa a rodar sem imagem: ele desenha um cartao
    tipografico e entrega um mp4 que PARECE pronto. Como aviso, isso passou
    tres vezes — a historia 5 e a 10 foram ao disco com o GANCHO (cena 1, o
    primeiro segundo, onde a pessoa decide ficar) virado cartao de texto, e o
    painel dizia "pronta para publicar".

    Aviso e o que se le depois. Erro e o que impede.
    """

    def _laudo(self, faltam: int, cenas_faltando: list):
        from contos.imagens import fila
        from contos.roteiro import roteiro as R
        from contos.publicar import qualidade as Q

        roteiro = {"serie": True, "titulo": "T", "provedor": "gemini",
                   "partes": [{"n": 1, "cenas": [
                       {"n": i, "imagem": "x", "tempo": 4, "narracao": "oi"}
                       for i in range(1, 15)]}]}
        alvos = [
            (fila, "resumo", lambda *a, **k: {
                "total": 14, "prontas": 14 - faltam, "faltam": faltam,
                "completa": faltam == 0}),
            # Os arquivos precisam EXISTIR: a vistoria compara o mtime da
            # imagem com o do mp4 ("imagem mais nova que o video").
            # `prova` presente: aqui se testa a cena que FALTA, nao a origem
            # da imagem — essa tem teste proprio em `ImagemSemProvaTests`.
            (fila, "estado", lambda *a, **k: [
                {"n": i, "parte": 1, "pronta": i not in cenas_faltando,
                 "arquivo": self._png(i), "prova": {"comprovada": True}}
                for i in range(1, 15)]),
            (R, "carregar", lambda _h: roteiro),
            (R, "titulo_da_parte", lambda *a, **k: "T"),
            (Q, "vistoriar_arquivo", lambda _c: {
                "existe": True, "duracao": 140.0, "bytes": 10 ** 7,
                "audio": True, "video": True, "media_db": -17.0,
                "silencio_final": 0.0, "erros": [], "avisos": []}),
        ]
        for alvo, nome, falso in alvos:
            self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
            setattr(alvo, nome, falso)
        # O mp4 tambem precisa existir, e ser MAIS NOVO que as imagens: senao
        # a vistoria acusa "imagem mais nova que o video" e o teste passaria
        # pelo motivo errado.
        video = Path(self._tmp.name) / "final.mp4"
        video.write_bytes(b"\x00" * 32)
        return Q.vistoriar_parte("historia_00010", 1, video, roteiro)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _png(self, numero: int) -> Path:
        alvo = Path(self._tmp.name) / f"c{numero}.png"
        if not alvo.exists():
            alvo.write_bytes(b"\x89PNG")
        return alvo

    def test_uma_cena_sem_imagem_REPROVA(self):
        laudo = self._laudo(faltam=1, cenas_faltando=[1])
        self.assertFalse(laudo["ok"], "video com buraco nao pode publicar")
        self.assertTrue(any("sem imagem" in e for e in laudo["erros"]))

    def test_o_erro_diz_QUAL_cena_falta(self):
        """Sem o numero, a pessoa tem que ir procurar na pasta."""
        laudo = self._laudo(faltam=2, cenas_faltando=[1, 7])
        junto = " ".join(laudo["erros"])
        self.assertIn("cena(s) 1, 7", junto)

    def test_todas_as_imagens_passa(self):
        laudo = self._laudo(faltam=0, cenas_faltando=[])
        self.assertTrue(laudo["ok"], laudo["erros"])


class ParteAvulsaTambemRegistraTests(unittest.TestCase):
    """Publicar parte avulsa nao pode subir duas vezes (08/09/2026).

    `main.py publicar <id> --youtube` subia sem OLHAR nem REGISTRAR o ledger —
    so o caminho `--serie` registrava. Rodar o comando de novo colocaria o
    MESMO video no canal outra vez, e video duplicado no canal nao tem
    desfazer bonito.

    Descoberto na PRIMEIRA publicacao real do projeto: ela saiu por esse
    caminho e nao deixou rastro nenhum no `publicados.jsonl`.
    """

    def test_o_caminho_avulso_confere_o_ledger_antes(self):
        fonte = Path(RAIZ / "main.py").read_text(encoding="utf-8")
        corpo = fonte[fonte.index("if args.youtube or args.tiktok:"):]
        self.assertIn("ja_publicado(", corpo)
        self.assertLess(corpo.index("ja_publicado("),
                        corpo.index("catalogo.publicar_youtube("))

    def test_o_caminho_avulso_registra_depois(self):
        fonte = Path(RAIZ / "main.py").read_text(encoding="utf-8")
        corpo = fonte[fonte.index("if args.youtube or args.tiktok:"):]
        self.assertIn("_serie.registrar(", corpo)
        self.assertLess(corpo.index("catalogo.publicar_youtube("),
                        corpo.index("_serie.registrar("))

    def test_forcar_ainda_deixa_subir_de_novo(self):
        """Republicar as vezes e o que se quer; so nao pode ser por descuido."""
        fonte = Path(RAIZ / "main.py").read_text(encoding="utf-8")
        corpo = fonte[fonte.index("if args.youtube or args.tiktok:"):]
        self.assertIn("not args.forcar", corpo)


def _postar():
    """Carrega `ferramentas/postar.py` (script solto, nao e pacote)."""
    import importlib.util
    caminho = RAIZ.parent / "ferramentas" / "postar.py"
    spec = importlib.util.spec_from_file_location("postar_tool", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class PostagemDiariaTests(unittest.TestCase):
    """Uma postagem por dia, um video de cada canal, publica (08/09/2026).

    Ele pediu depois de o sistema passar o dia inteiro CRIANDO sem entregar
    nada: "quero que seja apenas um e que tudo seja public, quero um video de
    cada canal".
    """

    def test_a_visibilidade_padrao_e_publica(self):
        cfg = json.loads((RAIZ / "config" / "publicacao.json").read_text(
            encoding="utf-8"))
        self.assertEqual(cfg["youtube"]["visibilidade"], "public")

    def test_a_descricao_nao_fala_de_IA(self):
        """Dizer 'narrado por IA' quebra a imersao no pior momento.

        A linha sobre os personagens serem invencao FICA: ela impede que um
        desabafo inventado seja lido como confissao de gente real, e nao fala
        de como o video foi feito.
        """
        cfg = json.loads((RAIZ / "config" / "publicacao.json").read_text(
            encoding="utf-8"))
        for chave in ("historia", "parte"):
            texto = cfg["descricoes"][chave].lower()
            for proibido in (" ia", "inteligência artificial",
                             "inteligencia artificial", "gerado por", "narrada por ia"):
                self.assertNotIn(proibido, texto, chave)
            self.assertIn("invenção", texto)

    def test_a_descricao_e_acentuada(self):
        """Isto o publico le, ao lado de um titulo acentuado."""
        cfg = json.loads((RAIZ / "config" / "publicacao.json").read_text(
            encoding="utf-8"))
        texto = cfg["descricoes"]["parte"]
        self.assertIn("histórias", texto)
        self.assertIn("você", texto)

    def test_a_fila_respeita_a_ordem_das_partes(self):
        """Serie fora de ordem esta quebrada: quem cai na 4 sem ver a 3 sai."""
        postar = _postar()
        fila = postar.fila_de_historias()
        vistos = {}
        for video in fila:
            anterior = vistos.get(video.fonte_id)
            if anterior is not None:
                self.assertGreater(video.parte or 0, anterior,
                                   f"{video.fonte_id} fora de ordem")
            vistos[video.fonte_id] = video.parte or 0

    def test_a_fila_PULA_o_que_a_vistoria_reprova(self):
        """Video ruim na frente travaria o canal para sempre.

        A `historia_00001` e placeholder (gradiente com o numero da cena) e e
        a mais antiga — sem pular, ela seria o primeiro video PUBLICO.
        """
        postar = _postar()
        fonte = Path(postar.__file__).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def proxima_historia("):]
        self.assertIn("vistoriar_parte", corpo)
        self.assertIn("recusados.append", corpo)

    def test_ha_teto_de_tentativas(self):
        """Cada vistoria decodifica um mp4; acervo todo ruim viraria moinho."""
        postar = _postar()
        self.assertGreater(postar.TENTATIVAS, 1)
        self.assertLessEqual(postar.TENTATIVAS, 12)

    def test_posta_de_UM_canal_de_cada_vez(self):
        postar = _postar()
        fonte = Path(postar.__file__).read_text(encoding="utf-8")
        self.assertIn("postar_historia(", fonte)
        self.assertIn("postar_build(", fonte)
        self.assertIn('"DAILY"', fonte)


class ImagemSemProvaTests(unittest.TestCase):
    """Imagem sem prova de origem nao vai ao ar (08/09/2026).

    As imagens de verdade vem do PicassoIA e ficam registradas com a prova (o
    card do historico com o nosso prompt). As da `historia_00001` sao
    PLACEHOLDER gerado com PIL — um gradiente borrado com o numero da cena — e
    passavam em tudo: o arquivo existe, tem tamanho, o video tem imagem.
    """

    def test_o_erro_existe_e_e_bloqueante(self):
        fonte = (RAIZ / "contos" / "publicar" / "qualidade.py").read_text(
            encoding="utf-8")
        self.assertIn("prova de origem", fonte)
        corpo = fonte[fonte.index("sem_prova = "):]
        # nenhuma com prova = ERRO; algumas sem = aviso
        self.assertLess(corpo.index('laudo["erros"]'), corpo.index('laudo["avisos"]'))


if __name__ == "__main__":
    unittest.main()
