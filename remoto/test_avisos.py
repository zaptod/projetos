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
    assert avisos.liberar("mesmo aviso", agora=AGORA)
    avisos.confirmar("mesmo aviso", agora=AGORA)
    for i in range(1, 5):
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


def test_carteiro_sem_rede_nao_cala_o_proximo_e_vai_para_pendentes(monkeypatch):
    """09/10: sem DNS o `mensagem` devolve {} sem levantar; contava como entregue."""
    from ias import carteiro
    from remoto import api

    class SemRede:
        def __init__(self, *_a, **_k):
            pass

        def mensagem(self, *_a, **_k):
            return {}

    monkeypatch.setattr(api, "Telegram", SemRede)
    monkeypatch.setattr(config, "carregar", lambda: {"autorizados": [1]})
    monkeypatch.setattr(config, "token", lambda: "x")
    assert carteiro.avisar_telegram("a rede caiu de novo") is False
    assert carteiro.avisar_telegram("a rede caiu de novo") is False
    textos = [p["texto"] for p in avisos.pendentes()]
    assert textos == ["a rede caiu de novo", "a rede caiu de novo"]
    assert avisos.liberar("a rede caiu de novo") is True


# ----------------------------------- APP-12/13: a fila e o porteiro entre processos
_PROCESSO_QUE_LIBERA = """
import sys, time
from pathlib import Path
from remoto import avisos
pasta = Path(sys.argv[1])
avisos.ARQUIVO = pasta / "avisos_estado.json"
avisos.REGISTRO = pasta / "avisos_enviados.jsonl"
avisos.PENDENTES = pasta / "avisos_pendentes.jsonl"
print("pronto", flush=True)
while not (pasta / "vai").exists():
    time.sleep(0.005)
for i in range(150):
    avisos.liberar(f"aviso {sys.argv[2]}-{i}", chave=f"{sys.argv[2]}-{i}")
"""


def test_liberar_em_dois_processos_nao_perde_ficha(tmp_path):
    """APP-12: sem trava, de 300 `liberar()` em dois processos sobravam ~116."""
    import subprocess
    import sys
    from pathlib import Path
    raiz = Path(avisos.__file__).resolve().parents[1]
    filhos = [subprocess.Popen([sys.executable, "-c", _PROCESSO_QUE_LIBERA,
                                str(tmp_path), nome], cwd=str(raiz),
                               stdout=subprocess.PIPE, text=True)
              for nome in ("a", "b")]
    try:
        for filho in filhos:
            assert filho.stdout.readline().strip() == "pronto"
        (tmp_path / "vai").write_text("", encoding="utf-8")
        for filho in filhos:
            assert filho.wait(timeout=120) == 0
    finally:
        for filho in filhos:
            if filho.poll() is None:
                filho.kill()
    dados = json.loads((tmp_path / "avisos_estado.json").read_text(encoding="utf-8"))
    assert len(dados) == 300


def test_linha_ruim_nao_apaga_a_fila():
    """APP-13: uma linha invalida fazia `pendentes()` devolver [] e o proximo
    `enfileirar` regravava a fila so com o item novo."""
    avisos.PENDENTES.parent.mkdir(parents=True, exist_ok=True)
    bons = [{"texto": "um", "chave": "k1", "em": "2026-10-14T10:00:00"},
            {"texto": "dois", "chave": "k2", "em": "2026-10-14T10:01:00"}]
    avisos.PENDENTES.write_text(json.dumps(bons[0]) + "\n{quebrado\n"
                                + json.dumps(bons[1]) + "\n", encoding="utf-8")
    assert [p["texto"] for p in avisos.pendentes()] == ["um", "dois"]
    assert avisos.ULTIMA_LEITURA_RUIM["linhas"] == 1
    avisos.enfileirar("novo")
    assert [p["texto"] for p in avisos.pendentes()] == ["um", "dois", "novo"]


def test_enfileirar_sem_quebra_de_linha_no_fim_nao_cola_no_anterior():
    avisos.PENDENTES.parent.mkdir(parents=True, exist_ok=True)
    avisos.PENDENTES.write_text(json.dumps({"texto": "um", "em": "x"}), encoding="utf-8")
    avisos.enfileirar("dois")
    assert [p["texto"] for p in avisos.pendentes()] == ["um", "dois"]


