# -*- coding: utf-8 -*-
"""Etapa 2 da reforma (um gerente so), item a item. Nada toca processo real:
o "mundo" de processos e um dublê em que `parar` mata e `iniciar` faz nascer.

1. codigo velho so marca; reinicia quando PEDIDO (vigia ou `reiniciar`);
2. `seguro()` respeita a janela `post-12 .. post+18` da grade (`grade.minuto`);
3. `coordenador reiniciar` recusado nao diz "ok" e sai com codigo != 0;
4. `reinicios_24h` sobrevive ao coordenador subir de novo;
5. `saudes_ruins` zera quando o servico e religado;
6. `gravar_estado` atomico e com nova tentativa (arquivo trancado);
7. a assinatura do bot nao casa `python -m remoto --avisar` (nem outro avulso);
8. `reiniciar_servico` mata o velho (todos) antes de subir o novo, sem duplicar.
"""
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from coordenador import __main__ as cli
from coordenador import estado as estado_mod
from coordenador import supervisor as mod
from coordenador.supervisor import Supervisor, carregar_servicos, janela_das_postagens
from random_builds.builds import grade


class Relogio:
    def __init__(self, agora=datetime(2026, 10, 1, 3, 0)):
        self.agora = agora

    def __call__(self):
        return self.agora

    def andar(self, segundos):
        self.agora += timedelta(seconds=segundos)


class Mundo:
    def __init__(self, *processos):
        # o Windows nunca lista vazio: lista vazia e consulta que falhou
        self.lista = [{"pid": 4, "comando": "System"}] + [dict(p) for p in processos]
        self.parou, self.iniciou, self.ordem, self.proximo = [], [], [], 100
        self.imortais = set()

    def processos(self):
        return [dict(p) for p in self.lista]

    def parar(self, pid):
        self.parou.append(pid)
        self.ordem.append(("parar", pid))
        if pid not in self.imortais:
            self.lista = [p for p in self.lista if p["pid"] != pid]

    def iniciar(self, ficha):
        pid, self.proximo = self.proximo, self.proximo + 1
        self.iniciou.append(pid)
        self.ordem.append(("iniciar", pid))
        self.lista.append({"pid": pid, "comando": " ".join(ficha["comando"])})
        return pid


def ficha(nome="app", seguro=True, assinatura=None):
    return {nome: {"nome": nome, "assinatura": assinatura or nome, "comando": [nome], "cwd": ".",
                   "log": "coordenador-teste.log", "janela": "oculta", "modulos": [],
                   "reinicio_seguro": seguro}}


def montar(mundo, **mais):
    relogio = mais.pop("relogio", Relogio())
    opcoes = {"porta": lambda: True, "carteiro": lambda: {"situacao": "ocioso"},
              "git": lambda *_: False, "avisar": lambda *_: None, "gravar": lambda _: None,
              "log": lambda _: None, "janela": lambda _agora: (False, ""),
              "dormir": lambda _s: None, "carregar": lambda: {}, "pendentes": lambda: [],
              "processos": mundo.processos, "parar": mundo.parar, "iniciar": mundo.iniciar}
    opcoes.update(mais)
    return Supervisor(servicos=opcoes.pop("servicos", ficha()), relogio=relogio, **opcoes), relogio


def casam(s, nome, mundo):
    padrao = re.compile(s.servicos[nome]["assinatura"], re.I)
    return [p["pid"] for p in mundo.lista if padrao.search(p["comando"])]


# ------------------------------------------------------------ 1. codigo velho
def test_codigo_velho_so_marca_e_nunca_reinicia_sozinho():
    mundo = Mundo({"pid": 10, "comando": "app"})
    s, relogio = montar(mundo, git=lambda *_: True)
    for _ in range(200):                               # ~17 min de pulsos
        s.pulso()
        relogio.andar(mod.PULSO_S)
    assert s.estado["app"]["codigo_velho"] is True
    assert mundo.parou == [] and mundo.iniciou == []
    assert "app" not in s.reinicio_pedido and s.estado["app"]["reinicio_pedido"] is False
    assert [e["tipo"] for e in s.eventos].count("codigo_velho") == 1


