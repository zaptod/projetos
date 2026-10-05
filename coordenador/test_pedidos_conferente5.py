# -*- coding: utf-8 -*-
"""Conferente 5 (05/10/2026): os defeitos da 3a conferencia da v2.

1. Responder em pedido de trabalhador LIMPO (ou ficha sumida) girava: um
   "recusado: ... ja foi limpa" por pulso (loop66). Agora UM trabalhador novo
   com a historia; recusado, falhou com o motivo.
2. A cobranca do DESFECHO ia ao Claude (sessao nova) sem a resposta original,
   e a resposta final virava o "Ok, conferido" da cobranca (c6).
3. O texto do servidor entrava em pedido["texto"]: "Nao refaca" tem "faca" e
   uma pergunta contratava o Codex (h1).
5. O passo segurava a trava do pedidos.json durante o `criar` (git worktree
   add): o Responder do app esperava e voltava 503.
+  Duas respostas do Grimorio no mesmo segundo: a segunda nunca rodava.
"""
from __future__ import annotations

import threading

import pytest

from coordenador import pedidos
from coordenador.test_pedidos import (ClaudeFalso, DespachanteFalso, Relogio, _andar,  # noqa: F401
                                      _pedido, mesa)
from coordenador.test_pedidos_honesto import _terminar, delegados  # noqa: F401

ANTIGA = "Tentei rodar o PicassoIA: a sessão caiu no login.\nDESFECHO: bloqueado — falta o login"
RESPOSTA_DELE = "tentei de novo pelo app, rode outra vez"


class DespLimpo(DespachanteFalso):
    """Como o `delegar` real: ficha LIMPA recusa `rodar`/`corrigir` no fundo
    (a linha "recusado:" no fundo.txt), e a ficha nao muda."""

    def __init__(self, pasta, recusa_novo=""):
        super().__init__(pasta)
        self.recusa_novo = recusa_novo

    def no_fundo(self, argv, ident):
        ficha = self.estados[ident]
        recusa = ("a tarefa " + ident + " já foi limpa" if ficha.get("limpo")
                  else self.recusa_novo if ficha.get("situacao") == "criado" and self.recusa_novo
                  else "")
        if recusa:
            self.fundos.append(list(argv))
            pasta = self.raiz / ident
            pasta.mkdir(parents=True, exist_ok=True)
            with open(pasta / "fundo.txt", "a", encoding="utf-8") as fh:
                fh.write("recusado: " + recusa + "\n")
            return 1
        return super().no_fundo(argv, ident)


