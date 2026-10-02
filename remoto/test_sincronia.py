# -*- coding: utf-8 -*-
"""Sincronia entre o que o app mostra e o que acontece no PC (29/09/2026).

Pedido do Adrian: "cuide desse problema de sincronização que existe hoje no
app". O que foi medido e vira teste aqui:

- 00:58:45 ele tocou "retomar a fila"; o comando ficou PENDENTE ate 01:01:21
  (2 min 36 s), porque o `esperar` do orquestrador estava desligado desde um
  checkpoint. A Mesa dizia "no ar": qualquer comando da CLI renova o sinal da
  sessao, e ninguem distinguia "sessao aberta" de "alguem ouvindo";
- 01:15:19 tres toques rapidos no "+" gravaram max_paralelo 4, 4 e 5 no
  mesmo segundo (duas respostas no Grimorio para uma mudanca so);
- a casca aberta no celular nao sabe que o servidor mudou (o cache foi do v8
  ao v13 em 28/09); as horas vao sem fuso para um celular de relogio proprio;
- a resposta dada numa tela velha trocava a decisao por cima de outra.

Tudo em `tmp_path` (no E:, pelo --basetemp). Nada toca o `%LOCALAPPDATA%`
real, o repositorio real, a rede ou o Telegram.
"""
from __future__ import annotations

import http.client
import json
import os
import time
from datetime import datetime, timedelta

import pytest

from remoto import api_http, decisoes as D, orquestrador as O, painel_dados
# as mesmas bancadas da Mesa: pasta do orquestrador, Grimorio num git temporario
from remoto.test_orquestrador import _parear, _pedir, mundo, servidor  # noqa: F401


def _iso(segundos_atras: float) -> str:
    return (datetime.now() - timedelta(seconds=segundos_atras)).isoformat(timespec="seconds")


def _vigia_em(mundo, dados: dict) -> None:
    pasta = mundo.tmp / "orquestrador"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "vigia.json").write_text(json.dumps(dados), encoding="utf-8")


def _comando_de(mundo, segundos_atras: float, comando="retomar_fila", valor=None,
                cid="49cfa9bb"):
    pasta = mundo.tmp / "orquestrador"
    pasta.mkdir(parents=True, exist_ok=True)
    with open(pasta / "comandos.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": cid, "em": _iso(segundos_atras), "comando": comando,
                             "valor": valor, "aparelho": "614c026b"}) + "\n")


# ============================================================ caso ZERO
def test_caso_zero_sem_vigia_sem_sessao_sem_comando(mundo):
    v = O.situacao_do_vigia()
    assert v["situacao"] == "fechada" and v["nunca_ligou"] is True
    assert "nunca deu sinal" in v["texto"]
    tela = O.para_o_app()
    assert tela["vigia"]["situacao"] == "fechada"
    assert tela["sem_ouvinte"] is None
    # ler nao cria nada, e o aviso do Telegram nao fala de nada
    assert O._AvisoSemOuvinte.verificar(avisar=pytest.fail) is None
    assert not (mundo.tmp / "orquestrador").exists()


# ================================================ as tres situacoes da Mesa
def test_ouvindo_so_com_pulso_novo_e_processo_vivo(mundo, monkeypatch):
    monkeypatch.setattr(O, "_pid_vivo", lambda pid: True)
    O.vigia_pulsar(_iso(600), pid=4242)
    v = O.situacao_do_vigia()
    assert v["situacao"] == "ouvindo" and "está ouvindo" in v["texto"]
    # tres pulsos perdidos (91 s): nao esta mais ouvindo
    assert O.situacao_do_vigia(time.time() + 91)["situacao"] != "ouvindo"
    # processo morto a forca: nem espera o pulso envelhecer
    monkeypatch.setattr(O, "_pid_vivo", lambda pid: False)
    assert O.situacao_do_vigia()["situacao"] != "ouvindo"


def test_pid_vivo_de_verdade():
    assert O._pid_vivo(os.getpid()) is True
    assert O._pid_vivo(0) is None and O._pid_vivo("x") is None


