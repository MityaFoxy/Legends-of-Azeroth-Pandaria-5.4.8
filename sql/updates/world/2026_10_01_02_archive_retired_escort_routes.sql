-- Preserve legacy waypoint rows while removing them from the active loader.
-- These entries belong to quests or instance layouts retired before MoP:
--   349   Corporal Keeshan, old quest 219 route (obsolete in MoP)
--   1754  Lord Gregor Lescovar, obsolete quest 434 event
--   3849/3850 Shadowfang prisoners; no creature spawns in this MoP world DB
--   4962  Tapoke "Slim" Jahn, retired Missing Diplomat escort
--   6575  Scarlet Trainee, old Herod encounter removed by the MoP rewrite
--   8856  Tyrion's Spybot, obsolete quest 2745/434 event
--   17238 Anchorite Truuen, obsolete quest 9446
CREATE TABLE IF NOT EXISTS `script_waypoint_legacy_archive` LIKE `script_waypoint`;

INSERT IGNORE INTO `script_waypoint_legacy_archive`
SELECT * FROM `script_waypoint`
WHERE `entry` IN (349, 1754, 3849, 3850, 4962, 6575, 8856, 17238);

DELETE FROM `script_waypoint`
WHERE `entry` IN (349, 1754, 3849, 3850, 4962, 6575, 8856, 17238);
