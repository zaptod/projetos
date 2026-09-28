# -*- coding: utf-8 -*-
"""A coleta que morre tem de dizer que morreu — e tentar de novo.

De 17 a 28/09/2026 a coleta do YouTube morreu ONZE noites seguidas
(NameError de 18 a 27/09, SSLError em 17, 19 e 28/09). `atualizar_tudo`
engolia a excecao, a marca do dia era gravada do mesmo jeito ("builds: 0"),
a rodada seguinte nem tentava, e o log da madrugada dizia "metricas da noite
atualizadas". A pagina lia o disco velho sem avisar.

Nada aqui toca rede, navegador ou a marca de verdade: a coleta de cada parte
e dublada um nivel abaixo, e a marca vai para uma pasta descartavel.
"""
import json
import tempfile
import unittest
from pathlib import Path

from builds import atividade
from builds.publicar import metricas
from builds.publicar import tiktok_metricas as T

NOITE = "noite-2026-09-27"


class MarcaDaNoite(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        reais = (metricas.MARCA_DO_DIA, metricas.reconciliar,
                 metricas.atualizar, T.coletar, atividade.registrar)
        self.addCleanup(self._restaurar, reais)
        metricas.MARCA_DO_DIA = Path(self._tmp.name) / "_atualizado_em.json"
        self.avisos, self.chamados = [], []
        atividade.registrar = lambda *a, **k: self.avisos.append((a, k))
        self.falhas = {}          # parte -> excecao a levantar
        metricas.reconciliar = lambda canal, log=print: 0

        def atualizar(log=print, canal="builds"):
            self.chamados.append(canal)
            if canal in self.falhas:
                raise self.falhas[canal]
            return [{"youtube_id": f"{canal}-1"}, {"youtube_id": f"{canal}-2"}]

        def coletar(canal, log=print, resumo=None, **_k):
            self.chamados.append(f"{canal}_tiktok")
            if f"{canal}_tiktok" in self.falhas:
                raise self.falhas[f"{canal}_tiktok"]
            if resumo is not None:
                resumo.update({"envios": 3, "posts": 9, "lista": "completa",
                               "casados": 3})
            return [{"tiktok_id": "t1"}, {"tiktok_id": "t2"},
                    {"tiktok_id": "t3"}]

        metricas.atualizar = atualizar
        T.coletar = coletar

    @staticmethod
    def _restaurar(reais):
        (metricas.MARCA_DO_DIA, metricas.reconciliar, metricas.atualizar,
         T.coletar, atividade.registrar) = reais

    def _rodar(self):
        return metricas.atualizar_uma_vez_por_dia(log=lambda *_a: None,
                                                  chave=NOITE)

    def _marca(self) -> dict:
        return json.loads(metricas.MARCA_DO_DIA.read_text(encoding="utf-8"))

    def test_noite_boa_fecha_e_nao_roda_de_novo(self):
        self.assertTrue(self._rodar())
        marca = self._marca()
        self.assertTrue(marca["completa"])
        self.assertEqual({"builds": 2, "builds_tiktok": 3, "historias": 2,
                          "historias_tiktok": 3}, marca["videos"])
        self.assertEqual(3, marca["partes"]["builds_tiktok"]["casados"])
        self.chamados.clear()
        self.assertFalse(self._rodar())
        self.assertEqual([], self.chamados)
        self.assertEqual([], self.avisos)

    def test_coleta_que_falha_vira_erro_e_nao_fecha_a_noite(self):
        # O caso das 01:20 de 28/09/2026: SSLError no YouTube de builds.
        self.falhas["builds"] = ConnectionError("SSLEOFError no playlistItems")
        self.assertFalse(self._rodar())
        marca = self._marca()
        self.assertFalse(marca["completa"])
        self.assertEqual("erro", marca["partes"]["builds"]["estado"])
        self.assertIn("SSLEOFError", marca["partes"]["builds"]["erro"])
        (args, kw), = self.avisos
        self.assertEqual("metricas", args[0])
        self.assertEqual(atividade.ERRO, args[1])
        self.assertIn("do YouTube de builds falhou", args[2])
        self.assertEqual("builds", kw["canal"])

    def test_a_rodada_seguinte_tenta_so_o_que_faltou(self):
        self.falhas["builds"] = ConnectionError("SSLEOFError")
        self._rodar()
        self.chamados.clear()
        del self.falhas["builds"]
        self.assertTrue(self._rodar())
        # So a parte pendente: repetir as outras seria gastar cota e segurar
        # o perfil do TikTok por nada.
        self.assertEqual(["builds"], self.chamados)
        marca = self._marca()
        self.assertTrue(marca["completa"])
        self.assertEqual("ok", marca["partes"]["builds"]["estado"])

    def test_a_mesma_falha_na_mesma_noite_avisa_uma_vez(self):
        self.falhas["historias"] = NameError("name 'titulos' is not defined")
        self._rodar()
        self._rodar()
        self._rodar()
        self.assertEqual(1, len(self.avisos))
        self.assertEqual(3, self._marca()["partes"]["historias"]["tentativas"])

    def test_falha_de_outro_tipo_avisa_de_novo(self):
        self.falhas["historias"] = ConnectionError("rede")
        self._rodar()
        self.falhas["historias"] = NameError("name 'titulos' is not defined")
        self._rodar()
        self.assertEqual(2, len(self.avisos))

    def test_a_falha_guarda_a_ultima_coleta_boa(self):
        # E o que o relatorio usa para dizer "velha desde 16/09".
        self._rodar()
        boa = self._marca()["partes"]["builds"]["ultimo_ok"]
        self.falhas["builds"] = ConnectionError("rede")
        metricas.atualizar_uma_vez_por_dia(log=lambda *_a: None,
                                           chave="noite-2026-09-28")
        parte = self._marca()["partes"]["builds"]
        self.assertEqual("erro", parte["estado"])
        self.assertEqual(boa, parte["ultimo_ok"])

    def test_marca_antiga_com_zero_nao_conta_como_feita(self):
        # A marca gravada as 01:20 de 28/09/2026, no formato de antes.
        metricas.MARCA_DO_DIA.write_text(json.dumps({
            "dia": NOITE, "quando": "2026-09-28T01:20:06",
            "videos": {"builds": 0, "builds_tiktok": 60, "historias": 156,
                       "historias_tiktok": 50}}), encoding="utf-8")
        self.assertTrue(self._rodar())
        self.assertEqual(["builds"], self.chamados)

    def test_a_marca_conta_video_e_nao_linha(self):
        # 28/09/2026: marca 126, disco 121 — o mesmo id em duas linhas do
        # ledger vira um arquivo so.
        metricas.atualizar = lambda log=print, canal="builds": [
            {"youtube_id": "I9ETJSGR1A0"}, {"youtube_id": "I9ETJSGR1A0"},
            {"youtube_id": "outro"}]
        self._rodar()
        parte = self._marca()["partes"]["builds"]
        self.assertEqual(2, parte["videos"])
        self.assertEqual(3, parte["linhas"])

    def test_parte_sem_nada_para_medir_e_vazio_e_nao_ok(self):
        # CASO ZERO: ledger sem id nenhum. Nao ha o que coletar — e isso nao
        # pode aparecer como "mediu 0 videos com sucesso" nem como falha.
        metricas.atualizar = lambda log=print, canal="builds": []
        self._rodar()
        parte = self._marca()["partes"]["builds"]
        self.assertEqual("vazio", parte["estado"])
        self.assertEqual(0, parte["videos"])
        self.assertEqual([], self.avisos)

    def test_o_log_nao_diz_mais_atualizadas_quando_falhou(self):
        linhas = []
        self.falhas["builds"] = ConnectionError("rede")
        metricas.atualizar_uma_vez_por_dia(log=linhas.append, chave=NOITE)
        resumo = [l for l in linhas if l.startswith("[metricas]")][-1]
        self.assertIn("builds erro", resumo)
        self.assertIn("PENDENTE", resumo)


class ChamadasContadas(unittest.TestCase):
    """Cada chamada a API e contada, e queda de conexao tem UMA repeticao."""

    def setUp(self):
        import requests
        self.requests = requests
        reais = (requests.get, metricas.PAUSA_ANTES_DE_TENTAR_DE_NOVO_S,
                 dict(metricas.CHAMADAS))
        self.addCleanup(self._restaurar, reais)
        metricas.PAUSA_ANTES_DE_TENTAR_DE_NOVO_S = 0.0
        for api in list(metricas.CHAMADAS):
            metricas.CHAMADAS[api] = 0

    def _restaurar(self, reais):
        self.requests.get, metricas.PAUSA_ANTES_DE_TENTAR_DE_NOVO_S, antes = \
            reais
        metricas.CHAMADAS.clear()
        metricas.CHAMADAS.update(antes)

    def test_queda_de_conexao_tenta_mais_uma_vez(self):
        respostas = [self.requests.exceptions.SSLError("SSLEOFError"), "ok"]

        def get(*_a, **_k):
            atual = respostas.pop(0)
            if isinstance(atual, Exception):
                raise atual
            return atual

        self.requests.get = get
        self.assertEqual("ok", metricas._get("data", "https://x"))
        self.assertEqual(2, metricas.CHAMADAS["data"])

    def test_duas_quedas_seguidas_sobem(self):
        def get(*_a, **_k):
            raise self.requests.exceptions.ConnectionError("fora do ar")

        self.requests.get = get
        with self.assertRaises(self.requests.exceptions.ConnectionError):
            metricas._get("analytics", "https://x")
        self.assertEqual(2, metricas.CHAMADAS["analytics"])

    def test_refresh_do_token_que_cai_por_rede_tenta_de_novo(self):
        # 17 e 19/09/2026: "HTTPSConnectionPool(host='oauth2.googleapis.com')"
        # derrubou a coleta inteira do canal.
        from builds.publicar import youtube
        reais = (youtube.carregar_credenciais, youtube.token_de_acesso)
        self.addCleanup(lambda: setattr(youtube, "carregar_credenciais",
                                        reais[0]))
        self.addCleanup(lambda: setattr(youtube, "token_de_acesso", reais[1]))
        credencial = object()
        quedas = [self.requests.exceptions.ConnectionError("oauth2 caiu")]

        def token(_cred):
            if quedas:
                raise quedas.pop()
            return "TOKEN"

        youtube.carregar_credenciais = lambda canal="builds": credencial
        youtube.token_de_acesso = token
        self.assertEqual(("TOKEN", credencial), metricas._token("builds"))
        self.assertEqual(2, metricas.CHAMADAS["token"])

    def test_resposta_ruim_nao_e_repetida(self):
        # 401/403/500 dizem alguma coisa; repetir so gasta cota.
        chamadas = []
        self.requests.get = lambda *_a, **_k: chamadas.append(1) or "403"
        self.assertEqual("403", metricas._get("data", "https://x"))
        self.assertEqual(1, len(chamadas))

    def test_a_parte_grava_quanto_custou(self):
        reais = (metricas.reconciliar, metricas.atualizar)
        self.addCleanup(lambda: setattr(metricas, "reconciliar", reais[0]))
        self.addCleanup(lambda: setattr(metricas, "atualizar", reais[1]))

        def atualizar(log=print, canal="builds"):
            metricas.CHAMADAS["data"] += 2
            metricas.CHAMADAS["analytics"] += 6
            return [{}, {}, {}]

        metricas.reconciliar = lambda canal, log=print: 0
        metricas.atualizar = atualizar
        ficha, _videos = metricas.coletar_parte("builds", "youtube",
                                                log=lambda *_a: None)
        self.assertEqual({"data": 2, "analytics": 6}, ficha["chamadas"])


class RetencaoSemEspectador(unittest.TestCase):
    """34,0% ou 51,5%? Em 28/09/2026 o duelo tinha dois numeros. O local
    (media de 7) contava dois rascunhos privados de 12/09 com 0 view e "0%"
    de retencao; a Analytics por video so devolve linha de quem foi visto
    (mediana de 5). Retencao de zero espectadores nao existe."""

    # Os sete arquivos de duelo em disco (atualizados 27/09 20:07).
    DUELOS = [("lK-sc2ZNw90", 124, 67.29, "public"),
              ("M34PrFvC70E", 44, 27.65, "public"),
              ("OVTVSrek3HA", 106, 55.06, "public"),
              ("ReZ81HQB1pU", 0, 0, "private"),
              ("YS7PiOSlmBc", 0, 0, "private"),
              ("lDz0Yv4jtEA", 80, 51.45, "public"),
              ("uQ9GP6B5CfI", 11, 36.26, "public")]

    def _dados(self):
        return [{"youtube_id": vid, "origem": "duelo", "views": views,
                 "views_analytics": views, "media_percentual": ret,
                 "privacidade": priv, "publicado_em": "2026-09-12T12:00:00Z",
                 "duracao": 20} for vid, views, ret, priv in self.DUELOS]

    def test_rascunho_privado_nao_entra_no_formato(self):
        from datetime import datetime
        (duelo,) = metricas.comparar_formatos(self._dados(),
                                              datetime(2026, 9, 28, 8, 0))
        self.assertEqual(5, duelo["videos"])
        self.assertEqual(2, duelo["privados_fora"])
        self.assertAlmostEqual(47.5, duelo["retencao_media"], places=1)
        self.assertEqual(51.45, duelo["retencao_mediana"])

    def test_zero_view_publico_nao_vira_zero_por_cento(self):
        # Arquivo gravado antes de 28/09: publico, 0 view, "0%".
        from datetime import datetime
        dados = self._dados()[:3] + [{
            "youtube_id": "novo", "origem": "duelo", "views": 0,
            "views_analytics": 0, "media_percentual": 0,
            "privacidade": "public", "publicado_em": "2026-09-27T12:00:00Z"}]
        (duelo,) = metricas.comparar_formatos(dados,
                                              datetime(2026, 9, 28, 8, 0))
        self.assertEqual(4, duelo["videos"])
        self.assertEqual(3, duelo["com_retencao"])

    def test_a_analytics_com_linha_de_zeros_nao_grava_retencao(self):
        class _Resposta:
            ok, status_code, text = True, 200, ""

            def json(self):
                return {"rows": [[0, 0, 0]]}

        real = metricas._get
        metricas._get = lambda *_a, **_k: _Resposta()
        self.addCleanup(lambda: setattr(metricas, "_get", real))
        medida = metricas.retencao("ReZ81HQB1pU", "t", "2026-09-12")
        self.assertNotIn("media_percentual", medida)
        self.assertIn("nao e 0%", medida["erro"])


class AMarcaNaoEVideo(unittest.TestCase):

    def test_carregar_salvas_pula_a_marca_do_dia(self):
        # Medido em 28/09/2026: 95 registros em builds, um deles a propria
        # marca (`canal, dia, quando, videos`), sem youtube_id.
        with tempfile.TemporaryDirectory() as pasta:
            real = metricas.PASTA
            metricas.PASTA = Path(pasta)
            self.addCleanup(lambda: setattr(metricas, "PASTA", real))
            (Path(pasta) / "abc.json").write_text(
                '{"youtube_id": "abc"}', encoding="utf-8")
            # Id de verdade que comeca com sublinhado: e video, nao marca.
            (Path(pasta) / "_bHp95XZpgc.json").write_text(
                '{"youtube_id": "_bHp95XZpgc"}', encoding="utf-8")
            (Path(pasta) / "_atualizado_em.json").write_text(
                '{"dia": "x", "videos": {}}', encoding="utf-8")
            self.assertEqual(["_bHp95XZpgc", "abc"],
                             [d["youtube_id"] for d in
                              metricas.carregar_salvas("builds")])


if __name__ == "__main__":
    unittest.main()
