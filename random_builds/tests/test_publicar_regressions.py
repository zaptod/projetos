# -*- coding: utf-8 -*-
"""Regressões da publicação (catálogo, textos e envio ao YouTube).

O que estes testes protegem:

1. Os três lugares onde nascem mp4 (build, estreia, torneio) aparecem no
   MESMO índice — era isso que obrigava a caçar arquivo em pasta.
2. Um dado que falta some da frase em vez de virar "None" ou quebrar o
   título — o texto vai para a plataforma, não para o log.
3. O texto EDITADO vale sobre o gerado, e vale nos dois envios.
4. Exportar produz nome legível + o .txt ao lado (é o que substitui
   "entrar na pasta e renomear na mão").
5. O YouTube recusa cedo e com frase clara quando o token não autoriza
   upload — em vez de 403 no fim de 30 MB enviados.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

from builds.publicar import catalogo, metricas, youtube          # noqa: E402

CONFIG = {
    "titulos": {"build": "{personagem}, {classe} — build {nota}/100",
                "estreia": "{personagem} estreia contra {adversario}",
                "torneio": "Torneio de {participantes} — campeão: {campeao}"},
    "descricoes": {"build": "Arma: {arma}\nForça {forca}",
                   "estreia": "{personagem} x {adversario}: {desfecho}",
                   "torneio": "Campeão: {campeao}"},
    "hashtags": {"build": ["#shorts", "#rpg"], "estreia": ["#luta"],
                 "torneio": ["#torneio"]},
    "youtube": {"visibilidade": "private", "categoria": "20"},
}
CONTEUDO = b"v" * (catalogo.BYTES_MINIMOS + 1)


class CatalogoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.outputs = Path(self._tmp.name) / "outputs"
        self.build = self.outputs / "generation_00001"
        self.build.mkdir(parents=True)
        (self.build / "character.json").write_text(json.dumps({
            "nome": "Cobaia", "classe": "Ninja (Velocidade)",
            "nome_arma": "Katana", "forca": 7.0}), encoding="utf-8")
        (self.build / "build.json").write_text(
            json.dumps({"final_score": 80, "verdict_label": "BOA"}),
            encoding="utf-8")
        self._mp4(self.build)

        estreia = self.build / "estreia"
        estreia.mkdir()
        self._mp4(estreia)
        (self.build / "estreia.json").write_text(json.dumps({
            "personagem": "Cobaia", "adversario": "Rival",
            "vencedor": "Cobaia", "ko_type": "KO", "duracao": 30.2}),
            encoding="utf-8")

        torneio = self.outputs / "tournament_00001"
        torneio.mkdir()
        self._mp4(torneio)
        (torneio / "tournament.json").write_text(
            json.dumps({"campeao": "Rival", "participantes": ["a", "b", "c", "d"]}),
            encoding="utf-8")

        self.export = Path(self._tmp.name) / "publicar"
        self._patches = [
            patch.object(catalogo, "OUTPUTS", self.outputs),
            patch.object(catalogo, "pasta_export", lambda config=None: self.export),
        ]
        for p in self._patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._patches])
        self.addCleanup(self._tmp.cleanup)

    def _mp4(self, pasta: Path):
        for perfil in catalogo.PERFIS:
            (pasta / f"final_{perfil}.mp4").write_bytes(CONTEUDO)

    def _listar(self):
        return catalogo.listar(CONFIG)

    # ---------------------------------------------------------------- testes
    def test_os_tres_lugares_entram_no_mesmo_indice(self):
        videos = self._listar()
        origens = {v.origem for v in videos}
        self.assertEqual({catalogo.BUILD, catalogo.ESTREIA, catalogo.TORNEIO},
                         origens)
        # dois perfis por vídeo (celular e normal)
        self.assertEqual(6, len(videos))
        self.assertTrue(all(v.caminho.is_file() for v in videos))

    def test_titulo_usa_os_dados_da_build(self):
        build = next(v for v in self._listar() if v.origem == catalogo.BUILD)
        self.assertEqual("Cobaia, Ninja (Velocidade) — build 80/100",
                         build.titulo)
        estreia = next(v for v in self._listar() if v.origem == catalogo.ESTREIA)
        self.assertIn("estreia contra Rival", estreia.titulo)
        self.assertIn("venceu por KO", estreia.descricao)

    def _generation(self, dados: dict):
        (self.build / "generation.json").write_text(json.dumps(dados),
                                                    encoding="utf-8")

    def _descricao_real(self) -> str:
        """Contra o texto QUE VAI AO AR (config/publicacao.json), nao o dublê.

        A afirmacao de aleatoriedade mora no arquivo de verdade; testar contra
        o template do teste mediria uma frase que ninguem publica.
        """
        with open(ROOT / "config" / "publicacao.json", encoding="utf-8") as fh:
            real = json.load(fh)
        video = next(v for v in catalogo.listar(real)
                     if v.origem == catalogo.BUILD)
        return video.descricao

    def test_sem_escolha_a_descricao_afirma_o_sorteio(self):
        self.assertIn("100% aleatório", self._descricao_real())

    def test_com_atributo_escolhido_a_descricao_para_de_dizer_100_por_cento(self):
        """A descricao vai para a plataforma: nao pode afirmar o que o video nega."""
        self._generation({"escolhas": {"tela": {"classe": "Mago (Arcano)",
                                                "genero": "feminino"}}})
        descricao = self._descricao_real()
        self.assertNotIn("100% aleatório", descricao)
        self.assertIn("Escolhido a dedo", descricao)
        self.assertIn("classe Mago (Arcano)", descricao)

    def test_com_nome_pedido_a_descricao_credita_em_vez_de_afirmar(self):
        self._generation({"nome_pedido": {"nome": "Kaelen", "autor": "@zeca"}})
        descricao = self._descricao_real()
        self.assertNotIn("100% aleatório", descricao)
        self.assertIn("nome veio de vocês", descricao)

    def test_estreia_em_serie_conta_o_placar_e_nao_o_ultimo_round(self):
        """"venceu por KO" descreveria so o round que fechou a melhor de 3."""
        (self.build / "estreia.json").write_text(json.dumps({
            "personagem": "Cobaia", "adversario": "Rival",
            "vencedor": "Cobaia", "ko_type": "KO", "duracao": 30.2,
            "melhor_de": 3, "placar": [2, 1]}), encoding="utf-8")
        estreia = next(v for v in self._listar() if v.origem == catalogo.ESTREIA)
        self.assertIn("venceu por 2 x 1", estreia.descricao)
        self.assertNotIn("venceu por KO", estreia.descricao)

    def test_campo_que_falta_some_em_vez_de_virar_None(self):
        """Título vai para a plataforma: 'None' ali é pior que frase curta."""
        (self.build / "build.json").write_text("{}", encoding="utf-8")
        build = next(v for v in self._listar() if v.origem == catalogo.BUILD)
        self.assertNotIn("None", build.titulo)
        self.assertNotIn("{", build.titulo)
        self.assertTrue(build.titulo.startswith("Cobaia"))

    def test_hashtags_entram_na_descricao_completa(self):
        build = next(v for v in self._listar() if v.origem == catalogo.BUILD)
        self.assertIn("#shorts #rpg", build.descricao_completa)
        self.assertNotIn("#shorts", build.descricao)

    def test_texto_editado_vale_sobre_o_gerado(self):
        build = next(v for v in self._listar() if v.origem == catalogo.BUILD)
        catalogo.salvar_texto(build.id, "Meu título", "Minha descrição",
                              hashtags=["#meu"])
        editado = catalogo.por_id(build.id, CONFIG)
        self.assertEqual("Meu título", editado.titulo)
        self.assertEqual("Minha descrição", editado.descricao)
        self.assertIn("#meu", editado.descricao_completa)

    def test_exportar_da_nome_legivel_e_escreve_o_texto(self):
        build = next(v for v in self._listar() if v.origem == catalogo.BUILD)
        destino = catalogo.exportar(build, config=CONFIG)
        self.assertTrue(destino.is_file())
        self.assertIn("generation_00001", destino.name)
        self.assertIn("Cobaia", destino.name)
        self.assertTrue(destino.name.endswith(".mp4"))
        texto = destino.with_suffix(".txt").read_text(encoding="utf-8")
        self.assertIn(build.titulo, texto)
        self.assertIn("#shorts", texto)

    def test_vertical_identifica_o_corte_de_celular(self):
        videos = self._listar()
        celular = [v for v in videos if v.perfil == "celular"]
        self.assertTrue(all(v.vertical for v in celular))
        self.assertTrue(all(not v.vertical for v in videos if v.perfil == "normal"))


class YouTubeTests(unittest.TestCase):
    def _video(self):
        return catalogo.Video(
            id="x:build:celular", origem=catalogo.BUILD, perfil="celular",
            caminho=Path("nao-existe.mp4"), titulo="T" * 150,
            descricao="descrição", hashtags=["#um", "#dois"],
            fonte_id="generation_00001")

    def test_credencial_sem_upload_recusa_antes_de_enviar(self):
        credencial = youtube.Credenciais("id", "secret", "refresh",
                                         escopo=youtube.ESCOPO_UPLOAD.replace(
                                             "upload", "readonly"))
        self.assertFalse(credencial.tem_upload)
        with patch.object(youtube, "carregar_credenciais",
                          lambda *a, **k: credencial):
            with self.assertRaises(youtube.PublicacaoFalhou) as erro:
                youtube.publicar(self._video(), config=CONFIG)
        self.assertIn("--com-upload", str(erro.exception))

    def test_sem_credencial_diz_o_que_fazer(self):
        """A mensagem tem que dizer ONDE resolver, e em QUAL canal.

        Desde que cada canal tem a propria conta, "configure o OAuth" nao
        basta: o mesmo erro pode ser da conta de builds ou da de historias,
        e sao arquivos de credencial diferentes.
        """
        with patch.object(youtube, "carregar_credenciais", lambda *a, **k: None):
            with self.assertRaises(youtube.PublicacaoFalhou) as erro:
                youtube.publicar(self._video(), config=CONFIG)
        mensagem = str(erro.exception)
        self.assertIn("Contas", mensagem)
        self.assertIn("Autorizar", mensagem)
        self.assertIn("builds", mensagem)

    def test_visibilidade_invalida_nao_chega_na_rede(self):
        with self.assertRaises(youtube.PublicacaoFalhou):
            youtube.publicar(self._video(), visibilidade="amigos",
                             config=CONFIG)

    def test_corpo_respeita_os_limites_da_api(self):
        corpo = youtube._corpo(self._video(), CONFIG, "private")
        self.assertEqual(100, len(corpo["snippet"]["title"]))
        self.assertEqual(["um", "dois"], corpo["snippet"]["tags"])
        self.assertEqual("private", corpo["status"]["privacyStatus"])
        self.assertEqual("20", corpo["snippet"]["categoryId"])


class RegistroDePublicacaoTests(unittest.TestCase):
    """O elo entre o mp4 e a metrica — foi ele que faltou por um mes.

    `registrar_publicacao` so era chamada dentro do caminho da API, mas o
    modo padrao e o navegador: 32 videos subiram e nenhum entrou no
    `publicados.jsonl` por conta propria. Sem registro nao ha `youtube_id`,
    sem `youtube_id` nao ha curva de retencao, e sem curva toda decisao de
    edicao volta a ser palpite.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._registro = metricas.REGISTRO
        metricas.REGISTRO = Path(self._tmp.name) / "publicados.jsonl"
        self.addCleanup(lambda: setattr(metricas, "REGISTRO", self._registro))

    def _video(self):
        return catalogo.Video(
            id="generation_00099:build:celular", origem="build",
            perfil="celular", caminho=Path(self._tmp.name) / "v.mp4",
            titulo="Fulano, Mago", descricao="d", hashtags=["#shorts"],
            fonte_id="generation_00099")

    def _linhas(self):
        return metricas.publicados()

    def test_modo_navegador_registra_o_upload(self):
        video = self._video()
        with patch.object(youtube, "modo", lambda *a, **k: "navegador"):
            with patch.dict("sys.modules"):
                from builds.publicar import youtube_web
                with patch.object(youtube_web, "publicar",
                                  lambda *a, **k: "https://youtu.be/ABCdef123"):
                    youtube.publicar_como_configurado(video, config=CONFIG)
        linhas = self._linhas()
        self.assertEqual(1, len(linhas))
        self.assertEqual("ABCdef123", linhas[0]["youtube_id"])
        self.assertEqual("navegador", linhas[0]["via"])
        self.assertEqual("generation_00099", linhas[0]["fonte_id"])

    def test_navegador_sem_link_ainda_registra_o_fato(self):
        """O Studio nem sempre entrega a URL. "Foi publicado" nao se perde."""
        from builds.publicar import youtube_web
        with patch.object(youtube, "modo", lambda *a, **k: "navegador"):
            with patch.object(youtube_web, "publicar",
                              lambda *a, **k: youtube_web.SUCESSO):
                youtube.publicar_como_configurado(self._video(), config=CONFIG)
        linhas = self._linhas()
        self.assertEqual(1, len(linhas))
        self.assertIsNone(linhas[0]["youtube_id"])

    def test_navegador_que_nao_confirmou_nao_registra(self):
        """Registrar um "nao consegui confirmar" como publicado e pior que
        nao registrar: o video nunca mais seria tentado."""
        from builds.publicar import youtube_web
        with patch.object(youtube, "modo", lambda *a, **k: "navegador"):
            with patch.object(youtube_web, "publicar",
                              lambda *a, **k: "cliquei em publicar, mas..."):
                youtube.publicar_como_configurado(self._video(), config=CONFIG)
        self.assertEqual([], self._linhas())

    def test_visibilidade_gravada_e_a_que_valeu(self):
        """Sem `--visibilidade` o backend resolve pelo config; o registro
        precisa dizer a mesma coisa, e nao `null`."""
        from builds.publicar import youtube_web
        with patch.object(youtube, "modo", lambda *a, **k: "navegador"):
            with patch.object(youtube_web, "publicar",
                              lambda *a, **k: "https://youtu.be/ABCdef123"):
                youtube.publicar_como_configurado(self._video(), config=CONFIG)
        self.assertEqual("private", self._linhas()[0]["visibilidade"])

    def test_canal_de_historias_nao_suja_o_registro_de_builds(self):
        metricas.registrar_publicado(self._video(), "https://youtu.be/zzz",
                                     canal="historias")
        self.assertEqual([], self._linhas())

    def test_registro_nunca_derruba_a_publicacao(self):
        """Observabilidade que quebra a pipeline e pior que nenhuma."""
        def explode(*a, **k):
            raise OSError("disco cheio")

        with patch.object(metricas, "registrar_publicacao", explode):
            self.assertIsNone(metricas.registrar_publicado(
                self._video(), "https://youtu.be/zzz"))


