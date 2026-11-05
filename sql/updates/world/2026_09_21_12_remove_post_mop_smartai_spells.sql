-- Remove two post-MoP abilities that were assigned to unrelated 5.4.8 NPCs.
-- Pterrorwing Skyscreamer uses Skycall, which remains in its SmartAI.
-- Arnold Raygun is a non-combat Isle of Giants vendor.

DELETE FROM `smart_scripts`
WHERE `entryorguid` = 70021
  AND `source_type` = 0
  AND `id` = 1
  AND `action_type` = 11
  AND `action_param1` = 223971;

DELETE FROM `smart_scripts`
WHERE `entryorguid` = 70034
  AND `source_type` = 0
  AND `id` = 0
  AND `action_type` = 11
  AND `action_param1` = 215377;
