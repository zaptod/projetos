# -*- coding: utf-8 -*-
"""A Oficina de sprites por dentro: limpar, fatiar, alinhar e exportar
folhas de sprite que vem de IA (o ChatGPT, por exemplo) para o palco.

Sem Tk aqui dentro: a pagina (`painel/paginas/oficina.py`) so desenha. Tudo
e numpy + Pillow, sem laco pixel a pixel em Python -- o `piriri.py` do
Adrian levava segundos numa folha de 1942x809 e a previa ao vivo precisa de
fracao de segundo.

    rotulos.py   componentes conectados (sem scipy), por corridas
    limpeza.py   fundo, alfa minimo, despill, linhas de grade, ilhas
    fatiar.py    a grade: linhas desenhadas, faixas vazias ou componentes
    alinhar.py   mesma ancora, mesma celula, a folha final
    receita.py   os parametros juntos (a mesma receita serve o lote)
    medidas.py   o que se mede para dizer "ficou limpo" sem olhar
    exportar.py  a folha, os metadados e a cena do palco

Decisao do Adrian (28/09/2026, `builds/sprites-animados` = "limpar depois"):
"quero apenas uma interface grafica que facilite ao maximo esse processo,
como essa limpeza de fundo, saneamento e auto fatiamento de frames,
identificacao e outras coisas uteis".
"""
