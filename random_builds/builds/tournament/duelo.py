"""O DUELO: a luta inteira em 20-35 s, sem nenhuma cena parada.

Por que este formato existe
---------------------------
Medido em 11/09/2026, com a primeira coleta de retencao real do canal:

    build    18 videos  28,1% de retencao media  19,4 s vistos de 74 s
    estreia  12 videos   3,4% de retencao media   3,3 s vistos de 103 s
                         (MEDIANA ZERO: metade nao e assistida por ninguem)

E a curva do unico video com amostra suficiente (143 views, 53 s) mostra
onde a audiencia morre: 86% aos 8,5 s, 60% aos 11,1 s depois de tres roletas
seguidas, e 18,6% quando a LUTA finalmente comeca, aos 50,9 s. O produto
chega a menos de um quinto de quem abriu o video.

O numero que decide o desenho deste formato nao e nenhum desses: e que o
publico entrega ~20 SEGUNDOS a este canal, e isso ja e a media do formato
que vai melhor. Um video de 25-30 s e assistido quase inteiro pela mesma
audiencia que abandona um de 74 s na metade.

O que o duelo e
---------------
UM evento de gameplay. Nao ha gancho, card, titulo de round, reacao nem
outro — nenhuma cena em que o jogo esteja parado. O que seria cena vira
SOBREPOSICAO no proprio clipe da luta:

    identidade  ~1,5 s iniciais: quem e quem, por cor e nome;
    hud         barras de vida e plano, o mesmo de sempre;
    callouts    PARRY!, COMBO x4, K.O., o mesmo de sempre;
    veredito    ~1,2 s finais: quem ganhou, sobre o ultimo frame.

Deriva de `FightTimelineBuilder` para MENOS: reusa `evento_gameplay` e
`planejar_callouts` deste mesmo modulo. Nada e copiado — ha teste cobrando
que o duelo nao tem timeline propria de gameplay.

Escopo: build, estreia e torneio NAO mudam. O duelo e publicado ao lado
deles e a comparacao decide qual vence (Onda 15E).
"""
from __future__ import annotations

import random

from ..content.caption_generator import CaptionGenerator
from .timeline import evento_gameplay


