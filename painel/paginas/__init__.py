# -*- coding: utf-8 -*-
"""As paginas do painel. Uma por arquivo, cada uma seguindo o contrato.

    chave / rotulo / icone      identidade no menu
    construir(pai)              monta os widgets, uma vez
    ao_mostrar() / ao_esconder()  entrar e sair da tela
    atualizar(resumo)           recebe o dicionario do `panorama`

Sair da tela ter callback proprio nao e simetria bonita: e o que desliga a
animacao da Vila em vez de deixa-la rodando escondida, gastando 60ms de
relogio para desenhar o que ninguem ve.
"""
