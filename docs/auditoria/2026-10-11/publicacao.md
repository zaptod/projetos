# Auditoria Publicacao — 11/10/2026

## Confirmados (do mais grave ao menos)

### 1. Escritor sem trava pode ter a publicacao apagada pelo reconciliador — gravidade: alta

- Onde: `random_builds/builds/publicar/metricas.py:175` (`acrescentar_ao_ledger`) e `random_builds/builds/publicar/metricas.py:194` (`reescrever_ledger`)

- O defeito: depois de expirar a espera pela trava, o escritor faz `append` mesmo sem possuir a trava. Um reconciliador que ja leu o ledger e ainda vai fazer `os.replace` pode substituir o arquivo e apagar essa linha nova.

- Quando acontece: a reconciliacao segura `ledger__builds` ou `ledger__historias` por mais de 120 s; uma publicacao conclui, esgota a espera e grava; em seguida a reconciliacao troca o arquivo pela fotografia anterior. A publicacao real fica sem ledger e pode voltar para a fila, levando a repostagem.

- Prova: `PYTHONPATH=random_builds;historias python -` (trecho isolado com `acrescentar_ao_ledger(..., paciencia=0)` sem posse da trava, seguido de `reescrever_ledger`) deixou como saida final somente `{"video_id": "antes"}`; a linha `durante` foi apagada.

- Conserto sugerido: nao permita append sem a trava; ao expirar, preserve a linha numa fila atomica separada que o reconciliador tambem incorpora antes do replace.

### 2. Duas chamadas simultaneas podem subir a mesma parte de historia duas vezes — gravidade: alta

- Onde: `historias/contos/publicar/serie.py:151` (`publicar`), especialmente `serie.py:219` e `serie.py:237`

- O defeito: a verificacao `ja_publicado` e o upload nao estao protegidos por uma trava da serie, da parte ou do ledger. Dois processos podem ambos observar que a parte ainda nao foi registrada e ambos executar o upload.

- Quando acontece: duas acoes de publicacao da mesma historia se sobrepoem (por exemplo, dois cliques ou dois processos). Antes de qualquer um registrar, os dois passam por `ja_publicado`; cada um envia o mesmo MP4 e so depois registra.

- Prova: `PYTHONPATH=random_builds;historias python -` (duas threads de `serie.publicar`, com o upload sincronizado logo apos a guarda) imprimiu duas vezes `publicado no YouTube` e terminou em `uploads_registrados= 2`.

- Conserto sugerido: segure uma trava interprocesso por `historia_id`/plataforma desde antes de `ja_publicado` ate apos `registrar`.

## Nao confirmados

- Nenhum adicional: os demais pontos suspeitos examinados tinham guardas ou exigiriam falha externa nao reproduzida.
