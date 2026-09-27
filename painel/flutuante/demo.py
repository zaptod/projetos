# -*- coding: utf-8 -*-
"""Um coletor de MENTIRA, so para provas e GIF (`--demo`). Nunca o padrao.

A janela em modo demo diz "DEMONSTRAÇÃO" na barra. O roteiro passa pelas
situacoes que as interacoes precisam mostrar: trabalho comecando, trabalho
acabando (comemoracao), erro (tristeza e consolo) e publicacao (confete).
"""
from __future__ import annotations

import queue
import threading
import time
from datetime import datetime, timedelta

from . import dados

# Hora FIXA da publicacao falsa: com o relogio andando, toda leitura parecia
# uma publicacao nova e a festa nao parava.
BASE = datetime(2026, 1, 1, 12, 0)

ROTEIRO = (
    # (a partir de t segundos, {predio: (status, balao)}, publicou?)
    (0.0, {"estudio": ("trabalhando", "render historia_00018"),
           "gemini": ("trabalhando", "vídeo historia_00013 p1")}, False),
    (2.0, {"estudio": ("trabalhando", "render historia_00018"),
           "gemini": ("trabalhando", "vídeo historia_00013 p1"),
           "tiktok": ("erro", "❗ upload falhou")}, False),
    (3.5, {"gemini": ("trabalhando", "vídeo historia_00013 p1"),
           "tiktok": ("erro", "❗ upload falhou")}, True),
    (9.0, {"picasso": ("trabalhando", "imagens historia_00018")}, False),
)


def estado_de_demo(t: float, base: dict | None = None) -> dict:
    agora = datetime.now()
    predios_demo = {}
    publicou = 0
    for inicio, predios, publica in ROTEIRO:
        if t >= inicio:
            predios_demo = predios
            publicou += 1 if publica else 0
    predios = {}
    for nome in dados.PREDIOS:
        status, balao = predios_demo.get(nome, ("ocioso", "💤"))
        predios[nome] = {"status": status, "balao": balao, "trabalhos": [],
                         "contas": ["principal"] if status == "trabalhando"
                         else [], "erro": None, "recente": None,
                         "em_uso": []}
    predios["bot"] = {"status": "no_ar", "balao": "no ar", "trabalhos": [],
                      "contas": [], "erro": None, "recente": None,
                      "em_uso": []}
    publicados = [{"quando": BASE + timedelta(minutes=publicou),
                   "canal": "historias", "plataforma": "tiktok",
                   "titulo": "Demonstração", "prova": True}]
    estado = dict(base or {})
    estado.update({
        "agora": agora, "predios": predios, "publicados": publicados,
        "publicados_hoje": 7 + publicou * 2, "abertos": [], "erros": [],
        "vivos": [], "processos_conhecidos": True, "feed": [],
        "bot": {"vivo": True}, "proximo": dados.proximo_horario(agora),
        "tarefas": None, "previsao": {}, "terminais": {},
    })
    focos = [f"{dados.rotulo(n)} · {i['balao']}" for n, i in predios.items()
             if i["status"] == "trabalhando"]
    estado["resumo"] = {"nivel": "trabalhando" if focos else "calmo",
                        "frase": "DEMONSTRAÇÃO · " + (
                            f"⚙ {len(focos)} em andamento · {focos[0]}"
                            if focos else "💤 tudo parado"),
                        "alerta": ""}
    return estado


class ColetorDemo:
    demo = True

    def __init__(self, fila: queue.Queue | None = None):
        self.fila = fila or queue.Queue()
        self._parar = threading.Event()
        self._inicio = time.monotonic()

    def iniciar(self):
        def laco():
            while not self._parar.is_set():
                self.fila.put(("estado", estado_de_demo(
                    time.monotonic() - self._inicio)))
                self._parar.wait(.5)
        threading.Thread(target=laco, daemon=True).start()

    def parar(self):
        self._parar.set()

    def ritmo(self, escondido):
        pass

    def agora(self):
        pass

    def pedir_previsao(self):
        pass


__all__ = ["ColetorDemo", "estado_de_demo"]
