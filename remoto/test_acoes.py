# -*- coding: utf-8 -*-
"""Fase 2 do app: acoes, guardas de publicacao e confirmacao em dois passos.

Nenhum teste encosta no `controle.json` real, no ledger real, no Telegram ou
num subprocesso de verdade: tudo que executa e duble, e o que se confere e o
que TERIA sido chamado. Os ids seguem o formato real do catalogo
(`generation_00041:build:celular`, com `:B` na variante).
"""
from __future__ import annotations

import http.client
import json
import subprocess
import sys
import threading
import time
import types
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from remoto import acoes, api_http, painel_dados

A = "generation_00041:build:celular"
B = "generation_00041:build:celular:B"
DOIS = "generation_00042:build:celular"
PENDENTE = "generation_00043:build:celular"
PC = "generation_00044:build:normal"
CINCO = "generation_00045:estreia:celular"


# ------------------------------------------------------------------ dubles
class _Controle:
    TUDO = "tudo"

    def __init__(self):
        self.chamadas = []

    def pausar(self, alvo, motivo, minutos):
        self.chamadas.append(("pausar", alvo, motivo, minutos))
        return {"resumo": f"pausado: {alvo}"}

    def retomar(self, alvo=None):
        self.chamadas.append(("retomar", alvo))
        return {"resumo": "rodando normalmente"}

    def pedir_parada(self, motivo):
        self.chamadas.append(("parar", motivo))
        return {"resumo": "parando"}

    def estado(self):
        return {"situacao": "rodando", "pausas": {}, "resumo": "rodando"}


class _Comandos:
    PY = "python"
    RANDOM_BUILDS = "rb"

    def __init__(self):
        self.gerados = 0

    def gerar(self):
        self.gerados += 1
        return "comecei: uma build nova"


class _Processo:
    """Um `main.py publicar` de mentira: devolve a saida roteirizada."""

    def __init__(self, saida, codigo=0, segurar=None):
        self.saida, self.returncode, self.segurar = saida, codigo, segurar

    def communicate(self, timeout=None):
        if self.segurar is not None:
            self.segurar.wait(10)
        if self.saida is None:
            raise subprocess.TimeoutExpired("main.py", timeout)
        return self.saida, None


def _video(id_, titulo, pendencias=(), perfil="celular"):
    return types.SimpleNamespace(
        id=id_, titulo=titulo, fonte_id=id_.split(":")[0],
        variante="B" if id_.endswith(":B") else "A",
        perfil=perfil, pendencias=list(pendencias),
        caminho="x.mp4", bytes=1, quando=1.0, origem="build")


class _Metricas:
    def __init__(self, pasta):
        self.linhas = []
        self.pasta = pasta

    def publicados(self, canal="builds"):
        return list(self.linhas)

    @staticmethod
    def publicado(linha):
        if "publicado" in linha:
            return bool(linha["publicado"])
        return bool(linha.get("url"))

    def registro_do_canal(self, canal):
        return self.pasta / "publicados.jsonl"


class _Titulos:
    @staticmethod
    def chave(texto):
        return str(texto or "").strip().lower()

    @classmethod
    def ja_publicados(cls, linhas):
        return {cls.chave(l.get("titulo")) for l in linhas if l.get("titulo")}

    @classmethod
    def repetido(cls, titulo, ja):
        k = cls.chave(titulo)
        return bool(k) and k in ja


class _Grade:
    def __init__(self):
        self.lista = ["06:37", "12:07"]

    def horarios(self):
        return list(self.lista)


class _Postar:
    """O que o app usa do postar.py: o desfecho e a marca (que grava de verdade,
    no arquivo que a guarda le)."""

    def __init__(self, pasta):
        self.pasta = pasta
        self.quebrar = False

    @staticmethod
    def desfecho_do_tiktok(estado, falha=None, laudo=None):
        texto = str(estado or "").lower()
        if "publicado no tiktok" in texto:
            return "publicado"
        if "cliquei em publicar" in texto:
            return "sem_confirmacao"
        if "chrome" in json.dumps(falha or {}).lower():
            return "infraestrutura"
        return "falha"

    def _marcar_para_conferir(self, canal, video_id, estado):
        if self.quebrar:
            raise OSError("disco cheio")
        caminho = self.pasta / "_tiktok_a_conferir.json"
        dados = json.loads(caminho.read_text(encoding="utf-8")) if caminho.is_file() else {}
        dados[video_id] = {"estado": estado}
        caminho.write_text(json.dumps(dados), encoding="utf-8")


