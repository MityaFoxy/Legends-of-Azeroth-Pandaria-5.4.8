-- These IDs exist in Item.db2 but have no Item-sparse.db2 records, so the core
-- cannot synthesize templates for them. They are required by valid objectives.
-- Client display IDs are from build 18414; names and quest use are corroborated
-- by the original quest data. Do not overwrite rows supplied by a later import.
INSERT IGNORE INTO `item_template`
    (`entry`, `class`, `subclass`, `SoundOverrideSubclass`, `name`, `displayid`,
     `Quality`, `Flags`, `FlagsExtra`, `Flags3`, `BuyCount`, `InventoryType`,
     `AllowableClass`, `AllowableRace`, `stackable`, `bonding`, `ItemLevel`,
     `RequiredLevel`, `startquest`, `VerifiedBuild`)
VALUES
    (68674, 12, 0, -1, 'Steelback''s Claw',       4808,   1, 0, 8192, 0, 1, 0, -1, -1, 1, 0,  1,  0,     0, 18414),
    (68676, 12, 0, -1, 'Grumpfin''s Eye',          920,   1, 0, 8192, 0, 1, 0, -1, -1, 1, 0,  1,  0,     0, 18414),
    (68680, 12, 0, -1, 'Coconuts',              20921,   1, 0, 8192, 0, 1, 0, -1, -1, 1, 0,  1,  0,     0, 18414),
    (71961, 12, 0, -1, 'Plump Frog',            66265,   1, 0, 8192, 0, 1, 0, -1, -1, 1, 0,  1,  0,     0, 18414),
    (73366, 12, 0, -1, 'Waterlogged Scraps',    36571,   1, 0, 8192, 0, 1, 0, -1, -1, 1, 0,  1,  0,     0, 18414),
    (93396, 12, 0, -1, 'Plundered Profferings',119811,   1, 0, 8192, 0, 1, 0, -1, -1, 1, 0,  1,  0,     0, 18414),
    (93660, 12, 0, -1, 'Thunder-Laced Egg',    119884,   1, 0, 8192, 0, 1, 0, -1, -1, 1, 1, 90, 90, 32475, 18414);
