# -*- coding: utf-8 -*-
"""A Vila para o celular: o mundo, quem esta em cada predio, e o placar.

A Vila do painel (`painel/paginas/vila.py`) e uma tela Tk: o cenario e uma
imagem so, composta por `vila.motor`, e os bots sao animados por cima. Aqui
vale a mesma divisao, com a fronteira na rede:

  - o CENARIO vai pronto, como PNG (`/vila.png`): compor custa 0,03 s e 46 KB,
    e o celular nao precisa refazer chao, decoracao e predios;
  - as POSICOES sao calculadas aqui, uma vez (`mundo()`), com as MESMAS
    contas do painel (porta = meio da base do predio) — para o app nao ter
    uma segunda geometria que possa divergir;
  - o ESTADO (`estado()`) e o que muda: quem trabalha, quem deu erro, ha
    quanto tempo, e o paralelismo.

TRES CUIDADOS QUE VIERAM DE FORA:
  1. `travas.estado()` responde "ocupada?" PEGANDO a trava por um instante —
     e um celular perguntando a cada 3 s faria o dono de verdade ouvir
     "ocupado" e desistir da rodada. Aqui a sonda e a de `acoes.trava_ocupada`,
     que so tenta LER o byte trancado.
  2. `panorama.resumo()` leva ~159 s na primeira conta (medido em 27/09/2026)
     e so depois fica em cache. Isso NAO pode acontecer dentro de um GET: o
     placar e calculado numa thread e servido com a idade dele.
  3. `deepseek` e `mimetizar` sao fabricas do diario que NAO tem predio no
     mapa. Elas ganham lugar na fila em frente a casa, como no painel, e o
     app mostra que elas nao tem predio (em vez de escondê-las).
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path

from .painel_dados import limpar

PLACAR_VALE_S = 30 * 60          # o resumo e caro; meia hora basta
ESCALA = 2
SERVICOS = ("picasso", "digen", "dreamface", "chatgpt", "gemini", "deepseek",
            "tiktok", "youtube_web")
CANAIS = ("builds", "historias")


def _motor():
    from vila import motor
    return motor


def _atividade():
    from builds import atividade
    return atividade


def _travas():
    from builds import travas
    return travas


def _trava_ocupada(nome: str):
    from .acoes import trava_ocupada
    return trava_ocupada(nome)


# ------------------------------------------------------------------ mundo
_MUNDO: dict | None = None
_MUNDO_TRAVA = threading.Lock()


def caminho_sprites() -> Path:
    motor = _motor()
    cfg = motor.carregar()
    folha = (cfg.get("folhas") or {}).get("base") or {}
    raiz = Path(motor.__file__).resolve().parent
    return raiz / str(folha.get("arquivo") or "sprites/base.png")


def versao_do_mundo() -> str:
    """Muda quando o cenario muda (a Oficina salvou, ou a folha foi trocada).

    E o que deixa o app guardar `/vila.png` por um dia sem ficar preso a um
    cenario velho: a versao vai junto no `/api/vila` e entra na URL.
    """
    partes = []
    for caminho in (Path(_motor().__file__).resolve().parent / "config.json",
                    caminho_sprites()):
        try:
            estado = caminho.stat()
            partes.append(f"{int(estado.st_mtime)}-{estado.st_size}")
        except OSError:
            partes.append("0")
    return ".".join(partes)


def png_do_mundo(escala: int = ESCALA) -> bytes:
    """O cenario inteiro (chao, decoracao, predios) como PNG."""
    import io

    motor = _motor()
    cfg = motor.carregar()
    if not motor.pronto(cfg):
        raise RuntimeError("a vila ainda nao tem cenario")
    imagem = motor.compor_mundo(cfg, motor.Atlas(cfg), escala)
    saco = io.BytesIO()
    imagem.save(saco, "PNG", optimize=True)
    return saco.getvalue()


def _porta(pos: dict, larg: float, alt: float, lado: int) -> list:
    """O pe do predio, no meio: e para la que o bot anda (a conta do painel)."""
    return [(pos["x"] + larg / 2) * lado, (pos["y"] + alt) * lado + 4]


def mundo(forcar: bool = False) -> dict:
    """Geometria e sprites, em pixels. Nao muda entre chamadas."""
    global _MUNDO
    with _MUNDO_TRAVA:
        if _MUNDO is not None and not forcar:
            return _MUNDO
        motor = _motor()
        atividade = _atividade()
        cfg = motor.carregar()
        mapa = cfg["mapa"]
        lado = int(cfg["tile"]) * ESCALA
        casa = mapa.get("casa") or {"x": mapa["larg"] // 2, "y": mapa["alt"] // 2}
        larg_casa, alt_casa = motor.tamanho(cfg, "predio.casa")
        porta_casa = _porta(casa, larg_casa, alt_casa, lado)

        predios = {}
        lugares = {}
        for i, nome in enumerate(atividade.FABRICAS):
            dados = atividade.FABRICAS[nome]
            pos = (mapa.get("predios") or {}).get(nome)
            # Fabrica sem predio fica na fila em frente a casa — a mesma
            # regra do painel, para os dois desenhos combinarem.
            fila = [porta_casa[0] + (i - 3) * lado * 0.9, porta_casa[1] + lado * 0.6]
            if pos:
                larg, alt = motor.tamanho(cfg, f"predio.{nome}")
                trabalho = _porta(pos, larg, alt, lado)
                predios[nome] = {
                    "x": pos["x"] * lado, "y": pos["y"] * lado,
                    "larg": larg * lado, "alt": alt * lado,
                    "topo": pos["y"] * lado, "porta": trabalho}
            else:
                trabalho = list(fila)
            lugares[nome] = {
                "rotulo": dados.get("rotulo", nome), "emoji": dados.get("emoji", ""),
                "faz": dados.get("faz", ""), "casa": fila, "trabalho": trabalho,
                "tem_predio": bool(pos), "fase": i * 1.3}

        papeis = cfg.get("papeis") or {}
        folha = (cfg.get("folhas") or {}).get("base") or {}
        _MUNDO = {
            "versao": versao_do_mundo(),
            "tamanho": [mapa["larg"] * lado, mapa["alt"] * lado],
            "lado": lado, "escala": ESCALA, "tile": int(cfg["tile"]),
            "colunas": 256 // int(folha.get("tile_w") or cfg["tile"]),
            "fundo": mapa.get("fundo") or "#17251a",
            "casa": {"x": casa["x"] * lado, "y": casa["y"] * lado,
                     "larg": larg_casa * lado, "alt": alt_casa * lado,
                     "porta": porta_casa},
            "predios": predios,
            "lugares": lugares,
            "sprites": {nome: {"frames": papel.get("frames") or [],
                               "fps": papel.get("fps") or 6}
                        for nome, papel in papeis.items()
                        if nome.startswith(("bot.", "fx."))},
        }
        return _MUNDO


# ---------------------------------------------------------------- estado
def _por_canal() -> dict:
    """{fabrica: [{canal, status, detalhe, ha_s}]} — dois canais, dois trabalhos."""
    atividade = _atividade()
    saida: dict = {}
    try:
        bruto = atividade.estado_por_canal()
    except Exception:                                        # noqa: BLE001
        return saida
    for chave, info in bruto.items():
        fabrica, canal = chave if isinstance(chave, tuple) else (chave, "")
        if (info or {}).get("status") == "ocioso":
            continue
        saida.setdefault(fabrica, []).append({
            "canal": canal, "status": info.get("status", ""),
            "detalhe": limpar(info.get("detalhe"))[:120],
            "ha_s": info.get("ha_s")})
    return saida


def paralelismo() -> list[dict]:
    """As travas de perfil, SEM pegar nenhuma. `ocupada: null` = nao sei.

    Mesma leitura da tabela do painel (uma linha por pasta de perfil, com os
    canais que a dividem), mas com a sonda de so-leitura.
    """
    travas = _travas()
    linhas: list[dict] = []
    for servico in SERVICOS:
        for canal in CANAIS:
            try:
                nome = travas.do_perfil(servico, canal)
            except Exception:                                # noqa: BLE001
                continue
            if any(l["trava"] == nome for l in linhas):
                continue
            canais = []
            for outro in CANAIS:
                try:
                    if travas.do_perfil(servico, outro) == nome:
                        canais.append(outro)
                except Exception:                            # noqa: BLE001
                    pass
            linhas.append({"trava": nome, "servico": servico, "canais": canais,
                           "ocupada": _trava_ocupada(nome),
                           "dividida": len(canais) > 1})
    return sorted(linhas, key=lambda l: l["trava"])


class _Placar:
    """Os quatro numeros do painel, calculados FORA do pedido.

    `panorama.resumo()` leva minutos na primeira conta. Servir o numero
    velho com a idade dele e honesto; fazer o celular esperar nao e.
    """

    def __init__(self):
        self._trava = threading.Lock()
        self._valor: dict | None = None
        self._quando = 0.0
        self._rodando = False

    def _calcular(self) -> None:
        valor = None
        try:
            from visao import panorama
            resumo = panorama.resumo(forcar=True)
            valor = {
                "publicados": (resumo.get("desempenho") or {}).get("total"),
                "prontos": ((resumo.get("inventario") or {})
                            .get("videos_prontos") or {}).get("total"),
                "trabalhando": len((resumo.get("saude") or {}).get("trabalhando") or []),
                "problemas": (resumo.get("qualidade") or {}).get("total_erros"),
            }
        except Exception as exc:                             # noqa: BLE001
            valor = {"falhou": type(exc).__name__}
        with self._trava:
            self._valor, self._quando, self._rodando = valor, time.time(), False

    def ler(self) -> dict | None:
        with self._trava:
            velho = time.time() - self._quando > PLACAR_VALE_S
            if velho and not self._rodando:
                self._rodando = True
                threading.Thread(target=self._calcular, daemon=True,
                                 name="placar-vila").start()
            if self._valor is None:
                return {"calculando": True}
            return dict(self._valor, idade_s=round(time.time() - self._quando))


PLACAR = _Placar()


def estado() -> dict:
    """O que muda: fabricas, trabalhos por canal, paralelismo e placar."""
    atividade = _atividade()
    saida: dict = {"agora": datetime.now().isoformat(timespec="seconds"),
                   "erros_de_leitura": []}
    try:
        por_fabrica = atividade.estado_das_fabricas()
    except Exception as exc:                                 # noqa: BLE001
        por_fabrica = {}
        saida["erros_de_leitura"].append(f"fabricas: {type(exc).__name__}")
    canais = _por_canal()
    fabricas = []
    for nome, dados in atividade.FABRICAS.items():
        info = por_fabrica.get(nome) or {}
        fabricas.append({
            "nome": nome, "rotulo": dados.get("rotulo", nome),
            "emoji": dados.get("emoji", ""), "faz": dados.get("faz", ""),
            "status": info.get("status", "ocioso"),
            "detalhe": limpar(info.get("detalhe")),
            "canal": info.get("canal") or "", "ha_s": info.get("ha_s"),
            "trabalhos": canais.get(nome, [])})
    saida["fabricas"] = fabricas
    try:
        saida["paralelismo"] = paralelismo()
    except Exception as exc:                                 # noqa: BLE001
        saida["paralelismo"] = []
        saida["erros_de_leitura"].append(f"travas: {type(exc).__name__}")
    saida["placar"] = PLACAR.ler()
    return saida


__all__ = ["PLACAR", "caminho_sprites", "estado", "mundo", "paralelismo",
           "png_do_mundo", "versao_do_mundo"]
