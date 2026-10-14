# -*- coding: utf-8 -*-
"""A vigia do tailnet: o app do celular alcancavel, e aviso quando nao esta.

28/09/2026: depois de um desligamento pelo botao, o cliente da bandeja do
Tailscale nao subiu, o backend ficou em `NoState`, o `serve` sumiu da vista e
o celular perdeu o app — sem aviso nenhum. Nada aqui toca o Tailscale de
verdade: o `rodar`, o `popen`, o relogio e o sono sao dubles.
"""
from __future__ import annotations

import json
import subprocess

import pytest

from remoto import vigia_tailnet as V

SERVE_OK = json.dumps({
    "TCP": {"443": {"HTTPS": True}},
    "Web": {"pc.tail.ts.net:443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8931"}}}}})
SERVE_FUNNEL = json.dumps({
    **json.loads(SERVE_OK), "AllowFunnel": {"pc.tail.ts.net:443": True}})
SERVE_OUTRO = json.dumps({
    "Web": {"pc.tail.ts.net:443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:9999"}}}}})
BANDEJA_ABERTA = '"tailscale-ipn.exe","9880","Console","1","32.392 K"\n'
BANDEJA_FECHADA = "INFORMAÇÕES: nenhuma tarefa em execução correspondente\n"


class Rodar:
    """O `subprocess.run` de mentira. `None` numa saida = o comando falhou."""

    def __init__(self, estado="Running", serve=SERVE_OK, tasklist=BANDEJA_ABERTA,
                 explode=False):
        self.estado, self.serve, self.tasklist = estado, serve, tasklist
        self.explode = explode
        self.chamadas = []

    def __call__(self, args, **_k):
        self.chamadas.append(list(args))
        if self.explode:
            raise OSError("sem tailscale")
        if args[0] == "tasklist":
            saida = self.tasklist
        elif list(args[1:3]) == ["serve", "status"]:
            saida = self.serve
        elif args[1] == "status":
            saida = (None if self.estado is None
                     else json.dumps({"BackendState": self.estado, "Health": [],
                                      "Self": {"DNSName": "pc.tail.ts.net."}}))
        else:
            raise AssertionError(f"comando que a vigia nao pode rodar: {args}")
        if saida is None:
            return subprocess.CompletedProcess(args, 1, "", "erro")
        return subprocess.CompletedProcess(args, 0, saida, "")


EXPLORER = r"C:\Windows\explorer.exe"


@pytest.fixture(autouse=True)
def _exe(monkeypatch):
    monkeypatch.setattr(V, "_tailscale_exe", lambda: "tailscale.exe")
    monkeypatch.setattr(V, "_bandeja_exe", lambda: "tailscale-ipn.exe")
    monkeypatch.setattr(V, "_explorer_exe", lambda: EXPLORER)


# ================================================================ sondar
def test_tudo_certo_e_so_dois_comandos_de_leitura():
    rodar = Rodar()
    ficha = V.sondar(rodar)
    assert ficha["ok"] is True and ficha["serve"] is True and not ficha["funnel"]
    assert rodar.chamadas == [["tailscale.exe", "status", "--json"],
                              ["tailscale.exe", "serve", "status", "--json"]]
    # a URL do app no tailnet sai do mesmo status (a prova da APP-15)
    assert ficha["url"] == "https://pc.tail.ts.net/"


def test_url_responde_so_com_200():
    class Resposta:
        def __init__(self, status):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    pedidos = []
    assert V.url_responde("https://pc.tail.ts.net/",
                          lambda url, timeout: pedidos.append((url, timeout)) or Resposta(200))
    assert pedidos == [("https://pc.tail.ts.net/", V.URL_PRAZO_S)]
    assert not V.url_responde("https://x/", lambda url, timeout: Resposta(502))

    def cai(url, timeout):
        raise OSError("sem rota")
    assert not V.url_responde("https://x/", cai)


def test_backend_parado_sem_bandeja():
    """O caso de 28/09: NoState e o cliente da bandeja fechado."""
    ficha = V.sondar(Rodar(estado="NoState", serve=None, tasklist=BANDEJA_FECHADA))
    assert ficha["ok"] is False and ficha["estado"] == "NoState"
    assert ficha["bandeja"] is False
    assert "NoState" in ficha["motivo"] and "bandeja" in ficha["motivo"]


@pytest.mark.parametrize("serve", ["{}", "No serve config\n", ""])
def test_serve_que_sumiu(serve):
    ficha = V.sondar(Rodar(serve=serve))
    assert ficha["ok"] is False and ficha["serve"] is False
    assert "serve sumiu" in ficha["motivo"]


