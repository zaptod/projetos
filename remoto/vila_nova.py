# -*- coding: utf-8 -*-
"""A Vila NOVA (a arte fofa) servida para o celular.

O Adrian pediu no app a Vila nova — a da janela flutuante, com arte
vetorial, ciclo dia/noite e habitantes que andam pela rua. A antiga (pixel
art) saiu do app.

A DIVISAO, e por que ela e assim:

  O DESENHO vai pronto do PC. `painel.flutuante.arte` desenha tudo com
  Pillow em 4x e reduz com LANCZOS; refazer isso em JavaScript seria um
  segundo desenho da mesma vila, que divergiria na primeira mudanca. Entao
  o servidor manda duas imagens, guardadas em memoria:
    - o FUNDO (chao, ruas, predios, decoracao), em dia e noite;
    - um ATLAS com os personagens em todas as poses.

  A VIDA roda aqui, nao la. `painel.flutuante.vida` e logica pura (grafo de
  caminhos, decisoes, encontros, emotes) e ja tem teste. Rodar de novo no
  celular seria a mesma divergencia, com o agravante de que o celular nao
  ve o diario. Entao um motor no servidor aplica o estado real e anda com
  os habitantes; o app le `/api/vilanova` e desenha o retrato.

  O app INTERPOLA entre dois retratos (chegam a cada ~1 s) para o passo nao
  ficar picotado. E so isso que ele calcula.

CUIDADOS HERDADOS:
  - as travas sao lidas pela sonda de so-leitura de `flutuante.dados`
    (`travas_ocupadas`), que nao pega trava nenhuma;
  - o motor so anda quando alguem esta olhando: sem pedido ha mais de
    `PARAR_SEM_PEDIDO_S`, a thread dorme (nada de queimar CPU do PC para
    ninguem).
"""
from __future__ import annotations

import io
import threading
import time
from datetime import datetime, timezone

TICK_S = 0.25                  # passo da simulacao
LEITURA_S = 3.0                # releitura do diario e das travas
PARAR_SEM_PEDIDO_S = 30.0      # sem ninguem olhando, o motor dorme
POSES = ("parado", "passo1", "passo2", "sentado", "trabalhar", "acenar",
         "triste", "feliz")
OLHOS = ("abertos", "fechados")
DIRECOES = ("dir", "esq")


def _arte():
    from painel.flutuante import arte
    return arte


def _dados():
    from painel.flutuante import dados
    return dados


def _vida():
    from painel.flutuante import vida
    return vida


def _caminhos():
    from painel.flutuante.caminhos import Caminhos
    return Caminhos()


# ------------------------------------------------------------------ arte
_TRAVA_ARTE = threading.Lock()
_FUNDOS: dict = {}
_ATLAS: dict = {}


def png_do_fundo(noite: bool) -> bytes:
    """Chao, ruas, predios e decoracao — a parte que nao se mexe."""
    with _TRAVA_ARTE:
        if noite not in _FUNDOS:
            imagem = _arte().compor_mundo(bool(noite)).convert("RGB")
            saco = io.BytesIO()
            imagem.save(saco, "PNG", optimize=True)
            _FUNDOS[noite] = saco.getvalue()
        return _FUNDOS[noite]


