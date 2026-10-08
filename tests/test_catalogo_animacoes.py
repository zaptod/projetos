"""Contrato do catalogo de animacoes com as definicoes do jogo."""
from __future__ import annotations

import json
from pathlib import Path

from neural_fights.core.skills import SKILL_DB
from neural_fights.data import database
from neural_fights.models.constants import CLASSES_DATA, TIPOS_ARMA
from neural_fights.recording import timeline
from neural_fights.tools import catalogo_animacoes


FIXTURE = Path(__file__).parent / "fixtures" / "corpus_engine"


def _copia_dados(tmp_path: Path) -> tuple[Path, Path, list, list]:
    armas = json.loads((FIXTURE / "armas.json").read_text(encoding="utf-8"))
    personagens = json.loads((FIXTURE / "personagens.json").read_text(encoding="utf-8"))
    arquivo_armas = tmp_path / "armas.json"
    arquivo_personagens = tmp_path / "personagens.json"
    arquivo_armas.write_text(json.dumps(armas, ensure_ascii=False), encoding="utf-8")
    arquivo_personagens.write_text(json.dumps(personagens, ensure_ascii=False), encoding="utf-8")
    return arquivo_armas, arquivo_personagens, armas, personagens


def _catalogo(arquivo_armas: Path, arquivo_personagens: Path) -> dict:
    return catalogo_animacoes.gerar_catalogo(
        arquivo_armas=arquivo_armas, arquivo_personagens=arquivo_personagens
    )


def test_catalogo_e_escalavel_com_copia_dos_dados(tmp_path, monkeypatch):
    arquivo_armas, arquivo_personagens, armas, personagens = _copia_dados(tmp_path)
    classe = "Classe de Teste (Catalogo)"
    skill = "Skill de Teste Catalogo"
    tipo = "Tipo de Teste Catalogo"
    estilo = "Estilo de Teste Catalogo"
    base = _catalogo(arquivo_armas, arquivo_personagens)

    # Uma instancia nova do banco nao cria trabalho de arte novo.
    nova_arma = dict(armas[0])
    nova_arma["nome"] = "Arma de Teste Catalogo"
    novo_personagem = dict(personagens[0])
    novo_personagem.update({"nome": "Lutador de Teste Catalogo", "nome_arma": nova_arma["nome"]})
    arquivo_armas.write_text(json.dumps([*armas, nova_arma], ensure_ascii=False), encoding="utf-8")
    arquivo_personagens.write_text(json.dumps([*personagens, novo_personagem], ensure_ascii=False), encoding="utf-8")
    assert catalogo_animacoes.bytes_catalogo(_catalogo(arquivo_armas, arquivo_personagens)) == \
        catalogo_animacoes.bytes_catalogo(base)

    with monkeypatch.context() as alteracoes:
        alteracoes.setitem(CLASSES_DATA, classe, dict(next(iter(CLASSES_DATA.values()))))
        alteracoes.setitem(TIPOS_ARMA, tipo, {
            "estilos": [estilo], "categoria": "Teste", "geometria": [],
        })
        alteracoes.setattr(database, "LISTA_TIPOS_ARMA", [*database.LISTA_TIPOS_ARMA, tipo])
        alteracoes.setitem(SKILL_DB, skill, {
            "tipo": "PROJETIL", "elemento": "TESTE", "custo": 1, "cooldown": 1,
        })
        arma_de_estilo_novo = dict(nova_arma)
        arma_de_estilo_novo.update({"nome": "Arma de Estilo de Teste", "tipo": tipo,
                                    "estilo": estilo})
        arquivo_armas.write_text(json.dumps([*armas, nova_arma, arma_de_estilo_novo], ensure_ascii=False),
                                 encoding="utf-8")
        expandido = _catalogo(arquivo_armas, arquivo_personagens)
        ids = {peca["id"] for peca in expandido["pecas"]}
        assert f"arma.tipo.{catalogo_animacoes.slug(tipo)}" in ids
        assert f"arma.estilo.{catalogo_animacoes.slug(estilo)}" in ids
        assert f"skill.{catalogo_animacoes.slug(skill)}" in ids
        assert f"classe.{catalogo_animacoes.slug(classe)}" in ids
        assert f"elemento.{catalogo_animacoes.slug('TESTE')}" in ids

    arquivo_armas.write_text(json.dumps([*armas, nova_arma], ensure_ascii=False), encoding="utf-8")
    removido = _catalogo(arquivo_armas, arquivo_personagens)
    ids_removidos = {peca["id"] for peca in removido["pecas"]}
    assert f"arma.tipo.{catalogo_animacoes.slug(tipo)}" not in ids_removidos
    assert f"arma.estilo.{catalogo_animacoes.slug(estilo)}" not in ids_removidos
    assert f"skill.{catalogo_animacoes.slug(skill)}" not in ids_removidos
    assert f"classe.{catalogo_animacoes.slug(classe)}" not in ids_removidos
    assert len(expandido["pecas"]) > len(base["pecas"])
    assert all(not peca["id"].startswith("arma.") or peca["id"].startswith(("arma.tipo.", "arma.estilo."))
               for peca in removido["pecas"])
    assert all(not peca["id"].startswith("lutador.") or peca["id"] in {
        "lutador.corpo", "lutador.rosto.olhos", "lutador.rosto.boca",
        "lutador.rosto.sobrancelhas", "lutador.rosto.detalhe_rosto",
    } for peca in removido["pecas"])


