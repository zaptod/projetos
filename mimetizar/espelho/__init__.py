# -*- coding: utf-8 -*-
"""Absorver e mimetizar: um canal do YouTube vira uma biblia de como refaze-lo.

O caminho, e por que cada passo existe:

    canal        cataloga o acervo (yt-dlp -J, sem baixar um byte)
    baixar       o acervo em disco, retomavel
    medir        os numeros que NAO precisam de IA (cortes/min, LUFS, silencio)
    transcrever  legenda do YouTube; whisper local so quando nao ha legenda
    analisar     ChatGPT e Gemini leem um dossie por video e devolvem a ficha
    biblia       as fichas viram o manual do canal, com evidencia
    preset       o manual vira config que o `historias/` consome

A ordem nao e burocracia: cada passo produz o insumo do seguinte em disco,
e e isso que torna tudo retomavel. Um canal de 300 videos nao termina numa
sentada, e um processo que morre na metade nao pode custar o que ja foi feito.

A medicao vem antes da IA de proposito. Um LLM olhando um video diz "o corte
e agil"; o ffmpeg diz "4,2 cortes por minuto". A biblia so tem autoridade
porque cada afirmacao dela tem numero ou timestamp atras.
"""
from __future__ import annotations

__all__ = ["canal", "config", "estado"]
