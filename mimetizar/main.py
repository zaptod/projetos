# -*- coding: utf-8 -*-
"""Absorver e mimetizar — um canal do YouTube vira a biblia de como refaze-lo.

O caminho inteiro, do endereco ao preset:

  1. python main.py canal https://www.youtube.com/@alguem   # cataloga (nao baixa)
  2. python main.py baixar canal_00001                      # o acervo em disco
  3. python main.py medir canal_00001                       # os numeros (ffmpeg)
  4. python main.py transcrever canal_00001                 # legenda ou whisper
  5. python main.py analisar canal_00001 --provedor ambos   # ChatGPT + Gemini
  6. python main.py biblia canal_00001                      # o manual do canal
  7. python main.py preset canal_00001                      # config pro historias/

  python main.py status [canal_00001]     onde cada canal esta

Todo comando e retomavel: o que ja tem artefato em disco e pulado. Um canal
grande nao termina numa sentada, e um processo morto no meio nao pode custar
o que ja foi feito.

Codigos de saida, para agendador e para o painel:
  0  deu certo
  1  ficou pendencia (parte do acervo nao veio, alguma ficha faltou)
  2  precisa de conserto humano (falta yt-dlp, sessao caiu, disco cheio)
"""
from __future__ import annotations

import argparse

PENDENCIA, CONSERTO = 1, 2


def _horas(segundos: float) -> str:
    segundos = float(segundos or 0)
    if segundos < 3600:
        return f"{segundos / 60:.0f}min"
    return f"{segundos / 3600:.1f}h"


def cmd_canal(args) -> int:
    from espelho import canal as modulo
    from espelho import ytdlp
    try:
        dados = modulo.catalogar(args.url, log=print)
    except (modulo.NaoColetou, ytdlp.NaoInstalado, ytdlp.Falhou) as exc:
        print(f"[canal] {exc}")
        return CONSERTO
    print()
    print(f"[canal] {dados['canal_id']}: {dados['nome'] or dados['url']}")
    print(f"[canal] {dados['n_videos']} videos, "
          f"{_horas(dados['duracao_total_s'])} de conteudo")
    if dados["inscritos"]:
        print(f"[canal] {dados['inscritos']:,} inscritos".replace(",", "."))
    print(f"[canal] {dados['pasta']}")
    print(f"\nproximo: python main.py baixar {dados['canal_id']}")
    return 0


def cmd_baixar(args) -> int:
    from espelho import baixar as modulo
    from espelho import config, ytdlp
    try:
        resultado = modulo.baixar(
            args.canal_id, limite=args.limite, criterio=args.criterio,
            sim=args.sim, com_sessao=args.com_sessao, log=print)
    except (modulo.NaoBaixou, config.NaoAchou, ytdlp.NaoInstalado) as exc:
        print(f"[baixar] {exc}")
        return CONSERTO
    except KeyboardInterrupt:
        print("\n[baixar] interrompido. O que ja baixou fica em disco — "
              "rode o mesmo comando para continuar de onde parou.")
        return PENDENCIA
    if resultado["faltando"]:
        print(f"\nproximo: python main.py medir {args.canal_id}   "
              "(os que faltaram nao voltam sozinhos)")
        return PENDENCIA
    print(f"\nproximo: python main.py medir {args.canal_id}")
    return 0


def cmd_medir(args) -> int:
    from espelho import config, ffmpeg
    from espelho import medidas as modulo
    try:
        resultado = modulo.medir(args.canal_id, limite=args.limite,
                                 refazer=args.refazer, log=print)
    except (ffmpeg.SemFerramenta, config.NaoAchou) as exc:
        print(f"[medir] {exc}")
        return CONSERTO
    except KeyboardInterrupt:
        print("\n[medir] interrompido. O que ja mediu fica em disco.")
        return PENDENCIA
    print(f"\nproximo: python main.py transcrever {args.canal_id}")
    return PENDENCIA if resultado["falharam"] else 0


