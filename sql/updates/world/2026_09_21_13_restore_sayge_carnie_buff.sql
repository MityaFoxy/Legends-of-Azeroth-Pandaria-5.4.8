-- Restore the hidden cooldown aura triggered by all eight of Sayge's fortunes.
-- Spell 23770 is server-side and therefore absent from the 5.4.8 client DBCs.
-- The values come from the last TrinityDB 4.3.4 definition of the spell, split
-- across the Spell, SpellMisc, and SpellEffect tables used by this core.

DELETE FROM `spelleffect_dbc`
WHERE `EffectSpellId` = 23770;

DELETE FROM `spell_dbc`
WHERE `Id` = 23770;

DELETE FROM `spellmisc_dbc`
WHERE `Id` = 204061;

INSERT INTO `spellmisc_dbc`
    (`Id`, `Attributes`, `AttributesEx`, `AttributesEx2`, `AttributesEx3`,
     `AttributesEx4`, `AttributesEx5`, `AttributesEx6`, `AttributesEx7`,
     `AttributesEx8`, `AttributesEx9`, `AttributesEx10`, `AttributesEx11`,
     `AttributesEx12`, `AttributesEx13`, `CastingTimeIndex`, `DurationIndex`,
     `RangeIndex`, `SchoolMask`, `Comment`)
VALUES
    (204061, 612368640, 268435592, 1, 1048576,
     4, 0, 0, 0,
     0, 0, 0, 0,
     0, 0, 1, 527,
     6, 1, 'Sayge''s Carnie Buff (spellid: 23770)');

INSERT INTO `spell_dbc`
    (`Id`, `SpellAuraOptionsId`, `SpellCastingRequirementsId`,
     `SpellCategoriesId`, `SpellClassOptionsId`, `SpellEquippedItemsId`,
     `SpellLevelsId`, `SpellTargetRestrictionsId`, `SpellInterruptsId`,
     `SpellMiscId`, `Comment`)
VALUES
    (23770, 0, 0,
     0, 0, 0,
     0, 0, 0,
     204061, 'Sayge''s Carnie Buff');

INSERT INTO `spelleffect_dbc`
    (`Id`, `Effect`, `EffectValueMultiplier`, `EffectApplyAuraName`,
     `EffectAplitude`, `EffectBasePoints`, `EffectBonusMultiplier`,
     `EffectDamageMultiplier`, `EffectChainTarget`, `EffectDieSides`,
     `EffectMechanic`, `EffectMiscValue`, `EffectMiscValueB`,
     `EffectRadiusIndex`, `EffectRadiusIndexMax`, `EffectRealPointsPerLevel`,
     `EffectSpellClassMaskA`, `EffectSpellClassMaskB`, `EffectSpellClassMaskC`,
     `EffectSpellClassMaskD`, `EffectTriggerSpell`, `EffectImplicitTargetA`,
     `EffectImplicitTargetB`, `EffectSpellId`, `EffectIndex`, `EffectAttributes`)
VALUES
    (500008, 6, 0, 4,
     0, 0, 0,
     1, 0, 0,
     0, 0, 0,
     0, 0, 0,
     0, 0, 0,
     0, 0, 25,
     0, 23770, 0, 0);

-- This LINK event has never had a parent action pointing to it. Casting 23770
-- directly would also duplicate the trigger built into every fortune spell.
DELETE FROM `smart_scripts`
WHERE `entryorguid` = 14822
  AND `source_type` = 0
  AND `id` = 14
  AND `event_type` = 61
  AND `action_type` = 11
  AND `action_param1` = 23770;
