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

import json
import re
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"
REGISTRO = OUTPUTS / "_reparos.json"

# Tres passadas por video. Cada uma custa geracao de imagem na conta
# compartilhada mais um render de ~2 min; alem disso e teimosia.
TETO_DE_TENTATIVAS = 3

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
    """Ja bateu o teto? Entao nao se tenta mais — e nem se avisa de novo."""
    return tentativas(video_id) >= TETO_DE_TENTATIVAS


def _anotar(video_id: str, motivo: str, feito: str) -> int:
    dados = _ler()
    ficha = dados.setdefault(str(video_id), {"tentativas": 0})
    ficha["tentativas"] = int(ficha.get("tentativas") or 0) + 1
    ficha["quando"] = datetime.now().isoformat(timespec="seconds")
    ficha["motivo"] = str(motivo)[:200]
    ficha["feito"] = feito
    _gravar(dados)
    return ficha["tentativas"]


def esquecer(video_id: str) -> None:
    """O video passou: a conta zera. Sem isto, um video consertado na
    terceira tentativa entraria na quarta como insistente."""
    dados = _ler()
    if str(video_id) in dados:
        del dados[str(video_id)]
        _gravar(dados)


# O MESMO DEFEITO TEM TRES NOMES. O nosso detector diz "colagem"; o Gemini,
# olhando a mesma imagem, escreve "tela dividida" ou "grade de paineis".
# Exigir a palavra literal deixava dois tercos dos motivos de fora.
DIZ_COLAGEM = ("colagem", "tela dividida", "grade de paine", "grade de painé",
               "dividida em", "paineis separados", "painéis separados")


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


def _refazer_cenas(pipeline, historia_id: str, parte: int, cenas: list, *,
                   headless: bool = False, log=print) -> tuple:
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

    Devolve `(cenas trocadas, cenas restauradas)`.
    """
    from ..imagens import composicao, fila

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
        log("[reparo] a conta estava em uso; restaurei tudo e adiei.")
        raise
    except Exception as erro:                                  # noqa: BLE001
        log(f"[reparo] a geracao falhou ({type(erro).__name__}); desfazendo.")

    trocadas, restauradas = [], []
    for n, (arquivo, reserva) in sorted(guardados.items()):
        nova_serve = arquivo.is_file() and not composicao.e_colagem(arquivo)
        if nova_serve:
            reserva.unlink(missing_ok=True)
            trocadas.append(n)
            continue
        # Nem veio, ou veio em painel de novo: a antiga volta.
        arquivo.unlink(missing_ok=True)
        reserva.replace(arquivo)
        restauradas.append(n)
    if restauradas:
        log(f"[reparo] a(s) cena(s) {restauradas} nao melhoraram; "
            "restaurei a imagem anterior.")
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
    detalhe = ""
    if any("a ia reprovou" in str(e).lower() for e in erros):
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
                    "a IA reprova e nao ha conserto automatico")
            return parar
        colagens = plano_da_ia["refazer"]
        detalhe = plano_da_ia["detalhe"]
    acao = ""
    try:
        if colagens:
            trocadas, guardadas = _refazer_cenas(
                pipeline, historia_id, parte, colagens,
                headless=headless, log=log)
            if not trocadas:
                # NADA de renderizar: as imagens voltaram para o lugar e o
                # video continua como estava. Ver abaixo por que isso importa.
                conta = _anotar(video_id, "; ".join(str(e) for e in erros),
                                "a imagem nova nao veio; desfiz")
                return {"acao": "adiado", "ok": False,
                        "detalhe": "o PicassoIA nao devolveu a imagem; "
                                   "restaurei a antiga e nao re-renderizei",
                        "tentativas": conta}
            pipeline.render(historia_id, parte=parte, log=log)
            acao = f"refiz as cenas {trocadas} e re-renderizei"
        elif _tem_cena_sem_imagem(erros):
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
                                   "nao re-renderizei",
                        "tentativas": conta}
            pipeline.render(historia_id, parte=parte, log=log)
            acao = "gerei as imagens que faltavam e re-renderizei"
        elif _so_render(erros):
            pipeline.render(historia_id, parte=parte, log=log)
            acao = "re-renderizei (o mp4 estava mais velho que as imagens)"
        else:
            return {"acao": "nada", "ok": False,
                    "detalhe": "nenhum dos motivos tem conserto automatico: "
                               + "; ".join(str(e) for e in erros)[:160]}
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

    olhado = _confirmar_com_a_ia(video, historia_id, parte,
                                 headless=headless, log=log)
    if olhado and not olhado["aprovado"]:
        conta = _anotar(video_id, "; ".join(str(e) for e in erros),
                        f"consertei mas a IA ainda reprova: {acao}")
        return {"acao": acao, "ok": False,
                "detalhe": "a IA olhou o video consertado e ainda reprova: "
                           + "; ".join(olhado["motivos"])[:200],
                "tentativas": conta}

    conta = _anotar(video_id, "; ".join(str(e) for e in erros), acao)
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
    reescrita_nao_rodou = ""
    if classes["narracao"]:
        # CONTA OCUPADA NAO E CULPA DO VIDEO. Em 14/09/2026, 6:21, a
        # publicacao segurava o Gemini e a reescrita pela narracao falhou por
        # isso; sem outro conserto no video, a rodada virava "nada" e gastava
        # uma das tres tentativas. Tres assim e o video saia com veto sem nunca
        # ter sido consertado. Conta ocupada adia, como o PicassoIA ocupado.
        from builds import travas
        if travas.ocupada(travas.do_perfil("gemini", "geral")):
            reescrita_nao_rodou = "a conta do Gemini esta em uso"
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


def rodada(*, limite: int = 2, headless: bool = False, log=print) -> dict:
    """Conserta o que estiver barrado. Chamada pela agenda, antes de criar.

    `limite` porque cada conserto custa geracao de imagem mais um render: uma
    noite com seis barrados nao pode virar seis renders enfileirados na frente
    da criacao, que e o que abastece a grade.
    """
    from . import agenda

    barrados = agenda.barrados_no_estoque()
    if not barrados:
        return {"barrados": 0, "consertados": 0, "insistentes": [],
                "acoes": []}

    from .controller import Pipeline
    pipeline = Pipeline()
    acoes, consertados, insistentes = [], 0, []
    for video, erros in barrados[:limite]:
        if insistente(video.id):
            insistentes.append(video.id)
            continue
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
        if video.id not in ainda_barrados and not insistente(video.id):
            esquecer(video.id)
    return {"barrados": len(barrados), "consertados": consertados,
            "insistentes": insistentes + [v.id for v, _e in barrados
                                          if insistente(v.id)],
            "acoes": acoes}


__all__ = ["reparar", "rodada", "insistente", "tentativas", "esquecer",
           "cenas_com_colagem", "TETO_DE_TENTATIVAS"]
