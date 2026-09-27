@echo off
rem Mantem a Vila flutuante no ar (janela do painel, sempre por cima).
rem Chamado pela tarefa NeuralFights_vila_flutuante a cada 10 min.
rem
rem SO ABRE SE NAO ESTIVER ABERTA. A janela ja tem instancia unica, mas o
rem segundo lancamento TRAZ A JANELA PARA A FRENTE de proposito (e o que faz
rem o atalho funcionar). Repetir isso de 10 em 10 minutos roubaria o foco da
rem tela do Adrian o dia inteiro, entao a guarda mora aqui.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$viva = Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match 'painel.flutuante|vila_flutuante' }; if (-not $viva) { Start-Process -FilePath 'C:\Python314\pythonw.exe' -ArgumentList '-X','utf8','-m','painel.flutuante','--medio' -WorkingDirectory 'E:\projetos' }"
