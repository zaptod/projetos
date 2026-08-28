# -*- coding: utf-8 -*-
"""Gerador de demos de skill estilo LoL (Onda 11D).

Uma cena encenada por skill: conjurador "Demo" + boneco de treino numa arena
limpa, cast roteirizado pela GEOMETRIA DO CONTRATO (core/skill_contract),
gravada offscreen com o mesmo encanamento do fight_recorder. O mp4 sai LIMPO
(sem texto queimado): quem descreve é o consumidor — a UI ao lado do preview
e a placa do renderer do random_builds (doutrina do HUD).

Saída:  outputs/skill_demos/<slug>.mp4  +  manifest.json no molde do
reactions catalog, com hash do contrato — ``--todas`` regrava só o que mudou.

Uso:
    python -m neural_fights.recording.skill_demo --skill "Bola de Fogo"
    python -m neural_fights.recording.skill_demo --todas [--forcar]
    python -m neural_fights.recording.skill_demo --skill X --sem-video
"""
from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import unicodedata  # noqa: E402
from pathlib import Path  # noqa: E402

from neural_fights.core.skill_contract import derivar_contrato  # noqa: E402
from neural_fights.core.skills import SKILL_DB, get_skill_data  # noqa: E402
from neural_fights.utils.config import FPS  # noqa: E402
from neural_fights.utils.console import SafeArgumentParser, safe_print  # noqa: E402

RAIZ_CHECKOUT = Path(__file__).resolve().parents[2]
PASTA_DEMOS = RAIZ_CHECKOUT / "outputs" / "skill_demos"
RESOLUCAO = (1280, 720)
FPS_SAIDA = 30
SEED_DEMO = 411


def slug_da_skill(nome: str) -> str:
    """"Julgamento Celestial" -> "julgamento-celestial" (ASCII, estável)."""
    texto = unicodedata.normalize("NFKD", nome)
    texto = texto.encode("ascii", "ignore").decode("ascii").lower()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto or "skill"


def hash_do_contrato(nome: str) -> str:
    """sha1 do contrato canônico — muda quando o COMPORTAMENTO declarado muda.

    ``fontes`` (quais kits alcançam a skill) fica fora: mexer nos pools não
    muda o que a demo mostra e não pode regravar 116 clipes à toa.
    """
    dados = derivar_contrato(nome).to_dict()
    dados.pop("fontes", None)
    dump = json.dumps(dados, ensure_ascii=True, sort_keys=True)
    return hashlib.sha1(dump.encode("utf-8")).hexdigest()


def carregar_manifest() -> dict:
    caminho = PASTA_DEMOS / "manifest.json"
    if caminho.is_file():
        try:
            with open(caminho, "r", encoding="utf-8") as arquivo:
                return json.load(arquivo)
        except (ValueError, OSError):
            return {}
    return {}


def salvar_manifest(manifest: dict) -> None:
    PASTA_DEMOS.mkdir(parents=True, exist_ok=True)
    with open(PASTA_DEMOS / "manifest.json", "w", encoding="utf-8") as arquivo:
        json.dump(manifest, arquivo, ensure_ascii=True, sort_keys=True, indent=2)
        arquivo.write("\n")


def caminho_da_demo(nome: str) -> Path | None:
    """mp4 da skill segundo o manifest (None sem demo gravada)."""
    entrada = carregar_manifest().get(nome)
    if not entrada:
        return None
    caminho = PASTA_DEMOS / entrada.get("file", "")
    return caminho if caminho.is_file() else None


def _duracao_da_cena(contrato) -> float:
    base = 1.2 + contrato.delay + max(contrato.duracao, 1.5) + 1.3
    return max(4.0, min(8.0, base))


