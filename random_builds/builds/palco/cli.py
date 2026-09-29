"""`main.py palco ...` e `main.py duelo --palco`: o palco pela linha de comando.

Nada aqui publica nem entra no catalogo: tudo sai em outputs/_palco/.

    python main.py palco render --timeline T.json --mp4 X.mp4
    python main.py palco render --seed 883770751 --p1 "A" --p2 "B" --arena Torre
    python main.py palco validar --timeline T.json
    python main.py palco testes
    python main.py palco editor                     # abre o editor (APPDATA no E:)
    python main.py palco sintetica --destino T.json --duracao 2
    python main.py palco ab --duelo duelo_00016     # o duelo publicado x o palco
    python main.py palco vitrine                    # video de revisao das pecas (16E)
    python main.py palco pecas-do-rosto             # refaz as pecas do rosto do SVG do Kenney
    python main.py palco efeitos-cc0                # refaz texturas e cenas de tipo x elemento
    python main.py duelo --seed N --palco [--ab]    # um duelo novo so no palco
"""
from __future__ import annotations

import json
from pathlib import Path

from . import ab, config, fonte, godot, render, sintetica, vitrine
from .config import ErroPalco


def construir_parser():
    import argparse

    pal = argparse.ArgumentParser(prog="main.py palco",
                                  description="Onda 16D: a luta desenhada pelo Godot a partir da timeline "
                                              "(nada publica; saida em outputs/_palco)")
    psub = pal.add_subparsers(dest="palco_command", required=True)
    ren = psub.add_parser("render", help="timeline -> mp4 conferido (ou --seed: simula e renderiza)")
    ren.add_argument("--timeline", default=None, help="timeline v1 (.json ou .gcpf)")
    # `--saida` NAO: o main.py a toma para o log (_redirecionar_saida).
    ren.add_argument("--mp4", default=None, help="mp4 de saida (padrao: outputs/_palco/...)")
    ren.add_argument("--seed", type=int, default=None, help="simula a luta desta seed (timeline da 16C)")
    ren.add_argument("--p1", default=None)
    ren.add_argument("--p2", default=None)
    ren.add_argument("--arena", default=None)
    ren.add_argument("--sem-corte", action="store_true", help="com --seed, sem corte de tedio")
    ren.add_argument("--estilo", action="append", default=[], metavar="CAMPO=VALOR",
                     help="sobrepoe um campo do estilo global (repetivel), ex. --estilo tremor=0")
    ren.add_argument("--hud", action="store_true", help="liga o HUD do palco (nome e vida)")
    ren.add_argument("--quadros", type=int, default=None, help="so os N primeiros quadros (previa)")
    ren.add_argument("--manter-avi", action="store_true", help="nao apaga o AVI intermediario")
    val = psub.add_parser("validar", help="valida uma timeline no Godot, sem janela")
    val.add_argument("--timeline", required=True)
    psub.add_parser("testes", help="roda os testes do nucleo do palco no Godot, sem janela")
    psub.add_parser("editor", help="abre o projeto do palco no editor do Godot (APPDATA no E:)")
    sin = psub.add_parser("sintetica", help="escreve uma timeline de mentira (testes e exemplo)")
    sin.add_argument("--destino", required=True, help="arquivo .json da timeline")
    sin.add_argument("--duracao", type=float, default=2.0)
    pab = psub.add_parser("ab", help="a MESMA luta no visual de hoje e no palco, lado a lado")
    pab.add_argument("--duelo", required=True, metavar="DUELO_ID", help="duelo ja gravado (duelo_00016)")
    pab.add_argument("--velho", default=None, metavar="MP4",
                     help="o lado de HOJE (padrao: o final_celular.mp4 do duelo)")
    pab.add_argument("--hud", action="store_true", help="liga o HUD do palco (nome, vida e plano) no lado do palco")
    pab.add_argument("--rotulo", default="PALCO 16E", help="rotulo do lado do palco no A/B")
    pab.add_argument("--pasta", default=None, help="pasta de saida (padrao: outputs/_palco/ab_<duelo>)")
    pvi = psub.add_parser("vitrine", help="video de revisao: as pecas da biblioteca animadas (16E)")
    pvi.add_argument("--mp4", default=None, help="mp4 de saida (padrao: outputs/_palco/vitrine/vitrine.mp4)")
    pvi.add_argument("--so", default=None, help="so as paginas cujo titulo contem isto (ex. rostos)")
    pro = psub.add_parser("pecas-do-rosto", help="recorta as pecas do rosto do SVG do Kenney (CC0) a 12x")
    pro.add_argument("--folha", default=None, help="png com as pecas lado a lado, para conferir")
    pef = psub.add_parser("efeitos-cc0", help="texturas CC0 e cenas de efeito por tipo x elemento")
    pef.add_argument("--so-cenas", action="store_true", help="so reescreve as cenas (nao traz texturas)")
    return pal