FORA_DA_GRADE = datetime(2026, 9, 17, 10, 0)


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    monkeypatch.setattr(api_http, "ARQUIVO", tmp_path / "app_celular.json")
    monkeypatch.setattr(acoes, "ARQUIVO_RASTRO", tmp_path / "acoes.jsonl")
    monkeypatch.setattr(acoes, "ARQUIVO_EM_VOO", tmp_path / "em_voo.json")
    acoes._RASTRO_FALHOU.clear()
    controle, comandos = _Controle(), _Comandos()
    metricas, grade, postar = _Metricas(tmp_path), _Grade(), _Postar(tmp_path)
    videos = [
        _video(A, "Build Um"),
        _video(B, "Build Um"),
        _video(DOIS, "Build Dois"),
        _video(PENDENTE, "Build Tres", pendencias=["sem payoff"]),
        _video(PC, "Build Quatro", perfil="normal"),
        _video(CINCO, "Build Cinco"),
    ]
    catalogo = types.SimpleNamespace(listar=lambda: list(videos),
                                     carregar_config=lambda: {})
    processos = []

    def abrir(comando, cwd):
        roteiro = mundo_ns.roteiro
        processos.append(list(comando))
        return roteiro()

    monkeypatch.setattr(acoes, "_controle", lambda: controle)
    monkeypatch.setattr(acoes, "_comandos", lambda: comandos)
    monkeypatch.setattr(acoes, "_metricas", lambda: metricas)
    monkeypatch.setattr(acoes, "_titulos", lambda: _Titulos)
    monkeypatch.setattr(acoes, "_grade", lambda: grade)
    monkeypatch.setattr(acoes, "_catalogo", lambda: catalogo)
    monkeypatch.setattr(acoes, "_postar", lambda: postar)
    monkeypatch.setattr(acoes, "_abrir_processo", abrir)
    monkeypatch.setattr(acoes, "_agora", lambda: FORA_DA_GRADE)
    monkeypatch.setattr(acoes, "alvos_de_pausa", lambda: ["tudo", "digen", "picasso"])
    monkeypatch.setattr(acoes, "trava_ocupada", lambda nome: False)
    monkeypatch.setattr(acoes, "perfil_ocupado", lambda destino: False)
    monkeypatch.setattr(acoes, "processos", lambda: [])
    avisos = []
    monkeypatch.setattr(acoes, "_entregar", avisos.append)
    monkeypatch.setattr(painel_dados._Previsao, "disponivel", staticmethod(lambda: False))
    mundo_ns = types.SimpleNamespace(
        tmp=tmp_path, controle=controle, comandos=comandos, metricas=metricas,
        grade=grade, postar=postar, avisos=avisos, catalogo=catalogo,
        processos=processos,
        roteiro=lambda: _Processo("YouTube: https://youtu.be/abc\n", 0))
    yield mundo_ns
    _esperar_publicacoes()
    acoes._FILA_AVISOS.join()


def _esperar_publicacoes():
    for fio in threading.enumerate():
        if fio.name.startswith("publicar-"):
            fio.join(10)


def _publicar(args, aparelho="ap"):
    """Os dois passos direto no modulo (o servidor tem os seus testes)."""
    pedido = acoes.preparar("publicar", args, aparelho)
    with acoes.trava_de_acoes():
        pedido = acoes.preparar("publicar", pedido["args"], aparelho)
        texto = acoes.executar("publicar", pedido["args"], aparelho)
        acoes.registrar(aparelho, "publicar", pedido["args"], texto)
    return texto


# ================================================= 1. publico no YouTube
def test_youtube_sobe_publico_e_o_texto_diz(mundo):
    pedido = acoes.preparar("publicar", {"id": A, "onde": "ambos"}, "ap")
    assert "PÚBLICO" in pedido["texto"] and "YouTube e no TikTok" in pedido["texto"]
    assert acoes.comando_de_publicar(pedido["args"]) == [
        "python", "-X", "utf8", "main.py", "publicar", A,
        "--youtube", "--visibilidade", "public", "--tiktok", "--postar"]
    so_tiktok = acoes.preparar("publicar", {"id": A, "onde": "tiktok"}, "ap")
    assert "PÚBLICO" not in so_tiktok["texto"]
    assert "--visibilidade" not in acoes.comando_de_publicar(so_tiktok["args"])


def test_o_processo_disparado_leva_o_publico(mundo):
    _publicar({"id": DOIS, "onde": "youtube"})
    _esperar_publicacoes()
    (comando,) = mundo.processos
    assert comando[comando.index("--visibilidade") + 1] == "public"


def test_confirmacao_diz_qual_gancho(mundo):
    assert "gancho" not in acoes.preparar("publicar", {"id": A, "onde": "youtube"}, "ap")["texto"]
    texto = acoes.preparar("publicar", {"id": B, "onde": "youtube"}, "ap")["texto"]
    assert "«Build Um» (gancho B) no YouTube" in texto


