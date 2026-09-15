# -*- coding: utf-8 -*-
"""Uma IA olha o video ANTES de ele sair, e o veto dela vale.

Pedido dele em 11/09/2026: "passar o video no gemini antes de postar para
saber o que ele acha, e postar apenas se ele der um comando correto; caso ele
de um comando negativo o texto vem pra esse chat".

O QUE VAI E O MP4 INTEIRO, e chegar ate isso custou tres tentativas
falhadas — todas com a mesma mensagem inutil, "cliquei em enviar mas nada
mudou na tela". Duas coisas separam anexar video de anexar arquivo, e ignorar
qualquer uma delas quebra em silencio:

    CONSENTIMENTO   o Gemini abre um dialogo MODAL de direitos autorais a
                    cada video. Com ele aberto, o botao de enviar existe,
                    reporta `disabled: false` e o clique nao faz nada.
    A DURACAO       a prova de que subiu nao e a miniatura, que aparece em
                    ~10 s: e a duracao (`1:47`) ao lado do nome do arquivo,
                    em ~30 s. Perguntar entre uma e outra faz o modelo
                    responder sobre um video que ele nao recebeu — e a
                    resposta parece boa.

O atributo `accept` do input NAO lista extensao de video, e foi por isso que
a primeira leitura deste modulo concluiu que o Gemini nao aceitava mp4. Ele
aceita: `accept` e filtro do seletor de arquivos do sistema, e
`set_input_files` passa por cima dele. Conclusao tirada de atributo, sem
tentar, custou meio caminho errado.

A FOLHA DE CONTATO ficou como RESERVA. E um mosaico com doze quadros do video
numa imagem so; quando o mp4 nao sobe (conta, tamanho, o site mudou), ela
ainda responde pela parte visual em vez de o video sair sem parecer nenhum.
O que ela nao mostra e movimento e audio.

O ChatGPT nao serve para isto nesta maquina: o input aceita `image/*,video/*`
mas a conta e FREE, e o mp4 entra como "Arquivo" opaco.

O CONTRATO DA RESPOSTA e uma palavra na primeira linha, `APROVADO` ou
`REPROVADO`. Nao e capricho: sem uma palavra fechada, ler "acho que esta bom,
mas..." vira adivinhacao, e o veto tem de ser mecanico.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

COLUNAS, LINHAS = 3, 4
QUADROS = COLUNAS * LINHAS
LARGURA_DO_QUADRO = 300
# Acima disto o Gemini demora a processar e as vezes recusa. A folha inteira
# em 900x2130 fica em ~400 KB, e o modelo le cada quadro sem esforco.
QUALIDADE = 82

APROVADO = "APROVADO"
REPROVADO = "REPROVADO"

# A VERSAO DO CRITERIO. Sobe quando o prompt passa a julgar diferente, para
# veto dado com a regua antiga ser perguntado de novo em vez de guiar
# conserto. 2 = 13/09/2026, 23h50: imagem so reprova por CONTRADIZER a
# narracao, nao por deixar detalhe de fora. Com a regua 1, a revisao da
# madrugada reprovou 11 de 11 videos do estoque, 25 das 34 cenas por detalhe
# (o gesto, o objeto na mao, a expressao, um personagem secundario).
CRITERIO = 2


# O veredito da IA fica GRAVADO, com a data do mp4 junto. Sem isso, o freio
# de estoque e o reparo teriam de perguntar de novo para saber — 100 s e um
# navegador por video, oito vezes por dia — ou, o que aconteceu em 11/09/2026,
# ignorar a IA e contar como aprovado um video que o publicador vai recusar.
#
# A data do arquivo e a chave: re-renderizou, o mp4 muda, e a memoria deixa
# de valer sozinha. Nao ha o que invalidar na mao.
LEMBRETES = Path(__file__).resolve().parents[2] / "outputs" / "_pareceres.json"


def _lembretes() -> dict:
    if not LEMBRETES.is_file():
        return {}
    try:
        with open(LEMBRETES, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _marca_do_video(video) -> float:
    # `Exception` e nao `OSError`: o alvo nem sempre e um caminho (um dublê de
    # teste, um objeto sem `caminho`), e gravar a lembranca NAO pode derrubar
    # o parecer que acabou de ser dado. A memoria e conveniencia; o veredito
    # e o produto.
    try:
        return round(Path(getattr(video, "caminho", video)).stat().st_mtime, 2)
    except Exception:                                          # noqa: BLE001
        return 0.0


def lembrar(video, veredito: dict) -> None:
    try:
        _lembrar(video, veredito)
    except Exception:                                          # noqa: BLE001
        pass


def _e_id_de_video(chave: str) -> bool:
    """`historia_00008:celular:p01` e um id; `<object object at 0x...>` nao.

    A guarda existe porque a de `metricas.registrar_publicacao` ja existia e
    ainda assim o mesmo erro voltou. La foram 322 de 358 linhas do ledger
    escritas por um teste que dublava a publicacao mas nao o registro; aqui
    foram tres chaves `<object object at 0x...>` no arquivo de vereditos de
    PRODUCAO, escritas por um teste que dublava `_pedir_em` mas nao isolava
    `LEMBRETES`.

    O formato e o do catalogo: `<fonte>:<perfil>[:pNN]`. Recusar o que nao
    tem essa cara e barato e para o lixo na porta.
    """
    limpo = str(chave or "")
    return bool(re.fullmatch(r"[A-Za-z0-9_]+:[A-Za-z0-9_]+(?::[A-Za-z0-9_]+)?",
                             limpo))


def _pela_folha(vista: str) -> bool:
    """O veredito veio da folha de contato, e nao do mp4?

    `vista` e escrito por `_pedir_em`: `"video inteiro (2:23)"` quando o
    arquivo subiu, `"folha de contato"` quando so as miniaturas subiram.
    Tratar vazio como folha e o lado seguro: o que nao prova que assistiu
    nao derruba quem assistiu.
    """
    return not str(vista or "").startswith("video")


def _lembrar(video, veredito: dict) -> None:
    chave = str(getattr(video, "id", video))
    if not _e_id_de_video(chave):
        raise ValueError(
            f"veredito recusado: {chave!r} nao identifica video nenhum. "
            "Quem pede parecer passa o item do catalogo.")
    dados = _lembretes()
    marca = _marca_do_video(video)
    vista = veredito.get("vista", "")

    # QUEM ASSISTIU GANHA DE QUEM SO VIU A FOLHA.
    #
    # `pedir` cai para o ChatGPT quando a conta do Gemini esta ocupada, e o
    # ChatGPT nao assiste video: ele julga a folha de contato, doze
    # miniaturas. Em 12/09/2026 o Gemini reprovou a parte 1 da historia 4 as
    # 06:14 depois de assistir 2:23 de video ("quadro 6: tela dividida"), e as
    # 20:25 o ChatGPT devolveu "APROVADO" em oito caracteres olhando a folha —
    # e este arquivo trocou a reprovacao pela aprovacao. O video voltou a ficar
    # liberado para a grade.
    #
    # A folha nao mostra movimento, corte nem audio. Ela serve quando nao ha
    # nada, nunca para derrubar quem viu o arquivo inteiro. Mesmo mp4 (mesma
    # mtime) e veredito antigo vindo do video: a folha nao entra.
    antigo = dados.get(chave)
    # Excecao unica: a folha POR CENA entra no lugar de um veredito de video
    # dado sem numerar as cenas. O video viu mais, mas o numero que ele deu
    # nao aponta cena nenhuma, e sem ele o reparador nao tem o que refazer.
    melhora_numeracao = (veredito.get("numeracao") == "cena"
                         and (antigo or {}).get("numeracao") != "cena")
    # E a regua nova entra no lugar da velha, mesmo vindo da folha.
    melhora_criterio = (int(veredito.get("criterio") or 1)
                        > int((antigo or {}).get("criterio") or 1))
    if (antigo and not _pela_folha(antigo.get("vista", ""))
            and _pela_folha(vista) and not melhora_numeracao
            and not melhora_criterio
            and abs(float(antigo.get("mtime") or 0) - marca) <= 1.0):
        return

    dados[chave] = {
        "mtime": marca,
        "aprovado": bool(veredito.get("aprovado")),
        "motivos": list(veredito.get("motivos") or []),
        "vista": vista,
        "numeracao": str(veredito.get("numeracao") or ""),
        "protagonista": str(veredito.get("protagonista") or ""),
        "criterio": int(veredito.get("criterio") or 1),
        "quando": datetime.now().isoformat(timespec="seconds"),
    }
    LEMBRETES.parent.mkdir(parents=True, exist_ok=True)
    with open(LEMBRETES, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)


def ja_olhado(video) -> bool:
    """A IA ja deu parecer sobre este VIDEO alguma vez, mesmo num mp4 antigo?

    E a regra de uma passada so (15/09/2026): o video consertado depois do
    veto tem mp4 novo, `lembrado` o trata como nunca visto, e a revisao da
    madrugada perguntaria de novo.
    """
    try:
        return bool(_lembretes().get(str(getattr(video, "id", video))))
    except Exception:                                          # noqa: BLE001
        return False


def lembrado(video) -> dict | None:
    """O ultimo veredito DAQUELE arquivo, ou `None` se ele mudou desde entao."""
    ficha = _lembretes().get(str(getattr(video, "id", video)))
    if not ficha:
        return None
    if abs(float(ficha.get("mtime") or 0) - _marca_do_video(video)) > 1.0:
        return None      # o video foi re-renderizado: o parecer velho morreu
    return ficha


def esquecer(video) -> None:
    dados = _lembretes()
    if dados.pop(str(getattr(video, "id", video)), None) is not None:
        with open(LEMBRETES, "w", encoding="utf-8") as fh:
            json.dump(dados, fh, ensure_ascii=False, indent=2)


class SemParecer(RuntimeError):
    """Nao deu para perguntar. NAO e reprovacao — a diferenca importa."""


def _recorte(painel: float | None) -> str:
    """Na tela dividida, so a metade de cima e a historia: a de baixo e o
    video de fundo, e na folha ele so confundiria quem julga as cenas."""
    return f"crop=iw:trunc(ih*{float(painel):g}/2)*2:0:0," if painel else ""


def folha_de_contato(video: Path, destino: Path, *,
                     quadros: int = QUADROS,
                     painel: float | None = None) -> Path:
    """Um mosaico com `quadros` momentos do video, igualmente espacados."""
    video, destino = Path(video), Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    duracao = _duracao(video)
    if duracao <= 0:
        raise SemParecer(f"nao consegui ler a duracao de {video.name}")
    # `fps` fracionario e o que espaca os quadros pelo video INTEIRO. Pegar
    # os N primeiros daria doze imagens do mesmo primeiro segundo.
    taxa = quadros / duracao
    filtro = (f"fps={taxa:.6f},{_recorte(painel)}"
              f"scale={LARGURA_DO_QUADRO}:-1,tile={COLUNAS}x{LINHAS}")
    comando = ["ffmpeg", "-v", "error", "-y", "-i", str(video),
               "-vf", filtro, "-frames:v", "1", "-q:v", "3", str(destino)]
    try:
        subprocess.run(comando, capture_output=True, timeout=300,
                       creationflags=NO_WINDOW, check=True)
    except (OSError, subprocess.SubprocessError) as erro:
        raise SemParecer(f"o ffmpeg nao montou a folha: {erro}") from erro
    if not destino.is_file():
        raise SemParecer("a folha de contato nao foi escrita")
    return destino


COLUNAS_POR_CENA = 4


def folha_por_cena(video: Path, destino: Path, cenas: list,
                   painel: float | None = None) -> Path:
    """Um quadro por CENA, tirado do meio dela, com o numero no canto.

    A folha no tempo pega doze momentos espacados, numa parte de 13 ou 14
    cenas: o "quadro 6" dela quase nunca e a cena 6.
    """
    import tempfile

    from PIL import Image, ImageDraw

    video, destino = Path(video), Path(destino)
    if not cenas:
        raise SemParecer("sem cenas para montar a folha por cena")
    quadros = []
    with tempfile.TemporaryDirectory() as tmp:
        for cena in cenas:
            meio = (float(cena["inicio"]) + float(cena["fim"])) / 2.0
            saida = Path(tmp) / f"c{int(cena['n']):02d}.jpg"
            comando = ["ffmpeg", "-v", "error", "-y", "-ss", f"{meio:.2f}",
                       "-i", str(video), "-frames:v", "1",
                       "-vf", f"{_recorte(painel)}scale={LARGURA_DO_QUADRO}:-1",
                       str(saida)]
            try:
                subprocess.run(comando, capture_output=True, timeout=120,
                               creationflags=NO_WINDOW, check=True)
                with Image.open(saida) as imagem:
                    quadros.append((int(cena["n"]), imagem.convert("RGB")))
            except (OSError, subprocess.SubprocessError) as erro:
                raise SemParecer(
                    f"nao tirei o quadro da cena {cena['n']}: {erro}"
                ) from erro
    altura = max(q.height for _n, q in quadros)
    colunas = min(COLUNAS_POR_CENA, len(quadros))
    linhas = (len(quadros) + colunas - 1) // colunas
    folha = Image.new("RGB", (colunas * LARGURA_DO_QUADRO, linhas * altura),
                      "black")
    desenho = ImageDraw.Draw(folha)
    for i, (n, quadro) in enumerate(quadros):
        x = (i % colunas) * LARGURA_DO_QUADRO
        y = (i // colunas) * altura
        folha.paste(quadro, (x, y))
        desenho.rectangle([x, y, x + 46, y + 30], fill="black")
        desenho.text((x + 8, y + 8), str(n), fill="yellow")
    destino.parent.mkdir(parents=True, exist_ok=True)
    folha.save(destino, quality=85)
    return destino


def _montar_folha(video, roteiro: dict, parte: int, caminho: Path,
                  destino: Path, painel: float | None = None) -> tuple:
    """`(folha, por_cena)`. Por cena quando da; no tempo quando nao da."""
    fonte = getattr(video, "fonte_id", None)
    if fonte:
        try:
            from ..video import plano
            cenas = plano.cenas_com_tempo(fonte, parte, roteiro)
            return folha_por_cena(caminho, destino, cenas, painel), True
        except Exception:                                      # noqa: BLE001
            pass
    return folha_de_contato(caminho, destino, painel=painel), False


def _duracao(video: Path) -> float:
    try:
        saida = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(video)],
            capture_output=True, text=True, timeout=60,
            creationflags=NO_WINDOW)
        return float((json.loads(saida.stdout or "{}").get("format") or {})
                     .get("duration") or 0.0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def prompt(video, roteiro: dict, parte: int, laudo: dict | None = None, *,
           pela_folha: bool = False, por_cena: bool = True) -> str:
    """O que se pergunta. Fechado de proposito: a resposta tem de ser lida
    por codigo, nao interpretada.

    NUMERADO POR CENA. Ate 13/09/2026 pedia "o numero do quadro" sem dizer o
    que era um quadro, e o reparador lia esse numero como cena. Agora a IA
    recebe a lista de cenas com o trecho de tempo de cada uma, e a folha de
    contato tem um quadro por cena: "cena 7" passa a ser literal.
    """
    from ..video import plano

    fonte = getattr(video, "fonte_id", None)
    cenas = (plano.cenas_com_tempo(fonte, parte, roteiro) if fonte
             else plano.cenas_do_roteiro(roteiro, parte))
    laudo = laudo or {}
    feito = laudo.get("formato") or {}
    dividido = feito.get("layout") == "dividido"
    # A FOLHA JA VEM RECORTADA no painel da historia: la, "ignore a metade de
    # baixo" viraria "ignore a metade de baixo de cada quadro" (onde ficam a
    # marca d'agua e a legenda) ou as ultimas linhas da folha. A isencao e so
    # de quem assiste ao video inteiro. Revisao adversarial de 14/09/2026.
    fundo_na_tela = dividido and not pela_folha
    velocidade = float(feito.get("velocidade") or 1.0)
    acelerado = abs(velocidade - 1.0) > 1e-6
    if pela_folha and por_cena:
        abertura = ("Voce e o revisor final de um canal de historias narradas "
                    "em video vertical. A imagem anexada e uma FOLHA DE "
                    "CONTATO com UM QUADRO POR CENA, na ordem, da esquerda "
                    "para a direita e de cima para baixo, com o numero da "
                    "cena escrito no canto. O quadro 1 e a CENA 1, o quadro "
                    "2 e a CENA 2, e assim por diante.")
    elif pela_folha:
        abertura = ("Voce e o revisor final de um canal de historias narradas "
                    "em video vertical. A imagem anexada e uma FOLHA DE "
                    f"CONTATO: {QUADROS} quadros do video inteiro, na ordem, "
                    "da esquerda para a direita e de cima para baixo.")
    else:
        abertura = ("Voce e o revisor final de um canal de historias narradas "
                    "em video vertical. Assista ao video anexado do comeco ao "
                    "fim antes de responder. Cada cena ocupa o trecho de "
                    "tempo indicado na lista abaixo: e por ele que voce sabe "
                    "em que cena esta.")
    lista = [f"CENA {c['n']} ({c['inicio']:.0f}s a {c['fim']:.0f}s): "
             f"{str(c['narracao'])[:260]}" for c in cenas]
    linhas = [
        abertura,
        "",
        f"TITULO QUE VAI NO YOUTUBE: {getattr(video, 'titulo', '')}",
        "",
        "AS CENAS DESTE VIDEO, na ordem, com o trecho e o que o narrador "
        "fala em cada uma:",
        *lista,
        "",
        "MEDIDAS JA CONFERIDAS (nao precisa julgar de novo): "
        f"{laudo.get('duracao', '?')}s de duracao, "
        f"audio a {laudo.get('media_db', '?')} dB, "
        f"{laudo.get('palavras_por_s', '?')} palavras por segundo, "
        f"{len(cenas)} cenas"
        + (f" (narracao acelerada {velocidade:g}x de proposito)."
           if acelerado else "."),
        "",
        "REPROVE se, e somente se, houver algum destes:",
        "  - alguma imagem nao pertence a esta historia (assunto de outro "
        "video, cena que nao tem nada a ver com o que a narracao conta);",
        "  - a imagem de uma cena CONTRADIZ a narracao daquela cena: mostra "
        "outra pessoa no lugar de quem a narracao diz (um adulto no lugar de "
        "uma crianca, um homem no lugar de uma mulher, outro personagem), "
        "outro lugar, ou o contrario do que acontece;",
        ("  - alguma IMAGEM DA HISTORIA (metade de cima da tela) e colagem, "
         "tela dividida ou grade de paineis dentro dela mesma "
         if fundo_na_tela else
         "  - alguma imagem e colagem, tela dividida ou grade de paineis ")
        + "(dois ou mais quadros dentro do mesmo quadro, com uma faixa "
        "separando);",
        "  - alguma imagem tem marca d'agua, logotipo de banco de imagens ou "
        "legenda SOBREPOSTA pelo gerador;",
        "  - o protagonista muda de rosto, idade, cabelo ou roupa entre os "
        "quadros, a ponto de parecer outra pessoa;",
        "  - o titulo promete algo que a narracao nao entrega;",
        "  - a narracao esta incompleta, se contradiz ou termina no meio;",
        "  - ha algo que derrubaria o video na plataforma (violencia "
        "explicita, conteudo sexual, menor de idade em situacao impropria).",
        "",
        "NAO reprove por nada disto, que e como o canal E:",
        "  - a legenda amarela sobre a imagem: e nossa, entra no render, e "
        "aparece em todos os videos de proposito;",
        *(["  - a TELA DIVIDIDA AO MEIO: e o formato do canal. A metade de "
           "cima e a historia; a metade de baixo e um video de fundo mudo, "
           "sem nenhuma relacao com a historia (maquiagem). Ignore tudo o que "
           "aparece na metade de baixo — pessoa, rosto, maos, produto, texto "
           "em qualquer lingua, marca d'agua, logotipo — e julgue so a "
           "metade de cima;"] if fundo_na_tela else []),
        *(["  - o fundo do video publicado: a tela dele e dividida, com um "
           "video de fundo embaixo, mas na folha ele ja foi RECORTADO e cada "
           "quadro e SO a imagem da historia. Julgue o quadro inteiro: marca "
           "d'agua ou logotipo dentro dele continua sendo problema;"]
          if dividido and pela_folha else []),
        *([f"  - a fala rapida: o video inteiro e acelerado {velocidade:g}x "
           "de proposito;"] if acelerado else []),
        "  - texto que faz parte da CENA (papel na mao, placa na porta, "
        "quadro na parede, tela de computador). So marca d'agua e logotipo "
        "de banco de imagens sao problema;",
        "  - gosto pessoal, ritmo, qualidade artistica, cor ou estilo de "
        "arte;",
        "  - a imagem nao mostrar um DETALHE da narracao: o objeto na mao, o "
        "gesto, a expressao do rosto, um personagem secundario ou a acao "
        "exata. Cada cena e UMA imagem que ilustra o momento, nao uma copia "
        "fiel de cada frase;",
        "  - a historia ser dramatica ou exagerada demais: o canal e de "
        "drama e de humor caricato, e isso e proposital.",
        "",
        "FORMATO DA RESPOSTA, exatamente assim e nada mais:",
        f"Primeira linha: a palavra {APROVADO} ou a palavra {REPROVADO}.",
        "Se REPROVADO, as linhas seguintes: um problema por linha, comecando "
        "com o NUMERO DA CENA quando for imagem (ex.: 'cena 7: ...'). Use "
        "sempre o numero da lista de cenas acima, nunca uma contagem sua.",
        "Se um dos problemas for o protagonista mudar de aparencia, termine "
        "com uma linha 'PROTAGONISTA: <como ele aparece na MAIORIA das "
        "cenas, em ingles: etnia ou tom de pele, idade, cabelo, um traco do "
        "rosto, roupa>'.",
        f"Se {APROVADO}, nao escreva mais nada.",
    ]
    return "\n".join(linhas)


def ler_veredito(texto: str) -> dict:
    """A resposta crua -> `{aprovado, motivos, texto}`.

    Exigente com a PRIMEIRA linha, e nao com o texto inteiro: um modelo que
    escreve "APROVADO, mas cuidado com..." aprovou. Um que enrola e nao diz
    nenhuma das duas palavras nao respondeu, e isso e `SemParecer` — nao e
    reprovacao, e por isso nao pode virar uma.
    """
    limpo = " ".join(str(texto or "").split())
    if not limpo:
        raise SemParecer("o modelo nao respondeu nada")
    primeira = str(texto).strip().splitlines()[0].upper()
    primeira = re.sub(r"[^A-Z]", "", primeira)
    if primeira.startswith(REPROVADO):
        linhas = [L.strip(" -•\t") for L in str(texto).strip().splitlines()[1:]
                  if L.strip(" -•\t")]
        protagonista, motivos = "", []
        for linha in linhas:
            if linha.upper().startswith("PROTAGONISTA:"):
                protagonista = linha.split(":", 1)[1].strip()
            else:
                motivos.append(linha)
        return {"aprovado": False, "motivos": motivos or ["sem motivo dado"],
                "protagonista": protagonista, "texto": str(texto).strip()}
    if primeira.startswith(APROVADO):
        return {"aprovado": True, "motivos": [], "protagonista": "",
                "texto": str(texto).strip()}
    raise SemParecer(
        "a resposta nao comeca com APROVADO nem com REPROVADO: "
        + limpo[:160])


# O mp4 de uma parte tem 30 a 40 MB. Subir e o Gemini processar leva
# minutos; medido em 11/09/2026, a duracao apareceu em ~30 s e a resposta
# veio depois. O teto e generoso porque o custo de desistir cedo e publicar
# sem parecer.
ESPERA_DO_VIDEO_S = 900.0


# A ordem importa e nao e gosto. O Gemini ASSISTE ao mp4; o ChatGPT desta
# maquina e conta free e so le imagem, entao ele julga pela folha de contato —
# ve as cenas, nao ve movimento nem ouve audio. Pior que o primeiro, muito
# melhor que publicar sem parecer nenhum.
#
# Ter o segundo e o que salva o horario quando a geracao esta segurando o
# Gemini: ela fica com a conta pela historia INTEIRA, horas, entao esperar
# nao resolve — trocar de provedor resolve.
PROVEDORES = ("gemini", "chatgpt")
# So o Gemini assiste ao mp4 nesta maquina. Mandar 33 MB para o ChatGPT free
# custa minutos de upload para ele tratar o arquivo como opaco e a folha
# entrar mesmo assim — entao nem se tenta.
ASSISTEM_VIDEO = ("gemini",)
# Espera pela conta antes de trocar de provedor. Curta de proposito: se nao
# liberou em um minuto, e uma geracao rodando, e ela nao vai liberar tao cedo.
ESPERA_DA_CONTA_S = 60.0
# Quanto o parecer espera o modelo calado e sem "Responder agora" antes de
# desistir e cair para o ChatGPT. Respostas boas de video vieram em 37-120 s;
# em 14/09/2026 tres revisoes ficaram os 900 s inteiros com 10 chars na tela,
# e cada uma atrasou o horario da postagem em quinze minutos.
ESPERA_CALADO_S = 480.0


def pedir(video, roteiro: dict, parte: int, *, laudo: dict | None = None,
          provedor: str | None = None, headless: bool = False,
          pasta_temp: Path | None = None,
          espera_video: float = ESPERA_DO_VIDEO_S, log=print) -> dict:
    """Monta a folha, pergunta, e devolve o veredito. Levanta `SemParecer`
    quando nao deu para perguntar em nenhum provedor."""
    from ..llm.cliente import ContaOcupada

    tentar = [provedor] if provedor else list(PROVEDORES)
    ultimo = ""
    for i, alvo in enumerate(tentar):
        try:
            veredito = _pedir_em(alvo, video, roteiro, parte, laudo=laudo,
                                 headless=headless, pasta_temp=pasta_temp,
                                 espera_video=espera_video, log=log)
            lembrar(video, veredito)
            return veredito
        except ContaOcupada as erro:
            ultimo = str(erro)
            if i + 1 < len(tentar):
                log(f"[parecer] a conta do {alvo} esta ocupada; tento o "
                    f"{tentar[i + 1]}.")
            continue
        except SemParecer as erro:
            ultimo = str(erro)
            if i + 1 < len(tentar):
                log(f"[parecer] o {alvo} nao respondeu ({erro}); tento o "
                    f"{tentar[i + 1]}.")
            continue
    raise SemParecer(ultimo or "nenhum provedor respondeu")


def _pedir_em(provedor: str, video, roteiro: dict, parte: int, *,
              laudo: dict | None = None, headless: bool = False,
              pasta_temp: Path | None = None,
              espera_video: float = ESPERA_DO_VIDEO_S, log=print) -> dict:
    from ..llm.cliente import ContaOcupada, abrir_cliente

    caminho = Path(getattr(video, "caminho", video))
    pasta = Path(pasta_temp or caminho.parent)
    destino = pasta / f"folha_p{int(parte):02d}.jpg"
    # COMO O VIDEO FOI FEITO decide o que se pergunta e o que a folha mostra:
    # desde 14/09/2026 ele pode vir acelerado e com a tela dividida.
    from . import qualidade
    from ..video import formato as _formato
    feito = (laudo or {}).get("formato") or qualidade.formato_de(
        qualidade._ffprobe(caminho), getattr(video, "fonte_id", None), parte)
    laudo = {**(laudo or {}), "formato": feito}
    painel = _formato.PAINEL if feito.get("layout") == "dividido" else None
    folha, por_cena = _montar_folha(video, roteiro, parte, caminho, destino,
                                    painel)
    log(f"[parecer] folha de contato: {folha.name} "
        f"({folha.stat().st_size // 1024} KB, "
        f"{'um quadro por cena' if por_cena else 'quadros no tempo'})")

    pergunta = prompt(video, roteiro, parte, laudo)
    try:
        with abrir_cliente(provedor, headless=headless,
                           esperar=ESPERA_DA_CONTA_S,
                           log=log) as cliente:
            cliente.abrir(novo_chat=True)
            # O VIDEO INTEIRO primeiro, e a folha como reserva. O Gemini
            # assiste ao mp4 — leva uns minutos, mas ve movimento, corte e
            # audio, que e o que a folha nao mostra. Quando ele nao aceita o
            # arquivo (conta, tamanho, o site mudou), a folha ainda responde
            # pela parte visual em vez de o video sair sem parecer nenhum.
            try:
                if provedor not in ASSISTEM_VIDEO:
                    raise SemParecer(f"{provedor} nao assiste video")
                duracao = cliente.anexar_video(caminho, espera=espera_video)
                vista = f"video inteiro ({duracao})"
            except ContaOcupada:
                raise
            except Exception as erro:                          # noqa: BLE001
                log(f"[parecer] o video nao vai pelo {provedor} ({erro}); "
                    "vou pela folha de contato.")
                if not cliente.anexar([folha], espera=180):
                    raise SemParecer("nem o video nem a folha subiram")
                vista = "folha de contato"
            cliente.enviar(pergunta if vista.startswith("video")
                           else prompt(video, roteiro, parte, laudo,
                                       pela_folha=True, por_cena=por_cena))
            resposta = cliente.esperar_resposta(
                timeout=900, desistir_calado=ESPERA_CALADO_S)
    except (SemParecer, ContaOcupada):
        # `ContaOcupada` sobe intacta: quem chamou decide trocar de provedor,
        # e transformar em `SemParecer` aqui apagaria essa informacao.
        raise
    except Exception as erro:                                  # noqa: BLE001
        raise SemParecer(f"{type(erro).__name__}: {erro}") from erro
    veredito = ler_veredito(resposta)
    veredito["folha"] = str(folha)
    veredito["vista"] = vista
    veredito["provedor"] = provedor
    # "cena" quando o numero aponta cena de verdade: video com a lista de
    # trechos, ou folha com um quadro por cena. So assim o reparador confia.
    veredito["numeracao"] = ("cena" if vista.startswith("video") or por_cena
                             else "quadro")
    veredito["criterio"] = CRITERIO
    log(f"[parecer] {'APROVADO' if veredito['aprovado'] else 'REPROVADO'}"
        + (f": {veredito['motivos'][0][:90]}" if veredito["motivos"] else ""))
    return veredito


__all__ = ["pedir", "prompt", "ler_veredito", "folha_de_contato",
           "folha_por_cena",
           "SemParecer", "APROVADO", "REPROVADO"]