def main(argv: list[str] | None = None) -> int:
    """Entrada de `main.py palco ...` (o main.py so importa isto no ramo do palco)."""
    return executar(construir_parser().parse_args(argv))


def _estilo(pares: list[str]) -> dict:
    campos = {}
    for par in pares or []:
        if "=" not in par:
            raise ErroPalco(f"--estilo espera CAMPO=VALOR: {par}")
        chave, valor = par.split("=", 1)
        try:
            campos[chave.strip()] = json.loads(valor)
        except ValueError:
            campos[chave.strip()] = valor
    return campos


def escolher_luta(*, p1: str | None, p2: str | None, seed: int | None, arena: str | None) -> tuple:
    """(p1, p2, seed, cenario) com as MESMAS regras do `main.py duelo`: rodizio
    para quem nao veio, e a arena pela seed (fork "luta:arena")."""
    from ..arena import rodizio
    from ..arena.ledger import Ledger
    from ..generation.random_engine import RandomEngine
    from ..tournament.runner import ARENAS_DE_VIDEO, fichas_do_banco, personagens_gerados

    seed = seed if seed is not None else RandomEngine.new_seed()
    if not (p1 and p2):
        rng = RandomEngine(seed).fork("duelo:participantes")
        p1, p2 = rodizio.escolher_par(fichas_do_banco(), personagens_gerados(), rng, ledger=Ledger(),
                                      p1=p1, p2=p2)
    if not p1 or not p2:
        raise ErroPalco("nao ha dois personagens com ficha no banco vivo para lutar")
    cenario = arena or RandomEngine(seed).fork("luta:arena").choice(ARENAS_DE_VIDEO)
    return p1, p2, seed, cenario


def _gameplay_duelo() -> dict:
    from ..generation.session_generator import load_config
    from ..tournament.runner import config_gameplay
    return config_gameplay(load_config("editing.json"), "duelo")


def _salvar_timeline(doc: dict, destino: Path) -> Path:
    try:
        from neural_fights.recording import timeline_arquivo
    except ImportError:
        destino = destino.with_suffix(".json")
        destino.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        return destino
    timeline_arquivo.salvar(doc, destino, compressao="zstd")
    return destino