def test_processo_religado_por_fora_perde_a_marca_de_codigo_velho():
    # 14/10 03:11: `coordenador reiniciar app` pela linha de comando religou o
    # app, o residente adotou o pid novo e seguia dizendo "codigo velho"
    mundo = Mundo({"pid": 10, "comando": "app"})
    velho = {"valor": True}
    s, relogio = montar(mundo, git=lambda *_: velho["valor"])
    s.pulso()
    assert s.estado["app"]["codigo_velho"] is True
    mundo.lista = [p for p in mundo.lista if p["pid"] != 10] + [{"pid": 77, "comando": "app"}]
    velho["valor"] = False                       # o novo subiu depois do commit
    relogio.andar(mod.PULSO_S)
    s.pulso()
    assert s.estado["app"]["pid"] == 77
    assert s.estado["app"]["codigo_velho"] is False
    assert mundo.iniciou == []


def test_codigo_velho_reinicia_quando_a_entrega_e_aplicada():
    mundo = Mundo({"pid": 10, "comando": "app"})
    s, _ = montar(mundo, git=lambda *_: True)
    s.pulso()
    assert mundo.iniciou == []
    s.pedir_reinicio("app")                            # o vigia aplicou codigo do app
    assert s.estado["app"]["reinicio_pedido"] is True
    s.pulso()
    assert mundo.parou == [10] and mundo.iniciou == [100]
    assert s.estado["app"]["codigo_velho"] is False and "app" not in s.reinicio_pedido


def test_reiniciar_pela_linha_de_comando_pendente_chega_ao_residente():
    # a CLI recusada grava em disco (pasta do teste, conftest); o residente toma
    estado_mod.pedir_reinicio_pendente("app")
    estado_mod.pedir_reinicio_pendente("app")          # repetido nao duplica
    mundo = Mundo({"pid": 10, "comando": "app"})
    s, _ = montar(mundo, pendentes=estado_mod.tomar_reinicios_pendentes)
    s.pulso()
    assert mundo.parou == [10] and mundo.iniciou == [100]
    assert not estado_mod.caminho_reinicios_pendentes().exists()
    s.pulso()
    assert mundo.iniciou == [100]                      # tomado uma vez so


# ------------------------------------------------------------ 2. janela da grade
@pytest.mark.parametrize("hora", grade.HORAS)
def test_janela_das_postagens_de_menos_12_a_mais_18_em_cada_horario(hora):
    post = datetime(2026, 10, 14, hora, grade.minuto(hora))
    assert janela_das_postagens(post - timedelta(minutes=12))[0]
    assert not janela_das_postagens(post - timedelta(minutes=12, seconds=1))[0]
    assert janela_das_postagens(post)[0]
    assert janela_das_postagens(post + timedelta(minutes=17, seconds=59))[0]
    assert not janela_das_postagens(post + timedelta(minutes=18))[0]


def test_janela_usa_o_minuto_de_cada_hora_e_atravessa_a_meia_noite():
    # o das 12h e :07, nao :37 (uma constante MINUTO erraria este)
    assert janela_das_postagens(datetime(2026, 10, 14, 11, 56))[0]
    assert not janela_das_postagens(datetime(2026, 10, 14, 12, 26))[0]
    assert janela_das_postagens(datetime(2026, 10, 14, 12, 20))[0]
    dentro, texto = janela_das_postagens(datetime(2026, 10, 14, 0, 30))
    assert dentro and "00:37" in texto
    dentro, texto = janela_das_postagens(datetime(2026, 10, 14, 23, 50))
    assert dentro and "23:37" in texto
    assert janela_das_postagens(datetime(2026, 10, 15, 0, 5))[0] is False   # 23:37 foi ha 28 min
    assert janela_das_postagens(datetime(2026, 10, 14, 3, 0)) == (False, "")


def test_seguro_recusa_reinicio_na_janela_e_reinicia_quando_ela_fecha():
    # janela REAL da grade: 15:30 e 7 min antes do post das 15:37
    mundo = Mundo({"pid": 10, "comando": "app"})
    s, relogio = montar(mundo, janela=janela_das_postagens,
                        relogio=Relogio(datetime(2026, 10, 14, 15, 30)))
    s.pedir_reinicio("app")
    s.pulso()
    assert mundo.parou == [] and mundo.iniciou == []
    assert "janela das postagens" in s.estado["app"]["motivo_espera"]
    relogio.agora = datetime(2026, 10, 14, 15, 54)     # post+17
    s.pulso()
    assert mundo.parou == []
    relogio.agora = datetime(2026, 10, 14, 15, 55)     # post+18: fechou
    s.pulso()
    assert mundo.parou == [10] and mundo.iniciou == [100]


