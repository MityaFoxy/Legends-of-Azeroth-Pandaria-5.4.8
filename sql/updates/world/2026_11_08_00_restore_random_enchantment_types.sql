-- Restore property/suffix namespaces in seven inherited enchantment pools.
-- 281 is ItemRandomSuffix "of the Feverflare", not an ItemRandomProperties ID.
-- The 2024-07-22 base has the categories reversed for pools 460/461 and
-- misplaced suffix rows in 458/462/463/464/465. Even IDs present in BOTH DBCs
-- (e.g. 287 and 360..363) have different effects and must keep their namespace.
-- Sources/evidence: doc/item_random_enchantment_audit.md.
-- Legacy property rows/weights corroborated by MaNGOS Four Database commit
-- 8b798ac6a6a51c0c00c7e20c0a864793eb53904c, item_enchantment_template.sql.
-- Keep every ID and chance. Do not normalize uncertain historical weights.
-- Guard each pool as a unit: missing/customized rows or destination collisions
-- leave that pool unchanged. Already-correct rows allow safe reapplication.

CREATE TEMPORARY TABLE `_enchantment_type_repair_20261108`
(
    `entry` MEDIUMINT UNSIGNED NOT NULL,
    `ench` MEDIUMINT UNSIGNED NOT NULL,
    `chance` FLOAT UNSIGNED NOT NULL,
    `old_type` TINYINT UNSIGNED NOT NULL,
    `new_type` TINYINT UNSIGNED NOT NULL,
    PRIMARY KEY (`entry`, `ench`)
);
INSERT INTO `_enchantment_type_repair_20261108`
    (`entry`, `ench`, `chance`, `old_type`, `new_type`) VALUES
    (458, 272, 35.5, 0, 1),
    (458, 273, 31.9, 0, 1),
    (458, 274, 32.6, 0, 1),
    (460, 280, 25.2, 0, 1),
    (460, 281, 26.6, 0, 1),
    (460, 282, 23.2, 0, 1),
    (460, 283, 25, 0, 1),
    (460, 360, 25.4, 0, 1),
    (460, 361, 26.4, 0, 1),
    (460, 362, 23.2, 0, 1),
    (460, 363, 25, 0, 1),
    (461, 284, 24.9, 0, 1),
    (461, 285, 24.8, 0, 1),
    (461, 286, 24.4, 0, 1),
    (461, 287, 26, 0, 1),
    (461, 360, 24.7, 0, 1),
    (461, 361, 24.8, 0, 1),
    (461, 362, 24.6, 0, 1),
    (461, 363, 25.9, 0, 1),
    (462, 288, 24.2, 0, 1),
    (462, 289, 23.9, 0, 1),
    (462, 290, 27.2, 0, 1),
    (462, 291, 24.7, 0, 1),
    (463, 292, 29.7, 0, 1),
    (463, 293, 22.8, 0, 1),
    (463, 294, 21.6, 0, 1),
    (463, 295, 26, 0, 1),
    (464, 288, 25.1, 0, 1),
    (464, 289, 25.6, 0, 1),
    (464, 290, 25.7, 0, 1),
    (464, 291, 23.6, 0, 1),
    (465, 292, 27, 0, 1),
    (465, 293, 22.7, 0, 1),
    (465, 294, 25, 0, 1),
    (465, 295, 25.4, 0, 1),
    (460, 176, 4.72, 1, 0),
    (460, 177, 4.72, 1, 0),
    (460, 181, 4.77, 1, 0),
    (460, 182, 4.77, 1, 0),
    (460, 186, 3.2, 1, 0),
    (460, 187, 3.2, 1, 0),
    (460, 769, 6.64, 1, 0),
    (460, 770, 6.64, 1, 0),
    (460, 771, 6.64, 1, 0),
    (460, 772, 6.64, 1, 0),
    (460, 854, 3.69, 1, 0),
    (460, 855, 3.69, 1, 0),
    (460, 856, 3.69, 1, 0),
    (460, 857, 3.69, 1, 0),
    (460, 1024, 4.58, 1, 0),
    (460, 1025, 4.58, 1, 0),
    (460, 1026, 4.58, 1, 0),
    (460, 1027, 4.58, 1, 0),
    (460, 1704, 0.1, 1, 0),
    (460, 1808, 2.9, 1, 0),
    (460, 1809, 2.9, 1, 0),
    (460, 1846, 1.56, 1, 0),
    (460, 1847, 1.56, 1, 0),
    (460, 1960, 3.02, 1, 0),
    (460, 1961, 3.02, 1, 0),
    (461, 178, 4.8, 1, 0),
    (461, 183, 4.99, 1, 0),
    (461, 188, 3.34, 1, 0),
    (461, 213, 4.8, 1, 0),
    (461, 215, 4.99, 1, 0),
    (461, 217, 3.34, 1, 0),
    (461, 772, 6.58, 1, 0),
    (461, 773, 6.58, 1, 0),
    (461, 774, 6.58, 1, 0),
    (461, 775, 6.58, 1, 0),
    (461, 857, 3.53, 1, 0),
    (461, 858, 3.53, 1, 0),
    (461, 859, 3.53, 1, 0),
    (461, 860, 3.53, 1, 0),
    (461, 1027, 4.46, 1, 0),
    (461, 1028, 4.46, 1, 0),
    (461, 1029, 4.46, 1, 0),
    (461, 1030, 4.46, 1, 0),
    (461, 1810, 3.19, 1, 0),
    (461, 1811, 3.19, 1, 0),
    (461, 1848, 1.59, 1, 0),
    (461, 1849, 1.59, 1, 0),
    (461, 1962, 2.91, 1, 0),
    (461, 1963, 2.91, 1, 0);

