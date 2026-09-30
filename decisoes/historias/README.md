# Decisões — Histórias

Gerado por `remoto/decisoes.py` a cada resposta. Não edite à mão:
a fonte são os `<id>.json` desta pasta.

Legenda: ✅ decidida · ⏳ pendente · 🔒 bloqueada · ↺ a rever

- ✅ **Vídeo reprovado ou não assistido** — Fica retido; só sai se o horário fosse ficar vazio (27/09/2026) `reprovado-ou-nao-assistido`
- ✅ **Gemini pago** — Não: fica na gratuita (28/09/2026) `gemini-pago`
- ✅ **Reprovados que já estão no ar** — Manter no ar (28/09/2026) `reprovados-no-ar`
- ✅ **Rodada de histórias travada há 10 h segurando a trava** — Matar o PID 7300 agora e deixar a próxima rodada retomar a 00038 (29/09/2026) `rodada-travada-7300`
- ⏳ **Histórias: teto diário de imagens no PicassoIA** — Quantos envios de imagem por dia as histórias podem fazer na conta compartilhada do PicassoIA? Ao bater, a geração para e avisa no Telegram. `teto-diario-picasso`
