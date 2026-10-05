# -*- coding: utf-8 -*-
"""Varredura de erros de 05/10/2026, parte das historias (grupo B).

Itens do relatorio, cada um com o defeito medido:

 1  57 de 58 partes RETIDAS: o conserto refazia o mp4, mas o veto do mp4
    antigo continuava valendo. Agora `parecer.consertado`/`estado_do_video`
    reconhecem a parte consertada, e a nova olhada da IA fica atras de
    `REOLHAR_DEPOIS_DO_CONSERTO` (decisao pendente do Adrian). Motivos-lixo
    ("MP4", "+ 1") saem do parecer. Na origem: genero e ficha fixa tambem
    para o elenco, e o motivo LITERAL vai ao conserto pela narracao.
 2  `_SaidaNoDiario` sem `buffer`: o `postar._linha` levantava, a publicacao
    devolvia -1 e o plano B contava as retidas (58 contra 1).
11  a recusa enlatada do Gemini derrubava a criacao ("sem cena legivel").
15  a vistoria era 74% do diario.
18  o reparo culpava "o PicassoIA" ate por colagem, e deixava o
    `imagens.json` apontando para a imagem descartada.
20  o avatar de quem esta logado casava com o seletor de "login".

Nada abre navegador, nada escreve em `outputs/` de producao.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from contos.imagens import composicao, fila
from contos.llm import cliente as llm_cliente
from contos.llm import seletores
from contos.pipeline import agenda, reparo
from contos.pipeline import conserto_de_cena as C
from contos.publicar import parecer, qualidade
from contos.roteiro import gerar
from contos.roteiro import serie as S
from contos.roteiro.modelo import carregar_config

ID = "historia_00099:celular:p03"


class _Video:
    def __init__(self, caminho, vid=ID):
        self.id = vid
        self.fonte_id = vid.split(":")[0]
        self.parte = int(vid.rsplit("p", 1)[1])
        self.perfil = "celular"
        self.caminho = Path(caminho)
        self.titulo = "t"


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pasta = Path(tmp.name)

    def _trocar(self, alvo, nome, valor):
        self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
        setattr(alvo, nome, valor)


# --------------------------------------------------------------- item 1
class _ComParecer(_Base):
    def setUp(self):
        super().setUp()
        self._trocar(parecer, "LEMBRETES", self.pasta / "_pareceres.json")
        self._trocar(reparo, "REGISTRO", self.pasta / "_reparos.json")
        self.mp4 = self.pasta / "p03.mp4"
        self.mp4.write_bytes(b"mp4 velho")
        self.video = _Video(self.mp4)
        self.agora = datetime(2026, 10, 4, 9, 0, 0)

    def _parecer(self, aprovado=False, quando=None, mtime=None):
        dados = json.loads(parecer.LEMBRETES.read_text(encoding="utf-8")
                           ) if parecer.LEMBRETES.is_file() else {}
        dados[ID] = {"mtime": round(mtime if mtime is not None
                                    else self.mp4.stat().st_mtime, 2),
                     "aprovado": aprovado,
                     "situacao": "aprovado" if aprovado else "reprovado",
                     "assistido": True,
                     "motivos": [] if aprovado else ["cena 9: um homem no "
                                                     "lugar da mulher"],
                     "vista": "video inteiro (2:18)", "numeracao": "cena",
                     "criterio": parecer.CRITERIO,
                     "quando": (quando or self.agora).isoformat(
                         timespec="seconds")}
        parecer.LEMBRETES.write_text(json.dumps(dados), encoding="utf-8")

    def _reparo(self, feito, quando):
        reparo.REGISTRO.write_text(json.dumps({ID: {
            "tentativas": 1, "quando": quando.isoformat(timespec="seconds"),
            "motivo": "a IA reprovou", "feito": feito, "passada": True}}),
            encoding="utf-8")

    def _rerenderizar(self, segundos=600):
        self.mp4.write_bytes(b"mp4 consertado")
        novo = self.mp4.stat().st_mtime + segundos
        os.utime(self.mp4, (novo, novo))


class ConsertadoTests(_ComParecer):

    def test_mp4_novo_e_refiz_depois_do_parecer_e_consertado(self):
        self._parecer()
        self._rerenderizar()
        self._reparo("refiz as cenas [9] e re-renderizei",
                     self.agora + timedelta(hours=1))
        self.assertTrue(parecer.consertado(self.video))
        self.assertEqual("consertado", parecer.estado_do_video(self.video))
        # o contrato antigo NAO muda: a valvula ainda le "reprovado"
        self.assertEqual("reprovado", parecer.situacao_do_video(self.video))

    def test_mesmo_mp4_nao_e_consertado(self):
        self._parecer()
        self._reparo("refiz as cenas [9] e re-renderizei",
                     self.agora + timedelta(hours=1))
        self.assertFalse(parecer.consertado(self.video))
        self.assertEqual("reprovado", parecer.estado_do_video(self.video))

    def test_re_render_sem_conserto_nao_e_consertado(self):
        """Mp4 novo por "imagem mais nova que o video" nao tira o veto."""
        self._parecer()
        self._rerenderizar()
        for feito in ("re-renderizei (o mp4 estava mais velho que as imagens)",
                      "a imagem nova nao veio; desfiz",
                      "a IA reprova e nao ha conserto automatico",
                      "consertei mas a vistoria ainda reprova: refiz"):
            with self.subTest(feito=feito):
                self._reparo(feito, self.agora + timedelta(hours=1))
                self.assertFalse(parecer.consertado(self.video))

    def test_conserto_antes_do_parecer_nao_conta(self):
        self._parecer()
        self._rerenderizar()
        self._reparo("refiz as cenas [9] e re-renderizei",
                     self.agora - timedelta(hours=1))
        self.assertFalse(parecer.consertado(self.video))

    def test_so_o_id_nao_basta(self):
        self._parecer()
        self._rerenderizar()
        self._reparo("refiz as cenas [9] e re-renderizei",
                     self.agora + timedelta(hours=1))
        self.assertFalse(parecer.consertado(ID))
        self.assertEqual("reprovado", parecer.estado_do_video(ID))

    def test_aprovado_nao_e_consertado(self):
        self._parecer(aprovado=True)
        self._rerenderizar()
        self._reparo("refiz as cenas [9] e re-renderizei",
                     self.agora + timedelta(hours=1))
        self.assertFalse(parecer.consertado(self.video))
        self.assertEqual("aprovado", parecer.estado_do_video(self.video))

    def test_sem_parecer_e_vazio(self):
        self.assertEqual("", parecer.estado_do_video(self.video))
        self.assertFalse(parecer.consertado(self.video))


class ReolharDepoisDoConsertoTests(_ComParecer):

    def setUp(self):
        super().setUp()
        self._parecer()
        self._rerenderizar()
        self._reparo("refiz as cenas [9] e re-renderizei",
                     self.agora + timedelta(hours=1))

    def test_desligado_a_regra_de_uma_passada_continua(self):
        self.assertFalse(parecer.REOLHAR_DEPOIS_DO_CONSERTO,
                         "a decisao e do Adrian (historias/reolhar-depois-"
                         "do-conserto): o padrao fica desligado")
        self.assertTrue(parecer.ja_olhado(self.video))

    def test_ligado_o_consertado_ganha_uma_olhada(self):
        self._trocar(parecer, "REOLHAR_DEPOIS_DO_CONSERTO", True)
        self.assertFalse(parecer.ja_olhado(self.video))
        # a olhada nova grava a ficha do mp4 novo: acabou o "consertado"
        parecer._lembrar(self.video, {"aprovado": False,
                                      "motivos": ["cena 2: outra coisa"],
                                      "vista": "video inteiro (2:18)",
                                      "numeracao": "cena",
                                      "criterio": parecer.CRITERIO})
        self.assertFalse(parecer.consertado(self.video))
        self.assertTrue(parecer.ja_olhado(self.video), "uma olhada so")

    def test_ligado_a_revisao_do_estoque_pergunta_o_consertado(self):
        self._trocar(parecer, "REOLHAR_DEPOIS_DO_CONSERTO", True)
        perguntados = self._revisar()
        self.assertEqual([ID], perguntados)

    def test_desligado_a_revisao_do_estoque_pula_o_consertado(self):
        self.assertEqual([], self._revisar())

    def _revisar(self):
        from contos.publicar import catalogo, serie
        from contos.roteiro import roteiro as R
        perguntados = []

        def pedir(video, *_a, **_k):
            perguntados.append(video.id)
            return {"aprovado": True, "situacao": "aprovado",
                    "vista": "video inteiro (2:18)"}

        self._trocar(catalogo, "listar", lambda *a, **k: [self.video])
        self._trocar(serie, "publicados", lambda *a, **k: [])
        self._trocar(agenda, "minutos_ate_fechar", lambda *a, **k: 999)
        self._trocar(R, "carregar", lambda *a, **k: {})
        self._trocar(qualidade, "vistoriar_parte",
                     lambda *a, **k: {"ok": True, "erros": [], "avisos": []})
        self._trocar(parecer, "pedir", pedir)
        agenda.revisar_estoque({"janela_pesada": None}, log=lambda *_a: None)
        return perguntados


class MotivoLixoTests(_Base):

    def test_rotulo_do_anexo_nao_e_motivo(self):
        veredito = parecer.ler_veredito(
            "REPROVADO\ncena 3: o policial ri com desdem\n"
            "cena 9: um homem no lugar da mulher\nMP4\n+ 1")
        self.assertEqual(["cena 3: o policial ri com desdem",
                          "cena 9: um homem no lugar da mulher"],
                         veredito["motivos"])

    def test_o_que_e_lixo(self):
        for lixo in ("MP4", "+ 1", "+4", "mp4", "2:18", "p03.mp4", "", " - "):
            with self.subTest(lixo=lixo):
                self.assertTrue(parecer.motivo_lixo(lixo))
        for bom in ("cena 2: a mae aparece como homem",
                    "o titulo promete algo que a narracao nao entrega",
                    "cena 4: MP4 na tela do celular da cena"):
            with self.subTest(bom=bom):
                self.assertFalse(parecer.motivo_lixo(bom))

    def test_so_lixo_vira_sem_motivo_dado(self):
        veredito = parecer.ler_veredito("REPROVADO\nMP4\n+ 1")
        self.assertEqual(["sem motivo dado"], veredito["motivos"])

    def test_limpa_o_que_ja_foi_gravado(self):
        arquivo = self.pasta / "_pareceres.json"
        arquivo.write_text(json.dumps({
            ID: {"aprovado": False, "mtime": 1.0, "quando": "x",
                 "motivos": ["cena 9: um homem", "MP4", "+ 1"]},
            "historia_00098:celular:p01": {"aprovado": False,
                                           "motivos": ["MP4", "+ 4"]},
            "historia_00097:celular:p01": {"aprovado": True, "motivos": []},
        }), encoding="utf-8")
        self.assertEqual(4, parecer.limpar_motivos_gravados(arquivo))
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        self.assertEqual(["cena 9: um homem"], dados[ID]["motivos"])
        self.assertEqual(1.0, dados[ID]["mtime"])
        self.assertEqual(["sem motivo dado"],
                         dados["historia_00098:celular:p01"]["motivos"])
        self.assertEqual(0, parecer.limpar_motivos_gravados(arquivo))

    def test_lembrar_nao_grava_lixo(self):
        self._trocar(parecer, "LEMBRETES", self.pasta / "_pareceres.json")
        parecer._lembrar(_Video(self.pasta / "nao.mp4"),
                         {"aprovado": False, "motivos": ["cena 1: x", "MP4"],
                          "vista": "video inteiro (1:00)"})
        dados = json.loads(parecer.LEMBRETES.read_text(encoding="utf-8"))
        self.assertEqual(["cena 1: x"], dados[ID]["motivos"])


class FichaFixaDoElencoTests(_Base):
    """Na origem: o genero e a ficha fixa valem para o elenco tambem."""

    BIBLIA = {"titulo": "t", "tipo": "normal", "partes_esperadas": 2,
              "protagonista": "man, Brazilian, 58 years old, gray hair",
              "elenco": "Fatima | woman, 60 years old, red blouse",
              "partes": [{"n": 1, "titulo": "a", "resumo": "r",
                          "gancho": "g", "cliffhanger": "c"},
                         {"n": 2, "titulo": "b", "resumo": "r",
                          "gancho": "g", "cliffhanger": "c"}]}

    def test_planejamento_livre_pede_genero_para_todos(self):
        texto = S.prompt_biblia_livre(partes=2, cenas_por_parte=12,
                                      tipo="normal")
        self.assertIn("GENERO (man, woman, boy, girl)", texto)
        self.assertIn("ELENCO", texto)
        self.assertIn("comecando pelo genero", texto)

    def test_parte_diz_quem_age_e_com_genero(self):
        config = carregar_config()
        texto = S.prompt_parte(self.BIBLIA, 1, cenas=12, config=config)
        self.assertIn("Fatima | woman, 60 years old", texto)
        self.assertIn("nunca so 'a clerk'", texto)
        self.assertIn("Nao ponha o protagonista onde a narracao fala de "
                      "outra pessoa", texto)

    def test_parte_com_molde_tambem(self):
        config = carregar_config()
        biblia = {**self.BIBLIA, "tipo": ""}
        texto = S.prompt_parte(biblia, 1, cenas=12, config=config)
        self.assertIn("descricao fixa dele INTEIRA", texto)
        self.assertIn("nunca so 'a clerk'", texto)


class MotivoLiteralNoConsertoTests(unittest.TestCase):

    def test_continuacao_sem_numero_vai_junto(self):
        motivos = ["cena 9: a imagem mostra um homem consultando fichas; a "
                   "narracao diz que uma mulher abriu a ficha",
                   "cena 3: o policial ri",
                   "o titulo promete algo"]
        self.assertEqual("cena 9: a imagem mostra um homem consultando "
                         "fichas; a narracao diz que uma mulher abriu a ficha",
                         C.motivos_da_cena(motivos, 9))
        self.assertEqual("cena 3: o policial ri", C.motivos_da_cena(motivos, 3))

    def test_o_pedido_leva_o_elenco_e_o_motivo_literal(self):
        roteiro = {"historia_id": "historia_00099",
                   "protagonista": "man, 58, gray mustache",
                   "elenco": "Fatima | woman, 60 years old, red blouse",
                   "partes": [{"n": 3, "cenas": [
                       {"n": 9, "narracao": "uma mulher abriu a ficha",
                        "imagem": "a middle-aged clerk"}]}]}
        pedidos = []
        C.reescrever_prompts(
            roteiro, 3, [9],
            ["cena 9: um homem no lugar; a narracao diz que e uma mulher"],
            perguntar=lambda p: pedidos.append(p) or "a woman in her 50s")
        self.assertIn("Fatima | woman, 60 years old", pedidos[0])
        self.assertIn("cena 9: um homem no lugar; a narracao diz que e uma "
                      "mulher", pedidos[0])
        self.assertIn("GENERO", pedidos[0])


# --------------------------------------------------------------- item 2
class SaidaNoDiarioTests(_Base):

    def test_tem_buffer_e_encoding(self):
        saida = agenda._SaidaNoDiario(self.pasta / "auto.txt")
        self.assertEqual("utf-8", saida.encoding)
        saida.buffer.write("história ✓\n".encode("utf-8"))
        saida.buffer.flush()
        texto = (self.pasta / "auto.txt").read_text(encoding="utf-8")
        self.assertIn("história ✓", texto)

    def test_a_contagem_da_publicacao_e_a_mesma_dentro_da_rodada(self):
        postar = agenda._postar()
        fila_ = [_Video(self.pasta / f"{i}.mp4",
                        f"historia_0009{i}:celular:p01") for i in range(3)]
        retidas = {fila_[2].id}

        def retencao(video):
            postar._linha(f"[teste] olhando {video.id}")
            return "a IA reprovou" if video.id in retidas else ""

        self._trocar(postar, "fila_de_historias", lambda: list(fila_))
        self._trocar(postar, "_retencao", retencao)
        self._trocar(postar, "_builds_prontos", lambda *a, **k: [])
        normal = agenda.estoque_publicavel()
        anterior = sys.stdout
        sys.stdout = agenda._SaidaNoDiario(self.pasta / "auto.txt", anterior)
        try:
            na_rodada = agenda.estoque_publicavel()
        finally:
            sys.stdout = anterior
        self.assertEqual(2, normal)
        self.assertEqual(normal, na_rodada)
        self.assertIn("[teste] olhando",
                      (self.pasta / "auto.txt").read_text(encoding="utf-8"))


class PlanoBTests(_Base):

    def setUp(self):
        super().setUp()
        self.aprovados = [_Video(self.pasta / f"{i}.mp4",
                                 f"historia_0009{i}:celular:p01")
                          for i in range(5)]
        self._trocar(agenda, "aprovados_no_estoque",
                     lambda: list(self.aprovados))
        situacoes = {self.aprovados[0].id: "reprovado",
                     self.aprovados[1].id: "nao_assistido",
                     self.aprovados[2].id: "aprovado"}
        self._trocar(parecer, "situacao_do_video",
                     lambda v: situacoes.get(getattr(v, "id", v), ""))
        self.diario = []
        from builds import atividade
        self._trocar(atividade, "registrar",
                     lambda *a, **k: self.diario.append((a, k)))
        self._trocar(agenda, "_PLANO_B_AVISADO", False)

    def _publicacao(self, valor):
        class _P:
            def pendentes_por_canal(self_):
                if isinstance(valor, Exception):
                    raise valor
                return {"historias": valor}
        self._trocar(agenda, "_POSTAR_CARREGADO", _P())

    def test_menos_um_desconta_as_retidas_e_avisa(self):
        self._publicacao(-1)
        saida = io.StringIO()
        anterior, sys.stdout = sys.stdout, saida
        try:
            self.assertEqual(3, agenda.estoque_publicavel())
        finally:
            sys.stdout = anterior
        self.assertIn("plano B: 3 publicavel(is) de 5", saida.getvalue())
        self.assertIn("devolveu -1", saida.getvalue())
        self.assertEqual(1, len(self.diario))
        self.assertEqual("aviso", self.diario[0][0][1])

    def test_excecao_tambem_desconta_e_avisa_uma_vez_so(self):
        self._publicacao(RuntimeError("ledger ilegivel"))
        for _ in range(3):
            self.assertEqual(3, agenda.estoque_publicavel())
        self.assertEqual(1, len(self.diario), "uma linha no diario por processo")
        self.assertIn("ledger ilegivel", self.diario[0][0][2])

    def test_numero_da_publicacao_nao_passa_pelo_plano_b(self):
        self._publicacao(1)
        self.assertEqual(1, agenda.estoque_publicavel())
        self.assertEqual([], self.diario)


class OrigemDaConferenciaTests(unittest.TestCase):

    def test_passa_a_origem_quando_a_funcao_aceita(self):
        def com_origem(*, log=print, origem="painel"):
            return origem
        self.assertEqual("servico",
                         agenda._kwargs_da_conferencia(com_origem, print)
                         ["origem"])

    def test_nao_quebra_a_assinatura_antiga(self):
        def sem_origem(*, log=print):
            return None
        kwargs = agenda._kwargs_da_conferencia(sem_origem, print)
        self.assertNotIn("origem", kwargs)
        sem_origem(**kwargs)


# -------------------------------------------------------------- item 11
RECUSA = "Não posso te ajudar com isso. Sou apenas um modelo de linguagem."
PARTE_OK = ("TITULO: x\n" + "\n".join(
    f"CENA {i}\nIMAGEM: a woman in her 40s, kitchen, moment {i}\n"
    f"NARRACAO: fala {i}." for i in range(1, 4)))


class _ClienteFalso:
    provedor = "gemini"

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chats = 0
        self.perguntas = []

    def perguntar(self, prompt):
        self.perguntas.append((self.chats, prompt))
        return self.respostas.pop(0)

    def abrir(self, novo_chat=True):
        self.chats += 1


class RecusaNoRoteiroTests(_Base):

    def test_recusa_e_depois_texto_valido(self):
        cliente = _ClienteFalso([RECUSA, PARTE_OK])
        logs = []
        texto = gerar._perguntar_sem_recusa(
            cliente, "escreva a parte 5", rotulo="a parte 5",
            pasta=self.pasta, nome="parte_05", log=logs.append)
        self.assertEqual(PARTE_OK, texto)
        self.assertEqual(1, cliente.chats, "a segunda vai num chat novo")
        self.assertEqual([0, 1], [c for c, _p in cliente.perguntas])
        self.assertTrue(any("recusa enlatada do gemini" in m for m in logs))
        self.assertTrue((self.pasta / "conversa" /
                         "parte_05_recusa1.txt").is_file())

    def test_tres_recusas_dizem_o_que_foi(self):
        cliente = _ClienteFalso([RECUSA] * 3)
        with self.assertRaises(gerar.RecusaEnlatada) as caso:
            gerar._perguntar_sem_recusa(cliente, "p", rotulo="a parte 5",
                                        log=lambda *_a: None)
        self.assertIn("recusa enlatada do gemini", str(caso.exception))
        self.assertNotIn("sem cena legivel", str(caso.exception))
        self.assertIsInstance(caso.exception, gerar.GeracaoFalhou)
        self.assertEqual(3, len(cliente.perguntas))

    def test_continuacao_recusada_nao_pede_mais(self):
        cliente = _ClienteFalso([RECUSA, PARTE_OK, PARTE_OK])
        parcial = gerar._completar_parte(cliente, PARTE_OK, 5, 14, self.pasta,
                                         lambda *_a: None)
        self.assertEqual(3, len(parcial["cenas"]))
        self.assertEqual(1, len(cliente.perguntas))

    def test_as_partes_passam_pelo_helper(self):
        import inspect
        fonte = inspect.getsource(gerar)
        for funcao in ("def gerar_serie(", "def retomar_serie("):
            corpo = fonte[fonte.index(funcao):]
            corpo = corpo[:corpo.index("\ndef ")]
            self.assertIn("_perguntar_sem_recusa(", corpo, funcao)


class RecusaNoClienteTests(_Base):

    def _cliente(self):
        c = llm_cliente.ClienteLLM("gemini", None, object(), log=lambda *_a: None)
        self.turnos = []
        self._trocar(llm_cliente.ClienteLLM, "_registrar_turno",
                     lambda _s, status, detalhe, dur_s=None:
                     self.turnos.append((status, detalhe)))
        return c

    def test_recusa_registra_aviso_e_nao_ok(self):
        c = self._cliente()
        self._trocar(llm_cliente.ClienteLLM, "_perguntar",
                     lambda _s, *_a: RECUSA)
        self.assertEqual(RECUSA, c.perguntar("p"))
        self.assertEqual("aviso", self.turnos[-1][0])
        self.assertIn("recusa enlatada", self.turnos[-1][1])

    def test_resposta_boa_continua_ok(self):
        c = self._cliente()
        self._trocar(llm_cliente.ClienteLLM, "_perguntar",
                     lambda _s, *_a: PARTE_OK)
        c.perguntar("p")
        self.assertEqual("ok", self.turnos[-1][0])

    def test_recusa_volta_na_hora_com_o_parar_na_tela(self):
        c = self._cliente()
        relogio = [0.0]

        def monotonic():
            relogio[0] += 1.0
            return relogio[0]

        falso = types.SimpleNamespace(monotonic=monotonic,
                                      sleep=lambda _s: None,
                                      strftime=time.strftime)
        self._trocar(llm_cliente, "time", falso)
        c._resposta_nova = lambda: RECUSA
        c.olha_imagem = lambda: False
        parar = c.sel["parar"]
        self._trocar(seletores, "encontrar",
                     lambda _p, candidatos, timeout=3.0:
                     object() if candidatos is parar else None)
        texto = c.esperar_resposta(timeout=600)
        self.assertEqual(RECUSA, texto)
        self.assertLess(relogio[0], 60, "nao espera o prazo de 600 s")


class SegundaTentativaDoConsertoTests(_Base):
    """A segunda pergunta do conserto JA ia num chat novo (medido em
    05/10/2026: o relatorio dizia o contrario). Fica provado aqui, pelo
    caminho de producao, com o `abrir_cliente` dublado."""

    def test_segunda_tentativa_em_chat_novo(self):
        cliente = _ClienteFalso([RECUSA, "a woman in her 50s at a desk, office"])
        from contextlib import contextmanager

        @contextmanager
        def abrir_cliente(*_a, **_k):
            yield cliente

        self._trocar(llm_cliente, "abrir_cliente", abrir_cliente)
        roteiro = {"historia_id": "historia_00099", "protagonista": "",
                   "partes": [{"n": 1, "cenas": [
                       {"n": 2, "narracao": "ela abriu", "imagem": "a clerk"}]}]}
        novos = C.reescrever_prompts(roteiro, 1, [2], ["cena 2: homem"],
                                     provedor="gemini", log=lambda *_a: None)
        self.assertEqual({2: "a woman in her 50s at a desk, office"}, novos)
        # chat 1 = a abertura; a pergunta repetida saiu no chat 2
        self.assertEqual([1, 2], [c for c, _p in cliente.perguntas])


# -------------------------------------------------------------- item 15
class VistoriaNoDiarioTests(_Base):

    def setUp(self):
        super().setUp()
        self.diario = []
        from builds import atividade
        self._trocar(atividade, "registrar",
                     lambda *a, **k: self.diario.append((a, k)))

    def test_vistoria_rapida_e_limpa_nao_vai_ao_diario(self):
        self.assertFalse(qualidade._registrar_vistoria(
            "historia_00099", 3, {"erros": []}, 0.2))
        self.assertEqual([], self.diario)

    def test_vistoria_com_erro_vai(self):
        self.assertTrue(qualidade._registrar_vistoria(
            "historia_00099", 3, {"erros": ["video mudo"]}, 0.2))
        self.assertIn("video mudo", self.diario[0][0][2])
        self.assertEqual("vistoria", self.diario[0][1]["etapa"])

    def test_vistoria_lenta_vai(self):
        self.assertTrue(qualidade._registrar_vistoria(
            "historia_00099", 3, {"erros": []}, qualidade.VISTORIA_LENTA_S))
        self.assertIn("lenta", self.diario[0][0][2])


# -------------------------------------------------------------- item 18
class MotivoPorCenaNoReparoTests(_Base):

    def setUp(self):
        super().setUp()
        self._trocar(fila, "OUTPUTS", self.pasta)
        self.hid, self.parte = "historia_00099", 3
        pasta = self.pasta / self.hid
        (pasta / "cenas").mkdir(parents=True)
        self.cena = {n: fila.caminho_da_cena(self.hid, n, self.parte)
                     for n in (4, 7)}
        for n, arquivo in self.cena.items():
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            arquivo.write_bytes(f"antiga {n}".encode())
        self.antigos = {f"{self.parte}:{n}": {"prompt": f"velho {n}",
                                               "arquivo": self.cena[n].name,
                                               "gerador": "gemini",
                                               "prova": {"comprovada": True}}
                        for n in (4, 7)}
        fila._gravar_meta(self.hid, {"gerador_imagem": "gemini",
                                     "cenas": dict(self.antigos)})
        self.colagens = set()
        self._trocar(composicao, "e_colagem",
                     lambda caminho: Path(caminho).name in self.colagens)
        self._trocar(composicao, "motivo",
                     lambda caminho: "parece colagem: 1 calha(s) atravessando "
                                     "a imagem (horizontal em 19%)")

    def _pipeline(self, gera):
        hid, parte = self.hid, self.parte

        class _P:
            def imagens(self_, *_a, **_k):
                for n in gera:
                    self.cena[n].write_bytes(b"nova")
                    fila.registrar(hid, n, prompt=f"novo {n}",
                                   arquivo=self.cena[n], parte=parte,
                                   gerador="gemini",
                                   prova={"comprovada": True})

            def render(self_, *_a, **_k):
                raise AssertionError("nao re-renderiza sem imagem nova")
        return _P()

    def test_colagem_e_nao_veio_tem_motivos_diferentes(self):
        self.colagens = {self.cena[4].name}
        porque = {}
        trocadas, restauradas = reparo._refazer_cenas(
            self._pipeline(gera=[4]), self.hid, self.parte, [4, 7],
            log=lambda *_a: None, motivos=porque)
        self.assertEqual([], trocadas)
        self.assertEqual([4, 7], restauradas)
        self.assertIn("veio e foi recusada", porque[4])
        self.assertIn("19%", porque[4])
        self.assertIn("Gemini", porque[4])
        self.assertEqual("o Gemini nao devolveu a imagem", porque[7])
        self.assertNotIn("PicassoIA", " ".join(porque.values()))

    def test_imagens_json_volta_junto_com_o_arquivo(self):
        self.colagens = {self.cena[4].name}
        reparo._refazer_cenas(self._pipeline(gera=[4]), self.hid, self.parte,
                              [4, 7], log=lambda *_a: None)
        self.assertEqual(b"antiga 4", self.cena[4].read_bytes())
        cenas = fila._meta(self.hid)["cenas"]
        self.assertEqual("velho 4", cenas[f"{self.parte}:4"]["prompt"])
        self.assertEqual(self.antigos, cenas)

    def test_imagem_boa_fica_com_o_registro_novo(self):
        porque = {}
        trocadas, restauradas = reparo._refazer_cenas(
            self._pipeline(gera=[4]), self.hid, self.parte, [4, 7],
            log=lambda *_a: None, motivos=porque)
        self.assertEqual([4], trocadas)
        self.assertEqual([7], restauradas)
        cenas = fila._meta(self.hid)["cenas"]
        self.assertEqual("novo 4", cenas[f"{self.parte}:4"]["prompt"])
        self.assertEqual("velho 7", cenas[f"{self.parte}:7"]["prompt"])

    def test_reparar_diz_o_motivo_por_cena(self):
        self._trocar(reparo, "REGISTRO", self.pasta / "_reparos.json")
        self.colagens = {self.cena[4].name}
        video = _Video(self.pasta / "p03.mp4", f"{self.hid}:celular:p03")
        resultado = reparo.reparar(
            video, ["parece colagem: cena 4: colagem", "cena 7: colagem"],
            pipeline=self._pipeline(gera=[4]), log=lambda *_a: None)
        self.assertEqual("adiado", resultado["acao"])
        self.assertIn("cena 4: a imagem do Gemini veio e foi recusada",
                      resultado["detalhe"])
        self.assertIn("cena 7: o Gemini nao devolveu", resultado["detalhe"])
        ficha = json.loads(reparo.REGISTRO.read_text(encoding="utf-8"))
        self.assertTrue(ficha[video.id]["feito"].startswith(
            "a imagem nova nao veio; desfiz"))


# -------------------------------------------------------------- item 20
class _Pagina:
    def __init__(self, visiveis):
        self.visiveis = list(visiveis)

    def title(self):
        return "Gemini"

    def evaluate(self, *_a):
        return "Gemini · Conversas · " * 10

    def screenshot(self, path=None, **_k):
        Path(path).write_bytes(b"png")


class LoginDoGeminiTests(_Base):

    def _cliente(self, pagina):
        self._trocar(llm_cliente, "time", types.SimpleNamespace(
            monotonic=time.monotonic, sleep=lambda _s: None,
            strftime=time.strftime))
        c = llm_cliente.ClienteLLM("gemini", None, pagina, log=lambda *_a: None)

        def encontrar(_p, candidatos, timeout=3.0):
            # a pagina muda a cada olhada quando `visiveis` e uma lista de
            # conjuntos: a primeira olhada consome o primeiro
            atual = pagina.visiveis[0] if pagina.visiveis else set()
            return (object() if any(candidatos is c.sel.get(k) for k in atual)
                    else None)

        self._trocar(seletores, "encontrar", encontrar)
        return c

    def test_o_seletor_de_login_nao_casa_o_avatar(self):
        login = seletores.do_provedor("gemini")["login"]
        self.assertNotIn("a[href*='accounts.google.com']", login)
        for seletor in login:
            self.assertNotIn("SignOutOptions", seletor)
        self.assertIn("a[href*='accounts.google.com/SignOutOptions']",
                      seletores.do_provedor("gemini")["conta"])

    def test_avatar_e_prova_de_sessao(self):
        c = self._cliente(_Pagina([{"conta"}]))
        self.assertEqual("logado", c.estado_da_pagina())

    def test_login_que_some_na_segunda_olhada_nao_e_login_caido(self):
        pagina = _Pagina([{"login"}, {"logado"}])
        c = self._cliente(pagina)
        original = c.estado_da_pagina

        def estado():
            resposta = original()
            if len(pagina.visiveis) > 1:
                pagina.visiveis.pop(0)
            return resposta

        c.estado_da_pagina = estado
        self.assertEqual("logado", c.conferir_sessao())

    def test_login_que_continua_e_login_caido(self):
        c = self._cliente(_Pagina([{"login"}]))
        with self.assertRaises(llm_cliente.NaoLogado):
            c.conferir_sessao()


if __name__ == "__main__":
    unittest.main()
