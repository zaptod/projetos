# -*- coding: utf-8 -*-
import json
from datetime import datetime

from ferramentas import obsidian


def decisao(raiz, projeto, nome, pendente=False):
    pasta = raiz / "decisoes" / projeto
    pasta.mkdir(parents=True, exist_ok=True)
    dados = {"titulo": "Pergunta importante", "pergunta": "O que devemos fazer?", "situacao": "pendente" if pendente else "decidida",
             "contexto": "Detalhe técnico", "opcoes": [{"id": "sim", "rotulo": "Fazer do jeito simples", "descricao": "Mais claro."}],
             "vigente": None if pendente else {"opcao": "sim", "em": "2026-10-06T04:16:15", "comentario": "Pode seguir"}}
    (pasta / nome).with_suffix(".json").write_text(json.dumps(dados), encoding="utf-8")


def test_decisoes_mostram_pergunta_vigente_e_links_com_caminho(tmp_path):
    cofre, raiz = tmp_path / "cofre", tmp_path / "repo"
    cofre.mkdir(); decisao(raiz, "app-e-bot", "pendente", True); decisao(raiz, "builds", "escolhida")
    obsidian.decisoes(cofre, raiz, datetime(2026, 10, 6, 8, 30))
    indice = (cofre / "04 🧭 Decisões" / "Decisões.md").read_text(encoding="utf-8")
    escolhida = (cofre / "04 🧭 Decisões" / "Neural Fights (builds).md").read_text(encoding="utf-8")
    assert "⏳ Esperando você (1)" in indice
    assert "[[04 🧭 Decisões/App e bot|App e bot]]" in indice
    assert "**Pergunta:** O que devemos fazer?" in escolhida
    assert "Você escolheu:** Fazer do jeito simples" in escolhida
    assert "> [!info]-" in escolhida


def test_instalar_preserva_notas_pessoais_e_molde_editado(tmp_path):
    modelos, cofre = tmp_path / "modelos", tmp_path / "cofre"
    (modelos / "03 🗺️ Entender o projeto").mkdir(parents=True)
    (modelos / "99 🧩 Modelos").mkdir(parents=True)
    (modelos / "00 Início.md").write_text("novo", encoding="utf-8")
    (modelos / "03 🗺️ Entender o projeto" / "Mapa.md").write_text("mapa", encoding="utf-8")
    (modelos / "99 🧩 Modelos" / "Ideia.md").write_text("molde", encoding="utf-8")
    (modelos / "01 💡 Ideias").mkdir(); (modelos / "01 💡 Ideias" / "Ideias.base").write_text("base", encoding="utf-8")
    (cofre / "01 💡 Ideias").mkdir(parents=True); (cofre / "02 📝 Minhas notas").mkdir()
    (cofre / "01 💡 Ideias" / "minha.md").write_text("minha", encoding="utf-8")
    (cofre / "99 🧩 Modelos").mkdir(); (cofre / "99 🧩 Modelos" / "Ideia.md").write_text("meu", encoding="utf-8")
    assert obsidian.instalar(cofre, modelos)
    assert (cofre / "01 💡 Ideias" / "minha.md").read_text(encoding="utf-8") == "minha"
    assert (cofre / "01 💡 Ideias" / "Ideias.base").read_text(encoding="utf-8") == "base"
    assert (cofre / "99 🧩 Modelos" / "Ideia.md").read_text(encoding="utf-8") == "meu"
    assert (cofre / "03 🗺️ Entender o projeto" / "Mapa.md").is_file()


def test_gerados_sao_atomicos_e_nao_criam_cofre_ausente(tmp_path):
    assert not obsidian.tudo(tmp_path / "ausente", tmp_path)
    cofre = tmp_path / "cofre"; cofre.mkdir()
    obsidian.agora_nota(cofre, medicao={"pendentes": {"historias": 3, "builds": 2}, "retidas": {"historias": 1}, "consertadas": {"historias": 1}})
    texto = (cofre / "📊 Agora.md").read_text(encoding="utf-8")
    assert "Atualizada sozinha às" in texto and not list(cofre.rglob("*.novo"))