def test_a_reproducao_de_29_09_as_00h58(mundo, monkeypatch):
    """Sessao aberta (um relato de agora), vigia desligado desde o checkpoint
    das 00:20, "retomar a fila" pendente ha 2 min 36 s. O campo antigo dizia
    que estava tudo bem; a Mesa agora diz quem NAO esta ouvindo."""
    monkeypatch.setattr(O, "_pid_vivo", lambda pid: False)
    O.pulso()                                        # a CLI deu sinal agora
    _vigia_em(mundo, {"situacao": "saiu", "pid": 999, "desde": _iso(3000),
                      "pulso_em": _iso(2340), "saiu_em": _iso(2330),
                      "motivo": "interrompido"})
    _comando_de(mundo, 156)
    tela = O.para_o_app()
    assert tela["fora_do_ar"] is False               # o sinal antigo: "tudo bem"
    assert tela["vigia"]["situacao"] == "fora"
    assert "o vigia está desligado há 38 min" in tela["vigia"]["texto"]
    aviso = tela["sem_ouvinte"]
    assert aviso["tipo"] == "sem_ouvinte" and aviso["comando"] == "49cfa9bb"
    assert aviso["texto"].startswith("Ninguém está ouvindo agora; o comando será "
                                     "aplicado quando o orquestrador voltar.")
    assert "«retomar a fila»" in aviso["texto"]


def test_sessao_fechada_diz_que_os_agentes_podem_nao_rodar(mundo):
    O.agente_inicio("builds", "re-render", forcar=True)
    caminho = mundo.tmp / "orquestrador" / "estado.json"
    estado = json.loads(caminho.read_text(encoding="utf-8"))
    estado["atualizado_em"] = _iso(40 * 60)
    caminho.write_text(json.dumps(estado), encoding="utf-8")
    v = O.situacao_do_vigia()
    assert v["situacao"] == "fechada"
    assert "sem sinal do orquestrador desde" in v["texto"]
    assert "O agente da lista pode não estar rodando" in v["texto"]


def test_acordou_com_comando_e_aplicando_ate_3_min(mundo, monkeypatch):
    O.pulso()
    _vigia_em(mundo, {"situacao": "saiu", "pid": 1, "desde": _iso(100),
                      "pulso_em": _iso(20), "saiu_em": _iso(10), "motivo": "comando"})
    _comando_de(mundo, 200)
    v = O.situacao_do_vigia()
    assert v["situacao"] == "acordou"
    # acordou = esta aplicando: nao e "ninguem ouvindo"
    assert O.sem_ouvinte(O.comandos_com_situacao()[0], v) is None
    assert O.situacao_do_vigia(time.time() + 181)["situacao"] == "fora"


def test_sem_ouvinte_so_depois_de_2_min_e_preso_quando_ouvindo(mundo, monkeypatch):
    # 100 s e nao 119: com a maquina carregada a suite levava >1 s ate aqui e o
    # comando "de 119 s" ja tinha 120,004 s (barrou a entrega da Arena, 02/10)
    _comando_de(mundo, 100)
    fora = {"situacao": "fora"}
    assert O.sem_ouvinte(O.comandos_com_situacao()[0], fora) is None
    assert O.sem_ouvinte(O.comandos_com_situacao()[0], fora, time.time() + 21)["tipo"] \
        == "sem_ouvinte"
    # ouvindo e ainda pendente depois de 2 min: travou do lado dele
    preso = O.sem_ouvinte(O.comandos_com_situacao()[0], {"situacao": "ouvindo"},
                          time.time() + 60)
    assert preso["tipo"] == "preso" and "Algo travou" in preso["texto"]


# ============================================================ o `esperar`
class _Relogio:
    def __init__(self):
        self.t = time.time()

    def agora(self):
        return self.t


