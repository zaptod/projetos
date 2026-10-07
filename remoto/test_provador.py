# -*- coding: utf-8 -*-
"""O provador do Ateliê: o "jogo de vestir" dos lutadores (06/10/2026).

Decisão builds/sprites-guarda-roupa: cada peça é uma coleção de variantes;
cada lutador recebe um sorteio fixo; o guarda-roupa (`partes/guarda_roupa.json`)
fixa escolhas. Aqui a API do provador é conferida contra o espelho Python do
palco (`manifesto_sprites.resolver_no_disco`, o mesmo `PartesLutador` que
`palco/testes/test_sorteio_variantes.py` compara com o Godot): o que o app
mostra é o que a luta usa.

Tudo em pasta temporária: biblioteca, banco de personagens, LOCALAPPDATA.
"""
from __future__ import annotations

import io
import json
import threading
import time
from pathlib import Path
from urllib.parse import quote

import pytest
from PIL import Image

from neural_fights.tools import manifesto_sprites
from remoto import api_http
from remoto.test_api_http import (_parear, _pedir, _png_rgba, _rota_slot, biblioteca_sprites,  # noqa: F401
                                  mundo, servidor)

PERSONAGENS = [
    {"nome": "Lucius a Sombria", "classe": "Guerreiro (Força Bruta)", "cor_r": 216, "cor_g": 54, "cor_b": 69},
    {"nome": "Júlia a Abençoada", "classe": "Berserker (Fúria)", "cor_r": 40, "cor_g": 200, "cor_b": 90},
    {"nome": "Achilles", "classe": "Monge (Chi)", "cor_r": 10, "cor_g": 20, "cor_b": 250},
]
OLHOS = "lutador/olhos/comum/_/neutro"
BOCA = "lutador/boca/comum/_/neutro"
PELE = "lutador/pele/comum/_/base"


