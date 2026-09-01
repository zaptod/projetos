# -*- coding: utf-8 -*-
"""Travas por RECURSO, para os processos rodarem em paralelo sem se pisar.

Ate aqui existia uma trava so (a do worker de identidade), e ela serializava
tudo: gerar imagem de historia esperava o Digen, que esperava o PicassoIA.
Mas a restricao real nunca foi "um processo por vez" — e "um Chrome por
PERFIL por vez" (o Chrome tranca o user_data_dir) e "um worker por FILA"
(dois roubam os jobs `running` um do outro).

Entao a trava certa tem o nome do recurso:

    picasso__principal     a conta principal do PicassoIA
    chatgpt__historias     a conta do ChatGPT usada pelas historias
    fila_identidade        a fila de jobs do random_builds

Digen + PicassoIA + ChatGPT + render rodam JUNTOS, porque sao perfis
diferentes. Duas coisas na MESMA conta continuam em fila — que e o unico
caso em que precisa.

Lock de arquivo (msvcrt/fcntl), nao-bloqueante por padrao: quem nao pega a
trava recebe False e decide o que dizer ao usuario. `esperar` transforma em
fila com paciencia limitada.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

# Travas que ESTA THREAD ja segura, com a profundidade de cada uma.
#
# Por que precisa existir: a guarda passou para dentro de
# `contexto_persistente`, e ha lugares que ja pegam a trava antes de chamar.
# Sem reentrancia eles travariam contra si mesmos, e o sintoma seria a
# pipeline parada parecendo disco lento.
#
# Por THREAD e nao por processo, de proposito: se fosse por processo, uma
# segunda thread veria o contador e acharia que e dona de uma trava que nao
# pegou.
_minhas = threading.local()


def _seguradas() -> dict:
    if not hasattr(_minhas, "nomes"):
        _minhas.nomes = {}
    return _minhas.nomes


def _pasta() -> Path:
    try:
        from .contas import runtime_dir
        base = runtime_dir() / "locks"
    except Exception:
        base = Path(__file__).resolve().parents[1] / "outputs" / "_locks"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _nome_seguro(nome: str) -> str:
    return "".join(c if c.isalnum() or c in "_-." else "_" for c in str(nome))[:80]


@contextmanager
def trava(nome: str, esperar: float = 0.0):
    """`with trava("picasso__principal") as minha:` — True se o recurso e seu.

    Com `esperar`, tenta de novo a cada meio segundo ate o prazo. O arquivo
    nunca e apagado (apagar lock em uso e corrida); ele e minusculo e fica.
    """
    seguradas = _seguradas()
    chave = _nome_seguro(nome)
    if chave in seguradas:
        # Ja e minha: so conta mais um nivel e devolve. Nao encosta no
        # arquivo, senao o `finally` de dentro soltaria a trava de fora.
        seguradas[chave] += 1
        try:
            yield True
        finally:
            seguradas[chave] -= 1
            if seguradas[chave] <= 0:
                seguradas.pop(chave, None)
        return

    caminho = _pasta() / f"{chave}.lock"
    arquivo = open(caminho, "a+b")
    adquirido = False
    fim = time.monotonic() + max(0.0, float(esperar))
    try:
        arquivo.seek(0, os.SEEK_END)
        if arquivo.tell() == 0:
            arquivo.write(b"\0")
            arquivo.flush()
        while True:
            arquivo.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                adquirido = True
                break
            except OSError:
                if time.monotonic() >= fim:
                    break
                time.sleep(0.5)
        if adquirido:
            seguradas[chave] = 1
        yield adquirido
    finally:
        if adquirido:
            seguradas.pop(chave, None)
            try:
                arquivo.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        arquivo.close()


def ocupada(nome: str) -> bool:
    """O recurso esta em uso agora? (testa sem segurar).

    Conta tambem a trava que ESTA thread ja segura. Sem essa linha, quem
    tem a trava perguntaria "esta ocupada?" e ouviria "nao" — verdade pela
    metade que faria um painel dizer que ha paralelismo onde nao ha.
    """
    if _nome_seguro(nome) in _seguradas():
        return True
    with trava(nome) as minha:
        return not minha


def estado() -> list:
    """Todas as travas conhecidas e quem esta segurando o que.

    E a resposta grafica para "o que esta rodando em paralelo agora?". Sem
    isto, saber se duas coisas podem rodar juntas exigia ler codigo: os
    perfis sao invisiveis, e o unico sintoma de colisao era uma mensagem de
    "em uso" no meio de uma geracao.
    """

    saida = []
    for servico in ("picasso", "digen", "dreamface", "chatgpt", "gemini",
                    "tiktok", "youtube_web"):
        for canal in ("builds", "historias"):
            try:
                nome = do_perfil(servico, canal)
            except Exception:
                continue
            if any(linha["trava"] == nome for linha in saida):
                continue        # a mesma pasta nos dois canais = uma trava so
            canais = [c for c in ("builds", "historias")
                      if _mesma(servico, c, nome)]
            pasta = pasta_do_perfil(servico, canal)
            saida.append({"trava": nome, "servico": servico,
                          "canais": canais, "ocupada": ocupada(nome),
                          # O caminho e o que torna "estes dois dividem a
                          # trava" verificavel em vez de afirmacao cega.
                          "perfil": str(pasta) if pasta else ""})
    return sorted(saida, key=lambda linha: linha["trava"])


def _mesma(servico: str, canal: str, nome: str) -> bool:
    try:
        return do_perfil(servico, canal) == nome
    except Exception:
        return False


def pasta_do_perfil(servico: str, canal: str = "builds",
                    conta: str | None = None) -> Path | None:
    """Onde fica o `user_data_dir` daquele servico/canal, ou None."""
    try:
        from .contas import perfil
        return perfil(servico, canal, conta)
    except Exception:
        return None


def do_perfil(servico: str, canal: str = "builds",
              conta: str | None = None) -> str:
    """O nome da trava do PERFIL de Chrome daquele servico/canal.

    O nome sai do CAMINHO resolvido, nao do nome da conta. A diferenca
    importa: o servico `youtube_web` tem `sessao_unica`, ou seja, um login do
    Google cobre os tres canais e `contas.perfil()` devolve a MESMA pasta
    para todos. Enquanto isto chavava por conta, `builds` e `historias`
    ganhavam travas diferentes para o mesmo `user_data_dir` — e duas
    instancias do Chrome na mesma pasta a corrompem. O sintoma seria "meu
    login sumiu", dias depois, sem causa aparente.

    Chavando pelo caminho, qualquer divergencia futura entre "que conta e
    esta" e "que pasta ela usa" se resolve sozinha: a trava protege o
    recurso, e o recurso e a pasta.

    O sufixo em hexadecimal desempata pastas de mesmo nome em raizes
    diferentes (a conta `principal` mora no caminho legado, as outras no
    diretorio de runtime).
    """
    caminho = pasta_do_perfil(servico, canal, conta)
    if caminho is None:
        # Sem registro de contas legivel, cai no comportamento antigo: e
        # melhor uma trava por conta do que nenhuma trava.
        return f"{servico}__{conta or 'principal'}"
    return do_caminho(caminho)


def do_caminho(caminho) -> str:
    """O nome da trava daquela pasta de perfil.

    Existe separado de `do_perfil` porque quem abre o Chrome nem sempre sabe
    de que servico/canal veio a pasta — `contexto_persistente` recebe so o
    `user_data_dir`. Sendo a pasta o recurso, a pasta basta.
    """
    # `normcase` e o certo aqui, nao `.lower()`: no Windows ele deixa tudo
    # minusculo (a mesma pasta escrita com outra caixa e a MESMA pasta, e
    # tem que dar a mesma trava); no Linux ele nao mexe, porque la duas
    # pastas que so diferem na caixa sao duas pastas mesmo.
    import os.path
    resolvido = os.path.normcase(str(Path(caminho).resolve()))
    digital = hashlib.sha1(resolvido.encode("utf-8")).hexdigest()[:8]
    legivel = _nome_seguro(os.path.normcase(Path(caminho).name))
    return f"perfil__{legivel}__{digital}"


__all__ = ["do_caminho", "do_perfil", "estado", "ocupada",
           "pasta_do_perfil", "trava"]
