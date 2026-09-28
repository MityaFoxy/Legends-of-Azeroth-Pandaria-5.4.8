-- Restore the 5.4.8 target conditions for Freya's Lifebinder's Gift and
-- Kologarn's 25-player Arm Dead Damage.
--
-- The imported condition set mixed obsolete heroic-template IDs into the
-- current unified-difficulty creature layout.  Three of those IDs now belong
-- to unrelated PvP vendors, two no longer have templates, and several
-- mutually exclusive creature entries were placed in the same ElseGroup.
-- Replace only these three damaged spell clusters with the exact SkyFire
-- 5.4.8 alternatives.  All seven intended Freya targets remain available in
-- both raid sizes and Kologarn remains the sole target of his arm damage.

DELETE FROM `conditions`
WHERE `SourceTypeOrReferenceId` = 13
  AND `SourceEntry` IN (62584, 63979, 64185);

INSERT INTO `conditions`
    (`SourceTypeOrReferenceId`, `SourceGroup`, `SourceEntry`, `SourceId`,
     `ElseGroup`, `ConditionTypeOrReference`, `ConditionTarget`,
     `ConditionValue1`, `ConditionValue2`, `ConditionValue3`,
     `NegativeCondition`, `ErrorType`, `ErrorTextId`, `ScriptName`, `Comment`)
VALUES
    (13, 7, 62584, 0, 0, 31, 0, 3, 32906, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift'),
    (13, 7, 62584, 0, 1, 31, 0, 3, 32916, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift'),
    (13, 7, 62584, 0, 2, 31, 0, 3, 32918, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift'),
    (13, 7, 62584, 0, 3, 31, 0, 3, 32919, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift'),
    (13, 7, 62584, 0, 4, 31, 0, 3, 33202, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift'),
    (13, 7, 62584, 0, 5, 31, 0, 3, 33203, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift'),
    (13, 7, 62584, 0, 6, 31, 0, 3, 33215, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift'),
    (13, 1, 63979, 0, 0, 31, 0, 3, 32930, 0, 0, 0, 0, '', 'Arm Dead Damage Kologarn (25m) Target'),
    (13, 7, 64185, 0, 0, 31, 0, 3, 32906, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift'),
    (13, 7, 64185, 0, 1, 31, 0, 3, 32916, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift'),
    (13, 7, 64185, 0, 2, 31, 0, 3, 32918, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift'),
    (13, 7, 64185, 0, 3, 31, 0, 3, 32919, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift'),
    (13, 7, 64185, 0, 4, 31, 0, 3, 33202, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift'),
    (13, 7, 64185, 0, 5, 31, 0, 3, 33203, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift'),
    (13, 7, 64185, 0, 6, 31, 0, 3, 33215, 0, 0, 0, 0, '', 'target for Lifebinder\'s Gift');
