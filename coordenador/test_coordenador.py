# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

import pytest

from coordenador import acoes_pc
from coordenador.__main__ import xml_tarefa
from coordenador.estado import gravar_estado, ler_estado
from coordenador.supervisor import Supervisor, TravaUnica


class Relogio:
    def __init__(self):
        self.agora = datetime(2026, 10, 1, 3, 0)

    def __call__(self):
        return self.agora

    def andar(self, segundos):
        self.agora += timedelta(seconds=segundos)


def ficha(nome="app", seguro=False):
    return {nome: {"nome": nome, "assinatura": nome, "comando": [nome], "cwd": ".",
                   "log": "coordenador-teste.log", "janela": "oculta", "modulos": [],
                   "reinicio_seguro": seguro}}


class Mundo:
    """Processos de mentira em que `parar` MATA (o pid some da lista) e
    `iniciar` faz nascer: sem isso, `reiniciar_servico` (que confere a morte
    do velho antes de subir o novo) esperaria um morto que nunca morre."""
    def __init__(self, *processos):
        # o Windows nunca lista vazio: lista vazia e consulta que falhou
        self.lista = [{"pid": 4, "comando": "System"}] + [dict(p) for p in processos]
        self.parou, self.iniciou, self.proximo = [], [], 100

    def processos(self):
        return [dict(p) for p in self.lista]

    def parar(self, pid):
        self.parou.append(pid)
        self.lista = [p for p in self.lista if p["pid"] != pid]

    def iniciar(self, ficha):
        pid, self.proximo = self.proximo, self.proximo + 1
        self.iniciou.append(pid)
        self.lista.append({"pid": pid, "comando": " ".join(ficha["comando"])})
        return pid


def supervisor(**mais):
    relogio = mais.pop("relogio", Relogio())
    opcoes = {"porta": lambda: True, "carteiro": lambda: {"situacao": "ocioso"},
              "git": lambda *_: False, "avisar": lambda *_: None, "gravar": lambda _: None,
              "log": lambda _: None, "janela": lambda _agora: (False, ""),
              "dormir": lambda _s: None, "carregar": lambda: {}, "pendentes": lambda: []}
    opcoes.update(mais)
    return Supervisor(servicos=opcoes.pop("servicos", ficha()), relogio=relogio,
                      **opcoes), relogio


def test_adota_existente_sem_duplicar():
    iniciou = []
    s, _ = supervisor(processos=lambda: [{"pid": 12, "comando": "app --ja"}],
                       iniciar=lambda _: iniciou.append(1) or 13)
    s.pulso()
    assert s.estado["app"]["pid"] == 12
    assert iniciou == []


def test_assembleia_avanca_em_fundo_no_maximo_a_cada_cinco_minutos():
    chamadas = []
    s, relogio = supervisor(assembleia=lambda: chamadas.append("avancou"),
                            em_fundo=lambda nome, funcao: funcao() or True)
    s.avancar_assembleia(); s.avancar_assembleia()
    assert chamadas == ["avancou"]
    relogio.andar(300); s.avancar_assembleia()
    assert chamadas == ["avancou", "avancou"]


def test_adotado_guarda_a_hora_em_que_o_processo_nasceu():
    # 01/10: adotar com a hora da adocao fez o bot (vivo desde 28/09) sair
    # "codigo em dia"; o codigo velho tem de ser medido contra o nascimento.
    s, _ = supervisor(processos=lambda: [{"pid": 12, "comando": "app --ja",
                                          "inicio": "2026-09-28T12:58:17"}])
    s.pulso()
    assert s.estado["app"]["desde"] == "2026-09-28T12:58:17"


def test_religa_com_espera_crescente_e_limite_avisa():
    iniciou, avisos = [], []
    def quebra(_):
        iniciou.append(1)
        raise OSError("nao subiu")
    s, relogio = supervisor(processos=lambda: [{"pid": 4, "comando": "System"}], iniciar=quebra, avisar=avisos.append)
    s.pulso()
    relogio.andar(4); s.pulso()
    assert len(iniciou) == 1
    relogio.andar(1); s.pulso()
    assert len(iniciou) == 2
    for _ in range(4):
        relogio.andar(301); s.pulso()
    assert s.estado["app"]["situacao"] == "falhou"
    assert avisos


