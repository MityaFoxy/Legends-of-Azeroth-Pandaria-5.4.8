-- Ghostwing's two-point flight was omitted when its SmartAI was imported.
-- The coordinates are from TrinityCore's original WotLK quest fix
-- (2016_03_03_01_world.sql): approach Olakin, then depart after taking him.
INSERT INTO `waypoints`
    (`entry`, `pointid`, `position_x`, `position_y`, `position_z`, `orientation`,
     `delay`, `point_comment`)
VALUES
    (31432, 1, 6644.43, 3222.912, 823.0705, NULL, 0, 'Ghostwing'),
    (31432, 2, 6690.65, 3177.279, 860.5705, NULL, 0, 'Ghostwing')
ON DUPLICATE KEY UPDATE
    `position_x` = VALUES(`position_x`),
    `position_y` = VALUES(`position_y`),
    `position_z` = VALUES(`position_z`),
    `orientation` = VALUES(`orientation`),
    `delay` = VALUES(`delay`),
    `point_comment` = VALUES(`point_comment`);

-- The imported script's comment and the retail scene both require Olakin,
-- not Ghostwing, to be removed at the final waypoint.  The original source
-- accidentally targeted Ghostwing twice; id 8 already despawns Ghostwing.
UPDATE `smart_scripts`
SET `target_param1` = 31428,
    `comment` = 'Ghostwing - On Reached WP2 - Despawn Crusader Olakin Sainrith'
WHERE `entryorguid` = 31432 AND `source_type` = 0 AND `id` = 7
    AND `action_type` = 41 AND `target_type` = 19;
