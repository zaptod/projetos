# -*- coding: utf-8 -*-
"""O vigia de trabalho com dublês de delegar, Mesa, Grimório, git, Telegram e relógio."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from coordenador import cerebro, vigia_trabalho
from coordenador.supervisor import Supervisor
from coordenador.vigia_trabalho import VigiaTrabalho, extrair_duvida


class Relogio:
    def __init__(self):
        self.agora = datetime(2026, 10, 2, 9, 0)

    def __call__(self):
        return self.agora

    def andar(self, minutos):
        self.agora += timedelta(minutes=minutos)


class Recusa(Exception):
    pass


class Delegar:
    """O despachante, com o estado em memoria."""
    def __init__(self, pasta):
        self.pasta = pasta
        self.tarefas = {}
        self.coletas = {}         # id -> resumo do validador
        self.testes = {}          # id -> [resultados, em ordem]
        self.chamadas = []

    def novo(self, ident, fim, *, resposta="Conserta o X e testa.\n", arquivos=("remoto/x.py",),
             ok=True, motivos=(), sha="aaa", titulo="titulo do delegado", criado=None):
        self.tarefas[ident] = {"id": ident, "situacao": "terminou", "fim": fim,
                               "criado_em": criado or fim, "titulo": titulo,
                               "aplicado": None, "limpo": None, "testes": None}
        (self.pasta / ident).mkdir(parents=True, exist_ok=True)
        (self.pasta / ident / "resposta.md").write_text(resposta, encoding="utf-8")
        (self.pasta / ident / "testes.log").write_text("E" * 5000 + "FIM DO LOG", encoding="utf-8")
        self.coletas[ident] = {"ok": ok, "motivos": list(motivos), "sha": sha,
                               "arquivos": [{"caminho": a} for a in arquivos]}

    def listar(self):
        return [dict(t) for t in self.tarefas.values()]

    def pasta_da(self, ident):
        return self.pasta / ident

    def coletar(self, ident):
        self.chamadas.append(("coletar", ident))
        return dict(self.coletas[ident])

    def testar(self, ident, cmd):
        self.chamadas.append(("testar", ident, cmd))
        resultado = dict(self.testes[ident].pop(0), cmd=cmd,
                         diff_sha=self.coletas[ident]["sha"])
        self.tarefas[ident]["testes"] = resultado
        return resultado

    def aplicar(self, ident, sem_testes=False):
        self.chamadas.append(("aplicar", ident))
        arquivos = [a["caminho"] for a in self.coletas[ident]["arquivos"]]
        self.tarefas[ident]["aplicado"] = {"arquivos": arquivos}
        return {"arquivos": arquivos}

    def limpar(self, ident):
        self.chamadas.append(("limpar", ident))
        self.tarefas[ident]["limpo"] = {"em": "x"}

    def abandonar(self, ident):
        self.chamadas.append(("abandonar", ident))
        self.tarefas[ident]["situacao"] = "abandonado"

    def feitas(self, nome):
        return [c for c in self.chamadas if c[0] == nome]


class Mesa:
    def __init__(self):
        self.agora, self.fila, self.fechados = [], [], []

    def ler_estado(self):
        return {"agora": [dict(a) for a in self.agora], "fila": list(self.fila)}

    def agente_fim(self, ident, situacao="concluido", commits=(), relato_final=""):
        self.fechados.append((ident, situacao, list(commits)))
        self.agora = [a for a in self.agora if a["id"] != ident]


class Grimorio:
    PROJETOS = ("geral", "builds", "app-e-bot")

    def __init__(self):
        self.itens, self.criados = {}, []

    def carregar(self):
        return dict(self.itens)

    def adicionar_e_commitar(self, projeto, titulo, pergunta, opcoes, **kw):
        ident = f"no{len(self.criados) + 1}"
        self.criados.append({"projeto": projeto, "titulo": titulo, "pergunta": pergunta,
                             "opcoes": opcoes, **kw})
        self.itens[ident] = {"id": ident, "titulo": titulo, "projeto": projeto,
                             "situacao": "pendente"}
        return {"id": ident}, "abc1234"


@pytest.fixture
def mundo(tmp_path):
    relogio = Relogio()
    mundo = SimpleNamespace(relogio=relogio, delegar=Delegar(tmp_path / "delegados"),
                            mesa=Mesa(), grimorio=Grimorio(), avisos=[], eventos=[],
                            commits=[], corrigidos=[], reinicios=[], seguro=[True, ""],
                            proibido="", fichas=[], sujos=[], em_uso=set())

    def classificar(duvida, contexto):
        if isinstance(mundo.fichas, Exception):
            raise mundo.fichas
        return mundo.fichas.pop(0) if mundo.fichas else {"precisa_decisao": False}

    def commitar(arquivos, mensagem):
        mundo.commits.append((list(arquivos), mensagem))
        return f"c{len(mundo.commits)}"

    mundo.vigia = VigiaTrabalho(
        delegar=mundo.delegar, orquestrador=mundo.mesa, decisoes=mundo.grimorio,
        commitar=commitar, sujos=lambda arquivos: list(mundo.sujos),
        corrigir=lambda ident, texto: mundo.corrigidos.append((ident, texto)),
        pode_corrigir=lambda delegados, agora: "",
        avisar=mundo.avisos.append, evento=lambda t, x: mundo.eventos.append((t, x)),
        relogio=relogio, seguro=lambda: tuple(mundo.seguro),
        pedir_reinicio=mundo.reinicios.append, proibido=lambda: mundo.proibido,
        classificar=classificar, propostas=lambda: 0,
        servicos=lambda: {"app": {"modulos": ["remoto"]}, "bot": {"modulos": ["remoto"]},
                          "vila": {"modulos": ["painel"]}},
        memoria=tmp_path / "memoria.json", em_uso=lambda: set(mundo.em_uso))
    # o vigia nasce agora; as entregas dos testes terminam depois
    mundo.vigia.passo()
    mundo.avisos.clear()
    mundo.depois = (relogio() + timedelta(minutes=1)).isoformat(timespec="seconds")
    relogio.andar(2)          # as entregas terminaram antes de o vigia olhar
    return mundo


def verde():
    return {"ok": True, "codigo": 0, "resumo": "10 passed"}


def vermelho():
    return {"ok": False, "codigo": 1, "resumo": "1 failed"}


def test_terminou_valido_verde_e_seguro_aplica_commita_por_caminho_e_limpa(mundo):
    d = mundo.delegar
    d.novo("conserto-x", mundo.depois, resposta="## Conserta o X sem quebrar o Y\nmais texto",
           arquivos=("remoto/x.py", "remoto/test_x.py"))
    d.testes["conserto-x"] = [verde()]
    t = mundo.vigia.passo()
    assert d.feitas("testar") == [("testar", "conserto-x", "python -m pytest remoto -q")]
    assert d.feitas("aplicar") and d.feitas("limpar")
    arquivos, mensagem = mundo.commits[0]
    assert arquivos == ["remoto/x.py", "remoto/test_x.py"]
    # 05/10: o assunto e o TITULO da tarefa (nao a fala do agente) com o que
    # o vigia MEDIU; o corpo diz quem fez e o comando que rodou
    assert mensagem.startswith("titulo do delegado — 10 passed\n\n")
    assert ("Feito pelo Codex (conserto-x), validado pelo vigia: "
            "`python -m pytest remoto -q` deu 10 passed.") in mensagem
    assert "## Conserta o X sem quebrar o Y" in mensagem
    assert "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" in mensagem
    assert sorted(mundo.reinicios) == ["app", "bot"]          # mudou codigo de servico
    assert t["aplicados"][0]["commit"] == "c1"
    # nao reaplica na volta seguinte
    mundo.vigia.passo()
    assert len(d.feitas("aplicar")) == 1


@pytest.mark.parametrize("arquivo", ["remoto/app/decisoes.js", "remoto\\api_http.py"])
def test_mudanca_na_casca_ou_csp_liga_a_prova_de_tela(mundo, arquivo):
    d = mundo.delegar
    d.novo("tela-" + arquivo.rsplit(".", 1)[0].replace("/", "-").replace("\\", "-"),
           mundo.depois, arquivos=(arquivo,))
    ident = next(iter(d.tarefas))
    d.testes[ident] = [verde()]
    mundo.vigia.passo()
    assert d.feitas("testar") == [
        ("testar", ident, "set NF_TESTE_NAVEGADOR=1&& python -m pytest remoto -q")]


def test_testes_vermelhos_corrige_uma_vez_e_na_segunda_avisa(mundo):
    d = mundo.delegar
    d.novo("teimoso", mundo.depois)
    d.testes["teimoso"] = [vermelho(), vermelho()]
    mundo.vigia.passo()
    assert len(mundo.corrigidos) == 1 and not d.feitas("aplicar")
    texto = mundo.corrigidos[0][1]
    assert texto.count("E") >= 3900 and "FIM DO LOG" in texto     # os ultimos 4 mil
    # o Codex corrige: termina de novo, com outro diff, e falha de novo
    mundo.relogio.andar(5)
    d.tarefas["teimoso"]["fim"] = mundo.relogio().isoformat(timespec="seconds")
    d.coletas["teimoso"]["sha"] = "bbb"
    mundo.vigia.passo()
    assert len(mundo.corrigidos) == 1 and not d.feitas("aplicar")
    assert any("teimoso travou" in a and "precisa de olho" in a for a in mundo.avisos)
    # e nao mexe mais
    n = len(d.chamadas)
    mundo.vigia.passo()
    assert len(d.chamadas) == n


def test_correcao_que_nao_comeca_em_10_min_avisa(mundo):
    d = mundo.delegar
    d.novo("parado", mundo.depois)
    d.testes["parado"] = [vermelho()]
    mundo.vigia.passo()
    mundo.relogio.andar(5)
    mundo.vigia.passo()
    assert not any("não começou" in a for a in mundo.avisos)
    mundo.relogio.andar(6)
    mundo.vigia.passo()
    assert any("não começou" in a for a in mundo.avisos)


def test_validador_recusou_avisa_e_nao_aplica(mundo):
    d = mundo.delegar
    d.novo("fora", mundo.depois, ok=False, motivos=["diff ilegível: palco/x.gd"])
    mundo.vigia.passo()
    assert not d.feitas("testar") and not d.feitas("aplicar")
    assert any("fora travou" in a and "palco/x.gd" in a and "precisa de olho" in a
               for a in mundo.avisos)
    assert mundo.vigia.ultimo["olho"][0]["id"] == "fora"


def test_olho_igual_so_avisa_uma_vez(mundo):
    """maquina.md #1 (11/10): 6.489 `trabalho_olho` num dia, o mesmo texto ao
    Telegram a cada passo. A mesma entrega com o mesmo motivo avisa 1x."""
    d = mundo.delegar
    d.novo("preso", mundo.depois, ok=False, motivos=["diff ilegível"])
    mundo.vigia.passo()
    primeiro = len(mundo.avisos)
    mem = mundo.vigia._ler_memoria()
    motivo = mem["olho"]["preso"]["motivo"]
    mundo.vigia._olho(mem, "preso", motivo)
    assert len(mundo.avisos) == primeiro
    mundo.vigia._olho(mem, "preso", "motivo novo")
    assert len(mundo.avisos) == primeiro + 1
    mundo.relogio.andar(1)
    mundo.vigia.passo()
    assert not [a for a in mundo.avisos[primeiro + 1:] if "preso travou" in a]


def test_janela_da_grade_espera_e_depois_aplica(mundo):
    d = mundo.delegar
    d.novo("na-janela", mundo.depois)
    d.testes["na-janela"] = [verde()]
    mundo.seguro[:] = [False, "janela da grade"]
    t = mundo.vigia.passo()
    assert not d.feitas("aplicar") and t["esperando"] == {"na-janela": "janela da grade"}
    mundo.seguro[:] = [True, ""]
    t = mundo.vigia.passo()
    assert d.feitas("aplicar") and t["esperando"] == {}


def test_janela_da_postagem_nao_aplica_nem_reinicia(mundo):
    d = mundo.delegar
    d.novo("postagem", mundo.depois)
    d.testes["postagem"] = [verde()]
    mundo.relogio.agora = datetime(2026, 10, 7, 20, 44)
    t = mundo.vigia.passo()
    assert not d.feitas("aplicar") and mundo.reinicios == []
    assert "janela da postagem" in t["esperando"]["postagem"]
    mundo.relogio.agora = datetime(2026, 10, 7, 20, 56)
    mundo.vigia.passo()
    assert d.feitas("aplicar") and sorted(mundo.reinicios) == ["app", "bot"]


def test_aplicar_recusado_pela_janela_do_despachante_espera(mundo):
    d = mundo.delegar
    d.novo("x25", mundo.depois)
    d.testes["x25"] = [verde()]

    def recusa(ident, sem_testes=False):
        raise Recusa("aplicar só fora de :25–:55, a janela da postagem (agora 09:30)")
    d.aplicar = recusa
    t = mundo.vigia.passo()
    assert "x25" in t["esperando"] and not mundo.commits
    assert not any("precisa de olho" in a for a in mundo.avisos)


def test_arvore_principal_suja_no_arquivo_avisa_e_nao_aplica(mundo):
    d = mundo.delegar
    d.novo("sujo", mundo.depois)
    d.testes["sujo"] = [verde()]
    mundo.sujos[:] = ["remoto/x.py"]
    mundo.vigia.passo()
    assert not d.feitas("aplicar") and not mundo.vigia.ultimo["olho"]   # espera, nao abandona (03/10)


def test_com_o_aplicar_desligado_a_entrega_pronta_espera_o_orquestrador(mundo, tmp_path):
    (tmp_path / "config.json").write_text('{"vigia_aplica": false}', encoding="utf-8")
    d = mundo.delegar
    d.novo("pronta", mundo.depois)
    d.testes["pronta"] = [verde()]
    t = mundo.vigia.passo()
    assert d.feitas("testar") and not d.feitas("aplicar") and not mundo.commits
    assert "pronta para aplicar" in t["esperando"]["pronta"]


def test_so_documentacao_aplica_sem_testes(mundo):
    d = mundo.delegar
    d.novo("doc", mundo.depois, arquivos=("docs/sessoes/x.md",))
    mundo.vigia.passo()
    assert not d.feitas("testar") and d.feitas("aplicar") and mundo.reinicios == []


def test_entrega_mais_velha_que_o_vigia_so_aparece(mundo):
    d = mundo.delegar
    d.novo("antiga", "2026-10-01T23:00:00")
    t = mundo.vigia.passo()
    assert d.chamadas == [] and t["antigos"] == ["antiga"]


def test_a_mesa_fecha_o_item_cujos_delegados_foram_aplicados(mundo):
    d = mundo.delegar
    d.novo("vigia-e-cerebro", mundo.depois)
    d.novo("armas-16f", mundo.depois)
    d.testes["vigia-e-cerebro"] = [verde()]
    d.testes["armas-16f"] = [vermelho()]
    desde = mundo.relogio().isoformat(timespec="seconds")
    mundo.mesa.agora = [
        {"id": "c89304c3", "parte": "geral", "desde": desde,
         "titulo": "CODEX x2: cérebro + vigia de trabalho do coordenador; armas 16F"},
        {"id": "cb99ada7", "parte": "builds", "desde": desde,
         "titulo": "16F armas como peça (Claude assume do Codex)"}]
    mundo.vigia.passo()
    assert mundo.mesa.fechados == []              # armas-16f ainda nao foi aplicada
    d.tarefas["armas-16f"]["aplicado"] = {"em": "x"}       # aplicada a mao
    mundo.vigia.passo()
    assert mundo.mesa.fechados == [("c89304c3", "concluido", ["c1"])]
    # o item do Claude (sem CODEX maiusculo) fica
    assert [a["id"] for a in mundo.mesa.agora] == ["cb99ada7"]


def test_delegado_antigo_de_palavra_comum_nao_conta_como_citado():
    item = {"titulo": "CODEX: vigia do coordenador", "desde": "2026-10-02T00:19:00"}
    velho = {"id": "coordenador", "criado_em": "2026-10-01T23:19:33"}
    novo = {"id": "coordenador-app", "criado_em": "2026-10-02T00:20:00"}
    assert vigia_trabalho.delegados_citados(item, [velho, novo]) == []


def test_item_parado_45_min_avisa_uma_vez(mundo):
    desde = mundo.relogio().isoformat(timespec="seconds")
    mundo.mesa.agora = [{"id": "a1", "parte": "builds", "titulo": "Som real", "desde": desde,
                         "relato_em": None}]
    mundo.relogio.andar(44)
    mundo.vigia.passo()
    assert not any("parada" in a for a in mundo.avisos)
    mundo.relogio.andar(2)
    mundo.vigia.passo()
    mundo.relogio.andar(10)
    mundo.vigia.passo()
    parados = [a for a in mundo.avisos if a.startswith("⏸")]
    assert len(parados) == 1 and "46 min" in parados[0]
    assert any(t == "trabalho_parada" for t, _ in mundo.eventos)
    # um relato novo, e 45 min de novo sem nada: avisa outra vez
    mundo.mesa.agora[0]["relato_em"] = mundo.relogio().isoformat(timespec="seconds")
    mundo.relogio.andar(50)
    mundo.vigia.passo()
    assert len([a for a in mundo.avisos if a.startswith("⏸")]) == 2


RESPOSTA_COM_DUVIDA = """Feito o filtro de vídeos.

