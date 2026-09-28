-- Restore the spellclick definitions required to install these vehicle
-- accessories. For accessory installation the vehicle itself casts spell
-- 46598, matching the verified 5.4 database pattern for nested vehicles.
INSERT IGNORE INTO `npc_spellclick_spells`
    (`npc_entry`, `spell_id`, `cast_flags`, `user_type`)
VALUES
    (54499, 46598, 0, 0),
    (57464, 46598, 0, 0),
    (65476, 46598, 0, 0),
    (65477, 46598, 0, 0);

-- These references point to quests absent from the 5.4.8 quest data (and the
-- IDs are used by unrelated items in this client build). Preserve the
-- area-specific phase aura while removing only the invalid quest gate.
UPDATE `spell_area`
SET `quest_start` = 0
WHERE `spell` = 67789
  AND `area` IN (6484, 6519)
  AND `quest_start` IN (40328, 40329);

-- Burning Crusade heroic keys were retired before the 5.4.8 client. Keep the
-- level and instance access rows, clearing only obsolete key item references.
UPDATE `access_requirement`
SET `item` = 0,
    `item2` = 0
WHERE `difficulty` = 'DUNGEON_HEROIC'
  AND `mapId` IN (540, 542, 543)
  AND (`item` = 30637 OR `item2` = 30622);

UPDATE `access_requirement`
SET `item` = 0
WHERE `difficulty` = 'DUNGEON_HEROIC'
  AND `mapId` IN (545, 546, 547)
  AND `item` = 30623;

UPDATE `access_requirement`
SET `item` = 0
WHERE `difficulty` = 'DUNGEON_HEROIC'
  AND `mapId` IN (552, 553, 554)
  AND `item` = 30634;

UPDATE `access_requirement`
SET `item` = 0
WHERE `difficulty` = 'DUNGEON_HEROIC'
  AND `mapId` IN (555, 556, 557, 558)
  AND `item` = 30633;

UPDATE `access_requirement`
SET `item` = 0
WHERE `difficulty` = 'DUNGEON_HEROIC'
  AND `mapId` = 560
  AND `item` = 30635;
