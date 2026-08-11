"""Manifesto literal de evidencias comportamentais para skills avancadas.

Este arquivo e lido por ``neural_fights.tools.auditoria_skills`` via AST. Ele nao deve
importar testes nem codigo do jogo. Cada referencia usa o formato
``(modulo, classe, metodo)``; uma tupla vazia deixa a capacidade explicitamente
sem evidencia e mantem o aviso da auditoria.
"""


SKILL_RUNTIME_EVIDENCE = {
    "afeta_caster": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_time_stop_consumes_duration_and_caster_targeting_contracts",
        ),
    ),
    "ativa_ao_morrer": (
        (
            "tests.test_death_skill_regressions",
            "DeathSkillRegressionTests",
            "test_last_breath_has_priority_then_resurrection_spends_real_resources",
        ),
    ),
    "bloqueia_projeteis": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_ice_wall_intercepts_fast_hostile_projectiles_until_destroyed",
        ),
    ),
    "bonus_area": (
        (
            "tests.test_buff_skill_contracts",
            "BuffSkillContractTests",
            "test_amplification_is_a_cast_snapshot_for_magic_damage_and_area",
        ),
    ),
    "bonus_dano_magico": (
        (
            "tests.test_buff_skill_contracts",
            "BuffSkillContractTests",
            "test_amplification_is_a_cast_snapshot_for_magic_damage_and_area",
        ),
    ),
    "bonus_vs_trevas": (
        (
            "tests.test_buff_skill_contracts",
            "BuffSkillContractTests",
            "test_holy_bonuses_apply_only_to_explicit_dark_affinity",
        ),
    ),
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
    "cura_percent": (
        (
            "tests.test_death_skill_regressions",
            "DeathSkillRegressionTests",
            "test_last_breath_has_priority_then_resurrection_spends_real_resources",
        ),
    ),
    "cura_por_morte": (
        (
            "tests.test_death_skill_regressions",
            "DeathSkillRegressionTests",
            "test_harvest_heals_flat_amount_only_after_a_terminal_owned_kill",
        ),
    ),
    "dano_contato": (
        (
            "tests.test_buff_skill_contracts",
            "BuffSkillContractTests",
            "test_ember_shield_retaliates_once_per_accepted_melee_source",
        ),
    ),
    "dano_chegada": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_lightning_teleport_applies_arrival_damage_contract",
        ),
    ),
    "delay_saida": (
        (
            "tests.test_buff_skill_contracts",
            "BuffSkillContractTests",
            "test_shadow_portal_has_delayed_untargetable_exit_and_cast_parity",
        ),
    ),
    "duplica_apos": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_temporal_echo_duplicates_once_without_recursive_tree",
        ),
    ),
    "duracao_stop": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_time_stop_consumes_duration_and_caster_targeting_contracts",
        ),
    ),
    "esquiva_garantida": (
        (
            "tests.test_buff_skill_contracts",
            "BuffSkillContractTests",
            "test_prediction_consumes_only_two_accepted_hostile_impacts",
        ),
    ),
    "forca_empurrao": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_repulsion_consumes_configured_force_without_changing_damage",
        ),
    ),
    "invisivel_durante": (
        (
            "tests.test_buff_skill_contracts",
            "BuffSkillContractTests",
            "test_shadow_portal_has_delayed_untargetable_exit_and_cast_parity",
        ),
    ),
    "pilares": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_celestial_pillars_share_one_impact_identity",
        ),
    ),
    "raio_pilar": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_celestial_pillars_share_one_impact_identity",
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
    "revive_hp_percent": (
        (
            "tests.test_death_skill_regressions",
            "DeathSkillRegressionTests",
            "test_last_breath_has_priority_then_resurrection_spends_real_resources",
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
    "stacks_por_segundo": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_toxic_cloud_stacks_only_for_each_targets_exposure",
        ),
    ),
    "vida_estrutura": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_ice_wall_intercepts_fast_hostile_projectiles_until_destroyed",
        ),
    ),
    "ve_ataques": (
        (
            "tests.test_buff_skill_contracts",
            "BuffSkillContractTests",
            "test_prediction_consumes_only_two_accepted_hostile_impacts",
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
