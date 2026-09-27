# As sessões do projeto

Este é o **grupo**: uma pasta com um documento por parte do projeto. Cada
documento é a passagem de bastão daquela parte — escrito pela sessão que a
conhece, para uma sessão que nunca a viu.

Criado em 27/09/2026, depois de um dia em que quatro sessões trabalharam juntas,
foram fechadas, e o que cada uma sabia só existia na conversa delas.

## Como usar

**Sessão nova?** Leia o documento da sua parte inteiro antes de tocar em
qualquer arquivo, e depois só a seção "Contratos com outras partes" das
vizinhas. Não precisa ler os seis.

**Terminou um trabalho que muda a sua parte?** Atualize o documento dela no
mesmo commit. Documento desatualizado é pior que documento ausente: ele é
acreditado.

**Vai mexer em arquivo de outra parte?** A tabela de contratos de cada
documento diz quem manda em cada arquivo. Fale com a sessão dona (ou, se não
houver nenhuma viva, assuma a parte e diga isso no commit).

## As partes

| Parte | Documento | Do que cuida |
|---|---|---|
| Publicação | [publicacao.md](publicacao.md) | A grade, as guardas contra repetição, o ledger, a conferência com os canais |
| Histórias | [historias.md](historias.md) | Roteiro (DeepSeek), imagens (PicassoIA), vídeo, vistoria e parecer |
| Builds / Neural Fights | [builds.md](builds.md) | Builds, estreias, duelos e torneios; o banco de personagens |
| App do celular e bot | [app-e-bot.md](app-e-bot.md) | O PWA pelo Tailscale, as ações e o bot do Telegram |
| Painel e Vila | [painel-e-vila.md](painel-e-vila.md) | O painel, a janela flutuante e a arte da Vila |
| Jogo zombie | [jogo-zombie.md](jogo-zombie.md) | `E:\jogo_ZOMBIE`, o gravador e o canal que ainda não publicou |
| Métricas e conferências | [metricas.md](metricas.md) | Audiência, relatórios do bot, o que deveria disparar alarme |

## O que vale para todas

Estas regras não são de nenhuma parte e valem para quem entrar:

- **Não ficar sem vídeo** é a prioridade declarada do dono — mas **repetir é
  pior que não postar**. Quando as duas brigam, o horário fica vazio com aviso.
- **Nada de trabalho pesado entre :25 e :55**: são os minutos das postagens
  automáticas. A criação de histórias roda de 01h às 06h.
- **Arquivo grande vai para o `E:`**, nunca para o `C:` (o disco do sistema já
  encheu e derrubou rodada).
- **Commit por caminho explícito** (`git add <arquivo>`), nunca `-A`: já houve
  commit que levou junto o trabalho de outra sessão.
- **Medir antes de consertar.** Boa parte dos defeitos deste projeto eram o
  contrário do que parecia, e vários "consertos" nasceram de palpite.
- **Guarda no funil, não no ponto**: proteção que depende de alguém lembrar de
  chamá-la em cada caminho não é proteção.
- **As memórias do dono** (em `~/.claude/projects/e--projetos/memory/`) trazem
  decisões já tomadas. Procure lá antes de perguntar de novo a ele.
