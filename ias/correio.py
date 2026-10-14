# -*- coding: utf-8 -*-
"""O CORREIO: a caixa de mensagens de cada IA (Vila das IAs, fase 2).

Pedido do Adrian (plano `vila-das-ias.md`): "que eu possa falar com cada uma
individualmente pelo app". Tudo passa por AQUI, nunca direto: o app deixa a
mensagem na caixa, o carteiro (`carteiro.py`) a entrega e guarda a resposta.
Fica auditavel, a Mesa mostra, e nenhum navegador abre dentro do servidor.

Onde: `%LOCALAPPDATA%\\neural-fights\\ias\\<ia>\\correio.jsonl` (fora do git;
`NF_IAS_PASTA` troca a raiz, para a instancia de teste). E um registro SO DE
ACRESCIMO: a primeira linha de uma mensagem e o registro inteiro e as
seguintes, com o mesmo `id`, sao deltas (`situacao`, `resposta`, `erro`...).
Ler e dobrar por id. Uma linha por `write`, sob trava de arquivo: nada e
reescrito, entao um carteiro e um servidor escrevendo ao mesmo tempo nao se
pisam, e meia linha (um processo morto no meio) e pulada na leitura.

Formato de uma mensagem dobrada:

    {"id": "3f9a1c2e", "em": "2026-09-29T07:40:00", "de": "adrian",
     "para": "deepseek", "thread": "casa:deepseek", "texto": "...",
     "anexos": ["C:\\...\\anexos\\20260929_074000_foto.png"],
     "situacao": "pendente|entregue|respondida|falhou",
     "resposta": null|"...", "erro": null|"...", "categoria": null|"limite",
     "nota": null|"esperando a pipeline soltar a conta",
     "entregue_em", "respondida_em", "falhou_em", "visto", "atualizado_em"}

`thread` e a CASA da IA (decisao `ias-chat-persistente`, 29/09/2026: um chat
de longa duracao por IA, com resumo periodico): `casa.json` guarda a URL do
chat e o contador de mensagens; `casa_resumo.md` e o ultimo resumo.

O caso ZERO existe: sem pasta, sem arquivo, `ler()` devolve `[]` e
`resumo()` diz zero em tudo.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# As IAs de CHAT conversam (texto). Desde 29/09 (tarde, pedido do Adrian:
# "os modelos que geram imagem, eu preciso ter suporte para isso tambem") o
# correio tambem leva PEDIDOS DE IMAGEM (`tipo: "imagem"`): para os geradores
# (PicassoIA, e Grok/Gemini/ChatGPT na casa deles) e para a caixa `livre`, o
# rodizio ("qualquer um livre"), que o carteiro resolve na hora de entregar.
CHATS = ("deepseek", "chatgpt", "gemini", "grok")
GERADORES = ("picasso", "grok", "gemini", "chatgpt", "dreamface", "digen")
LIVRE = "livre"
CAIXAS = CHATS + ("picasso", "dreamface", "digen", LIVRE)
ROTULOS = {"deepseek": "DeepSeek", "chatgpt": "ChatGPT", "gemini": "Gemini",
           "grok": "Grok", "picasso": "PicassoIA", "dreamface": "DreamFace",
           "digen": "Digen", LIVRE: "Qualquer um livre"}
EMOJIS = {"deepseek": "🐋", "chatgpt": "🤖", "gemini": "✨", "grok": "🚀",
          "picasso": "🎨", "dreamface": "🌙", "digen": "🎥", LIVRE: "🎲"}
SITUACOES = ("pendente", "entregue", "respondida", "falhou")
TIPOS = ("texto", "imagem")
TEXTO_MAX = 20_000
# O teto do prompt de imagem (o do PicassoIA; o campo do site nao mostra
# maxlength, e o worker das historias corta em 900).
PROMPT_IMAGEM_MAX = 5_000
ANEXO_MAX_BYTES = 8 * 1024 * 1024
EXTENSOES_DE_ANEXO = (".png", ".jpg", ".jpeg", ".webp")
# Quanto tempo depois do ultimo pedido do app a uma caixa ele ainda conta
# como "olhando": a resposta que chega nesse prazo vira balao, nao Telegram.
PRESENCA_S = 45.0


class CorreioInvalido(ValueError):
    """Mensagem que nao pode entrar na caixa: diz por que."""


# ------------------------------------------------------------------ onde
def raiz() -> Path:
    alvo = os.environ.get("NF_IAS_PASTA")
    if alvo:
        return Path(alvo)
    try:
        from builds.contas import runtime_dir
        return runtime_dir() / "ias"
    except Exception:                                          # noqa: BLE001
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "neural-fights"
        return base / "ias"


def pasta(ia: str) -> Path:
    return raiz() / _ia(ia)


def arquivo(ia: str) -> Path:
    return pasta(ia) / "correio.jsonl"


def _ia(ia: str) -> str:
    """Uma CAIXA do correio (as de chat, as de imagem e a `livre`)."""
    chave = str(ia or "").strip().lower()
    if chave not in CAIXAS:
        raise CorreioInvalido(
            f"IA desconhecida no correio: {ia!r}. Use uma de: {', '.join(CAIXAS)}")
    return chave


def _chat(ia: str) -> str:
    """Uma IA que CONVERSA (texto e casa)."""
    chave = _ia(ia)
    if chave not in CHATS:
        raise CorreioInvalido(
            f"{ROTULOS.get(chave, chave)} não conversa por texto: use Criar. "
            f"Conversam: {', '.join(CHATS)}")
    return chave


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def novo_id() -> str:
    return secrets.token_hex(4)


def thread_da_casa(ia: str) -> str:
    return f"casa:{_ia(ia)}"


def tipo(mensagem: dict) -> str:
    """`texto` (o padrao, e toda mensagem de antes de 29/09) ou `imagem`."""
    return "imagem" if (mensagem or {}).get("tipo") == "imagem" else "texto"


# ----------------------------------------------------------------- trava
@contextmanager
def _trancado(alvo: Path, esperar: float = 10.0):
    """Trava de arquivo ao lado do alvo (msvcrt/fcntl). Nunca apaga o lock."""
    alvo.parent.mkdir(parents=True, exist_ok=True)
    lock = alvo.with_suffix(alvo.suffix + ".lock")
    fh = open(lock, "a+b")
    fim = time.monotonic() + float(esperar)
    pego = False
    try:
        fh.seek(0, os.SEEK_END)
        if fh.tell() == 0:
            fh.write(b"\0")
            fh.flush()
        while True:
            fh.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                pego = True
                break
            except OSError:
                if time.monotonic() >= fim:
                    raise OSError(f"o correio esta ocupado ({lock.name})")
                time.sleep(0.1)
        yield
    finally:
        if pego:
            try:
                fh.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        fh.close()


def _anexar_linha(alvo: Path, dados: dict) -> None:
    linha = (json.dumps(dados, ensure_ascii=False) + "\n").encode("utf-8")
    with _trancado(alvo):
        with open(alvo, "ab") as fh:
            fh.write(linha)
            fh.flush()


# ---------------------------------------------------------------- escrita
def enviar(ia: str, texto: str, *, de: str = "adrian", anexos=(),
           thread: str | None = None) -> dict:
    """Deixa uma mensagem na caixa da IA. Devolve a mensagem (pendente)."""
    ia = _chat(ia)
    texto = str(texto or "").strip()
    if not texto:
        raise CorreioInvalido("mensagem vazia")
    if len(texto) > TEXTO_MAX:
        raise CorreioInvalido(f"mensagem longa demais ({len(texto)} > {TEXTO_MAX} chars)")
    caminhos = []
    for anexo in anexos or ():
        p = Path(anexo)
        if not p.is_file():
            raise CorreioInvalido(f"anexo nao existe: {p}")
        caminhos.append(str(p))
    mensagem = {
        "id": novo_id(), "em": agora(), "de": str(de or "adrian")[:40],
        "para": ia, "thread": thread or thread_da_casa(ia), "texto": texto,
        "anexos": caminhos, "situacao": "pendente", "resposta": None,
        "erro": None, "categoria": None, "nota": None,
    }
    _anexar_linha(arquivo(ia), mensagem)
    return dict(mensagem, atualizado_em=mensagem["em"])


def pedir_imagem(caixa: str, prompt: str, *, proporcao: str, modelo: str | None = None,
                 de: str = "adrian", dono: int | None = None, anexos=(),
                 mensagem_id: str | None = None) -> dict:
    """Deixa um PEDIDO DE IMAGEM na caixa de um gerador (ou na `livre`).

    O `texto` da mensagem e o prompt (a primeira linha de uma mensagem precisa
    de `texto`). Quem confere se o gerador gera hoje e a proporcao que ele
    oferece e `ias.imagem` (pela ficha); aqui so a forma.

    `dono` (um PID) RESERVA o pedido para quem vai entrega-lo ele mesmo (o
    worker das historias, com um Carteiro proprio): o carteiro de servico nao
    o pega enquanto o dono viver (`reservado_por_outro`). Ate 05/10/2026 o
    pedido nascia livre e os dois o entregavam: desde 02/10, 36 de 173
    imagens do PicassoIA, 12 de 178 do Gemini e 6 de 166 do ChatGPT foram
    geradas DUAS vezes (e 5 respondidas viraram "falhou" depois).
    """
    caixa = _ia(caixa)
    if caixa not in GERADORES and caixa != LIVRE:
        raise CorreioInvalido(f"{ROTULOS.get(caixa, caixa)} não gera imagem")
    prompt = str(prompt or "").strip()
    if not prompt:
        raise CorreioInvalido("o pedido de imagem está vazio")
    if len(prompt) > PROMPT_IMAGEM_MAX:
        raise CorreioInvalido(
            f"prompt longo demais ({len(prompt)} > {PROMPT_IMAGEM_MAX} caracteres)")
    proporcao = str(proporcao or "").strip()
    if not proporcao or len(proporcao) > 12:
        raise CorreioInvalido("diga a proporção (ex.: 1:1)")
    caminhos = []
    for anexo in anexos or ():
        p = Path(anexo)
        if not p.is_file():
            raise CorreioInvalido(f"anexo nao existe: {p}")
        if p.suffix.lower() not in EXTENSOES_DE_ANEXO:
            raise CorreioInvalido(f"anexo tem de ser imagem ({', '.join(EXTENSOES_DE_ANEXO)})")
        if p.stat().st_size <= 0 or p.stat().st_size > ANEXO_MAX_BYTES:
            raise CorreioInvalido("anexo vazio ou maior que 8 MB")
        caminhos.append(str(p))
    mensagem = {
        "id": str(mensagem_id or novo_id()), "em": agora(), "de": str(de or "adrian")[:40],
        "para": caixa, "thread": thread_da_casa(caixa), "tipo": "imagem",
        "texto": prompt, "proporcao": proporcao,
        "modelo_pedido": (str(modelo)[:60] if modelo else None),
        "gerador": None if caixa == LIVRE else caixa,
        "anexos": caminhos, "situacao": "pendente", "resposta": None,
        "erro": None, "categoria": None, "nota": None, "imagem": None,
    }
    if dono:
        mensagem["dono"] = int(dono)
        mensagem["reservado_em"] = mensagem["em"]
    _anexar_linha(arquivo(caixa), mensagem)
    return dict(mensagem, atualizado_em=mensagem["em"])


def atualizar(ia: str, mensagem_id: str, **campos) -> dict:
    """Acrescenta um delta a mensagem (situacao, resposta, erro, nota...).

    Le, confere que a mensagem existe e escreve SOB A MESMA TRAVA (IAS-10,
    11/10/2026): antes o delta de um id inexistente ia ao arquivo e so depois
    subia `CorreioInvalido`, deixando uma linha ilegivel para sempre."""
    ia = _ia(ia)
    situacao = campos.get("situacao")
    if situacao is not None and situacao not in SITUACOES:
        raise CorreioInvalido(f"situacao {situacao!r} fora de {SITUACOES}")
    if "resposta" in campos and campos["resposta"] is not None:
        campos["resposta"] = str(campos["resposta"])
    mid = str(mensagem_id)
    alvo = arquivo(ia)
    with _trancado(alvo):
        try:
            with open(alvo, encoding="utf-8", errors="replace") as fh:
                linhas = fh.readlines()
        except OSError:
            linhas = []
        mensagens, _ = _dobrar(linhas)
        achado = next((m for m in mensagens if m["id"] == mid), None)
        if achado is None:
            raise CorreioInvalido(f"mensagem {mensagem_id} nao existe na caixa de {ia}")
        delta = {"id": mid, "em": agora(), **campos}
        with open(alvo, "ab") as fh:
            fh.write((json.dumps(delta, ensure_ascii=False) + "\n").encode("utf-8"))
            fh.flush()
    # o mesmo dobrar de `_dobrar`: toda chave do delta, menos id e em
    achado.update({k: v for k, v in delta.items() if k not in ("id", "em")})
    achado["atualizado_em"] = delta["em"]
    return achado


def marcar_vistas(ia: str) -> int:
    """As respondidas/falhadas ainda nao vistas ganham `visto`. Quantas."""
    ia = _ia(ia)
    quantas = 0
    for m in ler(ia):
        if m["situacao"] in ("respondida", "falhou") and not m.get("visto"):
            _anexar_linha(arquivo(ia), {"id": m["id"], "em": agora(), "visto": True})
            quantas += 1
    return quantas


# ---------------------------------------------------------------- leitura
def _dobrar(linhas) -> tuple[list, int]:
    """[mensagens na ordem de chegada], ilegiveis."""
    por_id: dict[str, dict] = {}
    ordem: list[str] = []
    ilegiveis = 0
    for bruta in linhas:
        bruta = bruta.strip()
        if not bruta:
            continue
        try:
            dados = json.loads(bruta)
        except ValueError:
            ilegiveis += 1
            continue
        if not isinstance(dados, dict) or not dados.get("id"):
            ilegiveis += 1
            continue
        mid = str(dados["id"])
        if mid not in por_id:
            if "texto" not in dados:
                ilegiveis += 1      # delta de uma mensagem que nao existe
                continue
            por_id[mid] = dict(dados)
            por_id[mid]["atualizado_em"] = dados.get("em")
            ordem.append(mid)
            continue
        alvo = por_id[mid]
        quando = dados.get("em")
        for chave, valor in dados.items():
            if chave in ("id", "em"):
                continue
            alvo[chave] = valor
        if quando:
            alvo["atualizado_em"] = quando
    saida = []
    for mid in ordem:
        m = por_id[mid]
        m.setdefault("situacao", "pendente")
        m.setdefault("resposta", None)
        m.setdefault("erro", None)
        m.setdefault("anexos", [])
        saida.append(m)
    return saida, ilegiveis


def ler(ia: str) -> list:
    """Todas as mensagens da caixa, dobradas. `[]` no caso ZERO."""
    alvo = arquivo(_ia(ia))
    try:
        with open(alvo, encoding="utf-8", errors="replace") as fh:
            linhas = fh.readlines()
    except OSError:
        return []
    mensagens, _ = _dobrar(linhas)
    return mensagens


def ilegiveis(ia: str) -> int:
    alvo = arquivo(_ia(ia))
    try:
        with open(alvo, encoding="utf-8", errors="replace") as fh:
            return _dobrar(fh.readlines())[1]
    except OSError:
        return 0


def historico(ia: str, n: int = 50) -> list:
    """As ultimas `n` mensagens, da mais velha para a mais nova."""
    todas = ler(ia)
    return todas[-max(0, int(n)):] if n else todas


def uma(ia: str, mensagem_id: str) -> dict | None:
    for m in ler(ia):
        if m["id"] == str(mensagem_id):
            return m
    return None


def pendentes(ia: str, *, so_livres: bool = False) -> list:
    """As pendentes da caixa. `so_livres`: sem as reservadas por OUTRO
    processo vivo nem as abandonadas (o que o carteiro pode entregar)."""
    saida = [m for m in ler(ia) if m["situacao"] == "pendente"]
    if so_livres:
        saida = [m for m in saida if not reservado_por_outro(m) and not abandonada(m)]
    return saida


# ------------------------------------------------------------- reserva
# Quanto tempo uma reserva (`dono`) vale sem o dono entregar: depois disso o
# PID pode ser de outro processo (o Windows reusa PID).
RESERVA_MAX_S = 4 * 3600.0


def _pid_do_campo(mensagem: dict, campo: str) -> int | None:
    try:
        numero = int((mensagem or {}).get(campo) or 0)
    except (TypeError, ValueError):
        return None
    return numero or None


def _dono(mensagem: dict) -> int | None:
    """Quem PEDIU e reservou (`pedir_imagem(dono=...)`). So vale com
    `reservado_em`: ate a conferencia de 05/10/2026 o `reivindicar` gravava
    o PID de quem ENTREGA no mesmo campo, e uma mensagem do Adrian que voltou
    a `pendente` (a rede caiu) com o carteiro religado virava "abandonada"
    (falhou em silencio, com motivo falso)."""
    if not (mensagem or {}).get("reservado_em"):
        return None
    return _pid_do_campo(mensagem, "dono")


def _entregador(mensagem: dict) -> int | None:
    """Quem ESTA entregando (`reivindicar`). Linha antiga sem `entregador`:
    o `dono` gravado pelo reivindicar de antes."""
    return _pid_do_campo(mensagem, "entregador") or _pid_do_campo(mensagem, "dono")


def _idade_da_reserva(mensagem: dict, agora_s: float | None = None) -> float | None:
    quando = (mensagem or {}).get("reservado_em")
    try:
        inicio = datetime.fromisoformat(str(quando)).timestamp()
    except (TypeError, ValueError):
        return None
    return (time.time() if agora_s is None else agora_s) - inicio


def reservado_por_outro(mensagem: dict, pid: int | None = None,
                        agora_s: float | None = None) -> bool:
    """O pedido esta reservado (`dono` + `reservado_em`) para OUTRO processo
    que ainda existe (ou que nao da para saber), dentro de `RESERVA_MAX_S`?"""
    dono = _dono(mensagem)
    if dono is None or dono == (os.getpid() if pid is None else int(pid)):
        return False
    idade = _idade_da_reserva(mensagem, agora_s)
    if idade is not None and idade > RESERVA_MAX_S:
        return False
    return _pid_vivo(dono) is not False


def abandonada(mensagem: dict, pid: int | None = None) -> bool:
    """Pendente RESERVADA (`pedir_imagem(dono=...)`) por um processo que
    MORREU antes de entregar: quem pediu nao vai mais ler a resposta (nao vale
    gastar a conta com ela). Mensagem sem reserva (as do Adrian) nunca e
    abandonada, nem depois de um carteiro que a entregava morrer."""
    dono = _dono(mensagem)
    if dono is None or dono == (os.getpid() if pid is None else int(pid)):
        return False
    if (mensagem or {}).get("situacao", "pendente") != "pendente":
        return False
    return _pid_vivo(dono) is False


def reivindicar(ia: str, mensagem_id: str, *, pid: int | None = None, **campos) -> dict | None:
    """Passa a mensagem de `pendente` para `entregue` (com `entregador` =
    este processo) ATOMICAMENTE: lido e escrito sob a trava do arquivo.
    Devolve a mensagem atualizada, ou None se ela ja nao e de ninguem entregar
    (outro carteiro a pegou, ela ja foi respondida/falhou, ou e reservada por
    outro processo vivo). Quem ja entrega uma `entregue` (a recuperacao
    depois de o Chrome cair) reivindica de novo. O `dono` (a reserva de quem
    pediu) nao e tocado."""
    ia = _ia(ia)
    meu = os.getpid() if pid is None else int(pid)
    alvo = arquivo(ia)
    with _trancado(alvo):
        try:
            with open(alvo, encoding="utf-8", errors="replace") as fh:
                linhas = fh.readlines()
        except OSError:
            return None
        mensagens, _ = _dobrar(linhas)
        m = next((x for x in mensagens if x["id"] == str(mensagem_id)), None)
        if m is None:
            return None
        situacao = m.get("situacao")
        livre = situacao == "pendente" and not reservado_por_outro(m, meu)
        retomada = situacao == "entregue" and _entregador(m) == meu
        if not (livre or retomada):
            return None
        quando = agora()
        delta = {"id": str(mensagem_id), "em": quando, "situacao": "entregue",
                 "entregue_em": quando, "entregador": meu, "nota": None, **campos}
        with open(alvo, "ab") as fh:
            fh.write((json.dumps(delta, ensure_ascii=False) + "\n").encode("utf-8"))
            fh.flush()
    m.update({k: v for k, v in delta.items() if k not in ("id", "em")})
    m["atualizado_em"] = quando
    return m


def proxima_pendente(ias=CHATS, *, so_livres: bool = False) -> dict | None:
    """A mensagem pendente mais velha, entre todas as caixas."""
    candidatas = []
    for ia in ias:
        candidatas.extend(pendentes(ia, so_livres=so_livres))
    if not candidatas:
        return None
    return min(candidatas, key=lambda m: (str(m.get("em") or ""), m["id"]))


def pendentes_de_texto(ia: str) -> list:
    return [m for m in pendentes(ia) if tipo(m) == "texto"]


def resumo(ias=CHATS) -> dict:
    """{ia: {rotulo, emoji, pendentes, em_andamento, nao_vistas, ultima, total}}."""
    saida = {}
    for ia in ias:
        mensagens = ler(ia)
        saida[ia] = {
            "rotulo": ROTULOS.get(ia, ia), "emoji": EMOJIS.get(ia, "•"),
            "total": len(mensagens),
            "pendentes": sum(1 for m in mensagens if m["situacao"] == "pendente"),
            "em_andamento": sum(1 for m in mensagens if m["situacao"] == "entregue"),
            "nao_vistas": sum(1 for m in mensagens
                              if m["situacao"] in ("respondida", "falhou")
                              and not m.get("visto")),
            "ultima": mensagens[-1] if mensagens else None,
            "ilegiveis": ilegiveis(ia),
        }
    return saida


# ------------------------------------------------------------------ anexos
def guardar_anexo(ia: str, nome: str, conteudo: bytes) -> Path:
    """Grava um anexo (imagem) na pasta da IA e devolve o caminho."""
    ia = _ia(ia)
    limpo = "".join(c if c.isalnum() or c in "._-" else "_" for c in str(nome or ""))[:60]
    ext = Path(limpo).suffix.lower()
    if ext not in EXTENSOES_DE_ANEXO:
        raise CorreioInvalido(f"anexo tem de ser imagem ({', '.join(EXTENSOES_DE_ANEXO)})")
    if not conteudo or len(conteudo) > ANEXO_MAX_BYTES:
        raise CorreioInvalido("anexo vazio ou maior que 8 MB")
    destino = pasta(ia) / "anexos" / f"{datetime.now():%Y%m%d_%H%M%S}_{secrets.token_hex(2)}_{limpo}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    tmp.write_bytes(conteudo)
    os.replace(tmp, destino)
    return destino


# ----------------------------------------------------------------- imagens
# Uma imagem gerada mora em `<raiz>/<gerador>/imagens/<id>.<ext>`, com os
# BYTES ORIGINAIS (sem recomprimir) e `<id>.prova.json` ao lado. O nome sai
# SO do id da mensagem e da extensao lida dos bytes: nada vindo do celular.
_NOME_DA_IMAGEM = re.compile(r"^([0-9a-f]{8})\.(png|jpg|webp)$")


def pasta_imagens(gerador: str) -> Path:
    gerador = _ia(gerador)
    if gerador not in GERADORES:
        raise CorreioInvalido(f"{gerador} não gera imagem")
    return pasta(gerador) / "imagens"


def arquivo_da_imagem(caixa: str, mensagem_id: str) -> Path | None:
    """O arquivo da imagem de um pedido REGISTRADO e respondido, ou None.

    Tudo vem do registro: a caixa, o id, o gerador que a mensagem diz e o
    nome que o carteiro gravou (que tem de ser `<id>.<ext>`). O caminho final
    tem de morar dentro da pasta de imagens daquele gerador.
    """
    try:
        m = uma(caixa, mensagem_id)
    except CorreioInvalido:
        return None
    # o pedido pelo Criar, ou uma CONVERSA cuja resposta foi uma imagem
    if m is None or m.get("situacao") != "respondida":
        return None
    info = m.get("imagem") if isinstance(m.get("imagem"), dict) else {}
    nome = str(info.get("arquivo") or "")
    achado = _NOME_DA_IMAGEM.fullmatch(nome)
    if not achado or achado.group(1) != str(m["id"]):
        return None
    gerador = str(m.get("gerador") or (m.get("para") if tipo(m) == "texto" else "") or "")
    if gerador not in GERADORES:
        return None
    base = pasta_imagens(gerador)
    alvo = base / nome
    try:
        if alvo.resolve().parent != base.resolve() or not alvo.is_file():
            return None
    except OSError:
        return None
    return alvo


def imagens(gerador: str | None = None, n: int = 60) -> list:
    """A GALERIA: os pedidos de imagem respondidos (de todas as caixas), do
    mais novo para o mais velho; com `gerador`, so os dele."""
    saida = []
    for caixa in CAIXAS:
        for m in ler(caixa):
            if m.get("situacao") != "respondida" or not isinstance(m.get("imagem"), dict):
                continue
            if gerador and (m.get("gerador") or m.get("para")) != gerador:
                continue
            saida.append(dict(m, caixa=caixa))
    saida.sort(key=lambda m: str(m.get("respondida_em") or m.get("em") or ""),
               reverse=True)
    return saida[:max(0, int(n))] if n else saida


# -------------------------------------------------------------------- casa
def casa_vazia(ia: str) -> dict:
    return {"ia": _ia(ia), "url": None, "geracao": 0, "aberta_em": None,
            "mensagens": 0, "resumo_mensagens": 0, "ultimo_resumo_em": None,
            "falhas_seguidas": 0}


def casa(ia: str) -> dict:
    alvo = pasta(_ia(ia)) / "casa.json"
    base = casa_vazia(ia)
    try:
        with open(alvo, encoding="utf-8") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return base
    if not isinstance(dados, dict):
        return base
    base.update(dados)
    return base


SUBSTITUIR_TENTATIVAS = 6
SUBSTITUIR_PAUSA_S = 0.15


def _substituir(tmp: Path, alvo: Path) -> None:
    """`os.replace` que aguenta o arquivo aberto por outro processo.

    No Windows, trocar um `casa.json` que o app (ou outro carteiro) esta
    lendo da `PermissionError`; ate 14/10/2026 isso fazia a resposta ja
    obtida virar "falhou" (IAS-5). Tenta `SUBSTITUIR_TENTATIVAS` vezes."""
    for tentativa in range(1, SUBSTITUIR_TENTATIVAS + 1):
        try:
            os.replace(tmp, alvo)
            return
        except PermissionError:
            if tentativa >= SUBSTITUIR_TENTATIVAS:
                raise
            time.sleep(SUBSTITUIR_PAUSA_S)


def gravar_casa(ia: str, dados: dict) -> Path:
    alvo = pasta(_ia(ia)) / "casa.json"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    tmp = alvo.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    _substituir(tmp, alvo)
    return alvo


def resumo_da_casa(ia: str) -> str:
    alvo = pasta(_ia(ia)) / "casa_resumo.md"
    try:
        return alvo.read_text(encoding="utf-8")
    except OSError:
        return ""


def idade_do_resumo_da_casa(ia: str, agora_s: float | None = None) -> float | None:
    """Ha quantos segundos o `casa_resumo.md` foi gravado (None: nao ha)."""
    alvo = pasta(_ia(ia)) / "casa_resumo.md"
    try:
        gravado = alvo.stat().st_mtime
    except OSError:
        return None
    return (time.time() if agora_s is None else agora_s) - gravado


def gravar_resumo_da_casa(ia: str, texto: str) -> Path:
    alvo = pasta(_ia(ia)) / "casa_resumo.md"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    cabecalho = (f"# Resumo da casa do {ROTULOS.get(_ia(ia), ia)} — {agora()}\n\n")
    tmp = alvo.with_suffix(".tmp")
    tmp.write_text(cabecalho + str(texto).strip() + "\n", encoding="utf-8")
    _substituir(tmp, alvo)
    return alvo


# ----------------------------------------------------------- o carteiro
def _pid_vivo(pid) -> bool | None:
    try:
        from builds.atividade import _vivo
        return _vivo(pid)
    except Exception:                                          # noqa: BLE001
        pass
    try:
        numero = int(pid)
    except (TypeError, ValueError):
        return None
    if numero <= 0:
        return None
    if os.name == "nt":
        # NUNCA os.kill no Windows: la `os.kill(pid, 0)` chama TerminateProcess
        # e MATARIA o worker das historias (esta funcao roda a cada volta do
        # carteiro contra o PID dele). OpenProcess so pergunta.
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, numero)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False if kernel32.GetLastError() == 87 else None   # 87 = sumiu
        except Exception:                                      # noqa: BLE001
            return None
    try:
        os.kill(numero, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return None


def gravar_estado_do_carteiro(dados: dict) -> None:
    alvo = raiz() / "carteiro.json"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    dados = dict(dados, pid=os.getpid(), pulso_em=agora())
    tmp = alvo.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    _substituir(tmp, alvo)


def estado_do_carteiro(agora_s: float | None = None) -> dict:
    """O que o carteiro disse por ultimo, e se ele ainda existe.

    `vivo`: True/False/None (o PID e conferido; None = nao da para saber).
    `situacao`: ocioso, entregando, esperando_trava, resumindo, parado ou
    `nunca` (caso ZERO: nenhum carteiro escreveu ainda).
    """
    alvo = raiz() / "carteiro.json"
    try:
        with open(alvo, encoding="utf-8") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return {"situacao": "nunca", "vivo": None, "pulso_em": None,
                "pulso_ha_s": None, "ia": None, "mensagem_id": None, "desde": None}
    if not isinstance(dados, dict):
        dados = {}
    vivo = _pid_vivo(dados.get("pid"))
    try:
        pulso = datetime.fromisoformat(str(dados.get("pulso_em"))).timestamp()
        ha = (time.time() if agora_s is None else agora_s) - pulso
    except (TypeError, ValueError):
        ha = None
    situacao = str(dados.get("situacao") or "ocioso")
    if vivo is False or (ha is not None and ha > 15 * 60):
        situacao = "parado"
    return {"situacao": situacao, "vivo": vivo, "pulso_em": dados.get("pulso_em"),
            "pulso_ha_s": None if ha is None else round(ha, 1),
            "ia": dados.get("ia"), "mensagem_id": dados.get("mensagem_id"),
            "desde": dados.get("desde"), "pid": dados.get("pid"),
            "nota": dados.get("nota") or ""}


# ------------------------------------------------------------- presenca
def registrar_presenca(chave: str) -> None:
    """O app pediu esta caixa agora (o servidor chama; o carteiro le)."""
    alvo = raiz() / "presenca.json"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _trancado(alvo, esperar=2.0):
            try:
                dados = json.loads(alvo.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                dados = {}
            if not isinstance(dados, dict):
                dados = {}
            dados[str(chave)] = agora()
            tmp = alvo.with_suffix(".tmp")
            tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
            _substituir(tmp, alvo)
    except OSError:
        pass


def app_esta_olhando(ia: str, janela_s: float = PRESENCA_S,
                     agora_s: float | None = None) -> bool:
    """O app pediu a caixa desta IA ha menos de `janela_s`?"""
    alvo = raiz() / "presenca.json"
    try:
        dados = json.loads(alvo.read_text(encoding="utf-8"))
        quando = datetime.fromisoformat(str(dados.get(f"correio:{_ia(ia)}"))).timestamp()
    except (OSError, ValueError, TypeError, AttributeError):
        return False
    return ((time.time() if agora_s is None else agora_s) - quando) <= float(janela_s)


__all__ = ["CHATS", "GERADORES", "LIVRE", "CAIXAS", "ROTULOS", "EMOJIS", "SITUACOES",
           "CorreioInvalido", "enviar", "pedir_imagem", "tipo", "pendentes_de_texto",
           "pasta_imagens", "arquivo_da_imagem", "imagens", "atualizar", "marcar_vistas", "ler", "historico", "uma",
           "pendentes", "proxima_pendente", "resumo", "guardar_anexo", "casa",
           "reivindicar", "reservado_por_outro", "abandonada", "RESERVA_MAX_S",
           "gravar_casa", "resumo_da_casa", "gravar_resumo_da_casa", "idade_do_resumo_da_casa",
           "estado_do_carteiro", "gravar_estado_do_carteiro",
           "registrar_presenca", "app_esta_olhando", "raiz", "pasta", "arquivo"]
