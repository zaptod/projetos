# -*- coding: utf-8 -*-
"""Contratos dos experimentos e da metrica por canal (11/09/2026).

O que motivou: toda mudanca de edicao ate aqui foi palpite. Pior, a prova
nao existia nem em tese — medido em 11/09/2026, o ledger de builds tinha 18
uploads sem `youtube_id` e o de historias tinha TODOS os 30 assim, porque o
caminho por navegador quase nunca captura o link do Studio. `atualizar()`
so conhecia o canal de builds, entao nenhuma historia jamais teve uma
metrica. Um experimento sobre esses dados mediria o vazio.

O que este arquivo trava:

1. Sem experimento em curso, `aplicar` devolve o config INTACTO — o caminho
   normal da producao nao copia, nao grava e nao muda nada.
2. Com experimento, o ajuste entra por chave pontilhada numa COPIA: o
   config original nao pode vazar o braco para o video seguinte.
3. O rodizio alterna e PERSISTE entre processos.
4. Um experimento de ajuste por canal; observacional nao disputa essa vaga
   nem entra no sorteio.
5. A confianca le os DOIS PRIMEIROS bracos, nao o minimo global.
6. A metrica sabe de canal, e `builds` continua saindo das globais que tres
   suites trocam por tmpdir.
7. `reconciliar` preenche o `youtube_id` que faltou, casando pelo titulo.

Rode de dentro de random_builds/:
    python -m pytest tests/test_experimentos_regressions.py -q
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from builds import experimentos as X
from builds.publicar import metricas


class BaseIsolada(unittest.TestCase):
    """Registro e atribuicoes num tmpdir: o experimento de teste nao pode
    entrar na producao de ninguem — e o contrario tambem nao."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        raiz = Path(self._tmp.name)
        self._antes = (X.PASTA, X.REGISTRO, X.ATRIBUICOES, X.PRODUCOES)
        X.PASTA = raiz
        X.REGISTRO = raiz / "experimentos.json"
        X.ATRIBUICOES = raiz / "atribuicoes.jsonl"
        X.PRODUCOES = raiz / "producoes.json"
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        (X.PASTA, X.REGISTRO, X.ATRIBUICOES, X.PRODUCOES) = self._antes
        self._tmp.cleanup()


class AplicarTests(BaseIsolada):

    def test_sem_experimento_o_config_sai_intacto(self):
        """O caminho normal da producao. Se `aplicar` copiasse sempre, cada
        render pagaria uma serializacao do config inteiro por nada."""
        config = {"audio": {"trilha_procedural": True}}
        saida, marca = X.aplicar("historias", config)
        self.assertIsNone(marca)
        self.assertIs(config, saida)

    def test_o_ajuste_entra_por_chave_pontilhada(self):
        exp = X.criar("Trilha", "muda?", "historias", [
            {"nome": "com", "ajuste": {"audio.trilha_procedural": True}},
            {"nome": "sem", "ajuste": {"audio.trilha_procedural": False}}])
        X.ativar(exp["id"])
        config = {"audio": {"trilha_procedural": True, "ducking": True}}
        saida, marca = X.aplicar("historias", config)
        self.assertEqual("com", marca["braco"])
        self.assertTrue(saida["audio"]["trilha_procedural"])
        # o que o braco NAO menciona continua de pe
        self.assertTrue(saida["audio"]["ducking"])

    def test_o_config_original_nao_e_tocado(self):
        """Mutacao no lugar faria o braco vazar para a parte seguinte da
        mesma historia, e a atribuicao passaria a mentir sem deixar rastro."""
        exp = X.criar("Trilha", "muda?", "historias", [
            {"nome": "com", "ajuste": {"audio.trilha_procedural": True}},
            {"nome": "sem", "ajuste": {"audio.trilha_procedural": False}}])
        X.ativar(exp["id"])
        config = {"audio": {"trilha_procedural": True}}
        X.aplicar("historias", config)           # braco "com"
        saida, _ = X.aplicar("historias", config)  # braco "sem"
        self.assertFalse(saida["audio"]["trilha_procedural"])
        self.assertTrue(config["audio"]["trilha_procedural"],
                        "o config de quem chamou foi alterado no lugar")

    def test_chave_que_ainda_nao_existe_e_criada(self):
        exp = X.criar("Trilha", "qual?", "historias", [
            {"nome": "a", "ajuste": {"audio.trilha_arquivo": "a.mp3"}},
            {"nome": "b", "ajuste": {"audio.trilha_arquivo": "b.mp3"}}])
        X.ativar(exp["id"])
        saida, _ = X.aplicar("historias", {})
        self.assertEqual("a.mp3", saida["audio"]["trilha_arquivo"])


