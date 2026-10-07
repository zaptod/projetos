# -*- coding: utf-8 -*-
"""Folhas sinteticas para o recortador verde/magenta, sem biblioteca real."""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from painel.sprites import folha_de_olhos, limpeza, recortador

OLHO_CIMA = (480, 340, 645, 500)        # CONTRATO 2.3: a caixa de cada olho no gabarito
OLHO_BAIXO = (480, 524, 645, 684)


def _folha(cor_fundo):
    arr = np.zeros((260, 360, 4), np.uint8)
    arr[..., :3] = cor_fundo
    arr[..., 3] = 255
    # Seis desenhos; o primeiro sao dois olhos que precisam virar um so.
    for caixa, cor in [((30, 30, 52, 54), (20, 30, 180)), ((69, 30, 91, 54), (20, 30, 180)),
                       ((135, 26, 178, 70), (240, 70, 50)), ((220, 28, 267, 75), (80, 80, 80)),
                       ((45, 145, 95, 195), (250, 220, 30)), ((150, 145, 204, 198), (40, 180, 220)),
                       ((260, 145, 315, 202), (130, 50, 180))]:
        x0, y0, x1, y1 = caixa
        arr[y0:y1, x0:x1, :3] = cor
    # Verde verdadeiro dentro do desenho so pode sumir quando ele for fundo.
    arr[155:180, 164:190, :3] = (0, 255, 0)
    # Poeira isolada.
    arr[230:233, 20:23, :3] = (10, 10, 10)
    return arr


@pytest.mark.parametrize("fundo", [(0, 255, 0), (255, 0, 255)])
def test_recorta_seis_desenhos_junta_olhos_e_tira_poeira(fundo):
    resultado = recortador.recortar(_folha(fundo), juntar=20, area_min=20)
    assert resultado.fundo == ("verde" if fundo[1] == 255 and fundo[0] == 0 else "magenta")
    assert len(resultado.recortes) == 6
    assert resultado.recortes[0].imagem.shape[1] >= 55  # os dois olhos juntos
    # Fundo nao sobrevive opaco na borda; numa folha magenta o verde de dentro continua.
    chave = np.asarray(fundo, np.uint8)
    borda = np.r_[resultado.limpo[0], resultado.limpo[-1],
                  resultado.limpo[:, 0], resultado.limpo[:, -1]]
    assert not np.any((borda[:, 3] > 0) & np.all(borda[:, :3] == chave, axis=1))
    if fundo == (255, 0, 255):
        assert np.any(np.all(resultado.limpo[..., :3] == (0, 255, 0), axis=2)
                      & (resultado.limpo[..., 3] == 255))


def test_recusa_fundo_azul_com_a_frase_humana():
    with pytest.raises(ValueError, match="fundo precisa ser verde ou magenta liso"):
        recortador.recortar(_folha((30, 80, 220)))


def test_gabarito_de_olhos_preserva_proporcao_e_zona():
    resultado = recortador.recortar(_folha((255, 0, 255)), juntar=20, area_min=20)
    pronto = recortador.no_gabarito(resultado.recortes[0].imagem, "olhos")
    ys, xs = np.nonzero(pronto[..., 3])
    assert pronto.shape == (1024, 1024, 4)
    assert xs.min() >= 480 and xs.max() < 645 and ys.min() >= 340 and ys.max() < 684
    assert xs.max() - xs.min() >= 160


def test_halo_magenta_da_borda_nao_sobra_visivel():
    arr = np.full((64, 64, 4), (255, 0, 255, 255), np.uint8)
    arr[24:40, 24:40, :3] = (30, 80, 210)
    # Antialias/halo de uma folha sem alfa: mistura da cor-chave na borda.
    arr[23:41, 23, :3] = arr[23:41, 40, :3] = (200, 20, 240)
    arr[23, 23:41, :3] = arr[40, 23:41, :3] = (200, 20, 240)
    resultado = recortador.recortar(arr, area_min=20)
    recorte = resultado.recortes[0].imagem
    assert not np.any((recorte[..., 3] > 0) & np.all(recorte[..., :3] == (255, 0, 255), axis=2))