def test_enfileirar_durante_entrega_sobrevive(tmp_path, monkeypatch):
    """APP-12: `_entregar_pendentes` lia a fila no comeco e a regravava no
    fim; o que outro processo enfileirou no meio sumia."""
    try:
        robo, tg, _ = _bot(tmp_path, monkeypatch)
        avisos.enfileirar("aviso antigo", chave="antigo")
        mandar = tg.mensagem

        def mensagem_que_enfileira(chat_id, texto, markdown=False):
            avisos.enfileirar("chegou no meio", chave="meio")
            return mandar(chat_id, texto, markdown)
        tg.mensagem = mensagem_que_enfileira
        robo._entregar_pendentes()
        assert any(t == "aviso antigo" for _c, t in tg.enviadas)
        assert [p["texto"] for p in avisos.pendentes()] == ["chegou no meio"]
    finally:
        config.ARQUIVO = None


def test_grupo_nao_leva_o_que_o_porteiro_calou(tmp_path, monkeypatch):
    """APP-16: o texto agrupado era montado ANTES do porteiro, e levava o
    aviso que ele tinha calado (ja enviado hoje)."""
    try:
        robo, tg, _ = _bot(tmp_path, monkeypatch)
        assert avisos.liberar("repetido de hoje", chave="rep")
        avisos.confirmar("repetido de hoje", chave="rep")
        for i in range(3):
            avisos.enfileirar(f"novo {i}", chave=f"n{i}")
        avisos.enfileirar("repetido de hoje", chave="rep")
        robo._entregar_pendentes()
        (texto,) = [t for _c, t in tg.enviadas]
        assert all(f"novo {i}" in texto for i in range(3))
        assert "repetido de hoje" not in texto
        assert avisos.pendentes() == []
    finally:
        config.ARQUIVO = None


# ------------------------------------------------- APP-11: alertas que se perdiam
def test_erro_antes_da_religada_e_avisado(tmp_path, monkeypatch):
    """O bot A sobe e da uma volta; um erro cai no diario; o bot B (a
    religada) sobe. Antes o B marcava o erro como visto e ninguem avisava."""
    try:
        robo_a, _tg_a, _ = _bot(tmp_path, monkeypatch)
        robo_a.uma_volta(timeout=0)
        comandos.atividade.registrar("picasso", "erro", "caiu bem na religada",
                                     "historias", etapa="imagens")
        tg_b = TelegramFalso()
        robo_b = bot_mod.Bot(telegram=tg_b, log=lambda *_a: None)
        robo_b.uma_volta(timeout=0)
        assert len([t for _c, t in tg_b.enviadas if "caiu bem na religada" in t]) == 1
        # e o C, logo depois, nao repete
        tg_c = TelegramFalso()
        bot_mod.Bot(telegram=tg_c, log=lambda *_a: None).uma_volta(timeout=0)
        assert tg_c.enviadas == []
    finally:
        config.ARQUIVO = None


def test_primeira_subida_nao_despeja_o_historico(tmp_path, monkeypatch):
    try:
        config.ARQUIVO = str(tmp_path / "remoto.json")
        monkeypatch.setattr(comandos.atividade, "_arquivo",
                            lambda: tmp_path / "atividade.jsonl")
        comandos.atividade.registrar("picasso", "erro", "erro de ontem", "historias")
        robo, tg, _ = _bot(tmp_path, monkeypatch)
        robo.uma_volta(timeout=0)
        assert tg.enviadas == []
    finally:
        config.ARQUIVO = None


def test_alertar_sete_erros_nao_perde_nenhum(tmp_path, monkeypatch):
    """Os 5 mais novos um a um; antes do conserto o 6o e o 7o sumiam."""
    try:
        robo, tg, _ = _bot(tmp_path, monkeypatch)
        for i in range(7):
            comandos.atividade.registrar("estudio", "erro", f"falha numero {i}",
                                         "builds", etapa=f"e{i}")
        robo.uma_volta(timeout=0)
        tudo = "\n".join(t for _c, t in tg.enviadas)
        assert all(f"falha numero {i}" in tudo for i in range(7))
        assert len(tg.enviadas) == 6                   # 5 + "e mais 2 erro(s)"
        assert any(t.startswith("❗ e mais 2 erro(s)") for _c, t in tg.enviadas)
        robo.uma_volta(timeout=0)
        assert len(tg.enviadas) == 6                   # nada repete
    finally:
        config.ARQUIVO = None
