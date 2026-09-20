-- Fix SmartAI dialogue rows imported with obsolete creature spawn GUIDs.
--
-- The valid Drunken Brewfest Reveler script is already bound to -84667.
-- -84714 now refers to a Gordok Brew Chief, so its duplicate must not run.
DELETE FROM `smart_scripts`
WHERE `entryorguid` = -84714
  AND `source_type` = 0;

-- This event script belongs to the Horde Gordok Brew Barker.  GUID -84709
-- was reassigned to Driz Tumblequick; -84711 is the current Barker spawn.
UPDATE `smart_scripts`
SET `entryorguid` = -84711
WHERE `entryorguid` = -84709
  AND `source_type` = 0;

-- GUID 121192 is a Shoveltusk in the 5.4.8 world data, not the technical
-- ELM bunny described by this orphaned row.  It cannot produce valid text.
DELETE FROM `smart_scripts`
WHERE `entryorguid` = -121192
  AND `source_type` = 0
  AND `id` = 0;

-- This script changes the Necrolord into High Overlord Saurfang (25751).
-- Keep using the stored Saurfang target for the remaining dialogue actions;
-- the original self target has the stale source entry at validation time.
UPDATE `smart_scripts`
SET `target_type` = 12,
    `target_param1` = 1,
    `target_param2` = 0,
    `target_param3` = 0
WHERE `entryorguid` = 25730
  AND `source_type` = 0
  AND `id` IN (9, 10, 11, 15, 16, 23)
  AND `action_type` = 1;

-- Quest 29398: Fencing the Goods.  Fitch has three sequential gossip lines;
-- only the last one (BroadcastText 52640) survived the import.
INSERT INTO `creature_text`
    (`CreatureID`, `GroupID`, `ID`, `Text`, `Type`, `Language`, `Probability`, `Emote`, `Duration`, `Sound`, `SoundType`, `BroadcastTextId`, `TextRange`, `comment`)
VALUES
    (8719, 1, 0, 'Look, in my business, discretion is important. I shouldn''t be talking about this at all.', 12, 0, 100, 5, 0, 0, 0, 52638, 0, 'Auctioneer Fitch - Fencing the Goods'),
    (8719, 2, 0, 'The person you described was just here and he tried to persuade me to list a crateful of arcane objects.', 12, 0, 100, 5, 0, 0, 0, 52639, 0, 'Auctioneer Fitch - Fencing the Goods')
ON DUPLICATE KEY UPDATE
    `Text` = VALUES(`Text`),
    `Type` = VALUES(`Type`),
    `Language` = VALUES(`Language`),
    `Probability` = VALUES(`Probability`),
    `Emote` = VALUES(`Emote`),
    `Duration` = VALUES(`Duration`),
    `Sound` = VALUES(`Sound`),
    `SoundType` = VALUES(`SoundType`),
    `BroadcastTextId` = VALUES(`BroadcastTextId`),
    `TextRange` = VALUES(`TextRange`),
    `comment` = VALUES(`comment`);

-- These talk actions have no corresponding MoP text.  Some owners were
-- removed before MoP (Dustbelcher Lord and Meridith); the rest are stale
-- additions to otherwise valid combat or quest scripts.  Keep each actual
-- gameplay action and reconnect its link where the talk was its only bridge.
UPDATE `smart_scripts` SET `link` = 0
WHERE `entryorguid` = 15526 AND `source_type` = 0 AND `id` = 1;
DELETE FROM `smart_scripts`
WHERE `source_type` = 0 AND `action_type` = 1 AND `action_param1` = 0
    AND (`entryorguid`, `id`) IN ((2719, 0), (15324, 3), (15526, 2),
        (18938, 2), (30284, 5), (55488, 0));

-- Arzeth only has the four random ambient lines in group 0.  Group 1 was an
-- unreferenced imported link, not an additional retail line.
DELETE FROM `smart_scripts`
WHERE `entryorguid` = 19354 AND `source_type` = 0 AND `id` = 4;

