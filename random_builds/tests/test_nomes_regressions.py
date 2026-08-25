# -*- coding: utf-8 -*-
# Codigo e comentarios em ASCII; os valores de catalogo mantem acento
# ("Epico" no banco e "Epico" com acento), como manda a convencao do projeto.
"""Contratos da camada de nomes (pedido 4) e do nome vindo do comentario.

O que este arquivo trava:

1. NENHUM nome termina em qualidade/adjetivo. Era a reclamacao literal do
   usuario ("nao gosto do adjetivo no final"). A varredura roda o catalogo
   inteiro do neural_fights, nao uma amostra.
2. O nome antigo do jogo REPROVA na mesma regra - cobrado contra o
   vocabulario VIVO do gerador antigo, nao contra literais escolhidos a dedo.
   E a garantia principal nao e a blacklist (lista nunca fecha): e a whitelist
   estrutural de ClassificacaoEstrutural, que so aceita como ultima palavra
   uma palavra que as proprias tabelas do modulo conseguem construir.
3. Determinismo: mesmo rng + mesmos dados => mesmo nome, sempre.
4. Categoria que nao esta no lexico nao levanta excecao (pedido 2): cai no
   fallback e devolve nome valido.
5. O nome pedido no comentario vence o gerado, e o generation.json registra
   que ele veio de fora (e qual teria sido o gerado).
6. O sorteio nao muda por causa do pedido: a mesma seed com e sem nome de fora
   produz a MESMA arma e as MESMAS rolagens.

Rode de dentro de random_builds/:
    python -m pytest tests/test_nomes_regressions.py -q
"""
import random
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.character import lexico, nomes  # noqa: E402
from src.nf_bridge import loader as nf  # noqa: E402


def _elemento(encantamento):
    return nf.elemento_do_encantamento(encantamento)


class TerminaBem(unittest.TestCase):
    def test_reprova_o_formato_antigo_do_jogo(self):
        """A regra so vale se ela morde os nomes que existem hoje no banco."""
        for antigo in ["Silas o Sombrio", "Lucius a Sombria",
                       "Seraphina o Invicto", "Katana Comum",
                       "Marfim Katana Refinado", "Mistico Katana Superior",
                       "Tyr das Chamas", "Celestial Katana do Fim"]:
            self.assertFalse(nomes.termina_bem(antigo), antigo)

    def test_aprova_o_formato_novo(self):
        for novo in ["Erik Brasurro", "Arquimestra Ayame Vidrocripta",
                     "Gume Brasar", "Alta Salva de Ferielen"]:
            self.assertTrue(nomes.termina_bem(novo), novo)

    def test_nome_vazio_reprova(self):
        self.assertFalse(nomes.termina_bem(""))
        self.assertFalse(nomes.termina_bem("   "))


def _ultimas_palavras_construtiveis():
    """O conjunto FECHADO de terminacoes que podem fechar um nome gerado.

    POR QUE whitelist e nao blacklist: a lista de proibidos tem que adivinhar
    cada adjetivo que alguem possa colar no fim, e adivinhar errado deixa a
    varredura aprovar 40 mil nomes com "Celestial" no fim sem falhar nada.

    O conjunto sai da PROPRIA funcao de juncao do lexico, e nao de uma
    reimplementacao dela: `juntar` aplica elisao e ligacao na emenda, entao
    "umbr" + "veth" nao vira "umbrveth". Enumerar as tabelas sem passar por ela
    produzia um conjunto que o gerador real nao respeita - o teste falhava por
    defeito do teste. Aqui, toda emenda possivel entre um morfema qualquer e um
    morfema TERMINAL e materializada; nome gerado tem de terminar em uma delas.
    """
    morfemas = set()
    for tabela in (lexico.PREFIXOS_ELEMENTAIS, lexico.MEDIAIS_LINHAGEM,
                   lexico.SUFIXOS_LINHAGEM, lexico.SUFIXOS_ARMA):
        for pool in tabela.values():
            morfemas.update(pool)
    morfemas.update(lexico.MEDIAIS_FORJA)
    morfemas.update(lexico.CODAS_ALTAS)

    terminais = set()
    for tabela in (lexico.SUFIXOS_LINHAGEM, lexico.SUFIXOS_ARMA):
        for pool in tabela.values():
            terminais.update(pool)
    terminais.update(lexico.CODAS_ALTAS)

    fechado = {t.lower() for t in terminais}
    fechado |= {lexico.juntar(a, t).lower() for a in morfemas for t in terminais}
    return frozenset(fechado)