def gravar_demo(nome: str, *, saida: Path | None = None, seed: int = SEED_DEMO,
                sem_video: bool = False) -> dict:
    """Grava a demo de UMA skill (ou só encena, com ``sem_video``)."""
    from neural_fights.recording.fight_recorder import _abrir_ffmpeg
    from neural_fights.simulation.simulacao import Simulador
    from neural_fights.tools.skill_check import (
        _Observador,
        _consequencias_exigidas,
        _distancia_do_cenario,
        _provider_sintetico,
    )
    import pygame

    data = get_skill_data(nome)
    contrato = derivar_contrato(nome)
    resultado = {
        "skill": nome,
        "ok": False,
        "arquivo": None,
        "duracao": 0.0,
        "consequencia_observada": False,
        "erro": None,
    }
    if contrato.tipo == "NADA":
        resultado["erro"] = "skill sentinela"
        return resultado
    if data.get("ativa_ao_morrer") or data.get("revive_hp_percent"):
        resultado["erro"] = "passiva de morte não é castável em demo"
        return resultado

    caster_nome, alvo_nome = "Demo", "Alvo"
    sim = None
    ffmpeg = None
    try:
        sim = Simulador(
            match_config={
                "p1_nome": caster_nome,
                "p2_nome": alvo_nome,
                "cenario": "Arena",
                "best_of": 1,
                "modo_live": True,
                "resolucao": list(RESOLUCAO),
                "camera_modo": "AUTO",
                "overlays": {"hud": False, "analise": False,
                             "hitbox_debug": False},
                "rotulo_plano": False,
                "nomes_exibicao": {caster_nome: " ", alvo_nome: " "},
            },
            headless=False,
            seed=seed,
            roster_provider=_provider_sintetico(caster_nome, alvo_nome),
        )
        p1, p2 = sim.p1, sim.p2
        p1.brain = None
        p2.brain = None

        distancia = _distancia_do_cenario(contrato)
        cx, cy = 8.0, 5.0
        p1.pos[0], p1.pos[1] = cx - distancia / 2.0, cy
        p2.pos[0], p2.pos[1] = cx + distancia / 2.0, cy
        p1.angulo_olhar = 0.0
        p2.angulo_olhar = 180.0

        p1.mana_max = max(p1.mana_max, 1000.0)
        p1.mana = p1.mana_max
        p1.vida = p1.vida_max * 0.6
        # O boneco não pode cair no meio da demo (KO viraria comemoração).
        p2.vida_max = 5000.0
        p2.vida = 5000.0

        p1.skills_classe = [
            {"nome": nome, "custo": data.get("custo", 0.0), "data": data}
        ]
        p1.cd_skills[nome] = 0.0

        if contrato.condicao == "ALVO_BAIXA_VIDA":
            p2.vida = p2.vida_max * max(0.05, contrato.condicao_limiar - 0.1)
        elif contrato.condicao_status:
            p2.tomar_dano(
                0.0, 0.0, 0.0, contrato.condicao_status,
                atacante=p1, metadata_impacto={"eh_skill": True},
            )
        if data.get("reverte_estado") is not None:
            for _ in range(int((float(data["reverte_estado"]) + 0.6) * FPS)):
                sim.update(1.0 / FPS)

        observador = _Observador(sim, contrato)
        from neural_fights.core.skill_contract import custo_vida_do_cast
        observador.ancorar_pre_cast(custo_vida_do_cast(contrato, p1.vida_max))
        exigidas = _consequencias_exigidas(contrato)

        duracao_cena = _duracao_da_cena(contrato)
        proposito = None if contrato.tipo == "DASH" else "ENGAGE"
        t_cast = 0.5
        t_recast = (
            t_cast + contrato.delay + max(1.2, contrato.duracao) + 0.6
            if contrato.delay + contrato.duracao < 2.0
            else None
        )
        if t_recast is not None and t_recast > duracao_cena - 1.2:
            t_recast = None

        largura, altura = sim.tela.get_size()
        if not sem_video:
            destino = saida or (PASTA_DEMOS / f"{slug_da_skill(nome)}.mp4")
            ffmpeg = _abrir_ffmpeg(
                destino, largura, altura, FPS_SAIDA, 20, "veryfast"
            )

        passo = 1.0 / FPS
        a_cada = max(1, round(FPS / FPS_SAIDA))
        capturados = 0
        castou = False
        t_ko = None
        total_frames = int(duracao_cena * FPS)
        for indice in range(total_frames):
            t = indice * passo
            if not castou and t >= t_cast:
                castou = p1.usar_skill_classe(nome, alvo=p2, proposito=proposito)
                if not castou:
                    resultado["erro"] = "cast recusado pelo runtime"
                    return resultado
            elif t_recast is not None and t >= t_recast:
                p1.cd_skills[nome] = 0.0
                p1.mana = p1.mana_max
                p1.usar_skill_classe(nome, alvo=p2, proposito=proposito)
                t_recast = None

            pygame.event.pump()
            dt = sim.avancar_relogio(passo)
            sim.update(dt)
            sim.desenhar()
            observador.amostrar()

            if ffmpeg is not None and indice % a_cada == 0:
                ffmpeg.stdin.write(pygame.image.tobytes(sim.tela, "RGB"))
                capturados += 1

            # Se apesar do colchão o boneco cair (execute), corta curto.
            if sim.round_finalizado:
                if t_ko is None:
                    t_ko = t
                elif t - t_ko >= 0.8:
                    break

        resultado["consequencia_observada"] = bool(
            (exigidas & observador.observadas) or not exigidas
        )
        resultado["duracao"] = round(capturados / FPS_SAIDA, 2) if capturados \
            else round(duracao_cena, 2)
        resultado["ok"] = resultado["consequencia_observada"]
        if ffmpeg is not None:
            resultado["arquivo"] = str(
                saida or (PASTA_DEMOS / f"{slug_da_skill(nome)}.mp4")
            )
        return resultado
    except Exception as exc:
        resultado["erro"] = f"{type(exc).__name__}: {exc}"
        return resultado
    finally:
        if ffmpeg is not None:
            try:
                ffmpeg.stdin.close()
                ffmpeg.wait(timeout=60)
            except Exception:
                pass
        if sim is not None:
            try:
                sim.close()
            except Exception:
                pass