def test_folha_2048_termina_em_menos_de_tres_segundos():
    arr = np.full((2048, 2048, 4), (255, 0, 255, 255), np.uint8)
    for y in range(120, 1900, 280):
        for x in range(120, 1900, 280):
            arr[y:y + 80, x:x + 100, :3] = (25, 70, 200)
    inicio = time.perf_counter()
    resultado = recortador.recortar(arr, area_min=50)
    assert time.perf_counter() - inicio < 3.0
    assert len(resultado.recortes) == 49


# ---------------------------------------------- reprovacao do conferente, 06/10
def _caixa(img):
    ys, xs = np.nonzero(img[..., 3] >= 16)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else None


def _dentro(caixa, zona):
    return (caixa is not None and caixa[0] >= zona[0] and caixa[1] >= zona[1]
            and caixa[2] <= zona[2] and caixa[3] <= zona[3])


def _anel(limpo):
    """Os pixels visiveis que encostam num transparente: a borda do desenho."""
    vis = limpo[..., 3] > 0
    vazio = ~vis
    viz = np.zeros_like(vis)
    viz[1:] |= vazio[:-1]
    viz[:-1] |= vazio[1:]
    viz[:, 1:] |= vazio[:, :-1]
    viz[:, :-1] |= vazio[:, 1:]
    return vis & viz


@pytest.mark.parametrize("fundo", [(255, 0, 255), (0, 255, 0)])
def test_borda_sem_franja_da_cor_chave_na_folha_realista(fundo):
    """06/10: o anel de 1 px era mistura do contorno com o fundo -- media
    (96.6, 13.9, 100.6) no magenta, 108 pixels a menos de 60 da chave, 1307 de
    4528 mais perto do magenta que do contorno. Agora a borda e do contorno."""
    resultado = recortador.recortar(folha_de_olhos.folha(fundo, 40))
    px = resultado.limpo[_anel(resultado.limpo)]
    assert len(px) > 3000
    distancia = limpeza.distancia(px[:, :3], fundo)
    assert distancia.min() >= 100, distancia.min()
    contorno = np.asarray(folha_de_olhos.CONTORNO, np.float64)
    assert np.abs(px[:, :3].mean(0) - contorno).max() < 12, px[:, :3].mean(0)
    perto_da_chave = (np.linalg.norm(px[:, :3] - np.asarray(fundo, np.float64), axis=1)
                      < np.linalg.norm(px[:, :3] - contorno, axis=1))
    assert not perto_da_chave.any()
    # a borda continua macia (alfa parcial), nao virou degrau
    assert ((px[:, 3] > 0) & (px[:, 3] < 255)).mean() > 0.5


def test_franja_nao_mexe_em_traco_de_outra_cor_encostado_no_fundo():
    """Branco encostado no fundo nao esta na reta chave->vizinho: fica."""
    arr = np.full((80, 80, 4), (255, 0, 255, 255), np.uint8)
    arr[20:60, 20:60, :3] = (30, 80, 210)
    arr[20:60, 20, :3] = (255, 255, 255)
    resultado = recortador.recortar(arr, area_min=20)
    assert tuple(resultado.limpo[40, 20, :3]) == (255, 255, 255)
    assert resultado.limpo[40, 20, 3] == 255


def test_aviso_de_cor_chave_tem_acento():
    resultado = recortador.recortar(folha_de_olhos.folha((255, 0, 255), 40))
    assert resultado.avisos == ["há bastante magenta parecido dentro de um desenho; confira antes de mandar"]


