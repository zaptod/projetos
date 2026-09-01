# Painel — a Vila e as janelas de trabalho

> Parte do monorepo `e:/projetos`. O mapa está no
> [README da raiz](../README.md).

Era um arquivo de 4583 linhas com uma classe de 191 métodos. O que estava
errado não era o tamanho — era não haver contrato nenhum: cinco filas
copiadas, oito leitores de disco na thread da interface, 47 linhas de
comando montadas à mão e 74 rótulos com o estilo escrito na própria linha.

```
estilo.py     as duas caras e as três escalas
widgets.py    os componentes; um lugar só por coisa
processos.py  UM supervisor e UMA fila
app.py        a casca: barra lateral, conteúdo e o console em gaveta
janelas.py    quais janelas existem e como cada uma abre
paginas/      uma por arquivo, seguindo o contrato
```

## O contrato de página

```python
class Pagina:
    chave, rotulo, icone            identidade no menu
    def construir(self, pai)        monta os widgets, uma vez
    def ao_mostrar(self)            entrou na tela
    def ao_esconder(self)           saiu — é aqui que a animação desliga
    def atualizar(self, resumo)     recebe o dicionário do `panorama`
```

`ao_esconder` não é simetria bonita: é o que impede a animação da Vila de
continuar rodando escondida, gastando 60 ms de relógio para desenhar o que
ninguém vê.

## As duas caras

A **Vila** é quente e o pixel art é o protagonista; as **janelas de
trabalho** são sóbrias e densas. Como cada uma é um processo separado, as
duas nunca aparecem juntas e manter dois conjuntos de token custa pouco.

Três regras carregam o resto, e estão em `estilo.py`:

1. **Superfície se separa por borda de 1px**, não por bloco de cor mais
   clara. Quatro tons empilhados viram uma mancha de longe.
2. **O acento é só do que é clicável ou está ativo.** Se todo título de
   cartão for roxo, três cartões competem com o item de menu ativo e o
   acento deixa de querer dizer alguma coisa.
3. **Escalas fechadas**: espaço 4/8/12/16/24/32 e nada entre; texto por
   PAPEL (título/seção/corpo/legenda/mono), nunca por tamanho; cor por
   SIGNIFICADO (`erro`, não `vermelho`).

## O console é uma gaveta

Ele ocupava **130 px fixos** e quase sempre vazios. Numa tela de 768 px isso
empurrava para baixo da dobra o cartão "ONDE POSTAR", a tabela de
paralelismo e fileiras inteiras de botões. Agora são 32 px de faixa que se
abre sozinha quando um comando começa.

## Uma armadilha que custou tempo

`texto` era cor **e** método do tema. `__getattr__` só roda quando a busca
normal falha, então o Tk recebia o objeto do método virado string e dizia
*"unknown color name 2302295812480texto"*. O método virou `letra()`, e o
construtor do `Tema` agora **recusa** cor com nome de atributo real.
