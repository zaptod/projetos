"""Prova de origem: nada entra na build sem provar que nasceu do NOSSO prompt.

As contas do PicassoIA e do Digen sao compartilhadas com outras pessoas. Em
generation_00044 o worker aceitou, como referencia da build, a foto de outra
pessoa: ela apareceu no historico da conta 0,1 s depois do envio, era retrato,
e "nova na tela depois do clique" era toda a regra. O que este arquivo trava:

1. O card do historico que traz o prompt enviado e o escolhido; card de outro
   prompt, card anterior ao envio e prefixo curto demais nao contam.
2. Sem prova, o worker NAO baixa, NAO grava e conta a tentativa como falha —
   e o historico registra `origem_recusada`.
3. Com prova, o metadado do slot carrega a origem, e a URL fica reivindicada:
   outra build nunca aceita a mesma imagem.
4. O candidato que a espera devolveu e descartado quando o historico atribui
   outra imagem ao nosso prompt — baixa-se a do card.
5. `exigir: false` registra a prova mas nao barra (rollback), e a config
   versionada exige.
6. A auditoria aponta como SUSPEITO o artefato antigo que "ficou pronto" rapido
   demais para ter sido gerado, e a quarentena move (nunca apaga) e reenfileira.

Rode de dentro de random_builds/:
    python -m unittest discover -s tests -p "test_*.py"
"""
from __future__ import annotations

import inspect
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image                                                # noqa: E402

from src.identity import artefato, auditoria, history, proveniencia, slots  # noqa: E402
from src.identity import config as icfg                             # noqa: E402
from src.identity import picasso_selectors                          # noqa: E402
from src.identity import queue as fila                              # noqa: E402
from src.identity.client import GeracaoFalhou                       # noqa: E402

GID = "generation_88888"
PROMPT = ("Full-body character sheet portrait of Hakon Vyrpunth, a towering male "
          "raging berserker, athletic at 5.5 strength, 1.91 m tall, with a brawling "
          "presence and a steady arcane charge at the fingertips at 6.1 mana. "
          "Signature color vivid green (#72dd2a) runs through the armor trim, the "
          "cloth and the aura. Vertical 9:16. No text, no watermark, no logo.")
OUTRO = ("A very beautiful woman with tanned skin and a seductive gaze, long light "
         "blonde curly hair, loose surf shirt and tied sarong, small shell necklace, "
         "hippie bracelets, relaxed cool artistic vibe, soft natural lighting, "
         "sitting at a cafe table outdoors holding a cup of coffee, smiling.")
BUCKET = "https://pub-7388517e4cb848f899900623842f083b.r2.dev/text-to-image/uid/picassoia-image/"
NOSSA = BUCKET + "nossa.jpg"
ALHEIA = BUCKET + "alheia.jpg"


def _card(indice, prompt, data="25 DE AGO. DE 2026, 22:26", imagens=()):
    return {"indice": indice, "prompt": prompt,
            "texto": f"{prompt}\nVer mais\nCopiar prompt\n9:16\njpg\n4.59s\n{data}",
            "imagens": list(imagens)}


def _local(ano, mes, dia, hora, minuto) -> datetime:
    """Hora LOCAL, aware — como o worker grava o envio."""
    return datetime(ano, mes, dia, hora, minuto).astimezone()


