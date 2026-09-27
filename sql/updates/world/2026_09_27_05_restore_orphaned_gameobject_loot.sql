-- Restore gameobject loot rows present in MaNGOS Four database
-- (Rel23_02_056_Items_Loot_pt16.sql) but missing from this world database.
-- The templates currently have no spawns, yet retaining their verified loot
-- preserves the content if they are spawned later and satisfies the template
-- integrity check without removing the templates or their loot IDs.

DELETE FROM `gameobject_loot_template`
WHERE `entry` IN (218197, 218577, 220196, 221776);

INSERT INTO `gameobject_loot_template`
    (`entry`, `item`, `ChanceOrQuestChance`, `lootmode`, `groupid`, `mincountOrRef`, `maxcount`)
VALUES
    (218197, 93962, 100.00, 'REGULAR', 0, 1, 1),
    (218577, 46109,  16.67, 'REGULAR', 0, 1, 1),
    (218577, 74857,   6.67, 'REGULAR', 0, 1, 1),
    (218577, 86545,   6.67, 'REGULAR', 0, 1, 1),
    (218577, 88496,   6.67, 'REGULAR', 0, 1, 1),
    (218577, 94935,  16.67, 'REGULAR', 0, 1, 1),
    (218577, 97981,  16.67, 'REGULAR', 0, 1, 1),
    (220196, 81205,  19.24, 'REGULAR', 0, 1, 6),
    (220196, 82011,   0.11, 'REGULAR', 0, 1, 1),
    (220196, 82121,   0.11, 'REGULAR', 0, 1, 1),
    (220196, 82126,   2.59, 'REGULAR', 0, 1, 1),
    (220196, 82157,   0.54, 'REGULAR', 0, 1, 1),
    (220196, 82208,   0.11, 'REGULAR', 0, 1, 1),
    (220196, 82285,   0.11, 'REGULAR', 0, 1, 1),
    (221776, 87282, -44.11, 'REGULAR', 0, 1, 1),
    (221776, 87389, -40.98, 'REGULAR', 0, 1, 1);
