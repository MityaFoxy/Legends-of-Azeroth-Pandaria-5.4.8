-- Defias Envoker and Defias Miner use Renegade Strength. 91009 is the
-- corresponding 5.4.8 spell; the two legacy IDs below are absent from the DBC.
UPDATE `smart_scripts`
SET `action_param1` = 91009
WHERE `source_type` = 0
  AND `action_type` = 11
  AND (`entryorguid`, `id`) IN ((48418, 14), (48419, 1))
  AND `action_param1` IN (91006, 91010);
