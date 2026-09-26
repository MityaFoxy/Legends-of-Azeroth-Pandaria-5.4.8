-- Restore the six-location rare-spawn route for Minigob Manabonk (32838).
--
-- MaNGOS Four 5.4.8 FullDB is the source for pool 9868: it declares a
-- max_limit of one and six creature members (source GUIDs 54462, 54527,
-- 54528, 54531, 54532 and 54553).  The source GUIDs cannot be reused here:
-- they are occupied by unrelated local creatures.  Resolve an existing
-- equivalent spawn first and allocate a new GUID only when necessary.
--
-- The source schema has no zoneId/areaId columns.  These Storm Peaks points
-- use the locally established Minigob location profile (4395/4613); all
-- gameplay coordinates, orientation and respawn time come from the source.
-- Do not add local GUID 44457 to this pool: it is a seventh, unmatched local
-- point and has not yet been corroborated by a trusted source.

DROP TEMPORARY TABLE IF EXISTS `_minigob_manabonk_source`;
CREATE TEMPORARY TABLE `_minigob_manabonk_source`
(
    `sequence_id` TINYINT UNSIGNED NOT NULL,
    `source_guid` INT UNSIGNED NOT NULL,
    `position_x` FLOAT NOT NULL,
    `position_y` FLOAT NOT NULL,
    `position_z` FLOAT NOT NULL,
    `orientation` FLOAT NOT NULL,
    `resolved_guid` INT UNSIGNED NULL,
    PRIMARY KEY (`sequence_id`),
    UNIQUE KEY `uq_source_guid` (`source_guid`)
) ENGINE=InnoDB;

INSERT INTO `_minigob_manabonk_source`
    (`sequence_id`, `source_guid`, `position_x`, `position_y`, `position_z`, `orientation`)
VALUES
    (1, 54462, 5942.73, 629.969, 650.590, 2.86552),
    (2, 54527, 5843.95, 650.709, 647.513, 6.02801),
    (3, 54528, 5974.10, 611.642, 650.628, 2.70735),
    (4, 54531, 5638.53, 688.596, 651.993, 5.75313),
    (5, 54532, 5664.96, 669.614, 651.969, 5.97177),
    (6, 54553, 5854.42, 660.310, 647.512, 3.71924);

UPDATE `_minigob_manabonk_source` `source`
SET `resolved_guid` = (
    SELECT MIN(`creature`.`guid`)
    FROM `creature`
    WHERE `creature`.`id` = 32838
      AND `creature`.`map` = 571
      AND ABS(`creature`.`position_x` - `source`.`position_x`) < 0.01
      AND ABS(`creature`.`position_y` - `source`.`position_y`) < 0.01
      AND ABS(`creature`.`position_z` - `source`.`position_z`) < 0.01
);

SET @minigob_manabonk_guid_start := (SELECT COALESCE(MAX(`guid`), 0) FROM `creature`);
UPDATE `_minigob_manabonk_source`
SET `resolved_guid` = @minigob_manabonk_guid_start + `sequence_id`
WHERE `resolved_guid` IS NULL;

INSERT INTO `creature`
    (`guid`, `id`, `map`, `zoneId`, `areaId`, `spawnMask`, `phaseMask`, `phaseId`, `phaseGroup`,
     `modelid`, `equipment_id`, `position_x`, `position_y`, `position_z`, `orientation`,
     `spawntimesecs`, `spawntimesecs_max`, `wander_distance`, `currentwaypoint`, `curhealth`,
     `curmana`, `MovementType`, `npcflag`, `npcflag2`, `unit_flags`, `unit_flags2`, `dynamicflags`,
     `ScriptName`, `walk_mode`, `VerifiedBuild`)
SELECT
    `source`.`resolved_guid`, 32838, 571, 4395, 4613, 1, 1, 0, 0,
    0, 0, `source`.`position_x`, `source`.`position_y`, `source`.`position_z`, `source`.`orientation`,
    300, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0,
    NULL, 0, 0
FROM `_minigob_manabonk_source` `source`
LEFT JOIN `creature` ON `creature`.`guid` = `source`.`resolved_guid`
WHERE `creature`.`guid` IS NULL;

INSERT INTO `pool_creature` (`guid`, `pool_entry`, `chance`, `description`)
SELECT `source`.`resolved_guid`, 9868, 0, '32838'
FROM `_minigob_manabonk_source` `source`
LEFT JOIN `pool_creature` ON `pool_creature`.`guid` = `source`.`resolved_guid`
WHERE `pool_creature`.`guid` IS NULL;

DROP TEMPORARY TABLE `_minigob_manabonk_source`;
