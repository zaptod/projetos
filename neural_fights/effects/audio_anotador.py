"""O ``AudioManager`` que ANOTA em vez de tocar (Onda 16A).

Por que existe
--------------
O som do jogo nunca tinha entrado num video. O gravador roda com o driver
``dummy`` e a trilha ``anullsrc``: o ``AudioManager`` decidia tudo — qual som,
qual variante do grupo, quanto de volume pela categoria, pela distancia da
camera — e mandava para um dispositivo que nao existe. Os 20 sons do pacote e
os 11 wav que o Adrian ajustou em 28/08 nunca chegaram a um mp4.

Este anotador herda TODA essa decisao do ``AudioManager`` (nada de logica de
som copiada) e troca so as duas pontas que tocam no dispositivo:

- ``_iniciar_mixer``: nao abre mixer nenhum;
- ``_carregar_do_cache``: em vez de decodificar o arquivo, devolve o caminho —
  o registro fica com as MESMAS chaves e os MESMOS grupos, na mesma ordem.

O objeto que o registro guarda no lugar do ``pygame.mixer.Sound`` responde a
``set_volume``/``play`` como ele, e o ``play`` vira uma linha em ``sons``.

Determinismo
------------
A variante de um grupo continua sorteada pelo ``random`` GLOBAL, exatamente
como o jogo faz (``AudioManager.play``). Nao e descuido: o gravador sempre
rodou com o ``AudioManager`` de verdade (o driver dummy abre o mixer e os 65
sons carregam), entao esse sorteio ja consumia o ``random`` global — e e dele
que as particulas e o tremor de camera tiram os numeros. Mesmo tamanho de
grupo, mesmo consumo: a luta E o video saem iguais aos de antes do anotador.
O pitch, que o jogo nao tem, usa um ``random.Random`` proprio com semente, e
por isso nunca mexe na luta.

O formato de ``sons`` (a secao ``sons`` da timeline da 16C)
-----------------------------------------------------------
Uma lista em ordem de tempo; cada item e um dict::

    {"t": 12.433,          # s, relogio do VIDEO gravado (ver abaixo)
     "id": "slash_heavy",  # chave do som no jogo; num grupo, a variante sorteada
     "volume": 0.56,       # 0..1, o volume que o jogo aplicaria (base x
                           #   categoria x sfx x master x distancia, com o
                           #   mesmo teto de 1,0 do pygame)
     "pitch": 1.043,       # razao de reproducao (1.0 = o arquivo como e)
     "pan": -0.12,         # so quando o jogo calculou pan (som posicional)
     "x": 14.2}            # so no som posicional: onde a fonte estava, em m

- ``t`` e o tempo do quadro de video em que o jogo pediu o som (o mesmo relogio
  de ``eventos_dano``). Depois do corte de tedio, ``remapear_gravacao`` leva a
  lista para o relogio do CLIPE, como faz com os golpes; som que cai num corte
  sai.
- ``id`` e a CHAVE, nao o arquivo: quem mistura resolve o arquivo na hora, pelo
  ``sound_config.json`` e pelos ``SOUND_FALLBACKS``, na mesma cadeia do jogo.
  Trocar um wav e renderizar de novo basta — nao precisa regravar a luta.
- O jogo ao vivo nao faz estereo (``play`` soma esquerda e direita num volume
  so); ``pan`` fica anotado para quem quiser espacializar (o palco da 16D).

O contrato inteiro, para quem le a lista de fora (o palco), esta em
``docs/palco/sons.md``.
"""
from __future__ import annotations

import random
from pathlib import Path

from neural_fights.effects.audio import AudioManager

VERSAO_SONS = 1

# Variacao de pitch por categoria (fracao para cada lado). O jogo toca todo
# golpe na mesma altura; num video de 30 s, 25 golpes identicos soam como
# metralhadora (medido em 28/09/2026 no som sintetizado: 25 vezes o mesmo hit
# por duelo). Ambiente e interface ficam fixos: a abertura da arena e a vitoria
# nao sao repeticao.
VARIACAO_DE_PITCH = {
    "golpes": 0.07,
    "impactos": 0.06,
    "projeteis": 0.04,
    "skills": 0.04,
    "movimento": 0.08,
    "ambiente": 0.0,
    "ui": 0.0,
}


