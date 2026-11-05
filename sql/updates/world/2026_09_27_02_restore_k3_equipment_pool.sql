-- Restore the membership of the existing K3 Equipment pool.
--
-- Pool 14140 is explicitly labelled GO=191568 and has max_limit=12, but all
-- 19 Northrend K3 Equipment objects had lost pool_gameobject membership and
-- therefore spawned simultaneously. MaNGOS Four's 5.4.8 database contains
-- the same template and all 19 entry/map/coordinate tuples. SkyFire 5.4.8
-- independently corroborates 17 of those 19 positions.
--
-- Sources:
--   mangosfour/Database, World/Setup/FullDB/{pool_template,gameobject}.sql
--   ProjectSkyfire/SkyFire_548, SFDB_full_548_26.002_2026_008_18_Release.sql
--
-- No gameobjects are inserted, changed, or deleted. The existing template
-- defines the intended selection limit; implicit equal chance is appropriate
-- for this set of alternatives.

INSERT INTO `pool_gameobject` (`guid`, `pool_entry`, `chance`, `description`)
SELECT
    `gameobject`.`guid`, 14140, 0, 'GO=191568'
FROM `gameobject`
LEFT JOIN `pool_gameobject`
    ON `pool_gameobject`.`guid` = `gameobject`.`guid`
    AND `pool_gameobject`.`pool_entry` = 14140
WHERE `gameobject`.`id` = 191568
    AND `gameobject`.`map` = 571
    AND `pool_gameobject`.`guid` IS NULL;
