-- User-approved retirement of the pre-Cataclysm escorts for quests 1249/9446.
-- Keep the surviving NPCs, quest records and a lossless copy of every point.
-- See doc/quest_32592_and_legacy_escorts_audit.md for historical evidence.
-- Fail closed if a custom script/quest binding or a conflicting archive exists.
START TRANSACTION;

CREATE TEMPORARY TABLE `_retired_escort_guard` (`ok` TINYINT PRIMARY KEY);
INSERT INTO `_retired_escort_guard` VALUES (1);
INSERT INTO `_retired_escort_guard`
SELECT 1 WHERE EXISTS
    (SELECT 1 FROM `creature_template` WHERE `entry` IN (4962, 17238)
        AND (`ScriptName` <> '' OR `AIName` <> ''))
    OR EXISTS (SELECT 1 FROM `creature_queststarter` WHERE `id` IN (4962, 17238))
    OR EXISTS (SELECT 1 FROM `creature_questender` WHERE `id` IN (4962, 17238))
    OR NOT EXISTS (SELECT 1 FROM `quest_template` WHERE `ID` = 1249 AND (`Flags` & 16384) <> 0)
    OR NOT EXISTS (SELECT 1 FROM `quest_template` WHERE `ID` = 9446 AND (`Flags` & 16384) <> 0);

INSERT INTO `script_waypoint_legacy_archive`
    (`entry`, `pointid`, `location_x`, `location_y`, `location_z`, `waittime`, `point_comment`)
SELECT sw.`entry`, sw.`pointid`, sw.`location_x`, sw.`location_y`, sw.`location_z`, sw.`waittime`, sw.`point_comment`
FROM `script_waypoint` sw
WHERE sw.`entry` IN (4962, 17238)
  AND NOT EXISTS (SELECT 1 FROM `script_waypoint_legacy_archive` a
      WHERE a.`entry` = sw.`entry` AND a.`pointid` = sw.`pointid`);

-- A matching primary key alone is not proof that a path is safely archived.
INSERT INTO `_retired_escort_guard`
SELECT 1 WHERE EXISTS
    (SELECT 1 FROM `script_waypoint` sw
     LEFT JOIN `script_waypoint_legacy_archive` a
         ON a.`entry` = sw.`entry` AND a.`pointid` = sw.`pointid`
     WHERE sw.`entry` IN (4962, 17238)
       AND (a.`entry` IS NULL
         OR NOT (a.`location_x` <=> sw.`location_x`)
         OR NOT (a.`location_y` <=> sw.`location_y`)
         OR NOT (a.`location_z` <=> sw.`location_z`)
         OR NOT (a.`waittime` <=> sw.`waittime`)
         OR NOT (BINARY a.`point_comment` <=> BINARY sw.`point_comment`)));

DELETE FROM `script_waypoint` WHERE `entry` IN (4962, 17238);
DROP TEMPORARY TABLE `_retired_escort_guard`;
COMMIT;