def test_esperar_pulsa_a_cada_30_s_e_registra_a_saida(mundo, monkeypatch, capsys):
    relogio = _Relogio()
    pulsos, voltas = [], {"n": 0}
    real = O.vigia_pulsar
    monkeypatch.setattr(O, "vigia_pulsar",
                        lambda desde, pid=None: (pulsos.append(relogio.t), real(desde, pid)))

    def dormir(s):
        relogio.t += s
        voltas["n"] += 1
        if voltas["n"] == 3:                           # 3 x 5 s = pulso ainda nao
            assert O.situacao_do_vigia()["situacao"] == "ouvindo"
        if voltas["n"] == 13:                          # chega o comando
            O.gravar_comando("retomar_fila", None, "614c026b")

    assert O.esperar(5.0, relogio=relogio.agora, dormir=dormir) == 0
    assert "retomar_fila" in capsys.readouterr().out
    # 13 voltas de 5 s = 65 s: pulsou em 0, 30 e 60
    assert len(pulsos) == 3
    vigia = json.loads((mundo.tmp / "orquestrador" / "vigia.json").read_text(encoding="utf-8"))
    assert vigia["situacao"] == "saiu" and vigia["motivo"] == "comando"
    assert O.situacao_do_vigia()["situacao"] == "acordou"


def test_esperar_interrompido_fica_registrado(mundo):
    def dormir(_s):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        O.esperar(5.0, dormir=dormir)
    vigia = json.loads((mundo.tmp / "orquestrador" / "vigia.json").read_text(encoding="utf-8"))
    assert vigia["situacao"] == "saiu" and vigia["motivo"] == "interrompido"
    O.pulso()
    assert O.situacao_do_vigia()["situacao"] == "fora"


def test_esperar_com_registro_ilegivel_sai_com_o_motivo(mundo, capsys):
    pasta = mundo.tmp / "orquestrador"
    pasta.mkdir(parents=True)
    (pasta / "decisoes_vistas.json").write_text("{", encoding="utf-8")
    # ilegivel: o esperar sai (codigo 3 na CLI), e o motivo fica no vigia
    assert O.main(["esperar", "--intervalo", "1"]) == 3
    assert "ilegível" in capsys.readouterr().err
    vigia = json.loads((pasta / "vigia.json").read_text(encoding="utf-8"))
    assert vigia["situacao"] == "saiu" and vigia["motivo"].startswith("erro:")


def test_dois_esperar_a_saida_de_um_nao_apaga_o_pulso_do_outro(mundo, monkeypatch):
    monkeypatch.setattr(O, "_pid_vivo", lambda pid: True)
    O.vigia_pulsar(_iso(10), pid=111)
    assert O.vigia_saiu("comando", _iso(50), pid=222) is False
    assert O.situacao_do_vigia()["situacao"] == "ouvindo"


def test_cli_vigia_diz_quem_ouve(mundo, capsys):
    assert O.main(["vigia"]) == 1
    assert "fechada" in capsys.readouterr().out


# ================================= aviso no Telegram, uma vez por ocorrencia
def test_aviso_uma_vez_por_ocorrencia_e_o_voltou(mundo, monkeypatch):
    monkeypatch.setattr(O, "_pid_vivo", lambda pid: True)
    O.pulso()
    _comando_de(mundo, 150)
    enviados = []
    texto = O._AvisoSemOuvinte.verificar(avisar=enviados.append)
    assert texto and "Ninguém está ouvindo agora" in texto and len(enviados) == 1
    # mesma ocorrencia, e o servidor que reinicia: nada de novo
    assert O._AvisoSemOuvinte.verificar(avisar=enviados.append) is None
    assert O._AvisoSemOuvinte().verificar(avisar=enviados.append) is None
    # outro comando na mesma ocorrencia: ainda nada
    _comando_de(mundo, 130, comando="pausar_fila", cid="aaaa0001")
    assert O._AvisoSemOuvinte.verificar(avisar=enviados.append) is None
    # o orquestrador volta e aplica: um aviso de volta, com a demora
    O.aplicado("49cfa9bb")
    O.aplicado("aaaa0001")
    volta = O._AvisoSemOuvinte.verificar(avisar=enviados.append)
    assert volta.startswith("✓ Mesa de comando: o orquestrador voltou e aplicou «retomar a fila»")
    assert "ficou pendente 2 min" in volta
    assert len(enviados) == 2
    assert O._AvisoSemOuvinte.verificar(avisar=enviados.append) is None


