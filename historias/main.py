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
        # O codigo de saida diz se logou: quem chama isto de script (ou eu,
        # olhando o log depois) nao pode ter que adivinhar pelo traceback.
        return 0 if probe.login(args.provedor) else 1
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


def cmd_colagens(args, pipeline) -> int:
    """Lista (e opcionalmente apaga) as imagens que viraram colagem.

    Separado da vistoria DE PROPOSITO. Marcar as 44 como pendentes de uma vez
    faria a vistoria barrar cinco historias inteiras por "cena sem imagem" — e
    o estoque de hoje tem oito videos. Consertar o acervo e uma decisao de
    quando, nao um efeito colateral de ligar o detector.

    Com `--apagar`, a cena volta a ficar pendente e a proxima passada do
    worker a refaz com o mesmo prompt.
    """
    from contos.imagens import composicao
    from contos.pipeline.controller import OUTPUTS

    alvo = f"{args.historia_id}/cenas/*.png" if args.historia_id \
        else "historia_*/cenas/*.png"
    achadas, por_historia = 0, {}
    for arquivo in sorted(OUTPUTS.glob(alvo)):
        razao = composicao.motivo(arquivo)
        if not razao:
            continue
        achadas += 1
        historia = arquivo.parent.parent.name
        por_historia.setdefault(historia, []).append(arquivo)
        print(f"  {historia}/{arquivo.name}: {razao}")
    for historia, arquivos in sorted(por_historia.items()):
        print(f"{historia}: {len(arquivos)} colagem(ns)")
        if args.apagar:
            for arquivo in arquivos:
                arquivo.unlink()
            print(f"  apagadas — rode `main.py imagens {historia}` para refazer")
    print(f"\n{achadas} colagem(ns) encontradas.")
    return 0


def cmd_capas(args, pipeline) -> int:
    """Desenha a miniatura que falta em cada parte ja renderizada.

    Todo video anterior a 11/09/2026 subiu com o frame que o YouTube escolheu
    sozinho — e era isso que aparecia na prateleira de Shorts, sem uma letra
    na tela, do lado de concorrentes com titulo em corpo 120. Este comando
    existe para o ESTOQUE nao ficar esperando um novo render.
    """
    from contos.pipeline.controller import OUTPUTS
    from contos.roteiro import roteiro as R
    from contos.video import capa as capa_mod

    alvos = ([args.historia_id] if args.historia_id
             else sorted(p.name for p in OUTPUTS.glob("historia_*")
                         if p.is_dir()))
    feitas = puladas = 0
    for historia_id in alvos:
        try:
            roteiro = R.carregar(historia_id)
        except Exception as exc:                               # noqa: BLE001
            print(f"  ! {historia_id}: {exc}")
            continue
        pasta = OUTPUTS / historia_id
        total = len(roteiro.get("partes") or [])
        for bloco in roteiro.get("partes") or []:
            parte = int(bloco["n"])
            destino = capa_mod.caminho(pasta, parte, total)
            if destino.is_file() and not args.refazer:
                puladas += 1
                continue
            if not any(pasta.glob(f"final_*_p{parte:02d}.mp4")) \
                    and not any(pasta.glob("final_*.mp4")):
                continue
            feito = pipeline._capa(roteiro, historia_id, pasta, parte,
                                   pipeline.render_config, log=lambda _t: None)
            if feito:
                feitas += 1
                print(f"  {feito.relative_to(OUTPUTS)}")
    print(f"{feitas} capa(s) desenhada(s), {puladas} ja existiam.")
    return 0


def cmd_modelos(args, pipeline) -> int:
    from contos.roteiro import modelo
    for dados in modelo.listar(pipeline.roteiro_config):
        cenas = f"{dados['cenas']} cenas" if dados["cenas"] else "estrutura propria"
        print(f"  {dados['nome']:<14} {dados['rotulo']:<38} {cenas}")
    print("\nModelo proprio: um .txt em modelos/ (uma linha por bloco) e depois")
    print("  python main.py prompt --arquivo modelos/meu.txt")
    return 0


