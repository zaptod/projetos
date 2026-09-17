# -*- coding: utf-8 -*-
"""Fase 2 do app: acoes, guardas de publicacao e confirmacao em dois passos.

Nenhum teste encosta no `controle.json` real, no ledger real, no Telegram ou
em subprocesso: tudo que executa e duble, e o que se confere e o que TERIA
sido chamado.
"""
from __future__ import annotations

import http.client
import json
import threading
import types
from datetime import datetime

import pytest

from remoto import acoes, api_http, painel_dados


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
        self.rodados = []

    def gerar(self):
        self.rodados.append(["gerar"])
        return "comecei: uma build nova"

    def _rodar(self, args, cwd, rotulo):
        self.rodados.append(list(args))
        return f"comecei: {rotulo}"


def _video(id_, titulo, fonte, pendencias=(), perfil="celular"):
    return types.SimpleNamespace(id=id_, titulo=titulo, fonte_id=fonte,
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


FORA_DA_GRADE = datetime(2026, 9, 17, 10, 0)


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    monkeypatch.setattr(api_http, "ARQUIVO", tmp_path / "app_celular.json")
    monkeypatch.setattr(acoes, "ARQUIVO_RASTRO", tmp_path / "acoes.jsonl")
    controle, comandos = _Controle(), _Comandos()
    metricas, grade = _Metricas(tmp_path), _Grade()
    videos = [
        _video("g1:build:normal:", "Build Um", "g1"),
        _video("g1:build:normal::B", "Build Um", "g1"),
        _video("g2:build:normal:", "Build Dois", "g2"),
        _video("g3:build:normal:", "Build Tres", "g3", pendencias=["sem payoff"]),
        _video("g4:build:pc:", "Build Quatro", "g4", perfil="pc"),
        _video("g5:build:normal:", "Build Cinco", "g5"),
    ]
    catalogo = types.SimpleNamespace(listar=lambda: list(videos),
                                     carregar_config=lambda: {})
    monkeypatch.setattr(acoes, "_controle", lambda: controle)
    monkeypatch.setattr(acoes, "_comandos", lambda: comandos)
    monkeypatch.setattr(acoes, "_metricas", lambda: metricas)
    monkeypatch.setattr(acoes, "_titulos", lambda: _Titulos)
    monkeypatch.setattr(acoes, "_grade", lambda: grade)
    monkeypatch.setattr(acoes, "_catalogo", lambda: catalogo)
    monkeypatch.setattr(acoes, "_agora", lambda: FORA_DA_GRADE)
    monkeypatch.setattr(acoes, "alvos_de_pausa", lambda: ["tudo", "digen", "picasso"])
    monkeypatch.setattr(acoes, "trava_ocupada", lambda nome: False)
    monkeypatch.setattr(acoes, "gerando_builds", lambda: False)
    avisos = []
    monkeypatch.setattr(acoes, "avisar_telegram",
                        lambda ap, acao, res: avisos.append((ap, acao, res)))
    # a leitura da fase 1 nao importa aqui
    monkeypatch.setattr(painel_dados._Previsao, "disponivel", staticmethod(lambda: False))
    return types.SimpleNamespace(tmp=tmp_path, controle=controle, comandos=comandos,
                                 metricas=metricas, grade=grade, avisos=avisos,
                                 catalogo=catalogo)


# ------------------------------------------------------------ guardas
def test_publicar_monta_o_comando_com_o_id_exato(mundo):
    pedido = acoes.preparar("publicar", {"id": "g1:build:normal:", "onde": "ambos"}, "ap")
    assert pedido["dois_passos"]
    assert "Build Um" in pedido["texto"] and "YouTube e no TikTok" in pedido["texto"]
    assert "gancho" not in pedido["texto"]
    b = acoes.preparar("publicar", {"id": "g1:build:normal::B", "onde": "youtube"}, "ap")
    assert "«Build Um» (gancho B) no YouTube" in b["texto"]
    acoes.executar(pedido["acao"], pedido["args"])
    assert mundo.comandos.rodados == [["python", "main.py", "publicar",
                                       "g1:build:normal:", "--youtube",
                                       "--tiktok", "--postar"]]


@pytest.mark.parametrize("args,trecho", [
    ({"id": "g1:build", "onde": "youtube"}, "não está no catálogo"),   # prefixo nao vale
    ({"id": "g3:build:normal:", "onde": "youtube"}, "pendência"),
    ({"id": "g4:build:pc:", "onde": "youtube"}, "celular"),
    ({"id": "g2:build:normal:", "onde": "kwai"}, "destino inválido"),
    ({"id": "", "onde": "youtube"}, "não está no catálogo"),
])
def test_publicar_recusa_o_basico(mundo, args, trecho):
    with pytest.raises(acoes.Recusa, match=trecho):
        acoes.preparar("publicar", args, "ap")


def test_ja_saiu_naquele_destino(mundo):
    mundo.metricas.linhas = [{"video_id": "g2:build:normal:", "fonte_id": "g2",
                              "plataforma": "youtube", "url": "https://youtu.be/x",
                              "titulo": "Build Dois"}]
    with pytest.raises(acoes.Recusa, match="já saiu no YouTube"):
        acoes.preparar("publicar", {"id": "g2:build:normal:", "onde": "youtube"}, "ap")
    with pytest.raises(acoes.Recusa, match="já saiu no YouTube"):
        acoes.preparar("publicar", {"id": "g2:build:normal:", "onde": "ambos"}, "ap")
    # o outro destino continua livre
    acoes.preparar("publicar", {"id": "g2:build:normal:", "onde": "tiktok"}, "ap")


def test_linha_sem_plataforma_e_do_youtube_e_rascunho_nao_conta(mundo):
    mundo.metricas.linhas = [
        {"video_id": "g2:build:normal:", "url": "https://youtu.be/x"},
        {"video_id": "g5:build:normal:", "plataforma": "youtube",
         "url": "publicado no YouTube", "publicado": False},
    ]
    with pytest.raises(acoes.Recusa, match="já saiu no YouTube"):
        acoes.preparar("publicar", {"id": "g2:build:normal:", "onde": "youtube"}, "ap")
    acoes.preparar("publicar", {"id": "g5:build:normal:", "onde": "youtube"}, "ap")


def test_outra_variante_da_mesma_geracao(mundo):
    mundo.metricas.linhas = [{"video_id": "g1:build:normal::B", "fonte_id": "g1",
                              "plataforma": "tiktok", "publicado": True,
                              "titulo": "outro"}]
    with pytest.raises(acoes.Recusa, match="outra variante de g1 já saiu no TikTok"):
        acoes.preparar("publicar", {"id": "g1:build:normal:", "onde": "tiktok"}, "ap")
    acoes.preparar("publicar", {"id": "g1:build:normal:", "onde": "youtube"}, "ap")


def test_titulo_ja_no_ar_por_outro_video(mundo):
    mundo.metricas.linhas = [{"video_id": "g9:build:normal:", "fonte_id": "g9",
                              "plataforma": "youtube", "publicado": True,
                              "titulo": "  build dois "}]
    with pytest.raises(acoes.Recusa, match="título"):
        acoes.preparar("publicar", {"id": "g2:build:normal:", "onde": "youtube"}, "ap")
    # o interruptor do config desliga esta guarda, como no postar
    mundo.catalogo.carregar_config = lambda: {"grade": {"repetir_titulo": True}}
    acoes.preparar("publicar", {"id": "g2:build:normal:", "onde": "youtube"}, "ap")


def test_a_conferir_no_tiktok(mundo):
    (mundo.tmp / "_tiktok_a_conferir.json").write_text(
        json.dumps(["g5:build:normal:"]), encoding="utf-8")
    with pytest.raises(acoes.Recusa, match="a conferir"):
        acoes.preparar("publicar", {"id": "g5:build:normal:", "onde": "tiktok"}, "ap")
    with pytest.raises(acoes.Recusa, match="a conferir"):
        acoes.preparar("publicar", {"id": "g5:build:normal:", "onde": "ambos"}, "ap")
    acoes.preparar("publicar", {"id": "g5:build:normal:", "onde": "youtube"}, "ap")


@pytest.mark.parametrize("hora,minuto,barra", [
    (6, 17, True), (6, 37, True), (6, 55, True), (6, 16, False), (6, 56, False),
    (11, 47, True), (11, 46, False), (12, 25, True), (12, 26, False), (10, 0, False),
])
def test_janela_da_postagem(mundo, hora, minuto, barra):
    agora = datetime(2026, 9, 17, hora, minuto)
    assert (acoes.postagem_em_curso(agora) is not None) is barra


def test_janela_que_cruza_a_meia_noite(mundo):
    mundo.grade.lista = ["00:05"]
    assert acoes.postagem_em_curso(datetime(2026, 9, 17, 23, 50)) == "00:05"
    assert acoes.postagem_em_curso(datetime(2026, 9, 17, 0, 20)) == "00:05"


def test_publicar_na_janela_e_recusado(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "_agora", lambda: datetime(2026, 9, 17, 6, 40))
    with pytest.raises(acoes.Recusa, match="06:37"):
        acoes.preparar("publicar", {"id": "g2:build:normal:", "onde": "youtube"}, "ap")


def test_publicacao_em_voo_pelo_app_barra_o_mesmo_e_a_variante(servidor, mundo):
    token = _token()
    args = {"id": "g1:build:normal:", "onde": "tiktok"}
    _, dados = _pedir(servidor, "POST", "/api/acao", {"acao": "publicar", "args": args}, token)
    status, _ = _pedir(servidor, "POST", "/api/acao/confirmar",
                       {"codigo": dados["confirmar"]}, token)
    assert status == 200
    # o ledger ainda nao tem nada (o upload esta no Chrome)
    with pytest.raises(acoes.Recusa, match="mandado ao TikTok"):
        acoes.preparar("publicar", args, "outro")
    with pytest.raises(acoes.Recusa, match="outra variante de g1 foi mandada"):
        acoes.preparar("publicar", {"id": "g1:build:normal::B", "onde": "ambos"}, "x")
    # outro destino e outra geracao seguem livres
    acoes.preparar("publicar", {"id": "g1:build:normal::B", "onde": "youtube"}, "x")
    acoes.preparar("publicar", {"id": "g2:build:normal:", "onde": "tiktok"}, "x")


def test_em_voo_vence(mundo, monkeypatch):
    acoes.registrar("ap", "publicar", {"id": "g2:build:normal:", "onde": "youtube",
                                       "fonte": "g2"}, "comecei")
    with pytest.raises(acoes.Recusa):
        acoes.preparar("publicar", {"id": "g2:build:normal:", "onde": "youtube"}, "ap")
    from datetime import timedelta
    monkeypatch.setattr(acoes, "_agora",
                        lambda: FORA_DA_GRADE + timedelta(minutes=acoes.EM_VOO_MIN + 1))
    acoes.preparar("publicar", {"id": "g2:build:normal:", "onde": "youtube"}, "ap")


def test_ledger_ilegivel_barra(mundo):
    def quebra(canal="builds"):
        raise OSError("disco")
    mundo.metricas.publicados = quebra
    with pytest.raises(acoes.Recusa, match="registro de publicações"):
        acoes.preparar("publicar", {"id": "g2:build:normal:", "onde": "youtube"}, "ap")


# --------------------------------------------------------- gerar e pausa
def test_gerar_recusa_quando_ja_esta_gerando(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "trava_ocupada", lambda nome: nome == "historias__auto")
    with pytest.raises(acoes.Recusa, match="histórias"):
        acoes.preparar("gerar", {}, "ap")
    monkeypatch.setattr(acoes, "trava_ocupada", lambda nome: False)
    monkeypatch.setattr(acoes, "gerando_builds", lambda: True)
    with pytest.raises(acoes.Recusa, match="build sendo feita"):
        acoes.preparar("gerar", {}, "ap")
    monkeypatch.setattr(acoes, "gerando_builds", lambda: None)
    assert "não consegui conferir" in acoes.preparar("gerar", {}, "ap")["texto"]


def test_parar_explica_o_que_para_e_como_voltar(mundo):
    texto = acoes.preparar("parar", {}, "ap")["texto"]
    assert "termina o job atual" in texto and "Retomar" in texto
    assert "NÃO para" in texto


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


def test_limite_por_hora_conta_so_as_acoes_pesadas_do_aparelho(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "LIMITE_POR_HORA", 2)
    acoes.registrar("ap", "pausar", {}, "ok")
    acoes.registrar("outro", "gerar", {}, "ok")
    acoes.registrar("ap", "gerar", {}, "falhou", ok=False)
    acoes.registrar("ap", "gerar", {}, "ok")
    acoes.preparar("gerar", {}, "ap")
    acoes.registrar("ap", "publicar", {}, "ok")
    with pytest.raises(acoes.Recusa, match="limite"):
        acoes.preparar("gerar", {}, "ap")
    acoes.preparar("pausar", {"alvo": "tudo"}, "ap")        # pausa nao conta


# ------------------------------------------------------------ servidor
@pytest.fixture
def servidor(mundo):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True, com_acoes=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _pedir(srv, metodo, caminho, corpo=None, token=None, tipo="application/json"):
    porta = srv.server_address[1]
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
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
    status, _ = _pedir(servidor, "POST", "/api/acao", {"acao": "parar"})
    assert status == 401
    status, _ = _pedir(servidor, "POST", "/api/acao/confirmar", {"codigo": "x"})
    assert status == 401
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
    assert mundo.avisos and mundo.avisos[0][0] == linha["aparelho"]

    status, dados = _pedir(servidor, "GET", "/api/acoes", token=token)
    assert dados["ligadas"] and "digen" in dados["alvos"]


def test_parar_so_executa_na_confirmacao_e_uma_vez(servidor, mundo):
    token = _token()
    status, dados = _pedir(servidor, "POST", "/api/acao", {"acao": "parar"}, token)
    assert status == 200 and "confirmar" in dados and "Retomar" in dados["texto"]
    assert mundo.controle.chamadas == []                  # ainda nada

    codigo = dados["confirmar"]
    status, dados = _pedir(servidor, "POST", "/api/acao/confirmar",
                           {"codigo": codigo}, token)
    assert status == 200 and mundo.controle.chamadas == [("parar", "pelo app")]
    status, _ = _pedir(servidor, "POST", "/api/acao/confirmar", {"codigo": codigo}, token)
    assert status == 404
    assert len(mundo.controle.chamadas) == 1


def test_confirmacao_de_outro_aparelho_nao_vale_nem_queima(servidor, mundo):
    dono, intruso = _token(), _token()
    _, dados = _pedir(servidor, "POST", "/api/acao", {"acao": "gerar"}, dono)
    codigo = dados["confirmar"]
    status, _ = _pedir(servidor, "POST", "/api/acao/confirmar", {"codigo": codigo}, intruso)
    assert status == 404 and mundo.comandos.rodados == []
    status, _ = _pedir(servidor, "POST", "/api/acao/confirmar", {"codigo": codigo}, dono)
    assert status == 200 and mundo.comandos.rodados == [["gerar"]]


def test_confirmacao_vencida(servidor, mundo, monkeypatch):
    token = _token()
    _, dados = _pedir(servidor, "POST", "/api/acao", {"acao": "gerar"}, token)
    agora = acoes.time.time()
    monkeypatch.setattr(acoes.time, "time", lambda: agora + acoes.CONFIRMAR_VALE_S + 1)
    status, _ = _pedir(servidor, "POST", "/api/acao/confirmar",
                       {"codigo": dados["confirmar"]}, token)
    assert status == 404 and mundo.comandos.rodados == []


def test_guarda_reavaliada_na_confirmacao(servidor, mundo):
    token = _token()
    args = {"id": "g2:build:normal:", "onde": "youtube"}
    _, dados = _pedir(servidor, "POST", "/api/acao", {"acao": "publicar", "args": args}, token)
    # nos 60 s, a grade publicou o mesmo video
    mundo.metricas.linhas = [{"video_id": "g2:build:normal:", "plataforma": "youtube",
                              "publicado": True, "titulo": "Build Dois"}]
    status, dados = _pedir(servidor, "POST", "/api/acao/confirmar",
                           {"codigo": dados["confirmar"]}, token)
    assert status == 409 and "já saiu" in dados["erro"]
    assert mundo.comandos.rodados == []


def test_args_ficam_congelados_no_primeiro_passo(servidor, mundo):
    token = _token()
    _, dados = _pedir(servidor, "POST", "/api/acao",
                      {"acao": "publicar",
                       "args": {"id": "g2:build:normal:", "onde": "youtube"}}, token)
    # o segundo passo nao aceita trocar o video
    status, _ = _pedir(servidor, "POST", "/api/acao/confirmar",
                       {"codigo": dados["confirmar"],
                        "args": {"id": "g5:build:normal:", "onde": "ambos"}}, token)
    assert status == 200
    assert mundo.comandos.rodados == [["python", "main.py", "publicar",
                                       "g2:build:normal:", "--youtube"]]
    assert "g5" not in (mundo.tmp / "acoes.jsonl").read_text(encoding="utf-8")


def test_recusa_volta_409_com_motivo(servidor, mundo):
    status, dados = _pedir(servidor, "POST", "/api/acao",
                           {"acao": "publicar",
                            "args": {"id": "g3:build:normal:", "onde": "youtube"}},
                           _token())
    assert status == 409 and "pendência" in dados["erro"]


def test_codigo_inventado_conta_como_chute(servidor, mundo, monkeypatch):
    monkeypatch.setattr(api_http, "FALHAS_MAX", 2)
    token = _token()
    for _ in range(2):
        status, _ = _pedir(servidor, "POST", "/api/acao/confirmar",
                           {"codigo": "inventado"}, token)
        assert status == 404
    # token valido continua lendo (o bloqueio e so para chute)
    status, _ = _pedir(servidor, "GET", "/api/estado", token=token)
    assert status == 200


def test_escapa_markdown_do_telegram():
    assert acoes._escapar_markdown("g_1 *x* `y` [z]") == "g\\_1 \\*x\\* \\`y\\` \\[z]"
