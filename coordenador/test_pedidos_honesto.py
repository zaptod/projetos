# -*- coding: utf-8 -*-
"""Desfecho honesto, estado do servidor pelo servidor e conversa solta (05/10/2026).

O caso real: pedido-cb44cd52 ("ligar o gerente") ficou "entregue" com a
resposta "Nao foi possivel ligar"; pedido-cd2e5e0c ("arquivo no Drive") ficou
"entregue" com "Status: bloqueado so pelo login do Drive"; e "Ola coordenador,
como as coisas estao" e "Coordenador?" grudaram no cd2e5e0c."""
from __future__ import annotations

import json

import pytest

from coordenador import pedidos
from coordenador.test_pedidos import (ClaudeFalso, DespachanteFalso, _andar, _pedido,  # noqa: F401
                                      mesa)

# as respostas de verdade dos dois trabalhadores (delegados/<id>/resposta.md)
RESPOSTA_CB44 = (
    "Não foi possível ligar: a gravação atômica foi bloqueada ao abrir "
    "`%LOCALAPPDATA%\\neural-fights\\delegados\\delegar.lock`; o gerente continua desligado "
    "e não houve alteração parcial.\n\nAtualizei [`.permissao.json`](E:\\x) para pedir acesso "
    "à pasta operacional inteira.\n\nTeste: `python -m pytest coordenador/test_equipe.py -q` "
    "— 3 passaram.")
RESPOSTA_CD2E = (
    "Status: bloqueado só pelo login do Drive.\n\n- [resposta.md](E:\\x) atualizado com os 3 "
    "passos para o Adrian ativar o Drive.\n\nTeste: `python -m json.tool .permissao.json` "
    "passou.\n\nFalta o Adrian abrir o Google Drive para computador, entrar na conta de 5 TB "
    "e confirmar que `G:\\Meu Drive` apareceu.")


# ================================================ A. o desfecho
@pytest.mark.parametrize("resposta, tipo, motivo", [
    ("Liguei.\nDESFECHO: feito", "feito", ""),
    ("x\nDESFECHO: bloqueado — falta o Adrian entrar no Drive", "bloqueado",
     "falta o Adrian entrar no Drive"),
    ("x\n**DESFECHO:** falhou - o teste quebrou", "falhou", "o teste quebrou"),
    ("x\n`DESFECHO: Bloqueado: login`", "bloqueado", "login"),
    # a ultima vale: o rascunho de cima nao decide
    ("DESFECHO: bloqueado — antes\n...resolvi.\nDESFECHO: feito", "feito", ""),
])
def test_a_linha_do_desfecho(resposta, tipo, motivo):
    lido = pedidos.ler_desfecho(resposta)
    assert (lido["tipo"], lido["motivo"], lido["fonte"]) == (tipo, motivo, "linha")


def test_sem_a_linha_as_respostas_reais_viram_bloqueado():
    cb44 = pedidos.ler_desfecho(RESPOSTA_CB44)
    assert cb44["tipo"] == "bloqueado" and cb44["fonte"] == "heuristica"
    assert "Não foi possível ligar" in cb44["motivo"]
    cd2e = pedidos.ler_desfecho(RESPOSTA_CD2E)
    assert cd2e["tipo"] == "bloqueado" and "Falta o Adrian abrir o Google Drive" in cd2e["motivo"]


def test_sem_a_linha_caso_zero_e_resposta_comum():
    vazia = pedidos.ler_desfecho("")
    assert vazia["tipo"] == "bloqueado" and vazia["fonte"] == "vazia"
    assert pedidos.ler_desfecho("   \n")["fonte"] == "vazia"
    comum = pedidos.ler_desfecho("consertei X e os testes passaram")
    assert comum == {"tipo": "feito", "motivo": "", "fonte": "sem_linha", "aviso": ""}
    # palavra parecida nao e bloqueio
    assert pedidos.ler_desfecho("o vigia foi desbloqueado e roda")["tipo"] == "feito"


