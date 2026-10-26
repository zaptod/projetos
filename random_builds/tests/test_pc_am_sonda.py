# -*- coding: utf-8 -*-
"""A sonda do PC am, o roteamento automatico e a queda segura (ponto 9, 26/10/2026).

  - CASO ZERO: o am esta DESLIGADO (como em 26/10) -> o trabalho roda aqui, na
    hora, sem tentar SSH, sem aviso, sem erro: so uma linha de log;
  - sonda simulada "disponivel" -> o trabalho vai ao am;
  - "ocupado" -> o duelo (que nao espera) roda aqui; a medicao levanta;
  - o cache da sonda (45 s / 90 s) e o `forcar`;
  - arquivo de ativo que sobrou de uma queda NAO e "ocupado";
  - um trabalho pesado por vez no am (padrao 1);
  - a janela das postagens (ponto unico `relogio.py`);
  - o am nao fala com o GitHub (nao tem login; o Blue Lock e privado).
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime

import pytest

from builds.pc_am import lado_am, maquina, relogio, sonda
from builds.pc_am.maquina import AmFora, AmOcupado, NaJanela

# fixtures e ajudantes do teste vizinho (am = lado_am de verdade numa pasta temporaria)
from test_pc_am import (_ajustar_cwd, _rapido, _trabalho_que_escreve, am, avisos, cfg,  # noqa: F401
                        estado_isolado)


LIBERADO_REAL = relogio.liberado      # o autouse do vizinho troca por (True, "") a cada teste


def _sonda(estado, motivo=""):
    chamadas = []

    def lida(_cfg=None):
        chamadas.append(estado)
        return {"estado": estado, "motivo": motivo}
    lida.chamadas = chamadas
    return lida


def _proibido_o_ssh(*a, **k):
    pytest.fail("tentou o SSH com o am indisponivel")


# ------------------------------------------------------------- caso ZERO
def test_caso_zero_am_desligado_roda_aqui_sem_ssh_sem_aviso_sem_erro(am, cfg, tmp_path, avisos, capsys):
    am.chamar = _proibido_o_ssh            # qualquer conversa com o am falharia o teste
    am.enviar = _proibido_o_ssh
    resultado = maquina.executar(_trabalho_que_escreve(tmp_path / "x"), lambda: "local", cfg=cfg,
                                 transporte=am, avisar=avisos.append,
                                 sonda=_sonda(sonda.INDISPONIVEL, "ssh: connect timed out"), **_rapido())
    assert (resultado.onde, resultado.valor) == ("aqui", "local")
    assert "indisponivel" in resultado.motivo
    assert avisos == []                                            # SEM alarme
    assert not (tmp_path / "x").exists()
    saida = capsys.readouterr().out
    assert saida.count("[pc_am]") == 1 and "rodando neste PC" in saida   # UMA linha


def test_caso_zero_pela_sonda_real_com_o_ssh_sem_resposta(am, cfg, tmp_path, avisos, monkeypatch):
    """A sonda de verdade (`sonda.sondar`) contra um ssh que estoura o prazo,
    como um PC desligado: indisponivel, gravado no cache, trabalho aqui."""
    def ssh_morto(*a, **k):
        raise subprocess.TimeoutExpired("ssh", 12)
    monkeypatch.setattr(sonda.subprocess, "run", ssh_morto)
    am.chamar = _proibido_o_ssh
    resultado = maquina.executar(_trabalho_que_escreve(tmp_path / "x"), lambda: "local", cfg=cfg,
                                 transporte=am, avisar=avisos.append, sonda=sonda.sondar, **_rapido())
    assert resultado.onde == "aqui" and avisos == []
    gravado = json.loads(sonda.arquivo().read_text(encoding="utf-8"))
    assert gravado["estado"] == sonda.INDISPONIVEL and "nao respondeu" in gravado["motivo"]
    assert "indisponível" in sonda.texto(sonda.ultima())


def test_medicao_com_o_am_indisponivel_levanta_em_vez_de_rodar_aqui(am, cfg, tmp_path):
    with pytest.raises(AmFora):
        maquina.executar(_trabalho_que_escreve(tmp_path / "x"), lambda: pytest.fail("rodou aqui"),
                         cfg=cfg, transporte=am, cair_para_aqui=False, avisar=lambda t: None,
                         sonda=_sonda(sonda.INDISPONIVEL), **_rapido())


# ---------------------------------------------------- sonda simulada: disponivel
def test_sonda_disponivel_manda_o_pesado_para_o_am(am, cfg, tmp_path, avisos):
    destino = tmp_path / "aqui" / "produto"
    lida = _sonda(sonda.DISPONIVEL)
    resultado = maquina.executar(_ajustar_cwd(_trabalho_que_escreve(destino, conteudo="VIDEO")),
                                 lambda: pytest.fail("rodou aqui"), cfg=cfg, transporte=am,
                                 avisar=avisos.append, sonda=lida, **_rapido())
    assert resultado.onde == "am" and (destino / "video.mp4").read_text() == "VIDEO"
    assert lida.chamadas == [sonda.DISPONIVEL] and avisos == []


def test_sonda_disponivel_mas_o_ssh_cai_no_meio_avisa_e_marca_indisponivel(am, cfg, tmp_path, avisos):
    """A anomalia (a sonda disse que sim e o am sumiu): UM aviso, roda aqui, e
    o cache passa a dizer indisponivel (o proximo nem tenta)."""
    am.fora = True
    resultado = maquina.executar(_trabalho_que_escreve(tmp_path / "x"), lambda: "local", cfg=cfg,
                                 transporte=am, avisar=avisos.append,
                                 sonda=_sonda(sonda.DISPONIVEL), **_rapido())
    assert resultado.onde == "aqui" and len(avisos) == 1
    assert sonda.ultima()["estado"] == sonda.INDISPONIVEL


# ---------------------------------------------------------------- ocupado
def test_sonda_ocupado_o_duelo_nao_espera_e_roda_aqui(am, cfg, tmp_path, avisos):
    am.chamar = _proibido_o_ssh
    resultado = maquina.executar(_trabalho_que_escreve(tmp_path / "x"), lambda: "local", cfg=cfg,
                                 transporte=am, avisar=avisos.append, espera=0,
                                 sonda=_sonda(sonda.OCUPADO, "1 trabalho(s) rodando no am"), **_rapido())
    assert resultado.onde == "aqui" and "ocupado" in resultado.motivo and avisos == []


def test_sonda_ocupado_na_medicao_levanta_ocupado(am, cfg, tmp_path):
    with pytest.raises(AmOcupado):
        maquina.executar(_trabalho_que_escreve(tmp_path / "x"), lambda: pytest.fail("aqui"), cfg=cfg,
                         transporte=am, cair_para_aqui=False, espera=0, avisar=lambda t: None,
                         sonda=_sonda(sonda.OCUPADO), **_rapido())


# ------------------------------------------------------ a sonda em si (cache)
def test_cache_vale_45_s_disponivel_e_90_s_indisponivel_e_forcar_ignora(estado_isolado):
    relogio_falso = [1000.0]
    chamadas = []

    def ssh(cfg_am, s):
        chamadas.append(1)
        return (len(chamadas) != 1), "sem resposta", 0           # 1a: fora; depois: de pe

    def agora():
        return relogio_falso[0]
    cfg_am = maquina.carregar_config(__import__("pathlib").Path("nao-existe.json"))
    primeira = sonda.sondar(cfg_am, ssh=ssh, agora=agora)
    assert primeira["estado"] == sonda.INDISPONIVEL and not primeira["do_cache"]
    relogio_falso[0] += 80                                         # < 90: cache
    assert sonda.sondar(cfg_am, ssh=ssh, agora=agora)["do_cache"] and len(chamadas) == 1
    relogio_falso[0] += 20                                         # 100 s > 90: sonda de novo
    de_pe = sonda.sondar(cfg_am, ssh=ssh, agora=agora)
    assert de_pe["estado"] == sonda.DISPONIVEL and len(chamadas) == 2
    relogio_falso[0] += 44                                         # < 45: cache
    assert sonda.sondar(cfg_am, ssh=ssh, agora=agora)["do_cache"] and len(chamadas) == 2
    relogio_falso[0] += 2                                          # 46 s > 45
    assert not sonda.sondar(cfg_am, ssh=ssh, agora=agora)["do_cache"] and len(chamadas) == 3
    assert not sonda.sondar(cfg_am, ssh=ssh, agora=agora, forcar=True)["do_cache"] and len(chamadas) == 4


def test_arquivo_de_ativo_que_sobrou_nao_e_ocupado(estado_isolado):
    cfg_am = maquina.carregar_config(__import__("pathlib").Path("nao-existe.json"))
    sobra = sonda.sondar(cfg_am, forcar=True, ssh=lambda c, s: (True, "", 1), confirmar=lambda c: 0)
    assert sobra["estado"] == sonda.DISPONIVEL
    vivo = sonda.sondar(cfg_am, forcar=True, ssh=lambda c, s: (True, "", 1), confirmar=lambda c: 1)
    assert vivo["estado"] == sonda.OCUPADO and "1 trabalho" in vivo["motivo"]


def test_erro_inesperado_da_sonda_vira_indisponivel_nunca_excecao(estado_isolado):
    def quebra(c, s):
        raise RuntimeError("boom")
    assert sonda.sondar(ssh=quebra, forcar=True)["estado"] == sonda.INDISPONIVEL


def test_texto_para_o_retrato_e_o_status():
    assert sonda.texto({}) == "PC am: sem sonda ainda"
    assert "disponível" in sonda.texto({"estado": sonda.DISPONIVEL, "idade_s": 3.0})
    assert "indisponível" in sonda.texto({"estado": sonda.INDISPONIVEL, "idade_s": 3.0, "motivo": "x"})


def test_sonda_velha_avisa_e_o_status_do_coordenador_mostra_a_linha(estado_isolado, monkeypatch, capsys):
    assert "VELHA" in sonda.texto({"estado": sonda.DISPONIVEL, "idade_s": 7200.0})
    monkeypatch.setattr(sonda, "ultima", lambda: {"estado": sonda.INDISPONIVEL, "idade_s": 5.0, "motivo": "desligado"})
    from coordenador import __main__ as coord
    coord.main(["status", "--curto"])
    saida = capsys.readouterr().out
    assert "PC am: indispon" in saida and "o pesado roda neste PC" in saida


def test_a_sonda_pelo_comando_nao_levanta_e_diz_uma_linha(estado_isolado, monkeypatch, capsys):
    from builds.pc_am import __main__ as cli
    monkeypatch.setattr(sonda, "ssh_barato", lambda c, s: (False, "desligado", 0))
    codigo = cli.main(["sonda", "--agora"])
    assert codigo == 2 and capsys.readouterr().out.startswith("PC am: indispon")


# ---------------------------------------------------- um pesado por vez
def test_o_padrao_e_um_trabalho_pesado_por_vez_no_am():
    assert maquina.paralelo({})["maximo"] == 1
    assert maquina.paralelo(maquina.carregar_config())["maximo"] == 1      # e o config entregue
    com_um = {"ativos": [{"id": "x"}], "memoria_livre_mb": 99999}
    ok, motivo = maquina.cabe(com_um, "duelo", {})
    assert not ok and "maximo 1" in motivo
    assert maquina.cabe({"ativos": [], "memoria_livre_mb": 99999}, "duelo", {})[0]


# ------------------------------------------------------------- a janela
def test_janela_central_e_a_fonte_unica_e_cai_para_as_outras():
    dentro = datetime(2026, 10, 26, 12, 0)             # post 12:07, janela 11:55-12:25
    fora = datetime(2026, 10, 26, 13, 30)
    assert relogio._pela_grade(dentro)[0] is True and relogio._pela_grade(fora)[0] is False
    assert LIBERADO_REAL(dentro)[0] is False
    assert LIBERADO_REAL(fora) == (True, "")

    def quebrada(_):
        raise ImportError("sem a central")
    assert LIBERADO_REAL(dentro, fontes=(quebrada, relogio._pela_grade))[0] is False
    assert LIBERADO_REAL(fora, fontes=(quebrada, relogio._pela_grade)) == (True, "")
    pode, motivo = LIBERADO_REAL(fora, fontes=(quebrada,))          # nao consegui ler: espera
    assert pode is False and "nao consegui" in motivo


def test_dentro_da_janela_nada_vai_ao_am_e_a_chave_desligada_nao_e_barrada(am, cfg, tmp_path, monkeypatch):
    monkeypatch.setattr(relogio, "liberado", lambda *a, **k: (False, "janela das postagens (12:07)"))
    with pytest.raises(NaJanela):
        maquina.executar(_trabalho_que_escreve(tmp_path / "x"), lambda: pytest.fail("aqui"), cfg=cfg,
                         transporte=am, avisar=lambda t: None, sonda=_sonda(sonda.DISPONIVEL), **_rapido())
    assert am.chamadas == []
    cfg["trabalhos"]["testes"] = False                # desligada: e o de sempre, aqui, sem opinar
    resultado = maquina.executar(_trabalho_que_escreve(tmp_path / "y"), lambda: "local", cfg=cfg,
                                 transporte=am, avisar=lambda t: None, **_rapido())
    assert resultado.onde == "aqui"


# ---------------------------------------------------- sem GitHub no am
def test_o_am_nunca_fala_com_o_github(am, tmp_path, monkeypatch):
    """Sem clone, com o commit so aqui: o codigo chega por bundle. Nenhum
    comando do lado do am menciona `origin` nem uma URL."""
    comandos = []
    original = lado_am._rodar

    def espiao(comando, *a, **k):
        comandos.append(" ".join(str(c) for c in comando))
        return original(comando, *a, **k)
    monkeypatch.setattr(lado_am, "_rodar", espiao)
    aqui = tmp_path / "aqui"
    aqui.mkdir()
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                 ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", "-C", str(aqui), *args], check=True, capture_output=True)
    (aqui / "a.py").write_text("v = 1\n")
    subprocess.run(["git", "-C", str(aqui), "add", "a.py"], check=True)
    subprocess.run(["git", "-C", str(aqui), "commit", "-qm", "um"], check=True, capture_output=True)
    (aqui / "a.py").write_text("v = 2\n")
    repo = {"nome": "BLUE-Lock-project", "raiz": aqui, "url": "https://github.com/zaptod/BLUE-Lock-project.git",
            "mudancas": True, "instalar": False}
    resposta = maquina.sincronizar(am, repo)
    assert resposta["ok"] and (am.base / "BLUE-Lock-project" / "a.py").read_text().strip() == "v = 2"
    assert comandos and not [c for c in comandos if "origin" in c or "http" in c or "github" in c.lower()]
    # commit explicito (o ramo que o vigia do Blue Lock quer testar): tambem por bundle
    (aqui / "a.py").write_text("v = 3\n")
    subprocess.run(["git", "-C", str(aqui), "commit", "-qam", "tres"], check=True, capture_output=True)
    sha = subprocess.run(["git", "-C", str(aqui), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "-C", str(aqui), "commit", "-q", "--allow-empty", "-m", "quatro"], check=True,
                   capture_output=True)
    resposta = maquina.sincronizar(am, {**repo, "commit": sha, "mudancas": False})
    assert resposta["ok"] and resposta["commit"] == sha
    assert (am.base / "BLUE-Lock-project" / "a.py").read_text().strip() == "v = 3"
    refs = subprocess.run(["git", "-C", str(aqui), "for-each-ref", "refs/pcam"], capture_output=True,
                          text=True).stdout
    assert refs.strip() == ""                                  # a ref temporaria do bundle sumiu
