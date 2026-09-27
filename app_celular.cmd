@echo off
rem App do celular (PWA via Tailscale serve, somente tailnet).
rem Chamado pela tarefa NeuralFights_app_celular do Agendador, a cada 10 min:
rem se ja houver um no ar, a porta 8931 esta ocupada e este sai na hora.
cd /d "E:\projetos"
rem --perigosas liga a zona de perigo (apagar midia, regenerar banco, mexer
rem em conta). Decisao do Adrian em 27/09/2026: "entrar, com trava extra" —
rem e a trava e digitar o nome do alvo na confirmacao.
"C:\Python314\python.exe" -u -X utf8 -m remoto.api_http --local --porta 8931 --acoes --publicar --perigosas >> "E:\projetos\outputs\app_celular.txt" 2>&1
