-- Imported creature pools 210 and 30010 contain members from multiple maps.
-- PoolMgr supports one map per pool and skips the other members, which hides
-- Swiftmane and three of the five Cataclysm outdoor rare elites.
--
-- Preserve every creature spawn and split only the non-canonical map groups.
-- Existing pool ids stay with their lowest map because these templates have no
-- map metadata. Newly-created singleton pools with a partial explicit chance
-- are changed to equal chance: a singleton explicit pool whose chance is not
-- 100% is rejected by PoolMgr and would never spawn.

DROP TEMPORARY TABLE IF EXISTS `_pool_creature_canonical_map`;
CREATE TEMPORARY TABLE `_pool_creature_canonical_map`
(
    `pool_entry` MEDIUMINT UNSIGNED NOT NULL,
    `map_id` SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (`pool_entry`)
) ENGINE=InnoDB;

INSERT INTO `_pool_creature_canonical_map` (`pool_entry`, `map_id`)
SELECT `pc`.`pool_entry`, MIN(`creature`.`map`)
FROM `pool_creature` `pc`
INNER JOIN `creature` ON `creature`.`guid` = `pc`.`guid`
INNER JOIN `pool_template` `pt` ON `pt`.`entry` = `pc`.`pool_entry`
GROUP BY `pc`.`pool_entry`
HAVING COUNT(DISTINCT `creature`.`map`) > 1;

DROP TEMPORARY TABLE IF EXISTS `_pool_creature_map_split`;
CREATE TEMPORARY TABLE `_pool_creature_map_split`
(
    `sequence_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `old_pool_entry` MEDIUMINT UNSIGNED NOT NULL,
    `map_id` SMALLINT UNSIGNED NOT NULL,
    `member_count` INT UNSIGNED NOT NULL,
    `member_description` VARCHAR(255) NULL,
    PRIMARY KEY (`sequence_id`),
    UNIQUE KEY `uq_old_pool_map` (`old_pool_entry`, `map_id`)
) ENGINE=InnoDB;

INSERT INTO `_pool_creature_map_split`
    (`old_pool_entry`, `map_id`, `member_count`, `member_description`)
SELECT
    `pc`.`pool_entry`,
    `creature`.`map`,
    COUNT(*),
    MIN(`pc`.`description`)
FROM `pool_creature` `pc`
INNER JOIN `creature` ON `creature`.`guid` = `pc`.`guid`
INNER JOIN `_pool_creature_canonical_map` `canonical`
    ON `canonical`.`pool_entry` = `pc`.`pool_entry`
    AND `canonical`.`map_id` <> `creature`.`map`
GROUP BY `pc`.`pool_entry`, `creature`.`map`
ORDER BY `pc`.`pool_entry`, `creature`.`map`;

SET @pool_creature_split_start := (SELECT COALESCE(MAX(`entry`), 0) FROM `pool_template`);

INSERT INTO `pool_template` (`entry`, `max_limit`, `description`)
SELECT
    @pool_creature_split_start + `split`.`sequence_id`,
    `template`.`max_limit`,
    CONCAT(
        COALESCE(
            NULLIF(`template`.`description`, ''),
            NULLIF(`split`.`member_description`, ''),
            CONCAT('Creature pool ', `split`.`old_pool_entry`)
        ),
        ',map=', `split`.`map_id`
    )
FROM `_pool_creature_map_split` `split`
INNER JOIN `pool_template` `template` ON `template`.`entry` = `split`.`old_pool_entry`;

DROP TEMPORARY TABLE IF EXISTS `_pool_creature_guid_split`;
CREATE TEMPORARY TABLE `_pool_creature_guid_split`
(
    `guid` INT UNSIGNED NOT NULL,
    `sequence_id` INT UNSIGNED NOT NULL,
    `member_count` INT UNSIGNED NOT NULL,
    PRIMARY KEY (`guid`)
) ENGINE=InnoDB;

INSERT INTO `_pool_creature_guid_split` (`guid`, `sequence_id`, `member_count`)
SELECT STRAIGHT_JOIN `pc`.`guid`, `split`.`sequence_id`, `split`.`member_count`
FROM `pool_creature` `pc`
INNER JOIN `creature` ON `creature`.`guid` = `pc`.`guid`
INNER JOIN `_pool_creature_map_split` `split`
    ON `split`.`old_pool_entry` = `pc`.`pool_entry`
    AND `split`.`map_id` = `creature`.`map`;

UPDATE `pool_creature` `pc`
INNER JOIN `_pool_creature_guid_split` `split` ON `split`.`guid` = `pc`.`guid`
SET
    `pc`.`pool_entry` = @pool_creature_split_start + `split`.`sequence_id`,
    `pc`.`chance` = IF(
        `split`.`member_count` = 1 AND `pc`.`chance` > 0 AND `pc`.`chance` < 100,
        0,
        `pc`.`chance`
    );

-- Add map context to the two retained source templates as well.
UPDATE `pool_template` `template`
INNER JOIN `_pool_creature_canonical_map` `canonical`
    ON `canonical`.`pool_entry` = `template`.`entry`
SET `template`.`description` = CONCAT(
    COALESCE(NULLIF(`template`.`description`, ''), CONCAT('Creature pool ', `template`.`entry`)),
    ',map=', `canonical`.`map_id`
);

DROP TEMPORARY TABLE `_pool_creature_guid_split`;
DROP TEMPORARY TABLE `_pool_creature_map_split`;
DROP TEMPORARY TABLE `_pool_creature_canonical_map`;
