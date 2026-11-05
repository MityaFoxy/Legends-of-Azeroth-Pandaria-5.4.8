-- Quarantine achievement rows that belong to superseded pre-MoP paths while
-- retaining their complete payload for inspection and manual restoration.
-- Exact-match archive joins make this migration safe to reapply and prevent a
-- conflicting archive row from authorizing removal of live data.

CREATE TABLE IF NOT EXISTS `achievement_criteria_data_disabled_archive` LIKE `achievement_criteria_data`;
CREATE TABLE IF NOT EXISTS `achievement_reward_locale_retired_archive` LIKE `achievement_reward_locale`;

START TRANSACTION;

-- SkyFire retired database difficulty requirements in 2011 after moving them
-- into client achievement conditions. Every listed 5.4.8 criterion already
-- has ModifierTree condition 20 (instance difficulty) with value 1.
INSERT IGNORE INTO `achievement_criteria_data_disabled_archive`
SELECT * FROM `achievement_criteria_data`
WHERE `criteria_id` IN
      (6803,7315,7318,7319,7320,7361,7363,7579,7583,7587,7590,7593,7598,
       11789,12752,12976,12993)
  AND `type` = 12 AND `value1` = 1 AND `value2` = 0 AND `ScriptName` = '';

DELETE live
FROM `achievement_criteria_data` live
JOIN `achievement_criteria_data_disabled_archive` archived
  ON archived.`criteria_id` = live.`criteria_id`
 AND archived.`type` = live.`type`
 AND archived.`value1` = live.`value1`
 AND archived.`value2` = live.`value2`
 AND archived.`ScriptName` = live.`ScriptName`
WHERE live.`criteria_id` IN
      (6803,7315,7318,7319,7320,7361,7363,7579,7583,7587,7590,7593,7598,
       11789,12752,12976,12993)
  AND live.`type` = 12 AND live.`value1` = 1 AND live.`value2` = 0
  AND live.`ScriptName` = '';

-- These hooks have no script name because their active MoP implementations no
-- longer use achievement_criteria_data scripts: Keleseth and Volkhan award the
-- achievements directly, while Ashbury and Mandokir update ModifierTree state.
INSERT IGNORE INTO `achievement_criteria_data_disabled_archive`
SELECT * FROM `achievement_criteria_data`
WHERE `criteria_id` IN (7231,7321,16081,16848)
  AND `type` = 11 AND `value1` = 0 AND `value2` = 0 AND `ScriptName` = '';

DELETE live
FROM `achievement_criteria_data` live
JOIN `achievement_criteria_data_disabled_archive` archived
  ON archived.`criteria_id` = live.`criteria_id`
 AND archived.`type` = live.`type`
 AND archived.`value1` = live.`value1`
 AND archived.`value2` = live.`value2`
 AND archived.`ScriptName` = live.`ScriptName`
WHERE live.`criteria_id` IN (7231,7321,16081,16848)
  AND live.`type` = 11 AND live.`value1` = 0 AND live.`value2` = 0
  AND live.`ScriptName` = '';

-- 2145 and 3656 are retired faction-era IDs. Archive only locale rows that are
-- byte-for-byte duplicates of their active 5.4.8 replacements, and only while
-- the corresponding replacement reward exists.
INSERT IGNORE INTO `achievement_reward_locale_retired_archive`
SELECT legacy.*
FROM `achievement_reward_locale` legacy
JOIN
(
    SELECT 2145 AS `legacy_id`, 2144 AS `active_id`
    UNION ALL
    SELECT 3656 AS `legacy_id`, 3478 AS `active_id`
) mapping ON mapping.`legacy_id` = legacy.`ID`
JOIN `achievement_reward` reward ON reward.`entry` = mapping.`active_id`
JOIN `achievement_reward_locale` active
  ON active.`ID` = mapping.`active_id` AND active.`Locale` = legacy.`Locale`
WHERE BINARY legacy.`Subject` <=> BINARY active.`Subject`
  AND BINARY legacy.`Body` <=> BINARY active.`Body`;

DELETE legacy
FROM `achievement_reward_locale` legacy
JOIN
(
    SELECT 2145 AS `legacy_id`, 2144 AS `active_id`
    UNION ALL
    SELECT 3656 AS `legacy_id`, 3478 AS `active_id`
) mapping ON mapping.`legacy_id` = legacy.`ID`
JOIN `achievement_reward` reward ON reward.`entry` = mapping.`active_id`
JOIN `achievement_reward_locale` active
  ON active.`ID` = mapping.`active_id` AND active.`Locale` = legacy.`Locale`
JOIN `achievement_reward_locale_retired_archive` archived
  ON archived.`ID` = legacy.`ID` AND archived.`Locale` = legacy.`Locale`
 AND BINARY archived.`Subject` <=> BINARY legacy.`Subject`
 AND BINARY archived.`Body` <=> BINARY legacy.`Body`
WHERE BINARY legacy.`Subject` <=> BINARY active.`Subject`
  AND BINARY legacy.`Body` <=> BINARY active.`Body`;

-- 1681/1682 are the retired faction-specific Loremaster achievements. Their
-- texts are retained as evidence for a future faction-aware reward for 7520.
-- 4784/4785 are retired emblem-quartermaster achievements with no 5.4.8 entry.
INSERT IGNORE INTO `achievement_reward_locale_retired_archive`
SELECT * FROM `achievement_reward_locale`
WHERE `ID` IN (1681,1682,4784,4785);

DELETE live
FROM `achievement_reward_locale` live
JOIN `achievement_reward_locale_retired_archive` archived
  ON archived.`ID` = live.`ID`
 AND archived.`Locale` = live.`Locale`
 AND BINARY archived.`Subject` <=> BINARY live.`Subject`
 AND BINARY archived.`Body` <=> BINARY live.`Body`
WHERE live.`ID` IN (1681,1682,4784,4785);

-- Brew of the Month remains active in 5.4.8. Restore its verified welcome
-- letter without replacing any existing or custom reward configuration.
INSERT INTO `achievement_reward`
    (`entry`, `title_A`, `title_H`, `item`, `spell`, `sender`, `subject`, `text`)
SELECT
    2796, 0, 0, 0, 0, 27487,
    'Welcome to the Brew of the Month Club!',
    '$N,$B$BWelcome to the Brew of the Month club! This club is dedicated to bringing you some of the finest brew in all the realms.$B$BEvery month a new brew will be mailed directly to you. If you enjoy that brew and want more, talk to the Brew of the Month club members there.$B$BAgain, welcome to the club, $N.$B$B- Brew of the Month Club'
FROM `creature_template` sender
WHERE sender.`entry` = 27487
  AND NOT EXISTS
  (
      SELECT 1 FROM `achievement_reward` WHERE `entry` = 2796
  );

COMMIT;
