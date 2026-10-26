# -*- coding: utf-8 -*-
"""O trabalhador remoto (PC am) com um DUBLE de SSH.

O duble nao finge o agente: ele chama o `lado_am.py` DE VERDADE, numa pasta
temporaria no lugar de `C:\\nf` (`PC_AM_BASE`), e o trabalho roda num
subprocesso de verdade (`PC_AM_LANCAR=popen` no lugar do WMI). So o
transporte (ssh/scp) e trocado por copia de arquivo. Os casos:

  - ZERO: chave desligada -> roda aqui, sem tocar no am;
  - am fora -> roda aqui, com UM aviso por queda;
  - am ok -> roda la e o produto chega, conferido, no destino;
  - trabalho que falha la -> erro claro e NADA pela metade aqui;
  - produto que chega diferente -> recusado, nada no destino;
  - am ocupado, prazo estourado, sincronia do codigo por bundle + diff;
  - o duelo trazido vira o proximo duelo daqui, com os caminhos trocados.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from builds.pc_am import lado_am, maquina, relogio, trabalhos
from builds.pc_am.maquina import AmFora, FalhaNoAm, Trabalho

PY = sys.executable


class TransporteFalso:
    """ssh/scp trocados por copia; o agente e o lado_am.py de verdade."""

    def __init__(self, base: Path, fora: bool = False):
        self.base = base
        self.fora = fora
        self.chamadas: list[str] = []
        self.enviados: list[str] = []
        self.estragar = False

    def chamar(self, acao, parametros=None, prazo=None):
        if self.fora:
            raise AmFora("duble: o SSH nao conectou")
        self.chamadas.append(acao)
        return lado_am.chamar(acao, dict(parametros or {}))

    def enviar(self, pares, prazo=None):
        if self.fora:
            raise AmFora("duble: o scp nao conectou")
        for local, rel in pares:
            alvo = self.base / rel
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local, alvo)
            self.enviados.append(rel)

    def receber(self, rel, pasta_local, prazo=None):
        origem = self.base / rel
        pasta_local.mkdir(parents=True, exist_ok=True)
        alvo = pasta_local / origem.name
        if origem.is_dir():
            shutil.copytree(origem, alvo)
        else:
            shutil.copy2(origem, alvo)
        if self.estragar:
            arquivo = next(p for p in ([alvo] if alvo.is_file() else alvo.rglob("*")) if p.is_file())
            arquivo.write_bytes(arquivo.read_bytes() + b"!")


@pytest.fixture
def am(tmp_path, monkeypatch):
    base = tmp_path / "nf"
    base.mkdir()
    monkeypatch.setenv("PC_AM_BASE", str(base))
    monkeypatch.setenv("PC_AM_LANCAR", "popen")
    (base / "trabalho").mkdir()
    return TransporteFalso(base)


@pytest.fixture(autouse=True)
def estado_isolado(tmp_path, monkeypatch):
    """O estado da queda (um aviso por queda) de cada teste e so dele."""
    pasta = tmp_path / "runtime_pc_am"
    pasta.mkdir()
    monkeypatch.setattr(maquina, "runtime", lambda: pasta)
    # a janela das postagens depende da HORA: o teste nao pode (ver test_pc_am_sonda.py)
    monkeypatch.setattr(relogio, "liberado", lambda *a, **k: (True, ""))


@pytest.fixture
def cfg():
    config = maquina.carregar_config(Path("nao-existe.json"))
    config.update(trabalhos={"testes": True, "duelo": True, "bluelock": True},
                  disco_minimo_gb=0, memoria_minima_mb=0, espera_da_fila_s={},
                  # a memoria livre e a DESTE PC (o lado_am roda aqui): sem reserva
                  paralelo={"maximo": 3, "cpu_alvo": 101, "memoria_reserva_mb": -10 ** 6, "janela_cpu_s": 30})
    return config


@pytest.fixture
def avisos():
    return []


class Relogio:
    """Relogio de mentira: so anda quando alguem dorme (a paciencia de 45 s
    com o am fora acaba na hora, sem o teste esperar de verdade)."""

    def __init__(self):
        self.agora = 0.0

    def __call__(self):
        return self.agora

    def dorme(self, segundos):
        self.agora += segundos
        __import__("time").sleep(0.02)


def _rapido(**kw):
    relogio = Relogio()
    return dict(dorme=relogio.dorme, relogio=relogio, **kw)


def _trabalho_que_escreve(destino: Path, conteudo: str = "ok", rc: int = 0, **kw) -> Trabalho:
    codigo = (f"import pathlib,sys; p=pathlib.Path('saida'); p.mkdir(exist_ok=True); "
              f"(p/'video.mp4').write_text({conteudo!r}); (p/'luta.json').write_text('{{}}'); "
              f"print('feito'); sys.exit({rc})")
    return Trabalho(tipo="testes", comando=["{PY}", "-c", codigo], cwd=".", saida="trabalho/saida",
                    destino=destino, prazo_s=kw.pop("prazo_s", 60), **kw)


def _ajustar_cwd(trabalho: Trabalho) -> Trabalho:
    trabalho.cwd = "trabalho"
    return trabalho


# ------------------------------------------------------------------ chaves
def test_so_true_liga(tmp_path):
    config = tmp_path / "pc_am.json"
    config.write_text(json.dumps({"trabalhos": {"duelo": True, "testes": "sim", "bluelock": 1}}))
    cfg = maquina.carregar_config(config)
    assert maquina.ligado("duelo", cfg)
    assert not maquina.ligado("testes", cfg) and not maquina.ligado("bluelock", cfg)
    config.write_text("{ilegivel")
    assert not maquina.ligado("duelo", maquina.carregar_config(config))


def test_config_do_repositorio_so_liga_o_que_nao_mexe_no_estoque():
    """26/10/2026: testes e Blue Lock ligados (com o am fora rodam aqui, como
    sempre); o DUELO afeta o estoque do canal e so liga com a prova no am."""
    cfg = maquina.carregar_config()
    assert cfg["trabalhos"] == {"testes": True, "duelo": False, "bluelock": True}
    assert cfg["paralelo"]["maximo"] == 1


# -------------------------------------------------------------- caso ZERO
def test_caso_zero_chave_desligada_roda_aqui_sem_tocar_no_am(am, cfg, tmp_path, avisos):
    cfg["trabalhos"]["testes"] = False
    resultado = maquina.executar(_trabalho_que_escreve(tmp_path / "x"), lambda: "local", cfg=cfg,
                                 transporte=am, avisar=avisos.append, **_rapido())
    assert (resultado.onde, resultado.valor, resultado.motivo) == ("aqui", "local", "chave desligada")
    assert am.chamadas == [] and avisos == []


def test_am_fora_roda_aqui_com_um_aviso_por_queda(am, cfg, tmp_path, avisos):
    am.fora = True
    for _ in range(2):
        resultado = maquina.executar(_trabalho_que_escreve(tmp_path / "x"), lambda: "local", cfg=cfg,
                                     transporte=am, avisar=avisos.append, **_rapido())
        assert resultado.onde == "aqui" and resultado.valor == "local"
        assert "am fora" in resultado.motivo
    assert len(avisos) == 1 and "PC am fora" in avisos[0]
    assert not (tmp_path / "x").exists()
    # voltou: o proximo trabalho vai la, e a queda seguinte avisa de novo
    am.fora = False
    ok = maquina.executar(_ajustar_cwd(_trabalho_que_escreve(tmp_path / "y")), lambda: "local", cfg=cfg,
                          transporte=am, avisar=avisos.append, **_rapido())
    assert ok.onde == "am"
    am.fora = True
    maquina.executar(_trabalho_que_escreve(tmp_path / "z"), lambda: "local", cfg=cfg, transporte=am,
                     avisar=avisos.append, **_rapido())
    assert len(avisos) == 2


# ------------------------------------------------------------------- am ok
def test_am_ok_roda_la_e_traz_conferido(am, cfg, tmp_path, avisos):
    destino = tmp_path / "aqui" / "produto"
    trabalho = _ajustar_cwd(_trabalho_que_escreve(destino, conteudo="VIDEO"))
    resultado = maquina.executar(trabalho, lambda: pytest.fail("nao devia rodar aqui"), cfg=cfg,
                                 transporte=am, avisar=avisos.append, **_rapido())
    assert resultado.onde == "am" and resultado.rc == 0 and resultado.destino == destino
    assert (destino / "video.mp4").read_text() == "VIDEO"
    assert (destino / "luta.json").is_file()
    assert "feito" in resultado.log
    assert list(destino.parent.glob(".pc_am-*")) == []          # nada de temporario
    assert not (am.base / "ativo.json").exists()                  # a fila do am liberou
    assert avisos == []


def test_entrada_que_nao_mudou_nao_vai_de_novo(am, cfg, tmp_path):
    banco = tmp_path / "personagens.json"
    banco.write_text('{"a": 1}')
    for i in range(2):
        trabalho = _ajustar_cwd(_trabalho_que_escreve(tmp_path / f"d{i}"))
        trabalho.entradas = [(banco, "runtime/personagens.json")]
        maquina.executar(trabalho, lambda: None, cfg=cfg, transporte=am, avisar=lambda t: None, **_rapido())
    assert len(am.enviados) == 1 and am.enviados[0].endswith(".zip")      # um zip, um scp
    banco.write_text('{"a": 2}')
    trabalho = _ajustar_cwd(_trabalho_que_escreve(tmp_path / "d2"))
    trabalho.entradas = [(banco, "runtime/personagens.json")]
    maquina.executar(trabalho, lambda: None, cfg=cfg, transporte=am, avisar=lambda t: None, **_rapido())
    assert len(am.enviados) == 2
    assert list((am.base / "tmp").glob("*.zip")) == []                    # o zip some depois de aberto
    assert (am.base / "runtime" / "personagens.json").read_text() == '{"a": 2}'


# ---------------------------------------------------------- falha la
def test_trabalho_que_falha_la_da_erro_claro_e_nada_aqui(am, cfg, tmp_path):
    destino = tmp_path / "aqui" / "produto"
    trabalho = _ajustar_cwd(_trabalho_que_escreve(destino, rc=3))
    with pytest.raises(FalhaNoAm) as erro:
        maquina.executar(trabalho, lambda: pytest.fail("nao devia cair"), cfg=cfg, transporte=am,
                         cair_na_falha=False, avisar=lambda t: None, **_rapido())
    assert "rc 3" in str(erro.value) and "feito" in str(erro.value)   # o motivo e o fim do log
    assert not destino.exists()
    assert not destino.parent.exists() or list(destino.parent.iterdir()) == []


def test_falha_la_na_producao_cai_para_aqui(am, cfg, tmp_path):
    trabalho = _ajustar_cwd(_trabalho_que_escreve(tmp_path / "p", rc=1))
    resultado = maquina.executar(trabalho, lambda: "local", cfg=cfg, transporte=am,
                                 avisar=lambda t: None, **_rapido())
    assert resultado.onde == "aqui" and resultado.valor == "local"
    assert resultado.motivo.startswith("falhou no am")


def test_produto_que_chega_diferente_e_recusado(am, cfg, tmp_path):
    am.estragar = True
    destino = tmp_path / "aqui" / "produto"
    with pytest.raises(FalhaNoAm, match="chegou diferente"):
        maquina.executar(_ajustar_cwd(_trabalho_que_escreve(destino)), lambda: None, cfg=cfg,
                         transporte=am, cair_na_falha=False, avisar=lambda t: None, **_rapido())
    assert not destino.exists()
    assert list(destino.parent.glob(".pc_am-*")) == []


def test_sem_produto_e_falha(am, cfg, tmp_path):
    trabalho = Trabalho(tipo="testes", comando=["{PY}", "-c", "print(1)"], cwd="trabalho",
                        saida="trabalho/saida", destino=tmp_path / "p", prazo_s=30)
    with pytest.raises(FalhaNoAm, match="esperava 1 produto"):
        maquina.executar(trabalho, lambda: None, cfg=cfg, transporte=am, cair_na_falha=False,
                         avisar=lambda t: None, **_rapido())


def test_prazo_estourado_mata_o_trabalho_la(am, cfg, tmp_path):
    trabalho = Trabalho(tipo="testes", comando=["{PY}", "-c", "import time; time.sleep(30)"],
                        cwd="trabalho", prazo_s=1)
    with pytest.raises(FalhaNoAm, match="rc 124"):
        maquina.executar(trabalho, lambda: None, cfg=cfg, transporte=am, cair_na_falha=False,
                         avisar=lambda t: None, **_rapido())
    assert not (am.base / "ativo.json").exists()


def test_am_cheio_roda_aqui_na_producao_e_espera_na_medicao(am, cfg, tmp_path):
    cfg["paralelo"]["maximo"] = 1
    # um cliente antigo (o ativo.json de antes) conta como trabalho rodando
    (am.base / "ativo.json").write_text(json.dumps({"id": "outro", "pid": os.getpid()}))
    resultado = maquina.executar(_trabalho_que_escreve(tmp_path / "x"), lambda: "local", cfg=cfg,
                                 transporte=am, avisar=lambda t: None, **_rapido())
    assert resultado.onde == "aqui" and "cheio" in resultado.motivo
    with pytest.raises(maquina.AmOcupado):                      # e NAO "am fora"
        maquina.executar(_trabalho_que_escreve(tmp_path / "x"), lambda: pytest.fail("aqui"), cfg=cfg,
                         transporte=am, cair_para_aqui=False, avisar=lambda t: None, espera=60, **_rapido())
    # o lancar tambem recusa um segundo (a saude pode ter visto o am livre)
    resposta = lado_am.chamar("lancar", {"id": "segundo", "comando": ["{PY}", "-c", "1"]})
    assert resposta.get("ocupado") is True


def test_agente_de_outra_versao_e_recusado(am):
    resposta = lado_am.chamar("saude", {"_versao": "velha"})
    assert resposta == {"ok": False, "versao_errada": True, "versao": lado_am.versao()}


def test_agente_nao_sai_da_pasta_dele(am):
    assert lado_am.chamar("apagar", {"caminhos": ["../*"]})["ok"] is False


# ---------------------------------------------------------------- codigo
def _git(pasta: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(pasta), *args], capture_output=True, text=True,
                          check=True).stdout.strip()


def test_sincronia_leva_o_commit_por_bundle_e_as_mudancas(am, tmp_path):
    origem = tmp_path / "origem.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origem)], check=True)
    aqui = tmp_path / "aqui"
    subprocess.run(["git", "clone", "-q", str(origem), str(aqui)], check=True, capture_output=True)
    for chave, valor in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _git(aqui, "config", chave, valor)
    (aqui / "a.py").write_text("v = 1\n")
    _git(aqui, "add", "a.py")
    _git(aqui, "commit", "-qm", "um")
    _git(aqui, "push", "-q", "origin", "HEAD:main")
    # o am clona do "GitHub" (a origem) e o daqui anda um commit sem push
    (aqui / "a.py").write_text("v = 2\n")
    _git(aqui, "commit", "-qam", "dois")
    (aqui / "a.py").write_text("v = 3\n")                    # e uma mudanca nao commitada
    (aqui / "solto.py").write_text("")                       # e um arquivo sem git add
    repo = {"nome": "projetos", "raiz": aqui, "url": str(origem), "mudancas": True, "instalar": False}
    resposta = maquina.sincronizar(am, repo)
    clone = am.base / "projetos"
    assert resposta["ok"] and resposta["commit"] == _git(aqui, "rev-parse", "HEAD")
    assert _git(clone, "rev-parse", "HEAD") == _git(aqui, "rev-parse", "HEAD")
    assert (clone / "a.py").read_text().strip() == "v = 3"
    assert resposta["diff"] == ["a.py"] and resposta["nao_rastreados"] == ["solto.py"]
    # de novo, sem mudanca: o clone volta limpo ao commit
    (aqui / "a.py").write_text("v = 2\n")
    maquina.sincronizar(am, repo)
    assert (clone / "a.py").read_text().strip() == "v = 2"


# ------------------------------------------------------------------- duelo
def test_duelo_trazido_vira_o_proximo_daqui_com_caminhos_trocados(tmp_path, monkeypatch):
    outputs = tmp_path / "outputs"
    (outputs / "duelo_00041").mkdir(parents=True)
    monkeypatch.setattr(trabalhos, "OUTPUTS", outputs)
    veio = tmp_path / ".pc_am-x" / "duelo_00001"
    (veio / "gameplay").mkdir(parents=True)
    remoto = r"C:\nf\projetos\random_builds\outputs\duelo_00001"
    fight = {"duelo_id": "duelo_00001", "seed": 7, "luta": {"duracao": 21.5},
             "clipe": remoto + r"\gameplay\luta_00_celular.mp4",
             "musica": r"C:\nf\projetos\random_builds\assets\music\trilha.wav",
             "nome": "duelo_00001 nao e o id inteiro"}
    (veio / "fight.json").write_text(json.dumps(fight), encoding="utf-8")
    (veio / "gameplay" / "luta_00_celular.mp4").write_bytes(b"mp4")
    destino = trabalhos.instalar_duelo(veio, None)
    assert destino == outputs / "duelo_00042" and not veio.exists()
    novo = json.loads((destino / "fight.json").read_text(encoding="utf-8"))
    assert novo["duelo_id"] == "duelo_00042"
    assert novo["clipe"] == str(destino / "gameplay" / "luta_00_celular.mp4")
    assert novo["musica"] == str(trabalhos.RAIZ / "random_builds" / "assets" / "music" / "trilha.wav")
    assert novo["luta"] == fight["luta"] and novo["nome"] == fight["nome"]


def test_duelo_com_chave_desligada_e_o_de_sempre(monkeypatch, cfg):
    cfg["trabalhos"]["duelo"] = False
    monkeypatch.setattr(trabalhos, "escolher", lambda p1, p2, seed: ("A", "B", 9))
    chamadas = []

    class Controlador:
        def duelo(self, **kw):
            chamadas.append(kw)
            return Path("duelo_local")
    assert trabalhos.duelo(Controlador(), cfg=cfg) == Path("duelo_local")
    assert chamadas == [{"p1": "A", "p2": "B", "seed": 9, "cenario": None, "preview": False}]


def test_duelo_com_am_fora_roda_aqui_com_o_mesmo_par_e_semente(monkeypatch, cfg, tmp_path):
    monkeypatch.setattr(trabalhos, "escolher", lambda p1, p2, seed: ("A", "B", 9))
    monkeypatch.setattr(trabalhos, "entradas_do_duelo", lambda p1, p2: ([], [], []))
    chamadas = []

    class Controlador:
        def duelo(self, **kw):
            chamadas.append(kw)
            return Path("duelo_local")
    fora = TransporteFalso(tmp_path, fora=True)
    pasta = trabalhos.duelo(Controlador(), cfg=cfg, transporte=fora, avisar=lambda t: None, **_rapido())
    assert pasta == Path("duelo_local") and chamadas[0]["seed"] == 9 and chamadas[0]["p1"] == "A"


def test_alvo_dos_testes_igual_ao_testar_py():
    assert trabalhos._alvo_dos_testes("coordenador") == ("", "coordenador")
    assert trabalhos._alvo_dos_testes("random_builds") == ("random_builds", "tests")
    assert trabalhos._alvo_dos_testes("historias/tests/test_x.py") == ("historias", "tests/test_x.py")
    assert trabalhos.placar("x\n== 2 failed, 593 passed, 1 skipped in 38.21s ==") == \
        "2 failed, 593 passed, 1 skipped"


class Piscando(TransporteFalso):
    """O relay do Tailscale piscando: as N primeiras perguntas de `estado`
    (o trabalho ja lancado) nao conectam."""

    def __init__(self, base, falhas):
        super().__init__(base)
        self.falhas = falhas

    acao_que_pisca = "estado"

    def chamar(self, acao, parametros=None, prazo=None):
        if acao == self.acao_que_pisca and self.falhas > 0:
            self.falhas -= 1
            raise AmFora("duble: o relay piscou")
        return super().chamar(acao, parametros, prazo)


def test_queda_depois_de_lancado_nao_roda_aqui_de_novo(am, cfg, tmp_path):
    """19/10/2026: o SSH piscou com o duelo ja rodando no am, e o duelo foi
    feito AQUI tambem (dentro da janela das postagens)."""
    piscando = Piscando(am.base, falhas=3)
    destino = tmp_path / "aqui" / "produto"
    resultado = maquina.executar(_ajustar_cwd(_trabalho_que_escreve(destino, conteudo="V")),
                                 lambda: pytest.fail("rodou aqui com o trabalho vivo no am"), cfg=cfg,
                                 transporte=piscando, avisar=lambda t: None, **_rapido())
    assert resultado.onde == "am" and (destino / "video.mp4").read_text() == "V"
    assert piscando.falhas == 0


def test_piscar_antes_de_lancar_nao_tira_o_trabalho_do_am(am, cfg, tmp_path, avisos):
    piscando = Piscando(am.base, falhas=2)
    piscando.acao_que_pisca = "saude"
    destino = tmp_path / "aqui" / "produto"
    resultado = maquina.executar(_ajustar_cwd(_trabalho_que_escreve(destino)), lambda: pytest.fail("aqui"),
                                 cfg=cfg, transporte=piscando, avisar=avisos.append, **_rapido())
    assert resultado.onde == "am" and avisos == []
    assert set(resultado.etapas) >= {"saude", "codigo", "entradas", "rodando", "trazendo"}


def test_medir_no_am_nunca_roda_aqui(am, cfg, tmp_path):
    am.fora = True
    with pytest.raises(AmFora):
        maquina.executar(_trabalho_que_escreve(tmp_path / "x"), lambda: pytest.fail("rodou aqui"),
                         cfg=cfg, transporte=am, forcar=True, cair_para_aqui=False,
                         avisar=lambda t: None, **_rapido())


# ------------------------------------------------- varios ao mesmo tempo
def _dorminhoco(destino: Path, segundos: float) -> Trabalho:
    nome = destino.name
    codigo = (f"import pathlib,time; p=pathlib.Path('saida-{nome}'); p.mkdir(exist_ok=True); "
              f"time.sleep({segundos}); (p/'feito.txt').write_text('{nome}')")
    return Trabalho(tipo="testes", comando=["{PY}", "-c", codigo], cwd="trabalho",
                    saida=f"trabalho/saida-{nome}", destino=destino, prazo_s=60)


def test_dois_trabalhos_rodam_ao_mesmo_tempo_no_am(am, cfg, tmp_path):
    import threading
    import time as relogio_real
    resultados = {}

    def um(nome):
        resultados[nome] = maquina.executar(_dorminhoco(tmp_path / nome, 2), lambda: pytest.fail("aqui"),
                                            cfg=cfg, transporte=am, avisar=lambda t: None,
                                            cair_para_aqui=False, dorme=lambda s: relogio_real.sleep(0.05))
    inicio = relogio_real.monotonic()
    fios = [threading.Thread(target=um, args=(n,)) for n in ("a", "b")]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join(60)
    assert {n: r.onde for n, r in resultados.items()} == {"a": "am", "b": "am"}
    assert (tmp_path / "a" / "feito.txt").read_text() == "a" and (tmp_path / "b" / "feito.txt").read_text() == "b"
    # nao um depois do outro: o tempo de parede e bem menor que a soma dos dois
    # (26/10/2026: o limite absoluto de 10 s falhava com este PC carregado)
    soma = sum(r.segundos for r in resultados.values())
    assert relogio_real.monotonic() - inicio < 0.8 * soma


def test_sem_vaga_daqui_espera_a_vez_e_entao_roda(am, cfg, tmp_path):
    import threading
    from builds import travas
    cfg["paralelo"]["maximo"] = 1
    segurando, soltar = threading.Event(), threading.Event()

    def outro_processo():
        with travas.trava("pc_am_vaga_0"):
            segurando.set()
            soltar.wait(10)
    fio = threading.Thread(target=outro_processo)
    fio.start()
    segurando.wait(5)
    threading.Timer(0.5, soltar.set).start()
    resultado = maquina.executar(_ajustar_cwd(_trabalho_que_escreve(tmp_path / "p")), lambda: pytest.fail("aqui"),
                                 cfg=cfg, transporte=am, avisar=lambda t: None, cair_para_aqui=False,
                                 espera=600, **_rapido())
    fio.join(10)
    assert resultado.onde == "am"


def test_clone_em_uso_nao_muda_de_estado_no_meio_do_trabalho(am, tmp_path):
    origem = tmp_path / "origem.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origem)], check=True)
    aqui = tmp_path / "aqui"
    subprocess.run(["git", "clone", "-q", str(origem), str(aqui)], check=True, capture_output=True)
    for chave, valor in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _git(aqui, "config", chave, valor)
    (aqui / "a.py").write_text("v = 1\n")
    _git(aqui, "add", "a.py")
    _git(aqui, "commit", "-qm", "um")
    _git(aqui, "push", "-q", "origin", "HEAD:main")
    repo = {"nome": "projetos", "raiz": aqui, "url": str(origem), "mudancas": True, "instalar": False}
    assert maquina.sincronizar(am, repo)["ok"]
    # o mesmo estado com um trabalho rodando: nao toca no clone (e responde ja)
    marca = am.base / "ativos"
    marca.mkdir()
    (marca / "x.json").write_text(json.dumps({"id": "x", "pid": os.getpid(), "repo": "projetos"}))
    assert maquina.sincronizar(am, repo).get("ja_estava") is True
    # outro estado com o trabalho rodando: espera a vez (nao reseta por baixo dele)
    (aqui / "a.py").write_text("v = 2\n")
    with pytest.raises(maquina.AmOcupado):
        maquina.sincronizar(am, repo)
    assert (am.base / "projetos" / "a.py").read_text().strip() == "v = 1"
    (marca / "x.json").unlink()
    assert maquina.sincronizar(am, repo)["ok"]
    assert (am.base / "projetos" / "a.py").read_text().strip() == "v = 2"


def test_o_medidor_do_am_mede_memoria_e_cpu(am, cfg, tmp_path):
    if os.name != "nt":
        pytest.skip("o medidor usa a API do Windows")
    codigo = ("import time; x = bytearray(150 * 1024 * 1024); fim = time.time() + 4\n"
              "while time.time() < fim: pass")
    trabalho = Trabalho(tipo="testes", perfil="medido", comando=["{PY}", "-c", codigo], cwd="trabalho", prazo_s=60)
    resultado = maquina.executar(trabalho, lambda: None, cfg=cfg, transporte=am, avisar=lambda t: None,
                                 cair_para_aqui=False, dorme=lambda s: __import__("time").sleep(0.05))
    assert resultado.etapas["pico_memoria_mb"] >= 140
    # o medidor mede (> 0); o quanto depende da carga DESTE PC (prioridade abaixo
    # do normal: com o PC carregado deu 0,02 em 26/10/2026), entao nao se exige 0,5
    assert resultado.etapas["cpu_nucleos"] > 0
    assert maquina.perfis()["medido"]["memoria_mb"] >= 140         # aprendeu