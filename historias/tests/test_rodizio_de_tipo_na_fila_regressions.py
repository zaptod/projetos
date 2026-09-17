"""O rodizio de tipo entra na fila sem desfazer o que ja estava garantido.

Decisao do Adrian (17/09/2026): tres tipos de historia no ar ao mesmo tempo
— favela, normal e babaca — com os horarios em rodizio entre eles. Sem isso
a fila esgota uma serie inteira antes de tocar na proxima, e quem abre o
perfil ve seis partes do mesmo tipo em seguida.

`contos.publicar.tipos.ordenar_por_tipo` faz a ordenacao e e funcao pura; o
que este arquivo trava e a LIGACAO dela na fila, que e onde estao as tres
maneiras de estragar coisa que ja funcionava:

1. O PEDIDO MANUAL tem de continuar vencendo. `_prioridades()` e um pedido
   de pessoa ("quero ver este video no ar ja", 14/09/2026) e o rodizio,
   aplicado por cima sem cuidado, o desfaria em silencio.
2. A ORDEM DAS PARTES tem de sobreviver. Ela sobrevive por construcao —
   todas as partes de uma historia tem o mesmo tipo, e o rodizio preserva a
   ordem relativa dentro de cada tipo —, mas "por construcao" e exatamente o
   tipo de garantia que some numa refatoracao sem teste.
3. ORDENAR E MELHORIA, e melhoria que levanta vira horario vazio. "A
   prioridade e nao ficar sem video".
"""
import importlib.util
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "postar_rodizio", RAIZ / "ferramentas" / "postar.py")
postar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(postar)


class _Parte:
    def __init__(self, fonte, parte):
        self.fonte_id = fonte
        self.parte = parte
        self.id = f"{fonte}:celular:p{parte:02d}"
        self.titulo = f"{fonte} (Parte {parte}/6)"


TIPOS = {"h_favela": "favela", "h_normal": "normal", "h_babaca": "babaca"}


class RodizioTests(unittest.TestCase):
    def setUp(self):
        for nome in ("_tipo_da_fonte", "_prioridades", "_linha"):
            self.addCleanup(setattr, postar, nome, getattr(postar, nome))
        postar._tipo_da_fonte = lambda f: TIPOS.get(f, "")
        postar._prioridades = lambda: []
        self.ditas = []
        postar._linha = lambda t="": self.ditas.append(t)

    def test_intercala_os_tipos(self):
        fila = [_Parte("h_favela", 1), _Parte("h_favela", 2),
                _Parte("h_normal", 1), _Parte("h_babaca", 1)]
        fora = postar._no_rodizio_dos_tipos(fila, [])
        tipos = [TIPOS[v.fonte_id] for v in fora]
        self.assertEqual(3, len(set(tipos[:3])),
                         "os tres primeiros horarios tem de ser de tipos "
                         "diferentes")

    def test_a_ordem_das_PARTES_sobrevive(self):
        """Todas as partes de uma historia tem o mesmo tipo, entao a ordem
        relativa dentro do tipo carrega a ordem da serie."""
        fila = [_Parte("h_favela", 2), _Parte("h_favela", 3),
                _Parte("h_normal", 1)]
        fora = postar._no_rodizio_dos_tipos(fila, [])
        favela = [v.parte for v in fora if v.fonte_id == "h_favela"]
        self.assertEqual([2, 3], favela)

    def test_o_PEDIDO_MANUAL_continua_na_frente(self):
        """`_prioridades()` e pedido de pessoa; o rodizio o desfaria em
        silencio."""
        postar._prioridades = lambda: ["h_normal:celular:p01"]
        fila = [_Parte("h_favela", 1), _Parte("h_babaca", 1),
                _Parte("h_normal", 1)]
        fora = postar._no_rodizio_dos_tipos(fila, [])
        self.assertEqual("h_normal:celular:p01", fora[0].id)
        self.assertEqual(3, len(fora), "o pedido nao pode sumir nem duplicar")

    def test_quem_saiu_por_ultimo_vai_para_o_fim(self):
        """O tipo que acabou de publicar espera; o que esta ha mais tempo
        sem sair vem primeiro."""
        publicados = [{"plataforma": "youtube", "url": "http://x",
                       "fonte_id": "h_favela", "quando": "2026-09-17T18:00"}]
        fila = [_Parte("h_favela", 1), _Parte("h_normal", 1)]
        fora = postar._no_rodizio_dos_tipos(fila, publicados)
        self.assertEqual("h_normal", fora[0].fonte_id)

    def test_historia_SEM_tipo_nao_some(self):
        """Historia feita antes de os tipos existirem nao pode sumir da
        fila: ela e conteudo pronto."""
        fila = [_Parte("h_favela", 1), _Parte("h_velha", 1)]
        fora = postar._no_rodizio_dos_tipos(fila, [])
        self.assertEqual({"h_favela", "h_velha"},
                         {v.fonte_id for v in fora})

    def test_falhar_a_ordenar_NAO_esvazia_a_fila(self):
        """Ordenar e melhoria; melhoria que levanta vira horario vazio."""
        def explode(_f):
            raise RuntimeError("roteiro ilegivel")
        postar._tipo_da_fonte = explode
        fila = [_Parte("h_favela", 1), _Parte("h_normal", 1)]
        fora = postar._no_rodizio_dos_tipos(fila, [])
        self.assertEqual(2, len(fora))
        self.assertIn("rodizio", " ".join(self.ditas))

    def test_fila_vazia_nao_explode(self):
        self.assertEqual([], postar._no_rodizio_dos_tipos([], []))


class NaFilaDeVerdadeTests(unittest.TestCase):
    def test_a_fila_de_historias_usa_o_rodizio(self):
        import inspect
        fonte = inspect.getsource(postar.fila_de_historias)
        sem_comentario = "\n".join(
            l for l in fonte.splitlines() if not l.strip().startswith("#"))
        self.assertIn("_no_rodizio_dos_tipos(", sem_comentario,
                      "ordenador que ninguem chama nao ordena nada")

    def test_o_rodizio_vem_DEPOIS_dos_crivos(self):
        """Ele so ORDENA. Aplicado antes de `_sem_fonte_cheia` e do titulo
        repetido, ordenaria gente que vai ser removida — e o teto por fonte
        teria dois donos."""
        import inspect
        fonte = inspect.getsource(postar.fila_de_historias)
        self.assertLess(fonte.find("_sem_fonte_cheia("),
                        fonte.find("_no_rodizio_dos_tipos("))
        self.assertLess(fonte.find("_sem_titulo_repetido("),
                        fonte.find("_no_rodizio_dos_tipos("))


class TipoDaFonteTests(unittest.TestCase):
    def test_lembra_por_fonte(self):
        """A fila tem dezenas de partes e poucas historias; ler o roteiro
        uma vez por parte e disco a toa."""
        postar._TIPOS_LEMBRADOS.clear()
        postar._TIPOS_LEMBRADOS["h_x"] = "favela"
        self.assertEqual("favela", postar._tipo_da_fonte("h_x"))

    def test_roteiro_ilegivel_devolve_vazio_e_nao_levanta(self):
        postar._TIPOS_LEMBRADOS.clear()
        self.assertEqual("", postar._tipo_da_fonte("nao_existe_nenhuma"))


if __name__ == "__main__":
    unittest.main()
