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
                     else json.dumps({"BackendState": self.estado, "Health": []}))
        else:
            raise AssertionError(f"comando que a vigia nao pode rodar: {args}")
        if saida is None:
            return subprocess.CompletedProcess(args, 1, "", "erro")
        return subprocess.CompletedProcess(args, 0, saida, "")


@pytest.fixture(autouse=True)
def _exe(monkeypatch):
    monkeypatch.setattr(V, "_tailscale_exe", lambda: "tailscale.exe")
    monkeypatch.setattr(V, "_bandeja_exe", lambda: "tailscale-ipn.exe")


# ================================================================ sondar
def test_tudo_certo_e_so_dois_comandos_de_leitura():
    rodar = Rodar()
    ficha = V.sondar(rodar)
    assert ficha["ok"] is True and ficha["serve"] is True and not ficha["funnel"]
    assert rodar.chamadas == [["tailscale.exe", "status", "--json"],
                              ["tailscale.exe", "serve", "status", "--json"]]


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


def test_sem_tailscale_instalado(monkeypatch):
    monkeypatch.setattr(V, "_tailscale_exe", lambda: None)
    ficha = V.sondar(Rodar())
    assert ficha["ok"] is False and "tailscale.exe" in ficha["motivo"]


# ============================================================ a bandeja
def test_abrir_bandeja_sai_do_job_do_bot():
    chamadas = []
    V.abrir_bandeja(lambda args, **k: chamadas.append((args, k["creationflags"])))
    ((args, flags),) = chamadas
    assert args == ["tailscale-ipn.exe"]
    assert flags & V.FORA_DO_JOB == V.FORA_DO_JOB


def test_abrir_bandeja_sem_sair_do_job_quando_o_windows_nega():
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
    def __init__(self, fichas):
        self.fichas = list(fichas)
        self.avisos, self.abertas, self.sonos = [], 0, []
        self.agora = 0.0

    def sondar(self):
        return self.fichas.pop(0) if len(self.fichas) > 1 else self.fichas[0]

    def abrir(self):
        self.abertas += 1
        return "abri o tailscale-ipn.exe"

    def vigia(self):
        return V.Vigia(avisar=self.avisos.append, sondar=self.sondar,
                       abrir=self.abrir, dormir=self.sonos.append,
                       relogio=lambda: self.agora, intervalo=120, primeira=60)


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
