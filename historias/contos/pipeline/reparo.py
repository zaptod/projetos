# -*- coding: utf-8 -*-
"""Conserta sozinho o video que a vistoria barrou.

A pipeline aprendeu a DETECTAR bem: colagem, texto de outra historia, imagem
mais nova que o render, cena sem imagem, e o veto da IA. O que faltava era o
outro lado — nada consertava. O video ficava barrado para sempre, o freio de
estoque contava ele como se fosse estoque bom, e a grade chegava no horario
sem nada aprovado para publicar. Tres defeitos que so aparecem juntos, e o
sintoma final e um canal mudo sem nenhum alerta.

O QUE ELE CONSERTA:

    colagem numa cena     apaga aquela imagem e refaz. O prompt esta certo,
                          quem errou foi o desenho — a mesma doutrina do
                          worker, que reenvia o texto identico.
    render defasado       o mp4 e mais velho que as imagens: so re-renderizar.
    cena sem imagem       gera o que falta e re-renderiza.
    veto da IA            desde 13/09/2026, e so com numero de CENA
                          confiavel (`conserto_de_cena`): colagem e marca
                          d'agua refazem a cena; imagem que nao bate com a
                          narracao ganha prompt novo escrito a partir dela;
                          troca de rosto fixa a descricao do protagonista
                          pela aparencia que a IA viu na maioria das cenas.

O QUE ELE NAO CONSERTA, de proposito:

    texto de outra historia   nao e conserto de imagem, e reescrita de parte.
                              Quem faz isso e a retomada (`incompletas`), e
                              ela ja roda antes daqui.

TETO DE TENTATIVAS, e ele nao e opcional. A conta do PicassoIA e
compartilhada, e uma cena que o modelo insiste em desenhar em painel ficaria
consumindo geracao para sempre. Depois do teto o video e marcado como
INSISTENTE: para de ser tentado, e aparece no Telegram uma vez, para uma
pessoa decidir.
"""
from __future__ import annotations

import contextlib
import json
import re
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"
REGISTRO = OUTPUTS / "_reparos.json"

# Tres passadas por video. Cada uma custa geracao de imagem na conta
# compartilhada mais um render de ~2 min; alem disso e teimosia.
# UMA PASSADA SO NO GEMINI (pedido dele em 15/09/2026, 02:25: "o gemini
# parece estar mais atrasando do que ajudando, diminua para apenas uma passada
# no gemini e pronto"). O parecer da madrugada olha o video UMA vez; se
# reprovar, o reparo aplica o conserto UMA vez, confere so a vistoria mecanica
# (`CONFIRMAR_COM_A_IA`) e o veto vence (`UMA_PASSADA`).
#
# DOIS CONTADORES, e a revisao da mesma noite mostrou por que: com um so, a
# falha da MAQUINA (PicassoIA que nao devolve, render que quebra) gastava a
# unica rodada e o veto vencia sem conserto nenhum; e um video com defeito de
# arquivo que falhou uma vez ficava barrado para sempre. A passada do veto e
# `passada`; as tentativas de maquina seguem com teto 3.
TETO_DE_TENTATIVAS = 3
UMA_PASSADA = True
CONFIRMAR_COM_A_IA = False

# `cena 11: parece colagem: ...` — o numero e o que diz qual imagem apagar.
# Aceita "quadro" tambem, mas CUIDADO: ate 13/09/2026 o "quadro N" do Gemini
# nao era a cena N (na folha de contato era a N-esima de doze miniaturas
# espacadas no tempo). Veto da IA nao passa mais por aqui: vai por
# `_plano_pelo_veto_da_ia`, que so age com numero de cena confiavel e
# pergunta de novo quando nao ha.
CENA_NA_MENSAGEM = re.compile(r"(?:cena|quadro)\s+(\d+)\s*:", re.I)


def _ler() -> dict:
    if not REGISTRO.is_file():
        return {}
    try:
        with open(REGISTRO, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar(dados: dict) -> None:
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRO, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)


def tentativas(video_id: str) -> int:
    return int((_ler().get(str(video_id)) or {}).get("tentativas") or 0)


def insistente(video_id: str) -> bool:
    """Ja bateu o teto de tentativas? Entao nao se tenta mais consertar."""
    return tentativas(video_id) >= TETO_DE_TENTATIVAS


# O `feito` que gastava a passada do veto nos registros de antes do campo
# `passada` existir: conserto aplicado ou desistencia da IA. "A imagem nova nao
# veio", "ainda faltam" e "falhou" sao da MAQUINA e nao gastam.
_FEITO_DA_PASSADA = ("refiz", "consertei", "a ia reprova")


def _passada_da_ficha(ficha: dict) -> bool:
    if "passada" in ficha:
        return bool(ficha["passada"])
    return str(ficha.get("feito") or "").lower().startswith(_FEITO_DA_PASSADA)


def passada_gasta(video_id: str) -> bool:
    """O veto da IA ja teve a sua passada (conserto aplicado ou desistencia)?"""
    return _passada_da_ficha(_ler().get(str(video_id)) or {})


def veto_consumido(video_id: str) -> bool:
    """O veto da IA deixou de barrar este video?

    Com `UMA_PASSADA`, basta a passada gasta. Sempre: as tentativas acabaram.
    """
    return (UMA_PASSADA and passada_gasta(video_id)) or insistente(video_id)


# O `feito` de um conserto APLICADO (cenas refeitas, imagens geradas,
# re-render). Fora daqui: a desistencia ("a IA reprova e nao ha conserto
# automatico") e as falhas da maquina ("a imagem nova nao veio", "ainda
# faltam", "falhou").
_FEITO_DO_CONSERTO = ("refiz", "gerei", "re-renderizei", "consertei")


def _e_conserto(feito) -> bool:
    return str(feito or "").lower().startswith(_FEITO_DO_CONSERTO)


