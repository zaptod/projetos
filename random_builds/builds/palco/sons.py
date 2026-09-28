"""O som que o palco toca: id -> arquivo, e a lista de reserva.

1. `arquivos_de_som(ids)`: o arquivo de cada id pela MESMA cadeia do jogo
   (sound_config.json do runtime ou do pacote, %LOCALAPPDATA%\\neural-fights\\
   sounds\\ antes do pacote, <id>.wav/.ogg/.mp3, SOUND_FALLBACKS recursivo).
   Usa `audio_anotador.arquivos_de_som` da 16A quando ela estiver no disco; ate
   la, o espelho abaixo, que le as mesmas funcoes do jogo (nada de tabela
   copiada: `resolve_sound_file`, `load_sound_config` e `SOUND_FALLBACKS`).
   Resolvido a cada render: trocar um wav no jogo vale no proximo video.

2. `sons_dos_eventos(doc)`: RESERVA para timeline sem a secao `sons` (luta
   gravada antes da 16A, ou a 16A ainda fora do disco). Deriva os sons dos
   eventos da timeline com as regras de `AudioManager.play_attack/play_skill/
   play_special`, no formato da 16A (docs/palco/sons.md). Nao e o que o jogo
   tocou — e o que ele tocaria para estes eventos; o relatorio do render diz
   qual das duas fontes entrou.
"""
from __future__ import annotations

import math
import random

# Variacao de pitch por categoria: a MESMA tabela da 16A
# (audio_anotador.VARIACAO_DE_PITCH), para a reserva nao soar como metralhadora.
VARIACAO_DE_PITCH = {"golpes": 0.07, "impactos": 0.06, "projeteis": 0.04, "skills": 0.04,
                     "movimento": 0.08, "ambiente": 0.0, "ui": 0.0}
TIPOS_DE_LAMINA = ("Reta", "Dupla", "Corrente", "Transformável", "Transformavel")


def _espelho(ids) -> dict[str, str]:
    from neural_fights.effects.audio import AudioManager
    from neural_fights.effects.audio_paths import load_sound_config, resolve_sound_file

    config = load_sound_config()

    def resolver(nome: str, profundidade: int = 0):
        configurado = config.get(nome)
        if isinstance(configurado, str):
            achado = resolve_sound_file(configurado)
            if achado is not None:
                return achado
        for extensao in (".wav", ".ogg", ".mp3"):
            achado = resolve_sound_file(f"{nome}{extensao}")
            if achado is not None:
                return achado
        reserva = AudioManager.SOUND_FALLBACKS.get(nome)
        if reserva and reserva != nome and profundidade < 8:
            return resolver(reserva, profundidade + 1)
        return None

    saida = {}
    for nome in ids:
        achado = resolver(str(nome))
        if achado is not None:
            saida[str(nome)] = str(achado)
    return saida


def arquivos_de_som(ids) -> dict[str, str]:
    ids = sorted({str(i) for i in ids if i})
    if not ids:
        return {}
    try:
        from neural_fights.effects.audio_anotador import arquivos_de_som as da_16a
    except ImportError:
        return _espelho(ids)
    mapa = {str(k): str(v) for k, v in da_16a().items()}
    saida = {i: mapa[i] for i in ids if i in mapa}
    faltam = [i for i in ids if i not in saida]
    if faltam:
        saida.update(_espelho(faltam))
    return saida


def _volumes() -> tuple[dict, float, float]:
    """Categorias, master e sfx, como o AudioManager le no __init__."""
    try:
        from neural_fights.effects.audio_paths import load_sound_config
        volumes = dict(load_sound_config().get("_volumes") or {})
    except Exception:                                          # noqa: BLE001
        volumes = {}
    master = float(volumes.pop("master", 0.7))
    return volumes, master, 0.8


def _categoria(nome: str) -> str:
    try:
        from neural_fights.effects.audio import AudioManager
        tabela = AudioManager.SOUND_TO_CATEGORY
    except Exception:                                          # noqa: BLE001
        return "golpes"
    if nome in tabela:
        return tabela[nome]
    for prefixo, categoria in tabela.items():
        if nome.startswith(prefixo):
            return categoria
    return "golpes"


