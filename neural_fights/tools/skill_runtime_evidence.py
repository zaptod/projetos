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
    "aviso_visual": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_delayed_area_exposes_visual_warning_before_activation",
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
    "bonus_vs_trevas@BEAM": (
        (
            "tests.test_buff_skill_contracts",
            "BuffSkillContractTests",
            "test_holy_bonuses_apply_only_to_explicit_dark_affinity",
        ),
    ),
    "bonus_vs_trevas@PROJETIL": (
        (
            "tests.test_buff_skill_contracts",
            "BuffSkillContractTests",
            "test_holy_bonuses_apply_only_to_explicit_dark_affinity",
        ),
    ),
    "chance_stun": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_area_chance_stun_controls_primary_paralysis",
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
    "dano_contato@BUFF": (
        (
            "tests.test_buff_skill_contracts",
            "BuffSkillContractTests",
            "test_ember_shield_retaliates_once_per_accepted_melee_source",
        ),
    ),
    "dano_meteoro": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_meteor_shower_emits_every_configured_meteor_with_explicit_payload",
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
    "meteoros_aleatorios": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_meteor_shower_emits_every_configured_meteor_with_explicit_payload",
        ),
    ),
    "ondas": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_area_waves_emit_every_configured_wave_with_step_independence",
        ),
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_area_waves_apply_base_and_every_child_impact_after_a_coarse_step",
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
    "raio_meteoro": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_meteor_shower_emits_every_configured_meteor_with_explicit_payload",
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
            "test_area_status_stacks_ignore_only_hit_recovery_with_coarse_steps",
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
    "alcance_cone": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_ice_cone_uses_angular_geometry_and_stays_anchored",
        ),
    ),
    "angulo_cone": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_ice_cone_uses_angular_geometry_and_stays_anchored",
        ),
    ),
    "aura_raio": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_avatar_ice_aura_uses_declared_radius_and_slow_factor",
        ),
    ),
    "aura_slow": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_avatar_ice_aura_uses_declared_radius_and_slow_factor",
        ),
    ),
    "bloqueia_movimento": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_trap_blocks_movement_and_repeats_declared_contact_damage",
        ),
    ),
    "bonus_dano": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_blood_pact_pays_health_then_buffs_damage_and_real_lifesteal",
        ),
    ),
    "bonus_resistencia": (
        (
            "tests.test_runtime_combat_contracts",
            "RuntimeCombatContractTests",
            "test_transform_changes_real_fields_and_reverts_intangibility",
        ),
    ),
    "bonus_velocidade@BUFF": (
        (
            "tests.test_buff_runtime_regressions",
            "BuffRuntimeRegressionTests",
            "test_simple_buff_aliases_are_consumed",
        ),
    ),
    "bonus_velocidade@TRANSFORM": (
        (
            "tests.test_runtime_combat_contracts",
            "RuntimeCombatContractTests",
            "test_transform_changes_real_fields_and_reverts_intangibility",
        ),
    ),
    "bonus_velocidade_ataque": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_speed_buff_aliases_change_final_speed_attack_rate_and_damage_taken",
        ),
    ),
    "bonus_velocidade_movimento": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_speed_buff_aliases_change_final_speed_attack_rate_and_damage_taken",
        ),
    ),
    "buff_dano": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_executor_buff_is_consumed_only_after_accepted_damage",
        ),
    ),
    "buff_velocidade": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_speed_buff_aliases_change_final_speed_attack_rate_and_damage_taken",
        ),
    ),
    "canalizavel@BEAM": (
        (
            "tests.test_runtime_combat_contracts",
            "RuntimeCombatContractTests",
            "test_channel_cast_blocks_actions_and_interruption_clears_owner",
        ),
    ),
    "canalizavel@CHANNEL": (
        (
            "tests.test_runtime_combat_contracts",
            "RuntimeCombatContractTests",
            "test_channel_cast_blocks_actions_and_interruption_clears_owner",
        ),
    ),
    "chain_decay": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_chain_beam_decays_and_preserves_visited_targets",
        ),
    ),
    "chain_range": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_chain_beam_decays_and_preserves_visited_targets",
        ),
    ),
    "chance_backfire": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_russian_roulette_backfire_targets_owner_end_to_end",
        ),
    ),
    "condicao@AREA": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_shatter_rewards_and_consumes_freeze_once",
        ),
    ),
    "condicao@PROJETIL": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_projectile_conditions_change_real_damage_and_execute_low_health",
        ),
    ),
    "consome_ao_causar_dano": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_executor_buff_is_consumed_only_after_accepted_damage",
        ),
    ),
    "cura": (
        (
            "tests.test_buff_skill_contracts",
            "BuffSkillContractTests",
            "test_instant_buffs_are_not_persisted_or_stealable",
        ),
    ),
    "cura_por_segundo": (
        (
            "tests.test_buff_runtime_regressions",
            "BuffRuntimeRegressionTests",
            "test_channel_healing_also_respects_necrosis",
        ),
    ),
    "cura_tick": (
        (
            "tests.test_status_runtime_regressions",
            "StatusRuntimeRegressionTests",
            "test_regeneration_buff_accepts_cura_tick_alias",
        ),
    ),
    "custo_mana_metade": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_perfect_conjuration_halves_mana_and_removes_skill_cooldown",
        ),
    ),
    "custo_vida": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_blood_pact_pays_health_then_buffs_damage_and_real_lifesteal",
        ),
    ),
    "custo_vida_percent": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_sacrifice_pays_declared_max_health_percentage_and_creates_area",
        ),
    ),
    "dano_bonus_condicao@AREA": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_shatter_rewards_and_consumes_freeze_once",
        ),
    ),
    "dano_bonus_condicao@PROJETIL": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_projectile_conditions_change_real_damage_and_execute_low_health",
        ),
    ),
    "dano_contato@TRANSFORM": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_transform_contact_damage_is_step_independent",
        ),
    ),
    "dano_contato@TRAP": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_trap_blocks_movement_and_repeats_declared_contact_damage",
        ),
    ),
    "dano_por_segundo@AREA": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_area_base_and_periodic_damage_are_step_independent_end_to_end",
        ),
    ),
    "dano_por_segundo@BEAM": (
        (
            "tests.test_runtime_combat_contracts",
            "RuntimeCombatContractTests",
            "test_channel_ticks_are_dt_independent_and_penetrate_shields",
        ),
    ),
    "dano_recebido_bonus": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_speed_buff_aliases_change_final_speed_attack_rate_and_damage_taken",
        ),
    ),
    "dano_tick": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_area_base_and_periodic_damage_are_step_independent_end_to_end",
        ),
    ),
    "dano_variavel": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_chaos_projectile_consumes_injected_element_and_damage_rolls",
        ),
    ),
    "delay": (
        (
            "tests.test_area_structure_skill_regressions",
            "AreaStructureSkillRegressionTests",
            "test_delayed_area_exposes_visual_warning_before_activation",
        ),
    ),
    "delay_explosao": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_delayed_collapse_explodes_at_declared_time",
        ),
    ),
    "duracao_charme": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_area_catalog_durations_and_slow_reach_target_runtime",
        ),
    ),
    "duracao_controle": (
        (
            "tests.test_special_status_regressions",
            "SpecialStatusRegressionTests",
            "test_projectiles_carry_the_canonical_special_configuration",
        ),
        (
            "tests.test_special_status_regressions",
            "SpecialStatusRegressionTests",
            "test_possession_has_source_duration_and_suspends_autonomous_offense",
        ),
    ),
    "duracao_fear": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_area_catalog_durations_and_slow_reach_target_runtime",
        ),
    ),
    "duracao_imortal": (
        (
            "tests.test_buff_runtime_regressions",
            "BuffRuntimeRegressionTests",
            "test_immortality_is_consumed_by_one_lethal_hit",
        ),
    ),
    "duracao_portal": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_arcane_portal_is_bidirectional_without_ping_pong",
        ),
    ),
    "duracao_stun": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_area_catalog_durations_and_slow_reach_target_runtime",
        ),
    ),
    "duracao_taunt": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_taunt_restricts_damage_source_until_duration_expires",
        ),
    ),
    "efeito2": (
        (
            "tests.test_combat_effect_regressions",
            "AreaEffectRegressionTests",
            "test_area_collision_applies_secondary_without_reapplying_primary",
        ),
    ),
    "efeito_aleatorio": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_chaos_area_resolves_one_declared_random_effect_per_cast",
        ),
    ),
    "efeito_buff": (
        (
            "tests.test_buff_runtime_regressions",
            "BuffRuntimeRegressionTests",
            "test_fury_modifies_melee_and_incoming_damage_once",
        ),
    ),
    "efeitos_possiveis": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_chaos_area_resolves_one_declared_random_effect_per_cast",
        ),
    ),
    "elemento_aleatorio": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_chaos_projectile_consumes_injected_element_and_damage_rolls",
        ),
    ),
    "escudo": (
        (
            "tests.test_buff_skill_contracts",
            "BuffSkillContractTests",
            "test_ember_shield_retaliates_once_per_accepted_melee_source",
        ),
    ),
    "executa": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_projectile_conditions_change_real_damage_and_execute_low_health",
        ),
    ),
    "gravidade_aumentada": (
        (
            "tests.test_catalog_remaining_mechanics",
            "CatalogRemainingMechanicsTests",
            "test_gravity_field_blocks_new_jumps_while_active",
        ),
    ),
    "ground": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_levitation_grants_temporary_flight_and_ground_immunity",
        ),
    ),
    "homing": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_arcane_missile_homing_turns_toward_nearest_hostile",
        ),
    ),
    "imobiliza": (
        (
            "tests.test_runtime_combat_contracts",
            "RuntimeCombatContractTests",
            "test_channel_honors_explicit_movement_lock",
        ),
    ),
    "imune_debuffs": (
        (
            "tests.test_status_runtime_regressions",
            "StatusRuntimeRegressionTests",
            "test_purify_clears_debuff_families_and_grants_immunity",
        ),
    ),
    "imune_ground": (
        (
            "tests.test_remaining_skill_regressions",
            "RemainingSkillRegressionTests",
            "test_levitation_grants_temporary_flight_and_ground_immunity",
        ),
    ),
    "intangivel": (
        (
            "tests.test_runtime_combat_contracts",
            "RuntimeCombatContractTests",
            "test_transform_changes_real_fields_and_reverts_intangibility",
        ),
    ),
    "invencivel": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_lightning_teleport_applies_arrival_damage_contract",
        ),
    ),
    "lifesteal@AREA": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_necrotic_area_heals_from_damage_actually_applied",
        ),
    ),
    "lifesteal@BUFF": (
        (
            "tests.test_buff_runtime_regressions",
            "BuffRuntimeRegressionTests",
            "test_buff_lifesteal_uses_central_healing_rules",
        ),
    ),
    "lifesteal@PROJETIL": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_shadow_sphere_heals_from_projectile_damage_actually_applied",
        ),
    ),
    "link_percent": (
        (
            "tests.test_special_status_regressions",
            "SpecialStatusRegressionTests",
            "test_soul_link_splits_direct_damage_and_dot_without_recursion",
        ),
    ),
    "max_splits": (
        (
            "tests.test_catalog_remaining_mechanics",
            "CatalogRemainingMechanicsTests",
            "test_instability_split_schedule_is_step_independent_and_uses_runtime_rng",
        ),
    ),
    "multi_shot": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_multishot_bypasses_iframe_but_deduplicates_each_source",
        ),
    ),
    "penetra_escudo": (
        (
            "tests.test_runtime_combat_contracts",
            "RuntimeCombatContractTests",
            "test_channel_ticks_are_dt_independent_and_penetrate_shields",
        ),
    ),
    "perfura": (
        (
            "tests.test_catalog_remaining_mechanics",
            "CatalogRemainingMechanicsTests",
            "test_ice_spear_pierces_each_hostile_fighter_and_summon_once",
        ),
    ),
    "puxa_continuo": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_gravity_pulse_and_black_hole_emit_nonzero_pull",
        ),
    ),
    "puxa_para_centro": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_gravity_pulse_and_black_hole_emit_nonzero_pull",
        ),
    ),
    "raio_contagio": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_plague_contagion_selects_nearest_and_never_reinfects",
        ),
    ),
    "raio_explosao": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_delayed_collapse_explodes_at_declared_time",
        ),
    ),
    "reflete_dano": (
        (
            "tests.test_buff_runtime_regressions",
            "BuffRuntimeRegressionTests",
            "test_simple_buff_aliases_are_consumed",
        ),
    ),
    "refletir": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_mirrored_reflection_returns_declared_fraction_of_accepted_damage",
        ),
    ),
    "remove_debuffs": (
        (
            "tests.test_status_runtime_regressions",
            "StatusRuntimeRegressionTests",
            "test_cura_maior_removes_only_two_debuff_families",
        ),
    ),
    "remove_todos_debuffs": (
        (
            "tests.test_status_runtime_regressions",
            "StatusRuntimeRegressionTests",
            "test_purify_clears_debuff_families_and_grants_immunity",
        ),
    ),
    "retorna": (
        (
            "tests.test_catalog_remaining_mechanics",
            "CatalogRemainingMechanicsTests",
            "test_mjolnir_returns_after_impact_without_harming_owner",
        ),
    ),
    "slow_fator": (
        (
            "tests.test_catalog_field_contracts",
            "CatalogFieldContractTests",
            "test_area_catalog_durations_and_slow_reach_target_runtime",
        ),
    ),
    "split_aleatorio": (
        (
            "tests.test_catalog_remaining_mechanics",
            "CatalogRemainingMechanicsTests",
            "test_instability_split_schedule_is_step_independent_and_uses_runtime_rng",
        ),
    ),
    "summon_dano": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_summon_damage_uses_owner_modifiers_and_treant_profile",
        ),
    ),
    "summon_tipo": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_summon_damage_uses_owner_modifiers_and_treant_profile",
        ),
    ),
    "summon_vida": (
        (
            "tests.test_catalog_skill_runtime_regressions",
            "CatalogSkillRuntimeRegressionTests",
            "test_phoenix_revives_exactly_once",
        ),
    ),
    "taunt": (
        (
            "tests.test_advanced_skill_regressions",
            "AdvancedSkillRegressionTests",
            "test_taunt_restricts_damage_source_until_duration_expires",
        ),
    ),
}