def cmd_transcrever(args) -> int:
    from espelho import config
    from espelho import transcrever as modulo
    try:
        resultado = modulo.transcrever(args.canal_id, limite=args.limite,
                                       refazer=args.refazer,
                                       modelo=args.modelo, log=print)
    except (modulo.NaoTranscreveu, config.NaoAchou) as exc:
        print(f"[transcrever] {exc}")
        return CONSERTO
    except KeyboardInterrupt:
        print("\n[transcrever] interrompido. O que ja saiu fica em disco.")
        return PENDENCIA
    print(f"\n[transcrever] {resultado['por_legenda']} por legenda, "
          f"{resultado['por_whisper']} por whisper")
    print(f"proximo: python main.py analisar {args.canal_id} --provedor ambos")
    return PENDENCIA if resultado["sem_texto"] else 0


def cmd_analisar(args) -> int:
    from espelho import analise as modulo
    from espelho import config
    try:
        resultado = modulo.analisar(
            args.canal_id, provedor=args.provedor, limite=args.limite,
            refazer=args.refazer, headless=args.headless,
            so_estes=args.video or None, log=print)
    except (modulo.NaoAnalisou, config.NaoAchou) as exc:
        print(f"[analisar] {exc}")
        return CONSERTO
    except KeyboardInterrupt:
        print("\n[analisar] interrompido. As fichas prontas ficam em disco — "
              "rode o mesmo comando para continuar de onde parou.")
        return PENDENCIA
    print(f"\n[analisar] {resultado['fichas']} ficha(s), "
          f"{resultado['incompletas']} com pendencia, "
          f"{resultado['pendentes']} ainda por fazer")
    if resultado["pendentes"] or resultado["falharam"]:
        return PENDENCIA
    print(f"proximo: python main.py biblia {args.canal_id}")
    return 0


def cmd_absorver(args) -> int:
    from espelho import absorver as modulo
    from espelho import config, ffmpeg
    provedores = (("chatgpt", "gemini") if args.provedor == "ambos"
                  else (args.provedor,))
    try:
        resultado = modulo.absorver(
            args.canal_id, provedores=provedores, limite=args.limite,
            criterio=args.criterio, lote=args.lote, manter=args.manter,
            com_sessao=args.com_sessao, headless=args.headless, log=print)
    except (modulo.NaoAbsorveu, config.NaoAchou,
            ffmpeg.SemFerramenta) as exc:
        print(f"[absorver] {exc}")
        return CONSERTO
    except KeyboardInterrupt:
        print("\n[absorver] interrompido. As fichas prontas ficam em disco — "
              "rode o mesmo comando para continuar de onde parou.")
        return PENDENCIA
    print(f"\nproximo: python main.py biblia {args.canal_id}")
    return PENDENCIA if resultado["falharam"] else 0


def cmd_biblia(args) -> int:
    from espelho import biblia as modulo
    from espelho import config
    try:
        resultado = modulo.escrever(args.canal_id, provedor=args.provedor,
                                    headless=args.headless, log=print)
    except (modulo.NaoEscreveu, config.NaoAchou) as exc:
        print(f"[biblia] {exc}")
        return CONSERTO
    except KeyboardInterrupt:
        print("\n[biblia] interrompido. As respostas cruas ficaram em "
              "conversa/biblia/.")
        return PENDENCIA
    print(f"\nproximo: python main.py preset {args.canal_id}")
    return PENDENCIA if resultado["problemas"] else 0


def cmd_preset(args) -> int:
    from espelho import biblia, config
    from espelho import preset as modulo
    try:
        resultado = modulo.gerar(args.canal_id, provedor=args.provedor,
                                 headless=args.headless, log=print)
    except (modulo.NaoGerou, biblia.NaoEscreveu, config.NaoAchou) as exc:
        print(f"[preset] {exc}")
        return CONSERTO
    except KeyboardInterrupt:
        print("\n[preset] interrompido.")
        return PENDENCIA
    print("\nO preset NAO foi copiado para historias/config/ de proposito: "
          "leia antes de trocar o formato de um canal que ja funciona.")
    print(f"  {resultado['pasta']}")
    return 0