class ComandoDeOauthTests(unittest.TestCase):
    """O comando que a mensagem de erro manda rodar precisa EXISTIR.

    Em 11/09/2026 a mensagem dizia `neural-fights youtube-oauth --com-upload
    --com-analytics`. Nao havia entry point `youtube-oauth` no pyproject, e
    a ferramenta exigia --client-id/--client-secret: quem seguia a
    instrucao so via o `usage` e nenhum navegador abria. Uma instrucao
    errada custa mais que nenhuma instrucao.
    """

    def test_o_comando_sugerido_e_aceito_pelo_parser_da_ferramenta(self):
        from neural_fights.tools.youtube_oauth import build_parser

        linha = metricas.comando_oauth("builds").split()
        self.assertEqual(
            ["python", "-m", "neural_fights.tools.youtube_oauth"], linha[:3],
            "a mensagem tem que nomear o modulo, nao um entry point que nao existe")
        args = build_parser().parse_args(linha[3:])
        self.assertTrue(args.com_analytics, "sem isso nao ha curva de retencao")
        self.assertTrue(args.com_upload, "pedir os dois de uma vez: um token so "
                                         "de analytics quebraria a publicacao")
        self.assertTrue(args.conta, "sem --conta a reautorizacao sobrescreve "
                                    "o canal errado")

    def test_o_comando_aponta_para_a_conta_ativa_do_canal(self):
        """Cada canal tem a sua conta; o comando tem que nomear a certa."""
        with patch("builds.contas.ativa", return_value="neural_fights"):
            self.assertIn("--conta neural_fights", metricas.comando_oauth("builds"))

    def test_sem_registro_de_contas_o_comando_ainda_sai(self):
        """Mensagem de erro nao pode falhar por causa de outro erro."""
        with patch("builds.contas.ativa", side_effect=RuntimeError("boom")):
            self.assertIn("--conta principal", metricas.comando_oauth("builds"))


