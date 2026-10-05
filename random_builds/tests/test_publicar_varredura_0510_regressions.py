# -*- coding: utf-8 -*-
"""A varredura de erros de 05/10/2026, lado dos publicadores (navegador).

- Item 3: `tiktok._abrir` e `youtube_web._abrir` faziam UM `page.goto` de
  90 s. Entre 23:44 e 00:00 de 04/10 caiu o 23:37 inteiro (4 envios), e as
  09:42, 09:48 e 09:51 de 05/10 o TikTok de `generation_00102` e da
  `historia_00042 p06`, com o YouTube publicando no mesmo minuto. Agora:
  2a e 3a tentativa em aba nova com `wait_until="commit"`, e o erro final
  diz "infraestrutura" (que `desfecho.classificar` nao conta contra o video).
- Item 5: o editor do TikTok come o trecho que chega colado ao Enter (h34
  p06, 00:39 de 05/10; telas `_213926`/`_213929`). Pausa depois de cada Enter
  e da limpeza, tres tentativas, e a legenda so depois do envio a 100%.
- Item 19: o laudo gravava o CABECALHO do dialogo (`texto[:200]`): nas 13
  publicacoes com estagio "desconhecida" desde 16/09 a frase do rodape nunca
  foi vista. Agora so o rodape classifica e vai ao laudo, e o ultimo estagio
  legivel vai ao laudo e ao diario — mas NAO decide o clique: `desconhecida`
  no estouro publica (regra de 16/09; o conferente achou a 1a entrega
  segurando o video, o que teria custado o YouTube de 8 publicacoes reais).
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from builds.identity import browser
from builds.publicar import desfecho, escrita, tiktok, youtube_web


class _Aba:
    """Aba falsa: `goto` falha as primeiras `falhas` vezes (no contexto)."""

    def __init__(self, ctx, nome):
        self.ctx, self.nome = ctx, nome
        self.url = "about:blank"
        self.ouvintes = []

    def goto(self, url, wait_until="load", timeout=0):
        self.ctx.chamadas.append((self.nome, wait_until, timeout))
        if self.ctx.falhas > 0:
            self.ctx.falhas -= 1
            raise TimeoutError(f"Timeout {timeout}ms exceeded.\n"
                               f"navigating to \"{url}\"")
        self.url = url

    def on(self, evento, funcao):
        self.ouvintes.append((evento, funcao))

    def close(self):
        self.ctx.pages.remove(self)
        self.ctx.fechadas.append(self.nome)


class _Ctx:
    def __init__(self, falhas=0):
        self.falhas = falhas
        self.chamadas = []
        self.fechadas = []
        self.pages = [_Aba(self, "restaurada")]

    def new_page(self):
        aba = _Aba(self, f"nova{len(self.pages)}")
        self.pages.append(aba)
        return aba


# ------------------------------------------------------------------ item 3
class AbrirComNovasTentativasTests(unittest.TestCase):
    def test_primeira_falha_e_a_segunda_abre_em_aba_nova(self):
        ctx, pausas = _Ctx(falhas=1), []
        aba = browser.abrir_pagina(ctx, "https://x", dormir=pausas.append)
        self.assertEqual("nova1", aba.nome)
        self.assertEqual([("restaurada", "domcontentloaded", 90_000),
                          ("nova1", "commit", 60_000)], ctx.chamadas)
        self.assertEqual([browser.PAUSA_ENTRE_ABERTURAS_S], pausas)

    def test_caso_zero_nada_falha_e_a_aba_de_sempre(self):
        ctx = _Ctx()
        aba = browser.abrir_pagina(ctx, "https://x", dormir=lambda s: None)
        self.assertEqual("restaurada", aba.nome)
        self.assertEqual(1, len(ctx.chamadas))
        self.assertEqual(1, len(ctx.pages), "nenhuma aba a mais")

    def test_todas_falham_levanta_com_a_causa_de_cada_uma(self):
        ctx = _Ctx(falhas=99)
        with self.assertRaises(browser.AberturaFalhou) as caso:
            browser.abrir_pagina(ctx, "https://x", dormir=lambda s: None)
        self.assertEqual(browser.TENTATIVAS_DE_ABERTURA, len(ctx.chamadas))
        self.assertIn("1a: TimeoutError", str(caso.exception))
        self.assertIn("3a: TimeoutError", str(caso.exception))

    def test_aba_que_falhou_e_fechada(self):
        """Conferente, 05/10 (Chrome real, prazo de 1 ms): 3 falhas deixavam
        4 abas, e a travada seguia como `ctx.pages[0]` para a proxima rodada.
        Agora: sucesso na 2a deixa so a aba boa; 3 falhas deixam uma aba so.
        """
        ctx = _Ctx(falhas=1)
        aba = browser.abrir_pagina(ctx, "https://x", dormir=lambda s: None)
        self.assertEqual([aba], ctx.pages)
        self.assertEqual(["restaurada"], ctx.fechadas)
        self.assertIs(aba, browser.pagina(ctx), "a proxima rodada pega a boa")

        ctx = _Ctx(falhas=99)
        with self.assertRaises(browser.AberturaFalhou):
            browser.abrir_pagina(ctx, "https://x", dormir=lambda s: None)
        self.assertEqual(1, len(ctx.pages), "nunca sem aba, nunca 4 abas")
        self.assertEqual(["restaurada", "nova1"], ctx.fechadas)

    def test_new_page_que_falha_nao_fecha_a_unica_aba(self):
        ctx = _Ctx(falhas=1)

        def quebra():
            raise RuntimeError("Target closed")
        ctx.new_page = quebra
        with self.assertRaises(browser.AberturaFalhou):
            browser.abrir_pagina(ctx, "https://x", dormir=lambda s: None)
        self.assertEqual(["restaurada"], [a.nome for a in ctx.pages])
        self.assertEqual([], ctx.fechadas)

    def test_ir_para_tenta_de_novo_na_MESMA_aba(self):
        """O Studio pendura um ouvinte na aba antes do goto: aba nova o perde."""
        ctx = _Ctx(falhas=1)
        aba = ctx.pages[0]
        self.assertIs(aba, browser.ir_para(aba, "https://x",
                                           dormir=lambda s: None))
        self.assertEqual(["restaurada", "restaurada"],
                         [c[0] for c in ctx.chamadas])
        self.assertEqual("commit", ctx.chamadas[1][1])

    def test_tiktok_diz_infraestrutura_e_o_desfecho_entende(self):
        ctx = _Ctx(falhas=99)
        with patch.object(browser.time, "sleep", lambda s: None), \
                self.assertRaises(tiktok.TikTokFalhou) as caso:
            tiktok._abrir(ctx, tiktok.URL_UPLOAD)
        texto = str(caso.exception)
        self.assertTrue(texto.startswith("infraestrutura"))
        falha = {"tipo": "TikTokFalhou", "mensagem": texto}
        self.assertEqual("infraestrutura", desfecho.classificar("", falha),
                         "timeout de abertura nao e defeito do video")

    def test_youtube_diz_infraestrutura(self):
        ctx = _Ctx(falhas=99)
        with patch.object(browser.time, "sleep", lambda s: None), \
                self.assertRaises(youtube_web.YouTubeWebFalhou) as caso:
            youtube_web._abrir(ctx, youtube_web.URL_STUDIO)
        self.assertTrue(str(caso.exception).startswith("infraestrutura"))

    def test_tiktok_abre_na_segunda(self):
        ctx = _Ctx(falhas=1)
        with patch.object(browser.time, "sleep", lambda s: None):
            aba = tiktok._abrir(ctx, tiktok.URL_UPLOAD)
        self.assertEqual(tiktok.URL_UPLOAD, aba.url)


# ------------------------------------------------------------------ item 5
class _Teclado:
    def __init__(self, campo):
        self.campo, self.eventos = campo, []

    def press(self, tecla):
        self.eventos.append(("tecla", tecla))
        if tecla == "Delete":
            self.campo.texto = ""
        elif tecla == "Enter":
            self.campo.texto += "\n"

    def insert_text(self, texto):
        self.eventos.append(("colar", texto))
        self.campo.texto += texto

    def type(self, texto, delay=0):
        self.eventos.append(("digitar", texto))
        self.campo.texto += texto


class _CampoQueComeOEnter:
    """O editor do TikTok: o trecho que chega SEM pausa depois do Enter some.

    `pausas` e preenchido pelo `dormir` do teste: o trecho seguinte so entra
    se houve uma pausa desde o ultimo Enter — o defeito medido em 05/10.
    """

    def __init__(self):
        self.texto = ""
        self.cliques = 0

    def click(self):
        self.cliques += 1

    def inner_text(self):
        return self.texto


class _PaginaDoEditor:
    def __init__(self, campo):
        self.campo = campo
        self.keyboard = _Teclado(campo)


LEGENDA_H34_P06 = (
    "A Merenda\n\nParte 6 de 6 — as outras estão no canal, na ordem.\n\n"
    "Eu escrevo e conto essas histórias aqui. Os personagens e os nomes "
    "são invenção minha.\n\nO que você faria no lugar dele?\n\n#historias "
    "#relatos #reddit #storytime #shorts")


class PausaDepoisDoEnterTests(unittest.TestCase):
    def test_uma_pausa_depois_da_limpeza_e_de_cada_enter(self):
        campo = _CampoQueComeOEnter()
        pagina, pausas = _PaginaDoEditor(campo), []
        escrita.escrever(pagina, campo, LEGENDA_H34_P06, colar=False,
                         dormir=pausas.append)
        enters = LEGENDA_H34_P06.count("\n")
        self.assertEqual(8, enters)
        self.assertEqual(1 + enters, len(pausas))
        self.assertTrue(all(p == escrita.PAUSA_DEPOIS_DO_ENTER_S
                            for p in pausas))
        self.assertEqual(LEGENDA_H34_P06, campo.texto)

    def test_a_pausa_vem_ANTES_do_trecho_seguinte(self):
        campo = _CampoQueComeOEnter()
        pagina, ordem = _PaginaDoEditor(campo), []
        teclado = pagina.keyboard
        original = teclado.press

        def press(tecla):
            original(tecla)
            ordem.append(tecla)
        teclado.press = press
        escrita.escrever(pagina, campo, "linha 1\nlinha 2", colar=True,
                         dormir=lambda s: ordem.append("pausa"))
        self.assertEqual(["Control+A", "Delete", "pausa", "Enter", "pausa"],
                         ordem)

    def test_pausa_zero_nao_dorme(self):
        campo = _CampoQueComeOEnter()
        pausas = []
        escrita.escrever(_PaginaDoEditor(campo), campo, "a\nb", pausa_s=0,
                         dormir=pausas.append)
        self.assertEqual([], pausas)


class TresTentativasDaLegendaTests(unittest.TestCase):
    def setUp(self):
        original = tiktok._primeiro
        tiktok._primeiro = lambda page, sel, timeout=0: page.campo
        self.addCleanup(setattr, tiktok, "_primeiro", original)
        dormir = escrita.DORMIR
        escrita.DORMIR = lambda s: None
        self.addCleanup(setattr, escrita, "DORMIR", dormir)
        fotografar = escrita.fotografar
        escrita.fotografar = lambda page, rotulo, **k: ""
        self.addCleanup(setattr, escrita, "fotografar", fotografar)

    def test_os_tres_modos_em_ordem(self):
        self.assertEqual(["digitada", "colada", "digitada lenta"],
                         [m for m, _ in tiktok.MODOS_DA_LEGENDA])

    def test_a_terceira_salva_quando_as_duas_primeiras_perdem_texto(self):
        class Teimoso(_CampoQueComeOEnter):
            def __init__(self):
                super().__init__()
                self.vezes = 0

            def click(self):
                super().click()
                self.vezes += 1

            def inner_text(self):
                # As duas primeiras escritas perdem o paragrafo do meio.
                if self.vezes < 3:
                    return self.texto.replace("Eu escrevo", "")
                return self.texto
        campo = Teimoso()
        laudo, passos = {}, []
        ok = tiktok._escrever_legenda(_PaginaDoEditor(campo), LEGENDA_H34_P06,
                                      passos.append, laudo)
        self.assertTrue(ok)
        self.assertEqual("digitada lenta", laudo["legenda_modo"])
        self.assertEqual(3, campo.cliques)
        self.assertIn("3a tentativa", passos[-1])


class EnvioA100Tests(unittest.TestCase):
    class _Tela:
        def __init__(self, textos):
            self.textos = list(textos)

        def evaluate(self, _js):
            return self.textos.pop(0) if len(self.textos) > 1 else self.textos[0]

    def test_leituras(self):
        self.assertTrue(tiktok._envio_concluido(
            self._Tela(["final_celular_p06.mp4 1080P\nEnviado (60.85MB)"])))
        self.assertFalse(tiktok._envio_concluido(
            self._Tela(["final_celular_p06.mp4\nEnviando... 45%"])))
        self.assertIsNone(tiktok._envio_concluido(self._Tela(["Detalhes"])))
        # Um "0%" solto (sem a palavra do envio) nao segura a legenda.
        self.assertIsNone(tiktok._envio_concluido(
            self._Tela(["Verificacao de direitos autorais 0%"])))

    def test_enviado_com_parentese_de_largura_cheia(self):
        """Conferente, 05/10: na captura `20261004_213926` o rotulo e
        "Enviado （60.85MB）" (U+FF08). O NFD nao dobra esse parentese, e o
        sinal "enviado (" nunca casava: a espera so terminava pela porcentagem.
        """
        for rotulo in ("Enviado （60.85MB）",
                       "Enviado（60.85MB）",
                       "Enviado (60.85MB)", "Enviado(60.85MB)",
                       "Uploaded (12MB)"):
            self.assertTrue(tiktok._envio_concluido(
                self._Tela([f"final_celular_p06.mp4 1080P\n{rotulo}"])),
                rotulo)
        # "reenviado (" nao e o rotulo do arquivo, e "enviado" sem parentese
        # tambem nao (a tela diz "enviado" em outros lugares).
        self.assertIsNone(tiktok._envio_concluido(
            self._Tela(["video reenviado (2)"])))
        self.assertIsNone(tiktok._envio_concluido(
            self._Tela(["comentario enviado"])))

    def test_espera_a_porcentagem_e_sai_no_enviado(self):
        tela = self._Tela(["Enviando 12%", "Enviando 80%",
                           "Enviado (60.85MB)"])
        relogio = [0.0]
        estado = tiktok._esperar_envio(
            tela, lambda _t: None, espera=120,
            dormir=lambda s: relogio.__setitem__(0, relogio[0] + s),
            relogio=lambda: relogio[0])
        self.assertTrue(estado)
        self.assertEqual(4.0, relogio[0], "duas esperas de 2 s")

    def test_tela_que_nao_diz_nao_segura_ninguem(self):
        """Caso zero: sem porcentagem nem "Enviado", segue na hora."""
        dormiu = []
        estado = tiktok._esperar_envio(self._Tela([""]), lambda _t: None,
                                       dormir=dormiu.append)
        self.assertIsNone(estado)
        self.assertEqual([], dormiu)

    def test_porcentagem_parada_tem_teto(self):
        relogio = [0.0]
        estado = tiktok._esperar_envio(
            self._Tela(["Enviando 45%"]), lambda _t: None, espera=10,
            dormir=lambda s: relogio.__setitem__(0, relogio[0] + s),
            relogio=lambda: relogio[0])
        self.assertFalse(estado)
        self.assertLessEqual(relogio[0], 12.0)


# ----------------------------------------------------------------- item 19
# O dialogo de uma publicacao REAL com estagio ilegivel (duelo_00041, 04/10,
# 18:10, como o laudo o gravou): cabecalho com titulo e estado do rascunho.
CABECALHO = ("silas o sombrio x kael ventotabuleiro\nsalvo como privado\n"
             "detalhes\nelementos do video\nverificacao inicial\nvisibilidade\n"
             "visibilidade\nescolha quando publicar e quem podera ver seu "
             "video\n\nsalvar ou publicar\n")


class SoORodapeClassificaTests(unittest.TestCase):
    def test_o_laudo_grava_o_rodape_e_nao_o_cabecalho(self):
        texto = CABECALHO + ("torne o video publico\n" * 3
                             + "verificando direitos autorais\n"
                             "6 minutos restantes\nconcluir")
        fim = youtube_web._classificar_rodape(texto)
        self.assertEqual("desconhecida", fim["qualidade"])
        self.assertIn("verificando direitos autorais", fim["texto"],
                      "a frase que falta em FASES tem de aparecer")
        self.assertIn("6 minutos restantes", fim["texto"])
        self.assertNotIn("silas o sombrio", fim["texto"])
        self.assertEqual("contagem", fim["escopo"])

    def test_salvando_do_rascunho_no_cabecalho_nao_e_upload(self):
        """17/09: "salvando..." no CABECALHO virava "subindo"."""
        texto = ("titulo\nsalvando...\ndetalhes\n" + "x\n" * 80
                 + "processando ate hd 2 minutos restantes")
        fim = youtube_web._classificar_rodape(texto)
        self.assertEqual("sd", fim["qualidade"])

    def test_frase_de_fase_no_titulo_nao_classifica(self):
        texto = ("enviando cartas a um estranho (parte 1/6)\nsalvo como "
                 "privado\n" + "y\n" * 120 + "verificacoes concluidas\n"
                 "3 minutos restantes")
        fim = youtube_web._classificar_rodape(texto)
        self.assertNotEqual("subindo", fim["qualidade"])

    def test_rodape_pelo_seletor_manda(self):
        fim = youtube_web._classificar_rodape(
            CABECALHO, "processando ate sd ... 3 minutos restantes")
        self.assertEqual("processando", fim["qualidade"])
        self.assertEqual("rodape", fim["escopo"])

    def test_seletor_que_pegou_so_os_botoes_nao_esconde_o_processamento(self):
        """Se o seletor do rodape devolver o elemento errado, a contagem do
        dialogo ainda manda: publicar 'hd' processando seria o pior erro."""
        texto = CABECALHO + "processando ate sd\n3 minutos restantes\nvoltar"
        fim = youtube_web._classificar_rodape(texto, "voltar salvar")
        self.assertEqual("processando", fim["qualidade"])

    def test_caso_zero_sem_contagem_nem_frase_e_hd(self):
        fim = youtube_web._classificar_rodape(CABECALHO)
        self.assertEqual("hd", fim["qualidade"])

    def test_pagina_que_devolve_texto_puro_ainda_funciona(self):
        class Pagina:
            def evaluate(self, _js):
                return "Processando até SD ... 3 minutos restantes"
        self.assertEqual("processando",
                         youtube_web._qualidade_agora(Pagina())["qualidade"])

    def test_pagina_que_devolve_dialogo_e_rodape(self):
        class Pagina:
            def evaluate(self, _js):
                return {"dialogo": CABECALHO + "Envio concluído",
                        "rodape": "Envio concluído. O processamento vai "
                                  "começar em breve"}
        self.assertEqual("subindo",
                         youtube_web._qualidade_agora(Pagina())["qualidade"])


class HerdaOUltimoEstagioTests(unittest.TestCase):
    class _Relogio:
        def __init__(self):
            self.agora = 1000.0

        def monotonic(self):
            return self.agora

        def sleep(self, s):
            self.agora += s

    def _rodar(self, estagios, limite):
        restantes = list(estagios)
        relogio, diario, laudo = self._Relogio(), [], {}

        def ler(_page):
            return dict(restantes.pop(0) if len(restantes) > 1
                        else restantes[0])
        with patch.object(youtube_web, "_qualidade_agora", ler), \
                patch.object(youtube_web.time, "sleep", relogio.sleep), \
                patch.object(youtube_web.time, "monotonic",
                             relogio.monotonic), \
                patch.object(youtube_web.atividade, "registrar",
                             lambda *a, **k: diario.append((a, k))):
            fim = youtube_web._esperar_qualidade(
                None, lambda _t: None, laudo, limite_s=limite)
        return fim, laudo, diario

    @staticmethod
    def _e(qualidade, reconhecido=True, texto=""):
        return {"qualidade": qualidade, "falta": "3 minutos restantes",
                "texto": texto, "reconhecido": reconhecido,
                "escopo": "contagem"}

    def test_ilegivel_depois_de_processando_PUBLICA_no_estouro(self):
        """A regra de 16/09 vale: `desconhecida` no estouro publica.

        Conferente, 05/10: 1a leitura "Processando video... 8 minutos
        restantes", as seguintes uma frase nova com "6 minutos restantes".
        A 1a entrega herdava 'processando' ate o clique e NAO publicava;
        nos ledgers, 8 publicacoes reais (historias 2 processando + 1
        subindo, builds 5 subindo) teriam perdido o YouTube assim. O ultimo
        estagio legivel fica so no laudo e no diario.
        """
        fim, laudo, diario = self._rodar(
            [self._e("processando"),
             self._e("desconhecida", False, "frase nova 3 minutos restantes")],
            limite=30.0)
        self.assertEqual("desconhecida", fim["qualidade"])
        self.assertFalse(youtube_web._nao_publicar_ainda(fim),
                         "ilegivel no estouro publica (regra de 16/09)")
        self.assertEqual("desconhecida", laudo["qualidade_no_clique"])
        self.assertEqual("processando", laudo["ultimo_estagio_legivel"])
        self.assertEqual(1, len(diario), "o rodape ilegivel vai ao diario")
        mensagem = diario[0][0][2]
        self.assertIn("frase nova", mensagem)
        self.assertIn("publiquei assim mesmo", mensagem)
        self.assertIn("'processando'", mensagem)

    def test_caso_do_conferente_pelo_dialogo_de_verdade(self):
        """O mesmo caso, passando pelo `_qualidade_agora` real (sem dublê
        do classificador): o HEAD de 05/10 publicava, a 1a entrega nao."""
        leituras = (
            [{"dialogo": "titulo x\nsalvo como privado\n...\n"
                         "Processando video... 8 minutos restantes",
              "rodape": ""}]
            + [{"dialogo": "titulo x\nsalvo como privado\n...\n"
                           "Frase nova do Studio 6 minutos restantes",
                "rodape": ""}] * 50)

        class Pagina:
            def evaluate(self, _js):
                return leituras.pop(0) if len(leituras) > 1 else leituras[0]
        relogio, laudo = self._Relogio(), {}
        with patch.object(youtube_web.time, "sleep", relogio.sleep), \
                patch.object(youtube_web.time, "monotonic",
                             relogio.monotonic), \
                patch.object(youtube_web.atividade, "registrar",
                             lambda *a, **k: None):
            fim = youtube_web._esperar_qualidade(
                Pagina(), lambda _t: None, laudo, limite_s=30.0)
        self.assertEqual("processando", laudo["qualidade_ao_habilitar"])
        self.assertEqual("desconhecida", fim["qualidade"])
        self.assertFalse(youtube_web._nao_publicar_ainda(fim))
        self.assertTrue(laudo["estourou_a_espera"])

    def test_sem_leitura_reconhecida_antes_continua_desconhecida(self):
        fim, laudo, diario = self._rodar(
            [self._e("desconhecida", False)], limite=30.0)
        self.assertEqual("desconhecida", fim["qualidade"])
        self.assertNotIn("ultimo_estagio_legivel", laudo)
        self.assertFalse(youtube_web._nao_publicar_ainda(fim))
        self.assertIn("publiquei assim mesmo", diario[0][0][2])

    def test_processando_legivel_no_estouro_continua_sem_publicar(self):
        """O outro lado: 'processando' LIDO AGORA ainda segura o clique."""
        fim, laudo, diario = self._rodar([self._e("processando")],
                                         limite=30.0)
        self.assertTrue(youtube_web._nao_publicar_ainda(fim))
        self.assertNotIn("ultimo_estagio_legivel", laudo)
        self.assertEqual([], diario)

    def test_leitura_nova_reconhecida_encerra_a_espera(self):
        fim, laudo, _ = self._rodar(
            [self._e("processando"), self._e("desconhecida", False),
             self._e("hd", True)], limite=300.0)
        self.assertEqual("hd", fim["qualidade"])
        self.assertNotIn("ultimo_estagio_legivel", laudo)


if __name__ == "__main__":
    unittest.main()
