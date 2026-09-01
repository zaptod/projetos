"""Caminhos, credenciais e ajustes da integracao com o Digen.

Segue a convencao que o neural_fights ja usa para o YouTube
(`neural_fights/live/sources/youtube.py:48-49`): credencial em JSON num
arquivo fora do git, com o caminho sobrescrivivel por variavel de ambiente.
Nada de `.env`, nada de senha em codigo.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..generation.session_generator import load_config
from . import slots

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
IDENTITY_DIR = OUTPUTS / "_identity"

# Um perfil de Chrome POR PROVEDOR, e o motivo e mecanico, nao de cookie: o
# Chrome trava o `user_data_dir`, e `browser._liberar_perfil` mata processos
# filtrando por essa string. Com perfil unico, abrir o PicassoIA mataria o
# Chrome que esta esperando um video no Digen.
#
# O perfil persistente e o que guarda cookies, localStorage e os cookies de
# anti-bot — e o que faz o login acontecer uma vez so, por site.
PROVEDORES = {
    "digen": {
        "credenciais": "digen_credentials.json",
        "env_credenciais": "DIGEN_CREDENTIALS",
        "env_perfil": "DIGEN_PROFILE_DIR",
        "perfil": ROOT / ".browser_profile" / "digen",
    },
    "picasso": {
        "credenciais": "picasso_credentials.json",
        "env_credenciais": "PICASSO_CREDENTIALS",
        "env_perfil": "PICASSO_PROFILE_DIR",
        "perfil": ROOT / ".browser_profile" / "picasso",
    },
    # O segundo gerador de imagem. Perfil proprio pelo mesmo motivo mecanico
    # dos outros: o Chrome trava o `user_data_dir`, entao dois sites no mesmo
    # perfil nunca rodam juntos — e rodar junto e exatamente o objetivo dele.
    "dreamface": {
        "credenciais": "dreamface_credentials.json",
        "env_credenciais": "DREAMFACE_CREDENTIALS",
        "env_perfil": "DREAMFACE_PROFILE_DIR",
        "perfil": ROOT / ".browser_profile" / "dreamface",
    },
}
PADRAO = "digen"

# Nomes antigos, de quando so existia o Digen.
ARQUIVO_CREDENCIAIS = PROVEDORES[PADRAO]["credenciais"]
CREDENCIAIS_ENV = PROVEDORES[PADRAO]["env_credenciais"]
PERFIL_ENV = PROVEDORES[PADRAO]["env_perfil"]
PERFIL_PADRAO = PROVEDORES[PADRAO]["perfil"]


def _do_provedor(provedor: str | None) -> dict:
    nome = provedor or PADRAO
    if nome not in PROVEDORES:
        raise ValueError(f"provedor desconhecido: {nome!r} "
                         f"(esperado: {', '.join(PROVEDORES)})")
    return PROVEDORES[nome]


def settings(provedor: str | None = None) -> dict:
    """config/identity.json (prompts, timeouts, pacing, seletores de fluxo).

    Sem argumento devolve a RAIZ inteira, exatamente como sempre devolveu — o
    diagnostico, o cliente do Digen e os testes leem modelo/duracao/resolucao
    de la. Com provedor, a raiz vem com o bloco daquele site por cima: o que
    e comum fica escrito uma vez so, e o que e do site sobrescreve.
    """
    base = load_config("identity.json")
    if provedor is None:
        return base
    especifico = (base.get("provedores") or {}).get(provedor) or {}
    return {**base, **{k: v for k, v in especifico.items()
                       if not k.startswith("_")}}


def profile_dir(provedor: str | None = None, canal: str = "builds") -> Path:
    """A pasta de Chrome daquele provedor, na conta ATIVA do canal.

    A variavel de ambiente continua vencendo (e o jeito de apontar para um
    perfil fora do padrao numa rodada); sem ela, quem decide e o registro de
    contas — e a conta `principal` cai no caminho antigo, entao nenhum login
    ja feito se perde.
    """
    dados = _do_provedor(provedor)
    forcado = os.environ.get(dados["env_perfil"])
    if forcado:
        caminho = Path(forcado)
        caminho.mkdir(parents=True, exist_ok=True)
        return caminho
    try:
        from ..contas import perfil
        return perfil(provedor or PADRAO, canal)
    except Exception:
        caminho = Path(dados["perfil"])
        caminho.mkdir(parents=True, exist_ok=True)
        return caminho


def credentials_path(provedor: str | None = None) -> Path:
    dados = _do_provedor(provedor)
    return Path(os.environ.get(dados["env_credenciais"])
                or (ROOT / dados["credenciais"]))


def load_credentials(provedor: str | None = None) -> dict | None:
    """{'email': ..., 'password': ...} ou None se o arquivo nao existir.

    None NAO e erro: com o perfil persistente o login normalmente ja esta
    valido e nem chegamos a precisar da senha.
    """
    caminho = credentials_path(provedor)
    if not caminho.is_file():
        return None
    with open(caminho, encoding="utf-8-sig") as fh:
        dados = json.load(fh)
    faltando = [c for c in ("email", "password") if not dados.get(c)]
    if faltando:
        raise ValueError(
            f"{caminho} existe mas nao tem {', '.join(faltando)}. "
            'Formato: {"email": "...", "password": "..."}')
    return dados


def build_dir(generation_id: str) -> Path:
    return OUTPUTS / generation_id


def identity_dir(generation_id: str) -> Path:
    """outputs/<generation_id>/identity/ — prompts, identidades e metadados.

    Os mp4 NAO moram mais aqui: eles sao entregaveis da build (secao 18) e
    ficam na raiz da geracao, com os nomes canonicos `character_video.mp4`,
    `weapon_video.mp4` e `character_weapon_video.mp4`.
    """
    return OUTPUTS / generation_id / "identity"


def artefato_path(generation_id: str, slot: str = slots.CHARACTER) -> Path:
    """Onde GRAVAR o artefato daquele slot (nome canonico de hoje)."""
    return build_dir(generation_id) / slots.ARQUIVO[slots.valido(slot)]


# `clip_path` e `artefato_utilizavel` mudaram de casa para src/identity/artefato.py:
# a fila precisa dessas respostas de DENTRO do lock dela, e um modulo que so
# depende de config e slots e o unico que pode ser chamado de la sem risco de
# reentrancia. Este arquivo ficou so com caminhos.


# ----------------------------------------------------------- payoff em video
def payoff_video_ativo(ajustes: dict | None = None) -> bool:
    """O video do Digen (slot character_weapon) esta ligado?

    `payoff_video: false` em config/identity.json desliga o gerador de video:
    o job nao e enfileirado, o worker nao abre o Digen, e a montagem usa a
    IMAGEM do personagem com a arma como payoff. Existe porque o gerador
    de video quebra (fila do site estourando, conta sem credito) e a build
    nao pode ficar refem dele - as imagens sozinhas ja fazem o video.
    """
    if ajustes is None:
        ajustes = settings()
    return bool(ajustes.get("payoff_video", True))


def jobs_ativos(ajustes: dict | None = None) -> tuple[str, ...]:
    """Os jobs de identidade a enfileirar/processar com a config atual."""
    from . import slots
    if payoff_video_ativo(ajustes):
        return tuple(slots.JOBS)
    return tuple(s for s in slots.JOBS if s != slots.CHARACTER_WEAPON)


def slots_ativos(ajustes: dict | None = None) -> tuple[str, ...]:
    """Os slots de entrega (sem a referencia intermediaria) ativos."""
    from . import slots
    if payoff_video_ativo(ajustes):
        return tuple(slots.SLOTS)
    return tuple(s for s in slots.SLOTS if s != slots.CHARACTER_WEAPON)