def test_reinicio_pedido_com_codigo_velho_espera_publicacao_e_depois_reinicia():
    # D3 (13/10): o codigo velho sozinho nao reinicia; o PEDIDO espera a
    # publicacao em voo acabar e entao reinicia
    mundo = Mundo({"pid": 10, "comando": "app"}, {"pid": 20, "comando": "postar.py"})
    s, _ = supervisor(processos=mundo.processos, git=lambda *_: True,
                      parar=mundo.parar, iniciar=mundo.iniciar)
    s.pulso()
    assert s.estado["app"]["codigo_velho"]
    s.pedir_reinicio("app")
    s.pulso()
    assert not mundo.parou and s.estado["app"]["motivo_espera"] == "publicacao em andamento"
    mundo.lista = [p for p in mundo.lista if p["pid"] != 20]      # a publicacao acabou
    s.pulso()
    assert mundo.parou == [10] and mundo.iniciou == [100]
    assert "app" not in s.reinicio_pedido


def test_carteiro_entregando_adia_reinicio_pedido():
    parou = []
    s, _ = supervisor(servicos=ficha("carteiro", True), processos=lambda: [{"pid": 10, "comando": "carteiro"}],
                      git=lambda *_: True, carteiro=lambda: {"situacao": "entregando"}, parar=parou.append)
    s.pedir_reinicio("carteiro")
    s.pulso()
    assert s.estado["carteiro"]["motivo_espera"] == "carteiro entregando"
    assert not parou


def test_carteiro_entregando_espera_no_maximo_dez_minutos(monkeypatch):
    # 02/10 00:04: "ele nunca vai parar de rodar" - a espera tem teto.
    from coordenador import supervisor as mod
    monkeypatch.setattr(mod.Supervisor, "_interromper_entrega", lambda self: None)
    mundo = Mundo({"pid": 10, "comando": "carteiro"})
    s, relogio = supervisor(servicos=ficha("carteiro", True), processos=mundo.processos,
                            git=lambda *_: True, carteiro=lambda: {"situacao": "entregando"},
                            parar=mundo.parar, iniciar=mundo.iniciar)
    s.pedir_reinicio("carteiro")
    s.pulso()
    assert not mundo.parou
    relogio.andar(mod.ESPERA_ENTREGA_S + 1); s.pulso()
    assert mundo.parou == [10] and mundo.iniciou == [100]


def test_proibido_para_delegados_sem_parar_servico():
    delegados, parou = [], []
    s, _ = supervisor(processos=lambda: [{"pid": 7, "comando": "app"}], claude_proibido=lambda: "proibido",
                      delegados=lambda: ["a1"], parar_delegado=delegados.append, parar=parou.append)
    s.pulso()
    assert delegados == ["a1"] and parou == [] and s.estado["app"]["situacao"] == "rodando"


def test_comandos_so_os_novos_e_acao_fora_do_catalogo_recusada():
    feitos = []
    fila = [{"id": "1", "comando": "mensagem", "valor": "oi"},
            {"id": "2", "comando": "pc_acao", "valor": "nao-existe"}]
    s, _ = supervisor(processos=lambda: [{"pid": 4, "comando": "System"}], comandos=lambda: fila,
                      aplicar=lambda ident, **kw: feitos.append((ident, kw)))
    s.processar_comandos()
    assert feitos[0][0] == "2" and "recusado" in feitos[0][1]
    assert all(ident != "1" for ident, _ in feitos)


