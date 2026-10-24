# -*- coding: utf-8 -*-
"""Cliente minimo da API do Telegram — so `urllib`, nenhuma dependencia.

Poderia ser `python-telegram-bot`, mas isso traria um pacote (e as
atualizacoes dele) para dentro de um projeto que hoje roda com o que ja
existe na maquina. A API do bot e HTTP + JSON: cabe em cem linhas.

O que importa aqui:

  LONG POLLING. `getUpdates` fica pendurado ate `timeout` segundos esperando
  mensagem. E isso que faz o bot responder na hora sem ficar batendo no
  servidor — e, principalmente, e uma conexao de DENTRO para FORA: nenhuma
  porta aberta na maquina do Adrian, que guarda contas logadas.

  NUNCA LEVANTAR POR REDE. Wi-Fi cai, o Telegram tem instabilidade. Um erro
  de rede nao pode derrubar o bot; ele devolve vazio e a proxima volta tenta
  de novo.
"""
from __future__ import annotations

import json
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.telegram.org/bot{token}/{metodo}"
# O upload de bot para no meio dos 50 MB. Cortar antes e mais honesto do que
# tentar e receber um erro cru do servidor.
LIMITE_ARQUIVO_MB = 45


# O Telegram diz exatamente isto quando o Markdown nao fecha. Casar pela
# frase, e nao so pelo 400: um 400 tambem pode ser chat errado ou texto vazio,
# e reenviar sem formatacao nao conserta nenhum dos dois.
FALHAS_DE_FORMATACAO = ("can't parse entities", "can't find end of the entity",
                        "unsupported start tag")


def _e_erro_de_formatacao(resposta: dict) -> bool:
    motivo = str((resposta or {}).get("description") or "").lower()
    return any(sinal in motivo for sinal in FALHAS_DE_FORMATACAO)


# Folga sob os 4096 do Telegram. O teto do Telegram conta UNIDADES UTF-16,
# nao caracteres do Python: emoji fora do plano basico (🟢, 📏) vale 2. 110
# linhas com 🟢 davam 3.999 caracteres e 4.099 unidades (conferente, 21/10).
LIMITE_DA_MENSAGEM = 4000
# Recusa DEFINITIVA da mesma parte (4xx que nao e 429 nem de formatacao) ate
# a parte ser pulada. Falta de rede nao conta: aquilo volta.
TETO_DE_TENTATIVAS = 3
# Entregas pela metade lembradas (por chat e texto), e por quanto tempo.
MEMORIA_MAXIMA = 50
MEMORIA_S = 30 * 60


def unidades(texto: str) -> int:
    """O tamanho como o Telegram conta: unidades UTF-16."""
    return len(str(texto).encode("utf-16-le")) // 2


def _cabe(linha: str, limite: int) -> int:
    """Quantos caracteres do comeco de `linha` cabem em `limite` unidades
    (sem partir um emoji ao meio). Pelo menos 1."""
    total = 0
    for i, ch in enumerate(linha):
        total += 2 if ord(ch) > 0xFFFF else 1
        if total > limite:
            return max(1, i)
    return len(linha)


def partes_da_mensagem(texto: str, limite: int = LIMITE_DA_MENSAGEM) -> list:
    """O texto em pedacos de ate `limite` UNIDADES UTF-16, quebrados em FIM
    DE LINHA.

    Nada se perde: juntar as partes com "\\n" devolve o texto (so a linha
    sozinha maior que o limite e quebrada no meio, e parte feita so de
    espaco nao vai — o Telegram recusa texto vazio). Texto curto = uma
    parte. Texto vazio = `[""]` (o envio decide o que fazer, como antes)."""
    texto = str(texto if texto is not None else "")
    if unidades(texto) <= limite:
        return [texto]
    partes, atual, tamanho = [], None, 0
    for linha in texto.split("\n"):
        while unidades(linha) > limite:
            if atual is not None:
                partes.append(atual)
                atual = None
            corte = _cabe(linha, limite)
            partes.append(linha[:corte])
            linha = linha[corte:]
        n = unidades(linha)
        if atual is None:
            atual, tamanho = linha, n
        elif tamanho + 1 + n <= limite:
            atual += "\n" + linha
            tamanho += 1 + n
        else:
            partes.append(atual)
            atual, tamanho = linha, n
    if atual is not None:
        partes.append(atual)
    return [p for p in partes if p.strip()] or [texto[:_cabe(texto, limite)]]


def chegou_algo(resposta: dict) -> bool:
    """A mensagem chegou, ao menos em parte? Entrega PELA METADE conta como
    entregue para quem tem fila: o que falta vai em `resposta["resto"]`, e e
    so ele que se enfileira (reenfileirar o texto inteiro repetia a parte 1)."""
    if not isinstance(resposta, dict):
        return bool(resposta and resposta.get("ok"))
    return bool(resposta.get("ok") or resposta.get("partes_enviadas"))


