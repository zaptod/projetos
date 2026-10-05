# -*- coding: utf-8 -*-
"""O app do celular esta alcancavel pelo tailnet? A vigia que faltou.

POR QUE EXISTE. Em 28/09/2026 o PC foi desligado pelo botao (codigo 0x500ff)
e religado as 07:22. O cliente da bandeja do Tailscale (`tailscale-ipn.exe`,
aberto no logon pela pasta Inicializar) nao subiu, o `tailscaled` ficou em
`NoState`, e o `tailscale serve status` passou a dizer "No serve config". O
servidor do app seguia respondendo em 127.0.0.1:8931 — so que o celular nao o
alcancava, e NADA avisou: nem o bot, nem o app, nem o diario. Abrir o
`tailscale-ipn.exe` resolveu em 11 s, e o serve voltou sozinho, "tailnet
only".

O QUE ELA CONFERE, de tempos em tempos, dentro do laco do bot:
  - o backend do Tailscale esta `Running`;
  - o `serve` existe e aponta para o app (127.0.0.1:8931);
  - o `funnel` NAO esta ligado (a regra e "serve sim, funnel nunca").

O QUE ELA FAZ. Um aviso no Telegram por ocorrencia, e outro quando volta.
O UNICO conserto automatico e o de 28/09: abrir o cliente da bandeja quando
o backend esta parado e ele nao esta aberto (pelo `explorer.exe`, para ela
nao morrer junto com o bot; 05/10). Quando o Tailscale nao responde, ela nao
diz "fora": pergunta de novo e, depois de 3 olhadas seguidas sem resposta,
avisa "nao sei". Ela NUNCA roda `tailscale
funnel`, nunca mexe na configuracao do `serve` e nunca liga o modo
"unattended" (essa decisao e do Adrian). Os comandos que ela roda sao dois,
os dois de leitura: `status --json` e `serve status --json`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ALVO = "127.0.0.1:8931"
INTERVALO_S = 120.0
# Na subida do bot (logo depois de um boot) o Tailscale ainda pode estar
# conectando: a primeira olhada espera um pouco.
PRIMEIRA_OLHADA_S = 60.0
# Quanto esperar o Tailscale voltar depois de abrir a bandeja (em 28/09
# levou 11 s).
ESPERA_DO_CONSERTO_S = 30.0
PASSO_DA_ESPERA_S = 5.0
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DESLIGADO = (getattr(subprocess, "DETACHED_PROCESS", 0)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
FORA_DO_JOB = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
BANDEJA = "tailscale-ipn.exe"
REFAZER_SERVE = "tailscale serve --bg --https=443 http://127.0.0.1:8931"
# "Nao consegui perguntar" (o `tailscale status` falhou ou travou) NAO e "fora
# do tailnet": o app pode estar no ar. Varredura de 05/10/2026 (item 13): 4
# avisos "fora do tailnet: nao consegui perguntar o estado" entre 23:00 e
# 00:06 de 04/10, cada um depois de 2 olhadas. Agora a olhada sem resposta
# pergunta de novo na hora, e so vira aviso (com o texto "nao sei") depois de
# 3 olhadas seguidas sem resposta.
SEM_RESPOSTA_SEGUIDAS = 3


def _pasta_do_tailscale() -> Path:
    return Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tailscale"


def _tailscale_exe() -> str | None:
    achado = shutil.which("tailscale")
    if achado:
        return achado
    padrao = _pasta_do_tailscale() / "tailscale.exe"
    return str(padrao) if padrao.is_file() else None


def _bandeja_exe() -> str | None:
    caminho = _pasta_do_tailscale() / BANDEJA
    return str(caminho) if caminho.is_file() else None


def _explorer_exe() -> str | None:
    pasta = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows"
    caminho = Path(pasta) / "explorer.exe"
    return str(caminho) if caminho.is_file() else None


def _rodar(rodar, argumentos: list) -> str | None:
    """A saida do comando, ou None se ele nao rodou ou falhou."""
    try:
        feito = rodar(argumentos, capture_output=True, text=True,
                      encoding="utf-8", errors="replace", timeout=20,
                      creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if getattr(feito, "returncode", 1) != 0:
        return None
    return feito.stdout or ""


def _estado(exe: str, rodar) -> str | None:
    """`Running`, `NoState`, `Starting`... ou None se nao deu para perguntar."""
    saida = _rodar(rodar, [exe, "status", "--json"])
    if saida is None:
        return None
    try:
        return str(json.loads(saida).get("BackendState") or "") or None
    except (ValueError, AttributeError):
        return None


def _serve(exe: str, rodar) -> dict | None:
    """A configuracao do serve ({} se nao ha nenhuma), ou None se nao sei."""
    saida = _rodar(rodar, [exe, "serve", "status", "--json"])
    if saida is None:
        return None
    texto = saida.strip()
    if not texto or "no serve config" in texto.lower():
        return {}
    try:
        dados = json.loads(texto)
    except ValueError:
        return None
    return dados if isinstance(dados, dict) else None


def _aponta_para_o_app(serve: dict) -> bool:
    for site in (serve.get("Web") or {}).values():
        for rota in ((site or {}).get("Handlers") or {}).values():
            destino = str((rota or {}).get("Proxy") or "")
            if ALVO in destino or destino.endswith("localhost:8931"):
                return True
    return False


def _funnel_ligado(serve: dict) -> bool:
    return any(bool(v) for v in (serve.get("AllowFunnel") or {}).values())


def bandeja_aberta(rodar=subprocess.run) -> bool | None:
    """O `tailscale-ipn.exe` esta rodando? None = nao sei."""
    saida = _rodar(rodar, ["tasklist", "/FI", f"IMAGENAME eq {BANDEJA}",
                           "/FO", "CSV", "/NH"])
    if saida is None:
        return None
    return f'"{BANDEJA}"' in saida.lower()


def sondar(rodar=subprocess.run) -> dict:
    """{ok, motivo, estado, serve, funnel, bandeja}. Nunca levanta."""
    ficha = {"ok": False, "motivo": "", "estado": None, "serve": None,
             "funnel": False, "bandeja": None}
    exe = _tailscale_exe()
    if not exe:
        ficha["motivo"] = "não achei o tailscale.exe"
        return ficha
    ficha["estado"] = estado = _estado(exe, rodar)
    if estado is None:
        ficha["motivo"] = "não consegui perguntar o estado ao Tailscale"
        ficha["sem_resposta"] = True
        return ficha
    if estado != "Running":
        ficha["bandeja"] = aberta = bandeja_aberta(rodar)
        ficha["motivo"] = (f"o Tailscale está em {estado}"
                           + (" e o cliente da bandeja não está aberto"
                              if aberta is False else ""))
        return ficha
    serve = _serve(exe, rodar)
    ficha["serve"] = serve is not None and bool(serve)
    if serve is None:
        ficha["motivo"] = "não consegui ler a configuração do serve"
        ficha["sem_resposta"] = True
        return ficha
    if _funnel_ligado(serve):
        ficha["funnel"] = True
        ficha["motivo"] = "o FUNNEL está ligado: o app está aberto na internet"
        return ficha
    if not serve:
        ficha["motivo"] = "a configuração do serve sumiu"
        return ficha
    if not _aponta_para_o_app(serve):
        ficha["motivo"] = f"o serve não aponta para o app ({ALVO})"
        return ficha
    ficha["ok"] = True
    return ficha


def abrir_bandeja(popen=subprocess.Popen) -> str:
    """Abre o cliente da bandeja PELO EXPLORER. Devolve o que fez.

    Varredura de 05/10/2026 (item 13): aberta direto, a bandeja virava filha
    do bot (pid 9680 filho do 12780), e cada religada do bot pelo supervisor
    (`taskkill /t /f`, a arvore inteira) a matava junto: 1 a 2 min depois
    vinha o aviso de NoState (5 vezes em 03/10 e 5 em 04/10). Pelo
    `explorer.exe`, quem cria a bandeja e o shell do Windows, como no logon:
    ela fica fora da arvore e fora do job do bot. Sem explorer (ou se ele
    recusar), o caminho antigo: direto, tentando sair do job.
    """
    exe = _bandeja_exe()
    if not exe:
        return f"não achei o {BANDEJA} para abrir"
    comum = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, close_fds=True)
    explorer = _explorer_exe()
    if explorer:
        # O explorer so entrega o pedido ao shell e sai: mesmo preso ao job
        # do bot (o Agendador pode negar a saida), a bandeja nasce fora dele.
        for flags in (DESLIGADO | FORA_DO_JOB, DESLIGADO):
            try:
                popen([explorer, exe], creationflags=flags, **comum)
                return f"abri o {BANDEJA}"
            except OSError:
                continue
    try:
        try:
            popen([exe], creationflags=DESLIGADO | FORA_DO_JOB, **comum)
        except OSError:
            # O job do Agendador pode nao deixar sair; sem sair, a bandeja
            # vive enquanto a tarefa do bot viver, o que ainda e melhor.
            popen([exe], creationflags=DESLIGADO, **comum)
    except OSError as exc:
        return f"tentei abrir o {BANDEJA} e não consegui ({exc})"
    return f"abri o {BANDEJA}"


class Vigia:
    """Um aviso por ocorrencia, outro na volta, e o conserto da bandeja.

    Tudo injetavel: os testes passam dubles de `sondar`, `abrir`, `avisar`,
    `dormir` e `relogio`, e nada toca o Tailscale de verdade.
    """

    def __init__(self, *, avisar, sondar=sondar, abrir=abrir_bandeja,
                 dormir=time.sleep, relogio=time.monotonic,
                 intervalo: float = INTERVALO_S,
                 primeira: float = PRIMEIRA_OLHADA_S):
        self._avisar = avisar
        self._sondar = sondar
        self._abrir = abrir
        self._dormir = dormir
        self._relogio = relogio
        self.intervalo = intervalo
        self.proxima = relogio() + primeira
        self.fora = False          # ja avisei desta ocorrencia
        self.fora_sem_resposta = False   # ...e o aviso foi o de "nao sei"
        self.falhas = 0
        self.sem_resposta = 0      # olhadas seguidas sem resposta do Tailscale

    def talvez(self) -> str | None:
        """Chamada a cada volta do laco; so olha quando venceu o intervalo."""
        agora = self._relogio()
        if agora < self.proxima:
            return None
        self.proxima = agora + self.intervalo
        return self.uma_olhada()

    def uma_olhada(self) -> str | None:
        """Olha uma vez. Devolve o aviso mandado, se mandou algum."""
        ficha = self._sondar()
        if ficha.get("sem_resposta"):
            # o `tailscale status` falha por um instante (o servico ocupado):
            # pergunta de novo antes de contar a olhada como sem resposta
            self._dormir(PASSO_DA_ESPERA_S)
            ficha = self._sondar()
        if ficha.get("ok"):
            self.falhas = self.sem_resposta = 0
            if self.fora:
                self.fora = False
                if self.fora_sem_resposta:
                    self.fora_sem_resposta = False
                    return self._mandar("✅ o Tailscale voltou a responder: o app do "
                                        "celular está no tailnet (serve só no tailnet).")
                return self._mandar("✅ o app do celular voltou para o tailnet "
                                    "(Tailscale rodando, serve só no tailnet).")
            return None
        # `falhas` conta so as olhadas COM resposta (e ruim); as sem resposta
        # tem a conta delas: uma nao empurra a outra para o aviso
        sem_resposta = bool(ficha.get("sem_resposta"))
        self.sem_resposta = self.sem_resposta + 1 if sem_resposta else 0
        if not sem_resposta:
            self.falhas += 1
        if self.fora and self.fora_sem_resposta and not sem_resposta:
            # o aviso foi "nao sei"; agora ha resposta, e ela e ruim: e outra
            # ocorrencia (e o conserto da bandeja ainda pode ser tentado)
            self.fora = self.fora_sem_resposta = False
        if self.fora:
            return None                  # um aviso por ocorrencia
        if sem_resposta:
            if self.sem_resposta < SEM_RESPOSTA_SEGUIDAS:
                return None
            self.fora = self.fora_sem_resposta = True
            return self._mandar(self._texto_sem_resposta(ficha, self.sem_resposta))
        feito = ""
        if ficha.get("estado") not in (None, "Running") \
                and ficha.get("bandeja") is False:
            feito = self._abrir()
            if feito.startswith("abri"):
                depois = self._esperar_voltar()
                if depois.get("ok"):
                    self.falhas = 0
                    return self._mandar(
                        f"🔧 o app do celular tinha saído do tailnet "
                        f"({ficha['motivo']}). {feito.capitalize()}, e ele "
                        "voltou.")
                ficha = depois
        # Um tropeco so (o Tailscale conectando logo depois do boot) nao
        # vira aviso; funnel ligado e conserto tentado avisam na hora.
        if not (ficha.get("funnel") or feito or self.falhas >= 2):
            return None
        self.fora = True
        return self._mandar(self._texto_da_falha(ficha, feito))

    def _esperar_voltar(self) -> dict:
        ficha = {"ok": False}
        esperado = 0.0
        while esperado < ESPERA_DO_CONSERTO_S:
            self._dormir(PASSO_DA_ESPERA_S)
            esperado += PASSO_DA_ESPERA_S
            ficha = self._sondar()
            if ficha.get("ok"):
                return ficha
        return ficha

    def _texto_sem_resposta(self, ficha: dict, vezes: int) -> str:
        minutos = round(vezes * self.intervalo / 60)
        return (f"❔ não sei se o app do celular está no tailnet: "
                f"{ficha.get('motivo') or 'o Tailscale não respondeu'} "
                f"({vezes} olhadas seguidas, ~{minutos} min). Pode ser só o "
                "comando do Tailscale travado, e o app pode estar no ar. "
                "Não mexi em nada.")

    @staticmethod
    def _texto_da_falha(ficha: dict, feito: str) -> str:
        if ficha.get("funnel"):
            return ("🚨 o FUNNEL do Tailscale está ligado: o app do celular "
                    "está aberto na internet. Não mexi (a regra é serve sim, "
                    "funnel nunca): desligue o funnel no PC.")
        texto = (f"⚠️ o app do celular está fora do tailnet: "
                 f"{ficha.get('motivo') or 'motivo desconhecido'}.")
        if feito:
            texto += f" {feito.capitalize()}, e não bastou."
        else:
            texto += " Não mexi em nada."
        if ficha.get("estado") == "Running" and not ficha.get("serve"):
            texto += f" Para refazer, só no tailnet: {REFAZER_SERVE}"
        return texto

    def _mandar(self, texto: str) -> str:
        self._avisar(texto)
        return texto


__all__ = ["Vigia", "abrir_bandeja", "bandeja_aberta", "sondar"]
