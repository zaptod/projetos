# -*- coding: utf-8 -*-
"""Um video -> uma ficha. O prompt, o parser tolerante e o validador.

Molde de `historias/contos/roteiro/serie.py`, e pelo mesmo motivo: pedir
texto livre a um LLM e receber texto livre de volta e o jeito de ter uma
analise que nao da para somar. A ficha e um formato fixo justamente para que
177 respostas virem uma tabela — e a biblia sai de contar padrao na tabela,
nao de pedir a um modelo que "resuma o canal".

O que se pede e o que o modelo faz melhor que o ffmpeg: intencao, tom, a
quem aquilo esta falando, por que a pessoa fica. Os numeros ja vao prontos
no dossie, entao ele nao precisa (nem deve) estimar nada disso.

Sobre as citacoes: sao EVIDENCIA, curtas, com o instante em que foram ditas
— servem para sustentar uma afirmacao sobre o padrao. Nao se pede, e nao se
aceita, a transcricao de volta: o objetivo e descrever como o canal e feito,
nao recontar o conteudo dele.
"""
from __future__ import annotations

import json
import re
import unicodedata

# As secoes que toda ficha tem. A ordem e a do prompt, e e a ordem em que a
# biblia le depois.
SECOES = ("gancho", "estrutura", "fala", "edicao", "publico", "tema", "cta",
          "promessa", "reproduzivel", "evidencia")

# Sem estas quatro a ficha nao sustenta nenhuma secao da biblia.
OBRIGATORIAS = ("gancho", "fala", "edicao", "publico")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto))
                   if unicodedata.category(c) != "Mn")


def prompt_abertura(cabecalho_do_canal: str, *, total: int,
                    cfg: dict | None = None) -> str:
    """O primeiro turno de cada chat: a tarefa, o canal e o formato."""
    cfg = cfg or {}
    palavras = int(cfg.get("citacao_max_palavras") or 12)
    citacoes = int(cfg.get("citacoes_por_ficha") or 5)

    linhas = []
    add = linhas.append
    add("Voce e analista de formato de canais de video. Meu objetivo e "
        "ENTENDER COMO ESTE CANAL E FEITO, para produzir conteudo proprio no "
        "mesmo formato — nao para copiar o conteudo dele.")
    add("")
    add(cabecalho_do_canal)
    add("")
    add(f"Vou te mandar {total} videos deste canal, UM POR MENSAGEM. Cada um "
        "vem como um dossie: ficha tecnica, numeros ja MEDIDOS por software, "
        "mapa de cortes e a transcricao com os tempos. Quando houver, vai "
        "junto um mosaico com frames do video.")
    add("")
    add("REGRAS QUE VALEM PARA TODAS AS RESPOSTAS:")
    add("  - Os numeros do bloco MEDIDO sao fato. Nao os re-estime, nao os "
        "contradiga; use-os para explicar o EFEITO que produzem.")
    add("  - O que eu quero de voce e o que so voce le: intencao, tom, a quem "
        "aquilo fala, por que a pessoa continua assistindo.")
    add("  - Nao invente o que o dossie nao mostra. Campo sem base vira "
        '"nao da para saber pelo dossie".')
    add(f"  - As citacoes sao EVIDENCIA: no maximo {citacoes}, de ate "
        f"{palavras} palavras cada, sempre com o instante. Nao reescreva a "
        "transcricao — descreva o padrao e cite so o que o comprova.")
    add("  - Responda SOMENTE com o JSON do formato abaixo, dentro de uma "
        "cerca de codigo. Sem texto antes nem depois.")
    add("")
    add(_formato())
    add("")
    add("Confirme que entendeu com uma linha so, e eu mando o primeiro video.")
    return "\n".join(linhas)


