# -*- coding: utf-8 -*-
"""A trava central das postagens (`builds.janela`): bordas, troca de grade
por data, dia sem postagem, serie do Blue Lock, publicacao em voo, espera e as
ferramentas ligadas a ela (`testar`, `coordenador reiniciar`, bluelock)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from builds import janela

LIVRE = lambda: False        # noqa: E731 - publicacao em voo dublada
VOANDO = lambda: True        # noqa: E731


def dentro(agora, **kw):
    kw.setdefault("em_voo", LIVRE)
    return janela.em_janela(agora, **kw)


# -------------------------------------------------------------- bordas
@pytest.mark.parametrize("hora,minuto", [(6, 37), (9, 37), (12, 7), (15, 37),
                                         (17, 57), (20, 37), (21, 37),
                                         (22, 37), (23, 37)])
def test_bordas_de_menos_12_a_mais_18_em_cada_postagem_de_28_10(hora, minuto):
    post = datetime(2026, 10, 28, hora, minuto)
    assert dentro(post - timedelta(minutes=12))[0]
    assert not dentro(post - timedelta(minutes=12, seconds=1))[0]
    assert dentro(post)[0]
    assert dentro(post + timedelta(minutes=17, seconds=59))[0]
    assert not dentro(post + timedelta(minutes=18))[0]


def test_ate_quando_e_o_fim_da_janela():
    ok, motivo, ate = dentro(datetime(2026, 10, 28, 12, 0))
    assert ok and ate == datetime(2026, 10, 28, 12, 25)
    assert "12:07" in motivo and "12:25" in motivo


def test_janelas_que_se_tocam_se_emendam():
    # 21:37 (fim 21:55) e 22:37 (inicio 22:25) nao se tocam; ja 22:37 (fim
    # 22:55) e 23:37 (inicio 23:25) tambem nao. Com antes=45 elas se emendam.
    _ok, _m, ate = dentro(datetime(2026, 10, 28, 21, 40), antes=45)
    assert ate == datetime(2026, 10, 28, 23, 55)


# -------------------------------------------------------------- grade por data
def test_26_10_ainda_tem_as_historias_nos_dez_horarios():
    # antes de 27/10 so os builds tinham grade propria; as historias postavam
    # na grade inteira, 00:37 inclusive
    assert dentro(datetime(2026, 10, 26, 0, 30))[0]
    assert dentro(datetime(2026, 10, 26, 15, 30))[0]


def test_27_10_o_00_37_deixa_de_existir_e_a_madrugada_fica_livre():
    assert not dentro(datetime(2026, 10, 27, 0, 30))[0]          # sem 00:37 no dia 27
    assert not dentro(datetime(2026, 10, 28, 0, 30))[0]
    # a virada da meia-noite: o 23:37 de ontem vai a 23:55 e nao passa disso
    assert dentro(datetime(2026, 10, 27, 23, 50))[0]
    assert not dentro(datetime(2026, 10, 28, 0, 0))[0]


def test_horarios_do_dia_batem_com_as_grades_reais():
    antes = [p.strftime("%H:%M") for p in janela.horarios_do_dia(datetime(2026, 10, 26))]
    assert antes == ["00:37", "06:37", "09:37", "12:07", "15:37", "17:57",
                     "20:37", "21:37", "22:37", "23:37"]
    depois = [p.strftime("%H:%M") for p in janela.horarios_do_dia(datetime(2026, 10, 28))]
    assert depois == ["06:37", "09:37", "12:07", "15:37", "17:57", "20:37",
                      "21:37", "22:37", "23:37"]


# -------------------------------------------------------------- caso zero e serie
def test_dia_sem_postagem_perto_esta_livre():
    ok, motivo, ate = dentro(datetime(2026, 10, 28, 3, 0))
    assert (ok, motivo, ate) == (False, "", None)


def test_serie_do_blue_lock_as_20_37_tem_janela_propria():
    assert dentro(datetime(2026, 10, 28, 20, 25))[0]
    assert dentro(datetime(2026, 10, 28, 20, 54))[0]
    assert not dentro(datetime(2026, 10, 28, 20, 24, 59))[0]
    assert not dentro(datetime(2026, 10, 28, 20, 55))[0]
    assert "20:37" in dentro(datetime(2026, 10, 28, 20, 30))[1]


# -------------------------------------------------------------- publicacao em voo
def test_publicacao_em_voo_barra_fora_do_relogio_sem_prazo():
    ok, motivo, ate = janela.em_janela(datetime(2026, 10, 28, 3, 0), em_voo=VOANDO)
    assert ok and ate is None and "publicação" in motivo
    assert janela.em_janela(datetime(2026, 10, 28, 3, 0), em_voo=VOANDO,
                            olhar_voo=False)[0] is False


# -------------------------------------------------------------- proxima e esperar
def test_proxima_janela_e_a_em_curso_ou_a_seguinte():
    i, f, p = janela.proxima_janela(datetime(2026, 10, 28, 3, 0))
    assert (i, f, p) == (datetime(2026, 10, 28, 6, 25), datetime(2026, 10, 28, 6, 55),
                         datetime(2026, 10, 28, 6, 37))
    assert janela.proxima_janela(datetime(2026, 10, 28, 12, 10))[2] == datetime(2026, 10, 28, 12, 7)
    # depois do ultimo do dia, o primeiro de amanha
    assert janela.proxima_janela(datetime(2026, 10, 28, 23, 58))[2] == datetime(2026, 10, 29, 6, 37)


class Relogio:
    def __init__(self, inicio):
        self.t = inicio
        self.dormiu = []

    def agora(self):
        return self.t

    def dormir(self, s):
        self.dormiu.append(s)
        self.t += timedelta(seconds=s)


def test_esperar_ate_a_janela_passar():
    r = Relogio(datetime(2026, 10, 28, 12, 20))               # termina 12:25
    assert janela.esperar_fora_da_janela(1800, agora=r.agora, dormir=r.dormir,
                                         em_voo=LIVRE) is True
    assert r.t >= datetime(2026, 10, 28, 12, 25)


def test_esperar_desiste_sem_dormir_se_nao_passa_no_prazo():
    r = Relogio(datetime(2026, 10, 28, 12, 0))                # faltam 25 min
    assert janela.esperar_fora_da_janela(300, agora=r.agora, dormir=r.dormir,
                                         em_voo=LIVRE) is False
    assert r.dormiu == []


def test_esperar_livre_volta_na_hora():
    r = Relogio(datetime(2026, 10, 28, 3, 0))
    assert janela.esperar_fora_da_janela(10, agora=r.agora, dormir=r.dormir,
                                         em_voo=LIVRE) is True and r.dormiu == []


def test_esperar_publicacao_em_voo_tenta_de_30_em_30_e_desiste():
    r = Relogio(datetime(2026, 10, 28, 3, 0))
    assert janela.esperar_fora_da_janela(100, agora=r.agora, dormir=r.dormir,
                                         em_voo=VOANDO) is False
    assert r.dormiu == [30, 30, 30]


# -------------------------------------------------------------- recusa e CLI
def test_recusa_diz_o_motivo_e_o_forcar():
    texto = janela.recusa("testar", datetime(2026, 10, 28, 12, 0), em_voo=LIVRE)
    assert "testar recusado" in texto and "12:07" in texto and "--forcar" in texto
    assert janela.recusa("testar", datetime(2026, 10, 28, 3, 0), em_voo=LIVRE) is None


def test_cli_agora_sai_2_dentro_e_0_fora(monkeypatch, capsys):
    monkeypatch.setattr(janela, "publicacao_em_voo", lambda *a: False)
    relogio = {"t": datetime(2026, 10, 28, 12, 0)}

    class Fake(datetime):
        @classmethod
        def now(cls, tz=None):
            return relogio["t"]
    monkeypatch.setattr(janela, "datetime", Fake)
    assert janela.main(["agora"]) == 2
    assert "NÃO PODE" in capsys.readouterr().out
    relogio["t"] = datetime(2026, 10, 28, 3, 0)
    assert janela.main(["agora"]) == 0
    assert "pode" in capsys.readouterr().out


# -------------------------------------------------------------- ferramentas ligadas
def test_testar_recusa_dentro_da_janela_e_o_forcar_passa(monkeypatch, capsys):
    import testar
    monkeypatch.setattr(janela, "datetime", type("F", (datetime,), {
        "now": classmethod(lambda cls, tz=None: datetime(2026, 10, 28, 12, 0))}))
    monkeypatch.setattr(janela, "publicacao_em_voo", lambda *a: False)
    assert testar.main([]) == 4
    assert "testar recusado" in capsys.readouterr().out
    # --forcar nao recusa (--lista evita rodar a suite de verdade)
    assert testar.main(["--forcar", "--lista"]) == 0


def test_testar_usa_margem_maior_antes_do_post(monkeypatch):
    import testar
    monkeypatch.setattr(janela, "publicacao_em_voo", lambda *a: False)
    # 11:40 esta a 27 min do post das 12:07: livre para a lei, barrado para a suite
    assert janela.em_janela(datetime(2026, 10, 28, 11, 40), em_voo=LIVRE)[0] is False
    assert janela.em_janela(datetime(2026, 10, 28, 11, 40), antes=testar.ANTES_MIN,
                            em_voo=LIVRE)[0] is True


def test_reiniciar_forcar_ignora_so_a_janela(monkeypatch):
    from coordenador import __main__ as cli
    criados = []

    class Falso:
        ultima_recusa = {}
        estado = {"app": {}}

        def __init__(self, janela=None):
            criados.append(janela)

        def reiniciar_servico(self, nome):
            return True

    monkeypatch.setattr(cli, "Supervisor", Falso)
    saida = []
    assert cli.reiniciar_pela_linha_de_comando("app", saida=saida.append, forcar=True) == 0
    assert criados[0](datetime(2026, 10, 28, 12, 0)) == (False, "")      # janela ignorada
    cli.reiniciar_pela_linha_de_comando("app", saida=saida.append)
    assert criados[1] is None                                            # sem --forcar: a de sempre


def test_reiniciar_recusado_na_janela_sugere_forcar():
    from coordenador import __main__ as cli

    class Recusa:
        ultima_recusa = {"app": {"tipo": "momento", "motivo": "janela das postagens (12:07, em 5 min)"}}
        estado = {"app": {}}

        def reiniciar_servico(self, nome):
            return False

    saida = []
    codigo = cli.reiniciar_pela_linha_de_comando("app", supervisor=Recusa(),
                                                 pendente=lambda n: None, saida=saida.append)
    assert codigo == 2 and "--forcar" in saida[0]


def test_bluelock_delega_a_trava_central(monkeypatch):
    from bluelock import comum
    # janela larga do bluelock (18 antes): 09:19 ja esta dentro, na grade real de 28/10
    assert comum.janela_das_postagens(datetime(2026, 10, 28, 9, 19))[0] is True
    assert comum.janela_das_postagens(datetime(2026, 10, 28, 9, 18))[0] is False
    # e enxerga a serie das 20:37 e o dia sem 00:37
    assert comum.janela_das_postagens(datetime(2026, 10, 28, 20, 19))[0] is True
    assert comum.janela_das_postagens(datetime(2026, 10, 28, 0, 30))[0] is False
    monkeypatch.setattr(janela, "publicacao_em_voo", lambda *a: True)
    pode, motivo = comum.pode_pesado(datetime(2026, 10, 28, 3, 0), league=lambda: False)
    assert not pode and "publicação" in motivo
