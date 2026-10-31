# Proposta de modularização dos projetos (31/10/2026)

> **Estado:** proposta arquitetural para revisão. Não foi executada migração, publicação, alteração de dados ou criação dos novos repositórios. A branch de documentação não substitui o plano do produto nem a validação com o produtor.

## Objetivo e falha que motivou o redesenho

O painel antigo ("Vila") consumiu esforço de arte, animação e integração sem oferecer visibilidade suficiente dos projetos. O novo **Painel** deve funcionar como **centro de controle operacional**: tarefas, responsável, estágio, resultado, falhas, próximos passos, métricas e links para evidências. A Vila pode existir, no futuro, como **visualização optativa**; nunca é requisito para operar.

Todo projeto deve rodar de forma independente, sem depender da interface do Painel. O Painel consulta contratos padronizados, não importa diretamente módulos internos de cada jogo/fábrica.

## Fronteiras propostas

| Componente / possível repositório | Responsabilidade | Não deve fazer |
| --- | --- | --- |
| **Painel** | Inventariar projetos, exibir saúde real, filas, próximos marcos, resultados, logs e decisões. Comandos explícitos após autorização. | Renderizar vídeos, postar ou conter regras de negócio dos projetos. |
| **Publicador** | Receber vídeo pronto, validar, agendar, enviar por adaptador, conciliar o destino, manter registro e métricas por conta/plataforma. | Escrever roteiro, gerar mídia ou decidir conteúdo sem política enviada pelo consumidor. |
| **Midia-Core** (apenas se houver consumidores reais) | Render, composição 9:16, legendas, narração e validação de arquivos. | Guardar lógica editorial de histórias/builds. |
| **Automacao-Core** (se o reuso justificar) | Jobs, fila, locks, repetição segura, interrupção/retomada e eventos. | Escolher regras de cada produto ou armazenar senhas de outros projetos. |
| **Provedores-IA** (se o reuso justificar) | Adaptadores para serviços de roteiro/imagem/voz, limites e telemetria. | Impor prompts ou personagens a um produto. |
| **Telemetria** (iniciar como contrato/biblioteca, não necessariamente repositório) | Modelo único de evento, estado, falha, duração, rastreabilidade e evidência. | Ser outro orquestrador paralelo. |

**Regra anti-superengenharia:** componente com um único consumidor permanece como módulo do produto. Tornar repositório/biblioteca separada quando houver **dois consumidores reais**, contrato estável, testes e versionamento. Não criar dez repositórios vazios como substituto de arquitetura.

## Produtos independentes

- **Neural Fights:** simulação, personagens, arena, combate e torneios. Incorporar seletivamente acertos das versões históricas, em vez de importar tudo.
- **Random Builds:** sorteio e vídeo de build; pede catálogo ao Neural Fights e entrega mídia pronta ao Publicador.
- **Histórias:** roteiro seriado, continuidade, cenas, imagens, voz e render; entrega mídia pronta ao Publicador.
- **Mimetizar/Espelho:** observa canais de referência, mede, transcreve e gera bíblia/preset; não publica e não altera os consumidores por import circular.
- **Necroforge, Blue Lock e Zombie Sandbox:** motores autônomos, cada um com próprio ciclo de desenvolvimento e testes.
- **Hub pessoal e automações operacionais:** projetos independentes; **nunca** incorporar dados corporativos/credenciais ao Painel ou a repositórios públicos.
- **Sprites/Palco:** ferramentas de produção visual; distinguir motor genérico de configurações específicas de cada jogo.

**Reuso não é dependência irrestrita:** um produto pode usar biblioteca versionada ou API, mas não importar caminhos internos de outro produto.

## Inventário de pontos de extração já identificados em `zaptod/projetos`

1. **Publicação:** `ferramentas/postar.py` (programação/orquestração), `random_builds/builds/publicar/` (adapters, upload, catálogo, registro e métricas), `historias/contos/publicar/` (publicação por série), `remoto/acoes.py` (controles de publicação manual).
2. **YouTube:** `random_builds/builds/publicar/youtube.py` e `youtube_web.py`; há OAuth em `neural_fights/tools/youtube_oauth.py`.
3. **TikTok:** `random_builds/builds/publicar/tiktok.py`, confirmação/desfecho e recuperação de falhas.
4. **Instagram:** **não implementado como destino aceito** no código inspecionado. Criar adaptador depois de verificar permissões e fluxos oficiais; não anunciar suporte antes de validação real.
5. **Mídia/IA:** identificar recursos realmente comuns a `random_builds/`, `historias/` e `mimetizar/`; preservar regras específicas.
6. **Observabilidade e controle:** `visao/` (Panorama), `painel/`, `remoto/` e `coordenador/` têm leituras/filas/estados hoje acoplados. O novo Painel consome um único contrato, sem inventar um segundo sistema de estado.

