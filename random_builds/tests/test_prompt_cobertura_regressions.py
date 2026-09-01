"""O prompt tem que refletir a roleta INTEIRA - hoje e depois de crescer.

O que este arquivo trava:

1. TODA ROLETA CHEGA AO TEXTO. A lista de roletas e lida de
   `roulette_factory`, nao copiada aqui. Roleta nova (o pedido de "responsivo
   com o banco") cai neste teste com o nome do target e o que falta cadastrar,
   em vez de sair silenciosamente do prompt. Este e o coracao do arquivo.
2. NUMERO DE ROLETA VIRA DESENHO. dano, peso, critico, velocidade e mana
   chegam como faixa ([limite, rotulo] no config), nao so como numero cru.
3. IDENTIDADE E LITERAL, NAO REDACAO. Todo template que descreve o personagem
   cola o MESMO bloco de `blocos_identidade`; idem a arma. Foi reescrever a
   frase por slot que deu o cabelo branco no clipe e preto no payoff do
   generation_00020.
4. A VARIACAO SO MEXE NA MOLDURA. Trocar o seed muda cenario/luz/clima/angulo
   e NAO muda uma letra da identidade.
5. A MOLDURA E DETERMINISTICA. Mesma build, mesma moldura, em todo slot e no
   payoff - senao o payoff mostra uma arena que os dois clipes nao mostraram.
6. NADA E TRUNCADO. O texto cabe no teto do config com folga, porque o corte
   comeria justamente o negative prompt ("No text, no watermark...") que mora
   no fim.
7. AS 80 SKILLS E OS 12 ENCANTAMENTOS ESTAO TRADUZIDOS, em ASCII.

Rode de dentro de random_builds/:
    python -m pytest tests/test_prompt_cobertura_regressions.py -q
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from builds.generation.session_generator import SessionGenerator        # noqa: E402
from builds.identity import prompt as P                                 # noqa: E402
from builds.identity import slots                                       # noqa: E402
from builds.nf_bridge import loader as nf                               # noqa: E402
from builds.nf_bridge import roulette_factory as rf                     # noqa: E402

# Alvo de roleta -> campos de prompt que o representam. Quem mexe nas roletas
# mexe AQUI tambem: e esta tabela que o teste 1 cobra. Nao ha caso "esse alvo
# nao precisa aparecer" - se um dia houver, a entrada tem que ficar escrita
# com o motivo, nunca simplesmente sumir.
REPRESENTACAO = {
    "classe": ("CLASSE",),
    "personalidade": ("PERSONALIDADE",),
    "tamanho_cm": ("ALTURA", "PORTE"),
    "forca_x10": ("FORCA", "FISICO"),
    "mana_x10": ("MANA", "MANA_DESC"),
    "tipo": ("ARMA_TIPO",),
    "estilo": ("ARMA_ESTILO",),
    "raridade": ("RARIDADE", "ARTIGO_RARIDADE"),
    "encantamento": ("ENCANTAMENTO", "ENCANTAMENTO_VFX", "ELEMENTO", "AURA"),
    "habilidade": ("HABILIDADE_EN", "HABILIDADE_VFX"),
    "dano": ("DANO", "DANO_DESC"),
    "peso_x10": ("PESO", "PESO_DESC"),
    "critico_x10": ("CRITICO_DESC",),
    "velocidade_x100": ("VELOCIDADE", "VELOCIDADE_DESC"),
}

# Alvos numericos que NAO podem chegar so como numero: sem a faixa o modelo
# nao tem o que pintar com "0.81 attack speed".
PRECISA_DE_FAIXA = {
    "forca_x10": "FISICO", "mana_x10": "MANA_DESC", "dano": "DANO_DESC",
    "peso_x10": "PESO_DESC", "critico_x10": "CRITICO_DESC",
    "velocidade_x100": "VELOCIDADE_DESC", "tamanho_cm": "PORTE",
}

# Cada roleta tem que aparecer em pelo menos tantos templates. Tres e o piso
# de "esta no prompt de verdade", nao um numero bonito: o slot proprio, o
# payoff e a variante de payoff que descreve aquele lado em palavras.
MINIMO_DE_TEMPLATES = 3

SEEDS = (7, 11, 42, 99, 2024, 20260822, 314159, 777)

# Folga exigida entre o pior caso do catalogo e o teto de chars. Existe para o
# banco poder crescer (pedido "responsivo com o banco de dados") sem que o
# primeiro rotulo comprido corte o negative prompt em silencio.
FOLGA_MINIMA = 150

# De onde sai o valor MAIS LONGO que cada campo pode assumir. Numero e string
# fixa porque a roleta tem teto; o resto sai do proprio config, entao rotulo
# novo entra na conta sozinho.
FONTE_DO_PIOR = {
    "NOME": 40,  # nome gerado; 40 e o dobro do maior que ja saiu em outputs/
    "ARTIGO": "an", "ARTIGO_PERS": "an", "ARTIGO_RARIDADE": "an",
    "ALTURA": "2.20", "FORCA": "10.0", "MANA": "10.0",
    "DANO": "999", "PESO": "99.9", "VELOCIDADE": "9.99",
    "COR_HEX": "#ffffff",
    "GENERO": ("traducoes", "genero"),
    "SILHUETA": ("traducoes", "silhueta"),
    "CLASSE": ("traducoes", "classe"),
    "PERSONALIDADE": ("traducoes", "personalidade"),
    "ARMA_TIPO": ("traducoes", "tipo_arma"),
    "ARMA_ESTILO": ("traducoes", "estilo"),
    "RARIDADE": ("traducoes", "raridade"),
    "ELEMENTO": ("traducoes", "elemento"),
    "ENCANTAMENTO": ("traducoes", "encantamento"),
    "HABILIDADE_EN": ("traducoes", "habilidade"),
    "AURA": ("mapa", "aura"),
    "ENCANTAMENTO_VFX": ("mapa", "encantamento_vfx"),
    "HABILIDADE_VFX": ("mapa", "habilidade_vfx"),
    "COR": ("faixa", "cores"),
    "PORTE": ("faixa", "porte"), "FISICO": ("faixa", "fisico"),
    "MANA_DESC": ("faixa", "mana"), "DANO_DESC": ("faixa", "dano"),
    "PESO_DESC": ("faixa", "peso"), "CRITICO_DESC": ("faixa", "critico"),
    "VELOCIDADE_DESC": ("faixa", "velocidade"),
}


def _maior_valor(ajustes: dict, campo: str) -> str:
    fonte = FONTE_DO_PIOR[campo]
    if isinstance(fonte, int):
        return "M" * fonte
    if isinstance(fonte, str):
        return fonte
    origem, chave = fonte
    if origem == "traducoes":
        valores = ajustes["traducoes"][chave].values()
    elif origem == "mapa":
        valores = ajustes[chave].values()
    else:
        valores = [rotulo for _, rotulo in ajustes[chave]]
    return max((str(v) for v in valores), key=len)


def pior_caso(ajustes: dict) -> list[tuple[str, int, int]]:
    """[(caminho, tamanho no pior caso, teto)] de todo template.

    Pior caso = todo placeholder trocado pelo maior valor que o catalogo
    inteiro consegue devolver. E um limite superior pessimista (nem toda
    combinacao e possivel), que e exatamente o que se quer de um teto.
    """
    maiores = {c: _maior_valor(ajustes, c) for c in FONTE_DO_PIOR}
    for eixo, opcoes in (ajustes.get("moldura") or {}).items():
        if not eixo.startswith("_") and opcoes:
            maiores[eixo.upper()] = max(opcoes, key=len)
    teto_payoff = ajustes["prompt_max_chars"]["payoff"]
    saida = []
    for caminho, texto in todos_os_templates(ajustes).items():
        for campo, valor in maiores.items():
            texto = texto.replace("{" + campo + "}", valor)
        sobrando = P.PLACEHOLDER.findall(texto)
        if sobrando:
            raise AssertionError(
                f"{caminho} usa {sorted(set(sobrando))}: cadastre o campo em "
                "FONTE_DO_PIOR para ele entrar na conta do teto")
        grupo, _, chave = caminho.partition("/")
        if grupo == "prompts_payoff":
            limite = teto_payoff
        else:
            tipo = slots.IMAGEM if grupo == "prompts_imagem" else slots.VIDEO
            limite = P.limite_de_chars(ajustes, chave, tipo)
        saida.append((caminho, len(" ".join(texto.split())), limite))
    return saida


def gerar(seed: int) -> dict:
    return SessionGenerator().generate(
        seed=seed, generation_id=f"generation_{seed:05d}")


def alvos_das_roletas() -> list[str]:
    """A lista viva, tirada da fabrica de roletas - nunca uma copia."""
    alvos = []
    for bloco in (rf.character_roulettes(), rf.weapon_roulettes()):
        for roleta in bloco["roulettes"]:
            alvos.append(roleta["target"])
    return alvos


def todos_os_templates(ajustes: dict) -> dict:
    """{caminho no config: template}. Todo texto que vai para um provedor."""
    saida = {}
    for grupo in ("prompts", "prompts_imagem", "prompts_payoff"):
        for chave, texto in (ajustes.get(grupo) or {}).items():
            saida[f"{grupo}/{chave}"] = texto
    return saida


def todos_os_textos(generation: dict, ajustes: dict) -> dict:
    """{caminho: prompt renderizado}, do jeito que o worker manda."""
    saida = {}
    for slot in slots.JOBS:
        saida[f"slot/{slot}"] = P.build_prompt(generation, ajustes, slot)
    saida["slot/character#video"] = P.build_prompt(
        generation, ajustes, slots.CHARACTER, tipo=slots.VIDEO)
    saida["slot/weapon#video"] = P.build_prompt(
        generation, ajustes, slots.WEAPON, tipo=slots.VIDEO)
    for chave, refs in (("ambas", (slots.CHARACTER, slots.WEAPON)),
                        ("so_personagem", (slots.CHARACTER,)),
                        ("so_arma", (slots.WEAPON,))):
        saida[f"payoff/{chave}"] = P.para_payoff(generation, ajustes, refs)
    return saida


class CoberturaDeRoletaTests(unittest.TestCase):
    """1 e 2: nenhuma roleta fica de fora do texto."""

    @classmethod
    def setUpClass(cls):
        cls.ajustes = P.config.settings()
        cls.templates = todos_os_templates(cls.ajustes)
        cls.generation = gerar(20260822)
        cls.valores = P.campos(cls.generation, cls.ajustes)

    def test_todo_alvo_de_roleta_tem_campo_de_prompt(self):
        """Roleta nova sem representacao para AQUI, nao no video publicado."""
        for alvo in alvos_das_roletas():
            self.assertIn(
                alvo, REPRESENTACAO,
                f"a roleta de alvo {alvo!r} nao chega ao prompt. Cadastre em "
                "tests/test_prompt_cobertura_regressions.py:REPRESENTACAO o "
                "campo que a representa, crie o campo em prompt.campos() e "
                "use-o em config/identity.json:prompts*")

    def test_a_tabela_nao_tem_alvo_fantasma(self):
        """Alvo que sumiu da roleta tem que sumir da tabela junto."""
        vivos = set(alvos_das_roletas())
        for alvo in REPRESENTACAO:
            self.assertIn(alvo, vivos,
                          f"{alvo!r} nao e mais alvo de roleta nenhuma")

    def test_todo_campo_da_tabela_existe_em_campos(self):
        for alvo, campos in REPRESENTACAO.items():
            for campo in campos:
                self.assertIn(campo, self.valores,
                              f"{alvo}: prompt.campos() nao produz {campo}")

    def test_todo_alvo_aparece_em_pelo_menos_tres_templates(self):
        for alvo, campos in REPRESENTACAO.items():
            usando = [caminho for caminho, texto in self.templates.items()
                      if any("{" + c + "}" in texto for c in campos)]
            self.assertGreaterEqual(
                len(usando), MINIMO_DE_TEMPLATES,
                f"{alvo} so aparece em {usando or 'NENHUM template'}")

    def test_todo_alvo_aparece_no_TEXTO_final(self):
        """Estar no template nao basta: o valor tem que sobreviver ao render.

        Placeholder trocado por string vazia, ou frase cortada pelo teto de
        chars, sumiria com a roleta sem quebrar nada.
        """
        for seed in SEEDS:
            generation = gerar(seed)
            valores = P.campos(generation, self.ajustes)
            juntos = " || ".join(todos_os_textos(generation, self.ajustes).values())
            for alvo, campos in REPRESENTACAO.items():
                achados = [c for c in campos
                           if str(valores[c]).strip() and str(valores[c]) in juntos]
                self.assertTrue(
                    achados,
                    f"seed {seed}: nenhum campo de {alvo} "
                    f"({', '.join(campos)}) sobreviveu ate o texto final")

    def test_numero_de_roleta_nao_vai_cru_sem_a_faixa(self):
        for alvo, campo_faixa in PRECISA_DE_FAIXA.items():
            self.assertIn(campo_faixa, REPRESENTACAO[alvo])
            rotulo = str(self.valores[campo_faixa])
            self.assertTrue(rotulo.strip(),
                            f"{alvo}: a faixa {campo_faixa} veio vazia")
            self.assertFalse(rotulo.replace(".", "").isdigit(),
                             f"{alvo}: {campo_faixa} devolveu numero, nao desenho")

    def test_a_faixa_cobre_a_roleta_INTEIRA(self):
        """Ponta de faixa faltando devolveria o padrao, apagando o extremo."""
        tabelas = {"dano": "dano", "peso_x10": "peso", "critico_x10": "critico",
                   "velocidade_x100": "velocidade", "mana_x10": "mana",
                   "forca_x10": "fisico", "tamanho_cm": "porte"}
        escala = {"peso_x10": 10.0, "critico_x10": 10.0, "mana_x10": 10.0,
                  "forca_x10": 10.0, "velocidade_x100": 100.0, "tamanho_cm": 100.0,
                  "dano": 1.0}
        por_alvo = {r["target"]: r for bloco in (rf.character_roulettes(),
                                                 rf.weapon_roulettes())
                    for r in bloco["roulettes"]}
        for alvo, chave in tabelas.items():
            roleta = por_alvo[alvo]
            tabela = self.ajustes[chave]
            teto = max(float(limite) for limite, _ in tabela)
            maximo = max(roleta.get("eval_max", roleta["max"]),
                         roleta["max"]) / escala[alvo]
            self.assertGreaterEqual(
                teto, maximo,
                f"a tabela {chave} para em {teto} e a roleta {alvo} chega a "
                f"{maximo}: o topo da roleta cairia no rotulo padrao")


class BlocoDeIdentidadeTests(unittest.TestCase):
    """3: identidade e copiada, nunca reescrita."""

    @classmethod
    def setUpClass(cls):
        cls.ajustes = P.config.settings()
        cls.templates = todos_os_templates(cls.ajustes)
        cls.blocos = cls.ajustes["blocos_identidade"]

    def test_o_config_declara_os_tres_blocos(self):
        for chave in ("personagem", "arma_forma", "arma_movimento"):
            self.assertTrue(self.blocos.get(chave), chave)

    def test_quem_descreve_o_personagem_usa_o_BLOCO(self):
        alvo = self.blocos["personagem"]
        for caminho, texto in self.templates.items():
            if "{NOME}" in texto:
                self.assertIn(alvo, texto,
                              f"{caminho} reescreve o personagem em vez de "
                              "colar blocos_identidade.personagem")

    def test_quem_descreve_a_arma_usa_o_BLOCO(self):
        forma, movimento = self.blocos["arma_forma"], self.blocos["arma_movimento"]
        for caminho, texto in self.templates.items():
            if "{ARMA_ESTILO}" in texto:
                self.assertIn(forma, texto, caminho)
            if "{HABILIDADE_EN}" in texto:
                self.assertIn(movimento, texto, caminho)

    def test_a_imagem_da_arma_nao_promete_movimento(self):
        """Still nao mostra velocidade de ataque nem habilidade disparando.

        Pedir isso a uma imagem so gasta atencao do modelo com o que ele nao
        consegue entregar - e o texto da imagem deixa de ser um prefixo do
        texto do video.
        """
        texto = self.ajustes["prompts_imagem"]["weapon"]
        self.assertIn(self.blocos["arma_forma"], texto)
        self.assertNotIn(self.blocos["arma_movimento"], texto)

    def test_o_prompt_mais_rico_nao_estraga_a_REVELACAO(self):
        """Prompt vasto nao pode antecipar o que a roleta ainda vai revelar.

        O clipe do personagem sai antes da arma existir na tela; o da arma sai
        sem dono. Um bloco de identidade colado no template errado entregaria
        o payoff no primeiro segundo do video.
        """
        for seed in SEEDS:
            generation = gerar(seed)
            valores = P.campos(generation, self.ajustes)
            for tipo in (slots.IMAGEM, slots.VIDEO):
                personagem = P.build_prompt(generation, self.ajustes,
                                            slots.CHARACTER, tipo).lower()
                arma = P.build_prompt(generation, self.ajustes,
                                      slots.WEAPON, tipo).lower()
                for campo in ("ARMA_ESTILO", "HABILIDADE_EN"):
                    self.assertNotIn(str(valores[campo]).lower(), personagem,
                                     f"seed {seed}: {campo} vazou no personagem")
                for campo in ("NOME", "CLASSE"):
                    self.assertNotIn(str(valores[campo]).lower(), arma,
                                     f"seed {seed}: {campo} vazou na arma")

    def test_os_tres_slots_descrevem_a_MESMA_pessoa(self):
        for seed in SEEDS:
            generation = gerar(seed)
            valores = P.campos(generation, self.ajustes)
            bloco = self.blocos["personagem"]
            for chave, valor in valores.items():
                bloco = bloco.replace("{" + chave + "}", str(valor))
            textos = todos_os_textos(generation, self.ajustes)
            descrevem = [c for c, t in textos.items()
                         if str(valores["NOME"]) in t]
            self.assertGreaterEqual(len(descrevem), 3, f"seed {seed}")
            for caminho in descrevem:
                self.assertIn(bloco, textos[caminho],
                              f"seed {seed}: {caminho} descreve outra pessoa")


class MolduraTests(unittest.TestCase):
    """4 e 5: a variacao mora fora da identidade e nao e sorteada na hora."""

    @classmethod
    def setUpClass(cls):
        cls.ajustes = P.config.settings()
        cls.eixos = [e for e in (cls.ajustes.get("moldura") or {})
                     if not e.startswith("_")]

    def test_a_moldura_e_a_mesma_em_toda_chamada(self):
        generation = gerar(42)
        primeira = P.moldura(generation, self.ajustes)
        for _ in range(5):
            self.assertEqual(primeira, P.moldura(generation, self.ajustes))
        self.assertEqual(sorted(e.upper() for e in self.eixos),
                         sorted(primeira))

    def test_a_moldura_e_a_mesma_em_TODO_slot_da_build(self):
        """Moldura por slot faria o payoff mostrar outra arena."""
        generation = gerar(42)
        moldura = P.moldura(generation, self.ajustes)
        textos = todos_os_textos(generation, self.ajustes)
        for eixo, valor in moldura.items():
            usando = [c for c, t in textos.items() if valor in t]
            self.assertGreaterEqual(len(usando), 3, f"{eixo} em {usando}")

    def test_seeds_diferentes_dao_molduras_diferentes(self):
        vistas = {tuple(sorted(P.moldura(gerar(s), self.ajustes).items()))
                  for s in range(120)}
        self.assertGreater(len(vistas), 100,
                           f"so {len(vistas)} molduras em 120 builds")

    def test_toda_escolha_saiu_do_config(self):
        tabelas = self.ajustes["moldura"]
        for seed in SEEDS:
            for eixo, valor in P.moldura(gerar(seed), self.ajustes).items():
                self.assertIn(valor, tabelas[eixo.lower()], f"{seed}/{eixo}")

    def test_trocar_o_seed_NAO_mexe_na_identidade(self):
        """O contrato inteiro: a moldura muda, o personagem e a arma nao."""
        base = gerar(42)
        outra = json.loads(json.dumps(base))
        outra["seed"] = base["seed"] + 1
        antes = P.campos(base, self.ajustes)
        depois = P.campos(outra, self.ajustes)
        eixos = {e.upper() for e in self.eixos}
        mudou = {k for k in antes if str(antes[k]) != str(depois[k])}
        self.assertTrue(mudou & eixos, "a moldura nao mudou com outro seed")
        self.assertFalse(mudou - eixos,
                         f"o seed vazou para fora da moldura: {sorted(mudou - eixos)}")

    def test_geracao_sem_seed_ainda_tem_moldura_estavel(self):
        """Build antiga nao pode ter arena diferente a cada execucao."""
        antiga = gerar(42)
        antiga.pop("seed")
        self.assertEqual(P.moldura(antiga, self.ajustes),
                         P.moldura(antiga, self.ajustes))
        self.assertTrue(all(P.moldura(antiga, self.ajustes).values()))

    def test_eixo_sem_opcao_nao_vira_texto_vazio(self):
        """Melhor KeyError alto do que mandar 'Setting: ;' para o provedor."""
        ajustes = json.loads(json.dumps(self.ajustes))
        ajustes["moldura"]["cenario"] = []
        with self.assertRaises(KeyError):
            P.build_prompt(gerar(42), ajustes, slots.CHARACTER)


class TetoDeCharsTests(unittest.TestCase):
    """6: nada e cortado - o corte comeria o negative prompt."""

    @classmethod
    def setUpClass(cls):
        cls.ajustes = P.config.settings()

    def test_todo_prompt_cabe_no_teto(self):
        """O teto cobrado e o da midia do TEMPLATE que saiu.

        Cobrar `limite_de_chars(slot, tipo_pedido)` era tautologia: build_prompt
        corta com esse mesmo numero, entao o teste passava por construcao. Pior,
        passava justamente no caso quebrado - `character_weapon` em imagem cai
        no template de video (1600+ chars) e levava o teto de imagem (1100),
        perdendo o negative prompt inteiro. Aqui o teto vem da midia REAL.
        """
        for seed in SEEDS:
            generation = gerar(seed)
            for slot in slots.JOBS:
                for tipo in (slots.IMAGEM, slots.VIDEO):
                    texto = P.build_prompt(generation, self.ajustes, slot, tipo)
                    saiu = P.midia_do_template(self.ajustes, slot, tipo)
                    limite = P.limite_de_chars(self.ajustes, slot, saiu)
                    self.assertLessEqual(len(texto), limite,
                                         f"seed {seed} {slot}/{tipo}")
                    # A pergunta que importa: nada foi cortado de verdade.
                    self.assertIn("no watermark", texto,
                                  f"seed {seed} {slot}/{tipo} perdeu o negative")

    def test_um_teto_apertado_corta_em_fim_de_FRASE_e_nao_no_decimal(self):
        """`rfind('.')` cru cortava dentro de "7.3 strength" e ninguem via.

        O teste antigo do negative prompt validava "nao terminou no meio" com
        endswith("."), que "muscled at 7." satisfaz - a defesa e o detector
        tinham o mesmo furo.
        """
        texto = ("Portrait of X, heavily muscled at 7.3 strength, 1.86 m tall. "
                 "No text, no watermark.")
        for limite in range(45, len(texto)):
            saida = P._cortar(texto, limite)
            if saida.endswith("."):
                resto = texto[len(saida):]
                self.assertTrue(resto == "" or resto[0].isspace(),
                                f"limite {limite}: cortou em {saida[-8:]!r}")

    def test_o_negative_prompt_sobrevive(self):
        """Se algo foi truncado, o que sumiu foi justamente o fim do texto."""
        for seed in SEEDS:
            generation = gerar(seed)
            for caminho, texto in todos_os_textos(generation, self.ajustes).items():
                self.assertIn("no watermark", texto, f"seed {seed} {caminho}")
                self.assertTrue(texto.rstrip().endswith("."),
                                f"seed {seed} {caminho} terminou no meio")

    def test_o_payoff_tambem_tem_teto(self):
        """Ate esta mudanca `prompts_payoff` nao passava por corte nenhum."""
        teto = self.ajustes["prompt_max_chars"]["payoff"]
        for seed in SEEDS:
            generation = gerar(seed)
            for refs in ((slots.CHARACTER, slots.WEAPON), (slots.CHARACTER,),
                         (slots.WEAPON,)):
                self.assertLessEqual(
                    len(P.para_payoff(generation, self.ajustes, refs)), teto)

    def test_o_PIOR_CASO_do_catalogo_inteiro_cabe(self):
        """A build mais longa que o catalogo consegue produzir, nao a sorteada.

        Sortear seeds so prova o que ja saiu. O pedido de "responsivo ao
        banco" garante que vem rotulo novo: uma skill de nome comprido com o
        estilo mais comprido e a raridade mais comprida na mesma arma passaria
        do teto sem nenhuma build atual reclamar - e o corte comeria o
        negative prompt.
        """
        for caminho, tamanho, limite in pior_caso(self.ajustes):
            self.assertLessEqual(tamanho, limite, f"{caminho} estoura o teto")
            self.assertGreaterEqual(
                limite - tamanho, FOLGA_MINIMA,
                f"{caminho}: pior caso {tamanho} contra teto {limite}, so "
                f"{limite - tamanho} de folga. Suba o teto em "
                "config/identity.json:prompt_max_chars CONSCIENTEMENTE.")


class TraducaoTests(unittest.TestCase):
    """7: o catalogo inteiro traduzido, e em ASCII."""

    @classmethod
    def setUpClass(cls):
        cls.ajustes = P.config.settings()

    def test_toda_skill_rolavel_tem_nome_e_desenho(self):
        traducoes = self.ajustes["traducoes"]["habilidade"]
        vfx = self.ajustes["habilidade_vfx"]
        for skill in nf.skills_rolaveis():
            self.assertIn(skill, traducoes)
            self.assertIn(skill, vfx)
        self.assertIn("DEFAULT", vfx, "sem DEFAULT, skill nova ficaria sem VFX")

    def test_todo_encantamento_tem_nome_e_desenho(self):
        traducoes = self.ajustes["traducoes"]["encantamento"]
        vfx = self.ajustes["encantamento_vfx"]
        for enc in nf.LISTA_ENCANTAMENTOS:
            self.assertIn(enc, traducoes)
            self.assertIn(enc, vfx)
        self.assertIn("DEFAULT", vfx)

    def test_os_quatro_encantamentos_de_FISICO_nao_saem_iguais(self):
        """Velocidade, Critico, Penetracao e Execucao colapsam no mesmo
        elemento. Sem ENCANTAMENTO_VFX eram o mesmo pixel."""
        colapsam = [e for e in nf.LISTA_ENCANTAMENTOS
                    if nf.elemento_do_encantamento(e) == "FISICO"]
        self.assertGreaterEqual(len(colapsam), 4)
        desenhos = {self.ajustes["encantamento_vfx"][e] for e in colapsam}
        self.assertEqual(len(colapsam), len(desenhos))

    def test_o_texto_que_vai_ao_modelo_e_ASCII(self):
        """Prompt e em ingles; acento aqui e sinal de traducao faltando."""
        grupos = [self.ajustes["traducoes"][g] for g in
                  ("classe", "personalidade", "tipo_arma", "raridade",
                   "elemento", "estilo", "habilidade", "encantamento")]
        grupos += [self.ajustes["aura"], self.ajustes["habilidade_vfx"],
                   self.ajustes["encantamento_vfx"]]
        for grupo in grupos:
            for chave, valor in grupo.items():
                self.assertTrue(valor.isascii(), f"{chave} -> {valor!r}")
        for eixo, opcoes in self.ajustes["moldura"].items():
            for opcao in opcoes:
                self.assertTrue(opcao.isascii(), f"{eixo} -> {opcao!r}")

    def test_o_CODIGO_do_prompt_e_ascii_puro(self):
        """Console do projeto e cp1252: acento em .py quebra a saida.

        O texto que o modelo le e ingles e o comentario e portugues SEM acento,
        entao o arquivo inteiro tem que ser ASCII. Um travessao colado de um
        editor passa despercebido ate alguem rodar no terminal errado.
        """
        fonte = (ROOT / "builds" / "identity" / "prompt.py").read_text(encoding="utf-8")
        fora = sorted({c for c in fonte if not c.isascii()})
        self.assertFalse(fora, f"src/identity/prompt.py tem nao-ASCII: {fora}")

    def test_placeholder_orfao_continua_estourando(self):
        """Campo novo no template sem campo novo em campos() = KeyError."""
        ajustes = json.loads(json.dumps(self.ajustes))
        ajustes["prompts"]["character"] += " {CAMPO_QUE_NAO_EXISTE}"
        with self.assertRaises(KeyError):
            P.build_prompt(gerar(42), ajustes, slots.CHARACTER, slots.VIDEO)


class SilhuetaTests(unittest.TestCase):
    """A forma fisica do TIPO domina o prompt da arma (caso da build 36).

    O que aconteceu: a arma sorteada era Orbital/Sentinelas e o prompt dizia
    isso UMA vez - mas as tabelas de dano/critico/peso diziam "cutting edge",
    "razor edge", "two-hand grip", "tip to pommel" seis vezes. O modelo desenha
    o que for dito mais vezes: saiu uma adaga. A regra agora e que as tabelas
    numericas sao neutras de forma e a silhueta do tipo diz o que o objeto E.
    """

    # As frases exatas que produziram a adaga. Vocabulario de lamina so pode
    # existir dentro da SILHUETA de um tipo laminado - nunca nas tabelas.
    FRASES_DE_LAMINA = (
        "tip to pommel", "cutting edge", "blade and grip", "two-hand grip",
        "razor edge", "honed edge", "wear on the edge", "in the grip",
        "along the edge", "off the blade", "around the edge", "killing edge",
        "swung with the body", "in one hand", "thick-shafted",
    )

    def test_tabelas_numericas_sao_neutras_de_forma(self):
        ajustes = P.config.settings()
        for faixa in ("dano", "critico", "peso", "velocidade"):
            for _limite, rotulo in ajustes[faixa]:
                for frase in self.FRASES_DE_LAMINA:
                    self.assertNotIn(frase, rotulo,
                                     f"a faixa {faixa!r} volta a descrever "
                                     f"lamina: {rotulo!r}")

    def test_todo_tipo_do_banco_tem_silhueta(self):
        silhuetas = P.config.settings()["traducoes"]["silhueta"]
        for tipo in nf.LISTA_TIPOS_ARMA:
            self.assertIn(tipo, silhuetas, tipo)
            self.assertTrue(silhuetas[tipo].strip(), tipo)

    def test_arma_orbital_nunca_vira_lamina(self):
        """O prompt de uma Orbital descreve construtos flutuando, nao adaga."""
        generation = None
        for seed in range(1, 300):
            g = gerar(seed)
            if g["weapon"].get("tipo") == "Orbital":
                generation = g
                break
        self.assertIsNotNone(generation, "nenhuma Orbital em 300 seeds")
        for tipo_midia in ("imagem", "video"):
            texto = P.build_prompt(generation, slot="weapon",
                                        tipo=tipo_midia)
            self.assertIn("hovering in mid-air", texto, tipo_midia)
            for frase in self.FRASES_DE_LAMINA:
                self.assertNotIn(frase, texto,
                                 f"{tipo_midia}: {frase!r} num prompt de "
                                 "arma orbital")

    def test_tipo_novo_sem_silhueta_degrada_sem_contradizer(self):
        """Pedido 2 aplicado a silhueta: tipo desconhecido nao vira lamina."""
        generation = gerar(4242)
        generation["weapon"]["tipo"] = "Sopro"
        texto = P.build_prompt(generation, slot="weapon", tipo="imagem")
        self.assertIn("its full form clearly visible", texto)
        for frase in self.FRASES_DE_LAMINA:
            self.assertNotIn(frase, texto, frase)


if __name__ == "__main__":
    unittest.main()