# =========================================== 2. desfecho do TikTok e marca
@pytest.mark.parametrize("saida,codigo,onde,esperado", [
    ("TikTok: publicado no TikTok\n", 0, "tiktok", {"tiktok": "publicado"}),
    ("TikTok: cliquei em publicar; sem confirmação\n", 0, "tiktok",
     {"tiktok": "sem_confirmacao"}),
    ("TikTok FALHOU: nao consegui abrir o chrome\n", 1, "tiktok",
     {"tiktok": "infraestrutura"}),
    ("TikTok FALHOU: legenda\n", 1, "tiktok", {"tiktok": "falha"}),
    # sucesso na frase, mas o processo nao saiu limpo: vai para a conferencia
    ("TikTok: publicado no TikTok\n", 1, "tiktok", {"tiktok": "sem_confirmacao"}),
    (None, None, "tiktok", {"tiktok": "sem_confirmacao"}),            # tempo
    ("Traceback...\n", 1, "tiktok", {"tiktok": "sem_confirmacao"}),   # quebrou
    ("YouTube FALHOU: x\n", 1, "ambos", {"youtube": "falha", "tiktok": "nao_tentado"}),
    ("YouTube: cota esgotada\n", 2, "ambos",
     {"youtube": "falha", "tiktok": "nao_tentado"}),
    ("YouTube: https://youtu.be/a\nTikTok: publicado no TikTok\n", 0, "ambos",
     {"youtube": "publicado", "tiktok": "publicado"}),
    ("YouTube: https://youtu.be/a\n", 0, "youtube", {"youtube": "publicado"}),
])
def test_desfechos(mundo, saida, codigo, onde, esperado):
    assert acoes.desfechos(saida, codigo, onde) == esperado


def test_clique_sem_confirmacao_marca_a_conferir_e_segura_para_sempre(mundo, monkeypatch):
    mundo.roteiro = lambda: _Processo("TikTok: cliquei em publicar; sem confirmação\n", 0)
    _publicar({"id": A, "onde": "tiktok"})
    _esperar_publicacoes()
    conferir = json.loads((mundo.tmp / "_tiktok_a_conferir.json").read_text(encoding="utf-8"))
    assert A in conferir and "pelo app" in conferir[A]["estado"]
    assert acoes.em_voo() == {}                     # a marca assumiu o bloqueio
    # muito depois, e sem nada no ledger: continua barrado
    monkeypatch.setattr(acoes, "_agora", lambda: FORA_DA_GRADE + timedelta(days=3))
    with pytest.raises(acoes.Recusa, match="a conferir"):
        acoes.preparar("publicar", {"id": A, "onde": "tiktok"}, "ap")
    acoes.preparar("publicar", {"id": A, "onde": "youtube"}, "ap")
    acoes._FILA_AVISOS.join()
    assert any("sem\\_confirmacao" in a for a in mundo.avisos)   # markdown escapado


def test_sucesso_limpo_nao_marca_e_solta(mundo):
    mundo.roteiro = lambda: _Processo("TikTok: publicado no TikTok\n", 0)
    _publicar({"id": A, "onde": "tiktok"})
    _esperar_publicacoes()
    assert not (mundo.tmp / "_tiktok_a_conferir.json").exists()
    assert acoes.em_voo() == {}


def test_youtube_que_falhou_antes_nao_marca_o_tiktok(mundo):
    mundo.roteiro = lambda: _Processo("YouTube FALHOU: sessao\n", 1)
    _publicar({"id": A, "onde": "ambos"})
    _esperar_publicacoes()
    assert not (mundo.tmp / "_tiktok_a_conferir.json").exists()


def test_sem_desfecho_o_video_fica_em_voo(mundo, monkeypatch):
    solta = threading.Event()
    mundo.roteiro = lambda: _Processo("TikTok: publicado no TikTok\n", 0, segurar=solta)
    _publicar({"id": A, "onde": "tiktok"})
    # passou muito tempo e o processo nao voltou: o bloqueio nao vence
    monkeypatch.setattr(acoes, "_agora", lambda: FORA_DA_GRADE + timedelta(hours=5))
    with pytest.raises(acoes.Recusa, match="ainda não voltou"):
        acoes.preparar("publicar", {"id": A, "onde": "ambos"}, "outro")
    with pytest.raises(acoes.Recusa, match="outra variante de generation_00041"):
        acoes.preparar("publicar", {"id": B, "onde": "tiktok"}, "outro")
    acoes.preparar("publicar", {"id": B, "onde": "youtube"}, "outro")
    solta.set()
    _esperar_publicacoes()
    assert acoes.em_voo() == {}


def test_marca_que_falha_mantem_o_bloqueio_e_liberar_solta(mundo):
    mundo.postar.quebrar = True
    mundo.roteiro = lambda: _Processo("TikTok: cliquei em publicar\n", 0)
    _publicar({"id": A, "onde": "tiktok"})
    _esperar_publicacoes()
    assert [v["id"] for v in acoes.em_voo().values()] == [A]
    with pytest.raises(acoes.Recusa, match="ainda não voltou"):
        acoes.preparar("publicar", {"id": A, "onde": "tiktok"}, "ap")
    assert api_http.main(["--liberar", A]) == 0
    assert acoes.em_voo() == {}


def test_em_voo_sobrevive_ao_servidor(mundo):
    # o arquivo e a memoria: outro processo (o servidor reiniciado) ve o mesmo
    acoes._por_em_voo("x", {"id": DOIS, "onde": "youtube", "fonte": "generation_00042"})
    assert json.loads((mundo.tmp / "em_voo.json").read_text(encoding="utf-8"))["x"]["id"] == DOIS
    with pytest.raises(acoes.Recusa):
        acoes.preparar("publicar", {"id": DOIS, "onde": "youtube"}, "ap")


