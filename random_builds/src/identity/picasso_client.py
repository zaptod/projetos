"""PicassoClient: prompt -> imagem gerada -> arquivo no disco.

O fluxo, levantado do site real em 24/08/2026:

  1. `/pt/collection/text-to-image/picassoia-image` — logado, a pagina da
     colecao E o criador.
  2. Proporcao e quantidade sao <select> NATIVOS: `select_option`, nunca
     clique (uma <option> nao e "visivel" e o clique estoura em timeout).
  3. Prompt no `textarea#prompt`. O `#submit-button` nasce desabilitado e so
     habilita quando ha texto — e essa virada que confirma que o prompt entrou.
  4. A imagem pronta e servida direto de um bucket publico
     (`pub-*.r2.dev/text-to-image/<uid>/<modelo>/<uuid>.jpg`), entao nao existe
     nem faz falta botao de download: com a URL, `ctx.request.get` baixa
     reusando os cookies da sessao.

A interface e a MESMA do DigenClient (o worker usa por duck typing): mudam os
metodos por dentro, nao os nomes.
"""
from __future__ import annotations

import time
from pathlib import Path

from . import picasso_selectors as selectors
from .browser import esperar_hidratacao, pausa_humana
from .client import BrowserMorreu, EsperaEstourou, GeracaoFalhou

# Uma imagem de recompensa e vertical. Se o que apareceu e deitado, e quase
# certo que seja miniatura do historico carregada tarde — e nao a nossa
# geracao. Confundir as duas gravaria a imagem errada como personagem.
TOLERANCIA_RETRATO = 1.02


