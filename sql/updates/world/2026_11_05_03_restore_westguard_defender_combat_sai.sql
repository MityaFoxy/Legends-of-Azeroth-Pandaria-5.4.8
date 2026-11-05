-- Westguard Defender is bound to SmartAI, but its template-level combat
-- events were lost while the seven GUID-specific quest-scene scripts remain.
-- Restore the two rows from the original 5.4.8 SmartAI Lab payload. The core
-- deliberately gives GUID scripts precedence, so these rows affect only the
-- 58 ordinary spawns and do not alter the Peppy's Special Mix scene actors.

INSERT INTO `smart_scripts`
(
    `entryorguid`, `source_type`, `id`, `link`,
    `event_type`, `event_phase_mask`, `event_chance`, `event_flags`,
    `event_param1`, `event_param2`, `event_param3`, `event_param4`, `event_param5`,
    `action_type`, `action_param1`, `action_param2`, `action_param3`,
    `action_param4`, `action_param5`, `action_param6`,
    `target_type`, `target_param1`, `target_param2`, `target_param3`, `target_param4`,
    `target_x`, `target_y`, `target_z`, `target_o`, `comment`
)
SELECT
    23842, 0, 0, 0,
    0, 0, 100, 0,
    0, 0, 2300, 3900, 0,
    11, 6660, 64, 0,
    0, 0, 0,
    2, 0, 0, 0, 0,
    0, 0, 0, 0, 'Westguard Defender - In Combat - Cast Shoot'
FROM `creature_template` template
WHERE template.`entry` = 23842
  AND template.`AIName` = 'SmartAI'
  AND template.`ScriptName` = ''
  AND NOT EXISTS
  (
      SELECT 1
      FROM `smart_scripts` existing
      WHERE existing.`entryorguid` = 23842
        AND existing.`source_type` = 0
        AND existing.`id` = 0
  );

INSERT INTO `smart_scripts`
(
    `entryorguid`, `source_type`, `id`, `link`,
    `event_type`, `event_phase_mask`, `event_chance`, `event_flags`,
    `event_param1`, `event_param2`, `event_param3`, `event_param4`, `event_param5`,
    `action_type`, `action_param1`, `action_param2`, `action_param3`,
    `action_param4`, `action_param5`, `action_param6`,
    `target_type`, `target_param1`, `target_param2`, `target_param3`, `target_param4`,
    `target_x`, `target_y`, `target_z`, `target_o`, `comment`
)
SELECT
    23842, 0, 1, 0,
    9, 0, 100, 1,
    0, 5, 0, 0, 0,
    11, 7164, 0, 0,
    0, 0, 0,
    1, 0, 0, 0, 0,
    0, 0, 0, 0, 'Westguard Defender - Within 0-5 Range - Cast Defensive Stance'
FROM `creature_template` template
WHERE template.`entry` = 23842
  AND template.`AIName` = 'SmartAI'
  AND template.`ScriptName` = ''
  AND NOT EXISTS
  (
      SELECT 1
      FROM `smart_scripts` existing
      WHERE existing.`entryorguid` = 23842
        AND existing.`source_type` = 0
        AND existing.`id` = 1
  );