class EscolhaDeCardTests(unittest.TestCase):
    def test_o_card_com_o_prompt_e_o_escolhido_mesmo_nao_sendo_o_primeiro(self):
        cards = [_card(0, OUTRO, imagens=[ALHEIA]), _card(1, PROMPT, imagens=[NOSSA])]
        escolha = proveniencia.escolher_card(cards, PROMPT)
        self.assertEqual(1, escolha["card"]["indice"])

    def test_sem_card_com_o_prompt_nao_ha_escolha(self):
        escolha = proveniencia.escolher_card([_card(0, OUTRO, imagens=[ALHEIA])], PROMPT)
        self.assertIsNone(escolha["card"])
        self.assertIn("prompt", escolha["motivo"])

    def test_card_truncado_pela_tela_ainda_casa(self):
        truncado = PROMPT[:200] + "…"
        self.assertTrue(proveniencia.prompt_bate(truncado, PROMPT))

    def test_prefixo_curto_demais_nao_casa(self):
        """'Full-body character sheet portrait of' casa com toda roleta."""
        self.assertFalse(proveniencia.prompt_bate(PROMPT[:40], PROMPT))

    def test_espacos_e_caixa_nao_importam(self):
        self.assertTrue(proveniencia.prompt_bate("  " + PROMPT.upper().replace(" ", "  "), PROMPT))

    def test_card_anterior_ao_envio_e_recusado(self):
        """Prompt igual, mas de uma build antiga: o envio foi DEPOIS do card."""
        cards = [_card(0, PROMPT, data="25 DE AGO. DE 2026, 22:26", imagens=[ALHEIA])]
        envio = _local(2026, 8, 25, 22, 40)
        escolha = proveniencia.escolher_card(cards, PROMPT, envio, tolerancia_min=3)
        self.assertIsNone(escolha["card"])
        self.assertIn("anterior", escolha["motivo"])

    def test_card_dentro_da_tolerancia_passa(self):
        cards = [_card(0, PROMPT, data="25 DE AGO. DE 2026, 22:39", imagens=[NOSSA])]
        envio = _local(2026, 8, 25, 22, 40)
        self.assertIsNotNone(proveniencia.escolher_card(cards, PROMPT, envio, 3)["card"])

    def test_data_ilegivel_nao_recusa(self):
        cards = [_card(0, PROMPT, data="", imagens=[NOSSA])]
        envio = _local(2026, 8, 25, 22, 40)
        self.assertIsNotNone(proveniencia.escolher_card(cards, PROMPT, envio)["card"])

    def test_leitura_da_data_do_card(self):
        self.assertEqual(datetime(2026, 8, 25, 22, 26),
                         proveniencia.data_do_card("... GRÁTIS\n25 DE AGO. DE 2026, 22:26\nIMAGE"))
        self.assertEqual(datetime(2026, 1, 3, 9, 5),
                         proveniencia.data_do_card("3 DE JAN. DE 2026, 9:05"))
        self.assertIsNone(proveniencia.data_do_card("sem data nenhuma"))
        self.assertIsNone(proveniencia.data_do_card("31 DE FEV. DE 2026, 10:00"))


class PresetsDoDigenTests(unittest.TestCase):
    TEXTO = "🎭\nHakon morphing blade\nRM3.5\n3s\n480P"
    PRESETS = {"modelo": "RM3.5", "duracao": "3s", "resolucao": "480P", "aspecto": "9:16"}

    def test_presets_iguais_batem(self):
        self.assertTrue(proveniencia.presets_batem(self.TEXTO, self.PRESETS))

    def test_preset_diferente_e_evidencia_de_card_alheio(self):
        self.assertFalse(proveniencia.presets_batem(
            self.TEXTO, {**self.PRESETS, "duracao": "5s"}))

    def test_sem_texto_ou_sem_presets_nao_da_para_conferir(self):
        self.assertIsNone(proveniencia.presets_batem(None, self.PRESETS))
        self.assertIsNone(proveniencia.presets_batem(self.TEXTO, {}))
        self.assertIsNone(proveniencia.presets_batem(self.TEXTO, {"aspecto": "9:16"}))


class _Cliente:
    """Cliente de mentira com a porta que o worker usa (duck typing)."""
    PROVEDOR = "picasso"

    def __init__(self, candidato, prova):
        self.url_do_espaco = picasso_selectors.URL_CRIACAO
        self.presets_aplicados = {"modelo": "PICASSOIA IMAGE", "aspecto": "9:16"}
        self.prompt_enviado = None
        self.enviado_em = None
        self._candidato = candidato
        self._prova = prova
        self.baixou = []

    def preparar_espaco(self, espaco):
        return []

    def abrir_espaco(self, url):
        pass

    def submit_prompt(self, prompt, aspect="9:16", modelo=None, duracao=None,
                      resolucao=None, espaco=None, antes=None):
        self.prompt_enviado = prompt
        self.enviado_em = datetime.now(timezone.utc)
        return []

    def wait_for_render(self, timeout=None, antes=None):
        return self._candidato

    def comprovar_origem(self, alvo, prompt, enviado_em=None):
        return self._prova(alvo, prompt, enviado_em) if callable(self._prova) else self._prova

    def download(self, alvo, dest):
        self.baixou.append(alvo)
        dest.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (400, 700), (10, 90, 40)).save(dest)
        return dest

    def creditos(self, espera=0.0):
        return None

    def presets_atuais(self):
        return dict(self.presets_aplicados)