-- Plagued Dragonflayer Rune-Caster: spell-hit progression is faction change
-- then credit.  Replace the missing optional talk by that next real action.
UPDATE `smart_scripts`
SET `action_type` = 2, `action_param1` = 1925, `action_param2` = 0,
    `action_param3` = 0, `action_param4` = 0, `action_param5` = 0,
    `action_param6` = 0, `target_type` = 1, `target_param1` = 0,
    `target_param2` = 0, `target_param3` = 0, `link` = 5,
    `comment` = 'Plagued Dragonflayer Rune-Caster - On Spellhit Plague Spray - Set Faction 1925'
WHERE `entryorguid` = 24198 AND `source_type` = 0 AND `id` = 3;
DELETE FROM `smart_scripts`
WHERE `entryorguid` = 24198 AND `source_type` = 0 AND `id` = 4;

-- North Wind has two verified dialogue groups.  Finish the event after the
-- second one instead of trying to play an absent third line.
UPDATE `smart_scripts` SET `link` = 9
WHERE `entryorguid` = 30474 AND `source_type` = 0 AND `id` = 7;
DELETE FROM `smart_scripts`
WHERE `entryorguid` = 30474 AND `source_type` = 0 AND `id` = 8;

-- Caimas enters combat with the quest player; no fourth aggro line exists.
-- Retain the required explicit attack start without fabricating a dialogue.
UPDATE `smart_scripts`
SET `action_type` = 49, `action_param1` = 0, `action_param2` = 0,
    `action_param3` = 0, `action_param4` = 0, `action_param5` = 0,
    `action_param6` = 0, `target_type` = 7, `target_param1` = 0,
    `target_param2` = 0, `target_param3` = 0, `link` = 0,
    `comment` = 'Caimas the Pit Master - On Aggro - Attack Start'
WHERE `entryorguid` = 46276 AND `source_type` = 0 AND `id` = 1;
DELETE FROM `smart_scripts`
WHERE `entryorguid` = 46276 AND `source_type` = 0 AND `id` = 2;

-- Ramkahen Prisoner only has its freedom line.  Preserve credit, state and
-- waypoint progression after it, without the two unsupported intermediary talks.
UPDATE `smart_scripts` SET `link` = 9
WHERE `entryorguid` = 46425 AND `source_type` = 0 AND `id` = 7;
UPDATE `smart_scripts` SET `link` = 12
WHERE `entryorguid` = 46425 AND `source_type` = 0 AND `id` = 10;
DELETE FROM `smart_scripts`
WHERE `entryorguid` = 46425 AND `source_type` = 0 AND `id` IN (8, 11);

-- Wugou's completion signal was incorrectly made dependent on an absent
-- spoken line.  Send the existing signal directly to Ji Firepaw.
UPDATE `smart_scripts`
SET `action_type` = 45, `action_param1` = 0, `action_param2` = 1,
    `action_param3` = 0, `action_param4` = 0, `action_param5` = 0,
    `action_param6` = 0, `target_type` = 19, `target_param1` = 55477,
    `target_param2` = 0, `target_param3` = 0, `link` = 0,
    `comment` = 'Wugou - On Data Set 0 1 - Set Data 0 1 on Ji Firepaw'
WHERE `entryorguid` = 57760 AND `source_type` = 0 AND `id` = 9;
DELETE FROM `smart_scripts`
WHERE `entryorguid` = 57760 AND `source_type` = 0 AND `id` = 10;

-- Inspector Tarem, not the now-unrelated entry 9079, comments on the clues.
UPDATE `smart_scripts`
SET `target_type` = 1,
    `target_param1` = 0,
    `target_param2` = 0,
    `target_param3` = 0
WHERE `entryorguid` = 23567
  AND `source_type` = 0
  AND `id` = 2
  AND `action_type` = 1
  AND `target_type` = 11
  AND `target_param1` = 9079;

-- These three templates share a ranged-combat/flee SmartAI.  Its copied
-- 15%-health TALK action has no source dialogue and did not exist in MoP.
DELETE FROM `smart_scripts`
WHERE `source_type` = 0
  AND `id` = 20
  AND `event_type` = 2
  AND `action_type` = 1
  AND `entryorguid` IN (46134, 46402, 48012);

