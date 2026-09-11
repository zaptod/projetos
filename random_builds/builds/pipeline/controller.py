"""PipelineController: seed -> data -> edit plan -> assets -> final.mp4.

Modes (sections 55-59):
  generate     full pipeline
  --generation-only   data only (thousands of builds for balancing)
  --preview           small/fast render
  --rerender ID       reuse the stored JSONs, never re-spin a roulette

Onda 9 (a luta como video):
  fight        UMA luta gravada e editada como elemento dominante
  estreia      a primeira luta do personagem que a roleta acabou de criar,
               gravada logo apos a insercao no banco (outputs/<gen>/estreia/)
  torneio      cada luta gravada com a camera DIRETOR, em resolucao nativa,
               com HUD do video e callouts sincronizados com o motor
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
from ..editing import artifacts, comentario
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
        self.scoring = load_config("scoring.json")
        self.captions = CaptionGenerator(load_config("captions.json"),
                                         load_config("frases.json"))
        self.narration = NarrationGenerator()

    @property
    def perfis(self) -> tuple[str, ...]:
        return tuple(self.render_config["profiles"])

    @property
    def gameplay(self) -> dict:
        from ..tournament.runner import config_gameplay
        return config_gameplay(self.editing_config)

    @property
    def estreia_melhor_de(self) -> int:
        """Formato da estreia. Impar; 1 volta ao video de luta unica."""
        return int(self.editing_config.get("estreia_melhor_de", 3))

    # ---------------------------------------------------------------- generate
    def generate(self, seed: int | None = None, generation_only: bool = False,
                 preview: bool = False, insert: bool = True,
                 identity: bool = True, nome_pedido: str | None = None,
                 autor_pedido: str | None = None, estreia: bool = True,
                 print_pedido: str | Path | None = None,
                 escolhas: dict | None = None) -> Path:
        """nome_pedido/autor_pedido: o nome escolhido num comentario.

        Vem cru do CLI e nao e validado aqui de proposito - quem decide se o
        pedido e aceitavel e builds.character.nomes, que tambem grava o motivo da
        recusa no generation.json. Recusado, a geracao segue com o nome
        gerado e o video volta a apenas convidar.

        `print_pedido`: o print do comentario. E COPIADO para a pasta da
        geracao antes da montagem — dali em diante ele pertence a geracao, e
        um re-render meses depois continua achando o mesmo arquivo mesmo que o
        original tenha saido da area de trabalho.

        `estreia`: depois de inserir no banco, grava a PRIMEIRA luta do
        personagem como video proprio (ver `_gravar_estreia`).
        """
        generation_id = _next_generation_id()
        generation = self.session.generate(seed=seed, generation_id=generation_id,
                                           nome_pedido=nome_pedido,
                                           autor_pedido=autor_pedido,
                                           escolhas=escolhas)
        out_dir = OUTPUTS / generation_id
        self._write_data(out_dir, generation)
        if generation.get("escolhas"):
            tela = generation["escolhas"]["tela"]
            print("[escolha] " + ", ".join(f"{k}={v}" for k, v in tela.items())
                  + " (o resto foi sorteado)")
        salvo = comentario.guardar(out_dir, print_pedido)
        if salvo is not None:
            print(f"[pedido] print do comentario -> {salvo.name}")
        self._build_edit_plan(out_dir, generation)
        print(f"[gen] {generation_id} seed={generation['seed']} "
              f"final={generation['final_score']} ({generation['build']['verdict_label']})")
        if insert and not generation_only:
            # Inserir e gravar a estreia ANTES do render: o round decisivo da
            # estreia entra no fim do video de build (`luta_no_build`), e o
            # plano precisa encontrar o clipe no disco para isso.
            resultado = exporter.insert_into_database(
                generation["weapon"], generation["character"])
            _write_json(out_dir / "insercao.json", resultado)
            print(f"[db] inserido no neural_fights: {resultado['personagem']} "
                  f"+ {resultado['arma']}")
            if estreia:
                gravada = self._gravar_estreia(out_dir, generation,
                                               resultado["personagem"], preview)
                if gravada is not None:
                    self._build_edit_plan(out_dir, generation)
        if not generation_only:
            self._render_media(out_dir, generation, preview)
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
            for slot in icfg.jobs_ativos(ajustes):
                queue.enqueue(generation["generation_id"], prompts[slot],
                              slot=slot,
                              aguardar_ate=prazo if slots.depende_de(slot) else None)
            print(f"[identity] enfileirados {len(icfg.jobs_ativos(ajustes))} artefatos de "
                  f"{generation['generation_id']}: "
                  + ", ".join(f"{s} ({slots.midia(s)})" for s in icfg.jobs_ativos(ajustes)))
        except Exception as exc:
            # Identidade e um extra: nunca pode derrubar uma geracao que deu certo.
            print(f"[identity] nao enfileirado ({exc})")

    def batch(self, count: int, seed_start: int | None = None,
              nome_pedido: str | None = None,
              autor_pedido: str | None = None,
              escolhas: dict | None = None) -> None:
        scores = []
        for i in range(count):
            seed = None if seed_start is None else seed_start + i
            # identity=False: um batch de balanceamento faz milhares de builds
            # e nenhuma delas vira video - enfileirar todas entupiria a fila.
            out_dir = self.generate(seed=seed, generation_only=True,
                                    identity=False, nome_pedido=nome_pedido,
                                    autor_pedido=autor_pedido,
                                    escolhas=escolhas)
            with open(out_dir / "build.json", encoding="utf-8") as fh:
                scores.append(json.load(fh)["final_score"])
        avg = round(sum(scores) / len(scores), 1)
        print(f"[batch] {count} builds | final min={min(scores)} avg={avg} max={max(scores)}")

    # ---------------------------------------------------------------- estreia
    def _gravar_estreia(self, out_dir: Path, generation: dict, nome: str,
                        preview: bool) -> Path | None:
        """A primeira luta do personagem recem-criado, como video PROPRIO.

        Sai em `outputs/<generation_id>/estreia/` no formato de luta unica.
        Nao entra no video da roleta porque estouraria o teto dele (secao 20:
        95 s) e roubaria o lugar do elemento dominante de la, que e a roleta.
        E o "parte 2" natural; o outro da roleta ja convida.

        O adversario vem de `escolher_adversario`: o gerado mais recente que
        ainda nao lutou com ele (continuidade entre videos) ou, sem isso,
        alguem de poder proximo — estreia nao pode ser atropelo por
        construcao. Falhar aqui nunca derruba a geracao: a estreia e
        recompensa, nao obrigacao.
        """
        from .. import atividade
        atividade.registrar("arena", "inicio", f"estreia de {nome}", "builds")
        try:
            from ..arena.ledger import Ledger, escolher_adversario
            from ..tournament.runner import (FightSession, fichas_do_banco,
                                             personagens_gerados)
            ledger = Ledger()
            fichas = fichas_do_banco()
            if nome not in fichas:
                print(f"[estreia] {nome} nao esta no banco; estreia pulada")
                return None
            gerados = [g for g in personagens_gerados() if g != nome]
            rng = RandomEngine(generation["seed"]).fork("estreia:adversario")
            adversario = escolher_adversario(nome, list(fichas), rng, gerados=gerados,
                                             fichas=fichas, ledger=ledger)
            if not adversario:
                print("[estreia] sem adversario disponivel")
                return None
            pasta = out_dir / "estreia"
            sessao = FightSession(self.scoring, gameplay=self.gameplay)
            fight = sessao.gerar(p1=nome, p2=adversario, seed=generation["seed"],
                                 gravar_em=pasta, perfis=self.perfis,
                                 origem="estreia", estreia_de=nome, ledger=ledger,
                                 progresso=self._progresso_luta,
                                 melhor_de=self.estreia_melhor_de)
            fight["fight_id"] = f"{generation['generation_id']}/estreia"
            self._entregar_luta(pasta, fight, preview)
            # Cada round e uma luta na carreira: o id do ledger separa por
            # `match_id`, entao os tres contam no cartel em vez de colapsar.
            for round_ in fight["lutas"]:
                ledger.registrar(round_, origem="estreia", video=str(pasta))
            luta = fight["luta"]
            placar = fight["placar"]
            _write_json(out_dir / "estreia.json", {
                "personagem": nome, "adversario": adversario,
                "vencedor": fight["vencedor"], "ko_type": luta["ko_type"],
                "duracao": luta["duracao"], "hp_vencedor": luta["hp_vencedor"],
                "marcas": luta["marcas"], "tier": luta["tier"], "seed": fight["seed"],
                "cenario": fight["cenario"], "pasta": str(pasta),
                "cartel_apos": ledger.cartel(nome),
                "melhor_de": fight["melhor_de"],
                "placar": placar,
                "rounds": [{"round": r.get("round", 1), "vencedor": r["vencedor"],
                            "ko_type": r["ko_type"], "duracao": r["duracao"],
                            "hp_vencedor": r["hp_vencedor"], "tier": r["tier"],
                            "seed": r["seed"]}
                           for r in fight["lutas"]],
            })
            resumo = (f"{placar[0]} x {placar[1]}" if fight["melhor_de"] > 1
                      else f"{luta['ko_type']}, {luta['duracao']}s")
            print(f"[estreia] {nome} vs {adversario}: {fight['vencedor']} venceu "
                  f"({resumo}) -> {pasta}")
            atividade.registrar("arena", "ok", f"{nome} vs {adversario} ({resumo})",
                                "builds")
            return pasta
        except Exception as exc:
            print(f"[estreia] nao gravada ({exc})")
            atividade.registrar("arena", "erro",
                                f"estreia de {nome}: {str(exc)[:160]}", "builds")
            return None

    # ------------------------------------------------------------------ duelo
    def duelo(self, p1: str | None = None, p2: str | None = None,
              seed: int | None = None, cenario: str | None = None,
              preview: bool = False) -> Path:
        """Onda 15B: a luta inteira em 20-35 s -> `outputs/duelo_XXXXX/`.

        O formato curto, publicado AO LADO do build e da estreia. Reusa a
        mesma FightSession e o mesmo ledger — o que muda e o orcamento de
        gravacao (`GAMEPLAY_POR_ORIGEM["duelo"]`) e a montagem, que e um
        evento so. Ver `builds/tournament/duelo.py` para o porque.
        """
        from ..arena.ledger import Ledger, escolher_adversario
        from ..tournament.runner import (FightSession, config_gameplay,
                                         fichas_do_banco, personagens_gerados)

        duelo_id = _next_id("duelo")
        out_dir = OUTPUTS / duelo_id
        ledger = Ledger()
        fichas = fichas_do_banco()
        seed = seed if seed is not None else RandomEngine.new_seed()
        rng = RandomEngine(seed).fork("duelo:participantes")
        gerados = personagens_gerados()
        if not p1:
            recentes = [g for g in reversed(gerados) if g in fichas]
            p1 = recentes[0] if recentes else rng.choice(sorted(fichas))
        if not p2:
            p2 = escolher_adversario(p1, list(fichas), rng, gerados=gerados,
                                     fichas=fichas, ledger=ledger)
        if not p2:
            raise ValueError("nao ha adversario disponivel no banco")

        sessao = FightSession(self.scoring,
                              gameplay=config_gameplay(self.editing_config, "duelo"))
        fight = sessao.gerar(p1=p1, p2=p2, seed=seed, cenario=cenario,
                             gravar_em=out_dir, perfis=self.perfis,
                             origem="duelo", ledger=ledger,
                             progresso=self._progresso_luta, melhor_de=1)
        fight["duelo_id"] = duelo_id
        _write_json(out_dir / "fight.json", fight)
        luta = fight["luta"]
        print(f"[duelo] {duelo_id} seed={fight['seed']} {p1} vs {p2} -> "
              f"{fight['vencedor']} ({luta['ko_type']}, {luta['duracao']}s)")
        self._entregar_duelo(out_dir, fight, preview)
        for round_ in fight["lutas"]:
            ledger.registrar(round_, origem="duelo", video=str(out_dir))
        return out_dir

    def rerender_duelo(self, duelo_id: str, preview: bool = False,
                       refazer_edicao: bool = False) -> Path:
        out_dir = OUTPUTS / duelo_id
        with open(out_dir / "fight.json", encoding="utf-8") as fh:
            fight = json.load(fh)
        self._entregar_duelo(
            out_dir, fight, preview,
            remontar=refazer_edicao or not (out_dir / "edit_plan.json").exists())
        return out_dir

    def _entregar_duelo(self, out_dir: Path, fight: dict, preview: bool,
                        remontar: bool = True) -> None:
        # Import tardio pelo mesmo motivo de `_entregar_luta`: quem so gera
        # DADOS nao pode puxar pygame por tabela.
        from ..tournament.duelo import DueloTimelineBuilder

        engine = RandomEngine(fight["seed"])
        if remontar:
            builder = DueloTimelineBuilder(self.editing_config, self.captions)
            edit_plan = builder.build(engine.fork("duelo:edicao"), fight)
            _write_json(out_dir / "edit_plan.json", edit_plan)
            _write_json(out_dir / "fight.json", fight)
        else:
            with open(out_dir / "edit_plan.json", encoding="utf-8") as fh:
                edit_plan = json.load(fh)
        music = self._musica(engine)
        for profile in self.perfis:
            renderer = VideoRenderer(self.render_config, profile, preview)
            final = renderer.render(edit_plan, fight, out_dir, music)
            print(f"[render:{profile}] {final} ({edit_plan['total_duration']}s)")

    # ------------------------------------------------------------------- luta
    def luta(self, p1: str | None = None, p2: str | None = None,
             seed: int | None = None, cenario: str | None = None,
             generation_only: bool = False, preview: bool = False,
             origem: str = "luta", melhor_de: int = 1) -> Path:
        """UM confronto -> `outputs/fight_XXXXX/` com fight.json + 2 videos.

        Sem `p1`, luta o ultimo personagem criado na roleta (ou um do banco);
        sem `p2`, o adversario sai da mesma politica da estreia. A luta vai
        para o ledger da arena: e assim que nasce cartel, revanche e titulo.
        Com `melhor_de > 1` o confronto vira serie e cada round entra no
        ledger — o cartel conta rounds, nao series.
        """
        from ..arena.ledger import Ledger, escolher_adversario
        from ..tournament.runner import (FightSession, fichas_do_banco,
                                         personagens_gerados)

        fight_id = _next_id("fight")
        out_dir = OUTPUTS / fight_id
        ledger = Ledger()
        fichas = fichas_do_banco()
        seed = seed if seed is not None else RandomEngine.new_seed()
        rng = RandomEngine(seed).fork("luta:participantes")
        gerados = personagens_gerados()
        if not p1:
            recentes = [g for g in reversed(gerados) if g in fichas]
            p1 = recentes[0] if recentes else rng.choice(sorted(fichas))
        if not p2:
            p2 = escolher_adversario(p1, list(fichas), rng, gerados=gerados,
                                     fichas=fichas, ledger=ledger)
        if not p2:
            raise ValueError("nao ha adversario disponivel no banco")

        sessao = FightSession(self.scoring, gameplay=self.gameplay)
        fight = sessao.gerar(p1=p1, p2=p2, seed=seed, cenario=cenario,
                             gravar_em=None if generation_only else out_dir,
                             perfis=self.perfis, origem=origem, ledger=ledger,
                             progresso=self._progresso_luta,
                             melhor_de=melhor_de)
        fight["fight_id"] = fight_id
        _write_json(out_dir / "fight.json", fight)
        luta = fight["luta"]
        placar = fight["placar"]
        desfecho = (f"{placar[0]} x {placar[1]}" if melhor_de > 1
                    else f"{luta['ko_type']}, {luta['duracao']}s, {luta['tier']}")
        print(f"[luta] {fight_id} seed={fight['seed']} {p1} vs {p2} -> "
              f"{fight['vencedor']} ({desfecho}"
              + (", ZEBRA" if luta["zebra"] else "") + ")")
        if not generation_only:
            self._entregar_luta(out_dir, fight, preview)
            for round_ in fight["lutas"]:
                ledger.registrar(round_, origem=origem, video=str(out_dir))
        return out_dir

    def rerender_luta(self, fight_id: str, preview: bool = False,
                      refazer_edicao: bool = False) -> Path:
        """Re-renderiza uma luta (ou uma estreia: `generation_00037/estreia`)
        SEM regravar: o gameplay cortado e reaproveitado."""
        out_dir = OUTPUTS / fight_id
        with open(out_dir / "fight.json", encoding="utf-8") as fh:
            fight = json.load(fh)
        self._entregar_luta(out_dir, fight, preview,
                            remontar=refazer_edicao or not (out_dir / "edit_plan.json").exists())
        return out_dir

    def _entregar_luta(self, out_dir: Path, fight: dict, preview: bool,
                       remontar: bool = True) -> None:
        from ..tournament.timeline import FightTimelineBuilder

        engine = RandomEngine(fight["seed"])
        selector = AssetSelector(AssetCatalog(ASSETS))
        if remontar:
            builder = FightTimelineBuilder(self.editing_config, self.captions, selector)
            edit_plan = builder.build(engine.fork("luta:edicao"), fight)
            _write_json(out_dir / "edit_plan.json", edit_plan)
            _write_json(out_dir / "captions.json", [
                {"start": e["start"], "duration": e["duration"], "text": e["caption"]}
                for e in edit_plan["events"] if e.get("caption")])
            _write_json(out_dir / "fight.json", fight)
        else:
            with open(out_dir / "edit_plan.json", encoding="utf-8") as fh:
                edit_plan = json.load(fh)
        music = self._musica(engine)
        for profile in self.perfis:
            renderer = VideoRenderer(self.render_config, profile, preview)
            final = renderer.render(edit_plan, fight, out_dir, music)
            print(f"[render:{profile}] {final} ({edit_plan['total_duration']}s)")

    @staticmethod
    def _progresso_luta(feitas: int, total: int, luta: dict) -> None:
        print(f"[progresso] lutas {feitas}/{total}", flush=True)
        print(f"[luta] {luta.get('rodada_nome', 'LUTA')}: {luta['vencedor']} venceu "
              f"{luta['perdedor']} ({luta['ko_type']}, {luta['duracao']}s"
              + (", ZEBRA" if luta.get("zebra") else "") + ")", flush=True)

    # -------------------------------------------------------------- torneio
    def torneio(self, seed: int | None = None, fonte: str = "misto",
                quantidade: int = 8, generation_only: bool = False,
                preview: bool = False) -> Path:
        from ..arena.ledger import Ledger
        from ..tournament.runner import TournamentSession
        from ..tournament.timeline import TournamentTimelineBuilder

        tournament_id = _next_id("tournament")
        out_dir = OUTPUTS / tournament_id
        alvo = self.editing_config["durations"].get("gameplay_alvo", 10.0)
        sessao = TournamentSession(self.scoring, alvo_gameplay=alvo,
                                   gameplay=self.gameplay)

        # Sem video nao ha o que gravar; com video, cada luta e gravada e a
        # gravacao vira a fonte da verdade do resultado.
        torneio = sessao.gerar(seed=seed, fonte=fonte, quantidade=quantidade,
                               progresso=self._progresso_luta,
                               gravar_em=None if generation_only else out_dir,
                               perfis=self.perfis)
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
            music = self._musica(engine)
            for profile in self.perfis:
                renderer = VideoRenderer(self.render_config, profile, preview)
                final = renderer.render(edit_plan, torneio, out_dir, music)
                print(f"[render:{profile}] {final} ({edit_plan['total_duration']}s)")
            # Toda luta gravada conta para a carreira — inclusive as do torneio.
            ledger = Ledger()
            for luta in torneio["lutas"]:
                ledger.registrar(luta, origem=f"torneio:{tournament_id}",
                                 video=str(out_dir))
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
        music = self._musica(engine)
        for profile in self.perfis:
            renderer = VideoRenderer(self.render_config, profile, preview)
            final = renderer.render(edit_plan, torneio, out_dir, music)
            print(f"[render:{profile}] {final} ({edit_plan['total_duration']}s)")
        return out_dir

    # ------------------------------------------------------------------ arena
    def arena_ranking(self, limite: int = 10) -> None:
        from ..arena.ledger import Ledger
        ledger = Ledger()
        linhas = ledger.ranking(limite)
        if not linhas:
            print("Ledger vazio: nenhuma luta gravada ainda "
                  "(python main.py fight, ou uma estreia da roleta).")
            return
        campeao = ledger.campeao_atual()
        for i, linha in enumerate(linhas, 1):
            marca = "  (campeao)" if linha["nome"] == campeao else ""
            print(f"  #{i:<2} {linha['nome']:<28} {linha['vitorias']}V-{linha['derrotas']}D"
                  f"  seq {linha['sequencia']:+d}{marca}")
        print(f"  {len(ledger.lutas)} luta(s) registradas em {ledger.caminho}")

    # ---------------------------------------------------------------- rerender
    def rerender(self, generation_id: str, preview: bool = False,
                 refazer_edicao: bool = False,
                 print_pedido: str | Path | None = None) -> Path:
        """Re-renderiza uma geracao SEM re-rolar nenhuma roleta.

        `refazer_edicao` remonta a timeline a partir do generation.json. Como o
        plano vem de `RandomEngine(generation["seed"])`, a remontagem e
        deterministica: sai identica, mais os eventos cujo asset passou a
        existir no disco (e o caso do clipe de identidade do Digen, e do print
        do comentario que chegou depois).

        `print_pedido` guarda o print AGORA e forca a remontagem: colocar a
        prova do pedido num video ja gerado nao pode exigir regerar a build.
        """
        out_dir = OUTPUTS / generation_id
        with open(out_dir / "generation.json", encoding="utf-8") as fh:
            generation = json.load(fh)
        salvo = comentario.guardar(out_dir, print_pedido)
        if salvo is not None:
            print(f"[pedido] print do comentario -> {salvo.name}")
            refazer_edicao = True
        # never re-spin: reuse the stored plan (rebuild only if it is missing)
        if refazer_edicao or not (out_dir / "edit_plan.json").exists():
            self._build_edit_plan(out_dir, generation)
        self._render_media(out_dir, generation, preview)
        return out_dir

    # ------------------------------------------------------------------- som
    def _musica(self, engine: RandomEngine) -> dict | None:
        """A trilha do catalogo; com assets/music vazio, a sintetizada.

        Uma musica colocada a mao sempre vence: a procedural so nasce numa
        pasta vazia (src/video/trilha.py) e fica la para os proximos renders.
        """
        selector = AssetSelector(AssetCatalog(ASSETS))
        music = selector.select_music(engine.fork("music"))
        if music is None and self.render_config.get("audio", {}).get(
                "trilha_procedural", True):
            from ..video import trilha
            criada = trilha.garantir_trilha(ASSETS / "music")
            if criada is not None:
                print(f"[trilha] {criada.name} (sintetizada em assets/music)")
                selector = AssetSelector(AssetCatalog(ASSETS))
                music = selector.select_music(engine.fork("music"))
        return music

    def _medir_falas(self, linhas: list[dict]) -> dict:
        """Duracao real de cada fala (cache), ou {} sem voz disponivel."""
        from ..content import voz
        cfg_audio = self.render_config.get("audio", {})
        cfg = voz.config(cfg_audio.get("voz"))
        if not cfg.get("ativa", True):
            return {}
        try:
            return voz.medir(linhas, cfg, taxa=int(cfg_audio.get("sample_rate", 44100)),
                             log=print)
        except Exception as exc:  # nunca derruba a montagem por causa da voz
            print(f"[roteiro] nao medi as falas ({exc}); plano segue sem ajuste")
            return {}

    def _voz(self, out_dir: Path) -> Path | None:
        """`voz.wav` da geracao (narration.json falado), ou None."""
        from ..content import voz
        cfg = self.render_config.get("audio", {})
        return voz.gerar(out_dir, cfg.get("voz"),
                         taxa=int(cfg.get("sample_rate", 44100)))

    def gerar_trilha(self, regerar: bool = False, seed: int = 7) -> None:
        from ..video import trilha
        if not trilha.disponivel():
            print("[trilha] numpy nao instalado (pip install numpy)")
            return
        caminho = trilha.garantir_trilha(ASSETS / "music", seed=seed, regerar=regerar)
        print(f"[trilha] {caminho}")

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
        # Roteiro solido: a fala e sintetizada e MEDIDA antes de o plano ser
        # cronometrado; cada cena cresce ate a narracao dela terminar. Sem
        # voz (desligada, sem rede), o plano fica como a direcao montou.
        script = self.narration.build_script(engine.fork("narration"), edit_plan, generation)
        medidas = self._medir_falas(script["lines"])
        if medidas:
            from ..editing.timeline_builder import ajustar_ao_roteiro
            edit_plan = ajustar_ao_roteiro(edit_plan, script["lines"], medidas,
                                           self.editing_config)
            script = self.narration.build_script(engine.fork("narration"), edit_plan,
                                                 generation)
            print(f"[roteiro] {len(medidas)} fala(s) medidas; plano ajustado para "
                  f"{edit_plan['total_duration']}s")
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
        _write_json(out_dir / "narration.json", script)

    def _render_media(self, out_dir: Path, generation: dict, preview: bool) -> None:
        # Os cartoes de personagem e de arma nao sao mais desenhados: eles
        # eram a revelacao do formato antigo e sairam junto com ela (secoes 2,
        # 3 e 15). Quem revela agora sao os clipes; sem clipe, um nameplate.
        # `visualization/` continua no lugar para quem quiser a imagem avulsa.
        with open(out_dir / "edit_plan.json", encoding="utf-8") as fh:
            edit_plan = json.load(fh)
        engine = RandomEngine(generation["seed"])
        music = self._musica(engine)
        # sempre dois videos: celular (9:16) e normal (16:9)
        from .. import atividade
        atividade.registrar("estudio", "inicio", out_dir.name, "builds")
        voz_track = self._voz(out_dir)
        palavras = None
        if voz_track is not None:
            from ..content.voz import caminho_palavras
            palavras = caminho_palavras(voz_track)
        for profile in self.perfis:
            renderer = VideoRenderer(self.render_config, profile, preview)
            final = renderer.render(edit_plan, generation, out_dir, music,
                                    voz=voz_track, gancho_b=edit_plan.get("gancho_b"),
                                    palavras=palavras)
            print(f"[render:{profile}] {final} ({edit_plan['total_duration']}s)")
            if getattr(renderer, "ultimo_gancho_b", None):
                print(f"[render:{profile}] gancho B -> {renderer.ultimo_gancho_b.name}")
        atividade.registrar("estudio", "ok", out_dir.name, "builds")
