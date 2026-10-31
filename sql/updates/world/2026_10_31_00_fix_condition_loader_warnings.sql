-- Repair condition rows rejected by the MoP condition loader. Keep unsupported
-- source rows recoverable rather than silently deleting them.

CREATE TABLE IF NOT EXISTS `conditions_invalid_reference_archive` LIKE `conditions`;

START TRANSACTION;

-- Spell 60535 selects nearby gameobjects in EFFECT_0. These rows contain
-- existing Lamp Post entries, but were imported as title conditions with a
-- zero title ID and a zero effect mask.
UPDATE `conditions` c
JOIN `gameobject_template` g ON g.`entry` = c.`ConditionValue2`
SET c.`SourceGroup` = 1,
    c.`ConditionTypeOrReference` = 31,
    c.`ConditionValue1` = 5
WHERE c.`SourceTypeOrReferenceId` = 13
  AND c.`SourceGroup` = 0
  AND c.`SourceEntry` = 60535
  AND c.`SourceId` = 0
  AND c.`ConditionTypeOrReference` = 18
  AND c.`ConditionTarget` = 0
  AND c.`ConditionValue1` = 0
  AND c.`ConditionValue3` = 0;

-- Retain only DBC effects that perform implicit object selection. The loader
-- already applies the same masks in memory after warning; persisting them
-- makes the database match the behavior that actually runs.
UPDATE `conditions`
SET `SourceGroup` = 1
WHERE `SourceTypeOrReferenceId` = 13
  AND `SourceGroup` = 3
  AND `SourceEntry` IN (74670, 78499, 126022);

UPDATE `conditions`
SET `SourceGroup` = 2
WHERE `SourceTypeOrReferenceId` = 13
  AND `SourceGroup` = 3
  AND `SourceEntry` = 89008;

UPDATE `conditions`
SET `SourceGroup` = 1
WHERE `SourceTypeOrReferenceId` = 13
  AND `SourceGroup` = 7
  AND `SourceEntry` IN (64558, 68355, 89892, 100342, 100344, 137967);

UPDATE `conditions`
SET `SourceGroup` = 3
WHERE `SourceTypeOrReferenceId` = 13
  AND `SourceGroup` = 7
  AND `SourceEntry` = 100345;

-- These conditions cannot become active with the current source data:
-- 60430 and 75886 refer to absent creature templates, while 136909 EFFECT_0
-- has no implicit object target. Archive only the exact rejected rows.
INSERT IGNORE INTO `conditions_invalid_reference_archive`
SELECT * FROM `conditions`
WHERE (`SourceTypeOrReferenceId`, `SourceGroup`, `SourceEntry`, `SourceId`,
       `ElseGroup`, `ConditionTypeOrReference`, `ConditionTarget`,
       `ConditionValue1`, `ConditionValue2`, `ConditionValue3`) IN
      ((13, 7, 60430, 0, 1, 31, 0, 3, 31317, 0),
       (13, 1, 75886, 0, 0, 31, 0, 3, 40684, 0),
       (13, 1, 136909, 0, 0, 31, 0, 3, 69241, 0));

DELETE live FROM `conditions` live
JOIN `conditions_invalid_reference_archive` archived USING
 (`SourceTypeOrReferenceId`, `SourceGroup`, `SourceEntry`, `SourceId`,
  `ElseGroup`, `ConditionTypeOrReference`, `ConditionTarget`,
  `ConditionValue1`, `ConditionValue2`, `ConditionValue3`)
WHERE (live.`SourceTypeOrReferenceId`, live.`SourceGroup`, live.`SourceEntry`, live.`SourceId`,
       live.`ElseGroup`, live.`ConditionTypeOrReference`, live.`ConditionTarget`,
       live.`ConditionValue1`, live.`ConditionValue2`, live.`ConditionValue3`) IN
      ((13, 7, 60430, 0, 1, 31, 0, 3, 31317, 0),
       (13, 1, 75886, 0, 0, 31, 0, 3, 40684, 0),
       (13, 1, 136909, 0, 0, 31, 0, 3, 69241, 0));

COMMIT;
