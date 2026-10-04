# -*- coding: utf-8 -*-
"""O porteiro dos avisos: a mesma notificacao repetida sai UMA vez.

Medido em 04/10/2026, ultimas 48 h: 22x "No module named 'ias'" pelo bot,
24x "🤖 bot no ar" (um por religamento do coordenador), 5x o mesmo conserto do
tailnet no mesmo dia, e o Andamento do coordenador repetindo o mesmo item
parado da fila. Os testes aqui sao a regra: repetido cala, estado novo sai,
dia seguinte sai, e o calado aparece contado no relatorio.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from remoto import avisos
from remoto import bot as bot_mod
from remoto import comandos, config, relatorios


AGORA = datetime(2026, 10, 4, 12, 0)


class TelegramFalso:
    def __init__(self):
        self.enviadas = []

    def eu(self):
        return {"username": "meubot"}

    def novidades(self, desde=None, timeout=30):
        return []

    def mensagem(self, chat_id, texto, markdown=False):
        self.enviadas.append((chat_id, texto))
        return {"ok": True}


# ------------------------------------------------------------- o porteiro
def test_a_mesma_notificacao_n_vezes_sai_uma():
    saiu = [avisos.liberar("❗ PicassoIA (historias)\nNo module named 'ias'",
                           agora=AGORA + timedelta(minutes=i)) for i in range(22)]
    assert saiu.count(True) == 1 and saiu[0] is True


def test_so_a_hora_mudando_ainda_e_a_mesma_mensagem():
    assert avisos.liberar("🛰 Andamento (12:46) · Fila: 2", agora=AGORA)
    assert not avisos.liberar("🛰 Andamento (13:46) · Fila: 2",
                              agora=AGORA + timedelta(hours=1))
    assert avisos.liberar("tarefa x parada há 45 min (04/10)", agora=AGORA)
    assert not avisos.liberar("tarefa x parada há 90 min (05/10)",
                              agora=AGORA + timedelta(minutes=45))


def test_mudanca_de_estado_sai():
    assert avisos.liberar("⚠️ o app saiu do tailnet", chave="tailnet", agora=AGORA)
    assert avisos.liberar("✅ o app voltou ao tailnet", chave="tailnet",
                          agora=AGORA + timedelta(minutes=10))
    assert avisos.liberar("⚠️ o app saiu do tailnet", chave="tailnet",
                          agora=AGORA + timedelta(minutes=20))
    # e o mesmo estado de novo, sem mudar nada no meio, cala
    assert not avisos.liberar("⚠️ o app saiu do tailnet", chave="tailnet",
                              agora=AGORA + timedelta(minutes=30))


def test_parte_1_de_4_e_parte_2_de_4_sao_estados_diferentes():
    assert avisos.liberar("renderizando parte 1/4", agora=AGORA)
    assert avisos.liberar("renderizando parte 2/4", agora=AGORA)


def test_no_dia_seguinte_sai_de_novo():
    assert avisos.liberar("🤖 bot no ar", chave="bot.no_ar", agora=AGORA)
    assert not avisos.liberar("🤖 bot no ar", chave="bot.no_ar",
                              agora=AGORA + timedelta(hours=23))
    assert avisos.liberar("🤖 bot no ar", chave="bot.no_ar",
                          agora=AGORA + timedelta(hours=24, minutes=1))


def test_o_que_sai_fica_registrado_e_o_calado_e_contado():
    for i in range(5):
        avisos.liberar("mesmo aviso", agora=AGORA + timedelta(minutes=i))
    linhas = avisos._registro().read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 1 and json.loads(linhas[0])["texto"] == "mesmo aviso"
    calados = avisos.calados(24, agora=AGORA + timedelta(minutes=10))
    assert calados == [{"chave": calados[0]["chave"], "texto": "mesmo aviso",
                        "calados": 4}]


def test_porteiro_quebrado_deixa_passar(monkeypatch):
    def quebra(*_a, **_k):
        raise OSError("disco")
    monkeypatch.setattr(avisos, "_ler", quebra)
    assert avisos.liberar("x", agora=AGORA) and avisos.liberar("x", agora=AGORA)


def test_o_relatorio_de_funcionamento_conta_os_calados():
    for i in range(3):
        avisos.liberar("❗ PicassoIA erro igual", agora=datetime.now())
    linhas = relatorios._linhas_dos_calados(24)
    assert any("Avisos repetidos calados" in l and "(2)" in l for l in linhas)
    assert any("2x ❗ PicassoIA erro igual" in l for l in linhas)


# ------------------------------------------------------------------ o bot
def _bot(tmp_path, monkeypatch):
    config.ARQUIVO = str(tmp_path / "remoto.json")
    monkeypatch.setattr(comandos.atividade, "_arquivo",
                        lambda: tmp_path / "atividade.jsonl")
    apuracoes = []
    monkeypatch.setattr(bot_mod.Bot, "_apurar", lambda _s: apuracoes.append(1))
    monkeypatch.setattr(bot_mod.Bot, "_relatorios", lambda _s: None)
    config.autorizar(42)
    tg = TelegramFalso()
    return bot_mod.Bot(telegram=tg, log=lambda *_a: None), tg, apuracoes


def test_o_bot_manda_o_mesmo_erro_uma_vez_e_apura_uma_vez(tmp_path, monkeypatch):
    try:
        robo, tg, apuracoes = _bot(tmp_path, monkeypatch)
        for _ in range(6):                # o reparo falhando igual, hora a hora
            comandos.atividade.registrar("picasso", "erro", "No module named 'ias'",
                                         "historias", etapa="imagens")
            robo.uma_volta(timeout=0)
        assert len([t for _c, t in tg.enviadas if "No module named" in t]) == 1
        assert len(apuracoes) == 1
        # erro DIFERENTE ainda sai
        comandos.atividade.registrar("picasso", "erro", "parede de planos",
                                     "historias", etapa="imagens")
        robo.uma_volta(timeout=0)
        assert any("parede de planos" in t for _c, t in tg.enviadas)
        assert len(apuracoes) == 2
    finally:
        config.ARQUIVO = None


def test_bot_no_ar_uma_vez_por_dia(tmp_path, monkeypatch):
    try:
        robo, tg, _ = _bot(tmp_path, monkeypatch)
        for _ in range(5):                # cinco religamentos seguidos
            robo.avisar_todos("🤖 bot no ar. /ajuda para ver o que eu faço.",
                              chave="bot.no_ar")
        assert len(tg.enviadas) == 1
    finally:
        config.ARQUIVO = None


def test_resposta_a_comando_nao_passa_pelo_porteiro(tmp_path, monkeypatch):
    """Ele perguntou duas vezes: responde duas vezes."""
    try:
        robo, tg, _ = _bot(tmp_path, monkeypatch)
        robo._responder(42, "status: tudo certo")
        robo._responder(42, "status: tudo certo")
        assert len(tg.enviadas) == 2
    finally:
        config.ARQUIVO = None


def test_avisar_avulso_cala_o_repetido(tmp_path, monkeypatch):
    from remoto import api
    from remoto.__main__ import avisar

    enviados = []

    class Falso:
        def __init__(self, _token):
            pass

        def mensagem(self, chat, texto, markdown=False):
            enviados.append(texto)
            return {"ok": True}

    try:
        config.ARQUIVO = str(tmp_path / "remoto.json")
        config.salvar({"token": "t", "autorizados": [1], "alertas": True})
        monkeypatch.setattr(api, "Telegram", Falso)
        assert avisar("⚠️ historias: nao crio agora — C: com 3 GB")
        assert avisar("⚠️ historias: nao crio agora — C: com 3 GB")   # calado conta como ok
        assert avisar("⚠️ historias: nao crio agora — C: com 2 GB")   # mudou: sai
        assert enviados == ["⚠️ historias: nao crio agora — C: com 3 GB",
                            "⚠️ historias: nao crio agora — C: com 2 GB"]
    finally:
        config.ARQUIVO = None
