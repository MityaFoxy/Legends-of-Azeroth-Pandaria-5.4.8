-- Every relation below has a matching build-15595 area-trigger objective.
-- Preserve existing addon data and enable the server-side exploration/event
-- bit which prevents these quests from completing before that objective.
INSERT IGNORE INTO `quest_template_addon`
    (`ID`, `MaxLevel`, `AllowableClasses`, `SourceSpellID`, `PrevQuestID`,
     `NextQuestID`, `ExclusiveGroup`, `RewardMailTemplateID`,
     `RewardMailDelay`, `RequiredSkillID`, `RequiredSkillPoints`,
     `RequiredMinRepFaction`, `RequiredMaxRepFaction`,
     `RequiredMinRepValue`, `RequiredMaxRepValue`, `ProvidedItemCount`,
     `SpecialFlags`, `ScriptName`)
VALUES
    (29536, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ''),
    (29539, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '');

UPDATE `quest_template_addon`
SET `SpecialFlags` = `SpecialFlags` | 2
WHERE `ID` IN
    (869, 13564, 14066, 25621, 26512, 26930, 27007, 27152, 27610,
     29392, 29415, 29536, 29539);

-- Prison of Yogg-Saron uses the same effect-0 destination handoff as the
-- other Ulduar teleports.  Its imported effect index 2 does not exist.
DELETE FROM `spell_target_position`
WHERE `id` = 65042;

INSERT INTO `spell_target_position`
    (`id`, `effIndex`, `target_map`, `target_position_x`,
     `target_position_y`, `target_position_z`, `target_orientation`)
VALUES
    (65042, 0, 603, 1855.07, -11.4879, 334.559, 5.53269);

-- Keep the two Gilneas destinations restored by their zone implementation.
-- Their spell targets are corrected to TARGET_DEST_DB in SpellMgr.
-- Remove positions which cannot be consumed by their 5.4.8 spells:
-- 49986 already triggers correctly positioned spell 49988; Dreadflame uses
-- encounter-selected floor positions; the Wandering Isle balloon script
-- summons entry 55649 directly at the same coordinates.
DELETE FROM `spell_target_position`
WHERE `id` IN (49986, 100679, 105002);

-- These effects are absent from the 5.4.8 spell store.  Keep the valid
-- Prayer of Mending link (123262 -> 41637) and the live battleground disguise
-- spells (81744/81748); remove only the unloaded post-MoP/custom remnants.
DELETE FROM `spell_linked_spell`
WHERE (`spell_trigger` = 123262 AND `spell_effect` = 203754 AND `type` = 0)
   OR (`spell_trigger` = 200002 AND `spell_effect` = 200004 AND `type` = 0)
   OR (`spell_trigger` = 200003 AND `spell_effect` = 200005 AND `type` = 0);
