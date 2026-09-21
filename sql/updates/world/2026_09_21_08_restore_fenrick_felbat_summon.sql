-- Fenrick Barlowe's comment and linked aggro action identify this as the
-- standard Enraged Felbat summon. The row was encoded as a spell cast using
-- an unrelated absent ID, so it never executed. Match the existing Felbat
-- summon parameters while retaining Fenrick's event and link.
UPDATE `smart_scripts`
SET `action_type` = 12,
    `action_param1` = 9521,
    `action_param2` = 4,
    `action_param3` = 30000
WHERE `entryorguid` = 27842
  AND `source_type` = 0
  AND `id` = 2
  AND `event_type` = 4
  AND `action_type` = 11
  AND `action_param1` = 14252;
