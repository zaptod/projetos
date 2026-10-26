# -*- coding: utf-8 -*-
"""O trabalhador remoto: o PC `am` (Tailscale) roda o trabalho pesado.

    python -m builds.pc_am saude
    python -m builds.pc_am testar-no-am coordenador
    python -m builds.pc_am duelo --p1 X --p2 Y --seed S
    python -m builds.pc_am bluelock-gravar -- --saida E:\\x\\prova.mp4 --segundos 10

`maquina.py` e o lado daqui (fila, saude, codigo, entradas, execucao, busca
atomica, queda segura); `lado_am.py` e o agente que roda la; `trabalhos.py`
os trabalhos que ja sabem ir (cada um com a sua chave em
`config/pc_am.json`, todas desligadas por padrao). Doc: docs/sessoes/pc-am.md.
"""
