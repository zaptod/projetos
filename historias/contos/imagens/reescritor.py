# -*- coding: utf-8 -*-
"""Cena bloqueada -> o ChatGPT reescreve o prompt -> o worker cola o novo.

Pedido do Adrian em 31/08/2026, depois de o PicassoIA bloquear uma imagem de
novo: "quero que o programa consiga pegar o que deu erro, re gerar o chat gpt
ou algo assim e colar o novo".

A troca mecanica (`rb identity/moderacao.py`) e instantanea e de graca, mas e
burra: ela nao sabe o que a cena esta CONTANDO, entao troca palavra por
palavra e as vezes estraga a frase. O LLM sabe — ele escreveu a historia. Por
isso a ordem de tentativas do worker e:

    original -> LLM reescreve -> LLM reescreve sabendo que a 1a falhou
             -> mecanico nivel 2 -> mecanico nivel 3 (so o ambiente)

O mecanico continua no fim como REDE: se o navegador do LLM nao abrir (sem
login, conta ocupada, site fora), a cena ainda tem chance de gerar sem
depender de mais nada.

Detalhes que fazem diferenca:

  UM CHAT PARA A HISTORIA INTEIRA. A sessao abre na primeira recusa e fica
  aberta ate o fim da geracao. Alem de economizar o custo de abrir o Chrome
  por cena, o chat ACUMULA contexto: na terceira cena bloqueada o modelo ja
  sabe o que este filtro costuma barrar.

  PERFIL SEPARADO. O LLM usa o perfil do ChatGPT e o PicassoIA usa o dele, e
  a trava e por conta — as duas janelas convivem sem disputa.

  NUNCA DERRUBA A GERACAO. Qualquer falha aqui (sem login, timeout, resposta
  vazia) vira `None` e o worker segue para o proximo degrau.
"""
from __future__ import annotations

import re
from contextlib import ExitStack

# O pedido ao modelo. Explicito sobre o que NAO fazer, porque a resposta vai
# direto para o campo do PicassoIA: qualquer "Claro! Aqui esta:" entraria no
# prompt e viraria texto desenhado na imagem.
INSTRUCAO = """Voce esta me ajudando a gerar as imagens de uma historia em video.

O prompt de imagem abaixo foi BLOQUEADO pelo filtro de conteudo do gerador.

PROMPT BLOQUEADO:
{prompt}

MOTIVO QUE O SITE MOSTROU:
{motivo}

Reescreva esse prompt para que ele PASSE no filtro, seguindo estas regras:
- Mantenha a MESMA cena: mesmo lugar, mesma luz, mesmo momento da historia.
  A imagem tem que continuar servindo para a narracao daquela cena.
- Mostre o ANTES ou o DEPOIS em vez do ato: a mao tremendo, a porta fechada,
  o copo caido, a mancha no chao. Sugerir e mais forte que mostrar.
- Sem sangue, ferimento, arma, nudez, menor de idade em perigo, autolesao,
  droga ou violencia explicita. Nada de texto ou letras na imagem.
- Mantenha as clausulas de estilo tecnico que ja estao no prompt
  (lente, iluminacao, granulacao, cor) exatamente como estao.
- Em ingles, em uma linha so, clausulas separadas por virgula.

Responda APENAS com o novo prompt. Sem aspas, sem explicacao, sem titulo,
sem "aqui esta". A primeira letra da sua resposta e a primeira letra do
prompt."""

DE_NOVO = """Esse tambem foi BLOQUEADO.

PROMPT BLOQUEADO:
{prompt}

MOTIVO:
{motivo}

Tente de novo, agora bem mais conservador: descreva o AMBIENTE e um objeto
que conte a cena, com a pessoa de longe, de costas ou fora do quadro.
Mesmas regras de antes. Responda APENAS com o novo prompt."""

# Ruido tipico de resposta de chat que nao pode entrar no campo do gerador.
# Aplicado em LACO: "Claro! Aqui esta:" e dois prefixos colados, e tirar so
# o primeiro deixaria "! Aqui esta:" indo para dentro do prompt.
PREFIXOS = re.compile(
    r"^\s*(?:aqui\s+est[ao]|aqui\s+vai|claro|segue|certo|perfeito|entendi"
    r"|novo\s+prompt|prompt\s+novo|prompt|sure|here\s+(?:it\s+)?is)\b"
    r"\s*[:\-–—,!.]*\s*", re.IGNORECASE)
