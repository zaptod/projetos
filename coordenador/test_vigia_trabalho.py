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
                            proibido="", fichas=[], sujos=[])

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
        memoria=tmp_path / "memoria.json")
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
    assert mensagem.startswith("Conserta o X sem quebrar o Y (feito pelo Codex, validado pelo vigia)")
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
    assert any("teimoso precisa de olho" in a for a in mundo.avisos)
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
    d.novo("fora", mundo.depois, ok=False, motivos=["fora da lista permitida: palco/x.gd"])
    mundo.vigia.passo()
    assert not d.feitas("testar") and not d.feitas("aplicar")
    assert any("fora precisa de olho" in a and "palco/x.gd" in a for a in mundo.avisos)
    assert mundo.vigia.ultimo["olho"][0]["id"] == "fora"


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
    assert not d.feitas("aplicar") and any("não commitada" in a for a in mundo.avisos)


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
    s = Supervisor(servicos={"app": {"nome": "app", "assinatura": "app", "comando": ["app"],
                                     "cwd": ".", "log": "x.log", "janela": "oculta",
                                     "modulos": [], "reinicio_seguro": True}},
                   relogio=relogio, processos=lambda: [{"pid": 1, "comando": "app"}],
                   porta=lambda: True, git=lambda *_: False, avisar=lambda *_: None,
                   gravar=lambda _: None, log=lambda _: None, parar=parou.append,
                   iniciar=lambda _: iniciou.append(2) or 2,
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
