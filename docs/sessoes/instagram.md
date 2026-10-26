# Instagram (Reels) — como ligar um canal em 3 passos

Destino novo desde 26/10/2026. Código: `random_builds/builds/publicar/instagram.py`
(molde do `tiktok.py`), funil `postar._instagram_da_serie`, horário em
`grade.horas_do_instagram`, conta em `contas.py` (serviço `instagram`, opcional).
**Sem conta com login conferido o destino está DESLIGADO e CALADO** (sem ficha,
sem alarme, `conformidade()` não acusa). Hoje só a série do Blue Lock está ligada
no código; duelos (`builds`) e histórias têm horário e conta prontos, e o postar
ainda não chama o funil deles (ver "O que falta").

## Ligar um canal

1. **Criar a conta** no Instagram (o Adrian; o nome da conta = o @, ex. `egoistsoccer`).
2. **Login** (janela VISÍVEL para ele; a senha nunca passa por nós; ele não clica
   em nada além do login):
   `python -m builds.publicar.instagram --login --canal bluelock --conta egoistsoccer`
   (`--arroba` só se o @ tiver ponto e o nome da conta não puder). O comando
   escolhe a conta do canal, abre o perfil `browser_profiles/instagram__egoistsoccer`,
   traz a janela para a tela, espera o cookie de sessão, **lê o @ na tela** e só
   então liga o destino. Logou em outro @: não liga e diz qual.
3. **Ligar na grade**: nada a fazer para a série (20:37 junto do YouTube e do
   TikTok: `grade.HORAS_DA_SERIE["instagram"]`). Para duelos/histórias o horário
   padrão já está em `grade.HORAS_DO_INSTAGRAM_DOS_OUTROS_CANAIS` (21:37, a
   confirmar) — o que falta é o item abaixo.

Conferir: `--status` (barato, sem navegador), `--conferir` (login vivo + os Reels
do ledger estão no perfil; só lê; recusa dentro da janela das postagens),
`--sondar` (despeja o DOM; usar se o site mudar). Não existe comando de publicar:
só o `postar.py` publica.

## Regras que o código faz cumprir

- **Identidade na tela, antes de publicar** (26/10: um comentário saiu pela conta
  pessoal). O @ do menu é lido e fotografado antes do upload e de novo colado no
  clique em Compartilhar; diferente do @ do canal, ou ilegível = recusa.
- **Nunca** comentar, curtir, seguir ou responder. Pop-ups: só botão de dispensa
  (o fechamento genérico do TikTok, com lista de proibidos maior e a janela
  "Criar" protegida).
- **Capa** do quadro `capa_s` da ficha, enviada ANTES de publicar (não se troca
  depois). Se não entrar: **não publica** (adia) — diferente do TikTok.
- **Sempre o mp4 original da ficha** (marca d'água de outra rede derruba o alcance).
- Legenda: título, descrição e **até 5 hashtags** (instagram-seo: 3 a 5; o teto
  do site é 30 e 2200 caracteres UTF-16). "#1" do título não conta como hashtag.
  A palavra-chave principal vem no começo porque o título vem primeiro.
- "Compartilhar também no feed" ligado (melhor esforço; o laudo diz o que houve),
  corte Original (9:16).
- Ledger: plataforma `instagram`, `serie.registrar`; um por horário e teto de 1
  por dia valem como nos outros destinos; Instagram sai por ÚLTIMO e a falha dele
  nunca atrasa YouTube e TikTok. Se ficar atrás, o próximo episódio dele espera.

## Zona segura do Reel (para a fábrica e o conferente)

Vídeo 1080x1920. Hipóteses da skill `instagram-reels-publishing` (sem link da Meta;
reconferir no app): interface cobre o **topo ~250 px (13%)** e o **rodapé ~350 px
(18%)**; a grade do perfil recorta 3:4 (1080x1440, faixa central y 240–1680) e o
feed recorta 4:5. Gancho, rosto, legenda queimada e CTA ficam em **y 250–1570**,
com folga lateral. Nossa zona do TikTok/conferente (topo 10%, base 20%, direita 12%)
é menor em cima: pintar também a do Instagram na conferência. Capa: texto grande
no centro 3:4.

## O que falta

- **Seletores não validados no site de verdade** (não havia conta). Na primeira vez:
  `--login`, depois `--sondar`, e a primeira publicação com o Adrian olhando
  (`postar=False` pára antes de Compartilhar).
- Duelos e histórias: chamar o funil (`instagram.publicar`) dos `_voando` deles no
  `postar.py` e registrar (builds já registra dentro de `instagram.publicar`;
  histórias por `serie.registrar`). Hoje o `postar_bluelock` é o único chamador.
- Conferência (`--conferir`) não está no retrato de abertura (`handoff.py` tinha
  mudança de outro agente) nem no agendador; `--status` mostra `vivo_em`.