def test_o_pulso_aplica_os_comandos_do_app_sem_a_sessao(monkeypatch):
    # 04/10: capacidade, fila, parar, modelos e mensagem saem no pulso, por
    # `aplicar_app` (orquestrador.aplicar_pelo_servidor); servico continua aqui
    vistos, feitos = [], []
    fila = [{"id": "1", "comando": "mensagem", "valor": "oi"},
            {"id": "2", "comando": "max_paralelo", "valor": 3},
            {"id": "3", "comando": "servico_ligar", "valor": "app"}]

    def aplicar_app(comando):
        vistos.append(comando["id"])
        return {"id": comando["id"], "resultado": "aplicado", "nota": "virou o pedido p1"}
    s, _ = supervisor(processos=lambda: [{"pid": 4, "comando": "System"}], comandos=lambda: fila,
                      aplicar=lambda ident, **kw: feitos.append(ident), aplicar_app=aplicar_app,
                      iniciar=lambda _: 9)
    s.pulso()
    assert vistos == ["1", "2"] and feitos == ["3"]
    textos = [e["texto"] for e in s.eventos if e["tipo"] == "comando" and not e["servico"]]
    assert textos == ["aplicado mensagem: virou o pedido p1", "aplicado max_paralelo: virou o pedido p1"]


def test_erro_ao_aplicar_comando_do_app_vira_um_evento_e_nao_para_o_pulso():
    fila = [{"id": "1", "comando": "mensagem", "valor": "oi"}]

    def quebra(_comando):
        raise OSError("disco cheio")
    gravados = []
    s, _ = supervisor(processos=lambda: [{"pid": 4, "comando": "System"}], comandos=lambda: fila,
                      aplicar=lambda *a, **k: None, aplicar_app=quebra, gravar=gravados.append)
    s.pulso()
    s.pulso()
    assert [e["tipo"] for e in s.eventos].count("comando_erro") == 1
    assert len(gravados) == 2                      # o pulso seguiu e publicou o estado


def test_rodar_tarefa_so_prefixos_permitidos():
    chamadas = []
    acoes_pc.executar("rodar_tarefa:NeuralFights_postar_06", rodar=lambda *a, **k: chamadas.append(a))
    assert chamadas
    with pytest.raises(ValueError):
        acoes_pc.executar("rodar_tarefa:Outra")


def test_trava_unica(tmp_path):
    primeira, segunda = TravaUnica(tmp_path / "coordenador.lock"), TravaUnica(tmp_path / "coordenador.lock")
    assert primeira.adquirir() and not segunda.adquirir()
    primeira.soltar()


def test_estado_contrato_atomico(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path))
    dados = {"pid": 1, "desde": "x", "pulso_em": "x", "versao": "abc",
             "servicos": {}, "acoes_pc": [], "eventos": []}
    gravar_estado(dados)
    assert ler_estado() == dados


def test_xml_tem_logon_reinicio_e_bateria():
    xml = xml_tarefa("wscript.exe")
    assert "LogonTrigger" in xml and "RestartOnFailure" in xml and "PT1M" in xml
    assert "DisallowStartIfOnBatteries>false" in xml


def test_lista_de_processos_vazia_nao_derruba_nada():
    # 01/10 23:56: a consulta do Windows voltou vazia e o coordenador "religou" tudo.
    iniciou = []
    s, _ = supervisor(processos=lambda: [{"pid": 12, "comando": "app --ja"}],
                      iniciar=lambda _: iniciou.append(1) or 13)
    s.pulso()
    s.processos = lambda: []
    s.pulso()
    assert iniciou == [] and s.estado["app"]["situacao"] == "rodando"


def test_uma_ausencia_so_nao_religa_a_segunda_religa():
    iniciou = []
    vivos = [{"pid": 12, "comando": "app --ja"}]
    s, relogio = supervisor(processos=lambda: list(vivos) + [{"pid": 4, "comando": "System"}],
                            iniciar=lambda _: iniciou.append(1) or 13)
    s.pulso()
    vivos.clear()
    relogio.andar(5); s.pulso()
    assert iniciou == []
    relogio.andar(5); s.pulso()
    relogio.andar(6); s.pulso()
    assert iniciou


def test_trava_de_processo_morto_e_retomada(tmp_path):
    # 02/10: o coordenador morto deixava o .lock e nenhum outro subia mais.
    from coordenador.supervisor import TravaUnica
    caminho = tmp_path / "c.lock"
    caminho.write_text("999999", encoding="utf-8")
    assert TravaUnica(caminho).adquirir(vivo=lambda pid: False)
    caminho.write_text("4242", encoding="utf-8")
    # lock antigo (so o pid) de um coordenador vivo: respeita
    assert not TravaUnica(caminho).adquirir(
        vivo=lambda pid: True, comando=lambda pid: "python -m coordenador rodar")