def _construtivel(nome, conjunto):
    """A ultima palavra termina em alguma forma do conjunto fechado?

    Testa os SUFIXOS da palavra contra o conjunto, e nao o conjunto inteiro com
    endswith: sao ~62 mil formas e dezenas de milhares de nomes na varredura.
    Pelo lado da palavra sao poucas buscas em set; pelo lado do conjunto o teste
    levava minutos e ninguem rodaria.
    """
    ultima = nome.split()[-1].lower()
    return any(ultima[i:] in conjunto for i in range(len(ultima)))


class ClassificacaoEstrutural(unittest.TestCase):
    """A ultima palavra e construtivel pelas tabelas, nao "nao esta na lista"."""

    @classmethod
    def setUpClass(cls):
        cls.construtiveis = _ultimas_palavras_construtiveis()

    def test_a_ultima_palavra_de_todo_nome_gerado_e_construtivel(self):
        rng = random.Random(1234)
        for classe in nf.LISTA_CLASSES:
            for personalidade in nf.lista_personalidades():
                for encantamento in nf.LISTA_ENCANTAMENTOS:
                    for raridade in nf.LISTA_RARIDADES:
                        nome = nomes.gerar_nome_personagem(
                            rng, classe=classe, personalidade=personalidade,
                            encantamento=encantamento,
                            elemento=_elemento(encantamento), raridade=raridade)
                        self.assertTrue(_construtivel(nome, self.construtiveis), nome)

    def test_a_ultima_palavra_de_toda_arma_e_construtivel(self):
        rng = random.Random(4321)
        for tipo in nf.LISTA_TIPOS_ARMA:
            for encantamento in nf.LISTA_ENCANTAMENTOS:
                for raridade in nf.LISTA_RARIDADES:
                    for _ in range(20):
                        nome = nomes.gerar_nome_arma(
                            rng, tipo=tipo, encantamento=encantamento,
                            elemento=_elemento(encantamento), raridade=raridade)
                        self.assertTrue(_construtivel(nome, self.construtiveis), nome)

    def test_um_sufixo_colado_no_fim_NAO_pertence_ao_conjunto(self):
        """Prova que a whitelist morde onde a blacklist passava batido.

        "Celestial" nao estava entre os proibidos e a varredura inteira
        aprovava nomes terminados nele. Aqui ele reprova por construcao, junto
        com qualquer palavra que ninguem tenha previsto.
        """
        for sufixo in ("Celestial", "Divino", "Xyzzy", "Sombrio", "Supremo",
                       "Zqxwvu", "Comum", "Refinado"):
            self.assertFalse(_construtivel("Ragnar " + sufixo, self.construtiveis),
                             sufixo)