def test_em_voo_ilegivel_recusa(mundo):
    (mundo.tmp / "em_voo.json").write_text("{quebrado", encoding="utf-8")
    with pytest.raises(acoes.Recusa, match="ilegível"):
        acoes.preparar("publicar", {"id": DOIS, "onde": "youtube"}, "ap")


def test_postar_de_verdade_tem_as_funcoes_e_o_desfecho():
    """Sem duble: o app usa as funcoes do postar.py, nao uma copia."""
    postar = acoes._postar()
    assert callable(postar._marcar_para_conferir)
    assert postar.desfecho_do_tiktok("cliquei em publicar; sem confirmação") == \
        "sem_confirmacao"


# ================================================== 3. uma acao por vez
def test_duas_confirmacoes_simultaneas_nao_passam_juntas(mundo, monkeypatch):
    solta = threading.Event()
    mundo.roteiro = lambda: _Processo("TikTok: publicado no TikTok\n", 0, segurar=solta)
    lento = threading.Event()

    def processos_lentos():
        lento.wait(0.3)          # sem a trava, os dois passariam pela guarda
        return []
    monkeypatch.setattr(acoes, "processos", processos_lentos)
    resultados = []

    def tentar(video_id):
        try:
            _publicar({"id": video_id, "onde": "tiktok"})
            resultados.append("ok")
        except acoes.Recusa:
            resultados.append("recusa")
    fios = [threading.Thread(target=tentar, args=(v,)) for v in (A, B)]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join(20)
    assert sorted(resultados) == ["ok", "recusa"]
    assert len(mundo.processos) == 1
    solta.set()


def test_trava_de_acoes_vale_entre_processos(mundo):
    alvo = acoes.caminho_rastro().with_name("app_celular_acoes.lock")
    segurar = (
        "import time\n"
        "from pathlib import Path\n"
        "from remoto import api_http\n"
        f"with api_http.trava_arquivo(Path({str(alvo)!r})):\n"
        "    print('peguei', flush=True)\n"
        "    time.sleep(1.5)\n"
    )
    outro = subprocess.Popen([sys.executable, "-c", segurar], stdout=subprocess.PIPE,
                             text=True, cwd=str(Path(acoes.__file__).parents[1]))
    try:
        assert outro.stdout.readline().strip() == "peguei"
        inicio = time.monotonic()
        acoes.registrar("ap", "pausar", {}, "ok")
        assert time.monotonic() - inicio > 1.0
    finally:
        outro.wait(timeout=20)


def test_trava_e_reentrante_na_mesma_thread(mundo):
    inicio = time.monotonic()
    with acoes.trava_de_acoes():
        acoes.registrar("ap", "pausar", {}, "ok")     # pede a mesma trava
    assert time.monotonic() - inicio < 3


# ============================================================ 4. rastro
def test_rastro_ilegivel_recusa(mundo, monkeypatch):
    pasta = mundo.tmp / "rastro_pasta"
    pasta.mkdir()
    monkeypatch.setattr(acoes, "ARQUIVO_RASTRO", pasta)       # abrir levanta
    for acao, args in (("gerar", {}), ("publicar", {"id": DOIS, "onde": "youtube"}),
                       ("pausar", {"alvo": "tudo"})):
        with pytest.raises(acoes.Recusa, match="rastro"):
            acoes.preparar(acao, args, "ap")


def test_rastro_que_falha_bloqueia_ate_voltar(mundo, monkeypatch):
    quebrado = {"sim": True}
    real = acoes.trava_de_acoes

    def trava():
        if quebrado["sim"]:
            raise OSError("trava presa")
        return real()
    monkeypatch.setattr(acoes, "trava_de_acoes", trava)
    with pytest.raises(OSError):
        acoes.registrar("ap", "gerar", {}, "comecei")
    assert acoes._RASTRO_FALHOU.is_set()
    # o arquivo abre, mas a gravacao de verdade ainda falha: continua fechado
    with pytest.raises(acoes.Recusa, match="não está gravando"):
        acoes.preparar("gerar", {}, "ap")
    quebrado["sim"] = False
    acoes.preparar("gerar", {}, "ap")
    assert not acoes._RASTRO_FALHOU.is_set()


def test_limite_conta_por_tempo_e_le_o_arquivo_rodado(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "LIMITE_POR_HORA", 2)
    # UMA rotacao no meio (com 512 KB reais e os tetos por hora, uma hora de
    # rastro nunca atravessa duas).
    monkeypatch.setattr(acoes, "ROTACAO_BYTES", 1500)
    velho = FORA_DA_GRADE - timedelta(hours=2)
    monkeypatch.setattr(acoes, "_agora", lambda: velho)
    for _ in range(5):
        acoes.registrar("ap", "gerar", {}, "ok")              # fora da janela
    monkeypatch.setattr(acoes, "_agora", lambda: FORA_DA_GRADE)
    acoes.registrar("ap", "gerar", {}, "ok")
    for _ in range(12):                                       # enche e roda
        acoes.registrar("outro", "pausar", {}, "x" * 50)
    acoes.registrar("ap", "publicar", {}, "ok")
    assert (mundo.tmp / "acoes.jsonl.1").exists()
    assert acoes.usadas_na_ultima_hora("ap") == 2
    with pytest.raises(acoes.Recusa, match="limite"):
        acoes.preparar("gerar", {}, "ap")


