# -*- coding: utf-8 -*-
"""A Vila das IAs — fase 1: a FICHA de capacidades de cada IA, medida.

Pedido do Adrian (29/09/2026, plano `vila-das-ias.md`): "primeiro eu quero
passar IA por IA, tambem integrar o Grok, para podermos mapear tudo: o que
gera imagem, o que gera texto, possiveis erros, mensagem de limite de cota
etc."

    python -m ias sondar <ia>|todas     refaz a sonda (abre o navegador)
    python -m ias fichas                imprime a tabela comparativa
    python -m ias tabela-png <saida>    a mesma tabela em PNG (para o Grimorio)

O que mora aqui:

  ficha.py     o SCHEMA unico (`docs/ias/ficha.md`), ler/gravar/validar, e a
               tabela. `vazia()` e uma ficha valida: o caso ZERO existe.
  catalogo.py  os TEXTOS que cada site poe na tela no lugar da resposta
               (recusa enlatada, limite, upgrade, parede, Cloudflare) — o que
               o codigo e os logs ja conheciam, mais o que a sonda ve.
  sonda.py     a sonda de verdade: abre o perfil com a TRAVA da conta, mede
               com o minimo de cota e guarda captura + texto lido como prova.

Os clientes vem de `contos.llm` (ChatGPT, Gemini, DeepSeek, Grok) e de
`builds.identity` (PicassoIA, DreamFace, Digen); este pacote nao abre Chrome
por conta propria nem inventa seletor.
"""
from __future__ import annotations

IAS = ("gemini", "chatgpt", "deepseek", "grok", "picasso", "dreamface", "digen")
