# -*- coding: utf-8 -*-
"""Publicar a serie inteira: vistoria, sobe cada parte, AGENDA a sequencia.

E o "um clique" do canal. O que ele faz, nesta ordem e sem pular etapa:

  1. VISTORIA cada parte (`qualidade.py`). Erro impede o upload — publicar
     um video mudo ou sem imagem custa mais caro do que nao publicar.
  2. Sobe as partes NA ORDEM, na conta do canal `historias` (o registro de
     contas decide qual e).
  3. AGENDA: a parte 1 sai primeiro, e cada parte seguinte num intervalo
     (por padrao 24 h). Soltar oito partes no mesmo minuto mata a serie —
     ninguem assiste oito videos seguidos, e o algoritmo le como spam.
  4. REGISTRA o que subiu (`publicados.jsonl`), para nao subir duas vezes e
     para a metrica saber a que ligar.

Nada aqui torna nada publico sozinho: o padrao e privado-com-agendamento, e
o horario e a unica coisa que decide quando o video aparece.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from builds.publicar import tiktok as _rb_publicar_tiktok
from builds.publicar import youtube as _rb_publicar_youtube
import builds.atividade as _rb_atividade

from . import catalogo, qualidade

RAIZ = Path(__file__).resolve().parents[2]
REGISTRO = RAIZ / "outputs" / "_publicar" / "publicados.jsonl"

INTERVALO_PADRAO_H = 24.0
# O YouTube recusa publishAt no passado; a primeira parte precisa de folga
# para o upload terminar antes do horario marcado.
FOLGA_MINIMA_MIN = 15


class NaoPublicou(RuntimeError):
    """Motivo humano: o que reprovou, e o que fazer."""


def publicados() -> list:
    if not REGISTRO.is_file():
        return []
    saida = []
    with open(REGISTRO, encoding="utf-8") as fh:
        for linha in fh:
            linha = linha.strip()
            if linha:
                try:
                    saida.append(json.loads(linha))
                except ValueError:
                    continue
    return saida


def ja_publicado(video_id: str, plataforma: str = "youtube") -> dict | None:
    for linha in reversed(publicados()):
        if (linha.get("video_id") == video_id and linha.get("url")
                and linha.get("plataforma", "youtube") == plataforma):
            return linha
    return None


def registrar(video, url: str, plataforma: str, quando_publica: str | None,
              extra: dict | None = None) -> dict:
    linha = {
        "quando": datetime.now().isoformat(timespec="seconds"),
        "plataforma": plataforma, "url": url,
        "video_id": video.id, "fonte_id": video.fonte_id,
        "parte": video.parte, "partes": video.partes,
        "titulo": video.titulo, "agendado_para": quando_publica,
    }
    linha.update(extra or {})
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRO, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return linha


def horarios(quantidade: int, *, comecar_em: datetime | None = None,
             intervalo_h: float = INTERVALO_PADRAO_H) -> list:
    """Um horario por parte, em UTC ISO (o que a API do YouTube espera)."""
    inicio = comecar_em or (datetime.now(timezone.utc)
                            + timedelta(minutes=FOLGA_MINIMA_MIN))
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    minimo = datetime.now(timezone.utc) + timedelta(minutes=FOLGA_MINIMA_MIN)
    if inicio < minimo:
        inicio = minimo
    return [(inicio + timedelta(hours=intervalo_h * i))
            .astimezone(timezone.utc).isoformat(timespec="seconds")
            .replace("+00:00", "Z")
            for i in range(quantidade)]


def videos_da_serie(historia_id: str, perfil: str = "celular") -> list:
    return [v for v in catalogo.listar()
            if v.fonte_id == historia_id and v.perfil == perfil]


def _atividade():
    try:
        return _rb_atividade
    except Exception:
        class _Muda:
            @staticmethod
            def registrar(*a, **k):
                pass
        return _Muda


def publicar(historia_id: str, *, perfil: str = "celular",
             plataformas=("youtube",), agendar: bool = True,
             intervalo_h: float = INTERVALO_PADRAO_H,
             comecar_em: datetime | None = None,
             visibilidade: str | None = None, forcar: bool = False,
             so_vistoriar: bool = False, log=print) -> dict:
    """Vistoria e sobe a serie inteira, em todas as plataformas pedidas.

    YouTube: todas as partes, AGENDADAS (privado + publishAt) — o horario e o
    que decide quando cada uma aparece. TikTok: POSTA de verdade (decisao do
    Adrian, 31/08: um clique sem parada), mas so `tiktok_partes_por_clique`
    por execucao — o TikTok nao agenda por aqui, e despejar oito partes no
    mesmo minuto mata a serie; cada clique posta a proxima parte pendente.
    """
    atividade = _atividade()
    videos = videos_da_serie(historia_id, perfil)
    if not videos:
        raise NaoPublicou(
            f"{historia_id} nao tem nenhum video no perfil {perfil}. "
            f"Rode: python main.py video {historia_id}")

    laudo = qualidade.vistoriar_serie(historia_id, videos)
    for aviso in laudo["avisos"]:
        log(f"  ! {aviso}")
    for erro in laudo["erros"]:
        log(f"  x {erro}")
    if so_vistoriar:
        return {"laudo": laudo, "enviados": [], "pulados": []}
    if laudo["erros"] and not forcar:
        atividade.registrar("publicacao", "erro",
                            f"{historia_id}: vistoria reprovou "
                            f"({laudo['erros'][0][:120]})", "historias")
        raise NaoPublicou(
            f"{len(laudo['erros'])} problema(s) impedem a publicacao "
            "(acima). Corrija, ou repita com --forcar se souber o que esta "
            "fazendo.")

    # Perguntar a cota ANTES de comecar: descobrir o teto no meio da serie
    # custa a vistoria inteira e deixa metade das partes no ar. A sonda abre
    # uma sessao de upload e nao envia byte nenhum — nao cria video.
    if "youtube" in plataformas and not forcar:
        yt = _rb_publicar_youtube
        # A cota da API so manda quando a API publica. No modo navegador ela
        # e irrelevante — e bloquear por ela seria travar o caminho que
        # justamente existe para contornar o teto.
        pode, motivo = (True, "") if yt.modo() != "api" else \
            yt.cota_disponivel("historias")
        if not pode:
            atividade.registrar("publicacao", "erro",
                                f"{historia_id}: sem cota no YouTube",
                                "historias")
            raise NaoPublicou(motivo)

    config = catalogo.carregar_config().get("um_clique") or {}
    teto_tiktok = int(config.get("tiktok_partes_por_clique", 1))
    atividade.registrar("publicacao", "inicio",
                        f"{historia_id}: {len(videos)} parte(s) -> "
                        + "+".join(plataformas), "historias")
    enviados, pulados = [], []
    erros_envio = []
    try:
        for plataforma in plataformas:
            marcados = (horarios(len(videos), comecar_em=comecar_em,
                                 intervalo_h=intervalo_h)
                        if agendar and plataforma == "youtube"
                        else [None] * len(videos))
            postados_agora = 0
            for video, quando in zip(videos, marcados):
                anterior = ja_publicado(video.id, plataforma)
                if anterior and not forcar:
                    log(f"[publicar] {plataforma} parte {video.parte}: ja subiu "
                        f"em {anterior['quando'][:10]}")
                    pulados.append({"parte": video.parte, "plataforma": plataforma,
                                    "url": anterior["url"]})
                    continue
                if plataforma == "tiktok" and postados_agora >= teto_tiktok:
                    log(f"[publicar] tiktok: teto de {teto_tiktok} por clique "
                        f"atingido; a parte {video.parte} fica para o proximo.")
                    break
                rotulo = (f"parte {video.parte}/{video.partes}"
                          if video.partes > 1 else "video")
                log(f"[publicar] {plataforma} {rotulo}: {video.titulo}")
                if quando:
                    log(f"[publicar]   agendado para {quando}")
                try:
                    if plataforma == "youtube":
                        url = catalogo.publicar_youtube(
                            video, visibilidade, agendar_para=quando, log=log)
                        # (o corte para Shorts acontece dentro de
                        # `publicar_youtube`: uma parte comprida vira duas)
                    elif plataforma == "tiktok":
                        url = catalogo.publicar_tiktok(video, postar=True, log=log)
                        # O TikTok nao devolve URL: devolve um ESTADO. Sem
                        # esta checagem, "cliquei mas nao confirmou" entrava
                        # no registro como publicacao boa, e a parte nunca
                        # mais seria tentada.
                        if not _rb_publicar_tiktok.confirmado(url):
                            erros_envio.append(
                                f"tiktok parte {video.parte}: {url}")
                            log(f"[publicar]   NAO confirmado: {url}")
                            continue
                    else:
                        raise NaoPublicou(f"plataforma desconhecida: {plataforma}")
                except NaoPublicou:
                    raise
                except Exception as exc:
                    if type(exc).__name__ == "CotaEsgotada":
                        # Insistir aqui so gera N erros iguais: TODAS as
                        # partes seguintes cairiam no mesmo teto.
                        erros_envio.append(f"youtube: {exc}")
                        log(f"[publicar] PARANDO a serie: {exc}")
                        break
                    erros_envio.append(f"{plataforma} parte {video.parte}: {exc}")
                    log(f"[publicar]   FALHOU: {exc}")
                    continue
                registrar(video, url, plataforma, quando)
                enviados.append({"parte": video.parte, "plataforma": plataforma,
                                 "url": url, "quando": quando})
                postados_agora += 1
                log(f"[publicar]   {url}")
    finally:
        atividade.registrar(
            "publicacao", "erro" if erros_envio else "ok",
            f"{historia_id}: {len(enviados)} enviada(s), "
            f"{len(pulados)} ja no ar"
            + (f"; 1o erro: {erros_envio[0][:100]}" if erros_envio else ""),
            "historias")

    log(f"[publicar] {len(enviados)} enviada(s), {len(pulados)} ja estavam no ar"
        + (f", {len(erros_envio)} falha(s)" if erros_envio else "") + ".")
    return {"laudo": laudo, "enviados": enviados, "pulados": pulados,
            "erros": erros_envio}
