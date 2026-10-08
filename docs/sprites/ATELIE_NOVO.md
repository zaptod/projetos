# Atelie novo: contrato de animacao

Cada folha fica em `palco/biblioteca/animacoes/<peca>/<estado>/<animacao>/`.

## Vila

O grupo **Vila** e gerado de `docs/vila/inventario_vila.json`, sem alterar o
catalogo do jogo. As folhas de habitantes usam a pose como gatilho e uma
animacao por direcao. A Vila prefere a folha salva pelo Atelie e cai na arte
aprovada antiga, depois no desenho por codigo.
`folha.png` e guardada sem reencodar, exatamente como foi enviada. Ao salvar de
novo, a versao anterior vai para `historico/<carimbo>/`; desfazer troca a atual
pela mais recente desse historico.

O Atelie antigo foi retirado do app: nao ha Montar, Recortador, Provador,
variantes ou guarda-roupa. Permanecem somente as rotas `/api/animacoes/*`.

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

## Lutador montado

`GET /api/animacoes/montagem` devolve a composicao 320x180 usada pela previa.
Cada camada informa folha, contrato, camada, alvo e posicao da ancora. A conta
fica em `atelie_animacoes.montagem`: a ancora relativa vira pixels do quadro e
e desenhada em `posicao - ancora`, como `TocadorFolha` (`Rect2(-ancora, tamanho)`).
Sem folha, o canvas desenha o marcador neutro. Os parametros `peca`, `estado` e
`animacao` trocam a camada em edicao sem salvar a alteracao.

## Previa no Godot

`POST /api/animacoes/previa-godot` recebe peca, estado e animacao ja salvos e
devolve um id. `GET /api/animacoes/previa-godot/<id>` informa `rodando`,
`pronto` (com URL temporaria autenticada do MP4) ou `falhou`. O render e unico
por vez e fica em `runtime/atelie_previas` por no maximo um dia. A previa usa
uma seed estavel e escolhe fichas cuja classe, arma ou skill corresponde a peca;
quando nao ha como reconhecer um efeito, usa qualquer ficha do banco.