@pytest.fixture
def limpa(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coord"))
    avisos = []
    m = pedidos.MesaPedidos(despachante=DespLimpo(tmp_path / "d"), claude=ClaudeFalso(),
                            relogio=Relogio(), avisar=avisos.append, uso=lambda: {})
    m.avisos = avisos
    return m


def _parado_e_limpo(m, texto="rode o teste ao vivo do PicassoIA e encha a reserva"):
    p = m.registrar(texto)
    m.passo()
    m.despachante.estados[p["id"]]["thread_id"] = "t1"
    m.despachante.terminar(p["id"], resposta=ANTIGA, arquivos=0, aplicado=False)
    m.passo()
    assert _pedido(m, p["id"])["situacao"] == "esperando_voce"
    m.despachante.estados[p["id"]]["limpo"] = {"em": "2026-10-03T11:00:00"}
    return p


# ============================================================ 1. limpo
def test_responder_em_trabalhador_limpo_contrata_um_novo_com_a_historia(limpa):
    p = _parado_e_limpo(limpa)
    limpa.registrar(RESPOSTA_DELE, responde_a=p["id"])
    _andar(limpa, 2)
    atual = _pedido(limpa, p["id"])
    assert atual["situacao"] == "trabalhando" and atual["trabalhador"] == p["id"] + "-1"
    assert atual["continuar"] is False and not pedidos._pendente(atual)
    _andar(limpa, 6)                         # muitos pulsos: nada gira
    antigos = [f for f in limpa.despachante.fundos if f[2] == p["id"]]
    assert antigos == [["rodar", "--id", p["id"]]]          # so o 1o rodar: nenhum relancamento
    novos = [c for c in limpa.despachante.criados if c[0] != p["id"]]
    assert [c[0] for c in novos] == [p["id"] + "-1"]        # UM trabalhador novo
    tarefa = novos[0][2]
    i_pedido = tarefa.index("rode o teste ao vivo do PicassoIA")
    i_resposta = tarefa.index("a sessão caiu no login")
    i_dele = tarefa.rindex(RESPOSTA_DELE)
    assert i_pedido < i_resposta < i_dele                   # texto, ultima resposta, a dele
    fundo = limpa.despachante.pasta_da(p["id"]) / "fundo.txt"
    assert not fundo.exists() or "recusado" not in fundo.read_text(encoding="utf-8")


def test_ficha_que_sumiu_tambem_vai_a_um_novo_com_a_historia(limpa):
    p = _parado_e_limpo(limpa)
    del limpa.despachante.estados[p["id"]]
    limpa.registrar(RESPOSTA_DELE, responde_a=p["id"])
    _andar(limpa, 4)
    novos = [c for c in limpa.despachante.criados if c[0] != p["id"]]
    assert [c[0] for c in novos] == [p["id"] + "-1"]
    assert RESPOSTA_DELE in novos[0][2]
    assert _pedido(limpa, p["id"])["situacao"] == "trabalhando"


def test_trabalhador_novo_recusado_ao_criar_falha_com_o_motivo(limpa):
    p = _parado_e_limpo(limpa)

    def recusa(*_a, **_k):
        raise RuntimeError("a pasta E:/projetos-wt/codex-x já existe")
    limpa.despachante.criar = recusa
    limpa.registrar(RESPOSTA_DELE, responde_a=p["id"])
    _andar(limpa, 6)
    atual = _pedido(limpa, p["id"])
    assert atual["situacao"] == "falhou" and "já existe" in atual["motivo"]
    assert "limpo" in atual["motivo"] and limpa.avisos[-1].startswith("❌")
    assert [f for f in limpa.despachante.fundos if f[2] == p["id"]] == [["rodar", "--id", p["id"]]]


def test_trabalhador_novo_recusado_no_fundo_falha_uma_vez(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coord"))
    m = pedidos.MesaPedidos(despachante=DespLimpo(tmp_path / "d"), claude=ClaudeFalso(),
                            relogio=Relogio(), avisar=lambda t: None, uso=lambda: {})
    p = _parado_e_limpo(m)
    m.despachante.recusa_novo = "a worktree sumiu: E:/projetos-wt/codex-x"
    m.registrar(RESPOSTA_DELE, responde_a=p["id"])
    _andar(m, 10)
    atual = _pedido(m, p["id"])
    assert atual["situacao"] == "falhou" and "a worktree sumiu" in atual["motivo"]
    novo = p["id"] + "-1"
    assert len([f for f in m.despachante.fundos if f[2] == novo]) == 1   # sem girar


def test_recusa_de_espera_do_novo_nao_falha(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coord"))
    m = pedidos.MesaPedidos(despachante=DespLimpo(tmp_path / "d"), claude=ClaudeFalso(),
                            relogio=Relogio(), avisar=lambda t: None, uso=lambda: {})
    p = _parado_e_limpo(m)
    m.despachante.recusa_novo = "nada começa entre :25 e :55 (agora 17:40)"
    m.registrar(RESPOSTA_DELE, responde_a=p["id"])
    _andar(m, 3)
    assert _pedido(m, p["id"])["situacao"] != "falhou"


# ============================================================ 2. cobranca
def test_cobranca_ao_claude_leva_a_original_e_a_final_e_a_original(mesa):
    original = "A causa da queda foi o disco C: cheio às 03:12; o log mostra ENOSPC."
    p = mesa.registrar("por que o servidor caiu ontem de madrugada?")
    mesa.passo()
    assert mesa.despachante.estados[p["id"]]["ia"] == "claude"
    mesa.despachante.terminar(p["id"], resposta=original, arquivos=0, aplicado=False,
                              desfecho=None)
    _andar(mesa, 3)                          # cobra, relanca e o ve rodando
    assert _pedido(mesa, p["id"])["continuar"] is False
    cont = (mesa.despachante.pasta_da(p["id"]) / "continuacao.md").read_text(encoding="utf-8")
    assert "ENOSPC" in cont and pedidos.COBRAR_DESFECHO in cont
    mesa.despachante.terminar(p["id"], resposta="Ok, conferido.\nDESFECHO: feito", arquivos=0,
                              aplicado=False)
    _andar(mesa, 2)
    atual = _pedido(mesa, p["id"])
    finais = [c["texto"] for c in mesa.para_o_app()["conversa"]
              if c["pedido"] == p["id"] and c["tipo"] == "final"]
    assert atual["situacao"] == "respondido"
    assert "ENOSPC" in finais[-1] and finais[-1].rstrip().endswith("DESFECHO: feito")
    assert "Ok, conferido" not in finais[-1] and "ENOSPC" in mesa.avisos[-1]


def test_cobranca_sem_a_linha_de_novo_mostra_a_original(mesa):
    p = mesa.registrar("por que o servidor caiu ontem?")
    mesa.passo()
    mesa.despachante.terminar(p["id"], resposta="Foi o disco: ENOSPC.", arquivos=0,
                              aplicado=False, desfecho=None)
    _andar(mesa, 3)
    mesa.despachante.terminar(p["id"], resposta="ok", arquivos=0, aplicado=False, desfecho=None)
    _andar(mesa, 2)
    assert _pedido(mesa, p["id"])["motivo"] == pedidos.SEM_DESFECHO
    guardada = next(x for x in pedidos._ler()["pedidos"] if x["id"] == p["id"])["resposta"]
    assert guardada.startswith("Foi o disco: ENOSPC.") and guardada.rstrip().endswith("ok")


def test_cobranca_sem_diff_medido_nao_perde_a_original(mesa):
    """Conferente hf1 (2b): com o diff ainda nao medido, o _encerrar espera um
    pulso; o pop da `resposta_cobrada` ja tinha acontecido e o Adrian recebia
    so "Ok, conferido.\\nDESFECHO: feito"."""
    p = _terminar(mesa, "A causa foi ENOSPC.", arquivos=0, aplicado=False, desfecho=None,
                  texto="por que caiu?")
    mesa.despachante.estados[p["id"]].update(diff=None, aplicado=None)
    _andar(mesa, 2)
    mesa.despachante.terminar(p["id"], resposta="Ok, conferido.\nDESFECHO: feito", arquivos=0,
                              aplicado=False)
    mesa.despachante.estados[p["id"]]["diff"] = None
    _andar(mesa, 5)
    atual = _pedido(mesa, p["id"])
    conversa = [c for c in mesa.para_o_app()["conversa"] if c["pedido"] == p["id"]]
    finais = [c["texto"] for c in conversa if c["tipo"] == "final"]
    # passou pela espera do diff (o pulso em que a original se perdia)
    assert any("esperando o despachante medir o diff" in c["texto"] for c in conversa)
    assert atual["situacao"] == "respondido"
    guardado = next(x for x in pedidos._ler()["pedidos"] if x["id"] == p["id"])
    assert "ENOSPC" in finais[-1] and "ENOSPC" in str(guardado["resposta"])
    assert "Ok, conferido" not in finais[-1]
    assert guardado.get("resposta_cobrada") is None


def test_executar_na_resposta_da_cobranca_nao_vira_cobranca_e_guarda_a_original(mesa):
    """A resposta da cobranca trouxe EXECUTAR: a devolucao do servidor e uma
    continuacao comum (nao a cobranca de novo), e o fim leva a original e a
    resposta nova, inteiras."""
    p = mesa.registrar("por que caiu?")
    mesa.passo()
    mesa.despachante.terminar(p["id"], resposta="A causa foi ENOSPC.", arquivos=0,
                              aplicado=False, desfecho=None)
    _andar(mesa, 3)
    mesa.despachante.terminar(p["id"], resposta="preciso rodar\nEXECUTAR: nao_existe",
                              arquivos=0, aplicado=False, desfecho=None)
    _andar(mesa, 3)
    cont = (mesa.despachante.pasta_da(p["id"]) / "continuacao.md").read_text(encoding="utf-8")
    assert "recusou `EXECUTAR: nao_existe`" in cont
    assert "A sua mensagem final foi" not in cont            # nao e a cobranca
    mesa.despachante.terminar(p["id"], resposta="Sem a ação: o disco encheu.\nDESFECHO: feito",
                              arquivos=0, aplicado=False)
    _andar(mesa, 2)
    atual = _pedido(mesa, p["id"])
    finais = [c["texto"] for c in mesa.para_o_app()["conversa"]
              if c["pedido"] == p["id"] and c["tipo"] == "final"]
    assert atual["situacao"] == "respondido"
    assert "ENOSPC" in finais[-1] and "o disco encheu" in finais[-1]
    assert finais[-1].rstrip().endswith("DESFECHO: feito")


def test_cobranca_em_trabalhador_limpo_nao_contrata_e_espera_voce(limpa):
    p = limpa.registrar("corrija o defeito X do app")
    limpa.passo()
    limpa.despachante.estados[p["id"]]["thread_id"] = "t1"
    limpa.despachante.terminar(p["id"], resposta="Fiz.", arquivos=1, aplicado=True,
                               desfecho=None)
    limpa.despachante.estados[p["id"]]["limpo"] = {"em": "x"}
    _andar(limpa, 10)
    atual = _pedido(limpa, p["id"])
    assert atual["situacao"] == "esperando_voce" and atual["motivo"] == pedidos.SEM_DESFECHO
    assert len(limpa.despachante.criados) == 1
    assert [f for f in limpa.despachante.fundos if f[0] == "corrigir"] == []


# ============================================================ 3. texto do servidor
def test_texto_do_servidor_nao_entra_no_texto_nem_escolhe_a_ia(mesa):
    p = mesa.registrar("por que o servidor caiu ontem de madrugada?")
    mesa.passo()
    mesa.despachante.terminar(p["id"], resposta="A causa foi o disco cheio.", arquivos=0,
                              aplicado=False, desfecho=None)
    mesa.passo()
    atual = next(x for x in pedidos._ler()["pedidos"] if x["id"] == p["id"])
    assert atual["texto"] == "por que o servidor caiu ontem de madrugada?"
    assert pedidos.COBRAR_DESFECHO in atual["do_servidor"]
    assert not pedidos._construir(atual["texto"])
    mesa.claude = ClaudeFalso("Claude proibido pelo Adrian")
    n = len(mesa.despachante.criados)
    _andar(mesa, 3)
    assert mesa.despachante.criados[n:] == []


# ============================================================ 5. a trava
class DespLento(DespachanteFalso):
    """O `criar` confere que a trava esta SOLTA e, no meio dele, o app (outra
    thread, como outro processo) manda o Responder."""

    def __init__(self, pasta, mesa_ref):
        super().__init__(pasta)
        self.mesa_ref, self.no_meio, self.segurando = mesa_ref, [], []

    def criar(self, ident, arquivo, permitidos, **kw):
        self.segurando.append(pedidos._TRAVA.segurando())
        resultado = []
        fio = threading.Thread(target=lambda: resultado.append(
            self.mesa_ref[0].registrar("e confira no celular também", responde_a=ident)))
        fio.start()
        fio.join(timeout=5)
        self.no_meio.append(bool(resultado))
        return super().criar(ident, arquivo, permitidos, **kw)


def test_o_criar_roda_sem_a_trava_e_o_responder_do_meio_nao_se_perde(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coord"))
    ref = []
    m = pedidos.MesaPedidos(despachante=DespLento(tmp_path / "d", ref), claude=ClaudeFalso(),
                            relogio=Relogio(), avisar=lambda t: None, uso=lambda: {})
    ref.append(m)
    p = m.registrar("corrija a tela do Agora")
    m.passo()
    assert m.despachante.segurando == [False]                # o criar nao segura a trava
    assert m.despachante.no_meio == [True]                   # o Responder entrou no meio
    atual = _pedido(m, p["id"])
    assert atual["situacao"] == "trabalhando" and "contratando" not in atual
    assert atual["continuar"] is True and pedidos._pendente(atual)
    assert "e confira no celular também" in atual["texto"]
    # a rodada acaba: a mensagem do meio vai na continuacao, ao mesmo trabalhador
    m.despachante.estados[p["id"]].update(situacao="parado", thread_id="t1")
    m.passo()
    assert m.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
    cont = (m.despachante.pasta_da(p["id"]) / "continuacao.md").read_text(encoding="utf-8")
    assert "e confira no celular também" in cont


def test_responder_durante_continuacao_em_voo_vai_na_proxima(mesa):
    p = mesa.registrar("corrija a tela do Agora")
    mesa.passo()
    mesa.despachante.estados[p["id"]]["thread_id"] = "t1"
    mesa.despachante.terminar(p["id"], resposta="Fiz a tela.\nDESFECHO: bloqueado — falta você ver",
                              arquivos=0, aplicado=False)
    mesa.passo()
    mesa.registrar("primeira", responde_a=p["id"])
    mesa.passo()                                             # corrigir com "primeira"
    mesa.registrar("segunda", responde_a=p["id"])            # ainda nao rodou
    mesa.passo()                                             # rodando: nao some
    mesa.despachante.estados[p["id"]]["situacao"] = "parado"
    _andar(mesa, 1)
    cont = (mesa.despachante.pasta_da(p["id"]) / "continuacao.md").read_text(encoding="utf-8")
    assert "segunda" in cont


def test_contratando_de_pulso_que_morreu_volta_e_tenta_de_novo(mesa):
    p = mesa.registrar("corrija a tela do Agora")
    dados = pedidos._ler()
    alvo = dados["pedidos"][0]
    alvo.update(situacao="contratando", contratando={"dono": "morto", "antes": "recebido",
                                                     "em": "2026-10-03T10:00:00"})
    pedidos._gravar(dados)
    mesa.passo()                     # 20 min depois do "em": volta a recebido
    mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    mesa.passo()
    assert _pedido(mesa, p["id"])["situacao"] == "trabalhando"
    assert [c[0] for c in mesa.despachante.criados] == [p["id"]]


def test_contratando_recente_de_outro_pulso_espera(mesa):
    p = mesa.registrar("corrija a tela do Agora")
    dados = pedidos._ler()
    dados["pedidos"][0].update(situacao="contratando", contratando={
        "dono": "outro", "antes": "recebido", "em": pedidos._iso(mesa.relogio())})
    pedidos._gravar(dados)
    mesa.passo()
    assert _pedido(mesa, p["id"])["situacao"] == "contratando" and mesa.despachante.criados == []


# ============================================================ Grimorio
def test_duas_respostas_do_grimorio_no_mesmo_segundo_rodam_as_duas(mesa, delegados):
    no = {"id": "gerente-ligado", "projeto": "geral", "titulo": "Ligar o gerente?",
          "opcoes": [{"id": "ligar", "rotulo": "Ligar", "acao_servidor": "gerente ligar"},
                     {"id": "deixar", "rotulo": "Deixar", "acao_servidor": "gerente desligar"}]}
    eventos = [{"id": "gerente-ligado", "projeto": "geral", "opcao": o, "opcao_rotulo": o,
                "em": "2026-10-05T18:00:00", "n": n, "lida": False}
               for n, o in ((1, "deixar"), (2, "ligar"))]

    def marcar(ref, gerou, nota="", origem=""):
        next(e for e in eventos if not e["lida"])["lida"] = True
    mesa.grimorio = (lambda: [dict(e) for e in eventos if not e["lida"]], marcar,
                     lambda: {"gerente-ligado": no})
    mesa.passo()
    assert all(e["lida"] for e in eventos)
    assert delegados.ler_config()["gerente_ligado"] is True       # a ultima escolha vale
