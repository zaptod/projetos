from pathlib import Path


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
    assert '"acerto": "acerto_recebido"' in codigo
    assert '"ko": "ko"' in codigo
    assert "golpe_fase" in codigo


def test_marcadores_neutros_nao_reintroduzem_arte_propria():
    reserva = (RAIZ / "palco/nucleo/peca_reserva.gd").read_text(encoding="utf-8")
    assert "Color(0.55, 0.55, 0.55" in reserva
    assert "categoria != \"efeitos\"" in reserva


def test_previa_tem_seed_estavel_e_duracao_curta_sem_escrever_no_catalogo():
    codigo = (RAIZ / "random_builds/builds/palco/previa_animacao.py").read_text(encoding="utf-8")
    assert "hashlib.sha256" in codigo
    assert "quadros=150" in codigo
    assert "render_da_seed" in codigo
