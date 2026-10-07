# -*- coding: utf-8 -*-
"""Pedido honesto v2: regras fixas, sem adivinhar por texto (05/10/2026).

O caso real: pedido-cb44cd52 ("ligar o gerente") ficou "entregue" com a
resposta "Nao foi possivel ligar"; pedido-cd2e5e0c ("arquivo no Drive")
ficou "entregue" com "Status: bloqueado so pelo login do Drive"; e "Ola
coordenador, como as coisas estao" e "Coordenador?" grudaram no cd2e5e0c.

A v1 consertou adivinhando por frases e palavras soltas, e a segunda
conferencia derrubou 24 sondas. A v2 troca o desenho:
  1. estado do servidor: so a escolha ESTRUTURADA do Grimorio (`acao_servidor`)
     roda sozinha; o `EXECUTAR` do trabalhador vira pedido de permissao;
  2. desfecho: so a ULTIMA linha `DESFECHO:` decide; sem ela, uma cobranca
     ao trabalhador e depois "esperando voce";
  3. continuacao: texto livre so em pedido ATIVO; o resto, so o Responder;
  4. relancamento recusado por espera nao gasta retomada.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from coordenador import pedidos
from coordenador.test_pedidos import (ClaudeFalso, DespachanteFalso, _andar, _pedido,  # noqa: F401
                                      mesa)

RAIZ = Path(__file__).resolve().parents[1]

# as respostas de verdade dos trabalhadores (delegados/<id>/resposta.md)
RESPOSTA_CB44 = (
    "Não foi possível ligar: a gravação atômica foi bloqueada ao abrir "
    "`%LOCALAPPDATA%\\neural-fights\\delegados\\delegar.lock`; o gerente continua desligado "
    "e não houve alteração parcial.\n\nAtualizei [`.permissao.json`](E:\\x) para pedir acesso "
    "à pasta operacional inteira.\n\nTeste: `python -m pytest coordenador/test_equipe.py -q` "
    "— 3 passaram.")
RESPOSTA_CB44_16H09 = (
    "Ainda bloqueado: a segunda tentativa recebeu o mesmo `PermissionError` em "
    "`%LOCALAPPDATA%\\neural-fights\\delegados\\delegar.lock`.\n\nA permissão precisa ser "
    "efetivamente aplicada à ACL/sandbox do processo para essa pasta; não contornei a trava "
    "escrevendo o JSON diretamente.")
RESPOSTA_CD2E = (
    "Status: bloqueado só pelo login do Drive.\n\n- [resposta.md](E:\\x) atualizado com os 3 "
    "passos para o Adrian ativar o Drive.\n\nTeste: `python -m json.tool .permissao.json` "
    "passou.\n\nFalta o Adrian abrir o Google Drive para computador, entrar na conta de 5 TB "
    "e confirmar que `G:\\Meu Drive` apareceu.")
DIFF_SO_RESPOSTA = {"arquivos": 1, "avisos": ["fora da lista (entrou): resposta.md"]}


def _terminar(mesa, resposta, **kw):
    """Um pedido novo cujo trabalhador termina com `resposta`."""
    p = mesa.registrar(kw.pop("texto", "corrija o defeito X do app"), kw.pop("origem", "app"),
                       novo=kw.pop("novo", True))
    diff = kw.pop("diff", None)
    mesa.passo()
    mesa.despachante.estados[p["id"]]["thread_id"] = "t1"
    mesa.despachante.terminar(p["id"], resposta=resposta, **kw)
    if diff is not None:
        mesa.despachante.estados[p["id"]]["diff"] = dict(diff)
    mesa.passo()
    return p


def _de_novo(mesa, p, resposta, **kw):
    """O MESMO trabalhador roda a continuacao e termina de novo (um pulso
    depois de ele estar rodando, como numa rodada de verdade)."""
    _andar(mesa, 3)
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
    assert _pedido(mesa, p["id"])["continuar"] is False
    mesa.despachante.terminar(p["id"], resposta=resposta, **kw)
    mesa.passo()


def _conversa(mesa, ident):
    return [c["texto"] for c in mesa.para_o_app()["conversa"] if c["pedido"] == ident]


# ================================================ 0. nada de frases no codigo
def test_a_adivinhacao_por_texto_saiu_do_codigo():
    """A v1 lia frases ("nao foi possivel", "falta o Adrian") e palavras soltas
    (o "gerente" no texto autorizava ligar o gerente). Nada disso volta."""
    for nome in ("autorizada_pelo_adrian", "_frases_de_bloqueio", "_BLOQUEIO_ESTADO",
                 "_BLOQUEIO_ABERTURA", "_FEITO_COM_RESSALVA", "_OBJETO_DA_ACAO", "e_continuacao",
                 "_palavras", "_COMUNS", "_INFORMA", "_AGUARDAM_RESPOSTA"):
        assert not hasattr(pedidos, nome), nome
    # o desfecho le uma linha so, e a autorizacao nao le texto do pedido
    assert "splitlines" in inspect.getsource(pedidos.ler_desfecho)
    executar = inspect.getsource(pedidos.MesaPedidos._pedir_permissao_de_estado)
    assert "texto_do_adrian" not in executar and 'pedido["texto"]' not in executar


# ================================================ 1. a linha do desfecho
@pytest.mark.parametrize("resposta, tipo, motivo", [
    ("Liguei.\nDESFECHO: feito", "feito", ""),
    ("x\nDESFECHO: bloqueado — falta o Adrian entrar no Drive", "bloqueado",
     "falta o Adrian entrar no Drive"),
    ("x\n**DESFECHO:** falhou - o teste quebrou", "falhou", "o teste quebrou"),
    ("x\n`DESFECHO: Bloqueado: login`", "bloqueado", "login"),
    ("DESFECHO: bloqueado — antes\n...resolvi.\nDESFECHO: feito", "feito", ""),
    ("Pronto.\nDESFECHO: feito\n```\n\n", "feito", ""),        # a cerca do bloco nao conta
    ("A causa era o disco cheio.\nDESFECHO: feito — sem ressalvas", "feito", ""),
    ("x\nDESFECHO: bloqueado — falta o login A | e o B", "bloqueado", "falta o login A | e o B"),
])
def test_a_ultima_linha_e_o_desfecho(resposta, tipo, motivo):
    lido = pedidos.ler_desfecho(resposta)
    assert (lido["tipo"], lido["motivo"], lido["fonte"]) == (tipo, motivo, "linha")


@pytest.mark.parametrize("resposta", [
    "", "   \n", "consertei X e os testes passaram", RESPOSTA_CB44, RESPOSTA_CD2E,
    RESPOSTA_CB44_16H09,
    "DESFECHO: feito\nmas ainda falta o teste",                # nao e a ultima linha
    "Exemplo do formato: DESFECHO: feito, e segui.",           # nao e a linha inteira
    # conferente 3 (c2): o FORMATO colado nao declara nada
    "x\nDESFECHO: feito | bloqueado — ... | falhou — ...",
    "x\nDESFECHO: feito|bloqueado|falhou",
    "x\n`DESFECHO: feito` / `DESFECHO: bloqueado — <o que falta e quem faz>`",
    "x\nDESFECHO: bloqueado — <o que falta e quem faz>",
    "x\nDESFECHO: falhou — <motivo>",
])
def test_sem_a_linha_nada_e_adivinhado(resposta):
    assert pedidos.ler_desfecho(resposta) == {"tipo": None, "motivo": "", "fonte": "sem_linha"}


@pytest.mark.parametrize("resposta, situacao", [
    # vale a LINHA, e so ela: o texto de cima nao muda o desfecho
    ("Ainda bloqueado: o PermissionError continua.\nDESFECHO: feito", "respondido"),
    ("Não liguei o gerente.\nDESFECHO: feito", "respondido"),
    ("Respondi a pergunta.\nDESFECHO: feito — nada pendente", "respondido"),
    ("Corrigi tudo e passou.\nDESFECHO: bloqueado — falta o Adrian testar no celular",
     "esperando_voce"),
    ("Tentei.\nDESFECHO: falhou — o config está ilegível", "falhou"),
])
def test_vale_a_linha(mesa, resposta, situacao):
    _terminar(mesa, resposta, arquivos=0, aplicado=False, texto="por que caiu o serviço do app ontem?")
    assert _pedido(mesa)["situacao"] == situacao


def test_bloqueado_espera_voce_com_o_texto_da_linha_e_nao_gira(mesa):
    p = _terminar(mesa, "Fiz os passos.\nDESFECHO: bloqueado — falta o Adrian entrar no Drive",
                  arquivos=0, aplicado=False)
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando_voce"
    assert atual["motivo"] == "bloqueado: falta o Adrian entrar no Drive"
    assert "falta o Adrian entrar no Drive" in mesa.avisos[-1]
    assert "Responder" in mesa.avisos[-1]
    _andar(mesa, pedidos.MAX_RETOMADAS + 2)
    assert _pedido(mesa)["situacao"] == "esperando_voce"       # nao relanca, nao queima
    assert mesa.despachante.fundos == [["rodar", "--id", p["id"]]]


def test_falhou_vira_falhou_com_o_motivo(mesa):
    _terminar(mesa, "Tentei.\nDESFECHO: falhou — o config está ilegível", arquivos=0,
              aplicado=False)
    atual = _pedido(mesa)
    assert atual["situacao"] == "falhou" and atual["motivo"] == "o config está ilegível"
    assert mesa.avisos[-1].startswith("❌")


def test_feito_com_codigo_entregue_e_sem_codigo_respondido(mesa):
    _terminar(mesa, "Consertei.\nDESFECHO: feito", aplicado=False)
    assert _pedido(mesa)["situacao"] == "entregue"
    _terminar(mesa, "A causa é o disco.\nDESFECHO: feito", arquivos=0, aplicado=False,
              texto="por que caiu o serviço do app ontem?")
    assert _pedido(mesa)["situacao"] == "respondido"
    # o cb44: o "1 arquivo" do diff era o rascunho resposta.md
    _terminar(mesa, "Só respondi.\nDESFECHO: feito", aplicado=False, diff=DIFF_SO_RESPOSTA)
    assert _pedido(mesa)["situacao"] == "respondido"


def test_sem_a_linha_uma_cobranca_ao_mesmo_trabalhador_e_depois_espera_voce(mesa):
    p = _terminar(mesa, RESPOSTA_CB44, aplicado=False, diff=DIFF_SO_RESPOSTA, desfecho=None,
                  texto="ligue o gerente da equipe")
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando" and atual["continuar"] is True   # nunca "entregue"
    assert any("sem a linha DESFECHO" in t for t in _conversa(mesa, p["id"]))
    _andar(mesa, 2)
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
    cobranca = (mesa.despachante.pasta_da(p["id"]) / "continuacao.md").read_text(encoding="utf-8")
    assert pedidos.COBRAR_DESFECHO in cobranca
    # esqueceu de novo: para e espera o Adrian ler -- sem segunda cobranca
    mesa.despachante.terminar(p["id"], resposta=RESPOSTA_CB44_16H09, arquivos=0,
                              aplicado=False, desfecho=None)
    mesa.passo()
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando_voce" and atual["motivo"] == pedidos.SEM_DESFECHO
    assert atual["motivo"] == "o trabalhador não declarou o desfecho — leia a resposta"
    assert mesa.despachante.fundos.count(["corrigir", "--id", p["id"],
                                          "--texto", mesa.despachante.fundos[-1][-1]]) == 1
    _andar(mesa, 4)
    assert _pedido(mesa)["situacao"] == "esperando_voce"


def test_a_cobranca_com_a_linha_segue_pela_linha(mesa):
    p = _terminar(mesa, RESPOSTA_CD2E, arquivos=0, aplicado=False, desfecho=None)
    _de_novo(mesa, p, "Falta o login.\nDESFECHO: bloqueado — falta o Adrian entrar no Drive",
             arquivos=0, aplicado=False)
    assert _pedido(mesa)["motivo"] == "bloqueado: falta o Adrian entrar no Drive"


def test_caso_zero_resposta_vazia_e_cobrada_e_nunca_entregue(mesa):
    p = _terminar(mesa, "", arquivos=1, aplicado=False, desfecho=None)
    assert _pedido(mesa)["situacao"] != "entregue"
    _de_novo(mesa, p, "", arquivos=1, aplicado=False, desfecho=None)
    assert _pedido(mesa)["situacao"] == "esperando_voce"


def test_sem_a_linha_com_a_entrega_ja_aplicada_cobra_o_mesmo_sem_contratar(mesa):
    """Conferente 4 (05/10/2026): aplicada e sem a linha, ia DIRETO a esperando
    voce, sem a unica cobranca que a regra pede. Agora a cobranca vai ao MESMO
    trabalhador (nunca um novo, que refaria tudo so pela linha), com a resposta
    dele e o aviso de nao mudar nada; a linha que voltar decide."""
    p = _terminar(mesa, "Consertei o X.", desfecho=None)   # aplicado=True (o vigia ja aplicou)
    assert _pedido(mesa)["situacao"] == "esperando" and _pedido(mesa)["continuar"] is True
    _de_novo(mesa, p, "Consertei o X.\nDESFECHO: feito")
    continuacao = (mesa.despachante.pasta_da(p["id"]) / "continuacao.md").read_text(encoding="utf-8")
    assert "NÃO mude arquivo nenhum" in continuacao and "Consertei o X." in continuacao
    assert "DESFECHO: feito" in continuacao                # a cobranca vai no fim
    assert len(mesa.despachante.criados) == 1              # ninguem novo
    atual = _pedido(mesa)
    assert atual["situacao"] == "entregue" and not atual.get("so_desfecho")


def test_sem_a_linha_aplicada_faltou_de_novo_espera_voce(mesa):
    p = _terminar(mesa, "Consertei.", desfecho=None)
    _de_novo(mesa, p, "Consertei de novo.", desfecho=None)
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando_voce" and atual["motivo"] == pedidos.SEM_DESFECHO
    assert len(mesa.despachante.criados) == 1
    cobrancas = [f for f in mesa.despachante.fundos if f[0] == "corrigir"]
    assert len(cobrancas) == 1


def test_sem_a_linha_aplicada_codex_sem_conversa_nao_refaz_a_tarefa(mesa):
    """Codex sem thread so teria o `rodar` (a tarefa inteira de novo): nao cobra."""
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    mesa.despachante.estados[p["id"]].update(ia="codex", thread_id=None)
    mesa.despachante.terminar(p["id"], resposta="Consertei.", desfecho=None)
    _andar(mesa, 3)
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando_voce" and atual["motivo"] == pedidos.SEM_DESFECHO
    assert not [f for f in mesa.despachante.fundos if f[0] in ("corrigir", "rodar")][1:]


def test_a_resposta_do_adrian_zera_a_cobranca(mesa):
    p = _terminar(mesa, "x", arquivos=0, aplicado=False, desfecho=None)
    _de_novo(mesa, p, "y", arquivos=0, aplicado=False, desfecho=None)
    assert _pedido(mesa)["situacao"] == "esperando_voce"
    mesa.registrar("faça Z", responde_a=p["id"])
    _de_novo(mesa, p, "fiz Z", arquivos=0, aplicado=False, desfecho=None)
    assert _pedido(mesa)["situacao"] == "esperando"          # cobrou de novo, uma vez
    assert _pedido(mesa)["continuar"] is True


def test_o_prompt_pede_a_linha_e_explica_a_permissao(mesa):
    mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    tarefa = mesa.despachante.criados[0][2]
    for linha in ("DESFECHO: feito", "DESFECHO: bloqueado", "DESFECHO: falhou"):
        assert linha in tarefa
    assert "lê SÓ essa linha" in tarefa
    assert "EXECUTAR: gerente <ligar|desligar>" in tarefa
    assert "pedido de permissão ao Adrian" in tarefa and "NÃO executa sozinho" in tarefa
    assert "Só vale se o ADRIAN pediu" not in tarefa
    assert "EXECUTAR: historias_auto" in tarefa                 # a do repositorio continua


# ================================================ arquivos de codigo
def test_arquivos_de_codigo_nunca_conta_o_rascunho():
    assert pedidos.arquivos_de_codigo({"aplicado": {"arquivos": ["resposta.md"]}}) == 0
    assert pedidos.arquivos_de_codigo({"aplicado": {"arquivos": [
        "resposta.md", ".permissao.json", "remoto/x.py"]}}) == 1
    assert pedidos.arquivos_de_codigo({"aplicado": {"arquivos": ["a\\resposta.md"]}}) == 0
    assert pedidos.arquivos_de_codigo({"aplicado": {"arquivos": []}}) == 0
    assert pedidos.arquivos_de_codigo({"diff": DIFF_SO_RESPOSTA}) == 0          # o cb44 real
    assert pedidos.arquivos_de_codigo({"diff": {"arquivos": [
        {"caminho": "resposta.md"}, {"caminho": ".permissao.json"},
        {"caminho": "remoto/x.py"}]}}) == 1
    assert pedidos.arquivos_de_codigo({"diff": {"arquivos": 2}}) == 2
    assert pedidos.arquivos_de_codigo({"aplicado": {"arquivos": ["remoto/x.py"]}}) == 1
    assert pedidos.arquivos_de_codigo({}) == 0                                  # caso zero
    assert pedidos.arquivos_de_codigo(None) == 0


def test_aplicado_so_com_o_rascunho_nao_vira_entregue(mesa):
    p = mesa.registrar("ligue o gerente da equipe")
    mesa.passo()
    mesa.despachante.terminar(p["id"], resposta="Só respondi.\nDESFECHO: feito")
    mesa.despachante.estados[p["id"]].update(diff=dict(DIFF_SO_RESPOSTA),
                                             aplicado={"arquivos": ["resposta.md"]})
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "respondido"


def test_feito_com_diff_vazio_e_respondido(mesa):
    """Conferente 3 (c4): diff {} virava "entregue" para sempre."""
    p = mesa.registrar("explique o erro X")
    mesa.passo()
    mesa.despachante.terminar(p["id"], resposta="Explicado.\nDESFECHO: feito", arquivos=0,
                              aplicado=False)
    mesa.despachante.estados[p["id"]]["diff"] = {}
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "respondido"


def test_feito_sem_diff_medido_espera_o_despachante_e_depois_responde(mesa):
    """O delegar mede o diff logo depois de terminar; sem medida (a worktree
    sumiu), o pedido nao fica "entregue" sem nada para o vigia aplicar."""
    p = mesa.registrar("explique o erro X")
    mesa.passo()
    mesa.despachante.terminar(p["id"], resposta="Explicado.\nDESFECHO: feito", arquivos=0,
                              aplicado=False)
    mesa.despachante.estados[p["id"]]["diff"] = None
    mesa.passo()
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando" and "medir o diff" in atual["motivo"]
    mesa.despachante.estados[p["id"]]["diff"] = {"arquivos": 1}      # mediu: tem codigo
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "entregue" and "sem_diff_desde" not in _pedido(mesa)
    q = mesa.registrar("explique o erro Y")
    mesa.passo()
    mesa.despachante.terminar(q["id"], resposta="Explicado.\nDESFECHO: feito", arquivos=0,
                              aplicado=False)
    mesa.despachante.estados[q["id"]]["diff"] = None
    mesa.passo()
    mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    mesa.passo()
    assert _pedido(mesa, q["id"])["situacao"] == "respondido"
    assert any("não mediu o diff" in c["texto"] for c in mesa.para_o_app()["conversa"]
               if c["pedido"] == q["id"])


# ================================================ 2. estado do servidor
@pytest.fixture
def delegados(tmp_path, monkeypatch):
    """O config da equipe numa pasta temporaria (nunca o LOCALAPPDATA real)."""
    from remoto import delegar
    monkeypatch.setattr(delegar, "PASTA", None)
    monkeypatch.setenv("NF_DELEGADOS_PASTA", str(tmp_path / "delegados_cfg"))
    assert delegar.pasta() == tmp_path / "delegados_cfg"
    return delegar


def _pediu_executar(mesa, resposta="A worktree não grava o config.\nEXECUTAR: gerente ligar",
                    **kw):
    kw.setdefault("arquivos", 0)
    kw.setdefault("aplicado", False)
    return _terminar(mesa, resposta, **kw)


def test_executar_do_trabalhador_vira_pedido_de_permissao_e_nao_roda(mesa, delegados):
    mesa.executor = lambda *a: pytest.fail("acao do servidor nao vai ao executor")
    p = _pediu_executar(mesa, texto="ligue o gerente da equipe")
    assert delegados.ler_config()["gerente_ligado"] is False          # nada rodou
    ficha = mesa.despachante.estados[p["id"]]
    assert ficha["situacao"] == "aguardando_permissao"
    pp = ficha["pedido_permissao"]
    assert (pp["categoria"], pp["alvo"]) == ("estado_do_servidor", "gerente ligar")
    assert pp["situacao_antes"] == "terminou"
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando_voce" and "Pedidos de permissão" in atual["motivo"]
    assert atual["permissao_estado"]["comando"] == "gerente ligar"
    _andar(mesa, pedidos.MAX_RETOMADAS + 2)                           # espera, sem girar
    assert _pedido(mesa)["situacao"] == "esperando_voce"
    assert delegados.ler_config()["gerente_ligado"] is False
    assert mesa.despachante.fundos == [["rodar", "--id", p["id"]]]


def test_aprovado_o_servidor_executa_confere_e_responde(mesa, delegados):
    diario = []
    mesa.diario = lambda *a, **k: diario.append(a[1])
    p = _pediu_executar(mesa, texto="ligue o gerente da equipe")
    mesa.despachante.decidir_permissao(p["id"], True)                 # o Adrian, no app
    mesa.passo()
    assert delegados.ler_config()["gerente_ligado"] is True
    atual = _pedido(mesa)
    assert atual["situacao"] == "respondido" and atual["desfecho"]["fonte"] == "servidor"
    assert "LIGADO" in mesa.avisos[-1] and "relido" in mesa.avisos[-1]
    assert diario == ["pedido", "inicio", "ok"]
    assert atual["execucoes_feitas"][-1]["desfecho"].startswith("conferido")
    assert len(mesa.despachante.fundos) == 1          # o trabalhador nao e relancado
    assert not atual.get("permissao_estado")
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "respondido"                  # nao executa de novo


def test_negado_nada_muda(mesa, delegados):
    p = _pediu_executar(mesa, texto="ligue o gerente da equipe")
    mesa.despachante.decidir_permissao(p["id"], False)
    mesa.passo()
    assert delegados.ler_config()["gerente_ligado"] is False
    assert _pedido(mesa)["situacao"] == "respondido"
    assert "você negou `gerente ligar`" in _conversa(mesa, p["id"])[-1]
    assert len(mesa.despachante.fundos) == 1


def test_aprovado_com_codigo_ainda_passa_pelo_vigia(mesa, delegados):
    p = _pediu_executar(mesa, "Mudei a tela.\nEXECUTAR: gerente ligar", arquivos=1,
                        texto="mude a tela e ligue o gerente")
    mesa.despachante.decidir_permissao(p["id"], True)
    mesa.passo()
    assert delegados.ler_config()["gerente_ligado"] is True
    assert _pedido(mesa)["situacao"] == "entregue"
    assert mesa.despachante.estados[p["id"]]["situacao"] == "terminou"   # o vigia aplica


def test_aprovado_que_nao_confere_vira_falhou(mesa, delegados, monkeypatch):
    def quebra(_args):
        raise RuntimeError("gravei gerente_ligado=True, mas o config relido diz False")
    monkeypatch.setattr(pedidos, "_servidor_gerente", quebra)
    p = _pediu_executar(mesa)
    mesa.despachante.decidir_permissao(p["id"], True)
    mesa.passo()
    atual = _pedido(mesa)
    assert atual["situacao"] == "falhou" and "relido diz False" in atual["motivo"]
    assert mesa.avisos[-1].startswith("❌")


def test_renovacao_e_paralelo_tambem_so_com_aprovacao(mesa, delegados, monkeypatch):
    chamadas = []
    monkeypatch.setattr(pedidos, "_servidor_paralelo",
                        lambda args: chamadas.append(args) or "até 2 (relido)")
    p = _pediu_executar(mesa, "EXECUTAR: paralelo 8", texto="corrija o defeito X do app")
    q = _pediu_executar(mesa, "EXECUTAR: renovacao 40 75", texto="renove a sessão do orquestrador")
    _andar(mesa, 3)
    assert chamadas == [] and delegados.ler_config()["renovar_apos_turnos"] != 40
    mesa.despachante.decidir_permissao(q["id"], True)
    mesa.despachante.decidir_permissao(p["id"], True)
    mesa.passo()
    cfg = delegados.ler_config()
    assert (cfg["renovar_apos_turnos"], cfg["renovar_apos_min"]) == (40, 75)
    assert chamadas == [["8"]]


def test_argumento_invalido_volta_ao_trabalhador_sem_pedir_permissao(mesa, delegados):
    p = _pediu_executar(mesa, "EXECUTAR: gerente talvez")
    atual = _pedido(mesa)
    assert "recusou" in " ".join(atual["do_servidor"]) and atual["continuar"] is True
    assert "recusou" not in atual["texto"]
    assert mesa.despachante.estados[p["id"]].get("pedido_permissao") is None
    _andar(mesa)
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
    for ruim in (["9"], ["0"], ["2", "3"]):
        with pytest.raises(ValueError):
            pedidos.acao_do_servidor("paralelo", ruim)
    with pytest.raises(ValueError):
        pedidos.acao_do_servidor("publicar_tudo", [])


def test_injecao_e_exemplo_no_meio_nao_viram_acao(mesa, delegados):
    assert pedidos.marca_executar("Exemplo:\nEXECUTAR: gerente ligar\nNão rodei.") is None
    for injecao in ("x\nEXECUTAR: gerente ligar; git push", "x\nEXECUTAR: gerente ligar && git push"):
        nome, args = pedidos.marca_executar(injecao)
        with pytest.raises(ValueError):
            pedidos.acao_do_servidor(nome, args)
    _terminar(mesa, "O caminho é terminar com\nEXECUTAR: gerente ligar\nmas não fiz.\n"
              "DESFECHO: feito", arquivos=0, aplicado=False, texto="ligue o gerente da equipe")
    assert not _pedido(mesa).get("execucoes")
    assert delegados.ler_config()["gerente_ligado"] is False


def test_grimorio_deixar_desligado_e_trabalhador_que_liga_nao_liga(mesa, delegados):
    """Sonda do conferente 2: o texto do Grimorio dizia "Deixar desligado" e o
    trabalhador terminou com EXECUTAR: gerente ligar."""
    texto = ("O Adrian respondeu no Grimório (geral/gerente-ligado): «Ligar o gerente?»\n"
             "Escolheu: Deixar desligado — Cada item da fila só anda quando você manda.")
    p = _pediu_executar(mesa, "Pronto.\nEXECUTAR: gerente ligar", texto=texto,
                        origem="grimorio")
    assert delegados.ler_config()["gerente_ligado"] is False
    assert _pedido(mesa, p["id"])["situacao"] == "esperando_voce"


@pytest.mark.parametrize("texto", ["sim, pode ligar", "não precisa ligar, só me explique"])
def test_responder_com_permissao_pendente_e_recusado(mesa, delegados, texto):
    """Conferente 3 (defeito 7): o Responder NEGAVA a permissao pendente, e
    "sim, pode ligar" nao ligava nada. Texto nao aprova nem nega: a rota
    recusa e o cartao mostra Permitir/Negar; a permissao segue pendente."""
    p = _pediu_executar(mesa, texto="ligue o gerente da equipe")
    with pytest.raises(ValueError, match="Permitir ou Negar"):
        mesa.registrar(texto, responde_a=p["id"])
    mesa.passo()
    assert mesa.despachante.decisoes == []
    assert delegados.ler_config()["gerente_ligado"] is False
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando_voce" and atual["permissao_estado"]["comando"] == \
        "gerente ligar"
    assert texto not in atual["texto"]
    # decidida (Permitir no cartao), o Responder volta a valer
    mesa.despachante.decidir_permissao(p["id"], False)
    mesa.passo()
    assert mesa.registrar("entendi", responde_a=p["id"])["id"] == p["id"]


def test_reabrir_nega_a_permissao_pendente(mesa, delegados):
    p = _pediu_executar(mesa)
    mesa.reabrir(p["id"], "reaberto pelo orquestrador")
    assert mesa.despachante.decisoes == [(p["id"], False)]
    assert delegados.ler_config()["gerente_ligado"] is False
    assert _pedido(mesa)["situacao"] == "esperando" and not _pedido(mesa).get("permissao_estado")


def test_as_acoes_do_servidor_nao_publicam():
    for nome, acao in pedidos.ACOES_SERVIDOR.items():
        assert not pedidos._publica([nome, acao["fazer"], acao["o_que"]])
        assert callable(getattr(pedidos, acao["fazer"]))


# ------------------------------------------------ o delegar de verdade
def _ficha_real(delegar, ident, cargo="orquestrador", situacao="terminou"):
    pasta = delegar.pasta_da(ident)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "estado.json").write_text(json.dumps({
        "id": ident, "situacao": situacao, "cargo": cargo, "ia": "claude",
        "worktree": str(pasta / "wt")}), encoding="utf-8")


def test_delegar_estado_do_servidor_e_sempre_com_o_adrian(delegados):
    d = delegados
    assert d.ESTADO_DO_SERVIDOR == pedidos.CATEGORIA_ESTADO
    assert d.regra_de_permissao("orquestrador", "estado_do_servidor") == "perguntar_ao_adrian"
    # o "*" do jogo-zombie (gerente_aceita) nao alcanca o estado do servidor
    assert d.regra_de_permissao("jogo-zombie", "estado_do_servidor") == "perguntar_ao_adrian"
    with pytest.raises(d.Recusa):
        d.gravar_permissoes({"regras": {**d.ler_permissoes()["regras"],
                                        "estado_do_servidor": "gerente_aceita"}})
    with pytest.raises(d.Recusa):
        d.gravar_permissoes({"cargos": {"orquestrador": {"estado_do_servidor": "gerente_aceita"}}})
    d.gravar_permissoes({"regras": {**d.ler_permissoes()["regras"],
                                    "estado_do_servidor": "negar"}})
    assert d.regra_de_permissao("orquestrador", "estado_do_servidor") == "negar"


def test_delegar_aprovar_estado_nao_relanca_e_registra_a_decisao(delegados):
    d = delegados
    _ficha_real(d, "pedido-aaaa0001")
    d.registrar_pedido_permissao("pedido-aaaa0001", {
        "o_que": "o servidor executar `gerente ligar`", "categoria": "estado_do_servidor",
        "por_que": "teste", "alvo": "gerente ligar"})
    ficha = d.ler_estado("pedido-aaaa0001")
    assert ficha["situacao"] == "aguardando_permissao"
    assert ficha["pedido_permissao"]["situacao_antes"] == "terminou"
    ficha = d.decidir_permissao("pedido-aaaa0001", True, sempre=True)
    # volta ao que era (nao "criado": o app e o gerente so relancam "criado")
    assert ficha["situacao"] == "terminou" and ficha["pedido_permissao"] is None
    assert ficha["permissoes"][-1]["decisao"] == "permitir"
    assert ficha["permissoes"][-1]["pedido"]["alvo"] == "gerente ligar"
    # "Permitir sempre" nao vale para o estado do servidor
    assert "estado_do_servidor" not in (d.ler_permissoes()["cargos"].get("orquestrador") or {})


def test_o_trabalhador_nao_pede_estado_do_servidor_pelo_arquivo(delegados):
    d = delegados
    _ficha_real(d, "pedido-aaaa0002")
    wt = d.pasta_da("pedido-aaaa0002") / "wt"
    wt.mkdir(parents=True)
    (wt / ".permissao.json").write_text(json.dumps({
        "o_que": "ligar o gerente", "categoria": "estado_do_servidor", "por_que": "x",
        "alvo": "gerente ligar"}), encoding="utf-8")
    assert d.pedido_de_permissao("pedido-aaaa0002") is None


def test_o_gerente_nunca_aceita_estado_do_servidor():
    from coordenador import equipe

    class Desp:
        def __init__(self):
            self.decididos, self.fundos = [], []

        def ler_config(self):
            return {"gerente_ligado": True}

        def listar(self):
            return [{"id": "t1", "situacao": "aguardando_permissao", "cargo": "jogo-zombie",
                     "pedido_permissao": {"categoria": "estado_do_servidor", "o_que": "x",
                                          "por_que": "y", "alvo": "gerente ligar"}}]

        def regra_de_permissao(self, *_a):
            return "gerente_aceita"           # mesmo que a politica mentisse

        def decidir_permissao(self, ident, permitir):
            self.decididos.append((ident, permitir))

        def no_fundo(self, argv, ident):
            self.fundos.append(argv)

    desp, avisos = Desp(), []
    g = equipe.GerenteEquipe(mesa=None, despachante=desp, avisar=avisos.append)
    g._permissoes_pendentes(True)
    assert desp.decididos == [] and desp.fundos == []      # vira pergunta ao Adrian
    assert len(avisos) == 1 and avisos[0].startswith("❓ permissao de t1")


def test_permissao_de_estado_avisa_o_adrian_com_o_id_do_pedido(mesa, delegados):
    """Conferente 3 (b1): sem aviso, o Adrian so via a permissao abrindo o app."""
    p = _pediu_executar(mesa, texto="ligue o gerente da equipe")
    avisos = [a for a in mesa.avisos if "permissão" in a]
    assert len(avisos) == 1
    assert p["id"] in avisos[0] and "gerente ligar" in avisos[0] and "Permitir" in avisos[0]
    assert "ligue o gerente da equipe" in avisos[0]                       # diz DE QUAL pedido
    _andar(mesa, 4)
    assert len([a for a in mesa.avisos if "permissão" in a]) == 1          # nao repete
    # o gerente da equipe nao manda o mesmo aviso de novo
    pp = mesa.despachante.estados[p["id"]]["pedido_permissao"]
    assert pp["avisado"] == "coordenador"


class _DespPermissoes:
    def __init__(self):
        self.fichas = [{"id": "pedido-cb44cd52-1", "cargo": "orquestrador",
                        "situacao": "aguardando_permissao",
                        "pedido_permissao": {"categoria": "caminho_protegido", "o_que": "pasta",
                                             "alvo": "x", "em": "2026-10-05T10:00:00"}}]

    def listar(self):
        return self.fichas

    def regra_de_permissao(self, *_a):
        return "perguntar_ao_adrian"

    def ler_config(self):
        return {"gerente_ligado": False}


def test_gerente_avisa_a_segunda_permissao_do_mesmo_trabalhador():
    """Conferente 3 (b2): o aviso era deduplicado pelo id do TRABALHADOR para
    sempre; a segunda permissao do pedido-cb44cd52-1 nao avisava."""
    from coordenador import equipe
    d, avisos = _DespPermissoes(), []
    g = equipe.GerenteEquipe(mesa=None, despachante=d, avisar=avisos.append)
    g._permissoes_pendentes(False)
    g._permissoes_pendentes(False)
    assert len(avisos) == 1                                     # a mesma nao repete
    d.fichas[0].update(situacao="terminou", pedido_permissao=None)
    g._permissoes_pendentes(False)
    d.fichas[0].update(situacao="aguardando_permissao", pedido_permissao={
        "categoria": "estado_do_servidor", "o_que": "o servidor executar `gerente ligar`",
        "alvo": "gerente ligar", "em": "2026-10-05T11:00:00"})
    g._permissoes_pendentes(False)
    assert len(avisos) == 2 and "gerente ligar" in avisos[1]
    # negada e pedida de novo (mesmo alvo, hora nova): avisa de novo
    d.fichas[0]["pedido_permissao"] = dict(d.fichas[0]["pedido_permissao"], em="2026-10-05T12:00:00")
    g._permissoes_pendentes(False)
    assert len(avisos) == 3
    # a que o coordenador ja avisou (com o id do pedido) o gerente nao repete
    d.fichas[0]["pedido_permissao"] = dict(d.fichas[0]["pedido_permissao"], em="2026-10-05T13:00:00",
                                           avisado="coordenador")
    g._permissoes_pendentes(False)
    assert len(avisos) == 3
    assert len(g.estado["permissoes"]) == 1                     # a memoria nao cresce


def test_delegar_guarda_quem_avisou(delegados):
    _ficha_real(delegados, "pedido-aaaaaaaa")
    ficha = delegados.registrar_pedido_permissao("pedido-aaaaaaaa", {
        "o_que": "o servidor executar `gerente ligar`", "categoria": "estado_do_servidor",
        "por_que": "x", "alvo": "gerente ligar", "avisado": "coordenador"})
    assert ficha["pedido_permissao"]["avisado"] == "coordenador"
    _ficha_real(delegados, "pedido-bbbbbbbb")
    ficha = delegados.registrar_pedido_permissao("pedido-bbbbbbbb", {
        "o_que": "a", "categoria": "caminho_protegido", "por_que": "b", "alvo": "c"})
    assert "avisado" not in ficha["pedido_permissao"]


# ================================================ 1b. a escolha do Grimorio
class Grimorio:
    """leitor/marcar/carregar de mentira, com um no e as respostas dele."""

    def __init__(self, opcoes, falha_marcar=False):
        self.no = {"id": "gerente-ligado", "projeto": "geral", "titulo": "Ligar o gerente?",
                   "pergunta": "O gerente pode tocar a fila?", "contexto": "contrata em paralelo",
                   "opcoes": opcoes}
        self.eventos, self.marcados, self.falha_marcar = [], [], falha_marcar

    def responder(self, opcao, em="2026-10-03T10:00:00"):
        rotulo = next(o["rotulo"] for o in self.no["opcoes"] if o["id"] == opcao)
        self.eventos.append({"id": "gerente-ligado", "projeto": "geral", "opcao": opcao,
                             "opcao_rotulo": rotulo, "em": em, "lida": False,
                             "titulo": self.no["titulo"]})

    def leitor(self):
        return list(self.eventos)

    def marcar(self, ref, gerou, nota="", origem=""):
        if self.falha_marcar:
            raise OSError("decisoes ocupadas")
        self.marcados.append((ref, gerou, nota))
        for ev in self.eventos:
            ev["lida"] = True

    def carregar(self):
        return {"gerente-ligado": self.no}

    def ligar(self, mesa):
        mesa.grimorio = (self.leitor, self.marcar, self.carregar)
        return self


OPCOES_GERENTE = [
    {"id": "ligar", "rotulo": "Ligar (recomendado)", "descricao": "A fila anda.",
     "acao_servidor": "gerente ligar"},
    {"id": "deixar", "rotulo": "Deixar desligado", "descricao": "Só quando você manda.",
     "acao_servidor": "gerente desligar"}]


def test_escolha_com_acao_servidor_executa_na_hora_sem_trabalhador(mesa, delegados):
    g = Grimorio(OPCOES_GERENTE).ligar(mesa)
    g.responder("ligar")
    mesa.passo()
    assert delegados.ler_config()["gerente_ligado"] is True
    assert mesa.despachante.criados == [] and mesa.despachante.fundos == []
    atual = _pedido(mesa)
    assert atual["situacao"] == "respondido" and atual["origem"] == "grimorio"
    assert "relido" in _conversa(mesa, atual["id"])[-1]
    assert atual["grimorio_acao"] == "gerente ligar"
    assert g.marcados and g.marcados[0][1] == [f"tarefa:{atual['id']}"]
    assert "executou `gerente ligar`" in g.marcados[0][2]
    assert mesa.avisos[-1].startswith("🧭 Grimório (geral/gerente-ligado)")
    mesa.passo()
    assert len(mesa.para_o_app()["pedidos"]) == 1                    # lida: nao repete


def test_deixar_desligado_desliga_mesmo_com_o_contexto_falando_de_paralelo(mesa, delegados):
    delegados.gravar_config({"gerente_ligado": True})
    Grimorio(OPCOES_GERENTE).ligar(mesa).responder("deixar")
    mesa.passo()
    assert delegados.ler_config()["gerente_ligado"] is False
    assert delegados.ler_config()["delegados_paralelo"] == 1


def test_opcao_sem_acao_e_sem_origem_nao_vira_pedido(mesa, delegados):
    # Uma porta so (07/10/2026): resposta sem pedido de origem nao contrata ninguem.
    opcoes = [dict(o) for o in OPCOES_GERENTE]
    opcoes[0].pop("acao_servidor")
    Grimorio(opcoes).ligar(mesa).responder("ligar")
    mesa.passo()
    assert delegados.ler_config()["gerente_ligado"] is False
    assert len(mesa.despachante.criados) == 0


def test_acao_invalida_no_no_falha_sem_rodar(mesa, delegados):
    opcoes = [dict(OPCOES_GERENTE[0], acao_servidor="paralelo 99")]
    Grimorio(opcoes).ligar(mesa).responder("ligar")
    mesa.passo()
    atual = _pedido(mesa)
    assert atual["situacao"] == "falhou" and "não vale" in atual["motivo"]
    assert mesa.avisos[-1].startswith("❌")


def test_mesma_resposta_nao_roda_duas_vezes_se_marcar_falha(mesa, delegados, monkeypatch):
    vezes = []
    original = pedidos._servidor_gerente
    monkeypatch.setattr(pedidos, "_servidor_gerente",
                        lambda args: vezes.append(args) or original(args))
    g = Grimorio(OPCOES_GERENTE, falha_marcar=True).ligar(mesa)
    g.responder("ligar")
    mesa.passo()
    mesa.passo()
    assert vezes == [["ligar"]]
    assert any("não consegui marcar" in t for t in _conversa(mesa, _pedido(mesa)["id"]))


def test_acao_do_grimorio_com_pedido_esperando_volta_a_ele(mesa, delegados):
    g = Grimorio(OPCOES_GERENTE).ligar(mesa)
    p = mesa.registrar("ligue o gerente, se eu decidir")
    mesa.passo()
    mesa.despachante.terminar(p["id"], arquivos=0, aplicado=False,
                              resposta="GRIMÓRIO: geral/gerente-ligado")
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "esperando_voce"
    g.responder("ligar")
    mesa.passo()
    assert delegados.ler_config()["gerente_ligado"] is True
    atual = _pedido(mesa, p["id"])
    # o resultado da acao e do SERVIDOR: fica em do_servidor, o texto e do Adrian
    assert "O servidor executou `gerente ligar`" in " ".join(atual["do_servidor"])
    assert "O servidor executou" not in atual["texto"] and "Ligar" in atual["texto"]
    assert len(mesa.para_o_app()["pedidos"]) == 1


def test_decisoes_aceita_e_confere_a_acao_da_opcao():
    from remoto import decisoes
    opcoes = decisoes._opcoes(["ligar=Ligar|A fila anda.|gerente ligar", "Deixar",
                               {"id": "par", "rotulo": "Dois", "acao_servidor": "paralelo  2"}])
    assert opcoes[0]["acao_servidor"] == "gerente ligar" and opcoes[0]["descricao"] == "A fila anda."
    assert "acao_servidor" not in opcoes[1]
    assert opcoes[2]["acao_servidor"] == "paralelo 2"
    for ruim in ("x=X|d|gerente talvez", "x=X|d|paralelo 9", "x=Deixar|d|gerente ligar; push",
                 "x=X|d|renovacao"):
        with pytest.raises(decisoes.Recusa):
            decisoes._opcoes([ruim])


@pytest.mark.parametrize("bruta, descricao", [
    ("Manter|usa A | B como hoje", "usa A | B como hoje"),
    ("x=X|d|publicar tudo", "d|publicar tudo"),
    ("x=X|d|gerente ligar|mais", "d|gerente ligar|mais"),
])
def test_descricao_com_barra_continua_cabendo(bruta, descricao):
    """Conferente 3 (a11): a v2 quebrou "rotulo|descricao com | barra". O
    ultimo campo so e acao quando comeca pelo NOME de uma acao do servidor."""
    from remoto import decisoes
    opcao = decisoes._opcoes([bruta])[0]
    assert opcao["descricao"] == descricao and "acao_servidor" not in opcao


def test_o_no_real_do_gerente_tem_a_acao_estruturada():
    no = json.loads((RAIZ / "decisoes" / "geral" / "gerente-ligado.json").read_text(encoding="utf-8"))
    acoes = {o["id"]: o.get("acao_servidor") for o in no["opcoes"]}
    assert acoes == {"ligar": "gerente ligar", "deixar": "gerente desligar"}
    for acao in acoes.values():
        pedidos.ler_acao_servidor(acao)


# ================================================ 3. continuacao e conversa
# Conferente 5 (05/10/2026): volta a especificacao -- LISTA FIXA e pequena,
# comparada inteira (sem acento nem pontuacao), ou ate 3 frases dela em
# sequencia. O vocabulario aberto engolia pedidos de verdade.
@pytest.mark.parametrize("texto", [
    "Coordenador?", "?", "oi", "Olá", "Bom dia!", "boa tarde", "Boa noite", "e aí", "opa",
    "qual o progresso", "qual o progresso?", "Como estão as coisas?", "alguma novidade?",
    "status", "e aí, como tá?",
    "Ola coordenador, como as coisas estão",            # o de 05/10
    "e aí coordenador, alguma novidade?", "bom dia coordenador, qual o progresso?",
    "ok", "valeu", "Obrigado!", "beleza", "ok, valeu"])
def test_conversa_solta_forma_curta_e_fixa(texto):
    assert pedidos.e_conversa_solta(texto)


@pytest.mark.parametrize("texto", [
    "e confira no celular", "use a grave, não precisa esperar", "corrija o defeito X do app",
    "já loguei no Drive, como está?", "pode ligar o gerente", "agora faça Y também",
    "outra coisa", "como faço para publicar o vídeo da história 12 no TikTok amanhã cedo?",
    "um pedido em andamento", "mostre o progresso de cada pedido na aba",
    "oi, ligue o gerente", "qual o progresso do vídeo novo", "e o gerente?",
    "oi " * 13, "oi oi oi oi",                         # mais de 3 frases em sequencia
    "bom dia coordenador, como estão as coisas por aí? liga o gerente",
    # fora da lista fixa: viram pedido (conferente 5)
    "como está?", "e aí, tudo certo?", "alguém aí?", "sim", "pode", "já loguei",
    "beleza, pode seguir", "bom trabalho", "reinicie o app", "rode os testes",
    "pode ligar o gerente?", "bom dia coordenador, como estão as coisas por aí?"])
def test_nao_e_conversa_solta(texto):
    assert not pedidos.e_conversa_solta(texto)


def _parado(mesa, situacao, **kw):
    """Um pedido que parou na `situacao` (com trabalhador)."""
    if situacao == "esperando_voce":
        return _terminar(mesa, RESPOSTA_CD2E + "\nDESFECHO: bloqueado — falta o login do Drive",
                         arquivos=0, aplicado=False, texto="arquive os vídeos no Google Drive")
    if situacao == "entregue":
        return _terminar(mesa, "Consertei.\nDESFECHO: feito", aplicado=False)
    if situacao == "falhou":
        return _terminar(mesa, "x\nDESFECHO: falhou — quebrou", arquivos=0, aplicado=False)
    return _terminar(mesa, "A causa é o disco.\nDESFECHO: feito", arquivos=0, aplicado=False,
                     texto="por que caiu o serviço do app ontem?")


@pytest.mark.parametrize("situacao", ["esperando_voce", "entregue", "falhou", "respondido"])
@pytest.mark.parametrize("novo", [
    # as sondas do conferente 2, todas
    "Faz o backup das fotos", "Faz o vídeo novo do Neural Fights", "já loguei no Drive",
    "pode tentar de novo", "e confira no celular", "Crie uma conta nova no TikTok",
    "Faz o backup das fotos e depois abrir o relatório", "Faz a limpeza da pasta delegados",
    "Faz o backup das fotos no computador",
    "Faz o backup das fotos e confere se apareceu no celular"])
def test_texto_livre_nunca_gruda_em_pedido_parado(mesa, situacao, novo):
    p = _parado(mesa, situacao)
    assert _pedido(mesa, p["id"])["situacao"] == situacao
    antes = _pedido(mesa, p["id"])["texto"]
    r = mesa.registrar(novo)
    assert r["id"] != p["id"] and r["continuacao"] is False
    assert _pedido(mesa, p["id"])["texto"] == antes


@pytest.mark.parametrize("situacao", ["recebido", "trabalhando", "esperando", "executando"])
@pytest.mark.parametrize("novo", ["Faz o vídeo novo do Neural Fights", "Faz o backup das fotos",
                                  "e confira no celular", "pode ligar o gerente"])
def test_pedido_ativo_tambem_nao_recebe_texto_livre(mesa, situacao, novo):
    """Conferente 3 (defeito 1): a regra "texto livre gruda no ATIVO mais
    novo" mandou "Faz o video novo do Neural Fights" ao pedido-7c727778
    (digen-parede). Ativo ou parado, texto solto e pedido novo."""
    p = mesa.registrar("O Adrian respondeu no Grimório (builds/digen-parede): «Parede»",
                       "grimorio")
    with pedidos._TRAVA:
        dados = pedidos._ler()
        dados["pedidos"][-1]["situacao"] = situacao
        pedidos._gravar(dados)
    antes = _pedido(mesa, p["id"])["texto"]
    r = mesa.registrar(novo)
    assert r["id"] != p["id"] and r["continuacao"] is False
    assert _pedido(mesa, p["id"])["texto"] == antes


def test_o_7c727778_de_pid_morto_nao_recebe_o_pedido_novo(mesa):
    """A forma do disco real de 05/10: "trabalhando", ficha "rodando" com o
    pid 11412 morto, em retomada. O pedido novo abre o seu proprio."""
    p = mesa.registrar("O Adrian respondeu no Grimório (builds/digen-parede): «Parede»",
                       "grimorio")
    mesa.passo()
    mesa.despachante.estados[p["id"]]["pid"] = 11412
    mesa.despachante._pid_vivo = lambda pid: False
    mesa.relogio.andar(minutes=11)
    mesa.passo()
    r = mesa.registrar("Faz o vídeo novo do Neural Fights")
    assert r["id"] != p["id"] and r["continuacao"] is False
    assert "Neural Fights" not in _pedido(mesa, p["id"])["texto"]
    mesa.passo()
    assert [c[0] for c in mesa.despachante.criados] == [p["id"], r["id"]]


def test_responder_explicito_destrava_o_mesmo_trabalhador(mesa):
    p = _parado(mesa, "esperando_voce")
    outro = _parado(mesa, "esperando_voce")
    r = mesa.registrar("já loguei no Drive", responde_a=p["id"])
    assert r["id"] == p["id"] and r["continuacao"] is True
    _andar(mesa, 2)
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
    assert _pedido(mesa, p["id"])["situacao"] == "trabalhando"
    assert not _pedido(mesa, p["id"]).get("bloqueio")
    assert _pedido(mesa, outro["id"])["situacao"] == "esperando_voce"


def test_responder_a_um_falhou_reabre_com_as_retomadas_zeradas(mesa):
    p = _parado(mesa, "falhou")
    r = mesa.registrar("tente de novo com o disco limpo", responde_a=p["id"])
    assert r["situacao"] == "esperando" and r["retomadas"] == 0
    _andar(mesa, 2)
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]


def test_responder_caso_zero_e_erros(mesa):
    with pytest.raises(KeyError):
        mesa.registrar("oi", responde_a="pedido-00000000")
    conversa = mesa.registrar("Coordenador?")
    with pytest.raises(ValueError):
        mesa.registrar("e então?", responde_a=conversa["id"])
    with pytest.raises(ValueError):
        mesa.registrar("   ", responde_a=conversa["id"])


def test_saudacao_nao_gruda_e_responde_como_gente(mesa):
    """06/10/2026: a resposta e de gente (sem id nem lista); o que espera por
    ele aparece contado, e o pedido parado nao ganha a mensagem."""
    p = _parado(mesa, "esperando_voce")
    for frase in ("Ola coordenador, como as coisas estão", "Coordenador?"):
        r = mesa.registrar(frase)
        assert r["id"] != p["id"] and r["situacao"] == "respondido"
    assert _pedido(mesa, p["id"])["mensagens"] == 1
    mesa.atender_conversa()
    final = [c for c in mesa.para_o_app()["conversa"] if c["tipo"] == "final"][-1]["texto"]
    assert final.startswith("Oi, Adrian!") and "1 coisa espera uma resposta sua" in final
    assert "pedido-" not in final and "Retrato" not in final


def test_saudacao_durante_o_trabalho_nao_relanca_o_trabalhador(mesa):
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    mesa.registrar("como está?")
    assert _pedido(mesa, p["id"]).get("continuar") is False
    assert "como está?" not in _pedido(mesa, p["id"])["texto"]


def test_saudacao_pelo_telegram_volta_a_resposta_no_item(mesa):
    """Conferente 3 (defeito 2): o bot registra no PROCESSO DELE, onde o
    `avisar` e vazio; a resposta tem de voltar no item, que o bot devolve.
    06/10: a resposta-modelo de gente, na hora (o bot nao roda modelo)."""
    r = mesa.registrar("Coordenador?", "telegram")
    assert r["conversa"] is True and r["situacao"] == "respondido"
    assert r["papo"] == "respondido" and r["resposta"].startswith("Oi, Adrian!")
    assert "nenhum trabalho rodando" in r["resposta"]            # caso zero
    assert mesa.avisos == []                                     # nada ao avisar vazio
    assert mesa.atender_conversa() == []                         # nada fica pensando


# ================================================ 4. pid morto e recusa
def test_rodando_com_pid_morto_retoma_sem_laco(mesa):
    """O 7c727778 real: pid 11412 morto, ficha "rodando", `parar` recusa pid
    morto; o pulso alternava "parei" / "de volta" para sempre."""
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    mesa.despachante.estados[p["id"]]["pid"] = 11412
    mesa.despachante._pid_vivo = lambda pid: False if pid == 11412 else True
    mesa.relogio.andar(minutes=11)
    mesa.passo()
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando" and "morreu" in atual["motivo"]
    assert mesa.despachante.parados == []                # nao pede parar a pid morto
    mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    mesa.passo()
    assert mesa.despachante.fundos[-1] == ["rodar", "--id", p["id"]]       # retomou de verdade
    assert not any("de volta" in t for t in _conversa(mesa, p["id"]))


def test_pid_que_continua_morto_termina_em_falhou_sem_laco(mesa):
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    mesa.despachante.estados[p["id"]]["pid"] = 11412
    mesa.despachante._pid_vivo = lambda pid: False
    mesa.relogio.andar(minutes=11)
    for _ in range(600):
        mesa.relogio.andar(seconds=6)
        mesa.passo()
    linhas = _conversa(mesa, p["id"])
    assert not any("de volta" in t for t in linhas)
    assert len(linhas) <= 2 * (pedidos.MAX_RETOMADAS + 3), linhas
    assert _pedido(mesa)["situacao"] == "falhou"


def test_trabalhador_vivo_e_mudo_nao_vira_laco(mesa):
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    mesa.despachante.estados[p["id"]]["pid"] = 999
    mesa.despachante._pid_vivo = lambda pid: True
    mesa.relogio.andar(minutes=11)
    for _ in range(40):                       # 4 min de pulsos de 6 s
        mesa.relogio.andar(seconds=6)
        mesa.passo()
    linhas = _conversa(mesa, p["id"])
    assert len(linhas) <= 8, linhas
    assert not any("de volta" in t for t in linhas)
    assert _pedido(mesa)["situacao"] == "esperando"
    assert 2 <= len(mesa.despachante.parados) <= 3       # repete o parar a cada RETOMAR_S


def _recusando(mesa, ident, recusa):
    """O `no_fundo` do delegar recusado: so a linha no fundo.txt, ficha intacta."""
    def no_fundo(argv, _ident):
        mesa.despachante.fundos.append(list(argv))
        pasta = mesa.despachante.pasta_da(ident)
        pasta.mkdir(parents=True, exist_ok=True)
        with open(pasta / "fundo.txt", "a", encoding="utf-8") as fh:
            fh.write(f"recusado: {recusa}\n")
        return 1
    mesa.despachante.no_fundo = no_fundo


def _pid_morto(mesa):
    p = mesa.registrar("corrija o defeito X do app")
    mesa.passo()
    mesa.despachante.estados[p["id"]]["pid"] = 11412
    mesa.despachante._pid_vivo = lambda pid: False
    mesa.relogio.andar(minutes=11)
    return p


def test_relancamento_recusado_por_espera_nao_gasta_retomada(mesa):
    p = _pid_morto(mesa)
    _recusando(mesa, p["id"], "no máximo 1 delegado(s) ao mesmo tempo: pedido-x rodando")
    for _ in range(300):                      # 30 min de pulsos
        mesa.relogio.andar(seconds=6)
        mesa.passo()
    atual = _pedido(mesa)
    assert atual["situacao"] != "falhou" and int(atual.get("retomadas") or 0) <= 1
    assert "no máximo 1 delegado" in atual["ultima_recusa"]
    linhas = _conversa(mesa, p["id"])
    assert sum("recusou o relançamento" in t for t in linhas) == 1        # nao repete
    assert len(linhas) <= 12, linhas
    # o paralelo liberou: o relancamento entra e o pedido segue
    original = DespachanteFalso.no_fundo

    def no_fundo(argv, ident):
        r = original(mesa.despachante, argv, ident)
        mesa.despachante.estados[ident].update(pid=999, atualizado_em=mesa.relogio().isoformat())
        return r
    mesa.despachante.no_fundo = no_fundo
    mesa.despachante._pid_vivo = lambda pid: pid == 999
    for _ in range(40):
        mesa.relogio.andar(seconds=6)
        mesa.passo()
    assert _pedido(mesa)["situacao"] == "trabalhando"


def test_recusa_que_nao_e_de_espera_gasta_e_entra_no_motivo_do_falhou(mesa):
    p = _pid_morto(mesa)
    _recusando(mesa, p["id"], "a worktree sumiu: E:\\projetos-wt\\x")
    for _ in range(600):
        mesa.relogio.andar(seconds=6)
        mesa.passo()
    atual = _pedido(mesa)
    assert atual["situacao"] == "falhou"
    assert "o despachante recusou: a worktree sumiu" in atual["motivo"]


def test_as_recusas_de_espera_sao_as_mensagens_do_delegar():
    fonte = (RAIZ / "remoto" / "delegar.py").read_text(encoding="utf-8")
    for trecho in pedidos.RECUSAS_DE_ESPERA:
        assert trecho in fonte, trecho
    assert 'print(f"recusado: {exc}"' in fonte


# ================================================ correcao dos pedidos reais
def _como_em_05_10(mesa, resposta, *, soltas=()):
    """O pedido como o codigo velho deixou: "entregue", o trabalhador com a
    resposta de bloqueio (e as mensagens soltas grudadas no texto)."""
    p = mesa.registrar("O Adrian respondeu no Grimório (geral/x): «Ligar o gerente»", "grimorio",
                       novo=True)
    mesa.passo()
    mesa.despachante.terminar(p["id"], resposta=resposta, arquivos=1, aplicado=False,
                              desfecho=None)
    mesa.despachante.estados[p["id"]]["diff"] = dict(DIFF_SO_RESPOSTA)
    with pedidos._TRAVA:
        dados = pedidos._ler()
        alvo = next(x for x in dados["pedidos"] if x["id"] == p["id"])
        alvo.update(situacao="entregue")
        for s in soltas:
            alvo["texto"] += "\n\nContinuação do Adrian:\n" + s
            alvo["mensagens"] = int(alvo.get("mensagens") or 1) + 1
            alvo["ultima_continuacao"] = s
        pedidos._gravar(dados)
    return p


def test_reavaliar_os_pedidos_reais_sem_a_linha_esperam_voce(mesa):
    cd2e = _como_em_05_10(mesa, RESPOSTA_CD2E,
                          soltas=("Ola coordenador, como as coisas estão", "Coordenador?"))
    feito = mesa.reavaliar(cd2e["id"])
    assert feito["situacao"] == "esperando_voce" and feito["motivo"] == pedidos.SEM_DESFECHO
    assert "Coordenador?" not in feito["texto"] and feito["mensagens"] == 1
    with pytest.raises(ValueError):
        mesa.reavaliar(cd2e["id"])                    # so reavalia "entregue"
    with pytest.raises(KeyError):
        mesa.reavaliar("pedido-sumiu")


def test_reavaliar_entrega_com_a_linha_feito_continua_entregue(mesa):
    p = _como_em_05_10(mesa, "Consertei a tela.\nDESFECHO: feito")
    assert mesa.reavaliar(p["id"])["situacao"] == "entregue"
    mesa.despachante.estados[p["id"]]["aplicado"] = {"arquivos": ["remoto/x.py"]}
    with pytest.raises(ValueError):
        mesa.reavaliar(p["id"])                       # aplicado: decide o conferente


def test_linha_de_comando_reavaliar_e_reabrir_com_continuacao(tmp_path, monkeypatch, capsys):
    from coordenador import __main__ as cli
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coord"))
    m = pedidos.MesaPedidos(despachante=DespachanteFalso(tmp_path / "d"), claude=ClaudeFalso(),
                            uso=lambda: {"passou_teto": False})
    monkeypatch.setattr(pedidos, "MESA", m)
    p = _como_em_05_10(m, RESPOSTA_CB44)
    assert cli.main(["reavaliar-pedido", p["id"]]) == 0
    assert "esperando_voce" in capsys.readouterr().out
    assert cli.main(["reabrir-pedido", p["id"], "--continuacao", "termine com DESFECHO"]) == 0
    dados = json.loads((tmp_path / "coord" / "pedidos.json").read_text(encoding="utf-8"))
    alvo = next(x for x in dados["pedidos"] if x["id"] == p["id"])
    assert alvo["continuar"] is True and alvo["texto"].endswith("termine com DESFECHO")
    assert cli.main(["reavaliar-pedido", "pedido-sumiu"]) == 1


# ===================================================== conferente 4 (05/10/2026)
_FILHO_SEGURA_A_TRAVA = """
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from coordenador import pedidos
with pedidos._TRAVA:
    dados = pedidos._ler()
    Path(sys.argv[2]).write_text("dentro", encoding="utf-8")
    time.sleep(1.5)
    dados["pedidos"][0]["marca_do_filho"] = True
    pedidos._gravar(dados)
