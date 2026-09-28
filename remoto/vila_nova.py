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
# NITIDEZ (28/09/2026): a arte de 1x, ampliada ~2,3x pelo celular (e mais o
# devicePixelRatio), chegava borrada. Agora o celular recebe a Vila DOBRADA
# (`painel.flutuante.retrato`: as duas metades em fileiras, para caber em pe
# inteira) desenhada de verdade em ESCALA_CELULAR, e o atlas tambem. O fundo
# e o atlas de 1x continuam servidos: sao o que a casca antiga (a que ainda
# nao atualizou pelo service worker) pede.
ESCALA_CELULAR = 3

_TRAVA_ARTE = threading.Lock()
_FUNDOS: dict = {}
_RETRATOS: dict = {}
_ATLAS: dict = {}


def png_do_fundo(noite: bool) -> bytes:
    """Chao, ruas, predios e decoracao — a parte que nao se mexe (1x)."""
    with _TRAVA_ARTE:
        if noite not in _FUNDOS:
            imagem = _arte().compor_mundo(bool(noite)).convert("RGB")
            saco = io.BytesIO()
            imagem.save(saco, "PNG", optimize=True)
            _FUNDOS[noite] = saco.getvalue()
        return _FUNDOS[noite]


def imagem_do_retrato(noite: bool) -> bytes:
    """A Vila inteira em pe, em ESCALA_CELULAR, como WebP.

    WebP e nao PNG: o fundo e opaco e a 3x o PNG passava de 1 MB; com
    qualidade 90 fica em ~130 KB e a diferenca nao se ve (e grama).
    """
    from painel.flutuante import retrato

    with _TRAVA_ARTE:
        if noite not in _RETRATOS:
            imagem = retrato.compor_retrato(bool(noite), ESCALA_CELULAR)
            saco = io.BytesIO()
            imagem.convert("RGB").save(saco, "WEBP", quality=90, method=6)
            _RETRATOS[noite] = saco.getvalue()
        return _RETRATOS[noite]


def atlas(escala: int = 1) -> dict:
    """{png, mapa, larg, alt, tamanho, escala}: todo personagem, toda pose.

    Sao ~10 habitantes x 8 poses x 2 olhos x 2 direcoes. Cada sprite custa
    milissegundos e o conjunto vira uma imagem so — o celular baixa uma vez
    e depois so recorta. `larg`/`alt` e o `mapa` estao em pixels DO ATLAS
    (ja multiplicados pela escala); no mundo o sprite mede larg/escala.
    """
    from PIL import Image

    escala = max(1, int(escala))
    with _TRAVA_ARTE:
        if escala in _ATLAS:
            return _ATLAS[escala]
        arte = _arte()
        nomes = list(arte.LOTES)
        larg, alt = arte.PERSONAGEM_W * escala, arte.PERSONAGEM_H * escala
        combos = [(nome, pose, olho, direcao) for nome in nomes
                  for pose in POSES for olho in OLHOS for direcao in DIRECOES]
        # e os patos do lago (2 quadros x 2 lados), como na janela flutuante
        patos = [(q, d) for q in (0, 1) for d in DIRECOES]
        colunas = 16
        linhas = (len(combos) + len(patos) + colunas - 1) // colunas
        folha = Image.new("RGBA", (colunas * larg, linhas * alt), (0, 0, 0, 0))
        mapa = {}
        for i, (nome, pose, olho, direcao) in enumerate(combos):
            x, y = (i % colunas) * larg, (i // colunas) * alt
            try:
                sprite = arte.desenhar_personagem(nome, pose, olho, direcao,
                                                  escala)
            except Exception:                                # noqa: BLE001
                continue
            folha.paste(sprite, (x, y), sprite)
            mapa[f"{nome}|{pose}|{olho}|{direcao}"] = [x, y]
        for j, (quadro, direcao) in enumerate(patos):
            i = len(combos) + j
            x, y = (i % colunas) * larg, (i // colunas) * alt
            pato = arte.desenhar_pato(quadro, escala)
            if direcao == "esq":
                pato = pato.transpose(Image.FLIP_LEFT_RIGHT)
            folha.paste(pato, (x, y), pato)
            mapa[f"pato|{quadro}|{direcao}"] = [x, y]
        saco = io.BytesIO()
        folha.save(saco, "PNG", optimize=True)
        _ATLAS[escala] = {"png": saco.getvalue(), "mapa": mapa,
                          "larg": larg, "alt": alt, "escala": escala,
                          "tamanho": [folha.width, folha.height],
                          "pato": [14, 11], "lago": list(arte.LAGO)}
        return _ATLAS[escala]


ENQUADRAMENTOS = ("perto", "longe")
DECISAO_DO_ZOOM = ("painel-e-vila", "vila-zoom-celular")


def enquadramento() -> str:
    """Como a Vila abre no celular: a decisao do Adrian manda.

    `perto`: uma fileira enche a altura, comecando na casa (como era);
    `longe`: a Vila inteira de uma vez. Enquanto a decisao
    `painel-e-vila/vila-zoom-celular` estiver pendente (ou ilegivel), fica o
    que ja era: `perto`. A resposta dele vale na proxima abertura do app,
    sem mexer em codigo.
    """
    import json

    try:
        from remoto import decisoes
        item = json.loads(decisoes.caminho_item(*DECISAO_DO_ZOOM)
                          .read_text(encoding="utf-8"))
        opcao = (item.get("vigente") or {}).get("opcao")
    except Exception:                                        # noqa: BLE001
        opcao = None
    return opcao if opcao in ENQUADRAMENTOS else "perto"


def _info_do_atlas(folha: dict) -> dict:
    return {"mapa": folha["mapa"], "larg": folha["larg"], "alt": folha["alt"],
            "tamanho": folha["tamanho"], "escala": folha["escala"],
            "pato": folha["pato"], "lago": folha["lago"]}


def mundo() -> dict:
    """O que o app precisa saber uma vez: tamanho, lotes, portas, atlas."""
    from painel.flutuante import retrato

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
        "atlas": _info_do_atlas(folha),
        # a Vila do celular em pe: geometria da dobra, e o atlas na escala
        "retrato": {**retrato.geometria(), "escala": ESCALA_CELULAR,
                    "atlas": _info_do_atlas(atlas(ESCALA_CELULAR)),
                    "enquadramento": enquadramento()},
        "versao": versao(),
    }


def versao() -> str:
    """Muda quando a arte muda (os arquivos dela sao a fonte de tudo)."""
    from pathlib import Path

    from painel.flutuante import retrato
    try:
        partes = []
        for modulo in (_arte(), retrato):
            estado = Path(modulo.__file__).stat()
            partes.append(f"{int(estado.st_mtime)}-{estado.st_size}")
        return f"{'.'.join(partes)}-{ESCALA_CELULAR}"
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


__all__ = ["ESCALA_CELULAR", "MOTOR", "atlas", "imagem_do_retrato", "mundo",
           "png_do_fundo", "versao"]