def test_limite_ignora_falha_e_outro_aparelho(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "LIMITE_POR_HORA", 1)
    acoes.registrar("outro", "gerar", {}, "ok")
    acoes.registrar("ap", "gerar", {}, "falhou", ok=False)
    acoes.preparar("gerar", {}, "ap")


# ============================================= 5. grade, postar e perfis
@pytest.mark.parametrize("onde,minuto_antes,barra", [
    ("youtube", 25, True), ("youtube", 26, False),
    ("tiktok", 20, True), ("tiktok", 21, False),
    ("ambos", 40, True), ("ambos", 41, False),
])
def test_folga_por_destino(mundo, onde, minuto_antes, barra):
    agora = datetime(2026, 9, 17, 6, 37) - timedelta(minutes=minuto_antes)
    assert (acoes.postagem_em_curso(agora, onde) is not None) is barra


@pytest.mark.parametrize("agora,barra", [
    (datetime(2026, 9, 17, 6, 55), True), (datetime(2026, 9, 17, 6, 56), False),
    (datetime(2026, 9, 17, 12, 25), True), (datetime(2026, 9, 17, 12, 26), False),
])
def test_folga_depois(mundo, agora, barra):
    assert (acoes.postagem_em_curso(agora, "youtube") is not None) is barra


def test_janela_que_cruza_a_meia_noite(mundo):
    mundo.grade.lista = ["00:05"]
    assert acoes.postagem_em_curso(datetime(2026, 9, 17, 23, 45), "youtube") == "00:05"
    assert acoes.postagem_em_curso(datetime(2026, 9, 17, 0, 20), "youtube") == "00:05"


def test_publicar_na_janela_e_recusado(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "_agora", lambda: datetime(2026, 9, 17, 6, 40))
    with pytest.raises(acoes.Recusa, match="06:37"):
        acoes.preparar("publicar", {"id": DOIS, "onde": "youtube"}, "ap")


@pytest.mark.parametrize("vivos,trecho", [
    (["C:\\Python314\\python.exe -X utf8 ferramentas\\postar.py --so builds"],
     "grade está rodando"),
    (None, "não consegui conferir se a postagem"),
])
def test_postar_vivo_ou_desconhecido_recusa(mundo, monkeypatch, vivos, trecho):
    monkeypatch.setattr(acoes, "processos", lambda: vivos)
    with pytest.raises(acoes.Recusa, match=trecho):
        acoes.preparar("publicar", {"id": DOIS, "onde": "youtube"}, "ap")


@pytest.mark.parametrize("estado,trecho", [
    (True, "Chrome do TikTok está em uso"),
    (None, "não consegui conferir o Chrome do TikTok"),
])
def test_perfil_ocupado_ou_desconhecido_recusa(mundo, monkeypatch, estado, trecho):
    monkeypatch.setattr(acoes, "perfil_ocupado",
                        lambda destino: estado if destino == "tiktok" else False)
    with pytest.raises(acoes.Recusa, match=trecho):
        acoes.preparar("publicar", {"id": DOIS, "onde": "ambos"}, "ap")
    acoes.preparar("publicar", {"id": DOIS, "onde": "youtube"}, "ap")


# ============================================== guardas de ledger/catalogo
@pytest.mark.parametrize("args,trecho", [
    ({"id": "generation_00041:build", "onde": "youtube"}, "não está no catálogo"),
    ({"id": PENDENTE, "onde": "youtube"}, "pendência"),
    ({"id": PC, "onde": "youtube"}, "celular"),
    ({"id": DOIS, "onde": "kwai"}, "destino inválido"),
    ({"id": "", "onde": "youtube"}, "não está no catálogo"),
])
def test_publicar_recusa_o_basico(mundo, args, trecho):
    with pytest.raises(acoes.Recusa, match=trecho):
        acoes.preparar("publicar", args, "ap")


def test_ja_saiu_naquele_destino(mundo):
    mundo.metricas.linhas = [{"video_id": DOIS, "fonte_id": "generation_00042",
                              "plataforma": "youtube", "url": "https://youtu.be/x",
                              "titulo": "Build Dois"}]
    for onde in ("youtube", "ambos"):
        with pytest.raises(acoes.Recusa, match="já saiu no YouTube"):
            acoes.preparar("publicar", {"id": DOIS, "onde": onde}, "ap")
    acoes.preparar("publicar", {"id": DOIS, "onde": "tiktok"}, "ap")


def test_linha_sem_plataforma_e_do_youtube_e_rascunho_nao_conta(mundo):
    mundo.metricas.linhas = [
        {"video_id": DOIS, "url": "https://youtu.be/x"},
        {"video_id": CINCO, "plataforma": "youtube",
         "url": "publicado no YouTube", "publicado": False},
    ]
    with pytest.raises(acoes.Recusa, match="já saiu no YouTube"):
        acoes.preparar("publicar", {"id": DOIS, "onde": "youtube"}, "ap")
    acoes.preparar("publicar", {"id": CINCO, "onde": "youtube"}, "ap")