def test_na_janela_quem_caiu_continua_sendo_religado():
    # a lei e contra DERRUBAR quem esta vivo; o app caido sobe na hora
    mundo = Mundo()
    s, _ = montar(mundo, janela=janela_das_postagens,
                  relogio=Relogio(datetime(2026, 10, 14, 15, 37)))
    s.pulso()
    assert mundo.iniciou == [100] and mundo.parou == []


def test_comando_do_app_na_janela_fica_pendente_e_nao_executado():
    mundo = Mundo({"pid": 10, "comando": "app"})
    aplicados = []
    fila = [{"id": "c1", "comando": "servico_reiniciar", "valor": "app"}]
    dentro = [True]
    s, _ = montar(mundo, comandos=lambda: list(fila),
                  aplicar=lambda ident, **kw: aplicados.append((ident, kw)) or fila.clear(),
                  janela=lambda _a: (dentro[0], "janela das postagens (15:37, em 7 min)" if dentro[0] else ""))
    s.pulso()
    assert aplicados == [("c1", {"nota": "pendente: janela das postagens (15:37, em 7 min)"})]
    assert "app" in s.reinicio_pedido and mundo.parou == []
    dentro[0] = False
    s.pulso()
    assert mundo.parou == [10] and mundo.iniciou == [100] and "app" not in s.reinicio_pedido


# ------------------------------------------------------------ 3. CLI recusada
def test_cli_recusada_pela_janela_nao_diz_ok_e_sai_com_2():
    mundo = Mundo({"pid": 10, "comando": "app"})
    s, _ = montar(mundo, janela=lambda _a: (True, "janela das postagens (15:37, em 7 min)"))
    falado, pendentes = [], []
    codigo = cli.reiniciar_pela_linha_de_comando("app", supervisor=s, pendente=pendentes.append,
                                                 saida=falado.append)
    assert codigo == 2
    assert falado and "ok" not in falado and "janela das postagens" in falado[0]
    assert pendentes == ["app"] and mundo.parou == [] and mundo.iniciou == []


def test_cli_sem_permissao_para_matar_nao_diz_ok_e_nao_sobe_outro():
    mundo = Mundo({"pid": 10, "comando": "app"})
    mundo.imortais.add(10)                             # taskkill "Acesso negado"
    s, _ = montar(mundo)
    falado, pendentes = [], []
    codigo = cli.reiniciar_pela_linha_de_comando("app", supervisor=s, pendente=pendentes.append,
                                                 saida=falado.append)
    assert codigo == 3 and "ok" not in falado
    assert "não morreu" in falado[0] and "sem permissão" in falado[0]
    assert mundo.iniciou == [] and casam(s, "app", mundo) == [10]


def test_cli_com_excecao_diz_o_erro_e_sai_com_3():
    class Quebrado:
        def reiniciar_servico(self, nome):
            raise PermissionError("[WinError 5] Acesso negado")
    falado = []
    assert cli.reiniciar_pela_linha_de_comando("bot", supervisor=Quebrado(), saida=falado.append) == 3
    assert falado == ["não reiniciei o bot: PermissionError: [WinError 5] Acesso negado"]


def test_cli_ok_quando_reiniciou():
    mundo = Mundo({"pid": 10, "comando": "app"})
    s, _ = montar(mundo)
    falado = []
    assert cli.reiniciar_pela_linha_de_comando("app", supervisor=s, pendente=None, saida=falado.append) == 0
    assert falado == ["ok"] and mundo.parou == [10] and mundo.iniciou == [100]


def test_main_devolve_o_codigo_do_reiniciar(monkeypatch):
    monkeypatch.setattr(cli, "reiniciar_pela_linha_de_comando", lambda servico, **kw: 2)
    assert cli.main(["reiniciar", "app"]) == 2


def test_status_curto_diz_quem_esta_velho_e_quem_tem_pedido():
    assert cli.resumo_dos_servicos({}) == "serviços: código atual"
    estado = {"servicos": {"app": {"codigo_velho": True, "reinicio_pedido": True},
                           "bot": {"codigo_velho": True}, "vila": {}}}
    assert cli.resumo_dos_servicos(estado) == "serviços: código velho em app, bot; reinício pedido: app"


