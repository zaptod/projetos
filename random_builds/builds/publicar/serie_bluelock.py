# -*- coding: utf-8 -*-
"""A serie de videos do Blue Lock: a FONTE dos episodios e as guardas deles.

O que e: o Adrian faz uma serie de videos sobre como criou o simulador de
futebol Blue Lock dele. Os episodios nascem fora deste repositorio (em
`E:\\BLUE-Lock-serie-capturas`), passam pelo conferente e chegam aqui prontos.
Esta parte so ESCOLHE e REGISTRA — nao cria nada (ver `docs/sessoes/publicacao.md`).

Contas (nao mudam): o canal do PRODUTO e `bluelock`; os DESTINOS sao os do
antigo `zombie` (`contas.CANAIS_ANTIGOS`): YouTube pelo navegador
(`youtube_web`, conta `zombie_survivores`) e TikTok `zombie_surviv0rs`.

A FONTE (decisao do Adrian, 26/10/2026): uma pasta com UM JSON por episodio,
`NF_SERIE_BLUELOCK` ou `E:\\BLUE-Lock-serie-capturas\\publicar`:

    {"episodio": 1,
     "arquivo": "E:\\\\BLUE-Lock-serie-capturas\\\\piloto\\\\EP01_v6.mp4",
     "sha256": "<do mp4 aprovado>",
     "titulo": "...", "descricao": "...", "tags": ["#bluelock", ...],
     "idioma": "pt", "aprovado_por_conferente": true}

SO ENTRA O QUE TEM A MARCA, e a marca e AMARRADA AO ARQUIVO pelo `sha256`:
trocar o mp4 depois da conferencia (um re-render com o mesmo nome) tira o
episodio da fila em vez de publicar o que ninguem viu.

AS GUARDAS (todas FALHAM FECHADAS: na duvida nao publica; repetir e pior que
nao postar):

  1. so episodio aprovado, com arquivo e `sha256` iguais;
  2. a ORDEM: o episodio N so sai depois do N-1 NAQUELE destino (e o proximo
     da serie e sempre o menor que falta; se ele nao esta aprovado o horario
     fica vazio — nunca pula para o seguinte);
  3. titulo unico: `titulos.chave` igual a de um ja publicado no destino
     barra (nunca o `==` do texto);
  4. um por dia por destino (`TETO_POR_DIA`), contado pelo `quando` do ledger;
  5. "a conferir" ilegivel ou com o episodio nela barra (`desfecho.marcas`);
  6. as regras do Adrian para o TEXTO da serie: nada de ferramenta de IA de
     desenvolvimento, nada tecnico, nada do GitHub nem do local do projeto
     (`texto_proibido`) — vale para titulo, descricao e tags.

O ledger e PROPRIO (`metricas.registro_do_canal("bluelock")`), com a mesma
trava (`ledger__bluelock`) e o mesmo contrato de `metricas.publicado`.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from . import titulos

CANAL = "bluelock"
PASTA_PADRAO = Path(r"E:\BLUE-Lock-serie-capturas\publicar")
TETO_POR_DIA = 1
DESTINOS = ("youtube", "tiktok")

# As regras do Adrian para o texto da serie (26/10/2026). Um filtro de
# DEFESA: o texto ja nasce certo, e isto so impede que um episodio futuro
# escape com uma frase que ele proibiu. Palavra inteira, sem caixa nem acento.
_PROIBIDAS = (
    "github", "gitlab", "git", "commit", "commits", "pull request",
    "claude", "codex", "copilot", "cursor", "chatgpt", "gemini", "openai",
    "anthropic", "gpt", "llm",
    "codigo", "repositorio", "typescript", "javascript", "python", "vite",
    "npm", "terminal", "debug", "bug", "bugs", "algoritmo", "script",
    "e:\\", "c:\\",
)


def _sem_acento(texto: str) -> str:
    import unicodedata
    base = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in base if not unicodedata.combining(c)).lower()


def texto_proibido(*textos) -> str:
    """A primeira palavra proibida achada nos textos, ou `""`. Pura."""
    corpo = " ".join(_sem_acento(t) for t in textos)
    for palavra in _PROIBIDAS:
        if palavra.endswith("\\"):
            if palavra in corpo:
                return palavra
            continue
        if re.search(rf"(?<![\w]){re.escape(palavra)}(?![\w])", corpo):
            return palavra
    return ""


def pasta() -> Path:
    return Path(os.environ.get("NF_SERIE_BLUELOCK") or PASTA_PADRAO)


@dataclass
class Episodio:
    numero: int
    arquivo: Path
    titulo: str
    descricao: str
    tags: list = field(default_factory=list)
    idioma: str = "pt"
    sha256: str = ""
    ficha: Path | None = None
    pergunta: str = ""
    capa_s: float = 0.0

    @property
    def id(self) -> str:
        return f"bluelock_ep{self.numero:02d}"

    def descricao_com_pergunta(self) -> str:
        """A descricao com a `pergunta` da ficha como ULTIMA linha do texto,
        antes das hashtags (`Video.descricao_completa` poe as tags depois).
        Decisao do Adrian (26/10): a pergunta vai na descricao, nao em
        comentario. Sem `pergunta`, ou ja dentro do texto: nada muda."""
        if not self.pergunta or self.pergunta in self.descricao:
            return self.descricao
        return self.descricao + "\n\n" + self.pergunta

    def como_video(self):
        """O item que os publicadores esperam (`catalogo.Video`)."""
        from .catalogo import Video
        video = Video(
            id=self.id, origem="serie_bluelock", perfil="celular",
            caminho=self.arquivo, titulo=self.titulo,
            descricao=self.descricao_com_pergunta(),
            hashtags=list(self.tags), fonte_id=self.id,
            rotulo=f"Blue Lock #{self.numero}",
            bytes=self.arquivo.stat().st_size,
            quando=self.arquivo.stat().st_mtime)
        # O TikTok escolhe a CAPA no upload (so a serie passa isto): o quadro
        # `capa_s` da ficha, padrao 0 = o gancho.
        video.capa_s = self.capa_s
        return video


def sha256_de(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def _ler_ficha(arquivo: Path) -> tuple:
    """(Episodio | None, motivo). O motivo diz por que ficou de fora."""
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return None, f"{arquivo.name}: ilegivel ({type(exc).__name__})"
    if not isinstance(dados, dict):
        return None, f"{arquivo.name}: nao e um objeto"
    try:
        numero = int(dados.get("episodio"))
    except (TypeError, ValueError):
        return None, f"{arquivo.name}: sem numero de episodio"
    if numero < 1:
        return None, f"{arquivo.name}: numero de episodio invalido"
    nome = f"ep{numero:02d}"
    if dados.get("aprovado_por_conferente") is not True:
        return None, f"{nome}: sem a marca de aprovado pelo conferente"
    titulo = str(dados.get("titulo") or "").strip()
    descricao = str(dados.get("descricao") or "").strip()
    tags = [str(t).strip() for t in (dados.get("tags") or []) if str(t).strip()]
    if not titulo or not descricao:
        return None, f"{nome}: sem titulo ou sem descricao"
    if len(titulo) > 100:
        return None, f"{nome}: titulo com {len(titulo)} caracteres (maximo 100)"
    pergunta = str(dados.get("pergunta") or "").strip()
    if len(pergunta) > 500:
        return None, f"{nome}: pergunta com {len(pergunta)} caracteres (maximo 500)"
    try:
        capa_s = float(dados.get("capa_s", 0) or 0)
    except (TypeError, ValueError):
        return None, f"{nome}: capa_s invalido"
    if not 0 <= capa_s <= 600:
        return None, f"{nome}: capa_s fora de 0..600 s"
    proibida = texto_proibido(titulo, descricao, pergunta, *tags)
    if proibida:
        return None, (f"{nome}: o texto fala de '{proibida}' (regra do "
                      "Adrian: nada tecnico, de IA de desenvolvimento nem do "
                      "projeto)")
    if str(dados.get("idioma") or "") != "pt":
        return None, f"{nome}: idioma {dados.get('idioma')!r} (a serie e em pt)"
    caminho = Path(str(dados.get("arquivo") or ""))
    if not caminho.is_absolute():
        caminho = arquivo.parent / caminho
    if not caminho.is_file():
        return None, f"{nome}: o arquivo {caminho} nao existe"
    esperado = str(dados.get("sha256") or "").lower()
    if len(esperado) != 64:
        return None, f"{nome}: sem sha256 do arquivo aprovado"
    try:
        real = sha256_de(caminho)
    except OSError as exc:
        return None, f"{nome}: nao consegui ler o arquivo ({type(exc).__name__})"
    if real != esperado:
        return None, (f"{nome}: o arquivo mudou depois da aprovacao "
                      f"(sha256 {real[:12]} em vez de {esperado[:12]})")
    return Episodio(numero=numero, arquivo=caminho, titulo=titulo,
                    descricao=descricao, tags=tags, idioma="pt",
                    sha256=real, ficha=arquivo, pergunta=pergunta,
                    capa_s=capa_s), ""


def episodios(origem: Path | None = None) -> tuple:
    """([Episodio aprovados, por numero], [motivos dos que ficaram de fora]).

    Pasta que nao existe = fila vazia, sem erro (o horario fica vazio sem
    alarme falso). Dois JSON com o mesmo numero: nenhum dos dois entra.
    """
    base = Path(origem) if origem is not None else pasta()
    if not base.is_dir():
        return [], []
    validos, fora = {}, []
    repetidos = set()
    for arquivo in sorted(base.glob("*.json")):
        ep, motivo = _ler_ficha(arquivo)
        if ep is None:
            fora.append(motivo)
        elif ep.numero in validos:
            repetidos.add(ep.numero)
        else:
            validos[ep.numero] = ep
    for numero in sorted(repetidos):
        validos.pop(numero, None)
        fora.append(f"ep{numero:02d}: dois JSON com o mesmo numero")
    return [validos[n] for n in sorted(validos)], fora


def pergunta_de(numero: int, origem: Path | None = None) -> str:
    """A `pergunta` da ficha do episodio (comentario fixado), ou `""`. So de
    episodio aprovado e valido; nunca levanta."""
    try:
        for ep in episodios(origem)[0]:
            if ep.numero == int(numero):
                return ep.pergunta
    except Exception:                                          # noqa: BLE001
        pass
    return ""


def _destino(linha: dict) -> str:
    return str(linha.get("plataforma") or "youtube").lower()


def _quando(linha: dict):
    try:
        return datetime.fromisoformat(str(linha.get("quando")))
    except ValueError:
        return None


def escolher(plataforma: str, aprovados: list, linhas: list, marcados: set,
             hoje: date | None = None) -> tuple:
    """(Episodio | None, motivo): o proximo da serie NESTE destino. Pura.

    `linhas`: o ledger do canal; `marcados`: ids na lista "a conferir" do
    destino. O caso ZERO (sem aprovado, ledger vazio) devolve `(None, motivo)`
    — horario vazio, nao erro.
    """
    from . import metricas
    destino = str(plataforma).lower()
    hoje = hoje or datetime.now().date()
    feitos, titulos_no_ar, hoje_n = set(), set(), 0
    for linha in linhas:
        if _destino(linha) != destino:
            continue
        if metricas.apagado_do_canal(linha):
            feitos.add(str(linha.get("video_id") or ""))
            continue
        if not metricas.publicado(linha):
            continue
        feitos.add(str(linha.get("video_id") or ""))
        chave = titulos.chave(linha.get("titulo"))
        if chave:
            titulos_no_ar.add(chave)
        quando = _quando(linha)
        if quando is not None and quando.date() == hoje:
            hoje_n += 1
    if hoje_n >= TETO_POR_DIA:
        return None, f"ja saiu {hoje_n} episodio hoje no {destino}"
    proximo = 1
    while f"bluelock_ep{proximo:02d}" in feitos:
        proximo += 1
    por_numero = {ep.numero: ep for ep in aprovados}
    ep = por_numero.get(proximo)
    if ep is None:
        return None, (f"o episodio {proximo} ainda nao esta aprovado na "
                      "fila (a ordem da serie manda esperar por ele)")
    if ep.id in marcados:
        return None, f"{ep.id} esta na lista 'a conferir' do {destino}"
    chave = titulos.chave(ep.titulo)
    if chave and chave in titulos_no_ar:
        return None, f"o titulo de {ep.id} ja esta no ar no {destino}"
    return ep, ""


def registrar(video, url: str, plataforma: str, extra: dict | None = None
              ) -> dict:
    """Uma linha no ledger PROPRIO da serie. Nunca perde a linha (trava)."""
    from . import metricas
    linha = {
        "quando": datetime.now().isoformat(timespec="seconds"),
        "plataforma": plataforma, "url": url,
        "youtube_id": None, "video_id": video.id, "fonte_id": video.fonte_id,
        "origem": video.origem, "perfil": video.perfil, "variante": "A",
        "titulo": video.titulo, "canal": CANAL,
    }
    linha.update(extra or {})
    if "prova" in linha:
        linha["prova"] = metricas.em_lista(linha["prova"])
    metricas.acrescentar_ao_ledger(metricas.registro_do_canal(CANAL), linha,
                                   CANAL)
    return linha


QUEM_AUTORIZA = ("Adrian", "orquestrador", "conferente")
PASTA_DAS_DECISOES = Path(__file__).resolve().parents[3] / "decisoes"


def _autorizacao_confere(referencia: str) -> str:
    """`""` se a referencia serve; senao o motivo. Duas formas validas:
    `no:<projeto>/<id>` (um no do Grimorio JA DECIDIDO, lido do disco) ou uma
    citacao literal com a data (`"..." (26/10)`), de pelo menos 20 letras."""
    referencia = str(referencia or "").strip()
    achado = re.fullmatch(r"no:([\w-]+)/([\w-]+)", referencia)
    if achado:
        arquivo = PASTA_DAS_DECISOES / achado.group(1) / f"{achado.group(2)}.json"
        try:
            no = json.loads(arquivo.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return f"o no {referencia[3:]} do Grimorio nao existe ou nao abre"
        if no.get("situacao") != "decidida" or not (no.get("vigente") or {}):
            return f"o no {referencia[3:]} nao esta decidido"
        return ""
    if len(referencia) < 20 or not re.search(r"\d{1,2}/\d{1,2}", referencia):
        return ("a autorizacao e um no do Grimorio (`no:projeto/id`, ja "
                "decidido) ou uma citacao literal com a data (dd/mm)")
    return ""


def aprovar(numero: int, origem: Path | None = None, *, por: str = "",
            autorizacao: str = "", conferente: str = "") -> str:
    """Poe a marca de aprovado no JSON do episodio `numero`, CONFERINDO antes
    que o `sha256` dele e o do arquivo de hoje sao o mesmo (a marca e amarrada
    ao que alguem viu). Devolve o caminho da ficha. Levanta `ValueError` se
    nao da.

    A autorizacao fica REGISTRADA na ficha (26/10/2026: duas recusas por falta
    de prova de que o Adrian tinha mandado): `autorizado_por` (Adrian,
    orquestrador ou conferente), `autorizacao` (no do Grimorio ja decidido ou
    citacao literal com data), `conferente` (veredito + caminho da prova) e
    `autorizado_em`. Sem os tres, nao aprova: a marca sem rastro e o que
    fez o agente de publicacao desconfiar de uma ordem legitima.
    """
    por = str(por or "").strip()
    if por.lower() not in {q.lower() for q in QUEM_AUTORIZA}:
        raise ValueError(f"`por` e um de {QUEM_AUTORIZA}, nao {por!r}")
    motivo = _autorizacao_confere(autorizacao)
    if motivo:
        raise ValueError(motivo)
    if len(str(conferente or "").strip()) < 10:
        raise ValueError("`conferente`: o veredito e o caminho da prova")
    base = Path(origem) if origem is not None else pasta()
    for arquivo in sorted(base.glob("*.json")):
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if not isinstance(dados, dict) or dados.get("episodio") != numero:
            continue
        caminho = Path(str(dados.get("arquivo") or ""))
        if not caminho.is_absolute():
            caminho = arquivo.parent / caminho
        if not caminho.is_file():
            raise ValueError(f"o arquivo {caminho} nao existe")
        real = sha256_de(caminho)
        if real != str(dados.get("sha256") or "").lower():
            raise ValueError(
                f"o arquivo mudou (sha256 {real[:12]}): confira de novo antes "
                "de aprovar")
        agora = datetime.now().isoformat(timespec="seconds")
        dados["aprovado_por_conferente"] = True
        dados["aprovado_em"] = agora
        dados["autorizado_por"] = por
        dados["autorizacao"] = str(autorizacao).strip()
        dados["conferente"] = str(conferente).strip()
        dados["autorizado_em"] = agora
        arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2)
                           + "\n", encoding="utf-8")
        _, motivo = _ler_ficha(arquivo)
        if motivo:
            raise ValueError(f"aprovado, mas a ficha nao passa: {motivo}")
        return str(arquivo)
    raise ValueError(f"nao achei o JSON do episodio {numero} em {base}")


def main(argv=None) -> int:
    """`python -m builds.publicar.serie_bluelock` mostra a fila (so le);
    `... aprovar N` poe a marca de aprovado no episodio N."""
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["aprovar"]:
        import argparse
        ap = argparse.ArgumentParser(prog="serie_bluelock aprovar")
        ap.add_argument("numero", type=int)
        ap.add_argument("--por", required=True, choices=list(QUEM_AUTORIZA))
        ap.add_argument("--autorizacao", required=True,
                        help="no:projeto/id do Grimorio ja decidido, ou "
                             "citacao literal com a data")
        ap.add_argument("--conferente", required=True,
                        help="veredito + caminho da prova")
        ns = ap.parse_args(argv[1:])
        try:
            print("aprovado:", aprovar(ns.numero, por=ns.por,
                                       autorizacao=ns.autorizacao,
                                       conferente=ns.conferente))
            return 0
        except ValueError as exc:
            print("nao aprovei:", exc)
            return 1
    from . import metricas
    aprovados, fora = episodios()
    print(f"fonte: {pasta()}")
    print(f"aprovados: {[e.id for e in aprovados] or 'nenhum'}")
    for motivo in fora:
        print("  fora:", motivo)
    try:
        linhas = metricas.publicados(CANAL)
    except Exception as exc:                                   # noqa: BLE001
        print("ledger ilegivel:", exc)
        return 1
    for destino in DESTINOS:
        ep, motivo = escolher(destino, aprovados, linhas, set())
        print(f"{destino}: " + (f"proximo {ep.id}" if ep else motivo))
    return 0


__all__ = ["QUEM_AUTORIZA", "CANAL", "DESTINOS", "TETO_POR_DIA", "Episodio", "aprovar",
           "episodios", "escolher", "pasta", "pergunta_de", "registrar", "sha256_de",
           "texto_proibido"]


if __name__ == "__main__":                               # pragma: no cover
    raise SystemExit(main())