def test_o_servidor_liga_o_aviso():
    fonte = api_http.Path(api_http.__file__).read_text(encoding="utf-8")
    assert "orquestrador.AVISO_SEM_OUVINTE.iniciar()" in fonte


# ===================================== toque repetido nao vira comando repetido
def test_toques_rapidos_nao_gravam_o_mesmo_comando_duas_vezes(mundo):
    # 29/09 01:15:19: 4, 4 e 5 no mesmo segundo
    a = O.gravar_comando("max_paralelo", 4, "614c026b")
    b = O.gravar_comando("max_paralelo", 4, "614c026b")
    c = O.gravar_comando("max_paralelo", 5, "614c026b")
    assert b["repetido"] is True and b["id"] == a["id"]
    assert "repetido" not in c
    assert [x["valor"] for x in O.pendentes()] == [4, 5]
    # depois de aplicado, o mesmo pedido de novo e um pedido novo
    O.aplicado(a["id"])
    d = O.gravar_comando("max_paralelo", 4, "614c026b")
    assert "repetido" not in d and d["id"] != a["id"]
    # "subir" duas vezes e subir duas posicoes: esse soma
    O.fila_adicionar("builds", "x")
    item = O.fila_adicionar("builds", "y")
    for _ in range(2):
        O.gravar_comando("priorizar", {"item": item["id"], "direcao": "subir"}, "614c026b")
    assert sum(1 for x in O.pendentes() if x["comando"] == "priorizar") == 2


def test_rota_do_comando_diz_se_alguem_ouve_e_se_repetiu(servidor, mundo):
    token = _parear(servidor)
    status, r = _pedir(servidor, "POST", "/api/orquestrador/comando",
                       {"comando": "pausar_fila", "valor": None}, token)
    assert status == 200 and r["vigia"]["situacao"] == "fechada"
    status, r2 = _pedir(servidor, "POST", "/api/orquestrador/comando",
                        {"comando": "pausar_fila", "valor": None}, token)
    assert status == 200 and r2["comando"]["repetido"] is True
    assert r2["comando"]["id"] == r["comando"]["id"]
    status, tela = _pedir(servidor, "GET", "/api/orquestrador", token=token)
    assert tela["pendentes"] == 1 and tela["vigia"]["situacao"] == "fechada"


# ============================================ a casca e o relogio do PC
def _cru(srv, caminho, token=None):
    porta = srv.server_address[1]
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=15)
    cab = {"Host": f"127.0.0.1:{porta}"}
    if token:
        cab["Authorization"] = f"Bearer {token}"
    conexao.request("GET", caminho, headers=cab)
    resposta = conexao.getresponse()
    corpo = resposta.read()
    conexao.close()
    return resposta, corpo


def test_toda_resposta_json_leva_a_casca_e_o_relogio(servidor, mundo, tmp_path, monkeypatch):
    casca = tmp_path / "casca"
    casca.mkdir()
    for nome in {a for a, _t in api_http.ESTATICOS.values()}:
        (casca / nome).parent.mkdir(parents=True, exist_ok=True)   # icones/ (29/09)
        (casca / nome).write_bytes((api_http.APP / nome).read_bytes())
    monkeypatch.setattr(api_http, "APP", casca)
    token = _parear(servidor)
    resposta, _ = _cru(servidor, "/api/orquestrador", token)
    versao = resposta.getheader("X-Casca")
    assert versao and len(versao) == 12
    assert resposta.getheader("Date")
    assert int(resposta.getheader("X-Fuso-Min")) == api_http.fuso_do_pc_min()
    # o index.html sai com a MESMA versao (e o app compara as duas)
    _, html = _cru(servidor, "/")
    assert f'<meta name="casca" content="{versao}">'.encode() in html
    # erro tambem leva (o 401 e a primeira coisa que uma casca velha ve)
    resposta, _ = _cru(servidor, "/api/estado")
    assert resposta.status == 401 and resposta.getheader("X-Casca") == versao
    # um arquivo da casca muda no disco: a versao muda na hora, sem reiniciar
    js = casca / "orquestrador.js"
    js.write_bytes(js.read_bytes() + b"\n// mudou\n")
    resposta, _ = _cru(servidor, "/api/orquestrador", token)
    assert resposta.getheader("X-Casca") != versao