class VocabularioLegado(unittest.TestCase):
    """A regra e cobrada contra o vocabulario VIVO do gerador antigo."""

    @classmethod
    def setUpClass(cls):
        import itertools

        import neural_fights.tools.gerador_database as antigo
        cls.antigo = antigo
        vocab = set()
        for atributo in ("TITULOS", "SUFIXOS_ELEMENTO", "SUFIXOS_LENDARIOS",
                         "PREFIXOS_QUALIDADE"):
            valor = getattr(antigo, atributo, None)
            if valor is None:
                continue
            itens = (itertools.chain.from_iterable(valor.values())
                     if isinstance(valor, dict) else valor)
            for item in itens:
                for palavra in str(item).split():
                    marca = nomes.chave(palavra)
                    if marca:
                        vocab.add(marca)
        cls.vocab = vocab

    def test_o_vocabulario_do_gerador_antigo_esta_todo_barrado(self):
        """Sem isto a blacklist parece fechar e nao fecha.

        Medido antes: 59 das 94 palavras do gerador antigo NAO estavam na
        lista, e 536 de 2000 nomes no formato exato de que o usuario reclamou
        passavam pela regra.
        """
        fora = sorted(p for p in self.vocab
                      if p not in nomes.PROIBIDO_NO_FIM
                      and p.lower() not in nomes.ARTIGOS_PENDURADOS)
        self.assertEqual([], fora)

    def test_o_gerador_antigo_de_verdade_reprova_em_massa(self):
        """Nao 8 literais a dedo: o proprio gerar_nome_arma do jogo."""
        random.seed(3)
        aprovados = [n for n in
                     (self.antigo.gerar_nome_arma("Reta", "Lendário", "Katana",
                                                  "Chamas")
                      for _ in range(500))
                     if nomes.termina_bem(n)]
        self.assertEqual([], aprovados[:5])


class VarreduraPersonagem(unittest.TestCase):
    def test_catalogo_inteiro_sem_adjetivo_no_fim(self):
        rng = random.Random(20260824)
        total, exemplos = 0, []
        for classe in nf.LISTA_CLASSES:
            for personalidade in nf.LISTA_PERSONALIDADES:
                for encantamento in nf.LISTA_ENCANTAMENTOS:
                    for raridade in nf.LISTA_RARIDADES:
                        nome = nomes.gerar_nome_personagem(
                            rng, classe=classe, personalidade=personalidade,
                            encantamento=encantamento,
                            elemento=_elemento(encantamento),
                            raridade=raridade)
                        total += 1
                        if not nomes.termina_bem(nome):
                            exemplos.append(nome)
                        nome.encode("ascii")
                        self.assertFalse(nome.startswith(
                            nomes.PREFIXO_RESERVADO), nome)
        self.assertGreater(total, 10000, "varredura pequena demais")
        self.assertEqual(exemplos[:5], [], f"{len(exemplos)} de {total}")

    def test_casa_nunca_gagueja(self):
        """Agulha + agulha dava 'Agulhagulha'; a checagem de colisao morreu?"""
        rng = random.Random(7)
        for _ in range(4000):
            nome = nomes.gerar_nome_personagem(
                rng, classe="Duelista (Precisão)", personalidade="Assassino",
                encantamento="Crítico", elemento="FISICO", raridade="Comum")
            casa = nome.split()[-1].lower()
            self.assertNotIn(casa[:4], casa[4:], nome)

    def test_honorifico_concorda_com_o_genero(self):
        """'Lucius a Sombria' nasceu de titulo sorteado sem olhar o genero."""
        rng = random.Random(11)
        masc = {m for m, _f in nomes.HONORIFICOS["MITICO"]}
        fem = {f for _m, f in nomes.HONORIFICOS["MITICO"]}
        so_masc, so_fem = masc - fem, fem - masc
        for _ in range(500):
            homem = nomes.gerar_nome_personagem(
                rng, classe="Guerreiro (Força Bruta)", personalidade="Viking",
                encantamento="Chamas", raridade="Mítico", genero="m")
            mulher = nomes.gerar_nome_personagem(
                rng, classe="Guerreiro (Força Bruta)", personalidade="Viking",
                encantamento="Chamas", raridade="Mítico", genero="f")
            self.assertNotIn(homem.split()[0], so_fem, homem)
            self.assertNotIn(mulher.split()[0], so_masc, mulher)

    def test_raridade_baixa_nao_ganha_honorifico(self):
        rng = random.Random(3)
        for raridade in ("Comum", "Incomum", "Raro", "Épico"):
            for _ in range(100):
                nome = nomes.gerar_nome_personagem(
                    rng, classe="Mago (Arcano)", personalidade="Tático",
                    encantamento="Gelo", raridade=raridade)
                self.assertEqual(len(nome.split()), 2, f"{raridade}: {nome}")


