# -*- coding: utf-8 -*-
"""O vigia da main do Blue Lock, contra repositorios git DE VERDADE.

Cada teste monta tres repositorios numa pasta temporaria: o `origin` (nu,
o GitHub), o do `adrian` (onde ele commita e empurra) e o `espelho` (o nosso
E:\\BLUE-Lock-project). So o npm, o Telegram e a Mesa sao dublados.
"""
from __future__ import annotations

import subprocess
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest

from bluelock import vigia

PERMITIDOS = {"fetch", "rev-parse", "status", "merge-base", "merge", "log", "diff", "show"}
TESTE = ("test", "--", f"--testTimeout={vigia.TEMPO_POR_TESTE_MS}")


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=Adrian", "-c", "user.email=a@a", "-c",
                           "core.autocrlf=false", "-c", "init.defaultBranch=main", *args],
                          cwd=str(cwd), check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo, caminho, conteudo, mensagem):
    alvo = repo / caminho
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(conteudo, encoding="utf-8")
    _git(repo, "add", caminho)
    _git(repo, "commit", "-q", "-m", mensagem)


class Mundo:
    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.origin = tmp_path / "origin.git"
        self.adrian = tmp_path / "adrian"
        self.espelho = tmp_path / "espelho"
        _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(self.origin))
        _git(tmp_path, "clone", "-q", str(self.origin), str(self.adrian))
        _commit(self.adrian, ".gitignore", "node_modules/\n", "chore: ignore")
        _commit(self.adrian, "package.json", '{"version": "0.12.0"}\n', "feat: base")
        _git(self.adrian, "push", "-q", "origin", "main")
        _git(tmp_path, "clone", "-q", "-b", "main", str(self.origin), str(self.espelho))
        (self.espelho / "node_modules").mkdir()
        self.avisos, self.pedidos, self.npm_chamadas, self.git_chamadas = [], [], [], []
        self.pode = (True, "")
        self.agora = datetime(2026, 10, 19, 10, 0)
        self.npm_saida = (0, " Test Files  98 passed (98)\n      Tests  1378 passed (1378)\n   Duration  41.30s\n", "")

    def empurrar(self, caminho, conteudo, mensagem):
        _commit(self.adrian, caminho, conteudo, mensagem)
        _git(self.adrian, "push", "-q", "origin", "main")

    def head(self):
        return _git(self.espelho, "rev-parse", "HEAD")

    def vigia(self):
        real = vigia.git_real(self.espelho)

        def git(*args, prazo=60):
            self.git_chamadas.append(args)
            return real(*args, prazo=prazo)

        def npm(*args, prazo=60):
            self.npm_chamadas.append(args)
            return self.npm_saida if args[0] == "test" else (0, "added 70 packages", "")

        @contextmanager
        def trava():
            yield True

        def pedir(texto, alvo):
            self.pedidos.append((texto, alvo))
            return {"id": f"pedido-{len(self.pedidos):08d}"}

        return vigia.Vigia(espelho=self.espelho, git=git, npm=npm,
                           avisar=lambda texto: self.avisos.append(texto) or True, pedir=pedir,
                           pode_pesado=lambda agora: self.pode, relogio=lambda: self.agora,
                           estado=self.tmp / "estado" / "vigia.json", trava=trava, log=lambda _t: None)


@pytest.fixture
def mundo(tmp_path):
    return Mundo(tmp_path)


def test_caso_zero_main_parada_nao_faz_nada(mundo):
    antes = mundo.head()
    resultado = mundo.vigia().olhar()
    assert resultado["acao"] == "nada"
    assert mundo.head() == antes
    assert mundo.avisos == [] and mundo.pedidos == [] and mundo.npm_chamadas == []
    # e de novo: a segunda olhada tambem nao inventa noticia
    assert mundo.vigia().olhar()["acao"] == "nada"
    assert mundo.avisos == []