CREATE TEMPORARY TABLE `_enchantment_type_counts_20261108`
    (`entry` MEDIUMINT UNSIGNED PRIMARY KEY, `expected` INT UNSIGNED NOT NULL);
INSERT INTO `_enchantment_type_counts_20261108`
SELECT `entry`, COUNT(*) FROM `_enchantment_type_repair_20261108` GROUP BY `entry`;
CREATE TEMPORARY TABLE `_enchantment_type_ready_20261108`
    (`entry` MEDIUMINT UNSIGNED PRIMARY KEY);

START TRANSACTION;
-- Lock both possible keys, including any conflicting pre-existing row.
SELECT e.`entry`, e.`ench`, e.`type`
FROM `item_enchantment_template` e
JOIN `_enchantment_type_repair_20261108` p
  ON p.`entry` = e.`entry` AND p.`ench` = e.`ench`
WHERE e.`type` IN (p.`old_type`, p.`new_type`)
FOR UPDATE;

INSERT INTO `_enchantment_type_ready_20261108`
SELECT p.`entry`
FROM `_enchantment_type_repair_20261108` p
JOIN `_enchantment_type_counts_20261108` c ON c.`entry` = p.`entry`
LEFT JOIN `item_enchantment_template` e
  ON e.`entry` = p.`entry` AND e.`ench` = p.`ench`
 AND e.`type` IN (p.`old_type`, p.`new_type`)
GROUP BY p.`entry`
HAVING COUNT(e.`entry`) = MAX(c.`expected`)
   AND COUNT(DISTINCT e.`ench`) = MAX(c.`expected`)
   AND SUM(e.`chance` = p.`chance`) = MAX(c.`expected`);

UPDATE `item_enchantment_template` e
JOIN `_enchantment_type_repair_20261108` p
  ON p.`entry` = e.`entry` AND p.`ench` = e.`ench`
JOIN `_enchantment_type_ready_20261108` ready ON ready.`entry` = e.`entry`
SET e.`type` = p.`new_type`
WHERE e.`type` = p.`old_type` AND e.`chance` = p.`chance`;
COMMIT;

DROP TEMPORARY TABLE `_enchantment_type_ready_20261108`;
DROP TEMPORARY TABLE `_enchantment_type_counts_20261108`;
DROP TEMPORARY TABLE `_enchantment_type_repair_20261108`;
