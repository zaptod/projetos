"""Regressoes do adaptador de chat do YouTube.

Nenhum teste aqui toca a rede: o transporte e injetado e o relogio e falso. O
que se exercita e a maquina inteira -- parsing de payload gravado, refresh de
token, retomada por ``nextPageToken``, backoff e degradacao por quota.

O ultimo teste tranca a fronteira: fora deste adaptador, nenhum modulo da camada
de live pode importar rede. E o que impede a plataforma de vazar para dentro do
vocabulario de jogo.
"""

from __future__ import annotations

import ast
import json
import random
import unittest
from pathlib import Path

from neural_fights.live.events import EventKind
from neural_fights.live.sources.youtube import (
    CREDITOS_POR_MEMBRO,
    CUSTO_LISTAR_MENSAGENS,
    INTERVALO_MAXIMO,
    INTERVALO_MINIMO,
    Backoff,
    Credenciais,
    ErroDeAutenticacao,
    ErroDeTransporte,
    Quota,
    YouTubeChatSource,
    converter_mensagem,
)

FIXTURES = Path(__file__).parent / "fixtures"
CREDENCIAIS = Credenciais(
    client_id="cid", client_secret="segredo", refresh_token="refresh", video_id="VID"
)


def carregar_payload(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


class RelogioFalso:
    def __init__(self) -> None:
        self.agora = 0.0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


class TransporteFalso:
    """Devolve respostas roteirizadas e grava o que foi pedido."""

    def __init__(self, respostas: dict[str, object]) -> None:
        self.respostas = respostas
        self.chamadas: list[str] = []

    def __call__(self, url: str, **_kwargs) -> dict:
        self.chamadas.append(url)
        for fragmento, resposta in self.respostas.items():
            if fragmento in url:
                if isinstance(resposta, list):
                    return resposta.pop(0) if len(resposta) > 1 else resposta[0]
                if isinstance(resposta, Exception):
                    raise resposta
                if callable(resposta):
                    return resposta()
                return resposta
        raise AssertionError(f"URL nao roteirizada: {url}")


def fonte_de_teste(respostas, **opcoes) -> tuple[YouTubeChatSource, TransporteFalso, RelogioFalso]:
    transporte = TransporteFalso(respostas)
    relogio = RelogioFalso()
    fonte = YouTubeChatSource(
        CREDENCIAIS, transporte=transporte, relogio=relogio, **opcoes
    )
    return fonte, transporte, relogio


RESPOSTA_TOKEN = {"access_token": "tok", "expires_in": 3600}
RESPOSTA_VIDEO = {"items": [{"liveStreamingDetails": {"activeLiveChatId": "CHAT1"}}]}


class ParsingTests(unittest.TestCase):
    def test_mensagem_de_texto_vira_evento_de_chat(self) -> None:
        item = carregar_payload("youtube_chat_message.json")
        evento = converter_mensagem(item, sequence=1)

        self.assertIsNotNone(evento)
        self.assertEqual(evento.platform, "youtube")
        self.assertIs(evento.kind, EventKind.CHAT)
        self.assertEqual(evento.viewer_id, "UCabc123")
        self.assertEqual(evento.viewer_name, "Ana Clara")
        self.assertEqual(evento.text, "!entrar")
        self.assertEqual(evento.value_units, 0)
        self.assertFalse(evento.tem_valor)

    def test_super_chat_vira_creditos(self) -> None:
        item = carregar_payload("youtube_superchat.json")
        evento = converter_mensagem(item)

        self.assertIs(evento.kind, EventKind.SUPERCHAT)
        # 19.900.000 micros = R$ 19,90 -> 1990 creditos (1 por centavo)
        self.assertEqual(evento.value_units, 1990)
        self.assertAlmostEqual(evento.raw_amount, 19.9, places=4)
        self.assertEqual(evento.raw_currency, "BRL")
        self.assertEqual(evento.text, "!meteoro")

    def test_super_sticker_tambem_carrega_valor(self) -> None:
        item = carregar_payload("youtube_supersticker.json")
        evento = converter_mensagem(item)
        self.assertIs(evento.kind, EventKind.SUPERCHAT)
        self.assertEqual(evento.value_units, 500)

    def test_novo_membro_vale_creditos_fixos(self) -> None:
        item = carregar_payload("youtube_membership.json")
        evento = converter_mensagem(item)
        self.assertIs(evento.kind, EventKind.MEMBERSHIP)
        self.assertEqual(evento.value_units, CREDITOS_POR_MEMBRO)

    def test_moderador_e_dono_sao_preservados(self) -> None:
        item = carregar_payload("youtube_moderator.json")
        evento = converter_mensagem(item)
        self.assertTrue(evento.is_moderator)
        self.assertTrue(evento.privilegiado)

    def test_event_id_da_plataforma_e_a_chave_de_idempotencia(self) -> None:
        item = carregar_payload("youtube_chat_message.json")
        self.assertEqual(converter_mensagem(item).event_id, "LCC.MSG001")

    def test_tipos_nao_interpretados_sao_ignorados(self) -> None:
        """Ignorar e melhor que inventar semantica para um evento de sistema."""
        for tipo in ("chatEndedEvent", "sponsorOnlyModeStartedEvent", "tombstone"):
            with self.subTest(tipo=tipo):
                item = {
                    "id": "x",
                    "snippet": {"type": tipo},
                    "authorDetails": {"channelId": "UC1", "displayName": "A"},
                }
                self.assertIsNone(converter_mensagem(item))

    def test_payload_malformado_nao_explode(self) -> None:
        for item in (None, {}, [], {"snippet": {}}, {"snippet": {}, "authorDetails": []}):
            with self.subTest(item=repr(item)):
                self.assertIsNone(converter_mensagem(item))

    def test_mensagem_sem_channel_id_e_descartada(self) -> None:
        """Sem identidade estavel nao ha cooldown nem posse possiveis."""
        item = {
            "id": "x",
            "snippet": {"type": "textMessageEvent"},
            "authorDetails": {"displayName": "Anonimo"},
        }
        self.assertIsNone(converter_mensagem(item))

    def test_data_invalida_vira_zero_em_vez_de_erro(self) -> None:
        item = carregar_payload("youtube_chat_message.json")
        item["snippet"]["publishedAt"] = "nao e uma data"
        self.assertEqual(converter_mensagem(item).timestamp, 0.0)


class AutenticacaoTests(unittest.TestCase):
    def test_token_e_obtido_e_reaproveitado(self) -> None:
        fonte, transporte, relogio = fonte_de_teste(
            {
                "oauth2": RESPOSTA_TOKEN,
                "videos": RESPOSTA_VIDEO,
                "liveChat/messages": {"items": [], "nextPageToken": "T1"},
            }
        )
        fonte.buscar_pagina()
        fonte.buscar_pagina()

        pedidos_de_token = [u for u in transporte.chamadas if "oauth2" in u]
        self.assertEqual(len(pedidos_de_token), 1, "token pedido mais de uma vez")

    def test_token_expirado_e_renovado(self) -> None:
        fonte, transporte, relogio = fonte_de_teste(
            {
                "oauth2": RESPOSTA_TOKEN,
                "videos": RESPOSTA_VIDEO,
                "liveChat/messages": {"items": []},
            }
        )
        fonte.buscar_pagina()
        relogio.avancar(4000.0)
        fonte.buscar_pagina()

        self.assertEqual(len([u for u in transporte.chamadas if "oauth2" in u]), 2)

    def test_provedor_sem_access_token_falha_claro(self) -> None:
        fonte, _t, _r = fonte_de_teste({"oauth2": {"erro": "invalid_grant"}})
        with self.assertRaisesRegex(ErroDeAutenticacao, "access_token"):
            fonte.buscar_pagina()

    def test_credenciais_incompletas_sao_recusadas(self) -> None:
        with self.assertRaisesRegex(ErroDeAutenticacao, "incompletas"):
            Credenciais.de_dict({"client_id": "a"})

    def test_arquivo_ausente_diz_o_que_fazer(self) -> None:
        with self.assertRaisesRegex(ErroDeAutenticacao, "nao encontradas"):
            Credenciais.de_arquivo(FIXTURES / "nao_existe.json")


class PollingTests(unittest.TestCase):
    def test_pagina_converte_itens_e_guarda_o_token(self) -> None:
        pagina = carregar_payload("youtube_chat_page.json")
        fonte, _t, _r = fonte_de_teste(
            {"oauth2": RESPOSTA_TOKEN, "videos": RESPOSTA_VIDEO, "liveChat/messages": pagina}
        )
        eventos, intervalo = fonte.buscar_pagina()

        self.assertEqual(len(eventos), 3)
        self.assertEqual(fonte._page_token, "TOKEN_PAGINA_2")
        self.assertGreaterEqual(intervalo, INTERVALO_MINIMO)

    def test_token_de_pagina_e_enviado_na_chamada_seguinte(self) -> None:
        """E o que evita reprocessar tudo e o que retoma apos reconexao."""
        fonte, transporte, _r = fonte_de_teste(
            {
                "oauth2": RESPOSTA_TOKEN,
                "videos": RESPOSTA_VIDEO,
                "liveChat/messages": {"items": [], "nextPageToken": "T9"},
            }
        )
        fonte.buscar_pagina()
        fonte.buscar_pagina()

        ultima = [u for u in transporte.chamadas if "liveChat/messages" in u][-1]
        self.assertIn("pageToken=T9", ultima)

    def test_intervalo_respeita_o_piso_mesmo_com_valor_baixo(self) -> None:
        fonte, _t, _r = fonte_de_teste(
            {
                "oauth2": RESPOSTA_TOKEN,
                "videos": RESPOSTA_VIDEO,
                "liveChat/messages": {"items": [], "pollingIntervalMillis": 100},
            }
        )
        _eventos, intervalo = fonte.buscar_pagina()
        self.assertEqual(intervalo, INTERVALO_MINIMO)

    def test_intervalo_da_api_e_respeitado_quando_maior(self) -> None:
        """``pollingIntervalMillis`` e o contrato de quota do provedor."""
        fonte, _t, _r = fonte_de_teste(
            {
                "oauth2": RESPOSTA_TOKEN,
                "videos": RESPOSTA_VIDEO,
                "liveChat/messages": {"items": [], "pollingIntervalMillis": 9000},
            }
        )
        _eventos, intervalo = fonte.buscar_pagina()
        self.assertEqual(intervalo, 9.0)

    def test_item_invalido_no_meio_da_pagina_nao_perde_os_outros(self) -> None:
        pagina = carregar_payload("youtube_chat_page.json")
        pagina["items"].insert(1, {"id": "lixo"})
        fonte, _t, _r = fonte_de_teste(
            {"oauth2": RESPOSTA_TOKEN, "videos": RESPOSTA_VIDEO, "liveChat/messages": pagina}
        )
        eventos, _intervalo = fonte.buscar_pagina()
        self.assertEqual(len(eventos), 3)

    def test_sequence_e_monotonico_entre_paginas(self) -> None:
        pagina = carregar_payload("youtube_chat_page.json")
        fonte, _t, _r = fonte_de_teste(
            {"oauth2": RESPOSTA_TOKEN, "videos": RESPOSTA_VIDEO, "liveChat/messages": pagina}
        )
        primeira, _ = fonte.buscar_pagina()
        segunda, _ = fonte.buscar_pagina()
        self.assertLess(primeira[-1].sequence, segunda[0].sequence)


class ResolucaoTests(unittest.TestCase):
    def test_video_sem_transmissao_ativa_e_erro_recuperavel(self) -> None:
        fonte, _t, _r = fonte_de_teste(
            {"oauth2": RESPOSTA_TOKEN, "videos": {"items": []}}
        )
        with self.assertRaisesRegex(ErroDeTransporte, "sem transmissao ativa"):
            fonte.buscar_pagina()

    def test_transmissao_sem_chat_ativo_e_erro_recuperavel(self) -> None:
        fonte, _t, _r = fonte_de_teste(
            {"oauth2": RESPOSTA_TOKEN, "videos": {"items": [{"liveStreamingDetails": {}}]}}
        )
        with self.assertRaisesRegex(ErroDeTransporte, "sem chat ativo"):
            fonte.buscar_pagina()

    def test_sem_video_id_a_conta_e_consultada(self) -> None:
        credenciais = Credenciais(client_id="c", client_secret="s", refresh_token="r")
        fonte = YouTubeChatSource(
            credenciais,
            transporte=TransporteFalso(
                {
                    "oauth2": RESPOSTA_TOKEN,
                    "liveBroadcasts": {"items": [{"snippet": {"liveChatId": "C2"}}]},
                    "liveChat/messages": {"items": []},
                }
            ),
            relogio=RelogioFalso(),
        )
        fonte.buscar_pagina()
        self.assertEqual(fonte._live_chat_id, "C2")

    def test_chat_id_e_resolvido_uma_vez_so(self) -> None:
        fonte, transporte, _r = fonte_de_teste(
            {
                "oauth2": RESPOSTA_TOKEN,
                "videos": RESPOSTA_VIDEO,
                "liveChat/messages": {"items": []},
            }
        )
        fonte.buscar_pagina()
        fonte.buscar_pagina()
        self.assertEqual(len([u for u in transporte.chamadas if "videos" in u]), 1)


class BackoffTests(unittest.TestCase):
    def test_espera_cresce_e_satura_no_teto(self) -> None:
        backoff = Backoff(inicial=2.0, rng=random.Random(7))
        esperas = [backoff.proxima() for _ in range(10)]
        self.assertLess(esperas[0], esperas[3])
        self.assertLessEqual(max(esperas), INTERVALO_MAXIMO)

    def test_jitter_mantem_a_espera_na_faixa_esperada(self) -> None:
        """Jitter de +-25% evita que varios clientes voltem em uniao."""
        backoff = Backoff(inicial=8.0, rng=random.Random(3))
        espera = backoff.proxima()
        self.assertGreaterEqual(espera, 8.0 * 0.75)
        self.assertLessEqual(espera, 8.0 * 1.25)

    def test_reiniciar_volta_para_a_primeira_espera(self) -> None:
        backoff = Backoff(inicial=2.0, rng=random.Random(1))
        for _ in range(5):
            backoff.proxima()
        backoff.reiniciar()
        self.assertEqual(backoff.tentativas, 0)

    def test_backoff_e_deterministico_sob_rng_injetado(self) -> None:
        a = [Backoff(rng=random.Random(42)).proxima() for _ in range(1)]
        b = [Backoff(rng=random.Random(42)).proxima() for _ in range(1)]
        self.assertEqual(a, b)


class QuotaTests(unittest.TestCase):
    def test_consumo_e_contabilizado_por_chamada(self) -> None:
        fonte, _t, _r = fonte_de_teste(
            {
                "oauth2": RESPOSTA_TOKEN,
                "videos": RESPOSTA_VIDEO,
                "liveChat/messages": {"items": []},
            }
        )
        fonte.buscar_pagina()
        # uma resolucao de video (1) + uma listagem de mensagens (5)
        self.assertEqual(fonte.quota.gastas, 1 + CUSTO_LISTAR_MENSAGENS)

    def test_intervalo_cresce_conforme_a_quota_se_esgota(self) -> None:
        """Responder devagar e melhor que morrer com 403 no meio da live."""
        quota = Quota(limite=1000)
        base = 2.0
        quota.gastas = 100
        self.assertEqual(quota.intervalo_ajustado(base), base)
        quota.gastas = 600
        self.assertEqual(quota.intervalo_ajustado(base), base * 2)
        quota.gastas = 850
        self.assertEqual(quota.intervalo_ajustado(base), base * 4)
        quota.gastas = 990
        self.assertEqual(quota.intervalo_ajustado(base), INTERVALO_MAXIMO)

    def test_restantes_nunca_fica_negativo(self) -> None:
        quota = Quota(limite=10)
        quota.gastar(999)
        self.assertEqual(quota.restantes, 0)
        self.assertEqual(quota.fracao_usada, 1.0)


class ResilienciaTests(unittest.TestCase):
    def test_erro_de_rede_agenda_nova_tentativa_e_preserva_o_token(self) -> None:
        """A luta nunca para: queda de rede vira espera, nao fim de sessao."""
        fonte, _t, _r = fonte_de_teste(
            {
                "oauth2": RESPOSTA_TOKEN,
                "videos": RESPOSTA_VIDEO,
                "liveChat/messages": {"items": [], "nextPageToken": "T5"},
            }
        )
        fonte.buscar_pagina()
        self.assertEqual(fonte._page_token, "T5")

        fonte._transporte = TransporteFalso(
            {"liveChat/messages": ErroDeTransporte("cabo arrancado")}
        )
        with self.assertRaises(ErroDeTransporte):
            fonte.buscar_pagina()

        self.assertEqual(fonte._page_token, "T5", "token perdido: reprocessaria tudo")

    def test_loop_reconecta_apos_falha_e_encerra_no_sinal(self) -> None:
        chamadas = {"n": 0}

        def resposta_mensagens():
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                raise ErroDeTransporte("queda")
            return {"items": [], "nextPageToken": "T"}

        fonte, _t, _r = fonte_de_teste(
            {
                "oauth2": RESPOSTA_TOKEN,
                "videos": RESPOSTA_VIDEO,
                "liveChat/messages": resposta_mensagens,
            },
            backoff=Backoff(inicial=0.01, maximo=0.01, rng=random.Random(1)),
        )
        with self.assertLogs("neural_fights.live.sources.youtube", level="WARNING"):
            fonte.start()
            # Deixa o loop falhar, esperar e voltar antes de pedir parada.
            for _ in range(200):
                if fonte.conectado:
                    break
                import time as _time

                _time.sleep(0.01)
            fonte.stop()

        self.assertTrue(fonte.conectado)
        self.assertGreaterEqual(fonte.stats.erros_conexao, 1)

    def test_falha_de_autenticacao_encerra_em_vez_de_insistir(self) -> None:
        """Credencial ruim nao melhora com espera; insistir so queima quota."""
        fonte, _t, _r = fonte_de_teste(
            {"oauth2": RESPOSTA_TOKEN, "videos": ErroDeAutenticacao("403")}
        )
        with self.assertLogs("neural_fights.live.sources.youtube", level="ERROR"):
            fonte.start()
            fonte.stop()
        self.assertFalse(fonte.conectado)

    def test_diagnostico_nao_faz_chamada_de_rede(self) -> None:
        fonte, transporte, _r = fonte_de_teste({})
        diagnostico = fonte.diagnostico()
        self.assertEqual(transporte.chamadas, [])
        self.assertIn("quota_restante", diagnostico)
        self.assertFalse(diagnostico["conectado"])


class FronteiraDeRedeTests(unittest.TestCase):
    MODULOS_DE_REDE = {"urllib", "http", "socket", "ssl", "requests", "httpx", "asyncio"}

    def test_so_o_adaptador_do_youtube_conhece_rede(self) -> None:
        """Tranca a fronteira: plataforma nao vaza para o vocabulario de jogo."""
        raiz = Path(__file__).resolve().parents[1] / "neural_fights" / "live"
        permitido = raiz / "sources" / "youtube.py"
        infratores: list[str] = []

        for caminho in raiz.rglob("*.py"):
            if caminho == permitido:
                continue
            arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
            for no in ast.walk(arvore):
                if isinstance(no, ast.Import):
                    nomes = [alias.name for alias in no.names]
                elif isinstance(no, ast.ImportFrom):
                    nomes = [no.module or ""]
                else:
                    continue
                for nome in nomes:
                    if nome.split(".")[0] in self.MODULOS_DE_REDE:
                        infratores.append(f"{caminho.name}: {nome}")

        self.assertEqual(infratores, [], "modulo fora do adaptador importou rede")

    def test_motor_nao_importa_a_camada_de_live(self) -> None:
        """A dependencia e de mao unica: live conhece o motor, nunca o inverso."""
        raiz = Path(__file__).resolve().parents[1] / "neural_fights"
        infratores: list[str] = []

        for caminho in raiz.rglob("*.py"):
            if "live" in caminho.parts or caminho.name == "live.py":
                continue
            arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
            for no in ast.walk(arvore):
                alvo = ""
                if isinstance(no, ast.ImportFrom):
                    alvo = no.module or ""
                elif isinstance(no, ast.Import):
                    alvo = " ".join(alias.name for alias in no.names)
                if "neural_fights.live" in alvo:
                    infratores.append(f"{caminho.relative_to(raiz)}: {alvo}")

        self.assertEqual(infratores, [], "modulo do motor importou a camada de live")


if __name__ == "__main__":
    unittest.main()
