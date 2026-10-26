# -*- coding: utf-8 -*-
"""Os numeros da SERIE "Como eu criei um Blue Lock" (canal `bluelock`), 26/10/2026.

A serie estreou em 26/10 (YouTube `zombie_survivores` = canal Egoistsoccer,
TikTok `zombie_surviv0rs`) e, ate a manha desse dia, ninguem lia um numero
dela: a coleta so conhecia `builds` e `historias`. Desde 26/10 o canal
`bluelock` e uma PARTE da coleta (`metricas.CANAIS_DA_COLETA`, as partes
`bluelock` e `bluelock_tiktok` da marca do dia) e este modulo faz o que a
serie precisa a mais:

- guarda o HISTORICO de cada leitura (`_serie_bluelock/_leituras.jsonl`):
  o arquivo por video e sobrescrito a cada coleta, e "views 24 h" so existe
  se alguem escreveu o numero perto das 24 h;
- monta UMA LINHA POR EPISODIO para o relatorio diario do Telegram.

As tres perguntas da lei desta parte:

- ZERO: sem episodio no ledger a linha diz "nenhum episodio publicado" (nao
  "tudo bem"); episodio sem medida diz "sem medida"; "views 24 h" sem leitura
  perto das 24 h diz "ainda nao" — NUNCA 0.
- DENOMINADOR: um episodio e um `episodio` do ledger, com as duas plataformas
  lado a lado e nunca somadas; a idade de cada numero vem da hora em que ele
  foi lido (`views_medidas_em`), nao da hora em que o arquivo foi escrito.
- EXCECAO: quem chama (relatorio, coleta) recebe o erro como texto; nada aqui
  engole excecao em silencio.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import metricas

CANAL = "bluelock"
# "views 24 h" = a leitura mais perto de 24 h depois do post, dentro desta
# folga. Fora dela e "ainda nao" — sem interpolar (a mesma regra da medida da
# semana na mesma idade).
HORAS_DA_MEDIDA = 24.0
FOLGA_DA_MEDIDA_H = 5.0
# Numero com mais de tanto tempo vem com aviso.
VELHO_H = 30.0
NOME_DO_ARQUIVO = "_leituras.jsonl"


def pasta_da_serie() -> Path:
    return metricas.registro_do_canal(CANAL).parent


def arquivo_das_leituras() -> Path:
    return pasta_da_serie() / NOME_DO_ARQUIVO


# --------------------------------------------------------------- historico
def registrar_leitura(plataforma: str, dados: list, agora: datetime | None = None
                      ) -> Path | None:
    """Acrescenta UMA linha ao historico: o que cada video tinha agora.

    So grava o que veio (campo ausente = nao medido, nunca 0). Lista vazia nao
    grava nada (ausencia de video e dito por quem chama, nao com linha vazia).
    """
    agora = agora or datetime.now()
    campos = ("views", "likes", "comentarios", "compartilhamentos", "salvos",
              "views_analytics", "media_percentual", "media_segundos",
              "engaged_views", "ficou_para_ver", "inscritos_ganhos",
              "inscritos_perdidos", "seguidores_ganhos", "taxa_de_conclusao")
    por_video = {}
    for d in dados or ():
        if not isinstance(d, dict):
            continue
        vid = d.get("youtube_id") if plataforma == "youtube" else d.get("tiktok_id")
        if not vid:
            continue
        item = {c: d[c] for c in campos if isinstance(d.get(c), (int, float))}
        item["medido_em"] = (d.get("views_medidas_em") or d.get("atualizado")
                             or agora.isoformat(timespec="seconds"))
        por_video[str(vid)] = item
    if not por_video:
        return None
    caminho = arquivo_das_leituras()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    linha = {"quando": agora.isoformat(timespec="seconds"),
             "plataforma": plataforma, "videos": por_video}
    with open(caminho, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except OSError:
            pass
    return caminho


def carregar_leituras() -> list:
    """Todas as leituras, na ordem do arquivo. Linha ilegivel e pulada."""
    saida = []
    try:
        with open(arquivo_das_leituras(), encoding="utf-8") as fh:
            for linha in fh:
                try:
                    dado = json.loads(linha)
                except ValueError:
                    continue
                if isinstance(dado, dict):
                    saida.append(dado)
    except OSError:
        pass
    return saida


# ------------------------------------------------------------ o que e hora
def _instante(texto) -> datetime | None:
    try:
        return datetime.fromisoformat(str(texto)[:19])
    except ValueError:
        return None


def _publicado_local(linha: dict, dado: dict | None) -> datetime | None:
    """Quando o episodio foi ao ar, no relogio LOCAL. O `publicado_em` do
    YouTube vem em UTC (`...Z`) e e convertido; o `quando` do ledger ja e
    local."""
    texto = (dado or {}).get("publicado_em")
    if texto and str(texto).endswith("Z"):
        try:
            utc = datetime.fromisoformat(str(texto)[:19]).replace(tzinfo=timezone.utc)
            return utc.astimezone().replace(tzinfo=None)
        except ValueError:
            pass
    return _instante(linha.get("quando"))


def views_na_idade(leituras: list, plataforma: str, video_id: str,
                   publicado: datetime | None, horas: float = HORAS_DA_MEDIDA,
                   folga: float = FOLGA_DA_MEDIDA_H) -> tuple | None:
    """`(views, idade_h)` da leitura mais perto de `horas` depois do post,
    dentro da folga. `None` = nao ha leitura la — e e "ainda nao", nunca 0."""
    if publicado is None:
        return None
    melhor = None
    for leitura in leituras:
        if leitura.get("plataforma") != plataforma:
            continue
        item = (leitura.get("videos") or {}).get(str(video_id))
        if not isinstance(item, dict) or not isinstance(item.get("views"), (int, float)):
            continue
        lida = _instante(item.get("medido_em") or leitura.get("quando"))
        if lida is None:
            continue
        idade = (lida - publicado).total_seconds() / 3600.0
        distancia = abs(idade - horas)
        if distancia <= folga and (melhor is None or distancia < melhor[0]):
            melhor = (distancia, int(item["views"]), idade)
    return None if melhor is None else (melhor[1], round(melhor[2], 1))


# ------------------------------------------------------------- episodios
def episodios() -> list:
    """Os episodios do ledger, um por numero, com as duas plataformas.

    Cada item: `{episodio, titulo, youtube: linha|None, tiktok: linha|None}`.
    So linha PUBLICADA (`metricas.publicado`); rascunho nao e episodio no ar.
    """
    por_ep: dict = {}
    for linha in metricas.publicados(CANAL):
        if not isinstance(linha, dict) or not metricas.publicado(linha):
            continue
        numero = linha.get("episodio")
        if numero is None:
            numero = linha.get("video_id")
        item = por_ep.setdefault(numero, {"episodio": numero,
                                          "titulo": linha.get("titulo"),
                                          "youtube": None, "tiktok": None})
        plataforma = str(linha.get("plataforma") or "youtube")
        if plataforma in ("youtube", "tiktok"):
            item[plataforma] = linha
    return sorted(por_ep.values(), key=lambda e: str(e["episodio"]).zfill(6))


def _salvos_por_id(plataforma: str) -> dict:
    if plataforma == "youtube":
        dados, chave = metricas.carregar_salvas(CANAL), "youtube_id"
    else:
        from . import tiktok_metricas
        dados, chave = tiktok_metricas.carregar_salvas(CANAL), "tiktok_id"
    return {str(d.get(chave)): d for d in dados if d.get(chave)}


def _casar_tiktok(linha: dict, salvos: dict) -> dict | None:
    """O arquivo do TikTok daquele envio. O ledger do TikTok nao guarda o id
    do post; o arquivo carrega o `video_id`/`fonte_id` da linha que ele casou."""
    for d in salvos.values():
        if (d.get("video_id") == linha.get("video_id")
                and d.get("quando") == linha.get("quando")):
            return d
    return None


def _n(valor) -> str:
    if not isinstance(valor, (int, float)):
        return "?"
    return f"{int(valor):,}".replace(",", ".")


def _idade_do_numero(dado: dict, agora: datetime) -> float | None:
    medido = _instante(dado.get("views_medidas_em") or dado.get("atualizado"))
    return None if medido is None else (agora - medido).total_seconds() / 3600.0


def linha_youtube(ep: dict, salvos: dict, leituras: list, agora: datetime) -> str:
    linha = ep.get("youtube")
    if not linha:
        return "YouTube: não saiu"
    vid = linha.get("youtube_id")
    if not vid:
        return "YouTube: SEM youtube_id no ledger (não dá para medir)"
    dado = salvos.get(str(vid))
    if not dado:
        return f"YouTube {vid}: sem medida (a coleta ainda não leu)"
    publicado = _publicado_local(linha, dado)
    partes = [f"{_n(dado.get('views'))} views"]
    medida = views_na_idade(leituras, "youtube", vid, publicado)
    partes.append(f"24 h: {_n(medida[0])} (lida aos {medida[1]:.1f} h)".replace(".", ",", 1)
                  if medida else "24 h: ainda não")
    if isinstance(dado.get("media_percentual"), (int, float)):
        partes.append(f"assistido {dado['media_percentual']:.0f}%")
    else:
        # A Analytics do YouTube atrasa 2-3 dias para um video novo (medido
        # 26/10: ultimo dia com dado era 22/10, e o Studio diz "ate dois dias").
        partes.append("assistido: ainda sem dado (a Analytics atrasa 2–3 dias)")
    if isinstance(dado.get("ficou_para_ver"), (int, float)):
        partes.append(f"ficou p/ ver {100 * dado['ficou_para_ver']:.0f}%")
    if isinstance(dado.get("inscritos_ganhos"), (int, float)):
        partes.append(f"+{int(dado['inscritos_ganhos'])} inscr.")
    partes.append(f"{_n(dado.get('likes'))} curt. · {_n(dado.get('comentarios'))} coment."
                  + (f" · {_n(dado['compartilhamentos'])} comp."
                     if isinstance(dado.get("compartilhamentos"), (int, float)) else ""))
    idade = _idade_do_numero(dado, agora)
    aviso = f" ⚠ número de há {idade:.0f} h" if idade is not None and idade > VELHO_H else ""
    return "YouTube: " + " · ".join(partes) + aviso


def linha_tiktok(ep: dict, salvos: dict, leituras: list, agora: datetime) -> str:
    linha = ep.get("tiktok")
    if not linha:
        return "TikTok: não saiu"
    dado = _casar_tiktok(linha, salvos)
    if not dado:
        return "TikTok: sem medida (o Studio ainda não listou o post)"
    publicado = _publicado_local(linha, None)
    partes = [f"{_n(dado.get('views'))} views"]
    medida = views_na_idade(leituras, "tiktok", dado.get("tiktok_id"), publicado)
    partes.append(f"24 h: {_n(medida[0])} (lida aos {medida[1]:.1f} h)".replace(".", ",", 1)
                  if medida else "24 h: ainda não")
    if isinstance(dado.get("media_percentual"), (int, float)):
        partes.append(f"assistido {dado['media_percentual']:.0f}%")
    else:
        partes.append("assistido: sem dado")
    partes.append(f"{_n(dado.get('likes'))} curt. · {_n(dado.get('comentarios'))} coment. · "
                  f"{_n(dado.get('compartilhamentos'))} comp.")
    idade = _idade_do_numero(dado, agora)
    aviso = f" ⚠ número de há {idade:.0f} h" if idade is not None and idade > VELHO_H else ""
    return "TikTok: " + " · ".join(partes) + aviso


def atualizar_agora(agora: datetime | None = None, *, log=print,
                    intervalo_min: float = 30.0) -> str:
    """Le o YouTube da serie AGORA (so API: Data + Analytics, mais os
    comentarios) para o relatorio das 21h nao falar de numero de 07h. O TikTok
    nao entra: abre o Chrome do Studio e fica para a coleta do dia.

    Devolve "" se atualizou (ou se uma leitura de menos de `intervalo_min`
    minutos ja vale), ou o MOTIVO de nao ter atualizado — que o relatorio
    imprime. Nunca levanta."""
    agora = agora or datetime.now()
    try:
        ultima = max((_instante(l.get("quando")) for l in carregar_leituras()
                      if l.get("plataforma") == "youtube" and _instante(l.get("quando"))),
                     default=None)
        if ultima and 0 <= (agora - ultima).total_seconds() < intervalo_min * 60:
            return ""
        metricas.atualizar(log=log, canal=CANAL)
        return ""
    except Exception as exc:                                   # noqa: BLE001
        return f"{type(exc).__name__}: {str(exc)[:160]}"


def linhas_do_relatorio(agora: datetime | None = None, *,
                        atualizar: bool = False) -> list:
    """O bloco da serie para o relatorio diario: titulo + 1 linha por plataforma
    de cada episodio. Nunca levanta (o relatorio nao pode cair por isto).

    `atualizar=True` le o YouTube antes (so o relatorio de verdade; teste nao
    vai a rede). Se a leitura falhar, o bloco diz isso e usa o numero do disco
    com a hora dele."""
    agora = agora or datetime.now()
    recado = ""
    if atualizar:
        motivo = atualizar_agora(agora)
        if motivo:
            recado = f"  ⚠ não atualizei o YouTube agora ({motivo}); números do disco."
    try:
        eps = episodios()
    except Exception as exc:                                   # noqa: BLE001
        return ["📺 *Série Blue Lock*",
                f"  ⚠ não consegui ler o ledger da série: {type(exc).__name__}: {exc}"]
    if not eps:
        return ["📺 *Série Blue Lock*",
                "  nenhum episódio publicado no ledger (isto NÃO é nota boa)."]
    try:
        leituras = carregar_leituras()
        yt, tt = _salvos_por_id("youtube"), _salvos_por_id("tiktok")
    except Exception as exc:                                   # noqa: BLE001
        return ["📺 *Série Blue Lock*",
                f"  ⚠ não consegui ler os números: {type(exc).__name__}: {exc}"]
    saida = ["📺 *Série Blue Lock*"] + ([recado] if recado else [])
    for ep in eps:
        saida.append(f"  *Ep. {ep['episodio']}*")
        saida.append("   " + linha_youtube(ep, yt, leituras, agora))
        saida.append("   " + linha_tiktok(ep, tt, leituras, agora))
    return saida
