# Atelie novo: contrato de animacao

Cada folha fica em `palco/biblioteca/animacoes/<peca>/<estado>/<animacao>/`.
`folha.png` e guardada sem reencodar, exatamente como foi enviada. Ao salvar de
novo, a versao anterior vai para `historico/<carimbo>/`; desfazer troca a atual
pela mais recente desse historico.

`animacao.json` tem `quadros` (retangulos `x`, `y`, `w`, `h`), `fps`, `loop`,
`ida_e_volta`, `ancora` (`x`, `y` relativos ao quadro), `escala`, `rotacao`,
`espelho`, `gatilho` e `versao`. `duracao_por_quadro` e opcional e indexada por
quadro. Nenhum quadro pode sair da folha e fps/duracoes devem ser positivos.

O catalogo gerado continua sendo a base. `catalogo_ajustes.json` guarda somente
animacoes novas e as escondidas, portanto regenerar o catalogo nao perde esses
ajustes. A arvore informa quando uma animacao nao tem arte e de qual heranca a
folha sera usada. A API autenticada usa `/api/animacoes`: `arvore`, `gatilhos`,
leitura/folha por peca-estado-animacao, e POST para subir, salvar, desfazer,
criar, esconder e salvar ajustes.
