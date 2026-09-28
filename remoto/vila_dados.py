# -*- coding: utf-8 -*-
"""O que a Vila do celular mostra em TEXTO: fabricas, travas e placar.

O DESENHO da Vila e outro modulo: `remoto/vila_nova.py` serve a arte fofa
(a mesma da janela flutuante) e a vida dos habitantes. Aqui fica o que se le
em texto embaixo do cenario — e que o desenho nao mostra: o estado de cada
fabrica por canal, quais contas estao em uso, e o placar.

TRES CUIDADOS QUE VIERAM DE FORA:
  1. `travas.estado()` responde "ocupada?" PEGANDO a trava por um instante —
     e um celular perguntando a cada 3 s faria o dono de verdade ouvir
     "ocupado" e desistir da rodada. Aqui a sonda e a de `acoes.trava_ocupada`,
     que so tenta LER o byte trancado.
  2. `panorama.resumo()` leva ~159 s na primeira conta (medido em 27/09/2026)
     e so depois fica em cache. Isso NAO pode acontecer dentro de um GET: o
     placar e calculado numa thread e servido com a idade dele.
  3. toda fabrica do diario aparece na lista, inclusive as que nao tem
     predio na arte — esconder uma fabrica e pior do que mostra-la sem casa.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime

from .painel_dados import limpar

PLACAR_VALE_S = 30 * 60          # o resumo e caro; meia hora basta
ESCALA = 2
SERVICOS = ("picasso", "digen", "dreamface", "chatgpt", "gemini", "deepseek",
            "tiktok", "youtube_web")
CANAIS = ("builds", "historias")


def _atividade():
    from builds import atividade
    return atividade


def _travas():
    from builds import travas
    return travas


def _trava_ocupada(nome: str):
    from .acoes import trava_ocupada
    return trava_ocupada(nome)


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


__all__ = ["PLACAR", "estado", "paralelismo"]