-- Jade Forest: The White Pawn and Sufficient Motivation.
INSERT INTO `creature_text`
    (`CreatureID`, `GroupID`, `ID`, `Text`, `Type`, `Language`, `Probability`, `Emote`, `Duration`, `Sound`, `SoundType`, `BroadcastTextId`, `TextRange`, `comment`)
VALUES
    (54615, 2, 0, 'Alright, I think I know what our next move''s gotta be.', 12, 0, 100, 0, 0, 0, 0, 58269, 0, 'Nodd Codejack - The White Pawn'),
    (59296, 0, 0, 'Ookin'' dooker!', 12, 0, 100, 0, 0, 0, 0, 58275, 0, 'Lazy Hozen - Sufficient Motivation'),
    (59296, 0, 1, 'Wikkets is furry food!', 12, 0, 100, 0, 0, 0, 0, 58271, 0, 'Lazy Hozen - Sufficient Motivation'),
    (59296, 0, 2, 'Wikket grookin stinky slickies!', 12, 0, 100, 0, 0, 0, 0, 58272, 0, 'Lazy Hozen - Sufficient Motivation'),
    (59296, 0, 3, 'Hozen whakkin'' stinky wikket!', 12, 0, 100, 0, 0, 0, 0, 58273, 0, 'Lazy Hozen - Sufficient Motivation'),
    (59296, 0, 4, 'Grookie wikket!', 12, 0, 100, 0, 0, 0, 0, 58274, 0, 'Lazy Hozen - Sufficient Motivation')
ON DUPLICATE KEY UPDATE
    `Text` = VALUES(`Text`),
    `Type` = VALUES(`Type`),
    `Language` = VALUES(`Language`),
    `Probability` = VALUES(`Probability`),
    `Emote` = VALUES(`Emote`),
    `Duration` = VALUES(`Duration`),
    `Sound` = VALUES(`Sound`),
    `SoundType` = VALUES(`SoundType`),
    `BroadcastTextId` = VALUES(`BroadcastTextId`),
    `TextRange` = VALUES(`TextRange`),
    `comment` = VALUES(`comment`);

INSERT INTO `creature_text`
    (`CreatureID`, `GroupID`, `ID`, `Text`, `Type`, `Language`, `Probability`, `Emote`, `Duration`, `Sound`, `SoundType`, `BroadcastTextId`, `TextRange`, `comment`)
VALUES
    (23567, 0, 0, 'Mysterious hoofprints, scorched shields, stray badges... how do we make sense of all this?', 12, 0, 100, 0, 0, 0, 0, 22038, 0, 'Inspector Tarem - Shady Rest Inn'),
    (23669, 0, 0, 'For Ymiron!', 14, 0, 100, 0, 0, 0, 0, 22813, 0, 'Winterskorn Oracle - Combat'),
    (23669, 0, 1, 'YAAARRRGH!', 14, 0, 100, 0, 0, 0, 0, 22814, 0, 'Winterskorn Oracle - Combat'),
    (23669, 0, 2, 'My life for Ymiron!', 14, 0, 100, 0, 0, 0, 0, 22815, 0, 'Winterskorn Oracle - Combat'),
    (23669, 0, 3, 'You tiny creatures disgust me!', 14, 0, 100, 0, 0, 0, 0, 22816, 0, 'Winterskorn Oracle - Combat'),
    (23669, 0, 4, 'Look what''s come to play.', 14, 0, 100, 0, 0, 0, 0, 22820, 0, 'Winterskorn Oracle - Combat'),
    (23669, 0, 5, 'There will be no everlasting life for you!', 14, 0, 100, 0, 0, 0, 0, 22822, 0, 'Winterskorn Oracle - Combat'),
    (23669, 0, 6, 'Your race is a disease upon the world!', 14, 0, 100, 0, 0, 0, 0, 22824, 0, 'Winterskorn Oracle - Combat'),
    (23669, 0, 7, 'I''ll eat your heart!', 14, 0, 100, 0, 0, 0, 0, 30508, 0, 'Winterskorn Oracle - Combat')
