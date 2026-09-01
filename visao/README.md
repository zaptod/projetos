# Panorama — as quatro famílias de número

> Parte do monorepo `e:/projetos`. O mapa está no
> [README da raiz](../README.md).

```python
from panorama import resumo
dados = resumo()          # saude, desempenho, inventario, qualidade
```

## Por que existe

"Como estão as coisas?" tinha **três respostas diferentes**: a Vila contava
LINHAS de dois arquivos (o que conta também o que falhou), o painel rodava
um CLI e despejava o texto num log, e o bot do Telegram tinha a terceira
versão. Três respostas para a mesma pergunta, e uma delas errada — sem saber
qual.

| família | o que responde |
|---|---|
| `saude` | o que roda AGORA, por (fábrica, canal), fila, alertas, e quem divide pasta com quem |
| `desempenho` | publicados nos dois canais, views/likes/retenção já baixados |
| `inventario` | vídeos prontos, histórias por próximo passo, banco do jogo |
| `qualidade` | erros recentes por fábrica, ranking da arena, campeão |

## Três regras, e não são decoração

- **Só lê.** Há teste que tira um retrato (tamanho + mtime) de cada arquivo
  do runtime antes e depois. Um agregador que escreve corrompe estado quando
  alguém abre uma tela.
- **Sem rede.** As métricas do YouTube já são baixadas por
  `main.py metricas --atualizar` e ficam salvas; aqui só se lê o disco. Há
  teste que proíbe `socket.socket` durante a leitura — a tela não pode
  travar porque a internet caiu.
- **Não levanta.** Família que falha vira campo `erro` e as outras três
  seguem de pé; `contos` ausente é vazio, não exceção.

TTL de 3 s: cada leitura toca disco, e sem cache um poller viraria I/O
contínuo. Medido: 0,89 s a primeira, 0 ms as seguintes.

## O nome

O diretório se chama `visao` e o pacote `panorama` **de propósito**. Um
diretório da raiz com o mesmo nome do pacote vira namespace vazio e
sombreia a instalação — foi o que aconteceu com `historias`.
