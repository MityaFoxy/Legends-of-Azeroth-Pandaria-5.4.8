-- Six legacy NPCs have no spawns in this MoP world. Their escort/encounter
-- mechanics were removed before 5.4.8. Preserve their paths before removing
-- them from the active script_waypoint loader. Do not touch routes for NPCs
-- with a spawn (including custom spawns on another world database).
INSERT IGNORE INTO `script_waypoint_legacy_archive`
SELECT sw.* FROM `script_waypoint` sw
WHERE sw.`entry` IN (349, 1754, 3849, 3850, 6575, 8856)
  AND NOT EXISTS (SELECT 1 FROM `creature` c WHERE c.`id` = sw.`entry`);

DELETE sw FROM `script_waypoint` sw
WHERE sw.`entry` IN (349, 1754, 3849, 3850, 6575, 8856)
  AND NOT EXISTS (SELECT 1 FROM `creature` c WHERE c.`id` = sw.`entry`);
