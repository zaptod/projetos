# Decisões — Geral

Gerado por `remoto/decisoes.py` a cada resposta. Não edite à mão:
a fonte são os `<id>.json` desta pasta.

Legenda: ✅ decidida · ⏳ pendente · 🔒 bloqueada · ↺ a rever

- ✅ **Objetivo das próximas semanas** — Estabilizar o que existe (27/09/2026) `objetivo-das-semanas`
- ✅ **Modo de trabalho dos agentes** — Vários projetos em paralelo (29/09/2026) · “29/09 01:48, no chat: força total, até 3 agentes — nas palavras dele: Adrian pediu a janela flutuante do guia enquanto a sessão guiada e a sincronização rodam” `modo-de-trabalho`
- ✅ **Teto de uso do Claude** — Outro (comente) (28/09/2026) · “28/09 21:48, pela Mesa de comando: passou de 100% da sessão, para tudo” `teto-de-uso`
- ✅ **Força total antes de renovar: ainda vale?** — Só quando eu pedir (28/09/2026) · “28/09 22:26, pela Mesa de comando: força total só quando eu pedir” `forca-total-ainda-vale`
- ✅ **Capacidade mudada pelo app vira regra?** — Substitui: o que eu mudo no app vira a regra (28/09/2026) `capacidade-pelo-app`
- ✅ **Força total ligada pela Mesa: por quanto tempo?** — Até eu desligar (28/09/2026) `forca-total-pela-mesa`
- ✅ **Teto também no limite semanal?** — Outro (comente) (28/09/2026) · “Controlo isso com a mesa” `teto-da-semana`
- ✅ **Limpeza do disco (C: com 9 GB livres)** — Só o seguro (~1,2 GB) (29/09/2026) `limpeza-do-disco`
- ✅ **E: com 17 GB livres — o cache do Google Drive (186 GB)** — Abrir o Google Drive e deixar ele terminar e limpar sozinho (recomendado primeiro) (29/09/2026) `limpeza-do-disco-e`
- ✅ **Grok: por onde entra na roda?** — grok.com com a sua conta X (gratuito; você loga uma vez) (29/09/2026) `ias-grok-acesso`
- ✅ **Quando você fala com uma IA e a pipeline precisa da mesma conta** — Você: a pipeline espera a sua conversa terminar (29/09/2026) `ias-prioridade-conversa`
- ✅ **Cada IA tem UM chat de longa duração ou um chat novo por assunto?** — Um chat 'casa' por IA, com resumo periódico (29/09/2026) `ias-chat-persistente`
- ⏳ **Fichas das IAs (fase 1): li?** — As 7 fichas de capacidades (Grok, Gemini, ChatGPT, DeepSeek, PicassoIA, DreamFace, Digen) estao prontas em docs/ias/fichas.md e ias/fichas/*.json, medidas nas sessoes guiadas de 29/09 (01:44-02:40) e, para PicassoIA/DreamFace/Digen, pelo padrao em producao. A tabela esta na imagem. Fatos novos para voce ver: (1) a conta do Gemini mostra o selo PLUS em /usage (pool de 5 h + semanal), enquanto a decisao gemini-pago diz 'fica na gratuita'; (2) o PicassoIA limita a 2 geracoes em paralelo (+5 com creditos); (3) o DreamFace nunca gerou em producao; (4) no Grok, Auto/Expert/Heavy, 720p e 10s/15s pedem SuperGrok. `ias-fichas-lidas`