def _conserto_da_ficha(ficha: dict) -> bool:
    if "consertado" in ficha:
        return bool(ficha["consertado"])
    # Registro de antes do campo: deduz pelo `feito` que gastou a passada.
    return _passada_da_ficha(ficha) and _e_conserto(ficha.get("feito"))


def consertado(video_id: str) -> bool:
    """A passada do veto foi gasta com um conserto APLICADO?

    Decisao do Adrian em 05/10/2026 (Grimorio
    historias/reolhar-depois-do-conserto): a consertada NAO volta a IA, so
    ganha prioridade sobre a vetada sem conserto no ultimo recurso da
    postagem. Nunca levanta.
    """
    try:
        ficha = _ler().get(str(video_id)) or {}
        return (isinstance(ficha, dict) and _passada_da_ficha(ficha)
                and _conserto_da_ficha(ficha))
    except Exception:                                          # noqa: BLE001
        return False


TRAVA_DO_REGISTRO = "historias__reparos_json"


@contextlib.contextmanager
def _registro_travado():
    """Ler-mudar-gravar o `_reparos.json` sob trava entre PROCESSOS.

    Com as duas historias em paralelo (06/10/2026) duas rodadas consertam ao
    mesmo tempo, e a gravacao de uma apagaria a anotacao da outra (a conta de
    tentativas que decide o insistente). Sem a trava em 30 s grava assim
    mesmo: perder a anotacao e menos ruim que parar o conserto.
    """
    from builds import travas
    with travas.trava(TRAVA_DO_REGISTRO, esperar=30.0):
        yield


def _anotar(video_id: str, motivo: str, feito: str, *,
            passada: bool = False) -> int:
    with _registro_travado():
        dados = _ler()
        ficha = dados.setdefault(str(video_id), {"tentativas": 0})
        ja_gasta = _passada_da_ficha(ficha)
        ja_consertado = _conserto_da_ficha(ficha)
        ficha["tentativas"] = int(ficha.get("tentativas") or 0) + 1
        ficha["quando"] = datetime.now().isoformat(timespec="seconds")
        ficha["motivo"] = str(motivo)[:200]
        ficha["feito"] = feito
        # A passada, uma vez gasta, fica gasta. O conserto aplicado tambem: uma
        # falha da maquina depois dele troca o `feito`, mas nao desfaz o
        # conserto.
        ficha["passada"] = bool(passada) or ja_gasta
        ficha["consertado"] = ja_consertado or (bool(passada)
                                                and _e_conserto(feito))
        _gravar(dados)
        return ficha["tentativas"]


def esquecer(video_id: str) -> None:
    """O video passou: a conta zera. Sem isto, um video consertado na
    terceira tentativa entraria na quarta como insistente."""
    with _registro_travado():
        dados = _ler()
        if str(video_id) in dados:
            del dados[str(video_id)]
            _gravar(dados)


# O MESMO DEFEITO TEM TRES NOMES. O nosso detector diz "colagem"; o Gemini,
# olhando a mesma imagem, escreve "tela dividida" ou "grade de paineis".
# Exigir a palavra literal deixava dois tercos dos motivos de fora.
DIZ_COLAGEM = ("colagem", "tela dividida", "grade de paine", "grade de painé",
               "dividida em", "paineis separados", "painéis separados")


def _tela_dividida(video, historia_id: str, parte: int) -> bool:
    """O video foi feito com a tela dividida (formato de 14/09/2026)?"""
    try:
        from ..publicar import qualidade
        caminho = getattr(video, "caminho", None)
        dados = qualidade._ffprobe(Path(caminho)) if caminho else None
        return qualidade.formato_de(dados, historia_id,
                                    parte).get("layout") == "dividido"
    except Exception:                                          # noqa: BLE001
        return False


# O Gemini reclamando da TELA (o formato), e nao da imagem da cena...
DIZ_FORMATO = ("metade de baixo", "metade inferior", "parte de baixo",
               "parte inferior", "video de fundo", "vídeo de fundo",
               "maquiagem", "se maquiando", "batom", "tela inteira",
               "divisao da tela", "divisão da tela", "dividida ao meio")
# ...e descrevendo a IMAGEM da cena, que e colagem de verdade.
DIZ_IMAGEM_DA_CENA = ("a imagem e", "a imagem é", "dois quadros", "paineis",
                      "painéis", "empilhad", "grade")
# Marca d'agua e logotipo: o video de fundo TEM os dois, e a imagem gerada
# tambem pode ter. So quem assistiu ao video inteiro distingue onde estava.
DIZ_MARCA = ("marca d", "logotipo")


def _vista_do_veto(video) -> str:
    """Como o veto lembrado foi dado: "video inteiro (...)" ou "folha..."."""
    try:
        from ..publicar import parecer
        return str((parecer.lembrado(video) or {}).get("vista") or "")
    except Exception:                                          # noqa: BLE001
        return ""


def _motivo_e_do_formato(motivos, n: int, vista: str = "") -> bool:
    """A queixa da cena `n` e sobre a tela dividida em si, e nao sobre a imagem?

    Desde 14/09/2026 a metade de baixo do video e um video de fundo. O prompt
    do parecer avisa, mas o Gemini ainda pode escrever "cena 4: tela dividida
    ao meio, com um video de maquiagem embaixo" — e refazer a imagem por isso
    trocaria uma imagem boa por outra.

    PELO TEXTO, E NAO PELO DETECTOR. A primeira versao perguntava ao
    `composicao.e_colagem` se a imagem era colagem, e a revisao adversarial
    mostrou que isso nunca decide nada: a IA so e consultada DEPOIS de a
    vistoria passar, e a vistoria roda o mesmo detector em toda cena. Com veto
    da IA na mao, o detector ja disse "nao e colagem" — e toda colagem real
    que so a IA pega ("a imagem e uma tela dividida com dois quadros
    empilhados", h10 p04) seria descartada. Na duvida, refaz.

    MARCA NA METADE DE BAIXO (revisao de conflitos de 14/09/2026): o video de
    maquiagem tem texto e a marca "babycolor". Quando o veto veio de quem
    ASSISTIU (vista "video inteiro") e fala da metade de baixo, a marca e do
    fundo. Na folha de contato, ja recortada no painel, a mesma frase aponta a
    imagem da historia — e la ela continua sendo refeita.
    """
    from . import conserto_de_cena as C
    texto = C.motivos_da_cena(motivos, int(n)).lower()
    if not texto or any(t in texto for t in DIZ_IMAGEM_DA_CENA):
        return False
    if not any(t in texto for t in DIZ_FORMATO):
        return False
    if any(t in texto for t in DIZ_MARCA):
        return str(vista or "").lower().startswith("video")
    return True