## O que mudou
- remoto/x.py

## O que ficou duvidoso
- Não sei se o vídeo reprovado deve sumir da lista do app ou aparecer riscado.
"""


def ficha_de_produto(titulo="Vídeo reprovado: some ou fica riscado?"):
    return {"precisa_decisao": True, "titulo": titulo, "pergunta": "Como o app mostra?",
            "opcoes": [{"id": "some", "rotulo": "Some (recomendado)", "descricao": ""},
                       {"id": "riscado", "rotulo": "Fica riscado", "descricao": ""}],
            "contexto": "O filtro novo do app."}


def test_duvida_de_produto_vira_no_no_projeto_da_parte(mundo):
    d = mundo.delegar
    d.novo("filtro-x", mundo.depois, resposta=RESPOSTA_COM_DUVIDA)
    d.testes["filtro-x"] = [verde()]
    mundo.mesa.agora = [{"id": "m1", "parte": "app-e-bot", "titulo": "CODEX: filtro x",
                         "desde": mundo.relogio().isoformat(timespec="seconds")}]
    mundo.fichas = [ficha_de_produto()]
    mundo.vigia.passo()
    no = mundo.grimorio.criados[0]
    assert no["projeto"] == "app-e-bot" and len(no["opcoes"]) == 2
    assert "filtro-x" in no["contexto"]


def test_detalhe_tecnico_nao_vira_no(mundo):
    d = mundo.delegar
    d.novo("tecnico", mundo.depois, resposta=RESPOSTA_COM_DUVIDA)
    d.testes["tecnico"] = [verde()]
    mundo.fichas = [{"precisa_decisao": False}]
    mundo.vigia.passo()
    assert mundo.grimorio.criados == []


def test_sem_cerebro_so_avisa(mundo):
    d = mundo.delegar
    d.novo("sem-cerebro", mundo.depois, resposta=RESPOSTA_COM_DUVIDA)
    d.testes["sem-cerebro"] = [verde()]
    mundo.fichas = cerebro.CerebroIndisponivel("o Codex está em 90% da janela")
    mundo.vigia.passo()
    assert mundo.grimorio.criados == []
    assert any("sem cérebro" in a and "riscado" in a for a in mundo.avisos)


def test_no_maximo_5_nos_por_dia_e_nenhum_repetido(mundo):
    d = mundo.delegar
    for i in range(7):
        d.novo(f"d{i}", mundo.depois, resposta=RESPOSTA_COM_DUVIDA)
        d.testes[f"d{i}"] = [verde()]
    # d0 e d1 com o mesmo titulo (o segundo nao entra); depois 5 distintos
    mundo.fichas = [ficha_de_produto("Repetida"), ficha_de_produto("repetida!")] + [
        ficha_de_produto(f"Pergunta {i}") for i in range(5)]
    mundo.vigia.passo()
    titulos = [c["titulo"] for c in mundo.grimorio.criados]
    assert len(titulos) == 5 and titulos.count("Repetida") == 1
    assert any("já são 5 nós hoje" in a for a in mundo.avisos)
    # um titulo que ja existe no Grimorio tambem nao entra (no dia seguinte)
    mundo.relogio.andar(24 * 60)
    d.novo("d9", mundo.relogio().isoformat(timespec="seconds"), resposta=RESPOSTA_COM_DUVIDA)
    d.testes["d9"] = [verde()]
    mundo.fichas = [ficha_de_produto("Pergunta 0")]
    mundo.vigia.passo()
    assert len(mundo.grimorio.criados) == 5


def test_com_proibido_so_observa(mundo):
    d = mundo.delegar
    d.novo("quieto", mundo.depois, resposta=RESPOSTA_COM_DUVIDA)
    d.testes["quieto"] = [verde()]
    d.tarefas["quieto"]["aplicado"] = None
    mundo.mesa.agora = [{"id": "m1", "parte": "geral", "titulo": "CODEX: quieto",
                         "desde": mundo.relogio().isoformat(timespec="seconds")}]
    mundo.fichas = [ficha_de_produto()]
    mundo.proibido = "Claude proibido pelo Adrian desde 09:00"
    t = mundo.vigia.passo()
    assert d.chamadas == [] and mundo.commits == [] and mundo.corrigidos == []
    assert mundo.grimorio.criados == [] and mundo.mesa.fechados == []
    assert t["proibido"].startswith("Claude proibido")


def test_o_resumo_so_sai_com_novidade_e_no_maximo_a_cada_60_min(mundo):
    d = mundo.delegar
    mundo.vigia.passo()
    assert not any("Andamento" in a for a in mundo.avisos)   # nada novo: nada sai
    d.novo("r1", mundo.depois)
    d.testes["r1"] = [verde()]
    mundo.vigia.passo()
    resumos = [a for a in mundo.avisos if a.startswith("🛰 Andamento")]
    assert len(resumos) == 1 and "r1 aplicada: c1" in resumos[0]
    assert any(t == "trabalho_resumo" for t, _ in mundo.eventos)
    # novidade 10 min depois: espera fechar a hora
    mundo.relogio.andar(10)
    d.novo("r2", mundo.relogio().isoformat(timespec="seconds"))
    d.testes["r2"] = [verde()]
    mundo.vigia.passo()
    assert len([a for a in mundo.avisos if a.startswith("🛰 Andamento")]) == 1
    mundo.relogio.andar(51)
    t = mundo.vigia.passo()
    resumos = [a for a in mundo.avisos if a.startswith("🛰 Andamento")]
    assert len(resumos) == 2 and "r2 aplicada" in resumos[1]
    assert t["resumo_em"] == mundo.relogio().isoformat(timespec="seconds")
    # e sem novidade nao sai mais
    mundo.relogio.andar(70)
    mundo.vigia.passo()
    assert len([a for a in mundo.avisos if a.startswith("🛰 Andamento")]) == 2


def test_o_resumo_vai_para_o_estado_do_coordenador():
    relogio, gravado = Relogio(), []

    class VigiaFalso:
        def __init__(self):
            self.passos = 0

        def passo(self):
            self.passos += 1
            return {"em": relogio().isoformat(), "aplicados": []}
    falso = VigiaFalso()
    s = Supervisor(servicos={"app": {"nome": "app", "assinatura": "app", "comando": ["app"],
                                     "cwd": ".", "log": "x.log", "janela": "oculta",
                                     "modulos": [], "reinicio_seguro": False}},
                   relogio=relogio, processos=lambda: [{"pid": 1, "comando": "app"}],
                   porta=lambda: True, git=lambda *_: False, avisar=lambda *_: None,
                   gravar=gravado.append, log=lambda _: None, vigia_trabalho=falso,
                   em_fundo=lambda nome, f: f())
    s.pulso()
    s.pulso()
    assert falso.passos == 1                         # a cada ~60 s, nao a cada pulso
    relogio.andar(1)
    s.pulso()
    assert falso.passos == 2 and gravado[-1]["trabalho"]["em"] == relogio().isoformat()


def test_o_supervisor_chama_o_cerebro_e_reinicia_o_pedido_no_momento_seguro():
    relogio, chamadas, parou, iniciou = Relogio(), [], [], []
    vivos = [{"pid": 1, "comando": "app"}, {"pid": 4, "comando": "System"}]

    def parar(pid):                    # o taskkill de mentira mata de verdade
        parou.append(pid)
        vivos[:] = [p for p in vivos if p["pid"] != pid]

    def iniciar(_ficha):
        iniciou.append(2)
        vivos.append({"pid": 2, "comando": "app"})
        return 2
    s = Supervisor(servicos={"app": {"nome": "app", "assinatura": "app", "comando": ["app"],
                                     "cwd": ".", "log": "x.log", "janela": "oculta",
                                     "modulos": [], "reinicio_seguro": True}},
                   relogio=relogio, processos=lambda: list(vivos),
                   porta=lambda: True, git=lambda *_: False, avisar=lambda *_: None,
                   gravar=lambda _: None, log=lambda _: None, parar=parar,
                   iniciar=iniciar, janela=lambda _agora: (False, ""), dormir=lambda _s: None,
                   carregar=lambda: {}, pendentes=lambda: [],
                   comandos=lambda: [], aplicar=lambda *a, **k: None,
                   cerebro=lambda **kw: chamadas.append(sorted(kw)), em_fundo=lambda n, f: f())
    s.pulso()
    assert chamadas == [["aplicar", "avisar", "comandos"]]
    s.pedir_reinicio("app")
    s.pulso()
    assert parou == [1] and iniciou == [2] and "app" not in s.reinicio_pedido


def test_primeira_linha_sem_markdown_e_sem_link():
    resposta = "Construído: [api_http.py](/E:/projetos-wt/codex-x/remoto/api_http.py:186) e testes"
    assert vigia_trabalho.primeira_linha(resposta, "r") == "Construído: api_http.py e testes"
    assert vigia_trabalho.primeira_linha("## O que mudou\n- x", "o título") == "o título"
    assert vigia_trabalho.primeira_linha("", "") == "entrega do Codex"


def test_extrair_duvida():
    assert extrair_duvida(RESPOSTA_COM_DUVIDA).startswith("- Não sei se o vídeo")
    assert extrair_duvida("tudo certo\n\nDúvidas: nenhuma") == ""
    assert extrair_duvida("**O que ficou de fora ou em dúvida:** usar A ou B?") == "usar A ou B?"
    assert extrair_duvida("Feito.\n\n## Testes\n10 passed") == ""
    texto = "## Precisa de decisão\nCobrar por vídeo?\n\n## Testes\nok"
    assert extrair_duvida(texto) == "Cobrar por vídeo?"



def test_entrega_travada_contrata_o_integrador(mundo):
    """03/10/2026: "VOCE AINDA BARRA O CODEX DE RESOLVER O PROBLEMA"."""
    d = mundo.delegar
    criados, rodados = [], []
    d.criar = lambda ident, pedido, permitidos, **kw: criados.append((ident, kw)) or {"id": ident}
    d.no_fundo = lambda args, ident: rodados.append(ident)
    d.ler_estado = lambda ident: {"permitidos": ["remoto/**"]}

    def aplicar(ident, sem_testes=False):
        raise Exception("conflito de merge em: remoto/x.py")
    d.aplicar = aplicar
    d.novo("trava", mundo.depois)
    d.testes["trava"] = [{"ok": True, "codigo": 0, "resumo": "1 passed"}]
    mundo.vigia.passo()
    assert criados and criados[0][0] == "integrar-trava"
    assert criados[0][1]["cargo"] == "integrador"
    assert rodados == ["integrar-trava"]
    assert (d.pasta / "trava" / "integrar.md").is_file()
    assert any("integrador integrar-trava já está resolvendo" in a for a in mundo.avisos)
    mundo.vigia.passo()                          # nao contrata de novo
    assert len(criados) == 1
    assert criados[0][1]["ia"] == "codex"        # 08/10/2026: integrador e sempre Codex


@pytest.mark.parametrize("uso", [
    {"situacao": "ok", "passou_teto": True, "motivo_teto": "a sessão está em 60% (teto 50%)"},
    {"situacao": "velha", "passou_teto": True, "motivo_teto": "a semana está em 100% (teto 95%)"},
])
def test_integrador_acima_do_teto_vai_ao_codex(mundo, uso):
    """05/10/2026: integrar-pedido-66e4ba54 nasceu Claude com a semana no limite
    e morreu em "falhou" (rate_limit_event "rejected")."""
    d = mundo.delegar
    criados = []
    d.criar = lambda ident, pedido, permitidos, **kw: criados.append((ident, kw)) or {"id": ident}
    d.no_fundo = lambda args, ident: None
    d.ler_estado = lambda ident: {"permitidos": ["remoto/**"]}
    mundo.mesa.ler_uso = lambda: dict(uso)

    def aplicar(ident, sem_testes=False):
        raise Exception("conflito de merge em: remoto/x.py")
    d.aplicar = aplicar
    d.novo("trava", mundo.depois)
    d.testes["trava"] = [{"ok": True, "codigo": 0, "resumo": "1 passed"}]
    mundo.vigia.passo()
    assert [(c[0], c[1]["ia"]) for c in criados] == [("integrar-trava", "codex")]


def test_arvore_suja_espera_em_vez_de_abandonar(mundo):
    d = mundo.delegar
    mundo.sujos = ["remoto/x.py"]
    d.novo("suja", mundo.depois)
    d.testes["suja"] = [{"ok": True, "codigo": 0, "resumo": "1 passed"}]
    mundo.vigia.passo()
    assert not d.feitas("aplicar")
    assert not mundo.vigia.ultimo["olho"]
    assert "suja" in mundo.vigia.ultimo.get("esperando", {}) or any(
        e.get("id") == "suja" for e in mundo.vigia.ultimo.get("esperando", []))


# ---- 04/10/2026: o Andamento repetia o mesmo item parado da fila ----------
FILA_PARADA = {"id": "b0d22ef8", "parte": "builds", "prioridade": 1,
               "item": "Som real nas 15 builds de estoque ainda com som sintetizado"}


def _andamentos(mundo):
    return [a for a in mundo.avisos if a.startswith("🛰 Andamento")]


def test_contagem_do_grimorio_oscilando_nao_vira_andamento(mundo):
    """0 -> 1 -> 0 -> 1 decisoes (e leitura que falha) nao e novidade: so as
    linhas fixas e o item parado da fila saiam, hora apos hora."""
    mundo.mesa.fila = [FILA_PARADA]
    carregar = mundo.grimorio.carregar
    for i in range(6):
        if i % 3 == 2:
            mundo.grimorio.carregar = lambda: (_ for _ in ()).throw(OSError("lendo"))
        else:
            mundo.grimorio.carregar = carregar
            mundo.grimorio.itens = ({"n1": {"id": "n1", "projeto": "geral",
                                            "situacao": "pendente"}} if i % 2 else {})
        mundo.relogio.andar(61)
        mundo.vigia.passo()
    mundo.grimorio.carregar = carregar
    # o no n1 chegou UMA vez (i=1); ir e voltar de pendente nao e no novo
    resumos = _andamentos(mundo)
    assert len(resumos) == 1 and "1 decisão(ões) nova(s)" in resumos[0]


def test_decisao_nova_esperando_ele_sai_com_todas_as_letras(mundo):
    mundo.vigia.passo()
    mundo.grimorio.itens = {"n1": {"id": "n1", "titulo": "T", "projeto": "geral",
                                   "situacao": "pendente"}}
    mundo.relogio.andar(61)
    mundo.vigia.passo()
    resumos = _andamentos(mundo)
    assert len(resumos) == 1
    assert "📥 1 decisão(ões) nova(s) no Grimório esperando você" in resumos[0]
    # ele respondeu (a contagem caiu): nao e aviso
    mundo.grimorio.itens = {}
    mundo.relogio.andar(61)
    mundo.vigia.passo()
    assert len(_andamentos(mundo)) == 1


def test_o_item_parado_da_fila_aparece_uma_vez_e_depois_so_se_mudar(mundo):
    d = mundo.delegar
    mundo.mesa.fila = [FILA_PARADA]
    for n, ident in enumerate(("f1", "f2", "f3")):
        mundo.relogio.andar(61)
        d.novo(ident, mundo.relogio().isoformat(timespec="seconds"))
        d.testes[ident] = [verde()]
        mundo.vigia.passo()
    resumos = _andamentos(mundo)
    assert len(resumos) == 3                     # cada um com novidade de verdade
    assert ["Som real" in r for r in resumos] == [True, False, False]
    # a fila mudou: aparece de novo
    mundo.mesa.fila = [{"id": "n", "parte": "geral", "item": "outra coisa"}, FILA_PARADA]
    mundo.relogio.andar(61)
    d.novo("f4", mundo.relogio().isoformat(timespec="seconds"))
    d.testes["f4"] = [verde()]
    mundo.vigia.passo()
    assert "Fila: 2 item(ns); primeiro: [geral] outra coisa" in _andamentos(mundo)[-1]


def test_novidade_sem_linha_no_texto_nao_manda_andamento(mundo):
    mem = mundo.vigia._ler_memoria()
    mem["novidades"].append({"em": "2026-10-02T09:00:00", "tipo": "desconhecida",
                             "texto": "x"})
    mundo.vigia._gravar_memoria(mem)
    mundo.relogio.andar(61)
    mundo.vigia.passo()
    assert _andamentos(mundo) == []


# ---- varredura 05/10/2026 (itens 7, 12, 21c e 23) --------------------------
def test_conferente_so_registra_o_veredito_e_nunca_e_entrega(mundo):
    """5 conferentes caiam em `olho` com "o Codex não mudou nada", e os
    rascunhos deles (.conf_*.md, resposta.md) iam parar em commits."""
    d = mundo.delegar
    d.novo("conf-x", mundo.depois, resposta="Conferi a tela.\n\nREPROVADO: o botão some.",
           ok=False, motivos=["o Codex não mudou nada"])
    d.tarefas["conf-x"]["cargo"] = "conferente"
    t = mundo.vigia.passo()
    assert d.chamadas == [] and mundo.commits == []          # nem coletar
    assert not t["olho"] and not t["esperando"]
    assert t["conferencias"][0]["id"] == "conf-x"
    assert t["conferencias"][0]["veredito"] == "REPROVADO"
    mundo.relogio.andar(61)
    mundo.vigia.passo()                                      # registra uma vez so
    ditos = [a for a in mundo.avisos if "conferente conf-x: REPROVADO" in a]
    assert len(ditos) == 1 and ditos[0].startswith("🛰 Andamento")
    assert "🔎 conferente conf-x: REPROVADO" in ditos[0]


def test_sem_mudanca_e_nada_a_aplicar_nao_olho(mundo):
    d = mundo.delegar
    criados = []
    d.criar = lambda *a, **kw: criados.append(a)
    d.no_fundo = lambda *a: None
    d.novo("vazio", mundo.depois, ok=False, motivos=["o Codex não mudou nada"])
    t = mundo.vigia.passo()
    assert not t["olho"] and criados == [] and not mundo.commits
    assert not any("precisa de olho" in a for a in mundo.avisos)
    n = len(d.chamadas)
    mundo.vigia.passo()                                      # nao coleta de novo
    assert len(d.chamadas) == n


def test_commit_usa_o_titulo_e_so_sem_titulo_a_fala(mundo):
    assert vigia_trabalho.titulo_do_commit(
        {"titulo": "# Conserto do **cp1252** no despachante"}, "Implementado.") \
        == "Conserto do cp1252 no despachante"
    assert vigia_trabalho.titulo_do_commit(
        {"titulo": "", "id": "x1"}, "Troquei o print do _log por um seguro") \
        == "Troquei o print do _log por um seguro"
    d = mundo.delegar
    d.novo("fala", mundo.depois, resposta="Implementado.\n", titulo="Integrar pedido-66e4ba54")
    d.tarefas["fala"]["ia"] = "claude"
    d.testes["fala"] = [verde()]
    mundo.vigia.passo()
    # integrador sem o estado original legivel: o alvo e os arquivos que mudaram
    assert mundo.commits[0][1].startswith("pedido-66e4ba54: x.py — 10 passed\n")
    assert "Feito pelo Claude (fala), validado pelo vigia" in mundo.commits[0][1]


# ---- conferente 05/10: o titulo dos pedidos e a pergunta, nao o que mudou --
GRIMORIO_LONGO = ("O Adrian respondeu no Grimório (historias/imagens-divisao): «Imagens das "
                  "histórias: como dividir entre Gemini, ChatGPT e PicassoIA quando uma "
                  "delas cai no meio da rodada da madrugada»")


PEDIDO_FC = {"id": "pedido-fc098cab", "cargo": "orquestrador", "titulo":
              "O Adrian respondeu no Grimório (historias/reolhar-depois-do-conserto): "
              "«IA olha de novo a parte consertada?»"}
# a fala final real do pedido-fc098cab: narra a espera, nao o que mudou
FALA_FC = ("O trabalhador `consertada-primeiro` está rodando. Aguardo ele terminar para "
           "mandar a entrega ao `conferente`.\n")
ARQUIVOS_FC = ["ferramentas/postar.py", "historias/contos/pipeline/reparo.py",
               "historias/tests/test_valvula_de_qualidade_regressions.py",
               "tarefa-consertada-primeiro.md"]


def test_assunto_do_pedido_do_grimorio_diz_o_no_e_os_arquivos():
    # o no do Grimorio na frente, os arquivos que mudaram (rascunho fora)
    assert vigia_trabalho.titulo_do_commit(PEDIDO_FC, FALA_FC, arquivos=ARQUIVOS_FC) == (
        "historias/reolhar-depois-do-conserto: postar.py, reparo.py + 1 teste")
    # sem arquivos: a pergunta, cortada na PALAVRA e com reticencias
    assunto = vigia_trabalho.titulo_do_commit({"titulo": GRIMORIO_LONGO}, "Implementado.")
    assert assunto.startswith("historias/imagens-divisao: Imagens das histórias: como dividir")
    assert len(assunto) <= vigia_trabalho.ASSUNTO_MAX and assunto.endswith("…")
    assert "O Adrian respondeu" not in assunto and "«" not in assunto
    assert not assunto[:-1].endswith((" ", ","))


def test_mensagem_do_pedido_tem_a_pergunta_os_arquivos_e_a_medida():
    mensagem = vigia_trabalho.mensagem_do_commit(
        PEDIDO_FC, FALA_FC, {"ok": True, "cmd": "python -m pytest ferramentas historias -q",
                             "resumo": "1427 passed, 21 skipped in 148.1s"},
        arquivos=ARQUIVOS_FC)
    linhas = mensagem.splitlines()
    assert linhas[0] == ("historias/reolhar-depois-do-conserto: postar.py, reparo.py + 1 teste"
                         " — 1427 passed, 21 skipped")
    assert ("Pedido: «IA olha de novo a parte consertada?» "
            "(Grimório historias/reolhar-depois-do-conserto)") in linhas
    assert "Arquivos: ferramentas/postar.py, historias/contos/pipeline/reparo.py" in mensagem
    assert "`python -m pytest ferramentas historias -q` deu 1427 passed, 21 skipped." in mensagem
    assert "Aguardo" not in mensagem                  # a narracao do orquestrador fica fora
    assert linhas[-1] == vigia_trabalho.CO_AUTOR


def test_assunto_do_pedido_do_app_e_a_primeira_oracao_e_os_arquivos():
    pedido = {"id": "pedido-66e4ba54", "cargo": "orquestrador", "titulo":
              "Preciso que você conserte o problema do Picasso, teste novamente para ver se "
              "foi, se tiver ido encha a reserva de vídeos novamente"}
    assunto = vigia_trabalho.titulo_do_commit(
        pedido, "O Picasso voltou.", arquivos=["remoto/delegar.py", "remoto/test_delegar.py",
                                               "resposta.md"])
    assert assunto == "Preciso que você conserte o problema do Picasso: delegar.py + 1 teste"


def test_integrador_herda_o_assunto_da_entrega_original(mundo):
    d = mundo.delegar
    d.ler_estado = lambda ident: dict(PEDIDO_FC) if ident == "pedido-fc098cab" else {}
    (d.pasta / "pedido-fc098cab").mkdir(parents=True, exist_ok=True)
    (d.pasta / "pedido-fc098cab" / "resposta.md").write_text(FALA_FC, encoding="utf-8")
    d.novo("integrar-pedido-fc098cab", mundo.depois, titulo="Integrar pedido-fc098cab",
           resposta="A entrega pedido-fc098cab está aplicada e com a suíte verde.\n",
           arquivos=tuple(ARQUIVOS_FC[:3]))
    d.tarefas["integrar-pedido-fc098cab"].update(cargo="integrador", ia="claude")
    d.testes["integrar-pedido-fc098cab"] = [
        {"ok": True, "codigo": 0, "resumo": "1522 passed, 21 skipped in 230.3s (0:03:50)"}]
    mundo.vigia.passo()
    mensagem = mundo.commits[0][1]
    assert mensagem.splitlines()[0] == (
        "historias/reolhar-depois-do-conserto: postar.py, reparo.py + 1 teste (integrado)"
        " — 1522 passed, 21 skipped")
    assert "Feito pelo Claude (integrar-pedido-fc098cab)" in mensagem
    assert "Pedido: «IA olha de novo a parte consertada?»" in mensagem
    # a fala do integrador (o que ele juntou) entra no corpo
    assert "A entrega pedido-fc098cab está aplicada" in mensagem


def test_integrador_com_original_longo_nao_dobra_reticencias():
    original = {"id": "x", "titulo": "Um título comprido " * 10}
    assunto = vigia_trabalho.titulo_do_commit({"titulo": "Integrar x", "cargo": "integrador"},
                                              "", original)
    assert assunto.endswith("… (integrado)") and "……" not in assunto
    assert len(assunto) <= vigia_trabalho.ASSUNTO_MAX


def test_medida_dos_testes():
    medida = vigia_trabalho.medida_dos_testes
    assert medida({"resumo": "1 failed, 887 passed, 1 warning in 512.00s (0:08:32)"}) \
        == "1 failed, 887 passed, 1 warning"
    assert medida({"sem_testes": True}) == "só documentação, sem testes"
    assert medida({"ok": True, "resumo": ""}) == "testes verdes"


def test_arvore_suja_diz_qual_e_tem_prazo(mundo):
    d = mundo.delegar
    d.novo("suja2", mundo.depois)
    d.tarefas["suja2"]["repo"] = "E:/projetos-wt/codex-pedido-66e4ba54"
    d.testes["suja2"] = [verde(), verde(), verde()]
    mundo.vigia.sujos = lambda arquivos, repo=None: ["remoto/x.py"]
    criados = []
    d.criar = lambda *a, **kw: criados.append(a)
    d.no_fundo = lambda *a: None
    t = mundo.vigia.passo()
    texto = t["esperando"]["suja2"]
    assert "codex-pedido-66e4ba54" in texto and "remoto/x.py" in texto
    assert "aviso o Adrian" in texto

    def alertas():
        return [a for a in mundo.avisos if a.startswith("⚠ entrega suja2")]
    assert not t["olho"] and not alertas()
    mundo.relogio.andar(30)
    assert not mundo.vigia.passo()["olho"]
    mundo.relogio.andar(31)
    t = mundo.vigia.passo()
    # passou do prazo: avisa UMA vez e SEGUE esperando (olho era sem volta)
    assert not t["olho"] and "(avisado)" in t["esperando"]["suja2"]
    assert len(alertas()) == 1 and "codex-pedido-66e4ba54" in alertas()[0]
    assert "a entrega volta sozinha" in alertas()[0]
    mundo.relogio.andar(30)
    mundo.vigia.passo()
    assert len(alertas()) == 1                               # nao repete
    assert criados == [] and not d.feitas("aplicar")          # sem integrador


def test_suja_depois_do_prazo_volta_quando_limpa(mundo):
    """A prova do conferente (05/10): a mensagem dizia "commite ou descarte e a
    entrega volta", mas ela ia para `olho` e nunca mais era aplicada."""
    d = mundo.delegar
    d.novo("suja3", mundo.depois)
    d.testes["suja3"] = [verde(), verde(), verde(), verde()]
    estado = {"sujos": ["remoto/x.py"]}
    mundo.vigia.sujos = lambda arquivos, repo=None: list(estado["sujos"])
    d.criar = lambda *a, **kw: None
    d.no_fundo = lambda *a: None
    mundo.vigia.passo()
    mundo.relogio.andar(61)
    t = mundo.vigia.passo()
    assert "a entrega volta sozinha" in t["esperando"]["suja3"]
    estado["sujos"] = []          # o Adrian commitou, como a mensagem pede
    mundo.relogio.andar(5)
    t = mundo.vigia.passo()
    assert d.feitas("aplicar") and mundo.commits and "suja3" not in t["esperando"]
    mem = mundo.vigia._ler_memoria()
    assert "suja3" not in mem["sujo_desde"] and "suja3" not in mem["sujo_avisado"]


