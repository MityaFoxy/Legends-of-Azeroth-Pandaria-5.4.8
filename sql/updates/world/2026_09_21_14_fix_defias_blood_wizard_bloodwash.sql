-- In 5.4.8, Bloodwash spell 90946 directly applies its haste aura. The
-- Cataclysm script still referred to removed aura spell 90947, causing the
-- FRIENDLY_MISSING_BUFF event to be rejected during SmartAI validation.

UPDATE `smart_scripts`
SET `event_param1` = 90946,
    `action_param1` = 90946,
    `comment` = 'Defias Blood Wizard - On Friendly Missing Bloodwash - Cast Bloodwash'
WHERE `entryorguid` = 48417
  AND `source_type` = 0
  AND `id` = 14
  AND `event_type` = 16
  AND `event_param1` = 90947
  AND `action_type` = 11
  AND `action_param1` = 90947;