def cenas_com_colagem(erros: list) -> list[int]:
    """Os numeros de cena que a mensagem acusa de colagem.

    Os motivos chegam de dois jeitos: lista de frases (do detector) e uma
    string so com tudo junto por `;` (do veredito da IA, como o freio monta).
    Partir por `;` antes de olhar e o que impede o segundo caso de contaminar:
    sem isso, um unico "quadro 3: colagem" faria todo numero da frase virar
    colagem, e o reparador refaria cenas que estavam boas.
    """
    achados = set()
    for erro in erros or []:
        for pedaco in str(erro).split(";"):
            texto = pedaco.lower()
            if not any(t in texto for t in DIZ_COLAGEM):
                continue
            for m in CENA_NA_MENSAGEM.finditer(pedaco):
                achados.add(int(m.group(1)))
    return sorted(achados)


def _so_render(erros: list) -> bool:
    """O unico problema e o mp4 estar defasado?"""
    return bool(erros) and all("mais nova que o video" in str(e).lower()
                               for e in erros)


def _tem_cena_sem_imagem(erros: list) -> bool:
    return any("sem imagem" in str(e).lower() for e in erros)


def _nao_da_para_consertar(erros: list) -> list[str]:
    """Os motivos que exigem gente ou outra etapa."""
    fora = []
    for erro in erros or []:
        texto = str(erro).lower()
        if texto.startswith("roteiro:") or "outra conversa" in texto:
            fora.append(str(erro))
    return fora


def _titulo_recusado(erros: list) -> bool:
    """A vistoria achou a recusa do LLM no titulo da parte?"""
    from ..roteiro import roteiro as R
    return any(R.TITULO_RECUSADO in str(e) for e in erros or [])


def _faltam_imagens(historia_id: str, parte: int) -> bool:
    """A parte tem cena sem imagem no disco? (o que o render recusa)

    E a pergunta do render (`controller._partes_com_imagens` levanta
    `ImagensFaltando`), feita antes de trocar o titulo. Sem resposta = `False`:
    o render pergunta de novo e falha com o motivo.
    """
    return bool(_faltam_na_parte(historia_id, parte))


def _faltam_na_parte(historia_id: str, parte: int) -> int:
    """Quantas cenas da parte estao sem imagem no disco (0 sem resposta)."""
    from ..imagens import fila
    try:
        return int(fila.resumo(historia_id, parte=parte)["faltam"] or 0)
    except Exception:                                          # noqa: BLE001
        return 0


def _trocar_titulo_recusado(historia_id: str, parte: int, *,
                            log=print) -> str | None:
    """Poe o titulo do plano no lugar da recusa e grava. Devolve o novo
    (`None` se o titulo do roteiro ja nao era recusa: nada foi trocado).

    05/10/2026, h59 p06: o titulo era a recusa e as 14 cenas eram normais.
    O conserto nao precisa de LLM: o titulo que a biblia planejou para a
    parte (`R.titulo_do_plano`) ou, sem ele, nenhum — `titulo_da_parte` fica
    `Marca (Parte n/N)`. O titulo recusado fica em `titulo_recusado`.
    """
    from ..roteiro import roteiro as R
    from . import conserto_de_cena as C

    roteiro = R.carregar(historia_id)
    dados = R.parte_de(roteiro, parte)
    antigo = str(dados.get("titulo") or "")
    if not R.recusa_no_titulo(roteiro, parte):
        # O laudo era de antes: o titulo ja nao e recusa. Nada a trocar (e
        # nada a devolver se o render falhar); o render ainda e preciso.
        return None
    novo = R.titulo_do_plano(historia_id, parte)
    dados["titulo_recusado"] = antigo
    dados["titulo"] = novo
    C.gravar_roteiro(historia_id, roteiro)
    log(f"[reparo] {historia_id} p{parte}: titulo recusado trocado por "
        f"\"{novo or '(so a marca)'}\".")
    return novo


class CapaNaoRefeita(RuntimeError):
    """O render do titulo trocado saiu, mas a capa da parte nao foi refeita."""


def _capa_da_parte(video, historia_id: str, parte: int) -> Path:
    """A capa que o catalogo sobe como miniatura: ao lado do mp4."""
    from ..roteiro import roteiro as R
    from ..video import capa as capa_mod
    caminho = getattr(video, "caminho", None)
    pasta = Path(caminho).parent if caminho else R.OUTPUTS / historia_id
    try:
        total = len(R.carregar(historia_id).get("partes") or [])
    except Exception:                                          # noqa: BLE001
        total = int(getattr(video, "partes", 1) or 1)
    return capa_mod.caminho(pasta, parte, total)


def _assinatura(arquivo: Path):
    try:
        info = arquivo.stat()
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)


def _conferir_capa_refeita(capa: Path, antes, inicio: float) -> None:
    """Levanta `CapaNaoRefeita` se a capa nao saiu deste render.

    06/10/2026 (conferente): `controller._capa` engole a excecao — um video
    sem capa e melhor que nenhum video. Mas no conserto do titulo a capa
    VELHA traz a recusa desenhada ("NAO CONSIGO TE AJUDAR...") e o catalogo
    a sobe como miniatura. Capa que nao existe, que e a mesma de antes ou que
    e mais velha que o render = o conserto nao aconteceu.
    """
    depois = _assinatura(capa)
    if depois is None:
        raise CapaNaoRefeita(f"a capa {capa.name} nao saiu do render")
    if depois == antes or depois[0] < int((inicio - 2.0) * 1e9):
        raise CapaNaoRefeita(
            f"a capa {capa.name} nao foi refeita (e a de antes do render, "
            "com o titulo recusado)")


