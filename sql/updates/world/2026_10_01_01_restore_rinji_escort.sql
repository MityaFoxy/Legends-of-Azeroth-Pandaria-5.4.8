-- Restore Rin'ji's MoP escort (quest 2742).  The exact 24-point route is in
-- script_waypoint; MoP quest data identifies Rin'ji as the quest giver.
UPDATE `creature_template`
SET `ScriptName` = 'npc_rinji'
WHERE `entry` = 7780
  AND `ScriptName` = '';

INSERT IGNORE INTO `creature_queststarter` (`id`, `quest`)
VALUES (7780, 2742);