def _recusa_definitiva(resposta: dict) -> bool:
    """O Telegram respondeu e disse NAO de um jeito que repetir nao conserta.
    `{}` (sem rede), 429 (devagar) e 5xx voltam; 4xx fica."""
    codigo = (resposta or {}).get("error_code")
    return isinstance(codigo, int) and 400 <= codigo < 500 and codigo != 429


class Telegram:
    def __init__(self, token: str, *, abrir=None):
        self.token = token
        # injetavel para o teste nao tocar a rede
        self._abrir = abrir or urllib.request.urlopen
        # (chat, texto) -> {"feitas", "falhas", "puladas", "em"}: a entrega
        # PELA METADE de um texto longo. Quem chama reenvia o texto inteiro
        # (relatorio, alerta, fila); daqui sai so o que ainda nao chegou.
        self._pela_metade: dict = {}

    # ------------------------------------------------------------- interno
    def _url(self, metodo: str) -> str:
        return BASE.format(token=self.token, metodo=metodo)

    def chamar(self, metodo: str, **campos) -> dict:
        """POST simples (form-urlencoded). {} quando a rede falha.

        O CORPO DO 400 TAMBEM VOLTA. Ate 11/09/2026 qualquer erro virava `{}`,
        e o Telegram poe o motivo real no corpo de um 400 — foi assim que
        "can't parse entities" ficou meses invisivel.
        """
        dados = urllib.parse.urlencode(
            {k: v for k, v in campos.items() if v is not None}).encode()
        try:
            with self._abrir(self._url(metodo), data=dados, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as erro:
            try:
                return json.loads(erro.read().decode("utf-8", "replace"))
            except Exception:                                  # noqa: BLE001
                return {"ok": False, "error_code": erro.code}
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return {}

    # -------------------------------------------------------------- enviar
    def mensagem(self, chat_id, texto: str, *, markdown: bool = False) -> dict:
        """Manda o texto. O CONTEUDO chega mesmo quando a formatacao nao dá.

        DEFEITO ACHADO EM 11/09/2026, e ele calava o canal inteiro: o bot
        manda tudo com `parse_mode=Markdown`, e o Markdown legado do Telegram
        trata `_` e `*` como formatacao. Todo id deste projeto tem underscore
        (`historia_00004`, `p04_cena_02`, `generation_00055`), entao os tres
        relatorios voltavam

            400 Bad Request: can't parse entities

        e nada era entregue. Nao havia erro no log, nao havia excecao: a
        funcao devolvia `{}` e quem chamou seguiu em frente. Os relatorios de
        metas e funcionamento — os que existem justamente para avisar quando
        algo quebra — eram os que mais escapavam, porque listam ids.

        Reenviar SEM formatacao e a escolha certa: negrito e enfeite, a lista
        de videos barrados nao. Escapar os `_` seria a outra saida, e ela e
        pior — depende de quem escreve o relatorio lembrar de escapar, e o
        proximo relatorio vai esquecer de novo.
        """
        # 4096 e o teto do Telegram. Ate 21/10/2026 o texto era CORTADO em
        # 4000 — e o que morava no fim sumia calado (a medida da semana cheia
        # perdia o TikTok e todo aviso "!"). Agora o texto longo vai em
        # PARTES, quebradas em fim de linha; so uma linha sozinha maior que o
        # teto e quebrada no meio.
        #
        # RETOMADA (conferente, 21/10): quem chama reenvia o texto INTEIRO
        # quando a resposta nao e ok, a cada volta do laco. Sem memoria, a
        # parte 1 chegava de novo a cada volta (~120 vezes por hora com a
        # parte 2 recusada para sempre). Agora a parte que ja chegou nao vai
        # de novo; a recusa definitiva da mesma parte conta tentativa, e na
        # `TETO_DE_TENTATIVAS` ela e PULADA (o resto segue) e a resposta diz
        # `parcial` — nunca "tudo certo" calado.
        partes = partes_da_mensagem(texto)
        if len(partes) == 1:
            return self._uma_parte(chat_id, partes[0], markdown)
        chave = (str(chat_id), str(texto))
        agora = time.monotonic()
        self._esquecer_velhas(agora)
        estado = self._pela_metade.get(chave) or {"feitas": 0, "falhas": 0,
                                                  "puladas": [], "em": agora}
        # `em` NAO e renovado: a memoria vale MEMORIA_S desde a PRIMEIRA falha.
        # Renovar fazia o mesmo texto reenviado de proposito (o /semana das
        # 21:05, o alerta que o porteiro libera um dia depois) pular as
        # primeiras partes e responder ok (conferente, 24/10).
        resposta: dict = {}
        while estado["feitas"] < len(partes):
            i = estado["feitas"]
            resposta = self._uma_parte(chat_id, partes[i], markdown)
            if resposta.get("ok"):
                estado["feitas"], estado["falhas"] = i + 1, 0
                continue
            if _recusa_definitiva(resposta):
                estado["falhas"] += 1
                if estado["falhas"] >= TETO_DE_TENTATIVAS:
                    estado["puladas"].append(i + 1)
                    estado["feitas"], estado["falhas"] = i + 1, 0
                    continue
            self._pela_metade[chave] = estado
            return {**resposta, "ok": False, "partes": len(partes),
                    "partes_enviadas": i, "puladas": list(estado["puladas"]),
                    "resto": "\n".join(partes[i:])}
        self._pela_metade.pop(chave, None)
        saida = {**resposta, "ok": True, "partes": len(partes),
                 "partes_enviadas": len(partes) - len(estado["puladas"])}
        if estado["puladas"]:
            saida.update(parcial=True, puladas=list(estado["puladas"]),
                         description=f"partes {estado['puladas']} de {len(partes)} "
                                     f"recusadas {TETO_DE_TENTATIVAS}x e puladas")
        return saida

    def _uma_parte(self, chat_id, corpo: str, markdown: bool) -> dict:
        resposta = self.chamar("sendMessage", chat_id=chat_id, text=corpo,
                               parse_mode="Markdown" if markdown else None,
                               disable_web_page_preview="true")
        if markdown and not resposta.get("ok") and _e_erro_de_formatacao(resposta):
            resposta = self.chamar("sendMessage", chat_id=chat_id, text=corpo,
                                   disable_web_page_preview="true")
        return resposta

    def assumir_resto(self, chat_id, texto: str) -> None:
        """Quem chamou ja enfileirou o `resto`: a memoria desta entrega pela
        metade acaba AGORA (um envio novo do mesmo texto manda tudo)."""
        self._pela_metade.pop((str(chat_id), str(texto)), None)

    def _esquecer_velhas(self, agora: float) -> None:
        for chave in [k for k, v in self._pela_metade.items() if agora - v["em"] > MEMORIA_S]:
            self._pela_metade.pop(chave, None)
        while len(self._pela_metade) >= MEMORIA_MAXIMA:
            self._pela_metade.pop(min(self._pela_metade, key=lambda k: self._pela_metade[k]["em"]))

    def arquivo(self, chat_id, caminho, *, legenda: str = "",
                como_video: bool = True) -> dict:
        """Manda o mp4 para o celular. E o que permite ASSISTIR antes de publicar."""
        caminho = Path(caminho)
        if not caminho.is_file():
            return {"ok": False, "description": "arquivo nao existe"}
        mb = caminho.stat().st_size / 1e6
        if mb > LIMITE_ARQUIVO_MB:
            return {"ok": False,
                    "description": f"{mb:.0f} MB — acima do limite de "
                                   f"{LIMITE_ARQUIVO_MB} MB do Telegram"}
        metodo = "sendVideo" if como_video else "sendDocument"
        campo = "video" if como_video else "document"
        corpo, tipo = _multipart({"chat_id": str(chat_id),
                                  "caption": legenda[:1000]},
                                 campo, caminho)
        pedido = urllib.request.Request(self._url(metodo), data=corpo,
                                        headers={"Content-Type": tipo})
        try:
            with self._abrir(pedido, timeout=300) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
            return {"ok": False, "description": str(exc)}

    # -------------------------------------------------------------- receber
    def novidades(self, desde: int | None = None, timeout: int = 30) -> list | None:
        """As mensagens novas: lista (vazia quando nao ha nada), ou None quando
        a rede caiu (o `chamar` devolveu `{}`).

        A diferenca importa (APP-9, 14/10): sem rede o `chamar` volta NA HORA,
        e o laco do bot, sem saber, girava ~2.700 voltas por segundo
        remontando o relatorio vencido a cada uma.
        """
        resposta = self.chamar("getUpdates", offset=desde, timeout=timeout,
                               allowed_updates='["message"]')
        if not resposta:
            return None
        return resposta.get("result") or []

    def eu_bruto(self) -> dict:
        """A resposta inteira do `getMe`: `{}` = sem rede; `error_code` 401/404
        = token errado de verdade."""
        return self.chamar("getMe") or {}

    def eu(self) -> dict:
        return self.eu_bruto().get("result") or {}


def _multipart(campos: dict, nome_arquivo: str, caminho: Path) -> tuple:
    """Corpo multipart/form-data na mao (sem `requests` no projeto)."""
    limite = "----neuralfights7b2c1f"
    partes = []
    for chave, valor in campos.items():
        partes.append(f"--{limite}\r\n"
                      f'Content-Disposition: form-data; name="{chave}"\r\n\r\n'
                      f"{valor}\r\n".encode("utf-8"))
    tipo = mimetypes.guess_type(caminho.name)[0] or "application/octet-stream"
    partes.append(
        f"--{limite}\r\n"
        f'Content-Disposition: form-data; name="{nome_arquivo}"; '
        f'filename="{caminho.name}"\r\n'
        f"Content-Type: {tipo}\r\n\r\n".encode("utf-8"))
    partes.append(caminho.read_bytes())
    partes.append(f"\r\n--{limite}--\r\n".encode("utf-8"))
    return b"".join(partes), f"multipart/form-data; boundary={limite}"
