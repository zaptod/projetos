"""Contratos da fronteira de eventos de live.

Dados de plataforma sao entrada nao confiavel. Estes testes fixam o que a
fronteira aceita, o que ela rejeita, e as duas propriedades das quais o resto da
camada depende: idempotencia por ``event_id`` e backpressure que nunca bloqueia
a thread do jogo.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from neural_fights.live.events import LIMITE_NOME, EventKind, ViewerEvent
from neural_fights.live.sources.base import EventSource
from neural_fights.live.sources.replay import (
    ReplayEventSource,
    ScriptedEventSource,
    carregar_eventos,
    gravar_eventos,
)


def evento(**overrides) -> ViewerEvent:
    base = {
        "platform": "youtube",
        "viewer_id": "UC-abc",
        "viewer_name": "Ana",
        "kind": EventKind.CHAT,
    }
    base.update(overrides)
    return ViewerEvent(**base)


class ViewerEventValidationTests(unittest.TestCase):
    def test_identidade_e_obrigatoria(self) -> None:
        with self.assertRaises(ValueError):
            evento(platform="")
        with self.assertRaises(ValueError):
            evento(viewer_id="   ")

    def test_kind_desconhecido_e_rejeitado_na_fronteira(self) -> None:
        with self.assertRaisesRegex(ValueError, "kind de evento desconhecido"):
            evento(kind="explodir_tudo")

    def test_kind_aceita_texto_equivalente(self) -> None:
        self.assertIs(evento(kind="GIFT").kind, EventKind.GIFT)
        self.assertIs(evento(kind=" gift ").kind, EventKind.GIFT)

    def test_valores_numericos_precisam_ser_sanos(self) -> None:
        with self.assertRaises(ValueError):
            evento(value_units=-1)
        with self.assertRaises(ValueError):
            evento(raw_amount=float("nan"))
        with self.assertRaises(ValueError):
            evento(raw_amount=float("inf"))
        with self.assertRaises(TypeError):
            evento(value_units="muito")

    def test_bool_nao_passa_como_inteiro(self) -> None:
        """``True`` viraria 1 silenciosamente e mascararia erro de adaptador."""
        with self.assertRaises(TypeError):
            evento(value_units=True)

    def test_nome_gigante_e_rejeitado(self) -> None:
        with self.assertRaises(ValueError):
            evento(viewer_name="x" * (LIMITE_NOME + 1))

    def test_evento_e_imutavel(self) -> None:
        alvo = evento()
        with self.assertRaises(Exception):
            alvo.value_units = 999

    def test_raw_vira_copia_somente_leitura(self) -> None:
        original = {"a": 1}
        alvo = evento(raw=original)
        original["a"] = 2
        self.assertEqual(alvo.raw["a"], 1)
        with self.assertRaises(TypeError):
            alvo.raw["b"] = 3


class ViewerEventIdentityTests(unittest.TestCase):
    def test_event_id_ausente_vira_derivado_deterministico(self) -> None:
        """Idempotencia nunca pode ficar opcional."""
        a = evento(sequence=7)
        b = evento(sequence=7)
        self.assertEqual(a.event_id, "youtube:UC-abc:7")
        self.assertEqual(a.event_id, b.event_id)
        self.assertNotEqual(a.event_id, evento(sequence=8).event_id)

    def test_event_id_da_plataforma_tem_precedencia(self) -> None:
        self.assertEqual(evento(event_id="LCC.xyz", sequence=3).event_id, "LCC.xyz")

    def test_identidade_e_por_plataforma(self) -> None:
        mesmo_id = evento(platform="tiktok").chave_identidade
        self.assertEqual(mesmo_id, ("tiktok", "UC-abc"))
        self.assertNotEqual(mesmo_id, evento().chave_identidade)

    def test_valor_e_privilegio_sao_derivados(self) -> None:
        self.assertFalse(evento().tem_valor)
        self.assertTrue(evento(kind="gift", value_units=10).tem_valor)
        self.assertFalse(evento().privilegiado)
        self.assertTrue(evento(is_moderator=True).privilegiado)
        self.assertTrue(evento(is_owner=True).privilegiado)


class ViewerEventSerializationTests(unittest.TestCase):
    def test_round_trip_preserva_o_evento(self) -> None:
        alvo = evento(
            kind="superchat",
            event_id="LCC.1",
            sequence=4,
            text="vai!",
            value_units=250,
            raw_amount=19.9,
            raw_currency="BRL",
            is_moderator=True,
            timestamp=123.5,
        )
        self.assertEqual(ViewerEvent.from_dict(alvo.to_dict()), alvo)

    def test_campo_desconhecido_e_rejeitado(self) -> None:
        dados = evento().to_dict()
        dados["campo_novo"] = 1
        with self.assertRaisesRegex(ValueError, "campos desconhecidos"):
            ViewerEvent.from_dict(dados)

    def test_from_dict_exige_mapeamento(self) -> None:
        with self.assertRaises(TypeError):
            ViewerEvent.from_dict([("platform", "youtube")])


class BackpressureTests(unittest.TestCase):
    def test_fila_cheia_descarta_o_mais_antigo_e_contabiliza(self) -> None:
        """Perder interacao e aceitavel; travar a transmissao nao e."""
        fonte = ScriptedEventSource(capacidade=2)
        fonte.start()
        fonte.push(evento(sequence=1), evento(sequence=2), evento(sequence=3))

        drenados = fonte.drenar()
        self.assertEqual([e.sequence for e in drenados], [2, 3])
        self.assertEqual(fonte.stats.recebidos, 3)
        self.assertEqual(fonte.stats.descartados, 1)
        self.assertFalse(fonte.stats.saudavel)
        fonte.stop()

    def test_drenar_respeita_o_limite_por_frame(self) -> None:
        fonte = ScriptedEventSource(capacidade=10)
        fonte.start()
        fonte.push(*[evento(sequence=i) for i in range(6)])

        self.assertEqual(len(fonte.drenar(limite=2)), 2)
        self.assertEqual(len(fonte.drenar(limite=2)), 2)
        self.assertEqual(len(fonte.drenar()), 2)
        self.assertEqual(fonte.drenar(), [])
        fonte.stop()

    def test_fonte_so_publica_viewer_event(self) -> None:
        fonte = ScriptedEventSource()
        fonte.start()
        with self.assertRaises(TypeError):
            fonte._publicar({"platform": "youtube"})
        fonte.stop()

    def test_capacidade_precisa_ser_positiva(self) -> None:
        with self.assertRaises(ValueError):
            ScriptedEventSource(capacidade=0)

    def test_iniciar_duas_vezes_e_erro_de_uso(self) -> None:
        fonte = ReplayEventSource([evento()])
        fonte.start()
        try:
            with self.assertRaisesRegex(RuntimeError, "ja foi iniciada"):
                fonte.start()
        finally:
            fonte.stop()

    def test_erro_na_thread_produtora_nao_propaga(self) -> None:
        """Uma fonte que morre nao pode derrubar a live."""

        class FonteQuebrada(EventSource):
            nome = "quebrada"

            def _executar(self) -> None:
                raise RuntimeError("conexao caiu")

        fonte = FonteQuebrada()
        with self.assertLogs("neural_fights.live.sources.base", level="ERROR"):
            fonte.start()
            fonte.stop()
        self.assertEqual(fonte.stats.erros_conexao, 1)
        self.assertEqual(fonte.drenar(), [])


class ReplaySourceTests(unittest.TestCase):
    def test_replay_publica_a_sequencia_gravada(self) -> None:
        eventos = [evento(sequence=i) for i in range(3)]
        with ReplayEventSource(eventos) as fonte:
            fonte._thread.join(timeout=5)
            self.assertEqual([e.sequence for e in fonte.drenar()], [0, 1, 2])

    def test_replay_recusa_conteudo_invalido(self) -> None:
        with self.assertRaises(TypeError):
            ReplayEventSource([{"platform": "youtube"}])
        with self.assertRaises(ValueError):
            ReplayEventSource([evento()], velocidade=-1.0)

    def test_arquivo_jsonl_faz_round_trip(self) -> None:
        eventos = [evento(sequence=i, kind="gift", value_units=i * 10) for i in range(1, 4)]
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "sessao.jsonl"
            self.assertEqual(gravar_eventos(caminho, eventos), 3)
            self.assertEqual(list(carregar_eventos(caminho)), eventos)

    def test_linhas_vazias_e_comentarios_sao_ignorados(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "sessao.jsonl"
            caminho.write_text(
                "# gravado em uma live\n"
                "\n"
                + json.dumps(evento(sequence=1).to_dict())
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(len(carregar_eventos(caminho)), 1)

    def test_linha_invalida_aponta_o_numero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "sessao.jsonl"
            caminho.write_text(
                json.dumps(evento().to_dict()) + "\n{ nao e json\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, r":2: evento invalido"):
                carregar_eventos(caminho)


if __name__ == "__main__":
    unittest.main()
