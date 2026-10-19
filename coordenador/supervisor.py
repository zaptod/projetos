# -*- coding: utf-8 -*-
"""O coordenador residente: adota, vigia e religa os quatro servicos."""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import acoes_pc
from .estado import gravar_estado, ler_estado, pasta, tomar_reinicios_pendentes

RAIZ = Path(r"E:\projetos")
ESPERAS = (5, 15, 60, 300)
LIMITE_FALHAS_HORA = 5
FALHAS_SAUDE = 3
PULSO_S = 5
# A janela das postagens (CLAUDE.md, lei 4): nada de religar servico de
# `post-12` a `post+18` min. Ate 13/10/2026 o `seguro()` so olhava a
# publicacao em voo e o app/bot foram religados a 20 min do post das 15:37.
JANELA_ANTES_MIN = 12
JANELA_DEPOIS_MIN = 18
# Quanto `reiniciar_servico` espera o processo velho MORRER antes de subir o
# novo (12/10: o carteiro antigo seguiu vivo ao lado do novo).
MORTE_PRAZO_S = 15
MORTE_PASSO_S = 0.5


def janela_das_postagens(agora, antes_min=JANELA_ANTES_MIN, depois_min=JANELA_DEPOIS_MIN):
    """(dentro, texto): `agora` esta entre `post-antes` e `post+depois` de
    algum horario da grade (`random_builds/builds/grade.py`)?"""
    from random_builds.builds import grade
    proximo = grade.proximo_em(agora)
    if proximo - agora <= timedelta(minutes=antes_min):
        return True, f"janela das postagens ({proximo:%H:%M}, em {int((proximo - agora).total_seconds() // 60)} min)"
    hora = grade.slot(agora)
    ultimo = agora.replace(hour=hora, minute=grade.minuto(hora), second=0, microsecond=0)
    if ultimo > agora:                      # antes do 1o horario do dia: o ultimo foi ontem
        ultimo -= timedelta(days=1)
    if agora - ultimo < timedelta(minutes=depois_min):
        return True, f"janela das postagens ({ultimo:%H:%M}, há {int((agora - ultimo).total_seconds() // 60)} min)"
    return False, ""


def agora_iso(agora=None):
    return (agora or datetime.now()).isoformat(timespec="seconds")


def _hora_e_dia(iso) -> str:
    """"21:38 (16/10)" de um carimbo ISO; o texto cru se nao for um."""
    try:
        quando = datetime.fromisoformat(str(iso))
    except ValueError:
        return str(iso or "?")
    return quando.strftime("%H:%M (%d/%m)")


def texto_mesa_ilegivel(incidente: dict) -> str:
    """O aviso do Telegram quando a Mesa fica ilegivel (o mesmo texto do app)."""
    copia = incidente.get("copia")
    return ("⚠ A Mesa de pedidos está ilegível desde "
            f"{_hora_e_dia(incidente.get('desde'))}: nada foi gravado por cima"
            + (f" — o arquivo foi guardado em {copia}" if copia else "")
            + ". Os pedidos não andam até ela voltar; aviso de novo quando voltar.")


def carregar_servicos(caminho=None):
    caminho = Path(caminho or Path(__file__).with_name("servicos.json"))
    return {s["nome"]: s for s in json.loads(caminho.read_text(encoding="utf-8"))["servicos"]}


def processos_windows(rodar=subprocess.run):
    """[{pid, comando}], isolado para que testes nao dependam do Windows."""
    # Saida em UTF-8 e leitura que NUNCA quebra: um processo com byte fora do
    # padrao na linha de comando (0x87, cp850) fazia a leitura falhar, a lista
    # vinha vazia e o pulso pulava TUDO -- leitor do Grimorio, vigia, gerente,
    # pedidos. 3.043 pulsos assim de 02/10 a 04/10/2026.
    script = ("[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
              "Get-CimInstance Win32_Process | Select-Object ProcessId,CommandLine,"
              "@{n='Inicio';e={$_.CreationDate.ToString('s')}} | ConvertTo-Json -Compress")
    try:
        resultado = rodar(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          check=False)
        dados = json.loads(resultado.stdout or "[]")
    except (OSError, ValueError, TypeError):
        return []
    if isinstance(dados, dict):
        dados = [dados]
    # `inicio` e a hora em que o processo NASCEU: adotar com a hora da adocao
    # escondia codigo velho (01/10: o bot rodava desde 28/09 e saiu "em dia").
    return [{"pid": int(p.get("ProcessId")), "comando": str(p.get("CommandLine") or ""),
             "inicio": str(p.get("Inicio") or "") or None}
            for p in dados if p.get("ProcessId")]


def publicacao_rodando(processos):
    return any(re.search(r"postar\.py|publicacao_filha|main\.py.*\bpublicar\b", p.get("comando", ""), re.I)
               for p in processos)


# COO-13 (auditoria 11/10): o "Suspender o PC" nunca olhava o render. Conta
# como render: o Movie Maker do Godot (`--write-movie`), um Godot headless de
# render do palco, o ffmpeg montando video, e as rodadas que geram video
# (`main.py noite|palco|generate-video|duelo` dos builds, `main.py auto` das
# historias, o `producao`/`render_luta` do palco).
RENDER = re.compile(
    r"--write-movie|godot\S*\s.*--headless.*render|\bffmpeg(\.exe)?\b|render_luta|"
    r"palco[\\/]\S*render|\bproducao\b|"
    r"main\.py\"?\s+(noite|palco|generate-video|duelo|auto)\b", re.I)


def render_rodando(processos):
    return any(RENDER.search(p.get("comando", "")) for p in processos)


ESPERA_ENTREGA_S = 600   # quanto o reinicio por codigo velho espera uma entrega do carteiro

# 04/10/2026, 13:17-13:29: 13 religadas do app e do bot SEM commit nenhum (era
# edicao em andamento; mexer so em test_orquestrador.py ja religava), e cada
# religada do bot derrubava o app do celular do tailnet por 1 a 3 min.
CALMA_S = 90              # codigo so conta como "mudou" 90 s depois do ultimo save
RELIGADA_MIN_S = 120      # no maximo uma religada por codigo velho a cada 2 min
PASTAS_DE_TESTE = ("tests", "testes")
# A bandeja do Tailscale nasce filha do bot (vigia_tailnet.abrir_bandeja); o
# `taskkill /t` a levava junto e o celular saia do tailnet.
POUPAR_AO_PARAR = ("tailscale-ipn.exe",)


