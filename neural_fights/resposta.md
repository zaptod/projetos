# Como e hoje

O simulador manual entra por `ferramentas/diagnostico/test_manual.py` e cria
`neural_fights.simulation.manual.SimuladorManual`. Ele atualiza e desenha a
luta diretamente em pygame, por `Simulador.update()` e `Simulador.desenhar()`.
Antes desta mudanca nao chamava o palco nem escrevia uma timeline.

Na producao, `random_builds.builds.palco.fonte.timeline_da_luta()` chama
`neural_fights.recording.timeline.gravar_timeline()` com os nomes, seed e
cenario. Esse e o mesmo laco de simulacao do gravador: ele cria a timeline v1
com armas, corrente, efeitos e a lista de sons. A producao a grava por
`neural_fights.recording.timeline_arquivo.salvar()` e
`random_builds.builds.palco.render.renderizar()` monta o job, chama o Godot e
gera o mp4. O Godot le a timeline em `palco/nucleo/palco.gd`.

Agora `G` e `--palco janela` usam essa mesma `fonte.timeline_da_luta()` e
abrem uma previa em loop no Godot. `Shift+G` e `--palco mp4` usam tambem o
renderizador de producao, que resolve os arquivos de som e abre o mp4.

# Duvidas

O palco reproduz a luta automatica determinada por seed, lutadores, cenario e
chave da corrente, que e o contrato da producao. Comandos manuais e edicoes de
slots feitas durante uma partida nao sao um replay gravado; inclui-los exigiria
registrar inputs, algo que o formato de timeline da producao nao faz hoje.

# Prova

Foi executado `python -m neural_fights.simulation.manual --seed 9182 --palco
janela`. A timeline foi exportada, mas a abertura do Godot foi bloqueada pelo
ambiente: `APPDATA do Godot inacessivel em
E:/projetos/palco/_userdata` ao criar `.gdignore`. Tambem nao ha `ffmpeg` no
`PATH`; por isso nao foi possivel renderizar o mp4 nem salvar os tres PNG em
`E:\projetos-wt\_prova_simulador_godot\`.