def test_olho_antigo_por_arvore_suja_volta_a_ser_avaliado(mundo):
    d = mundo.delegar
    d.novo("velho-sujo", mundo.depois)
    d.testes["velho-sujo"] = [verde()]
    mem = mundo.vigia._ler_memoria()
    mem["olho"]["velho-sujo"] = {
        "motivo": "a árvore principal tem mudança não commitada em remoto/x.py",
        "em": mundo.relogio().isoformat(timespec="seconds")}
    mem["olho"]["outro"] = {"motivo": "o validador recusou: x",
                            "em": mundo.relogio().isoformat(timespec="seconds")}
    d.novo("outro", mundo.depois)
    mundo.vigia._gravar_memoria(mem)
    t = mundo.vigia.passo()
    assert d.feitas("aplicar") == [("aplicar", "velho-sujo")]
    assert [o["id"] for o in t["olho"]] == ["outro"]          # o resto segue no olho


@pytest.mark.parametrize("onde", ["testar", "coletar"])
def test_trava_ocupada_espera_sem_olho_nem_integrador(mundo, onde):
    """Conferente 05/10: outra rodada segurando o testar.lock (ou o
    delegar.lock) virava `olho` e contratava integrador por colisão de tempo."""
    d = mundo.delegar
    criados = []
    d.criar = lambda *a, **kw: criados.append(a)
    d.no_fundo = lambda *a: None
    d.novo("colide", mundo.depois)
    d.testes["colide"] = [verde()]
    original = getattr(d, onde)
    vezes = {"n": 0}

    def ocupado(ident, *a, **kw):
        vezes["n"] += 1
        if vezes["n"] == 1:
            raise Recusa("outra rodada de testes de colide está em andamento "
                         "(trava ocupada ha mais de 15 s: testar.lock)")
        return original(ident, *a, **kw)
    setattr(d, onde, ocupado)
    t = mundo.vigia.passo()
    assert not t["olho"] and criados == [] and "colide" in t["esperando"]
    assert not any("precisa de olho" in a or "travou" in a for a in mundo.avisos)
    mundo.relogio.andar(1)
    t = mundo.vigia.passo()                                  # o proximo passo aplica
    assert d.feitas("aplicar") and "colide" not in t["esperando"]