@pytest.fixture
def provador(servidor, biblioteca_sprites, mundo, monkeypatch):  # noqa: F811
    arquivo = mundo.tmp / "personagens.json"
    arquivo.write_text(json.dumps(PERSONAGENS, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(api_http, "ARQUIVO_PERSONAGENS", arquivo)
    monkeypatch.setattr(api_http, "_PERSONAGENS", {"chave": None, "lista": [], "por_id": {}})
    monkeypatch.setattr(api_http, "_PREVIAS_GODOT", {})
    monkeypatch.setattr(api_http, "_PEDIDOS_GODOT", {})
    monkeypatch.setattr(api_http, "_FILA_GODOT", [])
    monkeypatch.setattr(api_http, "_GODOT_OCUPADO", {"alvo": None})
    monkeypatch.setenv("NEURAL_FIGHTS_RUNTIME_DIR", str(mundo.tmp / "runtime"))
    # O "Ver no Godot" monta a biblioteca temporaria em runtime_dir(), que e o
    # LOCALAPPDATA: sem isto o teste escrevia no %LOCALAPPDATA% de verdade
    # (06/10, achado na conferencia: previas_sprites/provador/ no PC real).
    monkeypatch.setenv("LOCALAPPDATA", str(mundo.tmp / "localappdata"))
    token = _parear(servidor)
    servidor.RequestHandlerClass.estado.com_acoes = True
    return {"srv": servidor, "token": token, "raiz": biblioteca_sprites}


def _nova(p, slot, cor):
    resposta, bruto = _pedir(p["srv"], "POST", _rota_slot(slot, "anexar"),
                             {"imagem": _png_rgba(cor), "opcoes": {"nova": True}}, p["token"])
    assert resposta.status == 200, bruto


def _get(p, caminho):
    resposta, bruto = _pedir(p["srv"], "GET", caminho, token=p["token"])
    return resposta, bruto


def _provador(p, lutador, escolha="", expressao="neutro"):
    resposta, bruto = _get(p, f"/api/sprites/provador?lutador={quote(lutador)}&expressao={expressao}"
                              f"&escolha={quote(escolha)}")
    assert resposta.status == 200, bruto
    return json.loads(bruto)


def _post(p, acao, corpo):
    resposta, bruto = _pedir(p["srv"], "POST", f"/api/sprites/provador/{acao}", corpo, p["token"])
    return resposta.status, json.loads(bruto)


def _peca(dados, parte):
    return next(x for x in dados["pecas"] if x["parte"] == parte)


def _guarda(p):
    arquivo = p["raiz"] / "partes" / "guarda_roupa.json"
    return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else None


def _do_palco(p, parte, nome, classe):
    """O que o palco usaria (espelho Python do PartesLutador, lendo o disco)."""
    return manifesto_sprites.resolver_no_disco(p["raiz"], parte, nome, classe, "neutro")


def test_lista_de_lutadores_com_nome_humano_classe_e_exemplos(provador):
    inicio = time.perf_counter()
    resposta, bruto = _get(provador, "/api/sprites/provador/lutadores")
    gasto = time.perf_counter() - inicio
    assert resposta.status == 200 and gasto < 0.3 and len(bruto) < 60_000, (gasto, len(bruto))
    dados = json.loads(bruto)
    por_nome = {lut["nome"]: lut for lut in dados["lutadores"]}
    assert por_nome["Júlia a Abençoada"]["id"] == "julia_a_abencoada"
    assert por_nome["Júlia a Abençoada"]["classe_nome"] == "Berserker (Fúria)"
    assert por_nome["Lucius a Sombria"]["classe"] == "guerreiro_forca_bruta"
    assert len(dados["classes"]) == 16 and len(dados["exemplos"]) == 16
    assert dados["exemplos"][0]["nome"] == "Lutador de exemplo"
    # lutador desconhecido: frase em portugues, sem stack
    resposta, bruto = _get(provador, "/api/sprites/provador?lutador=ninguem")
    assert resposta.status == 404 and json.loads(bruto)["erro"] == "lutador não encontrado"


def test_combinacao_atual_e_a_mesma_que_o_palco_usa(provador):
    for cor in ((10, 0, 0, 255), (20, 0, 0, 255), (30, 0, 0, 255)):
        _nova(provador, OLHOS, cor)
    for cor in ((0, 10, 0, 255), (0, 20, 0, 255)):
        _nova(provador, BOCA, cor)
    for p in PERSONAGENS:
        ident = manifesto_sprites.slug(p["nome"])
        dados = _provador(provador, ident)
        assert dados["lutador"]["nome"] == p["nome"] and dados["pode_fixar"] is True
        for parte in ("olhos", "boca"):
            peca = _peca(dados, parte)
            palco = _do_palco(provador, parte, p["nome"], p["classe"])
            assert peca["atual"] == palco["variante"], (p["nome"], parte)
            assert peca["situacao"] == "sorteio" and peca["total"] == (3 if parte == "olhos" else 2)
            assert peca["ordem"][peca["indice"] - 1] == peca["atual"]
            assert peca["dono"] == "peça comum (todos os lutadores)"
    assert "Pele (o corpo)" in dados["sem_desenho"]


def test_setas_fixar_recarregar_e_voltar_ao_sorteio(provador):
    for cor in ((10, 0, 0, 255), (20, 0, 0, 255), (30, 0, 0, 255)):
        _nova(provador, OLHOS, cor)
    ident, nome, classe = "lucius_a_sombria", "Lucius a Sombria", "Guerreiro (Força Bruta)"
    sorteada = _peca(_provador(provador, ident), "olhos")["atual"]
    outra = next(v for v in ("v01", "v02", "v03") if v != sorteada)
    # A seta: so na tela (experimento); o disco nao muda.
    dados = _provador(provador, ident, f"olhos:{outra}")
    assert _peca(dados, "olhos")["situacao"] == "experimento" and dados["escolha"] == {"olhos": outra}
    assert _guarda(provador) is None
    # Fixar grava o guarda-roupa (atomico, LF, chaves em ordem) no formato do palco.
    status, dados = _post(provador, "fixar", {"lutador": ident, "parte": "olhos",
                                               "escolha": {"olhos": outra}, "expressao": "neutro"})
    assert status == 200 and _peca(dados, "olhos")["situacao"] == "fixada" and dados["escolha"] == {}
    assert "Fixado em Lucius a Sombria" in dados["aviso"]
    assert _guarda(provador) == {ident: {"olhos": outra}}
    assert b"\r\n" not in (provador["raiz"] / "partes" / "guarda_roupa.json").read_bytes()
    assert not list((provador["raiz"] / "partes").glob(".*.tmp"))
    # "Recarregar": sem escolha nenhuma a tela continua fixada, e o palco concorda.
    dados = _provador(provador, ident)
    assert _peca(dados, "olhos")["atual"] == outra and _peca(dados, "olhos")["situacao"] == "fixada"
    assert dados["lutador"]["fixadas"] == 1
    assert _do_palco(provador, "olhos", nome, classe)["variante"] == outra
    lista = json.loads(_get(provador, "/api/sprites/provador/lutadores")[1])["lutadores"]
    assert next(lut for lut in lista if lut["id"] == ident)["fixadas"] == 1
    # Voltar ao sorteio (a peca): o arquivo perde a escolha, o palco volta a sortear.
    status, dados = _post(provador, "desfixar", {"lutador": ident, "parte": "olhos"})
    assert status == 200 and _peca(dados, "olhos")["situacao"] == "sorteio"
    assert _peca(dados, "olhos")["atual"] == sorteada == _do_palco(provador, "olhos", nome, classe)["variante"]
    assert _guarda(provador) == {}


def test_fixar_tudo_e_tudo_ao_sorteio(provador):
    for cor in ((10, 0, 0, 255), (20, 0, 0, 255)):
        _nova(provador, OLHOS, cor)
        _nova(provador, BOCA, (0, cor[0], 0, 255))
    _nova(provador, PELE, (200, 200, 200, 255))           # um desenho so: nao entra no "tudo"
    ident = "achilles"
    status, dados = _post(provador, "fixar", {"lutador": ident, "escolha": "olhos:v02,boca:v01"})
    assert status == 200 and "Combinação fixada (2 peças)" in dados["aviso"]
    assert _guarda(provador) == {ident: {"boca": "v01", "olhos": "v02"}}
    status, dados = _post(provador, "desfixar", {"lutador": ident})
    assert status == 200 and _guarda(provador) == {}
    assert all(x["situacao"] == "sorteio" for x in dados["pecas"])


def test_sortear_e_so_na_tela_e_muda_so_a_peca_pedida(provador):
    for cor in ((10, 0, 0, 255), (20, 0, 0, 255), (30, 0, 0, 255)):
        _nova(provador, OLHOS, cor)
    for cor in ((0, 10, 0, 255), (0, 20, 0, 255)):
        _nova(provador, BOCA, cor)
    provador["srv"].RequestHandlerClass.estado.com_acoes = False    # sortear nao grava nada
    ident = "achilles"
    antes = _provador(provador, ident)
    status, dados = _post(provador, "sortear", {"lutador": ident, "parte": "olhos"})
    assert status == 200 and "toque em Fixar" in dados["aviso"]
    assert _peca(dados, "olhos")["atual"] != _peca(antes, "olhos")["atual"]
    assert _peca(dados, "boca")["atual"] == _peca(antes, "boca")["atual"]
    status, tudo = _post(provador, "sortear", {"lutador": ident, "escolha": dados["escolha"]})
    assert status == 200
    for parte in ("olhos", "boca"):
        assert _peca(tudo, parte)["atual"] != _peca(dados, parte)["atual"]
    assert _guarda(provador) is None
    # Fixar e desfixar gravam: sem --acoes, recusa.
    status, erro = _post(provador, "fixar", {"lutador": ident, "parte": "olhos"})
    assert status == 403 and "ações" in erro["erro"]


def test_lutador_de_exemplo_experimenta_mas_nao_fixa(provador):
    for cor in ((10, 0, 0, 255), (20, 0, 0, 255)):
        _nova(provador, "lutador/olhos/classe/berserker_furia/neutro", cor)
    dados = _provador(provador, "exemplo-berserker_furia")
    assert dados["pode_fixar"] is False and dados["lutador"]["classe_nome"] == "Berserker (Fúria)"
    assert _peca(dados, "olhos")["dono"] == "peça da classe Berserker (Fúria)"
    # Sem personagem, o sorteio e o da classe (o mesmo da folha do Godot sem --personagem).
    assert _peca(dados, "olhos")["atual"] == _do_palco(provador, "olhos", "", "berserker_furia")["variante"]
    status, erro = _post(provador, "fixar", {"lutador": "exemplo-berserker_furia", "parte": "olhos"})
    assert status == 400 and "lutador de exemplo" in erro["erro"]
    assert _guarda(provador) is None


def test_guarda_roupa_ilegivel_nunca_e_sobrescrito(provador):
    for cor in ((10, 0, 0, 255), (20, 0, 0, 255)):
        _nova(provador, OLHOS, cor)
    arquivo = provador["raiz"] / "partes" / "guarda_roupa.json"
    arquivo.write_text("{ isto nao e json", encoding="utf-8")
    dados = _provador(provador, "achilles")                     # a tela abre (sorteio)
    assert _peca(dados, "olhos")["situacao"] == "sorteio"
    status, erro = _post(provador, "fixar", {"lutador": "achilles", "parte": "olhos"})
    assert status == 409 and "nada foi mudado" in erro["erro"]
    assert arquivo.read_text(encoding="utf-8") == "{ isto nao e json"


def test_fixar_ao_mesmo_tempo_nao_perde_escolha(provador):
    """Dois toques quase juntos (dois lutadores): o arquivo final tem os dois."""
    for cor in ((10, 0, 0, 255), (20, 0, 0, 255)):
        _nova(provador, OLHOS, cor)
    erros = []

    def fixar(ident):
        status, _ = _post(provador, "fixar", {"lutador": ident, "parte": "olhos", "escolha": {"olhos": "v02"}})
        if status != 200:
            erros.append(status)
    fios = [threading.Thread(target=fixar, args=(i,)) for i in ("achilles", "lucius_a_sombria", "julia_a_abencoada")]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join()
    assert not erros
    assert _guarda(provador) == {i: {"olhos": "v02"} for i in ("achilles", "lucius_a_sombria", "julia_a_abencoada")}


def test_previa_usa_a_escolha_e_tinge_a_pele_com_a_cor_do_lutador(provador):
    _nova(provador, PELE, (255, 255, 255, 255))               # mascara branca: vira a cor dele
    _nova(provador, OLHOS, (255, 0, 0, 255))
    _nova(provador, OLHOS, (0, 0, 255, 255))

    def pixel(escolha, ponto):
        dados = _provador(provador, "achilles", escolha)
        resposta, bruto = _get(provador, dados["previa"])
        assert resposta.status == 200 and resposta.getheader("X-Previa-Pecas") == "2"
        return Image.open(io.BytesIO(bruto)).getpixel(ponto)[:3]
    # os olhos de teste cobrem tudo: a cor da previa e a da variante escolhida
    assert pixel("olhos:v01", (256, 256)) == (255, 0, 0)
    assert pixel("olhos:v02", (256, 256)) == (0, 0, 255)
    # sem olhos (variante so com outra carinha nao existe aqui): a pele sozinha
    (provador["raiz"] / "partes/lutador/olhos/comum/_/v01/neutro.png").unlink()
    (provador["raiz"] / "partes/lutador/olhos/comum/_/v02/neutro.png").unlink()
    api_http._indice_sprites(mudou=OLHOS)
    dados = _provador(provador, "achilles")
    resposta, bruto = _get(provador, dados["previa"])
    assert Image.open(io.BytesIO(bruto)).getpixel((256, 256))[:3] == (10, 20, 250)   # cor do Achilles


def test_miniatura_de_cada_variante(provador):
    _nova(provador, OLHOS, (255, 0, 0, 255))
    _nova(provador, OLHOS, (0, 255, 0, 255))
    dados = _provador(provador, "achilles")
    cores = []
    for variante, url in _peca(dados, "olhos")["imagens"].items():
        resposta, bruto = _get(provador, url)
        assert resposta.status == 200 and max(Image.open(io.BytesIO(bruto)).size) == 160
        cores.append(Image.open(io.BytesIO(bruto)).getpixel((80, 80))[:3])
    assert cores == [(255, 0, 0), (0, 255, 0)]
    # a galeria do cartao no painel de anexo usa o lugar + ?variante=
    for variante, cor in (("v01", (255, 0, 0)), ("v02", (0, 255, 0))):
        resposta, bruto = _get(provador, _rota_slot(OLHOS, "imagem") + f"?variante={variante}")
        assert resposta.status == 200 and Image.open(io.BytesIO(bruto)).getpixel((80, 80))[:3] == cor
    # a carinha "furia" dentro da v02 cai na neutra dela (a mesma regra da luta)
    resposta, bruto = _get(provador, _rota_slot("lutador/olhos/comum/_/furia", "imagem") + "?variante=v02")
    assert resposta.status == 200 and Image.open(io.BytesIO(bruto)).getpixel((80, 80))[:3] == (0, 255, 0)
    resposta, _ = _get(provador, _rota_slot(OLHOS, "imagem") + "?variante=v09")
    assert resposta.status == 404


def test_apagar_variante_fixada_volta_ao_sorteio_e_desfazer_devolve(provador):
    for cor in ((10, 0, 0, 255), (20, 0, 0, 255), (30, 0, 0, 255)):
        _nova(provador, OLHOS, cor)
    # Achilles fixa a v02 COMUM; Julia (Berserker) tem olhos de classe: a v02
    # comum nao e a dela, mesmo com o mesmo nome no guarda-roupa.
    _nova(provador, "lutador/olhos/classe/berserker_furia/neutro", (1, 1, 1, 255))
    _nova(provador, "lutador/olhos/classe/berserker_furia/neutro", (2, 2, 2, 255))
    assert _post(provador, "fixar", {"lutador": "achilles", "parte": "olhos", "escolha": "olhos:v02"})[0] == 200
    assert _post(provador, "fixar", {"lutador": "julia_a_abencoada", "parte": "olhos",
                                     "escolha": "olhos:v02"})[0] == 200
    rota = _rota_slot(OLHOS, "variante/v02/apagar")
    provador["srv"].RequestHandlerClass.estado.com_acoes = False
    assert _pedir(provador["srv"], "POST", rota, {}, provador["token"])[0].status == 403
    provador["srv"].RequestHandlerClass.estado.com_acoes = True
    resposta, bruto = _pedir(provador["srv"], "POST", rota, {}, provador["token"])
    dados = json.loads(bruto)
    assert resposta.status == 200, dados
    assert dados["mensagem"].startswith("A variante 2 de olhos foi apagada (todas as carinhas dela).")
    assert "Achilles usava esta variante fixa e voltou ao sorteio." in dados["mensagem"]
    assert dados["voltaram_ao_sorteio"] == ["Achilles"]
    assert dados["slot"]["variantes"] == ["v01", "v03"] and dados["slot"]["variantes_apagadas"] == 1
    assert _guarda(provador) == {"julia_a_abencoada": {"olhos": "v02"}}
    assert _peca(_provador(provador, "achilles"), "olhos")["situacao"] == "sorteio"
    # o palco tambem nao ve a pasta apagada
    assert _do_palco(provador, "olhos", "Achilles", "Monge (Chi)")["variante"] in ("v01", "v03")
    # Desfazer: a v02 volta com o nome dela e a escolha fixa volta ao Achilles.
    resposta, bruto = _pedir(provador["srv"], "POST", _rota_slot(OLHOS, "variante/desfazer"), {},
                             provador["token"])
    dados = json.loads(bruto)
    assert resposta.status == 200 and "voltou para Achilles" in dados["mensagem"]
    assert dados["slot"]["variantes"] == ["v01", "v02", "v03"] and dados["slot"]["variantes_apagadas"] == 0
    assert _guarda(provador)["achilles"] == {"olhos": "v02"}
    arquivo = provador["raiz"] / "partes/lutador/olhos/comum/_/v02/neutro.png"
    assert Image.open(arquivo).getpixel((512, 512))[0] == 20
    assert not (provador["raiz"] / "partes/lutador/olhos/comum/_/v02/_apagada.json").exists()
    resposta, bruto = _pedir(provador["srv"], "POST", _rota_slot(OLHOS, "variante/desfazer"), {},
                             provador["token"])
    assert resposta.status == 404 and "não há variante apagada" in json.loads(bruto)["erro"]


def test_galeria_conta_variante_como_o_palco(provador):
    """Pasta vNN so com uma carinha que a peca nao tem (base.png nos olhos)
    nao e variante para o palco (`dono_da_parte`): a galeria tambem nao a mostra."""
    for cor in ((10, 0, 0, 255), (20, 0, 0, 255)):
        _nova(provador, OLHOS, cor)
    estranha = provador["raiz"] / "partes/lutador/olhos/comum/_/v09"
    estranha.mkdir()
    Image.new("RGBA", (1024, 1024), (0, 0, 0, 0)).save(estranha / "base.png")
    api_http._indice_sprites(mudou=OLHOS)
    resposta, bruto = _get(provador, "/api/sprites/modulares?grupo=lutador&alvo=_")
    assert next(s for s in json.loads(bruto)["slots"] if s["id"] == OLHOS)["variantes"] == ["v01", "v02"]
    assert _peca(_provador(provador, "achilles"), "olhos")["ordem"] == ["v01", "v02"]


def test_desfazer_com_o_nome_ocupado_usa_o_proximo_livre(provador):
    for cor in ((10, 0, 0, 255), (20, 0, 0, 255)):
        _nova(provador, OLHOS, cor)
    assert _pedir(provador["srv"], "POST", _rota_slot(OLHOS, "variante/v02/apagar"), {},
                  provador["token"])[0].status == 200
    _nova(provador, OLHOS, (99, 0, 0, 255))                   # a nova pega o v02 livre
    resposta, bruto = _pedir(provador["srv"], "POST", _rota_slot(OLHOS, "variante/desfazer"), {},
                             provador["token"])
    assert resposta.status == 200
    assert json.loads(bruto)["slot"]["variantes"] == ["v01", "v02", "v03"]
    base = provador["raiz"] / "partes/lutador/olhos/comum/_"
    assert Image.open(base / "v02/neutro.png").getpixel((512, 512))[0] == 99
    assert Image.open(base / "v03/neutro.png").getpixel((512, 512))[0] == 20


def test_ver_no_godot_do_lutador_leva_so_a_combinacao_escolhida(provador, monkeypatch):
    for cor in ((10, 0, 0, 255), (20, 0, 0, 255), (30, 0, 0, 255)):
        _nova(provador, OLHOS, cor)
    _nova(provador, PELE, (200, 200, 200, 255))
    chamadas = []

    def godot(classe, personagem, biblioteca, saida, cor=None):
        variantes = sorted(str(p.relative_to(biblioteca)).replace("\\", "/")
                           for p in Path(biblioteca).rglob("*.png"))
        chamadas.append((classe, personagem, variantes, cor))
        Image.new("RGBA", (6, 6), (len(chamadas), 0, 0, 255)).save(saida)
        return {"estado": "pronta", "arquivo": str(saida)}
    monkeypatch.setattr(api_http, "_godot_folha", godot)
    monkeypatch.setattr(api_http, "GODOT_PREVIA", Path(__file__))
    dados = _provador(provador, "lucius_a_sombria", "olhos:v03")
    for _ in range(100):
        resposta, bruto = _get(provador, dados["godot"])
        if resposta.status == 200:
            break
        assert resposta.status == 202
        time.sleep(0.05)
    assert resposta.status == 200 and Image.open(io.BytesIO(bruto)).getpixel((0, 0))[0] == 1
    classe, personagem, arquivos, cor = chamadas[0]
    assert classe == "guerreiro_forca_bruta" and personagem == "Lucius a Sombria"
    assert tuple(cor) == (216, 54, 69)          # a folha pinta com a cor DELE (--cor)
    assert arquivos == ["partes/lutador/olhos/comum/_/v03/neutro.png",
                        "partes/lutador/pele/comum/_/v01/base.png"]
    # a biblioteca temporaria do Godot mora na pasta do teste, nunca no PC real
    assert Path(api_http.runtime_dir()).is_relative_to(provador["raiz"].parents[1])
    # mesma combinacao: a folha pronta volta sem rodar o Godot de novo
    assert _get(provador, dados["godot"])[0].status == 200 and len(chamadas) == 1


def test_provador_responde_rapido_e_curto(provador):
    for cor in ((10, 0, 0, 255), (20, 0, 0, 255), (30, 0, 0, 255)):
        _nova(provador, OLHOS, cor)
    _provador(provador, "achilles")
    inicio = time.perf_counter()
    resposta, bruto = _get(provador, "/api/sprites/provador?lutador=achilles&expressao=furia&escolha=olhos:v02")
    gasto = time.perf_counter() - inicio
    assert resposta.status == 200 and gasto < 0.3 and len(bruto) < 60_000, (gasto, len(bruto))
    texto = bruto.decode("utf-8")
    assert "palco" not in texto and "\\\\" not in texto and ":\\" not in texto     # nenhum caminho do PC


def test_miniaturas_das_variantes_ficam_na_mesma_escala():
    """Conferente, 07/10: a v54 recortava cada miniatura no próprio desenho e
    ampliava, então um olho pequeno e um grande saíam do mesmo tamanho. Com
    zona no CONTRATO 2.3, o recorte é a zona: mesma moldura, mesma escala, e o
    olho menor continua menor. Sem zona (pele), segue recortada no desenho."""
    from PIL import ImageDraw

    def olhos(raio):
        imagem = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        caneta = ImageDraw.Draw(imagem)
        for y in (420, 604):
            caneta.ellipse((563 - raio, y - raio, 563 + raio, y + raio), fill=(20, 20, 26, 255))
        return imagem

    grande, pequeno = (Image.open(io.BytesIO(api_http._miniatura_png(olhos(r), parte="olhos"))) for r in (51, 25))
    assert grande.size == pequeno.size and max(grande.size) == 160
    opacos = [sum(1 for a in m.getchannel("A").getdata() if a > 128) for m in (grande, pequeno)]
    assert opacos[1] < 0.4 * opacos[0], opacos
    # a pele (sem zona): recortada no desenho e ampliada
    pele = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    ImageDraw.Draw(pele).ellipse((272, 272, 752, 752), fill=(255, 255, 255, 255))
    mini = Image.open(io.BytesIO(api_http._miniatura_png(pele, parte="pele")))
    assert mini.size == (160, 160) and mini.getpixel((80, 80))[3] == 255 and mini.getpixel((80, 12))[3] == 255
