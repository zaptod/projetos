# -*- coding: utf-8 -*-
"""A aba 🧭 Fluxo da Biblioteca: o caminho de um pedido (05/10/2026).

Pedido do Adrian ("sim eu quero"): uma pagina no app com o diagrama de como
um pedido anda, das entradas ate a resposta, e os caminhos de erro. A pagina
e texto fixo no index.html; o risco dela e MENTIR quando o codigo mudar. Por
isso cada numero e cada nome que ela afirma e conferido aqui contra o codigo
de verdade (coordenador/pedidos.py, coordenador/vigia_trabalho.py,
coordenador/supervisor.py, remoto/delegar.py). Mudou la: este teste cai, e a
pagina e corrigida junto.
"""
from __future__ import annotations

import inspect
import re
from html.parser import HTMLParser
from pathlib import Path

from coordenador import pedidos, supervisor, vigia_trabalho
from remoto import delegar

APP = Path(__file__).resolve().parent / "app"
RAIZ = Path(__file__).resolve().parents[1]
HTML = (APP / "index.html").read_text(encoding="utf-8")
JS = (APP / "biblioteca.js").read_text(encoding="utf-8")
CSS = (APP / "app.css").read_text(encoding="utf-8")


def _pagina() -> str:
    inicio = HTML.index('id="biblioteca-fluxo"')
    return HTML[inicio:HTML.index("</section>", inicio)]


def _texto() -> str:
    """O texto que o Adrian le (sem tags, espacos juntos)."""
    sem_tags = re.sub(r"<!--.*?-->|<[^>]+>", " ", _pagina(), flags=re.S)
    sem_tags = sem_tags.replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", sem_tags)


