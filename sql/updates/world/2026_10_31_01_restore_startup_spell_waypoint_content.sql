-- Restore startup spell/waypoint content without inventing missing data.
--
-- Evidence used for this migration:
--   * local 5.4.8 Spell/SpellEffect DBC files;
--   * the current creature, waypoint and creature_text relationships;
--   * SkyFire 5.4.8 full DB 26.002;
--   * the serverMOPPREMIUM MyISAM world database supplied for recovery;
--   * the MaNGOS Three legacy db_script_string data for old waypoint texts.
--
-- Custom BroadcastText rows intentionally contain only the source English text.
-- No koKR-only localization is imported.

CREATE TABLE IF NOT EXISTS `spell_scripts_startup_archive` LIKE `spell_scripts`;
CREATE TABLE IF NOT EXISTS `spell_script_names_startup_archive` LIKE `spell_script_names`;
CREATE TABLE IF NOT EXISTS `waypoint_scripts_startup_archive` LIKE `waypoint_scripts`;
CREATE TABLE IF NOT EXISTS `waypoint_data_startup_archive` LIKE `waypoint_data`;

START TRANSACTION;

-- Powder Round (130973) triggers 130994. Spell 130994 already has native
-- SPELL_EFFECT_KILL_CREDIT2 effects for 66200 (three effects) and 66203.
-- These two DB commands duplicate that native content and cannot run from
-- effect 0 because it is SPELL_EFFECT_TRIGGER_MISSILE (32), not DUMMY/SCRIPT.
INSERT INTO `spell_scripts_startup_archive`
SELECT s.*
FROM `spell_scripts` s
WHERE s.`id` = 130973 AND s.`effIndex` = 0 AND s.`delay` = 0
  AND s.`command` = 8 AND s.`datalong` IN (66200,66203)
  AND s.`datalong2` = 0 AND s.`dataint` = 0
  AND s.`x` = 0 AND s.`y` = 0 AND s.`z` = 0 AND s.`o` = 0
  AND NOT EXISTS (
      SELECT 1
      FROM `spell_scripts_startup_archive` a
      WHERE a.`id` = s.`id` AND a.`effIndex` = s.`effIndex`
        AND a.`delay` = s.`delay` AND a.`command` = s.`command`
        AND a.`datalong` = s.`datalong` AND a.`datalong2` = s.`datalong2`
        AND a.`dataint` = s.`dataint` AND a.`x` = s.`x`
        AND a.`y` = s.`y` AND a.`z` = s.`z` AND a.`o` = s.`o`
  );

DELETE FROM `spell_scripts`
WHERE `id` = 130973 AND `effIndex` = 0 AND `delay` = 0
  AND `command` = 8 AND `datalong` IN (66200,66203)
  AND `datalong2` = 0 AND `dataint` = 0
  AND `x` = 0 AND `y` = 0 AND `z` = 0 AND `o` = 0;

-- The three Remove Talent spells form one complete rank chain whose first
-- rank is 127650. A negative first-rank binding is the loader's native form
-- for applying one script to every rank.
INSERT IGNORE INTO `spell_script_names_startup_archive`
SELECT *
FROM `spell_script_names`
WHERE `spell_id` IN (113873,127649,127650)
  AND `ScriptName` = 'spell_common_unlearn_talent';

DELETE FROM `spell_script_names`
WHERE `spell_id` IN (113873,127649,127650)
  AND `ScriptName` = 'spell_common_unlearn_talent';

INSERT IGNORE INTO `spell_script_names` (`spell_id`,`ScriptName`)
VALUES (-127650,'spell_common_unlearn_talent');

-- Preserve every invalid talk row before either restoring or retiring it.
INSERT IGNORE INTO `waypoint_scripts_startup_archive`
SELECT *
FROM `waypoint_scripts`
WHERE `command` = 0 AND `dataint` = 0;

-- Restore the small set of legacy strings that has no equivalent ID in the
-- local 5.4.8 BroadcastText data. The original 2,000,000,xxx IDs are kept so
-- their provenance stays visible and cannot collide with client DBC IDs.
CREATE TEMPORARY TABLE `_tmp_startup_broadcast_text` (
    `ID` INT UNSIGNED NOT NULL,
    `Text` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    PRIMARY KEY (`ID`)
);

