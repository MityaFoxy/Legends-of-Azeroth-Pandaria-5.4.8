-- Quest 29790 (Passing Wisdom) casts spell 109335, whose 5.4.8 DBC effect
-- already summons Walking Stick (57874). The linked direct summon creates a
-- second stick at the same position. Keep the native spell-driven summon and
-- preserve the redundant SmartAI action losslessly before removing it.
CREATE TABLE IF NOT EXISTS `smart_scripts_redundant_summon_archive` LIKE `smart_scripts`;

START TRANSACTION;

INSERT IGNORE INTO `smart_scripts_redundant_summon_archive`
SELECT live.*
FROM `smart_scripts` live
WHERE live.`entryorguid` = 56686
  AND live.`source_type` = 0
  AND live.`id` = 8
  AND live.`link` = 0
  AND live.`event_type` = 61
  AND live.`event_phase_mask` = 0
  AND live.`event_chance` = 100
  AND live.`event_flags` = 0
  AND live.`event_param1` = 0
  AND live.`event_param2` = 0
  AND live.`event_param3` = 0
  AND live.`event_param4` = 0
  AND live.`event_param5` = 0
  AND live.`action_type` = 12
  AND live.`action_param1` = 57874
  AND live.`action_param2` = 3
  AND live.`action_param3` = 33000
  AND live.`action_param4` = 0
  AND live.`action_param5` = 0
  AND live.`action_param6` = 0
  AND live.`target_type` = 8
  AND live.`target_param1` = 0
  AND live.`target_param2` = 0
  AND live.`target_param3` = 0
  AND live.`target_param4` = 0
  AND ABS(live.`target_x` - 873.094) < 0.001
  AND ABS(live.`target_y` - 4462.26) < 0.001
  AND ABS(live.`target_z` - 241.412) < 0.001
  AND ABS(live.`target_o` - 3.80482) < 0.001
  AND BINARY live.`comment` = BINARY 'Master Shang Xi - Linked To Id 7 - Summon Creature Walking Stick';

-- Require the archived payload to match the live row exactly. A conflicting
-- archive row therefore cannot authorize deletion of customized world data.
DELETE live
FROM `smart_scripts` live
JOIN `smart_scripts_redundant_summon_archive` archived
  ON archived.`entryorguid` = live.`entryorguid`
 AND archived.`source_type` = live.`source_type`
 AND archived.`id` = live.`id`
 AND archived.`link` = live.`link`
 AND archived.`event_type` = live.`event_type`
 AND archived.`event_phase_mask` = live.`event_phase_mask`
 AND archived.`event_chance` = live.`event_chance`
 AND archived.`event_flags` = live.`event_flags`
 AND archived.`event_param1` = live.`event_param1`
 AND archived.`event_param2` = live.`event_param2`
 AND archived.`event_param3` = live.`event_param3`
 AND archived.`event_param4` = live.`event_param4`
 AND archived.`event_param5` = live.`event_param5`
 AND archived.`action_type` = live.`action_type`
 AND archived.`action_param1` = live.`action_param1`
 AND archived.`action_param2` = live.`action_param2`
 AND archived.`action_param3` = live.`action_param3`
 AND archived.`action_param4` = live.`action_param4`
 AND archived.`action_param5` = live.`action_param5`
 AND archived.`action_param6` = live.`action_param6`
 AND archived.`target_type` = live.`target_type`
 AND archived.`target_param1` = live.`target_param1`
 AND archived.`target_param2` = live.`target_param2`
 AND archived.`target_param3` = live.`target_param3`
 AND archived.`target_param4` = live.`target_param4`
 AND archived.`target_x` = live.`target_x`
 AND archived.`target_y` = live.`target_y`
 AND archived.`target_z` = live.`target_z`
 AND archived.`target_o` = live.`target_o`
 AND BINARY archived.`comment` = BINARY live.`comment`
WHERE live.`entryorguid` = 56686
  AND live.`source_type` = 0
  AND live.`id` = 8
  AND live.`link` = 0
  AND live.`event_type` = 61
  AND live.`action_type` = 12
  AND live.`action_param1` = 57874;

-- Action 7 no longer links to the archived direct summon. Its cast of 109335
-- remains linked from action 6, so the complete quest sequence still runs.
UPDATE `smart_scripts` cast_action
LEFT JOIN `smart_scripts` direct_summon
  ON direct_summon.`entryorguid` = 56686
 AND direct_summon.`source_type` = 0
 AND direct_summon.`id` = 8
SET cast_action.`link` = 0
WHERE cast_action.`entryorguid` = 56686
  AND cast_action.`source_type` = 0
  AND cast_action.`id` = 7
  AND cast_action.`link` = 8
  AND cast_action.`event_type` = 61
  AND cast_action.`event_phase_mask` = 0
  AND cast_action.`event_chance` = 100
  AND cast_action.`event_flags` = 0
  AND cast_action.`event_param1` = 0
  AND cast_action.`event_param2` = 0
  AND cast_action.`event_param3` = 0
  AND cast_action.`event_param4` = 0
  AND cast_action.`event_param5` = 0
  AND cast_action.`action_type` = 11
  AND cast_action.`action_param1` = 109335
  AND cast_action.`action_param2` = 0
  AND cast_action.`action_param3` = 0
  AND cast_action.`action_param4` = 0
  AND cast_action.`action_param5` = 0
  AND cast_action.`action_param6` = 0
  AND cast_action.`target_type` = 1
  AND cast_action.`target_param1` = 0
  AND cast_action.`target_param2` = 0
  AND cast_action.`target_param3` = 0
  AND cast_action.`target_param4` = 0
  AND cast_action.`target_x` = 0
  AND cast_action.`target_y` = 0
  AND cast_action.`target_z` = 0
  AND cast_action.`target_o` = 0
  AND BINARY cast_action.`comment` = BINARY 'Master Shang Xi - Linked To Id 6 - Cast Summon Walking Stick'
  AND EXISTS
  (
      SELECT 1
      FROM `smart_scripts_redundant_summon_archive` archived
      WHERE archived.`entryorguid` = 56686
        AND archived.`source_type` = 0
        AND archived.`id` = 8
        AND archived.`link` = 0
        AND archived.`event_type` = 61
        AND archived.`action_type` = 12
        AND archived.`action_param1` = 57874
  )
  AND direct_summon.`entryorguid` IS NULL;

COMMIT;
