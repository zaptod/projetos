"""CaptionGenerator: legendas direto dos dados (sem speech-to-text).

Cada rolagem vira uma legenda shitposter montada combinatoriamente:
  prefixo(tier) + nucleo(roleta + banda de qualidade) + sufixo(tier)
Os nucleos vivem em config/frases.json, escritos POR ROLETA - velocidade ruim
zoa a lentidao, forca insana zoa a forca - e a combinacao com prefixos e
sufixos garante 500+ legendas possiveis distintas para cada (roleta x tier).
"""
from __future__ import annotations

import random
import unicodedata

# Teto do nome pedido DEPOIS de sanitizar: o MESMO de quem aceitou o pedido.
# Import direto e de proposito - src.character.nomes so puxa unicodedata, e um
# teto proprio aqui produzia video incoerente: a legenda dizia "CRIANDO
# BARTOLOMEU AGU" no segundo 1 e a placa mostrava "BARTOLOMEU AGUIAR NETO" no
# segundo 20. Nome maior so faz `fit_font_wrap` encolher a fonte; nome errado
# na tela nao tem conserto.
from ..character.nomes import MAX_CHARS_PEDIDO as LIMITE_NOME

# Valores de `origem` que dizem que o nome NAO veio de comentario. Creditar um
# comentarista que nao existe e pior do que apenas convidar.
ORIGENS_SEM_CREDITO = frozenset({
    "aleatorio", "aleatoria", "random", "gerado", "gerada", "banco",
    "sorteado", "sorteada", "auto", "automatico", "nenhum", "none",
})

# O campo nasce em outro ponto do pipeline; aceitar mais de um nome de chave
# evita que a CTA volte a ser generica so porque o dicionario mudou de rotulo.
_CHAVES_PEDIDO = ("nome_pedido", "pedido", "nome_do_comentario")
_CHAVES_NOME = ("nome", "nome_pedido", "valor", "texto")
_CHAVES_AUTOR = ("autor", "usuario", "user", "comentarista", "quem")

BAND_BY_TIER = {
    "TERRIBLE": "negativo", "BAD": "negativo", "WEAK": "negativo",
    "AVERAGE": "mediano", "GOOD": "positivo", "GREAT": "positivo",
    "INSANE": "insano",
}
POOL_BY_TIER = {
    "TERRIBLE": "negativo_forte", "BAD": "negativo", "WEAK": "negativo",
    "AVERAGE": "neutro", "GOOD": "positivo", "GREAT": "positivo",
    "INSANE": "hype",
}


def _sem_acento(texto: str) -> str:
    """Copia local de proposito: este modulo nao pode depender do nf_bridge.

    O helper equivalente mora em src/nf_bridge/loader.py, que ao ser importado
    carrega o pacote neural_fights inteiro. Puxar isso so para tirar um acento
    de um nome de comentario custa caro e amarra a legenda ao jogo.
    """
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def _sanitizar(valor) -> str:
    """Texto de comentario pronto para virar frame.

    Tres coisas quebram se isto nao rodar: acento (o console e cp1252), caixa
    baixa (o banco e caixa alta) e chaves (um nome com chave derrubaria a rede
    de seguranca do _pick_pedido e apagaria a frase certa).
    """
    if not isinstance(valor, str):
        return ""
    limpo = _sem_acento(valor).upper()
    limpo = "".join(c for c in limpo
                    if c.isprintable() and ord(c) < 128 and c not in "{}")
    limpo = " ".join(limpo.split())
    return _cortar_em_palavra(limpo, LIMITE_NOME)


def _cortar_em_palavra(texto: str, limite: int) -> str:
    """Corta na ultima palavra inteira que couber; nunca no meio de uma.

    Fatia crua transformava "BARTOLOMEU AGUIAR" em "BARTOLOMEU AGU", que nao e
    o nome de ninguem. Palavra unica maior que o teto e o unico caso em que
    ainda se corta letra: ali nao ha fronteira para respeitar.
    """
    if len(texto) <= limite:
        return texto.strip()
    corte = texto.rfind(" ", 0, limite + 1)
    if corte > 0:
        return texto[:corte].strip()
    return texto[:limite].strip()


