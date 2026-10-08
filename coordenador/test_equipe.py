# -*- coding: utf-8 -*-
"""Permissoes automaticas do gerente, sem abrir trabalhador real."""
from coordenador.equipe import GerenteEquipe


class Despachante:
    def __init__(self, ligado):
        self.ligado, self.decisões, self.fundos = ligado, [], []
        self.tarefa = {"id": "perm-1", "situacao": "aguardando_permissao", "cargo": "jogo-zombie",
                       "pedido_permissao": {"o_que": "usar repo", "categoria": "repositorio_externo",
                                              "por_que": "jogo separado", "alvo": r"E:\jogo_ZOMBIE"}}

    def ler_config(self):
        return {"gerente_ligado": self.ligado, "delegados_paralelo": 1}

    def listar(self):
        return [self.tarefa]

    def regra_de_permissao(self, *_args):
        return "gerente_aceita"

    def decidir_permissao(self, ident, permitir):
        self.decisões.append((ident, permitir))
        return {"situacao": "criado"}

    def no_fundo(self, args, ident):
        self.fundos.append((args, ident))

    def cargos(self):
        return []


class Mesa:
    def ler_estado(self):
        return {"fila": []}


def test_gerente_desligado_deixa_a_permissao_automatica_para_o_adrian():
    d, avisos = Despachante(False), []
    gerente = GerenteEquipe(mesa=Mesa(), despachante=d, avisar=avisos.append)
    gerente.passo()
    assert d.decisões == [] and d.fundos == []
    assert any(k.startswith("perm-1|") for k in gerente.estado["permissoes"]) and avisos


def test_gerente_ligado_aceita_e_retoma_a_permissao_automatica():
    d = Despachante(True)
    gerente = GerenteEquipe(mesa=Mesa(), despachante=d)
    gerente.passo()
    assert d.decisões == [("perm-1", True)]
    assert d.fundos == [(["retomar", "--id", "perm-1"], "perm-1")]


class MesaComFila:
    def __init__(self, pausada):
        self.pausada = pausada

    def ler_estado(self):
        return {"fila": [{"id": "f1", "parte": "builds", "item": "re-render"}]}

    def ler_config(self):
        return {"fila_pausada": self.pausada}


def test_gerente_nao_contrata_a_fila_da_mesa():
    # b3: fila e pedido; so MesaPedidos.passo pode contratar.
    for pausada in (True, False):
        d = Despachante(True)
        d.tarefa = {"id": "outra", "situacao": "terminou"}
        gerente = GerenteEquipe(mesa=MesaComFila(pausada), despachante=d)
        contratados = []
        gerente._contratar = lambda item: contratados.append(item["id"])
        gerente.passo()
        assert contratados == []


class DespachanteDeConferencia(Despachante):
    """Um trabalhador ja aplicado: o gerente contrata o conferente."""

    def __init__(self, raiz):
        super().__init__(True)
        self.raiz, self.criados = raiz, []
        self.tarefa = {"id": "t1", "situacao": "terminou", "aplicado": {"arquivos": ["x.py"]}}

    def pasta(self):
        return self.raiz

    def prompt_do_cargo(self, cargo):
        return f"[cargo {cargo}]"

    def criar(self, ident, arquivo, _permitidos, **kw):
        self.criados.append((ident, kw, arquivo.read_text(encoding="utf-8")))
        return {"ia": kw.get("ia")}


class MesaComUso(Mesa):
    def __init__(self, passou):
        self.passou = passou

    def ler_uso(self):
        return {"passou_teto": self.passou, "motivo_teto": "a semana está em 100% (teto 95%)"}


def test_conferente_responde_na_mensagem_final_e_vai_ao_codex_acima_do_teto(tmp_path):
    """Item 12 e 6 de 05/10: nada de resposta.md na worktree; com a semana no
    teto o conferente nao nasce Claude (caia na hora)."""
    for passou, ia in ((False, "claude"), (True, "codex")):
        d = DespachanteDeConferencia(tmp_path / ia)
        GerenteEquipe(mesa=MesaComUso(passou), despachante=d)._conferir_aplicadas()
        ident, kw, texto = d.criados[0]
        assert kw["ia"] == ia and kw["cargo"] == "conferente"
        assert "mensagem final" in texto and "em resposta.md" not in texto
        assert texto.startswith("[cargo conferente]") == (ia == "codex")