def test_recusa_passageira_pela_marca_da_excecao():
    class Ocupado(Exception):
        passageira = True
    assert vigia_trabalho.recusa_passageira(Ocupado("qualquer texto"))
    assert vigia_trabalho.recusa_passageira(OSError("trava ocupada ha mais de 15 s: delegar.lock"))
    assert not vigia_trabalho.recusa_passageira(Exception("conflito de merge em: x.py"))


def test_faxina_do_olho_e_dos_corrigidos(mundo):
    d = mundo.delegar
    d.novo("aplicada", mundo.depois)
    d.tarefas["aplicada"]["aplicado"] = {"arquivos": []}
    d.novo("velha", mundo.depois)
    mem = mundo.vigia._ler_memoria()
    agora = mundo.relogio()
    for ident, em in (("aplicada", agora), ("sumida", agora),
                      ("velha", agora - timedelta(hours=49))):
        mem["olho"][ident] = {"motivo": "x", "em": em.isoformat(timespec="seconds")}
    mem["corrigidos"]["sumida"] = {"em": agora.isoformat(timespec="seconds")}
    mundo.vigia._gravar_memoria(mem)
    t = mundo.vigia.passo()
    assert t["olho"] == []
    mem = mundo.vigia._ler_memoria()
    assert mem["corrigidos"] == {} and mem["arquivados"] == ["velha"]
    assert not d.feitas("coletar")                           # arquivada: o vigia nao volta