def render_da_seed(*, p1, p2, seed, arena, pasta: Path | None = None, sem_corte: bool = False,
                   estilo: dict | None = None, hud: bool = False, quadros: int | None = None) -> dict:
    cfg = config.carregar()
    p1, p2, seed, cenario = escolher_luta(p1=p1, p2=p2, seed=seed, arena=arena)
    duelo_cfg = cfg.get("duelo") or {}
    print(f"[palco] {p1} x {p2} | seed {seed} | {cenario} | simulando (sem desenhar)...", flush=True)
    doc, usada = fonte.timeline_da_luta(p1=p1, p2=p2, seed=seed, cenario=cenario,
                                        camera_largura_min_m=duelo_cfg.get("camera_largura_min_m"),
                                        camera_espera_zoom_in=duelo_cfg.get("camera_espera_zoom_in"))
    corte = None if sem_corte else fonte.corte_de_tedio(doc, _gameplay_duelo())
    if corte is not None:
        doc["remapeamento"] = {"relogio": "gravacao", "trechos": corte}
    pasta = Path(pasta) if pasta else config.SAIDAS / f"palco_{usada}"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = _salvar_timeline(doc, pasta / "timeline.gcpf")
    res = doc.get("resultado") or {}
    print(f"[palco] {res.get('vencedor')} venceu em {res.get('duracao_jogo')} s de jogo; "
          f"corte: {corte}", flush=True)
    return render.renderizar(arquivo, pasta / "palco_celular.mp4", estilo=estilo, hud=hud, quadros=quadros)


def ab_do_duelo(duelo_id: str, velho: str | None = None, *, hud: bool = False, rotulo_palco: str = "PALCO 16D",
                pasta: Path | None = None) -> dict:
    """O duelo ja gravado (visual de hoje) contra o palco: mesma seed, mesma
    arena, MESMO corte (o do fight.json)."""
    cfg = config.carregar()
    pasta_duelo = config.OUTPUTS / duelo_id
    fight = json.loads((pasta_duelo / "fight.json").read_text(encoding="utf-8"))
    luta = fight["luta"]
    trechos = [[float(a), float(b), 1.0] for a, b in (luta.get("clipes") or {}).get("celular", {}).get("trechos") or []]
    duelo_cfg = cfg.get("duelo") or {}
    print(f"[palco] A/B de {duelo_id}: {luta['p1']} x {luta['p2']} | seed {luta['seed']} | {luta['cenario']}",
          flush=True)
    doc, _usada = fonte.timeline_da_luta(p1=luta["p1"], p2=luta["p2"], seed=int(luta["seed"]),
                                         cenario=luta["cenario"], tentativas=1,
                                         camera_largura_min_m=duelo_cfg.get("camera_largura_min_m"),
                                         camera_espera_zoom_in=duelo_cfg.get("camera_espera_zoom_in"))
    res = doc.get("resultado") or {}
    if res.get("vencedor") != luta.get("vencedor") or abs(float(res.get("duracao_jogo") or 0) - float(luta.get("duracao") or 0)) > 0.1:
        raise ErroPalco(f"a luta re-simulada nao bate com o fight.json ({res.get('vencedor')}, "
                        f"{res.get('duracao_jogo')} s x {luta.get('vencedor')}, {luta.get('duracao')} s): "
                        "o banco mudou desde a gravacao?")
    if trechos:
        doc["remapeamento"] = {"relogio": "gravacao", "trechos": trechos}
    pasta = Path(pasta) if pasta else config.SAIDAS / f"ab_{duelo_id}"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = _salvar_timeline(doc, pasta / "timeline.gcpf")
    resumo = render.renderizar(arquivo, pasta / "palco_celular.mp4", hud=hud)
    # O lado esquerdo e o visual de HOJE. Se a 16A ja refez este duelo com o
    # som REAL (outputs/_ouvir/par*_<id>/), e ele: os dois lados soam com os
    # mesmos arquivos do jogo e so o desenho muda. Senao, o publicado.
    rotulo = "HOJE"
    if velho:
        esquerda = Path(velho)
    else:
        refeitos = sorted(config.OUTPUTS.glob(f"_ouvir/par*_{duelo_id}/final_celular.mp4"))
        esquerda = refeitos[-1] if refeitos else pasta_duelo / "final_celular.mp4"
        if refeitos:
            rotulo = "HOJE+SOM REAL"
    saida = ab.lado_a_lado(esquerda, pasta / "palco_celular.mp4", pasta / "ab_celular.mp4",
                           rotulos=(rotulo, rotulo_palco))
    # o quadro: o primeiro acerto forte que aparece no corte (ou 40% do video)
    t_quadro = float(resumo.get("duracao") or 10) * 0.4
    from . import plano
    for ev in doc.get("eventos") or []:
        if ev.get("tipo") == "acerto" and ev.get("tier") in ("heavy", "colossal"):
            f = plano.mapear(int(ev["i"]) / int(doc["hz"]), int(doc["n"]) / int(doc["hz"]), doc.get("remapeamento"))
            if f > 30:
                t_quadro = (f + 2) / 30.0
                break
    png = ab.quadro(saida, pasta / "ab_quadro.png", t_quadro)
    resumo["ab"] = {"mp4": str(saida), "quadro": str(png), "hoje": str(esquerda), "t_quadro": round(t_quadro, 3)}
    return resumo