def gerar(nomes=None, *, forcar: bool = False, sem_video: bool = False) -> int:
    """Gera as demos pedidas (todas por padrão), pulando hash inalterado."""
    alvos = nomes or [
        nome
        for nome in SKILL_DB
        if nome != "Nenhuma"
        and not SKILL_DB[nome].get("ativa_ao_morrer")
        and not SKILL_DB[nome].get("revive_hp_percent")
    ]
    manifest = carregar_manifest()
    falhas = 0
    geradas = 0
    puladas = 0
    for nome in alvos:
        hash_atual = hash_do_contrato(nome)
        entrada = manifest.get(nome)
        arquivo_existe = bool(
            entrada and (PASTA_DEMOS / entrada.get("file", "")).is_file()
        )
        if (
            not forcar
            and not sem_video
            and arquivo_existe
            and entrada.get("hash") == hash_atual
        ):
            puladas += 1
            continue
        resultado = gravar_demo(nome, sem_video=sem_video)
        if not resultado["ok"]:
            falhas += 1
            safe_print(f"FALHA {nome}: {resultado['erro'] or 'sem consequência'}")
            continue
        geradas += 1
        if not sem_video:
            manifest[nome] = {
                "file": f"{slug_da_skill(nome)}.mp4",
                "duration": resultado["duracao"],
                "seed": SEED_DEMO,
                "hash": hash_atual,
            }
            salvar_manifest(manifest)
        safe_print(f"OK    {nome} ({resultado['duracao']:.1f}s)")
    safe_print(
        f"\n{geradas} geradas | {puladas} em dia (hash) | {falhas} falhas"
    )
    return 1 if falhas else 0


def main(argv=None) -> int:
    parser = SafeArgumentParser(
        prog="python -m neural_fights.recording.skill_demo",
        description="Gera clipes de demonstração por skill (estilo LoL).",
    )
    parser.add_argument("--skill", help="uma skill específica")
    parser.add_argument("--todas", action="store_true")
    parser.add_argument("--forcar", action="store_true",
                        help="regrava mesmo com hash em dia")
    parser.add_argument("--sem-video", action="store_true",
                        help="encena e mede sem codificar (teste)")
    args = parser.parse_args(argv)

    if args.skill:
        nomes = [args.skill]
    elif args.todas:
        nomes = None
    else:
        parser.error("informe --skill ou --todas")
    return gerar(nomes, forcar=args.forcar, sem_video=args.sem_video)


if __name__ == "__main__":
    raise SystemExit(main())
