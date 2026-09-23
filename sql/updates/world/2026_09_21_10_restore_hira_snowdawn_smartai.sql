-- Restore Hira Snowdawn's idle flight sequence. The two parent rows had the
-- action type shifted into action_param1, while both timed action lists were
-- missing. The existing 11-point path and creature_text already match the
-- original sequence and are intentionally left untouched.
SET @HIRA := 31238;

DELETE FROM `smart_scripts`
WHERE (`entryorguid` = @HIRA AND `source_type` = 0)
   OR (`entryorguid` IN (@HIRA * 100, @HIRA * 100 + 1) AND `source_type` = 9);

INSERT INTO `smart_scripts`
(`entryorguid`, `source_type`, `id`, `link`, `event_type`, `event_phase_mask`, `event_chance`, `event_flags`,
 `event_param1`, `event_param2`, `event_param3`, `event_param4`,
 `action_type`, `action_param1`, `action_param2`, `action_param3`, `action_param4`, `action_param5`, `action_param6`,
 `target_type`, `target_param1`, `target_param2`, `target_param3`,
 `target_x`, `target_y`, `target_z`, `target_o`, `comment`)
VALUES
(@HIRA,         0, 0, 0,  1, 0, 100, 0, 600000, 600000, 600000, 600000, 80, @HIRA * 100,     0, 0,        0, 0, 0, 1, 0, 0, 0,    0,        0,        0,        0,        'Hira Snowdawn - OOC - Run idle flight action list'),
(@HIRA,         0, 1, 0, 40, 0, 100, 0,     11,      0,      0,      0, 80, @HIRA * 100 + 1, 0, 0,        0, 0, 0, 1, 0, 0, 0,    0,        0,        0,        0,        'Hira Snowdawn - On waypoint 11 reached - Run return action list'),
(@HIRA * 100,   9, 0, 0,  0, 0, 100, 0,      0,      0,      0,      0,  1, 1,                 0, 0,        0, 0, 0, 1, 0, 0, 0,    0,        0,        0,        0,        'Hira Snowdawn - Idle flight - Talk emote'),
(@HIRA * 100,   9, 1, 0,  0, 0, 100, 0,   5000,   5000,      0,      0,  1, 0,                 0, 0,        0, 0, 0, 1, 0, 0, 0,    0,        0,        0,        0,        'Hira Snowdawn - Idle flight - Talk'),
(@HIRA * 100,   9, 2, 0,  0, 0, 100, 0,      0,      0,      0,      0, 18, 33554432,          0, 0,        0, 0, 0, 1, 0, 0, 0,    0,        0,        0,        0,        'Hira Snowdawn - Idle flight - Set not selectable'),
(@HIRA * 100,   9, 3, 0,  0, 0, 100, 0,      0,      0,      0,      0, 53, 1,             @HIRA, 0,        0, 0, 0, 1, 0, 0, 0,    0,        0,        0,        0,        'Hira Snowdawn - Idle flight - Start waypoint path'),
(@HIRA * 100+1, 9, 0, 0,  0, 0, 100, 0,      0,      0,      0,      0, 66, 0,                 0, 0,        0, 0, 0, 8, 0, 0, 0, 5815.272, 473.4902, 658.7961, 4.660029, 'Hira Snowdawn - Return - Restore orientation'),
(@HIRA * 100+1, 9, 1, 0,  0, 0, 100, 0,      0,      0,      0,      0, 19, 33554432,          0, 0,        0, 0, 0, 1, 0, 0, 0,    0,        0,        0,        0,        'Hira Snowdawn - Return - Remove not selectable');