class _Isolado(unittest.TestCase):
    """outputs/, fila, historico e registro de origens em pasta temporaria."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self._guardado = (icfg.OUTPUTS, fila.ARQUIVO_FILA, history.ARQUIVO,
                          proveniencia.ARQUIVO_ORIGENS)
        icfg.OUTPUTS = base / "outputs"
        fila.ARQUIVO_FILA = base / "queue.json"
        history.ARQUIVO = base / "history.jsonl"
        proveniencia.ARQUIVO_ORIGENS = base / "origens.jsonl"
        (icfg.OUTPUTS / GID).mkdir(parents=True)

    def tearDown(self):
        (icfg.OUTPUTS, fila.ARQUIVO_FILA, history.ARQUIVO,
         proveniencia.ARQUIVO_ORIGENS) = self._guardado
        self._tmp.cleanup()


class RegistroDeOrigensTests(_Isolado):
    def test_reivindicar_e_listar(self):
        prova = proveniencia.prova_forte("picasso", _card(0, PROMPT), NOSSA, NOSSA, PROMPT)
        proveniencia.reivindicar(prova, GID, slots.CHARACTER)
        self.assertEqual({NOSSA: (GID, slots.CHARACTER)}, proveniencia.reivindicadas())

    def test_prova_sem_url_nao_reivindica(self):
        proveniencia.reivindicar(proveniencia.prova_media(
            "digen", 0, "https://digen.ai/en/space/1", {}, "", None, PROMPT), GID, slots.CHARACTER_WEAPON)
        self.assertEqual({}, proveniencia.reivindicadas())

    def test_url_de_outra_build_derruba_a_prova(self):
        prova = proveniencia.prova_forte("picasso", _card(0, PROMPT), NOSSA, NOSSA, PROMPT)
        proveniencia.reivindicar(prova, "generation_00001", slots.CHARACTER)
        cliente = _Cliente(NOSSA, prova)
        resultado = proveniencia.comprovar(cliente, GID, slots.CHARACTER, PROMPT, None, NOSSA, {})
        self.assertFalse(resultado["comprovada"])
        self.assertIn("generation_00001", resultado["motivo"])

    def test_a_propria_build_pode_reivindicar_de_novo(self):
        """Retomada depois de queda: a mesma URL, o mesmo slot."""
        prova = proveniencia.prova_forte("picasso", _card(0, PROMPT), NOSSA, NOSSA, PROMPT)
        proveniencia.reivindicar(prova, GID, slots.CHARACTER)
        resultado = proveniencia.comprovar(_Cliente(NOSSA, prova), GID, slots.CHARACTER,
                                           PROMPT, None, NOSSA, {})
        self.assertTrue(resultado["comprovada"])


class WorkerTests(_Isolado):
    AJUSTES = {"proveniencia": {"exigir": True}, "aspect": "9:16"}

    def setUp(self):
        super().setUp()
        from src.identity import worker
        self.worker = worker
        self.job = fila.enqueue(GID, PROMPT, slot=slots.CHARACTER)

    def _processar(self, cliente, ajustes=None):
        return self.worker.processar(cliente, dict(self.job), ajustes or self.AJUSTES,
                                     rerender=False)

    def _metadado(self):
        return artefato.metadados(GID, slots.CHARACTER)

    def test_sem_prova_nada_e_baixado_nem_gravado(self):
        cliente = _Cliente(ALHEIA, proveniencia.sem_prova("picasso", "teste", ALHEIA))
        with self.assertRaises(GeracaoFalhou) as ctx:
            self._processar(cliente)
        self.assertIn("prova de origem", str(ctx.exception))
        self.assertEqual([], cliente.baixou)
        self.assertFalse(artefato.caminho(GID, slots.CHARACTER).is_file())
        eventos = [e["evento"] for e in history.ler()]
        self.assertIn(history.ORIGEM_RECUSADA, eventos)
        self.assertNotIn(history.BAIXADO, eventos)
        job = next(j for j in fila.listar() if j["job_id"] == self.job["job_id"])
        self.assertFalse(job["enviado"], "a proxima tentativa tem que gerar de novo")

    def test_com_prova_o_metadado_carrega_a_origem_e_a_url_fica_reivindicada(self):
        def prova(alvo, prompt, enviado_em):
            return proveniencia.prova_forte("picasso", _card(0, prompt, imagens=[NOSSA]),
                                            NOSSA, alvo, prompt, enviado_em)
        cliente = _Cliente(NOSSA, prova)
        self._processar(cliente)
        self.assertTrue(artefato.caminho(GID, slots.CHARACTER).is_file())
        origem = self._metadado()["origem"]
        self.assertTrue(origem["comprovada"])
        self.assertEqual(proveniencia.FORTE, origem["forca"])
        self.assertEqual(NOSSA, origem["url"])
        self.assertFalse(origem["candidato_descartado"])
        self.assertEqual({NOSSA: (GID, slots.CHARACTER)}, proveniencia.reivindicadas())

    def test_candidato_alheio_e_trocado_pela_imagem_do_card(self):
        """O que apareceu primeiro era de outra pessoa; baixa-se o do card."""
        def prova(alvo, prompt, enviado_em):
            return proveniencia.prova_forte("picasso", _card(1, prompt, imagens=[NOSSA]),
                                            NOSSA, alvo, prompt, enviado_em)
        cliente = _Cliente(ALHEIA, prova)
        self._processar(cliente)
        self.assertEqual([NOSSA], cliente.baixou)
        self.assertTrue(self._metadado()["origem"]["candidato_descartado"])

    def test_o_prompt_conferido_e_o_que_entrou_no_campo(self):
        visto = {}

        def prova(alvo, prompt, enviado_em):
            visto["prompt"] = prompt
            visto["enviado_em"] = enviado_em
            return proveniencia.prova_forte("picasso", _card(0, prompt, imagens=[NOSSA]),
                                            NOSSA, alvo, prompt, enviado_em)
        self._processar(_Cliente(NOSSA, prova))
        self.assertEqual(PROMPT, visto["prompt"])
        self.assertIsInstance(visto["enviado_em"], datetime)

    def test_exigir_false_registra_mas_nao_barra(self):
        cliente = _Cliente(ALHEIA, proveniencia.sem_prova("picasso", "teste", ALHEIA))
        self._processar(cliente, {"proveniencia": {"exigir": False}, "aspect": "9:16"})
        self.assertEqual([ALHEIA], cliente.baixou)
        self.assertFalse(self._metadado()["origem"]["comprovada"])

    def test_url_ja_reivindicada_por_outra_build_e_recusada_no_worker(self):
        prova = proveniencia.prova_forte("picasso", _card(0, PROMPT, imagens=[NOSSA]),
                                         NOSSA, NOSSA, PROMPT)
        proveniencia.reivindicar(prova, "generation_00001", slots.CHARACTER)
        with self.assertRaises(GeracaoFalhou):
            self._processar(_Cliente(NOSSA, prova))
        self.assertFalse(artefato.caminho(GID, slots.CHARACTER).is_file())

    def test_a_prova_e_pedida_ANTES_do_download(self):
        fonte = inspect.getsource(self.worker.processar)
        self.assertLess(fonte.index("proveniencia.comprovar"), fonte.index("client.download"))
        self.assertLess(fonte.index("client.download"), fonte.index("proveniencia.reivindicar"))


class AuditoriaTests(_Isolado):
    def _artefato(self, gid, slot, meta=None, prompt=PROMPT):
        pasta = icfg.OUTPUTS / gid
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = pasta / slots.ARQUIVO[slot]
        if slots.midia(slot) == slots.VIDEO:
            arquivo.write_bytes(b"\x00" * 20_000)      # "mp4" que passa no piso
        else:
            Image.new("RGB", (400, 700), (10, 90, 40)).save(arquivo)
        ident = pasta / "identity"
        ident.mkdir(exist_ok=True)
        (ident / f"{slot}.prompt.txt").write_text(prompt, encoding="utf-8")
        with open(ident / f"{slot}.json", "w", encoding="utf-8") as fh:
            json.dump({"generation_id": gid, "slot": slot, "prompt": prompt, **(meta or {})}, fh)

    def test_classificacao(self):
        self._artefato(GID, slots.REFERENCIA)                      # antigo, pronto em 0,1 s
        history.registrar(GID, history.ENVIADO, slot=slots.REFERENCIA)
        history.registrar(GID, history.PRONTO, slot=slots.REFERENCIA, espera_s=0.1)
        self._artefato(GID, slots.CHARACTER, {"origem": {"comprovada": True, "forca": "forte",
                                                         "metodo": "historico_prompt"}})
        self._artefato(GID, slots.WEAPON)                          # antigo, sem historico
        estados = {ln["slot"]: ln["estado"] for ln in auditoria.classificar(GID)}
        self.assertEqual(auditoria.SUSPEITO, estados[slots.REFERENCIA])
        self.assertEqual(auditoria.OK, estados[slots.CHARACTER])
        self.assertEqual(auditoria.SEM_PROVA, estados[slots.WEAPON])
        self.assertNotIn(slots.CHARACTER_WEAPON, estados, "sem arquivo, sem linha")

    def test_espera_normal_nao_e_suspeita(self):
        self._artefato(GID, slots.WEAPON)
        history.registrar(GID, history.PRONTO, slot=slots.WEAPON, espera_s=15.1)
        self.assertEqual(auditoria.SEM_PROVA, auditoria.classificar(GID)[0]["estado"])

    def test_quarentena_move_nunca_apaga_e_reenfileira(self):
        self._artefato(GID, slots.REFERENCIA)
        original = artefato.caminho(GID, slots.REFERENCIA)
        copia_upload = original.with_name(f"{original.stem}_ref.jpg")
        copia_upload.write_bytes(b"\xff\xd8\xff" + b"0" * 600)
        movidos = auditoria.quarentenar(GID, slots.REFERENCIA, "foto de outra pessoa",
                                        reenfileirar=True, rerender=False)
        self.assertEqual(2, len(movidos))
        self.assertFalse(original.is_file())
        self.assertFalse(copia_upload.is_file())
        for caminho in movidos:
            self.assertTrue(caminho.is_file())
            self.assertEqual("quarentena", caminho.parent.name)
        self.assertEqual("foto de outra pessoa",
                         artefato.metadados(GID, slots.REFERENCIA)["quarentena"]["motivo"])
        job = next(j for j in fila.listar() if j["slot"] == slots.REFERENCIA)
        self.assertEqual(fila.PENDENTE, job["status"])
        self.assertEqual(PROMPT, job["prompt"])
        self.assertEqual(auditoria.QUARENTENA, auditoria.classificar(GID)[0]["estado"])
        self.assertIn(history.QUARENTENA, [e["evento"] for e in history.ler()])

    def test_aprovar_registra_a_verificacao_humana_e_limpa_a_suspeita(self):
        self._artefato(GID, slots.REFERENCIA)
        history.registrar(GID, history.PRONTO, slot=slots.REFERENCIA, espera_s=3.1)
        self.assertEqual(auditoria.SUSPEITO, auditoria.classificar(GID)[0]["estado"])
        self.assertTrue(auditoria.aprovar(GID, slots.REFERENCIA, "e o ninja da build"))
        linha = auditoria.classificar(GID)[0]
        self.assertEqual(auditoria.OK, linha["estado"])
        self.assertEqual(auditoria.FORCA_MANUAL, linha["forca"])
        origem = artefato.metadados(GID, slots.REFERENCIA)["origem"]
        self.assertEqual(auditoria.METODO_MANUAL, origem["metodo"])
        self.assertIn(history.APROVADO, [e["evento"] for e in history.ler()])

    def test_aprovar_sem_artefato_nao_inventa_origem(self):
        self.assertFalse(auditoria.aprovar(GID, slots.WEAPON, "x"))
        self.assertIsNone(artefato.metadados(GID, slots.WEAPON))

    def test_quarentena_sem_artefato_nao_faz_nada(self):
        self.assertEqual([], auditoria.quarentenar(GID, slots.WEAPON, "x", rerender=False))
        self.assertEqual([], fila.listar())

    def test_ultima_espera_por_slot(self):
        history.registrar(GID, history.PRONTO, slot=slots.WEAPON, espera_s=33.1)
        history.registrar(GID, history.PRONTO, slot=slots.WEAPON, espera_s=15.1)
        history.registrar(GID, history.PRONTO, slot=slots.CHARACTER)   # sem espera_s
        self.assertEqual({(GID, slots.WEAPON): 15.1}, history.ultima_espera_por_slot())

    def test_espera_depois_de_retomada_nao_mede_geracao(self):
        """generation_00039: `retomado` -> `pronto` em 4,5 s era o video ja
        pronto no espaco, nao uma geracao de 4,5 s. Nao pode virar suspeita."""
        self._artefato(GID, slots.CHARACTER_WEAPON)
        history.registrar(GID, history.ENVIADO, slot=slots.CHARACTER_WEAPON)
        history.registrar(GID, history.ESTOUROU, slot=slots.CHARACTER_WEAPON, espera_s=600.0)
        history.registrar(GID, history.RETOMADO, slot=slots.CHARACTER_WEAPON)
        history.registrar(GID, history.PRONTO, slot=slots.CHARACTER_WEAPON, espera_s=4.5)
        self.assertEqual({}, history.ultima_espera_por_slot())
        self.assertEqual(auditoria.SEM_PROVA, auditoria.classificar(GID)[0]["estado"])

    def test_envio_novo_depois_de_retomada_volta_a_medir(self):
        history.registrar(GID, history.RETOMADO, slot=slots.WEAPON)
        history.registrar(GID, history.PRONTO, slot=slots.WEAPON, espera_s=2.0)
        history.registrar(GID, history.ENVIADO, slot=slots.WEAPON)
        history.registrar(GID, history.PRONTO, slot=slots.WEAPON, espera_s=0.1)
        self.assertEqual({(GID, slots.WEAPON): 0.1}, history.ultima_espera_por_slot())


class _PaginaFake:
    def __init__(self, cards):
        self.cards = cards
        self.chamadas = []

    def evaluate(self, js, arg=None):
        self.chamadas.append(arg)
        return self.cards


class SeletoresDoHistoricoTests(unittest.TestCase):
    def test_url_do_historico_e_a_mesma_pagina_com_a_aba(self):
        self.assertEqual(picasso_selectors.URL_CRIACAO + "?tab=history",
                         picasso_selectors.url_historico(picasso_selectors.URL_CRIACAO))
        self.assertEqual(picasso_selectors.URL_EDITOR + "?tab=history",
                         picasso_selectors.url_historico(picasso_selectors.URL_EDITOR + "?x=1#y"))
        self.assertTrue(picasso_selectors.url_historico(None).endswith("?tab=history"))

    def test_cards_so_com_imagem_de_resultado(self):
        pagina = _PaginaFake([
            {"indice": 0, "prompt": PROMPT, "texto": "x",
             "imagens": ["https://picassoia.com/nextImageExportOptimizer/1-opt-10.WEBP",
                         NOSSA, NOSSA]},
            {"indice": 1, "prompt": None, "texto": None, "imagens": []},
        ])
        cards = picasso_selectors.cards_do_historico(pagina, limite=5, revelar=1)
        self.assertEqual([NOSSA], cards[0]["imagens"])
        self.assertEqual("", cards[1]["prompt"])
        self.assertEqual([[5, 1]], pagina.chamadas)

    def test_pagina_quebrada_devolve_lista_vazia(self):
        class Quebrada:
            def evaluate(self, *a):
                raise RuntimeError("fechou")
        self.assertEqual([], picasso_selectors.cards_do_historico(Quebrada()))

    def test_painel_do_historico_tem_candidato_conhecido(self):
        from src.identity import selectors
        for estrategia, _ in picasso_selectors.PAINEL_HISTORICO:
            self.assertIn(estrategia, ("css", "role", "text", "placeholder"))
        self.assertTrue(callable(selectors.texto_do_card))


class ContratoTests(unittest.TestCase):
    def test_config_versionada_exige_prova(self):
        ajustes = proveniencia.ajustes(icfg.settings())
        self.assertTrue(ajustes["exigir"])
        self.assertGreater(float(ajustes["espera_historico_s"]), 0)
        self.assertTrue(proveniencia.exigida(icfg.settings("picasso")))
        self.assertTrue(proveniencia.exigida(icfg.settings("digen")))

    def test_sem_bloco_o_padrao_e_exigir(self):
        self.assertTrue(proveniencia.exigida({}))
        self.assertTrue(proveniencia.exigida(None))
        self.assertFalse(proveniencia.exigida({"proveniencia": {"exigir": False}}))

    def test_os_dois_clientes_comprovam_origem_pela_mesma_porta(self):
        from src.identity.client import DigenClient
        from src.identity.picasso_client import PicassoClient
        for classe in (DigenClient, PicassoClient):
            assinatura = list(inspect.signature(classe.comprovar_origem).parameters)
            self.assertEqual(["self", "alvo", "prompt", "enviado_em"], assinatura)

    def test_registro_e_apagado_pela_quarentena(self):
        """origem some do metadado quando o artefato sai da build."""
        fonte = inspect.getsource(artefato.quarentenar)
        self.assertIn('meta.pop("origem"', fonte)


if __name__ == "__main__":
    unittest.main()
