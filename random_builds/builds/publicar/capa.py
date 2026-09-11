"""A capa do video — que ate a Onda 15D nao existia em lugar nenhum.

`youtube.py` nunca chamou `thumbnails/set` e `youtube_web.py` nao tinha
campo de miniatura: as capas de todos os 32 videos publicados sao um frame
automatico escolhido pelo YouTube.

HONESTIDADE SOBRE O RETORNO: o feed de Shorts praticamente nao mostra
thumbnail. Ela aparece na pagina do canal, na busca e no player web. A capa
sozinha nao vai mover as views do feed, e prometer isso seria mentira.

O que ela cumpre e a decisao 2 da Onda 15: a arte de IA sai do CORPO do
video (ocupava 12 s dos 62, e criava o contraste entre uma guerreira
cinematografica e duas bolinhas lisas) e vira capa. O video entrega o que
promete; a arte continua trabalhando onde ela funciona, que e vendendo o
clique fora do feed.

Nao ha "primeiro frame igual a capa". Isso estava no plano e foi
DESCARTADO: prefixar um cartao estatico quebraria a invariante central do
duelo — a luta comeca no frame zero, e a curva de retencao de 11/09/2026 e
o motivo. O equivalente honesto ja existe: a faixa de identidade dos
primeiros 1,5 s tem os mesmos nomes, as mesmas cores e o mesmo selo, so
que desenhada sobre a luta viva em vez de sobre uma placa.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from ..visualization.draw_common import fit_font, gradient, hex_rgb, load_font
from ..visualization.weapon_visualizer import _glyph

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"

# O que o YouTube aceita em `thumbnails/set`: 1280x720 e ate 2 MB.
LARGURA, ALTURA = 1280, 720
PESO_MAXIMO = 2 * 1024 * 1024


def arte_do_personagem(nome: str) -> Path | None:
    """A imagem de IA daquele personagem, se alguma geracao a produziu.

    O vinculo nome -> pasta vive em `insercao.json`, o mesmo arquivo que
    `runner.personagens_gerados` ja usa. Lutador do banco que nunca passou
    pela roleta simplesmente nao tem arte — e a capa cai no glifo.
    """
    if not nome:
        return None
    for arquivo in sorted(OUTPUTS.glob("generation_*/insercao.json"),
                          reverse=True):
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if dados.get("personagem") != nome:
            continue
        for candidato in ("character_weapon_reference.png", "character_image.png"):
            caminho = arquivo.parent / candidato
            if caminho.is_file():
                return caminho
    return None


def _retrato(caminho: Path | None, lado: int, cor, tipo_arma: str) -> Image.Image:
    """O bloco de um lutador: a arte de IA, ou o glifo da arma na cor dele."""
    bloco = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    if caminho is not None:
        try:
            with Image.open(caminho) as bruta:
                arte = bruta.convert("RGB")
            # `cover`: a arte e vertical e a caixa e quadrada; encaixar por
            # dentro deixaria duas tarjas em cada lado.
            escala = max(lado / arte.width, lado / arte.height)
            arte = arte.resize((max(1, int(arte.width * escala)),
                                max(1, int(arte.height * escala))),
                               Image.LANCZOS)
            recorte = ((arte.width - lado) // 2, (arte.height - lado) // 2)
            bloco.paste(arte.crop((recorte[0], recorte[1],
                                   recorte[0] + lado, recorte[1] + lado)), (0, 0))
            return bloco
        except OSError:
            pass  # arte ilegivel cai no glifo, como se nao existisse
    desenho = ImageDraw.Draw(bloco)
    desenho.ellipse([lado * 0.08, lado * 0.08, lado * 0.92, lado * 0.92],
                    fill=tuple(int(c * 0.35) for c in cor))
    _glyph(desenho, tipo_arma or "Reta", lado / 2, lado / 2, lado * 0.30, cor)
    return bloco


def gerar(fight: dict, out_dir: Path, render_config: dict,
          destino: Path | None = None) -> Path:
    """Escreve `capa.png` para um duelo e devolve o caminho."""
    luta = fight.get("luta") or {}
    cores = render_config["colors"]
    fontes = render_config["fonts"]

    imagem = gradient(LARGURA, ALTURA, cores["bg_top"], cores["bg_bottom"]).convert("RGB")
    # Os retratos deixam uma calha no meio: com eles quase se tocando, o
    # "VS" caia POR CIMA da arte dos dois e nenhum dos tres lia.
    lado = int(ALTURA * 0.70)
    topo = int(ALTURA * 0.06)

    def cor_de(slot, padrao):
        ficha = luta.get(f"{slot}_ficha") or {}
        return (ficha.get("cor_r", padrao[0]), ficha.get("cor_g", padrao[1]),
                ficha.get("cor_b", padrao[2]))

    cor1 = cor_de("p1", hex_rgb(cores["accent_character"]))
    cor2 = cor_de("p2", hex_rgb(cores["accent_weapon"]))
    for slot, cor, x in (("p1", cor1, int(LARGURA * 0.04)),
                         ("p2", cor2, LARGURA - int(LARGURA * 0.04) - lado)):
        ficha = luta.get(f"{slot}_ficha") or {}
        bloco = _retrato(arte_do_personagem(luta.get(slot, "")), lado, cor,
                         str(ficha.get("arma_tipo") or ""))
        imagem.paste(bloco, (x, topo), bloco)
        desenho_lado = ImageDraw.Draw(imagem)
        # Moldura na cor do lutador: e o que amarra a capa a identidade que
        # o video usa nas barras de vida e na faixa de abertura.
        desenho_lado.rectangle([x, topo, x + lado, topo + lado],
                               outline=cor, width=7)
        # O NOME embaixo do retrato. Sem ele a capa e dois desenhos sem
        # ninguem dentro — e e o nome que o espectador reconhece quando o
        # mesmo lutador volta (o ledger existe para isso).
        nome = str(luta.get(slot) or "").strip()
        if nome:
            desenho_lado.text(
                (x + lado // 2, topo + lado + int(ALTURA * 0.035)), nome.upper(),
                font=fit_font(nome.upper(), fontes["black"], lado,
                              int(ALTURA * 0.062)),
                fill=cor, anchor="mm", stroke_width=5, stroke_fill=(12, 10, 30))

    desenho = ImageDraw.Draw(imagem)
    meio = LARGURA // 2
    desenho.text((meio, int(ALTURA * 0.40)), "VS",
                 font=load_font(fontes["black"], int(ALTURA * 0.17)),
                 fill=(255, 255, 255), anchor="mm",
                 stroke_width=8, stroke_fill=(12, 10, 30))

    # O selo (TITULO EM JOGO, REVANCHE) e o unico texto que diz por que
    # ESTE confronto importa. Sem selo, a capa fica so com o VS.
    selo = ""
    if luta.get("titulo"):
        selo = "TITULO EM JOGO"
    elif luta.get("revanche"):
        selo = "REVANCHE"
    if selo:
        desenho.text((meio, int(ALTURA * 0.62)), selo,
                     font=fit_font(selo, fontes["black"], int(LARGURA * 0.28),
                                   int(ALTURA * 0.055)),
                     fill=(255, 214, 92), anchor="mm",
                     stroke_width=6, stroke_fill=(12, 10, 30))

    caminho = destino or (Path(out_dir) / "capa.png")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(caminho, "PNG", optimize=True)
    if caminho.stat().st_size > PESO_MAXIMO:
        # Acima de 2 MB o YouTube recusa. JPEG no lugar do PNG resolve sem
        # perda visivel numa imagem que sera vista pequena.
        caminho.unlink()
        caminho = caminho.with_suffix(".jpg")
        imagem.save(caminho, "JPEG", quality=88, optimize=True)
    return caminho