CERCA = re.compile(r"^```[a-z]*\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

# O modelo recusando tambem e uma resposta — e nao pode virar prompt.
RECUSA_DO_MODELO = re.compile(
    r"^\s*(?:n[aã]o\s+posso|n[aã]o\s+consigo|desculpe|sinto\s+muito"
    r"|i\s+(?:can'?t|cannot|am\s+unable)|i'?m\s+sorry|unfortunately)",
    re.IGNORECASE)


def limpar(resposta: str) -> str:
    """Texto de chat -> prompt puro (ou "" se nao veio nada aproveitavel).

    O modelo obedece "responda so o prompt" quase sempre; o "quase" e o que
    esta funcao existe para absorver.
    """
    texto = CERCA.sub("", str(resposta or "")).strip()
    if not texto:
        return ""
    # Varias linhas: fica a mais longa que pareca prompt (tem virgula), o que
    # descarta titulo, comentario e a pergunta de volta.
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    if len(linhas) > 1:
        candidatas = [l for l in linhas if l.count(",") >= 2] or linhas
        texto = max(candidatas, key=len)
    texto = texto.strip('"').strip("'").strip("*").strip()
    for _ in range(3):                    # "Claro! Aqui esta:" = dois prefixos
        limpo = PREFIXOS.sub("", texto).strip()
        if limpo == texto:
            break
        texto = limpo
    texto = texto.strip('"').strip("'").strip("*").strip()
    if RECUSA_DO_MODELO.match(texto):
        return ""
    # Prompt de imagem e uma lista de clausulas: sem virgula nenhuma, o que
    # veio foi conversa, nao prompt.
    if len(texto) < 25 or texto.count(" ") < 4 or "," not in texto:
        return ""
    return texto


class Reescritor:
    """Sessao de LLM viva durante a geracao, usada so quando algo e barrado.

    Preguicoso de proposito: quem nunca leva bloqueio nunca abre o navegador.
    """

    def __init__(self, provedor: str = "chatgpt", *, headless: bool = False,
                 ajustes: dict | None = None, log=print,
                 timeout: float | None = 180.0):
        self.provedor = provedor
        self.headless = headless
        self.ajustes = ajustes
        self.log = log
        self.timeout = timeout
        self._pilha: ExitStack | None = None
        self._cliente = None
        self._desistiu = False        # ja falhou em abrir: nao tenta de novo
        self.reescritas = 0

    # ------------------------------------------------------------- sessao
    def _garantir(self):
        if self._cliente is not None or self._desistiu:
            return self._cliente
        from ..llm.cliente import abrir_cliente
        try:
            self.log(f"[imagens] abrindo o {self.provedor} para reescrever o "
                     "prompt bloqueado...")
            self._pilha = ExitStack()
            self._cliente = self._pilha.enter_context(
                abrir_cliente(self.provedor, headless=self.headless,
                              ajustes=self.ajustes, log=self.log))
            self._cliente.abrir(novo_chat=True)
        except Exception as exc:
            # Sem login, conta ocupada, site fora: o worker cai no mecanico.
            self.log(f"[imagens] nao abri o {self.provedor} ({exc}); sigo com "
                     "a suavizacao automatica.")
            self._fechar_pilha()
            self._desistiu = True
        return self._cliente

    def _fechar_pilha(self):
        if self._pilha is not None:
            try:
                self._pilha.close()
            except Exception:
                pass
        self._pilha, self._cliente = None, None

    def fechar(self):
        if self._cliente is not None:
            self.log(f"[imagens] fechando o {self.provedor} "
                     f"({self.reescritas} reescrita(s)).")
        self._fechar_pilha()

    def __enter__(self):
        return self

    def __exit__(self, *_erro):
        self.fechar()
        return False

    # ---------------------------------------------------------- reescrita
    def reescrever(self, prompt: str, motivo: str,
                   primeira: bool = True) -> str | None:
        """O novo prompt, ou None quando o LLM nao pode ajudar agora."""
        cliente = self._garantir()
        if cliente is None:
            return None
        molde = INSTRUCAO if primeira else DE_NOVO
        pedido = molde.format(prompt=prompt,
                              motivo=(motivo or "conteudo bloqueado")[:300])
        try:
            resposta = cliente.perguntar(pedido, timeout=self.timeout)
        except Exception as exc:
            self.log(f"[imagens] o {self.provedor} nao respondeu ({exc}); "
                     "sigo com a suavizacao automatica.")
            self._desistiu = True
            self._fechar_pilha()
            return None
        novo = limpar(resposta)
        if not novo:
            self.log(f"[imagens] o {self.provedor} nao devolveu um prompt "
                     "utilizavel.")
            return None
        if novo.strip().lower() == (prompt or "").strip().lower():
            self.log(f"[imagens] o {self.provedor} devolveu o mesmo prompt.")
            return None
        self.reescritas += 1
        return novo
