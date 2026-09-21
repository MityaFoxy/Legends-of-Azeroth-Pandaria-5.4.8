-- Emote 9 is not present in the 5.4.8 Emotes store. Clear only the invalid
-- presentation fields that are skipped by the quest loader.
UPDATE `quest_details`
SET `Emote3` = 0
WHERE `ID` = 1242 AND `Emote3` = 9;

UPDATE `quest_offer_reward`
SET `Emote2` = 0
WHERE `ID` IN (1242, 1244) AND `Emote2` = 9;

-- These quests are completed by SmartAI events or spells with
-- SPELL_EFFECT_QUEST_COMPLETE. Preserve all existing flags while enabling
-- the required exploration/event bit.
UPDATE `quest_template_addon`
SET `SpecialFlags` = `SpecialFlags` | 2
WHERE `ID` IN (14482, 25924, 30470, 32640, 32641);
