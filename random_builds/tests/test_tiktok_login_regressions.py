"""A janela de login do TikTok: o que ela aceita como "entrou".

15/09/2026, conta nova `zombie_surviv0rs` do canal zombie: o Adrian entrou, o
titulo da janela ja mostrava "zombie_surviv0rs (@zombie_surviv0rs) | TikTok" e
mesmo assim a ferramenta imprimiu "tempo esgotado sem login" e saiu. Os
cookies estavam salvos no perfil o tempo todo (`sessionid`, `sessionid_ss`,
`sid_tt`, `uid_tt`).

A causa: o laco olhava `pagina(ctx)`, que e a PRIMEIRA aba do contexto. Login
feito em outra aba deixa a primeira parada em `/login` ate o prazo estourar.
Um login que deu certo sendo declarado fracasso e pior do que parece: quem le
o log conclui que a conta nao tem sessao e refaz tudo.
"""
import unittest
from pathlib import Path

from builds.publicar import tiktok


class _Aba:
    def __init__(self, url):
        self.url = url


class _Contexto:
    """Contexto de navegador falso: abas e cookies, como o Playwright."""

    def __init__(self, abas, cookies=()):
        self.pages = [_Aba(u) for u in abas]
        self._cookies = [{"name": n} for n in cookies]

    def cookies(self, _url=None):
        return list(self._cookies)


class TemSessaoTests(unittest.TestCase):
    def test_cookie_de_sessao_e_sessao(self):
        ctx = _Contexto(["https://www.tiktok.com/login"],
                        ["sessionid", "sessionid_ss", "sid_tt", "uid_tt"])
        self.assertTrue(tiktok._tem_sessao(ctx))

    def test_so_cookie_de_visitante_nao_e_sessao(self):
        """`uid_tt` e `tt_csrf_token` aparecem sem ninguem ter entrado."""
        ctx = _Contexto(["https://www.tiktok.com/login"],
                        ["tt_csrf_token", "ttwid", "uid_tt"])
        self.assertFalse(tiktok._tem_sessao(ctx))

    def test_contexto_que_explode_nao_derruba_a_janela(self):
        class _Quebrado:
            pages = []

            def cookies(self, _url=None):
                raise RuntimeError("contexto fechado")

        self.assertFalse(tiktok._tem_sessao(_Quebrado()))


class JanelaDeLoginTests(unittest.TestCase):
    """O laco de espera, sem navegador: so a decisao de parar ou continuar."""

    def _rodar(self, ctx, dormidas=None):
        """Roda `_janela_de_login` com o navegador e o relogio dublados."""
        falas = []
        original = {
            "contexto_persistente": tiktok.contexto_persistente,
            "_abrir": tiktok._abrir,
            "pagina": tiktok.pagina,
            "print": getattr(tiktok, "print", print),
        }

        class _Ctx:
            def __enter__(self_):
                return ctx

            def __exit__(self_, *_a):
                return False

        tiktok.contexto_persistente = lambda **_k: _Ctx()
        tiktok._abrir = lambda _c, _u: ctx.pages[0]
        tiktok.pagina = lambda c: c.pages[0]
        from builds.identity import browser
        montou = browser.montou
        browser.montou = lambda _p, minimo=0: True
        relogio = {"t": 0.0}
        dormir = tiktok.time.sleep
        agora = tiktok.time.time

        def _dormir(s):
            relogio["t"] += float(s)

        tiktok.time.sleep = _dormir
        tiktok.time.time = lambda: relogio["t"]
        saida = []
        tiktok.print = lambda *a, **_k: (falas.append(" ".join(map(str, a))))
        try:
            saida.append(tiktok._janela_de_login(Path("perfil_falso")))
        finally:
            tiktok.contexto_persistente = original["contexto_persistente"]
            tiktok._abrir = original["_abrir"]
            tiktok.pagina = original["pagina"]
            browser.montou = montou
            tiktok.time.sleep = dormir
            tiktok.time.time = agora
            if original["print"] is print:
                try:
                    del tiktok.print
                except AttributeError:
                    tiktok.print = print
            else:
                tiktok.print = original["print"]
        return saida[0], falas

    def test_login_em_OUTRA_aba_conta_como_entrou(self):
        """O caso real: aba 0 parada em /login, sessao salva pelo contexto."""
        ctx = _Contexto(["https://www.tiktok.com/login"],
                        ["sessionid", "sid_tt"])
        precisa_reparo, falas = self._rodar(ctx)
        self.assertFalse(precisa_reparo)
        juntas = " | ".join(falas)
        self.assertIn("sessão iniciada", juntas)
        self.assertNotIn("tempo esgotado", juntas)

    def test_sem_cookie_nenhum_ainda_espera_e_desiste(self):
        ctx = _Contexto(["https://www.tiktok.com/login"], ["ttwid"])
        precisa_reparo, falas = self._rodar(ctx)
        self.assertFalse(precisa_reparo)
        self.assertIn("tempo esgotado", " | ".join(falas))


if __name__ == "__main__":
    unittest.main()