class VarreduraArma(unittest.TestCase):
    def test_catalogo_inteiro_sem_qualidade_no_fim(self):
        rng = random.Random(99)
        total, exemplos = 0, []
        for tipo in nf.LISTA_TIPOS_ARMA:
            for encantamento in nf.LISTA_ENCANTAMENTOS:
                for raridade in nf.LISTA_RARIDADES:
                    for _ in range(6):
                        nome = nomes.gerar_nome_arma(
                            rng, tipo=tipo, encantamento=encantamento,
                            elemento=_elemento(encantamento),
                            raridade=raridade)
                        total += 1
                        if not nomes.termina_bem(nome):
                            exemplos.append(nome)
                        nome.encode("ascii")
        self.assertGreater(total, 3000, "varredura pequena demais")
        self.assertEqual(exemplos[:5], [], f"{len(exemplos)} de {total}")

    def test_raridade_alta_nao_reintroduz_epiteto(self):
        """A raridade pesa na SONORIDADE, nao acrescenta palavra.

        Era aqui que "Grande Relicario de Vulkoron" nascia. O nome de arma
        mitico continua sendo uma palavra; o que muda e a densidade dela.
        """
        rng = random.Random(1)
        curto, longo = [], []
        for _ in range(300):
            comum = nomes.gerar_nome_arma(rng, tipo="Dupla",
                                          encantamento="Trevas",
                                          raridade="Comum")
            mitico = nomes.gerar_nome_arma(rng, tipo="Dupla",
                                           encantamento="Trevas",
                                           raridade="Mítico")
            self.assertEqual(len(comum.split()), 1, comum)
            self.assertEqual(len(mitico.split()), 1, mitico)
            curto.append(len(comum))
            longo.append(len(mitico))
        media_curto = sum(curto) / len(curto)
        media_longo = sum(longo) / len(longo)
        self.assertGreater(media_longo, media_curto,
                           "raridade alta tem de soar mais densa: "
                           "Comum=%.1f Mitico=%.1f" % (media_curto, media_longo))

    def test_arma_e_sempre_uma_palavra_so(self):
        """Nome proprio puro, como Excalibur - nunca "tipo + qualificador".

        O formato antigo era "Machado-Martelo Comum": o substantivo do tipo
        colado a raridade. O dono trocou por nome proprio, entao QUALQUER
        segunda palavra e regressao - preposicao, epiteto ou classificador.
        """
        rng = random.Random(5)
        for raridade in (None, "Comum", "Incomum", "Raro", "Épico",
                         "Lendário", "Mítico"):
            for _ in range(120):
                nome = nomes.gerar_nome_arma(rng, tipo="Reta",
                                             encantamento="Chamas",
                                             raridade=raridade)
                self.assertEqual(len(nome.split()), 1, nome)
                self.assertNotIn(" de ", nome)