class UmaProducaoUmBracoTests(BaseIsolada):
    """Re-renderizar nao pode sortear de novo.

    Medido na `historia_00008` em 11/09/2026: a primeira renderizacao pegou
    'trilha atual', o re-render (feito porque uma imagem foi refeita) pegou
    'instrumental', e o seguinte voltou para 'trilha atual'. O mesmo video com
    dois bracos no ledger, o som trocando a cada passada, e o contador do
    rodizio queimado tres vezes por uma historia so — o que desalinha o
    sorteio de TODAS as historias seguintes.
    """

    def setUp(self):
        super().setUp()
        exp = X.criar("Trilha", "muda?", "historias", [
            {"nome": "com", "ajuste": {"audio.trilha_arquivo": "a.mp3"}},
            {"nome": "sem", "ajuste": {"audio.trilha_arquivo": "b.mp3"}}])
        X.ativar(exp["id"])
        self.exp_id = exp["id"]

    def test_o_re_render_mantem_o_braco_da_primeira_vez(self):
        primeiro, _ = None, None
        _, primeiro = X.aplicar("historias", {}, "historia_00008")
        _, segundo = X.aplicar("historias", {}, "historia_00008")
        self.assertEqual(primeiro["braco"], segundo["braco"])

    def test_o_re_render_devolve_o_mesmo_ajuste(self):
        cfg1, _ = X.aplicar("historias", {}, "historia_00008")
        cfg2, _ = X.aplicar("historias", {}, "historia_00008")
        self.assertEqual(cfg1["audio"]["trilha_arquivo"],
                         cfg2["audio"]["trilha_arquivo"])

    def test_o_re_render_nao_queima_a_vez_do_rodizio(self):
        X.aplicar("historias", {}, "historia_00008")
        X.aplicar("historias", {}, "historia_00008")
        X.aplicar("historias", {}, "historia_00008")
        _, outra = X.aplicar("historias", {}, "historia_00009")
        self.assertEqual("sem", outra["braco"],
                         "a historia seguinte pegou o braco errado porque o "
                         "re-render consumiu a vez")

    def test_historias_diferentes_alternam(self):
        bracos = [X.aplicar("historias", {}, f"historia_{i:05d}")[1]["braco"]
                  for i in range(1, 5)]
        self.assertEqual(["com", "sem", "com", "sem"], bracos)

    def test_sem_chave_o_comportamento_antigo_continua(self):
        """Um canal que ainda nao passa identidade nao pode quebrar."""
        _, um = X.aplicar("historias", {})
        _, dois = X.aplicar("historias", {})
        self.assertNotEqual(um["braco"], dois["braco"])