INSERT INTO `_tmp_startup_broadcast_text` (`ID`,`Text`) VALUES
    (2000000133,'Stormwind City is under reliable protection!'),
    (2000000134,'The enemy won`t pass!'),
    (2000000139,'Meal, drinks!'),
    (2000000142,'Ironforge is under reliable protection!'),
    (2000000143,'How can anyone live like this!?'),
    (2000000144,'This must be fixed!'),
    (2000000145,'This will never do..'),
    (2000000203,'I will do my best to take care of the children, Grandmother.'),
    (2000000204,'Well hand it overand let''s see what you got!'),
    (2000000221,'Approach, buy.'),
    (2000000223,'The back walls are completely blown out!'),
    (2000000224,'They call that a weld!..'),
    (2000000225,'This must be fixed..');

INSERT INTO `broadcast_text`
    (`ID`,`LanguageID`,`Text`,`Text1`,`EmoteID1`,`EmoteID2`,`EmoteID3`,
     `EmoteDelay1`,`EmoteDelay2`,`EmoteDelay3`,`SoundEntriesID`,`EmotesID`,
     `Flags`,`VerifiedBuild`)
SELECT t.`ID`,0,t.`Text`,'',0,0,0,0,0,0,0,0,1,0
FROM `_tmp_startup_broadcast_text` t
LEFT JOIN `broadcast_text` b ON b.`ID` = t.`ID`
WHERE b.`ID` IS NULL;

-- Map the 69 active talk commands to either their native 5.4.8 BroadcastText
-- row or to one of the source-backed legacy rows above. Matching the expected
-- text prevents an occupied/conflicting ID from being used silently.
CREATE TEMPORARY TABLE `_tmp_startup_waypoint_talk` (
    `guid` INT NOT NULL,
    `script_id` INT UNSIGNED NOT NULL,
    `text_id` INT UNSIGNED NOT NULL,
    `expected_text` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    PRIMARY KEY (`guid`)
);

INSERT INTO `_tmp_startup_waypoint_talk`
    (`guid`,`script_id`,`text_id`,`expected_text`) VALUES
    (1,1,2000000142,'Ironforge is under reliable protection!'),
    (2,24,10152,'Prizes!  Get your prizes right here!  Get over here and turn in your Darkmoon Prize Tickets for valuable prizes!'),
    (300,24,10149,'Tickets! Redeem your Darkmoon Prize Tickets here!  Wondrous and exotic prizes are waiting for you!'),
    (50,100,2000000134,'The enemy won`t pass!'),
    (51,101,2000000133,'Stormwind City is under reliable protection!'),
    (98,154,2000000134,'The enemy won`t pass!'),
    (99,156,4287,'Poor Dorius. If I ever get my hands on those Dark Irons, so help me...'),
    (140,212,2981,'I know you are there, rogue. Leave my home or join the others at the bottom of the world tree.'),
    (141,213,3001,'Filth! Filth everywhere! The forests must be cleansed!'),
    (142,214,2000000139,'Meal, drinks!'),
    (143,215,2000000139,'Meal, drinks!'),
    (144,216,2000000139,'Meal, drinks!'),
    (145,217,2000000139,'Meal, drinks!'),
    (146,218,2000000139,'Meal, drinks!'),
    (147,219,2000000139,'Meal, drinks!'),
    (148,220,2000000139,'Meal, drinks!'),
    (149,221,2000000139,'Meal, drinks!'),
    (150,222,2000000139,'Meal, drinks!'),
    (151,223,2000000139,'Meal, drinks!'),
    (152,224,2000000139,'Meal, drinks!'),
    (153,225,2000000139,'Meal, drinks!'),
    (154,226,2000000139,'Meal, drinks!'),
    (155,227,2000000139,'Meal, drinks!'),
    (156,228,2000000139,'Meal, drinks!'),
    (157,229,2000000139,'Meal, drinks!'),
    (158,230,2000000139,'Meal, drinks!'),
    (159,231,2000000139,'Meal, drinks!'),
    (343,214,2000000221,'Approach, buy.'),
    (344,215,2000000221,'Approach, buy.'),
    (345,216,2000000221,'Approach, buy.'),
    (346,217,2000000221,'Approach, buy.'),
    (347,218,2000000221,'Approach, buy.'),
    (348,219,2000000221,'Approach, buy.'),
    (349,220,2000000221,'Approach, buy.'),
    (350,221,2000000221,'Approach, buy.'),
    (351,222,2000000221,'Approach, buy.'),
    (352,223,2000000221,'Approach, buy.'),
    (353,224,2000000221,'Approach, buy.'),
    (354,225,2000000221,'Approach, buy.'),
    (355,226,2000000221,'Approach, buy.'),
    (356,227,2000000221,'Approach, buy.'),
    (357,228,2000000221,'Approach, buy.'),
    (358,229,2000000221,'Approach, buy.'),
    (359,230,2000000221,'Approach, buy.'),
    (360,231,2000000221,'Approach, buy.'),
    (160,232,2000000134,'The enemy won`t pass!'),
    (250,351,2000000204,'Well hand it overand let''s see what you got!'),
    (251,352,17056,'Great Gazlowe!'),
    (404,352,17060,'This data will be quite useful for Project Blue Book. Er, I mean, this will be great for my new look.  See if you can gather any more data.'),
    (252,354,23842,'I''ll never stop. Never...'),
    (253,426,18816,'Right.  We just busted our tails to haul all of this stuff up here, and you want to work more?'),
    (254,427,14565,'The wind speaks of our enemies'' movements, Ashyen.  The naga will attack again.'),
    (255,428,14567,'Very well.  When that decision is made, I will be ready.  Let us hope it won''t be too late.'),
    (256,443,19491,'Duck!'),
    (257,446,17035,'I have another reading from the nether.'),
    (258,460,15119,'Don''t go close to the lake! It''s haunted!'),
    (259,485,72213,'More work?'),
    (264,491,2000000203,'I will do my best to take care of the children, Grandmother.'),
    (265,499,2000000145,'This will never do..'),
    (405,499,2000000225,'This must be fixed..'),
    (266,500,2000000144,'This must be fixed!'),
    (406,500,2000000224,'They call that a weld!..'),
    (267,501,2000000143,'How can anyone live like this!?'),
    (407,501,2000000223,'The back walls are completely blown out!'),
    (272,537,10152,'Prizes!  Get your prizes right here!  Get over here and turn in your Darkmoon Prize Tickets for valuable prizes!'),
    (409,537,10149,'Tickets! Redeem your Darkmoon Prize Tickets here!  Wondrous and exotic prizes are waiting for you!'),
    (273,538,22216,'Ahh, my precious Ameenah! How wonderful to see you again.'),
    (274,539,22211,'Yer wearin down, princess. I can sense it!'),
    (275,540,22206,'Hmm, don''t mind if I do!');

