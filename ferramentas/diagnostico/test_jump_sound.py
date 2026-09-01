"""Diagnostico manual dos sons de pulo e aterrissagem.

O codigo fica protegido por ``main`` para que a descoberta de testes seja segura.
"""

from __future__ import annotations

import time


def main() -> int:
    import pygame

    from neural_fights.effects.audio import AudioManager

    pygame.init()
    pygame.mixer.init()
    audio = AudioManager.get_instance()

    checks = (
        ("play_movement('jump')", lambda: audio.play_movement("jump", 10.0, 10.0), 1),
        ("play_movement('land')", lambda: audio.play_movement("land", 10.0, 10.0), 1),
        ("play('jump_start')", lambda: audio.play("jump_start"), 1),
        ("play('jump')", lambda: audio.play("jump"), 2),
    )
    for index, (label, callback, wait_seconds) in enumerate(checks, start=1):
        print(f"\n{index}. Testing {label}...")
        callback()
        time.sleep(wait_seconds)

    print("\nTest complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
