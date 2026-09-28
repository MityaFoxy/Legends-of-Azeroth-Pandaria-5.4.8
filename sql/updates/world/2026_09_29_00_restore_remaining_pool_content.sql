-- Restore resource alternatives whose pool membership was lost during GUID
-- collisions in the original database merge.  AzerothCore's WotLK base is
-- used only where entry, map and coordinates identify the same spawns already
-- present in this database.  Missing alternatives are recreated at the same
-- verified location; no gameobject spawn is deleted.

DROP TEMPORARY TABLE IF EXISTS `_remaining_pool_location`;
CREATE TEMPORARY TABLE `_remaining_pool_location`
(
    `old_pool` MEDIUMINT UNSIGNED NOT NULL,
    `target_pool` MEDIUMINT UNSIGNED NOT NULL,
    `map_id` SMALLINT UNSIGNED NOT NULL,
    `zone_id` INT UNSIGNED NOT NULL,
    `area_id` INT UNSIGNED NOT NULL,
    `position_x` FLOAT NOT NULL,
    `position_y` FLOAT NOT NULL,
    `position_z` FLOAT NOT NULL,
    `orientation` FLOAT NOT NULL,
    `entry_1` MEDIUMINT UNSIGNED NOT NULL,
    `entry_2` MEDIUMINT UNSIGNED NOT NULL,
    `entry_3` MEDIUMINT UNSIGNED NOT NULL,
    `explicit_chance_entry` MEDIUMINT UNSIGNED NOT NULL,
    PRIMARY KEY (`old_pool`)
) ENGINE=InnoDB;

INSERT INTO `_remaining_pool_location`
    (`old_pool`, `target_pool`, `map_id`, `zone_id`, `area_id`,
     `position_x`, `position_y`, `position_z`, `orientation`,
     `entry_1`, `entry_2`, `entry_3`, `explicit_chance_entry`)
