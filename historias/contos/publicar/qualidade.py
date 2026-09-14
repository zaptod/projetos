# -*- coding: utf-8 -*-
"""O que impede uma parte de ir ao ar — conferido no ARQUIVO, nao no plano.

"Publicar com um clique" so e seguro se algo olhar o mp4 antes. Um roteiro
perfeito nao garante video bom: a imagem pode ter faltado, a voz pode nao ter
sido sintetizada (sem rede), o render pode ter saido mudo, e nada disso
levanta excecao — o arquivo existe do mesmo jeito.

Entao cada parte passa por uma vistoria antes do upload:

    ERRO    nao publica. Video sem audio, sem imagem nenhuma, curto demais.
    AVISO   publica, mas voce fica sabendo. Cena sem imagem, audio baixo.

Tudo medido com ffprobe/ffmpeg, que ja sao dependencia do render.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Faixas de um vertical publicavel. Fora disto nao e "estilo": e defeito.
DURACAO_MINIMA = 8.0
DURACAO_MAXIMA = 180.0
# As plataformas normalizam para perto de -14 LUFS; abaixo de -30 dB de media
# o video esta praticamente mudo no celular (foi o diagnostico do outro canal).
MEDIA_MINIMA_DB = -30.0
BYTES_MINIMOS = 100_000
# Fala humana em pt-BR fica entre ~1,5 e ~4,0 palavras/s (medido nas partes boas:
# 1,99 a 2,87). Contar as palavras do ROTEIRO contra a duracao do VIDEO responde
# a pergunta que nenhuma medida do arquivo sozinha responde: a narracao chegou
# inteira? A parte 1 da historia 8 dava 19,1 palavras/s e passava em tudo mais.
PALAVRAS_POR_S_MIN = 1.5
PALAVRAS_POR_S_MAX = 4.0
# Silencio no fim = a voz acabou antes das imagens. Um respiro de ~0,6 s e de
# proposito (o CTA precisa de tempo de leitura); tres segundos ja e defeito.
SILENCIO_FINAL_MAXIMO = 3.0
# Parte que destoa das irmas: a p01 tinha 35,7 s contra ~145 s das outras cinco.
FRACAO_MINIMA_DA_MEDIANA = 0.5


def _formato_no_arquivo(dados: dict | None) -> dict | None:
    from ..video import formato
    tags = ((dados or {}).get("format") or {}).get("tags") or {}
    return formato.ler_rotulo(tags.get("comment") or tags.get("COMMENT"))


def formato_de(dados: dict | None, historia_id: str | None = None,
               parte: int | None = None) -> dict:
    """Velocidade e layout com que a parte FOI feita.

    O arquivo responde primeiro: o render grava o formato no `comment` do mp4.
    Sem a etiqueta, vale o que o plano da parte registrou; sem plano, e video
    de antes de 14/09/2026 — velocidade normal, tela inteira.
    """
    from ..video import formato
    achado = _formato_no_arquivo(dados)
    if achado:
        return achado
    if historia_id and parte:
        from ..video import plano
        try:
            with open(plano.caminho_do_plano(historia_id, parte),
                      encoding="utf-8-sig") as fh:
                dados_plano = json.load(fh)
        except (OSError, ValueError):
            dados_plano = None
        if isinstance(dados_plano, dict):
            for chave in ("formato_efetivo", "formato"):
                if isinstance(dados_plano.get(chave), dict):
                    return formato.normalizar(dados_plano[chave])
    return dict(formato.LEGADO)


def avaliar_ritmo(palavras: int, duracao: float,
                  velocidade: float = 1.0) -> dict:
    """Palavras por segundo OUVIDAS e na velocidade NATURAL da fala.

    A faixa de 1,5 a 4,0 e de fala humana, e so faz sentido na velocidade em
    que a voz foi sintetizada. Desde 14/09/2026 o video acelera tudo 1,7x de
    proposito: medida crua, uma parte boa (2,5 palavras/s) viraria 4,3 e seria
    barrada como "audio cortado". Dividir pela velocidade devolve a pergunta
    original — a narracao chegou inteira? — e a parte 1 da historia 8, com
    19,1 palavras/s, continua sendo pega.
    """
    saida = {"palavras_por_s": None, "palavras_por_s_natural": None,
             "erros": [], "avisos": []}
    if not palavras or not duracao:
        return saida
    velocidade = float(velocidade or 1.0)
    ouvida = palavras / float(duracao)
    natural = ouvida / velocidade
    saida["palavras_por_s"] = round(ouvida, 2)
    saida["palavras_por_s_natural"] = round(natural, 2)
    acelerado = ("" if abs(velocidade - 1.0) < 1e-6 else
                 f", {natural:.1f} na fala natural a {velocidade:g}x")
    if natural > PALAVRAS_POR_S_MAX:
        saida["erros"].append(
            f"{palavras} palavras em {float(duracao):.0f}s "
            f"({ouvida:.1f} palavras/s{acelerado}): a narracao nao cabe no "
            "video — o audio veio incompleto")
    elif natural < PALAVRAS_POR_S_MIN:
        saida["avisos"].append(
            f"{natural:.1f} palavras/s: o video esta arrastado para o texto")
    return saida


def _ffprobe(caminho: Path) -> dict:
    try:
        saida = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration,size:format_tags=comment:"
             "stream=codec_type,codec_name",
             "-of", "json", str(caminho)],
            capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)
        return json.loads(saida.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}


def _audio(caminho: Path, duracao: float) -> tuple:
    """(media em dB, segundos calados no fim) numa DECODIFICACAO SO.

    Os dois filtros vao no mesmo `-af`: decodificar um video de 150 s duas
    vezes custava o dobro para responder duas perguntas sobre as mesmas
    amostras, e a vistoria de uma serie de 6 partes fazia isso 12 vezes.
    """
    try:
        saida = subprocess.run(
            # `-vn`: as duas perguntas sao sobre AUDIO, e decodificar 150 s de
            # 1080x1920 para responde-las e o grosso do custo. Sem ele, a
            # vistoria do acervo inteiro leva minutos em vez de segundos.
            ["ffmpeg", "-v", "info", "-i", str(caminho), "-vn", "-af",
             "volumedetect,silencedetect=n=-40dB:d=1.0", "-f", "null", "-"],
            capture_output=True, text=True, timeout=300, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None, 0.0
    media, inicios, fins = None, [], []
    for linha in (saida.stderr or "").splitlines():
        try:
            if "mean_volume:" in linha:
                media = float(linha.split("mean_volume:")[1].split("dB")[0].strip())
            elif "silence_start:" in linha:
                inicios.append(float(linha.split("silence_start:")[1].split()[0]))
            elif "silence_end:" in linha:
                fins.append(float(linha.split("silence_end:")[1].split()[0]))
        except (ValueError, IndexError):
            continue
    if not inicios or duracao <= 0:
        return media, 0.0
    comeco = inicios[-1]
    # O ffmpeg fecha o ultimo bloco no fim do arquivo, entao "tem silence_end"
    # NAO quer dizer "o silencio acabou antes do video": e preciso olhar ONDE
    # ele fecha. So conta o que vai ate o fim — pausa longa no meio e respiro.
    fim = fins[-1] if fins and fins[-1] > comeco else duracao
    if fim < duracao - 0.3:
        return media, 0.0
    return media, max(0.0, duracao - comeco)


def vistoriar_arquivo(caminho: Path) -> dict:
    """O que o mp4 tem de fato: duracao, faixas e nivel de audio."""
    caminho = Path(caminho)
    if not caminho.is_file():
        return {"existe": False, "erros": [f"{caminho.name} nao existe"],
                "avisos": []}
    dados = _ffprobe(caminho)
    fluxos = dados.get("streams") or []
    duracao = float((dados.get("format") or {}).get("duration") or 0.0)
    tem_video = any(f.get("codec_type") == "video" for f in fluxos)
    tem_audio = any(f.get("codec_type") == "audio" for f in fluxos)
    tamanho = caminho.stat().st_size

    erros, avisos = [], []
    if tamanho < BYTES_MINIMOS:
        erros.append(f"arquivo de {tamanho / 1000:.0f} KB: render interrompido")
    if not tem_video:
        erros.append("sem faixa de video")
    if not tem_audio:
        erros.append("sem faixa de audio: o video vai ao ar mudo")
    if duracao < DURACAO_MINIMA:
        erros.append(f"{duracao:.1f}s e curto demais para uma historia")
    elif duracao > DURACAO_MAXIMA:
        avisos.append(f"{duracao:.0f}s: longo para um Short/Reel")

    media, calado = _audio(caminho, duracao) if tem_audio else (None, 0.0)
    if media is not None and media < MEDIA_MINIMA_DB:
        erros.append(f"audio a {media:.1f} dB de media: praticamente mudo")

    if calado > SILENCIO_FINAL_MAXIMO:
        erros.append(f"os ultimos {calado:.1f}s sao mudos: a narracao acabou "
                     "antes das imagens")

    return {"existe": True, "duracao": round(duracao, 2), "bytes": tamanho,
            "audio": tem_audio, "video": tem_video, "media_db": media,
            "silencio_final": round(calado, 2),
            "formato": _formato_no_arquivo(dados),
            "erros": erros, "avisos": avisos}


def _erros_das_imagens(historia_id: str, roteiro: dict,
                       parte: int) -> list[str]:
    """O que as CENAS daquela parte tem de errado — e se o mp4 as reflete.

    Duas perguntas que nenhuma medida do arquivo responde:

    COLAGEM. Varridas as 440 imagens do disco em 11/09/2026, 44 eram colagem
    de paineis, apesar de o prompt negativo pedir uma cena so em todas elas.
    Num vertical cada painel fica com menos de metade da altura e a cena
    seguinte volta a ser inteira: o video pisca entre dois formatos.

    Quem cuida do resto ja existe: `utilizavel` recusa a cena que nao e
    vertical, e a comparacao de datas mais abaixo pega o mp4 renderizado
    ANTES de uma imagem ser refeita — sem ela, consertar a colagem no disco
    nao mudaria o arquivo que sobe.
    """
    from ..imagens import composicao, fila
    from ..video.timeline import cenas_da_parte

    erros = []
    for cena in cenas_da_parte(roteiro, parte):
        arquivo = fila.caminho_da_cena(historia_id, cena["n"], parte)
        if not arquivo.is_file():
            continue
        razao = composicao.motivo(arquivo)
        if razao:
            erros.append(f"cena {cena['n']}: {razao}")
    return erros


def _capa_existe(historia_id: str, roteiro: dict, parte: int) -> bool:
    from ..pipeline.controller import OUTPUTS
    from ..video.capa import caminho
    total = len(roteiro.get("partes") or [])
    return caminho(OUTPUTS / historia_id, parte, total).is_file()


def vistoriar_parte(historia_id: str, parte: int, caminho: Path,
                    roteiro: dict | None = None) -> dict:
    """A vistoria do arquivo MAIS o que so o roteiro sabe dizer."""
    from ..imagens import fila
    from ..roteiro import roteiro as R
    from ..video.timeline import cenas_da_parte

    roteiro = roteiro or R.carregar(historia_id)
    laudo = vistoriar_arquivo(caminho)

    # O TEXTO E MESMO DESTA HISTORIA? Nenhuma medida do arquivo responde isso.
    # Em 11/09/2026 as partes 3 a 6 da historia_00005 foram ao disco com 56
    # cenas de gameplay de Minecraft dentro de um drama sobre um homem que
    # esconde da esposa quem paga o apartamento — e a parte 3 tinha ate a
    # narracao de OUTRA historia. O video tinha audio, imagem, duracao e
    # palavras por segundo perfeitos: passava em tudo o que se mede abaixo, e
    # foi publicado no YouTube e no TikTok antes de alguem ver.
    #
    # Erro e nao aviso, pelo mesmo motivo da cena sem imagem: aviso e o que se
    # le depois, erro e o que impede.
    from ..roteiro import pertinencia
    for motivo in pertinencia.problemas(cenas_da_parte(roteiro, parte)):
        laudo["erros"].append(f"roteiro: {motivo}")

    laudo["erros"].extend(_erros_das_imagens(historia_id, roteiro, parte))
    if not _capa_existe(historia_id, roteiro, parte):
        # AVISO e nao erro: a capa melhora o clique, mas um video sem ela
        # ainda e um video — e todo o acervo anterior a 11/09/2026 esta
        # assim. Barrar por capa pararia a grade para consertar vitrine.
        laudo["avisos"].append(
            "sem capa propria: o YouTube vai escolher um frame sozinho "
            "(`main.py capas` desenha as que faltam)")

    # A NARRACAO CHEGOU INTEIRA? Nenhuma medida do arquivo sozinha responde
    # isso: um video com 85% da fala faltando tem audio, tem imagem, tem
    # duracao e passa em tudo. O roteiro sabe quantas palavras deviam ser
    # ditas; o arquivo sabe em quantos segundos. O resto e divisao.
    palavras = sum(len(str(c.get("narracao") or "").split())
                   for c in cenas_da_parte(roteiro, parte))
    laudo["palavras"] = palavras
    feito = laudo.get("formato") or formato_de(None, historia_id, parte)
    laudo["formato"] = feito
    ritmo = avaliar_ritmo(palavras, float(laudo.get("duracao") or 0.0),
                          feito["velocidade"])
    laudo["palavras_por_s"] = ritmo["palavras_por_s"]
    laudo["palavras_por_s_natural"] = ritmo["palavras_por_s_natural"]
    laudo["erros"].extend(ritmo["erros"])
    laudo["avisos"].extend(ritmo["avisos"])
    if laudo.get("existe") and feito.get("layout") == "vertical":
        from ..video import plano
        try:
            with open(plano.caminho_do_plano(historia_id, parte),
                      encoding="utf-8-sig") as fh:
                pedido = (json.load(fh) or {}).get("formato") or {}
        except (OSError, ValueError, AttributeError):
            pedido = {}
        if str(pedido.get("layout") or "") == "dividido":
            laudo["avisos"].append(
                "o plano pedia tela dividida e o video saiu na tela inteira: "
                "o video de fundo faltou no render")

    imagens = fila.resumo(historia_id, roteiro, parte)
    if imagens["total"] and imagens["prontas"] == 0:
        laudo["erros"].append(
            "nenhuma cena tem imagem: o video inteiro e cartao de texto")
    elif imagens["faltam"]:
        # CENA SEM IMAGEM E ERRO, NAO AVISO. O render nao se recusa a rodar sem
        # imagem: ele desenha um cartao tipografico e entrega um mp4 que parece
        # pronto. Como aviso, isso ja passou tres vezes — a historia 5 e a 10
        # foram ao disco com o GANCHO (cena 1, o primeiro segundo, onde a
        # pessoa decide ficar) virado cartao de texto, e o painel dizia
        # "pronta para publicar". Aviso e o que se le depois; erro e o que
        # impede.
        faltando = [l["n"] for l in fila.estado(historia_id, roteiro, parte)
                    if not l["pronta"]]
        laudo["erros"].append(
            f"{imagens['faltam']} de {imagens['total']} cena(s) sem imagem "
            f"(cena(s) {', '.join(str(c) for c in faltando[:6])}): o video tem "
            "cartao de texto no lugar. Gere as imagens e renderize de novo.")

    # IMAGEM SEM PROVA DE ORIGEM NAO VAI AO AR. As imagens de verdade vem do
    # PicassoIA e ficam registradas em `imagens.json` com a prova (o card do
    # historico com o nosso prompt). As da `historia_00001` sao PLACEHOLDER
    # gerado localmente com PIL — um gradiente borrado com o numero da cena no
    # meio — e as da `historia_00002` sao cartoes roxos de teste. As duas
    # passavam em tudo: o arquivo existe, tem tamanho, o video tem imagem.
    #
    # Descoberto em 08/09/2026 no primeiro ensaio da postagem diaria: a fila
    # comeca pela historia mais antiga, e a mais antiga e justamente a do
    # placeholder — ela seria o primeiro video PUBLICO do canal.
    linhas = fila.estado(historia_id, roteiro, parte)
    prontas = [l for l in linhas if l["pronta"]]
    # `prova` e um dict ate quando a prova FALHOU ({"comprovada": false}); so
    # a presenca dele deixou passar, em 14/09/2026, a foto de outra pessoa da
    # conta na historia_00011 p06_cena_07.
    sem_prova = [l["n"] for l in prontas
                 if not (l.get("prova") or {}).get("comprovada")]
    if prontas and len(sem_prova) == len(prontas):
        laudo["erros"].append(
            "nenhuma imagem tem prova de origem: estas cenas nao vieram do "
            "PicassoIA (placeholder ou teste). Isto nao vai ao ar.")
    elif sem_prova:
        laudo["avisos"].append(
            f"{len(sem_prova)} cena(s) sem prova de origem "
            f"(cena(s) {', '.join(str(c) for c in sem_prova[:6])})")

    # O mp4 mais velho que a ultima imagem = a imagem nova nao entrou nele.
    novas = [l["arquivo"] for l in fila.estado(historia_id, roteiro, parte)
             if l["pronta"]]
    if novas and laudo.get("existe"):
        mais_nova = max(a.stat().st_mtime for a in novas)
        if Path(caminho).stat().st_mtime + 5 < mais_nova:
            laudo["erros"].append(
                "imagem mais nova que o video: re-renderize antes de publicar")

    laudo.update({"parte": parte, "imagens": imagens,
                  "titulo": R.titulo_da_parte(roteiro, parte),
                  "ok": not laudo["erros"]})
    return laudo


def liberado(video, roteiro: dict | None = None) -> dict:
    """ESTE video pode sair? A resposta unica, para todo mundo consultar.

    Havia tres donos da mesma pergunta e duas respostas. A auditoria
    (`panorama.auditoria.qualidade`) chamava so `vistoriar_parte`; o freio de
    estoque (`agenda.aprovados_no_estoque`) somava o veto lembrado da IA; e o
    publicador fazia um terceiro arranjo. Medido em 11/09/2026: a tela dizia
    "0 barrados" enquanto o freio contava um video reprovado pela IA — e nao
    havia como saber qual das duas estava certa.

    SO LE, e isso e requisito, nao detalhe: o `panorama` tem regra escrita de
    nao tocar rede nem navegador. Por isso aqui entra `parecer.lembrado` (que
    le um arquivo) e nunca `parecer.pedir` (que abre o Gemini). Quem PERGUNTA
    e o publicador, uma vez, no horario; os outros dois LEEM o que ele achou.
    """
    from ..roteiro import roteiro as R

    if roteiro is None:
        roteiro = R.carregar(video.fonte_id)
    laudo = vistoriar_parte(video.fonte_id, video.parte, video.caminho,
                            roteiro)
    erros = list(laudo.get("erros") or [])
    avisos = list(laudo.get("avisos") or [])
    fonte = "vistoria"
    if not erros:
        try:
            from . import parecer
            ficha = parecer.lembrado(video)
        except Exception:                                      # noqa: BLE001
            ficha = None
        if ficha and not ficha.get("aprovado"):
            motivo = ("a IA reprovou: "
                      + "; ".join(ficha.get("motivos") or []))
            if veto_vencido(video):
                # O VETO VENCE. Depois das tres rodadas de conserto ele vira
                # aviso: o video sai do jeito que esta. Defeito de ARQUIVO
                # (mudo, sem imagem) continua barrando acima — isso nao e
                # opiniao, e video quebrado.
                avisos.append(f"{motivo} (as rodadas de conserto acabaram; "
                              "sai assim)")
                fonte = "veto vencido"
            else:
                erros.append(motivo)
                fonte = "parecer"
    return {"ok": not erros, "erros": erros, "avisos": avisos,
            "fonte": fonte, "laudo": laudo}


def veto_vencido(video) -> bool:
    """O veto da IA ja teve as tres rodadas de conserto e continua de pe?

    Pedido dele em 13/09/2026: "ela tem que ter apenas 3 rounds pra consertar
    as coisas, caso nao conserte o video tem que sair de qualquer forma". O
    veto que nunca vencia travou a grade: seis videos barrados na frente da
    fila, onze aprovados logo atras, e nenhuma historia saiu nos horarios.
    """
    try:
        from ..pipeline import reparo
        return reparo.insistente(str(getattr(video, "id", video)))
    except Exception:                                          # noqa: BLE001
        return False


def vistoriar_serie(historia_id: str, videos: list) -> dict:
    """Vistoria de todas as partes prontas. `videos` sao os do catalogo."""
    from ..roteiro import roteiro as R
    roteiro = R.carregar(historia_id)
    partes = [vistoriar_parte(historia_id, v.parte, v.caminho, roteiro)
              for v in videos]
    # UMA PARTE FORA DA CURVA. As partes de uma serie sao escritas com o mesmo
    # numero de cenas, entao duram quase o mesmo; a que destoa nao e estilo, e
    # defeito. A p01 da historia 8 tinha 35,7 s contra ~145 s das cinco irmas —
    # visivel de longe para quem olha a tabela, invisivel para quem olha um mp4.
    duracoes = sorted(float(p.get("duracao") or 0.0) for p in partes
                      if p.get("existe"))
    if len(duracoes) >= 3:
        mediana = duracoes[len(duracoes) // 2]
        for laudo in partes:
            atual = float(laudo.get("duracao") or 0.0)
            if laudo.get("existe") and atual < mediana * FRACAO_MINIMA_DA_MEDIANA:
                laudo["avisos"].append(
                    f"{atual:.0f}s contra {mediana:.0f}s das outras partes: "
                    "esta parte esta pela metade")
    if str(roteiro.get("provedor") or "").lower() == "fake":
        for laudo in partes:
            laudo["erros"].append(
                "historia de TESTE (provedor 'fake'): as imagens sao cartoes "
                "de placeholder, isto nao vai ao ar")
    for laudo in partes:
        laudo["ok"] = not laudo["erros"]
    esperadas = len(roteiro["partes"])
    faltando = sorted({p["n"] for p in roteiro["partes"]}
                      - {v.parte for v in videos})
    resumo = {
        "historia_id": historia_id, "titulo": roteiro.get("titulo", ""),
        "partes": partes, "esperadas": esperadas,
        "prontas": len(videos), "faltando": faltando,
        "erros": [f"parte {p['parte']}: {e}" for p in partes for e in p["erros"]],
        "avisos": [f"parte {p['parte']}: {a}" for p in partes for a in p["avisos"]],
    }
    if faltando:
        resumo["erros"].insert(
            0, f"faltam os videos da(s) parte(s) {', '.join(map(str, faltando))}")
    resumo["ok"] = not resumo["erros"]
    return resumo