@pytest.mark.parametrize("assinatura", [
    "PermissionError: [WinError 5] Acesso negado: 'E:/tmp_pytest/bt'",
    "OSError: [WinError 145] O diretório não está vazio",
    "FileExistsError: [WinError 183] Não é possível criar um arquivo já existente",
    '_tkinter.TclError: invalid command name "tcl_findLibrary"',
])
def test_falha_de_ambiente_roda_os_testes_de_novo_antes_de_corrigir(mundo, assinatura):
    d = mundo.delegar
    d.novo("infra", mundo.depois)
    (d.pasta / "infra" / "testes.log").write_text("...\n" + assinatura + "\n1 error",
                                                  encoding="utf-8")
    d.testes["infra"] = [vermelho(), verde()]
    mundo.vigia.passo()
    assert len(d.feitas("testar")) == 2 and d.feitas("aplicar") and not mundo.corrigidos


def test_falha_de_ambiente_so_reroda_uma_vez_e_falha_de_codigo_nao_reroda(mundo):
    d = mundo.delegar
    d.novo("infra2", mundo.depois)
    (d.pasta / "infra2" / "testes.log").write_text("[WinError 145]", encoding="utf-8")
    d.testes["infra2"] = [vermelho(), vermelho()]
    d.novo("codigo", mundo.depois)
    (d.pasta / "codigo" / "testes.log").write_text("AssertionError: 1 != 2", encoding="utf-8")
    d.testes["codigo"] = [vermelho()]
    mundo.vigia.passo()
    testados = [c[1] for c in d.feitas("testar")]
    assert testados.count("infra2") == 2 and testados.count("codigo") == 1
    assert sorted(c[0] for c in mundo.corrigidos) == ["codigo", "infra2"]


