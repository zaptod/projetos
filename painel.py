"""PAINEL DE CONTROLE - Neural Fights + Random Builds.

Menu unico para tudo: videos de build, simulacao, torneio, lives com chat
do YouTube, database e biblioteca de reacoes. Cada acao roda a CLI oficial
da ferramenta em um processo proprio (nada e reimplementado aqui).

Uso:  python painel.py   (ou dois cliques em painel.bat)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
RANDOM_BUILDS = RAIZ / "random_builds"
PY = sys.executable


# ----------------------------------------------------------------- utilidades
def perguntar(texto: str, padrao: str = "") -> str:
    sufixo = f" [{padrao}]" if padrao else ""
    try:
        resposta = input(f"{texto}{sufixo}: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return ""
    return resposta or padrao


def confirmar(texto: str, padrao_sim: bool = False) -> bool:
    opcoes = "S/n" if padrao_sim else "s/N"
    resposta = perguntar(f"{texto} ({opcoes})", "s" if padrao_sim else "n")
    return resposta.lower().startswith("s")


def rodar(args: list[str], cwd: Path = RAIZ, rotulo: str | None = None) -> None:
    mostrado = rotulo or " ".join(str(a) for a in args)
    print("\n>>> " + mostrado + "\n" + "-" * 56, flush=True)
    try:
        codigo = subprocess.call([str(a) for a in args], cwd=str(cwd))
    except KeyboardInterrupt:
        codigo = 130
    print("-" * 56, flush=True)
    print(f"(processo encerrado com codigo {codigo})", flush=True)
    perguntar("Enter para voltar ao menu")


def titulo(texto: str) -> None:
    print("\n" + "=" * 56)
    print(f"  {texto}")
    print("=" * 56)


def menu(texto: str, opcoes: list[tuple[str, str]]) -> str:
    titulo(texto)
    for chave, descricao in opcoes:
        print(f"  [{chave}] {descricao}")
    print("  [0] Voltar" if texto != "PAINEL DE CONTROLE" else "  [0] Sair")
    return perguntar("Opcao")


# ------------------------------------------------------------ [1] videos
def menu_videos() -> None:
    while True:
        opcao = menu("VIDEOS DE BUILD (random_builds)", [
            ("1", "Gerar video completo (2 formatos + insere no banco)"),
            ("2", "Gerar com seed especifica"),
            ("3", "Preview rapido (nao insere no banco)"),
            ("4", "So dados, sem video (--generation-only)"),
            ("5", "Lote de balanceamento (N builds, so dados)"),
            ("6", "Re-renderizar uma geracao existente"),
            ("7", "Biblioteca de reacoes (assistente interativo)"),
            ("8", "Identidade visual do personagem (Digen)"),
            ("9", "Luta unica -> video (a luta e o elemento dominante)"),
            ("r", "Ranking da arena (cartel dos personagens)"),
        ])
        base = [PY, "-u", "-X", "utf8", "main.py", "generate-video"]
        if opcao in ("", "0"):
            return
        elif opcao == "9":
            extras = []
            p1 = perguntar("P1 (vazio = ultimo criado na roleta)")
            p2 = perguntar("P2 (vazio = adversario por continuidade/poder)")
            if p1:
                extras += ["--p1", p1]
            if p2:
                extras += ["--p2", p2]
            seed = perguntar("Seed (vazio = aleatoria)")
            if seed:
                extras += ["--seed", seed]
            if confirmar("Preview rapido?"):
                extras.append("--preview")
            rodar([PY, "-u", "-X", "utf8", "main.py", "fight"] + extras, RANDOM_BUILDS)
        elif opcao == "r":
            rodar([PY, "-u", "-X", "utf8", "main.py", "arena", "ranking"], RANDOM_BUILDS)
        elif opcao == "1":
            rodar(base, RANDOM_BUILDS)
        elif opcao == "2":
            seed = perguntar("Seed (numero)")
            if not seed:
                continue
            extras = ["--seed", seed]
            if confirmar("Preview rapido?"):
                extras.append("--preview")
            if not confirmar("Inserir no banco do neural_fights?", padrao_sim=True):
                extras.append("--no-insert")
            rodar(base + extras, RANDOM_BUILDS)
        elif opcao == "3":
            rodar(base + ["--preview", "--no-insert"], RANDOM_BUILDS)
        elif opcao == "4":
            rodar(base + ["--generation-only"], RANDOM_BUILDS)
        elif opcao == "5":
            quantidade = perguntar("Quantas builds", "100")
            rodar(base + ["--generation-only", "--count", quantidade], RANDOM_BUILDS)
        elif opcao == "6":
            saidas = sorted(p.name for p in (RANDOM_BUILDS / "outputs").glob("generation_*"))
            if not saidas:
                print("  Nenhuma geracao encontrada em outputs/.")
                continue
            print("  Geracoes existentes:")
            for nome in saidas:
                print(f"    - {nome}")
            escolha = perguntar("Qual re-renderizar", saidas[-1])
            # --refazer-edicao: remonta a timeline. E so assim que um clipe
            # de identidade que chegou depois entra no video.
            extras = ["--rerender", escolha, "--refazer-edicao"]
            if confirmar("Preview rapido?"):
                extras.append("--preview")
            rodar(base + extras, RANDOM_BUILDS)
        elif opcao == "7":
            rodar([PY, "-u", "-X", "utf8", "main.py", "reactions"], RANDOM_BUILDS)
        elif opcao == "8":
            menu_identidade()


def menu_identidade() -> None:
    while True:
        opcao = menu("IDENTIDADE VISUAL (Digen)", [
            ("1", "Login no Digen (janela visivel; faca o 1o login aqui)"),
            ("2", "Processar a fila (baixa os clipes e refaz os videos)"),
            ("3", "Ficar em pe processando (Ctrl+C para sair)"),
            ("4", "Ver a fila"),
            ("5", "Limpar os jobs ja concluidos"),
            ("6", "Despejar seletores do site (quando o Digen muda)"),
            ("7", "Diagnostico completo (abre o Digen e confere os seletores)"),
            ("8", "Diagnostico rapido (sem abrir o browser)"),
            ("9", "Status: fila, clipes, videos finais e inconsistencias"),
            ("h", "Historico de geracoes"),
            ("a", "Auditar origem dos artefatos (as contas dos sites sao compartilhadas)"),
        ])
        base = [PY, "-u", "-X", "utf8", "main.py", "identity"]
        if opcao in ("", "0"):
            return
        elif opcao == "1":
            rodar(base + ["login"], RANDOM_BUILDS)
        elif opcao == "2":
            rodar(base + ["worker"], RANDOM_BUILDS)
        elif opcao == "3":
            rodar(base + ["worker", "--watch"], RANDOM_BUILDS)
        elif opcao == "4":
            rodar(base + ["queue"], RANDOM_BUILDS)
        elif opcao == "5":
            rodar(base + ["queue", "--limpar"], RANDOM_BUILDS)
        elif opcao == "6":
            rodar(base + ["probe"], RANDOM_BUILDS)
        elif opcao == "7":
            rodar(base + ["doctor", "--online"], RANDOM_BUILDS)
        elif opcao == "8":
            rodar(base + ["doctor"], RANDOM_BUILDS)
        elif opcao == "9":
            rodar(base + ["status"], RANDOM_BUILDS)
        elif opcao.lower() == "h":
            rodar(base + ["history", "-n", "40"], RANDOM_BUILDS)
        elif opcao.lower() == "a":
            rodar(base + ["auditar"], RANDOM_BUILDS)


# --------------------------------------------------------- [2] simulacao
def menu_simulacao() -> None:
    while True:
        opcao = menu("SIMULACAO (neural_fights)", [
            ("1", "Launcher com interface (UI)"),
            ("2", "Simulacao automatica (IA vs IA)"),
            ("3", "Modo de teste manual (WASD/skills)"),
            ("4", "Torneio (interface de torneio)"),
            ("5", "Simulacao headless (sem janela, com relatorio)"),
            ("6", "Debug da simulacao (arena com overlay)"),
        ])
        if opcao in ("", "0"):
            return
        elif opcao == "1":
            rodar([PY, "-m", "neural_fights.cli.main"])
        elif opcao == "2":
            rodar([PY, "-m", "neural_fights.cli.main", "--sim"])
        elif opcao == "3":
            rodar([PY, "-m", "neural_fights.cli.main", "--test"])
        elif opcao == "4":
            rodar([PY, "-m", "neural_fights.cli.tournament"])
        elif opcao == "5":
            modo = perguntar("Modo (rapido/stress/all)", "rapido")
            extras = ["--mode", modo]
            seed = perguntar("Seed (vazio = aleatoria)")
            if seed:
                extras += ["--seed", seed]
            p1 = perguntar("Lutador P1 (vazio = padrao)")
            p2 = perguntar("Lutador P2 (vazio = padrao)")
            if p1:
                extras += ["--p1", p1]
            if p2:
                extras += ["--p2", p2]
            rodar([PY, "-m", "neural_fights.cli.headless"] + extras)
        elif opcao == "6":
            rodar([PY, "debug_simulation.py"])


# ------------------------------------------------------ [3] live/youtube
def menu_live() -> None:
    while True:
        opcao = menu("LIVE / YOUTUBE (neural_fights)", [
            ("1", "Iniciar live (so o show, sem chat)"),
            ("2", "Live com chat do YouTube"),
            ("3", "Live replay de eventos gravados (.jsonl)"),
            ("4", "Configurar credenciais do YouTube (OAuth)"),
        ])
        base = [PY, "-m", "neural_fights.cli.live"]
        if opcao in ("", "0"):
            return
        elif opcao == "1":
            extras = []
            if confirmar("Formato vertical (--portrait)?"):
                extras.append("--portrait")
            rodar(base + ["--source", "nenhuma"] + extras)
        elif opcao == "2":
            extras = ["--source", "youtube"]
            video_id = perguntar("ID do video da transmissao (vazio = consultar a conta)")
            if video_id:
                extras += ["--video-id", video_id]
            if confirmar("Formato vertical (--portrait)?"):
                extras.append("--portrait")
            if confirmar("Gravar eventos da sessao (.jsonl)?"):
                destino = perguntar("Arquivo de gravacao", "live_eventos.jsonl")
                extras += ["--gravar-eventos", destino]
            rodar(base + extras)
        elif opcao == "3":
            arquivo = perguntar("Arquivo .jsonl de eventos")
            if not arquivo:
                continue
            extras = ["--source", "replay", "--events", arquivo]
            if confirmar("Repetir em loop (--loop-events)?"):
                extras.append("--loop-events")
            rodar(base + extras)
        elif opcao == "4":
            print("  (client_id e client_secret saem do Google Cloud Console)")
            client_id = perguntar("client-id")
            client_secret = perguntar("client-secret")
            if not client_id or not client_secret:
                print("  Cancelado.")
                continue
            rodar([PY, "-m", "neural_fights.tools.youtube_oauth",
                   "--client-id", client_id, "--client-secret", client_secret])


# --------------------------------------------------------- [4] database
def menu_database() -> None:
    while True:
        opcao = menu("DATABASE (neural_fights)", [
            ("1", "Ver banco atual (contagens e ultimos inseridos)"),
            ("2", "Gerar roster (completo/64/16)"),
            ("3", "Analise estrutural das armas"),
            ("4", "Harness de qualidade de luta"),
            ("5", "REGENERAR database inteira (SUBSTITUI tudo!)"),
        ])
        if opcao in ("", "0"):
            return
        elif opcao == "1":
            rodar([PY, "-u", "-X", "utf8", "-c", RESUMO_BANCO],
                  rotulo="resumo do banco (neural_fights.data.database)")
        elif opcao == "2":
            modo = perguntar("Modo (completo/64/16)", "64")
            extras = ["--modo", modo]
            seed = perguntar("Seed (vazio = aleatoria)")
            if seed:
                extras += ["--seed", seed]
            rodar([PY, "-m", "neural_fights.cli.roster"] + extras)
        elif opcao == "3":
            rodar([PY, "-m", "neural_fights.tools.analise_armas"])
        elif opcao == "4":
            rodar([PY, "-m", "neural_fights.tools.qualidade_luta"])
        elif opcao == "5":
            print("\n  ATENCAO: isso APAGA o banco atual e gera um novo do zero.")
            print("  Personagens inseridos pelos videos de build serao perdidos.")
            if confirmar("Tem certeza?") and confirmar("Certeza MESMO?"):
                rodar([PY, "-m", "neural_fights.tools.gerador_database"])


RESUMO_BANCO = """
from neural_fights.data import database
armas, personagens = database.carregar_database()
print(f'{len(personagens)} personagens | {len(armas)} armas')
print()
print('Ultimos 5 personagens:')
for p in personagens[-5:]:
    print(f"  - {p['nome']} ({p['classe']}, forca {p['forca']}, arma: {p['nome_arma']})")
print()
print('Ultimas 5 armas:')
for a in armas[-5:]:
    print(f"  - {a['nome']} ({a['tipo']}/{a['estilo']}, {a['raridade']}, dano {a['dano']})")
caminhos = database.resolver_database_paths(para_escrita=False)
print()
print(f'Arquivos: {caminhos[0]}')
print(f'          {caminhos[1]}')
"""


# --------------------------------------------------------------- principal
def main() -> None:
    while True:
        opcao = menu("PAINEL DE CONTROLE", [
            ("1", "Videos de build (roletas + edicao automatica)"),
            ("2", "Simulacao (launcher, IA vs IA, teste, torneio)"),
            ("3", "Live / YouTube (show continuo, chat, OAuth)"),
            ("4", "Database (ver, roster, analises, regenerar)"),
        ])
        if opcao in ("", "0"):
            print("Ate mais!")
            return
        elif opcao == "1":
            menu_videos()
        elif opcao == "2":
            menu_simulacao()
        elif opcao == "3":
            menu_live()
        elif opcao == "4":
            menu_database()
        else:
            print("  Opcao invalida.")


if __name__ == "__main__":
    main()