def _som_da_skill(tipo: str, elemento: str) -> str | None:
    elemento = (elemento or "").upper()
    if tipo == "PROJETIL":
        return {"FOGO": "fireball_cast", "GELO": "ice_cast", "RAIO": "lightning_bolt"}.get(elemento, "energy_blast")
    if tipo == "AREA":
        return {"FOGO": "fireball_impact", "GELO": "ice_impact"}.get(elemento, "energy_impact")
    return {"BEAM": "beam_fire", "DASH": "dash_whoosh", "BUFF": "buff_activate", "SUMMON": "summon_cast",
            "TRAP": "shield_up", "TRANSFORM": "buff_activate", "CHANNEL": "beam_fire",
            "TELEPORT": "teleport_out"}.get(tipo, "energy_blast")


def sons_dos_eventos(doc: dict) -> list[dict]:
    """A lista `sons` (formato 16A) derivada dos eventos da timeline."""
    hz = int(doc.get("hz", 60))
    por_quadro = int((doc.get("resultado") or {}).get("passos_por_quadro") or max(1, hz // 30))
    fps = hz / por_quadro
    seed = (doc.get("luta") or {}).get("seed") or 0
    rng = random.Random(f"neural-fights:som:{seed}")
    categorias, master, sfx = _volumes()
    armas = {l.get("slot"): (l.get("arma") or {}) for l in doc.get("lutadores") or [] if isinstance(l, dict)}
    itens: list[dict] = []

    def tocar(i: int, nome: str, base: float) -> None:
        # o relogio do gravador: um quadro a cada `por_quadro` passos; o som do
        # passo impar cai no quadro seguinte (docs/palco/timeline.md)
        t = math.ceil(i / por_quadro) / fps
        categoria = _categoria(nome)
        volume = min(1.0, base * float(categorias.get(categoria, 1.0)) * sfx * master)
        variacao = VARIACAO_DE_PITCH.get(categoria, 0.0)
        pitch = 1.0 + rng.uniform(-variacao, variacao) if variacao > 0 else 1.0
        itens.append({"t": round(t, 3), "id": nome, "volume": round(volume, 4), "pitch": round(pitch, 4)})

    tocar(0, "arena_start", 1.0)
    for ev in doc.get("eventos") or []:
        i, tipo = int(ev.get("i", 0)), ev.get("tipo")
        if tipo == "acerto":
            arma = armas.get(ev.get("autor")) or {}
            dano = float(ev.get("dano", 0.0))
            if arma.get("tipo") in TIPOS_DE_LAMINA and not str(ev.get("categoria", "")).startswith(("orbe", "projetil")):
                if ev.get("critico") or dano >= 35:
                    tocar(i, "slash_critical", 0.9)
                elif dano >= 20:
                    tocar(i, "slash_heavy", 0.8)
                else:
                    tocar(i, "slash_light", 0.7)
            else:
                tocar(i, "energy_impact", 0.7)
            if dano > 50:
                tocar(i, "impact_heavy", 0.8)
        elif tipo == "skill":
            nome = _som_da_skill(str(ev.get("tipo_skill") or ""), str(ev.get("elemento") or ""))
            if nome:
                tocar(i, nome, 1.0 if nome == "fireball_impact" else 0.7)
        elif tipo == "dash":
            tocar(i, "dash_whoosh", 0.7)
        elif tipo in ("esquiva", "desvio"):
            tocar(i, "dodge_whoosh", 0.7)
        elif tipo == "bloqueio":
            tocar(i, "shield_block", 0.8)
        elif tipo == "parry":
            tocar(i, "clash_swords", 0.8)
        elif tipo == "parede":
            # play_special("wall_hit") no jogo: sempre o leve; o pesado e do splat
            tocar(i, "wall_impact_light", 0.8)
        elif tipo == "wall_splat":
            tocar(i, "wall_impact_heavy", 0.9)
        elif tipo == "escudo_quebrou":
            tocar(i, "shield_break", 0.8)
        elif tipo == "cura":
            tocar(i, "heal_cast", 0.7)
        elif tipo == "ko":
            tocar(i, "ko_impact", 0.8)
            tocar(i, "slowmo_whoosh", 0.8)
    itens.sort(key=lambda s: s["t"])
    return itens