# Respostas REAIS de entregas que deram certo (delegados/<id>/resposta.md de
# 05/10/2026): a regra velha dava "bloqueado" em todas, por palavra solta.
ENTREGAS_BOAS_REAIS = {
    "app-5959d5ba": (
        "Corrigido o layout da aba Equipe em retrato.\n\n- `remoto/app/app.css`: controles "
        "recolhidos.\n\nTestes:\n\n- 11 passaram, 2 pulados.\n\nFicaram diretórios temporários "
        "`remoto/.pytest_tmp*` não rastreados; a remoção foi bloqueada pela política do sandbox. "
        "O `.codex_tarefa.md` já existia e não foi alterado."),
    "pedidos-app": (
        "Implementado o fluxo de pedidos soberanos.\n\nTestes:\n\n- 4 passed.\n- Navegador "
        "passou com TEMP local: 2 passed. Com `TEMP=E:\\tmp_pytest`, falha por permissão do "
        "sandbox.\n\nFicou um diretório temporário `.teste_tmp/` criado pelos testes; a remoção "
        "foi bloqueada pela política do sandbox."),
    "conf-cp1252-b": (
        "**APROVADO: o diff pode ir para o main.** Mas o mesmo tipo de queda continua em outro "
        "`print`. Ele não bloqueia este diff.\n\n**O que conferi**\n1. 42 passed.\n\n- Estrago: "
        "o estado já foi gravado antes. Não consegui reproduzir no app."),
    "mesa-conf-pedido-d23fa2c3": (
        "**DEFEITOS (menores).** O pedido em si está cumprido.\n\n**O que está certo:**\n- "
        "**Nada recoloca o item sozinho:** o cérebro só consegue pôr algo na fila como "
        "proposta, que depende do Adrian aprovar."),
    "simulador-godot": (
        "Implementei a ponte para o palco.\n\nTestes: 6 passed.\n\nA timeline foi exportada, "
        "mas o Godot foi bloqueado pelo sandbox; também não há `ffmpeg` no PATH. Portanto não "
        "foi possível gerar MP4 nem os 3 PNGs de prova."),
    "teste-instavel": (
        "causa (remoto/test_delegar.py:211): prazo fixo insuficiente sob carga.\n\ntestes: "
        "passou.\n\no que ficou duvidoso: não foi possível concluir as cinco execuções devido "
        "à permissão negada no diretório temporário do pytest."),
}
# e os bloqueios de verdade, tambem reais
BLOQUEIOS_REAIS = {
    "pedido-cb44cd52-1": RESPOSTA_CB44,
    "pedido-cd2e5e0c-1": RESPOSTA_CD2E,
    "pedido-7c727778": ("Não apliquei a escolha porque daqui não alcanço o arquivo. Pedi "
                        "permissão em `.permissao.json`.\n\n- **Por que travou:** o arquivo "
                        "não está no git."),
    "pedido-7c727778-1": "Bloqueado por permissão.\n\nCriei `.permissao.json` pedindo acesso.",
    "conf-pid-vazio": ("**Ainda não dá para aprovar nem reprovar.** Não consegui ver o diff do "
                       "`pid-vazio`.\n\n**O que conferi:**\n1. 10 passed."),
}


@pytest.mark.parametrize("nome", sorted(ENTREGAS_BOAS_REAIS))
def test_entrega_boa_real_nao_vira_bloqueio(nome):
    assert pedidos.ler_desfecho(ENTREGAS_BOAS_REAIS[nome])["tipo"] == "feito"


@pytest.mark.parametrize("nome", sorted(BLOQUEIOS_REAIS))
def test_bloqueio_real_continua_bloqueio(nome):
    lido = pedidos.ler_desfecho(BLOQUEIOS_REAIS[nome])
    assert (lido["tipo"], lido["fonte"]) == ("bloqueado", "heuristica")


@pytest.mark.parametrize("texto", [
    # as sondas do conferente: descrevem, nao estao bloqueadas
    "Corrigi o bug. O teste que estava bloqueado agora passa.\n3 passed.",
    "Pronto: agora pedido bloqueado vira esperando_voce no app.",
    "Implementado. O gerente continua desligado por padrão, como pedido.",
    "Consertei.\n\nNo app, o pedido fica bloqueado até o Adrian responder.",
])
def test_palavra_solta_nao_e_bloqueio(texto):
    assert pedidos.ler_desfecho(texto)["tipo"] == "feito"


@pytest.mark.parametrize("texto, aviso", [
    ("Não foi possível ligar o gerente.\nDESFECHO: feito", "Não foi possível ligar o gerente."),
    ("Feito.\nDESFECHO: feito parcialmente — faltou o teste", "parcialmente — faltou o teste"),
    ("Status: bloqueado pelo Drive.\nDESFECHO: feito", "Status: bloqueado pelo Drive."),
])
def test_feito_desmentido_pelo_texto_ganha_aviso(texto, aviso):
    lido = pedidos.ler_desfecho(texto)
    assert lido["tipo"] == "feito" and aviso in lido["aviso"]


@pytest.mark.parametrize("texto", [
    "Liguei e reli o config.\nDESFECHO: feito",
    "Pronto, só respondi: não mudei código.\n\nDESFECHO: feito — só respondi",
    "O teste que estava bloqueado agora passa.\nDESFECHO: feito",
])
def test_feito_limpo_nao_ganha_aviso(texto):
    assert pedidos.ler_desfecho(texto)["aviso"] == ""


