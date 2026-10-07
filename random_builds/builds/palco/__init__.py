"""O palco (Onda 16D): a luta desenhada pelo Godot a partir da timeline.

O Python faz o que nao e desenho: acha o Godot (config/palco.json ou
NF_GODOT), monta o trabalho (job) com a timeline e os arquivos de som
resolvidos pela cadeia do jogo, chama o Godot em Movie Maker, comprime o AVI
uma vez so (h264 + aac) e CONFERE a saida (resolucao, quadros, faixa de
audio, volume do trecho de luta). Falha e erro, nunca rc 0 calado.

O que sai pelos comandos daqui (`main.py palco ...`) mora em
`outputs/_palco/`, que o catalogo nao varre. A unica porta para a producao e
`producao` (16G, segunda metade): com a chave `producao.duelo_celular` do
config ligada, o `final_celular.mp4` de um duelo sai pelo palco. Ela vem
DESLIGADA; ligar e decisao do Adrian.

Modulos:
    config     o config/palco.json e onde estao o Godot e o projeto
    godot      rodar o Godot (headless, import, Movie Maker) sem roubar foco
    plano      a conta dos quadros (espelho do nucleo/plano.gd)
    sons       id do som -> arquivo, pela cadeia do jogo; sons derivados dos
               eventos quando a timeline ainda nao tem a secao `sons`
    fonte      seed -> luta -> timeline (16C) + corte de tedio
    render     timeline -> mp4 conferido
    checagens  ffprobe e ebur128 na saida
    sintetica  timeline de mentira para os testes
    ab         a MESMA luta no visual velho e no palco, lado a lado
    edicao     16G: a edicao do duelo (HUD, textos, som, musica) sobre o palco
    producao   16G: o celular do duelo de PRODUCAO pelo palco, atras da chave
               (padrao "desligado"); o controller so o importa dentro de um
               try, e qualquer falha devolve o celular ao pygame
    cli        `main.py palco ...` e `main.py duelo --palco`
"""
