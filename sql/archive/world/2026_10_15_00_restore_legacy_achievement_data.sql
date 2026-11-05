-- MANUAL RESTORE ONLY. Do not add this file to the automatic world update path.
-- Restoring these rows on the current 5.4.8 core also restores the associated
-- startup diagnostics. Review doc/world_data_archive_registry.md first.

START TRANSACTION;

INSERT IGNORE INTO `achievement_criteria_data`
SELECT * FROM `achievement_criteria_data_disabled_archive`
WHERE (`criteria_id` IN
       (6803,7315,7318,7319,7320,7361,7363,7579,7583,7587,7590,7593,7598,
        11789,12752,12976,12993)
       AND `type` = 12 AND `value1` = 1 AND `value2` = 0 AND `ScriptName` = '')
   OR (`criteria_id` IN (7231,7321,16081,16848)
       AND `type` = 11 AND `value1` = 0 AND `value2` = 0 AND `ScriptName` = '');

INSERT IGNORE INTO `achievement_reward_locale`
SELECT * FROM `achievement_reward_locale_retired_archive`
WHERE `ID` IN (1681,1682,2145,3656,4784,4785);

COMMIT;
