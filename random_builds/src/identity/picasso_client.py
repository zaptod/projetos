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
from datetime import datetime, timezone
from pathlib import Path

from . import config as iconfig
from . import proveniencia
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
        # O texto que ENTROU no campo e quando: e contra isso que o historico
        # e conferido na prova de origem (o aprimorador pode reescrever).
        self.prompt_enviado: str | None = None
        self.enviado_em: datetime | None = None
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
        # Page/contexto morto tem que virar BrowserMorreu AQUI: deixado para
        # o goto, o erro generico do Playwright ("Target ... has been
        # closed") caia no handler comum do worker e QUEIMAVA as tentativas
        # de todos os jobs seguintes contra uma aba defunta (26/08/2026:
        # 00044 e 00055 esgotaram assim em segundos). BrowserMorreu encerra
        # a passada e a proxima abre um Chrome limpo sem contar falha.
        self._checar_vivo()
        if self.page.url != alvo:
            try:
                self.page.goto(alvo, wait_until="domcontentloaded",
                               timeout=int(float(
                                   self.ajustes.get("navigation_timeout", 60)) * 1000))
            except Exception as exc:
                if "closed" in str(exc).lower():
                    raise BrowserMorreu(
                        "a aba/contexto do Chrome morreu ao navegar: "
                        f"{str(exc)[:120]}")
                raise
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

        prompt = self._aprimorar(campo, botao, prompt)

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
        try:
            botao.click(timeout=10000)
        except Exception:
            # O clique interceptado pelo modal de auth e a unica retomada
            # legitima; qualquer outra causa deve estourar como sempre.
            if not self._resolver_dialogo_de_auth():
                raise
            botao.click()
        self.prompt_enviado = prompt
        self.enviado_em = datetime.now(timezone.utc)
        self.url_do_espaco = self.page.url
        print(f"[picasso] prompt enviado ({len(prompt)} chars), "
              f"{len(antes)} imagem(ns) ja na tela")
        return antes



    def _resolver_dialogo_de_auth(self) -> bool:
        """Se o modal de login abriu no meio do fluxo, loga por ele.

        O cookie do Picasso expira, mas o criador continua aparecendo para
        visitante anonimo - entao `sessao_viva` diz "valida" e o fluxo segue
        ate o PRIMEIRO clique que exige conta (o aprimorador, o gerar), quando
        um dialogo de auth cobre a pagina e intercepta todo clique. Detectar
        aqui e logar pelo proprio modal e o unico ponto que ve a expiracao.
        """
        campo = self.page.locator("#auth-card-email")
        try:
            if not campo.count() or not campo.first.is_visible():
                return False
        except Exception:
            return False
        credenciais = iconfig.load_credentials("picasso")
        if credenciais is None:
            raise GeracaoFalhou(
                "o Picasso pediu login no meio do fluxo e nao ha "
                "picasso_credentials.json para responder.")
        print("[picasso] a sessao expirou no meio do fluxo; "
              "logando pelo modal...")
        campo.first.fill(credenciais["email"])
        pausa_humana(self.rng, 0.3, 0.8)
        senha = self.page.locator("div[role='dialog'] input[type='password']")
        senha.first.fill(credenciais["password"])
        pausa_humana(self.rng, 0.3, 0.8)
        botao = self.page.locator("div[role='dialog'] button[type='submit']")
        if not botao.count():
            botao = self.page.get_by_role("button", name="Entrar")
        botao.first.click()
        limite = time.monotonic() + 30
        while time.monotonic() < limite:
            time.sleep(0.5)
            try:
                if not campo.count() or not campo.first.is_visible():
                    print("[picasso] login pelo modal concluido.")
                    time.sleep(1.5)
                    return True
            except Exception:
                return True
        raise GeracaoFalhou(
            "o modal de login do Picasso nao fechou depois de preencher as "
            "credenciais; provavel senha rejeitada ou desafio anti-bot.")

    def _aprimorar(self, campo, botao_gerar, original: str) -> str:
        """Roda o Aprimorador de Prompt e devolve o texto que valeu.

        O botao NAO mexe no textarea: ele abre um painel "PROMPT ANTIGO ->
        NOVO PROMPT" com o texto novo chegando em streaming, e a aplicacao
        depende de um botao que vive coberto por popup de promocao. Por isso
        o caminho aqui e outro: esperar o streaming ESTABILIZAR, colher o
        texto do painel e preencher o campo por conta propria - nenhum clique
        em botao tapado. Se o painel nao abrir ou vier vazio, segue com o
        original: aprimorar e otimizacao, nao pode derrubar o job.
        """
        if not self.ajustes.get("aprimorar_prompt", False):
            return original
        try:
            botao = selectors.resolver(self.page, selectors.BOTAO_APRIMORAR,
                                       "o aprimorador de prompt")
        except Exception:
            print("[picasso] aprimorador de prompt nao encontrado; "
                  "seguindo com o prompt original")
            return original
        botao.click()
        pausa_humana(self.rng, 1.0, 2.0)
        if self._resolver_dialogo_de_auth():
            botao.click()

        rotulo = self.page.get_by_text("NOVO PROMPT", exact=False)
        try:
            rotulo.first.wait_for(state="visible", timeout=15000)
        except Exception:
            print("[picasso] o painel do aprimorador nao abriu; "
                  "seguindo com o prompt original")
            return original

        painel = rotulo.first.locator("xpath=..")
        limite = time.monotonic() + float(
            self.ajustes.get("aprimorar_timeout", 60))
        texto, estaveis = "", 0
        while time.monotonic() < limite:
            time.sleep(1.0)
            self._checar_vivo()
            try:
                atual = painel.inner_text()
            except Exception:
                atual = ""
            if atual == texto and len(atual) > 60:
                estaveis += 1
                if estaveis >= 2:
                    break
            else:
                texto, estaveis = atual, 0

        # O painel trunca a exibicao; "Mostrar mais" revela o resto.
        try:
            mais = self.page.get_by_text("Mostrar mais", exact=False)
            if mais.count() and mais.first.is_visible():
                mais.first.click()
                time.sleep(0.5)
                texto = painel.inner_text()
        except Exception:
            pass

        novo = self._texto_do_painel(texto)
        if len(novo) < 60:
            print("[picasso] o aprimorador nao entregou texto no prazo; "
                  "seguindo com o prompt original")
            return original

        # Fecha o painel antes de mexer no campo; ele nao pode ficar por cima.
        try:
            cancelar = self.page.get_by_text("Cancelar", exact=False)
            if cancelar.count() and cancelar.first.is_visible():
                cancelar.first.click()
                time.sleep(0.5)
        except Exception:
            pass
        campo.fill(novo)
        print(f"[picasso] prompt aprimorado ({len(original)} -> "
              f"{len(novo)} chars)")
        return novo

    @staticmethod
    def _texto_do_painel(bruto: str) -> str:
        """Tira do innerText do painel so o prompt: fora rotulos e botoes."""
        rotulos = {"novo prompt:", "prompt antigo:", "mostrar mais",
                   "mostrar menos", "copiar", "cancelar", "usar este prompt"}
        linhas = []
        for linha in (bruto or "").splitlines():
            limpa = linha.strip()
            if not limpa or limpa.lower() in rotulos:
                continue
            linhas.append(limpa)
        return " ".join(" ".join(linhas).split())

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

    # ----------------------------------------------------------------- origem
    def comprovar_origem(self, alvo, prompt: str, enviado_em=None) -> dict:
        """Prova FORTE: o card do Historico que traz o NOSSO prompt.

        `alvo` e o que `wait_for_render` devolveu - a primeira imagem nova em
        retrato. Numa conta compartilhada isso nao basta: em generation_00044
        essa "nova" era a foto de outra pessoa, que entrou no historico 0,1 s
        depois do clique. O Historico (`?tab=history`) mostra cada geracao da
        conta com o prompt inteiro e a data; o card com o prompt que enviamos
        e o nosso, e a imagem DELE e a que vale - se for outra que nao `alvo`,
        `alvo` e descartado. Se o card existe mas ainda esta sem imagem, e a
        nossa geracao que nao terminou: espera-se por ela, nao pela primeira
        que aparecer.

        Devolve sempre um dict (ver proveniencia.py); falta de prova nao
        levanta. Levanta SeletorNaoEncontrado se o painel do historico sumiu:
        isso e deploy do site, e a passada tem que parar e avisar.
        """
        ajustes = proveniencia.ajustes(self.ajustes)
        limite = int(ajustes["cards_inspecionados"])
        tolerancia = float(ajustes["tolerancia_data_min"])
        intervalo = max(2.0, float(self.ajustes.get("poll_interval", 3)))
        url = selectors.url_historico(self.url_do_espaco or self.page.url)
        # O historico abre numa ABA PROPRIA e a pagina do EDITOR fica parada
        # onde esta: navegar a aba do editor ~2 s depois do clique MATAVA a
        # geracao em voo (o anexo e um blob daquela pagina), o card nunca
        # nascia e a prova esperava 240 s por nada — visto em 26/08/2026: a
        # mesma cena, observada sem navegar, gerou e cardou em ~105 s.
        try:
            aba = self.ctx.new_page()
        except Exception as exc:
            if "closed" in str(exc).lower():
                raise BrowserMorreu(
                    f"o contexto do Chrome morreu ao abrir a aba do "
                    f"historico: {str(exc)[:120]}")
            raise
        try:
            aba.goto(url, wait_until="domcontentloaded",
                     timeout=int(float(
                         self.ajustes.get("navigation_timeout", 60)) * 1000))
            esperar_hidratacao(aba,
                               float(self.ajustes.get("hydration_timeout", 45)))
            selectors.resolver(aba, selectors.PAINEL_HISTORICO,
                               "o painel do historico (?tab=history)")
            return self._vigiar_historico(aba, ajustes, limite, tolerancia,
                                          intervalo, alvo, prompt, enviado_em)
        finally:
            try:
                aba.close()
            except Exception:
                pass

    def _vigiar_historico(self, aba, ajustes, limite, tolerancia, intervalo,
                          alvo, prompt, enviado_em) -> dict:
        """O loop da prova, rodando numa aba dedicada ao historico."""

        # Os cards do Editor Pro nao mostram DATA (conferido no DOM em
        # 26/08/2026), e o prompt da juncao e o MESMO entre tentativas da
        # mesma build — sem esta guarda, o card de ONTEM da propria build
        # (inclusive um ja quarentenado) casaria de novo e a prova baixaria
        # a imagem velha. Imagem ja reivindicada (origens.jsonl, por QUALQUER
        # build) nunca prova de novo: a tentativa atual exige imagem nova.
        vetadas = set(proveniencia.reivindicadas())

        def _cards_sem_vetadas():
            brutos = selectors.cards_do_historico(aba, limite)
            return [dict(card_bruto,
                         imagens=[u for u in card_bruto["imagens"]
                                  if u not in vetadas])
                    for card_bruto in brutos]

        fim = time.monotonic() + float(ajustes["espera_historico_s"])
        motivo = "o historico nao carregou"
        avisou = time.monotonic()
        while True:
            self._checar_vivo()
            if aba.is_closed():
                raise BrowserMorreu("a aba do historico foi fechada.")
            cards = _cards_sem_vetadas()
            escolha = proveniencia.escolher_card(cards, prompt, enviado_em,
                                                 tolerancia)
            card = escolha["card"]
            if card is not None and not card["imagens"]:
                # Imagem lazy: so ganha URL quando o card entra na tela.
                selectors.cards_do_historico(aba, limite,
                                             revelar=card["indice"])
                time.sleep(1.0)
                cards = _cards_sem_vetadas()
                escolha = proveniencia.escolher_card(cards, prompt, enviado_em,
                                                     tolerancia)
                card = escolha["card"]
            if card is not None and card["imagens"]:
                prova = proveniencia.prova_forte(
                    selectors.PROVEDOR, card, card["imagens"][0], alvo,
                    prompt, enviado_em)
                if prova["candidato_descartado"]:
                    print("[picasso] a imagem que apareceu primeiro NAO e a do "
                          "nosso prompt; vale a do card do historico.")
                else:
                    print(f"[picasso] origem comprovada: o card "
                          f"{card['indice'] + 1} do historico traz o prompt.")
                return prova
            motivo = (escolha["motivo"] if card is None
                      else "o card com o nosso prompt ainda esta sem imagem")
            if time.monotonic() >= fim:
                break
            if time.monotonic() - avisou >= 20:
                avisou = time.monotonic()
                print(f"[picasso] esperando o historico confirmar a origem... "
                      f"({motivo})", flush=True)
            time.sleep(intervalo)
        return proveniencia.sem_prova(selectors.PROVEDOR, motivo, alvo, prompt,
                                      enviado_em)

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
