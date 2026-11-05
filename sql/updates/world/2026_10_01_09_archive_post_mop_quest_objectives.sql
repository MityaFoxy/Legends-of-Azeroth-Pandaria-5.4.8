-- Exact foreign-version objectives, not missing MoP items/NPCs:
-- TrinityCore 2015_04_10_00_world.sql: 273866 / quest 10794 / build 19865.
-- TrinityCore 2016_09_02_00_world.sql: 280563/280564 / quest 11997 / build 22522.
-- MoP versions are the retired rogue breadcrumb and an unused REUSE breadcrumb.
-- Preserve all payloads and translations; never modify the quest templates.
CREATE TABLE IF NOT EXISTS `quest_objective_post_mop_archive` LIKE `quest_objective`;
CREATE TABLE IF NOT EXISTS `quest_objectives_locale_post_mop_archive` LIKE `quest_objectives_locale`;

START TRANSACTION;
CREATE TEMPORARY TABLE `_post_mop_objectives` LIKE `quest_objective`;
INSERT INTO `_post_mop_objectives`
    (`questId`, `id`, `index`, `type`, `objectId`, `amount`, `flags`, `description`) VALUES
    (10794, 273866, 0, 1, 113135, 1, 0, ''),
    (11997, 280563, 0, 0, 99418, 1, 0, 'Mage Portal Taken'),
    (11997, 280564, 1, 0, 100290, 1, 34, 'Obtain Felo''melorn');

INSERT INTO `quest_objective_post_mop_archive`
SELECT o.* FROM `quest_objective` o
JOIN `_post_mop_objectives` e USING (`questId`, `id`, `index`, `type`, `objectId`, `amount`, `flags`)
JOIN `quest_template` q ON q.`ID` = o.`questId`
WHERE BINARY o.`description` <=> BINARY e.`description`
  AND q.`VerifiedBuild` = 15595
  AND ((q.`ID` = 10794 AND q.`LogTitle` = 'Rogues of the Shattered Hand' AND (q.`Flags` & 16384) <> 0)
    OR (q.`ID` = 11997 AND q.`LogTitle` = 'REUSE'))
  AND NOT EXISTS (SELECT 1 FROM `quest_objective_post_mop_archive` a
      WHERE a.`id` = o.`id` AND a.`questId` = o.`questId` AND a.`index` = o.`index`);

-- Delete only exact expected payloads with exact archival copies.
DELETE o FROM `quest_objective` o
JOIN `_post_mop_objectives` e USING (`questId`, `id`, `index`, `type`, `objectId`, `amount`, `flags`)
JOIN `quest_objective_post_mop_archive` a USING (`questId`, `id`, `index`, `type`, `objectId`, `amount`, `flags`)
JOIN `quest_template` q ON q.`ID` = o.`questId`
WHERE BINARY o.`description` <=> BINARY e.`description`
  AND BINARY o.`description` <=> BINARY a.`description`
  AND q.`VerifiedBuild` = 15595
  AND ((q.`ID` = 10794 AND q.`LogTitle` = 'Rogues of the Shattered Hand' AND (q.`Flags` & 16384) <> 0)
    OR (q.`ID` = 11997 AND q.`LogTitle` = 'REUSE'));

INSERT INTO `quest_objectives_locale_post_mop_archive`
SELECT l.* FROM `quest_objectives_locale` l
WHERE l.`ID` IN (273866, 280563, 280564)
  AND EXISTS (SELECT 1 FROM `quest_objective_post_mop_archive` a WHERE a.`id` = l.`ID`)
  AND NOT EXISTS (SELECT 1 FROM `quest_objective` o WHERE o.`id` = l.`ID`)
  AND NOT EXISTS (SELECT 1 FROM `quest_objectives_locale_post_mop_archive` a
      WHERE a.`ID` = l.`ID` AND a.`locale` = l.`locale`);

DELETE l FROM `quest_objectives_locale` l
JOIN `quest_objectives_locale_post_mop_archive` a USING (`ID`, `locale`, `QuestId`, `StorageIndex`, `VerifiedBuild`)
WHERE l.`ID` IN (273866, 280563, 280564)
  AND BINARY l.`Description` <=> BINARY a.`Description`
  AND NOT EXISTS (SELECT 1 FROM `quest_objective` o WHERE o.`id` = l.`ID`);
DROP TEMPORARY TABLE `_post_mop_objectives`;
COMMIT;