ON DUPLICATE KEY UPDATE
    `Text` = VALUES(`Text`),
    `Type` = VALUES(`Type`),
    `Language` = VALUES(`Language`),
    `Probability` = VALUES(`Probability`),
    `Emote` = VALUES(`Emote`),
    `Duration` = VALUES(`Duration`),
    `Sound` = VALUES(`Sound`),
    `SoundType` = VALUES(`SoundType`),
    `BroadcastTextId` = VALUES(`BroadcastTextId`),
    `TextRange` = VALUES(`TextRange`),
    `comment` = VALUES(`comment`);

-- Classic dungeon dialogue restored from the historical creature AI dataset.
-- Entry 9079 was reassigned; Thal'trak's nearby speaker is Grunt Gargal 9086.
UPDATE `smart_scripts`
SET `target_param1` = 9086
WHERE `entryorguid` = 9082
  AND `source_type` = 0
  AND `id` = 0
  AND `action_type` = 1
  AND `target_type` = 11
  AND `target_param1` = 9079;

INSERT INTO `creature_text`
    (`CreatureID`, `GroupID`, `ID`, `Text`, `Type`, `Language`, `Probability`, `Emote`, `Duration`, `Sound`, `SoundType`, `BroadcastTextId`, `TextRange`, `comment`)
VALUES
    (9086, 0, 0, 'Well done, soldiers! At ease!', 12, 0, 100, 0, 0, 0, 0, 4692, 0, 'Grunt Gargal - Kargath Expeditionary Force'),
    (13601, 0, 0, 'Mine! Mine! Mine! Gizlock is the ruler of this domain! You shall never reveal my presence!', 12, 0, 100, 0, 0, 0, 0, 0, 0, 'Tinkerer Gizlock - Aggro')
ON DUPLICATE KEY UPDATE
    `Text` = VALUES(`Text`),
    `Type` = VALUES(`Type`),
    `Language` = VALUES(`Language`),
    `Probability` = VALUES(`Probability`),
    `Emote` = VALUES(`Emote`),
    `Duration` = VALUES(`Duration`),
    `Sound` = VALUES(`Sound`),
    `SoundType` = VALUES(`SoundType`),
    `BroadcastTextId` = VALUES(`BroadcastTextId`),
    `TextRange` = VALUES(`TextRange`),
    `comment` = VALUES(`comment`);

-- Verified dialogue for Cataclysm and MoP quest scenarios.
INSERT INTO `creature_text`
    (`CreatureID`, `GroupID`, `ID`, `Text`, `Type`, `Language`, `Probability`, `Emote`, `Duration`, `Sound`, `SoundType`, `BroadcastTextId`, `TextRange`, `comment`)
