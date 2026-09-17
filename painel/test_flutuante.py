# -*- coding: utf-8 -*-
"""Contratos da Vila flutuante. Quase tudo sem abrir janela.

O que este arquivo trava:

1. LEITURA TOLERANTE. O diario e escrito por outros processos o tempo todo:
   linha pela metade, lixo e arquivo sumido nao derrubam nada.
2. TRAVA SO LIDA. A sonda diz "ocupada" sem pegar a trava — pegar, mesmo
   por um instante, faz o dono de verdade desistir da rodada.
3. ESTADO. Quem esta trabalhando (PID vivo manda, relogio so sem PID),
   erro que vale (2 h), bot no ar pela trava dele.
4. RELOGIO. Proximo horario e contagem regressiva com relogio falso.
5. FEED E PAINEIS. O texto que aparece, sem Tk.
6. FALLBACK DE SPRITE. Predio sem arte nao some da Vila.
7. OCULTAR CONSOLES. A seco nao altera nada; o lancador passa o codigo.
8. A JANELA MONTA nos quatro tamanhos, e so ela chama `after`.

Rode da raiz:  python -m pytest painel/test_flutuante.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import queue
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from painel.flutuante import (coletor, dados, janela, mundo, preferencias,
                              previsao)
from painel.flutuante.caminhos import Caminhos

RAIZ = Path(__file__).resolve().parent.parent


def _carregar_ferramenta(nome: str):
    caminho = RAIZ / "ferramentas" / f"{nome}.py"
    spec = importlib.util.spec_from_file_location(f"_teste_{nome}", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _evento(ts, fabrica="picasso", status="inicio", canal="historias", **kw):
    linha = {"ts": ts.isoformat(timespec="seconds"), "fabrica": fabrica,
             "status": status, "canal": canal, "detalhe": kw.pop("detalhe", "")}
    linha.update(kw)
    return linha


AGORA_UTC = datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc)


class LeituraTolerante(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())

    def test_arquivo_sumido_devolve_vazio(self):
        self.assertEqual(dados.ler_cauda(self.pasta / "nao_existe.txt"), [])
        self.assertEqual(dados.ler_diario(self.pasta / "nao_existe.jsonl"), [])

    def test_linha_pela_metade_e_lixo_sao_pulados(self):
        diario = self.pasta / "atividade.jsonl"
        boa = json.dumps(_evento(AGORA_UTC))
        diario.write_bytes((boa + "\nisto nao e json\n{\"ts\": quebr\n"
                            + boa + "\n{\"ts\": \"2026-09-17T12:00:01\", \"fab")
                           .encode("utf-8"))
        eventos = dados.ler_diario(diario)
        self.assertEqual(len(eventos), 2)
        self.assertTrue(all(e["fabrica"] == "picasso" for e in eventos))

    def test_cauda_descarta_a_primeira_linha_cortada(self):
        arquivo = self.pasta / "log.txt"
        arquivo.write_text("A" * 50 + "\nsegunda\nterceira\n", encoding="utf-8")
        self.assertEqual(dados.ler_cauda(arquivo, max_bytes=20),
                         ["segunda", "terceira"])

    def test_utf8_quebrado_nao_derruba(self):
        arquivo = self.pasta / "log.txt"
        arquivo.write_bytes(b"ok\n\xff\xfe estranho\nfim\n")
        linhas = dados.ler_cauda(arquivo)
        self.assertEqual(linhas[0], "ok")
        self.assertEqual(linhas[-1], "fim")

    def test_ledger_tolerante(self):
        ledger = self.pasta / "publicados.jsonl"
        ledger.write_text('{"a": 1}\nlixo\n[1,2]\n{"b": 2}\n', encoding="utf-8")
        self.assertEqual(dados.ler_ledger(ledger), [{"a": 1}, {"b": 2}])


@unittest.skipUnless(os.name == "nt", "a trava do projeto e msvcrt")
class TravaSoLida(unittest.TestCase):
    SEGURAR = (
        "import msvcrt,sys,time\n"
        "f=open(sys.argv[1],'a+b')\n"
        "f.seek(0,2)\n"
        "f.tell() or (f.write(b'\\0'), f.flush())\n"
        "f.seek(0)\n"
        "msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)\n"
        "print('ok', flush=True)\n"
        "sys.stdin.readline()\n")

    def test_ocupada_livre_e_sumida(self):
        pasta = Path(tempfile.mkdtemp())
        trava = pasta / "picasso__principal.lock"
        trava.write_bytes(b"\0")
        self.assertIs(dados.trava_ocupada(trava), False)
        self.assertIs(dados.trava_ocupada(pasta / "nada.lock"), None)
        dono = subprocess.Popen([sys.executable, "-c", self.SEGURAR,
                                 str(trava)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(dono.stdout.readline().strip(), "ok")
            self.assertIs(dados.trava_ocupada(trava), True)
            self.assertEqual(dados.travas_ocupadas(pasta),
                             ["picasso__principal"])
        finally:
            dono.stdin.write("\n")
            dono.stdin.flush()
            dono.wait(10)
        self.assertIs(dados.trava_ocupada(trava), False)

    DONO_EM_LACO = (
        "import msvcrt,sys\n"
        "falhas=0\n"
        "print('pronto', flush=True)\n"
        "sys.stdin.readline()\n"
        "for _ in range(400):\n"
        "    f=open(sys.argv[1],'a+b'); f.seek(0)\n"
        "    try:\n"
        "        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)\n"
        "        f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)\n"
        "    except OSError:\n"
        "        falhas+=1\n"
        "    f.close()\n"
        "print(falhas, flush=True)\n")

    def test_a_sonda_nao_rouba_a_trava_do_dono(self):
        """O dono pega e solta 400 vezes, sem espera, com a sonda lendo sem
        parar: nenhuma tentativa pode falhar. `travas.ocupada()` falharia —
        ela responde PEGANDO a trava."""
        pasta = Path(tempfile.mkdtemp())
        trava = pasta / "picasso__principal.lock"
        trava.write_bytes(b"\0")
        dono = subprocess.Popen([sys.executable, "-c", self.DONO_EM_LACO,
                                 str(trava)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True)
        self.assertEqual(dono.stdout.readline().strip(), "pronto")
        dono.stdin.write("\n")
        dono.stdin.flush()
        sondas = 0
        while dono.poll() is None and sondas < 200_000:
            dados.trava_ocupada(trava)
            sondas += 1
        falhas = int(dono.stdout.readline().strip())
        dono.wait(10)
        self.assertGreater(sondas, 50)
        self.assertEqual(falhas, 0)

    def test_travas_de_teste_sao_ignoradas(self):
        pasta = Path(tempfile.mkdtemp())
        (pasta / "teste_agenda_1.lock").write_bytes(b"\0")
        with mock.patch.object(dados, "trava_ocupada", return_value=True):
            self.assertEqual(dados.travas_ocupadas(pasta), [])


class NomesDeTrava(unittest.TestCase):
    def test_perfis_e_legado(self):
        casos = {
            "perfil__tiktok__historinhas__9cfe3e40": ("tiktok", "historinhas"),
            "perfil__picasso__078d33ec": ("picasso", "principal"),
            "perfil__youtube_web__a7f967b5": ("youtube", "principal"),
            "perfil__deepseek__principal__d399e1b8": ("deepseek", "principal"),
            "perfil__chatgpt__plus__c5c08992": ("chatgpt", "plus"),
            "youtube_web__neural_fights": ("youtube", "neural_fights"),
            "tiktok__canal2": ("tiktok", "canal2"),
        }
        for nome, (predio, conta) in casos.items():
            info = dados.ler_trava(nome)
            self.assertEqual((info["predio"], info["conta"]), (predio, conta),
                             nome)

    def test_especiais_e_ignoradas(self):
        self.assertEqual(dados.ler_trava("remoto__bot")["predio"], "bot")
        self.assertEqual(dados.ler_trava("historias__auto")["predio"], "casa")
        render = dados.ler_trava("historias__render__historia_00017")
        self.assertEqual(render["predio"], "estudio")
        self.assertIn("historia_00017", render["texto"])
        for nome in ("ledger__builds", "teste_agenda_1", "sessao_editando"):
            self.assertIsNone(dados.ler_trava(nome))
        desconhecido = dados.ler_trava("perfil__dreamface__6c931855")
        self.assertEqual(desconhecido["predio"], "")

    def test_contas_por_predio_sem_render_nem_bot(self):
        contas = dados.contas_por_predio([
            "perfil__picasso__078d33ec", "picasso__principal",
            "remoto__bot", "historias__render__h1",
            "perfil__tiktok__historinhas__9cfe3e40"])
        self.assertEqual(contas, {"picasso": ["principal"],
                                  "tiktok": ["historinhas"]})


class EstadoDoSistema(unittest.TestCase):
    def test_pid_vivo_manda_mesmo_velho(self):
        velho = _evento(AGORA_UTC - timedelta(hours=5), pid=10)
        abertos = dados.trabalhos_abertos([velho], AGORA_UTC,
                                          vivo=lambda pid: True)
        self.assertEqual(len(abertos), 1)

    def test_pid_morto_some_na_hora(self):
        novo = _evento(AGORA_UTC - timedelta(seconds=5), pid=10)
        self.assertEqual(dados.trabalhos_abertos(
            [novo], AGORA_UTC, vivo=lambda pid: False), [])

    def test_sem_pid_o_relogio_decide(self):
        novo = _evento(AGORA_UTC - timedelta(minutes=5))
        velho = _evento(AGORA_UTC - timedelta(hours=3), fabrica="gemini")
        abertos = dados.trabalhos_abertos([novo, velho], AGORA_UTC,
                                          vivo=lambda pid: None)
        self.assertEqual([a["fabrica"] for a in abertos], ["picasso"])

    def test_ok_depois_fecha_e_log_nao_conta(self):
        eventos = [_evento(AGORA_UTC - timedelta(minutes=5), pid=1),
                   _evento(AGORA_UTC - timedelta(minutes=4), status="ok",
                           pid=1),
                   _evento(AGORA_UTC - timedelta(minutes=3), status="log",
                           pid=1)]
        self.assertEqual(dados.trabalhos_abertos(eventos, AGORA_UTC,
                                                 vivo=lambda p: True), [])

    def test_dois_canais_no_mesmo_predio_sao_dois_trabalhos(self):
        eventos = [_evento(AGORA_UTC, canal="historias", pid=1),
                   _evento(AGORA_UTC, canal="builds", pid=2)]
        abertos = dados.trabalhos_abertos(eventos, AGORA_UTC,
                                          vivo=lambda p: True)
        estado = dados.estado_dos_predios(abertos, [], [])
        self.assertEqual(estado["picasso"]["status"], "trabalhando")
        self.assertTrue(estado["picasso"]["balao"].endswith("+1"))

    def test_balao_curto_com_etapa_e_ref(self):
        evento = _evento(AGORA_UTC, fabrica="deepseek", etapa="roteiro",
                         ref="historia_09003:p2")
        self.assertEqual(dados.balao(evento), "roteiro historia_09003 p2")
        render = _evento(AGORA_UTC, fabrica="estudio", etapa="render",
                         ref="generation_00023:build:celular")
        self.assertEqual(dados.balao(render), "render generation_00023")
        longo = _evento(AGORA_UTC, detalhe="x" * 80)
        self.assertLessEqual(len(dados.balao(longo)), 30)

    def test_publicacao_vira_youtube_ou_tiktok(self):
        tiktok = _evento(AGORA_UTC, fabrica="publicacao",
                         etapa="publicar.tiktok")
        youtube = _evento(AGORA_UTC, fabrica="publicacao",
                          detalhe="upload no YouTube")
        self.assertEqual(dados.predio_do_evento(tiktok), "tiktok")
        self.assertEqual(dados.predio_do_evento(youtube), "youtube")
        self.assertEqual(dados.predio_do_evento(
            _evento(AGORA_UTC, fabrica="mimetizar")), "casa")
        self.assertEqual(dados.predio_do_evento(
            _evento(AGORA_UTC, fabrica="apurador")), "bot")

    def test_erros_so_das_ultimas_duas_horas(self):
        eventos = [
            _evento(AGORA_UTC - timedelta(hours=3), status="erro",
                    detalhe="velho"),
            _evento(AGORA_UTC - timedelta(minutes=30), status="erro",
                    detalhe="recente"),
            _evento(AGORA_UTC - timedelta(minutes=10), status="ok"),
            _evento(AGORA_UTC - timedelta(minutes=5), status="erro",
                    fabrica="publicacao", etapa="publicar.tiktok",
                    detalhe="nao subiu"),
        ]
        erros = dados.erros_recentes(eventos, AGORA_UTC)
        self.assertEqual([e["detalhe"] for e in erros],
                         ["nao subiu", "recente"])
        self.assertEqual(erros[0]["predio"], "tiktok")
        estado = dados.estado_dos_predios([], erros, [])
        self.assertEqual(estado["tiktok"]["status"], "erro")
        self.assertTrue(estado["tiktok"]["balao"].startswith("❗"))

    def test_bot_no_ar_pela_trava(self):
        estado = dados.estado_dos_predios([], [], ["remoto__bot"])
        self.assertEqual(estado["bot"]["status"], "no_ar")
        self.assertEqual(dados.estado_dos_predios([], [], [])["bot"]["status"],
                         "ocioso")

    def test_resumo_por_nivel(self):
        self.assertEqual(dados.resumo({})["nivel"], "calmo")
        trabalho = {"abertos": [{"texto": "render h1"}], "bot": {"vivo": True}}
        self.assertEqual(dados.resumo(trabalho)["nivel"], "trabalhando")
        self.assertIn("render h1", dados.resumo(trabalho)["frase"])
        morto = {"bot": {"vivo": False}}
        self.assertEqual(dados.resumo(morto)["nivel"], "erro")
        self.assertIn("bot", dados.resumo(morto)["alerta"])
        erro = {"erros": [{"predio": "picasso", "detalhe": "caiu"}]}
        self.assertIn("PicassoIA: caiu", dados.resumo(erro)["alerta"])


class Relogio(unittest.TestCase):
    GRADE = ((0, 37), (6, 37), (12, 7), (23, 37))

    def test_proximo_no_mesmo_dia(self):
        agora = datetime(2026, 9, 17, 6, 36, 30)
        self.assertEqual(dados.proximo_horario(agora, self.GRADE),
                         datetime(2026, 9, 17, 6, 37))

    def test_no_minuto_exato_ja_e_o_seguinte(self):
        agora = datetime(2026, 9, 17, 12, 7, 0)
        self.assertEqual(dados.proximo_horario(agora, self.GRADE),
                         datetime(2026, 9, 17, 23, 37))

    def test_vira_o_dia(self):
        agora = datetime(2026, 9, 17, 23, 50)
        self.assertEqual(dados.proximo_horario(agora, self.GRADE),
                         datetime(2026, 9, 18, 0, 37))

    def test_a_grade_real_e_lida(self):
        from builds import grade
        agora = datetime(2026, 9, 17, 12, 0)
        alvo = dados.proximo_horario(agora)
        self.assertEqual((alvo.hour, alvo.minute), (12, grade.minuto(12)))

    def test_contagem(self):
        self.assertEqual(dados.contagem(-3), "agora")
        self.assertEqual(dados.contagem(30), "em 0:30")
        self.assertEqual(dados.contagem(185), "em 3:05")
        self.assertEqual(dados.contagem(1800), "em 30 min")
        self.assertEqual(dados.contagem(4 * 3600 + 42 * 60 + 10),
                         "em 4h 42min")

    def test_texto_do_proximo_com_relogio_falso(self):
        estado = {"proximo": datetime(2026, 9, 17, 6, 37)}
        self.assertEqual(
            janela.texto_do_proximo(estado, datetime(2026, 9, 17, 6, 35, 0)),
            "⏭ 06:37 · em 2:00")
        # O horario lido ja passou (a leitura e de 3 s atras): recalcula.
        passou = janela.texto_do_proximo(estado,
                                         datetime(2026, 9, 17, 6, 38, 0))
        self.assertNotIn("06:37", passou)

    def test_duracao(self):
        self.assertEqual(dados.duracao(None), "—")
        self.assertEqual(dados.duracao(42), "42 s")
        self.assertEqual(dados.duracao(600), "10 min")
        self.assertEqual(dados.duracao(3600 + 5 * 60), "1h05")
        self.assertEqual(dados.duracao(3 * 86400), "3 dias")


class FeedEPaineis(unittest.TestCase):
    def test_linha_do_diario(self):
        evento = _evento(datetime(2026, 9, 17, 4, 49, 27, tzinfo=timezone.utc),
                         fabrica="estudio", status="ok",
                         detalhe="historia_09001:  1 video(s)")
        texto, marca = dados.linha_do_diario(evento)
        self.assertEqual(marca, "ok")
        self.assertIn("✓ Estúdio", texto)
        self.assertIn("hist", texto)
        self.assertIn("historia_09001: 1 video(s)", texto)
        local = datetime(2026, 9, 17, 4, 49, 27,
                         tzinfo=timezone.utc).astimezone()
        self.assertTrue(texto.startswith(local.strftime("%H:%M:%S")))
        self.assertEqual(dados.linha_do_diario(
            _evento(AGORA_UTC, status="log"))[1], "fraco")
        self.assertEqual(dados.linha_do_diario({"ts": "lixo"})[0][:8],
                         "--:--:--")

    def test_classificar_linha(self):
        casos = {
            "[postar] recuperacao do TikTok (historias) falhou (X)": "erro",
            "  gordura builds        0 dia(s)  <<< ABAIXO DO PISO": "aviso",
            "[tiktok] publicado no TikTok (com a confirmacao extra)": "ok",
            "[remoto] relatorio de metas enviado.": "ok",
            "   vídeo processado.": "fraco",
            "[-------] builds     generation_00023:build:celular": "cmd",
            "": "",
        }
        for texto, esperado in casos.items():
            self.assertEqual(dados.classificar_linha(texto), esperado, texto)

    def test_processos_classificados(self):
        c = dados.classificar_processo
        self.assertEqual(c('"C:\\Python314\\python.exe"  -u -X utf8 -m remoto')
                         ["tipo"], "bot")
        self.assertEqual(c("python.exe -u -X utf8 main.py auto --saida x")
                         ["tipo"], "historias")
        self.assertEqual(c("python.exe -u ferramentas\\postar.py")["tipo"],
                         "postar")
        self.assertIsNone(c("pythonw.exe -X utf8 -m painel.flutuante"))
        sessao = c("python.exe C:/Users/x/AppData/Local/Temp/claude/p/"
                   "scratchpad/remessa.py")
        self.assertEqual(sessao["tipo"], "sessao")
        self.assertIn("remessa.py", sessao["quem"])
        self.assertNotIn("Users", sessao["quem"])
        self.assertEqual(c("python.exe -m pytest painel")["tipo"], "testes")

    def test_linhas_vivas_juntam_diario_e_processo(self):
        agora = datetime(2026, 9, 17, 2, 0)
        processos = dados.ler_processos_json(json.dumps([
            {"ProcessId": 17112, "CommandLine": "python main.py auto",
             "Inicio": "2026-09-17T00:02:01"},
            {"ProcessId": 9324, "CommandLine": "python -u -m remoto",
             "Inicio": "2026-09-16T19:58:09"},
            {"ProcessId": 1, "CommandLine": "pythonw -m painel.flutuante",
             "Inicio": "2026-09-17T01:00:00"},
        ]))
        abertos = [
            {"predio": "estudio", "texto": "render historia_00017",
             "pid": 17112, "desde": agora, "ha_s": 60},
            {"predio": "picasso", "texto": "imagens h9", "pid": 555,
             "desde": agora, "ha_s": 30},
        ]
        linhas = dados.linhas_vivas(processos, abertos, agora)
        quem = [l["quem"] for l in linhas]
        self.assertEqual(len(linhas), 3)
        self.assertNotIn("painel", " ".join(quem).lower())
        historias = next(l for l in linhas if l["tipo"] == "historias")
        self.assertIn("render historia_00017 (Estúdio)", historias["oque"])
        self.assertEqual(historias["desde"], "00:02")
        self.assertEqual(historias["ha"], "1h57")
        self.assertTrue(any(l["tipo"] == "diario" and "imagens h9" in l["oque"]
                            for l in linhas))
        self.assertFalse(linhas[-1]["ativo"], "parado vai para o fim")

    def test_processos_json_de_um_so_e_lixo(self):
        self.assertEqual(len(dados.ler_processos_json(
            '{"ProcessId": 3, "CommandLine": "x"}')), 1)
        self.assertEqual(dados.ler_processos_json("nao e json"), [])
        self.assertEqual(dados.ler_processos_json(""), [])

    def test_ultimos_publicados_com_prova(self):
        por_canal = {
            "historias": [
                {"quando": "2026-09-16T23:39:42", "plataforma": "tiktok",
                 "titulo": "Parte 6", "url": "publicado", "prova_ok": True},
                {"quando": "2026-09-16T23:50:00", "plataforma": "youtube",
                 "titulo": "sem prova", "url": "frase", "prova_ok": False},
                {"quando": "2026-09-17T01:00:00", "plataforma": "youtube",
                 "titulo": "rascunho", "url": "x", "publicado": False},
            ],
            "builds": [
                {"quando": "2026-08-27T21:07:53", "plataforma": "tiktok",
                 "titulo": "conciliado", "publicado": True,
                 "tiktok_id": "76", "url": "https://www.tiktok.com/@/video/76"},
                {"quando": "lixo", "titulo": "sem data", "url": "x"},
            ],
        }
        itens = dados.ultimos_publicados(por_canal, 5)
        self.assertEqual([i["titulo"] for i in itens],
                         ["sem prova", "Parte 6", "conciliado"])
        self.assertEqual([i["prova"] for i in itens], [False, True, True])

    def test_painel_de_postagem_sem_tk(self):
        estado = {
            "previsao": {
                "historias": {"id": "historia_00016:celular:p06",
                              "titulo": "O Fim (Parte 6/6)"},
                "builds": None,
                "fila_historias": [{"id": "historia_00017:celular:p01"}],
                "gordura": {"historias": 2, "builds": 0},
                "atrasados_tiktok": {"historias": 6, "builds": 0},
            },
            "previsao_em": datetime(2026, 9, 17, 2, 15),
            "publicados": [{"quando": datetime(2026, 9, 16, 23, 40),
                            "canal": "builds", "plataforma": "tiktok",
                            "titulo": "Takeshi", "prova": False}],
            "bot": {"vivo": False},
        }
        texto = "".join(t for t, _m in janela.pedacos_da_postagem(estado))
        self.assertIn("historia_00016 p06", texto)
        self.assertIn("nada pronto para sair", texto)
        self.assertIn("depois: historia_00017 p01", texto)
        self.assertIn("0 dia(s)  ⚠ abaixo do piso", texto)
        self.assertIn("FORA DO AR", texto)
        self.assertIn("(sem prova)", texto)
        self.assertLess(texto.index("BOT DO TELEGRAM"),
                        texto.index("ÚLTIMOS PUBLICADOS"))
        self.assertIn("nada pronto", janela.texto_da_fila(estado))
        self.assertIn("previsão ainda não lida", janela.texto_da_fila({}))
        self.assertIn("falhou", janela.texto_da_fila(
            {"previsao": {"falhou": "Erro: x"}}))


class Preferencias(unittest.TestCase):
    TELA = (1366, 768)

    def test_sem_posicao_nasce_no_canto_direito(self):
        x, y = preferencias.encaixar(None, None, 720, 520, self.TELA)
        self.assertEqual((x, y), (1366 - 720 - 16, 16))

    def test_fora_da_tela_volta_para_dentro(self):
        self.assertEqual(preferencias.encaixar(5000, 5000, 340, 64, self.TELA),
                         (1366 - 340, 768 - preferencias.BARRA_DO_WINDOWS - 64))
        self.assertEqual(preferencias.encaixar(-50, -9, 340, 64, self.TELA),
                         (0, 0))

    def test_tamanhos_cabem_na_tela_dele(self):
        for modo in preferencias.MODOS:
            largura, altura = preferencias.tamanho(modo, self.TELA)
            self.assertLessEqual(largura, 1366, modo)
            self.assertLessEqual(altura, 768 - preferencias.BARRA_DO_WINDOWS,
                                 modo)
        self.assertLessEqual(preferencias.tamanho("medio", self.TELA),
                             (720, 520))
        self.assertEqual(preferencias.tamanho("mini", self.TELA), (340, 64))

    def test_ler_lixo_e_gravar(self):
        pasta = Path(tempfile.mkdtemp())
        arquivo = pasta / "flutuante.json"
        arquivo.write_text("{ quebrado", encoding="utf-8")
        self.assertEqual(preferencias.ler(arquivo)["modo"], "medio")
        arquivo.write_text(json.dumps({"modo": "voador", "anterior": "icone",
                                       "x": 10, "intruso": 1}),
                           encoding="utf-8")
        lidas = preferencias.ler(arquivo)
        self.assertEqual((lidas["modo"], lidas["anterior"], lidas["x"]),
                         ("medio", "medio", 10))
        self.assertNotIn("intruso", lidas)
        lidas["modo"] = "mini"
        self.assertTrue(preferencias.gravar(arquivo, lidas))
        self.assertEqual(preferencias.ler(arquivo)["modo"], "mini")
        self.assertFalse(arquivo.with_suffix(".tmp").exists())


class FallbackDeSprite(unittest.TestCase):
    class _AtlasSemNada:
        def sprite(self, *a, **k):
            raise KeyError("papel sem sprite atribuido")

    def test_papel_ausente_cai_no_procedural(self):
        img, origem = mundo.sprite_do_predio("deepseek", self._AtlasSemNada())
        self.assertEqual(origem, "procedural")
        self.assertEqual(img.size, (64, 48))

    def test_sem_vila_cai_no_vetorial(self):
        with mock.patch.dict(sys.modules, {"vila.gerar_base": None}):
            img, origem = mundo.sprite_do_predio("fabrica_nova", None)
        self.assertEqual(origem, "vetorial")
        self.assertEqual(img.size, (64, 48))

    def test_mundo_sem_folha_ainda_tem_todos_os_predios(self):
        img, origens, atlas = mundo.compor((None, None, None))
        self.assertEqual(img.size, (mundo.LARGURA_PX, mundo.ALTURA_PX))
        self.assertIsNone(atlas)
        self.assertEqual(set(origens), set(dados.PREDIOS) | {"casa"})

    def test_mundo_de_verdade_usa_os_papeis(self):
        _img, origens, _atlas = mundo.compor()
        self.assertEqual(origens["deepseek"], "sprite")
        self.assertEqual(origens["youtube"], "sprite")

    def test_lotes_nao_se_sobrepoem_e_cabem(self):
        ocupados = set()
        for nome, (x, y) in list(mundo.LOTES.items()) + [("casa", mundo.CASA)]:
            celulas = {(x + dx, y + dy) for dx in range(4) for dy in range(3)}
            self.assertFalse(celulas & ocupados, nome)
            ocupados |= celulas
            self.assertTrue(all(0 <= cx < mundo.LARG and 0 <= cy < mundo.ALT
                                for cx, cy in celulas), nome)
        self.assertEqual(set(mundo.LOTES), set(dados.PREDIOS))

    def test_mapa_compacto_e_deterministico(self):
        self.assertEqual(mundo.mapa_compacto(), mundo.mapa_compacto())


class TarefasOcultas(unittest.TestCase):
    """O verificador do Agendador: so le, e diz o que voltou ou quebrou."""

    VBS = "C:\\Users\\x\\AppData\\Local\\neural-fights\\oculto.vbs"

    def _oculta(self, nome, cmd="E:\\projetos\\postar.cmd"):
        return {"Nome": nome, "Acoes": 1,
                "Executa": "C:\\Windows\\System32\\wscript.exe",
                "Argumentos": f'//B //Nologo "{self.VBS}" "{cmd}"',
                "Pasta": "E:\\projetos"}

    def _existe_tudo(self, _caminho):
        return True

    def test_cada_forma_de_tarefa(self):
        from painel.flutuante import tarefas
        casos = [
            (self._oculta("NeuralFights_postar_06"), "oculta"),
            ({"Nome": "a", "Executa": '"E:\\projetos\\postar.cmd"'},
             "console"),
            ({"Nome": "b", "Executa": "C:\\Python314\\python.exe",
              "Argumentos": "x.py"}, "console"),
            ({"Nome": "c", "Executa": "C:\\Python314\\pythonw.exe",
              "Argumentos": "x.py"}, "oculta"),
            ({"Nome": "d", "Executa": "notepad.exe"}, "desconhecida"),
            ({"Nome": "e", "Executa": "wscript.exe", "Argumentos": "//B"},
             "desconhecida"),
        ]
        for tarefa, esperado in casos:
            ficha = tarefas.examinar_uma(tarefa, existe=self._existe_tudo)
            self.assertEqual(ficha["estado"], esperado, tarefa)
        oculta = tarefas.examinar_uma(self._oculta("x"),
                                      existe=self._existe_tudo)
        self.assertEqual(oculta["alvo"], "E:\\projetos\\postar.cmd")

    def test_lancador_ou_cmd_sumido_e_quebrada(self):
        from painel.flutuante import tarefas
        sem_vbs = tarefas.examinar_uma(
            self._oculta("x"), existe=lambda c: not c.endswith(".vbs"))
        self.assertEqual(sem_vbs["estado"], "quebrada")
        self.assertIn("oculto.vbs", sem_vbs["motivo"])
        sem_cmd = tarefas.examinar_uma(
            self._oculta("x"), existe=lambda c: not c.endswith(".cmd"))
        self.assertEqual(sem_cmd["estado"], "quebrada")

    def test_existe_expande_variavel_de_ambiente(self):
        from painel.flutuante import tarefas
        pasta = Path(tempfile.mkdtemp())
        (pasta / "oculto.vbs").write_text("x", encoding="ascii")
        with mock.patch.dict(os.environ, {"NF_TESTE_PASTA": str(pasta)}):
            self.assertTrue(tarefas._existe("%NF_TESTE_PASTA%\\oculto.vbs"))
            self.assertFalse(tarefas._existe("%NF_TESTE_PASTA%\\nada.vbs"))

    def test_resumo_e_selo(self):
        from painel.flutuante import tarefas
        todas = [self._oculta(f"NeuralFights_postar_{h:02d}")
                 for h in (0, 6, 9)]
        ok = tarefas.examinar(todas, existe=self._existe_tudo)
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["selo"], "tarefas ocultas ✓ 3/3")
        voltou = todas + [{"Nome": "NeuralFights_bot_telegram",
                           "Executa": '"E:\\projetos\\bot.cmd"'}]
        ruim = tarefas.examinar(voltou, existe=self._existe_tudo)
        self.assertFalse(ruim["ok"])
        self.assertEqual(ruim["selo"], "tarefas ⚠ 1 com console")
        self.assertEqual([i["nome"] for i in ruim["problemas"]],
                         ["NeuralFights_bot_telegram"])
        nada = tarefas.examinar(None)
        self.assertIsNone(nada["ok"])
        self.assertFalse(nada["lido"])
        texto = tarefas.descrever(ruim)
        self.assertIn("[CONSOLE] NeuralFights_bot_telegram", texto)
        self.assertIn("[ok] 3 tarefas (NeuralFights_postar_00", texto)
        self.assertLess(texto.index("[CONSOLE]"), texto.index("[ok]"),
                        "o problema vem primeiro")

    def test_quebrada_vira_erro_no_resumo_e_console_so_alerta(self):
        from painel.flutuante import tarefas
        quebrada = tarefas.examinar([self._oculta("x")],
                                    existe=lambda c: False)
        resumo = dados.resumo({"tarefas": quebrada, "bot": {"vivo": True}})
        self.assertEqual(resumo["nivel"], "erro")
        self.assertIn("quebrada", resumo["alerta"])
        console = tarefas.examinar([{"Nome": "a", "Executa": "a.cmd"}])
        resumo = dados.resumo({"tarefas": console, "bot": {"vivo": True}})
        self.assertEqual(resumo["nivel"], "calmo")
        self.assertIn("com console", resumo["alerta"])

    def test_leitura_tolerante_do_powershell(self):
        from painel.flutuante import tarefas

        class _Feito:
            def __init__(self, saida, codigo=0):
                self.stdout, self.returncode = saida, codigo

        um = json.dumps({"Nome": "a", "Executa": "x"}).encode()
        self.assertEqual(len(tarefas.ler_tarefas(
            rodar=lambda *a, **k: _Feito(um))), 1)
        self.assertIsNone(tarefas.ler_tarefas(
            rodar=lambda *a, **k: _Feito(b"lixo")))
        self.assertIsNone(tarefas.ler_tarefas(
            rodar=lambda *a, **k: _Feito(b"", 1)))

        def estoura(*_a, **_k):
            raise subprocess.TimeoutExpired("powershell", 60)
        self.assertIsNone(tarefas.ler_tarefas(rodar=estoura))

    def test_o_verificador_so_le(self):
        """Nenhum caminho do verificador muda tarefa."""
        fontes = (Path(janela.__file__).with_name("tarefas.py"),
                  RAIZ / "ferramentas" / "ocultar_consoles.py")
        for fonte in fontes:
            texto = fonte.read_text(encoding="utf-8")
            for proibido in ("Set-ScheduledTask", "Register-ScheduledTask",
                             "Unregister-ScheduledTask", "/Change", "/Create",
                             "/Delete", "Disable-ScheduledTask"):
                self.assertNotIn(proibido, texto, f"{fonte.name}: {proibido}")
        self.assertFalse((RAIZ / "ferramentas" / "sem_janela.py").exists())

    def test_cli_sai_1_com_problema_e_recusa_argumento(self):
        oc = _carregar_ferramenta("ocultar_consoles")
        from painel.flutuante import tarefas
        with mock.patch.object(tarefas, "ler_tarefas",
                               return_value=[{"Nome": "a",
                                              "Executa": "a.cmd"}]), \
                mock.patch("builtins.print"):
            self.assertEqual(oc.main([]), 1)
            self.assertEqual(oc.main(["--aplicar"]), 2)
        with mock.patch.object(tarefas, "ler_tarefas",
                               return_value=[self._oculta("b")]), \
                mock.patch.object(tarefas, "_existe", return_value=True), \
                mock.patch("builtins.print"):
            self.assertEqual(oc.main([]), 0)


class Previsao(unittest.TestCase):
    POSTAR = (
        "import sys\n"
        "class V:\n"
        "    def __init__(s, i, t): s.id, s.titulo, s.parte, s.partes = "
        "i, t, 1, 6\n"
        "def fila_de_historias():\n"
        "    sys.stdout.buffer.write(b'[postar] barulho\\n')\n"
        "    return [V('historia_1:celular:p01', 'A'), "
        "V('historia_1:celular:p02', 'B')]\n"
        "def proximo_build():\n"
        "    print('[postar] 3 build(s) fora da fila')\n"
        "    return None\n"
        "def estoque():\n"
        "    return {'historias': 2, 'builds': 0}\n"
        "def atrasados_no_tiktok(canal='historias'):\n"
        "    raise RuntimeError('sem rede')\n")

    def test_json_na_ultima_linha_e_ruido_capturado(self):
        raiz = Path(tempfile.mkdtemp())
        (raiz / "ferramentas").mkdir()
        (raiz / "ferramentas" / "postar.py").write_text(self.POSTAR,
                                                         encoding="utf-8")
        feito = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "painel.flutuante.previsao",
             "--raiz", str(raiz)], cwd=str(RAIZ), capture_output=True,
            timeout=60)
        linhas = feito.stdout.decode("utf-8").strip().splitlines()
        self.assertEqual(len(linhas), 1, linhas)
        dados_ = json.loads(linhas[0])
        self.assertEqual(dados_["historias"]["id"], "historia_1:celular:p01")
        self.assertEqual(len(dados_["fila_historias"]), 1)
        self.assertIsNone(dados_["builds"])
        self.assertEqual(dados_["gordura"], {"historias": 2, "builds": 0})
        self.assertEqual(dados_["erros"], [])
        self.assertIn("[postar] barulho", dados_["avisos"])
        self.assertIn("[postar] 3 build(s) fora da fila", dados_["avisos"])

    def test_nao_chama_o_ver_nem_vistoria(self):
        """O `--ver` grava vistoria no diario; a previsao so usa as filas."""
        fonte = Path(previsao.__file__).read_text(encoding="utf-8")
        self.assertNotIn("postar_historia", fonte)
        self.assertNotIn("postar_build", fonte)
        self.assertNotIn("vistoriar_parte", fonte)
        self.assertNotIn("proxima_historia(", fonte)


def _caminhos_de_teste() -> Caminhos:
    raiz = Path(tempfile.mkdtemp())
    rt = raiz / "rt"
    (rt / "locks").mkdir(parents=True)
    (raiz / "outputs").mkdir()
    agora = datetime.now(timezone.utc)
    linhas = [json.dumps(_evento(agora - timedelta(minutes=1), pid=os.getpid(),
                                 etapa="render", ref="historia_00017",
                                 fabrica="estudio")),
              json.dumps(_evento(agora, status="erro", fabrica="gemini",
                                 detalhe="Timeout: 600s"))]
    (rt / "atividade.jsonl").write_text("\n".join(linhas) + "\n{\"ts\":",
                                        encoding="utf-8")
    (raiz / "outputs" / "postar.txt").write_text(
        "[postar] algo\n  gordura builds 0 dia(s)  <<< ABAIXO DO PISO\n",
        encoding="utf-8")
    return Caminhos(raiz=raiz, rt=rt)


class Coleta(unittest.TestCase):
    def test_coletar_monta_o_estado(self):
        c = coletor.Coletor(_caminhos_de_teste(), queue.Queue(),
                            processos=lambda: [], previsao=lambda: {})
        c._processos = [{"pid": os.getpid() + 1, "cmd": "python -m remoto",
                         "inicio": datetime.now()}]
        estado = c.coletar()
        self.assertEqual(estado["predios"]["estudio"]["status"], "trabalhando")
        self.assertEqual(estado["predios"]["gemini"]["status"], "erro")
        self.assertEqual(len(estado["erros"]), 1)
        self.assertTrue(estado["bot"]["vivo"], "o processo do bot conta")
        self.assertEqual(estado["resumo"]["nivel"], "erro")
        self.assertEqual(estado["terminais"]["postar"][-1][1], "aviso")
        self.assertEqual(estado["terminais"]["bot"], [])
        self.assertEqual(estado["publicados"], [])

    def test_o_laco_publica_na_fila_e_para(self):
        fila = queue.Queue()
        pedidos = []
        c = coletor.Coletor(_caminhos_de_teste(), fila,
                            processos=lambda: [],
                            previsao=lambda: pedidos.append(1) or {"ok": 1},
                            agendador=lambda: [{"Nome": "x",
                                                "Executa": "x.cmd"}])
        c.iniciar()
        try:
            tipo, estado = fila.get(timeout=10)
            self.assertEqual(tipo, "estado")
            self.assertEqual(estado["tarefas"]["selo"],
                             "tarefas ⚠ 1 com console")
            fim = time.monotonic() + 10
            while not c._previsao and time.monotonic() < fim:
                time.sleep(0.05)
            self.assertEqual(c._previsao, {"ok": 1})
        finally:
            c.parar()
        c._thread.join(10)
        self.assertFalse(c._thread.is_alive())
        self.assertEqual(len(pedidos), 1, "a previsao roda uma vez so")

    def test_so_a_janela_chama_after(self):
        """`after()` de outra thread quebra o Tk: o coletor nem conhece Tk."""
        for modulo in (coletor, dados, previsao):
            fonte = Path(modulo.__file__).read_text(encoding="utf-8")
            self.assertNotIn(".after(", fonte, modulo.__name__)
            self.assertNotIn("import tkinter", fonte, modulo.__name__)

    def test_a_janela_so_le(self):
        """Nenhum modulo da janela CHAMA quem publica, gera ou pega trava.

        Olha as chamadas de verdade (ast), nao o texto: a docstring explica
        por que `travas.ocupada()` nao serve, e isso nao e uma chamada.
        """
        import ast
        proibidas = {"trava", "ocupada", "locking", "publicar",
                     "postar_historia", "postar_build", "registrar",
                     "vistoriar_parte", "instalar"}
        pasta = Path(coletor.__file__).parent
        for arquivo in pasta.glob("*.py"):
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            for no in ast.walk(arvore):
                if not isinstance(no, ast.Call):
                    continue
                alvo = no.func
                nome = (alvo.attr if isinstance(alvo, ast.Attribute)
                        else getattr(alvo, "id", ""))
                self.assertNotIn(nome, proibidas,
                                 f"{arquivo.name}:{no.lineno} chama {nome}")


class _ColetorParado:
    def __init__(self):
        self.fila = queue.Queue()
        self.ritmos = []
        self.pedidos = 0

    def iniciar(self):
        pass

    def parar(self):
        pass

    def ritmo(self, escondido):
        self.ritmos.append(escondido)

    def agora(self):
        pass

    def pedir_previsao(self):
        self.pedidos += 1


class JanelaMonta(unittest.TestCase):
    def setUp(self):
        caminhos = _caminhos_de_teste()
        self.coletor = _ColetorParado()
        real = coletor.Coletor(caminhos, queue.Queue(),
                               processos=lambda: [], previsao=lambda: {},
                               agendador=lambda: [])
        real._talvez_tarefas()
        self.estado = real.coletar()
        self.app = janela.Janela(caminhos=caminhos, modo="medio", topo=False,
                                 coletor=self.coletor, iniciar=False,
                                 persistir=False)
        self.addCleanup(self._fechar)

    def _fechar(self):
        try:
            self.app.sair()
        except tk.TclError:
            pass

    def test_quatro_tamanhos_com_estado(self):
        self.coletor.fila.put(("estado", self.estado))
        self.app._drenar()
        self.assertIs(self.app.estado, self.estado)
        for modo in ("mini", "grande", "icone", "medio"):
            self.app.trocar(modo)
            self.app.update()
            largura, altura = preferencias.tamanho(
                modo, (self.app.winfo_screenwidth(),
                       self.app.winfo_screenheight()))
            self.assertEqual((self.app.winfo_width(),
                              self.app.winfo_height()), (largura, altura),
                             modo)
        self.assertEqual(self.coletor.ritmos[-2:], [True, False])
        for aba, _rotulo in janela.ABAS:
            self.app.aba(aba)
            self.app.update()
        self.assertEqual(self.app._abas["erros"][0].cget("text"), "Erros (1)")

    def test_icone_restaura_o_tamanho_anterior(self):
        self.app.trocar("grande")
        self.app.trocar("icone")
        self.app.restaurar()
        self.assertEqual(self.app.modo, "grande")

    def test_detalhes_abrem_sem_quebrar(self):
        self.coletor.fila.put(("estado", self.estado))
        self.app._drenar()
        self.app.detalhe_predio("estudio")
        self.app.detalhe_erro(self.estado["erros"][0])
        self.app.detalhe_tarefas()
        self.assertEqual(self.app._lbl_tarefas.cget("text"),
                         "sem tarefas no Agendador")
        janelas = [w for w in self.app.winfo_children()
                   if isinstance(w, tk.Toplevel)]
        self.assertEqual(len(janelas), 3)
        self.app.trocar("mini")
        self.assertEqual(len([w for w in self.app.winfo_children()
                              if isinstance(w, tk.Toplevel)]), 3,
                         "trocar de tamanho nao fecha o detalhe aberto")

    def test_prova_nao_grava_preferencias(self):
        self.app.trocar("grande")
        self.assertFalse(self.app.caminhos.preferencias.exists())
        self.app.prever_agora()
        self.assertEqual(self.coletor.pedidos, 1)


if __name__ == "__main__":
    unittest.main()
