# -*- coding: utf-8 -*-
"""A FILA SEM DESCANSO do am: ele nunca fica parado com coisa util a fazer.

Pedidos do Adrian (20/10/2026): "nao de um minuto de descanso para ele",
"realmente quero que entupa ele de trabalho", "quero que fique em 90%". Um
laco (servico `am` do coordenador DESTE PC) mantem o am CHEIO: lanca mais um
trabalho enquanto a CPU media de 30 s do am estiver abaixo de
`paralelo.cpu_alvo` (80%: com o que ja esta entrando, fica perto de 90) e
sobrar memoria para ele (a estimativa do tipo, aprendida pelo medidor do am,
mais a reserva), ate `paralelo.maximo` trabalhos. O proximo vem nesta ordem:

  1. PEDIDOS explicitos (fila em disco: `python -m builds.pc_am pedir ...`):
     duelo X, gravacao Y, testar Z, voz de uma roleta;
  2. DUELOS ate o teto (dias de estoque x consumo por dia: 14 x 6,25 = 88,
     o consumo por formato da geracao nova, a346e118, so lido). O estoque e o
     da publicacao (`noite.contar_estoque`);
  3. formatos do BLUE LOCK, teto por formato — so quando a fabrica entrar no
     ramo (hoje esta no WIP d542b2a): ate la, a fonte diz o motivo e passa;
  4. a VOZ das roletas generation_00126..00185 que sairam com o SAPI (so as
     nao publicadas; `trabalhos.roletas_da_voz`);
  5. o npm test dos RAMOS do Blue Lock (o `VigiaDeRamos` com o teste no am),
     no maximo uma olhada a cada `ramos_a_cada_min`;
  6. sem nada util: as SUITES inteiras (pytest das partes + npm test do
     Blue Lock) no commit atual, uma vez por commit (de novo depois de
     `repetir_suites_h`, ou JA se a CPU ficar abaixo de `cpu_ociosa` (70%)
     por `ociosa_min` (10) com nada mais a fazer), placar em `suites.json`.

Guardas: teto por tipo (estoque alem do teto = nao faz), quantos de cada
grupo ao mesmo tempo (`max_por_grupo`: um duelo do estoque por vez — dois
sorteariam o mesmo par —, uma voz por vez), disco livre no am (>=
`disco_minimo_am_gb`) e aqui (o que volta), limpeza do que ja voltou, saude
do am (CPU, memoria, temperatura se a placa informar), grupo que falha 3
vezes seguidas descansa 1 h, UM aviso no Telegram por episodio (am fora,
disco, parado sem motivo mais de 15 min). Tudo e `cair_para_aqui=False`: a
fila NUNCA poe trabalho pesado neste PC.

O que vem depois (o Adrian quer este PC inteiro no am): trabalho com
navegador logado (historias, carteiro, publicacao) entra como mais uma fonte,
com `recursos=["perfil:<servico>__<canal>"]` (exclusivo no am, como as travas
de perfil daqui) e o perfil de memoria `navegador` (Chrome aberto e o que
enche os 8 GB: a memoria e o limite real, nao a CPU).

O estado para o app e a Vila: `%LOCALAPPDATA%\\neural-fights\\pc_am\\fila.json`
("o am esta fazendo X desde HH:MM, Y desde HH:MM; CPU 30 s 84%; fila: ...").

Desligada por padrao: `config/pc_am.json -> fila.ligada` (`python -m
builds.pc_am fila ligar`); o servico `am` do coordenador NAO esta registrado
(26/10/2026): o laco roda a mao, `python -m builds.pc_am fila rodar`.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from . import maquina, sonda
from . import relogio as janela_das_postagens

PADRAO_FILA = {
    "ligada": False,
    "dias_de_estoque_duelo": 14,
    "consumo_duelo_por_dia": 6.25,
    "teto_bluelock_por_formato": 10,
    "disco_minimo_am_gb": 15,
    "disco_minimo_aqui_gb": 10,
    "aviso_parado_min": 15,
    "cpu_ociosa": 70,
    "ociosa_min": 10,
    "ramos_a_cada_min": 30,
    "repetir_suites_h": 12,
    "descanso_depois_de_falhas_min": 60,
    "falhas_para_descansar": 3,
    "intervalo_s": 10,
    "max_por_grupo": {"duelo": 1, "voz": 1, "ramos": 1, "bluelock": 1, "pedido": 2, "suite": 3},
}
# Parado com motivo: nao e alarme.
MOTIVOS_JUSTOS = ("fila desligada", "nada util")


def config_da_fila(cfg: dict | None = None) -> dict:
    cfg = cfg if cfg is not None else maquina.carregar_config()
    fila = json.loads(json.dumps(PADRAO_FILA))
    if isinstance(cfg.get("fila"), dict):
        for chave, valor in cfg["fila"].items():
            if str(chave).startswith("_"):
                continue
            if isinstance(valor, dict) and isinstance(fila.get(chave), dict):
                fila[chave].update(valor)
            else:
                fila[chave] = valor
    return fila


def ligada(cfg: dict | None = None) -> bool:
    return config_da_fila(cfg).get("ligada") is True


def teto_de_duelos(cfg: dict | None = None) -> int:
    fila = config_da_fila(cfg)
    return int(math.ceil(float(fila["dias_de_estoque_duelo"]) * float(fila["consumo_duelo_por_dia"]) - 1e-9))


def arquivo(nome: str) -> Path:
    return maquina.runtime() / nome


def _ler(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def _gravar(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(f".{uuid.uuid4().hex[:6]}.tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temporario, caminho)


# ---------------------------------------------------------------- pedidos
TIPOS_DE_PEDIDO = ("duelo", "bluelock", "testar", "voz")


def _mexer_nos_pedidos(funcao):
    from .. import travas
    with travas.trava("pc_am_pedidos", esperar=30) as minha:
        if not minha:
            raise RuntimeError("a fila de pedidos do am esta ocupada; tente de novo")
        pedidos = _ler(arquivo("pedidos.json"), [])
        resultado, pedidos = funcao(pedidos)
        _gravar(arquivo("pedidos.json"), pedidos)
        return resultado


def pedir(tipo: str, **argumentos) -> dict:
    """Poe um pedido explicito no fim da fila em disco (prioridade 1)."""
    if tipo not in TIPOS_DE_PEDIDO:
        raise ValueError(f"tipo de pedido desconhecido: {tipo} (vale {', '.join(TIPOS_DE_PEDIDO)})")
    pedido = {"id": f"p-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}", "tipo": tipo,
              "argumentos": argumentos, "pedido_em": datetime.now().isoformat(timespec="seconds")}
    return _mexer_nos_pedidos(lambda pedidos: (pedido, pedidos + [pedido]))


def _tirar_pedido() -> dict | None:
    return _mexer_nos_pedidos(lambda pedidos: (pedidos[0], pedidos[1:]) if pedidos else (None, pedidos))


def _devolver_pedido(pedido: dict) -> None:
    """O pedido escolhido nao coube agora: volta para a FRENTE da fila."""
    _mexer_nos_pedidos(lambda pedidos: (None, [pedido] + pedidos))


def pedidos_na_fila() -> list[dict]:
    return _ler(arquivo("pedidos.json"), [])


# --------------------------------------------------------------- tarefas
@dataclass
class Tarefa:
    tipo: str                         # pedido | duelo | bluelock | voz | ramos | suite
    descricao: str
    rodar: Callable[[], object]
    traz_produto: bool = False        # precisa de disco AQUI
    chave: str = ""
    perfil: str = "testes"            # a estimativa de CPU/memoria (maquina.PERFIS_PADRAO)
    grupo: str = ""                   # para `max_por_grupo` (padrao: o tipo)
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        self.grupo = self.grupo or self.tipo
        self.chave = self.chave or self.descricao


class Fila:
    """Um `passo` = colhe o que terminou, olha o am e lanca quantos couberem.
    `rodar()` = o laco. `sincrono=True` (testes) roda cada tarefa no proprio
    passo, sem thread."""

    def __init__(self, cfg: dict | None = None, *, transporte=None, avisar: Callable | None = None,
                 relogio: Callable = datetime.now, dorme: Callable = time.sleep,
                 fontes: list | None = None, disco_aqui: Callable | None = None, log=print,
                 sincrono: bool = False):
        self.cfg = cfg if cfg is not None else maquina.carregar_config()
        self.t = transporte
        self.avisar = avisar or maquina.avisar_real
        self.relogio = relogio
        self.dorme = dorme
        self.log = log
        self.sincrono = sincrono
        self.disco_aqui = disco_aqui or self._disco_aqui_real
        self.fontes = fontes if fontes is not None else [
            ("pedido", self.fonte_pedidos), ("duelo", self.fonte_duelos),
            ("bluelock", self.fonte_bluelock), ("voz", self.fonte_voz),
            ("ramos", self.fonte_ramos), ("suite", self.fonte_suites)]
        self.estado = _ler(arquivo("fila.json"), {})
        if not isinstance(self.estado, dict):
            self.estado = {}
        self.estado["rodando"] = []          # o que estava rodando antes de subir nao e meu
        self.rodando: dict[str, dict] = {}
        self._trava = threading.Lock()
        self.ultimo_lancamento = None

    # --- utilidades -------------------------------------------------
    @property
    def fila(self) -> dict:
        return config_da_fila(self.cfg)

    def _agora_iso(self) -> str:
        return self.relogio().isoformat(timespec="seconds")

    def _transporte(self):
        if self.t is None:
            self.t = maquina.TransporteSsh(self.cfg)
        return self.t

    def _kw(self) -> dict:
        """Como a fila chama os trabalhos: so no am, ja admitido pela fila."""
        cfg = dict(self.cfg, disco_minimo_gb=self.fila["disco_minimo_am_gb"])
        return {"cfg": cfg, "transporte": self._transporte(), "cair_para_aqui": False,
                "cair_na_falha": False, "avisar": lambda texto: None, "dorme": self.dorme,
                "admitir": False, "espera": 900,
                "ignorar_janela": True}      # o passo ja respondeu pela janela

    @staticmethod
    def _disco_aqui_real() -> float:
        return shutil.disk_usage(maquina.RAIZ_RB).free / 1024 ** 3

    def _descansando(self, grupo: str) -> bool:
        ate = (self.estado.get("descanso") or {}).get(grupo)
        return bool(ate) and self._agora_iso() < ate

    def _rodando_do_grupo(self, grupo: str) -> int:
        return sum(1 for r in self.rodando.values() if r["tarefa"].grupo == grupo)

    def _rodando_chaves(self) -> set:
        return {r["tarefa"].chave for r in self.rodando.values()}

    # --- as fontes, em ordem ---------------------------------------
    def fonte_pedidos(self):
        pedido = _tirar_pedido()
        if not pedido:
            return None, "nenhum pedido"
        from . import trabalhos
        a = pedido.get("argumentos") or {}
        kw = self._kw()
        tipo = pedido["tipo"]
        perfil, grupo = {"duelo": ("duelo", "pedido"), "bluelock": ("bluelock", "bluelock"),
                         "testar": ("testes", "pedido"), "voz": ("voz", "voz")}[tipo]
        if tipo == "duelo":
            rodar = lambda: trabalhos.duelo(p1=a.get("p1"), p2=a.get("p2"), seed=a.get("seed"),  # noqa: E731
                                            cenario=a.get("arena"), forcar=True, **kw)
        elif tipo == "bluelock":
            rodar = lambda: trabalhos.bluelock_gravar(list(a.get("argumentos") or []), forcar=True, **kw)  # noqa: E731
        elif tipo == "testar":
            rodar = lambda: trabalhos.testar_no_am(a["pasta"], list(a.get("extras") or []),  # noqa: E731
                                                   forcar=True, **kw)
        else:
            rodar = lambda: trabalhos.refazer_voz(a["generation"], **kw)  # noqa: E731
        return Tarefa("pedido", f"pedido {pedido['id']}: {tipo} {json.dumps(a, ensure_ascii=False)[:80]}",
                      rodar, traz_produto=tipo != "testar", chave=pedido["id"], perfil=perfil, grupo=grupo,
                      extra={"pedido": pedido}), ""

    def contar_duelos(self) -> int:
        from ..pipeline import noite
        return int(noite.contar_estoque().get("duelo", 0))

    def fonte_duelos(self):
        teto = teto_de_duelos(self.cfg)
        estoque = self.contar_duelos()
        self.estado.setdefault("contas", {})["duelos"] = {"estoque": estoque, "teto": teto}
        if estoque >= teto:
            return None, f"estoque de duelos cheio ({estoque}/{teto})"
        from . import trabalhos
        kw = self._kw()
        return Tarefa("duelo", f"duelo para o estoque ({estoque + 1}/{teto})",
                      lambda: trabalhos.duelo(forcar=True, **kw), traz_produto=True, perfil="duelo",
                      chave=f"duelo-{estoque}"), ""

    def fonte_bluelock(self):
        try:
            import importlib.util
            tem = importlib.util.find_spec("bluelock.formatos") is not None
        except (ImportError, ValueError):
            tem = False
        if not tem:
            return None, "a fabrica do Blue Lock nao esta no ramo (WIP d542b2a)"
        return None, "fabrica do Blue Lock presente: falta ligar a fonte (docs/sessoes/pc-am.md)"

    def fonte_voz(self):
        from . import trabalhos
        try:
            faltam = trabalhos.roletas_da_voz()
        except Exception as exc:                               # noqa: BLE001
            return None, f"voz: nao li o estoque ({type(exc).__name__})"
        self.estado.setdefault("contas", {})["voz"] = {"faltam": len(faltam)}
        livres = [g for g in faltam if g not in self._rodando_chaves()]
        if not livres:
            return None, "voz das roletas em dia" if not faltam else "voz: as que faltam ja estao rodando"
        gid = livres[0]
        kw = self._kw()
        return Tarefa("voz", f"voz refeita de {gid} ({len(faltam)} na fila)",
                      lambda: trabalhos.refazer_voz(gid, **kw), traz_produto=True, chave=gid, perfil="voz"), ""

    def fonte_ramos(self):
        ultima = self.estado.get("ramos_em")
        minutos = float(self.fila["ramos_a_cada_min"])
        if ultima and self.relogio() - datetime.fromisoformat(ultima) < timedelta(minutes=minutos):
            return None, "ramos olhados ha pouco"
        try:
            from bluelock.ramos import VigiaDeRamos
        except ImportError:
            return None, "bluelock.ramos fora do caminho"
        from . import trabalhos
        kw = self._kw()

        def testar(sha, ramo):
            try:
                return trabalhos.ficha_de_ramo(trabalhos.testar_blue_lock_no_am(sha, **kw))
            except (maquina.AmFora, maquina.FalhaNoAm) as exc:
                # nao memoriza: o vigia guarda o que vier com rodou=True
                raise RuntimeError(f"npm test do ramo {ramo} no am: {exc}") from exc

        def rodar():
            vigia = VigiaDeRamos(testar=testar, pode_pesado=lambda agora=None: (True, ""))
            return vigia.olhar(avisar=True)
        self.estado["ramos_em"] = self._agora_iso()
        return Tarefa("ramos", "vigia dos ramos do Blue Lock (npm test no am)", rodar, perfil="npm"), ""

    def suites(self) -> list[str]:
        try:
            import testar as raiz_testar
            pastas = []
            for nome, cwd, comando in raiz_testar.SUITES:
                alvo = comando[-1]
                topo = Path(cwd).name if Path(cwd) != raiz_testar.RAIZ else ""
                pastas.append(f"{topo}/{alvo}".strip("/") if topo else alvo)
            return pastas
        except Exception:                                      # noqa: BLE001
            return ["mimetizar/tests", "random_builds/tests", "historias/tests", "remoto", "ias", "painel",
                    "visao/tests", "coordenador", "esteira_sprites", "palco/testes", "ferramentas",
                    "bluelock", "tests"]

    def fonte_suites(self, *, encher: bool = False):
        """`encher`: o am esta ocioso ha tempo (CPU baixa): roda de novo a
        suite feita ha mais tempo, sem esperar `repetir_suites_h`."""
        registro = _ler(arquivo("suites.json"), {})
        commit = maquina.estado_do_codigo(maquina.RAIZ)["commit"]
        if registro.get("commit") != commit:
            registro = {"commit": commit, "suites": {}}
        feitas = registro.get("suites") or {}
        repetir = timedelta(hours=float(self.fila["repetir_suites_h"]))
        candidatas = [n for n in self.suites() + ["npm:blue-lock"] if n not in self._rodando_chaves()]
        if encher:
            candidatas.sort(key=lambda n: (feitas.get(n) or {}).get("em") or "")
        from . import trabalhos
        kw = self._kw()
        for nome in candidatas:
            quando = (feitas.get(nome) or {}).get("em")
            if not encher and quando and self.relogio() - datetime.fromisoformat(quando) < repetir:
                continue
            if nome == "npm:blue-lock":
                rodar, perfil = (lambda: trabalhos.testar_blue_lock_no_am(None, **kw)), "npm"
            else:
                rodar, perfil = (lambda n=nome: trabalhos.testar_no_am(n, forcar=True, **kw)), "testes"
            return Tarefa("suite", f"suite {nome} no commit {commit[:10]}", rodar, chave=nome, perfil=perfil,
                          extra={"commit": commit, "encher": encher}), ""
        return None, "nada util: as suites do commit atual ja rodaram"

    # --- avisos e estado ------------------------------------------------
    def _avisar_uma_vez(self, chave: str, texto: str) -> None:
        avisados = self.estado.setdefault("avisados", {})
        if avisados.get(chave):
            return
        avisados[chave] = self._agora_iso()
        try:
            self.avisar(texto)
        except Exception:                                      # noqa: BLE001
            pass

    def _limpar_aviso(self, *chaves) -> None:
        avisados = self.estado.setdefault("avisados", {})
        for chave in chaves:
            avisados.pop(chave, None)

    def _parado(self, motivo: str) -> dict:
        """Nada rodando e nada entrou. Com algo rodando, e so `espera`."""
        if self.rodando:
            self.estado["motivo_espera"] = motivo
            self._salvar()
            return {"rodou": False, "motivo": motivo, "rodando": len(self.rodando)}
        self.estado["parado_desde"] = self.estado.get("parado_desde") or self._agora_iso()
        self.estado["motivo_parado"] = motivo
        # am fora e disco do am cheio ja tem o aviso proprio (uma vez): nao repete
        justo = motivo.startswith(MOTIVOS_JUSTOS + ("am fora", "disco do am"))
        desde = datetime.fromisoformat(self.estado["parado_desde"])
        if not justo and self.relogio() - desde >= timedelta(minutes=float(self.fila["aviso_parado_min"])):
            self._avisar_uma_vez("parado", f"🖥 O PC am está parado há mais de "
                                 f"{int(self.fila['aviso_parado_min'])} min: {motivo}")
        self._salvar()
        return {"rodou": False, "motivo": motivo}

    def _salvar(self) -> None:
        self.estado["atualizado"] = self._agora_iso()
        self.estado["ligada"] = ligada(self.cfg)
        self.estado["pedidos"] = [f"{p['tipo']} {p['id']}" for p in pedidos_na_fila()][:10]
        self.estado["rodando"] = [{"tipo": r["tarefa"].tipo, "descricao": r["tarefa"].descricao,
                                   "desde": r["desde"]} for r in self.rodando.values()]
        self.estado["fazendo"] = self.estado["rodando"][0] if self.estado["rodando"] else None
        if self.estado["rodando"]:
            texto = "o am está fazendo " + ", ".join(f"{r['descricao']} desde {r['desde'][11:16]}"
                                                     for r in self.estado["rodando"])
        else:
            texto = f"o am está parado: {self.estado.get('motivo_parado') or '?'}"
        am = self.estado.get("am") or {}
        if am.get("cpu_30s") is not None:
            texto += f"; CPU 30 s {am['cpu_30s']:.0f}%"
        if am.get("memoria_livre_mb") is not None:
            texto += f", livre {am['memoria_livre_mb'] / 1024:.1f} GB"
        if self.estado["pedidos"]:
            texto += f"; fila: {', '.join(self.estado['pedidos'][:3])}"
        self.estado["texto"] = texto
        _gravar(arquivo("fila.json"), self.estado)

    # --- escolher, lancar, colher ----------------------------------
    def _escolher(self, sem_produto: bool, *, encher: bool = False):
        """(tarefa, motivos de cada fonte que passou, BLOQUEIOS). Bloqueio e o
        que nao e "nada a fazer": disco, descanso por falha, fonte quebrada."""
        motivos, bloqueios = [], []
        limites = self.fila.get("max_por_grupo") or {}
        for nome, fonte in self.fontes:
            if self._descansando(nome):
                bloqueios.append(f"{nome}: descansando depois de falhas seguidas")
                continue
            if sem_produto and nome in ("duelo", "voz", "bluelock"):
                bloqueios.append(f"{nome}: disco daqui cheio")
                continue
            if nome in limites and self._rodando_do_grupo(nome) >= int(limites[nome]):
                motivos.append(f"{nome}: {self._rodando_do_grupo(nome)} rodando (maximo do grupo)")
                continue
            try:
                tarefa, motivo = fonte(encher=True) if (encher and nome == "suite") else fonte()
            except Exception as exc:                           # noqa: BLE001
                bloqueios.append(f"{nome}: {type(exc).__name__}: {str(exc)[:120]}")
                continue
            if tarefa is not None:
                if sem_produto and tarefa.traz_produto:
                    self._desfazer(tarefa)
                    bloqueios.append(f"{nome}: disco daqui cheio")
                    continue
                if tarefa.grupo in limites and self._rodando_do_grupo(tarefa.grupo) >= int(limites[tarefa.grupo]):
                    self._desfazer(tarefa)
                    motivos.append(f"{tarefa.grupo}: maximo do grupo rodando")
                    continue
                return tarefa, motivos, bloqueios
            motivos.append(f"{nome}: {motivo}")
        return None, motivos, bloqueios

    @staticmethod
    def _desfazer(tarefa: Tarefa) -> None:
        if tarefa.extra.get("pedido"):
            _devolver_pedido(tarefa.extra["pedido"])

    def _lancar(self, tarefa: Tarefa) -> None:
        ident = uuid.uuid4().hex[:8]
        registro = {"tarefa": tarefa, "desde": self._agora_iso(), "inicio": time.monotonic(),
                    "estimativa_mb": float(maquina.estimativa(tarefa.perfil)["memoria_mb"]), "ficha": None}
        with self._trava:
            self.rodando[ident] = registro
        self.ultimo_lancamento = time.monotonic()
        self.log(f"[pc_am fila] {tarefa.descricao}")
        self._limpar_aviso("parado")
        self.estado["parado_desde"] = None
        self.estado["motivo_parado"] = ""
        self.estado["motivo_espera"] = ""
        self._salvar()

        def trabalhar():
            ficha = {"tipo": tarefa.tipo, "descricao": tarefa.descricao, "inicio": registro["desde"]}
            try:
                valor = tarefa.rodar()
            except maquina.AmOcupado as exc:
                ficha.update(ok=False, erro=f"am cheio: {exc}", ocupado=True)
            except maquina.AmFora as exc:
                ficha.update(ok=False, erro=f"am fora: {exc}")
            except Exception as exc:                           # noqa: BLE001
                ficha.update(ok=False, erro=f"{type(exc).__name__}: {str(exc)[:300]}")
            else:
                ficha.update(ok=True, resultado=_resumo(valor))
            ficha["segundos"] = round(time.monotonic() - registro["inicio"], 1)
            ficha["fim"] = self._agora_iso()
            registro["ficha"] = ficha

        if self.sincrono:
            trabalhar()
        else:
            registro["fio"] = threading.Thread(target=trabalhar, name=f"pc_am-{tarefa.tipo}", daemon=True)
            registro["fio"].start()

    def colher(self) -> list[dict]:
        """O que terminou desde o ultimo passo: historico, suites, descanso."""
        prontos = []
        with self._trava:
            for ident, registro in list(self.rodando.items()):
                if registro["ficha"] is not None:
                    prontos.append(registro)
                    del self.rodando[ident]
        for registro in prontos:
            self._depois(registro["tarefa"], registro["ficha"])
        return [r["ficha"] for r in prontos]

    def esperar_todos(self, prazo: float = 60) -> None:
        fim = time.monotonic() + prazo
        while self.rodando and time.monotonic() < fim:
            for registro in list(self.rodando.values()):
                if registro.get("fio"):
                    registro["fio"].join(timeout=0.2)
            self.colher()

    def _depois(self, tarefa: Tarefa, ficha: dict) -> None:
        falhas = self.estado.setdefault("falhas_seguidas", {})
        nome = tarefa.tipo
        if ficha.get("ok") or ficha.get("ocupado"):
            falhas[nome] = 0 if ficha.get("ok") else falhas.get(nome, 0)
        else:
            falhas[nome] = int(falhas.get(nome, 0)) + 1
            if falhas[nome] >= int(self.fila["falhas_para_descansar"]):
                ate = self.relogio() + timedelta(minutes=float(self.fila["descanso_depois_de_falhas_min"]))
                self.estado.setdefault("descanso", {})[nome] = ate.isoformat(timespec="seconds")
                falhas[nome] = 0
        if ficha.get("ocupado"):
            self._desfazer(tarefa)              # o pedido volta para a frente da fila
        if tarefa.tipo == "suite" and ficha.get("ok"):
            registro = _ler(arquivo("suites.json"), {})
            if registro.get("commit") != tarefa.extra.get("commit"):
                registro = {"commit": tarefa.extra.get("commit"), "suites": {}}
            resultado = ficha.get("resultado") or {}
            registro.setdefault("suites", {})[tarefa.chave] = {
                "em": ficha["fim"], "rc": resultado.get("rc"), "placar": resultado.get("placar"),
                "segundos": ficha["segundos"]}
            _gravar(arquivo("suites.json"), registro)
        self.estado["ultimo"] = ficha
        try:
            with open(arquivo("fila_historico.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(ficha, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass
        self._salvar()

    # --- o passo ----------------------------------------------------
    def passo(self) -> dict:
        self.colher()
        if not ligada(self.cfg):
            return self._parado("fila desligada (config/pc_am.json -> fila.ligada)")
        liberado, porque = janela_das_postagens.liberado()
        if not liberado:
            return self._parado(f"janela das postagens: {porque}")
        t = self._transporte()
        if isinstance(t, maquina.TransporteSsh):
            # a SONDA barata antes da saude (26/10/2026): am desligado nao custa
            # o SSH da saude a cada passo e NAO e alarme (fila parada, sem aviso).
            lida = sonda.sondar(self.cfg)
            if lida.get("estado") == sonda.INDISPONIVEL:
                return self._parado(f"am fora: sonda ({lida.get('motivo') or 'sem resposta'})")
        try:
            saude = t.chamar("saude", {"temperatura": True, "cpu_s": 3}, prazo=60)
        except maquina.AmFora as exc:
            self._avisar_uma_vez("fora", f"🖥 PC am fora ({exc}). A fila dele espera; nada vem para este PC.")
            return self._parado(f"am fora: {exc}")
        self._limpar_aviso("fora")
        par = maquina.paralelo(self.cfg)
        maquina.registrar_cpu(saude.get("cpu"))
        media = maquina.cpu_media(float(par["janela_cpu_s"]))
        self.estado["am"] = {k: saude.get(k) for k in ("disco_livre_gb", "memoria_livre_mb", "cpu",
                                                         "temperatura_c", "agora")}
        self.estado["am"]["cpu_30s"] = media
        self.estado["am"]["trabalhos"] = len(saude.get("ativos") or [])
        disco = saude.get("disco_livre_gb")
        if disco is not None and disco < float(self.fila["disco_minimo_am_gb"]):
            self._avisar_uma_vez("disco_am", f"🖥 O disco do PC am está com {disco} GB livres "
                                 f"(mínimo {self.fila['disco_minimo_am_gb']}): a fila parou.")
            return self._parado(f"disco do am cheio ({disco} GB)")
        self._limpar_aviso("disco_am")
        aqui = self.disco_aqui()
        sem_produto = aqui < float(self.fila["disco_minimo_aqui_gb"])
        if sem_produto:
            self._avisar_uma_vez("disco_aqui", f"🖥 O disco deste PC está com {aqui:.0f} GB livres: "
                                 "o am só roda o que não traz arquivo (testes).")
        else:
            self._limpar_aviso("disco_aqui")
        # a CPU ociosa ha tempo puxa o nivel 6 (as suites) mesmo em dia
        ociosa = float(self.fila["cpu_ociosa"])
        if media is not None and media < ociosa:
            self.estado["cpu_baixa_desde"] = self.estado.get("cpu_baixa_desde") or self._agora_iso()
        else:
            self.estado["cpu_baixa_desde"] = None
        encher = bool(self.estado.get("cpu_baixa_desde")) and self.relogio() - datetime.fromisoformat(
            self.estado["cpu_baixa_desde"]) >= timedelta(minutes=float(self.fila["ociosa_min"]))
        # quem acabou de entrar ainda nao chegou ao pico: a CPU de 30 s nao o
        # mostra. Espera a janela antes do proximo, e conta a memoria dele.
        janela = float(par["janela_cpu_s"])
        if len(self.rodando) >= int(par["maximo"]):
            return self._parado(f"am cheio: {len(self.rodando)} trabalhos da fila (maximo {par['maximo']})")
        if self.rodando and self.ultimo_lancamento and time.monotonic() - self.ultimo_lancamento < janela \
                and not self.sincrono:
            return self._parado(f"esperando a CPU mostrar o ultimo que entrou ({janela:.0f} s)")
        recentes = sum(r["estimativa_mb"] for r in self.rodando.values()
                       if time.monotonic() - r["inicio"] < 2 * janela)
        tarefa, motivos, bloqueios = self._escolher(sem_produto)
        if tarefa is None and encher:
            tarefa, mais, _ = self._escolher(sem_produto, encher=True)
            motivos += mais
        self.estado["motivos"] = motivos + bloqueios
        if tarefa is None:
            if bloqueios:
                return self._parado("sem trabalho possivel: " + "; ".join(bloqueios))
            return self._parado("nada util: " + "; ".join(motivos))
        saude_com_os_meus = dict(saude)
        ok, motivo = maquina.cabe(saude_com_os_meus, tarefa.perfil, self.cfg, cpu=media, recentes_mb=recentes)
        if not ok:
            self._desfazer(tarefa)
            return self._parado(f"am cheio: {motivo}")
        self._lancar(tarefa)
        self._salvar()
        if self.sincrono:
            self.colher()
        return {"rodou": True, "lancou": tarefa.descricao, "rodando": len(self.rodando),
                **({"ficha": self.estado.get("ultimo")} if self.sincrono else {})}

    # --- o laco -----------------------------------------------------
    def rodar(self, voltas: int | None = None) -> None:
        feitas = 0
        while voltas is None or feitas < voltas:
            self.cfg = maquina.carregar_config()
            try:
                self.passo()
            except Exception as exc:                           # noqa: BLE001
                self.log(f"[pc_am fila] o passo quebrou: {type(exc).__name__}: {exc}")
            feitas += 1
            self.dorme(float(self.fila["intervalo_s"]))


def _resumo(valor) -> dict:
    """O que cabe no historico de um retorno de trabalho."""
    if isinstance(valor, maquina.Resultado):
        from .trabalhos import placar
        return {"onde": valor.onde, "rc": valor.rc, "segundos": valor.segundos,
                "destino": str(valor.destino) if valor.destino else None, "placar": placar(valor.log),
                "etapas": valor.etapas}
    if isinstance(valor, Path):
        return {"destino": str(valor)}
    if isinstance(valor, dict):
        return {k: v for k, v in valor.items() if k in ("acao", "testados_agora", "pesado")}
    return {"valor": str(valor)[:200]}


def estado_para_painel() -> dict:
    """O que o app e a Vila leem (sem tocar no am)."""
    return _ler(arquivo("fila.json"), {"texto": "a fila do am nunca rodou"})


def cuida_dos_duelos(cfg: dict | None = None, *, frescor_min: float = 10) -> bool:
    """A geracao daqui deixa os duelos para o am? So com a chave do duelo,
    a fila ligada E viva (estado de menos de `frescor_min`) E o am nao fora:
    am fora ou fila parada = a noite gera aqui, como sempre."""
    cfg = cfg if cfg is not None else maquina.carregar_config()
    return maquina.ligado("duelo", cfg) and viva(cfg, frescor_min=frescor_min)


def viva(cfg: dict | None = None, *, frescor_min: float = 10) -> bool:
    """A fila esta ligada, gravou estado ha pouco e o am nao esta fora?"""
    cfg = cfg if cfg is not None else maquina.carregar_config()
    if not ligada(cfg):
        return False
    estado = estado_para_painel()
    try:
        idade = datetime.now() - datetime.fromisoformat(estado.get("atualizado"))
    except (TypeError, ValueError):
        return False
    if idade > timedelta(minutes=frescor_min):
        return False
    motivo = str(estado.get("motivo_parado") or "")
    return not motivo.startswith(("am fora", "disco do am", "fila desligada"))