def test_main_andou_puxa_testa_avisa_e_pede(mundo):
    mundo.empurrar("src/field.ts", "export class Field {}\n", "feat: refine character graphics")
    mundo.empurrar("Docs/NOTA.md", "nota\n", "docs: nota")
    resultado = mundo.vigia().olhar()
    assert resultado["acao"] == "avisou" and resultado["commits"] == 2
    assert mundo.head() == _git(mundo.adrian, "rev-parse", "HEAD")
    assert mundo.npm_chamadas == [TESTE]                 # lock igual + node_modules: sem npm ci
    assert len(mundo.avisos) == 1
    aviso = mundo.avisos[0]
    assert "refine character graphics" in aviso and "1378 passaram" in aviso
    assert "src/field.ts" in aviso                          # ponto de contato em destaque
    assert len(mundo.pedidos) == 1
    texto, alvo = mundo.pedidos[0]
    assert alvo == vigia.ALVO_DO_PEDIDO
    assert texto.startswith("Blue Lock main mudou:") and "rever a integração" in texto
    assert "PROIBIDO" in texto
    estado = mundo.vigia().status()
    assert estado["ultimo"]["pedido"] == "pedido-00000001" and "pendente" not in estado
    # o registro das mudancas guardou os dois commits
    linhas = (mundo.tmp / "estado" / "mudancas.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 1 and '"commits"' in linhas[0]
    # e a olhada seguinte, com a main parada, nao repete nada
    assert mundo.vigia().olhar()["acao"] == "nada"
    assert len(mundo.avisos) == 1 and len(mundo.pedidos) == 1


def test_package_lock_mudou_roda_npm_ci_antes(mundo):
    mundo.empurrar("package-lock.json", "{}\n", "build: deps")
    mundo.vigia().olhar()
    assert mundo.npm_chamadas[0][0] == "ci" and mundo.npm_chamadas[1] == TESTE
    assert "npm ci" in mundo.avisos[0]


def test_teste_vermelho_vai_no_aviso(mundo):
    mundo.npm_saida = (1, "      Tests  2 failed | 1376 passed (1378)\n FAIL src/a.test.ts > quebra\n", "")
    mundo.empurrar("src/a.ts", "x\n", "fix: algo")
    mundo.vigia().olhar()
    assert "❌" in mundo.avisos[0] and "2 falharam" in mundo.avisos[0]
    assert mundo.vigia().status()["ultimo"]["testes"]["falhas"]


def test_teste_que_estoura_o_tempo_e_contado_a_parte(mundo):
    """19/10, medido: os 9 vermelhos com a maquina a 100% eram todos timeout."""
    mundo.npm_saida = (1, "      Tests  2 failed | 1376 passed (1378)\n"
                          "Error: Test timed out in 60000ms.\nError: Test timed out in 60000ms.\n", "")
    mundo.empurrar("src/b.ts", "x\n", "fix: b")
    mundo.vigia().olhar()
    assert "2 estouraram o tempo" in mundo.avisos[0]
    assert mundo.vigia().status()["ultimo"]["testes"]["por_tempo"] == 2


def test_pull_que_nao_e_fast_forward_avisa_e_para(mundo):
    mundo.empurrar("a.txt", "1\n", "feat: um")
    assert mundo.vigia().olhar()["acao"] == "avisou"
    antes = mundo.head()
    # o Adrian reescreve a main (amend + force-push)
    (mundo.adrian / "a.txt").write_text("2\n", encoding="utf-8")
    _git(mundo.adrian, "add", "a.txt")
    _git(mundo.adrian, "commit", "-q", "--amend", "-m", "feat: um (reescrito)")
    _git(mundo.adrian, "push", "-q", "--force", "origin", "main")
    avisos_antes, pedidos_antes = len(mundo.avisos), len(mundo.pedidos)
    resultado = mundo.vigia().olhar()
    assert resultado["acao"] == "divergiu"
    assert mundo.head() == antes                            # nao puxou
    assert len(mundo.avisos) == avisos_antes + 1 and "não seria fast-forward" in mundo.avisos[-1]
    assert len(mundo.pedidos) == pedidos_antes              # nada de pedido
    # a mesma divergencia na olhada seguinte nao vira outro aviso
    assert mundo.vigia().olhar()["acao"] == "divergiu"
    assert len(mundo.avisos) == avisos_antes + 1


def test_espelho_sujo_avisa_e_nao_puxa_nem_limpa(mundo):
    (mundo.espelho / "package.json").write_text('{"version": "mexido"}\n', encoding="utf-8")
    mundo.empurrar("b.txt", "b\n", "feat: b")
    antes = mundo.head()
    resultado = mundo.vigia().olhar()
    assert resultado["acao"] == "problema"
    assert mundo.head() == antes
    assert (mundo.espelho / "package.json").read_text(encoding="utf-8") == '{"version": "mexido"}\n'
    assert len(mundo.avisos) == 1 and "só leitura" in mundo.avisos[0]
    mundo.vigia().olhar()
    assert len(mundo.avisos) == 1                           # o mesmo problema, um aviso so


def test_fora_da_main_avisa_e_para(mundo):
    _git(mundo.espelho, "checkout", "-q", "-b", "outro")
    assert mundo.vigia().olhar()["acao"] == "problema"
    assert "saiu da `main`" in mundo.avisos[0]


def test_pesado_proibido_adia_e_conclui_depois(mundo):
    mundo.pode = (False, "League of Legends aberto")
    mundo.empurrar("c.txt", "c\n", "feat: c")
    resultado = mundo.vigia().olhar()
    assert resultado["acao"] == "adiado" and "League" in resultado["motivo"]
    assert mundo.head() == _git(mundo.adrian, "rev-parse", "HEAD")   # o pull e leve: foi feito
    assert mundo.avisos == [] and mundo.pedidos == [] and mundo.npm_chamadas == []
    # 30 min depois, o jogo fechou: testa, avisa e pede
    mundo.pode = (True, "")
    mundo.agora += timedelta(minutes=30)
    assert mundo.vigia().olhar()["acao"] == "avisou"
    assert mundo.npm_chamadas == [TESTE] and len(mundo.avisos) == 1 and len(mundo.pedidos) == 1


def test_adiado_alem_do_prazo_avisa_sem_testes(mundo):
    mundo.pode = (False, "janela das postagens (12:07, em 10 min)")
    mundo.empurrar("d.txt", "d\n", "feat: d")
    assert mundo.vigia().olhar()["acao"] == "adiado"
    mundo.agora += timedelta(hours=vigia.PRAZO_ADIADO_H, minutes=1)
    assert mundo.vigia().olhar()["acao"] == "avisou"
    assert mundo.npm_chamadas == []
    assert "não rodei" in mundo.avisos[0] and "janela das postagens" in mundo.avisos[0]


def test_dois_pushes_seguidos_adiados_viram_um_aviso_so(mundo):
    mundo.pode = (False, "League of Legends aberto")
    mundo.empurrar("e.txt", "1\n", "feat: e1")
    base = mundo.head()                                     # o espelho antes de puxar o e1
    mundo.vigia().olhar()
    mundo.empurrar("e.txt", "2\n", "feat: e2")
    mundo.agora += timedelta(minutes=30)
    mundo.vigia().olhar()
    mundo.pode = (True, "")
    mundo.agora += timedelta(minutes=30)
    resultado = mundo.vigia().olhar()
    assert resultado["acao"] == "avisou" and resultado["commits"] == 2
    assert len(mundo.avisos) == 1 and "feat: e1" in mundo.avisos[0] and "feat: e2" in mundo.avisos[0]
    assert mundo.vigia().status()["ultimo"]["de"] == base   # o intervalo cobre os dois pushes


def test_espelho_inexistente_avisa_uma_vez(tmp_path, mundo):
    mundo.espelho = tmp_path / "nao-existe"
    assert mundo.vigia().olhar()["acao"] == "problema"
    mundo.vigia().olhar()
    assert len(mundo.avisos) == 1 and "git clone" in mundo.avisos[0]


def test_sem_rede_avisa_so_depois_de_seis_falhas(mundo):
    _git(mundo.espelho, "remote", "set-url", "origin", str(mundo.tmp / "sumiu.git"))
    for vez in range(1, vigia.FALHAS_PARA_AVISAR + 2):
        resultado = mundo.vigia().olhar()
        assert resultado["acao"] == "fetch_falhou" and resultado["vezes"] == vez
        assert len(mundo.avisos) == (1 if vez >= vigia.FALHAS_PARA_AVISAR else 0)


def test_gravador_ocupando_o_espelho_pula_a_olhada(mundo):
    v = mundo.vigia()

    @contextmanager
    def ocupada():
        yield False
    v.trava = ocupada
    mundo.empurrar("f.txt", "f\n", "feat: f")
    antes = mundo.head()
    assert v.olhar()["acao"] == "ocupado"
    assert mundo.head() == antes and mundo.git_chamadas == []


def test_so_usa_comandos_de_leitura_e_o_avanco_ff(mundo):
    mundo.empurrar("g.txt", "g\n", "feat: g")
    mundo.vigia().olhar()
    usados = {chamada[0] for chamada in mundo.git_chamadas}
    assert usados <= PERMITIDOS, usados - PERMITIDOS
    merges = [chamada for chamada in mundo.git_chamadas if chamada[0] == "merge"]
    assert merges and all("--ff-only" in chamada for chamada in merges)


def test_falha_ao_abrir_pedido_vira_aviso_com_o_comando(mundo):
    v = mundo.vigia()

    def quebra(texto, alvo):
        raise OSError("trava do pedidos.json ocupada")
    v.pedir = quebra
    mundo.empurrar("h.txt", "h\n", "feat: h")
    assert v.olhar()["acao"] == "avisou"
    assert any("python -m coordenador pedir" in aviso for aviso in mundo.avisos)


def test_resumo_do_rodape_do_vitest():
    saida = ("\x1b[32m Test Files \x1b[39m 97 passed | 1 failed (98)\n"
             "      Tests  2 failed | 1370 passed | 6 skipped (1378)\n"
             "   Duration  1.52s (transform 3s)\n")
    ficha = vigia.resumo_de_testes(saida)
    assert ficha["arquivos"] == {"passou": 97, "falhou": 1, "pulou": 0, "total": 98}
    assert ficha["testes"] == {"passou": 1370, "falhou": 2, "pulou": 6, "total": 1378}
    assert ficha["duracao_s"] == 1.5
    assert vigia.resumo_de_testes("") == {}


def test_lancador_da_tarefa_usa_saida_e_nao_redireciona_para_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(vigia, "RAIZ", tmp_path)
    caminho = vigia.escrever_lancador(python=r"C:\Python314\python.exe")
    texto = caminho.read_bytes().decode("utf-8")
    assert "-m bluelock.vigia olhar --saida" in texto and ">>" not in texto
    assert "\r\r\n" not in texto


def test_instalar_cria_tarefa_de_30_min(monkeypatch, tmp_path):
    monkeypatch.setattr(vigia, "RAIZ", tmp_path)
    from builds import tarefas_windows
    monkeypatch.setattr(tarefas_windows, "endurecer", lambda nome: {"ok": True})
    monkeypatch.setattr(tarefas_windows, "limitar_execucao", lambda nome, limite: {"ok": True, "limite": limite})
    chamadas = []

    class Feito:
        returncode, stdout, stderr = 0, b"SUCCESS", b""

    ficha = vigia.instalar(rodar=lambda args, **kw: chamadas.append(args) or Feito())
    argumentos = chamadas[0]
    assert argumentos[:3] == ["schtasks", "/Create", "/TN"] and vigia.TAREFA in argumentos
    assert argumentos[argumentos.index("/MO") + 1] == "30"
    assert ficha["ok"] and ficha["limite"]["limite"] == vigia.LIMITE_DA_TAREFA
