# -*- coding: utf-8 -*-
"""O correio e o carteiro, com dublê: nenhum teste abre navegador, toca o
Telegram ou o `%LOCALAPPDATA%` real (a raiz vai para `NF_IAS_PASTA`).

Cobre o que a fase 2 prometeu: o caso ZERO do correio, o carteiro
entregando e falhando, a prioridade (trava ocupada pela pipeline -> espera,
nunca mata), a casa persistente (reabre; inutilizavel -> casa nova com o
resumo), o resumo periodico e o catalogo de erros virando motivo legivel.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from ias import carteiro as carteiro_mod, correio


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


# ================================================================ correio
class CorreioCasoZero(_Base):
    def test_sem_pasta_nada_quebra_e_tudo_e_zero(self):
        self.assertEqual(correio.ler("deepseek"), [])
        self.assertEqual(correio.historico("grok"), [])
        self.assertEqual(correio.pendentes("gemini"), [])
        self.assertIsNone(correio.proxima_pendente())
        r = correio.resumo()
        self.assertEqual(set(r), set(correio.CHATS))
        for ia in correio.CHATS:
            self.assertEqual(r[ia]["pendentes"], 0)
            self.assertEqual(r[ia]["nao_vistas"], 0)
            self.assertIsNone(r[ia]["ultima"])
        self.assertEqual(correio.estado_do_carteiro()["situacao"], "nunca")
        self.assertFalse(correio.app_esta_olhando("deepseek"))
        self.assertEqual(correio.casa("chatgpt")["geracao"], 0)
        self.assertEqual(correio.resumo_da_casa("chatgpt"), "")

    def test_ia_que_nao_conversa_e_recusada(self):
        with self.assertRaises(correio.CorreioInvalido):
            correio.enviar("picasso", "oi")
        with self.assertRaises(correio.CorreioInvalido):
            correio.ler("digen")


class CorreioEscreveEDobra(_Base):
    def test_enviar_e_pendente_e_a_thread_e_a_casa(self):
        m = correio.enviar("deepseek", "  PEDIDO DE TEXTO: responda só OK  ")
        self.assertEqual(m["situacao"], "pendente")
        self.assertEqual(m["para"], "deepseek")
        self.assertEqual(m["de"], "adrian")
        self.assertEqual(m["thread"], "casa:deepseek")
        self.assertEqual(m["texto"], "PEDIDO DE TEXTO: responda só OK")
        self.assertEqual(correio.pendentes("deepseek")[0]["id"], m["id"])
        self.assertEqual(correio.proxima_pendente()["id"], m["id"])

    def test_texto_vazio_e_anexo_inexistente_sao_recusados(self):
        with self.assertRaises(correio.CorreioInvalido):
            correio.enviar("deepseek", "   ")
        with self.assertRaises(correio.CorreioInvalido):
            correio.enviar("deepseek", "oi", anexos=["nao/existe.png"])

    def test_deltas_dobram_e_o_arquivo_so_cresce(self):
        m = correio.enviar("gemini", "oi")
        tamanho1 = correio.arquivo("gemini").stat().st_size
        correio.atualizar("gemini", m["id"], situacao="entregue", entregue_em="x")
        d = correio.atualizar("gemini", m["id"], situacao="respondida", resposta="OK")
        self.assertEqual(d["situacao"], "respondida")
        self.assertEqual(d["resposta"], "OK")
        self.assertEqual(d["entregue_em"], "x")
        self.assertEqual(d["texto"], "oi")
        self.assertGreater(correio.arquivo("gemini").stat().st_size, tamanho1)
        linhas = correio.arquivo("gemini").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(linhas), 3)
        self.assertEqual(len(correio.ler("gemini")), 1)

    def test_situacao_inventada_e_recusada(self):
        m = correio.enviar("gemini", "oi")
        with self.assertRaises(correio.CorreioInvalido):
            correio.atualizar("gemini", m["id"], situacao="sumiu")

    def test_linha_ilegivel_e_delta_orfao_sao_pulados_e_contados(self):
        m = correio.enviar("chatgpt", "a")
        with open(correio.arquivo("chatgpt"), "a", encoding="utf-8") as fh:
            fh.write('{"id": "zzzz", "situacao": "respondida"}\n')
            fh.write('{"meia linha\n')
        self.assertEqual([x["id"] for x in correio.ler("chatgpt")], [m["id"]])
        self.assertEqual(correio.resumo()["chatgpt"]["ilegiveis"], 2)

    def test_proxima_pendente_e_a_mais_velha_entre_todas_as_caixas(self):
        a = correio.enviar("grok", "1")
        with open(correio.arquivo("grok"), "a", encoding="utf-8") as fh:
            pass
        b = correio.enviar("deepseek", "2")
        # forca `em` mais velho na segunda
        with open(correio.arquivo("deepseek"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({**b, "em": "2020-01-01T00:00:00"}) + "\n")
        self.assertEqual(correio.proxima_pendente()["id"], b["id"])
        correio.atualizar("deepseek", b["id"], situacao="respondida", resposta="x")
        self.assertEqual(correio.proxima_pendente()["id"], a["id"])

    def test_vistas_e_resumo(self):
        m = correio.enviar("deepseek", "oi")
        correio.atualizar("deepseek", m["id"], situacao="respondida", resposta="OK")
        r = correio.resumo()["deepseek"]
        self.assertEqual((r["pendentes"], r["nao_vistas"], r["total"]), (0, 1, 1))
        self.assertEqual(r["ultima"]["resposta"], "OK")
        self.assertEqual(correio.marcar_vistas("deepseek"), 1)
        self.assertEqual(correio.resumo()["deepseek"]["nao_vistas"], 0)
        self.assertEqual(correio.marcar_vistas("deepseek"), 0)

    def test_anexo_so_imagem_e_vai_para_a_pasta_da_ia(self):
        destino = correio.guardar_anexo("gemini", "foto.PNG", b"\x89PNG" + b"x" * 100)
        self.assertTrue(destino.is_file())
        self.assertIn("anexos", str(destino))
        with self.assertRaises(correio.CorreioInvalido):
            correio.guardar_anexo("gemini", "virus.exe", b"x" * 10)
        with self.assertRaises(correio.CorreioInvalido):
            correio.guardar_anexo("gemini", "vazia.png", b"")
        m = correio.enviar("gemini", "o que é isto?", anexos=[destino])
        self.assertEqual(m["anexos"], [str(destino)])

    def test_casa_vai_e_volta(self):
        c = correio.casa("grok")
        c["url"] = "https://grok.com/c/abc"
        c["mensagens"] = 3
        correio.gravar_casa("grok", c)
        lida = correio.casa("grok")
        self.assertEqual(lida["url"], "https://grok.com/c/abc")
        self.assertEqual(lida["mensagens"], 3)
        self.assertEqual(lida["falhas_seguidas"], 0)
        correio.gravar_resumo_da_casa("grok", "combinamos X")
        self.assertIn("combinamos X", correio.resumo_da_casa("grok"))

    def test_presenca_do_app(self):
        correio.registrar_presenca("correio:deepseek")
        self.assertTrue(correio.app_esta_olhando("deepseek"))
        self.assertFalse(correio.app_esta_olhando("gemini"))
        self.assertFalse(correio.app_esta_olhando("deepseek", janela_s=0.0,
                                                  agora_s=10 ** 12))

    def test_estado_do_carteiro_vivo_e_parado(self):
        correio.gravar_estado_do_carteiro({"situacao": "entregando", "ia": "deepseek"})
        e = correio.estado_do_carteiro()
        self.assertEqual(e["situacao"], "entregando")
        self.assertTrue(e["vivo"])                     # este processo existe
        # pulso velho demais = parado, mesmo com o PID vivo
        velho = correio.estado_do_carteiro(agora_s=10 ** 12)
        self.assertEqual(velho["situacao"], "parado")


# =============================================================== carteiro
@contextmanager
def _trava_livre(nome, esperar=0.0):
    yield True


class _TravaOcupadaAte:
    """A pipeline segura a conta por N tentativas; depois solta."""

    def __init__(self, tentativas: int):
        self.restantes = tentativas
        self.pedidos = 0

    @contextmanager
    def __call__(self, nome, esperar=0.0):
        self.pedidos += 1
        if self.restantes > 0:
            self.restantes -= 1
            yield False
        else:
            yield True


def _novo(fabrica, **kw):
    avisos = []
    kw.setdefault("trava", _trava_livre)
    kw.setdefault("nome_da_trava", lambda ia: f"perfil__{ia}__teste")
    kw.setdefault("avisar", avisos.append)
    kw.setdefault("log", lambda m: None)
    kw.setdefault("dormir", lambda s: None)
    ajustes = {"janela_conversa_s": 0, "resumo_a_cada": 3, "espera_conta_max_s": 100}
    ajustes.update(kw.pop("ajustes", {}))
    c = carteiro_mod.Carteiro(fabrica_de_sessao=fabrica, ajustes=ajustes, **kw)
    c.avisos = avisos
    return c


class CarteiroEntrega(_Base):
    def test_entrega_responde_grava_casa_e_avisa_no_telegram(self):
        fabrica = carteiro_mod.fabrica_duble(responder=lambda t: "OK")
        c = _novo(fabrica)
        m = correio.enviar("deepseek", "PEDIDO DE TEXTO: responda só OK")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(fim["resposta"], "OK")
        self.assertEqual(fim["modelo"], "dublê")
        self.assertIn("entregue_em", fim)
        self.assertEqual(fabrica.criadas[0].turnos[0]["texto"], m["texto"])
        casa = correio.casa("deepseek")
        self.assertEqual(casa["geracao"], 1)
        self.assertEqual(casa["mensagens"], 1)
        self.assertTrue(casa["url"].startswith("https://duble.local/deepseek/"))
        self.assertEqual(len(c.avisos), 1)
        self.assertIn("DeepSeek respondeu", c.avisos[0])
        self.assertEqual(correio.estado_do_carteiro()["situacao"], "ocioso")
        self.assertIsNone(c.uma_volta())            # nada mais pendente

    def test_app_olhando_nao_manda_telegram(self):
        c = _novo(carteiro_mod.fabrica_duble())
        correio.enviar("gemini", "oi")
        correio.registrar_presenca("correio:gemini")
        c.uma_volta()
        self.assertEqual(c.avisos, [])

    def test_falha_vira_motivo_legivel_e_avisa(self):
        exc = RuntimeError("o deepseek nao respondeu em 420s e nao ha texto na tela")
        fabrica = carteiro_mod.fabrica_duble(
            falhar=exc, tela="Bate-papo\nYou've reached your daily limit. Try again in 3 hours\n")
        c = _novo(fabrica)
        correio.enviar("deepseek", "oi")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "limite")
        self.assertIn("o site diz", fim["erro"])
        self.assertIn("daily limit", fim["erro"])
        self.assertEqual(len(c.avisos), 1)
        self.assertIn("não consegui entregar", c.avisos[0])
        self.assertEqual(correio.casa("deepseek")["falhas_seguidas"], 1)

    def test_falha_sem_texto_na_tela_usa_a_excecao(self):
        fabrica = carteiro_mod.fabrica_duble(falhar=TimeoutError("estourou"))
        c = _novo(fabrica)
        correio.enviar("grok", "oi")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "erro")
        self.assertIn("TimeoutError", fim["erro"])

    def test_sessao_que_nem_abre_marca_a_mensagem_como_falhou(self):
        class NaoLogado(RuntimeError):
            pass

        @contextmanager
        def fabrica(ia):
            raise NaoLogado("a sessao caiu")
            yield  # pragma: no cover

        c = _novo(fabrica)
        correio.enviar("chatgpt", "oi")
        fim = c.uma_volta()
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "login")
        self.assertIn("faça login", fim["erro"])
        self.assertEqual(correio.estado_do_carteiro()["situacao"], "ocioso")


class CarteiroPrioridade(_Base):
    def test_trava_com_a_pipeline_espera_registra_e_nunca_mata(self):
        fabrica = carteiro_mod.fabrica_duble(responder=lambda t: "OK")
        trava = _TravaOcupadaAte(3)
        registros = []
        c = _novo(fabrica, trava=trava, log=registros.append)
        m = correio.enviar("gemini", "oi")
        fim = c.entregar(m)
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(trava.pedidos, 4)
        self.assertTrue(any("esta com a pipeline" in r for r in registros))
        self.assertTrue(any("soltou" in r for r in registros))
        # o rastro da espera ficou na propria mensagem
        linhas = [json.loads(x) for x in correio.arquivo("gemini")
                  .read_text(encoding="utf-8").splitlines()]
        self.assertTrue(any("esperando a pipeline soltar" in str(x.get("nota")) for x in linhas))
        self.assertIsNone(fim.get("nota"))

    def test_conta_presa_alem_do_limite_falha_com_motivo(self):
        fabrica = carteiro_mod.fabrica_duble()
        relogio = [0.0]

        def agora():
            relogio[0] += 60.0
            return relogio[0]

        c = _novo(fabrica, trava=_TravaOcupadaAte(999), relogio=agora,
                  ajustes={"espera_conta_max_s": 120})
        m = correio.enviar("gemini", "oi")
        fim = c.entregar(m)
        self.assertEqual(fim["situacao"], "falhou")
        self.assertEqual(fim["categoria"], "conta_ocupada")
        self.assertIn("ficou com a pipeline", fim["erro"])
        self.assertEqual(fabrica.criadas, [])        # nunca abriu navegador

    def test_janela_de_conversa_entrega_a_proxima_na_mesma_sessao(self):
        fabrica = carteiro_mod.fabrica_duble(responder=lambda t: "R:" + t)
        relogio = [0.0]

        def agora():
            relogio[0] += 1.0
            return relogio[0]
        c = _novo(fabrica, ajustes={"janela_conversa_s": 30}, relogio=agora)
        primeira = correio.enviar("deepseek", "um")
        # a segunda chega enquanto o carteiro segura a conta
        original = c._esperar_proxima
        chamadas = []

        def esperar(ia):
            if not chamadas:
                chamadas.append(1)
                correio.enviar("deepseek", "dois")
            return original(ia)
        c._esperar_proxima = esperar
        c.entregar(primeira)
        self.assertEqual(len(fabrica.criadas), 1)           # UMA sessao
        self.assertEqual([t["texto"] for t in fabrica.criadas[0].turnos], ["um", "dois"])
        self.assertEqual([m["situacao"] for m in correio.ler("deepseek")],
                         ["respondida", "respondida"])


class CarteiroCasa(_Base):
    def test_casa_persistente_e_reaberta_na_segunda_entrega(self):
        fabrica = carteiro_mod.fabrica_duble()
        c = _novo(fabrica)
        correio.enviar("deepseek", "um")
        c.uma_volta()
        url = correio.casa("deepseek")["url"]
        correio.enviar("deepseek", "dois")
        c.uma_volta()
        self.assertEqual(len(fabrica.criadas), 2)
        self.assertEqual(fabrica.criadas[1].casas_novas, 0)   # reabriu, nao criou
        self.assertEqual(fabrica.criadas[1].url(), url)
        casa = correio.casa("deepseek")
        self.assertEqual((casa["geracao"], casa["mensagens"]), (1, 2))

    def test_casa_inutilizavel_vira_casa_nova_com_o_resumo_primeiro(self):
        fabrica = carteiro_mod.fabrica_duble(casa_abre=False)
        c = _novo(fabrica)
        correio.gravar_casa("gemini", {**correio.casa("gemini"), "url": "https://x/1",
                                       "geracao": 1, "mensagens": 7})
        correio.gravar_resumo_da_casa("gemini", "combinamos: histórias curtas")
        correio.enviar("gemini", "e agora?")
        c.uma_volta()
        s = fabrica.criadas[0]
        self.assertEqual(s.casas_novas, 1)
        self.assertEqual(len(s.turnos), 2)
        self.assertTrue(s.turnos[0]["texto"].startswith(carteiro_mod.PROLOGO_CASA_NOVA))
        self.assertIn("histórias curtas", s.turnos[0]["texto"])
        self.assertEqual(s.turnos[1]["texto"], "e agora?")
        casa = correio.casa("gemini")
        self.assertEqual(casa["geracao"], 2)
        self.assertTrue(casa["comecou_com_resumo"])
        self.assertEqual(casa["mensagens"], 1)

    def test_duas_falhas_seguidas_abrem_casa_nova(self):
        fabrica = carteiro_mod.fabrica_duble()
        c = _novo(fabrica)
        correio.gravar_casa("grok", {**correio.casa("grok"), "url": "https://grok.com/c/1",
                                     "geracao": 1, "falhas_seguidas": 2})
        correio.enviar("grok", "oi")
        c.uma_volta()
        self.assertEqual(fabrica.criadas[0].casas_novas, 1)
        self.assertEqual(correio.casa("grok")["geracao"], 2)

    def test_resumo_periodico_a_cada_n_mensagens(self):
        fabrica = carteiro_mod.fabrica_duble(
            responder=lambda t: "RESUMO: tudo combinado" if "resuma" in t else "OK")
        c = _novo(fabrica, ajustes={"resumo_a_cada": 3})
        for n in range(3):
            correio.enviar("deepseek", f"m{n}")
            c.uma_volta()
        self.assertIn("tudo combinado", correio.resumo_da_casa("deepseek"))
        casa = correio.casa("deepseek")
        self.assertEqual(casa["resumo_mensagens"], 3)
        self.assertIsNotNone(casa["ultimo_resumo_em"])
        # o pedido de resumo nao virou mensagem do correio
        self.assertEqual(len(correio.ler("deepseek")), 3)
        pedidos = [t["texto"] for s in fabrica.criadas for t in s.turnos]
        self.assertEqual(pedidos.count(carteiro_mod.PEDIDO_RESUMO), 1)
        # a quarta nao pede outro resumo
        correio.enviar("deepseek", "m3")
        c.uma_volta()
        pedidos = [t["texto"] for s in fabrica.criadas for t in s.turnos]
        self.assertEqual(pedidos.count(carteiro_mod.PEDIDO_RESUMO), 1)


class CatalogoViraMotivo(unittest.TestCase):
    def test_texto_conhecido_da_ficha_do_gemini(self):
        tela = ("Gemini\nSou uma IA com base em texto, e isso está além das minhas "
                "capacidades\nEnviar")
        categoria, motivo = carteiro_mod.classificar_erro(
            "gemini", RuntimeError("nao respondeu"), tela)
        # a recusa enlatada e resposta, nao aviso de site: cai na varredura
        self.assertIn(categoria, ("recusa_enlatada", "erro"))
        cat2, motivo2 = carteiro_mod.classificar_erro(
            "gemini", RuntimeError("x"), "Algo deu errado (1155)\n")
        self.assertEqual(cat2, "erro_site")
        self.assertIn("1155", motivo2)

    def test_cloudflare_e_login(self):
        cat, _ = carteiro_mod.classificar_erro("chatgpt", RuntimeError("x"),
                                                "Just a moment...\nchatgpt.com")
        self.assertEqual(cat, "cloudflare")

        class NaoLogado(RuntimeError):
            pass
        cat, motivo = carteiro_mod.classificar_erro("chatgpt", NaoLogado("caiu"))
        self.assertEqual(cat, "login")
        self.assertIn("llm login --provedor chatgpt", motivo)

    def test_sem_nada_conhecido_e_a_excecao_curta(self):
        cat, motivo = carteiro_mod.classificar_erro("grok", ValueError("x" * 500), "")
        self.assertEqual(cat, "erro")
        self.assertLess(len(motivo), 260)


class SessaoRealComAnexo(unittest.TestCase):
    """O anexo so e recusado na hora para quem NAO sabe prova-lo na tela.

    Ate 29/09/2026 o DeepSeek estava nesse caso (`anexo_prova` vazio); o site
    aceita imagem, e a prova (miniatura + botao de enviar de volta) entrou em
    `contos/llm/seletores.py` (tarefa dc176b96)."""

    def _sessao(self, provedor, sel_):
        chamadas = []

        class _Cli:
            pass
        cli = _Cli()
        cli.provedor, cli.sel = provedor, sel_
        cli.perguntar = lambda texto, anexos=None: chamadas.append(anexos) or "vermelho"
        return carteiro_mod.SessaoReal(cli, log=lambda *_a: None), chamadas

    def test_imagem_para_o_deepseek_chega_ao_cliente(self):
        from contos.llm import seletores
        sessao, chamadas = self._sessao("deepseek", seletores.DEEPSEEK)
        self.assertEqual(sessao.perguntar("que cor?", anexos=["a.png"]), "vermelho")
        self.assertEqual(chamadas, [["a.png"]])

    def test_quem_nao_prova_anexo_recusa_na_hora_com_motivo(self):
        from contos.llm.cliente import LLMFalhou
        sessao, chamadas = self._sessao("outra", {"anexo_prova": []})
        with self.assertRaises(LLMFalhou) as erro:
            sessao.perguntar("que cor?", anexos=["a.png"])
        self.assertIn("mande sem anexo", str(erro.exception))
        self.assertEqual(chamadas, [])
        # sem anexo, passa
        self.assertEqual(sessao.perguntar("oi"), "vermelho")


class ConfigDoCarteiro(unittest.TestCase):
    def test_config_json_tem_as_chaves_e_padroes_sensatos(self):
        c = carteiro_mod.config()
        for chave in ("resumo_a_cada", "janela_conversa_s", "espera_conta_max_s",
                      "resposta_timeout_s", "headless"):
            self.assertIn(chave, c)
        self.assertGreaterEqual(c["resumo_a_cada"], 3)
        self.assertFalse(c["headless"].get("chatgpt", False))   # Cloudflare em headless


if __name__ == "__main__":
    unittest.main()
