-- These templates have no template-level or spawn-specific SmartAI content.
-- Their gameplay comes from static template data, quest relations, external
-- controllers, or the core's default creature/gameobject AI. Do not leave an
-- empty SmartAI engine attached, and do not override any custom DB scripts.
UPDATE `creature_template` template
SET `AIName` = ''
WHERE template.`entry` IN (16764, 17364, 19871, 21210, 21419, 24042)
  AND template.`AIName` = 'SmartAI'
  AND template.`ScriptName` = ''
  AND NOT EXISTS
  (
      SELECT 1
      FROM `smart_scripts` script
      WHERE script.`entryorguid` = template.`entry`
        AND script.`source_type` = 0
  )
  AND NOT EXISTS
  (
      SELECT 1
      FROM `creature` spawn
      JOIN `smart_scripts` script
        ON script.`entryorguid` = -CAST(spawn.`guid` AS SIGNED)
       AND script.`source_type` = 0
      WHERE spawn.`id` = template.`entry`
  );

-- Ball and Chain is a goober whose lock, spell and interaction behavior are
-- fully defined by gameobject_template. SkyFire 5.4.8 has no SmartGO script.
UPDATE `gameobject_template` template
SET `AIName` = ''
WHERE template.`entry` = 205098
  AND template.`AIName` = 'SmartGameObjectAI'
  AND template.`ScriptName` = ''
  AND NOT EXISTS
  (
      SELECT 1
      FROM `smart_scripts` script
      WHERE script.`entryorguid` = template.`entry`
        AND script.`source_type` = 1
  )
  AND NOT EXISTS
  (
      SELECT 1
      FROM `gameobject` spawn
      JOIN `smart_scripts` script
        ON script.`entryorguid` = -CAST(spawn.`guid` AS SIGNED)
       AND script.`source_type` = 1
      WHERE spawn.`id` = template.`entry`
  );
