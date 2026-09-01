@echo off
rem ===================================================================
rem  Neural Fights - Testar tudo
rem
rem  Toda a logica esta em ferramentas/abrir.py, de proposito: batch nao e
rem  lugar para decisao, e la o codigo pode ser testado. Aqui so se acha o
rem  Python e se decide se a janela fica aberta para mostrar o erro.
rem
rem  O caminho vai com BARRA NORMAL de proposito: o Windows aceita, e a
rem  barra invertida ja virou byte de controle neste projeto mais de uma vez
rem  (o `\a` de "abrir" vira BEL e o Python diz "Invalid argument").
rem ===================================================================
setlocal
chcp 65001 >nul 2>nul
cd /d "%~dp0"
title Neural Fights - Testar tudo

rem O `py` (lancador oficial do Windows) e mais confiavel que `python`, que
rem pode ser o atalho vazio da Microsoft Store.
set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python

if not defined PY (
    echo.
    echo  Nao achei o Python nesta maquina.
    echo.
    echo  Instale em https://www.python.org/downloads/ e marque a caixa
    echo  "Add Python to PATH" na primeira tela.
    echo.
    pause
    exit /b 1
)

%PY% -X utf8 ferramentas/abrir.py testar
if errorlevel 1 (
    echo.
    echo  --- deu problema. A mensagem acima diz o que foi. ---
    pause
    exit /b 1
)
echo.
pause
exit /b 0