# ------------------------------------------------ a esteira de sprites (02/10)
def test_esteira_roda_no_pulso_no_maximo_uma_vez_a_cada_5_min():
    # 02/10: ninguem chamava a esteira e 10 imagens ficaram paradas
    rodadas = []
    s, relogio = supervisor(processos=lambda: [{"pid": 12, "comando": "app --ja"}],
                            esteira=lambda: rodadas.append(1) or {},
                            em_fundo=lambda nome, f: f())
    s.pulso()
    assert rodadas == [1]
    relogio.andar(5); s.pulso()
    relogio.andar(289); s.pulso()
    assert rodadas == [1]
    relogio.andar(6); s.pulso()
    assert rodadas == [1, 1]
    assert s.resumo()["esteira"]["perfis"] == {}


def test_sem_esteira_ligada_o_pulso_nao_chama_nada():
    s, _ = supervisor(processos=lambda: [{"pid": 12, "comando": "app --ja"}],
                      em_fundo=lambda nome, f: (_ for _ in ()).throw(AssertionError(nome)))
    s.pulso()                       # o cerebro e o vigia tambem estao desligados
    assert s.esteira is None and s.ultima_esteira == {}


def test_esteira_so_vira_evento_quando_anda_ou_quebra():
    parado = {"codigo": 0, "andou": 0, "novos": [], "em_voo": 4, "saida": "{}"}
    resultados = [{"palco": dict(parado), "vila": dict(parado)},
                  {"palco": {**parado, "andou": 2, "novos": ["fogo"]},
                   "vila": {**parado, "codigo": 1, "saida": "ValueError: x"}}]
    s, relogio = supervisor(processos=lambda: [{"pid": 12, "comando": "app --ja"}],
                            esteira=lambda: resultados.pop(0),
                            em_fundo=lambda nome, f: f())
    s.pulso()
    assert not [e for e in s.eventos if e["tipo"] == "esteira"]
    relogio.andar(300); s.pulso()
    evento = [e for e in s.eventos if e["tipo"] == "esteira"][-1]["texto"]
    assert "palco: 2 andou, 1 novo(s)" in evento
    assert "vila: 0 andou" in evento and "codigo 1" in evento


def test_ciclo_das_esteiras_chama_palco_e_vila_em_subprocesso():
    import json
    import subprocess

    from coordenador.supervisor import ESTEIRA_PERFIS, ciclo_das_esteiras
    chamadas = []

    def rodar(comando, **kw):
        chamadas.append((comando, kw))
        if "vila" in comando:
            raise subprocess.TimeoutExpired(comando, kw["timeout"])
        linha = json.dumps({"perfil": "palco", "andou": 3, "em_voo": 4, "novos": ["a"]})
        return subprocess.CompletedProcess(comando, 0, stdout="aviso\n" + linha + "\n",
                                           stderr="")

    saida = ciclo_das_esteiras(rodar=rodar, python="py.exe", raiz="E:/x")
    assert ESTEIRA_PERFIS == ("palco", "vila")
    assert [c[0] for c in chamadas] == [
        ["py.exe", "-X", "utf8", "-m", "esteira_sprites", "--perfil", p, "ciclo"]
        for p in ESTEIRA_PERFIS]
    assert all(kw["cwd"] == "E:/x" and kw["timeout"] for _, kw in chamadas)
    assert saida["palco"]["andou"] == 3 and saida["palco"]["novos"] == ["a"]
    assert saida["palco"]["codigo"] == 0 and saida["palco"]["em_voo"] == 4
    assert saida["vila"]["codigo"] is None and saida["vila"]["saida"] == "TimeoutExpired"


def test_ciclo_com_saida_que_nao_e_json_nao_derruba():
    import subprocess

    from coordenador.supervisor import ciclo_das_esteiras
    saida = ciclo_das_esteiras(
        rodar=lambda c, **kw: subprocess.CompletedProcess(c, 1, stdout="",
                                                           stderr="Traceback\nErro: x"),
        python="py.exe")
    assert saida["palco"] == {"codigo": 1, "andou": 0, "novos": [], "em_voo": None,
                              "saida": "Erro: x"}


