# Coordenador residente

O coordenador e o processo local que mantem app, bot, carteiro e Vila flutuante vivos sem depender de uma janela do VS Code. Ele adota processos ja existentes pela linha de comando, registra o estado em `%LOCALAPPDATA%\neural-fights\coordenador\estado.json` e so reinicia codigo velho fora das janelas de postagem e de uma publicacao real.

Para instalar a tarefa (uma vez, em um prompt do usuario):

```powershell
cd E:\projetos
python -m coordenador instalar-tarefa
python -m coordenador desligar-tarefas-antigas
```

Ela inicia no logon como `NeuralFights_coordenador`. Para conferir ou controlar manualmente:

```powershell
python -m coordenador status
python -m coordenador reiniciar app
```

Para desfazer a substituicao das tres tarefas antigas, execute `python -m coordenador religar-tarefas-antigas`. Para remover somente a tarefa nova, execute `python -m coordenador remover-tarefa`.

Os comandos de celular aceitos sem IA sao `servico_reiniciar`, `servico_parar`, `servico_ligar` e `pc_acao`. Acoes do PC passam por uma allowlist; nao ha execucao de texto arbitrario. O interruptor do Claude interrompe somente delegados, nunca esses quatro servicos.