def e_codigo_de_servico(caminho: Path, base: Path) -> bool:
    """Teste nao e codigo de servico: mudar so teste nao pede religada."""
    nome = caminho.name.lower()
    if nome.startswith("test_") or nome.endswith("_test.py") or nome == "conftest.py":
        return False
    try:
        partes = caminho.relative_to(base).parts[:-1]
    except ValueError:
        partes = caminho.parts[:-1]
    return not any(p.lower() in PASTAS_DE_TESTE for p in partes)


def plano_de_parada(raiz: int, processos: list[dict]):
    """A ordem de matar a arvore de `raiz` poupando POUPAR_AO_PARAR (e o que
    estiver abaixo dele). `processos`: [{pid, pai, nome}]. None = nada a
    poupar (o `taskkill /t` de sempre serve); senao, os pids das folhas para
    a raiz, a raiz por ultimo."""
    filhos = {}
    for p in processos:
        filhos.setdefault(int(p.get("pai") or 0), []).append(p)
    matar, vistos, poupou = [], {int(raiz)}, False

    def descer(pid):
        nonlocal poupou
        for filho in filhos.get(pid, []):
            fpid = int(filho.get("pid") or 0)
            if not fpid or fpid in vistos:
                continue
            vistos.add(fpid)
            if str(filho.get("nome") or "").lower() in POUPAR_AO_PARAR:
                poupou = True
                continue
            descer(fpid)
            matar.append(fpid)
    descer(int(raiz))
    return (matar + [int(raiz)]) if poupou else None


def processos_com_pai(rodar=subprocess.run):
    """[{pid, pai, nome}] de todos os processos ([] se a leitura falhar)."""
    script = ("[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
              "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name"
              " | ConvertTo-Json -Compress")
    try:
        r = rodar(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                  capture_output=True, text=True, encoding="utf-8", errors="replace",
                  check=False, timeout=30,
                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        dados = json.loads(r.stdout or "[]")
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return []
    if isinstance(dados, dict):
        dados = [dados]
    return [{"pid": int(p.get("ProcessId") or 0), "pai": int(p.get("ParentProcessId") or 0),
             "nome": str(p.get("Name") or "")} for p in dados if isinstance(p, dict)]

# A ESTEIRA DE SPRITES (02/10/2026): ninguem chamava o `avancar` e 10 imagens
# ficaram paradas entre "pedido" e "julgado". O pulso agora roda o `ciclo`
# de cada perfil (anda tudo e mantem a producao cheia, commit 708a767), no
# maximo uma vez a cada 5 min, numa thread propria.
ESTEIRA_INTERVALO_S = 300
ESTEIRA_PERFIS = ("palco", "vila")
ESTEIRA_PRAZO_S = 240


def ciclo_das_esteiras(rodar=subprocess.run, python=None, raiz=RAIZ):
    """`python -m esteira_sprites --perfil <p> ciclo` para palco e vila.

    Subprocesso, e nao import: o perfil da esteira e global no processo
    (`config.usar`), e uma rodada que quebra nao leva o coordenador junto.
    O `ciclo` imprime uma linha JSON ({perfil, andou, em_voo, novos}).
    Devolve {perfil: {"codigo", "andou", "novos", "em_voo", "saida"}}.
    """
    saida = {}
    for perfil in ESTEIRA_PERFIS:
        comando = [python or sys.executable, "-X", "utf8", "-m", "esteira_sprites",
                   "--perfil", perfil, "ciclo"]
        try:
            r = rodar(comando, cwd=str(raiz), capture_output=True, text=True,
                      encoding="utf-8", errors="replace", timeout=ESTEIRA_PRAZO_S,
                      check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired) as exc:
            saida[perfil] = {"codigo": None, "andou": 0, "novos": [], "em_voo": None,
                             "saida": type(exc).__name__}
            continue
        linhas = (r.stdout or "").strip().splitlines()
        try:
            dados = json.loads(linhas[-1]) if linhas else {}
        except ValueError:
            dados = {}
        dados = dados if isinstance(dados, dict) else {}
        texto = (r.stderr or "").strip().splitlines()[-1:] if r.returncode else linhas[-1:]
        saida[perfil] = {"codigo": r.returncode, "andou": int(dados.get("andou") or 0),
                         "novos": list(dados.get("novos") or []),
                         "em_voo": dados.get("em_voo"),
                         "saida": (texto[0] if texto else "")[:200]}
    return saida


_LEMBRANCA_CLAUDE: dict = {}       # desde quando o claude.json esta ilegivel (COO-9)


def _pid_vivo(pid: int) -> bool:
    """Existe um processo com esse pid? (tasklist, sem psutil)."""
    try:
        feito = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH", "/FO", "CSV"],
                               capture_output=True, text=True, encoding="cp850",
                               errors="replace", check=False)
    except OSError:
        return True          # na duvida, nao rouba a trava de ninguem
    return f'"{int(pid)}"' in (feito.stdout or "")


def _criado_de(pid):
    try:
        from remoto.orquestrador import hora_de_criacao
        return hora_de_criacao(pid)
    except Exception:                                         # noqa: BLE001
        return None


def _comando_de(pid) -> str | None:
    """A linha de comando do processo `pid` (None = nao sei)."""
    try:
        feito = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if feito.returncode != 0:
        return None
    # vazio: processo elevado lido por um nao elevado (o Windows esconde a
    # linha de comando) ou que acabou de sair; "nao sei", e a trava e respeitada
    return feito.stdout.strip() or None