@pytest.mark.parametrize("vao", [24, 40])
@pytest.mark.parametrize("fundo", [(255, 0, 255), (0, 255, 0)])
def test_pares_de_olhos_viram_seis_e_cada_olho_cai_na_sua_zona(fundo, vao):
    """06/10: 6 pares davam 12 recortes (o medio nao junta 24-40 px) e o par
    encaixado inteiro ficava deitado no meio do rosto. O par so de pupilas
    tem 94 px de vao com vao=24 (110 com 40)."""
    folha = folha_de_olhos.folha(fundo, vao)
    assert len(recortador.recortar(folha).recortes) == 12
    resultado = recortador.recortar(folha, pares=True)
    assert [r.tipo for r in resultado.recortes] == ["par"] * 6
    assert {r.orientacao for r in resultado.recortes} == {"lado"}
    for recorte in resultado.recortes:
        pronto = recortador.olhos_no_gabarito(recorte, "separar")
        cima, baixo = pronto.copy(), pronto.copy()
        cima[512:] = 0
        baixo[:512] = 0
        assert _dentro(_caixa(cima), OLHO_CIMA), _caixa(cima)
        assert _dentro(_caixa(baixo), OLHO_BAIXO), _caixa(baixo)
        # sem distorcer: os dois olhos com o mesmo tamanho, maior lado = 122 px
        (cx0, cy0, cx1, cy1), (bx0, by0, bx1, by1) = _caixa(cima), _caixa(baixo)
        assert (cx1 - cx0, cy1 - cy0) == (bx1 - bx0, by1 - by0)
        assert max(cx1 - cx0, cy1 - cy0) in (121, 122)
        # e o meio entre os dois olhos fica vazio
        assert not pronto[501:524, :, 3].any()


def _cor_dominante(img):
    vis = img[..., 3] > 200
    r = ((img[..., 0] > 150) & (img[..., 2] < 90) & vis).sum()
    b = ((img[..., 2] > 150) & (img[..., 0] < 90) & vis).sum()
    return "vermelho" if r > b else "azul"


@pytest.mark.parametrize("modo", ["separar", "girar"])
def test_olho_da_direita_da_imagem_vai_para_cima(modo):
    """De frente, o olho da DIREITA da imagem e o esquerdo do rosto; no jogo
    (visto de cima, olhando para +x) o lado esquerdo fica em cima (y 420)."""
    folha = folha_de_olhos.folha((0, 255, 0), 40, cores_por_lado=((230, 20, 20), (20, 20, 230)))
    recorte = recortador.recortar(folha, pares=True).recortes[0]
    pronto = recortador.olhos_no_gabarito(recorte, modo)
    assert _cor_dominante(pronto[:512]) == "azul"
    assert _cor_dominante(pronto[512:]) == "vermelho"
    if modo == "girar":       # o par inteiro, de pe, na caixa dos dois olhos
        assert _dentro(_caixa(pronto), recortador.ZONAS["olhos"])


def test_vista_de_cima_nao_mexe():
    folha = folha_de_olhos.folha((255, 0, 255), 40)
    recorte = recortador.recortar(folha, pares=True).recortes[0]
    pronto = recortador.olhos_no_gabarito(recorte, "vista-de-cima")
    x0, y0, x1, y1 = _caixa(pronto)
    assert _dentro((x0, y0, x1, y1), recortador.ZONAS["olhos"])
    assert x1 - x0 > y1 - y0          # continua deitado, como veio
    with pytest.raises(ValueError):
        recortador.olhos_no_gabarito(recorte, "outro")


def _olho(caneta, cx, cy, cor=(20, 20, 26)):
    caneta.ellipse((cx - 40, cy - 30, cx + 40, cy + 30), fill=cor)
    caneta.ellipse((cx - 30, cy - 20, cx + 30, cy + 20), fill=(250, 250, 248))
    caneta.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill=cor)


def _folha_rgb(tamanho, desenhar):
    img = Image.new("RGB", tamanho, (255, 0, 255))
    desenhar(ImageDraw.Draw(img))
    return np.asarray(img).copy()


