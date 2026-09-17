# -*- coding: utf-8 -*-
"""O que aconteceu de verdade quando se clicou em publicar no TikTok.

Ate 16/09/2026 so havia duas respostas — confirmou ou nao — e o "nao" juntava
tres desfechos que pedem reacoes OPOSTAS:

  publicado        o TikTok confirmou.
  sem_confirmacao  o CLIQUE SAIU e o aviso de sucesso nao apareceu. O post
                   pode estar no ar; reenviar DUPLICA no perfil, e duplicata
                   o publico ve. Fica fora da fila ate alguem conferir.
  infraestrutura   Chrome que nao abre, perfil ocupado, login vencido, rede
                   fora. Nao e culpa do video: nao conta para a desistencia e
                   continua na fila, porque a proxima rodada pode funcionar.
  falha            legenda que nao fica, arquivo recusado. E dela, e so dela,
                   que o contador de tres tentativas fala.

POR QUE ESTE MODULO EXISTE, e nao um trecho dentro do `postar.py`: a
classificacao morava la, e o `main.py publicar <id> --tiktok --postar` — que
e o `/publicar` do bot e o botao do app — chama `tiktok.publicar` DIRETO.
Entao um clique sem confirmacao por esse caminho nao marcava nada, e a
recuperacao da grade repostava. E a terceira vez que uma guarda "no ponto"
deixa passar por uma porta que ninguem contou; por isso ela agora e chamada
de dentro do `tiktok.publicar`, que e o funil por onde TODOS passam.
"""
from __future__ import annotations

import json
import unicodedata
from datetime import datetime

# O CLIQUE SAIU. Qualquer estado com isto significa que o post PODE estar no
# ar, e reenviar duplicaria.
MARCAS_DE_CLIQUE = ("cliquei em publicar",)

# Falha que nao e do video: a maquina, a rede, a sessao. Contar isto como
# defeito do video abandonaria, depois de tres rodadas, um video sao.
MARCAS_DE_INFRAESTRUTURA = (
    "nao consegui abrir o chrome", "perfilocupado", "perfil esta em uso",
    "pediu login", "nao esta valida neste perfil",
    "err_name_not_resolved", "err_connection", "err_internet",
    "net::err", "nao achei o campo de arquivo",
)


def _sem_acentos(texto: str) -> str:
    """Minusculas e sem acento, para as marcas casarem de verdade.

    "nao achei o campo de arquivo" nunca casava: o `tiktok.py` escreve "nao"
    COM acento e a comparacao era byte a byte. Marca que nunca casa e pior
    que marca ausente — ela da a impressao de estar coberto.
    """
    normal = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(c for c in normal if not unicodedata.combining(c))


def classificar(estado, falha: dict | None = None,
                laudo: dict | None = None) -> str:
    """"publicado", "sem_confirmacao", "infraestrutura" ou "falha".

    A ORDEM IMPORTA, e `laudo["clicou"]` vem antes do texto: a frase de
    retorno se perde quando algo levanta DEPOIS do clique (o ledger preso, o
    Chrome fechando), e ai sobrava `""` — classificado como "falha" e
    reenviado ate tres vezes sobre um post que ja podia estar no ar. A marca
    do laudo e escrita no instante do clique e sobrevive a excecao.
    """
    from .tiktok import confirmado
    if confirmado(estado):
        return "publicado"
    if (laudo or {}).get("clicou"):
        return "sem_confirmacao"
    texto = _sem_acentos(str(estado or ""))
    if any(m in texto for m in MARCAS_DE_CLIQUE):
        return "sem_confirmacao"
    motivo = _sem_acentos(" ".join(str(v) for v in (falha or {}).values()))
    if any(m in motivo for m in MARCAS_DE_INFRAESTRUTURA):
        return "infraestrutura"
    return "falha"


def arquivo_a_conferir(canal: str):
    """Ao lado do ledger do canal: e estado da mesma familia."""
    from .metricas import registro_do_canal
    return registro_do_canal(canal).parent / "_tiktok_a_conferir.json"


def a_conferir(canal: str = "historias") -> set:
    """Videos cujo clique saiu sem confirmacao: ficam FORA da fila.

    Nao sao desistencia (o video nao tem defeito) nem atraso (pode estar no
    ar). Sao um terceiro estado, que so sai daqui por conferencia.
    """
    try:
        caminho = arquivo_a_conferir(canal)
        if not caminho.is_file():
            return set()
        return set(json.loads(caminho.read_text(encoding="utf-8")))
    except Exception:                                          # noqa: BLE001
        return set()


def marcar_para_conferir(canal: str, video_id: str, estado: str) -> None:
    """Tira da fila e AVISA. Erro no diario, nao aviso no log."""
    if not video_id:
        return
    try:
        caminho = arquivo_a_conferir(canal)
        dados = {}
        if caminho.is_file():
            try:
                dados = json.loads(caminho.read_text(encoding="utf-8"))
            except ValueError:
                dados = {}
        if video_id in dados:
            return                       # ja avisado; nao repete no diario
        dados[video_id] = {
            "quando": datetime.now().isoformat(timespec="seconds"),
            "estado": str(estado)[:200]}
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        from .. import atividade
        atividade.registrar(
            "publicacao", atividade.ERRO,
            f"{video_id}: cliquei em publicar no TikTok e nao veio "
            f"confirmacao. Pode estar no ar — NAO reenvio sozinho para nao "
            f"duplicar. Precisa de conferencia no perfil.",
            canal, etapa="publicar.tiktok.sem_confirmacao", ref=video_id)
    except Exception:                                          # noqa: BLE001
        pass


def resolver(canal: str, video, estado: str, laudo: dict | None = None,
             falha: dict | None = None) -> str:
    """Classifica e REAGE. Devolve o desfecho.

    Chamada de dentro do `tiktok.publicar`, para que nenhum dos caminhos que
    publicam no TikTok — rodada normal dos dois canais, "so TikTok",
    escoamento, recuperacao, reserva, `main.py publicar`, bot e app — escape
    dela. Guarda que depende de ser lembrada em cada ponto nao e guarda.
    """
    desfecho = classificar(estado, falha, laudo)
    if desfecho == "sem_confirmacao":
        marcar_para_conferir(
            canal, getattr(video, "id", ""),
            estado or "o clique saiu e nao veio confirmacao")
    return desfecho
