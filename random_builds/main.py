"""Gerador procedural de personagens + armas + edicao automatica de video.

Uso:
  python main.py generate-video                        # pipeline completa
  python main.py generate-video --seed 847293847       # reproducivel
  python main.py generate-video --preview              # render rapido/pequeno
  python main.py generate-video --generation-only      # so dados (sem video)
  python main.py generate-video --generation-only --count 1000   # balanceamento
  python main.py generate-video --rerender generation_00001      # re-render puro
  python main.py generate-video --nome-pedido "Kaelen" --autor-pedido "@zeca"

  python main.py cobertura             # o que o banco tem e o video nao descreve

  python main.py identity login       # 1o login no Digen (janela visivel)
  python main.py identity worker      # baixa os clipes da fila e re-renderiza
  python main.py identity queue       # estado da fila

Cada geracao rende TRES clipes (personagem, arma, personagem+arma), gerados
pelo worker e montados no video pelo re-render.
"""
from __future__ import annotations

import argparse

from src.identity.config import PROVEDORES as PROVEDORES_LOGIN
from src.pipeline.controller import PipelineController


def main() -> None:
    parser = argparse.ArgumentParser(description="Gerador procedural de builds + video")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate-video", help="gera build (e video) a partir de uma seed")
    gen.add_argument("--seed", type=int, default=None, help="seed deterministica")
    gen.add_argument("--preview", action="store_true", help="render rapido em baixa resolucao")
    gen.add_argument("--generation-only", action="store_true", help="gera apenas os dados")
    gen.add_argument("--count", type=int, default=1, help="quantidade de builds (com --generation-only)")
    gen.add_argument("--rerender", metavar="GENERATION_ID", default=None,
                     help="re-renderiza uma geracao existente sem rolar nada de novo")
    gen.add_argument("--no-insert", action="store_true",
                     help="nao inserir o resultado no banco do neural_fights")
    gen.add_argument("--refazer-edicao", action="store_true",
                     help="com --rerender, remonta a timeline (inclui o clipe "
                          "de identidade que tiver chegado depois)")
    gen.add_argument("--no-identity", action="store_true",
                     help="nao enfileirar o clipe de identidade visual (Digen)")
    gen.add_argument("--nome-pedido", metavar="NOME", default=None,
                     help="nome escolhido num comentario; vence o nome gerado "
                          "e o video credita quem pediu")
    gen.add_argument("--autor-pedido", metavar="ARROBA", default=None,
                     help="quem pediu o nome; so credito de tela, nao entra "
                          "em sorteio nenhum")

    tor = sub.add_parser("tournament",
                         help="roda um torneio e gera o video (2 formatos)")
    tor.add_argument("--seed", type=int, default=None, help="seed deterministica")
    tor.add_argument("--fonte", choices=["gerados", "banco", "misto"],
                     default="misto",
                     help="quem participa: personagens criados nas roletas, "
                          "o banco inteiro, ou gerados + banco (padrao)")
    tor.add_argument("--participantes", type=int, default=8,
                     help="quantidade (ajustada para potencia de 2)")
    tor.add_argument("--preview", action="store_true", help="render rapido")
    tor.add_argument("--generation-only", action="store_true",
                     help="so roda as lutas e grava os JSONs, sem video")
    tor.add_argument("--rerender", metavar="TOURNAMENT_ID", default=None,
                     help="re-renderiza um torneio existente reaproveitando as "
                          "lutas ja gravadas")
    tor.add_argument("--refazer-edicao", action="store_true",
                     help="com --rerender, remonta a timeline (legendas e "
                          "reacoes novas) sobre as mesmas lutas")

    imp = sub.add_parser("import-reactions",
                         help="importa videos de reacao com ID sequencial")
    imp.add_argument("source", help="pasta (ou arquivo) com os videos")
    from src.assets.catalog import CATEGORIES
    imp.add_argument("--categoria", required=True, choices=CATEGORIES,
                     help="categoria que esses videos substituem")
    imp.add_argument("--move", action="store_true",
                     help="mover os arquivos em vez de copiar")

    ident = sub.add_parser(
        "identity",
        help="identidade visual do personagem via Digen (browser automatizado)")
    isub = ident.add_subparsers(dest="identity_command", required=True)

    ilogin = isub.add_parser(
        "login", help="abre o site e garante a sessao (faca o 1o login aqui)")
    ilogin.add_argument("--provedor", choices=sorted(PROVEDORES_LOGIN),
                        default="digen",
                        help="qual site logar (perfis sao separados)")
    iprobe = isub.add_parser(
        "probe", help="despeja o DOM da tela atual (manutencao e descoberta)")
    iprobe.add_argument("--url", default=None,
                        help="despeja QUALQUER pagina, sem conferir seletor "
                             "conhecido (para site que o projeto ainda nao "
                             "conhece)")
    from src.identity.config import PROVEDORES
    iprobe.add_argument("--provedor", choices=sorted(PROVEDORES), default=None,
                        help="qual perfil de browser usar (padrao: digen)")
    iprobe.add_argument("--esperar", type=float, default=0.0, metavar="SEGUNDOS",
                        help="deixa a janela aberta este tempo antes de "
                             "despejar, para voce logar e chegar na tela certa")

    iwork = isub.add_parser("worker", help="processa a fila de identidade")
    modo = iwork.add_mutually_exclusive_group()
    modo.add_argument("--once", action="store_true",
                      help="drena a fila e sai (padrao)")
    modo.add_argument("--watch", action="store_true",
                      help="fica em pe drenando a fila (Ctrl+C para sair)")
    iwork.add_argument("--headless", action="store_true",
                       help="sem janela; menos furtivo e impede resolver desafio")
    iwork.add_argument("--no-rerender", action="store_true",
                       help="so baixa o clipe, sem refazer o video da roleta")
    iwork.add_argument("--preview", action="store_true",
                       help="re-render rapido em baixa resolucao")

    idoc = isub.add_parser(
        "doctor", help="diagnostico: esta tudo certo com o gerador de video?")
    idoc.add_argument("--online", action="store_true",
                      help="abre o Digen e confere sessao, creditos e se os "
                           "seletores ainda casam com a pagina real")
    idoc.add_argument("--headless", action="store_true",
                      help="com --online, sem janela")

    isub.add_parser("status",
                    help="visao operacional: fila, clipes, videos finais e "
                         "inconsistencias")

    ihist = isub.add_parser("history", help="historico de geracoes")
    ihist.add_argument("-n", type=int, default=20,
                       help="quantos eventos mostrar (padrao 20)")

    iqueue = isub.add_parser("queue", help="estado da fila de identidade")
    iqueue.add_argument("--limpar", action="store_true",
                        help="remove os jobs ja concluidos")

    irun = isub.add_parser("run",
                           help="enfileira os clipes de UMA geracao e processa agora")
    irun.add_argument("generation_id", help="ex.: generation_00011")
    from src.identity.slots import SLOTS
    irun.add_argument("--slot", choices=SLOTS, default=None,
                      help="so este clipe (padrao: os tres)")
    irun.add_argument("--headless", action="store_true")
    irun.add_argument("--no-rerender", action="store_true")
    irun.add_argument("--preview", action="store_true")

    cob = sub.add_parser(
        "cobertura",
        help="o que o banco do jogo ja tem e a camada de video ainda nao "
             "sabe descrever (prompt, legenda, reacao)")
    cob.add_argument("--apenas-faltando", action="store_true",
                     help="esconde os grupos que ja estao completos")
    cob.add_argument("--limite", type=int, default=None, metavar="N",
                     help="mostra so os N primeiros itens de cada grupo")
    cob.add_argument("--json", action="store_true",
                     help="despeja o dado estruturado em vez do texto")

    sub.add_parser("list-reactions", help="lista a biblioteca de reacoes")
    sub.add_parser("reactions",
                   help="assistente interativo: inserir/categorizar videos "
                        "(individual e em lote), listar, recategorizar, remover")

    args = parser.parse_args()
    controller = PipelineController()

    if args.command == "tournament":
        if args.rerender:
            controller.rerender_torneio(args.rerender, preview=args.preview,
                                        refazer_edicao=args.refazer_edicao)
            return
        controller.torneio(seed=args.seed, fonte=args.fonte,
                           quantidade=args.participantes,
                           generation_only=args.generation_only,
                           preview=args.preview)
        return
    if args.command == "import-reactions":
        controller.import_reactions(args.source, args.categoria, move=args.move)
        return
    if args.command == "list-reactions":
        controller.list_reactions()
        return
    if args.command == "reactions":
        controller.reactions_cli()
        return
    if args.command == "identity":
        _identity(args, controller)
        return
    if args.command == "cobertura":
        _cobertura(args)
        return

    if args.rerender:
        controller.rerender(args.rerender, preview=args.preview,
                            refazer_edicao=args.refazer_edicao)
    elif args.generation_only and args.count > 1:
        controller.batch(args.count, seed_start=args.seed,
                         nome_pedido=args.nome_pedido,
                         autor_pedido=args.autor_pedido)
    else:
        controller.generate(seed=args.seed, generation_only=args.generation_only,
                            preview=args.preview, insert=not args.no_insert,
                            identity=not args.no_identity,
                            nome_pedido=args.nome_pedido,
                            autor_pedido=args.autor_pedido)


