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


def _confirmado(estado) -> bool:
    """Algum dos dois destinos confirmou?

    Um link `http` conta: o YouTube devolve a URL quando publica de verdade.
    As frases de sucesso dos dois modulos contam. Qualquer outra coisa, nao —
    e e por isso que a funcao nao pergunta a QUEM pertence o estado: o
    criterio e o mesmo, e ter dois criterios de "publicou" foi o defeito que
    fez rascunho contar como publicacao por semanas.
    """
    texto = str(estado or "")
    if texto.startswith("http"):
        return True
    for modulo in ("tiktok", "youtube_web"):
        try:
            mod = __import__(f"builds.publicar.{modulo}", fromlist=["SUCESSO"])
            if texto.startswith(getattr(mod, "SUCESSO", "\0")):
                return True
        except Exception:                                      # noqa: BLE001
            continue
    return False


def classificar(estado, falha: dict | None = None,
                laudo: dict | None = None) -> str:
    """"publicado", "sem_confirmacao", "infraestrutura" ou "falha".

    A ORDEM IMPORTA, e `laudo["clicou"]` vem antes do texto: a frase de
    retorno se perde quando algo levanta DEPOIS do clique (o ledger preso, o
    Chrome fechando), e ai sobrava `""` — classificado como "falha" e
    reenviado ate tres vezes sobre um post que ja podia estar no ar. A marca
    do laudo e escrita no instante do clique e sobrevive a excecao.
    """
    if _confirmado(estado):
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


ESPERA_DA_TRAVA_S = 20.0


class NaoConsegviLer(RuntimeError):
    """Nao deu para saber quem esta bloqueado.

    Quem chama NAO pode seguir: sem a lista, a recuperacao acha que ninguem
    esta bloqueado e reposta. E a falha fechada — a unica no projeto — e ela
    existe porque aqui o erro barato e "adiar uma rodada" e o erro caro e
    "publicar de novo no perfil do Adrian".
    """


def nome_da_trava(plataforma: str = "tiktok") -> str:
    """A trava que TODO leitor e escritor da lista deve segurar.

    Publica de proposito: o app, o bot e a grade mexem no mesmo arquivo, e
    sem trava comum o `os.replace` de um faz a leitura do outro falhar — que
    no desenho anterior era interpretado como "corrompido" e apagava a lista.
    """
    return f"{plataforma}_a_conferir"


def arquivo_a_conferir(canal: str, plataforma: str = "tiktok"):
    """Ao lado do ledger do canal: e estado da mesma familia.

    Um arquivo POR DESTINO: um video sem confirmacao no YouTube nao pode
    ficar bloqueado no TikTok, onde ele talvez ainda precise sair.
    """
    from .metricas import registro_do_canal
    return (registro_do_canal(canal).parent
            / f"_{plataforma}_a_conferir.json")


def _ler(caminho, tentativas: int = 3) -> dict:
    """Le o JSON, com nova tentativa antes de concluir "corrompido".

    A DIFERENCA ENTRE ERRO PASSAGEIRO E CORRUPCAO. No Windows, ler enquanto
    outro processo faz `os.replace` devolve erro de compartilhamento — e a
    versao anterior tratava isso como arquivo quebrado, renomeava a lista e
    recomecava VAZIA. A protecao contra corrupcao virava a causa da perda.
    `OSError` tenta de novo; so `ValueError` (JSON invalido de verdade) conta
    como corrupcao.
    """
    import time
    ultimo = None
    for n in range(tentativas):
        try:
            if not caminho.is_file():
                return {}
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            if not isinstance(dados, dict):
                raise ValueError("a marca nao e um objeto")
            return dados
        except OSError as exc:
            ultimo = exc
            time.sleep(0.4 * (n + 1))
    raise ultimo or OSError("nao consegui ler")


def a_conferir(canal: str = "historias", plataforma: str = "tiktok") -> set:
    """Videos cujo clique saiu sem confirmacao: ficam FORA da fila.

    Nao sao desistencia (o video nao tem defeito) nem atraso (pode estar no
    ar). Sao um terceiro estado, que so sai daqui por conferencia.

    LEVANTA quando nao consegue ler. A versao anterior devolvia `set()` em
    qualquer erro, e quem chama entendia "ninguem bloqueado" — repostando
    todos os marcados. Um conjunto vazio e uma afirmacao, nao um "nao sei".
    """
    return set(marcas(canal, plataforma))


