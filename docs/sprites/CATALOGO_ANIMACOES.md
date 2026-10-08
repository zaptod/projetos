# Catálogo de animações

Gerado por `python -m neural_fights.tools.catalogo_animacoes`. Não edite esta lista à mão.

O catálogo traz a hierarquia estável do jogo. Armas e personagens do banco usam a arte do estilo/classe; só recebem uma sobrescrita quando o Adrian decidir criar uma.

## Resumo

| Grupo | Peças | Estados | Animações |
| --- | ---: | ---: | ---: |
| arma | 63 | 176 | 176 |
| buff | 6 | 6 | 6 |
| efeito | 38 | 51 | 51 |
| elemento | 12 | 12 | 12 |
| estado_personagem | 47 | 47 | 47 |
| lutador | 21 | 115 | 163 |
| skill | 127 | 254 | 254 |

## arma

| Peça | Estado | Animação | Quando toca | Loop | Tamanho / âncora |
| --- | --- | --- | --- | --- | --- |
| Adagas Gêmeas | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Adagas Gêmeas | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Alabarda | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Alabarda | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Arco Composto | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Arco Composto | Puxar a corda | Puxar | `arma_puxada` | não | 1,0 do corpo / mao |
| Arco Composto | Disparo | Disparo | `projetil_arma` | não | 1,0 do corpo / mao |
| Arco Curto | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Arco Curto | Puxar a corda | Puxar | `arma_puxada` | não | 1,0 do corpo / mao |
| Arco Curto | Disparo | Disparo | `projetil_arma` | não | 1,0 do corpo / mao |
| Arco Élfico | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Arco Élfico | Puxar a corda | Puxar | `arma_puxada` | não | 1,0 do corpo / mao |
| Arco Élfico | Disparo | Disparo | `projetil_arma` | não | 1,0 do corpo / mao |
| Arco-Lâminas | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Arco-Lâminas | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Arco-Lâminas | Forma 1 | Forma 1 | `ocioso` | sim | 1,0 do corpo / mao |
| Arco-Lâminas | Forma 2 | Forma 2 | `ocioso` | sim | 1,0 do corpo / mao |
| Arco-Lâminas | Transformar | Transformar | `transformado` | não | 1,0 do corpo / mao |
| Arco Longo | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Arco Longo | Puxar a corda | Puxar | `arma_puxada` | não | 1,0 do corpo / mao |
| Arco Longo | Disparo | Disparo | `projetil_arma` | não | 1,0 do corpo / mao |
| Bastão Segmentado | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Bastão Segmentado | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Bastão Segmentado | Forma 1 | Forma 1 | `ocioso` | sim | 1,0 do corpo / mao |
| Bastão Segmentado | Forma 2 | Forma 2 | `ocioso` | sim | 1,0 do corpo / mao |
| Bastão Segmentado | Transformar | Transformar | `transformado` | não | 1,0 do corpo / mao |
| Besta Leve | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Besta Leve | Puxar a corda | Puxar | `arma_puxada` | não | 1,0 do corpo / mao |
| Besta Leve | Disparo | Disparo | `projetil_arma` | não | 1,0 do corpo / mao |
| Besta Pesada | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Besta Pesada | Puxar a corda | Puxar | `arma_puxada` | não | 1,0 do corpo / mao |
| Besta Pesada | Disparo | Disparo | `projetil_arma` | não | 1,0 do corpo / mao |
| Bumerangue | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Bumerangue | Lançar | Lançar | `golpe_fase` | não | 1,0 do corpo / mao |
| Bumerangue | Projétil voando | Voando | `projetil_arma` | sim | 1,0 do corpo / mao |
| Bumerangue | Retorno | Retorno | `projetil_fim` | não | 1,0 do corpo / mao |
| Chakram | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Chakram | Lançar | Lançar | `golpe_fase` | não | 1,0 do corpo / mao |
| Chakram | Projétil voando | Voando | `projetil_arma` | sim | 1,0 do corpo / mao |
| Chakram | Retorno | Retorno | `projetil_fim` | não | 1,0 do corpo / mao |
| Chamas Espirituais | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Chamas Espirituais | Carregando | Carregar | `orbe` | sim | 1,0 do corpo / mao |
| Chamas Espirituais | Disparando | Disparar | `orbe` | não | 1,0 do corpo / mao |
| Chicote | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Chicote | Girando | Girar | `golpe_fase` | sim | 1,0 do corpo / mao |
| Chicote | Arremesso | Arremessar | `bola_x` | não | 1,0 do corpo / mao |
| Chicote-Espada | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Chicote-Espada | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Chicote-Espada | Forma 1 | Forma 1 | `ocioso` | sim | 1,0 do corpo / mao |
| Chicote-Espada | Forma 2 | Forma 2 | `ocioso` | sim | 1,0 do corpo / mao |
| Chicote-Espada | Transformar | Transformar | `transformado` | não | 1,0 do corpo / mao |
| Claymore | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Claymore | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Corrente com Peso | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Corrente com Peso | Girando | Girar | `golpe_fase` | sim | 1,0 do corpo / mao |
| Corrente com Peso | Arremesso | Arremessar | `bola_x` | não | 1,0 do corpo / mao |
| Cristais Arcanos | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Cristais Arcanos | Carregando | Carregar | `orbe` | sim | 1,0 do corpo / mao |
| Cristais Arcanos | Disparando | Disparar | `orbe` | não | 1,0 do corpo / mao |
| Cristais Flutuantes | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Drones de Combate | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Escudo Orbital | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Espada Curta | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Espada Curta | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Espada Extensível | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Espada Extensível | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Espada Extensível | Forma 1 | Forma 1 | `ocioso` | sim | 1,0 do corpo / mao |
| Espada Extensível | Forma 2 | Forma 2 | `ocioso` | sim | 1,0 do corpo / mao |
| Espada Extensível | Transformar | Transformar | `transformado` | não | 1,0 do corpo / mao |
| Espada-Lança | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Espada-Lança | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Espada-Lança | Forma 1 | Forma 1 | `ocioso` | sim | 1,0 do corpo / mao |
| Espada-Lança | Forma 2 | Forma 2 | `ocioso` | sim | 1,0 do corpo / mao |
| Espada-Lança | Transformar | Transformar | `transformado` | não | 1,0 do corpo / mao |
| Espada Longa | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Espada Longa | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Espadas Espectrais | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Espadas Espectrais | Carregando | Carregar | `orbe` | sim | 1,0 do corpo / mao |
| Espadas Espectrais | Disparando | Disparar | `orbe` | não | 1,0 do corpo / mao |
| Facas de Arremesso | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Facas de Arremesso | Lançar | Lançar | `golpe_fase` | não | 1,0 do corpo / mao |
| Facas de Arremesso | Projétil voando | Voando | `projetil_arma` | sim | 1,0 do corpo / mao |
| Facas de Arremesso | Retorno | Retorno | `projetil_fim` | não | 1,0 do corpo / mao |
| Facas Táticas | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Facas Táticas | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Foice | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Foice | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Garras | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Garras | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Kamas | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Kamas | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Katana | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Katana | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Kunai | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Kunai | Lançar | Lançar | `golpe_fase` | não | 1,0 do corpo / mao |
| Kunai | Projétil voando | Voando | `projetil_arma` | sim | 1,0 do corpo / mao |
| Kunai | Retorno | Retorno | `projetil_fim` | não | 1,0 do corpo / mao |
| Kusarigama | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Kusarigama | Girando | Girar | `golpe_fase` | sim | 1,0 do corpo / mao |
| Kusarigama | Arremesso | Arremessar | `bola_x` | não | 1,0 do corpo / mao |
| Lâminas Orbitais | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Lança | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Lança | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Lanças de Mana | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Lanças de Mana | Carregando | Carregar | `orbe` | sim | 1,0 do corpo / mao |
| Lanças de Mana | Disparando | Disparar | `orbe` | não | 1,0 do corpo / mao |
| Maça | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Maça | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Machado | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Machado | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Machado-Martelo | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Machado-Martelo | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Machado-Martelo | Forma 1 | Forma 1 | `ocioso` | sim | 1,0 do corpo / mao |
| Machado-Martelo | Forma 2 | Forma 2 | `ocioso` | sim | 1,0 do corpo / mao |
| Machado-Martelo | Transformar | Transformar | `transformado` | não | 1,0 do corpo / mao |
| Machados de Arremesso | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Machados de Arremesso | Lançar | Lançar | `golpe_fase` | não | 1,0 do corpo / mao |
| Machados de Arremesso | Projétil voando | Voando | `projetil_arma` | sim | 1,0 do corpo / mao |
| Machados de Arremesso | Retorno | Retorno | `projetil_fim` | não | 1,0 do corpo / mao |
| Mangual | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Mangual | Girando | Girar | `golpe_fase` | sim | 1,0 do corpo / mao |
| Mangual | Arremesso | Arremessar | `bola_x` | não | 1,0 do corpo / mao |
| Martelo | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Martelo | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Meteor Hammer | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Meteor Hammer | Girando | Girar | `golpe_fase` | sim | 1,0 do corpo / mao |
| Meteor Hammer | Arremesso | Arremessar | `bola_x` | não | 1,0 do corpo / mao |
| Montante | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Montante | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Orbes Místicos | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Rope Dart | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Rope Dart | Girando | Girar | `golpe_fase` | sim | 1,0 do corpo / mao |
| Rope Dart | Arremesso | Arremessar | `bola_x` | não | 1,0 do corpo / mao |
| Runas Flutuantes | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Runas Flutuantes | Carregando | Carregar | `orbe` | sim | 1,0 do corpo / mao |
| Runas Flutuantes | Disparando | Disparar | `orbe` | não | 1,0 do corpo / mao |
| Sabre | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Sabre | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Sai | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Sai | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Sentinelas | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Shuriken | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Shuriken | Lançar | Lançar | `golpe_fase` | não | 1,0 do corpo / mao |
| Shuriken | Projétil voando | Voando | `projetil_arma` | sim | 1,0 do corpo / mao |
| Shuriken | Retorno | Retorno | `projetil_fim` | não | 1,0 do corpo / mao |
| Tentáculos Sombrios | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Tentáculos Sombrios | Carregando | Carregar | `orbe` | sim | 1,0 do corpo / mao |
| Tentáculos Sombrios | Disparando | Disparar | `orbe` | não | 1,0 do corpo / mao |
| Tonfas | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Tonfas | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Arma Arco | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Arma Arco | Puxar a corda | Puxar | `arma_puxada` | não | 1,0 do corpo / mao |
| Arma Arco | Disparo | Disparo | `projetil_arma` | não | 1,0 do corpo / mao |
| Arma Arremesso | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Arma Arremesso | Lançar | Lançar | `golpe_fase` | não | 1,0 do corpo / mao |
| Arma Arremesso | Projétil voando | Voando | `projetil_arma` | sim | 1,0 do corpo / mao |
| Arma Arremesso | Retorno | Retorno | `projetil_fim` | não | 1,0 do corpo / mao |
| Arma Corrente | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Arma Corrente | Girando | Girar | `golpe_fase` | sim | 1,0 do corpo / mao |
| Arma Corrente | Arremesso | Arremessar | `bola_x` | não | 1,0 do corpo / mao |
| Cabeça da corrente | Parada | Parada | `ocioso` | sim | 0,4 do corpo / bola da corrente |
| Cabeça da corrente | Girando | Girando | `bola_x` | sim | 0,4 do corpo / bola da corrente |
| Cabeça da corrente | Arremesso | Arremesso | `bola_x` | não | 0,4 do corpo / bola da corrente |
| Arma Dupla | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Arma Dupla | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Arma Mágica | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Arma Mágica | Carregando | Carregar | `orbe` | sim | 1,0 do corpo / mao |
| Arma Mágica | Disparando | Disparar | `orbe` | não | 1,0 do corpo / mao |
| Arma Orbital | Orbitando | Orbitar | `orbe` | sim | 1,0 do corpo / mao |
| Arma Reta | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Arma Reta | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Arma Transformável | Parada | Parada | `ocioso` | sim | 1,0 do corpo / mao |
| Arma Transformável | Golpe | Golpe | `golpe_fase` | não | 1,0 do corpo / mao |
| Arma Transformável | Forma 1 | Forma 1 | `ocioso` | sim | 1,0 do corpo / mao |
| Arma Transformável | Forma 2 | Forma 2 | `ocioso` | sim | 1,0 do corpo / mao |
| Arma Transformável | Transformar | Transformar | `transformado` | não | 1,0 do corpo / mao |