def _terminar(mesa, resposta, **kw):
    p = mesa.registrar(kw.pop("texto", "corrija X"), novo=kw.pop("novo", False))
    diff = kw.pop("diff", None)
    mesa.passo()
    mesa.despachante.estados[p["id"]]["thread_id"] = "t1"
    mesa.despachante.terminar(p["id"], resposta=resposta, **kw)
    if diff is not None:
        mesa.despachante.estados[p["id"]]["diff"] = dict(diff)
    mesa.passo()
    return p


def test_bloqueado_espera_voce_com_o_que_falta_e_nao_gira(mesa):
    p = _terminar(mesa, "Fiz os passos.\nDESFECHO: bloqueado — falta o Adrian entrar no Drive",
                  arquivos=0, aplicado=False)
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando_voce"
    assert atual["motivo"] == "bloqueado: falta o Adrian entrar no Drive"
    assert "falta o Adrian entrar no Drive" in mesa.avisos[-1]
    _andar(mesa, pedidos.MAX_RETOMADAS + 2)
    assert _pedido(mesa)["situacao"] == "esperando_voce"       # nao relanca, nao queima
    assert mesa.despachante.fundos == [["rodar", "--id", p["id"]]]
    # a resposta dele no proprio pedido destrava o MESMO trabalhador
    volta = mesa.registrar("já loguei no Drive")
    assert volta["id"] == p["id"] and volta["continuacao"] is True
    _andar(mesa, 2)
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
    assert _pedido(mesa)["situacao"] == "trabalhando" and not _pedido(mesa).get("bloqueio")


def test_falhou_vira_falhou_com_o_motivo(mesa):
    _terminar(mesa, "Tentei.\nDESFECHO: falhou — o config está ilegível", arquivos=0,
              aplicado=False)
    atual = _pedido(mesa)
    assert atual["situacao"] == "falhou" and atual["motivo"] == "o config está ilegível"
    assert mesa.avisos[-1].startswith("❌")


DIFF_SO_RESPOSTA = {"arquivos": 1, "avisos": ["fora da lista (entrou): resposta.md"]}


def test_resposta_do_cb44_sem_a_linha_nao_vira_entregue(mesa):
    # o diff de 05/10 contava o resposta.md como 1 arquivo: caia em "entregue"
    _terminar(mesa, RESPOSTA_CB44, aplicado=False, texto="ligue o gerente",
              diff=DIFF_SO_RESPOSTA)
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando_voce"
    assert "Não foi possível ligar" in atual["motivo"]
    textos = [c["texto"] for c in mesa.para_o_app()["conversa"]]
    assert any("sem a linha DESFECHO" in t for t in textos)
    assert atual["desfecho"]["fonte"] == "heuristica"


def test_caso_zero_terminou_sem_resposta_nao_e_entregue(mesa):
    _terminar(mesa, "", arquivos=1, aplicado=False)
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando_voce" and "sem resposta" in atual["motivo"]


def test_feito_segue_como_antes(mesa):
    _terminar(mesa, "Consertei.\nDESFECHO: feito", aplicado=False)
    assert _pedido(mesa)["situacao"] == "entregue"
    mesa.novo_assunto()
    _terminar(mesa, "A causa é o disco.\nDESFECHO: feito", arquivos=0, aplicado=False,
              texto="por que caiu?")
    assert _pedido(mesa)["situacao"] == "respondido"


def test_entregue_com_o_trabalhador_pedindo_permissao_nao_fica_entregue(mesa):
    p = _terminar(mesa, "DESFECHO: feito", aplicado=False)
    assert _pedido(mesa)["situacao"] == "entregue"
    mesa.despachante.estados[p["id"]].update(
        situacao="aguardando_permissao", motivo="aguardando permissao: ligar o gerente",
        pedido_permissao={"o_que": "ligar o gerente", "categoria": "caminho_protegido"})
    mesa.passo()
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando" and "ligar o gerente" in atual["motivo"]


def test_o_prompt_pede_a_linha_do_desfecho_e_lista_as_acoes_do_servidor(mesa):
    mesa.registrar("corrija X")
    mesa.passo()
    tarefa = mesa.despachante.criados[0][2]
    assert "DESFECHO: feito" in tarefa and "DESFECHO: bloqueado" in tarefa
    assert "DESFECHO: falhou" in tarefa
    assert "EXECUTAR: gerente <ligar|desligar>" in tarefa
    assert "EXECUTAR: historias_auto" in tarefa                 # a do repositorio continua


