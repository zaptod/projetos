# Auditoria Painel e Vila — 11/10/2026

## Confirmados (do mais grave ao menos)

### 1. Veredito afirma que esta tudo em dia quando as verificacoes falham — gravidade: alta

- Onde: `visao/panorama/auditoria.py:veredito` (linhas 202-221)

- O defeito: o veredito so transforma contagens e alertas em problema; ignora os campos `erro` de qualidade e metas. Assim, uma auditoria que nao conseguiu ler a fila ou o ledger pode receber selo verde.

- Quando acontece: a vistoria e a leitura das metas falham e recursos nao tem alerta -> o topo/Telegram responde `tudo em dia` em vez de indicar que a verificacao nao foi feita.

- Prova: `PYTHONPATH='random_builds;historias;visao' python -c "from panorama.auditoria import veredito; print(veredito({'qualidade': {'erro': 'vistoria indisponivel'}, 'metas': {'erro': 'ledger indisponivel'}, 'recursos': {'alertas': []}}))"` saiu `{'cor': 'ok', 'frase': 'tudo em dia', 'problemas': []}`.

- Conserto sugerido: incluir os campos `erro` de cada controle em `problemas`, como aviso/erro de verificacao indisponivel.

### 2. Falha ao consultar cada tarefa do Agendador vira lista inteiramente saudavel — gravidade: media

- Onde: `visao/panorama/recursos.py:211` (`_agendador`)

- O defeito: a excecao de `tarefas_windows.conferir(nome)` e descartada com `continue`; nenhuma tarefa entra em `faltando` ou `fracas` e nao ha campo de erro.

- Quando acontece: a consulta do Agendador falha para todas as tarefas (por exemplo, PowerShell/servico indisponivel) -> recursos informa 34 tarefas e `faltando: []`, `fracas: []`.

- Prova: `PYTHONPATH='random_builds;historias;visao' python -c "from panorama import recursos; from builds import tarefas_windows; recursos._horas_de_criacao=lambda: []; tarefas_windows.conferir=lambda nome: (_ for _ in ()).throw(OSError('agendador indisponivel')); print(recursos._agendador())"` saiu `{'total': 34, 'faltando': [], 'fracas': []}`.

- Conserto sugerido: registrar a tarefa como nao verificavel e propagar um alerta de consulta falha, sem confundir com tarefa conferida.

### 3. Falha de leitura do Agendador nao acende alerta na Vila — gravidade: media

- Onde: `painel/flutuante/dados.py:830` (`resumo`, linhas 847 e 860-865)

- O defeito: `tarefas.examinar(None)` representa leitura impossivel com `ok: None` e selo `tarefas: ?`, mas o resumo so alerta para `ok is False`; por isso classifica o estado como calmo.

- Quando acontece: `Get-ScheduledTask` falha e nao ha outro erro/foco -> a faixa/icone mostra `💤 tudo parado`, sem avisar que nao conseguiu verificar as tarefas.

- Prova: `python -c "from painel.flutuante.dados import resumo; print(resumo({'tarefas': {'lido': False, 'ok': None, 'selo': 'tarefas: ?'}, 'bot': {'vivo': True}}))"` saiu `{'nivel': 'calmo', 'frase': '💤 tudo parado', 'alerta': ''}`.

- Conserto sugerido: tratar `lido: False`/`ok is None` como aviso visivel no resumo.

## Nao confirmados

- Nenhum: as demais suspeitas examinadas nao tiveram reproducao segura sem tocar no estado real.