def test_ciclo_de_verdade_da_vila_anda_e_pede_ao_chatgpt(tmp_path, monkeypatch):
    """14/10/2026, esteira religada: o subprocesso REAL `esteira_sprites --perfil vila ciclo`
    pede ate o alvo, tudo na caixa do ChatGPT. Fichas e correio em pastas de teste: nenhum
    carteiro le essa caixa, nada gasta cota. (O palco fica de fora: ele marca a pagina do app.)"""
    import json
    import subprocess
    import sys
    from pathlib import Path

    from PIL import Image

    from coordenador.supervisor import ciclo_das_esteiras
    esteira, correio = tmp_path / "esteira", tmp_path / "correio"
    (esteira / "_mestra").mkdir(parents=True)
    Image.new("RGBA", (8, 8), (20, 20, 26, 255)).save(esteira / "_mestra" / "aprovada.png")
    monkeypatch.setenv("ESTEIRA_SPRITES_PASTA", str(esteira))
    monkeypatch.setenv("NF_IAS_PASTA", str(correio))

    def rodar(comando, **kw):
        if "vila" in comando:
            return subprocess.run(comando, **kw)
        return subprocess.CompletedProcess(comando, 0, stdout="{}\n", stderr="")

    raiz = Path(__file__).resolve().parents[1]
    saida = ciclo_das_esteiras(rodar=rodar, python=sys.executable, raiz=raiz)["vila"]
    assert saida["codigo"] == 0, saida
    assert len(saida["novos"]) == 2 and saida["em_voo"] == 2
    pedidos = [json.loads(linha) for linha in
               (correio / "chatgpt" / "correio.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(pedidos) == 2 and {p["tipo"] for p in pedidos} == {"imagem"}
    assert not (correio / "gemini").exists()
    for item_id in saida["novos"]:
        ficha_vila = json.loads((esteira / "vila" / item_id / "ficha.json").read_text(encoding="utf-8"))
        assert ficha_vila["estado"] == "pedido" and ficha_vila["tentativas"][-1]["caixa"] == "chatgpt"


def test_o_coordenador_de_producao_liga_a_esteira():
    import inspect

    from coordenador import __main__ as principal
    assert "esteira=ciclo_das_esteiras" in inspect.getsource(principal.montar)


def test_processos_windows_le_em_utf8_sem_quebrar():
    """04/10/2026: um byte fora do padrao na linha de comando de um processo fazia a
    lista vir vazia e o pulso pular tudo (3.043 vezes em dois dias)."""
    import subprocess

    from coordenador.supervisor import processos_windows
    visto = {}

    def rodar(cmd, **kw):
        visto.update(kw)
        visto["script"] = cmd[-1]
        saida = '[{"ProcessId": 7, "CommandLine": "python -m ias carteiro \u00e7", "Inicio": "2026-10-04T07:00:00"}]'
        return subprocess.CompletedProcess(cmd, 0, stdout=saida, stderr="")
    lista = processos_windows(rodar=rodar)
    assert lista and lista[0]["pid"] == 7
    assert visto["encoding"] == "utf-8" and visto["errors"] == "replace"
    assert "OutputEncoding" in visto["script"]


# ---- varredura 05/10/2026, item 13: tempestade de religadas -----------------
def _arvore_de_modulo(tmp_path):
    for rel in ("remoto/servico.py", "remoto/test_orquestrador.py", "remoto/conftest.py",
                "remoto/tests/ajuda.py"):
        alvo = tmp_path / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def _tocar(caminho, quando):
    import os
    os.utime(caminho, (quando.timestamp(), quando.timestamp()))


def test_mexer_so_em_teste_nao_e_codigo_velho(tmp_path):
    """04/10: mexer so em test_orquestrador.py ja religava o app e o bot."""
    raiz = _arvore_de_modulo(tmp_path)
    s, relogio = supervisor(raiz=raiz, git=None)
    ficha_app = {"modulos": ["remoto"]}
    inicio = relogio() - timedelta(hours=1)
    for p in raiz.rglob("*.py"):
        _tocar(p, inicio - timedelta(minutes=5))             # tudo anterior ao processo
    for rel in ("remoto/test_orquestrador.py", "remoto/conftest.py", "remoto/tests/ajuda.py"):
        _tocar(raiz / rel, relogio() - timedelta(minutes=10))
    assert s._mudou_codigo(ficha_app, inicio.isoformat()) is False
    _tocar(raiz / "remoto" / "servico.py", relogio() - timedelta(minutes=10))
    assert s._mudou_codigo(ficha_app, inicio.isoformat()) is True


def test_codigo_so_conta_depois_de_90_s_sem_salvar(tmp_path):
    from coordenador import supervisor as mod
    raiz = _arvore_de_modulo(tmp_path)
    s, relogio = supervisor(raiz=raiz, git=None)
    ficha_app = {"modulos": ["remoto"]}
    inicio = relogio() - timedelta(hours=1)
    for p in raiz.rglob("*.py"):
        _tocar(p, inicio - timedelta(minutes=5))
    _tocar(raiz / "remoto" / "servico.py", relogio() - timedelta(seconds=mod.CALMA_S - 30))
    assert s._mudou_codigo(ficha_app, inicio.isoformat()) is False     # ainda editando
    relogio.andar(31)
    assert s._mudou_codigo(ficha_app, inicio.isoformat()) is True


def test_no_maximo_uma_religada_por_codigo_a_cada_2_min():
    from coordenador import supervisor as mod
    mundo = Mundo({"pid": 10, "comando": "app"})
    s, relogio = supervisor(processos=mundo.processos, git=lambda *_: True,
                            parar=mundo.parar, iniciar=mundo.iniciar)
    s.pedir_reinicio("app")
    s.pulso()
    assert len(mundo.iniciou) == 1                            # a primeira religa na hora
    s.pedir_reinicio("app")                                   # outra entrega aplicada logo depois
    for _ in range(int(mod.RELIGADA_MIN_S // mod.PULSO_S) - 1):
        relogio.andar(mod.PULSO_S)
        s.pulso()
    assert len(mundo.iniciou) == 1
    assert "no máximo uma vez" in s.estado["app"]["motivo_espera"]
    relogio.andar(mod.PULSO_S * 2)
    s.pulso()
    assert len(mundo.iniciou) == 2


def test_parar_poupa_a_bandeja_do_tailscale():
    """A bandeja (tailscale-ipn.exe) nasce filha do bot; o taskkill /t a matava
    e o app do celular saia do tailnet de 1 a 3 min a cada religada."""
    from coordenador.supervisor import plano_de_parada
    arvore = [{"pid": 100, "pai": 1, "nome": "python.exe"},
              {"pid": 101, "pai": 100, "nome": "chrome.exe"},
              {"pid": 102, "pai": 101, "nome": "chrome.exe"},
              {"pid": 103, "pai": 100, "nome": "tailscale-ipn.exe"},
              {"pid": 104, "pai": 103, "nome": "filho-da-bandeja.exe"},
              {"pid": 200, "pai": 1, "nome": "outro.exe"}]
    assert plano_de_parada(100, arvore) == [102, 101, 100]
    sem_bandeja = [p for p in arvore if p["pid"] not in (103, 104)]
    assert plano_de_parada(100, sem_bandeja) is None           # taskkill /t de sempre
    ciclo = [{"pid": 5, "pai": 6, "nome": "a"}, {"pid": 6, "pai": 5, "nome": "tailscale-ipn.exe"}]
    assert plano_de_parada(5, ciclo) == [5]

    chamadas = []
    s, _ = supervisor()
    s._parar(100, listar=lambda: arvore, rodar=lambda cmd, **kw: chamadas.append(cmd))
    assert chamadas == [["taskkill", "/pid", p, "/f"] for p in ("102", "101", "100")]
    chamadas.clear()
    s._parar(100, listar=lambda: [], rodar=lambda cmd, **kw: chamadas.append(cmd))
    assert chamadas == [["taskkill", "/pid", "100", "/t", "/f"]]  # sem lista: como antes
