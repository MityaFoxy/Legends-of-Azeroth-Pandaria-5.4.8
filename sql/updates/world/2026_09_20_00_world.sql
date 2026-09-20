DELETE FROM `creature_text` WHERE `CreatureID` IN (64160, 65574) AND `GroupID` = 0;

INSERT INTO `creature_text` (`CreatureID`, `GroupID`, `ID`, `Text`, `Type`, `Language`, `Probability`, `Emote`, `Duration`, `Sound`, `SoundType`, `BroadcastTextId`, `TextRange`, `comment`) VALUES
(64160, 0, 0, '', 12, 0, 100, 0, 0, 0, 0, 64160, 0, 'Frostflower - Say'),
(65574, 0, 0, '', 12, 0, 100, 0, 0, 0, 0, 65574, 0, 'Brad Rhodes - Say');