def _encerrado(d, ident, situacao, horas_atras, mundo, **mais):
    fim = (mundo.relogio() - timedelta(hours=horas_atras)).isoformat(timespec="seconds")
    d.novo(ident, fim)
    d.tarefas[ident].update(situacao=situacao, **mais)


def test_faxina_limpa_delegado_encerrado_ha_6h_sem_commit(mundo):
    d = mundo.delegar
    frente = {"tem-commit": 1}
    d.commits_a_frente = lambda estado: frente.get(estado["id"], 0)
    _encerrado(d, "caiu", "falhou", 7, mundo)
    _encerrado(d, "negado1", "negado", 7, mundo)
    _encerrado(d, "conf-velho", "terminou", 7, mundo, cargo="conferente")
    _encerrado(d, "integ-ok", "terminou", 7, mundo, cargo="integrador",
               aplicado={"arquivos": []})
    _encerrado(d, "recente", "falhou", 5, mundo)                 # menos de 6 h
    _encerrado(d, "tem-commit", "falhou", 7, mundo)              # commit proprio
    _encerrado(d, "do-pedido", "falhou", 7, mundo)               # pedido aberto o retoma
    _encerrado(d, "entrega", "parado", 7, mundo)                 # trabalhador comum parado
    mundo.em_uso = {"do-pedido"}
    t = mundo.vigia.passo()
    assert len(d.feitas("limpar")) == 3                          # no maximo 3 por passo
    t = mundo.vigia.passo()
    limpos = sorted(c[1] for c in d.feitas("limpar"))
    assert limpos == ["caiu", "conf-velho", "integ-ok", "negado1"]
    assert {f["id"] for f in t["faxina"]} == set(limpos)
    # o diff do que caiu fica guardado na pasta (coletar antes de limpar)
    assert ("coletar", "caiu") in d.chamadas and ("coletar", "conf-velho") not in d.chamadas


