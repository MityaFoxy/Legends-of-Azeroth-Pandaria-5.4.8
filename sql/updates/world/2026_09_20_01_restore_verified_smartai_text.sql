-- Restore SmartAI dialogue only where it is verified against the local MoP
-- broadcast_text data or an independently published original-era script.

-- Quest 25283, "Prepping the Speech": each of these three NPCs has one
-- reaction line in the local MoP data.  The imported WotLK chain referred to
-- non-existent groups 2-7 instead of these existing groups.
UPDATE `smart_scripts` SET `action_param1` = 0
WHERE (`entryorguid`, `source_type`, `id`) IN ((1268, 0, 0), (6119, 0, 0));

DELETE FROM `smart_scripts`
WHERE (`entryorguid`, `source_type`, `id`) IN (
    (1268, 0, 1), (1268, 0, 2), (1268, 0, 3),
    (6119, 0, 1), (6119, 0, 2), (6119, 0, 3),
    (7955, 0, 1), (7955, 0, 2)
);

-- Flik's three OOC lines are present in the archived project database and
-- reference existing MoP broadcast text records.
DELETE FROM `creature_text` WHERE `CreatureID` = 14860 AND `GroupID` = 1;
INSERT INTO `creature_text` (`CreatureID`, `GroupID`, `ID`, `Text`, `Type`, `Language`, `Probability`, `Emote`, `Duration`, `Sound`, `SoundType`, `BroadcastTextId`, `TextRange`, `comment`) VALUES
(14860, 1, 0, 'Get back here!', 12, 0, 100, 0, 0, 0, 0, 10147, 0, 'Flik'),
(14860, 1, 1, 'Hey, someone help me catch this thing!', 12, 0, 100, 0, 0, 0, 0, 10145, 0, 'Flik'),
(14860, 1, 2, 'It\'s getting away!', 12, 0, 100, 0, 0, 0, 0, 10146, 0, 'Flik');

-- Gordok Brew Barker: both temporary spawns use creature template 23685.
-- The verified event script supplies three random lines in group 0; group 1
-- was an invalid WotLK import and has no matching text record.
DELETE FROM `creature_text` WHERE `CreatureID` = 23685 AND `GroupID` = 0;
INSERT INTO `creature_text` (`CreatureID`, `GroupID`, `ID`, `Text`, `Type`, `Language`, `Probability`, `Emote`, `Duration`, `Sound`, `SoundType`, `BroadcastTextId`, `TextRange`, `comment`) VALUES
(23685, 0, 0, 'YOU TRY DA\' BEST, NOW TRY DA\' REST! OGRE BREW!', 14, 0, 100, 1, 0, 0, 0, 0, 0, 'Gordok Brew Barker'),
(23685, 0, 1, 'HEY YOU! DRINK OGRE BREWS! MAKE YOU BIG AND STRONG!', 14, 0, 100, 1, 0, 0, 0, 0, 0, 'Gordok Brew Barker'),
(23685, 0, 2, 'YOU WANT DRINK? WE GOT DRINK!', 14, 0, 100, 1, 0, 0, 0, 0, 0, 'Gordok Brew Barker');

UPDATE `smart_scripts` SET `action_param1` = 0
WHERE (`entryorguid`, `source_type`, `id`) IN ((-84709, 0, 4), (-84635, 0, 4));
