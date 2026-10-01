-- Restore the missing slave of the existing 10011 -> 136105 linked respawn.
-- MaNGOS Four creature.sql at 8b798ac6a6a51c0c00c7e20c0a864793eb53904c
-- preserves GUID 10011, entry 36808 and this exact position/orientation.
-- MoPDB 5.4.7 independently has the same spawn under GUID 201033;
-- AzerothCore has it under 247133. Do not import their different GUIDs.
-- Original 15 (four WotLK raid modes) maps to 120 in this MoP core,
-- matching the existing ICC boss and nearby spawn 114722.
START TRANSACTION;
INSERT INTO `creature`
    (`guid`, `id`, `map`, `spawnMask`, `phaseMask`, `modelid`, `equipment_id`,
     `position_x`, `position_y`, `position_z`, `orientation`, `spawntimesecs`,
     `wander_distance`, `curhealth`, `curmana`, `MovementType`, `VerifiedBuild`)
SELECT 10011, 36808, 631, 120, 1, 30357, 0,
       -587.632, 2189.23, 49.5599, 2.70526, 7200, 0, 404430, 0, 0, 0
WHERE NOT EXISTS (SELECT 1 FROM `creature` WHERE `guid` = 10011)
  AND NOT EXISTS (SELECT 1 FROM `creature` WHERE `id` = 36808 AND `map` = 631
      AND ABS(`position_x` + 587.632) < 1 AND ABS(`position_y` - 2189.23) < 1
      AND ABS(`position_z` - 49.5599) < 1)
  AND EXISTS (SELECT 1 FROM `linked_respawn`
      WHERE `guid` = 10011 AND `linkedGuid` = 136105 AND `linkType` = 0)
  AND EXISTS (SELECT 1 FROM `creature` WHERE `guid` = 136105
      AND `id` = 36855 AND `map` = 631 AND `spawnMask` = 120 AND `phaseMask` = 1)
  AND EXISTS (SELECT 1 FROM `creature` WHERE `guid` = 114722
      AND `id` = 36808 AND `map` = 631 AND `spawnMask` = 120 AND `phaseMask` = 1)
  AND EXISTS (SELECT 1 FROM `creature_template` WHERE `entry` = 36808)
  AND EXISTS (SELECT 1 FROM `creature_template_model`
      WHERE `CreatureID` = 36808 AND `CreatureDisplayID` = 30357);
COMMIT;