def _voltar_titulo_recusado(historia_id: str, parte: int) -> None:
    """Desfaz a troca quando o render nao saiu. Nunca levanta.

    Sem isto, o roteiro limpo faria a vistoria aprovar o mp4 VELHO, que
    ainda tem a recusa desenhada na primeira imagem e na capa.
    """
    from ..roteiro import roteiro as R
    from . import conserto_de_cena as C
    try:
        roteiro = R.carregar(historia_id)
        dados = R.parte_de(roteiro, parte)
        if "titulo_recusado" in dados:
            dados["titulo"] = dados.pop("titulo_recusado")
            C.gravar_roteiro(historia_id, roteiro)
    except Exception:                                          # noqa: BLE001
        pass


NOMES_DOS_GERADORES = {"picasso": "PicassoIA", "gemini": "Gemini",
                       "chatgpt": "ChatGPT", "grok": "Grok"}


def _nome_do_gerador(historia_id: str) -> str:
    """Quem gera as imagens DESTA historia (`imagens-divisao`, 03/10/2026).

    Ate 05/10 a mensagem dizia "o PicassoIA nao devolveu a imagem" para
    qualquer gerador — e para imagem que VEIO e foi recusada como colagem.
    """
    try:
        from ..imagens import fila
        gerador = (fila.gerador_da_historia(historia_id)
                   or fila.gerador_herdado(historia_id))
    except Exception:                                          # noqa: BLE001
        gerador = ""
    gerador = str(gerador or "").lower()
    return NOMES_DOS_GERADORES.get(gerador, gerador or "o gerador")


def _registro_das_cenas(historia_id: str, parte: int, cenas) -> dict:
    """`{n: registro em imagens.json ou None}` — para desfazer junto."""
    try:
        from ..imagens import fila
        registradas = fila._meta(historia_id).get("cenas") or {}
    except Exception:                                          # noqa: BLE001
        return {}
    return {int(n): (dict(registradas[f"{int(parte)}:{int(n)}"])
                     if isinstance(registradas.get(f"{int(parte)}:{int(n)}"),
                                   dict) else None)
            for n in cenas}


def _restaurar_registros(historia_id: str, parte: int, antes: dict,
                         cenas) -> None:
    """Devolve ao `imagens.json` o registro das cenas restauradas. Nunca
    levanta. Sem isto ele ficava apontando para a imagem DESCARTADA (o
    prompt, a prova e o gerador dela) com o arquivo antigo no disco — o
    caso do pedido `bffbf4ae` (colagem com 1 calha em 19%)."""
    if not cenas:
        return
    try:
        from ..imagens import fila
        dados = fila._meta(historia_id)
        registradas = dados.setdefault("cenas", {})
        mudou = False
        for n in cenas:
            chave = f"{int(parte)}:{int(n)}"
            if int(n) not in antes:
                continue
            velho = antes[int(n)]
            if velho is None:
                mudou |= registradas.pop(chave, None) is not None
            elif registradas.get(chave) != velho:
                registradas[chave] = velho
                mudou = True
        if mudou:
            fila._gravar_meta(historia_id, dados)
    except Exception:                                          # noqa: BLE001
        pass


def _refazer_cenas(pipeline, historia_id: str, parte: int, cenas: list, *,
                   headless: bool = False, log=print,
                   motivos: dict | None = None) -> tuple:
    """Troca as imagens daquelas cenas. NUNCA deixa pior do que achou.

    Aprendido em campo, 11/09/2026 as 20:33, na primeira rodada automatica
    deste modulo. A versao anterior APAGAVA a imagem em colagem e mandava
    gerar. A geracao estourou a espera, a cena ficou SEM imagem nenhuma, e o
    render seguiu em frente e produziu um video com cartao de texto no lugar
    da cena. Ou seja: o conserto piorou o defeito — colagem e ruim, cartao de
    texto no meio da historia e pior.

    Duas regras, e as duas vem daquele minuto:

      GUARDA ANTES DE APAGAR. A imagem velha vai para `.colagem` ao lado. Se
      a nova nao vier, ela volta e o video fica exatamente como estava.
      SO RE-RENDERIZA COM PROVA. `pipeline.imagens` NAO levanta quando o site
      falha: ele devolve o resultado com erros dentro. Quem confirma e o
      arquivo existir de novo e nao ser colagem outra vez.

    Devolve `(cenas trocadas, cenas restauradas)`. `motivos`, se vier,
    recebe `{n: por que a cena foi restaurada}` (05/10/2026): "nao veio" e
    "veio em colagem" sao defeitos diferentes, de quem gera e de quem desenha.
    O registro da cena em `imagens.json` volta junto com o arquivo.
    """
    from ..imagens import composicao, fila

    registros = _registro_das_cenas(historia_id, parte, cenas)
    guardados = {}
    for n in cenas:
        arquivo = fila.caminho_da_cena(historia_id, n, parte)
        if arquivo.is_file():
            reserva = arquivo.with_suffix(arquivo.suffix + ".colagem")
            arquivo.replace(reserva)
            guardados[n] = (arquivo, reserva)
    if not guardados:
        return [], []
    log(f"[reparo] guardei a(s) cena(s) {sorted(guardados)} e vou refazer.")

    from ..imagens.worker import NaoRodou
    try:
        pipeline.imagens(historia_id, headless=headless, parte=parte, log=log)
    except NaoRodou:
        # A maquina estava ocupada, nao foi o video que falhou. Desfaz e
        # SOBE: quem chamou precisa saber que isto foi adiado, para nao
        # gastar uma das tres tentativas com algo que nem chegou a tentar.
        for arquivo, reserva in guardados.values():
            arquivo.unlink(missing_ok=True)
            reserva.replace(arquivo)
        _restaurar_registros(historia_id, parte, registros, list(guardados))
        log("[reparo] a conta estava em uso; restaurei tudo e adiei.")
        raise
    except Exception as erro:                                  # noqa: BLE001
        log(f"[reparo] a geracao falhou ({type(erro).__name__}); desfazendo.")

    gerador = _nome_do_gerador(historia_id)
    trocadas, restauradas, porque = [], [], {}
    for n, (arquivo, reserva) in sorted(guardados.items()):
        if not arquivo.is_file():
            porque[n] = f"o {gerador} nao devolveu a imagem"
        elif not composicao.e_colagem(arquivo):
            reserva.unlink(missing_ok=True)
            trocadas.append(n)
            continue
        else:
            try:
                colagem = composicao.motivo(arquivo) or "parece colagem"
            except Exception:                                  # noqa: BLE001
                colagem = "parece colagem"
            porque[n] = f"a imagem do {gerador} veio e foi recusada: {colagem}"
        # Nem veio, ou veio em painel de novo: a antiga volta.
        arquivo.unlink(missing_ok=True)
        reserva.replace(arquivo)
        restauradas.append(n)
    _restaurar_registros(historia_id, parte, registros, restauradas)
    for n in restauradas:
        log(f"[reparo] cena {n}: {porque[n]}; restaurei a imagem anterior.")
    if motivos is not None:
        motivos.update(porque)
    return trocadas, restauradas