VALUES
    (52, 52, 0, 0, 0, 604.853, 644.405, 32.9334, -0.244346, 180582, 180655, 180656, 180655),
    (53, 53, 0, 0, 0, 1321.13, 757.507, 32.9309, -2.1293, 180582, 180655, 180656, 180655),
    (54, 54, 0, 0, 0, 817.672, 1896.21, 0, 2.60054, 180582, 180655, 180656, 180655),
    (55, 55, 0, 0, 0, 736.54, 1845.57, 0, -1.98968, 180582, 180655, 180656, 180655),
    (56, 1006, 0, 0, 0, 992.979, 1958.68, 0, -2.9147, 180582, 180655, 180656, 180655),
    (64, 64, 0, 11, 298, -2704.53, -1210.83, 0, 2.14675, 180657, 180662, 180664, 180662),
    (65, 65, 1, 17, 391, -1476.99, -3924.05, 0, -3.05433, 180582, 180655, 180656, 180655),
    (71, 71, 1, 148, 452, 6486.94, 822.047, 0, 0.994838, 180582, 180655, 180656, 180655),
    (73, 73, 1, 17, 385, -1951.5, -3759.95, 0, 0.663225, 180582, 180655, 180656, 180655),
    (74, 74, 1, 17, 392, -1011.95, -3808.33, 0, -2.3911, 180582, 180655, 180656, 180655),
    (75, 75, 1, 17, 391, -1773.84, -3813.52, 0, -2.68781, 180582, 180655, 180656, 180655),
    (82, 1066, 0, 11, 298, -2721.1, -1163.18, 0, 1.97222, 180657, 180662, 180664, 180662),
    (83, 1069, 0, 11, 298, -3262.99, -889.309, 0, -0.610865, 180657, 180662, 180664, 180662),
    (85, 85, 0, 11, 298, -2460.01, -1757.19, 0, 2.51327, 180657, 180662, 180664, 180662),
    (86, 86, 0, 11, 298, -2576.34, -1586.48, 0, -1.72788, 180657, 180662, 180664, 180662),
    (87, 87, 0, 11, 298, -2625.05, -1536.17, 0, -3.12414, 180657, 180662, 180664, 180662),
    (88, 88, 0, 11, 298, -2672.18, -1451.32, 0, 1.81514, 180657, 180662, 180664, 180662),
    (91, 91, 1, 17, 391, -1199.29, -3823.79, 0, -1.32645, 180582, 180655, 180656, 180655),
    (92, 92, 1, 17, 391, -1608.05, -3954.22, 0, 2.19912, 180582, 180655, 180656, 180655),
    (93, 93, 1, 17, 392, -957.178, -3778.92, 0, -0.174533, 180582, 180655, 180656, 180655),
    (94, 94, 1, 17, 392, -872.794, -3814.69, 0, -2.86234, 180582, 180655, 180656, 180655),
    (95, 95, 1, 17, 391, -1586.55, -3948.27, 0, -1.25664, 180582, 180655, 180656, 180655),
    (96, 96, 0, 38, 38, -5291.58, -3505.29, 297.605, 2.37365, 180582, 180655, 180656, 180655),
    (97, 97, 0, 38, 38, -5141.95, -3445.86, 297.025, 0.872665, 180582, 180655, 180656, 180655),
    (98, 98, 0, 38, 38, -4845.88, -3409.7, 297.605, 2.07694, 180582, 180655, 180656, 180655),
    (99, 99, 0, 38, 556, -5232.57, -3133.11, 297.605, -2.00713, 180582, 180655, 180656, 180655),
    (155, 155, 0, 33, 122, -11844.9, 908.972, 0, -1.65806, 180682, 180683, 0, 0),
    (175, 1094, 0, 0, 0, -13290.2, 651.097, 0, -2.74017, 180900, 180901, 180902, 180901),
    (192, 192, 0, 0, 0, -4982.37, -3543.38, 297.605, 1.50098, 180582, 180655, 180656, 180655),
    (193, 193, 0, 0, 0, -4773.38, -3163.92, 297.605, -2.18166, 180582, 180655, 180656, 180655),
    (195, 195, 0, 0, 0, -5167.09, -3142.34, 297.605, -0.034907, 180582, 180655, 180656, 180655),
    (329, 329, 0, 11, 298, -2489.85, -1712.92, 0, 2.40855, 180657, 180662, 180664, 180662),
    (330, 330, 1, 440, 988, -7691.51, -4923.28, 0, -0.663225, 180712, 180752, 0, 0),
    (331, 331, 1, 440, 1336, -7906.06, -5256.7, 0, -2.77507, 180712, 180752, 0, 0);