class MotivoDaRecusaTests(unittest.TestCase):
    """Um 403 tem varias causas; chutar sempre a mesma manda pro lugar errado.

    Em 11/09/2026 o token estava vivo e o escopo correto, e mesmo assim todo
    video vinha com "escopo yt-analytics.readonly ausente". A causa real era
    `accessNotConfigured`: a API nunca foi ligada no projeto do Google Cloud.
    A mensagem errada custou uma reautorizacao inutil.
    """

    class _Resposta:
        def __init__(self, status, corpo):
            self.status_code = status
            self._corpo = corpo
            self.text = json.dumps(corpo) if isinstance(corpo, dict) else str(corpo)

        def json(self):
            if not isinstance(self._corpo, dict):
                raise ValueError("nao e json")
            return self._corpo

    def _erro(self, reason, mensagem="detalhe do google"):
        return {"error": {"code": 403, "message": mensagem,
                          "errors": [{"reason": reason}]}}

    def test_api_desligada_nao_e_confundida_com_escopo(self):
        motivo = metricas.motivo_da_recusa(
            self._Resposta(403, self._erro("accessNotConfigured")))
        self.assertIn("DESLIGADA", motivo)
        self.assertIn("youtubeanalytics.googleapis.com", motivo)
        self.assertNotIn("escopo yt-analytics", motivo)

    def test_escopo_faltando_manda_reautorizar(self):
        motivo = metricas.motivo_da_recusa(
            self._Resposta(403, self._erro("insufficientPermissions")))
        self.assertIn("escopo yt-analytics.readonly", motivo)
        self.assertIn("youtube_oauth", motivo)

    def test_token_revogado_manda_reautorizar(self):
        motivo = metricas.motivo_da_recusa(
            self._Resposta(401, self._erro("authError")))
        self.assertIn("revogado", motivo)
        self.assertIn("youtube_oauth", motivo)

    def test_motivo_desconhecido_repassa_o_que_o_google_disse(self):
        """Nunca engolir a resposta: o proximo defeito pode ser outro."""
        motivo = metricas.motivo_da_recusa(
            self._Resposta(403, self._erro("quotaExceeded", "cota estourada")))
        self.assertIn("quotaExceeded", motivo)
        self.assertIn("cota estourada", motivo)

    def test_resposta_que_nao_e_json_nao_derruba(self):
        motivo = metricas.motivo_da_recusa(self._Resposta(403, "<html>502</html>"))
        self.assertIn("403", motivo)