"""


def test_trava_vale_entre_processos_e_o_responder_nao_se_perde(mesa, tmp_path):
    """Defeito 1: o app/bot (um processo) e o pulso (outro) gravavam o mesmo
    pedidos.json com uma trava so de thread; o pulso regravava o retrato velho
    por cima do Responder. Aqui o FILHO faz o papel do pulso: le, segura a
    trava 1,5 s e grava; o Responder do pai, no meio, espera e nao se perde."""
    import os
    import subprocess
    import sys
    import time
    p = _terminar(mesa, RESPOSTA_CD2E + "\nDESFECHO: bloqueado — falta o login do Drive",
                  arquivos=0, aplicado=False, texto="arquive os vídeos no Google Drive")
    sinal = tmp_path / "filho_dentro"
    filho = subprocess.Popen([sys.executable, "-c", _FILHO_SEGURA_A_TRAVA,
                              str(Path(pedidos.__file__).resolve().parents[1]), str(sinal)],
                             env=dict(os.environ))
    try:
        prazo = time.monotonic() + 30
        while not sinal.exists():
            assert time.monotonic() < prazo and filho.poll() is None, "o filho não entrou"
            time.sleep(0.02)
        inicio = time.monotonic()
        mesa.registrar("já loguei no Drive (corrida)", responde_a=p["id"])
        esperou = time.monotonic() - inicio
    finally:
        assert filho.wait(timeout=60) == 0
    assert esperou >= 0.5                       # esperou o "pulso" do filho soltar
    alvo = next(x for x in pedidos._ler()["pedidos"] if x["id"] == p["id"])
    assert alvo["ultima_continuacao"] == "já loguei no Drive (corrida)"
    assert alvo["continuar"] is True and "corrida" in alvo["texto"]


def test_aviso_com_a_trava_na_mao_sai_depois_de_solta_la(mesa):
    """O Telegram (rede) nao segura a trava que o Responder do app espera."""
    with pedidos._TRAVA:
        mesa.avisar("um aviso")
        with pedidos._TRAVA:                    # reentrante na mesma thread
            mesa.avisar("outro")
        assert mesa.avisos == []
    assert mesa.avisos == ["um aviso", "outro"]
    mesa.avisar("sem trava")
    assert mesa.avisos[-1] == "sem trava"


@pytest.mark.parametrize("texto", ["ok", "valeu", "obrigado", "Obrigada!", "beleza", "ok, valeu"])
def test_defeito2_agradecimento_solto_nao_contrata_ninguem(mesa, texto):
    """Defeito 2: "ok", "valeu" abriam pedido novo e contratavam um
    orquestrador pago, sem contexto. Agradecimento solto (lista fixa) volta o
    retrato e o lembrete do Responder; nada gruda."""
    cd = _terminar(mesa, RESPOSTA_CD2E + "\nDESFECHO: bloqueado — falta o login do Drive",
                   arquivos=0, aplicado=False, texto="arquive os vídeos no Google Drive")
    criados = len(mesa.despachante.criados)
    r = mesa.registrar(texto)
    _andar(mesa, 3)
    assert len(mesa.despachante.criados) == criados
    assert r["situacao"] == "respondido" and r["conversa"] is True and r["curto"] is True
    assert r["resposta"].startswith("De nada!") and "Responder" in r["resposta"]
    assert cd["id"] not in r["resposta"]                     # 06/10: sem id na conversa
    assert _pedido(mesa, cd["id"])["situacao"] == "esperando_voce"     # nada grudou


@pytest.mark.parametrize("texto", ["qual o progresso?", "Coordenador?", "bom dia",
                                   "Orquestrador?", "Orquestrador conversei comigo.",
                                   "o que você está fazendo?"])
def test_saudacao_e_status_respondem_como_gente_sem_o_aviso(mesa, texto):
    r = mesa.registrar(texto)
    mesa.passo()
    assert r["situacao"] == "respondido" and r["conversa"] is True and r["curto"] is False
    assert r["resposta"].startswith("Oi, Adrian!") and mesa.despachante.criados == []


@pytest.mark.parametrize("texto", [
    "Faz o vídeo novo do Neural Fights", "ligue o gerente da equipe",
    "pode ligar o gerente da equipe hoje à noite?",
    # conferente 5: o "curto" por contagem de palavras engolia estes
    "reinicie o app", "rode os testes", "pode ligar o gerente?", "sim", "pode", "já loguei",
    "beleza, pode seguir", "e o gerente?", "qual a situacao do pedido?",
    "alguma novidade do drive?", "Ola cordenador"])
def test_defeito2_pedido_de_verdade_ainda_contrata(mesa, texto):
    r = mesa.registrar(texto)
    mesa.passo()
    assert not r.get("conversa") and len(mesa.despachante.criados) == 1


def test_a_forma_fixa_e_a_lista_inteira():
    assert pedidos.forma_fixa("Olá, coordenador!") == "conversa"
    assert pedidos.forma_fixa("valeu") == "agradecimento"
    assert pedidos.forma_fixa("oi, valeu") == "agradecimento"
    assert pedidos.forma_fixa("ligue o gerente") == ""            # curto, mas fora da lista
    assert pedidos.forma_fixa("por que o vigia parou ontem?") == ""
    assert pedidos.forma_fixa("") == ""
    # o "curto" por contagem de palavras saiu (conferente 5)
    for nome in ("CURTO_MAX_PALAVRAS", "PERGUNTA_CURTA_MAX_PALAVRAS", "e_curto_demais",
                 "CONVERSA_MAX_PALAVRAS"):
        assert not hasattr(pedidos, nome), nome


def test_defeito3_grimorio_no_meio_nao_decide_contra_a_linha(mesa):
    no = {"id": "arquivo-de-videos", "projeto": "geral", "opcoes": [], "vigente": None}
    mesa.grimorio = (lambda: [], lambda *a, **k: None, lambda: {"arquivo-de-videos": no})
    p = _terminar(mesa, "Consultei o nó abaixo, já decidido:\nGRIMÓRIO: geral/arquivo-de-videos\n"
                        "e fiz o resto.\nDESFECHO: feito", arquivos=0, aplicado=False)
    assert _pedido(mesa, p["id"])["situacao"] == "respondido"


@pytest.mark.parametrize("resposta, ref", [
    ("Falta a decisão.\nGRIMÓRIO: geral/arquivo-de-videos", "geral/arquivo-de-videos"),
    ("Falta a decisão.\nGRIMÓRIO: geral/arquivo-de-videos\n```\nDESFECHO: bloqueado — decisão",
     "geral/arquivo-de-videos"),
    ("GRIMÓRIO: geral/a\ne mais texto", None),
    ("x\nGRIMÓRIO: geral/a\nDESFECHO: feito\nfim", None),
])
def test_defeito3_marca_grimorio_so_na_ultima_linha(resposta, ref):
    assert pedidos.marca_grimorio(resposta) == ref


def test_defeito4_permitiu_e_respondeu_antes_do_pulso_executa_e_depois_continua(mesa, delegados):
    """Defeito 4: Permitir e logo `/responder` antes do pulso: a acao aprovada
    era descartada ("sua resposta chegou antes da aprovacao"). A decisao vale
    primeiro; a resposta segue depois ao mesmo trabalhador."""
    p = _pediu_executar(mesa, texto="ligue o gerente da equipe")
    mesa.despachante.decidir_permissao(p["id"], True)                 # Permitir (app)
    mesa.registrar("valeu, depois confere o paralelo", responde_a=p["id"])   # /responder
    mesa.passo()
    assert delegados.ler_config()["gerente_ligado"] is True
    atual = _pedido(mesa, p["id"])
    assert atual["continuar"] is True and "depois confere o paralelo" in atual["texto"]
    conversa = _conversa(mesa, p["id"])
    assert any("o servidor executou `gerente ligar`" in c for c in conversa)
    assert not any("NÃO foi executado" in c for c in conversa)
    _andar(mesa, 2)
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]


def test_defeito4_negou_e_respondeu_antes_do_pulso_registra_o_negou_e_continua(mesa, delegados):
    p = _pediu_executar(mesa, texto="ligue o gerente da equipe")
    mesa.despachante.decidir_permissao(p["id"], False)                # Negar
    mesa.registrar("então só me explique o porquê", responde_a=p["id"])
    mesa.passo()
    assert delegados.ler_config()["gerente_ligado"] is False
    assert any("você negou `gerente ligar`" in c for c in _conversa(mesa, p["id"]))
    assert _pedido(mesa, p["id"])["continuar"] is True


@pytest.mark.parametrize("resposta, tipo, motivo", [
    ("x\nDESFECHO: bloqueado — espera o deploy / falhou o login", "bloqueado",
     "espera o deploy / falhou o login"),
    ("x\nDESFECHO: falhou — pytest/bloqueado pelo sandbox", "falhou",
     "pytest/bloqueado pelo sandbox"),
    ("x\nDESFECHO: bloqueado — falta A | falhou B", "bloqueado", "falta A | falhou B"),
    ("x\nDESFECHO: feito | bloqueado — ... | falhou — ...", None, ""),
    ("x\nDESFECHO: feito/falhou", None, ""),
    ("x\nDESFECHO: bloqueado — <o que falta e quem faz>", None, ""),
])
def test_defeito6_so_o_modelo_literal_e_formato_copiado(resposta, tipo, motivo):
    lido = pedidos.ler_desfecho(resposta)
    assert (lido["tipo"], lido["motivo"]) == (tipo, motivo)