def test_outra_variante_da_mesma_geracao(mundo):
    mundo.metricas.linhas = [{"video_id": B, "fonte_id": "generation_00041",
                              "plataforma": "tiktok", "publicado": True,
                              "titulo": "outro"}]
    with pytest.raises(acoes.Recusa,
                       match="outra variante de generation_00041 já saiu no TikTok"):
        acoes.preparar("publicar", {"id": A, "onde": "tiktok"}, "ap")
    acoes.preparar("publicar", {"id": A, "onde": "youtube"}, "ap")


def test_titulo_ja_no_ar_por_outro_video(mundo):
    mundo.metricas.linhas = [{"video_id": "generation_00009:build:celular",
                              "fonte_id": "generation_00009", "plataforma": "youtube",
                              "publicado": True, "titulo": "  build dois "}]
    with pytest.raises(acoes.Recusa, match="título"):
        acoes.preparar("publicar", {"id": DOIS, "onde": "youtube"}, "ap")
    mundo.catalogo.carregar_config = lambda: {"grade": {"repetir_titulo": True}}
    acoes.preparar("publicar", {"id": DOIS, "onde": "youtube"}, "ap")


def test_a_conferir_no_tiktok(mundo):
    (mundo.tmp / "_tiktok_a_conferir.json").write_text(json.dumps([CINCO]),
                                                        encoding="utf-8")
    for onde in ("tiktok", "ambos"):
        with pytest.raises(acoes.Recusa, match="a conferir"):
            acoes.preparar("publicar", {"id": CINCO, "onde": onde}, "ap")
    acoes.preparar("publicar", {"id": CINCO, "onde": "youtube"}, "ap")


def test_a_conferir_ilegivel_recusa(mundo):
    (mundo.tmp / "_tiktok_a_conferir.json").write_text("{", encoding="utf-8")
    with pytest.raises(acoes.Recusa, match="a conferir"):
        acoes.preparar("publicar", {"id": CINCO, "onde": "youtube"}, "ap")


def test_ledger_ilegivel_barra(mundo):
    def quebra(canal="builds"):
        raise OSError("disco")
    mundo.metricas.publicados = quebra
    with pytest.raises(acoes.Recusa, match="registro de publicações"):
        acoes.preparar("publicar", {"id": DOIS, "onde": "youtube"}, "ap")


# ============================================================ 6. parar
def test_parar_diz_a_verdade(mundo):
    texto = acoes.preparar("parar", {}, "ap")["texto"]
    assert "termina o job atual" in texto
    assert "a parada se apaga sozinha" in texto
    assert "postagem da grade continuam" in texto
    assert "só volta quando for iniciado de novo" in texto
    assert "até você tocar em Retomar" not in texto


# ============================================================ 7. gerar
def test_gerar_recusa_quando_ja_esta_gerando(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "trava_ocupada", lambda nome: nome == "historias__auto")
    with pytest.raises(acoes.Recusa, match="histórias"):
        acoes.preparar("gerar", {}, "ap")
    monkeypatch.setattr(acoes, "trava_ocupada", lambda nome: False)
    monkeypatch.setattr(acoes, "processos", lambda: [
        "C:\\Python314\\python.exe -u -X utf8 main.py generate-video --rerender generation_00041"])
    with pytest.raises(acoes.Recusa, match="build sendo feita"):
        acoes.preparar("gerar", {}, "ap")


def test_gerar_avisa_o_que_nao_conseguiu_conferir(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "trava_ocupada", lambda nome: None)
    monkeypatch.setattr(acoes, "processos", lambda: None)
    texto = acoes.preparar("gerar", {}, "ap")["texto"]
    assert "não consegui conferir a rodada das histórias nem se já há uma build" in texto


# ============================================================ pausa
@pytest.mark.parametrize("args,trecho", [
    ({"alvo": "rm -rf"}, "alvo desconhecido"),
    ({"alvo": "tudo", "minutos": 5}, "15 a 1440"),
    ({"alvo": "tudo", "minutos": 99999}, "15 a 1440"),
    ({"alvo": "tudo", "minutos": "x"}, "minutos inválidos"),
])
def test_pausar_valida(mundo, args, trecho):
    with pytest.raises(acoes.Recusa, match=trecho):
        acoes.preparar("pausar", args, "ap")


def test_acao_desconhecida_e_args_nao_dict(mundo):
    with pytest.raises(acoes.Recusa):
        acoes.preparar("shell", {}, "ap")
    with pytest.raises(acoes.Recusa):
        acoes.preparar("pausar", ["tudo"], "ap")


# ============================================================ 9. limites
def test_pausar_e_retomar_tem_teto(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "LIMITE_LEVES_POR_HORA", 2)
    acoes.registrar("ap", "pausar", {}, "ok")
    acoes.registrar("ap", "retomar", {}, "ok")
    with pytest.raises(acoes.Recusa, match="pausas/retomadas"):
        acoes.preparar("retomar", {}, "ap")
    acoes.preparar("gerar", {}, "ap")                     # conta separada


