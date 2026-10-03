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
    assert "perm-1" in gerente.estado["permissoes"] and avisos


def test_gerente_ligado_aceita_e_retoma_a_permissao_automatica():
    d = Despachante(True)
    gerente = GerenteEquipe(mesa=Mesa(), despachante=d)
    gerente.passo()
    assert d.decisões == [("perm-1", True)]
    assert d.fundos == [(["retomar", "--id", "perm-1"], "perm-1")]