# ================================================ B. estado do servidor
@pytest.fixture
def delegados(tmp_path, monkeypatch):
    """O config da equipe numa pasta temporaria (nunca o LOCALAPPDATA real)."""
    from remoto import delegar
    monkeypatch.setattr(delegar, "PASTA", None)
    monkeypatch.setenv("NF_DELEGADOS_PASTA", str(tmp_path / "delegados_cfg"))
    assert delegar.pasta() == tmp_path / "delegados_cfg"
    return delegar


def test_executar_gerente_ligar_o_servidor_grava_confere_e_responde(mesa, delegados):
    diario = []
    mesa.diario = lambda *a, **k: diario.append(a[1])
    mesa.executor = lambda *a: pytest.fail("acao do servidor nao vai ao executor do repositorio")
    assert delegados.ler_config()["gerente_ligado"] is False
    _terminar(mesa, "A worktree não grava o config.\nEXECUTAR: gerente ligar", arquivos=0,
              aplicado=False, texto="ligue o gerente")
    assert delegados.ler_config()["gerente_ligado"] is True
    atual = _pedido(mesa)
    assert atual["situacao"] == "respondido" and atual["desfecho"]["fonte"] == "servidor"
    assert "LIGADO" in mesa.avisos[-1] and "relido" in mesa.avisos[-1]
    assert diario == ["inicio", "ok"]
    assert atual["execucoes_feitas"][-1]["desfecho"].startswith("conferido")
    assert len(mesa.despachante.fundos) == 1          # nenhuma rodada a mais do trabalhador


def test_executar_gerente_desligar_e_renovacao(mesa, delegados):
    delegados.gravar_config({"gerente_ligado": True})
    _terminar(mesa, "EXECUTAR: gerente desligar", arquivos=0, aplicado=False,
              texto="desligue o gerente")
    assert delegados.ler_config()["gerente_ligado"] is False
    _terminar(mesa, "EXECUTAR: renovacao 40 75", arquivos=0, aplicado=False,
              texto="renove a conversa a cada 40 turnos")
    cfg = delegados.ler_config()
    assert (cfg["renovar_apos_turnos"], cfg["renovar_apos_min"]) == (40, 75)
    assert _pedido(mesa)["situacao"] == "respondido"


def test_executar_do_servidor_com_argumento_invalido_volta_ao_trabalhador(mesa, delegados):
    p = _terminar(mesa, "EXECUTAR: gerente talvez", arquivos=0, aplicado=False,
                  texto="ligue o gerente")
    assert delegados.ler_config()["gerente_ligado"] is False
    atual = _pedido(mesa)
    assert "recusou" in atual["texto"] and atual["continuar"] is True
    _andar(mesa)
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
    for ruim in (["9"], ["0"], ["2", "3"]):
        with pytest.raises(ValueError):
            pedidos.acao_do_servidor("paralelo", ruim)
    with pytest.raises(ValueError):
        pedidos.acao_do_servidor("publicar_tudo", [])


def test_executar_do_servidor_que_nao_confere_vira_falhou(mesa, delegados, monkeypatch):
    def quebra(_args):
        raise RuntimeError("gravei gerente_ligado=True, mas o config relido diz False")
    monkeypatch.setattr(pedidos, "_servidor_gerente", quebra)
    _terminar(mesa, "EXECUTAR: gerente ligar", arquivos=0, aplicado=False, texto="ligue o gerente")
    atual = _pedido(mesa)
    assert atual["situacao"] == "falhou" and "relido diz False" in atual["motivo"]
    assert mesa.avisos[-1].startswith("❌")


def test_executar_paralelo_vai_pela_mesa(mesa, monkeypatch):
    chamadas = []
    monkeypatch.setattr(pedidos, "_servidor_paralelo",
                        lambda args: chamadas.append(args) or "até 2 (relido)")
    _terminar(mesa, "EXECUTAR: paralelo 2", arquivos=0, aplicado=False,
              texto="deixe 2 trabalhadores em paralelo")
    assert chamadas == [["2"]] and _pedido(mesa)["situacao"] == "respondido"


def test_executar_do_servidor_com_codigo_ainda_passa_pelo_conferente(mesa, delegados):
    _terminar(mesa, "Mudei a tela.\nEXECUTAR: gerente ligar", aplicado=False,
              texto="mude a tela e ligue o gerente")
    assert delegados.ler_config()["gerente_ligado"] is True
    assert _pedido(mesa)["situacao"] == "entregue"


def test_as_acoes_do_servidor_nao_publicam():
    for nome, acao in pedidos.ACOES_SERVIDOR.items():
        assert not pedidos._publica([nome, acao["fazer"], acao["o_que"]])
        assert callable(getattr(pedidos, acao["fazer"]))