def cmd_llm(args) -> int:
    """Login e diagnostico do ChatGPT/Gemini.

    Delega para o `contos.llm.probe`: o perfil de Chrome e o registro de
    contas sao os MESMOS do `historias/`, entao logar aqui vale la e
    vice-versa. Existe como comando proprio para quem esta absorvendo um
    canal nao precisar saber que a sessao mora em outro projeto.
    """
    from contos.llm import probe
    from contos.llm.cliente import LLMFalhou
    try:
        if args.acao == "login":
            probe.login(args.provedor)
        else:
            probe.run(args.provedor, esperar=args.esperar)
    except LLMFalhou as exc:
        print(f"[llm] {exc}")
        return CONSERTO
    return 0


def cmd_status(args) -> int:
    from espelho import config, status
    try:
        alvos = ([status.do_canal(args.canal_id)] if args.canal_id
                 else status.todos())
    except config.NaoAchou as exc:
        print(f"[status] {exc}")
        return CONSERTO
    if not alvos:
        print("nenhum canal ainda. Comece com: "
              "python main.py canal https://www.youtube.com/@alguem")
        return 0
    print(f"  {'canal':<14}{'videos':>7}{'prontos':>8}{'medidos':>8}"
          f"{'fichas':>7}{'em disco':>10}  proximo passo")
    print("  " + "-" * 104)
    for dado in alvos:
        disco = dado["em_disco"]
        ocupado = (f"{disco['videos']}/{disco['mb']:.0f}MB"
                   if disco["videos"] else "-")
        print(f"  {dado['canal_id']:<14}{dado['n_videos']:>7}"
              f"{dado['completos']:>8}{dado['medidos']:>8}"
              f"{dado['fichas_total']:>7}{ocupado:>10}  "
              f"{dado['proximo_passo']}")
        if args.canal_id:
            print(f"    {dado['nome']}  ·  {dado['url']}")
            fichas = ", ".join(f"{p}: {n}" for p, n in dado["fichas"].items())
            print(f"    fichas por provedor — {fichas}")
            print(f"    transcritos: {dado['transcritos']}   "
                  f"biblia: {'sim' if dado['biblia'] else 'nao'}   "
                  f"preset: {'sim' if dado['preset'] else 'nao'}")
            print(f"    video em disco agora: {disco['videos']} arquivo(s), "
                  f"{disco['mb']:.0f} MB (o derivado nao conta)")
            print(f"    {dado['pasta']}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="mimetizar",
        description="estuda um canal do YouTube e escreve a biblia dele")
    sub = parser.add_subparsers(dest="comando", required=True)

    c = sub.add_parser("canal", help="cataloga o acervo de um canal (nao baixa)")
    c.add_argument("url", help="https://www.youtube.com/@nome (ou so @nome)")

    b = sub.add_parser("baixar", help="baixa o acervo (retomavel)")
    b.add_argument("canal_id")
    b.add_argument("--limite", type=int, default=0,
                   help="baixa no maximo N videos nesta passada")
    b.add_argument("--criterio", default="canal",
                   choices=("canal", "views", "antigos"),
                   help="quais N, quando ha --limite (padrao: ordem do canal)")
    b.add_argument("--sim", action="store_true",
                   help="baixa mesmo passando do teto de espaco")
    b.add_argument("--com-sessao", action="store_true",
                   help="usa os cookies do Chrome (video restrito por idade)")

    m = sub.add_parser("medir", help="os numeros do video (ffmpeg, sem IA)")
    m.add_argument("canal_id")
    m.add_argument("--limite", type=int, default=0,
                   help="mede no maximo N videos nesta passada")
    m.add_argument("--refazer", action="store_true",
                   help="mede de novo o que ja tem medida")

    t = sub.add_parser("transcrever",
                       help="a fala em texto (legenda do YouTube, ou whisper)")
    t.add_argument("canal_id")
    t.add_argument("--limite", type=int, default=0,
                   help="transcreve no maximo N videos nesta passada")
    t.add_argument("--refazer", action="store_true",
                   help="transcreve de novo o que ja tem texto")
    t.add_argument("--modelo", default="small",
                   help="modelo do whisper, quando ele for usado")

    a = sub.add_parser("analisar",
                       help="ChatGPT/Gemini leem um dossie por video")
    a.add_argument("canal_id")
    a.add_argument("--provedor", default="ambos",
                   choices=("chatgpt", "gemini", "ambos"))
    a.add_argument("--limite", type=int, default=0,
                   help="analisa no maximo N videos por provedor")
    a.add_argument("--refazer", action="store_true",
                   help="analisa de novo o que ja tem ficha")
    a.add_argument("--video", nargs="+", default=None, metavar="ID",
                   help="so estes videos (e como o `absorver` chama)")
    a.add_argument("--headless", action="store_true")

    ab = sub.add_parser(
        "absorver",
        help="baixa, analisa nos dois AO MESMO TEMPO, apaga, e vai ao proximo")
    ab.add_argument("canal_id")
    ab.add_argument("--limite", type=int, default=0,
                    help="quantos videos do canal entrar no total")
    ab.add_argument("--criterio", default="views",
                    choices=("views", "canal", "antigos"),
                    help="quais videos, quando ha --limite (padrao: os mais "
                         "vistos, que dizem mais sobre o formato que deu certo)")
    ab.add_argument("--lote", type=int, default=4,
                    help="quantos videos ficam em disco por vez (padrao 4; "
                         "use 1 para estritamente um de cada vez)")
    ab.add_argument("--provedor", default="ambos",
                    choices=("chatgpt", "gemini", "ambos"))
    ab.add_argument("--manter", action="store_true",
                    help="NAO apaga os videos depois de analisar")
    ab.add_argument("--com-sessao", action="store_true",
                    help="usa os cookies do Chrome (video restrito por idade)")
    ab.add_argument("--headless", action="store_true")

    bi = sub.add_parser("biblia", help="as fichas viram o manual do canal")
    bi.add_argument("canal_id")
    bi.add_argument("--provedor", default="chatgpt",
                    choices=("chatgpt", "gemini"),
                    help="quem escreve a sintese (le as fichas dos dois)")
    bi.add_argument("--headless", action="store_true")

    pr = sub.add_parser("preset",
                        help="a biblia vira config do historias/ + diagnostico")
    pr.add_argument("canal_id")
    pr.add_argument("--provedor", default="chatgpt",
                    choices=("chatgpt", "gemini"))
    pr.add_argument("--headless", action="store_true")

    llm = sub.add_parser("llm", help="login e diagnostico do ChatGPT/Gemini")
    llm.add_argument("acao", choices=("login", "probe"))
    llm.add_argument("--provedor", default="chatgpt",
                     choices=("chatgpt", "gemini"))
    llm.add_argument("--esperar", type=float, default=0.0,
                     help="no probe, segundos com a janela aberta antes de olhar")

    s = sub.add_parser("status", help="onde cada canal esta")
    s.add_argument("canal_id", nargs="?", default=None)

    args = parser.parse_args(argv)
    acoes = {"canal": cmd_canal, "baixar": cmd_baixar, "medir": cmd_medir,
             "transcrever": cmd_transcrever, "analisar": cmd_analisar,
             "absorver": cmd_absorver, "biblia": cmd_biblia,
             "preset": cmd_preset, "llm": cmd_llm, "status": cmd_status}
    return acoes[args.comando](args)


if __name__ == "__main__":
    raise SystemExit(main())
