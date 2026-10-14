"""O launcher nunca mais grava por cima do banco a lista que leu ao abrir.

BLD-1 da auditoria profunda (14/10/2026). A API do banco so sabia "troque a
lista inteira": o launcher aberto mandava ao disco a lista que tinha em
memoria, e duas coisas se perdiam.

1. O personagem que a roleta inseriu DEPOIS que a aba abriu (prova da
   auditoria: 143 -> roleta -> 144 -> salvar no launcher -> 143).
2. Todo campo que o modelo nao conhece: ``genero`` de 71 personagens,
   ``tipo_projetil``/``velocidade_projetil`` de 19 armas, ``tipo_orbital`` de
   18, mais ruido de ponto flutuante em ``tamanho``/``critico``.

O contrato que fica: ler, mesclar e gravar numa trava so; registro que nao
mudou vai ao disco igual, byte a byte; lista velha e recusada com
``ListaDesatualizada`` SEM gravar nada.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from neural_fights.data import database
from neural_fights.tools import gerador_database

PACOTE = Path(database.DATA_DIR)


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    """Banco descartavel com o catalogo empacotado; nunca o banco real."""
    shutil.copyfile(PACOTE / "armas.json", tmp_path / "armas.json")
    shutil.copyfile(PACOTE / "personagens.json", tmp_path / "personagens.json")
    monkeypatch.setenv(database.RUNTIME_DATA_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(database, "ARQUIVO_ARMAS_RUNTIME", str(tmp_path / "armas.json"))
    monkeypatch.setattr(database, "ARQUIVO_CHARS_RUNTIME", str(tmp_path / "personagens.json"))
    return tmp_path


def _ler(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8"))


def _novo_par(runtime: Path, sufixo: str):
    """Arma + personagem validos, copiados do catalogo, com nome novo."""
    arma = dict(_ler(runtime / "armas.json")[0])
    personagem = dict(_ler(runtime / "personagens.json")[0])
    arma["nome"] = f"Arma da Roleta {sufixo}"
    personagem["nome"] = f"Lutador da Roleta {sufixo}"
    personagem["nome_arma"] = arma["nome"]
    return arma, personagem


def _com_campos_desconhecidos(runtime: Path):
    """Poe no disco o que o banco real tem e o modelo nao conhece."""
    armas = _ler(runtime / "armas.json")
    chars = _ler(runtime / "personagens.json")
    armas[0]["tipo_projetil"] = "faca"
    armas[0]["velocidade_projetil"] = 17.5
    chars[0]["genero"] = "f"
    chars[1]["genero"] = "m"
    database.salvar_database(armas, chars)


def test_lista_velha_e_recusada_e_o_personagem_da_roleta_fica(runtime):
    lista = database.carregar_personagens()  # o launcher abre
    arma, personagem = _novo_par(runtime, "A")
    gerador_database.salvar_database([arma], [personagem], substituir=False)  # a roleta insere
    antes = (runtime / "personagens.json").read_bytes()

    with pytest.raises(database.ListaDesatualizada):
        database.salvar_lista_chars(lista)  # o launcher salva a lista velha

    assert (runtime / "personagens.json").read_bytes() == antes, "nada podia ser gravado"
    nomes = {p["nome"] for p in _ler(runtime / "personagens.json")}
    assert "Lutador da Roleta A" in nomes


def test_arma_da_roleta_tambem_nao_some_pela_aba_armas(runtime):
    lista = database.carregar_armas()
    arma, personagem = _novo_par(runtime, "B")
    gerador_database.salvar_database([arma], [personagem], substituir=False)
    with pytest.raises(database.ListaDesatualizada):
        database.salvar_lista_armas(lista)
    assert "Arma da Roleta B" in {a["nome"] for a in _ler(runtime / "armas.json")}


def test_salvar_sem_mudanca_deixa_o_disco_identico(runtime):
    _com_campos_desconhecidos(runtime)
    armas_antes = (runtime / "armas.json").read_bytes()
    chars_antes = (runtime / "personagens.json").read_bytes()

    database.salvar_lista_chars(database.carregar_personagens())
    database.salvar_lista_armas(database.carregar_armas())

    assert (runtime / "personagens.json").read_bytes() == chars_antes
    assert (runtime / "armas.json").read_bytes() == armas_antes


def test_editar_um_personagem_preserva_genero_e_nao_mexe_nos_outros(runtime):
    _com_campos_desconhecidos(runtime)
    antes = _ler(runtime / "personagens.json")
    lista = database.carregar_personagens()
    lista[0].forca = lista[0].forca + 1.0

    database.salvar_lista_chars(lista)

    depois = _ler(runtime / "personagens.json")
    assert depois[0]["genero"] == "f"
    assert depois[0]["forca"] == antes[0]["forca"] + 1.0
    assert {k: v for k, v in depois[0].items() if k != "forca"} == {
        k: v for k, v in antes[0].items() if k != "forca"
    }
    assert depois[1:] == antes[1:], "registro intocado vai igual ao disco"


def test_apagar_e_explicito_e_deixa_copia(runtime):
    lista = database.carregar_personagens()
    alvo = lista[-1].nome
    restante = [p for p in lista if p.nome != alvo]

    database.salvar_lista_chars(restante, apagar=[alvo])

    assert alvo not in {p["nome"] for p in _ler(runtime / "personagens.json")}
    copias = [d for d in runtime.iterdir() if d.name.startswith("_backup-")]
    assert len(copias) == 1
    assert alvo in {p["nome"] for p in _ler(copias[0] / "personagens.json")}


def test_criar_nome_que_outro_processo_ja_gravou_e_recusado(runtime):
    """A 'criacao' no launcher nao pode virar edicao por cima da roleta."""
    lista = database.carregar_personagens()
    arma, personagem = _novo_par(runtime, "C")
    gerador_database.salvar_database([arma], [personagem], substituir=False)
    # o launcher (lista velha) cria um campeao com o MESMO nome da roleta
    import copy
    criado = copy.copy(lista[0])
    criado.nome = personagem["nome"]
    with pytest.raises(database.ListaDesatualizada):
        database.salvar_lista_chars([*lista, criado], novos=[criado.nome])
    gravado = next(p for p in _ler(runtime / "personagens.json") if p["nome"] == personagem["nome"])
    assert gravado["nome_arma"] == arma["nome"]


def test_atualizar_arma_preserva_campos_que_o_modelo_nao_conhece(runtime):
    _com_campos_desconhecidos(runtime)
    arma = database.carregar_armas()[0]
    arma.dano_base = arma.dano_base + 1.0

    database.atualizar_arma(arma.nome, arma)

    gravada = _ler(runtime / "armas.json")[0]
    assert gravada["tipo_projetil"] == "faca"
    assert gravada["velocidade_projetil"] == 17.5


def test_launcher_rele_e_reaplica_quando_a_roleta_inseriu(runtime):
    """O caminho do botao: lista velha, roleta insere, salvar ainda funciona."""
    from neural_fights.ui import view_chars

    controller = SimpleNamespace(lista_personagens=database.carregar_personagens())

    def recarregar():
        controller.lista_personagens = database.carregar_personagens()

    controller.recarregar_dados = recarregar
    tela = object.__new__(view_chars.TelaPersonagens)
    tela.controller = controller
    tela.atualizar_dados = lambda: None

    arma, personagem = _novo_par(runtime, "D")
    gerador_database.salvar_database([arma], [personagem], substituir=False)

    alvo = controller.lista_personagens[0].nome

    def aplicar(lista):
        for p in lista:
            if p.nome == alvo:
                p.mana = p.mana + 0.5
        return lista

    with patch.object(view_chars.messagebox, "showwarning") as aviso:
        assert tela._gravar_lista(aplicar) is True
    aviso.assert_not_called()

    gravados = {p["nome"]: p for p in _ler(runtime / "personagens.json")}
    assert "Lutador da Roleta D" in gravados, "o personagem da roleta sobreviveu"
    original = {p["nome"]: p for p in _ler(PACOTE / "personagens.json")}
    assert gravados[alvo]["mana"] == original[alvo]["mana"] + 0.5