def reparar(video, erros: list, *, pipeline=None, headless: bool = False,
            log=print) -> dict:
    """Uma passada de conserto naquele video. Nao levanta.

    Devolve `{acao, ok, detalhe}`. `acao` e o que foi tentado — e o que o
    log e o Telegram precisam para a proxima pessoa entender o que a maquina
    fez sozinha de madrugada.
    """
    from ..imagens.worker import NaoRodou

    video_id = getattr(video, "id", str(video))
    if insistente(video_id):
        return {"acao": "nada", "ok": False,
                "detalhe": f"ja tentei {TETO_DE_TENTATIVAS} vezes; parei."}

    impossivel = _nao_da_para_consertar(erros)
    if impossivel:
        return {"acao": "nada", "ok": False,
                "detalhe": "nao e conserto de imagem: " + impossivel[0][:120]}

    if pipeline is None:
        from .controller import Pipeline
        pipeline = Pipeline()
    historia_id, parte = video.fonte_id, int(video.parte)

    colagens = cenas_com_colagem(erros)
    if colagens and _tela_dividida(video, historia_id, parte):
        vista = _vista_do_veto(video)
        colagens = [n for n in colagens
                    if not _motivo_e_do_formato(erros, n, vista)]
    detalhe = ""
    veio_do_veto = any("a ia reprovou" in str(e).lower() for e in erros)
    if veio_do_veto:
        plano_da_ia = _plano_pelo_veto_da_ia(video, historia_id, parte,
                                             headless=headless, log=log)
        if plano_da_ia.get("parar"):
            parar = plano_da_ia["parar"]
            if parar.get("acao") == "nada":
                # CONTA COMO RODADA. A IA continua reprovando e nao ha conserto
                # automatico: sem gastar tentativa, o video nunca chegaria ao
                # teto e ficaria barrado para sempre, travando a fila. Pedido
                # dele em 13/09/2026: tres rodadas e o video sai.
                parar["tentativas"] = _anotar(
                    video_id, "; ".join(str(e) for e in erros),
                    "a IA reprova e nao ha conserto automatico", passada=True)
            return parar
        colagens = plano_da_ia["refazer"]
        detalhe = plano_da_ia["detalhe"]
    acao = ""
    # O TITULO RECUSADO VAI NO MESMO RENDER DO RESTO (06/10/2026). O mp4 e a
    # capa trazem o titulo na primeira imagem: trocar so no roteiro deixaria a
    # recusa queimada no video, entao o titulo do plano entra logo antes do
    # render — o do conserto que houver (colagem, imagem que falta) ou um so
    # dele. Ate 06/10 o titulo era um ramo PROPRIO e vinha antes da imagem
    # que falta: o render levantava `ImagensFaltando`, o titulo voltava, a
    # tentativa era gasta e na 3a a parte virava insistente sem nunca gerar a
    # imagem (conferente, h59 p06 com a cena 5 escondida). Imagem que nao
    # vem = nada de trocar o titulo; render ou capa que falham = o titulo
    # volta (ver `renderizar`).
    titulo = _titulo_recusado(erros)
    capa = _capa_da_parte(video, historia_id, parte) if titulo else None
    troca = {"novo": None}

    def renderizar():
        antes = inicio = None
        if titulo:
            troca["novo"] = _trocar_titulo_recusado(historia_id, parte,
                                                    log=log)
            antes, inicio = _assinatura(capa), time.time()
        try:
            pipeline.render(historia_id, parte=parte, log=log)
            if titulo:
                _conferir_capa_refeita(capa, antes, inicio)
        except BaseException:
            if troca["novo"] is not None:
                _voltar_titulo_recusado(historia_id, parte)
            raise

    trocadas = None
    try:
        if colagens:
            porque = {}
            trocadas, guardadas = _refazer_cenas(
                pipeline, historia_id, parte, colagens,
                headless=headless, log=log, motivos=porque)
            faltando = (_faltam_na_parte(historia_id, parte) if titulo
                        else 0)
            if faltando:
                # Colagem E cena sem imagem (conferente, 06/10/2026): o
                # `pipeline.imagens` de `_refazer_cenas` ja pediu todas as
                # pendentes da parte. Se alguma ainda falta, o render levantaria
                # `ImagensFaltando` com o titulo trocado e devolvido, tres
                # vezes. Adia como o ramo da imagem: titulo intocado.
                conta = _anotar(video_id, "; ".join(str(e) for e in erros),
                                f"ainda faltam {faltando} imagem(ns)")
                return {"acao": "adiado", "ok": False,
                        "detalhe": f"ainda faltam {faltando} imagem(ns); nao "
                                   "re-renderizei (o titulo recusado fica "
                                   "para quando elas vierem)",
                        "motivos_por_cena": dict(porque),
                        "tentativas": conta}
            if not trocadas and titulo:
                # As cenas voltaram como estavam, mas o titulo tem conserto
                # sozinho: renderiza por ele.
                renderizar()
                acao = (f"as cenas {sorted(porque) or colagens} nao vieram "
                        "(restaurei as antigas) e re-renderizei")
            elif not trocadas:
                # NADA de renderizar: as imagens voltaram para o lugar e o
                # video continua como estava. Ver abaixo por que isso importa.
                # O MOTIVO E POR CENA (05/10/2026): "o PicassoIA nao devolveu"
                # era dito ate para imagem que VEIO e foi recusada como colagem.
                por_cena = "; ".join(f"cena {n}: {m}"
                                     for n, m in sorted(porque.items()))
                conta = _anotar(video_id, "; ".join(str(e) for e in erros),
                                "a imagem nova nao veio; desfiz"
                                + (f" ({por_cena[:300]})" if por_cena else ""))
                return {"acao": "adiado", "ok": False,
                        "detalhe": ((por_cena or "a imagem nova nao veio")
                                    + "; restaurei a antiga e nao "
                                      "re-renderizei")[:400],
                        "motivos_por_cena": dict(porque),
                        "tentativas": conta}
            else:
                renderizar()
                acao = f"refiz as cenas {trocadas} e re-renderizei"
        elif _tem_cena_sem_imagem(erros) or (
                titulo and _faltam_imagens(historia_id, parte)):
            from ..imagens import fila
            pipeline.imagens(historia_id, headless=headless, parte=parte,
                             log=log)
            # A MESMA prova de antes. `pipeline.imagens` devolve os erros em
            # vez de levantar, entao "rodou" nao quer dizer "gerou": sem esta
            # conferencia o render sairia de novo com cartao de texto.
            faltando = fila.resumo(historia_id, parte=parte)["faltam"]
            if faltando:
                conta = _anotar(video_id, "; ".join(str(e) for e in erros),
                                f"ainda faltam {faltando} imagem(ns)")
                return {"acao": "adiado", "ok": False,
                        "detalhe": f"ainda faltam {faltando} imagem(ns); "
                                   "nao re-renderizei"
                                   + (" (o titulo recusado fica para quando "
                                      "elas vierem)" if titulo else ""),
                        "tentativas": conta}
            renderizar()
            acao = "gerei as imagens que faltavam e re-renderizei"
        elif _so_render(erros) or titulo:
            renderizar()
            acao = ("re-renderizei" if titulo else
                    "re-renderizei (o mp4 estava mais velho que as imagens)")
        else:
            return {"acao": "nada", "ok": False,
                    "detalhe": "nenhum dos motivos tem conserto automatico: "
                               + "; ".join(str(e) for e in erros)[:160]}
        if troca["novo"] is not None:
            acao = ("troquei o titulo recusado pelo do plano ("
                    + (f"\"{troca['novo']}\"" if troca["novo"]
                       else "so a marca") + "); " + acao)
    except NaoRodou as exc:
        # Pipeline pausada ou conta em uso: NAO conta tentativa. Nao foi o
        # video que falhou, foi a maquina que estava ocupada.
        return {"acao": "adiado", "ok": False, "detalhe": str(exc)[:160]}
    except Exception as exc:                                   # noqa: BLE001
        conta = _anotar(video_id, "; ".join(str(e) for e in erros),
                        f"falhou: {type(exc).__name__}")
        return {"acao": "falhou", "ok": False,
                "detalhe": f"{type(exc).__name__}: {exc}"[:160],
                "tentativas": conta}

    # A passada do veto so e gasta se as cenas do veto foram refeitas: o
    # render so pelo titulo (as cenas nao vieram) nao consertou o veto.
    passada = veio_do_veto and not (colagens and not trocadas)
    if CONFIRMAR_COM_A_IA:
        olhado = _confirmar_com_a_ia(video, historia_id, parte,
                                     headless=headless, log=log)
    else:
        # Uma passada so: o conserto nao volta ao Gemini. A vistoria mecanica
        # continua valendo (imagem faltando, audio, mp4 velho).
        olhado = _so_vistoria(video, historia_id, parte, log=log)
    if olhado and not olhado["aprovado"]:
        quem = "a IA" if CONFIRMAR_COM_A_IA else "a vistoria"
        conta = _anotar(video_id, "; ".join(str(e) for e in erros),
                        f"consertei mas {quem} ainda reprova: {acao}",
                        passada=passada)
        return {"acao": acao, "ok": False,
                "detalhe": f"{quem} olhou o video consertado e ainda reprova: "
                           + "; ".join(olhado["motivos"])[:200],
                "tentativas": conta}

    conta = _anotar(video_id, "; ".join(str(e) for e in erros), acao,
                    passada=passada)
    return {"acao": acao, "ok": True, "detalhe": detalhe,
            "tentativas": conta}


