"""Gera o inventario de arte da Vila (docs/vila/inventario_vila.{json,md}).

PEDIDO DO ADRIAN (02/10/2026): "A Vila, pros padroes de agora e com base na
capacidade que temos pra criar, esta muito feia. Vamos repaginar tudo mais
uma vez, quero animacoes validadas e tudo mais." Estilo decidido no Grimorio
(`painel-e-vila/vila-estilo-novo`): o MESMO do Neural -- cartoon, contorno
escuro, 2 tons. Por isso a imagem-mestra da Vila e a do Neural (item 1,
`externo`): a Vila nao pede mestra propria.

Cada item sai do CODIGO da Vila de hoje (`painel/flutuante/arte.py`,
`dados.py`, `vida.py`, `retrato.py`, e a prateleira de `remoto/app`), para o
inventario nao esquecer nada que a tela mostra. Rodar de novo depois de
mudar a Vila:

    python -m esteira_sprites.inventario_vila

O formato de cada item e o do inventario do palco (grupo, subgrupo, id,
descricao, nome_arquivo, tipo, quadros, tamanho, fundo, prioridade, ordem,
existe, caminho_existente, fonte), mais `animacao` nas folhas em ciclo (grade,
ciclos com quadros/fps/loop, ancora) e `chroma`, que a esteira usa direto.
Os textos sao em portugues com acento: vao para o documento e para o prompt.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from painel.flutuante import arte, dados

from . import animacao, config

PASTA_DOC = config.RAIZ_PROJETO / "docs" / "vila"
RAIZ_ARTE = config.PERFIS["vila"].biblioteca
RAIZ_ARTE_TXT = "painel/flutuante/arte_vila/"
MAGENTA, VERDE = "#FF00FF", "#00FF00"

DIRECOES = (("frente", "de frente"),
            ("esquerda", "virado para a esquerda"),
            ("direita", "virado para a direita"),
            ("costas", "de costas"))

NOME_DA_COR = {
    "deepseek": "azul", "chatgpt": "verde-água", "gemini": "azul-claro",
    "picasso": "lilás", "digen": "rosa", "estudio": "laranja",
    "arena": "vermelho", "youtube": "vermelho vivo", "tiktok": "grafite",
    "bot": "violeta", "grok": "cinza-azulado", "casa": "coral",
}
# roxo, lilas, rosa: o chroma magenta comeria a cor -- fundo verde
ROXOS = ("picasso", "digen", "bot")

ACESSORIO = {
    "gorro": "gorro de lã com pompom branco",
    "fones": "fones de ouvido grandes",
    "estrela": "presilha de estrela amarela no cabelo",
    "boina": "boina de pintor",
    "bone": "boné de aba reta",
    "cachecol": "cachecol vermelho",
    "faixa": "faixa de lutador amarrada na testa",
    "capuz": "moletom de capuz com duas listras, ciano e vermelho",
    "antena": "anteninha na cabeça com uma bolinha na ponta",
}
EMBLEMA = {
    "deepseek": "uma baleia azul soltando água",
    "chatgpt": "um nó de três voltas entrelaçadas",
    "gemini": "uma estrela de quatro pontas",
    "picasso": "uma paleta de pintor com um pincel",
    "digen": "uma câmera de cinema antiga",
    "estudio": "uma claquete",
    "arena": "duas espadas cruzadas atrás de um escudo",
    "youtube": "um botão de play arredondado",
    "tiktok": "uma nota musical com eco ciano e vermelho",
    "bot": "um avião de papel",
    "grok": "um foguetinho inclinado",
    "casa": "um coração",
}
TELHADO = {
    "arena": "telhado em cúpula com uma bandeirinha amarela no topo",
    "bot": "telhado de duas águas com uma antena de luz vermelha no lugar da chaminé",
    "casa": "telhado de duas águas sem chaminé e uma floreira cheia na frente da porta",
}

# (nome, prioridade, fps, pose de hoje, o ciclo, quando aparece)
# O habitante e uma BOLINHA do Neural, sem bracos e sem pernas (decisao
# painel-e-vila/vila-habitante-forma, 02/10/2026): tudo e achatar/esticar,
# inclinar e o rosto. O pulo e do codigo: a base fica no chao da celula.
ANIMACOES = (
    ("parado", "P1", 4, "parado (+ olhos fechados ao piscar)",
     "respiração leve no lugar (estica e achata um pouco); no 3º quadro de cada linha ele pisca",
     "sempre que para: na porta, na esquina, no ponto de passeio"),
    ("andar", "P1", 8, "passo1/passo2",
     "quicando no lugar: achata ao tocar o chão, estica ao subir, volta redonda (a altura do pulo é do código)",
     "sempre: é como todo habitante anda pela rua"),
    ("trabalhar", "P2", 8, "trabalhar",
     "concentrado, inclina para a frente no ritmo, com uma ferramenta pequena flutuando ao lado (não tem mãos)",
     "quando o serviço dele trabalha DE VERDADE (estado real) e ao regar o canteiro"),
    ("conversar", "P2", 6, "acenar",
     "inclina de um lado para o outro falando, boca abrindo e fechando, olhos animados",
     "nos encontros da rua, no lago dando comida aos patos e ao animar um amigo"),
    ("triste", "P2", 4, "triste",
     "afunda um pouco achatado, olhar para baixo, um suspiro",
     "quando o prédio dele está com erro (estado real)"),
    ("comemorar", "P3", 8, "feliz",
     "estica para cima e achata no lugar com olhos fechados de alegria e estrelinhas (o pulo é do código)",
     "quando sai uma publicação (festa) e quando acaba um trabalho"),
    ("sentado", "P3", 4, "sentado",
     "acomodado e meio achatado, balançando devagar de um lado para o outro",
     "de folga, no banco da praça"),
)

PRATELEIRA = (
    # (tela, rotulo no app, emoji de hoje, desenho, prioridade, onde)
    ("quadro", "Avisos", "📌", "quadro de cortiça com três papéis presos por tachinhas", "P1", "prateleira"),
    ("diario", "Diário", "📓", "diário de capa de couro com uma fita marcadora", "P1", "prateleira"),
    ("videos", "Cinema", "🎞️", "rolo de filme com a fita saindo", "P1", "prateleira"),
    ("comandos", "Bancada", "🛠️", "martelo e chave inglesa cruzados", "P1", "prateleira"),
    ("relatorios", "Pergaminhos", "📜", "dois pergaminhos enrolados com fita", "P1", "prateleira"),
    ("decisoes", "Grimório", "📖", "grimório: livro grosso de capa roxa com fecho dourado e uma estrela",
     "P1", "prateleira"),
    ("orquestrador", "Mesa de comando", "🗺️", "mapa aberto sobre uma mesinha, com alfinetes", "P1", "prateleira"),
    ("biblioteca", "Biblioteca", "📚", "pilha de três livros coloridos", "P3", "dentro da Mesa de comando"),
    ("coordenador", "Coordenador", "🛰", "satélite com painéis azuis", "P3", "dentro da Mesa de comando"),
    ("oficina", "Oficina do Codex", "(sem ícone)", "bigorna com uma engrenagem em cima", "P3",
     "dentro da Mesa de comando"),
)
DECORACAO = {
    "bandeirolas": ("varal de bandeirolas triangulares coloridas (rosa, amarelo, verde-água, azul, lilás) "
                    "em arco", VERDE, "1024x256 (no mundo 110x16)"),
    "lanterna": ("poste baixo com uma lanterna amarela acesa", MAGENTA, "256x512 (no mundo 12x28)"),
    "balao": ("balão de festa rosa preso por um fio", VERDE, "256x512 (no mundo 14x26)"),
    "gnomo": ("gnomo de jardim de chapéu vermelho, barba branca e roupa azul", MAGENTA,
              "256x384 (no mundo 12x18)"),
    "estatua": ("estátua de estrela dourada sobre um pedestal de pedra", MAGENTA, "256x384 (no mundo 16x22)"),
    "arco": ("arco-íris pequeno de cinco faixas (vermelho, laranja, amarelo, verde, azul)", MAGENTA,
             "512x256 (no mundo 40x16)"),
}


def _chroma(nome: str) -> str:
    return VERDE if nome in ROXOS else MAGENTA


def _fundo(chroma: str) -> str:
    return "verde #00FF00 (o objeto é roxo/rosa)" if chroma == VERDE else "magenta #FF00FF"


def _ciclos_por_direcao(fps: int, loop: bool = True) -> list[dict]:
    return [{"nome": nome, "quadros": [j * 4 + k for k in range(4)], "fps": fps, "loop": loop,
             "descricao": rotulo}
            for j, (nome, rotulo) in enumerate(DIRECOES)]


def _ciclo_unico(nome: str, fps: int, descricao: str, loop: bool = True) -> list[dict]:
    return [{"nome": nome, "quadros": list(range(16)), "fps": fps, "loop": loop,
             "descricao": descricao}]


def _item(**campos) -> dict:
    base = {"grupo": "", "subgrupo": "", "id": "", "descricao": "", "nome_arquivo": "",
            "tipo": "peca", "quadros": 1, "tamanho": "", "fundo": "magenta #FF00FF",
            "chroma": MAGENTA, "prioridade": "P3", "ordem": None, "existe": False,
            "caminho_existente": "", "fonte": "", "arte_atual": "codigo",
            "presenca_txt": "", "bloqueio": "", "opcional": False, "contorno": True,
            "compartilha": "", "notas": ""}
    base.update(campos)
    if base["tipo"] == "folha":
        base["quadros"] = sum(len(c["quadros"]) for c in base["animacao"]["ciclos"])
    if base["fundo"].startswith("opaco"):
        base["chroma"] = ""
        base["contorno"] = False
    return base


# -------------------------------------------------------------------- itens
def _mestra() -> dict:
    return _item(
        grupo="base", subgrupo="estilo", id="imagem_mestra",
        descricao=("Imagem-mestra de estilo: a MESMA do Neural Fights (cartoon, contorno escuro "
                   "#14141A, cel de 2 tons, luz do alto à esquerda). A Vila não tem mestra própria."),
        nome_arquivo="_mestra/aprovada.png (na pasta da esteira, compartilhada com o palco)",
        tamanho="1254x1254 (o que o ChatGPT entrega)", prioridade="P1", arte_atual="nenhuma",
        externo="palco:imagem_mestra", contorno=False,
        caminho_existente="outputs/_ias/esteira_sprites/_mestra/aprovada.png (quando aprovada)",
        fonte="decisoes/painel-e-vila/vila-estilo-novo.json; decisoes/builds/imagem-mestra-v1.json",
        presenca_txt="referência de todo pedido e de todo julgamento",
        notas=("Não é pedida pelo perfil vila: `lote --perfil vila` espera a mestra do Neural "
               "aprovada (a v1 voltou para refazer em 02/10; a v2 está sendo escolhida)."))


def _predio(nome: str) -> dict:
    info = dados.PREDIOS.get(nome, dados.CASA)
    rotulo, faz = info["rotulo"], info["faz"]
    telhado = TELHADO.get(nome, "telhado de duas águas com chaminé")
    cor = arte.CORES.get(nome, arte.COR_RESERVA)
    quem = "A casa da Vila (onde os habitantes descansam)" if nome == "casa" \
        else f"O prédio do {rotulo} ({faz})"
    return _item(
        grupo="predios", subgrupo="casa" if nome == "casa" else "lote", id=f"predio_{nome}",
        descricao=(f"{quem}: casinha cartoon de frente, {telhado}, na cor "
                   f"{NOME_DA_COR.get(nome, '')} ({cor}); paredes creme, porta de madeira no centro "
                   f"embaixo, duas janelas e uma placa redonda branca no alto com o emblema: "
                   f"{EMBLEMA[nome]} (desenho próprio, nunca o logotipo de verdade). Base reta, "
                   "sem chão nem grama em volta."),
        nome_arquivo=f"predios/{nome}.png",
        tamanho="1024x1024 na entrega; o prédio ocupa ~900 px de largura, base reta; no mundo 72x64 (x3 no celular)",
        fundo=_fundo(_chroma(nome)), chroma=_chroma(nome), prioridade="P1",
        caminho_existente=f"painel/flutuante/arte.py desenhar_predio('{nome}') (desenho de código)",
        fonte="painel/flutuante/arte.py LOTES, CORES, _emblema, desenhar_predio; painel/flutuante/dados.py PREDIOS",
        presenca_txt="sempre (app em pé e deitado, janela flutuante)",
        notas=("O nome, a bandeira de conta, o selo de trabalho/erro e o contorno colorido do estado "
               "continuam desenhados pelo código por cima: o estado real manda, e prédio nunca some."))


def _predio_noite(nome: str) -> dict:
    item = _predio(nome)
    item.update(
        id=f"predio_{nome}_noite", subgrupo="noite", prioridade="P2", opcional=True,
        nome_arquivo=f"predios/{nome}_noite.png",
        descricao=(f"O MESMO predio_{nome} de noite: paredes e telhado azulados e escuros, as duas "
                   "janelas acesas em amarelo quente, a placa do emblema clara."),
        presenca_txt="das 19h às 6h (e_noite em painel/flutuante/cena.py)",
        notas=("Opcional: hoje o código escurece a arte do dia e acende as janelas por cima "
               "(_escurecer_imagem). A peça própria só se o escurecido ficar feio; a IA tende a "
               "desenhar OUTRO prédio, então exige conferir lado a lado com o de dia."))
    return item


def _habitante(nome: str, anim: tuple) -> dict:
    acao, prio, fps, pose_hoje, ciclo, quando = anim
    info = dados.PREDIOS[nome]
    cor = arte.CORES[nome]
    acessorio = ACESSORIO.get(arte.ACESSORIOS.get(nome, ""), "")
    return _item(
        grupo="habitantes", subgrupo=nome, id=f"habitante_{nome}_{acao}",
        descricao=(f"Habitante do {info['rotulo']} ({info['faz']}): uma BOLINHA redonda como os "
                   f"lutadores do Neural Fights, SEM braços e SEM pernas, corpo {NOME_DA_COR[nome]} "
                   f"({cor}), {acessorio}, rosto expressivo com olhos grandes e bochechas rosadas. "
                   f"Animação '{acao}': {ciclo}. A mesma bolinha em todas as folhas dela."),
        nome_arquivo=f"habitantes/{nome}/{acao}.png", tipo="folha",
        tamanho=("folha 1024x1024 (célula 256x256); bolinha com ~180 px de diâmetro, base a ~24 px "
                 "do pé da célula; no mundo 26x32 (x3 no celular)"),
        fundo=_fundo(_chroma(nome)), chroma=_chroma(nome), prioridade=prio,
        animacao={"ciclo": True, "grade": [4, 4], "ancora": "pes", "escala": False,
                  "ciclos": _ciclos_por_direcao(fps)},
        caminho_existente=f"painel/flutuante/arte.py desenhar_personagem('{nome}', pose={pose_hoje}) (desenho de código)",
        fonte="painel/flutuante/arte.py CORES, ACESSORIOS, PELES; painel/flutuante/vida.py Vida.pose; remoto/vila_nova.py POSES",
        presenca_txt=quando,
        notas=("Hoje só há esquerda e direita (espelhada); a folha traz as 4 direções porque o habitante "
               "também sobe e desce as travessas. O passeio anda a 34 px/s no mundo: o código casa o "
               "passo com o fps para o pé não deslizar no chão."))


def _cenario() -> list[dict]:
    i = []
    i.append(_item(
        grupo="cenario", subgrupo="chao", id="chao_grama", prioridade="P1",
        descricao=("Grama vista de cima, verde-clara (de #a4d77e a #7cc265), com tufos, manchas suaves "
                   "de luz e algumas florzinhas pequenas; textura contínua."),
        nome_arquivo="cenario/chao_grama.png", fundo="opaco (textura que emenda)",
        tamanho="512x512 que emenda nos 4 lados (o código ladrilha o mundo de 704x240)",
        caminho_existente="painel/flutuante/arte.py desenhar_chao (degradê + tufos + flores)",
        fonte="painel/flutuante/arte.py desenhar_chao, GRAMA_TOPO, GRAMA_BASE",
        presenca_txt="sempre: é o fundo do mundo inteiro"))
    i.append(_item(
        grupo="cenario", subgrupo="chao", id="caminho_terra", prioridade="P1",
        descricao="Terra batida clara (#f0dab0) com pedrinhas, vista de cima; textura contínua.",
        nome_arquivo="cenario/caminho_terra.png", fundo="opaco (textura que emenda)",
        tamanho="512x512 que emenda nos 4 lados",
        caminho_existente="painel/flutuante/arte.py desenhar_chao (ruas, travessas e calçadas)",
        fonte="painel/flutuante/arte.py RUA_Y, TRAVESSAS_X, portas()",
        presenca_txt="sempre: as duas ruas, as duas travessas e a calçada de cada porta",
        notas="O código recorta a textura no formato das ruas e desenha a borda mais escura (#d9b98a)."))
    i.append(_item(
        grupo="cenario", subgrupo="natureza", id="arvore_frutinhas", prioridade="P2",
        descricao=("Árvore cartoon de copa redonda (três bolas de folhagem verde), tronco curto "
                   "marrom e três frutinhas vermelhas; base reta, sem grama."),
        nome_arquivo="cenario/arvore.png", tamanho="512x640 (no mundo 36x44)",
        caminho_existente="painel/flutuante/arte.py desenhar_arvore", fonte="painel/flutuante/arte.py ARVORES",
        presenca_txt=f"sempre: {len(arte.ARVORES)} árvores no mundo, mais as do campo do celular",
        notas="O código varia o tom por árvore (ARVORES); a arte é uma só."))
    i.append(_item(
        grupo="cenario", subgrupo="natureza", id="lago", prioridade="P2",
        descricao=("Lago oval visto de cima com borda de grama clara, água azul com dois reflexos "
                   "brancos, duas vitórias-régias e uma florzinha rosa-clara."),
        nome_arquivo="cenario/lago.png", tamanho="1024x704 (no mundo 68x46)",
        caminho_existente="painel/flutuante/arte.py desenhar_chao (bloco do lago)",
        fonte="painel/flutuante/arte.py LAGO", presenca_txt="sempre (os patos nadam nele)"))
    i.append(_item(
        grupo="cenario", subgrupo="praca", id="fonte", prioridade="P2", tipo="folha",
        descricao=("Fonte de pedra lilás-acinzentada (#c9c2d6) da praça: bacia redonda com água azul "
                   "e três jatos que sobem e caem."),
        nome_arquivo="cenario/fonte.png",
        tamanho="folha 1024x1024 (célula 256x256); no mundo 40x30",
        animacao={"ciclo": True, "grade": [4, 4], "ancora": "base", "escala": False,
                  "ciclos": _ciclo_unico("agua", 10, "os jatos sobem e caem; a pedra fica parada")},
        caminho_existente="painel/flutuante/arte.py desenhar_fonte(quadro 0..2)",
        fonte="painel/flutuante/arte.py FONTE, desenhar_fonte; painel/flutuante/cena.py _animar_ambiente",
        presenca_txt="sempre: o centro da praça (é onde estoura o confete da festa)",
        notas="A escala não é medida: os jatos mudam a altura de propósito. A base da pedra é a âncora."))
    i.append(_item(
        grupo="cenario", subgrupo="praca", id="banco", prioridade="P2",
        descricao="Banco de praça de madeira com encosto, de frente.",
        nome_arquivo="cenario/banco.png", tamanho="512x320 (no mundo 26x16)",
        caminho_existente="painel/flutuante/arte.py desenhar_banco", fonte="painel/flutuante/arte.py BANCO",
        presenca_txt="sempre (ponto de passeio 'banco')"))
    i.append(_item(
        grupo="cenario", subgrupo="praca", id="canteiro", prioridade="P2",
        descricao="Canteiro de madeira com terra e sete flores coloridas (rosa, amarela, lilás, vermelha).",
        nome_arquivo="cenario/canteiro.png", fundo=_fundo(VERDE), chroma=VERDE,
        tamanho="640x352 (no mundo 34x18)",
        caminho_existente="painel/flutuante/arte.py desenhar_canteiro", fonte="painel/flutuante/arte.py CANTEIRO",
        presenca_txt="sempre (ponto de passeio 'canteiro': regar)"))
    i.append(_item(
        grupo="cenario", subgrupo="natureza", id="moita_florida", prioridade="P2",
        descricao="Moita redonda verde com florzinhas brancas e amarelas.",
        nome_arquivo="cenario/moita.png", tamanho="384x256",
        caminho_existente="painel/flutuante/retrato.py desenhar_sebe (moitas redondas)",
        fonte="painel/flutuante/retrato.py desenhar_sebe",
        presenca_txt="celular em pé: a sebe entre as duas fileiras da Vila",
        notas="O código enfileira a moita para fazer a sebe; só flores brancas e amarelas (o fundo é magenta)."))
    i.append(_item(
        grupo="cenario", subgrupo="ceu", id="nuvem", prioridade="P3",
        descricao="Nuvem branca fofa de três bolotas, com a sombra de baixo azulada.",
        nome_arquivo="cenario/nuvem.png", tamanho="512x256",
        caminho_existente="painel/flutuante/retrato.py _nuvem", fonte="painel/flutuante/retrato.py NUVENS",
        presenca_txt="celular (céu do retrato e da paisagem)"))
    i.append(_item(
        grupo="cenario", subgrupo="ceu", id="morro", prioridade="P3", opcional=True,
        descricao="Morro verde arredondado visto de longe, base reta.",
        nome_arquivo="cenario/morro.png", tamanho="1024x384",
        caminho_existente="painel/flutuante/retrato.py desenhar_ceu (elipses)",
        fonte="painel/flutuante/retrato.py MORROS_LONGE, MORROS_PERTO",
        presenca_txt="celular (horizonte do céu)", notas="Opcional: as elipses de código já servem."))
    i.append(_item(
        grupo="cenario", subgrupo="ceu", id="lua", prioridade="P3",
        descricao="Lua crescente amarelo-clara (#fff3c4), sem brilho em volta.",
        nome_arquivo="cenario/lua.png", tamanho="256x256",
        caminho_existente="painel/flutuante/retrato.py desenhar_ceu (lua crescente)",
        fonte="painel/flutuante/retrato.py LUA", presenca_txt="celular, de noite"))
    i.append(_item(
        grupo="cenario", subgrupo="praca", id="placa_voltar", prioridade="P3",
        descricao="Placa de madeira num poste, em forma de seta para a esquerda, sem letras.",
        nome_arquivo="cenario/placa.png", tamanho="256x320 (no mundo 22x26)",
        caminho_existente="painel/flutuante/retrato.py desenhar_placa",
        fonte="painel/flutuante/retrato.py desenhar_placa", presenca_txt="celular em pé (campo extra)"))
    i.append(_item(
        grupo="cenario", subgrupo="natureza", id="arvore_vento", prioridade="P3", tipo="folha",
        opcional=True,
        descricao="A arvore_frutinhas balançando ao vento: a copa oscila, o tronco fica parado.",
        nome_arquivo="cenario/arvore_vento.png", tamanho="folha 1024x1024 (célula 256x256)",
        animacao={"ciclo": True, "grade": [4, 4], "ancora": "pes", "escala": True,
                  "ciclos": _ciclo_unico("vento", 8, "a copa vai e volta; o pé do tronco não se mexe")},
        caminho_existente="", arte_atual="nenhuma", fonte="(novo: hoje a árvore é parada)",
        presenca_txt="sempre, se entrar", notas="Opcional: só se a Vila parada parecer morta."))
    i.append(_item(
        grupo="cenario", subgrupo="natureza", id="lago_brilho", prioridade="P3", tipo="folha",
        opcional=True,
        descricao="Reflexos brancos deslizando na água do lago (só os reflexos, sem o lago).",
        nome_arquivo="cenario/lago_brilho.png", tamanho="folha 1024x1024 (célula 256x256)",
        animacao={"ciclo": True, "grade": [4, 4], "ancora": "centro", "escala": False,
                  "ciclos": _ciclo_unico("brilho", 6, "os reflexos passeiam e voltam ao começo")},
        caminho_existente="", arte_atual="nenhuma", fonte="(novo)", contorno=False,
        presenca_txt="sempre, se entrar", notas="Opcional. Sem contorno (é luz na água)."))
    return i


def _bichos() -> list[dict]:
    i = []
    i.append(_item(
        grupo="bichos", subgrupo="lago", id="pato_nadar", prioridade="P2", tipo="folha",
        descricao="Patinho branco de bico laranja nadando (só o corpo acima da água).",
        nome_arquivo="bichos/pato.png", tamanho="folha 1024x1024 (célula 256x256); no mundo 14x11",
        animacao={"ciclo": True, "grade": [4, 4], "ancora": "centro", "escala": True,
                  "ciclos": _ciclos_por_direcao(4)},
        caminho_existente="painel/flutuante/arte.py desenhar_pato(quadro 0..1); remoto/vila_nova.py atlas (patos)",
        fonte="painel/flutuante/cena.py _animar_ambiente; remoto/app/vila.js vilaPatos",
        presenca_txt="sempre: dois patos dando voltas no lago",
        notas="Balançando na água, a cabeça sobe e desce; as 4 direções porque a volta no lago é oval."))
    gato = [{"nome": "andar_direita", "quadros": [0, 1, 2, 3], "fps": 8, "loop": True,
             "descricao": "andando para a direita"},
            {"nome": "andar_esquerda", "quadros": [4, 5, 6, 7], "fps": 8, "loop": True,
             "descricao": "andando para a esquerda"},
            {"nome": "sentado", "quadros": [8, 9, 10, 11], "fps": 4, "loop": True,
             "descricao": "sentado, mexendo o rabo"},
            {"nome": "dormindo", "quadros": [12, 13, 14, 15], "fps": 2, "loop": True,
             "descricao": "enrolado dormindo, respirando"}]
    i.append(_item(
        grupo="bichos", subgrupo="visitante", id="gato", prioridade="P3", tipo="folha",
        descricao="Gatinho laranja de patas e focinho claros.",
        nome_arquivo="bichos/gato.png", tamanho="folha 1024x1024 (célula 256x256); no mundo 22x14",
        animacao={"ciclo": True, "grade": [4, 4], "ancora": "pes", "escala": True, "ciclos": gato},
        caminho_existente="painel/flutuante/arte.py desenhar_gato(quadro 0..1)",
        fonte="painel/flutuante/cena.py _animar_visitante",
        presenca_txt="de vez em quando (15 a 40 s) atravessa a rua de baixo, só na janela flutuante"))
    passaro = [{"nome": "voar_direita", "quadros": [0, 1, 2, 3], "fps": 10, "loop": True,
                "descricao": "voando para a direita, batendo as asas"},
               {"nome": "voar_esquerda", "quadros": [4, 5, 6, 7], "fps": 10, "loop": True,
                "descricao": "voando para a esquerda, batendo as asas"},
               {"nome": "pousado_bicando", "quadros": [8, 9, 10, 11], "fps": 6, "loop": True,
                "descricao": "pousado, bicando o chão"},
               {"nome": "pousado_olhando", "quadros": [12, 13, 14, 15], "fps": 3, "loop": True,
                "descricao": "pousado, virando a cabeça"}]
    i.append(_item(
        grupo="bichos", subgrupo="visitante", id="passaro", prioridade="P3", tipo="folha",
        descricao="Passarinho azul-claro de bico laranja.",
        nome_arquivo="bichos/passaro.png", tamanho="folha 1024x1024 (célula 256x256); no mundo 14x10",
        animacao={"ciclo": True, "grade": [4, 4], "ancora": "centro", "escala": False, "ciclos": passaro},
        caminho_existente="painel/flutuante/arte.py desenhar_passaro(quadro 0..1)",
        fonte="painel/flutuante/cena.py _animar_visitante",
        presenca_txt="de vez em quando cruza o céu, só na janela flutuante",
        notas="A escala não é medida: as asas mudam a altura de propósito."))
    i.append(_item(
        grupo="bichos", subgrupo="noite", id="vagalume", prioridade="P3",
        descricao="Vagalume: bolinha amarelo-clara com duas asinhas.",
        nome_arquivo="bichos/vagalume.png", tamanho="128x128 (no mundo 10x10)",
        caminho_existente="painel/flutuante/arte.py desenhar_vagalume",
        fonte="painel/flutuante/cena.py _vagalumes", presenca_txt="janela flutuante, de noite (12 vagalumes)",
        notas="O brilho em volta é do código; a peça é só o bichinho."))
    return i


def _interface() -> list[dict]:
    i = []
    i.append(_item(
        grupo="interface", subgrupo="balao", id="balao_emote", prioridade="P2",
        descricao="Balãozinho de pensamento branco, redondo, com rabicho embaixo, VAZIO.",
        nome_arquivo="interface/balao_emote.png", tamanho="256x288 (no mundo 22x26)",
        caminho_existente="painel/flutuante/arte.py emote; remoto/app/vila.js vilaBalao",
        fonte="painel/flutuante/vida.py PONTOS, PAPO",
        presenca_txt="o tempo todo: emotes de passeio, de papo e da festa",
        notas="O emoji continua do código, dentro do balão (sem texto no sprite)."))
    i.append(_item(
        grupo="interface", subgrupo="predio", id="fumaca_chamine", prioridade="P2", tipo="folha",
        descricao="Fumacinha branca de chaminé (só a fumaça), subindo em bolinhas que somem.",
        nome_arquivo="interface/fumaca.png", tamanho="folha 1024x1024 (célula 256x256)",
        animacao={"ciclo": True, "grade": [4, 4], "ancora": "base", "escala": False,
                  "ciclos": _ciclo_unico("subir", 8, "as bolinhas sobem e somem; a de baixo nasce de novo")},
        caminho_existente="", arte_atual="nenhuma",
        fonte="(novo) o estado 'trabalhando' de painel/flutuante/dados.py estado_dos_predios",
        presenca_txt="na chaminé do prédio que está trabalhando",
        notas="A escala não é medida (a fumaça cresce de propósito). Reforça o estado real, não o substitui."))
    i.append(_item(
        grupo="interface", subgrupo="festa", id="confete", prioridade="P3", tipo="folha", opcional=True,
        descricao="Confete colorido estourando para cima e caindo (pedacinhos retangulares).",
        nome_arquivo="interface/confete.png", tamanho="folha 1024x1024 (célula 256x256)",
        animacao={"ciclo": True, "grade": [4, 4], "ancora": "livre", "escala": False,
                  "ciclos": _ciclo_unico("estouro", 12, "estoura no 1º quadro e cai até sumir", loop=False)},
        caminho_existente="painel/flutuante/cena.py festa (retângulos de código)",
        fonte="painel/flutuante/cena.py festa", presenca_txt="quando sai uma publicação",
        notas="Opcional: as partículas de código já servem."))
    for nome in arte.DECORACOES:
        desenho, chroma, tamanho = DECORACAO[nome]
        i.append(_item(
            grupo="interface", subgrupo="colecao", id=f"enfeite_{nome}", prioridade="P3",
            descricao=f"Enfeite da coleção da Vila: {desenho}.",
            nome_arquivo=f"enfeites/{nome}.png", tamanho=tamanho, fundo=_fundo(chroma), chroma=chroma,
            caminho_existente=f"painel/flutuante/arte.py desenhar_decoracao('{nome}')",
            fonte="painel/flutuante/arte.py DECORACOES, LUGAR_DAS_DECORACOES",
            presenca_txt="janela flutuante, conforme as publicações desbloqueiam a coleção"))
    for tela, rotulo, emoji, desenho, prio, onde in PRATELEIRA:
        chroma = VERDE if tela == "decisoes" else MAGENTA
        i.append(_item(
            grupo="objetos", subgrupo="prateleira" if onde == "prateleira" else "mesa",
            id=f"objeto_{tela}", prioridade=prio,
            descricao=f"Ícone do objeto '{rotulo}' do app: {desenho}. Silhueta simples, legível a 28 px.",
            nome_arquivo=f"objetos/{tela}.png", tamanho="512x512 (aparece com ~28 px no celular)",
            fundo=_fundo(chroma), chroma=chroma, arte_atual="emoji",
            caminho_existente=f"remoto/app/index.html (emoji {emoji})",
            fonte="remoto/app/index.html nav.prateleira; remoto/app/app.js TITULOS",
            presenca_txt=("sempre: a prateleira embaixo da Vila no app" if onde == "prateleira"
                          else "botão dentro da Mesa de comando"),
            notas="Pequeno de propósito: com 28 px, detalhe miúdo não aparece."))
    return i


def montar() -> list[dict]:
    """Todos os itens, ja na ordem de producao (campo `ordem`)."""
    nomes = list(arte.LOTES)
    # o primeiro habitante calibra o validador de animacao antes dos outros
    primeiro = "chatgpt"
    todos = [primeiro] + [n for n in nomes if n != primeiro]
    cenario, bichos, interface = _cenario(), _bichos(), _interface()
    p1 = [_mestra(), _predio("casa"),
          _habitante(primeiro, ANIMACOES[0]), _habitante(primeiro, ANIMACOES[1])]
    p1 += [c for c in cenario if c["prioridade"] == "P1"]
    for nome in nomes:
        p1.append(_predio(nome))
        if nome != primeiro:
            p1 += [_habitante(nome, ANIMACOES[0]), _habitante(nome, ANIMACOES[1])]
    p1 += [x for x in interface if x["prioridade"] == "P1"]
    p2 = [_habitante(nome, anim) for anim in ANIMACOES if anim[1] == "P2" for nome in todos]
    p2 += [c for c in cenario if c["prioridade"] == "P2"]
    p2 += [b for b in bichos if b["prioridade"] == "P2"]
    p2 += [x for x in interface if x["prioridade"] == "P2"]
    p2 += [_predio_noite(n) for n in ["casa"] + nomes]
    p3 = [_habitante(nome, anim) for anim in ANIMACOES if anim[1] == "P3" for nome in todos]
    p3 += [b for b in bichos if b["prioridade"] == "P3"]
    p3 += [c for c in cenario if c["prioridade"] == "P3"]
    p3 += [x for x in interface if x["prioridade"] == "P3"]
    itens = p1 + p2 + p3
    for n, item in enumerate(itens, 1):
        item["ordem"] = n
        if not item.get("externo"):
            item["existe"] = (RAIZ_ARTE / item["nome_arquivo"]).is_file()
            if item["existe"]:
                item["arte_atual"] = "ia"
                item["caminho_existente"] = RAIZ_ARTE_TXT + item["nome_arquivo"]
    return itens


# ------------------------------------------------------------------- totais
def _conta(lista: list[dict]) -> dict:
    c = Counter()
    for i in lista:
        c["total"] += 1
        c[i["tipo"]] += 1
        c["opcional"] += bool(i.get("opcional"))
        c["externo"] += bool(i.get("externo"))
        c["existe"] += bool(i.get("existe"))
        c["ciclos"] += len((i.get("animacao") or {}).get("ciclos", []))
    return {k: v for k, v in sorted(c.items()) if v}


def totais(itens: list[dict]) -> dict:
    por_grupo = defaultdict(dict)
    for g in dict.fromkeys(i["grupo"] for i in itens):
        for p in ("P1", "P2", "P3"):
            por_grupo[g][p] = _conta([i for i in itens if i["grupo"] == g and i["prioridade"] == p])
    return {"geral": _conta(itens),
            "por_prioridade": {p: _conta([i for i in itens if i["prioridade"] == p])
                               for p in ("P1", "P2", "P3")},
            "por_grupo": dict(por_grupo)}


CONVENCOES = {
    "estilo": ("`decisoes/painel-e-vila/vila-estilo-novo.json` = mesmo estilo do Neural: cartoon, contorno "
               "#14141A, cel de 2 tons, luz do alto à esquerda. A imagem-mestra é a do Neural (item 1)."),
    "raiz": (f"`nome_arquivo` é relativo a `{RAIZ_ARTE_TXT}` (config.PERFIS['vila'].biblioteca); "
             "a pasta `vila/` da raiz foi aposentada (nó `aposentar-vila-pixel`)."),
    "fundo": ("magenta #FF00FF liso; verde #00FF00 quando o objeto é roxo/lilás/rosa (Picasso, Digen, Bot, "
              "canteiro, balão, bandeirolas, Grimório); chão e caminho são texturas opacas que emendam."),
    "folhas": ("toda animação é folha 4x4 (16 quadros). Personagens e pato: cada LINHA é um ciclo de 4 "
               "quadros numa direção (1 frente, 2 esquerda, 3 direita, 4 costas). Gato e pássaro: cada "
               "linha é um ciclo diferente. Fonte, fumaça, confete e vento: um ciclo só de 16 quadros."),
    "ancora": ("pes = os pés no mesmo ponto em todo quadro (personagens, gato, árvore); base = o pé do "
               "objeto fica (fonte, fumaça); centro = o centro de massa fica (pato, pássaro, brilho); "
               "livre = não mede (confete)."),
    "prioridade": ("P1: aparece SEMPRE na tela do app (prédios, habitantes parados e andando, chão, "
                   "caminho, prateleira). P2: sempre no mundo mas secundário, ou estado real frequente "
                   "(trabalhar, erro, papo). P3: ocasional (festa, visitantes, coleção, céu do celular)."),
    "validador": ("`esteira_sprites/animacao.py` (limites em LIMITES; calibrar com as primeiras folhas "
                  "reais)."),
}


def documento(itens: list[dict], gerado_em: str) -> dict:
    return {"gerado_em": gerado_em, "tarefa": "49e52521", "perfil": "vila",
            "convencoes": CONVENCOES, "limites_do_validador": dict(animacao.LIMITES),
            "totais": totais(itens), "itens": itens}


# ----------------------------------------------------------------- markdown
def _ciclos_txt(item: dict) -> str:
    anim = item.get("animacao")
    if not anim:
        return ""
    partes = [f"{c['nome']} {len(c['quadros'])}q {c['fps']} fps{', laço' if c['loop'] else ', sem laço'}"
              for c in anim["ciclos"]]
    medida = f"âncora {anim['ancora']}" + ("" if anim.get("escala", True) else ", sem escala")
    return "; ".join(partes) + f" ({medida})"


def markdown(doc: dict) -> str:
    itens = doc["itens"]
    t = doc["totais"]
    g = t["geral"]
    linhas = [
        "# Inventário de arte da Vila",
        "",
        f"Tarefa {doc['tarefa']}, pedido do Adrian de 02/10/2026: \"A Vila, pros padrões de agora e com "
        "base na capacidade que temos pra criar, está muito feia. Vamos repaginar tudo mais uma vez, quero "
        f"animações validadas e tudo mais.\" Gerado em {doc['gerado_em'][:16].replace('T', ' ')} por "
        "`python -m esteira_sprites.inventario_vila`, a partir do código da Vila de hoje (o campo `fonte` "
        "de cada item diz de onde saiu). A versão para máquina é [`inventario_vila.json`](inventario_vila.json); "
        "a esteira lê com `python -m esteira_sprites --perfil vila ...`.",
        "",
        "## Resumo",
        "",
        f"- **{g['total']} itens**: {g.get('folha', 0)} folhas animadas e {g.get('peca', 0)} peças paradas, "
        f"com {g.get('ciclos', 0)} ciclos de animação no total.",
        f"- **{g.get('opcional', 0)} opcionais** (o código de hoje já cobre) e **{g.get('externo', 0)} externo**: "
        "a imagem-mestra, que é a do Neural.",
        f"- **Já existem {g.get('existe', 0)}**: a Vila de hoje é toda desenho de código "
        "(`painel/flutuante/arte.py`) ou emoji (a prateleira do app).",
        "- **Estilo**: o mesmo do Neural (decisão `painel-e-vila/vila-estilo-novo`). A Vila não pede mestra "
        "própria: `lote --perfil vila` espera a mestra do Neural aprovada.",
        "",
        "| prioridade | total | folhas | peças | ciclos | opcionais |",
        "|---|---|---|---|---|---|",
    ]
    for p in ("P1", "P2", "P3"):
        c = t["por_prioridade"][p]
        linhas.append(f"| {p} | {c.get('total', 0)} | {c.get('folha', 0)} | {c.get('peca', 0)} | "
                      f"{c.get('ciclos', 0)} | {c.get('opcional', 0)} |")
    linhas.append(f"| **todas** | {g['total']} | {g.get('folha', 0)} | {g.get('peca', 0)} | "
                  f"{g.get('ciclos', 0)} | {g.get('opcional', 0)} |")
    linhas += ["", "| grupo | P1 | P2 | P3 | total |", "|---|---|---|---|---|"]
    for grupo, ps in t["por_grupo"].items():
        n = [ps[p].get("total", 0) for p in ("P1", "P2", "P3")]
        linhas.append(f"| {grupo} | {n[0]} | {n[1]} | {n[2]} | {sum(n)} |")
    linhas += ["", "**Os 10 primeiros da ordem de produção** (a lista inteira está em \"Itens\" e no "
               "campo `ordem` do JSON):", ""]
    for item in itens[:10]:
        desc = item["descricao"]
        linhas.append(f"{item['ordem']}. `{item['id']}` ({item['prioridade']}, {item['tipo']}): "
                      f"{desc[:150]}{'…' if len(desc) > 150 else ''}")
    linhas += ["", "## Como ler", ""]
    for chave, valor in doc["convencoes"].items():
        linhas.append(f"- **{chave}**: {valor}")
    linhas += [
        "",
        "**O que continua no código, de propósito** (o estado real vence a animação, e prédio nunca some): "
        "o nome de cada prédio e o contorno colorido do estado, a bandeira de conta em uso, o selo de "
        "trabalho/erro, o balão de texto do trabalho embaixo do habitante, o emoji dentro do balão, as "
        "sombras, o céu em degradê, as estrelas e o escurecer da noite.",
        "",
        "## O validador de animação",
        "",
        "Toda folha com `animacao.ciclo` passa por `esteira_sprites/animacao.py` no portão, ciclo a ciclo, "
        "antes do Grok. Reprova com o número medido:",
        "",
        "| o quê | como mede | limite |",
        "|---|---|---|",
        f"| quadros | células com ≥ {animacao.AREA_MIN} px de alfa contra as dos ciclos | exato |",
        f"| âncora (pes/base) | centróide da faixa de baixo ({animacao.FAIXA_DOS_PES:.0%} da altura) e a "
        f"linha do chão | x: {animacao.ANCORA_X_MAX:.0%} da altura; chão: {animacao.ANCORA_Y_MAX:.0%} "
        f"(piso {animacao.ANCORA_MIN_PX:.0f} px) |",
        f"| âncora (centro) | centro de massa do alfa | {animacao.CENTRO_MAX:.0%} da altura |",
        f"| escala | altura do alfa entre quadros vizinhos | {animacao.ESCALA_MAX:.0%} |",
        f"| paleta | histograma 3 bits/canal de cada quadro contra a média do ciclo | {animacao.PALETA_MAX:.2f} |",
        f"| loop | último→primeiro contra a troca mediana do ciclo | {animacao.LOOP_FATOR:.0f}x "
        f"(piso {animacao.LOOP_MIN}) |",
        f"| congelado | trocas com diferença < {animacao.REPETIDO_MAX} | {animacao.CONGELADO_MAX:.0%} das trocas |",
        f"| contorno | perímetro sem pixel escuro (luma ≤ {animacao.CONTORNO_LUMA}) a {animacao.CONTORNO_RAIO} px "
        f"| {animacao.CONTORNO_FALTA_MAX:.0%} do perímetro |",
        "",
        "A prévia (GIF e WebP) toca os ciclos lado a lado e vai junto com a folha para o Grok, com a "
        "pergunta \"liste o que está errado NA ANIMAÇÃO\".",
        "",
        "## Itens",
    ]
    grupo_atual = None
    for item in itens:
        if item["grupo"] != grupo_atual:
            grupo_atual = item["grupo"]
            linhas += ["", f"### {grupo_atual}", "",
                       "| ordem | id | prio | tipo | o quê | arquivo | ciclos | tamanho | fundo | hoje | onde aparece |",
                       "|---|---|---|---|---|---|---|---|---|---|---|"]
        extra = " (opcional)" if item.get("opcional") else ""
        extra += " (externo)" if item.get("externo") else ""
        linhas.append(
            f"| {item['ordem']} | `{item['id']}`{extra} | {item['prioridade']} | {item['tipo']} | "
            f"{item['descricao']} | `{item['nome_arquivo']}` | {_ciclos_txt(item)} | {item['tamanho']} | "
            f"{item['fundo']} | {item['caminho_existente'] or item['arte_atual']} | {item['presenca_txt']} |")
    return "\n".join(linhas) + "\n"


def gravar(pasta: Path = PASTA_DOC) -> dict:
    doc = documento(montar(), datetime.now().isoformat(timespec="seconds"))
    pasta.mkdir(parents=True, exist_ok=True)
    # newline: o .gitattributes pede LF, e o write_text do Windows poria CRLF
    (pasta / "inventario_vila.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (pasta / "inventario_vila.md").write_text(markdown(doc), encoding="utf-8", newline="\n")
    return doc


if __name__ == "__main__":
    resultado = gravar()
    print(json.dumps(resultado["totais"]["geral"], ensure_ascii=False))