UPDATE `waypoint_scripts` ws
JOIN `_tmp_startup_waypoint_talk` m
  ON m.`guid` = ws.`guid` AND m.`script_id` = ws.`id`
JOIN `broadcast_text` b
  ON b.`ID` = m.`text_id` AND BINARY b.`Text` = BINARY m.`expected_text`
SET ws.`dataint` = m.`text_id`
WHERE ws.`command` = 0 AND ws.`dataint` = 0;

-- The Hellmaw/Blackheart rows contain non-retail placeholder dialogue and the
-- encounters already use their correct creature_text/voice lines. The Caliph
-- rows contain unrelated pirate-harbor text. Retire only these exact invalid
-- talk rows, then clear an action only when no script command remains for it.
DELETE FROM `waypoint_scripts`
WHERE `command` = 0 AND `dataint` = 0
  AND `id` IN (332,333,334,335,336,337,567,568,569,570,571,572);

INSERT IGNORE INTO `waypoint_data_startup_archive`
SELECT wd.*
FROM `waypoint_data` wd
WHERE wd.`action` IN (332,333,334,335,336,337,567,568,569,570,571,572)
  AND NOT EXISTS (
      SELECT 1 FROM `waypoint_scripts` ws WHERE ws.`id` = wd.`action`
  );

UPDATE `waypoint_data` wd
SET wd.`action` = 0
WHERE wd.`action` IN (332,333,334,335,336,337,567,568,569,570,571,572)
  AND NOT EXISTS (
      SELECT 1 FROM `waypoint_scripts` ws WHERE ws.`id` = wd.`action`
  );

-- Scripts 57-95 belonged to pre-MoP Stormwind child routes. Scripts 147-153
-- belonged to Sognar Cliffbeard's superseded seven-point route. The local MoP
-- spawns no longer use those paths; SkyFire 5.4.8 also keeps children 1413-1415
-- stationary. Archive every command and delete only while no waypoint links it.
INSERT IGNORE INTO `waypoint_scripts_startup_archive`
SELECT ws.*
FROM `waypoint_scripts` ws
WHERE (ws.`id` BETWEEN 57 AND 95 OR ws.`id` BETWEEN 147 AND 153)
  AND NOT EXISTS (
      SELECT 1 FROM `waypoint_data` wd WHERE wd.`action` = ws.`id`
  );

DELETE ws
FROM `waypoint_scripts` ws
LEFT JOIN `waypoint_data` wd ON wd.`action` = ws.`id`
WHERE (ws.`id` BETWEEN 57 AND 95 OR ws.`id` BETWEEN 147 AND 153)
  AND wd.`id` IS NULL;

DROP TEMPORARY TABLE `_tmp_startup_waypoint_talk`;
DROP TEMPORARY TABLE `_tmp_startup_broadcast_text`;

COMMIT;
