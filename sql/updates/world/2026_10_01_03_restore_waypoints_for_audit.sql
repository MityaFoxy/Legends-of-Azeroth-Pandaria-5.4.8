-- Restore the eight routes removed by 2026_10_01_02. Their absence from the
-- current loader does not prove that they are obsolete in MoP. Keep the archive
-- as a safety copy while their quest and encounter mechanics are audited.
INSERT IGNORE INTO `script_waypoint`
SELECT * FROM `script_waypoint_legacy_archive`
WHERE `entry` IN (349, 1754, 3849, 3850, 4962, 6575, 8856, 17238);