def _formato() -> str:
    """O contrato da resposta. Um exemplo vale mais que a descricao."""
    modelo = {
        "gancho": {
            "primeiros_segundos": "o que e dito e mostrado ate ~5s",
            "tecnica": "como prende (pergunta, promessa, choque, in medias res...)",
            "promessa": "o que o video promete entregar",
        },
        "estrutura": [
            {"de": "0:00", "ate": "0:12", "bloco": "gancho",
             "o_que_acontece": "uma frase"},
            {"de": "0:12", "ate": "2:40", "bloco": "desenvolvimento",
             "o_que_acontece": "uma frase"},
        ],
        "fala": {
            "pessoa": "primeira/segunda/terceira",
            "tom": "como soa (intimo, didatico, indignado, seco...)",
            "ritmo": "o efeito do wpm medido",
            "vocabulario": "nivel e campo (tecnico, coloquial, giria...)",
            "bordoes": ["expressoes que se repetem"],
            "formalidade": "de 1 (muito informal) a 5 (formal)",
        },
        "edicao": {
            "corte": "o efeito do numero medido de cortes",
            "b_roll": "o que aparece alem da pessoa falando",
            "texto_na_tela": "tem? como?",
            "som": "musica, efeitos, silencio",
            "camera": "enquadramento e movimento",
        },
        "publico": {
            "quem": "a quem isto fala",
            "pressupoe": "o que assume que a pessoa ja sabe",
            "dor": "que problema ou desejo toca",
            "por_que_fica": "o que segura ate o fim",
        },
        "tema": {"assunto": "sobre o que e", "angulo": "o recorte"},
        "cta": {"pede": "o que pede", "onde": "em que instante",
                "como": "explicito ou implicito"},
        "promessa": {"titulo_formula": "o padrao do titulo",
                     "thumb": "o que a capa promete, se der para ver"},
        "reproduzivel": {
            "ja_automatizavel": ["o que uma pipeline de IA faria hoje"],
            "exige_pessoa": ["o que depende de rosto, voz propria ou opiniao"],
            "dificil": ["o que da para fazer, mas com trabalho"],
        },
        "evidencia": [{"em": "1:24", "cita": "trecho curto"}],
    }
    return ("FORMATO (JSON, exatamente estas chaves):\n```json\n"
            + json.dumps(modelo, ensure_ascii=False, indent=2) + "\n```")


def prompt_ficha(video: dict, dossie: str, *, ordem: int = 0,
                 total: int = 0) -> str:
    """O turno de um video: o dossie e o pedido da ficha."""
    posicao = f" ({ordem} de {total})" if ordem and total else ""
    return (f"VIDEO{posicao}. Responda so o JSON da ficha, na cerca de "
            f"codigo.\n\n{dossie}")


def prompt_conserto(problemas: list) -> str:
    """A repergunta. No MESMO chat, listando o que faltou."""
    lista = "\n".join(f"  - {p}" for p in problemas)
    return ("A ficha veio incompleta. Nao refaca a analise: devolva o MESMO "
            "JSON, corrigindo so isto:\n" + lista +
            "\n\nSo o JSON, na cerca de codigo.")


# --------------------------------------------------------------- o parser
_CERCA = re.compile(r"```(?:json)?\s*(.+?)```", re.S)


def parse_ficha(texto: str) -> dict:
    """A resposta do LLM -> dicionario. Tolerante, como o resto da casa.

    Tres tentativas, da mais provavel para a mais teimosa: a cerca de codigo
    (o que se pediu), o JSON cru (quando o modelo esquece a cerca) e o maior
    bloco entre chaves (quando ele escreve um paragrafo antes).
    """
    bruto = str(texto or "")
    for candidato in _candidatos(bruto):
        try:
            dados = json.loads(candidato)
        except ValueError:
            continue
        if isinstance(dados, dict):
            return _normalizar(dados, bruto)
    return {"bruto": bruto, "_ilegivel": True}


def _candidatos(texto: str) -> list:
    tentativas = [m.strip() for m in _CERCA.findall(texto)]
    tentativas.append(texto.strip())
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio >= 0 and fim > inicio:
        tentativas.append(texto[inicio:fim + 1])
    return [t for t in tentativas if t]