## buff

| Peça | Estado | Animação | Quando toca | Loop | Tamanho / âncora |
| --- | --- | --- | --- | --- | --- |
| Abençoado | Ativo | Ativo | `buff` | sim | 1,2 do corpo / centro do corpo |
| Acelerado | Ativo | Ativo | `buff` | sim | 1,2 do corpo / centro do corpo |
| Determinado | Ativo | Ativo | `buff` | sim | 1,2 do corpo / centro do corpo |
| Furia | Ativo | Ativo | `buff` | sim | 1,2 do corpo / centro do corpo |
| Imortal | Ativo | Ativo | `buff` | sim | 1,2 do corpo / centro do corpo |
| Regenerando | Ativo | Ativo | `buff` | sim | 1,2 do corpo / centro do corpo |

## efeito

| Peça | Estado | Animação | Quando toca | Loop | Tamanho / âncora |
| --- | --- | --- | --- | --- | --- |
| area | Surgir | Surgir | `skill` | não | 1,0 do corpo / ponto do evento |
| area | Ativo | Ativo | `area` | sim | 1,0 do corpo / ponto do evento |
| area | Impacto | Impacto | `explosao` | não | 1,0 do corpo / ponto do evento |
| beam | Surgir | Surgir | `skill` | não | 1,0 do corpo / ponto do evento |
| beam | Ativo | Ativo | `beam` | sim | 1,0 do corpo / ponto do evento |
| orbe | Surgir | Surgir | `skill` | não | 1,0 do corpo / ponto do evento |
| orbe | Orbitando | Orbitar | `orbe` | sim | 0,5 do corpo / centro do orbe |
| portal | Surgir | Surgir | `skill` | não | 1,0 do corpo / ponto do evento |
| portal | Ativo | Ativo | `portal` | sim | 1,0 do corpo / ponto do evento |
| projetil | Surgir | Surgir | `skill` | não | 1,0 do corpo / ponto do evento |
| projetil | Voando | Voando | `projetil` | sim | 0,4 do corpo / centro do projétil |
| projetil | Impacto | Impacto | `acerto` | não | 0,7 do corpo / ponto do evento |
| projetil | Sumir | Sumir | `projetil_fim` | não | 0,4 do corpo / ponto do evento |
| Projétil arma | Surgir | Surgir | `skill` | não | 1,0 do corpo / ponto do evento |
| Projétil arma | Voando | Voando | `projetil_arma` | sim | 0,4 do corpo / centro do projétil |
| Projétil arma | Impacto | Impacto | `acerto` | não | 0,7 do corpo / ponto do evento |
| Projétil arma | Sumir | Sumir | `projetil_fim` | não | 0,4 do corpo / ponto do evento |
| summon | Surgir | Surgir | `skill` | não | 1,0 do corpo / ponto do evento |
| summon | Ativo | Ativo | `summon` | sim | 1,0 do corpo / ponto do evento |
| trap | Surgir | Surgir | `skill` | não | 1,0 do corpo / ponto do evento |
| trap | Ativo | Ativo | `trap` | sim | 1,0 do corpo / ponto do evento |
| acerto | Disparo | acerto | `acerto` | não | 0,8 do corpo / ponto do evento |
| agarrao | Disparo | agarrao | `agarrao` | não | 0,8 do corpo / ponto do evento |
| Agarrão desfecho | Disparo | Agarrão desfecho | `agarrao_desfecho` | não | 0,8 do corpo / ponto do evento |
| bloqueio | Disparo | bloqueio | `bloqueio` | não | 0,8 do corpo / ponto do evento |
| choque | Disparo | choque | `choque` | não | 0,8 do corpo / ponto do evento |
| combo | Disparo | combo | `combo` | não | 0,8 do corpo / ponto do evento |
| cura | Disparo | cura | `cura` | não | 0,8 do corpo / ponto do evento |
| dano | Disparo | dano | `dano` | não | 0,8 do corpo / ponto do evento |
| dash | Disparo | dash | `dash` | não | 0,8 do corpo / ponto do evento |
| desvio | Disparo | desvio | `desvio` | não | 0,8 do corpo / ponto do evento |
| Escudo quebrou | Disparo | Escudo quebrou | `escudo_quebrou` | não | 0,8 do corpo / ponto do evento |
| esquiva | Disparo | esquiva | `esquiva` | não | 0,8 do corpo / ponto do evento |
| explosao | Disparo | explosao | `explosao` | não | 0,8 do corpo / ponto do evento |
| hitstop | Disparo | hitstop | `hitstop` | não | 0,8 do corpo / ponto do evento |
| ko | Disparo | ko | `ko` | não | 0,8 do corpo / ponto do evento |
| movimento | Disparo | movimento | `movimento` | não | 0,8 do corpo / ponto do evento |
| obstaculo | Disparo | obstaculo | `obstaculo` | não | 0,8 do corpo / ponto do evento |
| parede | Disparo | parede | `parede` | não | 0,8 do corpo / ponto do evento |
| parry | Disparo | parry | `parry` | não | 0,8 do corpo / ponto do evento |
| Primeiro sangue | Disparo | Primeiro sangue | `primeiro_sangue` | não | 0,8 do corpo / ponto do evento |
| Projétil fim | Disparo | Projétil fim | `projetil_fim` | não | 0,8 do corpo / ponto do evento |
| skill | Disparo | skill | `skill` | não | 0,8 do corpo / ponto do evento |
| Wall splat | Disparo | Wall splat | `wall_splat` | não | 0,8 do corpo / ponto do evento |
| aterrissagem | Ação | aterrissagem | `aterrissagem` | não | 1,0 do corpo / ponto do evento |
| corrida | Ação | corrida | `corrida` | não | 1,0 do corpo / ponto do evento |
| dash | Ação | dash | `dash` | não | 1,0 do corpo / ponto do evento |
| knockback | Ação | knockback | `knockback` | não | 1,0 do corpo / ponto do evento |
| poeira | Ação | poeira | `poeira` | não | 1,0 do corpo / ponto do evento |
| pulo | Ação | pulo | `pulo` | não | 1,0 do corpo / ponto do evento |
| recuperacao | Ação | recuperacao | `recuperacao` | não | 1,0 do corpo / ponto do evento |