def duelo_no_palco(*, p1=None, p2=None, seed=None, arena=None, com_ab: bool = False) -> int:
    """`main.py duelo --palco`: um duelo novo desenhado pelo palco, fora do
    catalogo. Com --ab, grava tambem o visual de HOJE (gravador pygame + a
    edicao do duelo, so o perfil celular, sem ledger) e monta o lado a lado."""
    try:
        if not com_ab:
            resumo = render_da_seed(p1=p1, p2=p2, seed=seed, arena=arena)
            print(json.dumps({k: resumo[k] for k in ("saida", "quadros", "duracao", "sons_origem", "tempo")},
                             ensure_ascii=False, indent=1))
            return 0
        from ..generation.random_engine import RandomEngine
        from ..generation.session_generator import load_config
        from ..pipeline.controller import PipelineController
        from ..tournament.duelo import DueloTimelineBuilder
        from ..tournament.runner import FightSession
        from ..video.renderer import VideoRenderer

        p1, p2, seed, cenario = escolher_luta(p1=p1, p2=p2, seed=seed, arena=arena)
        pasta = config.SAIDAS / f"duelo_palco_{seed}"
        pasta.mkdir(parents=True, exist_ok=True)
        controller = PipelineController()
        sessao = FightSession(load_config("scoring.json"), gameplay=_gameplay_duelo())
        print(f"[palco] HOJE: gravando {p1} x {p2} (seed {seed}, {cenario}) no gravador pygame...", flush=True)
        fight = sessao.gerar(p1=p1, p2=p2, seed=seed, cenario=cenario, gravar_em=pasta, perfis=("celular",),
                             origem="duelo", ledger=None, melhor_de=1)
        engine = RandomEngine(fight["seed"])
        plano_edicao = DueloTimelineBuilder(controller.editing_config, controller.captions).build(
            engine.fork("duelo:edicao"), fight)
        final = VideoRenderer(controller.render_config, "celular", False).render(
            plano_edicao, fight, pasta, controller._musica(engine))
        hoje = pasta / "hoje_celular.mp4"
        Path(final).replace(hoje)
        (pasta / "fight.json").write_text(json.dumps(fight, ensure_ascii=False, indent=1), encoding="utf-8")
        luta = fight["luta"]
        duelo_cfg = config.carregar().get("duelo") or {}
        doc, _ = fonte.timeline_da_luta(p1=p1, p2=p2, seed=int(luta["seed"]), cenario=cenario, tentativas=1,
                                        camera_largura_min_m=duelo_cfg.get("camera_largura_min_m"),
                                        camera_espera_zoom_in=duelo_cfg.get("camera_espera_zoom_in"))
        trechos = [[float(a), float(b), 1.0] for a, b in luta["clipes"]["celular"]["trechos"]]
        doc["remapeamento"] = {"relogio": "gravacao", "trechos": trechos}
        arquivo = _salvar_timeline(doc, pasta / "timeline.gcpf")
        resumo = render.renderizar(arquivo, pasta / "palco_celular.mp4")
        saida = ab.lado_a_lado(hoje, pasta / "palco_celular.mp4", pasta / "ab_celular.mp4")
        ab.quadro(saida, pasta / "ab_quadro.png", float(resumo.get("duracao") or 10) * 0.4)
        print(f"[palco] A/B: {saida}")
        return 0
    except ErroPalco as erro:
        print(f"[palco] ERRO: {erro}")
        return 1