VALUES
    (45152, 0, 0, 'You''ll pay with your life for interfering with my plans, you miserable scum!', 14, 0, 100, 0, 0, 0, 0, 45301, 0, 'Magus Bisp - Bagging Bisp'),
    (66693, 0, 0, 'Work harder you lazy mongrels, or I''ll roast you alive!', 14, 0, 100, 0, 0, 0, 0, 67810, 0, 'Zandalari Overlord - Ambient'),
    (66693, 0, 1, 'Break any of these supplies, and I''ll break your skull!', 14, 0, 100, 0, 0, 0, 0, 67811, 0, 'Zandalari Overlord - Ambient'),
    (66693, 0, 2, 'Guard these supplies with your lives, you filthy mutts!', 14, 0, 100, 0, 0, 0, 0, 67812, 0, 'Zandalari Overlord - Ambient'),
    (66693, 0, 3, 'Keep your flea ridden paws out of the food, you mangy beasts!', 14, 0, 100, 0, 0, 0, 0, 67813, 0, 'Zandalari Overlord - Ambient'),
    (66693, 0, 4, 'Watch these mercenaries closely, brothers!', 14, 0, 100, 0, 0, 0, 0, 67814, 0, 'Zandalari Overlord - Ambient'),
    (69267, 0, 0, 'Thank you, friend. You have rescued me from a terrible fate.', 12, 0, 100, 0, 0, 0, 0, 71507, 0, 'Silver Covenant Scout - Soul Surrender'),
    (69267, 0, 1, 'Thank you, champion. Please, free the others as well!', 12, 0, 100, 0, 0, 0, 0, 71510, 0, 'Silver Covenant Scout - Soul Surrender'),
    (69267, 0, 2, 'How could the mogu be capable of such atrocity? Thank goodness you arrived when you did.', 12, 0, 100, 0, 0, 0, 0, 71511, 0, 'Silver Covenant Scout - Soul Surrender'),
    (69267, 0, 3, 'You have saved my life, champion. For that, I am in your debt.', 12, 0, 100, 0, 0, 0, 0, 71513, 0, 'Silver Covenant Scout - Soul Surrender'),
    (69267, 0, 4, 'Did the Silver Covenant send you? Thank you for the well-timed rescue.', 12, 0, 100, 0, 0, 0, 0, 71514, 0, 'Silver Covenant Scout - Soul Surrender'),
    (69267, 0, 5, 'I knew the Silver Covenant would not desert me. Thank you, champion.', 12, 0, 100, 0, 0, 0, 0, 71515, 0, 'Silver Covenant Scout - Soul Surrender'),
    (69305, 0, 0, 'I should tear you apart, Alliance scum! I will restrain myself this once.', 12, 0, 100, 0, 0, 0, 0, 71517, 0, 'Sunreaver Scout - Soul Surrender'),
    (69305, 0, 1, 'I will stay my hand this time, Alliance hero. Let it not be said that the Sunreavers do not show gratitude.', 12, 0, 100, 0, 0, 0, 0, 71518, 0, 'Sunreaver Scout - Soul Surrender'),
    (69305, 0, 2, 'If you had not just rescued me from certain death, I would kill you where you stand. Next time we meet, I will not hold back.', 12, 0, 100, 0, 0, 0, 0, 71519, 0, 'Sunreaver Scout - Soul Surrender'),
    (69305, 0, 3, 'Although we are enemies, I will thank you. Just this once.', 12, 0, 100, 0, 0, 0, 0, 71520, 0, 'Sunreaver Scout - Soul Surrender'),
    (69305, 0, 4, 'Thank you, Alliance hero, but next time we meet, I will show no mercy.', 12, 0, 100, 0, 0, 0, 0, 71521, 0, 'Sunreaver Scout - Soul Surrender')
ON DUPLICATE KEY UPDATE
    `Text` = VALUES(`Text`),
    `Type` = VALUES(`Type`),
    `Language` = VALUES(`Language`),
    `Probability` = VALUES(`Probability`),
    `Emote` = VALUES(`Emote`),
    `Duration` = VALUES(`Duration`),
    `Sound` = VALUES(`Sound`),
    `SoundType` = VALUES(`SoundType`),
    `BroadcastTextId` = VALUES(`BroadcastTextId`),
    `TextRange` = VALUES(`TextRange`),
    `comment` = VALUES(`comment`);

-- Jade Forest training and delivery quests (patch 5.0.4).
INSERT INTO `creature_text`
    (`CreatureID`, `GroupID`, `ID`, `Text`, `Type`, `Language`, `Probability`, `Emote`, `Duration`, `Sound`, `SoundType`, `BroadcastTextId`, `TextRange`, `comment`)
