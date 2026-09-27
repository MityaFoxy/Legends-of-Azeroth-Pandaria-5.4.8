-- Clear invalid optional linked-trap references reported by ObjectMgr.
--
-- GAMEOBJECT_TYPE_SPELL_FOCUS data2 and GAMEOBJECT_TYPE_GOOBER data12 are
-- linkedTrapId fields. The referenced templates 4 and 129 are type-0 objects
-- with no trap spell/data, so GameObject::TriggeringLinkedGameObject already
-- rejects them. Keeping the links only produces startup errors; it cannot
-- activate any gameplay effect.
--
-- Preserve the actual object functions: spell-focus ids stay unchanged and
-- Naxxramas portals retain their goober spell 28444 in data10.

UPDATE `gameobject_template`
SET `data2` = 0
WHERE `type` = 8
  AND `entry` IN (126337, 126338, 126339, 126340, 126341, 126342, 126345)
  AND `data2` = 4;

UPDATE `gameobject_template`
SET `data12` = 0
WHERE `type` = 10
  AND `entry` IN (181168, 181169)
  AND `data12` = 4;

UPDATE `gameobject_template`
SET `data12` = 0
WHERE `type` = 10
  AND `entry` IN (181575, 181576, 181577, 181578)
  AND `data12` = 129;
