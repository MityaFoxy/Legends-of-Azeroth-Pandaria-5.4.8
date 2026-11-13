-- Read-only post-migration checks for 2026_10_31_01.
-- Run with the audited world database selected. No data is changed here.

SELECT 'Powder Round uses native DBC quest credit' AS check_name,
       IF(COUNT(*) = 0, 'PASS', 'FAIL') AS result
FROM `spell_scripts`
WHERE `id` = 130973 AND `effIndex` = 0 AND `command` = 8
  AND `datalong` IN (66200,66203);

SELECT 'stale Powder Round commands recoverable' AS check_name,
       IF(COUNT(*) = 2, 'PASS', 'FAIL') AS result
FROM `spell_scripts_startup_archive`
WHERE `id` = 130973 AND `effIndex` = 0 AND `command` = 8
  AND `datalong` IN (66200,66203);

SELECT 'Remove Talent rank chain bound once' AS check_name,
       IF(SUM(`spell_id` = -127650) = 1
          AND SUM(`spell_id` IN (113873,127649,127650)) = 0,
          'PASS', 'FAIL') AS result
FROM `spell_script_names`
WHERE `ScriptName` = 'spell_common_unlearn_talent';

SELECT 'Remove Talent source bindings recoverable' AS check_name,
       IF(COUNT(*) = 3, 'PASS', 'FAIL') AS result
FROM `spell_script_names_startup_archive`
WHERE `spell_id` IN (113873,127649,127650)
  AND `ScriptName` = 'spell_common_unlearn_talent';

SELECT 'all active waypoint talks resolve' AS check_name,
       IF(COUNT(*) = 0, 'PASS', 'FAIL') AS result
FROM `waypoint_scripts` ws
LEFT JOIN `broadcast_text` bt ON bt.`ID` = ws.`dataint`
WHERE ws.`command` = 0
  AND (ws.`dataint` = 0 OR bt.`ID` IS NULL);

SELECT '69 source-backed waypoint talks restored' AS check_name,
       IF(COUNT(*) = 69, 'PASS', 'FAIL') AS result
FROM `waypoint_scripts` ws
JOIN `broadcast_text` bt ON bt.`ID` = ws.`dataint`
WHERE ws.`guid` IN
    (1,2,300,50,51,98,99,140,141,
     142,143,144,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,
     343,344,345,346,347,348,349,350,351,352,353,354,355,356,357,358,359,360,
     160,250,251,404,252,253,254,255,256,257,258,259,264,265,405,266,406,267,
     407,272,409,273,274,275)
  AND ws.`command` = 0 AND ws.`dataint` <> 0;

SELECT 'obsolete waypoint scripts inactive' AS check_name,
       IF(COUNT(*) = 0, 'PASS', 'FAIL') AS result
FROM `waypoint_scripts`
WHERE `id` BETWEEN 57 AND 95 OR `id` BETWEEN 147 AND 153;

SELECT 'obsolete waypoint commands recoverable' AS check_name,
       IF(COUNT(*) = 81, 'PASS', 'FAIL') AS result
FROM `waypoint_scripts_startup_archive`
WHERE `id` BETWEEN 57 AND 95 OR `id` BETWEEN 147 AND 153;

SELECT 'placeholder boss and Caliph actions retired' AS check_name,
       IF(COUNT(*) = 0, 'PASS', 'FAIL') AS result
FROM `waypoint_data`
WHERE `action` IN (332,333,334,335,336,337,567,568,569,570,571,572);

SELECT 'retired action points recoverable' AS check_name,
       IF(COUNT(*) = 12, 'PASS', 'FAIL') AS result
FROM `waypoint_data_startup_archive`
WHERE `action` IN (332,333,334,335,336,337,567,568,569,570,571,572);

SELECT 'no koKR rows added for legacy waypoint text' AS check_name,
       IF(COUNT(*) = 0, 'PASS', 'FAIL') AS result
FROM `broadcast_text_locale`
WHERE `locale` = 'koKR'
  AND `ID` IN (2000000133,2000000134,2000000139,2000000142,2000000143,
               2000000144,2000000145,2000000203,2000000204,2000000221,
               2000000223,2000000224,2000000225);
