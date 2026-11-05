-- Spell 30011 was a server-side slowing aura used by the Ancestral Spirit Wolf
-- during quest 9410, "A Spirit Guide". It is absent from the 5.4.8 client DBC,
-- although the SmartAI sequence and its waypoint path are still present. The
-- original script explicitly used it as a follow-movement prevention hack.
--
-- Its persistent duration, self target, and 50% movement reduction preserve the
-- wolf's walking pace while it guides the player to the Mag'har post.

DELETE FROM `spelleffect_dbc`
WHERE `EffectSpellId` = 30011;

DELETE FROM `spell_dbc`
WHERE `Id` = 30011;

DELETE FROM `spellmisc_dbc`
WHERE `Id` = 204062;

INSERT INTO `spellmisc_dbc`
    (`Id`, `Attributes`, `AttributesEx`, `AttributesEx2`, `AttributesEx3`,
     `AttributesEx4`, `AttributesEx5`, `AttributesEx6`, `AttributesEx7`,
     `AttributesEx8`, `AttributesEx9`, `AttributesEx10`, `AttributesEx11`,
     `AttributesEx12`, `AttributesEx13`, `CastingTimeIndex`, `DurationIndex`,
     `RangeIndex`, `SchoolMask`, `Comment`)
VALUES
    (204062, 384, 0, 0, 0,
     0, 0, 0, 0,
     0, 0, 0, 0,
     0, 0, 1, 21,
     2, 1, 'Quest - Ancestral Spirit Wolf Self Snare (spellid: 30011)');

INSERT INTO `spell_dbc`
    (`Id`, `SpellAuraOptionsId`, `SpellCastingRequirementsId`,
     `SpellCategoriesId`, `SpellClassOptionsId`, `SpellEquippedItemsId`,
     `SpellLevelsId`, `SpellTargetRestrictionsId`, `SpellInterruptsId`,
     `SpellMiscId`, `Comment`)
VALUES
    (30011, 0, 0,
     0, 0, 0,
     0, 0, 0,
     204062, 'Quest - Ancestral Spirit Wolf Self Snare');

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
    (500009, 6, 0, 33,
     0, -50, 0,
     1, 0, 0,
     0, 0, 0,
     0, 0, 0,
     0, 0, 0,
     0, 0, 1,
     0, 30011, 0, 0);