# ================================================ C. conversa solta
@pytest.mark.parametrize("texto", [
    "Ola coordenador, como as coisas estão", "Coordenador?", "?", "oi", "Bom dia!",
    "qual o progresso", "como está?", "alguma novidade?", "e aí, tudo certo?"])
def test_conversa_solta(texto):
    assert pedidos.e_conversa_solta(texto)


@pytest.mark.parametrize("texto", [
    "e confira no celular", "use a grave, não precisa esperar", "corrija X",
    "já loguei no Drive, como está?", "pode ligar o gerente", "agora faça Y também",
    "outra coisa", "como faço para publicar o vídeo da história 12 no TikTok amanhã cedo?",
    # a frase do test_servidor_aplica: "andamento" num pedido nao e pergunta
    "um pedido em andamento", "mostre o progresso de cada pedido na aba"])
def test_nao_e_conversa_solta(texto):
    assert not pedidos.e_conversa_solta(texto)


def test_saudacao_nao_gruda_no_pedido_bloqueado_e_responde_o_retrato(mesa):
    p = _terminar(mesa, RESPOSTA_CD2E, arquivos=0, aplicado=False, texto="arquive no Drive")
    assert _pedido(mesa, p["id"])["situacao"] == "esperando_voce"
    texto_antes = _pedido(mesa, p["id"])["texto"]
    for frase in ("Ola coordenador, como as coisas estão", "Coordenador?"):
        r = mesa.registrar(frase)
        assert r["id"] != p["id"] and r["continuacao"] is False
        assert r["situacao"] == "respondido"
    bloqueado = _pedido(mesa, p["id"])
    assert bloqueado["texto"] == texto_antes and bloqueado["mensagens"] == 1
    criados = len(mesa.despachante.criados)
    mesa.passo()
    assert len(mesa.despachante.criados) == criados             # ninguem contratado
    final = [c for c in mesa.para_o_app()["conversa"] if c["tipo"] == "final"][-1]["texto"]
    assert p["id"] in final and "esperando você" in final and "Falta o Adrian" in final
    assert not any("Retrato" in a for a in mesa.avisos)          # do app: nao vai ao Telegram


def test_saudacao_pelo_telegram_responde_la_e_nao_gasta_o_novo_assunto(mesa):
    mesa.novo_assunto("telegram")
    mesa.registrar("Coordenador?", "telegram")
    assert mesa.avisos and "Retrato do servidor" in mesa.avisos[-1]
    assert "nenhum pedido aberto" in mesa.avisos[-1]               # caso zero
    assert mesa.para_o_app()["novo_assunto"] is True


def test_saudacao_durante_o_trabalho_nao_relanca_o_trabalhador(mesa):
    p = mesa.registrar("corrija X")
    mesa.passo()
    mesa.registrar("como está?")
    assert _pedido(mesa, p["id"]).get("continuar") is False
    assert "como está?" not in _pedido(mesa, p["id"])["texto"]


# ================================================ correcao dos pedidos reais
def _como_em_05_10(mesa, resposta, *, soltas=(), permissao=False):
    """O pedido como o codigo velho deixou: "entregue", o trabalhador com a
    resposta de bloqueio (e as mensagens soltas grudadas no texto)."""
    p = mesa.registrar("O Adrian respondeu no Grimório (geral/x): «Ligar o gerente»", "grimorio",
                       novo=True)
    mesa.passo()
    mesa.despachante.terminar(p["id"], resposta=resposta, arquivos=1, aplicado=False)
    # o diff real dos dois: o "1 arquivo" era o rascunho resposta.md
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
    if permissao:
        mesa.despachante.estados[p["id"]].update(
            situacao="aguardando_permissao", motivo="aguardando permissao: ligar o gerente",
            pedido_permissao={"o_que": "ligar o gerente da equipe",
                              "categoria": "caminho_protegido"})
    return p


def test_reavaliar_corrige_os_dois_pedidos_reais(mesa):
    cd2e = _como_em_05_10(mesa, RESPOSTA_CD2E,
                          soltas=("Ola coordenador, como as coisas estão", "Coordenador?"))
    cb44 = _como_em_05_10(mesa, RESPOSTA_CB44, permissao=True)
    feito = mesa.reavaliar(cd2e["id"])
    assert feito["situacao"] == "esperando_voce" and "Falta o Adrian" in feito["motivo"]
    assert "Coordenador?" not in feito["texto"] and "como as coisas" not in feito["texto"]
    assert feito["mensagens"] == 1 and not feito.get("ultima_continuacao")
    feito = mesa.reavaliar(cb44["id"])
    assert feito["situacao"] == "esperando_voce" and "Não foi possível ligar" in feito["motivo"]
    with pytest.raises(ValueError):
        mesa.reavaliar(cb44["id"])                    # so reavalia "entregue"
    with pytest.raises(KeyError):
        mesa.reavaliar("pedido-sumiu")


