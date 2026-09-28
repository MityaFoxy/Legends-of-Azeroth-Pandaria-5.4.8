-- Restore the legacy PvP vendors that returned in patch 5.2.
--
-- Build 18414 contains new entries for the six returning vendors, including
-- their season-specific inventories, models and equipment.  Their cached
-- creature_template rows, however, have no server-side vendor/repair flags,
-- and the world still spawns the pre-MoP entries at the same locations.
-- Promote the existing spawns to the 5.2 entries so no duplicate NPCs are
-- created and the older inventories remain available as historical data.

UPDATE `creature_template`
SET `subname` = CASE `entry`
        WHEN 69971 THEN 'Wrathful Gladiator'
        WHEN 69973 THEN 'Relentless Gladiator'
        WHEN 69974 THEN 'Ruthless Gladiator'
        WHEN 69975 THEN 'Cataclysmic Gladiator'
        WHEN 69977 THEN 'Ruthless Gladiator'
        WHEN 69978 THEN 'Cataclysmic Gladiator'
    END,
    `faction` = CASE `entry`
        WHEN 69971 THEN 35
        WHEN 69973 THEN 35
        WHEN 69974 THEN 123
        WHEN 69975 THEN 1078
        WHEN 69977 THEN 125
        WHEN 69978 THEN 125
    END,
    `npcflag` = 4224,
    `unit_flags` = CASE
        WHEN `entry` IN (69971, 69973) THEN 768
        ELSE 33536
    END
WHERE `entry` IN (69971, 69973, 69974, 69975, 69977, 69978);

-- Dalaran: Xazi Smolderpipe and Zom Bocom.
UPDATE `creature`
SET `id` = CASE `guid`
        WHEN 304331 THEN 69973
        WHEN 304332 THEN 69971
    END,
    `VerifiedBuild` = 18414
WHERE (`guid` = 304331 AND `id` = 54651)
   OR (`guid` = 304332 AND `id` = 54652);

-- Orgrimmar: Sergeant Thunderhorn and Blood Guard Zar'shi.
UPDATE `creature`
SET `id` = CASE `guid`
        WHEN 303253 THEN 69978
        WHEN 265773 THEN 69977
    END,
    `VerifiedBuild` = 18414
WHERE (`guid` = 303253 AND `id` = 54658)
   OR (`guid` = 265773 AND `id` = 54659);

-- Stormwind: Captain Dirgehammer and Knight-Lieutenant T'Maire Sydes.
UPDATE `creature`
SET `id` = CASE `guid`
        WHEN 303298 THEN 69975
        WHEN 188602 THEN 69974
    END,
    `VerifiedBuild` = 18414
WHERE (`guid` = 303298 AND `id` = 54661)
   OR (`guid` = 188602 AND `id` = 54662);
