# -*- coding: utf-8 -*-
"""SCR-7 e SCR-1 da auditoria profunda (14/10/2026).

SCR-7: a rodada de historias das 07:02 de 12/10 (pid 4332) calou no Gemini as
13:09:33 e segurou `historias__auto` por 31 h; os 12 disparos seguintes sairam
"ja tem uma rodada em andamento" e ninguem matou o Python. O vigia le a ficha
da rodada (`builds.rodada_viva`) e encerra a que calou por
`LIMITE_SEM_PULSO_MIN` (120; o pior trecho calado SAUDAVEL medido nos logs de
setembro-outubro foi 43,4 min nos builds e 22,6 min nas historias).

SCR-1 (decisao `geral/pc-religado`): so um aviso "o PC religou" quando ele
entrar, uma vez por boot.
"""
from __future__ import annotations

import json
import time
from datetime import datetime

from coordenador import religou
from coordenador import vigia_rodadas as V

AGORA = datetime(2026, 10, 12, 15, 30).timestamp()
INICIO = datetime(2026, 10, 12, 7, 2, 5).timestamp()
NASCEU = INICIO - 3.0                    # o python nasceu antes de pegar a trava


def _ficha(pulso_min_atras: float, pid: int = 4332) -> dict:
    return {"pid": pid, "inicio": INICIO, "trava": "historias__auto",
            "rotulo": "historias", "pulso": AGORA - pulso_min_atras * 60,
            "_arquivo": f"x/{pid}.json"}


class _Mundo:
    def __init__(self, fichas, vivos=None, morre=True):
        self._fichas = fichas
        self.vivos = dict(vivos or {})
        self.morre = morre
        self.mortos, self.apagadas, self.avisos, self.eventos = [], [], [], []

    def criado(self, pid):
        return self.vivos.get(pid)

    def matar(self, pid):
        self.mortos.append(pid)
        if self.morre:
            self.vivos.pop(pid, None)

    def vigia(self, limite=120):
        return V.VigiaRodadas(
            avisar=self.avisos.append, log=lambda t: None,
            evento=lambda tipo, texto: self.eventos.append(tipo),
            relogio=lambda: AGORA, criado=self.criado, matar=self.matar,
            fichas=lambda: list(self._fichas), apagar=self.apagadas.append,
            limite_min=limite, dormir=lambda s: None)


def test_caso_zero_sem_ficha_nada_acontece():
    m = _Mundo([])
    assert m.vigia().passo() == []
    assert m.mortos == [] and m.avisos == []


def test_rodada_que_fala_nao_morre_por_mais_longa_que_seja():
    """8 h de rodada, pulso de 5 min atras: viva."""
    m = _Mundo([_ficha(5)], vivos={4332: NASCEU})
    assert m.vigia().passo() == []
    assert m.mortos == []


def test_calada_ha_43_min_nao_morre():
    """O pior trecho calado saudavel medido (builds, 05/10)."""
    m = _Mundo([_ficha(43.4)], vivos={4332: NASCEU})
    m.vigia().passo()
    assert m.mortos == []


def test_caso_de_12_10_calada_morre_e_avisa():
    """Pulso das 13:09 e relogio as 15:30 (141 min): mata, confere, apaga, avisa."""
    m = _Mundo([_ficha(141)], vivos={4332: NASCEU})
    feito = m.vigia().passo()
    assert m.mortos == [4332]
    assert feito == [{"pid": 4332, "acao": "encerrada", "calada_min": 141}]
    assert len(m.apagadas) == 1
    assert len(m.avisos) == 1 and "historias__auto" in m.avisos[0]
    assert "4332" in m.avisos[0] and "12/10 13:09" in m.avisos[0]
    assert m.eventos == ["rodada_encerrada"]


def test_pid_reaproveitado_nao_e_morto():
    """O pid 4332 agora e de outro processo, nascido DEPOIS da ficha."""
    m = _Mundo([_ficha(500)], vivos={4332: INICIO + 3600})
    feito = m.vigia().passo()
    assert m.mortos == []
    assert feito == [{"pid": 4332, "acao": "faxina"}]
    assert len(m.apagadas) == 1 and m.avisos == []


def test_ficha_de_processo_morto_e_faxinada_sem_aviso():
    m = _Mundo([_ficha(500)], vivos={})
    m.vigia().passo()
    assert m.mortos == [] and m.avisos == [] and len(m.apagadas) == 1


def test_processo_que_nao_morre_avisa_uma_vez_so():
    m = _Mundo([_ficha(200)], vivos={4332: NASCEU}, morre=False)
    vigia = m.vigia()
    vigia.passo()
    vigia.passo(forcar=True)
    assert m.mortos == [4332, 4332]
    assert m.apagadas == []
    assert len(m.avisos) == 1 and "NAO consegui" in m.avisos[0]


def test_ficha_ilegivel_nao_mata_ninguem():
    m = _Mundo([{"ilegivel": "ValueError", "_arquivo": "x/1.json"}])
    assert m.vigia().passo() == []