class Determinismo(unittest.TestCase):
    def test_mesmo_rng_mesmo_nome_personagem(self):
        args = dict(classe="Necromante (Trevas)", personalidade="Sombrio",
                    encantamento="Trevas", elemento="TREVAS",
                    raridade="Lendário")
        a = nomes.gerar_nome_personagem(random.Random(4242), **args)
        b = nomes.gerar_nome_personagem(random.Random(4242), **args)
        self.assertEqual(a, b)

    def test_mesmo_rng_mesmo_nome_arma(self):
        args = dict(tipo="Orbital", encantamento="Sagrado", elemento="LUZ",
                    raridade="Mítico")
        a = nomes.gerar_nome_arma(random.Random(4242), **args)
        b = nomes.gerar_nome_arma(random.Random(4242), **args)
        self.assertEqual(a, b)

    def test_sequencia_inteira_reproduz(self):
        def lote(seed):
            rng = random.Random(seed)
            return [nomes.gerar_nome_personagem(
                rng, classe="Ninja (Velocidade)", personalidade="Fantasma",
                encantamento="Velocidade", raridade="Raro")
                for _ in range(50)]
        self.assertEqual(lote(1), lote(1))
        self.assertNotEqual(lote(1), lote(2))

    def test_nao_toca_no_random_global(self):
        random.seed(123)
        antes = random.random()
        random.seed(123)
        nomes.gerar_nome_personagem(random.Random(9), classe="Mago (Arcano)")
        nomes.gerar_nome_arma(random.Random(9), tipo="Reta")
        self.assertEqual(antes, random.random())


class CategoriaDesconhecida(unittest.TestCase):
    """Pedido 2: banco pode ganhar classe/encantamento/raridade nova."""

    def test_tudo_desconhecido_ainda_gera_nome_valido(self):
        rng = random.Random(31)
        nome = nomes.gerar_nome_personagem(
            rng, classe="Xamane (Areia)", personalidade="Ansioso",
            encantamento="Areia", elemento="AREIA", raridade="Transcendente")
        self.assertTrue(nomes.termina_bem(nome), nome)
        self.assertEqual(len(nome.split()), 2, nome)

    def test_arma_de_tipo_desconhecido(self):
        rng = random.Random(31)
        nome = nomes.gerar_nome_arma(
            rng, tipo="Sopro", encantamento="Areia", elemento="AREIA",
            raridade="Transcendente")
        self.assertTrue(nomes.termina_bem(nome), nome)
        # Tipo que o lexico nao conhece cai no pool NEUTRO e ainda entrega um
        # nome proprio de uma palavra - o pedido 2 aplicado ao nome.
        self.assertEqual(len(nome.split()), 1, nome)
        self.assertGreaterEqual(len(nome), 4, nome)

    def test_none_em_tudo_nao_estoura(self):
        rng = random.Random(2)
        self.assertTrue(nomes.termina_bem(nomes.gerar_nome_personagem(rng)))
        self.assertTrue(nomes.termina_bem(nomes.gerar_nome_arma(rng)))

    def test_catalogo_de_hoje_esta_todo_mapeado(self):
        """Nao e regra de quebra: e a lista do que falta ganhar sabor.

        Se o jogo ganhar uma categoria, o gerador continua funcionando (os
        testes acima provam); este teste so aponta onde acrescentar a linha.
        """
        faltando = []
        for classe in nf.LISTA_CLASSES:
            if nomes.chave(classe) not in nomes.CULTURA_POR_CLASSE:
                faltando.append(f"CULTURA_POR_CLASSE: {classe}")
        for p in nf.LISTA_PERSONALIDADES:
            if nomes.chave(p) not in nomes.NUCLEO_POR_PERSONALIDADE:
                faltando.append(f"NUCLEO_POR_PERSONALIDADE: {p}")
        for e in nf.LISTA_ENCANTAMENTOS:
            if nomes.chave(e) not in nomes.RAIZES_CASA:
                faltando.append(f"RAIZES_CASA: {e}")
            if nomes.chave(e) not in nomes.RAIZES_ARMA:
                faltando.append(f"RAIZES_ARMA: {e}")
        for t in nf.LISTA_TIPOS_ARMA:
            if nomes.chave(t) not in nomes.CLASSIFICADOR_POR_TIPO:
                faltando.append(f"CLASSIFICADOR_POR_TIPO: {t}")
        for r in nf.LISTA_RARIDADES:
            if nomes.chave(r) not in nomes.DEGRAUS:
                faltando.append(f"DEGRAUS: {r}")
        self.assertEqual(faltando, [])