def pedido_de(generation: dict) -> dict:
    """Nome e autor que vieram dos comentarios, ou os dois vazios.

    Defensivo por contrato: quem grava o campo e outra etapa do pipeline e
    geracoes antigas nao o tem. Sem nome utilizavel o video se comporta como
    antes - convida, nao credita.
    """
    if not isinstance(generation, dict):
        return {"nome": "", "autor": ""}
    bruto = None
    for chave in _CHAVES_PEDIDO:
        if generation.get(chave):
            bruto = generation[chave]
            break
    if bruto is None:
        return {"nome": "", "autor": ""}

    if isinstance(bruto, str):
        return {"nome": _sanitizar(bruto), "autor": ""}
    if not isinstance(bruto, dict):
        return {"nome": "", "autor": ""}

    origem = str(bruto.get("origem", "")).strip().lower()
    if origem and origem in ORIGENS_SEM_CREDITO:
        return {"nome": "", "autor": ""}

    nome = ""
    for chave in _CHAVES_NOME:
        nome = _sanitizar(bruto.get(chave))
        if nome:
            break
    if not nome:
        return {"nome": "", "autor": ""}

    autor = ""
    for chave in _CHAVES_AUTOR:
        autor = _sanitizar(bruto.get(chave))
        if autor:
            break
    return {"nome": nome, "autor": autor}