def test_funnel_ligado_nunca_passa():
    ficha = V.sondar(Rodar(serve=SERVE_FUNNEL))
    assert ficha["ok"] is False and ficha["funnel"] is True
    assert "FUNNEL" in ficha["motivo"]


def test_serve_que_aponta_para_outro_lugar():
    ficha = V.sondar(Rodar(serve=SERVE_OUTRO))
    assert ficha["ok"] is False and "não aponta" in ficha["motivo"]


@pytest.mark.parametrize("rodar,trecho", [
    (Rodar(estado=None), "não consegui perguntar"),
    (Rodar(serve=None), "não consegui ler a configuração do serve"),
    (Rodar(explode=True), "não consegui perguntar"),
])
def test_o_que_nao_se_le_nao_passa(rodar, trecho):
    ficha = V.sondar(rodar)
    assert ficha["ok"] is False and trecho in ficha["motivo"]
    assert ficha["sem_resposta"] is True          # "não sei", não "fora"


def test_resposta_ruim_nao_e_sem_resposta():
    assert not V.sondar(Rodar(estado="NoState", tasklist=BANDEJA_FECHADA)).get("sem_resposta")
    assert not V.sondar(Rodar(serve=SERVE_FUNNEL)).get("sem_resposta")


def test_sem_tailscale_instalado(monkeypatch):
    monkeypatch.setattr(V, "_tailscale_exe", lambda: None)
    ficha = V.sondar(Rodar())
    assert ficha["ok"] is False and "tailscale.exe" in ficha["motivo"]
    assert not ficha.get("sem_resposta")


# ============================================================ a bandeja
def test_abrir_bandeja_pelo_explorer_fora_da_arvore_do_bot():
    """Item 13 da varredura de 05/10: aberta direto, a bandeja era FILHA do
    bot (pid 9680 do 12780) e morria no `taskkill /t /f` de cada religada.
    Pelo explorer, quem a cria e o shell do Windows."""
    chamadas = []
    feito = V.abrir_bandeja(lambda args, **k: chamadas.append((args, k["creationflags"])))
    ((args, flags),) = chamadas
    assert args == [EXPLORER, "tailscale-ipn.exe"]
    assert flags & V.FORA_DO_JOB == V.FORA_DO_JOB
    assert feito == "abri o tailscale-ipn.exe"


def test_abrir_bandeja_pelo_explorer_preso_ao_job_ainda_e_pelo_explorer():
    """O Agendador pode negar a saida do job: o explorer preso ao job so
    entrega o pedido ao shell, e a bandeja nasce fora dele assim mesmo."""
    chamadas = []

    def popen(args, **k):
        chamadas.append((args, k["creationflags"]))
        if len(chamadas) == 1:
            raise OSError("acesso negado")
    assert V.abrir_bandeja(popen) == "abri o tailscale-ipn.exe"
    assert chamadas[1] == ([EXPLORER, "tailscale-ipn.exe"], V.DESLIGADO)


@pytest.mark.parametrize("sem_explorer", [True, False])
def test_abrir_bandeja_direto_so_sem_explorer(monkeypatch, sem_explorer):
    """Sem explorer.exe (ou com ele recusando), o caminho antigo: direto,
    tentando sair do job."""
    chamadas = []
    if sem_explorer:
        monkeypatch.setattr(V, "_explorer_exe", lambda: None)

    def popen(args, **k):
        chamadas.append((args, k["creationflags"]))
        if args[0] == EXPLORER:
            raise OSError("explorer recusou")
    assert V.abrir_bandeja(popen) == "abri o tailscale-ipn.exe"
    assert chamadas[-1] == (["tailscale-ipn.exe"], V.DESLIGADO | V.FORA_DO_JOB)


def test_abrir_bandeja_sem_sair_do_job_quando_o_windows_nega(monkeypatch):
    monkeypatch.setattr(V, "_explorer_exe", lambda: None)
    chamadas = []

    def popen(args, **k):
        chamadas.append(k["creationflags"])
        if len(chamadas) == 1:
            raise OSError("acesso negado")
    assert V.abrir_bandeja(popen) == "abri o tailscale-ipn.exe"
    assert chamadas[1] == V.DESLIGADO


def test_abrir_bandeja_que_nao_existe(monkeypatch):
    monkeypatch.setattr(V, "_bandeja_exe", lambda: None)
    assert V.abrir_bandeja(lambda *a, **k: None).startswith("não achei")


# ============================================================ a vigia
OK = {"ok": True}
CONECTANDO = {"ok": False, "estado": "Starting", "bandeja": True,
              "motivo": "o Tailscale está em Starting"}
