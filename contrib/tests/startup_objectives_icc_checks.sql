-- Read-only post-migration checks for the audited world database.
-- Run with world selected. No data is changed by this file.
SELECT 'foreign objectives absent' AS check_name,
       IF(COUNT(*) = 0, 'PASS', 'FAIL') AS result
FROM `quest_objective` WHERE `id` IN (273866, 280563, 280564);

SELECT 'three objectives recoverable' AS check_name,
       IF(COUNT(*) = 3, 'PASS', 'FAIL') AS result
FROM `quest_objective_post_mop_archive` WHERE `id` IN (273866, 280563, 280564);

SELECT 'foreign locales absent' AS check_name,
       IF(COUNT(*) = 0, 'PASS', 'FAIL') AS result
FROM `quest_objectives_locale` WHERE `ID` IN (273866, 280563, 280564);

SELECT 'twenty locales recoverable' AS check_name,
       IF(COUNT(*) = 20, 'PASS', 'FAIL') AS result
FROM `quest_objectives_locale_post_mop_archive` WHERE `ID` IN (273866, 280563, 280564);

SELECT 'missing zealot restored once at historical position' AS check_name,
       IF(COUNT(*) = 1 AND MIN(`guid`) = 10011 AND MIN(`spawnMask`) = 120
          AND MIN(`phaseMask`) = 1 AND MIN(`modelid`) = 30357, 'PASS', 'FAIL') AS result
FROM `creature` WHERE `id` = 36808 AND `map` = 631
  AND ABS(`position_x` + 587.632) < 1 AND ABS(`position_y` - 2189.23) < 1
  AND ABS(`position_z` - 49.5599) < 1;

SELECT 'existing boss respawn link preserved and resolvable' AS check_name,
       IF(COUNT(*) = 1, 'PASS', 'FAIL') AS result
FROM `linked_respawn` r JOIN `creature` slave ON slave.`guid` = r.`guid`
JOIN `creature` master ON master.`guid` = r.`linkedGuid`
WHERE r.`guid` = 10011 AND r.`linkedGuid` = 136105 AND r.`linkType` = 0
  AND slave.`id` = 36808 AND master.`id` = 36855
  AND slave.`map` = 631 AND master.`map` = 631
  AND (slave.`spawnMask` & master.`spawnMask`) <> 0;

-- Open content debt, NOT a passing claim: expected 16 immediately after 09/10.
SELECT 'unresolved POI headers' AS diagnostic, COUNT(*) AS remaining
FROM `quest_poi` q WHERE NOT EXISTS
    (SELECT 1 FROM `quest_poi_points` p WHERE p.`QuestID` = q.`QuestID` AND p.`Idx1` = q.`Idx1`);
