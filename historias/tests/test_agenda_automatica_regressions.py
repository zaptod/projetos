# -*- coding: utf-8 -*-
"""Criação automática de histórias nos horários da agenda (08/09/2026).

O Adrian pediu criação automática às 6, 7, 8, 10, 12, 15, 17 e 20 — oito
disparos por dia, cada um fazendo uma história inteira. O número que manda no
desenho: uma história custa **~4h** (medido na 8: 5 min de roteiro, 3h13 das
84 imagens, 53 min dos seis vídeos). Oito por dia não cabem em 24h, e dois ao
mesmo tempo brigariam pelo MESMO perfil de Chrome do LLM e pela MESMA conta do
PicassoIA — que ainda é dividida com o canal de builds.

Então o que estes testes travam não é "roda oito vezes", é o que impede os
oito disparos de virar bagunça:

    trava      disparo que encontra rodada em andamento SAI, não espera
    pausa      o interruptor da Vila segura a tarefa agendada também
    retomar    termina a história pela metade antes de começar outra
    tarefa     interativa (sessão gráfica), nunca em sessão 0

Rode de dentro de historias/:
    python -m unittest tests.test_agenda_automatica_regressions -v
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from contos.pipeline import agenda, tarefas                    # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]

# O que ele pediu. Se alguém mexer no config sem querer, o teste conta.
# De madrugada desde 13/09/2026, e nos horarios da grade so para nao ficar
# sem video. `carregar` devolve ordenado.
HORAS_PEDIDAS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 17, 20, 23]


class ConfigTests(unittest.TestCase):
    def test_a_agenda_e_a_que_ele_pediu(self):
        self.assertEqual(agenda.carregar()["horas"], HORAS_PEDIDAS)

    def test_horas_repetidas_ou_impossiveis_sao_descartadas(self):
        with TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "agenda.json"
            caminho.write_text(json.dumps(
                {"horas": [20, 6, 6, 25, -1, 12]}), encoding="utf-8")
            self.assertEqual(agenda.carregar(caminho)["horas"], [6, 12, 20])


class UmaDeCadaVezTests(unittest.TestCase):
    """A trava é o que faz oito disparos caberem num dia de 24 horas.

    CUIDADO AO MEXER AQUI, aprendido do jeito caro em 08/09/2026: a primeira
    versão deste teste segurava a trava e chamava `rodar()` no MESMO processo,
    esperando que ela recusasse. `travas.trava` é REENTRANTE — trava que já é
    sua devolve True de novo, de propósito, para o `finally` de dentro não
    soltar a trava de fora. Resultado: `rodar()` seguiu em frente, abriu o
    Gemini e escreveu cinco partes de uma história antes de eu perceber.

    A reentrância não é defeito e é justamente por isso que a proteção
    funciona em produção: os oito disparos são oito PROCESSOS separados do
    Agendador, e entre processos a trava é um arquivo. Por isso o teste da
    trava embaixo usa subprocesso de verdade — e todos os testes que chamam
    `rodar()` trocam `_trabalhar` por um dublê, para um deslize nunca mais
    conseguir gastar 4h de PicassoIA.
    """

    def setUp(self):
        self.chamou = []
        original = agenda._trabalhar

        def _duble(*a, **k):
            self.chamou.append(1)
            return {"feito": "historia", "erros": []}

        agenda._trabalhar = _duble
        self.addCleanup(setattr, agenda, "_trabalhar", original)
        # `rodar()` grava no diario ANTES de qualquer checagem. Sem desviar o
        # OUTPUTS, cada teste escreve "disparo das HH:MM" no log de PRODUCAO —
        # e foi o que aconteceu em 08/09/2026: linhas de teste no meio do
        # registro de uma rodada de verdade, que e onde se procura defeito.
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(setattr, agenda, "OUTPUTS", agenda.OUTPUTS)
        agenda.OUTPUTS = Path(self._tmp.name)

    def test_a_trava_vale_entre_processos(self):
        """O que importa de verdade: dois disparos do Agendador não se cruzam.

        Não passa por `rodar()` de propósito — a pergunta aqui é só sobre a
        trava, e um subprocesso que nem sabe o que é pipeline responde melhor.

        E usa um nome PRÓPRIO, não `agenda.TRAVA`: com o nome de produção este
        teste falhava sempre que uma rodada de verdade estivesse acontecendo
        na máquina (aconteceu em 08/09/2026). Teste que depende do que mais
        está rodando não mede nada — o nome certo é conferido no teste abaixo.
        """
        import os
        import subprocess
        import sys
        from builds import travas

        nome = f"teste_agenda_{os.getpid()}"
        # Sem cirurgia de sys.path: os pacotes do repositorio estao instalados
        # (workspace do pyproject), e a catraca de arquitetura conta cada
        # `sys.path.insert` do repo — inclusive dentro de string.
        codigo = ("from builds import travas;"
                  "ctx = travas.trava('%s', esperar=0.0);"
                  "print('peguei' if ctx.__enter__() else 'ocupada')" % nome)

        with travas.trava(nome, esperar=0.0) as minha:
            self.assertTrue(minha)
            proc = subprocess.run([sys.executable, "-c", codigo],
                                  capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.stdout.strip(), "ocupada", proc.stderr[-300:])

    def test_a_rodada_usa_uma_trava_so_dela(self):
        """O nome não pode colidir com o do PicassoIA nem com o dos builds."""
        self.assertEqual(agenda.TRAVA, "historias__auto")
        fonte = Path(agenda.__file__).read_text(encoding="utf-8")
        self.assertIn("trava(TRAVA,", fonte)

    def test_disparo_com_a_trava_ocupada_nao_trabalha(self):
        import contextlib
        from builds import travas

        original = travas.trava

        @contextlib.contextmanager
        def _ocupada(nome, esperar=0.0):
            yield False

        travas.trava = _ocupada
        self.addCleanup(setattr, travas, "trava", original)
        # SEM JANELA: o config real so deixa rodar de madrugada, e este teste
        # pergunta sobre a TRAVA. Rodando de dia com o config real, a rodada
        # sairia "fora da janela" antes de chegar nela, e o teste dependeria
        # do relogio.
        config = {**agenda.carregar(), "janela_pesada": None}
        resultado = agenda.rodar(config=config, tela=None)
        self.assertEqual(resultado["motivo"], "ja rodando")
        self.assertEqual(self.chamou, [], "nao podia ter comecado a trabalhar")

    def test_a_trava_nao_espera(self):
        """Esperar empurraria a fila para cima do disparo seguinte.

        Com oito disparos e rodadas de ~4h, um disparo que ficasse esperando
        acordaria no meio da rodada seguinte e o problema só se mudaria de
        lugar. Sair é a resposta certa: o próximo horário tenta de novo.
        """
        fonte = Path(agenda.__file__).read_text(encoding="utf-8")
        self.assertIn("trava(TRAVA, esperar=0.0)", fonte)

    def test_a_pausa_da_vila_segura_a_tarefa_agendada(self):
        from builds.identity import controle
        original = controle.pausado_para
        controle.pausado_para = lambda *a, **k: True
        self.addCleanup(setattr, controle, "pausado_para", original)
        resultado = agenda.rodar(tela=None)
        self.assertEqual(resultado["motivo"], "pausado")
        self.assertEqual(self.chamou, [])

    def test_agenda_desligada_nao_cria_nada(self):
        resultado = agenda.rodar(config={"ativo": False, "horas": []},
                                 tela=None)
        self.assertEqual(resultado["motivo"], "agenda desligada")
        self.assertEqual(self.chamou, [])


class IncompletasTests(unittest.TestCase):
    """Terminar a história pela metade vem antes de começar outra."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.original = agenda.OUTPUTS
        agenda.OUTPUTS = self.raiz
        self.addCleanup(setattr, agenda, "OUTPUTS", self.original)

    def _fingir(self, roteiros: dict, faltam: dict):
        from contos.imagens import fila
        from contos.roteiro import roteiro as R
        listar, carregar, resumo = R.listar, R.carregar, fila.resumo
        R.listar = lambda: [{"historia_id": k} for k in roteiros]
        R.carregar = lambda hid: roteiros[hid]
        fila.resumo = lambda hid, rot=None, parte=None: {
            "total": 14, "prontas": 14 - faltam.get(hid, 0),
            "faltam": faltam.get(hid, 0), "completa": not faltam.get(hid, 0)}
        self.addCleanup(setattr, R, "listar", listar)
        self.addCleanup(setattr, R, "carregar", carregar)
        self.addCleanup(setattr, fila, "resumo", resumo)

    def _serie(self, provedor="gemini", partes=2):
        return {"serie": True, "provedor": provedor,
                "partes": [{"n": i} for i in range(1, partes + 1)]}

    def _video(self, historia_id: str, parte: int):
        pasta = self.raiz / historia_id
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / f"final_celular_p{parte:02d}.mp4").write_bytes(b"x" * 10)

    def test_historia_sem_imagem_e_pendente(self):
        self._fingir({"historia_00010": self._serie()}, {"historia_00010": 3})
        self._video("historia_00010", 1)
        self._video("historia_00010", 2)
        pendentes = agenda.incompletas()
        self.assertEqual(len(pendentes), 1)
        self.assertEqual(pendentes[0]["imagens_faltando"], 3)

    def test_historia_sem_video_e_pendente(self):
        self._fingir({"historia_00010": self._serie()}, {})
        self._video("historia_00010", 1)          # falta a parte 2
        pendentes = agenda.incompletas()
        self.assertEqual(pendentes[0]["partes_sem_video"], [2])

    def test_historia_completa_nao_e_pendente(self):
        self._fingir({"historia_00010": self._serie()}, {})
        self._video("historia_00010", 1)
        self._video("historia_00010", 2)
        self.assertEqual(agenda.incompletas(), [])

    def test_historia_de_teste_nunca_entra(self):
        """`provedor: fake` tem imagens de placeholder.

        Sem esta guarda, a rodada acharia a `historia_00002` "incompleta" e
        gastaria o PicassoIA gerando de verdade as cenas de um teste.
        """
        self._fingir({"historia_00002": self._serie(provedor="fake")},
                     {"historia_00002": 16})
        self.assertEqual(agenda.incompletas(), [])

    def test_terminar_vem_antes_de_criar(self):
        fonte = Path(agenda.__file__).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def _trabalhar("):]
        self.assertLess(corpo.index("incompletas()"),
                        corpo.index("pipeline.gerar("))


class JanelaPesadaTests(unittest.TestCase):
    """Pedido de 13/09/2026: trabalho pesado de madrugada, entrega de dia."""

    JANELA = {"inicio": 23, "fim": 6}

    def test_a_janela_atravessa_a_meia_noite(self):
        for hora in (23, 0, 3, 5):
            self.assertTrue(agenda.na_janela(hora, self.JANELA), hora)
        for hora in (6, 7, 12, 22):
            self.assertFalse(agenda.na_janela(hora, self.JANELA), hora)

    def test_sem_janela_roda_a_qualquer_hora(self):
        self.assertTrue(agenda.na_janela(14, None))

    def test_23h_e_3h_sao_a_mesma_noite(self):
        """Senao a metrica de "uma vez por noite" rodaria duas."""
        from datetime import datetime
        self.assertEqual(
            agenda.chave_da_noite(datetime(2026, 9, 12, 23, 20), self.JANELA),
            agenda.chave_da_noite(datetime(2026, 9, 13, 3, 20), self.JANELA))

    def test_quanto_falta_para_fechar(self):
        from datetime import datetime
        self.assertEqual(40, agenda.minutos_ate_fechar(
            datetime(2026, 9, 13, 5, 20), self.JANELA))
        self.assertEqual(400, agenda.minutos_ate_fechar(
            datetime(2026, 9, 12, 23, 20), self.JANELA))

    def test_a_agenda_cobre_a_madrugada_e_os_horarios_da_grade(self):
        from builds import grade
        config = agenda.carregar()
        janela = config["janela_pesada"]
        self.assertEqual((23, 6), (janela["inicio"], janela["fim"]))
        noite = [h for h in config["horas"] if agenda.na_janela(h, janela)]
        dia = [h for h in config["horas"] if not agenda.na_janela(h, janela)]
        self.assertEqual([0, 1, 2, 3, 4, 5, 23], noite)
        self.assertEqual(sorted(grade.HORAS), dia)

    def test_fora_da_janela_sai_antes_da_trava_e_nao_e_erro(self):
        """A tarefa perdida roda quando o PC volta, de manha: tem de sair."""
        fonte = Path(agenda.__file__).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def rodar("):]
        self.assertLess(corpo.index("na_janela("),
                        corpo.index("travas.trava("))
        self.assertGreaterEqual(fonte.count('"fora da janela"'), 3)

    def test_historia_nova_so_comeca_se_couber_na_janela(self):
        fonte = Path(agenda.__file__).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def _trabalhar("):]
        self.assertLess(corpo.index("minutos_por_historia"),
                        corpo.index("pipeline.gerar("))


class ModoDiaTests(unittest.TestCase):
    """De dia so o que evita ficar sem video (13/09/2026).

    "esse tipo de problema eu quero que seja resolvido a qualquer momento, a
    prioridade e nao ficar sem video."
    """

    def _dublar(self, barrados: int, aprovados: int):
        for nome, n in (("barrados_no_estoque", barrados),
                        ("aprovados_no_estoque", aprovados)):
            self.addCleanup(setattr, agenda, nome, getattr(agenda, nome))
            setattr(agenda, nome, lambda n=n: [object()] * n)

    def test_horarios_que_ainda_faltam_hoje(self):
        from datetime import datetime
        self.assertEqual(8, agenda.horarios_restantes(
            datetime(2026, 9, 13, 5, 0)))
        self.assertEqual(3, agenda.horarios_restantes(
            datetime(2026, 9, 13, 13, 0)))
        self.assertEqual(0, agenda.horarios_restantes(
            datetime(2026, 9, 13, 21, 0)))

    def test_falta_video_quando_o_estoque_nao_cobre_o_dia(self):
        from datetime import datetime
        meio_dia = datetime(2026, 9, 13, 13, 0)
        self.assertTrue(agenda.falta_video(3, meio_dia))
        self.assertFalse(agenda.falta_video(4, meio_dia))

    def test_de_dia_sem_barrado_e_com_estoque_sai(self):
        from datetime import datetime
        self._dublar(barrados=0, aprovados=11)
        self.assertIsNone(agenda.modo_dia({}, datetime(2026, 9, 13, 13, 0)))

    def test_de_dia_com_barrado_conserta_e_nao_cria(self):
        from datetime import datetime
        self._dublar(barrados=5, aprovados=11)
        dia = agenda.modo_dia({"reparos_de_dia": 2},
                              datetime(2026, 9, 13, 13, 0))
        self.assertTrue(dia["config"]["so_consertar"])
        self.assertIsNone(dia["config"]["janela_pesada"])
        self.assertFalse(dia["config"]["revisar_estoque_a_noite"])
        self.assertEqual(2, dia["config"]["reparos_por_rodada"])

    def test_de_dia_faltando_video_cria_tambem(self):
        from datetime import datetime
        self._dublar(barrados=0, aprovados=1)
        dia = agenda.modo_dia({}, datetime(2026, 9, 13, 13, 0))
        self.assertFalse(dia["config"]["so_consertar"])
        self.assertTrue(dia["config"]["retomar_incompletas"])

    def test_so_consertar_para_antes_de_criar(self):
        fonte = Path(agenda.__file__).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def _trabalhar("):]
        self.assertLess(corpo.index("reparo.rodada"),
                        corpo.index('config.get("so_consertar")'))
        self.assertLess(corpo.index('config.get("so_consertar")'),
                        corpo.index("pipeline.gerar("))


class TarefaDoWindowsTests(unittest.TestCase):
    def test_uma_tarefa_por_hora_com_nome_da_familia(self):
        nomes = [tarefas.nome_da_tarefa(h) for h in HORAS_PEDIDAS]
        self.assertEqual(len(set(nomes)), len(HORAS_PEDIDAS))
        self.assertTrue(all(n.startswith(tarefas.PREFIXO) for n in nomes))
        self.assertIn("Historias_auto_23", nomes)

    def test_o_lancador_entra_na_pasta_certa_e_chama_o_python_certo(self):
        import sys
        texto = tarefas.escrever_lancador().read_text(encoding="utf-8")
        self.assertIn(f'cd /d "{RAIZ}"', texto)
        self.assertIn(sys.executable, texto)
        self.assertIn("main.py auto", texto)

    def test_a_tarefa_e_interativa_e_nao_de_sessao_0(self):
        """O navegador precisa de área de trabalho.

        `/RU SYSTEM` faria a tarefa rodar na sessão 0, onde não existe tela: o
        Chrome abriria e ficaria esperando para sempre. O LLM, o PicassoIA e o
        Studio todos dependem do perfil logado, então a tarefa tem que ser do
        usuário.
        """
        fonte = Path(tarefas.__file__).read_text(encoding="utf-8")
        self.assertNotIn("SYSTEM", fonte.split('"""', 2)[-1])
        self.assertIn('"/RL", "LIMITED"', fonte)


class SaidaNaoPodeTravarTests(unittest.TestCase):
    """O `print` que segurou a rodada por 13 minutos (08/09/2026).

    Primeira manhã da agenda ligada. A rodada das 08:00 escreveu o roteiro
    inteiro, abriu o PicassoIA, logou — e parou. Treze minutos, zero imagens,
    CPU em zero, Chrome ocioso. O py-spy mostrou onde:

        ensure_logged_in (builds/identity/session.py:77)   <- um print()

    Não era o PicassoIA nem a rede: o processo não conseguia escrever uma
    linha no console que o Agendador dá a ele e ninguém esvazia. Escrita em
    console cheio bloqueia para sempre, e a rodada morre em pé — de janela
    aberta, segurando a trava do PicassoIA que o canal de builds também usa.

    Duas camadas consertam, e as duas ficam travadas aqui: o .cmd redireciona
    para arquivo, e a rodada troca `sys.stdout` por um que grava no diário.
    A segunda também resolve o motivo de ele não ter percebido antes — tudo
    que a geração de imagem conta sobre si mesma sai por `print`, então o
    diário de uma rodada de 4h tinha três linhas.
    """

    def test_o_lancador_redireciona_a_saida_para_arquivo(self):
        texto = tarefas.escrever_lancador().read_text(encoding="utf-8")
        self.assertIn(">>", texto)
        self.assertIn("2>&1", texto)
        self.assertIn("auto_saida.txt", texto)

    def test_print_vai_para_o_diario_com_horario(self):
        import sys
        with TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "diario.txt"
            antes = sys.stdout
            sys.stdout = agenda._SaidaNoDiario(alvo, antes)
            try:
                print("[picasso] gerando... 21s")
            finally:
                sys.stdout = antes
            linha = alvo.read_text(encoding="utf-8").strip()
        self.assertIn("[picasso] gerando... 21s", linha)
        self.assertRegex(linha, r"^\d\d:\d\d:\d\d ")

    def test_nao_ecoa_para_console_que_nao_e_terminal(self):
        """O eco é o que trava. Só stream interativo de verdade recebe cópia.

        O console do Agendador é exatamente o que bloqueia, então ele não
        pode receber cópia — e ele não é um terminal.
        """
        class _Falso:
            def __init__(self, tty):
                self.tty, self.escreveu = tty, []

            def isatty(self):
                return self.tty

            def write(self, t):
                self.escreveu.append(t)
                return len(t)

        uma_linha = "linha" + chr(10)
        with TemporaryDirectory() as tmp:
            nao_tty = _Falso(False)
            saida = agenda._SaidaNoDiario(Path(tmp) / "d.txt", nao_tty)
            saida.write(uma_linha)
            self.assertEqual(nao_tty.escreveu, [])

            tty = _Falso(True)
            saida = agenda._SaidaNoDiario(Path(tmp) / "e.txt", tty)
            saida.write(uma_linha)
            self.assertEqual(tty.escreveu, [uma_linha])

    def test_o_diario_nao_derruba_a_rodada_se_o_disco_negar(self):
        # Log que levanta seria pior do que log que falta: a rodada inteira
        # cairia por causa de uma linha de texto.
        saida = agenda._SaidaNoDiario(Path("Z:/nao/existe/d.txt"), None)
        self.assertEqual(saida.write("linha" + chr(10)), 6)

    def test_cada_linha_aparece_UMA_vez(self):
        """Log em dobro é log que ninguém lê (08/09/2026).

        A primeira versão tinha dois escritores no mesmo arquivo: `_diario`
        gravava direto E chamava `tela=print`, que já estava redirecionado
        para o mesmo diário. Toda linha saía duas vezes — e num arquivo de
        4h de corrida isso é a diferença entre acompanhar e desistir.
        """
        import sys
        from builds import travas

        with TemporaryDirectory() as tmp:
            original_outputs = agenda.OUTPUTS
            agenda.OUTPUTS = Path(tmp)
            self.addCleanup(setattr, agenda, "OUTPUTS", original_outputs)

            def _fala(config, headless, log):
                log("[auto] linha que nao pode duplicar")
                print("[picasso] print que tambem nao pode duplicar")
                return {"feito": "historia", "erros": []}

            # A RESTAURACAO NAO E ZELO, e correcao: sem ela `_trabalhar`
            # ficava sendo `_fala` pelo RESTO da sessao, e todo teste seguinte
            # que o chamasse recebia `{"feito": "historia"}` — sem `motivo`,
            # sem `erros` de verdade. Foi o que quebrou
            # `test_acima_do_teto_a_criacao_para` com um KeyError que nao
            # tinha nada a ver com o freio de estoque.
            self.addCleanup(setattr, agenda, "_trabalhar", agenda._trabalhar)
            agenda._trabalhar = _fala
            # A trava e de verdade e uma rodada real pode estar segurando ela
            # nesta maquina — o teste nao pode depender disso (ja quebrou uma
            # vez). Aqui a pergunta e sobre o LOG, entao a trava e concedida.
            import contextlib
            original_trava = travas.trava

            @contextlib.contextmanager
            def _livre(nome, esperar=0.0):
                yield True

            travas.trava = _livre
            self.addCleanup(setattr, travas, "trava", original_trava)
            antes = sys.stdout
            # `avisar_telegram: False` NAO e detalhe: sem ele este teste chega
            # no caminho do aviso e manda mensagem DE VERDADE para o celular
            # dele. Rodar a suite nao pode tocar o telefone de ninguem.
            agenda.rodar(config={"ativo": True, "horas": [],
                                 "avisar_telegram": False}, tela=None)
            self.assertIs(sys.stdout, antes)

            diarios = list((Path(tmp) / "_logs").glob("auto_*.txt"))
            self.assertEqual(len(diarios), 1)
            texto = diarios[0].read_text(encoding="utf-8")
        self.assertEqual(texto.count("linha que nao pode duplicar"), 1)
        self.assertEqual(texto.count("print que tambem nao pode duplicar"), 1)

    def test_NENHUM_teste_manda_telegram_de_verdade(self):
        """A suite nao pode tocar o telefone dele.

        `agenda.rodar` avisa por padrao (`avisar_telegram` cai em True quando
        a chave falta), e um teste que chegue no fim do caminho manda mensagem
        DE VERDADE — descoberto rodando a suite em 08/09/2026. Todo teste que
        passa por `_trabalhar` tem que desligar o aviso ou dublar o subprocesso.
        """
        fonte = Path(__file__).read_text(encoding="utf-8")
        chamadas = fonte.count("agenda.rodar(")
        seguras = (fonte.count('"avisar_telegram": False')
                   + fonte.count('"ativo": False')
                   + fonte.count("subprocess.run = ")
                   # os que saem antes de trabalhar: trava ocupada e pausa
                   + fonte.count('"ja rodando"')
                   + fonte.count('"pausado"'))
        self.assertLessEqual(chamadas, seguras,
                             "algum `rodar()` pode estar mandando Telegram")

    def test_a_rodada_devolve_a_saida_original_no_fim(self):
        import sys
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(setattr, agenda, "OUTPUTS", agenda.OUTPUTS)
        agenda.OUTPUTS = Path(tmp.name)
        antes_out, antes_err = sys.stdout, sys.stderr
        agenda.rodar(config={"ativo": False, "horas": []}, tela=None)
        self.assertIs(sys.stdout, antes_out)
        self.assertIs(sys.stderr, antes_err)


class AvisoNoTelegramTests(unittest.TestCase):
    """A rodada conta no celular o que fez (08/09/2026).

    Ele pediu depois de assistir uma rodada travada por 13 minutos sem
    nenhum sinal. O bot de `remoto/` ja existia e ja alertava em erro — mas
    so enquanto o processo dele estivesse no ar, e naquele dia ele NAO
    estava. Por isso a rodada avisa por conta propria, por subprocesso.
    """

    def _resultado(self, **kw):
        base = {"feito": "historia", "historia_id": "historia_00009",
                "titulo": "Um titulo qualquer", "partes": 6, "cenas": 84,
                "erros": []}
        base.update(kw)
        return base

    def test_historia_pronta_conta_o_que_saiu(self):
        texto = agenda.mensagem(self._resultado(), 5623)
        self.assertIn("historia_00009", texto)
        self.assertIn("Um titulo qualquer", texto)
        self.assertIn("6 partes", texto)
        self.assertIn("84 cenas", texto)
        self.assertIn("1h33", texto)

    def test_problema_aparece_no_aviso(self):
        texto = agenda.mensagem(
            self._resultado(erros=["parte 3: sem imagem"]), 60)
        self.assertIn("1 problema", texto)
        self.assertIn("parte 3: sem imagem", texto)

    def test_falha_diz_o_motivo(self):
        texto = agenda.mensagem(
            {"feito": "nada", "motivo": "roteiro falhou",
             "erro": "o gemini nao respondeu"}, 30)
        self.assertIn("falhou", texto)
        self.assertIn("o gemini nao respondeu", texto)

    def test_disparo_que_sai_sem_fazer_nada_NAO_avisa(self):
        """4 a 6 por dia dizendo a mesma coisa vira aviso que se ignora."""
        for motivo in ("ja rodando", "pausado", "agenda desligada",
                       "estoque cheio"):
            self.assertIsNone(
                agenda.mensagem({"feito": "nada", "motivo": motivo}, 1),
                motivo)

    def test_o_aviso_sai_pela_raiz_do_monorepo(self):
        """`remoto` nao esta instalado: so importa com a raiz como cwd."""
        import subprocess
        visto = {}

        def _falso(cmd, **kw):
            visto["cmd"], visto["cwd"] = cmd, kw.get("cwd")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        original = subprocess.run
        subprocess.run = _falso
        self.addCleanup(setattr, subprocess, "run", original)
        self.assertTrue(agenda.avisar("oi", log=lambda *_a: None))
        self.assertIn("-m", visto["cmd"])
        self.assertIn("remoto", visto["cmd"])
        self.assertIn("--avisar", visto["cmd"])
        self.assertEqual(Path(visto["cwd"]), RAIZ.parent)

    def test_telegram_fora_do_ar_nao_derruba_a_rodada(self):
        # Quatro horas de trabalho nao se perdem porque o aviso falhou.
        import subprocess
        original = subprocess.run

        def _explode(*_a, **_kw):
            raise OSError("sem rede")

        subprocess.run = _explode
        self.addCleanup(setattr, subprocess, "run", original)
        self.assertFalse(agenda.avisar("oi", log=lambda *_a: None))

    def test_o_lancador_forca_utf8(self):
        """Sem `-X utf8` a rodada morre no primeiro acento.

        A saida vai para ARQUIVO, e o Python assume a pagina de codigo do
        Windows (cp1252) — um "ç" ou um emoji vira UnicodeEncodeError.
        """
        texto = tarefas.escrever_lancador().read_text(encoding="utf-8")
        self.assertIn("-X utf8", texto)
        self.assertIn("-u", texto)


class NaoRenderizarSemImagemTests(unittest.TestCase):
    """Parte com imagem faltando fica para o proximo disparo (08/09/2026).

    O render nao se recusa a rodar sem imagem: ele desenha um cartao
    tipografico no lugar e entrega um mp4 que PARECE pronto. Na historia 10 a
    cena 1 da parte 1 — o gancho — estourou os 600 s do PicassoIA; sem esta
    guarda o video sairia com texto no primeiro segundo, que e onde a pessoa
    decide ficar. A historia 5 ja tinha passado por isso sem ninguem ver.

    Adiar custa horas. Publicar assim custa o video.
    """

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, agenda, "OUTPUTS", agenda.OUTPUTS)
        agenda.OUTPUTS = Path(self.tmp.name)

        from contos.imagens import fila
        from contos.roteiro import roteiro as R
        cenas = [{"n": i, "imagem": "a photo", "tempo": 4,
                  "narracao": f"fala {i}"} for i in range(1, 15)]
        self.roteiro = {"serie": True, "provedor": "gemini", "total_cenas": 28,
                        "titulo": "T",
                        "partes": [{"n": 1, "cenas": cenas},
                                   {"n": 2, "cenas": cenas}]}
        self.addCleanup(setattr, R, "carregar", R.carregar)
        R.carregar = lambda _hid: self.roteiro
        self.addCleanup(setattr, fila, "resumo", fila.resumo)
        fila.resumo = lambda *a, **k: {"total": 14, "prontas": 14,
                                       "faltam": 0, "completa": True}
        # a parte 1 esta com uma imagem faltando; a 2 esta inteira
        self.addCleanup(setattr, fila, "resumo_por_parte", fila.resumo_por_parte)
        fila.resumo_por_parte = lambda *a, **k: [
            {"parte": 1, "total": 14, "prontas": 13, "faltam": 1},
            {"parte": 2, "total": 14, "prontas": 14, "faltam": 0}]

    def test_so_renderiza_a_parte_completa(self):
        renderizadas = []

        class _Pipeline:
            @staticmethod
            def render(_hid, parte=None, log=None):
                renderizadas.append(parte)

        resultado = agenda._terminar(_Pipeline(), "historia_00010", False,
                                     lambda *_a: None, criada=False)
        self.assertEqual(renderizadas, [2], "renderizou parte sem imagem")
        self.assertTrue(any("imagem(ns) faltando" in e
                            for e in resultado["erros"]))

    def test_o_adiamento_aparece_no_aviso(self):
        resultado = agenda._terminar(
            type("P", (), {"render": staticmethod(lambda *a, **k: None)})(),
            "historia_00010", False, lambda *_a: None, criada=False)
        texto = agenda.mensagem(resultado, 60)
        self.assertIn("video adiado", texto)


class TodoErroNoMesmoLugarTests(unittest.TestCase):
    """A falha da rodada entra no ledger compartilhado (08/09/2026).

    Pedido dele: "os erros que acontecem na minha maquina vao para algum lugar
    que o Claude possa pegar". O lugar e `atividade.jsonl` — de onde o bot tira
    os alertas e onde a apuracao automatica procura o que investigar.

    As ETAPAS ja registravam (imagens, LLM). A rodada em si nao: uma falha dela
    ficava so no log de texto, sem chegar ao Telegram nem ao Claude.
    """

    def test_falha_da_rodada_vira_evento_de_erro(self):
        from builds import atividade
        registrados = []
        original = atividade.registrar
        atividade.registrar = lambda *a, **k: registrados.append(a)
        self.addCleanup(setattr, atividade, "registrar", original)

        agenda._registrar_erro({"feito": "nada", "motivo": "roteiro falhou",
                                "erro": "o gemini nao respondeu"})
        self.assertTrue(registrados)
        fabrica, status, detalhe = registrados[0][:3]
        self.assertEqual(status, "erro")
        self.assertIn("gemini", detalhe)

    def test_disparo_que_sai_sem_fazer_nada_NAO_vira_erro(self):
        """Trava ocupada e pausa sao o funcionamento normal, nao defeito.

        Registrar isso encheria o ledger 4 a 6 vezes por dia e faria a apuracao
        automatica gastar sessao investigando o que esta certo.
        """
        fonte = Path(agenda.__file__).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("_registrar_erro(resultado)") - 600:]
        for normal in ('"ja rodando"', '"pausado"', '"agenda desligada"'):
            self.assertIn(normal, corpo.split("_registrar_erro")[0])

    def test_registrar_erro_nunca_derruba_a_rodada(self):
        from builds import atividade
        original = atividade.registrar

        def _explode(*_a, **_k):
            raise RuntimeError("ledger fora do ar")

        atividade.registrar = _explode
        self.addCleanup(setattr, atividade, "registrar", original)
        agenda._registrar_erro({"feito": "nada", "motivo": "x"})   # nao levanta


class GorduraDeEstoqueTests(unittest.TestCase):
    """O canal nao pode ficar sem video novo (08/09/2026).

    Ele pediu: "quero que meus canais tenham pelo menos um video novo por dia,
    isso significa que preciso ter um video de gordura ja pronto pra soltar
    naquele horario e nao comecar a gerar ele naquele horario".

    A postagem JA so escolhe do que esta pronto — ela nunca gera. O que
    faltava era vigiar a gordura pelos DOIS lados: nao deixar acabar, e nao
    deixar crescer sem fim. Medido no mesmo dia: a criacao entrega 24 a 36
    videos/dia e a postagem consome 1 — sem teto, em um mes sao ~800 videos
    parados.
    """

    def test_o_estoque_e_medido_em_DIAS_de_postagem(self):
        """Um video por dia, entao um pendente = um dia.

        Antes contava HISTORIAS nao publicadas, e a conta quebrou no dia em
        que a postagem passou a ser parte por parte: historia com a parte 1 no
        ar e cinco pendentes contava como publicada e sumia do estoque.
        """
        fonte = Path(agenda.__file__).read_text(encoding="utf-8")
        self.assertIn("def dias_de_estoque(", fonte)
        corpo = fonte[fonte.index("def dias_de_estoque("):]
        self.assertIn('v.id not in ja', corpo)

    def test_o_teto_e_um_DIA_de_grade(self):
        """Pedido dele em 10/09/2026: "gordura de apenas um dia em tudo".

        DERIVADO da grade, e nao um numero solto: se a grade for de 8 para 12
        horarios, o teto acompanha sozinho. Numero fixo ao lado de uma grade
        que muda vira mentira na primeira mudanca.
        """
        config = agenda.carregar()
        self.assertGreater(config["piso_de_estoque"], 0)
        from builds import grade
        self.assertEqual(len(grade.HORAS), agenda.teto_de_estoque(config))

    def test_os_TRES_estados_do_teto(self):
        """A diferenca entre "derivar" e "desligado" ja se perdeu uma vez.

        Ao fazer `0` significar "derive da grade" eu apaguei sem querer a
        valvula de escape que existia — `0` sempre foi "freio desligado".
        Ausente = derivar; 0 = desligado; N = N.
        """
        from builds import grade
        self.assertEqual(len(grade.HORAS),
                         agenda.teto_de_estoque({"horas": [1, 2]}))
        self.assertEqual(0, agenda.teto_de_estoque(
            {"horas": [1, 2], "teto_de_estoque": 0}))
        self.assertEqual(5, agenda.teto_de_estoque(
            {"horas": [1, 2], "teto_de_estoque": 5}))

    def test_acima_do_teto_a_criacao_para(self):
        """CUIDADO AO MEXER: este teste ja gerou historia de verdade.

        Ele dublava `dias_de_estoque`; quando o teto passou a olhar
        `dias_de_estoque_novo`, o duble deixou de valer, o estoque real deu 0,
        o freio nao pegou e `_trabalhar` abriu o navegador e escreveu uma
        historia inteira (08/09/2026). Por isso agora `pipeline.gerar` tambem
        e dublado: mesmo que o freio falhe, nada sai da maquina.
        """
        criou = []
        for nome in ("dias_de_estoque", "dias_de_estoque_novo"):
            self.addCleanup(setattr, agenda, nome, getattr(agenda, nome))
            setattr(agenda, nome, lambda: 999)

        from contos.pipeline import controller
        original = controller.Pipeline.gerar
        controller.Pipeline.gerar = lambda *a, **k: criou.append(1)
        self.addCleanup(setattr, controller.Pipeline, "gerar", original)

        # O REPARADOR TAMBEM, e pelo mesmo motivo do aviso la em cima.
        # `_trabalhar` chama `reparo.rodada()` ANTES do freio, e a rodada abre
        # o PicassoIA para refazer cena com colagem. Este teste passava sem
        # dublar porque `cenas_com_colagem` estava cega ao vocabulario da IA e
        # nunca achava nada; consertada a cegueira em 12/09/2026, o teste
        # encontrou 14 cenas de verdade no `outputs/` e a suite parou de
        # terminar (900 s de estouro). Duble que so era seguro por causa de
        # um defeito nao e duble.
        from contos.pipeline import reparo
        antes_rodada = reparo.rodada
        reparo.rodada = lambda **k: {"barrados": 0, "consertados": 0,
                                     "insistentes": [], "acoes": []}
        self.addCleanup(setattr, reparo, "rodada", antes_rodada)

        resultado = agenda._trabalhar(
            {"retomar_incompletas": False, "teto_de_estoque": 8},
            False, lambda *_a: None)
        self.assertEqual(resultado["motivo"], "estoque cheio")
        self.assertEqual(criou, [], "o freio nao segurou a criacao")

    def test_teto_zero_desliga_o_freio(self):
        """Quem quiser encher a fila de proposito continua podendo."""
        chamou = []
        original = agenda.dias_de_estoque
        agenda.dias_de_estoque = lambda: chamou.append(1) or 999
        self.addCleanup(setattr, agenda, "dias_de_estoque", original)
        self.assertEqual(0, agenda.teto_de_estoque(
            {"horas": [6, 7, 8], "teto_de_estoque": 0}))
        fonte = Path(agenda.__file__).read_text(encoding="utf-8")
        self.assertIn("teto = teto_de_estoque(config)", fonte)
        self.assertIn("if teto:", fonte)


class EstoqueNovoContraReservaTests(unittest.TestCase):
    """O teto conta o estoque NOVO, nao o total (08/09/2026).

    Ele pediu "quero novos videos com o novo modelo de video" depois de as
    melhorias entrarem. O problema: os 38 dias prontos foram TODOS feitos com
    o Gemini Flash, sem molde, sem revisao e sem alavancas. Contando o total,
    um teto de 45 deixaria sete dias de folga e as melhorias apareceriam a
    conta-gotas.

    O estoque velho e RESERVA — serve para o canal nao ficar mudo se a criacao
    parar, mas nao e motivo para deixar de produzir o que esta melhor.
    """

    def test_a_marca_do_modelo_e_gravada_no_roteiro(self):
        from contos.roteiro import roteiro as R
        with TemporaryDirectory() as tmp:
            antigo, R.OUTPUTS = R.OUTPUTS, Path(tmp)
            try:
                caminho = R.salvar_serie(
                    {"titulo": "T", "partes": [{"n": 1}]},
                    [{"n": 1, "titulo": "A", "cta": "", "cenas": [
                        {"n": 1, "imagem": "x" * 30, "tempo": 4,
                         "narracao": "oi"}]}],
                    "historia_00099", modelo_llm="3.1 Pro")
                with open(caminho, encoding="utf-8-sig") as fh:
                    self.assertEqual(json.load(fh)["modelo_llm"], "3.1 Pro")
            finally:
                R.OUTPUTS = antigo

    def test_historia_sem_a_marca_nao_conta_como_nova(self):
        from contos.publicar import catalogo, serie
        from contos.roteiro import roteiro as R

        alvos = [
            (R, "listar", lambda: [{"historia_id": "h_velha"},
                                   {"historia_id": "h_nova",
                                    "modelo_llm": "3.1 Pro"}]),
            (serie, "publicados", lambda: []),
            (catalogo, "listar", lambda: [
                type("V", (), {"id": f"{h}:celular:p{i}", "fonte_id": h,
                               "perfil": "celular"})()
                for h in ("h_velha", "h_nova") for i in (1, 2)]),
        ]
        for alvo, nome, falso in alvos:
            self.addCleanup(setattr, alvo, nome, getattr(alvo, nome))
            setattr(alvo, nome, falso)
        self.assertEqual(agenda.dias_de_estoque(), 4)        # total
        self.assertEqual(agenda.dias_de_estoque_novo(), 2)   # so a marcada

    def test_o_teto_olha_o_estoque_NOVO(self):
        fonte = Path(agenda.__file__).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("teto = teto_de_estoque(config)"):]
        self.assertIn("dias_de_estoque_novo()", corpo[:400])


class FilaPrefereONovoTests(unittest.TestCase):
    """Termina o que comecou; depois, a mais NOVA (08/09/2026).

    Postar da mais antiga para a mais nova faria as melhorias aparecerem so
    depois de 38 dias de estoque velho. Mas abandonar serie ja iniciada e
    pior do que qualquer atraso: quem viu a parte 2 e nunca recebe a 3 sai.
    """

    @staticmethod
    def _postar():
        import importlib.util
        caminho = Path(agenda.RAIZ).parent / "ferramentas" / "postar.py"
        spec = importlib.util.spec_from_file_location("postar_fila", caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo

    def test_serie_comecada_vem_antes_da_mais_nova(self):
        postar = self._postar()
        from contos.publicar import catalogo, serie

        def _video(h, parte):
            return type("V", (), {"id": f"{h}:celular:p{parte:02d}",
                                  "fonte_id": h, "perfil": "celular",
                                  "parte": parte})()

        videos = [_video("historia_00003", i) for i in (1, 2, 3)]
        videos += [_video("historia_00009", i) for i in (1, 2)]
        self.addCleanup(setattr, catalogo, "listar", catalogo.listar)
        self.addCleanup(setattr, serie, "publicados", serie.publicados)
        catalogo.listar = lambda: videos
        serie.publicados = lambda: [
            {"video_id": "historia_00003:celular:p01", "url": "x"}]

        fila = postar.fila_de_historias()
        self.assertEqual(fila[0].fonte_id, "historia_00003",
                         "abandonou a serie ja iniciada")
        self.assertEqual(fila[0].parte, 2)
        # so depois de terminar a 3 e que a 9 (mais nova) entra
        self.assertEqual(fila[-1].fonte_id, "historia_00009")

    def test_entre_as_nao_comecadas_a_mais_nova_ganha(self):
        postar = self._postar()
        from contos.publicar import catalogo, serie

        def _video(h):
            return type("V", (), {"id": f"{h}:celular:p01", "fonte_id": h,
                                  "perfil": "celular", "parte": 1})()

        self.addCleanup(setattr, catalogo, "listar", catalogo.listar)
        self.addCleanup(setattr, serie, "publicados", serie.publicados)
        catalogo.listar = lambda: [_video("historia_00004"),
                                   _video("historia_00010"),
                                   _video("historia_00008")]
        serie.publicados = lambda: []
        fila = postar.fila_de_historias()
        self.assertEqual([v.fonte_id for v in fila],
                         ["historia_00010", "historia_00008", "historia_00004"])


if __name__ == "__main__":
    unittest.main()