PARADO = {"ok": False, "estado": "NoState", "bandeja": False,
          "motivo": "o Tailscale está em NoState e o cliente da bandeja não "
                    "está aberto"}
SEM_SERVE = {"ok": False, "estado": "Running", "serve": False,
             "motivo": "a configuração do serve sumiu"}
FUNNEL = {"ok": False, "estado": "Running", "serve": True, "funnel": True,
          "motivo": "o FUNNEL está ligado"}


class Mundo:
    def __init__(self, fichas, url_abre=True):
        self.fichas = list(fichas)
        self.avisos, self.abertas, self.sonos = [], 0, []
        self.agora = 0.0
        self.sondas, self.logs, self.provas = 0, [], []
        self.url_abre = url_abre

    def sondar(self):
        self.sondas += 1
        return self.fichas.pop(0) if len(self.fichas) > 1 else self.fichas[0]

    def abrir(self):
        self.abertas += 1
        return "abri o tailscale-ipn.exe"

    def provar(self, url):
        self.provas.append(url)
        return self.url_abre

    def vigia(self):
        return V.Vigia(avisar=self.avisos.append, sondar=self.sondar,
                       abrir=self.abrir, dormir=self.sonos.append,
                       relogio=lambda: self.agora, intervalo=120, primeira=60,
                       log=self.logs.append, provar=self.provar)


def test_tudo_certo_nao_fala_nada():
    m = Mundo([OK])
    v = m.vigia()
    for _ in range(3):
        assert v.uma_olhada() is None
    assert m.avisos == [] and m.abertas == 0


def test_um_tropeco_so_nao_vira_aviso():
    """Logo depois do boot o Tailscale ainda conecta: uma olhada ruim so."""
    m = Mundo([CONECTANDO, OK])
    v = m.vigia()
    v.uma_olhada()
    v.uma_olhada()
    assert m.avisos == [] and m.abertas == 0


def test_um_aviso_por_ocorrencia_e_outro_na_volta():
    m = Mundo([CONECTANDO, CONECTANDO, CONECTANDO, OK, CONECTANDO, CONECTANDO])
    v = m.vigia()
    for _ in range(6):
        v.uma_olhada()
    assert len(m.avisos) == 3
    assert m.avisos[0].startswith("⚠️") and "Não mexi em nada" in m.avisos[0]
    assert m.avisos[1].startswith("✅")
    assert m.avisos[2].startswith("⚠️")           # nova ocorrencia, novo aviso
    assert m.abertas == 0                           # a bandeja estava aberta


def test_o_caso_de_28_09_se_conserta_sozinho_e_avisa_o_que_fez():
    m = Mundo([PARADO, OK])
    v = m.vigia()
    aviso = v.uma_olhada()
    assert m.abertas == 1
    assert aviso.startswith("🔧") and "Abri o tailscale-ipn.exe" in aviso
    assert "voltou" in aviso and m.avisos == [aviso]
    assert v.fora is False
    assert v.uma_olhada() is None                   # voltou: nada a dizer


def test_conserto_que_nao_basta_avisa_uma_vez_e_nao_insiste():
    m = Mundo([PARADO])
    v = m.vigia()
    aviso = v.uma_olhada()
    assert m.abertas == 1 and aviso.startswith("⚠️")
    assert "e não bastou" in aviso
    assert sum(m.sonos) >= V.ESPERA_DO_CONSERTO_S
    for _ in range(3):
        assert v.uma_olhada() is None
    assert m.abertas == 1 and len(m.avisos) == 1


def test_funnel_avisa_na_hora_e_nao_mexe():
    m = Mundo([FUNNEL])
    v = m.vigia()
    aviso = v.uma_olhada()
    assert aviso.startswith("🚨") and "Não mexi" in aviso
    assert m.abertas == 0
    assert v.uma_olhada() is None                   # uma vez por ocorrencia


def test_serve_sumido_so_ensina_a_refazer_nunca_refaz():
    m = Mundo([SEM_SERVE])
    v = m.vigia()
    v.uma_olhada()
    aviso = v.uma_olhada()
    assert m.abertas == 0
    assert "Não mexi em nada" in aviso and V.REFAZER_SERVE in aviso
    assert "--https=443 http://127.0.0.1:8931" in V.REFAZER_SERVE
    assert "funnel" not in V.REFAZER_SERVE


SEM_RESPOSTA = {"ok": False, "estado": None, "sem_resposta": True,
                "motivo": "não consegui perguntar o estado ao Tailscale"}


