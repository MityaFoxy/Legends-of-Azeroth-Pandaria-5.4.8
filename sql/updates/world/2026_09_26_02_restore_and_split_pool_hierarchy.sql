-- MaNGOS Four database commit 8b798ac6 contains four resource pools whose
-- gameobject members were lost here through GUID collisions during import.
-- Restore those twelve spawns without overwriting the objects which currently
-- own eight of the legacy GUIDs, then split flat mother pools by map. PoolMgr
-- supports only one map per mother pool and otherwise skips child relations.

DROP TEMPORARY TABLE IF EXISTS `_pool_gameobject_restore`;
CREATE TEMPORARY TABLE `_pool_gameobject_restore`
(
    `sequence_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `legacy_guid` INT UNSIGNED NOT NULL,
    `pool_entry` MEDIUMINT UNSIGNED NOT NULL,
    `chance` FLOAT NOT NULL,
    `description` VARCHAR(255) NOT NULL,
    `id` MEDIUMINT UNSIGNED NOT NULL,
    `map_id` SMALLINT UNSIGNED NOT NULL,
    `zone_id` INT UNSIGNED NOT NULL,
    `area_id` INT UNSIGNED NOT NULL,
    `spawn_mask` INT NOT NULL,
    `phase_mask` INT UNSIGNED NOT NULL,
    `position_x` FLOAT NOT NULL,
    `position_y` FLOAT NOT NULL,
    `position_z` FLOAT NOT NULL,
    `orientation` FLOAT NOT NULL,
    `rotation0` FLOAT NOT NULL,
    `rotation1` FLOAT NOT NULL,
    `rotation2` FLOAT NOT NULL,
    `rotation3` FLOAT NOT NULL,
    `spawntimesecs` INT NOT NULL,
    `animprogress` TINYINT UNSIGNED NOT NULL,
    `state` TINYINT UNSIGNED NOT NULL,
    `resolved_guid` INT UNSIGNED NULL,
    PRIMARY KEY (`sequence_id`),
    UNIQUE KEY `uq_legacy_guid` (`legacy_guid`)
) ENGINE=InnoDB;

INSERT INTO `_pool_gameobject_restore`
    (`legacy_guid`, `pool_entry`, `chance`, `description`, `id`, `map_id`,
     `zone_id`, `area_id`, `spawn_mask`, `phase_mask`, `position_x`,
     `position_y`, `position_z`, `orientation`, `rotation0`, `rotation1`,
     `rotation2`, `rotation3`, `spawntimesecs`, `animprogress`, `state`)
VALUES
    (22567, 6576, 90, 'GO 1732,[1733],map=1', 1732, 1, 4709, 4709, 1, 65535, -1823.37, -3773.67, 12.588, 3.22719, 0, 0, 0.999084, -0.0427856, 600, 100, 1),
    (81263, 6576, 10, 'GO 1732,[1733],map=1', 1733, 1, 4709, 4709, 1, 65535, -1823.37, -3773.67, 12.588, 3.22719, 0, 0, 0.999084, -0.0427856, 1200, 100, 1),
    (22569, 6590, 90, 'GO 1732,[1733],map=1', 1732, 1, 4709, 4709, 1, 65535, -1832.49, -3684.95, 25.1246, 3.22719, 0, 0, 0.999084, -0.0427856, 600, 100, 1),
    (81257, 6590, 10, 'GO 1732,[1733],map=1', 1733, 1, 4709, 4709, 1, 65535, -1832.49, -3684.95, 25.1246, 3.22719, 0, 0, 0.999084, -0.0427856, 1200, 100, 1),
    (3176, 7154, 70, 'GO 1735,[1733,1734,1732],map=1', 1735, 1, 440, 985, 1, 65535, -7386, -4485, 13.804, 0.297, 0, 0, 0.147955, 0.988994, 600, 100, 1),
    (82273, 7154, 10, 'GO 1735,[1733,1734,1732],map=1', 1733, 1, 440, 985, 1, 65535, -7386, -4485, 13.804, 0.297, 0, 0, 0.147955, 0.988994, 1200, 100, 1),
    (82274, 7154, 10, 'GO 1735,[1733,1734,1732],map=1', 1734, 1, 440, 985, 1, 65535, -7386, -4485, 13.804, 0.297, 0, 0, 0.147955, 0.988994, 1200, 100, 1),
    (82275, 7154, 10, 'GO 1735,[1733,1734,1732],map=1', 1732, 1, 440, 985, 1, 65535, -7386, -4485, 13.804, 0.297, 0, 0, 0.147955, 0.988994, 600, 100, 1),
    (4003, 7713, 70, 'GO 1735,[1733,1734,1732],map=1', 1735, 1, 440, 985, 1, 65535, -7764, -4435, 9.63485, 4.846, 0, 0, 0.658326, -0.752733, 600, 100, 1),
    (82342, 7713, 10, 'GO 1735,[1733,1734,1732],map=1', 1733, 1, 440, 985, 1, 65535, -7764, -4435, 9.63485, 4.846, 0, 0, 0.658326, -0.752733, 1200, 100, 1),
    (82343, 7713, 10, 'GO 1735,[1733,1734,1732],map=1', 1734, 1, 440, 985, 1, 65535, -7764, -4435, 9.63485, 4.846, 0, 0, 0.658326, -0.752733, 1200, 100, 1),
    (82344, 7713, 10, 'GO 1735,[1733,1734,1732],map=1', 1732, 1, 440, 985, 1, 65535, -7764, -4435, 9.63485, 4.846, 0, 0, 0.658326, -0.752733, 600, 100, 1);

INSERT INTO `pool_template` (`entry`, `max_limit`, `description`)
SELECT 6576, 1, 'GO 1732,[1733],map=1'
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM `pool_template` WHERE `entry` = 6576)
UNION ALL
SELECT 6590, 1, 'GO 1732,[1733],map=1'
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM `pool_template` WHERE `entry` = 6590);

-- Reuse an already-restored spawn when the migration is run more than once.
UPDATE `_pool_gameobject_restore` `restore`
INNER JOIN `gameobject` `existing`
    ON `existing`.`id` = `restore`.`id`
    AND `existing`.`map` = `restore`.`map_id`
    AND ABS(`existing`.`position_x` - `restore`.`position_x`) < 0.01
    AND ABS(`existing`.`position_y` - `restore`.`position_y`) < 0.01
    AND ABS(`existing`.`position_z` - `restore`.`position_z`) < 0.01
SET `restore`.`resolved_guid` = `existing`.`guid`;

SET @pool_restore_guid_start := (SELECT COALESCE(MAX(`guid`), 0) FROM `gameobject`);

UPDATE `_pool_gameobject_restore`
SET `resolved_guid` = @pool_restore_guid_start + `sequence_id`
WHERE `resolved_guid` IS NULL;

INSERT INTO `gameobject`
    (`guid`, `id`, `map`, `zoneId`, `areaId`, `spawnMask`, `phaseMask`,
     `phaseId`, `phaseGroup`, `position_x`, `position_y`, `position_z`,
     `orientation`, `rotation0`, `rotation1`, `rotation2`, `rotation3`,
     `spawntimesecs`, `animprogress`, `state`, `ScriptName`, `VerifiedBuild`)
SELECT
    `restore`.`resolved_guid`, `restore`.`id`, `restore`.`map_id`,
    `restore`.`zone_id`, `restore`.`area_id`, `restore`.`spawn_mask`,
    `restore`.`phase_mask`, 0, 0, `restore`.`position_x`,
    `restore`.`position_y`, `restore`.`position_z`, `restore`.`orientation`,
    `restore`.`rotation0`, `restore`.`rotation1`, `restore`.`rotation2`,
    `restore`.`rotation3`, `restore`.`spawntimesecs`, `restore`.`animprogress`,
    `restore`.`state`, '', 0
FROM `_pool_gameobject_restore` `restore`
LEFT JOIN `gameobject` `existing` ON `existing`.`guid` = `restore`.`resolved_guid`
WHERE `existing`.`guid` IS NULL;

INSERT INTO `pool_gameobject` (`guid`, `pool_entry`, `chance`, `description`)
SELECT
    `restore`.`resolved_guid`, `restore`.`pool_entry`, `restore`.`chance`,
    `restore`.`description`
FROM `_pool_gameobject_restore` `restore`
LEFT JOIN `pool_gameobject` `existing`
    ON `existing`.`guid` = `restore`.`resolved_guid`
WHERE `existing`.`guid` IS NULL;

DROP TEMPORARY TABLE IF EXISTS `_pool_pool_child_map`;
CREATE TEMPORARY TABLE `_pool_pool_child_map`
(
    `pool_id` MEDIUMINT UNSIGNED NOT NULL,
    `mother_pool` MEDIUMINT UNSIGNED NOT NULL,
    `map_id` SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (`pool_id`),
    KEY `idx_mother_map` (`mother_pool`, `map_id`)
) ENGINE=InnoDB;

-- Real spawn maps take precedence. Empty imported GO pools retain a reliable
-- map suffix in their template description and can still be grouped safely.
INSERT INTO `_pool_pool_child_map` (`pool_id`, `mother_pool`, `map_id`)
SELECT
    `pp`.`pool_id`,
    `pp`.`mother_pool`,
    COALESCE(
        `actual`.`map_id`,
        CASE
            WHEN `child_template`.`description` REGEXP 'map[= ][0-9]+$' THEN
                CAST(
                    REPLACE(
                        REPLACE(SUBSTRING_INDEX(`child_template`.`description`, 'map', -1), '=', ''),
                        ' ',
                        ''
                    ) AS UNSIGNED
                )
        END
    ) AS `map_id`
FROM `pool_pool` `pp`
LEFT JOIN
(
    SELECT `leaf`.`pool_entry`, MIN(`leaf`.`map_id`) AS `map_id`
    FROM
    (
        SELECT `pc`.`pool_entry`, `creature`.`map` AS `map_id`
        FROM `pool_creature` `pc`
        INNER JOIN `creature` ON `creature`.`guid` = `pc`.`guid`
        UNION ALL
        SELECT `pg`.`pool_entry`, `go`.`map` AS `map_id`
        FROM `pool_gameobject` `pg`
        INNER JOIN `gameobject` `go` ON `go`.`guid` = `pg`.`guid`
    ) `leaf`
    GROUP BY `leaf`.`pool_entry`
) `actual` ON `actual`.`pool_entry` = `pp`.`pool_id`
LEFT JOIN `pool_template` `child_template`
    ON `child_template`.`entry` = `pp`.`pool_id`
WHERE COALESCE(
    `actual`.`map_id`,
    CASE
        WHEN `child_template`.`description` REGEXP 'map[= ][0-9]+$' THEN
            CAST(
                REPLACE(
                    REPLACE(SUBSTRING_INDEX(`child_template`.`description`, 'map', -1), '=', ''),
                    ' ',
                    ''
                ) AS UNSIGNED
            )
    END
) IS NOT NULL;

DROP TEMPORARY TABLE IF EXISTS `_pool_pool_canonical_map`;
CREATE TEMPORARY TABLE `_pool_pool_canonical_map`
(
    `mother_pool` MEDIUMINT UNSIGNED NOT NULL,
    `map_id` SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (`mother_pool`)
) ENGINE=InnoDB;

INSERT INTO `_pool_pool_canonical_map` (`mother_pool`, `map_id`)
SELECT `mother_pool`, MIN(`map_id`)
FROM `_pool_pool_child_map`
GROUP BY `mother_pool`
HAVING COUNT(DISTINCT `map_id`) > 1;

DROP TEMPORARY TABLE IF EXISTS `_pool_pool_map_split`;
CREATE TEMPORARY TABLE `_pool_pool_map_split`
(
    `sequence_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `old_mother_pool` MEDIUMINT UNSIGNED NOT NULL,
    `map_id` SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (`sequence_id`),
    UNIQUE KEY `uq_old_mother_map` (`old_mother_pool`, `map_id`)
) ENGINE=InnoDB;

