# Perguntas de produto para o Adrian

Aqui só entra o que é escolha dele. O resto está decidido no [`CONTRATO_SLOTS.md`](CONTRATO_SLOTS.md).

Cada pergunta já traz a recomendação. O contrato foi escrito assumindo a recomendação, e trocar qualquer uma delas não muda a estrutura do contrato.

**1. Quais são as partes da bolinha?**
- **Proposta:** 9 camadas, de baixo para cima:
  1. sombra
  2. acessório de costas (capa, asas)
  3. pele
  4. marcas (cicatriz, pintura)
  5. olhos (o par)
  6. sobrancelhas
  7. boca
  8. detalhe do rosto (suor, lágrima, veia)
  9. acessório de cabeça
- **Recomendo:** as 9. Só pele, olhos e boca são obrigatórias; o resto é opcional.
- **Por que sobrancelhas e detalhe:** o rosto de hoje usa os dois para mostrar fúria, medo e tristeza.

**2. Olhos, sobrancelhas e boca mudam com o estado?**
- **Como funciona hoje:** o jogo já transforma o que acontece (apanhou, atordoado, atacando, bloqueando…) numa das **24 expressões**.
- **Recomendo:** sim, pelas expressões, com **6 representantes**: neutro, fúria, animado, pânico, dor e morto. As outras 18 caem no representante até você querer desenhar.
- **O que não muda com o estado:** pele e acessórios. O Godot faz o flash vermelho do dano, o gelo, o piscar e o fantasma.

**3. Pele tingida ou pintada?**
- **Recomendo:** a pele comum vem em tons de cinza e o Godot pinta com a cor de cada personagem. Uma imagem serve aos 106.
- **Exceção:** pele de classe ou de personagem pode vir colorida, e o painel pergunta na hora.

**4. O rosto gira para onde o lutador olha, ou fica sempre de frente?**
- **Hoje:** a luta é vista de cima e o rosto fica na frente da bolinha, girando com o olhar.
- **Recomendo:** manter. O gabarito é a bolinha olhando para a direita, e o Godot gira.

**5. Variação por elemento no lutador?**
- **O problema:** o jogo não dá elemento a um lutador. O elemento só aparece no nome de algumas classes, como "Piromante (Fogo)".
- **Recomendo:** não criar o nível elemento no lutador. Os níveis ficam comum → classe → personagem.
- **Onde o elemento continua valendo:** skills, efeitos e encantamento, onde o jogo realmente usa elemento.

**6. Quando a classe tem olhos próprios, mas não desenhou a expressão pedida, o que entra?**
- **Recomendo:** o **neutro da própria classe**, para não misturar o olho do Berserker com o olho comum.
- **A alternativa:** entrar o olho comum daquela expressão. O rosto reage, mas troca de estilo no meio da luta.

**7. Efeitos de impacto (acerto, KO, conjuração): imagem parada ou folha de quadros?**
- **Recomendo:** os dois. O padrão é a imagem parada, que o Godot anima com cresce, gira e some. A folha 4×4 continua aceita para quem quiser desenhar quadro a quadro.

**8. O que fazer com o que o Ateliê tem hoje?**
- **O catálogo:** o Ateliê guarda animações de lado (`parado_direita`, `ataque_leve_esquerda`…), que não servem para a bolinha modular.
- **As duas artes de 02/10:** "corpo_bolinha" e "classe_berserker" foram salvas como skill e **nunca aparecem na luta**.
- **Recomendo:**
  - trocar o catálogo pelos slots de parte;
  - mover as duas artes para **pele comum** e **acessório de cabeça do Berserker**.

**9. Vitória e entrada.**
- **Hoje:** o jogo não tem pose de vitória nem animação de entrada. A vitória é "o vivo quando a luta acaba".
- **Recomendo:** não criar slot agora. Na vitória, o Godot usa a expressão "eufórico" com um pulinho.
- **Entrada:** vira pedido separado, se você quiser.