OK_COM_URL = {"ok": True, "url": "https://pc.tail.ts.net/"}


def test_sem_resposta_nao_vai_ao_telegram():
    """APP-15: 12 mensagens "❔ não sei" + "voltou" em 12/10, sem informação
    nenhuma. Sem resposta do Tailscale agora vai SO ao log."""
    m = Mundo([SEM_RESPOSTA] * 5 + [OK])
    v = m.vigia()
    for _ in range(6):
        assert v.uma_olhada() is None
    assert m.avisos == [] and m.abertas == 0
    assert m.sondas == 6 and m.sonos == []          # uma sonda por olhada, sem cochilo
    assert sum(l.startswith("tailnet: sem resposta") for l in m.logs) == 5
    assert any("voltou a responder" in l for l in m.logs)


def test_sem_resposta_com_a_url_do_app_no_ar_so_vai_ao_log():
    m = Mundo([OK_COM_URL] + [SEM_RESPOSTA] * 5 + [OK], url_abre=True)
    v = m.vigia()
    for _ in range(7):
        assert v.uma_olhada() is None
    assert m.avisos == []
    assert m.provas == ["https://pc.tail.ts.net/"] * 3     # da 3a olhada sem resposta em diante
    assert any("respondeu 200" in l for l in m.logs)


def test_sem_resposta_e_a_url_que_nao_abre_e_prova_de_queda():
    """Aviso so com prova: a URL do app no tailnet sem 200."""
    m = Mundo([OK_COM_URL] + [SEM_RESPOSTA] * 6 + [OK], url_abre=False)
    v = m.vigia()
    assert v.uma_olhada() is None                   # tudo certo, aprende a URL
    assert v.uma_olhada() is None
    assert v.uma_olhada() is None
    aviso = v.uma_olhada()                          # 3a sem resposta: prova
    assert aviso.startswith("⚠️") and "https://pc.tail.ts.net/" in aviso
    assert "Não mexi em nada" in aviso and m.abertas == 0
    for _ in range(3):
        assert v.uma_olhada() is None               # um aviso por ocorrencia
    volta = v.uma_olhada()
    assert volta.startswith("✅") and "voltou a responder" in volta
    assert m.avisos == [aviso, volta]


def test_sem_resposta_sem_saber_a_url_nao_avisa():
    m = Mundo([SEM_RESPOSTA], url_abre=False)
    v = m.vigia()
    for _ in range(5):
        assert v.uma_olhada() is None
    assert m.avisos == [] and m.provas == []


def test_sem_resposta_e_tropeco_nao_se_somam():
    """Duas olhadas sem resposta e um tropeço (Starting) não viram aviso:
    cada um tem a sua conta."""
    m = Mundo([OK_COM_URL, SEM_RESPOSTA, SEM_RESPOSTA, CONECTANDO, OK], url_abre=False)
    v = m.vigia()
    for _ in range(5):
        assert v.uma_olhada() is None
    assert m.avisos == [] and m.provas == []


def test_depois_da_url_sem_resposta_a_bandeja_fechada_ainda_e_consertada():
    """O aviso da URL não pode calar a ocorrência de verdade que vem depois."""
    m = Mundo([OK_COM_URL] + [SEM_RESPOSTA] * 3 + [PARADO, OK], url_abre=False)
    v = m.vigia()
    for _ in range(4):
        v.uma_olhada()
    assert len(m.avisos) == 1
    aviso = v.uma_olhada()
    assert m.abertas == 1 and aviso.startswith("🔧")
    assert len(m.avisos) == 2


def test_olha_no_ritmo_certo():
    m = Mundo([OK])
    olhadas = []
    v = m.vigia()
    v._sondar = lambda: olhadas.append(m.agora) or OK
    for m.agora in (0, 30, 59, 60, 100, 179, 180, 300):
        v.talvez()
    assert olhadas == [60, 180, 300]


def test_a_vigia_nunca_roda_funnel_nem_mexe_no_serve():
    """Toda LISTA de argumentos do fonte (o que vira comando) e de leitura.

    O `Rodar` de mentira ja recusa qualquer comando fora dos tres de leitura;
    isto pega o que um teste de comportamento nao exercitasse.
    """
    import ast
    import inspect
    proibidos = {"funnel", "set", "up", "--bg", "--unattended", "--https=443",
                 "off", "reset", "down"}
    listas = [n for n in ast.walk(ast.parse(inspect.getsource(V)))
              if isinstance(n, ast.List)]
    palavras = {e.value for n in listas for e in n.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    assert palavras & proibidos == set()
    assert {"status", "--json", "serve", "tasklist"} <= palavras
