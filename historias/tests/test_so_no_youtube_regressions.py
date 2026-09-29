"""A parte que so saiu no TikTok vai ao YouTube pelas guardas, nao por fora.

Decisao do Adrian em 28/09/2026 (`partes-so-no-tiktok`): subir no YouTube
`historia_00022:p03`, `00027:p01` e `00032:p04`. O caminho que existia
(`historias/main.py publicar <id> --youtube`) nao olha titulo no canal, nem a
vistoria (audio mudo, imagem sem prova de origem), nem a lista a conferir, e
grava a linha sem `prova` e sem `youtube_id`. `postar.py --so-youtube` passa
pelas guardas que fazem sentido para uma parte avulsa; estes testes travam
cada uma, e que o `--ver` nunca publica.

Medido no `--ver` de 28/09, 22:04: as tres passam, e as tres sao RETIDAS
("a IA reprovou e as rodadas de conserto acabaram") — por isso a retida que
sai vai para a lista a conferir, como na grade.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_so_youtube", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _V:
    id = "historia_00027:celular:p01"
    fonte_id, parte, partes = "historia_00027", 1, 4
    titulo = "Pensão da Lourdes — A ligação das sete da manhã (Parte 1/4)"
    caminho = "x.mp4"
    perfil = "celular"


class SoNoYoutubeTests(unittest.TestCase):
    def setUp(self):
        self.p = _postar()
        self.p._linha = lambda *_a, **_k: None
        self.publicou, self.registrou, self.marcou = [], [], []
        self.ja = None
        self.no_canal = ""
        self.laudo = {"ok": True, "erros": [], "avisos": []}
        self.retencao = ""
        self.a_conferir = False

        import contos.publicar.catalogo as C
        import contos.publicar.qualidade as Q
        import contos.publicar.serie as S
        from builds import travas
        for mod, nome, valor in (
                (C, "publicar_youtube", self._publicar),
                (S, "registrar", lambda *a, **k: self.registrou.append(a)),
                (S, "ja_publicado", lambda *_a, **_k: self.ja),
                (Q, "vistoriar_parte", lambda *_a, **_k: self.laudo),
                (travas, "ocupada", lambda *_a, **_k: False)):
            self.addCleanup(setattr, mod, nome, getattr(mod, nome))
            setattr(mod, nome, valor)
        roteiro = sys.modules.get("contos.roteiro.roteiro")
        if roteiro is None:
            import contos.roteiro.roteiro as roteiro
        self.addCleanup(setattr, roteiro, "carregar", roteiro.carregar)
        roteiro.carregar = lambda *_a, **_k: {}
        self.p._video_por_id = lambda vid: _V() if vid == _V.id else None
        self.p.titulo_repetido = lambda *_a, **_k: False
        self.p._publico_no_canal = lambda *_a, **_k: self.no_canal
        self.p._sem_a_conferir = (lambda fila, _c: []
                                  if self.a_conferir else fila)
        self.p._retencao = lambda _a: self.retencao
        self.p._marcar_retido = lambda a, r: self.marcou.append((a.id, r))
        self.p._visibilidade_das_historias = lambda: "public"

    def _publicar(self, alvo, visibilidade, provas=None, **_k):
        self.publicou.append((alvo.id, visibilidade))
        if provas is not None:
            provas.append({"youtube_id": "ABCdef12345", "estado": "publicado"})
        return "publicado no YouTube"

    def test_ver_NUNCA_publica(self):
        r = self.p.subir_so_no_youtube(_V.id, so_ver=True)
        self.assertFalse(r["feito"])
        self.assertIn("so vendo", r["motivo"])
        self.assertEqual([], self.publicou)
        self.assertEqual([], self.registrou)

    def test_publica_e_registra_com_prova_e_id(self):
        r = self.p.subir_so_no_youtube(_V.id)
        self.assertTrue(r["feito"])
        self.assertEqual(["ABCdef12345"], r["ids"])
        (alvo, url, plataforma, _ag, extra), = self.registrou
        self.assertEqual("youtube", plataforma)
        self.assertEqual("ABCdef12345", extra["youtube_id"])
        self.assertEqual("postar.py --so-youtube", extra["por"])
        self.assertTrue(extra["prova"])

    def test_ja_no_youtube_pelo_ledger_recusa(self):
        self.ja = {"quando": "2026-09-22T12:00:00"}
        r = self.p.subir_so_no_youtube(_V.id)
        self.assertFalse(r["feito"])
        self.assertEqual([], self.publicou)

    def test_titulo_publico_no_canal_recusa(self):
        """O rascunho gemeo de 15/09 subiu sem gravar linha: o ledger nao
        sabe, o canal sabe."""
        self.no_canal = "fn1_Sy3RpMk"
        r = self.p.subir_so_no_youtube(_V.id)
        self.assertIn("fn1_Sy3RpMk", r["motivo"])
        self.assertEqual([], self.publicou)

    def test_vistoria_reprovada_recusa(self):
        """Audio mudo e imagem sem prova de origem moram na vistoria."""
        self.laudo = {"ok": False, "avisos": [], "erros": [
            "nenhuma imagem tem prova de origem"]}
        r = self.p.subir_so_no_youtube(_V.id)
        self.assertIn("prova de origem", r["motivo"])
        self.assertEqual([], self.publicou)

    def test_a_conferir_recusa(self):
        self.a_conferir = True
        r = self.p.subir_so_no_youtube(_V.id)
        self.assertIn("a conferir", r["motivo"])
        self.assertEqual([], self.publicou)

    def test_retida_que_sai_fica_a_conferir(self):
        self.retencao = "a IA reprovou e as rodadas de conserto acabaram"
        self.p.subir_so_no_youtube(_V.id)
        self.assertEqual([(_V.id, self.retencao)], self.marcou)

    def test_retida_no_ver_nao_marca(self):
        self.retencao = "a IA reprovou"
        self.p.subir_so_no_youtube(_V.id, so_ver=True)
        self.assertEqual([], self.marcou)

    def test_fora_do_catalogo_recusa(self):
        r = self.p.subir_so_no_youtube("historia_00099:celular:p01")
        self.assertFalse(r["feito"])
        self.assertEqual([], self.publicou)


if __name__ == "__main__":
    unittest.main()
