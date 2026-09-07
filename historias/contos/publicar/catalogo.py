# -*- coding: utf-8 -*-
"""Os mp4 prontos, com titulo e descricao ja escritos.

Mesma ideia do outro projeto: o atrito de publicar nunca foi o render, era
ACHAR o arquivo e escrever o texto. Aqui o titulo ja e o titulo da historia
(que o LLM escreveu para prender), a descricao vem de `config/publicacao.json`
e o upload reusa o YouTube do random_builds — mesmo OAuth, mesmo escopo.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from builds.publicar import cortes as _rb_publicar_cortes
from builds.publicar import tiktok as _rb_publicar_tiktok
from builds.publicar import youtube as _rb_publicar_youtube

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"
CONFIG = RAIZ / "config" / "publicacao.json"
BYTES_MINIMOS = 100_000


def carregar_config() -> dict:
    try:
        with open(CONFIG, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def slug(texto: str, limite: int = 48) -> str:
    normal = unicodedata.normalize("NFKD", str(texto or ""))
    ascii_ = normal.encode("ascii", "ignore").decode("ascii")
    limpo = re.sub(r"[^A-Za-z0-9]+", "-", ascii_).strip("-")
    return limpo[:limite].strip("-") or "historia"


@dataclass
class Video:
    id: str
    perfil: str
    caminho: Path
    titulo: str
    descricao: str
    parte: int = 1
    partes: int = 1
    hashtags: list = field(default_factory=list)
    fonte_id: str = ""
    origem: str = "historia"
    variante: str = "A"
    bytes: int = 0
    quando: float = 0.0

    @property
    def vertical(self) -> bool:
        return self.perfil == "celular"

    @property
    def nome_export(self) -> str:
        """O nome carrega a ORDEM: numa serie, o arquivo tem que ser obvio
        na hora de publicar a parte certa no dia certo."""
        data = datetime.fromtimestamp(self.quando).strftime("%Y%m%d")
        ordem = f"_p{self.parte:02d}" if self.partes > 1 else ""
        return f"{data}_{self.fonte_id}{ordem}_{self.perfil}_{slug(self.titulo)}.mp4"

    @property
    def descricao_completa(self) -> str:
        tags = " ".join(self.hashtags)
        return f"{self.descricao}\n\n{tags}".strip() if tags else self.descricao


def _formatar(modelo: str, campos: dict) -> str:
    def troca(achado):
        valor = campos.get(achado.group(1))
        return "" if valor is None else str(valor)
    texto = re.sub(r"\{(\w+)\}", troca, modelo or "")
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def listar(config: dict | None = None) -> list:
    config = carregar_config() if config is None else config
    videos = []
    if not OUTPUTS.is_dir():
        return videos
    for pasta in sorted(OUTPUTS.glob("historia_*"), reverse=True):
        roteiro = pasta / "roteiro.json"
        if not roteiro.is_file():
            continue
        try:
            with open(roteiro, encoding="utf-8-sig") as fh:
                dados = json.load(fh)
        except (OSError, ValueError):
            continue
        # Historia de TESTE nao e conteudo. A `historia_00002` tem
        # `provedor: "fake"` e imagens que sao cartoes roxos escritos "P1 / 1",
        # e mesmo assim o status dizia "pronta: 3 video(s) para publicar" e uma
        # parte dela ja tinha sido exportada. O catalogo e a porta do upload:
        # ela para aqui.
        if str(dados.get("provedor") or "").lower() == "fake":
            continue
        from ..roteiro import roteiro as R
        dados = R.normalizar(dados)
        total_partes = len(dados["partes"])
        for arquivo in sorted(pasta.glob("final_*.mp4")):
            if arquivo.stat().st_size < BYTES_MINIMOS:
                continue
            # `..._corte01.mp4` e PEDACO de um video, criado na hora de
            # publicar quando a parte passa do limite do Shorts. Ele nao e um
            # video da historia: se entrasse aqui, apareceria na lista como
            # se fosse uma parte nova e poderia ser publicado duas vezes.
            if re.search(r"_corte\d+$", arquivo.stem):
                continue
            # `final_celular_p03.mp4` -> perfil celular, parte 3.
            resto = arquivo.stem[len("final_"):]
            achado = re.search(r"_p(\d+)$", resto)
            parte = int(achado.group(1)) if achado else 1
            perfil = resto[:achado.start()] if achado else resto
            campos = {"titulo": R.titulo_da_parte(dados, parte),
                      "serie": dados.get("titulo", ""),
                      "parte": parte, "partes": total_partes,
                      "cta": dados.get("cta", ""),
                      "cenas": len(R.parte_de(dados, parte)["cenas"])
                      if any(p["n"] == parte for p in dados["partes"]) else 0}
            chave = "parte" if total_partes > 1 else "historia"
            titulo = _formatar(
                config.get("titulos", {}).get(chave)
                or config.get("titulos", {}).get("historia", "{titulo}"),
                campos) or pasta.name
            descricao = _formatar(
                config.get("descricoes", {}).get(chave)
                or config.get("descricoes", {}).get("historia", ""), campos)
            sufixo = f":p{parte:02d}" if total_partes > 1 else ""
            videos.append(Video(
                id=f"{pasta.name}:{perfil}{sufixo}", perfil=perfil,
                parte=parte, partes=total_partes, caminho=arquivo,
                titulo=titulo, descricao=descricao,
                hashtags=list(config.get("hashtags", {}).get("historia", [])),
                fonte_id=pasta.name, bytes=arquivo.stat().st_size,
                quando=arquivo.stat().st_mtime))
    # Mais nova primeiro, mas as partes de uma serie SEMPRE em ordem: e a
    # ordem em que elas tem que ir ao ar.
    videos.sort(key=lambda v: (-v.quando if v.partes == 1 else 0,
                               v.fonte_id, v.parte, v.perfil))
    videos.sort(key=lambda v: v.fonte_id, reverse=True)
    return videos


def resumo() -> list:
    """A lista pronta para outro processo ler (o painel, por JSON).

    Existe porque o painel nao pode IMPORTAR este projeto: os dois tem um
    pacote chamado `src`, e um sobrescreveria o outro. Entao ele roda um
    python aqui dentro e le a saida.
    """
    return [{"id": v.id, "titulo": v.titulo, "perfil": v.perfil,
             "parte": v.parte, "partes": v.partes, "fonte_id": v.fonte_id,
             "caminho": str(v.caminho), "bytes": v.bytes, "quando": v.quando,
             "descricao": v.descricao_completa, "origem": "historia"}
            for v in listar()]


def pasta_export(config: dict | None = None) -> Path:
    config = carregar_config() if config is None else config
    bruto = config.get("pasta_export") or "outputs/_publicar"
    caminho = Path(bruto)
    return caminho if caminho.is_absolute() else RAIZ / caminho


def exportar(video: Video, destino: Path | None = None) -> Path:
    import shutil
    destino = pasta_export() if destino is None else Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    alvo = destino / video.nome_export
    shutil.copy2(video.caminho, alvo)
    alvo.with_suffix(".txt").write_text(
        f"{video.titulo}\n\n{video.descricao_completa}\n", encoding="utf-8")
    return alvo


def publicar_youtube(video: Video, visibilidade: str | None = None, *,
                     agendar_para: str | None = None, log=print) -> str:
    """Sobe a parte no canal `historias` — cortada, se passar do Shorts.

    O corte mora AQUI, e nao em quem chama, porque todo caminho de publicacao
    das historias passa por esta funcao: a serie inteira, a parte avulsa e o
    botao do painel. Uma parte de 206 s vira dois Shorts de ~100 s cortados
    na troca de cena, e o retorno junta as URLs.

    Agendamento: quando a parte vira dois pedacos, os dois recebem o MESMO
    horario. Espalhar os pedacos ao longo de dias quebraria a leitura — eles
    sao a mesma parte, e quem assiste o primeiro quer o segundo em seguida.
    """
    youtube = _rb_publicar_youtube
    cortes = _rb_publicar_cortes
    config = carregar_config()

    # POR NAVEGADOR por padrao (decisao de 01/09/2026). A API continua no
    # projeto, mas so para LER: metricas e identidade do canal.
    urls = []
    for pedaco in cortes.preparar(video, limite=cortes.limite(config), log=log):
        urls.append(youtube.publicar_como_configurado(
            pedaco, visibilidade=visibilidade, canal="historias",
            agendar_para=agendar_para, config=config, log=log))
    return " | ".join(u for u in urls if u)


def publicar_tiktok(video: Video, *, postar: bool = False, log=print) -> str:
    """Sobe no TikTok pela conta do canal `historias` (para antes de postar
    quando `postar` e False — publicar sozinho nao e decisao de ferramenta)."""
    tiktok = _rb_publicar_tiktok
    # `postar or None` fazia `False` virar `None`, e `None` significa "use o
    # config" — ou seja, nao dava para dizer "NAO poste" a partir daqui.
    return tiktok.publicar(video, postar=bool(postar), canal="historias")