# ------------------------------------------------------------ 4. reinicios_24h persistido
def test_reinicios_24h_sobrevivem_ao_coordenador_subir_de_novo():
    mundo = Mundo()
    s, relogio = montar(mundo, gravar=estado_mod.gravar_estado)
    s.pulso()                                          # sobe o app (1)
    s.reiniciar_servico("app")                         # (2)
    s.pedir_reinicio("app")
    s.pulso()                                          # throttle de 120 s: so marca
    assert s.estado["app"]["reinicios_24h"] == 2
    # o coordenador morre e a tarefa o religa: le o estado.json do disco
    novo = Supervisor(servicos=ficha(), relogio=relogio, processos=mundo.processos,
                      porta=lambda: True, git=lambda *_: False, avisar=lambda *_: None,
                      gravar=lambda _: None, log=lambda _: None, janela=lambda _a: (False, ""),
                      dormir=lambda _s: None, pendentes=lambda: [])
    assert novo.estado["app"]["reinicios_24h"] == 2
    assert "app" in novo.reinicio_pedido               # o pedido tambem sobrevive
    relogio.andar(24 * 3600 + 1)
    novo._contar_reinicios("app")
    assert novo.estado["app"]["reinicios_24h"] == 0


def test_reinicio_antigo_no_estado_nao_conta():
    agora = datetime(2026, 10, 14, 3, 0)
    anterior = {"servicos": {"app": {"reinicios": [(agora - timedelta(hours=25)).isoformat(),
                                                   (agora - timedelta(hours=2)).isoformat(),
                                                   "lixo"]}}}
    s, _ = montar(Mundo(), carregar=lambda: anterior, relogio=Relogio(agora))
    assert s.estado["app"]["reinicios_24h"] == 1


# ------------------------------------------------------------ 5. saudes_ruins
def test_saude_ruim_zera_quando_religa_e_o_novo_nao_morre_no_pulso_seguinte():
    mundo = Mundo({"pid": 10, "comando": "app"})
    s, relogio = montar(mundo, porta=lambda: False)    # a porta 8931 nunca abre
    while not mundo.iniciou:
        s.pulso()
        relogio.andar(mod.PULSO_S)
    assert mundo.parou == [10]
    assert s.saudes_ruins["app"] == 0                  # antes ficava em 3
    s.pulso(); relogio.andar(mod.PULSO_S)
    s.pulso()
    assert mundo.parou == [10]                         # o 100 ganhou os mesmos 3 pulsos
    assert s.saudes_ruins["app"] == 2


def test_reiniciar_servico_tambem_zera_saudes_ruins():
    mundo = Mundo({"pid": 10, "comando": "app"})
    s, _ = montar(mundo)
    s.saudes_ruins["app"] = 2
    assert s.reiniciar_servico("app")
    assert s.saudes_ruins["app"] == 0


# ------------------------------------------------------------ 6. gravar_estado
def test_gravar_estado_tenta_de_novo_no_arquivo_trancado():
    import os
    falhas, pausas = [2], []

    def trocar(origem, destino):
        if falhas[0]:
            falhas[0] -= 1
            raise PermissionError(5, "Acesso negado")
        os.replace(origem, destino)
    estado_mod.gravar_estado({"pid": 1}, pausa=pausas.append, trocar=trocar)
    assert estado_mod.ler_estado() == {"pid": 1}
    assert len(pausas) == 2
    assert list(estado_mod.pasta().glob("*.tmp")) == []


def test_gravar_estado_desiste_sem_estragar_o_antigo_nem_deixar_temporario():
    estado_mod.gravar_estado({"pid": 1})

    def sempre(origem, destino):
        raise PermissionError(5, "Acesso negado")
    pausas = []
    with pytest.raises(PermissionError):
        estado_mod.gravar_estado({"pid": 2}, pausa=pausas.append, trocar=sempre)
    assert len(pausas) == estado_mod.GRAVAR_TENTATIVAS - 1
    assert estado_mod.ler_estado() == {"pid": 1}
    assert list(estado_mod.pasta().glob("*.tmp")) == []


