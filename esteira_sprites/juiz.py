"""Juiz consultivo: pergunta por defeitos e registra controles de qualidade."""
from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image, ImageDraw
from ias import correio

from . import config, ficha, prompt

# Quem julga. O Grok respondia mal (Adrian, 02/10/2026); o Gemini ja e os olhos
# dos videos e aceita anexo. O ChatGPT fica livre para gerar as imagens.
JUIZ = "gemini"


def _xadrez(origem: str, destino: Path) -> Path:
    arte = Image.open(origem).convert("RGBA")
    fundo = Image.new("RGBA", arte.size, "#B0B0B0")
    desenho = ImageDraw.Draw(fundo)
    for y in range(0, arte.height, 12):
        for x in range(0, arte.width, 12):
            if (x // 12 + y // 12) % 2:
                desenho.rectangle((x, y, x + 11, y + 11), fill="#D8D8D8")
    fundo.alpha_composite(arte)
    fundo.save(destino, "PNG")
    return destino


def _estragado(origem: str, destino: Path) -> Path:
    """Controle visivel: corta metade da arte para testar o juiz."""
    arte = Image.open(origem).convert("RGBA")
    pixels = arte.load()
    for y in range(arte.height):
        for x in range(arte.width // 2, arte.width):
            pixels[x, y] = (0, 0, 0, 0)
    arte.save(destino, "PNG")
    return destino


def _controle(dados: dict) -> bool:
    return (sum(len(d.get("tentativas", [])) for d in _fichas()) + 1) % 10 == 0


def _fichas() -> list[dict]:
    saida = []
    raiz = config.pasta_do_perfil()
    if not raiz.exists():
        return saida
    for caminho in raiz.glob("*/ficha.json"):
        try:
            saida.append(json.loads(caminho.read_text(encoding="utf-8")))
        except ValueError:
            pass
    return saida


# O que o juiz precisa saber para julgar: o que e o desenho e para que serve.
# Sem isso ele so tinha "notas" soltas e respondia generico (Adrian, 02/10/2026).
JOGO = {
    "palco": ("Neural Fights: jogo de luta automática entre bolinhas guerreiras vistas de cima, "
              "gravado como vídeo vertical para YouTube Shorts e TikTok e assistido no celular."),
    "vila": ("A Vila: tela inicial do app do celular do Neural Fights, uma cidadezinha vista de "
             "frente e levemente de cima, onde cada IA tem um prédio e um habitante (uma bolinha "
             "sem braços e pernas). O app desenha nome, selos e estado por cima da arte."),
}
GRAVIDADE = ("Gravidade: 'grave' = não dá para usar como está (não se lê no tamanho real, foge do "
             "estilo da referência, desenho cortado ou incompleto, linha ou quadro faltando, fundo "
             "ou moldura que não devia existir, coisa diferente do que foi pedido); 'media' = dá "
             "para usar mas se nota (cor fora, contorno falhando, detalhe confuso); 'leve' = "
             "polimento.")


def _tamanho_real(item: dict) -> tuple[int, int] | None:
    """O tamanho em que o desenho aparece na tela do celular, quando o inventario diz."""
    m = re.search(r"no mundo (\d+)x(\d+)(?: \(x(\d+) no celular\))?", str(item.get("tamanho") or ""))
    if not m:
        return None
    escala = int(m.group(3) or 1)
    return int(m.group(1)) * escala, int(m.group(2)) * escala


def _no_tamanho_real(origem: str, tamanho: tuple[int, int], destino: Path) -> Path:
    """O desenho reduzido ao tamanho da tela, sobre a grama da Vila, ampliado 2x sem suavizar."""
    arte = Image.open(origem).convert("RGBA")
    caixa = arte.getbbox() or (0, 0, arte.width, arte.height)
    arte = arte.crop(caixa)
    arte.thumbnail(tamanho, Image.LANCZOS)
    fundo = Image.new("RGBA", (tamanho[0] + 16, tamanho[1] + 16), "#8cc96e")
    fundo.alpha_composite(arte, ((fundo.width - arte.width) // 2, (fundo.height - arte.height) // 2))
    fundo = fundo.resize((fundo.width * 2, fundo.height * 2), Image.NEAREST)
    fundo.save(destino, "PNG")
    return destino


def _pergunta(item: dict, rotulos: list[str]) -> str:
    perfil = item.get("perfil") or config.PERFIL
    linhas = ["PEDIDO DE TEXTO. Você é o diretor de arte que aprova sprites para um jogo.",
              "O JOGO: " + JOGO.get(perfil, JOGO["palco"]),
              f"O QUE É ESTE DESENHO: {str(item.get('descricao') or item['id']).strip()}"]
    tipo = ("folha de animação" if prompt.animacao(item) is not None
            else "folha de quadros" if item.get("tipo") == "folha" else "peça parada")
    linhas.append(f"FORMATO: {tipo}; {item.get('tamanho') or 'tamanho livre'}; fundo transparente "
                  "(o xadrez cinza é só para mostrar a transparência).")
    uso = item.get("presenca_txt") or ""
    if uso:
        linhas.append(f"QUANDO APARECE: {uso}.")
    if item.get("notas"):
        linhas.append(f"OBSERVAÇÃO: {item['notas']}")
    linhas.append("ANEXOS: " + "; ".join(f"{n}) {r}" for n, r in enumerate(rotulos, 1)) + ".")
    linhas.append("PARA QUE SERVE A SUA RESPOSTA: o que você marcar como 'grave' faz o desenho ser "
                  "pedido de novo com os seus defeitos escritos no pedido; sem grave, ele vai para o "
                  "Adrian aprovar. Então seja específico e acionável (onde, o quê, como corrigir).")
    linhas.append("Liste o que está errado PARA ESSE USO; nunca diga só que está bom. " + GRAVIDADE)
    linhas.append('Responda JSON estrito: {"defeitos":[{"o_que":str,"onde":str,"como_corrigir":str,'
                  '"gravidade":"leve|media|grave"}],"notas":{"le_no_tamanho_real":0-3,'
                  '"igual_a_referencia":0-3,"e_o_que_foi_pedido":0-3,"recorte":0-3,'
                  '"continuidade":0-3}} (continuidade só em animação; senão 3).')
    return "\n".join(linhas)


def perguntar(item_id: str) -> bool:
    dados = ficha.ler(item_id)
    if not dados or dados.get("estado") != "medido":
        return False
    item = dados["item"]
    tentativa = dados["tentativas"][-1]
    pasta = ficha.caminho(item_id).parent
    controle = _controle(dados)
    # o controle e cego: o juiz nao sabe que a arte foi estragada de proposito
    limpo = tentativa["caminhos"]["limpo"]
    origem = str(_estragado(limpo, pasta / "controle_estragado.png")) if controle else limpo
    anexos = [str(_xadrez(origem, pasta / "para_juiz.png"))]
    rotulos = ["o desenho em tamanho de entrega"]
    if prompt.animacao(item) is not None:
        gif = tentativa.get("caminhos", {}).get("previa_gif")
        if gif and Path(gif).is_file() and not controle:
            anexos.append(gif)
            rotulos.append("o GIF com os ciclos tocando lado a lado (julgue a ANIMAÇÃO: "
                           "continuidade, base deslizando, pulos de tamanho, partes que somem)")
    tamanho = _tamanho_real(item)
    if tamanho:
        anexos.append(str(_no_tamanho_real(origem, tamanho, pasta / "tamanho_real.png")))
        rotulos.append(f"o desenho no tamanho em que aparece no celular ({tamanho[0]}x{tamanho[1]} px, "
                       "ampliado 2x sem suavizar, sobre a grama): tem de ser legível assim")
    if config.mestra().is_file():
        anexos.append(str(config.mestra()))
        rotulos.append("a imagem-mestra aprovada: o ESTILO a seguir (traço, contorno, sombra, "
                       "cores); não o conteúdo")
    texto = _pergunta(item, rotulos)
    mensagem = correio.enviar(JUIZ, texto, de="esteira_sprites", anexos=anexos)
    tentativa["juiz_id"] = mensagem["id"]
    tentativa["juiz_caixa"] = JUIZ
    tentativa["controle"] = controle
    dados["estado"] = "julgado"
    ficha.registrar(dados, "juiz_pedido", correio_id=mensagem["id"], controle=controle)
    ficha.gravar(dados)
    return True


def _defeito_acionavel(defeito: dict) -> str:
    """O defeito como vai no pedido refeito: o que, onde e como corrigir."""
    texto = str(defeito.get("o_que") or "defeito grave")
    if defeito.get("onde"):
        texto += f" (em {defeito['onde']})"
    if defeito.get("como_corrigir"):
        texto += f": {defeito['como_corrigir']}"
    return texto


def ler_json(texto: str) -> dict | None:
    decodificador = json.JSONDecoder()
    for inicio in (m.start() for m in re.finditer(r"\{", texto or "")):
        try:
            valor, _ = decodificador.raw_decode(texto[inicio:])
            if isinstance(valor, dict) and isinstance(valor.get("defeitos"), list):
                return valor
        except ValueError:
            continue
    return None


def colher(item_id: str) -> bool:
    dados = ficha.ler(item_id)
    if not dados or dados.get("estado") != "julgado":
        return False
    tentativa = dados["tentativas"][-1]
    # fichas antigas nao guardavam a caixa: eram todas do Grok
    mensagem = correio.uma(tentativa.get("juiz_caixa") or "grok", tentativa["juiz_id"])
    if not mensagem or mensagem.get("situacao") not in ("respondida", "falhou"):
        return False
    veredito = ler_json(mensagem.get("resposta") or "") if mensagem["situacao"] == "respondida" else None
    if veredito is None:
        veredito = {"defeitos": [{"o_que": mensagem.get("erro") or "juiz sem JSON", "gravidade": "grave"}], "notas": {}}
    tentativa["veredito"] = veredito
    graves = [_defeito_acionavel(d) for d in veredito["defeitos"] if d.get("gravidade") == "grave"]
    if tentativa.get("controle") and not graves:
        tentativa["juiz_fraco"] = True
        ficha.registrar(dados, "juiz_fraco", motivo="controle sem defeito grave")
    if graves:
        if len(dados["tentativas"]) <= 2:
            from .pedir import pedir
            ficha.gravar(dados)
            pedir(item_id, "; ".join(graves))
            return True
        dados["estado"] = "a_conferir"
    else:
        dados["estado"] = "a_conferir"
    ficha.registrar(dados, "juiz_respondeu", veredito=veredito)
    ficha.gravar(dados)
    return True
