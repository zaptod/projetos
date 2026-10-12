# Decisões — Histórias

Gerado por `remoto/decisoes.py` a cada resposta. Não edite à mão:
a fonte são os `<id>.json` desta pasta.

Legenda: ✅ decidida · ⏳ pendente · 🔒 bloqueada · ↺ a rever

- ✅ **Vídeo reprovado ou não assistido** — Fica retido; só sai se o horário fosse ficar vazio (27/09/2026) `reprovado-ou-nao-assistido`
- ✅ **Gemini pago** — Não: fica na gratuita (28/09/2026) `gemini-pago`
- ✅ **Reprovados que já estão no ar** — Manter no ar (28/09/2026) `reprovados-no-ar`
- ✅ **Rodada de histórias travada há 10 h segurando a trava** — Matar o PID 7300 agora e deixar a próxima rodada retomar a 00038 (29/09/2026) `rodada-travada-7300`
- ✅ **Histórias: teto diário de imagens no PicassoIA** — Sem teto (30/09/2026) `teto-diario-picasso`
- ✅ **Imagens das histórias: como dividir entre Gemini, ChatGPT e PicassoIA** — Um gerador por história (recomendado) (03/10/2026) `imagens-divisao`
- ✅ **IA olha de novo a parte consertada?** — Não, manter uma passada só (05/10/2026) `reolhar-depois-do-conserto`
- ✅ **Títulos com o nome da série no meio** — Tirar a marca da frente (06/10/2026) `titulo-marca-no-meio`
- ✅ **Imagens sem o PicassoIA: Gemini e ChatGPT trabalham juntos?** — Duas histórias ao mesmo tempo, uma em cada gerador (recomendado) (06/10/2026) `imagens-dois-geradores-juntos`
- ✅ **Pausa dos canais de histórias** — Continuar publicando (11/10/2026) · “11/10 04h pelo chat: 'eu ja nao quero mais que o builds pare nem o canal de historias'” `pausa-dos-canais`
  - ↺ **Criar histórias durante a pausa?** — Parar a criação também (10/10/2026) · “10/10 01:4x pelo chat: 'por que ainda esta abrindo meu chat gpt??' (a criacao gerava imagens no ChatGPT dele durante a pausa)” · espera Pausa dos canais de histórias = Pausar a publicação `criacao-durante-a-pausa`
- ⏳ **Gemini sem o modelo forte pode escrever roteiro?** — Quando o Gemini não consegue entrar no modelo forte (Pro), hoje a história é escrita no Flash sem avisar você (224 vezes de 06 a 08/10). O que fazer? `gemini-sem-pro-escreve`