def test_o_html_do_disco_tem_o_lugar_da_versao():
    html = (api_http.APP / "index.html").read_text(encoding="utf-8")
    assert '<meta name="casca" content="">' in html
    assert 'id="casca-nova"' in html and 'id="btn-recarregar"' in html


# ================================== resposta dada numa tela velha
def _uma_decisao(mundo):
    D.adicionar("geral", "Teste de sincronia", "Qual?", ["a=Opção A", "b=Opção B"],
                id="teste-sincronia")
    return D.carregar()["teste-sincronia"]


def test_resposta_de_tela_velha_e_recusada_e_nada_muda(mundo):
    _uma_decisao(mundo)
    primeira = D.responder("teste-sincronia", "a", esperava="", commitar=False)
    # outra aba ainda mostrava "sem resposta" e responde B
    linhas = D.caminho_eventos().read_text(encoding="utf-8").splitlines()
    with pytest.raises(D.Recusa, match="mudou enquanto a tela estava aberta"):
        D.responder("teste-sincronia", "b", esperava="", commitar=False)
    assert D.caminho_eventos().read_text(encoding="utf-8").splitlines() == linhas
    assert D.carregar()["teste-sincronia"]["vigente"]["opcao"] == "a"
    # a tela que viu a resposta A pode trocar
    D.responder("teste-sincronia", "b", esperava=primeira["em"], commitar=False)
    assert D.carregar()["teste-sincronia"]["vigente"]["opcao"] == "b"
    # sem `esperava` (a casca antiga) segue como antes
    D.responder("teste-sincronia", "a", commitar=False)


def test_rota_responder_com_tela_velha_da_409(servidor, mundo):
    _uma_decisao(mundo)
    token = _parear(servidor)
    status, r = _pedir(servidor, "POST", "/api/decisao/responder",
                       {"id": "teste-sincronia", "opcao": "a", "esperava": ""}, token)
    assert status == 200
    status, r = _pedir(servidor, "POST", "/api/decisao/responder",
                       {"id": "teste-sincronia", "opcao": "b", "esperava": ""}, token)
    assert status == 409 and "mudou enquanto" in r["erro"]
    status, dados = _pedir(servidor, "GET", "/api/decisoes", token=token)
    assert status == 200 and dados["vigia"]["situacao"] == "fechada"
    assert dados["itens"]["teste-sincronia"]["vigente"]["opcao"] == "a"


# ======================================== o dado guardado diz a propria idade
def test_previsao_velha_vem_marcada(monkeypatch):
    previsao = painel_dados._Previsao()
    monkeypatch.setattr(previsao, "disponivel", lambda: True)
    monkeypatch.setattr(previsao, "_calcular", lambda: None)
    previsao._valor, previsao._quando = {"builds": {"titulo": "x"}}, time.time()
    assert previsao.ler()["vencida"] is False
    previsao._quando = time.time() - 39 * 60
    lida = previsao.ler()
    assert lida["vencida"] is True and lida["idade_s"] >= 39 * 60


def test_fluxo_velho_vem_marcado(monkeypatch):
    fluxo = painel_dados._Fluxo()
    monkeypatch.setattr(fluxo, "_calcular", lambda: None)
    fluxo._valor, fluxo._quando = {"etapas": []}, time.time() - 600
    assert fluxo.ler()["vencida"] is True
