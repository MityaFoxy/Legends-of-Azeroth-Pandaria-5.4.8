-- Bind scripts to the spell in each trigger chain that actually owns the
-- effect handled by the script. Driver spells and their triggered effects are
-- both retained; only stale cross-bindings are replaced.

-- Apparitions: 111698 triggers the absorb aura 112060. The combined script's
-- target filter and absorb calculation both belong to 112060.
DELETE FROM `spell_script_names`
WHERE `spell_id` = 111698 AND `ScriptName` = 'spell_shadopan_apparitions';

-- Tranquility (Symbiosis): 113277 is the driver and 113278 is the raid heal.
DELETE FROM `spell_script_names`
WHERE `spell_id` = 113277 AND `ScriptName` = 'spell_common_smart_heal_raid_25';
INSERT IGNORE INTO `spell_script_names` (`spell_id`, `ScriptName`) VALUES
(113278, 'spell_common_smart_heal_raid_25');

-- 116267 is the Incanter's Ward result buff, not an absorb aura. The absorb
-- is already handled on 1463 by spell_mage_incanters_ward.
DELETE FROM `spell_script_names`
WHERE `spell_id` = 116267 AND `ScriptName` = 'spell_mage_incanters_absorbtion_absorb';

-- Titan Gas 116779 triggers the two actual gas auras. Keep the driver intact
-- and attach the existing scripts only to their matching triggered spells.
DELETE FROM `spell_script_names`
WHERE `spell_id` = 116779
  AND `ScriptName` IN ('spell_titan_gas', 'spell_titan_gas2');

-- Charging Ox Wave: 119392 owns the cone effects; 125084 is only its visual.
DELETE FROM `spell_script_names`
WHERE `spell_id` = 125084 AND `ScriptName` = 'spell_monk_charging_ox_wave';
INSERT IGNORE INTO `spell_script_names` (`spell_id`, `ScriptName`) VALUES
(119392, 'spell_monk_charging_ox_wave');

-- Bombard's periodic driver 120559 triggers damage spell 120202. Preserve the
-- periodic AuraScript and move only the target filter to the damage spell.
INSERT IGNORE INTO `spell_script_names` (`spell_id`, `ScriptName`) VALUES
(120202, 'spell_rimok_saboteur_bombard_effect');

-- Dark of Night 123740 is the driver; its triggered aura 123742 owns the
-- source-area target list filtered by the script.
DELETE FROM `spell_script_names`
WHERE `spell_id` = 123740 AND `ScriptName` = 'spell_dark_of_night_fixate';
INSERT IGNORE INTO `spell_script_names` (`spell_id`, `ScriptName`) VALUES
(123742, 'spell_dark_of_night_fixate');

-- These two bindings target spells without an object-area selection. Their
-- default DBC effects remain active; only unreachable target filters go away.
DELETE FROM `spell_script_names`
WHERE (`spell_id` = 119338 AND `ScriptName` = 'spell_dart')
   OR (`spell_id` = 120124 AND `ScriptName` = 'spell_crossbow_xin');