LEITOR = """
import json, sys, time
from pathlib import Path
alvo, parada = Path(sys.argv[1]), Path(sys.argv[2])
lidas = ruins = 0
while not parada.exists():
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError:
        continue
    try:
        json.loads(texto); lidas += 1
    except ValueError:
        ruins += 1
    time.sleep(0.001)
print(lidas, ruins)
"""


def test_gravar_estado_com_leitor_em_outro_processo_nunca_falha_nem_le_pela_metade(tmp_path):
    # o cenario da auditoria: o app (OUTRO processo) lendo estado.json sem
    # parar enquanto o coordenador grava; antes, 0 gravacoes ate o
    # PermissionError. Aqui ~500 leituras/s, muito acima do app.
    import subprocess
    import sys
    import time
    estado_mod.gravar_estado({"n": -1, "lixo": "x" * 5000})
    parada = tmp_path / "parar"
    leitor = subprocess.Popen([sys.executable, "-c", LEITOR, str(estado_mod.caminho()), str(parada)],
                              stdout=subprocess.PIPE, text=True)
    try:
        time.sleep(0.5)
        for n in range(60):
            estado_mod.gravar_estado({"n": n, "lixo": "x" * 5000})
    finally:
        parada.write_text("1")
        saida = leitor.communicate(timeout=30)[0]
    lidas, ruins = map(int, saida.split())
    assert lidas > 0 and ruins == 0
    assert estado_mod.ler_estado()["n"] == 59
    assert list(estado_mod.pasta().glob("*.tmp")) == []


def test_pulso_que_quebra_nao_mata_o_laco(monkeypatch):
    monkeypatch.setattr(mod, "PULSO_S", 0)
    logs, vezes = [], []
    s, _ = montar(Mundo(), log=logs.append)

    def pulso():
        vezes.append(1)
        raise PermissionError(5, "Acesso negado", "estado.json")
    s.pulso = pulso
    assert s.rodar(parar=lambda: len(vezes) >= 3) == 0
    assert len(vezes) == 3 and all("pulso falhou: PermissionError" in x for x in logs)


# ------------------------------------------------------------ 7. assinatura do bot
BOT = carregar_servicos()["bot"]["assinatura"]
PY = r'"C:\Python314\python.exe" -u -X utf8'


@pytest.mark.parametrize("comando", [
    rf"{PY} -m remoto",
    r"C:\Python314\python.exe -u -X utf8 -m remoto",
    rf'{PY} -m remoto --saida "E:\projetos\outputs\bot.txt"',
    rf"{PY} -m remoto --token 123:abc",
])
def test_assinatura_do_bot_casa_o_bot(comando):
    assert re.search(BOT, comando, re.I)


@pytest.mark.parametrize("comando", [
    rf'{PY} -m remoto --avisar "Publicado: build 44 no ar"',
    rf'{PY} -m remoto --avisar=oi',
    rf"{PY} -m remoto --apurar",
    rf"{PY} -m remoto --status",
    rf"{PY} -m remoto --esquecer 12345",
    rf"{PY} -m remoto --instalar",
    rf"{PY} -m remoto --desinstalar",
    rf"{PY} -m remoto --testar-conserto 2026-10-14T03:00",
    rf'{PY} -m remoto --saida "E:\x.txt" --avisar "oi"',
    rf"{PY} -m remoto.api_http --local --porta 8931",
    rf"{PY} -m remoto.delegar criar",
])
def test_assinatura_do_bot_nao_casa_avulsos(comando):
    assert not re.search(BOT, comando, re.I)


def test_toda_opcao_avulsa_do_remoto_esta_fora_da_assinatura():
    # contrato: quem acrescentar um `--x` que "faz e sai" em remoto/__main__.py
    # tem de pô-lo na assinatura, senao o coordenador adota (e mata) o avulso
    fonte = (Path(mod.__file__).resolve().parents[1] / "remoto" / "__main__.py").read_text(encoding="utf-8")
    opcoes = set(re.findall(r'add_argument\("(--[a-z-]+)"', fonte))
    assert "--avisar" in opcoes and len(opcoes) >= 7
    for opcao in opcoes - {"--token"}:            # --token guarda e LIGA o bot
        assert not re.search(BOT, f"{PY} -m remoto {opcao} x", re.I), opcao