## elemento

| Peça | Estado | Animação | Quando toca | Loop | Tamanho / âncora |
| --- | --- | --- | --- | --- | --- |
| Arcano | Ativo | Brilho | `skill` | sim | 0,8 do corpo / ponto do evento |
| Caos | Ativo | Brilho | `skill` | sim | 0,8 do corpo / ponto do evento |
| Fogo | Ativo | Brilho | `skill` | sim | 0,8 do corpo / ponto do evento |
| Gelo | Ativo | Brilho | `skill` | sim | 0,8 do corpo / ponto do evento |
| Gravitação | Ativo | Brilho | `skill` | sim | 0,8 do corpo / ponto do evento |
| Luz | Ativo | Brilho | `skill` | sim | 0,8 do corpo / ponto do evento |
| Natureza | Ativo | Brilho | `skill` | sim | 0,8 do corpo / ponto do evento |
| Raio | Ativo | Brilho | `skill` | sim | 0,8 do corpo / ponto do evento |
| Sangue | Ativo | Brilho | `skill` | sim | 0,8 do corpo / ponto do evento |
| Tempo | Ativo | Brilho | `skill` | sim | 0,8 do corpo / ponto do evento |
| Trevas | Ativo | Brilho | `skill` | sim | 0,8 do corpo / ponto do evento |
| Void | Ativo | Brilho | `skill` | sim | 0,8 do corpo / ponto do evento |