def test_criado_antigo_sem_pedido_aberto_vira_abandonado(mundo):
    d = mundo.delegar
    d.tarefas["esquecido"] = {"id": "esquecido", "situacao": "criado", "limpo": None,
                               "criado_em": "2026-10-01T09:00:00"}
    d.commits_a_frente = lambda _estado: 0
    mundo.vigia.passo()
    assert d.tarefas["esquecido"]["situacao"] == "abandonado"
    assert ("abandonar", "esquecido") in d.chamadas


def test_criado_antigo_sujo_precisa_de_olho_sem_apagar(mundo):
    d = mundo.delegar
    d.tarefas["sujo-antigo"] = {"id": "sujo-antigo", "situacao": "criado", "limpo": None,
                                 "criado_em": "2026-10-01T09:00:00"}
    d.commits_a_frente = lambda _estado: 1
    mundo.vigia.passo()
    assert d.tarefas["sujo-antigo"]["situacao"] == "criado"
    assert any(x["id"] == "sujo-antigo" for x in mundo.vigia.ultimo["olho"])


def test_faxina_sem_ler_os_pedidos_nao_limpa_nada(mundo):
    d = mundo.delegar
    d.commits_a_frente = lambda estado: 0
    _encerrado(d, "caiu", "falhou", 7, mundo)

    def quebrado():
        raise ValueError("pedidos.json ilegível")
    mundo.vigia.em_uso = quebrado
    mundo.vigia.passo()
    assert not d.feitas("limpar")
    assert any(t == "trabalho_faxina" and "não limpo nada" in x for t, x in mundo.eventos)