def _plano_pelo_veto_da_ia(video, historia_id: str, parte: int, *,
                           headless: bool = False, log=print) -> dict:
    """O que refazer, lido do veto da IA. `{"parar": resultado}` para sair.

    SO CONFIA EM NUMERO DE CENA. Ate 13/09/2026 o prompt do parecer nao dizia
    ao Gemini o que era "quadro 6": na folha de contato era a sexta de doze
    miniaturas espacadas no tempo, numa parte de 13 ou 14 cenas; no video, a
    contagem dele. O reparador lia esse numero como cena e podia refazer a
    imagem boa e deixar a ruim. Veto sem numeracao por cena e perguntado de
    novo AQUI, com as cenas numeradas — nunca esquecido, porque esquecer
    liberaria o video para a grade sem parecer nenhum.
    """
    from ..publicar import parecer
    from ..roteiro import roteiro as R
    from . import conserto_de_cena as C

    try:
        ficha = parecer.lembrado(video)
    except Exception:                                          # noqa: BLE001
        ficha = None
    if not C.atual(ficha) and not CONFIRMAR_COM_A_IA:
        # Uma passada so (15/09/2026): nao se pergunta de novo. Conta como a
        # rodada do video, e o veto vence.
        return {"parar": {"acao": "nada", "ok": False,
                          "detalhe": "o veto da IA nao numera as cenas e a "
                                     "regra e uma passada so no Gemini"}}
    if not C.atual(ficha):
        log(f"[reparo] {getattr(video, 'id', video)}: o veto da IA nao "
            "numera as cenas; peco para ela olhar de novo.")
        ficha = _confirmar_com_a_ia(video, historia_id, parte,
                                    headless=headless, log=log)
        if ficha is None:
            return {"parar": {"acao": "adiado", "ok": False,
                              "detalhe": "precisava que a IA olhasse de novo "
                                         "com as cenas numeradas e nao deu"}}
        if ficha.get("aprovado"):
            return {"parar": {"acao": "reolhado", "ok": True,
                              "detalhe": "olhando de novo, com as cenas "
                                         "numeradas, a IA aprovou"}}
        if not C.confiavel(ficha):
            return {"parar": {"acao": "adiado", "ok": False,
                              "detalhe": "a IA respondeu sem numerar as "
                                         "cenas; nao refaco no escuro"}}

    motivos = list(ficha.get("motivos") or [])
    classes = C.classificar(motivos)
    roteiro = R.carregar(historia_id)
    mudou, contado = False, []
    # O FILTRO VALE PARA AS TRES CLASSES, e antes de mexer no roteiro. "Cena 4:
    # aparece outra mulher se maquiando" cai em ROSTO, e sem isto trocaria a
    # descricao do protagonista em todos os prompts da serie por causa do video
    # de fundo (revisao de conflitos de 14/09/2026).
    if any(classes.values()) and _tela_dividida(video, historia_id, parte):
        vista = str(ficha.get("vista") or "")
        for classe in ("imagem", "rosto", "narracao"):
            falsas = [n for n in classes[classe]
                      if _motivo_e_do_formato(motivos, n, vista)]
            if falsas:
                classes[classe] = [n for n in classes[classe]
                                   if n not in falsas]
                contado.append(f"cena(s) {falsas}: a queixa e da tela "
                               "dividida (o formato do video), nao da cena")
    if classes["rosto"]:
        nova = str(ficha.get("protagonista") or "").strip()
        if nova:
            trocas = C.fixar_protagonista(roteiro, nova)
            mudou = True
            contado.append(f"fixei o protagonista em {trocas} prompt(s): "
                           f"{nova[:80]}")
        else:
            # Sem a descricao, refazer so sortearia outro rosto.
            classes["rosto"] = []
            contado.append("a IA apontou troca de rosto sem descrever o "
                           "protagonista")
    reescrita_nao_rodou, conta_ocupada = "", False
    if classes["narracao"]:
        # CONTA OCUPADA NAO E CULPA DO VIDEO. Em 14/09/2026, 6:21, a
        # publicacao segurava o Gemini e a reescrita pela narracao falhou por
        # isso; sem outro conserto no video, a rodada virava "nada" e gastava
        # uma das tres tentativas. Tres assim e o video saia com veto sem nunca
        # ter sido consertado. Conta ocupada adia, como o PicassoIA ocupado.
        from builds import travas
        if travas.ocupada(travas.do_perfil("gemini", "geral")):
            reescrita_nao_rodou = "a conta do Gemini esta em uso"
            conta_ocupada = True
            novos = {}
        else:
            # O GEMINI QUE NAO RESPONDE tambem nao e culpa do video: 6:32 do
            # mesmo dia, 600 s com 0 caracteres, e a terceira tentativa do
            # h10 p06 foi gasta sem conserto nenhum.
            falhas = []
            novos = C.reescrever_prompts(roteiro, parte, classes["narracao"],
                                         motivos, headless=headless, log=log,
                                         falhas=falhas)
            if falhas and not novos:
                reescrita_nao_rodou = falhas[0][:120]
        if novos:
            mudou = True
            contado.append(f"reescrevi pela narracao o prompt da(s) cena(s) "
                           f"{sorted(novos)}")
        classes["narracao"] = sorted(novos)
    if mudou:
        # NAO `R.salvar`: aquele e o gravador do roteiro avulso e remonta o
        # arquivo so com titulo, cta e cenas — numa serie apagaria tudo.
        C.gravar_roteiro(historia_id, roteiro)
    refazer = sorted(set(classes["imagem"]) | set(classes["rosto"])
                     | set(classes["narracao"]))
    if not refazer:
        if (reescrita_nao_rodou and UMA_PASSADA and not CONFIRMAR_COM_A_IA
                and not conta_ocupada
                and "ContaOcupada" not in reescrita_nao_rodou):
            # Uma passada so (revisao de 15/09/2026): o Gemini que nao responde
            # a reescrita gasta a passada do veto. Adiar reabria o Gemini a
            # cada rodada para o mesmo video, e ele seguia barrado.
            return {"parar": {"acao": "nada", "ok": False,
                              "detalhe": "a reescrita pelo Gemini nao rodou "
                                         f"({reescrita_nao_rodou}) e a regra "
                                         "e uma passada so"}}
        if reescrita_nao_rodou:
            return {"parar": {"acao": "adiado", "ok": False,
                              "detalhe": "a reescrita pela narracao nao rodou "
                                         f"({reescrita_nao_rodou}); tento de "
                                         "novo na proxima rodada"}}
        return {"parar": {"acao": "nada", "ok": False,
                          "detalhe": "nenhum motivo da IA tem conserto "
                                     "automatico: "
                                     + "; ".join(motivos)[:160]}}
    return {"refazer": refazer, "detalhe": "; ".join(contado)}