class PicassoClient:
    def __init__(self, ctx, page, ajustes: dict, rng=None,
                 ao_descobrir_espaco=None):
        self.ctx = ctx
        self.page = page
        self.ajustes = ajustes
        import random
        self.rng = rng or random.Random()
        # Nao existe "espaco" aqui: cada geracao e independente e a pagina e
        # sempre a mesma. O atributo existe porque o worker o consulta.
        self.url_do_espaco: str | None = None
        self.presets_aplicados: dict = {}
        self._ao_descobrir_espaco = ao_descobrir_espaco

    # -------------------------------------------------------------- creditos
    def creditos(self, espera: float = 0.0) -> int | None:
        """None de proposito: este modelo e ilimitado e o botao diz GRATIS.

        Devolver 0 faria o worker abortar a rodada por "sem creditos"; devolver
        um numero inventado seria pior. None significa "nao ha contador para
        ler", que e a verdade.
        """
        return None

    def _modelo_atual(self) -> str | None:
        try:
            botao = self.page.locator('button:has-text("picassoia image")')
            if botao.count():
                return " ".join((botao.first.inner_text() or "").split())
        except Exception:
            pass
        return None

    # --------------------------------------------------------------- pagina
    def abrir_espaco(self, url: str | None = None) -> None:
        """Volta para o criador. Retomada aqui e so recarregar a pagina."""
        alvo = url or selectors.URL_CRIACAO
        self.url_do_espaco = alvo
        if self.page.url != alvo:
            self.page.goto(alvo, wait_until="domcontentloaded",
                           timeout=int(float(
                               self.ajustes.get("navigation_timeout", 60)) * 1000))
            esperar_hidratacao(self.page,
                               float(self.ajustes.get("hydration_timeout", 45)))
            pausa_humana(self.rng, 1.0, 2.0)

    def preparar_espaco(self, espaco: str | None) -> list[str]:
        """Mesma assinatura do Digen. Devolve a foto do que ja esta na tela."""
        self.abrir_espaco(espaco)
        return self._resultados()

    def _esperar_estabilizar(self, quieto: float = 4.0,
                             teto: float = 25.0) -> list[str]:
        """Espera a lista de resultados ficar parada e devolve a foto dela."""
        fim = time.monotonic() + teto
        atual = self._resultados()
        estavel_desde = time.monotonic()
        while time.monotonic() < fim:
            time.sleep(1.0)
            agora = self._resultados()
            if set(agora) != set(atual):
                atual, estavel_desde = agora, time.monotonic()
                continue
            if time.monotonic() - estavel_desde >= quieto:
                break
        print(f"[picasso] {len(atual)} resultado(s) ja na tela (lista estavel)")
        return atual

    def _resultados(self) -> list[str]:
        return [i["src"] for i in selectors.resultados_na_tela(self.page)]

    def anexar_referencias(self, caminhos) -> list:
        """Sobe as imagens de entrada do Editor Pro. NUNCA levanta.

        Aqui, ao contrario do Digen, o formulario aceita VARIAS (verificado na
        tela: subir personagem e depois arma deixou as duas). Por isso o teto e
        o tamanho da lista, e nao 1.
        """
        if not caminhos:
            return []
        from . import referencias
        prontos = [referencias.para_upload(Path(c)) for c in caminhos]
        anexadas = referencias.anexar(self.page, prontos, selectors, self.rng,
                                      maximo=len(prontos))
        print(f"[picasso] {len(anexadas)} imagem(ns) de entrada no editor")
        return anexadas

    # ------------------------------------------------------------ controles
    def _ajustar_select(self, nome: str, valor: str) -> str | None:
        """Escolhe no <select> e CONFERE o que ficou.

        Mesma doutrina do Digen: setar sem conferir entrega a geracao errada
        com o custo ja pago. Aqui custa menos (a geracao e gratis), mas o
        prejuizo e o mesmo — a imagem sai deitada e o video inteiro fica torto.
        """
        alvo = selectors.select_com_opcao(self.page, valor)
        if alvo is None:
            print(f"[picasso] nao achei o controle de {nome}; "
                  "seguindo com o padrao da pagina.")
            return None
        try:
            atual = alvo.input_value()
            if atual == valor:
                print(f"[picasso] {nome} ja em {valor}.")
                return atual
            alvo.select_option(valor)
            pausa_humana(self.rng, 0.3, 0.8)
            virou = alvo.input_value()
        except Exception as exc:
            raise GeracaoFalhou(
                f"nao consegui ajustar {nome} para {valor!r}: {str(exc)[:120]}")
        if virou != valor:
            raise GeracaoFalhou(
                f"pedi {nome} {valor!r} e o controle ficou em {virou!r}. "
                "Nao vou gerar com a imagem no formato errado.")
        print(f"[picasso] {nome} {atual} -> {virou}")
        return virou

    def presets_atuais(self) -> dict:
        def valor(chave):
            alvo = selectors.select_com_opcao(self.page, chave)
            try:
                return alvo.input_value() if alvo is not None else None
            except Exception:
                return None
        return {"modelo": self._modelo_atual(),
                "aspecto": valor("9:16"), "quantidade": valor("2")}

    # ------------------------------------------------------------- submissao
    def submit_prompt(self, prompt: str, aspect: str = "9:16",
                      modelo: str | None = None, duracao=None,
                      resolucao=None, espaco: str | None = None,
                      antes: list[str] | None = None) -> list[str]:
        """Envia o prompt e devolve a FOTO das imagens que ja estavam na tela.

        `duracao`, `resolucao` e `antes` sao aceitos e podem nao significar
        nada aqui: existem na assinatura porque o worker fala com os DOIS
        provedores pela mesma porta. Imagem nao tem duracao, e so o payoff
        precisa preparar a pagina antes (para anexar) — mas a porta tem que ser
        a mesma, senao ela derriça em silencio.
        """
        if antes is None:
            self.abrir_espaco(espaco)

        campo = selectors.resolver(self.page, selectors.CAMPO_PROMPT,
                                   "o campo de prompt (textarea#prompt)")
        campo.fill(prompt)
        pausa_humana(self.rng, 0.4, 1.0)

        botao = selectors.resolver(self.page, selectors.BOTAO_GERAR,
                                   "o botao de gerar (#submit-button)")
        limite = time.monotonic() + 20
        while botao.is_disabled() and time.monotonic() < limite:
            time.sleep(0.5)
        if botao.is_disabled():
            raise GeracaoFalhou(
                "o botao de gerar continuou desabilitado: o prompt nao entrou "
                "no textarea. Rode `python main.py identity probe --provedor "
                "picasso --url ...` para conferir o seletor.")

        self._ajustar_select("proporcao", aspect)
        quantidade = str(self.ajustes.get("quantidade", 1))
        if quantidade in selectors.OPCOES_QUANTIDADE:
            self._ajustar_select("quantidade", quantidade)
        self.presets_aplicados = self.presets_atuais()
        print("[picasso] presets: " + ", ".join(
            f"{k}={v}" for k, v in self.presets_aplicados.items()))
        if self.presets_aplicados.get("aspecto") not in selectors.ASPECTOS_VERTICAIS:
            raise GeracaoFalhou(
                f"a proporcao ficou em {self.presets_aplicados.get('aspecto')!r}, "
                "que nao e vertical. A imagem entraria deitada num video 9:16.")

        # A foto so vale depois que a lista PARA de crescer. Tirar no ultimo
        # instante antes do clique nao bastava: o historico da conta chega em
        # ondas, e uma imagem que aparece 2 s depois do clique parece nossa —
        # foi assim que o job da arma baixou a imagem do personagem.
        antes = self._esperar_estabilizar()
        pausa_humana(self.rng)
        botao.click()
        self.url_do_espaco = self.page.url
        print(f"[picasso] prompt enviado ({len(prompt)} chars), "
              f"{len(antes)} imagem(ns) ja na tela")
        return antes

    # ----------------------------------------------------------------- espera
    def _checar_vivo(self) -> None:
        if self.page.is_closed():
            raise BrowserMorreu("a aba do Chrome foi fechada durante a espera.")

    def wait_for_render(self, timeout: float | None = None,
                        antes: list[str] | None = None) -> str:
        """Espera a imagem nova aparecer e devolve a URL dela.

        DUAS guardas, e as duas sao necessarias: a URL tem que ser nova em
        relacao a foto, e a imagem tem que ser RETRATO. So a primeira nao
        basta — o historico da conta chega tarde e cada miniatura dele e uma
        URL "nova" que nunca esteve na foto. Foi exatamente assim que a
        primeira exploracao concluiu "pronto" em 5 s com uma imagem 1920x1088
        que ninguem tinha pedido.
        """
        timeout = float(timeout if timeout is not None
                        else self.ajustes.get("render_timeout", 300))
        intervalo = float(self.ajustes.get("poll_interval", 3))
        conhecidas = set(antes or [])
        inicio = time.monotonic()
        fim = inicio + timeout
        ultimo_aviso = 0.0

        while time.monotonic() < fim:
            self._checar_vivo()
            for imagem in selectors.resultados_na_tela(self.page):
                if imagem["src"] in conhecidas:
                    continue
                largura, altura = imagem.get("w") or 0, imagem.get("h") or 0
                if not (largura and altura):
                    # 0x0 = o <img> existe mas ainda nao decodificou. Aceitar
                    # aqui furaria a guarda de retrato justamente no instante
                    # em que ela nao pode ser aplicada; a proxima volta ja tem
                    # a medida. NAO entra em `conhecidas`: e para reavaliar.
                    continue
                if altura < largura * TOLERANCIA_RETRATO:
                    # Deitada: e miniatura do historico, nao a nossa. Entra na
                    # lista de conhecidas para nao ser reavaliada a cada volta.
                    conhecidas.add(imagem["src"])
                    continue
                print(f"[picasso] imagem pronta ({largura}x{altura}) em "
                      f"{time.monotonic() - inicio:.0f}s")
                return imagem["src"]
            decorrido = time.monotonic() - inicio
            if decorrido - ultimo_aviso >= 20:
                ultimo_aviso = decorrido
                print(f"[picasso] gerando... {decorrido:.0f}s", flush=True)
            time.sleep(intervalo)

        raise EsperaEstourou(
            f"a imagem nao ficou pronta em {timeout:.0f}s.")

    # --------------------------------------------------------------- download
    def download(self, alvo: str, dest: Path) -> Path:
        """Baixa a URL publica reusando os cookies do proprio browser.

        Nao ha botao de download nesta tela, e nao faz falta: `ctx.request` sai
        da mesma sessao, entao nada aqui precisa de `requests` — mesma razao
        pela qual o Digen tambem nao precisa.
        """
        dest.parent.mkdir(parents=True, exist_ok=True)
        resposta = self.ctx.request.get(
            alvo, timeout=float(self.ajustes.get("download_timeout", 120)) * 1000)
        if not resposta.ok:
            raise GeracaoFalhou(f"download de {alvo[:80]} respondeu {resposta.status}.")
        corpo = resposta.body()
        if len(corpo) < 512:
            raise GeracaoFalhou(
                f"download de {alvo[:80]} veio com {len(corpo)} bytes: nao e imagem.")
        # O bucket serve .jpg; o slot espera .png. Converter aqui mantem o
        # nome canonico do artefato sem espalhar excecao de formato pelo resto.
        if dest.suffix.lower() == ".png" and not corpo.startswith(b"\x89PNG"):
            from io import BytesIO
            from PIL import Image
            with Image.open(BytesIO(corpo)) as img:
                img.convert("RGB").save(dest)
        else:
            dest.write_bytes(corpo)
        print(f"[picasso] baixado -> {dest} ({dest.stat().st_size} bytes)")
        return dest
