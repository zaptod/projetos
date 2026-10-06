# -*- coding: utf-8 -*-
import json
import os
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
    pendente = (cofre / "04 🧭 Decisões" / "App e bot.md").read_text(encoding="utf-8")
    escolhida = (cofre / "04 🧭 Decisões" / "Neural Fights (builds).md").read_text(encoding="utf-8")
    assert "⏳ Esperando você (1)" in indice
    assert "[[04 🧭 Decisões/App e bot|App e bot]]" in indice
    assert "**Pergunta:** O que devemos fazer?" in escolhida
    assert "Você escolheu:** Fazer do jeito simples" in escolhida
    assert "📖 Decidir → Responder" in pendente
    assert "> [!info]-" in escolhida


def test_instalar_preserva_notas_pessoais_e_molde_editado(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURAL_FIGHTS_RUNTIME_DIR", str(tmp_path / "runtime"))
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


def test_instalar_atualiza_so_molde_que_o_sistema_instalou(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURAL_FIGHTS_RUNTIME_DIR", str(tmp_path / "runtime"))
    modelos, cofre = tmp_path / "modelos", tmp_path / "cofre"
    (modelos / "03 🗺️ Entender o projeto").mkdir(parents=True)
    (modelos / "99 🧩 Modelos").mkdir()
    (modelos / "01 💡 Ideias").mkdir()
    (modelos / "00 Início.md").write_text("início", encoding="utf-8")
    molde = modelos / "99 🧩 Modelos" / "Dia.md"
    molde.write_text("versão 1", encoding="utf-8")
    cofre.mkdir()

    assert obsidian.instalar(cofre, modelos)
    molde.write_text("versão 2", encoding="utf-8")
    assert obsidian.instalar(cofre, modelos)
    instalado = cofre / "99 🧩 Modelos" / "Dia.md"
    assert instalado.read_text(encoding="utf-8") == "versão 2"

    instalado.write_text("texto do Adrian", encoding="utf-8")
    molde.write_text("versão 3", encoding="utf-8")
    assert obsidian.instalar(cofre, modelos)
    assert instalado.read_text(encoding="utf-8") == "texto do Adrian"
    favoritos = json.loads((cofre / ".obsidian" / "bookmarks.json").read_text(encoding="utf-8"))
    assert {item["path"] for item in favoritos["items"]} == {"00 Início.md", "📊 Agora.md"}


def test_gerados_sao_atomicos_e_nao_criam_cofre_ausente(tmp_path):
    assert not obsidian.tudo(tmp_path / "ausente", tmp_path)
    cofre = tmp_path / "cofre"; cofre.mkdir()
    obsidian.agora_nota(cofre, medicao={"pendentes": {"historias": 3, "builds": 2}, "retidas": {"historias": 1}, "consertadas": {"historias": 1}})
    texto = (cofre / "📊 Agora.md").read_text(encoding="utf-8")
    assert "Atualizada sozinha às" in texto and not list(cofre.rglob("*.novo"))


def _registrar(arquivo, *itens):
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("\n".join(json.dumps(item) for item in itens) + "\n", encoding="utf-8")


def test_diario_le_apenas_os_dois_ledgers_e_mostra_cada_destino(tmp_path):
    cofre, raiz = tmp_path / "cofre", tmp_path / "repo"
    cofre.mkdir()
    _registrar(raiz / "historias" / "outputs" / "_publicar" / "publicados.jsonl",
               {"quando": "2026-10-06T06:40:00", "plataforma": "youtube",
                "publicado": True, "titulo": "A história que saiu"})
    _registrar(raiz / "random_builds" / "outputs" / "_publicar" / "publicados.jsonl",
               {"quando": "2026-10-06T06:40:00", "plataforma": "tiktok",
                "publicado": True, "titulo": "A luta que saiu"},
               {"quando": "2026-10-06T06:40:00", "plataforma": "youtube",
                "publicado": False, "url": "https://nao-conta", "titulo": "Rascunho"})
    log = raiz / "outputs" / "postar.txt"
    log.parent.mkdir(parents=True)
    log.write_text("[2026-10-06 06:40] historias YouTube falhou: sem rede\n", encoding="utf-8")
    _registrar(raiz / "atividade.jsonl", {"quando": "2026-10-06T06:40:00", "titulo": "não é publicação"})

    assert obsidian.diario(cofre, raiz, "2026-10-06", datetime(2026, 10, 6, 8))
    texto = (cofre / "05 📅 Diário do sistema" / "2026-10-06.md").read_text(encoding="utf-8")
    trecho = texto[texto.index("### 06:37"):texto.index("### 09:37")]
    assert "A história que saiu" in trecho and "A luta que saiu" in trecho
    assert "Rascunho" not in texto
    assert "Histórias — YouTube: não saiu" not in trecho
    assert "Builds — YouTube: não saiu" in trecho


def test_diario_zero_e_madrugada_pertencem_ao_dia_local(tmp_path):
    cofre, raiz = tmp_path / "cofre", tmp_path / "repo"
    cofre.mkdir()
    _registrar(raiz / "random_builds" / "outputs" / "_publicar" / "publicados.jsonl",
               {"quando": "2026-10-06T00:40:00", "plataforma": "youtube",
                "publicado": True, "titulo": "Última luta da noite"})

    obsidian.diario(cofre, raiz, "2026-10-06", datetime(2026, 10, 6, 1))
    texto = (cofre / "05 📅 Diário do sistema" / "2026-10-06.md").read_text(encoding="utf-8")
    trecho = texto[texto.index("### 00:37"):]
    assert "Última luta da noite" in trecho

    obsidian.diario(cofre, raiz, "2026-10-08", datetime(2026, 10, 9, 8))
    zero = (cofre / "05 📅 Diário do sistema" / "2026-10-08.md").read_text(encoding="utf-8")
    assert zero.count("não saiu.") == len(obsidian._grade().GRADE) * 4


def test_diario_nao_acusa_horario_que_ainda_nao_chegou(tmp_path):
    cofre, raiz = tmp_path / "cofre", tmp_path / "repo"
    cofre.mkdir()
    _registrar(raiz / "random_builds" / "outputs" / "_publicar" / "publicados.jsonl",
               {"quando": "2026-10-06T09:44:00", "plataforma": "youtube",
                "publicado": True, "titulo": "Luta das 09:37"})

    obsidian.diario(cofre, raiz, "2026-10-06", datetime(2026, 10, 6, 10))
    texto = (cofre / "05 📅 Diário do sistema" / "2026-10-06.md").read_text(encoding="utf-8")
    passado = texto[texto.index("### 09:37"):texto.index("### 12:07")]
    futuro = texto[texto.index("### 12:07"):]
    assert "Luta das 09:37" in passado and "Builds — TikTok: não saiu." in passado
    assert "não saiu" not in futuro
    assert futuro.count("Ainda não chegou.") == 7


def test_grade_carrega_sem_a_raiz_no_sys_path(tmp_path):
    """`python ferramentas/obsidian.py` roda sem a raiz no sys.path."""
    import subprocess
    import sys
    cofre = tmp_path / "cofre"
    cofre.mkdir()
    env = {**os.environ, "PYTHONPATH": "", "NEURAL_FIGHTS_RUNTIME_DIR": str(tmp_path / "rt")}
    saida = subprocess.run(
        [sys.executable, "-X", "utf8", "-S", str(obsidian.RAIZ / "ferramentas" / "obsidian.py"),
         "--cofre", str(cofre), "--raiz", str(tmp_path / "repo"), "diario", "--dia", "2026-10-06"],
        capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=60)
    assert saida.returncode == 0, saida.stderr
    assert (cofre / "05 📅 Diário do sistema" / "2026-10-06.md").is_file()


def test_agora_usa_a_escolha_real_e_avisa_piso(tmp_path, monkeypatch):
    class Video:
        def __init__(self, titulo):
            self.titulo = titulo

    historia, build = Video("Título humano da história"), Video("Título humano da luta")

    class Postar:
        @staticmethod
        def proxima_historia():
            return historia, []

        @staticmethod
        def proximo_build(*, marcar):
            assert not marcar
            return build

        @staticmethod
        def _retencao(video):
            return "qualidade" if video is historia else ""

    monkeypatch.setattr(obsidian, "_postar", lambda: Postar())
    cofre = tmp_path / "cofre"; cofre.mkdir()
    obsidian.agora_nota(cofre, medicao={"pendentes": {"historias": 19, "builds": 21},
                                        "retidas": {"historias": 4},
                                        "consertadas": {"historias": 3}})
    texto = (cofre / "📊 Agora.md").read_text(encoding="utf-8")
    assert "Título humano da história — retida; sai só para o horário não ficar vazio." in texto
    assert "Título humano da luta" in texto
    assert "uma passada só" in texto and "ninguém vai assistir de novo" in texto
    assert "Histórias abaixo do piso" in texto
    assert "Consertadas" not in texto


def test_atualizacao_automatica_ouve_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURAL_FIGHTS_RUNTIME_DIR", str(tmp_path / "runtime"))
    cofre, raiz = tmp_path / "cofre", tmp_path / "repo"
    cofre.mkdir()
    ledger = raiz / "random_builds" / "outputs" / "_publicar" / "publicados.jsonl"
    _registrar(ledger, {"quando": "2026-10-06T06:37:00", "publicado": True})
    chamadas = []
    monkeypatch.setattr(obsidian, "decisoes", lambda *args: chamadas.append("decisoes") or True)
    monkeypatch.setattr(obsidian, "diario", lambda *args, **kwargs: chamadas.append("diario") or True)
    monkeypatch.setattr(obsidian, "agora_nota", lambda *args: chamadas.append("agora") or True)

    obsidian.atualizar_automaticamente(raiz, cofre, datetime(2026, 10, 6, 8))
    chamadas.clear()
    os.utime(ledger, (2000000000, 2000000000))
    obsidian.atualizar_automaticamente(raiz, cofre, datetime(2026, 10, 6, 8))
    assert chamadas == ["diario", "agora"]

    # O log da postagem cresce a cada poucos segundos: sozinho, nao refaz nada.
    chamadas.clear()
    log = raiz / "outputs" / "postar.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("[youtube-web] esperando o processamento...\n", encoding="utf-8")
    os.utime(log, (2000000100, 2000000100))
    obsidian.atualizar_automaticamente(raiz, cofre, datetime(2026, 10, 6, 8))
    assert chamadas == []
