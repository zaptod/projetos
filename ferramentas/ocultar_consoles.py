# -*- coding: utf-8 -*-
"""As tarefas do Agendador abrem janela preta? VERIFICADOR, so leitura.

    python ferramentas/ocultar_consoles.py

Diz, tarefa por tarefa (`NeuralFights_*`, `Historias_auto*`), se ela roda
oculta (`wscript //B oculto.vbs <.cmd>`, desde 17/09/2026), se voltou a abrir
console, ou se QUEBROU (o `oculto.vbs` ou o .cmd sumiu). Sai com 0 quando
esta tudo oculto e 1 quando ha o que olhar.

Nao muda nada. A troca das 25 tarefas ja foi feita. Desde 14/10/2026 (SCR-4)
todos os instaladores (`postar.py --instalar`, `main.py auto --instalar`,
`main.py noite --instalar`) recriam a tarefa ja com `tarefas_windows.
acao_oculta`; o que ainda poderia desfaze-la e uma tarefa recriada a mao. A
Vila flutuante mostra o mesmo resultado no selo "tarefas ocultas" da barra.
"""
from __future__ import annotations

import sys

from painel.flutuante import tarefas


def main(argv=None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if argumentos and argumentos[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argumentos:
        print(f"nao conheco {' '.join(argumentos)}: este verificador so le.")
        return 2
    resumo = tarefas.examinar(tarefas.ler_tarefas())
    print(tarefas.descrever(resumo))
    return 0 if resumo.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
