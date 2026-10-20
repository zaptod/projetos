---
name: builds-voz-do-duelo
description: Pôr ou conferir VOZ no vídeo do Neural Fights — a frase falada no 1º segundo do duelo ("Sword versus Dagger, who wins?"), a troca da narração para inglês, a voz do Adrian gravada no celular (semana 3 do plano), ou investigar narração robótica, cortada, muda ou "pipocando". Use antes de mexer em `builds/content/voz.py`, no bloco `audio.voz` do `config/render.json` ou em qualquer mixagem de fala.
---

# Voz no duelo

**Estado em 20/10/2026:** o duelo NÃO tem voz; só a roleta (build) narra, por
`builds/content/voz.py` (edge-tts, reserva SAPI do Windows), voz `pt-BR-AntonioNeural` em
`random_builds/config/render.json → audio.voz`. O plano pede: semana 1, o que o público ouve em
inglês (decisão `geral/canal-em-ingles`); semana 3, teste da voz do Adrian (3 narrados × 3 sem).
Pesquisa (docs/pesquisa/shorts-que-deram-certo.md §5): 6/12 canais que cresceram NÃO têm voz;
2/12 usam UMA frase no 1º segundo ("Vampire versus Toxic Spike, who will win?"). Voz parece
criar vínculo (inscrito), não segurar o swipe — meça inscritos/mil views, não só % assistido.

## Procedimento
1. **O motor responde?** `python -m edge_tts --voice en-US-GuyNeural --text "Who wins?" --write-media E:\tmp_pytest\t.mp3`.
   403 = pacote velho (a 7.2.8 levou 403 de 12 a 19/10 em silêncio); hoje 7.3.1
   (`pyproject` exige ≥ 7.3.1). Processo longo aberto antes do conserto segue com o módulo velho.
2. **Ouça pelo caminho real** com o conferidor (cache descartável, nunca o de produção):
   `python .claude/skills/builds-voz-do-duelo/scripts/conferir_fala.py "Sword VS Dagger. Who wins?" --voz en-US-GuyNeural`
   Saída 0 = edge; **3 = caiu na reserva SAPI** (voz do Windows); confira `texto_falado`.
3. Para trocar a língua, mude `audio.voz` (`voz`, e `voz_sapi` para "Zira" ou "David" — a
   reserva "Maria" leria inglês com sotaque) e trate o `falavel` (abaixo). O cache é por
   motor|voz|taxa|tom|texto: voz nova = cache novo, nada a apagar.
4. Mixagem: a voz entra com ducking da música (`render.json → audio.ducking`) e o vídeo sai no
   `loudnorm` -14; a régua de áudio da publicação mede o resultado (skill `conferente-video-mp4`).
5. **Som só o Adrian julga** — o Gemini não recebe o áudio. Mande o mp4 para ele no A/B.

## Armadilhas que já custaram caro
- **`voz.falavel` é pt-BR**: troca "KO" por "nocaute", "kg" por "quilos", "/100" por "de 100",
  "IA" por "inteligência artificial". Medido agora: "Sword VS Dagger. Who wins? KO" sai falado
  "…Who wins? nocaute." com a voz inglesa. Inglês precisa de outra tabela `_SUBS`.
- **A reserva SAPI é silenciosa**: `sintetizar` cai no Windows e o render segue; só o log diz
  `[voz] edge: ...`. 51 roletas (generation_00126–00185) saíram com a voz do Windows em 12–19/10
  (decisão `builds/voz-do-windows-12-a-19-10`: refazer só se forem publicadas).
- **Cache envenenado**: mp3 truncado era servido para sempre; hoje `motivo_do_cache_ruim` +
  `implausivel` (fora de 1,0–4,0 palavras/s, calibrado em pt-BR; com < 12 palavras não afere —
  a frase do 1º segundo NÃO é aferida, ouça).
- **Pipoco**: trocar o "entre palavras" por zero absoluto fazia a voz sumir 2,6x/s
  (`respirar`, 10/09). Conte com `conferir_fala.py --wav <voz.wav>` (hoje 0,02/s numa roleta boa).
- Detalhe do motor e da voz do Adrian: [reference/motor-e-voz-do-adrian.md](reference/motor-e-voz-do-adrian.md).

## Checklist antes de entregar
- [ ] `conferir_fala.py` saiu 0 (edge), com a voz certa e `texto_falado` sem português
- [ ] `--wav` no áudio final: pipocos/s ≈ 0; fala dentro do 1º segundo quando é a pergunta
- [ ] mp4 medido (LUFS, pico ≤ -1 dBTP, `regua_da_publicacao` ok) e quadros olhados
- [ ] A/B para o Adrian ouvir (ele é o único juiz de som)