def atlas() -> dict:
    """{png, mapa, largura, altura}: todo personagem, toda pose, num arquivo.

    Sao ~10 habitantes x 8 poses x 2 olhos x 2 direcoes. Cada sprite custa
    milissegundos e o conjunto vira uma imagem so — o celular baixa uma vez
    e depois so recorta.
    """
    from PIL import Image

    with _TRAVA_ARTE:
        if _ATLAS:
            return _ATLAS
        arte = _arte()
        nomes = list(arte.LOTES)
        larg, alt = arte.PERSONAGEM_W, arte.PERSONAGEM_H
        combos = [(nome, pose, olho, direcao) for nome in nomes
                  for pose in POSES for olho in OLHOS for direcao in DIRECOES]
        colunas = 16
        linhas = (len(combos) + colunas - 1) // colunas
        folha = Image.new("RGBA", (colunas * larg, linhas * alt), (0, 0, 0, 0))
        mapa = {}
        for i, (nome, pose, olho, direcao) in enumerate(combos):
            x, y = (i % colunas) * larg, (i // colunas) * alt
            try:
                sprite = arte.desenhar_personagem(nome, pose, olho, direcao)
            except Exception:                                # noqa: BLE001
                continue
            folha.paste(sprite, (x, y), sprite)
            mapa[f"{nome}|{pose}|{olho}|{direcao}"] = [x, y]
        saco = io.BytesIO()
        folha.save(saco, "PNG", optimize=True)
        _ATLAS.update({"png": saco.getvalue(), "mapa": mapa,
                       "larg": larg, "alt": alt,
                       "tamanho": [folha.width, folha.height]})
        return _ATLAS


def mundo() -> dict:
    """O que o app precisa saber uma vez: tamanho, lotes, portas, atlas."""
    arte = _arte()
    dados = _dados()
    folha = atlas()
    return {
        "tamanho": [arte.LARGURA, arte.ALTURA],
        "tile": arte.TILE if hasattr(arte, "TILE") else 16,
        "lotes": {nome: {"x": x, "y": y} for nome, (x, y) in arte.LOTES.items()},
        "casa": {"x": arte.CASA[0], "y": arte.CASA[1]},
        "portas": {nome: list(p) for nome, p in arte.portas().items()},
        "predios": {nome: {"rotulo": info.get("rotulo", nome),
                           "emoji": info.get("emoji", ""),
                           "faz": info.get("faz", "")}
                    for nome, info in dados.PREDIOS.items()},
        "atlas": {"mapa": folha["mapa"], "larg": folha["larg"],
                  "alt": folha["alt"], "tamanho": folha["tamanho"]},
        "versao": versao(),
    }


def versao() -> str:
    """Muda quando a arte muda (o arquivo dela e a fonte de tudo)."""
    from pathlib import Path
    try:
        estado = Path(_arte().__file__).stat()
        return f"{int(estado.st_mtime)}-{estado.st_size}"
    except OSError:
        return "0"


# ----------------------------------------------------------------- motor
class Motor:
    """A vida da Vila rodando no servidor, enquanto alguem olha."""

    def __init__(self):
        self._trava = threading.Lock()
        self._vida = None
        self._caminhos = None
        self._predios: dict = {}
        self._ultimo_pedido = 0.0
        self._fio: threading.Thread | None = None
        self._ultima_leitura = 0.0
        self._erro = ""

    # -------------------------------------------------------- leitura
    def _ler_estado(self) -> dict:
        """O estado REAL dos predios, com as leituras da janela flutuante."""
        dados = _dados()
        if self._caminhos is None:
            self._caminhos = _caminhos()
        c = self._caminhos
        agora_utc = datetime.now(timezone.utc)
        eventos = dados.ler_diario(c.diario)
        ocupadas = dados.travas_ocupadas(c.travas)     # sonda, nao pega trava
        abertos = dados.trabalhos_abertos(eventos, agora_utc)
        erros = dados.erros_recentes(eventos, agora_utc)
        recentes = dados.atividade_recente(eventos, agora_utc)
        return dados.estado_dos_predios(abertos, erros, ocupadas, recentes)

    def _girar(self) -> None:
        vida = _vida()
        dados = _dados()
        if self._vida is None:
            self._vida = vida.Vida(list(dados.PREDIOS))
        anterior = time.monotonic()
        while True:
            agora = time.monotonic()
            with self._trava:
                parado = agora - self._ultimo_pedido > PARAR_SEM_PEDIDO_S
            if parado:
                with self._trava:
                    self._fio = None
                return
            if agora - self._ultima_leitura >= LEITURA_S:
                try:
                    predios = self._ler_estado()
                    with self._trava:
                        self._predios = predios
                        self._erro = ""
                    self._vida.aplicar(predios, agora)
                except Exception as exc:                     # noqa: BLE001
                    with self._trava:
                        self._erro = f"{type(exc).__name__}"
                self._ultima_leitura = agora
            self._vida.tick(min(agora - anterior, 1.0), agora)
            anterior = agora
            time.sleep(TICK_S)

    def _acordar(self) -> None:
        with self._trava:
            self._ultimo_pedido = time.monotonic()
            vivo = self._fio is not None and self._fio.is_alive()
            if vivo:
                return
            self._fio = threading.Thread(target=self._girar, daemon=True,
                                         name="vila-nova")
            fio = self._fio
        fio.start()

    # -------------------------------------------------------- retrato
    def retrato(self) -> dict:
        """Onde esta cada habitante agora, e como desenha-lo."""
        self._acordar()
        vida = _vida()
        agora = time.monotonic()
        # a primeira chamada pode chegar antes do primeiro giro
        if self._vida is None:
            time.sleep(0.05)
        habitantes = []
        if self._vida is not None:
            for nome, h in self._vida.habitantes.items():
                pose, olhos, direcao, pulo = self._vida.pose(h, agora)
                x, y = self._vida.posicao_de_desenho(h)
                habitantes.append({
                    "nome": nome, "x": round(x, 1), "y": round(y - pulo, 1),
                    "pose": pose, "olhos": olhos, "direcao": direcao,
                    "emote": h.emote if h.emote_ate > agora else "",
                    "balao": h.balao or "", "modo": h.modo,
                    "atividade": h.atividade,
                    "descricao": vida.DESCRICAO.get(h.atividade, "")})
        with self._trava:
            predios = dict(self._predios)
            erro = self._erro
        return {
            "agora": datetime.now().isoformat(timespec="seconds"),
            "noite": bool(_noite()),
            "habitantes": habitantes,
            "predios": {nome: {"status": info.get("status", "ocioso"),
                               "balao": info.get("balao", ""),
                               "erro": (info.get("erro") or {}).get("detalhe", "")
                               if isinstance(info.get("erro"), dict)
                               else (info.get("erro") or ""),
                               "contas": info.get("contas") or [],
                               "trabalhos": [t.get("detalhe", "")
                                             for t in (info.get("trabalhos") or [])]}
                        for nome, info in predios.items()},
            "erro_de_leitura": erro,
        }


def _noite() -> bool:
    from painel.flutuante.cena import e_noite
    return e_noite(datetime.now())


MOTOR = Motor()


__all__ = ["MOTOR", "atlas", "mundo", "png_do_fundo", "versao"]
