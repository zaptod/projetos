"""Manifesto literal de evidencias de runtime para os comandos de live.

Este arquivo e lido por ``neural_fights.tools.auditoria_comandos`` via AST. Ele
nao deve importar testes nem codigo do jogo. Cada referencia usa o formato
``(modulo, classe, metodo)``; uma tupla vazia deixa o comando explicitamente sem
evidencia e mantem o aviso da auditoria.

O ponto do manifesto e impedir que o vocabulario cresca mais rapido que os
testes: com ``--verify-evidence-sources``, a auditoria abre o arquivo de teste e
confere por AST que a classe e o metodo existem de verdade. Um nome inventado e
rejeitado.

Ele prova que **existe um teste nomeado** para cada comando -- nao que o teste
seja bom. Essa distincao e a mesma que ``skill_runtime_evidence`` declara.
"""


COMMAND_RUNTIME_EVIDENCE = {
    "curar": (
        (
            "tests.test_live_command_regressions",
            "EfeitoAssistTests",
            "test_curar_restaura_vida_do_alvo_escolhido",
        ),
    ),
    "curar_forte": (
        (
            "tests.test_live_command_regressions",
            "EfeitoAssistTests",
            "test_cura_forte_tambem_remove_debuffs",
        ),
    ),
    "purificar": (
        (
            "tests.test_live_command_regressions",
            "EfeitoAssistTests",
            "test_purificar_limpa_debuffs_e_concede_imunidade",
        ),
    ),
    "acelerar": (
        (
            "tests.test_live_command_regressions",
            "EfeitoAssistTests",
            "test_buff_persistente_entra_na_lista_do_lutador",
        ),
    ),
    "fuma": (
        (
            "tests.test_live_command_regressions",
            "EfeitoAssistTests",
            "test_buff_persistente_entra_na_lista_do_lutador",
        ),
    ),
    "livrar": (
        (
            "tests.test_live_command_regressions",
            "EfeitoAssistTests",
            "test_livrar_remove_os_debuffs_ativos",
        ),
    ),
    "meteoro": (
        (
            "tests.test_live_command_regressions",
            "EfeitoCaosTests",
            "test_caos_instancia_uma_area_por_lutador",
        ),
        (
            "tests.test_live_command_regressions",
            "EfeitoCaosTests",
            "test_area_de_caos_e_drenada_pelo_frame_como_uma_skill",
        ),
    ),
    "nevasca": (
        (
            "tests.test_live_command_regressions",
            "EfeitoCaosTests",
            "test_caos_atinge_os_dois_lutadores",
        ),
    ),
    "tempestade": (
        (
            "tests.test_live_command_regressions",
            "EfeitoCaosTests",
            "test_caos_exige_os_dois_lutadores_vivos",
        ),
    ),
    "arena": (
        (
            "tests.test_live_command_regressions",
            "ProximoRoundTests",
            "test_arena_valida_entra_na_fila_do_proximo_round",
        ),
        (
            "tests.test_live_command_regressions",
            "ProximoRoundTests",
            "test_arena_desconhecida_e_recusada",
        ),
    ),
}
