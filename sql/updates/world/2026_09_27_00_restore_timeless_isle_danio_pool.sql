-- Restore the seven Timeless Isle spawn points for pool 30053.
--
-- The local pool template declares five simultaneous Glimmering Jewel Danio
-- pools but had no members. SkyFire 5.4.8 database release 26.002 supplies
-- seven matching map 870 spawn points. Wowhead independently identifies
-- gameobject 218652 as a Timeless Isle fishing pool. The nearby local
-- gameobjects establish zone 6757 / area 6831 for the newer schema.
--
-- Source:
--   ProjectSkyfire/SkyFire_548, SFDB_full_548_26.002_2026_008_18_Release.sql
--   https://www.wowhead.com/object=218652/glimmering-jewel-danio-pool
--
-- Existing spawns at the same logical coordinate are reused. Otherwise a new
-- GUID above the current maximum is allocated; unrelated current content is
-- never overwritten. All members use implicit equal selection (chance = 0).

DROP TEMPORARY TABLE IF EXISTS `_timeless_danio_pool_restore`;
CREATE TEMPORARY TABLE `_timeless_danio_pool_restore`
(
    `sequence_id` TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `position_x` FLOAT NOT NULL,
    `position_y` FLOAT NOT NULL,
    `position_z` FLOAT NOT NULL,
    `resolved_guid` INT UNSIGNED NULL,
    PRIMARY KEY (`sequence_id`)
) ENGINE=InnoDB;

INSERT INTO `_timeless_danio_pool_restore` (`position_x`, `position_y`, `position_z`)
VALUES
    (-602.786, -5230.040, -0.822097),
    (-625.911, -5241.290, -0.822100),
    (-626.335, -5247.640, -0.822094),
    (-642.536, -5195.670, -0.822112),
    (-667.710, -5188.890, -0.822098),
    (-673.234, -5201.650, -0.822109),
    (-690.240, -5213.540, -0.822098);

UPDATE `_timeless_danio_pool_restore` `restore`
INNER JOIN `gameobject` `existing`
    ON `existing`.`id` = 218652
    AND `existing`.`map` = 870
    AND ABS(`existing`.`position_x` - `restore`.`position_x`) < 0.01
    AND ABS(`existing`.`position_y` - `restore`.`position_y`) < 0.01
    AND ABS(`existing`.`position_z` - `restore`.`position_z`) < 0.01
SET `restore`.`resolved_guid` = `existing`.`guid`;

SET @timeless_danio_guid_start := (SELECT COALESCE(MAX(`guid`), 0) FROM `gameobject`);

UPDATE `_timeless_danio_pool_restore`
SET `resolved_guid` = @timeless_danio_guid_start + `sequence_id`
WHERE `resolved_guid` IS NULL;

INSERT INTO `gameobject`
    (`guid`, `id`, `map`, `zoneId`, `areaId`, `spawnMask`, `phaseMask`,
     `phaseId`, `phaseGroup`, `position_x`, `position_y`, `position_z`,
     `orientation`, `rotation0`, `rotation1`, `rotation2`, `rotation3`,
     `spawntimesecs`, `animprogress`, `state`, `ScriptName`, `VerifiedBuild`)
SELECT
    `restore`.`resolved_guid`, 218652, 870, 6757, 6831, 1, 1, 0, 0,
    `restore`.`position_x`, `restore`.`position_y`, `restore`.`position_z`,
    0, 0, 0, 0, 1, 120, 255, 1, '', 0
FROM `_timeless_danio_pool_restore` `restore`
LEFT JOIN `gameobject` `existing` ON `existing`.`guid` = `restore`.`resolved_guid`
WHERE `existing`.`guid` IS NULL;

INSERT INTO `pool_gameobject` (`guid`, `pool_entry`, `chance`, `description`)
SELECT
    `restore`.`resolved_guid`, 30053, 0, 'Glimmering Jewel Danio Pool (218652)'
FROM `_timeless_danio_pool_restore` `restore`
LEFT JOIN `pool_gameobject` `existing`
    ON `existing`.`guid` = `restore`.`resolved_guid`
    AND `existing`.`pool_entry` = 30053
WHERE `existing`.`guid` IS NULL;

DROP TEMPORARY TABLE IF EXISTS `_timeless_danio_pool_restore`;