## Contrato mínimo entre cada projeto e o Painel

Um resumo versionado (HTTP local ou arquivo JSON emitido pelo processo) deve oferecer:
```json
{
  "schema_version": 1,
  "project_id": "historias",
  "observed_at": "2026-10-31T11:32:00-03:00",
  "status": "running",
  "active_jobs": 1,
  "queued_jobs": 2,
  "blocked_jobs": 0,
  "last_success_at": null,
  "last_error": null,
  "next_milestone": "Revisar pipeline de render",
  "evidence": []
}
```
Campos do exemplo são **ilustrativos**, não dados medidos. Todo job deve ter ID estável, projeto, etapa, estado (queued/running/blocked/failed/succeeded/cancelled), timestamps, progresso comprovado, evento e evidência. **Sem evento novo = sem progresso**, nunca confundir ausência de falha com sucesso.

Comandos opcionais: `start`, `pause`, `retry`, `cancel`, `publish`. Toda ação que altera estado requer permissão explícita, trilha de auditoria e confirmação reforçada para publicação.

## Contrato do Publicador

Entrada: `job_id`, `source_project`, `source_video_id`, caminho/artefato, título, descrição, conta/perfil, plataformas solicitadas, privacidade e agendamento. Saída: estado **por plataforma**, `remote_post_id`, URL, confirmação verificada, tentativas e razão de falha.

Garantias:
- Idempotência por `(source_video_id, plataforma, conta, variante)`.
- Trava transacional por publicação, comprovante antes/depois do envio e fila de **a conferir** quando resultado é ambíguo.
- Retries **somente quando seguros**; reconciliar destino antes de repetir upload.
- A publicação parcial (ex.: YouTube OK / TikTok falhou) preserva o mesmo job e o débito daquele destino, não gera novo vídeo.
- Guardas: vídeo íntegro, áudio, duração/formato, título repetido, parte ordenada, autorização, cota, conta correta, janela agendada.
- Credenciais locais/segredos fora do Git; autorização e capacidades diferentes para cada plataforma.
- Nunca migrar diretamente a programação real: primeiro **modo simulado**, regressões e comparativo lado a lado.

## MVP do Painel: zero Vila

Tela simples (lista/tabela), com:
1. **Projetos:** parado / rodando / bloqueado / falhou / sucesso, último evento real e commit.
2. **Trabalhos:** fila, estágio, duração, resultado e link para log/artefato.
3. **Publicação:** por canal e plataforma, publicados, pendentes, a conferir, horários, falhas e métricas.
4. **Decisões:** dono, prioridade, bloqueio, próximo marco e evidência.
5. **Controles:** comandos isolados, autenticados e auditados; inicia com **somente leitura**.

Usar o que já existe de `Panorama` como referência, mas sem importar o monorepo inteiro. A camada visual opcional só pode consumir a mesma API; nenhuma regra fica dentro da animação.

## Ordem de migração (sem quebrar a produção)

1. Congelar **inventário e contratos**; mapear consumidores, dados, credenciais e testes por módulo.
2. Criar **Publicador** e seus testes; conectar **um** consumidor em modo simulado/dupla leitura sem enviar nada.
3. Migrar YouTube e TikTok com guardas e auditoria intactas; comparar registro/retentativa contra a base e fazer rollout por canal.
4. Iniciar **Painel** somente leitura com dados comprovados de dois projetos e do Publicador.
5. Conectar os demais produtores e extrair Mídia/Automação/IA somente onde o reuso for real.
6. Planejar Instagram como destino separado, com validação de API/conta antes de habilitar.
7. Só considerar a Vila como tema plugável quando o MVP tiver uso e valor demonstrados.

## Critérios de aceite

- Cada jogo/fábrica funciona sem o Painel nem os outros produtos abertos.
- O Publicador atende pelo menos dois produtores sem importar seus modelos internos.
- Nenhum vídeo duplicado em falha, retry ou retomada; registros conciliados com resultado real.
- O Painel é utilizável com arte/animação desabilitadas, e mostra erro/estado sem inventar dados.
- Interfaces públicas versionadas, testes de contrato, migração reversível e manual mínimo.
- Nenhum segredo, dado pessoal ou configuração interna de empresa incluído neste repositório.

## Situação em 31/10/2026

Este documento foi feito por **leitura** da organização e de arquivos do repositório, não por execução dos sistemas. `main` e `refactor/arquitetura` podem representar etapas diferentes. O novo repositório **Painel ainda não foi criado**, nem os demais repositórios propostos.
