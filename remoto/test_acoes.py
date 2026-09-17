# -*- coding: utf-8 -*-
"""Fase 2 do app: acoes, guardas de publicacao e confirmacao em dois passos.

Nenhum teste encosta no `controle.json` real, no ledger real, na lista
"a conferir" real, no Telegram ou num `main.py publicar` de verdade. A
`publicacao_filha` e trocada por um duble que escreve `saida.log` e
`fim.json` como a de verdade escreveria; a de verdade tem testes proprios,
com um filho Python minusculo. As portas de confirmacao (`youtube_web` e
`tiktok`.confirmado) sao as REAIS. Os ids seguem o formato do catalogo.
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

from remoto import acoes, api_http, painel_dados, publicacao_filha

A = "generation_00041:build:celular"
B = "generation_00041:build:celular:B"
DOIS = "generation_00042:build:celular"
PENDENTE = "generation_00043:build:celular"
PC = "generation_00044:build:normal"
CINCO = "generation_00045:estreia:celular"

YT_OK = "https://youtu.be/abc123XYZ"
YT_FRASE = "publicado no YouTube"
YT_RASCUNHO = ("cliquei em publicar, mas o Studio nao mostrou a confirmacao. "
               "A janela ficou aberta: confira em studio.youtube.com se o video "
               "subiu antes de tentar de novo — ele pode ter ficado como RASCUNHO.")
TK_OK = "publicado no TikTok"
TK_CLIQUE = "cliquei em publicar; sem confirmação do TikTok"


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


class _Filha:
    """A `publicacao_filha` de mentira. `roteiro` = (saida, codigo) ou None
    (a filha "sumiu" sem fim). `segurar` atrasa o fim ate ser solto."""

    def __init__(self):
        self.comandos = []
        self.roteiro = ("", 0)
        self.segurar = None
        self.vivos = {}
        self._pid = 1000

    def iniciar(self, pasta, comando, cwd):
        self._pid += 1
        pid = self._pid
        self.comandos.append(list(comando))
        roteiro, segurar = self.roteiro, self.segurar
        self.vivos[pid] = True

        def correr():
            if segurar is not None:
                segurar.wait(10)
            if roteiro is None:
                self.vivos[pid] = False
                return
            saida, codigo = roteiro
            (pasta / "saida.log").write_text(saida, encoding="utf-8")
            (pasta / "fim.json").write_text(json.dumps({"codigo": codigo}),
                                            encoding="utf-8")
            self.vivos[pid] = False
        threading.Thread(target=correr, daemon=True).start()
        return pid


FORA_DA_GRADE = datetime(2026, 9, 17, 10, 0)


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    monkeypatch.setattr(api_http, "ARQUIVO", tmp_path / "app_celular.json")
    monkeypatch.setattr(acoes, "ARQUIVO_RASTRO", tmp_path / "acoes.jsonl")
    monkeypatch.setattr(acoes, "ARQUIVO_EM_VOO", tmp_path / "em_voo.json")
    monkeypatch.setattr(acoes, "PASTA_PUBLICACOES", tmp_path / "publicacoes")
    monkeypatch.setattr(acoes, "ARQUIVO_A_CONFERIR", tmp_path / "_tiktok_a_conferir.json")
    monkeypatch.setattr(acoes, "VIGIA_S", 0.05)
    acoes._RASTRO_FALHOU.clear()
    controle, comandos = _Controle(), _Comandos()
    metricas, grade, filha = _Metricas(tmp_path), _Grade(), _Filha()
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
    monkeypatch.setattr(acoes, "_controle", lambda: controle)
    monkeypatch.setattr(acoes, "_comandos", lambda: comandos)
    monkeypatch.setattr(acoes, "_metricas", lambda: metricas)
    monkeypatch.setattr(acoes, "_titulos", lambda: _Titulos)
    monkeypatch.setattr(acoes, "_grade", lambda: grade)
    monkeypatch.setattr(acoes, "_catalogo", lambda: catalogo)
    monkeypatch.setattr(acoes, "_iniciar_filha", filha.iniciar)
    monkeypatch.setattr(acoes, "_vivo", lambda pid: filha.vivos.get(pid))
    monkeypatch.setattr(acoes, "_agora", lambda: FORA_DA_GRADE)
    monkeypatch.setattr(acoes, "alvos_de_pausa", lambda: ["tudo", "digen", "picasso"])
    monkeypatch.setattr(acoes, "trava_ocupada", lambda nome: False)
    monkeypatch.setattr(acoes, "perfil_ocupado", lambda destino: False)
    monkeypatch.setattr(acoes, "processos", lambda: [])
    avisos = []
    monkeypatch.setattr(acoes, "_entregar", avisos.append)
    monkeypatch.setattr(painel_dados._Previsao, "disponivel", staticmethod(lambda: False))
    ns = types.SimpleNamespace(
        tmp=tmp_path, controle=controle, comandos=comandos, metricas=metricas,
        grade=grade, filha=filha, avisos=avisos, catalogo=catalogo)
    yield ns
    if filha.segurar is not None:
        filha.segurar.set()
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


def _marcas(mundo) -> dict:
    caminho = mundo.tmp / "_tiktok_a_conferir.json"
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}


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
    mundo.filha.roteiro = (f"YouTube: {YT_OK}\n", 0)
    _publicar({"id": DOIS, "onde": "youtube"})
    _esperar_publicacoes()
    (comando,) = mundo.filha.comandos
    assert comando[comando.index("--visibilidade") + 1] == "public"


def test_confirmacao_diz_qual_gancho(mundo):
    assert "gancho" not in acoes.preparar("publicar", {"id": A, "onde": "youtube"}, "ap")["texto"]
    texto = acoes.preparar("publicar", {"id": B, "onde": "youtube"}, "ap")["texto"]
    assert "«Build Um» (gancho B) no YouTube" in texto


# ==================================================== desfechos (A2 e cia.)
def test_portas_reais_recusam_o_rascunho():
    assert acoes.confirmado("youtube", YT_OK) is True
    assert acoes.confirmado("youtube", YT_FRASE + " (com a confirmacao extra)") is True
    assert acoes.confirmado("youtube", YT_RASCUNHO) is False
    assert acoes.confirmado("tiktok", TK_OK) is True
    assert acoes.confirmado("tiktok", TK_CLIQUE) is False


@pytest.mark.parametrize("saida,codigo,onde,esperado", [
    (f"YouTube: {YT_OK}\n", 0, "youtube", {"youtube": "publicado"}),
    (f"YouTube: {YT_FRASE}\n", 0, "youtube", {"youtube": "publicado"}),
    # A2: o Studio nao confirmou, e o main.py sai com 0 mesmo assim
    (f"YouTube: {YT_RASCUNHO}\n", 0, "youtube", {"youtube": "a_conferir"}),
    # video longo: TODAS as partes precisam confirmar
    (f"YouTube: {YT_OK}\nYouTube: {YT_OK}\n", 0, "youtube", {"youtube": "publicado"}),
    (f"YouTube: {YT_OK}\nYouTube: {YT_RASCUNHO}\n", 0, "youtube", {"youtube": "a_conferir"}),
    ("YouTube FALHOU: sessao\n", 1, "youtube", {"youtube": "a_conferir"}),
    ("YouTube: cota esgotada\n", 2, "youtube", {"youtube": "falha_limpa"}),
    # a parte 1 subiu e a cota acabou na 2
    (f"YouTube: {YT_OK}\nYouTube: cota esgotada\n", 2, "youtube",
     {"youtube": "a_conferir"}),
    (None, None, "youtube", {"youtube": "a_conferir"}),
    ("", 0, "youtube", {"youtube": "a_conferir"}),
    (f"TikTok: {TK_OK}\n", 0, "tiktok", {"tiktok": "publicado"}),
    (f"TikTok: {TK_CLIQUE}\n", 0, "tiktok", {"tiktok": "a_conferir"}),
    ("TikTok FALHOU: nao consegui abrir o chrome\n", 1, "tiktok", {"tiktok": "a_conferir"}),
    (f"TikTok: {TK_OK}\n", 1, "tiktok", {"tiktok": "a_conferir"}),      # nao saiu limpo
    (None, None, "tiktok", {"tiktok": "a_conferir"}),
    ("Traceback...\nOSError: [Errno 22]\n", 1, "tiktok", {"tiktok": "a_conferir"}),
    ("YouTube FALHOU: x\n", 1, "ambos", {"youtube": "a_conferir", "tiktok": "nao_tentado"}),
    ("YouTube: cota esgotada\n", 2, "ambos",
     {"youtube": "falha_limpa", "tiktok": "nao_tentado"}),
    (f"YouTube: {YT_OK}\nTikTok: {TK_OK}\n", 0, "ambos",
     {"youtube": "publicado", "tiktok": "publicado"}),
    (f"YouTube: {YT_RASCUNHO}\nTikTok: {TK_OK}\n", 0, "ambos",
     {"youtube": "a_conferir", "tiktok": "publicado"}),
])
def test_desfechos(saida, codigo, onde, esperado):
    assert acoes.desfechos(saida, codigo, onde) == esperado


def test_porta_que_nao_carrega_vira_a_conferir(monkeypatch):
    def quebra(destino, estado):
        raise ImportError("sem o modulo")
    monkeypatch.setattr(acoes, "confirmado", quebra)
    assert acoes.desfechos(f"TikTok: {TK_OK}\n", 0, "tiktok") == {"tiktok": "a_conferir"}
    assert acoes.desfechos(f"YouTube: {YT_OK}\n", 0, "youtube") == {"youtube": "a_conferir"}


# ============================== A1/A3: marca antes, soltura so no sucesso
def test_marca_do_tiktok_existe_antes_do_processo(mundo):
    mundo.filha.segurar = threading.Event()
    mundo.filha.roteiro = (f"TikTok: {TK_OK}\n", 0)
    _publicar({"id": A, "onde": "tiktok"})
    marca = _marcas(mundo)[A]
    assert marca["estado"].startswith("pelo app: publicação em andamento")
    (item,) = acoes.em_voo().values()
    assert item["estado"] == "em_andamento" and item["titulo"] == "Build Um"
    mundo.filha.segurar.set()
    _esperar_publicacoes()
    assert _marcas(mundo) == {} and acoes.em_voo() == {}      # sucesso limpo


def test_marca_nao_gravada_nao_sobe_nada(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "_gravar_json",
                        lambda caminho, dados: (_ for _ in ()).throw(OSError("cheio")))
    with pytest.raises(acoes.Recusa, match="marca"):
        _publicar({"id": A, "onde": "tiktok"})
    assert mundo.filha.comandos == []


def test_marca_que_nao_fica_nao_sobe_nada(mundo, monkeypatch):
    # grava "com sucesso", mas a releitura nao acha o id (o que a funcao do
    # postar faria com um arquivo cortado: engole o erro)
    monkeypatch.setattr(acoes, "_gravar_json", lambda caminho, dados: None)
    with pytest.raises(acoes.Recusa, match="não ficou gravada"):
        _publicar({"id": A, "onde": "tiktok"})
    assert mundo.filha.comandos == []


def test_lista_a_conferir_ilegivel_recusa_e_nao_e_regravada(mundo):
    caminho = mundo.tmp / "_tiktok_a_conferir.json"
    caminho.write_text('{"generation_00001:build:celular": {"estado": "x"', encoding="utf-8")
    with pytest.raises(acoes.Recusa, match="a conferir"):
        acoes.preparar("publicar", {"id": A, "onde": "tiktok"}, "ap")
    with pytest.raises(acoes.Recusa, match="a conferir"):
        acoes.preparar("publicar", {"id": A, "onde": "youtube"}, "ap")
    assert caminho.read_text(encoding="utf-8").startswith('{"generation_00001')


def test_lista_antiga_em_formato_de_lista_e_lida(mundo):
    (mundo.tmp / "_tiktok_a_conferir.json").write_text(json.dumps([CINCO]),
                                                        encoding="utf-8")
    for onde in ("tiktok", "ambos"):
        with pytest.raises(acoes.Recusa, match="a conferir"):
            acoes.preparar("publicar", {"id": CINCO, "onde": onde}, "ap")
    acoes.preparar("publicar", {"id": CINCO, "onde": "youtube"}, "ap")


def test_clique_sem_confirmacao_fica_marcado_e_bloqueado(mundo, monkeypatch):
    mundo.filha.roteiro = (f"TikTok: {TK_CLIQUE}\n", 0)
    _publicar({"id": A, "onde": "tiktok"})
    _esperar_publicacoes()
    marca = _marcas(mundo)[A]
    assert "a conferir" in marca["estado"] and TK_CLIQUE[:20] in marca["estado"]
    (item,) = acoes.em_voo().values()
    assert item["estado"] == "a_conferir" and "TikTok" in item["motivo"]
    monkeypatch.setattr(acoes, "_agora", lambda: FORA_DA_GRADE + timedelta(days=3))
    for video, onde in ((A, "tiktok"), (DOIS, "tiktok"), (A, "ambos")):
        with pytest.raises(acoes.Recusa):
            acoes.preparar("publicar", {"id": video, "onde": onde}, "ap")
    # o YouTube nao tem nada com isso
    acoes.preparar("publicar", {"id": DOIS, "onde": "youtube"}, "ap")
    acoes._FILA_AVISOS.join()
    assert any("a\\_conferir" in a for a in mundo.avisos)


def test_youtube_nao_confirmado_bloqueia_o_youtube(mundo):
    mundo.filha.roteiro = (f"YouTube: {YT_RASCUNHO}\n", 0)
    _publicar({"id": DOIS, "onde": "youtube"})
    _esperar_publicacoes()
    (item,) = acoes.em_voo().values()
    assert item["estado"] == "a_conferir" and "YouTube" in item["motivo"]
    with pytest.raises(acoes.Recusa, match="a conferir"):
        acoes.preparar("publicar", {"id": CINCO, "onde": "youtube"}, "ap")
    acoes.preparar("publicar", {"id": CINCO, "onde": "tiktok"}, "ap")
    assert _marcas(mundo) == {}              # o TikTok nem entrou nessa


def test_youtube_que_falhou_antes_tira_a_marca_do_tiktok(mundo):
    mundo.filha.roteiro = ("YouTube: cota esgotada\n", 2)
    _publicar({"id": A, "onde": "ambos"})
    _esperar_publicacoes()
    assert _marcas(mundo) == {} and acoes.em_voo() == {}


def test_ambos_com_youtube_em_rascunho_solta_so_o_tiktok(mundo):
    mundo.filha.roteiro = (f"YouTube: {YT_RASCUNHO}\nTikTok: {TK_OK}\n", 0)
    _publicar({"id": A, "onde": "ambos"})
    _esperar_publicacoes()
    assert _marcas(mundo) == {}
    (item,) = acoes.em_voo().values()
    assert item["motivo"] == "confira no YouTube"


def test_filha_que_some_sem_fim_fica_a_conferir(mundo):
    mundo.filha.roteiro = None                       # morreu sem escrever o fim
    _publicar({"id": A, "onde": "tiktok"})
    _esperar_publicacoes()
    assert "sem desfecho" in _marcas(mundo)[A]["estado"]
    (item,) = acoes.em_voo().values()
    assert item["estado"] == "a_conferir"


def test_servidor_que_cai_concilia_na_subida(mundo, monkeypatch):
    """O servidor morre com a publicacao no ar; o proximo le o fim e conclui."""
    mundo.filha.segurar = threading.Event()
    mundo.filha.roteiro = (f"TikTok: {TK_OK}\n", 0)
    monkeypatch.setattr(acoes, "vigiar", lambda chave: None)    # ninguem vigia
    _publicar({"id": A, "onde": "tiktok"})
    mundo.filha.segurar.set()                                   # a filha termina sozinha
    chave = next(iter(acoes.em_voo()))
    pasta = Path(acoes.em_voo()[chave]["pasta"])
    for _ in range(100):
        if (pasta / "fim.json").exists():
            break
        time.sleep(0.02)
    assert acoes.em_voo()[chave]["estado"] == "em_andamento"    # ainda sem conclusao
    monkeypatch.undo()          # volta tudo, e o mundo de novo sem o `vigiar` falso
    monkeypatch.setattr(api_http, "ARQUIVO", mundo.tmp / "app_celular.json")
    monkeypatch.setattr(acoes, "ARQUIVO_RASTRO", mundo.tmp / "acoes.jsonl")
    monkeypatch.setattr(acoes, "ARQUIVO_EM_VOO", mundo.tmp / "em_voo.json")
    monkeypatch.setattr(acoes, "PASTA_PUBLICACOES", mundo.tmp / "publicacoes")
    monkeypatch.setattr(acoes, "ARQUIVO_A_CONFERIR", mundo.tmp / "_tiktok_a_conferir.json")
    monkeypatch.setattr(acoes, "VIGIA_S", 0.05)
    monkeypatch.setattr(acoes, "_entregar", mundo.avisos.append)
    monkeypatch.setattr(acoes, "_metricas", lambda: mundo.metricas)
    assert acoes.conciliar() == [chave]
    _esperar_publicacoes()
    assert acoes.em_voo() == {} and _marcas(mundo) == {}


def test_marca_que_nao_atualiza_no_fim_mantem_tudo_e_avisa(mundo, monkeypatch):
    mundo.filha.segurar = threading.Event()
    mundo.filha.roteiro = (f"TikTok: {TK_CLIQUE}\n", 0)
    _publicar({"id": A, "onde": "tiktok"})
    (mundo.tmp / "_tiktok_a_conferir.json").write_text("{cortado", encoding="utf-8")
    mundo.filha.segurar.set()
    _esperar_publicacoes()
    (item,) = acoes.em_voo().values()
    assert item["estado"] == "a_conferir"
    acoes._FILA_AVISOS.join()
    assert any("marca do TikTok não atualizada" in a for a in mundo.avisos)
    assert (mundo.tmp / "_tiktok_a_conferir.json").read_text(encoding="utf-8") == "{cortado"


def test_qualquer_publicacao_do_app_no_destino_barra_as_outras(mundo):
    mundo.filha.segurar = threading.Event()
    mundo.filha.roteiro = (f"TikTok: {TK_OK}\n", 0)
    _publicar({"id": A, "onde": "tiktok"})
    with pytest.raises(acoes.Recusa, match=f"outra publicação do app no TikTok \\({A}\\)"):
        acoes.preparar("publicar", {"id": DOIS, "onde": "tiktok"}, "outro")
    with pytest.raises(acoes.Recusa, match="já foi mandado"):
        acoes.preparar("publicar", {"id": A, "onde": "ambos"}, "outro")
    acoes.preparar("publicar", {"id": B, "onde": "youtube"}, "outro")


def test_em_voo_ilegivel_recusa_depois_de_tentar(mundo, monkeypatch):
    (mundo.tmp / "em_voo.json").write_text("{quebrado", encoding="utf-8")
    comeco = time.monotonic()
    with pytest.raises(acoes.Recusa, match="ilegível"):
        acoes.preparar("publicar", {"id": DOIS, "onde": "youtube"}, "ap")
    assert time.monotonic() - comeco >= 0.3          # tentou de novo


def test_em_voo_que_volta_na_segunda_leitura(mundo, monkeypatch):
    real = Path.read_text
    vezes = {"n": 0}

    def instavel(self, *a, **k):
        if self.name == "em_voo.json":
            vezes["n"] += 1
            if vezes["n"] == 1:
                raise PermissionError("sendo trocado")
        return real(self, *a, **k)
    (mundo.tmp / "em_voo.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(Path, "read_text", instavel)
    assert acoes.em_voo() == {}


# ================================================= liberar (B7) e CLI
def test_liberar_mostra_antes_e_so_solta_com_confirmo(mundo, capsys):
    mundo.filha.roteiro = (f"TikTok: {TK_CLIQUE}\n", 0)
    _publicar({"id": A, "onde": "tiktok"})
    _esperar_publicacoes()
    mundo.metricas.linhas = [{"video_id": A, "plataforma": "youtube",
                              "quando": "2026-09-16T20:00:00", "publicado": True}]
    assert api_http.main(["--liberar", A]) == 0
    saida = capsys.readouterr().out
    assert "em voo: tiktok a_conferir" in saida
    assert "ledger: youtube" in saida and "a conferir (TikTok)" in saida
    assert "--confirmo" in saida
    assert len(acoes.em_voo()) == 1                     # nada saiu
    assert api_http.main(["--liberar", A, "--confirmo"]) == 0
    assert acoes.em_voo() == {}
    assert A in _marcas(mundo)                          # a marca fica
    assert api_http.main(["--liberar", "generation_00099:build:celular",
                          "--confirmo"]) == 1


def test_liberar_com_trava_presa(mundo, monkeypatch, capsys):
    def presa():
        raise OSError("trava ocupada")
    monkeypatch.setattr(acoes, "trava_de_acoes", presa)
    assert api_http.main(["--liberar", A, "--confirmo"]) == 3
    assert "não consegui soltar agora" in capsys.readouterr().out


def test_cli_em_voo(mundo, capsys):
    acoes._mexer_no_voo("k", {"id": A, "onde": "tiktok", "estado": "em_andamento",
                              "desde": "2026-09-17T10:00:00", "aparelho": "076f31d9"})
    assert api_http.main(["--em-voo"]) == 0
    assert A in capsys.readouterr().out


# ================================================== 3/M6. uma acao por vez
def test_trava_entre_threads_tem_prazo(mundo, monkeypatch):
    monkeypatch.setattr(api_http, "TRAVA_PRAZO_S", 0.3)
    dentro, sair = threading.Event(), threading.Event()

    def segurar():
        with acoes.trava_de_acoes():
            dentro.set()
            sair.wait(5)
    fio = threading.Thread(target=segurar)
    fio.start()
    dentro.wait(5)
    try:
        with pytest.raises(OSError, match="ocupada"):
            with acoes.trava_de_acoes():
                pass
    finally:
        sair.set()
        fio.join(5)


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
        acoes.registrar("ap", "pausar", {}, "ok")
    assert time.monotonic() - inicio < 3


# ============================================================ 4. rastro
def test_rastro_ilegivel_recusa(mundo, monkeypatch):
    pasta = mundo.tmp / "rastro_pasta"
    pasta.mkdir()
    monkeypatch.setattr(acoes, "ARQUIVO_RASTRO", pasta)
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
        acoes.registrar("ap", "gerar", {}, "ok")
    monkeypatch.setattr(acoes, "_agora", lambda: FORA_DA_GRADE)
    acoes.registrar("ap", "gerar", {}, "ok")
    for _ in range(12):
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
                              "plataforma": "youtube", "url": YT_OK,
                              "titulo": "Build Dois"}]
    for onde in ("youtube", "ambos"):
        with pytest.raises(acoes.Recusa, match="já saiu no YouTube"):
            acoes.preparar("publicar", {"id": DOIS, "onde": onde}, "ap")
    acoes.preparar("publicar", {"id": DOIS, "onde": "tiktok"}, "ap")


def test_linha_sem_plataforma_e_do_youtube_e_rascunho_nao_conta(mundo):
    mundo.metricas.linhas = [
        {"video_id": DOIS, "url": YT_OK},
        {"video_id": CINCO, "plataforma": "youtube",
         "url": YT_FRASE, "publicado": False},
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
    acoes.preparar("gerar", {}, "ap")


def test_avisos_saem_por_uma_thread_so_e_em_ordem(mundo):
    for i in range(20):
        acoes.avisar_telegram("ap", "pausar", f"n{i}")
    acoes._FILA_AVISOS.join()
    carteiros = [f for f in threading.enumerate() if f.name == "avisos-app"]
    assert len(carteiros) == 1
    assert [a.rsplit(" ", 1)[-1] for a in mundo.avisos[-20:]] == [f"n{i}" for i in range(20)]


def test_escapa_markdown_do_telegram():
    assert acoes._escapar_markdown("g_1 *x* `y` [z]") == "g\\_1 \\*x\\* \\`y\\` \\[z]"


# ============================================ publicacao_filha (de verdade)
def test_filha_de_verdade_escreve_saida_e_fim(tmp_path):
    pasta = tmp_path / "pub"
    filho = [sys.executable, "-c",
             "import sys; print('YouTube: https://youtu.be/x'); "
             "print('TikTok: publicado no TikTok'); sys.exit(0)"]
    assert publicacao_filha.main(["--pasta", str(pasta), "--cwd", str(tmp_path),
                                  "--"] + filho) == 0
    assert "TikTok: publicado no TikTok" in (pasta / "saida.log").read_text(encoding="utf-8")
    assert json.loads((pasta / "fim.json").read_text(encoding="utf-8"))["codigo"] == 0
    assert acoes.desfechos((pasta / "saida.log").read_text(encoding="utf-8"), 0,
                           "ambos") == {"youtube": "publicado", "tiktok": "publicado"}


def test_filha_desligada_sobrevive_ao_servidor_que_morre(tmp_path):
    """O "servidor" (um processo) sobe a filha real e MORRE na hora, com o
    pipe dele fechado. O filho so escreve depois disso — e muito — e mesmo
    assim termina e deixa o fim gravado."""
    pasta = tmp_path / "pub"
    pasta.mkdir()
    filho = [sys.executable, "-c",
             "import time; time.sleep(1.5); "
             "print('TikTok: publicado no TikTok', flush=True); "
             "print('x' * 100000, flush=True)"]
    servidor = (
        "import sys\n"
        "from pathlib import Path\n"
        "from remoto import acoes\n"
        f"pid = acoes._iniciar_filha(Path({str(pasta)!r}), {filho!r}, {str(tmp_path)!r})\n"
        "print(pid, flush=True)\n"
        "sys.exit(0)\n"
    )
    pai = subprocess.run([sys.executable, "-c", servidor], capture_output=True,
                         text=True, timeout=30,
                         cwd=str(Path(acoes.__file__).parents[1]))
    assert pai.returncode == 0 and int(pai.stdout.strip()) > 0
    assert not (pasta / "fim.json").exists()          # o pai morreu antes do fim
    for _ in range(200):
        if (pasta / "fim.json").exists():
            break
        time.sleep(0.05)
    fim = json.loads((pasta / "fim.json").read_text(encoding="utf-8"))
    assert fim["codigo"] == 0
    assert "publicado no TikTok" in (pasta / "saida.log").read_text(encoding="utf-8")


def test_filha_com_comando_que_nao_existe_grava_fim(tmp_path):
    pasta = tmp_path / "pub"
    assert publicacao_filha.main(["--pasta", str(pasta), "--cwd", str(tmp_path),
                                  "--", str(tmp_path / "nao_existe.exe")]) == 1
    fim = json.loads((pasta / "fim.json").read_text(encoding="utf-8"))
    assert fim["codigo"] is None and fim["erro"]


# ============================================================ servidor
@pytest.fixture
def servidor(mundo):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True, com_acoes=True,
                                  com_publicar=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _pedir(srv, metodo, caminho, corpo=None, token=None, tipo="application/json"):
    porta = srv.server_address[1]
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=30)
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


def test_acoes_sem_publicar(mundo):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True, com_acoes=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        token = _token()
        _, info = _pedir(srv, "GET", "/api/acoes", token=token)
        assert info["ligadas"] is True and info["publicar"] is False
        status, dados = _pedir(srv, "POST", "/api/acao",
                               {"acao": "publicar", "args": {"id": DOIS, "onde": "youtube"}},
                               token)
        assert status == 403 and "publicar" in dados["erro"]
        assert _pedir(srv, "POST", "/api/acao",
                      {"acao": "pausar", "args": {"alvo": "tudo"}}, token)[0] == 200
        assert mundo.filha.comandos == []
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
    assert dados["ligadas"] and dados["publicar"] and dados["restantes"] == 6


def test_parar_so_executa_na_confirmacao_e_toque_duplo_nao_e_chute(servidor, mundo,
                                                                  monkeypatch):
    monkeypatch.setattr(api_http, "FALHAS_MAX", 1)
    token = _token()
    status, dados = _pedir(servidor, "POST", "/api/acao", {"acao": "parar"}, token)
    assert status == 200 and "confirmar" in dados
    assert mundo.controle.chamadas == []
    codigo = dados["confirmar"]
    assert _pedir(servidor, "POST", "/api/acao/confirmar", {"codigo": codigo}, token)[0] == 200
    for _ in range(3):
        assert _pedir(servidor, "POST", "/api/acao/confirmar",
                      {"codigo": codigo}, token)[0] == 410
    assert mundo.controle.chamadas == [("parar", "pelo app")]
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
    assert mundo.filha.comandos == []


def test_args_ficam_congelados_no_primeiro_passo(servidor, mundo):
    mundo.filha.roteiro = (f"YouTube: {YT_OK}\n", 0)
    token = _token()
    _, dados = _pedir(servidor, "POST", "/api/acao",
                      {"acao": "publicar", "args": {"id": DOIS, "onde": "youtube"}}, token)
    status, resposta = _pedir(servidor, "POST", "/api/acao/confirmar",
                              {"codigo": dados["confirmar"],
                               "args": {"id": CINCO, "onde": "ambos"}}, token)
    assert status == 200 and "público" in resposta["texto"]
    _esperar_publicacoes()
    (comando,) = mundo.filha.comandos
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


def test_servidor_serializa_confirmacoes_simultaneas(servidor, mundo, monkeypatch):
    mundo.filha.segurar = threading.Event()
    mundo.filha.roteiro = (f"TikTok: {TK_OK}\n", 0)
    monkeypatch.setattr(acoes, "processos", lambda: (time.sleep(0.3), [])[1])
    token = _token()
    codigos = []
    for video_id in (A, DOIS):
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
    assert len(mundo.filha.comandos) == 1


# =================================================== quarta rodada
_JOB = r'''
import ctypes, sys
from ctypes import wintypes
from pathlib import Path
from remoto import acoes
k32 = ctypes.windll.kernel32
k32.CreateJobObjectW.restype = wintypes.HANDLE
k32.GetCurrentProcess.restype = wintypes.HANDLE
k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                        ctypes.c_void_p, wintypes.DWORD]
class BASIC(ctypes.Structure):
    _fields_ = [("a", ctypes.c_int64), ("b", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("c", ctypes.c_size_t),
                ("d", ctypes.c_size_t), ("e", wintypes.DWORD),
                ("f", ctypes.c_size_t), ("g", wintypes.DWORD), ("h", wintypes.DWORD)]
class EXT(ctypes.Structure):
    _fields_ = [("Basic", BASIC), ("Io", ctypes.c_uint64 * 6),
                ("i", ctypes.c_size_t), ("j", ctypes.c_size_t),
                ("k", ctypes.c_size_t), ("l", ctypes.c_size_t)]
job = k32.CreateJobObjectW(None, None)
info = EXT()
info.Basic.LimitFlags = 0x2000 | 0x800
assert k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
assert k32.AssignProcessToJobObject(job, k32.GetCurrentProcess())
if sys.argv[2] == "sem":
    acoes.FORA_DO_JOB = 0
pasta = Path(sys.argv[1])
filho = [sys.executable, "-c",
         "import time; time.sleep(2.0); print('TikTok: publicado no TikTok')"]
print(acoes._iniciar_filha(pasta, filho, str(pasta)), flush=True)
'''


def _servidor_num_job(pasta, modo):
    return subprocess.run([sys.executable, "-c", _JOB, str(pasta), modo],
                          capture_output=True, text=True, timeout=30,
                          cwd=str(Path(acoes.__file__).parents[1]))


def _esperar_arquivo(caminho, segundos=15.0):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        if caminho.exists():
            return True
        time.sleep(0.1)
    return False


@pytest.mark.skipif(sys.platform != "win32", reason="job object e do Windows")
def test_filha_sobrevive_ao_job_que_mata_ao_fechar(tmp_path):
    pasta = tmp_path / "com"
    pasta.mkdir()
    pai = _servidor_num_job(pasta, "com")
    assert pai.returncode == 0, pai.stderr
    assert _esperar_arquivo(pasta / "fim.json")
    assert json.loads((pasta / "fim.json").read_text(encoding="utf-8"))["codigo"] == 0


@pytest.mark.skipif(sys.platform != "win32", reason="job object e do Windows")
def test_sem_breakaway_o_job_mata_a_filha(tmp_path):
    """O controle do teste acima: sem sair do job, a filha morre com o pai.
    Se este passar a falhar, o teste acima deixou de provar alguma coisa."""
    pasta = tmp_path / "sem"
    pasta.mkdir()
    pai = _servidor_num_job(pasta, "sem")
    assert pai.returncode == 0, pai.stderr
    assert not _esperar_arquivo(pasta / "fim.json", segundos=6.0)


# ---------------------------------------------------------------- M1
def test_vigia_nao_desiste_quando_a_trava_estoura(mundo, monkeypatch):
    mundo.filha.roteiro = (f"TikTok: {TK_OK}\n", 0)
    real = acoes.concluir_publicacao
    tentativas = {"n": 0}

    def instavel(chave):
        tentativas["n"] += 1
        if tentativas["n"] <= 2:
            raise OSError("trava ocupada ha mais de 15 s")
        return real(chave)
    monkeypatch.setattr(acoes, "concluir_publicacao", instavel)
    _publicar({"id": A, "onde": "tiktok"})
    _esperar_publicacoes()
    assert tentativas["n"] == 3
    assert acoes.em_voo() == {} and _marcas(mundo) == {}


def test_vigia_espera_crescente(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "ESPERA_ERRO_MAX_S", 0.4)
    esperas = []
    real_sleep = time.sleep

    def dormir(segundos):
        esperas.append(segundos)
        real_sleep(0.001)
    monkeypatch.setattr(acoes.time, "sleep", dormir)
    mundo.filha.roteiro = (f"TikTok: {TK_OK}\n", 0)
    real = acoes.concluir_publicacao
    tentativas = {"n": 0}

    def instavel(chave):
        tentativas["n"] += 1
        if tentativas["n"] <= 5:
            raise OSError("disco")
        return real(chave)
    monkeypatch.setattr(acoes, "concluir_publicacao", instavel)
    _publicar({"id": A, "onde": "tiktok"})
    _esperar_publicacoes()
    monkeypatch.undo()
    # a primeira espera de erro e o proprio VIGIA_S (0,05), igual as normais
    erros = [e for e in esperas if e != 0.05]
    assert erros == [0.1, 0.2, 0.4, 0.4] and tentativas["n"] == 6


# ---------------------------------------------------------------- M2
def _item_preso(mundo, *, fim, filha, filho=None):
    pasta = mundo.tmp / "publicacoes" / "k"
    pasta.mkdir(parents=True, exist_ok=True)
    if fim:
        (pasta / "fim.json").write_text('{"codigo": 0}', encoding="utf-8")
    if filho is not None:
        (pasta / "filho.json").write_text(json.dumps({"pid": 77, "criado": None}),
                                          encoding="utf-8")
        mundo.filha.vivos[77] = filho
    mundo.filha.vivos[55] = filha
    acoes._mexer_no_voo("k", {"id": A, "onde": "youtube", "estado": "a_conferir",
                              "pasta": str(pasta), "pid": 55, "criado": None})


@pytest.mark.parametrize("fim,filha,filho,pode", [
    (False, True, None, False),          # rodando
    (False, None, None, False),          # nao sei
    (True, False, True, False),          # a filha acabou, o main.py nao
    (True, False, None, True),           # acabou tudo
    (False, False, False, True),         # morreram sem fim: ja nao roda nada
    (True, True, False, True),           # fim gravado; o que resta e o fim da filha
])
def test_liberar_so_quando_nada_mais_roda(mundo, fim, filha, filho, pode):
    _item_preso(mundo, fim=fim, filha=filha, filho=filho)
    if pode:
        assert acoes.liberar(A) == 1
    else:
        with pytest.raises(acoes.Recusa, match="não solto"):
            acoes.liberar(A)
        assert len(acoes.em_voo()) == 1


def test_liberar_recusado_pelo_cli(mundo, capsys):
    _item_preso(mundo, fim=False, filha=True)
    assert api_http.main(["--liberar", A, "--confirmo"]) == 1
    assert "ainda não terminou" in capsys.readouterr().out


def test_pid_reaproveitado_conta_como_morto(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "_vivo", lambda pid: True)
    monkeypatch.setattr(acoes, "_criado_em", lambda pid: 2000.0)
    assert acoes.vivo_de_verdade(55, 2000.5) is True
    assert acoes.vivo_de_verdade(55, 1000.0) is False
    assert acoes.vivo_de_verdade(55, None) is True
    monkeypatch.setattr(acoes, "_criado_em", lambda pid: None)
    assert acoes.vivo_de_verdade(55, 1000.0) is None
    monkeypatch.setattr(acoes, "_vivo", lambda pid: False)
    assert acoes.vivo_de_verdade(55, 1000.0) is False


def test_criado_em_do_proprio_processo():
    import os
    agora = time.time()
    criado = publicacao_filha.criado_em(os.getpid())
    assert criado is not None and agora - 86400 < criado <= agora + 1
    assert publicacao_filha.criado_em(0) is None
    assert publicacao_filha.criado_em("x") is None


def test_filha_de_verdade_grava_a_hora_do_filho(tmp_path):
    pasta = tmp_path / "pub"
    publicacao_filha.main(["--pasta", str(pasta), "--cwd", str(tmp_path), "--",
                           sys.executable, "-c", "print('ok')"])
    filho = json.loads((pasta / "filho.json").read_text(encoding="utf-8"))
    assert filho["pid"] > 0 and filho["criado"]


# ------------------------------------------------ conciliar e casos novos
def test_conciliar_com_filha_viva_nao_conclui(mundo):
    pasta = mundo.tmp / "publicacoes" / "viva"
    pasta.mkdir(parents=True)
    mundo.filha.vivos[88] = True
    acoes._mexer_no_voo("viva", {"id": A, "onde": "tiktok", "estado": "em_andamento",
                                 "pasta": str(pasta), "pid": 88})
    assert acoes.conciliar() == ["viva"]
    time.sleep(0.3)
    assert acoes.em_voo()["viva"]["estado"] == "em_andamento"
    mundo.filha.vivos[88] = False
    _esperar_publicacoes()
    assert acoes.em_voo()["viva"]["estado"] == "a_conferir"


def test_conciliar_com_pasta_sumida(mundo):
    mundo.filha.vivos[89] = False
    acoes._mexer_no_voo("sumida", {"id": DOIS, "onde": "youtube",
                                   "estado": "em_andamento",
                                   "pasta": str(mundo.tmp / "nao_existe"), "pid": 89})
    acoes.conciliar()
    _esperar_publicacoes()
    item = acoes.em_voo()["sumida"]
    assert item["estado"] == "a_conferir" and "YouTube" in item["motivo"]


@pytest.mark.parametrize("saida,codigo,onde", [
    ("TikTok: A CONFERIR - cliquei e nao confirmou\n", 3, "tiktok"),
    ("YouTube: A CONFERIR - rascunho\n", 3, "youtube"),
    (f"TikTok: {TK_OK}\n", 3, "tiktok"),
    (f"YouTube: {YT_OK}\n", 3, "youtube"),
])
def test_a_conferir_e_codigo_3(saida, codigo, onde):
    assert set(acoes.desfechos(saida, codigo, onde).values()) == {"a_conferir"}


def test_escrita_concorrente_no_em_voo(mundo):
    def poe(i):
        acoes._mexer_no_voo(f"k{i}", {"id": f"generation_{i:05d}:build:celular",
                                      "onde": "youtube", "estado": "a_conferir"})
    fios = [threading.Thread(target=poe, args=(i,)) for i in range(25)]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join(30)
    assert len(acoes.em_voo()) == 25


def test_escrita_concorrente_entre_processos(mundo):
    outro = (
        "from remoto import acoes\n"
        f"acoes.ARQUIVO_EM_VOO = {str(mundo.tmp / 'em_voo.json')!r}\n"
        f"acoes.ARQUIVO_RASTRO = {str(mundo.tmp / 'acoes.jsonl')!r}\n"
        "for i in range(30):\n"
        "    acoes._mexer_no_voo(f'p{i}', {'id': f'p{i}', 'onde': 'tiktok', 'estado': 'x'})\n"
    )
    processo = subprocess.Popen([sys.executable, "-c", outro],
                                cwd=str(Path(acoes.__file__).parents[1]))
    for i in range(30):
        acoes._mexer_no_voo(f"t{i}", {"id": f"t{i}", "onde": "tiktok", "estado": "x"})
    assert processo.wait(timeout=60) == 0
    chaves = set(acoes.em_voo())
    assert {f"p{i}" for i in range(30)} <= chaves
    assert {f"t{i}" for i in range(30)} <= chaves


# ------------------------------------------------------- soltar a marca
def test_soltar_marca_so_a_do_app_e_so_fora_do_voo(mundo, capsys):
    mundo.filha.roteiro = (f"TikTok: {TK_CLIQUE}\n", 0)
    _publicar({"id": A, "onde": "tiktok"})
    _esperar_publicacoes()
    with pytest.raises(acoes.Recusa, match="em-voo"):
        acoes.soltar_marca(A)
    acoes.liberar(A)
    assert api_http.main(["--soltar-marca", A]) == 0
    saida = capsys.readouterr().out
    assert "a conferir (TikTok)" in saida and "--confirmo" in saida
    assert A in _marcas(mundo)
    assert api_http.main(["--soltar-marca", A, "--confirmo"]) == 0
    assert A not in _marcas(mundo)
    assert api_http.main(["--soltar-marca", A, "--confirmo"]) == 1


def test_marca_da_grade_nao_sai_pelo_app(mundo):
    (mundo.tmp / "_tiktok_a_conferir.json").write_text(
        json.dumps({CINCO: {"quando": "2026-09-16T20:00:00", "estado": "cliquei"}}),
        encoding="utf-8")
    with pytest.raises(acoes.Recusa, match="da grade"):
        acoes.soltar_marca(CINCO)
    assert CINCO in _marcas(mundo)
