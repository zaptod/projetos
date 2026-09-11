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
  python main.py trilha                # trilha sintetizada em assets/music (gratis)
  python main.py metricas --atualizar  # retencao dos publicados x timeline (YouTube API)
  python main.py fluxo                 # onde cada build esta e o proximo passo
  python main.py publicar              # lista os videos prontos, com texto pronto
  python main.py publicar <id> --exportar   # copia com nome legivel + .txt
  python main.py publicar <id> --youtube    # sobe pela API (privado por padrao)
  python main.py publicar <id> --tiktok     # abre o navegador e sobe (nao publica)

  python main.py pausar               # PARA de pegar trabalho (conta compartilhada)
  python main.py pausar --minutos 60  # volta sozinho depois de 1h
  python main.py pausar --provedor digen --motivo "video em uso"
  python main.py retomar              # volta a trabalhar
  python main.py parar                # encerra o worker DEPOIS do job atual
  python main.py controle             # rodando? pausado? parando?

  python main.py identity login       # 1o login no Digen (janela visivel)
  python main.py identity worker      # baixa os clipes da fila e re-renderiza
  python main.py identity queue       # estado da fila
  python main.py identity auditar     # prova de origem (contas compartilhadas)

Cada geracao rende TRES clipes (personagem, arma, personagem+arma), gerados
pelo worker e montados no video pelo re-render.
"""
from __future__ import annotations

import argparse

from builds.identity.config import PROVEDORES as PROVEDORES_LOGIN
from builds.pipeline.controller import PipelineController


def _publicar(args) -> int:
    """Listar / exportar / enviar. Sem id, lista tudo o que existe pronto."""
    from builds.publicar import catalogo

    videos = catalogo.listar()
    if args.origem:
        videos = [v for v in videos if v.origem == args.origem]

    if not args.video_id:
        if not videos:
            print("nenhum video pronto ainda.")
            return 0
        print(f"{len(videos)} video(s) prontos "
              f"(exporte com: main.py publicar <id> --exportar)\n")
        for video in videos:
            print(f"  {video.id}")
            print(f"      {video.titulo}")
            print(f"      {video.bytes / 1e6:.1f} MB · {video.perfil} · "
                  f"{video.caminho}")
            for pendencia in video.pendencias:
                print(f"      ! {pendencia}")
        print(f"\npasta de exportacao: {catalogo.pasta_export()}")
        return 0

    video = catalogo.por_id(args.video_id)
    if video is None:
        print(f"video nao encontrado: {args.video_id}")
        print("rode `python main.py publicar` para ver os ids.")
        return 1

    if video.pendencias and not args.forcar:
        print(f"{video.id} ainda nao esta completo:")
        for pendencia in video.pendencias:
            print(f"  ! {pendencia}")
        print("resolva (ou repita com --forcar para publicar assim mesmo).")
        return 1

    feito = False
    if args.exportar:
        destino = catalogo.exportar(video)
        print(f"exportado: {destino}")
        print(f"texto:     {destino.with_suffix('.txt')}")
        feito = True
    if args.youtube:
        from builds.publicar import cortes, youtube
        # Passou dos 3 min, o YouTube tira o video da esteira de Shorts. O
        # corte acontece AQUI, na hora de publicar, e nas trocas de cena.
        pedacos = cortes.preparar(video, limite=cortes.limite(), log=print)
        for pedaco in pedacos:
            try:
                url = youtube.publicar_como_configurado(
                    pedaco, visibilidade=args.visibilidade,
                    log=lambda linha: print(linha, flush=True))
            except youtube.CotaEsgotada as exc:
                print(f"YouTube: {exc}")
                return 2
            except Exception as exc:
                print(f"YouTube FALHOU: {exc}")
                return 1
            print(f"YouTube: {url}")
        feito = True
    if args.tiktok:
        from builds.publicar import tiktok
        try:
            print(f"TikTok: {tiktok.publicar(video, postar=args.postar or None)}")
        except tiktok.TikTokFalhou as exc:
            print(f"TikTok FALHOU: {exc}")
            return 1
        feito = True

    if not feito:
        print(video.titulo)
        print()
        print(video.descricao_completa)
        print()
        print(f"arquivo: {video.caminho}")
    return 0


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
    gen.add_argument("--print-pedido", metavar="IMAGEM", default=None,
                     help="print do comentario (png/jpg/webp): entra como tela "
                          "logo depois do gancho. Funciona junto com --rerender "
                          "para colocar a prova num video ja gerado")
    gen.add_argument("--genero", metavar="M_OU_F", default=None,
                     help="fixa o genero do personagem (masculino|feminino) "
                          "em vez de sortear")
    gen.add_argument("--fixar", metavar="ATRIBUTO=VALOR", action="append",
                     default=None,
                     help="escolhe um atributo em vez de sortear (repetivel): "
                          "--fixar classe=Mago --fixar tamanho=1,90. "
                          "Veja --atributos")
    gen.add_argument("--atributos", action="store_true",
                     help="lista o que da para escolher com --fixar e sai")
    gen.add_argument("--no-estreia", action="store_true",
                     help="nao gravar a primeira luta do personagem "
                          "(outputs/<geracao>/estreia/)")

    fig = sub.add_parser("fight",
                         help="grava UMA luta e gera o video dela (2 formatos)")
    fig.add_argument("--p1", default=None,
                     help="lutador 1 (padrao: o ultimo criado na roleta)")
    fig.add_argument("--p2", default=None,
                     help="lutador 2 (padrao: adversario por continuidade/poder)")
    fig.add_argument("--seed", type=int, default=None, help="seed deterministica")
    fig.add_argument("--arena", default=None,
                     help="cenario (padrao: sorteado entre as arenas de video)")
    fig.add_argument("--preview", action="store_true", help="render rapido")
    fig.add_argument("--melhor-de", type=int, default=1, metavar="N",
                     help="serie melhor de N (impar; padrao 1 = luta unica). "
                          "A serie para assim que alguem fecha o placar")
    fig.add_argument("--generation-only", action="store_true",
                     help="so simula (headless) e grava o fight.json, sem video")
    fig.add_argument("--rerender", metavar="FIGHT_ID", default=None,
                     help="re-renderiza uma luta existente (fight_00001 ou "
                          "generation_00037/estreia) reaproveitando o gameplay")
    fig.add_argument("--refazer-edicao", action="store_true",
                     help="com --rerender, remonta a timeline (legendas, "
                          "callouts e reacao novos) sobre o mesmo gameplay")

    due = sub.add_parser("duelo",
                         help="Onda 15B: a luta inteira em 20-35 s, um "
                              "segmento so, sem cena parada")
    due.add_argument("--p1", default=None,
                     help="lutador 1 (padrao: o ultimo criado na roleta)")
    due.add_argument("--p2", default=None,
                     help="lutador 2 (padrao: adversario por continuidade/poder)")
    due.add_argument("--seed", type=int, default=None, help="seed deterministica")
    due.add_argument("--arena", default=None,
                     help="cenario (padrao: sorteado entre as arenas de video)")
    due.add_argument("--preview", action="store_true", help="render rapido")
    due.add_argument("--rerender", metavar="DUELO_ID", default=None,
                     help="re-renderiza um duelo existente (duelo_00001) "
                          "reaproveitando o gameplay ja gravado")
    due.add_argument("--refazer-edicao", action="store_true",
                     help="com --rerender, remonta a timeline sobre o mesmo "
                          "gameplay")

    are = sub.add_parser("arena", help="carreira dos personagens entre videos")
    asub = are.add_subparsers(dest="arena_command", required=True)
    arank = asub.add_parser("ranking", help="ranking por vitorias do ledger")
    arank.add_argument("-n", type=int, default=10, help="quantos mostrar")

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
    # nargs="+": o painel abre um seletor de MULTIPLOS arquivos e mandava
    # todos; com um positional so, o segundo em diante virava erro.
    imp.add_argument("source", nargs="+", help="pasta(s) ou arquivo(s) com os videos")
    from builds.assets.catalog import CATEGORIES
    imp.add_argument("--categoria", required=True, choices=CATEGORIES,
                     help="categoria que esses videos substituem")
    # `--mover` e o nome canonico (o resto da CLI fala portugues); `--move`
    # continua valendo para nao quebrar quem ja tinha script.
    imp.add_argument("--mover", "--move", action="store_true", dest="move",
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
    ilogin.add_argument("--canal", default="builds",
                        help="de qual canal e a conta (builds|historias|geral)")
    iprobe = isub.add_parser(
        "probe", help="despeja o DOM da tela atual (manutencao e descoberta)")
    iprobe.add_argument("--url", default=None,
                        help="despeja QUALQUER pagina, sem conferir seletor "
                             "conhecido (para site que o projeto ainda nao "
                             "conhece)")
    from builds.identity.config import PROVEDORES
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

    ipausar = isub.add_parser(
        "pausar", help="para de pegar trabalho novo (o job atual termina). "
                       "Use quando a conta do site estiver em uso por outra pessoa")
    ipausar.add_argument("--provedor", choices=("tudo", "digen", "picasso"),
                         default="tudo",
                         help="pausar so um site (padrao: tudo)")
    ipausar.add_argument("--minutos", type=float, default=None, metavar="N",
                         help="volta sozinho depois de N minutos")
    ipausar.add_argument("--motivo", default="", help="fica anotado no status")

    iretomar = isub.add_parser("retomar", help="tira a pausa e volta a pegar trabalho")
    iretomar.add_argument("--provedor", choices=("tudo", "digen", "picasso"),
                          default=None, help="retomar so um site (padrao: tudo)")

    iparar = isub.add_parser(
        "parar", help="encerra o worker DEPOIS do job atual (parada limpa, "
                      "sem matar processo no meio)")
    iparar.add_argument("--motivo", default="", help="fica anotado no status")

    isub.add_parser("controle", help="mostra se a pipeline esta rodando, "
                                     "pausada ou parando")

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
    from builds.identity.slots import SLOTS
    irun.add_argument("--slot", choices=SLOTS, default=None,
                      help="so este clipe (padrao: os tres)")
    irun.add_argument("--headless", action="store_true")
    irun.add_argument("--no-rerender", action="store_true")
    irun.add_argument("--preview", action="store_true")

    from builds.identity.slots import JOBS
    iaud = isub.add_parser(
        "auditar",
        help="prova de origem de cada artefato (as contas dos sites sao "
             "compartilhadas; o que 'ficou pronto' rapido demais e suspeito)")
    iaud.add_argument("generation_id", nargs="?", default=None,
                      help="so esta geracao (padrao: todas)")
    iaud.add_argument("--quarentenar-suspeitos", action="store_true",
                      help="tira da build os artefatos SUSPEITOS e reenfileira "
                           "os slots para gerar de novo, com prova")
    iaud.add_argument("--sem-rerender", action="store_true",
                      help="nao refaz o video das geracoes que perderem clipe")
    iqua = isub.add_parser(
        "quarentenar",
        help="tira um artefato da build (imagem/video que nao e nosso) e "
             "reenfileira o slot; nada e apagado (identity/quarentena/)")
    iqua.add_argument("generation_id")
    iqua.add_argument("slot", choices=list(JOBS))
    iqua.add_argument("--motivo", default="quarentena manual")
    iqua.add_argument("--sem-reenfileirar", action="store_true",
                      help="so tira da build, sem mandar gerar de novo")
    iqua.add_argument("--sem-rerender", action="store_true")

    iapr = isub.add_parser(
        "aprovar",
        help="voce abriu a imagem e ela e sua: registra a verificacao humana "
             "e o slot sai da lista de suspeitos")
    iapr.add_argument("generation_id")
    iapr.add_argument("slot", choices=list(JOBS))
    iapr.add_argument("--motivo", default="conferido visualmente")

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

    pub = sub.add_parser(
        "publicar",
        help="lista/exporta/envia os videos prontos (YouTube e TikTok)")
    pub.add_argument("video_id", nargs="?",
                     help="id do catalogo (sem nada: lista tudo)")
    pub.add_argument("--exportar", action="store_true",
                     help="copia o mp4 com nome legivel + .txt com o texto")
    pub.add_argument("--youtube", action="store_true",
                     help="envia pela API oficial (privado por padrao)")
    pub.add_argument("--tiktok", action="store_true",
                     help="abre o navegador e sobe; NAO publica sozinho")
    pub.add_argument("--postar", action="store_true",
                     help="no TikTok, clica em publicar no fim")
    pub.add_argument("--forcar", action="store_true",
                     help="exporta/publica mesmo com pendencia (sem payoff, "
                          "sem luta, mp4 velho)")
    pub.add_argument("--visibilidade", choices=("private", "unlisted", "public"),
                     default=None, help="visibilidade no YouTube")
    pub.add_argument("--origem", choices=("build", "estreia", "torneio"),
                     default=None, help="filtra a listagem")

    flu = sub.add_parser(
        "fluxo",
        help="onde cada build esta na pipeline e o proximo passo de cada uma")
    flu.add_argument("--limite", type=int, default=12, metavar="N",
                     help="quantas builds mais novas mostrar (0 = todas)")
    flu.add_argument("--json", action="store_true",
                     help="despeja o dado estruturado em vez do texto")

    tri = sub.add_parser("trilha",
                         help="gera a trilha sintetizada em assets/music "
                              "(so quando a pasta esta vazia, ou com --regerar)")
    tri.add_argument("--regerar", action="store_true",
                     help="regrava a trilha sintetizada mesmo que ja exista")
    tri.add_argument("--seed", type=int, default=7, help="variacao da trilha")

    met = sub.add_parser("metricas",
                         help="retencao e numeros dos videos publicados no YouTube "
                              "(API gratuita), cruzados com a timeline de cada um")
    met.add_argument("--atualizar", action="store_true",
                     help="consulta a API agora (sem isso, mostra o ultimo dado salvo)")
    met.add_argument("--json", action="store_true", help="despeja o dado bruto")

    # --- controle da pipeline, no TOPO: e o freio de mao, tem que ser a
    # coisa mais facil de achar na CLI (tambem em `identity ...`).
    tpausar = sub.add_parser(
        "pausar", help="para de pegar trabalho novo; o job atual termina "
                       "(use quando a conta do site estiver com outra pessoa)")
    tpausar.add_argument("--provedor", choices=("tudo", "digen", "picasso"),
                         default="tudo", help="pausar so um site (padrao: tudo)")
    tpausar.add_argument("--minutos", type=float, default=None, metavar="N",
                         help="volta sozinho depois de N minutos")
    tpausar.add_argument("--motivo", default="", help="fica anotado no status")

    tretomar = sub.add_parser("retomar", help="tira a pausa e volta a trabalhar")
    tretomar.add_argument("--provedor", choices=("tudo", "digen", "picasso"),
                          default=None, help="retomar so um site (padrao: tudo)")

    tparar = sub.add_parser(
        "parar", help="encerra o worker depois do job atual (parada limpa)")
    tparar.add_argument("--motivo", default="", help="fica anotado no status")

    sub.add_parser("controle", help="a pipeline esta rodando, pausada ou parando?")

    sub.add_parser("list-reactions", help="lista a biblioteca de reacoes")
    rea = sub.add_parser("reactions",
                         help="assistente interativo: inserir/categorizar videos "
                              "(individual e em lote), listar, recategorizar, remover")
    # Sem flag, segue o assistente interativo de sempre. COM flag, faz a acao
    # e sai: e o que o painel precisa, porque subprocesso do painel nao tem
    # stdin — os botoes Recategorizar e Remover chamavam exatamente estas
    # duas bandeiras e o parser nao aceitava nenhuma.
    rea.add_argument("--recategorizar", metavar="CATEGORIA", choices=CATEGORIES,
                     help="muda a categoria dos IDs informados e sai")
    rea.add_argument("--remover", action="store_true",
                     help="tira os IDs informados da biblioteca e sai")
    rea.add_argument("ids", nargs="*", help="IDs da biblioteca (ex.: 0007)")

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
    if args.command == "fight":
        if args.rerender:
            controller.rerender_luta(args.rerender, preview=args.preview,
                                     refazer_edicao=args.refazer_edicao)
            return
        controller.luta(p1=args.p1, p2=args.p2, seed=args.seed, cenario=args.arena,
                        generation_only=args.generation_only, preview=args.preview,
                        melhor_de=args.melhor_de)
        return
    if args.command == "duelo":
        if args.rerender:
            controller.rerender_duelo(args.rerender, preview=args.preview,
                                      refazer_edicao=args.refazer_edicao)
            return
        controller.duelo(p1=args.p1, p2=args.p2, seed=args.seed,
                         cenario=args.arena, preview=args.preview)
        return
    if args.command == "arena":
        controller.arena_ranking(limite=args.n)
        return
    if args.command == "import-reactions":
        for origem in args.source:
            controller.import_reactions(origem, args.categoria, move=args.move)
        return
    if args.command in ("pausar", "retomar", "parar", "controle"):
        raise SystemExit(_controle(args.command, args))
    if args.command == "list-reactions":
        controller.list_reactions()
        return
    if args.command == "trilha":
        controller.gerar_trilha(regerar=args.regerar, seed=args.seed)
        return
    if args.command == "metricas":
        from builds.publicar import metricas
        raise SystemExit(metricas.cli(atualizar=args.atualizar, como_json=args.json))
    if args.command == "reactions":
        if args.recategorizar or args.remover:
            raise SystemExit(_reactions_em_lote(args))
        controller.reactions_cli()
        return
    if args.command == "identity":
        _identity(args, controller)
        return
    if args.command == "cobertura":
        _cobertura(args)
        return
    if args.command == "publicar":
        raise SystemExit(_publicar(args))
    if args.command == "fluxo":
        import json as _json

        from builds.pipeline import fluxo
        dados = fluxo.snapshot(limite=args.limite or None)
        if args.json:
            print(_json.dumps(dados, ensure_ascii=False, indent=2, default=str))
            raise SystemExit(0)
        # Codigo de saida para agendador: 1 quando ha alerta esperando acao.
        raise SystemExit(1 if fluxo.imprimir(dados) else 0)

    from builds.generation import escolhas as mod_escolhas

    if args.atributos:
        print("Atributos que dao para escolher (--fixar atributo=valor):\n")
        print("\n".join(mod_escolhas.descrever()))
        print("\nExemplo: --genero feminino --fixar classe=Mago --fixar tamanho=1,90")
        return
    # Escolha invalida para AQUI, antes de gastar geracao: um atributo
    # ignorado em silencio viraria um sorteio que voce acha que escolheu.
    pares = list(args.fixar or [])
    if args.genero:
        pares.append(f"genero={args.genero}")
    try:
        escolhidos = mod_escolhas.interpretar(pares)
    except ValueError as erro:
        raise SystemExit(f"[escolha] {erro}") from None

    if args.rerender:
        controller.rerender(args.rerender, preview=args.preview,
                            refazer_edicao=args.refazer_edicao,
                            print_pedido=args.print_pedido)
    elif args.generation_only and args.count > 1:
        controller.batch(args.count, seed_start=args.seed,
                         nome_pedido=args.nome_pedido,
                         autor_pedido=args.autor_pedido,
                         escolhas=escolhidos)
    else:
        controller.generate(seed=args.seed, generation_only=args.generation_only,
                            preview=args.preview, insert=not args.no_insert,
                            identity=not args.no_identity,
                            nome_pedido=args.nome_pedido,
                            autor_pedido=args.autor_pedido,
                            estreia=not args.no_estreia,
                            print_pedido=args.print_pedido,
                            escolhas=escolhidos)


def _reactions_em_lote(args) -> int:
    """Recategorizar/remover sem assistente. E o caminho do painel.

    O assistente de `reactions` pergunta no stdin, e subprocesso do painel
    nao tem stdin: os botoes Recategorizar e Remover mandavam
    `--recategorizar`/`--remover`, o parser recusava, e nada acontecia.
    As funcoes ja existiam em `builds/assets/importer.py` — faltava a porta.
    """
    from builds.assets.importer import recategorize_reaction, remove_reaction
    from builds.pipeline.controller import ASSETS

    if not args.ids:
        print("reactions: informe pelo menos um ID (ex.: `reactions --remover 0007`).")
        return 2
    falhas = 0
    for asset_id in args.ids:
        if args.recategorizar:
            entrada = recategorize_reaction(asset_id, args.recategorizar, ASSETS)
            print(f"[reactions] {asset_id} -> {args.recategorizar}" if entrada
                  else f"[reactions] ID nao encontrado: {asset_id}")
        else:
            entrada = remove_reaction(asset_id, ASSETS)
            print(f"[reactions] {asset_id} removido" if entrada
                  else f"[reactions] ID nao encontrado: {asset_id}")
        falhas += 0 if entrada else 1
    return 1 if falhas else 0


def _controle(acao: str, args) -> int:
    """pausar / retomar / parar / controle — o freio de mao da pipeline.

    Mesma funcao para `main.py pausar` e `main.py identity pausar`: um
    comportamento so, dois caminhos de digitacao.
    """
    from builds.identity import controle

    if acao == "pausar":
        estado = controle.pausar(getattr(args, "provedor", None) or controle.TUDO,
                                 getattr(args, "motivo", ""),
                                 getattr(args, "minutos", None))
    elif acao == "retomar":
        estado = controle.retomar(getattr(args, "provedor", None))
    elif acao == "parar":
        estado = controle.pedir_parada(getattr(args, "motivo", ""))
    else:
        estado = controle.estado()
    print(f"[pipeline] {estado['resumo']}")
    if acao == "pausar":
        print("[pipeline] o job em andamento termina; nenhum novo comeca. "
              "Volte com `main.py retomar`.")
    elif acao == "parar":
        print("[pipeline] o worker sai assim que terminar o job atual. "
              "Volte com `main.py retomar`.")
    return 0


def _cobertura(args) -> None:
    """Relatorio de cobertura do banco -> camada de video.

    Import tardio como o resto: o modulo puxa o pacote neural_fights inteiro,
    e quem so quer `--help` nao precisa pagar por isso. O codigo de saida
    existe para agendador/CI: 0 nada pendente, 1 tem item para cadastrar,
    2 alguma fonte nao pode nem ser lida.
    """
    import json as _json

    from builds.nf_bridge import cobertura as cob
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

    Import tardio: `builds.identity` puxa patchright, que so quem usa o Digen
    precisa ter instalado - `generate-video` continua rodando sem ele.
    """
    from builds.identity import queue

    if args.identity_command == "doctor":
        from builds.identity import health
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

    if args.identity_command in ("pausar", "retomar", "parar", "controle"):
        _controle(args.identity_command, args)
        return

    if args.identity_command == "status":
        from builds.identity import status
        raise SystemExit(1 if status.imprimir() else 0)

    if args.identity_command == "history":
        from builds.identity import history
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

    if args.identity_command == "auditar":
        from builds.identity import auditoria
        linhas = auditoria.classificar(args.generation_id)
        suspeitos = auditoria.imprimir(linhas)
        if args.quarentenar_suspeitos:
            for linha in linhas:
                if linha["estado"] == auditoria.SUSPEITO:
                    auditoria.quarentenar(
                        linha["generation_id"], linha["slot"],
                        f"auditoria: {linha['detalhe']}",
                        rerender=not args.sem_rerender)
        raise SystemExit(1 if suspeitos else 0)

    if args.identity_command == "aprovar":
        from builds.identity import auditoria
        raise SystemExit(0 if auditoria.aprovar(
            args.generation_id, args.slot, args.motivo) else 1)

    if args.identity_command == "quarentenar":
        from builds.identity import auditoria
        movidos = auditoria.quarentenar(
            args.generation_id, args.slot, args.motivo,
            reenfileirar=not args.sem_reenfileirar,
            rerender=not args.sem_rerender)
        raise SystemExit(0 if movidos else 1)

    if args.identity_command == "login":
        from builds.identity import config as icfg
        from builds.identity.browser import contexto_persistente, montou, pagina
        from builds.identity.session import ensure_logged_in
        provedor = getattr(args, "provedor", "digen")
        canal = getattr(args, "canal", "builds")
        if provedor == "dreamface":
            # Login MANUAL: a janela abre no site e espera voce entrar. E o
            # mesmo caminho do primeiro login do TikTok — nao ha automacao de
            # credencial aqui, e nao deveria haver: quem digita a senha e
            # voce, e o perfil guarda a sessao daí em diante.
            import time as _t
            from builds.identity import dreamface_selectors as dsel
            perfil = icfg.profile_dir(provedor, canal=canal)
            with contexto_persistente(profile=perfil) as ctx:
                page = pagina(ctx)
                page.goto(dsel.URL_LOGIN, wait_until="domcontentloaded",
                          timeout=90_000)
                # O app e pesado: 5 s davam "pagina em branco" numa pagina
                # que so estava carregando.
                for _ in range(12):
                    _t.sleep(3)
                    if montou(page):
                        break
                print("[identity] a janela e SUA: preencha e-mail, senha e o "
                      "captcha com calma. Ela fica aberta 15 minutos e eu nao "
                      "encosto nela — na tentativa anterior eu fechei o "
                      "navegador no meio da sua digitacao.")
                # A sessao e detectada pelo SUMICO da tela de login, nao pela
                # URL: o modal abre e fecha sem mudar de endereco.
                from builds.identity import selectors as _sel
                limite = _t.time() + 900
                while _t.time() < limite:
                    _t.sleep(5)
                    try:
                        if page.is_closed():
                            print("[identity] janela fechada por voce.")
                            break
                        logado = _sel.encontrar(page, dsel.TELA_LOGIN,
                                                timeout=1.0) is None
                        if logado:
                            print(f"[identity] sessao iniciada ({page.url}).")
                            _t.sleep(4)
                            break
                    except Exception:
                        break
            print(f"[identity] perfil de {provedor} ({canal}) salvo em "
                  f"{perfil}")
            return
        with contexto_persistente(
                profile=icfg.profile_dir(provedor, canal=canal)) as ctx:
            ensure_logged_in(pagina(ctx), icfg.settings())
        print(f"[identity] perfil de {provedor} ({canal}) salvo em "
              f"{icfg.profile_dir(provedor, canal=canal)}")
        return

    if args.identity_command == "probe":
        from builds.identity import probe
        probe.run(url=args.url, provedor=args.provedor, esperar=args.esperar)
        return

    if args.identity_command == "run":
        import json
        from pathlib import Path
        from builds.identity import config as icfg
        from builds.identity.identity_model import gravar
        from builds.identity.prompt import build_prompts
        caminho = Path("outputs") / args.generation_id / "generation.json"
        if not caminho.is_file():
            raise SystemExit(f"{caminho} nao existe.")
        with open(caminho, encoding="utf-8") as fh:
            generation = json.load(fh)
        gravar(generation)
        prompts = build_prompts(generation)
        alvos = [args.slot] if args.slot else list(icfg.jobs_ativos())
        for slot in alvos:
            queue.enqueue(args.generation_id, prompts[slot], slot=slot)
        print(f"[identity] {args.generation_id} enfileirado: "
              + ", ".join(alvos))

    from builds.identity import worker
    alvo = worker.observar if getattr(args, "watch", False) else worker.drenar
    try:
        alvo(headless=args.headless, rerender=not args.no_rerender,
             preview=args.preview)
    except worker.DeployDoDigen:
        # Codigo 2 para agendador: nao e "nada a fazer", e "precisa de conserto".
        raise SystemExit(2)


if __name__ == "__main__":
    main()