# ================================ auditoria profunda 11/10 (consertos 14/10)
def test_commit_do_integrador_vai_para_as_duas_fichas(mundo):
    # COO-2: o pedido so fecha com commit; quem aplicou foi o integrador, e a
    # ficha original fica sabendo (aplicado_por + commit)
    d = mundo.delegar
    gravados = []

    def registrar_commit(ident, commit, aplicado_por=None):
        gravados.append((ident, commit, aplicado_por))
        d.tarefas.setdefault(ident, {"id": ident}).update(
            commit=commit, **({"aplicado_por": aplicado_por} if aplicado_por else {}))
    d.registrar_commit = registrar_commit
    d.ler_estado = lambda ident: {"id": ident, "titulo": "a original"} if ident == "x1" else {}
    d.novo("integrar-x1", mundo.depois, titulo="Integrar x1")
    d.tarefas["integrar-x1"]["cargo"] = "integrador"
    d.testes["integrar-x1"] = [verde()]
    mundo.vigia.passo()
    assert gravados == [("integrar-x1", "c1", None), ("x1", "c1", "integrar-x1")]


def test_commit_que_falha_nao_contrata_integrador(mundo):
    # COO-2 (3): os arquivos ja estao na arvore; um integrador bateria neles
    d = mundo.delegar
    criados = []
    d.criar = lambda ident, pedido, permitidos, **kw: criados.append(ident) or {"id": ident}
    d.no_fundo = lambda args, ident: None
    d.ler_estado = lambda ident: {"permitidos": ["remoto/**"]}

    def commitar(arquivos, mensagem):
        raise RuntimeError("git commit falhou: index.lock")
    mundo.vigia.commitar = commitar
    d.novo("sem-commit", mundo.depois)
    d.testes["sem-commit"] = [verde()]
    mundo.vigia.passo()
    assert criados == []
    assert any("aplicado na árvore, mas o commit falhou" in a for a in mundo.avisos)


def test_esperando_sai_quando_aplicada_por_fora(mundo):
    # COO-18: as entradas de `esperando` ficavam para sempre no retrato
    d = mundo.delegar
    d.novo("x1", mundo.depois)
    d.tarefas["x1"].update(aplicado={"em": "x"}, limpo={"em": "x"})
    d.novo("x2", mundo.depois)
    d.tarefas["x2"]["situacao"] = "parado"
    d.novo("vivo", mundo.depois)
    d.testes["vivo"] = [verde()]
    mundo.seguro[:] = [False, "publicacao em andamento"]
    mem = mundo.vigia._ler_memoria()
    mem["esperando"] = {"x1": "publicacao em andamento", "x2": "janela",
                        "sumiu": "janela"}
    mem["sujo_desde"] = {"x1": "2026-10-02T08:00:00"}
    mem["sujo_avisado"] = {"sumiu": "2026-10-02T08:00:00"}
    mundo.vigia._gravar_memoria(mem)
    mundo.vigia.passo()
    mem = mundo.vigia._ler_memoria()
    assert mem["esperando"] == {"vivo": "publicacao em andamento"}
    assert mem["sujo_desde"] == {} and mem["sujo_avisado"] == {}


def test_criado_antigo_sujo_avisa_uma_vez(mundo):
    # COO-19: o "criado antigo" ia ao olho (e ao Telegram) a cada passo
    d = mundo.delegar
    d.tarefas["sujo-antigo"] = {"id": "sujo-antigo", "situacao": "criado", "limpo": None,
                                 "criado_em": "2026-10-01T09:00:00"}
    d.commits_a_frente = lambda _estado: 1
    for _ in range(5):
        mundo.vigia.passo()
        mundo.relogio.andar(1)
    assert len([a for a in mundo.avisos if a.startswith("⚠") and "sujo-antigo" in a]) == 1


def test_criado_antigo_sem_saber_o_commit_nao_alarma(mundo):
    d = mundo.delegar
    d.tarefas["quem-sabe"] = {"id": "quem-sabe", "situacao": "criado", "limpo": None,
                               "criado_em": "2026-10-01T09:00:00"}
    d.commits_a_frente = lambda _estado: None
    for _ in range(3):
        mundo.vigia.passo()
    assert not [a for a in mundo.avisos if "quem-sabe" in a]
    assert d.tarefas["quem-sabe"]["situacao"] == "criado"
    assert [x for t, x in mundo.eventos if "quem-sabe" in x] == [
        "quem-sabe: não sei se tem commit"]


def test_em_uso_real_le_trabalhador_e_conferente_dos_pedidos_abertos(tmp_path, monkeypatch):
    import json
    from coordenador import pedidos
    arquivo = tmp_path / "pedidos.json"
    arquivo.write_text(json.dumps({"pedidos": [
        {"situacao": "parado_limite", "trabalhador": "w1", "conferente": None},
        {"situacao": "entregue", "trabalhador": "w2", "conferente": "c2"},
        {"situacao": "conferido", "trabalhador": "w3", "conferente": "c3"}]}),
        encoding="utf-8")
    monkeypatch.setattr(pedidos, "_arquivo", lambda: arquivo)
    assert vigia_trabalho._em_uso_real() == {"w1", "w2", "c2"}
    arquivo.write_text("{quebrado", encoding="utf-8")
    with pytest.raises(ValueError):
        vigia_trabalho._em_uso_real()