def test_gatilhos_e_estados_da_timeline_estao_cobertos(tmp_path):
    arquivo_armas, arquivo_personagens, _armas, _personagens = _copia_dados(tmp_path)
    catalogo = _catalogo(arquivo_armas, arquivo_personagens)
    assert catalogo_animacoes.validar_catalogo(catalogo) == []
    conhecidos = catalogo_animacoes.gatilhos_do_jogo()
    gatilhos = {
        animacao["gatilho"]
        for peca in catalogo["pecas"]
        for estado in peca["estados"]
        for animacao in estado["animacoes"]
    }
    sem_animacao = {item["id"] for item in catalogo["sem_animacao"]}
    assert gatilhos <= conhecidos
    assert set(catalogo_animacoes._eventos_da_timeline()) <= gatilhos | sem_animacao
    assert set(timeline.FLAGS) <= gatilhos | sem_animacao


def test_hierarquia_e_estados_reais_do_atelie(tmp_path):
    arquivo_armas, arquivo_personagens, _armas, _personagens = _copia_dados(tmp_path)
    pecas = {peca["id"]: peca for peca in _catalogo(arquivo_armas, arquivo_personagens)["pecas"]}
    olhos = pecas["lutador.rosto.olhos"]
    animacoes_medo = {animacao["id"]: animacao for estado in olhos["estados"] if estado["id"] == "panico"
                       for animacao in estado["animacoes"]}
    assert animacoes_medo["piscar"]["intervalo_ocioso"] == {
        "min_s": 2, "max_s": 5, "semente": "slot+expressao",
    }
    assert {estado["id"] for estado in pecas["lutador.corpo"]["estados"]} == {"parado", "dano", "ko"}
    assert {estado["id"] for estado in pecas["arma.tipo.arco"]["estados"]} == {
        "parada", "puxar", "disparo",
    }
    assert {estado["id"] for estado in pecas["efeito.projetil"]["estados"]} == {
        "surgir", "voando", "impacto", "sumir",
    }


def test_determinismo_ids_e_verificacao_de_saida(tmp_path):
    arquivo_armas, arquivo_personagens, _armas, _personagens = _copia_dados(tmp_path)
    primeiro = _catalogo(arquivo_armas, arquivo_personagens)
    segundo = _catalogo(arquivo_armas, arquivo_personagens)
    assert catalogo_animacoes.bytes_catalogo(primeiro) == catalogo_animacoes.bytes_catalogo(segundo)
    ids = [peca["id"] for peca in primeiro["pecas"]]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))

    saida = tmp_path / "catalogo.json"
    assert catalogo_animacoes.main(["--saida", str(saida), "--verificar"]) == 1
    saida.write_bytes(catalogo_animacoes.bytes_catalogo(catalogo_animacoes.gerar_catalogo()))
    assert catalogo_animacoes.main(["--saida", str(saida), "--verificar"]) == 0
