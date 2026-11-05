-- MaNGOS Four's imported gathering-node data reused pool identifiers across
-- maps.  PoolMgr assigns one map to each pool and skips every member from a
-- different map, so the collisions silently remove valid resource spawns.
--
-- Keep the original pool identifier for the map recorded in the template
-- description (or the lowest map id when the old template has no map), then
-- move every other map-specific group into a new pool.  No gameobject spawn is
-- deleted and all chance/max_limit values are preserved.

DROP TEMPORARY TABLE IF EXISTS `_pool_gameobject_canonical_map`;
CREATE TEMPORARY TABLE `_pool_gameobject_canonical_map`
(
    `pool_entry` MEDIUMINT UNSIGNED NOT NULL,
    `map_id` SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (`pool_entry`)
) ENGINE=InnoDB;

INSERT INTO `_pool_gameobject_canonical_map` (`pool_entry`, `map_id`)
SELECT
    `pg`.`pool_entry`,
    COALESCE(
        MIN(CASE
            WHEN `pt`.`description` REGEXP 'map=[0-9]+$'
                AND `go`.`map` = CAST(SUBSTRING_INDEX(`pt`.`description`, 'map=', -1) AS UNSIGNED)
            THEN `go`.`map`
        END),
        MIN(`go`.`map`)
    ) AS `map_id`
FROM `pool_gameobject` `pg`
INNER JOIN `gameobject` `go` ON `go`.`guid` = `pg`.`guid`
INNER JOIN `pool_template` `pt` ON `pt`.`entry` = `pg`.`pool_entry`
GROUP BY `pg`.`pool_entry`
HAVING COUNT(DISTINCT `go`.`map`) > 1;

DROP TEMPORARY TABLE IF EXISTS `_pool_gameobject_map_split`;
CREATE TEMPORARY TABLE `_pool_gameobject_map_split`
(
    `sequence_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `old_pool_entry` MEDIUMINT UNSIGNED NOT NULL,
    `map_id` SMALLINT UNSIGNED NOT NULL,
    `member_count` INT UNSIGNED NOT NULL,
    PRIMARY KEY (`sequence_id`),
    UNIQUE KEY `uq_old_pool_map` (`old_pool_entry`, `map_id`)
) ENGINE=InnoDB;

INSERT INTO `_pool_gameobject_map_split` (`old_pool_entry`, `map_id`, `member_count`)
SELECT `pg`.`pool_entry`, `go`.`map`, COUNT(*)
FROM `pool_gameobject` `pg`
INNER JOIN `gameobject` `go` ON `go`.`guid` = `pg`.`guid`
INNER JOIN `_pool_gameobject_canonical_map` `canonical`
    ON `canonical`.`pool_entry` = `pg`.`pool_entry`
    AND `canonical`.`map_id` <> `go`.`map`
GROUP BY `pg`.`pool_entry`, `go`.`map`
ORDER BY `pg`.`pool_entry`, `go`.`map`;

SET @pool_gameobject_split_start := (SELECT COALESCE(MAX(`entry`), 0) FROM `pool_template`);

INSERT INTO `pool_template` (`entry`, `max_limit`, `description`)
SELECT
    @pool_gameobject_split_start + `split`.`sequence_id`,
    `template`.`max_limit`,
    CASE
        WHEN `template`.`description` REGEXP 'map=[0-9]+$' THEN
            CONCAT(SUBSTRING_INDEX(`template`.`description`, 'map=', 1), 'map=', `split`.`map_id`)
        ELSE
            CONCAT(
                COALESCE(`template`.`description`, ''),
                IF(COALESCE(`template`.`description`, '') = '', '', ','),
                'map=', `split`.`map_id`
            )
    END
FROM `_pool_gameobject_map_split` `split`
INNER JOIN `pool_template` `template` ON `template`.`entry` = `split`.`old_pool_entry`;

DROP TEMPORARY TABLE IF EXISTS `_pool_gameobject_guid_split`;
CREATE TEMPORARY TABLE `_pool_gameobject_guid_split`
(
    `guid` INT UNSIGNED NOT NULL,
    `sequence_id` INT UNSIGNED NOT NULL,
    PRIMARY KEY (`guid`)
) ENGINE=InnoDB;

-- STRAIGHT_JOIN makes MySQL scan pool_gameobject once and use the indexed
-- guid/map and old_pool_entry/map lookups. Without this intermediate mapping,
-- MySQL 8 can choose a nested-loop update over the unindexed pool_entry column.
INSERT INTO `_pool_gameobject_guid_split` (`guid`, `sequence_id`)
SELECT STRAIGHT_JOIN `pg`.`guid`, `split`.`sequence_id`
FROM `pool_gameobject` `pg`
INNER JOIN `gameobject` `go` ON `go`.`guid` = `pg`.`guid`
INNER JOIN `_pool_gameobject_map_split` `split`
    ON `split`.`old_pool_entry` = `pg`.`pool_entry`
    AND `split`.`map_id` = `go`.`map`;

UPDATE `pool_gameobject` `pg`
INNER JOIN `_pool_gameobject_guid_split` `split` ON `split`.`guid` = `pg`.`guid`
SET `pg`.`pool_entry` = @pool_gameobject_split_start + `split`.`sequence_id`;

DROP TEMPORARY TABLE `_pool_gameobject_guid_split`;
DROP TEMPORARY TABLE `_pool_gameobject_map_split`;
DROP TEMPORARY TABLE `_pool_gameobject_canonical_map`;
