-- Quest spells 32307 and 32314 have a temporary gameobject summon in EFFECT_0
-- and their target-dependent script handler in EFFECT_1. Their unit/dead-target
-- conditions therefore belong only to the second effect (bit 2), not to both.
-- Retain every condition row; correct only its effect mask.
UPDATE `conditions`
SET `SourceGroup` = 2
WHERE `SourceTypeOrReferenceId` = 13
  AND `SourceEntry` IN (32307, 32314)
  AND `SourceGroup` = 3;
