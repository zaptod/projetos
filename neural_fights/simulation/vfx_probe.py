# -*- coding: utf-8 -*-
"""Sonda de VOLUME VISUAL — a régua da reforma "luta limpa".

Conta, por frame, quantos objetos de efeito estão vivos. A doutrina de
efeitos (plano da reforma) tem alvos numéricos; sem medir, "limpo" é
opinião. Uso:

    probe = VFXCountProbe()
    ... a cada frame: probe.amostrar(sim)
    print(probe.relatorio())

IMPORTANTE: rode com ``headless=False`` + ``SDL_VIDEODRIVER=dummy``. No
modo headless o Simulador pula os blocos de VFX (trilhas, aura,
ambiente, feedback de defesa) e a sonda mediria zero.
"""

LISTAS_SIM = (
    "particulas", "textos", "decals", "shockwaves", "impact_flashes",
    "hit_sparks", "magic_clashes", "block_effects", "dash_trails",
    "areas", "portais", "summons", "traps", "projeteis", "beams",
)


def _tam(obj, nome):
    return len(getattr(obj, nome, ()) or ())


class VFXCountProbe:
    """Amostra o volume de VFX por frame e resume em percentis."""

    def __init__(self):
        self.amostras = []          # totais por frame
        self.por_lista = {}         # nome -> [contagens]
        self.textos = []
        self.particulas = []

    # ------------------------------------------------------------------
    def amostrar(self, sim):
        detalhe = {}
        total = 0
        for nome in LISTAS_SIM:
            n = _tam(sim, nome)
            detalhe[nome] = n
            total += n

        mvfx = getattr(sim, "magic_vfx", None)
        if mvfx is not None:
            n_trail = sum(len(t.particulas) for t in mvfx.trails.values())
            n_beam = sum(len(b.particulas) for b in getattr(mvfx, "beams", ()))
            n_expl = sum(len(e.particulas) for e in mvfx.explosions)
            n_aura = sum(len(a.particulas) for a in mvfx.auras)
            n_sum = sum(len(s.particulas) for s in mvfx.summons)
            detalhe["magic_trails"] = n_trail
            detalhe["magic_beams"] = n_beam
            detalhe["magic_explosions"] = n_expl
            detalhe["magic_auras"] = n_aura
            detalhe["magic_summons"] = n_sum
            detalhe["magic_containers"] = (
                len(mvfx.trails) + len(getattr(mvfx, "beams", ()))
                + len(mvfx.explosions) + len(mvfx.auras) + len(mvfx.summons)
            )
            total += n_trail + n_beam + n_expl + n_aura + n_sum

        anims = getattr(sim, "attack_anims", None)
        if anims is not None:
            for nome in ("weapon_trails", "shockwaves", "sparks",
                         "screen_flashes", "anticipations", "ground_cracks",
                         "crater_marks"):
                n = _tam(anims, nome)
                detalhe[f"atk_{nome}"] = n
                total += n

        mov = getattr(sim, "movement_anims", None)
        if mov is not None:
            for nome in ("afterimage_trails", "dust_clouds", "speed_lines",
                         "motion_blurs", "recovery_flashes"):
                n = _tam(mov, nome)
                detalhe[f"mov_{nome}"] = n
                total += n

        for nome, valor in detalhe.items():
            self.por_lista.setdefault(nome, []).append(valor)
        self.amostras.append(total)
        self.textos.append(detalhe.get("textos", 0))
        self.particulas.append(detalhe.get("particulas", 0))

    # ------------------------------------------------------------------
    @staticmethod
    def _pct(valores, q):
        if not valores:
            return 0
        ordenados = sorted(valores)
        idx = min(len(ordenados) - 1, int(len(ordenados) * q))
        return ordenados[idx]

    def resumo(self):
        """Números que a doutrina cobra."""
        return {
            "frames": len(self.amostras),
            "vfx_p50": self._pct(self.amostras, 0.50),
            "vfx_p90": self._pct(self.amostras, 0.90),
            "vfx_p99": self._pct(self.amostras, 0.99),
            "vfx_max": max(self.amostras) if self.amostras else 0,
            "textos_p90": self._pct(self.textos, 0.90),
            "textos_max": max(self.textos) if self.textos else 0,
            "particulas_p99": self._pct(self.particulas, 0.99),
        }

    def piores_listas(self, n=10):
        """As listas que mais contribuem (média por frame)."""
        medias = {
            nome: sum(vals) / max(1, len(vals))
            for nome, vals in self.por_lista.items()
        }
        return sorted(medias.items(), key=lambda kv: -kv[1])[:n]

    def relatorio(self):
        r = self.resumo()
        linhas = [
            f"frames={r['frames']}",
            f"VFX  p50={r['vfx_p50']:4d}  p90={r['vfx_p90']:4d}  "
            f"p99={r['vfx_p99']:4d}  max={r['vfx_max']:4d}",
            f"textos p90={r['textos_p90']:3d}  max={r['textos_max']:3d}",
            f"particulas p99={r['particulas_p99']:4d}",
            "maiores fontes (média/frame):",
        ]
        for nome, media in self.piores_listas():
            if media >= 0.5:
                linhas.append(f"   {nome:22s} {media:7.1f}")
        return "\n".join(linhas)

    # compat com o protocolo de probe do HeadlessMatchRunner
    def on_inicio(self, sim):
        pass

    def on_frame(self, sim, dt):
        self.amostrar(sim)
