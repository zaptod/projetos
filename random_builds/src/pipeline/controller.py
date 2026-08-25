"""PipelineController: seed -> data -> edit plan -> assets -> final.mp4.

Modes (sections 55-59):
  generate     full pipeline
  --generation-only   data only (thousands of builds for balancing)
  --preview           small/fast render
  --rerender ID       reuse the stored JSONs, never re-spin a roulette
"""
from __future__ import annotations

import json
from pathlib import Path

from ..generation.session_generator import SessionGenerator, load_config
from ..generation.random_engine import RandomEngine
from ..nf_bridge import exporter
from ..assets.catalog import AssetCatalog
from ..assets.selector import AssetSelector
from ..content.caption_generator import CaptionGenerator
from ..content.narration_generator import NarrationGenerator
from ..editing import artifacts
from ..editing.timeline_builder import TimelineBuilder
from ..video.renderer import VideoRenderer

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
ASSETS = ROOT / "assets"


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _next_id(prefixo: str = "generation") -> str:
    OUTPUTS.mkdir(exist_ok=True)
    existing = [int(p.name.split("_")[1]) for p in OUTPUTS.glob(f"{prefixo}_*")
                if p.name.split("_")[1].isdigit()]
    return f"{prefixo}_{(max(existing) + 1 if existing else 1):05d}"


def _next_generation_id() -> str:
    return _next_id("generation")