# O modelo as vezes traduz a chave, tira o acento ou usa sinonimo. Sao
# poucos casos e custam uma ficha inteira quando nao se trata.
_ALIAS = {
    "hook": "gancho", "abertura": "gancho",
    "structure": "estrutura", "roteiro": "estrutura",
    "speech": "fala", "narracao": "fala", "voz": "fala",
    "editing": "edicao", "montagem": "edicao",
    "audience": "publico", "audiencia": "publico",
    "theme": "tema", "assunto": "tema", "tema_e_angulo": "tema",
    "call_to_action": "cta", "chamada": "cta",
    "promise": "promessa", "titulo": "promessa",
    "reproducible": "reproduzivel", "reproducao": "reproduzivel",
    "evidence": "evidencia", "citacoes": "evidencia",
}


def _normalizar(dados: dict, bruto: str) -> dict:
    ficha = {}
    for chave, valor in dados.items():
        limpa = _sem_acento(str(chave)).strip().lower().replace(" ", "_")
        ficha[_ALIAS.get(limpa, limpa)] = valor
    ficha["bruto"] = bruto
    return ficha


def _vazio(valor) -> bool:
    """Campo que existe mas nao diz nada — o modo mais comum de ficha ruim."""
    if valor is None:
        return True
    if isinstance(valor, str):
        texto = _sem_acento(valor).strip().lower()
        return (not texto or texto in
                {"n/a", "na", "-", "?", "nao se aplica", "nao sei",
                 "desconhecido", "nao informado", "null", "none"})
    if isinstance(valor, (list, tuple, dict)):
        return all(_vazio(v) for v in (valor.values()
                                       if isinstance(valor, dict) else valor))
    return False


def problemas_da_ficha(ficha: dict, *, cfg: dict | None = None) -> list:
    """O que impede esta ficha de sustentar uma secao da biblia."""
    cfg = cfg or {}
    if ficha.get("_ilegivel"):
        return ["a resposta nao continha JSON legivel"]

    faltando = []
    for secao in OBRIGATORIAS:
        if secao not in ficha or _vazio(ficha.get(secao)):
            faltando.append(f"a secao {secao} veio vazia ou ausente")

    gancho = ficha.get("gancho")
    if isinstance(gancho, dict) and _vazio(gancho.get("tecnica")):
        faltando.append("gancho.tecnica vazio (e o que a biblia copia)")

    estrutura = ficha.get("estrutura")
    if not isinstance(estrutura, list) or len(estrutura) < 2:
        faltando.append("estrutura precisa de pelo menos 2 blocos com tempo")

    evidencia = ficha.get("evidencia")
    if not isinstance(evidencia, list) or not evidencia:
        faltando.append("evidencia vazia (sem citacao com instante, a "
                        "afirmacao nao se sustenta)")
    else:
        teto = int(cfg.get("citacao_max_palavras") or 12)
        longas = [e for e in evidencia if isinstance(e, dict)
                  and len(str(e.get("cita", "")).split()) > teto * 2]
        if longas:
            faltando.append(f"{len(longas)} citacao(oes) longas demais — "
                            f"evidencia e trecho curto (ate ~{teto} palavras), "
                            "nao transcricao")
        sem_tempo = [e for e in evidencia if isinstance(e, dict)
                     and _vazio(e.get("em"))]
        if sem_tempo:
            faltando.append(f"{len(sem_tempo)} citacao(oes) sem o instante")
    return faltando


def resumo_da_ficha(ficha: dict) -> str:
    """Uma linha para o log — o suficiente para ver que nao veio generico."""
    gancho = ficha.get("gancho") or {}
    tecnica = gancho.get("tecnica") if isinstance(gancho, dict) else ""
    blocos = len(ficha.get("estrutura") or [])
    citacoes = len(ficha.get("evidencia") or [])
    return (f"{blocos} bloco(s), {citacoes} citacao(oes) · "
            f"gancho: {str(tecnica)[:56]}")
