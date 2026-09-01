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
# Import direto e de proposito - builds.character.nomes so puxa unicodedata, e um
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

        # Atributo ESCOLHIDO nao usa o banco por tier: as frases de la reagem
        # ao sorteio ("a roleta escolheu", "isso ja e sorte") e o `_compor`
        # ainda empilha um "olha isso!" por cima. Comemorar sorte num valor
        # que foi digitado e mentira — e a frase diz que foi escolha.
        if event.get("escolhido"):
            pool = self.frases.get("escolhido")
            if pool:
                return (self._pick(rng, pool)
                        .replace("{CATEGORY}", event["category"])
                        .replace("{VALUE}", event["display_value"]))

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

    # ------------------------------------------------------------- luta
    @staticmethod
    def _sub_luta(texto: str, luta: dict) -> str:
        nome = str(luta.get("estreia_de") or luta.get("p1") or "")
        return (texto
                .replace("{P1}", str(luta.get("p1", "")))
                .replace("{P2}", str(luta.get("p2", "")))
                .replace("{NOME}", nome)
                .replace("{VENCEDOR}", str(luta.get("vencedor", "")))
                .replace("{PERDEDOR}", str(luta.get("perdedor", "")))
                .replace("{R1}", str(luta.get("p1_cartel", "")))
                .replace("{R2}", str(luta.get("p2_cartel", ""))))

    def luta_hook(self, rng: random.Random, luta: dict) -> str:
        """Gancho do video de luta unica: estreia, revanche, titulo ou duelo.

        A luta carrega o proprio contexto (`origem`, `revanche`, `titulo`);
        o banco `luta` em frases.json tem um pool por contexto e cai no pool
        generico quando o contexto nao tem frase.
        """
        banco = self.frases.get("luta") or {}
        generico = banco.get("hook") or self.frases["torneio"]["card"]
        if luta.get("origem") == "estreia" and luta.get("estreia_de"):
            pool = banco.get("hook_estreia") or generico
        elif luta.get("titulo") and banco.get("hook_titulo"):
            pool = banco["hook_titulo"]
        elif luta.get("revanche") and banco.get("hook_revanche"):
            pool = banco["hook_revanche"]
        else:
            pool = generico
        return self._sub_luta(self._pick(rng, pool), luta)

    def luta_card(self, rng: random.Random, luta: dict) -> str:
        """Card VS: com cartel dos dois quando existe carreira registrada."""
        banco = self.frases.get("luta") or {}
        tem_cartel = luta.get("p1_cartel") and luta.get("p2_cartel")
        if tem_cartel and banco.get("card_recorde") and rng.random() < 0.6:
            return self._sub_luta(self._pick(rng, banco["card_recorde"]), luta)
        return self.torneio_card(rng, luta)

    @staticmethod
    def _placar(valores) -> str:
        valores = list(valores or [])
        return " x ".join(str(v) for v in valores) if len(valores) == 2 else ""

    def _sub_serie(self, texto: str, luta: dict, placar=None) -> str:
        return (self._sub_luta(texto, luta)
                .replace("{PLACAR}", self._placar(
                    placar if placar is not None else luta.get("placar")))
                .replace("{ROUND}", str(luta.get("round", "")))
                .replace("{DURACAO}", str(luta.get("duracao", "")))
                .replace("{HP}", str(luta.get("hp_vencedor", ""))))

    def luta_round(self, rng: random.Random, luta: dict,
                   usados: set | None = None) -> str:
        """Resultado de UM round da serie.

        Voz propria de proposito: com tres rounds, reusar o pool de resultado
        do torneio faria o mesmo video dizer "vitoria de X" tres vezes.

        `usados` guarda as FRASES-MODELO ja sorteadas nesta serie e sai daqui
        atualizado: num pool pequeno, tres sorteios independentes repetem com
        facilidade, e a repeticao aparece porque as telas ficam a segundos uma
        da outra. Esgotado o pool, o sorteio volta a ser livre.
        """
        pool = (self.frases.get("luta") or {}).get("resultado_round")
        if not pool:
            return self.torneio_resultado(rng, luta)
        livres = [f for f in pool if f not in (usados or ())] or list(pool)
        escolhido = self._pick(rng, livres)
        if usados is not None:
            usados.add(escolhido)
        return self._sub_serie(escolhido, luta)

    def luta_serie(self, rng: random.Random, luta: dict, placar) -> str:
        """Veredito da serie: o placar decide a frase, nao o ultimo round."""
        banco = (self.frases.get("luta") or {}).get("resultado_serie") or {}
        valores = sorted(placar or [], reverse=True)
        varreu = len(valores) == 2 and valores[1] == 0
        pool = banco.get("varreu" if varreu else "apertada") or banco.get("apertada")
        if not pool:
            return self.torneio_resultado(rng, luta)
        return self._sub_serie(self._pick(rng, pool), luta, placar)

    def luta_outro(self, rng: random.Random, luta: dict) -> str:
        banco = self.frases.get("luta") or {}
        if luta.get("origem") == "estreia" and luta.get("estreia_de"):
            pool = banco.get("outro_estreia") or banco.get("outro") or self.config["outro"]
        else:
            pool = banco.get("outro") or self.config["outro"]
        return self._sub_luta(self._pick(rng, pool), luta)

    def callout(self, rng: random.Random, tipo: str, textos: dict,
                n: int | None = None, rotulo: str | None = None) -> str:
        """Texto curto sincronizado com um evento narrativo do motor."""
        pool = textos.get(tipo) or [tipo.upper()]
        texto = self._pick(rng, pool).replace("{N}", str(n if n is not None else ""))
        # Onda 10C: {ROTULO} e o rotulo do plano ("PRESSAO", "ISCA"...).
        return texto.replace("{ROTULO}", str(rotulo or "PLANO"))

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
    def hook(self, rng: random.Random, pedido: dict | None = None,
             escolhas: dict | None = None) -> str:
        """Gancho de abertura; anuncia o nome pedido quando existe um.

        Com atributo ESCOLHIDO em vez de sorteado, o pool neutro sai de cena:
        as frases dele afirmam "100% aleatorio" e "nada escolhido", e abrir um
        video com isso depois de fixar a classe seria mentira dita na primeira
        linha. O pool `hook_escolhido` conta a verdade — parte foi escolhida,
        o resto a roleta decide.
        """
        nome = (pedido or {}).get("nome") or ""
        if nome:
            return self._pick_pedido(rng, "hook_pedido", self.config["hook"],
                                     {"{NOME_PEDIDO}": nome})
        if escolhas:
            pool = self.config.get("hook_escolhido")
            if pool:
                return self._pick(rng, pool)
        return self._pick(rng, self.config["hook"])

    def hook_payoff(self, rng: random.Random, pedido: dict | None = None,
                    escolhas: dict | None = None) -> str:
        """Gancho por cima da IMAGEM do personagem pronto.

        O nome pedido continua vencendo (e o credito que rende comentario);
        sem pedido, o pool `hook_payoff` fala do que a tela mostra — um
        personagem que a roleta montou — em vez de um slogan sobre a roleta.
        """
        nome = (pedido or {}).get("nome") or ""
        if nome:
            return self._pick_pedido(rng, "hook_pedido", self.config["hook"],
                                     {"{NOME_PEDIDO}": nome})
        pool = self.config.get("hook_payoff") or None
        if pool:
            return self._pick(rng, pool)
        return self.hook(rng, pedido, escolhas)

    def hook_absurdo(self, rng: random.Random, roll: dict) -> str:
        """Gancho pela rolagem mais absurda: abre pelo que vai dar assunto."""
        pool = self.config.get("hook_absurdo") or ["SAIU {VALUE} DE {CATEGORY}"]
        return (self._pick(rng, pool)
                .replace("{CATEGORY}", str(roll.get("category", "")).upper())
                .replace("{VALUE}", str(roll.get("display_value", ""))))

    def stakes(self, rng: random.Random, roll: dict) -> str:
        """O que esta em jogo nesta roleta, mostrado DURANTE o giro.

        Tensao antes do resultado: sem isso a roda gira sobre um "?" e o
        espectador nao sabe por que deveria se importar com o que vai cair.
        """
        banco = self.frases.get("stakes") or {}
        pool = banco.get(roll.get("roulette_id")) or banco.get("_default")
        if not pool:
            return ""
        return self._pick(rng, pool)

    def outro_com_estreia(self, rng: random.Random,
                          pedido: dict | None = None) -> str:
        """CTA do fim quando a luta apareceu: convida para a estreia inteira.

        Com nome pedido, o credito de sempre vence — e o que rende o proximo
        comentario.
        """
        if (pedido or {}).get("nome"):
            return self.outro(rng, pedido)
        pool = self.config.get("outro_com_estreia")
        return self._pick(rng, pool) if pool else self.outro(rng, pedido)

    def stinger(self, rng: random.Random, entity: str) -> str:
        """Batida curta de virada entre as roletas do personagem e as da arma.

        Existe para o corte nao ficar seco: sem ela o video passa do clipe do
        personagem direto para uma roleta laranja, e o espectador leva meio
        segundo para entender que comecou outra metade.
        """
        banco = self.config.get("stinger", {})
        pool = banco.get(entity) or {"luta": ["HORA DA VERDADE"]}.get(entity) or ["AGORA A ARMA"]
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