def test_avisos_saem_por_uma_thread_so_e_em_ordem(mundo):
    for i in range(20):
        acoes.avisar_telegram("ap", "pausar", f"n{i}")
    acoes._FILA_AVISOS.join()
    carteiros = [f for f in threading.enumerate() if f.name == "avisos-app"]
    assert len(carteiros) == 1
    assert [a.rsplit(" ", 1)[-1] for a in mundo.avisos[-20:]] == [f"n{i}" for i in range(20)]


def test_escapa_markdown_do_telegram():
    assert acoes._escapar_markdown("g_1 *x* `y` [z]") == "g\\_1 \\*x\\* \\`y\\` \\[z]"


# ============================================================ servidor
@pytest.fixture
def servidor(mundo):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True, com_acoes=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _pedir(srv, metodo, caminho, corpo=None, token=None, tipo="application/json"):
    porta = srv.server_address[1]
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=20)
    cab = {"Host": f"127.0.0.1:{porta}"}
    if token:
        cab["Authorization"] = f"Bearer {token}"
    if corpo is not None:
        corpo = json.dumps(corpo).encode()
        cab["Content-Type"] = tipo
    conexao.request(metodo, caminho, body=corpo, headers=cab)
    resp = conexao.getresponse()
    dados = resp.read()
    conexao.close()
    return resp.status, (json.loads(dados) if dados else None)


def _token():
    return api_http.trocar_codigo(api_http.novo_codigo(), "moto")


def test_desligadas_por_padrao(mundo):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        token = _token()
        assert _pedir(srv, "GET", "/api/acoes", token=token) == (200, {"ligadas": False})
        status, _ = _pedir(srv, "POST", "/api/acao",
                           {"acao": "pausar", "args": {"alvo": "tudo"}}, token)
        assert status == 403
        assert mundo.controle.chamadas == []
    finally:
        srv.shutdown()
        srv.server_close()


def test_sem_token_nao_age(servidor, mundo):
    assert _pedir(servidor, "POST", "/api/acao", {"acao": "parar"})[0] == 401
    assert _pedir(servidor, "POST", "/api/acao/confirmar", {"codigo": "x"})[0] == 401
    assert mundo.controle.chamadas == []


def test_content_type_obrigatorio(servidor, mundo):
    status, _ = _pedir(servidor, "POST", "/api/acao", {"acao": "retomar"}, _token(),
                       tipo="text/plain")
    assert status == 415


def test_pausar_e_um_passo_e_deixa_rastro(servidor, mundo):
    token = _token()
    status, dados = _pedir(servidor, "POST", "/api/acao",
                           {"acao": "pausar", "args": {"alvo": "digen", "minutos": 60}},
                           token)
    assert status == 200 and dados["feito"]
    assert mundo.controle.chamadas == [("pausar", "digen", "pelo app", 60)]
    (linha,) = [json.loads(l) for l in
                (mundo.tmp / "acoes.jsonl").read_text(encoding="utf-8").splitlines()]
    assert linha["acao"] == "pausar" and len(linha["aparelho"]) == 8
    assert token not in json.dumps(linha)
    acoes._FILA_AVISOS.join()
    assert any(linha["aparelho"] in a for a in mundo.avisos)
    status, dados = _pedir(servidor, "GET", "/api/acoes", token=token)
    assert dados["ligadas"] and "digen" in dados["alvos"] and dados["restantes"] == 6


def test_parar_so_executa_na_confirmacao_e_toque_duplo_nao_e_chute(servidor, mundo,
                                                                  monkeypatch):
    monkeypatch.setattr(api_http, "FALHAS_MAX", 1)
    token = _token()
    status, dados = _pedir(servidor, "POST", "/api/acao", {"acao": "parar"}, token)
    assert status == 200 and "confirmar" in dados
    assert mundo.controle.chamadas == []
    codigo = dados["confirmar"]
    assert _pedir(servidor, "POST", "/api/acao/confirmar", {"codigo": codigo}, token)[0] == 200
    for _ in range(3):                                   # toque duplo, triplo...
        assert _pedir(servidor, "POST", "/api/acao/confirmar",
                      {"codigo": codigo}, token)[0] == 410
    assert mundo.controle.chamadas == [("parar", "pelo app")]
    # nada disso contou como chute: um codigo inventado ainda e 404, nao 429
    assert _pedir(servidor, "POST", "/api/acao/confirmar",
                  {"codigo": "inventado"}, token)[0] == 404


def test_confirmacao_vencida_do_proprio_aparelho_e_410(servidor, mundo, monkeypatch):
    monkeypatch.setattr(api_http, "FALHAS_MAX", 1)
    token = _token()
    _, dados = _pedir(servidor, "POST", "/api/acao", {"acao": "gerar"}, token)
    agora = acoes.time.time()
    monkeypatch.setattr(acoes.time, "time", lambda: agora + acoes.CONFIRMAR_VALE_S + 1)
    for _ in range(2):
        assert _pedir(servidor, "POST", "/api/acao/confirmar",
                      {"codigo": dados["confirmar"]}, token)[0] == 410
    assert mundo.comandos.gerados == 0