class NomePedido(unittest.TestCase):
    def test_arroba_e_reservado_pelo_jogo(self):
        """'@' e prefixo de lutador de espectador no neural_fights."""
        nome, motivo = nomes.sanitizar_nome_pedido("@kaelen")
        self.assertEqual(nome, "Kaelen")
        self.assertIsNone(motivo)

    def test_corta_lixo_e_limita_tamanho(self):
        nome, _ = nomes.sanitizar_nome_pedido("  kaelen!!! <3 o brabo  ")
        self.assertEqual(nome, "Kaelen O Brabo")
        longo, _ = nomes.sanitizar_nome_pedido("Z" * 60)
        self.assertLessEqual(len(longo), nomes.MAX_CHARS_PEDIDO)
        muitas, _ = nomes.sanitizar_nome_pedido("um dois tres quatro cinco")
        self.assertEqual(len(muitas.split()), nomes.MAX_PALAVRAS_PEDIDO)

    def test_recusa_o_que_nao_da_nome(self):
        for lixo in ["", "   ", "@@@", "!!!", "\U0001f600", 42, None, "1"]:
            nome, motivo = nomes.sanitizar_nome_pedido(lixo)
            self.assertIsNone(nome, repr(lixo))
            self.assertTrue(motivo, repr(lixo))

    def test_pedido_vence_o_gerado(self):
        proc = nomes.resolver_nome_personagem(
            random.Random(4242), classe="Mago (Arcano)",
            personalidade="Tático", encantamento="Gelo", raridade="Épico",
            nome_pedido="  vitinho da massa  ")
        self.assertEqual(proc["name"], "Vitinho Da Massa")
        self.assertEqual(proc["origin"], "comment")
        self.assertTrue(proc["requested_accepted"])
        self.assertNotEqual(proc["generated_name"], proc["name"])

    def test_pedido_invalido_cai_no_gerado_com_motivo(self):
        proc = nomes.resolver_nome_personagem(
            random.Random(4242), classe="Mago (Arcano)",
            personalidade="Tático", encantamento="Gelo", raridade="Épico",
            nome_pedido="@@@")
        self.assertEqual(proc["name"], proc["generated_name"])
        self.assertEqual(proc["origin"], "generated")
        self.assertFalse(proc["requested_accepted"])
        self.assertTrue(proc["requested_reason"])

    def test_pedido_nao_muda_o_nome_gerado(self):
        """O gerado tem que sair igual com e sem pedido: mesma seed, mesma build."""
        base = dict(classe="Mago (Arcano)", personalidade="Tático",
                    encantamento="Gelo", raridade="Épico")
        com = nomes.resolver_nome_personagem(random.Random(77),
                                             nome_pedido="Lyra", **base)
        sem = nomes.resolver_nome_personagem(random.Random(77), **base)
        self.assertEqual(com["generated_name"], sem["generated_name"])


