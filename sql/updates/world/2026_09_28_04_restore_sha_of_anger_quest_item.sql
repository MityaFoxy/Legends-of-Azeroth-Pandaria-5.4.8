-- Restore Claw of Anger to Sha of Anger's per-player loot path.
--
-- The item starts Remnants of Anger (31809).  Its original loot condition is
-- still present and prevents another claw after that quest is rewarded, but
-- the corresponding loot row was lost when Sha of Anger was converted to
-- personal loot.  The core now forwards quest and quest-start items from a
-- personal-loot creature's conventional template through the per-player
-- reward path, while retaining all normal loot conditions.

DELETE FROM `creature_loot_template`
WHERE `entry` = 60491
  AND `item` = 89317;

INSERT INTO `creature_loot_template`
    (`entry`, `item`, `ChanceOrQuestChance`, `lootmode`, `groupid`,
     `mincountOrRef`, `maxcount`)
VALUES
    (60491, 89317, 100, 'REGULAR', 0, 1, 1);