def test_reavaliar_entrega_de_verdade_continua_entregue(mesa):
    p = _como_em_05_10(mesa, "Consertei a tela.\nDESFECHO: feito")
    assert mesa.reavaliar(p["id"])["situacao"] == "entregue"
    mesa.despachante.estados[p["id"]]["aplicado"] = {"arquivos": ["remoto/x.py"]}
    with pytest.raises(ValueError):
        mesa.reavaliar(p["id"])                       # aplicado: decide o conferente


def test_reabrir_o_cb44_pelo_caminho_novo_liga_o_gerente(mesa, delegados):
    """Reaberto com a continuacao, a permissao pendente e negada, o MESMO
    trabalhador pede EXECUTAR e o servidor liga, rele e responde."""
    p = _como_em_05_10(mesa, RESPOSTA_CB44, permissao=True)
    mesa.reavaliar(p["id"])
    mesa.reabrir(p["id"], "reaberto: o servidor grava o estado",
                 continuacao="Termine com a linha `EXECUTAR: gerente ligar`.")
    assert mesa.despachante.decisoes == [(p["id"], False)]
    mesa.despachante.estados[p["id"]]["thread_id"] = "t1"
    _andar(mesa, 2)
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
    continuacao = (mesa.despachante.pasta_da(p["id"]) / "continuacao.md").read_text(encoding="utf-8")
    assert "EXECUTAR: gerente ligar" in continuacao
    mesa.despachante.terminar(p["id"], resposta="EXECUTAR: gerente ligar", arquivos=0,
                              aplicado=False)
    mesa.passo()
    assert delegados.ler_config()["gerente_ligado"] is True
    assert _pedido(mesa, p["id"])["situacao"] == "respondido"


def test_linha_de_comando_reavaliar_e_reabrir_com_continuacao(tmp_path, monkeypatch, capsys):
    from coordenador import __main__ as cli
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coord"))
    m = pedidos.MesaPedidos(despachante=DespachanteFalso(tmp_path / "d"), claude=ClaudeFalso(),
                            uso=lambda: {"passou_teto": False})
    monkeypatch.setattr(pedidos, "MESA", m)
    p = _como_em_05_10(m, RESPOSTA_CB44)
    assert cli.main(["reavaliar-pedido", p["id"]]) == 0
    assert "esperando_voce" in capsys.readouterr().out
    assert cli.main(["reabrir-pedido", p["id"], "--continuacao", "EXECUTAR: gerente ligar"]) == 0
    dados = json.loads((tmp_path / "coord" / "pedidos.json").read_text(encoding="utf-8"))
    alvo = next(x for x in dados["pedidos"] if x["id"] == p["id"])
    assert alvo["continuar"] is True and alvo["texto"].endswith("EXECUTAR: gerente ligar")
    assert cli.main(["reavaliar-pedido", "pedido-sumiu"]) == 1


# ================================================ conferente 1: com codigo, aviso
def test_arquivos_de_codigo_nao_conta_o_rascunho():
    assert pedidos.arquivos_de_codigo({"diff": DIFF_SO_RESPOSTA}) == 0          # o cb44 real
    assert pedidos.arquivos_de_codigo({"diff": {"arquivos": [
        {"caminho": "resposta.md"}, {"caminho": ".permissao.json"},
        {"caminho": "remoto/x.py"}]}}) == 1
    assert pedidos.arquivos_de_codigo({"diff": {"arquivos": 2}}) == 2
    assert pedidos.arquivos_de_codigo({"aplicado": {"arquivos": ["remoto/x.py"]}}) == 1
    assert pedidos.arquivos_de_codigo({}) == 0                                  # caso zero
    assert pedidos.arquivos_de_codigo(None) == 0


def test_frase_de_bloqueio_com_codigo_vai_como_entregue_com_aviso(mesa):
    _terminar(mesa, "Consertei a tela, mas não consegui rodar o navegador.\n\n2 passed.",
              arquivos=1, aplicado=False)
    atual = _pedido(mesa)
    assert atual["situacao"] == "entregue"                  # o vigia e o conferente seguem
    assert atual["motivo"].startswith("entregue com aviso: ")
    assert "não consegui rodar o navegador" in atual["motivo"]
    assert not any(a.startswith("⏸") for a in mesa.avisos)  # nada de "esperando voce" falso


