-- Quest 31713 is completed by the active Ace Longpaw template 58506.
-- Template 58507 is an unspawned duplicate at the same position and must not
-- remain registered as an additional quest ender.
CREATE TABLE IF NOT EXISTS `creature_questender_disabled_archive` LIKE `creature_questender`;

START TRANSACTION;

INSERT IGNORE INTO `creature_questender_disabled_archive` (`id`, `quest`)
SELECT `id`, `quest`
FROM `creature_questender`
WHERE `id` = 58507 AND `quest` = 31713;

DELETE q
FROM `creature_questender` q
JOIN `creature_questender_disabled_archive` a
  ON a.`id` = q.`id` AND a.`quest` = q.`quest`
WHERE q.`id` = 58507 AND q.`quest` = 31713;

-- Lorewalker Cho 73136 is the sole turn-in NPC for quest 33138. Preserve any
-- other NPC capabilities while adding UNIT_NPC_FLAG_QUESTGIVER (0x02).
UPDATE `creature_template` ct
SET ct.`npcflag` = ct.`npcflag` | 2
WHERE ct.`entry` = 73136
  AND (ct.`npcflag` & 2) = 0
  AND EXISTS
  (
      SELECT 1
      FROM `creature_questender` q
      WHERE q.`id` = ct.`entry` AND q.`quest` = 33138
  );

COMMIT;
