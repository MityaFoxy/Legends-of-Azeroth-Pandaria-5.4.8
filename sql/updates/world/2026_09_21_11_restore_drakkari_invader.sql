-- Restore the third Drakkari Invader variant used by Trollgore's encounter.
-- Its SmartAI movement sequence is already present in smart_scripts and its
-- flight capabilities are already present in creature_template_movement.

DELETE FROM `creature_template` WHERE `entry` = 27754;
INSERT INTO `creature_template` (
    `entry`, `name`, `minlevel`, `maxlevel`, `exp`, `faction`,
    `speed_walk`, `speed_run`, `scale`, `BaseAttackTime`, `RangeAttackTime`,
    `unit_class`, `unit_flags`, `unit_flags2`, `type`, `AIName`,
    `HoverHeight`, `Health_mod`, `Mana_mod`, `Mana_mod_extra`, `Armor_mod`,
    `RegenHealth`, `flags_extra`, `ScriptName`, `VerifiedBuild`
) VALUES (
    27754, 'Drakkari Invader', 74, 75, 2, 1693,
    1, 1, 1, 2000, 2000,
    1, 768, 2048, 7, 'SmartAI',
    1, 0.188058, 0.5, 1, 1,
    1, 64, '', 15595
);

DELETE FROM `creature_template_model` WHERE `CreatureID` = 27754;
INSERT INTO `creature_template_model`
    (`CreatureID`, `Idx`, `CreatureDisplayID`, `DisplayScale`, `Probability`, `VerifiedBuild`)
VALUES
    (27754, 0, 27079, 1, 1, 15595),
    (27754, 1, 27080, 1, 1, 15595),
    (27754, 2, 27081, 1, 1, 15595);

DELETE FROM `creature_equip_template` WHERE `CreatureID` = 27754;
INSERT INTO `creature_equip_template`
    (`CreatureID`, `ID`, `ItemID1`, `ItemID2`, `ItemID3`, `VerifiedBuild`)
VALUES
    (27754, 1, 14874, 0, 0, 0);

DELETE FROM `creature_template_addon` WHERE `entry` = 27754;
INSERT INTO `creature_template_addon`
    (`entry`, `path_id`, `mount`, `MountCreatureID`, `StandState`, `AnimTier`,
     `VisFlags`, `SheathState`, `PvPFlags`, `emote`, `aiAnimKit`,
     `movementAnimKit`, `meleeAnimKit`, `visibilityDistanceType`, `auras`)
VALUES
    (27754, 0, 26751, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 3, NULL);
