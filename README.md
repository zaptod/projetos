# projetos — o mapa

Seis projetos que se alimentam: um jogo, duas fábricas de vídeo, um estúdio
de engenharia reversa, um painel e um bot. Este arquivo é o mapa; cada pasta
tem o seu próprio README com o detalhe.

## Começar

Clique duas vezes:

| arquivo | o que abre |
|---|---|
| **`painel.bat`** | a **Vila** — o painel principal |
| `criar videos.bat` | a janela de criação de vídeos |
| `jogo.bat` | a janela do jogo |
| `testar.bat` | roda tudo e mostra o resultado |

Os `.bat` conferem a instalação e **consertam o que falta** antes de abrir.
Se algo der errado, a janela fica aberta com a mensagem em vez de sumir sem
explicação.

Pela linha de comando, o equivalente é `python -m painel`.

## Os projetos

```
neural_fights/   o jogo: simulação de luta com IA, arena, torneio, live
random_builds/   a roleta de builds -> vídeo publicado     (pacote: builds)
historias/       o canal de histórias por IA               (pacote: contos)
mimetizar/       canal alheio -> bíblia -> preset          (pacote: espelho)
visao/           as quatro famílias de número              (pacote: panorama)
painel/          o painel de controle: Vila e janelas de trabalho
vila/            o motor de sprites da Vila + a Oficina
remoto/          o bot de Telegram, para acompanhar do celular
```

Os cinco primeiros **produzem**; `mimetizar/` é o único que **estuda**. Ele
aponta para um canal que já funciona, mede o que ele faz, faz o ChatGPT e o
Gemini lerem cada vídeo, e devolve o manual — mais um preset que o
`historias/` consome. Foi a resposta para um problema real: todo formato aqui
foi escolhido no olho e corrigido depois pela retenção medida.

### Quem depende de quem

```
        neural_fights            (não depende de ninguém)
              ▲
              │
           builds                (o catálogo do jogo alimenta as roletas)
           ▲    ▲
           │    │
       contos   panorama         (histórias reusa narrador/trilha/PicassoIA)
        ▲     ▲
        │     │
     espelho  painel             (espelho reusa o cliente de ChatGPT/Gemini;
                                  painel lê tudo, escreve nada)
```

`espelho` alimenta `contos` de volta — mas **por arquivo**, nunca por import:
ele escreve um preset em `mimetizar/outputs/canal_000NN/preset/`, e quem copia
para `historias/config/` é uma pessoa. Import de volta faria um ciclo.

`remoto` e `vila` ficam de fora do desenho de propósito: os dois só leem o
diário e o registro de contas.

**Nada é importado por acaso.** Cada projeto é um pacote instalado:

```
pip install -e . -e ./random_builds -e ./historias -e ./mimetizar \
            -e ./visao -e ./painel
```

Duas regras que o repositório trata como invioláveis, porque quebrá-las
custou tempo antes:

1. **Nenhum pacote pode ter o nome de um diretório da raiz que não seja ele
   mesmo.** Um diretório sem `__init__.py` vira *namespace package* e
   **sombreia a instalação em silêncio** — `import historias` da raiz
   devolvia um pacote vazio. É por isso que o pacote se chama `contos`.
2. **Nenhuma cirurgia de `sys.path`.** Havia 45; sobraram 2, e as duas são
   legítimas. `ferramentas/auditoria_arquitetura.py` é a catraca que impede
   o número de voltar a subir.

## As três janelas

Cada uma é um **processo próprio**: uma travar não derruba as outras, e com
Tkinter isso importa de verdade — duas telas pesadas no mesmo processo
disputam a mesma thread.

| janela | o que tem | cara |
|---|---|---|
| **Vila** | o mundo ao vivo, o diário, o paralelismo | quente, pixel art |
| **Criação** | fluxo, publicar, vídeos, histórias, espelho, contas, reações | sóbria, densa |
| **Jogo** | torneio, simulação, banco, live, áudio | sóbria, densa |

A Vila é o hub: dela se abrem as outras duas.

## Onde o estado mora

Nada de estado fica no repositório. Tudo vive em
`%LOCALAPPDATA%\neural-fights\`:

| arquivo | o que é |
|---|---|
| `armas.json`, `personagens.json` | o banco do jogo |
| `atividade.jsonl` | o diário — é o que a Vila mostra |
| `contas.json` | qual conta publica em qual canal |
| `locks/` | uma trava por **pasta de perfil** do Chrome |
| `browser_profiles/` | os logins dos sites |
| `live.sqlite3` | os espectadores da live |

A variável `NEURAL_FIGHTS_RUNTIME_DIR` move tudo isso — é o que deixa os
testes rodarem sem encostar no banco de verdade.

## Testar

```
python testar.py          tudo: ~1900 testes + o smoke do painel (~3 min)
python testar.py --rapido só as suítes, sem abrir janela
```

Ele roda os cinco projetos, o agregador e o painel **num comando só**. Isso
não era verdade até 01/09/2026: havia dois mundos de teste disjuntos (este
arquivo cobria três projetos, o CI cobria outro) e o CI ficou vermelho por
dias sem ninguém ver.

Antes das suítes, três verificações baratas:

- **ferramentas** — `ffmpeg`/`ffprobe` no PATH (metade do projeto depende
  deles, e a falta só aparece no meio de um render de 20 minutos);
- **integridade** — byte de controle no fonte. Já quebrou uma regex em
  silêncio, porque o heredoc do shell converte `\b` em 0x08;
- **arquitetura** — a catraca. Falha se os números **piorarem**.

## Documentação

- `docs/neural_fights/PROJECT_CONTEXT.md` — o jogo por dentro
- `docs/historico/` — changelogs e prompts antigos
- `random_builds/README.md`, `historias/README.md`, `vila/README.md`,
  `remoto/README.md` — um por projeto
- `ferramentas/` — utilitários de desenvolvimento e diagnósticos
  interativos (ficam fora dos testes de propósito: abrem janela e pedem
  olho humano)