class PipelineController:
    def __init__(self):
        self.session = SessionGenerator()
        self.render_config = load_config("render.json")
        self.editing_config = load_config("editing.json")
        self.captions = CaptionGenerator(load_config("captions.json"),
                                         load_config("frases.json"))
        self.narration = NarrationGenerator()

    # ---------------------------------------------------------------- generate
    def generate(self, seed: int | None = None, generation_only: bool = False,
                 preview: bool = False, insert: bool = True,
                 identity: bool = True, nome_pedido: str | None = None,
                 autor_pedido: str | None = None) -> Path:
        """nome_pedido/autor_pedido: o nome escolhido num comentario.

        Vem cru do CLI e nao e validado aqui de proposito - quem decide se o
        pedido e aceitavel e src.character.nomes, que tambem grava o motivo da
        recusa no generation.json. Recusado, a geracao segue com o nome
        gerado e o video volta a apenas convidar.
        """
        generation_id = _next_generation_id()
        generation = self.session.generate(seed=seed, generation_id=generation_id,
                                           nome_pedido=nome_pedido,
                                           autor_pedido=autor_pedido)
        out_dir = OUTPUTS / generation_id
        self._write_data(out_dir, generation)
        self._build_edit_plan(out_dir, generation)
        print(f"[gen] {generation_id} seed={generation['seed']} "
              f"final={generation['final_score']} ({generation['build']['verdict_label']})")
        if not generation_only:
            self._render_media(out_dir, generation, preview)
        if insert and not generation_only:
            resultado = exporter.insert_into_database(
                generation["weapon"], generation["character"])
            _write_json(out_dir / "insercao.json", resultado)
            print(f"[db] inserido no neural_fights: {resultado['personagem']} "
                  f"+ {resultado['arma']}")
        if identity:
            self._enfileirar_identidade(generation)
        return out_dir

    def _enfileirar_identidade(self, generation: dict) -> None:
        """Grava as identidades e enfileira os TRES clipes; volta na hora.

        A roleta NAO espera o Digen: o worker (`python main.py identity worker`)
        baixa os mp4 depois e re-renderiza o video com eles dentro. Import
        tardio porque o modulo puxa patchright, que e opcional para quem so
        gera dados.

        As identidades sao gravadas ANTES da fila de proposito: e delas que os
        tres prompts saem, e e o arquivo em disco que permite re-gerar so o
        payoff meses depois sem o personagem mudar de rosto (secao 16).
        """
        try:
            from datetime import datetime, timedelta, timezone

            from ..identity import config as icfg
            from ..identity import queue, slots
            from ..identity.identity_model import gravar
            from ..identity.prompt import build_prompts
            gravar(generation)
            prompts = build_prompts(generation)
            ajustes = icfg.settings()
            espera = float((ajustes.get("referencias") or {})
                           .get("espera_referencias_s", 900))
            # Prazo ABSOLUTO, gravado agora e nunca renovado: e a rede que
            # impede o payoff de ficar esperando para sempre por uma imagem que
            # nao vem. Vencido, ele vai ao ar so com texto.
            prazo = (datetime.now(timezone.utc) + timedelta(seconds=espera)
                     ).isoformat(timespec="seconds")
            for slot in slots.JOBS:
                queue.enqueue(generation["generation_id"], prompts[slot],
                              slot=slot,
                              aguardar_ate=prazo if slots.depende_de(slot) else None)
            print(f"[identity] enfileirados {len(slots.JOBS)} artefatos de "
                  f"{generation['generation_id']}: "
                  + ", ".join(f"{s} ({slots.midia(s)})" for s in slots.JOBS))
        except Exception as exc:
            # Identidade e um extra: nunca pode derrubar uma geracao que deu certo.
            print(f"[identity] nao enfileirado ({exc})")

    def batch(self, count: int, seed_start: int | None = None,
              nome_pedido: str | None = None,
              autor_pedido: str | None = None) -> None:
        scores = []
        for i in range(count):
            seed = None if seed_start is None else seed_start + i
            # identity=False: um batch de balanceamento faz milhares de builds
            # e nenhuma delas vira video - enfileirar todas entupiria a fila.
            out_dir = self.generate(seed=seed, generation_only=True,
                                    identity=False, nome_pedido=nome_pedido,
                                    autor_pedido=autor_pedido)
            with open(out_dir / "build.json", encoding="utf-8") as fh:
                scores.append(json.load(fh)["final_score"])
        avg = round(sum(scores) / len(scores), 1)
        print(f"[batch] {count} builds | final min={min(scores)} avg={avg} max={max(scores)}")

    # -------------------------------------------------------------- torneio
    def torneio(self, seed: int | None = None, fonte: str = "misto",
                quantidade: int = 8, generation_only: bool = False,
                preview: bool = False) -> Path:
        from ..tournament.runner import TournamentSession
        from ..tournament.timeline import TournamentTimelineBuilder

        tournament_id = _next_id("tournament")
        out_dir = OUTPUTS / tournament_id
        alvo = self.editing_config["durations"].get("gameplay_alvo", 10.0)
        sessao = TournamentSession(load_config("scoring.json"), alvo_gameplay=alvo)

        def progresso(feitas, total, luta):
            print(f"[progresso] lutas {feitas}/{total}", flush=True)
            print(f"[luta] {luta['rodada_nome']}: {luta['vencedor']} venceu "
                  f"{luta['perdedor']} ({luta['ko_type']}, {luta['duracao']}s"
                  + (", ZEBRA" if luta["zebra"] else "") + ")", flush=True)

        # Sem video nao ha o que gravar; com video, cada luta e gravada e a
        # gravacao vira a fonte da verdade do resultado.
        torneio = sessao.gerar(seed=seed, fonte=fonte, quantidade=quantidade,
                               progresso=progresso,
                               gravar_em=None if generation_only else out_dir,
                               perfis=tuple(self.render_config["profiles"]))
        torneio["tournament_id"] = tournament_id
        _write_json(out_dir / "tournament.json", torneio)
        print(f"[torneio] {tournament_id} seed={torneio['seed']} "
              f"campeao={torneio['campeao']}"
              + (" (criado na roleta)" if torneio["campeao_gerado"] else ""))

        engine = RandomEngine(torneio["seed"])
        selector = AssetSelector(AssetCatalog(ASSETS))
        builder = TournamentTimelineBuilder(self.editing_config, self.captions,
                                            selector)
        edit_plan = builder.build(engine.fork("torneio:edicao"), torneio)
        _write_json(out_dir / "edit_plan.json", edit_plan)
        _write_json(out_dir / "captions.json", [
            {"start": e["start"], "duration": e["duration"], "text": e["caption"]}
            for e in edit_plan["events"] if e.get("caption")])

        if not generation_only:
            music = selector.select_music(engine.fork("music"))
            for profile in self.render_config["profiles"]:
                renderer = VideoRenderer(self.render_config, profile, preview)
                final = renderer.render(edit_plan, torneio, out_dir, music)
                print(f"[render:{profile}] {final} ({edit_plan['total_duration']}s)")
        return out_dir

    # ------------------------------------------------------------ importacao
    def import_reactions(self, source: str, category: str, move: bool = False) -> None:
        from ..assets.importer import import_reactions
        imported = import_reactions(Path(source), category, ASSETS, move=move)
        for entry in imported:
            duracao = f"{entry['duration']}s" if entry["duration"] else "?s"
            print(f"[import] {entry['id']} <- {entry['source']} "
                  f"({entry['category']}, {duracao})")
        print(f"[import] {len(imported)} video(s) na categoria '{category}'")

    def reactions_cli(self) -> None:
        from ..assets.reaction_cli import run
        run(ASSETS)

    def list_reactions(self) -> None:
        from ..assets.importer import list_reactions
        entries = list_reactions(ASSETS)
        if not entries:
            print("Biblioteca vazia. Use: python main.py import-reactions <pasta> --categoria <cat>")
            return
        for entry in entries:
            duracao = f"{entry['duration']}s" if entry.get("duration") else "?s"
            print(f"  {entry['id']}  {entry['category']:<9} {duracao:>6}  ({entry.get('source', '')})")
        print(f"Total: {len(entries)} reacao(oes)")

    def rerender_torneio(self, tournament_id: str, preview: bool = False,
                         refazer_edicao: bool = False) -> Path:
        """Re-renderiza um torneio SEM regravar as lutas.

        As lutas gravadas sao a parte cara (~20 s de CPU por luta); elas ficam
        em `gameplay/` e sao reaproveitadas. Com `refazer_edicao`, a timeline e
        remontada (legendas e reacoes novas) sobre as mesmas lutas.
        """
        out_dir = OUTPUTS / tournament_id
        with open(out_dir / "tournament.json", encoding="utf-8") as fh:
            torneio = json.load(fh)

        if refazer_edicao or not (out_dir / "edit_plan.json").exists():
            from ..tournament.timeline import TournamentTimelineBuilder
            engine = RandomEngine(torneio["seed"])
            selector = AssetSelector(AssetCatalog(ASSETS))
            builder = TournamentTimelineBuilder(self.editing_config,
                                                self.captions, selector)
            edit_plan = builder.build(engine.fork("torneio:edicao"), torneio)
            _write_json(out_dir / "edit_plan.json", edit_plan)
        else:
            with open(out_dir / "edit_plan.json", encoding="utf-8") as fh:
                edit_plan = json.load(fh)

        engine = RandomEngine(torneio["seed"])
        selector = AssetSelector(AssetCatalog(ASSETS))
        music = selector.select_music(engine.fork("music"))
        for profile in self.render_config["profiles"]:
            renderer = VideoRenderer(self.render_config, profile, preview)
            final = renderer.render(edit_plan, torneio, out_dir, music)
            print(f"[render:{profile}] {final} ({edit_plan['total_duration']}s)")
        return out_dir

    # ---------------------------------------------------------------- rerender
    def rerender(self, generation_id: str, preview: bool = False,
                 refazer_edicao: bool = False) -> Path:
        """Re-renderiza uma geracao SEM re-rolar nenhuma roleta.

        `refazer_edicao` remonta a timeline a partir do generation.json. Como o
        plano vem de `RandomEngine(generation["seed"])`, a remontagem e
        deterministica: sai identica, mais os eventos cujo asset passou a
        existir no disco (e o caso do clipe de identidade do Digen).
        """
        out_dir = OUTPUTS / generation_id
        with open(out_dir / "generation.json", encoding="utf-8") as fh:
            generation = json.load(fh)
        # never re-spin: reuse the stored plan (rebuild only if it is missing)
        if refazer_edicao or not (out_dir / "edit_plan.json").exists():
            self._build_edit_plan(out_dir, generation)
        self._render_media(out_dir, generation, preview)
        return out_dir

    # ---------------------------------------------------------------- internal
    def _write_data(self, out_dir: Path, generation: dict) -> None:
        _write_json(out_dir / "generation.json", generation)
        _write_json(out_dir / "character.json", generation["character"])
        _write_json(out_dir / "weapon.json", generation["weapon"])
        _write_json(out_dir / "rolls.json", generation["rolls"])
        _write_json(out_dir / "build.json",
                    {**generation["build"], "compatibility": generation["compatibility"]})

    def _build_edit_plan(self, out_dir: Path, generation: dict) -> None:
        engine = RandomEngine(generation["seed"])
        selector = AssetSelector(AssetCatalog(ASSETS))
        builder = TimelineBuilder(self.editing_config, self.captions, selector)
        edit_plan = builder.build(engine.fork("editing"), generation, out_dir)
        _write_json(out_dir / "edit_plan.json", edit_plan)
        _write_json(out_dir / "captions.json", [
            {"start": e["start"], "duration": e["duration"], "text": e["caption"]}
            for e in edit_plan["events"] if e.get("caption")])
        # Entregaveis da build (secoes 18 e 19): a montagem legivel, o
        # julgamento editorial de cada rolagem e as legendas no tempo do video.
        _write_json(out_dir / "timeline.json", artifacts.timeline(edit_plan))
        _write_json(out_dir / "evaluation.json",
                    artifacts.evaluation(generation, edit_plan, self.editing_config))
        (out_dir / "subtitles.srt").write_text(artifacts.srt(edit_plan),
                                               encoding="utf-8")
        script = self.narration.build_script(engine.fork("narration"), edit_plan, generation)
        _write_json(out_dir / "narration.json", script)

    def _render_media(self, out_dir: Path, generation: dict, preview: bool) -> None:
        # Os cartoes de personagem e de arma nao sao mais desenhados: eles
        # eram a revelacao do formato antigo e sairam junto com ela (secoes 2,
        # 3 e 15). Quem revela agora sao os clipes; sem clipe, um nameplate.
        # `visualization/` continua no lugar para quem quiser a imagem avulsa.
        with open(out_dir / "edit_plan.json", encoding="utf-8") as fh:
            edit_plan = json.load(fh)
        engine = RandomEngine(generation["seed"])
        selector = AssetSelector(AssetCatalog(ASSETS))
        music = selector.select_music(engine.fork("music"))
        # sempre dois videos: celular (9:16) e normal (16:9)
        for profile in self.render_config["profiles"]:
            renderer = VideoRenderer(self.render_config, profile, preview)
            final = renderer.render(edit_plan, generation, out_dir, music)
            print(f"[render:{profile}] {final} ({edit_plan['total_duration']}s)")