class _SomRegistrado:
    """O que o registro guarda no lugar de um ``pygame.mixer.Sound``.

    Responde a ``set_volume``/``play`` do mesmo jeito que o ``AudioManager.play``
    usa o ``Sound`` (volume logo antes de tocar), e o ``play`` anota.
    """

    __slots__ = ("id", "arquivo", "_anotador", "_volume")

    def __init__(self, anotador: "AnotadorDeAudio", id_som: str, arquivo: Path):
        self.id = id_som
        self.arquivo = Path(arquivo)
        self._anotador = anotador
        self._volume = 1.0

    def __bool__(self) -> bool:
        return True

    def set_volume(self, valor: float) -> None:
        # Semantica do pygame: negativo nao muda nada, acima de 1 vira 1.
        if valor < 0:
            return
        self._volume = min(1.0, float(valor))

    def get_volume(self) -> float:
        return self._volume

    def play(self, *_args, **_kwargs) -> None:
        self._anotador._anotar(self, self._volume)

    def stop(self) -> None:
        return None

    def __repr__(self) -> str:  # pragma: no cover - diagnostico
        return f"_SomRegistrado({self.id!r}, {self.arquivo.name!r})"


class AnotadorDeAudio(AudioManager):
    """Mesma API do ``AudioManager``; cada som vira uma linha de ``sons``.

    ``t_video`` e o relogio: quem grava o video o avanca a cada quadro, antes
    de ``update``. ``seed`` semeia o pitch (use a seed da luta: o mesmo video
    gravado de novo sai com o mesmo som).
    """

    def __init__(self, *, seed=0):
        self.t_video = 0.0
        self.sons: list[dict] = []
        self._rng_pitch = random.Random(f"neural-fights:som:{seed}")
        self._pedido: str | None = None
        self._pan = 0.0
        self._posicao: tuple[float, float] | None = None
        super().__init__()

    # ------------------------------------------------ as duas pontas trocadas
    def _iniciar_mixer(self) -> bool:
        return True

    def _carregar_do_cache(self, filepath):
        # O jogo decodifica aqui; o anotador so precisa saber que o arquivo
        # existe (resolve_sound_file ja conferiu). Diferenca unica e
        # documentada: um arquivo que existe mas nao decodifica seria pulado
        # pelo jogo e aqui entra.
        return Path(filepath)

    def _load_or_generate_sound(self, name: str):
        resolvido = super()._load_or_generate_sound(name)
        if resolvido is None:
            return None
        if isinstance(resolvido, _SomRegistrado):   # veio por um fallback
            resolvido = resolvido.arquivo
        return _SomRegistrado(self, name, resolvido)

    def stop_all(self):
        return None

    # --------------------------------------------- o contexto de cada pedido
    def play(self, sound_name: str, volume: float = 1.0, pan: float = 0.0):
        self._pedido, self._pan = sound_name, float(pan or 0.0)
        try:
            super().play(sound_name, volume, pan)
        finally:
            self._pedido, self._pan = None, 0.0

    def play_positional(self, sound_name: str, pos_x: float, listener_x: float,
                        max_distance: float = 20.0, volume: float = 1.0):
        self._posicao = (float(pos_x), float(listener_x))
        try:
            super().play_positional(sound_name, pos_x, listener_x,
                                    max_distance=max_distance, volume=volume)
        finally:
            self._posicao = None

    # ------------------------------------------------------------ a anotacao
    def _anotar(self, som: _SomRegistrado, volume: float) -> None:
        categoria = self._get_sound_category(self._pedido or som.id)
        variacao = float(VARIACAO_DE_PITCH.get(categoria, 0.0))
        pitch = 1.0 + self._rng_pitch.uniform(-variacao, variacao) if variacao > 0 else 1.0
        entrada = {
            "t": round(float(self.t_video), 3),
            "id": som.id,
            "volume": round(float(volume), 4),
            "pitch": round(pitch, 4),
        }
        if self._pan:
            entrada["pan"] = round(self._pan, 3)
        if self._posicao is not None:
            entrada["x"] = round(self._posicao[0], 2)
        self.sons.append(entrada)

    def arquivos(self) -> dict[str, Path]:
        """``id -> arquivo`` de tudo que o registro conhece (para a mistura)."""
        return {nome: som.arquivo for nome, som in self.sounds.items()
                if isinstance(som, _SomRegistrado)}


def arquivos_de_som() -> dict[str, Path]:
    """``id -> arquivo`` resolvidos AGORA, na mesma cadeia do jogo.

    A mistura chama isto na hora de renderizar: e assim que trocar um wav (ou
    o ``sound_config.json``) vale para o proximo render sem regravar a luta.
    """
    return AnotadorDeAudio(seed=0).arquivos()
