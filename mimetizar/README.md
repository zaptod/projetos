# mimetizar — Absorver e Mimetizar

> Parte do monorepo. O mapa geral está em [../README.md](../README.md).
> Pacote instalado: **`espelho`** (`pip install -e ./mimetizar`).

Os outros projetos daqui **produzem** conteúdo. Este **estuda** conteúdo dos
outros: aponta para um canal do YouTube que já funciona, mede o que ele faz,
faz o ChatGPT e o Gemini lerem cada vídeo, e devolve duas coisas —

- **a bíblia** (`biblia.md`): como aquele canal é feito, por dentro;
- **o preset** (`preset/`): a mesma coisa em JSON, no formato que o
  `historias/` já sabe ler, mais o diagnóstico do que falta construir.

## O caminho

Três comandos:

```
python main.py canal https://www.youtube.com/@alguem   cataloga (não baixa)
python main.py absorver canal_00001 --limite 30        o trabalho todo
python main.py biblia canal_00001                      o manual do canal
python main.py preset canal_00001                      config pro historias/

python main.py status [canal_00001]                    onde cada canal está
```

### O vídeo é material de passagem

`absorver` é o coração, e o desenho dele é o que torna um canal de 342 vídeos
viável numa máquina só:

```
baixa o lote → mede → transcreve → monta o dossiê
             → ChatGPT e Gemini leem AO MESMO TEMPO
             → apaga os vídeos → próximo lote
```

**O disco fica plano.** Só o lote atual existe em vídeo — quatro arquivos por
padrão, `--lote 1` para estritamente um de cada vez. Cada mp4 é apagado assim
que os dois provedores terminam com ele. O acervo inteiro do canal nunca
existe em disco, e não precisa: o que a bíblia usa é o derivado —
medida, transcrição, mosaico de frames e as duas fichas, alguns quilobytes
por vídeo.

**Os dois provedores rodam de verdade em paralelo**, um processo cada. As
travas de `builds.travas` são por pasta de perfil do Chrome, então ChatGPT e
Gemini não disputam nada. A saída dos dois vem prefixada no mesmo console.

É retomável no nível do vídeo: um que já tem as duas fichas nunca volta para
a fila, mesmo com o mp4 apagado — quem decide é a ficha em disco, não o
arquivo. Um canal grande não termina numa sentada.

Os comandos por etapa (`baixar`, `medir`, `transcrever`, `analisar`)
continuam existindo para rodar uma parte isolada ou depurar. Seguir por eles
num acervo grande enche o disco; o `status` sugere sempre o `absorver`.

## Por que medir antes de perguntar à IA

Um LLM olhando um vídeo diz *"o corte é ágil"*. O ffmpeg diz *"4,2 cortes por
minuto"*. A bíblia só tem autoridade porque cada afirmação dela tem número ou
timestamp atrás — e é o `medir` que produz esses números, sem IA nenhuma.

O que sobe para o ChatGPT/Gemini não é o mp4 (nenhum dos dois engole um vídeo
de 12 minutos pelo navegador): é um **dossiê** por vídeo — ficha técnica,
números medidos, transcrição com tempos e um contact sheet de frames.

## Os dois provedores não são redundância

ChatGPT e Gemini analisam o **mesmo dossiê**, independentes. Onde os dois
concordam vira regra da bíblia; onde divergem vira hipótese marcada.

`--provedor ambos` roda os dois **em sequência** (um console, um log). Para
rodar em paralelo, abra dois terminais e use `--provedor chatgpt` num e
`--provedor gemini` no outro: as travas de `builds.travas` são por pasta de
perfil do Chrome, então os dois não disputam nada.

## O que ele reusa dos vizinhos

| de onde | o quê |
|---|---|
| `contos.llm.cliente` | ChatGPT/Gemini por navegador, com prova de envio e espera por estabilidade |
| `builds.travas` | uma trava por pasta de perfil do Chrome |
| `builds.contas` | qual conta em qual canal, e onde mora o login |
| `builds.atividade` | o diário que a Vila desenha |

O login é o mesmo do `historias/` — o perfil de Chrome e o registro de contas
são compartilhados, então `python main.py llm login --provedor chatgpt` num
projeto vale no outro. O comando existe nos dois para quem está absorvendo um
canal não precisar saber que a sessão mora ao lado.

## Onde isto aparece no painel

Janela **Criação**, página **🪞 Espelho**, ao lado de Histórias — que é quem
consome o preset. Os botões disparam esta mesma CLI por subprocesso; a página
não reimplementa nada.

## Precisa de

- **ffmpeg** e **ffprobe** no PATH (`winget install Gyan.FFmpeg`)
- **yt-dlp** (entra com o `pip install -e ./mimetizar`)
- **Chrome** pelo patchright (`patchright install chrome`), para os LLMs
- opcional: `pip install -e "./mimetizar[transcricao]"` — o whisper local, só
  usado quando o vídeo não tem legenda no YouTube

## Uma nota sobre o acervo

Baixar em massa contraria os termos de uso do YouTube. Esta ferramenta é
local, o material não é republicado, e no fluxo `absorver` o vídeo nem sequer
fica: ele entra, vira medida e ficha, e sai. O que persiste descreve **como o
canal é feito** — cortes por minuto, fórmula, tom, cadência — não o conteúdo
dele. As citações são evidência curta com timestamp, e o validador recusa
citação longa com a mensagem "evidência é trecho curto, não transcrição".

`mimetizar/.gitignore` mantém tudo isso fora do repositório. O comando
`baixar` avulso, que guarda o acervo, mostra a estimativa de espaço antes de
começar e exige `--sim` acima do teto de `config/coleta.json`.

## Testar

```
cd mimetizar && python -m unittest discover -s tests -p "test_*.py"
```

Ou, junto com o resto do monorepo, da raiz: `python testar.py`.