def _cobertura(args) -> None:
    """Relatorio de cobertura do banco -> camada de video.

    Import tardio como o resto: o modulo puxa o pacote neural_fights inteiro,
    e quem so quer `--help` nao precisa pagar por isso. O codigo de saida
    existe para agendador/CI: 0 nada pendente, 1 tem item para cadastrar,
    2 alguma fonte nao pode nem ser lida.
    """
    import json as _json

    from src.nf_bridge import cobertura as cob
    dados = cob.cobertura()
    if args.json:
        print(_json.dumps(dados, ensure_ascii=False, indent=2))
    else:
        print(cob.relatorio(dados, limite=args.limite,
                            apenas_faltando=args.apenas_faltando), end="")
    if any(g["erro"] for g in dados["grupos"]):
        raise SystemExit(2)
    raise SystemExit(0 if dados["ok"] else 1)


def _identity(args, controller) -> None:
    """Subcomandos de identidade.

    Import tardio: `src.identity` puxa patchright, que so quem usa o Digen
    precisa ter instalado - `generate-video` continua rodando sem ele.
    """
    from src.identity import queue

    if args.identity_command == "doctor":
        from src.identity import health
        locais = health.checar_local()
        health.imprimir(locais, "DIAGNOSTICO LOCAL")
        estados = [health.pior_estado(locais)]
        if args.online:
            online = health.checar_online(headless=args.headless)
            health.imprimir(online, "DIAGNOSTICO ONLINE (Digen)")
            estados.append(health.pior_estado(online))
        else:
            print()
            print("  (use --online para conferir sessao, creditos e seletores)")
        pior = health.ERRO if health.ERRO in estados else (
            health.AVISO if health.AVISO in estados else health.OK)
        print()
        print(f"RESULTADO: {pior.upper()}")
        # Codigo de saida serve para agendador/CI: 0 ok, 1 aviso, 2 erro.
        raise SystemExit({health.OK: 0, health.AVISO: 1, health.ERRO: 2}[pior])

    if args.identity_command == "status":
        from src.identity import status
        raise SystemExit(1 if status.imprimir() else 0)

    if args.identity_command == "history":
        from src.identity import history
        eventos = history.ler(limite=args.n)
        if not eventos:
            print("Sem historico ainda.")
            return
        for evento in eventos:
            extra = " ".join(f"{k}={v}" for k, v in evento.items()
                             if k not in ("ts", "generation_id", "evento")
                             and v is not None)
            print(f"  {evento['ts']}  {evento['generation_id']:<20} "
                  f"{evento['evento']:<10} {extra[:90]}")
        resumo = history.resumo(history.ler())
        if resumo["espera_mediana_s"]:
            print()
            print(f"  espera mediana do Digen: {resumo['espera_mediana_s']:.0f}s "
                  f"| taxa de sucesso: {(resumo['taxa_sucesso'] or 0) * 100:.0f}%")
        return

    if args.identity_command == "queue":
        if args.limpar:
            print(f"[identity] {queue.limpar_concluidos()} job(s) concluido(s) removido(s)")
        jobs = queue.listar()
        if not jobs:
            print("Fila vazia.")
            return
        for job in jobs:
            erro = f"  {job['error'][:52]}" if job.get("error") else ""
            print(f"  {job['generation_id']:<18} {job['slot']:<17} "
                  f"{job['status']:<8} tentativas={job.get('attempts', 0)}{erro}")
        print(f"Total: {len(jobs)} job(s)")
        return

    if args.identity_command == "login":
        from src.identity import config as icfg
        from src.identity.browser import contexto_persistente, pagina
        from src.identity.session import ensure_logged_in
        provedor = getattr(args, "provedor", "digen")
        with contexto_persistente(profile=icfg.profile_dir(provedor)) as ctx:
            ensure_logged_in(pagina(ctx), icfg.settings())
        print(f"[identity] perfil de {provedor} salvo em "
              f"{icfg.profile_dir(provedor)}")
        return

    if args.identity_command == "probe":
        from src.identity import probe
        probe.run(url=args.url, provedor=args.provedor, esperar=args.esperar)
        return

    if args.identity_command == "run":
        import json
        from pathlib import Path
        from src.identity import slots
        from src.identity.identity_model import gravar
        from src.identity.prompt import build_prompts
        caminho = Path("outputs") / args.generation_id / "generation.json"
        if not caminho.is_file():
            raise SystemExit(f"{caminho} nao existe.")
        with open(caminho, encoding="utf-8") as fh:
            generation = json.load(fh)
        gravar(generation)
        prompts = build_prompts(generation)
        alvos = [args.slot] if args.slot else list(slots.SLOTS)
        for slot in alvos:
            queue.enqueue(args.generation_id, prompts[slot], slot=slot)
        print(f"[identity] {args.generation_id} enfileirado: "
              + ", ".join(alvos))

    from src.identity import worker
    alvo = worker.observar if getattr(args, "watch", False) else worker.drenar
    try:
        alvo(headless=args.headless, rerender=not args.no_rerender,
             preview=args.preview)
    except worker.DeployDoDigen:
        # Codigo 2 para agendador: nao e "nada a fazer", e "precisa de conserto".
        raise SystemExit(2)


if __name__ == "__main__":
    main()
