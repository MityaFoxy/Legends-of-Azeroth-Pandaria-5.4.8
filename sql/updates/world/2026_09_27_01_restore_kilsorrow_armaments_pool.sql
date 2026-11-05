-- Restore the membership of the existing Kil'sorrow Armaments pool.
--
-- Pool 14139 is explicitly labelled GO=182355 and has max_limit=20, but all
-- of its 54 Outland objects had lost pool_gameobject membership and therefore
-- spawned simultaneously. The 54 local entry/map/coordinate tuples exactly
-- match SkyFire 5.4.8 database release 26.002.
--
-- Source:
--   ProjectSkyfire/SkyFire_548, SFDB_full_548_26.002_2026_008_18_Release.sql
--
-- No gameobjects are inserted, changed, or deleted. The existing template
-- defines the intended selection limit; implicit equal chance is appropriate
-- for this set of alternatives.

INSERT INTO `pool_gameobject` (`guid`, `pool_entry`, `chance`, `description`)
SELECT
    `gameobject`.`guid`, 14139, 0, 'GO=182355'
FROM `gameobject`
LEFT JOIN `pool_gameobject`
    ON `pool_gameobject`.`guid` = `gameobject`.`guid`
    AND `pool_gameobject`.`pool_entry` = 14139
WHERE `gameobject`.`id` = 182355
    AND `gameobject`.`map` = 530
    AND `pool_gameobject`.`guid` IS NULL;
