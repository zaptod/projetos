"""Instala e testa overrides locais de áudio sem alterar assets do pacote.

Execute depois de instalar o projeto, por exemplo com ``pip install -e .``.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from neural_fights.effects.audio_paths import (
    SUPPORTED_SOUND_EXTENSIONS,
    get_runtime_sound_dir,
    load_sound_config,
    remove_runtime_sound_overrides,
    save_sound_config,
)


def _validar_evento(event_id: str) -> str:
    if not event_id or Path(event_id).name != event_id:
        raise ValueError("o identificador do evento deve ser um nome simples")
    return event_id


def instalar_override(event_id: str, arquivo: str | Path) -> Path:
    """Copia um arquivo para o runtime e associa-o ao evento."""

    event_id = _validar_evento(event_id)
    origem = Path(arquivo).expanduser().resolve(strict=True)
    if not origem.is_file():
        raise ValueError(f"a origem não é um arquivo: {origem}")

    extensao = origem.suffix.lower()
    if extensao not in SUPPORTED_SOUND_EXTENSIONS:
        formatos = ", ".join(SUPPORTED_SOUND_EXTENSIONS)
        raise ValueError(f"formato não suportado: {extensao or '(sem extensão)'}; use {formatos}")

    runtime_dir = get_runtime_sound_dir()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    destino = (runtime_dir / f"{event_id}{extensao}").resolve()

    if origem != destino:
        remove_runtime_sound_overrides(event_id)
        shutil.copy2(origem, destino)

    config = load_sound_config()
    config[event_id] = destino.name
    save_sound_config(config)
    return destino


def remover_override(event_id: str) -> int:
    """Remove a associação e os arquivos locais, preservando o pacote."""

    event_id = _validar_evento(event_id)
    removidos = remove_runtime_sound_overrides(event_id)
    config = load_sound_config()
    config.pop(event_id, None)
    save_sound_config(config)
    return removidos


def tocar_evento(event_id: str) -> None:
    """Recarrega a configuração e toca um evento pela API pública."""

    from neural_fights.effects.audio import AudioManager

    event_id = _validar_evento(event_id)
    audio = AudioManager.get_instance()
    audio.reload_sounds()
    audio.play(event_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="comando", required=True)

    subparsers.add_parser("caminho", help="mostra o diretório local de áudio")

    instalar = subparsers.add_parser("instalar", help="instala um override local")
    instalar.add_argument("evento", help="identificador, por exemplo slash_light")
    instalar.add_argument("arquivo", help="arquivo WAV, OGG ou MP3")

    remover = subparsers.add_parser("remover", help="remove um override local")
    remover.add_argument("evento")

    tocar = subparsers.add_parser("tocar", help="toca um evento configurado")
    tocar.add_argument("evento")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.comando == "caminho":
            print(get_runtime_sound_dir())
        elif args.comando == "instalar":
            print(f"Override instalado em: {instalar_override(args.evento, args.arquivo)}")
        elif args.comando == "remover":
            print(f"Arquivos locais removidos: {remover_override(args.evento)}")
        elif args.comando == "tocar":
            tocar_evento(args.evento)
    except (OSError, TypeError, ValueError) as exc:
        parser = build_parser()
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
