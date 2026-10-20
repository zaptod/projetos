---
name: conferente-app-390x844
description: Conferir no Chrome de verdade, em 390x844 (e 844x390), uma tela do app do celular que serve ao canal de duelos — o A/B de duelo para o Adrian escolher, a "Análise dos vídeos" na Biblioteca, a Arena, a lista de vídeos, a gravação da voz dele (semana 3) — com servidor e LOCALAPPDATA isolados, coletando erro de console, CSP, imagem quebrada e API com erro, e OLHANDO a captura. Use depois de toda entrega que mexe em remoto/app/** ou remoto/api_http.py, antes de dizer "pronto".
---

# Conferir o app em 390x844

## Procedimento
1. **A prova de tela que já existe** (servidor loopback, LOCALAPPDATA e fichas temporários —
   nunca lê os dados do PC), da worktree da entrega:
   ```powershell
   $env:TEMP="E:\tmp_pytest"; $env:PYTEST_ADDOPTS="-p no:cacheprovider"; $env:NF_TESTE_NAVEGADOR="1"
   python -m pytest remoto/test_app_tela.py -q
   ```
   Medido 20/10 03:2x: **14 passed em 235 s**. Sem `NF_TESTE_NAVEGADOR=1` os testes de tela são
   PULADOS (verde falso). Usa `patchright` com o Chrome instalado, headless, `is_mobile`,
   `service_workers="block"`, claro e escuro.
2. **Capturas** em `%TEMP%\tela_app\` (com o TEMP acima: `E:\tmp_pytest\tela_app\`), nomes
   `390x844-<tema>-<tela>.png` — para o duelo: `videos`, `biblioteca`, `arena`, `decisoes`.
   **Read em cada uma que a entrega tocou**, claro e escuro.
3. **Tela nova ou mudada sem teste**: acrescente um caso no mesmo arquivo seguindo
   `test_o_app_abre_vila_objetos_e_abas_sem_erros_de_tela` (coleta `pageerror`,
   `console.error`, respostas ≥ 400 com a URL, `<img>` com `naturalWidth == 0`) e clique no
   objeto/aba novos — tela que ninguém clicou não foi conferida.
4. Procure: texto cortado, rolagem lateral (`scrollWidth > clientWidth`), botão fora da tela,
   contraste ruim no escuro, imagem quebrada, número velho (o app não pode mostrar dado de
   ontem como de hoje).
5. Devolva `APROVADO` com as capturas olhadas, ou `DEFEITOS` com captura + seletor + causa.

## Armadilhas
- **A captura de "Vídeos" (Cinema) sai com a CORTINA FECHADA** (medido 20/10:
  `390x844-light-videos.png` só mostra a cortina vermelha): o teste passa sem mostrar o
  conteúdo. Para conferir essa tela, espere a abertura da cortina antes do `screenshot` e olhe
  de novo.
- CSP: imagem/arte de outra origem quebra em silêncio na tela, não nos testes de API (02/10).
- Casca nova (`sw.js`) só vale junto com `python -m coordenador reiniciar app` — e reiniciar é
  do orquestrador, fora da janela das postagens (post−12 a post+18). O conferente não reinicia.
- Não abra o app de produção para "testar clicando": ações do app publicam e mexem em fila.

## Checklist
- [ ] `NF_TESTE_NAVEGADOR=1` setado; contagem de passed (não skipped)
- [ ] Read nas capturas das telas tocadas, 390x844 claro e escuro (844x390 se a tela gira)
- [ ] zero `pageerror`/`console.error`/imagem quebrada/API ≥ 400 inesperada
- [ ] tela nova clicada de verdade num teste