def test_feito_desmentido_sem_codigo_espera_voce(mesa):
    _terminar(mesa, "Não foi possível ligar o gerente.\nDESFECHO: feito", aplicado=False,
              diff=DIFF_SO_RESPOSTA, texto="ligue o gerente")
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando_voce"
    assert "Não foi possível ligar o gerente" in atual["motivo"]
    mesa.novo_assunto()
    _terminar(mesa, "Feito.\nDESFECHO: feito parcialmente — faltou o teste", aplicado=False)
    atual = _pedido(mesa)
    assert atual["situacao"] == "entregue" and "faltou o teste" in atual["motivo"]


def test_bloqueado_pela_linha_com_codigo_continua_bloqueado(mesa):
    # o trabalhador DISSE que esta bloqueado: vale o que ele disse
    _terminar(mesa, "Mudei a tela.\nDESFECHO: bloqueado — falta o Adrian testar no celular",
              arquivos=1, aplicado=False)
    assert _pedido(mesa)["situacao"] == "esperando_voce"


# ================================================ conferente 2: amarrado ao pedido
def test_marca_executar_so_na_ultima_linha():
    assert pedidos.marca_executar("Faço.\nEXECUTAR: gerente ligar") == ("gerente", ["ligar"])
    assert pedidos.marca_executar("EXECUTAR: gerente ligar\n\nDESFECHO: feito\n") == \
        ("gerente", ["ligar"])
    assert pedidos.marca_executar("Exemplo:\nEXECUTAR: `gerente ligar`\nNão rodei nada.") is None
    assert pedidos.marca_executar("") is None


def test_exemplo_de_executar_no_meio_da_resposta_nao_dispara(mesa, delegados):
    _terminar(mesa, "O caminho é terminar com\nEXECUTAR: gerente ligar\nmas isso é com o "
              "Adrian.\nDESFECHO: feito", arquivos=0, aplicado=False, texto="ligue o gerente")
    assert delegados.ler_config()["gerente_ligado"] is False
    assert not _pedido(mesa).get("execucoes")


@pytest.mark.parametrize("texto, resposta, porque", [
    ("corrija X", "EXECUTAR: gerente ligar", "não pediu nada sobre o gerente"),
    ("corrija X", "EXECUTAR: renovacao 10 30", "não pediu nada sobre a renovação"),
    ("desligue o gerente", "EXECUTAR: gerente ligar", "DESLIGAR"),
])
def test_acao_de_estado_que_o_adrian_nao_pediu_nao_roda(mesa, delegados, texto, resposta,
                                                         porque):
    antes = delegados.ler_config()
    _terminar(mesa, resposta, arquivos=0, aplicado=False, texto=texto)
    assert delegados.ler_config() == antes
    atual = _pedido(mesa)
    assert atual["situacao"] == "esperando_voce" and porque in atual["motivo"]
    assert "não executei" in mesa.avisos[-1]


def test_paralelo_que_o_adrian_nao_pediu_nao_chega_na_mesa(mesa, monkeypatch):
    monkeypatch.setattr(pedidos, "_servidor_paralelo",
                        lambda args: pytest.fail("mudou o paralelo sem o Adrian pedir"))
    _terminar(mesa, "EXECUTAR: paralelo 8", arquivos=0, aplicado=False, texto="corrija X")
    assert _pedido(mesa)["situacao"] == "esperando_voce"


def test_lista_de_acoes_devolvida_pelo_servidor_nao_autoriza(mesa, delegados):
    """A recusa devolve a lista de acoes (com "gerente") ao `texto` do pedido:
    isso nao e o Adrian pedindo."""
    p = _terminar(mesa, "EXECUTAR: gerente talvez", arquivos=0, aplicado=False,
                  texto="corrija X")
    assert "gerente" in _pedido(mesa)["texto"]
    _andar(mesa, 2)                       # a continuacao sai e ele roda
    mesa.despachante.terminar(p["id"], resposta="EXECUTAR: gerente ligar", arquivos=0,
                              aplicado=False)
    mesa.passo()
    assert delegados.ler_config()["gerente_ligado"] is False
    assert _pedido(mesa)["situacao"] == "esperando_voce"


def test_o_adrian_autoriza_na_resposta_e_o_servidor_executa(mesa, delegados):
    p = _terminar(mesa, "EXECUTAR: gerente ligar", arquivos=0, aplicado=False,
                  texto="corrija X")
    assert _pedido(mesa)["situacao"] == "esperando_voce"
    volta = mesa.registrar("pode ligar o gerente")
    assert volta["id"] == p["id"]
    _andar(mesa, 3)                       # destrava, a continuacao sai e ele roda
    assert mesa.despachante.fundos[-1][:3] == ["corrigir", "--id", p["id"]]
    mesa.despachante.terminar(p["id"], resposta="EXECUTAR: gerente ligar", arquivos=0,
                              aplicado=False)
    mesa.passo()
    assert delegados.ler_config()["gerente_ligado"] is True
    assert _pedido(mesa)["situacao"] == "respondido"


