# Decisões — App e bot

Gerado por `remoto/decisoes.py` a cada resposta. Não edite à mão:
a fonte são os `<id>.json` desta pasta.

Legenda: ✅ decidida · ⏳ pendente · 🔒 bloqueada · ↺ a rever

- ✅ **Quem publica pelo celular** — Só o app (28/09/2026) `quem-publica-pelo-celular`
- ✅ **Destino padrão da publicação** — YouTube e TikTok (28/09/2026) `destino-padrao`
- ✅ **Tailscale sem login (unattended)** — Sim, ligar (28/09/2026) · “falta ele rodar o comando: tailscale set --unattended=true (a permissão do agente barrou)” `tailscale-unattended`
- ✅ **Onde fica pausar / retomar / parar** — Na Bancada, junto dos comandos (28/09/2026) `controle-onde`
- ⏳ **Aviso no Telegram: comando da Mesa sem ninguém ouvindo** — Quando um comando seu na Mesa fica mais de 2 min pendente porque o orquestrador não está ouvindo, o app agora te avisa no Telegram (um aviso por ocorrência) e avisa de novo quando ele volta e aplica. Fica assim? `aviso-no-telegram-comando-da-mesa-sem-ni`
