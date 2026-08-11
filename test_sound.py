"""Diagnostico manual do sistema de audio.

Este modulo e import-safe para nao reproduzir som durante a descoberta de testes.
Execute-o diretamente quando quiser realizar o diagnostico interativo.
"""

from __future__ import annotations

import time


def main() -> int:
    import pygame

    from neural_fights.effects.audio import AudioManager

    pygame.init()
    pygame.mixer.init()

    audio = AudioManager.get_instance()
    print(f"Audio enabled: {audio.enabled}")
    print(f"Sounds loaded: {list(audio.sounds.keys())}")
    print(f"Sound groups: {list(audio.sound_groups.keys())}")

    print("\nPlaying wall_impact_light directly at full volume...")
    if "wall_impact_light" not in audio.sounds:
        print("Sound not found!")
        return 1

    sound = audio.sounds["wall_impact_light"]
    sound.set_volume(1.0)
    sound.play()
    time.sleep(3)
    print("Done!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