def test_contexto_do_no_do_grimorio_nao_autoriza():
    """O cb44 real: o contexto do no fala em "paralelo"; ele escolheu so ligar."""
    texto = ("O Adrian respondeu no Grimório (geral/gerente-ligado): «Ligar o gerente da "
             "equipe?»\nPergunta: O gerente pode tocar a fila sozinho?\nEscolheu: Ligar\n"
             "Contexto do nó: Ligado, ele contrata em paralelo e renova a conversa.\n\n"
             "APLIQUE a escolha: faça o que ela pede.")
    assert pedidos.autorizada_pelo_adrian("gerente", ["ligar"], texto) == ""
    assert pedidos.autorizada_pelo_adrian("paralelo", ["8"], texto)
    assert pedidos.autorizada_pelo_adrian("renovacao", ["10", "30"], texto)
    assert pedidos.autorizada_pelo_adrian("gerente", ["ligar"], "")              # caso zero


# ================================================ conferente 4: pedido novo nao gruda
def _bloqueado_do_drive(mesa):
    return _terminar(mesa, RESPOSTA_CD2E, aplicado=False, diff=DIFF_SO_RESPOSTA,
                     texto="arquive os vídeos antigos no Google Drive")


def test_pedido_novo_nao_gruda_no_bloqueado(mesa):
    drive = _bloqueado_do_drive(mesa)
    antes = _pedido(mesa, drive["id"])["texto"]
    novo = mesa.registrar("Faz o backup das fotos")
    assert novo["id"] != drive["id"] and novo["continuacao"] is False
    assert _pedido(mesa, drive["id"])["texto"] == antes
    mesa.passo()
    assert _pedido(mesa, drive["id"])["situacao"] == "esperando_voce"   # nao destravou


def test_resposta_ao_bloqueio_vai_ao_pedido_certo(mesa):
    drive = _bloqueado_do_drive(mesa)
    mesa.novo_assunto()
    gerente = _terminar(mesa, RESPOSTA_CB44, aplicado=False, diff=DIFF_SO_RESPOSTA,
                        texto="ligue o gerente")
    assert _pedido(mesa, gerente["id"])["situacao"] == "esperando_voce"
    # o do gerente e o mais novo, mas a mensagem fala do Drive
    r = mesa.registrar("já loguei no Drive")
    assert r["id"] == drive["id"] and r["continuacao"] is True
    # forma de continuacao sem palavra em comum: vai ao mais novo
    assert mesa.registrar("pode tentar de novo")["id"] == gerente["id"]


def test_pedido_novo_nao_gruda_no_entregue(mesa):
    p = _terminar(mesa, "Consertei.\nDESFECHO: feito", aplicado=False)
    assert _pedido(mesa, p["id"])["situacao"] == "entregue"
    assert mesa.registrar("Faz o backup das fotos")["id"] != p["id"]
    assert mesa.registrar("e confira no celular")["continuacao"] is True


def test_pedido_ativo_recebe_como_antes(mesa):
    p = mesa.registrar("corrija X")
    mesa.passo()
    assert mesa.registrar("Faz o backup das fotos")["id"] == p["id"]


def test_caso_zero_sem_pedido_nenhum_abre_novo(mesa):
    assert mesa.registrar("pode ligar")["continuacao"] is False


# ================================================ conferente 5: o laco do pid morto
def test_rodando_com_pid_morto_retoma_sem_laco(mesa):
    """O 7c727778 real: pid 11412 morto, ficha "rodando", `parar` recusa pid
    morto; o pulso alternava "parei" / "de volta" para sempre."""
    p = mesa.registrar("corrija X")
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
    textos = [c["texto"] for c in mesa.para_o_app()["conversa"]]
    assert not any("de volta" in t for t in textos)


def test_trabalhador_vivo_e_mudo_nao_vira_laco(mesa):
    p = mesa.registrar("corrija X")
    mesa.passo()
    mesa.despachante.estados[p["id"]]["pid"] = 999
    mesa.despachante._pid_vivo = lambda pid: True
    mesa.relogio.andar(minutes=11)
    for _ in range(40):                       # 4 min de pulsos de 6 s
        mesa.relogio.andar(seconds=6)
        mesa.passo()
    linhas = [c for c in mesa.para_o_app()["conversa"] if c["pedido"] == p["id"]]
    assert len(linhas) <= 8, [c["texto"] for c in linhas]
    assert not any("de volta" in c["texto"] for c in linhas)
    assert _pedido(mesa)["situacao"] == "esperando"
    assert 2 <= len(mesa.despachante.parados) <= 3       # repete o parar a cada RETOMAR_S