def executar(args) -> int:
    try:
        comando = args.palco_command
        if comando == "render":
            estilo = _estilo(args.estilo)
            if args.seed is not None and not args.timeline:
                resumo = render_da_seed(p1=args.p1, p2=args.p2, seed=args.seed, arena=args.arena,
                                        pasta=Path(args.mp4).parent if args.mp4 else None,
                                        sem_corte=args.sem_corte, estilo=estilo, hud=args.hud,
                                        quadros=args.quadros)
            elif args.timeline:
                saida = Path(args.mp4) if args.mp4 else config.SAIDAS / (Path(args.timeline).stem + ".mp4")
                resumo = render.renderizar(args.timeline, saida, estilo=estilo, hud=args.hud,
                                           quadros=args.quadros, manter_avi=args.manter_avi)
            else:
                print("palco render: passe --timeline ou --seed")
                return 2
            print(json.dumps({k: resumo.get(k) for k in ("saida", "quadros", "duracao", "sons_origem", "tempo",
                                                        "nivel", "reservas")}, ensure_ascii=False, indent=1))
            return 0
        if comando == "validar":
            rc, saida = godot.rodar_script("res://ferramentas/validar.gd", [f"--timeline={Path(args.timeline).resolve()}"])
            print("\n".join(linha for linha in saida.splitlines() if "validar" in linha))
            return rc
        if comando == "testes":
            rc, saida = godot.rodar_script("res://ferramentas/testes.gd")
            print("\n".join(linha for linha in saida.splitlines() if "FALHOU" in linha or "testes do palco" in linha))
            return rc
        if comando == "editor":
            import subprocess
            cfg = config.carregar()
            exe = config.godot(cfg)
            # o editor usa o executavel de janela (sem _console), ao lado do do config
            janela = exe.with_name(exe.name.replace("_console", ""))
            godot.garantir_importado(cfg)
            subprocess.Popen([str(janela if janela.is_file() else exe), "--editor", "--path",
                              str(config.projeto(cfg))], env=godot.ambiente(cfg),
                             creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
            print(f"editor aberto: {config.projeto(cfg)}")
            return 0
        if comando == "sintetica":
            destino = Path(args.destino)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps(sintetica.timeline_sintetica(args.duracao), separators=(",", ":")),
                               encoding="utf-8")
            print(destino)
            return 0
        if comando == "pecas-do-rosto":
            from . import rosto_pecas
            for nome, medida in rosto_pecas.gerar(folha=args.folha).items():
                print(f"{nome:18s} {tuple(medida['px'])}")
            return 0
        if comando == "efeitos-cc0":
            from . import efeitos_cc0
            print(f"{efeitos_cc0.gerar(so_cenas=args.so_cenas)} cenas")
            return 0
        if comando == "vitrine":
            resumo = vitrine.gerar(Path(args.mp4) if args.mp4 else None, so=args.so)
            print(json.dumps({k: resumo.get(k) for k in ("saida", "quadros", "duracao", "paginas", "reservas", "tempo")},
                             ensure_ascii=False, indent=1))
            return 0
        if comando == "ab":
            resumo = ab_do_duelo(args.duelo, args.velho, hud=args.hud, rotulo_palco=args.rotulo,
                                 pasta=Path(args.pasta) if args.pasta else None)
            print(json.dumps({"ab": resumo["ab"], "palco": resumo["saida"], "tempo": resumo["tempo"],
                              "sons_origem": resumo["sons_origem"]}, ensure_ascii=False, indent=1))
            return 0
    except ErroPalco as erro:
        print(f"[palco] ERRO: {erro}")
        return 1
    print(f"palco: comando desconhecido {args.palco_command}")
    return 2