class RodizioTests(BaseIsolada):

    def _dois_bracos(self):
        exp = X.criar("T", "?", "historias", [
            {"nome": "a", "ajuste": {}}, {"nome": "b", "ajuste": {}}])
        X.ativar(exp["id"])
        return exp["id"]

    def test_alterna_e_da_a_volta(self):
        """Rodizio, e nao periodo: alternando video a video, o crescimento do
        canal e a hora da postagem caem igualmente nos dois lados."""
        self._dois_bracos()
        saidas = [X.sortear("historias")["braco"] for _ in range(5)]
        self.assertEqual(["a", "b", "a", "b", "a"], saidas)

    def test_a_vez_sobrevive_ao_processo(self):
        """O contador mora no disco: cada render e um processo novo, e um
        contador em memoria daria sempre o primeiro braco."""
        exp_id = self._dois_bracos()
        X.sortear("historias")
        self.assertEqual(1, X.carregar()[exp_id]["proximo"])

    def test_observacional_nao_entra_no_sorteio(self):
        X.ativar(X.criar("Formato", "?", "builds", tipo="observacional",
                         campo="origem")["id"])
        self.assertIsNone(X.sortear("builds"))

    def test_so_um_ajuste_por_canal(self):
        self._dois_bracos()
        outro = X.criar("Voz", "?", "historias", [
            {"nome": "x", "ajuste": {}}, {"nome": "y", "ajuste": {}}])
        with self.assertRaises(X.ExperimentoInvalido) as caso:
            X.ativar(outro["id"])
        self.assertIn("ja esta rodando", str(caso.exception))

    def test_observacionais_convivem(self):
        """Eles nao mexem na producao: dez ao mesmo tempo nao se atrapalham."""
        X.ativar(X.criar("A", "?", "builds", tipo="observacional",
                         campo="origem")["id"])
        segundo = X.criar("B", "?", "builds", tipo="observacional",
                          campo="variante")
        X.ativar(segundo["id"])
        self.assertEqual("rodando", X.carregar()[segundo["id"]]["estado"])


class DefinicaoTests(BaseIsolada):

    def test_um_braco_so_e_recusado(self):
        with self.assertRaises(X.ExperimentoInvalido) as caso:
            X.criar("T", "?", "historias", [{"nome": "unico", "ajuste": {}}])
        self.assertIn("DOIS", str(caso.exception))

    def test_bracos_nao_mudam_depois_de_produzir(self):
        """Trocar o ajuste no meio faria dois videos diferentes carregarem o
        mesmo rotulo, e o resultado somaria os dois sem avisar."""
        exp = X.criar("T", "?", "historias", [
            {"nome": "a", "ajuste": {}}, {"nome": "b", "ajuste": {}}])
        X.ativar(exp["id"])
        X.atribuir(X.sortear("historias"), "historia_00001:celular:p01")
        with self.assertRaises(X.ExperimentoInvalido):
            X.editar(exp["id"], bracos=[{"nome": "c", "ajuste": {}},
                                        {"nome": "d", "ajuste": {}}])

    def test_campo_observavel_invalido_e_recusado(self):
        with self.assertRaises(X.ExperimentoInvalido):
            X.criar("T", "?", "builds", tipo="observacional", campo="inventado")

    def test_marcar_a_mao_recusa_braco_que_nao_existe(self):
        exp = X.criar("T", "?", "historias", [
            {"nome": "a", "ajuste": {}}, {"nome": "b", "ajuste": {}}])
        with self.assertRaises(X.ExperimentoInvalido):
            X.marcar_a_mao(exp["id"], "z", ["historia_00001:celular:p01"])

    def test_marcar_a_mao_nao_duplica(self):
        exp = X.criar("T", "?", "historias", [
            {"nome": "a", "ajuste": {}}, {"nome": "b", "ajuste": {}}])
        alvo = ["historia_00001:celular:p01"]
        self.assertEqual(1, X.marcar_a_mao(exp["id"], "a", alvo))
        self.assertEqual(0, X.marcar_a_mao(exp["id"], "a", alvo))