## estado_personagem

| Peça | Estado | Animação | Quando toca | Loop | Tamanho / âncora |
| --- | --- | --- | --- | --- | --- |
| Atordoado | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Bomba relógio | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Cego | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Charme | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Congelado | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Corroendo | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Enraizado | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Envenenado | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Exausto | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Exposto | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Fraco | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Knock up | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Lento | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Link alma | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Maldito | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Marcado | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Medo | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Necrose | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Paralisia | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Possesso | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Puxado | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Queimando | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Sangrando | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Silenciado | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Sono | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Tempo parado | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Trocar pos | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Vortex | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| Vulnerável | Ativo | Ativo | `status` | sim | 1,15 do corpo / centro do corpo |
| adrenalina | Ativo | Ativo | `adrenalina` | sim | 1,0 do corpo / centro do corpo |
| agarrado | Ativo | Ativo | `agarrado` | sim | 1,0 do corpo / centro do corpo |
| atacando | Ativo | Ativo | `atacando` | sim | 1,0 do corpo / centro do corpo |
| atordoado | Ativo | Ativo | `atordoado` | sim | 1,0 do corpo / centro do corpo |
| bloqueando | Ativo | Ativo | `bloqueando` | sim | 1,0 do corpo / centro do corpo |
| canalizando | Ativo | Ativo | `canalizando` | sim | 1,0 do corpo / centro do corpo |
| congelado | Ativo | Ativo | `congelado` | sim | 1,0 do corpo / centro do corpo |
| dash | Ativo | Ativo | `dash` | sim | 1,0 do corpo / centro do corpo |
| dormindo | Ativo | Ativo | `dormindo` | sim | 1,0 do corpo / centro do corpo |
| intangivel | Ativo | Ativo | `intangivel` | sim | 1,0 do corpo / centro do corpo |
| invencivel | Ativo | Ativo | `invencivel` | sim | 1,0 do corpo / centro do corpo |
| lancado | Ativo | Ativo | `lancado` | sim | 1,0 do corpo / centro do corpo |
| morto | Ativo | Ativo | `morto` | sim | 1,0 do corpo / centro do corpo |
| No ar | Ativo | Ativo | `no_ar` | sim | 1,0 do corpo / centro do corpo |
| oculto | Ativo | Ativo | `oculto` | sim | 1,0 do corpo / centro do corpo |
| Super armor | Ativo | Ativo | `super_armor` | sim | 1,0 do corpo / centro do corpo |
| Tempo parado | Ativo | Ativo | `tempo_parado` | sim | 1,0 do corpo / centro do corpo |
| transformado | Ativo | Ativo | `transformado` | sim | 1,0 do corpo / centro do corpo |

