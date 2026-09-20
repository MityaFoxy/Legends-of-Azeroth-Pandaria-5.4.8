-- Zidormi is handled by the dedicated C++ gossip AI.  A stale SmartAI row
-- used an action from a different core revision and prevented that handler
-- from being selected.
DELETE FROM `smart_scripts`
WHERE `entryorguid` = 31848 AND `source_type` = 0;

UPDATE `creature_template`
SET `AIName` = '', `ScriptName` = 'npc_zidormi_dalaran'
WHERE `entry` = 31848;