class ReRenderTests(BaseIsolada):
    """Re-renderizar uma parte nao pode fazer o video contar duas vezes."""

    def setUp(self):
        super().setUp()
        self.exp = X.criar("T", "?", "historias", [
            {"nome": "a", "ajuste": {}}, {"nome": "b", "ajuste": {}}])
        X.ativar(self.exp["id"])

    def _resultado(self):
        # Sem metrica nenhuma no caminho: o que se mede aqui e a CONTAGEM de
        # videos por braco, nao a retencao deles.
        original = X._metricas_por_video
        X._metricas_por_video = lambda canal: {}
        try:
            return X.resultado(self.exp["id"])
        finally:
            X._metricas_por_video = original

    def test_o_mesmo_video_conta_uma_vez_so(self):
        alvo = "historia_00008:celular:p01"
        X.atribuir({"experimento": self.exp["id"], "braco": "a"}, alvo)
        X.atribuir({"experimento": self.exp["id"], "braco": "b"}, alvo)
        total = sum(b["videos"] for b in self._resultado()["bracos"])
        self.assertEqual(1, total, "o mesmo mp4 entrou nos dois bracos")

    def test_vale_a_ultima_passada(self):
        """O arquivo no disco saiu do braco da ULTIMA renderizacao."""
        alvo = "historia_00008:celular:p01"
        X.atribuir({"experimento": self.exp["id"], "braco": "a"}, alvo)
        X.atribuir({"experimento": self.exp["id"], "braco": "b"}, alvo)
        por_nome = {b["nome"]: b["videos"] for b in self._resultado()["bracos"]}
        self.assertEqual(0, por_nome["a"])
        self.assertEqual(1, por_nome["b"])

    def test_videos_diferentes_continuam_somando(self):
        for i, braco in enumerate(("a", "b", "a")):
            X.atribuir({"experimento": self.exp["id"], "braco": braco},
                       f"historia_00008:celular:p{i + 1:02d}")
        por_nome = {b["nome"]: b["videos"] for b in self._resultado()["bracos"]}
        self.assertEqual({"a": 2, "b": 1}, por_nome)


class ConfiancaTests(unittest.TestCase):
    """O rotulo tem que falar dos dois bracos que estao sendo COMPARADOS."""

    @staticmethod
    def _braco(nome, medidos, valor):
        return {"nome": nome, "videos": medidos, "medidos": medidos,
                "views": 0, "views_por_dia": valor, "retencao": valor}

    def test_um_braco_minusculo_no_fim_nao_derruba_a_leitura(self):
        """Medido no canal: quatro formatos no eixo, `torneio` com 1 video.
        Olhando o minimo global, `build` (32) x `estreia` (10) com 83% de
        diferenca saia como 'insuficiente' — e era o achado mais forte."""
        bracos = [self._braco("build", 32, 38.5), self._braco("estreia", 10, 6.4),
                  self._braco("torneio", 1, 0.0)]
        rotulo, recado = X._confianca(bracos, "retencao")
        self.assertEqual("indicio", rotulo)
        self.assertIn("build x estreia", recado)

    def test_poucos_videos_nos_dois_do_topo_e_insuficiente(self):
        bracos = [self._braco("a", 3, 20.0), self._braco("b", 40, 5.0)]
        self.assertEqual("insuficiente", X._confianca(bracos, "retencao")[0])

    def test_diferenca_pequena_e_empate(self):
        bracos = [self._braco("a", 20, 10.0), self._braco("b", 20, 9.5)]
        self.assertEqual("empate", X._confianca(bracos, "retencao")[0])

    def test_muito_video_e_muita_diferenca_e_claro(self):
        bracos = [self._braco("a", 20, 40.0), self._braco("b", 20, 10.0)]
        self.assertEqual("claro", X._confianca(bracos, "retencao")[0])

    def test_sem_metrica_nao_inventa_veredito(self):
        bracos = [{"nome": "a", "videos": 9, "medidos": 0, "views": 0,
                   "views_por_dia": None, "retencao": None}]
        self.assertEqual("sem dados", X._confianca(bracos, "retencao")[0])


class MetricaPorCanalTests(unittest.TestCase):
    """O canal de historias tem ledger, credencial e metricas PROPRIOS."""

    def test_builds_continua_saindo_das_globais(self):
        """Tres suites trocam `REGISTRO` por tmpdir. Ler o valor na hora da
        chamada, e nao num dicionario montado no import, e o que mantem isso."""
        antes = metricas.REGISTRO
        try:
            metricas.REGISTRO = Path("qualquer") / "publicados.jsonl"
            self.assertEqual(Path("qualquer") / "publicados.jsonl",
                             metricas.registro_do_canal("builds"))
        finally:
            metricas.REGISTRO = antes

    def test_historias_aponta_para_a_pasta_dela(self):
        alvo = metricas.registro_do_canal("historias")
        self.assertIn("historias", alvo.as_posix())
        self.assertNotIn("random_builds", alvo.as_posix())

    def test_a_pasta_de_metricas_tambem_e_por_canal(self):
        self.assertNotEqual(metricas.pasta_do_canal("builds"),
                            metricas.pasta_do_canal("historias"))