INSERT INTO `_pool_pool_map_split` (`old_mother_pool`, `map_id`)
SELECT DISTINCT `child`.`mother_pool`, `child`.`map_id`
FROM `_pool_pool_child_map` `child`
INNER JOIN `_pool_pool_canonical_map` `canonical`
    ON `canonical`.`mother_pool` = `child`.`mother_pool`
    AND `canonical`.`map_id` <> `child`.`map_id`
ORDER BY `child`.`mother_pool`, `child`.`map_id`;

SET @pool_pool_split_start := (SELECT COALESCE(MAX(`entry`), 0) FROM `pool_template`);

INSERT INTO `pool_template` (`entry`, `max_limit`, `description`)
SELECT
    @pool_pool_split_start + `split`.`sequence_id`,
    `source_template`.`max_limit`,
    CASE
        WHEN `source_template`.`description` REGEXP 'map=[0-9]+$' THEN
            CONCAT(
                SUBSTRING_INDEX(`source_template`.`description`, 'map=', 1),
                'map=', `split`.`map_id`
            )
        ELSE
            CONCAT(
                COALESCE(NULLIF(`source_template`.`description`, ''),
                    CONCAT('Mother pool ', `split`.`old_mother_pool`)),
                ',map=', `split`.`map_id`
            )
    END
