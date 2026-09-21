-- SMART_EVENT_REWARD_QUEST uses event_param2/event_param3 as the cooldown
-- range. These legacy rows placed a non-zero minimum beside a zero maximum,
-- so the loader skipped their otherwise valid action lists/summon action.
-- Preserve the original immediate, non-repeating behavior with a 0/0 range.
UPDATE `smart_scripts`
SET `event_param2` = 0
WHERE `source_type` = 0
  AND `event_type` = 20
  AND `event_param2` IN (1, 2)
  AND `event_param3` = 0
  AND `event_param4` = 0
  AND (`entryorguid`, `id`) IN ((17214, 0), (17215, 2), (32423, 0));
