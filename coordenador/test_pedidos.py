# -*- coding: utf-8 -*-
"""A mesa de pedidos nao chama Claude/Codex de verdade (dubles)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta

import pytest

from coordenador import pedidos

AGORA = datetime(2026, 10, 3, 10, 20)


class ClaudeFalso:
    def __init__(self, motivo=""):
        self.motivo = motivo

    def motivo_proibido(self):
        return self.motivo


class DespachanteFalso:
    """O `remoto.delegar` de mentira: grava o que pediram, nao abre processo."""

    def __init__(self, pasta):
        self.raiz = pasta
        self.estados, self.criados, self.fundos, self.parados = {}, [], [], []
        self.decisoes = []

    def pasta_da(self, ident):
        return self.raiz / ident

    def prompt_do_cargo(self, cargo):
        return f"[cargo {cargo}]"

    def criar(self, ident, arquivo, _permitidos, **kw):
        self.criados.append((ident, kw, arquivo.read_text(encoding="utf-8")))
        ficha = {"id": ident, "situacao": "criado", "atualizado_em": "2026-10-03T10:19:00",
                 "ia": kw.get("ia"), "thread_id": None}
        self.estados[ident] = ficha
        return ficha

    def no_fundo(self, argv, ident):
        self.fundos.append(list(argv))
        self.estados[ident].update(situacao="rodando", atualizado_em="2026-10-03T10:19:30")
        return 1

    def ler_estado(self, ident):
        if ident not in self.estados:
            raise KeyError(ident)
        return self.estados[ident]

    def ler_eventos(self, ident, desde=-1):
        return {"eventos": [{"tipo": "testa", "texto": "python -m pytest remoto -q"}],
                "offset": 10}

    def parar(self, ident):
        self.parados.append(ident)

    def terminar(self, ident, *, arquivos=1, resposta="feito", aplicado=True, desfecho="feito"):
        """O trabalhador terminou. Como o prompt manda, a resposta acaba com a
        linha DESFECHO (`desfecho`, so se ela ainda nao tiver); `desfecho=None`
        e o trabalhador que esqueceu a linha (v2, 05/10/2026)."""
        if desfecho is not None and pedidos.ler_desfecho(resposta)["fonte"] == "sem_linha":
            resposta = f"{resposta}\nDESFECHO: {desfecho}"
        self.estados[ident].update(situacao="terminou", diff={"arquivos": arquivos},
                                   aplicado={"arquivos": ["remoto/x.py"]} if aplicado else None)
        (self.raiz / ident).mkdir(parents=True, exist_ok=True)
        (self.raiz / ident / "resposta.md").write_text(resposta, encoding="utf-8")

    def registrar_pedido_permissao(self, ident, pedido):
        """Como o `delegar.registrar_pedido_permissao`: a ficha para esperando a
        decisao (o estado do servidor guarda a situacao de antes)."""
        estado = self.estados[ident]
        if estado.get("situacao") == "aguardando_permissao" and estado.get("pedido_permissao"):
            return estado
        pp = dict(pedido, regra="perguntar_ao_adrian", em=f"2026-10-03T10:2{len(self.decisoes)}:00")
        if pp.get("categoria") == "estado_do_servidor":
            pp["situacao_antes"] = estado.get("situacao") or "terminou"
        estado.update(situacao="aguardando_permissao", pedido_permissao=pp,
                      motivo="aguardando permissao: " + pp["o_que"])
        return estado

    def decidir_permissao(self, ident, permitir, sempre=False):
        self.decisoes.append((ident, permitir))
        estado = self.estados[ident]
        pp = estado.get("pedido_permissao") or {}
        estado["permissoes"] = list(estado.get("permissoes") or []) + [
            {"pedido": pp, "decisao": "permitir" if permitir else "negar"}]
        if pp.get("categoria") == "estado_do_servidor":
            # como o delegar: a ficha volta ao que era, ninguem e relancado
            estado.update(situacao=pp.get("situacao_antes") or "terminou", pedido_permissao=None,
                          motivo=("permissao concedida: " if permitir else "permissao negada: ")
                          + str(pp.get("o_que") or ""))
            return estado
        estado.update(
            situacao="criado" if permitir else "negado", pedido_permissao=None,
            motivo=("permissao concedida: " if permitir else "permissao negada: ")
            + str(pp.get("o_que") or ""))
        return estado

    def cair_no_limite(self, ident, renova_em, *, codigo_saida=1):
        """A rodada como a de 04/10: inicio, rate_limit_event "rejected", o
        result de erro 429 e o fim "o codex saiu com o codigo 1"."""
        pasta = self.raiz / ident
        pasta.mkdir(parents=True, exist_ok=True)
        anteriores = (pasta / "eventos.jsonl").read_text(encoding="utf-8").count("\n") \
            if (pasta / "eventos.jsonl").exists() else 0
        evs = [{"type": "delegar.inicio", "ok": True},
               {"type": "rate_limit_event", "rate_limit_info": {
                   "status": "rejected", "resetsAt": renova_em, "rateLimitType": "seven_day",
                   "unifiedWindows": {"five_hour": {"utilization": 0.41},
                                      "seven_day": {"utilization": 1}}}},
               {"type": "result", "is_error": True, "api_error_status": 429,
                "result": "You've hit your weekly limit · resets 9am (America/Sao_Paulo)"},
               {"type": "delegar.fim", "ok": False}]
        with open(pasta / "eventos.jsonl", "a", encoding="utf-8") as fh:
            for i, ev in enumerate(evs, start=anteriores + 1):
                fh.write(json.dumps({"n": i, "em": "2026-10-03T10:19:40", "ev": ev}) + "\n")
        (pasta / "resposta.md").write_text("You've hit your weekly limit", encoding="utf-8")
        self.estados[ident].update(situacao="terminou" if codigo_saida == 0 else "falhou",
                                   motivo="o codex saiu com o código 1",
                                   diff={"arquivos": 0}, aplicado=None)

    def rodada_boa(self, ident):
        """Uma rodada nova (sem limite) depois da que caiu."""
        pasta = self.raiz / ident
        n = (pasta / "eventos.jsonl").read_text(encoding="utf-8").count("\n")
        with open(pasta / "eventos.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"n": n + 1, "em": "x", "ev": {"type": "delegar.inicio"}}) + "\n")


class Relogio:
    def __init__(self):
        self.agora = AGORA

    def __call__(self):
        return self.agora

    def andar(self, **kw):
        self.agora += timedelta(**kw)


@pytest.fixture
def mesa(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coord"))
    avisos = []
    m = pedidos.MesaPedidos(despachante=DespachanteFalso(tmp_path / "delegados"),
                            claude=ClaudeFalso(), relogio=Relogio(),
                            avisar=avisos.append, uso=lambda: {"passou_teto": False})
    m.avisos = avisos
    return m


def _pedido(mesa, ident=None):
    lista = mesa.para_o_app()["pedidos"]
    return next(p for p in lista if p["id"] == ident) if ident else lista[0]


def test_pedido_cria_orquestrador_com_o_texto(mesa):
    p = mesa.registrar("corrija a tela do Agora")
    assert p["situacao"] == "recebido" and mesa.despachante.criados == []   # nada na hora
    mesa.passo()
    ident, kw, tarefa = mesa.despachante.criados[0]
    assert ident == p["id"] and kw["ia"] == "claude" and kw["cargo"] == "orquestrador"
    assert "corrija a tela do Agora" in tarefa
    assert mesa.despachante.fundos == [["rodar", "--id", p["id"]]]
    assert _pedido(mesa)["situacao"] == "trabalhando"


def test_continuacao_so_pelo_id_e_texto_solto_abre_outro(mesa):
    """05/10 (conferente 3): texto solto nunca gruda; a continuacao e pelo id."""
    primeiro = mesa.registrar("corrija a tela do app")
    mesa.passo()
    mesmo = mesa.registrar("e confira no celular", responde_a=primeiro["id"])
    assert mesmo["id"] == primeiro["id"] and mesmo["continuacao"] is True
    # rodando: a continuacao espera a rodada acabar (nunca roda no processo)
    mesa.passo()
    assert mesa.despachante.fundos == [["rodar", "--id", primeiro["id"]]]
    mesa.despachante.estados[primeiro["id"]].update(situacao="parado", thread_id="t1")
    mesa.passo()
    ultimo = mesa.despachante.fundos[-1]
    assert ultimo[:3] == ["corrigir", "--id", primeiro["id"]]
    texto = (mesa.despachante.pasta_da(primeiro["id"]) / "continuacao.md").read_text(encoding="utf-8")
    assert "corrija a tela do app" in texto and "e confira no celular" in texto
    outro = mesa.registrar("construa outra coisa no app")
    assert outro["id"] != primeiro["id"] and outro["continuacao"] is False
    mesa.passo()
    assert [c[0] for c in mesa.despachante.criados] == [primeiro["id"], outro["id"]]


def test_travado_espera_e_e_retomado(mesa):
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    mesa.relogio.andar(minutes=11)               # nenhum evento desde 10:19:30
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "esperando"
    assert "10 min" in _pedido(mesa)["motivo"]
    assert mesa.despachante.parados == [p["id"]]
    mesa.despachante.estados[p["id"]]["situacao"] = "parado"
    mesa.passo()                                 # ainda dentro do intervalo de retomada
    assert _pedido(mesa)["situacao"] == "esperando"
    mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "trabalhando"
    assert mesa.despachante.fundos[-1] == ["rodar", "--id", p["id"]]


def test_trabalhador_que_cai_sempre_vira_falhou(mesa):
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    for _ in range(pedidos.MAX_RETOMADAS + 2):
        mesa.despachante.estados[p["id"]].update(situacao="falhou", motivo="saiu com 1")
        mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
        mesa.passo()                  # trabalhando -> esperando
        mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
        mesa.passo()                  # esperando -> retomado (ou falhou)
    assert _pedido(mesa)["situacao"] == "falhou"
    assert mesa.despachante.fundos.count(["rodar", "--id", p["id"]]) == 1 + pedidos.MAX_RETOMADAS
    assert "caiu" in mesa.avisos[-1]


def test_espera_nao_repete_a_linha_a_cada_pulso(mesa):
    mesa.claude.motivo = "Claude proibido pelo Adrian"
    mesa.registrar("me explique o vigia")
    for _ in range(5):
        mesa.passo()
        mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    linhas = [c for c in mesa.para_o_app()["conversa"] if "em espera" in c["texto"]]
    assert len(linhas) == 1


def test_claude_proibido_deixa_pedido_em_espera_e_volta_sozinho(mesa):
    mesa.claude.motivo = "Claude proibido pelo Adrian"
    mesa.registrar("me explique o vigia")
    mesa.passo()
    p = _pedido(mesa)
    assert p["situacao"] == "esperando" and "proibido" in p["motivo"]
    assert mesa.despachante.criados == []
    mesa.claude.motivo = ""
    mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "trabalhando"


def test_teto_do_claude_tambem_espera(mesa):
    mesa.uso = lambda: {"passou_teto": True}
    mesa.registrar("me explique o vigia")
    mesa.passo()
    assert "teto" in _pedido(mesa)["motivo"]


def test_construir_com_claude_proibido_vai_para_codex(mesa):
    mesa.claude.motivo = "Claude proibido"
    p = mesa.registrar("construa a tela X")
    mesa.passo()
    ident, kw, tarefa = mesa.despachante.criados[0]
    assert ident == p["id"] and kw["ia"] == "codex"
    assert tarefa.startswith("[cargo orquestrador]")       # o Codex nao le o cargo sozinho
    assert _pedido(mesa)["situacao"] == "trabalhando"


def test_claude_proibido_no_meio_de_construir_passa_ao_codex(mesa):
    p = mesa.registrar("construa a tela X")
    mesa.passo()
    mesa.despachante.estados[p["id"]].update(situacao="parado", motivo="Claude proibido")
    mesa.claude.motivo = "Claude proibido"
    mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    mesa.passo()                     # parado -> esperando
    mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    mesa.passo()                     # o Codex assume com um trabalhador novo
    mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    mesa.passo()
    assert [(c[0], c[1]["ia"]) for c in mesa.despachante.criados] == [
        (p["id"], "claude"), (p["id"] + "-1", "codex")]


def test_entrega_aplicada_vai_ao_conferente_e_o_final_chega_ao_telegram(mesa):
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    mesa.despachante.terminar(p["id"], aplicado=False, resposta="consertei X")
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "entregue"
    mesa.passo()
    assert len(mesa.despachante.criados) == 1           # espera o vigia aplicar
    mesa.despachante.estados[p["id"]]["aplicado"] = {"arquivos": ["remoto/x.py"]}
    mesa.passo()
    conf, kw, tarefa = mesa.despachante.criados[1]
    assert conf == "mesa-conf-" + p["id"] and kw["cargo"] == "conferente"
    assert "corrija o defeito X do app" in tarefa and "consertei X" in tarefa
    mesa.despachante.terminar(conf, resposta="APROVADO: testes ok")
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "conferido"
    assert mesa.avisos and "consertei X" in mesa.avisos[-1]


def test_conferente_com_defeitos_falha(mesa):
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    mesa.despachante.terminar(p["id"])
    mesa.passo()
    mesa.passo()
    mesa.despachante.terminar("mesa-conf-" + p["id"], resposta="DEFEITOS: quebrou Y")
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "falhou"
    assert "quebrou Y" in mesa.avisos[-1]


def test_so_resposta_sem_codigo_fica_respondido(mesa):
    p = mesa.registrar("por que o vigia parou ontem à noite?")
    mesa.passo()
    mesa.despachante.terminar(p["id"], arquivos=0, aplicado=False, resposta="faltou disco")
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "respondido"
    assert "faltou disco" in mesa.avisos[-1]
    # um pedido encerrado nao recebe continuacao: o proximo texto abre outro
    assert mesa.registrar("outra coisa para fazer agora")["id"] != p["id"]


def test_continuacao_depois_de_aplicado_vai_a_um_orquestrador_novo(mesa):
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    mesa.despachante.terminar(p["id"], resposta="consertei X")      # o vigia ja aplicou
    mesa.passo()
    # v2: entregue so recebe a resposta EXPLICITA (o Responder do app)
    assert mesa.registrar("agora faça Y também", responde_a=p["id"])["id"] == p["id"]
    mesa.passo()                       # o mesmo nao pode: o aplicar nao reaplica
    mesa.passo()
    novo, kw, tarefa = mesa.despachante.criados[-1]
    assert novo == p["id"] + "-1" and kw["cargo"] == "orquestrador"
    assert "corrija o defeito X do app" in tarefa and "agora faça Y também" in tarefa


def test_veredito_e_a_primeira_palavra():
    assert pedidos._aprovado("APROVADO, nenhum defeito")
    assert not pedidos._aprovado("DEFEITOS: X. Depois de corrigir fica APROVADO")
    assert not pedidos._aprovado("")


def test_progresso_ao_vivo_resumido(mesa):
    mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    mesa.passo()
    textos = [c["texto"] for c in mesa.para_o_app()["conversa"]]
    assert "rodando testes: python -m pytest remoto -q" in textos


def test_pergunta_de_estado_fica_com_o_cerebro():
    assert pedidos.e_de_estado("o app está no ar?")
    assert pedidos.e_de_estado("status")
    assert not pedidos.e_de_estado("corrija o app que não está no ar?")
    assert not pedidos.e_de_estado("faça a aba de pedidos mostrar o status de cada um, com "
                                   "progresso ao vivo e a resposta final do conferente " * 3)


def test_resposta_do_grimorio_vira_pedido_e_fica_lida(mesa):
    """04/10/2026: "Por que nao tem ninguem lendo as decisoes?"."""
    eventos = [{"id": "arquivo-de-videos", "projeto": "geral", "titulo": "Liberar espaço",
                "opcao": "drive-desktop", "opcao_rotulo": "Google Drive para computador",
                "comentario": "", "lida": False}]
    itens = {"arquivo-de-videos": {"titulo": "Liberar espaço", "pergunta": "Como arquivar?",
                                   "contexto": "73 GB de vídeos",
                                   "opcoes": [{"id": "drive-desktop", "descricao": "move para o G:"}]}}
    marcados = []

    def marcar(ref, gerou, nota="", origem="leitor"):
        marcados.append((ref, gerou))
        eventos[0]["lida"] = True
    mesa.grimorio = (lambda: [e for e in eventos if not e["lida"]], marcar, lambda: itens)
    mesa.passo()
    assert marcados and marcados[0][0] == "geral/arquivo-de-videos"
    p = _pedido(mesa)
    assert marcados[0][1] == [f"tarefa:{p['id']}"]
    assert "Google Drive para computador" in p["texto"] and "move para o G:" in p["texto"]
    assert p["origem"] == "grimorio"
    assert mesa.despachante.criados[0][1]["cargo"] == "orquestrador"
    mesa.passo()                                   # ja lida: nao cria de novo
    assert len(marcados) == 1


def test_sem_grimorio_ligado_o_passo_nao_le_nada(mesa):
    assert mesa.grimorio is None and mesa.ler_grimorio() == []


# ======================================================== limite (05/10/2026)
USO_LIVRE = {"situacao": "ok", "passou_teto": False}
USO_NO_TETO = {"situacao": "ok", "passou_teto": True}


def _andar(mesa, vezes=1):
    for _ in range(vezes):
        mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
        mesa.passo()


def test_queda_por_limite_nao_gasta_retomada_e_volta_quando_o_uso_libera(mesa):
    """04/10: cb44cd52 e cd2e5e0c queimaram as 5 retomadas no limite semanal."""
    mesa.uso = lambda: USO_LIVRE
    p = mesa.registrar("me explique o vigia")
    mesa.passo()
    renova = (AGORA + timedelta(days=1)).timestamp()
    mesa.despachante.cair_no_limite(p["id"], renova)
    mesa.uso = lambda: USO_NO_TETO              # a sonda ja ve o teto
    _andar(mesa, pedidos.MAX_RETOMADAS + 3)
    atual = _pedido(mesa)
    assert atual["situacao"] == "parado_limite"
    assert "limite" in atual["motivo"] and "renova" in atual["motivo"]
    assert int(atual.get("retomadas") or 0) == 0
    assert mesa.despachante.fundos.count(["rodar", "--id", p["id"]]) == 1   # nenhum relancamento
    assert not any("caiu" in a for a in mesa.avisos)
    mesa.uso = lambda: USO_LIVRE                # o uso voltou a "allowed"
    _andar(mesa)
    assert _pedido(mesa)["situacao"] == "esperando"
    _andar(mesa)
    assert _pedido(mesa)["situacao"] == "trabalhando"
    assert mesa.despachante.fundos[-1] == ["rodar", "--id", p["id"]]


def test_limite_libera_pela_hora_de_renovar_mesmo_sem_sonda(mesa):
    mesa.uso = lambda: {"situacao": "velha", "passou_teto": False}
    p = mesa.registrar("me explique o vigia")
    mesa.passo()
    mesa.despachante.cair_no_limite(p["id"], (AGORA + timedelta(minutes=30)).timestamp())
    _andar(mesa, 3)
    assert _pedido(mesa)["situacao"] == "parado_limite"
    assert "renova" in _pedido(mesa)["motivo"]
    mesa.relogio.andar(minutes=30)
    _andar(mesa, 2)
    assert _pedido(mesa)["situacao"] == "trabalhando"


def test_a_mesma_queda_ja_liberada_nao_prende_de_novo(mesa):
    """Os eventos da rodada velha continuam no arquivo: liberada a queda, o
    pedido anda (sem isto ele girava parado_limite <-> esperando)."""
    mesa.uso = lambda: USO_LIVRE
    p = mesa.registrar("me explique o vigia")
    mesa.passo()
    mesa.despachante.cair_no_limite(p["id"], (AGORA - timedelta(hours=1)).timestamp())
    _andar(mesa, 4)
    assert _pedido(mesa)["situacao"] == "trabalhando"
    assert mesa.despachante.fundos.count(["rodar", "--id", p["id"]]) == 2
    # caiu de novo numa rodada NOVA: essa prende
    mesa.uso = lambda: USO_NO_TETO
    mesa.despachante.cair_no_limite(p["id"], (AGORA + timedelta(days=1)).timestamp())
    _andar(mesa, 2)
    assert _pedido(mesa)["situacao"] == "parado_limite"


def test_terminou_com_a_mensagem_do_limite_nao_vira_respondido(mesa):
    mesa.uso = lambda: USO_NO_TETO
    p = mesa.registrar("me explique o vigia")
    mesa.uso = lambda: USO_LIVRE
    mesa.passo()
    mesa.despachante.cair_no_limite(p["id"], (AGORA + timedelta(days=1)).timestamp(),
                                    codigo_saida=0)
    mesa.uso = lambda: USO_NO_TETO
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "parado_limite"
    assert not mesa.avisos                       # nada de "respondido: You've hit..."


def test_construir_no_limite_vai_ao_codex_na_hora(mesa):
    mesa.uso = lambda: USO_LIVRE
    p = mesa.registrar("construa a tela X")
    mesa.passo()
    mesa.despachante.cair_no_limite(p["id"], (AGORA + timedelta(days=1)).timestamp())
    _andar(mesa, 3)
    assert [(c[0], c[1]["ia"]) for c in mesa.despachante.criados] == [
        (p["id"], "claude"), (p["id"] + "-1", "codex")]
    assert _pedido(mesa)["situacao"] == "trabalhando"


def test_teto_da_semana_espera_dizendo_o_porque_e_quando_renova(mesa):
    renova = (AGORA + timedelta(hours=20)).timestamp()
    mesa.uso = lambda: {"situacao": "ok", "passou_teto": True, "renova_em": renova,
                        "motivo_teto": "a semana está em 100% (teto 95%)"}
    mesa.registrar("me explique o vigia")
    mesa.passo()
    motivo = _pedido(mesa)["motivo"]
    assert "teto" in motivo and "semana" in motivo and "renova" in motivo
    assert mesa.despachante.criados == []


def test_reabrir_devolve_o_pedido_falhou_ao_mesmo_trabalhador(mesa):
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    for _ in range(pedidos.MAX_RETOMADAS + 2):
        mesa.despachante.estados[p["id"]].update(situacao="falhou", motivo="saiu com 1")
        _andar(mesa, 2)
    assert _pedido(mesa)["situacao"] == "falhou"
    reaberto = mesa.reabrir(p["id"])
    assert reaberto["situacao"] == "esperando" and reaberto["retomadas"] == 0
    antes = len(mesa.despachante.fundos)
    _andar(mesa)
    assert _pedido(mesa)["situacao"] == "trabalhando"
    assert mesa.despachante.fundos[antes:] == [["rodar", "--id", p["id"]]]
    assert len(mesa.despachante.criados) == 1                 # o mesmo, nao um novo
    with pytest.raises(KeyError):
        mesa.reabrir("pedido-naoexiste")
    with pytest.raises(ValueError):
        mesa.reabrir(p["id"])                                  # esta trabalhando


def test_reabrir_um_pedido_que_morreu_no_limite_ja_renovado(mesa):
    """O caso real: cb44cd52/cd2e5e0c em "falhou", limite renovado as 9h."""
    mesa.uso = lambda: USO_LIVRE
    p = mesa.registrar("me explique o vigia")
    mesa.passo()
    mesa.despachante.cair_no_limite(p["id"], (AGORA - timedelta(hours=1)).timestamp())
    with pedidos._TRAVA:                       # o estado de 04/10, gravado pelo codigo velho
        dados = pedidos._ler()
        dados["pedidos"][0].update(situacao="falhou", retomadas=5,
                                   motivo="caiu 5 vezes: o codex saiu com o código 1")
        pedidos._gravar(dados)
    mesa.reabrir(p["id"], "reaberto: o limite renovou")
    _andar(mesa, 4)
    assert _pedido(mesa)["situacao"] == "trabalhando"
    assert mesa.despachante.fundos.count(["rodar", "--id", p["id"]]) == 2


def test_reabrir_pela_linha_de_comando(tmp_path, monkeypatch):
    from coordenador import __main__ as cli
    monkeypatch.setattr(pedidos, "MESA", pedidos.MesaPedidos(
        despachante=DespachanteFalso(tmp_path / "d"), claude=ClaudeFalso()))
    p = pedidos.registrar("corrija o defeito X do app")
    with pedidos._TRAVA:
        dados = pedidos._ler()
        dados["pedidos"][0]["situacao"] = "falhou"
        pedidos._gravar(dados)
    assert cli.main(["reabrir-pedido", p["id"]]) == 0
    assert pedidos.para_o_app()["pedidos"][0]["situacao"] == "esperando"
    assert cli.main(["reabrir-pedido", "pedido-sumiu"]) == 1


# ================================================ Grimorio retoma (lacuna 2)
def _grimorio(mesa, eventos, itens):
    marcados = []

    def marcar(ref, gerou, nota="", origem="leitor"):
        marcados.append((ref, gerou, nota))
        for e in eventos:
            if f"{e['projeto']}/{e['id']}" == ref:
                e["lida"] = True
    mesa.grimorio = (lambda: [e for e in eventos if not e["lida"]], marcar, lambda: itens)
    return marcados


def test_permissao_de_decisao_espera_o_grimorio_e_a_resposta_retoma_o_mesmo(mesa):
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    mesa.despachante.estados[p["id"]].update(
        situacao="aguardando_permissao", motivo="aguardando permissao: escolher a voz",
        pedido_permissao={"o_que": "escolher a voz", "categoria": "decisao_de_produto",
                          "por_que": "duas boas", "alvo": "voz", "decisao_id": "permissao-voz"})
    _andar(mesa, pedidos.MAX_RETOMADAS + 2)        # esperar NAO gasta retomada nem relanca
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando_voce"
    assert atual["grimorio_ref"] == "geral/permissao-voz"
    assert mesa.despachante.fundos == [["rodar", "--id", p["id"]]]
    eventos = [{"id": "permissao-voz", "projeto": "geral", "titulo": "Permissao: escolher a voz",
                "opcao": "permitir", "opcao_rotulo": "Permitir", "comentario": "a grave",
                "lida": False}]
    itens = {"permissao-voz": {"titulo": "Permissao: escolher a voz", "pergunta": "duas boas",
                               "opcoes": [{"id": "permitir", "descricao": "voz"}]}}
    marcados = _grimorio(mesa, eventos, itens)
    mesa.passo()
    assert len(mesa.para_o_app()["pedidos"]) == 1            # NAO abriu pedido novo
    assert marcados[0][:2] == ("geral/permissao-voz", [f"tarefa:{p['id']}"])
    assert mesa.despachante.decisoes == [(p["id"], True)]
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
    texto = (mesa.despachante.pasta_da(p["id"]) / "continuacao.md").read_text(encoding="utf-8")
    assert "Permitir" in texto and "a grave" in texto
    assert _pedido(mesa)["situacao"] == "trabalhando"


def test_marca_grimorio_na_resposta_espera_e_a_resposta_volta_ao_mesmo(mesa):
    p = mesa.registrar("me explique qual voz usar")
    mesa.passo()
    mesa.despachante.estados[p["id"]]["thread_id"] = "t1"
    mesa.despachante.terminar(p["id"], arquivos=0, aplicado=False,
                              resposta="Preciso que ele escolha.\nGRIMÓRIO: historias/qual-voz")
    mesa.passo()
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando_voce"
    assert atual["grimorio_ref"] == "historias/qual-voz"
    assert any("Grimório" in a for a in mesa.avisos)
    _andar(mesa, 3)
    assert _pedido(mesa)["situacao"] == "esperando_voce"   # nao virou "respondido"
    eventos = [{"id": "qual-voz", "projeto": "historias", "titulo": "Qual voz",
                "opcao": "grave", "opcao_rotulo": "A grave", "comentario": "", "lida": False},
               {"id": "outra", "projeto": "geral", "titulo": "Outra coisa",
                "opcao": "sim", "opcao_rotulo": "Sim", "comentario": "", "lida": False}]
    marcados = _grimorio(mesa, eventos, {"qual-voz": {"opcoes": []}, "outra": {"opcoes": []}})
    mesa.passo()
    lista = mesa.para_o_app()["pedidos"]
    assert len(lista) == 2                      # so a OUTRA resposta abriu pedido novo
    assert marcados[0][:2] == ("historias/qual-voz", [f"tarefa:{p['id']}"])
    assert mesa.despachante.fundos[1][:3] == ["corrigir", "--id", p["id"]]
    assert "A grave" in _pedido(mesa, p["id"])["texto"]


def test_continuacao_do_adrian_acorda_o_pedido_que_esperava_o_grimorio(mesa):
    p = mesa.registrar("me explique qual voz usar")
    mesa.passo()
    mesa.despachante.terminar(p["id"], arquivos=0, aplicado=False,
                              resposta="GRIMÓRIO: historias/qual-voz")
    mesa.passo()
    # v2: texto solto nao gruda no que espera o Grimorio; a resposta explicita sim
    solto = mesa.registrar("use a grave, não precisa esperar")
    assert solto["id"] != p["id"] and solto["continuacao"] is False
    mesa.registrar("use a grave, não precisa esperar", responde_a=p["id"])
    _andar(mesa, 2)
    assert _pedido(mesa)["situacao"] == "trabalhando"
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]


def test_permissao_comum_espera_sem_queimar_retomadas(mesa):
    """03/10: o 66e4ba54 foi relancado 5 vezes esperando a permissao."""
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    mesa.despachante.estados[p["id"]].update(
        situacao="aguardando_permissao", motivo="aguardando permissao: rodar no repo real",
        pedido_permissao={"o_que": "rodar no repo real", "categoria": "caminho_protegido"})
    _andar(mesa, pedidos.MAX_RETOMADAS + 2)
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando" and "permiss" in atual["motivo"]
    assert mesa.despachante.fundos == [["rodar", "--id", p["id"]]]
    mesa.despachante.decidir_permissao(p["id"], True)        # o Adrian permitiu no app
    _andar(mesa)
    assert mesa.despachante.fundos[-1] == ["retomar", "--id", p["id"]]


# ------------------------------------------- conferente de 05/10 (defeitos)
def _projetos_do_grimorio():
    from remoto import decisoes
    pastas = {p.name for p in (pedidos.RAIZ / "decisoes").iterdir()
              if p.is_dir() and not p.name.startswith(("_", "."))}
    return sorted(set(decisoes.PROJETOS) | pastas)


@pytest.mark.parametrize("projeto", _projetos_do_grimorio())
def test_marca_grimorio_vale_para_todo_projeto_do_grimorio(projeto):
    """app-e-bot, jogo-zombie e painel-e-vila tem hifen: a marca sumia calada."""
    for linha in (f"GRIMÓRIO: {projeto}/abc", f"GRIMORIO: {projeto}/abc",
                  f"**GRIMÓRIO:** {projeto}/abc-2", f"- GRIMÓRIO: `{projeto}/abc`"):
        marca = pedidos._MARCA_GRIMORIO.search("Feito.\n" + linha + "\n")
        assert marca, linha
        assert marca.group(1).lower() == projeto


NO_LIGADO = {"gerente-ligado": {
    "id": "gerente-ligado", "projeto": "geral", "titulo": "Ligar o gerente",
    "vigente": {"opcao": "sim", "comentario": "pode ligar", "em": "2026-10-04T09:00:00"},
    "opcoes": [{"id": "sim", "rotulo": "Sim, ligar", "descricao": "o gerente contrata"},
               {"id": "nao", "rotulo": "Não"}]}}


def test_marca_para_no_ja_respondido_e_lido_entrega_a_decisao_na_hora(mesa):
    """O caso do cb44cd52: geral/gerente-ligado ja decidido e lido. Antes, o
    pedido ficava em espera 100 h e o Adrian recebia "espera a sua decisao"."""
    eventos = [{"id": "gerente-ligado", "projeto": "geral", "opcao": "sim", "lida": True}]
    _grimorio(mesa, eventos, NO_LIGADO)
    p = mesa.registrar("ligue o gerente da equipe")
    mesa.passo()
    mesa.despachante.estados[p["id"]]["thread_id"] = "t1"
    mesa.despachante.terminar(p["id"], arquivos=0, aplicado=False,
                              resposta="Preciso da decisão.\nGRIMÓRIO: geral/gerente-ligado")
    mesa.passo()
    assert _pedido(mesa)["situacao"] != "esperando_voce"
    assert not any("Grimório" in a for a in mesa.avisos)
    _andar(mesa)
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
    texto = (mesa.despachante.pasta_da(p["id"]) / "continuacao.md").read_text(encoding="utf-8")
    assert "Sim, ligar" in texto and "pode ligar" in texto
    assert len(mesa.para_o_app()["pedidos"]) == 1


def test_marca_para_no_que_nao_existe_devolve_e_nao_prende(mesa):
    _grimorio(mesa, [], {})
    p = mesa.registrar("me explique qual voz usar")
    mesa.passo()
    mesa.despachante.estados[p["id"]]["thread_id"] = "t1"
    for vez in range(3):
        mesa.despachante.terminar(p["id"], arquivos=0, aplicado=False,
                                  resposta="GRIMÓRIO: app-e-bot/nao-existe")
        _andar(mesa, 2)
        if vez < 2:
            assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
            # o que o SERVIDOR devolve nunca entra no texto do Adrian (conferente 5)
            assert "não existe" in " ".join(_pedido(mesa)["do_servidor"])
            assert "não existe" not in _pedido(mesa)["texto"]
            mesa.passo()                     # o pulso o ve rodando a continuacao
    assert _pedido(mesa)["situacao"] == "respondido"       # na 3a vez segue, nao gira
    assert not any("❓" in a for a in mesa.avisos)


def test_no_respondido_e_lido_por_outro_solta_o_pedido_que_esperava(mesa):
    """O no estava pendente; a sessao do VS Code leu a resposta antes do
    servidor. O pedido nao fica esperando um evento que nunca vem."""
    eventos = []
    itens = {"qual-voz": {"id": "qual-voz", "projeto": "historias",
                          "opcoes": [{"id": "grave", "rotulo": "A grave"}]}}
    _grimorio(mesa, eventos, itens)
    p = mesa.registrar("me explique qual voz usar")
    mesa.passo()
    mesa.despachante.estados[p["id"]]["thread_id"] = "t1"
    mesa.despachante.terminar(p["id"], arquivos=0, aplicado=False,
                              resposta="GRIMÓRIO: historias/qual-voz")
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "esperando_voce"
    assert sum("❓" in a for a in mesa.avisos) == 1
    itens["qual-voz"]["vigente"] = {"opcao": "grave", "comentario": ""}
    eventos.append({"id": "qual-voz", "projeto": "historias", "opcao": "grave", "lida": True})
    _andar(mesa, 2)
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
    assert "A grave" in _pedido(mesa)["texto"]
    assert sum("❓" in a for a in mesa.avisos) == 1          # o aviso nao se repete


def test_permissao_decidida_no_app_nao_decide_de_novo_nem_gasta_rodada(mesa):
    """O fluxo real: o api_http decide a permissao e relanca `retomar`; o
    delegar real recusa uma 2a decisao. Antes: erro falso na conversa e um
    `corrigir` a mais no mesmo trabalhador."""
    desp = mesa.despachante
    original = desp.decidir_permissao

    def decidir_como_o_real(ident, permitir, sempre=False):
        if not desp.estados[ident].get("pedido_permissao"):
            raise RuntimeError("nao ha permissao pendente nessa tarefa")
        return original(ident, permitir, sempre)
    desp.decidir_permissao = decidir_como_o_real
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    desp.estados[p["id"]].update(
        situacao="aguardando_permissao", motivo="aguardando permissao: escolher a voz",
        pedido_permissao={"o_que": "escolher a voz", "categoria": "decisao_de_produto",
                          "decisao_id": "permissao-voz"})
    _andar(mesa)
    assert _pedido(mesa)["situacao"] == "esperando_voce"
    # o app: api_http.decidir_permissao + `retomar` no fundo
    desp.decidir_permissao(p["id"], True)
    desp.no_fundo(["retomar", "--id", p["id"]], p["id"])
    eventos = [{"id": "permissao-voz", "projeto": "geral", "opcao": "permitir",
                "opcao_rotulo": "Permitir", "comentario": "", "lida": False}]
    marcados = _grimorio(mesa, eventos, {"permissao-voz": {"projeto": "geral", "opcoes": []}})
    _andar(mesa, 2)
    assert marcados and marcados[0][:2] == ("geral/permissao-voz", [f"tarefa:{p['id']}"])
    assert len(mesa.para_o_app()["pedidos"]) == 1
    assert desp.decisoes == [(p["id"], True)]               # so a do app
    conversa = " ".join(c["texto"] for c in mesa.para_o_app()["conversa"])
    assert "não consegui registrar" not in conversa
    assert _pedido(mesa)["situacao"] == "trabalhando"
    desp.terminar(p["id"], resposta="feito")              # a rodada do app termina
    _andar(mesa, 3)
    assert not [f for f in desp.fundos if f[0] == "corrigir"]
    do_trabalhador = [f for f in desp.fundos if f[2] == p["id"]]
    assert do_trabalhador == [["rodar", "--id", p["id"]], ["retomar", "--id", p["id"]]]


def test_mensagem_nova_com_o_pedido_parado_no_limite_vai_ao_codex(mesa):
    mesa.uso = lambda: USO_LIVRE
    p = mesa.registrar("me explique o vigia")
    mesa.passo()
    mesa.despachante.cair_no_limite(p["id"], (AGORA + timedelta(days=3)).timestamp())
    mesa.uso = lambda: USO_NO_TETO
    _andar(mesa, 2)
    assert _pedido(mesa)["situacao"] == "parado_limite"
    # v2: o pedido parado no limite so recebe a resposta explicita
    r = mesa.registrar("e também me diga quando ele roda", responde_a=p["id"])
    assert r["continuacao"]
    _andar(mesa, 2)
    assert [(c[0], c[1]["ia"]) for c in mesa.despachante.criados] == [
        (p["id"], "claude"), (p["id"] + "-1", "codex")]
    assert "quando ele roda" in mesa.despachante.criados[-1][2]
    assert _pedido(mesa)["situacao"] == "trabalhando"


def _eventos(caminho, registros):
    with open(caminho, "a", encoding="utf-8") as fh:
        for r in registros:
            fh.write(json.dumps(r) + "\n")


def test_queda_numa_rodada_longa_acha_o_inicio_dela(mesa, tmp_path):
    """Rodadas reais passam de 256 KB (vila-inventario 1751 KB): o inicio
    ficava fora da leitura, `inicio_n` virava None, e None == None fazia a
    queda nova parecer "ja liberada"."""
    ident = "longo"
    pasta = mesa.despachante.pasta_da(ident)
    pasta.mkdir(parents=True)
    rejeitado = {"type": "rate_limit_event",
                 "rate_limit_info": {"status": "rejected", "resetsAt": 1791201600}}
    _eventos(pasta / "eventos.jsonl", [{"n": 1, "ev": {"type": "delegar.inicio"}},
                                       {"n": 2, "ev": rejeitado},
                                       {"n": 3, "ev": {"type": "delegar.inicio"}}])
    enchimento = "x" * 1000
    _eventos(pasta / "eventos.jsonl", [{"n": 4 + i, "ev": {"type": "assistant", "t": enchimento}}
                                       for i in range(700)])          # ~720 KB
    _eventos(pasta / "eventos.jsonl", [{"n": 800, "ev": rejeitado}])
    queda = mesa._queda_por_limite(ident)
    assert queda and queda["inicio_n"] == 3
    # a queda velha (rodada 1), ja liberada, nao engole a nova (rodada 3)
    assert mesa._queda_nova({"limite_liberado_n": 1}, ident) is not None
    assert mesa._queda_nova({"limite_liberado_n": 3}, ident) is None


def test_queda_sem_inicio_nunca_tem_chave_none(mesa):
    ident = "antigo"
    pasta = mesa.despachante.pasta_da(ident)
    pasta.mkdir(parents=True)
    _eventos(pasta / "eventos.jsonl", [{"n": 1, "ev": {
        "type": "result", "is_error": True, "result": "You've hit your weekly limit"}}])
    queda = mesa._queda_por_limite(ident)
    assert queda and queda["inicio_n"] is not None
    assert mesa._queda_nova({"limite_liberado_n": None}, ident) is not None


# ================================================ executor (lacuna 3)
@pytest.fixture
def acao_duble(monkeypatch):
    monkeypatch.setattr(pedidos, "ACOES_REPO", {
        "duble": {"o_que": "comando dublê", "argv": [sys.executable, "-c",
                                                    "print('ola do repo real')"],
                  "cwd": ".", "timeout_s": 60, "janela": False},
        "duble_janela": {"o_que": "respeita a janela",
                         "argv": [sys.executable, "-c", "print('ok')"],
                         "cwd": ".", "timeout_s": 60},
        "duble_param": {"o_que": "com argumento",
                        "argv": [sys.executable, "-c", "print('{1}')"],
                        "cwd": ".", "parametros": [r"historia_\d{5}"], "timeout_s": 60,
                        "janela": False}})


def _executor_real(mesa):
    """O executor de producao (thread + subprocess de verdade), com o comando
    dublê; guarda as threads para o teste esperar."""
    fios = []
    mesa.executor = lambda acao, pasta: fios.append(pedidos.executar_no_fundo(acao, pasta))
    return fios


def test_executar_roda_no_repo_registra_no_diario_e_volta_ao_trabalhador(mesa, acao_duble):
    diario = []
    mesa.diario = lambda *a, **k: diario.append((a, k))
    fios = _executor_real(mesa)
    p = mesa.registrar("rode o teste ao vivo")
    mesa.passo()
    mesa.despachante.estados[p["id"]]["thread_id"] = "t1"
    mesa.despachante.terminar(p["id"], arquivos=0, aplicado=False,
                              resposta="Preciso do repo real.\nEXECUTAR: duble")
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "executando"
    assert len(fios) == 1
    fios[0].join(60)
    mesa.passo()
    texto = " ".join(_pedido(mesa)["do_servidor"])
    assert "ola do repo real" in texto and "código 0" in texto
    assert "ola do repo real" not in _pedido(mesa)["texto"]
    assert [a[1] for a, _k in diario] == ["inicio", "ok"]
    assert diario[0][0][0] == "coordenador" and diario[1][1]["ref"] == p["id"]
    mesa.passo()
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
    continuacao = (mesa.despachante.pasta_da(p["id"]) / "continuacao.md").read_text(encoding="utf-8")
    assert "ola do repo real" in continuacao
    assert _pedido(mesa)["situacao"] == "trabalhando"


def test_executar_fora_da_lista_branca_e_recusado(mesa, acao_duble):
    chamadas = []
    mesa.executor = lambda *a: chamadas.append(a)
    p = mesa.registrar("rode o teste ao vivo")
    mesa.passo()
    mesa.despachante.terminar(p["id"], arquivos=0, aplicado=False,
                              resposta="EXECUTAR: rm_tudo")
    mesa.passo()
    assert chamadas == []
    notas = " ".join(_pedido(mesa)["do_servidor"])
    assert "recusou" in notas and "duble" in notas
    # argumento fora da expressao tambem
    with pytest.raises(ValueError):
        pedidos.montar_acao("duble_param", ["../../etc"])
    assert pedidos.montar_acao("duble_param", ["historia_00053"])["argv"][-1] == \
        "print('historia_00053')"


def test_executor_nunca_publica(monkeypatch):
    monkeypatch.setattr(pedidos, "ACOES_REPO", {
        "posta": {"argv": [sys.executable, "ferramentas/postar.py", "--agora"], "cwd": "."},
        "sobe": {"argv": [sys.executable, "main.py", "publicar", "h1"], "cwd": "."}})
    for nome in ("posta", "sobe"):
        with pytest.raises(ValueError, match="nunca publica"):
            pedidos.montar_acao(nome)


def test_a_lista_branca_real_nao_publica():
    for nome in pedidos.ACOES_REPO:
        acao = pedidos.montar_acao(nome, ["historia_00001"] * len(
            pedidos.ACOES_REPO[nome].get("parametros") or []))
        assert not pedidos._publica(acao["argv"])


def test_executar_espera_a_janela_da_postagem(mesa, acao_duble):
    chamadas = []
    mesa.executor = lambda acao, pasta: chamadas.append(acao["nome"])
    mesa.relogio.agora = datetime(2026, 10, 3, 17, 40)        # 17:57 - 17 min: fora
    p = mesa.registrar("rode a ação da lista branca")
    mesa.passo()
    mesa.relogio.agora = datetime(2026, 10, 3, 17, 50)        # dentro da janela do 17:57
    mesa.despachante.terminar(p["id"], arquivos=0, aplicado=False,
                              resposta="EXECUTAR: duble_janela")
    mesa.passo()
    assert chamadas == [] and "janela" in _pedido(mesa)["motivo"]
    mesa.relogio.agora = datetime(2026, 10, 3, 18, 16)
    mesa.passo()
    assert chamadas == ["duble_janela"]


def test_janela_das_postagens():
    j = pedidos.na_janela_das_postagens
    assert j(datetime(2026, 10, 5, 17, 45)) and j(datetime(2026, 10, 5, 18, 15))
    assert not j(datetime(2026, 10, 5, 17, 44)) and not j(datetime(2026, 10, 5, 18, 16))
    assert j(datetime(2026, 10, 5, 0, 25)) and j(datetime(2026, 10, 5, 0, 55))
    assert j(datetime(2026, 10, 5, 23, 55)) and not j(datetime(2026, 10, 5, 23, 59))
    assert not j(datetime(2026, 10, 5, 10, 20))


def test_execucao_que_nao_volta_vira_erro_no_diario(mesa, acao_duble):
    diario = []
    mesa.diario = lambda *a, **k: diario.append(a[1])
    mesa.executor = lambda acao, pasta: None                   # morreu sem resultado
    p = mesa.registrar("rode a ação da lista branca")
    mesa.passo()
    mesa.despachante.terminar(p["id"], arquivos=0, aplicado=False, resposta="EXECUTAR: duble")
    mesa.passo()
    mesa.relogio.andar(seconds=60 + 301)
    mesa.passo()
    assert diario == ["inicio", "erro"]
    assert "não voltou" in " ".join(_pedido(mesa)["do_servidor"])


def test_no_maximo_tres_execucoes_por_pedido(mesa, acao_duble):
    chamadas = []

    def executor(acao, pasta):
        chamadas.append(acao["nome"])
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "resultado.json").write_text('{"codigo": 0}', encoding="utf-8")
    mesa.executor = executor
    p = mesa.registrar("rode a ação da lista branca")
    mesa.passo()
    for _ in range(pedidos.MAX_EXECUCOES + 2):
        mesa.despachante.terminar(p["id"], arquivos=0, aplicado=False,
                                  resposta="EXECUTAR: duble")
        _andar(mesa, 3)
    assert len(chamadas) == pedidos.MAX_EXECUCOES


# ================================================ prompts (item 12)
def test_prompts_mandam_responder_na_mensagem_final(mesa):
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    tarefa = mesa.despachante.criados[0][2]
    assert "mensagem final" in tarefa and "NÃO crie arquivo resposta.md" in tarefa
    assert "EXECUTAR:" in tarefa and "decisao_de_produto" in tarefa
    mesa.despachante.terminar(p["id"])
    mesa.passo()
    mesa.passo()
    conferente = mesa.despachante.criados[1][2]
    assert "mensagem final" in conferente and "em resposta.md" not in conferente


def test_o_cargo_do_orquestrador_nao_manda_criar_resposta_md():
    """05/10 (conferente): o cargo dizia "deixe em `resposta.md`" e o pedido
    "NÃO crie resposta.md"; para o Codex os dois vao no mesmo pedido.md, e a
    marca escrita no arquivo se perdia."""
    cargo = (pedidos.RAIZ / ".claude" / "agents" / "orquestrador.md").read_text(encoding="utf-8")
    assert "deixe em `resposta.md`" not in cargo
    assert "MENSAGEM FINAL" in cargo and "Nao crie arquivo `resposta.md`" in cargo
    assert "vale acima de qualquer instrução antiga do cargo" in pedidos._COMO_RESPONDER
