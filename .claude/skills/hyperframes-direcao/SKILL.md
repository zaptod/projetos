---
name: hyperframes-direcao
description: Direção de vídeo curto vertical: roteiro que retém (gancho no quadro 0, laços abertos, virada, convite para o próximo), visual (zonas seguras do 9:16, ritmo de 1–2 s por plano, legenda por grupos de palavras, sem "cara de vídeo gerado") e som (trilha com um momento de mudança, efeitos reais poucos e exatos, níveis para celular). Use antes de roteirizar, montar ou revisar um vídeo do canal — série do Blue Lock, duelos, histórias — em HyperFrames, ffmpeg ou editor.
---

# Direção de vídeo curto (guias oficiais do HyperFrames)

Guias em texto do repositório oficial da HeyGen (`references/`, Apache-2.0, ver `ORIGEM.md`). Esta página é o índice e as regras da casa. Para o contrato técnico da composição, use `hyperframes-core`; para movimento de câmera e keyframes, `hyperframes-keyframes`.

## Ler conforme a tarefa

| Tarefa | Ler |
| --- | --- |
| Roteiro de qualquer vídeo que conta algo (>15 s) | `references/story.md` (a coisa única, gancho, beats, cara de vídeo gerado) |
| Vídeo vertical para TikTok/Shorts/Reels | `references/types/vertical.md` (zonas da interface, 1º segundo, ritmo) |
| Explicar uma ideia ("como funciona") | `references/types/explainer.md` (exemplo concreto, diagrama que cresce, mito virado) |
| Som: trilha, efeitos, níveis | `references/sound.md`, `references/audio/sfx.md`, `references/audio/bgm.md` |
| Legenda queimada | `references/captions.md`, `references/audio/captions/*.md` |
| Movimento, transições, câmera | `references/motion.md` |
| Paleta, tipo, materiais | `references/look.md`; montagem sobre música: `references/film.md` |
| Revisar antes de entregar | `references/review.md` |

## O essencial (resumo dos guias)

- **Quadro 0 é a miniatura e o gancho:** uma frase forte já na tela, mais a imagem que cria a pergunta. Nunca preto, nunca logo.
- **Zonas do 9:16 (1080×1920):** nada nos 168 px de cima; todo texto e o assunto entre 168 e 1330 px; abaixo de 1330 só textura; nada sob a coluna de botões à direita. A legenda fica no pé dessa faixa.
- **Ritmo:** planos de 1–2 s, um beat novo a cada 2–4 s, o payoff antes do swipe. O payoff fica a 60–80% do vídeo.
- **Texto:** no máximo 5 palavras por linha num título, sem ponto final, e nunca repetindo a fala palavra por palavra. A legenda vai em grupos de 3–5 palavras, um grupo por vez, presa ao tempo da palavra.
- **Mostrar, não listar:** nada de três cartões em fila, slides de tópicos ou prints pequenos boiando num fundo escuro.
- **Som:** trilha com pulso que entra no compasso forte e tem **um** momento de mudança (silêncio antes da virada, e a música abre no payoff). Os efeitos são poucos e exatos, cada um com causa na tela, alternando 2–3 versões do mesmo som; riser e impacto só uma vez. **Nenhum tom sintetizado.** Voz como relógio; trilha ~0,14 de volume sob a voz; −14 a −16 LUFS e pico real ≤ −1 dBTP.
- **Cara de vídeo gerado (proibido):** fundo escuro com coisas pequenas flutuando, brilho e partículas, tudo entrando com fade e subindo, a mesma entrada cena após cena, logo encaixado no canto, títulos que continuam deslizando depois de assentar.

## Regras da casa (acima dos guias)

1. **CLI proibido** nestes subcomandos: `feedback`, `events`, `cloud`, `auth`, `lambda`, `cloudrun`, `publish`, `capture`, `usage`, `open`, `catch-up`, `skills`, `upgrade` (ver `hyperframes-core/ORIGEM.md`). Toda chamada com `HYPERFRAMES_NO_TELEMETRY=1`, `HYPERFRAMES_SKIP_SKILLS=1` e `HYPERFRAMES_NO_UPDATE_CHECK=1`; versão fixa `hyperframes@0.8.181`.
2. **Sem serviços pagos nem contas** (voz HeyGen, música de catálogo, avatar). Música: CC0 ou domínio público com fonte anotada. Efeitos: a biblioteca do Pixabay copiada em `E:\BLUE-Lock-serie-capturas\sfx_pixabay\` (Licença Pixabay, uso livre sem atribuição) ou CC0/CC BY com crédito.
3. **Honestidade antes da estética:** captura real; ilustração, cenário e efeito de edição levam selo.
4. **Série do Blue Lock:** valem também as regras do Adrian (memória `serie-blue-lock-regras-do-adrian`): nada de IA de desenvolvimento, nada técnico, nada do GitHub.
5. **Som não se julga pelo arquivo:** medir (ebur128) e dizer que foi medido, não ouvido. Quem ouve é o Adrian.