class CaptionGenerator:
    def __init__(self, captions_config: dict, frases_config: dict):
        self.config = captions_config
        self.frases = frases_config

    def _pick(self, rng: random.Random, pool: list[str]) -> str:
        return rng.choice(pool)

    def _pick_pedido(self, rng: random.Random, banco: str, neutro: list,
                     substituicoes: dict) -> str:
        """Frase que credita o comentario, com rede de seguranca.

        A substituicao aqui e literal (str.replace), nao format(): um banco
        escrito com um placeholder que ninguem preenche iria para a tela com as
        chaves cruas. Se sobrar chave depois de substituir, a frase e
        descartada e o banco neutro assume - a tela nunca ve o placeholder.
        """
        pool = self.config.get(banco) or []
        if not pool:
            return self._pick(rng, neutro)
        texto = self._pick(rng, pool)
        for chave, valor in substituicoes.items():
            texto = texto.replace(chave, valor)
        if "{" in texto or "}" in texto:
            return self._pick(rng, neutro)
        return texto

    # ------------------------------------------------------------ montagem
    def _compor(self, rng: random.Random, nucleo: str, tier: str) -> str:
        prefixo = self._pick(rng, self.frases["prefixos"][POOL_BY_TIER[tier]])
        sufixo = self._pick(rng, self.frases["sufixos"][POOL_BY_TIER[tier]])
        if sufixo.strip(",.!? ").lower() == prefixo.strip(",.!? ").lower():
            sufixo = ""
        return " ".join(parte for parte in (prefixo, nucleo, sufixo) if parte)

    def _nucleos(self, roulette_id: str, band: str) -> list[str]:
        banco = self.frases["por_roleta"].get(roulette_id, {})
        return banco.get(band) or self.frases["_default"][band]

    def pool_size(self, roulette_id: str, tier: str) -> int:
        """Quantas legendas distintas existem para (roleta, tier)."""
        nucleos = self._nucleos(roulette_id, BAND_BY_TIER[tier])
        pool = POOL_BY_TIER[tier]
        return (len(nucleos) * len(self.frases["prefixos"][pool])
                * len(self.frases["sufixos"][pool]))

    # -------------------------------------------------------------- eventos
    def for_event(self, rng: random.Random, event: dict) -> str:
        # descompasso contextual (peso x forca) tem banco proprio
        method = event["evaluation"]
        if isinstance(method, dict):
            method = method.get("method")
        if method == "contextual" and event["roulette_id"] == "peso":
            if event["score"] <= 20:
                nucleo = self._pick(rng, self.frases["contextual"]["cant_lift"])
                nucleo = nucleo.replace("{VALUE}", event["display_value"])
                return self._compor(rng, nucleo, "TERRIBLE")
            if event["score"] >= 80:
                nucleo = self._pick(rng, self.frases["contextual"]["perfect_fit"])
                return self._compor(rng, nucleo, "INSANE")

        nucleo = self._pick(rng, self._nucleos(event["roulette_id"],
                                               BAND_BY_TIER[event["tier"]]))
        nucleo = (nucleo
                  .replace("{CATEGORY}", event["category"])
                  .replace("{VALUE}", event["display_value"]))
        return self._compor(rng, nucleo, event["tier"])

    # ----------------------------------------------------------- torneio
    def torneio_hook(self, rng: random.Random, quantidade: int) -> str:
        return self._pick(rng, self.frases["torneio"]["hook"]).replace(
            "{N}", str(quantidade))

    def torneio_card(self, rng: random.Random, luta: dict) -> str:
        banco = self.frases["torneio"]
        if luta.get("favorito") and rng.random() < 0.4:
            texto = self._pick(rng, banco["card_favorito"]).replace(
                "{FAV}", luta["favorito"])
        else:
            texto = self._pick(rng, banco["card"])
        return texto.replace("{P1}", luta["p1"]).replace("{P2}", luta["p2"])

    def torneio_resultado(self, rng: random.Random, luta: dict) -> str:
        banco = self.frases["torneio"]
        marcas = [m for m in luta.get("marcas", []) if m in banco["marcas"]]
        # uma marca especial (zebra, virada, duplo KO...) rouba a cena
        if marcas and rng.random() < 0.75:
            nucleo = self._pick(rng, banco["marcas"][rng.choice(marcas)])
        else:
            nucleo = self._pick(rng, banco["resultado"][BAND_BY_TIER[luta["tier"]]])
        nucleo = (nucleo
                  .replace("{VENCEDOR}", luta["vencedor"])
                  .replace("{PERDEDOR}", luta["perdedor"])
                  .replace("{DURACAO}", str(luta["duracao"]))
                  .replace("{HP}", str(luta["hp_vencedor"])))
        return self._compor(rng, nucleo, luta["tier"])

    def torneio_campeao(self, rng: random.Random, torneio: dict) -> str:
        banco = self.frases["torneio"]["campeao"]
        hp_medio = torneio.get("estatisticas", {}).get("hp_medio_campeao", 0)
        if hp_medio >= 60:
            pool = banco["dominante"]
        elif hp_medio and hp_medio <= 25:
            pool = banco["sofrido"]
        else:
            pool = banco["gerado"] if torneio.get("campeao_gerado") else banco["banco"]
        return (self._pick(rng, pool)
                .replace("{CAMPEAO}", str(torneio.get("campeao", "???")))
                .replace("{HP}", str(hp_medio)))

    # ------------------------------------------------------- demais telas
    def hook(self, rng: random.Random, pedido: dict | None = None) -> str:
        """Gancho de abertura; anuncia o nome pedido quando existe um."""
        nome = (pedido or {}).get("nome") or ""
        if not nome:
            return self._pick(rng, self.config["hook"])
        return self._pick_pedido(rng, "hook_pedido", self.config["hook"],
                                 {"{NOME_PEDIDO}": nome})

    def stinger(self, rng: random.Random, entity: str) -> str:
        """Batida curta de virada entre as roletas do personagem e as da arma.

        Existe para o corte nao ficar seco: sem ela o video passa do clipe do
        personagem direto para uma roleta laranja, e o espectador leva meio
        segundo para entender que comecou outra metade.
        """
        banco = self.config.get("stinger", {})
        pool = banco.get(entity) or ["AGORA A ARMA"]
        return self._pick(rng, pool)

    def outro(self, rng: random.Random, pedido: dict | None = None) -> str:
        """CTA do fim: convida o espectador a pedir o proprio personagem.

        Nao fala mais em seed. Seed e detalhe de reproducao do pipeline e nao
        oferece nada que o espectador queira pedir; um nome, sim.
        """
        pedido = pedido or {}
        nome = pedido.get("nome") or ""
        autor = pedido.get("autor") or ""
        if not nome:
            return self._pick(rng, self.config["outro"])
        if autor:
            return self._pick_pedido(
                rng, "outro_pedido_autor", self.config["outro"],
                {"{AUTOR}": autor, "{NOME_PEDIDO}": nome})
        return self._pick_pedido(rng, "outro_pedido", self.config["outro"],
                                 {"{NOME_PEDIDO}": nome})

    def nameplate_pedido(self, rng: random.Random) -> str:
        """Linha de credito sob o nome na placa do clipe do personagem.

        E o unico lugar em que o credito aparece por cima da revelacao: o
        renderer desenha a placa, nunca a `caption` do evento identity.
        """
        pool = self.config.get("nameplate_pedido") or []
        return self._pick(rng, pool) if pool else ""

    def for_reveal(self, rng: random.Random, kind: str, name: str) -> str:
        key = "reveal_character" if kind == "character" else "reveal_weapon"
        return self._pick(rng, self.config[key]).replace("{NAME}", name.upper())

    def for_identity(self, rng: random.Random, personagem: dict,
                     pedido: dict | None = None) -> str:
        """Legenda do clipe de identidade visual (Digen)."""
        nome_pedido = (pedido or {}).get("nome") or ""
        if nome_pedido:
            return self._pick_pedido(rng, "identity_pedido",
                                     self.config["identity"],
                                     {"{NOME_PEDIDO}": nome_pedido})
        return (self._pick(rng, self.config["identity"])
                .replace("{NAME}", str(personagem.get("nome", "")).upper())
                .replace("{CLASSE}", str(personagem.get("classe", "")).upper()))

    def for_synergy(self, rng: random.Random, compatibility: dict) -> str:
        score = compatibility["compatibility_score"]
        if score >= 70:
            pool = self.config["synergy"]["positive"]
        elif score <= 40:
            pool = self.config["synergy"]["negative"]
        else:
            pool = self.config["synergy"]["neutral"]
        return self._pick(rng, pool)

    def for_final(self, rng: random.Random, build: dict) -> str:
        pool = self.config["final_by_verdict"][build["verdict"]]
        return self._pick(rng, pool).replace("{SCORE}", str(build["final_score"]))