FROM `_pool_pool_map_split` `split`
INNER JOIN `pool_template` `source_template`
    ON `source_template`.`entry` = `split`.`old_mother_pool`;

UPDATE `pool_pool` `pp`
INNER JOIN `_pool_pool_child_map` `child`
    ON `child`.`pool_id` = `pp`.`pool_id`
INNER JOIN `_pool_pool_map_split` `split`
    ON `split`.`old_mother_pool` = `child`.`mother_pool`
    AND `split`.`map_id` = `child`.`map_id`
SET `pp`.`mother_pool` = @pool_pool_split_start + `split`.`sequence_id`;

UPDATE `pool_template` `mother_template`
INNER JOIN `_pool_pool_canonical_map` `canonical`
    ON `canonical`.`mother_pool` = `mother_template`.`entry`
SET `mother_template`.`description` = CASE
    WHEN `mother_template`.`description` REGEXP 'map=[0-9]+$' THEN
        CONCAT(
            SUBSTRING_INDEX(`mother_template`.`description`, 'map=', 1),
            'map=', `canonical`.`map_id`
        )
    ELSE
        CONCAT(
            COALESCE(NULLIF(`mother_template`.`description`, ''),
                CONCAT('Mother pool ', `mother_template`.`entry`)),
            ',map=', `canonical`.`map_id`
        )
END;

DROP TEMPORARY TABLE `_pool_pool_map_split`;
DROP TEMPORARY TABLE `_pool_pool_canonical_map`;
DROP TEMPORARY TABLE `_pool_pool_child_map`;
DROP TEMPORARY TABLE `_pool_gameobject_restore`;