def test_olho_sozinho_vira_o_par_com_o_mesmo_olho():
    folha = _folha_rgb((300, 200), lambda c: _olho(c, 150, 100))
    resultado = recortador.recortar(folha, pares=True)
    assert [r.tipo for r in resultado.recortes] == ["um"]
    pronto = recortador.olhos_no_gabarito(resultado.recortes[0], "separar")
    cx0, cy0, cx1, cy1 = _caixa(pronto[:512])
    bx0, by0, bx1, by1 = _caixa(pronto[512:])
    by0, by1 = by0 + 512, by1 + 512
    assert _dentro((cx0, cy0, cx1, cy1), OLHO_CIMA) and _dentro((bx0, by0, bx1, by1), OLHO_BAIXO)
    assert np.array_equal(pronto[cy0:cy1, cx0:cx1], pronto[by0:by1, bx0:bx1])     # o mesmo olho


def test_par_colado_que_o_medio_junta_e_dividido_e_par_em_pe_tambem():
    # 10 px entre os olhos: o medio (16) junta num desenho so; o par e achado dentro dele
    colado = recortador.recortar(_folha_rgb((300, 200), lambda c: (_olho(c, 100, 100), _olho(c, 190, 100))),
                                 pares=True)
    assert [r.tipo for r in colado.recortes] == ["par"]
    assert all(o is not None for o in colado.recortes[0].olhos)
    # ja desenhado visto de cima (um em cima do outro): par "pe", o de cima continua em cima
    em_pe = recortador.recortar(
        _folha_rgb((200, 360), lambda c: (_olho(c, 100, 90, (200, 20, 20)), _olho(c, 100, 250, (20, 20, 200)))),
        pares=True)
    assert [(r.tipo, r.orientacao) for r in em_pe.recortes] == [("par", "pe")]
    pronto = recortador.olhos_no_gabarito(em_pe.recortes[0], "separar")
    assert _cor_dominante(pronto[:512]) == "vermelho" and _cor_dominante(pronto[512:]) == "azul"


def test_recorte_de_outra_peca_vai_no_quadro_do_slot():
    folha = _folha_rgb((300, 200), lambda c: c.rectangle((40, 80, 260, 120), fill=(90, 90, 90)))
    recorte = recortador.recortar(folha).recortes[0]
    arma = recortador.encaixar(recorte, "arma", grupo="arma", tamanho=(1024, 256))
    assert arma.shape == (256, 1024, 4)
    sombra = recortador.encaixar(recorte, "sombra")
    assert _dentro(_caixa(sombra), recortador.ZONAS["sombra"])


def _brilho(caneta, cx, cy, r=7):
    """Faisca de 4 pontas (o "brilho" que a IA desenha perto do olho)."""
    caneta.polygon([(cx, cy - r), (cx + 2, cy - 2), (cx + r, cy), (cx + 2, cy + 2),
                    (cx, cy + r), (cx - 2, cy + 2), (cx - r, cy), (cx - 2, cy - 2)], fill=(255, 255, 240))


@pytest.mark.parametrize("vao", [10, 14])
def test_brilho_perto_do_olho_nao_entra_no_par_nem_encolhe_o_olho(vao):
    """Conferente, 07/10: um brilho a menos de 16 px do olho entrava no
    recorte (o medio junta ate 16 px) e, no encaixe pela caixa, o olho
    encolhia. Nos PARES DE OLHOS o pedacinho que so passou perto vira recorte
    proprio ("sobra"), nunca entra num par, e o par sai do mesmo tamanho."""
    pares = recortador.recortar(_folha_rgb((400, 200), lambda c: (
        _olho(c, 100, 100), _olho(c, 220, 100), _brilho(c, 260 + vao + 7, 70))), pares=True, area_min=10)
    assert sorted(r.tipo for r in pares.recortes) == ["par", "sobra"]
    par = next(r for r in pares.recortes if r.tipo == "par")
    par_sem = recortador.recortar(_folha_rgb((400, 200), lambda c: (_olho(c, 100, 100), _olho(c, 220, 100))),
                                  pares=True)
    assert _caixa(recortador.olhos_no_gabarito(par)) == _caixa(
        recortador.olhos_no_gabarito(par_sem.recortes[0]))
    # um olho so com o brilho: o olho continua do mesmo tamanho
    um = recortador.recortar(_folha_rgb((300, 200), lambda c: (_olho(c, 120, 100), _brilho(c, 160 + vao + 7, 80))),
                             pares=True, area_min=10)
    assert sorted(r.tipo for r in um.recortes) == ["sobra", "um"]


