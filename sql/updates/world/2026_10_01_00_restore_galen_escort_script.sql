-- Restore the MoP escort implementation for Galen Goodward (quest 1393).
-- The waypoint route and questgiver relation already exist in this database.
UPDATE `creature_template`
SET `ScriptName` = 'npc_galen_goodward'
WHERE `entry` = 5391
  AND `ScriptName` = '';
