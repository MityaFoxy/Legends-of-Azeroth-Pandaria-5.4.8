-- Quest 7062 (The Reason for the Season) belongs to Goli Krumn (1365).
-- The correct relation is already seasonal in game_event_creature_quest
-- (Winter Veil event 2). Gothor Brumn (1362) is an unrelated armorer.
-- Preserve the mistaken permanent relation before removing it.
CREATE TABLE IF NOT EXISTS `creature_queststarter_legacy_archive` LIKE `creature_queststarter`;

INSERT IGNORE INTO `creature_queststarter_legacy_archive` (`id`, `quest`)
SELECT `id`, `quest` FROM `creature_queststarter`
WHERE `id` = 1362 AND `quest` = 7062
  AND EXISTS (SELECT 1 FROM `game_event_creature_quest`
              WHERE `eventEntry` = 2 AND `id` = 1365 AND `quest` = 7062);

DELETE FROM `creature_queststarter`
WHERE `id` = 1362 AND `quest` = 7062
  AND EXISTS (SELECT 1 FROM `game_event_creature_quest`
              WHERE `eventEntry` = 2 AND `id` = 1365 AND `quest` = 7062);

-- Goli is spawned only during event 2; without this flag the event-added
-- quest relation cannot be offered in gossip.
UPDATE `creature_template`
SET `npcflag` = `npcflag` | 2
WHERE `entry` = 1365
  AND EXISTS (SELECT 1 FROM `game_event_creature_quest`
              WHERE `eventEntry` = 2 AND `id` = 1365 AND `quest` = 7062);