class CaminhoDeCredencialTests(unittest.TestCase):
    """Motor e fabrica precisam concordar em ONDE mora cada credencial.

    `neural_fights.tools.youtube_oauth` repete a regra de nomes de
    `builds.contas.credencial_youtube` de proposito: o motor nao importa a
    fabrica. Repeticao sem teste e divergencia com data marcada — e o
    sintoma seria a autorizacao gravar num arquivo que ninguem le.
    """

    def test_as_duas_regras_de_nome_dao_o_mesmo_arquivo(self):
        from builds import contas
        from neural_fights.tools.youtube_oauth import caminho_da_conta

        for nome in ("principal", "historinhas", "neural_fights", "outra_qualquer"):
            with self.subTest(conta=nome):
                self.assertEqual(contas.credencial_youtube("geral", nome),
                                 caminho_da_conta(nome))

    def test_o_par_do_app_e_reusado_de_outra_credencial(self):
        """client_id/secret sao do PROJETO, nao do canal.

        Reautorizar um canal novo nao pode exigir volta ao Google Cloud
        Console so para copiar dois campos que ja estao em disco.
        """
        from neural_fights.tools.youtube_oauth import credenciais_do_app

        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            (pasta / "youtube_credentials.json").write_text(json.dumps({
                "client_id": "ID-DO-APP", "client_secret": "SEGREDO",
                "refresh_token": "t"}), encoding="utf-8")
            alvo = pasta / "youtube_credentials_canal_novo.json"
            self.assertEqual(("ID-DO-APP", "SEGREDO"), credenciais_do_app(alvo))

    def test_a_credencial_do_proprio_destino_tem_prioridade(self):
        from neural_fights.tools.youtube_oauth import credenciais_do_app

        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            (pasta / "youtube_credentials.json").write_text(json.dumps({
                "client_id": "OUTRO", "client_secret": "X",
                "refresh_token": "t"}), encoding="utf-8")
            alvo = pasta / "youtube_credentials_meu.json"
            alvo.write_text(json.dumps({
                "client_id": "MEU", "client_secret": "Y",
                "refresh_token": "t"}), encoding="utf-8")
            self.assertEqual(("MEU", "Y"), credenciais_do_app(alvo))

    def test_sem_nenhuma_credencial_devolve_none_em_vez_de_inventar(self):
        from neural_fights.tools.youtube_oauth import credenciais_do_app

        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(credenciais_do_app(Path(tmp) / "nada.json"))


if __name__ == "__main__":
    unittest.main()
