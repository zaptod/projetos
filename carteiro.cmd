@echo off
rem O carteiro da Vila das IAs (fase 2): entrega o correio do Adrian a cada
rem IA e traz a resposta (ias/carteiro.py). Chamado pela tarefa
rem NeuralFights_carteiro do Agendador, a cada 10 min: se ja houver um
rem rodando, a trava ias__carteiro faz este sair na hora (codigo 3).
rem O log e aberto pelo Python (--saida): o >> do cmd trancaria o arquivo.
cd /d "E:\projetos"
"C:\Python314\python.exe" -u -X utf8 -m ias carteiro --saida "E:\projetos\outputs\carteiro.txt"