def _so_vistoria(video, historia_id: str, parte: int, *,
                 log=print) -> dict | None:
    """A vistoria mecanica do video consertado, sem perguntar a IA."""
    from ..publicar import qualidade
    from ..roteiro import roteiro as R
    try:
        laudo = qualidade.vistoriar_parte(historia_id, parte, video.caminho,
                                          R.carregar(historia_id))
    except Exception as exc:                                   # noqa: BLE001
        log(f"[reparo] a vistoria do conserto falhou ({type(exc).__name__}: {exc}).")
        return None
    return {"aprovado": bool(laudo.get("ok")),
            "motivos": list(laudo.get("erros") or [])}


def _confirmar_com_a_ia(video, historia_id: str, parte: int, *,
                        headless: bool = False, log=print) -> dict | None:
    """O video consertado ficou bom MESMO? Quem responde e quem assiste.

    O detector de colagem olha pixel: ele sabe dizer que nao ha mais faixa
    dividindo a imagem, e nao sabe dizer que a cena nova continua sem ter
    nada a ver com a narracao. Confirmar conserto por pixel e conferir a
    parte facil e chamar de pronto.

    Entao o reparo fecha no mesmo crivo do publicador: a vistoria mecanica
    mais o parecer de quem viu o video. Se a IA ainda reprova, o conserto
    nao aconteceu — e gasta tentativa, porque tentar de novo o mesmo caminho
    tende a dar no mesmo.

    `None` quando nao deu para perguntar: isso NAO e reprovacao, e o
    publicador vai perguntar de novo no horario.
    """
    from ..publicar import parecer, qualidade
    from ..roteiro import roteiro as R

    try:
        roteiro = R.carregar(historia_id)
        laudo = qualidade.vistoriar_parte(historia_id, parte, video.caminho,
                                          roteiro)
        if not laudo.get("ok"):
            # A vistoria mecanica ainda barra: nem vale gastar o navegador.
            return {"aprovado": False,
                    "motivos": list(laudo.get("erros") or [])}
        return parecer.pedir(video, roteiro, parte, laudo=laudo,
                             headless=headless, log=log)
    except parecer.SemParecer as exc:
        log(f"[reparo] nao consegui pedir o parecer ({exc}); o publicador "
            "pergunta de novo no horario.")
        return None
    except Exception as exc:                                   # noqa: BLE001
        log(f"[reparo] a confirmacao falhou ({type(exc).__name__}: {exc}).")
        return None


