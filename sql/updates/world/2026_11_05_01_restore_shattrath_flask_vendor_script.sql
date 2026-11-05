-- Arcanist Xorith and Haldor the Compulsive use a C++ gossip script to expose
-- their Mark of the Illidari flask inventory only to players exalted with the
-- required Outland factions. Their empty SmartAI binding bypasses that check.
-- Restore the 5.4.8 SkyFire binding only while no custom SmartAI rows exist.
UPDATE `creature_template` template
SET `AIName` = '',
    `ScriptName` = 'npc_shattrathflaskvendors'
WHERE template.`entry` IN (23483, 23484)
  AND template.`AIName` = 'SmartAI'
  AND template.`ScriptName` = ''
  AND NOT EXISTS
  (
      SELECT 1
      FROM `smart_scripts` script
      WHERE script.`entryorguid` = template.`entry`
        AND script.`source_type` = 0
  );
