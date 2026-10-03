# -*- coding: utf-8 -*-
"""Pedir imagem pelo correio (29/09/2026), com dublê: nenhum teste abre
navegador, toca o Telegram ou o `%LOCALAPPDATA%` real (`NF_IAS_PASTA`).

Cobre: o pedido no correio (forma, teto de 5.000, caso ZERO), o catalogo dos
geradores pela ficha (quem gera, quem nao e por que, proporcoes), o carteiro
gerando arquivo com prova (bytes originais), sem prova -> recusa sem nada no
disco, recusa de conteudo e cota -> motivo legivel, parede de planos reabre
uma vez, o rodizio escolhendo o livre (e esperando, e desistindo com os
motivos), a imagem na casa de um chat e o Telegram como documento.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from ias import carteiro as carteiro_mod, correio, imagem


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._antes = os.environ.get("NF_IAS_PASTA")
        os.environ["NF_IAS_PASTA"] = str(Path(self._tmp.name) / "ias")

    def tearDown(self):
        if self._antes is None:
            os.environ.pop("NF_IAS_PASTA", None)
        else:
            os.environ["NF_IAS_PASTA"] = self._antes
        self._tmp.cleanup()


@contextmanager
def _trava_livre(nome, esperar=0.0):
    yield True


class _TravasPorNome:
    """Travas que ficam OCUPADAS para os nomes dados (a pipeline com a conta)."""

    def __init__(self, ocupadas=(), soltar_depois=None):
        self.ocupadas = set(ocupadas)
        self.soltar_depois = soltar_depois
        self.pedidos = []

    @contextmanager
    def __call__(self, nome, esperar=0.0):
        self.pedidos.append(nome)
        if self.soltar_depois is not None and len(self.pedidos) > self.soltar_depois:
            self.ocupadas.clear()
        yield nome not in self.ocupadas


def _novo(fabrica_imagem=None, fabrica=None, **kw):
    avisos, documentos = [], []
    kw.setdefault("trava", _trava_livre)
    kw.setdefault("nome_da_trava", lambda ia: f"perfil__{ia}__teste")
    kw.setdefault("avisar", avisos.append)
    kw.setdefault("avisar_arquivo", lambda caminho, legenda: documentos.append(
        (Path(caminho), legenda)))
    kw.setdefault("log", lambda m: None)
    kw.setdefault("dormir", lambda s: None)
    ajustes = {"janela_conversa_s": 0, "resumo_a_cada": 50, "espera_conta_max_s": 100,
               "rodizio_imagem": ["picasso", "gemini", "grok", "chatgpt"],
               "cota_pausa_h": 6}
    ajustes.update(kw.pop("ajustes", {}))
    c = carteiro_mod.Carteiro(
        fabrica_de_sessao=fabrica or carteiro_mod.fabrica_duble(),
        fabrica_imagem=fabrica_imagem or imagem.fabrica_imagem_duble(),
        ajustes=ajustes, **kw)
    c.avisos, c.documentos = avisos, documentos
    return c


class ConteudoRecusado(Exception):
    """Mesmo nome da excecao do identity: o classificador olha o nome."""


class ParedeDePlanos(Exception):
    pass


# ================================================================ correio
class PedidoNoCorreio(_Base):
    def test_caso_zero(self):
        self.assertEqual(correio.imagens(), [])
        self.assertEqual(correio.ler("picasso"), [])
        self.assertEqual(correio.ler(correio.LIVRE), [])
        self.assertIsNone(correio.arquivo_da_imagem("picasso", "abcdef12"))
        self.assertIsNone(correio.proxima_pendente(correio.CAIXAS))
        self.assertEqual(imagem.fora_de_cota("picasso"), "")

    def test_pedido_entra_com_tipo_imagem(self):
        m = correio.pedir_imagem("picasso", "a red circle on white", proporcao="1:1")
        dobrada = correio.uma("picasso", m["id"])
        self.assertEqual(dobrada["tipo"], "imagem")
        self.assertEqual(dobrada["texto"], "a red circle on white")
        self.assertEqual(dobrada["proporcao"], "1:1")
        self.assertEqual(dobrada["gerador"], "picasso")
        self.assertEqual(dobrada["situacao"], "pendente")
        self.assertEqual(correio.tipo(dobrada), "imagem")
        livre = correio.pedir_imagem("livre", "x", proporcao="1:1")
        self.assertIsNone(livre["gerador"])
        # mensagem antiga (sem `tipo`) continua sendo texto
        self.assertEqual(correio.tipo({"texto": "oi"}), "texto")

    def test_pedido_invalido_recusa_com_motivo(self):
        with self.assertRaises(correio.CorreioInvalido):
            correio.pedir_imagem("deepseek", "x", proporcao="1:1")    # nao gera
        with self.assertRaises(correio.CorreioInvalido):
            correio.pedir_imagem("picasso", "   ", proporcao="1:1")
        with self.assertRaises(correio.CorreioInvalido) as erro:
            correio.pedir_imagem("picasso", "a" * 5001, proporcao="1:1")
        self.assertIn("5000", str(erro.exception))
        correio.pedir_imagem("picasso", "a" * 5000, proporcao="1:1")   # o teto entra
        with self.assertRaises(correio.CorreioInvalido):
            correio.pedir_imagem("picasso", "x", proporcao="")
        with self.assertRaises(correio.CorreioInvalido):
            correio.enviar("picasso", "oi")                            # texto nao

    def test_imagem_so_sai_de_pedido_registrado_e_respondido(self):
        m = correio.pedir_imagem("picasso", "x", proporcao="1:1")
        pasta = correio.pasta_imagens("picasso")
        pasta.mkdir(parents=True)
        (pasta / f"{m['id']}.png").write_bytes(imagem.png_de_teste())
        # pendente: nao serve, mesmo com o arquivo no disco
        self.assertIsNone(correio.arquivo_da_imagem("picasso", m["id"]))
        # respondida com um nome que nao e `<id>.<ext>`: nao serve
        correio.atualizar("picasso", m["id"], situacao="respondida",
                          imagem={"arquivo": "../../segredo.png"})
        self.assertIsNone(correio.arquivo_da_imagem("picasso", m["id"]))
        correio.atualizar("picasso", m["id"], imagem={"arquivo": "ffffffff.png"})
        self.assertIsNone(correio.arquivo_da_imagem("picasso", m["id"]))
        correio.atualizar("picasso", m["id"], imagem={"arquivo": f"{m['id']}.png"})
        self.assertEqual(correio.arquivo_da_imagem("picasso", m["id"]),
                         pasta / f"{m['id']}.png")
        # gerador trocado no registro para quem nao gera: nao serve
        correio.atualizar("picasso", m["id"], gerador="deepseek")
        self.assertIsNone(correio.arquivo_da_imagem("picasso", m["id"]))


# ================================================================ fichas
class GeradoresPelaFicha(unittest.TestCase):
    def test_quem_gera_hoje(self):
        por_ia = {g["ia"]: g for g in imagem.geradores()}
        self.assertEqual(set(por_ia), set(correio.GERADORES))
        self.assertNotIn("deepseek", por_ia)
        p = por_ia["picasso"]
        self.assertTrue(p["disponivel"])
        self.assertEqual(p["via"], "picasso")
        self.assertIn("1:1", p["proporcoes"])
        self.assertIn("9:16", p["proporcoes"])
        self.assertIn("Aprimorador desligado", p["nota"])
        for chat in ("grok", "gemini", "chatgpt"):
            self.assertTrue(por_ia[chat]["disponivel"], chat)
            self.assertEqual(por_ia[chat]["via"], "chat")
        # ChatGPT: medido em 29/09 17:16 (o gato do 0edfbdb5): a tela nao diz
        # mais "nao medido"
        self.assertNotIn("não medido", por_ia["chatgpt"]["nota"])

    def test_ficha_que_nao_mediu_diz_na_tela(self):
        original = imagem.fichas.carregar
        try:
            imagem.fichas.carregar = lambda ia: {"imagem": {"gera": None}}
            info = imagem.gerador("grok")
            self.assertTrue(info["disponivel"])
            self.assertIn("não medido", info["nota"])
        finally:
            imagem.fichas.carregar = original

    def test_quem_nao_gera_diz_por_que(self):
        por_ia = {g["ia"]: g for g in imagem.geradores()}
        d = por_ia["dreamface"]
        self.assertFalse(d["disponivel"])
        self.assertIn("créditos 0", d["motivo"])
        g = por_ia["digen"]
        self.assertFalse(g["disponivel"])
        self.assertTrue(g["proximo_passo"])
        self.assertIn("VÍDEO", g["motivo"])

    def test_ficha_que_diz_nao_gera_desabilita(self):
        original = imagem.fichas.carregar
        try:
            imagem.fichas.carregar = lambda ia: {"imagem": {"gera": False,
                                                            "prova_origem": {"motivo": "sem"}}}
            self.assertFalse(imagem.gerador("gemini")["disponivel"])
        finally:
            imagem.fichas.carregar = original

    def test_conferir_pedido(self):
        self.assertEqual(imagem.conferir_pedido("picasso", "1:1")["ia"], "picasso")
        with self.assertRaises(correio.CorreioInvalido) as erro:
            imagem.conferir_pedido("picasso", "5:7")
        self.assertIn("oferece", str(erro.exception))
        with self.assertRaises(correio.CorreioInvalido) as erro:
            imagem.conferir_pedido("dreamface", "1:1")
        self.assertIn("não gera imagem hoje", str(erro.exception))
        self.assertTrue(imagem.conferir_pedido("livre", "1:1")["disponivel"])


# ================================================================ carteiro
class CarteiroGeraImagem(_Base):
    def test_picasso_gera_arquivo_com_prova_e_manda_documento(self):
        corpo = imagem.png_de_teste(80, 80)
        fabrica = imagem.fabrica_imagem_duble(corpo=corpo)
        c = _novo(fabrica)
        m = correio.pedir_imagem("picasso", "a red circle on white", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(fim["gerador"], "picasso")
        self.assertIn("imagem pronta", fim["resposta"])
        info = fim["imagem"]
        self.assertEqual(info["arquivo"], f"{m['id']}.png")
        self.assertEqual((info["largura"], info["altura"]), (80, 80))
        alvo = correio.arquivo_da_imagem("picasso", m["id"])
        # BYTES ORIGINAIS: nada recomprimido
        self.assertEqual(alvo.read_bytes(), corpo)
        prova = json.loads((alvo.parent / f"{m['id']}.prova.json").read_text("utf-8"))
        self.assertEqual(prova["prova"]["metodo"], "duble")
        self.assertEqual(prova["bytes"], len(corpo))
        sessao = fabrica.criadas[0]
        self.assertEqual(sessao.pedidos[0]["proporcao"], "1:1")
        self.assertEqual(sessao.reivindicadas, [m["id"]])      # a URL fica nossa
        self.assertEqual(len(c.documentos), 1)
        self.assertEqual(c.documentos[0][0], alvo)
        self.assertIn("a red circle", c.documentos[0][1])
        self.assertEqual(c.avisos, [])
        self.assertEqual(correio.imagens("picasso")[0]["id"], m["id"])
        self.assertIsNone(c.uma_volta())

    def test_sem_prova_recusa_e_nada_vai_ao_disco(self):
        c = _novo(imagem.fabrica_imagem_duble(sem_prova=True))
        m = correio.pedir_imagem("picasso", "x", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "sem_prova")
        self.assertIn("nada foi baixado", fim["erro"])
        pasta = correio.pasta(("picasso")) / "imagens"
        self.assertFalse(pasta.exists() and any(pasta.iterdir()))
        self.assertIsNone(correio.arquivo_da_imagem("picasso", m["id"]))
        self.assertEqual(c.documentos, [])
        self.assertEqual(len(c.avisos), 1)
        self.assertIn("a imagem não saiu", c.avisos[0])

    def test_prova_que_nao_comprova_nao_grava(self):
        class _SemComprovar(imagem.SessaoImagemDuble):
            def gerar_imagem(self, prompt, proporcao, mensagem_id=""):
                saida = super().gerar_imagem(prompt, proporcao, mensagem_id)
                saida["prova"] = {"comprovada": False}
                return saida

        @contextmanager
        def fabrica(ia):
            yield _SemComprovar(ia)
        c = _novo(fabrica)
        correio.pedir_imagem("picasso", "x", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["categoria"], "sem_prova")
        self.assertFalse((correio.pasta("picasso") / "imagens").exists()
                         and any((correio.pasta("picasso") / "imagens").glob("*.png")))

    def test_recusa_de_conteudo_vira_motivo(self):
        exc = ConteudoRecusado("o PicassoIA recusou o prompt: CONTEÚDO ILEGAL")
        c = _novo(imagem.fabrica_imagem_duble(falhar=exc))
        correio.pedir_imagem("picasso", "x", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["categoria"], "conteudo")
        self.assertIn("CONTEÚDO ILEGAL", fim["erro"])
        self.assertIn("reescreva", fim["erro"])

    def test_cota_vira_motivo_e_tira_do_rodizio(self):
        tela = "Gerar GRATIS\nVoce atingiu seu limite de geracoes em paralelo. Espere uma terminar."
        c = _novo(imagem.fabrica_imagem_duble(falhar=RuntimeError("EsperaEstourou"), tela=tela))
        correio.pedir_imagem("picasso", "x", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["categoria"], "limite")
        self.assertIn("o site diz", fim["erro"])
        self.assertIn("limite de geracoes", fim["erro"])
        self.assertIn("limite", imagem.fora_de_cota("picasso"))
        self.assertEqual(imagem.fora_de_cota("picasso", horas=0), "")

    def test_parede_de_planos_reabre_o_perfil_uma_vez(self):
        chamadas = []

        @contextmanager
        def fabrica(ia):
            chamadas.append(ia)
            falhar = ParedeDePlanos("Assine para Gerar") if len(chamadas) == 1 else None
            yield imagem.SessaoImagemDuble(ia, falhar=falhar)
        c = _novo(fabrica)
        correio.pedir_imagem("picasso", "x", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(len(chamadas), 2)

    def test_parede_duas_vezes_falha_com_motivo(self):
        @contextmanager
        def fabrica(ia):
            yield imagem.SessaoImagemDuble(ia, falhar=ParedeDePlanos("Assine para Gerar"))
        c = _novo(fabrica)
        correio.pedir_imagem("picasso", "x", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["categoria"], "parede")
        self.assertIn("Assine para Gerar", fim["erro"])

    def test_gerador_que_nao_gera_falha_sem_abrir_navegador(self):
        abriu = []

        @contextmanager
        def fabrica(ia):
            abriu.append(ia)
            yield imagem.SessaoImagemDuble(ia)
        c = _novo(fabrica)
        correio.pedir_imagem("dreamface", "x", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "indisponivel")
        self.assertIn("créditos 0", fim["erro"])
        self.assertEqual(abriu, [])

    def test_trava_da_pipeline_espera_nunca_mata(self):
        travas = _TravasPorNome(ocupadas={"perfil__picasso__teste"}, soltar_depois=2)
        c = _novo(trava=travas)
        m = correio.pedir_imagem("picasso", "x", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "respondida")
        self.assertGreaterEqual(len(travas.pedidos), 3)
        self.assertIn("esperando a pipeline", json.dumps(
            [json.loads(linha) for linha in correio.arquivo("picasso").read_text(
                "utf-8").splitlines() if m["id"] in linha], ensure_ascii=False))

    def test_app_olhando_nao_manda_telegram(self):
        c = _novo()
        correio.pedir_imagem("picasso", "x", proporcao="1:1")
        correio.registrar_presenca("correio:picasso")
        c.uma_volta()
        self.assertEqual(c.documentos, [])
        self.assertEqual(c.avisos, [])

    def test_imagem_na_casa_do_chat(self):
        fabrica = carteiro_mod.fabrica_duble()
        c = _novo(fabrica=fabrica)
        correio.enviar("grok", "oi")
        m = correio.pedir_imagem("grok", "um gato", proporcao="3:4")
        c.ajustes["janela_conversa_s"] = 1
        primeira = c.uma_volta()                       # texto, e na janela a imagem
        self.assertEqual(primeira["situacao"], "respondida")
        fim = correio.uma("grok", m["id"])
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(fim["imagem"]["arquivo"], f"{m['id']}.png")
        self.assertEqual(len(fabrica.criadas), 1)      # a MESMA sessao do navegador...
        self.assertEqual([t.get("imagem") for t in fabrica.criadas[0].turnos
                          if t.get("imagem")], ["3:4"])
        # ...mas a imagem vai numa conversa NOVA e nao entra na casa (02/10/2026:
        # na casa o Gemini lembrava do texto e recusava gerar)
        self.assertEqual(fabrica.criadas[0].casas_novas, 2)   # a casa (nova) + a da imagem
        self.assertEqual(correio.casa("grok")["mensagens"], 1)
        self.assertTrue(correio.arquivo_da_imagem("grok", m["id"]).is_file())

    def test_imagem_do_chat_sem_imagem_vira_motivo(self):
        fabrica = carteiro_mod.fabrica_duble(
            imagem_falhar=imagem.SemImagem("o Gemini respondeu sem imagem: «não posso»"))
        c = _novo(fabrica=fabrica)
        correio.pedir_imagem("gemini", "x", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["categoria"], "sem_imagem")
        self.assertIn("não posso", fim["erro"])

    def test_chrome_fechado_no_download_reabre_sem_gerar_de_novo(self):
        """A segunda sessao recupera a imagem ja na casa, sem novo pedido a IA."""
        criadas, aberturas = [], []

        class _Sessao:
            def __init__(self, numero):
                self.numero = numero
                self.geradas = self.recuperadas = 0

            def abrir_casa(self, url):
                aberturas.append((self.numero, url))
                return self.numero == 1 and bool(url)

            def novo_chat(self):
                pass

            def gerar_imagem(self, prompt, proporcao, mensagem_id):
                self.geradas += 1
                raise RuntimeError("TargetClosedError: browser fechou no download")

            def recuperar_imagem(self, prompt, proporcao):
                self.recuperadas += 1
                return {"bytes": imagem.png_de_teste(),
                        "prova": {"comprovada": True, "metodo": "duble", "forca": "teste"}}

            def url(self):
                return "https://gemini.google.com/app/casa"

        @contextmanager
        def fabrica(ia):
            sessao = _Sessao(len(criadas))
            criadas.append(sessao)
            yield sessao

        c = _novo(fabrica=fabrica)
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual([s.geradas for s in criadas], [1, 0])
        self.assertEqual([s.recuperadas for s in criadas], [0, 1])
        # a casa abre, e a recuperacao volta na conversa PROPRIA da imagem (02/10)
        self.assertEqual(aberturas, [(1, "https://gemini.google.com/app/casa")] * 2)
        self.assertEqual(correio.uma("gemini", m["id"])["chat_imagem_url"],
                         "https://gemini.google.com/app/casa")
        self.assertTrue(correio.arquivo_da_imagem("gemini", m["id"]).is_file())


# ======================================================= conversa com imagem
class ConversaQueRespondeComImagem(_Base):
    """O caso real de 29/09 14:24 (`dde066f1`): "gere uma imagem de um gato"
    ao Gemini pela CONVERSA. A resposta e a imagem, sem texto."""

    def test_a_imagem_da_resposta_vira_a_resposta(self):
        fabrica = carteiro_mod.fabrica_duble(responder=lambda t: "",
                                             responder_com_imagem=True)
        c = _novo(fabrica=fabrica)
        m = correio.enviar("gemini", "Tudo ótimo, gere uma imagem de um gato pra mim")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(fim["gerador"], "gemini")
        self.assertEqual(fim["imagem"]["arquivo"], f"{m['id']}.png")
        self.assertTrue(fim["resposta"].startswith("(imagem"))
        alvo = correio.arquivo_da_imagem("gemini", m["id"])
        self.assertTrue(alvo.is_file())
        self.assertEqual(alvo.parent, correio.pasta_imagens("gemini"))
        self.assertEqual(len(c.documentos), 1)          # Telegram como documento
        self.assertEqual(c.documentos[0][0], alvo)
        self.assertEqual([i["id"] for i in correio.imagens("gemini")], [m["id"]])

    def test_texto_com_imagem_guarda_os_dois(self):
        fabrica = carteiro_mod.fabrica_duble(responder=lambda t: "Aqui está o gato!",
                                             responder_com_imagem=True)
        c = _novo(fabrica=fabrica)
        m = correio.enviar("gemini", "gere um gato")
        fim = c.uma_volta()
        self.assertEqual(fim["resposta"], "Aqui está o gato!")
        self.assertTrue(correio.arquivo_da_imagem("gemini", m["id"]).is_file())

    def test_imagem_sem_prova_e_sem_texto_falha_com_motivo(self):
        fabrica = carteiro_mod.fabrica_duble(responder=lambda t: "",
                                             responder_com_imagem=True,
                                             imagem_sem_prova=True)
        c = _novo(fabrica=fabrica)
        m = correio.enviar("gemini", "gere um gato")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "sem_prova")
        self.assertIn("a resposta foi uma imagem", fim["erro"])
        self.assertIsNone(correio.arquivo_da_imagem("gemini", m["id"]))

    def test_resposta_so_de_texto_continua_como_antes(self):
        c = _novo(fabrica=carteiro_mod.fabrica_duble(responder=lambda t: "OK"))
        m = correio.enviar("gemini", "oi")
        fim = c.uma_volta()
        self.assertEqual(fim["resposta"], "OK")
        self.assertNotIn("imagem", fim)
        self.assertIsNone(correio.arquivo_da_imagem("gemini", m["id"]))
        self.assertEqual(c.documentos, [])
        self.assertEqual(len(c.avisos), 1)


class SessaoRealBaixaAImagemDaResposta(_Base):
    """`SessaoReal.imagem_da_resposta` com um cliente falso: prova do turno."""

    def _cliente(self, turno, imagens, *, na_tela=None, antes=(), resposta=True,
                 gerando=False, fora=0):
        """Um cliente falso: `imagens` e o que a espera aceitou; `na_tela` e o
        que esta AGORA dentro da resposta ao nosso turno (padrao: as mesmas);
        `antes` e a foto da pagina antes do envio (None = sem foto)."""
        corpo = imagem.png_de_teste(300, 300)
        baixados = []

        class _Resp:
            ok = True
            status = 200

            def body(self):
                return corpo

        class _Ctx:
            class request:                                      # noqa: N801
                @staticmethod
                def get(url, timeout=None):
                    baixados.append(url)
                    return _Resp()

        class _Pagina:
            url = "https://gemini.google.com/app/casa123"

        dentro = list(imagens if na_tela is None else na_tela)

        class _Cli:
            provedor = "gemini"
            sel = {}
            ajustes = {}
            modelo_atual = "Pro"
            ctx = _Ctx()
            page = _Pagina()
            imagens_na_resposta = imagens
            _srcs_antes_do_envio = None if antes is None else set(antes)

            def imagens_da_resposta(self):
                return {"ancorado": True, "turno": turno, "resposta": resposta,
                        "gerando": gerando, "imagens": dentro, "fora": fora}
        cli = _Cli()
        cli.baixados = baixados
        return cli, corpo

    def test_baixa_com_a_prova_do_turno(self):
        gato = {"src": "https://lh3.googleusercontent.com/gato", "w": 1024, "h": 1024}
        cli, corpo = self._cliente("Você disse Tudo ótimo, gere uma imagem de um gato", [gato])
        sessao = carteiro_mod.SessaoReal(cli, log=lambda *_a: None)
        saida = sessao.imagem_da_resposta("Tudo ótimo, gere uma imagem de um gato")
        self.assertEqual(saida["bytes"], corpo)
        self.assertEqual(saida["prova"]["metodo"], "turno_na_casa")
        self.assertEqual(saida["prova"]["casa_url"], "https://gemini.google.com/app/casa123")

    def _gemini_com_botao(self, *, download=True, resposta=None, habilitado=True,
                          reserva=None, fecha_no_download=False):
        """Um Gemini falso com o botao "Baixar imagem no tamanho original": o
        clique solta o evento de download (ou so a resposta de imagem)."""
        original = imagem.png_de_teste(352, 192)      # a forma do original: 2816x1536 / 8
        arquivo = Path(self._tmp.name) / "Gemini_Generated_Image.png"
        arquivo.write_bytes(original)
        cliques = []

        class _Download:
            suggested_filename = arquivo.name

            @staticmethod
            def path():
                if fecha_no_download:
                    raise RuntimeError("TargetClosedError: browser fechou")
                return str(arquivo)

        class _Resposta:
            headers = {"content-type": "image/png"}

            class request:                                      # noqa: N801
                resource_type = "fetch"

            @staticmethod
            def body():
                return resposta

        class _Pagina:
            url = "https://gemini.google.com/app/casa"

            def __init__(self):
                self.ouvintes = {}

            def evaluate(self, script, arg=None):
                if "data-nf-imagem" in script:
                    # a imagem achada DENTRO da resposta, e o botao dela
                    return {"imagem": arg[3] == "https://lh3/gato", "botao": True}
                return None

            def locator(self, seletor):
                assert seletor == "[data-nf-baixar='1']"
                return alvo

            def on(self, evento, funcao):
                self.ouvintes[evento] = funcao

            def remove_listener(self, evento, funcao):
                self.ouvintes.pop(evento, None)

            def wait_for_timeout(self, ms):
                pass

        pagina = _Pagina()

        class _Alvo:
            first = None

            def scroll_into_view_if_needed(self, timeout=None):
                pass

            def evaluate(self, script):
                return habilitado

            def hover(self, timeout=None, force=False):
                pass

            def click(self, timeout=None, force=False):
                cliques.append(force)
                if resposta is not None:
                    pagina.ouvintes["response"](_Resposta())
                if download:
                    pagina.ouvintes["download"](_Download())

        alvo = _Alvo()
        alvo.first = alvo

        class _Ctx:
            class request:                                      # noqa: N801
                @staticmethod
                def get(url, timeout=None):
                    if reserva is None:
                        raise AssertionError("o src nao devia ser usado")

                    class _R:
                        ok, status = True, 200

                        @staticmethod
                        def body():
                            return reserva
                    return _R()

        from contos.llm import seletores

        class _Cli:
            provedor = "gemini"
            sel = seletores.GEMINI
            ajustes = {}
            modelo_atual = "Pro"
            ctx = _Ctx()
            page = pagina
            imagens_na_resposta = [{"src": "https://lh3/gato", "w": 1024, "h": 559}]
            _srcs_antes_do_envio = set()

            def imagens_da_resposta(self):
                return {"ancorado": True, "turno": "gere um gato", "resposta": True,
                        "imagens": list(self.imagens_na_resposta)}
        return _Cli(), original, cliques

    def test_gemini_baixa_pelo_botao_do_tamanho_original(self):
        """15:23: o `src` da tela nao baixou (CORS); o botao do site baixa."""
        cli, original, cliques = self._gemini_com_botao()
        saida = carteiro_mod.SessaoReal(cli, log=lambda *_a: None).imagem_da_resposta(
            "gere um gato")
        self.assertEqual(saida["bytes"], original)            # bytes do site, intactos
        self.assertEqual(saida["prova"]["download"], "botao_tamanho_original")
        self.assertEqual(cliques, [False])
        self.assertEqual(cli.page.ouvintes, {})               # ouvintes removidos

    def test_sem_evento_de_download_vale_a_resposta_de_imagem(self):
        jpeg = b"\xff\xd8\xff\xe0" + b"j" * 4000
        cli, _, _ = self._gemini_com_botao(download=False, resposta=jpeg)
        # relogio falso: os 90 s de espera pelo download passam em 18 voltas
        import types
        agora = [0.0]

        def monotonic():
            agora[0] += 5.0
            return agora[0]
        self.addCleanup(setattr, imagem, "time", imagem.time)
        imagem.time = types.SimpleNamespace(monotonic=monotonic, sleep=lambda _s: None)
        saida = imagem.baixar_da_resposta(cli, "gere um gato", log=lambda *_a: None)
        self.assertEqual(saida["bytes"], jpeg)

    def test_chrome_fecha_no_download_usa_a_reserva_do_src(self):
        """O `Download.path` cai com o navegador, mas o src ja foi guardado."""
        reserva = imagem.png_de_teste(352, 192)
        cli, _, cliques = self._gemini_com_botao(reserva=reserva, fecha_no_download=True)
        saida = imagem.baixar_da_resposta(cli, "gere um gato", log=lambda *_a: None)
        self.assertEqual(saida["bytes"], reserva)
        self.assertEqual(saida["prova"]["download"], "src_da_tela")
        self.assertEqual(cliques, [False])

    def test_botao_desabilitado_nao_clica_e_diz_por_que(self):
        cli, _, cliques = self._gemini_com_botao(habilitado=False)
        with self.assertRaises(imagem.ImagemFalhou) as erro:
            imagem.baixar_da_resposta(cli, "gere um gato", log=lambda *_a: None)
        self.assertIn("desabilitado", str(erro.exception))
        self.assertEqual(cliques, [])

    def test_src_vazio_nunca_baixa_a_pagina(self):
        """`fetch("")` baixava a propria pagina (864 KB de HTML)."""
        with self.assertRaises(imagem.ImagemFalhou) as erro:
            imagem.baixar(None, None, "")
        self.assertIn("sem URL de imagem", str(erro.exception))

    def test_turno_que_nao_e_o_nosso_nao_baixa(self):
        gato = {"src": "https://lh3.googleusercontent.com/gato", "w": 1024, "h": 1024}
        cli, _ = self._cliente("outra pergunta de outra pessoa", [gato])
        sessao = carteiro_mod.SessaoReal(cli, log=lambda *_a: None)
        with self.assertRaises(imagem.SemProva):
            sessao.imagem_da_resposta("Tudo ótimo, gere uma imagem de um gato")

    def test_sem_imagem_na_resposta_e_none(self):
        cli, _ = self._cliente("oi", [])
        sessao = carteiro_mod.SessaoReal(cli, log=lambda *_a: None)
        self.assertIsNone(sessao.imagem_da_resposta("oi"))


# ================================== a imagem tem de ser a do NOSSO turno
GATO_CHATGPT = {"src": "https://chatgpt.com/backend-api/estuary/content?id=file_gato",
                "w": 1254, "h": 1254, "pronta": True, "borrada": False,
                "alt": "Imagem gerada: Retrato Aconchegante de Gato Tigrado"}
ANUNCIO = {"src": "https://images.openai.com/static-rsc-5/mesa-de-som", "w": 512, "h": 512,
           "pronta": True, "borrada": False, "alt": ""}


class ImagemSoDoNossoTurno(_Base):
    """29/09/2026, 16:02 (correio d228c94f): "Crie um gato" ao ChatGPT voltou
    "imagem pronta" com a foto de uma MESA DE SOM — a miniatura de um anuncio
    que o ChatGPT pos no mesmo turno. Na hora de baixar, a prova e refeita:
    dentro da resposta ao nosso turno, nova, e com a geracao terminada."""

    _cliente = SessaoRealBaixaAImagemDaResposta._cliente
    PEDIDO = "Crie uma imagem na proporção 1:1. Responda só com a imagem, sem texto.\n\nCrie um gato"

    def _baixar(self, cli):
        return imagem.baixar_da_resposta(cli, self.PEDIDO, "1:1", log=lambda *_a: None)

    def test_imagem_nova_dentro_da_resposta_baixa_com_a_prova(self):
        cli, corpo = self._cliente(self.PEDIDO, [GATO_CHATGPT],
                                   antes={"https://antiga/do-turno-anterior"}, fora=1)
        saida = self._baixar(cli)
        self.assertEqual(saida["bytes"], corpo)
        prova = saida["prova"]
        self.assertTrue(prova["dentro_da_resposta"])
        self.assertTrue(prova["src_novo"])
        self.assertEqual(prova["imagens_antes_do_envio"], 1)
        self.assertEqual(prova["ignoradas_fora_da_resposta"], 1)
        self.assertTrue(prova["alt"].startswith("Imagem gerada"))
        self.assertEqual(cli.baixados, [GATO_CHATGPT["src"]])

    def test_imagem_fora_da_resposta_nao_baixa_nada(self):
        # o anuncio foi aceito pela espera (codigo velho), mas NAO esta dentro
        # da resposta ao nosso turno: nada e baixado
        cli, _ = self._cliente(self.PEDIDO, [ANUNCIO], na_tela=[GATO_CHATGPT], fora=1)
        with self.assertRaises(imagem.SemProva) as erro:
            self._baixar(cli)
        self.assertIn("não está dentro da resposta", str(erro.exception))
        self.assertEqual(cli.baixados, [])

    def test_sem_resposta_ao_nosso_turno_nao_baixa(self):
        cli, _ = self._cliente(self.PEDIDO, [GATO_CHATGPT], resposta=False)
        with self.assertRaises(imagem.SemProva):
            self._baixar(cli)
        self.assertEqual(cli.baixados, [])

    def test_imagem_que_ja_estava_na_pagina_antes_do_envio_nao_baixa(self):
        cli, _ = self._cliente(self.PEDIDO, [GATO_CHATGPT], antes={GATO_CHATGPT["src"]})
        with self.assertRaises(imagem.SemProva) as erro:
            self._baixar(cli)
        self.assertIn("já estava na página", str(erro.exception))
        self.assertEqual(cli.baixados, [])

    def test_sem_a_foto_de_antes_do_envio_nao_baixa(self):
        cli, _ = self._cliente(self.PEDIDO, [GATO_CHATGPT], antes=None)
        with self.assertRaises(imagem.SemProva) as erro:
            self._baixar(cli)
        self.assertIn("antes do envio", str(erro.exception))

    def test_ainda_gerando_nao_baixa_a_previa(self):
        cli, _ = self._cliente(self.PEDIDO, [GATO_CHATGPT], gerando=True)
        with self.assertRaises(imagem.SemProva) as erro:
            self._baixar(cli)
        self.assertIn("gerando", str(erro.exception))
        self.assertEqual(cli.baixados, [])

    def test_caso_zero_nada_na_resposta_e_none(self):
        cli, _ = self._cliente(self.PEDIDO, [], na_tela=[], antes=set())
        self.assertIsNone(self._baixar(cli))
        self.assertEqual(cli.baixados, [])

    def test_proporcao_do_arquivo_contra_a_tela(self):
        # Gemini: a tela mostra 1024x559 e o original e 2816x1536 (mesma forma)
        self.assertTrue(imagem.mesma_proporcao(imagem.png_de_teste(2816 // 8, 1536 // 8),
                                               {"w": 1024, "h": 559}))
        self.assertFalse(imagem.mesma_proporcao(imagem.png_de_teste(64, 64),
                                                {"w": 1024, "h": 559}))
        self.assertTrue(imagem.mesma_proporcao(imagem.png_de_teste(64, 64), {"w": 0}))


class ChatGPTBaixaPelaTelaCheia(_Base):
    """Medido em 29/09 16:1x: o "Baixar" do ChatGPT so existe na tela cheia,
    que abre com o clique na imagem; entrega o PNG original. No cartao novo
    (02/10) o clique e na PREVIA do item, que abre o visualizador com o mesmo
    "Baixar"; o "Compartilhar" nunca e clicado (decisao do Adrian: o dialogo
    dele cria link publico da imagem)."""

    def _chatgpt(self, *, botao_aparece=True, original=None, cartao_novo=False,
                 rotulo_abrir="Imagem 1 gerada", rotulo_baixar="Baixar"):
        from contos.llm import seletores
        original = original or imagem.png_de_teste(96, 96)
        arquivo = Path(self._tmp.name) / "ChatGPT Image.png"
        arquivo.write_bytes(original)
        passos = []
        rotulos = {"imagem": "", "previa": rotulo_abrir, "dialogo": rotulo_baixar}

        class _Download:
            suggested_filename = arquivo.name

            @staticmethod
            def path():
                return str(arquivo)

        class _Loc:
            def __init__(self, nome):
                self.nome = nome
                self.first = self

            def count(self):
                return 1 if (self.nome != "dialogo" or pagina.aberta) else 0

            def scroll_into_view_if_needed(self, timeout=None):
                pass

            def evaluate(self, script):
                if "aria-label" in script:                      # o rotulo
                    return rotulos[self.nome]
                return True                                     # habilitado

            def hover(self, timeout=None, force=False):
                pass

            def click(self, timeout=None, force=False):
                passos.append(f"clique:{self.nome}")
                if "ompartilh" in rotulos[self.nome]:
                    passos.append("COMPARTILHOU")
                if self.nome in ("imagem", "previa"):
                    pagina.aberta = botao_aparece
                else:
                    pagina.ouvintes["download"](_Download())

        class _Teclado:
            @staticmethod
            def press(tecla):
                passos.append(f"tecla:{tecla}")
                pagina.aberta = False

        class _Pagina:
            url = "https://chatgpt.com/c/casa"
            keyboard = _Teclado()

            def __init__(self):
                self.ouvintes = {}
                self.aberta = False

            def evaluate(self, script, arg=None):
                if "data-nf-imagem" in script:
                    passos.append("marcar")
                    # no ChatGPT o botao nao esta no turno: so a imagem e marcada
                    assert arg[4] == []
                    # quem abre o visualizador e a previa do item
                    assert arg[5] == seletores.CHATGPT["imagem_abrir"], arg[5]
                    return {"imagem": arg[3] == GATO_CHATGPT["src"], "botao": False,
                            "abrir": bool(cartao_novo)}
                return None

            def locator(self, seletor):
                if seletor == "[data-nf-imagem='1']":
                    return _Loc("imagem")
                if seletor == "[data-nf-abrir='1']":
                    return _Loc("previa")
                assert seletor.startswith("[role='dialog']"), seletor
                return _Loc("dialogo")

            def on(self, evento, funcao):
                self.ouvintes[evento] = funcao

            def remove_listener(self, evento, funcao):
                self.ouvintes.pop(evento, None)

            def wait_for_timeout(self, ms):
                pass

        pagina = _Pagina()

        class _Ctx:
            class request:                                      # noqa: N801
                @staticmethod
                def get(url, timeout=None):
                    passos.append("src")

                    class _R:
                        ok, status = True, 200

                        @staticmethod
                        def body():
                            return imagem.png_de_teste(80, 80, cor=(1, 2, 3))
                    return _R()

        class _Cli:
            provedor = "chatgpt"
            sel = seletores.CHATGPT
            ajustes = {}
            modelo_atual = ""
            ctx = _Ctx()
            page = pagina
            imagens_na_resposta = [dict(GATO_CHATGPT)]
            _srcs_antes_do_envio = {ANUNCIO["src"]}

            def imagens_da_resposta(self):
                return {"ancorado": True, "turno": "crie um gato", "resposta": True,
                        "imagens": [dict(GATO_CHATGPT)], "fora": 1}
        return _Cli(), original, passos

    def test_abre_a_imagem_baixa_e_fecha(self):
        cli, original, passos = self._chatgpt()
        saida = imagem.baixar_da_resposta(cli, "crie um gato", log=lambda *_a: None)
        self.assertEqual(saida["bytes"], original)
        self.assertEqual(saida["prova"]["download"], "botao_tamanho_original")
        self.assertEqual(passos, ["src", "marcar", "clique:imagem", "clique:dialogo",
                                  "tecla:Escape"])
        self.assertEqual(cli.page.ouvintes, {})

    def test_cartao_novo_abre_pela_previa_baixa_e_fecha(self):
        """02/10 (decisao do Adrian, "Visualizador"): o clique e na previa do
        proprio item, nunca no "Compartilhar imagem gerada N"."""
        cli, original, passos = self._chatgpt(cartao_novo=True)
        saida = imagem.baixar_da_resposta(cli, "crie um gato", log=lambda *_a: None)
        self.assertEqual(saida["bytes"], original)
        self.assertEqual(saida["prova"]["download"], "botao_tamanho_original")
        self.assertEqual(passos, ["src", "marcar", "clique:previa", "clique:dialogo",
                                  "tecla:Escape"])
        self.assertNotIn("COMPARTILHOU", passos)

    def test_abridor_de_compartilhar_nunca_e_clicado(self):
        """Se o seletor de abrir voltar a achar o "Compartilhar imagem gerada
        N" (o caminho de e8470c8), o clique e recusado e a imagem vem pelo
        src: o dialogo dele cria link publico."""
        cli, _, passos = self._chatgpt(cartao_novo=True,
                                       rotulo_abrir="Compartilhar imagem gerada 1")
        falas = []
        saida = imagem.baixar_da_resposta(cli, "crie um gato", log=falas.append)
        self.assertEqual(saida["prova"]["download"], "src_da_tela")
        self.assertNotIn("COMPARTILHOU", passos)
        self.assertEqual([p for p in passos if p.startswith("clique")], [])
        self.assertTrue(any("compartilhar" in f for f in falas), falas)

    def test_botao_de_baixar_de_compartilhar_nunca_e_clicado(self):
        """O "Compartilhar" do proprio visualizador tambem nao: abre, recusa,
        fecha com Escape e cai no src."""
        cli, _, passos = self._chatgpt(cartao_novo=True, rotulo_baixar="Compartilhar")
        saida = imagem.baixar_da_resposta(cli, "crie um gato", log=lambda *_a: None)
        self.assertEqual(saida["prova"]["download"], "src_da_tela")
        self.assertNotIn("COMPARTILHOU", passos)
        self.assertNotIn("clique:dialogo", passos)
        self.assertIn("tecla:Escape", passos)

    def test_seletores_do_chatgpt_nao_apontam_para_compartilhar(self):
        from contos.llm import seletores
        for chave in ("imagem_abrir", "imagem_baixar"):
            for seletor in seletores.CHATGPT[chave]:
                self.assertNotRegex(seletor.lower(), "compartilh|share", chave)
        self.assertEqual(seletores.CHATGPT["imagem_abrir"],
                         ["button[data-testid='generated-image-preview']"])

    def test_tela_cheia_sem_botao_fecha_e_cai_no_src(self):
        cli, _, passos = self._chatgpt(botao_aparece=False)
        saida = imagem.baixar_da_resposta(cli, "crie um gato", log=lambda *_a: None)
        self.assertEqual(saida["prova"]["download"], "src_da_tela")
        self.assertIn("tecla:Escape", passos)
        self.assertEqual(passos[0], "src")

    def test_arquivo_de_outra_forma_nao_vale_e_cai_no_src(self):
        # o botao entregou um arquivo 2:1 para uma imagem 1:1 na tela
        cli, _, passos = self._chatgpt(original=imagem.png_de_teste(128, 64))
        saida = imagem.baixar_da_resposta(cli, "crie um gato", log=lambda *_a: None)
        self.assertEqual(saida["prova"]["download"], "src_da_tela")
        self.assertEqual(passos[0], "src")


class CarteiroComAImagemDeForaDoTurno(_Base):
    """O caminho inteiro do d228c94f pelo carteiro: a sessao real com um
    cliente cuja resposta so tem imagem FORA do nosso turno. O pedido falha
    com o motivo e NADA vai ao disco."""

    def _fabrica(self, na_resposta, antes):
        class _Cli:
            provedor = "chatgpt"
            sel = {}
            ajustes = {}
            modelo_atual = ""
            ctx = None

            class page:                                         # noqa: N801
                url = "https://chatgpt.com/c/casa"

            def __init__(self):
                self.imagens_na_resposta = []
                self._srcs_antes_do_envio = None
                self.pedido = ""

            def perguntar(self, texto, anexos=None):
                self.pedido = texto
                self._srcs_antes_do_envio = set(antes)
                self.imagens_na_resposta = list(na_resposta)
                return ""

            def imagens_da_resposta(self):
                return {"ancorado": True, "turno": self.pedido, "resposta": True,
                        "imagens": [i for i in na_resposta if i is not ANUNCIO],
                        "fora": 1}

        class _Sessao(carteiro_mod.SessaoReal):
            def abrir_casa(self, url):
                return False

            def novo_chat(self):
                pass

            def url(self):
                return "https://chatgpt.com/c/casa"

            def texto_visivel(self):
                return ""

        @contextmanager
        def _abrir(ia):
            yield _Sessao(_Cli(), log=lambda *_a: None)
        return _abrir

    def test_anuncio_aceito_pela_espera_vira_falha_sem_arquivo(self):
        c = _novo(fabrica=self._fabrica([ANUNCIO], antes=set()))
        m = correio.pedir_imagem("chatgpt", "Crie um gato para mim", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "sem_prova")
        self.assertIn("não está dentro da resposta", fim["erro"])
        self.assertIsNone(correio.arquivo_da_imagem("chatgpt", m["id"]))
        self.assertFalse(correio.pasta_imagens("chatgpt").exists()
                         and any(correio.pasta_imagens("chatgpt").iterdir()))

    def test_imagem_antiga_da_pagina_vira_falha_sem_arquivo(self):
        c = _novo(fabrica=self._fabrica([GATO_CHATGPT], antes={GATO_CHATGPT["src"]}))
        m = correio.pedir_imagem("chatgpt", "Crie um gato para mim", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertIn("já estava na página", fim["erro"])
        self.assertIsNone(correio.arquivo_da_imagem("chatgpt", m["id"]))


# ================================================================ rodizio
class Rodizio(_Base):
    def test_escolhe_o_primeiro_livre_pela_ordem(self):
        travas = _TravasPorNome(ocupadas={"perfil__picasso__teste"})
        fabrica_chat = carteiro_mod.fabrica_duble()
        c = _novo(fabrica=fabrica_chat, trava=travas)
        m = correio.pedir_imagem("livre", "x", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(fim["gerador"], "gemini")     # picasso ocupado, gemini o 2o
        self.assertIn("Gemini estava livre", fim.get("rodizio") or "")
        self.assertTrue(correio.arquivo_da_imagem("livre", m["id"]).is_file())
        self.assertEqual(correio.arquivo_da_imagem("livre", m["id"]).parent,
                         correio.pasta_imagens("gemini"))
        self.assertEqual(travas.pedidos[:2], ["perfil__picasso__teste",
                                              "perfil__gemini__teste"])

    def test_pula_quem_esta_fora_de_cota(self):
        antiga = correio.pedir_imagem("picasso", "y", proporcao="1:1")
        correio.atualizar("picasso", antiga["id"], situacao="falhou", categoria="limite",
                          erro="limite de geracoes", falhou_em=correio.agora())
        c = _novo()
        correio.pedir_imagem("livre", "x", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["gerador"], "gemini")

    def test_todas_ocupadas_espera_e_depois_gera(self):
        travas = _TravasPorNome(ocupadas={f"perfil__{g}__teste" for g in
                                          ("picasso", "gemini", "grok", "chatgpt")},
                                soltar_depois=4)
        c = _novo(trava=travas)
        correio.pedir_imagem("livre", "x", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(fim["gerador"], "picasso")

    def test_ninguem_pode_gerar_falha_com_os_motivos(self):
        c = _novo(ajustes={"rodizio_imagem": ["dreamface", "digen"]})
        correio.pedir_imagem("livre", "x", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "rodizio")
        self.assertIn("DreamFace", fim["erro"])
        self.assertIn("Digen", fim["erro"])

    def test_proporcao_que_o_primeiro_nao_faz_vai_para_o_proximo(self):
        c = _novo()
        correio.pedir_imagem("livre", "x", proporcao="2:3")   # so o PicassoIA faz
        fim = c.uma_volta()
        self.assertEqual(fim["gerador"], "picasso")
        c2 = _novo(ajustes={"rodizio_imagem": ["gemini", "picasso"]})
        correio.pedir_imagem("livre", "x", proporcao="2:3")
        self.assertEqual(c2.uma_volta()["gerador"], "picasso")


# ================================================================ disco
class AltaProcuraDoGrok(_Base):
    """29/09 17:30 e 17:44: o card "Alta procura" do grok.com no lugar da
    resposta. O cliente agora sai em segundos com `SiteIndisponivel`; aqui, o
    carteiro marca `indisponivel` (e nao o `erro_site` do 1o pedido, pelo
    "tente novamente" generico) e o rodizio tira o Grok por `cota_pausa_h`."""

    CARD = ("o grok respondeu com o aviso do site no lugar da resposta: «Alta procura "
            "Por favor, tente novamente em breve, ou atualize para um acesso com maior "
            "prioridade Aprimorar»; não reenvio agora.")

    def _exc(self):
        from contos.llm.cliente import SiteIndisponivel
        return SiteIndisponivel(self.CARD)

    def test_classificadores_dizem_indisponivel(self):
        cat, motivo = carteiro_mod.classificar_erro("grok", self._exc())
        self.assertEqual(cat, "indisponivel")
        self.assertIn("Alta procura", motivo)
        cat, motivo = imagem.classificar("grok", self._exc(), tela="Tente novamente")
        self.assertEqual(cat, "indisponivel")
        self.assertIn("Alta procura", motivo)

    def test_pedido_ao_grok_falha_indisponivel_e_sai_do_rodizio(self):
        c = _novo(fabrica=carteiro_mod.fabrica_duble(imagem_falhar=self._exc()))
        m = correio.pedir_imagem("grok", "um gato laranja", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "indisponivel")
        self.assertTrue(fim.get("pausa_rodizio"))
        self.assertIsNone(correio.arquivo_da_imagem("grok", m["id"]))
        self.assertIn("indisponivel", imagem.fora_de_cota("grok"))
        self.assertEqual(imagem.fora_de_cota("grok", horas=0), "")
        # o proximo "qualquer um livre" com o Grok primeiro pula para o seguinte
        c2 = _novo(ajustes={"rodizio_imagem": ["grok", "chatgpt"]})
        correio.pedir_imagem("livre", "x", proporcao="1:1")
        self.assertEqual(c2.uma_volta()["gerador"], "chatgpt")

    def test_indisponivel_sem_pausa_continua_no_rodizio(self):
        # caso zero: o `indisponivel` de antes (EsperaEstourou do PicassoIA,
        # "sem cliente") NAO tira ninguem da roda — so o aviso do site
        antiga = correio.pedir_imagem("picasso", "y", proporcao="1:1")
        correio.atualizar("picasso", antiga["id"], situacao="falhou", categoria="indisponivel",
                          erro="não devolveu a imagem (3 tentativas)", falhou_em=correio.agora(),
                          gerador="picasso")
        self.assertEqual(imagem.fora_de_cota("picasso"), "")


class PaginaEmBrancoDoGrok(_Base):
    """30/09 09:16: o grok.com abriu EM BRANCO no perfil `grok__principal` (o
    app nao montou em 45 s, nenhum HTTP >= 400). O cliente agora levanta
    `SiteIndisponivel` NA ABERTURA (antes dizia "chat novo aberto" e morria no
    envio). Aqui, o carteiro: nao abandona a casa (nem casa nova, nem falha
    contada contra ela), marca `indisponivel` com pausa, e o rodizio pula o
    Grok. O login caido continua como era."""

    MOTIVO = ("o grok não montou a página em 45 s (título 'Grok', 0 caracteres "
              "visíveis): o site não carregou — não é o login; não reabro agora.")

    def _fabrica(self, exc=None):
        from contos.llm.cliente import SiteIndisponivel
        erro = exc or SiteIndisponivel(self.MOTIVO)
        criadas = []

        class _EmBranco(carteiro_mod.SessaoDuble):
            def abrir_casa(self, url):
                raise erro

            def novo_chat(self):
                self.casas_novas += 1
                raise erro

        @contextmanager
        def abrir(ia):
            sessao = _EmBranco(ia)
            criadas.append(sessao)
            yield sessao

        abrir.criadas = criadas
        return abrir

    def _casa_antiga(self):
        correio.gravar_casa("grok", {**correio.casa("grok"), "url": "https://grok.com/c/1",
                                     "geracao": 3, "mensagens": 9})

    def test_casa_em_branco_nao_vira_casa_nova(self):
        self._casa_antiga()
        fabrica = self._fabrica()
        c = _novo(fabrica=fabrica)
        correio.enviar("grok", "oi")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "indisponivel")
        self.assertIn("não é o login", fim["erro"])
        self.assertEqual(fabrica.criadas[0].casas_novas, 0, "nao abre chat novo no site fora")
        casa = correio.casa("grok")
        self.assertEqual((casa["url"], casa["geracao"], casa["mensagens"]),
                         ("https://grok.com/c/1", 3, 9))
        self.assertEqual(int(casa.get("falhas_seguidas") or 0), 0,
                         "a casa nao tem culpa: duas falhas assim a abandonariam")

    def test_pedido_de_imagem_em_branco_tira_o_grok_do_rodizio(self):
        c = _novo(fabrica=self._fabrica(), ajustes={"rodizio_imagem": ["grok", "chatgpt"]})
        correio.pedir_imagem("livre", "um gato laranja", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "indisponivel")
        self.assertEqual(fim["gerador"], "grok")
        self.assertTrue(fim.get("pausa_rodizio"))
        self.assertIn("indisponivel", imagem.fora_de_cota("grok"))
        c2 = _novo(ajustes={"rodizio_imagem": ["grok", "chatgpt"]})
        correio.pedir_imagem("livre", "x", proporcao="1:1")
        self.assertEqual(c2.uma_volta()["gerador"], "chatgpt")

    def test_login_caido_continua_como_era(self):
        from contos.llm.cliente import NaoLogado
        self._casa_antiga()
        c = _novo(fabrica=self._fabrica(NaoLogado("a sessao do grok nao esta valida")))
        correio.enviar("grok", "oi")
        fim = c.uma_volta()
        self.assertEqual(fim["categoria"], "login")
        self.assertFalse(fim.get("pausa_rodizio"))
        self.assertEqual(correio.casa("grok")["falhas_seguidas"], 1)


class Disco(_Base):
    def test_guardar_recusa_o_que_nao_e_imagem(self):
        with self.assertRaises(imagem.ImagemInvalida):
            imagem.guardar("picasso", "abcdef12", b"<html>" + b"x" * 900,
                           {"comprovada": True})
        with self.assertRaises(imagem.ImagemInvalida):
            imagem.guardar("picasso", "abcdef12", b"\x89PNG", {"comprovada": True})
        with self.assertRaises(imagem.SemProva):
            imagem.guardar("picasso", "abcdef12", imagem.png_de_teste(), {})
        with self.assertRaises(imagem.ImagemInvalida):
            imagem.guardar("picasso", "../x", imagem.png_de_teste(), {"comprovada": True})

    def test_png_de_teste_e_png_de_verdade(self):
        corpo = imagem.png_de_teste(40, 30)
        self.assertEqual(imagem.extensao(corpo), ".png")
        from io import BytesIO

        from PIL import Image
        with Image.open(BytesIO(corpo)) as img:
            self.assertEqual(img.size, (40, 30))
        self.assertEqual(imagem.extensao(b"\xff\xd8\xff\xe0" + b"0" * 600), ".jpg")
        self.assertEqual(imagem.extensao(b"RIFF1234WEBPVP8 " + b"0" * 600), ".webp")

    def test_pedido_de_imagem_no_chat_nao_e_pedido_de_texto(self):
        texto = imagem.pedido_de_imagem("um gato", "1:1")
        self.assertNotIn("PEDIDO DE TEXTO", texto)
        self.assertIn("1:1", texto)
        self.assertTrue(texto.rstrip().endswith("um gato"))


if __name__ == "__main__":
    unittest.main()


class CarteiroImagemNovaERede(_Base):
    def test_texto_depois_da_imagem_volta_para_a_casa(self):
        fabrica = carteiro_mod.fabrica_duble()
        c = _novo(fabrica=fabrica)
        correio.enviar("grok", "oi")
        correio.pedir_imagem("grok", "um gato", proporcao="1:1")
        c.ajustes["janela_conversa_s"] = 1
        c.uma_volta()
        url_casa = correio.casa("grok")["url"]
        # a 1a conversa nova e a casa; a 2a e a da imagem, que nunca vira casa
        self.assertIn("/grok/c/1-", url_casa or "")

    def test_recusa_de_imagem_tenta_uma_vez_em_conversa_nova(self):
        tentativas = []

        def gerar(prompt):
            tentativas.append(prompt)
            if len(tentativas) == 1:
                raise imagem.SemImagem("o Gemini respondeu sem imagem: «sou um modelo de linguagem»")
            return None
        fabrica = carteiro_mod.fabrica_duble(antes_de_gerar=gerar)
        c = _novo(fabrica=fabrica)
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "respondida")
        self.assertTrue(tentativas[1].startswith(carteiro_mod.REFORCO_IMAGEM))
        self.assertTrue(correio.arquivo_da_imagem("gemini", m["id"]).is_file())

    def test_rede_caida_volta_para_a_fila(self):
        fabrica = carteiro_mod.fabrica_duble(
            imagem_falhar=RuntimeError("Page.goto: net::ERR_NAME_NOT_RESOLVED at https://gemini.google.com/app"))
        c = _novo(fabrica=fabrica)
        esperas = []
        c.dormir = esperas.append
        m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
        c.uma_volta()
        atual = correio.uma("gemini", m["id"])
        self.assertEqual(atual["situacao"], "pendente")
        self.assertEqual(atual["rede_tentativas"], 1)
        self.assertEqual(esperas, [60])
        for _ in range(carteiro_mod.REDE_TENTATIVAS):
            c.uma_volta()
        self.assertEqual(correio.uma("gemini", m["id"])["situacao"], "falhou")


class RodizioDivide(_Base):
    """03/10/2026: Gemini, ChatGPT e Picasso DIVIDEM - vai quem gerou ha mais tempo."""

    def test_quem_gerou_ha_mais_tempo_vem_primeiro(self):
        from unittest import mock
        with mock.patch.object(imagem, "_config", lambda: {"rodizio_imagem": ["gemini", "chatgpt", "picasso"]}):
            self.assertEqual(imagem.rodizio_ordem(), ["gemini", "chatgpt", "picasso"])  # ninguem gerou
            m = correio.pedir_imagem("gemini", "um gato", proporcao="1:1")
            correio.atualizar("gemini", m["id"], situacao="respondida", gerador="gemini",
                              respondida_em="2026-10-03T10:00:00")
            m = correio.pedir_imagem("picasso", "um gato", proporcao="1:1")
            correio.atualizar("picasso", m["id"], situacao="respondida", gerador="picasso",
                              respondida_em="2026-10-03T09:00:00")
            self.assertEqual(imagem.rodizio_ordem(), ["chatgpt", "picasso", "gemini"])