def cmd_auto(args, pipeline) -> int:
    """Criacao automatica: a rodada em si e as tarefas que a disparam."""
    from contos.pipeline import agenda, tarefas

    config = agenda.carregar()
    horas = args.horas or config["horas"]

    if args.instalar:
        resultados = tarefas.instalar(horas)
        for r in resultados:
            marca = "ok " if r["ok"] else "FALHOU"
            print(f"  [{marca}] {r['tarefa']}  {r['hora']:02d}:00  "
                  f"{r['mensagem'][:90]}")
        if any(not r["ok"] for r in resultados):
            print("\nAlguma tarefa nao entrou. O schtasks costuma precisar de "
                  "um terminal ABERTO COMO ADMINISTRADOR.")
            return 1
        print(f"\n{len(resultados)} tarefa(s) diaria(s) criadas. Elas chamam "
              f"{tarefas.caminho_do_lancador()}")
        print("O PC precisa estar ligado e com a sessao do Windows aberta na "
              "hora: a rodada abre Chrome de verdade.")
        return 0

    if args.remover:
        removidas = tarefas.remover()
        for r in removidas:
            print(f"  removida: {r['tarefa']}")
        print(f"{len(removidas)} tarefa(s) removida(s).")
        return 0

    if args.listar:
        instaladas = tarefas.listar()
        if not instaladas:
            print("nenhuma tarefa instalada. Rode: python main.py auto --instalar")
            return 1
        for t in instaladas:
            print(f"  {t['tarefa']:<22} proximo: {t['proximo']:<22} "
                  f"{t['situacao']}")
        print(f"\nagenda: {', '.join(f'{h:02d}:00' for h in config['horas'])}"
              f"  ({'ativa' if config.get('ativo', True) else 'DESLIGADA'})")
        pendentes = agenda.incompletas()
        for p in pendentes:
            print(f"  pendente: {p['historia_id']} - "
                  f"{p['imagens_faltando']} imagem(ns), "
                  f"{len(p['partes_sem_video'])} video(s)")
        return 0

    # Sem bandeira: E a rodada. E isto que a tarefa do Windows chama.
    resultado = agenda.rodar(config=config, headless=args.headless)
    if resultado.get("erros"):
        return 1
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
            from contos.publicar import serie as _serie
            # NAO PUBLICAR DUAS VEZES. Este caminho (parte avulsa) subia sem
            # olhar nem registrar o ledger — so `--serie` registrava. Rodar o
            # comando de novo colocaria o MESMO video no canal outra vez, e
            # video duplicado nao tem desfazer bonito. Medido em 08/09/2026:
            # a primeira publicacao do projeto saiu por aqui e nao deixou
            # rastro nenhum.
            ja = _serie.ja_publicado(alvo.id, "youtube")
            if ja and not args.forcar:
                print(f"YouTube: {alvo.id} ja foi publicado em "
                      f"{ja.get('quando', '?')} ({ja.get('url', 'sem url')}). "
                      "Use --forcar para subir de novo.")
                return 0
            try:
                url = catalogo.publicar_youtube(alvo, args.visibilidade)
                print("YouTube:", url)
                _serie.registrar(alvo, url, "youtube", None,
                                 {"visibilidade": args.visibilidade or ""})
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

    cg = sub.add_parser("colagens",
                        help="acha imagem que virou colagem de paineis")
    cg.add_argument("historia_id", nargs="?", default=None)
    cg.add_argument("--apagar", action="store_true",
                    help="apaga as achadas para o worker refazer")

    cp = sub.add_parser("capas", help="desenha a miniatura das partes prontas")
    cp.add_argument("historia_id", nargs="?", default=None)
    cp.add_argument("--refazer", action="store_true",
                    help="redesenha inclusive as que ja existem")

    s = sub.add_parser("status", help="onde cada historia esta")
    s.add_argument("historia_id", nargs="?", default=None)

    au = sub.add_parser("auto",
                        help="criacao automatica (rodada + tarefas do Windows)")
    au.add_argument("--instalar", action="store_true",
                    help="cria as tarefas diarias no Agendador do Windows")
    au.add_argument("--remover", action="store_true",
                    help="remove as tarefas diarias")
    au.add_argument("--listar", action="store_true",
                    help="mostra as tarefas, a agenda e o que ficou pendente")
    au.add_argument("--horas", type=int, nargs="+", default=None,
                    help="horas a instalar (padrao: as de config/agenda.json)")
    au.add_argument("--headless", action="store_true",
                    help="navegador invisivel (nao funciona para o LLM)")

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
             "conferir": cmd_conferir, "auto": cmd_auto, "capas": cmd_capas,
             "colagens": cmd_colagens}
    return acoes[args.comando](args, pipeline)


if __name__ == "__main__":
    raise SystemExit(main())