class TravaUnica:
    def __init__(self, caminho=None):
        self.caminho = Path(caminho or pasta() / "coordenador.lock")
        self.adquirida = False
        self.dono = None

    def _ler_dono(self):
        """(pid, hora de criacao) gravados; o lock antigo so tinha o pid."""
        try:
            texto = self.caminho.read_text(encoding="utf-8").strip()
        except OSError:
            return 0, None
        try:
            dados = json.loads(texto or "0")
        except ValueError:
            return 0, None
        if isinstance(dados, dict):
            try:
                return int(dados.get("pid") or 0), dados.get("criado")
            except (TypeError, ValueError):
                return 0, None
        try:
            return int(dados), None
        except (TypeError, ValueError):
            return 0, None

    @staticmethod
    def _ainda_e_o_dono(dono, hora, criado, comando) -> bool:
        """COO-14 (auditoria 11/10): o pid do lock pode ter virado outro
        programa (o Windows reaproveita). Com a hora de criacao gravada, ela
        tem de bater; no lock antigo, a linha de comando tem de ser a do
        coordenador. Sem como saber, respeita o dono."""
        if hora is not None:
            agora = criado(dono)
            try:
                return agora is None or abs(float(agora) - float(hora)) < 2.0
            except (TypeError, ValueError):
                return True
        linha = comando(dono)
        if linha is None:
            return True
        return re.search(r"-m\s+coordenador\b", linha) is not None

    def adquirir(self, vivo=None, criado=None, comando=None):
        """Uma trava de processo MORTO e retomada: sem isso, o coordenador que
        morre de repente deixa o arquivo e nenhum outro sobe mais (02/10).
        Idem a de pid vivo que ja nao e o coordenador (COO-14)."""
        vivo = vivo or _pid_vivo
        criado = criado or _criado_de
        comando = comando or _comando_de
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(json.dumps({"pid": os.getpid(), "criado": criado(os.getpid())}))
                self.adquirida = True
                return True
            except FileExistsError:
                dono, hora = self._ler_dono()
                if dono and vivo(dono) and self._ainda_e_o_dono(dono, hora, criado, comando):
                    self.dono = dono
                    return False
                try:
                    self.caminho.unlink()
                except OSError:
                    return False
        return False

    def soltar(self):
        if self.adquirida:
            try:
                self.caminho.unlink()
            except OSError:
                pass
            self.adquirida = False


