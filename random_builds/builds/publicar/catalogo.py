# -*- coding: utf-8 -*-
"""Todos os vídeos publicáveis num lugar só, com o texto pronto para colar.

O atrito de publicar nunca foi o render: era ACHAR o arquivo. Os mp4 nascem
espalhados por três lugares diferentes (`generation_XXXXX/final_*.mp4`,
`generation_XXXXX/estreia/final_*.mp4`, `tournament_XXXXX/final_*.mp4`), com
o mesmo nome, e sem nada que diga de quem é aquele vídeo.

Este módulo é o índice: varre os três lugares, junta com os dados que a build
já gravou (personagem, arma, nota, adversário, campeão) e devolve, por vídeo,
o caminho, um título, uma descrição e as hashtags — os mesmos textos que a
exportação escreve num .txt ao lado do arquivo e que o upload manda para o
YouTube e o TikTok.

Leitura pura: nada aqui copia, envia ou apaga.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"
CONFIG = RAIZ / "config" / "publicacao.json"

BUILD, ESTREIA, TORNEIO, DUELO = "build", "estreia", "torneio", "duelo"
PERFIS = ("celular", "normal")

# Abaixo disto não é vídeo: render interrompido ou arquivo pela metade.
BYTES_MINIMOS = 100_000


def carregar_config() -> dict:
    try:
        with open(CONFIG, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _json(caminho: Path) -> dict:
    try:
        with open(caminho, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def _formatar(modelo: str, campos: dict) -> str:
    """Preenche {campos}; o que faltar some da frase em vez de quebrá-la.

    Título com dado ausente vira "None" ou estoura KeyError — os dois piores
    resultados possíveis num texto que vai para a plataforma.
    """
    def troca(achado: re.Match) -> str:
        valor = campos.get(achado.group(1))
        return "" if valor is None else str(valor)

    texto = re.sub(r"\{(\w+)\}", troca, modelo)
    # Sobra de pontuação de um campo que sumiu (" — ", " · " no fim, etc.)
    texto = re.sub(r"\s*[—·|-]\s*$", "", texto.strip())
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def slug(texto: str, limite: int = 40) -> str:
    normal = unicodedata.normalize("NFKD", str(texto or ""))
    ascii_ = normal.encode("ascii", "ignore").decode("ascii")
    limpo = re.sub(r"[^A-Za-z0-9]+", "-", ascii_).strip("-")
    return limpo[:limite].strip("-") or "video"


@dataclass
class Video:
    """Um mp4 publicável, com identidade e texto."""

    id: str
    origem: str
    perfil: str
    caminho: Path
    titulo: str
    descricao: str
    hashtags: list[str] = field(default_factory=list)
    fonte_id: str = ""          # generation_00057 / tournament_00006
    rotulo: str = ""            # o que aparece na lista do painel
    bytes: int = 0
    quando: float = 0.0
    variante: str = "A"          # gancho A (payoff) ou B (alternativo)
    pendencias: list[str] = field(default_factory=list)

    @property
    def pronto(self) -> bool:
        """Sem pendencia: tem payoff, tem luta e o mp4 e mais novo que eles."""
        return not self.pendencias

    @property
    def vertical(self) -> bool:
        """O 9:16 é o que vai para Shorts/TikTok; o 16:9 é o do YouTube."""
        return self.perfil == "celular"

    @property
    def nome_export(self) -> str:
        data = datetime.fromtimestamp(self.quando).strftime("%Y%m%d")
        sufixo = "" if self.variante == "A" else f"_gancho{self.variante}"
        return f"{data}_{self.fonte_id}_{self.perfil}{sufixo}_{slug(self.titulo)}.mp4"

    @property
    def descricao_completa(self) -> str:
        tags = " ".join(self.hashtags)
        return f"{self.descricao}\n\n{tags}".strip() if tags else self.descricao

    def to_dict(self) -> dict:
        return {"id": self.id, "origem": self.origem, "perfil": self.perfil,
                "caminho": str(self.caminho), "titulo": self.titulo,
                "descricao": self.descricao, "hashtags": list(self.hashtags),
                "fonte_id": self.fonte_id, "rotulo": self.rotulo,
                "bytes": self.bytes, "quando": self.quando,
                "variante": self.variante, "pendencias": list(self.pendencias)}


def pendencias_da_build(pasta: Path, perfil: str) -> list[str]:
    """O que falta para o video de build estar COMPLETO.

    27 de 64 builds saiam sem o clipe de payoff e iam para a plataforma com
    um nameplate no lugar do personagem. Publicar incompleto e decisao de
    gente, nao de ferramenta: a lista aparece no catalogo, o `publicar`
    recusa sem `--forcar`.
    """
    from ..identity import config as identity_config
    pasta = Path(pasta)
    final = pasta / f"final_{perfil}.mp4"
    lista: list[str] = []
    if identity_config.payoff_video_ativo():
        payoff = pasta / "character_weapon_video.mp4"
        falta_payoff = "sem payoff (clipe do Digen): `identity worker`"
    else:
        # Video do Digen desligado: o payoff e a imagem personagem+arma.
        payoff = pasta / "character_weapon_reference.png"
        falta_payoff = "sem imagem personagem+arma (PicassoIA): `identity worker`"
    imagem = pasta / "character_image.png"
    estreia = pasta / "estreia" / "fight.json"
    if not payoff.is_file():
        lista.append(falta_payoff)
    if not imagem.is_file():
        lista.append("sem imagem do personagem (PicassoIA)")
    if not estreia.is_file():
        lista.append("sem luta no fim (estreia nao gravada)")
    if final.is_file():
        mais_novo = max((c.stat().st_mtime for c in (payoff, imagem, estreia)
                         if c.is_file()), default=0.0)
        if mais_novo and final.stat().st_mtime + 5 < mais_novo:
            lista.append("mp4 mais velho que os clipes: "
                         "`generate-video --rerender <id> --refazer-edicao`")
    return lista


def _campos_build(pasta: Path) -> dict:
    personagem = _json(pasta / "character.json")
    build = _json(pasta / "build.json")
    return {
        "personagem": personagem.get("nome"),
        "classe": personagem.get("classe"),
        "arma": personagem.get("nome_arma"),
        "forca": personagem.get("forca"),
        "mana": personagem.get("mana"),
        "altura": personagem.get("tamanho"),
        "nota": build.get("final_score"),
        "veredito": build.get("verdict_label"),
        "compatibilidade": build.get("compatibility_score"),
        **_campos_origem(pasta),
    }


def _campos_origem(pasta: Path) -> dict:
    """A descricao publicada nao pode afirmar o que o video ja nao afirma.

    O texto dizia "Personagem 100% aleatorio" e "Tudo sorteado por roleta"
    fixo — falso quando o nome veio de um comentario, e mais ainda quando um
    atributo foi escolhido. `sorteio` e `escolhas` carregam a verdade; campo
    vazio some da frase (ver `_formatar`).
    """
    generation = _json(pasta / "generation.json")
    escolhidas = ((generation.get("escolhas") or {}).get("tela") or {})
    pedido = (generation.get("nome_pedido") or {}).get("nome")
    if escolhidas:
        lista = ", ".join(f"{chave} {valor}" for chave, valor in escolhidas.items())
        return {"sorteio": "quase todo aleatório",
                "escolhas": f"Escolhido a dedo: {lista}. O resto saiu na roleta."}
    if pedido:
        return {"sorteio": "aleatório", "escolhas": "Só o nome veio de vocês."}
    return {"sorteio": "100% aleatório", "escolhas": None}


def _campos_estreia(pasta: Path) -> dict:
    resumo = _json(pasta / "estreia.json")
    campos = _campos_build(pasta)
    vencedor = resumo.get("vencedor")
    personagem = resumo.get("personagem") or campos.get("personagem")
    # Numa serie o desfecho e o PLACAR: "venceu por KO" descreveria so o
    # round que fechou, e o titulo do video fala do confronto inteiro.
    placar = resumo.get("placar") or []
    placar_texto = " x ".join(str(v) for v in placar) if len(placar) == 2 else None
    if vencedor and personagem:
        desfecho = ("venceu" if vencedor == personagem else "perdeu")
        detalhe = placar_texto or resumo.get("ko_type")
        desfecho = f"{desfecho} por {detalhe}" if detalhe else desfecho
    else:
        desfecho = None
    campos.update({
        "personagem": personagem,
        "adversario": resumo.get("adversario"),
        "desfecho": desfecho,
        "placar": placar_texto,
        "melhor_de": resumo.get("melhor_de"),
        "duracao": (round(resumo["duracao"]) if resumo.get("duracao") else None),
    })
    return campos


def _campos_torneio(pasta: Path) -> dict:
    dados = _json(pasta / "tournament.json")
    campeao = dados.get("campeao") or dados.get("champion")
    participantes = dados.get("participantes") or dados.get("players") or []
    return {"campeao": campeao if isinstance(campeao, str) else None,
            "participantes": len(participantes) or None}


def _campos_duelo(pasta: Path) -> dict:
    """Onda 15B. O titulo do duelo NAO leva placar nem nota.

    O da estreia dizia "venceu por 2 x 0" e o do build "BUILD MEDIANA":
    um entregava o final antes do video, o outro anunciava que o video era
    mediano. Aqui o titulo e o confronto, e o desfecho fica no video.
    """
    dados = _json(pasta / "fight.json")
    luta = dados.get("luta") or {}
    return {
        "p1": luta.get("p1"),
        "p2": luta.get("p2"),
        "arena": luta.get("cenario"),
        "duracao": (round(luta["duracao"]) if luta.get("duracao") else None),
    }


def _videos_de(pasta: Path, origem: str, fonte_id: str, campos: dict,
               config: dict, rotulo: str) -> list[Video]:
    titulo = _formatar(config.get("titulos", {}).get(origem, "{personagem}"),
                       campos)
    descricao = _formatar(config.get("descricoes", {}).get(origem, ""), campos)
    hashtags = list(config.get("hashtags", {}).get(origem, []))
    saida = []
    for perfil in PERFIS:
        pendencias = pendencias_da_build(pasta, perfil) if origem == BUILD else []
        for variante, nome in (("A", f"final_{perfil}.mp4"),
                               ("B", f"final_{perfil}_ganchoB.mp4")):
            caminho = pasta / nome
            if not caminho.is_file() or caminho.stat().st_size < BYTES_MINIMOS:
                continue
            sufixo_id = "" if variante == "A" else f":{variante}"
            sufixo_rotulo = "" if variante == "A" else f" (gancho {variante})"
            saida.append(Video(
                id=f"{fonte_id}:{origem}:{perfil}{sufixo_id}", origem=origem,
                perfil=perfil, caminho=caminho, titulo=titulo or fonte_id,
                descricao=descricao, hashtags=hashtags, fonte_id=fonte_id,
                rotulo=rotulo + sufixo_rotulo, bytes=caminho.stat().st_size,
                quando=caminho.stat().st_mtime, variante=variante,
                pendencias=list(pendencias)))
    return saida


def _pasta_textos(config: dict | None = None) -> Path:
    return pasta_export(config) / "_textos"


def salvar_texto(video_id: str, titulo: str, descricao: str,
                 hashtags: list[str] | None = None,
                 config: dict | None = None) -> Path:
    """Guarda o texto EDITADO daquele vídeo, que passa a valer sobre o gerado.

    O texto automático é um bom ponto de partida, não um decreto: quando você
    reescreve o título na hora de publicar, essa versão é a que vale dali em
    diante — inclusive num envio futuro para a outra plataforma.
    """
    destino = _pasta_textos(config)
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"{slug(video_id, 80)}.json"
    dados = {"video_id": video_id, "titulo": titulo, "descricao": descricao}
    if hashtags is not None:
        dados["hashtags"] = list(hashtags)
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return arquivo


def _aplicar_textos(videos: list[Video], config: dict | None = None) -> None:
    pasta = _pasta_textos(config)
    if not pasta.is_dir():
        return
    editados = {}
    for arquivo in pasta.glob("*.json"):
        dados = _json(arquivo)
        if dados.get("video_id"):
            editados[dados["video_id"]] = dados
    for video in videos:
        dados = editados.get(video.id)
        if not dados:
            continue
        video.titulo = dados.get("titulo") or video.titulo
        video.descricao = dados.get("descricao", video.descricao)
        if dados.get("hashtags") is not None:
            video.hashtags = list(dados["hashtags"])


def listar(config: dict | None = None) -> list[Video]:
    """Todos os vídeos publicáveis, do mais novo para o mais velho."""
    config = carregar_config() if config is None else config
    videos: list[Video] = []
    for pasta in sorted(OUTPUTS.glob("generation_*")):
        campos = _campos_build(pasta)
        nome = campos.get("personagem") or pasta.name
        videos += _videos_de(pasta, BUILD, pasta.name, campos, config,
                             f"{nome} — build")
        estreia = pasta / "estreia"
        if estreia.is_dir():
            campos_estreia = _campos_estreia(pasta)
            videos += _videos_de(estreia, ESTREIA, pasta.name, campos_estreia,
                                 config, f"{nome} — estreia")
    for pasta in sorted(OUTPUTS.glob("duelo_*")):
        campos = _campos_duelo(pasta)
        videos += _videos_de(pasta, DUELO, pasta.name, campos, config,
                             f"{campos.get('p1') or pasta.name} x "
                             f"{campos.get('p2') or '?'}")
    for pasta in sorted(OUTPUTS.glob("tournament_*")):
        campos = _campos_torneio(pasta)
        videos += _videos_de(pasta, TORNEIO, pasta.name, campos, config,
                             f"Torneio {pasta.name.split('_')[-1]}")
    _aplicar_textos(videos, config)
    videos.sort(key=lambda v: v.quando, reverse=True)
    return videos


def por_id(video_id: str, config: dict | None = None) -> Video | None:
    return next((v for v in listar(config) if v.id == video_id), None)


# ------------------------------------------------------------------ exportar
def pasta_export(config: dict | None = None) -> Path:
    config = carregar_config() if config is None else config
    bruto = config.get("pasta_export") or "outputs/_publicar"
    caminho = Path(bruto)
    return caminho if caminho.is_absolute() else RAIZ / caminho


def exportar(video: Video, destino: Path | None = None,
             config: dict | None = None) -> Path:
    """Copia o mp4 com nome legível e grava o texto ao lado.

    É o atalho que substitui "entrar na pasta, achar qual é, renomear": tudo
    o que vai para a plataforma fica num lugar só, com o nome dizendo de quem
    é o vídeo e um .txt com título, descrição e hashtags prontos para colar.
    """
    import shutil

    destino = pasta_export(config) if destino is None else Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    alvo = destino / video.nome_export
    shutil.copy2(video.caminho, alvo)
    alvo.with_suffix(".txt").write_text(
        f"{video.titulo}\n\n{video.descricao_completa}\n", encoding="utf-8")
    return alvo


__all__ = ["BUILD", "ESTREIA", "TORNEIO", "Video", "carregar_config",
           "exportar", "listar", "pasta_export", "pendencias_da_build", "por_id",
           "salvar_texto", "slug"]
