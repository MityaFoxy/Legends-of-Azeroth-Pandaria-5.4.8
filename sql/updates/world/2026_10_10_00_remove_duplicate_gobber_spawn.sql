-- Keep the quest-facing Gobber (34954) at the player's Kezan home and remove
-- the overlapping banker variant (36613). Both use display 32385 and were
-- visible in phase 1 at nearly identical coordinates, producing two merged
-- models. The current SkyFire 5.4.8 world data has only 34954 at this location.
CREATE TABLE IF NOT EXISTS `creature_duplicate_spawn_archive` LIKE `creature`;

START TRANSACTION;

INSERT IGNORE INTO `creature_duplicate_spawn_archive`
SELECT duplicate.*
FROM `creature` duplicate
WHERE duplicate.`id` = 36613
  AND duplicate.`map` = 648
  AND duplicate.`spawnMask` = 1
  AND duplicate.`phaseMask` = 1
  AND duplicate.`phaseId` = 0
  AND duplicate.`phaseGroup` = 0
  AND ABS(duplicate.`position_x` + 8179.37) < 0.01
  AND ABS(duplicate.`position_y` - 1321.39) < 0.01
  AND ABS(duplicate.`position_z` - 27.6083) < 0.01
  AND EXISTS
  (
      SELECT 1
      FROM `creature` intended
      WHERE intended.`id` = 34954
        AND intended.`map` = 648
        AND intended.`spawnMask` = 1
        AND intended.`phaseMask` = 1
        AND intended.`phaseId` = 0
        AND intended.`phaseGroup` = 0
        AND ABS(intended.`position_x` + 8179.48) < 0.01
        AND ABS(intended.`position_y` - 1321.38) < 0.01
        AND ABS(intended.`position_z` - 27.6826) < 0.01
  );

DELETE duplicate
FROM `creature` duplicate
JOIN `creature_duplicate_spawn_archive` archived
  ON archived.`guid` = duplicate.`guid`
 AND archived.`id` = duplicate.`id`
 AND archived.`map` = duplicate.`map`
 AND archived.`position_x` = duplicate.`position_x`
 AND archived.`position_y` = duplicate.`position_y`
 AND archived.`position_z` = duplicate.`position_z`
WHERE duplicate.`id` = 36613
  AND duplicate.`map` = 648
  AND duplicate.`spawnMask` = 1
  AND duplicate.`phaseMask` = 1
  AND duplicate.`phaseId` = 0
  AND duplicate.`phaseGroup` = 0
  AND ABS(duplicate.`position_x` + 8179.37) < 0.01
  AND ABS(duplicate.`position_y` - 1321.39) < 0.01
  AND ABS(duplicate.`position_z` - 27.6083) < 0.01;

COMMIT;
