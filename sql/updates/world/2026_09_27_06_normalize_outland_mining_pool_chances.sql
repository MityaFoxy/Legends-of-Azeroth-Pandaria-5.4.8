-- Normalize the gameobject selection weights restored by
-- 2026_09_26_03_restore_outland_mining_pools.sql.
--
-- YTDB's member values describe the individual node occurrence rates.  When
-- they were copied directly into a max_limit=1 Trinity-style pool, 290 child
-- pools had only explicit members whose sums were 180 or 200.  PoolMgr
-- consequently rejected them and did not activate their parent hierarchy.
--
-- Retain every member and its relative probability, but normalize each
-- all-explicit YTDB child group to the 100-percent invariant required by
-- PoolMgr.  Groups with an equal-chance (zero) member are intentionally left
-- unchanged because the core handles that mixed form separately.

DROP TEMPORARY TABLE IF EXISTS `_outland_ore_invalid_chance_total`;
CREATE TEMPORARY TABLE `_outland_ore_invalid_chance_total`
(
    `pool_entry` MEDIUMINT UNSIGNED NOT NULL,
    `chance_total` DECIMAL(12,6) NOT NULL,
    PRIMARY KEY (`pool_entry`)
) ENGINE=InnoDB;

INSERT INTO `_outland_ore_invalid_chance_total` (`pool_entry`, `chance_total`)
SELECT
    `member`.`pool_entry`,
    SUM(`member`.`chance`)
FROM `pool_gameobject` `member`
INNER JOIN `pool_template` `template`
    ON `template`.`entry` = `member`.`pool_entry`
WHERE `member`.`pool_entry` BETWEEN 50000 AND 51319
  AND `template`.`max_limit` = 1
  AND LEFT(COALESCE(`template`.`description`, ''), 11) = 'YTDB R667: '
GROUP BY `member`.`pool_entry`
HAVING MIN(`member`.`chance`) > 0
   AND ABS(SUM(`member`.`chance`) - 100) > 0.0001;

UPDATE `pool_gameobject` `member`
INNER JOIN `_outland_ore_invalid_chance_total` `invalid`
    ON `invalid`.`pool_entry` = `member`.`pool_entry`
SET `member`.`chance` = ROUND(`member`.`chance` * 100 / `invalid`.`chance_total`, 6);

DROP TEMPORARY TABLE `_outland_ore_invalid_chance_total`;