def test_confirmacao_de_outro_aparelho_e_chute_e_nao_queima(servidor, mundo):
    dono, intruso = _token(), _token()
    _, dados = _pedir(servidor, "POST", "/api/acao", {"acao": "gerar"}, dono)
    codigo = dados["confirmar"]
    assert _pedir(servidor, "POST", "/api/acao/confirmar", {"codigo": codigo},
                  intruso)[0] == 404
    assert mundo.comandos.gerados == 0
    assert _pedir(servidor, "POST", "/api/acao/confirmar", {"codigo": codigo},
                  dono)[0] == 200
    assert mundo.comandos.gerados == 1


def test_guarda_reavaliada_na_confirmacao(servidor, mundo):
    token = _token()
    args = {"id": DOIS, "onde": "youtube"}
    _, dados = _pedir(servidor, "POST", "/api/acao", {"acao": "publicar", "args": args}, token)
    mundo.metricas.linhas = [{"video_id": DOIS, "plataforma": "youtube",
                              "publicado": True, "titulo": "Build Dois"}]
    status, dados = _pedir(servidor, "POST", "/api/acao/confirmar",
                           {"codigo": dados["confirmar"]}, token)
    assert status == 409 and "já saiu" in dados["erro"]
    assert mundo.processos == []


def test_args_ficam_congelados_no_primeiro_passo(servidor, mundo):
    token = _token()
    _, dados = _pedir(servidor, "POST", "/api/acao",
                      {"acao": "publicar", "args": {"id": DOIS, "onde": "youtube"}}, token)
    status, resposta = _pedir(servidor, "POST", "/api/acao/confirmar",
                              {"codigo": dados["confirmar"],
                               "args": {"id": CINCO, "onde": "ambos"}}, token)
    assert status == 200 and "público" in resposta["texto"]
    _esperar_publicacoes()
    (comando,) = mundo.processos
    assert DOIS in comando and CINCO not in comando and "--tiktok" not in comando


def test_recusa_volta_409_com_motivo(servidor, mundo):
    status, dados = _pedir(servidor, "POST", "/api/acao",
                           {"acao": "publicar", "args": {"id": PENDENTE, "onde": "youtube"}},
                           _token())
    assert status == 409 and "pendência" in dados["erro"]


def test_rastro_que_nao_grava_avisa_na_resposta(servidor, mundo, monkeypatch):
    token = _token()
    real = acoes.registrar

    def falha(*a, **k):
        acoes._RASTRO_FALHOU.set()
        raise OSError("disco")
    monkeypatch.setattr(acoes, "registrar", falha)
    status, dados = _pedir(servidor, "POST", "/api/acao",
                           {"acao": "pausar", "args": {"alvo": "tudo"}}, token)
    assert status == 200 and "rastro não foi gravado" in dados["texto"]
    status, dados = _pedir(servidor, "POST", "/api/acao", {"acao": "gerar"}, token)
    assert status == 409 and "não está gravando" in dados["erro"]
    monkeypatch.setattr(acoes, "registrar", real)
    status, _ = _pedir(servidor, "POST", "/api/acao", {"acao": "gerar"}, token)
    assert status == 200


def test_codigo_inventado_conta_como_chute(servidor, mundo, monkeypatch):
    monkeypatch.setattr(api_http, "FALHAS_MAX", 2)
    token = _token()
    for _ in range(2):
        assert _pedir(servidor, "POST", "/api/acao/confirmar",
                      {"codigo": "inventado"}, token)[0] == 404
    assert _pedir(servidor, "POST", "/api/acao/confirmar",
                  {"codigo": "inventado"}, token)[0] == 429
    assert _pedir(servidor, "GET", "/api/estado", token=token)[0] == 200


def test_cli_em_voo(mundo, capsys):
    acoes._por_em_voo("k", {"id": A, "onde": "tiktok", "desde": "2026-09-17T10:00:00",
                            "aparelho": "076f31d9"})
    assert api_http.main(["--em-voo"]) == 0
    assert A in capsys.readouterr().out
    assert api_http.main(["--liberar", "generation_00099:build:celular"]) == 1


def test_servidor_serializa_confirmacoes_simultaneas(servidor, mundo, monkeypatch):
    solta = threading.Event()
    mundo.roteiro = lambda: _Processo("TikTok: publicado no TikTok\n", 0, segurar=solta)
    monkeypatch.setattr(acoes, "processos", lambda: (time.sleep(0.3), [])[1])
    token = _token()
    codigos = []
    for video_id in (A, B):
        _, dados = _pedir(servidor, "POST", "/api/acao",
                          {"acao": "publicar", "args": {"id": video_id, "onde": "tiktok"}},
                          token)
        codigos.append(dados["confirmar"])
    respostas = []
    fios = [threading.Thread(target=lambda c=c: respostas.append(
        _pedir(servidor, "POST", "/api/acao/confirmar", {"codigo": c}, token)[0]))
        for c in codigos]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join(30)
    assert sorted(respostas) == [200, 409]
    assert len(mundo.processos) == 1
    solta.set()
