from pathlib import Path
import json


RAIZ = Path(__file__).resolve().parents[2]


def test_tocador_do_atelie_le_folha_sem_import_e_tem_regras_de_tempo():
    codigo = (RAIZ / "palco/nucleo/tocador_folha.gd").read_text(encoding="utf-8")
    assert "Image.load_from_file" in codigo
    assert "duracao_por_quadro" in codigo
    assert "ida_e_volta" in codigo
    assert "draw_texture_rect_region" in codigo
    assert "ancora" in codigo


def test_gatilhos_da_timeline_ficam_centralizados():
    codigo = (RAIZ / "palco/nucleo/gatilhos_animacao.gd").read_text(encoding="utf-8")
    assert "const GATILHOS" in codigo
    assert "reconhece" in codigo
    assert "golpe_fase" in codigo


def test_todo_gatilho_do_catalogo_esta_na_tabela_unica():
    catalogo = json.loads((RAIZ / "palco/biblioteca/catalogo_animacoes.json").read_text(encoding="utf-8"))
    codigo = (RAIZ / "palco/nucleo/gatilhos_animacao.gd").read_text(encoding="utf-8")
    gatilhos = {a["gatilho"] for p in catalogo["pecas"] for e in p["estados"] for a in e["animacoes"]}
    for gatilho in gatilhos:
        assert f'"{gatilho}"' in codigo


def test_resolvedor_do_catalogo_usa_ids_e_heranca_da_peca():
    codigo = (RAIZ / "palco/nucleo/biblioteca.gd").read_text(encoding="utf-8")
    assert "func resolver_peca" in codigo
    assert "peca.get(\"heranca\"" in codigo
    assert '"arma.estilo." + UtilPalco.slug(estilo)' in codigo
    assert '"arma.tipo." + UtilPalco.slug(tipo)' in codigo


def test_marcadores_neutros_nao_reintroduzem_arte_propria():
    reserva = (RAIZ / "palco/nucleo/peca_reserva.gd").read_text(encoding="utf-8")
    assert "Color(0.55, 0.55, 0.55" in reserva
    assert "categoria != \"efeitos\"" in reserva


def test_previa_tem_seed_estavel_e_duracao_curta_sem_escrever_no_catalogo():
    codigo = (RAIZ / "random_builds/builds/palco/previa_animacao.py").read_text(encoding="utf-8")
    assert "hashlib.sha256" in codigo
    assert "quadros=150" in codigo
    assert "render_da_seed" in codigo


def test_previa_escolhe_fichas_da_classe_arma_e_skill():
    from random_builds.builds.palco.previa_animacao import _tem_peca
    armas = [{"nome": "Sabre", "estilo": "Espada Longa", "tipo": "Reta"}]
    ficha = {"classe": "Mago (Arcano)", "nome_arma": "Sabre",
             "kit": [{"nome": "Chama Arcana", "elemento": "Fogo", "descricao": "aplica queimadura"}]}
    assert _tem_peca(ficha, "classe.mago", armas)
    assert _tem_peca(ficha, "arma.estilo.espada_longa", armas)
    assert _tem_peca(ficha, "arma.tipo.reta", armas)
    assert _tem_peca(ficha, "skill.chama arcana", armas)


def test_previa_registra_troca_de_arma_quando_ninguem_usa_o_estilo(monkeypatch):
    from random_builds.builds.palco import previa_animacao
    fichas = {"A": {"nome_arma": "Reta", "classe": "Mago"}, "B": {"nome_arma": "Reta", "classe": "Guerreiro"}}
    armas = [{"nome": "Reta", "tipo": "Reta", "estilo": "Comum"},
             {"nome": "Cristais", "tipo": "Orbital", "estilo": "Cristais Flutuantes"}]
    monkeypatch.setattr("random_builds.builds.tournament.runner.fichas_do_banco", lambda: fichas)
    monkeypatch.setattr("neural_fights.data.database.carregar_database", lambda: (armas, []))
    primeiro, _segundo, trocas = previa_animacao.escolher_lutadores_da_peca(
        "arma.estilo.cristais_flutuantes", 1, com_trocas=True)
    assert trocas[primeiro]["arma"]["nome"] == "Cristais"
    assert fichas[primeiro]["nome_arma"] == "Reta"