def test_intervalo_entre_olhadas():
    m = _Mundo([_ficha(141)], vivos={4332: NASCEU})
    vigia = m.vigia()
    vigia.passo()
    m._fichas.append(_ficha(141, pid=77))
    m.vivos[77] = NASCEU
    assert vigia.passo() == []           # menos de INTERVALO_S depois


def test_limite_padrao_e_o_da_rodada_viva():
    from builds import rodada_viva
    assert rodada_viva.LIMITE_SEM_PULSO_MIN == 120
    assert V._limite_min() == 120.0


def test_rodada_viva_grava_pulsa_e_apaga(tmp_path, monkeypatch):
    """A ficha nasce com a trava, o pulso anda so a cada 30 s, e some no fim."""
    from builds import rodada_viva
    monkeypatch.setattr(rodada_viva, "pasta", lambda: tmp_path)
    with rodada_viva.rodada("historias__auto", "historias"):
        arquivos = list(tmp_path.glob("*.json"))
        assert len(arquivos) == 1
        ficha = json.loads(arquivos[0].read_text(encoding="utf-8"))
        assert ficha["trava"] == "historias__auto"
        assert rodada_viva.pulsar(ficha["pulso"] + 10) is False
        assert rodada_viva.pulsar(ficha["pulso"] + 31) is True
        lido = rodada_viva.fichas()
        assert lido[0]["pulso"] == ficha["pulso"] + 31
    assert list(tmp_path.glob("*.json")) == []
    assert rodada_viva.pulsar() is False        # fora da rodada, nada


def test_criado_em_do_proprio_processo_e_agora():
    import os
    nasceu = V.criado_em(os.getpid())
    assert nasceu is not None and abs(time.time() - nasceu) < 24 * 3600


def test_supervisor_so_liga_o_vigia_quando_montado():
    from coordenador.supervisor import Supervisor
    s = Supervisor(servicos={}, gravar=lambda e: None, log=lambda t: None,
                   carregar=lambda: {})
    s.vigiar_rodadas()                         # sem vigia: nada
    chamadas = []

    class Duble:
        def passo(self, forcar=False):
            chamadas.append(forcar)
            return []
    s.vigia_rodadas = Duble()
    s.em_fundo = lambda nome, f: f()
    s.vigiar_rodadas()
    s.vigiar_rodadas()                         # dentro do intervalo
    assert chamadas == [True]


# ------------------------------------------------------------------ SCR-6
def test_tarefas_antigas_segue_depois_de_erro():
    """`check=True` no laco: a primeira tarefa ausente deixava as outras."""
    import coordenador.__main__ as cli
    chamadas = []

    def rodar(args, check=False):
        chamadas.append(args[3])
        if len(chamadas) == 1:
            return type("P", (), {"returncode": 1})()
        return type("P", (), {"returncode": 0})()
    resumo = cli.tarefas_antigas(False, rodar=rodar)
    assert len(chamadas) == 3
    assert list(resumo.values()) == [1, 0, 0]


def test_avisar_se_religou_nao_derruba_a_subida(monkeypatch):
    import coordenador.__main__ as cli
    from coordenador import religou as mod

    def explode(*a, **k):
        raise OSError("disco")
    monkeypatch.setattr(mod, "verificar", explode)
    logs, avisos = [], []
    s = type("S", (), {"log": logs.append, "avisar": avisos.append,
                       "evento": lambda *a: None})()
    assert cli.avisar_se_religou(s, {}) is None
    assert avisos == [] and logs


# ------------------------------------------------------------------ SCR-1
BOOT = datetime(2026, 10, 13, 22, 43).timestamp()


def test_religou_primeira_vez_so_grava_a_marca(tmp_path):
    assert religou.verificar(tmp_path, anterior={}, agora=BOOT + 600,
                             boot=BOOT) is None
    assert len(list(tmp_path.glob("boot_*.marca"))) == 1


def test_religou_avisa_uma_vez_por_boot(tmp_path):
    religou.verificar(tmp_path, anterior={}, agora=BOOT - 86400,
                      boot=BOOT - 2 * 86400)
    anterior = {"pulso_em": "2026-10-13T22:17:00"}
    texto = religou.verificar(tmp_path, anterior=anterior,
                              agora=BOOT + 48 * 60, boot=BOOT)
    assert texto.startswith("O PC religou as 22:43 (13/10)")
    assert "48 min depois" in texto
    assert "13/10 22:17" in texto and "1 h 14 min sem nada rodando" in texto
    # a mesma sessao (o coordenador religado) e o gatilho de 5 min: calado
    assert religou.verificar(tmp_path, anterior=anterior,
                             agora=BOOT + 3600, boot=BOOT + 30) is None


def test_religou_sem_boot_conhecido_nao_avisa(tmp_path):
    assert religou.verificar(tmp_path, anterior={}, boot=None) is None


def test_boot_em_e_no_passado():
    boot = religou.boot_em()
    assert boot is None or boot < time.time()