class _Pais(HTMLParser):
    """id -> a <section> onde ele mora."""

    def __init__(self):
        super().__init__()
        self.pilha, self.onde = [], {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        secao = a.get("id") if tag == "section" else None
        if a.get("id"):
            self.onde[a["id"]] = secao or next((s for _t, s in reversed(self.pilha) if s), None)
        if tag not in ("input", "img", "meta", "link", "br", "canvas"):
            self.pilha.append((tag, secao))

    def handle_endtag(self, tag):
        while self.pilha:
            if self.pilha.pop()[0] == tag:
                break


# ------------------------------------------------------------- a casca
def test_a_aba_fluxo_mora_na_biblioteca():
    abas = HTML[HTML.index('id="biblioteca-abas"'):HTML.index('id="biblioteca-lista"')]
    assert 'data-aba="fluxo"' in abas
    p = _Pais()
    p.feed(HTML)
    assert p.onde["biblioteca-fluxo"] == "tela-biblioteca"
    assert p.onde["fluxo-passos"] == "tela-biblioteca"
    # escondida ate a aba ser tocada; a troca esconde a busca e a lista
    assert re.search(r'id="biblioteca-fluxo" class="[^"]*\boculto\b', HTML)
    troca = JS[JS.index("function bibliotecaTrocarAba"):]
    for alvo in ("biblioteca-fluxo", "biblioteca-lista", "biblioteca-busca"):
        assert f'$("{alvo}").classList.toggle("oculto"' in troca
    assert "bibliotecaTrocarAba(botao.dataset.aba)" in JS


def test_a_pagina_respeita_a_csp_da_casca():
    """`style-src 'self'`: atributo style e <style> dentro da casca nao valem;
    o desenho e por classe (app.css) e SVG com atributos de geometria."""
    pagina = _pagina()
    assert " style=" not in pagina and "<style" not in pagina
    assert "<script" not in pagina
    assert not re.search(r"\son\w+=", pagina)
    assert pagina.count("<svg") >= 2
    for classe in ("biblioteca-fluxo", "fluxo-passo", "fluxo-erro", "fluxo-entradas",
                   "fluxo-seta", "fluxo-junta", "fluxo-desvio"):
        assert f".{classe}" in CSS


def test_a_ordem_do_caminho():
    texto = _texto()
    ordem = ["📝 App", "✈️ Telegram", "📖 Grimório", "1 · Mesa de pedidos", "2 · Orquestrador",
             "3 · Permissão", "4 · Despachante", "5 · Vigia", "6 · Conferente", "7 · Resposta"]
    posicoes = [texto.index(nome) for nome in ordem]
    assert posicoes == sorted(posicoes)
    for erro in ("Limite do Claude", "Espera do Grimório", "Conflito", "Falhou"):
        assert erro in texto


# ------------------------------------------- o que a pagina afirma x o codigo
def test_as_entradas_sao_as_que_o_registrar_aceita():
    fonte = inspect.getsource(pedidos.MesaPedidos.registrar)
    assert '("app", "telegram", "grimorio")' in fonte
    assert pedidos.e_de_estado("o app está no ar?")          # vai ao cerebro
    from remoto import comandos
    # 05/10 (conferente 3): texto solto e sempre pedido novo; continuar e
    # explicito (Responder no app, /responder <id> no Telegram)
    assert "responder" in comandos.TABELA and "/responder <id>" in _texto()
    assert "sempre um pedido novo" in _texto()
    assert "ATIVOS" not in fonte and "_ativo_mais_novo" not in fonte
    # conferente 5: so a LISTA FIXA e conversa (comparada inteira); o "curto"
    # por contagem de palavras saiu. As frases que a pagina cita sao as da lista
    texto = _texto()
    assert "forma_fixa" in fonte and "e_curto_demais" not in fonte
    assert not hasattr(pedidos, "CURTO_MAX_PALAVRAS") and "até 3 palavras" not in texto
    assert "lista fixa" in texto and "comparada inteira" in texto
    for frase in ("oi", "bom dia", "coordenador?", "qual o progresso?", "alguma novidade?",
                  "status"):
        assert f"“{frase}”" in texto and pedidos.forma_fixa(frase) == "conversa", frase
    for frase in ("ok", "valeu", "obrigado", "beleza"):
        assert f"“{frase}”" in texto and pedidos.forma_fixa(frase) == "agradecimento", frase
    for frase in ("reinicie o app", "pode ligar o gerente?"):     # curtos, mas pedidos
        assert f"“{frase}”" in texto and pedidos.forma_fixa(frase) == "", frase


def test_nenhum_texto_do_app_promete_a_regra_do_curto():
    """Conferente hf1 (05/10/2026): a dica do cartao Pedir (fora da pagina
    Fluxo) e o CURTO_AVISO diziam "mensagem curta nao abre pedido", e a regra
    e a lista fixa: "reinicie o app" e "sim" abrem pedido. Confere o app
    inteiro e o aviso que o servidor devolve, nao so o #biblioteca-fluxo."""
    proibidas = re.compile(r"mensagem curta|mensagens curtas|texto curto não|curto demais",
                           re.I)
    for nome in sorted(p.name for p in APP.glob("*.html")) + sorted(
            p.name for p in APP.glob("*.js")):
        achou = proibidas.search((APP / nome).read_text(encoding="utf-8"))
        assert achou is None, f"{nome}: {achou.group(0) if achou else ''}"
    assert proibidas.search(pedidos.CURTO_AVISO) is None
    assert "Agradecimento solto" in pedidos.CURTO_AVISO
    assert all(f in pedidos.CURTO_AVISO for f in ("ok", "valeu", "obrigado", "beleza"))
    pedir = HTML[HTML.index('id="pedir-cartao"'):HTML.index("</textarea>",
                                                             HTML.index('id="pedir-cartao"'))]
    assert "lista fixa" in pedir and "agradecimento solto" in pedir


def test_responder_em_trabalhador_limpo_cobranca_e_contratando():
    """Conferente 5 (05/10/2026): o que a pagina diz do trabalhador ja limpo,
    da cobranca do desfecho e do "chamando o trabalhador" e o que o codigo faz."""
    texto = _texto()
    troca = inspect.getsource(pedidos.MesaPedidos._substituir_trabalhador)
    assert "self._contratar(" in troca and "_em_cobranca" in troca and "_bloquear" in troca
    assert "_substituto_recusado" in inspect.getsource(pedidos.MesaPedidos._contratar)
    assert "já foi limpa" in texto and "um orquestrador novo" in texto.replace("<b>", "")
    assert "o seu texto, a última resposta e a sua resposta" in texto
    assert "falha com o motivo da recusa" in texto
    assert "A cobrança do desfecho não contrata ninguém" in texto
    # a cobranca leva a original e a resposta final e a original
    assert "resposta_cobrada" in inspect.getsource(pedidos.MesaPedidos._continuar)
    assert "original.rstrip()" in inspect.getsource(pedidos.MesaPedidos._entregue)
    assert "mandando de volta a resposta original" in texto
    assert "a original, com o desfecho declarado depois" in texto
    # a trava: o lento roda fora dela, e o app mostra o estado do meio
    assert pedidos._ROTULO["contratando"] == "chamando o trabalhador"
    assert "chamando o trabalhador" in texto and "não se perde" in texto
    assert "_rodar_os_lentos" in inspect.getsource(pedidos.MesaPedidos.passo)


def test_os_numeros_da_pagina_sao_os_do_codigo():
    texto = _texto()
    assert supervisor.PULSO_S == 5 and "a cada 5 s" in texto
    assert pedidos.MAX_RETOMADAS == 5
    assert "nenhuma das 5 retomadas" in texto and "cai 5 vezes" in texto
    assert pedidos.RETOMAR_S == 120 and "retoma a cada 2 min" in texto
    assert pedidos.SEM_EVENTO_S == 600 and "10 min sem sinal" in texto
    assert vigia_trabalho.INTERVALO_S == 60 and "a cada 1 min" in texto
    assert vigia_trabalho.ESPERA_SUJA_S == 3600 and "avisa uma vez depois de 1 h" in texto


def test_as_situacoes_mostradas_existem():
    """Cada situacao da faixa "O que o app mostra" e um estado do pedido (ou o
    rotulo que o app da a ele), e nenhum estado fica de fora."""
    faixa = _pagina()[_pagina().index('class="fluxo-situacoes"'):]
    faixa = faixa[:faixa.index("</p>")]
    mostradas = set(re.findall(r"<span>([^<]+)</span>", faixa))
    rotulos = dict(re.findall(r'(\w+): "([^"]+)"',
                              (APP / "coordenador.js").read_text(encoding="utf-8")
                              .split("const PEDIDO_ROTULO = {", 1)[1].split("};", 1)[0]))
    estados = set(pedidos.VIVOS) | set(pedidos.FINAIS)
    assert set(rotulos) <= estados
    como_aparece = {e: rotulos.get(e, e) for e in estados}
    assert mostradas == set(como_aparece.values())


def test_as_tres_regras_de_permissao_e_a_conta_sempre_negada():
    assert delegar.REGRAS_PERMISSAO == ("gerente_aceita", "perguntar_ao_adrian", "negar")
    fonte = inspect.getsource(delegar.regra_de_permissao)
    assert re.search(r'categoria == "conta":\s*return "negar"', fonte)
    texto = _texto()
    assert "gerente aceita" in texto and "pergunta a você" in texto and "nega" in texto
    assert "conta é sempre negado" in texto
    # sem gerente ligado, a regra "gerente aceita" vira pergunta ao Adrian
    equipe = (RAIZ / "coordenador" / "equipe.py").read_text(encoding="utf-8")
    assert 'regra == "gerente_aceita" and ligado' in equipe


def test_o_conferente_decide_pela_primeira_palavra():
    assert pedidos._aprovado("APROVADO, nenhum defeito")
    assert not pedidos._aprovado("DEFEITOS: 1) o botao sumiu")
    texto = _texto()
    assert "APROVADO → conferido" in texto and "DEFEITOS → falhou" in texto


def test_reabrir_existe_como_a_pagina_ensina():
    main = (RAIZ / "coordenador" / "__main__.py").read_text(encoding="utf-8")
    assert '"reabrir-pedido"' in main
    assert "python -m coordenador reabrir-pedido <id>" in _texto()
    assert callable(pedidos.MesaPedidos.reabrir)


def test_o_validador_so_recusa_a_entrega_vazia():
    """Desde 02/10 fora da lista, binario e diff grande ENTRAM com aviso; a
    pagina dizia que eram recusados (conferente, 05/10)."""
    config = dict(delegar.PADRAO_CONFIG)
    grande = config["diff_max_linhas"] + 1
    entrega = [{"caminho": "fora/da/lista.png", "binario": True, "mais": grande, "menos": 0}]
    assert delegar.validar_diff(entrega, ["remoto/**"], config) == []
    avisos = " ".join(delegar.avisos_do_diff(entrega, ["remoto/**"], config))
    assert "fora da lista" in avisos and "binário" in avisos and "diff grande" in avisos
    assert delegar.validar_diff([], ["remoto/**"], config)          # vazia: recusa
    texto = _texto()
    assert "só a entrega vazia é recusada" in texto
    assert "fora da lista, binário e diff grande entram com aviso" in texto
    assert "recusad" not in texto.replace("só a entrega vazia é recusada", "")
    assert "validador recusou" not in texto
    # a vazia nao vai ao integrador: vira "nada a aplicar"
    integrador = inspect.getsource(vigia_trabalho.VigiaTrabalho._contratar_integrador)
    assert '"não mudou nada" in motivo' in integrador
    assert "Entrega vazia não é conflito: vira nada a aplicar" in texto


def test_o_momento_seguro_e_sem_publicacao_em_voo_e_nao_tem_horario():
    """Desde 03/10 ("NÃO FICA ESPERANDO HORÁRIO") o vigia nao espera a janela da
    postagem para aplicar: so a publicacao em voo barra (conferente, 05/10).

    O REINICIO de servico e outra conversa: D3 (13/10/2026) voltou a janela
    `post-12 .. post+18` ao `supervisor.seguro` (etapa 2 da reforma)."""
    from datetime import datetime

    def sup(processos, quando=datetime(2026, 10, 5, 17, 30)):
        return supervisor.Supervisor(
            servicos={"app": {"nome": "app", "assinatura": "app", "comando": ["app"],
                              "cwd": ".", "log": "x.log", "janela": "oculta",
                              "modulos": [], "reinicio_seguro": True}},
            relogio=lambda: quando,
            processos=lambda: processos, porta=lambda: True, git=lambda *_: False,
            avisar=lambda *_: None, gravar=lambda _: None, log=lambda _: None,
            parar=lambda *_: None, iniciar=lambda _: 1, comandos=lambda: [],
            aplicar=lambda *a, **k: None, carregar=lambda: {}, pendentes=lambda: [])

    assert sup([]).seguro("") == (True, "")
    ok, motivo = sup([{"pid": 7, "comando": "python ferramentas/postar.py"}]).seguro("")
    assert not ok and "publicacao" in motivo
    ok, motivo = sup([], datetime(2026, 10, 5, 17, 55)).seguro("")   # 2 min antes do post das 17:57
    assert not ok and "janela das postagens" in motivo
    assert delegar.PADRAO_CONFIG["janela_sem_aplicar"] is None
    texto = _texto()
    assert "sem publicação em voo; não espera horário" in texto
    assert "Publicação em voo também só faz esperar" in texto
    # a unica janela que sobrou na pagina e a da acao que mexe no estoque
    assert texto.count("janela da postagem") == 1
    assert "espera a janela da postagem quando a ação mexe no estoque" in texto


def test_o_limite_nao_gasta_retomada_e_o_codex_assume_quem_constroi():
    fonte = inspect.getsource(pedidos.MesaPedidos._parar_por_limite)
    assert 'ia_forcada="codex"' in fonte and 'situacao="parado_limite"' in fonte
    assert "retomadas" not in fonte                  # parar no limite nao conta retomada
