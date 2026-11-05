-- The Darkmoon Faire island spawns retain MovementType = WAYPOINT_MOTION_TYPE,
-- but their GUID-keyed paths were omitted from the imported world data.
-- Coordinates are from the historical Darkmoon Faire data for map 974.
INSERT INTO `waypoint_data`
    (`id`, `point`, `position_x`, `position_y`, `position_z`, `orientation`,
     `delay`, `move_flag`, `action`, `action_chance`, `wpguid`, `entry`)
VALUES
    (303619, 0, -4359.23, 6341.64, 10.5720, 0, 0, 0, 0, 100, 0, 'Silas Darkmoon'),
    (303619, 1, -4360.21, 6341.45, 10.5720, 0, 0, 0, 0, 100, 0, 'Silas Darkmoon'),
    (303619, 2, -4361.21, 6341.25, 10.6210, 0, 0, 0, 0, 100, 0, 'Silas Darkmoon'),
    (303619, 3, -4364.32, 6340.63, 10.8405, 0, 0, 0, 0, 100, 0, 'Silas Darkmoon'),
    (303619, 4, -4374.91, 6337.66, 11.4015, 0, 0, 0, 0, 100, 0, 'Silas Darkmoon'),
    (303619, 5, -4378.73, 6336.58, 11.6141, 0, 0, 0, 0, 100, 0, 'Silas Darkmoon'),
    (303619, 6, -4378.73, 6336.58, 11.6141, 0, 0, 0, 0, 100, 0, 'Silas Darkmoon'),
    (303637, 0, -4172.85, 6276.03, 13.2417, 0, 0, 0, 0, 100, 0, 'Flik'),
    (303637, 1, -4173.57, 6276.72, 13.2417, 0, 0, 0, 0, 100, 0, 'Flik'),
    (303637, 2, -4175.00, 6278.13, 13.2417, 0, 0, 0, 0, 100, 0, 'Flik'),
    (303637, 3, -4176.04, 6279.17, 13.2417, 0, 0, 0, 0, 100, 0, 'Flik'),
    (303637, 4, -4179.17, 6281.77, 13.2417, 0, 0, 0, 0, 100, 0, 'Flik'),
    (303637, 5, -4180.63, 6281.76, 13.5457, 0, 0, 0, 0, 100, 0, 'Flik'),
    (303637, 6, -4181.31, 6282.92, 14.1531, 0, 0, 0, 0, 100, 0, 'Flik')
ON DUPLICATE KEY UPDATE
    `position_x` = VALUES(`position_x`),
    `position_y` = VALUES(`position_y`),
    `position_z` = VALUES(`position_z`),
    `orientation` = VALUES(`orientation`),
    `delay` = VALUES(`delay`),
    `move_flag` = VALUES(`move_flag`),
    `action` = VALUES(`action`),
    `action_chance` = VALUES(`action_chance`),
    `wpguid` = VALUES(`wpguid`),
    `entry` = VALUES(`entry`);
