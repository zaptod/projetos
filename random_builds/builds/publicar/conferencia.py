# -*- coding: utf-8 -*-
"""O ledger contra o canal — a unica pergunta que ninguem fazia.

Por que existe: entre 10 e 15/09/2026, 29 videos entraram no
`publicados.jsonl` como publicados e estavam como RASCUNHO no canal. Cinco
dias, um por postagem, e nenhum alarme disparou — porque auditoria, gordura
e meta leem o MESMO ledger que estava errado. `auditoria.metas()` compara
ledger contra grade, o que e o ledger contra si mesmo. Quem descobriu foi o
Adrian, olhando o canal com os proprios olhos.

O que ja existia e nao resolvia:

  `metricas.reconciliar` baixa os uploads reais do canal e casa por titulo,
  mas so PREENCHE id faltante — nunca denuncia linha sem video nem video sem
  linha. E mutirao de completar, nao auditoria.

  `tiktok_metricas.casar` casa a hora da postagem com o ledger e apenas LOGA
  a taxa. O numero passava na tela toda noite sem ninguem somar.

A regra desta casa: `conferir` e PURA quando as duas listas sao injetadas.
So `buscar_no_canal` toca a rede, e ela e chamada em um lugar so. E o que
permite testar a deteccao do caso de 15/09 sem pedir nada ao YouTube.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from .. import grade
from . import metricas, titulos

# Janela curta de proposito. O acervo antigo nao tem laudo nem id, e uma
# conferencia que acende para tudo no primeiro dia e uma conferencia que
# ninguem olha no segundo.
DIAS_PADRAO = 3


def pasta(canal: str = "builds") -> Path:
    return metricas.pasta_do_canal(canal).parent / "_conferencia"


def _recente(quando: str, desde: date) -> bool:
    try:
        return datetime.fromisoformat(str(quando)).date() >= desde
    except (TypeError, ValueError):
        return False


def _dia_do_canal(ts) -> date:
    """O dia LOCAL de um `publishedAt` do YouTube (vem em UTC, com Z).

    Sem data, o video fica no passado remoto: nao da para dizer que e
    recente, e contar como recente o faria virar orfao todo dia.
    """
    try:
        quando = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return date.min
    if quando.tzinfo is not None:
        quando = quando.astimezone()
    return quando.date()


# ------------------------------------------------------------ o dia de grade
# A CONFERENCIA RODA DE MADRUGADA (01:28 a 05:20 em 27/09/2026) e contava os
# posts do dia do CALENDARIO que tinha acabado de comecar. As 05:20 o unico
# horario desse dia que ja venceu e o das 00:37: um dia 10/10 dava deficit 9,
# todas as noites. A pergunta certa e sobre o dia de grade que ACABOU de
# fechar, e ele nao e o do calendario.

def _minutos(hora: int) -> int:
    return int(hora) * 60 + grade.minuto(hora)


def _horas_em_ordem(plataforma: str) -> list:
    """As horas da plataforma na ordem do relogio (00:37 primeiro)."""
    return sorted(grade.horas_da_plataforma(plataforma), key=_minutos)


def _abertura_e_fechamento(plataforma: str) -> tuple:
    """(primeira, ultima) hora do DIA DE GRADE daquela plataforma.

    O dia de grade abre no horario que vem depois do MAIOR buraco da grade e
    fecha no que vem antes dele. O maior buraco e a madrugada (em 27/09/2026,
    00:37 -> 06:37, seis horas): o dia abre as 06:37 e fecha as 00:37 do dia
    seguinte. Nenhum horario escrito aqui — se a grade mudar, o dia de grade
    muda junto.
    """
    horas = _horas_em_ordem(plataforma)

    def buraco_antes(i: int) -> int:
        return (_minutos(horas[i]) - _minutos(horas[i - 1])) % (24 * 60)

    i = max(range(len(horas)), key=buraco_antes)
    return horas[i], horas[i - 1]


def _horario_da_grade(quando: datetime, plataforma: str) -> tuple:
    """(dia do calendario, hora) do horario da grade a que `quando` pertence.

    O criterio de `grade.slot`: o ultimo horario que ja venceu. A rodada das
    17:57 que termina as 18:01, e a recuperada que so rodou as 19:30, ainda
    sao aquele horario. Antes do primeiro horario do relogio, o momento e do
    ultimo de ontem.
    """
    passados = grade.vencidos(quando, plataforma)
    if passados:
        return quando.date(), max(passados, key=_minutos)
    return quando.date() - timedelta(days=1), _horas_em_ordem(plataforma)[-1]


def _dia_de_grade(dia: date, hora: int, plataforma: str) -> date:
    """O dia de grade a que pertence o horario `hora` do dia `dia`."""
    abertura, _ = _abertura_e_fechamento(plataforma)
    if _minutos(hora) >= _minutos(abertura):
        return dia
    return dia - timedelta(days=1)


def dia_de_grade_fechado(agora: datetime | None = None,
                         plataforma: str = "youtube") -> date:
    """O ultimo dia de grade com TODOS os horarios ja vencidos.

    As 05:20 de 28/09 e o de 27/09 (06:37 de 27 ate 00:37 de 28). As 14:00 de
    28/09 continua sendo o de 27/09: o de 28 ainda nao fechou. As 00:30 de
    28/09 e o de 26/09, porque o das 00:37 ainda nao venceu.
    """
    agora = agora or datetime.now()
    dia, hora = _horario_da_grade(agora, plataforma)
    corrente = _dia_de_grade(dia, hora, plataforma)
    _, fechamento = _abertura_e_fechamento(plataforma)
    return corrente if hora == fechamento else corrente - timedelta(days=1)


def _instante_local(ts) -> datetime | None:
    """`quando` do ledger (hora local, sem fuso) como datetime local."""
    try:
        quando = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if quando.tzinfo is not None:
        quando = quando.astimezone().replace(tzinfo=None)
    return quando


ACEITOS_MOTIVO = ("decisão do Adrian 15/09/2026: os rascunhos do "
                  "\"Publicar mesmo assim\" ficam de gordura")


def arquivo_de_aceitos() -> Path:
    """Fora do repositorio: e estado da operacao, nao codigo."""
    from .. import contas
    return contas.runtime_dir() / "rascunhos_aceitos.json"


def rascunhos_aceitos() -> dict:
    """{youtube_id: ficha} dos rascunhos que ja se decidiu deixar. Nunca levanta."""
    try:
        dados = json.loads(arquivo_de_aceitos().read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    ids = dados.get("ids") if isinstance(dados, dict) else None
    return ids if isinstance(ids, dict) else {}


def aceitar(itens, motivo: str, canal: str = "builds") -> Path:
    """Grava videos PRIVADOS como conhecidos e aceitos, cada um com o motivo.

    Serve para rascunho do ledger e para orfao privado — a lista e por id do
    video, e o que importa e que uma PESSOA decidiu. Soma aos que ja estavam
    e nunca apaga; um id ja aceito mantem o motivo original.

    Nunca e chamada pela rodada da madrugada: se fosse, todo privado novo
    seria aceito na mesma noite em que aparecesse.
    """
    destino = arquivo_de_aceitos()
    atuais = rascunhos_aceitos()
    agora = datetime.now().isoformat(timespec="seconds")
    for item in itens or ():
        vid = item.get("youtube_id")
        if vid and vid not in atuais:
            atuais[vid] = {"canal": canal,
                           "video_id": item.get("video_id"),
                           "titulo": item.get("titulo"),
                           "quando_no_ledger": item.get("quando"),
                           "publicado_em": item.get("publicado_em"),
                           "aceito_em": agora, "motivo": motivo}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"ids": atuais}, ensure_ascii=False,
                                  indent=1), encoding="utf-8")
    return destino


def aceitar_rascunhos(ficha: dict, motivo: str = ACEITOS_MOTIVO) -> Path:
    """Os rascunhos do ledger DESTA ficha, como aceitos."""
    return aceitar(ficha.get("rascunhos") or [], motivo,
                   ficha.get("canal") or "builds")


def conferir(canal: str = "builds", plataforma: str = "youtube", *,
             dias: int = DIAS_PADRAO, publicados=None, no_canal=None,
             hoje: date | None = None, aceitos: dict | None = None,
             agora: datetime | None = None) -> dict:
    """O que o ledger afirma contra o que o canal tem de fato.

    `publicados` sao as linhas do ledger; `no_canal` e o que a plataforma
    devolveu. Injetando as duas, nada aqui toca a rede.

    `agora` e o relogio da conferencia: dele saem o dia da ficha e o dia de
    grade conferido. Quem passa so `hoje` recebe o relogio no fim desse dia.
    """
    if agora is None:
        agora = (datetime.combine(hoje, datetime.max.time()) if hoje
                 else datetime.now())
    hoje = hoje or agora.date()
    desde = hoje - timedelta(days=max(0, int(dias)))
    if publicados is None:
        publicados = metricas.publicados(canal)
    if no_canal is None:
        no_canal = buscar_no_canal(canal, plataforma)

    linhas = [l for l in (publicados or ())
              if isinstance(l, dict) and l.get("plataforma") == plataforma
              and _recente(l.get("quando"), desde)]
    do_canal = [v for v in (no_canal or ()) if isinstance(v, dict)]

    por_id = {str(v.get("id")): v for v in do_canal if v.get("id")}
    por_titulo = {}
    for v in do_canal:
        chave = titulos.chave(v.get("titulo"))
        if chave:
            por_titulo.setdefault(chave, v)

    def achar(linha: dict):
        """O video do canal que casa com a linha do ledger, ou `None`."""
        return por_id.get(str(linha.get("youtube_id") or "")) \
            or por_titulo.get(titulos.chave(linha.get("titulo")))

    fantasmas, casados, rascunhos, so_sd = [], [], [], []
    vistos = set()
    for linha in linhas:
        alvo = achar(linha)
        ficha = {"video_id": linha.get("video_id"),
                 "titulo": linha.get("titulo"),
                 "quando": linha.get("quando"),
                 "prova_ok": linha.get("prova_ok")}
        if alvo is None:
            # O LEDGER AFIRMA E O CANAL NAO TEM. E o nome exato do defeito.
            fantasmas.append(ficha)
            continue
        vistos.add(id(alvo))
        casados.append(ficha)
        if str(alvo.get("privacidade") or "").lower() in ("private", "privado"):
            # A ASSINATURA DO RASCUNHO DE 15/09/2026.
            rascunhos.append({**ficha, "youtube_id": alvo.get("id"),
                              "privacidade": alvo.get("privacidade"),
                              "upload": alvo.get("upload")})
        if str(alvo.get("definicao") or "").lower() == "sd":
            so_sd.append({**ficha, "youtube_id": alvo.get("id")})

    # ORFAO E DUPLICADO SO DENTRO DA JANELA. Na primeira rodada real
    # (16/09/2026) a janela de 3 dias do ledger era comparada com o canal
    # INTEIRO: 98 "orfaos" em builds e 58 em historias, que eram so os videos
    # antigos. Um numero que e sempre grande nao diz nada.
    na_janela = [v for v in do_canal
                 if _dia_do_canal(v.get("publicado_em")) >= desde]
    orfaos = [{"youtube_id": v.get("id"), "titulo": v.get("titulo"),
               "publicado_em": v.get("publicado_em"),
               "privacidade": v.get("privacidade")}
              for v in na_janela if id(v) not in vistos]

    # Duplicado conta o canal todo, MAS so entra se um dos videos e recente:
    # restringir os dois a janela esconderia justamente o caso que importa,
    # um video novo com o titulo de um antigo.
    contagem = {}
    for v in do_canal:
        chave = titulos.chave(v.get("titulo"))
        if chave:
            contagem.setdefault(chave, []).append(v)
    recentes = {id(v) for v in na_janela}
    duplicados = [{"chave": k, "ids": [v.get("id") for v in grupo]}
                  for k, grupo in contagem.items()
                  if len(grupo) > 1 and any(id(v) in recentes for v in grupo)]

    # RASCUNHO JA CONHECIDO E ACEITO nao suja. Decisao do Adrian em 15/09:
    # os rascunhos do "Publicar mesmo assim" ficam como gordura. Sem esta
    # separacao a madrugada acusaria o mesmo estado sabido todas as noites
    # ate ele sair da janela, e o apurador investigaria o que ja foi decidido.
    # Rascunho NOVO, fora da lista, continua sujando.
    aceitos = rascunhos_aceitos() if aceitos is None else aceitos
    ja_aceitos = [r for r in rascunhos if r.get("youtube_id") in aceitos]
    rascunhos = [r for r in rascunhos if r.get("youtube_id") not in aceitos]

    # ORFAO PRIVADO SUJA. Um video privado no canal, sem linha no ledger, e
    # um upload que ninguem registrou e que nao foi ao ar — o mesmo sintoma
    # do rascunho, visto pelo outro lado. Na primeira rodada real (16/09)
    # havia 10 deles, e como orfao nunca sujava, a conferencia disse "limpo".
    # Os que uma pessoa ja explicou ficam na mesma lista de aceitos.
    privados = [o for o in orfaos
                if str(o.get("privacidade") or "").lower()
                in ("private", "privado")]
    orfaos_privados = [o for o in privados
                       if o.get("youtube_id") not in aceitos]
    orfaos_privados_aceitos = [o for o in privados
                               if o.get("youtube_id") in aceitos]

    # DUAS LINHAS DO LEDGER PARA O MESMO VIDEO: o ledger conta duas
    # publicacoes onde o canal tem uma. Achado da primeira rodada real
    # (I9ETJSGR1A0 e opdRgGJ1y_8, em 15/09). Registrado, nao corrigido: a
    # cura do ledger e decisao do Adrian.
    por_video: dict = {}
    for linha in linhas:
        vid = str(linha.get("youtube_id") or "")
        if vid:
            por_video.setdefault(vid, []).append(
                {"video_id": linha.get("video_id"),
                 "quando": linha.get("quando")})
    mesmo_video = [{"youtube_id": vid, "linhas": grupo}
                   for vid, grupo in por_video.items() if len(grupo) > 1]

    # CANAL PARADO TIRAVA NOTA MAXIMA. Ate 27/09/2026 a unica pergunta era
    # "o que o ledger afirma esta no canal?" — e um canal que nao publica NADA
    # nao afirma nada, entao passava com taxa 1,0 e veredito limpo. Foi o que
    # aconteceu em 24, 25, 26 e 27/09 com o builds: zero publicacoes, quatro
    # noites de "limpo". A intencao (a grade prometeu N por dia) tambem entra
    # na conta, senao a conferencia mede so o que existe e nunca o que falta.
    #
    # O DIA CONFERIDO E O DIA DE GRADE QUE JA FECHOU, nao o do calendario. A
    # conferencia roda de madrugada, e ate 27/09/2026 contava o dia que tinha
    # acabado de comecar: as 05:20 so o horario das 00:37 existia nele, e um
    # dia 10/10 dava deficit 9.
    dia_da_grade = dia_de_grade_fechado(agora, plataforma)
    abertura, fechamento = _abertura_e_fechamento(plataforma)
    horas = _horas_em_ordem(plataforma)
    ordem = horas[horas.index(abertura):] + horas[:horas.index(abertura)]
    prometidos = len(ordem)

    # HORARIO, NAO LINHA: a grade promete um video por horario. Duas linhas no
    # mesmo horario (a normal e a recuperacao) pagam um horario so, e o mesmo
    # video em duas linhas do ledger (I9ETJSGR1A0, 15/09) paga um so.
    #
    # So paga o que o CANAL confirma PUBLICO. Linha sem video la ja esta em
    # `fantasmas` — conta-la seria medir o ledger contra ele mesmo — e
    # rascunho no canal (15/09) e horario sem video para quem assiste.
    #
    # Sai do ledger inteiro, e nao da janela de `dias`: com `--dias 0` a
    # metade do dia de grade antes da meia-noite ficaria de fora.
    cumpridos, usados, linhas_do_dia = set(), set(), 0
    for linha in sorted((l for l in (publicados or ())
                         if isinstance(l, dict)
                         and l.get("plataforma") == plataforma),
                        key=lambda l: str(l.get("quando") or "")):
        instante = _instante_local(linha.get("quando"))
        if instante is None:
            continue
        dia, hora = _horario_da_grade(instante, plataforma)
        if _dia_de_grade(dia, hora, plataforma) != dia_da_grade:
            continue
        linhas_do_dia += 1
        video = achar(linha)
        if video is None or id(video) in usados:
            continue
        if str(video.get("privacidade") or "").lower() != "public":
            continue
        usados.add(id(video))
        cumpridos.add(hora)
    em_falta = [grade.horario(h) for h in ordem if h not in cumpridos]
    deficit = len(em_falta)
    ultimo_dia = dia_da_grade + timedelta(
        days=1 if _minutos(fechamento) < _minutos(abertura) else 0)

    # DUAS PERGUNTAS, DOIS VEREDITOS. "O ledger bate com o canal?" e "a grade
    # foi cumprida?" nao sao a mesma coisa: um canal parado tem ledger
    # coerente (nao afirma nada) e grade furada. Misturar as duas faria toda
    # ficha de dia parcial nascer suja e apagaria o significado de `sujo`.
    sujo = bool(fantasmas or rascunhos or orfaos_privados)
    return {
        "canal": canal, "plataforma": plataforma,
        "dia": hoje.isoformat(), "janela_dias": int(dias),
        "dia_de_grade": dia_da_grade.isoformat(),
        "janela_da_grade": [
            f"{dia_da_grade.isoformat()}T{grade.horario(abertura)}",
            f"{ultimo_dia.isoformat()}T{grade.horario(fechamento)}"],
        "slots_da_grade": prometidos,
        "horarios_cumpridos": len(cumpridos),
        "horarios_em_falta": em_falta,
        "linhas_no_dia_de_grade": linhas_do_dia,
        "deficit": deficit,
        "grade": "em falta" if deficit else "cumprida",
        "no_ledger": len(linhas), "no_canal": len(do_canal),
        "no_canal_na_janela": len(na_janela),
        "casados": len(casados),
        "fantasmas": fantasmas, "orfaos": orfaos,
        "orfaos_privados": orfaos_privados,
        "orfaos_privados_aceitos": orfaos_privados_aceitos,
        "rascunhos": rascunhos, "rascunhos_aceitos": ja_aceitos,
        "so_sd": so_sd, "duplicados": duplicados,
        "mesmo_video": mesmo_video,
        "taxa": round(len(casados) / len(linhas), 3) if linhas else 1.0,
        "veredito": "sujo" if sujo else "limpo",
        "quando": datetime.now().isoformat(timespec="seconds"),
    }


def buscar_no_canal(canal: str = "builds",
                    plataforma: str = "youtube") -> list:
    """A UNICA funcao com rede. Devolve o que a plataforma diz ter."""
    if plataforma != "youtube":
        raise ValueError(
            "so o YouTube tem consulta direta. O TikTok nao expoe a lista "
            "por API: a conferencia dele passa pelo Studio, em "
            "`tiktok_metricas.coletar`.")
    # `_token` devolve (token, credenciais). Ate 16/09/2026 a TUPLA inteira
    # ia para o cabecalho `Authorization`, o Google respondia 401, e o 401
    # virava "token invalido ou revogado" — um diagnostico falso que chegou
    # a ser repassado ao Adrian como "os tres tokens estao revogados".
    token, _ = metricas._token(canal)
    enviados = metricas.enviados(token)
    ids = [v.get("youtube_id") or v.get("id") for v in enviados]
    ids = [i for i in ids if i]
    detalhes = metricas.estatisticas(ids, token) if ids else {}
    saida = []
    for v in enviados:
        vid = v.get("youtube_id") or v.get("id")
        saida.append({**(detalhes.get(vid) or {}),
                      "id": vid, "titulo": v.get("titulo")})
    return saida


def salvar(ficha: dict) -> Path:
    destino = pasta(ficha.get("canal", "builds"))
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{ficha.get('dia', 'hoje')}.json"
    caminho.write_text(json.dumps(ficha, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    return caminho


def ultima(canal: str = "builds") -> dict:
    """A conferencia mais recente daquele canal, ou `{}`."""
    try:
        arquivos = sorted(pasta(canal).glob("*.json"))
        return json.loads(arquivos[-1].read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, IndexError):
        return {}


def conferir_tudo(canais=("builds", "historias"), *, dias: int = DIAS_PADRAO,
                  log=print, agora: datetime | None = None) -> dict:
    """Confere cada canal, grava e ACENDE o alarme quando esta sujo.

    O alarme nao tem uma linha de Telegram: uma linha de erro no diario ja
    vira aviso no celular (`bot._alertar`) e ja convoca a apuracao automatica
    do Claude. Escrever um segundo caminho de aviso seria criar a proxima
    divergencia.
    """
    from .. import atividade

    fichas = {}
    for canal in canais:
        try:
            ficha = conferir(canal, dias=dias, agora=agora)
        except Exception as exc:                               # noqa: BLE001
            # Servico da noite NAO derruba rodada. E o OAuth de um canal pode
            # estar morto sem que o outro esteja.
            log(f"[conferencia] {canal}: {type(exc).__name__}: {exc}")
            fichas[canal] = {"canal": canal,
                             "dia": (agora or datetime.now()).date().isoformat(),
                             "erro": f"{type(exc).__name__}: {exc}"}
            # A FALHA TAMBEM VAI PARA DISCO. Sem isto a pagina via "nunca
            # rodou" — medido em 16/09/2026, com os tres tokens revogados — e
            # "nunca rodou" e "rodou e o token morreu" pedem acoes diferentes.
            try:
                salvar(fichas[canal])
            except OSError:
                pass
            continue
        salvar(ficha)
        fichas[canal] = ficha
        log(f"[conferencia] {canal}: {ficha['casados']}/{ficha['no_ledger']} "
            f"casados, {len(ficha['fantasmas'])} fantasma(s), "
            f"{len(ficha['rascunhos'])} rascunho(s), "
            f"{len(ficha.get('orfaos_privados') or [])} privado(s) fora do "
            f"ledger, {ficha.get('horarios_cumpridos', 0)}/"
            f"{ficha.get('slots_da_grade', 0)} horarios cumpridos no dia de "
            f"grade {ficha.get('dia_de_grade', '?')} — {ficha['veredito']}")
        if ficha["veredito"] == "sujo":
            # FABRICA PROPRIA, e nao "publicacao". O alarme continua indo ao
            # celular (o bot le todo erro do diario), mas o apurador ignora
            # esta fabrica: em 16/09/2026 dois alarmes daqui dispararam um
            # conserto automatico que editou codigo por causa de rascunhos
            # no canal — achado de dados, nao defeito do fonte.
            atividade.registrar(
                "conferencia", atividade.ERRO,
                f"conferencia {canal}/{ficha['plataforma']}: "
                f"{len(ficha['fantasmas'])} no ledger sem video no canal, "
                f"{len(ficha['rascunhos'])} rascunho(s), "
                f"{len(ficha.get('orfaos_privados') or [])} privado(s) fora "
                f"do ledger em {ficha['janela_dias']} dia(s)", canal=canal)
        if ficha.get("deficit"):
            # ALARME PROPRIO PARA A GRADE FURADA. O builds ficou de 21 a 27/09
            # sem publicar e a conferencia dizia "limpo" toda noite, porque
            # ledger coerente e grade cumprida nao sao a mesma pergunta. Quem
            # nao publica tem de acender aqui, e nao no relatorio diario, onde
            # a linha "builds: 0/10" passou seis dias sem ser notada.
            de, ate = (ficha.get("janela_da_grade") or ["?", "?"])[:2]
            atividade.registrar(
                "conferencia", atividade.ERRO,
                f"grade {canal}/{ficha.get('plataforma')}: "
                f"{ficha.get('horarios_cumpridos', 0)} de "
                f"{ficha.get('slots_da_grade', 0)} horarios com video publico "
                f"confirmado no canal, de {str(de)[:16].replace('T', ' ')} a "
                f"{str(ate)[:16].replace('T', ' ')} ({ficha['deficit']} em "
                f"falta: {', '.join(ficha.get('horarios_em_falta') or [])}; "
                f"{ficha.get('linhas_no_dia_de_grade', 0)} linha(s) no ledger)",
                canal=canal)
    return fichas


def main(argv=None) -> int:
    """`python -m builds.publicar.conferencia --canal builds --dias 1`."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="conferencia",
        description="o ledger contra o que o canal realmente tem")
    parser.add_argument("--canal", default="", help="builds, historias, ou "
                                                    "vazio para os dois")
    parser.add_argument("--dias", type=int, default=DIAS_PADRAO)
    parser.add_argument(
        "--aceitar-rascunhos", dest="aceitar_rascunhos", action="store_true",
        help="grava os rascunhos DESTA rodada como conhecidos e aceitos (so "
             "com decisao de uma pessoa; a madrugada nunca faz isto)")
    args = parser.parse_args(argv)

    canais = (args.canal,) if args.canal else ("builds", "historias")
    fichas = conferir_tudo(canais, dias=args.dias)
    sujo = False
    for canal, ficha in fichas.items():
        if ficha.get("erro"):
            print(f"[{canal}] NAO DEU PARA CONFERIR: {ficha['erro']}")
            continue
        sujo = sujo or ficha.get("veredito") == "sujo"
        print(f"[{canal}] {len(ficha.get('rascunhos_aceitos') or [])} "
              f"rascunho(s) ja aceito(s), {len(ficha.get('orfaos') or [])} "
              f"orfao(s) de {ficha.get('no_canal_na_janela', 0)} video(s) "
              "na janela")
        for nome in ("fantasmas", "rascunhos", "orfaos_privados", "orfaos", "so_sd"):
            for item in (ficha.get(nome) or [])[:6]:
                print(f"   [{canal}] {nome[:-1]:10} "
                      f"{item.get('titulo') or item.get('youtube_id')}")
        for grupo in ficha.get("mesmo_video") or []:
            quando = ", ".join(str(l.get("quando"))[:16]
                               for l in grupo["linhas"])
            print(f"   [{canal}] mesmo video {grupo['youtube_id']} em "
                  f"{len(grupo['linhas'])} linhas do ledger: {quando}")
        if args.aceitar_rascunhos and ficha.get("rascunhos"):
            destino = aceitar_rascunhos(ficha)
            print(f"[{canal}] {len(ficha['rascunhos'])} rascunho(s) "
                  f"gravado(s) como aceito(s) em {destino}")
    return 1 if sujo else 0


__all__ = ["ACEITOS_MOTIVO", "DIAS_PADRAO", "aceitar_rascunhos",
           "aceitar", "arquivo_de_aceitos", "buscar_no_canal", "conferir",
           "conferir_tudo", "dia_de_grade_fechado", "main", "pasta",
           "rascunhos_aceitos",
           "salvar", "ultima"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
