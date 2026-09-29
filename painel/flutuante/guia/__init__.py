# -*- coding: utf-8 -*-
"""A janela do GUIA das IAs: onde o Adrian cola o HTML de cada coisa.

Pedido dele (29/09/2026, 01:55): "cria uma interface grafica flutuante pra
eu colar os htmls e etc tb". Contexto: a Vila das IAs (plano
`vila-das-ias.md`, fase 1). Outro agente abre o navegador de cada IA
visivel na tela e ele mostra onde escreve, manda, anexa, troca de modelo;
esta janela fica ao lado para ele COLAR o HTML do elemento (copiado do
DevTools), seletores, textos de erro/cota e observacoes — e tudo entra no
mesmo guia que o agente le.

  colado.py   as contas sem Tk: detectar o tipo do que foi colado, a previa
              enxuta, o seletor robusto (role/aria/data-testid/texto, nunca
              classe gerada), o `colado.jsonl` (append atomico) e o
              `_atual.json` (qual IA esta em mapeamento agora).
  janela.py   a janela: sem borda, por cima, arrastavel, tamanho lembrado.
  __main__    `python -m painel.flutuante.guia [--prova PNG] [--ia grok]`

A INTERFACE COM O AGENTE DO GUIA E SO POR ARQUIVO, em
`random_builds/outputs/_ias/`: esta janela le `_atual.json` e escreve
`<ia>/guia/colado.jsonl`. Nada aqui importa `ias` nem `historias`.
"""
