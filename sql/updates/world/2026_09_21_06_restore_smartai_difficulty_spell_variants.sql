-- The affected rows are alternate difficulty variants of abilities that already
-- have a valid MoP spell in the matching scenario. Keep the event flags and all
-- gameplay timing intact; only use the available variant spell.
UPDATE `smart_scripts`
SET `action_param1` = 90980
WHERE `source_type` = 0
  AND `action_type` = 11
  AND (`entryorguid`, `id`) IN ((47403, 2), (47404, 2))
  AND `action_param1` = 90981;

UPDATE `smart_scripts`
SET `action_param1` = 90099
WHERE `source_type` = 0
  AND `action_type` = 11
  AND (`entryorguid`, `id`) IN ((47403, 4), (47404, 4))
  AND `action_param1` = 90982;

UPDATE `smart_scripts`
SET `action_param1` = 91038
WHERE `source_type` = 0
  AND `action_type` = 11
  AND (`entryorguid`, `id`) IN ((48278, 14), (48278, 15))
  AND `action_param1` = 91039;

-- Both event rows describe the same Firelands achievement failure condition.
-- 99705 is the 5.4.8 Kneel to the Flame! spell; 100101 is absent from its DBC.
UPDATE `smart_scripts`
SET `event_param1` = 99705
WHERE `entryorguid` = 53619
  AND `source_type` = 0
  AND `id` = 10
  AND `event_type` = 31
  AND `event_param1` = 100101
  AND `action_type` = 34;
