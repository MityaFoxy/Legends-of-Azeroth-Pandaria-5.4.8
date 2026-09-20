-- SmartAI scripts already exist for these templates, but the corresponding
-- AI handler was never assigned.  Without this, the scripts are loaded yet
-- cannot run for the spawned creature or gameobject.
UPDATE `creature_template`
SET `AIName` = 'SmartAI'
WHERE `entry` IN (
    18166, 25967, 30134, 31428, 31432, 31848, 35589, 35604, 37063,
    64267, 64360, 64362, 64363, 64364, 64656, 66654
) AND `AIName` = '';

UPDATE `gameobject_template`
SET `AIName` = 'SmartGameObjectAI'
WHERE `entry` IN (181058, 187073, 190555) AND `AIName` = '';