def marcas(canal: str = "historias", plataforma: str = "tiktok") -> dict:
    """{video_id: {quando, estado, plataforma}}: a lista COM o motivo.

    A mesma leitura e a mesma falha fechada de `a_conferir` (que e o conjunto
    das chaves disto). Existe para quem precisa saber POR QUE o video esta
    parado — o audio (`[audio] ...`) sai sozinho quando o som volta; o
    clique sem confirmacao, so por conferencia.
    """
    from .. import travas
    caminho = arquivo_a_conferir(canal, plataforma)
    try:
        with travas.trava(nome_da_trava(plataforma),
                          esperar=ESPERA_DA_TRAVA_S) as minha:
            if minha is False:
                raise NaoConsegviLer(
                    f"a trava {nome_da_trava(plataforma)} esta ocupada")
            return dict(_ler(caminho))
    except (ValueError, OSError) as exc:
        _avisar(canal, texto=(
            f"nao consegui ler {caminho.name} ({type(exc).__name__}). A "
            f"recuperacao NAO roda nesta rodada: sem a lista eu nao sei quem "
            f"esta bloqueado, e publicar de novo e pior que adiar."))
        raise NaoConsegviLer(str(exc)) from exc


class NaoConsegviMarcar(RuntimeError):
    """Nao deu para gravar a marca de "a conferir".

    Levanta em vez de seguir calada porque a marca E o bloqueio: sem ela o
    video volta para a fila e a recuperacao o reposta. Um `except: pass` aqui
    transforma "nao consegui bloquear" em "nao havia o que bloquear".
    """


def marcar_para_conferir(canal: str, video_id: str, estado: str,
                         plataforma: str = "tiktok", *,
                         aviso: str | None = None, etapa: str | None = None,
                         erro: bool = True) -> bool:
    """Tira da fila e AVISA. Erro no diario, nao aviso no log.

    `aviso`, `etapa` e `erro` existem para quem marca POR OUTRO MOTIVO que o
    clique sem confirmacao (o audio mudo, desde 28/09/2026): o texto padrao
    diz "cliquei e pode estar no ar", o que para esses seria falso, e ERRO
    acionaria a apuracao por uma guarda que funcionou.

    ESCRITA ATOMICA E ARQUIVO CORROMPIDO PRESERVADO. A primeira versao lia o
    JSON, e com o arquivo cortado caia em `{}` e regravava a lista **so com o
    item novo** — apagando todas as marcas antigas e devolvendo aqueles
    videos para a fila. O modo de falha era exatamente o defeito que a marca
    existe para impedir, e chegava em silencio.

    Agora: arquivo ilegivel e RENOMEADO para `.corrompido` (nunca
    sobrescrito, porque ele e a unica copia de quem estava bloqueado), a
    gravacao vai por `.tmp` + `os.replace` (troca atomica: ou o arquivo
    antigo inteiro, ou o novo inteiro, nunca meio), e nao gravar LEVANTA.
    """
    if not video_id:
        return False
    import os
    from .. import travas
    caminho = arquivo_a_conferir(canal, plataforma)
    # LER E ESCREVER SOB A MESMA TRAVA, e nao so escrever: entre uma leitura
    # sem trava e a gravacao, outro processo pode marcar um video — e a
    # gravacao o apagaria.
    with travas.trava(nome_da_trava(plataforma),
                      esperar=ESPERA_DA_TRAVA_S) as minha:
        if minha is False:
            _avisar(canal, ref=video_id, texto=(
                f"{video_id}: a trava {nome_da_trava(plataforma)} nao veio; "
                f"NAO marquei. O video pode estar no ar e nao esta bloqueado."))
            raise NaoConsegviMarcar("a trava esta ocupada")
        try:
            dados = _ler(caminho)
        except ValueError as exc:
            # CORRUPCAO DE VERDADE (JSON invalido), e nao erro passageiro:
            # `_ler` ja tentou de novo em `OSError`.
            #
            # AQUI NAO SE GRAVA E NAO SE RENOMEIA, e as duas coisas pelo mesmo
            # motivo. A versao anterior renomeava o ilegivel e recomecava com
            # o item novo: as marcas antigas sobreviviam no `.corrompido` para
            # olho humano, mas a MAQUINA passava a ler uma lista de um item
            # so, e todos os outros voltavam para a fila e eram repostados.
            #
            # E renomear sozinho ja seria o bastante para o estrago: sem
            # arquivo, `a_conferir` devolve `set()` — "ninguem bloqueado" —,
            # que e uma AFIRMACAO. A falha fechada que a leitura mantem de
            # proposito viraria falha aberta na chamada seguinte, pela porta
            # dos fundos.
            #
            # Entao: copia de seguranca, o ilegivel FICA onde esta, e levanta.
            # `a_conferir` segue levantando, a rodada nao publica, e ninguem e
            # reposto ate uma pessoa olhar o arquivo. O erro barato e adiar.
            copia = caminho.with_suffix(
                f".corrompido-{datetime.now():%Y%m%d-%H%M%S}")
            try:
                copia.write_bytes(caminho.read_bytes())
            except OSError:
                pass
            _avisar(canal, ref=video_id, texto=(
                f"o {caminho.name} esta ilegivel ({type(exc).__name__}); "
                f"copiei para {copia.name} e NAO gravei nada. {video_id} pode "
                f"estar no ar e NAO esta bloqueado, e nenhuma rodada publica "
                f"ate o arquivo ser consertado a mao."))
            raise NaoConsegviMarcar(f"{caminho.name} ilegivel") from exc
        if video_id in dados:
            return True                  # ja avisado; nao repete no diario
        dados[video_id] = {
            "quando": datetime.now().isoformat(timespec="seconds"),
            "estado": str(estado)[:200], "plataforma": plataforma}
        try:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            tmp = caminho.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            os.replace(tmp, caminho)
        except OSError as exc:
            _avisar(canal, ref=video_id, texto=(
                f"{video_id}: NAO consegui gravar a marca de 'a conferir' "
                f"({type(exc).__name__}). O video pode estar no ar e NAO esta "
                f"bloqueado — confira antes da proxima rodada."))
            raise NaoConsegviMarcar(str(exc)) from exc
    _avisar(canal, ref=video_id, etapa=etapa, atividade_erro=erro,
            texto=aviso or (
                f"{video_id}: cliquei em publicar no {plataforma} e nao veio "
                f"confirmacao. Pode estar no ar — NAO reenvio sozinho para "
                f"nao duplicar. Precisa de conferencia no perfil."))
    return True


