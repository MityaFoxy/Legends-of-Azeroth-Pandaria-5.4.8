-- Correct stale labels while preserving the verified live resource topology.
-- Pool 30091 contains only Jade Forest Fool's Cap (209355) spawns.
UPDATE `pool_template`
SET `description` = 'The Jade Forest (5785) - Fool''s Cap (209355)'
WHERE `entry` = 30091
  AND `description` = 'The Jade Forest (5785) - Sha-Touched Herb (214510)';

-- Pool 30098 contains only Valley of the Four Winds Ghost Iron Deposit
-- (209311) spawns; it is neither Rich Ghost Iron nor template 209328.
UPDATE `pool_template`
SET `description` = 'Valley of the Four Winds (5805) - Ghost Iron Deposit (209311)'
WHERE `entry` = 30098
  AND `description` = 'Valley of the Four Winds (5805) - Rich Ghost Iron Deposit (209328)';
