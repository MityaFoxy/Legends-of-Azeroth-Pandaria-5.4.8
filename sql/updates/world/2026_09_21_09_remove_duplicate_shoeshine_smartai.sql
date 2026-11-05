-- The Shoeshine Seat uses gameobject template 194115 and action list 19411500.
-- These rows are exact legacy duplicates under a non-existent gameobject
-- template (96036). Keeping them only makes SmartAIMgr reject the trigger;
-- the live 194115 script retains the complete shoeshine sequence.
DELETE FROM `smart_scripts`
WHERE (`entryorguid` = 96036 AND `source_type` = 1)
   OR (`entryorguid` = 9603600 AND `source_type` = 9);