## lutador

| Peça | Estado | Animação | Quando toca | Loop | Tamanho / âncora |
| --- | --- | --- | --- | --- | --- |
| Assassino (Crítico) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Berserker (Fúria) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Cavaleiro (Defesa) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Criomante (Gelo) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Druida (Natureza) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Duelista (Precisão) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Feiticeiro (Caos) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Gladiador (Combate) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Guerreiro (Força Bruta) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Ladino (Evasão) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Mago (Arcano) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Monge (Chi) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Necromante (Trevas) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Ninja (Velocidade) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Paladino (Sagrado) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Piromante (Fogo) | Base | Ociosa | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Corpo e pele | Parado | Parado | `ocioso` | sim | 1,0 do corpo / centro do corpo |
| Corpo e pele | Dano | Dano | `acerto` | não | 1,0 do corpo / centro do corpo |
| Corpo e pele | Nocaute | Nocaute | `ko` | não | 1,0 do corpo / centro do corpo |
| boca | neutro | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | neutro | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | focado | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | focado | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | glacial | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | glacial | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | determinado | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | determinado | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | furia | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | furia | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | berserk | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | berserk | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | confiante | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | confiante | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | animado | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | animado | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | euforico | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | euforico | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | extase | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | extase | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | panico | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | panico | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | nervoso | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | nervoso | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | desespero | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | desespero | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | tedio | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | tedio | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | tristeza | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | tristeza | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | morto | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | morto | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | tonto | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | tonto | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | dor | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | dor | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | esforco | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | esforco | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | firmeza | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | firmeza | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | alerta | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | alerta | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | confuso | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | confuso | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | limite | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | limite | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| boca | concentrado | Parado | `expr` | sim | fração do rosto / centro do boca no gabarito do rosto |
| boca | concentrado | Grito | `golpe_fase` | não | fração do rosto / centro da boca no gabarito do rosto |
| Detalhe rosto | neutro | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | focado | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | glacial | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | determinado | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | furia | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | berserk | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | confiante | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | animado | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | euforico | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | extase | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | panico | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | nervoso | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | desespero | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | tedio | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | tristeza | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | morto | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | tonto | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | dor | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | esforco | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | firmeza | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | alerta | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | confuso | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | limite | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| Detalhe rosto | concentrado | Parado | `expr` | sim | fração do rosto / centro do detalhe_rosto no gabarito do rosto |
| olhos | neutro | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | neutro | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | focado | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | focado | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | glacial | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | glacial | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | determinado | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | determinado | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | furia | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | furia | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | berserk | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | berserk | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | confiante | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | confiante | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | animado | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | animado | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | euforico | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | euforico | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | extase | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | extase | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | panico | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | panico | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | nervoso | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | nervoso | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | desespero | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | desespero | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | tedio | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | tedio | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | tristeza | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | tristeza | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | morto | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | morto | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | tonto | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | tonto | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | dor | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | dor | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | esforco | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | esforco | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | firmeza | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | firmeza | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | alerta | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | alerta | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | confuso | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | confuso | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | limite | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | limite | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| olhos | concentrado | Parado | `expr` | sim | fração do rosto / centro do olhos no gabarito do rosto |
| olhos | concentrado | Piscar | `ocioso`; a cada 2–5 s | não | fração do rosto / centro dos olhos no gabarito do rosto |
| sobrancelhas | neutro | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | focado | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | glacial | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | determinado | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | furia | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | berserk | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | confiante | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | animado | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | euforico | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | extase | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | panico | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | nervoso | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | desespero | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | tedio | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | tristeza | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | morto | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | tonto | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | dor | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | esforco | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | firmeza | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | alerta | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | confuso | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | limite | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |
| sobrancelhas | concentrado | Parado | `expr` | sim | fração do rosto / centro do sobrancelhas no gabarito do rosto |

