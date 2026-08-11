"""Manifesto literal de evidencias comportamentais para skills avancadas.

Este arquivo e lido por ``tools/auditoria_skills.py`` via AST. Ele nao deve
importar testes nem codigo do jogo. Cada referencia usa o formato
``(modulo, classe, metodo)``; uma tupla vazia deixa a capacidade explicitamente
sem evidencia e mantem o aviso da auditoria.
"""


SKILL_RUNTIME_EVIDENCE = {
    "chain": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_chain_beam_decays_and_preserves_visited_targets",
        ),
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_chain_beam_runtime_creates_segment_for_hostile_summon",
        ),
    ),
    "cone": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_ice_cone_uses_angular_geometry_and_stays_anchored",
        ),
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_ice_cone_runtime_hits_every_hostile_inside_volume",
        ),
    ),
    "contagioso": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_plague_contagion_selects_nearest_and_never_reinfects",
        ),
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_plague_runtime_enqueues_contagion_for_additional_hostile",
        ),
    ),
    "copia_caster": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_shadow_copy_repeats_each_basic_attack_exactly_once",
        ),
    ),
    "cria_portal": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_arcane_portal_is_bidirectional_without_ping_pong",
        ),
    ),
    "dano_chegada": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_lightning_teleport_applies_arrival_damage_contract",
        ),
    ),
    "duplica_apos": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_temporal_echo_duplicates_once_without_recursive_tree",
        ),
    ),
    "reflete_projeteis": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_projectile_reflection_changes_owner_once_before_damage",
        ),
    ),
    "reflete_skills": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_counterspell_reflects_one_hostile_skill_without_recursion",
        ),
    ),
    "remove_congelamento": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_shatter_rewards_and_consumes_freeze_once",
        ),
    ),
    "reverte_estado": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_revert_restores_only_historical_hp_and_position",
        ),
    ),
    "rouba_buff": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_steal_magic_transfers_independent_random_buff",
        ),
    ),
    "sem_cooldown": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_perfect_conjuration_halves_mana_and_removes_skill_cooldown",
        ),
    ),
    "stats_aleatorios": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_mutation_uses_injected_rng_and_reverts_without_base_mutation",
        ),
    ),
    "voo": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_levitation_grants_temporary_flight_and_ground_immunity",
        ),
    ),
}
