# Manutenção

- `vigia_som.py`: re-renderiza os duelos com o som real nas janelas noturnas; use `python ferramentas/manutencao/vigia_som.py --repo random_builds`.
- `vigia_som_dia.py`: re-renderiza em cópia durante o dia, respeita a grade e troca os arquivos fora dela; use `python ferramentas/manutencao/vigia_som_dia.py --repo random_builds`.
- `copiar.py`: copia arquivos de uma worktree somente se o destino não mudou desde a base; use `python ferramentas/manutencao/copiar.py BASE ORIGEM DESTINO --conferir`.
- `inventario/montar.py`: gera as páginas do Inventário de Sprites a partir do JSON; use `python ferramentas/manutencao/inventario/montar.py inventario-sprites`.
- `parecer_gemini_video.py`: pede ao Gemini no navegador um parecer textual sobre um MP4; use `python ferramentas/manutencao/parecer_gemini_video.py caminho/video.mp4 "Pergunta"`.

O antigo `reiniciar_app.ps1` não foi trazido: ele reiniciava apenas o app pela tarefa agendada e abortava quando detectava publicação real em andamento (processos de publicação ou tarefa `NeuralFights_postar_*`). O coordenador atual o substitui.
