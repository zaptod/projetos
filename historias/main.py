# -*- coding: utf-8 -*-
"""Canal de historias por IA — roteiro, imagens, narracao e video.

O fluxo, do zero ao mp4:

  AUTOMATICO (o browser faz tudo):
  0. python main.py llm login --provedor chatgpt   # uma vez, para salvar a sessao
  1. python main.py gerar --partes 8               # abre o LLM e escreve a serie
  2. python main.py tudo historia_00002            # imagens + um video por parte

  MANUAL (se preferir escolher o LLM na mao):
  1. python main.py prompt --copiar          # o prompt-mestre vai pro clipboard
  2. python main.py roteiro --colar          # a resposta vira roteiro.json
  3. python main.py tudo historia_00001      # imagens + video

Outros:
  python main.py modelos                     # estruturas de roteiro disponiveis
  python main.py status [historia_00001]     # onde cada historia esta
  python main.py publicar [id] [--exportar]  # mp4 com nome legivel + texto
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _clipboard_ler() -> str:
    """O que esta no clipboard do Windows (a resposta que voce copiou)."""
    try:
        saida = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            capture_output=True, text=True, timeout=30, encoding="utf-8",
            creationflags=NO_WINDOW)
        return saida.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _clipboard_escrever(texto: str) -> bool:
    try:
        proc = subprocess.run(["clip"], input=texto.encode("utf-16-le"),
                              timeout=30, creationflags=NO_WINDOW)
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _texto_da_entrada(args) -> str:
    if args.colar:
        return _clipboard_ler()
    if args.arquivo and args.arquivo != "-":
        return Path(args.arquivo).read_text(encoding="utf-8-sig")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def cmd_prompt(args, pipeline) -> int:
    dados = pipeline.prompt(args.modelo, tema=args.tema, cenas=args.cenas,
                            arquivo=args.arquivo)
    print(dados["prompt"])
    print()
    print(f"[prompt] modelo '{dados['modelo']}' · {dados['cenas_alvo']} cenas alvo")
    print(f"[prompt] salvo em {dados['arquivo']}")
    if args.copiar and _clipboard_escrever(dados["prompt"]):
        print("[prompt] copiado para o clipboard - cole no LLM.")
    print("[prompt] com a resposta copiada: python main.py roteiro --colar")
    return 0


def cmd_roteiro(args, pipeline) -> int:
    texto = _texto_da_entrada(args)
    if not texto.strip():
        print("nada para ler. Use --colar (clipboard), um arquivo, ou pipe.")
        return 1
    resultado = pipeline.importar(texto, modelo=args.modelo or "",
                                  tema=args.tema or "")
    for problema in resultado.get("problemas") or []:
        print(f"  ! {problema}")
    if not resultado["ok"]:
        print(f"roteiro RECUSADO ({resultado['cenas']} cena(s) lidas):")
        for erro in resultado["erros"]:
            print(f"  x {erro}")
        print("\nCorrija a resposta do LLM (ou peca de novo) e rode outra vez.")
        return 1
    print(f"[roteiro] {resultado['historia_id']}: {resultado['cenas']} cenas")
    print(f"[roteiro] {resultado['titulo']}")
    print(f"[roteiro] {resultado['caminho']}")
    print(f"\nproximo: python main.py tudo {resultado['historia_id']}")
    return 0


def cmd_gerar(args, pipeline) -> int:
    from contos.roteiro.gerar import GeracaoFalhou
    from contos.llm.cliente import LLMFalhou
    try:
        resultado = pipeline.gerar(provedor=args.provedor, partes=args.partes,
                                   cenas_por_parte=args.cenas, tema=args.tema,
                                   headless=args.headless)
    except (GeracaoFalhou, LLMFalhou) as exc:
        print(f"[gerar] {exc}")
        return 1
    print(f"\n[gerar] {resultado['historia_id']}: {resultado['partes']} parte(s), "
          f"{resultado['cenas']} cenas")
    print(f"[gerar] {resultado['titulo']}")
    print(f"\nproximo: python main.py tudo {resultado['historia_id']}")
    return 0


def cmd_llm(args, pipeline) -> int:
    from contos.llm import probe
    if args.acao == "login":
        probe.login(args.provedor)
        return 0
    probe.run(args.provedor, esperar=args.esperar)
    return 0


def cmd_imagens(args, pipeline) -> int:
    from contos.imagens.worker import NaoRodou
    try:
        resultado = pipeline.imagens(args.historia_id, limite=args.limite,
                                     headless=args.headless, parte=args.parte)
    except NaoRodou as exc:
        print(f"[imagens] {exc}")
        return 1
    for erro in resultado["erros"]:
        print(f"  ! {erro}")
    return 0 if not resultado["faltam"] else 1


def cmd_video(args, pipeline) -> int:
    pipeline.render(args.historia_id, preview=args.preview, parte=args.parte)
    return 0


def cmd_tudo(args, pipeline) -> int:
    resultado = pipeline.tudo(args.historia_id, preview=args.preview,
                              headless=args.headless)
    for erro in resultado["imagens"]["erros"]:
        print(f"  ! {erro}")
    return 0


def cmd_modelos(args, pipeline) -> int:
    from contos.roteiro import modelo
    for dados in modelo.listar(pipeline.roteiro_config):
        cenas = f"{dados['cenas']} cenas" if dados["cenas"] else "estrutura propria"
        print(f"  {dados['nome']:<14} {dados['rotulo']:<38} {cenas}")
    print("\nModelo proprio: um .txt em modelos/ (uma linha por bloco) e depois")
    print("  python main.py prompt --arquivo modelos/meu.txt")
    return 0


def cmd_conferir(args, pipeline) -> int:
    """Procura defeito no que ja existe. Sai 1 se achou algo que impede publicar."""
    from contos.pipeline import conferir as C
    from contos.roteiro import coerencia, roteiro as R

    achou = False
    ruins = C.cache_de_voz()
    if ruins:
        achou = True
        print(f"CACHE DE VOZ: {len(ruins)} entrada(s) que nao servem")
        for item in ruins:
            print(f"  {item['arquivo'].name}  {item['duracao']:.1f}s  "
                  f"{item['motivo']}")
        if args.consertar:
            print(f"  apagadas {C.limpar_cache(ruins)}; a proxima renderizacao "
                  "sintetiza de novo.")
        else:
            print("  rode com --consertar para apaga-las.")
    else:
        print("CACHE DE VOZ: ok")

    if args.historia_id:
        alvos = [args.historia_id]
    else:
        alvos = [r["historia_id"] for r in R.listar()]
    for historia_id in alvos:
        try:
            laudo = C.conferir_historia(historia_id)
        except (OSError, ValueError, KeyError) as exc:
            print(f"{historia_id}: nao deu para conferir ({exc})")
            achou = True
            continue
        marca = "  [TESTE]" if laudo["teste"] else ""
        print(f"{chr(10)}{historia_id}{marca}  {laudo['titulo'][:70]}")
        print(f"  {'parte':>5} {'palavras':>9} {'video':>9} {'pal/s':>7}")
        for linha in laudo["partes"]:
            taxa = ("-" if linha["palavras_por_s"] is None
                    else f"{linha['palavras_por_s']:.2f}")
            print(f"  {linha['parte']:>5} {linha['palavras']:>9} "
                  f"{linha['duracao']:>8.1f}s {taxa:>7}")
            for erro in linha["erros"]:
                achou = True
                print(f"        ERRO  {erro}")
            for aviso in linha["avisos"]:
                print(f"        aviso {aviso}")
        # Na varredura geral a pergunta e "tem defeito?"; as historias antigas
        # nao tem ficha de FATOS e repetir isso em todas so faz barulho. Com um
        # id (ou --numeros) a pergunta passa a ser sobre esta historia, e ai
        # vale dizer.
        if args.historia_id or args.numeros:
            for aviso in laudo["numeros"]:
                print(f"    numeros: {aviso}")
        if args.numeros:
            citadas = coerencia.citacoes(R.carregar(historia_id))
            for tipo in ("dinheiro", "ano"):
                for valor, onde in sorted(citadas[tipo]):
                    print(f"    {tipo:>8} {valor:>8}  {onde}")
    return 1 if achou else 0


def cmd_status(args, pipeline) -> int:
    alvos = [pipeline.status(args.historia_id)] if args.historia_id \
        else pipeline.listar()
    if not alvos:
        print("nenhuma historia ainda. Comece com: python main.py prompt --copiar")
        return 0
    print(f"  {'historia':<16}{'partes':>7}{'cenas':>6}{'imagens':>10}"
          f"{'videos':>8}{'dur':>7}  proximo passo")
    print("  " + "-" * 104)
    for status in alvos:
        imagens = f"{status['imagens']['prontas']}/{status['imagens']['total']}"
        videos = f"{status['videos_prontos']}/{status['n_partes']}"
        dur = f"{status['duracao']:.0f}s" if status["duracao"] else "-"
        print(f"  {status['historia_id']:<16}{status['n_partes']:>7}"
              f"{status['cenas']:>6}{imagens:>10}{videos:>8}{dur:>7}  "
              f"{status['proximo_passo']}")
        if args.historia_id:
            print(f"    {status['titulo']}")
            for parte in status["partes"]:
                pronto = "video ok" if all(parte["videos"].values()) else "sem video"
                print(f"      parte {parte['parte']}: {parte['cenas']} cenas, "
                      f"{parte['imagens']['prontas']}/{parte['imagens']['total']} "
                      f"imagens, {pronto}  -  {parte['titulo'][:52]}")
            print(f"    {status['pasta']}")
    return 0


def cmd_publicar(args, pipeline) -> int:
    from contos.publicar import catalogo
    if args.serie or args.vistoriar:
        return _publicar_serie(args)
    videos = catalogo.listar()
    if not args.historia_id:
        if not videos:
            print("nenhum video pronto ainda.")
            return 0
        for video in videos:
            print(f"  {video.id}")
            print(f"      {video.titulo}")
            print(f"      {video.bytes / 1e6:.1f} MB · {video.caminho}")
        print(f"\npasta de exportacao: {catalogo.pasta_export()}")
        return 0
    alvo = next((v for v in videos if v.id.startswith(args.historia_id)), None)
    if alvo is None:
        print(f"video nao encontrado para {args.historia_id}.")
        return 1
    if args.exportar:
        destino = catalogo.exportar(alvo)
        print(f"exportado: {destino}")
        print(f"texto:     {destino.with_suffix('.txt')}")
        return 0
    if args.youtube or args.tiktok:
        # `--tiktok` era declarado e IGNORADO fora do modo --serie: o comando
        # imprimia a descricao e saia com 0, como se tivesse publicado.
        codigo = 0
        if args.youtube:
            try:
                print("YouTube:",
                      catalogo.publicar_youtube(alvo, args.visibilidade))
            except Exception as exc:
                print(f"YouTube FALHOU: {exc}")
                codigo = 1
        if args.tiktok:
            try:
                print("TikTok:", catalogo.publicar_tiktok(alvo, postar=True))
            except Exception as exc:
                print(f"TikTok FALHOU: {exc}")
                codigo = 1
        return codigo
    print(alvo.titulo)
    print()
    print(alvo.descricao_completa)
    print()
    print(f"arquivo: {alvo.caminho}")
    return 0


def _publicar_serie(args) -> int:
    """A serie inteira: vistoria, sobe na ordem e agenda a sequencia."""
    from datetime import datetime
    from contos.publicar.serie import NaoPublicou, publicar as publicar_serie
    if not args.historia_id:
        print("diga qual historia: main.py publicar historia_00002 --serie")
        return 1
    comecar = None
    if args.comecar:
        try:
            comecar = datetime.fromisoformat(args.comecar)
        except ValueError:
            print(f"--comecar invalido: {args.comecar!r} "
                  "(use 2026-09-01T18:00)")
            return 1
    plataformas = ["youtube"] + (["tiktok"] if args.tiktok else [])
    try:
        resultado = publicar_serie(
            args.historia_id, plataformas=tuple(plataformas),
            agendar=not args.sem_agendar, intervalo_h=args.intervalo,
            comecar_em=comecar, visibilidade=args.visibilidade,
            forcar=args.forcar, so_vistoriar=args.vistoriar)
    except NaoPublicou as exc:
        print(f"[publicar] {exc}")
        return 1
    laudo = resultado["laudo"]
    if args.vistoriar:
        print(f"\n{laudo['titulo']}")
        for parte in laudo["partes"]:
            marca = "ok " if parte["ok"] else "ERRO"
            print(f"  [{marca}] parte {parte['parte']}: {parte['duracao']}s, "
                  f"audio {parte['media_db']} dB, "
                  f"{parte['imagens']['prontas']}/{parte['imagens']['total']} imagens")
        print(f"\nvistoria: {'PASSOU' if laudo['ok'] else 'REPROVOU'} "
              f"({len(laudo['erros'])} erro(s), {len(laudo['avisos'])} aviso(s))")
        return 0 if laudo["ok"] else 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Canal de historias por IA: roteiro -> imagens -> video")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("prompt", help="monta o prompt-mestre para colar no LLM")
    p.add_argument("modelo", nargs="?", default=None,
                   help="estrutura do roteiro (veja: main.py modelos)")
    p.add_argument("--tema", default=None,
                   help="ponto de partida opcional; sem isto o LLM inventa tudo")
    p.add_argument("--cenas", type=int, default=None, help="quantas cenas pedir")
    p.add_argument("--arquivo", default=None,
                   help="seu proprio modelo (.txt, uma linha por bloco)")
    p.add_argument("--copiar", action="store_true",
                   help="ja copia o prompt para o clipboard")

    r = sub.add_parser("roteiro", help="importa a resposta do LLM como roteiro")
    r.add_argument("arquivo", nargs="?", default=None,
                   help="arquivo com a resposta (ou '-' para stdin)")
    r.add_argument("--colar", action="store_true",
                   help="le a resposta do clipboard")
    r.add_argument("--modelo", default=None, help="so para registro")
    r.add_argument("--tema", default=None, help="so para registro")

    g = sub.add_parser("gerar",
                       help="AUTOMATICO: abre o LLM no browser e escreve a serie")
    g.add_argument("--provedor", default="chatgpt", choices=("chatgpt", "gemini"))
    g.add_argument("--partes", type=int, default=6,
                   help="quantas partes (cada parte vira um video)")
    g.add_argument("--cenas", type=int, default=14, help="cenas por parte")
    g.add_argument("--tema", default=None,
                   help="ponto de partida; sem isto o LLM inventa tudo")
    g.add_argument("--headless", action="store_true")

    llm = sub.add_parser("llm", help="login e diagnostico do ChatGPT/Gemini")
    llm.add_argument("acao", choices=("login", "probe"))
    llm.add_argument("--provedor", default="chatgpt", choices=("chatgpt", "gemini"))
    llm.add_argument("--esperar", type=float, default=0.0,
                     help="no probe, segundos com a janela aberta antes de olhar")

    i = sub.add_parser("imagens", help="gera as imagens das cenas (PicassoIA)")
    i.add_argument("historia_id")
    i.add_argument("--parte", type=int, default=None, help="so esta parte")
    i.add_argument("--limite", type=int, default=None,
                   help="gera no maximo N cenas nesta passada")
    i.add_argument("--headless", action="store_true")

    v = sub.add_parser("video", help="narracao + legenda + mp4 (um por parte)")
    v.add_argument("historia_id")
    v.add_argument("--parte", type=int, default=None, help="so esta parte")
    v.add_argument("--preview", action="store_true", help="render rapido")

    t = sub.add_parser("tudo", help="imagens que faltam + video")
    t.add_argument("historia_id")
    t.add_argument("--preview", action="store_true")
    t.add_argument("--headless", action="store_true")

    sub.add_parser("modelos", help="estruturas de roteiro disponiveis")

    s = sub.add_parser("status", help="onde cada historia esta")
    s.add_argument("historia_id", nargs="?", default=None)

    cf = sub.add_parser("conferir",
                        help="procura defeito no que ja esta no disco")
    cf.add_argument("historia_id", nargs="?", default=None)
    cf.add_argument("--consertar", action="store_true",
                    help="apaga as entradas ruins do cache de voz")
    cf.add_argument("--numeros", action="store_true",
                    help="lista os valores e anos que a narracao cita")

    pub = sub.add_parser("publicar", help="lista/exporta/envia os videos prontos")
    pub.add_argument("historia_id", nargs="?", default=None)
    pub.add_argument("--exportar", action="store_true",
                     help="copia com nome legivel + .txt do texto")
    pub.add_argument("--youtube", action="store_true", help="sobe pela API")
    pub.add_argument("--tiktok", action="store_true",
                     help="sobe pelo navegador e PARA antes de postar")
    pub.add_argument("--visibilidade", default=None,
                     choices=("private", "unlisted", "public"))
    pub.add_argument("--serie", action="store_true",
                     help="vistoria e sobe TODAS as partes, na ordem, agendadas")
    pub.add_argument("--vistoriar", action="store_true",
                     help="so confere se as partes estao publicaveis")
    pub.add_argument("--sem-agendar", action="store_true",
                     help="sobe tudo agora, sem espalhar no calendario")
    pub.add_argument("--intervalo", type=float, default=24.0,
                     help="horas entre uma parte e a proxima (padrao 24)")
    pub.add_argument("--comecar", default=None, metavar="ISO",
                     help="quando a parte 1 vai ao ar (ex.: 2026-09-01T18:00)")
    pub.add_argument("--forcar", action="store_true",
                     help="publica mesmo com problema na vistoria")

    args = parser.parse_args()
    from contos.pipeline.controller import Pipeline
    pipeline = Pipeline()
    acoes = {"prompt": cmd_prompt, "roteiro": cmd_roteiro, "gerar": cmd_gerar,
             "llm": cmd_llm, "imagens": cmd_imagens,
             "video": cmd_video, "tudo": cmd_tudo, "modelos": cmd_modelos,
             "status": cmd_status, "publicar": cmd_publicar,
             "conferir": cmd_conferir}
    return acoes[args.comando](args, pipeline)


if __name__ == "__main__":
    raise SystemExit(main())