class Supervisor:
    """Nucleo injetavel. Os efeitos externos entram pelas funcoes do construtor."""
    def __init__(self, *, servicos=None, relogio=datetime.now, processos=processos_windows,
                 iniciar=None, parar=None, avisar=None, porta=None, carteiro=None,
                 git=None, comandos=None, aplicar=None, claude_proibido=None,
                 delegados=None, parar_delegado=None, executar_acao=None, gravar=None, log=None, raiz=RAIZ,
                 cerebro=None, vigia_trabalho=None, em_fundo=None, esteira=None, assembleia=None,
                 gerente_equipe=None, pedidos=None, aplicar_app=None, conversa=None, obsidian=None,
                 carregar=None, janela=None, dormir=None, pendentes=None,
                 vigia_rodadas=None):
        self.servicos = servicos or carregar_servicos()
        self.relogio, self.processos = relogio, processos
        # a janela das postagens (dublavel), a espera pela morte do processo
        # velho e os `coordenador reiniciar` que ficaram pendentes em disco
        self.janela = janela or janela_das_postagens
        self.dormir = dormir or time.sleep
        self.pendentes = pendentes or tomar_reinicios_pendentes
        self.iniciar = iniciar or self._iniciar
        self.parar = parar or self._parar
        self.avisar = avisar or self._avisar
        self.porta = porta or self._porta_8931
        self.carteiro = carteiro or self._carteiro
        self.git = git or self._mudou_codigo
        self.comandos, self.aplicar = comandos, aplicar
        # os comandos do app que nao sao de servico (orquestrador.aplicar_pelo_servidor);
        # ausente nos testes que nao o pedem: o comando fica pendente
        self.aplicar_app = aplicar_app
        self.erros_comando = set()
        self.claude_proibido = claude_proibido or self._claude_proibido
        self.delegados = delegados or self._delegados
        self.parar_delegado = parar_delegado or self._parar_delegado
        self.executar_acao = executar_acao or self._executar_acao
        self.gravar = gravar or gravar_estado
        self.log = log or self._log
        self.raiz = Path(raiz)
        self.desde = agora_iso(self.relogio())
        self.falhas = {n: [] for n in self.servicos}
        self.saudes_ruins = {n: 0 for n in self.servicos}
        self.ausencias = {n: 0 for n in self.servicos}
        self.velho_desde = {}
        self.religado_por_codigo = {}
        self.eventos = []
        # O cerebro (`cerebro.atender`) e o vigia de trabalho so existem quando
        # o `__main__` os liga: nos testes, ausentes = nada de Codex nem git.
        self.cerebro, self.vigia_trabalho = cerebro, vigia_trabalho
        self.gerente_equipe = gerente_equipe
        self.pedidos = pedidos
        # a conversa com o Adrian (06/10/2026): thread PROPRIA, para a
        # resposta nao esperar um `passo` lento dos pedidos (contratar leva ate
        # ~28 s) nem a fila de trabalho
        self.conversa = conversa
        # O cofre e secundario: se nao existir ou estiver sincronizando, a
        # producao segue normalmente. A propria rotina decide se houve mudanca.
        self.obsidian = obsidian
        self.equipe = {}
        # a esteira de sprites idem: so o `montar()` de producao a liga
        self.esteira = esteira
        self.esteira_em = None
        self.ultima_esteira = {}
        self.assembleia = assembleia
        self.em_fundo = em_fundo or self._em_fundo
        self.fundos = {}
        self.vigia_em = None
        # SCR-7 (14/10/2026): a rodada longa calada ha horas e encerrada;
        # so o `montar()` de producao liga
        self.vigia_rodadas = vigia_rodadas
        self.rodadas, self.rodadas_em = [], None
        self.assembleia_em = None
        self.trabalho = {}
        self.reinicio_pedido = set()
        self.sair_quando_seguro = False     # pedir_reinicio("coordenador")
        self.ultima_recusa = {}
        self.estado = {n: {"situacao": "parado", "pid": None, "desde": None,
                           "reinicios_24h": 0, "reinicios": [], "ultimo_erro": "",
                           "codigo_velho": False, "reinicio_pedido": False,
                           "saude": "desconhecida", "proximo_reinicio": None,
                           "motivo_espera": ""} for n in self.servicos}
        # `reinicios_24h` e o reinicio pedido sobrevivem ao coordenador subir
        # de novo (antes zeravam a cada subida: a tarefa religa a cada 5 min)
        self._retomar((carregar or ler_estado)())

    def _retomar(self, anterior):
        servicos = anterior.get("servicos") if isinstance(anterior, dict) else None
        if not isinstance(servicos, dict):
            return
        for nome, estado in self.estado.items():
            velho = servicos.get(nome) or {}
            if not isinstance(velho, dict):
                continue
            estado["reinicios"] = [str(x) for x in (velho.get("reinicios") or []) if x]
            if velho.get("reinicio_pedido"):
                self.reinicio_pedido.add(nome)
            self._contar_reinicios(nome)

    def _contar_reinicios(self, nome):
        """Os reinicios das ultimas 24 h, contados de verdade (nao zera na subida)."""
        estado = self.estado[nome]
        limite = self.relogio() - timedelta(hours=24)
        vivos = []
        for carimbo in estado.get("reinicios") or []:
            try:
                if datetime.fromisoformat(carimbo) > limite:
                    vivos.append(carimbo)
            except ValueError:
                continue
        estado["reinicios"] = vivos[-200:]
        estado["reinicios_24h"] = len(estado["reinicios"])
        estado["reinicio_pedido"] = nome in self.reinicio_pedido
        return estado["reinicios_24h"]

    def evento(self, servico, tipo, texto):
        self.eventos.append({"em": agora_iso(self.relogio()), "servico": servico,
                             "tipo": tipo, "texto": str(texto)[:300]})
        self.eventos = self.eventos[-100:]
        self.log(f"{servico or 'coordenador'} {tipo}: {texto}")

    @staticmethod
    def _log(texto):
        alvo = Path(r"E:\projetos\outputs\coordenador.txt")
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with open(alvo, "a", encoding="utf-8") as fh:
            fh.write(f"{agora_iso()} {texto}\n")

    def _iniciar(self, ficha):
        log = Path(ficha["log"])
        log.parent.mkdir(parents=True, exist_ok=True)
        fh = open(log, "a", encoding="utf-8")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if ficha["janela"] == "oculta" else 0
        try:
            proc = subprocess.Popen(ficha["comando"], cwd=ficha["cwd"], stdout=fh, stderr=subprocess.STDOUT,
                                    creationflags=flags)
            return proc.pid
        finally:
            fh.close()

    def _parar(self, pid, listar=processos_com_pai, rodar=subprocess.run):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        plano = plano_de_parada(int(pid), listar())
        if plano is None:
            rodar(["taskkill", "/pid", str(pid), "/t", "/f"], check=False, creationflags=flags)
            return
        for alvo in plano:                    # folhas primeiro, a bandeja fica
            rodar(["taskkill", "/pid", str(alvo), "/f"], check=False, creationflags=flags)

    @staticmethod
    def _porta_8931():
        try:
            with socket.create_connection(("127.0.0.1", 8931), timeout=1):
                return True
        except OSError:
            return False

    @staticmethod
    def _carteiro():
        try:
            from ias.correio import estado_do_carteiro
            return estado_do_carteiro()
        except Exception:
            return {"situacao": "nunca", "pulso_em": None}

    @staticmethod
    def _avisar(texto):
        try:
            from ias.carteiro import avisar_telegram
            return avisar_telegram(texto)
        except Exception:
            return False

    @staticmethod
    def _claude_proibido():
        # COO-9: so para os delegados com o "proibido" do arquivo, ou com o
        # claude.json ilegivel em duas leituras a 2 s ou mais uma da outra
        from remoto.claude_estado import motivo_para_parar
        return motivo_para_parar(_LEMBRANCA_CLAUDE)

    @staticmethod
    def _delegados():
        try:
            from remoto.orquestrador import ler_estado
            return [a["id"] for a in ler_estado().get("agora", []) if a.get("situacao") == "trabalhando"]
        except Exception:
            return []

    @staticmethod
    def _parar_delegado(ident):
        subprocess.run(["python", "-m", "remoto.delegar", "parar", "--id", str(ident)], check=False)

    def _mudou_codigo(self, ficha, desde):
        """Codigo de servico (nao teste) mais novo que o processo, e parado ha
        CALMA_S: enquanto alguem salva arquivo, a edicao nao terminou."""
        inicio = datetime.fromisoformat(desde).timestamp() if desde else 0
        mais_nova = None
        for modulo in ficha.get("modulos", []):
            alvo = self.raiz / modulo
            if not alvo.exists():
                continue
            for p in alvo.rglob("*.py"):
                if not e_codigo_de_servico(p, alvo):
                    continue
                try:
                    quando = p.stat().st_mtime
                except OSError:                    # apagado no meio da varredura
                    continue
                if quando > inicio and (mais_nova is None or quando > mais_nova):
                    mais_nova = quando
        if mais_nova is None:
            return False
        return self.relogio().timestamp() - mais_nova >= CALMA_S

    def _executar_acao(self, acao):
        return acoes_pc.executar(acao, publicar_ativo=lambda: publicacao_rodando(self.processos()),
                                 render_ativo=lambda: render_rodando(self.processos()),
                                 reiniciar_tudo=self.reiniciar_tudo, resumo=self.resumo)

    def _adotar(self, ficha, processos):
        padrao = re.compile(ficha["assinatura"], re.I)
        return next((p for p in processos if padrao.search(p["comando"])), None)

    def _saude(self, nome, vivo):
        if not vivo:
            return "ruim"
        if nome == "app":
            return "ok" if self.porta() else "ruim"
        if nome == "carteiro":
            estado = self.carteiro()
            return "ok" if estado.get("situacao") not in ("parado", "nunca") else "ruim"
        return "ok"

    def seguro(self, nome, processos=None, *, janela=True):
        """(ok, motivo). `janela=False` para SUBIR um servico que caiu: a lei
        da janela e contra derrubar quem esta vivo, e o app fora do ar meia
        hora em cada um dos 10 horarios seria pior que o defeito."""
        processos = self.processos() if processos is None else processos
        if publicacao_rodando(processos):
            return False, "publicacao em andamento"
        agora = self.relogio()
        # D3 (Grimorio, 13/10/2026): nunca dentro da janela das postagens,
        # `post-12` a `post+18` min da grade. A publicacao em voo continua acima.
        if janela:
            dentro, texto = self.janela(agora)
            if dentro:
                return False, texto
        if nome == "carteiro" and self.carteiro().get("situacao") == "entregando":
            # 02/10 00:04: um pedido condenado segurou o carteiro velho por 7 min
            # e o Adrian: "ele nunca vai parar de rodar". Espera no maximo
            # ESPERA_ENTREGA_S desde que o codigo ficou velho; depois reinicia
            # e a mensagem do meio fica marcada como interrompida.
            desde = self.velho_desde.get(nome)
            if desde is None or (agora - desde).total_seconds() < ESPERA_ENTREGA_S:
                return False, "carteiro entregando"
            self._interromper_entrega()
        return True, ""

    def _interromper_entrega(self):
        try:
            from ias import correio
            atual = correio.estado_do_carteiro()
            if atual.get("situacao") == "entregando" and atual.get("ia") and atual.get("mensagem_id"):
                correio.atualizar(atual["ia"], atual["mensagem_id"], situacao="falhou",
                                  erro="interrompida: o coordenador reiniciou o carteiro com o codigo novo",
                                  categoria="interrompida")
        except Exception as exc:  # noqa: BLE001 - reiniciar vale mais que marcar
            self.log(f"[coordenador] nao marquei a entrega interrompida: {exc}")

    def _limite(self, nome):
        agora = self.relogio().timestamp()
        self.falhas[nome] = [x for x in self.falhas[nome] if agora - x < 3600]
        return len(self.falhas[nome]) >= LIMITE_FALHAS_HORA

    def religar(self, nome, motivo="caiu", forcar=False):
        ficha, estado = self.servicos[nome], self.estado[nome]
        proximo = estado.get("proximo_reinicio")
        if not forcar and proximo:
            try:
                if self.relogio() < datetime.fromisoformat(proximo):
                    return False
            except ValueError:
                pass
        if ficha.get("reinicio_seguro") and not forcar:
            ok, espera = self.seguro(nome, janela=False)
            if not ok:
                estado.update(situacao="reiniciando", motivo_espera=espera)
                return False
        if self._limite(nome):
            estado.update(situacao="falhou", ultimo_erro="limite de 5 falhas por hora")
            self.avisar(f"Coordenador: {nome} falhou 5 vezes em uma hora; parei de tentar.")
            return False
        try:
            pid = self.iniciar(ficha)
        except Exception as exc:  # o processo nao pode matar o coordenador
            self.falhas[nome].append(self.relogio().timestamp())
            espera = ESPERAS[min(len(self.falhas[nome]) - 1, len(ESPERAS) - 1)]
            estado.update(situacao="caiu", ultimo_erro=str(exc),
                          proximo_reinicio=agora_iso(self.relogio() + timedelta(seconds=espera)))
            self.evento(nome, "caiu", str(exc))
            return False
        estado.update(situacao="rodando", pid=pid, desde=agora_iso(self.relogio()), saude="desconhecida",
                      proximo_reinicio=None, motivo_espera="", codigo_velho=False)
        estado.setdefault("reinicios", []).append(agora_iso(self.relogio()))
        self._contar_reinicios(nome)
        # religou com sucesso: a conta de saude ruim recomeca (antes ficava em
        # 3 e o app novo era morto no pulso seguinte, com a porta ainda fechada)
        self.saudes_ruins[nome] = 0
        self.evento(nome, "religou", f"PID {pid}")
        return True

    def verificar_servico(self, nome, processos):
        ficha, estado = self.servicos[nome], self.estado[nome]
        achado = self._adotar(ficha, processos)
        if achado is None:
            # Uma ausencia so nao basta: o processo pode estar trocando de pid ou
            # a listagem pode ter vindo pela metade. Religa na segunda seguida.
            self.ausencias[nome] = self.ausencias.get(nome, 0) + 1
            if self.ausencias[nome] < 2 and estado.get("pid"):
                return
            if estado["situacao"] != "falhou":
                estado.update(situacao="caiu", pid=None, saude="ruim")
                self.evento(nome, "caiu", "processo ausente")
                # A primeira subida e imediata; uma queda depois de adotado
                # respeita o primeiro degrau do backoff.
                if estado.get("desde") and not estado.get("proximo_reinicio"):
                    self.falhas[nome].append(self.relogio().timestamp())
                    estado["proximo_reinicio"] = agora_iso(self.relogio() + timedelta(seconds=ESPERAS[0]))
                self.religar(nome, "ausente")
            return
        self.ausencias[nome] = 0
        if state_pid := achado.get("pid"):
            if estado["pid"] != state_pid:
                # processo novo (religado por fora, ex.: `coordenador reiniciar`
                # na linha de comando): a marca de codigo velho era do anterior;
                # o `git` abaixo reavalia com o `desde` do novo (14/10/2026)
                estado.update(pid=state_pid, situacao="rodando", codigo_velho=False,
                              desde=achado.get("inicio") or estado["desde"] or agora_iso(self.relogio()))
                self.velho_desde.pop(nome, None)
        estado["saude"] = self._saude(nome, True)
        if estado["saude"] == "ruim":
            self.saudes_ruins[nome] += 1
            if self.saudes_ruins[nome] >= FALHAS_SAUDE:
                estado["situacao"] = "caiu"
                self.parar(achado["pid"])
                self.falhas[nome].append(self.relogio().timestamp())
                estado["proximo_reinicio"] = agora_iso(self.relogio() + timedelta(seconds=ESPERAS[0]))
                self.religar(nome, "saude ruim")
            return
        self.saudes_ruins[nome] = 0
        # D3 (13/10/2026): codigo velho so INFORMA (status, app); o reinicio
        # acontece quando alguem PEDE (vigia ao aplicar, `coordenador reiniciar`).
        if not estado["codigo_velho"] and self.git(ficha, estado["desde"]):
            estado["codigo_velho"] = True
            self.evento(nome, "codigo_velho", "codigo mudou desde o inicio; reinicio so quando pedido")
        if nome in self.reinicio_pedido:
            self.velho_desde.setdefault(nome, self.relogio())
            recusa = self.ultima_recusa.get(nome) or {}
            if recusa.get("tipo") == "morte" and \
                    (self.relogio() - recusa["em"]).total_seconds() < RELIGADA_MIN_S:
                return      # o velho nao morreu ha pouco: nao trava o pulso 15 s de novo agora
            ultima = self.religado_por_codigo.get(nome)
            if ultima is not None:
                passou = (self.relogio() - ultima).total_seconds()
                if passou < RELIGADA_MIN_S:
                    estado.update(motivo_espera=f"religou por código há {int(passou)} s; "
                                                f"no máximo uma vez a cada {RELIGADA_MIN_S} s",
                                  proximo_reinicio=None)
                    return
            self.reiniciar_servico(nome, processos=processos)

    def processar_comandos(self):
        """Todo comando pendente do app e aplicado AQUI, no pulso (04/10/2026).

        Servico e acao do PC sao do supervisor; o resto (capacidade, fila,
        parar, modelos, mensagem -> pedido) vai a `aplicar_app`
        (`orquestrador.aplicar_pelo_servidor`). A sessao do VS Code deixou de
        ser necessaria: antes esses ficavam pendentes ate ela rodar `aplicado`.
        """
        if not self.comandos or not self.aplicar:
            return
        meus = {"servico_reiniciar", "servico_parar", "servico_ligar", "pc_acao"}
        try:
            lista = self.comandos()
        except Exception as exc:                  # noqa: BLE001 - registro ilegivel nao para o pulso
            self._erro_de_comando("lista", f"não li os comandos: {type(exc).__name__}: {exc}")
            return
        for comando in lista:
            if comando.get("comando") not in meus:
                self._aplicar_do_app(comando)
                continue
            try:
                nome, valor = comando["comando"], comando.get("valor")
                if nome == "servico_parar":
                    pid = self.estado.get(valor, {}).get("pid")
                    if pid:
                        self.parar(pid)
                    self.estado[valor].update(situacao="desligado", pid=None)
                elif nome == "servico_ligar":
                    self.religar(valor)
                elif nome == "servico_reiniciar":
                    if not self.reiniciar_servico(valor):
                        # recusado pelo momento (janela, publicacao, carteiro):
                        # fica PEDIDO e sai no pulso em que for seguro; o
                        # comando nao e "executado" (auditoria, item 4)
                        motivo = self._deixar_pendente(valor)
                        desfecho = "pendente" if valor in self.reinicio_pedido else "recusado"
                        if desfecho == "pendente":
                            self.aplicar(comando["id"], nota=f"pendente: {motivo}")
                        else:
                            self.aplicar(comando["id"], recusado=motivo)
                        self.evento(str(valor), "comando", f"{nome} {desfecho}: {motivo}")
                        continue
                else:
                    self._executar_acao(valor)
                self.aplicar(comando["id"], nota="executado pelo coordenador")
                self.evento(str(valor), "comando", nome)
            except (KeyError, ValueError, OSError, subprocess.SubprocessError) as exc:
                try:
                    self.aplicar(comando["id"], recusado=str(exc))
                except Exception as erro:         # noqa: BLE001 - ja resolvido por outro
                    self._erro_de_comando(comando.get("id"), f"{type(erro).__name__}: {erro}")
            except Exception as exc:              # noqa: BLE001 - JaResolvido e afins
                self._erro_de_comando(comando.get("id"), f"{type(exc).__name__}: {exc}")

    def _aplicar_do_app(self, comando):
        if not self.aplicar_app:
            return
        try:
            linha = self.aplicar_app(comando)
        except Exception as exc:                  # noqa: BLE001 - fica pendente; o pulso tenta de novo
            self._erro_de_comando(comando.get("id"),
                                  f"{comando.get('comando')}: {type(exc).__name__}: {exc}")
            return
        if linha:
            resultado = linha.get("resultado", "aplicado")
            detalhe = linha.get("motivo") or linha.get("nota") or ""
            self.evento("", "comando", f"{resultado} {comando.get('comando')}"
                        + (f": {detalhe}" if detalhe else ""))

    def _erro_de_comando(self, ident, texto):
        """Um evento por comando com erro, nao um a cada pulso de 5 s."""
        chave = (ident, texto)
        if chave in self.erros_comando:
            return
        self.erros_comando.add(chave)
        self.evento("", "comando_erro", f"{ident}: {texto}")

    # ------------------------------------------------ cerebro e vigia de trabalho
    def _em_fundo(self, nome, funcao):
        """Uma thread por tarefa: pensar e testar levam minutos e o pulso de
        5 s nao pode esperar. Se a anterior ainda roda, esta vez passa."""
        import threading
        atual = self.fundos.get(nome)
        if atual is not None and atual.is_alive():
            return False

        def rodar():
            try:
                funcao()
            except Exception as exc:  # noqa: BLE001 - a thread nao derruba o laco
                self.evento("", f"{nome}_erro", f"{type(exc).__name__}: {exc}")
        self.fundos[nome] = threading.Thread(target=rodar, name=f"coordenador-{nome}", daemon=True)
        self.fundos[nome].start()
        return True

    def processar_cerebro(self):
        if not self.cerebro:
            return
        self.em_fundo("cerebro", lambda: self.cerebro(comandos=self.comandos, aplicar=self.aplicar,
                                                       avisar=self.avisar))

    def vigiar_trabalho(self):
        if not self.vigia_trabalho:
            return
        from .vigia_trabalho import INTERVALO_S
        agora = self.relogio()
        if self.vigia_em is not None and (agora - self.vigia_em).total_seconds() < INTERVALO_S:
            return
        self.vigia_em = agora

        def passo():
            self.trabalho = self.vigia_trabalho.passo()
        self.em_fundo("vigia", passo)

    def vigiar_rodadas(self):
        """SCR-7: o vigia das rodadas penduradas, em fundo (o `taskkill` e a
        confirmacao de morte levam segundos), uma olhada por `INTERVALO_S`."""
        if not self.vigia_rodadas:
            return
        from .vigia_rodadas import INTERVALO_S
        agora = self.relogio()
        anterior = self.rodadas_em
        if anterior is not None and (agora - anterior).total_seconds() < INTERVALO_S:
            return
        self.rodadas_em = agora

        def passo():
            feito = self.vigia_rodadas.passo(forcar=True)
            if feito:
                self.rodadas = feito
        self.em_fundo("rodadas", passo)

    def gerenciar_equipe(self):
        if not self.gerente_equipe:
            return
        self.em_fundo("equipe", lambda: setattr(self, "equipe", self.gerente_equipe.passo()))

    def processar_pedidos(self):
        """Pedidos livres sobrevivem a uma sessao fechada do VS Code."""
        if self.pedidos:
            self.em_fundo("pedidos", self._pedidos_vigiados)

    def _pedidos_vigiados(self):
        """O passo dos pedidos, com o alarme da Mesa ilegivel (19/10/2026: tres
        dias ilegivel e ninguem avisado). UM aviso por incidente, nao por
        pulso, e outro quando ela volta. O `pedidos_erro` do log continua (a
        excecao sobe para o `em_fundo`)."""
        from coordenador import pedidos as mesa
        try:
            self.pedidos()
        except mesa.PedidosIlegiveis as exc:
            novo = mesa.marcar_ilegivel(exc, self.relogio())
            if novo:
                self.avisar(texto_mesa_ilegivel(novo))
            raise
        voltou = mesa.marcar_legivel()
        if voltou:
            self.avisar("✅ A Mesa de pedidos voltou: o pedidos.json foi lido de novo "
                        f"(estava ilegível desde {_hora_e_dia(voltou.get('desde'))}).")
            self.evento("", "mesa_voltou", f"ilegível desde {voltou.get('desde')}")

    def processar_conversa(self):
        """A resposta de conversa (segundos), fora da fila de trabalho."""
        if self.conversa:
            self.em_fundo("conversa", self.conversa)

    def rodar_esteira(self):
        """Um `ciclo` da esteira (palco e vila) a cada ESTEIRA_INTERVALO_S."""
        if not self.esteira:
            return
        agora = self.relogio()
        desde = (agora - self.esteira_em).total_seconds() if self.esteira_em else None
        if desde is not None and desde < ESTEIRA_INTERVALO_S:
            return
        self.esteira_em = agora

        def passo():
            resultado = self.esteira() or {}
            self.ultima_esteira = {"em": agora_iso(self.relogio()), "perfis": resultado}
            # so vira evento o que andou ou quebrou: 288 rodadas por dia
            # empurrariam para fora os 100 eventos que o app mostra
            notaveis = {p: r for p, r in resultado.items()
                        if r.get("andou") or r.get("novos") or r.get("codigo") != 0}
            if notaveis:
                self.evento("", "esteira", "; ".join(
                    f"{p}: {r.get('andou', 0)} andou, {len(r.get('novos') or [])} novo(s)"
                    + (f", codigo {r.get('codigo')} {r.get('saida', '')}" if r.get("codigo") != 0 else "")
                    for p, r in notaveis.items()))
        self.em_fundo("esteira", passo)

    def avancar_assembleia(self):
        """O correio entrega devagar; a assembleia so precisa de um pulso/5 min."""
        if not self.assembleia:
            return          # so o `montar()` de producao a liga: teste nunca toca o correio real
        agora = self.relogio()
        if self.assembleia_em is not None and (agora - self.assembleia_em).total_seconds() < 300:
            return
        self.assembleia_em = agora
        self.em_fundo("assembleia", lambda: self.assembleia())

    def atualizar_obsidian(self):
        """Atualiza as notas geradas sem deixar o pulso esperar pelo disco."""
        if self.obsidian:
            self.em_fundo("obsidian", self.obsidian)

    def pedir_reinicio(self, nome):
        """O vigia aplicou codigo deste servico: reinicia no proximo momento seguro.

        COO-12 (auditoria 11/10): "coordenador" nao e servico da lista, e o
        pedido sumia: ele seguia com o codigo velho. Agora o laco sai no
        proximo momento seguro, sem thread de fundo no meio, e a tarefa do
        Agendador (a cada 5 min) o sobe com o codigo novo; os servicos ficam
        vivos e sao adotados pela linha de comando."""
        if nome == "coordenador":
            if not self.sair_quando_seguro:
                self.sair_quando_seguro = True
                self.evento("", "reinicio_pedido", "código do coordenador aplicado; saio no "
                                                   "próximo momento seguro e a tarefa me religa")
            return
        if nome in self.servicos:
            self.reinicio_pedido.add(nome)
            self.estado[nome]["reinicio_pedido"] = True
            self.evento(nome, "reinicio_pedido", "entrega do Codex aplicada")

    def reiniciar_tudo(self):
        for nome in self.servicos:
            if not self.reiniciar_servico(nome):
                self._deixar_pendente(nome)

    def _esperar_morrer(self, nome, pids):
        """Espera os pids sumirem da lista de processos (ate MORTE_PRAZO_S);
        devolve os que continuaram vivos."""
        padrao = re.compile(self.servicos[nome]["assinatura"], re.I)
        prazo = max(1, int(MORTE_PRAZO_S / MORTE_PASSO_S))
        vivos = set(pids)
        for _ in range(prazo):
            lista = self.processos()
            # lista vazia e a consulta do Windows que falhou (01/10), nao
            # prova de que morreu: espera e olha de novo
            if lista:
                vivos &= {p["pid"] for p in lista if padrao.search(p["comando"])}
                if not vivos:
                    return []
            self.dormir(MORTE_PASSO_S)
        return sorted(vivos)

    def _recusar(self, nome, tipo, motivo):
        """Reinicio que nao aconteceu: `tipo` e "momento" (janela, publicacao,
        carteiro: tenta de novo quando for seguro), "morte" (o velho nao
        morreu, sem permissao?) ou "subir" (matou e o novo nao subiu)."""
        self.ultima_recusa[nome] = {"tipo": tipo, "motivo": motivo, "em": self.relogio()}
        if tipo == "momento":
            self.estado[nome].update(situacao="reiniciando", motivo_espera=motivo)
        else:
            self.estado[nome]["motivo_espera"] = motivo
            self.evento(nome, "reinicio_falhou", motivo)
        if tipo == "subir":
            # o velho ja morreu: o novo, quando o pulso o religar por
            # "ausente", ja nasce com o codigo novo; nada mais a pedir
            self.reinicio_pedido.discard(nome)
            self.estado[nome]["reinicio_pedido"] = False
        return False

    def _deixar_pendente(self, nome):
        """Depois de um `reiniciar_servico` recusado: fica PEDIDO (o pulso
        refaz quando for seguro) salvo quando o velho ja morreu. Devolve o
        motivo para quem precisa contar a alguem."""
        recusa = self.ultima_recusa.get(nome) or {}
        if recusa.get("tipo") in ("momento", "morte"):
            self.reinicio_pedido.add(nome)
            self.estado[nome]["reinicio_pedido"] = True
        return recusa.get("motivo") or self.estado[nome].get("motivo_espera") or "momento não seguro"

    def reiniciar_servico(self, nome, *, forcar=False, processos=None):
        """Mata o(s) processo(s) adotado(s) DE VERDADE antes de subir outro.

        Recusado (janela das postagens, publicacao em voo, carteiro
        entregando) devolve False com `motivo_espera` preenchido e o porque em
        `ultima_recusa[nome]`; quem chamou decide se deixa pendente.
        12/10/2026: o carteiro velho seguiu vivo ao lado do novo porque
        ninguem conferia se o `taskkill` tinha surtido efeito.
        """
        estado = self.estado[nome]
        self.ultima_recusa.pop(nome, None)
        processos = self.processos() if processos is None else processos
        if not forcar:
            ok, espera = self.seguro(nome, processos)
            if not ok:
                return self._recusar(nome, "momento", espera)
        padrao = re.compile(self.servicos[nome]["assinatura"], re.I)
        # TODOS os que casam: um duplicado de antes tambem sai, senao o
        # religar soma mais um ao lado dele
        pids = [p["pid"] for p in processos if padrao.search(p["comando"])]
        if pids:
            try:
                for pid in pids:
                    self.parar(pid)
            except OSError as exc:
                return self._recusar(nome, "morte", f"sem permissão para parar o processo velho: {exc}")
            vivos = self._esperar_morrer(nome, pids)
            if vivos:
                try:
                    for pid in vivos:             # segunda tentativa, e sem subir outro
                        self.parar(pid)
                except OSError:
                    pass
                return self._recusar(nome, "morte",
                                     f"o processo velho ({', '.join(map(str, vivos))}) não morreu "
                                     "(sem permissão para matá-lo?); não subi outro ao lado")
            estado["pid"] = None
        if not self.religar(nome, "pedido", forcar=True):
            return self._recusar(nome, "subir", f"parei o velho mas o novo não subiu: "
                                                f"{estado.get('ultimo_erro') or 'erro desconhecido'}")
        self.religado_por_codigo[nome] = self.relogio()
        self.reinicio_pedido.discard(nome)
        self.velho_desde.pop(nome, None)
        estado["reinicio_pedido"] = False
        self.evento(nome, "reiniciou", "a pedido")
        return True

    def pulso(self):
        # `coordenador reiniciar <svc>` recusado pela janela deixa o pedido em
        # disco; o residente o assume aqui e reinicia quando for seguro
        try:
            for nome in self.pendentes():
                if nome in self.servicos and nome not in self.reinicio_pedido:
                    self.reinicio_pedido.add(nome)
                    self.evento(nome, "reinicio_pedido", "pedido pela linha de comando")
        except Exception as exc:                  # noqa: BLE001 - disco nao para o pulso
            self.log(f"[coordenador] nao li os reinicios pendentes: {exc}")
        for nome in self.servicos:
            self._contar_reinicios(nome)
        processos = self.processos()
        # 01/10 23:56: a consulta do Windows as vezes volta vazia (lenta ou
        # falhou) e o coordenador achava que TUDO tinha caido e subia de novo.
        # Lista vazia nao e prova de queda: pula a verificacao neste pulso.
        if not processos:
            self.log("[coordenador] lista de processos vazia; pulo a verificacao")
            self.processar_comandos()
            self.processar_conversa()
            self.avancar_assembleia()
            self.atualizar_obsidian()
            self.gravar(self.resumo())
            return
        for nome in self.servicos:
            if self.estado[nome]["situacao"] != "desligado":
                self.verificar_servico(nome, processos)
        if self.claude_proibido():
            for ident in self.delegados():
                self.parar_delegado(ident)
        self.processar_comandos()
        self.processar_cerebro()
        self.processar_conversa()
        self.processar_pedidos()
        self.vigiar_trabalho()
        self.vigiar_rodadas()
        self.gerenciar_equipe()
        self.rodar_esteira()
        self.avancar_assembleia()
        self.atualizar_obsidian()
        self.gravar(self.resumo())

    def resumo(self):
        from coordenador import pedidos as mesa
        return {"pid": os.getpid(), "desde": self.desde, "pulso_em": agora_iso(self.relogio()),
                # o incidente aberto da Mesa (o app mostra o cartão vermelho)
                "mesa_ilegivel": mesa.incidente_mesa() if self.pedidos else None,
                "versao": self._versao(), "servicos": self.estado,
                "acoes_pc": acoes_pc.catalogo(), "eventos": self.eventos[-100:],
                "cerebro": {"ligado": bool(self.cerebro)},
                "trabalho": self.trabalho, "equipe": self.equipe, "esteira": self.ultima_esteira,
                # SCR-7: o que o vigia das rodadas fez na ultima olhada com novidade
                "rodadas": self.rodadas}

    @staticmethod
    def _versao():
        try:
            return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                  text=True, check=False).stdout.strip() or "desconhecida"
        except OSError:
            return "desconhecida"

    def _avisar_trava_ocupada(self, dono):
        """COO-14: nao subir saia com 1 calado. A tarefa tenta a cada 5 min:
        a linha vai ao log no maximo uma vez por hora."""
        marca = pasta() / "trava_ocupada_avisada.txt"
        try:
            ultima = float(marca.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            ultima = 0.0
        agora = time.time()
        if agora - ultima < 3600:
            return
        try:
            marca.parent.mkdir(parents=True, exist_ok=True)
            marca.write_text(str(agora), encoding="utf-8")
        except OSError:
            pass
        self.log(f"[coordenador] trava de {dono or '?'} ativa; não subi")

    def pode_sair(self):
        """O reinicio pedido do proprio coordenador pode acontecer agora?"""
        if not self.sair_quando_seguro:
            return False
        if any(t.is_alive() for t in self.fundos.values()):
            return False                  # o vigia aplicando, os pedidos contratando...
        try:
            return bool(self.seguro("")[0])
        except Exception:                 # noqa: BLE001 - na duvida, fica
            return False

    def rodar(self, parar=lambda: False):
        trava = TravaUnica()
        if not trava.adquirir():
            # SCR-6 (14/10/2026): "ja ha um coordenador no ar" nao e falha.
            # Com 1, o RestartOnFailure (PT1M x999) da tarefa relancava a
            # cada minuto enquanto o outro (aberto pela linha de comando)
            # vivesse.
            self._avisar_trava_ocupada(trava.dono)
            return 0
        try:
            while not parar():
                if self.pode_sair():
                    self.log("[coordenador] saio para subir com o código novo "
                             "(a tarefa NeuralFights_coordenador me religa)")
                    break
                try:
                    self.pulso()
                except Exception as exc:          # noqa: BLE001 - um pulso ruim nao mata o laco
                    # 13/10/2026: um PermissionError do `estado.json` (o app
                    # lendo no instante do replace) saia daqui e o coordenador
                    # morria com as threads do vigia e dos pedidos
                    self.log(f"[coordenador] pulso falhou: {type(exc).__name__}: {exc}")
                time.sleep(PULSO_S)
        finally:
            trava.soltar()
        return 0
