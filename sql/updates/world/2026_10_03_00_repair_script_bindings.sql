-- Repair the 31 distinct missing ScriptName values reported during world startup.
-- Working scripts are renamed/registered in code. Incomplete or invalid bindings
-- are archived here before removal so they remain recoverable for future work.

CREATE TABLE IF NOT EXISTS `achievement_criteria_data_disabled_archive` LIKE `achievement_criteria_data`;
CREATE TABLE IF NOT EXISTS `areatrigger_scripts_disabled_archive` LIKE `areatrigger_scripts`;
CREATE TABLE IF NOT EXISTS `spell_script_names_disabled_archive` LIKE `spell_script_names`;
CREATE TABLE IF NOT EXISTS `spell_areatrigger_template_disabled_archive` LIKE `spell_areatrigger_template`;
CREATE TABLE IF NOT EXISTS `conditions_invalid_script_archive` LIKE `conditions`;
CREATE TABLE IF NOT EXISTS `gameobject_invalid_script_archive` LIKE `gameobject`;

START TRANSACTION;

-- The guard implementation was renamed by the combat-system modernization,
-- but its world data was never migrated. These names match guards.cpp.
UPDATE `creature_template`
SET `ScriptName` = 'npc_guard_generic'
WHERE `ScriptName` = 'guard_generic'
  AND `entry` IN (68,727,1423,3084,3218,3296,3502,4624,5595,5624,9460,11190,15184,19687,45015,45230,45814,51346);

UPDATE `creature_template`
SET `ScriptName` = 'npc_guard_shattrath_faction'
WHERE (`entry` = 18549 AND `ScriptName` = 'guard_shattrath_aldor')
   OR (`entry` = 18568 AND `ScriptName` = 'guard_shattrath_scryer');

-- This achievement handler has never tracked deck visits in this branch.
-- The encounter currently awards the achievement directly during its outro,
-- so retaining these criteria hooks only requests a nonexistent script.
INSERT IGNORE INTO `achievement_criteria_data_disabled_archive`
SELECT * FROM `achievement_criteria_data`
WHERE `criteria_id` IN (12777,13079,13080,13081)
  AND `type` = 11 AND `value1` = 0 AND `value2` = 0
  AND `ScriptName` = 'achievement_im_on_a_boat';

DELETE d FROM `achievement_criteria_data` d
JOIN `achievement_criteria_data_disabled_archive` a
  ON a.`criteria_id` = d.`criteria_id` AND a.`type` = d.`type`
 AND a.`value1` = d.`value1` AND a.`value2` = d.`value2`
 AND a.`ScriptName` = d.`ScriptName`
WHERE d.`criteria_id` IN (12777,13079,13080,13081)
  AND d.`type` = 11 AND d.`value1` = 0 AND d.`value2` = 0
  AND d.`ScriptName` = 'achievement_im_on_a_boat';

-- Disabled in source because it can close the route before the first trash pack.
INSERT IGNORE INTO `areatrigger_scripts_disabled_archive`
SELECT * FROM `areatrigger_scripts`
WHERE `entry` = 7144 AND `ScriptName` = 'at_well_of_eternity_skip_illidan_intro';

DELETE s FROM `areatrigger_scripts` s
JOIN `areatrigger_scripts_disabled_archive` a
  ON a.`entry` = s.`entry` AND a.`ScriptName` = s.`ScriptName`
WHERE s.`entry` = 7144 AND s.`ScriptName` = 'at_well_of_eternity_skip_illidan_intro';

-- 85084 has a no-op handler (all effects are commented out). TrinityCore also
-- retired the obsolete 38528 binding; the local AuraScript was not registerable.
INSERT IGNORE INTO `spell_script_names_disabled_archive`
SELECT * FROM `spell_script_names`
WHERE (`spell_id` = 85084 AND `ScriptName` = 'spell_howling_gale_howling_gale')
   OR (`spell_id` = 38528 AND `ScriptName` = 'spell_protection_of_elune');

DELETE s FROM `spell_script_names` s
JOIN `spell_script_names_disabled_archive` a
  ON a.`spell_id` = s.`spell_id` AND a.`ScriptName` = s.`ScriptName`
WHERE (s.`spell_id` = 85084 AND s.`ScriptName` = 'spell_howling_gale_howling_gale')
   OR (s.`spell_id` = 38528 AND s.`ScriptName` = 'spell_protection_of_elune');

-- Icy Shadows has only an unregistered, unverified local implementation.
INSERT IGNORE INTO `spell_areatrigger_template_disabled_archive`
SELECT * FROM `spell_areatrigger_template`
WHERE `Entry` = 742 AND `ScriptName` = 'sat_icy_shadows';

DELETE s FROM `spell_areatrigger_template` s
JOIN `spell_areatrigger_template_disabled_archive` a
  ON a.`Entry` = s.`Entry` AND a.`Flags` = s.`Flags`
 AND a.`CollisionType` = s.`CollisionType` AND a.`Radius` = s.`Radius`
 AND a.`ScaleX` = s.`ScaleX` AND a.`ScaleY` = s.`ScaleY`
 AND a.`ScriptName` = s.`ScriptName`
WHERE s.`Entry` = 742 AND s.`ScriptName` = 'sat_icy_shadows';

-- Numeric strings are corrupted defaults, not script identifiers. Preserve
-- the declarative conditions and spawn; clear only their ScriptName fields.
INSERT IGNORE INTO `conditions_invalid_script_archive`
SELECT * FROM `conditions`
WHERE `ScriptName` = '0'
  AND (`SourceTypeOrReferenceId`,`SourceGroup`,`SourceEntry`,`SourceId`,`ElseGroup`,
       `ConditionTypeOrReference`,`ConditionTarget`,`ConditionValue1`,`ConditionValue2`,`ConditionValue3`) IN
      ((17,0,52410,0,0,22,0,607,0,0),
       (17,0,52418,0,0,22,0,607,0,0),
       (17,0,117866,0,0,22,0,996,0,0),
       (17,0,126845,0,0,23,0,6435,0,0),
       (17,0,126845,0,0,9,0,31496,0,0),
       (17,0,139603,0,0,29,0,70388,5,0));

UPDATE `conditions` c
JOIN `conditions_invalid_script_archive` a USING
 (`SourceTypeOrReferenceId`,`SourceGroup`,`SourceEntry`,`SourceId`,`ElseGroup`,
  `ConditionTypeOrReference`,`ConditionTarget`,`ConditionValue1`,`ConditionValue2`,`ConditionValue3`)
SET c.`ScriptName` = ''
WHERE c.`ScriptName` = '0' AND a.`ScriptName` = '0';

INSERT IGNORE INTO `gameobject_invalid_script_archive`
SELECT * FROM `gameobject`
WHERE `guid` = 20936 AND `id` = 200004 AND `map` = 1064 AND `ScriptName` = '1';

UPDATE `gameobject` g
JOIN `gameobject_invalid_script_archive` a
  ON a.`guid` = g.`guid` AND a.`id` = g.`id` AND a.`map` = g.`map`
SET g.`ScriptName` = ''
WHERE g.`guid` = 20936 AND g.`id` = 200004 AND g.`map` = 1064
  AND g.`ScriptName` = '1' AND a.`ScriptName` = '1';

COMMIT;
