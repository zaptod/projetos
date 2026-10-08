"""Prova do registro honesto: folha de cor unica chega ao consumidor real."""
import io

from PIL import Image

from neural_fights.tools import atelie_animacoes, catalogo_vila, consumo_atelie
from painel.flutuante import arte, arte_pronta, retrato


COR = (3, 251, 71, 255)


def _folha() -> bytes:
    saida = io.BytesIO()
    Image.new("RGBA", (8, 8), COR).save(saida, "PNG")
    return saida.getvalue()


def _salvar(peca: dict) -> None:
    estado = peca["estados"][0]["id"]
    atelie_animacoes.salvar(peca["id"], estado, "parado", _folha(), {
        "quadros": [{"x": 0, "y": 0, "w": 8, "h": 8}], "fps": 8,
        "loop": True, "ancora": {"x": .5, "y": 1}})


def _consumir(peca: dict):
    ident = peca["id"]
    if ident.startswith("vila.habitantes."):
        return arte.desenhar_personagem(ident.rsplit(".", 1)[-1])
    if ident.startswith("vila.predios."):
        nome = ident.rsplit(".", 1)[-1]
        noite = nome.endswith("_noite")
        return arte.desenhar_predio(nome.removesuffix("_noite"), noite)
    if ident in {"vila.cenario.chao_grama", "vila.cenario.caminho_terra"}:
        return arte.desenhar_chao()
    if ident == "vila.cenario.arvore":
        return arte.desenhar_arvore()
    if ident in {"vila.cenario.lago", "vila.cenario.lago_brilho"}:
        return arte.desenhar_chao()
    if ident == "vila.cenario.placa":
        return retrato.desenhar_placa()
    if ident == "vila.cenario.moita":
        return retrato.desenhar_sebe(False, 1)
    if ident == "vila.cenario.lua":
        return retrato.desenhar_ceu(True, 1)
    if ident in {"vila.cenario.nuvem", "vila.cenario.morro"}:
        return retrato.desenhar_ceu(False, 1)
    if ident.startswith("vila.cenario."):
        return getattr(arte, "desenhar_" + ident.rsplit(".", 1)[-1])()
    if ident.startswith("vila.bichos."):
        return getattr(arte, "desenhar_" + ident.rsplit(".", 1)[-1])()
    if ident == "vila.interface.balao_emote":
        return arte.emote("✨")
    if ident == "vila.interface.confete":
        return arte.desenhar_confete()
    return arte.desenhar_decoracao(ident.rsplit(".", 1)[-1])


def test_registro_da_vila_tem_prova_de_cor_para_cada_peca(tmp_path, monkeypatch):
    """Toda peca marcada como visivel entrega a cor ao desenhador real."""
    monkeypatch.setattr(atelie_animacoes, "ANIMACOES", tmp_path / "animacoes")
    arte_pronta.usar(tmp_path / "arte", arte_pronta.INVENTARIO_PADRAO)
    pecas = {p["id"]: p for p in catalogo_vila.catalogo()}
    assert consumo_atelie.PECAS_VILA_COM_PROVA <= pecas.keys()
    for ident in consumo_atelie.PECAS_VILA_COM_PROVA:
        _salvar(pecas[ident])
        assert COR in _consumir(pecas[ident]).get_flattened_data(), ident
    arte_pronta.usar()


def test_registro_nao_promete_consumidor_sem_prova():
    pecas = [p for p in catalogo_vila.catalogo()]
    provadas = {p["id"] for p in pecas if consumo_atelie.consumidores(p["id"], "vila")}
    assert provadas == consumo_atelie.PECAS_VILA_COM_PROVA
    ausentes = {p["id"] for p in pecas} - provadas
    assert ausentes
    assert all(consumo_atelie.motivo_sem_consumidor(ident, "vila")
               for ident in ausentes)


def test_arvore_expoe_destino_e_aviso_honesto():
    pecas = [p for grupo in atelie_animacoes.arvore() for p in grupo["pecas"]]
    for peca in pecas:
        if peca["id"] in consumo_atelie.PECAS_VILA_COM_PROVA:
            assert peca["aparece_em"] in (["Vila (PC e celular)"], ["Vila (PC)"])
        if peca["grupo"] in {"skill", "efeito", "elemento", "estado_personagem", "buff"}:
            assert not peca["aparece_em"]
            assert "Godot" in peca["motivo_sem_consumidor"]