def rodada(*, limite: int = 2, headless: bool = False, log=print,
           posse=None) -> dict:
    """Conserta o que estiver barrado. Chamada pela agenda, antes de criar.

    `limite` porque cada conserto custa geracao de imagem mais um render: uma
    noite com seis barrados nao pode virar seis renders enfileirados na frente
    da criacao, que e o que abastece a grade.

    `posse(historia_id)` (rodada em paralelo, 06/10/2026) e um gerenciador de
    contexto que diz se ESTA rodada pode consertar a historia (True) e a
    segura enquanto conserta; o barrado que nao e dela e pulado e nao gasta o
    `limite`. Sem `posse`, os `limite` primeiros, como sempre.
    """
    from . import agenda

    barrados = agenda.barrados_no_estoque()
    if not barrados:
        return {"barrados": 0, "consertados": 0, "insistentes": [],
                "acoes": []}

    from .controller import Pipeline
    pipeline = Pipeline()
    acoes, consertados = [], 0
    # OS INSISTENTES SAEM ANTES DO LIMITE (revisao de 15/09/2026): cortar
    # primeiro deixava videos que ja esgotaram as tentativas ocupando as vagas,
    # e o barrado seguinte nunca era tentado.
    insistentes = [v.id for v, _e in barrados if insistente(v.id)]
    tentaveis = [(v, e) for v, e in barrados if not insistente(v.id)]
    if posse is None:
        tentaveis = tentaveis[:limite]
    feitos = 0
    for video, erros in tentaveis:
        if feitos >= limite:
            break
        with (posse(video.fonte_id) if posse is not None
              else contextlib.nullcontext(True)) as minha:
            if not minha:
                continue
            feitos += 1
            log(f"[reparo] {video.id}: {erros[0][:100]}")
            resultado = reparar(video, erros, pipeline=pipeline,
                                headless=headless, log=log)
        acoes.append({"video": video.id, **resultado})
        if resultado.get("ok"):
            consertados += 1
            log(f"[reparo] {video.id}: {resultado['acao']}.")
        else:
            log(f"[reparo] {video.id}: {resultado['detalhe']}")
    # SO ESQUECE QUEM REALMENTE PASSOU. A primeira versao comparava com
    # `barrados_no_estoque()` quando ela ainda olhava so a vistoria mecanica:
    # o video re-renderizado passava ali, o contador zerava, e a IA continuava
    # reprovando — reparo eterno, tres tentativas de cada vez, sem nunca virar
    # insistente. Agora aquela funcao ja conta o veto da IA, e uma chamada so
    # responde pelos dois crivos.
    ainda_barrados = {v.id for v, _e in agenda.barrados_no_estoque()}
    for video, _erros in barrados:
        # VETO VENCIDO NAO E CONSERTO. Depois das tres rodadas o video deixa
        # de aparecer como barrado porque o veto venceu, e nao porque passou.
        # Zerar a conta dele aqui o traria de volta para a fila de barrados:
        # foi o que aconteceu na primeira rodada com a regra, em 13/09/2026, e
        # os quatro videos liberados voltaram a travar.
        if video.id not in ainda_barrados and not veto_consumido(video.id):
            esquecer(video.id)
    return {"barrados": len(barrados), "consertados": consertados,
            "insistentes": sorted(set(insistentes)
                                  | {v.id for v, _e in barrados
                                     if insistente(v.id)}),
            "acoes": acoes}


__all__ = ["reparar", "rodada", "insistente", "tentativas", "esquecer",
           "consertado", "cenas_com_colagem", "TETO_DE_TENTATIVAS"]