VALUES
    (54924, 1, 0, 'Alright, enough, enough! STOP HITTING ZHI-ZHI!', 12, 0, 100, 0, 0, 0, 0, 53204, 0, 'Zhi-Zhi - Defeat'),
    (54944, 1, 0, 'Nice moves!', 12, 0, 100, 0, 0, 0, 0, 53238, 0, 'Tian Pupil - Defeat'),
    (54944, 1, 1, 'Man... I thought I had that one...', 12, 0, 100, 0, 0, 0, 0, 53239, 0, 'Tian Pupil - Defeat'),
    (54944, 1, 2, 'Good fight. I''ll get you next time.', 12, 0, 100, 0, 0, 0, 0, 53240, 0, 'Tian Pupil - Defeat'),
    (54944, 1, 3, 'Master Stone Fist was right about you. You''re good.', 12, 0, 100, 0, 0, 0, 0, 53241, 0, 'Tian Pupil - Defeat'),
    (54944, 1, 4, 'Thank you for the opportunity of getting beaten up by you.', 12, 0, 100, 0, 0, 0, 0, 53242, 0, 'Tian Pupil - Defeat'),
    (54944, 1, 5, 'You take this pretty seriously, don''t you?', 12, 0, 100, 0, 0, 0, 0, 53243, 0, 'Tian Pupil - Defeat'),
    (54944, 1, 6, 'Good fight.', 12, 0, 100, 0, 0, 0, 0, 53244, 0, 'Tian Pupil - Defeat'),
    (54944, 1, 7, 'I don''t think I ever stood a chance. See you around, then!', 12, 0, 100, 0, 0, 0, 0, 53246, 0, 'Tian Pupil - Defeat'),
    (59392, 0, 0, 'It''s about time we got another shipment. I heard they were having trouble at the mines, but our work cannot wait.', 12, 0, 100, 0, 0, 0, 0, 58451, 0, 'Kitemaster Shoku - Love''s Labor')
ON DUPLICATE KEY UPDATE
    `Text` = VALUES(`Text`),
    `Type` = VALUES(`Type`),
    `Language` = VALUES(`Language`),
    `Probability` = VALUES(`Probability`),
    `Emote` = VALUES(`Emote`),
    `Duration` = VALUES(`Duration`),
    `Sound` = VALUES(`Sound`),
    `SoundType` = VALUES(`SoundType`),
    `BroadcastTextId` = VALUES(`BroadcastTextId`),
    `TextRange` = VALUES(`TextRange`),
    `comment` = VALUES(`comment`);

-- Quest 30798: Breaking the Emperor's Shield.  Nakk'rakas yells at each
-- encounter transition; the five matching MoP BroadcastText records exist.
INSERT INTO `creature_text`
    (`CreatureID`, `GroupID`, `ID`, `Text`, `Type`, `Language`, `Probability`, `Emote`, `Duration`, `Sound`, `SoundType`, `BroadcastTextId`, `TextRange`, `comment`)
VALUES
    (60572, 0, 0, 'You can''t stop what has begun!', 14, 0, 100, 0, 0, 0, 0, 61229, 0, 'Nakk''rakas - Aggro'),
    (60572, 1, 0, 'Da Thunder King will return!', 14, 0, 100, 0, 0, 0, 0, 61232, 0, 'Nakk''rakas - Imperial Guard killed'),
    (60572, 2, 0, 'These guardians are just da beginning!', 14, 0, 100, 0, 0, 0, 0, 61230, 0, 'Nakk''rakas - Imperial Guard killed'),
    (60572, 3, 0, 'Enough! I''ll handle you myself!', 14, 0, 100, 0, 0, 0, 0, 61269, 0, 'Nakk''rakas - Final Imperial Guard killed'),
    (60572, 4, 0, 'My death will not stop da storm that is coming! Da Thunder King will rise!', 14, 0, 100, 0, 0, 0, 0, 60775, 0, 'Nakk''rakas - Death')
ON DUPLICATE KEY UPDATE
    `Text` = VALUES(`Text`),
    `Type` = VALUES(`Type`),
    `Language` = VALUES(`Language`),
    `Probability` = VALUES(`Probability`),
    `Emote` = VALUES(`Emote`),
    `Duration` = VALUES(`Duration`),
    `Sound` = VALUES(`Sound`),
    `SoundType` = VALUES(`SoundType`),
    `BroadcastTextId` = VALUES(`BroadcastTextId`),
    `TextRange` = VALUES(`TextRange`),
    `comment` = VALUES(`comment`);
