-- data2 for GAMEOBJECT_TYPE_SPELL_FOCUS and data12 for GAMEOBJECT_TYPE_GOOBER
-- are linkedTrapId fields. These entries contain legacy references to non-trap
-- templates (4 and 129), which produces startup errors and cannot be triggered.
UPDATE `gameobject_template`
SET `data2` = 0
WHERE `entry` IN (126337, 126338, 126339, 126340, 126341, 126342, 126345)
  AND `data2` = 4;

UPDATE `gameobject_template`
SET `data12` = 0
WHERE `entry` IN (181168, 181169)
  AND `data12` = 4;

UPDATE `gameobject_template`
SET `data12` = 0
WHERE `entry` IN (181575, 181576, 181577, 181578)
  AND `data12` = 129;