def test_fora_dos_olhos_o_brilho_continua_no_desenho():
    """A v54 separava o "pedacinho" em todo modo menos o "muito" e amputou
    arte de efeito (reprovacao do conferente, 07/10). Fora dos pares de olhos
    nada sai do desenho: o brilho a 12 px fica no recorte, como sempre."""
    folha = _folha_rgb((300, 200), lambda c: (_olho(c, 120, 100), _brilho(c, 160 + 12 + 7, 80)))
    for juntar in (recortador.JUNCAO["medio"], recortador.JUNCAO["muito"]):
        resultado = recortador.recortar(folha, juntar=juntar, area_min=10)
        assert [r.tipo for r in resultado.recortes] == [""]
        assert resultado.recortes[0].caixa[2] >= 160 + 12 + 7 + 7      # o brilho esta no recorte


def test_cilio_em_corrente_e_reflexo_dentro_continuam_no_olho():
    """Nos pares: o reflexo dentro da caixa e os cilios a ate 8 px, em
    corrente (um cilio puxa o outro), ficam no olho."""
    def desenhar(c):
        _olho(c, 120, 100)
        c.line((100, 64, 112, 50), fill=(20, 20, 26), width=5)       # cilio a ~6 px do topo (y 70)
        c.line((108, 44, 118, 30), fill=(20, 20, 26), width=5)       # outro, a ~5 px do primeiro
        _brilho(c, 160 + 12 + 7, 80)
    resultado = recortador.recortar(_folha_rgb((300, 200), desenhar), pares=True, area_min=10)
    assert sorted(r.tipo for r in resultado.recortes) == ["sobra", "um"]
    assert next(r for r in resultado.recortes if r.tipo == "um").caixa[1] < 30     # os dois cilios


def _folha_real(caminho):
    im0 = Image.open(caminho).convert("RGBA")
    im = Image.new("RGBA", im0.size, (255, 0, 255, 255))
    im.alpha_composite(im0)
    return im.convert("RGB")


EVENTO_DANO = Path(__file__).resolve().parents[1] / "palco/biblioteca/efeitos/folhas/evento_dano.png"
FOLHAS_REAIS = [
    # (folha, {juncao: (recortes, pixels opacos somados)}) -- medido no HEAD
    # (c7b3ac6..de238e9) e igual byte a byte ao codigo novo em 07/10.
    (Path(__file__).resolve().parents[1] / "painel/sprites/fixtures/folha_acida_chatgpt.png",
     {"pouco": (49, 379260), "medio": (26, 379301), "muito": (26, 379301)}),
    (EVENTO_DANO, {"pouco": (35, 295107), "medio": (27, 295206), "muito": (24, 295224)}),
]


@pytest.mark.parametrize("folha,esperado", FOLHAS_REAIS, ids=["acida_11243", "evento_dano"])
def test_folhas_reais_de_efeito_nao_perdem_nada(folha, esperado):
    """Reprovacao do conferente, 07/10: na v54 o projetil acido (a 11243.png
    da raiz, copia em fixtures) dava 26 + 49 "pedacinhos" e 24 de 26 quadros
    perdiam a cauda de gotas; o evento_dano ia de 27 a 37 com buracos. Fora
    dos olhos o recorte e o de antes: mesmo numero, mesmos pixels, nada de
    "sobra". O evento_dano e arte do Adrian (fora do git): so roda se estiver
    no disco."""
    if not folha.is_file():
        pytest.skip(f"{folha.name} nao esta neste disco")
    imagem = _folha_real(folha)
    for nivel, (quantos, pixels) in esperado.items():
        resultado = recortador.recortar(imagem, juntar=recortador.JUNCAO[nivel])
        assert {r.tipo for r in resultado.recortes} == {""}, nivel
        assert len(resultado.recortes) == quantos, nivel
        assert sum(int((r.imagem[..., 3] >= 16).sum()) for r in resultado.recortes) == pixels, nivel