## skill

| Peça | Estado | Animação | Quando toca | Loop | Tamanho / âncora |
| --- | --- | --- | --- | --- | --- |
| Acelerar | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Acelerar | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Amplificar Magia | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Amplificar Magia | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Anjo Guardião | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Anjo Guardião | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Apocalipse | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Apocalipse | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Avanço Brutal | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Avanço Brutal | Efeito | Efeito | `dash` | não | 1,0 do corpo / ponto do evento |
| Avatar de Gelo | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Avatar de Gelo | Efeito | Efeito | `transformacao` | sim | 1,0 do corpo / ponto do evento |
| Barreira de Espinhos | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Barreira de Espinhos | Efeito | Efeito | `trap` | sim | 1,0 do corpo / ponto do evento |
| Barreira Divina | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Barreira Divina | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Benção | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Benção | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Bola de Fogo | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Bola de Fogo | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Bomba Relógio | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Bomba Relógio | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Buraco Negro | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Buraco Negro | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Campo de Gravidade | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Campo de Gravidade | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Campo Elétrico | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Campo Elétrico | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Chama Caótica | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Chama Caótica | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Chamas do Dragão | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Chamas do Dragão | Efeito | Efeito | `beam` | sim | 1,0 do corpo / ponto do evento |
| Colapso | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Colapso | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Colheita de Almas | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Colheita de Almas | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Combustão Espontânea | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Combustão Espontânea | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Cone de Gelo | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Cone de Gelo | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Conjuração Perfeita | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Conjuração Perfeita | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Contrafeitiço | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Contrafeitiço | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Cópia Sombria | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Cópia Sombria | Efeito | Efeito | `summon` | sim | 1,0 do corpo / ponto do evento |
| Corrente Elétrica | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Corrente Elétrica | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Corrente em Cadeia | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Corrente em Cadeia | Efeito | Efeito | `beam` | sim | 1,0 do corpo / ponto do evento |
| Cura Maior | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Cura Maior | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Cura Menor | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Cura Menor | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Dardo Venenoso | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Dardo Venenoso | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Desintegrar | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Desintegrar | Efeito | Efeito | `beam` | sim | 1,0 do corpo / ponto do evento |
| Determinação | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Determinação | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Disparo de Mana | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Disparo de Mana | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Eco Temporal | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Eco Temporal | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Escudo Arcano | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Escudo Arcano | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Escudo de Brasas | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Escudo de Brasas | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Esfera Sombria | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Esfera Sombria | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Espinhos | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Espinhos | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Esporos Alucinógenos | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Esporos Alucinógenos | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Estilhaço de Gelo | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Estilhaço de Gelo | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Estilhaço Vermelho | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Estilhaço Vermelho | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Execução | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Execução | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Explosão Arcana | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Explosão Arcana | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Explosão do Caos | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Explosão do Caos | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Explosão Necrótica | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Explosão Necrótica | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Explosão Nova | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Explosão Nova | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Fenda do Vazio | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Fenda do Vazio | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Fênix | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Fênix | Efeito | Efeito | `summon` | sim | 1,0 do corpo / ponto do evento |
| Forma Relâmpago | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Forma Relâmpago | Efeito | Efeito | `transformacao` | sim | 1,0 do corpo / ponto do evento |
| Forma Sanguinária | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Forma Sanguinária | Efeito | Efeito | `transformacao` | sim | 1,0 do corpo / ponto do evento |
| Fotossíntese | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Fotossíntese | Efeito | Efeito | `canal` | sim | 1,0 do corpo / ponto do evento |
| Fúria do Trovão | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Fúria do Trovão | Efeito | Efeito | `canal` | sim | 1,0 do corpo / ponto do evento |
| Fúria Giratória | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Fúria Giratória | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Golpe do Executor | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Golpe do Executor | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Grito de Guerra | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Grito de Guerra | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Idade Acelerada | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Idade Acelerada | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Impacto Sônico | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Impacto Sônico | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Inferno | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Inferno | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Instabilidade | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Instabilidade | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Invocação: Espírito | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Invocação: Espírito | Efeito | Efeito | `summon` | sim | 1,0 do corpo / ponto do evento |
| Ira da Floresta | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Ira da Floresta | Efeito | Efeito | `summon` | sim | 1,0 do corpo / ponto do evento |
| Julgamento Celestial | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Julgamento Celestial | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Julgamento de Thor | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Julgamento de Thor | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Lâmina de Sangue | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Lâmina de Sangue | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Lança de Fogo | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Lança de Fogo | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Lança de Gelo | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Lança de Gelo | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Lança do Vazio | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Lança do Vazio | Efeito | Efeito | `beam` | sim | 1,0 do corpo / ponto do evento |
| Levitar | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Levitar | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Link de Vida | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Link de Vida | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Maldição | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Maldição | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Medo Profundo | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Medo Profundo | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Meteoro | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Meteoro | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Mísseis Arcanos | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Mísseis Arcanos | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Mjolnir | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Mjolnir | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Morte Glacial | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Morte Glacial | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Muralha de Gelo | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Muralha de Gelo | Efeito | Efeito | `trap` | sim | 1,0 do corpo / ponto do evento |
| Muro Ardente | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Muro Ardente | Efeito | Efeito | `trap` | sim | 1,0 do corpo / ponto do evento |
| Mutação | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Mutação | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Necrose | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Necrose | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Nevasca | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Nevasca | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Nuvem Tóxica | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Nuvem Tóxica | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Pacto de Sangue | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Pacto de Sangue | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Parar o Tempo | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Parar o Tempo | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Passo do Vazio | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Passo do Vazio | Efeito | Efeito | `dash` | não | 1,0 do corpo / ponto do evento |
| Pilar de Fogo | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Pilar de Fogo | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Portal Arcano | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Portal Arcano | Efeito | Efeito | `dash` | não | 1,0 do corpo / ponto do evento |
| Portal Sombrio | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Portal Sombrio | Efeito | Efeito | `dash` | não | 1,0 do corpo / ponto do evento |
| Possessão | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Possessão | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Praga | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Praga | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Previsão | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Previsão | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Prisão de Gelo | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Prisão de Gelo | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Provocar | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Provocar | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Pulso Gravitacional | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Pulso Gravitacional | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Purificar | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Purificar | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Raio Sagrado | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Raio Sagrado | Efeito | Efeito | `beam` | sim | 1,0 do corpo / ponto do evento |
| Raízes | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Raízes | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Reflexo Espelhado | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Reflexo Espelhado | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Regeneração | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Regeneração | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Relâmpago | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Relâmpago | Efeito | Efeito | `beam` | sim | 1,0 do corpo / ponto do evento |
| Repulsão | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Repulsão | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Ressurreição | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Ressurreição | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Reverter | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Reverter | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Ritual Carmesim | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Ritual Carmesim | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Roleta Russa | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Roleta Russa | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Roubar Magia | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Roubar Magia | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Sacrifício | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Sacrifício | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Shatter | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Shatter | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Slow Motion | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Slow Motion | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Smite | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Smite | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Sobrecarga | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Sobrecarga | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Teleporte Relâmpago | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Teleporte Relâmpago | Efeito | Efeito | `dash` | não | 1,0 do corpo / ponto do evento |
| Tempestade | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Tempestade | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Tentáculos do Vazio | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Tentáculos do Vazio | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Terremoto | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Terremoto | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Area | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Area | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Beam | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Beam | Efeito | Efeito | `beam` | sim | 1,0 do corpo / ponto do evento |
| Buff | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Buff | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Channel | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Channel | Efeito | Efeito | `canal` | sim | 1,0 do corpo / ponto do evento |
| Dash | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Dash | Efeito | Efeito | `dash` | não | 1,0 do corpo / ponto do evento |
| Projétil | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Projétil | Efeito | Efeito | `projetil` | sim | 1,0 do corpo / ponto do evento |
| Summon | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Summon | Efeito | Efeito | `summon` | sim | 1,0 do corpo / ponto do evento |
| Transform | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Transform | Efeito | Efeito | `transformacao` | sim | 1,0 do corpo / ponto do evento |
| Trap | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Trap | Efeito | Efeito | `trap` | sim | 1,0 do corpo / ponto do evento |
| Transfusão | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Transfusão | Efeito | Efeito | `canal` | sim | 1,0 do corpo / ponto do evento |
| Troca de Almas | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Troca de Almas | Efeito | Efeito | `dash` | não | 1,0 do corpo / ponto do evento |
| Último Suspiro | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Último Suspiro | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Velocidade Arcana | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Velocidade Arcana | Efeito | Efeito | `buff` | sim | 1,0 do corpo / ponto do evento |
| Wrath of Nature | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Wrath of Nature | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |
| Zero Absoluto | Conjuração | Conjurar | `skill` | não | 0,6 do corpo / mao |
| Zero Absoluto | Efeito | Efeito | `area` | sim | 1,0 do corpo / ponto do evento |

## Sem animação

Estes sinais existem no jogo, mas não pedem arte no palco:

- `plano`: sinal para a narrativa; nao e uma peca do combate.
- `refletido`: troca o dono da trilha existente; nao cria uma peca nova.
- `tell`: sinal da IA para a narrativa; sem desenho no palco.
- `texto`: decisao do jogo: numeros de dano nao entram no palco.
- `virada`: marcacao da narrativa; sem desenho no combate.

## Como acrescentar uma animação nova

1. Acrescente o tipo, estilo, classe, skill, elemento ou estado na definição do jogo.
2. Gere o catálogo. A nova peça aparece com a herança de arte (estilo, tipo e genérica).
3. No Ateliê, escolha a peça, o estado e a animação; envie a folha, fatie e ajuste a âncora.
4. Uma arma ou personagem específico só ganha arte própria como sobrescrita opcional; não entra nesta lista.
5. Se o sinal novo não deve desenhar nada, registre o motivo em `sem_animacao` no gerador.