class ReconciliarTests(unittest.TestCase):
    """O id do YouTube que o navegador nao capturou, recuperado pelo titulo."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.registro = Path(self._tmp.name) / "publicados.jsonl"
        self._antes = (metricas.REGISTRO, metricas._token, metricas.enviados)
        metricas.REGISTRO = self.registro
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        (metricas.REGISTRO, metricas._token,
         metricas.enviados) = self._antes
        self._tmp.cleanup()

    def _escrever(self, linhas):
        with open(self.registro, "w", encoding="utf-8") as fh:
            for linha in linhas:
                fh.write(json.dumps(linha, ensure_ascii=False) + "\n")

    def _dublar(self, catalogo):
        metricas._token = lambda canal="builds": ("t", None)
        metricas.enviados = lambda token, quantos=200: catalogo

    def test_preenche_o_id_casando_pelo_titulo(self):
        self._escrever([{"video_id": "g1:build:celular", "titulo": "Alfa x Beta",
                         "plataforma": "youtube", "url": "publicado no YouTube",
                         "youtube_id": None}])
        self._dublar([{"youtube_id": "ABC123", "titulo": "Alfa x Beta",
                       "publicado_em": "2026-09-10T12:00:00Z"}])
        self.assertEqual(1, metricas.reconciliar("builds", log=lambda *_a: None))
        linha = metricas.publicados("builds")[0]
        self.assertEqual("ABC123", linha["youtube_id"])
        self.assertEqual("https://youtu.be/ABC123", linha["url"])

    def test_o_titulo_e_comparado_sem_emoji_nem_caixa(self):
        """O Studio devolve o titulo que ACEITOU: corta, troca espaco e come
        emoji. Comparar cru nao casava quase nada."""
        self._escrever([{"video_id": "g1:build:celular",
                         "titulo": "🔥 Alfa  x  BETA", "plataforma": "youtube",
                         "youtube_id": None}])
        self._dublar([{"youtube_id": "ABC123", "titulo": "Alfa x Beta"}])
        self.assertEqual(1, metricas.reconciliar("builds", log=lambda *_a: None))

    def test_quem_ja_tem_id_nao_e_tocado(self):
        self._escrever([{"video_id": "g1:build:celular", "titulo": "Alfa",
                         "plataforma": "youtube", "youtube_id": "JASEI"}])
        self._dublar([{"youtube_id": "OUTRO", "titulo": "Alfa"}])
        metricas.reconciliar("builds", log=lambda *_a: None)
        self.assertEqual("JASEI", metricas.publicados("builds")[0]["youtube_id"])

    def test_tiktok_fica_de_fora(self):
        """A linha do TikTok tem o mesmo titulo e nenhum id do YouTube:
        sem esta guarda ela ganharia o id do video do YouTube e a metrica
        contaria o mesmo video duas vezes."""
        self._escrever([{"video_id": "g1:build:celular", "titulo": "Alfa",
                         "plataforma": "tiktok", "youtube_id": None}])
        self._dublar([{"youtube_id": "ABC123", "titulo": "Alfa"}])
        self.assertEqual(0, metricas.reconciliar("builds", log=lambda *_a: None))
        self.assertIsNone(metricas.publicados("builds")[0]["youtube_id"])

    def test_sem_nada_a_fazer_nao_pede_token(self):
        """Sem esta saida antecipada, abrir a pagina num canal ja reconciliado
        gastaria uma ida a rede para nada."""
        self._escrever([{"video_id": "g1", "titulo": "Alfa",
                         "plataforma": "youtube", "youtube_id": "JASEI"}])

        def explodir(canal="builds"):
            raise AssertionError("pediu token sem ter o que reconciliar")

        metricas._token = explodir
        self.assertEqual(0, metricas.reconciliar("builds", log=lambda *_a: None))


if __name__ == "__main__":
    unittest.main()
