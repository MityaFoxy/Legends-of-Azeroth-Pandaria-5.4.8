-- AreaTrigger 1282 is created by spell 147294 in Proving Grounds.  It is a
-- dynamic spell area trigger, not a static AreaTrigger.dbc record.  Restore
-- the missing template beside the related Proving Grounds trigger 1281 before
-- removing the invalid static-script binding that caused the DBC error.
INSERT INTO `spell_areatrigger_template`
    (`Entry`, `Flags`, `CollisionType`, `Radius`, `ScaleX`, `ScaleY`, `ScriptName`)
VALUES
    (1282, 0, 1, 3, 0, 0, 'sat_proving_grounds_berserking')
ON DUPLICATE KEY UPDATE
    `Flags` = VALUES(`Flags`),
    `CollisionType` = VALUES(`CollisionType`),
    `Radius` = VALUES(`Radius`),
    `ScaleX` = VALUES(`ScaleX`),
    `ScaleY` = VALUES(`ScaleY`),
    `ScriptName` = VALUES(`ScriptName`);

DELETE FROM `areatrigger_scripts`
WHERE `entry` = 1282
  AND `ScriptName` = 'sat_proving_grounds_berserking';

-- Prince Sarsarun has no static map-734 entrance trigger.  Restore the
-- explicit LFG entrance used by the later SkyFire world database for both
-- normal dungeon-list records, so LFG does not fall back to a nonexistent
-- areatrigger.  No LFG dungeon entry is removed or disabled.
INSERT INTO `lfg_dungeon_template`
    (`dungeonId`, `position_x`, `position_y`, `position_z`, `orientation`,
     `requiredItemLevel`)
VALUES
    (299, -9132.12, 1599.28, 26.848, 5.31086, 0),
    (310, -9132.12, 1599.28, 26.848, 5.31086, 0)
ON DUPLICATE KEY UPDATE
    `position_x` = VALUES(`position_x`),
    `position_y` = VALUES(`position_y`),
    `position_z` = VALUES(`position_z`),
    `orientation` = VALUES(`orientation`),
    `requiredItemLevel` = VALUES(`requiredItemLevel`);