class DueloTimelineBuilder:
    """Monta o `edit_plan.json` do duelo: um unico evento de gameplay."""

    def __init__(self, editing_config: dict, captions: CaptionGenerator):
        self.config = editing_config
        self.captions = captions

    @property
    def _cfg(self) -> dict:
        return self.config.get("duelo") or {}

    def build(self, rng: random.Random, fight: dict) -> dict:
        # O duelo e sempre UMA luta. Numa serie, o round que fechou — mas a
        # politica do formato e `melhor_de=1`, entao na pratica e a unica.
        rounds = list(fight.get("lutas") or [fight["luta"]])
        luta = rounds[-1]

        evento = evento_gameplay(rng, luta, self.config, self.captions)
        if evento is None:
            raise ValueError(
                "duelo sem clipe gravado: o formato E a luta, entao nao ha "
                "o que montar sem ela (o build, esse sim, cai para roleta)")

        duracao = max(float(c["duracao"]) for c in (luta.get("clipes") or {}).values())
        evento["start"] = 0.0
        evento["duration"] = round(duracao, 3)
        # Semana 1 do plano (20/10/2026): a faixa do topo diz o CONFRONTO pela
        # arma, a luta inteira, cada lado na cor do seu lutador — o mesmo
        # rotulo do titulo. Carimbado no fight (o controller regrava o
        # fight.json depois da edicao), entao titulo e faixa nunca divergem.
        from ..publicar import confronto
        confronto.carimbar(fight)
        lado1, lado2 = confronto.da_luta(luta)
        evento["confronto"] = {"p1": lado1, "p2": lado2}
        evento["identidade"] = self._identidade(luta, duracao)
        evento["veredito"] = self._veredito(luta, duracao)
        # Sem `caption`: legenda de cena e coisa de cena, e aqui nao ha cena.
        # O que o espectador le esta desenhado sobre o jogo.
        evento["caption"] = ""
        self._em_ingles(evento, luta)

        return {
            "generation_id": fight.get("duelo_id", fight.get("fight_id", "duelo")),
            "seed": fight["seed"],
            "kind": "duelo",
            "total_duration": round(duracao, 3),
            "events": [evento],
        }

    # ------------------------------------------------------------- ingles
    def _em_ingles(self, evento: dict, luta: dict) -> None:
        """Tudo o que o duelo ESCREVE na tela, em ingles (decisao
        `geral/canal-em-ingles`, 20/10/2026), pelo mapa de `ingles.py`:
        classe e cartel da identidade, selo, callouts, plano do HUD e o tipo
        de K.O. do veredito. Os nomes proprios ficam. O `luta` (que vai para
        o fight.json) nao e tocado: a serie do plano e copiada antes."""
        from ..publicar import ingles
        evento["idioma"] = "en"
        ident = evento.get("identidade") or {}
        for slot in ("p1", "p2"):
            lado = ident.get(slot)
            if isinstance(lado, dict):
                # o epiteto do nome so na exibicao ("Helga the Protector")
                lado["nome"] = ingles.nome(lado.get("nome"))
                lado["classe"] = ingles.classe(lado.get("classe"))
                lado["cartel"] = ingles.cartel(lado.get("cartel"))
        if ident.get("selo"):
            nome, seq = "", 0
            for slot in ("p1", "p2"):
                s = ((luta.get(f"{slot}_recorde") or {}).get("sequencia") or 0)
                if s >= 3:
                    nome, seq = ingles.nome(luta.get(slot) or ""), int(s)
                    break
            ident["selo"] = ingles.selo(ident["selo"], nome, seq)
        ver = evento.get("veredito") or {}
        if ver:
            # O cartao final RESPONDE a pergunta do quadro 0 ("WHO WINS?"):
            # "SHURIKEN WINS!", pelo rotulo do confronto do vencedor; o nome
            # do personagem vai pequeno embaixo (conferente, 20/10/2026).
            rotulo = evento.get("confronto") or {}
            vencedor_pt = ver.get("vencedor") or ""
            slot = ("p1" if vencedor_pt and vencedor_pt == luta.get("p1")
                    else "p2" if vencedor_pt and vencedor_pt == luta.get("p2") else "")
            if slot and rotulo.get(slot):
                ver["titulo"] = ingles.vence(rotulo[slot])
            ver["vencedor"] = ingles.nome(vencedor_pt)
            ver["ko_type"] = ingles.ko(ver.get("ko_type"))
            ver["cartel_apos"] = ingles.cartel(ver.get("cartel_apos"))
        hud = evento.get("hud")
        if isinstance(hud, dict):
            for slot in ("p1", "p2"):
                if hud.get(slot):
                    hud[slot] = ingles.nome(hud[slot])
        modelos = ((self.config.get("fight_callouts") or {}).get("textos") or {})
        for callout in evento.get("callouts") or []:
            tipo = str(callout.get("tipo") or "")
            callout["texto"] = ingles.callout(
                str(callout.get("texto") or ""), tipo, modelos.get(tipo),
                n=callout.get("n"), rotulo_pt=callout.get("rotulo"))
            if callout.get("rotulo"):
                callout["rotulo"] = ingles.plano(callout["rotulo"])
        if isinstance(hud, dict) and hud.get("serie_plano"):
            hud["serie_plano"] = [
                [a[0], ingles.plano(a[1]), a[2], ingles.plano(a[3]), *a[4:]]
                if len(a) >= 5 else list(a)
                for a in hud["serie_plano"]]

    # ------------------------------------------------------------ overlays
    def _identidade(self, luta: dict, duracao: float) -> dict:
        """Quem e quem, nos primeiros segundos, SEM parar a luta.

        A referencia do genero resolve identidade em meio segundo porque a
        bola E a identidade ("a vermelha da espada"). Aqui o equivalente
        barato e cor + nome + arma sobre o proprio jogo. O ledger (cartel,
        revanche, titulo) entra nesta mesma caixa na 15D.
        """
        from ..publicar import confronto
        ate = float(self._cfg.get("identidade_s", 1.5))
        saida = {
            "ate": round(min(ate, duracao * 0.25), 3),
            "p1": self._lado(luta, "p1"),
            "p2": self._lado(luta, "p2"),
            # Semana 1 (20/10/2026): a arma subiu para a faixa do topo, entao
            # a linha de identidade volta a dizer QUEM e (nome · classe ·
            # cartel), e a pergunta ("WHO WINS?", o canal e em ingles) fica
            # escrita desde o quadro 0 (6 de 12 canais que cresceram
            # perguntam; os 6 abertos quadro a quadro mostram o confronto ja
            # no quadro 0).
            "primeiro": "nome",
            "pergunta": str(self._cfg.get("pergunta", confronto.PERGUNTA) or ""),
        }
        # Onda 15D: a CARREIRA na tela. O ledger tem 61 lutas registradas e
        # `FightSession._carreira` ja injetava cartel, revanche e titulo no
        # evento desde a onda 9 — o renderer nunca leu nenhum campo. Era o
        # unico motivo para o espectador querer o proximo video, guardado
        # num arquivo que ninguem ve.
        selo = self._selo(luta)
        if selo:
            saida["selo"] = selo
        return saida

    @staticmethod
    def _selo(luta: dict) -> str:
        """A frase curta que diz por que ESTE confronto importa.

        Um selo so, e o mais forte: dois avisos competindo no mesmo segundo
        nao sao lidos. Titulo ganha de revancha porque cinturao em jogo vale
        mais que historico.
        """
        if luta.get("titulo"):
            return "TITULO EM JOGO"
        if luta.get("revanche"):
            return "REVANCHE"
        for slot in ("p1", "p2"):
            seq = ((luta.get(f"{slot}_recorde") or {}).get("sequencia") or 0)
            if seq >= 3:
                return f"{luta.get(slot, '')} VEM DE {seq} SEGUIDAS".strip()
        return ""

    def _veredito(self, luta: dict, duracao: float) -> dict:
        """O desfecho sobre o ultimo frame — nunca um cartao depois dele.

        Um cartao de resultado e uma cena parada no exato momento em que o
        espectador ja decidiu ficar ate o fim: e onde o formato antigo
        gastava 2,5 s para dizer o que a tela ja mostrou.
        """
        dur = float(self._cfg.get("veredito_s", 1.2))
        dur = min(dur, max(0.4, duracao * 0.2))
        return {
            "de": round(max(0.0, duracao - dur), 3),
            "vencedor": luta.get("vencedor") or "",
            "ko_type": luta.get("ko_type") or "",
            # O numero que MUDOU e o gancho do proximo video: "5V-0D" diz
            # que existe uma sequencia em risco. O cartel de antes ja
            # apareceu na abertura; repeti-lo aqui nao acrescenta nada.
            "cartel_apos": self._cartel_apos(luta),
        }

    @staticmethod
    def _cartel_apos(luta: dict) -> str:
        """Cartel do vencedor JA CONTANDO esta luta.

        O ledger so registra o duelo depois da renderizacao (`controller.
        duelo`), entao o recorde que chega aqui e o de ANTES. Somar a
        vitoria na mao e mais barato e mais previsivel que inverter a ordem
        do pipeline — e o registro continua acontecendo uma vez so.
        """
        vencedor = luta.get("vencedor")
        if not vencedor:
            return ""
        slot = "p1" if luta.get("p1") == vencedor else "p2"
        recorde = luta.get(f"{slot}_recorde") or {}
        if not recorde:
            return ""
        return f"{int(recorde.get('vitorias', 0)) + 1}V-{int(recorde.get('derrotas', 0))}D"

    @staticmethod
    def _lado(luta: dict, slot: str) -> dict:
        """O que da para dizer de um lutador em meio segundo de leitura.

        A ficha da luta tem `nome_arma` (o nome proprio, "Iskimantr") mas
        NAO o tipo ("Reta", "Arco"). Identidade por TIPO de arma — que e o
        que a referencia do genero usa, com glifo — depende do glifo por
        tipo que a 15C traz; ate la o nome da arma e o que existe.
        """
        ficha = luta.get(f"{slot}_ficha") or {}
        return {
            "nome": luta.get(slot) or "",
            "arma": ficha.get("nome_arma") or "",
            "classe": ficha.get("classe") or "",
            # Cartel vazio quando o lutador estreia: "0V-0D" ocuparia a
            # linha para dizer que nao ha historia nenhuma.
            "cartel": (luta.get(f"{slot}_cartel") or "").replace("0V-0D", ""),
        }