DROP TEMPORARY TABLE IF EXISTS `_remaining_pool_variant`;
CREATE TEMPORARY TABLE `_remaining_pool_variant`
(
    `sequence_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `old_pool` MEDIUMINT UNSIGNED NOT NULL,
    `target_pool` MEDIUMINT UNSIGNED NOT NULL,
    `entry` MEDIUMINT UNSIGNED NOT NULL,
    `map_id` SMALLINT UNSIGNED NOT NULL,
    `zone_id` INT UNSIGNED NOT NULL,
    `area_id` INT UNSIGNED NOT NULL,
    `position_x` FLOAT NOT NULL,
    `position_y` FLOAT NOT NULL,
    `position_z` FLOAT NOT NULL,
    `orientation` FLOAT NOT NULL,
    `chance` FLOAT NOT NULL,
    `resolved_guid` INT UNSIGNED NULL,
    PRIMARY KEY (`sequence_id`),
    UNIQUE KEY `uq_location_entry` (`old_pool`, `entry`)
) ENGINE=InnoDB;

INSERT INTO `_remaining_pool_variant`
    (`old_pool`, `target_pool`, `entry`, `map_id`, `zone_id`, `area_id`,
     `position_x`, `position_y`, `position_z`, `orientation`, `chance`)
SELECT
    `location`.`old_pool`, `location`.`target_pool`,
    CASE `variant`.`number`
        WHEN 1 THEN `location`.`entry_1`
        WHEN 2 THEN `location`.`entry_2`
        ELSE `location`.`entry_3`
    END AS `entry`,
    `location`.`map_id`, `location`.`zone_id`, `location`.`area_id`,
    `location`.`position_x`, `location`.`position_y`, `location`.`position_z`,
    `location`.`orientation`,
    IF(
        CASE `variant`.`number`
            WHEN 1 THEN `location`.`entry_1`
            WHEN 2 THEN `location`.`entry_2`
            ELSE `location`.`entry_3`
        END = `location`.`explicit_chance_entry`,
        20,
        0
    ) AS `chance`
FROM `_remaining_pool_location` `location`
CROSS JOIN
(
    SELECT 1 AS `number`
    UNION ALL SELECT 2
    UNION ALL SELECT 3
) `variant`
WHERE CASE `variant`.`number`
          WHEN 1 THEN `location`.`entry_1`
          WHEN 2 THEN `location`.`entry_2`
          ELSE `location`.`entry_3`
      END <> 0;

-- Reuse matching live spawns regardless of their imported GUID.
UPDATE `_remaining_pool_variant` `restore`
INNER JOIN `gameobject` `existing`
    ON `existing`.`id` = `restore`.`entry`
    AND `existing`.`map` = `restore`.`map_id`
    AND ABS(`existing`.`position_x` - `restore`.`position_x`) < 0.05
    AND ABS(`existing`.`position_y` - `restore`.`position_y`) < 0.05
    AND ABS(`existing`.`position_z` - `restore`.`position_z`) < 0.05
    AND ABS(`existing`.`orientation` - `restore`.`orientation`) < 0.01
SET `restore`.`resolved_guid` = `existing`.`guid`;

SET @remaining_pool_guid_start := (SELECT COALESCE(MAX(`guid`), 0) FROM `gameobject`);

UPDATE `_remaining_pool_variant`
SET `resolved_guid` = @remaining_pool_guid_start + `sequence_id`
WHERE `resolved_guid` IS NULL;

INSERT INTO `gameobject`
    (`guid`, `id`, `map`, `zoneId`, `areaId`, `spawnMask`, `phaseMask`,
     `phaseId`, `phaseGroup`, `position_x`, `position_y`, `position_z`,
     `orientation`, `rotation0`, `rotation1`, `rotation2`, `rotation3`,
     `spawntimesecs`, `animprogress`, `state`, `ScriptName`, `VerifiedBuild`)
SELECT
    `restore`.`resolved_guid`, `restore`.`entry`, `restore`.`map_id`,
    `restore`.`zone_id`, `restore`.`area_id`, 1, 1, 0, 0,
    `restore`.`position_x`, `restore`.`position_y`, `restore`.`position_z`,
    `restore`.`orientation`, 0, 0, SIN(`restore`.`orientation` / 2),
    COS(`restore`.`orientation` / 2),
    IF(`restore`.`entry` = 180662, 180, 3600), 100, 1, '', 0
FROM `_remaining_pool_variant` `restore`
LEFT JOIN `gameobject` `existing` ON `existing`.`guid` = `restore`.`resolved_guid`
WHERE `existing`.`guid` IS NULL;

-- Move collided memberships to the verified location pool, then add the
-- alternatives that were never pooled.  The spawns themselves stay intact.
UPDATE `pool_gameobject` `member`
INNER JOIN `_remaining_pool_variant` `restore`
    ON `restore`.`resolved_guid` = `member`.`guid`
SET `member`.`pool_entry` = `restore`.`target_pool`,
    `member`.`chance` = `restore`.`chance`,
    `member`.`description` = CONCAT('Restored resource location (source pool ',
                                    `restore`.`old_pool`, ')');

INSERT INTO `pool_gameobject` (`guid`, `pool_entry`, `chance`, `description`)
SELECT
    `restore`.`resolved_guid`, `restore`.`target_pool`, `restore`.`chance`,
    CONCAT('Restored resource location (source pool ', `restore`.`old_pool`, ')')
FROM `_remaining_pool_variant` `restore`
LEFT JOIN `pool_gameobject` `existing`
    ON `existing`.`guid` = `restore`.`resolved_guid`
WHERE `existing`.`guid` IS NULL;

UPDATE `pool_template` `template`
INNER JOIN
(
    SELECT `target_pool`, MIN(`old_pool`) AS `source_pool`
    FROM `_remaining_pool_variant`
    GROUP BY `target_pool`
) `restore` ON `restore`.`target_pool` = `template`.`entry`
SET `template`.`description` = CASE
    WHEN `template`.`description` IS NULL OR `template`.`description` = ''
        THEN CONCAT('Restored resource pool (AzerothCore source pool ',
                    `restore`.`source_pool`, ')')
    ELSE `template`.`description`
END;

-- ICC chooses the weekly quest in instance_icecrown_citadel and changes the
-- Kor'kron lieutenant to its Alliance entry at runtime.  Database pools 301,
-- 303 and the empty 517 hierarchy predate that logic and could suppress the
-- NPC selected by WeeklyIndex.  Preserve every spawn by making it direct.
DELETE FROM `pool_creature`
WHERE `pool_entry` IN (301, 303)
  AND `guid` IN
  (
      SELECT `guid`
      FROM `creature`
      WHERE `id` IN (38471, 38491, 38501, 38551)
  );

INSERT IGNORE INTO `creature_queststarter` (`id`, `quest`)
VALUES
    (38471, 24869), (38471, 24875),
    (38491, 24870), (38491, 24877),
    (38492, 24871), (38492, 24876),
    (38501, 24873), (38501, 24878),
    (38551, 24874), (38551, 24879),
    (38589, 24872), (38589, 24880);

-- All six weekly ICC quest NPCs are questgivers in both SkyFire reference
-- releases.  Preserve any existing flags (for example gossip) while restoring
-- UNIT_NPC_FLAG_QUESTGIVER (0x02), otherwise the relations above cannot be used.
UPDATE `creature_template`
SET `npcflag` = `npcflag` | 2
WHERE `entry` IN (38471, 38491, 38492, 38501, 38551, 38589);

DELETE FROM `pool_pool`
WHERE `mother_pool` = 517
  AND `pool_id` IN (518, 519, 520, 521, 522);

-- Retire only verified-empty, unreferenced definitions.  Their object content
-- either lives in the restored pools above, in the map-safe Outland 600xx
-- pools, or in the consolidated Pandaria resource pools.  The joins make the
-- cleanup refuse to remove a definition if it has acquired any real content.
DELETE `template`
FROM `pool_template` `template`
LEFT JOIN `pool_creature` `creature_member`
    ON `creature_member`.`pool_entry` = `template`.`entry`
LEFT JOIN `pool_gameobject` `gameobject_member`
    ON `gameobject_member`.`pool_entry` = `template`.`entry`
LEFT JOIN `pool_pool` `as_child`
    ON `as_child`.`pool_id` = `template`.`entry`
LEFT JOIN `pool_pool` `as_parent`
    ON `as_parent`.`mother_pool` = `template`.`entry`
LEFT JOIN `pool_quest` `quest_member`
    ON `quest_member`.`pool_entry` = `template`.`entry`
LEFT JOIN `game_event_pool` `event_member`
    ON `event_member`.`pool_entry` = `template`.`entry`
WHERE `template`.`entry` IN
(
    40, 56, 57, 58, 59, 60, 61, 62, 63, 66, 67, 68, 69, 70, 72,
    76, 77, 78, 79, 80, 81, 82, 83, 84, 89, 90,
    107, 113, 162, 175, 301, 302, 303, 304, 327, 328,
    517, 518, 519, 520, 521, 522, 1052, 1095,
    1134, 1137, 1138, 1139, 1140, 1141, 1142, 1143, 1240,
    30058, 30059, 30062, 30065, 30066, 30071, 30075, 30076,
    30081, 30085, 30086, 30088, 30090, 30096, 30097, 30100,
    30106, 30109, 30110, 30112, 30114, 30121, 30124, 30125,
    30126, 30135, 30184, 30186
)
  AND `creature_member`.`guid` IS NULL
  AND `gameobject_member`.`guid` IS NULL
  AND `as_child`.`pool_id` IS NULL
  AND `as_parent`.`mother_pool` IS NULL
  AND `quest_member`.`entry` IS NULL
  AND `event_member`.`pool_entry` IS NULL;

DROP TEMPORARY TABLE `_remaining_pool_variant`;
DROP TEMPORARY TABLE `_remaining_pool_location`;
