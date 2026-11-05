-- Restore the 5.4.8 ItemExtendedCost IDs for legacy PvP vendors.
--
-- These inventories were imported with post-MoP cost IDs 5962, 5963, 5964
-- and 5966. They do not exist in the 5.4.8 (build 18414)
-- ItemExtendedCost.db2, whose highest ID is 5280. Every retained item has an
-- exact counterpart in an existing 5.4.8 legacy vendor inventory. Copy the
-- per-item cost from those inventories so weapon and armour price tiers are
-- preserved instead of replacing the four foreign IDs with guessed values.

-- Xazi Smolderpipe: Wrathful Gladiator armour and weapons.
UPDATE `npc_vendor` AS `target`
JOIN `npc_vendor` AS `reference`
  ON `reference`.`item` = `target`.`item`
 AND `reference`.`entry` IN (12784, 12785)
SET `target`.`ExtendedCost` = `reference`.`ExtendedCost`
WHERE `target`.`entry` = 69971
  AND `target`.`ExtendedCost` IN (5962, 5963, 5964, 5966);

-- Zom Bocom: Relentless Gladiator armour, accessories and weapons.
UPDATE `npc_vendor` AS `target`
JOIN `npc_vendor` AS `reference`
  ON `reference`.`item` = `target`.`item`
 AND `reference`.`entry` IN (33924, 34038)
SET `target`.`ExtendedCost` = `reference`.`ExtendedCost`
WHERE `target`.`entry` = 69973
  AND `target`.`ExtendedCost` IN (5962, 5963, 5964, 5966);

-- Alliance Ruthless/Cataclysmic legacy vendors. Kylo Kelwin owns the armour
-- prices and Herwin Steampop owns the weapon prices.
UPDATE `npc_vendor` AS `target`
JOIN `npc_vendor` AS `reference`
  ON `reference`.`item` = `target`.`item`
 AND `reference`.`entry` IN (69318, 69321)
SET `target`.`ExtendedCost` = `reference`.`ExtendedCost`
WHERE `target`.`entry` IN (69974, 69975)
  AND `target`.`ExtendedCost` IN (5962, 5963, 5964, 5966);

-- Horde Ruthless/Cataclysmic legacy vendors. Capps Carlin owns the armour
-- prices and Tiny Tayger owns the weapon prices.
UPDATE `npc_vendor` AS `target`
JOIN `npc_vendor` AS `reference`
  ON `reference`.`item` = `target`.`item`
 AND `reference`.`entry` IN (69322, 69323)
SET `target`.`ExtendedCost` = `reference`.`ExtendedCost`
WHERE `target`.`entry` IN (69977, 69978)
  AND `target`.`ExtendedCost` IN (5962, 5963, 5964, 5966);
