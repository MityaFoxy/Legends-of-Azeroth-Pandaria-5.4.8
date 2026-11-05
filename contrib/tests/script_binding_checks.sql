-- Read-only post-migration checks for 2026_10_03_00.
-- Run with the world database selected.

SELECT 'legacy guard names removed' AS check_name,
       IF(COUNT(*) = 0, 'PASS', 'FAIL') AS result
FROM `creature_template`
WHERE `ScriptName` IN ('guard_generic','guard_shattrath_aldor','guard_shattrath_scryer');

SELECT 'guard bindings migrated' AS check_name,
       IF(SUM(`ScriptName` = 'npc_guard_generic') = 18
          AND SUM(`ScriptName` = 'npc_guard_shattrath_faction') = 2, 'PASS', 'FAIL') AS result
FROM `creature_template`
WHERE `entry` IN (68,727,1423,3084,3218,3296,3502,4624,5595,5624,9460,11190,15184,19687,
                  45015,45230,45814,51346,18549,18568);

SELECT 'inactive script bindings removed' AS check_name,
       IF(SUM(binding_count) = 0, 'PASS', 'FAIL') AS result
FROM (
    SELECT COUNT(*) AS binding_count FROM `achievement_criteria_data`
     WHERE `ScriptName` = 'achievement_im_on_a_boat'
    UNION ALL SELECT COUNT(*) FROM `areatrigger_scripts`
     WHERE `ScriptName` = 'at_well_of_eternity_skip_illidan_intro'
    UNION ALL SELECT COUNT(*) FROM `spell_script_names`
     WHERE `ScriptName` IN ('spell_howling_gale_howling_gale','spell_protection_of_elune')
) bindings;

SELECT 'retired bindings archived' AS check_name,
       IF(SUM(binding_count) = 8, 'PASS', 'FAIL') AS result
FROM (
    SELECT COUNT(*) AS binding_count FROM `achievement_criteria_data_disabled_archive`
     WHERE `criteria_id` IN (12777,13079,13080,13081) AND `ScriptName` = 'achievement_im_on_a_boat'
    UNION ALL SELECT COUNT(*) FROM `areatrigger_scripts_disabled_archive`
     WHERE `entry` = 7144 AND `ScriptName` = 'at_well_of_eternity_skip_illidan_intro'
    UNION ALL SELECT COUNT(*) FROM `spell_script_names_disabled_archive`
     WHERE (`spell_id`,`ScriptName`) IN ((85084,'spell_howling_gale_howling_gale'),(38528,'spell_protection_of_elune'))
    UNION ALL SELECT COUNT(*) FROM `spell_areatrigger_template_disabled_archive`
     WHERE `Entry` = 742 AND `ScriptName` = 'sat_icy_shadows'
) bindings;

SELECT 'Icy Shadows geometry restored' AS check_name,
       IF(COUNT(*) = 1, 'PASS', 'FAIL') AS result
FROM `spell_areatrigger_template`
WHERE `Entry` = 742 AND `Flags` = 0 AND `CollisionType` = 0
  AND `Radius` = 7 AND `ScaleX` = 0 AND `ScaleY` = 0 AND `ScriptName` = '';

SELECT 'numeric pseudo-scripts cleared' AS check_name,
       IF(SUM(binding_count) = 0, 'PASS', 'FAIL') AS result
FROM (
    SELECT COUNT(*) AS binding_count FROM `conditions` WHERE `ScriptName` = '0'
    UNION ALL SELECT COUNT(*) FROM `gameobject` WHERE `guid` = 20936 AND `ScriptName` = '1'
) bindings;

SELECT 'numeric pseudo-scripts archived' AS check_name,
       IF(SUM(binding_count) = 7, 'PASS', 'FAIL') AS result
FROM (
    SELECT COUNT(*) AS binding_count FROM `conditions_invalid_script_archive` WHERE `ScriptName` = '0'
    UNION ALL SELECT COUNT(*) FROM `gameobject_invalid_script_archive`
     WHERE `guid` = 20936 AND `id` = 200004 AND `ScriptName` = '1'
) bindings;

SELECT 'battle pay item bindings preserved' AS check_name,
       IF(COUNT(*) = 21, 'PASS', 'FAIL') AS result
FROM `item_script_names`
WHERE `Id` IN (110001,110002,110003,110004,110005,110006,110007,110008,110009,110010,110011,
               110012,110013,110014,110015,110016,110017,110018,110019,110100,110101)
  AND `ScriptName` IN ('wow_token_1','wow_token_2','wow_token_5','wow_token_10',
                       'battle_pay_currency_honor_1000','battle_pay_currency_justice_1000',
                       'battle_pay_currency_valor_1000','battle_pay_currency_conquest_1000',
                       'battle_pay_gold_1k','battle_pay_gold_5k','battle_pay_gold_10k',
                       'battle_pay_gold_30k','battle_pay_gold_80k','battle_pay_gold_150k',
                       'battle_pay_service_level_90','battle_pay_service_rename',
                       'battle_pay_service_change_faction','battle_pay_service_change_race',
                       'battle_pay_service_customize','battle_pay_boost_profession',
                       'battle_pay_boost_profession_small');