def soltar_marca(canal: str, video_id: str, plataforma: str = "tiktok", *,
                 prefixo: str) -> bool:
    """Tira UMA marca, e so se o `estado` dela comecar com `prefixo`.

    Existe para as marcas que a MAQUINA sabe desfazer — o audio mudo
    (`audio.PREFIXO_DA_MARCA`), que sai quando o re-render devolve o som. A
    de clique sem confirmacao nunca sai por aqui: so por conferencia humana.
    Por isso `prefixo` e obrigatorio e nao pode ser vazio: "" casaria com
    toda marca.

    Mesma trava, mesma leitura e mesma escrita atomica de
    `marcar_para_conferir`. Trava ocupada ou arquivo ilegivel: nao mexe, e
    devolve False — o video so fica mais uma rodada parado.
    """
    if not video_id or not prefixo:
        return False
    import os
    from .. import travas
    caminho = arquivo_a_conferir(canal, plataforma)
    with travas.trava(nome_da_trava(plataforma),
                      esperar=ESPERA_DA_TRAVA_S) as minha:
        if minha is False:
            return False
        try:
            dados = _ler(caminho)
        except (ValueError, OSError):
            return False
        marca = dados.get(video_id)
        if not isinstance(marca, dict):
            return False
        if not str(marca.get("estado") or "").startswith(prefixo):
            return False
        del dados[video_id]
        try:
            tmp = caminho.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            os.replace(tmp, caminho)
        except OSError:
            return False
    return True


def _avisar(canal: str, texto: str, ref: str = "",
            atividade_erro: bool = True, etapa: str | None = None) -> None:
    """Diario, nunca log: ninguem le log as 3 da manha."""
    try:
        from .. import atividade
        atividade.registrar(
            "publicacao",
            atividade.ERRO if atividade_erro else atividade.LOG,
            texto, canal, etapa=etapa or "publicar.tiktok.sem_confirmacao",
            ref=ref)
    except Exception:                                          # noqa: BLE001
        pass


def resolver(canal: str, video, estado: str, laudo: dict | None = None,
             falha: dict | None = None, plataforma: str = "tiktok") -> str:
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
            estado or "o clique saiu e nao veio confirmacao", plataforma)
    return desfecho
