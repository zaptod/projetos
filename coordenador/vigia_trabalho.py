# -*- coding: utf-8 -*-
"""O vigia de trabalho: alguem de olho nas tarefas, entregas e decisoes.

Pedido do Adrian (02/10, 00:1x): "as tarefas no app estao todas paradas,
quero alguem de olho nisso tambem", "alguem checando se precisa de decisao
pro Grimorio" e "alguem checando o avanco das tasks".

O laco do supervisor chama `VigiaTrabalho.passo()` a cada ~60 s, numa thread
propria (os testes de uma entrega levam minutos). Sem novidade, ele so le.

1. Entregas do Codex (`remoto.delegar`). Delegado que TERMINOU depois que o
   vigia nasceu, sem aplicar nem limpar:
   coletar -> validador -> testes da area -> momento seguro -> aplicar ->
   commit POR CAMINHO (so os arquivos do diff) -> limpar. Testes vermelhos:
   UMA correcao (`corrigir`, no fundo, com a cauda da saida); falhou de novo,
   ou o validador recusou: avisa ("precisa de olho") e nao mexe mais. Codigo
   de servico mudou: pede o reinicio ao supervisor (que so reinicia em
   momento seguro). Entregas mais velhas que o vigia so aparecem no resumo:
   muitas ja foram aplicadas a mao, e reaplicar seria barulho.
2. Mesa (`remoto.orquestrador`). Item "CODEX ..." cujos delegados citados ja
   foram aplicados: fecha (`agente_fim`). Item sem relato ha 45 min: avisa
   uma vez por relato.
3. Grimorio (`remoto.decisoes`). A secao de duvida da resposta do Codex vai
   ao CEREBRO, que diz se e escolha de produto e redige o no (2 ou 3 opcoes).
   Sem cerebro (proibido, teto, limite), so avisa. No maximo 5 nos por dia,
   nunca dois de mesmo titulo.
4. Resumo de andamento no Telegram e nos eventos do app: so com novidade, e
   no maximo a cada 60 min. O retrato vai sempre para `estado.json`, chave
   `trabalho`:
     {"em", "proibido", "rodando": [{id, titulo}], "mesa": [{id, parte,
      titulo, sem_relato_min}], "aplicados": [{id, commit, em}] (ultimos 10),
      "olho": [{id, motivo, em}], "esperando": {id: motivo},
      "corrigindo": [ids], "antigos": [ids], "espera_adrian": {"decisoes": n,
      "titulos": [...], "propostas": n}, "fila": {"n", "primeiros"},
      "resumo_em", "novidades": n}
5. Com o Claude proibido, so observa: nao aplica, nao corrige, nao fecha a
   Mesa e nao cria no.

A memoria (o que ja foi avisado, aplicado, corrigido) fica em
`trabalho_memoria.json`, na pasta do coordenador: reiniciar nao repete aviso.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from .estado import pasta

INTERVALO_S = 60
PARADA_S = 45 * 60
NOS_POR_DIA = 5
RESUMO_A_CADA_S = 60 * 60
CORRECAO_ESPERA_S = 10 * 60      # a correcao pedida tem de comecar nesse prazo
CAUDA_TESTES = 4000
SEM_TESTE = ("docs",)            # pasta de topo que nao tem teste
CO_AUTOR = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# "O que ficou duvidoso", "o que ficou de fora ou em duvida" (o pedido padrao
# do despachante), "Duvidas", "Precisa de decisao"
DUVIDA = re.compile(r"(o que ficou[\w\s]{0,24}duvid\w*|duvid\w*|precisa(?:m)? de decisao)",
                    re.I)
FIM_DE_SECAO = re.compile(r"^\s*(#+\s|\*\*[^*]+\*\*\s*:?\s*$|[A-Z][^.:]{0,60}:\s*$)")


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()


def _norm(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _sem_acento(texto).lower()).strip()


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _data(iso) -> datetime | None:
    try:
        return datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return None


# ================================================================ ajudantes
def extrair_duvida(resposta: str) -> str:
    """O texto da secao de duvida da resposta do Codex ('' se nao ha).

    Aceita "O que ficou duvidoso", "Duvidas", "Precisa de decisao", como
    titulo (##, **...**) ou como rotulo ("Duvidas: ..."). Vai ate o proximo
    titulo. "nenhuma", "nada" e "-" contam como sem duvida."""
    linhas = str(resposta or "").splitlines()
    for i, linha in enumerate(linhas):
        limpa = _sem_acento(linha)
        if not DUVIDA.search(limpa) or len(limpa.strip()) > 200:
            continue
        cabeca = re.match(r"^\s*(#+\s*|\*\*|[-*]\s*\*\*)?(.*)$", limpa).group(2)
        if not DUVIDA.match(cabeca.strip(" *:")):
            continue
        resto = linha.split(":", 1)[1].strip(" *") if ":" in linha else ""
        corpo = [resto] if resto else []
        for seguinte in linhas[i + 1:]:
            if FIM_DE_SECAO.match(seguinte) and corpo:
                break
            corpo.append(seguinte)
        texto = "\n".join(corpo).strip()
        if _norm(texto) in ("", "nenhuma", "nenhum", "nada", "nao", "sem duvidas",
                            "nenhuma duvida", "nada ficou duvidoso"):
            return ""
        return texto[:4000]
    return ""


def primeira_linha(resposta: str, reserva: str) -> str:
    """A primeira linha util da resposta (sem Markdown); generica = a reserva."""
    for linha in str(resposta or "").splitlines():
        # "[api_http.py](/E:/projetos-wt/...:186)" vira "api_http.py"
        limpa = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", linha)
        limpa = re.sub(r"[#*`>]+", "", limpa).strip(" -:")
        if not limpa:
            continue
        if len(limpa) < 12 or limpa.endswith(":") or _norm(limpa) in (
                "o que mudou", "resumo", "pronto", "feito", "o que construiu"):
            break
        return limpa[:120]
    return (str(reserva or "").strip() or "entrega do Codex")[:120]


def comando_de_teste(estado: dict, arquivos: list[str]) -> str | None:
    """O comando dos testes: o do estado (`testes_cmd`, ou o `testes` em texto,
    ou o `cmd` da ultima rodada), senao o pytest das pastas de topo mudadas.
    None = so documentacao (nada para testar)."""
    for bruto in (estado.get("testes_cmd"), estado.get("testes")):
        if isinstance(bruto, str) and bruto.strip():
            return bruto.strip()
        if isinstance(bruto, dict) and str(bruto.get("cmd") or "").strip():
            return str(bruto["cmd"]).strip()
    pastas = []
    for caminho in arquivos:
        partes = str(caminho).replace("\\", "/").split("/")
        if len(partes) < 2 or partes[0] in SEM_TESTE or partes[0].startswith("."):
            continue
        if partes[0] not in pastas:
            pastas.append(partes[0])
    if not pastas:
        return None
    return "python -m pytest " + " ".join(pastas) + " -q"


def precisa_da_prova_de_tela(arquivos: list[str]) -> bool:
    """A casca ou a CSP mudou: o pytest precisa abrir o app de verdade."""
    caminhos = [str(a).replace("\\", "/") for a in arquivos]
    return any(caminho == "remoto/api_http.py" or caminho.startswith("remoto/app/")
               for caminho in caminhos)


def servicos_afetados(arquivos: list[str], servicos: dict) -> list[str]:
    saida = []
    for nome, ficha in servicos.items():
        for modulo in ficha.get("modulos", []):
            prefixo = str(modulo).rstrip("/") + "/"
            if any(str(a).replace("\\", "/").startswith(prefixo) for a in arquivos):
                saida.append(nome)
                break
    return saida


def delegados_citados(item: dict, delegados: list[dict]) -> list[dict]:
    """Os delegados que o titulo de um item da Mesa cita: o id literal, ou
    todas as palavras do id ("armas 16F" cita `armas-16f`). So os criados
    a partir de 30 min antes do item (um id antigo de palavra comum, como
    `coordenador`, nao conta)."""
    titulo = _norm(item.get("titulo"))
    palavras = set(titulo.split())
    desde = _data(item.get("desde"))
    saida = []
    for d in delegados:
        ident = str(d.get("id") or "")
        criado = _data(d.get("criado_em"))
        if desde and criado and criado < desde - timedelta(minutes=30):
            continue
        tokens = [t for t in ident.split("-") if len(t) >= 2]
        if ident.replace("-", " ") in titulo or (tokens and all(t in palavras for t in tokens)):
            saida.append(d)
    return saida


# ========================================================== efeitos reais
def _git(args, repo, entrada=None):
    return subprocess.run(["git", *args], cwd=str(repo), input=entrada, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          creationflags=NO_WINDOW)


def arquivos_sujos(arquivos: list[str], repo=None) -> list[str]:
    """Os arquivos do diff que ja tem mudanca nao commitada na arvore principal
    (aplicar por cima levaria a mudanca de outro para dentro do commit)."""
    if not arquivos:
        return []
    if repo is None:
        from remoto import delegar
        repo = delegar.repo()
    feito = _git(["status", "--porcelain", "--", *arquivos], repo)
    if feito.returncode != 0:
        raise RuntimeError("git status falhou: " + (feito.stderr or "").strip()[:200])
    return [linha[3:].strip() for linha in feito.stdout.splitlines() if linha.strip()]


def commitar_por_caminho(arquivos: list[str], mensagem: str, repo=None) -> str:
    """`git add` + `git commit -- <arquivos>` (so eles), com nova tentativa
    quando o index.lock esta preso. Devolve o hash curto."""
    if repo is None:
        from remoto import delegar
        repo = delegar.repo()
    feito = _git(["add", "-A", "--", *arquivos], repo)
    if feito.returncode != 0:
        raise RuntimeError("git add falhou: " + (feito.stderr or "").strip()[:300])
    for tentativa in range(6):
        feito = _git(["commit", "-F", "-", "--", *arquivos], repo, entrada=mensagem)
        if feito.returncode == 0:
            break
        erro = (feito.stderr or feito.stdout or "").strip()
        if "index.lock" not in erro or tentativa == 5:
            raise RuntimeError("git commit falhou: " + erro[:300])
        time.sleep(2)
    return _git(["rev-parse", "--short", "HEAD"], repo).stdout.strip()


def corrigir_no_fundo(ident: str, texto: str) -> None:
    """`python -m remoto.delegar corrigir --id X --texto arq --fundo`."""
    from remoto import delegar
    arquivo = delegar.pasta_da(ident) / "vigia_correcao.md"
    arquivo.write_text(texto, encoding="utf-8")
    delegar.no_fundo(["corrigir", "--id", ident, "--texto", str(arquivo)], ident)


def codex_pode_comecar(delegados: list[dict], agora: datetime) -> str:
    """'' se uma rodada do Codex pode comecar agora; senao, o motivo (as
    mesmas guardas do despachante, para a correcao nao ser recusada calada)."""
    from remoto import delegar
    try:
        config = delegar.ler_config()
        if delegar._janela(config["janela_sem_comecar"], agora):
            de, ate = config["janela_sem_comecar"]
            return f"nada começa entre :{de:02d} e :{ate:02d}"
        rodando = sum(1 for d in delegados if d.get("situacao") == "rodando")
        if rodando >= int(config.get("delegados_paralelo") or 1):
            return "outro delegado está rodando"
        delegar.conferir_teto(config)
    except Exception as exc:                                  # noqa: BLE001
        return str(exc) or type(exc).__name__
    return ""


def _proibido_real() -> str:
    try:
        from remoto import claude_estado
        return claude_estado.motivo_proibido()
    except Exception as exc:                                  # noqa: BLE001
        return f"não li o interruptor do Claude ({type(exc).__name__})"


def _classificar_real(duvida: str, contexto: str) -> dict:
    from . import cerebro
    return cerebro.classificar_duvida(duvida, contexto)


def _propostas_real() -> int:
    from . import cerebro
    return len(cerebro.propostas_pendentes())


def _servicos_real() -> dict:
    from .supervisor import carregar_servicos
    return carregar_servicos()


# ================================================================== o vigia
class VigiaTrabalho:
    def __init__(self, *, delegar=None, orquestrador=None, decisoes=None, commitar=None,
                 sujos=None, corrigir=None, pode_corrigir=None, avisar=None, evento=None,
                 relogio=datetime.now, seguro=None, pedir_reinicio=None, proibido=None,
                 classificar=None, propostas=None, servicos=None, memoria=None):
        if delegar is None:
            from remoto import delegar
        if orquestrador is None:
            from remoto import orquestrador
        if decisoes is None:
            from remoto import decisoes
        self.delegar, self.orquestrador, self.decisoes = delegar, orquestrador, decisoes
        self.commitar = commitar or commitar_por_caminho
        self.sujos = sujos or arquivos_sujos
        self.corrigir = corrigir or corrigir_no_fundo
        self.pode_corrigir = pode_corrigir or codex_pode_comecar
        self.avisar = avisar or (lambda texto: False)
        self.evento = evento or (lambda tipo, texto: None)
        self.relogio = relogio
        # sem criterio de momento seguro, nunca e seguro (falha fechado)
        self.seguro = seguro or (lambda: (False, "sem critério de momento seguro"))
        self.pedir_reinicio = pedir_reinicio or (lambda nome: None)
        self.proibido = proibido or _proibido_real
        self.classificar = classificar or _classificar_real
        self.propostas = propostas or _propostas_real
        self.servicos = servicos or _servicos_real
        self.caminho_memoria = Path(memoria) if memoria else pasta() / "trabalho_memoria.json"
        self.ultimo = {}

    def _aplica_sozinho(self) -> bool:
        """`{"vigia_aplica": false}` no config.json do coordenador para a
        entrega pronta e deixa o aplicar para o orquestrador (o padrao, como
        pedido em 02/10, e aplicar)."""
        try:
            dados = json.loads((self.caminho_memoria.parent / "config.json").read_text(
                encoding="utf-8"))
        except (OSError, ValueError):
            return True
        return not (isinstance(dados, dict) and dados.get("vigia_aplica") is False)

    # ------------------------------------------------------------ memoria
    def _ler_memoria(self) -> dict:
        try:
            dados = json.loads(self.caminho_memoria.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            dados = {}
        if not isinstance(dados, dict):
            dados = {}
        for chave, padrao in (("vistos", []), ("olho", {}), ("aplicados", {}),
                              ("corrigidos", {}), ("esperando", {}), ("parados", []),
                              ("nos", {}), ("titulos", []), ("novidades", []),
                              ("duvidas", []), ("fechados", [])):
            if not isinstance(dados.get(chave), type(padrao)):
                dados[chave] = padrao
        return dados

    def _gravar_memoria(self, mem: dict) -> None:
        for chave, n in (("vistos", 300), ("parados", 300), ("titulos", 300),
                         ("novidades", 60), ("duvidas", 300), ("fechados", 300)):
            mem[chave] = mem[chave][-n:]
        mem["nos"] = dict(sorted(mem["nos"].items())[-10:])
        self.caminho_memoria.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho_memoria.with_name(f".{self.caminho_memoria.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.caminho_memoria)

    def _novidade(self, mem: dict, tipo: str, texto: str) -> None:
        mem["novidades"].append({"em": _iso(self.relogio()), "tipo": tipo, "texto": texto})
        self.evento(f"trabalho_{tipo}", texto)

    def _olho(self, mem: dict, ident: str, motivo: str) -> None:
        mem["olho"][ident] = {"motivo": motivo[:400], "em": _iso(self.relogio())}
        mem["esperando"].pop(ident, None)
        # 03/10/2026, o Adrian: "VOCE AINDA BARRA O CODEX DE RESOLVER O PROBLEMA".
        # Entrega travada nao fica esperando ninguem: um INTEGRADOR e contratado
        # na hora para juntar, testar e entregar de novo (uma vez por entrega).
        integrador = self._contratar_integrador(mem, ident, motivo)
        texto = (f"entrega {ident} travou ({motivo[:300]}); "
                 + (f"o integrador {integrador} já está resolvendo" if integrador
                    else "precisa de olho"))
        self.avisar("⚠ " + texto)
        self._novidade(mem, "olho", texto)

    def _contratar_integrador(self, mem: dict, ident: str, motivo: str) -> str | None:
        if ident.startswith("integrar-") or "não mudou nada" in motivo:
            return None                   # nao integra integrador; vazio vira permissao
        feitos = mem.setdefault("integrando", {})
        if ident in feitos:
            return feitos[ident]
        criar, no_fundo = getattr(self.delegar, "criar", None), getattr(self.delegar, "no_fundo", None)
        if not (callable(criar) and callable(no_fundo)):
            return None
        novo = ("integrar-" + ident)[:40]
        try:
            pasta = self.delegar.pasta_da(ident)
            pedido = pasta / "integrar.md"
            pedido.write_text(
                f"A entrega `{ident}` travou no vigia: {motivo}\n\n"
                f"O diff dela está em `{pasta / 'diff.patch'}` e a tarefa original em "
                f"`{pasta / 'tarefa.md'}`. Na SUA worktree (que saiu do HEAD atual):\n"
                "1. aplique com `git apply -3`; resolva cada conflito JUNTANDO os dois lados "
                "(as duas funções têm de ficar); a casca do app (`painel-casca-vN`) fica na "
                "maior versão + 1, igual em `remoto/app/sw.js` e `remoto/test_app_vila_objetos.py`;\n"
                "2. se o motivo foi teste falhando, conserte o código (não o teste, a não ser "
                "que o teste seja instável de tempo — aí dê folga);\n"
                "3. rode os testes da parte com -p no:cacheprovider até ficarem verdes.\n"
                "A sua entrega É a entrega original, já integrada. Não desista: se precisar de "
                "algo fora do escopo, peça permissão (.permissao.json).\n", encoding="utf-8")
            ia = "claude"
            try:
                from remoto.orquestrador import claude_estado
                if not claude_estado.ler().get("liberado", True):
                    ia = "codex"
            except Exception:                                 # noqa: BLE001
                pass
            permitidos = (self.delegar.ler_estado(ident).get("permitidos") or ["**"])
            criar(novo, pedido, permitidos, ia=ia, cargo="integrador",
                  titulo=f"Integrar {ident}")
            no_fundo(["rodar", "--id", novo], novo)
        except Exception as exc:                              # noqa: BLE001
            self.evento("trabalho_integrador", f"{ident}: não contratei o integrador ({exc})")
            return None
        feitos[ident] = novo
        self._novidade(mem, "integrando", f"{ident} travou; contratei o integrador {novo}")
        return novo

    # --------------------------------------------------------------- passo
    def passo(self) -> dict:
        agora = self.relogio()
        mem = self._ler_memoria()
        mem.setdefault("desde", _iso(agora))
        proibido = self.proibido()
        delegados = self._listar()
        mesa = self._mesa()
        if not proibido:
            for d in delegados:
                if d.get("situacao") == "terminou" and not d.get("aplicado") and not d.get("limpo"):
                    try:
                        self._cuidar(d, mem, mesa, delegados, agora)
                    except Exception as exc:                  # noqa: BLE001
                        self._olho(mem, str(d.get("id")), f"o vigia tropeçou: {exc}")
            delegados = self._listar()
            self._fechar_mesa(mesa, delegados, mem)
        self._mesa_parada(mesa, mem, agora)
        trabalho = self._retrato(delegados, mesa, mem, agora, proibido)
        self._resumo(trabalho, mem, agora)
        trabalho["resumo_em"] = mem.get("resumo_em")
        self._gravar_memoria(mem)
        self.ultimo = trabalho
        return trabalho

    def _listar(self) -> list[dict]:
        try:
            return [d for d in self.delegar.listar() if isinstance(d, dict)]
        except Exception:                                     # noqa: BLE001
            return []

    def _mesa(self) -> dict:
        try:
            estado = self.orquestrador.ler_estado()
        except Exception:                                     # noqa: BLE001
            return {"agora": [], "fila": [], "ilegivel": True}
        return {"agora": list(estado.get("agora") or []), "fila": list(estado.get("fila") or [])}

    # ----------------------------------------------------------- entregas
    def _resposta(self, ident: str) -> str:
        try:
            return (self.delegar.pasta_da(ident) / "resposta.md").read_text(encoding="utf-8")
        except (OSError, AttributeError):
            return ""

    def _cauda_testes(self, ident: str) -> str:
        try:
            texto = (self.delegar.pasta_da(ident) / "testes.log").read_text(
                encoding="utf-8", errors="replace")
        except (OSError, AttributeError):
            return ""
        return texto[-CAUDA_TESTES:]

    def _cuidar(self, d: dict, mem: dict, mesa: dict, delegados: list, agora: datetime) -> None:
        did = str(d["id"])
        if did in mem["olho"]:
            return
        if str(d.get("fim") or "") < mem["desde"]:
            mem.setdefault("antigos", [])
            if did not in mem["antigos"]:
                mem["antigos"].append(did)
            return
        if did not in mem["vistos"]:
            mem["vistos"].append(did)
            self._novidade(mem, "terminou", f"o Codex terminou {did}")
            self._duvida(d, mem, mesa, agora)
        corr = mem["corrigidos"].get(did)
        if corr and str(d.get("fim") or "") <= corr.get("em", ""):
            # a correcao foi pedida e ainda nao rodou (ou foi recusada calada)
            pedida = _data(corr.get("em"))
            if pedida and (agora - pedida).total_seconds() > CORRECAO_ESPERA_S:
                self._olho(mem, did, "a correção pedida às "
                           f"{corr['em'][11:16]} não começou")
            return
        try:
            resumo = self.delegar.coletar(did)
        except Exception as exc:                              # noqa: BLE001
            self._olho(mem, did, f"não consegui coletar o diff: {exc}")
            return
        if not resumo.get("ok"):
            self._olho(mem, did, "o validador recusou: " + "; ".join(resumo.get("motivos") or []))
            return
        arquivos = [a["caminho"] for a in resumo.get("arquivos") or []]
        ok, motivo = self.seguro()
        if not ok:
            mem["esperando"][did] = motivo
            return
        testes = d.get("testes") if isinstance(d.get("testes"), dict) else None
        if not testes or testes.get("diff_sha") != resumo.get("sha"):
            cmd = comando_de_teste(d, arquivos)
            if cmd is None:
                testes = {"ok": True, "sem_testes": True, "resumo": "só documentação"}
            else:
                if precisa_da_prova_de_tela(arquivos):
                    # `delegar.testar` usa cmd.exe: a prova, marcada para nao
                    # abrir Chrome nas suites comuns, entra nesta entrega.
                    cmd = "set NF_TESTE_NAVEGADOR=1&& " + cmd
                try:
                    testes = self.delegar.testar(did, cmd)
                except Exception as exc:                      # noqa: BLE001
                    self._olho(mem, did, f"não consegui rodar os testes: {exc}")
                    return
        if not testes.get("ok"):
            self._vermelho(d, mem, delegados, agora, resumo, testes)
            return
        ok, motivo = self.seguro()                 # os testes levaram minutos
        if not ok:
            mem["esperando"][did] = motivo
            return
        if not self._aplica_sozinho():
            mem["esperando"][did] = ("pronta para aplicar (validador e testes ok); o aplicar "
                                     "sozinho está desligado no config.json do coordenador")
            return
        try:
            repo_tarefa = Path(d["repo"]) if d.get("repo") else None
            if repo_tarefa is None and hasattr(self.delegar, "repo"):
                repo_tarefa = self.delegar.repo()
            sujos = self.sujos(arquivos, repo=repo_tarefa) if repo_tarefa else self.sujos(arquivos)
        except Exception as exc:                              # noqa: BLE001
            self._olho(mem, did, f"não consegui conferir a árvore principal: {exc}")
            return
        if sujos:
            # alguem esta mexendo nesses arquivos agora: espera, nao abandona
            mem["esperando"][did] = ("a árvore principal tem mudança não commitada em "
                                     + ", ".join(sujos[:5]))
            return
        try:
            aplicado = self.delegar.aplicar(did, sem_testes=bool(testes.get("sem_testes")))
        except Exception as exc:                              # noqa: BLE001
            texto = str(exc)
            if texto.startswith("aplicar só fora") or texto.startswith("publicação em voo"):
                mem["esperando"][did] = texto
            else:
                self._olho(mem, did, f"aplicar recusou: {texto}")
            return
        arquivos = list(aplicado.get("arquivos") or arquivos)
        mensagem = (f"{primeira_linha(self._resposta(did), d.get('titulo'))} "
                    f"(feito pelo Codex, validado pelo vigia)\n\n{CO_AUTOR}\n")
        try:
            commit = (self.commitar(arquivos, mensagem, repo=repo_tarefa)
                      if repo_tarefa else self.commitar(arquivos, mensagem))
        except Exception as exc:                              # noqa: BLE001
            self._olho(mem, did, f"aplicado na árvore, mas o commit falhou ({exc}); "
                       "os arquivos estão lá sem commit: " + ", ".join(arquivos[:8]))
            return
        mem["esperando"].pop(did, None)
        mem["aplicados"][did] = {"commit": commit, "em": _iso(self.relogio()),
                                 "arquivos": arquivos[:20]}
        self._novidade(mem, "aplicado", f"entrega {did} aplicada: {commit}")
        try:
            servicos = self.servicos()
        except Exception:                                     # noqa: BLE001
            servicos = {}
        for nome in servicos_afetados(arquivos, servicos):
            self.pedir_reinicio(nome)
        try:
            self.delegar.limpar(did)
        except Exception as exc:                              # noqa: BLE001
            self.evento("trabalho_limpar", f"{did}: não limpei a worktree ({exc})")

    def _vermelho(self, d, mem, delegados, agora, resumo, testes) -> None:
        did = str(d["id"])
        if did in mem["corrigidos"]:
            self._olho(mem, did, "os testes falharam de novo depois da correção: "
                       + str(testes.get("resumo") or f"código {testes.get('codigo')}"))
            return
        motivo = self.pode_corrigir(delegados, agora)
        if motivo:
            mem["esperando"][did] = f"testes falharam; a correção espera: {motivo}"
            return
        cauda = self._cauda_testes(did)
        texto = ("Os testes da sua entrega falharam no vigia do coordenador.\n\n"
                 f"Comando: `{testes.get('cmd') or '?'}` (código {testes.get('codigo')}).\n\n"
                 f"Os últimos {CAUDA_TESTES} caracteres da saída:\n\n```\n{cauda}\n```\n\n"
                 "Conserte mexendo só nos caminhos permitidos, rode os testes de novo "
                 "(com -p no:cacheprovider) e responda como antes.")
        try:
            self.corrigir(did, texto)
        except Exception as exc:                              # noqa: BLE001
            self._olho(mem, did, f"os testes falharam e a correção não abriu: {exc}")
            return
        mem["corrigidos"][did] = {"em": _iso(self.relogio()), "sha": resumo.get("sha")}
        mem["esperando"].pop(did, None)
        self._novidade(mem, "corrigindo", f"testes de {did} falharam; pedi UMA correção")

    # ------------------------------------------------------------- duvidas
    def _projeto(self, ident: str, mesa: dict) -> str:
        projetos = getattr(self.decisoes, "PROJETOS", ())
        for item in mesa.get("agora") or []:
            if any(d.get("id") == ident for d in delegados_citados(item, [{"id": ident}])):
                if item.get("parte") in projetos:
                    return item["parte"]
        return "geral"

    def _duvida(self, d: dict, mem: dict, mesa: dict, agora: datetime) -> None:
        did = str(d["id"])
        if did in mem["duvidas"]:
            return
        mem["duvidas"].append(did)
        duvida = extrair_duvida(self._resposta(did))
        if not duvida:
            return
        hoje = agora.date().isoformat()
        if int(mem["nos"].get(hoje, 0)) >= NOS_POR_DIA:
            self.avisar(f"❔ dúvida na entrega do Codex {did} (já são {NOS_POR_DIA} nós "
                        f"hoje; não criei outro): {duvida[:600]}")
            return
        contexto = f"Entrega do Codex {did}: {d.get('titulo') or ''}"
        try:
            ficha = self.classificar(duvida, contexto)
        except Exception as exc:                              # noqa: BLE001
            self.avisar(f"❔ dúvida na entrega do Codex {did} (sem cérebro para "
                        f"classificar: {exc}): {duvida[:600]}")
            return
        if not isinstance(ficha, dict) or not ficha.get("precisa_decisao"):
            return                                   # detalhe tecnico: nao vira no
        titulo = str(ficha.get("titulo") or "").strip()[:80]
        pergunta = str(ficha.get("pergunta") or "").strip()
        opcoes = [o for o in ficha.get("opcoes") or []
                  if isinstance(o, dict) and str(o.get("rotulo") or "").strip()][:3]
        if not titulo or not pergunta or len(opcoes) < 2:
            self.avisar(f"❔ dúvida de produto na entrega {did}, mas o cérebro não "
                        f"redigiu um nó completo: {duvida[:400]}")
            return
        chave = _norm(titulo)
        try:
            existentes = {_norm(i.get("titulo")) for i in self.decisoes.carregar().values()}
        except Exception:                                     # noqa: BLE001
            existentes = set()
        if chave in existentes or chave in mem["titulos"]:
            return
        projeto = self._projeto(did, mesa)
        contexto_no = (str(ficha.get("contexto") or "").strip() + f" (entrega do Codex {did}; "
                       "nó criado pelo vigia de trabalho do coordenador)").strip()
        brutas = [{"id": str(o.get("id") or ""), "rotulo": str(o["rotulo"]).strip()[:80],
                   "descricao": str(o.get("descricao") or "").strip()[:300]} for o in opcoes]
        try:
            item, _ = self.decisoes.adicionar_e_commitar(projeto, titulo, pergunta, brutas,
                                                         contexto=contexto_no)
        except Exception as exc:                              # noqa: BLE001
            self.avisar(f"❔ não consegui criar o nó da dúvida de {did}: {exc}")
            return
        mem["nos"][hoje] = int(mem["nos"].get(hoje, 0)) + 1
        mem["titulos"].append(chave)
        self._novidade(mem, "no", f"nó novo no Grimório: {projeto}/{item.get('id')} — {titulo}")

    # ---------------------------------------------------------------- Mesa
    def _fechar_mesa(self, mesa: dict, delegados: list, mem: dict) -> None:
        for item in mesa.get("agora") or []:
            if not re.search(r"\bCODEX\b", str(item.get("titulo") or "")):
                continue
            citados = delegados_citados(item, delegados)
            if not citados or not all(d.get("aplicado") for d in citados):
                continue
            commits = [mem["aplicados"].get(d["id"], {}).get("commit") for d in citados]
            commits = [c for c in commits if c]
            try:
                self.orquestrador.agente_fim(
                    item["id"], situacao="concluido", commits=commits,
                    relato_final="entregas do Codex aplicadas: "
                    + ", ".join(d["id"] for d in citados) + " (fechado pelo vigia)")
            except Exception as exc:                          # noqa: BLE001
                self.evento("trabalho_mesa", f"não fechei {item.get('id')}: {exc}")
                continue
            mem["fechados"].append(item["id"])
            self._novidade(mem, "mesa", f"fechei na Mesa: {item.get('titulo')}")

    def _mesa_parada(self, mesa: dict, mem: dict, agora: datetime) -> None:
        for item in mesa.get("agora") or []:
            ref = item.get("relato_em") or item.get("desde")
            quando = _data(ref)
            if quando is None:
                continue
            minutos = int((agora - quando).total_seconds() // 60)
            if minutos * 60 < PARADA_S:
                continue
            chave = f"{item.get('id')}@{ref}"
            if chave in mem["parados"]:
                continue
            mem["parados"].append(chave)
            texto = f"tarefa «{item.get('titulo')}» ({item.get('id')}) parada há {minutos} min"
            self.avisar("⏸ " + texto)
            self._novidade(mem, "parada", texto)

    # -------------------------------------------------------------- resumo
    def _espera_adrian(self) -> dict:
        saida = {"decisoes": None, "titulos": [], "propostas": None}
        try:
            itens = self.decisoes.carregar()
            pendentes = [i for i in itens.values() if i.get("situacao") in ("pendente", "a_rever")]
            saida["decisoes"] = len(pendentes)
            saida["titulos"] = [f"{i.get('projeto')}/{i.get('titulo')}" for i in pendentes][:5]
        except Exception:                                     # noqa: BLE001
            pass
        try:
            saida["propostas"] = int(self.propostas())
        except Exception:                                     # noqa: BLE001
            pass
        return saida

    def _retrato(self, delegados, mesa, mem, agora, proibido) -> dict:
        agora_mesa = []
        for item in mesa.get("agora") or []:
            quando = _data(item.get("relato_em") or item.get("desde"))
            agora_mesa.append({"id": item.get("id"), "parte": item.get("parte"),
                               "titulo": item.get("titulo"),
                               "sem_relato_min": int((agora - quando).total_seconds() // 60)
                               if quando else None})
        aplicados = sorted(({"id": k, **v} for k, v in mem["aplicados"].items()),
                           key=lambda x: x.get("em", ""))[-10:]
        fila = mesa.get("fila") or []
        return {"em": _iso(agora), "proibido": proibido,
                "rodando": [{"id": d.get("id"), "titulo": d.get("titulo")}
                            for d in delegados if d.get("situacao") == "rodando"],
                "mesa": agora_mesa, "aplicados": aplicados,
                "olho": [{"id": k, **v} for k, v in mem["olho"].items()][-10:],
                "esperando": dict(mem["esperando"]),
                "corrigindo": [k for k in mem["corrigidos"] if k not in mem["aplicados"]
                               and k not in mem["olho"]],
                "antigos": list(mem.get("antigos", []))[-20:],
                "espera_adrian": self._espera_adrian(),
                "fila": {"n": len(fila), "primeiros": [f"[{f.get('parte')}] {f.get('item')}"
                                                       for f in fila[:3]]},
                "novidades": len(mem["novidades"])}

    def _resumo(self, trabalho: dict, mem: dict, agora: datetime) -> None:
        espera = trabalho["espera_adrian"]
        assinatura = f"{espera.get('decisoes')}|{espera.get('propostas')}"
        if mem.get("espera_assinatura") not in (None, assinatura):
            mem["novidades"].append({"em": _iso(agora), "tipo": "espera",
                                     "texto": "mudou o que espera você"})
        mem["espera_assinatura"] = assinatura
        if not mem["novidades"]:
            return
        ultimo = _data(mem.get("resumo_em"))
        if ultimo and (agora - ultimo).total_seconds() < RESUMO_A_CADA_S:
            return
        linhas = [f"🛰 Andamento ({agora:%H:%M})"]
        icones = {"aplicado": "✓", "terminou": "⏹", "olho": "⚠", "corrigindo": "🔧",
                  "no": "🌳", "mesa": "📌", "parada": "⏸"}
        for n in mem["novidades"][-12:]:
            if n["tipo"] in icones:
                linhas.append(f"{icones[n['tipo']]} {n['texto']}")
        rodando = len(trabalho["rodando"])
        linhas.append(f"Rodando: {rodando} delegado(s) do Codex, "
                      f"{len(trabalho['mesa'])} tarefa(s) na Mesa")
        if espera.get("decisoes") is not None or espera.get("propostas") is not None:
            linhas.append(f"Espera você: {espera.get('decisoes') or 0} decisão(ões) no "
                          f"Grimório, {espera.get('propostas') or 0} proposta(s) do cérebro")
        fila = trabalho["fila"]
        linhas.append(f"Fila: {fila['n']} item(ns)"
                      + (f"; primeiro: {fila['primeiros'][0]}" if fila["primeiros"] else ""))
        if trabalho["proibido"]:
            linhas.append(f"({trabalho['proibido']}: só observo)")
        texto = "\n".join(linhas)
        self.avisar(texto)
        self.evento("trabalho_resumo", texto.replace("\n", " · ")[:300])
        mem["resumo_em"] = _iso(agora)
        mem["novidades"] = []