class Pipeline(unittest.TestCase):
    """Amarra a camada nova no exporter e no generation.json."""

    @classmethod
    def setUpClass(cls):
        from src.generation.session_generator import SessionGenerator
        cls.session = SessionGenerator()

    def test_generation_traz_naming_e_nome_bom(self):
        g = self.session.generate(seed=4242)
        self.assertTrue(nomes.termina_bem(g["character"]["nome"]),
                        g["character"]["nome"])
        self.assertTrue(nomes.termina_bem(g["weapon"]["nome"]),
                        g["weapon"]["nome"])
        self.assertEqual(g["naming"]["character_name"], g["character"]["nome"])
        self.assertEqual(g["naming"]["weapon_name"], g["weapon"]["nome"])
        self.assertEqual(g["naming"]["character_name_origin"], "generated")
        self.assertNotIn("nome_pedido", g)
        # o vinculo do jogo continua apontando para o nome que o video mostra
        self.assertEqual(g["character"]["nome_arma"], g["weapon"]["nome"])

    def test_pedido_vence_e_fica_registrado(self):
        g = self.session.generate(seed=4242, nome_pedido="@kaelen",
                                  autor_pedido="@fulano")
        base = self.session.generate(seed=4242)
        self.assertEqual(g["character"]["nome"], "Kaelen")
        self.assertEqual(g["naming"]["character_name_origin"], "comment")
        self.assertEqual(g["naming"]["requested_name"], "@kaelen")
        self.assertTrue(g["naming"]["requested_name_accepted"])
        self.assertEqual(g["naming"]["generated_character_name"],
                         base["character"]["nome"])
        # formato lido pela CTA (caption_generator.pedido_de)
        self.assertEqual(g["nome_pedido"]["nome"], "Kaelen")
        self.assertEqual(g["nome_pedido"]["autor"], "@fulano")
        self.assertEqual(g["nome_pedido"]["origem"], "comentario")

    def test_pedido_nao_altera_o_resto_da_build(self):
        com = self.session.generate(seed=4242, nome_pedido="Kaelen")
        sem = self.session.generate(seed=4242)
        self.assertEqual(com["weapon"], sem["weapon"])
        self.assertEqual(com["character_rolls"], sem["character_rolls"])
        self.assertEqual(com["weapon_rolls"], sem["weapon_rolls"])
        self.assertEqual(com["final_score"], sem["final_score"])

    def test_mesma_seed_mesma_build(self):
        a = self.session.generate(seed=1234)
        b = self.session.generate(seed=1234)
        self.assertEqual(a["character"], b["character"])
        self.assertEqual(a["weapon"], b["weapon"])

    def test_cta_le_o_pedido(self):
        from src.content.caption_generator import pedido_de
        g = self.session.generate(seed=99, nome_pedido="lyra",
                                  autor_pedido="@zeca")
        self.assertEqual(pedido_de(g)["nome"], "LYRA")


class Unicidade(unittest.TestCase):
    def test_nome_unico_continua_desambiguando(self):
        from src.nf_bridge.exporter import _nome_unico
        usados = {"Erik Brasurro", "Erik Brasurro #2"}
        self.assertEqual(_nome_unico("Erik Brasurro", usados),
                         "Erik Brasurro #3")
        self.assertEqual(_nome_unico("Gume Brasar", usados), "Gume Brasar")

    def test_colisao_e_rara_em_lote(self):
        """Nome repetido vira '#2' na placa; nao pode ser o caso comum."""
        rng = random.Random(2026)
        vistos = [nomes.gerar_nome_personagem(
            rng,
            classe=rng.choice(nf.LISTA_CLASSES),
            personalidade=rng.choice(nf.LISTA_PERSONALIDADES),
            encantamento=rng.choice(nf.LISTA_ENCANTAMENTOS),
            raridade=rng.choice(nf.LISTA_RARIDADES)) for _ in range(2000)]
        self.assertGreater(len(set(vistos)), 1900, len(set(vistos)))


class SemCiclo(unittest.TestCase):
    def test_nomes_nao_importa_identity_nem_editing(self):
        """Ciclo de import: nomes e chamado la de baixo, no exporter."""
        import ast
        fonte = (RAIZ / "src" / "character" / "nomes.py").read_text()
        for no in ast.walk(ast.parse(fonte)):
            if isinstance(no, ast.ImportFrom):
                self.assertNotIn("identity", no.module or "")
                self.assertNotIn("editing", no.module or "")
            if isinstance(no, ast.Import):
                for alias in no.names:
                    self.assertNotIn("identity", alias.name)
                    self.assertNotIn("editing", alias.name)

    def test_modulo_e_ascii_puro(self):
        fonte = (RAIZ / "src" / "character" / "nomes.py").read_bytes()
        fonte.decode("ascii")


if __name__ == "__main__":
    unittest.main()