def test_reiniciar_o_bot_nao_mata_o_aviso_avulso():
    servicos = {"bot": dict(carregar_servicos()["bot"], comando=["python", "-m", "remoto"])}
    mundo = Mundo({"pid": 50, "comando": rf'{PY} -m remoto --avisar "oi"'},
                  {"pid": 60, "comando": rf"{PY} -m remoto"})
    s, _ = montar(mundo, servicos=servicos)
    s.pulso()
    assert s.estado["bot"]["pid"] == 60
    assert s.reiniciar_servico("bot")
    assert mundo.parou == [60] and 50 in [p["pid"] for p in mundo.lista]


# ------------------------------------------------------------ 8. mata antes de subir
def test_reiniciar_mata_todos_os_velhos_antes_de_subir_um_so():
    mundo = Mundo({"pid": 10, "comando": "app"}, {"pid": 11, "comando": "app"})   # ja duplicado
    s, _ = montar(mundo)
    assert s.reiniciar_servico("app")
    assert mundo.ordem == [("parar", 10), ("parar", 11), ("iniciar", 100)]
    assert casam(s, "app", mundo) == [100]
    assert s.estado["app"]["pid"] == 100


def test_reiniciar_espera_o_velho_morrer_de_verdade():
    mundo = Mundo({"pid": 10, "comando": "app"})
    mundo.imortais.add(10)
    dormidas = []

    def dormir(segundos):                              # morre na 3a olhada
        dormidas.append(segundos)
        if len(dormidas) == 2:
            mundo.lista = [p for p in mundo.lista if p["pid"] != 10]
    s, _ = montar(mundo, dormir=dormir)
    assert s.reiniciar_servico("app")
    assert len(dormidas) == 2 and mundo.iniciou == [100]
    assert mundo.ordem.index(("iniciar", 100)) > mundo.ordem.index(("parar", 10))


def test_velho_que_nao_morre_nao_ganha_irmao_e_o_pulso_nao_trava_toda_vez():
    mundo = Mundo({"pid": 10, "comando": "app"})
    mundo.imortais.add(10)
    dormidas = []
    s, relogio = montar(mundo, dormir=dormidas.append)
    s.pedir_reinicio("app")
    s.pulso()
    assert mundo.iniciou == [] and casam(s, "app", mundo) == [10]
    assert len(dormidas) == int(mod.MORTE_PRAZO_S / mod.MORTE_PASSO_S)    # prazo limitado
    assert s.ultima_recusa["app"]["tipo"] == "morte" and "app" in s.reinicio_pedido
    tentativas = len(mundo.parou)
    relogio.andar(mod.PULSO_S); s.pulso()
    assert len(mundo.parou) == tentativas              # espera RELIGADA_MIN_S para tentar de novo
    relogio.andar(mod.RELIGADA_MIN_S); s.pulso()
    assert len(mundo.parou) > tentativas and mundo.iniciou == []


def test_lista_vazia_do_windows_nao_e_prova_de_morte():
    mundo = Mundo({"pid": 10, "comando": "app"})
    olhadas = []

    def processos():
        olhadas.append(1)
        if len(olhadas) == 2:                          # a consulta falhou uma vez
            return []
        return mundo.processos()
    mundo.imortais.add(10)
    s, _ = montar(mundo, processos=processos)
    assert not s.reiniciar_servico("app")
    assert mundo.iniciou == []


def test_parar_sem_permissao_vira_recusa_e_nao_sobe_outro():
    mundo = Mundo({"pid": 10, "comando": "app"})

    def negar(pid):
        raise PermissionError(5, "Acesso negado")
    s, _ = montar(mundo, parar=negar)
    assert not s.reiniciar_servico("app")
    assert s.ultima_recusa["app"]["tipo"] == "morte"
    assert "sem permissão" in s.estado["app"]["motivo_espera"]
    assert mundo.iniciou == []


def test_matou_e_o_novo_nao_subiu_nao_fica_pedido():
    mundo = Mundo({"pid": 10, "comando": "app"})

    def quebra(_ficha):
        raise OSError("python sumiu")
    s, _ = montar(mundo, iniciar=quebra)
    s.pedir_reinicio("app")
    assert not s.reiniciar_servico("app")
    assert s.ultima_recusa["app"]["tipo"] == "subir" and "python sumiu" in s.ultima_recusa["app"]["motivo"]
    assert "app" not in s.reinicio_pedido              # o velho ja morreu; o pulso religa o ausente
