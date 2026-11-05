-- Restore I Need a Champion (32592), not merely its questgiver references.
-- Objective: SkyFire 5.4.8, 2014_09_04_02_world_quest_objective.sql.
-- Template: TrinityCore, 2014_12_29_00_world.sql (source build 19034).
-- MoP reward mapping: local 18414 quest 32591, QuestXP/QuestFactionReward.dbc,
-- and the original-era quest description. Do not import WoD bonus money.
-- Recovery approach also found in ingussuveiks-dev's 2026_07_17_00 update;
-- explicit columns avoid cloning unrelated/custom fields from a donor quest.
-- See doc/quest_32592_and_legacy_escorts_audit.md for evidence and limits.

START TRANSACTION;

-- Existing/custom versions of this quest are never overwritten. If the
-- template is missing, require the expected surrounding chain and no orphan
-- payload/colliding objective ID before inserting the complete definition.
SET @restore_wrathion_32592 := NOT EXISTS
    (SELECT 1 FROM `quest_template` WHERE `ID` = 32592);

CREATE TEMPORARY TABLE `_wrathion_32592_precondition` (`ok` TINYINT PRIMARY KEY);
INSERT INTO `_wrathion_32592_precondition` VALUES (1);
INSERT INTO `_wrathion_32592_precondition`
SELECT 1 WHERE @restore_wrathion_32592 AND NOT
    (EXISTS (SELECT 1 FROM `quest_template` WHERE `ID` = 32591
        AND `QuestLevel` = 90 AND `MinLevel` = 90 AND `QuestSortID` = -344
        AND `QuestInfoID` = 83 AND `RewardXPDifficulty` = 6
        AND `RewardMoney` = 228000 AND `RewardBonusMoney` = 247200
        AND `RewardFactionID1` = 1359 AND `RewardFactionValue1` = 5)
    AND EXISTS (SELECT 1 FROM `quest_template_addon` WHERE `ID` = 32591
        AND `PrevQuestID` = 32590 AND `NextQuestID` = 32593 AND `ExclusiveGroup` = -32591)
    AND EXISTS (SELECT 1 FROM `creature_queststarter` WHERE `id` = 69782 AND `quest` = 32592)
    AND EXISTS (SELECT 1 FROM `creature_questender` WHERE `id` = 69782 AND `quest` = 32592)
    AND NOT EXISTS (SELECT 1 FROM `quest_template_addon` WHERE `ID` = 32592)
    AND NOT EXISTS (SELECT 1 FROM `quest_objective` WHERE `questId` = 32592 OR `id` = 270242)
    AND NOT EXISTS (SELECT 1 FROM `quest_poi` WHERE `QuestID` = 32592)
    AND NOT EXISTS (SELECT 1 FROM `quest_poi_points` WHERE `QuestID` = 32592)
    AND NOT EXISTS (SELECT 1 FROM `quest_offer_reward` WHERE `ID` = 32592)
    AND NOT EXISTS (SELECT 1 FROM `quest_request_items` WHERE `ID` = 32592));
DROP TEMPORARY TABLE `_wrathion_32592_precondition`;

INSERT INTO `quest_template`
    (`ID`, `QuestType`, `QuestLevel`, `MinLevel`, `QuestSortID`, `QuestInfoID`,
     `RewardXPDifficulty`, `RewardMoney`, `RewardBonusMoney`, `RewardSpell`,
     `Flags`, `FlagsEx`, `RewardFactionID1`, `RewardFactionValue1`,
     `AcceptedSoundKitID`, `CompleteSoundKitID`, `AllowableRaces`,
     `LogTitle`, `LogDescription`, `QuestDescription`, `AreaDescription`,
     `PortraitGiverText`, `PortraitGiverName`, `PortraitTurnInText`,
     `PortraitTurnInName`, `QuestCompletionLog`, `VerifiedBuild`)
SELECT 32592, 2, 90, 90, -344, 83, 6, 228000, 247200, 139524,
       45088768, 256, 1359, 5, 890, 878, 0,
       'I Need a Champion',
       'Earn Exalted Reputation with the Black Prince by defeating mogu, Zandalari, and saurok enemies on the Isle of Thunder.',
       'You are a superb representative of your people, $r. But I need someone special. I have big plans. And to enact them I will need a champion to carry my flame to the four corners of the world.$b$bAre you the one?$b$bProve it to me on the Isle of Thunder! Lay waste to any mogu, Zandalari, or saurok that you find. Impress me!',
       '', '', '', '', '',
       'Return to Wrathion on the second floor of the Tavern in the Mists in the Veiled Stair.',
       0 -- reconstructed from documented sources, not a newly captured 18414 sniff
WHERE @restore_wrathion_32592;

-- Negative ExclusiveGroup means BOTH parallel quests must be rewarded before
-- 32593 becomes available. Reputation is a completion objective, not an
-- acceptance requirement (RequiredMinRepFaction must remain zero).
INSERT INTO `quest_template_addon` (`ID`, `PrevQuestID`, `NextQuestID`, `ExclusiveGroup`)
SELECT 32592, 32590, 32593, -32591 WHERE @restore_wrathion_32592;

-- SkyFire's unsigned index 255 is signed -1 in this schema.
INSERT INTO `quest_objective`
    (`questId`, `id`, `index`, `type`, `objectId`, `amount`, `flags`, `description`)
SELECT 32592, 270242, -1, 6, 1359, 42000, 0,
       'Earn Exalted Reputation with the Black Prince'
WHERE @restore_wrathion_32592;

-- The same Wrathion turn-in position is already used by local quest 32591;
-- independently preserved for 32592 in TrinityCore's 2015_04_05_03_world.sql.
INSERT INTO `quest_poi`
    (`QuestID`, `Idx1`, `ObjectiveIndex`, `QuestObjectiveId`, `MapID`,
     `WorldMapAreaId`, `Floor`, `Priority`, `Flags`, `VerifiedBuild`)
SELECT 32592, 0, -1, 0, 870, 873, 0, 0, 0, 0 WHERE @restore_wrathion_32592;
INSERT INTO `quest_poi_points`
    (`QuestID`, `BlobIndex`, `Idx1`, `Idx2`, `X`, `Y`, `VerifiedBuild`)
SELECT 32592, 0, 0, 0, 832, -167, 0 WHERE @restore_wrathion_32592;

-- Historical quest dialogue; neutral emotes rather than invented animations.
INSERT INTO `quest_request_items` (`ID`, `CompletionText`, `VerifiedBuild`)
SELECT 32592, 'How goes the battle on the island?', 0 WHERE @restore_wrathion_32592;
INSERT INTO `quest_offer_reward` (`ID`, `RewardText`, `VerifiedBuild`)
SELECT 32592,
       'My Shado-Pan associates have spoken highly of your deeds. You have earned quite the name for yourself here in Pandaria!$B$BIt is settled. When the materials are ready, you will be my champion. You will be my instrument, my standard-bearer, my voice of change across this world.$B$BWe will do marvelous things together.',
       0 WHERE @restore_wrathion_32592;

COMMIT;
