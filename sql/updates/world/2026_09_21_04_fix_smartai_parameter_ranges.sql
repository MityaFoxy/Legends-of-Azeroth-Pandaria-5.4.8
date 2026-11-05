-- Preserve the existing SmartAI actions while restoring valid inclusive
-- ranges. The loader rejects rows whose maximum value is less than minimum.

-- Darkspine Siren: flee below 15% health (the original bounds were reversed).
UPDATE `smart_scripts`
SET `event_param1` = 0,
    `event_param2` = 15
WHERE `entryorguid` = 25073
  AND `source_type` = 0
  AND `id` = 4
  AND `event_type` = 2
  AND `action_type` = 25
  AND `event_param1` = 15
  AND `event_param2` = 0;

-- The distance event may run once after five milliseconds; its prior 5/0
-- cooldown range was invalid and was therefore skipped.
UPDATE `smart_scripts`
SET `event_param4` = 5
WHERE `entryorguid` = 3304100
  AND `source_type` = 9
  AND `id` = 0
  AND `event_type` = 75
  AND `event_param3` = 5
  AND `event_param4` = 0;
